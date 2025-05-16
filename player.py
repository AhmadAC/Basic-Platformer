########## START OF FILE: player.py ##########

# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.3 (Standardized pos/rect sync to midbottom, refined wall collision re-check)
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
from player_movement_physics import update_player_core_logic
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)

# Import EXISTING handler functions
from player_input_handler import process_player_input_logic
from player_combat_handler import (fire_player_fireball, check_player_attack_collisions, 
                                   player_take_damage, player_self_inflict_damage, player_heal_to_full)
from player_network_handler import (get_player_network_data, set_player_network_data, 
                                    handle_player_network_input, get_player_input_state_for_network)

# Import new projectile types
from projectiles import Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard


class Player(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True
        
        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info ({self.player_id}): Unrecognized ID. Defaulting to player1 assets.")
        
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        if self.animations is None:
            print(f"CRITICAL Player Init Error ({self.player_id}): Failed to load critical animations. Player invalid.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.pos = pygame.math.Vector2(self.rect.midbottom) # Store midbottom
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
            self.rect = self.image.get_rect(midbottom=(start_x, start_y)) # Set rect before pos
            self.pos = pygame.math.Vector2(self.rect.midbottom)      # Store midbottom
            self._valid_init = False; return
            
        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(self.rect.midbottom) # Store midbottom as float Vector2
        
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

        # Projectile firing attributes
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Aim direction
        self.projectile_sprites_group = None
        self.all_sprites_group = None
        
        # Weapon keys
        self.fireball_key = None 
        self.poison_key = None
        self.bolt_key = None
        self.blood_key = None
        self.ice_key = None

        if self.player_id == 1: 
            self.fireball_key = pygame.K_1
            self.poison_key = pygame.K_2
            self.bolt_key = pygame.K_3
            self.blood_key = pygame.K_4
            self.ice_key = pygame.K_5
        elif self.player_id == 2: # Player 2 key setup (can be different)
            # Example: P2 uses numpad keys or different letter keys
            self.fireball_key = getattr(C, 'P2_FIREBALL_KEY', pygame.K_KP_1) # Fallback to numpad 1
            self.poison_key = getattr(C, 'P2_POISON_KEY', pygame.K_KP_2)
            self.bolt_key = getattr(C, 'P2_BOLT_KEY', pygame.K_KP_3)
            self.blood_key = getattr(C, 'P2_BLOOD_KEY', pygame.K_KP_4)
            self.ice_key = getattr(C, 'P2_ICE_KEY', pygame.K_KP_5)


    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group, 
                                        all_sprites_group: pygame.sprite.Group):
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

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

            spawn_x = self.rect.centerx
            spawn_y = self.rect.centery
            
            current_aim_direction = self.fireball_last_input_dir.copy()
            if current_aim_direction.length_squared() == 0: 
                current_aim_direction.x = 1.0 if self.facing_right else -1.0
                current_aim_direction.y = 0.0
            
            # Use projectile's own dimensions from constants for offset calc
            proj_dims = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10,10)) # Fallback
            
            offset_distance = (self.rect.width / 2) + (proj_dims[0] / 2) - 10 # Generic offset
            if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x): 
                offset_distance = (self.rect.height / 2) + (proj_dims[1] / 2) - 10
            
            if current_aim_direction.length_squared() > 0: 
                offset_vector = current_aim_direction.normalize() * offset_distance
                spawn_x += offset_vector.x
                spawn_y += offset_vector.y

            new_projectile = projectile_class(spawn_x, spawn_y, current_aim_direction, self)
            self.projectile_sprites_group.add(new_projectile)
            self.all_sprites_group.add(new_projectile)
            
            if self.print_limiter.can_print(f"player_{self.player_id}_fire_{projectile_config_name}_msg"):
                print(f"Player {self.player_id} fires {projectile_config_name}. Aim Dir: {current_aim_direction}, Spawn: ({spawn_x:.1f}, {spawn_y:.1f})")
        else:
            if self.print_limiter.can_print(f"player_{self.player_id}_{projectile_config_name}_cooldown"):
                print(f"Player {self.player_id}: {projectile_config_name} on cooldown.")

    def fire_fireball(self):
        self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')

    def fire_poison(self):
        self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')

    def fire_bolt(self):
        self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')

    def fire_blood(self):
        self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')

    def fire_ice(self):
        self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')


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
        if not self._valid_init: 
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True
                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30,40)); self.image.fill(C.RED)
                # Update rect and pos based on new image for potentially invalid player
                self.rect = self.image.get_rect(midbottom=spawn_position_tuple)
                self.pos = pygame.math.Vector2(self.rect.midbottom)
            else: return
        
        self.pos = pygame.math.Vector2(spawn_position_tuple) # spawn_position_tuple is already (midbottom_x, midbottom_y)
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y))
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)
        
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True
        
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0; 
        
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0)

        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)
        
        set_player_state(self, 'idle')

########## END OF FILE: player.py ##########