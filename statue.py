#################### START OF FILE: statue.py ####################

# statue.py
# -*- coding: utf-8 -*-
"""
Defines the Statue class, an immobile object that can be smashed.
Refactored for PySide6.
"""
# version 2.0.0 (PySide6 Refactor)
import os
from typing import List, Optional, Any, Dict # Added Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage # Added QImage for placeholder check
from PySide6.QtCore import QRectF, QPointF, QSize, Qt # Added QSize, Qt

# Game imports
import constants as C
from assets import load_gif_frames, resource_path # load_gif_frames now returns List[QPixmap]

# Logger import
try:
    from logger import debug, info
except ImportError:
    def debug(msg): print(f"DEBUG_STATUE: {msg}")
    def info(msg): print(f"INFO_STATUE: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_statue = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_statue) * 1000)


class Statue:
    """
    An immobile statue object that can be smashed. Uses QPixmap for visuals.
    """
    def __init__(self, center_x: float, center_y: float, statue_id: Optional[Any] = None,
                 initial_image_path: Optional[str] = None, smashed_anim_path: Optional[str] = None):
        self.statue_id = statue_id if statue_id is not None else id(self)
        self._valid_init = True
        self.initial_image_frames: List[QPixmap] = []
        self.smashed_frames: List[QPixmap] = []

        stone_asset_folder = os.path.join('characters', 'Stone')
        default_initial_image_path = initial_image_path if initial_image_path else os.path.join(stone_asset_folder, '__Stone.png')
        default_smashed_anim_path = smashed_anim_path if smashed_anim_path else os.path.join(stone_asset_folder, '__StoneSmashed.gif')

        full_initial_path = resource_path(default_initial_image_path)
        self.initial_image_frames = load_gif_frames(full_initial_path)
        if not self.initial_image_frames or self._is_placeholder_qpixmap(self.initial_image_frames[0]):
            debug(f"Statue Error: Failed to load initial image from '{full_initial_path}'. Using placeholder.")
            self.image = self._create_placeholder_qpixmap(QColor(*C.GRAY), "StatueImg")
            self.initial_image_frames = [self.image]
        else:
            self.image = self.initial_image_frames[0]

        full_smashed_path = resource_path(default_smashed_anim_path)
        self.smashed_frames = load_gif_frames(full_smashed_path)
        if not self.smashed_frames or self._is_placeholder_qpixmap(self.smashed_frames[0]):
            debug(f"Statue Error: Failed to load smashed animation from '{full_smashed_path}'. Using placeholder.")
            self.smashed_frames = [self._create_placeholder_qpixmap(QColor(*C.DARK_GRAY), "SmashedStat")]
        
        img_w, img_h = float(self.image.width()), float(self.image.height())
        rect_x = float(center_x - img_w / 2.0)
        rect_y = float(center_y - img_h / 2.0)
        self.rect = QRectF(rect_x, rect_y, img_w, img_h)
        self.pos = QPointF(float(center_x), float(center_y)) # Store center position

        self.is_smashed = False
        self.smashed_timer_start = 0
        self.current_frame_index = 0
        self.last_anim_update = get_current_ticks()
        
        self.is_dead = False 
        self.death_animation_finished = False
        self._alive = True

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.size() == QSize(30,40):
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*C.RED) if hasattr(C, 'RED') else QColor(255,0,0)
                qcolor_blue = QColor(*C.BLUE) if hasattr(C, 'BLUE') else QColor(0,0,255)
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        height = self.initial_image_frames[0].height() if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull() else int(C.TILE_SIZE * 1.5)
        width = self.initial_image_frames[0].width() if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull() else C.TILE_SIZE
        pixmap = QPixmap(max(1, width), max(1, height))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*C.BLACK))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try: 
            font = QFont(); font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"STATUE PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        """Updates self.rect (centered) based on self.image and self.pos (center)."""
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = self.pos.x() - img_w / 2.0
            rect_y = self.pos.y() - img_h / 2.0
            self.rect.setRect(rect_x, rect_y, img_w, img_h)

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def smash(self):
        if not self.is_smashed and self._valid_init and self._alive:
            info(f"Statue {self.statue_id} at {self.rect.center().toTuple()} is being smashed.")
            self.is_smashed = True
            self.smashed_timer_start = get_current_ticks()
            self.current_frame_index = 0
            self.last_anim_update = self.smashed_timer_start
            if self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                self.image = self.smashed_frames[0]
                self._update_rect_from_image_and_pos()

    def take_damage(self, damage_amount: int):
        if not self.is_smashed and self._valid_init and self._alive:
            self.smash()

    def update(self, dt_sec: float = 0): # dt_sec currently unused
        if not self._valid_init or not self._alive: return
        now = get_current_ticks()

        if self.is_smashed:
            if now - self.smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                if not self.death_animation_finished:
                    info(f"Statue {self.statue_id} smashed duration ended. Killing.")
                    self.death_animation_finished = True
                self.is_dead = True
                self.kill() 
                return

            if self.smashed_frames and len(self.smashed_frames) > 1:
                anim_speed = C.ANIM_FRAME_DURATION 
                if now - self.last_anim_update > anim_speed:
                    self.last_anim_update = now
                    self.current_frame_index += 1
                    if self.current_frame_index >= len(self.smashed_frames):
                        self.current_frame_index = len(self.smashed_frames) - 1 
                    
                    if 0 <= self.current_frame_index < len(self.smashed_frames) and \
                       self.smashed_frames[self.current_frame_index] and \
                       not self.smashed_frames[self.current_frame_index].isNull():
                        self.image = self.smashed_frames[self.current_frame_index]
                        self._update_rect_from_image_and_pos()
        elif self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull():
                 # Ensure non-smashed state shows the initial image
                 if self.image != self.initial_image_frames[0]:
                    self.image = self.initial_image_frames[0]
                    self._update_rect_from_image_and_pos()

    def get_network_data(self) -> Dict[str, Any]:
        return {
            'id': self.statue_id, 'type': 'Statue',
            'pos': (self.pos.x(), self.pos.y()), 'is_smashed': self.is_smashed,
            'smashed_timer_start': self.smashed_timer_start,
            'current_frame_index': self.current_frame_index,
            '_valid_init': self._valid_init,
            'is_dead': self.is_dead,
            'death_animation_finished': self.death_animation_finished
        }

    def set_network_data(self, data: Dict[str, Any]):
        self._valid_init = data.get('_valid_init', self._valid_init)
        if not self._valid_init:
            if self.alive(): self.kill()
            return

        if 'pos' in data:
            self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
            # Rect will be updated below based on image and state
        
        new_is_smashed = data.get('is_smashed', self.is_smashed)
        if new_is_smashed != self.is_smashed:
            self.is_smashed = new_is_smashed
            if self.is_smashed:
                self.smashed_timer_start = data.get('smashed_timer_start', get_current_ticks())
                self.current_frame_index = data.get('current_frame_index', 0)
                self.last_anim_update = get_current_ticks() # Reset anim timer for synced state
            
        self.is_dead = data.get('is_dead', self.is_dead)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)

        if self.is_smashed:
            self.smashed_timer_start = data.get('smashed_timer_start', self.smashed_timer_start) # Ensure this is synced
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
            if self.smashed_frames and 0 <= self.current_frame_index < len(self.smashed_frames) and \
               self.smashed_frames[self.current_frame_index] and not self.smashed_frames[self.current_frame_index].isNull():
                self.image = self.smashed_frames[self.current_frame_index]
            elif self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                self.image = self.smashed_frames[0] # Fallback to first frame
        else: # Not smashed, use initial image
            if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull():
                 self.image = self.initial_image_frames[0]
        
        self._update_rect_from_image_and_pos() # Update rect based on current image and pos
        
        if self.is_dead and self.alive():
            self.kill()

    @property
    def platform_type(self) -> str: # For potential collision filtering
        return "smashed_debris" if self.is_smashed else "stone_wall"

#################### END OF FILE: statue.py ####################