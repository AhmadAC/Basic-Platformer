########## START OF FILE: enemy.py ##########
# enemy.py
# -*- coding: utf-8 -*-
## version 1.0.0.14 (Added apply_freeze_effect method)
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

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
# --- End Logger ---

import constants as C
from assets import load_all_player_animations
from tiles import Lava

from enemy_ai_handler import set_enemy_new_patrol_target, enemy_ai_update
from enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage
from enemy_network_handler import get_enemy_network_data, set_enemy_network_data


class Enemy(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None, color_name=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area
        self.enemy_id = enemy_id if enemy_id is not None else id(self)
        self._valid_init = True
        character_base_asset_folder = 'characters'
        
        available_enemy_colors = ['cyan', 'green', 'pink', 'purple', 'red', 'yellow']
        if not available_enemy_colors:
             warning(f"Enemy Warning (ID: {self.enemy_id}): No enemy colors defined! Defaulting to 'player1' assets.")
             available_enemy_colors = ['player1'] 

        if color_name and color_name in available_enemy_colors: 
            self.color_name = color_name
            debug(f"Enemy {self.enemy_id}: Initialized with specified color: {self.color_name}")
        elif color_name: 
            warning(f"Enemy Warning (ID: {self.enemy_id}): Specified color '{color_name}' not in available_enemy_colors. Choosing random.")
            self.color_name = random.choice(available_enemy_colors)
        else: 
            self.color_name = random.choice(available_enemy_colors)
            debug(f"Enemy {self.enemy_id}: Initialized with random color: {self.color_name}")

        chosen_enemy_asset_folder = os.path.join(character_base_asset_folder, self.color_name)

        self.animations = load_all_player_animations(relative_asset_folder=chosen_enemy_asset_folder)
        if self.animations is None:
            critical(f"Enemy CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): Failed loading animations from '{chosen_enemy_asset_folder}'.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False; self.is_dead = True; return

        self._last_facing_right = True
        self._last_state_for_debug = "init" 
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()

        initial_idle_animation = self.animations.get('idle')
        if not initial_idle_animation:
             warning(f"Enemy Warning (ID: {self.enemy_id}, Color: {self.color_name}): 'idle' animation missing. Attempting fallback.")
             first_anim_key = next(iter(self.animations), None)
             initial_idle_animation = self.animations.get(first_anim_key) if first_anim_key and self.animations.get(first_anim_key) else None

        if initial_idle_animation and len(initial_idle_animation) > 0:
            self.image = initial_idle_animation[0]
        else:
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.BLUE)
            critical(f"Enemy CRITICAL (ID: {self.enemy_id}): No suitable initial animation found after fallbacks.")
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

        self.is_stomp_dying = False
        self.stomp_death_start_time = 0
        self.original_stomp_death_image = None
        self.original_stomp_facing_right = True
        
        self.is_frozen = False
        self.is_defrosting = False
        self.frozen_effect_timer = 0

        self.is_aflame = False
        self.aflame_timer_start = 0
        self.is_deflaming = False
        self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.has_ignited_another_enemy_this_cycle = False
        
        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.stone_image_frame = self.animations.get('stone', [self._create_placeholder_surface(C.GRAY, "Stone")])[0]
        self.stone_smashed_frames = self.animations.get('stone_smashed', [self._create_placeholder_surface(C.DARK_GRAY, "Smash")])


    def _create_placeholder_surface(self, color, text="Err"):
        surf = pygame.Surface((30, 40)).convert_alpha() 
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: 
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass 
        return surf

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified): 
            return
        debug(f"Enemy {self.enemy_id} is being petrified.")
        self.is_petrified = True
        self.is_stone_smashed = False
        self.is_dead = True 
        self.current_health = 0 
        self.vel.xy = 0, 0
        self.acc.xy = 0, 0
        self.is_attacking = False
        self.is_taking_hit = False
        self.is_frozen = False; self.is_defrosting = False
        self.is_aflame = False; self.is_deflaming = False
        self.state = 'petrified' 
        self.current_frame = 0 
        self.death_animation_finished = True 
        self.set_state('petrified') 

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified:
            debug(f"Enemy {self.enemy_id}: apply_aflame_effect called but already aflame/deflaming/dead/petrified. Ignoring.")
            return

        debug(f"Enemy {self.enemy_id} ({self.color_name}): Applying aflame effect.")
        self.is_aflame = True
        self.is_deflaming = False
        self.is_frozen = False 
        self.is_defrosting = False

        self.aflame_timer_start = pygame.time.get_ticks()
        self.aflame_damage_last_tick = self.aflame_timer_start
        self.has_ignited_another_enemy_this_cycle = False
        
        self.is_attacking = False 
        self.attack_type = 0
        self.vel.x *= 0.5 
        
        self.set_state('aflame')

    def apply_freeze_effect(self):
        """Applies the frozen status effect to the enemy."""
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified:
            debug(f"Enemy {self.enemy_id}: apply_freeze_effect called but already frozen/deflating/dead/petrified. Ignoring.")
            return
        
        debug(f"Enemy {self.enemy_id} ({self.color_name}): Applying freeze effect.")
        self.is_frozen = True
        self.is_defrosting = False
        self.is_aflame = False # Freeze extinguishes fire
        self.is_deflaming = False
        
        self.frozen_effect_timer = pygame.time.get_ticks()
        self.vel.xy = 0,0
        self.acc.x = 0
        
        self.is_attacking = False # Stop current attack
        self.attack_type = 0
        
        self.set_state('frozen')


    def set_state(self, new_state: str):
        if not self._valid_init: return

        if self.is_petrified and new_state not in ['petrified', 'smashed', 'death', 'death_nm']: 
            debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' due to being petrified.")
            return

        if (self.is_aflame or self.is_deflaming) and \
           new_state not in ['aflame', 'deflame', 'idle', 'death', 'death_nm', 'stomp_death', 'petrified', 'smashed']:
            debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' due to aflame/deflaming.")
            return

        if (self.is_frozen or self.is_defrosting) and \
           new_state not in ['frozen', 'defrost', 'idle', 'death', 'death_nm', 'stomp_death', 'aflame', 'deflame', 'petrified', 'smashed']:
            debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' due to frozen/defrosting.")
            return
            
        if self.is_stomp_dying and new_state != 'stomp_death':
            return

        animation_key_to_validate = new_state
        valid_direct_animation_states = ['idle', 'run', 'attack', 'attack_nm', 'hit', 'death', 'death_nm', 'fall', 'stomp_death', 
                                         'frozen', 'defrost', 'aflame', 'deflame', 'petrified', 'smashed'] 

        if new_state not in valid_direct_animation_states:
            if new_state in ['chasing', 'patrolling']:
                animation_key_to_validate = 'run'
            elif 'attack' in new_state:
                animation_key_to_validate = new_state
            else:
                animation_key_to_validate = 'idle'
        
        is_new_anim_special_effect = animation_key_to_validate in ['frozen', 'defrost', 'aflame', 'deflame', 'petrified', 'smashed']
        if is_new_anim_special_effect and animation_key_to_validate not in ['petrified', 'smashed'] and self.color_name != 'green':
            debug(f"Enemy {self.enemy_id} ({self.color_name}): Cannot use state '{animation_key_to_validate}', not green. Defaulting to idle.")
            animation_key_to_validate = 'idle' 
        
        if animation_key_to_validate == 'petrified': animation_key_to_validate = 'stone'
        if animation_key_to_validate == 'smashed': animation_key_to_validate = 'stone_smashed'


        if new_state == 'stomp_death':
            pass 
        elif animation_key_to_validate not in self.animations or not self.animations[animation_key_to_validate]:
            warning(f"Enemy Warning (ID: {self.enemy_id}): Animation for key '{animation_key_to_validate}' (from logical: '{new_state}') missing. Trying 'idle'.")
            animation_key_to_validate = 'idle'
            if 'idle' not in self.animations or not self.animations['idle']:
                 critical(f"Enemy CRITICAL (ID: {self.enemy_id}): Cannot find valid 'idle' animation. Halting state change for '{new_state}'.")
                 return

        can_change_state_now = (self.state != new_state or new_state in ['death', 'stomp_death', 'frozen', 'defrost', 'aflame', 'deflame', 'petrified', 'smashed']) and \
                               not (self.is_dead and not self.death_animation_finished and new_state not in ['death', 'stomp_death', 'petrified', 'smashed'])

        if can_change_state_now:
            self._last_state_for_debug = new_state 
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False

            if self.state == 'frozen' and new_state != 'frozen': self.is_frozen = False
            if self.state == 'defrost' and new_state != 'defrost': self.is_defrosting = False
            if self.state == 'aflame' and new_state != 'aflame': self.is_aflame = False
            if self.state == 'deflame' and new_state != 'deflame': self.is_deflaming = False
            if self.state == 'petrified' and new_state != 'petrified': self.is_petrified = False 
            if self.state == 'smashed' and new_state != 'smashed': self.is_stone_smashed = False
            
            self.state = new_state
            self.current_frame = 0
            current_ticks_ms = pygame.time.get_ticks()
            self.last_anim_update = current_ticks_ms
            self.state_timer = current_ticks_ms

            if new_state == 'frozen': 
                self.is_frozen = True; self.is_defrosting = False 
                self.is_aflame = False; self.is_deflaming = False 
                self.frozen_effect_timer = current_ticks_ms 
                self.vel.xy = 0,0; self.acc.x = 0
            elif new_state == 'defrost': 
                self.is_defrosting = True; self.is_frozen = False 
                self.is_aflame = False; self.is_deflaming = False
                self.frozen_effect_timer = current_ticks_ms 
                self.vel.xy = 0,0; self.acc.x = 0
            elif new_state == 'aflame':
                self.is_aflame = True; self.is_deflaming = False
                self.is_frozen = False; self.is_defrosting = False 
                self.aflame_timer_start = current_ticks_ms 
                self.aflame_damage_last_tick = current_ticks_ms
                self.has_ignited_another_enemy_this_cycle = False
            elif new_state == 'deflame':
                self.is_deflaming = True; self.is_aflame = False
                self.is_frozen = False; self.is_defrosting = False
                self.deflame_timer_start = current_ticks_ms
            elif new_state == 'petrified': 
                self.is_petrified = True; self.is_stone_smashed = False
                self.is_dead = True; self.death_animation_finished = True 
                self.vel.xy = 0,0; self.acc.xy = 0,0
            elif new_state == 'smashed': 
                self.is_stone_smashed = True; self.is_petrified = True 
                self.stone_smashed_timer_start = current_ticks_ms
                self.vel.xy = 0,0; self.acc.xy = 0,0
            elif new_state == 'idle': 
                self.is_frozen = False; self.is_defrosting = False
                self.is_aflame = False; self.is_deflaming = False
                if self.is_petrified or self.is_stone_smashed:
                    self.is_petrified = False; self.is_stone_smashed = False
                    self.is_dead = False; self.death_animation_finished = False 

            elif 'attack' in new_state:
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
                 self.is_frozen = False; self.is_defrosting = False 
                 self.is_aflame = False; self.is_deflaming = False 
                 self.is_petrified = False; self.is_stone_smashed = False 
                 if new_state == 'stomp_death' and not self.is_stomp_dying: 
                     self.stomp_kill() 

            self.animate()
        elif not self.is_dead:
             self._last_state_for_debug = self.state

    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations') or not self.animations: return
        if not (self.alive() or (self.is_dead and not self.death_animation_finished)):
            if not self.is_petrified:
                return

        current_time_ms = pygame.time.get_ticks()
        animation_frame_duration_ms = getattr(C, 'ANIM_FRAME_DURATION', 100)

        if self.is_stomp_dying:
            if not self.original_stomp_death_image:
                self.death_animation_finished = True
                self.is_stomp_dying = False
                return
            elapsed_time = current_time_ms - self.stomp_death_start_time
            stomp_death_total_duration = getattr(C, 'ENEMY_STOMP_DEATH_DURATION', 300)
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
            if new_height <= 1: 
                self.image = pygame.Surface((original_width, 1), pygame.SRCALPHA)
                self.image.fill((0,0,0,0)) 
                if not self.death_animation_finished: 
                    self.death_animation_finished = True
                    self.is_stomp_dying = False
            else:
                self.image = pygame.transform.scale(self.original_stomp_death_image, (original_width, new_height))
            old_midbottom = self.rect.midbottom
            self.rect = self.image.get_rect(midbottom=old_midbottom)
            return 

        determined_animation_key = 'idle'
        current_animation_frames_list = None

        if self.is_petrified:
            if self.is_stone_smashed:
                determined_animation_key = 'stone_smashed' # This is the key for self.animations
                current_animation_frames_list = self.stone_smashed_frames # Use pre-loaded specific frames
            else: 
                determined_animation_key = 'stone'
                current_animation_frames_list = [self.stone_image_frame] if self.stone_image_frame else []
        elif self.is_dead: 
            determined_animation_key = 'death_nm' if abs(self.vel.x) < 0.1 and abs(self.vel.y) < 0.1 and \
                                     self.animations.get('death_nm') else 'death'
            if not self.animations.get(determined_animation_key):
                determined_animation_key = 'death' if self.animations.get('death') else 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'aflame': 
            determined_animation_key = 'aflame'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'deflame':
            determined_animation_key = 'deflame'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'frozen': 
            determined_animation_key = 'frozen'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'defrost': 
            determined_animation_key = 'defrost'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.post_attack_pause_timer > 0 and current_time_ms < self.post_attack_pause_timer:
            determined_animation_key = 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state in ['patrolling', 'chasing'] or (self.state == 'run' and abs(self.vel.x) > 0.1):
             determined_animation_key = 'run' if abs(self.vel.x) > 0.1 else 'idle'
             current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.is_attacking:
            determined_animation_key = 'attack_nm' if self.animations.get('attack_nm') else 'attack'
            if not self.animations.get(determined_animation_key): determined_animation_key = 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.is_taking_hit:
            determined_animation_key = 'hit' if self.animations.get('hit') else 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif not self.on_ground:
            determined_animation_key = 'fall' if self.animations.get('fall') else 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'idle':
            determined_animation_key = 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        elif self.state == 'run':
            determined_animation_key = 'run' if abs(self.vel.x) > 0.1 else 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)
        
        is_new_anim_green_specific_anim = determined_animation_key in ['frozen', 'defrost', 'aflame', 'deflame'] 
        if is_new_anim_green_specific_anim and self.color_name != 'green':
            determined_animation_key = 'idle' 
            current_animation_frames_list = self.animations.get(determined_animation_key)

        if not current_animation_frames_list: 
            if not self.animations.get(determined_animation_key):
                warning(f"Enemy Animate Warning (ID: {self.enemy_id}): Key '{determined_animation_key}' invalid for state '{self.state}'. Defaulting to 'idle'.")
                determined_animation_key = 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)


        if not current_animation_frames_list:
            if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
            critical(f"Enemy CRITICAL Animate (ID: {self.enemy_id}): No frames for '{determined_animation_key}' (state: {self.state})")
            return

        if not (self.is_dead and self.death_animation_finished and not self.is_petrified) or self.is_stone_smashed: 
            if current_time_ms - self.last_anim_update > animation_frame_duration_ms:
                self.last_anim_update = current_time_ms
                self.current_frame += 1

                if self.current_frame >= len(current_animation_frames_list):
                    if self.is_dead and not self.is_petrified: 
                        self.current_frame = len(current_animation_frames_list) - 1
                        self.death_animation_finished = True
                        return 
                    elif self.is_stone_smashed: 
                        self.current_frame = len(current_animation_frames_list) - 1
                    elif self.state == 'hit':
                        self.set_state('idle' if self.on_ground else 'fall')
                        return
                    else: 
                        self.current_frame = 0

                if self.current_frame >= len(current_animation_frames_list) and not self.is_dead and not self.is_petrified : self.current_frame = 0

        if self.is_dead and self.death_animation_finished and not self.alive() and not self.is_petrified:
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
        if self.is_dead or self.is_stomp_dying or self.is_petrified:
            return
        debug(f"Enemy {self.enemy_id}: Stomp kill initiated.")
        self.current_health = 0
        self.is_dead = True
        self.is_stomp_dying = True
        self.is_frozen = False; self.is_defrosting = False 
        self.is_aflame = False; self.is_deflaming = False 
        self.stomp_death_start_time = pygame.time.get_ticks()

        self.original_stomp_death_image = self.image.copy()
        self.original_stomp_facing_right = self.facing_right

        self.vel.xy = 0,0
        self.acc.xy = 0,0

    def _ai_update(self, players_list_for_targeting):
        enemy_ai_update(self, players_list_for_targeting)

    def _check_attack_collisions(self, player_target_list_for_combat):
        check_enemy_attack_collisions(self, player_target_list_for_combat)

    def take_damage(self, damage_amount_taken): 
        if self.is_petrified:
            if not self.is_stone_smashed:
                debug(f"Petrified Enemy {self.enemy_id} hit, changing to stone_smashed.")
                self.is_stone_smashed = True
                self.stone_smashed_timer_start = pygame.time.get_ticks()
                self.set_state('smashed') 
            return 
        enemy_take_damage(self, damage_amount_taken) 

    def get_network_data(self):
        return get_enemy_network_data(self)

    def set_network_data(self, received_network_data):
        set_enemy_network_data(self, received_network_data)


    def update(self, dt_sec, players_list_for_logic, platforms_group, hazards_group, all_enemies_list):
        if not self._valid_init: return

        current_time_ms = pygame.time.get_ticks()

        if self.is_stone_smashed:
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                debug(f"Smashed stone Enemy {self.enemy_id} duration ended. Killing.")
                self.kill()
                return
            self.animate() 
            return 
        
        if self.is_petrified: 
            self.vel.xy = 0,0
            self.acc.xy = 0,0
            self.animate() 
            return 

        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
                self.set_state('deflame') 
            elif current_time_ms - self.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
                self.aflame_damage_last_tick = current_time_ms
            if self.state == 'deflame': 
                self.animate() 
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
                self.set_state('idle') 
            if self.state == 'idle' and not self.is_aflame and not self.is_deflaming: 
                self.animate()

        if self.is_stomp_dying:
            self.animate(); return

        if self.is_dead: 
            self.is_aflame = False; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False
            if self.alive():
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
            if self.death_animation_finished and self.alive(): self.kill()
            return

        if self.is_frozen:
            self.vel.xy = 0,0; self.acc.x = 0
            if current_time_ms - self.frozen_effect_timer > C.ENEMY_FROZEN_DURATION_MS:
                self.set_state('defrost')
            self.animate(); return
        if self.is_defrosting:
            self.vel.xy = 0,0; self.acc.x = 0
            if current_time_ms - self.frozen_effect_timer > C.ENEMY_DEFROST_DURATION_MS: 
                self.set_state('idle')
            self.animate(); return

        if self.post_attack_pause_timer > 0 and current_time_ms >= self.post_attack_pause_timer:
            self.post_attack_pause_timer = 0
        if self.is_taking_hit and current_time_ms - self.hit_timer > self.hit_cooldown:
            self.is_taking_hit = False
        self._ai_update(players_list_for_logic)
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
        all_other_characters = players_list_for_logic + [e for e in all_enemies_list if e is not self]
        collided_horizontally_with_char = self.check_character_collision('x', all_other_characters)
        self.pos.y += self.vel.y
        self.rect.bottom = round(self.pos.y)
        self.check_platform_collisions('y', platforms_group)
        if not collided_horizontally_with_char:
            self.check_character_collision('y', all_other_characters)
        self.pos.x = self.rect.centerx
        self.pos.y = self.rect.bottom
        self.check_hazard_collisions(hazards_group)
        if self.is_attacking and not (self.is_aflame or self.is_deflaming):
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


    def check_character_collision(self, direction: str, character_list: list): 
        if not self._valid_init or self.is_dead or not self.alive() or self.is_petrified: 
            return False
        collision_occurred = False
        for other_char_sprite in character_list:
            if other_char_sprite is self: continue 

            if not (other_char_sprite and hasattr(other_char_sprite, '_valid_init') and \
                    other_char_sprite._valid_init and hasattr(other_char_sprite, 'is_dead') and \
                    (not other_char_sprite.is_dead or getattr(other_char_sprite, 'is_petrified', False)) and 
                    other_char_sprite.alive()):
                continue

            if self.rect.colliderect(other_char_sprite.rect):
                collision_occurred = True
                
                is_other_petrified = getattr(other_char_sprite, 'is_petrified', False)

                if self.is_aflame and isinstance(other_char_sprite, Enemy) and \
                   not getattr(other_char_sprite, 'is_aflame', False) and \
                   not getattr(other_char_sprite, 'is_deflaming', False) and \
                   not self.has_ignited_another_enemy_this_cycle and not is_other_petrified: 
                    
                    if hasattr(other_char_sprite, 'apply_aflame_effect'):
                        debug(f"Enemy {self.enemy_id} (aflame) touched Enemy {getattr(other_char_sprite, 'enemy_id', 'Unknown')}. Igniting.")
                        other_char_sprite.apply_aflame_effect()
                        self.has_ignited_another_enemy_this_cycle = True
                        continue 

                bounce_vel_on_collision = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                if direction == 'x':
                    push_direction_for_self = -1 if self.rect.centerx < other_char_sprite.rect.centerx else 1
                    if push_direction_for_self == -1: self.rect.right = other_char_sprite.rect.left
                    else: self.rect.left = other_char_sprite.rect.right
                    self.vel.x = push_direction_for_self * bounce_vel_on_collision
                    
                    if not is_other_petrified: 
                        can_push_other = True
                        if hasattr(other_char_sprite, 'is_attacking') and other_char_sprite.is_attacking: can_push_other = False
                        if hasattr(other_char_sprite, 'is_aflame') and other_char_sprite.is_aflame: can_push_other = False
                        if hasattr(other_char_sprite, 'is_frozen') and other_char_sprite.is_frozen: can_push_other = False

                        if hasattr(other_char_sprite, 'vel') and can_push_other:
                            other_char_sprite.vel.x = -push_direction_for_self * bounce_vel_on_collision
                        if hasattr(other_char_sprite, 'pos') and hasattr(other_char_sprite, 'rect') and can_push_other:
                            other_char_sprite.pos.x += (-push_direction_for_self * 1.5)
                            other_char_sprite.rect.centerx = round(other_char_sprite.pos.x)
                            other_char_sprite.rect.bottom = round(other_char_sprite.pos.y)
                            other_char_sprite.pos.x = other_char_sprite.rect.centerx
                            other_char_sprite.pos.y = other_char_sprite.rect.bottom
                    self.pos.x = self.rect.centerx
                elif direction == 'y': 
                    if self.vel.y > 0 and self.rect.bottom > other_char_sprite.rect.top and \
                       self.rect.centery < other_char_sprite.rect.centery: 
                        self.rect.bottom = other_char_sprite.rect.top; self.on_ground = True; self.vel.y = 0
                    elif self.vel.y < 0 and self.rect.top < other_char_sprite.rect.bottom and \
                         self.rect.centery > other_char_sprite.rect.centery: 
                        self.rect.top = other_char_sprite.rect.bottom; self.vel.y = 0
                    self.pos.y = self.rect.bottom
        return collision_occurred


    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        current_time_ms = pygame.time.get_ticks()
        if not self._valid_init or self.is_dead or not self.alive() or \
           (self.is_taking_hit and current_time_ms - self.hit_timer < self.hit_cooldown) or self.is_petrified: 
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

        self.is_stomp_dying = False
        self.stomp_death_start_time = 0
        self.original_stomp_death_image = None
        self.original_stomp_facing_right = self.facing_right
        
        self.is_frozen = False 
        self.is_defrosting = False 
        self.frozen_effect_timer = 0
        
        self.is_aflame = False
        self.aflame_timer_start = 0
        self.is_deflaming = False
        self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.has_ignited_another_enemy_this_cycle = False

        self.is_petrified = False 
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0

        self.set_state('idle')
########## END OF FILE: enemy.py ##########