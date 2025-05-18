# projectiles.py
# -*- coding: utf-8 -*-
"""
Defines projectile classes like Fireball, PoisonShot, etc.
Handles projectile effects including setting targets aflame or frozen.
"""
# version 1.0.7 (Players can be set aflame/frozen by projectiles not their own)
import pygame
import os # For os.path.join if needed (though resource_path handles most of it)
import math # For vector math if pygame.math.Vector2 is not sufficient
import constants as C
from assets import load_gif_frames, resource_path
from enemy import Enemy # For isinstance checks to apply effects correctly
from statue import Statue # Import Statue for collision checking

try:
    from logger import debug # Use your game's logger
except ImportError:
    def debug(msg): print(f"DEBUG_PROJ: {msg}") # Fallback print


class BaseProjectile(pygame.sprite.Sprite):
    def __init__(self, x, y, direction_vector, owner_player, config):
        super().__init__()
        self.owner_player = owner_player # The Player instance that fired this
        self.damage = config['damage']
        self.speed = config['speed']
        self.lifespan = config['lifespan'] # In milliseconds
        self.dimensions = config['dimensions'] # Tuple (width, height), mainly for fallback
        self.sprite_path = config['sprite_path'] # Relative path to GIF
        self.effect_type = config.get('effect_type', None) # e.g., "aflame", "freeze", "petrify"
        
        # Load animation frames
        full_gif_path = resource_path(self.sprite_path)
        self.frames = load_gif_frames(full_gif_path)
        
        # Fallback if GIF loading fails
        if not self.frames or \
           (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): 
            debug(f"Warning: Projectile GIF '{full_gif_path}' failed to load or is default placeholder. Using fallback.")
            # If frames were loaded but are the error placeholder, try to get dimensions from original config
            # If frames were loaded but invalid, self.dimensions might be from the placeholder
            if self.frames and not (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED):
                self.dimensions = self.frames[0].get_size() # Use dimensions of the loaded (but bad) frame

            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA).convert_alpha()
            self.image.fill((0,0,0,0)) # Transparent fallback
            # Simple visual fallback (e.g., colored circle)
            pygame.draw.circle(self.image, config.get('fallback_color1', C.ORANGE_RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//3)
            pygame.draw.circle(self.image, config.get('fallback_color2', C.RED), (self.dimensions[0]//2, self.dimensions[1]//2), self.dimensions[0]//4)
            self.frames = [self.image] # Use the single fallback frame
        else: # Frames loaded successfully
            self.dimensions = self.frames[0].get_size() # Update dimensions based on loaded GIF
        
        self.current_frame_index = 0
        self.image = self.frames[self.current_frame_index] # Set initial image
        self.rect = self.image.get_rect(center=(x, y))
        
        # Set velocity based on direction vector
        if direction_vector.length_squared() > 0:
            self.vel = direction_vector.normalize() * self.speed
        else: # Fallback if direction is zero (should not happen ideally)
            self.vel = pygame.math.Vector2(1 if owner_player.facing_right else -1, 0) * self.speed

        # Store original frames for transformations (like rotation in Bolt)
        self.original_frames = [frame.copy() for frame in self.frames] # Deep copy
        self._post_init_hook(self.vel) # For class-specific transformations like Bolt rotation

        # After potential transformation by _post_init_hook, re-set image and rect
        self.image = self.frames[self.current_frame_index % len(self.frames)] # Ensure index is valid
        self.rect = self.image.get_rect(center=(x,y)) # Re-center based on new image
        self.pos = pygame.math.Vector2(self.rect.center) # Position for precise movement
        
        # Timing and ID
        self.spawn_time = pygame.time.get_ticks()
        self.last_anim_update = self.spawn_time
        proj_type_name = self.__class__.__name__.lower()
        # Create a unique ID for network synchronization
        self.projectile_id = f"{proj_type_name}_{getattr(owner_player, 'player_id', 'unknown')}_{self.spawn_time}"

    def _post_init_hook(self, final_velocity_vector):
        """
        Optional hook for subclasses to perform actions after initial setup,
        like rotating sprites based on velocity (e.g., BoltProjectile).
        """
        pass # Base class does nothing here

    def animate(self):
        """Handles frame cycling for animated projectiles."""
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 # Default animation speed for projectiles
        if hasattr(self, 'custom_anim_speed_divisor'): # Allow subclasses to override
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if now - self.last_anim_update > anim_duration:
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center # Preserve center for consistent positioning
            
            base_image_for_anim = self.frames[self.current_frame_index] # Get the current frame

            # Handle flipping for non-Bolt projectiles (Bolt handles its own rotation)
            if not isinstance(self, BoltProjectile): # Bolts are rotated, not flipped
                if self.vel.x < 0: # If moving left
                    self.image = pygame.transform.flip(base_image_for_anim, True, False)
                else:
                    self.image = base_image_for_anim # Moving right or vertically, no flip needed
            else: # For Bolt or other rotation-handled projectiles
                self.image = base_image_for_anim 
            
            self.rect = self.image.get_rect(center=old_center) # Re-apply rect with new image

    def update(self, dt_sec, platforms, characters_to_hit_group): 
        """
        Updates projectile position, animation, and checks for collisions.
        dt_sec is delta time (not directly used if movement is frame-based, but good practice to pass).
        """
        # Movement based on velocity (scaled by FPS for consistent speed)
        self.pos += self.vel * dt_sec * C.FPS # dt_sec * FPS effectively cancels out, giving per-frame movement
        self.rect.center = round(self.pos.x), round(self.pos.y)
        
        self.animate() # Update animation frame

        # Lifespan check
        if pygame.time.get_ticks() - self.spawn_time > self.lifespan:
            self.kill(); return

        # Collision with platforms
        if pygame.sprite.spritecollideany(self, platforms):
            self.kill(); return

        # Collision with characters (Enemies, other Players, Statues)
        hit_characters = pygame.sprite.spritecollide(self, characters_to_hit_group, False)
        for char in hit_characters:
            # --- Skip hitting self under certain conditions ---
            is_self_hit_allowed_fireball = getattr(C, "ALLOW_SELF_FIREBALL_DAMAGE", False)
            is_fireball_and_self = self.__class__.__name__ == "Fireball" and char is self.owner_player
            is_bloodshot_and_self = self.__class__.__name__ == "BloodShot" and char is self.owner_player
            is_ice_shard_and_self = self.__class__.__name__ == "IceShard" and char is self.owner_player
            
            # Prevent immediate self-collision (e.g., if spawned inside owner)
            if char is self.owner_player and (pygame.time.get_ticks() - self.spawn_time < 100): # 100ms grace period
                continue
            # Fireball self-hit logic (controlled by constant)
            if is_fireball_and_self and not is_self_hit_allowed_fireball:
                continue
            # Bloodshot and Iceshard generally don't hit their owner
            if is_bloodshot_and_self or is_ice_shard_and_self:
                continue
                
            # --- Damage and Effect Application ---
            if hasattr(char, 'take_damage') and callable(char.take_damage):
                can_damage_target = True
                # Check if target is invulnerable (e.g., in hit cooldown)
                if hasattr(char, 'is_taking_hit') and hasattr(char, 'hit_timer') and hasattr(char, 'hit_cooldown'):
                    now = pygame.time.get_ticks()
                    if char.is_taking_hit and (now - char.hit_timer < char.hit_cooldown):
                        can_damage_target = False
                
                # Prevent re-applying same status if already active and not a damage-over-time effect
                # This simple check might need refinement for stacking effects or DoTs.
                if self.effect_type == "freeze" and getattr(char, 'is_frozen', False): can_damage_target = False 
                elif self.effect_type == "aflame" and getattr(char, 'is_aflame', False): can_damage_target = False 

                if can_damage_target:
                    target_type_name = type(char).__name__
                    target_id_log = getattr(char, 'player_id', getattr(char, 'enemy_id', getattr(char, 'statue_id', 'UnknownTarget')))

                    # Specific logic for GREY projectile (petrify)
                    if self.effect_type == 'petrify':
                        if isinstance(char, Statue): # Grey projectile hitting an already stone statue
                            debug(f"Grey shot hit a Statue object {target_id_log}. No effect (already stone). Projectile continues or dies.")
                            # Optionally, self.kill() here if it should dissipate on hitting existing statues.
                            # If it should pass through, do nothing here or break to allow multiple hits if desired.
                            continue # Skip further damage/effect processing for this statue
                        elif hasattr(char, 'petrify') and not getattr(char, 'is_petrified', False):
                            debug(f"Grey shot hit {target_type_name} {target_id_log}. Petrifying.")
                            char.petrify()
                            self.kill(); return # Petrify effect applied, projectile is consumed

                    # Apply direct damage if projectile has damage value
                    if self.damage > 0 : 
                        debug(f"{self.__class__.__name__} (Owner: P{self.owner_player.player_id}) hit {target_type_name} {target_id_log} for {self.damage} DMG.")
                        char.take_damage(self.damage) 
                    
                    # Apply status effects (Freeze, Aflame)
                    if self.effect_type == "freeze":
                        if hasattr(char, 'apply_freeze_effect') and not getattr(char, 'is_frozen', False): # Check if not already frozen
                            debug(f"{self.__class__.__name__} applying freeze to {target_type_name} {target_id_log}.")
                            char.apply_freeze_effect()
                    elif self.effect_type == "aflame":
                        if hasattr(char, 'apply_aflame_effect') and not getattr(char, 'is_aflame', False): # Check if not already aflame
                            # Special condition for green enemies (if that's still a rule)
                            if isinstance(char, Enemy) and getattr(char, 'color_name', None) == 'green':
                                debug(f"{self.__class__.__name__} with 'aflame' effect hit green Enemy {target_id_log}. Applying aflame.")
                                char.apply_aflame_effect()
                            elif 'Player' in target_type_name or isinstance(char, Enemy): # If it's a player or any other enemy type
                                debug(f"{self.__class__.__name__} with 'aflame' effect hit {target_type_name} {target_id_log}. Applying aflame.")
                                char.apply_aflame_effect()
                                
                    self.kill(); return # Projectile is consumed after hitting a valid target and applying effects/damage
        
    def get_network_data(self):
        """Gathers projectile data for network transmission."""
        image_flipped = False # Default for non-Bolt projectiles
        if not isinstance(self, BoltProjectile): # Bolts handle rotation, not simple flipping
            image_flipped = self.vel.x < 0

        return {
            'id': self.projectile_id, 
            'type': self.__class__.__name__, # Class name to recreate on client
            'pos': (self.pos.x, self.pos.y), 
            'vel': (self.vel.x, self.vel.y), # Send velocity for client-side prediction if used
            'owner_id': self.owner_player.player_id if self.owner_player else None,
            'frame': self.current_frame_index, 
            'spawn_time': self.spawn_time, # For client-side lifespan calculation
            'image_flipped': image_flipped, # For client-side rendering
            'effect_type': self.effect_type # So client can potentially show special effects
        }

    def set_network_data(self, data):
        """Applies received network data to update the local projectile instance."""
        self.pos.x, self.pos.y = data['pos']
        if 'vel' in data: # Velocity sync might be optional if client does full prediction
            self.vel.x, self.vel.y = data['vel'] 
        
        self.rect.center = round(self.pos.x), round(self.pos.y) # Update rect based on new pos
        self.current_frame_index = data.get('frame', self.current_frame_index)
        self.effect_type = data.get('effect_type', self.effect_type) # Sync effect type
        
        # If frames were not loaded correctly initially (e.g., on client due to missing assets),
        # try to reload them based on type if sprite_path is missing.
        old_center = self.rect.center
        
        if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (1,1)): # Placeholder check
            if not self.sprite_path: # Attempt to re-derive sprite_path if missing
                proj_type_name_from_data = data.get('type')
                if proj_type_name_from_data:
                    # Construct constant name, e.g., "FIREBALL_SPRITE_PATH"
                    path_const_name = f"{proj_type_name_from_data.upper()}_SPRITE_PATH" 
                    if hasattr(C, path_const_name):
                        self.sprite_path = getattr(C, path_const_name)
            
            if self.sprite_path: # If sprite_path is now available
                full_gif_path = resource_path(self.sprite_path)
                # Prefer original_frames if they exist and are valid (to preserve transformations)
                if hasattr(self, 'original_frames') and self.original_frames and \
                   not (len(self.original_frames) == 1 and self.original_frames[0].get_size() == (30,40) and self.original_frames[0].get_at((0,0)) == C.RED):
                    self.frames = [frame.copy() for frame in self.original_frames] # Restore from original
                else: # Otherwise, load fresh
                    self.frames = load_gif_frames(full_gif_path)
                    self.original_frames = [frame.copy() for frame in self.frames] # Store newly loaded as original
                
                if not self.frames or (len(self.frames) == 1 and self.frames[0].get_size() == (30,40) and self.frames[0].get_at((0,0)) == C.RED): # Still failed
                    fallback_dims = self.dimensions if self.dimensions else (1,1) # Use stored or tiny default
                    self.frames = [pygame.Surface(fallback_dims, pygame.SRCALPHA)] # Single transparent frame
                    self.frames[0].fill(C.MAGENTA) # Error color
                else: # Successfully loaded or reloaded
                    self.dimensions = self.frames[0].get_size() # Update dimensions
                
                # Re-apply post_init_hook for rotation if applicable (e.g., Bolt)
                final_velocity_vector_for_hook = pygame.math.Vector2(data.get('vel', (self.vel.x, self.vel.y)))
                self._post_init_hook(final_velocity_vector_for_hook) 

        # Ensure frames list is not empty before trying to access it
        if not self.frames: # Absolute fallback if still no frames
            self.image = pygame.Surface((1,1)); self.rect = self.image.get_rect(center=old_center)
            return

        # Set current image based on (potentially reloaded) frames and synced index/flip
        self.current_frame_index = self.current_frame_index % len(self.frames) # Ensure valid index
        base_image = self.frames[self.current_frame_index] # Get the correct frame

        # Apply flip for non-Bolt projectiles
        if not isinstance(self, BoltProjectile) and data.get('image_flipped', False):
            self.image = pygame.transform.flip(base_image, True, False)
        else: # For Bolt (rotated) or non-flipped projectiles
            self.image = base_image 
        
        self.rect = self.image.get_rect(center=old_center) # Update rect with new image and preserved center


# --- Specific Projectile Classes ---

class Fireball(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.FIREBALL_DAMAGE, 'speed': C.FIREBALL_SPEED, 'lifespan': C.FIREBALL_LIFESPAN,
            'sprite_path': C.FIREBALL_SPRITE_PATH, 'dimensions': C.FIREBALL_DIMENSIONS,
            'fallback_color1': (255,120,0,200), 'fallback_color2': C.RED, # RGBA for fallback
            'effect_type': "aflame" # This projectile applies the 'aflame' effect
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        # Fireball specific properties can be added here if needed

class PoisonShot(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.POISON_DAMAGE, 'speed': C.POISON_SPEED, 'lifespan': C.POISON_LIFESPAN,
            'sprite_path': C.POISON_SPRITE_PATH, 'dimensions': C.POISON_DIMENSIONS,
            'fallback_color1': (0,150,0,200), 'fallback_color2': C.DARK_GREEN
            # 'effect_type': "poison" # If you add a poison status effect
        }
        super().__init__(x, y, direction_vector, owner_player, config)

class BoltProjectile(BaseProjectile):
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.BOLT_DAMAGE, 'speed': C.BOLT_SPEED, 'lifespan': C.BOLT_LIFESPAN,
            'sprite_path': C.BOLT_SPRITE_PATH, 'dimensions': C.BOLT_DIMENSIONS, # Original dimensions before rotation
            'fallback_color1': (255,255,0,200), 'fallback_color2': C.YELLOW
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        # Bolt rotation is handled by _post_init_hook called by BaseProjectile constructor

    def _post_init_hook(self, final_velocity_vector):
        """Rotates the bolt sprites based on the final velocity vector."""
        if not self.original_frames or not self.original_frames[0]: # Check if original frames are valid
            debug("BoltProjectile: No original frames to rotate in _post_init_hook.")
            return 
        
        self.frames = [frame.copy() for frame in self.original_frames] # Work with copies of original for rotation
        
        vx, vy = final_velocity_vector.x, final_velocity_vector.y
        transformed_frames = []

        # Determine rotation based on velocity vector
        # Prioritize vertical if moving mostly up/down, otherwise horizontal
        if abs(vy) > abs(vx) * 1.5 and vy < 0: # Moving mostly upwards
            debug(f"Bolt shot upwards (vx:{vx:.2f}, vy:{vy:.2f}). Applying vertical flip (or no rotation if sprite is already up).")
            # If your bolt sprite is designed to point right by default, rotating -90 (or 270) would make it point up.
            # If it's designed to point up, flip may not be needed or use rotate(0)
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    # Assuming original bolt points right: rotate -90 deg for up
                    transformed_frames.append(pygame.transform.rotate(frame, 90)) 
                elif frame: transformed_frames.append(frame) # Add original if transform fails
        elif vx > 0: # Moving right (or mostly right)
            debug(f"Bolt shot right (vx:{vx:.2f}, vy:{vy:.2f}). No rotation needed (sprite defaults right).")
            transformed_frames = self.frames # No rotation needed if sprite already points right
        elif vx < 0: # Moving left (or mostly left)
            debug(f"Bolt shot left (vx:{vx:.2f}, vy:{vy:.2f}). Rotating 180 deg.")
            for frame in self.frames:
                if frame and frame.get_width() > 0 and frame.get_height() > 0:
                    transformed_frames.append(pygame.transform.rotate(frame, 180)) # Flip 180 deg for left
                elif frame: transformed_frames.append(frame)
        else: # Default case (e.g., if vy is dominant but positive, or vx is zero and vy is not strongly up)
              # Could be straight down, or a shallow angle. Default to original orientation.
            transformed_frames = self.frames 
            
        if transformed_frames:
            self.frames = transformed_frames
        
        # Update current image and rect based on new frames
        self.current_frame_index = 0 # Reset frame index after transformation
        if self.frames:
            self.image = self.frames[self.current_frame_index % len(self.frames)]
            # Re-center rect because rotation can change dimensions
            old_center = self.rect.center if hasattr(self, 'rect') else self.pos
            self.rect = self.image.get_rect(center=old_center)
            self.dimensions = self.image.get_size() # Update dimensions
        else: # Should not happen if original_frames was valid
            self.image = pygame.Surface(self.dimensions, pygame.SRCALPHA); self.image.fill(C.MAGENTA)
            self.frames = [self.image] 


    def animate(self): # Bolt animation might be simpler if it's not a multi-frame GIF after rotation
        """Handles frame cycling for animated projectiles. Bolt might just be static after rotation."""
        now = pygame.time.get_ticks()
        anim_duration = C.ANIM_FRAME_DURATION / 1.5 
        if hasattr(self, 'custom_anim_speed_divisor'):
            anim_duration = C.ANIM_FRAME_DURATION / self.custom_anim_speed_divisor

        if len(self.frames) > 1 and (now - self.last_anim_update > anim_duration): # Only animate if multiple frames
            self.last_anim_update = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            old_center = self.rect.center
            self.image = self.frames[self.current_frame_index] # Bolt frames are already rotated
            self.rect = self.image.get_rect(center=old_center)
        elif len(self.frames) == 1: # If only one frame (e.g., after rotation or if static GIF)
            self.image = self.frames[0] # Ensure it's set, no animation needed
            # Rect should already be correct from init or _post_init_hook

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
            'effect_type': "freeze" # This projectile applies the 'freeze' effect
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
            'effect_type': None # No special status effect by default
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        self.custom_anim_speed_divisor = 1.2 # Example: make shadow projectile animate slightly faster

class GreyProjectile(BaseProjectile): 
    def __init__(self, x, y, direction_vector, owner_player):
        config = {
            'damage': C.GREY_PROJECTILE_DAMAGE, # Usually 0, as it petrifies
            'speed': C.GREY_PROJECTILE_SPEED, 
            'lifespan': C.GREY_PROJECTILE_LIFESPAN,
            'sprite_path': C.GREY_PROJECTILE_SPRITE_PATH, 
            'dimensions': C.GREY_PROJECTILE_DIMENSIONS, 
            'fallback_color1': (100,100,100,200), 'fallback_color2': C.DARK_GRAY,
            'effect_type': 'petrify' # Applies petrification
        }
        super().__init__(x, y, direction_vector, owner_player, config)
        self.custom_anim_speed_divisor = 1.0 # Normal animation speed