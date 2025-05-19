# minimap_widget.py
# -*- coding: utf-8 -*-
"""
## version 2.0.0
Minimap Widget for the Platformer Level Editor.
Displays a scaled-down overview of the map and the current viewport.
Allows navigation by clicking or dragging on the minimap.
"""
import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QPaintEvent, QPixmap
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Slot, QSize

import editor_config as ED_CONFIG
from editor_state import EditorState

if TYPE_CHECKING:
    from map_view_widget import MapViewWidget

logger = logging.getLogger(__name__)

class MinimapWidget(QWidget):
    def __init__(self, editor_state: EditorState, map_view_ref: 'MapViewWidget', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.map_view_ref = map_view_ref # Reference to the main MapViewWidget

        self.setMinimumSize(100, 75)
        self.setMaximumSize(400,300) # Prevent it from becoming too large
        self.setPreferredSize(QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT))
        
        self._map_content_pixmap: Optional[QPixmap] = None # Pre-rendered map objects
        self._view_rect_on_minimap = QRectF()
        
        self._is_dragging_view_rect = False
        self._drag_offset = QPointF()

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(ED_CONFIG.MINIMAP_UPDATE_INTERVAL_MS)
        self.update_timer.timeout.connect(self.schedule_full_update) # Full update includes view rect
        self.update_timer.start()

        self.setMouseTracking(True) # For hover effects if any, and consistent updates
        self.schedule_map_content_redraw() # Initial draw

    def sizeHint(self) -> QSize:
        return self.preferredSize()

    def setPreferredSize(self, size: QSize):
        self._preferred_size = size
        self.updateGeometry()

    def preferredSize(self) -> QSize:
        return getattr(self, '_preferred_size', QSize(ED_CONFIG.MINIMAP_DEFAULT_WIDTH, ED_CONFIG.MINIMAP_DEFAULT_HEIGHT))

    @Slot()
    def schedule_map_content_redraw(self):
        logger.debug("Minimap: Map content redraw scheduled.")
        self._map_content_pixmap = None # Invalidate pre-rendered content
        self.update_view_rect() # View rect depends on map content scale
        self.update() # Trigger paintEvent

    @Slot()
    def schedule_full_update(self):
        self.update_view_rect()
        self.update() # Trigger paintEvent for view rect changes

    def _get_map_to_minimap_scales(self) -> tuple[float, float]:
        map_pixel_width = self.editor_state.get_map_pixel_width()
        map_pixel_height = self.editor_state.get_map_pixel_height()

        if map_pixel_width <= 0 or map_pixel_height <= 0:
            return 0.0, 0.0

        # Scale to fit within the minimap widget's current size
        scale_x = self.width() / map_pixel_width
        scale_y = self.height() / map_pixel_height
        
        # Use the smaller scale to maintain aspect ratio and fit entirely
        final_scale = min(scale_x, scale_y)
        return final_scale, final_scale


    def _render_map_content_to_pixmap(self):
        logger.debug("Minimap: Rendering map content to internal pixmap.")
        scale_x, scale_y = self._get_map_to_minimap_scales()
        if scale_x == 0 or scale_y == 0:
            self._map_content_pixmap = QPixmap(self.size())
            self._map_content_pixmap.fill(QColor(*ED_CONFIG.MINIMAP_BACKGROUND_COLOR_TUPLE))
            return

        self._map_content_pixmap = QPixmap(self.size())
        self._map_content_pixmap.fill(Qt.GlobalColor.transparent) # Start with transparent

        painter = QPainter(self._map_content_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Keep it blocky for performance

        # Draw background color for the map area within the minimap
        map_minimap_width = self.editor_state.get_map_pixel_width() * scale_x
        map_minimap_height = self.editor_state.get_map_pixel_height() * scale_y
        painter.fillRect(QRectF(0,0, map_minimap_width, map_minimap_height), QColor(*self.editor_state.background_color))


        obj_color = QColor(*ED_CONFIG.MINIMAP_OBJECT_COLOR_TUPLE)
        painter.setBrush(obj_color)
        painter.setPen(Qt.GlobalColor.transparent) # No border for individual objects

        for obj_data in self.editor_state.placed_objects:
            asset_key = obj_data.get("asset_editor_key")
            asset_info = self.editor_state.assets_palette.get(str(asset_key))
            if not asset_info: continue

            original_w, original_h = asset_info.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
            
            world_x, world_y = obj_data.get("world_x", 0), obj_data.get("world_y", 0)

            mini_x = world_x * scale_x
            mini_y = world_y * scale_y
            mini_w = original_w * scale_x
            mini_h = original_h * scale_y
            
            # Ensure minimum size for visibility on minimap
            mini_w = max(1.0, mini_w)
            mini_h = max(1.0, mini_h)

            painter.drawRect(QRectF(mini_x, mini_y, mini_w, mini_h))
        
        painter.end()

    def update_view_rect(self):
        if not self.map_view_ref: return

        scale_x, scale_y = self._get_map_to_minimap_scales()
        if scale_x == 0 or scale_y == 0:
            self._view_rect_on_minimap = QRectF()
            return

        visible_scene_rect = self.map_view_ref.get_visible_scene_rect()

        self._view_rect_on_minimap = QRectF(
            visible_scene_rect.x() * scale_x,
            visible_scene_rect.y() * scale_y,
            visible_scene_rect.width() * scale_x,
            visible_scene_rect.height() * scale_y
        )
        # logger.debug(f"Minimap: Updated view rect: {self._view_rect_on_minimap}") # Can be spammy


    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Overall minimap background (covers entire widget area)
        painter.fillRect(self.rect(), QColor(*ED_CONFIG.MINIMAP_BACKGROUND_COLOR_TUPLE))

        if self._map_content_pixmap is None:
            self._render_map_content_to_pixmap()
        
        if self._map_content_pixmap:
            painter.drawPixmap(0, 0, self._map_content_pixmap)

        # Draw the view rectangle
        if not self._view_rect_on_minimap.isNull():
            painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE), 1))
            painter.setBrush(QBrush(QColor(*ED_CONFIG.MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE)))
            painter.drawRect(self._view_rect_on_minimap)

        # Draw border for the entire minimap widget
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(*ED_CONFIG.MINIMAP_BORDER_COLOR_TUPLE), 1))
        painter.drawRect(0, 0, self.width() -1, self.height() -1)
        
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if not self.map_view_ref: return

        scale_x, scale_y = self._get_map_to_minimap_scales()
        if scale_x == 0 or scale_y == 0: return

        map_pos_x = event.position().x() / scale_x
        map_pos_y = event.position().y() / scale_y

        if event.button() == Qt.MouseButton.LeftButton:
            if self._view_rect_on_minimap.contains(event.position()):
                self._is_dragging_view_rect = True
                self._drag_offset = event.position() - self._view_rect_on_minimap.topLeft()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                logger.debug(f"Minimap: Started dragging view rect. Offset: {self._drag_offset}")
            else:
                # Click outside view rect: center main view on this point
                self.map_view_ref.center_on_map_coords(QPointF(map_pos_x, map_pos_y))
                logger.debug(f"Minimap: Clicked to center main view at map coords ({map_pos_x:.0f}, {map_pos_y:.0f})")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging_view_rect and self.map_view_ref:
            if not (event.buttons() & Qt.MouseButton.LeftButton): # Drag ended unexpectedly
                self._is_dragging_view_rect = False
                self.unsetCursor()
                return

            scale_x, scale_y = self._get_map_to_minimap_scales()
            if scale_x == 0 or scale_y == 0: return

            new_top_left_minimap = event.position() - self._drag_offset
            
            # Calculate target center for the main map view
            target_center_map_x = (new_top_left_minimap.x() + self._view_rect_on_minimap.width() / 2) / scale_x
            target_center_map_y = (new_top_left_minimap.y() + self._view_rect_on_minimap.height() / 2) / scale_y
            
            self.map_view_ref.center_on_map_coords(QPointF(target_center_map_x, target_center_map_y))
            # schedule_full_update will be called by timer or map_view_ref.view_changed signal
            # For immediate feedback:
            self.update_view_rect() 
            self.update()
            logger.debug(f"Minimap: Dragging view rect to center map at ({target_center_map_x:.0f}, {target_center_map_y:.0f})")

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_view_rect:
            self._is_dragging_view_rect = False
            self.unsetCursor()
            logger.debug("Minimap: Stopped dragging view rect.")
        super().mouseReleaseEvent(event)