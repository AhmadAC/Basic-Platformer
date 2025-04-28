# -*- coding: utf-8 -*-
"""
Defines the Player class, handling movement, animations, states, and interactions.
"""
import pygame
import os
import sys
import math

# Import necessary components from other modules
import constants as C # Use constants with C. prefix
from assets import load_all_player_animations # Import the animation loader
from tiles import Lava # Import Lava for type checking in hazard collision

class Player(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y):
        super().__init__()

        # --- Load Animations ---
        self.animations = load_all_player_animations(relative_asset_folder='characters/player1')
        if self.animations is None:
            print("Player Init Error: Failed to load critical animations.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.is_dead = True
            self._valid_init = False
            return
        else:
             self._valid_init = True

        # Store the height of a standard frame (e.g., idle) for consistent UI positioning
        try:
            self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError):
            print("Warning: Could not get player idle animation height, using default.")
            self.standard_height = 60 # Provide a fallback default height

        # Internal state trackers
        self._last_facing = True # True = Right
        self._last_state_for_debug = "init"

        # Initialize player attributes using Constants
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()
        self.image = self.animations.get(self.state, self.animations['idle'])[0]
        self.rect = self.image.get_rect(midbottom=(start_x, start_y))

        self.pos = pygame.math.Vector2(start_x, start_y)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)

        self.facing_right = True
        self.on_ground = False
        self.on_ladder = False
        self.can_grab_ladder = False
        self.touching_wall = 0 # 0=None, -1=Left, 1=Right
        self.is_crouching = False
        self.is_dashing = False
        self.dash_timer = 0
        self.dash_duration = 150 # ms
        self.is_rolling = False
        self.roll_timer = 0
        self.roll_duration = 300 # ms
        self.is_sliding = False
        self.slide_timer = 0
        self.slide_duration = 400 # ms
        self.is_attacking = False
        self.attack_timer = 0
        self.attack_duration = 300 # Depends on attack anim
        self.attack_type = 0 # 0: none, 1: attack1, 2: attack2, 3: combo, 4: crouch_attack
        self.can_combo = False
        self.combo_window = 150 # ms
        self.wall_climb_timer = 0
        self.wall_climb_duration = 500 # ms
        self.can_wall_jump = False
        self.is_taking_hit = False
        self.hit_timer = 0
        self.hit_duration = 400 # ms (Duration of hit stun/animation)
        self.hit_cooldown = 600 # ms (Invincibility time after getting hit)

        self.is_dead = False
        self.state_timer = 0 # Time the current state was entered

        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health

        self.attack_hitbox = pygame.Rect(0, 0, 45, 30)


    def set_state(self, new_state):
        if not self._valid_init: return

        # Ensure the target state animation exists
        if new_state in ['ladder_idle', 'ladder_climb'] and new_state not in self.animations:
             new_state = 'idle' # Fallback if ladder anims missing

        # Check if the state exists in the loaded animations dictionary
        if new_state not in self.animations:
             # If the specific state is missing, try a general fallback like 'idle' or 'fall'
             print(f"Warning Player: Animation state '{new_state}' not found in loaded animations.")
             if not self.on_ground: new_state = 'fall' # Default to fall if in air
             else: new_state = 'idle' # Default to idle if on ground

             # Check again if the fallback exists
             if new_state not in self.animations:
                 print(f"CRITICAL ERROR Player: Fallback state '{new_state}' also missing!")
                 new_state = list(self.animations.keys())[0] # Fallback to the very first available animation key
                 if not new_state: return # No animations loaded at all


        # Check if the animation list for the state is empty
        if not self.animations[new_state]:
            print(f"Warning Player: Animation list for state '{new_state}' is empty.")
            # Handle empty list case, e.g., by falling back to idle
            if new_state != 'idle' and 'idle' in self.animations and self.animations['idle']:
                new_state = 'idle'
            else:
                # If idle is also empty or doesn't exist, this is critical
                print(f"CRITICAL ERROR Player: Cannot set state to '{new_state}' (empty list) and cannot fallback to 'idle'.")
                return # Avoid proceeding

        # Proceed with state change if valid state and animation found
        if self.state != new_state and not self.is_dead:
            self._last_state_for_debug = new_state

            # Reset flags and handle state entry logic
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'dash': self.is_dashing = False
            if new_state != 'roll': self.is_rolling = False
            if new_state != 'slide' and 'slide_trans' not in new_state: self.is_sliding = False
            if new_state != 'hit': self.is_taking_hit = False

            self.state = new_state
            self.current_frame = 0
            self.last_anim_update = pygame.time.get_ticks()
            self.state_timer = pygame.time.get_ticks()

            # Handle specific state entry logic
            if new_state == 'dash':
                self.is_dashing = True; self.dash_timer = self.state_timer
                self.vel.x = C.PLAYER_DASH_SPEED * (1 if self.facing_right else -1); self.vel.y = 0
            elif new_state == 'roll':
                 self.is_rolling = True; self.roll_timer = self.state_timer
                 if abs(self.vel.x) < C.PLAYER_ROLL_SPEED / 2: self.vel.x = C.PLAYER_ROLL_SPEED * (1 if self.facing_right else -1)
                 elif abs(self.vel.x) < C.PLAYER_ROLL_SPEED: self.vel.x += (C.PLAYER_ROLL_SPEED / 3) * (1 if self.facing_right else -1)
                 self.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, self.vel.x))
            elif new_state == 'slide' or new_state == 'slide_trans_start':
                 self.is_sliding = True; self.slide_timer = self.state_timer
                 if abs(self.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if self.facing_right else -1)
            elif 'attack' in new_state:
                self.is_attacking = True; self.attack_timer = self.state_timer
                anim = self.animations.get(new_state) # Get animation list for the state
                # Ensure anim is not None and has frames before calculating duration
                self.attack_duration = len(anim) * C.ANIM_FRAME_DURATION if anim else 300
                if new_state in ['attack_nm', 'attack2_nm', 'attack_combo_nm', 'crouch_attack']: self.vel.x = 0
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.3; self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4
                 self.is_attacking = False
            elif new_state == 'death' or new_state == 'death_nm':
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc = pygame.math.Vector2(0, 0); self.current_health = 0
            elif new_state == 'wall_climb':
                 self.wall_climb_timer = self.state_timer; self.vel.y = C.PLAYER_WALL_CLIMB_SPEED
            elif new_state == 'wall_slide' or new_state == 'wall_hang':
                 self.wall_climb_timer = 0

            self.animate() # Update visual immediately
        elif not self.is_dead:
             self._last_state_for_debug = self.state


    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return

        now = pygame.time.get_ticks()
        state_key = self.state
        keys = pygame.key.get_pressed()

        # Determine specific animation key based on state and movement
        if self.is_attacking:
            moving = keys[pygame.K_a] or keys[pygame.K_d]
            if self.attack_type == 1: state_key = 'attack' if moving else 'attack_nm'
            elif self.attack_type == 2: state_key = 'attack2' if moving else 'attack2_nm'
            elif self.attack_type == 3: state_key = 'attack_combo' if moving else 'attack_combo_nm'
            elif self.attack_type == 4: state_key = 'crouch_attack'
            # Fallback if specific moving/nm version missing
            if state_key not in self.animations or not self.animations[state_key]:
                 base_state = state_key.replace('_nm', '')
                 state_key = base_state if base_state in self.animations and self.animations[base_state] else 'idle'
        elif self.state == 'wall_climb':
             state_key = 'wall_climb_nm' if (not keys[pygame.K_w] or abs(self.vel.y - C.PLAYER_WALL_CLIMB_SPEED) > 0.1) else 'wall_climb'
             if state_key not in self.animations or not self.animations[state_key]: state_key = 'wall_climb' # Fallback to moving climb
        elif self.state == 'death':
             state_key = 'death_nm' if abs(self.vel.x) < 0.5 and abs(self.vel.y) < 1.0 else 'death'
             if state_key not in self.animations or not self.animations[state_key]: state_key = 'death' # Fallback to moving death
        elif self.state == 'hit': state_key = 'hit'
        elif not self.on_ground and not self.on_ladder and self.touching_wall == 0 and self.state not in ['jump', 'jump_fall_trans'] and self.vel.y > 1:
             state_key = 'fall' # Override other ground states if falling

        # Ensure the final state_key exists and has animations
        if state_key not in self.animations or not self.animations[state_key]:
             state_key = 'idle' # Ultimate fallback
             if state_key not in self.animations or not self.animations[state_key]:
                 # If idle is STILL missing, we have a critical problem handled in __init__
                 if hasattr(self, 'image') and self.image: self.image.fill(C.RED) # Draw placeholder
                 return # Cannot animate

        animation = self.animations[state_key] # Now guaranteed to exist and be non-empty

        # Advance Frame
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1)

            # Animation End Handling
            if self.current_frame >= len(animation):
                # Non-looping actions transition
                non_looping_states = [
                    'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                    'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                    'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end']
                if self.state in non_looping_states:
                     next_state = None
                     current_state = self.state # Store before potentially changing

                     if current_state == 'jump': next_state = 'jump_fall_trans' if 'jump_fall_trans' in self.animations else 'fall'
                     elif current_state == 'jump_fall_trans': next_state = 'fall'
                     elif current_state == 'hit':
                          # Flag reset based on cooldown timer in update()
                          if self.on_ladder: pass # Stay on ladder?
                          elif not self.on_ground: next_state = 'fall'
                          else: next_state = 'idle'
                     elif current_state == 'turn': next_state = 'run' if keys[pygame.K_a] or keys[pygame.K_d] else 'idle'
                     elif 'attack' in current_state:
                          self.is_attacking = False; self.attack_type = 0 # Reset attack flags
                          if self.on_ladder: pass
                          elif self.is_crouching: next_state = 'crouch'
                          elif not self.on_ground: next_state = 'fall'
                          elif keys[pygame.K_a] or keys[pygame.K_d]: next_state = 'run'
                          else: next_state = 'idle'
                     elif current_state == 'crouch_trans': next_state = 'crouch' if keys[pygame.K_s] else 'idle'; self.is_crouching = keys[pygame.K_s]
                     elif current_state == 'slide_trans_start': next_state = 'slide'
                     elif current_state == 'slide_trans_end' or current_state == 'slide':
                         self.is_sliding = False
                         next_state = 'crouch' if keys[pygame.K_s] else 'idle'; self.is_crouching = keys[pygame.K_s]
                     else: # For dash, roll end
                          if current_state == 'dash': self.is_dashing = False
                          if current_state == 'roll': self.is_rolling = False
                          if self.on_ladder: pass
                          elif self.is_crouching: next_state = 'crouch'
                          elif not self.on_ground: next_state = 'fall'
                          elif keys[pygame.K_a] or keys[pygame.K_d]: next_state = 'run'
                          else: next_state = 'idle'

                     # Set the determined next state if one was found
                     if next_state:
                         self.set_state(next_state)
                         # We return here because set_state calls animate again, preventing double frame advance
                         return
                     else:
                         # If no next state defined for a non-looping anim, loop it? Or force idle?
                         self.current_frame = 0 # Default to looping if no transition

                # Death animation holds last frame
                elif self.is_dead:
                    self.current_frame = len(animation) - 1
                # Looping animations (idle, run, fall, crouch, wall_slide, etc.)
                else:
                    self.current_frame = 0

            # Final frame index check (safety)
            if self.current_frame >= len(animation):
                 self.current_frame = 0


        # Update Image and Rect
        # Ensure animation is valid and frame index is within bounds
        if not animation or self.current_frame < 0 or self.current_frame >= len(animation):
            # This case should ideally not happen due to checks above, but as a safety net:
            print(f"Warning: Invalid frame index ({self.current_frame}) for state '{state_key}' (len {len(animation)}). Using frame 0.")
            self.current_frame = 0
            # If animation is somehow still invalid, use placeholder image
            if not animation:
                if hasattr(self, 'image') and self.image: self.image.fill(C.RED)
                return # Cannot proceed with image update

        new_image = animation[self.current_frame]
        current_facing_is_right = self.facing_right
        if not current_facing_is_right:
            new_image = pygame.transform.flip(new_image, True, False)

        # Optimization: only update image and rect if necessary
        if self.image is not new_image or self._last_facing != current_facing_is_right:
            old_midbottom = self.rect.midbottom
            self.image = new_image
            # Update rect based on the NEW image's dimensions
            self.rect = self.image.get_rect(midbottom=old_midbottom) # Re-anchor
            self._last_facing = current_facing_is_right


    def handle_input(self, keys, events):
        now = pygame.time.get_ticks()
        # Prevent input if dead or still in hit stun (use hit_duration for stun length)
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
             self.acc.x = 0
             return

        # Continuous Key Presses
        self.acc.x = 0
        is_trying_to_move_lr = False
        can_control_horizontal = not (self.is_dashing or self.is_rolling or self.is_sliding or self.on_ladder or \
                                     (self.is_attacking and self.state in ['attack_nm', 'attack2_nm', 'attack_combo_nm', 'crouch_attack']) or \
                                      self.state in ['turn', 'hit', 'death', 'death_nm', 'wall_climb', 'wall_climb_nm', 'wall_hang'])
        if can_control_horizontal:
            pressed_a = keys[pygame.K_a]; pressed_d = keys[pygame.K_d]
            if pressed_a and not pressed_d:
                self.acc.x = -C.PLAYER_ACCEL; is_trying_to_move_lr = True
                if self.facing_right and self.on_ground and not self.is_crouching and not self.is_attacking and self.state in ['idle', 'run']: self.set_state('turn')
                self.facing_right = False
            elif pressed_d and not pressed_a:
                self.acc.x = C.PLAYER_ACCEL; is_trying_to_move_lr = True
                if not self.facing_right and self.on_ground and not self.is_crouching and not self.is_attacking and self.state in ['idle', 'run']: self.set_state('turn')
                self.facing_right = True

        # Crouching (S - Hold)
        can_initiate_crouch = self.on_ground and not self.on_ladder and not (self.is_dashing or self.is_rolling or self.is_sliding or self.is_attacking or self.state in ['turn', 'hit', 'death'])
        if keys[pygame.K_s] and can_initiate_crouch:
            if not self.is_crouching:
                 self.is_crouching = True
                 if self.is_sliding: self.is_sliding = False
                 if 'crouch_trans' in self.animations and self.animations['crouch_trans'] and self.state not in ['crouch', 'crouch_walk', 'crouch_trans']: self.set_state('crouch_trans')
        elif not keys[pygame.K_s] and self.is_crouching:
             self.is_crouching = False # Add ceiling check later if needed

        # Ladder Movement (W/S - Hold, only if on_ladder)
        if self.on_ladder:
             self.vel.y = 0
             if keys[pygame.K_w]: self.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
             elif keys[pygame.K_s]: self.vel.y = C.PLAYER_LADDER_CLIMB_SPEED
             else: self.vel.y = 0

        # Single Key Press Actions (Events)
        for event in events:
            if event.type == pygame.KEYDOWN:
                 # Jump (W)
                 if event.key == pygame.K_w:
                      can_jump = not self.is_crouching and not self.is_attacking and not self.is_rolling and not self.is_sliding and not self.is_dashing and self.state not in ['turn', 'hit']
                      if self.on_ground and can_jump: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.set_state('jump'); self.on_ground = False
                      elif self.on_ladder: self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if self.facing_right else -1); self.on_ladder = False; self.set_state('jump')
                      elif self.can_wall_jump and self.touching_wall != 0: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-self.touching_wall); self.facing_right = not self.facing_right; self.set_state('jump'); self.can_wall_jump = False; self.touching_wall = 0; self.wall_climb_timer = 0
                 # Attack 1 (J)
                 if event.key == pygame.K_j:
                      can_attack = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn', 'hit']
                      if can_attack:
                           if self.is_crouching: self.attack_type = 4; self.set_state('crouch_attack')
                           else: self.attack_type = 1; moving = keys[pygame.K_a] or keys[pygame.K_d]; self.set_state('attack' if moving and 'attack' in self.animations else 'attack_nm')
                 # Attack 2 / Combo (K)
                 if event.key == pygame.K_k:
                      can_attack = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn', 'hit']
                      if can_attack:
                           time_since_attack_state = now - self.state_timer
                           combo_possible = (self.state in ['attack', 'attack_nm'] and self.attack_type == 1 and time_since_attack_state < self.attack_duration + self.combo_window)
                           if combo_possible and 'attack_combo' in self.animations: self.attack_type = 3; moving = keys[pygame.K_a] or keys[pygame.K_d]; self.set_state('attack_combo' if moving and 'attack_combo' in self.animations else 'attack_combo_nm')
                           elif self.is_crouching: self.attack_type = 4; self.set_state('crouch_attack')
                           elif 'attack2' in self.animations: self.attack_type = 2; moving = keys[pygame.K_a] or keys[pygame.K_d]; self.set_state('attack2' if moving and 'attack2' in self.animations else 'attack2_nm')
                           elif self.attack_type == 0: self.attack_type = 1; moving = keys[pygame.K_a] or keys[pygame.K_d]; self.set_state('attack' if moving and 'attack' in self.animations else 'attack_nm')
                 # Dash (LSHIFT)
                 if event.key == pygame.K_LSHIFT:
                      can_dash = self.on_ground and not self.is_dashing and not self.is_rolling and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn', 'hit']
                      if can_dash: self.set_state('dash')
                 # Roll (LCTRL)
                 if event.key == pygame.K_LCTRL:
                      can_roll = self.on_ground and not self.is_rolling and not self.is_dashing and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn', 'hit']
                      if can_roll: self.set_state('roll')
                 # Slide (S - Press)
                 if event.key == pygame.K_s:
                      can_slide = self.on_ground and self.state == 'run' and abs(self.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and not self.is_sliding and not self.is_crouching and not self.is_attacking and not self.is_rolling and not self.is_dashing and not self.on_ladder and self.state not in ['turn', 'hit']
                      if can_slide:
                           start_state = 'slide_trans_start' if 'slide_trans_start' in self.animations and self.animations['slide_trans_start'] else 'slide'
                           if start_state in self.animations: self.set_state(start_state)
                 # Ladder Interaction (E)
                 if event.key == pygame.K_e:
                      if self.can_grab_ladder and not self.on_ladder: self.on_ladder = True; self.vel.y = 0; self.vel.x = 0; self.on_ground = False; self.touching_wall = 0; self.can_wall_jump = False; self.wall_climb_timer = 0
                      elif self.on_ladder: self.on_ladder = False

        # Determine Player State (Automatic state changes)
        is_in_manual_state = self.is_attacking or self.is_dashing or self.is_rolling or self.is_sliding or self.is_taking_hit or \
                             self.state in ['jump', 'turn', 'death', 'death_nm', 'hit', 'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end', 'wall_climb', 'wall_climb_nm', 'wall_hang', 'wall_slide']
        if not is_in_manual_state:
            if self.on_ladder: pass # Ladder state handled by input
            elif self.on_ground:
                 if self.is_crouching:
                     target_state = 'crouch_walk' if is_trying_to_move_lr and 'crouch_walk' in self.animations else 'crouch'
                     if target_state in self.animations: self.set_state(target_state)
                     else: self.set_state('idle')
                 elif is_trying_to_move_lr: self.set_state('run' if 'run' in self.animations else 'idle')
                 else: self.set_state('idle')
            else: # In Air
                 if self.touching_wall != 0: # Wall interaction logic
                     now = pygame.time.get_ticks()
                     climb_expired = (self.wall_climb_duration > 0 and self.wall_climb_timer > 0 and now - self.wall_climb_timer > self.wall_climb_duration)
                     if self.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired: self.set_state('wall_slide'); self.can_wall_jump = True
                     elif keys[pygame.K_w] and abs(self.vel.x) < 1.0 and not climb_expired and 'wall_climb' in self.animations: self.set_state('wall_climb'); self.can_wall_jump = False
                     else:
                         hang_state = 'wall_hang' if ('wall_hang' in self.animations and self.animations['wall_hang']) else 'wall_slide'
                         self.set_state(hang_state)
                         if self.state == hang_state: self.vel.y = C.PLAYER_WALL_SLIDE_SPEED * 0.1
                         self.can_wall_jump = True
                 else: # Regular Air -> Fall state
                     if self.vel.y > 1.0 and self.state not in ['jump', 'jump_fall_trans']:
                          target_state = 'fall' if 'fall' in self.animations else 'idle'
                          if self.state != 'fall': self.set_state(target_state)
                     elif self.state not in ['jump', 'jump_fall_trans', 'fall']:
                          self.set_state('idle')


    def update(self, dt, platforms, ladders, hazards, enemies):
        """ Main update method: physics, collisions, interactions. """
        if not self._valid_init or self.is_dead:
            if self.is_dead: self.animate()
            return

        # Check Hit Stun Cooldown - allows taking damage again after hit_cooldown
        now = pygame.time.get_ticks()
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False # No longer invincible

        self.check_ladder_collisions(ladders)
        if self.on_ladder and not self.can_grab_ladder: self.on_ladder = False

        # --- Physics Calculation ---
        apply_gravity = not (self.on_ladder or self.state == 'wall_hang' or (self.state == 'wall_climb' and self.vel.y == C.PLAYER_WALL_CLIMB_SPEED))
        if apply_gravity: self.vel.y += C.PLAYER_GRAVITY

        apply_horizontal_physics = not (self.is_dashing or self.is_rolling or self.on_ladder or (self.state == 'wall_climb' and self.vel.y == C.PLAYER_WALL_CLIMB_SPEED))
        if apply_horizontal_physics:
            self.vel.x += self.acc.x # Apply acceleration from input
            # Apply friction
            current_friction = 0
            if self.on_ground and self.acc.x == 0 and not self.is_sliding and self.state != 'slide': current_friction = C.PLAYER_FRICTION
            elif not self.on_ground and not self.is_attacking and self.state not in ['wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm']: current_friction = C.PLAYER_FRICTION * 0.2
            elif self.is_sliding or self.state == 'slide': current_friction = C.PLAYER_FRICTION * 0.7
            if current_friction != 0:
                 friction_force = self.vel.x * current_friction
                 if abs(self.vel.x) > 0.1: self.vel.x += friction_force
                 else: self.vel.x = 0 # Stop completely if slow enough
                 # Stop sliding state if friction stops movement
                 if abs(self.vel.x) < 0.5 and (self.is_sliding or self.state == 'slide'):
                     self.is_sliding = False; keys = pygame.key.get_pressed()
                     end_state = 'slide_trans_end' if 'slide_trans_end' in self.animations and self.animations['slide_trans_end'] else None
                     if end_state: self.set_state(end_state)
                     else: self.is_crouching = keys[pygame.K_s]; self.set_state('crouch' if self.is_crouching else 'idle')
            # Apply speed limit
            current_limit = C.PLAYER_RUN_SPEED_LIMIT * 0.6 if self.is_crouching and self.state == 'crouch_walk' else C.PLAYER_RUN_SPEED_LIMIT
            if not self.is_dashing and not self.is_rolling and not self.is_sliding and self.state != 'slide':
                self.vel.x = max(-current_limit, min(current_limit, self.vel.x))
        # Apply terminal velocity
        if self.vel.y > 0 and not self.on_ladder: self.vel.y = min(self.vel.y, 18)

        # --- Collision Detection & Position Update ---
        self.touching_wall = 0; self.on_ground = False

        # Move X, Check Platforms, Check Enemies
        self.pos.x += self.vel.x
        self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        collided_x_enemy = self.check_character_collisions('x', enemies) # Store result

        # Move Y, Check Platforms, Check Enemies
        self.pos.y += self.vel.y
        self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        if not collided_x_enemy: # Only check Y char collision if no X collision occurred
             self.check_character_collisions('y', enemies)

        # Final pos update based on rect changes during collision checks
        self.pos.x = self.rect.centerx
        self.pos.y = self.rect.bottom

        # --- Post-Movement Checks ---
        self.check_hazard_collisions(hazards) # Check AFTER final position is set
        self.check_attack_collisions(enemies)

        self.animate()


    def check_platform_collisions(self, direction, platforms):
        collided_wall_side = 0
        collided_sprites = pygame.sprite.spritecollide(self, platforms, False)
        for plat in collided_sprites:
            if direction == 'x':
                if self.vel.x > 0: # Moving Right
                    self.rect.right = plat.rect.left
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5: collided_wall_side = 1
                    self.vel.x = 0
                elif self.vel.x < 0: # Moving Left
                    self.rect.left = plat.rect.right
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5: collided_wall_side = -1
                    self.vel.x = 0
            elif direction == 'y':
                if self.vel.y > 0: # Moving Down
                    previous_bottom = self.pos.y - self.vel.y
                    if previous_bottom <= plat.rect.top + 1:
                        self.rect.bottom = plat.rect.top
                        if not self.on_ground: self.can_wall_jump = False; self.wall_climb_timer = 0; self.vel.x *= 0.8 # Dampen x on land slightly
                        self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0: # Moving Up
                    previous_top = (self.pos.y - self.rect.height) - self.vel.y
                    if previous_top >= plat.rect.bottom - 1 :
                         if self.on_ladder: self.on_ladder = False
                         self.rect.top = plat.rect.bottom; self.vel.y = 0

        if direction == 'x' and collided_wall_side != 0 and not self.on_ground and not self.on_ladder:
             self.touching_wall = collided_wall_side
             self.can_wall_jump = not (self.state == 'wall_climb' and self.vel.y == C.PLAYER_WALL_CLIMB_SPEED)


    def check_ladder_collisions(self, ladders):
        if not self._valid_init: return
        check_rect = self.rect.inflate(-self.rect.width * 0.6, 0)
        self.can_grab_ladder = False
        collided_ladders = pygame.sprite.spritecollide(self, ladders, False, collided=lambda p, l: check_rect.colliderect(l.rect))
        for ladder in collided_ladders:
            if abs(self.rect.centerx - ladder.rect.centerx) < ladder.rect.width * 0.6 and \
               ladder.rect.top < self.rect.bottom and self.rect.top < ladder.rect.bottom:
                  self.can_grab_ladder = True; break


    def check_character_collisions(self, direction, enemies):
        """ Checks for collisions with enemy sprites and applies bounce. Returns True if collision occurred. """
        if not self._valid_init or self.is_dead: return False
        collided_enemies = pygame.sprite.spritecollide(self, enemies, False)
        collision_occurred = False
        for enemy in collided_enemies:
            if enemy.is_dead: continue
            collision_occurred = True

            if direction == 'x':
                push_dir = 0 # Direction player should be pushed
                if self.vel.x >= 0 and self.rect.centerx < enemy.rect.centerx: # Player moving right or static, hits left side of enemy
                    self.rect.right = enemy.rect.left
                    push_dir = -1
                elif self.vel.x <= 0 and self.rect.centerx > enemy.rect.centerx: # Player moving left or static, hits right side of enemy
                    self.rect.left = enemy.rect.right
                    push_dir = 1

                # If a push direction was determined (collision resolved)
                if push_dir != 0:
                    self.vel.x = push_dir * C.CHARACTER_BOUNCE_VELOCITY
                    # Apply opposite bounce to enemy
                    if hasattr(enemy, 'vel'):
                        enemy.vel.x = -push_dir * C.CHARACTER_BOUNCE_VELOCITY
                        enemy.rect.x += -push_dir # Nudge enemy slightly
                    self.pos.x = self.rect.centerx # Update player pos

            elif direction == 'y':
                # Vertical collision: Player lands on enemy or hits head
                if self.vel.y > 0 and self.rect.bottom > enemy.rect.top: # Moving Down onto Enemy
                    self.rect.bottom = enemy.rect.top
                    self.on_ground = True # Landed on enemy
                    self.vel.y = 0
                elif self.vel.y < 0 and self.rect.top < enemy.rect.bottom: # Moving Up into Enemy
                    self.rect.top = enemy.rect.bottom
                    self.vel.y = 0
                self.pos.y = self.rect.bottom # Update player pos

        return collision_occurred


    def check_hazard_collisions(self, hazards):
        """ Checks for collisions with hazards like Lava using feet check. """
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
             return

        collided_hazards = pygame.sprite.spritecollide(self, hazards, False)
        damaged_this_frame = False
        for hazard in collided_hazards:
            # Precise check: Check if the center-bottom point is inside the hazard rect
            check_point = (self.rect.centerx, self.rect.bottom - 1) # Point just inside bottom edge
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point) and not damaged_this_frame:
                # print(f"DEBUG: Player collided Lava point check. P: {self.rect.bottom} vs L: {hazard.rect.top}-{hazard.rect.bottom}")
                self.take_damage(C.LAVA_DAMAGE)
                damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.7 # Stronger bounce
                     push_dir = 1 if self.rect.centerx < hazard.rect.centerx else -1
                     self.vel.x = -push_dir * 6 # Stronger horizontal push
                     self.on_ground = False # Ensure airborne
                break


    def check_attack_collisions(self, enemies):
        """ Checks if the player's attack hitbox collides with any enemies. """
        if not self._valid_init or not self.is_attacking or self.is_dead: return

        # Position hitbox
        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery + (-10 if self.is_crouching else 0) # Adjust Y if crouching

        hit_enemies = pygame.sprite.spritecollide(self, enemies, False, collided=lambda p, e: self.attack_hitbox.colliderect(e.rect))
        for enemy in hit_enemies:
            if not enemy.is_dead and hasattr(enemy, 'take_damage') and callable(enemy.take_damage):
                 enemy.take_damage(C.PLAYER_ATTACK_DAMAGE)
                 # Add logic here to prevent hitting the same enemy multiple times per swing if needed


    def take_damage(self, amount):
        """ Reduces player health and handles hit/death states. Includes cooldown. """
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            return # Ignore damage if dead or invincible

        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        # print(f"Player took {amount} damage, health: {self.current_health}") # Debug

        if self.current_health <= 0:
            if not self.is_dead: self.set_state('death')
        else:
            # Set hit state only if not already in hit stun animation phase
            if not (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
                 self.set_state('hit') # This sets is_taking_hit = True and hit_timer = now

    # <<< START OF CHANGE >>>
    def heal_to_full(self):
        """ Restores the player's health to its maximum value. """
        if not self._valid_init: return
        self.current_health = self.max_health
        print(f"Debug: Player healed to {self.current_health}/{self.max_health}") # Optional debug output
    # <<< END OF CHANGE >>>
