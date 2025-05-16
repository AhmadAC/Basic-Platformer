########## START OF FILE: projectiles.py ##########
# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc.
"""
# version 1.0.4 (Bolt rotation fix, Ice Shot fix trigger, Blood Shot health cost trigger)
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
            # Update dimensions if actual GIF loaded and it's not a placeholder
            if self.frames and not (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                self.dimensions = self.frames[0].get_size()

            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) 
            pygame.draw.circle(self.image, config.get('fallback_color1', C.ORANGE_RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//3)
            pygame.draw.circle(self.image, config.get('fallback_color2', C.RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//4)
            self.frames = [self.image]
        else: # Successfully loaded frames
            self.dimensions = self.frames[0].get_size() # Update dimensions from actual GIF
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index]
        # Initial rect for _post_init_hook which might rotate frames
        self.rect = self.image.get_rect(center=(x, y))
        
        if direction_vector.length_squared() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: 
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed

        self._post_init_hook(self.vel) # This might change self.frames and self.image

        # Re-set rect and pos after potential rotation in post_init_hook
        self.image = self.frames[self.current_frame_index % len(self.frames)] # Ensure current_frame_index is valid
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
            base_image_for_anim = self.frames[self.current_frame_index]

            if not isinstance(self, BoltProjectile): 
                if self.vel.x < 0: 
                    self.image = pygame.transform.flip(base_image_for_anim, True, False)
                else:
                    self.image = base_image_for_anim 
            else: 
                self.image = base_image_for_anim # BoltProjectile handles its rotation in _post_init_hook


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
            # For blood shot, owner takes damage when firing, not on hit self.
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
                    # If it's a grey shot and the target can be petrified
                    if self.__class__.__name__ == "GreyProjectile" and hasattr(char, 'petrify') and not getattr(char, 'is_petrified', False):
                        char.petrify()
                        self.kill() # Grey shot disappears after petrifying
                        return # Skip normal damage if petrified

                    char.take_damage(self.damage) # Apply normal damage
                    
                    if self.effect_type == "freeze":
                        if hasattr(char, 'apply_freeze_effect'):
                            char.apply_freeze_effect()
                    elif self.effect_type == "aflame":
                        if isinstance(char, Enemy) and getattr(char, 'color_name', None) == 'green':
                            if hasattr(char, 'apply_aflame_effect'):
                                debug(f"Projectile with 'aflame' effect hit green Enemy {getattr(char, 'enemy_id', 'Unknown')}. Applying aflame effect.")
                                char.apply_aflame_effect()
                                
                    self.kill() # Projectile disappears after hitting and applying effects/damage
                    return 
        
    def get_network_data(self):
        image_flipped = False
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
            'image_flipped': image_flipped,
            'effect_type': self.effect_type 
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data:
             self.vel.x, self.vel.y = data['vel']
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type) 
        
        old_center = self.rect.center
        
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): 
            if not self.sprite_path: 
                proj_type_name_from_data = data.get('type')
                if proj_type_name_from_data:
                    path_const_name = f"{proj_type_name_from_data.upper()}_SPRITE_PATH" # e.g. FIREBALL_SPRITE_PATH
                    if hasattr(C, path_const_name):
                        self.sprite_path = getattr(C, path_const_name)
                
            if self.sprite_path:
                full_gif_path = resource_path(self.sprite_path)
                self.frames = load_gif_frames(full_gif_path)
                if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                    fallback_dims = self.dimensions if self.dimensions else (1,1)
                    self.frames = [pygame.Surface(fallback_dims, pygame.SRCALPHA)] 
                    self.frames[0].fill(C.MAGENTA) 
                else: 
                    self.dimensions = self.frames[0].get_size() 
                
                final_velocity_vector_for_hook = pygame.math.Vector2(data.get('vel', (1,0)))
                self._post_init_hook(final_velocity_vector_for_hook) 


        if not self.frames: 
            self.image = pygame.Surface((1,1)) 
            self.rect = self.image.get_rect(center=old_center)
            return

        self.current_frame_index = self.current_frame_index % len(self.frames)
        base_image = self.frames[self.current_frame_index]

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
        # Initial super().__init__ will load original frames
        super().__init__(x, y, direction_vector, owner_player, config)
        # _post_init_hook (called by super) will handle the rotation based on self.vel

    def _post_init_hook(self, final_velocity_vector):
        if not self.frames or not self.frames[0]: return 

        angle = 0
        # Determine rotation based on horizontal velocity component
        if final_velocity_vector.x > 0: # Shot right
            angle = 90 # Rotate 90 degrees left (counter-clockwise)
        elif final_velocity_vector.x < 0: # Shot left
            angle = -90 # Rotate 90 degrees right (clockwise)
        # If vel.x is 0 (e.g. shot straight up/down), no additional rotation based on L/R direction

        if angle != 0:
            rotated_frames = []
            for frame_idx, frame in enumerate(self.frames):
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    rotated_frames.append(pygame.transform.rotate(frame, angle))
                elif frame: 
                    rotated_frames.append(frame) 
            if rotated_frames:
                self.frames = rotated_frames
        
        # Set the initial image after potential rotation
        self.current_frame_index = 0 
        self.image = self.frames[self.current_frame_index]
        # The rect will be re-centered by the BaseProjectile's __init__ after this hook.

    def animate(self): 
        # Bolt's animation uses pre-rotated frames, so it doesn't need standard flipping.
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor'):
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index] # Image is already correctly rotated
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
            'effect_type': 'petrify' # Special effect type
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        self.custom_anim_speed_divisor = 1.0
########## END OF FILE: projectiles.py ##########