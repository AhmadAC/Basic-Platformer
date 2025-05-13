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
import time # For PrintLimiter

# Import necessary components
import constants as C # Use constants with C. prefix
from assets import load_all_player_animations # Reuse player animation loader
from tiles import Lava # Import Lava for type checking in hazard collision

# --- Print Limiter Utility ---
class PrintLimiter:
    def __init__(self, default_limit=5, default_period=2.0):
        self.counts = {}
        self.timestamps = {}
        self.default_limit = default_limit
        self.default_period = default_period
        self.globally_suppressed = {} # Tracks if the "suppressing further prints" message was shown

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
            self.globally_suppressed[message_key] = False # Reset suppression message flag

        if self.counts[message_key] < limit:
            self.counts[message_key] += 1
            return True
        elif not self.globally_suppressed[message_key]: # Only print suppression message once per period
            # print(f"[PrintLimiter] Suppressing further prints for '{message_key}' for {period:.1f}s (limit: {limit})") # Keep this commented for less console noise
            self.globally_suppressed[message_key] = True
            return False
        return False

class Enemy(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=3, default_period=2.0) # Class-level limiter for shared messages

    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area
        self.enemy_id = enemy_id

        character_base_folder = 'characters'
        available_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow']
        if not available_colors:
             if Enemy.print_limiter.can_print("enemy_init_no_colors"):
                print("ERROR: No enemy colors defined in Enemy.__init__!")
             available_colors = ['player1']
             character_base_folder = '.'

        chosen_color = random.choice(available_colors)
        self.color_name = chosen_color
        chosen_folder_path = os.path.join(character_base_folder, chosen_color)

        self.animations = load_all_player_animations(relative_asset_folder=chosen_folder_path)
        if self.animations is None:
            print(f"CRITICAL Enemy {self.enemy_id} ({self.color_name}) Init Error: Failed loading animations from {chosen_folder_path}.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False; self.is_dead = True; return
        else: self._valid_init = True

        self._last_facing = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks()
        initial_anim = self.animations.get('idle')
        if not initial_anim:
             if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_idle_missing"):
                print(f"Warning Enemy {self.enemy_id} ({self.color_name}): Idle animation missing or empty, using first available.")
             first_key = next(iter(self.animations), None)
             initial_anim = self.animations.get(first_key) if first_key and self.animations.get(first_key) else None
        
        self.image = initial_anim[0] if initial_anim else pygame.Surface((30, 40)).convert_alpha()
        if not initial_anim: self.image.fill(C.BLUE)

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y); self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, getattr(C, 'PLAYER_GRAVITY', 0.8))
        self.facing_right = random.choice([True, False]); self.on_ground = False
        self.on_ladder = False; self.can_grab_ladder = False; self.touching_wall = 0
        self.is_crouching = False; self.is_dashing = False; self.is_rolling = False
        self.is_sliding = False; self.can_wall_jump = False; self.wall_climb_timer = 0
        
        self.is_attacking = False; self.attack_timer = 0
        self.attack_duration = getattr(C, 'ENEMY_ATTACK_STATE_DURATION', 
                                   getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 500))
        
        self.attack_type = 0
        self.attack_cooldown_timer = 0 
        self.post_attack_pause_timer = 0 
        self.post_attack_pause_duration = getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200) 

        self.is_taking_hit = False; self.hit_timer = 0; self.hit_duration = getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)
        self.hit_cooldown = getattr(C, 'ENEMY_HIT_COOLDOWN', 500)
        self.is_dead = False; self.state_timer = 0
        self.max_health = getattr(C, 'ENEMY_MAX_HEALTH', 100); self.current_health = self.max_health
        self.ai_state = 'patrolling'; self.patrol_target_x = start_x
        self.set_new_patrol_target()
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35)
        try: self.standard_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
        except (KeyError, IndexError, TypeError):
            self.standard_height = 60
        self.death_animation_finished = False


    def set_new_patrol_target(self):
        if self.patrol_area and isinstance(self.patrol_area, pygame.Rect):
             min_x = self.patrol_area.left + self.rect.width / 2
             max_x = self.patrol_area.right - self.rect.width / 2
             if min_x < max_x: self.patrol_target_x = random.uniform(min_x, max_x)
             else: self.patrol_target_x = self.patrol_area.centerx
        else:
            direction = 1 if random.random() > 0.5 else -1
            self.patrol_target_x = self.pos.x + direction * getattr(C, 'ENEMY_PATROL_DIST', 150)

    def set_state(self, new_state):
        if not self._valid_init: return
        
        anim_state = new_state
        valid_anim_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall']
        
        if new_state not in valid_anim_states:
            if new_state in ['chasing', 'patrolling']: anim_state = 'run' if abs(self.vel.x) > 0.1 else 'idle'
            elif 'attack' in new_state: anim_state = new_state
            else: anim_state = 'idle'

        if anim_state not in self.animations or not self.animations[anim_state]:
             if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_anim_missing_{anim_state}"):
                print(f"DEBUG Enemy {self.enemy_id} ({self.color_name}): Animation for state '{anim_state}' (orig logic: {new_state}) missing/empty. Falling back to idle.")
             anim_state = 'idle'
             if 'idle' not in self.animations or not self.animations['idle']:
                 if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_critical_idle_missing"):
                    print(f"DEBUG CRITICAL Enemy {self.enemy_id} ({self.color_name}): Cannot find valid idle animation. Halting state change.")
                 return

        if (self.state != new_state or new_state == 'death') and \
           not (self.is_dead and not self.death_animation_finished and new_state != 'death'):
            
            if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_set_state", limit=50, period=5.0):
                print(f"DEBUG Enemy {self.enemy_id} ({self.color_name}): Set Logical State from '{self.state}' to '{new_state}' (Anim key: '{anim_state}')")
            
            self._last_state_for_debug = new_state
            
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False

            self.state = new_state
            self.current_frame = 0
            current_ticks = pygame.time.get_ticks() # Get current time once
            self.last_anim_update = current_ticks
            self.state_timer = current_ticks       # General state timer

            if 'attack' in new_state:
                self.is_attacking = True
                self.attack_type = 1 
                self.attack_timer = current_ticks # *** MODIFICATION: Directly set attack_timer ***
                # self.attack_duration is already set in __init__ from constants.
                self.vel.x = 0 
                if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_attack_state_init"):
                    print(f"DEBUG Enemy {self.enemy_id}: Entered attack state. Duration: {self.attack_duration}ms. Attack Timer starts at: {self.attack_timer}")

            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.5
                 self.vel.y = getattr(C, 'ENEMY_HIT_BOUNCE_Y', getattr(C, 'PLAYER_JUMP_STRENGTH', -10) * 0.3)
                 self.is_attacking = False 
            elif new_state == 'death':
                 if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_entering_death_state"):
                    print(f"DEBUG Enemy {self.enemy_id} ({self.color_name}): In set_state('death'). is_dead=True, current_health={self.current_health}")
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc.xy = 0, 0
                 self.current_health = 0
                 self.death_animation_finished = False
            
            if self.alive() or new_state == 'death':
                self.animate() 
        elif not self.is_dead:
             self._last_state_for_debug = self.state

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        if not self.alive() and not (self.is_dead and not self.death_animation_finished): return

        now = pygame.time.get_ticks()
        anim_frame_duration = getattr(C, 'ANIM_FRAME_DURATION', 100)

        state_key = self.state
        if self.is_dead:
            state_key = 'death_nm' if abs(self.vel.x) < 0.1 and abs(self.vel.y) < 0.1 and \
                                     'death_nm' in self.animations and self.animations['death_nm'] \
                                  else 'death'
            if state_key not in self.animations or not self.animations[state_key]: state_key = 'death'
        elif self.post_attack_pause_timer > 0 and now < self.post_attack_pause_timer: 
            state_key = 'idle' 
        elif self.state in ['patrolling', 'chasing']:
             state_key = 'run' if abs(self.vel.x) > 0.5 else 'idle'
        elif self.is_attacking: 
            state_key = 'attack_nm' if 'attack_nm' in self.animations and self.animations['attack_nm'] else 'attack'
        elif self.is_taking_hit:
            state_key = 'hit'
        elif not self.on_ground:
            state_key = 'fall' if 'fall' in self.animations and self.animations['fall'] else 'idle'

        if state_key not in self.animations or not self.animations[state_key]:
            state_key = 'idle'
        
        animation_frames = self.animations.get(state_key)
        if not animation_frames:
             if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
             return

        if not self.death_animation_finished:
            if now - self.last_anim_update > anim_frame_duration:
                self.last_anim_update = now
                self.current_frame += 1
                if self.current_frame >= len(animation_frames):
                    if self.is_dead:
                        self.current_frame = len(animation_frames) - 1
                        self.death_animation_finished = True
                        base_image_of_frame = animation_frames[self.current_frame]
                        image_to_render = base_image_of_frame.copy()
                        if not self.facing_right: image_to_render = pygame.transform.flip(image_to_render, True, False)
                        old_midbottom = self.rect.midbottom
                        self.image = image_to_render
                        self.rect = self.image.get_rect(midbottom=old_midbottom)
                        return 
                    elif self.state == 'hit':
                        self.set_state('idle'); return
                    else: 
                        self.current_frame = 0
                if self.current_frame >= len(animation_frames) and not self.is_dead : self.current_frame = 0
        
        if self.is_dead and self.death_animation_finished and not self.alive(): 
            return

        if not animation_frames or self.current_frame < 0 or self.current_frame >= len(animation_frames):
            self.current_frame = 0 
            if not animation_frames:
                 if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE); return

        base_image_of_frame = animation_frames[self.current_frame]
        image_to_render = base_image_of_frame.copy()
        current_facing_is_right = self.facing_right
        if not current_facing_is_right: image_to_render = pygame.transform.flip(image_to_render, True, False)
        
        if self.image is not image_to_render or self._last_facing != current_facing_is_right:
            old_midbottom = self.rect.midbottom
            self.image = image_to_render
            self.rect = self.image.get_rect(midbottom=old_midbottom)
            self._last_facing = current_facing_is_right

    def ai_update(self, players_list):
        now = pygame.time.get_ticks()
        
        if self.post_attack_pause_timer > 0 and now < self.post_attack_pause_timer:
            self.acc.x = 0 
            if self.state != 'idle': self.set_state('idle') 
            return 

        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            self.acc.x = 0; return

        target_player_for_ai = None; min_dist_sq = float('inf')
        for p_candidate in players_list:
            is_targetable = p_candidate and p_candidate._valid_init and hasattr(p_candidate, 'pos') and \
                            hasattr(p_candidate, 'rect') and p_candidate.alive()
            if is_targetable:
                if hasattr(p_candidate, 'is_dead') and p_candidate.is_dead:
                    is_targetable = False 
                
                if is_targetable:
                    dist_sq = (p_candidate.pos.x - self.pos.x)**2 + (p_candidate.pos.y - self.pos.y)**2
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq; target_player_for_ai = p_candidate
        
        if not target_player_for_ai:
            self.ai_state = 'patrolling'
            if self.state != 'patrolling' and self.state != 'idle': self.set_state('patrolling')
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right_patrol = (self.patrol_target_x > self.pos.x)
            enemy_accel_patrol = getattr(C, 'ENEMY_ACCEL', 0.4)
            self.acc.x = enemy_accel_patrol * 0.7 * (1 if target_facing_right_patrol else -1)
            if not self.is_attacking and self.facing_right != target_facing_right_patrol:
                self.facing_right = target_facing_right_patrol
            return

        dist_to_player = math.sqrt(min_dist_sq)
        enemy_attack_cooldown_val = getattr(C, 'ENEMY_ATTACK_COOLDOWN', 1500)
        enemy_attack_range_val = getattr(C, 'ENEMY_ATTACK_RANGE', 60)
        enemy_detection_range_val = getattr(C, 'ENEMY_DETECTION_RANGE', 0)
        enemy_accel_val = getattr(C, 'ENEMY_ACCEL', 0.4)
        
        can_attack_now = now - self.attack_cooldown_timer > enemy_attack_cooldown_val
        y_diff = abs(target_player_for_ai.rect.centery - self.rect.centery)
        line_of_sight_vertical_check = y_diff < self.rect.height * 1.0 
        
        player_in_range_for_attack = dist_to_player < enemy_attack_range_val and line_of_sight_vertical_check
        player_detected_for_chase = dist_to_player < enemy_detection_range_val and line_of_sight_vertical_check

        if self.is_attacking and now - self.attack_timer >= self.attack_duration:
             self.is_attacking = False; self.attack_type = 0
             self.attack_cooldown_timer = now 
             self.post_attack_pause_timer = now + self.post_attack_pause_duration
             if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_post_attack_pause_start"):
                 print(f"DEBUG Enemy {self.enemy_id}: Attack finished. AttackTimer: {self.attack_timer}, Duration: {self.attack_duration}, Now: {now}. Starting post-attack pause until {self.post_attack_pause_timer}")
             self.set_state('idle') 
             self.acc.x = 0 
             return 

        if self.is_attacking:
            self.acc.x = 0; return

        target_acc_x = 0; target_facing_right = self.facing_right
        if player_in_range_for_attack and can_attack_now:
            self.ai_state = 'attacking'
            target_facing_right = (target_player_for_ai.pos.x > self.pos.x)
            self.facing_right = target_facing_right
            self.set_state('attack_nm' if 'attack_nm' in self.animations else 'attack')
            return
        elif player_detected_for_chase:
            self.ai_state = 'chasing'
            target_facing_right = (target_player_for_ai.pos.x > self.pos.x)
            target_acc_x = enemy_accel_val * (1 if target_facing_right else -1)
            if self.state != 'chasing': self.set_state('chasing')
        else: 
            self.ai_state = 'patrolling'
            if self.state != 'patrolling': self.set_state('patrolling')
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right = (self.patrol_target_x > self.pos.x)
            target_acc_x = enemy_accel_val * 0.7 * (1 if target_facing_right else -1)

        self.acc.x = target_acc_x
        if not self.is_attacking and self.facing_right != target_facing_right:
             self.facing_right = target_facing_right


    def update(self, dt, players_list, platforms, hazards):
        if not self._valid_init: return
        if self.is_dead and not self.alive() and self.death_animation_finished: return
        if self.is_dead and self.alive(): 
            self.animate()
            return

        now = pygame.time.get_ticks()
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False
        
        if self.post_attack_pause_timer > 0 and now >= self.post_attack_pause_timer:
            self.post_attack_pause_timer = 0
            if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_post_attack_pause_end"):
                 print(f"DEBUG Enemy {self.enemy_id}: Post-attack pause ended.")


        self.ai_update(players_list)

        if not self.is_dead: 
            if not (self.post_attack_pause_timer > 0 and now < self.post_attack_pause_timer):
                player_gravity = getattr(C, 'PLAYER_GRAVITY', 0.7)
                enemy_friction_constant = getattr(C, 'ENEMY_FRICTION', -0.12)
                enemy_run_speed_limit = getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5)
                terminal_velocity_y = getattr(C, 'TERMINAL_VELOCITY_Y', 18) 

                self.vel.y += player_gravity
                self.vel.x += self.acc.x 

                apply_friction_flag = self.on_ground and self.acc.x == 0
                if apply_friction_flag:
                    friction_force = self.vel.x * enemy_friction_constant
                    if abs(self.vel.x) > 0.1: self.vel.x += friction_force
                    else: self.vel.x = 0

                self.vel.x = max(-enemy_run_speed_limit, min(enemy_run_speed_limit, self.vel.x))
                self.vel.y = min(self.vel.y, terminal_velocity_y)
            else: 
                if self.on_ground: self.vel.x *= 0.8 
            
            self.on_ground = False

            self.pos.x += self.vel.x
            self.rect.centerx = round(self.pos.x)
            self.check_platform_collisions('x', platforms)
            
            collided_x_with_any_player = False
            for p_target in players_list:
                if p_target and p_target._valid_init and not p_target.is_dead and p_target.alive():
                    if self.check_character_collision('x', p_target): collided_x_with_any_player = True
            
            self.pos.y += self.vel.y
            self.rect.bottom = round(self.pos.y)
            self.check_platform_collisions('y', platforms)

            if not collided_x_with_any_player:
                for p_target_y in players_list:
                     if p_target_y and p_target_y._valid_init and not p_target_y.is_dead and p_target_y.alive():
                        self.check_character_collision('y', p_target_y)

            self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom

            if self.is_attacking: 
                for p_attack_target in players_list:
                    if p_attack_target and p_attack_target._valid_init and not p_attack_target.is_dead and p_attack_target.alive():
                        self.check_attack_collisions(p_attack_target)
            
            self.check_hazard_collisions(hazards)
        
        self.animate()


    def check_platform_collisions(self, direction, platforms):
        for plat in pygame.sprite.spritecollide(self, platforms, False):
            if direction == 'x':
                if self.vel.x > 0: self.rect.right = plat.rect.left
                elif self.vel.x < 0: self.rect.left = plat.rect.right
                self.vel.x = 0
                if self.ai_state == 'patrolling': self.set_new_patrol_target()
            elif direction == 'y':
                if self.vel.y > 0:
                    if self.rect.bottom > plat.rect.top and (self.pos.y - self.vel.y) <= plat.rect.top + 1:
                         self.rect.bottom = plat.rect.top; self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0:
                    if self.rect.top < plat.rect.bottom and (self.pos.y - self.rect.height - self.vel.y) >= plat.rect.bottom -1 :
                         self.rect.top = plat.rect.bottom; self.vel.y = 0


    def check_character_collision(self, direction, player_obj): 
        if not (player_obj and player_obj._valid_init and not player_obj.is_dead and player_obj.alive()): return False
        if not self._valid_init or self.is_dead: return False

        collision_occurred = False
        if self.rect.colliderect(player_obj.rect):
            collision_occurred = True
            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            
            if direction == 'x':
                push_dir = -1 if self.rect.centerx < player_obj.rect.centerx else 1
                if push_dir == -1: self.rect.right = player_obj.rect.left
                else: self.rect.left = player_obj.rect.right
                self.vel.x = push_dir * bounce_vel
                if hasattr(player_obj, 'vel'): player_obj.vel.x = -push_dir * bounce_vel
                if hasattr(player_obj, 'pos') and hasattr(player_obj, 'rect'): 
                    player_obj.pos.x += (-push_dir * 2) 
                    player_obj.rect.centerx = round(player_obj.pos.x)
                self.pos.x = self.rect.centerx
            elif direction == 'y':
                 if self.vel.y > 0 and self.rect.bottom > player_obj.rect.top and self.rect.centery < player_obj.rect.centery :
                    self.rect.bottom = player_obj.rect.top; self.on_ground = True; self.vel.y = 0
                 elif self.vel.y < 0 and self.rect.top < player_obj.rect.bottom and self.rect.centery > player_obj.rect.centery:
                    self.rect.top = player_obj.rect.bottom; self.vel.y = 0
                 self.pos.y = self.rect.bottom
        return collision_occurred

    def check_hazard_collisions(self, hazards):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown): return

        lava_damage = getattr(C, 'LAVA_DAMAGE', 50)
        player_jump_strength = getattr(C, 'PLAYER_JUMP_STRENGTH', -15)
        
        damaged_this_frame = False
        for hazard in pygame.sprite.spritecollide(self, hazards, False):
            check_point = (self.rect.centerx, self.rect.bottom - 1) 
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point) and not damaged_this_frame:
                self.take_damage(lava_damage); damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = player_jump_strength * 0.3
                     push_dir_from_hazard = 1 if self.rect.centerx < hazard.rect.centerx else -1
                     self.vel.x = -push_dir_from_hazard * 4 
                     self.on_ground = False
                break

    def check_attack_collisions(self, player_obj): 
        if not (player_obj and player_obj._valid_init and not player_obj.is_dead and player_obj.alive()): return
        if not self._valid_init or not self.is_attacking or self.is_dead or not self.alive(): return

        now = pygame.time.get_ticks()
        player_invincible = False
        if hasattr(player_obj, 'is_taking_hit') and player_obj.is_taking_hit and \
           hasattr(player_obj, 'hit_timer') and hasattr(player_obj, 'hit_cooldown') and \
           now - player_obj.hit_timer < player_obj.hit_cooldown:
            player_invincible = True
        if player_invincible: return

        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery
        
        if self.attack_hitbox.colliderect(player_obj.rect):
            if hasattr(player_obj, 'take_damage') and callable(player_obj.take_damage):
                player_obj.take_damage(getattr(C, 'ENEMY_ATTACK_DAMAGE', 10))


    def take_damage(self, amount):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            return
        
        self.current_health -= amount
        self.current_health = max(0, self.current_health)
        
        if self.current_health <= 0:
            if not self.is_dead:
                self.set_state('death')
        else: 
             if not (self.is_taking_hit and now - self.hit_timer < self.hit_duration): 
                self.set_state('hit')


    def reset(self):
        if not self._valid_init: return
        
        self.pos = self.spawn_pos.copy(); self.vel.xy = 0,0
        self.acc.xy = 0, getattr(C, 'PLAYER_GRAVITY', 0.7)
        self.current_health = self.max_health
        self.is_dead = False; self.is_taking_hit = False
        self.is_attacking = False; self.attack_type = 0; self.attack_cooldown_timer = 0
        self.post_attack_pause_timer = 0 
        self.facing_right = random.choice([True, False]); self.on_ground = False
        self.death_animation_finished = False
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        if hasattr(self.image, 'get_alpha') and self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)
        self.set_state('idle'); self.ai_state = 'patrolling'; self.set_new_patrol_target()

    def get_network_data(self):
        return {
            'pos': (self.pos.x, self.pos.y), 'vel': (self.vel.x, self.vel.y), 'state': self.state,
            'current_frame': self.current_frame, 'last_anim_update': self.last_anim_update,
            'facing_right': self.facing_right, 'current_health': self.current_health,
            'is_dead': self.is_dead, 'is_attacking': self.is_attacking, 'attack_type': self.attack_type,
            'enemy_id': self.enemy_id, 'color_name': self.color_name,
            '_valid_init': self._valid_init,
            'death_animation_finished': self.death_animation_finished,
            'post_attack_pause_timer': self.post_attack_pause_timer 
        }

    def set_network_data(self, data):
        if data is None: return
        self._valid_init = data.get('_valid_init', self._valid_init)
        if not self._valid_init:
            if self.alive(): self.kill(); return 
        self.pos.x, self.pos.y = data.get('pos', (self.pos.x, self.pos.y))
        self.vel.x, self.vel.y = data.get('vel', (self.vel.x, self.vel.y))
        new_logical_state = data.get('state', self.state)
        self.is_attacking = data.get('is_attacking', self.is_attacking)
        self.attack_type = data.get('attack_type', self.attack_type)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)
        self.post_attack_pause_timer = data.get('post_attack_pause_timer', self.post_attack_pause_timer)
        new_is_dead = data.get('is_dead', self.is_dead)
        
        if new_is_dead and not self.is_dead:
            self.is_dead = True; self.current_health = 0
            self.set_state('death')
        elif not new_is_dead and self.is_dead:
            self.is_dead = False; self.death_animation_finished = False
            if self.state in ['death', 'death_nm']: self.set_state('idle')
        else:
            self.is_dead = new_is_dead

        if self.state != new_logical_state and not (self.is_dead and new_logical_state in ['death', 'death_nm']):
             self.set_state(new_logical_state)
        else:
            self.current_frame = data.get('current_frame', self.current_frame)
            self.last_anim_update = data.get('last_anim_update', self.last_anim_update)

        self.facing_right = data.get('facing_right', self.facing_right)
        new_health = data.get('current_health', self.current_health)
        if new_health < self.current_health and not self.is_taking_hit and not self.is_dead:
            if new_health > 0: self.set_state('hit')
        self.current_health = new_health
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        
        if self._valid_init and (self.alive() or (self.is_dead and not self.death_animation_finished)):
             self.animate()