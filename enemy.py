# -*- coding: utf-8 -*-
"""
enemy.py
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
    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None): # Added enemy_id
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area
        self.enemy_id = enemy_id 
        self.target_player_object = None # Stores the current AI target player object

        character_base_folder = 'characters'
        available_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow']
        if not available_colors:
             print("ERROR: No enemy colors defined in Enemy.__init__!")
             available_colors = ['player1'] 
             character_base_folder = '.' 

        chosen_color = random.choice(available_colors)
        self.color_name = chosen_color 
        chosen_folder_path = os.path.join(character_base_folder, chosen_color)

        print(f"Initializing Enemy instance with color: {chosen_color} (Path: {chosen_folder_path}) (ID: {self.enemy_id})")

        self.animations = load_all_player_animations(relative_asset_folder=chosen_folder_path) # Corrected typo
        if self.animations is None: 
            print(f"CRITICAL Enemy Init Error: Failed loading animations from {chosen_folder_path} for enemy {self.enemy_id}. Check path and idle animation.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False
            self.is_dead = True 
            return 
        else:
             self._valid_init = True

        self._last_facing = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks()
        initial_anim = self.animations.get('idle')
        if not initial_anim: 
             print(f"Warning: Idle animation missing for {chosen_color} enemy, using first available.")
             first_key = next(iter(self.animations), None)
             initial_anim = self.animations.get(first_key) if first_key else None
        self.image = initial_anim[0] if initial_anim else pygame.Surface((30, 40)).convert_alpha() 
        if not initial_anim: self.image.fill(C.BLUE) 

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y); self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = random.choice([True, False]); self.on_ground = False
        self.on_ladder = False; self.can_grab_ladder = False; self.touching_wall = 0
        self.is_crouching = False; self.is_dashing = False; self.is_rolling = False
        self.is_sliding = False; self.can_wall_jump = False; self.wall_climb_timer = 0
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.is_taking_hit = False; self.hit_timer = 0; self.hit_duration = 300 
        self.hit_cooldown = 500 
        self.is_dead = False; self.state_timer = 0
        self.max_health = C.ENEMY_MAX_HEALTH; self.current_health = self.max_health
        self.ai_state = 'patrolling'; self.patrol_target_x = start_x
        self.set_new_patrol_target()
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35)
        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError): 
            print(f"Warning Enemy ({self.color_name}): Could not get idle anim height, using default.")
            self.standard_height = 60

    def set_new_patrol_target(self):
        if self.patrol_area and isinstance(self.patrol_area, pygame.Rect):
             min_x = self.patrol_area.left + self.rect.width / 2
             max_x = self.patrol_area.right - self.rect.width / 2
             if min_x < max_x: 
                 self.patrol_target_x = random.uniform(min_x, max_x)
             else: 
                 self.patrol_target_x = self.patrol_area.centerx
        else:
            direction = 1 if random.random() > 0.5 else -1
            self.patrol_target_x = self.pos.x + direction * C.ENEMY_PATROL_DIST

    def set_state(self, new_state):
        if not self._valid_init: return
        anim_state = new_state
        valid_anim_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall']
        if new_state not in valid_anim_states:
            if new_state in ['chasing', 'patrolling']: anim_state = 'run' if abs(self.vel.x) > 0.1 else 'idle'
            elif 'attack' in new_state: anim_state = new_state 
            else: anim_state = 'idle' 

        if anim_state not in self.animations or not self.animations[anim_state]:
             print(f"Warning Enemy ({self.color_name}): Animation for state '{anim_state}' missing/empty. Falling back to idle.")
             anim_state = 'idle'
             if 'idle' not in self.animations or not self.animations['idle']:
                 print(f"CRITICAL ERROR Enemy ({self.color_name}): Cannot find valid idle animation.")
                 return 

        if self.state != new_state and not self.is_dead:
            self._last_state_for_debug = new_state
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False 

            self.state = new_state 
            self.current_frame = 0; self.last_anim_update = pygame.time.get_ticks(); self.state_timer = pygame.time.get_ticks()

            if 'attack' in new_state:
                self.is_attacking = True; self.attack_type = 1; self.attack_timer = self.state_timer
                anim = self.animations.get(anim_state) 
                self.attack_duration = len(anim) * C.ANIM_FRAME_DURATION if anim else 400
                self.vel.x = 0 
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.5; self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3
                 self.is_attacking = False 
            elif new_state == 'death': 
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc = pygame.math.Vector2(0, 0); self.current_health = 0
            self.animate() 
        elif not self.is_dead:
             self._last_state_for_debug = self.state 

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        now = pygame.time.get_ticks()

        state_key = self.state
        if self.state == 'patrolling' or self.state == 'chasing':
             state_key = 'run' if abs(self.vel.x) > 0.5 else 'idle'
        elif self.is_attacking: state_key = 'attack_nm' if 'attack_nm' in self.animations and self.animations['attack_nm'] else 'attack' 
        elif self.is_taking_hit: state_key = 'hit' 
        elif self.is_dead: state_key = 'death_nm' if abs(self.vel.x) < 0.5 and 'death_nm' in self.animations and self.animations['death_nm'] else 'death'
        elif not self.on_ground: state_key = 'fall' if 'fall' in self.animations and self.animations['fall'] else 'idle' 
        else: state_key = 'idle' 

        if state_key not in self.animations or not self.animations[state_key]: state_key = 'idle'
        animation = self.animations.get(state_key) 
        if not animation:
             if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
             return 

        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1)
            if self.current_frame >= len(animation):
                if self.state == 'hit': 
                    self.set_state('idle')
                    return
                elif self.is_dead: self.current_frame = len(animation) - 1 
                else: self.current_frame = 0 
            if self.current_frame >= len(animation): self.current_frame = 0

        if not animation or self.current_frame < 0 or self.current_frame >= len(animation):
            self.current_frame = 0 
            if not animation: 
                 if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
                 return

        new_image = animation[self.current_frame]
        current_facing_is_right = self.facing_right
        if not current_facing_is_right: new_image = pygame.transform.flip(new_image, True, False)
        if self.image is not new_image or self._last_facing != current_facing_is_right:
            old_midbottom = self.rect.midbottom
            self.image = new_image
            self.rect = self.image.get_rect(midbottom=old_midbottom) 
            self._last_facing = current_facing_is_right

    def ai_update(self, players_list): # MODIFIED: Parameter is now a list
        now = pygame.time.get_ticks()
        
        # Prevent AI if dead or in hit stun cooldown
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
            self.acc.x = 0
            self.target_player_object = None # Clear target
            return

        # Find the closest, living player
        closest_player_obj = None
        min_dist_sq = float('inf') # Use squared distance to avoid sqrt initially

        if not players_list: # Handle empty players_list (e.g., if both players disconnect or die simultaneously)
            self.target_player_object = None
        else:
            for p_obj in players_list:
                if p_obj and hasattr(p_obj, 'is_dead') and not p_obj.is_dead and hasattr(p_obj, 'pos'):
                    # Calculate squared distance first
                    dist_x = p_obj.pos.x - self.pos.x
                    dist_y = p_obj.pos.y - self.pos.y
                    current_dist_sq = dist_x**2 + dist_y**2
                    if current_dist_sq < min_dist_sq:
                        min_dist_sq = current_dist_sq
                        closest_player_obj = p_obj
        
        self.target_player_object = closest_player_obj # Update the AI's current target

        # If no valid target, default to patrolling
        if not self.target_player_object:
            self.ai_state = 'patrolling'
            if self.state != 'patrolling': self.set_state('patrolling')
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right_patrol = (self.patrol_target_x > self.pos.x)
            self.acc.x = C.ENEMY_ACCEL * 0.7 * (1 if target_facing_right_patrol else -1)
            if not self.is_attacking and self.facing_right != target_facing_right_patrol:
                self.facing_right = target_facing_right_patrol
            return

        # Use the chosen target_player_object for AI logic
        player = self.target_player_object 
        dist_to_player = math.sqrt(min_dist_sq) # Now calculate actual distance if needed

        y_diff = abs(player.rect.centery - self.rect.centery)
        line_of_sight = y_diff < self.rect.height * 2.0 
        player_in_range = dist_to_player < C.ENEMY_ATTACK_RANGE and line_of_sight # player.is_dead already checked
        player_detected = dist_to_player < C.ENEMY_DETECTION_RANGE and line_of_sight # player.is_dead already checked
        can_attack_now = now - self.attack_cooldown_timer > C.ENEMY_ATTACK_COOLDOWN

        if self.is_attacking and now - self.attack_timer > self.attack_duration:
             self.is_attacking = False; self.attack_type = 0
             self.attack_cooldown_timer = now
             self.set_state('idle') 
             return 

        if self.is_attacking:
            self.acc.x = 0; return

        target_acc_x = 0; target_facing_right = self.facing_right

        if player_in_range and can_attack_now:
            self.ai_state = 'attacking' 
            target_facing_right = (player.pos.x > self.pos.x) 
            self.facing_right = target_facing_right 
            self.set_state('attack_nm' if 'attack_nm' in self.animations else 'attack') 
            return 
        elif player_detected:
            self.ai_state = 'chasing'
            target_facing_right = (player.pos.x > self.pos.x)
            target_acc_x = C.ENEMY_ACCEL * (1 if target_facing_right else -1)
            if self.state != 'chasing': self.set_state('chasing') 
        else: 
            self.ai_state = 'patrolling'
            if self.state != 'patrolling': self.set_state('patrolling')
            if abs(self.pos.x - self.patrol_target_x) < 10: self.set_new_patrol_target()
            target_facing_right = (self.patrol_target_x > self.pos.x)
            target_acc_x = C.ENEMY_ACCEL * 0.7 * (1 if target_facing_right else -1)

        self.acc.x = target_acc_x
        if not self.is_attacking and self.facing_right != target_facing_right:
             self.facing_right = target_facing_right

    # MODIFIED: 'player' parameter renamed to 'players_list'
    def update(self, dt, players_list, platforms, hazards):
        if not self._valid_init or self.is_dead:
            if self.is_dead: self.animate() 
            return

        now = pygame.time.get_ticks()
        if self.is_taking_hit and now - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False

        self.ai_update(players_list) # Pass the list of players

        if not self.is_dead: self.vel.y += C.PLAYER_GRAVITY 
        self.vel.x += self.acc.x 
        current_friction = 0
        if self.on_ground and self.acc.x == 0: current_friction = C.ENEMY_FRICTION
        if current_friction != 0:
             friction_force = self.vel.x * current_friction
             if abs(self.vel.x) > 0.1: self.vel.x += friction_force
             else: self.vel.x = 0 
        self.vel.x = max(-C.ENEMY_RUN_SPEED_LIMIT, min(C.ENEMY_RUN_SPEED_LIMIT, self.vel.x))
        self.vel.y = min(self.vel.y, 18)

        self.on_ground = False 

        self.pos.x += self.vel.x
        self.rect.centerx = round(self.pos.x)
        self.check_platform_collisions('x', platforms)
        collided_x_player = self.check_character_collision('x', players_list) # Pass list

        self.pos.y += self.vel.y
        self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms)
        if not collided_x_player:
            self.check_character_collision('y', players_list) # Pass list

        self.pos.x = self.rect.centerx; self.pos.y = self.rect.bottom

        self.check_attack_collisions(players_list) # Pass list
        self.check_hazard_collisions(hazards)

        self.animate() 

    def check_platform_collisions(self, direction, platforms):
        """ Resolves collisions with solid platforms. Bounces horizontally if specified in original code. """
        collided_sprites = pygame.sprite.spritecollide(self, platforms, False)
        for plat in collided_sprites:
            if direction == 'x':
                original_vel_x = self.vel.x
                if original_vel_x > 0: 
                    self.rect.right = plat.rect.left
                elif original_vel_x < 0: 
                    self.rect.left = plat.rect.right
                
                # Check if your original code had bouncing for enemies or just stopping
                # self.vel.x *= -1 # If bouncing
                # self.facing_right = not self.facing_right # If bouncing
                self.vel.x = 0 # If stopping (as per the code you provided before this error)

                self.pos.x = self.rect.centerx
                if self.ai_state == 'patrolling':
                    self.set_new_patrol_target()
            elif direction == 'y':
                if self.vel.y > 0: 
                    previous_bottom = self.pos.y - self.vel.y
                    if previous_bottom <= plat.rect.top + 1: 
                         self.rect.bottom = plat.rect.top
                         self.on_ground = True
                         self.vel.y = 0
                         self.pos.y = self.rect.bottom
                elif self.vel.y < 0: 
                    previous_top = (self.pos.y - self.rect.height) - self.vel.y
                    if previous_top >= plat.rect.bottom - 1: 
                         self.rect.top = plat.rect.bottom
                         self.vel.y = 0
                         self.pos.y = self.rect.bottom 


    # MODIFIED: 'player' parameter renamed to 'players_list'
    def check_character_collision(self, direction, players_list):
        if not self._valid_init or self.is_dead: return False
        
        any_collision_this_frame = False
        for player_obj in players_list:
            if not player_obj or (hasattr(player_obj, 'is_dead') and player_obj.is_dead):
                continue

            if self.rect.colliderect(player_obj.rect):
                any_collision_this_frame = True
                if direction == 'x':
                    push_dir = 0 
                    if self.rect.centerx < player_obj.rect.centerx: 
                        self.rect.right = player_obj.rect.left
                        push_dir = -1 
                    else: 
                        self.rect.left = player_obj.rect.right
                        push_dir = 1 

                    self.vel.x = push_dir * C.CHARACTER_BOUNCE_VELOCITY
                    if hasattr(player_obj, 'vel'):
                        player_obj.vel.x = -push_dir * C.CHARACTER_BOUNCE_VELOCITY
                        player_obj.rect.x += -push_dir * 2 
                    self.pos.x = self.rect.centerx 
                elif direction == 'y':
                     if self.vel.y > 0 and self.rect.bottom > player_obj.rect.top: 
                        self.rect.bottom = player_obj.rect.top
                        self.on_ground = True 
                        self.vel.y = 0
                     elif self.vel.y < 0 and self.rect.top < player_obj.rect.bottom: 
                        self.rect.top = player_obj.rect.bottom
                        self.vel.y = 0
                     self.pos.y = self.rect.bottom 
                # If a collision happened with one player, we might break or continue
                # For now, let it check all players, but bounce logic might be tricky for multiple simultaneous
        return any_collision_this_frame


    def check_hazard_collisions(self, hazards):
        now = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or (self.is_taking_hit and now - self.hit_timer < self.hit_cooldown):
             return

        collided_hazards = pygame.sprite.spritecollide(self, hazards, False)
        damaged_this_frame = False
        for hazard in collided_hazards:
            check_point = (self.rect.centerx, self.rect.bottom - 1)
            if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point) and not damaged_this_frame:
                self.take_damage(C.LAVA_DAMAGE)
                damaged_this_frame = True
                if not self.is_dead:
                     self.vel.y = C.PLAYER_JUMP_STRENGTH * 0.3 
                     push_dir = 1 if self.rect.centerx < hazard.rect.centerx else -1
                     self.vel.x = -push_dir * 4 
                     self.on_ground = False 
                break 

    # MODIFIED: 'player' parameter renamed to 'players_list'
    def check_attack_collisions(self, players_list):
        if not self._valid_init or not self.is_attacking or self.is_dead: return

        if self.facing_right: self.attack_hitbox.midleft = self.rect.midright
        else: self.attack_hitbox.midright = self.rect.midleft
        self.attack_hitbox.centery = self.rect.centery

        now = pygame.time.get_ticks()
        for player_obj in players_list:
            if not player_obj or (hasattr(player_obj, 'is_dead') and player_obj.is_dead):
                continue
            
            # Check if player_obj is invincible
            if hasattr(player_obj, 'is_taking_hit') and player_obj.is_taking_hit and \
               hasattr(player_obj, 'hit_timer') and hasattr(player_obj, 'hit_cooldown') and \
               now - player_obj.hit_timer < player_obj.hit_cooldown:
                continue 

            if self.attack_hitbox.colliderect(player_obj.rect):
                if hasattr(player_obj, 'take_damage') and callable(player_obj.take_damage):
                    player_obj.take_damage(C.ENEMY_ATTACK_DAMAGE)
                    # Potentially break if an attack only hits one target per swing


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

    def reset(self):
        if not self._valid_init: return
        self.pos = self.spawn_pos.copy()
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY) 
        self.current_health = self.max_health
        self.is_dead = False; self.is_taking_hit = False; self.is_attacking = False
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.facing_right = random.choice([True, False])
        self.on_ground = False 
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.set_state('idle') 
        self.ai_state = 'patrolling' 
        self.target_player_object = None # Reset target
        self.set_new_patrol_target() 