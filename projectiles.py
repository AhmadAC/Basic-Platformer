# projectiles.py
# -*- coding: utf-8 -*-
"""
1.00000.1
Defines projectile classes like Fireball.
"""
import pygame
import os # For path joining
import constants as C
from assets import load_gif_frames, resource_path

class Fireball(pygame.sprite.Sprite):
    def __init__(self, x, y, direction_vector, owner_player):
        super().__init__()
        self.owner_player = owner_player
        self.damage = C.FIREBALL_DAMAGE
        self.speed = C.FIREBALL_SPEED

        # Load animation
        # The user's provided path is absolute. For portability, ensure it's relative from project root.
        # C.FIREBALL_SPRITE_PATH should be "characters/weapons/fire.gif"
        # And the actual file should be in project_root/characters/weapons/fire.gif
        full_gif_path = resource_path(C.FIREBALL_SPRITE_PATH)
        self.frames = load_gif_frames(full_gif_path)
        
        if not self.frames or \
           (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): # Check for assets.py placeholder
            print(f"Warning: Fireball GIF '{full_gif_path}' failed to load or is default placeholder. Using fallback.")
            self.image = pygame.Surface(C.FIREBALL_DIMENSIONS, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) # Transparent
            pygame.draw.circle(self.image, (255, 120, 0, 200), (C.FIREBALL_DIMENSIONS[0]//2, C.FIREBALL_DIMENSIONS[1]//2), C.FIREBALL_DIMENSIONS[0]//3)
            pygame.draw.circle(self.image, C.RED, (C.FIREBALL_DIMENSIONS[0]//2, C.FIREBALL_DIMENSIONS[1]//2), C.FIREBALL_DIMENSIONS[0]//4)
            self.frames = [self.image]
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index]
        self.rect = self.image.get_rect(center=(x, y))
        self.pos = pygame.math.Vector2(self.rect.center) # Use float position for accuracy

        if direction_vector.length_sq() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: # Fallback if direction is zero (e.g., player was static, no prior input)
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed
        
        self.spawn_time = pygame.time.get_ticks()
        self.last_anim_update = self.spawn_time
        self.projectile_id = f"fb_{getattr(owner_player, 'player_id', 'unknown')}_{self.spawn_time}"

    def animate(self):
        now = pygame.time.get_ticks()
        # Use a slightly faster animation for fireballs perhaps, or keep C.ANIM_FRAME_DURATION
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 # Example: 1.5x faster animation
        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index]
            # Flip image based on horizontal velocity if desired (fireball might always face forward)
            if self.vel.x < 0: # If moving left, flip it. Assumes base GIF faces right.
                 self.image = pygame.transform.flip(self.frames[self.current_frame_index], True, False)
            else:
                 self.image = self.frames[self.current_frame_index]
            self.rect = self.image.get_rect(center=old_center)

    def update(self, dt_sec, platforms, characters_to_hit_group): # dt_sec is passed by sprite group update
        # Note: Player movement seems to be self.pos += self.vel (vel is px/frame)
        # For consistency, fireball will also use vel as px/frame and ignore dt_sec for position.
        self.pos += self.vel 
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.animate()

        # Check lifespan
        if pygame.time.get_ticks() - self.spawn_time > C.FIREBALL_LIFESPAN:
            self.kill()
            return

        # Collision with platforms (walls)
        if pygame.sprite.spritecollideany(self, platforms):
            self.kill()
            # TODO: Add explosion/dissipation animation here if desired
            return

        # Collision with characters (enemies or other players)
        hit_characters = pygame.sprite.spritecollide(self, characters_to_hit_group, False)
        for char in hit_characters:
            # Ensure fireball doesn't hit its owner immediately or other specific conditions
            if char is self.owner_player and (pygame.time.get_ticks() - self.spawn_time < 100): # brief self-immunity
                continue
            if char is self.owner_player and not getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False): # Configurable self-damage
                continue

            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                # Check target's invincibility frames
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                if can_damage_target:
                    char.take_damage(self.damage)
                    self.kill()
                    # TODO: Add explosion/dissipation animation here
                    return # Fireball disappears after hitting one target
        
        # Optional: Off-screen check (more robust would be vs camera view + margin)
        # For now, this is a simple check against a large area around origin.
        # A better check would involve level_pixel_width/height from main.py
        # if not (-200 < self.rect.centerx < C.LEVEL_WIDTH_PLACEHOLDER + 200 or \
        #    -200 < self.rect.centery < C.LEVEL_HEIGHT_PLACEHOLDER + 200):
        #    self.kill()


    def get_network_data(self):
        return {
            'id': self.projectile_id,
            'pos': (self.pos.x, self.pos.y),
            'vel': (self.vel.x, self.vel.y), # For server authoritative movement
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index,
            'spawn_time': self.spawn_time,
            'image_flipped': self.vel.x < 0 # if you flip image based on vel
        }

    def set_network_data(self, data):
        self.pos.x, self.pos.y = data['pos']
        # If server sends velocity, client can use it. Otherwise, client might not need to update vel.
        if 'vel' in data:
             self.vel.x, self.vel.y = data['vel']
        self.rect.center = round(self.pos.x), round(self.pos.y)
        self.current_frame_index = data.get('frame', self.current_frame_index)
        # Animation sync can be complex. spawn_time helps.
        # Image flipping based on network data
        old_center = self.rect.center
        base_image = self.frames[self.current_frame_index]
        if data.get('image_flipped', False):
            self.image = pygame.transform.flip(base_image, True, False)
        else:
            self.image = base_image
        self.rect = self.image.get_rect(center=old_center)