# main_game/tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6 with deferred QPixmap creation.
Lava class now uses animated GIF. BackgroundTile added.
MODIFIED: `BackgroundTile` now correctly uses `resource_path` for its image path.
"""
# version 2.1.6 (BackgroundTile image path correction)

import sys # For logger fallback
from typing import Optional, Any, Tuple, Dict, List 
import os
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QBrush, QImage
from PySide6.QtCore import QRectF, QPointF, Qt, QSize 
import logging
import time # For monotonic timer

import main_game.constants as C 
from main_game.assets import resource_path, load_gif_frames # Corrected import

# --- Monotonic Timer (shared by classes in this module) ---
_start_time_tiles_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
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
            try:
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
            try:
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
                 properties: Optional[Dict[str, Any]] = None):
        self.log_prefix = f"Lava(rect=({x},{y},{width},{height}))"
        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width {width}. Using 1.0"); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height {height}. Using 1.0"); _h = 1.0
        self.width = _w; self.height = _h
        
        self.color_tuple_fallback = color_tuple
        self.q_color_fallback = QColor(*self.color_tuple_fallback)
        
        self._frames: List[QPixmap] = []
        self._current_frame_index = 0
        self._last_anim_update = 0
        self._scaled_frames_cache: Dict[Tuple[int, int], List[QPixmap]] = {}

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
        self.properties = properties if properties is not None else {}

    def _load_frames_once(self):
        if not self._frames:
            # LAVA_SPRITE_PATH from constants.py is already relative to project root (e.g., "assets/environment/lava.gif")
            lava_gif_path_relative_to_project = getattr(C, 'LAVA_SPRITE_PATH', "assets/environment/lava.gif") 
            full_path = resource_path(lava_gif_path_relative_to_project) # resource_path prepends the absolute base path
            loaded_raw_frames = load_gif_frames(full_path)
            if not loaded_raw_frames or (loaded_raw_frames and loaded_raw_frames[0].isNull()):
                logger.warning(f"{self.log_prefix}: Failed to load GIF from '{full_path}'. Will use color fill fallback.")
            else:
                self._frames = loaded_raw_frames
            self._current_frame_index = 0
            self._last_anim_update = get_current_ticks_monotonic()

    def _get_scaled_frames(self, target_width: int, target_height: int) -> List[QPixmap]:
        target_dims = (target_width, target_height)
        if target_dims in self._scaled_frames_cache:
            return self._scaled_frames_cache[target_dims]

        self._load_frames_once()

        scaled_frames_list: List[QPixmap] = []
        if not self._frames or (self._frames and self._frames[0].isNull()):
            pix_w = max(1, target_width); pix_h = max(1, target_height)
            fallback_pixmap = QPixmap(pix_w, pix_h)
            if fallback_pixmap.isNull():
                fallback_pixmap = QPixmap(1,1); fallback_pixmap.fill(Qt.GlobalColor.magenta)
                logger.error(f"{self.log_prefix}: Fallback QPixmap creation FAILED (color fill).")
            else:
                fallback_pixmap.fill(self.q_color_fallback)
            scaled_frames_list = [fallback_pixmap]
        else:
            for original_frame in self._frames:
                if original_frame and not original_frame.isNull():
                    scaled_f = original_frame.scaled(target_width, target_height, 
                                                     Qt.AspectRatioMode.IgnoreAspectRatio, 
                                                     Qt.TransformationMode.SmoothTransformation)
                    scaled_frames_list.append(scaled_f)
                else:
                    fb_scaled = QPixmap(target_width, target_height); fb_scaled.fill(Qt.GlobalColor.magenta)
                    scaled_frames_list.append(fb_scaled)
        
        self._scaled_frames_cache[target_dims] = scaled_frames_list
        return scaled_frames_list

    @property
    def image(self) -> QPixmap:
        render_width = max(1, int(self.width))
        render_height = max(1, int(self.height))
        
        current_scaled_frames = self._get_scaled_frames(render_width, render_height)

        if not current_scaled_frames:
            logger.error(f"{self.log_prefix}: No valid frames to return for image property after scaling attempt.")
            fallback_img = QPixmap(render_width, render_height)
            fallback_img.fill(Qt.GlobalColor.magenta)
            return fallback_img

        if len(current_scaled_frames) > 1:
            now = get_current_ticks_monotonic() 
            anim_speed = getattr(C, 'ANIM_FRAME_DURATION', 100) * 1.2
            if now - self._last_anim_update > anim_speed:
                self._last_anim_update = now
                self._current_frame_index = (self._current_frame_index + 1) % len(current_scaled_frames)
        
        return current_scaled_frames[self._current_frame_index]


    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self.rect.isValid(): return
        img_to_draw = self.image
        if img_to_draw and not img_to_draw.isNull():
            screen_rect = camera.apply(self.rect)
            if painter.window().intersects(screen_rect.toRect()):
                 painter.drawPixmap(screen_rect.topLeft(), img_to_draw)
        else: 
            logger.warning(f"{self.log_prefix}: image is null during draw_pyside. Drawing solid rect with q_color_fallback.")
            screen_rect_fb = camera.apply(self.rect)
            painter.fillRect(screen_rect_fb, self.q_color_fallback)
            
    def alive(self) -> bool:
        return True


class BackgroundTile:
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: Tuple[int, int, int] = getattr(C, 'DARK_GRAY', (50, 50, 50)),
                 tile_type: str = "generic_background",
                 image_path: Optional[str] = None, # Path relative to project root, e.g., "assets/environment/some_bg.png"
                 properties: Optional[Dict[str, Any]] = None):

        self.log_prefix = f"BackgroundTile(type='{tile_type}', rect=({x},{y},{width},{height}))"

        _w = float(width); _h = float(height)
        if _w <= 0: logger.warning(f"{self.log_prefix}: Non-positive width: {width}. Using 1.0."); _w = 1.0
        if _h <= 0: logger.warning(f"{self.log_prefix}: Non-positive height: {height}. Using 1.0."); _h = 1.0
        
        self.width = _w; self.height = _h
        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)
        self.tile_type = tile_type
        self.properties = properties if properties is not None else {}
        self.image_path_relative_to_project_root = image_path # Store the relative path
        
        self._image_original: Optional[QPixmap] = None # Cache for the original loaded image
        self._image_scaled_for_render: Optional[QPixmap] = None # Cache for the currently scaled image
        self._last_render_dims: Tuple[int, int] = (0,0)

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

    def _load_original_image_once(self):
        if self._image_original is None and self.image_path_relative_to_project_root:
            # `resource_path` expects path relative to project root.
            full_absolute_path = resource_path(self.image_path_relative_to_project_root)
            
            # Background tiles are usually static images, not GIFs.
            # If they could be GIFs, use load_gif_frames here.
            # For PNG/JPG, QPixmap.load() or QImage then QPixmap.fromImage() is fine.
            loaded_pixmap = QPixmap()
            if os.path.exists(full_absolute_path):
                if not loaded_pixmap.load(full_absolute_path):
                    logger.warning(f"{self.log_prefix}: QPixmap.load() FAILED for image '{full_absolute_path}'.")
                    self._image_original = None # Mark as failed
                else:
                    self._image_original = loaded_pixmap
                    logger.debug(f"{self.log_prefix}: Loaded original image from '{full_absolute_path}'.")
            else:
                logger.warning(f"{self.log_prefix}: Image file NOT FOUND at '{full_absolute_path}'.")
                self._image_original = None # Mark as failed
        elif self.image_path_relative_to_project_root is None:
            self._image_original = None # No path, so no original image

    @property
    def image(self) -> QPixmap:
        render_width = max(1, int(self.width))
        render_height = max(1, int(self.height))

        if self._image_scaled_for_render and not self._image_scaled_for_render.isNull() and \
           self._last_render_dims == (render_width, render_height):
            return self._image_scaled_for_render

        self._load_original_image_once() # Ensure original is loaded if path exists

        if self._image_original and not self._image_original.isNull():
            self._scaled_image_cache = self._image_original.scaled(QSize(render_width, render_height), 
                                                         Qt.AspectRatioMode.IgnoreAspectRatio, 
                                                         Qt.TransformationMode.SmoothTransformation)
        else: # Fallback to color fill if no original image or loading failed
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