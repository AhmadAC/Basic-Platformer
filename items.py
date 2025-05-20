#################### START OF FILE: items.py ####################

# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper. Refactored for PySide6.
"""
# version 2.0.3 (Chest uses single animation, heals after opening anim)
import os
import sys
import random
from typing import Dict, Optional, Any, List, Tuple
import time

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QSize, Qt, QPointF

import constants as C
from assets import load_gif_frames, resource_path

try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_ITEMS: {msg}")
    def info(msg): print(f"INFO_ITEMS: {msg}")
    def warning(msg): print(f"WARNING_ITEMS: {msg}")

_start_time_items = time.monotonic()
def get_current_ticks():
    return int((time.monotonic() - _start_time_items) * 1000)


class Chest:
    """
    A chest that starts closed, plays an opening animation when interacted with,
    and then stays on its last (open) frame. Heals player after opening.
    """
    def __init__(self, x: float, y: float): # x, y are for midbottom
        self._valid_init = True
        self.all_frames: List[QPixmap] = [] # Will hold all frames: closed -> opening -> open

        # CHEST_CLOSED_SPRITE_PATH should now point to a GIF that includes
        # the closed state, the opening animation, and the final open state.
        full_chest_animation_path = resource_path(C.CHEST_CLOSED_SPRITE_PATH)
        self.all_frames = load_gif_frames(full_chest_animation_path)

        if not self.all_frames or self._is_placeholder_qpixmap(self.all_frames[0]):
            warning(f"Chest: Failed to load animation frames from '{full_chest_animation_path}'. Using placeholder.")
            self._valid_init = False
            # Create a simple 2-frame placeholder: closed and open
            self.all_frames = [
                self._create_placeholder_qpixmap(QColor(*C.YELLOW), "ChestClosed"),
                self._create_placeholder_qpixmap(QColor(*C.BLUE), "ChestOpen")
            ]
            self.num_opening_frames = 1 # Placeholder has 1 frame for "opening"
        else:
            # Assume the animation sequence is:
            # Frame 0: Closed state
            # Frame 1 to N-1: Opening animation frames
            # Frame N: Fully open state (last frame)
            self.num_opening_frames = len(self.all_frames) -1 # All frames after the first are "opening" to the last "open"

        self.state = 'closed' # Initial state
        self.is_collected_flag_internal = False
        self.player_to_heal: Optional[Any] = None

        self.image: QPixmap = self.all_frames[0] # Start with the first frame (closed)

        img_width = self.image.width()
        img_height = self.image.height()
        rect_x = float(x - img_width / 2.0)
        rect_y = float(y - img_height)
        self.rect = QRectF(rect_x, rect_y, float(img_width), float(img_height))
        self.pos_midbottom = QPointF(float(x), float(y))

        self.current_frame_index = 0 # Index within self.all_frames
        self.animation_timer = get_current_ticks()
        self._alive = True

        if not self._valid_init:
             self.image = self.all_frames[0] # Ensure image is set even if placeholder
             self._update_rect_from_image_and_pos()

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
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
        pixmap = QPixmap(30, 30)
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*C.BLACK))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(8); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"ITEMS PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        if self.image and not self.image.isNull():
            img_width = float(self.image.width())
            img_height = float(self.image.height())
            rect_x = self.pos_midbottom.x() - img_width / 2.0
            rect_y = self.pos_midbottom.y() - img_height
            self.rect.setRect(rect_x, rect_y, img_width, img_height)
        else:
            self.rect.setRect(self.pos_midbottom.x() - 15, self.pos_midbottom.y() - 30, 30, 30)

    def alive(self) -> bool: return self._alive
    def kill(self): self._alive = False

    def update(self, dt_sec: float):
        if self.state == 'killed' or not self._alive:
            return

        now = get_current_ticks()
        anim_speed_ms = int(C.ANIM_FRAME_DURATION * 0.7) # Opening animation speed

        if self.state == 'opening':
            if now - self.animation_timer > anim_speed_ms:
                self.animation_timer = now
                self.current_frame_index += 1

                if self.current_frame_index >= len(self.all_frames): # Animation finished
                    self.current_frame_index = len(self.all_frames) - 1 # Stay on last frame
                    self.state = 'opened'
                    info(f"Chest opened for Player {getattr(self.player_to_heal, 'player_id', 'Unknown')}. Healing.")
                    if self.player_to_heal and hasattr(self.player_to_heal, 'heal_to_full'):
                        self.player_to_heal.heal_to_full()
                    # Chest now stays open on the last frame. No fading or killing state after opening.
                
                if self.all_frames and 0 <= self.current_frame_index < len(self.all_frames):
                    self.image = self.all_frames[self.current_frame_index]
                    self._update_rect_from_image_and_pos()
        # If state is 'closed' or 'opened', it's static, no animation update needed here.
        # The image is set to all_frames[0] for 'closed'
        # and all_frames[last_index] for 'opened'.

    def collect(self, player: Any):
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed' or not self._alive:
            return

        info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True # Mark as collected to prevent re-trigger
        self.player_to_heal = player

        self.state = 'opening'
        self.current_frame_index = 0 # Start opening animation from the first frame (which is the closed state)
                                     # The animation will progress to subsequent frames.
        self.animation_timer = get_current_ticks()

        if self.all_frames and self.all_frames[0] and not self.all_frames[0].isNull():
            # Image will be updated frame-by-frame in update() method
            pass
        else:
            warning("Chest: Collect called, but animation frames are invalid. Chest might not animate correctly.")

    def get_network_data(self) -> Dict[str, Any]:
        """Gets data for network synchronization."""
        return {
            'pos_center': (self.rect.center().x(), self.rect.center().y()),
            'is_collected_internal': self.is_collected_flag_internal,
            'chest_state': self.state,
            'animation_timer': self.animation_timer, # Sync animation timer for opening
            'current_frame_index': self.current_frame_index,
            # No need for fade_alpha, time_opened_start if it just stays open
        }

    def set_network_data(self, data: Dict[str, Any]):
        """Sets state from network data."""
        server_chest_pos_center_tuple = data.get('pos_center')
        server_chest_state = data.get('chest_state')

        if server_chest_state == 'killed': # Server says it's gone
            self.kill()
            return
        
        if server_chest_pos_center_tuple:
             self.rect.moveCenter(QPointF(server_chest_pos_center_tuple[0], server_chest_pos_center_tuple[1]))
             self.pos_midbottom = QPointF(self.rect.center().x(), self.rect.bottom())

        old_state = self.state
        self.state = server_chest_state
        self.is_collected_flag_internal = data.get('is_collected_internal', False)
        
        if self.state == 'opening' and old_state != 'opening': # If server initiated opening
            self.animation_timer = data.get('animation_timer', get_current_ticks())
            self.current_frame_index = data.get('current_frame_index', 0)
        elif self.state == 'opened':
            self.current_frame_index = len(self.all_frames) - 1 if self.all_frames else 0
        elif self.state == 'closed':
            self.current_frame_index = 0
        
        if self.all_frames and 0 <= self.current_frame_index < len(self.all_frames):
            self.image = self.all_frames[self.current_frame_index]
            self._update_rect_from_image_and_pos()
        elif self.all_frames: # Fallback to first frame if index is bad
            self.image = self.all_frames[0]
            self._update_rect_from_image_and_pos()


#################### END OF FILE: items.py ####################