# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.4 (Added can_stand_up and collision height attributes)
Defines the Player class, handling core attributes, collision heights, and
the ability to check for safe uncrouching.
Delegates state, animation, physics, collisions, input, combat, and network handling
to respective handler modules.
"""
import pygame
from typing import Dict, List, Optional # For type hinting
import os # Not directly used but often kept for consistency if path ops were needed
import sys # Not directly used but often kept
import math # For math operations if any become complex

from utils import PrintLimiter # Assuming PrintLimiter is in utils.py
import constants as C
from assets import load_all_player_animations

# Import NEW handler functions
from player_state_handler import set_player_state
from player_animation_handler import update_player_animation
from player_movement_physics import update_player_core_logic # This will now handle uncrouch check
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)

# Import EXISTING handler functions
from player_input_handler import process_player_input_logic
from player_combat_handler import ( # fire_player_fireball is now part of _generic_fire_projectile
                                   check_player_attack_collisions,
                                   player_take_damage, player_self_inflict_damage, player_heal_to_full)
from player_network_handler import (get_player_network_data, set_player_network_data,
                                    handle_player_network_input, get_player_input_state_for_network)

# Import projectile types
from projectiles import Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard


class Player(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True # Assume valid until a critical failure

        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info (ID: {self.player_id}): Unrecognized ID. Defaulting to player1 assets.")
            # asset_folder will remain as player1 default

        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        if self.animations is None:
            print(f"CRITICAL Player Init Error (ID: {self.player_id}): Failed to load critical animations from '{asset_folder}'. Player invalid.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.pos = pygame.math.Vector2(self.rect.midbottom)
            self.is_dead = True
            self._valid_init = False
            # Collision heights will be 0 if animations are None
            self.standing_collision_height = 0
            self.crouching_collision_height = 0
            self.standard_height = 0 # Deprecated, use standing_collision_height
            return # Stop initialization

        # --- Initialize Collision Heights ---
        self.standing_collision_height = 0
        self.crouching_collision_height = 0

        try:
            if self.animations.get('idle') and self.animations['idle']:
                self.standing_collision_height = self.animations['idle'][0].get_height()
            else:
                self.standing_collision_height = 60 # Default fallback
                if Player.print_limiter.can_print(f"player_init_no_idle_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'idle' animation missing for standing height. Using default {self.standing_collision_height}.")

            if self.animations.get('crouch') and self.animations['crouch']:
                self.crouching_collision_height = self.animations['crouch'][0].get_height()
            else:
                self.crouching_collision_height = self.standing_collision_height // 2 # Educated guess
                if Player.print_limiter.can_print(f"player_init_no_crouch_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'crouch' animation missing for crouching height. Using default {self.crouching_collision_height}.")

            if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
               self.crouching_collision_height >= self.standing_collision_height:
                print(f"Player {self.player_id} CRITICAL: Collision heights invalid after init. "
                      f"Standing: {self.standing_collision_height}, Crouching: {self.crouching_collision_height}")
                self._valid_init = False # Player might not behave correctly
                # Still set a default image below
        except Exception as e:
            print(f"Player {self.player_id} Error setting collision heights: {e}")
            self.standing_collision_height = 60 # Fallback values
            self.crouching_collision_height = 30
            self._valid_init = False

        self.standard_height = self.standing_collision_height # For compatibility if anything still uses it

        # --- Animation and Visual State ---
        self._last_facing_right = True
        self._last_state_for_debug = "init"
        self.state = 'idle' # Initial logical state
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()

        # Set initial image and rect (based on standing)
        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and len(initial_idle_frames) > 0:
            self.image = initial_idle_frames[0]
        else: # Fallback if 'idle' animation is somehow missing after successful load_all_player_animations
            self.image = pygame.Surface((30, self.standing_collision_height or 60)) # Use determined/fallback standing height
            self.image.fill(C.RED) # Error color
            print(f"Player {self.player_id} CRITICAL: 'idle' animation frames missing for initial image. Using RED placeholder.")
            self._valid_init = False # Mark as potentially problematic

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(self.rect.midbottom) # Player's true position (float, anchored at midbottom)

        # --- Physics and Movement State ---
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = True
        self.on_ground = False
        self.on_ladder = False
        self.can_grab_ladder = False # True if player is near a ladder and can choose to climb
        self.touching_wall = 0  # -1 for left, 1 for right, 0 for none
        self.can_wall_jump = False
        self.wall_climb_timer = 0 # Timestamp for when wall climb started

        # --- Ability/Action States & Timers ---
        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = getattr(C, 'PLAYER_DASH_DURATION', 150)
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = getattr(C, 'PLAYER_ROLL_DURATION', 300)
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = getattr(C, 'PLAYER_SLIDE_DURATION', 400)

        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300 # attack_duration might be set by state handler
        self.attack_type = 0 # e.g., 1 for primary, 2 for secondary, 3 for combo, 4 for crouch
        self.can_combo = False; self.combo_window = getattr(C, 'PLAYER_COMBO_WINDOW', 150) # ms
        self.wall_climb_duration = getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500) # ms

        self.is_taking_hit = False; self.hit_timer = 0 # Timestamp for when hit stun started
        self.hit_duration = getattr(C, 'PLAYER_HIT_STUN_DURATION', 300) # How long hit animation plays / player is stunned
        self.hit_cooldown = getattr(C, 'PLAYER_HIT_COOLDOWN', 600) # Invulnerability period after being hit

        self.is_dead = False
        self.death_animation_finished = False
        self.state_timer = 0 # Timestamp for when the current logical state started

        # --- Health ---
        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30) # Default size, positioned in combat_handler

        # --- Input Intentions (set by input handler) ---
        self.is_trying_to_move_left = False
        self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False # e.g., holding 'up' on a wall or ladder
        self.is_holding_crouch_ability_key = False# e.g., holding 'down'

        # --- Projectile Firing Attributes ---
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Default aim direction
        self.projectile_sprites_group: Optional[pygame.sprite.Group] = None # Set by game_setup
        self.all_sprites_group: Optional[pygame.sprite.Group] = None      # Set by game_setup

        # --- Weapon Keys (can be customized per player instance) ---
        self.fireball_key: Optional[int] = None
        self.poison_key: Optional[int] = None
        self.bolt_key: Optional[int] = None
        self.blood_key: Optional[int] = None
        self.ice_key: Optional[int] = None

        if self.player_id == 1:
            self.fireball_key = pygame.K_1
            self.poison_key = pygame.K_2
            self.bolt_key = pygame.K_3
            self.blood_key = pygame.K_4
            self.ice_key = pygame.K_5
        elif self.player_id == 2: # Player 2 key setup
            self.fireball_key = getattr(C, 'P2_FIREBALL_KEY', pygame.K_KP_1)
            self.poison_key = getattr(C, 'P2_POISON_KEY', pygame.K_KP_2)
            self.bolt_key = getattr(C, 'P2_BOLT_KEY', pygame.K_KP_3)
            self.blood_key = getattr(C, 'P2_BLOOD_KEY', pygame.K_KP_4)
            self.ice_key = getattr(C, 'P2_ICE_KEY', pygame.K_KP_5)

        if not self._valid_init:
            print(f"Player {self.player_id}: Initialization was marked as invalid. Player might not function correctly.")


    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group,
                                        all_sprites_group: pygame.sprite.Group):
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

    def can_stand_up(self, platforms_group: pygame.sprite.Group) -> bool:
        """
        Checks if the player can stand up from a crouching position without
        colliding with any platforms above them.
        """
        if not self.is_crouching or not self._valid_init:
            return True # Not crouching or invalid, so no restriction on standing

        if self.standing_collision_height <= self.crouching_collision_height:
            if Player.print_limiter.can_print(f"can_stand_up_height_issue_{self.player_id}"):
                print(f"Player {self.player_id} Info: Standing height ({self.standing_collision_height}) "
                      f"<= crouching height ({self.crouching_collision_height}). Assuming can stand.")
            return True # Logical error in heights, allow standing to avoid getting stuck

        # Current position of the player's feet (bottom of their rect)
        current_feet_y = self.rect.bottom
        current_center_x = self.rect.centerx
        # Assume standing width is similar to crouching width, or get from standing animation frame
        # For simplicity, use current rect's width. If it changes significantly, this needs adjustment.
        standing_width = self.rect.width

        # Create a temporary rectangle representing the player in a standing position,
        # anchored by their current feet position.
        potential_standing_rect = pygame.Rect(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.bottom = current_feet_y
        potential_standing_rect.centerx = current_center_x

    # --- Delegated Methods to Handlers ---
    def set_state(self, new_state: str):
        set_player_state(self, new_state)

    def animate(self):
        update_player_animation(self)

    def handle_input(self, keys_pressed_state, pygame_event_list): # For local P1 typically
        default_key_config = { # P1 Default
            'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
            'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
            'roll': pygame.K_LCTRL, 'interact': pygame.K_e
        }
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, default_key_config)

    def handle_mapped_input(self, keys_pressed_state, pygame_event_list, key_map_dict): # For Couch P2
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, key_map_dict)

    def _generic_fire_projectile(self, projectile_class, cooldown_attr_name, cooldown_const, projectile_config_name):
        if not self._valid_init or self.is_dead or not self.alive(): return
        if self.projectile_sprites_group is None or self.all_sprites_group is None:
            if self.print_limiter.can_print(f"player_{self.player_id}_fire_{projectile_config_name}_no_group_ref"):
                print(f"Player {self.player_id}: Cannot fire {projectile_config_name}, projectile/all_sprites group not set.")
            return

        current_time_ms = pygame.time.get_ticks()
        last_fire_time = getattr(self, cooldown_attr_name, 0)

        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)
            spawn_x, spawn_y = self.rect.centerx, self.rect.centery
            current_aim_direction = self.fireball_last_input_dir.copy()
            if current_aim_direction.length_squared() == 0:
                current_aim_direction.x = 1.0 if self.facing_right else -1.0
                current_aim_direction.y = 0.0

            proj_dims = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10,10))
            offset_distance = (self.rect.width / 2) + (proj_dims[0] / 2) - 10
            if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x):
                offset_distance = (self.rect.height / 2) + (proj_dims[1] / 2) - 10

            if current_aim_direction.length_squared() > 0:
                offset_vector = current_aim_direction.normalize() * offset_distance
                spawn_x += offset_vector.x
                spawn_y += offset_vector.y

            new_projectile = projectile_class(spawn_x, spawn_y, current_aim_direction, self)
            self.projectile_sprites_group.add(new_projectile)
            self.all_sprites_group.add(new_projectile)
        # else: pass # On cooldown

    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')

    def check_attack_collisions(self, list_of_targets):
        check_player_attack_collisions(self, list_of_targets)

    def take_damage(self, damage_amount_taken):
        player_take_damage(self, damage_amount_taken)

    def self_inflict_damage(self, damage_amount_to_self):
        player_self_inflict_damage(self, damage_amount_to_self)

    def heal_to_full(self):
        player_heal_to_full(self)

    def get_network_data(self):
        return get_player_network_data(self)

    def set_network_data(self, received_network_data):
        set_player_network_data(self, received_network_data)

    def handle_network_input(self, network_input_data_dict):
        handle_player_network_input(self, network_input_data_dict)

    def get_input_state_for_network(self, keys_state, events, key_map):
        return get_player_input_state_for_network(self, keys_state, events, key_map)

    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        check_player_platform_collisions(self, direction, platforms_group)

    def check_ladder_collisions(self, ladders_group: pygame.sprite.Group):
        check_player_ladder_collisions(self, ladders_group)

    def check_character_collisions(self, direction: str, characters_list: list):
        return check_player_character_collisions(self, direction, characters_list)

    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        check_player_hazard_collisions(self, hazards_group)

    def update(self, dt_sec, platforms_group, ladders_group, hazards_group,
               other_players_sprite_list, enemies_sprite_list):
        update_player_core_logic(self, dt_sec, platforms_group, ladders_group, hazards_group,
                                 other_players_sprite_list, enemies_sprite_list)

    def reset_state(self, spawn_position_tuple: tuple):
        # If player was invalid due to animation load fail, try to re-validate
        if not self._valid_init and self.animations is None:
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True # Now potentially valid
                # Re-initialize collision heights
                try:
                    self.standing_collision_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
                    self.crouching_collision_height = self.animations['crouch'][0].get_height() if self.animations.get('crouch') else 30
                    if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
                       self.crouching_collision_height >= self.standing_collision_height:
                        self._valid_init = False
                except: self._valid_init = False

                # Re-initialize image based on newly loaded animations
                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30, self.standing_collision_height or 60)); self.image.fill(C.RED)
            else:
                # Still couldn't load animations, remain invalid
                if Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"):
                    print(f"Player {self.player_id} Error: Failed to load animations during reset. Player remains invalid.")
                return

        # --- Actual Reset Logic ---
        self.pos = pygame.math.Vector2(spawn_position_tuple) # spawn_position_tuple is midbottom
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y)) # Sync rect to new pos
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)

        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True

        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;

        # Reset projectile cooldowns
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Default aim

        # Ensure image is not transparent if it was faded out
        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)

        set_player_state(self, 'idle') # Set to default state, which also updates animation/rect