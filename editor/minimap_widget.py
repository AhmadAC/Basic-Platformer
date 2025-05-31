# editor/minimap_widget.py
# -*- coding: utf-8 -*-
"""
## version 2.2.5 (Selection Pane Hide/Lock Integration - Minimap)
Minimap Widget for the Platformer Level Editor.
- Hidden objects are no longer rendered on the minimap.
"""
import logging
import os # For path joining for custom images on minimap
from typing import Optional, TYPE_CHECKING, Tuple

from PySide6.QtWidgets import (
    QWidget,
    QSizePolicy
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QPaintEvent, QPixmap, QImage
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Slot, QSize

from editor import editor_config as ED_CONFIG
from editor.editor_state import EditorState
from editor import editor_map_utils # For map folder path

if TYPE_CHECKING:
    from editor.map_view_widget import MapViewWidget

logger = logging.getLogger(__name__)

class MinimapWidget(QWidget):
    def __init__(self, editor_state: EditorState, map_view_ref: 'MapViewWidget', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.map_view_ref = map_view_ref

        self.setMinimumSize(100, 75)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self._map_content_pixmap: Optional[QPixmap] = None
        self._view_rect_on_minimap = QRectF()
        
        self._is_dragging_view_rect = False
        self._drag_offset = QPointF()

        self.view_rect_update_timer = QTimer(self)
        self.view_rect_update_timer.setInterval(ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS) # type: ignore
        self.view_rect_update_timer.timeout.connect(self.schedule_view_rect_update_and_repaint)
        self.view_rect_update_timer.start()

        self.setMouseTracking(True)
        self.schedule_map_content_redraw()

        if logger: logger.info(f"MinimapWidget initialized. Update interval: {ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS}ms.") # type: ignore

    def sizeHint(self) -> QSize:
        return QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT) # type: ignore

    @Slot()
    def schedule_map_content_redraw(self):
        if logger: logger.debug("Minimap: Map content redraw scheduled (invalidating content pixmap).")
        self._map_content_pixmap = None
        self.update_view_rect()
        self.update()

    @Slot()
    def schedule_view_rect_update_and_repaint(self):
        needs_repaint = self.update_view_rect()
        if needs_repaint:
            self.update()

    def _get_map_to_minimap_transform(self) -> Tuple[float, float, float, float, float, float, float]:
        map_px_w = float(self.editor_state.get_map_pixel_width())
        map_px_h = float(self.editor_state.get_map_pixel_height())
        
        widget_w = float(self.width())
        widget_h = float(self.height())

        if map_px_w <= 1e-6 or map_px_h <= 1e-6 or widget_w <= 1e-6 or widget_h <= 1e-6:
            if logger: logger.warning(f"Minimap transform: Invalid dimensions. map_px: ({map_px_w}x{map_px_h}), widget: ({widget_w}x{widget_h})")
            return 0.0, 0.0, 0.0, 0.0, 0.0, max(1.0, map_px_w), max(1.0, map_px_h)

        scale_x = widget_w / map_px_w
        scale_y = widget_h / map_px_h
        final_scale = min(scale_x, scale_y)
        
        if final_scale <= 1e-6:
            final_scale = 0.0

        eff_w = map_px_w * final_scale
        eff_h = map_px_h * final_scale
        
        offset_x = (widget_w - eff_w) / 2.0
        offset_y = (widget_h - eff_h) / 2.0
        
        return final_scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h

    def _render_map_content_to_pixmap(self):
        if logger: logger.debug(f"Minimap: Rendering map content. Widget size: {self.size()}")
        current_widget_size = self.size()
        if current_widget_size.isEmpty() or current_widget_size.width() <=0 or current_widget_size.height() <=0:
            if logger: logger.warning("Minimap: Cannot render content, widget size is invalid.")
            self._map_content_pixmap = QPixmap(1,1)
            self._map_content_pixmap.fill(Qt.GlobalColor.magenta)
            return

        self._map_content_pixmap = QPixmap(current_widget_size)
        self._map_content_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self._map_content_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        scale, eff_w, eff_h, offset_x, offset_y, map_px_w_orig, map_px_h_orig = self._get_map_to_minimap_transform()

        map_bg_rect_on_minimap = QRectF(offset_x, offset_y, max(0.0, eff_w), max(0.0, eff_h))
        map_bg_qcolor = QColor(*self.editor_state.background_color)
        painter.fillRect(map_bg_rect_on_minimap, map_bg_qcolor)

        category_colors: Dict[str, QColor] = ED_CONFIG.MINIMAP_CATEGORY_COLORS # type: ignore
        default_obj_color = category_colors.get("unknown", QColor(255, 0, 255, 150))
        
        painter.setPen(Qt.PenStyle.NoPen)

        if scale > 1e-5 and self.editor_state.placed_objects:
            fixed_obj_dot_size_px = max(1.0, getattr(ED_CONFIG, 'MINIMAP_OBJECT_REPRESENTATION_SIZE_PX', 2.0)) # type: ignore

            sorted_objects_for_minimap = sorted(self.editor_state.placed_objects, key=lambda obj: obj.get("layer_order", 0))

            for obj_data in sorted_objects_for_minimap:
                if obj_data.get("editor_hidden", False): # Skip hidden objects
                    continue

                world_x = float(obj_data.get("world_x", 0.0))
                world_y = float(obj_data.get("world_y", 0.0))
                asset_key = obj_data.get("asset_editor_key", "unknown_asset")
                
                obj_current_w = float(obj_data.get("current_width", ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
                obj_current_h = float(obj_data.get("current_height", ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
                
                asset_info = self.editor_state.assets_palette.get(str(asset_key))

                mini_x = offset_x + (world_x * scale)
                mini_y = offset_y + (world_y * scale)
                mini_w = max(1.0, obj_current_w * scale)
                mini_h = max(1.0, obj_current_h * scale)
                
                draw_rect = QRectF(mini_x, mini_y, mini_w, mini_h)
                object_qcolor: QColor

                if asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY: # type: ignore
                    object_qcolor = category_colors.get("custom_image", default_obj_color)
                elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: # type: ignore
                    props = obj_data.get("properties", {})
                    fill_color_rgba = props.get("fill_color_rgba")
                    if props.get("image_in_square"):
                         object_qcolor = category_colors.get("trigger_image", default_obj_color)
                    elif fill_color_rgba and isinstance(fill_color_rgba, (list,tuple)) and len(fill_color_rgba) == 4:
                        object_qcolor = QColor(*fill_color_rgba) # type: ignore
                    else:
                        object_qcolor = category_colors.get("trigger", default_obj_color)
                elif asset_info:
                    obj_category = asset_info.get("category", "unknown")
                    color_tuple = obj_data.get("override_color")
                    if not color_tuple:
                        color_tuple = asset_info.get("base_color_tuple")
                        if not color_tuple:
                            sp = asset_info.get("surface_params")
                            if sp and isinstance(sp, tuple) and len(sp) == 3:
                                color_tuple = sp[2] # type: ignore
                    object_qcolor = QColor(*color_tuple) if color_tuple else category_colors.get(obj_category, default_obj_color) # type: ignore
                else:
                    object_qcolor = default_obj_color

                if mini_w < fixed_obj_dot_size_px or mini_h < fixed_obj_dot_size_px:
                    if asset_key not in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]: # type: ignore
                        centered_mini_x = mini_x + (mini_w / 2.0) - (fixed_obj_dot_size_px / 2.0)
                        centered_mini_y = mini_y + (mini_h / 2.0) - (fixed_obj_dot_size_px / 2.0)
                        draw_rect = QRectF(centered_mini_x, centered_mini_y, fixed_obj_dot_size_px, fixed_obj_dot_size_px)

                if object_qcolor.alpha() > 0:
                    painter.setBrush(object_qcolor)
                    painter.drawRect(draw_rect)
        
        painter.end()
        if logger: logger.debug("Minimap: Finished rendering map content to pixmap.")

    def update_view_rect(self) -> bool:
        if not self.map_view_ref:
            return False
        
        scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
        old_view_rect = QRectF(self._view_rect_on_minimap)

        if scale <= 1e-6:
            self._view_rect_on_minimap = QRectF()
        else:
            visible_scene_rect_in_map_coords = self.map_view_ref.get_visible_scene_rect()
            
            vx = offset_x + (visible_scene_rect_in_map_coords.x() * scale)
            vy = offset_y + (visible_scene_rect_in_map_coords.y() * scale)
            vw = visible_scene_rect_in_map_coords.width() * scale
            vh = visible_scene_rect_in_map_coords.height() * scale
            
            self._view_rect_on_minimap = QRectF(vx, vy, max(1.0, vw), max(1.0, vh))
        
        changed = (abs(old_view_rect.x() - self._view_rect_on_minimap.x()) > 0.1 or
                   abs(old_view_rect.y() - self._view_rect_on_minimap.y()) > 0.1 or
                   abs(old_view_rect.width() - self._view_rect_on_minimap.width()) > 0.1 or
                   abs(old_view_rect.height() - self._view_rect_on_minimap.height()) > 0.1)
        
        if changed and logger:
            rect_tuple_str = (f"({self._view_rect_on_minimap.x():.1f}, {self._view_rect_on_minimap.y():.1f}, "
                              f"{self._view_rect_on_minimap.width():.1f}, {self._view_rect_on_minimap.height():.1f})")
            logger.debug(f"Minimap: View rect updated to {rect_tuple_str}")
        return changed

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        widget_bg_color = QColor(*ED_CONFIG.MINIMAP_BACKGROUND_COLOR_TUPLE) # type: ignore
        painter.fillRect(self.rect(), widget_bg_color)

        if self._map_content_pixmap is None:
            self._render_map_content_to_pixmap()
        
        if self._map_content_pixmap and not self._map_content_pixmap.isNull():
            painter.drawPixmap(0, 0, self._map_content_pixmap)
        elif logger:
            logger.error("Minimap paintEvent: _map_content_pixmap is None or Null after render attempt!")
            painter.fillRect(self.rect(), Qt.GlobalColor.magenta)

        if not self._view_rect_on_minimap.isNull() and self._view_rect_on_minimap.isValid():
            painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE), 1.5)) # type: ignore
            painter.setBrush(QBrush(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE))) # type: ignore
            painter.drawRect(self._view_rect_on_minimap)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_BORDER_COLOR_TUPLE), 1)) # type: ignore
        painter.drawRect(self.rect().adjusted(0,0,-1,-1))
        
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if not self.map_view_ref:
            return
        
        scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
        if scale <= 1e-6:
            return

        click_pos_on_widget = event.position()
        map_content_rect_on_widget = QRectF(offset_x, offset_y, eff_w, eff_h)

        if event.button() == Qt.MouseButton.LeftButton:
            if map_content_rect_on_widget.contains(click_pos_on_widget):
                click_x_rel_to_map_area = click_pos_on_widget.x() - offset_x
                click_y_rel_to_map_area = click_pos_on_widget.y() - offset_y

                map_coord_x = click_x_rel_to_map_area / scale
                map_coord_y = click_y_rel_to_map_area / scale
                
                clamped_map_coord_x = max(0.0, min(map_coord_x, map_px_w))
                clamped_map_coord_y = max(0.0, min(map_coord_y, map_px_h))

                if self._view_rect_on_minimap.isValid() and self._view_rect_on_minimap.contains(click_pos_on_widget):
                    self._is_dragging_view_rect = True
                    self._drag_offset = click_pos_on_widget - self._view_rect_on_minimap.topLeft()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                else:
                    self.map_view_ref.center_on_map_coords(QPointF(clamped_map_coord_x, clamped_map_coord_y))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging_view_rect and self.map_view_ref:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                self._is_dragging_view_rect = False
                self.unsetCursor()
                return

            scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
            if scale <= 1e-6:
                return

            new_view_rect_top_left_on_widget = event.position() - self._drag_offset
            
            target_center_x_on_widget = new_view_rect_top_left_on_widget.x() + self._view_rect_on_minimap.width() / 2.0
            target_center_y_on_widget = new_view_rect_top_left_on_widget.y() + self._view_rect_on_minimap.height() / 2.0

            actual_target_center_map_x = (target_center_x_on_widget - offset_x) / scale
            actual_target_center_map_y = (target_center_y_on_widget - offset_y) / scale
            
            clamped_target_x = max(0.0, min(actual_target_center_map_x, map_px_w))
            clamped_target_y = max(0.0, min(actual_target_center_map_y, map_px_h))
            
            self.map_view_ref.center_on_map_coords(QPointF(clamped_target_x, clamped_target_y))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_view_rect:
            self._is_dragging_view_rect = False
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QPaintEvent): # Param is QResizeEvent, but QPaintEvent is often used as a general type hint
        if logger: logger.info(f"Minimap: Resized to {self.size()}. Scheduling content redraw.")
        self.schedule_map_content_redraw()
        super().resizeEvent(event) # type: ignore