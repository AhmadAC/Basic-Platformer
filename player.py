# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.10 (process_input returns action_events)
Defines the Player class, handling core attributes, collision heights, and
the ability to check for safe uncrouching.
Delegates state, animation, physics, collisions, input, combat, and network handling
to respective handler modules.
"""
import pygame
from typing import Dict, List, Optional, Any # Added Any
import os
import sys
import math

from utils import PrintLimiter
import constants as C
import config as game_config
from assets import load_all_player_animations, load_gif_frames, resource_path

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
        self.control_scheme: Optional[str] = None
        self.joystick_id_idx: Optional[int] = None
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None # For projectiles to access game elements


        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info (ID: {self.player_id}): Unrecognized ID. Defaulting to player1 assets.")

        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)

        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0

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
        self.is_holding_crouch_ability_key = False # For aiming down and slide->crouch transition

        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0 # Now used for reset cooldown if needed, or ignored
        self.grey_cooldown_timer = 0

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0)
        self.projectile_sprites_group: Optional[pygame.sprite.Group] = None
        self.all_sprites_group: Optional[pygame.sprite.Group] = None

        self.fireball_key: Optional[int] = None
        self.poison_key: Optional[int] = None
        self.bolt_key: Optional[int] = None
        self.blood_key: Optional[int] = None
        self.ice_key: Optional[int] = None
        self.shadow_key: Optional[int] = None # This will be the RESET key
        self.grey_key: Optional[int] = None


        if self.player_id == 1:
            self.fireball_key = C.P1_FIREBALL_KEY
            self.poison_key = C.P1_POISON_KEY
            self.bolt_key = C.P1_BOLT_KEY
            self.blood_key = C.P1_BLOOD_KEY
            self.ice_key = C.P1_ICE_KEY
            self.shadow_key = C.P1_SHADOW_PROJECTILE_KEY # Mapped to K_6
            self.grey_key = C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2:
            self.fireball_key = C.P2_FIREBALL_KEY
            self.poison_key = C.P2_POISON_KEY
            self.bolt_key = C.P2_BOLT_KEY
            self.blood_key = C.P2_BLOOD_KEY
            self.ice_key = C.P2_ICE_KEY
            self.shadow_key = C.P2_SHADOW_PROJECTILE_KEY # Mapped to K_KP_6
            self.grey_key = C.P2_GREY_PROJECTILE_KEY

        # Load common stone assets
        stone_common_folder = os.path.join('characters', 'Stone')
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))

        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame = loaded_common_stone_frames[0]
        elif 'stone' in self.animations and self.animations['stone']: # Fallback to character-specific stone if common fails
             self.stone_image_frame = self.animations['stone'][0]
        else:
            self.stone_image_frame = self._create_placeholder_surface(C.GRAY, "StoneP")

        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames = loaded_common_smashed_frames
        elif 'stone_smashed' in self.animations and self.animations['stone_smashed']: # Fallback to character-specific
            self.stone_smashed_frames = self.animations['stone_smashed']
        else:
            self.stone_smashed_frames = [self._create_placeholder_surface(C.DARK_GRAY, "SmashP")]


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
        except: pass # Ignore if font fails (e.g., pygame.font not init in a test)
        return surf

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified): # Don't re-petrify if already dead unless becoming stone
            return
        print(f"Player {self.player_id} is being petrified.")
        self.is_petrified = True
        self.is_stone_smashed = False
        self.is_dead = True # Petrified means effectively dead for gameplay
        self.current_health = 0
        self.vel.xy = 0,0
        self.acc.xy = 0,0
        self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False

        self.state = 'petrified' # Set logical state
        self.current_frame = 0 # Reset frame for new animation/image
        self.death_animation_finished = True # For petrified, "death anim" is instant (becomes stone)
        set_player_state(self, 'petrified') # Update visual state via handler

    def smash_petrification(self):
        """Called when a petrified player is hit, to start the smashed animation."""
        if self.is_petrified and not self.is_stone_smashed:
            print(f"Player {self.player_id} (Petrified) is being smashed.")
            self.is_stone_smashed = True
            self.stone_smashed_timer_start = pygame.time.get_ticks()
            set_player_state(self, 'smashed') # This will trigger the smashed animation
        elif Player.print_limiter.can_print(f"smash_petrify_fail_{self.player_id}"):
            print(f"Player {self.player_id}: smash_petrification called but not petrified or already smashed. State: petrified={self.is_petrified}, smashed={self.is_stone_smashed}")


    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group,
                                        all_sprites_group: pygame.sprite.Group):
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group

    def can_stand_up(self, platforms_group: pygame.sprite.Group) -> bool:
        if not self.is_crouching or not self._valid_init:
            return True # Can "stand" if not crouching or invalid

        if self.standing_collision_height <= self.crouching_collision_height:
            if Player.print_limiter.can_print(f"can_stand_up_height_issue_{self.player_id}"):
                print(f"Player {self.player_id} Info: Standing height ({self.standing_collision_height}) "
                      f"<= crouching height ({self.crouching_collision_height}). Assuming can stand.")
            return True

        # Store current rect properties
        current_feet_y = self.rect.bottom
        current_center_x = self.rect.centerx
        # Assume standing width is same as current rect width for this check
        standing_width = self.rect.width # Or use self.animations['idle'][0].get_width() if more precise

        # Create a hypothetical rect for the player if they were standing
        potential_standing_rect = pygame.Rect(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.bottom = current_feet_y      # Align feet
        potential_standing_rect.centerx = current_center_x   # Align center

        # Check for collisions with platforms
        for platform in platforms_group:
            if potential_standing_rect.colliderect(platform.rect):
                # If a platform is above the player's current crouched head and below where their standing head would be
                if platform.rect.bottom > potential_standing_rect.top and platform.rect.top < self.rect.top :
                    return False # Blocked by a platform above
        return True # No obstructions found


    def set_state(self, new_state: str):
        set_player_state(self, new_state)

    def animate(self):
        update_player_animation(self)


    def process_input(self, pygame_events, platforms_group, keys_pressed_override=None):
        """
        Processes input for the player based on their control_scheme.
        `keys_pressed_override` is for network clients.
        Returns a dictionary of action_events that occurred this frame.
        """
        active_mappings_for_input: Dict[str, Any] = {}
        current_keys_for_input = keys_pressed_override if keys_pressed_override is not None else pygame.key.get_pressed()

        # Determine which mapping set to use
        if self.control_scheme:
            if self.control_scheme == "keyboard_p1":
                active_mappings_for_input = game_config.P1_MAPPINGS
            elif self.control_scheme == "keyboard_p2":
                active_mappings_for_input = game_config.P2_MAPPINGS
            elif self.control_scheme.startswith("joystick_") and self.player_id == 1:
                active_mappings_for_input = game_config.P1_MAPPINGS # P1_MAPPINGS holds joystick defs for P1
            elif self.control_scheme.startswith("joystick_") and self.player_id == 2:
                active_mappings_for_input = game_config.P2_MAPPINGS # P2_MAPPINGS holds joystick defs for P2
            else: # Fallback
                if Player.print_limiter.can_print(f"proc_input_fallback_map_{self.player_id}_{self.control_scheme}"):
                    print(f"Player {self.player_id}: process_input using default P1 keyboard map due to scheme '{self.control_scheme}'.")
                active_mappings_for_input = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        else: # Should not happen if game_setup assigns control_scheme
            if Player.print_limiter.can_print(f"proc_input_no_scheme_{self.player_id}"):
                print(f"Player {self.player_id}: No control_scheme set in process_input. Using default P1 keyboard map.")
            active_mappings_for_input = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS

        return process_player_input_logic(self, current_keys_for_input, pygame_events, active_mappings_for_input, platforms_group)


    def handle_mapped_input(self, keys_pressed_state, pygame_event_list, key_map_dict, platforms_group):
        # This method is largely superseded by process_input directly using configured mappings.
        # Kept for potential specific override scenarios, but player.process_input is preferred.
        if Player.print_limiter.can_print(f"handle_mapped_input_call_{self.player_id}"):
            print(f"Player {self.player_id}: handle_mapped_input called directly. Control scheme: '{self.control_scheme}'. This method might be deprecated.")
        return process_player_input_logic(self, keys_pressed_state, pygame_event_list, key_map_dict, platforms_group)


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
            setattr(self, cooldown_attr_name, current_time_ms) # Reset cooldown timer
            
            # Determine spawn position based on player center and aim direction
            spawn_x, spawn_y = self.rect.centerx, self.rect.centery
            
            current_aim_direction = self.fireball_last_input_dir.copy() # Use the stored aim direction
            if current_aim_direction.length_squared() == 0: # Fallback if no aim input
                current_aim_direction.x = 1.0 if self.facing_right else -1.0
                current_aim_direction.y = 0.0

            # Offset spawn slightly in front of player based on aim
            proj_dims = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10,10)) # Get dims from constants
            offset_distance = (self.rect.width / 2) + (proj_dims[0] / 2) - 10 # Heuristic offset
            # More refined offset if aiming mostly vertical
            if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x): # Prioritize vertical offset
                offset_distance = (self.rect.height / 2) + (proj_dims[1] / 2) - 10

            if current_aim_direction.length_squared() > 0:
                offset_vector = current_aim_direction.normalize() * offset_distance
                spawn_x += offset_vector.x
                spawn_y += offset_vector.y

            new_projectile = projectile_class(spawn_x, spawn_y, current_aim_direction, self)
            if hasattr(self, 'game_elements_ref_for_projectiles'): # Pass game elements ref if available
                new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles

            self.projectile_sprites_group.add(new_projectile)
            self.all_sprites_group.add(new_projectile)

            # Special case for BloodShot: costs health
            if projectile_config_name == 'blood' and self.current_health > 0:
                health_cost_percent = 0.05 # Example: 5% of current health
                health_cost_amount = self.current_health * health_cost_percent
                self.current_health -= health_cost_amount
                self.current_health = max(0, self.current_health) # Ensure health doesn't go below 0
                # print(f"Player {self.player_id} paid {health_cost_amount:.1f} health for BloodShot. Current health: {self.current_health:.1f}")
                if self.current_health <= 0 and not self.is_dead:
                    self.set_state('death')
        # else: pass # On cooldown

    # Specific projectile firing methods
    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')


    # Combat methods (delegated)
    def check_attack_collisions(self, list_of_targets):
        check_player_attack_collisions(self, list_of_targets)

    def take_damage(self, damage_amount_taken):
        player_take_damage(self, damage_amount_taken)

    def self_inflict_damage(self, damage_amount_to_self):
        player_self_inflict_damage(self, damage_amount_to_self)

    def heal_to_full(self):
        player_heal_to_full(self)

    # Network methods (delegated)
    def get_network_data(self):
        return get_player_network_data(self)

    def set_network_data(self, received_network_data):
        set_player_network_data(self, received_network_data)

    def handle_network_input(self, network_input_data_dict):
        # Ensure platforms_group is available for handle_player_network_input if it calls process_player_input_logic
        # For now, assuming handle_player_network_input doesn't directly need platforms for its own logic,
        # but if it internally calls process_player_input_logic, that will require it.
        # This suggests network input handling might need to be simpler or have access to game_elements.
        handle_player_network_input(self, network_input_data_dict)


    def get_input_state_for_network(self, keys_state, events, key_map):
        """
        Gathers the local player's current input state, including processed action events,
        into a dictionary format suitable for sending over the network.
        """
        # Process input to get all continuous states and one-time events
        # Ensure platforms_group is available. If game_elements_ref is not set yet, pass an empty group.
        platforms_group_for_input = pygame.sprite.Group()
        if hasattr(self, 'game_elements_ref_for_projectiles') and \
           self.game_elements_ref_for_projectiles and \
           'platform_sprites' in self.game_elements_ref_for_projectiles:
            platforms_group_for_input = self.game_elements_ref_for_projectiles['platform_sprites']
        
        # process_player_input_logic returns a dictionary of action_events that occurred.
        # It also updates player's continuous states like is_trying_to_move_left.
        processed_action_events = process_player_input_logic(self, keys_state, events, key_map, platforms_group_for_input)

        network_input_dict = {
            # Continuous states (might be derived by server too, but sending can be useful)
            'left_held': self.is_trying_to_move_left,
            'right_held': self.is_trying_to_move_right,
            'up_held': self.is_holding_climb_ability_key,
            'down_held': self.is_holding_crouch_ability_key, # For aiming, slide->crouch
            'is_crouching_state': self.is_crouching, # Send the actual toggled state

            # Aiming direction
            'fireball_aim_x': self.fireball_last_input_dir.x,
            'fireball_aim_y': self.fireball_last_input_dir.y
        }
        # Add all *events* from processed_action_events
        # This will include things like "jump":True, "attack1":True, "reset":True, "crouch":True (for toggle)
        network_input_dict.update(processed_action_events)
        
        return network_input_dict


    # Collision methods (delegated)
    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        check_player_platform_collisions(self, direction, platforms_group)

    def check_ladder_collisions(self, ladders_group: pygame.sprite.Group):
        check_player_ladder_collisions(self, ladders_group)

    def check_character_collisions(self, direction: str, characters_list: list):
        return check_player_character_collisions(self, direction, characters_list)

    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        check_player_hazard_collisions(self, hazards_group)

    # Main update method
    def update(self, dt_sec, platforms_group, ladders_group, hazards_group,
               other_players_sprite_list, enemies_sprite_list):
        if self.is_stone_smashed: # Check if stone form is smashed and disappearing
            current_time_ms = pygame.time.get_ticks()
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                # print(f"Smashed stone Player {self.player_id} duration ended. Killing.")
                self.kill() # Remove from all sprite groups
                return # Do not proceed with further updates
            self.animate() # Continue smashed animation
            return # No other logic if smashed

        if self.is_petrified: # If petrified (but not yet smashed or smash timer not up)
            self.vel.xy = 0,0 # Ensure no movement
            self.acc.xy = 0,0
            self.animate() # Show static stone image
            return # No other logic if petrified

        update_player_core_logic(self, dt_sec, platforms_group, ladders_group, hazards_group,
                                 other_players_sprite_list, enemies_sprite_list)

    def reset_state(self, spawn_position_tuple: tuple):
        """Resets the player's state to initial values."""
        if not self._valid_init and self.animations is None: # Attempt to reload animations if totally invalid
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True # Assume it's now valid enough to proceed
                # Re-initialize collision heights
                try:
                    self.standing_collision_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
                    self.crouching_collision_height = self.animations['crouch'][0].get_height() if self.animations.get('crouch') else 30
                    if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
                       self.crouching_collision_height >= self.standing_collision_height:
                        self._valid_init = False # Mark invalid again if heights are bad
                except: self._valid_init = False

                # Re-initialize image
                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30, self.standing_collision_height or 60)); self.image.fill(C.RED)
            else:
                if Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"):
                    print(f"Player {self.player_id} Error: Failed to load animations during reset. Player remains invalid.")
                return # Cannot proceed with reset if animations are still missing

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

        # Reset cooldowns
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Default aim right

        # Reset petrification state
        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0

        # Ensure stone assets are loaded (or re-loaded if they were placeholders)
        stone_common_folder = os.path.join('characters', 'Stone')
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))
        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame = loaded_common_stone_frames[0]
        elif 'stone' in self.animations and self.animations['stone']: # Fallback to character-specific stone
             self.stone_image_frame = self.animations['stone'][0]
        else:
            self.stone_image_frame = self._create_placeholder_surface(C.GRAY, "StoneP_Reset")
        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames = loaded_common_smashed_frames
        elif 'stone_smashed' in self.animations and self.animations['stone_smashed']: # Fallback
            self.stone_smashed_frames = self.animations['stone_smashed']
        else:
            self.stone_smashed_frames = [self._create_placeholder_surface(C.DARK_GRAY, "SmashP_Reset")]


        # Ensure player image is not transparent from a previous state like fading
        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)

        set_player_state(self, 'idle') # Reset to idle state