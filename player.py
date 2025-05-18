# player.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.13 (Add crouched petrification visuals)
Defines the Player class, handling core attributes, collision heights, and
the ability to check for safe uncrouching.
Delegates state, animation, physics, collisions, input, combat, and network handling
to respective handler modules.
"""
import pygame
from typing import Dict, List, Optional, Any
import os
import sys # Not strictly needed here after path changes moved to main, but common.
import math # For math.Vector2 if not directly from pygame

from utils import PrintLimiter
import constants as C
import config as game_config # For player-specific key mappings from config
from assets import load_all_player_animations, load_gif_frames, resource_path

# Import handler modules
try:
    from player_state_handler import set_player_state
    from player_animation_handler import update_player_animation
    from player_movement_physics import update_player_core_logic
    from player_collision_handler import (
        check_player_platform_collisions,
        check_player_ladder_collisions,
        check_player_character_collisions,
        check_player_hazard_collisions
    )
    from player_input_handler import process_player_input_logic # Assuming this is the main input processing function
    from player_combat_handler import (
                                       check_player_attack_collisions,
                                       player_take_damage, player_self_inflict_damage, player_heal_to_full)
    from player_network_handler import (get_player_network_data, set_player_network_data,
                                        handle_player_network_input, get_player_input_state_for_network)
    # Import Projectile classes for firing logic
    from projectiles import Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard, ShadowProjectile, GreyProjectile
except ImportError as e:
    print(f"CRITICAL PLAYER: Failed to import a handler or projectile module: {e}")
    # This is a fatal error for the Player class to function.
    # Consider raising an exception or having a more robust fallback if some handlers are optional.
    raise


class Player(pygame.sprite.Sprite):
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0) # Class-level limiter

    def __init__(self, start_x, start_y, player_id=1):
        super().__init__()
        self.player_id = player_id
        self._valid_init = True # Assume valid until a critical failure
        self.control_scheme: Optional[str] = None # Set by game_setup based on config
        self.joystick_id_idx: Optional[int] = None # Set by game_setup for joystick players
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None # For projectile access to game elements


        # Determine asset folder based on player_id
        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        if self.player_id not in [1, 2]:
            if Player.print_limiter.can_print(f"player_init_unrecognized_id_{self.player_id}"):
                print(f"Player Info (ID: {self.player_id}): Unrecognized ID. Defaulting to player1 assets.")
            # asset_folder remains 'characters/player1' due to the if/else structure

        # Load all animations for this player
        self.animations = load_all_player_animations(relative_asset_folder=asset_folder)

        # Status Effect Flags & Timers (initialized before animation/asset loading)
        self.is_aflame = False
        self.aflame_timer_start = 0
        self.is_deflaming = False
        self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0

        self.is_frozen = False
        self.is_defrosting = False
        self.frozen_effect_timer = 0

        self.is_petrified = False
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = True # Default, will be set when petrified
        self.was_crouching_when_petrified = False


        # Critical check: If animations failed to load, player is invalid
        if self.animations is None:
            print(f"CRITICAL Player Init Error (ID: {self.player_id}): Failed to load critical animations from '{asset_folder}'. Player invalid.")
            # Create a basic placeholder image and rect
            self.image = pygame.Surface((30, 40)).convert_alpha(); self.image.fill(C.RED)
            self.rect = self.image.get_rect(midbottom=(start_x, start_y))
            self.pos = pygame.math.Vector2(self.rect.midbottom) # Initialize pos
            self.is_dead = True # Mark as unusable
            self._valid_init = False
            # Initialize some core attributes to prevent crashes later if methods are called on invalid player
            self.standing_collision_height = 0
            self.crouching_collision_height = 0
            self.standard_height = 0 # Used for camera, ensure it's set
            # Initialize stone asset placeholders too
            self.stone_image_frame_original = self._create_placeholder_surface(C.GRAY, "StonePFail")
            self.stone_image_frame = self.stone_image_frame_original
            self.stone_smashed_frames_original = [self._create_placeholder_surface(C.DARK_GRAY, "SmashPFail")]
            self.stone_smashed_frames = list(self.stone_smashed_frames_original)
            self.stone_crouch_image_frame_original = self._create_placeholder_surface(C.GRAY, "SCrouchFailP")
            self.stone_crouch_image_frame = self.stone_crouch_image_frame_original
            self.stone_crouch_smashed_frames_original = [self._create_placeholder_surface(C.DARK_GRAY, "SCSmashFailP")]
            self.stone_crouch_smashed_frames = list(self.stone_crouch_smashed_frames_original)
            return # Stop further initialization

        # Determine collision heights from animations
        self.standing_collision_height = 0
        self.crouching_collision_height = 0

        try:
            if self.animations.get('idle') and self.animations['idle']:
                self.standing_collision_height = self.animations['idle'][0].get_height()
            else: # Fallback if 'idle' is missing (should ideally not happen)
                self.standing_collision_height = 60 # Default height
                if Player.print_limiter.can_print(f"player_init_no_idle_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'idle' animation missing for standing height. Using default {self.standing_collision_height}.")

            if self.animations.get('crouch') and self.animations['crouch']:
                self.crouching_collision_height = self.animations['crouch'][0].get_height()
            else: # Fallback if 'crouch' is missing
                self.crouching_collision_height = self.standing_collision_height // 2 # Default crouch height
                if Player.print_limiter.can_print(f"player_init_no_crouch_height_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'crouch' animation missing for crouching height. Using default {self.crouching_collision_height}.")

            # Validate heights
            if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
               self.crouching_collision_height >= self.standing_collision_height:
                print(f"Player {self.player_id} CRITICAL: Collision heights invalid after init. "
                      f"Standing: {self.standing_collision_height}, Crouching: {self.crouching_collision_height}")
                self._valid_init = False # Mark as invalid if heights are problematic
        except Exception as e:
            print(f"Player {self.player_id} Error setting collision heights: {e}")
            self.standing_collision_height = 60 # Hard fallback
            self.crouching_collision_height = 30 # Hard fallback
            self._valid_init = False

        self.standard_height = self.standing_collision_height # Standard height for camera focus, etc.

        # Animation state
        self._last_facing_right = True # For optimizing image flipping
        self._last_state_for_debug = "init" # For debugging state changes
        self.state = 'idle'        # Current logical state of the player
        self.current_frame = 0     # Current frame index for animation
        self.last_anim_update = pygame.time.get_ticks() # For timing animation updates

        # Initial image setup
        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and len(initial_idle_frames) > 0:
            self.image = initial_idle_frames[0]
        else: # Fallback if idle animation is missing (should be caught by load_all_player_animations)
            self.image = pygame.Surface((30, self.standing_collision_height or 60)) # Use determined height or default
            self.image.fill(C.RED) # Error color
            print(f"Player {self.player_id} CRITICAL: 'idle' animation frames missing for initial image. Using RED placeholder.")
            self._valid_init = False # Invalid if no idle animation

        # Core physics and position attributes
        self.rect = self.image.get_rect(midbottom=(start_x, start_y))
        self.pos = pygame.math.Vector2(self.rect.midbottom) # Use midbottom as the consistent anchor point

        # Physics properties
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY) # Initial downward acceleration
        self.facing_right = True
        self.on_ground = False
        self.on_ladder = False
        self.can_grab_ladder = False # If player is in a position to grab a ladder
        self.touching_wall = 0  # -1 for left wall, 1 for right wall, 0 for none
        self.can_wall_jump = False
        self.wall_climb_timer = 0 # Timestamp for when wall climb started

        # Action states and timers
        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = getattr(C, 'PLAYER_DASH_DURATION', 150)
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = getattr(C, 'PLAYER_ROLL_DURATION', 300)
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = getattr(C, 'PLAYER_SLIDE_DURATION', 400)

        # Combat states and timers
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300 # Default, will be set by anim
        self.attack_type = 0 # 1: primary, 2: secondary, 3: combo, 4: crouch_attack
        self.can_combo = False; self.combo_window = getattr(C, 'PLAYER_COMBO_WINDOW', 150)
        self.wall_climb_duration = getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500)

        # Damage states and timers
        self.is_taking_hit = False; self.hit_timer = 0 # Timestamp when hit started
        self.hit_duration = getattr(C, 'PLAYER_HIT_STUN_DURATION', 300) # Visual/input lock duration
        self.hit_cooldown = getattr(C, 'PLAYER_HIT_COOLDOWN', 600)      # Invulnerability period

        # Death state
        self.is_dead = False
        self.death_animation_finished = False
        self.state_timer = 0 # Timestamp for when the current state began

        # Health
        self.max_health = C.PLAYER_MAX_HEALTH
        self.current_health = self.max_health
        self.attack_hitbox = pygame.Rect(0, 0, 45, 30) # Default, adjust as needed

        # Input intent flags (set by input handler, used by physics/state logic)
        self.is_trying_to_move_left = False
        self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False # For actions like 'up' on ladder or wall climb
        self.is_holding_crouch_ability_key = False # For actions like 'down' on ladder or continuous crouch

        # Projectile cooldowns
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0

        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Default aim direction
        self.projectile_sprites_group: Optional[pygame.sprite.Group] = None # Set by game_setup
        self.all_sprites_group: Optional[pygame.sprite.Group] = None      # Set by game_setup

        # Projectile key mapping (loaded from constants)
        self.fireball_key: Optional[int] = None
        self.poison_key: Optional[int] = None
        self.bolt_key: Optional[int] = None
        self.blood_key: Optional[int] = None
        self.ice_key: Optional[int] = None
        self.shadow_key: Optional[int] = None # Also reset key
        self.grey_key: Optional[int] = None


        if self.player_id == 1:
            self.fireball_key = C.P1_FIREBALL_KEY
            self.poison_key = C.P1_POISON_KEY
            self.bolt_key = C.P1_BOLT_KEY
            self.blood_key = C.P1_BLOOD_KEY
            self.ice_key = C.P1_ICE_KEY
            self.shadow_key = C.P1_SHADOW_PROJECTILE_KEY # This is also P1 Reset Key
            self.grey_key = C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2:
            self.fireball_key = C.P2_FIREBALL_KEY
            self.poison_key = C.P2_POISON_KEY
            self.bolt_key = C.P2_BOLT_KEY
            self.blood_key = C.P2_BLOOD_KEY
            self.ice_key = C.P2_ICE_KEY
            self.shadow_key = C.P2_SHADOW_PROJECTILE_KEY # This is also P2 Reset Key
            self.grey_key = C.P2_GREY_PROJECTILE_KEY

        # --- Load Common Stone Assets (Shared by all players for petrification) ---
        # These are fallback assets if player-specific 'petrified'/'smashed' anims are not desired/available.
        # Or, they can be the primary assets for this effect.
        stone_common_folder = os.path.join('characters', 'Stone')
        
        # Standing Stone
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame_original = loaded_common_stone_frames[0]
        else: # Fallback to player's own 'petrified' anim if common fails, then placeholder
            self.stone_image_frame_original = (self.animations.get('petrified') or [self._create_placeholder_surface(C.GRAY, "StoneP")])[0]
        self.stone_image_frame = self.stone_image_frame_original # Current frame to use (can be flipped)

        # Standing Smashed Stone
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))
        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames_original = loaded_common_smashed_frames
        else: # Fallback
            self.stone_smashed_frames_original = (self.animations.get('smashed') or [self._create_placeholder_surface(C.DARK_GRAY, "SmashP")])
        self.stone_smashed_frames = list(self.stone_smashed_frames_original) # Current frames to use (can be flipped)

        # Crouching Stone (NEW)
        common_stone_crouch_png_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouch.png'))
        loaded_common_stone_crouch_frames = load_gif_frames(common_stone_crouch_png_path)
        if loaded_common_stone_crouch_frames and not (len(loaded_common_stone_crouch_frames) == 1 and loaded_common_stone_crouch_frames[0].get_size() == (30,40) and loaded_common_stone_crouch_frames[0].get_at((0,0)) == C.RED):
            self.stone_crouch_image_frame_original = loaded_common_stone_crouch_frames[0]
        else: # Fallback to standing stone if crouch version fails
            self.stone_crouch_image_frame_original = self.stone_image_frame_original # Assumes standing stone_image_frame_original is loaded
            if Player.print_limiter.can_print(f"stone_crouch_load_fail_{player_id}"):
                 print(f"PLAYER {player_id} WARNING: Failed to load __StoneCrouch.png, using standing stone image as fallback for crouch petrify.")
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original

        # Crouching Smashed Stone (NEW)
        common_stone_crouch_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouchSmashed.gif'))
        loaded_common_crouch_smashed_frames = load_gif_frames(common_stone_crouch_smashed_gif_path)
        if loaded_common_crouch_smashed_frames and not (len(loaded_common_crouch_smashed_frames) == 1 and loaded_common_crouch_smashed_frames[0].get_size() == (30,40) and loaded_common_crouch_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_crouch_smashed_frames_original = loaded_common_crouch_smashed_frames
        else: # Fallback to standing smashed if crouch version fails
            self.stone_crouch_smashed_frames_original = list(self.stone_smashed_frames_original) # Assumes standing smashed frames are loaded
            if Player.print_limiter.can_print(f"stone_crouch_smashed_load_fail_{player_id}"):
                print(f"PLAYER {player_id} WARNING: Failed to load __StoneCrouchSmashed.gif, using standing smashed frames as fallback.")
        self.stone_crouch_smashed_frames = list(self.stone_crouch_smashed_frames_original)


        if not self._valid_init: # Final check after all initializations
            print(f"Player {self.player_id}: Initialization was marked as invalid. Player might not function correctly.")


    def _create_placeholder_surface(self, color, text="Err"):
        """Helper to create a placeholder surface if assets fail to load."""
        # Use a sensible default height if standing_collision_height isn't set yet
        height = self.standing_collision_height if hasattr(self, 'standing_collision_height') and self.standing_collision_height > 0 else 60
        surf = pygame.Surface((30, height)).convert_alpha()
        surf.fill(color)
        pygame.draw.rect(surf, C.BLACK, surf.get_rect(), 1)
        try: # Try to render text, but don't fail if font system isn't ready (e.g. during very early init error)
            font = pygame.font.Font(None, 18)
            text_surf = font.render(text, True, C.BLACK)
            surf.blit(text_surf, text_surf.get_rect(center=surf.get_rect().center))
        except: pass
        return surf

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self):
        """Applies the 'aflame' status effect to the player."""
        # Check if already in a conflicting state
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            if self.print_limiter.can_print(f"player_apply_aflame_blocked_{self.player_id}"):
                print(f"Player {self.player_id}: apply_aflame_effect called but already in conflicting state. Ignoring.")
            return
        if self.print_limiter.can_print(f"player_apply_aflame_{self.player_id}"):
            print(f"Player {self.player_id}: Applying aflame effect. Crouching: {self.is_crouching}")

        # This is the crucial part for initiating the fire sequence
        self.is_aflame = True
        self.is_deflaming = False # Ensure deflaming is off
        self.aflame_timer_start = pygame.time.get_ticks()
        self.aflame_damage_last_tick = self.aflame_timer_start # Start damage ticks from now

        # Set the initial visual state (e.g., __Aflame.gif or __Aflame_crouch.gif)
        # The animation handler will transition this to 'burning' or 'burning_crouch' after the initial anim.
        if self.is_crouching:
            self.set_state('aflame_crouch') # Initial fire while crouched
        else:
            self.set_state('aflame')      # Initial fire while standing

        # Stop any current attack
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        """Applies the 'frozen' status effect to the player."""
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            if self.print_limiter.can_print(f"player_apply_frozen_blocked_{self.player_id}"):
                print(f"Player {self.player_id}: apply_freeze_effect called but already in conflicting state. Ignoring.")
            return
        if self.print_limiter.can_print(f"player_apply_frozen_{self.player_id}"):
            print(f"Player {self.player_id}: Applying frozen effect.")
        self.set_state('frozen') # This will trigger flag setting in player_state_handler
        # player_state_handler will also clear conflicting action flags like attacking
        self.is_attacking = False; self.attack_type = 0 # Explicitly clear here too
        self.vel.xy = 0,0; self.acc.x = 0 # Stop movement


    def update_status_effects(self, current_time_ms):
        """Manages timers and transitions for player's own status effects."""
        # Aflame / Deflame logic
        if self.is_aflame: # True during 'aflame', 'burning', 'aflame_crouch', 'burning_crouch'
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                # Transition to deflaming
                if self.print_limiter.can_print(f"player_aflame_end_{self.player_id}"):
                    print(f"Player {self.player_id}: Aflame duration ended. Transitioning to deflame. Crouching: {self.is_crouching}")
                self.is_aflame = False
                self.is_deflaming = True
                self.deflame_timer_start = current_time_ms # Reset timer for deflame
                if self.is_crouching:
                    self.set_state('deflame_crouch')
                else:
                    self.set_state('deflame')
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                # Apply damage if on fire
                self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
                self.aflame_damage_last_tick = current_time_ms
        elif self.is_deflaming: # True during 'deflame', 'deflame_crouch'
            if current_time_ms - self.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
                # Deflaming finished
                if self.print_limiter.can_print(f"player_deflame_end_{self.player_id}"):
                    print(f"Player {self.player_id}: Deflame duration ended. Transitioning to normal. Crouching: {self.is_crouching}")
                self.is_deflaming = False
                # Determine next state based on current posture and movement
                if self.is_crouching:
                    self.set_state('crouch')
                else:
                    self.set_state('idle' if self.on_ground else 'fall')

        # Frozen / Defrost logic
        if self.is_frozen: # Player is fully frozen
            self.vel.xy = 0,0; self.acc.x = 0 # Ensure no movement
            if current_time_ms - self.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
                if self.print_limiter.can_print(f"player_frozen_end_{self.player_id}"):
                    print(f"Player {self.player_id}: Frozen duration ended. Transitioning to defrost.")
                self.set_state('defrost') # player_state_handler will set is_frozen=False, is_defrosting=True
        elif self.is_defrosting: # Player is in the defrost animation
            self.vel.xy = 0,0; self.acc.x = 0 # Still no movement
            # Check if total frozen + defrost duration has passed
            if current_time_ms - self.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
                if self.print_limiter.can_print(f"player_defrost_end_{self.player_id}"):
                    print(f"Player {self.player_id}: Defrost duration ended. Transitioning to idle/fall.")
                self.set_state('idle' if self.on_ground else 'fall') # player_state_handler will clear is_defrosting


    def petrify(self):
        """Turns the player into stone."""
        if self.is_petrified or (self.is_dead and not self.is_petrified): # Don't re-petrify or petrify if truly dead
            return
        print(f"Player {self.player_id} is being petrified. Crouching: {self.is_crouching}")
        self.facing_at_petrification = self.facing_right # Store facing for consistent visuals
        self.was_crouching_when_petrified = self.is_crouching # Store crouch state

        # Set all flags for petrified state
        self.is_petrified = True
        self.is_stone_smashed = False # Not smashed yet
        self.is_dead = True           # Petrified counts as "dead" for game over logic
        self.current_health = 0       # Set health to 0 (or a specific "stone health" if desired)
        self.vel.xy = 0,0             # Stop all movement
        self.acc.xy = 0,0             # Stop all acceleration
        # Clear action flags
        self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        # Clear other status effects
        self.is_aflame = False; self.is_deflaming = False
        self.is_frozen = False; self.is_defrosting = False

        self.state = 'petrified' # Set the logical state
        self.current_frame = 0   # Animation frame reset
        self.death_animation_finished = True # For petrified, the "death" is instant, smashed has an animation
        set_player_state(self, 'petrified') # Use the handler to ensure all state logic is run

    def smash_petrification(self):
        """Smashes the petrified player."""
        if self.is_petrified and not self.is_stone_smashed:
            print(f"Player {self.player_id} (Petrified, Crouching: {self.was_crouching_when_petrified}) is being smashed.")
            self.is_stone_smashed = True
            self.stone_smashed_timer_start = pygame.time.get_ticks()
            # death_animation_finished will be false until smash anim is done or timer expires
            self.death_animation_finished = False
            set_player_state(self, 'smashed') # Use handler for state transition
        elif Player.print_limiter.can_print(f"smash_petrify_fail_{self.player_id}"):
            print(f"Player {self.player_id}: smash_petrification called but not petrified or already smashed. State: petrified={self.is_petrified}, smashed={self.is_stone_smashed}")


    def set_projectile_group_references(self, projectile_group: pygame.sprite.Group,
                                        all_sprites_group: pygame.sprite.Group):
        """Sets references to sprite groups needed for firing projectiles."""
        self.projectile_sprites_group = projectile_group
        self.all_sprites_group = all_sprites_group


    def can_stand_up(self, platforms_group: pygame.sprite.Group) -> bool:
        """Checks if the player can safely transition from crouching to standing."""
        if not self.is_crouching or not self._valid_init:
            return True # Not crouching or invalid, so can "stand" (or is already standing)

        # If collision heights are misconfigured, assume can stand to avoid getting stuck
        if self.standing_collision_height <= self.crouching_collision_height:
            if Player.print_limiter.can_print(f"can_stand_up_height_issue_{self.player_id}"):
                print(f"Player {self.player_id} Info: Standing height ({self.standing_collision_height}) "
                      f"<= crouching height ({self.crouching_collision_height}). Assuming can stand.")
            return True

        # Simulate the player's bounding box if they were standing
        current_feet_y = self.rect.bottom # Anchor to current feet position
        current_center_x = self.rect.centerx
        standing_width = self.rect.width # Assume width doesn't change significantly

        # Create a hypothetical rect for the standing player
        potential_standing_rect = pygame.Rect(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.bottom = current_feet_y
        potential_standing_rect.centerx = current_center_x

        # Check for collisions with platforms
        for platform in platforms_group:
            if potential_standing_rect.colliderect(platform.rect):
                # If a platform is above the player's current crouched head
                # and would intersect the standing rect, then cannot stand.
                if platform.rect.bottom > potential_standing_rect.top and platform.rect.top < self.rect.top : # Check if platform is above current head
                    return False # Collision detected, cannot stand
        return True # No collision, can stand


    # --- Delegated Methods ---
    def set_state(self, new_state: str):
        """Sets the player's logical state using the state handler."""
        set_player_state(self, new_state)

    def animate(self):
        """Updates the player's animation using the animation handler."""
        update_player_animation(self)


    def process_input(self, pygame_events, platforms_group, keys_pressed_override=None):
        """
        Processes raw input (keyboard/joystick) and translates it into game actions.
        Delegates to player_input_handler.
        Returns a dictionary of action events (e.g., {"jump": True}).
        """
        # Determine the correct key mapping based on player's control_scheme
        active_mappings_for_input: Dict[str, Any] = {}
        current_keys_for_input = keys_pressed_override if keys_pressed_override is not None else pygame.key.get_pressed()

        if self.control_scheme:
            if self.control_scheme == "keyboard_p1": active_mappings_for_input = game_config.P1_MAPPINGS
            elif self.control_scheme == "keyboard_p2": active_mappings_for_input = game_config.P2_MAPPINGS
            elif self.control_scheme.startswith("joystick_") and self.player_id == 1: active_mappings_for_input = game_config.P1_MAPPINGS
            elif self.control_scheme.startswith("joystick_") and self.player_id == 2: active_mappings_for_input = game_config.P2_MAPPINGS
            else: active_mappings_for_input = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS # Fallback
        else: active_mappings_for_input = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS # Fallback if no scheme

        return process_player_input_logic(self, current_keys_for_input, pygame_events, active_mappings_for_input, platforms_group)


    def handle_mapped_input(self, keys_pressed_state, pygame_event_list, key_map_dict, platforms_group):
        """
        DEPRECATED in favor of process_input if control_scheme is used.
        Processes input using an explicitly passed key_map_dict.
        """
        if Player.print_limiter.can_print(f"handle_mapped_input_call_{self.player_id}"):
            print(f"Player {self.player_id}: handle_mapped_input called directly. Control scheme: '{self.control_scheme}'. This method might be deprecated.")
        return process_player_input_logic(self, keys_pressed_state, pygame_event_list, key_map_dict, platforms_group)


    def _generic_fire_projectile(self, projectile_class, cooldown_attr_name, cooldown_const, projectile_config_name):
        """Generic method to fire any projectile type, handling cooldowns and spawn logic."""
        # Allow firing even if aflame/deflaming, but not if frozen/petrified/dead
        if not self._valid_init or self.is_dead or not self.alive() or \
           getattr(self, 'is_petrified', False) or \
           getattr(self, 'is_frozen', False) or getattr(self, 'is_defrosting', False):
             return

        if self.projectile_sprites_group is None or self.all_sprites_group is None:
            if self.print_limiter.can_print(f"player_{self.player_id}_fire_{projectile_config_name}_no_group_ref"):
                print(f"Player {self.player_id}: Cannot fire {projectile_config_name}, projectile/all_sprites group not set.")
            return

        current_time_ms = pygame.time.get_ticks()
        last_fire_time = getattr(self, cooldown_attr_name, 0)

        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms) # Update cooldown timer

            # Determine spawn position and direction
            spawn_x, spawn_y = self.rect.centerx, self.rect.centery
            current_aim_direction = self.fireball_last_input_dir.copy() # Use stored aim direction
            if current_aim_direction.length_squared() == 0: # Fallback if no aim input
                current_aim_direction.x = 1.0 if self.facing_right else -1.0
                current_aim_direction.y = 0.0

            # Offset projectile spawn slightly from player center based on aim
            proj_dims = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10,10)) # Get dimensions from constants
            offset_distance = (self.rect.width / 2) + (proj_dims[0] / 2) - 30 # Adjust base offset
            if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x): # If aiming mostly up/down
                offset_distance = (self.rect.height / 2) + (proj_dims[1] / 2) - 10 # Adjust for vertical

            if current_aim_direction.length_squared() > 0:
                offset_vector = current_aim_direction.normalize() * offset_distance
                spawn_x += offset_vector.x
                spawn_y += offset_vector.y

            # Create and add projectile
            new_projectile = projectile_class(spawn_x, spawn_y, current_aim_direction, self)
            if hasattr(self, 'game_elements_ref_for_projectiles'): # Pass game elements if available
                new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles
            self.projectile_sprites_group.add(new_projectile)
            self.all_sprites_group.add(new_projectile)

            # Special case: Blood projectile consumes health
            if projectile_config_name == 'blood' and self.current_health > 0:
                health_cost_percent = 0.05 # Example: 5% of current health
                health_cost_amount = self.current_health * health_cost_percent
                self.current_health -= health_cost_amount
                self.current_health = max(0, self.current_health)
                if self.current_health <= 0 and not self.is_dead:
                    self.set_state('death') # Player dies if health depleted by blood magic

    # Specific fire methods
    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')


    # --- Combat ---
    def check_attack_collisions(self, list_of_targets):
        """Delegates to player_combat_handler to check for attack hits."""
        check_player_attack_collisions(self, list_of_targets)

    def take_damage(self, damage_amount_taken):
        """Delegates to player_combat_handler to process damage taken."""
        player_take_damage(self, damage_amount_taken)

    def self_inflict_damage(self, damage_amount_to_self): # For debug
        """Delegates to player_combat_handler for self-inflicted damage."""
        player_self_inflict_damage(self, damage_amount_to_self)
    def self_inflict_damage_local_debug(self, damage_amount_to_self): # For client-side debug for P1
        """Local debug version of self-inflict damage."""
        player_self_inflict_damage(self, damage_amount_to_self)

    def heal_to_full(self): # For debug
        """Delegates to player_combat_handler for healing."""
        player_heal_to_full(self)
    def heal_to_full_local_debug(self): # For client-side debug for P1
        """Local debug version of heal to full."""
        player_heal_to_full(self)

    # --- Network ---
    def get_network_data(self):
        """Delegates to player_network_handler to get data for network sync."""
        # Ensure was_crouching_when_petrified is included
        data = get_player_network_data(self)
        data['was_crouching_when_petrified'] = self.was_crouching_when_petrified
        return data


    def set_network_data(self, received_network_data):
        """Delegates to player_network_handler to apply received network data."""
        set_player_network_data(self, received_network_data) # Includes petrify flags
        # Ensure this specific flag is also updated from network data
        self.was_crouching_when_petrified = received_network_data.get('was_crouching_when_petrified', self.was_crouching_when_petrified)


    def handle_network_input(self, network_input_data_dict):
        """Delegates to player_network_handler to process input received over network."""
        handle_player_network_input(self, network_input_data_dict)


    def get_input_state_for_network(self, keys_state, events, key_map):
        """
        Processes local input and returns a dictionary of states/events for network transmission.
        Relies on player_input_handler.process_player_input_logic for action events.
        """
        # Get a reference to the platform group, if available.
        # This is needed by process_player_input_logic for crouch/stand checks.
        platforms_group_for_input = pygame.sprite.Group() # Empty group by default
        if hasattr(self, 'game_elements_ref_for_projectiles') and \
           self.game_elements_ref_for_projectiles and \
           'platform_sprites' in self.game_elements_ref_for_projectiles:
            platforms_group_for_input = self.game_elements_ref_for_projectiles['platform_sprites']

        # Get one-time action events (like jump_pressed, attack1_pressed)
        processed_action_events = process_player_input_logic(self, keys_state, events, key_map, platforms_group_for_input)

        # Build the dictionary for network transmission
        network_input_dict = {
            'left_held': self.is_trying_to_move_left,
            'right_held': self.is_trying_to_move_right,
            'up_held': self.is_holding_climb_ability_key,
            'down_held': self.is_holding_crouch_ability_key,
            'is_crouching_state': self.is_crouching, # Current logical crouch state
            # Aiming direction
            'fireball_aim_x': self.fireball_last_input_dir.x,
            'fireball_aim_y': self.fireball_last_input_dir.y
        }
        # Merge the processed action events (jump, attack, etc.)
        network_input_dict.update(processed_action_events)
        return network_input_dict


    # --- Collision Wrappers (delegating to player_collision_handler) ---
    def check_platform_collisions(self, direction: str, platforms_group: pygame.sprite.Group):
        check_player_platform_collisions(self, direction, platforms_group)

    def check_ladder_collisions(self, ladders_group: pygame.sprite.Group):
        check_player_ladder_collisions(self, ladders_group)

    def check_character_collisions(self, direction: str, characters_list: list):
        return check_player_character_collisions(self, direction, characters_list)

    def check_hazard_collisions(self, hazards_group: pygame.sprite.Group):
        check_player_hazard_collisions(self, hazards_group)

    # --- Main Update Loop ---
    def update(self, dt_sec, platforms_group, ladders_group, hazards_group,
               other_players_sprite_list, enemies_sprite_list):
        """Main update loop for the player."""

        current_time_ms_for_status = pygame.time.get_ticks()
        self.update_status_effects(current_time_ms_for_status) # Manage timers for aflame/frozen etc.

        # If petrified and smashed, handle disappearance timer
        if self.is_stone_smashed:
            if current_time_ms_for_status - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                self.kill() # Remove sprite after duration
                return
            self.animate() # Play smashed animation
            return # No other updates if smashed

        # If just petrified (not smashed), remain static
        if self.is_petrified:
            # Could add gravity if petrified in air, but for now, assume it stops
            self.vel.xy = 0,0
            self.acc.xy = 0,0 # No gravity or other forces
            self.animate() # Show petrified (standing or crouched) static image
            return

        # If not petrified/smashed, proceed with normal core logic
        update_player_core_logic(self, dt_sec, platforms_group, ladders_group, hazards_group,
                                 other_players_sprite_list, enemies_sprite_list)

    # --- Reset ---
    def reset_state(self, spawn_position_tuple: tuple):
        """Resets the player to their initial state at the spawn position."""
        # If animations were critically missing, try to reload them
        if not self._valid_init and self.animations is None:
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True # Potentially valid again
                # Re-initialize heights
                try:
                    self.standing_collision_height = self.animations['idle'][0].get_height() if self.animations.get('idle') else 60
                    self.crouching_collision_height = self.animations['crouch'][0].get_height() if self.animations.get('crouch') else 30
                    if self.standing_collision_height == 0 or self.crouching_collision_height == 0 or \
                       self.crouching_collision_height >= self.standing_collision_height:
                        self._valid_init = False # Mark invalid again if heights are bad
                except: self._valid_init = False # Mark invalid on any error

                idle_frames = self.animations.get('idle')
                if idle_frames and len(idle_frames) > 0: self.image = idle_frames[0]
                else: self.image = pygame.Surface((30, self.standing_collision_height or 60)); self.image.fill(C.RED)
            else:
                if Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"):
                    print(f"Player {self.player_id} Error: Failed to load animations during reset. Player remains invalid.")
                return # Cannot proceed with reset if animations still missing


        # Reset position and physics
        self.pos = pygame.math.Vector2(spawn_position_tuple)
        self.rect.midbottom = (round(self.pos.x), round(self.pos.y)) # Anchor by feet
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY if hasattr(C, 'PLAYER_GRAVITY') else 0.7) # Default gravity

        # Reset health and flags
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True # Default facing

        # Reset timers
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;

        # Reset projectile cooldowns and aim
        self.fireball_cooldown_timer = 0
        self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0
        self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0
        self.fireball_last_input_dir = pygame.math.Vector2(1.0, 0.0) # Reset aim

        # Reset status effect flags and timers
        self.is_aflame = False; self.aflame_timer_start = 0
        self.is_deflaming = False; self.deflame_timer_start = 0; self.aflame_damage_last_tick = 0
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0

        self.is_petrified = False # Reset petrification
        self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right # Reset to current facing
        self.was_crouching_when_petrified = False # Reset this flag

        # Re-load stone assets to ensure original state if they were modified (e.g., flipped during gameplay)
        stone_common_folder = os.path.join('characters', 'Stone')
        # Standing Stone
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        loaded_common_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_common_stone_frames and not (len(loaded_common_stone_frames) == 1 and loaded_common_stone_frames[0].get_size() == (30,40) and loaded_common_stone_frames[0].get_at((0,0)) == C.RED):
            self.stone_image_frame_original = loaded_common_stone_frames[0]
        else: self.stone_image_frame_original = (self.animations.get('petrified') or [self._create_placeholder_surface(C.GRAY, "StoneP")])[0]
        self.stone_image_frame = self.stone_image_frame_original

        # Standing Smashed Stone
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))
        loaded_common_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_common_smashed_frames and not (len(loaded_common_smashed_frames) == 1 and loaded_common_smashed_frames[0].get_size() == (30,40) and loaded_common_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_smashed_frames_original = loaded_common_smashed_frames
        else: self.stone_smashed_frames_original = (self.animations.get('smashed') or [self._create_placeholder_surface(C.DARK_GRAY, "SmashP")])
        self.stone_smashed_frames = list(self.stone_smashed_frames_original)

        # Crouching Stone
        common_stone_crouch_png_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouch.png'))
        loaded_common_stone_crouch_frames = load_gif_frames(common_stone_crouch_png_path)
        if loaded_common_stone_crouch_frames and not (len(loaded_common_stone_crouch_frames) == 1 and loaded_common_stone_crouch_frames[0].get_size() == (30,40) and loaded_common_stone_crouch_frames[0].get_at((0,0)) == C.RED):
            self.stone_crouch_image_frame_original = loaded_common_stone_crouch_frames[0]
        else: self.stone_crouch_image_frame_original = self.stone_image_frame_original # Fallback to standing if already loaded
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original

        # Crouching Smashed Stone
        common_stone_crouch_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouchSmashed.gif'))
        loaded_common_crouch_smashed_frames = load_gif_frames(common_stone_crouch_smashed_gif_path)
        if loaded_common_crouch_smashed_frames and not (len(loaded_common_crouch_smashed_frames) == 1 and loaded_common_crouch_smashed_frames[0].get_size() == (30,40) and loaded_common_crouch_smashed_frames[0].get_at((0,0)) == C.RED):
            self.stone_crouch_smashed_frames_original = loaded_common_crouch_smashed_frames
        else: self.stone_crouch_smashed_frames_original = list(self.stone_smashed_frames_original) # Fallback to standing smashed
        self.stone_crouch_smashed_frames = list(self.stone_crouch_smashed_frames_original)


        # Reset visual state (alpha if faded)
        if hasattr(self.image, 'set_alpha') and hasattr(self.image, 'get_alpha') and \
           self.image.get_alpha() is not None and self.image.get_alpha() < 255:
            self.image.set_alpha(255)

        # Set initial state and animate
        set_player_state(self, 'idle') # Use handler to ensure consistency