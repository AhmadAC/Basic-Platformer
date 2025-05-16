# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball.
"""
# version 1.0.1 (fixed length_sq typo in init)
import pygame
import os # For path joining
import math # For math.atan2 and math.degrees if more complex rotation is needed
import constants as C
from assets import load_gif_frames, resource_path

class BaseProjectile(pygame.sprite.Sprite):
    def __init__(self, x, y, direction_vector, owner_player, config):
        super().__init__()
        self.owner_player = owner_player
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan']
        self.dimensions = config['dimensions']
        self.sprite_path = config['sprite_path']
        self.effect_type = config.get('effect_type', None) # Added for special effects
        
        full_gif_path = resource_path(self.sprite_path)
        self.frames = load_gif_frames(full_gif_path)
        
        if not self.frames or \
           (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): 
            print(f"Warning: Projectile GIF '{full_gif_path}' failed to load or is default placeholder. Using fallback.")
            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) 
            pygame.draw.circle(self.image, config.get('fallback_color1', C.ORANGE_RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//3)
            pygame.draw.circle(self.image, config.get('fallback_color2', C.RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//4)
            self.frames = [self.image]
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index]
        self.rect = self.image.get_rect(center=(x, y)) 
        
        if direction_vector.length_squared() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: 
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed

        self._post_init_hook(self.vel) 

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
        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index]
            if not isinstance(self, BoltProjectile): 
                if self.vel.x < 0: 
                    self.image = pygame.transform.flip(self.frames[self.current_frame_index], True, False)
            self.rect = self.image.get_rect(center=old_center)

    def update(self, dt_sec, platforms, characters_to_hit_group): 
        self.pos += self.vel 
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
            if char is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False): 
                continue

            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                if hasattr(char, 'is_frozen') and char.is_frozen and self.effect_type == "freeze": # Don't re-freeze already frozen
                    can_damage_target = False # Or, allow damage but not re-freeze effect

                if can_damage_target:
                    char.take_damage(self.damage)
                    
                    if self.effect_type == "freeze":
                        if hasattr(char, 'apply_freeze_effect'):
                            char.apply_freeze_effect()
                            
                    self.kill()
                    return 
        
    def get_network_data(self):
        image_flipped = self.vel.x < 0
        if isinstance(self, BoltProjectile): 
             image_flipped = False 

        return {
            'id': self.projectile_id,
            'type': self.__class__.__name__, 
            'pos': (self.pos.x, self.pos.y),
            'vel': (self.vel.x, self.vel.y), 
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index,
            'spawn_time': self.spawn_time,
            'image_flipped': image_flipped,
            'effect_type': self.effect_type # Send effect type
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data:
             self.vel.x, self.vel.y = data['vel']
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type) # Sync effect type
        
        old_center = self.rect.center
        
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): 
            if not self.sprite_path: 
                proj_type = data.get('type')
                if proj_type == "Fireball": self.sprite_path = C.FIREBALL_SPRITE_PATH
                elif proj_type == "PoisonShot": self.sprite_path = C.POISON_SPRITE_PATH
                elif proj_type == "BoltProjectile": self.sprite_path = C.BOLT_SPRITE_PATH
                elif proj_type == "BloodShot": self.sprite_path = C.BLOOD_SPRITE_PATH
                elif proj_type == "IceShard": self.sprite_path = C.ICE_SPRITE_PATH
                
            if self.sprite_path:
                full_gif_path = resource_path(self.sprite_path)
                self.frames = load_gif_frames(full_gif_path)
                if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                    self.frames = [pygame.Surface(self.dimensions or (1,1), pygame.SRCALPHA)] 
                    self.frames[0].fill(C.MAGENTA) 
                
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
            'fallback_color1': (255,120,0,200), 'fallback_color2': C.RED
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
        if not self.frames: return
        angle = 0
        vx, vy = final_velocity_vector.x, final_velocity_vector.y
        if abs(vy) > abs(vx): 
            if vy < 0: angle = 180
            elif vy > 0: angle = 180 
        else: 
            if vx > 0: angle = -90
            elif vx < 0: angle = 90
            
        if angle != 0:
            rotated_frames = []
            for frame in self.frames:
                rotated_frames.append(pygame.transform.rotate(frame, angle))
            self.frames = rotated_frames
        
        if self.frames: 
            self.current_frame_index = 0 
            self.image = self.frames[self.current_frame_index]

    def animate(self): 
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
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
            'effect_type': "freeze" # Add the effect type
        }
        super().__init__(x, y, direction_vector, owner_player, config)