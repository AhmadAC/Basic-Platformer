#################### START OF FILE: editor\map_view_widget.py ####################

# editor/map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
Version 2.0.7 (Corrected controller cursor initialization)
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

from . import editor_config as ED_CONFIG # Use relative import
from .editor_state import EditorState # Use relative import
from . import editor_history # Use relative import
from .editor_assets import get_asset_pixmap # Use relative import
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                             ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY,
                             ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN)


logger = logging.getLogger(__name__) # Uses logger configured in editor.py

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
            new_pos = value # This is a QPointF
            grid_size_prop = self.scene().property("grid_size")
            grid_size = grid_size_prop if isinstance(grid_size_prop, (int, float)) and grid_size_prop > 0 else ED_CONFIG.BASE_GRID_SIZE # type: ignore

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if int(snapped_x) != self.map_object_data_ref.get('world_x') or \
               int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                # Emit signal that an object was moved by the user graphically
                if self.scene() and hasattr(self.scene().parent(), 'object_graphically_moved_signal'):
                    # Ensure parent is MapViewWidget to access the signal
                    if isinstance(self.scene().parent(), MapViewWidget):
                        logger.debug(f"MapObjectItem: Emitting object_graphically_moved_signal for {self.editor_key}")
                        self.scene().parent().object_graphically_moved_signal.emit(self.map_object_data_ref)

            # If the new position is not already snapped, return the snapped position
            if abs(new_pos.x() - snapped_x) > 0.01 or abs(new_pos.y() - snapped_y) > 0.01:
                return QPointF(float(snapped_x), float(snapped_y)) # Ensure return is QPointF
            return new_pos # Return QPointF
        return super().itemChange(change, value)

    def update_visuals(self, new_pixmap: Optional[QPixmap] = None, new_color: Optional[QColor] = None, editor_state: Optional[EditorState] = None):
        if new_pixmap and not new_pixmap.isNull():
            self.setPixmap(new_pixmap)
            self.initial_pixmap = new_pixmap # Update the base pixmap if a completely new one is provided
        elif new_color and editor_state:
            # Colorize the initial_pixmap
            asset_data = editor_state.assets_palette.get(self.editor_key)
            if asset_data and asset_data.get("colorable"):
                try:
                    # Use original_size_pixels from asset_data for consistent sizing
                    original_w, original_h = asset_data.get("original_size_pixels",
                                                             (self.initial_pixmap.width() if self.initial_pixmap else ED_CONFIG.BASE_GRID_SIZE, # type: ignore
                                                              self.initial_pixmap.height() if self.initial_pixmap else ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
                    
                    colored_pixmap = get_asset_pixmap(
                        self.editor_key, asset_data,
                        target_size=QSize(int(original_w), int(original_h)), # Ensure target_size is QSize
                        override_color=new_color.getRgb()[:3], # Pass color as tuple
                        get_native_size_only=True # We want the native, colored pixmap
                    )

                    if colored_pixmap and not colored_pixmap.isNull():
                        self.setPixmap(colored_pixmap)
                    elif self.initial_pixmap and not self.initial_pixmap.isNull(): # Fallback to initial if coloring failed
                        self.setPixmap(self.initial_pixmap)
                    else: # Ultimate fallback
                        fallback_pix = QPixmap(int(original_w), int(original_h))
                        fallback_pix.fill(Qt.GlobalColor.magenta)
                        self.setPixmap(fallback_pix)
                except Exception as e:
                    logger.error(f"Error updating visual for {self.editor_key} with color {new_color.name()}: {e}", exc_info=True)
                    if self.initial_pixmap and not self.initial_pixmap.isNull(): self.setPixmap(self.initial_pixmap) # Fallback
        elif self.initial_pixmap and not self.initial_pixmap.isNull(): # No new color/pixmap, ensure it's the base
             self.setPixmap(self.initial_pixmap)


class MapViewWidget(QGraphicsView):
    mouse_moved_on_map = Signal(tuple)
    map_object_selected_for_properties = Signal(object)
    map_content_changed = Signal()
    object_graphically_moved_signal = Signal(dict) # For undo after graphical move
    view_changed = Signal() # For minimap updates

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent # EditorMainWindow

        self.map_scene = QGraphicsScene(self)
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.setScene(self.map_scene)
        self.object_graphically_moved_signal.connect(self._handle_internal_object_move_for_unsaved_changes)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag) # Default to NoDrag, enable RubberBandDrag on click

        self._grid_lines: List[QGraphicsLineItem] = []
        self._map_object_items: Dict[int, MapObjectItem] = {} # Stores MapObjectItem instances, keyed by id(obj_data)
        self._hover_preview_item: Optional[QGraphicsPixmapItem] = None # For mouse hover

        self.current_tool = "place" # Default tool for mouse interaction
        self.middle_mouse_panning = False
        self.last_pan_point = QPointF()
        self._is_dragging_map_object = False # For mouse-drag of existing objects
        self._drag_start_data_coords: Optional[Tuple[int, int]] = None # world_x, world_y

        # Edge scrolling timer
        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(30) # ms
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Allow receiving Qt focus
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)

        # --- Controller Navigation State ---
        self._controller_has_focus = False
        self._controller_cursor_pos: Optional[Tuple[int, int]] = None # Tile coords (grid_x, grid_y)
        self._controller_cursor_item: Optional[QGraphicsRectItem] = None
        self._controller_tool_mode = "place" # Can be 'place', 'erase', 'color_pick' 
                                            # (Note: color_pick via controller is not fully implemented yet)

        self.load_map_from_state()
        logger.debug("MapViewWidget initialized.")

    def _update_controller_cursor_visuals(self):
        if not self._controller_has_focus or self._controller_cursor_pos is None:
            if self._controller_cursor_item:
                self._controller_cursor_item.setVisible(False)
            return

        if not self._controller_cursor_item:
            self._controller_cursor_item = QGraphicsRectItem()
            cursor_color = QColor(*ED_CONFIG.MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE) # type: ignore
            self._controller_cursor_item.setPen(QPen(cursor_color, 2)) 
            self._controller_cursor_item.setBrush(QColor(cursor_color.red(), cursor_color.green(), cursor_color.blue(), cursor_color.alpha() // 2)) # More transparent fill
            self._controller_cursor_item.setZValue(200) # Above everything
            self.map_scene.addItem(self._controller_cursor_item)

        grid_x, grid_y = self._controller_cursor_pos
        gs = float(self.editor_state.grid_size)
        self._controller_cursor_item.setRect(grid_x * gs, grid_y * gs, gs, gs)
        self._controller_cursor_item.setVisible(True)
        self.ensureVisible(self._controller_cursor_item, 50, 50) # Ensure cursor is visible, with 50px margins

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        self.editor_state.controller_mode_active = True
        if self._controller_cursor_pos is None: # Initialize cursor
            map_center_gx = self.editor_state.map_width_tiles // 2
            map_center_gy = self.editor_state.map_height_tiles // 2
            self._controller_cursor_pos = (map_center_gx, map_center_gy)
        self._update_controller_cursor_visuals()
        logger.debug("MapView: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self.editor_state.controller_mode_active = False
        if self._controller_cursor_item:
            self._controller_cursor_item.setVisible(False)
        logger.debug("MapView: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus:
            return
        
        if self._controller_cursor_pos is None: 
            map_center_gx = self.editor_state.map_width_tiles // 2
            map_center_gy = self.editor_state.map_height_tiles // 2
            self._controller_cursor_pos = (map_center_gx, map_center_gy)
            self._update_controller_cursor_visuals() 
            logger.debug(f"MapView: Controller cursor initialized to center ({map_center_gx},{map_center_gy}) during action handling.")

        # Now _controller_cursor_pos is guaranteed to be a tuple
        grid_x, grid_y = self._controller_cursor_pos 
        
        moved = False
        pan_speed_tiles = 1 # How many tiles to move cursor per D-pad press

        if action == ACTION_UI_UP:
            grid_y = max(0, grid_y - pan_speed_tiles); moved = True
        elif action == ACTION_UI_DOWN:
            grid_y = min(self.editor_state.map_height_tiles - 1, grid_y + pan_speed_tiles); moved = True
        elif action == ACTION_UI_LEFT:
            grid_x = max(0, grid_x - pan_speed_tiles); moved = True
        elif action == ACTION_UI_RIGHT:
            grid_x = min(self.editor_state.map_width_tiles - 1, grid_x + pan_speed_tiles); moved = True
        
        if moved:
            self._controller_cursor_pos = (grid_x, grid_y)
            self._update_controller_cursor_visuals()
            logger.debug(f"MapView: Controller cursor moved to ({grid_x},{grid_y})")

        elif action == ACTION_MAP_TOOL_PRIMARY:
            logger.debug(f"MapView: Controller ACTION_MAP_TOOL_PRIMARY at ({grid_x},{grid_y})")
            if self.editor_state.selected_asset_editor_key: # Place tool
                self._perform_place_action(grid_x, grid_y, is_first_action=True) 
        elif action == ACTION_MAP_TOOL_SECONDARY:
            logger.debug(f"MapView: Controller ACTION_MAP_TOOL_SECONDARY at ({grid_x},{grid_y})")
            self._perform_erase_action(grid_x, grid_y, is_first_action=True) 
        elif action == ACTION_MAP_ZOOM_IN:
            self.zoom_in()
        elif action == ACTION_MAP_ZOOM_OUT:
            self.zoom_out()
        elif action == ACTION_UI_ACCEPT:
            self._select_object_at_controller_cursor()

    def handle_controller_camera_pan(self, action: str, axis_value: float):
        pan_amount_pixels_per_input_event = getattr(ED_CONFIG, "CONTROLLER_CAMERA_PAN_SPEED_PIXELS", 30)
        
        dy_pixels = 0
        if action == ACTION_CAMERA_PAN_UP: 
            dy_pixels = int(pan_amount_pixels_per_input_event * axis_value) 
        elif action == ACTION_CAMERA_PAN_DOWN: 
            dy_pixels = int(pan_amount_pixels_per_input_event * axis_value)

        if dy_pixels != 0:
            self.pan_view_by_scrollbars(0, dy_pixels) 
            logger.debug(f"MapView: Controller panned camera vertically by {dy_pixels} pixels (Action: {action}, Value: {axis_value:.2f})")


    def _select_object_at_controller_cursor(self):
        if not self._controller_cursor_pos: return
        grid_x, grid_y = self._controller_cursor_pos
        world_x = grid_x * self.editor_state.grid_size
        world_y = grid_y * self.editor_state.grid_size
        
        found_item_to_select: Optional[MapObjectItem] = None
        for item_id, map_obj_item in self._map_object_items.items():
            obj_data = map_obj_item.map_object_data_ref
            if obj_data.get("world_x") == world_x and obj_data.get("world_y") == world_y:
                found_item_to_select = map_obj_item
                break 
        
        self.map_scene.clearSelection()
        if found_item_to_select:
            found_item_to_select.setSelected(True)
            logger.info(f"MapView: Controller selected object '{found_item_to_select.editor_key}' at controller cursor.")
        else:
            logger.info(f"MapView: Controller accept pressed, no object at controller cursor.")
            self.map_object_selected_for_properties.emit(None)


    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        logger.debug(f"MapView: Received object_graphically_moved_signal for object data ID: {id(moved_object_data_ref)}. Emitting map_content_changed.")
        self.map_content_changed.emit()

    def clear_scene(self):
        logger.debug("MapViewWidget: Clearing scene...")
        self.map_scene.blockSignals(True) 
        items_to_remove = list(self.map_scene.items()) 
        for item in items_to_remove:
            if item.scene() == self.map_scene: 
                self.map_scene.removeItem(item)
                if item is self._controller_cursor_item: self._controller_cursor_item = None
                if item is self._hover_preview_item: self._hover_preview_item = None
        self.map_scene.blockSignals(False)
        self._grid_lines.clear()
        self._map_object_items.clear() 
        self.update() 
        logger.debug("MapViewWidget: Scene cleared.")

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

        if self._controller_has_focus:
            self._update_controller_cursor_visuals()

        logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}, Zoom: {self.editor_state.zoom_level:.2f}, Offset: ({self.editor_state.camera_offset_x:.1f}, {self.editor_state.camera_offset_y:.1f})")
        self.viewport().update() 
        self.view_changed.emit() 


    def update_background_color(self, emit_view_changed=True):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        if emit_view_changed:
            self.view_changed.emit()

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene: 
                self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.viewport().update(); return

        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0) # type: ignore 
        pen.setCosmetic(True) 

        gs_float = float(self.editor_state.grid_size)
        scene_rect = self.map_scene.sceneRect()
        map_w_px = scene_rect.width(); map_h_px = scene_rect.height()
        start_x = scene_rect.left(); start_y = scene_rect.top()
        
        current_x_coord = start_x
        while current_x_coord <= start_x + map_w_px + 1e-6: 
            line = self.map_scene.addLine(float(current_x_coord), start_y, float(current_x_coord), start_y + map_h_px, pen)
            line.setZValue(-1); self._grid_lines.append(line)
            if gs_float <= 1e-6: break; current_x_coord += gs_float

        current_y_coord = start_y
        while current_y_coord <= start_y + map_h_px + 1e-6:
            line = self.map_scene.addLine(start_x, float(current_y_coord), start_x + map_w_px, float(current_y_coord), pen)
            line.setZValue(-1); self._grid_lines.append(line)
            if gs_float <= 1e-6: break; current_y_coord += gs_float
        self.viewport().update()


    def update_grid_visibility(self, emit_view_changed=True):
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible: return 
        if not is_visible and self._grid_lines: 
            for line in self._grid_lines: line.setVisible(False)
        elif is_visible : self.draw_grid() 
        self.viewport().update()
        if emit_view_changed: self.view_changed.emit()


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
            if not asset_info_from_palette: 
                game_id_of_obj = obj_data.get("game_type_id")
                if game_id_of_obj:
                    found_fallback = False
                    for pal_key_iter, pal_data_iter in self.editor_state.assets_palette.items():
                        if pal_data_iter.get("game_type_id") == game_id_of_obj:
                            asset_info_from_palette = pal_data_iter; asset_key = pal_key_iter 
                            logger.info(f"DrawPlaced (Fallback): Remapped loaded asset with game_type_id '{game_id_of_obj}' to palette key '{asset_key}'.")
                            found_fallback = True; break
                    if not found_fallback: logger.warning(f"DrawPlaced: Asset info for key '{obj_data.get('asset_editor_key')}' or game_type_id '{game_id_of_obj}' not found. Skipping."); continue
                else: logger.warning(f"DrawPlaced: Asset info for key '{asset_key}' not found and no game_type_id. Skipping."); continue
            if not asset_info_from_palette: logger.error(f"DrawPlaced: CRITICAL - asset_info_from_palette is None for asset_key '{asset_key}'. Skipping."); continue

            original_w, original_h = asset_info_from_palette.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
            pixmap_to_draw = get_asset_pixmap(asset_key, asset_info_from_palette, QSize(original_w, original_h), obj_data.get("override_color"), get_native_size_only=True)
            if not pixmap_to_draw or pixmap_to_draw.isNull(): logger.warning(f"DrawPlaced: Pixmap for asset '{asset_key}' is null. Not drawn."); continue

            world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
            if item_data_id in self._map_object_items: 
                map_obj_item = self._map_object_items[item_data_id]
                if map_obj_item.pixmap().cacheKey() != pixmap_to_draw.cacheKey(): map_obj_item.setPixmap(pixmap_to_draw)
                if map_obj_item.pos() != QPointF(world_x, world_y): map_obj_item.setPos(QPointF(world_x, world_y))
                map_obj_item.editor_key = asset_key; map_obj_item.game_type_id = str(obj_data.get("game_type_id")); map_obj_item.map_object_data_ref = obj_data 
            else: 
                map_obj_item = MapObjectItem(asset_key, str(obj_data.get("game_type_id")), pixmap_to_draw, int(world_x), int(world_y), obj_data)
                self.map_scene.addItem(map_obj_item); self._map_object_items[item_data_id] = map_obj_item
        self.viewport().update()


    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
        return self.mapToScene(screen_pos_qpoint.toPoint()) 
    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint); gs = self.editor_state.grid_size
        if gs <= 0: return (int(scene_pos.x()), int(scene_pos.y())); return (int(scene_pos.x() // gs), int(scene_pos.y() // gs))
    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]:
        gs = self.editor_state.grid_size; return (float(round(world_x / gs) * gs), float(round(world_y / gs) * gs)) if gs > 0 else (world_x, world_y)
    def _emit_zoom_update_status(self):
        vp_center = self.viewport().rect().center(); sc_center = self.mapToScene(vp_center)
        gc = self.screen_to_grid_coords(QPointF(float(vp_center.x()), float(vp_center.y())))
        self.mouse_moved_on_map.emit((sc_center.x(), sc_center.y(), gc[0], gc[1], self.editor_state.zoom_level))
    @Slot()
    def zoom_in(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT); self.view_changed.emit() # type: ignore
    @Slot()
    def zoom_out(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT); self.view_changed.emit() # type: ignore
    @Slot()
    def reset_zoom(self):
        vp_center_scene = self.mapToScene(self.viewport().rect().center()); self.resetTransform()
        self.editor_state.camera_offset_x = 0.0; self.editor_state.camera_offset_y = 0.0; self.editor_state.zoom_level = 1.0
        self.translate(0,0); self.centerOn(vp_center_scene)
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
        self._emit_zoom_update_status(); self.view_changed.emit()
    def scale_view(self, factor: float):
        current_zoom = self.transform().m11(); new_zoom = current_zoom * factor
        if abs(current_zoom) < 1e-5 and factor < 1.0: return
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL)) # type: ignore
        actual_factor = clamped_zoom / current_zoom if abs(current_zoom) > 1e-5 else (clamped_zoom if clamped_zoom > ED_CONFIG.MIN_ZOOM_LEVEL else 1.0) # type: ignore
        if abs(actual_factor - 1.0) > 1e-4:
            self.scale(actual_factor, actual_factor); self.editor_state.zoom_level = self.transform().m11()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self._emit_zoom_update_status()
    def pan_view_by_scrollbars(self, dx_pixels: int, dy_pixels: int):
        h_bar, v_bar = self.horizontalScrollBar(), self.verticalScrollBar()
        h_bar.setValue(h_bar.value() + dx_pixels); v_bar.setValue(v_bar.value() + dy_pixels)
        self.editor_state.camera_offset_x = float(h_bar.value()); self.editor_state.camera_offset_y = float(v_bar.value())
        self.view_changed.emit()
    def center_on_map_coords(self, map_coords_qpointf: QPointF):
        self.centerOn(map_coords_qpointf)
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
        self.editor_state.zoom_level = self.transform().m11(); self.view_changed.emit()
    def get_visible_scene_rect(self) -> QRectF: return self.mapToScene(self.viewport().rect()).boundingRect()
    def keyPressEvent(self, event: QKeyEvent):
        key, mods = event.key(), event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key in [Qt.Key.Key_Plus, Qt.Key.Key_Equal]: self.zoom_in(); event.accept(); return
            elif key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            elif key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return
        pan_step = int(ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND / 60.0); dx, dy = 0,0 # type: ignore
        if key == Qt.Key.Key_A: dx = -pan_step
        elif key == Qt.Key.Key_D: dx = pan_step
        elif key == Qt.Key.Key_W: dy = -pan_step
        elif key == Qt.Key.Key_S and not (mods & Qt.KeyboardModifier.ControlModifier): dy = pan_step
        if dx or dy: self.pan_view_by_scrollbars(dx, dy); event.accept(); return
        if key == Qt.Key.Key_Delete: self.delete_selected_map_objects(); event.accept(); return
        super().keyPressEvent(event)
    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False; scene_pos = self.mapToScene(event.position().toPoint())
        grid_tx, grid_ty = self.screen_to_grid_coords(event.position()); item_under_mouse = self.itemAt(event.position().toPoint())
        logger.debug(f"MapView: mousePressEvent - Btn:{event.button()}, Tool:'{self.current_tool}', Asset:'{self.editor_state.selected_asset_editor_key}', ItemUnder:{type(item_under_mouse).__name__ if item_under_mouse else 'None'}, Grid:({grid_tx},{grid_ty})")
        if event.button() == Qt.MouseButton.LeftButton:
            if item_under_mouse and isinstance(item_under_mouse, MapObjectItem):
                self._is_dragging_map_object = True; self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y'])
                super().mousePressEvent(event) 
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key: self._perform_place_action(grid_tx, grid_ty, is_first_action=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_tx, grid_ty, is_first_action=True)
            else: self.setDragMode(QGraphicsView.DragMode.RubberBandDrag); super().mousePressEvent(event) 
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_under_mouse):
                self._perform_erase_action(grid_tx, grid_ty, is_first_action=True)
            else: super().mousePressEvent(event) 
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True; self.last_pan_point = event.globalPosition()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return 
        if not event.isAccepted(): super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint()); grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snap, world_y_snap = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))
        self._update_hover_preview(world_x_snap, world_y_snap)
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object: super().mouseMoveEvent(event) 
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key: self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color: self._perform_color_tile_action(grid_x, grid_y, continuous=True)
            elif self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: super().mouseMoveEvent(event) 
        elif event.buttons() == Qt.MouseButton.RightButton and (self.current_tool == "erase" or (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key)):
            self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point; self.last_pan_point = event.globalPosition()
            self.pan_view_by_scrollbars(int(-delta.x()), int(-delta.y())); event.accept(); return 
        self._check_edge_scroll(event.position())
        if not event.isAccepted(): super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False
            sel_items = self.map_scene.selectedItems()
            item_dragged = sel_items[0] if sel_items and isinstance(sel_items[0], MapObjectItem) else None
            if item_dragged and self._drag_start_data_coords and \
               (self._drag_start_data_coords[0] != item_dragged.map_object_data_ref['world_x'] or self._drag_start_data_coords[1] != item_dragged.map_object_data_ref['world_y']):
                editor_history.push_undo_state(self.editor_state); self.map_content_changed.emit() # type: ignore
            self._drag_start_data_coords = None 
        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False; self.setDragMode(QGraphicsView.DragMode.NoDrag); self.unsetCursor()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self.view_changed.emit(); event.accept(); return
        self.editor_state.last_painted_tile_coords = None; self.editor_state.last_erased_tile_coords = None; self.editor_state.last_colored_tile_coords = None
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)
    def enterEvent(self, event: QFocusEvent): 
        if not self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start(); super().enterEvent(event)
    def leaveEvent(self, event: QFocusEvent): 
        if self.edge_scroll_timer.isActive(): self.edge_scroll_timer.stop()
        self._edge_scroll_dx, self._edge_scroll_dy = 0,0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False); super().leaveEvent(event)
    def _check_edge_scroll(self, mouse_pos_vp: QPointF):
        self._edge_scroll_dx, self._edge_scroll_dy = 0,0; zone, vr = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS, self.viewport().rect() # type: ignore
        if mouse_pos_vp.x() < zone: self._edge_scroll_dx = -1
        elif mouse_pos_vp.x() > vr.width() - zone: self._edge_scroll_dx = 1
        if mouse_pos_vp.y() < zone: self._edge_scroll_dy = -1
        elif mouse_pos_vp.y() > vr.height() - zone: self._edge_scroll_dy = 1
        should_be_active = bool(self._edge_scroll_dx or self._edge_scroll_dy)
        if should_be_active != self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start() if should_be_active else self.edge_scroll_timer.stop()
    @Slot()
    def perform_edge_scroll(self):
        if self._edge_scroll_dx or self._edge_scroll_dy:
            amount = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0) # type: ignore
            self.pan_view_by_scrollbars(int(self._edge_scroll_dx * amount), int(self._edge_scroll_dy * amount))
    def _perform_place_action(self, gx, gy, continuous=False, is_first=False):
        if continuous and (gx,gy) == self.editor_state.last_painted_tile_coords: return
        asset_key = self.editor_state.selected_asset_editor_key
        if not asset_key: logger.warning("MapView: Place action but no asset selected."); return
        asset_data_pal = self.editor_state.assets_palette.get(str(asset_key))
        if not asset_data_pal: logger.error(f"MapView: Asset data for '{asset_key}' not in palette."); return
        actual_key = asset_data_pal.get("places_asset_key", asset_key).strip() or asset_key
        target_def = self.editor_state.assets_palette.get(str(actual_key))
        if not target_def: logger.error(f"MapView: Target asset def for '{actual_key}' not found."); return
        made_change = False
        if is_first: editor_history.push_undo_state(self.editor_state) # type: ignore
        if asset_data_pal.get("places_asset_key") and asset_data_pal.get("icon_type") == "2x2_placer":
            for ro, co in [(0,0),(0,1),(1,0),(1,1)]:
                if self._place_single_object_on_map(str(actual_key), target_def, gx+co, gy+ro): made_change = True
        elif self._place_single_object_on_map(str(actual_key), target_def, gx, gy): made_change = True
        if made_change: self.map_content_changed.emit()
        self.editor_state.last_painted_tile_coords = (gx,gy)
    def _place_single_object_on_map(self, asset_key, asset_def, gx, gy) -> bool:
        wx, wy = float(gx*self.editor_state.grid_size), float(gy*self.editor_state.grid_size)
        game_id = asset_def.get("game_type_id", "unknown"); is_spawn = asset_def.get("category") == "spawn"
        if not is_spawn:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x")==int(wx) and obj.get("world_y")==int(wy) and obj.get("asset_editor_key")==asset_key:
                    if asset_def.get("colorable") and self.editor_state.current_selected_asset_paint_color and obj.get("override_color")!=self.editor_state.current_selected_asset_paint_color:
                        obj["override_color"] = self.editor_state.current_selected_asset_paint_color
                        item_id = id(obj); 
                        if item_id in self._map_object_items: self._map_object_items[item_id].update_visuals(new_color=QColor(*obj["override_color"]), editor_state=self.editor_state)
                        return True
                    return False
        new_obj_data = {"asset_editor_key":asset_key, "world_x":int(wx), "world_y":int(wy), "game_type_id":game_id, "properties":{}}
        if asset_def.get("colorable") and self.editor_state.current_selected_asset_paint_color: new_obj_data["override_color"] = self.editor_state.current_selected_asset_paint_color
        if game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: new_obj_data["properties"] = {k:v["default"] for k,v in ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_id].items()} # type: ignore
        if is_spawn:
            indices_rem = [i for i,obj in enumerate(self.editor_state.placed_objects) if obj.get("game_type_id")==game_id]
            for i in sorted(indices_rem, reverse=True):
                rem_obj = self.editor_state.placed_objects.pop(i); rem_id = id(rem_obj)
                if rem_id in self._map_object_items:
                    if self._map_object_items[rem_id].scene(): self.map_scene.removeItem(self._map_object_items[rem_id])
                    del self._map_object_items[rem_id]
        self.editor_state.placed_objects.append(new_obj_data)
        orig_w,orig_h = asset_def.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
        item_pix = get_asset_pixmap(asset_key, asset_def, QSize(orig_w,orig_h), new_obj_data.get("override_color"), get_native_size_only=True)
        if not item_pix or item_pix.isNull():
            if new_obj_data in self.editor_state.placed_objects: self.editor_state.placed_objects.remove(new_obj_data)
            return False
        map_obj_item = MapObjectItem(asset_key, game_id, item_pix, int(wx), int(wy), new_obj_data)
        self.map_scene.addItem(map_obj_item); self._map_object_items[id(new_obj_data)] = map_obj_item
        return True
    def _perform_erase_action(self, gx, gy, continuous=False, is_first=False):
        if continuous and (gx,gy)==self.editor_state.last_erased_tile_coords: return
        wx_snap, wy_snap = float(gx*self.editor_state.grid_size), float(gy*self.editor_state.grid_size)
        idx_rem = next((i for i,obj in reversed(list(enumerate(self.editor_state.placed_objects))) if obj.get("world_x")==int(wx_snap) and obj.get("world_y")==int(wy_snap)), None)
        if idx_rem is not None:
            if is_first: editor_history.push_undo_state(self.editor_state) # type: ignore
            obj_rem = self.editor_state.placed_objects.pop(idx_rem); item_id = id(obj_rem)
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene(): self.map_scene.removeItem(self._map_object_items[item_id])
                del self._map_object_items[item_id]
            self.map_content_changed.emit(); self.editor_state.last_erased_tile_coords=(gx,gy)
    def _perform_color_tile_action(self, gx, gy, continuous=False, is_first=False):
        if not self.editor_state.current_tile_paint_color: return
        if continuous and (gx,gy)==self.editor_state.last_colored_tile_coords: return
        wx_snap, wy_snap = float(gx*self.editor_state.grid_size), float(gy*self.editor_state.grid_size)
        colored_this_call = False
        for obj_data in reversed(self.editor_state.placed_objects):
            if obj_data.get("world_x")==int(wx_snap) and obj_data.get("world_y")==int(wy_snap):
                asset_key = str(obj_data.get("asset_editor_key")); asset_info = self.editor_state.assets_palette.get(asset_key)
                if asset_info and asset_info.get("colorable"):
                    new_color = self.editor_state.current_tile_paint_color
                    if obj_data.get("override_color") != new_color:
                        if is_first: editor_history.push_undo_state(self.editor_state) # type: ignore
                        obj_data["override_color"] = new_color; item_id = id(obj_data)
                        if item_id in self._map_object_items: self._map_object_items[item_id].update_visuals(new_color=QColor(*new_color), editor_state=self.editor_state)
                        colored_this_call = True; break
        if colored_this_call: self.map_content_changed.emit(); self.editor_state.last_colored_tile_coords=(gx,gy)
    def delete_selected_map_objects(self):
        sel_items = self.map_scene.selectedItems()
        if not sel_items: return
        editor_history.push_undo_state(self.editor_state) # type: ignore
        data_refs_rem = [item.map_object_data_ref for item in sel_items if isinstance(item,MapObjectItem)]
        self.editor_state.placed_objects = [obj for obj in self.editor_state.placed_objects if obj not in data_refs_rem]
        for data_ref in data_refs_rem:
            item_id = id(data_ref)
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene(): self.map_scene.removeItem(self._map_object_items.pop(item_id))
        self.map_scene.clearSelection(); self.map_content_changed.emit(); self.map_object_selected_for_properties.emit(None)
        if hasattr(self.parent_window,'show_status_message'): self.parent_window.show_status_message(f"Deleted {len(data_refs_rem)} object(s).") # type: ignore
    @Slot(str)
    def on_asset_selected(self, asset_key: Optional[str]):
        self.editor_state.selected_asset_editor_key = asset_key; self.current_tool = "place"; self._controller_tool_mode = "place"
        if asset_key and self.underMouse():
            scene_pos = self.mapToScene(self.mapFromGlobal(self.cursor().pos()))
            wx_snap, wy_snap = self.snap_to_grid(scene_pos.x(), scene_pos.y())
            self._update_hover_preview(wx_snap, wy_snap)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
    def _update_hover_preview(self, wx, wy):
        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key; asset_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_data and "q_pixmap_cursor" in asset_data:
                pix = asset_data["q_pixmap_cursor"]
                if pix and not pix.isNull():
                    if not self._hover_preview_item: self._hover_preview_item = QGraphicsPixmapItem(); self._hover_preview_item.setZValue(100); self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey()!=pix.cacheKey(): self._hover_preview_item.setPixmap(pix) # type: ignore
                    self._hover_preview_item.setPos(QPointF(wx,wy)); self._hover_preview_item.setVisible(True); return
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
    @Slot(str)
    def on_tool_selected(self, tool_key: str):
        self.editor_state.selected_asset_editor_key = None
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if tool_key=="tool_eraser": self.current_tool, self._controller_tool_mode, self.editor_state.current_tile_paint_color = "erase", "erase", None
        elif tool_key=="tool_tile_color_picker":
            self.current_tool, self._controller_tool_mode = "color_pick", "color_pick"
            if self.parent_window:
                init_c = self.editor_state.current_selected_asset_paint_color or self.editor_state.current_tile_paint_color or ED_CONFIG.C.BLUE # type: ignore
                new_q_color = QColorDialog.getColor(QColor(*init_c), self.parent_window, "Select Tile Paint Color")
                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None
                status_msg = f"Color Picker Tool: {self.editor_state.current_tile_paint_color or 'Cancelled'}"
                if hasattr(self.parent_window,'show_status_message'): self.parent_window.show_status_message(status_msg) # type: ignore
        elif tool_key=="platform_wall_gray_2x2_placer": self.current_tool,self._controller_tool_mode,self.editor_state.selected_asset_editor_key = "place","place",tool_key
        else: self.current_tool,self._controller_tool_mode,self.editor_state.current_tile_paint_color = "select","select",None
    @Slot(dict)
    def on_object_properties_changed(self, changed_obj_data_ref: Dict[str,Any]):
        map_item_found: Optional[MapObjectItem] = next((item for item in self._map_object_items.values() if item.map_object_data_ref is changed_obj_data_ref), None)
        if map_item_found:
            new_color_tuple = changed_obj_data_ref.get("override_color")
            map_item_found.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
        self.map_content_changed.emit()
    @Slot()
    def on_scene_selection_changed(self):
        sel_items = self.map_scene.selectedItems()
        if len(sel_items)==1 and isinstance(sel_items[0],MapObjectItem): self.map_object_selected_for_properties.emit(sel_items[0].map_object_data_ref)
        else: self.map_object_selected_for_properties.emit(None)

#################### END OF FILE: map_view_widget.py ####################