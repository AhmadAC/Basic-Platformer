#################### START OF FILE: statue.py ####################

# statue.py
# -*- coding: utf-8 -*-
"""
Defines the Statue class, an immobile object that can be smashed.
Refactored for PySide6.
MODIFIED: Applies gravity, handles destruction by attack or player stomp.
Ensures smashed statues are no longer solid platforms.
"""
# version 2.1.2 (Finalized lifecycle and solidity logic)
import os
import time # For monotonic timer
from typing import List, Optional, Any, Dict, Tuple

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QPointF, QSizeF, Qt

# Game imports
import constants as C
from assets import load_gif_frames, resource_path

# Logger import
try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_STATUE: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_STATUE: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_STATUE: {msg}")


# --- Monotonic Timer ---
_start_time_statue_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_statue_monotonic) * 1000)
# --- End Monotonic Timer ---


class Statue:
    def __init__(self, center_x: float, center_y: float, statue_id: Optional[Any] = None,
                 initial_image_path: Optional[str] = None, smashed_anim_path: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None):
        self.statue_id = statue_id if statue_id is not None else id(self)
        self._valid_init = True
        self.properties = properties if properties is not None else {}
        self.initial_image_frames: List[QPixmap] = []
        self.smashed_frames: List[QPixmap] = []
        self.original_entity_type: Optional[str] = self.properties.get("original_entity_type")
        self.original_player_id: Optional[int] = self.properties.get("original_player_id")


        stone_asset_folder = os.path.join('characters', 'Stone')
        # Use properties for image paths if provided (e.g., player-specific petrified images)
        default_initial_image_path = self.properties.get("initial_image_path",
                                      initial_image_path if initial_image_path else os.path.join(stone_asset_folder, '__Stone.png'))
        default_smashed_anim_path = self.properties.get("smashed_anim_path",
                                     smashed_anim_path if smashed_anim_path else os.path.join(stone_asset_folder, '__StoneSmashed.gif'))


        full_initial_path = resource_path(default_initial_image_path)
        self.initial_image_frames = load_gif_frames(full_initial_path)
        if not self.initial_image_frames or self._is_placeholder_qpixmap(self.initial_image_frames[0]):
            debug(f"Statue Error: Failed to load initial image from '{full_initial_path}'. Using placeholder.")
            gray_color = getattr(C, 'GRAY', (128, 128, 128))
            self.image = self._create_placeholder_qpixmap(QColor(*gray_color), "StatueImg")
            self.initial_image_frames = [self.image]
        else:
            self.image = self.initial_image_frames[0]

        full_smashed_path = resource_path(default_smashed_anim_path)
        self.smashed_frames = load_gif_frames(full_smashed_path)
        if not self.smashed_frames or self._is_placeholder_qpixmap(self.smashed_frames[0]):
            debug(f"Statue Error: Failed to load smashed animation from '{full_smashed_path}'. Using placeholder.")
            dark_gray_color = getattr(C, 'DARK_GRAY', (50, 50, 50))
            self.smashed_frames = [self._create_placeholder_qpixmap(QColor(*dark_gray_color), "SmashedStat")]

        img_w, img_h = float(self.image.width()), float(self.image.height())
        self.pos = QPointF(float(center_x), float(center_y))
        rect_x = self.pos.x() - img_w / 2.0
        rect_y = self.pos.y() - img_h / 2.0
        self.rect = QRectF(rect_x, rect_y, img_w, img_h)


        self.is_smashed = False
        self.smashed_timer_start = 0
        self.current_frame_index = 0
        self.last_anim_update = get_current_ticks_monotonic()

        self.is_dead = False
        self.death_animation_finished = False
        self._alive = True

        self.vel = QPointF(0.0, 0.0)
        self.on_ground = False
        self._gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSizeF(30,40):
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0))))
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        base_tile_size = getattr(C, 'TILE_SIZE', 40)
        # Try to use initial image dimensions if available, else fallback
        height_val = (self.initial_image_frames[0].height()
                      if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull()
                      else int(base_tile_size * 1.5))
        width_val = (self.initial_image_frames[0].width()
                     if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull()
                     else base_tile_size)

        pixmap = QPixmap(max(1, width_val), max(1, height_val))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        black_color = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(10); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"STATUE PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        img_w, img_h = self.dimensions.width(), self.dimensions.height()
        rect_x = self.pos.x() - img_w / 2.0
        rect_y = self.pos.y() - img_h / 2.0
        if not hasattr(self, 'rect') or self.rect is None:
             self.rect = QRectF(rect_x, rect_y, img_w, img_h)
        else:
             self.rect.setRect(rect_x, rect_y, img_w, img_h)

    @property
    def dimensions(self) -> QSizeF:
        if self.image and not self.image.isNull():
            return QSizeF(float(self.image.width()), float(self.image.height()))
        return QSizeF(float(getattr(C, 'TILE_SIZE', 40)), float(getattr(C, 'TILE_SIZE', 40) * 1.5))

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        if self._alive:
            info(f"Statue {self.statue_id} kill() called. Setting _alive = False.")
        self._alive = False
        self.is_dead = True
        self.death_animation_finished = True

    def smash(self):
        if not self.is_smashed and self._valid_init and self._alive:
            info(f"Statue {self.statue_id} is being smashed.")
            self.is_smashed = True
            self.is_dead = True
            self.death_animation_finished = False
            self.smashed_timer_start = get_current_ticks_monotonic()
            self.current_frame_index = 0
            self.last_anim_update = self.smashed_timer_start
            if self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                self.image = self.smashed_frames[0]
            self._update_rect_from_image_and_pos()
            self.vel = QPointF(0.0, 0.0)
            self.on_ground = True # Smashed statues don't fall further

    def take_damage(self, damage_amount: int):
        if not self.is_smashed and self._valid_init and self._alive:
            debug(f"Statue {self.statue_id} took {damage_amount} damage, proceeding to smash.")
            self.smash()

    def get_stomped(self, stomping_player: Any):
        if not self.is_smashed and self._valid_init and self._alive:
            player_id_log = getattr(stomping_player, 'player_id', 'UnknownPlayer')
            info(f"Statue {self.statue_id} stomped by Player {player_id_log}. Smashing.")
            self.smash()

    def apply_physics_step(self, dt_sec: float, platforms_list: List[Any]):
        if not self._valid_init or not self._alive or self.is_smashed:
            if self.is_smashed: self.vel.setY(0.0); self.on_ground = True
            return

        if not self.on_ground:
            # Assuming vel is units per "conceptual frame" (scaled by C.FPS elsewhere if dt_sec represents actual time)
            # If vel is units/second, then: self.vel.setY(self.vel.y() + self._gravity * dt_sec)
            # Given the game loop pattern (vel * dt_sec * C.FPS), self.vel should be "per physics update at reference FPS"
            # So, gravity should be applied directly without dt_sec here if dt_sec is used later for position.
            # For consistency with Player class which has `self.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))`
            # and then `player.vel.setY(player.vel.y() + player.acc.y())`, we do the same.
            self.vel.setY(self.vel.y() + self._gravity)
            self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
        
        # Actual position update uses the scaled velocity (dt_sec * C.FPS)
        # If vel is units/frame: self.pos.setY(self.pos.y() + self.vel.y())
        # If vel is units/sec: self.pos.setY(self.pos.y() + self.vel.y() * dt_sec)
        # Matching the game loop's player update:
        scaled_vel_y_for_pos_update = self.vel.y() * dt_sec * C.FPS
        self.pos.setY(self.pos.y() + scaled_vel_y_for_pos_update)
        self._update_rect_from_image_and_pos()

        self.on_ground = False
        for platform_obj in platforms_list:
            if isinstance(platform_obj, Statue) and platform_obj is self:
                continue
            if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF):
                continue
            if self.rect.intersects(platform_obj.rect):
                if self.vel.y() >= 0:
                    overlap_y = self.rect.bottom() - platform_obj.rect.top()
                    if overlap_y > 0:
                        min_h_overlap_ratio = 0.1
                        min_h_overlap_pixels = self.rect.width() * min_h_overlap_ratio
                        actual_h_overlap = min(self.rect.right(), platform_obj.rect.right()) - \
                                           max(self.rect.left(), platform_obj.rect.left())
                        
                        prev_bottom_y_estimate = self.rect.bottom() - scaled_vel_y_for_pos_update
                        if actual_h_overlap >= min_h_overlap_pixels and prev_bottom_y_estimate <= platform_obj.rect.top() + 1.0:
                            self.rect.moveBottom(platform_obj.rect.top())
                            self.pos.setY(self.rect.center().y())
                            self.vel.setY(0.0)
                            self.on_ground = True
                            break 
        self._update_rect_from_image_and_pos()

    def update(self, dt_sec: float = 0.0):
        if not self._valid_init or not self._alive:
            return
        
        now = get_current_ticks_monotonic()

        if self.is_smashed:
            if not self.death_animation_finished:
                if now - self.smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                    info(f"Statue {self.statue_id} smashed animation/duration ended.")
                    self.death_animation_finished = True
                
                elif self.smashed_frames and len(self.smashed_frames) > 1:
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
                 if self.image != self.initial_image_frames[0]:
                    self.image = self.initial_image_frames[0]
                    self._update_rect_from_image_and_pos()

        if self.is_dead and self.death_animation_finished:
            self.kill() # Statue can call its own kill once its logic is complete

    def get_network_data(self) -> Dict[str, Any]:
        pos_x = self.pos.x() if hasattr(self.pos, 'x') else 0.0
        pos_y = self.pos.y() if hasattr(self.pos, 'y') else 0.0
        vel_y_val = self.vel.y() if hasattr(self.vel, 'y') else 0.0
        return {
            'id': self.statue_id, 'type': 'Statue',
            'pos': (pos_x, pos_y),
            'vel_y': vel_y_val,
            'on_ground': self.on_ground,
            'is_smashed': self.is_smashed,
            'smashed_timer_start': self.smashed_timer_start,
            'current_frame_index': self.current_frame_index,
            '_valid_init': self._valid_init,
            'is_dead': self.is_dead,
            'death_animation_finished': self.death_animation_finished,
            'properties': self.properties,
            'original_entity_type': self.original_entity_type,
            'original_player_id': self.original_player_id,
        }

    def set_network_data(self, data: Dict[str, Any]):
        self._valid_init = data.get('_valid_init', self._valid_init)
        if not self._valid_init:
            if self.alive(): self.kill()
            return

        if 'pos' in data and hasattr(self, 'pos'):
            self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        
        if hasattr(self, 'vel') and 'vel_y' in data: self.vel.setY(data['vel_y'])
        self.on_ground = data.get('on_ground', self.on_ground)
        self.properties = data.get('properties', self.properties)
        self.original_entity_type = data.get('original_entity_type', self.original_entity_type)
        self.original_player_id = data.get('original_player_id', self.original_player_id)

        new_is_smashed = data.get('is_smashed', self.is_smashed)
        if new_is_smashed != self.is_smashed:
            self.is_smashed = new_is_smashed
            if self.is_smashed:
                self.is_dead = True
                self.death_animation_finished = False
                self.smashed_timer_start = data.get('smashed_timer_start', get_current_ticks_monotonic())
                self.current_frame_index = data.get('current_frame_index', 0)
                self.last_anim_update = get_current_ticks_monotonic()

        self.is_dead = data.get('is_dead', self.is_dead)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)

        if self.is_smashed:
            self.smashed_timer_start = data.get('smashed_timer_start', self.smashed_timer_start)
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
            if self.smashed_frames and 0 <= self.current_frame_index < len(self.smashed_frames) and \
               self.smashed_frames[self.current_frame_index] and not self.smashed_frames[self.current_frame_index].isNull():
                self.image = self.smashed_frames[self.current_frame_index]
            elif self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                self.image = self.smashed_frames[0]
            else: # Fallback if smashed_frames are somehow invalid
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'DARK_GRAY', (50,50,50))), "SmashNet")
        else: # Not smashed
            if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull():
                 self.image = self.initial_image_frames[0]
            else: # Fallback if initial_image_frames are invalid
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'GRAY', (128,128,128))), "StoneNet")


        self._update_rect_from_image_and_pos()

        if self.is_dead and self.death_animation_finished and self.alive():
            self.kill()

    @property
    def platform_type(self) -> str:
        return "smashed_debris" if self.is_smashed else "stone_obstacle"

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return
        
        should_draw = self._alive or (self.is_smashed and not self.death_animation_finished)
        if not should_draw:
            return

        screen_rect_qrectf = camera.apply(self.rect)
        if painter.window().intersects(screen_rect_qrectf.toRect()):
            painter.drawPixmap(screen_rect_qrectf.topLeft(), self.image)