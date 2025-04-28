
# -*- coding: utf-8 -*-
"""
Defines the Enemy class (CPU player clone).
Handles AI-driven movement, animations mirroring player, states, and interactions.
Each instance randomly selects a color variant for its animations.
"""
import pygame
import random
import math
import os # Needed for path joining

# Import necessary components
import constants as C # Use constants with C. prefix
from assets import load_all_player_animations # Reuse player animation loader
from tiles import Lava # Import Lava for type checking in hazard collision

class Enemy(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y, patrol_area=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area

        # --- Define available character color folders ---
        # Assumes these folders are inside a 'characters' sub-directory
        # relative to where main.py is run.
        character_base_folder = 'characters'
        available_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow']
        if not available_colors:
             print("ERROR: No enemy colors defined in Enemy.__init__!")
             available_colors = ['player1'] # Fallback to player1 folder if colors list is empty
             character_base_folder = '.' # Adjust base path if falling back

        # --- Randomly choose a color/folder ---
        chosen_color = random.choice(available_colors)
        self.color_name = chosen_color # Store for debugging/info
        chosen_folder_path = os.path.join(character_base_folder, chosen_color)

        print(f"Initializing Enemy instance with color: {chosen_color} (Path: {chosen_folder_path})") # Debug print

        # --- Load Animations using the chosen folder ---
        self.animations = load_all_player_animations(asset_folder=chosen_folder_path)
        if self.animations is None: # Check if loading failed critically (e.g., missing idle)
            print(f"CRITICAL Enemy Init Error: Failed loading animations from {chosen_folder_path}. Check path and idle animation.")
            # Create minimal placeholder to avoid crashing game init entirely
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False
            self.is_dead = True # Mark as inactive
            return # Stop further initialization
        else:
             self._valid_init = True


        # --- Mirror Player State Flags & Physics Vars (Same as before) ---
        self._last_facing = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks()
        # Ensure initial image uses loaded animation, handle potential missing keys gracefully
        initial_anim = self.animations.get('idle')
        if not initial_anim: # If idle somehow failed despite earlier check, find *any* anim
             print(f"Warning: Idle animation missing for {chosen_color} enemy, using first available.")
             first_key = next(iter(self.animations), None)
             initial_anim = self.animations.get(first_key) if first_key else None
        # Set initial image from the found animation list
        self.image = initial_anim[0] if initial_anim else pygame.Surface((30, 40)).convert_alpha() # Fallback surface
        if not initial_anim: self.image.fill(C.BLUE) # Color fallback surface

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y); self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = random.choice([True, False]); self.on_ground = False
        # Flags not used by enemy AI
        self.on_ladder = False; self.can_grab_ladder = False; self.touching_wall = 0
        self.is_crouching = False; self.is_dashing = False; self.is_rolling = False
        self.is_sliding = False; self.can_wall_jump = False; self.wall_climb_timer = 0
        # Flags used by enemy
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.is_taking_hit = False; self.hit_timer = 0; self.hit_duration = 300 # Stun duration
        self.hit_cooldown = 500 # Invincibility time after hit
        self.is_dead = False; self.state_timer = 0
        # Health
        self.max_health = C.ENEMY_MAX_HEALTH; self.current_health = self.max_health
        # AI Specific
        self.ai_state = 'patrolling'; self.patrol_target_x = start_x
        self.set_new_patrol_target()
        # Attack Hitbox
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35)
        # Standard height (for health bar positioning relative to 'head')
        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError): # Added TypeError safety
            print(f"Warning Enemy ({self.color_name}): Could not get idle anim height, using default.")
            self.standard_height = 60


    def set_new_patrol_target(self):
        """Sets a new patrol target coordinate."""
        if self.patrol_area and isinstance(self.patrol_area, pygame.Rect):
             # Ensure patrol target is reachable within bounds
             min_x = self.patrol_area.left + self.rect.width / 2
             max_x = self.patrol_area.right - self.rect.width / 2
             if min_x < max_x: # Check if range is valid
                 self.patrol_target_x = random.uniform(min_x, max_x)
             else: # Fallback if area is too small
                 self.patrol_target_x = self.patrol_area.centerx
        else:
            # Simple wander
            direction = 1 if random.random() > 0.5 else -1
            self.patrol_target_x = self.pos.x + direction * C.ENEMY_PATROL_DIST


    def set_state(self, new_state):
        if not self._valid_init: return
        anim_state = new_state
        # Map logical states to available animations
        valid_anim_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall']
        if new_state not in valid_anim_states:
            if new_state in ['chasing', 'patrolling']: anim_state = 'run' if abs(self.vel.x) > 0.1 else 'idle'
            elif 'attack' in new_state: anim_state = new_state # Allow variants like attack_nm
            else: anim_state = 'idle' # Default fallback

        # Check if anim_state exists and has frames in the loaded dictionary
        if anim_state not in self.animations or not self.animations[anim_state]:
             print(f"Warning Enemy ({self.color_name}): Animation for state '{anim_state}' missing/empty. Falling back to idle.")
             anim_state = 'idle'
             # If idle itself is missing/empty, it's a critical issue caught earlier, but double-check
             if 'idle' not in self.animations or not self.animations['idle']:
                 print(f"CRITICAL ERROR Enemy ({self.color_name}): Cannot find valid idle animation.")
                 return # Cannot proceed

        # Only change state if it's actually different
        if self.state != new_state and not self.is_dead:
            self._last_state_for_debug = new_state
            # Reset flags based on the *logical* state
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False # Reset unless entering hit state

            self.state = new_state # Store logical state
            self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks(); self.state_timer = pygame.time.get_ticks()

            # State entry logic
            if 'attack' in new_state:
                self.is_attacking = True; self.attack_type = 1; self.attack_timer = self.state_timer
                anim = self.animations.get(anim_state) # Get animation list
                self.attack_duration = len(anim) * C.ANIM_FRAME_DURATION if anim else 400
                self.vel.x = 0 # Stop moving during attack
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.5; self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3
                 self.is_attacking = False # Cancel current attack
            elif new_state == 'death': # Covers death and death_nm logical states
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc = pygame.math.Vector2(0, 0); self.current_health = 0

            self.animate() # Update visual immediately after state change
        elif not self.is_dead:
             self._last_state_for_debug = self.state # Update debug tracker even if state is same


    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        now = pygame.time.get_ticks()

        # Determine animation key based on current logical state and physics
        state_key = self.state
        if self.state == 'patrolling' or self.state == 'chasing':
             state_key = 'run' if abs(self.vel.x) > 0.5 else 'idle'
        elif self.is_attacking: state_key = 'attack_nm' if 'attack_nm' in self.animations and self.animations['attack_nm'] else 'attack' # Prefer non-moving if available
        elif self.is_taking_hit: state_key = 'hit' # Use hit state directly if taking hit
        elif self.is_dead: state_key = 'death_nm' if abs(self.vel.x) < 0.5 and 'death_nm' in self.animations and self.animations['death_nm'] else 'death'
        elif not self.on_ground: state_key = 'fall' if 'fall' in self.animations and self.animations['fall'] else 'idle' # Use fall if airborne and available
        else: state_key = 'idle' # Default to idle if on ground and no other state

        # Final check and fallback for state_key
        if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        animation = self.animations.get(state_key) # Use the final state_key
        # If idle somehow failed, this would be caught in __init__, but safety check
        if not animation:
             if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
             return # Cannot animate

        # Advance Frame
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1)
            # Animation End Handling
            if self.current_frame >= len(animation):
                if self.state == 'hit': # Logical state check
                    # Flag is reset in update, just transition state after anim
                    self.set_state('idle')
                    # Return because set_state calls animate again
                    return
                # Attack end handled in ai_update
                elif self.is_dead: self.current_frame = len(animation) - 1 # Hold death frame
                else: self.current_frame = 0 # Loop other animations (idle, run, fall)
            # Safety reset for index
            if self.current_frame >= len(animation): self.current_frame = 0

        # Update Image and Rect
        # Ensure frame index is valid before accessing animation list
        if not animation or self.current_frame < 0 or self.current_frame >= len(animation):
            self.current_frame = 0 # Reset frame index if invalid
            if not animation: # Cannot proceed if animation is still invalid
                 if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
                 return

        new_image = animation[self.current_frame]
        current_facing_is_right = self.facing_right
        if not current_facing_is_right: new_image = pygame.transform.flip(new_image, True, False)
        if self.image is not new_image or self._last_facing != current_facing_is_right:
            old_midbottom = self.rect.midbottom
            self.image = new_image
            self.rect = self.image.get_rect(midbottom=old_midbottom) # Re-anchor rect
            self._last_facing = current_facing_is_right


    def ai_update(self, player):
        """Determines AI actions and sets acceleration/state intentions."""
        now = pygame.time.get_ticks()
        # Prevent AI if dead or in hit stun cooldown
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            self.acc.x = 0
            return

        dist_to_player = math.hypot(player.pos.x - self.pos.x, player.pos.y - self.pos.y)
        can_attack_now = now - self.attack_cooldown_timer > C.ENEMY_ATTACK_COOLDOWN
        y_diff = abs(player.rect.centery - self.rect.centery)
        # Check line of sight (basic: is player relatively close vertically?)
        line_of_sight = y_diff < self.rect.height * 2.0
        player_in_range = dist_to_player < C.ENEMY_ATTACK_RANGE and line_of_sight and not player.is_dead
        player_detected = dist_to_player < C.ENEMY_DETECTION_RANGE and line_of_sight and not player.is_dead

        # Handle Attack Completion (start cooldown)
        if self.is_attacking and now - self.attack_timer > self.attack_duration:
             self.is_attacking = False; self.attack_type = 0
             self.attack_cooldown_timer = now
             self.set_state('idle') # Transition back to idle
             return # Prevent other actions this frame

        # Don't change state/acc if attack animation is playing
        if self.is_attacking:
            self.acc.x = 0; return

        # AI Decision Logic
        target_acc_x = 0; target_facing_right = self.facing_right

        if player_in_range and can_attack_now:
            self.ai_state = 'attacking' # Set AI intention
            target_facing_right = (player.pos.x > self.pos.x) # Face player
            self.facing_right = target_facing_right # Turn immediately
            self.set_state('attack_nm' if 'attack_nm' in self.animations else 'attack') # Set logical state
            return # Commit to attack
        elif player_detected:
            self.ai_state = 'chasing'
            target_facing_right = (player.pos.x > self.pos.x)
            target_acc_x = C.ENEMY_ACCEL * (1 if target_facing_right else -1)
            if self.state != 'chasing': self.set_state('chasing') # Update logical state
        else: # Patrol
            self.ai_state = 'patrolling'
            if self.state != 'patrolling': self.set_state('patrolling')
            # Move towards patrol target
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right = (self.patrol_target_x > self.pos.x)
            # Patrol slightly slower
            target_acc_x = C.ENEMY_ACCEL * 0.7 * (1 if target_facing_right else -1)

        # Apply AI Intentions
        self.acc.x = target_acc_x
        # Turn if needed (and not attacking)
        if not self.is_attacking and self.facing_right != target_facing_right:
             self.facing_right = target_facing_right


    def update(self, dt, player, platforms, hazards):
        """ Main update method: AI, physics, collisions, interactions. """
        if not self._valid_init or self.is_dead:
            if self.is_dead: self.animate() # Keep animating death even if not updating physics
            return

        now = pygame.time.get_ticks()
        # Reset hit flag after cooldown expires (allows taking damage again)
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False

        self.ai_update(player) # Determine AI intentions (acc.x, state)

        # --- Physics Calculation ---
        if not self.is_dead: self.vel.y += C.PLAYER_GRAVITY # Apply gravity
        self.vel.x += self.acc.x # Apply horizontal acceleration from AI
        # Apply friction
        current_friction = 0
        if self.on_ground and self.acc.x == 0: current_friction = C.ENEMY_FRICTION
        if current_friction != 0:
             friction_force = self.vel.x * current_friction
             if abs(self.vel.x) > 0.1: self.vel.x += friction_force
             else: self.vel.x = 0 # Stop completely if slow
        # Apply speed limit
        self.vel.x = max(-C.ENEMY_RUN_SPEED_LIMIT, min(C.ENEMY_RUN_SPEED_LIMIT, self.vel.x))
        # Apply terminal velocity
        self.vel.y = min(self.vel.y, 18)

        # --- Collision Detection & Position Update ---
        self.on_ground = False # Assume not on ground until collision check

        # Move X, Check Platforms, Check Player
        self.pos.x += self.vel.x
        self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        collided_x_player = self.check_character_collision('x', player)

        # Move Y, Check Platforms, Check Player
        self.pos.y += self.vel.y
        self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        # Only check Y char collision if no X collision occurred to prevent corner snagging
        if not collided_x_player:
            self.check_character_collision('y', player)

        # Final pos update based on rect adjustments during collision checks
        self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom

        # --- Post-Movement Checks ---
        self.check_attack_collisions(player) # Check if enemy attack hits player
        self.check_hazard_collisions(hazards) # Check if enemy touches lava

        self.animate() # Update animation based on final state and velocity


    def check_platform_collisions(self, direction, platforms):
        """ Resolves collisions with solid platforms. """
        collided_sprites = pygame.sprite.spritecollide(self, platforms, False)
        for plat in collided_sprites:
            if direction == 'x':
                # Resolve horizontal collision
                if self.vel.x > 0: self.rect.right = plat.rect.left
                elif self.vel.x < 0: self.rect.left = plat.rect.right
                self.vel.x = 0 # Stop horizontal movement
                # If patrolling, hitting a wall should trigger finding a new target
                if self.ai_state == 'patrolling': self.set_new_patrol_target()
            elif direction == 'y':
                # Resolve vertical collision
                if self.vel.y > 0: # Moving Down
                    # Check if enemy was above platform before moving
                    previous_bottom = self.pos.y - self.vel.y
                    if previous_bottom <= plat.rect.top + 1: # +1 tolerance
                         self.rect.bottom = plat.rect.top; self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0: # Moving Up
                    # Check if enemy was below platform before moving
                    previous_top = (self.pos.y - self.rect.height) - self.vel.y
                    if previous_top >= plat.rect.bottom - 1: # -1 tolerance
                         self.rect.top = plat.rect.bottom; self.vel.y = 0


    def check_character_collision(self, direction, player):
        """ Checks for collision with the player sprite and applies bounce. Returns True if collision occurred. """
        if not self._valid_init or self.is_dead or player.is_dead: return False

        collision_occurred = False
        if self.rect.colliderect(player.rect):
            collision_occurred = True

            if direction == 'x':
                push_dir = 0 # Direction enemy should be pushed
                # Determine push based on relative position
                if self.rect.centerx < player.rect.centerx: # Enemy is to the left
                    self.rect.right = player.rect.left
                    push_dir = -1 # Enemy pushed left
                else: # Enemy is to the right
                    self.rect.left = player.rect.right
                    push_dir = 1 # Enemy pushed right

                # Apply bounce velocity to enemy
                self.vel.x = push_dir * C.CHARACTER_BOUNCE_VELOCITY
                # Apply opposite bounce velocity to player
                if hasattr(player, 'vel'):
                    player.vel.x = -push_dir * C.CHARACTER_BOUNCE_VELOCITY
                    # Nudge player rect slightly away to prevent immediate re-collision
                    player.rect.x += -push_dir * 2 # Increased nudge

                self.pos.x = self.rect.centerx # Update enemy internal pos

            elif direction == 'y':
                 # Vertical collision: Enemy lands on player or hits head
                 if self.vel.y > 0 and self.rect.bottom > player.rect.top: # Moving Down onto Player
                    self.rect.bottom = player.rect.top
                    self.on_ground = True # Landed on player
                    self.vel.y = 0
                 elif self.vel.y < 0 and self.rect.top < player.rect.bottom: # Moving Up into Player
                    self.rect.top = player.rect.bottom
                    self.vel.y = 0
                 self.pos.y = self.rect.bottom # Update enemy internal pos

        return collision_occurred


    def check_hazard_collisions(self, hazards):
        """ Checks for collisions with hazards like Lava using feet check. """
        now = pygame.time.get_ticks()
        # Prevent hazard damage if recently hit
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
             return

        collided_hazards = pygame.sprite.spritecollide(self, hazards, False)
        damaged_this_frame = False
        for hazard in collided_hazards:
            # Check if the center-bottom point is inside the hazard rect
            check_point = (self.rect.centerx, self.rect.bottom - 1)
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point) and not damaged_this_frame:
                # print(f"DEBUG: Enemy collided Lava point check. E: {self.rect.bottom} vs L: {hazard.rect.top}-{hazard.rect.bottom}")
                self.take_damage(C.LAVA_DAMAGE)
                damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3 # Small bounce
                     push_dir = 1 if self.rect.centerx < hazard.rect.centerx else -1
                     self.vel.x = -push_dir * 4 # Push away
                     self.on_ground = False # Ensure airborne after bounce
                break # Apply damage only once per frame


    def check_attack_collisions(self, player):
        """ Checks if the enemy's attack hitbox collides with the player. """
        if not self._valid_init or not self.is_attacking or self.is_dead or player.is_dead: return

        # Check if player is invincible
        now = pygame.time.get_ticks()
        if player.is_taking_hit and now - player.hit_timer < player.hit_cooldown: return

        # Position hitbox
        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery
        # Check collision
        if self.attack_hitbox.colliderect(player.rect):
            if hasattr(player, 'take_damage') and callable(player.take_damage):
                player.take_damage(C.ENEMY_ATTACK_DAMAGE)


    def take_damage(self, amount):
        """ Reduces enemy health and handles hit/death states. Includes cooldown. """
        now = pygame.time.get_ticks()
        # Check cooldown: Prevent taking damage if within hit_cooldown period
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            return

        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        # print(f"Enemy ({self.color_name}) took {amount} damage, health: {self.current_health}") # Debug

        if self.current_health <= 0:
            if not self.is_dead: self.set_state('death')
        else:
            # Set hit state only if not already in hit animation phase
             if not (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
                self.set_state('hit') # Sets is_taking_hit=True and hit_timer=now


    def reset(self):
        """ Resets the enemy to its initial state and position. """
        if not self._valid_init: return
        self.pos = self.spawn_pos.copy()
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY) # Reset gravity
        self.current_health = self.max_health
        self.is_dead = False; self.is_taking_hit = False; self.is_attacking = False
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.facing_right = random.choice([True, False])
        self.on_ground = False # Will be determined next update
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.set_state('idle') # Reset logical state
        self.ai_state = 'patrolling' # Reset AI state
        self.set_new_patrol_target() # Get initial patrol target again

# -*- coding: utf-8 -*-
"""
Defines the Enemy class (CPU player clone).
Handles AI-driven movement, animations mirroring player, states, and interactions.
Each instance randomly selects a color variant for its animations.
"""
import pygame
import random
import math
import os # Needed for path joining

# Import necessary components
import constants as C # Use constants with C. prefix
from assets import load_all_player_animations # Reuse player animation loader
from tiles import Lava # Import Lava for type checking in hazard collision

class Enemy(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y, patrol_area=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area

        # --- Define available character color folders ---
        # Assumes these folders are inside a 'characters' sub-directory
        # relative to where main.py is run.
        character_base_folder = 'characters'
        available_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow']
        if not available_colors:
             print("ERROR: No enemy colors defined in Enemy.__init__!")
             available_colors = ['player1'] # Fallback to player1 folder if colors list is empty
             character_base_folder = '.' # Adjust base path if falling back

        # --- Randomly choose a color/folder ---
        chosen_color = random.choice(available_colors)
        self.color_name = chosen_color # Store for debugging/info
        chosen_folder_path = os.path.join(character_base_folder, chosen_color)

        print(f"Initializing Enemy instance with color: {chosen_color} (Path: {chosen_folder_path})") # Debug print

        # --- Load Animations using the chosen folder ---
        self.animations = load_all_player_animations(asset_folder=chosen_folder_path)
        if self.animations is None: # Check if loading failed critically (e.g., missing idle)
            print(f"CRITICAL Enemy Init Error: Failed loading animations from {chosen_folder_path}. Check path and idle animation.")
            # Create minimal placeholder to avoid crashing game init entirely
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False
            self.is_dead = True # Mark as inactive
            return # Stop further initialization
        else:
             self._valid_init = True


        # --- Mirror Player State Flags & Physics Vars (Same as before) ---
        self._last_facing = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks()
        # Ensure initial image uses loaded animation, handle potential missing keys gracefully
        initial_anim = self.animations.get('idle')
        if not initial_anim: # If idle somehow failed despite earlier check, find *any* anim
             print(f"Warning: Idle animation missing for {chosen_color} enemy, using first available.")
             first_key = next(iter(self.animations), None)
             initial_anim = self.animations.get(first_key) if first_key else None
        # Set initial image from the found animation list
        self.image = initial_anim[0] if initial_anim else pygame.Surface((30, 40)).convert_alpha() # Fallback surface
        if not initial_anim: self.image.fill(C.BLUE) # Color fallback surface

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y); self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = random.choice([True, False]); self.on_ground = False
        # Flags not used by enemy AI
        self.on_ladder = False; self.can_grab_ladder = False; self.touching_wall = 0
        self.is_crouching = False; self.is_dashing = False; self.is_rolling = False
        self.is_sliding = False; self.can_wall_jump = False; self.wall_climb_timer = 0
        # Flags used by enemy
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.is_taking_hit = False; self.hit_timer = 0; self.hit_duration = 300 # Stun duration
        self.hit_cooldown = 500 # Invincibility time after hit
        self.is_dead = False; self.state_timer = 0
        # Health
        self.max_health = C.ENEMY_MAX_HEALTH; self.current_health = self.max_health
        # AI Specific
        self.ai_state = 'patrolling'; self.patrol_target_x = start_x
        self.set_new_patrol_target()
        # Attack Hitbox
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35)
        # Standard height (for health bar positioning relative to 'head')
        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError): # Added TypeError safety
            print(f"Warning Enemy ({self.color_name}): Could not get idle anim height, using default.")
            self.standard_height = 60


    def set_new_patrol_target(self):
        """Sets a new patrol target coordinate."""
        if self.patrol_area and isinstance(self.patrol_area, pygame.Rect):
             # Ensure patrol target is reachable within bounds
             min_x = self.patrol_area.left + self.rect.width / 2
             max_x = self.patrol_area.right - self.rect.width / 2
             if min_x < max_x: # Check if range is valid
                 self.patrol_target_x = random.uniform(min_x, max_x)
             else: # Fallback if area is too small
                 self.patrol_target_x = self.patrol_area.centerx
        else:
            # Simple wander
            direction = 1 if random.random() > 0.5 else -1
            self.patrol_target_x = self.pos.x + direction * C.ENEMY_PATROL_DIST


    def set_state(self, new_state):
        if not self._valid_init: return
        anim_state = new_state
        # Map logical states to available animations
        valid_anim_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall']
        if new_state not in valid_anim_states:
            if new_state in ['chasing', 'patrolling']: anim_state = 'run' if abs(self.vel.x) > 0.1 else 'idle'
            elif 'attack' in new_state: anim_state = new_state # Allow variants like attack_nm
            else: anim_state = 'idle' # Default fallback

        # Check if anim_state exists and has frames in the loaded dictionary
        if anim_state not in self.animations or not self.animations[anim_state]:
             print(f"Warning Enemy ({self.color_name}): Animation for state '{anim_state}' missing/empty. Falling back to idle.")
             anim_state = 'idle'
             # If idle itself is missing/empty, it's a critical issue caught earlier, but double-check
             if 'idle' not in self.animations or not self.animations['idle']:
                 print(f"CRITICAL ERROR Enemy ({self.color_name}): Cannot find valid idle animation.")
                 return # Cannot proceed

        # Only change state if it's actually different
        if self.state != new_state and not self.is_dead:
            self._last_state_for_debug = new_state
            # Reset flags based on the *logical* state
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False # Reset unless entering hit state

            self.state = new_state # Store logical state
            self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks(); self.state_timer = pygame.time.get_ticks()

            # State entry logic
            if 'attack' in new_state:
                self.is_attacking = True; self.attack_type = 1; self.attack_timer = self.state_timer
                anim = self.animations.get(anim_state) # Get animation list
                self.attack_duration = len(anim) * C.ANIM_FRAME_DURATION if anim else 400
                self.vel.x = 0 # Stop moving during attack
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.5; self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3
                 self.is_attacking = False # Cancel current attack
            elif new_state == 'death': # Covers death and death_nm logical states
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc = pygame.math.Vector2(0, 0); self.current_health = 0

            self.animate() # Update visual immediately after state change
        elif not self.is_dead:
             self._last_state_for_debug = self.state # Update debug tracker even if state is same


    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        now = pygame.time.get_ticks()

        # Determine animation key based on current logical state and physics
        state_key = self.state
        if self.state == 'patrolling' or self.state == 'chasing':
             state_key = 'run' if abs(self.vel.x) > 0.5 else 'idle'
        elif self.is_attacking: state_key = 'attack_nm' if 'attack_nm' in self.animations and self.animations['attack_nm'] else 'attack' # Prefer non-moving if available
        elif self.is_taking_hit: state_key = 'hit' # Use hit state directly if taking hit
        elif self.is_dead: state_key = 'death_nm' if abs(self.vel.x) < 0.5 and 'death_nm' in self.animations and self.animations['death_nm'] else 'death'
        elif not self.on_ground: state_key = 'fall' if 'fall' in self.animations and self.animations['fall'] else 'idle' # Use fall if airborne and available
        else: state_key = 'idle' # Default to idle if on ground and no other state

        # Final check and fallback for state_key
        if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        animation = self.animations.get(state_key) # Use the final state_key
        # If idle somehow failed, this would be caught in __init__, but safety check
        if not animation:
             if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
             return # Cannot animate

        # Advance Frame
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1)
            # Animation End Handling
            if self.current_frame >= len(animation):
                if self.state == 'hit': # Logical state check
                    # Flag is reset in update, just transition state after anim
                    self.set_state('idle')
                    # Return because set_state calls animate again
                    return
                # Attack end handled in ai_update
                elif self.is_dead: self.current_frame = len(animation) - 1 # Hold death frame
                else: self.current_frame = 0 # Loop other animations (idle, run, fall)
            # Safety reset for index
            if self.current_frame >= len(animation): self.current_frame = 0

        # Update Image and Rect
        # Ensure frame index is valid before accessing animation list
        if not animation or self.current_frame < 0 or self.current_frame >= len(animation):
            self.current_frame = 0 # Reset frame index if invalid
            if not animation: # Cannot proceed if animation is still invalid
                 if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
                 return

        new_image = animation[self.current_frame]
        current_facing_is_right = self.facing_right
        if not current_facing_is_right: new_image = pygame.transform.flip(new_image, True, False)
        if self.image is not new_image or self._last_facing != current_facing_is_right:
            old_midbottom = self.rect.midbottom
            self.image = new_image
            self.rect = self.image.get_rect(midbottom=old_midbottom) # Re-anchor rect
            self._last_facing = current_facing_is_right


    def ai_update(self, player):
        """Determines AI actions and sets acceleration/state intentions."""
        now = pygame.time.get_ticks()
        # Prevent AI if dead or in hit stun cooldown
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            self.acc.x = 0
            return

        dist_to_player = math.hypot(player.pos.x - self.pos.x, player.pos.y - self.pos.y)
        can_attack_now = now - self.attack_cooldown_timer > C.ENEMY_ATTACK_COOLDOWN
        y_diff = abs(player.rect.centery - self.rect.centery)
        # Check line of sight (basic: is player relatively close vertically?)
        line_of_sight = y_diff < self.rect.height * 2.0
        player_in_range = dist_to_player < C.ENEMY_ATTACK_RANGE and line_of_sight and not player.is_dead
        player_detected = dist_to_player < C.ENEMY_DETECTION_RANGE and line_of_sight and not player.is_dead

        # Handle Attack Completion (start cooldown)
        if self.is_attacking and now - self.attack_timer > self.attack_duration:
             self.is_attacking = False; self.attack_type = 0
             self.attack_cooldown_timer = now
             self.set_state('idle') # Transition back to idle
             return # Prevent other actions this frame

        # Don't change state/acc if attack animation is playing
        if self.is_attacking:
            self.acc.x = 0; return

        # AI Decision Logic
        target_acc_x = 0; target_facing_right = self.facing_right

        if player_in_range and can_attack_now:
            self.ai_state = 'attacking' # Set AI intention
            target_facing_right = (player.pos.x > self.pos.x) # Face player
            self.facing_right = target_facing_right # Turn immediately
            self.set_state('attack_nm' if 'attack_nm' in self.animations else 'attack') # Set logical state
            return # Commit to attack
        elif player_detected:
            self.ai_state = 'chasing'
            target_facing_right = (player.pos.x > self.pos.x)
            target_acc_x = C.ENEMY_ACCEL * (1 if target_facing_right else -1)
            if self.state != 'chasing': self.set_state('chasing') # Update logical state
        else: # Patrol
            self.ai_state = 'patrolling'
            if self.state != 'patrolling': self.set_state('patrolling')
            # Move towards patrol target
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right = (self.patrol_target_x > self.pos.x)
            # Patrol slightly slower
            target_acc_x = C.ENEMY_ACCEL * 0.7 * (1 if target_facing_right else -1)

        # Apply AI Intentions
        self.acc.x = target_acc_x
        # Turn if needed (and not attacking)
        if not self.is_attacking and self.facing_right != target_facing_right:
             self.facing_right = target_facing_right


    def update(self, dt, player, platforms, hazards):
        """ Main update method: AI, physics, collisions, interactions. """
        if not self._valid_init or self.is_dead:
            if self.is_dead: self.animate() # Keep animating death even if not updating physics
            return

        now = pygame.time.get_ticks()
        # Reset hit flag after cooldown expires (allows taking damage again)
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False

        self.ai_update(player) # Determine AI intentions (acc.x, state)

        # --- Physics Calculation ---
        if not self.is_dead: self.vel.y += C.PLAYER_GRAVITY # Apply gravity
        self.vel.x += self.acc.x # Apply horizontal acceleration from AI
        # Apply friction
        current_friction = 0
        if self.on_ground and self.acc.x == 0: current_friction = C.ENEMY_FRICTION
        if current_friction != 0:
             friction_force = self.vel.x * current_friction
             if abs(self.vel.x) > 0.1: self.vel.x += friction_force
             else: self.vel.x = 0 # Stop completely if slow
        # Apply speed limit
        self.vel.x = max(-C.ENEMY_RUN_SPEED_LIMIT, min(C.ENEMY_RUN_SPEED_LIMIT, self.vel.x))
        # Apply terminal velocity
        self.vel.y = min(self.vel.y, 18)

        # --- Collision Detection & Position Update ---
        self.on_ground = False # Assume not on ground until collision check

        # Move X, Check Platforms, Check Player
        self.pos.x += self.vel.x
        self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        collided_x_player = self.check_character_collision('x', player)

        # Move Y, Check Platforms, Check Player
        self.pos.y += self.vel.y
        self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        # Only check Y char collision if no X collision occurred to prevent corner snagging
        if not collided_x_player:
            self.check_character_collision('y', player)

        # Final pos update based on rect adjustments during collision checks
        self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom

        # --- Post-Movement Checks ---
        self.check_attack_collisions(player) # Check if enemy attack hits player
        self.check_hazard_collisions(hazards) # Check if enemy touches lava

        self.animate() # Update animation based on final state and velocity


    def check_platform_collisions(self, direction, platforms):
        """ Resolves collisions with solid platforms. """
        collided_sprites = pygame.sprite.spritecollide(self, platforms, False)
        for plat in collided_sprites:
            if direction == 'x':
                # Resolve horizontal collision
                if self.vel.x > 0: self.rect.right = plat.rect.left
                elif self.vel.x < 0: self.rect.left = plat.rect.right
                self.vel.x = 0 # Stop horizontal movement
                # If patrolling, hitting a wall should trigger finding a new target
                if self.ai_state == 'patrolling': self.set_new_patrol_target()
            elif direction == 'y':
                # Resolve vertical collision
                if self.vel.y > 0: # Moving Down
                    # Check if enemy was above platform before moving
                    previous_bottom = self.pos.y - self.vel.y
                    if previous_bottom <= plat.rect.top + 1: # +1 tolerance
                         self.rect.bottom = plat.rect.top; self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0: # Moving Up
                    # Check if enemy was below platform before moving
                    previous_top = (self.pos.y - self.rect.height) - self.vel.y
                    if previous_top >= plat.rect.bottom - 1: # -1 tolerance
                         self.rect.top = plat.rect.bottom; self.vel.y = 0


    def check_character_collision(self, direction, player):
        """ Checks for collision with the player sprite and applies bounce. Returns True if collision occurred. """
        if not self._valid_init or self.is_dead or player.is_dead: return False

        collision_occurred = False
        if self.rect.colliderect(player.rect):
            collision_occurred = True

            if direction == 'x':
                push_dir = 0 # Direction enemy should be pushed
                # Determine push based on relative position
                if self.rect.centerx < player.rect.centerx: # Enemy is to the left
                    self.rect.right = player.rect.left
                    push_dir = -1 # Enemy pushed left
                else: # Enemy is to the right
                    self.rect.left = player.rect.right
                    push_dir = 1 # Enemy pushed right

                # Apply bounce velocity to enemy
                self.vel.x = push_dir * C.CHARACTER_BOUNCE_VELOCITY
                # Apply opposite bounce velocity to player
                if hasattr(player, 'vel'):
                    player.vel.x = -push_dir * C.CHARACTER_BOUNCE_VELOCITY
                    # Nudge player rect slightly away to prevent immediate re-collision
                    player.rect.x += -push_dir * 2 # Increased nudge

                self.pos.x = self.rect.centerx # Update enemy internal pos

            elif direction == 'y':
                 # Vertical collision: Enemy lands on player or hits head
                 if self.vel.y > 0 and self.rect.bottom > player.rect.top: # Moving Down onto Player
                    self.rect.bottom = player.rect.top
                    self.on_ground = True # Landed on player
                    self.vel.y = 0
                 elif self.vel.y < 0 and self.rect.top < player.rect.bottom: # Moving Up into Player
                    self.rect.top = player.rect.bottom
                    self.vel.y = 0
                 self.pos.y = self.rect.bottom # Update enemy internal pos

        return collision_occurred


    def check_hazard_collisions(self, hazards):
        """ Checks for collisions with hazards like Lava using feet check. """
        now = pygame.time.get_ticks()
        # Prevent hazard damage if recently hit
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
             return

        collided_hazards = pygame.sprite.spritecollide(self, hazards, False)
        damaged_this_frame = False
        for hazard in collided_hazards:
            # Check if the center-bottom point is inside the hazard rect
            check_point = (self.rect.centerx, self.rect.bottom - 1)
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point) and not damaged_this_frame:
                # print(f"DEBUG: Enemy collided Lava point check. E: {self.rect.bottom} vs L: {hazard.rect.top}-{hazard.rect.bottom}")
                self.take_damage(C.LAVA_DAMAGE)
                damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3 # Small bounce
                     push_dir = 1 if self.rect.centerx < hazard.rect.centerx else -1
                     self.vel.x = -push_dir * 4 # Push away
                     self.on_ground = False # Ensure airborne after bounce
                break # Apply damage only once per frame


    def check_attack_collisions(self, player):
        """ Checks if the enemy's attack hitbox collides with the player. """
        if not self._valid_init or not self.is_attacking or self.is_dead or player.is_dead: return

        # Check if player is invincible
        now = pygame.time.get_ticks()
        if player.is_taking_hit and now - player.hit_timer < player.hit_cooldown: return

        # Position hitbox
        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery
        # Check collision
        if self.attack_hitbox.colliderect(player.rect):
            if hasattr(player, 'take_damage') and callable(player.take_damage):
                player.take_damage(C.ENEMY_ATTACK_DAMAGE)


    def take_damage(self, amount):
        """ Reduces enemy health and handles hit/death states. Includes cooldown. """
        now = pygame.time.get_ticks()
        # Check cooldown: Prevent taking damage if within hit_cooldown period
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            return

        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        # print(f"Enemy ({self.color_name}) took {amount} damage, health: {self.current_health}") # Debug

        if self.current_health <= 0:
            if not self.is_dead: self.set_state('death')
        else:
            # Set hit state only if not already in hit animation phase
             if not (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
                self.set_state('hit') # Sets is_taking_hit=True and hit_timer=now


    def reset(self):
        """ Resets the enemy to its initial state and position. """
        if not self._valid_init: return
        self.pos = self.spawn_pos.copy()
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY) # Reset gravity
        self.current_health = self.max_health
        self.is_dead = False; self.is_taking_hit = False; self.is_attacking = False
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.facing_right = random.choice([True, False])
        self.on_ground = False # Will be determined next update
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.set_state('idle') # Reset logical state
        self.ai_state = 'patrolling' # Reset AI state
        self.set_new_patrol_target() # Get initial patrol target again
        # print(f"Enemy ({self.color_name}) reset to {self.pos}") # Optional debug