# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.2 (Refactored into modular handlers, wall collision fix integrated)
Defines the Player class, handling core attributes.
Delegates state, animation, physics, collisions, input, combat, and network handling
to respective handler modules.
"""
import pygame
import os
import sys
import math

from utils import PrintLimiter
import constants as C
from assets import load_all_player_animations

# Import NEW handler functions
from player_state_handler import set_player_state
from player_animation_handler import update_player_animation
from player_movement_physics import update_player_core_logic # This now contains the main update loop logic
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)

# Import EXISTING handler functions (these were already external calls)
from player_input_handler import process_player_input_logic
from player_combat_handler import (fire_player_fireball, check_player_attack_collisions, 
                                   player_take_damage, player_self_inflict_damage, player_heal_to_full)
from player_network_handler import (get_player_network_data, set_player_network_data, 
                                    handle_player_network_input, get_player_input_state_for_network)


class Player(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True
        # print(f"DEBUG Player (init P{self.player_id}): Initializing at ({start_x}, {start_y})")

        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info ({self.player_id}): Unrecognized ID. Defaulting to player1 assets.")
        
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        if self.animations is None:
            print(f"CRITICAL Player Init Error ({self.player_id}): Failed to load critical animations. Player invalid.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.is_dead = True; self._valid_init = False; return

        try: self.standard_height = self.animations['idle'][0].get_height()
        except (KeyError, IndexError, TypeError): self.standard_height = 60

        self._last_facing_right = True
        self._last_state_for_debug = "init"
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()

        idle_frames = self.animations.get('idle')
        if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
        else:
            self.image = pygame.Surface((30,40)); self.image.fill(C.RED)
            self._valid_init = False; return
        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        
        self.pos = pygame.math.Vector2(start_x, start_y)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY)
        self.facing_right = True
        self.on_ground = False
        self.on_ladder = False
        self.can_grab_ladder = False
        self.touching_wall = 0
        self.can_wall_jump = False
        self.wall_climb_timer = 0

        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = getattr(C, 'PLAYER_DASH_DURATION', 150)
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = getattr(C, 'PLAYER_ROLL_DURATION', 300)
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = getattr(C, 'PLAYER_SLIDE_DURATION', 400)
        
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300
        self.attack_type = 0
        self.can_combo = False; self.combo_window = getattr(C, 'PLAYER_COMBO_WINDOW', 150)
        self.wall_climb_duration = getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500)
        self.is_taking_hit = False; self.hit_timer = 0
        self.hit_duration = getattr(C, 'PLAYER_HIT_STUN_DURATION', 300)
        self.hit_cooldown = getattr(C, 'PLAYER_HIT_COOLDOWN', 600)
        self.is_dead = False
        self.death_animation_finished = False
        self.state_timer = 0

        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30)

        self.is_trying_to_move_left = False
        self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False
        self.is_holding_crouch_ability_key = False

        self.fireball_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0)
        self.projectile_sprites_group = None
        self.all_sprites_group = None
        
        self.fireball_key = None 
        if self.player_id == 1: self.fireball_key = getattr(C, 'P1_FIREBALL_KEY', pygame.K_1)
        elif self.player_id == 2: self.fireball_key = getattr(C, 'P2_FIREBALL_KEY', pygame.K_0)
        # print(f"DEBUG Player (init P{self.player_id}): Init completed. _valid_init: {self._valid_init}")

    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group, 
                                        all_sprites_group: pygame.sprite.Group):
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

    # --- Delegated Methods ---
    def set_state(self, new_state: str):
        set_player_state(self, new_state)

    def animate(self):
        update_player_animation(self)

    def handle_input(self, keys_pressed_state, pygame_event_list):
        default_key_config = {
            'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
            'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
            'roll': pygame.K_LCTRL, 'interact': pygame.K_e
        }
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, default_key_config)

    def handle_mapped_input(self, keys_pressed_state, pygame_event_list, key_map_dict):
        process_player_input_logic(self, keys_pressed_state, pygame_event_list, key_map_dict)

    def fire_fireball(self):
        fire_player_fireball(self)

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

    # --- Collision Check Delegations ---
    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        check_player_platform_collisions(self, direction, platforms_group)

    def check_ladder_collisions(self, ladders_group: pygame.sprite.Group):
        check_player_ladder_collisions(self, ladders_group)

    def check_character_collisions(self, direction: str, characters_list: list):
        # This method will return a boolean, so capture it if needed in update_player_core_logic
        return check_player_character_collisions(self, direction, characters_list)
        
    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        check_player_hazard_collisions(self, hazards_group)

    # --- Core Update Method ---
    def update(self, dt_sec, platforms_group, ladders_group, hazards_group, 
               other_players_sprite_list, enemies_sprite_list):
        update_player_core_logic(self, dt_sec, platforms_group, ladders_group, hazards_group,
                                 other_players_sprite_list, enemies_sprite_list)

    def reset_state(self, spawn_position_tuple: tuple):
        # print(f"DEBUG Player (reset_state P{self.player_id}): Resetting state. Current valid: {self._valid_init}")
        if not self._valid_init: 
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True
                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30,40)); self.image.fill(C.RED)
            else: return
        
        self.pos = pygame.math.Vector2(spawn_position_tuple[0], spawn_position_tuple[1])
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)
        
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True
        
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0; self.fireball_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0)

        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)
        
        set_player_state(self, 'idle')
        # print(f"DEBUG Player (reset_state P{self.player_id}): Reset complete. Pos: {self.pos}, HP: {self.current_health}")