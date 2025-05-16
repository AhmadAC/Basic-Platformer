########## START OF FILE: projectiles.py ##########
# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc.
"""
# version 1.0.6 (Bolt vertical flip for upwards, horizontal rotation for L/R)
import pygame
import os # For path joining
import math # For math.atan2 and math.degrees if more complex rotation is needed
import constants as C
from assets import load_gif_frames, resource_path
# Import Enemy type for isinstance checks if needed, and debug
from enemy import Enemy # For type checking and debug log
try:
    from logger import debug # Use your logger
except ImportError:
    def debug(msg): print(f"DEBUG_PROJ: {msg}")


class BaseProjectile(pygame.sprite.Sprite):
    def __init__(self, x, y, direction_vector, owner_player, config):
        super().__init__()
        self.owner_player = owner_player
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan']
        self.dimensions = config['dimensions']
        self.sprite_path = config['sprite_path']
        self.effect_type = config.get('effect_type', None) 
        
        full_gif_path = resource_path(self.sprite_path)
        self.frames = load_gif_frames(full_gif_path)
        
        if not self.frames or \
           (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): 
            debug(f"Warning: Projectile GIF '{full_gif_path}' failed to load or is default placeholder. Using fallback.")
            if self.frames and not (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                self.dimensions = self.frames[0].get_size()

            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) 
            pygame.draw.circle(self.image, config.get('fallback_color1', C.ORANGE_RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//3)
            pygame.draw.circle(self.image, config.get('fallback_color2', C.RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//4)
            self.frames = [self.image]
        else: 
            self.dimensions = self.frames[0].get_size() 
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index]
        self.rect = self.image.get_rect(center=(x, y))
        
        if direction_vector.length_squared() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: 
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed

        # Store original frames before _post_init_hook might modify them (especially for Bolt)
        self.original_frames = [frame.copy() for frame in self.frames]
        self._post_init_hook(self.vel) 

        self.image = self.frames[self.current_frame_index % len(self.frames)] 
        self.rect = self.image.get_rect(center=(x,y)) 
        self.pos = pygame.math.Vector2(self.rect.center)
        
        self.spawn_time = pygame.time.get_ticks()
        self.last_anim_update = self.spawn_time
        proj_type_name = self.__class__.__name__.lower()
        self.projectile_id = f"{proj_type_name}_{getattr(owner_player, 'player_id', 'unknown')}_{self.spawn_time}"

    def _post_init_hook(self, final_velocity_vector):
        """ Hook for subclasses to perform actions after basic init, like rotation based on velocity. """
        pass 

    def animate(self):
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor'): 
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            base_image_for_anim = self.frames[self.current_frame_index] # Use potentially transformed frames

            # For most projectiles, flipping is based on horizontal velocity for visual consistency.
            # BoltProjectile handles its primary orientation in _post_init_hook and its animate().
            if not isinstance(self, BoltProjectile): 
                if self.vel.x < 0: 
                    self.image = pygame.transform.flip(base_image_for_anim, True, False)
                else:
                    self.image = base_image_for_anim 
            else: 
                # Bolt's frames are already oriented by _post_init_hook.
                # Its animate method just cycles through these pre-oriented frames.
                self.image = base_image_for_anim 


            self.rect = self.image.get_rect(center=old_center)

    def update(self, dt_sec, platforms, characters_to_hit_group): 
        self.pos += self.vel * dt_sec * C.FPS 
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.animate()

        if pygame.time.get_ticks() - self.spawn_time > self.lifespan:
            self.kill()
            return

        if pygame.sprite.spritecollideany(self, platforms):
            self.kill()
            return

        hit_characters = pygame.sprite.spritecollide(self, characters_to_hit_group, False)
        for char in hit_characters:
            if char is self.owner_player and (pygame.time.get_ticks() - self.spawn_time < 100): 
                continue
            if char is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False) and self.__class__.__name__ == "Fireball": 
                continue
            if char is self.owner_player and self.__class__.__name__ == "BloodShot":
                continue


            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                if self.effect_type == "freeze" and hasattr(char, 'is_frozen') and char.is_frozen:
                    can_damage_target = False 
                elif self.effect_type == "aflame" and hasattr(char, 'is_aflame') and char.is_aflame:
                    can_damage_target = False 

                if can_damage_target:
                    if self.effect_type == 'petrify' and hasattr(char, 'petrify') and not getattr(char, 'is_petrified', False):
                        debug(f"Grey shot hit {type(char).__name__} {getattr(char, 'player_id', getattr(char, 'enemy_id', ''))}. Petrifying.")
                        char.petrify()
                        self.kill() 
                        return 

                    char.take_damage(self.damage) 
                    
                    if self.effect_type == "freeze":
                        if hasattr(char, 'apply_freeze_effect'):
                            char.apply_freeze_effect()
                    elif self.effect_type == "aflame":
                        if isinstance(char, Enemy) and getattr(char, 'color_name', None) == 'green':
                            if hasattr(char, 'apply_aflame_effect'):
                                debug(f"Projectile with 'aflame' effect hit green Enemy {getattr(char, 'enemy_id', 'Unknown')}. Applying aflame effect.")
                                char.apply_aflame_effect()
                                
                    self.kill() 
                    return 
        
    def get_network_data(self):
        image_flipped = False # For Bolt, this might be less relevant if rotation covers direction
        if not isinstance(self, BoltProjectile):
            image_flipped = self.vel.x < 0

        return {
            'id': self.projectile_id,
            'type': self.__class__.__name__, 
            'pos': (self.pos.x, self.pos.y),
            'vel': (self.vel.x, self.vel.y), 
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index,
            'spawn_time': self.spawn_time,
            'image_flipped': image_flipped, # Bolt's orientation is more complex than simple flip
            'effect_type': self.effect_type 
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data:
             self.vel.x, self.vel.y = data['vel'] # Important for Bolt's _post_init_hook if re-applied
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type) 
        
        old_center = self.rect.center
        
        # Check if frames need to be (re)loaded or (re)transformed
        # This is especially important if a client joins late or if projectile state needs full reconstruction
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): 
            if not self.sprite_path: 
                proj_type_name_from_data = data.get('type')
                if proj_type_name_from_data:
                    path_const_name = f"{proj_type_name_from_data.upper()}_SPRITE_PATH" 
                    if hasattr(C, path_const_name):
                        self.sprite_path = getattr(C, path_const_name)
                
            if self.sprite_path:
                full_gif_path = resource_path(self.sprite_path)
                # Use self.original_frames if available and valid, otherwise load fresh
                if hasattr(self, 'original_frames') and self.original_frames and \
                   not (len(self.original_frames) == 1 and self.original_frames[0].get_size() == (30,40) and self.original_frames[0].get_at((0,0)) == C.RED):
                    self.frames = [frame.copy() for frame in self.original_frames] # Work with copies
                else:
                    self.frames = load_gif_frames(full_gif_path)
                    self.original_frames = [frame.copy() for frame in self.frames] # Store originals

                if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                    fallback_dims = self.dimensions if self.dimensions else (1,1)
                    self.frames = [pygame.Surface(fallback_dims, pygame.SRCALPHA)] 
                    self.frames[0].fill(C.MAGENTA) 
                else: 
                    self.dimensions = self.frames[0].get_size() 
                
                # Re-apply transformations based on network velocity
                final_velocity_vector_for_hook = pygame.math.Vector2(data.get('vel', (self.vel.x, self.vel.y)))
                self._post_init_hook(final_velocity_vector_for_hook) 


        if not self.frames: 
            self.image = pygame.Surface((1,1)) 
            self.rect = self.image.get_rect(center=old_center)
            return

        self.current_frame_index = self.current_frame_index % len(self.frames)
        base_image = self.frames[self.current_frame_index] # These are now the (potentially) transformed frames

        # For non-Bolt projectiles, simple flip might still apply based on net data if needed,
        # but Bolt handles its own orientation entirely in _post_init_hook based on velocity.
        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            self.image = pygame.transform.flip(base_image, True, False)
        else: 
            self.image = base_image 
        self.rect = self.image.get_rect(center=old_center)


class Fireball(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.FIREBALL_DAMAGE, 'speed': C.FIREBALL_SPEED, 'lifespan': C.FIREBALL_LIFESPAN,
            'sprite_path': C.FIREBALL_SPRITE_PATH, 'dimensions': C.FIREBALL_DIMENSIONS,
            'fallback_color1': (255,120,0,200), 'fallback_color2': C.RED,
            'effect_type': "aflame"
        }
        super().__init__(x, y, direction_vector, owner_player, config)

class PoisonShot(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.POISON_DAMAGE, 'speed': C.POISON_SPEED, 'lifespan': C.POISON_LIFESPAN,
            'sprite_path': C.POISON_SPRITE_PATH, 'dimensions': C.POISON_DIMENSIONS,
            'fallback_color1': (0,150,0,200), 'fallback_color2': C.DARK_GREEN
        }
        super().__init__(x, y, direction_vector, owner_player, config)

class BoltProjectile(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.BOLT_DAMAGE, 'speed': C.BOLT_SPEED, 'lifespan': C.BOLT_LIFESPAN,
            'sprite_path': C.BOLT_SPRITE_PATH, 'dimensions': C.BOLT_DIMENSIONS, 
            'fallback_color1': (255,255,0,200), 'fallback_color2': C.YELLOW
        }
        super().__init__(x, y, direction_vector, owner_player, config)

    def _post_init_hook(self, final_velocity_vector):
        # Use self.original_frames for transformations to avoid cumulative effects
        if not self.original_frames or not self.original_frames[0]: return 
        
        self.frames = [frame.copy() for frame in self.original_frames] # Start with fresh copies

        vx, vy = final_velocity_vector.x, final_velocity_vector.y
        transformed_frames = []

        if abs(vy) > abs(vx) * 1.5 and vy < 0: # Moving primarily upwards
            debug(f"Bolt shot upwards (vx:{vx:.2f}, vy:{vy:.2f}). Applying vertical flip.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.flip(frame, False, True)) # Flip vertically
                elif frame:
                    transformed_frames.append(frame)
        elif vx > 0: # Shot right (and not primarily vertical)
            debug(f"Bolt shot right (vx:{vx:.2f}, vy:{vy:.2f}). Rotating 90 deg left.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.rotate(frame, 90)) # Rotate 90 deg left
                elif frame:
                    transformed_frames.append(frame)
        elif vx < 0: # Shot left (and not primarily vertical)
            debug(f"Bolt shot left (vx:{vx:.2f}, vy:{vy:.2f}). Rotating 90 deg right.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.rotate(frame, -90)) # Rotate 90 deg right
                elif frame:
                    transformed_frames.append(frame)
        else: # No specific transformation (e.g., shot straight down or vx=0, vy=0)
            transformed_frames = self.frames # Use as is

        if transformed_frames:
            self.frames = transformed_frames
        
        self.current_frame_index = 0 
        if self.frames: # Ensure self.frames is not empty after transformations
             self.image = self.frames[self.current_frame_index % len(self.frames)]
        else: # Fallback if something went wrong with frame processing
            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA)
            self.image.fill(C.MAGENTA)
            self.frames = [self.image] # Ensure self.frames has at least one image

    def animate(self): 
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor'):
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index] 
            self.rect = self.image.get_rect(center=old_center)


class BloodShot(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.BLOOD_DAMAGE, 'speed': C.BLOOD_SPEED, 'lifespan': C.BLOOD_LIFESPAN,
            'sprite_path': C.BLOOD_SPRITE_PATH, 'dimensions': C.BLOOD_DIMENSIONS,
            'fallback_color1': (150,0,0,200), 'fallback_color2': C.DARK_RED
        }
        super().__init__(x, y, direction_vector, owner_player, config)

class IceShard(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.ICE_DAMAGE, 'speed': C.ICE_SPEED, 'lifespan': C.ICE_LIFESPAN,
            'sprite_path': C.ICE_SPRITE_PATH, 'dimensions': C.ICE_DIMENSIONS,
            'fallback_color1': (150,200,255,200), 'fallback_color2': C.LIGHT_BLUE,
            'effect_type': "freeze"
        }
        super().__init__(x, y, direction_vector, owner_player, config)

class ShadowProjectile(BaseProjectile): 
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.SHADOW_PROJECTILE_DAMAGE, 'speed': C.SHADOW_PROJECTILE_SPEED, 
            'lifespan': C.SHADOW_PROJECTILE_LIFESPAN,
            'sprite_path': C.SHADOW_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.SHADOW_PROJECTILE_DIMENSIONS, 
            'fallback_color1': (50,50,50,200), 'fallback_color2': C.BLACK,
            'effect_type': None 
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        self.custom_anim_speed_divisor = 1.2 

class GreyProjectile(BaseProjectile): 
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.GREY_PROJECTILE_DAMAGE, 'speed': C.GREY_PROJECTILE_SPEED, 
            'lifespan': C.GREY_PROJECTILE_LIFESPAN,
            'sprite_path': C.GREY_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.GREY_PROJECTILE_DIMENSIONS, 
            'fallback_color1': (100,100,100,200), 'fallback_color2': C.DARK_GRAY,
            'effect_type': 'petrify' 
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        self.custom_anim_speed_divisor = 1.0
########## END OF FILE: projectiles.py ##########