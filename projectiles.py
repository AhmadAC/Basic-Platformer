#################### START OF FILE: projectiles.py ####################

# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc. for PySide6.
Handles projectile effects including setting targets aflame or frozen.
"""
# version 2.0.1 (PySide6 Refactor - Added missing QSize, Dict imports)
import os
import math # For atan2, degrees for rotation
from typing import List, Optional, Any, Tuple, Dict # Added QSize, Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSizeF, Qt, QSize # Added QSize

# Game imports
import constants as C
from assets import load_gif_frames, resource_path # load_gif_frames now returns List[QPixmap]
from enemy import Enemy # For isinstance checks
from statue import Statue # For isinstance checks

# Logger import
try:
    from logger import debug
except ImportError:
    def debug(msg): print(f"DEBUG_PROJ: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame # Try to import for get_ticks if Pygame is still lingering
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_projectiles = time.monotonic()
    def get_current_ticks(): # Fallback timer
        return int((time.monotonic() - _start_time_projectiles) * 1000)


class BaseProjectile:
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any, config: dict):
        self.owner_player = owner_player
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan']
        self.dimensions = QSizeF(float(config['dimensions'][0]), float(config['dimensions'][1]))
        self.sprite_path = config['sprite_path']
        self.effect_type = config.get('effect_type')

        full_gif_path = resource_path(self.sprite_path)
        self.frames: List[QPixmap] = load_gif_frames(full_gif_path)

        if not self.frames or self._is_placeholder_qpixmap(self.frames[0]):
            debug(f"Warning: Projectile GIF '{full_gif_path}' failed. Using fallback for {self.__class__.__name__}.")
            fb_color1 = QColor(*(config.get('fallback_color1', C.ORANGE_RED)))
            fb_color2 = QColor(*(config.get('fallback_color2', C.RED)))
            
            w, h = int(self.dimensions.width()), int(self.dimensions.height())
            fallback_pixmap = QPixmap(w,h)
            fallback_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(fallback_pixmap)
            painter.setBrush(fb_color1)
            painter.drawEllipse(QRectF(0,0,w,h)) 
            if w > 4 and h > 4:
                 painter.setBrush(fb_color2)
                 painter.drawEllipse(QRectF(w*0.25, h*0.25, w*0.5, h*0.5))
            painter.end()
            self.frames = [fallback_pixmap]
        
        self.dimensions = QSizeF(float(self.frames[0].width()), float(self.frames[0].height()))

        self.current_frame_index = 0
        self.image: QPixmap = self.frames[self.current_frame_index]
        
        rect_w, rect_h = self.image.width(), self.image.height()
        rect_x = float(x - rect_w / 2.0)
        rect_y = float(y - rect_h / 2.0)
        self.rect = QRectF(rect_x, rect_y, float(rect_w), float(rect_h))
        
        self.pos = QPointF(float(x), float(y)) 

        direction_mag = math.sqrt(direction_qpointf.x()**2 + direction_qpointf.y()**2)
        if direction_mag > 1e-6: # Avoid division by zero for very small vectors
            norm_dir_x = direction_qpointf.x() / direction_mag
            norm_dir_y = direction_qpointf.y() / direction_mag
            self.vel = QPointF(norm_dir_x * self.speed, norm_dir_y * self.speed)
        else:
            vel_x_fallback = self.speed if owner_player.facing_right else -self.speed
            self.vel = QPointF(vel_x_fallback, 0.0)

        self.original_frames = [frame.copy() for frame in self.frames]
        self._post_init_hook(self.vel) 

        self.current_frame_index = 0 
        if self.frames: 
            self.image = self.frames[self.current_frame_index % len(self.frames)]
            self.dimensions = QSizeF(float(self.image.width()), float(self.image.height()))
            self._update_rect_from_image_and_pos() 

        self.spawn_time = get_current_ticks()
        self.last_anim_update = self.spawn_time
        proj_type_name = self.__class__.__name__.lower()
        owner_id_str = str(getattr(owner_player, 'player_id', 'unknownP'))
        self.projectile_id = f"{proj_type_name}_{owner_id_str}_{self.spawn_time}"
        self._alive = True
        
    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.size() == QSize(30,40):
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*C.RED) if hasattr(C, 'RED') else QColor(255,0,0)
                if color_at_origin == qcolor_red:
                    return True
        return False

    def _update_rect_from_image_and_pos(self):
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = self.pos.x() - img_w / 2.0
            rect_y = self.pos.y() - img_h / 2.0
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        else: 
            fallback_w, fallback_h = self.dimensions.width(), self.dimensions.height()
            self.rect.setRect(self.pos.x() - fallback_w/2, self.pos.y() - fallback_h/2, fallback_w, fallback_h)

    def _post_init_hook(self, final_velocity_qpointf: QPointF):
        pass

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def animate(self):
        if not self._alive or not self.frames or len(self.frames) <= 1:
            return

        now = get_current_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5
        if hasattr(self, 'custom_anim_speed_divisor'):
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            
            new_image_candidate = self.frames[self.current_frame_index]

            if not isinstance(self, BoltProjectile):
                if self.vel.x() < -0.01: 
                    qimg = new_image_candidate.toImage()
                    if not qimg.isNull():
                        self.image = QPixmap.fromImage(qimg.mirrored(True, False))
                    else: self.image = new_image_candidate 
                else:
                    self.image = new_image_candidate
            else: 
                self.image = new_image_candidate
            
            self._update_rect_from_image_and_pos()

    def update(self, dt_sec: float, platforms: List[Any], characters_to_hit_list: List[Any]):
        if not self._alive: return

        self.pos += self.vel * dt_sec * C.FPS 
        self._update_rect_from_image_and_pos()
        self.animate()

        if get_current_ticks() - self.spawn_time > self.lifespan:
            self.kill(); return

        for platform_obj in platforms:
            if hasattr(platform_obj, 'rect') and self.rect.intersects(platform_obj.rect):
                self.kill(); return
        
        for char in characters_to_hit_list:
            if not hasattr(char, 'rect') or (hasattr(char, 'alive') and not char.alive()): continue # Check if char is alive attribute exists
            if char is self.owner_player and (get_current_ticks() - self.spawn_time < 100): continue
            
            is_self_hit_allowed_fireball = getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False)
            is_fireball_and_self = self.__class__.__name__ == "Fireball" and char is self.owner_player
            if is_fireball_and_self and not is_self_hit_allowed_fireball: continue
            if (self.__class__.__name__ == "BloodShot" or self.__class__.__name__ == "IceShard") and char is self.owner_player: continue

            if self.rect.intersects(char.rect):
                can_damage_target = True
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    if char.is_taking_hit and (get_current_ticks() - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                if self.effect_type == "freeze" and getattr(char, 'is_frozen', False): can_damage_target = False 
                elif self.effect_type == "aflame" and getattr(char, 'is_aflame', False): can_damage_target = False 

                if can_damage_target:
                    target_type_name = type(char).__name__
                    target_id_log = getattr(char, 'player_id', getattr(char, 'enemy_id', getattr(char, 'statue_id', 'UnknownTarget')))

                    if self.effect_type == 'petrify':
                        if isinstance(char, Statue): continue 
                        elif hasattr(char, 'petrify') and not getattr(char, 'is_petrified', False):
                            debug(f"Grey shot hit {target_type_name} {target_id_log}. Petrifying.")
                            char.petrify()
                            self.kill(); return

                    if self.damage > 0 and hasattr(char, 'take_damage'): 
                        debug(f"{self.__class__.__name__} (Owner: P{self.owner_player.player_id}) hit {target_type_name} {target_id_log} for {self.damage} DMG.")
                        char.take_damage(self.damage) 
                    
                    if self.effect_type == "freeze" and hasattr(char, 'apply_freeze_effect') and not getattr(char, 'is_frozen', False):
                        char.apply_freeze_effect()
                    elif self.effect_type == "aflame" and hasattr(char, 'apply_aflame_effect') and not getattr(char, 'is_aflame', False):
                        is_green_enemy = isinstance(char, Enemy) and getattr(char, 'color_name', None) == 'green'
                        if is_green_enemy or 'Player' in target_type_name or isinstance(char, Enemy):
                            char.apply_aflame_effect()
                                
                    self.kill(); return
        
    def get_network_data(self) -> Dict[str, Any]:
        image_flipped = False
        if not isinstance(self, BoltProjectile):
            image_flipped = self.vel.x() < -0.01

        return {
            'id': self.projectile_id, 
            'type': self.__class__.__name__,
            'pos': (self.pos.x(), self.pos.y()), 
            'vel': (self.vel.x(), self.vel.y()),
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index, 
            'spawn_time': self.spawn_time,
            'image_flipped': image_flipped,
            'effect_type': self.effect_type
        }

    def set_network_data(self, data: Dict[str, Any]):
        self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        if 'vel' in data: self.vel.setX(data['vel'][0]); self.vel.setY(data['vel'][1])
        
        self._update_rect_from_image_and_pos()
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type)
        
        old_center_qpointf = self.rect.center()

        if not self.frames or (len(self.frames) == 1 and self.frames[0].size() == QSize(1,1)):
            pass 

        if not self.frames:
            self.image = QPixmap(1,1); self.image.fill(QColor(*C.MAGENTA))
            self._update_rect_from_image_and_pos(); return

        self.current_frame_index = self.current_frame_index % len(self.frames)
        base_image = self.frames[self.current_frame_index]

        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            qimg = base_image.toImage(); self.image = QPixmap.fromImage(qimg.mirrored(True, False)) if not qimg.isNull() else base_image
        else: self.image = base_image
        
        new_img_w, new_img_h = float(self.image.width()), float(self.image.height())
        self.rect.setRect(old_center_qpointf.x() - new_img_w/2, old_center_qpointf.y() - new_img_h/2, new_img_w, new_img_h)
        self.dimensions = QSizeF(new_img_w, new_img_h)


# --- Specific Projectile Classes ---
class Fireball(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.FIREBALL_DAMAGE, 'speed': C.FIREBALL_SPEED, 'lifespan': C.FIREBALL_LIFESPAN,
            'sprite_path': C.FIREBALL_SPRITE_PATH, 'dimensions': C.FIREBALL_DIMENSIONS,
            'fallback_color1': C.ORANGE_RED, 'fallback_color2': C.RED,
            'effect_type': "aflame"
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class PoisonShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.POISON_DAMAGE, 'speed': C.POISON_SPEED, 'lifespan': C.POISON_LIFESPAN,
            'sprite_path': C.POISON_SPRITE_PATH, 'dimensions': C.POISON_DIMENSIONS,
            'fallback_color1': C.GREEN, 'fallback_color2': C.DARK_GREEN
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class BoltProjectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BOLT_DAMAGE, 'speed': C.BOLT_SPEED, 'lifespan': C.BOLT_LIFESPAN,
            'sprite_path': C.BOLT_SPRITE_PATH, 'dimensions': C.BOLT_DIMENSIONS,
            'fallback_color1': C.YELLOW, 'fallback_color2': C.YELLOW
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

    def _post_init_hook(self, final_velocity_qpointf: QPointF):
        if not self.original_frames or (self.original_frames and self.original_frames[0].isNull()):
            debug("BoltProjectile: No original frames for rotation."); return

        self.frames = [frame.copy() for frame in self.original_frames]
        
        angle_rad = math.atan2(final_velocity_qpointf.y(), final_velocity_qpointf.x())
        angle_deg = math.degrees(angle_rad)

        transformed_frames_new: List[QPixmap] = []
        for frame_pixmap in self.frames:
            if frame_pixmap.isNull():
                transformed_frames_new.append(frame_pixmap); continue
            
            transform = QTransform().rotate(angle_deg)
            # Ensure the transformation center is the pixmap's center for better rotation
            # However, QPixmap.transformed uses the top-left as the default rotation origin.
            # For accurate rotation around center, one might need to draw onto a new, larger pixmap
            # or use QPainter with translate/rotate/translate back.
            # For simplicity here, we use the direct transform.
            rotated_pixmap = frame_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            transformed_frames_new.append(rotated_pixmap)
        
        if transformed_frames_new:
            self.frames = transformed_frames_new
        
        self.current_frame_index = 0
        if self.frames and self.frames[0] and not self.frames[0].isNull():
            self.image = self.frames[0]
            self._update_rect_from_image_and_pos() 
        else: 
            self.image = QPixmap(int(self.dimensions.width()), int(self.dimensions.height()))
            self.image.fill(QColor(*C.MAGENTA)) 
            self.frames = [self.image]

    def animate(self):
        if not self._alive or not self.frames or len(self.frames) <= 1:
             if self.frames and len(self.frames) == 1 and self.frames[0] and not self.frames[0].isNull():
                 self.image = self.frames[0] 
             return
        # For Bolt, the frames are already rotated. Base animate handles frame cycling if any.
        super().animate()


class BloodShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BLOOD_DAMAGE, 'speed': C.BLOOD_SPEED, 'lifespan': C.BLOOD_LIFESPAN,
            'sprite_path': C.BLOOD_SPRITE_PATH, 'dimensions': C.BLOOD_DIMENSIONS,
            'fallback_color1': C.RED, 'fallback_color2': C.DARK_RED
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class IceShard(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.ICE_DAMAGE, 'speed': C.ICE_SPEED, 'lifespan': C.ICE_LIFESPAN,
            'sprite_path': C.ICE_SPRITE_PATH, 'dimensions': C.ICE_DIMENSIONS,
            'fallback_color1': C.LIGHT_BLUE, 'fallback_color2': C.BLUE,
            'effect_type': "freeze"
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class ShadowProjectile(BaseProjectile): 
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.SHADOW_PROJECTILE_DAMAGE, 'speed': C.SHADOW_PROJECTILE_SPEED, 
            'lifespan': C.SHADOW_PROJECTILE_LIFESPAN,
            'sprite_path': C.SHADOW_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.SHADOW_PROJECTILE_DIMENSIONS, 
            'fallback_color1': C.DARK_GRAY, 'fallback_color2': C.BLACK,
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)
        self.custom_anim_speed_divisor = 1.2

class GreyProjectile(BaseProjectile): 
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.GREY_PROJECTILE_DAMAGE, 
            'speed': C.GREY_PROJECTILE_SPEED, 
            'lifespan': C.GREY_PROJECTILE_LIFESPAN,
            'sprite_path': C.GREY_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.GREY_PROJECTILE_DIMENSIONS, 
            'fallback_color1': C.GRAY, 'fallback_color2': C.DARK_GRAY,
            'effect_type': 'petrify'
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)
        self.custom_anim_speed_divisor = 1.0

#################### END OF FILE: projectiles.py ####################