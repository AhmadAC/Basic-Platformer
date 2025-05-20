# editor/minimap_widget.py
# -*- coding: utf-8 -*-
"""
## version 2.0.3 (Fixed QRectF.toTuple() error)
## version 2.0.4 (Enhanced object rendering with category-specific colors)
Minimap Widget for the Platformer Level Editor.
Displays a scaled-down overview of the map and the current viewport.
Allows navigation by clicking or dragging on the minimap.
"""
import logging
from typing import Optional, TYPE_CHECKING, Tuple

from PySide6.QtWidgets import (
    QWidget,
    QSizePolicy
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QPaintEvent, QPixmap
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Slot, QSize

from . import editor_config as ED_CONFIG # Use relative import
from .editor_state import EditorState # Use relative import

if TYPE_CHECKING:
    from .map_view_widget import MapViewWidget # Use relative import

logger = logging.getLogger(__name__)

class MinimapWidget(QWidget):
    def __init__(self, editor_state: EditorState, map_view_ref: 'MapViewWidget', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.map_view_ref = map_view_ref

        self.setMinimumSize(100, 75)
        # Allow it to be larger if space permits, but respect preferredSize as a base
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._map_content_pixmap: Optional[QPixmap] = None
        self._view_rect_on_minimap = QRectF()
        
        self._is_dragging_view_rect = False
        self._drag_offset = QPointF()

        self.view_rect_update_timer = QTimer(self)
        self.view_rect_update_timer.setInterval(ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS) # Default 50ms
        self.view_rect_update_timer.timeout.connect(self.schedule_view_rect_update_and_repaint)
        self.view_rect_update_timer.start()

        self.setMouseTracking(True)
        self.schedule_map_content_redraw() # Initial draw

        logger.info(f"MinimapWidget initialized. Update interval: {ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS}ms.")

    def sizeHint(self) -> QSize:
        # Return a reasonable default preferred size
        return QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT)

    @Slot()
    def schedule_map_content_redraw(self):
        logger.debug("Minimap: Map content redraw scheduled (invalidating content pixmap).")
        self._map_content_pixmap = None # Invalidate to force redraw
        self.update_view_rect() # Update view rect based on new content potentially
        self.update() # Schedule a repaint of the widget

    @Slot()
    def schedule_view_rect_update_and_repaint(self):
        needs_repaint = self.update_view_rect()
        if needs_repaint:
            self.update() # Schedule a repaint of the widget

    def _get_map_to_minimap_transform(self) -> Tuple[float, float, float, float, float, float, float]:
        # Uses the full map dimensions from editor_state for scaling calculations
        map_px_w = float(self.editor_state.get_map_pixel_width())
        map_px_h = float(self.editor_state.get_map_pixel_height())
        
        widget_w = float(self.width())
        widget_h = float(self.height())

        if map_px_w <= 1e-6 or map_px_h <= 1e-6 or widget_w <= 1e-6 or widget_h <= 1e-6:
            logger.warning(f"Minimap transform: Invalid dimensions. map_px: ({map_px_w}x{map_px_h}), widget: ({widget_w}x{widget_h})")
            return 0.0, 0.0, 0.0, 0.0, 0.0, max(1.0, map_px_w), max(1.0, map_px_h)

        scale_x = widget_w / map_px_w
        scale_y = widget_h / map_px_h
        final_scale = min(scale_x, scale_y) # Fit entire map within widget
        
        if final_scale <= 1e-6: final_scale = 0.0 # Avoid tiny or zero scale

        # Effective dimensions of the map drawing area on the minimap
        eff_w = map_px_w * final_scale
        eff_h = map_px_h * final_scale
        
        # Centering offsets
        offset_x = (widget_w - eff_w) / 2.0
        offset_y = (widget_h - eff_h) / 2.0
        
        return final_scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h

    def _render_map_content_to_pixmap(self):
        logger.debug(f"Minimap: Rendering map content. Widget size: {self.size()}")
        current_widget_size = self.size()
        if current_widget_size.isEmpty() or current_widget_size.width() <=0 or current_widget_size.height() <=0:
            logger.warning("Minimap: Cannot render content, widget size is invalid.")
            self._map_content_pixmap = QPixmap(1,1); self._map_content_pixmap.fill(Qt.GlobalColor.magenta)
            return

        self._map_content_pixmap = QPixmap(current_widget_size)
        self._map_content_pixmap.fill(Qt.GlobalColor.transparent) # Start with transparent

        painter = QPainter(self._map_content_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Usually better for pixel art

        scale, eff_w, eff_h, offset_x, offset_y, map_px_w_orig, map_px_h_orig = self._get_map_to_minimap_transform()

        # Draw the map background color onto the effective map area on the minimap
        map_bg_rect_on_minimap = QRectF(offset_x, offset_y, max(0.0, eff_w), max(0.0, eff_h))
        map_bg_qcolor = QColor(*self.editor_state.background_color)
        painter.fillRect(map_bg_rect_on_minimap, map_bg_qcolor)

        # Define colors for different object categories on the minimap (customize as needed)
        category_colors = {
            "spawn": QColor(0, 255, 0, 180),    # Green
            "enemy": QColor(255, 0, 0, 180),    # Red
            "item": QColor(255, 255, 0, 180),   # Yellow
            "object": QColor(0, 0, 255, 180),   # Blue (e.g., stones)
            "hazard": QColor(255, 100, 0, 200), # Orange/Red (e.g., lava)
            "tile": QColor(150, 150, 150, 200), # Default for tiles if no override_color
            "unknown": QColor(255, 0, 255, 150) # Magenta for unknown
        }
        default_tile_color = category_colors["tile"]
        
        painter.setPen(Qt.PenStyle.NoPen) # Draw filled rectangles without outlines for objects

        if scale > 1e-5 and self.editor_state.placed_objects:
            fixed_obj_dot_size_px = max(1.0, getattr(ED_CONFIG, 'MINIMAP_OBJECT_REPRESENTATION_SIZE_PX', 2.0))

            for obj_data in self.editor_state.placed_objects:
                world_x = float(obj_data.get("world_x", 0.0))
                world_y = float(obj_data.get("world_y", 0.0))
                asset_key = obj_data.get("asset_editor_key", "unknown_asset")
                asset_info = self.editor_state.assets_palette.get(str(asset_key))
                
                if not asset_info:
                    logger.warning(f"Minimap render: Asset info for '{asset_key}' not found. Skipping object.")
                    continue

                obj_orig_w, obj_orig_h = float(ED_CONFIG.BASE_GRID_SIZE), float(ED_CONFIG.BASE_GRID_SIZE)
                orig_size_tuple = asset_info.get("original_size_pixels")
                if orig_size_tuple and len(orig_size_tuple) == 2:
                    obj_orig_w, obj_orig_h = float(orig_size_tuple[0]), float(orig_size_tuple[1])
                
                # Position on minimap (top-left of object)
                mini_x = offset_x + (world_x * scale)
                mini_y = offset_y + (world_y * scale)
                
                obj_category = asset_info.get("category", "unknown")
                object_qcolor: QColor

                # For tiles, try to use their actual color and scaled size
                if obj_category == "tile" or "platform" in obj_data.get("game_type_id", ""):
                    rect_w_on_minimap = max(1.0, obj_orig_w * scale)
                    rect_h_on_minimap = max(1.0, obj_orig_h * scale)
                    draw_rect = QRectF(mini_x, mini_y, rect_w_on_minimap, rect_h_on_minimap)
                    
                    color_tuple = obj_data.get("override_color")
                    if not color_tuple: # If no override, try base color from palette asset
                        color_tuple = asset_info.get("base_color_tuple")
                        if not color_tuple: # If still no color, check surface_params
                            sp = asset_info.get("surface_params")
                            if sp and isinstance(sp, tuple) and len(sp) == 3:
                                color_tuple = sp[2] # (width, height, color_tuple)
                    object_qcolor = QColor(*color_tuple) if color_tuple else default_tile_color
                else: # For non-tile objects (characters, items), draw a fixed-size dot
                     # Center the dot representation
                     centered_mini_x = mini_x + (obj_orig_w * scale / 2.0) - (fixed_obj_dot_size_px / 2.0)
                     centered_mini_y = mini_y + (obj_orig_h * scale / 2.0) - (fixed_obj_dot_size_px / 2.0)
                     draw_rect = QRectF(centered_mini_x, centered_mini_y, fixed_obj_dot_size_px, fixed_obj_dot_size_px)
                     object_qcolor = category_colors.get(obj_category, category_colors["unknown"])
                
                if object_qcolor.alpha() > 0: # Only draw if not fully transparent
                    painter.setBrush(object_qcolor)
                    painter.drawRect(draw_rect)
        
        painter.end()
        logger.debug("Minimap: Finished rendering map content to pixmap.")

    def update_view_rect(self) -> bool:
        if not self.map_view_ref: return False
        
        # Get transformation parameters based on the full map size
        scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
        old_view_rect = QRectF(self._view_rect_on_minimap) # Copy current rect

        if scale <= 1e-6: # If scale is too small or invalid
            self._view_rect_on_minimap = QRectF()
        else:
            # Get the portion of the scene visible in the MapViewWidget
            visible_scene_rect_in_map_coords = self.map_view_ref.get_visible_scene_rect()
            
            # Transform this scene rectangle to minimap coordinates
            vx = offset_x + (visible_scene_rect_in_map_coords.x() * scale)
            vy = offset_y + (visible_scene_rect_in_map_coords.y() * scale)
            vw = visible_scene_rect_in_map_coords.width() * scale
            vh = visible_scene_rect_in_map_coords.height() * scale
            
            self._view_rect_on_minimap = QRectF(vx, vy, max(1.0, vw), max(1.0, vh))
        
        # Check if the view rectangle has actually changed significantly
        changed = (abs(old_view_rect.x() - self._view_rect_on_minimap.x()) > 0.1 or
                   abs(old_view_rect.y() - self._view_rect_on_minimap.y()) > 0.1 or
                   abs(old_view_rect.width() - self._view_rect_on_minimap.width()) > 0.1 or
                   abs(old_view_rect.height() - self._view_rect_on_minimap.height()) > 0.1)
        
        if changed:
            rect_tuple_str = (f"({self._view_rect_on_minimap.x():.1f}, {self._view_rect_on_minimap.y():.1f}, "
                              f"{self._view_rect_on_minimap.width():.1f}, {self._view_rect_on_minimap.height():.1f})")
            logger.debug(f"Minimap: View rect updated to {rect_tuple_str}")
        return changed

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Fill the entire widget background (acts as border/padding area)
        widget_bg_color = QColor(*ED_CONFIG.MINIMAP_BACKGROUND_COLOR_TUPLE)
        painter.fillRect(self.rect(), widget_bg_color)

        if self._map_content_pixmap is None:
            self._render_map_content_to_pixmap() # Render if not already cached
        
        if self._map_content_pixmap and not self._map_content_pixmap.isNull():
            # Draw the cached map content (which itself includes the map's background color)
            painter.drawPixmap(0, 0, self._map_content_pixmap)
        else:
            logger.error("Minimap paintEvent: _map_content_pixmap is None or Null after render attempt!")
            painter.fillRect(self.rect(), Qt.GlobalColor.magenta) # Fallback if rendering failed badly

        # Draw the view rectangle (yellow box)
        if not self._view_rect_on_minimap.isNull() and self._view_rect_on_minimap.isValid():
            painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE), 1.5))
            painter.setBrush(QBrush(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE)))
            painter.drawRect(self._view_rect_on_minimap)

        # Draw a border around the entire minimap widget
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_BORDER_COLOR_TUPLE), 1))
        painter.drawRect(self.rect().adjusted(0,0,-1,-1)) # Adjust to be inside the widget
        
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if not self.map_view_ref: return
        
        scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
        if scale <= 1e-6: return # Cannot interact if map scale is too small

        click_pos_on_widget = event.position()
        
        # Calculate where the click occurred relative to the drawn map content area on the minimap
        map_content_rect_on_widget = QRectF(offset_x, offset_y, eff_w, eff_h)

        if event.button() == Qt.MouseButton.LeftButton:
            if map_content_rect_on_widget.contains(click_pos_on_widget):
                # Click is within the bounds of where map content is drawn
                click_x_rel_to_map_area = click_pos_on_widget.x() - offset_x
                click_y_rel_to_map_area = click_pos_on_widget.y() - offset_y

                # Convert click on minimap's map area to actual map coordinates
                map_coord_x = click_x_rel_to_map_area / scale
                map_coord_y = click_y_rel_to_map_area / scale
                
                # Clamp to actual map boundaries
                clamped_map_coord_x = max(0.0, min(map_coord_x, map_px_w))
                clamped_map_coord_y = max(0.0, min(map_coord_y, map_px_h))

                if self._view_rect_on_minimap.isValid() and self._view_rect_on_minimap.contains(click_pos_on_widget):
                    self._is_dragging_view_rect = True
                    # Calculate offset from top-left of view_rect to the click point
                    self._drag_offset = click_pos_on_widget - self._view_rect_on_minimap.topLeft()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                else:
                    # Clicked outside view_rect but inside map area: center MapView there
                    self.map_view_ref.center_on_map_coords(QPointF(clamped_map_coord_x, clamped_map_coord_y))
            # If click is outside map_content_rect_on_widget, do nothing for left click.
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging_view_rect and self.map_view_ref:
            if not (event.buttons() & Qt.MouseButton.LeftButton): # Mouse button released mid-drag
                self._is_dragging_view_rect = False; self.unsetCursor(); return

            scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
            if scale <= 1e-6: return

            # New desired top-left of the view_rect based on mouse drag and initial offset
            new_view_rect_top_left_on_widget = event.position() - self._drag_offset
            
            # Calculate the center of this new desired view_rect
            target_center_x_on_widget = new_view_rect_top_left_on_widget.x() + self._view_rect_on_minimap.width() / 2.0
            target_center_y_on_widget = new_view_rect_top_left_on_widget.y() + self._view_rect_on_minimap.height() / 2.0

            # Convert this target center on minimap back to actual map coordinates
            actual_target_center_map_x = (target_center_x_on_widget - offset_x) / scale
            actual_target_center_map_y = (target_center_y_on_widget - offset_y) / scale
            
            # Clamp the target map coordinates to be within the map boundaries
            clamped_target_x = max(0.0, min(actual_target_center_map_x, map_px_w))
            clamped_target_y = max(0.0, min(actual_target_center_map_y, map_px_h))
            
            self.map_view_ref.center_on_map_coords(QPointF(clamped_target_x, clamped_target_y))
            # The MapViewWidget.center_on_map_coords will emit view_changed, which triggers update_view_rect
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_view_rect:
            self._is_dragging_view_rect = False
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QPaintEvent): # Param is QResizeEvent
        logger.info(f"Minimap: Resized to {self.size()}. Scheduling content redraw.")
        self.schedule_map_content_redraw() # Redraw content and update view rect
        super().resizeEvent(event)