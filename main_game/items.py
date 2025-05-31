# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper. Refactored for PySide6.
Chest now has gravity applied by an external physics step.
MODIFIED: Path for CHEST_CLOSED_SPRITE_PATH is now correctly handled via constants.py and resource_path.
MODIFIED: Corrected logger fallback and import path.
"""
# version 2.0.7 (Asset path refactor, Logger fix)
import os
import sys # Added for logger fallback
import random
from typing import Dict, Optional, Any, List, Tuple
import time
import math # For math.ceil

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QSize, Qt, QPointF

import main_game.constants as C
from main_game.assets import load_gif_frames, resource_path

# --- Logger Setup ---
import logging
_items_logger_instance = logging.getLogger(__name__ + "_items_internal_fallback")
if not _items_logger_instance.hasHandlers():
    _handler_items_fb = logging.StreamHandler(sys.stdout)
    _formatter_items_fb = logging.Formatter('ITEMS (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_items_fb.setFormatter(_formatter_items_fb)
    _items_logger_instance.addHandler(_handler_items_fb)
    _items_logger_instance.setLevel(logging.DEBUG)
    _items_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _items_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _items_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _items_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _items_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _items_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info
debug = _fallback_log_debug
warning = _fallback_log_warning
error = _fallback_log_error
critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info
    debug = project_debug
    warning = project_warning
    error = project_error
    critical = project_critical
    debug("Items: Successfully aliased project's logger functions from main_game.logger.")
except ImportError:
    critical("CRITICAL ITEMS: Failed to import logger from main_game.logger. Using internal fallback print statements for logging.")
except Exception as e_logger_init_items:
    critical(f"CRITICAL ITEMS: Unexpected error during logger setup from main_game.logger: {e_logger_init_items}. Using internal fallback.")
# --- End Logger Setup ---

_SCRIPT_LOGGING_ENABLED = True

_start_time_items = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_items) * 1000)


class Chest:
    def __init__(self, x: float, y: float): # x, y are for midbottom
        self._valid_init = True
        self.all_frames: List[QPixmap] = []

        # The path to chest.gif is now correctly prefixed with "assets/items/" in constants.py
        # getattr will fetch this updated path. resource_path will resolve it.
        chest_sprite_path_constant = getattr(C, 'CHEST_CLOSED_SPRITE_PATH', "assets/items/chest.gif") # Fallback if constant somehow missing
        full_chest_animation_path = resource_path(chest_sprite_path_constant)
        
        if _SCRIPT_LOGGING_ENABLED: debug(f"Chest: Attempting to load animation from: '{full_chest_animation_path}' (resolved from constant: '{chest_sprite_path_constant}')")

        self.all_frames = load_gif_frames(full_chest_animation_path)
        self.initial_image_frames = self.all_frames 

        self.num_opening_frames = 0
        if not self.all_frames or self._is_placeholder_qpixmap(self.all_frames[0]):
            if _SCRIPT_LOGGING_ENABLED: warning(f"Chest: Failed to load animation frames from '{full_chest_animation_path}'. Using placeholder.")
            self._valid_init = False
            self.all_frames = [
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'YELLOW', (255,255,0))), "ChestClosed"),
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "ChestOpen")
            ]
            self.num_opening_frames = 1
        else:
            self.num_opening_frames = len(self.all_frames)

        self.state = 'closed'
        self.is_collected_flag_internal = False
        self.player_to_heal: Optional[Any] = None

        self.image: QPixmap = self.all_frames[0]

        img_width = self.image.width()
        img_height = self.image.height()
        rect_x = float(x - img_width / 2.0)
        rect_y = float(y - img_height)
        self.rect = QRectF(rect_x, rect_y, float(img_width), float(img_height))
        self.pos_midbottom = QPointF(float(x), float(y))

        self.current_frame_index = 0
        self.animation_timer = 0
        self._alive = True

        self.vel_x = 0.0
        self.vel_y = 0.0
        self.acc_x = 0.0
        self.on_ground = False
        self._gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
        self._friction = float(getattr(C, 'CHEST_FRICTION', -0.12))
        self._max_speed_x = float(getattr(C, 'CHEST_MAX_SPEED_X', 3.0))

        self.alpha = 255
        self.opened_visible_start_time = 0
        self.fading_start_time = 0
        self.fade_duration_ms = int(getattr(C, 'CHEST_FADE_OUT_DURATION_MS', 300))
        self.open_display_duration_ms = int(getattr(C, 'CHEST_OPEN_DISPLAY_DURATION_MS', 300))

        if not self._valid_init:
             self.image = self.all_frames[0]
             self._update_rect_from_image_and_pos()
        if _SCRIPT_LOGGING_ENABLED: debug(f"Chest initialized at ({x},{y}). Valid: {self._valid_init}")

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.width() <= 40 and pixmap.height() <= 60: # Common placeholder size
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_yellow = QColor(*getattr(C, 'YELLOW', (255,255,0)))
                if color_at_origin in [qcolor_red, qcolor_blue, qcolor_yellow]:
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        placeholder_size = getattr(C, 'TILE_SIZE', 30)
        pixmap = QPixmap(placeholder_size, placeholder_size)
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0))))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, placeholder_size // 4)); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e:
            if _SCRIPT_LOGGING_ENABLED: info(f"ITEMS PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        if self.image and not self.image.isNull():
            img_width = float(self.image.width())
            img_height = float(self.image.height())
            rect_x = self.pos_midbottom.x() - img_width / 2.0
            rect_y = self.pos_midbottom.y() - img_height
            self.rect.setRect(rect_x, rect_y, img_width, img_height)
        elif hasattr(self, 'rect'):
            placeholder_size = getattr(C, 'TILE_SIZE', 30)
            self.rect.setRect(self.pos_midbottom.x() - placeholder_size / 2.0,
                              self.pos_midbottom.y() - placeholder_size,
                              float(placeholder_size), float(placeholder_size))

    def alive(self) -> bool: return self._alive
    def kill(self):
        self._alive = False
        if _SCRIPT_LOGGING_ENABLED: debug(f"Chest killed. State: {self.state}")

    def apply_physics_step(self, dt_sec: float):
        if self.state == 'collected' or self.is_collected_flag_internal:
            self.vel_x = 0.0
            self.acc_x = 0.0
            if self.state not in ['opening', 'opened_visible', 'fading']:
                self.vel_y = 0.0
            return

        self.vel_x += self.acc_x # Assuming acc_x is change per frame
        if self.on_ground and self.acc_x == 0:
            friction_force = self.vel_x * self._friction
            if abs(self.vel_x) > 0.1:
                self.vel_x += friction_force
            else:
                self.vel_x = 0.0
        self.vel_x = max(-self._max_speed_x, min(self._max_speed_x, self.vel_x))
        self.pos_midbottom.setX(self.pos_midbottom.x() + self.vel_x) # Assuming vel_x is units/frame
        self.acc_x = 0.0

        if not self.on_ground:
            self.vel_y += self._gravity # Assuming _gravity is change per frame
            self.vel_y = min(self.vel_y, getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))
        else:
            self.vel_y = 0.0

        self.pos_midbottom.setY(self.pos_midbottom.y() + self.vel_y) # Assuming vel_y is units/frame
        self._update_rect_from_image_and_pos()

    def update(self, dt_sec: float):
        if self.state == 'collected' or not self._alive:
            return

        now = get_current_ticks_monotonic()
        anim_speed_ms = int(getattr(C, 'CHEST_ANIM_FRAME_DURATION_MS', C.ANIM_FRAME_DURATION * 0.7))

        if self.state == 'opening':
            if now - self.animation_timer > anim_speed_ms:
                self.animation_timer = now
                self.current_frame_index += 1

                if self.current_frame_index >= self.num_opening_frames:
                    self.current_frame_index = self.num_opening_frames - 1
                    self.state = 'opened_visible'
                    self.opened_visible_start_time = now
                    if _SCRIPT_LOGGING_ENABLED: info(f"Chest opened for Player {getattr(self.player_to_heal, 'player_id', 'Unknown')}. Healing.")
                    if self.player_to_heal and hasattr(self.player_to_heal, 'heal_to_full'):
                        self.player_to_heal.heal_to_full()

                self.current_frame_index = max(0, min(self.current_frame_index, len(self.all_frames) - 1))
                
                if self.all_frames:
                    self.image = self.all_frames[self.current_frame_index]
                    self._update_rect_from_image_and_pos()

        elif self.state == 'opened_visible':
            if now - self.opened_visible_start_time > self.open_display_duration_ms:
                self.state = 'fading'
                self.fading_start_time = now
                self.alpha = 255
                if _SCRIPT_LOGGING_ENABLED: info("Chest display duration ended. Starting fade.")

        elif self.state == 'fading':
            elapsed_fade_time = now - self.fading_start_time
            if elapsed_fade_time >= self.fade_duration_ms:
                self.alpha = 0
                self.state = 'collected'
                self.kill()
                if _SCRIPT_LOGGING_ENABLED: info("Chest fade complete. State: collected.")
            else:
                self.alpha = int(255 * (1.0 - (elapsed_fade_time / self.fade_duration_ms)))
                self.alpha = max(0, min(255, self.alpha))

        if self.state == 'closed':
            self.current_frame_index = 0
            if self.all_frames: self.image = self.all_frames[0]
        elif self.state == 'opened_visible':
             self.current_frame_index = self.num_opening_frames - 1
             if self.all_frames and self.current_frame_index < len(self.all_frames):
                 self.image = self.all_frames[self.current_frame_index]

        if self.state != 'opening':
            self._update_rect_from_image_and_pos()


    def collect(self, player: Any):
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed' or not self._alive:
            return

        if _SCRIPT_LOGGING_ENABLED: info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True
        self.player_to_heal = player
        self.on_ground = True
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.acc_x = 0.0

        self.state = 'opening'
        self.current_frame_index = 0
        self.animation_timer = get_current_ticks_monotonic()

    def get_network_data(self) -> Dict[str, Any]:
        return {
            'pos_midbottom': (self.pos_midbottom.x(), self.pos_midbottom.y()),
            'vel_x': self.vel_x,
            'vel_y': self.vel_y,
            'on_ground': self.on_ground,
            'is_collected_internal': self.is_collected_flag_internal,
            'chest_state': self.state,
            'animation_timer': self.animation_timer,
            'opened_visible_start_time': self.opened_visible_start_time,
            'fading_start_time': self.fading_start_time,
            'current_frame_index': self.current_frame_index,
            'alpha': self.alpha,
            '_alive': self._alive,
            '_valid_init': self._valid_init # Send validity in case client needs to create it
        }

    def set_network_data(self, data: Dict[str, Any]):
        server_chest_pos_midbottom_tuple = data.get('pos_midbottom')
        server_chest_state = data.get('chest_state')

        self._valid_init = data.get('_valid_init', self._valid_init) # Sync validity
        self._alive = data.get('_alive', self._alive)
        if not self._alive:
             self.state = 'collected'
             return
        if not self._valid_init: # If server says it's not valid, reflect that
            self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'YELLOW', (255,255,0))), "InvChest")
            self._update_rect_from_image_and_pos()
            return

        if server_chest_pos_midbottom_tuple:
             self.pos_midbottom.setX(float(server_chest_pos_midbottom_tuple[0]))
             self.pos_midbottom.setY(float(server_chest_pos_midbottom_tuple[1]))

        self.vel_x = data.get('vel_x', self.vel_x)
        self.vel_y = data.get('vel_y', self.vel_y)
        self.on_ground = data.get('on_ground', self.on_ground)

        old_state = self.state
        self.state = server_chest_state if server_chest_state else self.state
        self.is_collected_flag_internal = data.get('is_collected_internal', self.is_collected_flag_internal)
        self.alpha = data.get('alpha', self.alpha)
        self.animation_timer = data.get('animation_timer', self.animation_timer)
        self.opened_visible_start_time = data.get('opened_visible_start_time', self.opened_visible_start_time)
        self.fading_start_time = data.get('fading_start_time', self.fading_start_time)
        self.current_frame_index = data.get('current_frame_index', self.current_frame_index)

        if self.all_frames:
            self.current_frame_index = max(0, min(self.current_frame_index, len(self.all_frames) -1))
            self.image = self.all_frames[self.current_frame_index]
        elif self._valid_init:
            if _SCRIPT_LOGGING_ENABLED: warning("Chest.set_network_data: Valid init but no frames. This should not happen.")
            self.image = self._create_placeholder_qpixmap(QColor(255,0,255), "NetErr")

        self._update_rect_from_image_and_pos()

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self._alive or self.state == 'collected' or not self.rect.isValid() or not self.image or self.image.isNull():
            return

        screen_rect = camera.apply(self.rect)
        if painter.window().intersects(screen_rect.toRect()):
            if self.alpha < 255:
                current_opacity = painter.opacity()
                painter.setOpacity(self.alpha / 255.0)
                painter.drawPixmap(screen_rect.topLeft(), self.image)
                painter.setOpacity(current_opacity)
            else:
                painter.drawPixmap(screen_rect.topLeft(), self.image)