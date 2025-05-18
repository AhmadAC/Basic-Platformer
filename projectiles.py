# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc.
Handles projectile effects including setting targets aflame or frozen.
"""
# version 1.0.7 (Players can be set aflame/frozen by projectiles not their own)
import pygame
import os 
import math 
import constants as C
from assets import load_gif_frames, resource_path
from enemy import Enemy 
try:
    from logger import debug 
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
                self.image = base_image_for_anim 
            self.rect = self.image.get_rect(center=old_center)

    def update(self, dt_sec, platforms, characters_to_hit_group): 
        self.pos += self.vel * dt_sec * C.FPS 
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.animate()

        if pygame.time.get_ticks() - self.spawn_time > self.lifespan:
            self.kill(); return

        if pygame.sprite.spritecollideany(self, platforms):
            self.kill(); return

        hit_characters = pygame.sprite.spritecollide(self, characters_to_hit_group, False)
        for char in hit_characters:
            # --- Skip hitting self under certain conditions ---
            is_self_hit_allowed_fireball = getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False)
            is_fireball_and_self = self.__class__.__name__ == "Fireball" and char is self.owner_player
            is_bloodshot_and_self = self.__class__.__name__ == "BloodShot" and char is self.owner_player
            is_ice_shard_and_self = self.__class__.__name__ == "IceShard" and char is self.owner_player
            
            # Prevent immediate self-collision
            if char is self.owner_player and (pygame.time.get_ticks() - self.spawn_time < 100): 
                continue
            # Fireball self-hit logic
            if is_fireball_and_self and not is_self_hit_allowed_fireball:
                continue
            # Bloodshot and Iceshard don't hit self
            if is_bloodshot_and_self or is_ice_shard_and_self:
                continue
                
            # --- Damage and Effect Application ---
            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                # Prevent re-applying same status if already active
                if self.effect_type == "freeze" and getattr(char, 'is_frozen', False): can_damage_target = False 
                elif self.effect_type == "aflame" and getattr(char, 'is_aflame', False): can_damage_target = False 

                if can_damage_target:
                    if self.effect_type == 'petrify' and hasattr(char, 'petrify') and not getattr(char, 'is_petrified', False):
                        debug(f"Grey shot hit {type(char).__name__} {getattr(char, 'player_id', getattr(char, 'enemy_id', ''))}. Petrifying.")
                        char.petrify()
                        self.kill(); return 

                    if self.damage > 0 : # Apply direct damage if any
                        char.take_damage(self.damage) 
                    
                    # Apply status effects
                    if self.effect_type == "freeze":
                        if hasattr(char, 'apply_freeze_effect') and not getattr(char, 'is_frozen', False): # Check if not already frozen
                            char.apply_freeze_effect()
                    elif self.effect_type == "aflame":
                        if hasattr(char, 'apply_aflame_effect') and not getattr(char, 'is_aflame', False): # Check if not already aflame
                             # For enemies, specific color check (green) might be needed if that's still a rule
                            if isinstance(char, Enemy) and getattr(char, 'color_name', None) == 'green':
                                debug(f"Projectile with 'aflame' effect hit green Enemy {getattr(char, 'enemy_id', 'Unknown')}. Applying aflame.")
                                char.apply_aflame_effect()
                            elif 'Player' in char.__class__.__name__: # If it's a player
                                debug(f"Projectile with 'aflame' effect hit Player {getattr(char, 'player_id', 'Unknown')}. Applying aflame.")
                                char.apply_aflame_effect()
                                
                    self.kill(); return 
        
    def get_network_data(self):
        image_flipped = False 
        if not isinstance(self, BoltProjectile):
            image_flipped = self.vel.x < 0

        return {
            'id': self.projectile_id, 'type': self.__class__.__name__, 
            'pos': (self.pos.x, self.pos.y), 'vel': (self.vel.x, self.vel.y), 
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index, 'spawn_time': self.spawn_time,
            'image_flipped': image_flipped, 'effect_type': self.effect_type 
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data: self.vel.x, self.vel.y = data['vel'] 
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type) 
        
        old_center = self.rect.center
        
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): 
            if not self.sprite_path: 
                proj_type_name_from_data = data.get('type')
                if proj_type_name_from_data:
                    path_const_name = f"{proj_type_name_from_data.upper()}_SPRITE_PATH" 
                    if hasattr(C, path_const_name): self.sprite_path = getattr(C, path_const_name)
            if self.sprite_path:
                full_gif_path = resource_path(self.sprite_path)
                if hasattr(self, 'original_frames') and self.original_frames and \
                   not (len(self.original_frames) == 1 and self.original_frames[0].get_size() == (30,40) and self.original_frames[0].get_at((0,0)) == C.RED):
                    self.frames = [frame.copy() for frame in self.original_frames] 
                else:
                    self.frames = load_gif_frames(full_gif_path)
                    self.original_frames = [frame.copy() for frame in self.frames] 
                if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                    fallback_dims = self.dimensions if self.dimensions else (1,1)
                    self.frames = [pygame.Surface(fallback_dims, pygame.SRCALPHA)] 
                    self.frames[0].fill(C.MAGENTA) 
                else: self.dimensions = self.frames[0].get_size() 
                final_velocity_vector_for_hook = pygame.math.Vector2(data.get('vel', (self.vel.x, self.vel.y)))
                self._post_init_hook(final_velocity_vector_for_hook) 

        if not self.frames: 
            self.image = pygame.Surface((1,1)); self.rect = self.image.get_rect(center=old_center)
            return

        self.current_frame_index = self.current_frame_index % len(self.frames)
        base_image = self.frames[self.current_frame_index] 

        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            self.image = pygame.transform.flip(base_image, True, False)
        else: self.image = base_image 
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
        if not self.original_frames or not self.original_frames[0]: return 
        self.frames = [frame.copy() for frame in self.original_frames] 
        vx, vy = final_velocity_vector.x, final_velocity_vector.y
        transformed_frames = []
        if abs(vy) > abs(vx) * 1.5 and vy < 0: 
            debug(f"Bolt shot upwards (vx:{vx:.2f}, vy:{vy:.2f}). Applying vertical flip.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.flip(frame, False, True)) 
                elif frame: transformed_frames.append(frame)
        elif vx > 0: 
            debug(f"Bolt shot right (vx:{vx:.2f}, vy:{vy:.2f}). Rotating 90 deg left.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.rotate(frame, 90)) 
                elif frame: transformed_frames.append(frame)
        elif vx < 0: 
            debug(f"Bolt shot left (vx:{vx:.2f}, vy:{vy:.2f}). Rotating 90 deg right.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.rotate(frame, -90)) 
                elif frame: transformed_frames.append(frame)
        else: transformed_frames = self.frames 
        if transformed_frames: self.frames = transformed_frames
        self.current_frame_index = 0 
        if self.frames: self.image = self.frames[self.current_frame_index % len(self.frames)]
        else: 
            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA)
            self.image.fill(C.MAGENTA); self.frames = [self.image] 

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