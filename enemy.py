########## START OF FILE: enemy.py ##########

# enemy.py
# -*- coding: utf-8 -*-
## version 1.0.0.9 (Added stomp kill mechanic)
"""
Defines the Enemy class, a CPU-controlled character.
Handles AI-driven movement (via enemy_ai_handler), animations, states,
combat (via enemy_combat_handler), and network synchronization
(via enemy_network_handler).
Each instance randomly selects a color variant for its animations if configured.
"""
import pygame
import random
import math
import os

from utils import PrintLimiter 
import constants as C 
from assets import load_all_player_animations 
from tiles import Lava 

from enemy_ai_handler import set_enemy_new_patrol_target, enemy_ai_update
from enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage
from enemy_network_handler import get_enemy_network_data, set_enemy_network_data


class Enemy(pygame.sprite.Sprite):
    # Class-level print limiter for non-critical warnings or infrequent info.
    # For heavy debugging, print statements should be temporary or use a more verbose logger.
    print_limiter = PrintLimiter(default_limit=3, default_period=10.0) 

    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y) 
        self.patrol_area = patrol_area 
        self.enemy_id = enemy_id if enemy_id is not None else id(self) 
        self._valid_init = True 
        character_base_asset_folder = 'characters'
        available_enemy_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow'] 
        if not available_enemy_colors: 
             if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_init_no_colors"): # Use unique key
                print(f"Enemy Warning (ID: {self.enemy_id}): No enemy colors defined! Defaulting to 'player1' assets.")
             available_enemy_colors = ['player1'] 
        self.color_name = random.choice(available_enemy_colors) 
        chosen_enemy_asset_folder = os.path.join(character_base_asset_folder, self.color_name)
        
        self.animations = load_all_player_animations(relative_asset_folder=chosen_enemy_asset_folder)
        if self.animations is None: 
            print(f"Enemy CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): Failed loading animations from '{chosen_enemy_asset_folder}'.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE) 
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False; self.is_dead = True; return 
        
        self._last_facing_right = True 
        self._last_state_for_debug = "init" # Can be removed if not actively debugging state machine
        self.state = 'idle'      
        self.current_frame = 0   
        self.last_anim_update = pygame.time.get_ticks() 
        
        initial_idle_animation = self.animations.get('idle')
        if not initial_idle_animation: 
             if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_init_idle_missing"): # Use unique key
                print(f"Enemy Warning (ID: {self.enemy_id}, Color: {self.color_name}): 'idle' animation missing. Attempting fallback.")
             first_anim_key = next(iter(self.animations), None)
             initial_idle_animation = self.animations.get(first_anim_key) if first_anim_key and self.animations.get(first_anim_key) else None
        
        if initial_idle_animation and len(initial_idle_animation) > 0:
            self.image = initial_idle_animation[0]
        else: 
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE) 
            print(f"Enemy CRITICAL (ID: {self.enemy_id}): No suitable initial animation found after fallbacks.")
            self._valid_init = False; self.is_dead = True; return
            
        self.rect = self.image.get_rect(midbottom=(start_x, start_y)) 
        self.pos = pygame.math.Vector2(start_x, start_y) 
        self.vel = pygame.math.Vector2(0, 0)             
        self.acc = pygame.math.Vector2(0, getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8))) 
        self.facing_right = random.choice([True, False]) 
        self.on_ground = False     
        self.ai_state = 'patrolling' 
        self.patrol_target_x = start_x 
        set_enemy_new_patrol_target(self) 
        self.is_attacking = False; self.attack_timer = 0
        self.attack_duration = getattr(C, 'ENEMY_ATTACK_STATE_DURATION', getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 500)) 
        self.attack_type = 0 
        self.attack_cooldown_timer = 0 
        self.post_attack_pause_timer = 0 
        self.post_attack_pause_duration = getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200) 
        self.is_taking_hit = False; self.hit_timer = 0 
        self.hit_duration = getattr(C, 'ENEMY_HIT_STUN_DURATION', 300) 
        self.hit_cooldown = getattr(C, 'ENEMY_HIT_COOLDOWN', 500)      
        self.is_dead = False
        self.death_animation_finished = False 
        self.state_timer = 0 
        self.max_health = getattr(C, 'ENEMY_MAX_HEALTH', 100)
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35) 
        try: self.standard_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
        except (KeyError, IndexError, TypeError): self.standard_height = 60 

        # Stomp death attributes
        self.is_stomp_dying = False
        self.stomp_death_start_time = 0
        self.original_stomp_death_image = None
        self.original_stomp_facing_right = True


    def set_state(self, new_state: str):
        if not self._valid_init: return 
        
        # If being stomp-killed, visual state is handled by is_stomp_dying in animate()
        if self.is_stomp_dying and new_state != 'stomp_death': # Allow setting to 'stomp_death' if needed by logic
            return

        animation_key_to_validate = new_state 
        valid_direct_animation_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall', 'stomp_death']
        
        if new_state not in valid_direct_animation_states: 
            if new_state in ['chasing', 'patrolling']:
                animation_key_to_validate = 'run' 
            elif 'attack' in new_state: 
                animation_key_to_validate = new_state 
            else: 
                animation_key_to_validate = 'idle'

        # For stomp_death, there's no dedicated animation sheet, it's procedural
        if new_state == 'stomp_death':
            pass # No animation frames to validate for stomp_death
        elif animation_key_to_validate not in self.animations or not self.animations[animation_key_to_validate]:
            if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_set_state_anim_miss_{animation_key_to_validate}"): # Use unique key
                print(f"Enemy Warning (ID: {self.enemy_id}): Animation for key '{animation_key_to_validate}' (from logical: '{new_state}') missing. Trying 'idle'.")
            animation_key_to_validate = 'idle' 
            if 'idle' not in self.animations or not self.animations['idle']: 
                 if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_set_state_crit_idle_miss"): # Use unique key
                    print(f"Enemy CRITICAL (ID: {self.enemy_id}): Cannot find valid 'idle' animation. Halting state change for '{new_state}'.")
                 return 

        can_change_state_now = (self.state != new_state or new_state in ['death', 'stomp_death']) and \
                               not (self.is_dead and not self.death_animation_finished and new_state not in ['death', 'stomp_death'])

        if can_change_state_now:
            self._last_state_for_debug = new_state # Keep if still useful for your own debugging
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False

            self.state = new_state 
            self.current_frame = 0 
            current_ticks_ms = pygame.time.get_ticks()
            self.last_anim_update = current_ticks_ms 
            self.state_timer = current_ticks_ms       

            if 'attack' in new_state: 
                self.is_attacking = True; self.attack_type = 1 
                self.attack_timer = current_ticks_ms; self.vel.x = 0 
            elif new_state == 'hit': 
                 self.is_taking_hit = True; self.hit_timer = self.state_timer 
                 self.vel.x *= -0.5 
                 self.vel.y = getattr(C, 'ENEMY_HIT_BOUNCE_Y', getattr(C, 'PLAYER_JUMP_STRENGTH', -10) * 0.3)
                 self.is_attacking = False 
            elif new_state == 'death' or new_state == 'stomp_death': 
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0 
                 self.acc.xy = 0, 0; self.current_health = 0 
                 self.death_animation_finished = False 
                 if new_state == 'stomp_death' and not self.is_stomp_dying: # Ensure stomp flags are set if directly setting this state
                     self.stomp_kill() # This will correctly initialize stomp death
            
            self.animate() 
        elif not self.is_dead: 
             self._last_state_for_debug = self.state 

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        # Allow animation if alive() OR if is_dead and death animation not finished (covers normal and stomp death)
        if not (self.alive() or (self.is_dead and not self.death_animation_finished)):
            return

        current_time_ms = pygame.time.get_ticks()
        animation_frame_duration_ms = getattr(C, 'ANIM_FRAME_DURATION', 100) 

        if self.is_stomp_dying:
            if not self.original_stomp_death_image:
                self.death_animation_finished = True
                self.is_stomp_dying = False
                # if self.alive(): self.kill() # Let external logic handle kill based on death_animation_finished
                return

            elapsed_time = current_time_ms - self.stomp_death_start_time
            stomp_death_total_duration = getattr(C, 'ENEMY_STOMP_DEATH_DURATION', 500)
            scale_factor = 0.0

            if elapsed_time >= stomp_death_total_duration:
                self.death_animation_finished = True
                self.is_stomp_dying = False
            else:
                scale_factor = 1.0 - (elapsed_time / stomp_death_total_duration)
            
            scale_factor = max(0.0, min(1.0, scale_factor))

            original_width = self.original_stomp_death_image.get_width()
            original_height = self.original_stomp_death_image.get_height()
            new_height = int(original_height * scale_factor)

            if new_height <= 1: # Make it effectively invisible or 1px high
                self.image = pygame.Surface((original_width, 1), pygame.SRCALPHA)
                self.image.fill((0,0,0,0)) # Transparent
                if not self.death_animation_finished: # Ensure flags are set if shrink makes it disappear early
                    self.death_animation_finished = True
                    self.is_stomp_dying = False
            else:
                self.image = pygame.transform.scale(self.original_stomp_death_image, (original_width, new_height))
            
            old_midbottom = self.rect.midbottom
            self.rect = self.image.get_rect(midbottom=old_midbottom)
            # self._last_facing_right is not strictly needed here as stomp image is fixed.
            return # Stomp death animation overrides other animation logic

        determined_animation_key = 'idle' 

        if self.is_dead: # Regular death (not stomp)
            determined_animation_key = 'death_nm' if abs(self.vel.x) < 0.1 and abs(self.vel.y) < 0.1 and \
                                     self.animations.get('death_nm') else 'death'
            if not self.animations.get(determined_animation_key):
                determined_animation_key = 'death' if self.animations.get('death') else 'idle' 
        elif self.post_attack_pause_timer > 0 and current_time_ms < self.post_attack_pause_timer: 
            determined_animation_key = 'idle' 
        elif self.state in ['patrolling', 'chasing'] or (self.state == 'run' and abs(self.vel.x) > 0.1): 
             determined_animation_key = 'run' if abs(self.vel.x) > 0.1 else 'idle'
        elif self.is_attacking: 
            determined_animation_key = 'attack_nm' if self.animations.get('attack_nm') else 'attack'
            if not self.animations.get(determined_animation_key): determined_animation_key = 'idle'
        elif self.is_taking_hit: 
            determined_animation_key = 'hit' if self.animations.get('hit') else 'idle'
        elif not self.on_ground: 
            determined_animation_key = 'fall' if self.animations.get('fall') else 'idle'
        elif self.state == 'idle': 
            determined_animation_key = 'idle'
        elif self.state == 'run': 
            determined_animation_key = 'run' if abs(self.vel.x) > 0.1 else 'idle' 
        
        if not self.animations.get(determined_animation_key):
            if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_animate_key_fallback_{determined_animation_key}"): # Use unique key
                print(f"Enemy Animate Warning (ID: {self.enemy_id}): Key '{determined_animation_key}' invalid for state '{self.state}'. Defaulting to 'idle'.")
            determined_animation_key = 'idle'
        
        current_animation_frames_list = self.animations.get(determined_animation_key)

        if not current_animation_frames_list: 
            if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE) 
            if Enemy.print_limiter.can_print(f"enemy_{self.enemy_id}_animate_no_frames_{determined_animation_key}"): # Use unique key
                print(f"Enemy CRITICAL Animate (ID: {self.enemy_id}): No frames for '{determined_animation_key}' (state: {self.state})")
            return

        if not (self.is_dead and self.death_animation_finished): 
            if current_time_ms - self.last_anim_update > animation_frame_duration_ms: 
                self.last_anim_update = current_time_ms 
                self.current_frame += 1 
                
                if self.current_frame >= len(current_animation_frames_list): 
                    if self.is_dead: # Regular death animation finished
                        self.current_frame = len(current_animation_frames_list) - 1 
                        self.death_animation_finished = True
                        final_death_image_surface = current_animation_frames_list[self.current_frame]
                        if not self.facing_right: final_death_image_surface = pygame.transform.flip(final_death_image_surface, True, False)
                        old_enemy_midbottom = self.rect.midbottom
                        self.image = final_death_image_surface
                        self.rect = self.image.get_rect(midbottom=old_enemy_midbottom)
                        return 
                    elif self.state == 'hit': 
                        self.set_state('idle' if self.on_ground else 'fall') 
                        return 
                    else: 
                        self.current_frame = 0
                
                if self.current_frame >= len(current_animation_frames_list) and not self.is_dead : self.current_frame = 0
        
        if self.is_dead and self.death_animation_finished and not self.alive(): 
            return 

        if not current_animation_frames_list or self.current_frame < 0 or \
           self.current_frame >= len(current_animation_frames_list):
            self.current_frame = 0 
            if not current_animation_frames_list: 
                if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE); return

        image_for_this_frame = current_animation_frames_list[self.current_frame]
        current_facing_is_right_for_anim = self.facing_right
        if not current_facing_is_right_for_anim: 
            image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)
        
        if self.image is not image_for_this_frame or self._last_facing_right != current_facing_is_right_for_anim:
            old_enemy_midbottom_pos = self.rect.midbottom 
            self.image = image_for_this_frame 
            self.rect = self.image.get_rect(midbottom=old_enemy_midbottom_pos) 
            self._last_facing_right = current_facing_is_right_for_anim 

    def stomp_kill(self):
        if self.is_dead or self.is_stomp_dying:
            return
        # print(f"DEBUG Enemy {self.enemy_id}: Stomp kill initiated.")
        self.current_health = 0
        self.is_dead = True 
        self.is_stomp_dying = True
        self.stomp_death_start_time = pygame.time.get_ticks()
        
        # Capture current visual state for scaling
        # self.animate() # Ensure self.image is up-to-date before copying (might be risky if animate has side effects)
        # Best to rely on self.image being set from previous frame's animate call.
        self.original_stomp_death_image = self.image.copy() 
        self.original_stomp_facing_right = self.facing_right
        
        self.vel.xy = 0,0 
        self.acc.xy = 0,0 
        # No self.set_state('stomp_death') needed if animate() checks self.is_stomp_dying first.
        # self.state remains as is, or can be set to a generic 'dying' if needed.

    def _ai_update(self, players_list_for_targeting):
        enemy_ai_update(self, players_list_for_targeting)

    def _check_attack_collisions(self, player_target_list_for_combat):
        check_enemy_attack_collisions(self, player_target_list_for_combat)

    def take_damage(self, damage_amount_taken):
        enemy_take_damage(self, damage_amount_taken) 

    def get_network_data(self):
        return get_enemy_network_data(self)

    def set_network_data(self, received_network_data):
        set_enemy_network_data(self, received_network_data)


    def update(self, dt_sec, players_list_for_logic, platforms_group, hazards_group):
        if not self._valid_init: return
        
        if self.is_stomp_dying:
            self.animate() # Handles scaling and sets death_animation_finished
            # Removal from groups is handled by main game loop when death_animation_finished is true
            return

        if self.is_dead and self.alive(): # Regular death (not stomp)
            if not self.death_animation_finished: 
                if not self.on_ground: 
                    self.vel.y += self.acc.y 
                    self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
                    self.pos.y += self.vel.y
                    self.rect.bottom = round(self.pos.y)
                    self.on_ground = False 
                    for platform_sprite in pygame.sprite.spritecollide(self, platforms_group, False):
                        if self.vel.y > 0 and self.rect.bottom > platform_sprite.rect.top and \
                           (self.pos.y - self.vel.y) <= platform_sprite.rect.top + 1:
                            self.rect.bottom = platform_sprite.rect.top
                            self.on_ground = True; self.vel.y = 0; self.acc.y = 0 
                            self.pos.y = self.rect.bottom; break
            self.animate() 
            return 

        if self.is_dead and self.death_animation_finished: # Fully dead (stomp or regular)
            if self.alive(): self.kill() 
            return

        current_time_ms = pygame.time.get_ticks()

        if self.post_attack_pause_timer > 0 and current_time_ms >= self.post_attack_pause_timer:
            self.post_attack_pause_timer = 0 

        if self.is_taking_hit and current_time_ms - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False 

        self._ai_update(players_list_for_logic) 

        if not self.is_dead: 
            self.vel.y += self.acc.y 
            
            enemy_friction_val = getattr(C, 'ENEMY_FRICTION', -0.12)
            enemy_run_speed_max = getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5)
            terminal_fall_speed_y = getattr(C, 'TERMINAL_VELOCITY_Y', 18) 

            self.vel.x += self.acc.x 

            apply_friction_to_enemy = self.on_ground and self.acc.x == 0 
            if apply_friction_to_enemy:
                friction_force_on_enemy = self.vel.x * enemy_friction_val
                if abs(self.vel.x) > 0.1: self.vel.x += friction_force_on_enemy
                else: self.vel.x = 0 

            self.vel.x = max(-enemy_run_speed_max, min(enemy_run_speed_max, self.vel.x))
            self.vel.y = min(self.vel.y, terminal_fall_speed_y)
            
            self.on_ground = False 

            self.pos.x += self.vel.x
            self.rect.centerx = round(self.pos.x)
            self.check_platform_collisions('x', platforms_group) 
            
            collided_horizontally_with_player = self.check_character_collision('x', players_list_for_logic)

            self.pos.y += self.vel.y
            self.rect.bottom = round(self.pos.y)
            self.check_platform_collisions('y', platforms_group) 

            if not collided_horizontally_with_player: 
                self.check_character_collision('y', players_list_for_logic)

            self.pos.x = self.rect.centerx
            self.pos.y = self.rect.bottom

            self.check_hazard_collisions(hazards_group)
            
            if self.is_attacking: 
                self._check_attack_collisions(players_list_for_logic) 
        
        self.animate()


    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        for platform_sprite in pygame.sprite.spritecollide(self, platforms_group, False):
            if direction == 'x': 
                original_vel_x = self.vel.x 
                if self.vel.x > 0: self.rect.right = platform_sprite.rect.left 
                elif self.vel.x < 0: self.rect.left = platform_sprite.rect.right 
                self.vel.x = 0 
                if self.ai_state == 'patrolling': 
                    if abs(original_vel_x) > 0.1 and \
                       (abs(self.rect.right - platform_sprite.rect.left) < 2 or \
                        abs(self.rect.left - platform_sprite.rect.right) < 2) :
                        set_enemy_new_patrol_target(self) 
            elif direction == 'y': 
                if self.vel.y > 0: 
                    if self.rect.bottom > platform_sprite.rect.top and \
                       (self.pos.y - self.vel.y) <= platform_sprite.rect.top + 1: 
                         self.rect.bottom = platform_sprite.rect.top
                         self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0: 
                    if self.rect.top < platform_sprite.rect.bottom and \
                       ((self.pos.y - self.rect.height) - self.vel.y) >= platform_sprite.rect.bottom -1:
                         self.rect.top = platform_sprite.rect.bottom
                         self.vel.y = 0 
            if direction == 'x': self.pos.x = self.rect.centerx
            else: self.pos.y = self.rect.bottom


    def check_character_collision(self, direction: str, player_list: list): 
        if not self._valid_init or self.is_dead or not self.alive(): return False
        collision_with_player_occurred = False
        for player_char_sprite in player_list:
            if not (player_char_sprite and player_char_sprite._valid_init and \
                    not player_char_sprite.is_dead and player_char_sprite.alive()):
                continue
            if self.rect.colliderect(player_char_sprite.rect): 
                collision_with_player_occurred = True
                bounce_vel_on_collision = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                if direction == 'x': 
                    push_direction_for_enemy = -1 if self.rect.centerx < player_char_sprite.rect.centerx else 1
                    if push_direction_for_enemy == -1: self.rect.right = player_char_sprite.rect.left
                    else: self.rect.left = player_char_sprite.rect.right
                    self.vel.x = push_direction_for_enemy * bounce_vel_on_collision 
                    if hasattr(player_char_sprite, 'vel'): 
                        player_char_sprite.vel.x = -push_direction_for_enemy * bounce_vel_on_collision
                    if hasattr(player_char_sprite, 'pos') and hasattr(player_char_sprite, 'rect'): 
                        player_char_sprite.pos.x += (-push_direction_for_enemy * 1.5) 
                        player_char_sprite.rect.centerx = round(player_char_sprite.pos.x)
                    self.pos.x = self.rect.centerx 
                elif direction == 'y': 
                    if self.vel.y > 0 and self.rect.bottom > player_char_sprite.rect.top and \
                       self.rect.centery < player_char_sprite.rect.centery:
                        self.rect.bottom = player_char_sprite.rect.top; self.on_ground = True; self.vel.y = 0
                    elif self.vel.y < 0 and self.rect.top < player_char_sprite.rect.bottom and \
                         self.rect.centery > player_char_sprite.rect.centery:
                        self.rect.top = player_char_sprite.rect.bottom; self.vel.y = 0
                    self.pos.y = self.rect.bottom 
        return collision_with_player_occurred


    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        current_time_ms = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and current_time_ms - self.hit_timer < self.hit_cooldown): 
            return
        damage_taken_from_hazard_this_frame = False
        hazard_check_point_enemy_feet = (self.rect.centerx, self.rect.bottom - 1) 
        for hazard_sprite in hazards_group:
            if isinstance(hazard_sprite, Lava) and \
               hazard_sprite.rect.collidepoint(hazard_check_point_enemy_feet) and \
               not damage_taken_from_hazard_this_frame:
                self.take_damage(getattr(C, 'LAVA_DAMAGE', 50)) 
                damage_taken_from_hazard_this_frame = True
                if not self.is_dead: 
                     self.vel.y = getattr(C, 'PLAYER_JUMP_STRENGTH', -15) * 0.3 
                     push_dir_from_lava_hazard = 1 if self.rect.centerx < hazard_sprite.rect.centerx else -1
                     self.vel.x = -push_dir_from_lava_hazard * 4 
                     self.on_ground = False 
                break 


    def reset(self):
        if not self._valid_init: return
        self.pos = self.spawn_pos.copy() 
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel.xy = 0,0 
        self.acc.xy = 0, getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)) 
        self.current_health = self.max_health
        self.is_dead = False
        self.death_animation_finished = False
        self.is_taking_hit = False
        self.is_attacking = False; self.attack_type = 0
        self.hit_timer = 0; self.attack_timer = 0; self.attack_cooldown_timer = 0
        self.post_attack_pause_timer = 0 
        self.facing_right = random.choice([True, False]) 
        self.on_ground = False 
        self.ai_state = 'patrolling'
        set_enemy_new_patrol_target(self) 
        if hasattr(self.image, 'get_alpha') and self.image.get_alpha() is not None and \
           self.image.get_alpha() < 255:
            self.image.set_alpha(255)
        
        # Reset stomp death attributes
        self.is_stomp_dying = False
        self.stomp_death_start_time = 0
        self.original_stomp_death_image = None
        self.original_stomp_facing_right = self.facing_right

        self.set_state('idle')
########## END OF FILE: enemy.py ##########