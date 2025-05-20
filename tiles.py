#################### START OF FILE: tiles.py ####################

# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6.
"""
# version 2.1.2 (More detailed QPixmap creation logging)

from typing import Optional, Any, Tuple, Dict

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen
from PySide6.QtCore import QRectF, QPointF, Qt
import logging

import constants as C

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    _tiles_handler = logging.StreamHandler()
    _tiles_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _tiles_handler.setFormatter(_tiles_formatter)
    logger.addHandler(_tiles_handler)
    logger.setLevel(logging.DEBUG)
    logger.debug("Tiles.py: Basic logger configured.")


class Platform:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = C.GRAY,
                 platform_type: str = "generic_platform",
                 properties: Optional[Dict[str, Any]] = None):

        _w = float(width)
        _h = float(height)
        log_prefix = f"Platform(type='{platform_type}', rect=({x},{y},{width},{height}))"

        if _w <= 0:
            logger.warning(f"{log_prefix}: Non-positive width: {width}. Using 1.0.")
            _w = 1.0
        if _h <= 0:
            logger.warning(f"{log_prefix}: Non-positive height: {height}. Using 1.0.")
            _h = 1.0
        
        self.width = _w
        self.height = _h

        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        logger.debug(f"{log_prefix}: Effective dims {_w}x{_h}. Color: {self.q_color.name()}")


        pix_w = max(1, int(self.width))
        pix_h = max(1, int(self.height))
        
        try:
            logger.debug(f"{log_prefix}: Attempting QPixmap({pix_w}, {pix_h})")
            self.image = QPixmap(pix_w, pix_h)
            if self.image.isNull():
                logger.error(f"{log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                self.image = QPixmap(1,1)
                self.image.fill(Qt.GlobalColor.magenta)
            else:
                logger.debug(f"{log_prefix}: QPixmap created successfully (size {self.image.size()}). Filling with {self.q_color.name()}.")
                self.image.fill(self.q_color)
                # Verify fill
                # temp_img_check = self.image.toImage()
                # if not temp_img_check.isNull() and temp_img_check.pixelColor(0,0) != self.q_color:
                #     logger.warning(f"{log_prefix}: Fill color mismatch. Expected {self.q_color.name()}, got {temp_img_check.pixelColor(0,0).name()}")
                
        except Exception as e_pixmap:
            logger.error(f"{log_prefix}: EXCEPTION creating/filling QPixmap for size {pix_w}x{pix_h}: {e_pixmap}", exc_info=True)
            self.image = QPixmap(1,1)
            self.image.fill(Qt.GlobalColor.magenta)

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.platform_type = platform_type
        self.properties = properties if properties is not None else {}
        self.is_collidable = True
        if "boundary" in self.platform_type: self.properties.setdefault("is_boundary", True)
        self._graphics_item_ref: Optional[Any] = None

    def get_qpixmap(self) -> QPixmap: return self.image
    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull():
            painter.drawPixmap(self.rect.topLeft(), self.image)
        else:
            painter.fillRect(self.rect, self.q_color)


class Ladder:
    # ... (Ladder code remains the same, ensure its self.image is valid if used) ...
    def __init__(self, x: float, y: float, width: float, height: float):
        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"Ladder width {width} <=0, using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"Ladder height {height} <=0, using 1.0"); _h = 1.0
        self.width = _w; self.height = _h
        pix_w = max(1, int(self.width)); pix_h = max(1, int(self.height))
        self.image = QPixmap(pix_w, pix_h)
        self.image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rung_qcolor = QColor(139, 69, 19, 220); pen = QPen(rung_qcolor)
        num_rungs = int(self.height / (C.TILE_SIZE * 0.35))
        if num_rungs > 0:
            rung_spacing = self.height / (num_rungs +1)
            pen.setWidth(max(1, int(C.TILE_SIZE * 0.05))); painter.setPen(pen)
            for i in range(1, num_rungs + 1):
                rung_y_pos = i * rung_spacing
                if rung_y_pos < self.height - 1: painter.drawLine(QPointF(0, rung_y_pos), QPointF(self.width, rung_y_pos))
        rail_thickness = max(2, int(C.TILE_SIZE * 0.075)); pen.setWidth(rail_thickness); painter.setPen(pen)
        left_rail_x = float(rail_thickness / 2.0); right_rail_x = self.width - float(rail_thickness / 2.0)
        if self.width >= rail_thickness: painter.drawLine(QPointF(left_rail_x, 0), QPointF(left_rail_x, self.height))
        if self.width >= rail_thickness * 2: painter.drawLine(QPointF(right_rail_x, 0), QPointF(right_rail_x, self.height))
        elif self.width > rail_thickness: painter.drawLine(QPointF(self.width / 2.0, 0), QPointF(self.width / 2.0, self.height))
        painter.end()
        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
    def get_qpixmap(self) -> QPixmap: return self.image
    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull(): painter.drawPixmap(self.rect.topLeft(), self.image)


class Lava:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = C.ORANGE_RED):
        _w = float(width); _h = float(height)
        log_prefix = f"Lava(rect=({x},{y},{width},{height}))"
        if _w <= 0: logger.warning(f"{log_prefix}: Non-positive width: {width}. Using 1.0."); _w = 1.0
        if _h <= 0: logger.warning(f"{log_prefix}: Non-positive height: {height}. Using 1.0."); _h = 1.0
        self.width = _w; self.height = _h
        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        logger.debug(f"{log_prefix}: Effective dims {_w}x{_h}. Color: {self.q_color.name()}")
        pix_w = max(1, int(self.width)); pix_h = max(1, int(self.height))
        try:
            logger.debug(f"{log_prefix}: Attempting QPixmap({pix_w}, {pix_h})")
            self.image = QPixmap(pix_w, pix_h)
            if self.image.isNull():
                logger.error(f"{log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                self.image = QPixmap(1,1); self.image.fill(Qt.GlobalColor.magenta)
            else:
                logger.debug(f"{log_prefix}: QPixmap created successfully (size {self.image.size()}). Filling with {self.q_color.name()}.")
                self.image.fill(self.q_color)
        except Exception as e_pixmap_lava:
            logger.error(f"{log_prefix}: EXCEPTION creating/filling QPixmap for size {pix_w}x{pix_h}: {e_pixmap_lava}", exc_info=True)
            self.image = QPixmap(1,1); self.image.fill(Qt.GlobalColor.magenta)
        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
    def get_qpixmap(self) -> QPixmap: return self.image
    def draw(self, painter: QPainter):
        if self.image and not self.image.isNull(): painter.drawPixmap(self.rect.topLeft(), self.image)
        else: painter.fillRect(self.rect, self.q_color)

#################### END OF FILE: tiles.py ####################