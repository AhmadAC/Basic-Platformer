# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper. Refactored for PySide6.
Chest now has gravity applied by an external physics step.
"""
# version 2.0.6 (Chest overhaul: physics, state machine, fade)
import os
import sys
import random
from typing import Dict, Optional, Any, List, Tuple
import time
import math # For math.ceil

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QSize, Qt, QPointF

import constants as C
from assets import load_gif_frames, resource_path

try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_ITEMS: {msg}") # Added *args
    def info(msg, *args, **kwargs): print(f"INFO_ITEMS: {msg}")   # Added *args
    def warning(msg, *args, **kwargs): print(f"WARNING_ITEMS: {msg}") # Added *args

_SCRIPT_LOGGING_ENABLED = True # For per-script logging control

_start_time_items = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_items) * 1000)


class Chest:
    def __init__(self, x: float, y: float): # x, y are for midbottom
        self._valid_init = True
        self.all_frames: List[QPixmap] = []

        full_chest_animation_path = resource_path(getattr(C, 'CHEST_CLOSED_SPRITE_PATH', "characters/items/chest.gif"))
        self.all_frames = load_gif_frames(full_chest_animation_path)
        self.initial_image_frames = self.all_frames # Keep a reference

        self.num_opening_frames = 0
        if not self.all_frames or self._is_placeholder_qpixmap(self.all_frames[0]):
            if _SCRIPT_LOGGING_ENABLED: warning(f"Chest: Failed to load animation frames from '{full_chest_animation_path}'. Using placeholder.")
            self._valid_init = False
            self.all_frames = [
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'YELLOW', (255,255,0))), "ChestClosed"),
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "ChestOpen")
            ]
            self.num_opening_frames = 1 # Placeholder has 2 frames, 1st is closed, 2nd is open
        else:
            self.num_opening_frames = len(self.all_frames)

        self.state = 'closed'
        self.is_collected_flag_internal = False # True when interaction starts
        self.player_to_heal: Optional[Any] = None # Stores player who opened it

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

        # Physics attributes
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.acc_x = 0.0 # For when pushed
        self.on_ground = False
        self._gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7)) # Using player gravity
        self._friction = float(getattr(C, 'CHEST_FRICTION', -0.12))
        self._max_speed_x = float(getattr(C, 'CHEST_MAX_SPEED_X', 3.0))

        # State-specific timers and attributes
        self.alpha = 255 # 0-255
        self.opened_visible_start_time = 0 # Time when 'opened_visible' state began
        self.fading_start_time = 0         # Time when 'fading' state began
        self.fade_duration_ms = int(getattr(C, 'CHEST_FADE_OUT_DURATION_MS', 300))
        self.open_display_duration_ms = int(getattr(C, 'CHEST_OPEN_DISPLAY_DURATION_MS', 300))

        if not self._valid_init:
             self.image = self.all_frames[0]
             self._update_rect_from_image_and_pos()
        if _SCRIPT_LOGGING_ENABLED: debug(f"Chest initialized at ({x},{y}). Valid: {self._valid_init}")

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        # Simplified check, assumes placeholder might be small
        if pixmap.width() <= 40 and pixmap.height() <= 60:
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
        if self.state == 'collected' or self.is_collected_flag_internal: # Don't apply physics if collected or in opening sequence
            self.vel_x = 0.0
            self.acc_x = 0.0
            if self.state not in ['opening', 'opened_visible', 'fading']: # Allow gravity if it was opening mid-air then landed
                self.vel_y = 0.0
            return

        # Horizontal movement (pushed)
        self.vel_x += self.acc_x * dt_sec * C.FPS
        if self.on_ground and self.acc_x == 0: # Apply friction
            friction_force = self.vel_x * self._friction
            if abs(self.vel_x) > 0.1:
                self.vel_x += friction_force * dt_sec * C.FPS
            else:
                self.vel_x = 0.0
        self.vel_x = max(-self._max_speed_x, min(self._max_speed_x, self.vel_x))
        self.pos_midbottom.setX(self.pos_midbottom.x() + self.vel_x * dt_sec * C.FPS)
        self.acc_x = 0.0 # Reset horizontal acceleration each frame (applied by external push)

        # Vertical movement (gravity)
        if not self.on_ground:
            self.vel_y += self._gravity * dt_sec * C.FPS
            self.vel_y = min(self.vel_y, getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))
        else: # If on_ground is true (set by external collision check), stop vertical velocity
            self.vel_y = 0.0

        self.pos_midbottom.setY(self.pos_midbottom.y() + self.vel_y * dt_sec * C.FPS)
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

                # Ensure current_frame_index is valid
                self.current_frame_index = max(0, min(self.current_frame_index, len(self.all_frames) - 1))
                
                if self.all_frames: # Check if all_frames is not empty
                    self.image = self.all_frames[self.current_frame_index]
                    self._update_rect_from_image_and_pos()

        elif self.state == 'opened_visible':
            if now - self.opened_visible_start_time > self.open_display_duration_ms:
                self.state = 'fading'
                self.fading_start_time = now
                self.alpha = 255 # Start fade from full opacity
                if _SCRIPT_LOGGING_ENABLED: info("Chest display duration ended. Starting fade.")

        elif self.state == 'fading':
            elapsed_fade_time = now - self.fading_start_time
            if elapsed_fade_time >= self.fade_duration_ms:
                self.alpha = 0
                self.state = 'collected'
                self.kill() # Mark as no longer active
                if _SCRIPT_LOGGING_ENABLED: info("Chest fade complete. State: collected.")
            else:
                self.alpha = int(255 * (1.0 - (elapsed_fade_time / self.fade_duration_ms)))
                self.alpha = max(0, min(255, self.alpha)) # Clamp alpha

        # Ensure image is correct for non-animating states
        if self.state == 'closed':
            self.current_frame_index = 0
            if self.all_frames: self.image = self.all_frames[0]
        elif self.state == 'opened_visible':
             self.current_frame_index = self.num_opening_frames - 1
             if self.all_frames and self.current_frame_index < len(self.all_frames):
                 self.image = self.all_frames[self.current_frame_index]

        if self.state != 'opening': # Always update rect if not in opening animation (which handles it)
            self._update_rect_from_image_and_pos()


    def collect(self, player: Any):
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed' or not self._alive:
            return

        if _SCRIPT_LOGGING_ENABLED: info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True
        self.player_to_heal = player
        # Chest becomes static once interacted with (gravity/pushing stops)
        self.on_ground = True # Effectively
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.acc_x = 0.0

        self.state = 'opening'
        self.current_frame_index = 0
        self.animation_timer = get_current_ticks_monotonic()
        # Image will be updated by the 'opening' state in update()

    def get_network_data(self) -> Dict[str, Any]:
        return {
            'pos_midbottom': (self.pos_midbottom.x(), self.pos_midbottom.y()),
            'vel_x': self.vel_x, # Send velocity for client prediction if needed
            'vel_y': self.vel_y,
            'on_ground': self.on_ground,
            'is_collected_internal': self.is_collected_flag_internal,
            'chest_state': self.state,
            'animation_timer': self.animation_timer,
            'opened_visible_start_time': self.opened_visible_start_time,
            'fading_start_time': self.fading_start_time,
            'current_frame_index': self.current_frame_index,
            'alpha': self.alpha,
            '_alive': self._alive
        }

    def set_network_data(self, data: Dict[str, Any]):
        server_chest_pos_midbottom_tuple = data.get('pos_midbottom')
        server_chest_state = data.get('chest_state')

        self._alive = data.get('_alive', self._alive)
        if not self._alive:
             self.state = 'collected' # Or some other inactive state
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

        # Ensure frame index is valid and update image
        if self.all_frames: # Only if frames are loaded
            self.current_frame_index = max(0, min(self.current_frame_index, len(self.all_frames) -1))
            self.image = self.all_frames[self.current_frame_index]
        elif self._valid_init: # If valid_init but no frames, this is an issue
            if _SCRIPT_LOGGING_ENABLED: warning("Chest.set_network_data: Valid init but no frames. This should not happen.")
            self.image = self._create_placeholder_qpixmap(QColor(255,0,255), "NetErr") # Magenta error

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
                painter.setOpacity(current_opacity) # Restore original opacity
            else:
                painter.drawPixmap(screen_rect.topLeft(), self.image)