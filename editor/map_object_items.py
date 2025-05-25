#################### START OF FILE: map_object_items.py ####################

# editor/map_object_items.py
# -*- coding: utf-8 -*-
"""
Contains QGraphicsItem representations for standard map objects.
"""
import logging
from typing import Optional, Dict, Any, Tuple

from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QTransform, QImage, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QSize

from . import editor_config as ED_CONFIG
from .editor_state import EditorState # Forward declaration for type hint
from .editor_assets import get_asset_pixmap
from .editor_custom_items import BaseResizableMapItem # If BaseResizable isn't moved here

logger = logging.getLogger(__name__)

class StandardMapObjectItem(QGraphicsPixmapItem): # Or BaseResizableMapItem if we move it
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
            
            transparent_pm_size = QSize(int(self.procedural_width), int(self.procedural_height))
            if transparent_pm_size.isEmpty(): transparent_pm_size = QSize(1,1) 
            transparent_pm = QPixmap(transparent_pm_size)
            transparent_pm.fill(Qt.GlobalColor.transparent)
            super().__init__(transparent_pm, parent) 
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

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

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
            return self.pos() 
        
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

#################### END OF FILE: map_object_items.py ####################