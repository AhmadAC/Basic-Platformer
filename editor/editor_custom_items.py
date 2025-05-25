# editor/editor_custom_items.py
# -*- coding: utf-8 -*-
"""
Custom QGraphicsItem classes for special map objects in the editor,
such as uploaded images and trigger squares.
"""
import os
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QApplication, QStyleOptionGraphicsItem, QWidget, QGraphicsSceneHoverEvent # Added QGraphicsSceneHoverEvent
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor
from PySide6.QtCore import Qt, QRectF, QPointF, QSize

from . import editor_config as ED_CONFIG
from . import editor_map_utils # For paths to custom assets
# from .editor_state import EditorState # Might need for context if not passed directly

logger = logging.getLogger(__name__)

# Define constants for resize handle positions (can be shared or redefined if needed)
HANDLE_TOP_LEFT = 0; HANDLE_TOP_MIDDLE = 1; HANDLE_TOP_RIGHT = 2
HANDLE_MIDDLE_LEFT = 3; HANDLE_MIDDLE_RIGHT = 4
HANDLE_BOTTOM_LEFT = 5; HANDLE_BOTTOM_MIDDLE = 6; HANDLE_BOTTOM_RIGHT = 7
HANDLE_SIZE = 8.0 # Pixels


class BaseResizableMapItem(QGraphicsPixmapItem): # Using QGraphicsPixmapItem as a base for common functionality
    """
    Base class for map items that can be resized and have common properties.
    Could also be QGraphicsObject if signals/slots are needed directly on items.
    """
    def __init__(self, map_object_data_ref: Dict[str, Any], initial_pixmap: QPixmap, parent: Optional[QGraphicsItem] = None):
        super().__init__(initial_pixmap, parent)
        self.map_object_data_ref = map_object_data_ref
        
        self.original_aspect_ratio: Optional[float] = None
        ow = self.map_object_data_ref.get("original_width")
        oh = self.map_object_data_ref.get("original_height")
        if isinstance(ow, (int,float)) and isinstance(oh, (int,float)) and oh > 0:
            self.original_aspect_ratio = float(ow) / float(oh)

        self.setPos(QPointF(float(self.map_object_data_ref.get("world_x", 0)), 
                            float(self.map_object_data_ref.get("world_y", 0))))
        
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(self.map_object_data_ref.get("layer_order", 0))

        self.resize_handles: List[QGraphicsRectItem] = []
        self.current_resize_handle_index: Optional[int] = None # For MapViewWidget to know which handle is active
        self._create_resize_handles()
        self.show_resize_handles(False)

    def _create_resize_handles(self):
        if self.resize_handles:
            for handle in self.resize_handles:
                if handle.scene(): self.scene().removeItem(handle)
            self.resize_handles.clear()

        for i in range(8):
            handle = QGraphicsRectItem(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, self)
            handle.setBrush(QColor(Qt.GlobalColor.white))
            handle.setPen(QPen(QColor(Qt.GlobalColor.black), 1))
            handle.setZValue(self.zValue() + 10) # Ensure handles are well above item
            handle.setVisible(False)
            handle.setData(0, i) # Store handle index
            self.resize_handles.append(handle)
        self.update_handle_positions()

    def update_handle_positions(self):
        if not self.resize_handles: return
        # Pixmap might be empty for items that custom paint (like TriggerSquare if it subclasses this)
        # So, use current_width/height from data if bounding rect is not reliable from pixmap
        br_width = self.map_object_data_ref.get("current_width", self.pixmap().width())
        br_height = self.map_object_data_ref.get("current_height", self.pixmap().height())
        br = QRectF(0, 0, br_width, br_height) # Item's local coordinates

        self.resize_handles[HANDLE_TOP_LEFT].setPos(br.left(), br.top())
        self.resize_handles[HANDLE_TOP_MIDDLE].setPos(br.center().x(), br.top())
        self.resize_handles[HANDLE_TOP_RIGHT].setPos(br.right(), br.top())
        self.resize_handles[HANDLE_MIDDLE_LEFT].setPos(br.left(), br.center().y())
        self.resize_handles[HANDLE_MIDDLE_RIGHT].setPos(br.right(), br.center().y())
        self.resize_handles[HANDLE_BOTTOM_LEFT].setPos(br.left(), br.bottom())
        self.resize_handles[HANDLE_BOTTOM_MIDDLE].setPos(br.center().x(), br.bottom())
        self.resize_handles[HANDLE_BOTTOM_RIGHT].setPos(br.right(), br.bottom())
        
    def show_resize_handles(self, show: bool):
        if not self.resize_handles and show: self._create_resize_handles() # Create if showing first time
        if not self.resize_handles: return

        for handle in self.resize_handles:
            handle.setVisible(show)
        if show:
            self.update_handle_positions()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.show_resize_handles(bool(value))

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            # Prevent position change updates if an internal resize operation is active
            if self.scene().property("is_resizing_item_internal") is True: # type: ignore
                return super().itemChange(change, value) # Allow change if it's part of resize update

            new_pos: QPointF = value
            grid_size = self.scene().property("grid_size") # type: ignore
            grid_size = grid_size if isinstance(grid_size, (int, float)) and grid_size > 0 else ED_CONFIG.BASE_GRID_SIZE

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if int(snapped_x) != self.map_object_data_ref.get('world_x') or \
               int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                
                # Access MapViewWidget through scene().parent() to emit signal
                map_view = self.scene().parent() # type: ignore
                if hasattr(map_view, 'object_graphically_moved_signal'):
                    map_view.object_graphically_moved_signal.emit(self.map_object_data_ref)

            if abs(new_pos.x() - snapped_x) > 1e-3 or abs(new_pos.y() - snapped_y) > 1e-3: # Snap if not already snapped
                return QPointF(float(snapped_x), float(snapped_y))
            return new_pos # Already snapped or no change
        
        return super().itemChange(change, value)

    def update_visuals_from_data(self, editor_state: Any): # editor_state: EditorState (forward ref)
        """
        Updates the item's appearance based on its map_object_data_ref.
        This method needs to be implemented or overridden by subclasses.
        """
        # Update Z-value (layer order)
        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z:
            self.setZValue(new_z)
        
        # Update position if it changed in data (e.g. through properties panel)
        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y):
            self.setPos(new_pos_x, new_pos_y)

        # Subclasses will handle pixmap/size updates.
        self.update_handle_positions() # If size might have changed
        self.prepareGeometryChange() # Inform scene if bounding rect changes

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent): # type: ignore
        if self.isSelected():
            for i, handle in enumerate(self.resize_handles):
                if handle.isVisible() and handle.sceneBoundingRect().contains(event.scenePos()):
                    cursors = [Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor,
                               Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeHorCursor,
                               Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor]
                    QApplication.setOverrideCursor(QCursor(cursors[i]))
                    return
        QApplication.restoreOverrideCursor()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent): # type: ignore
        QApplication.restoreOverrideCursor()
        super().hoverLeaveEvent(event)


class CustomImageMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: Any, parent: Optional[QGraphicsItem] = None): # editor_state: EditorState
        # Load initial pixmap based on data
        self.editor_state_ref = editor_state # Keep a reference if needed for path resolution
        initial_pixmap = self._load_pixmap_from_data(map_object_data_ref, editor_state)
        super().__init__(map_object_data_ref, initial_pixmap, parent)

    def _load_pixmap_from_data(self, obj_data: Dict[str, Any], editor_state: Any) -> QPixmap:
        current_width = obj_data.get("current_width", ED_CONFIG.BASE_GRID_SIZE)
        current_height = obj_data.get("current_height", ED_CONFIG.BASE_GRID_SIZE)
        
        map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function)
        rel_path = obj_data.get("source_file_path", "")
        pixmap = QPixmap(int(current_width), int(current_height)) # Default transparent

        if map_folder and rel_path:
            full_image_path = os.path.join(map_folder, rel_path)
            if os.path.exists(full_image_path):
                loaded_img = QImage(full_image_path)
                if not loaded_img.isNull():
                    pixmap = QPixmap.fromImage(loaded_img.scaled(
                        int(current_width), int(current_height),
                        Qt.AspectRatioMode.IgnoreAspectRatio, # Resizing handles explicit size
                        Qt.TransformationMode.SmoothTransformation
                    ))
                else:
                    logger.warning(f"CustomImageMapItem: Failed to load QImage from {full_image_path}")
                    pixmap.fill(QColor(255, 0, 255, 120)) # Magenta fallback
            else:
                logger.warning(f"CustomImageMapItem: Image file not found at {full_image_path}")
                pixmap.fill(QColor(255, 165, 0, 120)) # Orange fallback
        else:
            logger.warning(f"CustomImageMapItem: Missing map_folder or relative_path for custom image.")
            pixmap.fill(QColor(255, 255, 0, 120)) # Yellow fallback
        return pixmap

    def update_visuals_from_data(self, editor_state: Any): # editor_state: EditorState
        super().update_visuals_from_data(editor_state)
        new_pixmap = self._load_pixmap_from_data(self.map_object_data_ref, editor_state)
        if self.pixmap().cacheKey() != new_pixmap.cacheKey():
            self.setPixmap(new_pixmap)
        # Position and Z-value are handled by base class


class TriggerSquareMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: Any, parent: Optional[QGraphicsItem] = None): # editor_state: EditorState
        # Trigger squares don't have a fixed initial pixmap from a file in the same way.
        # BaseResizableMapItem expects a QPixmap. We'll give it a transparent one of current size.
        current_w = map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        transparent_pixmap = QPixmap(int(current_w), int(current_h))
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        
        super().__init__(map_object_data_ref, transparent_pixmap, parent)
        self.editor_state_ref = editor_state
        # Ensure initial size in data is reflected (BaseResizableMapItem does not set pixmap based on current_width/height)
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h
        self.update_visuals_from_data(editor_state) # To set correct internal state/pixmap if needed by base


    def boundingRect(self) -> QRectF:
        # Define bounding rect based on current_width/height for custom painting
        w = self.map_object_data_ref.get("current_width", 0)
        h = self.map_object_data_ref.get("current_height", 0)
        return QRectF(0, 0, w, h)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        props = self.map_object_data_ref.get("properties", {})
        rect = self.boundingRect() # Uses our overridden boundingRect

        is_editor_preview = self.scene().parent().editor_state.is_game_preview_mode if self.scene() and self.scene().parent() and hasattr(self.scene().parent(), 'editor_state') else False # type: ignore

        if not props.get("visible", True) and is_editor_preview:
            return # Invisible in game preview mode

        # Editor-only indication for invisible triggers when not in preview
        if not props.get("visible", True) and not is_editor_preview:
            painter.setPen(QPen(QColor(150, 150, 255, 100), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Invisible Trigger")
            return

        # Image fill
        image_path_rel = props.get("image_in_square", "")
        if image_path_rel:
            map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state_ref, self.editor_state_ref.map_name_for_function)
            if map_folder:
                full_image_path = os.path.join(map_folder, image_path_rel)
                if os.path.exists(full_image_path):
                    img = QImage(full_image_path)
                    if not img.isNull():
                        painter.drawImage(rect, img.scaled(rect.size().toSize(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        # If selected, QGraphicsView will draw selection outline
                        if option.state & QStyleOptionGraphicsItem.StyleState.State_Selected: # type: ignore
                            pen = QPen(QColor(Qt.GlobalColor.yellow), 2, Qt.PenStyle.DashLine)
                            painter.setPen(pen)
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.drawRect(rect)
                        return # Image drawn

        # Color fill if no image or image failed
        fill_color_rgba = props.get("fill_color_rgba")
        if fill_color_rgba and isinstance(fill_color_rgba, (list, tuple)) and len(fill_color_rgba) == 4:
            painter.setBrush(QColor(*fill_color_rgba)) # type: ignore
            painter.setPen(QPen(QColor(0,0,0,180), 1)) # Thin border
            painter.drawRect(rect)
        else: # Default fallback drawing if no color/image
            painter.setBrush(QColor(100,100,255,50))
            painter.setPen(QPen(QColor(50,50,150,150),1))
            painter.drawRect(rect)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Trigger")


        if option.state & QStyleOptionGraphicsItem.StyleState.State_Selected: # type: ignore
            pen = QPen(QColor(Qt.GlobalColor.yellow), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)


    def update_visuals_from_data(self, editor_state: Any): # editor_state: EditorState
        super().update_visuals_from_data(editor_state)
        # Trigger a repaint because our appearance depends on properties, not just pixmap
        # The bounding rect might have changed if current_width/height was updated
        self.prepareGeometryChange() 
        
        # Update the transparent pixmap to the new size
        current_w = self.map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = self.map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        if self.pixmap().width() != current_w or self.pixmap().height() != current_h:
            new_pixmap = QPixmap(int(current_w), int(current_h))
            new_pixmap.fill(Qt.GlobalColor.transparent)
            self.setPixmap(new_pixmap)
        
        self.update() # Schedule a repaint