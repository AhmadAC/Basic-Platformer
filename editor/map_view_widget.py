#################### START OF FILE: editor\map_view_widget.py ####################

# editor/map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
Version 2.0.5 (Controller Navigation Foundations)
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
# MODIFIED: Import editor action constants from editor_actions.py
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                             ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY)


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
        # Change viewport background slightly when controller is active on map view
        # self.setStyleSheet("QGraphicsView { border: 2px solid lightblue; }")
        logger.debug("MapView: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self.editor_state.controller_mode_active = False
        if self._controller_cursor_item:
            self._controller_cursor_item.setVisible(False)
        # self.setStyleSheet("") # Reset style
        logger.debug("MapView: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus:
            return
        
        if self._controller_cursor_pos is None: 
            self._controller_cursor_pos = (self.editor_state.map_width_tiles // 2, self.editor_state.map_height_tiles // 2)

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
                self._perform_place_action(grid_x, grid_y, is_first_action=True) # Assume single press for now
            # Add other primary tool actions if any (e.g., select with controller)
        elif action == ACTION_MAP_TOOL_SECONDARY:
            logger.debug(f"MapView: Controller ACTION_MAP_TOOL_SECONDARY at ({grid_x},{grid_y})")
            self._perform_erase_action(grid_x, grid_y, is_first_action=True) # Assume single press
        elif action == ACTION_MAP_ZOOM_IN:
            self.zoom_in()
        elif action == ACTION_MAP_ZOOM_OUT:
            self.zoom_out()
        # ACTION_UI_ACCEPT could be used for selecting an existing object under the controller cursor
        elif action == ACTION_UI_ACCEPT:
            self._select_object_at_controller_cursor()


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
                break # Select the top-most if multiple overlap (based on internal order)
        
        self.map_scene.clearSelection()
        if found_item_to_select:
            found_item_to_select.setSelected(True)
            logger.info(f"MapView: Controller selected object '{found_item_to_select.editor_key}' at controller cursor.")
        else:
            logger.info(f"MapView: Controller accept pressed, no object at controller cursor.")
            # If no object, perhaps clear selection or other behavior
            self.map_object_selected_for_properties.emit(None)


    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        logger.debug(f"MapView: Received object_graphically_moved_signal for object data ID: {id(moved_object_data_ref)}. Emitting map_content_changed.")
        # This already implies an unsaved change, no need to push_undo_state here as itemChange does that effectively.
        self.map_content_changed.emit()

    def clear_scene(self):
        logger.debug("MapViewWidget: Clearing scene...")
        self.map_scene.blockSignals(True) # Avoid selectionChanged during clear
        items_to_remove = list(self.map_scene.items()) # Make a copy
        for item in items_to_remove:
            if item.scene() == self.map_scene: # Double check it's still there
                self.map_scene.removeItem(item)
                # If it's our special cursor, nullify the reference
                if item is self._controller_cursor_item: self._controller_cursor_item = None
                if item is self._hover_preview_item: self._hover_preview_item = None
        self.map_scene.blockSignals(False)
        self._grid_lines.clear()
        self._map_object_items.clear() # This holds MapObjectItem instances
        # _hover_preview_item and _controller_cursor_item are handled above
        self.update() # Request a repaint
        logger.debug("MapViewWidget: Scene cleared.")

    def load_map_from_state(self):
        logger.debug("MapViewWidget: Loading map from editor_state...")
        self.clear_scene() # Clears all items including controller cursor
        scene_w = float(self.editor_state.get_map_pixel_width())
        scene_h = float(self.editor_state.get_map_pixel_height())
        self.map_scene.setSceneRect(QRectF(0, 0, max(1.0, scene_w), max(1.0, scene_h)))
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)

        self.update_background_color(emit_view_changed=False) # Don't emit yet

        # Reset transform and apply saved state
        self.resetTransform() # Clears current transform
        current_transform = QTransform()
        # Note: PySide6 QTransform.translate uses positive values for right/down
        current_transform.translate(float(self.editor_state.camera_offset_x * -1), float(self.editor_state.camera_offset_y * -1))
        current_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(current_transform)

        self.update_grid_visibility(emit_view_changed=False) # Don't emit yet
        self.draw_placed_objects() # Redraws map objects

        # Re-initialize controller cursor if map view has focus
        if self._controller_has_focus:
            self._update_controller_cursor_visuals()

        logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}, Zoom: {self.editor_state.zoom_level:.2f}, Offset: ({self.editor_state.camera_offset_x:.1f}, {self.editor_state.camera_offset_y:.1f})")
        self.viewport().update() # Ensure viewport repaints with new content
        self.view_changed.emit() # Now emit view changed for minimap etc.


    def update_background_color(self, emit_view_changed=True):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        if emit_view_changed:
            self.view_changed.emit()

    def draw_grid(self):
        # Remove old grid lines
        for line in self._grid_lines:
            if line.scene() == self.map_scene: # Check if it's still in the scene
                self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.viewport().update() # Repaint to remove grid if it was visible
            return

        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0) # type: ignore # 0 for cosmetic pen
        pen.setCosmetic(True) 

        gs_float = float(self.editor_state.grid_size)
        scene_rect = self.map_scene.sceneRect()
        map_w_px = scene_rect.width()
        map_h_px = scene_rect.height()
        start_x = scene_rect.left()
        start_y = scene_rect.top()
        
        current_x_coord = start_x
        while current_x_coord <= start_x + map_w_px + 1e-6: 
            line = self.map_scene.addLine(float(current_x_coord), start_y, float(current_x_coord), start_y + map_h_px, pen)
            line.setZValue(-1) 
            self._grid_lines.append(line)
            if gs_float <= 1e-6: break 
            current_x_coord += gs_float

        current_y_coord = start_y
        while current_y_coord <= start_y + map_h_px + 1e-6:
            line = self.map_scene.addLine(start_x, float(current_y_coord), start_x + map_w_px, float(current_y_coord), pen)
            line.setZValue(-1)
            self._grid_lines.append(line)
            if gs_float <= 1e-6: break
            current_y_coord += gs_float
        self.viewport().update()


    def update_grid_visibility(self, emit_view_changed=True):
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible:
            return # No change needed
        if not is_visible and self._grid_lines: # Hide existing lines
            for line in self._grid_lines:
                line.setVisible(False)
        elif is_visible : # Show grid (implies drawing if not already drawn)
            self.draw_grid() # This will make new lines visible
        self.viewport().update()
        if emit_view_changed:
            self.view_changed.emit()


    def draw_placed_objects(self):
        # logger.debug("MapViewWidget: draw_placed_objects called.")
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        
        # Remove items from scene and _map_object_items if their data is no longer in editor_state
        items_to_remove_ids = [item_id for item_id in self._map_object_items if item_id not in current_data_ids]
        for item_id in items_to_remove_ids:
            if self._map_object_items[item_id].scene() == self.map_scene:
                self.map_scene.removeItem(self._map_object_items[item_id])
            del self._map_object_items[item_id]

        # Add or update items
        for obj_data in self.editor_state.placed_objects:
            item_data_id = id(obj_data) # Use memory ID of the data dict as key
            asset_key = str(obj_data.get("asset_editor_key",""))

            asset_info_from_palette = self.editor_state.assets_palette.get(asset_key)

            if not asset_info_from_palette: # Try to find by game_type_id as a fallback
                game_id_of_obj = obj_data.get("game_type_id")
                if game_id_of_obj:
                    found_fallback = False
                    for pal_key_iter, pal_data_iter in self.editor_state.assets_palette.items():
                        if pal_data_iter.get("game_type_id") == game_id_of_obj:
                            asset_info_from_palette = pal_data_iter
                            asset_key = pal_key_iter # Update asset_key to the one found in palette
                            logger.info(f"DrawPlaced (Fallback): Remapped loaded asset with game_type_id '{game_id_of_obj}' to palette key '{asset_key}'.")
                            # Update obj_data if you want this remapping to persist for this session's save
                            # obj_data["asset_editor_key"] = asset_key 
                            found_fallback = True
                            break
                    if not found_fallback:
                         logger.warning(f"DrawPlaced: Asset info for key '{obj_data.get('asset_editor_key')}' or game_type_id '{game_id_of_obj}' not found in palette state. Skipping object.")
                         continue
                else:
                    logger.warning(f"DrawPlaced: Asset info for key '{asset_key}' not found and no game_type_id. Skipping object.")
                    continue
            
            if not asset_info_from_palette: # Should not happen if fallback worked or initial key was good
                logger.error(f"DrawPlaced: CRITICAL - asset_info_from_palette is None for asset_key '{asset_key}'. This should not happen. Skipping.")
                continue

            original_w, original_h = asset_info_from_palette.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
            pixmap_to_draw = get_asset_pixmap(asset_key, asset_info_from_palette,
                                              QSize(original_w, original_h),
                                              obj_data.get("override_color"),
                                              get_native_size_only=True)

            if not pixmap_to_draw or pixmap_to_draw.isNull():
                logger.warning(f"DrawPlaced: Pixmap for asset '{asset_key}' is null. Object not drawn/updated.")
                continue

            world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
            if item_data_id in self._map_object_items: # Update existing QGraphicsItem
                map_obj_item = self._map_object_items[item_data_id]
                # Only update pixmap if it actually changed
                if map_obj_item.pixmap().cacheKey() != pixmap_to_draw.cacheKey():
                    map_obj_item.setPixmap(pixmap_to_draw)
                if map_obj_item.pos() != QPointF(world_x, world_y): # Update position if changed in data
                    map_obj_item.setPos(QPointF(world_x, world_y))
                # Ensure internal references are up-to-date (e.g., if asset_key was remapped)
                map_obj_item.editor_key = asset_key 
                map_obj_item.game_type_id = str(obj_data.get("game_type_id"))
                map_obj_item.map_object_data_ref = obj_data # Ensure it points to current data
            else: # Create new QGraphicsItem
                map_obj_item = MapObjectItem(asset_key, str(obj_data.get("game_type_id")), pixmap_to_draw, int(world_x), int(world_y), obj_data)
                self.map_scene.addItem(map_obj_item)
                self._map_object_items[item_data_id] = map_obj_item
        self.viewport().update()


    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
        return self.mapToScene(screen_pos_qpoint.toPoint()) # QPointF.toPoint() is fine
    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint)
        gs = self.editor_state.grid_size
        if gs <= 0: return (int(scene_pos.x()), int(scene_pos.y())) # Avoid division by zero
        grid_tx = int(scene_pos.x() // gs)
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
    def zoom_in(self):
        self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT) # type: ignore
        self.view_changed.emit()

    @Slot()
    def zoom_out(self):
        self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT) # type: ignore
        self.view_changed.emit()

    @Slot()
    def reset_zoom(self):
        view_center_scene = self.mapToScene(self.viewport().rect().center()) # Get current center in scene coords
        self.resetTransform() # Resets zoom to 1.0 and removes translation
        self.editor_state.camera_offset_x = 0.0 # Reset internal state
        self.editor_state.camera_offset_y = 0.0
        self.editor_state.zoom_level = 1.0
        self.translate(0,0) # No effect after resetTransform, but good practice
        self.centerOn(view_center_scene) # Re-center on the previous scene point
        # Update editor_state with new scrollbar values after centerOn
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
        self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
        self._emit_zoom_update_status()
        self.view_changed.emit()

    def scale_view(self, factor: float):
        current_zoom = self.transform().m11() # m11 is scaleX, m22 is scaleY
        new_zoom = current_zoom * factor
        if abs(current_zoom) < 1e-5 and factor < 1.0: return # Avoid issues with near-zero zoom
        
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL)) # type: ignore
        
        actual_factor_to_apply = clamped_zoom / current_zoom if abs(current_zoom) > 1e-5 else \
                                 (clamped_zoom if clamped_zoom > ED_CONFIG.MIN_ZOOM_LEVEL else 1.0) # type: ignore

        if abs(actual_factor_to_apply - 1.0) > 0.0001: # Only scale if factor is significant
            self.scale(actual_factor_to_apply, actual_factor_to_apply)
            self.editor_state.zoom_level = self.transform().m11() # Update state
            # Update camera offset based on scrollbar positions AFTER scaling
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
            self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self._emit_zoom_update_status()
            # self.view_changed is emitted by the calling public zoom methods

    def pan_view_by_scrollbars(self, dx_pixels: int, dy_pixels: int):
        h_bar = self.horizontalScrollBar(); v_bar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() + dx_pixels)
        v_bar.setValue(v_bar.value() + dy_pixels)
        self.editor_state.camera_offset_x = float(h_bar.value())
        self.editor_state.camera_offset_y = float(v_bar.value())
        self.view_changed.emit()

    def center_on_map_coords(self, map_coords_p_qpointf: QPointF):
        self.centerOn(map_coords_p_qpointf)
        # Update editor_state with new scrollbar values after centerOn
        self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
        self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
        self.editor_state.zoom_level = self.transform().m11() # Zoom might not change, but good to sync
        self.view_changed.emit()

    def get_visible_scene_rect(self) -> QRectF:
        # mapToScene with viewport().rect() gives the visible part of the scene in scene coordinates
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key(); modifiers = event.modifiers()
        pan_changed_by_key = False

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom_in(); event.accept(); return
            elif key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            elif key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return
        
        pan_pixel_step = int(ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND / 60.0); dx_pixels, dy_pixels = 0, 0 # type: ignore
        if key == Qt.Key.Key_A: dx_pixels = -pan_pixel_step; pan_changed_by_key = True
        elif key == Qt.Key.Key_D: dx_pixels = pan_pixel_step; pan_changed_by_key = True
        elif key == Qt.Key.Key_W: dy_pixels = -pan_pixel_step; pan_changed_by_key = True
        elif key == Qt.Key.Key_S and not (modifiers & Qt.KeyboardModifier.ControlModifier): 
            dy_pixels = pan_pixel_step; pan_changed_by_key = True

        if pan_changed_by_key:
            self.pan_view_by_scrollbars(dx_pixels, dy_pixels); event.accept(); return

        if key == Qt.Key.Key_Delete: self.delete_selected_map_objects(); event.accept(); return
        
        # Allow parent (EditorMainWindow) to handle other keys if this widget doesn't
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False # Reset flag
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_tx, grid_ty = self.screen_to_grid_coords(event.position())
        item_under_mouse = self.itemAt(event.position().toPoint()) # QPoint for itemAt

        logger.debug(f"MapView: mousePressEvent - Button: {event.button()}, Tool: '{self.current_tool}', "
                     f"Selected Asset: '{self.editor_state.selected_asset_editor_key}', "
                     f"Item under mouse: {type(item_under_mouse).__name__ if item_under_mouse else 'None'}, "
                     f"Grid Coords: ({grid_tx},{grid_ty})")

        if event.button() == Qt.MouseButton.LeftButton:
            if item_under_mouse and isinstance(item_under_mouse, MapObjectItem):
                logger.debug("MapView: Left click on MapObjectItem. Starting drag possibility.")
                self._is_dragging_map_object = True
                self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y'])
                super().mousePressEvent(event) # Let QGraphicsView handle selection/move start
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                logger.debug(f"MapView: Left click with 'place' tool. Calling _perform_place_action for grid ({grid_tx},{grid_ty}).")
                self._perform_place_action(grid_tx, grid_ty, is_first_action=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                logger.debug(f"MapView: Left click with 'color_pick' tool. Calling _perform_color_tile_action for grid ({grid_tx},{grid_ty}).")
                self._perform_color_tile_action(grid_tx, grid_ty, is_first_action=True)
            else: # Default left click with no tool action: RubberBandDrag for selection
                logger.debug("MapView: Left click, no specific tool action. Setting RubberBandDrag.")
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event) # Important for RubberBandDrag to work
        
        elif event.button() == Qt.MouseButton.RightButton:
            # Eraser tool or if no asset selected in place mode (implies erase)
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_under_mouse): # Don't erase if right-clicking an item
                logger.debug(f"MapView: Right click with 'erase' tool or empty 'place'. Calling _perform_erase_action for grid ({grid_tx},{grid_ty}).")
                self._perform_erase_action(grid_tx, grid_ty, is_first_action=True)
            else:
                logger.debug("MapView: Right click, no specific erase action. Passing to super.")
                super().mousePressEvent(event) # For context menu if any, or other default behaviors

        elif event.button() == Qt.MouseButton.MiddleButton:
            logger.debug("MapView: Middle mouse button pressed. Starting ScrollHandDrag.")
            self.middle_mouse_panning = True
            self.last_pan_point = event.globalPosition() # Use global position for panning delta
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept(); return # Consume the event

        # If not accepted by any of the above, pass to superclass
        if not event.isAccepted():
            logger.debug("MapView: mousePressEvent not accepted by custom logic. Passing to super().")
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        
        # Emit mouse moved signal for status bar update
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))

        # Update hover preview item for placing assets
        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key
            asset_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_data and "q_pixmap_cursor" in asset_data:
                pixmap = asset_data["q_pixmap_cursor"]
                if pixmap and not pixmap.isNull():
                    if not self._hover_preview_item:
                        self._hover_preview_item = QGraphicsPixmapItem()
                        self._hover_preview_item.setZValue(100) # Above grid, below controller cursor
                        self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): # type: ignore
                        self._hover_preview_item.setPixmap(pixmap) # type: ignore
                    self._hover_preview_item.setPos(QPointF(world_x_snapped, world_y_snapped))
                    self._hover_preview_item.setVisible(True)
                elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
            elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        elif self._hover_preview_item: # If not in place mode, hide hover item
            self._hover_preview_item.setVisible(False)

        # Handle actions based on mouse buttons pressed
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object:
                super().mouseMoveEvent(event) # Let QGraphicsView handle item dragging
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y, continuous=True)
            elif self.dragMode() == QGraphicsView.DragMode.RubberBandDrag:
                super().mouseMoveEvent(event) # For selection rect

        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key):
                self._perform_erase_action(grid_x, grid_y, continuous=True)

        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point
            self.last_pan_point = event.globalPosition()
            self.pan_view_by_scrollbars(int(-delta.x()), int(-delta.y()))
            event.accept(); return # Consume the event

        # Edge scrolling logic
        self._check_edge_scroll(event.position())

        if not event.isAccepted():
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False # Reset flag
            # Check if object actually moved from its original data coords before pushing undo
            item_dragged: Optional[MapObjectItem] = None
            if self.map_scene.selectedItems() and isinstance(self.map_scene.selectedItems()[0], MapObjectItem):
                item_dragged = self.map_scene.selectedItems()[0] # type: ignore
            
            if item_dragged and self._drag_start_data_coords:
                final_data_x = item_dragged.map_object_data_ref['world_x']
                final_data_y = item_dragged.map_object_data_ref['world_y']
                if self._drag_start_data_coords[0] != final_data_x or self._drag_start_data_coords[1] != final_data_y:
                    logger.debug(f"Object drag completed. Pushing undo for move from {self._drag_start_data_coords} to ({final_data_x},{final_data_y}).")
                    editor_history.push_undo_state(self.editor_state) # type: ignore
                    self.map_content_changed.emit() # Ensure state is saved
            self._drag_start_data_coords = None # Reset

        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag) # Revert from ScrollHandDrag
            self.unsetCursor()
            # Update camera state after panning
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
            self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            self.view_changed.emit() # For minimap
            event.accept(); return

        # Reset last action coords for continuous actions
        self.editor_state.last_painted_tile_coords = None
        self.editor_state.last_erased_tile_coords = None
        self.editor_state.last_colored_tile_coords = None
        
        # If RubberBandDrag was active, reset DragMode after mouse release
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: QFocusEvent): # QEnterEvent, but QFocusEvent is fine for type hint
        if not self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QFocusEvent): # QMouseEvent for leave, QFocusEvent ok
        if self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.stop()
        self._edge_scroll_dx = 0 # Reset scroll direction
        self._edge_scroll_dy = 0
        if self._hover_preview_item: # Hide hover preview when mouse leaves view
            self._hover_preview_item.setVisible(False)
        super().leaveEvent(event)

    def _check_edge_scroll(self, mouse_pos_viewport: QPointF):
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0
        zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS; view_rect = self.viewport().rect() # type: ignore
        
        if mouse_pos_viewport.x() < zone: self._edge_scroll_dx = -1
        elif mouse_pos_viewport.x() > view_rect.width() - zone: self._edge_scroll_dx = 1
        
        if mouse_pos_viewport.y() < zone: self._edge_scroll_dy = -1
        elif mouse_pos_viewport.y() > view_rect.height() - zone: self._edge_scroll_dy = 1
        
        should_be_active = (self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0)
        if should_be_active and not self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.start()
        elif not should_be_active and self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.stop()

    @Slot()
    def perform_edge_scroll(self):
        if self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0:
            amount_pixels = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0) # type: ignore
            self.pan_view_by_scrollbars(int(self._edge_scroll_dx * amount_pixels), int(self._edge_scroll_dy * amount_pixels))

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords:
            return # Avoid re-placing on same tile during mouse drag
        
        asset_key = self.editor_state.selected_asset_editor_key
        logger.debug(f"MapView (_perform_place_action): Palette AssetKey='{asset_key}', Grid=({grid_x},{grid_y}), FirstAction={is_first_action}, Continuous={continuous}")

        if not asset_key:
            logger.warning("MapView (_perform_place_action): No asset_key selected from palette. Cannot place.")
            return

        asset_data_from_palette = self.editor_state.assets_palette.get(str(asset_key))
        if not asset_data_from_palette:
            logger.error(f"MapView (_perform_place_action): Asset data for palette key '{asset_key}' not found in editor_state.assets_palette. Cannot place.")
            return

        # Handle tools like "2x2 placer" that place a different asset
        places_asset_key_value = asset_data_from_palette.get("places_asset_key")
        actual_asset_key_to_place = places_asset_key_value.strip() if places_asset_key_value and isinstance(places_asset_key_value, str) and places_asset_key_value.strip() else asset_key
        
        logger.debug(f"MapView (_perform_place_action): Resolved actual_asset_key_to_place: '{actual_asset_key_to_place}' (derived from palette key '{asset_key}')")

        target_asset_definition_for_placement = self.editor_state.assets_palette.get(str(actual_asset_key_to_place))
        if not target_asset_definition_for_placement:
            logger.error(f"MapView (_perform_place_action): Target asset definition for resolved key '{actual_asset_key_to_place}' not found in editor_state.assets_palette. Cannot place.")
            return

        made_change_in_stroke = False
        if is_first_action: # Only push undo for the beginning of a drag/click action
            logger.debug("MapView (_perform_place_action): First action in stroke, pushing undo state.")
            editor_history.push_undo_state(self.editor_state) # type: ignore

        # Special handling for 2x2 placer tool
        if asset_data_from_palette.get("places_asset_key") and asset_data_from_palette.get("icon_type") == "2x2_placer":
            logger.debug("MapView (_perform_place_action): Using 2x2 placer tool.")
            for r_off in range(2):
                for c_off in range(2):
                    if self._place_single_object_on_map(str(actual_asset_key_to_place), target_asset_definition_for_placement, grid_x + c_off, grid_y + r_off):
                        made_change_in_stroke = True
        else: # Standard single asset placement
            if self._place_single_object_on_map(str(actual_asset_key_to_place), target_asset_definition_for_placement, grid_x, grid_y):
                made_change_in_stroke = True

        if made_change_in_stroke:
            logger.debug("MapView (_perform_place_action): Change made, emitting map_content_changed.")
            self.map_content_changed.emit()
        self.editor_state.last_painted_tile_coords = (grid_x, grid_y) # For continuous drag optimization


    def _place_single_object_on_map(self, asset_to_place_key: str, asset_definition_for_placement: Dict, grid_x: int, grid_y: int) -> bool:
        world_x_float = float(grid_x * self.editor_state.grid_size)
        world_y_float = float(grid_y * self.editor_state.grid_size)
        game_id = asset_definition_for_placement.get("game_type_id", "unknown_game_id")
        is_spawn_type = asset_definition_for_placement.get("category") == "spawn"

        logger.debug(f"MapView (_place_single_object): Attempting to place '{asset_to_place_key}' (GameID: {game_id}) at grid ({grid_x},{grid_y}), world ({world_x_float},{world_y_float}). IsSpawn: {is_spawn_type}")

        # Prevent placing multiple non-spawn objects on the exact same tile with the same asset key
        # (unless it's a color update)
        if not is_spawn_type:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == int(world_x_float) and \
                   obj.get("world_y") == int(world_y_float) and \
                   obj.get("asset_editor_key") == asset_to_place_key:
                    # If asset is colorable and current paint color is different, update color instead of skipping
                    if asset_definition_for_placement.get("colorable") and \
                       self.editor_state.current_selected_asset_paint_color and \
                       obj.get("override_color") != self.editor_state.current_selected_asset_paint_color:
                        
                        obj["override_color"] = self.editor_state.current_selected_asset_paint_color
                        item_id = id(obj)
                        if item_id in self._map_object_items:
                            self._map_object_items[item_id].update_visuals(new_color=QColor(*obj["override_color"]), editor_state=self.editor_state)
                        logger.info(f"MapView (_place_single_object): Updated color of existing '{asset_to_place_key}' at ({grid_x},{grid_y}) to {obj['override_color']}.")
                        return True # A change was made (color update)
                    else:
                        logger.debug(f"MapView (_place_single_object): Identical object '{asset_to_place_key}' (or non-colorable update) already at ({grid_x},{grid_y}). Placement skipped.")
                        return False # No change made

        new_object_map_data: Dict[str, Any] = {
            "asset_editor_key": asset_to_place_key,
            "world_x": int(world_x_float),
            "world_y": int(world_y_float),
            "game_type_id": game_id,
            "properties": {} # Initialize properties
        }

        # Apply current paint color if asset is colorable
        if asset_definition_for_placement.get("colorable") and self.editor_state.current_selected_asset_paint_color:
            new_object_map_data["override_color"] = self.editor_state.current_selected_asset_paint_color

        # Populate default properties if defined in ED_CONFIG
        if game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: # type: ignore
            new_object_map_data["properties"] = {
                k: v_def["default"] for k, v_def in ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_id].items() # type: ignore
            }
        
        # If placing a spawn point, remove any existing spawn of the same game_type_id
        if is_spawn_type:
            indices_to_remove = [i for i, obj in enumerate(self.editor_state.placed_objects) if obj.get("game_type_id") == game_id]
            if indices_to_remove:
                logger.debug(f"MapView (_place_single_object): Removing {len(indices_to_remove)} existing spawn(s) of type '{game_id}'.")
            for i in sorted(indices_to_remove, reverse=True): # Remove from end to avoid index issues
                removed_obj_data = self.editor_state.placed_objects.pop(i)
                item_id_removed = id(removed_obj_data)
                if item_id_removed in self._map_object_items:
                    if self._map_object_items[item_id_removed].scene(): # Check if it's in scene
                        self.map_scene.removeItem(self._map_object_items[item_id_removed])
                    del self._map_object_items[item_id_removed] # Remove from our tracking dict

        self.editor_state.placed_objects.append(new_object_map_data)
        logger.debug(f"MapView (_place_single_object): Added object data to editor_state.placed_objects. New count: {len(self.editor_state.placed_objects)}")

        # Create and add the QGraphicsItem for the new object
        original_w, original_h = asset_definition_for_placement.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
        item_pixmap = get_asset_pixmap(asset_to_place_key, asset_definition_for_placement,
                                       QSize(original_w, original_h), # Pass QSize
                                       new_object_map_data.get("override_color"),
                                       get_native_size_only=True)

        if not item_pixmap or item_pixmap.isNull():
            logger.error(f"MapView (_place_single_object): FAILED to get valid pixmap for MapObjectItem '{asset_to_place_key}'. Pixmap is null. Cannot create scene item.")
            # Rollback: remove the data if pixmap fails (important)
            if new_object_map_data in self.editor_state.placed_objects:
                 self.editor_state.placed_objects.remove(new_object_map_data)
            return False

        logger.debug(f"MapView (_place_single_object): Got valid pixmap for MapObjectItem (Size: {item_pixmap.size()}). Creating and adding item to scene.")
        map_object_scene_item = MapObjectItem(asset_to_place_key, game_id, item_pixmap, int(world_x_float), int(world_y_float), new_object_map_data)
        self.map_scene.addItem(map_object_scene_item)
        self._map_object_items[id(new_object_map_data)] = map_object_scene_item # Track the new item

        logger.info(f"MapView: Placed '{asset_to_place_key}' at grid ({grid_x},{grid_y}) with color {new_object_map_data.get('override_color')}.")
        return True # Change was made


    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords:
            return # Avoid re-erasing same tile during drag
        
        world_x_snapped = float(grid_x * self.editor_state.grid_size)
        world_y_snapped = float(grid_y * self.editor_state.grid_size)
        
        item_data_index_to_remove: Optional[int] = None
        # Find the topmost object at this grid location
        for i, obj_data in reversed(list(enumerate(self.editor_state.placed_objects))):
            if obj_data.get("world_x") == int(world_x_snapped) and \
               obj_data.get("world_y") == int(world_y_snapped):
                item_data_index_to_remove = i
                break # Found an object to remove
        
        if item_data_index_to_remove is not None:
            if is_first_action: # Only push undo for the beginning of a drag/click action
                editor_history.push_undo_state(self.editor_state) # type: ignore
            
            obj_data_to_remove = self.editor_state.placed_objects.pop(item_data_index_to_remove)
            item_id = id(obj_data_to_remove) # Get ID of the removed data
            
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene(): # Check if it's in scene
                    self.map_scene.removeItem(self._map_object_items[item_id])
                del self._map_object_items[item_id] # Remove from our tracking dict
            
            self.map_content_changed.emit() # Notify that content changed
            self.editor_state.last_erased_tile_coords = (grid_x, grid_y) # For continuous drag optimization
            logger.info(f"MapView: Erased object at grid ({grid_x},{grid_y}).")

    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if not self.editor_state.current_tile_paint_color: # No color selected for this tool
            return
        if continuous and (grid_x, grid_y) == self.editor_state.last_colored_tile_coords:
            return # Avoid re-coloring same tile during drag

        world_x_snapped = float(grid_x * self.editor_state.grid_size)
        world_y_snapped = float(grid_y * self.editor_state.grid_size)
        colored_something_this_call = False

        # Iterate through objects to find one at the target location
        for obj_data in reversed(self.editor_state.placed_objects): # Iterate reversed to get topmost
            if obj_data.get("world_x") == int(world_x_snapped) and \
               obj_data.get("world_y") == int(world_y_snapped):
                
                asset_key = str(obj_data.get("asset_editor_key"))
                asset_info = self.editor_state.assets_palette.get(asset_key)
                
                if asset_info and asset_info.get("colorable"): # Check if the asset is colorable
                    new_color_tuple = self.editor_state.current_tile_paint_color
                    if obj_data.get("override_color") != new_color_tuple: # Only if color actually changes
                        if is_first_action: # Push undo state at start of action
                            editor_history.push_undo_state(self.editor_state) # type: ignore
                        
                        obj_data["override_color"] = new_color_tuple
                        item_id = id(obj_data)
                        if item_id in self._map_object_items:
                            self._map_object_items[item_id].update_visuals(new_color=QColor(*new_color_tuple), editor_state=self.editor_state)
                        colored_something_this_call = True
                        break # Colored one object, stop (topmost)
        
        if colored_something_this_call:
            self.map_content_changed.emit()
            self.editor_state.last_colored_tile_coords = (grid_x, grid_y) # For continuous drag
            logger.info(f"MapView (Color Picker Tool): Colored object at grid ({grid_x},{grid_y}) to {self.editor_state.current_tile_paint_color}.")


    def delete_selected_map_objects(self):
        selected_items = self.map_scene.selectedItems()
        if not selected_items:
            return
        
        logger.debug(f"MapView: delete_selected_map_objects - {len(selected_items)} items selected.")
        editor_history.push_undo_state(self.editor_state) # type: ignore # Save state before deletion
        
        data_refs_to_remove = [item.map_object_data_ref for item in selected_items if isinstance(item, MapObjectItem)]
        
        # Remove from editor_state.placed_objects
        self.editor_state.placed_objects = [
            obj for obj in self.editor_state.placed_objects if obj not in data_refs_to_remove
        ]
        
        # Remove from scene and tracking dictionary
        for item_data_ref in data_refs_to_remove:
            item_id = id(item_data_ref)
            if item_id in self._map_object_items:
                if self._map_object_items[item_id].scene():
                    self.map_scene.removeItem(self._map_object_items.pop(item_id))
        
        self.map_scene.clearSelection() # Clear selection in the scene
        self.map_content_changed.emit() # Notify content change
        self.map_object_selected_for_properties.emit(None) # Clear properties panel
        
        if hasattr(self.parent_window, 'show_status_message'): # type: ignore
            self.parent_window.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).") # type: ignore

    @Slot(str)
    def on_asset_selected(self, asset_editor_key: Optional[str]):
        logger.debug(f"MapView: on_asset_selected received key: '{asset_editor_key}'")
        self.editor_state.selected_asset_editor_key = asset_editor_key
        self.current_tool = "place" # Switch to place tool when an asset is selected
        self._controller_tool_mode = "place" # Sync controller tool mode

        # Update hover preview if mouse is over the view
        if asset_editor_key:
            # asset_data = self.editor_state.assets_palette.get(str(asset_editor_key))
            # asset_name_display = asset_data.get("name_in_palette", str(asset_editor_key)) if asset_data else str(asset_editor_key)
            if self.underMouse(): # Trigger a mouseMove to update hover preview
                 # QTimer.singleShot(0, lambda: self.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, self.mapFromGlobal(self.cursor().pos()), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)))
                 # Simpler way: just update the hover item directly if needed
                 scene_pos = self.mapToScene(self.mapFromGlobal(self.cursor().pos()))
                 world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
                 self._update_hover_preview(world_x_snapped, world_y_snapped)

        elif self._hover_preview_item: # No asset selected, hide hover preview
            self._hover_preview_item.setVisible(False)
        logger.debug(f"MapView: current_tool set to '{self.current_tool}', selected_asset_key in state: '{self.editor_state.selected_asset_editor_key}'")

    def _update_hover_preview(self, world_x: float, world_y: float):
        """Helper to update the mouse hover preview item."""
        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key
            asset_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_data and "q_pixmap_cursor" in asset_data:
                pixmap = asset_data["q_pixmap_cursor"]
                if pixmap and not pixmap.isNull():
                    if not self._hover_preview_item:
                        self._hover_preview_item = QGraphicsPixmapItem()
                        self._hover_preview_item.setZValue(100) 
                        self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): # type: ignore
                        self._hover_preview_item.setPixmap(pixmap) # type: ignore
                    self._hover_preview_item.setPos(QPointF(world_x, world_y))
                    self._hover_preview_item.setVisible(True)
                    return
        # If conditions not met, hide it
        if self._hover_preview_item:
            self._hover_preview_item.setVisible(False)


    @Slot(str)
    def on_tool_selected(self, tool_key: str):
        logger.debug(f"MapView: on_tool_selected received tool_key: '{tool_key}'")
        self.editor_state.selected_asset_editor_key = None # Clear asset selection when a tool is picked
        if self._hover_preview_item: # Hide asset hover preview
            self._hover_preview_item.setVisible(False)

        tool_data = self.editor_state.assets_palette.get(str(tool_key))
        # tool_name_for_status = tool_data.get("name_in_palette", tool_key.replace("tool_", "").replace("_", " ").title()) if tool_data else tool_key

        if tool_key == "tool_eraser":
            self.current_tool = "erase"
            self._controller_tool_mode = "erase"
            self.editor_state.current_tile_paint_color = None # Eraser doesn't use paint color
        elif tool_key == "tool_tile_color_picker":
            self.current_tool = "color_pick"
            self._controller_tool_mode = "color_pick"
            # Color selection dialog is modal and needs mouse/keyboard
            if self.parent_window: # Check if parent (EditorMainWindow) exists
                initial_c = self.editor_state.current_selected_asset_paint_color or \
                            self.editor_state.current_tile_paint_color or \
                            ED_CONFIG.C.BLUE # type: ignore
                current_q_color = QColor(*initial_c)
                new_q_color = QColorDialog.getColor(current_q_color, self.parent_window, "Select Tile Paint Color (for Color Picker Tool)")

                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None
                
                status_msg_color = f"Color Picker Tool paint: {self.editor_state.current_tile_paint_color}" if self.editor_state.current_tile_paint_color else "Color Picker Tool paint selection cancelled."
                if hasattr(self.parent_window, 'show_status_message'): # type: ignore
                    self.parent_window.show_status_message(status_msg_color) # type: ignore
        
        elif tool_key == "platform_wall_gray_2x2_placer": # This tool places an asset
            self.current_tool = "place"
            self._controller_tool_mode = "place"
            self.editor_state.selected_asset_editor_key = tool_key # Set this tool as the "asset" to place
            logger.debug(f"MapView: 2x2 Placer tool selected. Tool mode: '{self.current_tool}', Selected Key: '{tool_key}'")
        else: # Default to select tool if unknown
            self.current_tool = "select" # Generic select/pan tool
            self._controller_tool_mode = "select"
            self.editor_state.current_tile_paint_color = None
        
        logger.debug(f"MapView: current_tool set to '{self.current_tool}', controller tool mode: '{self._controller_tool_mode}'")


    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: Dict[str, Any]):
        # This slot is called when properties of an ALREADY PLACED object are changed
        # via the PropertiesEditor. We need to find the corresponding MapObjectItem and update its visuals.
        map_item_found: Optional[MapObjectItem] = None
        # Try to find by direct data reference identity first (most reliable)
        for item_candidate in self._map_object_items.values():
            if item_candidate.map_object_data_ref is changed_object_data_ref:
                map_item_found = item_candidate
                break

        if map_item_found:
            logger.debug(f"MapView: on_object_properties_changed - Found MapObjectItem by identity: {map_item_found.editor_key} (Data ID: {id(changed_object_data_ref)})")
            new_color_tuple = changed_object_data_ref.get("override_color")
            # Update visuals based on potentially new color or other properties that affect appearance
            # For now, primarily handles color change. More complex visual updates would go here.
            map_item_found.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
            logger.debug(f"MapView: Visuals updated for item {map_item_found.editor_key}")
        else:
            # Fallback: try to find by coordinates and key if identity match failed (should be rare)
            logger.warning(f"MapView: on_object_properties_changed - MapObjectItem for received data_ref (ID: {id(changed_object_data_ref)}) not found by identity in _map_object_items.")
            wx = changed_object_data_ref.get("world_x"); wy = changed_object_data_ref.get("world_y"); akey = changed_object_data_ref.get("asset_editor_key")
            if wx is not None and wy is not None and akey is not None:
                for item_candidate in self._map_object_items.values():
                    if item_candidate.map_object_data_ref.get("world_x") == wx and \
                       item_candidate.map_object_data_ref.get("world_y") == wy and \
                       item_candidate.map_object_data_ref.get("asset_editor_key") == akey:
                        logger.info(f"MapView: Found item by fallback coords/key: {akey}. Updating its visuals.")
                        # Crucially, update the item's internal data reference to the new one if it's different
                        # This ensures consistency if the properties panel modified a copy.
                        # However, the design intends for the properties panel to modify the original reference.
                        # For safety, we can re-assign if a full re-draw isn't done.
                        item_candidate.map_object_data_ref.update(changed_object_data_ref) # Update existing data ref
                        new_color_tuple = changed_object_data_ref.get("override_color")
                        item_candidate.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
                        map_item_found = item_candidate
                        break
            if not map_item_found:
                 logger.error(f"MapView: Still could not find item for property change after fallback. Data: {changed_object_data_ref}")
        
        self.map_content_changed.emit() # Signal that content (properties) changed

    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.map_scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], MapObjectItem):
            logger.debug(f"MapView: Scene selection changed. Selected 1 MapObjectItem: {selected_items[0].editor_key}")
            self.map_object_selected_for_properties.emit(selected_items[0].map_object_data_ref)
        else: # No selection or multiple selection
            logger.debug(f"MapView: Scene selection changed. Selection count: {len(selected_items)}. Emitting None for properties.")
            self.map_object_selected_for_properties.emit(None) # Clear properties panel

#################### END OF FILE: map_view_widget.py ####################