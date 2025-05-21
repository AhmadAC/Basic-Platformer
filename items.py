# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper. Refactored for PySide6.
Chest now has gravity applied by an external physics step.
"""
# version 2.0.5 (Chest gravity handled externally, removed platform dependency)
import os
import sys
import random
from typing import Dict, Optional, Any, List, Tuple
import time

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QSize, Qt, QPointF

import constants as C
from assets import load_gif_frames, resource_path
# No longer need to import Platform here

try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_ITEMS: {msg}")
    def info(msg): print(f"INFO_ITEMS: {msg}")
    def warning(msg): print(f"WARNING_ITEMS: {msg}")

_start_time_items = time.monotonic()
def get_current_ticks_monotonic(): 
    return int((time.monotonic() - _start_time_items) * 1000)


class Chest:
    def __init__(self, x: float, y: float): # x, y are for midbottom
        self._valid_init = True
        self.all_frames: List[QPixmap] = [] 

        full_chest_animation_path = resource_path(getattr(C, 'CHEST_CLOSED_SPRITE_PATH', "characters/items/chest.gif"))
        self.all_frames = load_gif_frames(full_chest_animation_path)
        self.initial_image_frames = self.all_frames 

        if not self.all_frames or self._is_placeholder_qpixmap(self.all_frames[0]):
            warning(f"Chest: Failed to load animation frames from '{full_chest_animation_path}'. Using placeholder.")
            self._valid_init = False
            self.all_frames = [
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'YELLOW', (255,255,0))), "ChestClosed"),
                self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "ChestOpen")
            ]
            self.num_opening_frames = 1 
        else:
            self.num_opening_frames = len(self.all_frames) -1 

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
        self.animation_timer = get_current_ticks_monotonic()
        self._alive = True
        
        # Physics attributes (velocity and state)
        self.vel_y = 0.0  
        self.on_ground = False 
        self._gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7)) # Using player gravity for now

        if not self._valid_init:
             self.image = self.all_frames[0] 
             self._update_rect_from_image_and_pos()

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        # ... (implementation as before) ...
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40):
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0))))
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                qcolor_yellow = QColor(*(getattr(C, 'YELLOW', (255,255,0))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue or color_at_origin == qcolor_yellow:
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        # ... (implementation as before) ...
        placeholder_size = getattr(C, 'TILE_SIZE', 30)
        pixmap = QPixmap(placeholder_size, placeholder_size)
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*(getattr(C, 'BLACK', (0,0,0)))))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, placeholder_size // 4)); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: info(f"ITEMS PlaceholderFontError: {e}") 
        painter.end()
        return pixmap
        
    def _update_rect_from_image_and_pos(self):
        # ... (implementation as before) ...
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
    def kill(self): self._alive = False

    def apply_physics_step(self, dt_sec: float):
        """Applies gravity if not collected and not on ground."""
        if not self.is_collected_flag_internal and self.state != 'opening' and self.state != 'opened' and not self.on_ground:
            self.vel_y += self._gravity * dt_sec * C.FPS # Consistent scaling
            self.vel_y = min(self.vel_y, getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))
            
            self.pos_midbottom.setY(self.pos_midbottom.y() + self.vel_y * dt_sec * C.FPS)
            self._update_rect_from_image_and_pos()
        elif self.is_collected_flag_internal or self.on_ground:
            self.vel_y = 0.0


    def update(self, dt_sec: float): # Removed platforms_list from here
        if self.state == 'killed' or not self._alive:
            return

        # Gravity and basic position update is now handled by apply_physics_step
        # which will be called by the main game loop before collision checks.
        # The collision checks (including landing on ground) will also be handled by the main game loop.

        # --- Animation Logic ---
        now = get_current_ticks_monotonic()
        anim_speed_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 80) * 0.7) 

        if self.state == 'opening':
            if now - self.animation_timer > anim_speed_ms:
                self.animation_timer = now
                self.current_frame_index += 1

                if self.current_frame_index >= len(self.all_frames): 
                    self.current_frame_index = len(self.all_frames) - 1 
                    self.state = 'opened'
                    info(f"Chest opened for Player {getattr(self.player_to_heal, 'player_id', 'Unknown')}. Healing.")
                    if self.player_to_heal and hasattr(self.player_to_heal, 'heal_to_full'):
                        self.player_to_heal.heal_to_full()
                
                if self.all_frames and 0 <= self.current_frame_index < len(self.all_frames):
                    self.image = self.all_frames[self.current_frame_index]
                    self._update_rect_from_image_and_pos()

    def collect(self, player: Any):
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed' or not self._alive:
            return

        info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True 
        self.player_to_heal = player
        self.on_ground = True # Interaction stops physics, effectively makes it grounded
        self.vel_y = 0.0

        self.state = 'opening'
        self.current_frame_index = 0 
        self.animation_timer = get_current_ticks_monotonic()


    def get_network_data(self) -> Dict[str, Any]:
        # ... (implementation as before, includes vel_y and on_ground) ...
        return {
            'pos_center': (self.rect.center().x(), self.rect.center().y()),
            'pos_midbottom': (self.pos_midbottom.x(), self.pos_midbottom.y()), 
            'vel_y': self.vel_y,
            'on_ground': self.on_ground,
            'is_collected_internal': self.is_collected_flag_internal,
            'chest_state': self.state,
            'animation_timer': self.animation_timer, 
            'current_frame_index': self.current_frame_index,
            '_alive': self._alive 
        }

    def set_network_data(self, data: Dict[str, Any]):
        # ... (implementation as before, updates vel_y and on_ground) ...
        server_chest_pos_midbottom_tuple = data.get('pos_midbottom')
        server_chest_state = data.get('chest_state')
        
        self._alive = data.get('_alive', self._alive) 
        if not self._alive:
             self.state = 'killed' 
             return

        if server_chest_pos_midbottom_tuple:
             self.pos_midbottom.setX(float(server_chest_pos_midbottom_tuple[0]))
             self.pos_midbottom.setY(float(server_chest_pos_midbottom_tuple[1]))
        
        self.vel_y = data.get('vel_y', self.vel_y)
        self.on_ground = data.get('on_ground', self.on_ground)
        
        old_state = self.state
        self.state = server_chest_state if server_chest_state else self.state 
        self.is_collected_flag_internal = data.get('is_collected_internal', False)
        
        if self.state == 'opening' and old_state != 'opening': 
            self.animation_timer = data.get('animation_timer', self.animation_timer)
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
        elif self.state == 'opened':
            self.current_frame_index = len(self.all_frames) - 1 if self.all_frames else 0
        elif self.state == 'closed':
            self.current_frame_index = 0
        
        if self.all_frames and 0 <= self.current_frame_index < len(self.all_frames):
            self.image = self.all_frames[self.current_frame_index]
        elif self.all_frames: 
            self.image = self.all_frames[0] 
        
        self._update_rect_from_image_and_pos() 

    def draw_pyside(self, painter: QPainter, camera: Any):
        # ... (implementation as before) ...
        if not self._alive or not self.rect.isValid() or not self.image or self.image.isNull():
            return
        
        screen_rect = camera.apply(self.rect)
        if painter.window().intersects(screen_rect.toRect()): 
            painter.drawPixmap(screen_rect.topLeft(), self.image)