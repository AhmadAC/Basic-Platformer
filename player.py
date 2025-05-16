########## START OF FILE: player.py ##########
# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.8 (Ensured petrification attributes initialized in __init__ and reset_state)
Defines the Player class, handling core attributes, collision heights, and
the ability to check for safe uncrouching.
Delegates state, animation, physics, collisions, input, combat, and network handling
to respective handler modules.
"""
import pygame
from typing import Dict, List, Optional 
import os 
import sys 
import math 

from utils import PrintLimiter 
import constants as C
from assets import load_all_player_animations

from player_state_handler import set_player_state
from player_animation_handler import update_player_animation
from player_movement_physics import update_player_core_logic 
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)

from player_input_handler import process_player_input_logic
from player_combat_handler import ( 
                                   check_player_attack_collisions,
                                   player_take_damage, player_self_inflict_damage, player_heal_to_full)
from player_network_handler import (get_player_network_data, set_player_network_data,
                                    handle_player_network_input, get_player_input_state_for_network)

from projectiles import Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard, ShadowProjectile, GreyProjectile


class Player(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True 

        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info (ID: {self.player_id}): Unrecognized ID. Defaulting to player1 assets.")
            
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        if self.animations is None:
            print(f"CRITICAL Player Init Error (ID: {self.player_id}): Failed to load critical animations from '{asset_folder}'. Player invalid.")
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.pos = pygame.math.Vector2(self.rect.midbottom)
            self.is_dead = True
            self._valid_init = False
            self.standing_collision_height = 0
            self.crouching_collision_height = 0
            self.standard_height = 0 
            # Initialize petrification attributes even on failed animation load for safety
            self.is_petrified = False
            self.is_stone_smashed = False
            self.stone_smashed_timer_start = 0
            self.stone_image_frame = self._create_placeholder_surface(C.GRAY, "StoneP_Fail")
            self.stone_smashed_frames = [self._create_placeholder_surface(C.DARK_GRAY, "SmashP_Fail")]
            return 

        self.standing_collision_height = 0
        self.crouching_collision_height = 0

        try:
            if self.animations.get('idle') and self.animations['idle']:
                self.standing_collision_height = self.animations['idle'][0].get_height()
            else:
                self.standing_collision_height = 60 
                if Player.print_limiter.can_print(f"player_init_no_idle_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'idle' animation missing for standing height. Using default {self.standing_collision_height}.")

            if self.animations.get('crouch') and self.animations['crouch']:
                self.crouching_collision_height = self.animations['crouch'][0].get_height()
            else:
                self.crouching_collision_height = self.standing_collision_height // 2 
                if Player.print_limiter.can_print(f"player_init_no_crouch_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'crouch' animation missing for crouching height. Using default {self.crouching_collision_height}.")

            if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
               self.crouching_collision_height >= self.standing_collision_height:
                print(f"Player {self.player_id} CRITICAL: Collision heights invalid after init. "
                      f"Standing: {self.standing_collision_height}, Crouching: {self.crouching_collision_height}")
                self._valid_init = False 
        except Exception as e:
            print(f"Player {self.player_id} Error setting collision heights: {e}")
            self.standing_collision_height = 60 
            self.crouching_collision_height = 30
            self._valid_init = False

        self.standard_height = self.standing_collision_height 

        self._last_facing_right = True
        self._last_state_for_debug = "init"
        self.state = 'idle' 
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()

        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and len(initial_idle_frames) > 0:
            self.image = initial_idle_frames[0]
        else: 
            self.image = pygame.Surface((30, self.standing_collision_height or 60)) 
            self.image.fill(C.RED) 
            print(f"Player {self.player_id} CRITICAL: 'idle' animation frames missing for initial image. Using RED placeholder.")
            self._valid_init = False 

        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(self.rect.midbottom) 

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
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0 
        self.grey_cooldown_timer = 0   

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) 
        self.projectile_sprites_group: Optional[pygame.sprite.Group] = None 
        self.all_sprites_group: Optional[pygame.sprite.Group] = None      

        self.fireball_key: Optional[int] = None
        self.poison_key: Optional[int] = None
        self.bolt_key: Optional[int] = None
        self.blood_key: Optional[int] = None
        self.ice_key: Optional[int] = None
        self.shadow_key: Optional[int] = None 
        self.grey_key: Optional[int] = None   


        if self.player_id == 1:
            self.fireball_key = C.P1_FIREBALL_KEY
            self.poison_key = C.P1_POISON_KEY
            self.bolt_key = C.P1_BOLT_KEY
            self.blood_key = C.P1_BLOOD_KEY
            self.ice_key = C.P1_ICE_KEY
            self.shadow_key = C.P1_SHADOW_PROJECTILE_KEY 
            self.grey_key = C.P1_GREY_PROJECTILE_KEY     
        elif self.player_id == 2: 
            self.fireball_key = C.P2_FIREBALL_KEY
            self.poison_key = C.P2_POISON_KEY
            self.bolt_key = C.P2_BOLT_KEY
            self.blood_key = C.P2_BLOOD_KEY
            self.ice_key = C.P2_ICE_KEY
            self.shadow_key = C.P2_SHADOW_PROJECTILE_KEY 
            self.grey_key = C.P2_GREY_PROJECTILE_KEY     

        # Petrification attributes
        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        
        # Pre-load stone images if available from the character's animation set
        # If 'stone' or 'stone_smashed' are not in self.animations (e.g., missing files),
        # load_all_player_animations should have provided a BLUE placeholder.
        # We'll use that or the specific loaded one.
        self.stone_image_frame = self.animations.get('stone', [self._create_placeholder_surface(C.GRAY, "StoneP")])[0]
        self.stone_smashed_frames = self.animations.get('stone_smashed', [self._create_placeholder_surface(C.DARK_GRAY, "SmashP")])


        if not self._valid_init:
            print(f"Player {self.player_id}: Initialization was marked as invalid. Player might not function correctly.")

    def _create_placeholder_surface(self, color, text="Err"):
        height = self.standing_collision_height if hasattr(self, 'standing_collision_height') and self.standing_collision_height > 0 else 60
        surf = pygame.Surface((30, height)).convert_alpha() 
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
        print(f"Player {self.player_id} is being petrified.")
        self.is_petrified = True
        self.is_stone_smashed = False
        self.is_dead = True 
        self.current_health = 0
        self.vel.xy = 0,0
        self.acc.xy = 0,0
        self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        
        self.state = 'petrified' 
        self.current_frame = 0 
        self.death_animation_finished = True 
        set_player_state(self, 'petrified') 

    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group,
                                        all_sprites_group: pygame.sprite.Group):
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

    def can_stand_up(self, platforms_group: pygame.sprite.Group) -> bool:
        if not self.is_crouching or not self._valid_init:
            return True 

        if self.standing_collision_height <= self.crouching_collision_height:
            if Player.print_limiter.can_print(f"can_stand_up_height_issue_{self.player_id}"):
                print(f"Player {self.player_id} Info: Standing height ({self.standing_collision_height}) "
                      f"<= crouching height ({self.crouching_collision_height}). Assuming can stand.")
            return True 

        current_feet_y = self.rect.bottom
        current_center_x = self.rect.centerx
        standing_width = self.rect.width

        potential_standing_rect = pygame.Rect(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.bottom = current_feet_y
        potential_standing_rect.centerx = current_center_x
        
        for platform in platforms_group:
            if potential_standing_rect.colliderect(platform.rect):
                if platform.rect.bottom > potential_standing_rect.top and platform.rect.top < self.rect.top:
                    return False 
        return True


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
        if not self._valid_init or self.is_dead or not self.alive() or getattr(self, 'is_petrified', False): 
             return
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

            if projectile_config_name == 'blood' and self.current_health > 0:
                health_cost_percent = 0.05 
                health_cost_amount = self.current_health * health_cost_percent
                self.current_health -= health_cost_amount
                self.current_health = max(0, self.current_health)
                print(f"Player {self.player_id} paid {health_cost_amount:.1f} health for BloodShot. Current health: {self.current_health:.1f}")
                if self.current_health <= 0 and not self.is_dead:
                    self.set_state('death')
        # else: pass 

    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile') 
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')       


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
        if self.is_stone_smashed:
            current_time_ms = pygame.time.get_ticks()
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                print(f"Smashed stone Player {self.player_id} duration ended. Killing.")
                self.kill()
                return
            self.animate() 
            return 
        
        if self.is_petrified: 
            self.vel.xy = 0,0
            self.acc.xy = 0,0
            self.animate() 
            return 

        update_player_core_logic(self, dt_sec, platforms_group, ladders_group, hazards_group,
                                 other_players_sprite_list, enemies_sprite_list)

    def reset_state(self, spawn_position_tuple: tuple):
        if not self._valid_init and self.animations is None:
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True 
                try:
                    self.standing_collision_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
                    self.crouching_collision_height = self.animations['crouch'][0].get_height() if self.animations.get('crouch') else 30
                    if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
                       self.crouching_collision_height >= self.standing_collision_height:
                        self._valid_init = False
                except: self._valid_init = False

                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30, self.standing_collision_height or 60)); self.image.fill(C.RED)
            else:
                if Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"):
                    print(f"Player {self.player_id} Error: Failed to load animations during reset. Player remains invalid.")
                return

        self.pos = pygame.math.Vector2(spawn_position_tuple) 
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y)) 
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7)

        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True

        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;

        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0 
        self.grey_cooldown_timer = 0   
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) 

        # Reset petrification state
        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0

        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)

        set_player_state(self, 'idle') 
########## END OF FILE: player.py ##########