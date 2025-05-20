# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6 with deferred QPixmap creation.
"""
# version 2.1.3 (Deferred QPixmap creation)

import sys # For logger fallback
from typing import Optional, Any, Tuple, Dict

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen
from PySide6.QtCore import QRectF, QPointF, Qt
import logging

import constants as C # Assuming C.GRAY, C.TILE_SIZE, C.ORANGE_RED exist

# --- Logger Setup ---
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Basic fallback if no parent logger is configured
    _tiles_handler = logging.StreamHandler(sys.stdout) # Use sys.stdout for visibility
    _tiles_formatter = logging.Formatter('%(asctime)s - TILES - %(levelname)s - %(message)s')
    _tiles_handler.setFormatter(_tiles_formatter)
    logger.addHandler(_tiles_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False # Prevent duplicate logs if root logger gets configured later
    logger.debug("Tiles.py: Basic console logger configured (module-level fallback).")
# --- End Logger Setup ---

class Platform:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = getattr(C, 'GRAY', (128,128,128)), # Safe getattr
                 platform_type: str = "generic_platform",
                 properties: Optional[Dict[str, Any]] = None):

        self.log_prefix = f"Platform(type='{platform_type}', rect=({x},{y},{width},{height}))"

        _w = float(width)
        _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width: {width}. Using 1.0."); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height: {height}. Using 1.0."); _h = 1.0
        
        self.width = _w
        self.height = _h

        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        # logger.debug(f"{self.log_prefix}: Effective dims {_w}x{_h}. Color: {self.q_color.name()}") # Logged in image property

        self._image: Optional[QPixmap] = None # Initialize as None for deferred creation

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.platform_type = platform_type
        self.properties = properties if properties is not None else {}
        self.is_collidable = True # Typically true for platforms
        if "boundary" in self.platform_type: self.properties.setdefault("is_boundary", True)
        self._graphics_item_ref: Optional[Any] = None # For QGraphicsScene integration if used

    @property
    def image(self) -> QPixmap:
        """
        Lazily creates and caches the QPixmap for this platform.
        """
        if self._image is None or self._image.isNull():
            pix_w = max(1, int(self.width))
            pix_h = max(1, int(self.height))
            log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h}), Color: {self.q_color.name()}"
            try:
                # logger.debug(log_msg_detail) # Uncomment for very verbose logging
                temp_pixmap = QPixmap(pix_w, pix_h)
                if temp_pixmap.isNull():
                    logger.error(f"{self.log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                    temp_pixmap = QPixmap(1,1) # Minimal valid pixmap
                    temp_pixmap.fill(Qt.GlobalColor.magenta) # Magenta error color
                else:
                    temp_pixmap.fill(self.q_color)
                self._image = temp_pixmap
            except Exception as e_pixmap:
                logger.error(f"{self.log_prefix}: EXCEPTION creating/filling QPixmap for size {pix_w}x{pix_h}: {e_pixmap}", exc_info=True)
                self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
        return self._image

    def draw_pyside(self, painter: QPainter, camera: Any): # Use 'Any' for camera if Camera class isn't imported here to avoid circularity
        """Draws the platform using PySide6 QPainter, transformed by camera."""
        if not self.rect.isValid(): return
        
        img_to_draw = self.image # Access via property to ensure it's created
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect) # Assume camera.apply exists and returns QRectF
            # Optional: Add culling here if screen_rect is outside painter.viewport()
            if painter.window().intersects(screen_rect.toRect()): # Basic culling
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else: # Fallback if image is somehow still null
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color)


class Ladder:
    def __init__(self, x: float, y: float, width: float, height: float):
        self.log_prefix = f"Ladder(rect=({x},{y},{width},{height}))"
        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width {width}. Using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height {height}. Using 1.0"); _h = 1.0
        self.width = _w; self.height = _h
        self._image: Optional[QPixmap] = None
        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    @property
    def image(self) -> QPixmap:
        if self._image is None or self._image.isNull():
            pix_w = max(1, int(self.width)); pix_h = max(1, int(self.height))
            log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h})"
            try:
                # logger.debug(log_msg_detail)
                temp_pixmap = QPixmap(pix_w, pix_h)
                if temp_pixmap.isNull():
                    logger.error(f"{self.log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                    temp_pixmap = QPixmap(1,1); temp_pixmap.fill(Qt.GlobalColor.magenta)
                else:
                    temp_pixmap.fill(Qt.GlobalColor.transparent) # Ladders are mostly transparent with rungs
                    painter = QPainter(temp_pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    
                    # Safe getattr for C.TILE_SIZE with a fallback
                    tile_size = float(getattr(C, 'TILE_SIZE', 40.0))
                    rung_qcolor = QColor(139, 69, 19, 220) # Brownish, semi-transparent
                    pen = QPen(rung_qcolor)
                    
                    num_rungs = int(self.height / (tile_size * 0.35))
                    if num_rungs > 0:
                        rung_spacing = self.height / (num_rungs + 1) # Distribute rungs evenly
                        pen.setWidth(max(1, int(tile_size * 0.05)))
                        painter.setPen(pen)
                        for i in range(1, num_rungs + 1):
                            rung_y_pos = i * rung_spacing
                            # Ensure rung_y_pos is float for QPointF
                            if rung_y_pos < self.height - 1:
                                painter.drawLine(QPointF(0.0, float(rung_y_pos)), QPointF(self.width, float(rung_y_pos)))
                    
                    rail_thickness = max(2, int(tile_size * 0.075))
                    pen.setWidth(rail_thickness)
                    painter.setPen(pen)
                    left_rail_x = float(rail_thickness / 2.0)
                    right_rail_x = self.width - float(rail_thickness / 2.0)

                    if self.width >= rail_thickness: # Draw left rail
                        painter.drawLine(QPointF(left_rail_x, 0.0), QPointF(left_rail_x, self.height))
                    if self.width >= rail_thickness * 2: # Draw right rail if space
                        painter.drawLine(QPointF(right_rail_x, 0.0), QPointF(right_rail_x, self.height))
                    elif self.width > rail_thickness: # Or a single central rail if very narrow
                        painter.drawLine(QPointF(self.width / 2.0, 0.0), QPointF(self.width / 2.0, self.height))
                    painter.end()
                self._image = temp_pixmap
            except Exception as e_pixmap_ladder:
                logger.error(f"{self.log_prefix}: EXCEPTION creating QPixmap for Ladder: {e_pixmap_ladder}", exc_info=True)
                self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
        return self._image

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        img_to_draw = self.image
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect)
            if painter.window().intersects(screen_rect.toRect()):
                painter.drawPixmap(screen_rect.topLeft(), img_to_draw)


class Lava:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = getattr(C, 'ORANGE_RED', (255, 69, 0))):
        self.log_prefix = f"Lava(rect=({x},{y},{width},{height}))"
        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width {width}. Using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height {height}. Using 1.0"); _h = 1.0
        self.width = _w; self.height = _h
        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        self._image: Optional[QPixmap] = None
        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    @property
    def image(self) -> QPixmap:
        if self._image is None or self._image.isNull():
            pix_w = max(1, int(self.width)); pix_h = max(1, int(self.height))
            log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h}), Color: {self.q_color.name()}"
            try:
                # logger.debug(log_msg_detail)
                temp_pixmap = QPixmap(pix_w, pix_h)
                if temp_pixmap.isNull():
                    logger.error(f"{self.log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                    temp_pixmap = QPixmap(1,1); temp_pixmap.fill(Qt.GlobalColor.magenta)
                else:
                    temp_pixmap.fill(self.q_color) # Simple fill for Lava
                self._image = temp_pixmap
            except Exception as e_pixmap_lava:
                logger.error(f"{self.log_prefix}: EXCEPTION creating QPixmap for Lava: {e_pixmap_lava}", exc_info=True)
                self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
        return self._image

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        img_to_draw = self.image
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect)
            if painter.window().intersects(screen_rect.toRect()):
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else: # Fallback if image is null
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color)