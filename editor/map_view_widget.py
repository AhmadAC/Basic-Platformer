#################### START OF FILE: map_view_widget.py ####################

# editor/map_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widget for the Map View in the PySide6 Level Editor.
Version 2.2.5 (Selection Pane Hide/Lock Integration)
- Map items now respect "editor_hidden" and "editor_locked" flags from object data.
- Locked items are not movable or resizable/croppable.
"""
import logging
import os
import math # For rotation
from typing import Optional, Dict, Any, List, Tuple, cast

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsItem, QColorDialog, QWidget, QApplication, QStyleOptionGraphicsItem
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QTransform, QImage,
    QWheelEvent, QMouseEvent, QKeyEvent, QFocusEvent, QCursor, QContextMenuEvent, QHoverEvent,
    QPainterPath 
)
from PySide6.QtCore import Qt, Signal, Slot, QRectF, QPointF, QSizeF, QTimer

from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_history
from .editor_assets import get_asset_pixmap
from . import editor_map_utils
from .editor_custom_items import BaseResizableMapItem, CustomImageMapItem, TriggerSquareMapItem, \
                                 HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT, \
                                 HANDLE_MIDDLE_LEFT, HANDLE_MIDDLE_RIGHT, \
                                 HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT

from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                             ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY)


logger = logging.getLogger(__name__)

class StandardMapObjectItem(QGraphicsPixmapItem):
    def __init__(self, editor_key: str, game_type_id: str,
                 world_x: int, world_y: int, map_object_data_ref: Dict[str, Any],
                 editor_state_ref: EditorState,
                 parent: Optional[QGraphicsItem] = None):
        
        self.editor_key = editor_key
        self.game_type_id = game_type_id
        self.map_object_data_ref = map_object_data_ref
        self.editor_state_ref = editor_state_ref 

        self.is_procedural_tile = False
        self.procedural_color_tuple: Optional[Tuple[int,int,int]] = None 
        self.procedural_width: float = float(ED_CONFIG.TS) # type: ignore
        self.procedural_height: float = float(ED_CONFIG.TS) # type: ignore

        asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
        initial_pixmap = QPixmap() 

        if asset_info and asset_info.get("surface_params") and \
           asset_info.get("category") == "tile" and not asset_info.get("source_file"):
            self.is_procedural_tile = True
            params = asset_info["surface_params"]
            self.procedural_width = float(params[0])
            self.procedural_height = float(params[1])
            if "override_color" not in self.map_object_data_ref:
                self.procedural_color_tuple = params[2]
            else:
                self.procedural_color_tuple = self.map_object_data_ref["override_color"]
            super().__init__(parent) 
        else:
            self.is_procedural_tile = False
            if asset_info:
                original_w, original_h = asset_info.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
                pixmap = get_asset_pixmap(self.editor_key, asset_info, QSizeF(int(original_w), int(original_h)),
                                          self.map_object_data_ref.get("override_color"), 
                                          get_native_size_only=True,
                                          is_flipped_h=False, rotation=0) 
                if pixmap and not pixmap.isNull():
                    initial_pixmap = pixmap
                else:
                    logger.warning(f"StandardMapObjectItem: Null pixmap for {self.editor_key}")
                    initial_pixmap = QPixmap(int(original_w), int(original_h))
                    initial_pixmap.fill(Qt.GlobalColor.magenta)
            else: 
                initial_pixmap = QPixmap(ED_CONFIG.TS, ED_CONFIG.TS) # type: ignore
                initial_pixmap.fill(Qt.GlobalColor.cyan)
            super().__init__(initial_pixmap, parent)
        
        self.setPos(QPointF(float(world_x), float(world_y)))
        
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        current_flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        if not is_locked:
            current_flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlags(current_flags)
        
        self.setZValue(map_object_data_ref.get("layer_order", 0))
        self.setVisible(not map_object_data_ref.get("editor_hidden", False))
        
        self._apply_orientation_transform()


    def boundingRect(self) -> QRectF:
        if self.is_procedural_tile:
            return QRectF(0, 0, self.procedural_width, self.procedural_height)
        else:
            if self.pixmap() and not self.pixmap().isNull():
                return super().boundingRect()
            return QRectF(0,0, ED_CONFIG.TS, ED_CONFIG.TS) # type: ignore

    def _apply_orientation_transform(self):
        item_should_be_flipped = self.map_object_data_ref.get("is_flipped_h", False)
        rotation_angle = float(self.map_object_data_ref.get("rotation", 0))

        current_transform = QTransform() 
        
        rect = self.boundingRect() 
        center_x = rect.width() / 2.0
        center_y = rect.height() / 2.0

        current_transform.translate(center_x, center_y)
        if item_should_be_flipped:
            current_transform.scale(-1, 1)
        if rotation_angle != 0:
            current_transform.rotate(rotation_angle)
        current_transform.translate(-center_x, -center_y)
        
        self.setTransform(current_transform)


    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        if self.is_procedural_tile:
            painter.save()

            color_to_use = self.map_object_data_ref.get("override_color", self.procedural_color_tuple)
            if not color_to_use: 
                 asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
                 if asset_info and asset_info.get("surface_params"):
                     color_to_use = asset_info["surface_params"][2]
                 else:
                     color_to_use = ED_CONFIG.C.MAGENTA # type: ignore
            
            brush_color = QColor(*color_to_use) # type: ignore
            painter.setBrush(brush_color)
            
            pen_color = brush_color.darker(130) if brush_color.alpha() == 255 else Qt.GlobalColor.transparent
            painter.setPen(QPen(pen_color, 0.5)) 

            props = self.map_object_data_ref.get("properties", {})
            radius = float(props.get("corner_radius", 0))
            rect = self.boundingRect()

            if radius > 1: 
                path = QPainterPath()
                if props.get("round_top_left", False): 
                    path.moveTo(rect.topLeft() + QPointF(radius, 0))
                    path.arcTo(QRectF(rect.topLeft(), QSizeF(radius * 2, radius * 2)), 180, -90)
                else:
                    path.moveTo(rect.topLeft())
                
                path.lineTo(rect.topRight() - QPointF(radius if props.get("round_top_right", False) else 0, 0))
                if props.get("round_top_right", False):
                    path.arcTo(QRectF(rect.topRight() - QPointF(radius*2,0), QSizeF(radius * 2, radius * 2)), 90, -90)
                else:
                    path.lineTo(rect.topRight())

                path.lineTo(rect.bottomRight() - QPointF(0, radius if props.get("round_bottom_right", False) else 0))
                if props.get("round_bottom_right", False):
                    path.arcTo(QRectF(rect.bottomRight() - QPointF(radius*2,radius*2), QSizeF(radius * 2, radius * 2)), 0, -90)
                else:
                    path.lineTo(rect.bottomRight())

                path.lineTo(rect.bottomLeft() + QPointF(radius if props.get("round_bottom_left", False) else 0, 0))
                if props.get("round_bottom_left", False):
                     path.arcTo(QRectF(rect.bottomLeft() - QPointF(0,radius*2) , QSizeF(radius * 2, radius * 2)), -90, -90)
                else:
                    path.lineTo(rect.bottomLeft())
                path.closeSubpath()
                painter.drawPath(path)
            else:
                painter.drawRect(rect)
            
            painter.restore() 
        else:
            super().paint(painter, option, widget)


    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        
        if is_locked and change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            return self.pos() # Prevent movement if locked
        
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            if self.scene().property("is_actively_transforming_item") is True: 
                 return super().itemChange(change, value)

            new_pos: QPointF = value 
            grid_size = self.scene().property("grid_size") 
            grid_size = grid_size if isinstance(grid_size, (int, float)) and grid_size > 0 else ED_CONFIG.BASE_GRID_SIZE # type: ignore

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

    def update_visuals_from_data(self, editor_state: EditorState): 
        asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
        if not asset_info: return

        self.setVisible(not self.map_object_data_ref.get("editor_hidden", False))
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not is_locked)

        if not self.is_procedural_tile:
            original_w, original_h = asset_info.get("original_size_pixels", (self.pixmap().width(), self.pixmap().height()))
            new_pixmap = get_asset_pixmap(self.editor_key, asset_info,
                                          QSizeF(int(original_w), int(original_h)),
                                          self.map_object_data_ref.get("override_color"),
                                          get_native_size_only=True,
                                          is_flipped_h=False, rotation=0) 
            if new_pixmap and not new_pixmap.isNull():
                if self.pixmap().cacheKey() != new_pixmap.cacheKey(): 
                    self.prepareGeometryChange() 
                    self.setPixmap(new_pixmap)
            else: 
                fallback_pm = QPixmap(int(original_w), int(original_h))
                fallback_pm.fill(Qt.GlobalColor.magenta)
                self.prepareGeometryChange()
                self.setPixmap(fallback_pm)
        else:
            new_color = self.map_object_data_ref.get("override_color")
            if not new_color and asset_info.get("surface_params"):
                new_color = asset_info["surface_params"][2]
            
            needs_geom_change = False
            if asset_info.get("surface_params"):
                params = asset_info["surface_params"]
                new_pw = float(params[0])
                new_ph = float(params[1])
                if abs(self.procedural_width - new_pw) > 1e-3 or abs(self.procedural_height - new_ph) > 1e-3:
                    self.procedural_width = new_pw
                    self.procedural_height = new_ph
                    needs_geom_change = True
            
            if self.procedural_color_tuple != new_color or needs_geom_change:
                self.procedural_color_tuple = new_color
                if needs_geom_change: self.prepareGeometryChange()
                self.update() 

        self._apply_orientation_transform() 

        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z:
            self.setZValue(new_z)

        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y):
            self.setPos(new_pos_x, new_pos_y)


class MapViewWidget(QGraphicsView):
    mouse_moved_on_map = Signal(tuple)
    map_object_selected_for_properties = Signal(object) 
    map_content_changed = Signal()
    object_graphically_moved_signal = Signal(dict)
    view_changed = Signal()
    context_menu_requested_for_item = Signal(object, QPointF) 

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent

        self.map_scene = QGraphicsScene(self)
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.map_scene.setProperty("is_actively_transforming_item", False) 
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        self.setScene(self.map_scene)
        self.object_graphically_moved_signal.connect(self._handle_internal_object_move_for_unsaved_changes)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True) 
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True) 
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag) 

        self._grid_lines: List[QGraphicsLineItem] = []
        self._map_object_items: Dict[int, QGraphicsItem] = {} 
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
        self._crop_start_item_data: Optional[Dict[str, Any]] = None

        self.edge_scroll_timer = QTimer(self)
        self.edge_scroll_timer.setInterval(30)
        self.edge_scroll_timer.timeout.connect(self.perform_edge_scroll)
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.map_scene.selectionChanged.connect(self.on_scene_selection_changed)

        self._controller_has_focus = False
        self._controller_cursor_pos: Optional[Tuple[int, int]] = None
        self._controller_cursor_item: Optional[QGraphicsRectItem] = None 
        
        self.load_map_from_state()
        logger.debug("MapViewWidget initialized.")

    def _update_controller_cursor_visuals(self):
        if not self._controller_has_focus or self._controller_cursor_pos is None:
            if self._controller_cursor_item: self._controller_cursor_item.setVisible(False)
            return
        if not self._controller_cursor_item:
            self._controller_cursor_item = QGraphicsRectItem(); cursor_color = QColor(*ED_CONFIG.MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE) # type: ignore
            self._controller_cursor_item.setPen(QPen(cursor_color, 2)); self._controller_cursor_item.setBrush(QColor(cursor_color.red(), cursor_color.green(), cursor_color.blue(), cursor_color.alpha() // 2))
            self._controller_cursor_item.setZValue(200); self.map_scene.addItem(self._controller_cursor_item)
        grid_x, grid_y = self._controller_cursor_pos; gs = float(self.editor_state.grid_size)
        self._controller_cursor_item.setRect(grid_x * gs, grid_y * gs, gs, gs)
        self._controller_cursor_item.setVisible(True); self.ensureVisible(self._controller_cursor_item, 50, 50)

    def on_controller_focus_gained(self): self._controller_has_focus = True; self.editor_state.controller_mode_active = True; self._update_controller_cursor_visuals()
    def on_controller_focus_lost(self): self._controller_has_focus = False; self.editor_state.controller_mode_active = False; self._update_controller_cursor_visuals()

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus: return
        if self._controller_cursor_pos is None: self._controller_cursor_pos = (self.editor_state.map_width_tiles // 2, self.editor_state.map_height_tiles // 2)
        grid_x, grid_y = self._controller_cursor_pos; moved = False; pan_speed_tiles = 1
        if action == ACTION_UI_UP: grid_y = max(0, grid_y - pan_speed_tiles); moved = True
        elif action == ACTION_UI_DOWN: grid_y = min(self.editor_state.map_height_tiles - 1, grid_y + pan_speed_tiles); moved = True
        elif action == ACTION_UI_LEFT: grid_x = max(0, grid_x - pan_speed_tiles); moved = True
        elif action == ACTION_UI_RIGHT: grid_x = min(self.editor_state.map_width_tiles - 1, grid_x + pan_speed_tiles); moved = True
        elif action == ACTION_MAP_ZOOM_IN: self.zoom_in()
        elif action == ACTION_MAP_ZOOM_OUT: self.zoom_out()
        elif action == ACTION_MAP_TOOL_PRIMARY: 
            if self.editor_state.current_tool_mode == "select":
                self._select_object_at_controller_cursor()
            else: 
                self._perform_place_action(grid_x, grid_y, is_first_action=True)
        elif action == ACTION_MAP_TOOL_SECONDARY: 
             self._perform_erase_action(grid_x, grid_y, is_first_action=True)
        elif action == ACTION_UI_ACCEPT: 
            if self.editor_state.current_tool_mode == "select":
                self._select_object_at_controller_cursor()
            else:
                self._perform_place_action(grid_x, grid_y, is_first_action=True)
        if moved: self._controller_cursor_pos = (grid_x, grid_y); self._update_controller_cursor_visuals()

    def _select_object_at_controller_cursor(self):
        if not self._controller_cursor_pos: return
        grid_x, grid_y = self._controller_cursor_pos; world_x = grid_x * self.editor_state.grid_size; world_y = grid_y * self.editor_state.grid_size
        cursor_rect_scene = QRectF(world_x, world_y, float(self.editor_state.grid_size), float(self.editor_state.grid_size))
        items_at_cursor = self.map_scene.items(cursor_rect_scene, Qt.ItemSelectionMode.IntersectsItemShape)

        found_item_to_select: Optional[QGraphicsItem] = None
        for item in items_at_cursor:
            if isinstance(item, (StandardMapObjectItem, BaseResizableMapItem)):
                if not item.map_object_data_ref.get("editor_locked", False): 
                    found_item_to_select = item
                    break

        self.map_scene.clearSelection()
        if found_item_to_select:
            found_item_to_select.setSelected(True)
        else:
            self.map_object_selected_for_properties.emit(None)

    @Slot(dict)
    def _handle_internal_object_move_for_unsaved_changes(self, moved_object_data_ref: dict):
        self.map_content_changed.emit()

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
        self.clear_scene(); scene_w = float(self.editor_state.get_map_pixel_width()); scene_h = float(self.editor_state.get_map_pixel_height())
        self.map_scene.setSceneRect(QRectF(0, 0, max(1.0, scene_w), max(1.0, scene_h)))
        self.map_scene.setProperty("grid_size", self.editor_state.grid_size)
        self.update_background_color(emit_view_changed=False)
        self.resetTransform(); current_transform = QTransform()
        current_transform.translate(float(self.editor_state.camera_offset_x * -1), float(self.editor_state.camera_offset_y * -1))
        current_transform.scale(self.editor_state.zoom_level, self.editor_state.zoom_level)
        self.setTransform(current_transform)
        self.update_grid_visibility(emit_view_changed=False); self.draw_placed_objects()
        if self._controller_has_focus: self._update_controller_cursor_visuals()
        self.viewport().update(); self.view_changed.emit()

    def update_background_color(self, emit_view_changed=True):
        self.map_scene.setBackgroundBrush(QColor(*self.editor_state.background_color))
        if emit_view_changed: self.view_changed.emit()

    def draw_grid(self):
        for line in self._grid_lines:
            if line.scene() == self.map_scene: self.map_scene.removeItem(line)
        self._grid_lines.clear()
        if not self.editor_state.show_grid or self.editor_state.grid_size <= 0: self.viewport().update(); return
        pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_GRID_COLOR_TUPLE), 0); pen.setCosmetic(True)  # type: ignore
        gs_float = float(self.editor_state.grid_size); scene_rect = self.map_scene.sceneRect()
        map_w_px = scene_rect.width(); map_h_px = scene_rect.height(); start_x = scene_rect.left(); start_y = scene_rect.top()
        current_x_coord = start_x
        while current_x_coord <= start_x + map_w_px + 1e-6: line = self.map_scene.addLine(float(current_x_coord), start_y, float(current_x_coord), start_y + map_h_px, pen); line.setZValue(-100); self._grid_lines.append(line); current_x_coord += gs_float
        current_y_coord = start_y
        while current_y_coord <= start_y + map_h_px + 1e-6: line = self.map_scene.addLine(start_x, float(current_y_coord), start_x + map_w_px, float(current_y_coord), pen); line.setZValue(-100); self._grid_lines.append(line); current_y_coord += gs_float
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
        current_data_ids = {id(obj_data) for obj_data in self.editor_state.placed_objects}

        items_to_remove_ids = [item_id for item_id in self._map_object_items if item_id not in current_data_ids]
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
            item_data_id = id(obj_data)
            asset_key = str(obj_data.get("asset_editor_key",""))
            map_scene_item: Optional[QGraphicsItem] = None

            if item_data_id in self._map_object_items:
                map_scene_item = self._map_object_items[item_data_id]
                if hasattr(map_scene_item, 'map_object_data_ref'):
                    map_scene_item.map_object_data_ref = obj_data # type: ignore
                if hasattr(map_scene_item, 'update_visuals_from_data'):
                    map_scene_item.update_visuals_from_data(self.editor_state) # type: ignore
            else:
                world_x, world_y = float(obj_data["world_x"]), float(obj_data["world_y"])
                if asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY: # type: ignore
                    map_scene_item = CustomImageMapItem(obj_data, self.editor_state)
                elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY:  # type: ignore
                    map_scene_item = TriggerSquareMapItem(obj_data, self.editor_state)
                else:
                    map_scene_item = StandardMapObjectItem(asset_key, str(obj_data.get("game_type_id")),
                                                           int(world_x), int(world_y), obj_data, self.editor_state)
                if map_scene_item:
                    self.map_scene.addItem(map_scene_item)
                    self._map_object_items[item_data_id] = map_scene_item
            
            if map_scene_item: 
                map_scene_item.setVisible(not obj_data.get("editor_hidden", False))


            if isinstance(map_scene_item, BaseResizableMapItem) and map_scene_item.isSelected():
                map_scene_item.show_interaction_handles(True)

        self.viewport().update()

    def update_specific_object_visuals(self, map_object_data_ref: Dict[str, Any]):
        item_id = id(map_object_data_ref)
        if item_id in self._map_object_items:
            map_obj_item = self._map_object_items[item_id]
            if hasattr(map_obj_item, 'update_visuals_from_data'):
                map_obj_item.update_visuals_from_data(self.editor_state) # type: ignore
                self.viewport().update()
        else:
            logger.warning(f"Attempted to update visuals for non-tracked object data ID: {item_id}")

    def screen_to_scene_coords(self, screen_pos_qpoint: QPointF) -> QPointF: return self.mapToScene(screen_pos_qpoint.toPoint())
    def screen_to_grid_coords(self, screen_pos_qpoint: QPointF) -> Tuple[int, int]: scene_pos = self.screen_to_scene_coords(screen_pos_qpoint); gs = self.editor_state.grid_size; return (int(scene_pos.x() // gs), int(scene_pos.y() // gs)) if gs > 0 else (int(scene_pos.x()), int(scene_pos.y()))
    def snap_to_grid(self, world_x: float, world_y: float) -> Tuple[float, float]: gs = self.editor_state.grid_size; return (float(round(world_x / gs) * gs), float(round(world_y / gs) * gs)) if gs > 0 else (world_x,world_y)
    def _emit_zoom_update_status(self): vp_center = self.viewport().rect().center(); scene_center = self.mapToScene(vp_center); grid_coords = self.screen_to_grid_coords(QPointF(float(vp_center.x()), float(vp_center.y()))); self.mouse_moved_on_map.emit((scene_center.x(), scene_center.y(), grid_coords[0], grid_coords[1], self.editor_state.zoom_level))

    @Slot()
    def zoom_in(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_INCREMENT); self.view_changed.emit() # type: ignore
    @Slot()
    def zoom_out(self): self.scale_view(ED_CONFIG.ZOOM_FACTOR_DECREMENT); self.view_changed.emit() # type: ignore
    @Slot()
    def reset_zoom(self): center = self.mapToScene(self.viewport().rect().center()); self.resetTransform(); self.editor_state.camera_offset_x = 0.0; self.editor_state.camera_offset_y = 0.0; self.editor_state.zoom_level = 1.0; self.centerOn(center); self._emit_zoom_update_status(); self.view_changed.emit()

    def scale_view(self, factor: float):
        current_zoom_transform = self.transform().m11()
        if abs(current_zoom_transform) < 1e-5 and factor < 1.0 : return

        new_zoom_level_target = self.editor_state.zoom_level * factor
        clamped_new_zoom_target = max(ED_CONFIG.MIN_ZOOM_LEVEL, min(new_zoom_level_target, ED_CONFIG.MAX_ZOOM_LEVEL)) # type: ignore
        
        actual_factor_to_apply = clamped_new_zoom_target / self.editor_state.zoom_level if self.editor_state.zoom_level != 0 else clamped_new_zoom_target
        
        if abs(actual_factor_to_apply - 1.0) > 1e-5 :
            self.scale(actual_factor_to_apply, actual_factor_to_apply)
            self.editor_state.zoom_level = self.transform().m11() 
            self._emit_zoom_update_status()

    def pan_view_by_scrollbars(self, dx: int, dy: int): hbar=self.horizontalScrollBar();vbar=self.verticalScrollBar(); hbar.setValue(hbar.value()+dx); vbar.setValue(vbar.value()+dy); self.editor_state.camera_offset_x=float(hbar.value()); self.editor_state.camera_offset_y=float(vbar.value()); self.view_changed.emit()
    def center_on_map_coords(self, p:QPointF): self.centerOn(p); self.editor_state.camera_offset_x=float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y=float(self.verticalScrollBar().value()); self.view_changed.emit()
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

        if (self._is_resizing_item or self._is_cropping_item) and key == Qt.Key.Key_Escape:
            cancel_msg = "Resize cancelled." if self._is_resizing_item else "Crop cancelled."
            self._cancel_active_transform(cancel_msg); event.accept(); return

        if key == Qt.Key.Key_C and modifiers == Qt.KeyboardModifier.ShiftModifier:
            selected_items = self.map_scene.selectedItems()
            if len(selected_items) == 1 and isinstance(selected_items[0], CustomImageMapItem):
                item = cast(CustomImageMapItem, selected_items[0])
                if item.current_interaction_mode == "crop":
                    item.set_interaction_mode("resize")
                    self.show_status_message("Exited crop mode for selected image.")
                    if self._is_cropping_item and self._cropping_item_ref == item:
                        self._is_cropping_item = False; self._cropping_item_ref = None
                        self.map_scene.setProperty("is_actively_transforming_item", False)
                else:
                    item.set_interaction_mode("crop")
                    self.show_status_message("Crop mode enabled. Drag handles to crop.")
                event.accept()
                return
        
        if key == Qt.Key.Key_A and modifiers == Qt.KeyboardModifier.ControlModifier:
            self.map_scene.clearSelection()
            for item_id, map_item in self._map_object_items.items():
                if map_item.isVisible() and not map_item.map_object_data_ref.get("editor_locked", False): # type: ignore
                    map_item.setSelected(True)
            self.show_status_message("Selected all visible, unlocked objects.")
            event.accept()
            return

        if key == Qt.Key.Key_Delete and not (modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if self.map_scene.selectedItems():
                self.delete_selected_map_objects()
                event.accept()
                return

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
                self.zoom_in()
                event.accept()
                return
            if key == Qt.Key.Key_Minus:
                self.zoom_out()
                event.accept()
                return
            if key == Qt.Key.Key_0:
                self.reset_zoom()
                event.accept()
                return
        
        pan_amount = ED_CONFIG.KEY_PAN_SPEED_UNITS_PER_SECOND * (1.0 / ED_CONFIG.C.FPS) / self.editor_state.zoom_level # type: ignore
        pan_x, pan_y = 0, 0
        if key == Qt.Key.Key_Left: pan_x = -pan_amount
        elif key == Qt.Key.Key_Right: pan_x = pan_amount
        elif key == Qt.Key.Key_Up: pan_y = -pan_amount
        elif key == Qt.Key.Key_Down: pan_y = pan_amount
        if pan_x != 0 or pan_y != 0:
            self.pan_view_by_scrollbars(int(pan_x), int(pan_y))
            event.accept()
            return

        if not event.isAccepted():
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        modifiers = QApplication.keyboardModifiers()
        
        if self.editor_state.current_tool_mode == "place" and \
           self.editor_state.palette_current_asset_key and \
           not (modifiers & Qt.KeyboardModifier.ControlModifier) and \
           not (modifiers & Qt.KeyboardModifier.ShiftModifier): 

            current_base_asset_key = self.editor_state.palette_current_asset_key
            effective_placement_info = self.editor_state.get_current_placement_info()
            effective_asset_key_for_rules = effective_placement_info[0]
            
            status_msg_orientation = ""
            asset_palette_data = self.editor_state.assets_palette.get(str(current_base_asset_key))
            category = asset_palette_data.get("category", "unknown") if asset_palette_data else "unknown"

            is_rotatable_type = effective_asset_key_for_rules in ED_CONFIG.ROTATABLE_ASSET_KEYS # type: ignore
            is_flippable_type = category in ED_CONFIG.FLIPPABLE_ASSET_CATEGORIES or \
                                (current_base_asset_key is not None and current_base_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX)) or \
                                current_base_asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY # type: ignore

            delta = event.angleDelta().y()
            if delta == 0: 
                delta = event.angleDelta().x()

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
                    if current_base_asset_key and asset_palette_data:
                        asset_display_name = asset_palette_data.get("name_in_palette", current_base_asset_key)
                    self.show_status_message(f"{asset_display_name} preview: {status_msg_orientation}")
                    
                    scene_pos = self.mapToScene(event.position().toPoint()) 
                    world_x_s, world_y_s = self.snap_to_grid(scene_pos.x(), scene_pos.y())
                    self._update_hover_preview(world_x_s, world_y_s)
                event.accept()
                return 

        elif modifiers == Qt.KeyboardModifier.ControlModifier: # Zoom
            delta = event.angleDelta().y()
            if delta > 0: self.zoom_in()
            elif delta < 0: self.zoom_out()
            event.accept()
            return

        super().wheelEvent(event) 

    def mousePressEvent(self, event: QMouseEvent):
        self._is_dragging_map_object = False
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_tx, grid_ty = self.screen_to_grid_coords(event.position())
        items_under_mouse = self.items(event.position().toPoint())

        for item_candidate in items_under_mouse:
            if isinstance(item_candidate, QGraphicsRectItem) and \
               isinstance(item_candidate.parentItem(), BaseResizableMapItem):
                
                parent_map_item = cast(BaseResizableMapItem, item_candidate.parentItem())
                if parent_map_item.map_object_data_ref.get("editor_locked", False): 
                    event.accept() 
                    return

                if parent_map_item.isSelected() and item_candidate in parent_map_item.interaction_handles:
                    if event.button() == Qt.MouseButton.LeftButton:
                        try:
                            handle_index = parent_map_item.interaction_handles.index(item_candidate)
                            
                            if isinstance(parent_map_item, CustomImageMapItem) and parent_map_item.current_interaction_mode == "crop":
                                self._is_cropping_item = True; self._cropping_item_ref = parent_map_item
                                self._crop_handle_active = handle_index; self._crop_start_mouse_pos_scene = scene_pos
                                self._crop_start_item_data = {
                                    "world_x": parent_map_item.map_object_data_ref.get("world_x"),
                                    "world_y": parent_map_item.map_object_data_ref.get("world_y"),
                                    "current_width": parent_map_item.map_object_data_ref.get("current_width"),
                                    "current_height": parent_map_item.map_object_data_ref.get("current_height"),
                                    "crop_rect": parent_map_item.map_object_data_ref.get("crop_rect"),
                                    "original_width": parent_map_item.map_object_data_ref.get("original_width"),
                                    "original_height": parent_map_item.map_object_data_ref.get("original_height")
                                }
                                if self._crop_start_item_data["crop_rect"]:
                                    self._crop_start_item_data["crop_rect"] = self._crop_start_item_data["crop_rect"].copy()
                            else: 
                                self._is_resizing_item = True; self._resizing_item_ref = parent_map_item
                                self._resize_handle_active = handle_index; self._resize_start_mouse_pos_scene = scene_pos
                                self._resize_start_item_rect_scene = parent_map_item.sceneBoundingRect()

                            self.map_scene.setProperty("is_actively_transforming_item", True)
                            editor_history.push_undo_state(self.editor_state)
                            event.accept()
                            return
                        except ValueError: pass

        item_under_mouse: Optional[QGraphicsItem] = None
        for itm in items_under_mouse:
            if isinstance(itm, (StandardMapObjectItem, BaseResizableMapItem)):
                item_under_mouse = itm; break
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_resizing_item or self._is_cropping_item: return 
            
            if self.editor_state.current_tool_mode == "select":
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) 
                if item_under_mouse and hasattr(item_under_mouse, 'map_object_data_ref') and item_under_mouse.map_object_data_ref.get("editor_locked", False): # type: ignore
                    if not item_under_mouse.isSelected():
                        self.map_scene.clearSelection()
                        item_under_mouse.setSelected(True)
                    event.accept() # Accept the event to prevent rubber band drag from starting on a locked item
                    return
                # If not a locked item or no item, proceed with super call for selection/rubber band
                super().mousePressEvent(event)
            elif self.editor_state.current_tool_mode == "place":
                if self.editor_state.palette_current_asset_key:
                    self._perform_place_action(grid_tx, grid_ty, is_first_action=True)
            elif self.editor_state.current_tool_mode == "color_pick":
                if self.editor_state.current_tile_paint_color:
                     self._perform_color_tile_action(grid_tx, grid_ty, is_first_action=True)
            # If item is under mouse and not select tool, it might be draggable.
            elif item_under_mouse and isinstance(item_under_mouse, (StandardMapObjectItem, BaseResizableMapItem)):
                if hasattr(item_under_mouse, 'map_object_data_ref') and not item_under_mouse.map_object_data_ref.get("editor_locked", False): # type: ignore
                    self._is_dragging_map_object = True 
                    self._drag_start_data_coords = (item_under_mouse.map_object_data_ref['world_x'], item_under_mouse.map_object_data_ref['world_y']) # type: ignore
                    super().mousePressEvent(event) 
                else: 
                    event.accept() 
                    return
            else: # No specific tool action, allow rubber band if select tool was implied or no item under mouse
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event)
        
        elif event.button() == Qt.MouseButton.RightButton:
            if self.editor_state.current_tool_mode == "tool_eraser": 
                self._perform_erase_action(grid_tx, grid_ty, is_first_action=True)
            elif item_under_mouse and isinstance(item_under_mouse, (BaseResizableMapItem, StandardMapObjectItem)):
                data_ref = getattr(item_under_mouse, 'map_object_data_ref', None)
                if data_ref:
                    self.context_menu_requested_for_item.emit(data_ref, event.globalPosition())
                    event.accept()

        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_mouse_panning = True; self.last_pan_point = event.globalPosition();
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept(); return

        if not event.isAccepted(): super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        grid_x, grid_y = self.screen_to_grid_coords(event.position())
        world_x_snapped, world_y_snapped = self.snap_to_grid(scene_pos.x(), scene_pos.y())
        
        self.mouse_moved_on_map.emit((scene_pos.x(), scene_pos.y(), grid_x, grid_y, self.editor_state.zoom_level))

        if self._is_cropping_item and self._cropping_item_ref and self._crop_start_mouse_pos_scene and self._crop_start_item_data and self._crop_handle_active is not None:
            delta_scene = scene_pos - self._crop_start_mouse_pos_scene
            item_data_ref = self._cropping_item_ref.map_object_data_ref
            start_data = self._crop_start_item_data

            original_img_w = float(start_data.get("original_width", 1.0)) 
            original_img_h = float(start_data.get("original_height", 1.0))
            if original_img_w <= 0: original_img_w = 1.0
            if original_img_h <= 0: original_img_h = 1.0

            start_visual_x = float(start_data["world_x"])
            start_visual_y = float(start_data["world_y"])
            start_visual_w = float(start_data["current_width"])
            start_visual_h = float(start_data["current_height"])

            start_crop_x, start_crop_y, start_crop_w, start_crop_h = 0.0, 0.0, original_img_w, original_img_h
            if start_data["crop_rect"]: 
                start_crop_x = float(start_data["crop_rect"]["x"])
                start_crop_y = float(start_data["crop_rect"]["y"])
                start_crop_w = float(start_data["crop_rect"]["width"])
                start_crop_h = float(start_data["crop_rect"]["height"])
            
            if start_crop_w <= 0: start_crop_w = 1.0
            if start_crop_h <= 0: start_crop_h = 1.0

            scale_visual_to_crop_x = start_visual_w / start_crop_w if start_crop_w != 0 else 1.0
            scale_visual_to_crop_y = start_visual_h / start_crop_h if start_crop_h != 0 else 1.0
            
            new_visual_x, new_visual_y = start_visual_x, start_visual_y
            new_visual_w, new_visual_h = start_visual_w, start_visual_h
            new_crop_x, new_crop_y = start_crop_x, start_crop_y
            new_crop_w, new_crop_h = start_crop_w, start_crop_h
            
            delta_crop_equivalent_x = delta_scene.x() / scale_visual_to_crop_x if scale_visual_to_crop_x != 0 else 0
            delta_crop_equivalent_y = delta_scene.y() / scale_visual_to_crop_y if scale_visual_to_crop_y != 0 else 0

            if self._crop_handle_active in [HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT]:
                new_visual_y += delta_scene.y(); new_visual_h -= delta_scene.y()
                new_crop_y += delta_crop_equivalent_y; new_crop_h -= delta_crop_equivalent_y
            if self._crop_handle_active in [HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT]:
                new_visual_h += delta_scene.y()
                new_crop_h += delta_crop_equivalent_y
            if self._crop_handle_active in [HANDLE_TOP_LEFT, HANDLE_MIDDLE_LEFT, HANDLE_BOTTOM_LEFT]:
                new_visual_x += delta_scene.x(); new_visual_w -= delta_scene.x()
                new_crop_x += delta_crop_equivalent_x; new_crop_w -= delta_crop_equivalent_x
            if self._crop_handle_active in [HANDLE_TOP_RIGHT, HANDLE_MIDDLE_RIGHT, HANDLE_BOTTOM_RIGHT]:
                new_visual_w += delta_scene.x()
                new_crop_w += delta_crop_equivalent_x
            
            min_visual_dim = max(1.0, float(self.editor_state.grid_size) / 8.0)
            min_crop_dim_pixels = 1.0

            if new_visual_w < min_visual_dim: new_visual_w = min_visual_dim
            if new_visual_h < min_visual_dim: new_visual_h = min_visual_dim

            new_crop_w = max(min_crop_dim_pixels, new_crop_w)
            new_crop_h = max(min_crop_dim_pixels, new_crop_h)
            new_crop_x = max(0.0, min(new_crop_x, original_img_w - new_crop_w))
            new_crop_y = max(0.0, min(new_crop_y, original_img_h - new_crop_h))
            new_crop_w = min(new_crop_w, original_img_w - new_crop_x)
            new_crop_h = min(new_crop_h, original_img_h - new_crop_y)

            item_data_ref["world_x"] = int(round(new_visual_x))
            item_data_ref["world_y"] = int(round(new_visual_y))
            item_data_ref["current_width"] = int(round(new_visual_w))
            item_data_ref["current_height"] = int(round(new_visual_h))
            item_data_ref["crop_rect"] = {
                "x": int(round(new_crop_x)), "y": int(round(new_crop_y)),
                "width": int(round(new_crop_w)), "height": int(round(new_crop_h))
            }
            
            self._cropping_item_ref.update_visuals_from_data(self.editor_state)
            self.map_content_changed.emit()
            event.accept(); return

        elif self._is_resizing_item and self._resizing_item_ref and self._resize_start_mouse_pos_scene and self._resize_start_item_rect_scene and self._resize_handle_active is not None:
            delta_scene = scene_pos - self._resize_start_mouse_pos_scene
            current_item_rect_scene = QRectF(self._resize_start_item_rect_scene)
            new_x_s, new_y_s, new_w_s, new_h_s = current_item_rect_scene.x(), current_item_rect_scene.y(), current_item_rect_scene.width(), current_item_rect_scene.height()

            if self._resize_handle_active in [HANDLE_TOP_LEFT, HANDLE_TOP_MIDDLE, HANDLE_TOP_RIGHT]: new_y_s += delta_scene.y(); new_h_s -= delta_scene.y()
            if self._resize_handle_active in [HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM_MIDDLE, HANDLE_BOTTOM_RIGHT]: new_h_s += delta_scene.y()
            if self._resize_handle_active in [HANDLE_TOP_LEFT, HANDLE_MIDDLE_LEFT, HANDLE_BOTTOM_LEFT]: new_x_s += delta_scene.x(); new_w_s -= delta_scene.x()
            if self._resize_handle_active in [HANDLE_TOP_RIGHT, HANDLE_MIDDLE_RIGHT, HANDLE_BOTTOM_RIGHT]: new_w_s += delta_scene.x()

            min_dim_scene = float(self.editor_state.grid_size) / 2.0
            if new_w_s < min_dim_scene: new_w_s = min_dim_scene
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

            item_data_ref = self._resizing_item_ref.map_object_data_ref
            item_data_ref["world_x"] = int(round(new_x_s))
            item_data_ref["world_y"] = int(round(new_y_s))
            item_data_ref["current_width"] = int(round(new_w_s))
            item_data_ref["current_height"] = int(round(new_h_s))
            
            self._resizing_item_ref.update_visuals_from_data(self.editor_state)
            self.map_content_changed.emit()
            event.accept(); return

        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key:
            self._update_hover_preview(world_x_snapped, world_y_snapped)
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
            self.map_scene.setProperty("is_actively_transforming_item", False)
            QApplication.restoreOverrideCursor()
            item_transformed_ref = self._resizing_item_ref or self._cropping_item_ref
            if item_transformed_ref:
                self.map_content_changed.emit()
                status_msg = "Object resized." if self._is_resizing_item else "Image cropped."
                self.show_status_message(status_msg)
                self.map_object_selected_for_properties.emit(item_transformed_ref.map_object_data_ref)

            self._is_resizing_item = False; self._resizing_item_ref = None
            self._resize_handle_active = None; self._resize_start_item_rect_scene = None
            self._resize_start_mouse_pos_scene = None

            self._is_cropping_item = False; self._cropping_item_ref = None
            self._crop_handle_active = None; self._crop_start_item_data = None
            self._crop_start_mouse_pos_scene = None
            if event.button() == Qt.MouseButton.LeftButton: 
                event.accept(); return

        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging_map_object:
            self._is_dragging_map_object = False
            item_dragged: Optional[QGraphicsItem] = None
            if self.map_scene.selectedItems() and isinstance(self.map_scene.selectedItems()[0], (StandardMapObjectItem, BaseResizableMapItem)):
                item_dragged = self.map_scene.selectedItems()[0]
            if item_dragged and self._drag_start_data_coords and hasattr(item_dragged, 'map_object_data_ref'):
                item_data = item_dragged.map_object_data_ref # type: ignore
                if self._drag_start_data_coords[0] != item_data['world_x'] or self._drag_start_data_coords[1] != item_data['world_y']:
                    editor_history.push_undo_state(self.editor_state); self.map_content_changed.emit() # type: ignore
            self._drag_start_data_coords = None
        if event.button() == Qt.MouseButton.MiddleButton and self.middle_mouse_panning:
            self.middle_mouse_panning = False; self.setDragMode(QGraphicsView.DragMode.NoDrag); self.unsetCursor()
            self.editor_state.camera_offset_x = float(self.horizontalScrollBar().value()); self.editor_state.camera_offset_y = float(self.verticalScrollBar().value()); self.view_changed.emit(); event.accept(); return
        self.editor_state.last_painted_tile_coords = None; self.editor_state.last_erased_tile_coords = None; self.editor_state.last_colored_tile_coords = None
        if self.dragMode() == QGraphicsView.DragMode.RubberBandDrag: self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key:
             if not self.itemAt(event.pos()): 
                 event.accept()
                 return

        scene_pos = self.mapToScene(event.pos())
        item_under_mouse = self.itemAt(scene_pos.toPoint())

        if isinstance(item_under_mouse, BaseResizableMapItem):
            data_ref = getattr(item_under_mouse, 'map_object_data_ref', None)
            if data_ref:
                asset_key = data_ref.get("asset_editor_key")
                if asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY or asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY:  # type: ignore
                    self.context_menu_requested_for_item.emit(data_ref, event.globalPos())
                    event.accept()
                    return

        if not event.isAccepted():
            super().contextMenuEvent(event)

    def enterEvent(self, event: QHoverEvent):  # type: ignore
        if not self.edge_scroll_timer.isActive(): self.edge_scroll_timer.start()
        super().enterEvent(event) 
    def leaveEvent(self, event: QHoverEvent):  # type: ignore
        if self.edge_scroll_timer.isActive(): self.edge_scroll_timer.stop()
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)
        QApplication.restoreOverrideCursor()
        super().leaveEvent(event) 
    def _check_edge_scroll(self, mouse_pos_viewport: QPointF):
        self._edge_scroll_dx = 0; self._edge_scroll_dy = 0; zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS; view_rect = self.viewport().rect() # type: ignore
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
            amount_pixels = ED_CONFIG.EDGE_SCROLL_SPEED_UNITS_PER_SECOND * (self.edge_scroll_timer.interval() / 1000.0) # type: ignore
            self.pan_view_by_scrollbars(int(self._edge_scroll_dx * amount_pixels), int(self._edge_scroll_dy * amount_pixels))

    def _perform_place_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if self.editor_state.current_tool_mode != "place": return 
        if continuous and (grid_x, grid_y) == self.editor_state.last_painted_tile_coords: return
        
        effective_asset_key, is_flipped, rotation, _ = self.editor_state.get_current_placement_info()
        if not effective_asset_key: return
        
        asset_definition_for_placement = self.editor_state.assets_palette.get(effective_asset_key)
        if not asset_definition_for_placement:
            if effective_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): # type: ignore
                 filename = effective_asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1] # type: ignore
                 asset_definition_for_placement = {
                    "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, # type: ignore
                    "asset_editor_key": effective_asset_key, 
                    "source_file_path": f"Custom/{filename}", 
                    "colorable": False, "category": "custom"
                 }
            else:
                logger.error(f"Palette data for effective asset '{effective_asset_key}' not found for placement.")
                return

        made_change_in_stroke = False
        if is_first_action: editor_history.push_undo_state(self.editor_state) # type: ignore

        is_placer_tool = False
        if self.editor_state.palette_current_asset_key: 
            original_palette_asset_data = self.editor_state.assets_palette.get(self.editor_state.palette_current_asset_key)
            if original_palette_asset_data and \
               original_palette_asset_data.get("places_asset_key") and \
               original_palette_asset_data.get("icon_type") == "2x2_placer":
                is_placer_tool = True
        
        if is_placer_tool:
            for r_off in range(2):
                for c_off in range(2):
                    if self._place_single_object_on_map(effective_asset_key, asset_definition_for_placement, grid_x + c_off, grid_y + r_off, is_flipped, rotation):
                        made_change_in_stroke = True
        else:
            if self._place_single_object_on_map(effective_asset_key, asset_definition_for_placement, grid_x, grid_y, is_flipped, rotation):
                made_change_in_stroke = True

        if made_change_in_stroke: self.map_content_changed.emit()
        self.editor_state.last_painted_tile_coords = (grid_x, grid_y)

    def _place_single_object_on_map(self, asset_key_for_data: str, asset_definition: Dict, grid_x: int, grid_y: int, is_flipped_h: bool, rotation: int) -> bool:
        world_x = int(float(grid_x * self.editor_state.grid_size))
        world_y = int(float(grid_y * self.editor_state.grid_size))

        game_id = asset_definition.get("game_type_id", "unknown")
        category = asset_definition.get("category", "unknown")
        is_spawn_type = category == "spawn"
        
        is_custom_image_type = (asset_key_for_data == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY or # type: ignore
                               (asset_key_for_data.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX) and game_id == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) ) # type: ignore
        is_trigger_type = asset_key_for_data == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY # type: ignore

        if not is_spawn_type and not is_custom_image_type and not is_trigger_type:
            for obj in self.editor_state.placed_objects:
                if obj.get("world_x") == world_x and obj.get("world_y") == world_y and \
                   obj.get("asset_editor_key") == asset_key_for_data and \
                   obj.get("is_flipped_h", False) == is_flipped_h and \
                   obj.get("rotation", 0) == rotation: 
                    if asset_definition.get("colorable") and self.editor_state.current_selected_asset_paint_color and obj.get("override_color") != self.editor_state.current_selected_asset_paint_color:
                        obj["override_color"] = self.editor_state.current_selected_asset_paint_color
                        self.update_specific_object_visuals(obj); return True
                    return False

        new_obj_data: Dict[str, Any] = {
            "asset_editor_key": asset_key_for_data, 
            "world_x": world_x, "world_y": world_y,
            "game_type_id": game_id,
            "layer_order": 0,
            "properties": ED_CONFIG.get_default_properties_for_asset(game_id), # type: ignore
            "is_flipped_h": is_flipped_h,
            "rotation": rotation,
            "editor_hidden": False, 
            "editor_locked": False  
        }

        if is_custom_image_type:
            if asset_key_for_data.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): # type: ignore
                 filename_from_key = asset_key_for_data.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX, 1)[1] # type: ignore
                 new_obj_data["source_file_path"] = f"Custom/{filename_from_key}"
            else:
                 new_obj_data["source_file_path"] = asset_definition.get("source_file_path", "")

            map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function)
            full_path = ""
            if map_folder and new_obj_data["source_file_path"]:
                 full_path = os.path.join(map_folder, new_obj_data["source_file_path"])
            
            if full_path and os.path.exists(full_path):
                q_img = QImage(full_path)
                if not q_img.isNull():
                    new_obj_data["original_width"] = q_img.width(); new_obj_data["original_height"] = q_img.height()
                    new_obj_data["current_width"] = q_img.width(); new_obj_data["current_height"] = q_img.height()
                else:
                    new_obj_data["original_width"]=new_obj_data["current_width"]=ED_CONFIG.BASE_GRID_SIZE*2 # type: ignore
                    new_obj_data["original_height"]=new_obj_data["current_height"]=ED_CONFIG.BASE_GRID_SIZE*2 # type: ignore
            else: 
                new_obj_data["original_width"]=new_obj_data["current_width"]=ED_CONFIG.BASE_GRID_SIZE*2 # type: ignore
                new_obj_data["original_height"]=new_obj_data["current_height"]=ED_CONFIG.BASE_GRID_SIZE*2 # type: ignore
            new_obj_data["crop_rect"] = None 

        elif is_trigger_type:
            new_obj_data["current_width"] = ED_CONFIG.BASE_GRID_SIZE * 2 # type: ignore
            new_obj_data["current_height"] = ED_CONFIG.BASE_GRID_SIZE * 2 # type: ignore

        elif asset_definition.get("colorable") and self.editor_state.current_selected_asset_paint_color:
            new_obj_data["override_color"] = self.editor_state.current_selected_asset_paint_color

        if is_spawn_type: 
            self.editor_state.placed_objects = [obj for obj in self.editor_state.placed_objects if obj.get("game_type_id") != game_id]

        self.editor_state.placed_objects.append(new_obj_data)
        self.draw_placed_objects()
        return True

    def _perform_erase_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if self.editor_state.current_tool_mode != "tool_eraser": return
        if continuous and (grid_x, grid_y) == self.editor_state.last_erased_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size); world_y_snapped = float(grid_y * self.editor_state.grid_size)
        target_point_scene = QPointF(world_x_snapped + self.editor_state.grid_size / 2.0, world_y_snapped + self.editor_state.grid_size / 2.0)
        item_to_remove_data: Optional[Dict[str, Any]] = None; highest_z = -float('inf')
        for obj_data in self.editor_state.placed_objects:
            obj_x = obj_data.get("world_x", 0); obj_y = obj_data.get("world_y", 0)
            obj_w = obj_data.get("current_width", self.editor_state.grid_size if obj_data.get("asset_editor_key") not in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY] else ED_CONFIG.BASE_GRID_SIZE)  # type: ignore
            obj_h = obj_data.get("current_height", self.editor_state.grid_size if obj_data.get("asset_editor_key") not in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY] else ED_CONFIG.BASE_GRID_SIZE)  # type: ignore
            obj_rect = QRectF(float(obj_x), float(obj_y), float(obj_w), float(obj_h))
            if obj_rect.contains(target_point_scene):
                current_obj_z = obj_data.get("layer_order", 0)
                if current_obj_z >= highest_z:
                    highest_z = current_obj_z; item_to_remove_data = obj_data
        if item_to_remove_data:
            if is_first_action: editor_history.push_undo_state(self.editor_state) # type: ignore
            self.editor_state.placed_objects.remove(item_to_remove_data)
            item_id = id(item_to_remove_data)
            if item_id in self._map_object_items:
                map_obj_item = self._map_object_items.pop(item_id)
                if isinstance(map_obj_item, BaseResizableMapItem):
                    map_obj_item.show_interaction_handles(False)
                    for handle in map_obj_item.interaction_handles:
                        if handle.scene(): self.map_scene.removeItem(handle)
                    map_obj_item.interaction_handles.clear()
                if map_obj_item.scene(): self.map_scene.removeItem(map_obj_item)
            self.map_content_changed.emit(); self.editor_state.last_erased_tile_coords = (grid_x, grid_y)

    def _perform_color_tile_action(self, grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
        if self.editor_state.current_tool_mode != "color_pick": return
        if not self.editor_state.current_tile_paint_color: return
        if continuous and (grid_x, grid_y) == self.editor_state.last_colored_tile_coords: return
        world_x_snapped = float(grid_x * self.editor_state.grid_size); world_y_snapped = float(grid_y * self.editor_state.grid_size)
        colored_something = False; target_point_scene = QPointF(world_x_snapped + self.editor_state.grid_size / 2.0, world_y_snapped + self.editor_state.grid_size / 2.0)
        item_to_color_data: Optional[Dict[str, Any]] = None; highest_z = -float('inf')
        for obj_data in self.editor_state.placed_objects:
            if obj_data.get("asset_editor_key") in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]: continue  # type: ignore
            asset_info = self.editor_state.assets_palette.get(str(obj_data.get("asset_editor_key")))
            if not asset_info or not asset_info.get("colorable"): continue
            obj_x = obj_data.get("world_x", 0); obj_y = obj_data.get("world_y", 0)
            obj_w_tuple, obj_h_tuple = asset_info.get("original_size_pixels", (self.editor_state.grid_size, self.editor_state.grid_size)) 
            obj_w, obj_h = float(obj_w_tuple), float(obj_h_tuple) 
            obj_rect = QRectF(float(obj_x), float(obj_y), float(obj_w), float(obj_h))
            if obj_rect.contains(target_point_scene):
                current_obj_z = obj_data.get("layer_order", 0)
                if current_obj_z >= highest_z: highest_z = current_obj_z; item_to_color_data = obj_data
        if item_to_color_data:
            new_color = self.editor_state.current_tile_paint_color
            if item_to_color_data.get("override_color") != new_color:
                if is_first_action: editor_history.push_undo_state(self.editor_state) # type: ignore
                item_to_color_data["override_color"] = new_color
                self.update_specific_object_visuals(item_to_color_data); colored_something = True
        if colored_something: self.map_content_changed.emit(); self.editor_state.last_colored_tile_coords = (grid_x, grid_y)

    def delete_selected_map_objects(self):
        selected_qt_items = self.map_scene.selectedItems()
        if not selected_qt_items: return

        items_to_process = [item for item in selected_qt_items if isinstance(item, (StandardMapObjectItem, BaseResizableMapItem))]
        if not items_to_process: return

        editor_history.push_undo_state(self.editor_state) # type: ignore

        data_refs_to_remove = [item.map_object_data_ref for item in items_to_process if hasattr(item, 'map_object_data_ref')] # type: ignore

        self.editor_state.placed_objects = [
            obj for obj in self.editor_state.placed_objects if obj not in data_refs_to_remove
        ]

        for item_map_obj in items_to_process:
            item_data_ref = getattr(item_map_obj, 'map_object_data_ref', None)
            if item_data_ref:
                item_id = id(item_data_ref)
                if item_id in self._map_object_items:
                    del self._map_object_items[item_id]

            if isinstance(item_map_obj, BaseResizableMapItem):
                item_map_obj.show_interaction_handles(False)
                for handle in item_map_obj.interaction_handles:
                    if handle.scene(): self.map_scene.removeItem(handle)
                item_map_obj.interaction_handles.clear()

            if item_map_obj.scene():
                self.map_scene.removeItem(item_map_obj)

        self.map_scene.clearSelection(); self.map_content_changed.emit(); self.map_object_selected_for_properties.emit(None)
        self.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).")

    @Slot(str, bool, int, int) 
    def on_asset_selected_for_placement(self, asset_key: Optional[str], is_flipped: bool, wall_variant_idx: int, rotation: int):
        logger.debug(f"MapView: on_asset_selected_for_placement key: '{asset_key}', flipped: {is_flipped}, rotation: {rotation}, wall_idx: {wall_variant_idx}")
        
        self.editor_state.palette_current_asset_key = asset_key
        self.editor_state.palette_asset_is_flipped_h = is_flipped
        self.editor_state.palette_asset_rotation = rotation
        self.editor_state.palette_wall_variant_index = wall_variant_idx
        
        if self.editor_state.current_tool_mode == "place" and self.editor_state.palette_current_asset_key:
             if self.underMouse(): 
                scene_pos = self.mapToScene(self.mapFromGlobal(QCursor.pos())); 
                world_x_s, world_y_s = self.snap_to_grid(scene_pos.x(), scene_pos.y()); 
                self._update_hover_preview(world_x_s, world_y_s)
        elif self._hover_preview_item: self._hover_preview_item.setVisible(False)


    def _update_hover_preview(self, world_x: float, world_y: float):
        effective_asset_key, is_flipped_for_hover, rotation_for_hover, _ = self.editor_state.get_current_placement_info()

        if self.editor_state.current_tool_mode == "place" and effective_asset_key:
            pixmap: Optional[QPixmap] = None
            
            if effective_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): # type: ignore
                filename = effective_asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1]; map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function)  # type: ignore
                full_path = ""
                if map_folder: full_path = os.path.join(map_folder, "Custom", filename)
                if map_folder and os.path.exists(full_path): 
                    temp_asset_data = {
                        "source_file": full_path, 
                        "original_size_pixels": None 
                    }
                    img_obj = QImage(full_path)
                    if not img_obj.isNull():
                        orig_w, orig_h = img_obj.width(), img_obj.height()
                        pixmap = get_asset_pixmap(effective_asset_key, temp_asset_data, 
                                                  QSizeF(orig_w, orig_h),
                                                  None, 
                                                  get_native_size_only=True,
                                                  is_flipped_h=is_flipped_for_hover, 
                                                  rotation=rotation_for_hover)
            else:
                asset_data = self.editor_state.assets_palette.get(effective_asset_key) 
                if asset_data: 
                    original_w_tuple, original_h_tuple = asset_data.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE));  # type: ignore
                    original_w, original_h = int(original_w_tuple), int(original_h_tuple); 
                    pixmap = get_asset_pixmap(effective_asset_key, asset_data, 
                                              QSizeF(original_w,original_h), 
                                              self.editor_state.current_selected_asset_paint_color, 
                                              get_native_size_only=True,
                                              is_flipped_h=is_flipped_for_hover, 
                                              rotation=rotation_for_hover) 
            
            if pixmap and not pixmap.isNull():
                if not self._hover_preview_item: 
                    self._hover_preview_item = QGraphicsPixmapItem(); 
                    self._hover_preview_item.setZValue(100); 
                    self.map_scene.addItem(self._hover_preview_item)
                    self._hover_preview_item.setOpacity(0.7) 

                if self._hover_preview_item.pixmap().cacheKey() != pixmap.cacheKey(): 
                    self._hover_preview_item.setPixmap(pixmap)
                
                self._hover_preview_item.setPos(QPointF(world_x, world_y)); 
                self._hover_preview_item.setVisible(True); 
                return
        
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)

    @Slot(str) 
    def on_tool_selected(self, tool_key: str):
        logger.debug(f"MapView: on_tool_selected tool_key: '{tool_key}'")
        self.editor_state.palette_current_asset_key = None 
        self.editor_state.palette_asset_is_flipped_h = False
        self.editor_state.palette_asset_rotation = 0
        self.editor_state.palette_wall_variant_index = 0
        if self._hover_preview_item: self._hover_preview_item.setVisible(False)

        if tool_key == "tool_select":
            self.editor_state.current_tool_mode = "select"
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) 
        elif tool_key == "tool_eraser": 
            self.editor_state.current_tool_mode = "tool_eraser"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        elif tool_key == "tool_tile_color_picker":
            self.editor_state.current_tool_mode = "color_pick"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            if self.parent_window:
                initial_c = self.editor_state.current_selected_asset_paint_color or self.editor_state.current_tile_paint_color or ED_CONFIG.C.BLUE # type: ignore
                new_q_color = QColorDialog.getColor(QColor(*initial_c), cast(QWidget, self.parent_window), "Select Tile Paint Color") 
                self.editor_state.current_tile_paint_color = new_q_color.getRgb()[:3] if new_q_color.isValid() else None 
                if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(f"Color Picker: {self.editor_state.current_tile_paint_color or 'None'}") # type: ignore
        elif tool_key == "platform_wall_gray_2x2_placer": 
            self.editor_state.current_tool_mode = "place"
            self.editor_state.palette_current_asset_key = tool_key 
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else: 
            self.editor_state.current_tool_mode = "select" 
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            logger.warning(f"MapView: Unknown tool_key '{tool_key}', defaulting to select mode.")
        
        logger.debug(f"MapView: current_tool_mode set to '{self.editor_state.current_tool_mode}'")


    @Slot(dict)
    def on_object_properties_changed(self, changed_object_data_ref: Dict[str, Any]):
        self.update_specific_object_visuals(changed_object_data_ref)

    @Slot()
    def on_scene_selection_changed(self):
        selected_qt_items = self.map_scene.selectedItems()

        for item_id, map_obj_item_generic in self._map_object_items.items():
            if isinstance(map_obj_item_generic, BaseResizableMapItem):
                is_currently_selected = map_obj_item_generic in selected_qt_items
                map_obj_item_generic.show_interaction_handles(is_currently_selected)
                if not is_currently_selected and map_obj_item_generic.current_interaction_mode == "crop":
                    map_obj_item_generic.set_interaction_mode("resize")

        if len(selected_qt_items) == 1:
            selected_item_generic = selected_qt_items[0]
            if isinstance(selected_item_generic, (StandardMapObjectItem, BaseResizableMapItem)):
                data_ref = getattr(selected_item_generic, 'map_object_data_ref', None)
                if data_ref:
                    self.map_object_selected_for_properties.emit(data_ref)
                else: self.map_object_selected_for_properties.emit(None)
            else: self.map_object_selected_for_properties.emit(None)
        else: 
            self.map_object_selected_for_properties.emit(None)

    def show_status_message(self, message: str, timeout: int = 2000):
        if hasattr(self.parent_window, "show_status_message"): self.parent_window.show_status_message(message, timeout) # type: ignore
        else: logger.info(f"Status (MapView): {message}")

#################### END OF FILE: map_view_widget.py ####################