#################### START OF FILE: editor_custom_items.py ####################

# editor/editor_custom_items.py
# -*- coding: utf-8 -*-
"""
Custom QGraphicsItem classes for special map objects in the editor,
such as uploaded images and trigger squares.
Version 2.2.0 (Added Cropping Support for CustomImageMapItem)
"""
import os
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QApplication, QStyleOptionGraphicsItem, QWidget, QGraphicsSceneHoverEvent
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QRect # Added QRect

from . import editor_config as ED_CONFIG
from . import editor_map_utils # For paths to custom assets
# from .editor_state import EditorState # Might need for context if not passed directly

logger = logging.getLogger(__name__)

# Define constants for resize handle positions
HANDLE_TOP_LEFT = 0; HANDLE_TOP_MIDDLE = 1; HANDLE_TOP_RIGHT = 2
HANDLE_MIDDLE_LEFT = 3; HANDLE_MIDDLE_RIGHT = 4
HANDLE_BOTTOM_LEFT = 5; HANDLE_BOTTOM_MIDDLE = 6; HANDLE_BOTTOM_RIGHT = 7
HANDLE_SIZE = 8.0 # Pixels


class BaseResizableMapItem(QGraphicsPixmapItem):
    """
    Base class for map items that can be resized and have common properties.
    """
    def __init__(self, map_object_data_ref: Dict[str, Any], initial_pixmap: QPixmap, parent: Optional[QGraphicsItem] = None):
        super().__init__(initial_pixmap, parent)
        self.map_object_data_ref = map_object_data_ref
        
        self.display_aspect_ratio: Optional[float] = None
        self._update_display_aspect_ratio() # Calculate based on current crop/original

        self.setPos(QPointF(float(self.map_object_data_ref.get("world_x", 0)),
                            float(self.map_object_data_ref.get("world_y", 0))))
        
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(self.map_object_data_ref.get("layer_order", 0))

        self.resize_handles: List[QGraphicsRectItem] = []
        self.current_resize_handle_index: Optional[int] = None
        self._create_resize_handles()
        self.show_resize_handles(False)

    def _update_display_aspect_ratio(self):
        ow_data = self.map_object_data_ref.get("original_width")
        oh_data = self.map_object_data_ref.get("original_height")
        crop_rect_data = self.map_object_data_ref.get("crop_rect")

        source_w: Optional[float] = None
        source_h: Optional[float] = None

        if isinstance(crop_rect_data, dict) and \
           all(k in crop_rect_data for k in ["width", "height"]) and \
           isinstance(crop_rect_data["width"], (int, float)) and crop_rect_data["width"] > 0 and \
           isinstance(crop_rect_data["height"], (int, float)) and crop_rect_data["height"] > 0:
            source_w = float(crop_rect_data["width"])
            source_h = float(crop_rect_data["height"])
        elif isinstance(ow_data, (int,float)) and isinstance(oh_data, (int,float)) and ow_data > 0 and oh_data > 0:
            source_w = float(ow_data)
            source_h = float(oh_data)
        
        if source_w is not None and source_h is not None and source_h > 0:
            self.display_aspect_ratio = source_w / source_h
        else:
            cw = self.map_object_data_ref.get("current_width")
            ch = self.map_object_data_ref.get("current_height")
            if isinstance(cw, (int,float)) and isinstance(ch, (int,float)) and ch > 0 and cw > 0 :
                self.display_aspect_ratio = float(cw) / float(ch)
            else:
                self.display_aspect_ratio = None


    def _create_resize_handles(self):
        if self.resize_handles:
            for handle in self.resize_handles:
                if handle.scene(): self.scene().removeItem(handle)
            self.resize_handles.clear()

        for i in range(8):
            handle = QGraphicsRectItem(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, self)
            handle.setBrush(QColor(Qt.GlobalColor.white))
            handle.setPen(QPen(QColor(Qt.GlobalColor.black), 1))
            handle.setZValue(self.zValue() + 10)
            handle.setVisible(False)
            handle.setData(0, i)
            self.resize_handles.append(handle)
        self.update_handle_positions()

    def update_handle_positions(self):
        if not self.resize_handles: return
        br_width = self.map_object_data_ref.get("current_width", self.pixmap().width())
        br_height = self.map_object_data_ref.get("current_height", self.pixmap().height())
        br = QRectF(0, 0, float(br_width), float(br_height))

        self.resize_handles[HANDLE_TOP_LEFT].setPos(br.left(), br.top())
        self.resize_handles[HANDLE_TOP_MIDDLE].setPos(br.center().x(), br.top())
        self.resize_handles[HANDLE_TOP_RIGHT].setPos(br.right(), br.top())
        self.resize_handles[HANDLE_MIDDLE_LEFT].setPos(br.left(), br.center().y())
        self.resize_handles[HANDLE_MIDDLE_RIGHT].setPos(br.right(), br.center().y())
        self.resize_handles[HANDLE_BOTTOM_LEFT].setPos(br.left(), br.bottom())
        self.resize_handles[HANDLE_BOTTOM_MIDDLE].setPos(br.center().x(), br.bottom())
        self.resize_handles[HANDLE_BOTTOM_RIGHT].setPos(br.right(), br.bottom())
        
    def show_resize_handles(self, show: bool):
        if not self.resize_handles and show: self._create_resize_handles()
        if not self.resize_handles: return

        for handle in self.resize_handles:
            handle.setVisible(show)
        if show:
            self.update_handle_positions()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.show_resize_handles(bool(value))

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            if self.scene().property("is_resizing_item_internal") is True:
                return super().itemChange(change, value)

            new_pos: QPointF = value
            grid_size = self.scene().property("grid_size")
            grid_size = grid_size if isinstance(grid_size, (int, float)) and grid_size > 0 else ED_CONFIG.BASE_GRID_SIZE

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if int(snapped_x) != self.map_object_data_ref.get('world_x') or \
               int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                
                map_view = self.scene().parent()
                if hasattr(map_view, 'object_graphically_moved_signal'):
                    map_view.object_graphically_moved_signal.emit(self.map_object_data_ref)

            if abs(new_pos.x() - snapped_x) > 1e-3 or abs(new_pos.y() - snapped_y) > 1e-3:
                return QPointF(float(snapped_x), float(snapped_y))
            return new_pos
        
        return super().itemChange(change, value)

    def update_visuals_from_data(self, editor_state: Any): # editor_state: EditorState
        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z:
            self.setZValue(new_z)
        
        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y):
            self.setPos(new_pos_x, new_pos_y)

        self._update_display_aspect_ratio()
        
        self.prepareGeometryChange()
        self.update_handle_positions()

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
        self.editor_state_ref = editor_state
        initial_pixmap = self._load_pixmap_from_data(map_object_data_ref, editor_state)
        super().__init__(map_object_data_ref, initial_pixmap, parent)

    def _load_pixmap_from_data(self, obj_data: Dict[str, Any], editor_state: Any) -> QPixmap:
        current_width = obj_data.get("current_width", ED_CONFIG.BASE_GRID_SIZE)
        current_height = obj_data.get("current_height", ED_CONFIG.BASE_GRID_SIZE)
        
        map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function)
        rel_path = obj_data.get("source_file_path", "")
        
        # Create a default transparent pixmap of the target display size
        # Ensure dimensions are at least 1x1
        display_w = int(max(1, current_width))
        display_h = int(max(1, current_height))
        pixmap = QPixmap(display_w, display_h)
        pixmap.fill(Qt.GlobalColor.transparent)

        if map_folder and rel_path:
            full_image_path = os.path.join(map_folder, rel_path)
            if os.path.exists(full_image_path):
                full_qimage = QImage(full_image_path)
                if not full_qimage.isNull():
                    # Update original_width/height in obj_data if they are missing or don't match the loaded image
                    if (obj_data.get("original_width") != full_qimage.width() or
                        obj_data.get("original_height") != full_qimage.height()):
                        obj_data["original_width"] = full_qimage.width()
                        obj_data["original_height"] = full_qimage.height()
                        # If original dimensions changed, any existing crop_rect might become invalid.
                        # The validation below will handle it.

                    image_to_render = full_qimage
                    crop_rect_data = obj_data.get("crop_rect")

                    if isinstance(crop_rect_data, dict) and \
                       all(k in crop_rect_data for k in ["x", "y", "width", "height"]):
                        
                        crop_x = int(crop_rect_data["x"])
                        crop_y = int(crop_rect_data["y"])
                        crop_w = int(crop_rect_data["width"])
                        crop_h = int(crop_rect_data["height"])

                        # Validate crop_rect against (potentially updated) original_width/height
                        orig_w = obj_data.get("original_width", full_qimage.width())
                        orig_h = obj_data.get("original_height", full_qimage.height())

                        if not (0 <= crop_x < orig_w and \
                                0 <= crop_y < orig_h and \
                                crop_w > 0 and crop_h > 0 and \
                                crop_x + crop_w <= orig_w and \
                                crop_y + crop_h <= orig_h):
                            logger.warning(f"Invalid crop_rect {crop_rect_data} for image {rel_path} (original size {orig_w}x{orig_h}). Using full image.")
                            obj_data["crop_rect"] = None # Reset invalid crop
                            # image_to_render remains full_qimage
                        else:
                            qt_crop_rect = QRect(crop_x, crop_y, crop_w, crop_h)
                            image_to_render = full_qimage.copy(qt_crop_rect)
                    
                    if not image_to_render.isNull():
                        # Scale the (potentially cropped) image_to_render to current_width/height for display
                        scaled_image = image_to_render.scaled(
                            display_w, display_h,
                            Qt.AspectRatioMode.IgnoreAspectRatio, # User controls current_width/height via resize
                            Qt.TransformationMode.SmoothTransformation
                        )
                        pixmap = QPixmap.fromImage(scaled_image)
                    else:
                        logger.warning(f"CustomImageMapItem: image_to_render is null after crop/copy for {full_image_path}")
                        pixmap.fill(QColor(255, 0, 255, 120)) # Magenta fallback
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
        new_pixmap = self._load_pixmap_from_data(self.map_object_data_ref, editor_state)
        
        current_pixmap = self.pixmap()
        pixmap_changed = (current_pixmap.isNull() or new_pixmap.isNull() or
                          current_pixmap.cacheKey() != new_pixmap.cacheKey() or
                          current_pixmap.size() != new_pixmap.size())

        if pixmap_changed:
            self.setPixmap(new_pixmap)
        
        super().update_visuals_from_data(editor_state)


class TriggerSquareMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: Any, parent: Optional[QGraphicsItem] = None): # editor_state: EditorState
        current_w = map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        # Ensure dimensions are at least 1x1
        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))
        transparent_pixmap = QPixmap(display_w, display_h)
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        
        super().__init__(map_object_data_ref, transparent_pixmap, parent)
        self.editor_state_ref = editor_state
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h
        # Call update_visuals_from_data once to ensure base class aspect ratio etc. is set up correctly
        # even though this class custom paints.
        self.update_visuals_from_data(editor_state)


    def boundingRect(self) -> QRectF:
        w = self.map_object_data_ref.get("current_width", 0.0)
        h = self.map_object_data_ref.get("current_height", 0.0)
        return QRectF(0, 0, float(w), float(h))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        props = self.map_object_data_ref.get("properties", {})
        rect = self.boundingRect()

        is_editor_preview = False
        if self.scene() and self.scene().parent() and hasattr(self.scene().parent(), 'editor_state'):
            parent_widget = self.scene().parent()
            if hasattr(parent_widget, 'editor_state'): # Check specific attribute
                 is_editor_preview = parent_widget.editor_state.is_game_preview_mode

        if not props.get("visible", True) and is_editor_preview:
            return

        if not props.get("visible", True) and not is_editor_preview:
            painter.setPen(QPen(QColor(150, 150, 255, 100), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Invisible Trigger")
            return

        image_path_rel = props.get("image_in_square", "")
        image_drawn_successfully = False
        if image_path_rel:
            map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state_ref, self.editor_state_ref.map_name_for_function)
            if map_folder:
                full_image_path = os.path.join(map_folder, image_path_rel)
                if os.path.exists(full_image_path):
                    img = QImage(full_image_path)
                    if not img.isNull():
                        target_size = rect.size().toSize()
                        # Ensure target size is valid for QImage.scaled
                        if target_size.width() > 0 and target_size.height() > 0:
                            painter.drawImage(rect, img.scaled(target_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                            image_drawn_successfully = True
                        else:
                            logger.warning(f"TriggerSquareMapItem: Invalid target_size {target_size} for image drawing.")
        
        if not image_drawn_successfully: # Draw color fill if no image or image failed
            fill_color_rgba = props.get("fill_color_rgba")
            if fill_color_rgba and isinstance(fill_color_rgba, (list, tuple)) and len(fill_color_rgba) == 4:
                painter.setBrush(QColor(*fill_color_rgba)) # type: ignore
                painter.setPen(QPen(QColor(0,0,0,180), 1))
                painter.drawRect(rect)
            else:
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
        # Update the transparent pixmap to the new size for correct bounding box in base class
        current_w = self.map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = self.map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        
        # Ensure dimensions are at least 1x1
        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))

        if self.pixmap().width() != display_w or self.pixmap().height() != display_h:
            new_pixmap = QPixmap(display_w, display_h)
            new_pixmap.fill(Qt.GlobalColor.transparent)
            self.setPixmap(new_pixmap)
            # This will call prepareGeometryChange internally if pixmap changes.
        
        super().update_visuals_from_data(editor_state) # Handles Z, pos, aspect ratio, and calls prepareGeometryChange & update_handle_positions
        self.update() # Schedule a repaint for custom painting changes

#################### END OF FILE: editor_custom_items.py ####################