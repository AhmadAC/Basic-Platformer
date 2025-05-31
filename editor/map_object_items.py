#################### START OF FILE: map_object_items.py ####################

# editor/map_object_items.py
# -*- coding: utf-8 -*-
"""
Contains QGraphicsItem representations for standard map objects.
MODIFIED: StandardMapObjectItem now handles 'render_as_rotated_segment'.
ADDED: InvisibleWallMapItem, made resizable and visually similar to TriggerSquare (red).
FIXED: QStyleOptionGraphicsItem.StyleState access to QStyle.StateFlag.
"""
import logging
from typing import Optional, Dict, Any, Tuple

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QStyle # Import QStyle
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QTransform, QImage, QPainterPath, QFont
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QSize

from editor import editor_config as ED_CONFIG
from editor.editor_state import EditorState 
from editor.editor_assets import get_asset_pixmap, _create_colored_pixmap 
# BaseResizableMapItem is now imported in editor_custom_items where InvisibleWallMapItem is
# from editor.editor_custom_items import BaseResizableMapItem 

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
        self.is_render_as_rotated_segment = False 
        self.procedural_color_tuple: Optional[Tuple[int,int,int]] = None 
        self.procedural_width: float = float(ED_CONFIG.TS) 
        self.procedural_height: float = float(ED_CONFIG.TS) 
        self.segment_base_width: float = float(ED_CONFIG.TS)
        self.segment_base_height: float = float(ED_CONFIG.TS) // 4


        asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
        initial_pixmap_for_super = QPixmap() 

        if asset_info:
            self.is_render_as_rotated_segment = asset_info.get("render_as_rotated_segment", False)
            if self.is_render_as_rotated_segment:
                self.is_procedural_tile = True 
                self.procedural_width = float(ED_CONFIG.TS) 
                self.procedural_height = float(ED_CONFIG.TS)
                
                seg_params = asset_info.get("surface_params")
                if seg_params and isinstance(seg_params, tuple) and len(seg_params) >= 2:
                    self.segment_base_width = float(seg_params[0])
                    self.segment_base_height = float(seg_params[1])
                else: 
                    self.segment_base_width = float(ED_CONFIG.TS)
                    self.segment_base_height = float(ED_CONFIG.TS) // 4
                    logger.warning(f"Segment asset {editor_key} missing valid surface_params, using defaults.")

                transparent_pm_size = QSize(int(self.procedural_width), int(self.procedural_height))
                if transparent_pm_size.isEmpty(): transparent_pm_size = QSize(1,1) 
                initial_pixmap_for_super = QPixmap(transparent_pm_size)
                initial_pixmap_for_super.fill(Qt.GlobalColor.transparent)

            elif asset_info.get("surface_params") and \
                 asset_info.get("category") == "tile" and not asset_info.get("source_file"):
                self.is_procedural_tile = True
                params = asset_info["surface_params"]
                self.procedural_width = float(params[0])
                self.procedural_height = float(params[1])
                transparent_pm_size = QSize(int(self.procedural_width), int(self.procedural_height))
                if transparent_pm_size.isEmpty(): transparent_pm_size = QSize(1,1) 
                initial_pixmap_for_super = QPixmap(transparent_pm_size)
                initial_pixmap_for_super.fill(Qt.GlobalColor.transparent)
            else: # Image-based asset
                self.is_procedural_tile = False
                original_w, original_h = asset_info.get("original_size_pixels", (ED_CONFIG.BASE_GRID_SIZE, ED_CONFIG.BASE_GRID_SIZE))
                pixmap = get_asset_pixmap(self.editor_key, asset_info, QSizeF(int(original_w), int(original_h)),
                                          self.map_object_data_ref.get("override_color"), 
                                          get_native_size_only=True,
                                          is_flipped_h=False, rotation=0) 
                if pixmap and not pixmap.isNull(): initial_pixmap_for_super = pixmap
                else:
                    initial_pixmap_for_super = QPixmap(int(original_w), int(original_h))
                    initial_pixmap_for_super.fill(Qt.GlobalColor.magenta)
        else: 
            initial_pixmap_for_super = QPixmap(ED_CONFIG.TS, ED_CONFIG.TS) 
            initial_pixmap_for_super.fill(Qt.GlobalColor.cyan)
        
        super().__init__(initial_pixmap_for_super, parent)
        
        self.setPos(QPointF(float(world_x), float(world_y)))
        
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        current_flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        if not is_locked: current_flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlags(current_flags)
        
        self.setZValue(map_object_data_ref.get("layer_order", 0))
        self.setVisible(not map_object_data_ref.get("editor_hidden", False))
        
        if not self.is_render_as_rotated_segment:
            self._apply_orientation_transform()


    def boundingRect(self) -> QRectF:
        if self.is_procedural_tile: 
            return QRectF(0, 0, self.procedural_width, self.procedural_height) 
        else: 
            pm = self.pixmap()
            if pm and not pm.isNull():
                return QRectF(0,0, float(pm.width()), float(pm.height()))
            return QRectF(0,0, ED_CONFIG.TS, ED_CONFIG.TS) 

    def shape(self) -> QPainterPath:
        path = QPainterPath(); path.addRect(self.boundingRect()); return path

    def _apply_orientation_transform(self):
        if self.is_render_as_rotated_segment:
            self.setTransform(QTransform()); return

        item_should_be_flipped = self.map_object_data_ref.get("is_flipped_h", False)
        rotation_angle = float(self.map_object_data_ref.get("rotation", 0))
        current_transform = QTransform() 
        rect = self.boundingRect() 
        center_x = rect.width() / 2.0; center_y = rect.height() / 2.0
        current_transform.translate(center_x, center_y)
        if item_should_be_flipped: current_transform.scale(-1, 1)
        if rotation_angle != 0: current_transform.rotate(rotation_angle)
        current_transform.translate(-center_x, -center_y)
        self.setTransform(current_transform)


    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        if self.is_render_as_rotated_segment:
            painter.save()
            asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
            if not asset_info: painter.restore(); return

            color_tuple_seg = self.map_object_data_ref.get("override_color")
            seg_params = asset_info.get("surface_params")
            if not color_tuple_seg:
                 if seg_params and len(seg_params) == 3: color_tuple_seg = seg_params[2]
                 else: color_tuple_seg = getattr(ED_CONFIG.C, "MAGENTA", (255,0,255))
            
            base_segment_pm = _create_colored_pixmap(int(self.segment_base_width), int(self.segment_base_height), color_tuple_seg)
            rotation = self.map_object_data_ref.get("rotation", 0)
            rotated_segment_pm = base_segment_pm
            if rotation != 0:
                img = base_segment_pm.toImage()
                center = QPointF(img.width() / 2.0, img.height() / 2.0)
                transform = QTransform().translate(center.x(), center.y()).rotate(float(rotation)).translate(-center.x(), -center.y())
                rotated_img = img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                if not rotated_img.isNull(): rotated_segment_pm = QPixmap.fromImage(rotated_img)

            rsw, rsh = float(rotated_segment_pm.width()), float(rotated_segment_pm.height())
            canvas_w_float, canvas_h_float = self.procedural_width, self.procedural_height 
            paint_x, paint_y = 0.0, 0.0

            if rotation == 0: paint_x = (canvas_w_float - rsw) / 2.0; paint_y = 0.0
            elif rotation == 90: paint_x = canvas_w_float - rsw; paint_y = (canvas_h_float - rsh) / 2.0
            elif rotation == 180: paint_x = (canvas_w_float - rsw) / 2.0; paint_y = canvas_h_float - rsh
            elif rotation == 270: paint_x = 0.0; paint_y = (canvas_h_float - rsh) / 2.0
            
            painter.drawPixmap(QPointF(paint_x, paint_y), rotated_segment_pm)
            
            if option.state & QStyle.StateFlag.State_Selected: # Corrected
                pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_SELECTION_RECT_COLOR_TUPLE), 2, Qt.PenStyle.SolidLine); pen.setCosmetic(True)
                painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(self.boundingRect().adjusted(0.5,0.5,-0.5,-0.5))
            painter.restore()
            return 

        elif self.is_procedural_tile:
            painter.save()
            color_to_use = self.map_object_data_ref.get("override_color", self.procedural_color_tuple)
            asset_info_paint = self.editor_state_ref.assets_palette.get(self.editor_key)
            if not color_to_use: 
                 if asset_info_paint and asset_info_paint.get("surface_params"): color_to_use = asset_info_paint["surface_params"][2]
                 else: color_to_use = getattr(ED_CONFIG.C, "MAGENTA", (255,0,255))
            brush_color = QColor(*color_to_use) 
            painter.setBrush(brush_color)
            pen_color = brush_color.darker(130) if brush_color.alpha() == 255 else Qt.GlobalColor.transparent
            painter.setPen(QPen(pen_color, 0.5)) 
            props = self.map_object_data_ref.get("properties", {}); radius = float(props.get("corner_radius", 0)); rect = self.boundingRect()
            if radius > 1: 
                path = QPainterPath()
                if props.get("round_top_left", False): path.moveTo(rect.topLeft() + QPointF(radius, 0)); path.arcTo(QRectF(rect.topLeft(), QSizeF(radius * 2, radius * 2)), 180, -90)
                else: path.moveTo(rect.topLeft())
                path.lineTo(rect.topRight() - QPointF(radius if props.get("round_top_right", False) else 0, 0))
                if props.get("round_top_right", False): path.arcTo(QRectF(rect.topRight() - QPointF(radius*2,0), QSizeF(radius * 2, radius * 2)), 90, -90)
                else: path.lineTo(rect.topRight())
                path.lineTo(rect.bottomRight() - QPointF(0, radius if props.get("round_bottom_right", False) else 0))
                if props.get("round_bottom_right", False): path.arcTo(QRectF(rect.bottomRight() - QPointF(radius*2,radius*2), QSizeF(radius * 2, radius * 2)), 0, -90)
                else: path.lineTo(rect.bottomRight())
                path.lineTo(rect.bottomLeft() + QPointF(radius if props.get("round_bottom_left", False) else 0, 0))
                if props.get("round_bottom_left", False): path.arcTo(QRectF(rect.bottomLeft() - QPointF(0,radius*2) , QSizeF(radius * 2, radius * 2)), -90, -90)
                else: path.lineTo(rect.bottomLeft())
                path.closeSubpath(); painter.drawPath(path)
            else: painter.drawRect(rect)
            
            if option.state & QStyle.StateFlag.State_Selected: # Corrected
                pen = QPen(QColor(*ED_CONFIG.MAP_VIEW_SELECTION_RECT_COLOR_TUPLE), 2, Qt.PenStyle.SolidLine); pen.setCosmetic(True)
                painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(self.boundingRect().adjusted(0.5,0.5,-0.5,-0.5))
            painter.restore() 
        else: # Image-based tiles
            super().paint(painter, option, widget) # QGraphicsPixmapItem handles its own selection highlight


    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        if is_locked and change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged: return self.pos() 
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and self.isSelected():
            if self.scene().property("is_actively_transforming_item") is True: return super().itemChange(change, value)
            new_pos: QPointF = value 
            grid_size = self.scene().property("grid_size") 
            grid_size = grid_size if isinstance(grid_size, (int, float)) and grid_size > 0 else ED_CONFIG.BASE_GRID_SIZE
            snapped_x = round(new_pos.x() / grid_size) * grid_size; snapped_y = round(new_pos.y() / grid_size) * grid_size
            if int(snapped_x) != self.map_object_data_ref.get('world_x') or int(snapped_y) != self.map_object_data_ref.get('world_y'):
                self.map_object_data_ref['world_x'] = int(snapped_x); self.map_object_data_ref['world_y'] = int(snapped_y)
                map_view = self.scene().parent() 
                if hasattr(map_view, 'object_graphically_moved_signal'): map_view.object_graphically_moved_signal.emit(self.map_object_data_ref) 
            if abs(new_pos.x() - snapped_x) > 1e-3 or abs(new_pos.y() - snapped_y) > 1e-3: return QPointF(float(snapped_x), float(snapped_y))
            return new_pos
        return super().itemChange(change, value)

    def update_visuals_from_data(self, editor_state: EditorState): 
        asset_info = self.editor_state_ref.assets_palette.get(self.editor_key)
        if not asset_info: return

        self.setVisible(not self.map_object_data_ref.get("editor_hidden", False))
        is_locked = self.map_object_data_ref.get("editor_locked", False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not is_locked)

        if self.is_render_as_rotated_segment:
            self.update() 
        elif not self.is_procedural_tile: 
            original_w, original_h = asset_info.get("original_size_pixels", (self.pixmap().width(), self.pixmap().height()))
            new_pixmap = get_asset_pixmap(self.editor_key, asset_info,
                                          QSizeF(int(original_w), int(original_h)),
                                          self.map_object_data_ref.get("override_color"),
                                          get_native_size_only=True,
                                          is_flipped_h=False, rotation=0) 
            if new_pixmap and not new_pixmap.isNull():
                if self.pixmap().cacheKey() != new_pixmap.cacheKey(): 
                    self.prepareGeometryChange(); self.setPixmap(new_pixmap)
            else: 
                fallback_pm = QPixmap(int(original_w), int(original_h)); fallback_pm.fill(Qt.GlobalColor.magenta)
                self.prepareGeometryChange(); self.setPixmap(fallback_pm)
            self._apply_orientation_transform() 
        else: 
            new_color = self.map_object_data_ref.get("override_color")
            asset_info_paint = self.editor_state_ref.assets_palette.get(self.editor_key) 
            if not new_color and asset_info_paint and asset_info_paint.get("surface_params"): new_color = asset_info_paint["surface_params"][2]
            needs_geom_change = False
            if asset_info_paint and asset_info_paint.get("surface_params"):
                params = asset_info_paint["surface_params"]
                new_pw, new_ph = float(params[0]), float(params[1])
                if abs(self.procedural_width - new_pw) > 1e-3 or abs(self.procedural_height - new_ph) > 1e-3:
                    self.procedural_width = new_pw; self.procedural_height = new_ph
                    needs_geom_change = True
            if self.procedural_color_tuple != new_color or needs_geom_change:
                self.procedural_color_tuple = new_color 
                if needs_geom_change: self.prepareGeometryChange()
                self.update() 

        new_z = self.map_object_data_ref.get("layer_order", 0)
        if self.zValue() != new_z: self.setZValue(new_z)
        new_pos_x = float(self.map_object_data_ref.get("world_x", 0))
        new_pos_y = float(self.map_object_data_ref.get("world_y", 0))
        if self.pos() != QPointF(new_pos_x, new_pos_y): self.setPos(new_pos_x, new_pos_y)

# InvisibleWallMapItem is now moved to editor_custom_items.py
# This file (map_object_items.py) will now only contain StandardMapObjectItem.

#################### END OF FILE: map_object_items.py ####################