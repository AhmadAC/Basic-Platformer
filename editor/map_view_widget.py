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
    QWheelEvent, QMouseEvent, QKeyEvent, QFocusEvent # QKeySequence (Not directly used in this file's current code)
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
    # Initialize logger here if it's the first point of use in this module
    # However, logger is typically configured once in the main application entry point.
    # For this structure, assume logger is configured in editor.py and available.
    # If running this file standalone for testing, you'd need a basicConfig here.
    logging.basicConfig(level=logging.DEBUG) # Basic config for standalone if needed
    logger_mv = logging.getLogger(__name__) # Use a local logger instance
    logger_mv.critical("map_view_widget.py: Failed to import get_asset_pixmap from editor_assets. Visuals may be incorrect.")
    def get_asset_pixmap(asset_editor_key: str, asset_data_entry: Dict[str, Any],
                         target_size: QSize, override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
        logger_mv.error(f"Dummy get_asset_pixmap called for {asset_editor_key}. editor_assets not imported correctly.")
        # Create a minimal QPixmap to avoid None return if possible, though it won't be correct.
        dummy_pix = QPixmap(target_size)
        dummy_pix.fill(Qt.GlobalColor.magenta)
        return dummy_pix

logger = logging.getLogger(__name__) # Main logger for the rest of the module

# --- Custom Graphics Items ---

class MapObjectItem(QGraphicsPixmapItem):
    """Represents a single placed object on the map scene."""
    def __init__(self, editor_key: str, game_type_id: str, pixmap: QPixmap,
                 world_x: int, world_y: int, map_object_data_ref: Dict, parent: Optional[QGraphicsItem] = None):
        super().__init__(pixmap, parent)
        self.editor_key = editor_key
        self.game_type_id = game_type_id
        self.map_object_data_ref = map_object_data_ref
        self.setPos(QPointF(float(world_x), float(world_y)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        self.initial_pixmap = pixmap

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            new_pos = self.pos()
            grid_size_prop = self.scene().property("grid_size")
            grid_size = grid_size_prop if isinstance(grid_size_prop, (int, float)) and grid_size_prop > 0 else ED_CONFIG.BASE_GRID_SIZE

            snapped_x = round(new_pos.x() / grid_size) * grid_size
            snapped_y = round(new_pos.y() / grid_size) * grid_size

            if snapped_x != self.map_object_data_ref.get('world_x') or \
               snapped_y != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x)
                self.map_object_data_ref['world_y'] = int(snapped_y)
                if self.scene() and hasattr(self.scene().parent(), 'object_graphically_moved_signal'):
                     if isinstance(self.scene().parent(), MapViewWidget): # Ensure parent is MapViewWidget
                         self.scene().parent().object_graphically_moved_signal.emit(self.map_object_data_ref)
                return QPointF(snapped_x, snapped_y)
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


# --- MapViewWidget ---
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
        self.object_graphically_moved_signal.connect(self._handle_internal_object_move)

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
        self._drag_start_scene_pos: Optional[QPointF] = None

        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(16)
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.load_map_from_state()

    @Slot(dict)
    def _handle_internal_object_move(self, moved_object_data_ref: dict):
        # This slot is called when a MapObjectItem's position has changed in the data_ref
        # After a drag operation (on mouseRelease), push to undo stack.
        # Here, we just signal that content changed for UI updates like unsaved status.
        self.map_content_changed.emit()


    def clear_scene(self):
        self.map_scene.clear()
        self._grid_lines.clear()
        self._map_object_items.clear()
        self._hover_preview_item = None
        self.update()

    def load_map_from_state(self):
        logger.debug("MapViewWidget: Loading map from state...")
        self.clear_scene()

        self.map_scene.setSceneRect(
            QRectF(0, 0,
                  float(self.editor_state.get_map_pixel_width()),
                  float(self.editor_state.get_map_pixel_height())
            )
        )
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))

        self.resetTransform() # Ensure transform is reset before applying new state
        # Apply existing camera offset and zoom from editor_state
        current_transform = QTransform()
        current_transform.translate(self.editor_state.camera_offset_x * -1, self.editor_state.camera_offset_y * -1)
        current_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(current_transform)

        self.update_grid_visibility()
        self.draw_placed_objects()
        self.update() # Request full repaint
        logger.debug(f"MapViewWidget: Map loaded. Scene rect: {self.map_scene.sceneRect()}")


    def update_background_color(self):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.update()

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene:
                 self.map_scene.removeItem(line)
        self._grid_lines.clear()

        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0:
            self.update()
            return

        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0)
        pen.setCosmetic(True)
        gs = self.editor_state.grid_size
        scene_rect = self.map_scene.sceneRect()
        map_w_px = scene_rect.width()
        map_h_px = scene_rect.height()
        start_x, start_y = scene_rect.left(), scene_rect.top()

        for x_coord in range(int(start_x), int(start_x + map_w_px) + gs, gs): # CORRECTED: Use gs as step
            line = self.map_scene.addLine(x_coord, start_y, x_coord, start_y + map_h_px, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        for y_coord in range(int(start_y), int(start_y + map_h_px) + gs, gs): # CORRECTED: Use gs as step
            line = self.map_scene.addLine(start_x, y_coord, start_x + map_w_px, y_coord, pen)
            line.setZValue(-1); self._grid_lines.append(line)
        self.update()

    def update_grid_visibility(self):
        is_visible = self.editor_state.show_grid
        if self._grid_lines and self._grid_lines[0].isVisible() == is_visible:
            return
        if not is_visible and self._grid_lines:
            for line in self._grid_lines: line.setVisible(False)
        elif is_visible:
            self.draw_grid()
            for line in self._grid_lines: line.setVisible(True) # Ensure visible after drawing
        self.update()

    def draw_placed_objects(self):
        # Clear existing graphical items first (handles if an object was removed from state)
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}
        items_to_remove_from_scene = []
        for item_data_id, q_item in list(self._map_object_items.items()): # Iterate copy for safe removal
            if item_data_id not in current_data_ids:
                items_to_remove_from_scene.append(q_item)
                del self._map_object_items[item_data_id]
        for q_item in items_to_remove_from_scene:
            self.map_scene.removeItem(q_item)

        # Add/update objects
        for obj_data in self.editor_state.placed_objects:
            item_data_id = id(obj_data)
            asset_key = obj_data.get("asset_editor_key")
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
            except Exception as e_get_pix: logger.error(f"Error in get_asset_pixmap for {asset_key}: {e_get_pix}")

            if not pixmap_to_draw or pixmap_to_draw.isNull():
                # Could add a placeholder error rect here if desired
                continue

            if item_data_id in self._map_object_items: # Update existing
                map_obj_item = self._map_object_items[item_data_id]
                map_obj_item.setPixmap(pixmap_to_draw) # Update pixmap (e.g. if color changed)
                map_obj_item.setPos(QPointF(float(obj_data["world_x"]), float(obj_data["world_y"])))
            else: # Add new
                map_obj_item = MapObjectItem(
                    asset_key, obj_data.get("game_type_id"), pixmap_to_draw,
                    obj_data["world_x"], obj_data["world_y"], obj_data
                )
                self.map_scene.addItem(map_obj_item)
                self._map_object_items[item_data_id] = map_obj_item
        self.update()


    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF:
        return self.mapToScene(screen_pos_qpoint.toPoint())

    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]:
        scene_pos = self.screen_to_scene_coords(screen_pos_qpoint)
        gs = self.editor_state.grid_size
        if gs <= 0: return (int(scene_pos.x()), int(scene_pos.y()))
        return int(scene_pos.x() // gs), int(scene_pos.y() // gs)

    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[int, int]:
        gs = self.editor_state.grid_size
        if gs <= 0: return int(world_x), int(world_y)
        return int(round(world_x / gs) * gs), int(round(world_y / gs) * gs)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = ED_CONFIG.ZOOM_FACTOR_INCREMENT if delta > 0 else ED_CONFIG.ZOOM_FACTOR_DECREMENT
            self.scale_view(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier: # Check for Control modifier
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
                self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT); event.accept(); return
            elif key == Qt.Key.Key_Minus:
                self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT); event.accept(); return
            elif key == Qt.Key.Key_0:
                 self.reset_zoom(); event.accept(); return

        pan_speed = ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND
        current_zoom = self.transform().m11()
        pan_step = pan_speed / (current_zoom * 60.0) if current_zoom > 0 else pan_speed / 60.0 # Account for zoom, ~60fps update rate
        
        dx, dy = 0.0, 0.0
        if key == Qt.Key.Key_A: dx = -pan_step
        elif key == Qt.Key.Key_D: dx = pan_step
        elif key == Qt.Key.Key_W: dy = -pan_step
        elif key == Qt.Key.Key_S and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            dy = pan_step

        if dx != 0 or dy != 0:
            self.pan_view(dx, dy); event.accept(); return
        
        if key == Qt.Key.Key_Delete:
            self.delete_selected_map_objects(); event.accept(); return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False # Reset flag
        self._drag_start_scene_pos = self.mapToScene(event.position().toPoint())

        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())

        item_at_pos = self.itemAt(event.position().toPoint()) # Check if clicking on an existing item

        if event.button() == Qt.MouseButton.LeftButton:
            if item_at_pos and isinstance(item_at_pos, MapObjectItem):
                self._is_dragging_map_object = True # Preparing for a potential drag
                # Let QGraphicsView handle selection and movement initiation
                super().mousePressEvent(event)
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y)
            else: # Not clicking an item, and not a specific placement tool
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event) # For rubber band selection

        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key and not item_at_pos):
                self._perform_erase_action(grid_x, grid_y)
            # Potentially add context menu here
            # super().mousePressEvent(event) # Allow context menu if implemented

        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True
            self.last_pan_point = event.position()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        
        if not event.isAccepted():
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())

        zoom = self.transform().m11()
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, zoom))

        if self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
            asset_key = self.editor_state.selected_asset_editor_key
            asset_data = self.editor_state.assets_palette.get(asset_key)
            if asset_data and "q_pixmap_cursor" in asset_data: # Check for pre-generated cursor pixmap
                pixmap = asset_data["q_pixmap_cursor"]
                if pixmap and not pixmap.isNull():
                    if not self._hover_preview_item:
                        self._hover_preview_item = QGraphicsPixmapItem()
                        self._hover_preview_item.setZValue(100) # High Z-value
                        self.map_scene.addItem(self._hover_preview_item)
                    
                    if self._hover_preview_item.pixmap() != pixmap:
                        self._hover_preview_item.setPixmap(pixmap)
                    
                    self._hover_preview_item.setPos(QPointF(float(world_x_snapped), float(world_y_snapped)))
                    self._hover_preview_item.setVisible(True)
                elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
            elif self._hover_preview_item: self._hover_preview_item.setVisible(False)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._is_dragging_map_object:
                super().mouseMoveEvent(event) # Let QGraphicsView handle item move
            elif self.current_tool == "place" and self.editor_state.selected_asset_editor_key:
                self._perform_place_action(grid_x, grid_y, continuous=True)
            elif self.current_tool == "color_pick" and self.editor_state.current_tile_paint_color:
                self._perform_color_tile_action(grid_x, grid_y, continuous=True)
            # else let super handle rubber band drag if active
        elif event.buttons() == Qt.MouseButton.RightButton:
            if self.current_tool == "erase" or \
               (self.current_tool == "place" and not self.editor_state.selected_asset_editor_key):
                self._perform_erase_action(grid_x, grid_y, continuous=True)
        elif self.middle_mouse_panning and event.buttons() == Qt.MouseButton.MiddleButton:
            delta = event.position() - self.last_pan_point
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            self.last_pan_point = event.position()
            event.accept()
            return
        
        self._check_edge_scroll(event.position())
        if not event.isAccepted():
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            # Drag finished, check if the object's data actually changed due to snapping
            # The itemChange in MapObjectItem already updated the data_ref.
            # Now we decide if this constitutes an undo-able action.
            # It's tricky because itemChange is called many times.
            # A better approach: store start pos on press, compare on release.
            if self._drag_start_scene_pos and self.mapToScene(event.position().toPoint()) != self._drag_start_scene_pos:
                # Only push to undo if it actually moved significantly from start
                # The internal data in editor_state.placed_objects is already updated by MapObjectItem.itemChange
                item_at_pos = self.itemAt(event.position().toPoint())
                if isinstance(item_at_pos, MapObjectItem): # Ensure we have the item
                     # Check if its data coords match its current visual pos
                     snapped_x, snapped_y = self.snap_to_grid(item_at_pos.pos().x(), item_at_pos.pos().y())
                     if item_at_pos.map_object_data_ref['world_x'] != snapped_x or item_at_pos.map_object_data_ref['world_y'] != snapped_y:
                          # This should not happen if itemChange is working correctly
                          logger.warning("Mismatch between item visual pos and data pos after drag.")
                          item_at_pos.map_object_data_ref['world_x'] = snapped_x
                          item_at_pos.map_object_data_ref['world_y'] = snapped_y

                editor_history.push_undo_state(self.editor_state)
                self.map_content_changed.emit() # Signal unsaved changes
            self._is_dragging_map_object = False
            self._drag_start_scene_pos = None

        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.unsetCursor()
            event.accept()
            # Store camera offset after panning
            self.editor_state.camera_offset_x = self.horizontalScrollBar().value()
            self.editor_state.camera_offset_y = self.verticalScrollBar().value()
            return # Important to return if accepted

        # Reset continuous action trackers
        self.editor_state.last_painted_tile_coords = None
        self.editor_state.last_erased_tile_coords = None
        self.editor_state.last_colored_tile_coords = None
        
        # Reset drag mode if it was rubber band
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        super().mouseReleaseEvent(event)


    def enterEvent(self, event: QFocusEvent): # QEvent used by QWidget, QFocusEvent for focus
        if not self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QFocusEvent):
        if self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.stop()
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        super().leaveEvent(event)

    def _check_edge_scroll(self, mouse_pos_viewport: QPointF): # Expects QPointF
        self._edge_scroll_dx = 0
        self._edge_scroll_dy = 0
        zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS
        view_rect = self.viewport().rect() # This is QRect, use .width(), .height()

        if mouse_pos_viewport.x() < zone: self._edge_scroll_dx = -1
        elif mouse_pos_viewport.x() > view_rect.width() - zone: self._edge_scroll_dx = 1
        if mouse_pos_viewport.y() < zone: self._edge_scroll_dy = -1
        elif mouse_pos_viewport.y() > view_rect.height() - zone: self._edge_scroll_dy = 1
        
        # Restart timer if scroll needed and not active, stop if not needed and active
        if (self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0) and not self.edge_scroll_timer.isActive():
            self.edge_scroll_timer.start()
        elif (self._edge_scroll_dx == 0 and self._edge_scroll_dy == 0) and self.edge_scroll_timer.isActive():
             self.edge_scroll_timer.stop()


    @Slot()
    def perform_edge_scroll(self):
        if self._edge_scroll_dx != 0 or self._edge_scroll_dy != 0:
            # Panning speed should be independent of zoom for edge scroll feel
            # So, we don't divide by zoom here, amount is in screen pixels
            amount = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0)
            
            # Pan view directly using scrollbar values
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() + int(self._edge_scroll_dx * amount))
            v_bar.setValue(v_bar.value() + int(self._edge_scroll_dy * amount))

            # Update editor_state camera offsets
            self.editor_state.camera_offset_x = float(h_bar.value())
            self.editor_state.camera_offset_y = float(v_bar.value())

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords: return
        asset_key = self.editor_state.selected_asset_editor_key
        if not asset_key: return
        asset_data = self.editor_state.assets_palette.get(asset_key)
        if not asset_data: return
        actual_asset_key = asset_data.get("places_asset_key", asset_key)
        target_asset_data = self.editor_state.assets_palette.get(actual_asset_key)
        if not target_asset_data: return
        
        placed_this_call = False
        if asset_data.get("places_asset_key") and asset_data.get("icon_type") == "2x2_placer":
            for r_off in range(2):
                for c_off in range(2):
                    if self._place_single_object_on_map(actual_asset_key, target_asset_data, grid_x + c_off, grid_y + r_off):
                        placed_this_call = True
        else:
            if self._place_single_object_on_map(actual_asset_key, target_asset_data, grid_x, grid_y):
                placed_this_call = True
        
        if placed_this_call and not continuous: # Push undo only for the first click of a paint action
            editor_history.push_undo_state(self.editor_state)
        
        self.editor_state.last_painted_tile_coords = (grid_x, grid_y)

    def _place_single_object_on_map(self, asset_editor_key: str, asset_data_for_placement: Dict, grid_x: int, grid_y: int) -> bool:
        world_x, world_y = grid_x * self.editor_state.grid_size, grid_y * self.editor_state.grid_size
        game_id = asset_data_for_placement["game_type_id"]
        is_spawn = asset_data_for_placement.get("category") == "spawn"

        if not is_spawn:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == world_x and obj.get("world_y") == world_y and obj.get("game_type_id") == game_id:
                    return False # Duplicate

        temp_new_object_data = {
            "asset_editor_key": asset_editor_key, "world_x": int(world_x), "world_y": int(world_y), "game_type_id": game_id
        }
        if asset_data_for_placement.get("colorable") and self.editor_state.current_tile_paint_color:
            temp_new_object_data["override_color"] = self.editor_state.current_tile_paint_color
        if game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            temp_new_object_data["properties"] = {
                k: v["default"] for k, v in ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_id].items()
            }
        
        # If placing a spawn, remove existing of same type FIRST from state and scene
        if is_spawn:
            indices_to_remove = []
            for i, existing_obj_data in enumerate(self.editor_state.placed_objects):
                if existing_obj_data.get("game_type_id") == game_id:
                    indices_to_remove.append(i)
                    item_id = id(existing_obj_data)
                    if item_id in self._map_object_items:
                        self.map_scene.removeItem(self._map_object_items[item_id])
                        del self._map_object_items[item_id]
            for i in sorted(indices_to_remove, reverse=True):
                self.editor_state.placed_objects.pop(i)

        self.editor_state.placed_objects.append(temp_new_object_data)
        
        # Add to scene (visual representation)
        original_w, original_h = asset_data_for_placement.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size))
        pixmap = None
        try:
            pixmap = get_asset_pixmap(asset_editor_key, asset_data_for_placement,
                                      QSize(original_w, original_h),
                                      temp_new_object_data.get("override_color"))
        except Exception as e: logger.error(f"Error getting pixmap for placing {asset_editor_key}: {e}")

        if pixmap and not pixmap.isNull():
            map_obj_item = MapObjectItem(asset_editor_key, game_id, pixmap, int(world_x), int(world_y), temp_new_object_data)
            self.map_scene.addItem(map_obj_item)
            self._map_object_items[id(temp_new_object_data)] = map_obj_item
        
        self.map_content_changed.emit()
        return True


    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False):
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords: return

        world_x_snapped = grid_x * self.editor_state.grid_size
        world_y_snapped = grid_y * self.editor_state.grid_size
        
        # Find topmost item at this exact grid cell (more precise would be itemAt)
        # For simplicity, we check our data list.
        item_data_index_to_remove: Optional[int] = None
        for i, obj_data in reversed(list(enumerate(self.editor_state.placed_objects))):
            if obj_data.get("world_x") == world_x_snapped and obj_data.get("world_y") == world_y_snapped:
                item_data_index_to_remove = i
                break
        
        if item_data_index_to_remove is not None:
            if not continuous: editor_history.push_undo_state(self.editor_state)
            obj_data_to_remove = self.editor_state.placed_objects.pop(item_data_index_to_remove)
            item_id = id(obj_data_to_remove)
            if item_id in self._map_object_items:
                self.map_scene.removeItem(self._map_object_items[item_id])
                del self._map_object_items[item_id]
            self.map_content_changed.emit()
            self.editor_state.last_erased_tile_coords = (grid_x, grid_y)


    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False):
        if not self.editor_state.current_tile_paint_color: return
        if continuous and (grid_x, grid_y) == self.editor_state.last_colored_tile_coords: return

        world_x_snapped = grid_x * self.editor_state.grid_size
        world_y_snapped = grid_y * self.editor_state.grid_size
        
        colored_something_this_call = False
        for obj_data in reversed(self.editor_state.placed_objects):
            if obj_data.get("world_x") == world_x_snapped and obj_data.get("world_y") == world_y_snapped:
                asset_key = obj_data.get("asset_editor_key")
                asset_info = self.editor_state.assets_palette.get(asset_key)
                if asset_info and asset_info.get("colorable"):
                    new_color_tuple = self.editor_state.current_tile_paint_color
                    if obj_data.get("override_color") != new_color_tuple:
                        if not continuous or not self.editor_state.last_colored_tile_coords : # Push undo for first color action in a potential drag
                            editor_history.push_undo_state(self.editor_state)
                        obj_data["override_color"] = new_color_tuple
                        item_id = id(obj_data)
                        if item_id in self._map_object_items:
                            q_color = QColor(*new_color_tuple)
                            self._map_object_items[item_id].update_visuals(new_color=q_color, editor_state=self.editor_state)
                        colored_something_this_call = True
                    break 
        if colored_something_this_call:
            self.map_content_changed.emit()
            self.editor_state.last_colored_tile_coords = (grid_x, grid_y)

    def delete_selected_map_objects(self):
        selected_scene_items = self.map_scene.selectedItems()
        if not selected_scene_items: return

        editor_history.push_undo_state(self.editor_state)
        
        data_refs_to_remove = [item.map_object_data_ref for item in selected_scene_items if isinstance(item, MapObjectItem)]

        new_placed_objects = []
        for obj_data in self.editor_state.placed_objects:
            if obj_data not in data_refs_to_remove:
                new_placed_objects.append(obj_data)
            else: # Object is being removed, also remove its QGraphicsItem
                item_id = id(obj_data)
                if item_id in self._map_object_items:
                    self.map_scene.removeItem(self._map_object_items[item_id])
                    del self._map_object_items[item_id]
        
        self.editor_state.placed_objects = new_placed_objects
        self.map_scene.clearSelection() # Clear selection in the scene
        self.map_content_changed.emit()
        self.map_object_selected_for_properties.emit(None)
        if hasattr(self.parent_window, 'show_status_message'):
             self.parent_window.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).")


    @Slot(str)
    def on_asset_selected(self, asset_editor_key: Optional[str]):
        self.editor_state.selected_asset_editor_key = asset_editor_key
        self.editor_state.current_tile_paint_color = None
        if asset_editor_key:
            self.current_tool = "place"
            # Force a mouseMoveEvent to update hover preview if mouse is in view
            if self.underMouse():
                 QTimer.singleShot(0, lambda: self.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, self.mapFromGlobal(self.cursor().pos()), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)))

        else:
            self.current_tool = "select"
            if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        if hasattr(self.parent_window, 'show_status_message'):
            self.parent_window.show_status_message(f"Tool: {self.current_tool.capitalize()}")

    @Slot(str)
    def on_tool_selected(self, tool_key: str):
        self.editor_state.selected_asset_editor_key = None
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)

        if tool_key == "tool_eraser": self.current_tool = "erase"; self.editor_state.current_tile_paint_color = None
        elif tool_key == "tool_tile_color_picker":
            self.current_tool = "color_pick"
            if self.parent_window:
                current_q_color = QColor(*(self.editor_state.current_tile_paint_color or ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE))
                new_q_color = QColorDialog.getColor(current_q_color, self.parent_window, "Select Tile Paint Color")
                if new_q_color.isValid(): self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3]
                else: self.editor_state.current_tile_paint_color = None
                status_msg = f"Tile paint color: {self.editor_state.current_tile_paint_color}" if self.editor_state.current_tile_paint_color else "Tile paint color selection cancelled."
                self.parent_window.show_status_message(status_msg)
        else: self.current_tool = "select"; self.editor_state.current_tile_paint_color = None
        
        if hasattr(self.parent_window, 'show_status_message'):
            self.parent_window.show_status_message(f"Tool: {self.current_tool.capitalize()}")

    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: dict):
        item_id = id(changed_object_data_ref)
        if item_id in self._map_object_items:
            map_item = self._map_object_items[item_id]
            new_color_tuple = changed_object_data_ref.get("override_color")
            new_q_color = QColor(*new_color_tuple) if new_color_tuple else None
            map_item.update_visuals(new_color=new_q_color, editor_state=self.editor_state)
        self.map_content_changed.emit()

    @Slot()
    def on_scene_selection_changed(self):
        selected_items = self.map_scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], MapObjectItem):
            self.map_object_selected_for_properties.emit(selected_items[0].map_object_data_ref)
        else:
            self.map_object_selected_for_properties.emit(None)

    def scale_view(self, factor: float):
        current_zoom = self.transform().m11()
        new_zoom = current_zoom * factor
        clamped_zoom = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom, ED_CONFIG.MAX_ZOOM_LEVEL))
        actual_factor = clamped_zoom / current_zoom if current_zoom != 0 else 1.0

        if abs(actual_factor - 1.0) > 0.001 : # Only scale if there's a change
            self.scale(actual_factor, actual_factor)
            self.editor_state.zoom_level = self.transform().m11() # Update state
            # Update status bar with new zoom
            center_scene_pos = self.mapToScene(self.viewport().rect().center())
            grid_coords = self.screen_to_grid_coords(QPointF(self.viewport().rect().center().x(), self.viewport().rect().center().y()))
            self.mouse_moved_on_map.emit((center_scene_pos.x(), center_scene_pos.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))


    def reset_zoom(self):
        current_zoom = self.transform().m11()
        if abs(current_zoom - 1.0) > 0.001: # Only reset if not already 1.0
             if current_zoom == 0: return
             self.scale(1.0 / current_zoom, 1.0 / current_zoom)
             self.editor_state.zoom_level = 1.0
             # Update status bar
             center_scene_pos = self.mapToScene(self.viewport().rect().center())
             grid_coords = self.screen_to_grid_coords(QPointF(self.viewport().rect().center().x(), self.viewport().rect().center().y()))
             self.mouse_moved_on_map.emit((center_scene_pos.x(), center_scene_pos.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))


    def pan_view(self, dx: float, dy: float):
        # dx and dy are in scene units at current zoom=1.
        # QGraphicsView scrollbars work with pixel units of the scrollbar itself,
        # not directly with scene units if the scene is larger than the view.
        # A simpler way to pan by scene units is to translate the view's transform.
        # However, using scrollbars is often more conventional for QGraphicsView.
        # The values dx, dy are small, intended for key presses.
        
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        
        # Convert scene units dx, dy to scrollbar pixel units
        # This needs to account for the current zoom level
        # If dx, dy are already effectively screen pixels, then direct addition is fine.
        # If dx, dy are scene units (at zoom 1), need to scale them by current zoom
        # For now, assume dx, dy are small steps appropriate for scrollbar
        
        h_bar.setValue(h_bar.value() + int(dx))
        v_bar.setValue(v_bar.value() + int(dy))

        # Update editor_state camera offsets based on scrollbar values
        # This assumes camera_offset is top-left of visible scene rect
        # QGraphicsView scrollbars give the top-left of the visible portion of the scene.
        self.editor_state.camera_offset_x = float(h_bar.value())
        self.editor_state.camera_offset_y = float(v_bar.value())