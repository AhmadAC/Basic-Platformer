# player.py
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
    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id

        asset_folder = 'characters/player1'
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)

        if self.animations is None:
            print(f"Player {self.player_id} Init Error: Failed to load critical animations from {asset_folder}.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.is_dead = True
            self._valid_init = False
            return
        else:
             self._valid_init = True
        try:
            self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError): # Handle if 'idle' or its frames are missing
            print(f"Warning Player {self.player_id}: Could not get player idle animation height, using default.")
            self.standard_height = 60 # Fallback
        except TypeError: # Handle if animations['idle'] is None or not a list
            print(f"Warning Player {self.player_id}: Idle animation data is invalid, using default height.")
            self.standard_height = 60 # Fallback

        self._last_facing = True
        self._last_state_for_debug = "init"
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()
        idle_anim = self.animations.get('idle')
        if idle_anim and len(idle_anim) > 0:
            self.image = idle_anim[0]
        else:
            self.image = pygame.Surface((30,40)); self.image.fill(C.RED) # Fallback image
            print(f"CRITICAL Player {self.player_id}: Missing or empty 'idle' animation during init.")
        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = True
        self.on_ground = False
        self.on_ladder = False
        self.can_grab_ladder = False
        self.touching_wall = 0
        self.is_crouching = False
        self.is_dashing = False
        self.dash_timer = 0
        self.dash_duration = 150
        self.is_rolling = False
        self.roll_timer = 0
        self.roll_duration = 300
        self.is_sliding = False
        self.slide_timer = 0
        self.slide_duration = 400
        self.is_attacking = False
        self.attack_timer = 0
        self.attack_duration = 300
        self.attack_type = 0
        self.can_combo = False
        self.combo_window = 150
        self.wall_climb_timer = 0
        self.wall_climb_duration = 500
        self.can_wall_jump = False
        self.is_taking_hit = False
        self.hit_timer = 0
        self.hit_duration = 400
        self.hit_cooldown = 600
        self.is_dead = False
        self.state_timer = 0
        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30)
        self.is_trying_to_move_left = False
        self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False
        self.is_holding_crouch_ability_key = False

    def set_state(self, new_state):
        if not self._valid_init: return
        if new_state in ['ladder_idle', 'ladder_climb'] and new_state not in self.animations:
             new_state = 'idle'
        if new_state not in self.animations:
             print(f"Warning Player {self.player_id}: Animation state '{new_state}' not found.")
             new_state = 'fall' if not self.on_ground else 'idle'
             if new_state not in self.animations:
                 print(f"CRITICAL ERROR Player {self.player_id}: Fallback state '{new_state}' also missing!")
                 available_keys = list(self.animations.keys())
                 if not available_keys : return
                 new_state = available_keys[0]
        if not self.animations.get(new_state): # Check if list is None or empty
            print(f"Warning Player {self.player_id}: Animation list for state '{new_state}' is empty or None.")
            # Try to find 'idle', if not, first available key, if none, then it's critical.
            new_state_candidate = 'idle' if new_state != 'idle' and 'idle' in self.animations and self.animations['idle'] else None
            if not new_state_candidate:
                available_keys = [k for k,v in self.animations.items() if v] # find first non-empty animation
                if available_keys: new_state_candidate = available_keys[0]

            if not new_state_candidate: # Still no valid animation
                print(f"CRITICAL ERROR Player {self.player_id}: Cannot find any valid animation for fallback. Animations dict: {self.animations.keys()}")
                if hasattr(self, 'image') and self.image: self.image.fill(C.RED) # Show error on player
                self._valid_init = False # Mark as invalid to stop further processing
                return
            new_state = new_state_candidate


        if self.state != new_state and not self.is_dead: # Only change if different and not dead
            self._last_state_for_debug = new_state
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'dash': self.is_dashing = False
            if new_state != 'roll': self.is_rolling = False
            if new_state != 'slide' and 'slide_trans' not in new_state: self.is_sliding = False
            if new_state != 'hit': self.is_taking_hit = False # Reset unless entering hit state

            self.state = new_state
            self.current_frame = 0
            self.last_anim_update = pygame.time.get_ticks()
            self.state_timer = pygame.time.get_ticks()

            # State entry logic
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
                self.is_attacking = True; self.attack_timer = self.state_timer; anim = self.animations.get(new_state)
                self.attack_duration = len(anim) * C.ANIM_FRAME_DURATION if anim else 300
                if new_state in ['attack_nm', 'attack2_nm', 'attack_combo_nm', 'crouch_attack']: self.vel.x = 0
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.3; self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4; self.is_attacking = False
            elif new_state == 'death' or new_state == 'death_nm':
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc = pygame.math.Vector2(0, 0); self.current_health = 0
            elif new_state == 'wall_climb':
                 self.wall_climb_timer = self.state_timer; self.vel.y = C.PLAYER_WALL_CLIMB_SPEED
            elif new_state == 'wall_slide' or new_state == 'wall_hang': self.wall_climb_timer = 0
            self.animate() # Update visual immediately
        elif not self.is_dead: self._last_state_for_debug = self.state # Keep track even if state is same

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        now = pygame.time.get_ticks(); state_key = self.state
        moving_intended = abs(self.acc.x) > C.PLAYER_ACCEL * 0.1
        if self.is_attacking:
            if self.attack_type == 1: state_key = 'attack' if moving_intended else 'attack_nm'
            elif self.attack_type == 2: state_key = 'attack2' if moving_intended else 'attack2_nm'
            elif self.attack_type == 3: state_key = 'attack_combo' if moving_intended else 'attack_combo_nm'
            elif self.attack_type == 4: state_key = 'crouch_attack'
            if state_key not in self.animations or not self.animations[state_key]:
                 base_state = state_key.replace('_nm', '')
                 state_key = base_state if base_state in self.animations and self.animations[base_state] else 'idle'
        elif self.state == 'wall_climb':
             is_actively_climbing = self.is_holding_climb_ability_key and abs(self.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
             state_key = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
             if state_key not in self.animations or not self.animations[state_key]: state_key = 'wall_climb'
        elif self.state == 'death':
             state_key = 'death_nm' if abs(self.vel.x) < 0.5 and abs(self.vel.y) < 1.0 else 'death'
             if state_key not in self.animations or not self.animations[state_key]: state_key = 'death'
        elif self.state == 'hit': state_key = 'hit'
        elif not self.on_ground and not self.on_ladder and self.touching_wall == 0 and self.state not in ['jump', 'jump_fall_trans'] and self.vel.y > 1:
             state_key = 'fall'
        if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        animation = self.animations.get(state_key)
        if not animation :
            if hasattr(self, 'image') and self.image: self.image.fill(C.RED)
            print(f"Player {self.player_id}: Animation list for '{state_key}' empty in animate.")
            return
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now; self.current_frame = (self.current_frame + 1)
            if self.current_frame >= len(animation):
                non_looping = ['attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                               'crouch_attack','dash','roll','slide','hit','turn','jump',
                               'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end']
                if self.state in non_looping:
                     next_s = None; current_s = self.state
                     is_input_moving = self.is_trying_to_move_left or self.is_trying_to_move_right
                     if current_s == 'jump': next_s = 'jump_fall_trans' if 'jump_fall_trans' in self.animations else 'fall'
                     elif current_s == 'jump_fall_trans': next_s = 'fall'
                     elif current_s == 'hit': next_s = 'fall' if not self.on_ground and not self.on_ladder else 'idle'
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
                elif self.is_dead: self.current_frame = len(animation) - 1
                else: self.current_frame = 0
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
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
            self.acc.x = 0; return
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
        elif not self.is_holding_crouch_ability_key and self.is_crouching: self.is_crouching = False
        if self.on_ladder:
             self.vel.y = 0
             if self.is_holding_climb_ability_key: self.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
             elif self.is_holding_crouch_ability_key: self.vel.y = C.PLAYER_LADDER_CLIMB_SPEED
        for event in events:
            if event.type == pygame.KEYDOWN:
                 if event.key == key_config['up']:
                      can_jump = not self.is_crouching and not self.is_attacking and not self.is_rolling and not self.is_sliding and not self.is_dashing and self.state not in ['turn','hit']
                      if self.on_ground and can_jump: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.set_state('jump'); self.on_ground = False
                      elif self.on_ladder: self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if self.facing_right else -1); self.on_ladder = False; self.set_state('jump')
                      elif self.can_wall_jump and self.touching_wall != 0: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-self.touching_wall); self.facing_right = not self.facing_right; self.set_state('jump'); self.can_wall_jump = False; self.touching_wall = 0; self.wall_climb_timer = 0
                 if event.key == key_config['attack1']:
                      can_attack = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn','hit']
                      if can_attack:
                           moving = (self.acc.x !=0)
                           if self.is_crouching: self.attack_type = 4; self.set_state('crouch_attack')
                           else: self.attack_type = 1; self.set_state('attack' if moving and 'attack' in self.animations else 'attack_nm')
                 if event.key == key_config['attack2']:
                      can_attack = not self.is_attacking and not self.is_dashing and not self.is_rolling and not self.is_sliding and not self.on_ladder and self.state not in ['turn','hit']
                      if can_attack:
                           time_since_attack = now - self.state_timer; moving = (self.acc.x != 0)
                           combo = (self.state in ['attack','attack_nm'] and self.attack_type == 1 and time_since_attack < self.attack_duration + self.combo_window)
                           if combo and 'attack_combo' in self.animations: self.attack_type = 3; self.set_state('attack_combo' if moving and 'attack_combo' in self.animations else 'attack_combo_nm')
                           elif self.is_crouching: self.attack_type = 4; self.set_state('crouch_attack')
                           elif 'attack2' in self.animations: self.attack_type = 2; self.set_state('attack2' if moving and 'attack2' in self.animations else 'attack2_nm')
                           elif self.attack_type == 0: self.attack_type = 1; self.set_state('attack' if moving and 'attack' in self.animations else 'attack_nm')
                 if event.key == key_config['dash']:
                      if self.on_ground and not self.is_dashing and not self.is_rolling and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn','hit']: self.set_state('dash')
                 if event.key == key_config['roll']:
                      if self.on_ground and not self.is_rolling and not self.is_dashing and not self.is_attacking and not self.is_crouching and not self.on_ladder and self.state not in ['turn','hit']: self.set_state('roll')
                 if event.key == key_config['down']:
                      can_slide = self.on_ground and self.state == 'run' and abs(self.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and not self.is_sliding and not self.is_crouching and not self.is_attacking and not self.is_rolling and not self.is_dashing and not self.on_ladder and self.state not in ['turn','hit']
                      if can_slide:
                           start_s = 'slide_trans_start' if 'slide_trans_start' in self.animations and self.animations['slide_trans_start'] else 'slide'
                           if start_s in self.animations: self.set_state(start_s)
                 if event.key == key_config['interact']:
                      if self.can_grab_ladder and not self.on_ladder: self.on_ladder = True; self.vel.y=0; self.vel.x=0; self.on_ground=False; self.touching_wall=0; self.can_wall_jump=False; self.wall_climb_timer=0; self.set_state('ladder_idle')
                      elif self.on_ladder: self.on_ladder = False; self.set_state('fall' if not self.on_ground else 'idle')
        is_manual_state = self.is_attacking or self.is_dashing or self.is_rolling or self.is_sliding or self.is_taking_hit or self.state in ['jump','turn','death','death_nm','hit','jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end','wall_climb','wall_climb_nm','wall_hang','wall_slide','ladder_idle','ladder_climb']
        if not is_manual_state:
            if self.on_ladder:
                if abs(self.vel.y) > 0.1 : self.set_state('ladder_climb')
                else: self.set_state('ladder_idle')
            elif self.on_ground:
                 if self.is_crouching:
                     target_s = 'crouch_walk' if is_trying_to_move_lr_thistick and 'crouch_walk' in self.animations else 'crouch'
                     self.set_state(target_s if target_s in self.animations else 'idle')
                 elif is_trying_to_move_lr_thistick: self.set_state('run' if 'run' in self.animations else 'idle')
                 else: self.set_state('idle')
            else: # In Air
                 if self.touching_wall != 0:
                     now_w = pygame.time.get_ticks()
                     climb_exp = (self.wall_climb_duration > 0 and self.wall_climb_timer > 0 and now_w - self.wall_climb_timer > self.wall_climb_duration)
                     if self.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_exp: self.set_state('wall_slide'); self.can_wall_jump = True
                     elif self.is_holding_climb_ability_key and abs(self.vel.x) < 1.0 and not climb_exp and 'wall_climb' in self.animations: self.set_state('wall_climb'); self.can_wall_jump = False
                     else:
                         hang_s = 'wall_hang' if ('wall_hang' in self.animations and self.animations['wall_hang']) else 'wall_slide'
                         self.set_state(hang_s)
                         if self.state == hang_s: self.vel.y = C.PLAYER_WALL_SLIDE_SPEED * 0.1
                         self.can_wall_jump = True
                 elif self.vel.y > 1.0 and self.state not in ['jump','jump_fall_trans']:
                      self.set_state('fall' if 'fall' in self.animations else 'idle')
                 elif self.state not in ['jump','jump_fall_trans','fall']: self.set_state('idle')

    def handle_input(self, keys, events):
        key_config = {'left':pygame.K_a,'right':pygame.K_d,'up':pygame.K_w,'down':pygame.K_s,
                      'attack1':pygame.K_v,'attack2':pygame.K_b,'dash':pygame.K_LSHIFT, # Changed J,K to V,B for P1 default
                      'roll':pygame.K_LCTRL,'interact':pygame.K_e}
        self._process_input_logic(keys, events, key_config)

    def handle_mapped_input(self, keys, events, key_map):
        self._process_input_logic(keys, events, key_map)

    def update(self, dt, platforms, ladders, hazards, enemies):
        if not self._valid_init or self.is_dead:
            if self.is_dead: self.animate(); return
        now = pygame.time.get_ticks()
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown: self.is_taking_hit = False
        self.check_ladder_collisions(ladders)
        if self.on_ladder and not self.can_grab_ladder: self.on_ladder = False; self.set_state('fall' if not self.on_ground else 'idle')
        apply_grav = not (self.on_ladder or self.state == 'wall_hang' or (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1))
        if apply_grav: self.vel.y += C.PLAYER_GRAVITY
        apply_horiz_phys = not (self.is_dashing or self.is_rolling or self.on_ladder or (self.state == 'wall_climb' and self.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1))
        if apply_horiz_phys:
            self.vel.x += self.acc.x; current_fric = 0
            if self.on_ground and self.acc.x == 0 and not self.is_sliding and self.state != 'slide': current_fric = C.PLAYER_FRICTION
            elif not self.on_ground and not self.is_attacking and self.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']: current_fric = C.PLAYER_FRICTION * 0.2
            elif self.is_sliding or self.state == 'slide': current_fric = C.PLAYER_FRICTION * 0.7
            if current_fric != 0:
                 fric_force = self.vel.x * current_fric
                 if abs(self.vel.x) > 0.1: self.vel.x += fric_force
                 else: self.vel.x = 0
                 if abs(self.vel.x) < 0.5 and (self.is_sliding or self.state == 'slide'):
                     self.is_sliding = False
                     end_s = 'slide_trans_end' if 'slide_trans_end' in self.animations and self.animations['slide_trans_end'] else None
                     if end_s: self.set_state(end_s)
                     else: self.is_crouching = self.is_holding_crouch_ability_key; self.set_state('crouch' if self.is_crouching else 'idle')
            limit = C.PLAYER_RUN_SPEED_LIMIT * 0.6 if self.is_crouching and self.state == 'crouch_walk' else C.PLAYER_RUN_SPEED_LIMIT
            if not self.is_dashing and not self.is_rolling and not self.is_sliding and self.state != 'slide':
                self.vel.x = max(-limit, min(limit, self.vel.x))
        if self.vel.y > 0 and not self.on_ladder: self.vel.y = min(self.vel.y, 18)
        self.touching_wall = 0; self.on_ground = False
        self.pos.x += self.vel.x; self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        collided_x_enemy = self.check_character_collisions('x', enemies)
        self.pos.y += self.vel.y; self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        if not collided_x_enemy: self.check_character_collisions('y', enemies)
        self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom
        self.check_hazard_collisions(hazards); self.check_attack_collisions(enemies); self.animate()

    def check_platform_collisions(self, direction, platforms):
        collided_wall_side = 0
        for plat in pygame.sprite.spritecollide(self, platforms, False):
            if direction == 'x':
                if self.vel.x > 0: self.rect.right = plat.rect.left; collided_wall_side = 1 if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5 else 0
                elif self.vel.x < 0: self.rect.left = plat.rect.right; collided_wall_side = -1 if not self.on_ground and not self.on_ladder and self.rect.bottom > plat.rect.top + 5 else 0
                self.vel.x = 0; self.pos.x = self.rect.centerx
            elif direction == 'y':
                if self.vel.y > 0:
                    if (self.pos.y - self.vel.y) <= plat.rect.top + 1: # Check previous bottom
                        self.rect.bottom = plat.rect.top
                        if not self.on_ground: self.can_wall_jump=False; self.wall_climb_timer=0; self.vel.x *= 0.8
                        self.on_ground=True; self.vel.y=0
                elif self.vel.y < 0:
                    if ((self.pos.y - self.rect.height) - self.vel.y) >= plat.rect.bottom -1 : # Check previous top
                         if self.on_ladder: self.on_ladder = False
                         self.rect.top = plat.rect.bottom; self.vel.y=0
                self.pos.y = self.rect.bottom # Update pos after y-collision resolution
        if direction == 'x' and collided_wall_side != 0 and not self.on_ground and not self.on_ladder:
             self.touching_wall = collided_wall_side
             self.can_wall_jump = not (self.state == 'wall_climb' and self.is_holding_climb_ability_key)

    def check_ladder_collisions(self, ladders):
        if not self._valid_init: return
        check_r = self.rect.inflate(-self.rect.width * 0.6, 0); self.can_grab_ladder = False
        for ladder in pygame.sprite.spritecollide(self, ladders, False, collided=lambda p,l: check_r.colliderect(l.rect)):
            if abs(self.rect.centerx - ladder.rect.centerx) < ladder.rect.width * 0.7 and ladder.rect.top < self.rect.bottom and self.rect.top < ladder.rect.bottom:
                  self.can_grab_ladder = True; break

    def check_character_collisions(self, direction, enemies):
        if not self._valid_init or self.is_dead: return False
        collision_occurred = False
        for enemy in pygame.sprite.spritecollide(self, enemies, False):
            if enemy.is_dead: continue; collision_occurred = True
            if direction == 'x':
                push_dir = 0
                if self.vel.x >= 0 and self.rect.centerx < enemy.rect.centerx: self.rect.right = enemy.rect.left; push_dir = -1
                elif self.vel.x <= 0 and self.rect.centerx > enemy.rect.centerx: self.rect.left = enemy.rect.right; push_dir = 1
                elif self.vel.x == 0: # Static collision
                    push_dir = -1 if self.rect.centerx < enemy.rect.centerx else 1
                    if push_dir == -1: self.rect.right = enemy.rect.left
                    else: self.rect.left = enemy.rect.right
                if push_dir != 0:
                    self.vel.x = push_dir * C.CHARACTER_BOUNCE_VELOCITY
                    if hasattr(enemy, 'vel'): enemy.vel.x = -push_dir * C.CHARACTER_BOUNCE_VELOCITY; enemy.rect.x += -push_dir * 2
                    self.pos.x = self.rect.centerx # Update internal position
            elif direction == 'y':
                if self.vel.y > 0 and self.rect.bottom > enemy.rect.top: self.rect.bottom = enemy.rect.top; self.on_ground=True; self.vel.y=0
                elif self.vel.y < 0 and self.rect.top < enemy.rect.bottom: self.rect.top = enemy.rect.bottom; self.vel.y=0
                self.pos.y = self.rect.bottom # Update internal position
        return collision_occurred

    def check_hazard_collisions(self, hazards):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown): return
        damaged_this_frame = False
        for hazard in pygame.sprite.spritecollide(self, hazards, False):
            if isinstance(hazard, Lava) and hazard.rect.collidepoint((self.rect.centerx, self.rect.bottom - 1)) and not damaged_this_frame:
                self.take_damage(C.LAVA_DAMAGE); damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.7
                     self.vel.x = - (1 if self.rect.centerx < hazard.rect.centerx else -1) * 6 # Push away from center
                     self.on_ground = False # Ensure airborne after bounce
                break

    def check_attack_collisions(self, enemies):
        if not self._valid_init or not self.is_attacking or self.is_dead: return
        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery + (-10 if self.is_crouching else 0)
        for enemy in pygame.sprite.spritecollide(self, enemies, False, collided=lambda p,e: self.attack_hitbox.colliderect(e.rect)):
            if not enemy.is_dead and hasattr(enemy, 'take_damage') and callable(enemy.take_damage):
                 can_damage = True
                 if hasattr(enemy, 'is_taking_hit') and hasattr(enemy, 'hit_timer') and hasattr(enemy, 'hit_cooldown'):
                     if enemy.is_taking_hit and (pygame.time.get_ticks() - enemy.hit_timer < enemy.hit_cooldown): can_damage = False
                 if can_damage: enemy.take_damage(C.PLAYER_ATTACK_DAMAGE)

    def take_damage(self, amount):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            return
        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        if self.current_health <= 0:
            if not self.is_dead: self.set_state('death')
        else:
            if not (self.is_taking_hit and now - self.hit_timer < self.hit_duration):
                 self.set_state('hit')

    def self_inflict_damage(self, amount):
        """Player inflicts damage upon themselves."""
        if not self._valid_init or self.is_dead:
            return
        self.take_damage(amount)

    def heal_to_full(self):
        """ Restores the player's health to its maximum value. """
        if not self._valid_init or self.is_dead: return
        self.current_health = self.max_health
        print(f"Player {self.player_id} healed to full: {self.current_health}/{self.max_health}")
        if self.is_taking_hit: self.is_taking_hit = False
        # If healing revives, uncomment below:
        # if self.is_dead: self.is_dead = False; self.set_state('idle')

    def reset_state(self, spawn_pos):
        if not self._valid_init: return
        self.pos = pygame.math.Vector2(spawn_pos[0], spawn_pos[1])
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)
        self.current_health = self.max_health; self.is_dead = False; self.is_taking_hit = False
        self.is_attacking = False; self.attack_type = 0; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True
        self.set_state('idle')
        print(f"Player {self.player_id} reset to {self.pos} with {self.current_health} HP.")

    def get_network_data(self):
        # Basic implementation, expand as needed for network sync
        return {'pos': (self.pos.x, self.pos.y), 'vel': (self.vel.x, self.vel.y), 'state': self.state,
                'facing_right': self.facing_right, 'current_health': self.current_health, 'is_dead': self.is_dead,
                'is_attacking': self.is_attacking, 'attack_type': self.attack_type,
                'current_frame': self.current_frame, 'last_anim_update': self.last_anim_update, # For smoother anim sync
                'player_id': self.player_id} # Include player_id for server to identify

    def set_network_data(self, data): # Basic implementation
        if data is None: return
        self.pos.x, self.pos.y = data.get('pos', (self.pos.x, self.pos.y))
        self.vel.x, self.vel.y = data.get('vel', (self.vel.x, self.vel.y))
        new_state = data.get('state', self.state)
        # Only call set_state if it's truly different to avoid interrupting animations unnecessarily
        # unless the server is also sending frame data for perfect sync.
        if self.state != new_state and not self.is_dead: # Don't change state if dead, let death anim play
            self.set_state(new_state)
        self.facing_right = data.get('facing_right', self.facing_right)
        self.current_health = data.get('current_health', self.current_health)
        self.is_dead = data.get('is_dead', self.is_dead)
        self.is_attacking = data.get('is_attacking', self.is_attacking)
        self.attack_type = data.get('attack_type', self.attack_type)
        # For smoother animation sync from server:
        self.current_frame = data.get('current_frame', self.current_frame)
        self.last_anim_update = data.get('last_anim_update', self.last_anim_update)
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y)) # Crucial to update rect


    def handle_network_input(self, input_data_dict):
        # This is a conceptual placeholder for client-side player (controlled by server)
        # or server-side player (controlled by client input).
        # It would map dictionary keys (like 'left_held': True) to player actions.
        # E.g., if input_data_dict.get('left_held'): self.acc.x = -C.PLAYER_ACCEL
        # This method should essentially mirror parts of _process_input_logic,
        # but using the dictionary from the network instead of direct Pygame key/event checks.
        # This requires a well-defined input_data_dict structure.
        # print(f"P{self.player_id} received network input: {input_data_dict}") # For debugging
        
        # Example of processing (needs to be robust and match get_input_state structure)
        # This is highly simplified and needs careful implementation matching get_input_state
        if not self._valid_init or self.is_dead: return

        self.acc.x = 0 # Reset acceleration
        if input_data_dict.get('left_held'):
            self.acc.x = -C.PLAYER_ACCEL
            if self.facing_right and self.on_ground: self.set_state('turn') # Basic turn
            self.facing_right = False
        if input_data_dict.get('right_held'):
            self.acc.x = C.PLAYER_ACCEL
            if not self.facing_right and self.on_ground: self.set_state('turn') # Basic turn
            self.facing_right = True
        
        # Event-like actions (these would ideally be distinct flags like 'jump_pressed_this_tick')
        if input_data_dict.get('up_pressed_event'): # Assuming 'up_pressed_event' is sent for jump
            if self.on_ground: self.vel.y = C.PLAYER_JUMP_STRENGTH; self.set_state('jump'); self.on_ground = False
        # Add similar for attack, dash, roll based on flags in input_data_dict
        # This needs to be carefully designed to match what get_input_state sends.


    def get_input_state(self, current_keys, current_events, key_map_for_player=None):
        # This method should generate a dictionary representing the player's current input.
        # This dictionary is then sent over the network by the client.
        input_state = {
            'left_held': False, 'right_held': False, 'up_held': False, 'down_held': False,
            'attack1_pressed_event': False, 'attack2_pressed_event': False,
            'dash_pressed_event': False, 'roll_pressed_event': False,
            'interact_pressed_event': False,
            # 'action_reset': False, # This might be handled at a higher level, not per-player input
            # 'action_self_harm': False # Could be added if client requests self-harm
        }

        if key_map_for_player: # Use the provided key map
            input_state['left_held'] = current_keys[key_map_for_player['left']]
            input_state['right_held'] = current_keys[key_map_for_player['right']]
            input_state['up_held'] = current_keys[key_map_for_player['up']]
            input_state['down_held'] = current_keys[key_map_for_player['down']]

            for event in current_events:
                if event.type == pygame.KEYDOWN:
                    if event.key == key_map_for_player.get('attack1'): input_state["attack1_pressed_event"] = True
                    if event.key == key_map_for_player.get('attack2'): input_state["attack2_pressed_event"] = True
                    if event.key == key_map_for_player.get('dash'): input_state["dash_pressed_event"] = True
                    if event.key == key_map_for_player.get('roll'): input_state["roll_pressed_event"] = True
                    if event.key == key_map_for_player.get('interact'): input_state["interact_pressed_event"] = True
                    # If you add a self-harm key to the map (e.g., 'self_harm': pygame.K_h)
                    # if 'self_harm' in key_map_for_player and event.key == key_map_for_player.get('self_harm'):
                    #     input_state["action_self_harm"] = True
        else: # Fallback to default P1 keys if no map provided (less flexible for network)
            input_state['left_held'] = current_keys[pygame.K_a]
            input_state['right_held'] = current_keys[pygame.K_d]
            input_state['up_held'] = current_keys[pygame.K_w]
            input_state['down_held'] = current_keys[pygame.K_s]
            for event in current_events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_v: input_state["attack1_pressed_event"] = True # Assuming V,B for P1 if no map
                    if event.key == pygame.K_b: input_state["attack2_pressed_event"] = True
                    if event.key == pygame.K_LSHIFT: input_state["dash_pressed_event"] = True
                    if event.key == pygame.K_LCTRL: input_state["roll_pressed_event"] = True
                    if event.key == pygame.K_e: input_state["interact_pressed_event"] = True
        return input_state