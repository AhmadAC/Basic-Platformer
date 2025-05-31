# editor/map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
Handles display, interaction, and dispatches actions to map_view_actions.
Version 2.2.3 (Fixed TypeError in keyPressEvent, respects lock on delete)
"""
import logging
import os
import math
from typing import Optional, Dict, Any, List, Tuple, cast

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsItem, QColorDialog, QWidget, QApplication
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QTransform, QImage,
    QWheelEvent, QMouseEvent, QKeyEvent, QFocusEvent, QCursor, QContextMenuEvent, QHoverEvent,
    QPainterPath
)
from PySide6.QtCore import Qt, Signal, Slot, QRectF, QPointF, QSizeF, QTimer

from editor import editor_config as ED_CONFIG
from editor.editor_state import EditorState
from editor import editor_history
from editor.editor_assets import get_asset_pixmap
from editor import editor_map_utils

from editor.map_object_items import StandardMapObjectItem
from editor.editor_custom_items import ( # Updated import
    BaseResizableMapItem, CustomImageMapItem, TriggerSquareMapItem, InvisibleWallMapItem,
    HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_LEFT, HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT
)

from editor import map_view_actions as MVActions

from editor.editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                             ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY,
                             ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN)


logger = logging.getLogger(__name__)


class MapViewWidget(QGraphicsView):
    mouse_moved_on_map = Signal(tuple) # (world_x, world_y, tile_x, tile_y, zoom)
    map_object_selected_for_properties = Signal(object) # Emits map_object_data_ref or None
    map_content_changed = Signal() # Emitted when objects are added, removed, or their core data changes
    object_graphically_moved_signal = Signal(dict)
    view_changed = Signal() # Emitted on pan or zoom for minimap update
    context_menu_requested_for_item = Signal(object, QPointF) # map_object_data_ref, global_pos

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent # Reference to EditorMainWindow

        self.map_scene = QGraphicsScene(self)
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setProperty("is_actively_transforming_item", False)
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.setScene(self.map_scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._grid_lines: List[QGraphicsLineItem] = []
        self._map_object_items: Dict[int, QGraphicsItem] = {} # Stores QGraphicsItem by id(map_object_data_ref)
        self._hover_preview_item: Optional[QGraphicsPixmapItem] = None

        self.middle_mouse_panning = False
        self.last_pan_point = QPointF()
        self._is_dragging_map_object = False
        self._drag_start_data_coords: Optional[Tuple[int, int]] = None

        self._is_resizing_item = False
        self._resizing_item_ref: Optional[BaseResizableMapItem] = None
        self._resize_start_mouse_pos_scene: Optional[QPointF] = None
        self._resize_start_item_rect_scene: Optional[QRectF] = None
        self._resize_handle_active: Optional[int] = None

        self._is_cropping_item = False
        self._cropping_item_ref: Optional[CustomImageMapItem] = None
        self._crop_handle_active: Optional[int] = None
        self._crop_start_mouse_pos_scene: Optional[QPointF] = None
        self._crop_start_item_data: Optional[Dict[str, Any]] = None # For original crop/pos/size data

        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(30) # ~33 FPS for scrolling
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)

        self._controller_has_focus = False
        self._controller_cursor_pos: Optional[Tuple[int, int]] = None # (grid_x, grid_y)
        self._controller_cursor_item: Optional[QGraphicsRectItem] = None
        
        self.load_map_from_state() # Initial load
        logger.debug("MapViewWidget initialized.")

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        MVActions.perform_place_action(self, grid_x, grid_y, continuous, is_first_action)

    def _place_single_object_on_map(self, asset_key_for_data: str, asset_definition: Dict, grid_x: int, grid_y: int, is_flipped_h: bool, rotation: int) -> bool:
        return MVActions.place_single_object_on_map(self, asset_key_for_data, asset_definition, grid_x, grid_y, is_flipped_h, rotation)

    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        MVActions.perform_erase_action(self, grid_x, grid_y, continuous, is_first_action)

    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        MVActions.perform_color_tile_action(self, grid_x, grid_y, continuous, is_first_action)

    def delete_selected_map_objects(self):
        MVActions.delete_selected_map_objects_action(self)
        
    def _select_object_at_controller_cursor(self): 
        if not self._controller_cursor_pos: return
        grid_x, grid_y = self._controller_cursor_pos
        world_x = float(grid_x * self.editor_state.grid_size)
        world_y = float(grid_y * self.editor_state.grid_size)
        cursor_rect_scene = QRectF(world_x, world_y, float(self.editor_state.grid_size), float(self.editor_state.grid_size))
        
        items_at_cursor = self.map_scene.items(cursor_rect_scene, Qt.ItemSelectionMode.IntersectsItemShape)

        found_item_to_select: Optional[QGraphicsItem] = None
        highest_z_found = -float('inf')
        for item in items_at_cursor:
            if isinstance(item, (StandardMapObjectItem, BaseResizableMapItem)): # BaseResizableMapItem covers CustomImage, Trigger, InvisibleWall
                if hasattr(item, 'map_object_data_ref') and not item.map_object_data_ref.get("editor_locked", False): # type: ignore
                    item_z = item.zValue()
                    if item_z > highest_z_found:
                        highest_z_found = item_z
                        found_item_to_select = item
        
        self.map_scene.clearSelection()
        if found_item_to_select:
            found_item_to_select.setSelected(True)
        else:
            self.map_object_selected_for_properties.emit(None)

    def _update_controller_cursor_visuals(self):
        if not self._controller_has_focus or self._controller_cursor_pos is None:
            if self._controller_cursor_item: self._controller_cursor_item.setVisible(False)
            return

        if not self._controller_cursor_item:
            self._controller_cursor_item = QGraphicsRectItem()
            cursor_color_tuple_rgba = ED_CONFIG.MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE
            cursor_qcolor = QColor(*cursor_color_tuple_rgba[:3], cursor_color_tuple_rgba[3])
            self._controller_cursor_item.setPen(QPen(cursor_qcolor, 2))
            self._controller_cursor_item.setBrush(QColor(cursor_qcolor.red(), cursor_qcolor.green(), cursor_qcolor.blue(), cursor_qcolor.alpha() // 2))
            self._controller_cursor_item.setZValue(200)
            self.map_scene.addItem(self._controller_cursor_item)

        grid_x, grid_y = self._controller_cursor_pos
        gs_float = float(self.editor_state.grid_size)
        self._controller_cursor_item.setRect(grid_x * gs_float, grid_y * gs_float, gs_float, gs_float)
        self._controller_cursor_item.setVisible(True)
        self.ensureVisible(self._controller_cursor_item, 50, 50)

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        self.editor_state.controller_mode_active = True
        self._update_controller_cursor_visuals()
        logger.debug("MapViewWidget: Controller focus GAINED.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self.editor_state.controller_mode_active = False
        self._update_controller_cursor_visuals()
        logger.debug("MapViewWidget: Controller focus LOST.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus: return
        if self._controller_cursor_pos is None:
            self._controller_cursor_pos = (self.editor_state.map_width_tiles // 2, self.editor_state.map_height_tiles // 2)
        
        grid_x, grid_y = self._controller_cursor_pos
        moved = False
        pan_speed_tiles = 1

        if action == ACTION_UI_UP: grid_y = max(0, grid_y - pan_speed_tiles); moved = True
        elif action == ACTION_UI_DOWN: grid_y = min(self.editor_state.map_height_tiles - 1, grid_y + pan_speed_tiles); moved = True
        elif action == ACTION_UI_LEFT: grid_x = max(0, grid_x - pan_speed_tiles); moved = True
        elif action == ACTION_UI_RIGHT: grid_x = min(self.editor_state.map_width_tiles - 1, grid_x + pan_speed_tiles); moved = True
        elif action == ACTION_MAP_ZOOM_IN: self.zoom_in()
        elif action == ACTION_MAP_ZOOM_OUT: self.zoom_out()
        elif action == ACTION_MAP_TOOL_PRIMARY or action == ACTION_UI_ACCEPT:
            if self.editor_state.current_tool_mode == "select":
                self._select_object_at_controller_cursor()
            elif self.editor_state.current_tool_mode == "place":
                 self._perform_place_action(grid_x, grid_y, is_first_action=True)
            elif self.editor_state.current_tool_mode == "color_pick":
                 self._perform_color_tile_action(grid_x, grid_y, is_first_action=True)
        elif action == ACTION_MAP_TOOL_SECONDARY:
             if self.editor_state.current_tool_mode == "tool_eraser":
                 self._perform_erase_action(grid_x, grid_y, is_first_action=True)
        
        if moved:
            self._controller_cursor_pos = (grid_x, grid_y)
            self._update_controller_cursor_visuals()
        return True # Indicate action was handled

    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        self.map_content_changed.emit()
        logger.debug(f"MapView: Object graphically moved (ID: {id(moved_object_data_ref)}). Unsaved changes flag set.")

    def clear_scene(self):
        logger.debug("MapViewWidget: Clearing scene...")
        self.map_scene.blockSignals(True)
        items_to_remove = list(self.map_scene.items())
        for item in items_to_remove:
            if item.scene() == self.map_scene:
                if isinstance(item, BaseResizableMapItem):
                    item.show_interaction_handles(False)
                    for handle in item.interaction_handles:
                        if handle.scene(): self.map_scene.removeItem(handle)
                    item.interaction_handles.clear()
                self.map_scene.removeItem(item)
                if item is self._controller_cursor_item: self._controller_cursor_item = None
                if item is self._hover_preview_item: self._hover_preview_item = None
        self.map_scene.blockSignals(False)
        self._grid_lines.clear(); self._map_object_items.clear()
        self.update(); logger.debug("MapViewWidget: Scene cleared.")


    def load_map_from_state(self):
        logger.debug("MapViewWidget: Loading map from editor_state...")
        self.clear_scene()
        scene_w = float(self.editor_state.get_map_pixel_width())
        scene_h = float(self.editor_state.get_map_pixel_height())
        self.map_scene.setSceneRect(QRectF(0, 0, max(1.0, scene_w), max(1.0, scene_h)))
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)

        self.update_background_color(emit_view_changed=False)
        
        self.resetTransform()
        current_transform = QTransform()
        current_transform.translate(float(self.editor_state.camera_offset_x * -1), float(self.editor_state.camera_offset_y * -1))
        current_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(current_transform)

        self.update_grid_visibility(emit_view_changed=False)
        self.draw_placed_objects()

        if self._controller_has_focus: self._update_controller_cursor_visuals()
        
        self.viewport().update()
        self.view_changed.emit()
        logger.debug("MapViewWidget: Map loaded from state.")


    def update_background_color(self, emit_view_changed=True):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        if emit_view_changed: self.view_changed.emit()

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene: self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.viewport().update(); return
        
        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0)
        pen.setCosmetic(True)
        
        gs_float = float(self.editor_state.grid_size)
        scene_rect = self.map_scene.sceneRect()
        map_w_px = scene_rect.width(); map_h_px = scene_rect.height()
        start_x = scene_rect.left(); start_y = scene_rect.top()

        current_x_coord = start_x
        while current_x_coord <= start_x + map_w_px + 1e-6:
            line = self.map_scene.addLine(float(current_x_coord), start_y, float(current_x_coord), start_y + map_h_px, pen)
            line.setZValue(-100); self._grid_lines.append(line)
            current_x_coord += gs_float
        current_y_coord = start_y
        while current_y_coord <= start_y + map_h_px + 1e-6:
            line = self.map_scene.addLine(start_x, float(current_y_coord), start_x + map_w_px, float(current_y_coord), pen)
            line.setZValue(-100); self._grid_lines.append(line)
            current_y_coord += gs_float
        self.viewport().update()

    def update_grid_visibility(self, emit_view_changed=True):
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible: return
        
        if not is_visible and self._grid_lines:
            for line in self._grid_lines: line.setVisible(False)
        elif is_visible : self.draw_grid()
        
        self.viewport().update();
        if emit_view_changed: self.view_changed.emit()


    def draw_placed_objects(self):
        current_data_ids_in_state = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        items_to_remove_ids = [item_id for item_id in self._map_object_items if item_id not in current_data_ids_in_state]
        
        for item_id in items_to_remove_ids:
            map_obj_item_to_remove = self._map_object_items[item_id]
            if isinstance(map_obj_item_to_remove, BaseResizableMapItem):
                map_obj_item_to_remove.show_interaction_handles(False)
                for handle in map_obj_item_to_remove.interaction_handles:
                    if handle.scene(): self.map_scene.removeItem(handle)
                map_obj_item_to_remove.interaction_handles.clear()
            if map_obj_item_to_remove.scene() == self.map_scene:
                self.map_scene.removeItem(map_obj_item_to_remove)
            del self._map_object_items[item_id]

        sorted_placed_objects = sorted(self.editor_state.placed_objects, key=lambda obj: obj.get("layer_order", 0))

        for obj_data in sorted_placed_objects:
            item_data_id_from_state = id(obj_data)
            asset_key = str(obj_data.get("asset_editor_key",""))
            map_scene_item: Optional[QGraphicsItem] = None

            if item_data_id_from_state in self._map_object_items:
                map_scene_item = self._map_object_items[item_data_id_from_state]
                if hasattr(map_scene_item, 'map_object_data_ref') and map_scene_item.map_object_data_ref is not obj_data: # type: ignore
                    map_scene_item.map_object_data_ref = obj_data # type: ignore
                if hasattr(map_scene_item, 'update_visuals_from_data'):
                    map_scene_item.update_visuals_from_data(self.editor_state) # type: ignore
            else:
                world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
                if asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY:
                    map_scene_item = CustomImageMapItem(obj_data, self.editor_state)
                elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY:
                    map_scene_item = TriggerSquareMapItem(obj_data, self.editor_state)
                elif asset_key == ED_CONFIG.INVISIBLE_WALL_ASSET_KEY_PALETTE: # Check for invisible wall
                    map_scene_item = InvisibleWallMapItem(obj_data, self.editor_state)
                else:
                    map_scene_item = StandardMapObjectItem(asset_key, str(obj_data.get("game_type_id")),
                                                           int(world_x), int(world_y), obj_data, self.editor_state)
                if map_scene_item:
                    self.map_scene.addItem(map_scene_item)
                    self._map_object_items[item_data_id_from_state] = map_scene_item
            
            if map_scene_item:
                is_editor_hidden = obj_data.get("editor_hidden", False)
                opacity_prop = obj_data.get("properties", {}).get("opacity", 100)
                is_visible_by_opacity = True
                if isinstance(map_scene_item, (CustomImageMapItem, TriggerSquareMapItem, InvisibleWallMapItem)): # Added InvisibleWallMapItem
                    is_visible_by_opacity = opacity_prop > 0
                map_scene_item.setVisible(not is_editor_hidden and is_visible_by_opacity)

            if isinstance(map_scene_item, BaseResizableMapItem) and map_scene_item.isSelected():
                map_scene_item.show_interaction_handles(True)
        
        self.viewport().update()


    def update_specific_object_visuals(self, map_object_data_ref_received: Dict[str, Any]):
        received_id = id(map_object_data_ref_received)
        map_obj_item_to_update: Optional[QGraphicsItem] = self._map_object_items.get(received_id)

        if map_obj_item_to_update:
            if hasattr(map_obj_item_to_update, 'map_object_data_ref'):
                if map_obj_item_to_update.map_object_data_ref is not map_object_data_ref_received: # type: ignore
                    map_obj_item_to_update.map_object_data_ref = map_object_data_ref_received # type: ignore
            
            if hasattr(map_obj_item_to_update, 'update_visuals_from_data'):
                map_obj_item_to_update.update_visuals_from_data(self.editor_state) # type: ignore
            else:
                logger.warning(f"MapView: Item for data ID {received_id} found, but no 'update_visuals_from_data' method.")
        else:
            logger.error(f"MapView: update_specific_object_visuals - Item ID {received_id} "
                         f"(Asset: {map_object_data_ref_received.get('asset_editor_key')}) "
                         "NOT found in _map_object_items. Forcing full redraw.")
            self.draw_placed_objects() 
        
        self.viewport().update()

    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF: return self.mapToScene(screen_pos_qpoint.toPoint())
    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint)
        gs = self.editor_state.grid_size
        return (int(scene_pos.x() // gs), int(scene_pos.y() // gs)) if gs > 0 else (int(scene_pos.x()), int(scene_pos.y()))
    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]:
        gs = self.editor_state.grid_size
        return (float(round(world_x / gs) * gs), float(round(world_y / gs) * gs)) if gs > 0 else (world_x,world_y)
    def _emit_zoom_update_status(self):
        vp_center = self.viewport().rect().center()
        scene_center = self.mapToScene(vp_center)
        grid_coords = self.screen_to_grid_coords(QPointF(float(vp_center.x()), float(vp_center.y())))
        self.mouse_moved_on_map.emit((scene_center.x(), scene_center.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))

    @Slot()
    def zoom_in(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT); self.view_changed.emit()
    @Slot()
    def zoom_out(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT); self.view_changed.emit()
    @Slot()
    def reset_zoom(self):
        center_point_scene = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.editor_state.camera_offset_x = 0.0
        self.editor_state.camera_offset_y = 0.0
        self.editor_state.zoom_level = 1.0
        self.centerOn(center_point_scene)
        self._emit_zoom_update_status()
        self.view_changed.emit()

    def scale_view(self, factor: float):
        current_zoom_transform_m11 = self.transform().m11()
        if abs(current_zoom_transform_m11) < 1e-5 and factor < 1.0 : return

        new_zoom_level_target = self.editor_state.zoom_level * factor
        clamped_new_zoom_target = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom_level_target, ED_CONFIG.MAX_ZOOM_LEVEL))
        
        actual_factor_to_apply = clamped_new_zoom_target / self.editor_state.zoom_level if abs(self.editor_state.zoom_level) > 1e-5 else clamped_new_zoom_target
        
        if abs(actual_factor_to_apply - 1.0) > 1e-5 :
            self.scale(actual_factor_to_apply, actual_factor_to_apply)
            self.editor_state.zoom_level = self.transform().m11()
            self._emit_zoom_update_status()
            self.view_changed.emit()


    def pan_view_by_scrollbars(self, dx: int, dy: int):
        hbar=self.horizontalScrollBar();vbar=self.verticalScrollBar()
        hbar.setValue(hbar.value()+dx); vbar.setValue(vbar.value()+dy)
        self.view_changed.emit()

    def center_on_map_coords(self, p_scene_coords:QPointF):
        self.centerOn(p_scene_coords)
        self.view_changed.emit()

    def get_visible_scene_rect(self) -> QRectF: return self.mapToScene(self.viewport().rect()).boundingRect()
    
    def _cancel_active_transform(self, status_message: str):
        if self.map_scene.property("is_actively_transforming_item"):
            if self.editor_state.undo_stack:
                editor_history.undo(self.editor_state) # type: ignore
                self.on_scene_selection_changed()
            else:
                self.load_map_from_state()

        self._is_resizing_item = False; self._resizing_item_ref = None
        self._resize_handle_active = None; self._resize_start_item_rect_scene = None
        self._resize_start_mouse_pos_scene = None

        self._is_cropping_item = False; self._cropping_item_ref = None
        self._crop_handle_active = None; self._crop_start_item_data = None
        self._crop_start_mouse_pos_scene = None
        
        self.map_scene.setProperty("is_actively_transforming_item", False)
        QApplication.restoreOverrideCursor()
        self.show_status_message(status_message)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key(); modifiers = event.modifiers()
        active_panel: Optional[QWidget] = None
        
        is_map_view_active_panel = False
        if self.parent_window and hasattr(self.parent_window, '_focusable_panels') and \
           hasattr(self.parent_window, '_current_focused_panel_index'):
            main_win = cast('EditorMainWindow', self.parent_window) # type: ignore
            if main_win._focusable_panels and \
               0 <= main_win._current_focused_panel_index < len(main_win._focusable_panels) and \
               main_win._focusable_panels[main_win._current_focused_panel_index] is self:
                is_map_view_active_panel = True

        if is_map_view_active_panel and hasattr(self, 'handle_controller_action'):
            key_name_str: Optional[str] = None
            try:
                key_name_str = Qt.Key(key).name
            except Exception:
                key_name_str = None
            
            if key_name_str is not None:
                action_handled_by_panel = self.handle_controller_action(key_name_str, None)
                if action_handled_by_panel: # handle_controller_action should return True if handled
                    event.accept()
                    return
        
        if (self._is_resizing_item or self._is_cropping_item) and key == Qt.Key.Key_Escape:
            cancel_msg = "Resize cancelled." if self._is_resizing_item else "Crop cancelled."
            self._cancel_active_transform(cancel_msg); event.accept(); return

        if key == Qt.Key.Key_C and modifiers == Qt.KeyboardModifier.ShiftModifier:
            selected_items = self.map_scene.selectedItems()
            if len(selected_items) == 1 and isinstance(selected_items[0], CustomImageMapItem):
                item = cast(CustomImageMapItem, selected_items[0])
                if item.current_interaction_mode == "crop": item.set_interaction_mode("resize"); self.show_status_message("Exited crop mode.")
                else: item.set_interaction_mode("crop"); self.show_status_message("Crop mode enabled.")
                event.accept(); return
        
        if key == Qt.Key.Key_A and modifiers == Qt.KeyboardModifier.ControlModifier:
            self.map_scene.clearSelection()
            for item_id, map_item in self._map_object_items.items():
                if map_item.isVisible() and hasattr(map_item, 'map_object_data_ref') and \
                   not map_item.map_object_data_ref.get("editor_locked", False): # type: ignore
                    map_item.setSelected(True)
            self.show_status_message("Selected all visible, unlocked objects."); event.accept(); return

        if key == Qt.Key.Key_Delete and not (modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if self.map_scene.selectedItems(): self.delete_selected_map_objects(); event.accept(); return

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom_in(); event.accept(); return
            if key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            if key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return
        
        pan_amount = ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND * (1.0 / ED_CONFIG.C.FPS) / self.editor_state.zoom_level # type: ignore
        pan_x, pan_y = 0, 0
        if key == Qt.Key.Key_Left: pan_x = -pan_amount
        elif key == Qt.Key.Key_Right: pan_x = pan_amount
        elif key == Qt.Key.Key_Up: pan_y = -pan_amount
        elif key == Qt.Key.Key_Down: pan_y = pan_amount
        if pan_x != 0 or pan_y != 0: self.pan_view_by_scrollbars(int(pan_x), int(pan_y)); event.accept(); return
        if not event.isAccepted(): super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        modifiers = QApplication.keyboardModifiers()
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key and \
           not (modifiers & Qt.KeyboardModifier.ControlModifier) and not (modifiers & Qt.KeyboardModifier.ShiftModifier): 
            current_base_asset_key = self.editor_state.palette_current_asset_key
            effective_placement_info = self.editor_state.get_current_placement_info()
            effective_asset_key_for_rules = effective_placement_info[0]
            status_msg_orientation = ""; asset_palette_data = self.editor_state.assets_palette.get(str(current_base_asset_key))
            category = asset_palette_data.get("category", "unknown") if asset_palette_data else "unknown"
            is_rotatable_type = effective_asset_key_for_rules in ED_CONFIG.ROTATABLE_ASSET_KEYS
            is_flippable_type = category in ED_CONFIG.FLIPPABLE_ASSET_CATEGORIES or \
                                (current_base_asset_key is not None and current_base_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX)) or \
                                current_base_asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY
            delta = event.angleDelta().y();
            if delta == 0: delta = event.angleDelta().x()
            if delta != 0:
                if is_rotatable_type:
                    direction = 1 if delta > 0 else -1
                    self.editor_state.palette_asset_rotation = (self.editor_state.palette_asset_rotation + direction * 90 + 360) % 360
                    self.editor_state.palette_asset_is_flipped_h = False 
                    status_msg_orientation = f"Rotated to {self.editor_state.palette_asset_rotation}°"
                elif is_flippable_type:
                    if abs(delta) >= 120: 
                        self.editor_state.palette_asset_is_flipped_h = not self.editor_state.palette_asset_is_flipped_h
                        self.editor_state.palette_asset_rotation = 0 
                        status_msg_orientation = "Flipped" if self.editor_state.palette_asset_is_flipped_h else "Normal orientation"
                if status_msg_orientation:
                    asset_display_name = "Current Asset"
                    if current_base_asset_key and asset_palette_data: asset_display_name = asset_palette_data.get("name_in_palette", current_base_asset_key)
                    self.show_status_message(f"{asset_display_name} preview: {status_msg_orientation}")
                    scene_pos = self.mapToScene(event.position().toPoint()); world_x_s, world_y_s = self.snap_to_grid(scene_pos.x(), scene_pos.y())
                    self._update_hover_preview(world_x_s, world_y_s)
                event.accept(); return 
        elif modifiers == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() # Ensure delta is correctly assigned for zoom
            if delta > 0: self.zoom_in()
            elif delta < 0: self.zoom_out()
            event.accept(); return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_tx, grid_ty = self.screen_to_grid_coords(event.position())
        items_under_mouse = self.items(event.position().toPoint())
        for item_candidate in items_under_mouse:
            if isinstance(item_candidate, QGraphicsRectItem) and isinstance(item_candidate.parentItem(), BaseResizableMapItem):
                parent_map_item = cast(BaseResizableMapItem, item_candidate.parentItem())
                if parent_map_item.map_object_data_ref.get("editor_locked", False): event.accept(); return
                if parent_map_item.isSelected() and item_candidate in parent_map_item.interaction_handles:
                    if event.button() == Qt.MouseButton.LeftButton:
                        try:
                            handle_index = parent_map_item.interaction_handles.index(item_candidate)
                            if isinstance(parent_map_item, CustomImageMapItem) and parent_map_item.current_interaction_mode == "crop":
                                self._is_cropping_item = True; self._cropping_item_ref = parent_map_item; self._crop_handle_active = handle_index; self._crop_start_mouse_pos_scene = scene_pos
                                self._crop_start_item_data = {k: parent_map_item.map_object_data_ref.get(k) for k in ["world_x", "world_y", "current_width", "current_height", "crop_rect", "original_width", "original_height"]}
                                if self._crop_start_item_data["crop_rect"]: self._crop_start_item_data["crop_rect"] = self._crop_start_item_data["crop_rect"].copy()
                            else: 
                                self._is_resizing_item = True; self._resizing_item_ref = parent_map_item; self._resize_handle_active = handle_index; self._resize_start_mouse_pos_scene = scene_pos; self._resize_start_item_rect_scene = parent_map_item.sceneBoundingRect()
                            self.map_scene.setProperty("is_actively_transforming_item", True); editor_history.push_undo_state(self.editor_state); event.accept(); return
                        except ValueError: pass
        item_under_mouse: Optional[QGraphicsItem] = None
        for itm in items_under_mouse:
            if isinstance(itm, (StandardMapObjectItem, BaseResizableMapItem)): item_under_mouse = itm; break
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_resizing_item or self._is_cropping_item: return
            if self.editor_state.current_tool_mode == "select":
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) 
                if item_under_mouse and hasattr(item_under_mouse, 'map_object_data_ref') and item_under_mouse.map_object_data_ref.get("editor_locked", False): # type: ignore
                    if not item_under_mouse.isSelected(): self.map_scene.clearSelection(); item_under_mouse.setSelected(True)
                    event.accept(); return
                super().mousePressEvent(event)
            elif self.editor_state.current_tool_mode == "place":
                if self.editor_state.palette_current_asset_key: self._perform_place_action(grid_tx, grid_ty, is_first_action=True)
            elif self.editor_state.current_tool_mode == "color_pick":
                if self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_tx, grid_ty, is_first_action=True)
            elif item_under_mouse and isinstance(item_under_mouse, (StandardMapObjectItem, BaseResizableMapItem)):
                if hasattr(item_under_mouse, 'map_object_data_ref') and not item_under_mouse.map_object_data_ref.get("editor_locked", False): # type: ignore
                    self._is_dragging_map_object = True; self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y']); super().mousePressEvent(event) # type: ignore
                else: event.accept(); return
            else: self.setDragMode(QGraphicsView.DragMode.RubberBandDrag); super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.editor_state.current_tool_mode == "tool_eraser": self._perform_erase_action(grid_tx, grid_ty, is_first_action=True)
            elif item_under_mouse and isinstance(item_under_mouse, (BaseResizableMapItem, StandardMapObjectItem)):
                data_ref = getattr(item_under_mouse, 'map_object_data_ref', None)
                if data_ref: self.context_menu_requested_for_item.emit(data_ref, event.globalPosition()); event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True; self.last_pan_point = event.globalPosition(); self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
        if not event.isAccepted(): super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint()); grid_x, grid_y = self.screen_to_grid_coords(event.position()); world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))
        if self._is_cropping_item and self._cropping_item_ref and self._crop_start_mouse_pos_scene and self._crop_start_item_data and self._crop_handle_active is not None:
            delta_scene = scene_pos - self._crop_start_mouse_pos_scene; item_data_ref = self._cropping_item_ref.map_object_data_ref; start_data = self._crop_start_item_data
            original_img_w = float(start_data.get("original_width", 1.0)); original_img_h = float(start_data.get("original_height", 1.0))
            if original_img_w <= 0: original_img_w = 1.0;
            if original_img_h <= 0: original_img_h = 1.0
            start_visual_x = float(start_data["world_x"]); start_visual_y = float(start_data["world_y"]); start_visual_w = float(start_data["current_width"]); start_visual_h = float(start_data["current_height"])
            start_crop_x, start_crop_y, start_crop_w, start_crop_h = 0.0, 0.0, original_img_w, original_img_h
            if start_data["crop_rect"]: start_crop_x = float(start_data["crop_rect"]["x"]); start_crop_y = float(start_data["crop_rect"]["y"]); start_crop_w = float(start_data["crop_rect"]["width"]); start_crop_h = float(start_data["crop_rect"]["height"])
            if start_crop_w <= 0: start_crop_w = 1.0;
            if start_crop_h <= 0: start_crop_h = 1.0
            scale_visual_to_crop_x = start_visual_w / start_crop_w if start_crop_w != 0 else 1.0; scale_visual_to_crop_y = start_visual_h / start_crop_h if start_crop_h != 0 else 1.0
            new_visual_x, new_visual_y = start_visual_x, start_visual_y; new_visual_w, new_visual_h = start_visual_w, start_visual_h; new_crop_x, new_crop_y = start_crop_x, start_crop_y; new_crop_w, new_crop_h = start_crop_w, start_crop_h
            delta_crop_equivalent_x = delta_scene.x() / scale_visual_to_crop_x if scale_visual_to_crop_x != 0 else 0; delta_crop_equivalent_y = delta_scene.y() / scale_visual_to_crop_y if scale_visual_to_crop_y != 0 else 0
            if self._crop_handle_active in [HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT]: new_visual_y += delta_scene.y(); new_visual_h -= delta_scene.y(); new_crop_y += delta_crop_equivalent_y; new_crop_h -= delta_crop_equivalent_y
            if self._crop_handle_active in [HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT]: new_visual_h += delta_scene.y(); new_crop_h += delta_crop_equivalent_y
            if self._crop_handle_active in [HANDLE_TOP_LEFT, HANDLE_MIDDLE_LEFT, HANDLE_BOTTOM_LEFT]: new_visual_x += delta_scene.x(); new_visual_w -= delta_scene.x(); new_crop_x += delta_crop_equivalent_x; new_crop_w -= delta_crop_equivalent_x
            if self._crop_handle_active in [HANDLE_TOP_RIGHT, HANDLE_MIDDLE_RIGHT, HANDLE_BOTTOM_RIGHT]: new_visual_w += delta_scene.x(); new_crop_w += delta_crop_equivalent_x
            min_visual_dim = max(1.0, float(self.editor_state.grid_size) / 8.0); min_crop_dim_pixels = 1.0
            if new_visual_w < min_visual_dim: new_visual_w = min_visual_dim;
            if new_visual_h < min_visual_dim: new_visual_h = min_visual_dim
            new_crop_w = max(min_crop_dim_pixels, new_crop_w); new_crop_h = max(min_crop_dim_pixels, new_crop_h); new_crop_x = max(0.0, min(new_crop_x, original_img_w - new_crop_w)); new_crop_y = max(0.0, min(new_crop_y, original_img_h - new_crop_h)); new_crop_w = min(new_crop_w, original_img_w - new_crop_x); new_crop_h = min(new_crop_h, original_img_h - new_crop_y)
            item_data_ref["world_x"] = int(round(new_visual_x)); item_data_ref["world_y"] = int(round(new_visual_y)); item_data_ref["current_width"] = int(round(new_visual_w)); item_data_ref["current_height"] = int(round(new_visual_h))
            item_data_ref["crop_rect"] = {"x": int(round(new_crop_x)), "y": int(round(new_crop_y)), "width": int(round(new_crop_w)), "height": int(round(new_crop_h))}
            self._cropping_item_ref.update_visuals_from_data(self.editor_state); self.map_content_changed.emit(); self.map_object_selected_for_properties.emit(item_data_ref); event.accept(); return
        elif self._is_resizing_item and self._resizing_item_ref and self._resize_start_mouse_pos_scene and self._resize_start_item_rect_scene and self._resize_handle_active is not None:
            delta_scene = scene_pos - self._resize_start_mouse_pos_scene; current_item_rect_scene = QRectF(self._resize_start_item_rect_scene); new_x_s, new_y_s, new_w_s, new_h_s = current_item_rect_scene.x(), current_item_rect_scene.y(), current_item_rect_scene.width(), current_item_rect_scene.height()
            if self._resize_handle_active in [HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT]: new_y_s += delta_scene.y(); new_h_s -= delta_scene.y()
            if self._resize_handle_active in [HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT]: new_h_s += delta_scene.y()
            if self._resize_handle_active in [HANDLE_TOP_LEFT, HANDLE_MIDDLE_LEFT, HANDLE_BOTTOM_LEFT]: new_x_s += delta_scene.x(); new_w_s -= delta_scene.x()
            if self._resize_handle_active in [HANDLE_TOP_RIGHT, HANDLE_MIDDLE_RIGHT, HANDLE_BOTTOM_RIGHT]: new_w_s += delta_scene.x()
            min_dim_scene = float(self.editor_state.grid_size) / 2.0;
            if new_w_s < min_dim_scene: new_w_s = min_dim_scene;
            if new_h_s < min_dim_scene: new_h_s = min_dim_scene
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier and self._resizing_item_ref.display_aspect_ratio and self._resizing_item_ref.display_aspect_ratio > 0:
                aspect = self._resizing_item_ref.display_aspect_ratio
                if self._resize_handle_active in [HANDLE_TOP_MIDDLE, HANDLE_BOTTOM_MIDDLE]: new_w_s = new_h_s * aspect; new_x_s = self._resize_start_item_rect_scene.x() + (self._resize_start_item_rect_scene.width() - new_w_s) / 2
                elif self._resize_handle_active in [HANDLE_MIDDLE_LEFT, HANDLE_MIDDLE_RIGHT]: new_h_s = new_w_s / aspect; new_y_s = self._resize_start_item_rect_scene.y() + (self._resize_start_item_rect_scene.height() - new_h_s) / 2
                else:
                    if abs(delta_scene.x()) > abs(delta_scene.y()): new_h_s = new_w_s / aspect
                    else: new_w_s = new_h_s * aspect
                    if self._resize_handle_active == HANDLE_TOP_LEFT: new_x_s = current_item_rect_scene.right() - new_w_s; new_y_s = current_item_rect_scene.bottom() - new_h_s
                    elif self._resize_handle_active == HANDLE_TOP_RIGHT: new_y_s = current_item_rect_scene.bottom() - new_h_s
                    elif self._resize_handle_active == HANDLE_BOTTOM_LEFT: new_x_s = current_item_rect_scene.right() - new_w_s
            item_data_ref = self._resizing_item_ref.map_object_data_ref; item_data_ref["world_x"] = int(round(new_x_s)); item_data_ref["world_y"] = int(round(new_y_s)); item_data_ref["current_width"] = int(round(new_w_s)); item_data_ref["current_height"] = int(round(new_h_s))
            self._resizing_item_ref.update_visuals_from_data(self.editor_state); self.map_content_changed.emit(); self.map_object_selected_for_properties.emit(item_data_ref); event.accept(); return
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key: self._update_hover_preview(world_x_snapped, world_y_snapped)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object: super().mouseMoveEvent(event)
            elif self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key: self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.editor_state.current_tool_mode == "color_pick" and self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_x, grid_y, continuous=True)
            elif self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: super().mouseMoveEvent(event) 
        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.editor_state.current_tool_mode == "tool_eraser": self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point; self.last_pan_point = event.globalPosition(); self.pan_view_by_scrollbars(int(-delta.x()), int(-delta.y())); event.accept(); return
        self._check_edge_scroll(event.position())
        if not event.isAccepted(): super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_resizing_item or self._is_cropping_item:
            self.map_scene.setProperty("is_actively_transforming_item", False); QApplication.restoreOverrideCursor()
            item_transformed_ref = self._resizing_item_ref or self._cropping_item_ref
            if item_transformed_ref: self.map_content_changed.emit(); self.show_status_message("Object resized." if self._is_resizing_item else "Image cropped."); self.map_object_selected_for_properties.emit(item_transformed_ref.map_object_data_ref)
            self._is_resizing_item = False; self._resizing_item_ref = None; self._resize_handle_active = None; self._resize_start_item_rect_scene = None; self._resize_start_mouse_pos_scene = None
            self._is_cropping_item = False; self._cropping_item_ref = None; self._crop_handle_active = None; self._crop_start_item_data = None; self._crop_start_mouse_pos_scene = None
            if event.button() == Qt.MouseButton.LeftButton: event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False; item_dragged: Optional[QGraphicsItem] = None
            if self.map_scene.selectedItems() and isinstance(self.map_scene.selectedItems()[0], (StandardMapObjectItem, BaseResizableMapItem)): item_dragged = self.map_scene.selectedItems()[0]
            if item_dragged and self._drag_start_data_coords and hasattr(item_dragged, 'map_object_data_ref'):
                item_data = item_dragged.map_object_data_ref # type: ignore
                if self._drag_start_data_coords[0] != item_data['world_x'] or self._drag_start_data_coords[1] != item_data['world_y']: editor_history.push_undo_state(self.editor_state); self.map_content_changed.emit()
            self._drag_start_data_coords = None
        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False; self.setDragMode(QGraphicsView.DragMode.NoDrag); self.unsetCursor()
            self.view_changed.emit(); event.accept(); return
        self.editor_state.last_painted_tile_coords = None; self.editor_state.last_erased_tile_coords = None; self.editor_state.last_colored_tile_coords = None
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key:
             if not self.itemAt(event.pos()): event.accept(); return
        scene_pos = self.mapToScene(event.pos()); item_under_mouse = self.itemAt(scene_pos.toPoint())
        if isinstance(item_under_mouse, BaseResizableMapItem):
            data_ref = getattr(item_under_mouse, 'map_object_data_ref', None)
            if data_ref:
                asset_key = data_ref.get("asset_editor_key")
                # Allow context menu for TriggerSquare, CustomImage, and now InvisibleWall
                if asset_key in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY, ED_CONFIG.INVISIBLE_WALL_ASSET_KEY_PALETTE]:
                    self.context_menu_requested_for_item.emit(data_ref, event.globalPos()); event.accept(); return
        if not event.isAccepted(): super().contextMenuEvent(event)

    def enterEvent(self, event: QHoverEvent): # type: ignore
        if not self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start(); super().enterEvent(event) 
    def leaveEvent(self, event: QHoverEvent): # type: ignore
        if self.edge_scroll_timer.isActive(): self.edge_scroll_timer.stop(); self._edge_scroll_dx = 0; self._edge_scroll_dy = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False); QApplication.restoreOverrideCursor(); super().leaveEvent(event) 
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

    @Slot(str, bool, int, int) 
    def on_asset_selected_for_placement(self, asset_key: Optional[str], is_flipped: bool, wall_variant_idx: int, rotation: int):
        logger.debug(f"MapView: on_asset_selected_for_placement key: '{asset_key}', flipped: {is_flipped}, rotation: {rotation}, wall_idx: {wall_variant_idx}")
        self.editor_state.palette_current_asset_key = asset_key; self.editor_state.palette_asset_is_flipped_h = is_flipped; self.editor_state.palette_asset_rotation = rotation; self.editor_state.palette_wall_variant_index = wall_variant_idx
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key:
             if self.underMouse(): scene_pos = self.mapToScene(self.mapFromGlobal(QCursor.pos())); world_x_s, world_y_s = self.snap_to_grid(scene_pos.x(), scene_pos.y()); self._update_hover_preview(world_x_s, world_y_s)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)

    def _update_hover_preview(self, world_x: float, world_y: float):
        effective_asset_key, is_flipped_for_hover, rotation_for_hover, _ = self.editor_state.get_current_placement_info()
        if self.editor_state.current_tool_mode == "place" and effective_asset_key:
            pixmap: Optional[QPixmap] = None
            if effective_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
                filename = effective_asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1]; map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function)
                full_path = "";
                if map_folder: full_path = os.path.join(map_folder, "Custom", filename)
                if map_folder and os.path.exists(full_path): 
                    temp_asset_data = {"source_file": full_path, "original_size_pixels": None }; img_obj = QImage(full_path)
                    if not img_obj.isNull(): orig_w, orig_h = img_obj.width(), img_obj.height(); pixmap = get_asset_pixmap(effective_asset_key, temp_asset_data, QSizeF(float(orig_w), float(orig_h)), None, get_native_size_only=True, is_flipped_h=is_flipped_for_hover, rotation=rotation_for_hover)
            else:
                asset_data = self.editor_state.assets_palette.get(effective_asset_key) 
                if asset_data: 
                    original_w_tuple, original_h_tuple = asset_data.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE)); original_w, original_h = float(original_w_tuple), float(original_h_tuple); pixmap = get_asset_pixmap(effective_asset_key, asset_data, QSizeF(original_w,original_h), self.editor_state.current_selected_asset_paint_color, get_native_size_only=True, is_flipped_h=is_flipped_for_hover, rotation=rotation_for_hover)
            if pixmap and not pixmap.isNull():
                if not self._hover_preview_item: self._hover_preview_item = QGraphicsPixmapItem(); self._hover_preview_item.setZValue(100); self.map_scene.addItem(self._hover_preview_item); self._hover_preview_item.setOpacity(0.7) 
                if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): self._hover_preview_item.setPixmap(pixmap)
                self._hover_preview_item.setPos(QPointF(world_x, world_y)); self._hover_preview_item.setVisible(True); return
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)

    @Slot(str) 
    def on_tool_selected(self, tool_key: str):
        logger.debug(f"MapView: on_tool_selected tool_key: '{tool_key}'")
        self.editor_state.palette_current_asset_key = None; self.editor_state.palette_asset_is_flipped_h = False; self.editor_state.palette_asset_rotation = 0; self.editor_state.palette_wall_variant_index = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if tool_key == "tool_select": self.editor_state.current_tool_mode = "select"; self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) 
        elif tool_key == "tool_eraser": self.editor_state.current_tool_mode = "tool_eraser"; self.setDragMode(QGraphicsView.DragMode.NoDrag)
        elif tool_key == "tool_tile_color_picker":
            self.editor_state.current_tool_mode = "color_pick"; self.setDragMode(QGraphicsView.DragMode.NoDrag)
            if self.parent_window:
                initial_c = self.editor_state.current_selected_asset_paint_color or self.editor_state.current_tile_paint_color or ED_CONFIG.C.BLUE # type: ignore
                new_q_color = QColorDialog.getColor(QColor(*initial_c), cast(QWidget, self.parent_window), "Select Tile Paint Color") 
                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None 
                if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(f"Color Picker: {self.editor_state.current_tile_paint_color or 'None'}") #type: ignore
        elif tool_key == "platform_wall_gray_2x2_placer": self.editor_state.current_tool_mode = "place"; self.editor_state.palette_current_asset_key = tool_key; self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else: self.editor_state.current_tool_mode = "select"; self.setDragMode(QGraphicsView.DragMode.RubberBandDrag); logger.warning(f"MapView: Unknown tool_key '{tool_key}', defaulting to select mode.")
        logger.debug(f"MapView: current_tool_mode set to '{self.editor_state.current_tool_mode}'")

    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: Dict[str, Any]):
        logger.debug(f"MapView: on_object_properties_changed for obj data ID: {id(changed_object_data_ref)}")
        self.update_specific_object_visuals(changed_object_data_ref)

    @Slot()
    def on_scene_selection_changed(self):
        selected_qt_items = self.map_scene.selectedItems()
        logger.debug(f"MapView: on_scene_selection_changed. Count: {len(selected_qt_items)}")
        for item_id, map_obj_item_generic in self._map_object_items.items():
            if isinstance(map_obj_item_generic, BaseResizableMapItem):
                is_currently_selected = map_obj_item_generic in selected_qt_items
                map_obj_item_generic.show_interaction_handles(is_currently_selected)
                if not is_currently_selected and map_obj_item_generic.current_interaction_mode == "crop": map_obj_item_generic.set_interaction_mode("resize")
        if len(selected_qt_items) == 1:
            selected_item_generic = selected_qt_items[0]
            if isinstance(selected_item_generic, (StandardMapObjectItem, BaseResizableMapItem)): # BaseResizableMapItem covers CustomImage, Trigger, InvisibleWall
                data_ref = getattr(selected_item_generic, 'map_object_data_ref', None)
                if data_ref: self.map_object_selected_for_properties.emit(data_ref)
                else: self.map_object_selected_for_properties.emit(None)
            else: self.map_object_selected_for_properties.emit(None)
        else: self.map_object_selected_for_properties.emit(None)

    def show_status_message(self, message: str, timeout: int = 2000):
        if hasattr(self.parent_window, "show_status_message"): self.parent_window.show_status_message(message, timeout) # type: ignore
        else: logger.info(f"Status (MapView): {message}")

    def remove_visual_item_for_data_ref(self, obj_data_ref_to_remove: Dict[str, Any]):
        item_id_to_remove = id(obj_data_ref_to_remove)
        if item_id_to_remove in self._map_object_items:
            item_qgraphics = self._map_object_items[item_id_to_remove]
            if isinstance(item_qgraphics, BaseResizableMapItem):
                item_qgraphics.show_interaction_handles(False)
                for handle in item_qgraphics.interaction_handles:
                    if handle.scene(): self.map_scene.removeItem(handle)
                item_qgraphics.interaction_handles.clear()
            
            if item_qgraphics.scene() == self.map_scene:
                self.map_scene.removeItem(item_qgraphics)
            
            del self._map_object_items[item_id_to_remove]
            logger.debug(f"MapView: Removed visual item for data ID {item_id_to_remove}.")
        else:
            logger.warning(f"MapView: Attempted to remove visual item for data ID {item_id_to_remove}, but it was not found in _map_object_items.")
        
        self.viewport().update()