# map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
Version 2.0.2 (Corrected placement logic, extensive logging)
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsItem, QColorDialog, QWidget
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QTransform, QImage,
    QWheelEvent, QMouseEvent, QKeyEvent, QFocusEvent
)
from PySide6.QtCore import Qt, Signal, Slot, QRectF, QPointF, QSize, QTimer

import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history
try:
    from editor_assets import get_asset_pixmap
except ImportError:
    logging.basicConfig(level=logging.DEBUG) 
    logger_mv_fallback = logging.getLogger(__name__ + ".fallback_assets")
    logger_mv_fallback.critical("map_view_widget.py: Failed to import get_asset_pixmap from editor_assets.")
    def get_asset_pixmap(asset_editor_key: str, asset_data_entry: Dict[str, Any],
                         target_size: QSize, override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
        logger_mv_fallback.error(f"Dummy get_asset_pixmap called for {asset_editor_key}")
        dummy_pix = QPixmap(target_size); dummy_pix.fill(Qt.GlobalColor.magenta); return dummy_pix

logger = logging.getLogger(__name__)

class MapObjectItem(QGraphicsPixmapItem):
    def __init__(self, editor_key: str, game_type_id: str, pixmap: QPixmap,
                 world_x: int, world_y: int, map_object_data_ref: Dict[str, Any], parent: Optional[QGraphicsItem] = None):
        super().__init__(pixmap, parent)
        self.editor_key = editor_key
        self.game_type_id = game_type_id
        self.map_object_data_ref = map_object_data_ref
        self.setPos(QPointF(float(world_x), float(world_y)))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.initial_pixmap = pixmap

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            new_pos = value 
            grid_size_prop = self.scene().property("grid_size")
            grid_size = grid_size_prop if isinstance(grid_size_prop, (int, float)) and grid_size_prop > 0 else ED_CONFIG.BASE_GRID_SIZE
            
            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if int(snapped_x) != self.map_object_data_ref.get('world_x') or \
               int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                if self.scene() and hasattr(self.scene().parent(), 'object_graphically_moved_signal'):
                    if isinstance(self.scene().parent(), MapViewWidget):
                        logger.debug(f"MapObjectItem: Emitting object_graphically_moved_signal for {self.editor_key}")
                        self.scene().parent().object_graphically_moved_signal.emit(self.map_object_data_ref)
            
            if abs(new_pos.x() - snapped_x) > 0.01 or abs(new_pos.y() - snapped_y) > 0.01:
                return QPointF(float(snapped_x), float(snapped_y))
            return new_pos 
        return super().itemChange(change, value)

    def update_visuals(self, new_pixmap: Optional[QPixmap] = None, new_color: Optional[QColor] = None, editor_state: Optional[EditorState] = None):
        if new_pixmap and not new_pixmap.isNull():
            self.setPixmap(new_pixmap)
            self.initial_pixmap = new_pixmap
        elif new_color and editor_state:
            asset_data = editor_state.assets_palette.get(self.editor_key)
            if asset_data and asset_data.get("colorable"):
                try:
                    target_w = self.initial_pixmap.width() if self.initial_pixmap and not self.initial_pixmap.isNull() else ED_CONFIG.BASE_GRID_SIZE
                    target_h = self.initial_pixmap.height() if self.initial_pixmap and not self.initial_pixmap.isNull() else ED_CONFIG.BASE_GRID_SIZE
                    colored_pixmap = get_asset_pixmap(
                        self.editor_key, asset_data,
                        target_size=QSize(int(target_w), int(target_h)),
                        override_color=new_color.getRgb()[:3]
                    )
                    if colored_pixmap and not colored_pixmap.isNull():
                        self.setPixmap(colored_pixmap)
                    elif self.initial_pixmap and not self.initial_pixmap.isNull():
                        self.setPixmap(self.initial_pixmap)
                except Exception as e:
                    logger.error(f"Error updating visual for {self.editor_key} with color {new_color.name()}: {e}", exc_info=True)
                    if self.initial_pixmap and not self.initial_pixmap.isNull(): self.setPixmap(self.initial_pixmap)
        elif self.initial_pixmap and not self.initial_pixmap.isNull():
             self.setPixmap(self.initial_pixmap)


class MapViewWidget(QGraphicsView):
    mouse_moved_on_map = Signal(tuple)
    map_object_selected_for_properties = Signal(object)
    map_content_changed = Signal()
    object_graphically_moved_signal = Signal(dict)

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent

        self.map_scene = QGraphicsScene(self)
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.setScene(self.map_scene)
        self.object_graphically_moved_signal.connect(self._handle_internal_object_move_for_unsaved_changes)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._grid_lines: List[QGraphicsLineItem] = []
        self._map_object_items: Dict[int, MapObjectItem] = {}
        self._hover_preview_item: Optional[QGraphicsPixmapItem] = None

        self.current_tool = "place"
        self.middle_mouse_panning = False
        self.last_pan_point = QPointF()
        self._is_dragging_map_object = False
        self._drag_start_data_coords: Optional[Tuple[int, int]] = None

        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(30)
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)
        
        self.load_map_from_state()
        logger.debug("MapViewWidget initialized.") # MOVED Log after load_map_from_state

    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        logger.debug(f"MapView: Received object_graphically_moved_signal for object data ID: {id(moved_object_data_ref)}. Emitting map_content_changed.")
        self.map_content_changed.emit()

    def clear_scene(self):
        logger.debug("MapViewWidget: Clearing scene...")
        self.map_scene.blockSignals(True)
        items_to_remove = list(self.map_scene.items())
        for item in items_to_remove:
            if item.scene() == self.map_scene: self.map_scene.removeItem(item)
        self.map_scene.blockSignals(False)
        self._grid_lines.clear()
        self._map_object_items.clear()
        if self._hover_preview_item: # Ensure hover item is also cleared from scene if it exists
            if self._hover_preview_item.scene():
                self.map_scene.removeItem(self._hover_preview_item)
            self._hover_preview_item = None
        self.update()
        logger.debug("MapViewWidget: Scene cleared.")

    def load_map_from_state(self):
        logger.debug("MapViewWidget: Loading map from editor_state...")
        self.clear_scene()
        scene_w = float(self.editor_state.get_map_pixel_width())
        scene_h = float(self.editor_state.get_map_pixel_height())
        self.map_scene.setSceneRect(QRectF(0, 0, max(1.0, scene_w), max(1.0, scene_h)))
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.update_background_color()
        self.resetTransform()
        current_transform = QTransform()
        current_transform.translate(float(self.editor_state.camera_offset_x * -1), float(self.editor_state.camera_offset_y * -1))
        current_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(current_transform)
        self.update_grid_visibility()
        self.draw_placed_objects()
        logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}, Zoom: {self.editor_state.zoom_level:.2f}, Offset: ({self.editor_state.camera_offset_x:.1f}, {self.editor_state.camera_offset_y:.1f})")
        self.viewport().update()

    def update_background_color(self):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene: self.map_scene.removeItem(line)
        self._grid_lines.clear()
        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.viewport().update(); return
        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0); pen.setCosmetic(True)
        gs = self.editor_state.grid_size; scene_rect = self.map_scene.sceneRect()
        map_w_px, map_h_px = scene_rect.width(), scene_rect.height()
        start_x, start_y = scene_rect.left(), scene_rect.top()
        for x_val in range(int(start_x), int(start_x + map_w_px) + gs, gs): # Adjusted range end
            x_coord = float(x_val)
            if x_coord > start_x + map_w_px + 1e-6 : continue
            line = self.map_scene.addLine(x_coord, start_y, x_coord, start_y + map_h_px, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        for y_val in range(int(start_y), int(start_y + map_h_px) + gs, gs): # Adjusted range end
            y_coord = float(y_val)
            if y_coord > start_y + map_h_px + 1e-6 : continue
            line = self.map_scene.addLine(start_x, y_coord, start_x + map_w_px, y_coord, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        self.viewport().update()

    def update_grid_visibility(self):
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible: return
        if not is_visible and self._grid_lines:
            for line in self._grid_lines: line.setVisible(False)
        elif is_visible : self.draw_grid()
        self.viewport().update()

    def draw_placed_objects(self):
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        items_to_remove_ids = [item_id for item_id in self._map_object_items if item_id not in current_data_ids]
        for item_id in items_to_remove_ids:
            if self._map_object_items[item_id].scene() == self.map_scene:
                self.map_scene.removeItem(self._map_object_items[item_id])
            del self._map_object_items[item_id]
        for obj_data in self.editor_state.placed_objects:
            item_data_id = id(obj_data)
            asset_key = str(obj_data.get("asset_editor_key",""))
            asset_info_from_palette = self.editor_state.assets_palette.get(asset_key)
            if not asset_info_from_palette: logger.warning(f"DrawPlaced: Asset info for key '{asset_key}' not found in palette state."); continue
            original_w, original_h = asset_info_from_palette.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE))
            pixmap_to_draw = get_asset_pixmap(asset_key, asset_info_from_palette, QSize(original_w, original_h), obj_data.get("override_color"))
            if not pixmap_to_draw or pixmap_to_draw.isNull():
                logger.warning(f"DrawPlaced: Pixmap for asset '{asset_key}' is null. Object not drawn/updated."); continue
            world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
            if item_data_id in self._map_object_items:
                map_obj_item = self._map_object_items[item_data_id]
                if map_obj_item.pixmap().cacheKey() != pixmap_to_draw.cacheKey(): map_obj_item.setPixmap(pixmap_to_draw)
                if map_obj_item.pos() != QPointF(world_x, world_y): map_obj_item.setPos(QPointF(world_x, world_y))
                map_obj_item.editor_key = asset_key
                map_obj_item.game_type_id = str(obj_data.get("game_type_id"))
                map_obj_item.map_object_data_ref = obj_data
            else:
                map_obj_item = MapObjectItem(asset_key, str(obj_data.get("game_type_id")), pixmap_to_draw, int(world_x), int(world_y), obj_data)
                self.map_scene.addItem(map_obj_item)
                self._map_object_items[item_data_id] = map_obj_item
        self.viewport().update()

    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
        return self.mapToScene(screen_pos_qpoint.toPoint())
    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint)
        gs = self.editor_state.grid_size
        if gs <= 0: return (int(scene_pos.x()), int(scene_pos.y()))
        grid_tx = int(scene_pos.x() // gs) # Integer division for grid cells
        grid_ty = int(scene_pos.y() // gs)
        return grid_tx, grid_ty
    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]:
        gs = self.editor_state.grid_size
        if gs <= 0: return world_x, world_y
        return float(round(world_x / gs) * gs), float(round(world_y / gs) * gs)
    def _emit_zoom_update_status(self):
        viewport_center_point = self.viewport().rect().center()
        scene_center_point = self.mapToScene(viewport_center_point)
        grid_coords = self.screen_to_grid_coords(QPointF(float(viewport_center_point.x()), float(viewport_center_point.y())))
        self.mouse_moved_on_map.emit((scene_center_point.x(), scene_center_point.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))
    @Slot()
    def zoom_in(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT)
    @Slot()
    def zoom_out(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT)
    @Slot()
    def reset_zoom(self):
        view_center_scene = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.editor_state.camera_offset_x = 0.0 # Reset camera offset logic
        self.editor_state.camera_offset_y = 0.0
        self.editor_state.zoom_level = 1.0
        self.translate(0,0) # Ensure translation is reset if camera_offset is truly 0,0
        self.centerOn(view_center_scene) # Re-center
        # After centerOn, scrollbars might change, so update camera_offset based on them
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
        self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
        self._emit_zoom_update_status()
    def scale_view(self, factor: float):
        current_zoom = self.transform().m11() ; new_zoom = current_zoom * factor
        if abs(current_zoom) < 1e-5 and factor < 1.0: return
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL))
        actual_factor_to_apply = clamped_zoom / current_zoom if abs(current_zoom) > 1e-5 else (clamped_zoom if clamped_zoom > ED_CONFIG.MIN_ZOOM_LEVEL else 1.0)
        if abs(actual_factor_to_apply - 1.0) > 0.0001:
            self.scale(actual_factor_to_apply, actual_factor_to_apply)
            self.editor_state.zoom_level = self.transform().m11()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self._emit_zoom_update_status()
    def pan_view_by_scrollbars(self, dx_pixels: int, dy_pixels: int):
        h_bar = self.horizontalScrollBar(); v_bar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() + dx_pixels); v_bar.setValue(v_bar.value() + dy_pixels)
        self.editor_state.camera_offset_x = float(h_bar.value()); self.editor_state.camera_offset_y = float(v_bar.value())
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key(); modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom_in(); event.accept(); return
            elif key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            elif key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return
        pan_pixel_step = int(ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND / 60.0); dx_pixels, dy_pixels = 0, 0
        if key == Qt.Key.Key_A: dx_pixels = -pan_pixel_step
        elif key == Qt.Key.Key_D: dx_pixels = pan_pixel_step
        elif key == Qt.Key.Key_W: dy_pixels = -pan_pixel_step
        elif key == Qt.Key.Key_S and not (modifiers & Qt.KeyboardModifier.ControlModifier): dy_pixels = pan_pixel_step
        if dx_pixels != 0 or dy_pixels != 0: self.pan_view_by_scrollbars(dx_pixels, dy_pixels); event.accept(); return
        if key == Qt.Key.Key_Delete: self.delete_selected_map_objects(); event.accept(); return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False 
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_tx, grid_ty = self.screen_to_grid_coords(event.position())
        item_under_mouse = self.itemAt(event.position().toPoint())
        
        logger.debug(f"MapView: mousePressEvent - Button: {event.button()}, Tool: '{self.current_tool}', "
                     f"Selected Asset: '{self.editor_state.selected_asset_editor_key}', "
                     f"Item under mouse: {type(item_under_mouse).__name__ if item_under_mouse else 'None'}, "
                     f"Grid Coords: ({grid_tx},{grid_ty})")

        if event.button() == Qt.MouseButton.LeftButton:
            if item_under_mouse and isinstance(item_under_mouse, MapObjectItem):
                logger.debug("MapView: Left click on MapObjectItem. Starting drag possibility.")
                self._is_dragging_map_object = True
                self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y'])
                super().mousePressEvent(event) 
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                logger.debug(f"MapView: Left click with 'place' tool. Calling _perform_place_action for grid ({grid_tx},{grid_ty}).")
                self._perform_place_action(grid_tx, grid_ty, is_first_action=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                logger.debug(f"MapView: Left click with 'color_pick' tool. Calling _perform_color_tile_action for grid ({grid_tx},{grid_ty}).")
                self._perform_color_tile_action(grid_tx, grid_ty, is_first_action=True)
            else: 
                logger.debug("MapView: Left click, no specific tool action. Setting RubberBandDrag.")
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event) 
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_under_mouse):
                logger.debug(f"MapView: Right click with 'erase' tool or empty 'place'. Calling _perform_erase_action for grid ({grid_tx},{grid_ty}).")
                self._perform_erase_action(grid_tx, grid_ty, is_first_action=True)
            else:
                logger.debug("MapView: Right click, no specific erase action. Passing to super.")
                super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.MiddleButton:
            logger.debug("MapView: Middle mouse button pressed. Starting ScrollHandDrag.")
            self.middle_mouse_panning = True; self.last_pan_point = event.globalPosition()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept(); return
        if not event.isAccepted():
            logger.debug("MapView: mousePressEvent not accepted by custom logic. Passing to super().")
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint()); grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))
        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key
            asset_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_data and "q_pixmap_cursor" in asset_data:
                pixmap = asset_data["q_pixmap_cursor"]
                if pixmap and not pixmap.isNull():
                    if not self._hover_preview_item: self._hover_preview_item = QGraphicsPixmapItem(); self._hover_preview_item.setZValue(100); self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): self._hover_preview_item.setPixmap(pixmap)
                    self._hover_preview_item.setPos(QPointF(world_x_snapped, world_y_snapped)); self._hover_preview_item.setVisible(True)
                elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
            elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object: super().mouseMoveEvent(event)
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key: self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_x, grid_y, continuous=True)
            elif self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: super().mouseMoveEvent(event)
        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key): self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point; self.last_pan_point = event.globalPosition()
            self.pan_view_by_scrollbars(int(-delta.x()), int(-delta.y())); event.accept(); return
        self._check_edge_scroll(event.position())
        if not event.isAccepted(): super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False
            item_dragged: Optional[MapObjectItem] = None
            if self.map_scene.selectedItems() and isinstance(self.map_scene.selectedItems()[0], MapObjectItem): item_dragged = self.map_scene.selectedItems()[0] # type: ignore
            if item_dragged and self._drag_start_data_coords:
                final_data_x = item_dragged.map_object_data_ref['world_x']; final_data_y = item_dragged.map_object_data_ref['world_y']
                if self._drag_start_data_coords[0] != final_data_x or self._drag_start_data_coords[1] != final_data_y:
                    logger.debug(f"Object drag completed. Pushing undo for move from {self._drag_start_data_coords} to ({final_data_x},{final_data_y}).")
                    editor_history.push_undo_state(self.editor_state); self.map_content_changed.emit()
            self._drag_start_data_coords = None
        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False; self.setDragMode(QGraphicsView.DragMode.NoDrag); self.unsetCursor()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            event.accept(); return
        self.editor_state.last_painted_tile_coords = None; self.editor_state.last_erased_tile_coords = None; self.editor_state.last_colored_tile_coords = None
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)
    def enterEvent(self, event: QFocusEvent):
        if not self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start()
        super().enterEvent(event)
    def leaveEvent(self, event: QFocusEvent):
        if self.edge_scroll_timer.isActive(): self.edge_scroll_timer.stop()
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        super().leaveEvent(event)
    def _check_edge_scroll(self, mouse_pos_viewport: QPointF):
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0; zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS; view_rect = self.viewport().rect()
        if mouse_pos_viewport.x() < zone: self._edge_scroll_dx = -1
        elif mouse_pos_viewport.x() > view_rect.width() - zone: self._edge_scroll_dx = 1
        if mouse_pos_viewport.y() < zone: self._edge_scroll_dy = -1
        elif mouse_pos_viewport.y() > view_rect.height() - zone: self._edge_scroll_dy = 1
        should_be_active = (self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0)
        if should_be_active and not self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start()
        elif not should_be_active and self.edge_scroll_timer.isActive(): self.edge_scroll_timer.stop()
    @Slot()
    def perform_edge_scroll(self):
        if self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0:
            amount_pixels = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0)
            self.pan_view_by_scrollbars(int(self._edge_scroll_dx * amount_pixels), int(self._edge_scroll_dy * amount_pixels))

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords: return
        asset_key = self.editor_state.selected_asset_editor_key 
        logger.debug(f"MapView (_perform_place_action): Palette AssetKey='{asset_key}', Grid=({grid_x},{grid_y}), FirstAction={is_first_action}, Continuous={continuous}")

        if not asset_key: 
            logger.warning("MapView (_perform_place_action): No asset_key selected from palette. Cannot place.")
            return
        
        asset_data_from_palette = self.editor_state.assets_palette.get(str(asset_key))
        if not asset_data_from_palette:
            logger.error(f"MapView (_perform_place_action): Asset data for palette key '{asset_key}' not found in editor_state.assets_palette. Cannot place.")
            return
        
        # --- CORRECTED LOGIC for actual_asset_key_to_place ---
        places_asset_key_value = asset_data_from_palette.get("places_asset_key") 
        if places_asset_key_value and isinstance(places_asset_key_value, str) and places_asset_key_value.strip():
            actual_asset_key_to_place = places_asset_key_value.strip()
        else:
            actual_asset_key_to_place = asset_key
        # --- END CORRECTED LOGIC ---
        
        logger.debug(f"MapView (_perform_place_action): Resolved actual_asset_key_to_place: '{actual_asset_key_to_place}' (derived from palette key '{asset_key}')")

        target_asset_definition_for_placement = self.editor_state.assets_palette.get(str(actual_asset_key_to_place))
        if not target_asset_definition_for_placement:
            logger.error(f"MapView (_perform_place_action): Target asset definition for resolved key '{actual_asset_key_to_place}' not found in editor_state.assets_palette. Cannot place.")
            return
        
        made_change_in_stroke = False
        if is_first_action: 
            logger.debug("MapView (_perform_place_action): First action in stroke, pushing undo state.")
            editor_history.push_undo_state(self.editor_state)

        if asset_data_from_palette.get("places_asset_key") and asset_data_from_palette.get("icon_type") == "2x2_placer":
            logger.debug("MapView (_perform_place_action): Using 2x2 placer tool.")
            for r_off in range(2):
                for c_off in range(2):
                    if self._place_single_object_on_map(str(actual_asset_key_to_place), target_asset_definition_for_placement, grid_x + c_off, grid_y + r_off):
                        made_change_in_stroke = True
        else: 
            if self._place_single_object_on_map(str(actual_asset_key_to_place), target_asset_definition_for_placement, grid_x, grid_y):
                made_change_in_stroke = True
        
        if made_change_in_stroke:
            logger.debug("MapView (_perform_place_action): Change made, emitting map_content_changed.")
            self.map_content_changed.emit()
        self.editor_state.last_painted_tile_coords = (grid_x, grid_y)

    def _place_single_object_on_map(self, asset_to_place_key: str, asset_definition_for_placement: Dict, grid_x: int, grid_y: int) -> bool:
        world_x_float = float(grid_x * self.editor_state.grid_size)
        world_y_float = float(grid_y * self.editor_state.grid_size)
        game_id = asset_definition_for_placement.get("game_type_id", "unknown_game_id")
        is_spawn_type = asset_definition_for_placement.get("category") == "spawn"

        logger.debug(f"MapView (_place_single_object): Attempting to place '{asset_to_place_key}' (GameID: {game_id}) at grid ({grid_x},{grid_y}), world ({world_x_float},{world_y_float}). IsSpawn: {is_spawn_type}")

        if not is_spawn_type:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == int(world_x_float) and \
                   obj.get("world_y") == int(world_y_float) and \
                   obj.get("asset_editor_key") == asset_to_place_key: 
                    logger.debug(f"MapView (_place_single_object): Identical object '{asset_to_place_key}' already at ({grid_x},{grid_y}). Placement skipped.")
                    return False 

        new_object_map_data: Dict[str, Any] = {
            "asset_editor_key": asset_to_place_key, "world_x": int(world_x_float), "world_y": int(world_y_float), 
            "game_type_id": game_id, "properties": {}
        }
        if asset_definition_for_placement.get("colorable") and self.editor_state.current_tile_paint_color:
            new_object_map_data["override_color"] = self.editor_state.current_tile_paint_color
        if game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            new_object_map_data["properties"] = {k: v_def["default"] for k, v_def in ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_id].items()}
        
        if is_spawn_type:
            indices_to_remove = [i for i, obj in enumerate(self.editor_state.placed_objects) if obj.get("game_type_id") == game_id]
            if indices_to_remove: logger.debug(f"MapView (_place_single_object): Removing {len(indices_to_remove)} existing spawn(s) of type '{game_id}'.")
            for i in sorted(indices_to_remove, reverse=True):
                removed_obj_data = self.editor_state.placed_objects.pop(i)
                item_id_removed = id(removed_obj_data)
                if item_id_removed in self._map_object_items:
                    if self._map_object_items[item_id_removed].scene(): self.map_scene.removeItem(self._map_object_items[item_id_removed])
                    del self._map_object_items[item_id_removed]

        self.editor_state.placed_objects.append(new_object_map_data)
        logger.debug(f"MapView (_place_single_object): Added object data to editor_state.placed_objects. New count: {len(self.editor_state.placed_objects)}")
        
        original_w, original_h = asset_definition_for_placement.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
        item_pixmap = get_asset_pixmap(asset_to_place_key, asset_definition_for_placement, QSize(original_w, original_h), new_object_map_data.get("override_color"))

        if not item_pixmap or item_pixmap.isNull():
            logger.error(f"MapView (_place_single_object): FAILED to get valid pixmap for MapObjectItem '{asset_to_place_key}'. Pixmap is null. Cannot create scene item.")
            if new_object_map_data in self.editor_state.placed_objects: self.editor_state.placed_objects.remove(new_object_map_data)
            return False

        logger.debug(f"MapView (_place_single_object): Got valid pixmap for MapObjectItem (Size: {item_pixmap.size()}). Creating and adding item to scene.")
        map_object_scene_item = MapObjectItem(asset_to_place_key, game_id, item_pixmap, int(world_x_float), int(world_y_float), new_object_map_data)
        self.map_scene.addItem(map_object_scene_item)
        self._map_object_items[id(new_object_map_data)] = map_object_scene_item
        
        logger.info(f"MapView: Placed '{asset_to_place_key}' at grid ({grid_x},{grid_y}).")
        return True

    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size); world_y_snapped = float(grid_y * self.editor_state.grid_size)
        item_data_index_to_remove: Optional[int] = None
        for i, obj_data in reversed(list(enumerate(self.editor_state.placed_objects))):
            if obj_data.get("world_x") == int(world_x_snapped) and obj_data.get("world_y") == int(world_y_snapped):
                item_data_index_to_remove = i; break
        if item_data_index_to_remove is not None:
            if is_first_action: editor_history.push_undo_state(self.editor_state)
            obj_data_to_remove = self.editor_state.placed_objects.pop(item_data_index_to_remove)
            item_id = id(obj_data_to_remove)
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene(): self.map_scene.removeItem(self._map_object_items[item_id])
                del self._map_object_items[item_id]
            self.map_content_changed.emit(); self.editor_state.last_erased_tile_coords = (grid_x, grid_y)
            logger.info(f"MapView: Erased object at grid ({grid_x},{grid_y}).")
    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if not self.editor_state.current_tile_paint_color: return
        if continuous and (grid_x, grid_y) == self.editor_state.last_colored_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size); world_y_snapped = float(grid_y * self.editor_state.grid_size)
        colored_something_this_call = False
        for obj_data in reversed(self.editor_state.placed_objects):
            if obj_data.get("world_x") == int(world_x_snapped) and obj_data.get("world_y") == int(world_y_snapped):
                asset_key = str(obj_data.get("asset_editor_key"))
                asset_info = self.editor_state.assets_palette.get(asset_key)
                if asset_info and asset_info.get("colorable"):
                    new_color_tuple = self.editor_state.current_tile_paint_color
                    if obj_data.get("override_color") != new_color_tuple:
                        if is_first_action: editor_history.push_undo_state(self.editor_state)
                        obj_data["override_color"] = new_color_tuple
                        item_id = id(obj_data)
                        if item_id in self._map_object_items:
                            self._map_object_items[item_id].update_visuals(new_color=QColor(*new_color_tuple), editor_state=self.editor_state)
                        colored_something_this_call = True; break 
        if colored_something_this_call:
            self.map_content_changed.emit(); self.editor_state.last_colored_tile_coords = (grid_x, grid_y)
            logger.info(f"MapView: Colored object at grid ({grid_x},{grid_y}) to {self.editor_state.current_tile_paint_color}.")
    def delete_selected_map_objects(self):
        selected_items = self.map_scene.selectedItems()
        if not selected_items: return
        logger.debug(f"MapView: delete_selected_map_objects - {len(selected_items)} items selected.")
        editor_history.push_undo_state(self.editor_state)
        data_refs_to_remove = [item.map_object_data_ref for item in selected_items if isinstance(item, MapObjectItem)]
        self.editor_state.placed_objects = [obj for obj in self.editor_state.placed_objects if obj not in data_refs_to_remove]
        for item_data_ref in data_refs_to_remove:
            item_id = id(item_data_ref)
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene(): self.map_scene.removeItem(self._map_object_items.pop(item_id))
        self.map_scene.clearSelection()
        self.map_content_changed.emit(); self.map_object_selected_for_properties.emit(None)
        if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).")

    @Slot(str)
    def on_asset_selected(self, asset_editor_key: Optional[str]):
        logger.debug(f"MapView: on_asset_selected received key: '{asset_editor_key}'")
        self.editor_state.selected_asset_editor_key = asset_editor_key
        self.editor_state.current_tile_paint_color = None 
        self.current_tool = "place" 
        asset_name_display = "None"
        if asset_editor_key:
            asset_data = self.editor_state.assets_palette.get(str(asset_editor_key))
            asset_name_display = asset_data.get("name_in_palette", str(asset_editor_key)) if asset_data else str(asset_editor_key)
            if self.underMouse():
                 QTimer.singleShot(0, lambda: self.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, self.mapFromGlobal(self.cursor().pos()), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)))
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        logger.debug(f"MapView: current_tool set to '{self.current_tool}', selected_asset_key in state: '{self.editor_state.selected_asset_editor_key}'")

    @Slot(str)
    def on_tool_selected(self, tool_key: str):
        logger.debug(f"MapView: on_tool_selected received tool_key: '{tool_key}'")
        self.editor_state.selected_asset_editor_key = None 
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        tool_data = self.editor_state.assets_palette.get(str(tool_key))
        tool_name_for_status = tool_data.get("name_in_palette", tool_key.replace("tool_", "").replace("_", " ").title()) if tool_data else tool_key
        if tool_key == "tool_eraser": self.current_tool = "erase"; self.editor_state.current_tile_paint_color = None
        elif tool_key == "tool_tile_color_picker":
            self.current_tool = "color_pick"
            if self.parent_window: 
                initial_c = self.editor_state.current_tile_paint_color or ED_CONFIG.C.BLUE 
                current_q_color = QColor(*initial_c)
                new_q_color = QColorDialog.getColor(current_q_color, self.parent_window, "Select Tile Paint Color")
                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None
                status_msg_color = f"Paint color: {self.editor_state.current_tile_paint_color}" if self.editor_state.current_tile_paint_color else "Paint color selection cancelled."
                if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(status_msg_color)
        elif tool_key == "platform_wall_gray_2x2_placer": # Handle specific placer tool
            self.current_tool = "place" # It's a place action
            self.editor_state.selected_asset_editor_key = tool_key # Select the tool itself as the 'asset'
            logger.debug(f"MapView: 2x2 Placer tool selected. Tool mode: '{self.current_tool}', Selected Key: '{tool_key}'")
        else: 
            self.current_tool = "select"; self.editor_state.current_tile_paint_color = None
        logger.debug(f"MapView: current_tool set to '{self.current_tool}'")

    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: Dict[str, Any]):
        item_id = id(changed_object_data_ref)
        logger.debug(f"MapView: on_object_properties_changed for data_ref ID {item_id}")
        if item_id in self._map_object_items:
            map_item = self._map_object_items[item_id]
            new_color_tuple = changed_object_data_ref.get("override_color")
            map_item.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
            logger.debug(f"MapView: Visuals updated for item {map_item.editor_key}")
        else: logger.warning(f"MapView: on_object_properties_changed - MapObjectItem for data_ref ID {item_id} not found.")
        self.map_content_changed.emit()

    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.map_scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], MapObjectItem):
            logger.debug(f"MapView: Scene selection changed. Selected 1 MapObjectItem: {selected_items[0].editor_key}")
            self.map_object_selected_for_properties.emit(selected_items[0].map_object_data_ref)
        else:
            logger.debug(f"MapView: Scene selection changed. Selection count: {len(selected_items)}. Emitting None for properties.")
            self.map_object_selected_for_properties.emit(None)