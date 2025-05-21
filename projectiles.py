# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc. for PySide6.
Handles projectile effects including setting targets aflame or frozen.
"""
# version 2.0.4 (BoltProjectile initial position and upward firing rotation adjustment)
import os
import math # For atan2, degrees for rotation
import time # For monotonic timer
from typing import List, Optional, Any, Tuple, Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSizeF, Qt, QSize

# Game imports
import constants as C 
from assets import load_gif_frames, resource_path # Assumed Qt-based
from enemy import Enemy # For isinstance checks (assumed PySide6 compatible)
from statue import Statue # For isinstance checks (assumed PySide6 compatible)

# Logger import
try:
    from logger import debug
except ImportError:
    def debug(msg): print(f"DEBUG_PROJ: {msg}")

# --- Monotonic Timer ---
_start_time_projectiles_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_projectiles_monotonic) * 1000)
# --- End Monotonic Timer ---


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
        
        img_w_initial, img_h_initial = self.image.width(), self.image.height()
        
        spawn_offset_x = -30.0 
        spawn_offset_y= 0
        spawn_initial_x = float(x) # Default to player's center x for spawn
        spawn_initial_y = float(y) 
        if self.__class__.__name__ == "BoltProjectile":
            # Bolt projectile specific spawn X offset from player's center X
            # If owner player is facing right, spawn slightly in front
            # If owner player is facing left, spawn slightly in front (which is to the left)
            player_facing_right = getattr(owner_player, 'facing_right', True)
            bolt_x_offset_from_player_center = float(getattr(C,'TILE_SIZE', 40)/4) # Example: 1/4 tile in front
            
            if player_facing_right:
                spawn_initial_x = float(x) + bolt_x_offset_from_player_center
            else:
                spawn_initial_x = float(x) - bolt_x_offset_from_player_center
            spawn_offset_x = -10 # The main offset is handled by adjusting spawn_initial_x
            # spawn_offset_y = 30 # The main offset is handled by adjusting spawn_initial_y
        
        # self.pos = QPointF(spawn_initial_x + spawn_offset_x, float(y)) 
        self.pos = QPointF(spawn_initial_x + spawn_offset_x, spawn_initial_y + spawn_offset_y) 

        rect_x = self.pos.x() - img_w_initial / 2.0
        rect_y = self.pos.y() - img_h_initial / 2.0
        self.rect = QRectF(rect_x, rect_y, float(img_w_initial), float(img_h_initial))


        direction_mag = math.sqrt(direction_qpointf.x()**2 + direction_qpointf.y()**2)
        if direction_mag > 1e-6:
            norm_dir_x = direction_qpointf.x() / direction_mag
            norm_dir_y = direction_qpointf.y() / direction_mag
            self.vel = QPointF(norm_dir_x * self.speed, norm_dir_y * self.speed)
        else: 
            facing_right = getattr(owner_player, 'facing_right', True) 
            vel_x_fallback = self.speed if facing_right else -self.speed
            self.vel = QPointF(vel_x_fallback, 0.0)

        self.original_frames = [frame.copy() for frame in self.frames] 
        self._post_init_hook(self.vel) 

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
        if pixmap.size() == QSize(30,40): 
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0)))) 
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _update_rect_from_image_and_pos(self):
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = self.pos.x() - img_w / 2.0
            rect_y = self.pos.y() - img_h / 2.0
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif hasattr(self, 'rect'): 
            fallback_w, fallback_h = self.dimensions.width(), self.dimensions.height()
            self.rect.setRect(self.pos.x() - fallback_w/2.0, self.pos.y() - fallback_h/2.0, fallback_w, fallback_h)

    def _post_init_hook(self, final_velocity_qpointf: QPointF):
        pass

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def animate(self):
        if not self._alive or not self.frames or len(self.frames) <= 1:
            return 

        now = get_current_ticks_monotonic() 
        anim_duration = getattr(C, 'ANIM_FRAME_DURATION', 100) / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor') and self.custom_anim_speed_divisor > 0:
            anim_duration = getattr(C, 'ANIM_FRAME_DURATION', 100) / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            
            new_image_candidate = self.frames[self.current_frame_index]

            if not isinstance(self, BoltProjectile):
                if hasattr(self.vel, 'x') and self.vel.x() < -0.01: 
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

        frame_scaled_vel_x = self.vel.x() * dt_sec * C.FPS 
        frame_scaled_vel_y = self.vel.y() * dt_sec * C.FPS
        self.pos.setX(self.pos.x() + frame_scaled_vel_x)
        self.pos.setY(self.pos.y() + frame_scaled_vel_y)
        
        self._update_rect_from_image_and_pos()
        self.animate()

        current_time_ticks = get_current_ticks_monotonic() 
        if current_time_ticks - self.spawn_time > self.lifespan:
            self.kill(); return

        for platform_obj in platforms:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               hasattr(self, 'rect') and self.rect.intersects(platform_obj.rect):
                self.kill(); return 
        
        for char_target in characters_to_hit_list:
            if not hasattr(char_target, 'rect') or not isinstance(char_target.rect, QRectF) or \
               (hasattr(char_target, 'alive') and not char_target.alive()):
                continue
            
            if char_target is self.owner_player and (current_time_ticks - self.spawn_time < 100): 
                continue
            if isinstance(self, Fireball) and char_target is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False):
                continue
            if isinstance(self, (BloodShot, IceShard)) and char_target is self.owner_player: 
                continue

            if hasattr(self, 'rect') and self.rect.intersects(char_target.rect):
                can_damage_target = True
                if hasattr(char_target, 'is_taking_hit') and hasattr(char_target, 'hit_timer') and hasattr(char_target, 'hit_cooldown'):
                    if char_target.is_taking_hit and (current_time_ticks - char_target.hit_timer < char_target.hit_cooldown):
                        can_damage_target = False
                
                if self.effect_type == "freeze" and getattr(char_target, 'is_frozen', False): can_damage_target = False 
                elif self.effect_type == "aflame" and getattr(char_target, 'is_aflame', False): can_damage_target = False 

                if can_damage_target:
                    target_type_name = type(char_target).__name__
                    target_id_log = getattr(char_target, 'player_id', getattr(char_target, 'enemy_id', getattr(char_target, 'statue_id', 'UnknownTarget')))
                    owner_id_log = getattr(self.owner_player, 'player_id', 'Owner?') if self.owner_player else 'NoOwner'


                    if self.effect_type == 'petrify':
                        if isinstance(char_target, Statue): continue 
                        elif hasattr(char_target, 'petrify') and callable(char_target.petrify) and \
                             not getattr(char_target, 'is_petrified', False):
                            debug(f"GreyProjectile by P{owner_id_log} hit {target_type_name} {target_id_log}. Petrifying.")
                            char_target.petrify()
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
        vel_x_val = getattr(getattr(self, 'vel', None), 'x', lambda: 0.0)()
        if not isinstance(self, BoltProjectile): 
            image_flipped = vel_x_val < -0.01

        owner_player_id = getattr(getattr(self, 'owner_player', None), 'player_id', None)
        pos_x_val = getattr(getattr(self, 'pos', None), 'x', lambda: 0.0)()
        pos_y_val = getattr(getattr(self, 'pos', None), 'y', lambda: 0.0)()

        return {
            'id': getattr(self, 'projectile_id', f"unknown_{get_current_ticks_monotonic()}"), 
            'type': self.__class__.__name__,
            'pos': (pos_x_val, pos_y_val), 
            'vel': (vel_x_val, getattr(getattr(self, 'vel', None), 'y', lambda: 0.0)()),
            'owner_id': owner_player_id,
            'frame': getattr(self, 'current_frame_index', 0), 
            'spawn_time': getattr(self, 'spawn_time', 0),
            'image_flipped': image_flipped, 
            'effect_type': getattr(self, 'effect_type', None)
        }

    def set_network_data(self, data: Dict[str, Any]):
        if hasattr(self, 'pos') and isinstance(self.pos, QPointF) and 'pos' in data:
            self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        if hasattr(self, 'vel') and isinstance(self.vel, QPointF) and 'vel' in data:
            self.vel.setX(data['vel'][0]); self.vel.setY(data['vel'][1])
        
        self._update_rect_from_image_and_pos() 
        self.current_frame_index = data.get('frame', getattr(self, 'current_frame_index', 0))
        self.effect_type = data.get('effect_type', getattr(self, 'effect_type', None))
        
        old_center_qpointf = self.rect.center() if hasattr(self, 'rect') else QPointF()

        if not self.frames or (len(self.frames) == 1 and self.frames[0].size() == QSize(1,1)): 
            pass 

        if not self.frames: 
            self.image = QPixmap(1,1); self.image.fill(QColor(*(getattr(C, 'MAGENTA', (255,0,255)))))
            self._update_rect_from_image_and_pos(); return

        self.current_frame_index = self.current_frame_index % len(self.frames) if self.frames else 0
        base_image = self.frames[self.current_frame_index] if self.frames else self.image 

        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            qimg = base_image.toImage(); 
            self.image = QPixmap.fromImage(qimg.mirrored(True, False)) if not qimg.isNull() else base_image
        else: 
            self.image = base_image
        
        if self.image and not self.image.isNull():
            new_img_w, new_img_h = float(self.image.width()), float(self.image.height())
            if hasattr(self, 'rect'):
                self.rect.setRect(old_center_qpointf.x() - new_img_w/2.0, old_center_qpointf.y() - new_img_h/2.0, new_img_w, new_img_h)
            self.dimensions = QSizeF(new_img_w, new_img_h)


# --- Specific Projectile Classes ---
class Fireball(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.FIREBALL_DAMAGE, 'speed': C.FIREBALL_SPEED, 'lifespan': C.FIREBALL_LIFESPAN,
            'sprite_path': C.FIREBALL_SPRITE_PATH, 'dimensions': C.FIREBALL_DIMENSIONS,
            'fallback_color1': getattr(C, 'ORANGE_RED', (255, 69, 0)), 
            'fallback_color2': getattr(C, 'RED', (255, 0, 0)),
            'effect_type': "aflame"
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class PoisonShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.POISON_DAMAGE, 'speed': C.POISON_SPEED, 'lifespan': C.POISON_LIFESPAN,
            'sprite_path': C.POISON_SPRITE_PATH, 'dimensions': C.POISON_DIMENSIONS,
            'fallback_color1': getattr(C, 'GREEN', (0,255,0)), 
            'fallback_color2': getattr(C, 'DARK_GREEN', (0,100,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class BoltProjectile(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BOLT_DAMAGE, 'speed': C.BOLT_SPEED, 'lifespan': C.BOLT_LIFESPAN,
            'sprite_path': C.BOLT_SPRITE_PATH, 'dimensions': C.BOLT_DIMENSIONS,
            'fallback_color1': getattr(C, 'YELLOW', (255,255,0)), 
            'fallback_color2': getattr(C, 'YELLOW', (255,255,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

    def _post_init_hook(self, final_velocity_qpointf: QPointF):
        if not self.original_frames or (self.original_frames and self.original_frames[0].isNull()):
            debug("BoltProjectile: No original frames for rotation."); return

        self.frames = [frame.copy() for frame in self.original_frames] # Work with copies for transformation
        
        # Calculate the flight angle based on velocity
        # atan2 returns angle in radians from positive X-axis.
        # Positive Y is typically downwards in screen/Qt coordinates.
        # Velocity components: final_velocity_qpointf.x(), final_velocity_qpointf.y()
        flight_angle_rad = math.atan2(final_velocity_qpointf.y(), final_velocity_qpointf.x())
        flight_angle_deg = math.degrees(flight_angle_rad)

        # --- Determine base rotation assuming sprite is drawn pointing UP in its source image ---
        # To align an UP-pointing sprite with the flight_angle_deg, we need to rotate it by (flight_angle_deg + 90)
        # Example:
        # - Firing RIGHT (flight_angle_deg=0): Sprite needs to rotate 0+90=90 deg (clockwise) to point right.
        # - Firing UP (flight_angle_deg=-90): Sprite needs to rotate -90+90=0 deg to point up.
        # - Firing LEFT (flight_angle_deg=180): Sprite needs to rotate 180+90=270 (or -90) deg to point left.
        # - Firing DOWN (flight_angle_deg=90): Sprite needs to rotate 90+90=180 deg to point down.
        base_rotation_deg = flight_angle_deg + 90.0
        
        # --- Conditional rotation adjustment for firing UP ---
        # Check if firing primarily upwards (Y component is negative and dominant)
        is_firing_predominantly_upwards = False
        if final_velocity_qpointf.y() < -0.01: # Moving upwards (Y is negative)
            # Check if the upward component's magnitude is significantly larger than horizontal
            # Or if the angle is within a certain "upward cone"
            if abs(final_velocity_qpointf.y()) > abs(final_velocity_qpointf.x()) * 1.5: # Factor can be tuned
                is_firing_predominantly_upwards = True
            elif -120 < flight_angle_deg < -60 : # Angle between -60 and -120 deg (cone around -90)
                 is_firing_predominantly_upwards = True
        
        if is_firing_predominantly_upwards:
            # The base_rotation_deg has aligned the UP-pointing sprite to also point UP.
            # To make it point 90 degrees LEFT from this UPWARD orientation,
            # the final visual rotation of the sprite should be -90 degrees.
            debug(f"BoltProjectile (owner P{getattr(self.owner_player,'player_id','?')}) firing upwards (flight angle: {flight_angle_deg:.1f}). Overriding visual rotation to -90 deg (to point left).")
            final_rotation_deg = -90.0 
        else:
            final_rotation_deg = base_rotation_deg # Use the standard alignment for other directions

        # Apply the final_rotation_deg to all frames
        transformed_frames_new: List[QPixmap] = []
        for frame_pixmap in self.frames: # self.frames currently holds copies of original_frames
            if frame_pixmap.isNull():
                transformed_frames_new.append(frame_pixmap); continue
            
            center = QPointF(frame_pixmap.width() / 2.0, frame_pixmap.height() / 2.0)
            transform = QTransform().translate(center.x(), center.y()).rotate(final_rotation_deg).translate(-center.x(), -center.y())
            rotated_pixmap = frame_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            transformed_frames_new.append(rotated_pixmap)
        
        if transformed_frames_new: self.frames = transformed_frames_new # Replace with rotated frames
        
        # Update current image and rect based on the (potentially new) first frame and its rotation
        self.current_frame_index = 0
        if self.frames and self.frames[0] and not self.frames[0].isNull():
            self.image = self.frames[0]
            self._update_rect_from_image_and_pos() 
        else:
            # Fallback if transformation somehow resulted in null/empty frames
            debug("BoltProjectile: Frame transformation resulted in invalid frames. Using placeholder.")
            fallback_color_tuple = getattr(C, 'MAGENTA', (255,0,255))
            # Use original dimensions before rotation if possible, else a small default
            dim_w = self.original_frames[0].width() if self.original_frames and not self.original_frames[0].isNull() else int(self.dimensions.width())
            dim_h = self.original_frames[0].height() if self.original_frames and not self.original_frames[0].isNull() else int(self.dimensions.height())
            self.image = QPixmap(max(1,dim_w), max(1,dim_h))
            self.image.fill(QColor(*fallback_color_tuple)) 
            self.frames = [self.image] # Ensure self.frames has at least one valid pixmap
            self._update_rect_from_image_and_pos()


    def animate(self): # Bolt animation might be simpler if it's just one rotated frame
        if not self._alive or not self.frames: return
        # If Bolt is a single rotated frame, no need to cycle.
        # If it's an animated GIF that's then rotated, super().animate() handles cycling.
        if len(self.frames) <= 1:
             if self.frames and self.frames[0] and not self.frames[0].isNull():
                 self.image = self.frames[0] 
             return
        super().animate() # Call base if it's a multi-frame rotated animation


class BloodShot(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.BLOOD_DAMAGE, 'speed': C.BLOOD_SPEED, 'lifespan': C.BLOOD_LIFESPAN,
            'sprite_path': C.BLOOD_SPRITE_PATH, 'dimensions': C.BLOOD_DIMENSIONS,
            'fallback_color1': getattr(C, 'RED', (255,0,0)), 
            'fallback_color2': getattr(C, 'DARK_RED', (139,0,0))
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)

class IceShard(BaseProjectile):
    def __init__(self, x: float, y: float, direction_qpointf: QPointF, owner_player: Any):
        config = {
            'damage': C.ICE_DAMAGE, 'speed': C.ICE_SPEED, 'lifespan': C.ICE_LIFESPAN,
            'sprite_path': C.ICE_SPRITE_PATH, 'dimensions': C.ICE_DIMENSIONS,
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
            'sprite_path': C.SHADOW_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.SHADOW_PROJECTILE_DIMENSIONS, 
            'fallback_color1': getattr(C, 'DARK_GRAY', (50,50,50)), 
            'fallback_color2': getattr(C, 'BLACK', (0,0,0)),
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
            'fallback_color1': getattr(C, 'GRAY', (128,128,128)), 
            'fallback_color2': getattr(C, 'DARK_GRAY', (50,50,50)),
            'effect_type': 'petrify'
        }
        super().__init__(x, y, direction_qpointf, owner_player, config)
        self.custom_anim_speed_divisor = 1.0