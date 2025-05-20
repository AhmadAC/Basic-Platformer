#################### START OF FILE: tiles.py ####################

# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6.
"""
# version 2.1.1 (Added explicit float casting and logging for zero/negative dimensions)

from typing import Optional, Any, Tuple, Dict

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen
from PySide6.QtCore import QRectF, QPointF, Qt
import logging # Import logging

# Import game constants
import constants as C

logger = logging.getLogger(__name__) # Standard logger for this module
if not logger.hasHandlers(): # Basic setup if not configured by main logger
    _tiles_handler = logging.StreamHandler()
    _tiles_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _tiles_handler.setFormatter(_tiles_formatter)
    logger.addHandler(_tiles_handler)
    logger.setLevel(logging.DEBUG)


class Platform:
    """
    Standard solid platform.
    Can be tagged with a platform_type (e.g., "ground", "ledge", "wall").
    Image is a simple colored rectangle using QPixmap.
    """
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = C.GRAY,
                 platform_type: str = "generic_platform",
                 properties: Optional[Dict[str, Any]] = None):

        _w = float(width)
        _h = float(height)

        if _w <= 0:
            logger.warning(f"Platform created with non-positive width: {width} (type: {platform_type}). Using 1.0.")
            _w = 1.0
        if _h <= 0:
            logger.warning(f"Platform created with non-positive height: {height} (type: {platform_type}). Using 1.0.")
            _h = 1.0
        
        self.width = _w
        self.height = _h

        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)

        # Ensure dimensions for QPixmap are integers and at least 1x1
        pix_w = max(1, int(self.width))
        pix_h = max(1, int(self.height))
        
        try:
            self.image = QPixmap(pix_w, pix_h)
            if self.image.isNull():
                logger.error(f"Platform Error: QPixmap creation returned null for size {pix_w}x{pix_h} (type: {platform_type}, color: {self.q_color.name()}).")
                # Create a fallback QPixmap
                self.image = QPixmap(1,1)
                self.image.fill(Qt.GlobalColor.magenta)
            else:
                self.image.fill(self.q_color)
        except Exception as e_pixmap:
            logger.error(f"Platform Error: Exception creating/filling QPixmap for size {pix_w}x{pix_h} (type: {platform_type}): {e_pixmap}")
            self.image = QPixmap(1,1) # Fallback
            self.image.fill(Qt.GlobalColor.magenta)


        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.platform_type = platform_type
        self.properties = properties if properties is not None else {}
        
        self.is_collidable = True
        if "boundary" in self.platform_type:
            self.properties.setdefault("is_boundary", True)
        
        self._graphics_item_ref: Optional[Any] = None

    def get_qpixmap(self) -> QPixmap:
        return self.image

    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull():
            painter.drawPixmap(self.rect.topLeft(), self.image)
        else: # Fallback drawing if image is bad
            painter.fillRect(self.rect, self.q_color)


class Ladder:
    def __init__(self, x: float, y: float, width: float, height: float):
        _w = float(width)
        _h = float(height)
        if _w <= 0: logger.warning(f"Ladder width {width} <=0, using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"Ladder height {height} <=0, using 1.0"); _h = 1.0
        
        self.width = _w
        self.height = _h

        pix_w = max(1, int(self.width))
        pix_h = max(1, int(self.height))
        self.image = QPixmap(pix_w, pix_h)
        self.image.fill(Qt.GlobalColor.transparent) # Transparent background

        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rung_qcolor = QColor(139, 69, 19, 220) # SaddleBrown
        pen = QPen(rung_qcolor)

        num_rungs = int(self.height / (C.TILE_SIZE * 0.35))
        if num_rungs > 0:
            rung_spacing = self.height / (num_rungs +1)
            pen.setWidth(max(1, int(C.TILE_SIZE * 0.05)))
            painter.setPen(pen)
            for i in range(1, num_rungs + 1):
                rung_y_pos = i * rung_spacing
                if rung_y_pos < self.height - 1:
                    painter.drawLine(QPointF(0, rung_y_pos), QPointF(self.width, rung_y_pos))

        rail_thickness = max(2, int(C.TILE_SIZE * 0.075))
        pen.setWidth(rail_thickness)
        painter.setPen(pen)
        left_rail_x = float(rail_thickness / 2.0)
        right_rail_x = self.width - float(rail_thickness / 2.0)

        if self.width >= rail_thickness:
            painter.drawLine(QPointF(left_rail_x, 0), QPointF(left_rail_x, self.height))
        if self.width >= rail_thickness * 2:
             painter.drawLine(QPointF(right_rail_x, 0), QPointF(right_rail_x, self.height))
        elif self.width > rail_thickness:
            center_rail_x = self.width / 2.0
            painter.drawLine(QPointF(center_rail_x, 0), QPointF(center_rail_x, self.height))
        painter.end()

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
    
    def get_qpixmap(self) -> QPixmap:
        return self.image
    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull():
            painter.drawPixmap(self.rect.topLeft(), self.image)

class Lava:
    def __init__(self, x: float, y: float, width: float, height: float, 
                 color_tuple: Tuple[int, int, int] = C.ORANGE_RED):
        _w = float(width)
        _h = float(height)
        if _w <= 0: logger.warning(f"Lava width {width} <=0, using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"Lava height {height} <=0, using 1.0"); _h = 1.0

        self.width = _w
        self.height = _h
        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)

        pix_w = max(1, int(self.width))
        pix_h = max(1, int(self.height))
        try:
            self.image = QPixmap(pix_w, pix_h)
            if self.image.isNull():
                logger.error(f"Lava Error: QPixmap creation returned null for size {pix_w}x{pix_h} (color: {self.q_color.name()}).")
                self.image = QPixmap(1,1); self.image.fill(Qt.GlobalColor.magenta)
            else:
                self.image.fill(self.q_color)
        except Exception as e_pixmap_lava:
            logger.error(f"Lava Error: Exception creating/filling QPixmap for size {pix_w}x{pix_h}: {e_pixmap_lava}")
            self.image = QPixmap(1,1); self.image.fill(Qt.GlobalColor.magenta)

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    def get_qpixmap(self) -> QPixmap:
        return self.image
    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull():
            painter.drawPixmap(self.rect.topLeft(), self.image)
        else:
            painter.fillRect(self.rect, self.q_color)

#################### END OF FILE: tiles.py ####################