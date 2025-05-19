# minimap_widget.py
# -*- coding: utf-8 -*-
"""
## version 2.0.3 (Fixed QRectF.toTuple() error)
Minimap Widget for the Platformer Level Editor.
Displays a scaled-down overview of the map and the current viewport.
Allows navigation by clicking or dragging on the minimap.
"""
import logging
from typing import Optional, TYPE_CHECKING, Tuple

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QPaintEvent, QPixmap
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Slot, QSize

import editor_config as ED_CONFIG
from editor_state import EditorState

if TYPE_CHECKING:
    from map_view_widget import MapViewWidget # type: ignore

logger = logging.getLogger(__name__)

class MinimapWidget(QWidget):
    def __init__(self, editor_state: EditorState, map_view_ref: 'MapViewWidget', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.map_view_ref = map_view_ref

        self.setMinimumSize(100, 75)
        self.setMaximumSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH * 3, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT * 3)
        self.setPreferredSize(QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT))
        
        self._map_content_pixmap: Optional[QPixmap] = None
        self._view_rect_on_minimap = QRectF()
        
        self._is_dragging_view_rect = False
        self._drag_offset = QPointF()

        self.view_rect_update_timer = QTimer(self)
        self.view_rect_update_timer.setInterval(ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS)
        self.view_rect_update_timer.timeout.connect(self.schedule_view_rect_update_and_repaint)
        self.view_rect_update_timer.start()

        self.setMouseTracking(True)
        self.schedule_map_content_redraw()

        logger.info(f"MinimapWidget initialized. Preferred size: {self.preferredSize()}. Update interval: {ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS}ms.")

    def sizeHint(self) -> QSize:
        return self.preferredSize()

    def setPreferredSize(self, size: QSize):
        self._preferred_size = size
        self.updateGeometry()

    def preferredSize(self) -> QSize:
        return getattr(self, '_preferred_size', QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT))

    @Slot()
    def schedule_map_content_redraw(self):
        logger.debug("Minimap: Map content redraw scheduled (invalidating content pixmap).")
        self._map_content_pixmap = None
        self.update_view_rect()
        self.update()

    @Slot()
    def schedule_view_rect_update_and_repaint(self):
        needs_update = self.update_view_rect()
        if needs_update:
            self.update()

    def _get_map_to_minimap_transform(self) -> Tuple[float, float, float, float, float, float, float]:
        map_px_w = float(self.editor_state.get_map_pixel_width())
        map_px_h = float(self.editor_state.get_map_pixel_height())
        widget_w = float(self.width())
        widget_h = float(self.height())

        if map_px_w <= 1e-6 or map_px_h <= 1e-6 or widget_w <= 1e-6 or widget_h <= 1e-6:
            return 0.0, 0.0, 0.0, 0.0, 0.0, map_px_w, map_px_h

        scale_x = widget_w / map_px_w
        scale_y = widget_h / map_px_h
        final_scale = min(scale_x, scale_y)
        if final_scale <= 1e-6: final_scale = 0.0

        eff_w = map_px_w * final_scale
        eff_h = map_px_h * final_scale
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
        self._map_content_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self._map_content_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        scale, eff_w, eff_h, offset_x, offset_y, _, _ = self._get_map_to_minimap_transform()
        # logger.debug(f"Minimap Render - Transform: scale={scale:.4f}, eff_w={eff_w:.1f}, eff_h={eff_h:.1f}, offset_x={offset_x:.1f}, offset_y={offset_y:.1f}")
        # logger.debug(f"Minimap Render - Map BG Color: {self.editor_state.background_color}")

        map_bg_rect = QRectF(offset_x, offset_y, max(0.0, eff_w), max(0.0, eff_h))
        map_bg_qcolor = QColor(*self.editor_state.background_color)
        painter.fillRect(map_bg_rect, map_bg_qcolor)
        # logger.debug(f"Minimap Render - Drawn map background rect: ({map_bg_rect.x():.1f},{map_bg_rect.y():.1f},{map_bg_rect.width():.1f},{map_bg_rect.height():.1f}) with color {map_bg_qcolor.name()}")

        if scale > 1e-5 and self.editor_state.placed_objects:
            # logger.info(f"Minimap Render - Drawing {len(self.editor_state.placed_objects)} objects with scale {scale:.4f}")
            fixed_obj_size_on_minimap = getattr(ED_CONFIG, 'MINIMAP_OBJECT_REPRESENTATION_SIZE_PX', 2.0)
            debug_object_color = QColor(255, 0, 0, 255) # Solid Bright Red for debug
            painter.setPen(Qt.PenStyle.NoPen)

            for i, obj_data in enumerate(self.editor_state.placed_objects):
                world_x = float(obj_data.get("world_x", 0.0))
                world_y = float(obj_data.get("world_y", 0.0))
                asset_key = obj_data.get("asset_editor_key", "unknown_asset")
                asset_info = self.editor_state.assets_palette.get(str(asset_key))
                obj_orig_w, obj_orig_h = float(ED_CONFIG.BASE_GRID_SIZE), float(ED_CONFIG.BASE_GRID_SIZE)
                if asset_info:
                    orig_size_tuple = asset_info.get("original_size_pixels")
                    if orig_size_tuple and len(orig_size_tuple) == 2: obj_orig_w, obj_orig_h = float(orig_size_tuple[0]), float(orig_size_tuple[1])
                
                mini_x = offset_x + (world_x * scale)
                mini_y = offset_y + (world_y * scale)
                obj_category = asset_info.get("category", "unknown") if asset_info else "unknown"
                
                draw_rect: QRectF
                if obj_category == "tile" or "platform" in obj_data.get("game_type_id", ""):
                    rect_w_on_minimap = max(1.0, obj_orig_w * scale)
                    rect_h_on_minimap = max(1.0, obj_orig_h * scale)
                    draw_rect = QRectF(mini_x, mini_y, rect_w_on_minimap, rect_h_on_minimap)
                else:
                     draw_rect = QRectF(mini_x, mini_y, fixed_obj_size_on_minimap, fixed_obj_size_on_minimap)
                
                painter.setBrush(debug_object_color)
                painter.drawRect(draw_rect)
                
                # if i < 1 : # Log only the first object per render to reduce spam
                #     logger.debug(f"  Minimap Obj {i} ('{asset_key}'): Cat='{obj_category}' WPos=({world_x:.0f},{world_y:.0f}) DrawRect=({draw_rect.x():.1f},{draw_rect.y():.1f},{draw_rect.width():.1f},{draw_rect.height():.1f})")
        # else:
            # if scale <= 1e-5: logger.warning("Minimap Render - Scale is too small, not drawing objects.")
            # if not self.editor_state.placed_objects: logger.info("Minimap Render - No objects placed on map.")

        painter.end()
        logger.debug("Minimap: Finished rendering map content to pixmap.")


    def update_view_rect(self) -> bool:
        if not self.map_view_ref: return False
        scale, _, _, offset_x, offset_y, _, _ = self._get_map_to_minimap_transform()
        old_view_rect = QRectF(self._view_rect_on_minimap)

        if scale == 0.0:
            self._view_rect_on_minimap = QRectF()
        else:
            visible_scene_rect = self.map_view_ref.get_visible_scene_rect()
            self._view_rect_on_minimap = QRectF(
                offset_x + (visible_scene_rect.x() * scale),
                offset_y + (visible_scene_rect.y() * scale),
                max(1.0, visible_scene_rect.width() * scale),
                max(1.0, visible_scene_rect.height() * scale)
            )
        
        changed = (abs(old_view_rect.x() - self._view_rect_on_minimap.x()) > 0.1 or
                   abs(old_view_rect.y() - self._view_rect_on_minimap.y()) > 0.1 or
                   abs(old_view_rect.width() - self._view_rect_on_minimap.width()) > 0.1 or
                   abs(old_view_rect.height() - self._view_rect_on_minimap.height()) > 0.1)
        
        if changed:
            # Correct way to log QRectF components
            rect_tuple_str = (f"({self._view_rect_on_minimap.x():.1f}, {self._view_rect_on_minimap.y():.1f}, "
                              f"{self._view_rect_on_minimap.width():.1f}, {self._view_rect_on_minimap.height():.1f})")
            logger.debug(f"Minimap: View rect updated to {rect_tuple_str}")
        return changed

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        widget_bg_color = QColor(*ED_CONFIG.MINIMAP_BACKGROUND_COLOR_TUPLE)
        painter.fillRect(self.rect(), widget_bg_color)

        if self._map_content_pixmap is None:
            # logger.info("Minimap paintEvent: _map_content_pixmap is None, re-rendering.") # Can be spammy
            self._render_map_content_to_pixmap()
        
        if self._map_content_pixmap and not self._map_content_pixmap.isNull():
            painter.drawPixmap(0, 0, self._map_content_pixmap)
        else:
            logger.error("Minimap paintEvent: _map_content_pixmap is None or Null after render attempt!")
            painter.fillRect(self.rect(), Qt.GlobalColor.magenta)

        if not self._view_rect_on_minimap.isNull():
            painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE), 1.5))
            painter.setBrush(QBrush(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE)))
            painter.drawRect(self._view_rect_on_minimap)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_BORDER_COLOR_TUPLE), 1))
        painter.drawRect(self.rect().adjusted(0,0,-1,-1))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if not self.map_view_ref: return
        scale, eff_w, eff_h, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
        if scale == 0.0: return

        click_x_on_widget = event.position().x()
        click_y_on_widget = event.position().y()
        click_x_rel_to_map_content = click_x_on_widget - offset_x
        click_y_rel_to_map_content = click_y_on_widget - offset_y
        map_coord_x = click_x_rel_to_map_content / scale
        map_coord_y = click_y_rel_to_map_content / scale

        if event.button() == Qt.MouseButton.LeftButton:
            map_content_rect_on_widget = QRectF(offset_x, offset_y, eff_w, eff_h)
            if map_content_rect_on_widget.contains(event.position()):
                if self._view_rect_on_minimap.contains(event.position()):
                    self._is_dragging_view_rect = True
                    self._drag_offset = event.position() - self._view_rect_on_minimap.topLeft()
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    # logger.debug(f"Minimap: Started dragging view rect. Offset: ({self._drag_offset.x():.1f},{self._drag_offset.y():.1f})")
                else:
                    clamped_map_coord_x = max(0.0, min(map_coord_x, map_px_w))
                    clamped_map_coord_y = max(0.0, min(map_coord_y, map_px_h))
                    self.map_view_ref.center_on_map_coords(QPointF(clamped_map_coord_x, clamped_map_coord_y))
                    # logger.debug(f"Minimap: Clicked to center main view at map coords ({clamped_map_coord_x:.0f}, {clamped_map_coord_y:.0f})")
            # else:
                # logger.debug("Minimap: Clicked outside scaled map content area.")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging_view_rect and self.map_view_ref:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                self._is_dragging_view_rect = False; self.unsetCursor(); return

            scale, _, _, offset_x, offset_y, map_px_w, map_px_h = self._get_map_to_minimap_transform()
            if scale == 0.0: return

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
            # logger.debug("Minimap: Stopped dragging view rect.")
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QPaintEvent): # event is QResizeEvent, but QPaintEvent is often used as a general type hint here
        logger.info(f"Minimap: Resized to {self.size()}. Scheduling content redraw.")
        self.schedule_map_content_redraw()
        super().resizeEvent(event)