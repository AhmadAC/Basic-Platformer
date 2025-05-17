# enemy.py
# -*- coding: utf-8 -*-
## version 1.0.0.18 (Petrified enemies fall with gravity)
"""
Defines the Enemy class, a CPU-controlled character.
Handles AI-driven movement (via enemy_ai_handler), animations, states,
combat (via enemy_combat_handler), and network synchronization
(via enemy_network_handler).
Each instance randomly selects a color variant for its animations if configured.
Petrification turns the enemy to stone but doesn't kill it; further damage
is required, which then triggers a smash animation. Petrified enemies are
affected by gravity.
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
    def error_log_func(msg): print(f"ERROR: {msg}") # Renamed to avoid conflict
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func # Assign after local def to avoid shadowing
# --- End Logger ---

import constants as C
from assets import load_all_player_animations, load_gif_frames, resource_path 
from tiles import Lava

from enemy_ai_handler import set_enemy_new_patrol_target, enemy_ai_update
from enemy_combat_handler import check_enemy_attack_collisions 
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
        self.facing_right = random.choice([True, False]) # Initial facing direction
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
        self.is_dead = False # Initially not dead
        self.death_animation_finished = False # For regular death or smashed stone
        self.state_timer = 0
        self.max_health = getattr(C, 'ENEMY_MAX_HEALTH', 80)
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
        
        # Petrification state
        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right # Store facing direction when petrified
        
        # Load common stone assets (shared, not from character-specific folder)
        stone_common_folder = os.path.join('characters', 'Stone')
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))

        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame_original = loaded_common_stone_frames[0] # Store the original loaded frame
        else:
            self.stone_image_frame_original = self._create_placeholder_surface(C.GRAY, "Stone")
        self.stone_image_frame = self.stone_image_frame_original # Initially use the original

        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames_original = loaded_common_smashed_frames # Store original loaded frames
        else:
            self.stone_smashed_frames_original = [self._create_placeholder_surface(C.DARK_GRAY, "Smash")]
        self.stone_smashed_frames = list(self.stone_smashed_frames_original) # Initially use copies


    def _create_placeholder_surface(self, color, text="Err"):
        # Use a somewhat generic size based on TILE_SIZE for consistency
        width = C.TILE_SIZE
        height = int(C.TILE_SIZE * 1.5) # Assuming enemies are taller than wide
        surf = pygame.Surface((width, height)).convert_alpha() 
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: 
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass 
        return surf

    def petrify(self):
        # If already petrified, or truly dead (not just petrified with health), do nothing
        if self.is_petrified or (self.is_dead and not self.is_petrified): 
            return
        debug(f"Enemy {self.enemy_id} is being petrified.")
        self.is_petrified = True
        self.is_stone_smashed = False 
        # self.is_dead = True # REMOVED - Not dead yet, just stone
        # self.current_health = 0 # REMOVED - Health is not set to 0
        self.vel.x = 0  # Stop horizontal movement
        self.acc.x = 0  # Stop horizontal acceleration
        # self.vel.y and self.acc.y (gravity) remain for falling
        self.facing_at_petrification = self.facing_right # Store current facing direction
        self.is_attacking = False
        self.is_taking_hit = False # Cannot be hit-stunned while petrified
        self.is_frozen = False; self.is_defrosting = False
        self.is_aflame = False; self.is_deflaming = False
        # self.death_animation_finished = True # REMOVED
        
        self.set_state('petrified')

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified: # ADDED self.is_petrified
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
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified: # ADDED self.is_petrified
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
        current_ticks_ms = pygame.time.get_ticks()

        # If petrified (but not smashed), only allow transitions to 'smashed', 'petrified' (refresh), or 'idle' (for reset)
        if self.is_petrified and not self.is_stone_smashed and \
           new_state not in ['petrified', 'smashed', 'idle']: 
            debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' "
                  f"due to being petrified (and not smashed).")
            return
        
        # If smashed, only allow 'smashed' (refresh) or 'idle' (for reset)
        if self.is_stone_smashed and new_state not in ['smashed', 'idle']:
            debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' "
                  f"due to being stone_smashed.")
            return

        # Block other status effects if petrified (unless it's a reset to idle)
        if self.is_petrified and new_state not in ['petrified', 'smashed', 'idle']:
            if new_state in ['frozen', 'defrost', 'aflame', 'deflame', 'hit', 'stomp_death']:
                debug(f"Enemy {self.enemy_id}: Blocked state change from '{self.state}' to '{new_state}' due to petrification.")
                return

        animation_key_to_validate = new_state
        # Map logical states to animation keys (some states might share an animation or use placeholders)
        if new_state in ['chasing', 'patrolling']: animation_key_to_validate = 'run'
        elif 'attack' in new_state: animation_key_to_validate = new_state # e.g., 'attack', 'attack_nm'
        
        is_new_anim_special_effect = animation_key_to_validate in ['frozen', 'defrost', 'aflame', 'deflame'] # Removed petrified/smashed here
        if is_new_anim_special_effect and self.color_name != 'green':
            debug(f"Enemy {self.enemy_id} ({self.color_name}): Cannot use state '{animation_key_to_validate}', not green. Defaulting to idle.")
            animation_key_to_validate = 'idle' 
        
        # For petrified/smashed, the actual animation frames come from self.stone_image_frame / self.stone_smashed_frames,
        # so we use 'stone' / 'stone_smashed' as "logical" animation keys here for validation,
        # but Enemy.animate will handle the actual image source.
        logical_anim_key_for_validation = animation_key_to_validate
        if new_state == 'petrified': logical_anim_key_for_validation = 'stone' 
        elif new_state == 'smashed': logical_anim_key_for_validation = 'stone_smashed'

        # Animation validation (except for 'stone' and 'stone_smashed' which use direct image/frame attributes)
        if logical_anim_key_for_validation not in ['stone', 'stone_smashed']:
            if logical_anim_key_for_validation not in self.animations or not self.animations[logical_anim_key_for_validation]:
                warning(f"Enemy Warning (ID: {self.enemy_id}): Animation for key '{logical_anim_key_for_validation}' (from logical: '{new_state}') missing. Trying 'idle'.")
                logical_anim_key_for_validation = 'idle' # This becomes the animation key if original fails
                if 'idle' not in self.animations or not self.animations['idle']:
                     critical(f"Enemy CRITICAL (ID: {self.enemy_id}): Cannot find valid 'idle' animation. Halting state change for '{new_state}'.")
                     return
            animation_key_to_validate = logical_anim_key_for_validation # Use the validated/fallen-back key

        # Determine if state can change
        can_change_state_now = (self.state != new_state or new_state in ['death', 'stomp_death', 'frozen', 'defrost', 'aflame', 'deflame', 'petrified', 'smashed'])
        if self.is_dead and self.death_animation_finished: # If truly game-over dead
             if new_state not in ['idle']: # Allow reset to idle if it was dead and finished
                can_change_state_now = False

        if can_change_state_now:
            self._last_state_for_debug = new_state 
            if 'attack' not in new_state: self.is_attacking = False; self.attack_type = 0
            if new_state != 'hit': self.is_taking_hit = False

            # Clear conflicting status effects
            if new_state != 'frozen' and self.is_frozen: self.is_frozen = False
            if new_state != 'defrost' and self.is_defrosting: self.is_defrosting = False
            if new_state != 'aflame' and self.is_aflame: self.is_aflame = False
            if new_state != 'deflame' and self.is_deflaming: self.is_deflaming = False
            
            # If changing from petrified/smashed to something else (e.g. reset to 'idle'), clear these flags.
            if (self.is_petrified or self.is_stone_smashed) and new_state not in ['petrified', 'smashed']:
                self.is_petrified = False
                self.is_stone_smashed = False
                # is_dead and death_animation_finished would be handled by reset() if it's a reset

            self.state = new_state
            self.current_frame = 0
            self.last_anim_update = current_ticks_ms
            self.state_timer = current_ticks_ms

            # State-specific initializations
            if new_state == 'frozen': 
                self.is_frozen = True; self.is_defrosting = False; self.is_aflame = False; self.is_deflaming = False
                self.frozen_effect_timer = current_ticks_ms; self.vel.xy = 0,0; self.acc.x = 0
            elif new_state == 'defrost': 
                self.is_defrosting = True; self.is_frozen = False; self.is_aflame = False; self.is_deflaming = False
                self.frozen_effect_timer = current_ticks_ms; self.vel.xy = 0,0; self.acc.x = 0
            elif new_state == 'aflame':
                self.is_aflame = True; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False 
                self.aflame_timer_start = current_ticks_ms; self.aflame_damage_last_tick = current_ticks_ms
                self.has_ignited_another_enemy_this_cycle = False
            elif new_state == 'deflame':
                self.is_deflaming = True; self.is_aflame = False; self.is_frozen = False; self.is_defrosting = False
                self.deflame_timer_start = current_ticks_ms
            elif new_state == 'petrified': # Initial petrification (not smashed yet)
                self.is_petrified = True; self.is_stone_smashed = False
                self.vel.x = 0; self.acc.x = 0 # Stop horizontal
                self.acc.y = getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)) # Ensure gravity is on
                # self.facing_at_petrification was already set when petrify() was called
                self.stone_image_frame = self.stone_image_frame_original # Ensure using the base stone image
                if not self.facing_at_petrification: # Flip the base stone image if needed
                    self.stone_image_frame = pygame.transform.flip(self.stone_image_frame_original, True, False)
                # self.is_dead is NOT set here, health is preserved
            elif new_state == 'smashed': # Transition to smashed (means health was 0)
                self.is_stone_smashed = True; self.is_petrified = True 
                self.is_dead = True # Confirmed dead
                self.death_animation_finished = False # Smashed animation needs to play
                self.stone_smashed_timer_start = current_ticks_ms # Could be already set by take_damage
                self.vel.xy = 0,0; self.acc.xy = 0,0 # Smashed doesn't fall
                # Prepare smashed frames based on facing direction at petrification
                self.stone_smashed_frames = []
                for frame in self.stone_smashed_frames_original:
                    if not self.facing_at_petrification:
                        self.stone_smashed_frames.append(pygame.transform.flip(frame, True, False))
                    else:
                        self.stone_smashed_frames.append(frame)

            elif new_state == 'idle':
                pass # General cleanup already done if transitioning from special states
            elif 'attack' in new_state:
                self.is_attacking = True; self.attack_type = 1 # Assuming type 1 for generic 'attack'
                self.attack_timer = current_ticks_ms; self.vel.x = 0
            elif new_state == 'hit':
                 self.is_taking_hit = True; self.hit_timer = self.state_timer
                 self.vel.x *= -0.5
                 self.vel.y = getattr(C, 'ENEMY_HIT_BOUNCE_Y', getattr(C, 'PLAYER_JUMP_STRENGTH', -10) * 0.3)
                 self.is_attacking = False
            elif new_state == 'death' or new_state == 'stomp_death': # Regular death or stomp death
                 self.is_dead = True; self.vel.x = 0; self.vel.y = 0
                 self.acc.xy = 0, 0; self.current_health = 0
                 self.death_animation_finished = False
                 # Clear other effects on death
                 self.is_frozen = False; self.is_defrosting = False 
                 self.is_aflame = False; self.is_deflaming = False 
                 self.is_petrified = False; self.is_stone_smashed = False # Death overrides petrification
                 if new_state == 'stomp_death' and not self.is_stomp_dying: 
                     self.stomp_kill() 

            self.animate()
        elif not self.is_dead: # If state didn't change but not dead, log current state
             self._last_state_for_debug = self.state


    def animate(self):
        if not self._valid_init or not hasattr(self, 'animations'): return
        
        can_animate = self.alive() or \
                      (self.is_dead and not self.death_animation_finished) or \
                      self.is_petrified

        if not can_animate:
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

        determined_animation_key = 'idle' # Default
        current_animation_frames_list = None

        # Determine animation key based on state
        if self.is_petrified:
            if self.is_stone_smashed:
                determined_animation_key = 'stone_smashed' 
                current_animation_frames_list = self.stone_smashed_frames # Already pre-flipped if needed
            else: 
                determined_animation_key = 'stone'
                current_animation_frames_list = [self.stone_image_frame] if self.stone_image_frame else [] # Already pre-flipped
        elif self.is_dead: # Regular death
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
        
        # Green specific animations
        is_new_anim_green_specific_anim = determined_animation_key in ['frozen', 'defrost', 'aflame', 'deflame'] 
        if is_new_anim_green_specific_anim and self.color_name != 'green':
            determined_animation_key = 'idle' 
            current_animation_frames_list = self.animations.get(determined_animation_key)

        # Fallback if determined key has no frames (should be rare if 'stone'/'stone_smashed' handled above)
        if not current_animation_frames_list: 
            if determined_animation_key not in ['stone', 'stone_smashed']: # Don't warn for stone/smashed if they correctly use instance frames
                warning(f"Enemy Animate Warning (ID: {self.enemy_id}): Key '{determined_animation_key}' invalid for state '{self.state}'. Defaulting to 'idle'.")
            determined_animation_key = 'idle'
            current_animation_frames_list = self.animations.get(determined_animation_key)

        if not current_animation_frames_list:
            if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE)
            critical(f"Enemy CRITICAL Animate (ID: {self.enemy_id}): No frames for '{determined_animation_key}' (state: {self.state})")
            return

        # --- Frame Advancement Logic ---
        if current_time_ms - self.last_anim_update > animation_frame_duration_ms:
            self.last_anim_update = current_time_ms
            
            # Only advance frame if not static petrified (i.e., petrified AND NOT smashed)
            if not (self.is_petrified and not self.is_stone_smashed):
                self.current_frame += 1

            if self.current_frame >= len(current_animation_frames_list):
                if self.is_dead and not self.is_petrified: # Regular death animation finished
                    self.current_frame = len(current_animation_frames_list) - 1
                    self.death_animation_finished = True 
                    # Allow image to be set to final frame, don't return yet
                elif self.is_stone_smashed: # Smashed animation finished (reached end)
                    self.current_frame = len(current_animation_frames_list) - 1
                    self.death_animation_finished = True # Mark as visually "done" for removal logic
                elif self.state == 'hit':
                    self.set_state('idle' if self.on_ground else 'fall')
                    return # State changed, re-animate will be called or handled
                else: # Loop other animations
                    self.current_frame = 0
        
        # If petrified (but not smashed), force to first frame of stone image
        if self.is_petrified and not self.is_stone_smashed:
            self.current_frame = 0
        
        # Boundary check for current_frame before accessing list
        if not current_animation_frames_list or self.current_frame < 0 or \
            self.current_frame >= len(current_animation_frames_list):
            self.current_frame = 0 # Default to first frame
            if not current_animation_frames_list: # Should not happen if previous checks passed
                if hasattr(self, 'image') and self.image: self.image.fill(C.BLUE); return
        
        image_for_this_frame = current_animation_frames_list[self.current_frame]
        
        # Flipping for regular animations
        # For petrified/smashed states, the frames are already pre-oriented in self.stone_image_frame / self.stone_smashed_frames by set_state
        current_display_facing_right = self.facing_right
        if self.is_petrified: # Use the facing direction at the moment of petrification for stone visuals
            current_display_facing_right = self.facing_at_petrification
        
        if not self.is_petrified and not current_display_facing_right: # Standard flip for non-petrified states
            image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)
        # Stone/Smashed images are already oriented (self.stone_image_frame and self.stone_smashed_frames are set in set_state)

        if self.image is not image_for_this_frame or self._last_facing_right != current_display_facing_right:
            old_enemy_midbottom_pos = self.rect.midbottom
            self.image = image_for_this_frame
            self.rect = self.image.get_rect(midbottom=old_enemy_midbottom_pos)
            self._last_facing_right = current_display_facing_right # Track the displayed facing direction


    def stomp_kill(self):
        if self.is_dead or self.is_stomp_dying or self.is_petrified: # Cannot stomp a petrified enemy
            return
        debug(f"Enemy {self.enemy_id}: Stomp kill initiated.")
        self.current_health = 0
        self.is_dead = True
        self.is_stomp_dying = True
        self.death_animation_finished = False # Stomp anim needs to play
        self.is_frozen = False; self.is_defrosting = False 
        self.is_aflame = False; self.is_deflaming = False 
        self.stomp_death_start_time = pygame.time.get_ticks()

        self.original_stomp_death_image = self.image.copy()
        self.original_stomp_facing_right = self.facing_right

        self.vel.xy = 0,0
        self.acc.xy = 0,0
        self.set_state('stomp_death') # Ensure state is set for animation

    def _ai_update(self, players_list_for_targeting):
        enemy_ai_update(self, players_list_for_targeting)

    def _check_attack_collisions(self, player_target_list_for_combat):
        check_enemy_attack_collisions(self, player_target_list_for_combat)

    def take_damage(self, damage_amount_taken): 
        if not self._valid_init or (self.is_dead and self.death_animation_finished and not self.is_stone_smashed): # If truly dead and anim done (and not just about to smash), ignore
            return

        if self.is_petrified:
            if self.is_stone_smashed: # Already smashed, animating, ignore further damage
                return 
            
            # Is petrified but not smashed yet. Take damage.
            self.current_health -= damage_amount_taken
            self.current_health = max(0, self.current_health)
            debug(f"Petrified Enemy {self.enemy_id} took {damage_amount_taken} damage. Health: {self.current_health}")

            if self.current_health <= 0:
                debug(f"Petrified Enemy {self.enemy_id} health reached 0. Smashing.")
                self.is_stone_smashed = True
                self.is_dead = True # Now it's considered truly "game over" dead
                self.death_animation_finished = False # Smash animation needs to play
                self.stone_smashed_timer_start = pygame.time.get_ticks()
                self.set_state('smashed')
            # No 'hit' state or visual change if just taking damage while petrified (not smashed yet)
            return # Handled petrified damage

        # --- Original logic for non-petrified enemies ---
        current_time_ms = pygame.time.get_ticks()
        if (self.is_taking_hit and current_time_ms - self.hit_timer < self.hit_cooldown) or \
            self.is_frozen or self.is_defrosting: # Cannot take damage if frozen/defrosting
            return

        self.current_health -= damage_amount_taken
        self.current_health = max(0, self.current_health) 

        if self.current_health <= 0: 
            if not self.is_dead: # Only set to 'death' if not already in a death process
                self.set_state('death') 
        else: # Health > 0
            if not (self.state == 'hit' and current_time_ms - self.state_timer < getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)):
                 self.set_state('hit') 

    def get_network_data(self):
        return get_enemy_network_data(self)

    def set_network_data(self, received_network_data):
        set_enemy_network_data(self, received_network_data)


    def update(self, dt_sec, players_list_for_logic, platforms_group, hazards_group, all_enemies_list):
        if not self._valid_init: return

        current_time_ms = pygame.time.get_ticks() 

        # --- Petrified and Smashed State Handling (Overrides other logic) ---
        if self.is_stone_smashed:
            if self.death_animation_finished or \
               (current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS): 
                debug(f"Smashed stone Enemy {self.enemy_id} duration/animation ended. Killing.")
                self.kill()
                return
            self.animate() 
            return 
        
        if self.is_petrified: # Is petrified but not smashed
            # Apply gravity
            self.vel.y += self.acc.y # acc.y should be gravity
            self.vel.y = min(self.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18)) # Terminal velocity
            
            self.on_ground = False # Reset before y-collision check
            self.pos.y += self.vel.y
            self.rect.bottom = round(self.pos.y)
            self.check_platform_collisions('y', platforms_group) # Check for landing
            self.pos.y = self.rect.bottom # Sync pos from rect after collision
            
            self.animate() # Will show static stone image (potentially flipped)
            return 
        
        # --- Regular Update Logic (if not petrified) ---
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
                self.set_state('deflame') 
            elif current_time_ms - self.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
                self.aflame_damage_last_tick = current_time_ms
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
                self.set_state('idle') 

        if self.is_stomp_dying:
            self.animate(); return 

        if self.is_dead: # REGULAR death (not petrified and not smashed yet)
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
            if current_time_ms - (self.frozen_effect_timer) > (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS): 
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
                if self.vel.y > 0: # Moving Down
                    if self.rect.bottom > platform_sprite.rect.top and \
                       (self.pos.y - self.vel.y) <= platform_sprite.rect.top + 1: 
                         self.rect.bottom = platform_sprite.rect.top
                         self.on_ground = True; self.vel.y = 0
                elif self.vel.y < 0: # Moving Up
                    if self.rect.top < platform_sprite.rect.bottom and \
                       ((self.pos.y - self.standard_height) - self.vel.y) >= platform_sprite.rect.bottom -1 : 
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

        # Reset petrification flags
        self.is_petrified = False 
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right # Reset this too

        self.set_state('idle')