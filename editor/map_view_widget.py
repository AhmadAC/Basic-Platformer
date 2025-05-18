# map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

# --- PySide6.QtWidgets imports ---
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsItem, QColorDialog, QWidget
)
# --- PySide6.QtGui imports ---
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QTransform, QImage,
    QWheelEvent, QMouseEvent, QKeyEvent, QFocusEvent # QKeySequence (Not used in this file's current code)
)
# --- PySide6.QtCore imports ---
from PySide6.QtCore import Qt, Signal, Slot, QRectF, QPointF, QSize, QTimer

# --- Editor specific imports ---
import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history   # For undo/redo
try:
    from editor_assets import get_asset_pixmap
except ImportError:
    logging.basicConfig(level=logging.DEBUG) 
    logger_mv = logging.getLogger(__name__) 
    logger_mv.critical("map_view_widget.py: Failed to import get_asset_pixmap from editor_assets. Visuals may be incorrect.")
    def get_asset_pixmap(asset_editor_key: str, asset_data_entry: Dict[str, Any],
                         target_size: QSize, override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
        logger_mv.error(f"Dummy get_asset_pixmap called for {asset_editor_key}. editor_assets not imported correctly.")
        dummy_pix = QPixmap(target_size)
        dummy_pix.fill(Qt.GlobalColor.magenta)
        return dummy_pix

logger = logging.getLogger(__name__)

# --- Custom Graphics Items ---

class MapObjectItem(QGraphicsPixmapItem):
    """Represents a single placed object on the map scene."""
    def __init__(self, editor_key: str, game_type_id: str, pixmap: QPixmap,
                 world_x: int, world_y: int, map_object_data_ref: Dict[str, Any], parent: Optional[QGraphicsItem] = None):
        super().__init__(pixmap, parent)
        self.editor_key = editor_key
        self.game_type_id = game_type_id
        self.map_object_data_ref = map_object_data_ref
        self.setPos(QPointF(float(world_x), float(world_y)))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True) # If you add hover effects to the item itself
        self.initial_pixmap = pixmap

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected(): # Only snap if selected and moved by user
            new_pos = value # value is the new proposed QPointF position
            grid_size_prop = self.scene().property("grid_size")
            grid_size = grid_size_prop if isinstance(grid_size_prop, (int, float)) and grid_size_prop > 0 else ED_CONFIG.BASE_GRID_SIZE

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size
            
            current_data_x = self.map_object_data_ref.get('world_x')
            current_data_y = self.map_object_data_ref.get('world_y')

            if int(snapped_x) != current_data_x or int(snapped_y) != current_data_y:
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                
                # Emit signal that the underlying data has changed due to graphical move
                # This is important for the MapViewWidget to know when to push an undo state (on mouseRelease)
                if self.scene() and hasattr(self.scene().parent(), 'object_graphically_moved_signal'):
                    if isinstance(self.scene().parent(), MapViewWidget):
                        self.scene().parent().object_graphically_moved_signal.emit(self.map_object_data_ref)
            
            # Always return the snapped position for the graphical item during drag
            return QPointF(float(snapped_x), float(snapped_y))
        return super().itemChange(change, value)

    def update_visuals(self, new_pixmap: Optional[QPixmap] = None, new_color: Optional[QColor] = None, editor_state: Optional[EditorState] = None):
        if new_pixmap and not new_pixmap.isNull():
            self.setPixmap(new_pixmap)
            self.initial_pixmap = new_pixmap # Update base if the asset itself changes
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
                        self.setPixmap(self.initial_pixmap) # Fallback to initial if coloring fails
                except ImportError:
                     logger.error("Could not import get_asset_pixmap from editor_assets in MapObjectItem.update_visuals")
                except Exception as e:
                    logger.error(f"Error updating visual for {self.editor_key} with color {new_color.name()}: {e}", exc_info=True)
                    if self.initial_pixmap and not self.initial_pixmap.isNull(): self.setPixmap(self.initial_pixmap)
        elif self.initial_pixmap and not self.initial_pixmap.isNull(): # Reset to original if no specific update
             self.setPixmap(self.initial_pixmap)


# --- MapViewWidget ---
class MapViewWidget(QGraphicsView):
    mouse_moved_on_map = Signal(tuple)  # (world_x, world_y, tile_x, tile_y, zoom_level)
    map_object_selected_for_properties = Signal(object) # dict or None
    map_content_changed = Signal()
    object_graphically_moved_signal = Signal(dict) # Emitted by MapObjectItem when its data changes

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent

        self.map_scene = QGraphicsScene(self)
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.setScene(self.map_scene)
        self.object_graphically_moved_signal.connect(self._handle_internal_object_move_for_unsaved_changes)

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Override for pixel art
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False) # Override for pixel art

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._grid_lines: List[QGraphicsLineItem] = []
        self._map_object_items: Dict[int, MapObjectItem] = {}
        self._hover_preview_item: Optional[QGraphicsPixmapItem] = None

        self.current_tool = "place"
        self.middle_mouse_panning = False
        self.last_pan_point = QPointF() # For MMB panning
        self._is_dragging_map_object = False
        self._drag_start_data_coords: Optional[Tuple[int, int]] = None


        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(30) # Interval for edge scroll updates
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.load_map_from_state()

    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        """Triggers the unsaved changes flag when an item's data is modified by graphical move."""
        self.map_content_changed.emit()

    def clear_scene(self):
        self.map_scene.blockSignals(True)
        # Remove items safely
        items_to_remove = list(self.map_scene.items())
        for item in items_to_remove:
            self.map_scene.removeItem(item)
            # If it's a MapObjectItem, also remove from our tracking dict
            # This check is a bit indirect, better to clear _map_object_items explicitly
        self.map_scene.blockSignals(False)

        self._grid_lines.clear()
        self._map_object_items.clear()
        self._hover_preview_item = None # Was in scene, clear() removes it
        self.update()

    def load_map_from_state(self):
        logger.debug("MapViewWidget: Loading map from state...")
        self.clear_scene()

        scene_width = float(self.editor_state.get_map_pixel_width())
        scene_height = float(self.editor_state.get_map_pixel_height())
        self.map_scene.setSceneRect(QRectF(0, 0, scene_width if scene_width > 0 else 1.0, scene_height if scene_height > 0 else 1.0))
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.update_background_color() # Sets brush on scene

        # Restore camera transform
        self.resetTransform() # Important before applying new transform
        new_transform = QTransform()
        # camera_offset is the top-left of the *scene* that should be at top-left of *view*
        # So, translate the view's understanding of the scene by negative offset
        new_transform.translate(-self.editor_state.camera_offset_x, -self.editor_state.camera_offset_y)
        new_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(new_transform)

        self.update_grid_visibility() # Calls draw_grid if needed
        self.draw_placed_objects()
        # self.update() # Called by sub-functions
        logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}, Zoom: {self.editor_state.zoom_level}, Offset: ({self.editor_state.camera_offset_x}, {self.editor_state.camera_offset_y})")

    def update_background_color(self):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        # No need to call self.update() here, setBackgroundBrush triggers it.

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene: self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.update(); return

        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0)
        pen.setCosmetic(True)
        gs = self.editor_state.grid_size
        scene_rect = self.map_scene.sceneRect()
        map_w_px, map_h_px = scene_rect.width(), scene_rect.height()
        start_x, start_y = scene_rect.left(), scene_rect.top()

        for x_val in range(int(start_x), int(start_x + map_w_px) + 1, gs): # +1 to include edge if exact multiple
            x_coord = float(x_val)
            line = self.map_scene.addLine(x_coord, start_y, x_coord, start_y + map_h_px, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        for y_val in range(int(start_y), int(start_y + map_h_px) + 1, gs):
            y_coord = float(y_val)
            line = self.map_scene.addLine(start_x, y_coord, start_x + map_w_px, y_coord, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        # self.update() # Viewport update might be better after all items are added/changed

    def update_grid_visibility(self):
        is_visible = self.editor_state.show_grid
        # Check if grid needs to be (re)drawn or just visibility toggled
        if is_visible and not self._grid_lines:
            self.draw_grid() # This will create and make them visible
        else: # Grid lines exist or should not be visible
            for line in self._grid_lines:
                line.setVisible(is_visible)
        self.viewport().update() # More targeted update


    def draw_placed_objects(self):
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        items_to_remove_ids = []
        for item_data_id, q_item in list(self._map_object_items.items()):
            if item_data_id not in current_data_ids:
                items_to_remove_ids.append(item_data_id)
                self.map_scene.removeItem(q_item)
        for item_id in items_to_remove_ids: del self._map_object_items[item_id]

        for obj_data in self.editor_state.placed_objects:
            item_data_id = id(obj_data)
            asset_key = str(obj_data.get("asset_editor_key",""))
            asset_info = self.editor_state.assets_palette.get(asset_key)
            if not asset_info: continue

            original_w, original_h = asset_info.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE))
            pixmap_to_draw = None
            try:
                pixmap_to_draw = get_asset_pixmap(
                    asset_key, asset_info,
                    target_size=QSize(original_w, original_h),
                    override_color=obj_data.get("override_color")
                )
            except Exception as e: logger.error(f"Error getting pixmap for {asset_key}: {e}", exc_info=True)

            if not pixmap_to_draw or pixmap_to_draw.isNull():
                logger.warning(f"Pixmap for asset '{asset_key}' is null. Object not drawn/updated."); continue

            world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
            if item_data_id in self._map_object_items:
                map_obj_item = self._map_object_items[item_data_id]
                if map_obj_item.pixmap().cacheKey() != pixmap_to_draw.cacheKey(): map_obj_item.setPixmap(pixmap_to_draw)
                if map_obj_item.pos() != QPointF(world_x, world_y): map_obj_item.setPos(QPointF(world_x, world_y))
                map_obj_item.editor_key = asset_key # Update in case it changed (e.g. replace tool)
                map_obj_item.game_type_id = str(obj_data.get("game_type_id"))
            else:
                map_obj_item = MapObjectItem(
                    asset_key, str(obj_data.get("game_type_id")), pixmap_to_draw,
                    int(world_x), int(world_y), obj_data
                )
                self.map_scene.addItem(map_obj_item)
                self._map_object_items[item_data_id] = map_obj_item
        self.viewport().update()


    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
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
        """Helper to emit mouse_moved_on_map for status bar zoom update."""
        # Get current center of the view in scene coordinates
        viewport_center_point = self.viewport().rect().center()
        scene_center_point = self.mapToScene(viewport_center_point)
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
        self.resetTransform() # Reset to identity
        # Re-apply camera offset, but with zoom 1.0
        self.translate(self.editor_state.camera_offset_x * -1, self.editor_state.camera_offset_y * -1)
        self.editor_state.zoom_level = 1.0
        self._emit_zoom_update_status()


    def scale_view(self, factor: float):
        current_zoom = self.transform().m11()
        new_zoom = current_zoom * factor
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL))
        
        if abs(clamped_zoom - current_zoom) > 0.0001: # Only scale if there's a meaningful change
            actual_factor_to_apply = clamped_zoom / current_zoom if abs(current_zoom) > 0.00001 else (clamped_zoom / 1.0) # Avoid division by zero
            
            if abs(actual_factor_to_apply - 1.0) > 0.0001 :
                self.scale(actual_factor_to_apply, actual_factor_to_apply)
                self.editor_state.zoom_level = self.transform().m11()
                self._emit_zoom_update_status()


    def pan_view_by_scene_units(self, dx_scene: float, dy_scene: float):
        """Pans the view by a given amount in scene coordinates."""
        # We translate the scene relative to the view
        # A positive dx_scene means we want to see more to the right,
        # so the scene's content (and thus camera_offset_x) effectively decreases.
        # However, QGraphicsView.translate moves the *viewpoint*.
        # So if we want content to move left (viewpoint moves right), dx_scene is positive.
        self.translate(dx_scene, dy_scene) # This translates the view's transformation matrix

        # After translate, the origin of the scene relative to view's top-left has changed.
        # We need to update camera_offset to reflect the new top-left scene coordinate visible.
        # mapToScene(0,0) gives the scene coordinate at the view's top-left.
        topLeftScenePoint = self.mapToScene(QPointF(0.0,0.0).toPoint()) # QPoint for mapToScene
        self.editor_state.camera_offset_x = topLeftScenePoint.x()
        self.editor_state.camera_offset_y = topLeftScenePoint.y()


    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal: self.zoom_in(); event.accept(); return
            elif key == Qt.Key.Key_Minus: self.zoom_out(); event.accept(); return
            elif key == Qt.Key.Key_0: self.reset_zoom(); event.accept(); return

        pan_speed_scene = ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND
        # For key panning, the step should be in scene units to feel consistent regardless of zoom.
        # The QGraphicsView.translate() method works in scene units if the transform is identity,
        # or applies to the current transform.
        # Let's make pan_step directly in scene units.
        pan_step = pan_speed_scene / 60.0 # Approximate per-frame if updates were at 60Hz

        dx_scene, dy_scene = 0.0, 0.0
        if key == Qt.Key.Key_A: dx_scene = -pan_step
        elif key == Qt.Key.Key_D: dx_scene = pan_step
        elif key == Qt.Key.Key_W: dy_scene = -pan_step
        elif key == Qt.Key.Key_S and not (modifiers & Qt.KeyboardModifier.ControlModifier): dy_scene = pan_step

        if abs(dx_scene) > 0.001 or abs(dy_scene) > 0.001:
            # We want to move the *view* over the scene.
            # If user presses D (right), content should move left, so view point moves right.
            # Scrollbars are easier: positive dx means scrollbar value increases, content moves left.
            h_bar = self.horizontalScrollBar(); v_bar = self.verticalScrollBar()
            current_h_val = h_bar.value(); current_v_val = v_bar.value()
            # dx_scene is scene units. Scrollbar step is usually in pixels.
            # We need to convert scene pan step to scrollbar step.
            # A simple approximation:
            scrollbar_step_x = dx_scene * self.transform().m11() # Scale by zoom
            scrollbar_step_y = dy_scene * self.transform().m22()

            h_bar.setValue(current_h_val + int(scrollbar_step_x))
            v_bar.setValue(current_v_val + int(scrollbar_step_y))
            self.editor_state.camera_offset_x = float(h_bar.value())
            self.editor_state.camera_offset_y = float(v_bar.value())
            event.accept(); return
        
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
                # Store the data coordinates at the start of the drag
                self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y'])
                super().mousePressEvent(event) # Let QGraphicsView handle selection & initiate move
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y, is_first_action=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y, is_first_action=True)
            else: # Not clicking an item, and not a specific placement tool -> rubber band
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event)

        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_under_mouse):
                self._perform_erase_action(grid_x, grid_y, is_first_action=True)
            # Consider context menu here
            # super().mousePressEvent(event) # If you want default right-click behavior (e.g. for scene context menu)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True
            self.last_pan_point = event.globalPosition()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        
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
                        self._hover_preview_item = QGraphicsPixmapItem()
                        self._hover_preview_item.setZValue(100)
                        self.map_scene.addItem(self._hover_preview_item)
                    if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey():
                         self._hover_preview_item.setPixmap(pixmap)
                    self._hover_preview_item.setPos(QPointF(world_x_snapped, world_y_snapped))
                    self._hover_preview_item.setVisible(True)
                elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
            elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object: super().mouseMoveEvent(event)
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y, continuous=True)
        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key):
                self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.globalPosition() - self.last_pan_point
            self.last_pan_point = event.globalPosition()
            h_bar, v_bar = self.horizontalScrollBar(), self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            self.editor_state.camera_offset_x = float(h_bar.value())
            self.editor_state.camera_offset_y = float(v_bar.value())
            event.accept(); return
        
        self._check_edge_scroll(event.position())
        if not event.isAccepted(): super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False
            # Item's position in map_object_data_ref was updated by MapObjectItem.itemChange
            # Now, check if the final data position is different from the start of the drag.
            item = self.itemAt(event.position().toPoint()) # Re-check item, could be None if dragged off
            if isinstance(item, MapObjectItem):
                final_data_x = item.map_object_data_ref['world_x']
                final_data_y = item.map_object_data_ref['world_y']
                if self._drag_start_data_coords and \
                   (self._drag_start_data_coords[0] != final_data_x or \
                    self._drag_start_data_coords[1] != final_data_y):
                    logger.debug(f"Object drag finished. Data changed. Pushing undo.")
                    editor_history.push_undo_state(self.editor_state)
                    self.map_content_changed.emit() # Signal for unsaved changes, title update etc.
            self._drag_start_data_coords = None


        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.unsetCursor()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value())
            self.editor_state.camera_offset_y = float(self.verticalScrollBar().value())
            event.accept()
            return

        self.editor_state.last_painted_tile_coords = None
        self.editor_state.last_erased_tile_coords = None
        self.editor_state.last_colored_tile_coords = None
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
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
            amount_scene = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0)
            # For edge scroll, we want to pan by scene units, not screen pixels directly affecting scrollbars
            self.pan_view_by_scene_units(self._edge_scroll_dx * amount_scene, self._edge_scroll_dy * amount_scene)


    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords: return
        asset_key = self.editor_state.selected_asset_editor_key
        if not asset_key: return
        asset_data = self.editor_state.assets_palette.get(str(asset_key))
        if not asset_data: return
        actual_asset_key = asset_data.get("places_asset_key", asset_key)
        target_asset_data = self.editor_state.assets_palette.get(str(actual_asset_key))
        if not target_asset_data: return
        
        made_change_in_stroke = False
        if is_first_action and not continuous: editor_history.push_undo_state(self.editor_state)

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
        world_x, world_y = float(grid_x * self.editor_state.grid_size), float(grid_y * self.editor_state.grid_size)
        game_id = asset_data_for_placement.get("game_type_id", "unknown_game_id")
        is_spawn = asset_data_for_placement.get("category") == "spawn"

        if not is_spawn:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == int(world_x) and obj.get("world_y") == int(world_y) and obj.get("game_type_id") == game_id:
                    return False

        temp_new_object_data = {
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
            return True
        return False


    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size)
        world_y_snapped = float(grid_y * self.editor_state.grid_size)
        
        item_data_index_to_remove: Optional[int] = None
        for i, obj_data in reversed(list(enumerate(self.editor_state.placed_objects))):
            if obj_data.get("world_x") == int(world_x_snapped) and obj_data.get("world_y") == int(world_y_snapped):
                item_data_index_to_remove = i; break
        
        if item_data_index_to_remove is not None:
            if is_first_action and not continuous: editor_history.push_undo_state(self.editor_state)
            obj_data_to_remove = self.editor_state.placed_objects.pop(item_data_index_to_remove)
            item_id = id(obj_data_to_remove)
            if item_id in self._map_object_items:
                self.map_scene.removeItem(self._map_object_items.pop(item_id))
            self.map_content_changed.emit()
            self.editor_state.last_erased_tile_coords = (grid_x, grid_y)


    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
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
                        if is_first_action and not continuous: editor_history.push_undo_state(self.editor_state)
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
        item_id = id(changed_object_data_ref)
        if item_id in self._map_object_items:
            map_item = self._map_object_items[item_id]
            new_color_tuple = changed_object_data_ref.get("override_color")
            map_item.update_visuals(new_color=QColor(*new_color_tuple) if new_color_tuple else None, editor_state=self.editor_state)
        self.map_content_changed.emit()

    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.map_scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], MapObjectItem):
            self.map_object_selected_for_properties.emit(selected_items[0].map_object_data_ref)
        else:
            self.map_object_selected_for_properties.emit(None) # Emit None for dict type hint compatibility