# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc. for PySide6.
Handles projectile effects including setting targets aflame or frozen.
"""
# version 2.0.2 
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
        self.owner_player = owner_player # Should be a Player instance
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan']
        # Ensure dimensions are float for QSizeF
        self.dimensions = QSizeF(float(config['dimensions'][0]), float(config['dimensions'][1]))
        self.sprite_path = config['sprite_path']
        self.effect_type = config.get('effect_type') # e.g., "aflame", "freeze", "petrify"

        full_gif_path = resource_path(self.sprite_path)
        self.frames: List[QPixmap] = load_gif_frames(full_gif_path) # Returns List[QPixmap]

        if not self.frames or self._is_placeholder_qpixmap(self.frames[0]):
            debug(f"Warning: Projectile GIF '{full_gif_path}' failed. Using fallback for {self.__class__.__name__}.")
            # Ensure fallback colors are tuples
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
        
        # Update dimensions based on the first (potentially fallback) frame
        if self.frames and self.frames[0] and not self.frames[0].isNull():
            self.dimensions = QSizeF(float(self.frames[0].width()), float(self.frames[0].height()))
        else: # Absolute fallback if frames list is still bad
            self.dimensions = QSizeF(10.0, 10.0) # Small default
            self.image = QPixmap(10,10); self.image.fill(QColor(255,0,255)) # Magenta error
            self.frames = [self.image]


        self.current_frame_index = 0
        self.image: QPixmap = self.frames[self.current_frame_index] # Should be valid now
        
        # Initial rect based on current image and spawn position (center of projectile)
        rect_w, rect_h = self.image.width(), self.image.height()
        rect_x = float(x - rect_w / 2.0) 
        rect_y = float(y - rect_h / 2.0)
        self.rect = QRectF(rect_x, rect_y, float(rect_w), float(rect_h))
        #projectile spawn from player
        self.pos = QPointF(float(x)-30, float(y)) # Position is center of projectile

        # Normalize direction and set velocity
        direction_mag = math.sqrt(direction_qpointf.x()**2 + direction_qpointf.y()**2)
        if direction_mag > 1e-6:
            norm_dir_x = direction_qpointf.x() / direction_mag
            norm_dir_y = direction_qpointf.y() / direction_mag
            self.vel = QPointF(norm_dir_x * self.speed, norm_dir_y * self.speed)
        else: # Fallback if direction is zero vector
            facing_right = getattr(owner_player, 'facing_right', True) # Safe getattr
            vel_x_fallback = self.speed if facing_right else -self.speed
            self.vel = QPointF(vel_x_fallback, 0.0)

        self.original_frames = [frame.copy() for frame in self.frames] # For transformations like Bolt
        self._post_init_hook(self.vel) # For special setup like Bolt rotation

        # Ensure image and rect are consistent after potential _post_init_hook changes
        if self.frames and self.current_frame_index < len(self.frames) and \
           self.frames[self.current_frame_index] and not self.frames[self.current_frame_index].isNull():
            self.image = self.frames[self.current_frame_index]
            self.dimensions = QSizeF(float(self.image.width()), float(self.image.height()))
        self._update_rect_from_image_and_pos() 

        self.spawn_time = get_current_ticks_monotonic() # Use monotonic timer
        self.last_anim_update = self.spawn_time
        proj_type_name = self.__class__.__name__.lower()
        owner_id_str = str(getattr(owner_player, 'player_id', 'unknownP')) # Safe getattr
        self.projectile_id = f"{proj_type_name}_{owner_id_str}_{self.spawn_time}"
        self._alive = True # Projectile starts alive
        
        # Reference to game_elements, to be set by the Player class when firing
        self.game_elements_ref: Optional[Dict[str, Any]] = None
        
    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        # Check if the pixmap is one of the known placeholders from assets.py
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40): # Common placeholder size
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0)))) # Safe getattr
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _update_rect_from_image_and_pos(self):
        """Updates self.rect (centered) based on self.image and self.pos (center)."""
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = self.pos.x() - img_w / 2.0
            rect_y = self.pos.y() - img_h / 2.0
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif hasattr(self, 'rect'): # Fallback if image is null
            fallback_w, fallback_h = self.dimensions.width(), self.dimensions.height()
            self.rect.setRect(self.pos.x() - fallback_w/2.0, self.pos.y() - fallback_h/2.0, fallback_w, fallback_h)

    def _post_init_hook(self, final_velocity_qpointf: QPointF):
        """Hook for subclasses to perform actions after basic init and velocity calculation."""
        pass

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False
        # debug(f"Projectile {self.projectile_id} killed.") # Optional log

    def animate(self):
        if not self._alive or not self.frames or len(self.frames) <= 1:
            return # No animation if not alive, no frames, or single static frame

        now = get_current_ticks_monotonic() # Use monotonic timer
        # Default animation speed, can be overridden by subclasses
        anim_duration = getattr(C, 'ANIM_FRAME_DURATION', 100) / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor') and self.custom_anim_speed_divisor > 0:
            anim_duration = getattr(C, 'ANIM_FRAME_DURATION', 100) / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            
            new_image_candidate = self.frames[self.current_frame_index]

            # Handle mirroring for non-Bolt projectiles (Bolt rotation is pre-applied)
            if not isinstance(self, BoltProjectile):
                # Check velocity for facing direction; use x() for QPointF
                if hasattr(self.vel, 'x') and self.vel.x() < -0.01: 
                    qimg = new_image_candidate.toImage()
                    if not qimg.isNull():
                        self.image = QPixmap.fromImage(qimg.mirrored(True, False))
                    else: self.image = new_image_candidate # Fallback if image conversion fails
                else:
                    self.image = new_image_candidate
            else: # BoltProjectile uses pre-rotated frames
                self.image = new_image_candidate
            
            self._update_rect_from_image_and_pos()

    def update(self, dt_sec: float, platforms: List[Any], characters_to_hit_list: List[Any]):
        if not self._alive: return

        # Update position: pos += vel * (dt_sec * FPS_TARGET)
        # The (dt_sec * C.FPS) effectively scales velocity to be per-frame if C.FPS is the target frame rate.
        # If dt_sec is already true delta time, then just pos += vel * dt_sec.
        # Assuming C.FPS is the target simulation rate for velocity units.
        frame_scaled_vel_x = self.vel.x() * dt_sec * C.FPS 
        frame_scaled_vel_y = self.vel.y() * dt_sec * C.FPS
        self.pos.setX(self.pos.x() + frame_scaled_vel_x)
        self.pos.setY(self.pos.y() + frame_scaled_vel_y)
        
        self._update_rect_from_image_and_pos()
        self.animate()

        current_time_ticks = get_current_ticks_monotonic() # Use monotonic timer
        if current_time_ticks - self.spawn_time > self.lifespan:
            self.kill(); return

        # Collision with platforms
        for platform_obj in platforms:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               hasattr(self, 'rect') and self.rect.intersects(platform_obj.rect):
                self.kill(); return # Projectile dies on platform impact
        
        # Collision with characters
        for char_target in characters_to_hit_list:
            if not hasattr(char_target, 'rect') or not isinstance(char_target.rect, QRectF) or \
               (hasattr(char_target, 'alive') and not char_target.alive()):
                continue
            
            # Prevent self-collision too early or for specific projectiles
            if char_target is self.owner_player and (current_time_ticks - self.spawn_time < 100): # Brief immunity
                continue
            if isinstance(self, Fireball) and char_target is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False):
                continue
            if isinstance(self, (BloodShot, IceShard)) and char_target is self.owner_player: # These types never hit owner
                continue

            if hasattr(self, 'rect') and self.rect.intersects(char_target.rect):
                # Check if target is invincible (e.g., in hit stun)
                can_damage_target = True
                if hasattr(char_target, 'is_taking_hit') and hasattr(char_target, 'hit_timer') and hasattr(char_target, 'hit_cooldown'):
                    if char_target.is_taking_hit and (current_time_ticks - char_target.hit_timer < char_target.hit_cooldown):
                        can_damage_target = False
                
                # Prevent re-applying status effects if already active
                if self.effect_type == "freeze" and getattr(char_target, 'is_frozen', False): can_damage_target = False 
                elif self.effect_type == "aflame" and getattr(char_target, 'is_aflame', False): can_damage_target = False 

                if can_damage_target:
                    target_type_name = type(char_target).__name__
                    target_id_log = getattr(char_target, 'player_id', getattr(char_target, 'enemy_id', getattr(char_target, 'statue_id', 'UnknownTarget')))
                    owner_id_log = getattr(self.owner_player, 'player_id', 'Owner?') if self.owner_player else 'NoOwner'


                    if self.effect_type == 'petrify':
                        if isinstance(char_target, Statue): continue # Grey projectiles might not affect statues
                        elif hasattr(char_target, 'petrify') and callable(char_target.petrify) and \
                             not getattr(char_target, 'is_petrified', False):
                            debug(f"GreyProjectile by P{owner_id_log} hit {target_type_name} {target_id_log}. Petrifying.")
                            char_target.petrify()
                            self.kill(); return # Projectile consumed

                    if self.damage > 0 and hasattr(char_target, 'take_damage') and callable(char_target.take_damage): 
                        debug(f"{self.__class__.__name__} (Owner: P{owner_id_log}) hit {target_type_name} {target_id_log} for {self.damage} DMG.")
                        char_target.take_damage(self.damage) 
                    
                    # Apply status effects
                    if self.effect_type == "freeze" and hasattr(char_target, 'apply_freeze_effect') and callable(char_target.apply_freeze_effect) and \
                       not getattr(char_target, 'is_frozen', False): # Check if already frozen
                        char_target.apply_freeze_effect()
                    elif self.effect_type == "aflame" and hasattr(char_target, 'apply_aflame_effect') and callable(char_target.apply_aflame_effect) and \
                         not getattr(char_target, 'is_aflame', False): # Check if already aflame
                        # Green enemies might be immune or react differently, handled by Enemy class itself
                        char_target.apply_aflame_effect()
                                
                    self.kill(); return # Projectile consumed on hit
        
    def get_network_data(self) -> Dict[str, Any]:
        image_flipped = False
        # Check vel and its x attribute safely
        vel_x_val = getattr(getattr(self, 'vel', None), 'x', lambda: 0.0)()
        if not isinstance(self, BoltProjectile): # Bolt rotation handles direction
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
            'image_flipped': image_flipped, # For client-side rendering if needed
            'effect_type': getattr(self, 'effect_type', None)
        }

    def set_network_data(self, data: Dict[str, Any]):
        # Ensure pos and vel exist and are QPointF before setting
        if hasattr(self, 'pos') and isinstance(self.pos, QPointF) and 'pos' in data:
            self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        if hasattr(self, 'vel') and isinstance(self.vel, QPointF) and 'vel' in data:
            self.vel.setX(data['vel'][0]); self.vel.setY(data['vel'][1])
        
        self._update_rect_from_image_and_pos() # Update rect based on new pos
        self.current_frame_index = data.get('frame', getattr(self, 'current_frame_index', 0))
        self.effect_type = data.get('effect_type', getattr(self, 'effect_type', None))
        # spawn_time is usually authoritative from server, not set on client unless for creation
        
        old_center_qpointf = self.rect.center() if hasattr(self, 'rect') else QPointF()

        if not self.frames or (len(self.frames) == 1 and self.frames[0].size() == QSize(1,1)): # Placeholder check
            pass # Do nothing if frames are bad

        if not self.frames: # Should not happen if constructor handles fallback well
            self.image = QPixmap(1,1); self.image.fill(QColor(*(getattr(C, 'MAGENTA', (255,0,255)))))
            self._update_rect_from_image_and_pos(); return

        # Ensure frame_index is within bounds
        self.current_frame_index = self.current_frame_index % len(self.frames) if self.frames else 0
        base_image = self.frames[self.current_frame_index] if self.frames else self.image # Fallback to current image

        # Apply mirroring based on network data (BoltProjectile handles its own rotation)
        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            qimg = base_image.toImage(); 
            self.image = QPixmap.fromImage(qimg.mirrored(True, False)) if not qimg.isNull() else base_image
        else: 
            self.image = base_image
        
        # Update dimensions and rect based on potentially new image
        if self.image and not self.image.isNull():
            new_img_w, new_img_h = float(self.image.width()), float(self.image.height())
            if hasattr(self, 'rect'):
                self.rect.setRect(old_center_qpointf.x() - new_img_w/2.0, old_center_qpointf.y() - new_img_h/2.0, new_img_w, new_img_h)
            self.dimensions = QSizeF(new_img_w, new_img_h)


# --- Specific Projectile Classes (constructors remain largely the same) ---
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
            # No effect_type, just damage
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
        # This rotation logic assumes self.frames and self.original_frames are populated
        if not self.original_frames or (self.original_frames and self.original_frames[0].isNull()):
            debug("BoltProjectile: No original frames for rotation."); return

        self.frames = [frame.copy() for frame in self.original_frames] # Work with copies
        
        angle_rad = math.atan2(final_velocity_qpointf.y(), final_velocity_qpointf.x())
        angle_deg = math.degrees(angle_rad)

        transformed_frames_new: List[QPixmap] = []
        for frame_pixmap in self.frames:
            if frame_pixmap.isNull():
                transformed_frames_new.append(frame_pixmap); continue # Preserve null if it was there
            
            # Rotate around center
            center = QPointF(frame_pixmap.width() / 2.0, frame_pixmap.height() / 2.0)
            transform = QTransform().translate(center.x(), center.y()).rotate(angle_deg).translate(-center.x(), -center.y())
            rotated_pixmap = frame_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            transformed_frames_new.append(rotated_pixmap)
        
        if transformed_frames_new: self.frames = transformed_frames_new
        
        # Update current image and rect after transformation
        self.current_frame_index = 0
        if self.frames and self.frames[0] and not self.frames[0].isNull():
            self.image = self.frames[0]
            self._update_rect_from_image_and_pos() 
        else: # Fallback if transformation somehow failed
            fallback_color_tuple = getattr(C, 'MAGENTA', (255,0,255))
            self.image = QPixmap(int(self.dimensions.width()), int(self.dimensions.height()))
            self.image.fill(QColor(*fallback_color_tuple)) 
            self.frames = [self.image] # Ensure self.frames has at least one valid pixmap


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
        self.custom_anim_speed_divisor = 1.2 # Example: makes this projectile animate slightly slower

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
        self.custom_anim_speed_divisor = 1.0 # Normal animation speed