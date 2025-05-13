# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling movement, animations, states, and interactions.
"""
# version 1.00000.6 (refining death physics, print limiter, lava freeze)
import pygame
import os
import sys
import math
import time # For PrintLimiter

# Import necessary components from other modules
import constants as C # Use constants with C. prefix
from assets import load_all_player_animations # Import the animation loader
from tiles import Lava # Import Lava for type checking in hazard collision

# --- Print Limiter Utility ---
class PrintLimiter:
    def __init__(self, default_limit=5, default_period=2.0):
        self.counts = {}
        self.timestamps = {}
        self.default_limit = default_limit
        self.default_period = default_period
        self.globally_suppressed = {}

    def can_print(self, message_key, limit=None, period=None):
        limit = limit if limit is not None else self.default_limit
        period = period if period is not None else self.default_period
        current_time = time.time()
        
        if message_key not in self.timestamps:
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 0
            self.globally_suppressed[message_key] = False

        if current_time - self.timestamps[message_key] > period:
            self.timestamps[message_key] = current_time
            self.counts[message_key] = 0
            self.globally_suppressed[message_key] = False

        if self.counts[message_key] < limit:
            self.counts[message_key] += 1
            return True
        elif not self.globally_suppressed[message_key]:
            print(f"[PrintLimiter] Suppressing further prints for '{message_key}' for {period:.1f}s (limit: {limit})")
            self.globally_suppressed[message_key] = True
            return False
        return False

class Player(pygame.sprite.Sprite):
    # Class-level limiter for messages that might be common across instances or general warnings
    print_limiter = PrintLimiter(default_limit=3, default_period=5.0)

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True 
        # self.instance_print_limiter = PrintLimiter(default_limit=5, default_period=2.0) # Per-instance if needed

        if self.player_id == 1: asset_folder = 'characters/player1'
        elif self.player_id == 2: asset_folder = 'characters/player2'
        else:
            asset_folder = 'characters/player1'
            if Player.print_limiter.can_print(f"player_unrecognized_id_{self.player_id}"):
                print(f"Warning: Player {self.player_id} has an unrecognized ID. Defaulting to player1 assets.")

        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)

        if self.animations is None:
            print(f"CRITICAL Player {self.player_id} Init Error: Failed to load critical animations from {asset_folder}.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.is_dead = True; self._valid_init = False; return

        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError):
            self.standard_height = 60
            if Player.print_limiter.can_print(f"player_{self.player_id}_idle_height_warning"):
                print(f"Warning Player {self.player_id}: Could not get player idle animation height, using default {self.standard_height}.")


        self._last_facing = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()

        idle_anim = self.animations.get('idle')
        if idle_anim and len(idle_anim) > 0: self.image = idle_anim[0]
        else:
            self.image = pygame.Surface((30,40)); self.image.fill(C.RED)
            print(f"CRITICAL Player {self.player_id}: Missing or empty 'idle' animation during init.")
            self._valid_init = False; return

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = True; self.on_ground = False; self.on_ladder = False
        self.can_grab_ladder = False; self.touching_wall = 0; self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = getattr(C, 'PLAYER_DASH_DURATION', 150)
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = getattr(C, 'PLAYER_ROLL_DURATION', 300)
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = getattr(C, 'PLAYER_SLIDE_DURATION', 400)
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300; self.attack_type = 0
        self.can_combo = False; self.combo_window = getattr(C, 'PLAYER_COMBO_WINDOW', 150)
        self.wall_climb_timer = 0; self.wall_climb_duration = getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500)
        self.can_wall_jump = False
        self.is_taking_hit = False; self.hit_timer = 0
        self.hit_duration = getattr(C, 'PLAYER_HIT_STUN_DURATION', 300) 
        self.hit_cooldown = getattr(C, 'PLAYER_HIT_COOLDOWN', 600)   
        self.is_dead = False; self.state_timer = 0
        self.max_health = C.PLAYER_MAX_HEALTH; self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30) 

        self.is_trying_to_move_left = False; self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False; self.is_holding_crouch_ability_key = False
        self.death_animation_finished = False


    def set_state(self, new_state):
        if not self._valid_init: return
        original_new_state_request = new_state

        anim_exists = new_state in self.animations and self.animations[new_state]
        if not anim_exists:
            fallback_state = 'fall' if not self.on_ground else 'idle'
            if fallback_state in self.animations and self.animations[fallback_state]: new_state = fallback_state
            else:
                first_available = next((key for key, anim in self.animations.items() if anim), None)
                if not first_available: self._valid_init = False; return
                new_state = first_available
        
        can_change_state = (self.state != new_state or new_state == 'death') and \
                           not (self.is_dead and not self.death_animation_finished and new_state != 'death')

        if can_change_state:
            if Player.print_limiter.can_print(f"player_{self.player_id}_set_state", limit=10, period=1.0):
                print(f"DEBUG Player {self.player_id}: Set State from '{self.state}' to '{new_state}' (Original req: '{original_new_state_request}')")
            self._last_state_for_debug = new_state
            if 'attack' not in new_state and self.is_attacking: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False
            if new_state != 'dash': self.is_dashing = False
            if new_state != 'roll': self.is_rolling = False
            if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: self.is_sliding = False

            self.state = new_state
            self.current_frame = 0
            self.last_anim_update = pygame.time.get_ticks()
            self.state_timer = pygame.time.get_ticks()

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
                anim = self.animations.get(new_state)
                num_frames = len(anim) if anim else 0
                base_frame_duration = C.ANIM_FRAME_DURATION
                if self.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
                    self.attack_duration = num_frames * int(base_frame_duration * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER) if num_frames > 0 else 300
                else:
                    self.attack_duration = num_frames * base_frame_duration if num_frames > 0 else 300
                if new_state in ['attack_nm', 'attack2_nm', 'attack_combo_nm', 'crouch_attack']: self.vel.x = 0
            elif new_state == 'hit':
                 if Player.print_limiter.can_print(f"player_{self.player_id}_enter_hit_state"):
                    print(f"DEBUG Player {self.player_id}: Entering 'hit' state. Vel BEFORE modification: ({self.vel.x:.2f}, {self.vel.y:.2f})")
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 if not self.on_ground and self.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): 
                    self.vel.x *= -0.3 
                    self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4 
                 self.is_attacking = False; self.attack_type = 0
                 # if Player.print_limiter.can_print(f"player_{self.player_id}_set_hit_state_vel"):
                 #    print(f"DEBUG Player {self.player_id}: Set state to 'hit'. Vel AFTER modification (if any): ({self.vel.x:.2f}, {self.vel.y:.2f})")
            elif new_state == 'death' or new_state == 'death_nm':
                 if Player.print_limiter.can_print(f"player_{self.player_id}_enter_death_state"):
                    print(f"DEBUG Player {self.player_id}: Entering 'death' state. Vel BEFORE: ({self.vel.x:.2f}, {self.vel.y:.2f})")
                 self.is_dead = True; self.vel.x = 0
                 if self.vel.y < -1: self.vel.y = 1 # Prevent flying up, start gentle fall
                 self.acc.x = 0
                 if not self.on_ground: self.acc.y = C.PLAYER_GRAVITY 
                 else: self.vel.y = 0; self.acc.y = 0 
                 self.death_animation_finished = False 
                 if Player.print_limiter.can_print(f"player_{self.player_id}_in_death_state_vel"):
                    print(f"DEBUG Player {self.player_id}: In 'death' state. Final vel: ({self.vel.x:.2f}, {self.vel.y:.2f}), Acc: ({self.acc.x:.2f}, {self.acc.y:.2f})")
            elif new_state == 'wall_climb':
                 self.wall_climb_timer = self.state_timer; self.vel.y = C.PLAYER_WALL_CLIMB_SPEED
            elif new_state == 'wall_slide' or new_state == 'wall_hang': self.wall_climb_timer = 0

            self.animate()
        elif not self.is_dead: self._last_state_for_debug = self.state

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        if not self.alive(): return 

        now = pygame.time.get_ticks(); state_key = self.state
        moving_intended_by_input = self.is_trying_to_move_left or self.is_trying_to_move_right

        if self.is_dead: 
            state_key = 'death_nm' if abs(self.vel.x) < 0.5 and abs(self.vel.y) < 1.0 and 'death_nm' in self.animations else 'death'
            if state_key not in self.animations or not self.animations[state_key]: state_key = 'death'
        elif self.is_attacking:
            if self.attack_type == 1: state_key = 'attack' if moving_intended_by_input else 'attack_nm'
            elif self.attack_type == 2: state_key = 'attack2' if moving_intended_by_input else 'attack2_nm'
            elif self.attack_type == 3: state_key = 'attack_combo' if moving_intended_by_input else 'attack_combo_nm'
            elif self.attack_type == 4: state_key = 'crouch_attack'
            if state_key not in self.animations or not self.animations[state_key]:
                 base_state = state_key.replace('_nm', '')
                 state_key = base_state if base_state in self.animations and self.animations[base_state] else 'idle'
        elif self.state == 'wall_climb':
             is_actively_climbing = self.is_holding_climb_ability_key and abs(self.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
             state_key = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
             if state_key not in self.animations or not self.animations[state_key]: state_key = 'wall_climb'
        elif self.state == 'hit': state_key = 'hit'
        elif not self.on_ground and not self.on_ladder and self.touching_wall == 0 and self.state not in ['jump', 'jump_fall_trans'] and self.vel.y > 1:
             state_key = 'fall'
        elif self.on_ladder:
            state_key = 'ladder_climb' if abs(self.vel.y) > 0.1 else 'ladder_idle'
            if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        elif self.is_dashing: state_key = 'dash'
        elif self.is_rolling: state_key = 'roll'
        elif self.is_sliding: state_key = 'slide'
        elif self.state == 'slide_trans_start': state_key = 'slide_trans_start'
        elif self.state == 'slide_trans_end': state_key = 'slide_trans_end'
        elif self.state == 'crouch_trans': state_key = 'crouch_trans'
        elif self.state == 'turn': state_key = 'turn'
        elif self.state == 'jump': state_key = 'jump'
        elif self.state == 'jump_fall_trans': state_key = 'jump_fall_trans'
        elif self.state == 'wall_slide': state_key = 'wall_slide'
        elif self.state == 'wall_hang': state_key = 'wall_hang'
        elif self.on_ground: 
            if self.is_crouching: state_key = 'crouch_walk' if moving_intended_by_input else 'crouch'
            elif moving_intended_by_input: state_key = 'run'
            else: state_key = 'idle'
        
        if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        animation = self.animations.get(state_key)

        if not animation :
            if hasattr(self, 'image') and self.image: self.image.fill(C.RED); return

        current_anim_frame_duration = C.ANIM_FRAME_DURATION
        if self.is_attacking and self.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
            current_anim_frame_duration = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

        if not (self.is_dead and self.death_animation_finished):
            if now - self.last_anim_update > current_anim_frame_duration:
                self.last_anim_update = now; self.current_frame = (self.current_frame + 1)
                if self.current_frame >= len(animation):
                    if self.is_dead: 
                        if Player.print_limiter.can_print(f"player_{self.player_id}_death_anim_done"):
                            print(f"DEBUG Player {self.player_id}: Death Animation FINISHED.")
                        self.current_frame = len(animation) - 1 
                        self.death_animation_finished = True
                        # Player doesn't self.kill() here; main game loop handles game over/removal
                        return 
                    
                    non_looping_states = [
                        'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                        'crouch_attack','dash','roll','slide','hit','turn','jump',
                        'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end']
                    if self.state in non_looping_states:
                         next_s = None; current_s = self.state
                         is_input_moving = self.is_trying_to_move_left or self.is_trying_to_move_right
                         if current_s == 'jump': next_s = 'jump_fall_trans' if 'jump_fall_trans' in self.animations else 'fall'
                         elif current_s == 'jump_fall_trans': next_s = 'fall'
                         elif current_s == 'hit': 
                             next_s = 'fall' if not self.on_ground and not self.on_ladder else 'idle'
                             if Player.print_limiter.can_print(f"player_{self.player_id}_hit_anim_done"):
                                print(f"DEBUG Player {self.player_id}: 'hit' animation finished. Transitioning to: {next_s}. On_ground: {self.on_ground}, VelY: {self.vel.y:.2f}")
                         elif current_s == 'turn': next_s = 'run' if is_input_moving else 'idle'
                         elif 'attack' in current_s:
                              self.is_attacking = False; self.attack_type = 0
                              if self.on_ladder: pass 
                              elif self.is_crouching: next_s = 'crouch'
                              elif not self.on_ground: next_s = 'fall'
                              elif is_input_moving : next_s = 'run'
                              else: next_s = 'idle'
                         elif current_s == 'crouch_trans':
                             self.is_crouching = self.is_holding_crouch_ability_key
                             next_s = 'crouch' if self.is_crouching else 'idle'
                         elif current_s == 'slide_trans_start': next_s = 'slide'
                         elif current_s in ['slide_trans_end', 'slide']:
                             self.is_sliding = False; self.is_crouching = self.is_holding_crouch_ability_key
                             next_s = 'crouch' if self.is_crouching else 'idle'
                         else: 
                              if current_s == 'dash': self.is_dashing = False
                              if current_s == 'roll': self.is_rolling = False
                              if self.on_ladder: pass
                              elif self.is_crouching: next_s = 'crouch'
                              elif not self.on_ground: next_s = 'fall'
                              elif is_input_moving : next_s = 'run'
                              else: next_s = 'idle'
                         if next_s: self.set_state(next_s); return
                         else: self.current_frame = 0
                    else: 
                        self.current_frame = 0
                if self.current_frame >= len(animation): self.current_frame = 0

        if not animation or self.current_frame < 0 or self.current_frame >= len(animation):
            self.current_frame = 0
            if not animation:
                if hasattr(self, 'image') and self.image: self.image.fill(C.RED); return

        new_image = animation[self.current_frame]
        if not self.facing_right: new_image = pygame.transform.flip(new_image, True, False)
        if self.image is not new_image or self._last_facing != self.facing_right:
            old_midbottom = self.rect.midbottom; self.image = new_image
            self.rect = self.image.get_rect(midbottom=old_midbottom); self._last_facing = self.facing_right

    def _process_input_logic(self, keys, events, key_config):
        now = pygame.time.get_ticks()
        input_blocked_by_state = self.is_dead or \
                                 (self.is_taking_hit and now - self.hit_timer < self.hit_duration) 

        if not self._valid_init or input_blocked_by_state :
            self.acc.x = 0
            # if input_blocked_by_state and Player.print_limiter.can_print(f"player_{self.player_id}_input_skip"):
                # print(f"DEBUG Player {self.player_id}: Input processing SKIPPED. is_dead={self.is_dead}, is_taking_hit={self.is_taking_hit}, stun_active={(self.is_taking_hit and now - self.hit_timer < self.hit_duration)}")
            return

        self.is_trying_to_move_left = keys[key_config['left']]
        self.is_trying_to_move_right = keys[key_config['right']]
        self.is_holding_climb_ability_key = keys[key_config['up']]
        self.is_holding_crouch_ability_key = keys[key_config['down']]
        self.acc.x = 0; is_trying_to_move_lr_thistick = False

        can_control_horizontal = not (self.is_dashing or self.is_rolling or self.is_sliding or self.on_ladder or \
                                     (self.is_attacking and self.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or \
                                      self.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang'])
        if can_control_horizontal:
            if self.is_trying_to_move_left and not self.is_trying_to_move_right:
                self.acc.x = -C.PLAYER_ACCEL; is_trying_to_move_lr_thistick = True
                if self.facing_right and self.on_ground and not self.is_crouching and not self.is_attacking and self.state in ['idle','run']: self.set_state('turn')
                self.facing_right = False
            elif self.is_trying_to_move_right and not self.is_trying_to_move_left:
                self.acc.x = C.PLAYER_ACCEL; is_trying_to_move_lr_thistick = True
                if not self.facing_right and self.on_ground and not self.is_crouching and not self.is_attacking and self.state in ['idle','run']: self.set_state('turn')
                self.facing_right = True

        can_initiate_crouch = self.on_ground and not self.on_ladder and not (self.is_dashing or self.is_rolling or self.is_sliding or self.is_attacking or self.state in ['turn','hit','death'])
        if self.is_holding_crouch_ability_key and can_initiate_crouch:
            if not self.is_crouching:
                 self.is_crouching = True; self.is_sliding = False
                 if 'crouch_trans' in self.animations and self.animations['crouch_trans'] and self.state not in ['crouch','crouch_walk','crouch_trans']: self.set_state('crouch_trans')
        elif not self.is_holding_crouch_ability_key and self.is_crouching:
            self.is_crouching = False

        if self.on_ladder:
             self.vel.y = 0
             if self.is_holding_climb_ability_key: self.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
             elif self.is_holding_crouch_ability_key: self.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

        for event in events:
            if event.type == pygame.KEYDOWN:
                 if event.key == key_config['up']:
                      can_jump_action = not self.is_crouching and not self.is_attacking and not self.is_rolling and not self.is_sliding and not self.is_dashing and self.state not in ['turn','hit']
                      if self.on_ground and can_jump_action:
                          self.vel.y = C.PLAYER_JUMP_STRENGTH; self.set_state('jump'); self.on_ground = False
                      elif self.on_ladder and can_jump_action:
                          self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if self.facing_right else -1)
                          self.on_ladder = False; self.set_state('jump')
                      elif self.can_wall_jump and self.touching_wall != 0 and can_jump_action:
                          self.vel.y = C.PLAYER_JUMP_STRENGTH; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-self.touching_wall)
                          self.facing_right = not self.facing_right; self.set_state('jump'); self.can_wall_jump = False; self.touching_wall = 0; self.wall_climb_timer = 0
                 if event.key == key_config['attack1']:
                      can_attack_action = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn','hit']
                      if can_attack_action:
                           self.attack_type = 1 
                           is_moving_for_attack = (self.acc.x !=0 or abs(self.vel.x) > 1.0)
                           if self.is_crouching: self.attack_type = 4; self.set_state('crouch_attack')
                           else: self.set_state('attack' if is_moving_for_attack and 'attack' in self.animations else 'attack_nm')
                 if event.key == key_config['attack2']:
                      can_attack_action = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn','hit']
                      if can_attack_action:
                           is_moving_for_attack = (self.acc.x != 0 or abs(self.vel.x) > 1.0)
                           time_since_attack1_finished_approx = now - (self.attack_timer + self.attack_duration) 
                           is_in_combo_window = (self.attack_type == 1 and not self.is_attacking and 
                                                 time_since_attack1_finished_approx < self.combo_window)
                           if is_in_combo_window and 'attack_combo' in self.animations:
                               self.attack_type = 3 
                               self.set_state('attack_combo' if is_moving_for_attack and 'attack_combo' in self.animations else 'attack_combo_nm')
                           elif self.is_crouching and 'crouch_attack' in self.animations:
                               self.attack_type = 4 
                               self.set_state('crouch_attack')
                           elif 'attack2' in self.animations:
                               self.attack_type = 2 
                               self.set_state('attack2' if is_moving_for_attack and 'attack2' in self.animations else 'attack2_nm')
                           elif self.attack_type == 0: 
                               self.attack_type = 1; self.set_state('attack' if is_moving_for_attack and 'attack' in self.animations else 'attack_nm')
                 if event.key == key_config['dash']:
                      if self.on_ground and not self.is_dashing and not self.is_rolling and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn','hit']: self.set_state('dash')
                 if event.key == key_config['roll']:
                      if self.on_ground and not self.is_rolling and not self.is_dashing and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn','hit']: self.set_state('roll')
                 if event.key == key_config['down']:
                      can_slide_action = self.on_ground and self.state == 'run' and abs(self.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                   not self.is_sliding and not self.is_crouching and not self.is_attacking and \
                                   not self.is_rolling and not self.is_dashing and not self.on_ladder and self.state not in ['turn','hit']
                      if can_slide_action:
                           start_slide_state = 'slide_trans_start' if 'slide_trans_start' in self.animations and self.animations['slide_trans_start'] else 'slide'
                           if start_slide_state in self.animations: self.set_state(start_slide_state)
                 if event.key == key_config['interact']:
                      if self.can_grab_ladder and not self.on_ladder:
                          self.on_ladder = True; self.vel.y=0; self.vel.x=0; self.on_ground=False; self.touching_wall=0; self.can_wall_jump=False; self.wall_climb_timer=0
                          self.set_state('ladder_idle')
                      elif self.on_ladder:
                          self.on_ladder = False; self.set_state('fall' if not self.on_ground else 'idle')

        is_in_manual_override_state = self.is_attacking or self.is_dashing or self.is_rolling or self.is_sliding or self.is_taking_hit or \
                                   self.state in ['jump','turn','death','death_nm','hit','jump_fall_trans',
                                                  'crouch_trans','slide_trans_start','slide_trans_end',
                                                  'wall_climb','wall_climb_nm','wall_hang','wall_slide',
                                                  'ladder_idle','ladder_climb']
        if not is_in_manual_override_state: 
            if self.on_ladder:
                if abs(self.vel.y) > 0.1 : self.set_state('ladder_climb')
                else: self.set_state('ladder_idle')
            elif self.on_ground:
                 if self.is_crouching:
                     target_crouch_state = 'crouch_walk' if is_trying_to_move_lr_thistick and 'crouch_walk' in self.animations else 'crouch'
                     self.set_state(target_crouch_state if target_crouch_state in self.animations else 'idle')
                 elif is_trying_to_move_lr_thistick: self.set_state('run' if 'run' in self.animations else 'idle')
                 else: self.set_state('idle')
            else: 
                 if self.touching_wall != 0:
                     now_wall_time = pygame.time.get_ticks()
                     wall_climb_expired = (self.wall_climb_duration > 0 and self.wall_climb_timer > 0 and
                                           now_wall_time - self.wall_climb_timer > self.wall_climb_duration)
                     if self.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or wall_climb_expired:
                         self.set_state('wall_slide'); self.can_wall_jump = True
                     elif self.is_holding_climb_ability_key and abs(self.vel.x) < 1.0 and not wall_climb_expired and 'wall_climb' in self.animations:
                         self.set_state('wall_climb'); self.can_wall_jump = False
                     else:
                         hang_state = 'wall_hang' if ('wall_hang' in self.animations and self.animations['wall_hang']) else 'wall_slide'
                         self.set_state(hang_state)
                         if self.state == hang_state: self.vel.y = C.PLAYER_WALL_SLIDE_SPEED * 0.1
                         self.can_wall_jump = True
                 elif self.vel.y > 1.0 and self.state not in ['jump','jump_fall_trans']: 
                      self.set_state('fall' if 'fall' in self.animations else 'idle')
                 elif self.state not in ['jump','jump_fall_trans','fall']: 
                      self.set_state('idle')

    def handle_input(self, keys, events):
        key_config = {'left':pygame.K_a,'right':pygame.K_d,'up':pygame.K_w,'down':pygame.K_s,
                      'attack1':pygame.K_v,'attack2':pygame.K_b,'dash':pygame.K_LSHIFT,
                      'roll':pygame.K_LCTRL,'interact':pygame.K_e}
        self._process_input_logic(keys, events, key_config)

    def handle_mapped_input(self, keys, events, key_map):
        self._process_input_logic(keys, events, key_map)

    def update(self, dt, platforms, ladders, hazards, other_players_list, enemies_list):
        if not self._valid_init: return
        
        if self.is_dead: 
            if self.alive() and hasattr(self, 'animate'): 
                if not self.death_animation_finished: 
                    if not self.on_ground: 
                        self.vel.y += self.acc.y 
                        self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
                        self.pos.y += self.vel.y
                        self.rect.bottom = round(self.pos.y)
                        self.on_ground = False 
                        for plat in pygame.sprite.spritecollide(self, platforms, False):
                            if self.vel.y > 0 and self.rect.bottom > plat.rect.top and (self.pos.y - self.vel.y) <= plat.rect.top + 1:
                                self.rect.bottom = plat.rect.top
                                self.on_ground = True; self.vel.y = 0; self.acc.y = 0 
                                self.pos.y = self.rect.bottom; break 
                self.animate() 
            return 

        now = pygame.time.get_ticks()
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            if self.state == 'hit': 
                if Player.print_limiter.can_print(f"player_{self.player_id}_hit_cooldown_end_in_hit"):
                    print(f"DEBUG Player {self.player_id}: Hit COOLDOWN ended during 'hit' state. Transitioning. VelY: {self.vel.y:.2f}")
                self.is_taking_hit = False 
                self.set_state('fall' if not self.on_ground else 'idle') 
            else: 
                self.is_taking_hit = False
        
        self.check_ladder_collisions(ladders)
        if self.on_ladder and not self.can_grab_ladder: 
            self.on_ladder = False; self.set_state('fall' if not self.on_ground else 'idle')

        apply_gravity = not (self.on_ladder or self.state == 'wall_hang' or \
                            (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or \
                             self.is_dashing)
        if apply_gravity: self.vel.y += C.PLAYER_GRAVITY

        apply_horizontal_physics = not (self.is_dashing or self.is_rolling or self.on_ladder or \
                                      (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1))
        if apply_horizontal_physics:
            self.vel.x += self.acc.x
            current_friction = 0
            if self.on_ground and self.acc.x == 0 and not self.is_sliding and self.state != 'slide': current_friction = C.PLAYER_FRICTION
            elif not self.on_ground and not self.is_attacking and self.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']: current_friction = C.PLAYER_FRICTION * 0.2
            elif self.is_sliding or self.state == 'slide': current_friction = C.PLAYER_FRICTION * 0.7
            if current_friction != 0:
                 friction_force = self.vel.x * current_friction
                 if abs(self.vel.x) > 0.1: self.vel.x += friction_force
                 else: self.vel.x = 0
                 if abs(self.vel.x) < 0.5 and (self.is_sliding or self.state == 'slide'):
                     self.is_sliding = False
                     end_slide_state = 'slide_trans_end' if 'slide_trans_end' in self.animations and self.animations['slide_trans_end'] else None
                     if end_slide_state: self.set_state(end_slide_state)
                     else: self.is_crouching = self.is_holding_crouch_ability_key; self.set_state('crouch' if self.is_crouching else 'idle')
            run_limit = C.PLAYER_RUN_SPEED_LIMIT * 0.6 if self.is_crouching and self.state == 'crouch_walk' else C.PLAYER_RUN_SPEED_LIMIT
            if not self.is_dashing and not self.is_rolling and not self.is_sliding and self.state != 'slide':
                self.vel.x = max(-run_limit, min(run_limit, self.vel.x))

        if self.vel.y > 0 and not self.on_ladder: 
            self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))

        self.touching_wall = 0; self.on_ground = False
        self.pos.x += self.vel.x; self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        all_other_characters = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not self] + \
                               [e for e in enemies_list if e and e._valid_init and e.alive()]
        collided_x_char = self.check_character_collisions('x', all_other_characters)
        self.pos.y += self.vel.y; self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        if not collided_x_char: 
            self.check_character_collisions('y', all_other_characters) 

        self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom
        self.check_hazard_collisions(hazards)
        if self.alive() and not self.is_dead:
            attack_targets = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not self] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
            self.check_attack_collisions(attack_targets)
        self.animate()


    def check_platform_collisions(self, direction, platforms):
        collided_wall_side = 0 
        for plat in pygame.sprite.spritecollide(self, platforms, False):
            if direction == 'x':
                if self.vel.x > 0: 
                    self.rect.right = plat.rect.left
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5: 
                        collided_wall_side = 1 
                elif self.vel.x < 0: 
                    self.rect.left = plat.rect.right
                    if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5:
                        collided_wall_side = -1
                self.vel.x = 0; self.pos.x = self.rect.centerx
            elif direction == 'y':
                if self.vel.y > 0: 
                    if self.rect.bottom > plat.rect.top and (self.pos.y - self.vel.y) <= plat.rect.top + 1: 
                        self.rect.bottom = plat.rect.top
                        if not self.on_ground: 
                            self.can_wall_jump=False; self.wall_climb_timer=0 
                            if not self.is_sliding and self.state != 'slide_trans_end': self.vel.x *= 0.8 
                        self.on_ground=True; self.vel.y=0
                elif self.vel.y < 0: 
                    if self.rect.top < plat.rect.bottom and ((self.pos.y - self.rect.height) - self.vel.y) >= plat.rect.bottom -1 :
                         if self.on_ladder: self.on_ladder = False 
                         self.rect.top = plat.rect.bottom; self.vel.y=0
                self.pos.y = self.rect.bottom 
        if direction == 'x' and collided_wall_side != 0 and not self.on_ground and not self.on_ladder:
             self.touching_wall = collided_wall_side
             self.can_wall_jump = not (self.state == 'wall_climb' and self.is_holding_climb_ability_key)


    def check_ladder_collisions(self, ladders):
        if not self._valid_init: return
        check_rect_ladder = self.rect.inflate(-self.rect.width * 0.6, -self.rect.height * 0.1) 
        self.can_grab_ladder = False
        for ladder in pygame.sprite.spritecollide(self, ladders, False, collided=lambda p,l: check_rect_ladder.colliderect(l.rect)):
            if abs(self.rect.centerx - ladder.rect.centerx) < ladder.rect.width * 0.7 and \
               ladder.rect.top < self.rect.centery < ladder.rect.bottom : 
                  self.can_grab_ladder = True; break


    def check_character_collisions(self, direction, characters_list):
        if not self._valid_init or self.is_dead or not self.alive(): return False
        collision_occurred_this_frame = False
        for char_other in characters_list:
            if char_other is self: continue 
            if not (char_other and hasattr(char_other, '_valid_init') and char_other._valid_init and \
                    hasattr(char_other, 'is_dead') and not char_other.is_dead and char_other.alive()):
                continue 

            if self.rect.colliderect(char_other.rect):
                collision_occurred_this_frame = True
                bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                if direction == 'x':
                    push_dir = -1 if self.rect.centerx < char_other.rect.centerx else 1
                    if push_dir == -1: self.rect.right = char_other.rect.left
                    else: self.rect.left = char_other.rect.right
                    self.vel.x = push_dir * bounce_vel
                    if hasattr(char_other, 'vel'): char_other.vel.x = -push_dir * bounce_vel
                    if hasattr(char_other, 'pos') and hasattr(char_other, 'rect'): 
                        char_other.pos.x += -push_dir 
                        char_other.rect.centerx = round(char_other.pos.x)
                    self.pos.x = self.rect.centerx
                elif direction == 'y':
                    if self.vel.y > 0 and self.rect.bottom > char_other.rect.top and self.rect.centery < char_other.rect.centery:
                        self.rect.bottom = char_other.rect.top; self.on_ground=True; self.vel.y=0
                    elif self.vel.y < 0 and self.rect.top < char_other.rect.bottom and self.rect.centery > char_other.rect.centery:
                        self.rect.top = char_other.rect.bottom; self.vel.y=0
                    self.pos.y = self.rect.bottom
        return collision_occurred_this_frame

    def check_hazard_collisions(self, hazards):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown): 
            return
            
        damaged_this_frame = False
        feet_check_point = (self.rect.centerx, self.rect.bottom - 2) 

        for hazard in hazards: 
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(feet_check_point):
                if not damaged_this_frame: 
                    if Player.print_limiter.can_print(f"player_{self.player_id}_lava_touch"):
                        print(f"DEBUG Player {self.player_id}: Touched LAVA at {feet_check_point}. Player rect: {self.rect}, Lava rect: {hazard.rect}. Current state: {self.state}, VelY: {self.vel.y:.2f}")
                    self.take_damage(C.LAVA_DAMAGE) 
                    damaged_this_frame = True 
                    if not self.is_dead: 
                         self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 
                         push_dir = 1 if self.rect.centerx < hazard.rect.centerx else -1
                         self.vel.x = -push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.5 
                         self.on_ground = False 
                         self.on_ladder = False 
                         if Player.print_limiter.can_print(f"player_{self.player_id}_lava_bounce"):
                            print(f"DEBUG Player {self.player_id}: Bounced from LAVA. New vel: ({self.vel.x:.2f}, {self.vel.y:.2f}). State after take_damage will be '{self.state}'")
                    break 

    def check_attack_collisions(self, targets_list):
        if not self._valid_init or not self.is_attacking or self.is_dead or not self.alive(): return
        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery + (-10 if self.is_crouching else 0)
        now = pygame.time.get_ticks()
        for target in targets_list:
            if target is self: continue
            if not (target and hasattr(target, '_valid_init') and target._valid_init and \
                    hasattr(target, 'is_dead') and not target.is_dead and target.alive()): continue
            can_be_damaged = True
            if hasattr(target, 'is_taking_hit') and hasattr(target, 'hit_timer') and hasattr(target, 'hit_cooldown'):
                if target.is_taking_hit and (now - target.hit_timer < target.hit_cooldown):
                    can_be_damaged = False
            if can_be_damaged and self.attack_hitbox.colliderect(target.rect):
                if hasattr(target, 'take_damage') and callable(target.take_damage):
                    damage_to_deal = C.PLAYER_ATTACK1_DAMAGE 
                    if self.attack_type == 1: damage_to_deal = C.PLAYER_ATTACK1_DAMAGE
                    elif self.attack_type == 2: damage_to_deal = C.PLAYER_ATTACK2_DAMAGE
                    elif self.attack_type == 3: damage_to_deal = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif self.attack_type == 4: damage_to_deal = C.PLAYER_CROUCH_ATTACK_DAMAGE
                    if damage_to_deal > 0: target.take_damage(damage_to_deal)

    def take_damage(self, amount):
        now = pygame.time.get_ticks()
        if Player.print_limiter.can_print(f"player_{self.player_id}_take_damage_call", limit=10, period=1.0):
            print(f"DEBUG Player {self.player_id}: take_damage({amount}) called. HP: {self.current_health}, is_dead: {self.is_dead}, alive: {self.alive()}, is_taking_hit: {self.is_taking_hit}")
        
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown): 
            if Player.print_limiter.can_print(f"player_{self.player_id}_damage_ignored", limit=3, period=1.0):
                print(f"DEBUG Player {self.player_id}: Damage IGNORED. Conditions: is_dead={self.is_dead}, alive={self.alive()}, is_taking_hit={self.is_taking_hit}, cooldown_active={(self.is_taking_hit and now - self.hit_timer < self.hit_cooldown)}")
            return

        if Player.print_limiter.can_print(f"player_{self.player_id}_damage_details", limit=10, period=1.0):
            print(f"DEBUG Player {self.player_id}: Taking {amount} damage. Old HP: {self.current_health}")
        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        if Player.print_limiter.can_print(f"player_{self.player_id}_health_update", limit=10, period=1.0):
            print(f"DEBUG Player {self.player_id}: New HP: {self.current_health}/{self.max_health}")

        if self.current_health <= 0:
            if not self.is_dead: 
                if Player.print_limiter.can_print(f"player_{self.player_id}_setting_death"):
                    print(f"DEBUG Player {self.player_id}: Health <= 0. Setting state to death.")
                self.set_state('death') 
        else: 
            if not (self.state == 'hit' and now - self.state_timer < self.hit_duration):
                 if Player.print_limiter.can_print(f"player_{self.player_id}_setting_hit_after_damage"):
                    print(f"DEBUG Player {self.player_id}: Setting state to 'hit' after taking damage.")
                 self.set_state('hit') 

    def self_inflict_damage(self, amount):
        if not self._valid_init or self.is_dead or not self.alive(): return
        print(f"Player {self.player_id} self-inflicted {amount} damage. HP before: {self.current_health}")
        self.take_damage(amount)
        print(f"Player {self.player_id} HP after self-inflict: {self.current_health}/{self.max_health}")

    def heal_to_full(self):
        if not self._valid_init: return
        if self.is_dead and self.current_health <=0 : return
        self.current_health = self.max_health
        print(f"Player {self.player_id} healed to full: {self.current_health}/{self.max_health}")
        if self.is_taking_hit: self.is_taking_hit = False 
        if self.state == 'hit': self.set_state('idle')

    def reset_state(self, spawn_pos):
        if not self._valid_init: 
            print(f"Player {self.player_id} cannot reset, _valid_init is False.")
            return
        print(f"Player {self.player_id}: RESETTING STATE to spawn {spawn_pos}")
        self.pos = pygame.math.Vector2(spawn_pos[0], spawn_pos[1])
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)
        self.current_health = self.max_health; self.is_dead = False; self.is_taking_hit = False
        self.is_attacking = False; self.attack_type = 0; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True
        self.death_animation_finished = False 
        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255) 
        self.set_state('idle')

    def get_network_data(self):
        return {'pos': (self.pos.x, self.pos.y), 'vel': (self.vel.x, self.vel.y), 'state': self.state,
                'facing_right': self.facing_right, 'current_health': self.current_health, 'is_dead': self.is_dead,
                'is_attacking': self.is_attacking, 'attack_type': self.attack_type,
                'current_frame': self.current_frame, 'last_anim_update': self.last_anim_update,
                'player_id': self.player_id, '_valid_init': self._valid_init,
                'death_animation_finished': self.death_animation_finished
               }

    def set_network_data(self, data): 
        if data is None: return
        self._valid_init = data.get('_valid_init', self._valid_init)
        if not self._valid_init:
            if self.alive(): self.kill(); return
        self.pos.x, self.pos.y = data.get('pos', (self.pos.x, self.pos.y))
        self.vel.x, self.vel.y = data.get('vel', (self.vel.x, self.vel.y))
        new_state = data.get('state', self.state)
        self.is_attacking = data.get('is_attacking', self.is_attacking)
        self.attack_type = data.get('attack_type', self.attack_type)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)
        new_is_dead = data.get('is_dead', self.is_dead)
        if new_is_dead and not self.is_dead:
            self.is_dead = True; self.current_health = 0
            self.set_state('death')
        elif not new_is_dead and self.is_dead: 
            self.is_dead = False; self.death_animation_finished = False
            if self.state in ['death', 'death_nm']: self.set_state('idle')
        else: self.is_dead = new_is_dead
        if self.state != new_state and not (self.is_dead and new_state in ['death', 'death_nm']):
             self.set_state(new_state)
        else:
            self.current_frame = data.get('current_frame', self.current_frame)
            self.last_anim_update = data.get('last_anim_update', self.last_anim_update)
        self.facing_right = data.get('facing_right', self.facing_right)
        self.current_health = data.get('current_health', self.current_health) 
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        if self._valid_init and self.alive(): self.animate()

    def handle_network_input(self, input_data_dict): 
        if not self._valid_init or self.is_dead or not self.alive(): return
        self.acc.x = 0
        is_trying_to_move_left_net = input_data_dict.get('left_held', False)
        is_trying_to_move_right_net = input_data_dict.get('right_held', False)
        can_control_horizontal_net = not (self.is_dashing or self.is_rolling or self.is_sliding or self.on_ladder or \
                                     (self.is_attacking and self.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or \
                                      self.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang'])
        new_facing_right = self.facing_right
        if can_control_horizontal_net:
            if is_trying_to_move_left_net and not is_trying_to_move_right_net:
                self.acc.x = -C.PLAYER_ACCEL; new_facing_right = False
            elif is_trying_to_move_right_net and not is_trying_to_move_left_net:
                self.acc.x = C.PLAYER_ACCEL; new_facing_right = True
        if self.on_ground and self.state in ['idle', 'run'] and not self.is_attacking and self.facing_right != new_facing_right:
            self.facing_right = new_facing_right; self.set_state('turn')
        else: self.facing_right = new_facing_right
        now = pygame.time.get_ticks()
        can_act_net = not self.is_attacking and not self.is_dashing and not self.is_rolling and \
                      not self.is_sliding and not self.on_ladder and self.state not in ['turn','hit']
        if input_data_dict.get('attack1_pressed_event', False) and can_act_net:
            self.attack_type = 4 if self.is_crouching else 1
            self.set_state('crouch_attack' if self.is_crouching else ('attack' if (is_trying_to_move_left_net or is_trying_to_move_right_net) else 'attack_nm'))
        if input_data_dict.get('attack2_pressed_event', False) and can_act_net:
            self.attack_type = 4 if self.is_crouching else 2
            self.set_state('crouch_attack' if self.is_crouching else ('attack2' if (is_trying_to_move_left_net or is_trying_to_move_right_net) else 'attack2_nm'))
        if input_data_dict.get('jump_intent', False) and can_act_net and not self.is_crouching:
             if self.on_ground: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.set_state('jump'); self.on_ground = False
        if input_data_dict.get('dash_pressed_event', False) and self.on_ground and can_act_net and not self.is_crouching: self.set_state('dash')
        if input_data_dict.get('roll_pressed_event', False) and self.on_ground and can_act_net and not self.is_crouching: self.set_state('roll')

    def get_input_state(self, current_keys, current_events, key_map_for_player=None):
        input_state = {'left_held': False, 'right_held': False, 'up_held': False, 'down_held': False,
                       'attack1_pressed_event': False, 'attack2_pressed_event': False,
                       'dash_pressed_event': False, 'roll_pressed_event': False,
                       'interact_pressed_event': False, 'jump_intent': False}
        active_key_map = key_map_for_player or \
                         {'left':pygame.K_a,'right':pygame.K_d,'up':pygame.K_w,'down':pygame.K_s,
                          'attack1':pygame.K_v,'attack2':pygame.K_b,'dash':pygame.K_LSHIFT,
                          'roll':pygame.K_LCTRL,'interact':pygame.K_e}
        input_state['left_held'] = current_keys[active_key_map['left']]
        input_state['right_held'] = current_keys[active_key_map['right']]
        input_state['up_held'] = current_keys[active_key_map['up']]
        input_state['down_held'] = current_keys[active_key_map['down']]
        for event in current_events:
            if event.type == pygame.KEYDOWN:
                if event.key == active_key_map.get('attack1'): input_state["attack1_pressed_event"] = True
                if event.key == active_key_map.get('attack2'): input_state["attack2_pressed_event"] = True
                if event.key == active_key_map.get('dash'): input_state["dash_pressed_event"] = True
                if event.key == active_key_map.get('roll'): input_state["roll_pressed_event"] = True
                if event.key == active_key_map.get('interact'): input_state["interact_pressed_event"] = True
                if event.key == active_key_map.get('up'): input_state["jump_intent"] = True
        return input_state