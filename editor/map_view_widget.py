# map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
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
    logger_mv = logging.getLogger(__name__)
    logger_mv.critical("map_view_widget.py: Failed to import get_asset_pixmap from editor_assets.")
    def get_asset_pixmap(asset_editor_key: str, asset_data_entry: Dict[str, Any],
                         target_size: QSize, override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
        logger_mv.error(f"Dummy get_asset_pixmap for {asset_editor_key}")
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
                        self.scene().parent().object_graphically_moved_signal.emit(self.map_object_data_ref)
            
            # Return the snapped position if it differs from the proposed value
            if abs(new_pos.x() - snapped_x) > 0.01 or abs(new_pos.y() - snapped_y) > 0.01:
                return QPointF(float(snapped_x), float(snapped_y))
            return new_pos # Already snapped or no change
        return super().itemChange(change, value)

    def update_visuals(self, new_pixmap: Optional[QPixmap] = None, new_color: Optional[QColor] = None, editor_state: Optional[EditorState] = None):
        # ... (implementation as before) ...
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

    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        self.map_content_changed.emit()

    def clear_scene(self):
        self.map_scene.blockSignals(True)
        items_to_remove = list(self.map_scene.items())
        for item in items_to_remove: self.map_scene.removeItem(item)
        self.map_scene.blockSignals(False)
        self._grid_lines.clear()
        self._map_object_items.clear()
        self._hover_preview_item = None
        self.update()

    def load_map_from_state(self):
        # logger.debug("MapViewWidget: Loading map from state...")
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
        # logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}, Zoom: {self.editor_state.zoom_level}, Offset: ({self.editor_state.camera_offset_x}, {self.editor_state.camera_offset_y})")


    def update_background_color(self):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))

    def draw_grid(self):
        # ... (implementation as before, ensure gs is valid) ...
        for line in self._grid_lines:
            if line.scene() == self.map_scene: self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.viewport().update(); return

        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0)
        pen.setCosmetic(True)
        gs = self.editor_state.grid_size
        scene_rect = self.map_scene.sceneRect()
        map_w_px, map_h_px = scene_rect.width(), scene_rect.height()
        start_x, start_y = scene_rect.left(), scene_rect.top()

        for x_val in range(int(start_x), int(start_x + map_w_px) + 1, gs):
            x_coord = float(x_val)
            if x_coord > start_x + map_w_px + 1e-6 : continue # Prevent drawing outside due to float
            line = self.map_scene.addLine(x_coord, start_y, x_coord, start_y + map_h_px, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        for y_val in range(int(start_y), int(start_y + map_h_px) + 1, gs):
            y_coord = float(y_val)
            if y_coord > start_y + map_h_px + 1e-6 : continue
            line = self.map_scene.addLine(start_x, y_coord, start_x + map_w_px, y_coord, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        self.viewport().update()


    def update_grid_visibility(self):
        # ... (implementation as before) ...
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible: return
        if not is_visible and self._grid_lines:
            for line in self._grid_lines: line.setVisible(False)
        elif is_visible :
            self.draw_grid()
        self.viewport().update()

    def draw_placed_objects(self):
        # ... (implementation as before, ensure get_asset_pixmap is robust) ...
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        items_to_remove_ids = [item_id for item_id in self._map_object_items if item_id not in current_data_ids]
        for item_id in items_to_remove_ids:
            if self._map_object_items[item_id].scene() == self.map_scene: # Check if still in scene
                self.map_scene.removeItem(self._map_object_items[item_id])
            del self._map_object_items[item_id]

        for obj_data in self.editor_state.placed_objects:
            item_data_id = id(obj_data)
            asset_key = str(obj_data.get("asset_editor_key",""))
            asset_info = self.editor_state.assets_palette.get(asset_key)
            if not asset_info: logger.warning(f"Asset info for key '{asset_key}' not found."); continue

            original_w, original_h = asset_info.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE))
            pixmap_to_draw = get_asset_pixmap(asset_key, asset_info, QSize(original_w, original_h), obj_data.get("override_color"))

            if not pixmap_to_draw or pixmap_to_draw.isNull():
                logger.warning(f"Pixmap for asset '{asset_key}' is null. Object not drawn/updated."); continue

            world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
            if item_data_id in self._map_object_items:
                map_obj_item = self._map_object_items[item_data_id]
                if map_obj_item.pixmap().cacheKey() != pixmap_to_draw.cacheKey(): map_obj_item.setPixmap(pixmap_to_draw)
                if map_obj_item.pos() != QPointF(world_x, world_y): map_obj_item.setPos(QPointF(world_x, world_y))
                map_obj_item.editor_key = asset_key
                map_obj_item.game_type_id = str(obj_data.get("game_type_id"))
            else:
                map_obj_item = MapObjectItem(
                    asset_key, str(obj_data.get("game_type_id")), pixmap_to_draw,
                    int(world_x), int(world_y), obj_data # MapObjectItem expects int for world_x, world_y in constructor
                )
                self.map_scene.addItem(map_obj_item)
                self._map_object_items[item_data_id] = map_obj_item
        self.viewport().update()


    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
        # screen_pos_qpoint is QPointF from event.position()
        return self.mapToScene(screen_pos_qpoint.toPoint())

    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint)
        gs = self.editor_state.grid_size
        if gs <= 0: return (int(scene_pos.x()), int(scene_pos.y()))
        return int(scene_pos.x() // gs), int(scene_pos.y() // gs)

    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]:
        gs = self.editor_state.grid_size
        if gs <= 0: return world_x, world_y
        return float(round(world_x / gs) * gs), float(round(world_y / gs) * gs)

    def _emit_zoom_update_status(self):
        viewport_center_point = self.viewport().rect().center()
        scene_center_point = self.mapToScene(viewport_center_point)
        # mapFromGlobal might be needed if cursor isn't over view during programmatic zoom
        # For now, assume viewport center is sufficient.
        grid_coords = self.screen_to_grid_coords(QPointF(float(viewport_center_point.x()), float(viewport_center_point.y())))
        self.mouse_moved_on_map.emit((scene_center_point.x(), scene_center_point.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))

    @Slot()
    def zoom_in(self):
        self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT)

    @Slot()
    def zoom_out(self):
        self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT)

    @Slot()
    def reset_zoom(self):
        current_transform = self.transform()
        # Calculate view center in scene coords before reset
        view_center_scene = self.mapToScene(self.viewport().rect().center())

        self.resetTransform() # Resets scale to 1, and translation to (0,0) relative to scene origin

        # Re-apply camera offset (top-left of scene to be visible)
        # Then, ensure the point that was at the center of the view remains at the center
        self.translate(self.editor_state.camera_offset_x * -1, self.editor_state.camera_offset_y * -1)
        self.editor_state.zoom_level = 1.0

        # After reset and translate, center on the old view_center_scene
        self.centerOn(view_center_scene)
        # Update camera_offset based on new scrollbar positions after centerOn
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
        self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())

        self._emit_zoom_update_status()

    def scale_view(self, factor: float):
        current_zoom = self.transform().m11()
        new_zoom = current_zoom * factor
        if abs(current_zoom) < 1e-5 and factor < 1.0: return # Avoid extreme zoom out
        
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL))
        actual_factor_to_apply = clamped_zoom / current_zoom if abs(current_zoom) > 1e-5 else (clamped_zoom if clamped_zoom > ED_CONFIG.MIN_ZOOM_LEVEL else 1.0)

        if abs(actual_factor_to_apply - 1.0) > 0.0001:
            self.scale(actual_factor_to_apply, actual_factor_to_apply)
            self.editor_state.zoom_level = self.transform().m11()
            # Update camera_offset based on new scrollbar positions after scale
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
            self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self._emit_zoom_update_status()

    def pan_view_by_scrollbars(self, dx_pixels: int, dy_pixels: int):
        """Pans the view by adjusting scrollbar values directly (dx/dy in screen pixels)."""
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() + dx_pixels)
        v_bar.setValue(v_bar.value() + dy_pixels)
        self.editor_state.camera_offset_x = float(h_bar.value())
        self.editor_state.camera_offset_y = float(v_bar.value())

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom_in(); event.accept(); return
            elif key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            elif key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return

        # For WASD panning, pan by a fixed amount of screen pixels for consistent feel
        pan_pixel_step = int(ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND / 60.0) # Treat as screen pixels per "frame"
        dx_pixels, dy_pixels = 0, 0
        if key == Qt.Key.Key_A: dx_pixels = -pan_pixel_step
        elif key == Qt.Key.Key_D: dx_pixels = pan_pixel_step
        elif key == Qt.Key.Key_W: dy_pixels = -pan_pixel_step
        elif key == Qt.Key.Key_S and not (modifiers & Qt.KeyboardModifier.ControlModifier): dy_pixels = pan_pixel_step

        if dx_pixels != 0 or dy_pixels != 0:
            self.pan_view_by_scrollbars(dx_pixels, dy_pixels); event.accept(); return
        
        if key == Qt.Key.Key_Delete: self.delete_selected_map_objects(); event.accept(); return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())
        item_under_mouse = self.itemAt(event.position().toPoint())

        if event.button() == Qt.MouseButton.LeftButton:
            if item_under_mouse and isinstance(item_under_mouse, MapObjectItem):
                self._is_dragging_map_object = True
                self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y'])
                super().mousePressEvent(event)
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y, is_first_action=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y, is_first_action=True)
            else:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_under_mouse):
                self._perform_erase_action(grid_x, grid_y, is_first_action=True)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True
            self.last_pan_point = event.globalPosition()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept(); return
        if not event.isAccepted(): super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))

        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key
            asset_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_data and "q_pixmap_cursor" in asset_data:
                pixmap = asset_data["q_pixmap_cursor"]
                if pixmap and not pixmap.isNull():
                    if not self._hover_preview_item:
                        self._hover_preview_item = QGraphicsPixmapItem(); self._hover_preview_item.setZValue(100); self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): self._hover_preview_item.setPixmap(pixmap)
                    self._hover_preview_item.setPos(QPointF(world_x_snapped, world_y_snapped)); self._hover_preview_item.setVisible(True)
                elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
            elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object: super().mouseMoveEvent(event)
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key: self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_x, grid_y, continuous=True)
        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key): self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point
            self.last_pan_point = event.globalPosition()
            self.pan_view_by_scrollbars(int(-delta.x()), int(-delta.y())); event.accept(); return
        
        self._check_edge_scroll(event.position())
        if not event.isAccepted(): super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        # Handle undo for drag after the drag is complete
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False
            item_dragged: Optional[MapObjectItem] = None
            # Find which item was being dragged (QGraphicsView doesn't easily tell us *which* item finished moving)
            # We rely on the item itself having updated its data_ref via itemChange.
            # We check if the *data* actually changed from the start of the drag.
            if self.map_scene.selectedItems() and isinstance(self.map_scene.selectedItems()[0], MapObjectItem):
                 item_dragged = self.map_scene.selectedItems()[0] # type: ignore

            if item_dragged and self._drag_start_data_coords:
                final_data_x = item_dragged.map_object_data_ref['world_x']
                final_data_y = item_dragged.map_object_data_ref['world_y']
                if self._drag_start_data_coords[0] != final_data_x or self._drag_start_data_coords[1] != final_data_y:
                    logger.debug(f"Object drag completed. Data changed from {self._drag_start_data_coords} to ({final_data_x},{final_data_y}). Pushing undo.")
                    editor_history.push_undo_state(self.editor_state)
                    self.map_content_changed.emit() # For unsaved changes flag etc.
            self._drag_start_data_coords = None


        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False; self.setDragMode(QGraphicsView.DragMode.NoDrag); self.unsetCursor()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
            self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            event.accept(); return

        self.editor_state.last_painted_tile_coords = None
        self.editor_state.last_erased_tile_coords = None
        self.editor_state.last_colored_tile_coords = None
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
        # ... (implementation as before) ...
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0
        zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS
        view_rect = self.viewport().rect()
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
            # Edge scroll is based on screen pixels for consistent feel
            self.pan_view_by_scrollbars(int(self._edge_scroll_dx * amount_pixels), int(self._edge_scroll_dy * amount_pixels))

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        # ... (implementation as before, ensure push_undo_state is called for is_first_action) ...
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords: return
        asset_key = self.editor_state.selected_asset_editor_key
        if not asset_key: return
        asset_data = self.editor_state.assets_palette.get(str(asset_key))
        if not asset_data: return
        actual_asset_key = asset_data.get("places_asset_key", asset_key)
        target_asset_data = self.editor_state.assets_palette.get(str(actual_asset_key))
        if not target_asset_data: return
        
        made_change_in_stroke = False
        if is_first_action: editor_history.push_undo_state(self.editor_state)

        if asset_data.get("places_asset_key") and asset_data.get("icon_type") == "2x2_placer":
            for r_off in range(2):
                for c_off in range(2):
                    if self._place_single_object_on_map(str(actual_asset_key), target_asset_data, grid_x + c_off, grid_y + r_off):
                        made_change_in_stroke = True
        else:
            if self._place_single_object_on_map(str(actual_asset_key), target_asset_data, grid_x, grid_y):
                made_change_in_stroke = True
        
        if made_change_in_stroke: self.map_content_changed.emit()
        self.editor_state.last_painted_tile_coords = (grid_x, grid_y)


    def _place_single_object_on_map(self, asset_editor_key: str, asset_data_for_placement: Dict, grid_x: int, grid_y: int) -> bool:
        # ... (implementation as before) ...
        world_x, world_y = float(grid_x * self.editor_state.grid_size), float(grid_y * self.editor_state.grid_size)
        game_id = asset_data_for_placement.get("game_type_id", "unknown_game_id") # Ensure game_id exists
        is_spawn = asset_data_for_placement.get("category") == "spawn"

        if not is_spawn:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == int(world_x) and obj.get("world_y") == int(world_y) and obj.get("game_type_id") == game_id:
                    return False

        temp_new_object_data: Dict[str, Any] = { # Ensure type for dict
            "asset_editor_key": asset_editor_key, "world_x": int(world_x), "world_y": int(world_y), "game_type_id": game_id, "properties": {}
        }
        if asset_data_for_placement.get("colorable") and self.editor_state.current_tile_paint_color:
            temp_new_object_data["override_color"] = self.editor_state.current_tile_paint_color
        if game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            temp_new_object_data["properties"] = {
                k: v["default"] for k, v in ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_id].items()
            }
        
        if is_spawn:
            indices_to_remove = [i for i, obj in enumerate(self.editor_state.placed_objects) if obj.get("game_type_id") == game_id]
            for i in sorted(indices_to_remove, reverse=True):
                item_id = id(self.editor_state.placed_objects.pop(i))
                if item_id in self._map_object_items: self.map_scene.removeItem(self._map_object_items.pop(item_id))

        self.editor_state.placed_objects.append(temp_new_object_data)
        
        original_w, original_h = asset_data_for_placement.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
        pixmap = get_asset_pixmap(asset_editor_key, asset_data_for_placement,
                                  QSize(original_w, original_h),
                                  temp_new_object_data.get("override_color"))

        if pixmap and not pixmap.isNull():
            map_obj_item = MapObjectItem(asset_editor_key, game_id, pixmap, int(world_x), int(world_y), temp_new_object_data)
            self.map_scene.addItem(map_obj_item)
            self._map_object_items[id(temp_new_object_data)] = map_obj_item
            # self.map_content_changed.emit() # Moved to _perform_place_action
            return True
        return False


    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        # ... (implementation as before, ensure push_undo_state for is_first_action) ...
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size)
        world_y_snapped = float(grid_y * self.editor_state.grid_size)
        
        item_data_index_to_remove: Optional[int] = None
        for i, obj_data in reversed(list(enumerate(self.editor_state.placed_objects))):
            if obj_data.get("world_x") == int(world_x_snapped) and obj_data.get("world_y") == int(world_y_snapped):
                item_data_index_to_remove = i; break
        
        if item_data_index_to_remove is not None:
            if is_first_action: editor_history.push_undo_state(self.editor_state)
            obj_data_to_remove = self.editor_state.placed_objects.pop(item_data_index_to_remove)
            item_id = id(obj_data_to_remove)
            if item_id in self._map_object_items:
                self.map_scene.removeItem(self._map_object_items.pop(item_id))
            self.map_content_changed.emit()
            self.editor_state.last_erased_tile_coords = (grid_x, grid_y)


    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        # ... (implementation as before, ensure push_undo_state for is_first_action) ...
        if not self.editor_state.current_tile_paint_color: return
        if continuous and (grid_x, grid_y) == self.editor_state.last_colored_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size)
        world_y_snapped = float(grid_y * self.editor_state.grid_size)
        
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
                        colored_something_this_call = True
                    break 
        if colored_something_this_call:
            self.map_content_changed.emit()
            self.editor_state.last_colored_tile_coords = (grid_x, grid_y)


    def delete_selected_map_objects(self):
        # ... (implementation as before) ...
        selected_items = self.map_scene.selectedItems()
        if not selected_items: return
        editor_history.push_undo_state(self.editor_state)
        data_refs_to_remove = [item.map_object_data_ref for item in selected_items if isinstance(item, MapObjectItem)]
        self.editor_state.placed_objects = [obj for obj in self.editor_state.placed_objects if obj not in data_refs_to_remove]
        for item_data_ref in data_refs_to_remove:
            item_id = id(item_data_ref)
            if item_id in self._map_object_items:
                self.map_scene.removeItem(self._map_object_items.pop(item_id))
        self.map_scene.clearSelection()
        self.map_content_changed.emit()
        self.map_object_selected_for_properties.emit(None)
        if hasattr(self.parent_window, 'show_status_message'):
             self.parent_window.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).")


    @Slot(str)
    def on_asset_selected(self, asset_editor_key: Optional[str]):
        # ... (implementation as before) ...
        self.editor_state.selected_asset_editor_key = asset_editor_key
        self.editor_state.current_tile_paint_color = None
        tool_name = "Place"
        asset_name_display = "None"
        if asset_editor_key:
            self.current_tool = "place"
            asset_data = self.editor_state.assets_palette.get(str(asset_editor_key))
            asset_name_display = asset_data.get("name_in_palette", str(asset_editor_key)) if asset_data else str(asset_editor_key)
            if self.underMouse():
                 QTimer.singleShot(0, lambda: self.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, self.mapFromGlobal(self.cursor().pos()), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)))
        else:
            self.current_tool = "select"
            if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if hasattr(self.parent_window, 'show_status_message'):
            self.parent_window.show_status_message(f"Tool: {tool_name}. Asset: {asset_name_display}")


    @Slot(str)
    def on_tool_selected(self, tool_key: str):
        # ... (implementation as before) ...
        self.editor_state.selected_asset_editor_key = None
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        tool_data = self.editor_state.assets_palette.get(str(tool_key))
        tool_name_for_status = tool_data.get("name_in_palette", tool_key.replace("tool_", "").replace("_", " ").title()) if tool_data else tool_key

        if tool_key == "tool_eraser": self.current_tool = "erase"; self.editor_state.current_tile_paint_color = None
        elif tool_key == "tool_tile_color_picker":
            self.current_tool = "color_pick"
            if self.parent_window:
                initial_c = self.editor_state.current_tile_paint_color or ED_CONFIG.C.BLUE # Fallback initial color
                current_q_color = QColor(*initial_c)
                new_q_color = QColorDialog.getColor(current_q_color, self.parent_window, "Select Tile Paint Color")
                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None
                status_msg = f"Paint color: {self.editor_state.current_tile_paint_color}" if self.editor_state.current_tile_paint_color else "Paint color selection cancelled."
                self.parent_window.show_status_message(status_msg)
        else: self.current_tool = "select"; self.editor_state.current_tile_paint_color = None
        
        if hasattr(self.parent_window, 'show_status_message'):
            self.parent_window.show_status_message(f"Tool: {tool_name_for_status}")


    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: Dict[str, Any]):
        # ... (implementation as before) ...
        item_id = id(changed_object_data_ref)
        if item_id in self._map_object_items:
            map_item = self._map_object_items[item_id]
            new_color_tuple = changed_object_data_ref.get("override_color")
            map_item.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
        self.map_content_changed.emit()


    @Slot()
    def on_scene_selection_changed(self):
        # ... (implementation as before) ...
        selected_items = self.map_scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], MapObjectItem):
            self.map_object_selected_for_properties.emit(selected_items[0].map_object_data_ref)
        else:
            self.map_object_selected_for_properties.emit(None) # Emit None for dict type hint compatibility