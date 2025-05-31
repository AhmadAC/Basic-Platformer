# player/projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc. for PySide6.
Handles projectile effects including setting targets aflame or frozen.
MODIFIED: Corrected path for `resource_path` import.
MODIFIED: Updated asset paths for projectile sprites.
"""
# version 2.0.8 (Corrected resource_path import and projectile asset paths)

import os
import sys # Added sys for path manipulation if run standalone
import math
import time
from typing import List, Optional, Any, Tuple, Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSizeF, Qt, QSize

# --- Project Root Setup for Standalone Testing/Linting ---
# Assumes projectiles.py is in Project_Root/player/
_PROJECTILES_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_PROJECTILES_PY = os.path.dirname(_PROJECTILES_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_PROJECTILES_PY not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_PROJECTILES_PY)
# --- End Project Root Setup ---

# Game imports
import main_game.constants as C
from main_game.assets import load_gif_frames, resource_path # Corrected import path for assets
from enemy import Enemy
from player.statue import Statue

# Logger import
try:
    from main_game.logger import debug # Corrected import path for logger
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_PROJ: {msg}")

# --- Monotonic Timer ---
_start_time_projectiles_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_projectiles_monotonic) * 1000)
# --- End Monotonic Timer ---


class BaseProjectile:
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any, config: dict):
        self.owner_player = owner_player
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan']
        self.dimensions = QSizeF(float(config['dimensions'][0]), float(config['dimensions'][1]))
        self.sprite_path = config['sprite_path'] # This path is now relative to project root, e.g., "assets/weapons/fire.gif"
        self.effect_type = config.get('effect_type')

        # `resource_path` now correctly resolves from project root
        full_gif_path = resource_path(self.sprite_path)
        self.frames: List[QPixmap] = load_gif_frames(full_gif_path)

        if not self.frames or self._is_placeholder_qpixmap(self.frames[0]):
            debug(f"Warning: Projectile GIF '{full_gif_path}' failed. Using fallback for {self.__class__.__name__}.")
            fb_color1_tuple = config.get('fallback_color1', getattr(C, 'ORANGE_RED', (255, 69, 0)))
            fb_color2_tuple = config.get('fallback_color2', getattr(C, 'RED', (255, 0, 0)))
            fb_color1 = QColor(*fb_color1_tuple)
            fb_color2 = QColor(*fb_color2_tuple)

            w, h = max(1, int(self.dimensions.width())), max(1, int(self.dimensions.height()))
            fallback_pixmap = QPixmap(w, h)
            fallback_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(fallback_pixmap)
            painter.setBrush(fb_color1); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(0,0,float(w),float(h)))
            if w > 4 and h > 4:
                 painter.setBrush(fb_color2)
                 painter.drawEllipse(QRectF(w*0.25, h*0.25, w*0.5, h*0.5))
            painter.end()
            self.frames = [fallback_pixmap]

        if self.frames and self.frames[0] and not self.frames[0].isNull():
            self.dimensions = QSizeF(float(self.frames[0].width()), float(self.frames[0].height()))
        else:
            self.dimensions = QSizeF(10.0, 10.0)
            self.image = QPixmap(10,10); self.image.fill(QColor(255,0,255))
            self.frames = [self.image]


        self.current_frame_index = 0
        self.image: QPixmap = self.frames[self.current_frame_index]

        player_facing_right = getattr(self.owner_player, 'facing_right', True)
        direction_mag = math.sqrt(direction_qpointf.x()**2 + direction_qpointf.y()**2)
        if direction_mag > 1e-6:
            norm_dir_x = direction_qpointf.x() / direction_mag
            norm_dir_y = direction_qpointf.y() / direction_mag
            self.vel = QPointF(norm_dir_x * self.speed, norm_dir_y * self.speed)
        else:
            vel_x_fallback = self.speed if player_facing_right else -self.speed
            self.vel = QPointF(vel_x_fallback, 0.0)

        spawn_initial_x = float(x)
        spawn_initial_y = float(y)
        projectile_spawn_offset_x = 0.0
        projectile_spawn_offset_y = 0.0

        if self.__class__.__name__ == "BoltProjectile":
            bolt_x_offset_from_player_center = float(getattr(C,'TILE_SIZE', 40)/4)
            if player_facing_right:
                spawn_initial_x += bolt_x_offset_from_player_center
                projectile_spawn_offset_x = -10.0
            else:
                spawn_initial_x -= bolt_x_offset_from_player_center
                projectile_spawn_offset_x = 10.0
            self._bolt_flight_angle_deg = math.degrees(math.atan2(self.vel.y(), self.vel.x()))
            self._bolt_is_firing_predominantly_upwards = False
            is_firing_predominantly_downwards = False
            if self.vel.y() < -0.01:
                if abs(self.vel.y()) > abs(self.vel.x()) * 1.5 or \
                   (-120 < self._bolt_flight_angle_deg < -60):
                    self._bolt_is_firing_predominantly_upwards = True
            elif self.vel.y() > 0.01:
                 if abs(self.vel.y()) > abs(self.vel.x()) * 1.5 or \
                   (60 < self._bolt_flight_angle_deg < 120):
                    is_firing_predominantly_downwards = True
                    projectile_spawn_offset_y = 10.0

        self.pos = QPointF(spawn_initial_x + projectile_spawn_offset_x,
                           spawn_initial_y + projectile_spawn_offset_y)

        img_w_initial = float(self.image.width()) if self.image and not self.image.isNull() else self.dimensions.width()
        img_h_initial = float(self.image.height()) if self.image and not self.image.isNull() else self.dimensions.height()
        rect_x = self.pos.x() - img_w_initial / 2.0
        rect_y = self.pos.y() - img_h_initial / 2.0
        self.rect = QRectF(rect_x, rect_y, img_w_initial, img_h_initial)

        self.original_frames = [frame.copy() for frame in self.frames]
        self._post_init_hook()

        if self.frames and self.current_frame_index < len(self.frames) and \
           self.frames[self.current_frame_index] and not self.frames[self.current_frame_index].isNull():
            self.image = self.frames[self.current_frame_index]
            self.dimensions = QSizeF(float(self.image.width()), float(self.image.height()))
        self._update_rect_from_image_and_pos()

        self.spawn_time = get_current_ticks_monotonic()
        self.last_anim_update = self.spawn_time
        proj_type_name = self.__class__.__name__.lower()
        owner_id_str = str(getattr(owner_player, 'player_id', 'unknownP'))
        self.projectile_id = f"{proj_type_name}_{owner_id_str}_{self.spawn_time}"
        self._alive = True
        self.game_elements_ref: Optional[Dict[str, Any]] = None

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(1,1) and pixmap.toImage().pixelColor(0,0) == QColor(255,0,255): # Magenta
            return True
        if pixmap.size() == QSize(30,40): # Common placeholder size from assets.py
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0))))
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _update_rect_from_image_and_pos(self):
        img_w, img_h = self.dimensions.width(), self.dimensions.height()
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
        rect_x = self.pos.x() - img_w / 2.0
        rect_y = self.pos.y() - img_h / 2.0 # pos is visual center
        if not hasattr(self, 'rect') or self.rect is None:
             self.rect = QRectF(rect_x, rect_y, img_w, img_h)
        else:
             self.rect.setRect(rect_x, rect_y, img_w, img_h)

    def _post_init_hook(self):
        pass

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def animate(self):
        if not self._alive or not self.frames or len(self.frames) <= 1:
            if self.frames and len(self.frames) == 1 and self.frames[0] and not self.frames[0].isNull():
                self.image = self.frames[0]
            return

        now = get_current_ticks_monotonic()
        anim_frame_duration_config = getattr(C, 'ANIM_FRAME_DURATION', 100)
        anim_speed_divisor = getattr(self, 'custom_anim_speed_divisor', 1.0) # Default divisor to 1 for projectiles
        if anim_speed_divisor <= 1e-6: anim_speed_divisor = 1.0
        actual_anim_duration = anim_frame_duration_config / anim_speed_divisor

        if now - self.last_anim_update > actual_anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            new_image_candidate = self.frames[self.current_frame_index]

            if not isinstance(self, BoltProjectile): # Bolt handles its own rotation in _post_init_hook
                current_vel_x = 0.0
                if hasattr(self, 'vel') and self.vel is not None and hasattr(self.vel, 'x') and callable(self.vel.x):
                    current_vel_x = self.vel.x()
                if current_vel_x < -0.01: # Moving left
                    qimg = new_image_candidate.toImage()
                    self.image = QPixmap.fromImage(qimg.mirrored(True, False)) if not qimg.isNull() else new_image_candidate
                else: # Moving right or stationary
                    self.image = new_image_candidate
            else: # Bolt projectile, image is already rotated
                self.image = new_image_candidate
            self._update_rect_from_image_and_pos()

    def update(self, dt_sec: float, platforms: List[Any], characters_to_hit_list: List[Any]):
        if not self._alive: return
        time_scaling_factor = dt_sec * getattr(C, 'FPS', 60.0)
        frame_scaled_vel_x = self.vel.x() * time_scaling_factor
        frame_scaled_vel_y = self.vel.y() * time_scaling_factor
        self.pos.setX(self.pos.x() + frame_scaled_vel_x)
        self.pos.setY(self.pos.y() + frame_scaled_vel_y)
        self._update_rect_from_image_and_pos()
        self.animate()
        current_time_ticks = get_current_ticks_monotonic()
        if current_time_ticks - self.spawn_time > self.lifespan:
            self.kill(); return
        for platform_obj in platforms:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               hasattr(self, 'rect') and self.rect is not None and self.rect.intersects(platform_obj.rect):
                self.kill(); return
        for char_target in characters_to_hit_list:
            if not hasattr(char_target, 'rect') or not isinstance(char_target.rect, QRectF) or \
               (hasattr(char_target, 'alive') and not char_target.alive()):
                continue
            if char_target is self.owner_player and (current_time_ticks - self.spawn_time < 100): # Brief immunity to self
                continue
            if isinstance(self, Fireball) and char_target is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False):
                continue
            if isinstance(self, (BloodShot, IceShard)) and char_target is self.owner_player: # No self-damage for these by default
                continue
            if hasattr(self, 'rect') and self.rect is not None and self.rect.intersects(char_target.rect):
                can_damage_target = True
                if hasattr(char_target, 'is_taking_hit') and hasattr(char_target, 'hit_timer') and hasattr(char_target, 'hit_cooldown'):
                    if char_target.is_taking_hit and (current_time_ticks - char_target.hit_timer < char_target.hit_cooldown):
                        can_damage_target = False # Target is in hit cooldown (invincible)
                if self.effect_type == "freeze" and getattr(char_target, 'is_frozen', False): can_damage_target = False
                elif self.effect_type == "aflame" and getattr(char_target, 'is_aflame', False): can_damage_target = False

                if can_damage_target:
                    target_type_name = type(char_target).__name__
                    target_id_log = getattr(char_target, 'player_id', getattr(char_target, 'enemy_id', getattr(char_target, 'statue_id', 'UnknownTarget')))
                    owner_id_log = getattr(self.owner_player, 'player_id', 'Owner?') if self.owner_player else 'NoOwner'

                    if self.effect_type == 'petrify':
                        if isinstance(char_target, Statue): continue # Don't petrify statues
                        elif hasattr(char_target, 'petrify') and callable(char_target.petrify) and \
                             not getattr(char_target, 'is_petrified', False):
                            debug(f"GreyProjectile by P{owner_id_log} hit {target_type_name} {target_id_log}. Petrifying.")
                            char_target.petrify() # Player.petrify() now takes game_elements if it was an external call
                            self.kill(); return
                    if self.damage > 0 and hasattr(char_target, 'take_damage') and callable(char_target.take_damage):
                        debug(f"{self.__class__.__name__} (Owner: P{owner_id_log}) hit {target_type_name} {target_id_log} for {self.damage} DMG.")
                        char_target.take_damage(self.damage)
                    if self.effect_type == "freeze" and hasattr(char_target, 'apply_freeze_effect') and callable(char_target.apply_freeze_effect) and \
                       not getattr(char_target, 'is_frozen', False):
                        char_target.apply_freeze_effect()
                    elif self.effect_type == "aflame" and hasattr(char_target, 'apply_aflame_effect') and callable(char_target.apply_aflame_effect) and \
                         not getattr(char_target, 'is_aflame', False):
                        char_target.apply_aflame_effect()
                    self.kill(); return

    def get_network_data(self) -> Dict[str, Any]:
        image_flipped = False
        vel_x_val, vel_y_val = 0.0, 0.0
        if hasattr(self, 'vel') and self.vel is not None:
            if hasattr(self.vel, 'x') and callable(self.vel.x): vel_x_val = self.vel.x()
            if hasattr(self.vel, 'y') and callable(self.vel.y): vel_y_val = self.vel.y()
        if not isinstance(self, BoltProjectile): # Bolt handles its own rotation, not simple flip
            image_flipped = vel_x_val < -0.01

        owner_player_id = getattr(getattr(self, 'owner_player', None), 'player_id', None)
        pos_x_val = self.pos.x() if hasattr(self, 'pos') and self.pos is not None else 0.0
        pos_y_val = self.pos.y() if hasattr(self, 'pos') and self.pos is not None else 0.0
        return {
            'id': getattr(self, 'projectile_id', f"unknown_{get_current_ticks_monotonic()}"),
            'type': self.__class__.__name__, 'pos': (pos_x_val, pos_y_val),
            'vel': (vel_x_val, vel_y_val), 'owner_id': owner_player_id,
            'frame': getattr(self, 'current_frame_index', 0),
            'spawn_time': getattr(self, 'spawn_time', 0),
            'image_flipped': image_flipped, 'effect_type': getattr(self, 'effect_type', None)
        }

    def set_network_data(self, data: Dict[str, Any]):
        if hasattr(self, 'pos') and isinstance(self.pos, QPointF) and 'pos' in data and isinstance(data['pos'], (list, tuple)) and len(data['pos']) == 2:
            self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        if hasattr(self, 'vel') and isinstance(self.vel, QPointF) and 'vel' in data and isinstance(data['vel'], (list, tuple)) and len(data['vel']) == 2:
            self.vel.setX(data['vel'][0]); self.vel.setY(data['vel'][1])
        self._update_rect_from_image_and_pos()
        self.current_frame_index = data.get('frame', getattr(self, 'current_frame_index', 0))
        self.effect_type = data.get('effect_type', getattr(self, 'effect_type', None))

        # Image update (consider flip for non-Bolt projectiles)
        old_center_qpointf = self.rect.center() if hasattr(self, 'rect') and self.rect is not None else QPointF(self.pos.x(), self.pos.y())

        if not self.frames: # Should not happen if init was successful
            self.image = QPixmap(1,1); self.image.fill(QColor(*(getattr(C, 'MAGENTA', (255,0,255)))))
            self._update_rect_from_image_and_pos(); return

        self.current_frame_index = self.current_frame_index % len(self.frames) if self.frames and len(self.frames) > 0 else 0
        base_image_candidate = self.frames[self.current_frame_index] if self.frames and len(self.frames) > self.current_frame_index else None
        base_image = base_image_candidate if base_image_candidate and not base_image_candidate.isNull() else QPixmap(10,10); base_image.fill(QColor(255,0,255))

        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            qimg = base_image.toImage();
            self.image = QPixmap.fromImage(qimg.mirrored(True, False)) if not qimg.isNull() else base_image
        else: # Bolt or not flipped
            self.image = base_image

        # Update rect and dimensions after image change
        if self.image and not self.image.isNull():
            new_img_w, new_img_h = float(self.image.width()), float(self.image.height())
            if hasattr(self, 'rect') and self.rect is not None:
                self.rect.setRect(old_center_qpointf.x() - new_img_w/2.0, old_center_qpointf.y() - new_img_h/2.0, new_img_w, new_img_h)
            else: # Initialize rect if it was None
                 self.rect = QRectF(self.pos.x() - new_img_w/2.0, self.pos.y() - new_img_h/2.0, new_img_w, new_img_h)
            self.dimensions = QSizeF(new_img_w, new_img_h)
        else: # Fallback if image became null
            self._update_rect_from_image_and_pos()


# --- Specific Projectile Classes ---
class Fireball(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.FIREBALL_DAMAGE, 'speed': C.FIREBALL_SPEED, 'lifespan': C.FIREBALL_LIFESPAN,
            'sprite_path': C.FIREBALL_SPRITE_PATH, # This will be "assets/weapons/fire.gif"
            'dimensions': C.FIREBALL_DIMENSIONS,
            'fallback_color1': getattr(C, 'ORANGE_RED', (255, 69, 0)),
            'fallback_color2': getattr(C, 'RED', (255, 0, 0)),
            'effect_type': "aflame"
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class PoisonShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.POISON_DAMAGE, 'speed': C.POISON_SPEED, 'lifespan': C.POISON_LIFESPAN,
            'sprite_path': C.POISON_SPRITE_PATH, # "assets/weapons/poison.gif"
            'dimensions': C.POISON_DIMENSIONS,
            'fallback_color1': getattr(C, 'GREEN', (0,255,0)),
            'fallback_color2': getattr(C, 'DARK_GREEN', (0,100,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class BoltProjectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BOLT_DAMAGE, 'speed': C.BOLT_SPEED, 'lifespan': C.BOLT_LIFESPAN,
            'sprite_path': C.BOLT_SPRITE_PATH, # "assets/weapons/bolt1_resized_11x29.gif"
            'dimensions': C.BOLT_DIMENSIONS,
            'fallback_color1': getattr(C, 'YELLOW', (255,255,0)),
            'fallback_color2': getattr(C, 'YELLOW', (255,255,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

    def _post_init_hook(self):
        if not self.original_frames or (self.original_frames and self.original_frames[0].isNull()):
            debug("BoltProjectile: No original frames for rotation or first frame is null."); return
        if not hasattr(self, '_bolt_flight_angle_deg') or not hasattr(self, '_bolt_is_firing_predominantly_upwards'):
            debug("BoltProjectile: Missing flight angle or upward firing flag for rotation. Skipping rotation.")
            if hasattr(self, '_bolt_flight_angle_deg'): del self._bolt_flight_angle_deg
            if hasattr(self, '_bolt_is_firing_predominantly_upwards'): del self._bolt_is_firing_predominantly_upwards
            return

        self.frames = [frame.copy() for frame in self.original_frames] # Work on copies
        flight_angle_deg = self._bolt_flight_angle_deg
        is_firing_predominantly_upwards = self._bolt_is_firing_predominantly_upwards
        alignment_rotation_deg = flight_angle_deg + 90.0 # Align with flight path (bolt points "up" by default)
        final_rotation_deg: float
        debug_msg_prefix = ""

        if is_firing_predominantly_upwards:
            final_rotation_deg = -180.0 # Keep this logic if desired
            debug_msg_prefix = f"Bolt (UP override to -180deg P{getattr(self.owner_player,'player_id','?')})"
            debug(f"{debug_msg_prefix}: FlightAngle={flight_angle_deg:.1f}, FinalRot={final_rotation_deg:.1f}")
        else:
            final_rotation_deg = alignment_rotation_deg + 180.0
            debug_msg_prefix = f"Bolt (180deg flip from alignment P{getattr(self.owner_player,'player_id','?')})"
            debug(f"{debug_msg_prefix}: FlightAngle={flight_angle_deg:.1f}, AlignRot={alignment_rotation_deg:.1f}, FinalRot={final_rotation_deg:.1f}")

        transformed_frames_new: List[QPixmap] = []
        for frame_idx, frame_pixmap in enumerate(self.frames):
            if frame_pixmap.isNull():
                debug(f"BoltProjectile: Frame {frame_idx} is null, skipping rotation.")
                transformed_frames_new.append(frame_pixmap); continue
            center = QPointF(frame_pixmap.width() / 2.0, frame_pixmap.height() / 2.0)
            transform = QTransform().translate(center.x(), center.y()).rotate(final_rotation_deg).translate(-center.x(), -center.y())
            rotated_pixmap = frame_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            if rotated_pixmap.isNull():
                debug(f"BoltProjectile: Rotated frame {frame_idx} became null. Using original.")
                transformed_frames_new.append(frame_pixmap.copy())
            else:
                transformed_frames_new.append(rotated_pixmap)
        if transformed_frames_new: self.frames = transformed_frames_new
        self.current_frame_index = 0
        del self._bolt_flight_angle_deg # Clean up temp attributes
        del self._bolt_is_firing_predominantly_upwards

    def animate(self):
        if not self._alive or not self.frames: return
        if len(self.frames) <= 1: # Static image or single frame anim
             if self.frames and self.frames[0] and not self.frames[0].isNull():
                 self.image = self.frames[0] # Ensure image is set if single frame
             return
        super().animate() # Call base animation for multi-frame


class BloodShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BLOOD_DAMAGE, 'speed': C.BLOOD_SPEED, 'lifespan': C.BLOOD_LIFESPAN,
            'sprite_path': C.BLOOD_SPRITE_PATH, # "assets/weapons/blood.gif"
            'dimensions': C.BLOOD_DIMENSIONS,
            'fallback_color1': getattr(C, 'RED', (255,0,0)),
            'fallback_color2': getattr(C, 'DARK_RED', (139,0,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class IceShard(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.ICE_DAMAGE, 'speed': C.ICE_SPEED, 'lifespan': C.ICE_LIFESPAN,
            'sprite_path': C.ICE_SPRITE_PATH, # "assets/weapons/ice.gif"
            'dimensions': C.ICE_DIMENSIONS,
            'fallback_color1': getattr(C, 'LIGHT_BLUE', (173,216,230)),
            'fallback_color2': getattr(C, 'BLUE', (0,0,255)),
            'effect_type': "freeze"
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class ShadowProjectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.SHADOW_PROJECTILE_DAMAGE, 'speed': C.SHADOW_PROJECTILE_SPEED,
            'lifespan': C.SHADOW_PROJECTILE_LIFESPAN,
            'sprite_path': C.SHADOW_PROJECTILE_SPRITE_PATH, # "assets/weapons/shadow095.gif"
            'dimensions': C.SHADOW_PROJECTILE_DIMENSIONS,
            'fallback_color1': getattr(C, 'DARK_GRAY', (50,50,50)),
            'fallback_color2': getattr(C, 'BLACK', (0,0,0)),
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)
        self.custom_anim_speed_divisor = 1.2 # Example of custom speed

class GreyProjectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.GREY_PROJECTILE_DAMAGE,
            'speed': C.GREY_PROJECTILE_SPEED,
            'lifespan': C.GREY_PROJECTILE_LIFESPAN,
            'sprite_path': C.GREY_PROJECTILE_SPRITE_PATH, # "assets/weapons/grey.gif"
            'dimensions': C.GREY_PROJECTILE_DIMENSIONS,
            'fallback_color1': getattr(C, 'GRAY', (128,128,128)),
            'fallback_color2': getattr(C, 'DARK_GRAY', (50,50,50)),
            'effect_type': 'petrify'
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)
        self.custom_anim_speed_divisor = 1.0