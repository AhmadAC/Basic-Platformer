########## START OF FILE: projectiles.py ##########

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
        
        full_gif_path = resource_path(self.sprite_path)
        self.frames = load_gif_frames(full_gif_path)
        
        if not self.frames or \
           (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): 
            print(f"Warning: Projectile GIF '{full_gif_path}' failed to load or is default placeholder. Using fallback.")
            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) 
            # Generic placeholder visual
            pygame.draw.circle(self.image, config.get('fallback_color1', C.ORANGE_RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//3)
            pygame.draw.circle(self.image, config.get('fallback_color2', C.RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//4)
            self.frames = [self.image]
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index]
        # Initial rect based on first frame, potentially before rotation for Bolt
        self.rect = self.image.get_rect(center=(x, y)) 
        
        # Calculate self.vel first, as it might be needed by _post_init_hook
        if direction_vector.length_squared() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: 
            # Fallback if aim vector is zero (e.g. no directional input)
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed

        # Handle specific projectile logic like rotation AFTER frames are loaded and self.vel is set
        self._post_init_hook(self.vel) # Pass the actual calculated velocity vector

        # Finalize rect and pos AFTER potential modifications (like rotation in _post_init_hook)
        self.rect = self.image.get_rect(center=(x,y))
        self.pos = pygame.math.Vector2(self.rect.center)
        
        self.spawn_time = pygame.time.get_ticks()
        self.last_anim_update = self.spawn_time
        # Generate a more specific projectile ID
        proj_type_name = self.__class__.__name__.lower()
        self.projectile_id = f"{proj_type_name}_{getattr(owner_player, 'player_id', 'unknown')}_{self.spawn_time}"

    def _post_init_hook(self, final_velocity_vector):
        """Hook for subclasses to perform actions after frames are loaded but before final rect/pos."""
        pass # Default does nothing

    def animate(self):
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index]
            # Flipping logic (can be overridden if rotation handles direction)
            if not isinstance(self, BoltProjectile): # Bolt handles its own orientation
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
            if char is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False): # Generalize self-damage constant name
                continue

            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                if can_damage_target:
                    char.take_damage(self.damage)
                    self.kill()
                    return 
        
    def get_network_data(self):
        image_flipped = self.vel.x < 0
        if isinstance(self, BoltProjectile): # Bolt might not need flipping if frames are pre-rotated based on direction
             image_flipped = False # Or specific logic for bolt if its sprite sheet is always one way

        return {
            'id': self.projectile_id,
            'type': self.__class__.__name__, # Send projectile type
            'pos': (self.pos.x, self.pos.y),
            'vel': (self.vel.x, self.vel.y), 
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index,
            'spawn_time': self.spawn_time,
            'image_flipped': image_flipped 
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data:
             self.vel.x, self.vel.y = data['vel']
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        
        old_center = self.rect.center
        
        # Ensure frames are loaded if this instance was created empty on client
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): # Check for dummy 1x1 surface
            if not self.sprite_path: # Try to get sprite_path from data if class name matches
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
                    self.frames = [pygame.Surface(self.dimensions or (1,1), pygame.SRCALPHA)] # Fallback to configured/dummy dimensions
                    self.frames[0].fill(C.MAGENTA) # Error color
                
                # Re-run post_init_hook if frames were just loaded (e.g., for Bolt rotation)
                # Determine direction_vector from velocity for the hook
                # Use the actual velocity for rotation determination
                final_velocity_vector_for_hook = pygame.math.Vector2(data.get('vel', (1,0)))
                self._post_init_hook(final_velocity_vector_for_hook)


        if not self.frames: # Still no frames?
            self.image = pygame.Surface((1,1)) # Minimal image
            self.rect = self.image.get_rect(center=old_center)
            return

        # Ensure current_frame_index is valid
        self.current_frame_index = self.current_frame_index % len(self.frames)
        base_image = self.frames[self.current_frame_index]

        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            self.image = pygame.transform.flip(base_image, True, False)
        else: # Bolt handles its own orientation in _post_init_hook
            self.image = base_image # For Bolt, image is already rotated frame
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
            'sprite_path': C.BOLT_SPRITE_PATH, 'dimensions': C.BOLT_DIMENSIONS, # Original dimensions
            'fallback_color1': (255,255,0,200), 'fallback_color2': C.YELLOW
        }
        # Initial call to BaseProjectile.__init__ will load frames.
        # Rotation happens in _post_init_hook.
        super().__init__(x, y, direction_vector, owner_player, config)

    def _post_init_hook(self, final_velocity_vector):
        # This hook is called by BaseProjectile after frames are loaded and self.vel is determined.
        # Bolt-specific rotation logic:
        if not self.frames: return
        angle = 0
        # final_velocity_vector is self.vel (the actual direction of movement)
        vx, vy = final_velocity_vector.x, final_velocity_vector.y

        # Determine dominant direction for rotation
        # Assuming the base GIF sprite (11x29) is oriented pointing UP.
        if abs(vy) > abs(vx): # Primarily vertical movement
            if vy < 0: # Moving UP (negative Y in Pygame)
                # User: "if the bolt is going vertically up it should be flipped vertially or rotated 180 degrees"
                # This means it should point DOWN visually when fired UP.
                angle = 180
            elif vy > 0: # Moving DOWN (positive Y in Pygame)
                # To make an UP-pointing sprite point DOWN.
                angle = 180 
            # If vy is 0 but abs(vy) > abs(vx) was true, it means vx is also 0.
            # This case is handled by how self.vel is initially set in BaseProjectile if direction_vector is (0,0) - defaults to horizontal.
        
        else: # Primarily horizontal movement (or perfectly diagonal, where x takes precedence for rotation)
            if vx > 0: # Moving RIGHT
                # Original sprite points UP. To make it point RIGHT, rotate -90 deg (clockwise).
                angle = -90
            elif vx < 0: # Moving LEFT
                # Original sprite points UP. To make it point LEFT, rotate 90 deg (counter-clockwise).
                angle = 90
            # If vx is 0 and it wasn't primarily vertical, means vy is also 0.
            # self.vel would have defaulted to horizontal, so one of the above vx conditions would have matched.
            
        if angle != 0:
            rotated_frames = []
            for frame in self.frames:
                rotated_frames.append(pygame.transform.rotate(frame, angle))
            self.frames = rotated_frames
        
        if self.frames: # This check is good practice
            self.current_frame_index = 0 
            self.image = self.frames[self.current_frame_index]
            # The player's self.rect will be updated in BaseProjectile.__init__ 
            # *after* this hook returns, using the potentially modified self.image.

    def animate(self): # Bolt might not flip based on vel.x if frames are pre-rotated
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index]
            # No flipping, as orientation is handled by initial rotation in _post_init_hook
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
            'fallback_color1': (150,200,255,200), 'fallback_color2': C.LIGHT_BLUE
        }
        super().__init__(x, y, direction_vector, owner_player, config)

########## END OF FILE: projectiles.py ##########