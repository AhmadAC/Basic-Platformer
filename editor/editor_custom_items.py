#################### START OF FILE: editor_custom_items.py ####################

# editor/editor_custom_items.py
# -*- coding: utf-8 -*-
"""
Custom QGraphicsItem classes for special map objects in the editor,
such as uploaded images and trigger squares.
Version 2.2.12 (Refined BaseResizableMapItem visibility and transform)
- `update_visuals_from_data` in `BaseResizableMapItem` now correctly calls
  `self.setVisible()` *after* all other property updates, including opacity.
- `_apply_orientation_transform` for `BaseResizableMapItem` now applies to the item's
  transform directly, ensuring correct visual representation for custom items too.
- Ensured `TriggerSquareMapItem` uses the `item_opacity_float` for all its drawing
  elements (fill, pen, text) to respect the 'opacity' property consistently.
"""
import sys
import os
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QApplication,
    QStyleOptionGraphicsItem, QWidget, QStyle
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor, QHoverEvent,
    QPainterPath, QTransform, QFont # Added QFont
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QRect

# --- Project Root Setup ---
_EDITOR_CUSTOM_ITEMS_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_EDITOR_CUSTOM_ITEMS = os.path.dirname(_EDITOR_CUSTOM_ITEMS_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_EDITOR_CUSTOM_ITEMS not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_EDITOR_CUSTOM_ITEMS)
# --- End Project Root Setup ---

# --- Corrected Relative Imports for editor package modules ---
try:
    from editor import editor_config as ED_CONFIG
    from editor import editor_map_utils
    from editor.editor_state import EditorState # Forward declaration sufficient for type hints
except ImportError as e_cust_imp:
    import logging as logging_fallback_cust
    logging_fallback_cust.basicConfig(level=logging.DEBUG)
    _logger_cust_fb = logging_fallback_cust.getLogger(__name__ + "_cust_fb")
    _logger_cust_fb.critical(f"CRITICAL editor_custom_items.py Import Error: {e_cust_imp}. Editor items might not function.", exc_info=True)
    # Define minimal fallbacks for ED_CONFIG if needed for standalone testing/basic functionality
    class ED_CONFIG_FALLBACK_CUST:
        BASE_GRID_SIZE = 40
        TS = 40 # Added for InvisibleWallMapItem defaults consistency
        CUSTOM_IMAGE_ASSET_KEY = "custom_image_object"
        TRIGGER_SQUARE_ASSET_KEY = "trigger_square"
        INVISIBLE_WALL_ASSET_KEY_PALETTE = "invisible_wall_tool" # For type check in map_view_widget if needed
        DEFAULT_INVISIBLE_WALL_FILL_COLOR_RGBA = (255,0,0,100)
        SEMI_TRANSPARENT_RED = (255,0,0,100)


    ED_CONFIG = ED_CONFIG_FALLBACK_CUST() # type: ignore
    class EditorState: pass # Dummy for type hint

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
        self.setFlags(current_flags) # type: ignore

        self.setAcceptHoverEvents(True)
        self.setZValue(self.map_object_data_ref.get("layer_order", 0))

        self.interaction_handles: List[QGraphicsRectItem] = []
        self.current_interaction_mode: str = "resize" # Default mode
        self._create_interaction_handles()
        self.show_interaction_handles(False) # Initially hidden

        # Apply initial transform and visibility after all setup
        self._apply_orientation_transform()
        is_editor_hidden = self.map_object_data_ref.get("editor_hidden", False)
        opacity_prop = self.map_object_data_ref.get("properties", {}).get("opacity", 100)
        self.setVisible(not is_editor_hidden and opacity_prop > 0)

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
            else: # Fallback if no valid dimensions found
                pix = self.pixmap()
                if not pix.isNull() and pix.height() > 0:
                    self.display_aspect_ratio = float(pix.width()) / float(pix.height())
                else:
                    self.display_aspect_ratio = None


    def _create_interaction_handles(self):
        if self.interaction_handles:
            for handle in self.interaction_handles:
                if handle.scene(): self.scene().removeItem(handle) # type: ignore
            self.interaction_handles.clear()

        for i in range(ALL_HANDLES_COUNT):
            handle = QGraphicsRectItem(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, self)
            handle.setZValue(self.zValue() + 10) # Ensure handles are above the item
            handle.setVisible(False)
            handle.setData(0, i) # Store handle index
            self.interaction_handles.append(handle)

    def update_handle_positions(self):
        if not self.interaction_handles: return

        # Handles are positioned relative to the item's local 0,0
        # The item's pixmap defines its local bounding rect if it's a QGraphicsPixmapItem
        # For QGraphicsRectItem (TriggerSquare), its own rect defines it.
        br_width = 0.0
        br_height = 0.0

        if isinstance(self, QGraphicsPixmapItem) and not self.pixmap().isNull():
            br_width = float(self.pixmap().width())
            br_height = float(self.pixmap().height())
        elif isinstance(self, QGraphicsRectItem): # Like TriggerSquareMapItem
            br_width = self.rect().width()
            br_height = self.rect().height()
        else: # Fallback if type is unknown or pixmap is null
            br_width = float(self.map_object_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE))
            br_height = float(self.map_object_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE))


        br = QRectF(0, 0, br_width, br_height) # Local coordinates

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
            # Style based on interaction mode
            if self.current_interaction_mode == "crop":
                handle.setBrush(QColor(50, 50, 50, 180)) # Dark semi-transparent for crop
                handle.setPen(QPen(QColor(Qt.GlobalColor.white), 1.2))
            else: # Default resize mode
                handle.setBrush(QColor(Qt.GlobalColor.white))
                handle.setPen(QPen(QColor(Qt.GlobalColor.black), 1))

    def show_interaction_handles(self, show: bool):
        if not self.interaction_handles and show:
            self._create_interaction_handles() # Create if they don't exist
        if not self.interaction_handles: return # Still no handles, bail

        is_locked = self.map_object_data_ref.get("editor_locked", False)
        effective_show = show and not is_locked and self.isVisible() # Handles only visible if item is

        for handle in self.interaction_handles:
            handle.setVisible(effective_show)

        if effective_show:
            self.update_handle_positions() # Update positions when shown

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            is_selected = bool(value)
            self.show_interaction_handles(is_selected)
            if not is_selected and self.current_interaction_mode == "crop":
                self.set_interaction_mode("resize") # Revert to resize if deselected while cropping

        is_locked = self.map_object_data_ref.get("editor_locked", False)
        if is_locked and change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            return self.pos() # Prevent movement if locked

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            if self.scene().property("is_actively_transforming_item") is True: # If resizing/cropping, allow sub-pixel
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
                return QPointF(float(snapped_x), float(snapped_y)) # Return snapped position
            return new_pos
        
        return super().itemChange(change, value)


    def _apply_orientation_transform(self):
        """Applies flip and rotation transform to the item itself."""
        is_flipped_h = self.map_object_data_ref.get("is_flipped_h", False)
        rotation_angle_deg = float(self.map_object_data_ref.get("rotation", 0))

        # BasePixmapItem's local rect is (0,0, pixmap.width(), pixmap.height())
        # Or for TriggerSquare, it's (0,0, self.rect().width(), self.rect().height())
        item_local_rect = self.boundingRect() # This gives local bounds
        center_x = item_local_rect.width() / 2.0
        center_y = item_local_rect.height() / 2.0

        transform = QTransform()
        transform.translate(center_x, center_y)
        if is_flipped_h:
            transform.scale(-1, 1)
        if rotation_angle_deg != 0:
            transform.rotate(rotation_angle_deg)
        transform.translate(-center_x, -center_y)
        
        self.setTransform(transform)

    def update_visuals_from_data(self, editor_state: EditorState):
        # Position
        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y):
            self.setPos(new_pos_x, new_pos_y)

        # Z-order (layer)
        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z:
            self.setZValue(new_z)

        # Lock state affects movability
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not is_locked) # type: ignore
        
        # Transformations (flip/rotation)
        self._apply_orientation_transform() # Apply flip/rotation

        # Aspect ratio for constrained resize
        self._update_display_aspect_ratio()

        # Handles need to be updated if selection state changes or item becomes visible/hidden
        if self.isSelected():
            self.show_interaction_handles(True) # This will re-evaluate visibility based on lock state
        else:
            self.show_interaction_handles(False)
            
        # Visibility (must be last, after opacity and lock are set)
        is_editor_hidden_flag = self.map_object_data_ref.get("editor_hidden", False)
        opacity_prop_val = self.map_object_data_ref.get("properties", {}).get("opacity", 100)
        self.setVisible(not is_editor_hidden_flag and opacity_prop_val > 0)
        
        # Ensure geometry changes are propagated for bounding rect updates if pixmap changed
        self.prepareGeometryChange()
        self.update_handle_positions() # Update handle positions if item's geometry changed
        self.update() # Schedule a repaint for the item itself


    def hoverMoveEvent(self, event: QHoverEvent):
        if self.isSelected() and not self.map_object_data_ref.get("editor_locked", False) and self.isVisible():
            for i in range(len(self.interaction_handles)):
                handle = self.interaction_handles[i]
                # Check if handle itself is visible and mouse is over it
                if handle.isVisible() and handle.sceneBoundingRect().contains(event.scenePos()): # type: ignore
                    if i < ALL_HANDLES_COUNT: # Ensure index is valid for cursors
                        cursors = [Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor,
                                   Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeHorCursor,
                                   Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor]
                        QApplication.setOverrideCursor(QCursor(cursors[i]))
                        return
        QApplication.restoreOverrideCursor() # Restore if not over a handle
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
                self.update_handle_positions() # Updates handle style
            return

        if mode in ["resize", "crop"]:
            if self.current_interaction_mode != mode:
                self.current_interaction_mode = mode
                self.update_handle_positions() # Updates handle style
                if logger: logger.debug(f"Item (ID: {id(self.map_object_data_ref)}) interaction mode set to {mode}")
        else:
            logger.warning(f"Unknown interaction mode: {mode}")


class CustomImageMapItem(BaseResizableMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: EditorState, parent: Optional[QGraphicsItem] = None):
        self.editor_state_ref = editor_state
        initial_pixmap = self._load_pixmap_from_data(map_object_data_ref, editor_state)
        super().__init__(map_object_data_ref, initial_pixmap, parent)

    def _load_pixmap_from_data(self, obj_data: Dict[str, Any], editor_state: EditorState) -> QPixmap:
        current_width = obj_data.get("current_width", ED_CONFIG.BASE_GRID_SIZE)
        current_height = obj_data.get("current_height", ED_CONFIG.BASE_GRID_SIZE)

        map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function)
        rel_path_from_map_custom_folder = obj_data.get("source_file_path", "") # e.g., "Custom/my_image.png"

        display_w = int(max(1, current_width))
        display_h = int(max(1, current_height))

        final_pixmap = QPixmap(display_w, display_h)
        final_pixmap.fill(Qt.GlobalColor.transparent)

        opacity_percent = obj_data.get("properties", {}).get("opacity", 100)
        if not isinstance(opacity_percent, (int, float)): opacity_percent = 100
        opacity_value = max(0.0, min(1.0, float(opacity_percent) / 100.0))

        if map_folder and rel_path_from_map_custom_folder:
            # The path stored in `source_file_path` is relative to the map's folder (e.g., "Custom/image.png")
            # So, join it with `map_folder` which is the absolute path to the map's directory.
            full_image_path_abs = os.path.normpath(os.path.join(map_folder, rel_path_from_map_custom_folder))

            if os.path.exists(full_image_path_abs):
                full_qimage = QImage(full_image_path_abs)
                if not full_qimage.isNull():
                    # Update original dimensions if they differ from loaded image or aren't set
                    if obj_data.get("original_width") != full_qimage.width() or \
                       obj_data.get("original_height") != full_qimage.height():
                        obj_data["original_width"] = full_qimage.width()
                        obj_data["original_height"] = full_qimage.height()

                    image_to_render = full_qimage
                    crop_rect_data = obj_data.get("crop_rect")

                    if isinstance(crop_rect_data, dict) and \
                       all(k in crop_rect_data for k in ["x", "y", "width", "height"]):
                        crop_x = int(crop_rect_data["x"]); crop_y = int(crop_rect_data["y"])
                        crop_w = int(crop_rect_data["width"]); crop_h = int(crop_rect_data["height"])
                        orig_w = obj_data.get("original_width", full_qimage.width())
                        orig_h = obj_data.get("original_height", full_qimage.height())

                        if not (0 <= crop_x < orig_w and 0 <= crop_y < orig_h and \
                                crop_w > 0 and crop_h > 0 and \
                                crop_x + crop_w <= orig_w and crop_y + crop_h <= orig_h):
                            logger.warning(f"Invalid crop_rect {crop_rect_data} for image {rel_path_from_map_custom_folder}. Using full.")
                            obj_data["crop_rect"] = None # Reset invalid crop
                        else:
                            qt_crop_rect = QRect(crop_x, crop_y, crop_w, crop_h)
                            image_to_render = full_qimage.copy(qt_crop_rect)

                    if not image_to_render.isNull():
                        scaled_image = image_to_render.scaled(
                            display_w, display_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                        )
                        painter = QPainter(final_pixmap)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                        painter.setOpacity(opacity_value)
                        painter.drawImage(0, 0, scaled_image)
                        painter.end()
                    else: # image_to_render became null after crop/copy
                        logger.warning(f"CustomImageMapItem: image_to_render is null after crop/copy for {full_image_path_abs}")
                        painter = QPainter(final_pixmap); painter.setOpacity(opacity_value); painter.fillRect(final_pixmap.rect(), QColor(255,0,255)); painter.end() # Magenta fallback
                else: # full_qimage isNull
                    logger.warning(f"CustomImageMapItem: Failed to load QImage from {full_image_path_abs}")
                    painter = QPainter(final_pixmap); painter.setOpacity(opacity_value); painter.fillRect(final_pixmap.rect(), QColor(255,0,255)); painter.end()
            else: # File not found
                logger.warning(f"CustomImageMapItem: Image file not found at {full_image_path_abs}")
                painter = QPainter(final_pixmap); painter.setOpacity(opacity_value); painter.fillRect(final_pixmap.rect(), QColor(255,165,0)); painter.end() # Orange fallback
        else: # Missing map_folder or rel_path
            logger.warning(f"CustomImageMapItem: Missing map_folder ('{map_folder}') or relative_path ('{rel_path_from_map_custom_folder}').")
            painter = QPainter(final_pixmap); painter.setOpacity(opacity_value); painter.fillRect(final_pixmap.rect(), QColor(255,255,0)); painter.end() # Yellow fallback

        return final_pixmap

    def update_visuals_from_data(self, editor_state: EditorState):
        self.prepareGeometryChange() # Signal that geometry might change
        new_pixmap = self._load_pixmap_from_data(self.map_object_data_ref, editor_state)
        self.setPixmap(new_pixmap)
        super().update_visuals_from_data(editor_state) # Handles pos, Z, lock, handles, visibility, transform
        self.update() # Request repaint
        if self.scene(): self.scene().update(self.mapToScene(self.boundingRect()).boundingRect())


class BaseShapeMapItem(BaseResizableMapItem):
    """
    Common base for resizable items that are primarily defined by a shape
    drawn in their paint method (e.g., TriggerSquare, InvisibleWall).
    Their pixmap is a transparent placeholder.
    """
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: EditorState,
                 default_size_multiplier: int = 2, parent: Optional[QGraphicsItem] = None):
        # For these items, the "pixmap" is just a transparent placeholder.
        # The actual drawing happens in the paint method.
        default_dim = ED_CONFIG.BASE_GRID_SIZE * default_size_multiplier
        current_w = map_object_data_ref.get("current_width", default_dim)
        current_h = map_object_data_ref.get("current_height", default_dim)
        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))
        transparent_pixmap = QPixmap(display_w, display_h)
        transparent_pixmap.fill(Qt.GlobalColor.transparent)

        super().__init__(map_object_data_ref, transparent_pixmap, parent)
        self.editor_state_ref = editor_state
        # Ensure current_width/height are in data_ref if not already (BaseResizable uses them)
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h
        # update_visuals_from_data is called by BaseResizableMapItem's __init__
        # which in turn calls _apply_orientation_transform and setVisible.
        # If further specific updates are needed immediately for BaseShapeMapItem, they can be done here.

    def boundingRect(self) -> QRectF:
        # Bounding rect is based on current_width/height from data_ref, in local coords
        w = self.map_object_data_ref.get("current_width", 0.0)
        h = self.map_object_data_ref.get("current_height", 0.0)
        return QRectF(0, 0, float(w), float(h))

    def shape(self) -> QPainterPath: # For accurate collision/selection
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def update_visuals_from_data(self, editor_state: EditorState):
        # Determine default dimension based on a common understanding (e.g., multiplier 2)
        # This part should ideally not need to know the 'default_size_multiplier' again,
        # as current_width/height should already be in map_object_data_ref.
        # If they are missing, it implies an issue with initial data setup.
        default_dim_fallback = ED_CONFIG.BASE_GRID_SIZE * 2 # Fallback default size
        current_w = self.map_object_data_ref.get("current_width", default_dim_fallback)
        current_h = self.map_object_data_ref.get("current_height", default_dim_fallback)
        
        # Ensure data_ref has these, as BaseResizableMapItem might use them internally
        # or other parts of the system might expect them after an update.
        self.map_object_data_ref["current_width"] = current_w
        self.map_object_data_ref["current_height"] = current_h

        # The "pixmap" for these items is just a transparent placeholder.
        # Its size needs to match current_width/height for BaseResizableMapItem's handle logic.
        display_w = int(max(1, current_w))
        display_h = int(max(1, current_h))

        current_pixmap = self.pixmap()
        if current_pixmap.width() != display_w or current_pixmap.height() != display_h:
            self.prepareGeometryChange() # Crucial before changing effective bounds
            new_transparent_pixmap = QPixmap(display_w, display_h)
            new_transparent_pixmap.fill(Qt.GlobalColor.transparent)
            self.setPixmap(new_transparent_pixmap)
            # prepareGeometryChange was called, so scene will update bounding rect.

        super().update_visuals_from_data(editor_state) # Handles pos, Z, lock, handles, visibility, transform
        self.update() # Request repaint for paint() method to redraw content

    def set_interaction_mode(self, mode: str):
        # These items generally only support resize mode, not crop.
        if mode == "resize":
            super().set_interaction_mode(mode)
        else: # If trying to set to crop or other, default to resize.
            if self.current_interaction_mode != "resize":
                super().set_interaction_mode("resize")
                logger.debug(f"{type(self).__name__} (ID: {id(self.map_object_data_ref)}): Interaction mode forced to 'resize' as '{mode}' is not supported.")


class TriggerSquareMapItem(BaseShapeMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: EditorState, parent: Optional[QGraphicsItem] = None):
        super().__init__(map_object_data_ref, editor_state, default_size_multiplier=2, parent=parent)
        # Specific initialization for TriggerSquareMapItem, if any, can go here.
        # Example: self.setToolTip("Trigger Square") if needed

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        props = self.map_object_data_ref.get("properties", {})
        rect_to_draw_local = self.boundingRect() # Use local bounding rect for drawing

        # Determine if in-game preview mode
        is_editor_preview = False
        if self.scene() and self.scene().parent() and hasattr(self.scene().parent(), 'editor_state'):
            parent_map_view_widget = self.scene().parent()
            if hasattr(parent_map_view_widget, 'editor_state'):
                 is_editor_preview = parent_map_view_widget.editor_state.is_game_preview_mode # type: ignore

        item_opacity_percent = props.get("opacity", 100)
        if not isinstance(item_opacity_percent, (int, float)): item_opacity_percent = 100
        item_opacity_float = max(0.0, min(1.0, float(item_opacity_percent) / 100.0))

        # Check visibility property for game preview
        if not props.get("visible", True) and is_editor_preview:
            return # Don't draw if invisible in game preview
        
        # Check overall item opacity for game preview
        if item_opacity_float < 0.01 and is_editor_preview:
            return # Don't draw if effectively transparent in game preview

        painter.save()
        painter.setOpacity(item_opacity_float) # Apply overall item opacity

        # Case 1: Invisible in-game, but visible in editor (draw dashed)
        if not props.get("visible", True) and not is_editor_preview:
            pen_alpha_editor = int(180 * item_opacity_float) # Modulate editor dashed line alpha
            painter.setPen(QPen(QColor(150, 150, 255, pen_alpha_editor), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect_to_draw_local)

            text_alpha_editor = int(200 * item_opacity_float) # Modulate text alpha
            text_color_editor = QColor(50, 50, 50, text_alpha_editor)
            painter.setPen(text_color_editor)
            painter.drawText(rect_to_draw_local, Qt.AlignmentFlag.AlignCenter, "Invisible Trigger") # type: ignore
        else: # Case 2: Visible in-game (or always visible in editor if props.visible is True)
            image_path_rel_in_props = props.get("image_in_square", "")
            image_drawn_successfully = False

            if image_path_rel_in_props and hasattr(self, 'editor_state_ref'):
                map_folder_path = editor_map_utils.get_map_specific_folder_path(self.editor_state_ref, self.editor_state_ref.map_name_for_function)
                if map_folder_path:
                    full_image_path_abs = os.path.normpath(os.path.join(map_folder_path, image_path_rel_in_props))
                    if os.path.exists(full_image_path_abs):
                        img = QImage(full_image_path_abs)
                        if not img.isNull():
                            target_size = rect_to_draw_local.size().toSize()
                            if target_size.width() > 0 and target_size.height() > 0:
                                painter.drawImage(rect_to_draw_local, img.scaled(target_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                                image_drawn_successfully = True
                            else: logger.warning(f"TriggerSquareMapItem: Invalid target_size {target_size} for image drawing.")
                        else: logger.warning(f"TriggerSquareMapItem: QImage failed to load from {full_image_path_abs}")
                    else: logger.warning(f"TriggerSquareMapItem: Image for trigger not found at {full_image_path_abs}")

            if not image_drawn_successfully: # Fallback to colored rectangle if no image or image failed
                fill_color_rgba_prop = props.get("fill_color_rgba")
                base_q_color: QColor
                if fill_color_rgba_prop and isinstance(fill_color_rgba_prop, (list,tuple)) and len(fill_color_rgba_prop) == 4:
                    # The fill color's alpha is already part of RGBA, painter.setOpacity modulates it further
                    base_q_color = QColor(fill_color_rgba_prop[0], fill_color_rgba_prop[1], fill_color_rgba_prop[2], fill_color_rgba_prop[3])
                else:
                    base_q_color = QColor(100, 100, 255, 100) # Default semi-transparent blue

                painter.setBrush(base_q_color)
                pen_alpha_visible = int(200 * item_opacity_float) # Modulate pen alpha
                painter.setPen(QPen(QColor(0, 0, 0, pen_alpha_visible), 1))
                painter.drawRect(rect_to_draw_local)

                # Draw "Trigger" text if no RGBA color property is explicitly set (implies default visual)
                if not fill_color_rgba_prop:
                    text_alpha_visible = int(220 * item_opacity_float) # Modulate text alpha
                    painter.setPen(QColor(0, 0, 0, text_alpha_visible))
                    painter.drawText(rect_to_draw_local, Qt.AlignmentFlag.AlignCenter, "Trigger") # type: ignore

        # Selection highlight (applies to both dashed and filled versions)
        if option.state & QStyle.StateFlag.State_Selected: # type: ignore
            selection_pen_alpha = int(255 * item_opacity_float) # Modulate selection highlight alpha
            pen = QPen(QColor(255, 255, 0, selection_pen_alpha), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect_to_draw_local.adjusted(0.5, 0.5, -0.5, -0.5)) # Slight inset for better look

        painter.restore() # Restore opacity and other painter states


class InvisibleWallMapItem(BaseShapeMapItem):
    def __init__(self, map_object_data_ref: Dict[str, Any], editor_state: EditorState, parent: Optional[QGraphicsItem] = None):
        super().__init__(map_object_data_ref, editor_state, default_size_multiplier=2, parent=parent)
        self.setToolTip("Invisible Wall")

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        props = self.map_object_data_ref.get("properties", {})
        rect_to_draw_local = self.boundingRect()

        is_editor_preview = False
        if self.scene() and self.scene().parent() and hasattr(self.scene().parent(), 'editor_state'):
             parent_map_view = self.scene().parent()
             if hasattr(parent_map_view, 'editor_state'): is_editor_preview = parent_map_view.editor_state.is_game_preview_mode

        item_opacity_percent = props.get("opacity", 100) 
        if not isinstance(item_opacity_percent, (int, float)): item_opacity_percent = 100
        item_opacity_float = max(0.0, min(1.0, float(item_opacity_percent) / 100.0))
        
        if not props.get("visible_in_game", False) and is_editor_preview: return 
        if item_opacity_float < 0.01 and not is_editor_preview: return # If in editor and opacity is ~0, don't draw

        painter.save()
        # When in editor (not preview), use the item_opacity_float.
        # When in preview AND visible_in_game is true, draw fully opaque (or based on a potential game-time opacity if that existed).
        effective_paint_opacity = item_opacity_float if not is_editor_preview else 1.0 
        
        # Use DEFAULT_INVISIBLE_WALL_FILL_COLOR_RGBA from ED_CONFIG
        fill_color_rgba_prop = ED_CONFIG.DEFAULT_INVISIBLE_WALL_FILL_COLOR_RGBA 
        base_q_color: QColor
        if fill_color_rgba_prop and isinstance(fill_color_rgba_prop, (list,tuple)) and len(fill_color_rgba_prop) == 4:
            r,g,b,a_config = fill_color_rgba_prop
            # The config alpha is the base; effective_paint_opacity modulates this
            final_alpha = int(a_config * effective_paint_opacity) 
            base_q_color = QColor(r,g,b, final_alpha) 
        else: # Fallback if config is somehow invalid
            r,g,b,a_default = ED_CONFIG.SEMI_TRANSPARENT_RED # Fallback
            base_q_color = QColor(r,g,b, int(a_default * effective_paint_opacity))
        
        painter.setBrush(base_q_color)
        
        # Solid border, slightly darker than fill
        border_color = base_q_color.darker(130)
        border_color.setAlpha(min(255, base_q_color.alpha() + 75)) # Make border more opaque
        pen_width = 1.0 # Thinner solid border
        painter.setPen(QPen(border_color, pen_width, Qt.PenStyle.SolidLine))
        painter.drawRect(rect_to_draw_local)

        # Text "INV" only in editor if reasonably opaque
        if not is_editor_preview and item_opacity_float > 0.1 : 
            text_alpha = int(200 * item_opacity_float) # Modulated by overall item opacity
            text_color_val = QColor(0,0,0, text_alpha) if base_q_color.lightnessF() > 0.6 else QColor(255,255,255, text_alpha)
            painter.setPen(text_color_val)
            font = painter.font(); 
            # Dynamic font size based on item height/width, with min/max
            font_size_px = max(8, min(rect_to_draw_local.height() * 0.25, rect_to_draw_local.width() * 0.2))
            font.setPixelSize(int(font_size_px)) # Use setPixelSize for more consistent sizing
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect_to_draw_local, Qt.AlignmentFlag.AlignCenter, "INV") # Changed to INV

        if option.state & QStyle.StateFlag.State_Selected: # type: ignore
            selection_pen_alpha = 255 # Always fully opaque selection highlight
            pen = QPen(QColor(255, 255, 0, selection_pen_alpha), 2, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True) # Ensure consistent line width regardless of zoom
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            # Adjust for pen width to draw inside the bounding rect for selection
            painter.drawRect(rect_to_draw_local.adjusted(pen.widthF()/2.0, pen.widthF()/2.0, -pen.widthF()/2.0, -pen.widthF()/2.0))
        painter.restore()

#################### END OF FILE: editor_custom_items.py ####################