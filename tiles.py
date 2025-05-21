# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6 with deferred QPixmap creation.
BackgroundTile added.
"""
# version 2.1.4 (BackgroundTile added and integrated)

import sys # For logger fallback
from typing import Optional, Any, Tuple, Dict, List # Added List for type hint consistency

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen
from PySide6.QtCore import QRectF, QPointF, Qt, QSize # Added QSize
import logging

import constants as C # Assuming C.GRAY, C.TILE_SIZE, C.ORANGE_RED exist
from assets import resource_path, load_gif_frames # For BackgroundTile image loading

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

        self._image: Optional[QPixmap] = None # Initialize as None for deferred creation

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.platform_type = platform_type
        self.properties = properties if properties is not None else {}
        self.is_collidable = True 
        if "boundary" in self.platform_type: self.properties.setdefault("is_boundary", True)
        self._graphics_item_ref: Optional[Any] = None 

    @property
    def image(self) -> QPixmap:
        if self._image is None or self._image.isNull():
            pix_w = max(1, int(self.width))
            pix_h = max(1, int(self.height))
            log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h}), Color: {self.q_color.name()}"
            try:
                # logger.debug(log_msg_detail) 
                temp_pixmap = QPixmap(pix_w, pix_h)
                if temp_pixmap.isNull():
                    logger.error(f"{self.log_prefix}: QPixmap creation FAILED (isNull=True) for size {pix_w}x{pix_h}.")
                    temp_pixmap = QPixmap(1,1); temp_pixmap.fill(Qt.GlobalColor.magenta)
                else:
                    temp_pixmap.fill(self.q_color)
                self._image = temp_pixmap
            except Exception as e_pixmap:
                logger.error(f"{self.log_prefix}: EXCEPTION creating/filling QPixmap for size {pix_w}x{pix_h}: {e_pixmap}", exc_info=True)
                self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
        return self._image

    def draw_pyside(self, painter: QPainter, camera: Any): 
        if not self.rect.isValid(): return
        
        img_to_draw = self.image 
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect) 
            if painter.window().intersects(screen_rect.toRect()): 
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else: 
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color)

    def alive(self) -> bool: # Static tiles are always "alive" for rendering purposes
        return True


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
                    temp_pixmap.fill(Qt.GlobalColor.transparent) 
                    painter = QPainter(temp_pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    
                    tile_size = float(getattr(C, 'TILE_SIZE', 40.0))
                    rung_qcolor = QColor(139, 69, 19, 220) 
                    pen = QPen(rung_qcolor)
                    
                    num_rungs = int(self.height / (tile_size * 0.35))
                    if num_rungs > 0:
                        rung_spacing = self.height / (num_rungs + 1) 
                        pen.setWidth(max(1, int(tile_size * 0.05)))
                        painter.setPen(pen)
                        for i in range(1, num_rungs + 1):
                            rung_y_pos = i * rung_spacing
                            if rung_y_pos < self.height - 1:
                                painter.drawLine(QPointF(0.0, float(rung_y_pos)), QPointF(self.width, float(rung_y_pos)))
                    
                    rail_thickness = max(2, int(tile_size * 0.075))
                    pen.setWidth(rail_thickness)
                    painter.setPen(pen)
                    left_rail_x = float(rail_thickness / 2.0)
                    right_rail_x = self.width - float(rail_thickness / 2.0)

                    if self.width >= rail_thickness: 
                        painter.drawLine(QPointF(left_rail_x, 0.0), QPointF(left_rail_x, self.height))
                    if self.width >= rail_thickness * 2: 
                        painter.drawLine(QPointF(right_rail_x, 0.0), QPointF(right_rail_x, self.height))
                    elif self.width > rail_thickness: 
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
    
    def alive(self) -> bool:
        return True


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
        else: 
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color)
            
    def alive(self) -> bool:
        return True


class BackgroundTile:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = getattr(C, 'DARK_GRAY', (50, 50, 50)),
                 tile_type: str = "generic_background",
                 image_path: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None):

        self.log_prefix = f"BackgroundTile(type='{tile_type}', rect=({x},{y},{width},{height}))"

        _w = float(width)
        _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width: {width}. Using 1.0."); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height: {height}. Using 1.0."); _h = 1.0
        
        self.width = _w
        self.height = _h

        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        self.tile_type = tile_type
        self.properties = properties if properties is not None else {}
        self.image_path = image_path
        self._image: Optional[QPixmap] = None 

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    @property
    def image(self) -> QPixmap:
        if self._image is None or self._image.isNull():
            pix_w = max(1, int(self.width))
            pix_h = max(1, int(self.height))
            log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h})"
            
            if self.image_path:
                full_path = resource_path(self.image_path)
                loaded_frames = load_gif_frames(full_path) # load_gif_frames returns List[QPixmap]
                if loaded_frames and not loaded_frames[0].isNull():
                    # Scale the loaded image to fit the tile dimensions
                    # Use IgnoreAspectRatio if the tile's rect dimensions are the desired final dimensions.
                    # Use KeepAspectRatio if you want to preserve the image's aspect ratio within the tile's bounds.
                    self._image = loaded_frames[0].scaled(QSize(pix_w, pix_h), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    logger.debug(f"{self.log_prefix}: Loaded image from '{self.image_path}' and scaled to {pix_w}x{pix_h}.")
                else:
                    logger.warning(f"{self.log_prefix}: Failed to load image from '{self.image_path}'. Using color fill.")
                    self._image = QPixmap(pix_w, pix_h)
                    if self._image.isNull(): # Extra check for QPixmap creation itself
                         logger.error(f"{self.log_prefix}: Fallback QPixmap creation FAILED (color fill) for size {pix_w}x{pix_h}.")
                         self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
                    else:
                         self._image.fill(self.q_color)
            else:
                # logger.debug(log_msg_detail + f", Color: {self.q_color.name()}") # For procedural color fill
                self._image = QPixmap(pix_w, pix_h)
                if self._image.isNull():
                    logger.error(f"{self.log_prefix}: QPixmap creation FAILED (isNull=True) for color fill, size {pix_w}x{pix_h}.")
                    self._image = QPixmap(1,1); self._image.fill(Qt.GlobalColor.magenta)
                else:
                    self._image.fill(self.q_color)
        return self._image

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        
        img_to_draw = self.image 
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect) 
            # Background tiles are often large; culling is important.
            # The painter's clipRegion or window is in widget coordinates.
            # screen_rect is also in widget coordinates.
            if painter.window().intersects(screen_rect.toRect()): 
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else:
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color)

    def alive(self) -> bool:
        return True