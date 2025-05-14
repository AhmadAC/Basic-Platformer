########## START OF FILE: player.py ##########

# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.1 (Added stomp functionality)
Defines the Player class, handling core attributes, physics, animation,
and state transitions. Delegates input, combat, and network handling
to respective handler modules for improved organization.
"""
import pygame
import os # Not strictly needed here if assets.py handles all pathing
import sys # Not strictly needed here
import math
# import time # Only if PrintLimiter was defined directly in this file

from utils import PrintLimiter # Use the shared PrintLimiter from utils.py
import constants as C # Game constants
from assets import load_all_player_animations # For loading player sprites
from tiles import Lava # For type checking in hazard collision
from enemy import Enemy # For type checking in stomp

# Import handler modules that contain functions operating on the Player instance
from player_input_handler import process_player_input_logic
from player_combat_handler import (fire_player_fireball, check_player_attack_collisions, 
                                   player_take_damage, player_self_inflict_damage, player_heal_to_full)
from player_network_handler import (get_player_network_data, set_player_network_data, 
                                    handle_player_network_input, get_player_input_state_for_network)


class Player(pygame.sprite.Sprite):
    """
    Represents a player character in the game.
    Manages player's state, animation, physics, and interactions.
    Delegates complex input, combat, and network logic to specialized handlers.
    """
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0) # Class-level limiter for player messages

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True # Flag to indicate if initialization was successful
        print(f"DEBUG Player (init P{self.player_id}): Initializing at ({start_x}, {start_y})") # DEBUG

        # --- Determine Asset Folder based on Player ID ---
        if self.player_id == 1: asset_folder_path = 'characters/player1'
        elif self.player_id == 2: asset_folder_path = 'characters/player2'
        else: # Fallback for any other player_id
            asset_folder_path = 'characters/player1' # Default to player1 assets
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info ({self.player_id}): Unrecognized ID. Defaulting to player1 assets from '{asset_folder_path}'.")
        
        print(f"DEBUG Player (init P{self.player_id}): Asset folder path: '{asset_folder_path}'") # DEBUG
        # --- Load Animations ---
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder_path)
        if self.animations is None: # Critical failure if essential animations (like idle) are missing
            print(f"CRITICAL Player Init Error ({self.player_id}): Failed to load critical animations from '{asset_folder_path}'. Player will be invalid.")
            # Create a minimal placeholder image for error representation
            self.image = pygame.Surface((30, 40)).convert_alpha()
            self.image.fill(C.RED) # Red indicates error
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.is_dead = True; self._valid_init = False # Mark as invalid and stop further initialization
            print(f"DEBUG Player (init P{self.player_id}): Animation load FAILED. _valid_init set to False.") # DEBUG
            return

        print(f"DEBUG Player (init P{self.player_id}): Animations loaded. Number of animation states: {len(self.animations)}") # DEBUG
        if 'idle' not in self.animations or not self.animations['idle']: # DEBUG
            print(f"DEBUG Player (init P{self.player_id}): CRITICAL - 'idle' animation missing after load_all_player_animations returned non-None.") # DEBUG


        # --- Initialize Core Attributes ---
        # Standard height (from idle animation, used for some calculations)
        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError): # Handle if 'idle' animation is missing or empty
            self.standard_height = 60 # Fallback height
            if Player.print_limiter.can_print(f"player_init_idle_height_warning_{self.player_id}"):
                print(f"Player Warning ({self.player_id}): Could not get idle animation height, using default {self.standard_height}.")

        # Animation and State Variables
        self._last_facing_right = True # Tracks last facing direction for image flipping (True for right)
        self._last_state_for_debug = "init" # For debugging state transitions
        self.state = 'idle'      # Current logical state of the player
        self.current_frame = 0   # Index of the current animation frame
        self.last_anim_update = pygame.time.get_ticks() # Timestamp of last animation frame update

        # Set initial image (first frame of idle animation)
        idle_animation_frames = self.animations.get('idle')
        if idle_animation_frames and len(idle_animation_frames) > 0:
            self.image = idle_animation_frames[0]
            print(f"DEBUG Player (init P{self.player_id}): Initial image set from 'idle' animation, frame 0. Image size: {self.image.get_size()}") # DEBUG
        else: # Fallback if idle animation is missing (should be caught by load_all_player_animations)
            self.image = pygame.Surface((30,40)); self.image.fill(C.RED) # Error placeholder
            print(f"CRITICAL Player Init Error ({self.player_id}): 'idle' animation missing or empty after loader. Player invalid.")
            self._valid_init = False; return

        self.rect = self.image.get_rect(midbottom=(start_x, start_y)) # Player's collision rectangle
        print(f"DEBUG Player (init P{self.player_id}): Initial rect: {self.rect}") # DEBUG
        
        # Physics and Movement Attributes
        self.pos = pygame.math.Vector2(start_x, start_y) # Precise position (floating point)
        self.vel = pygame.math.Vector2(0, 0)             # Current velocity
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY) # Current acceleration (gravity applied by default)
        self.facing_right = True   # True if facing right, False if facing left
        self.on_ground = False     # True if standing on a solid platform
        self.on_ladder = False     # True if currently on a ladder
        self.can_grab_ladder = False # True if overlapping a ladder and can interact
        self.touching_wall = 0       # -1 for left wall, 1 for right wall, 0 for no wall contact
        self.can_wall_jump = False   # True if conditions for a wall jump are met
        self.wall_climb_timer = 0    # Timer for wall climb duration ability

        # Player State Flags and Timers (for actions like dash, roll, attack, etc.)
        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = getattr(C, 'PLAYER_DASH_DURATION', 150) # ms
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = getattr(C, 'PLAYER_ROLL_DURATION', 300) # ms
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = getattr(C, 'PLAYER_SLIDE_DURATION', 400) # ms
        
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300 # ms, duration varies by attack type
        self.attack_type = 0 # 0:none, 1:attack1, 2:attack2, 3:combo, 4:crouch_attack
        self.can_combo = False # Flag indicating if player is in a window to perform a combo attack
        self.combo_window = getattr(C, 'PLAYER_COMBO_WINDOW', 150) # ms time window for combo input

        self.wall_climb_duration = getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500) # Max ms for a wall climb attempt

        self.is_taking_hit = False; self.hit_timer = 0 # Timer for current hit stun / invincibility period
        self.hit_duration = getattr(C, 'PLAYER_HIT_STUN_DURATION', 300) # ms duration of the hit stun animation/effect
        self.hit_cooldown = getattr(C, 'PLAYER_HIT_COOLDOWN', 600)   # ms total invincibility period after being hit

        self.is_dead = False # True if player's health is zero or less
        self.death_animation_finished = False # True when the death animation sequence has completed
        self.state_timer = 0 # General timer that can be used by states for duration tracking

        # Health and Combat
        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30) # Default size, positioned dynamically during attack checks

        # Input State Flags (primarily set by input handlers, read by update/state logic)
        self.is_trying_to_move_left = False
        self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False # Usually 'up' key, for climbing ladders/walls
        self.is_holding_crouch_ability_key = False # Usually 'down' key, for crouching/sliding

        # Fireball / Projectile Attributes
        self.fireball_cooldown_timer = 0 # Timestamp of last fireball fired (for cooldown)
        self.fireball_last_input_dir = pygame.math.Vector2(1.0 if self.facing_right else -1.0, 0.0) # Default aim direction
        self.projectile_sprites_group = None # Reference to game's projectile group (set by main game)
        self.all_sprites_group = None      # Reference to game's all_sprites group (set by main game)
        
        # Player-specific key for firing fireball (allows different keys for P1/P2)
        self.fireball_key = None 
        if self.player_id == 1: self.fireball_key = getattr(C, 'P1_FIREBALL_KEY', pygame.K_1)
        elif self.player_id == 2: self.fireball_key = getattr(C, 'P2_FIREBALL_KEY', pygame.K_0)
        print(f"DEBUG Player (init P{self.player_id}): Init completed. _valid_init: {self._valid_init}") # DEBUG


    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group, 
                                        all_sprites_group: pygame.sprite.Group):
        """
        Called by the main game setup to provide the Player instance with references
        to the sprite groups needed for managing projectiles.
        """
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

    def set_state(self, new_state: str):
        """
        Sets the player's logical and animation state, handling transitions and
        state-specific initializations.

        Args:
            new_state (str): The key for the new state (e.g., 'idle', 'run', 'attack').
        """
        if not self._valid_init: return # Cannot change state if player init failed
        
        original_new_state_request = new_state # For debugging purposes

        # --- Validate that the requested animation state exists; fallback if necessary ---
        animation_frames_for_new_state = self.animations.get(new_state)
        if not animation_frames_for_new_state: # Animation for new_state doesn't exist or is empty
            # Determine a sensible fallback state
            fallback_state_key = 'fall' if not self.on_ground else 'idle'
            if fallback_state_key in self.animations and self.animations[fallback_state_key]:
                new_state = fallback_state_key # Use idle/fall as fallback
                if Player.print_limiter.can_print(f"player_set_state_fallback_{self.player_id}_{original_new_state_request}"):
                    print(f"Player Warning ({self.player_id}): State '{original_new_state_request}' anim missing. Fallback to '{new_state}'.")
            else: # Critical: Even idle/fall animations are missing (should be caught by asset loader)
                first_available_anim_key = next((key for key, anim in self.animations.items() if anim), None)
                if not first_available_anim_key: # No animations loaded at all
                    if Player.print_limiter.can_print(f"player_set_state_no_anims_{self.player_id}"):
                        print(f"CRITICAL Player Error ({self.player_id}): No animations available in set_state. Requested: '{original_new_state_request}'. Player invalid.")
                    self._valid_init = False; return # Player cannot function
                new_state = first_available_anim_key # Use the first available animation as a last resort
                if Player.print_limiter.can_print(f"player_set_state_critical_fallback_{self.player_id}"):
                    print(f"Player CRITICAL Warning ({self.player_id}): State '{original_new_state_request}' and fallbacks missing. Using first available: '{new_state}'.")
        
        # --- Determine if a state change is allowed/needed ---
        # Can change if new state is different, OR if it's 'death' (can re-trigger death anim),
        # AND not already dead with death animation finished (unless new state is 'death' itself).
        can_change_state_now = (self.state != new_state or new_state == 'death') and \
                               not (self.is_dead and self.death_animation_finished and new_state != 'death')

        if can_change_state_now:
            # print(f"DEBUG Player ({self.player_id}): Set State: '{self.state}' -> '{new_state}' (Req: '{original_new_state_request}'). Pos: {self.pos.x:.1f},{self.pos.y:.1f}, Vel: {self.vel.x:.1f},{self.vel.y:.1f}") # DEBUG
            self._last_state_for_debug = new_state # Update debug tracker
            
            # --- Reset flags for states the player is exiting ---
            if 'attack' not in new_state and self.is_attacking: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False # Clear general hit stun if not entering 'hit' state
            if new_state != 'dash': self.is_dashing = False
            if new_state != 'roll': self.is_rolling = False
            if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: self.is_sliding = False

            # --- Set the new state and reset animation frame/timers ---
            self.state = new_state
            self.current_frame = 0 # Start animation from the beginning
            self.last_anim_update = pygame.time.get_ticks() # Reset animation timer
            self.state_timer = pygame.time.get_ticks()      # General timer for this new state

            # --- State-Specific Initialization Logic (executed when entering a new state) ---
            if new_state == 'dash':
                self.is_dashing = True; self.dash_timer = self.state_timer # Record dash start time
                self.vel.x = C.PLAYER_DASH_SPEED * (1 if self.facing_right else -1) # Apply dash velocity
                self.vel.y = 0 # Dash is purely horizontal
            elif new_state == 'roll':
                 self.is_rolling = True; self.roll_timer = self.state_timer
                 # Give a speed boost if rolling from standstill or slow movement
                 if abs(self.vel.x) < C.PLAYER_ROLL_SPEED / 2: self.vel.x = C.PLAYER_ROLL_SPEED * (1 if self.facing_right else -1)
                 elif abs(self.vel.x) < C.PLAYER_ROLL_SPEED: self.vel.x += (C.PLAYER_ROLL_SPEED / 3) * (1 if self.facing_right else -1)
                 self.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, self.vel.x)) # Clamp to roll speed limit
            elif new_state == 'slide' or new_state == 'slide_trans_start': # Entering slide
                 self.is_sliding = True; self.slide_timer = self.state_timer
                 # Ensure some initial speed if sliding from a slow run (input handler might also do this)
                 if abs(self.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5:
                     self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if self.facing_right else -1)
            elif 'attack' in new_state: # Covers all attack variations (attack, attack_nm, attack2, etc.)
                self.is_attacking = True; self.attack_timer = self.state_timer # Record attack start time
                # Calculate attack duration based on animation frames and speed modifier (if any)
                animation_for_this_attack = self.animations.get(new_state)
                num_attack_frames = len(animation_for_this_attack) if animation_for_this_attack else 0
                base_ms_per_frame = C.ANIM_FRAME_DURATION
                
                # Attack 2 might have a different speed (longer frame duration)
                if self.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
                    self.attack_duration = num_attack_frames * int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER) if num_attack_frames > 0 else 300 # Default duration
                else:
                    self.attack_duration = num_attack_frames * base_ms_per_frame if num_attack_frames > 0 else 300
                
                # Stop horizontal movement for "No Movement" (_nm) attacks or crouch attacks
                if new_state.endswith('_nm') or new_state == 'crouch_attack':
                    self.vel.x = 0
            elif new_state == 'hit': # Player is hit
                 self.is_taking_hit = True; self.hit_timer = self.state_timer # Start hit stun / invincibility timer
                 # Apply knockback/stun effect physics
                 if not self.on_ground and self.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): # If in air and not strongly ascending
                    self.vel.x *= -0.3 # Slight horizontal knockback in opposite direction of current vel
                    self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4 # Slight vertical pop-up
                 self.is_attacking = False; self.attack_type = 0 # Cancel any current attack
            elif new_state == 'death' or new_state == 'death_nm': # Player dies
                 self.is_dead = True; self.vel.x = 0 # Stop horizontal movement
                 if self.vel.y < -1: self.vel.y = 1 # Stop strong upward momentum (e.g., if died mid-jump)
                 self.acc.x = 0 # No horizontal acceleration during death
                 if not self.on_ground: self.acc.y = C.PLAYER_GRAVITY # Normal gravity if dying in air
                 else: self.vel.y = 0; self.acc.y = 0 # Rest on ground if already there
                 self.death_animation_finished = False # Reset death animation flag
            elif new_state == 'wall_climb':
                 self.wall_climb_timer = self.state_timer # Start wall climb duration timer
                 self.vel.y = C.PLAYER_WALL_CLIMB_SPEED # Apply wall climb speed
            elif new_state == 'wall_slide' or new_state == 'wall_hang':
                 self.wall_climb_timer = 0 # Reset wall climb timer if sliding or hanging (not actively climbing up)

            self.animate() # Update player image immediately to reflect the new state
        
        elif not self.is_dead: # If state didn't change but player is not dead
             self._last_state_for_debug = self.state # Keep debug state current


    def animate(self):
        """
        Updates the player's current image based on its state, frame, and facing direction.
        Handles animation looping, transitions at the end of non-looping animations,
        and image flipping.
        """
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations:
            # print(f"DEBUG Player (animate P{self.player_id}): Animation skipped. Valid: {self._valid_init}, HasAnims: {hasattr(self, 'animations')}, AnimsOK: {bool(self.animations if hasattr(self, 'animations') else False)}") # DEBUG
            return
        if not self.alive(): # Don't animate if sprite is not in any groups (e.g., after self.kill())
            # print(f"DEBUG Player (animate P{self.player_id}): Animation skipped, player not alive (not in groups).") # DEBUG
            return 

        current_time_ms = pygame.time.get_ticks()
        animation_key_to_use = self.state # Start with the player's current logical state

        # --- Determine the correct animation key based on current state and conditions ---
        # This complex logic maps the player's detailed situation to specific animation sheet keys.
        player_is_intending_to_move_lr = self.is_trying_to_move_left or self.is_trying_to_move_right

        if self.is_dead: 
            # Choose between death animation with movement (_nm for No Movement) or static death animation
            animation_key_to_use = 'death_nm' if abs(self.vel.x) < 0.5 and abs(self.vel.y) < 1.0 and \
                                     'death_nm' in self.animations and self.animations['death_nm'] \
                                  else 'death'
            if animation_key_to_use not in self.animations or not self.animations[animation_key_to_use]:
                animation_key_to_use = 'death' # Fallback if preferred death animation is missing
        elif self.is_attacking:
            # Choose attack animation based on attack_type and if player is intending to move
            if self.attack_type == 1: animation_key_to_use = 'attack' if player_is_intending_to_move_lr and 'attack' in self.animations and self.animations['attack'] else 'attack_nm'
            elif self.attack_type == 2: animation_key_to_use = 'attack2' if player_is_intending_to_move_lr and 'attack2' in self.animations and self.animations['attack2'] else 'attack2_nm'
            elif self.attack_type == 3: animation_key_to_use = 'attack_combo' if player_is_intending_to_move_lr and 'attack_combo' in self.animations and self.animations['attack_combo'] else 'attack_combo_nm'
            elif self.attack_type == 4: animation_key_to_use = 'crouch_attack'
            
            # Fallback if specific attack_nm (No Movement) or standard attack animation is missing
            if animation_key_to_use not in self.animations or not self.animations[animation_key_to_use]:
                 base_attack_state_key = animation_key_to_use.replace('_nm', '') # Try without '_nm' suffix
                 if base_attack_state_key in self.animations and self.animations[base_attack_state_key]:
                     animation_key_to_use = base_attack_state_key
                 else: # Ultimate fallback for attack animations
                     animation_key_to_use = 'idle' 
        elif self.state == 'wall_climb': # Specific logic for wall climb animation
             player_is_actively_climbing_wall = self.is_holding_climb_ability_key and \
                                    abs(self.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1 # Check if actually moving upwards
             animation_key_to_use = 'wall_climb' if player_is_actively_climbing_wall and 'wall_climb' in self.animations and self.animations['wall_climb'] else 'wall_climb_nm'
             if animation_key_to_use not in self.animations or not self.animations[animation_key_to_use]:
                 animation_key_to_use = 'wall_climb' # Fallback to base wall_climb if _nm variant missing
        elif self.state == 'hit': animation_key_to_use = 'hit' # Standard hit animation
        elif not self.on_ground and not self.on_ladder and self.touching_wall == 0 and \
             self.state not in ['jump', 'jump_fall_trans'] and self.vel.y > 1: # Standard falling animation
             animation_key_to_use = 'fall'
        elif self.on_ladder: # Ladder animations
            animation_key_to_use = 'ladder_climb' if abs(self.vel.y) > 0.1 else 'ladder_idle' # Moving or idle on ladder
            if animation_key_to_use not in self.animations or not self.animations[animation_key_to_use]:
                animation_key_to_use = 'idle' # Fallback if specific ladder animations are missing
        # Direct state-to-animation key mappings for special movement/action states
        elif self.is_dashing: animation_key_to_use = 'dash'
        elif self.is_rolling: animation_key_to_use = 'roll'
        elif self.is_sliding: animation_key_to_use = 'slide' # Main sliding animation
        elif self.state == 'slide_trans_start': animation_key_to_use = 'slide_trans_start'
        elif self.state == 'slide_trans_end': animation_key_to_use = 'slide_trans_end'
        elif self.state == 'crouch_trans': animation_key_to_use = 'crouch_trans'
        elif self.state == 'turn': animation_key_to_use = 'turn'
        elif self.state == 'jump': animation_key_to_use = 'jump'
        elif self.state == 'jump_fall_trans': animation_key_to_use = 'jump_fall_trans'
        elif self.state == 'wall_slide': animation_key_to_use = 'wall_slide'
        elif self.state == 'wall_hang': animation_key_to_use = 'wall_hang'
        elif self.on_ground: # Grounded states based on movement intention and crouching
            if self.is_crouching:
                animation_key_to_use = 'crouch_walk' if player_is_intending_to_move_lr and 'crouch_walk' in self.animations and self.animations['crouch_walk'] else 'crouch'
            elif player_is_intending_to_move_lr: animation_key_to_use = 'run'
            else: animation_key_to_use = 'idle'
        
        # Final fallback if the derived animation_key_to_use is invalid or missing
        if animation_key_to_use not in self.animations or not self.animations[animation_key_to_use]: 
            # print(f"DEBUG Player (animate P{self.player_id}): Anim key '{animation_key_to_use}' for state '{self.state}' not found or empty. Falling back to 'idle'.") # DEBUG
            animation_key_to_use = 'idle' # Default to 'idle' animation
        
        current_animation_frames_list = self.animations.get(animation_key_to_use)

        if not current_animation_frames_list: # Should not happen if 'idle' is guaranteed by asset loader
            if hasattr(self, 'image') and self.image: self.image.fill(C.RED) # Error placeholder
            if Player.print_limiter.can_print(f"player_animate_no_frames_{self.player_id}_{animation_key_to_use}"):
                print(f"CRITICAL Player Animate Error ({self.player_id}): No frames found for anim key '{animation_key_to_use}' (Logical state: {self.state})")
            return
        
        # print(f"DEBUG Player (animate P{self.player_id}): Using anim key '{animation_key_to_use}', state '{self.state}', {len(current_animation_frames_list)} frames. Current frame idx: {self.current_frame}") # DEBUG - Can be noisy

        # Determine frame duration (e.g., Attack 2 might be slower, having longer frame durations)
        ms_per_frame_for_current_anim = C.ANIM_FRAME_DURATION
        if self.is_attacking and self.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
            ms_per_frame_for_current_anim = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

        # --- Animation Frame Progression ---
        if not (self.is_dead and self.death_animation_finished): # Don't advance frame if death animation has completed
            if current_time_ms - self.last_anim_update > ms_per_frame_for_current_anim: # Time for next frame
                self.last_anim_update = current_time_ms # Reset timer for this frame
                self.current_frame += 1 # Advance to the next frame
                
                if self.current_frame >= len(current_animation_frames_list): # Reached the end of the animation sequence
                    if self.is_dead: # If death animation just finished playing
                        # if Player.print_limiter.can_print(f"player_animate_death_anim_completed_{self.player_id}"):
                        #     print(f"DEBUG Player ({self.player_id}): Death Animation sequence visually FINISHED.")
                        self.current_frame = len(current_animation_frames_list) - 1 # Hold the last frame of death animation
                        self.death_animation_finished = True
                        # Update image one last time for the final death frame before returning
                        final_death_image_surface = current_animation_frames_list[self.current_frame]
                        if not self.facing_right: final_death_image_surface = pygame.transform.flip(final_death_image_surface, True, False)
                        old_player_midbottom = self.rect.midbottom
                        self.image = final_death_image_surface
                        self.rect = self.image.get_rect(midbottom=old_player_midbottom)
                        return # Stop further animation processing for this frame once death anim is done
                    
                    # --- Handle transitions for non-looping animations ---
                    # Define states whose animations should not loop but transition to another state.
                    non_looping_animation_states = [
                        'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                        'crouch_attack','dash','roll','slide','hit','turn','jump',
                        'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end']
                    
                    if self.state in non_looping_animation_states: # If current logical state's animation just finished
                         next_logical_state_after_anim = None # Determine the state to transition to
                         current_logical_state_of_player = self.state 
                         player_is_intending_to_move_at_anim_end = self.is_trying_to_move_left or self.is_trying_to_move_right

                         # Determine next state based on the one that just finished
                         if current_logical_state_of_player == 'jump':
                             next_logical_state_after_anim = 'jump_fall_trans' if 'jump_fall_trans' in self.animations and self.animations['jump_fall_trans'] else 'fall'
                         elif current_logical_state_of_player == 'jump_fall_trans':
                             next_logical_state_after_anim = 'fall'
                         elif current_logical_state_of_player == 'hit': 
                             next_logical_state_after_anim = 'fall' if not self.on_ground and not self.on_ladder else 'idle'
                         elif current_logical_state_of_player == 'turn':
                             next_logical_state_after_anim = 'run' if player_is_intending_to_move_at_anim_end else 'idle'
                         elif 'attack' in current_logical_state_of_player: # Any attack animation finished
                              self.is_attacking = False; self.attack_type = 0 # Reset attack flags
                              # Transition based on player's situation after attack
                              if self.on_ladder: pass # Ladder logic will take over if still on ladder
                              elif self.is_crouching: next_logical_state_after_anim = 'crouch'
                              elif not self.on_ground: next_logical_state_after_anim = 'fall'
                              elif player_is_intending_to_move_at_anim_end : next_logical_state_after_anim = 'run'
                              else: next_logical_state_after_anim = 'idle'
                         elif current_logical_state_of_player == 'crouch_trans': # Crouch transition (e.g., stand to crouch) finished
                             self.is_crouching = self.is_holding_crouch_ability_key # Update crouch based on key hold
                             next_logical_state_after_anim = 'crouch' if self.is_crouching else 'idle'
                         elif current_logical_state_of_player == 'slide_trans_start': # Slide entry transition finished
                             next_logical_state_after_anim = 'slide' # Enter main slide animation
                         elif current_logical_state_of_player in ['slide_trans_end', 'slide']: # Slide finished (either main or exit transition)
                             self.is_sliding = False # No longer sliding
                             self.is_crouching = self.is_holding_crouch_ability_key # Check if still holding crouch
                             next_logical_state_after_anim = 'crouch' if self.is_crouching else 'idle'
                         else: # For other non-looping states like dash, roll
                              if current_logical_state_of_player == 'dash': self.is_dashing = False # Dash action ends
                              if current_logical_state_of_player == 'roll': self.is_rolling = False # Roll action ends
                              # Default transition based on environment after action
                              if self.on_ladder: pass 
                              elif self.is_crouching: next_logical_state_after_anim = 'crouch'
                              elif not self.on_ground: next_logical_state_after_anim = 'fall'
                              elif player_is_intending_to_move_at_anim_end : next_logical_state_after_anim = 'run'
                              else: next_logical_state_after_anim = 'idle'
                         
                         if next_logical_state_after_anim: # If a next state was determined
                             self.set_state(next_logical_state_after_anim) # Transition to it
                             return # set_state calls animate(), so return to avoid double processing this frame
                         else: # Should not happen for defined non-looping states; implies missing transition logic
                             self.current_frame = 0 # Loop this non-looping anim (usually an error in state logic)
                    else: # For looping animations (e.g. idle, run, fall), reset to first frame
                        self.current_frame = 0 
                
                # Ensure current_frame is valid after potential reset/change due to animation end
                if self.current_frame >= len(current_animation_frames_list): self.current_frame = 0
        
        # --- Get the actual image surface for the current animation frame ---
        # Handle cases where animation frames might be empty (though asset loader should prevent this)
        if not current_animation_frames_list or self.current_frame < 0 or self.current_frame >= len(current_animation_frames_list):
            # print(f"DEBUG Player (animate P{self.player_id}): Invalid frame index ({self.current_frame}) or empty frame list for anim '{animation_key_to_use}'. Resetting to 0.") # DEBUG
            self.current_frame = 0 # Reset frame index to prevent crash
            if not current_animation_frames_list: # Still no frames (major issue)
                if hasattr(self, 'image') and self.image: self.image.fill(C.RED) # Error placeholder
                return

        image_for_this_frame = current_animation_frames_list[self.current_frame]
        # Flip image horizontally if player is not facing right
        if not self.facing_right: 
            image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)
        
        # --- Update player's main image and rect if it changed or facing direction changed ---
        # This optimizes by avoiding unnecessary image/rect updates if nothing visual changed.
        if self.image is not image_for_this_frame or self._last_facing_right != self.facing_right:
            old_player_midbottom_pos = self.rect.midbottom # Preserve position anchor (midbottom)
            self.image = image_for_this_frame # Set the new image
            self.rect = self.image.get_rect(midbottom=old_player_midbottom_pos) # Re-anchor rect
            self._last_facing_right = self.facing_right # Update tracking of last facing direction
            # print(f"DEBUG Player (animate P{self.player_id}): Image updated. New image size: {self.image.get_size()}, Rect: {self.rect}") # DEBUG


    # --- Input Handling Methods (delegate to player_input_handler) ---
    def handle_input(self, keys_pressed_state, pygame_event_list):
        """Handles standard WASD keyboard input by delegating to the input handler."""
        # Default key configuration for Player 1 (or single player)
        default_key_config = {
            'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
            'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
            'roll': pygame.K_LCTRL, 'interact': pygame.K_e
        }
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, default_key_config)

    def handle_mapped_input(self, keys_pressed_state, pygame_event_list, key_map_dict):
        """Handles input based on a provided key_map dictionary (e.g., for Player 2)."""
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, key_map_dict)

    # --- Combat Handling Methods (delegate to player_combat_handler) ---
    def fire_fireball(self):
        """Initiates firing a fireball by delegating to the combat handler."""
        fire_player_fireball(self)

    def check_attack_collisions(self, list_of_targets):
        """Checks for collisions during an attack by delegating to the combat handler."""
        check_player_attack_collisions(self, list_of_targets)

    def take_damage(self, damage_amount_taken):
        """Processes damage taken by delegating to the combat handler."""
        player_take_damage(self, damage_amount_taken)

    def self_inflict_damage(self, damage_amount_to_self):
        """Inflicts damage on self (debug/special) by delegating to the combat handler."""
        player_self_inflict_damage(self, damage_amount_to_self)

    def heal_to_full(self):
        """Heals player to full health by delegating to the combat handler."""
        player_heal_to_full(self)
        
    # --- Network Handling Methods (delegate to player_network_handler) ---
    def get_network_data(self):
        """Gets player state for network transmission by delegating to the network handler."""
        return get_player_network_data(self)

    def set_network_data(self, received_network_data):
        """Applies received network data to this player by delegating to the network handler."""
        set_player_network_data(self, received_network_data)

    def handle_network_input(self, network_input_data_dict):
        """Processes input commands received over network by delegating to the network handler."""
        handle_player_network_input(self, network_input_data_dict)

    def get_input_state_for_network(self, current_pygame_keys_state, current_pygame_event_list, 
                                    key_map_for_this_player):
        """Gathers local input state for network transmission by delegating to the network handler."""
        return get_player_input_state_for_network(self, current_pygame_keys_state, 
                                                  current_pygame_event_list, key_map_for_this_player)

    # --- Core Update Method (Physics, State Timers, Collisions) ---
    def update(self, dt_sec, platforms_group, ladders_group, hazards_group, 
               other_players_sprite_list, enemies_sprite_list):
        """
        Main update loop for the player. Handles physics, state timer progression,
        and collision detection/resolution.

        Args:
            dt_sec (float): Delta time in seconds since the last frame. Not directly used in this
                            version's physics, but good practice for frame-rate independent movement.
            platforms_group (pygame.sprite.Group): Group of solid platform sprites.
            ladders_group (pygame.sprite.Group): Group of ladder sprites.
            hazards_group (pygame.sprite.Group): Group of hazard sprites (e.g., lava).
            other_players_sprite_list (list): List of other Player sprites for character collision.
            enemies_sprite_list (list): List of Enemy sprites for character and attack collision.
        """
        # print(f"DEBUG Player (update P{self.player_id}): Start of update. Pos: {self.pos.x:.1f},{self.pos.y:.1f}, Vel: {self.vel.x:.1f},{self.vel.y:.1f}, State: {self.state}, Valid: {self._valid_init}, Alive: {self.alive()}") # DEBUG - Very noisy
        if not self._valid_init: return # Do nothing if player initialization failed
        
        # --- Handle Death State Separately ---
        # If player is dead, only handle falling physics (if applicable) and death animation.
        if self.is_dead: 
            if self.alive() and hasattr(self, 'animate'): # Ensure still in sprite groups and can animate
                if not self.death_animation_finished: # If death animation is still playing
                    if not self.on_ground: # Apply gravity if in air during death sequence
                        # self.acc.y should be C.PLAYER_GRAVITY, set in set_state('death')
                        self.vel.y += self.acc.y 
                        self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18)) # Cap fall speed
                        self.pos.y += self.vel.y # Update position
                        self.rect.bottom = round(self.pos.y) # Update rect
                        # Check for ground collision during death fall
                        self.on_ground = False # Assume not on ground until collision proves otherwise
                        for platform_sprite in pygame.sprite.spritecollide(self, platforms_group, False):
                            # Check if landed on top of platform
                            if self.vel.y > 0 and self.rect.bottom > platform_sprite.rect.top and \
                               (self.pos.y - self.vel.y) <= platform_sprite.rect.top + 1: # Approx. prev bottom
                                self.rect.bottom = platform_sprite.rect.top
                                self.on_ground = True; self.vel.y = 0; self.acc.y = 0 # Stop falling
                                self.pos.y = self.rect.bottom; break # Landed
                self.animate() # Continue playing/holding death animation
            return # No further updates (movement, input, etc.) if dead

        current_time_ms = pygame.time.get_ticks() # Current game time

        # --- Manage State Timers and Cooldowns (Dash, Roll, Slide, Hit Invincibility) ---
        # Dash timer: if dash duration ends, transition out of dash state
        if self.is_dashing and current_time_ms - self.dash_timer > self.dash_duration:
            self.is_dashing = False # Dash action finished
            self.set_state('idle' if self.on_ground else 'fall') # Transition to appropriate state
        
        # Roll timer: if roll duration ends, transition out of roll state
        if self.is_rolling and current_time_ms - self.roll_timer > self.roll_duration:
            self.is_rolling = False # Roll action finished
            self.set_state('idle' if self.on_ground else 'fall')
        
        # Slide timer: if slide duration ends (can also end by friction or animation)
        if self.is_sliding and current_time_ms - self.slide_timer > self.slide_duration:
            # Slide logic in animate() or input_handler often transitions out earlier based on friction/anim end.
            # This timer is a failsafe or for fixed-duration slides.
            if self.state == 'slide': # If still in main slide state by timer end
                self.is_sliding = False
                # Transition to slide end animation or crouch/idle based on input
                slide_end_anim_key = 'slide_trans_end' if 'slide_trans_end' in self.animations else None
                if slide_end_anim_key: self.set_state(slide_end_anim_key)
                else: self.set_state('crouch' if self.is_holding_crouch_ability_key else 'idle')

        # Hit stun / invincibility cooldown: manage when player can be hit again
        if self.is_taking_hit and current_time_ms - self.hit_timer > self.hit_cooldown:
            # Note: self.hit_duration is for the stun animation/effect. self.hit_cooldown is for total invincibility.
            if self.state == 'hit': # If still in 'hit' state after invincibility cooldown (anim might be longer)
                self.is_taking_hit = False # Cooldown over, can be hit again
                # Don't force state change here; let 'hit' animation finish or other logic transition player out.
            else: # Cooldown ended, and player is no longer in 'hit' state (already transitioned)
                self.is_taking_hit = False
        
        # --- Ladder Interaction ---
        self.check_ladder_collisions(ladders_group) # Update self.can_grab_ladder
        if self.on_ladder and not self.can_grab_ladder: # If was on ladder but no longer can grab (e.g., moved off)
            self.on_ladder = False # No longer on ladder
            self.set_state('fall' if not self.on_ground else 'idle') # Transition to fall or idle

        # --- Apply Physics (Movement based on Velocity and Acceleration) ---
        # Vertical movement (gravity, jump, ladder climbing speed)
        should_apply_gravity_this_frame = not (
            self.on_ladder or self.state == 'wall_hang' or
            (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # If actively climbing up
            self.is_dashing # Dashing is purely horizontal
        )
        if should_apply_gravity_this_frame:
            self.vel.y += self.acc.y # self.acc.y is usually C.PLAYER_GRAVITY

        # Horizontal movement (acceleration from input, friction)
        should_apply_horizontal_physics = not (
            self.is_dashing or self.is_rolling or self.on_ladder or
            (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) # No horiz control while climbing up
        )
        if should_apply_horizontal_physics:
            self.vel.x += self.acc.x # self.acc.x is set by input_handler

            # --- Apply Friction ---
            friction_coefficient_to_apply = 0 # Default: no friction
            if self.on_ground and self.acc.x == 0 and not self.is_sliding and self.state != 'slide':
                friction_coefficient_to_apply = C.PLAYER_FRICTION # Standard ground friction when not accelerating
            elif not self.on_ground and not self.is_attacking and \
                 self.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']:
                friction_coefficient_to_apply = C.PLAYER_FRICTION * 0.2 # Air friction (less effective)
            elif self.is_sliding or self.state == 'slide':
                friction_coefficient_to_apply = C.PLAYER_FRICTION * 0.7 # Specific friction for sliding

            if friction_coefficient_to_apply != 0:
                 friction_force_applied = self.vel.x * friction_coefficient_to_apply # Friction opposes velocity
                 if abs(self.vel.x) > 0.1: self.vel.x += friction_force_applied # Apply friction
                 else: self.vel.x = 0 # Stop if velocity is very low
                 
                 # If sliding and friction brings velocity very low, end slide
                 if abs(self.vel.x) < 0.5 and (self.is_sliding or self.state == 'slide'):
                     self.is_sliding = False # No longer sliding
                     # Transition to slide end animation or crouch/idle
                     slide_end_anim_key_friction = 'slide_trans_end' if 'slide_trans_end' in self.animations and self.animations['slide_trans_end'] else None
                     if slide_end_anim_key_friction: self.set_state(slide_end_anim_key_friction)
                     else: # No transition animation, decide based on crouch key hold
                         self.is_crouching = self.is_holding_crouch_ability_key
                         self.set_state('crouch' if self.is_crouching else 'idle')
            
            # --- Speed Limiting (Horizontal) ---
            # Apply normal run speed limit, or reduced limit if crouch-walking.
            # Dash, roll, and slide manage their own speeds and are excluded here.
            current_horizontal_speed_limit = C.PLAYER_RUN_SPEED_LIMIT
            if self.is_crouching and self.state == 'crouch_walk':
                current_horizontal_speed_limit *= 0.6 # Slower when crouch-walking
            
            if not self.is_dashing and not self.is_rolling and not self.is_sliding and self.state != 'slide':
                self.vel.x = max(-current_horizontal_speed_limit, min(current_horizontal_speed_limit, self.vel.x))

        # --- Terminal Velocity (Vertical) ---
        # Cap falling speed to prevent excessive acceleration.
        if self.vel.y > 0 and not self.on_ladder: # If moving downwards and not on a ladder
            self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))

        # --- Collision Detection and Resolution ---
        self.touching_wall = 0 # Reset wall touch state each frame; will be set by x-collision
        self.on_ground = False # Reset ground state; will be set by y-collision with platforms

        # --- Horizontal Collision Pass ---
        self.pos.x += self.vel.x # Update precise horizontal position
        self.rect.centerx = round(self.pos.x) # Update rect for collision check
        self.check_platform_collisions('x', platforms_group) # Check and resolve platform collisions
        
        # Consolidate list of other characters for collision checks
        all_other_character_sprites = [p for p in other_players_sprite_list if p and p._valid_init and p.alive() and p is not self] + \
                                      [e for e in enemies_sprite_list if e and e._valid_init and e.alive()]
        collided_horizontally_with_character = self.check_character_collisions('x', all_other_character_sprites)

        # --- Vertical Collision Pass ---
        self.pos.y += self.vel.y # Update precise vertical position
        self.rect.bottom = round(self.pos.y) # Update rect for collision check
        self.check_platform_collisions('y', platforms_group) # Check and resolve platform collisions (sets self.on_ground)

        # Only check for vertical character collisions if no horizontal character collision occurred in this frame
        # to prevent characters from getting "stuck" or pushed through each other weirdly due to double collision resolution.
        if not collided_horizontally_with_character: 
            self.check_character_collisions('y', all_other_character_sprites) 

        # --- Synchronize Precise Position with Rect after all collision resolutions ---
        self.pos.x = self.rect.centerx 
        self.pos.y = self.rect.bottom

        # --- Hazard Collisions (e.g., Lava) ---
        self.check_hazard_collisions(hazards_group)

        # --- Attack Collisions (if player is currently attacking) ---
        if self.alive() and not self.is_dead and self.is_attacking: # Ensure player is in a state to attack
            # Targets for melee attacks can be other players or enemies
            targets_for_player_attack = [p for p in other_players_sprite_list if p and p._valid_init and p.alive() and p is not self] + \
                                        [e for e in enemies_sprite_list if e and e._valid_init and e.alive()]
            self.check_attack_collisions(targets_for_player_attack) # Delegates to combat_handler via self.method
        
        # --- Final Animation Update for the Frame ---
        # This ensures the player's visual representation matches their current state and facing direction.
        self.animate()
        # print(f"DEBUG Player (update P{self.player_id}): End of update. Pos: {self.pos.x:.1f},{self.pos.y:.1f}, Rect: {self.rect}, Image: {self.image.get_size() if self.image else 'NoImg'}") # DEBUG - Very Noisy


    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        """
        Handles collisions between the player and solid platforms.
        Resolves collisions by adjusting player position and velocity.
        Updates `self.on_ground` and `self.touching_wall` flags.

        Args:
            direction (str): The axis of collision to check ('x' or 'y').
            platforms_group (pygame.sprite.Group): The sprite group containing platforms.
        """
        collided_with_wall_on_side = 0 # For detecting wall touch: -1 for left, 1 for right
        
        # Iterate through all platforms the player is currently colliding with
        for platform_sprite in pygame.sprite.spritecollide(self, platforms_group, False):
            if direction == 'x': # --- Horizontal Collision Resolution ---
                if self.vel.x > 0: # Player was moving right, collided with platform's left side
                    self.rect.right = platform_sprite.rect.left # Align player's right edge with platform's left
                    # Check if this collision constitutes a wall touch (player is in air, not on ladder)
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > platform_sprite.rect.top + 5: # +5 to avoid false positives from ground edges
                        collided_with_wall_on_side = 1 # Touched a wall on player's right
                elif self.vel.x < 0: # Player was moving left, collided with platform's right side
                    self.rect.left = platform_sprite.rect.right # Align player's left edge with platform's right
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > platform_sprite.rect.top + 5:
                        collided_with_wall_on_side = -1 # Touched a wall on player's left
                self.vel.x = 0 # Stop horizontal movement due to collision
                self.pos.x = self.rect.centerx # Update precise position based on new rect.centerx
            
            elif direction == 'y': # --- Vertical Collision Resolution ---
                if self.vel.y > 0: # Player was moving down (falling or landing)
                    # Check if player was above or at platform's top edge in the previous frame (approximately)
                    # This helps ensure landing only happens when coming from above.
                    if self.rect.bottom > platform_sprite.rect.top and \
                       (self.pos.y - self.vel.y) <= platform_sprite.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX: # pos.y is bottom, vel.y is positive
                        self.rect.bottom = platform_sprite.rect.top # Align player's bottom with platform's top
                        if not self.on_ground: # If this is the frame the player lands
                            self.can_wall_jump=False; self.wall_climb_timer=0 # Reset wall abilities upon landing
                            if not self.is_sliding and self.state != 'slide_trans_end': # Don't kill slide momentum on land
                                self.vel.x *= 0.8 # Apply slight horizontal friction on landing if not sliding
                        self.on_ground=True; self.vel.y=0 # Player is now on ground, stop vertical velocity
                elif self.vel.y < 0: # Player was moving up (e.g., jumping into a ceiling)
                    # Check if player was below or at platform's bottom edge in previous frame (approx)
                    # Player's top edge is at (pos.y - rect.height)
                    if self.rect.top < platform_sprite.rect.bottom and \
                       ((self.pos.y - self.rect.height) - self.vel.y) >= platform_sprite.rect.bottom -1 :
                         if self.on_ladder: self.on_ladder = False # Knocked off ladder if hit ceiling
                         self.rect.top = platform_sprite.rect.bottom # Align player's top with platform's bottom
                         self.vel.y=0 # Stop upward movement due to collision
                self.pos.y = self.rect.bottom # Update precise position based on new rect.bottom
        
        # After checking all platforms, if a wall collision was detected horizontally:
        if direction == 'x' and collided_with_wall_on_side != 0 and \
           not self.on_ground and not self.on_ladder: # Wall interactions only happen in air
             self.touching_wall = collided_with_wall_on_side # Set which side wall is on
             # Player can wall jump unless they are actively climbing upwards (which consumes the jump ability for that climb)
             self.can_wall_jump = not (self.state == 'wall_climb' and self.is_holding_climb_ability_key)


    def check_ladder_collisions(self, ladders_group: pygame.sprite.Group):
        """
        Checks if the player is overlapping a ladder and can grab onto it.
        Updates `self.can_grab_ladder`.

        Args:
            ladders_group (pygame.sprite.Group): The sprite group containing ladders.
        """
        if not self._valid_init: return # Cannot interact if player is invalid
        
        # Use a slightly smaller rectangle for ladder detection to make grabbing more intentional
        # This helps avoid grabbing ladders accidentally when just brushing past the sides.
        # Inflate by negative values to shrink the rect. Shrink width more than height.
        ladder_check_rect = self.rect.inflate(-self.rect.width * 0.6, -self.rect.height * 0.1) 
        
        self.can_grab_ladder = False # Reset flag each frame
        # Check for collision with any ladder using the smaller check_rect
        for ladder_sprite in pygame.sprite.spritecollide(self, ladders_group, False, 
                               collided=lambda player_sprite, ladder_rect_obj: ladder_check_rect.colliderect(ladder_rect_obj.rect)):
            # Additional conditions for a valid grab:
            # Player should be somewhat horizontally centered on the ladder.
            # Player's vertical center should be within the ladder's vertical span.
            if abs(self.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
               ladder_sprite.rect.top < self.rect.centery < ladder_sprite.rect.bottom : 
                  self.can_grab_ladder = True; break # Found a grabbable ladder


    def check_character_collisions(self, direction: str, characters_list: list):
        """
        Handles collisions between this player and other characters (players, enemies).
        Applies a simple push-back effect to both colliding characters.
        Handles stomp mechanic if player lands on an enemy.

        Args:
            direction (str): The axis of collision to check ('x' or 'y').
            characters_list (list): A list of other character Sprites to check against.

        Returns:
            bool: True if a collision with another character occurred on this axis, False otherwise.
        """
        if not self._valid_init or self.is_dead or not self.alive(): return False # Cannot collide if in these states
        
        a_character_collision_occurred_this_frame = False
        for other_char_sprite in characters_list:
            if other_char_sprite is self: continue # Skip collision check with self
            
            # Ensure the other character is valid, alive, and not dead
            if not (other_char_sprite and hasattr(other_char_sprite, '_valid_init') and \
                    other_char_sprite._valid_init and hasattr(other_char_sprite, 'is_dead') and \
                    not other_char_sprite.is_dead and other_char_sprite.alive()):
                continue 

            if self.rect.colliderect(other_char_sprite.rect): # If a collision is detected
                a_character_collision_occurred_this_frame = True
                
                # --- Stomp Mechanic (check before generic character collision resolution) ---
                is_enemy_and_stompable = isinstance(other_char_sprite, Enemy) and \
                                         not other_char_sprite.is_dead and \
                                         not getattr(other_char_sprite, 'is_stomp_dying', False)

                if is_enemy_and_stompable and direction == 'y' and self.vel.y > 0.5: # Player is falling/jumping downwards
                    # Stomp condition: Player's bottom is near the enemy's top
                    player_bottom_vs_enemy_top_diff = self.rect.bottom - other_char_sprite.rect.top
                    
                    # Check if player's bottom edge is within a small grace area of the enemy's top edge
                    # and player's previous bottom edge was above or at the enemy's top edge.
                    # This ensures the player is landing ON TOP, not just brushing past vertically.
                    previous_player_bottom = self.pos.y - self.vel.y 
                    
                    if (previous_player_bottom <= other_char_sprite.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX and \
                        player_bottom_vs_enemy_top_diff >= 0 and \
                        player_bottom_vs_enemy_top_diff < other_char_sprite.rect.height * 0.33): # Landed within top third
                        
                        if hasattr(other_char_sprite, 'stomp_kill') and callable(other_char_sprite.stomp_kill):
                            other_char_sprite.stomp_kill()
                            self.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH # Player bounces off
                            self.on_ground = False # Player is in the air after bounce
                            self.set_state('jump') # Optional: Could use a specific bounce animation if available
                            # Player position might need slight adjustment to ensure clear bounce
                            self.rect.bottom = other_char_sprite.rect.top -1 # Place player slightly above enemy
                            self.pos.y = self.rect.bottom 
                        return True # Stomp occurred, no further collision checks for this interaction

                # --- Generic Character Collision (if not a stomp) ---
                bounce_velocity_on_char_collision = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5) # From constants
                
                if direction == 'x': # --- Horizontal Character Collision ---
                    # Determine push direction: self is pushed away from other_char
                    push_direction_for_self = -1 if self.rect.centerx < other_char_sprite.rect.centerx else 1
                    
                    # Adjust self's rect to resolve overlap
                    if push_direction_for_self == -1: self.rect.right = other_char_sprite.rect.left
                    else: self.rect.left = other_char_sprite.rect.right
                    self.vel.x = push_direction_for_self * bounce_velocity_on_char_collision # Apply bounce to self
                    
                    # Apply opposite bounce to the other character if it has physics attributes
                    if hasattr(other_char_sprite, 'vel'): 
                        other_char_sprite.vel.x = -push_direction_for_self * bounce_velocity_on_char_collision
                    # Slightly nudge other character's precise position to help prevent immediate re-collision
                    if hasattr(other_char_sprite, 'pos') and hasattr(other_char_sprite, 'rect'): 
                        other_char_sprite.pos.x += (-push_direction_for_self * 1.5) # Small separation nudge
                        other_char_sprite.rect.centerx = round(other_char_sprite.pos.x)
                    self.pos.x = self.rect.centerx # Update self's precise position

                elif direction == 'y': # --- Vertical Character Collision ---
                    # Scenario 1: This player lands on top of another character
                    if self.vel.y > 0 and self.rect.bottom > other_char_sprite.rect.top and \
                       self.rect.centery < other_char_sprite.rect.centery: # Ensure self is mostly above other
                        self.rect.bottom = other_char_sprite.rect.top # Land on top of other character
                        self.on_ground = True; self.vel.y = 0 # Player is now "on_ground" (on the other char)
                    # Scenario 2: This player hits another character from below (e.g., headbutt)
                    elif self.vel.y < 0 and self.rect.top < other_char_sprite.rect.bottom and \
                         self.rect.centery > other_char_sprite.rect.centery: # Ensure self is mostly below other
                        self.rect.top = other_char_sprite.rect.bottom # Align top with other's bottom
                        self.vel.y = 0 # Stop upward movement
                    self.pos.y = self.rect.bottom # Update self's precise position
        return a_character_collision_occurred_this_frame


    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        """
        Checks for collisions with hazards like lava.
        If a collision occurs, player takes damage and is bounced.

        Args:
            hazards_group (pygame.sprite.Group): The sprite group containing hazards.
        """
        current_time_ms = pygame.time.get_ticks()
        # Player cannot be damaged by hazards if invalid, dead, or in hit cooldown period
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and current_time_ms - self.hit_timer < self.hit_cooldown): 
            return
            
        has_been_damaged_by_hazard_this_frame = False
        # Use a specific point for hazard collision (e.g., near player's feet for lava)
        # This prevents taking damage if only the top of the player sprite brushes a hazard.
        hazard_check_point_at_feet = (self.rect.centerx, self.rect.bottom - 2) 

        for hazard_sprite_instance in hazards_group: 
            # Check specifically for Lava instances (can be extended for other hazard types)
            if isinstance(hazard_sprite_instance, Lava) and \
               hazard_sprite_instance.rect.collidepoint(hazard_check_point_at_feet):
                
                if not has_been_damaged_by_hazard_this_frame: # Avoid multiple damage ticks per frame from same hazard type
                    # if Player.print_limiter.can_print(f"player_hazard_touch_{self.player_id}_lava"):
                    #     print(f"DEBUG Player ({self.player_id}): Touched LAVA at {hazard_check_point_at_feet}.")
                    
                    self.take_damage(C.LAVA_DAMAGE) # Delegates to combat_handler via self.take_damage method
                    has_been_damaged_by_hazard_this_frame = True 
                    
                    if not self.is_dead: # If player survived the lava damage, bounce them out
                         self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 # Strong bounce upwards
                         # Bounce horizontally away from the center of the lava hazard
                         horizontal_push_direction_from_hazard = 1 if self.rect.centerx < hazard_sprite_instance.rect.centerx else -1
                         self.vel.x = -horizontal_push_direction_from_hazard * \
                                      getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.5 # Moderate horizontal push
                         self.on_ground = False # Player is now in the air
                         self.on_ladder = False # And definitely not on a ladder
                    break # Process one lava collision per frame to avoid multiple damage instances


    def reset_state(self, spawn_position_tuple: tuple):
        """
        Resets the player to their initial state at the given spawn position.
        Called for game restarts or when player respawns.

        Args:
            spawn_position_tuple (tuple): (x, y) coordinates for the player's midbottom.
        """
        print(f"DEBUG Player (reset_state P{self.player_id}): Resetting state to spawn at {spawn_position_tuple}. Current valid: {self._valid_init}") # DEBUG
        if not self._valid_init: 
            # if Player.print_limiter.can_print(f"player_reset_fail_invalid_init_{self.player_id}"):
            #     print(f"Player Warning ({self.player_id}): Cannot reset, _valid_init is False.")
            # Try to re-validate if possible, might be risky if assets truly failed
            asset_folder_path = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder_path)
            if self.animations is not None:
                self._valid_init = True
                idle_animation_frames = self.animations.get('idle')
                if idle_animation_frames and len(idle_animation_frames) > 0:
                    self.image = idle_animation_frames[0]
                else:
                    self.image = pygame.Surface((30,40)); self.image.fill(C.RED)
                print(f"DEBUG Player (reset_state P{self.player_id}): Re-attempted animation load. New _valid_init: {self._valid_init}") # DEBUG
            else:
                print(f"DEBUG Player (reset_state P{self.player_id}): Re-animation load FAILED. Still invalid.") # DEBUG
                return
        
        # print(f"Player Info ({self.player_id}): RESETTING state to spawn at {spawn_position_tuple}")
        # Reset position and physics
        self.pos = pygame.math.Vector2(spawn_position_tuple[0], spawn_position_tuple[1])
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel = pygame.math.Vector2(0, 0) # Reset velocity
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7) # Reset accel
        
        # Reset health and status flags
        self.current_health = self.max_health
        self.is_dead = False
        self.death_animation_finished = False
        self.is_taking_hit = False
        self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True # Default to facing right
        
        # Reset any lingering timers or cooldowns
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0; self.fireball_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0 if self.facing_right else -1.0, 0.0)

        # Ensure visual state is reset (e.g., if player image was faded out or alpha changed)
        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255: # If image is transparent
            self.image.set_alpha(255) # Make fully opaque
        
        self.set_state('idle') # Set to a neutral, stable initial state
        print(f"DEBUG Player (reset_state P{self.player_id}): Reset complete. Pos: {self.pos}, HP: {self.current_health}") # DEBUG

########## END OF FILE: player.py ##########