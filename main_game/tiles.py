#################### START OF FILE: tiles.py ####################

# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6 with deferred QPixmap creation.
Lava class now uses animated GIF. BackgroundTile added.
"""
# version 2.1.5 (Lava animation and GIF loading, BackgroundTile image path)

import sys # For logger fallback
from typing import Optional, Any, Tuple, Dict, List 

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QBrush, QImage # Added QImage
from PySide6.QtCore import QRectF, QPointF, Qt, QSize 
import logging
import time # For monotonic timer

import main_game.constants as C 
from assets import resource_path, load_gif_frames # For image loading

# --- Monotonic Timer (shared by classes in this module) ---
_start_time_tiles_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_tiles_monotonic) * 1000)
# --- End Monotonic Timer ---

# --- Logger Setup ---
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): 
    _tiles_handler = logging.StreamHandler(sys.stdout) 
    _tiles_formatter = logging.Formatter('%(asctime)s - TILES - %(levelname)s - %(message)s')
    _tiles_handler.setFormatter(_tiles_formatter)
    logger.addHandler(_tiles_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False 
    logger.debug("Tiles.py: Basic console logger configured (module-level fallback).")
# --- End Logger Setup ---

class Platform:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = getattr(C, 'GRAY', (128,128,128)), 
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

        self._image: Optional[QPixmap] = None 

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
            # log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h}), Color: {self.q_color.name()}" # Verbose
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

    def alive(self) -> bool: 
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
            # log_msg_detail = f"{self.log_prefix}: Creating QPixmap({pix_w}, {pix_h})" # Verbose
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
                 color_tuple: Tuple[int, int, int] = getattr(C, 'ORANGE_RED', (255, 69, 0)),
                 properties: Optional[Dict[str, Any]] = None): # Added properties
        self.log_prefix = f"Lava(rect=({x},{y},{width},{height}))"
        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width {width}. Using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height {height}. Using 1.0"); _h = 1.0
        self.width = _w; self.height = _h
        
        self.color_tuple_fallback = color_tuple # Color from map data, used as fallback
        self.q_color_fallback = QColor(*self.color_tuple_fallback)
        
        self._frames: List[QPixmap] = []
        self._current_frame_index = 0
        self._last_anim_update = 0
        self._scaled_frames_cache: Dict[Tuple[int, int], List[QPixmap]] = {} # Cache for scaled frames

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
        self.properties = properties if properties is not None else {}

    def _load_frames_once(self):
        if not self._frames: # Load frames only once
            lava_gif_path = getattr(C, 'LAVA_SPRITE_PATH', "characters/assets/lava.gif") 
            full_path = resource_path(lava_gif_path)
            loaded_raw_frames = load_gif_frames(full_path)
            if not loaded_raw_frames or (loaded_raw_frames and loaded_raw_frames[0].isNull()):
                logger.warning(f"{self.log_prefix}: Failed to load GIF from '{full_path}'. Will use color fill fallback.")
                # Fallback frames will be generated on demand by the image property if needed
            else:
                self._frames = loaded_raw_frames # Store original loaded frames
            self._current_frame_index = 0
            self._last_anim_update = get_current_ticks_monotonic()

    def _get_scaled_frames(self, target_width: int, target_height: int) -> List[QPixmap]:
        target_dims = (target_width, target_height)
        if target_dims in self._scaled_frames_cache:
            return self._scaled_frames_cache[target_dims]

        self._load_frames_once() # Ensure original frames are loaded

        scaled_frames_list: List[QPixmap] = []
        if not self._frames or (self._frames and self._frames[0].isNull()): # Fallback to color fill
            pix_w = max(1, target_width); pix_h = max(1, target_height)
            fallback_pixmap = QPixmap(pix_w, pix_h)
            if fallback_pixmap.isNull():
                fallback_pixmap = QPixmap(1,1); fallback_pixmap.fill(Qt.GlobalColor.magenta)
                logger.error(f"{self.log_prefix}: Fallback QPixmap creation FAILED (color fill).")
            else:
                fallback_pixmap.fill(self.q_color_fallback)
            scaled_frames_list = [fallback_pixmap]
        else: # Scale loaded frames
            for original_frame in self._frames:
                if original_frame and not original_frame.isNull():
                    scaled_f = original_frame.scaled(target_width, target_height, 
                                                     Qt.AspectRatioMode.IgnoreAspectRatio, 
                                                     Qt.TransformationMode.SmoothTransformation)
                    scaled_frames_list.append(scaled_f)
                else: # Should not happen if _frames has valid pixmaps
                    fb_scaled = QPixmap(target_width, target_height); fb_scaled.fill(Qt.GlobalColor.magenta)
                    scaled_frames_list.append(fb_scaled)
        
        self._scaled_frames_cache[target_dims] = scaled_frames_list
        return scaled_frames_list

    @property
    def image(self) -> QPixmap:
        render_width = max(1, int(self.width))
        render_height = max(1, int(self.height))
        
        current_scaled_frames = self._get_scaled_frames(render_width, render_height)

        if not current_scaled_frames: # Should be handled by _get_scaled_frames fallback
            logger.error(f"{self.log_prefix}: No valid frames to return for image property after scaling attempt.")
            fallback_img = QPixmap(render_width, render_height)
            fallback_img.fill(Qt.GlobalColor.magenta)
            return fallback_img

        # Animate if multiple frames
        if len(current_scaled_frames) > 1:
            now = get_current_ticks_monotonic() 
            anim_speed = getattr(C, 'ANIM_FRAME_DURATION', 100) * 1.2 # Lava might animate slower
            if now - self._last_anim_update > anim_speed:
                self._last_anim_update = now
                self._current_frame_index = (self._current_frame_index + 1) % len(current_scaled_frames)
        
        return current_scaled_frames[self._current_frame_index]


    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        img_to_draw = self.image # Access the animated or static image
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect)
            if painter.window().intersects(screen_rect.toRect()):
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else: 
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect with q_color_fallback.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color_fallback) # Fallback to color if image fails
            
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
        self._scaled_image_cache: Optional[QPixmap] = None # Cache for the scaled image
        self._last_render_dims: Tuple[int, int] = (0,0) # To track if scaling is needed

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    @property
    def image(self) -> QPixmap:
        render_width = max(1, int(self.width))
        render_height = max(1, int(self.height))

        # Check if cached scaled image is still valid for current dimensions
        if self._scaled_image_cache and not self._scaled_image_cache.isNull() and \
           self._last_render_dims == (render_width, render_height):
            return self._scaled_image_cache

        # If no image path, or if image needs to be (re)created/scaled
        if self._image is None or self._image.isNull() or self._last_render_dims != (render_width, render_height):
            if self.image_path:
                full_path = resource_path(self.image_path)
                loaded_frames = load_gif_frames(full_path) 
                if loaded_frames and not loaded_frames[0].isNull():
                    self._image = loaded_frames[0] # Store the original loaded image
                    logger.debug(f"{self.log_prefix}: Loaded original image from '{self.image_path}'.")
                else:
                    logger.warning(f"{self.log_prefix}: Failed to load image from '{self.image_path}'. Using color fill.")
                    self._image = None # Mark that image loading failed
            else: # No image path, will use color fill
                self._image = None 
        
        # Now, create/scale the pixmap for the current render dimensions
        if self._image and not self._image.isNull(): # We have an original image to scale
            self._scaled_image_cache = self._image.scaled(QSize(render_width, render_height), 
                                                         Qt.AspectRatioMode.IgnoreAspectRatio, 
                                                         Qt.TransformationMode.SmoothTransformation)
        else: # Fallback to color fill
            self._scaled_image_cache = QPixmap(render_width, render_height)
            if self._scaled_image_cache.isNull():
                logger.error(f"{self.log_prefix}: QPixmap creation FAILED for color fill.")
                self._scaled_image_cache = QPixmap(1,1); self._scaled_image_cache.fill(Qt.GlobalColor.magenta)
            else:
                self._scaled_image_cache.fill(self.q_color)
        
        self._last_render_dims = (render_width, render_height)
        return self._scaled_image_cache


    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        
        img_to_draw = self.image # Access the (potentially scaled) image
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

#################### END OF FILE: tiles.py ####################