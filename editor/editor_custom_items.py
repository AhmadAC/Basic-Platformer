#################### START OF FILE: editor_custom_items.py ####################

# editor/editor_custom_items.py
# -*- coding: utf-8 -*-
"""
Custom QGraphicsItem classes for special map objects in the editor,
such as uploaded images and trigger squares.
Version 2.2.11 (Aggressive Real-time Opacity Update)
- Added scene-level update for CustomImageMapItem to try and force repaint.
MODIFIED: TriggerSquareMapItem.paint() now respects the 'opacity' property.
MODIFIED: BaseResizableMapItem visibility logic updated for opacity.
"""
import os
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QApplication, QStyleOptionGraphicsItem, QWidget, QStyle
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor, QHoverEvent, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QRect


from . import editor_config as ED_CONFIG
from . import editor_map_utils
# from .editor_state import EditorState # Forward declaration often sufficient for type hints

logger = logging.getLogger(__name__)

# Define constants for resize handle positions
HANDLE_TOP_LEFT = 0; HANDLE_TOP_MIDDLE = 1; HANDLE_TOP_RIGHT = 2
HANDLE_MIDDLE_LEFT = 3; HANDLE_MIDDLE_RIGHT = 4
HANDLE_BOTTOM_LEFT = 5; HANDLE_BOTTOM_MIDDLE = 6; HANDLE_BOTTOM_RIGHT = 7
HANDLE_SIZE = 8.0 # Pixels
ALL_HANDLES_COUNT = 8


class BaseResizableMapItem(QGraphicsPixmapItem):
    """
    Base class for map items that can be resized and have common properties.
    Can switch between 'resize' and 'crop' interaction modes.
    """
    def __init__(self, map_object_data_ref: Dict[str, Any], initial_pixmap: QPixmap, parent: Optional[QGraphicsItem] = None):
        super().__init__(initial_pixmap, parent)
        self.map_object_data_ref = map_object_data_ref
        
        self.display_aspect_ratio: Optional[float] = None
        self._update_display_aspect_ratio()

        self.setPos(QPointF(float(self.map_object_data_ref.get("world_x", 0)),
                            float(self.map_object_data_ref.get("world_y", 0))))
        
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        current_flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | \
                        QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        if not is_locked:
            current_flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlags(current_flags)
        
        self.setAcceptHoverEvents(True)
        self.setZValue(self.map_object_data_ref.get("layer_order", 0))
        
        is_editor_hidden = self.map_object_data_ref.get("editor_hidden", False)
        opacity_prop = self.map_object_data_ref.get("properties", {}).get("opacity", 100)
        self.setVisible(not is_editor_hidden and opacity_prop > 0)


        self.interaction_handles: List[QGraphicsRectItem] = []
        self.current_interaction_mode: str = "resize"
        self._create_interaction_handles()
        self.show_interaction_handles(False)

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


    def _create_interaction_handles(self):
        if self.interaction_handles:
            for handle in self.interaction_handles:
                if handle.scene(): self.scene().removeItem(handle) # type: ignore
            self.interaction_handles.clear()

        for i in range(ALL_HANDLES_COUNT):
            handle = QGraphicsRectItem(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, self)
            handle.setZValue(self.zValue() + 10)
            handle.setVisible(False)
            handle.setData(0, i)
            self.interaction_handles.append(handle)

    def update_handle_positions(self):
        if not self.interaction_handles: return
        
        br_width = self.map_object_data_ref.get("current_width", self.pixmap().width())
        br_height = self.map_object_data_ref.get("current_height", self.pixmap().height())
        br = QRectF(0, 0, float(br_width), float(br_height))

        self.interaction_handles[HANDLE_TOP_LEFT].setPos(br.left(), br.top())
        self.interaction_handles[HANDLE_TOP_MIDDLE].setPos(br.center().x(), br.top())
        self.interaction_handles[HANDLE_TOP_RIGHT].setPos(br.right(), br.top())
        self.interaction_handles[HANDLE_MIDDLE_LEFT].setPos(br.left(), br.center().y())
        self.interaction_handles[HANDLE_MIDDLE_RIGHT].setPos(br.right(), br.center().y())
        self.interaction_handles[HANDLE_BOTTOM_LEFT].setPos(br.left(), br.bottom())
        self.interaction_handles[HANDLE_BOTTOM_MIDDLE].setPos(br.center().x(), br.bottom())
        self.interaction_handles[HANDLE_BOTTOM_RIGHT].setPos(br.right(), br.bottom())
        
        self.set_handle_style_and_visibility()

    def set_handle_style_and_visibility(self):
        is_selected_and_item_visible = self.isSelected() and self.isVisible()
        is_locked = self.map_object_data_ref.get("editor_locked", False)


        for i, handle in enumerate(self.interaction_handles):
            if not is_selected_and_item_visible or is_locked:
                handle.setVisible(False)
                continue

            handle.setVisible(True)
            if self.current_interaction_mode == "crop":
                handle.setBrush(QColor(50, 50, 50))
                handle.setPen(QPen(QColor(Qt.GlobalColor.white), 1.2))
            else:
                handle.setBrush(QColor(Qt.GlobalColor.white))
                handle.setPen(QPen(QColor(Qt.GlobalColor.black), 1))

    def show_interaction_handles(self, show: bool):
        if not self.interaction_handles and show:
            self._create_interaction_handles()
        if not self.interaction_handles: return

        is_locked = self.map_object_data_ref.get("editor_locked", False)
        effective_show = show and not is_locked

        for handle in self.interaction_handles:
            handle.setVisible(effective_show)
        
        if effective_show:
            self.update_handle_positions()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            is_selected = bool(value)
            self.show_interaction_handles(is_selected)
            if not is_selected and self.current_interaction_mode == "crop":
                self.set_interaction_mode("resize")

        is_locked = self.map_object_data_ref.get("editor_locked", False)
        if is_locked and change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            return self.pos()

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            if self.scene().property("is_actively_transforming_item") is True:
                return super().itemChange(change, value)

            new_pos: QPointF = value # type: ignore
            grid_size_prop = self.scene().property("grid_size")
            grid_size = grid_size_prop if isinstance(grid_size_prop, (int, float)) and grid_size_prop > 0 else ED_CONFIG.BASE_GRID_SIZE

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if int(snapped_x) != self.map_object_data_ref.get('world_x') or \
               int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                
                map_view = self.scene().parent() # type: ignore
                if hasattr(map_view, 'object_graphically_moved_signal'):
                    map_view.object_graphically_moved_signal.emit(self.map_object_data_ref)

            if abs(new_pos.x() - snapped_x) > 1e-3 or abs(new_pos.y() - snapped_y) > 1e-3:
                return QPointF(float(snapped_x), float(snapped_y))
            return new_pos
        
        return super().itemChange(change, value)

    def update_visuals_from_data(self, editor_state: Any): # editor_state type hint can be 'EditorState' from .editor_state
        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z:
            self.setZValue(new_z)
        
        is_editor_hidden = self.map_object_data_ref.get("editor_hidden", False)
        opacity_prop = self.map_object_data_ref.get("properties", {}).get("opacity", 100)
        self.setVisible(not is_editor_hidden and opacity_prop > 0)
        
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not is_locked)
        if is_locked:
             self.show_interaction_handles(False)
        elif self.isSelected():
             self.show_interaction_handles(True)


        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y):
            self.setPos(new_pos_x, new_pos_y)

        self._update_display_aspect_ratio()
        
        self.prepareGeometryChange()
        self.update_handle_positions()

    def hoverMoveEvent(self, event: QHoverEvent):
        if self.isSelected() and not self.map_object_data_ref.get("editor_locked", False):
            for i in range(len(self.interaction_handles)):
                handle = self.interaction_handles[i]
                if handle.isVisible() and handle.sceneBoundingRect().contains(event.scenePos()): # type: ignore
                    if i < 8:
                        cursors = [Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor,
                                   Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeHorCursor,
                                   Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor]
                        QApplication.setOverrideCursor(QCursor(cursors[i]))
                        return
        QApplication.restoreOverrideCursor()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QHoverEvent):
        QApplication.restoreOverrideCursor()
        super().hoverLeaveEvent(event)

    def set_interaction_mode(self, mode: str):
        is_custom_image = isinstance(self, CustomImageMapItem)
        
        if mode == "crop" and not is_custom_image:
            logger.debug(f"Crop mode not supported for {type(self).__name__}. Staying in resize.")
            if self.current_interaction_mode != "resize":
                self.current_interaction_mode = "resize"
                self.update_handle_positions()
            return

        if mode in ["resize", "crop"]:
            if self.current_interaction_mode != mode:
                self.current_interaction_mode = mode
                self.update_handle_positions()
                if logger: logger.debug(f"Item {id(self.map_object_data_ref)} interaction mode set to {mode}")
        else:
            logger.warning(f"Unknown interaction mode: {mode}")


class CustomImageMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: Any, parent: Optional[QGraphicsItem] = None): # editor_state type hint can be 'EditorState'
        self.editor_state_ref = editor_state
        initial_pixmap = self._load_pixmap_from_data(map_object_data_ref, editor_state)
        super().__init__(map_object_data_ref, initial_pixmap, parent)
        logger.debug(f"CustomImageMapItem (ID {id(self.map_object_data_ref)}) __init__ called. Opacity from data: {self.map_object_data_ref.get('properties', {}).get('opacity')}")


    def _load_pixmap_from_data(self, obj_data: Dict[str, Any], editor_state: Any) -> QPixmap: # editor_state type hint
        current_width = obj_data.get("current_width", ED_CONFIG.BASE_GRID_SIZE)
        current_height = obj_data.get("current_height", ED_CONFIG.BASE_GRID_SIZE)
        
        map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function)
        rel_path = obj_data.get("source_file_path", "")
        
        display_w = int(max(1, current_width))
        display_h = int(max(1, current_height))
        
        final_pixmap = QPixmap(display_w, display_h)
        final_pixmap.fill(Qt.GlobalColor.transparent)

        opacity_percent = obj_data.get("properties", {}).get("opacity", 100)
        if not isinstance(opacity_percent, (int, float)):
            opacity_percent = 100
        opacity_value = max(0.0, min(1.0, float(opacity_percent) / 100.0))
        # logger.debug(f"CustomImageMapItem (ID {id(obj_data)}): _load_pixmap_from_data. Opacity: {opacity_percent}% ({opacity_value:.2f}) for path '{rel_path}'")


        if map_folder and rel_path:
            full_image_path = os.path.join(map_folder, rel_path)
            if os.path.exists(full_image_path):
                full_qimage = QImage(full_image_path)
                if not full_qimage.isNull():
                    if (obj_data.get("original_width") != full_qimage.width() or
                        obj_data.get("original_height") != full_qimage.height()):
                        obj_data["original_width"] = full_qimage.width()
                        obj_data["original_height"] = full_qimage.height()

                    image_to_render = full_qimage
                    crop_rect_data = obj_data.get("crop_rect")

                    if isinstance(crop_rect_data, dict) and \
                       all(k in crop_rect_data for k in ["x", "y", "width", "height"]):
                        crop_x = int(crop_rect_data["x"])
                        crop_y = int(crop_rect_data["y"])
                        crop_w = int(crop_rect_data["width"])
                        crop_h = int(crop_rect_data["height"])

                        orig_w = obj_data.get("original_width", full_qimage.width())
                        orig_h = obj_data.get("original_height", full_qimage.height())

                        if not (0 <= crop_x < orig_w and \
                                0 <= crop_y < orig_h and \
                                crop_w > 0 and crop_h > 0 and \
                                crop_x + crop_w <= orig_w and \
                                crop_y + crop_h <= orig_h):
                            logger.warning(f"Invalid crop_rect {crop_rect_data} for image {rel_path} (original size {orig_w}x{orig_h}). Using full image.")
                            obj_data["crop_rect"] = None
                        else:
                            qt_crop_rect = QRect(crop_x, crop_y, crop_w, crop_h)
                            image_to_render = full_qimage.copy(qt_crop_rect)
                    
                    if not image_to_render.isNull():
                        scaled_image = image_to_render.scaled(
                            display_w, display_h,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        painter = QPainter(final_pixmap)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                        painter.setOpacity(opacity_value) # This applies the item's overall opacity
                        painter.drawImage(0, 0, scaled_image)
                        painter.end()
                            
                    else:
                        logger.warning(f"CustomImageMapItem: image_to_render is null after crop/copy for {full_image_path}")
                        painter = QPainter(final_pixmap)
                        painter.fillRect(final_pixmap.rect(), QColor(255, 0, 255, int(120 * opacity_value))) 
                        painter.end()
                else:
                    logger.warning(f"CustomImageMapItem: Failed to load QImage from {full_image_path}")
                    painter = QPainter(final_pixmap)
                    painter.fillRect(final_pixmap.rect(), QColor(255, 0, 255, int(120 * opacity_value))) 
                    painter.end()
            else:
                logger.warning(f"CustomImageMapItem: Image file not found at {full_image_path}")
                painter = QPainter(final_pixmap)
                painter.fillRect(final_pixmap.rect(), QColor(255, 165, 0, int(120 * opacity_value))) 
                painter.end()
        else:
            logger.warning(f"CustomImageMapItem: Missing map_folder or relative_path for custom image.")
            painter = QPainter(final_pixmap)
            painter.fillRect(final_pixmap.rect(), QColor(255, 255, 0, int(120 * opacity_value))) 
            painter.end()
            
        return final_pixmap

    def update_visuals_from_data(self, editor_state: Any): # editor_state type hint
        current_opacity_percent = self.map_object_data_ref.get('properties', {}).get('opacity', 100)
        # logger.debug(f"CustomImageMapItem (ID {id(self.map_object_data_ref)}): ENTER update_visuals_from_data. Opacity from data: {current_opacity_percent}")
        
        self.prepareGeometryChange() 
        
        new_pixmap = self._load_pixmap_from_data(self.map_object_data_ref, editor_state)
        
        self.setPixmap(new_pixmap)
        # logger.debug(f"CustomImageMapItem (ID {id(self.map_object_data_ref)}): Pixmap set. New pixmap size: {new_pixmap.size()}")
        
        super().update_visuals_from_data(editor_state) 
        
        # logger.debug(f"CustomImageMapItem (ID {id(self.map_object_data_ref)}): Calling self.update() to schedule repaint.")
        self.update()
        
        if self.scene() and self.scene().views():
            # logger.debug(f"CustomImageMapItem (ID {id(self.map_object_data_ref)}): Calling scene().update() for item's bounding rect.")
            self.scene().update(self.mapToScene(self.boundingRect()).boundingRect())
            for view in self.scene().views():
                view.viewport().update()


class TriggerSquareMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: Any, parent: Optional[QGraphicsItem] = None): # editor_state type hint
        current_w = map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))
        transparent_pixmap = QPixmap(display_w, display_h)
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        
        super().__init__(map_object_data_ref, transparent_pixmap, parent)
        self.editor_state_ref = editor_state
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h
        self.update_visuals_from_data(editor_state)


    def boundingRect(self) -> QRectF:
        w = self.map_object_data_ref.get("current_width", 0.0)
        h = self.map_object_data_ref.get("current_height", 0.0)
        return QRectF(0, 0, float(w), float(h))

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        props = self.map_object_data_ref.get("properties", {})
        rect = self.boundingRect()

        is_editor_preview = False
        if self.scene() and self.scene().parent() and hasattr(self.scene().parent(), 'editor_state'):
            parent_widget = self.scene().parent()
            if hasattr(parent_widget, 'editor_state'):
                 is_editor_preview = parent_widget.editor_state.is_game_preview_mode # type: ignore
        
        item_opacity_percent = props.get("opacity", 100)
        item_opacity_float = max(0.0, min(1.0, float(item_opacity_percent) / 100.0))

        if not props.get("visible", True) and is_editor_preview:
            return
        if item_opacity_float < 0.01 and is_editor_preview: 
            return

        painter.save()
        painter.setOpacity(item_opacity_float)

        if not props.get("visible", True) and not is_editor_preview: 
            painter.setPen(QPen(QColor(150, 150, 255, int(100 * item_opacity_float)), 2, Qt.PenStyle.DashLine)) 
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            
            text_color = QColor(0,0,0, int(255 * item_opacity_float)) 
            if item_opacity_float * 100 < 50: 
                text_color = QColor(50,50,50, int(255 * item_opacity_float))
            painter.setPen(text_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Invisible Trigger")
            
            if option.state & QStyle.StateFlag.State_Selected: # type: ignore
                selection_pen = QPen(QColor(255, 255, 0, int(255 * item_opacity_float)), 2.5, Qt.PenStyle.SolidLine)
                painter.setPen(selection_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect.adjusted(1,1,-1,-1))
            painter.restore(); return

        image_path_rel = props.get("image_in_square", "")
        image_drawn_successfully = False
        if image_path_rel and hasattr(self, 'editor_state_ref'):
            map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state_ref, self.editor_state_ref.map_name_for_function)
            if map_folder:
                full_image_path = os.path.join(map_folder, image_path_rel)
                if os.path.exists(full_image_path):
                    img = QImage(full_image_path)
                    if not img.isNull():
                        target_size = rect.size().toSize()
                        if target_size.width() > 0 and target_size.height() > 0:
                            painter.drawImage(rect, img.scaled(target_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                            image_drawn_successfully = True
                        else:
                            logger.warning(f"TriggerSquareMapItem: Invalid target_size {target_size} for image drawing.")
        
        if not image_drawn_successfully:
            fill_color_rgba = props.get("fill_color_rgba")
            base_q_color: QColor
            if fill_color_rgba and isinstance(fill_color_rgba, (list, tuple)) and len(fill_color_rgba) == 4:
                # Use the alpha from RGBA, painter.setOpacity will further modulate this
                base_q_color = QColor(fill_color_rgba[0], fill_color_rgba[1], fill_color_rgba[2], fill_color_rgba[3])
            else: 
                base_q_color = QColor(100,100,255,100) # Default semi-transparent blue

            painter.setBrush(base_q_color)
            painter.setPen(QPen(QColor(0,0,0, int(180 * item_opacity_float)), 1)) 
            painter.drawRect(rect)

            if not fill_color_rgba: 
                text_color_with_opacity = QColor(0,0,0, int(255 * item_opacity_float))
                painter.setPen(text_color_with_opacity)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Trigger")

        if option.state & QStyle.StateFlag.State_Selected: # type: ignore
            pen = QPen(QColor(255, 255, 0, int(255*item_opacity_float)), 2, Qt.PenStyle.SolidLine) 
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
        
        painter.restore()

    def update_visuals_from_data(self, editor_state: Any): # editor_state type hint
        current_w = self.map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE * 2)
        current_h = self.map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE * 2)
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h

        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))

        if self.pixmap().width() != display_w or self.pixmap().height() != display_h:
            self.prepareGeometryChange()
            new_pixmap = QPixmap(display_w, display_h)
            new_pixmap.fill(Qt.GlobalColor.transparent)
            self.setPixmap(new_pixmap)
        
        super().update_visuals_from_data(editor_state) 
        self.update() 

    def set_interaction_mode(self, mode: str):
        if mode == "resize":
            super().set_interaction_mode(mode)
        else: 
            if self.current_interaction_mode != "resize":
                super().set_interaction_mode("resize")

#################### END OF FILE: editor_custom_items.py ####################