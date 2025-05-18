# enemy_base.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.1
Defines the EnemyBase class, the foundational class for enemies.
Handles core attributes like ID, color, basic physics properties,
health, and animation dictionary loading.
Also includes common asset loading for stone/smashed states.
"""
import pygame
import random
import math
import os

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_BASE: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func
# --- End Logger ---

import constants as C
from assets import load_all_player_animations, load_gif_frames, resource_path
# from tiles import Lava # Not directly used in base, but good to keep if other base methods might need it

class EnemyBase(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y, patrol_area=None, enemy_id=None, color_name=None):
        super().__init__()
        self.spawn_pos = pygame.math.Vector2(start_x, start_y)
        self.patrol_area = patrol_area
        self.enemy_id = enemy_id if enemy_id is not None else id(self) # Unique ID
        self._valid_init = True # Flag to check if initialization was successful
        self.color_name = "unknown" # Will be set below

        character_base_asset_folder = 'characters'
        available_enemy_colors = ['cyan', 'green', 'pink', 'purple', 'gray', 'yellow', 'orange']

        if not available_enemy_colors:
             warning(f"EnemyBase Warning (ID: {self.enemy_id}): No enemy colors defined! Defaulting to 'player1' assets for structure.")
             available_enemy_colors = ['player1'] # Fallback for asset loading structure

        if color_name and color_name in available_enemy_colors:
            self.color_name = color_name
            debug(f"EnemyBase (ID: {self.enemy_id}): Initialized with specified color: {self.color_name}")
        elif color_name:
            warning(f"EnemyBase Warning (ID: {self.enemy_id}): Specified color '{color_name}' not in available_colors. Choosing random from list: {available_enemy_colors}")
            self.color_name = random.choice(available_enemy_colors)
        else:
            self.color_name = random.choice(available_enemy_colors)
            debug(f"EnemyBase (ID: {self.enemy_id}): Initialized with random color: {self.color_name}")

        chosen_enemy_asset_folder = os.path.join(character_base_asset_folder, self.color_name)
        self.animations = load_all_player_animations(relative_asset_folder=chosen_enemy_asset_folder)

        if self.animations is None:
            critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): Failed loading animations from '{chosen_enemy_asset_folder}'. Enemy invalid.")
            self.image = self._create_placeholder_surface(C.BLUE, f"AnimLoadFail-{self.color_name[:3]}")
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self._valid_init = False
            self.is_dead = True # Mark as dead if essential assets fail
            # Initialize essential attributes even on failure to prevent crashes
            self.pos = pygame.math.Vector2(start_x, start_y)
            self.vel = pygame.math.Vector2(0, 0)
            self.acc = pygame.math.Vector2(0, 0)
            self.state = 'idle' # Default state
            self.current_frame = 0
            self.last_anim_update = 0
            self.facing_right = True
            self.on_ground = False
            self.current_health = 0
            self.max_health = 0
            return # Stop further initialization

        self._last_facing_right = True # For animation flipping optimization
        self._last_state_for_debug = "init" # For debugging state changes
        self.state = 'idle'        # Current logical state of the enemy
        self.current_frame = 0     # Current frame index for animation
        self.last_anim_update = pygame.time.get_ticks() # For timing animation updates

        initial_idle_animation = self.animations.get('idle')
        if not initial_idle_animation or not initial_idle_animation[0]:
             warning(f"EnemyBase Warning (ID: {self.enemy_id}, Color: {self.color_name}): 'idle' animation missing or empty. Attempting fallback to first available animation.")
             first_anim_key = next(iter(self.animations), None)
             initial_idle_animation = self.animations.get(first_anim_key) if first_anim_key and self.animations.get(first_anim_key) else None

        if initial_idle_animation and len(initial_idle_animation) > 0:
            self.image = initial_idle_animation[0]
        else:
            self.image = self._create_placeholder_surface(C.BLUE, f"NoIdle-{self.color_name[:3]}")
            critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): No suitable initial animation found after fallbacks. Enemy invalid.")
            self._valid_init = False
            self.is_dead = True

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(start_x, start_y) # Use midbottom as reference
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)))
        self.facing_right = random.choice([True, False])
        self.on_ground = False

        # AI related (can be further managed by enemy_ai_handler.py)
        self.ai_state = 'patrolling' # e.g., 'patrolling', 'chasing', 'attacking', 'idle'
        self.patrol_target_x = start_x # Initial patrol target

        # Combat related (can be further managed by enemy_combat_handler.py)
        self.is_attacking = False
        self.attack_timer = 0 # Timestamp of last attack start
        self.attack_duration = getattr(C, 'ENEMY_ATTACK_STATE_DURATION', getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 500))
        self.attack_type = 0 # e.g., 1 for primary, 2 for secondary
        self.attack_cooldown_timer = 0 # Timestamp of last attack end (for cooldown)
        self.post_attack_pause_timer = 0 # Timestamp for when post-attack pause ends
        self.post_attack_pause_duration = getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200)

        self.is_taking_hit = False # If currently in hit stun animation
        self.hit_timer = 0         # Timestamp of last hit taken
        self.hit_duration = getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)  # Duration of hit stun
        self.hit_cooldown = getattr(C, 'ENEMY_HIT_COOLDOWN', 500)      # Invulnerability after being hit

        self.is_dead = False
        self.death_animation_finished = False
        self.state_timer = 0 # Timestamp for when the current state began

        self.max_health = getattr(C, 'ENEMY_MAX_HEALTH', 80)
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 50, 35) # Default, can be adjusted

        try:
            self.standard_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
        except (KeyError, IndexError, TypeError):
            self.standard_height = 60
            warning(f"EnemyBase (ID: {self.enemy_id}): Could not determine standard_height from idle anim. Defaulting to 60.")

        # Status effect flags & timers (managed by enemy_status_effects.py)
        self.is_stomp_dying = False
        self.stomp_death_start_time = 0
        self.original_stomp_death_image = None # For stomp shrink animation
        self.original_stomp_facing_right = True

        self.is_frozen = False
        self.is_defrosting = False
        self.frozen_effect_timer = 0 # Timestamp for when freeze/defrost started

        self.is_aflame = False
        self.aflame_timer_start = 0 # Timestamp for when aflame started
        self.is_deflaming = False
        self.deflame_timer_start = 0 # Timestamp for when deflame started
        self.aflame_damage_last_tick = 0 # Timestamp for last damage tick from aflame
        self.has_ignited_another_enemy_this_cycle = False # Prevents chain ignition in one frame

        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0 # Timestamp for when smashed animation started
        self.facing_at_petrification = self.facing_right

        # --- Load Common Stone Assets (Shared by all enemies) ---
        stone_common_folder = os.path.join('characters', 'Stone')
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))

        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame_original = loaded_common_stone_frames[0]
        else:
            warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __Stone.png. Using placeholder.")
            self.stone_image_frame_original = self._create_placeholder_surface(C.GRAY, "Stone")
        self.stone_image_frame = self.stone_image_frame_original # Current frame to use (can be flipped)

        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames_original = loaded_common_smashed_frames
        else:
            warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __StoneSmashed.gif. Using placeholder.")
            self.stone_smashed_frames_original = [self._create_placeholder_surface(C.DARK_GRAY, "Smash")]
        self.stone_smashed_frames = list(self.stone_smashed_frames_original) # Current frames to use (can be flipped)

        if not self._valid_init:
            warning(f"EnemyBase (ID: {self.enemy_id}): Initialization was marked as invalid. Enemy might not function correctly.")


    def _create_placeholder_surface(self, color, text="Err"):
        """Creates a placeholder surface for missing animations."""
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
        except Exception as e:
            # Fallback if font rendering fails (e.g. font module not init yet during very early error)
            print(f"ENEMY_BASE PlaceholderFontError: {e}")
        return surf

    def reset(self):
        """
        Resets the enemy to its initial state at its spawn position.
        Specific status effects and state transitions are handled by enemy_state_handler.
        """
        if not self._valid_init:
            # Attempt to re-initialize basic visual components if they were missing
            if not hasattr(self, 'image') or self.image is None:
                 self.image = self._create_placeholder_surface(C.BLUE, f"ResetFail-{getattr(self, 'color_name', '???')[:3]}")
                 self.rect = self.image.get_rect(midbottom=self.spawn_pos)
            warning(f"EnemyBase (ID: {self.enemy_id}): Attempting reset on an invalid enemy.")
            # Even if invalid, try to set some sane defaults to prevent crashes
            self.is_dead = True
            self.current_health = 0


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
        # set_enemy_new_patrol_target(self) # This should be called by the main enemy or AI handler after reset

        # Ensure image is not transparent
        if hasattr(self.image, 'get_alpha') and self.image.get_alpha() is not None and \
           self.image.get_alpha() < 255:
            self.image.set_alpha(255)

        # Reset status effect flags
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
        self.facing_at_petrification = self.facing_right

        # The actual self.set_state('idle') should be called by the main Enemy class
        # after all handlers have had a chance to reset their parts.
        # For the base class, we just ensure the 'state' attribute is set.
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()
        debug(f"EnemyBase (ID: {self.enemy_id}): Core attributes reset.")