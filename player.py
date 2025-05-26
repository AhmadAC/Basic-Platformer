# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes, collision heights, and
delegating state, animation, physics, collisions, input, combat, and network handling
to respective handler modules. Refactored for PySide6.
Player.reset_state() method has been REMOVED. Player reset is handled by game_state_manager.
Wall climb functionality REMOVED.
Collision rect is now tighter than visual sprite.
can_stand_up logic improved.
Corrected camera.apply usage in draw_pyside.
MODIFIED: Added insta_kill method for chest crush.
MODIFIED: Ensure timer consistency for status effects by passing current_time_ms to set_player_state.
MODIFIED: Added overall_fire_effect_start_time for 5-second fire cycle override.
"""
# version 2.1.11 (5-second fire cycle override)

import os
import sys
import math
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage, QKeyEvent
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game-specific imports
from assets import load_all_player_animations, load_gif_frames, resource_path
from utils import PrintLimiter
import constants as C
import config as game_config

# Handler modules
try:
    from player_state_handler import set_player_state
    from player_animation_handler import update_player_animation
    from player_movement_physics import update_player_core_logic
    from player_collision_handler import (
        check_player_platform_collisions, check_player_ladder_collisions,
        check_player_character_collisions, check_player_hazard_collisions
    )
    from player_input_handler import process_player_input_logic
    from player_combat_handler import (
        check_player_attack_collisions, player_take_damage,
        player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input
    )
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    from logger import info, debug, warning, error, critical
except ImportError as e:
    # This basic print is a last resort if logger itself fails.
    print(f"CRITICAL PLAYER.PY IMPORT ERROR: {e}. Some functionalities might be broken.")
    # Define dummy functions if logger fails, to prevent NameErrors later
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")
    # Dummy for set_player_state if its import failed
    if 'set_player_state' not in globals():
        def set_player_state(player, new_state, current_game_time_ms_param=None): # Add param for consistency
            if hasattr(player, 'state'): player.state = new_state
            warning("Fallback set_player_state used.")


if TYPE_CHECKING:
    from app_core import MainWindow
    from camera import Camera as CameraClass_TYPE
    # If player_status_effects is directly called from Player methods (it isn't currently for setting effects)
    # from player_status_effects import apply_aflame_effect as apply_aflame_to_player_direct etc.

_start_time_player_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_monotonic) * 1000)

class Player:
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x: float, start_y: float, player_id: int = 1,
                 initial_properties: Optional[Dict[str, Any]] = None):
        self.player_id = player_id
        self._valid_init = True
        self.properties = initial_properties if initial_properties is not None else {}
        self.control_scheme: Optional[str] = None
        self.joystick_id_idx: Optional[int] = None
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None

        self.initial_spawn_pos = QPointF(float(start_x), float(start_y))
        self.pos = QPointF(self.initial_spawn_pos)

        if self.player_id == 1: asset_folder = 'characters/player1'
        elif self.player_id == 2: asset_folder = 'characters/player2'
        elif self.player_id == 3: asset_folder = 'characters/player3'
        elif self.player_id == 4: asset_folder = 'characters/player4'
        else: asset_folder = 'characters/player1' # Default fallback

        self.animations: Optional[Dict[str, List[QPixmap]]] = None
        try:
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        except Exception as e_anim_load:
            critical(f"Player {self.player_id}: Exception during load_all_player_animations from '{asset_folder}': {e_anim_load}", exc_info=True)
            self._valid_init = False
        if self.animations is None:
            critical(f"Player Init Error (ID: {self.player_id}): Failed loading animations from '{asset_folder}'. Player invalid.")
            self._valid_init = False

        # Collision dimensions
        self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6) # Base width for standing
        self.base_crouch_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.7) # Base width for crouching
        self.standing_collision_height: float = 60.0 # Default, might be overridden
        self.crouching_collision_height: float = 30.0 # Default, might be overridden
        # Add to Player.__init__ in player.py
        self.is_tipping: bool = False
        self.tipping_angle: float = 0.0  # Degrees
        self.tipping_direction: int = 0  # -1 if tipping left (falling off left), 1 if tipping right
        self.tipping_pivot_x_world: float = 0.0 # The world X-coordinate of the pivot point (ledge edge)
        # Core attributes
        self.image: Optional[QPixmap] = None
        self.rect = QRectF() # Collision rectangle
        self.vel = QPointF(0.0, 0.0) # Velocity vector
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7))) # Acceleration vector
        self.state: str = 'idle' # Current logical state
        self.current_frame: int = 0 # Current animation frame index
        self.last_anim_update: int = 0 # Timestamp of last animation update
        self._last_facing_right: bool = True # For animation logic to detect facing change
        self.facing_right: bool = True # Current facing direction
        self.on_ground: bool = False
        self.on_ladder: bool = False
        self.can_grab_ladder: bool = False
        self.touching_wall: int = 0 # -1 for left, 1 for right, 0 for none
        self.can_wall_jump: bool = False
        self.is_crouching: bool = False # True if player is in a crouch state

        # Action Timers & Durations
        self.is_dashing: bool = False; self.dash_timer: int = 0
        self.dash_duration: int = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling: bool = False; self.roll_timer: int = 0
        self.roll_duration: int = int(getattr(C, 'PLAYER_ROLL_DURATION', 300)) # Typically longer than dash
        self.is_sliding: bool = False; self.slide_timer: int = 0
        self.slide_duration: int = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        # Combat
        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = int(getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300))
        self.attack_type: int = 0 # 1 for primary, 2 for secondary, 3 for combo, 4 for crouch
        self.can_combo: bool = False
        self.combo_window: int = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))
        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600)) # Invincibility after hit

        # Health & Status
        self.is_dead: bool = False
        self.death_animation_finished: bool = False
        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'PLAYER_MAX_HEALTH', 100)))
        self.current_health: int = self.max_health
        self._alive: bool = True # Overall liveness, used by game loop to stop processing

        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0) # Example, adjust based on sprites
        self.standard_height: float = 60.0 # Used as a fallback if animations fail

        # Input intent flags (set by input_handler)
        self.is_trying_to_move_left: bool = False
        self.is_trying_to_move_right: bool = False
        self.is_holding_climb_ability_key: bool = False # Used for ladder climb up, was wall climb
        self.is_holding_crouch_ability_key: bool = False # Used for ladder climb down, or general crouch hold

        # Projectile cooldowns
        current_time_for_init_cooldown = get_current_ticks_monotonic()
        self.fireball_cooldown_timer: int = current_time_for_init_cooldown - C.FIREBALL_COOLDOWN
        self.poison_cooldown_timer: int = current_time_for_init_cooldown - C.POISON_COOLDOWN
        self.bolt_cooldown_timer: int = current_time_for_init_cooldown - C.BOLT_COOLDOWN
        self.blood_cooldown_timer: int = current_time_for_init_cooldown - C.BLOOD_COOLDOWN
        self.ice_cooldown_timer: int = current_time_for_init_cooldown - C.ICE_COOLDOWN
        self.shadow_cooldown_timer: int = current_time_for_init_cooldown - C.SHADOW_PROJECTILE_COOLDOWN
        self.grey_cooldown_timer: int = current_time_for_init_cooldown - C.GREY_PROJECTILE_COOLDOWN

        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aiming right

        # Status Effect Flags & Timers
        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.overall_fire_effect_start_time: int = 0 # MODIFIED: For 5s total fire cycle

        self.is_frozen: bool = False; self.is_defrosting: bool = False
        self.frozen_effect_timer: int = 0

        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = True # Which way player was facing when petrified
        self.was_crouching_when_petrified: bool = False # Visual variant for petrified statue

        self.state_timer: int = 0 # General timer for current state, if needed

        # For joystick discrete event priming (input_handler)
        self._prev_discrete_axis_hat_state: Dict[Tuple[str, int, Tuple[int, int]], bool] = {}
        self._first_joystick_input_poll_done: bool = False # Flag to prime joystick on first poll

        if self._valid_init and self.animations:
            try:
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                    self.standing_collision_height = float(idle_frames[0].height() * 0.85) # Slightly smaller than visual
                    self.base_standing_collision_width = float(idle_frames[0].width() * 0.5)
                else: # Fallback if idle frames missing
                    self.standing_collision_height = float(getattr(C, 'TILE_SIZE', 40) * 1.5)
                    self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6)

                crouch_frames = self.animations.get('crouch')
                if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                    self.crouching_collision_height = float(crouch_frames[0].height() * 0.9)
                    self.base_crouch_collision_width = float(crouch_frames[0].width() * 0.7)
                else: # Fallback if crouch frames missing
                    self.crouching_collision_height = self.standing_collision_height * 0.55
                    self.base_crouch_collision_width = self.base_standing_collision_width * 1.1

                if not (1e-6 < self.standing_collision_height < 1000 and 1e-6 < self.crouching_collision_height < self.standing_collision_height):
                    critical(f"Player {self.player_id}: Invalid collision heights derived from animations. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                    self._valid_init = False
                
                self.standard_height = self.standing_collision_height # For fallback if needed

                # Set initial image
                initial_idle_frames = self.animations.get('idle')
                if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
                    self.image = initial_idle_frames[0]
                else: # Critical if idle is missing
                    self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'RED', (255,0,0))), "NoIdle")
                    self._valid_init = False
            except Exception as e_col_h:
                error(f"Player {self.player_id} Exception setting collision heights from animations: {e_col_h}", exc_info=True)
                self._valid_init = False
        elif not self._valid_init: # If animations failed to load at all
            self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "AnimFail")

        self._update_rect_from_image_and_pos() # Initialize rect based on current collision height and image
        self._assign_projectile_keys()
        self._init_stone_assets() # Load common stone/smashed assets

        if not self._valid_init:
            self.is_dead = True; self._alive = False; self.current_health = 0
            warning(f"Player {self.player_id}: Initialization completed with _valid_init as False. Player might be non-functional.")
        else:
            self.last_anim_update = get_current_ticks_monotonic() # Set after valid init
            debug(f"Player {self.player_id} initialized. Valid: {self._valid_init}. CollisionRect: W{self.rect.width():.1f} H{self.rect.height():.1f}")


    def reset_for_new_game_or_round(self):
        """Resets timers and input priming flags, typically called by game_setup on full map reload."""
        debug(f"Player {self.player_id}: Resetting input priming and cooldowns for new game/round.")
        self._first_joystick_input_poll_done = False
        self._prev_discrete_axis_hat_state.clear()

        current_time_reset = get_current_ticks_monotonic()
        self.fireball_cooldown_timer = current_time_reset - C.FIREBALL_COOLDOWN
        self.poison_cooldown_timer = current_time_reset - C.POISON_COOLDOWN
        self.bolt_cooldown_timer = current_time_reset - C.BOLT_COOLDOWN
        self.blood_cooldown_timer = current_time_reset - C.BLOOD_COOLDOWN
        self.ice_cooldown_timer = current_time_reset - C.ICE_COOLDOWN
        self.shadow_cooldown_timer = current_time_reset - C.SHADOW_PROJECTILE_COOLDOWN
        self.grey_cooldown_timer = current_time_reset - C.GREY_PROJECTILE_COOLDOWN
        debug(f"Player {self.player_id}: Projectile cooldowns reset for immediate use.")


    def _init_stone_assets(self):
        """Loads common stone/smashed assets for petrification."""
        stone_common_folder = os.path.join('characters', 'Stone')
        qcolor_gray = QColor(*getattr(C,'GRAY', (128,128,128)))
        qcolor_dark_gray = QColor(*getattr(C,'DARK_GRAY', (50,50,50)))

        # Helper to load or create placeholder, checking player's own animations first
        def load_or_placeholder(path_suffix, default_placeholder_color, default_placeholder_text, is_list=False):
            anim_key_fallback: Optional[str] = None
            if "Stone.png" in path_suffix: anim_key_fallback = 'petrified'
            elif "Smashed.gif" in path_suffix: anim_key_fallback = 'smashed'
            elif "StoneCrouch.png" in path_suffix: anim_key_fallback = 'petrified' # Use standing if crouch specific missing
            elif "StoneCrouchSmashed.gif" in path_suffix: anim_key_fallback = 'smashed' # Use standing if crouch specific missing

            # Try player's specific animation first if key matches
            if anim_key_fallback and self.animations:
                player_specific_frames = self.animations.get(anim_key_fallback)
                if player_specific_frames and not self._is_placeholder_qpixmap(player_specific_frames[0]):
                    debug(f"Player {self.player_id} StoneAsset: Using player's own '{anim_key_fallback}' anim for stone effect '{path_suffix}'.")
                    return player_specific_frames if is_list else player_specific_frames[0]
            
            # Fallback to common assets
            full_path = resource_path(os.path.join(stone_common_folder, path_suffix))
            frames = load_gif_frames(full_path)
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]

            warning(f"Player {self.player_id} StoneAsset: Failed to load '{path_suffix}' (common and player-specific). Using placeholder.")
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        self.stone_image_frame_original = load_or_placeholder('__Stone.png', qcolor_gray, "StoneP")
        self.stone_image_frame = self.stone_image_frame_original.copy()
        self.stone_smashed_frames_original = load_or_placeholder('__StoneSmashed.gif', qcolor_dark_gray, "SmashP", is_list=True)
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]
        
        self.stone_crouch_image_frame_original = load_or_placeholder('__StoneCrouch.png', qcolor_gray, "SCrouchP")
        if self._is_placeholder_qpixmap(self.stone_crouch_image_frame_original) and not self._is_placeholder_qpixmap(self.stone_image_frame_original):
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy() # Fallback to standing stone if crouch stone fails
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()
        
        self.stone_crouch_smashed_frames_original = load_or_placeholder('__StoneCrouchSmashed.gif', qcolor_dark_gray, "SCSmashP", is_list=True)
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]) and \
           not (len(self.stone_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_smashed_frames_original[0])):
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original] # Fallback to standing smash
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]


    def _assign_projectile_keys(self):
        # Assigns string identifiers for projectile activation keys based on player ID
        # These are for reference; actual key mapping is handled by config.py and input_handler.
        if self.player_id == 1: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P1_FIREBALL_KEY, C.P1_POISON_KEY, C.P1_BOLT_KEY, C.P1_BLOOD_KEY, C.P1_ICE_KEY, C.P1_SHADOW_PROJECTILE_KEY, C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P2_FIREBALL_KEY, C.P2_POISON_KEY, C.P2_BOLT_KEY, C.P2_BLOOD_KEY, C.P2_ICE_KEY, C.P2_SHADOW_PROJECTILE_KEY, C.P2_GREY_PROJECTILE_KEY
        elif self.player_id == 3: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P3_FIREBALL_KEY, C.P3_POISON_KEY, C.P3_BOLT_KEY, C.P3_BLOOD_KEY, C.P3_ICE_KEY, C.P3_SHADOW_PROJECTILE_KEY, C.P3_GREY_PROJECTILE_KEY
        elif self.player_id == 4: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P4_FIREBALL_KEY, C.P4_POISON_KEY, C.P4_BOLT_KEY, C.P4_BLOOD_KEY, C.P4_ICE_KEY, C.P4_SHADOW_PROJECTILE_KEY, C.P4_GREY_PROJECTILE_KEY
        # else: No specific keys for P > 4 for now

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        # Uses current collision height to size the placeholder appropriately
        h = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        if h <= 1e-6 : h = self.standard_height # Use standard_height if current collision height is invalid
        if h <= 1e-6 : h = 60.0 # Absolute fallback height
        
        w = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width
        if w <= 1e-6 : w = h * 0.5 # Approx aspect ratio if width is invalid

        pixmap = QPixmap(max(10, int(w)), max(10, int(h))) # Ensure minimum size
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0))))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1)) # Draw border inside
        try:
            font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e:
            error(f"PLAYER PlaceholderFontError (P{self.player_id}): {e}", exc_info=True)
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        # Check against common placeholder sizes/colors used in assets.py and here
        if pixmap.size() in [QSize(30,40), QSize(30,60), QSize(10,10)]: # Common placeholder sizes
            qimage = pixmap.toImage()
            if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_magenta = QColor(*getattr(C, 'MAGENTA', (255,0,255)))
                if color_at_origin in [qcolor_red, qcolor_blue, qcolor_magenta]:
                    return True
        return False


    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        """Updates self.rect (collision rect) based on self.pos (which is midbottom) and current collision height/width."""
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF): # Ensure target_pos is valid
            target_pos = self.pos if isinstance(self.pos, QPointF) else QPointF(self.initial_spawn_pos)

        # Use current collision dimensions, not visual image dimensions
        current_collision_height = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        current_collision_width = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width

        # Fallback if collision dimensions are invalid (should be rare after init)
        if current_collision_height <= 1e-6: current_collision_height = self.standard_height
        if current_collision_width <= 1e-6: current_collision_width = current_collision_height * 0.5 # Approx aspect

        rect_x = target_pos.x() - current_collision_width / 2.0
        rect_y = target_pos.y() - current_collision_height # Midbottom anchor

        # Ensure self.rect exists and update it
        if not hasattr(self, 'rect') or self.rect is None:
            self.rect = QRectF(rect_x, rect_y, current_collision_width, current_collision_height)
        else:
            self.rect.setRect(rect_x, rect_y, current_collision_width, current_collision_height)

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        if self._alive: # Only log if it was previously alive
            debug(f"Player {self.player_id} kill() called.")
        self._alive = False
        # is_dead might be set by state handler or take_damage, kill() is for game loop removal

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True # Not crouching or invalid, so can "stand"
        # If standing height is not significantly greater than crouching, assume can stand
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True

        current_crouch_rect = self.rect # Current collision rect (crouched)
        current_feet_y = current_crouch_rect.bottom()
        current_center_x = current_crouch_rect.center().x()

        # Calculate potential standing rect dimensions
        potential_standing_width = self.base_standing_collision_width
        potential_standing_height = self.standing_collision_height

        # Calculate top-left of potential standing rect, anchored at current feet Y and center X
        potential_standing_rect_left = current_center_x - (potential_standing_width / 2.0)
        potential_standing_rect_top = current_feet_y - potential_standing_height
        potential_standing_rect = QRectF(potential_standing_rect_left, potential_standing_rect_top,
                                         potential_standing_width, potential_standing_height)

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF):
                if potential_standing_rect.intersects(platform_obj.rect):
                    # Check if the intersection is with a platform above the player's crouched head
                    if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                       platform_obj.rect.top() < current_crouch_rect.top(): # Platform is at/above where head would be
                        if self.print_limiter.can_log(f"cannot_stand_p{self.player_id}"):
                             debug(f"Player {self.player_id} cannot stand: Blocked by platform {platform_obj.rect} "
                                   f"(Pot. Stand Rect: {potential_standing_rect}, Crouch Top: {current_crouch_rect.top()})")
                        return False
        if self.print_limiter.can_log(f"can_stand_p{self.player_id}"):
             debug(f"Player {self.player_id} can stand up. (Pot. Stand Rect: {potential_standing_rect})")
        return True

    # --- Delegated Methods ---
    def set_state(self, new_state: str, current_game_time_ms_param: Optional[int] = None): # MODIFIED
        # Pass time to ensure timer consistency for status effects
        set_player_state(self, new_state, current_game_time_ms_param) # MODIFIED

    def animate(self):
        update_player_animation(self)

    def process_input(self,
                      qt_keys_held_snapshot: Dict[Qt.Key, bool],
                      qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
                      platforms_list: List[Any], # For can_stand_up check
                      joystick_data_for_handler: Optional[Dict[str, Any]] = None # Pygame data
                     ) -> Dict[str, bool]: # Returns discrete action events
        # Determine active mappings based on player's control_scheme
        active_mappings = {}
        player_id_for_map_get = self.player_id # Use instance player_id

        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_pygame_"):
            # Use the player's specific runtime map for their assigned joystick
            active_mappings = getattr(game_config, f"P{player_id_for_map_get}_MAPPINGS", game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS)
        else: # Fallback if control_scheme is None or unrecognized
            active_mappings = game_config.P1_MAPPINGS if self.player_id == 1 else game_config.P2_MAPPINGS # Example fallback
            if Player.print_limiter.can_log(f"p_input_scheme_fallback_{self.player_id}"):
                warning(f"Player {self.player_id}: Unrecognized control_scheme '{self.control_scheme}'. Using default keyboard map.")

        return process_player_input_logic(self, qt_keys_held_snapshot, qt_key_event_data_this_frame,
                                          active_mappings, platforms_list, joystick_data_for_handler)

    # Projectile Firing (Generic Handler)
    def _generic_fire_projectile(self, projectile_class: type, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        # Ensure player can fire
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting:
            return

        # Check game elements reference (set by game_setup or player_network_handler)
        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_log(f"proj_fire_no_game_elements_{self.player_id}"):
                warning(f"Player {self.player_id}: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return

        projectiles_list_ref: Optional[List[Any]] = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref: Optional[List[Any]] = self.game_elements_ref_for_projectiles.get("all_renderable_objects")
        # platforms_list_for_proj_coll = self.game_elements_ref_for_projectiles.get("platforms_list") # Not directly used in this method

        if projectiles_list_ref is None or all_renderables_ref is None:
            if Player.print_limiter.can_log(f"proj_fire_list_missing_{self.player_id}"):
                warning(f"Player {self.player_id}: Projectile or renderable list missing from game_elements_ref. Cannot fire {projectile_config_name}.")
            return

        current_time_ms = get_current_ticks_monotonic() # Use monotonic time
        last_fire_time = getattr(self, cooldown_attr_name, 0)

        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms) # Update cooldown timer

            # Determine spawn position and direction
            if self.rect.isNull(): self._update_rect_from_image_and_pos() # Ensure rect is current
            if self.rect.isNull(): error(f"Player {self.player_id}: Rect is null, cannot fire projectile."); return

            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6): # Fallback if aim_dir is zero vector
                aim_dir.setX(1.0 if self.facing_right else -1.0)
                aim_dir.setY(0.0)

            # Offset projectile spawn slightly from player center
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0)) # Default if const missing
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0 # Adjust '-5.0' for better visual origin
            # Check if aiming mostly up/down for vertical offset
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): # More vertical than horizontal
                 offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0

            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: # Avoid division by zero
                norm_x = aim_dir.x()/length
                norm_y = aim_dir.y()/length

            spawn_x += norm_x * offset_dist
            spawn_y += norm_y * offset_dist

            # Create and add projectile
            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles # Pass reference

            projectiles_list_ref.append(new_projectile)
            all_renderables_ref.append(new_projectile) # Ensure it's rendered

            if Player.print_limiter.can_log(f"fired_{projectile_config_name}_{self.player_id}"):
                debug(f"Player {self.player_id} fired {projectile_config_name} at ({spawn_x:.1f},{spawn_y:.1f}) dir ({aim_dir.x():.1f},{aim_dir.y():.1f})")

            # Special case for BloodShot (example of self-damage projectile)
            if projectile_config_name == 'blood' and self.current_health > 0: # Example: costs 5% health
                self.current_health -= self.current_health * 0.05 # Lose 5% of current health
                if self.current_health <= 0 and not self.is_dead:
                    self.set_state('death', get_current_ticks_monotonic()) # MODIFIED: Pass time

    # Specific projectile fire methods
    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')

    # Combat and Collision
    def check_attack_collisions(self, list_of_targets: List[Any]): check_player_attack_collisions(self, list_of_targets)
    def take_damage(self, damage_amount_taken: int): player_take_damage(self, damage_amount_taken)
    def self_inflict_damage(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)
    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]) -> bool: return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    def insta_kill(self):
        """Instantly kills the player, bypassing normal damage mechanics."""
        if not self._valid_init or self.is_dead or not self._alive: return # No effect if already gone
        player_id_log = f"P{self.player_id}" # For logging
        info(f"Player {player_id_log}: insta_kill() called.")
        self.current_health = 0
        self.is_dead = True # Mark as dead
        # Transition to death state, ensuring animation plays
        self.set_state('death', get_current_ticks_monotonic()) # MODIFIED: Pass time
        if hasattr(self, 'animate'): self.animate() # Update animation immediately if possible


    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
               hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
        if not self._valid_init or not self._alive: return # Do nothing if not valid or not "alive"

        current_time_ms = get_current_ticks_monotonic()
        # Update status effects (like aflame, frozen, petrified timers and effects)
        # The update_status_effects function now returns True if an effect fully overrides other updates
        status_overrode_update = False
        # Call the Player's own update_status_effects method
        status_overrode_update = self.update_status_effects(current_time_ms)

        if status_overrode_update: # e.g., frozen, petrified, or 5s fire timeout occurred
            if hasattr(self, 'animate'): self.animate() # Still animate to show visual status
            return # Skip core logic if status effect took precedence

        # Core logic (movement, physics, collisions) if not overridden by a terminal status effect
        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)


    def update_status_effects(self, current_time_ms: int) -> bool:
        """
        Manages the player's status effects, including duration checks,
        damage over time, and state transitions based on those effects.
        This method is now part of the Player class.
        Returns True if a status effect fully handled the update for this frame,
        False otherwise (allowing normal player logic to proceed).
        """
        player_id_log = f"P{self.player_id}"

        # --- Overall 5-second fire effect timeout ---
        if (self.is_aflame or self.is_deflaming) and \
           hasattr(self, 'overall_fire_effect_start_time') and \
           self.overall_fire_effect_start_time > 0:
            
            if current_time_ms - self.overall_fire_effect_start_time > 5000: # 5 seconds
                if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"force_idle_after_5s_fire_{self.player_id}"):
                    debug(f"Player {player_id_log}: Overall 5s fire effect duration met. Forcing state to 'idle'.")
                
                # Force clear all fire-related flags
                self.is_aflame = False
                self.is_deflaming = False
                self.overall_fire_effect_start_time = 0 
                
                # Force state to 'idle' and ensure player is on ground visually/logically for this state.
                self.on_ground = True 
                if hasattr(self.vel, 'setY'): self.vel.setY(0)      
                if hasattr(self.acc, 'setY'): self.acc.setY(0)
                self.set_state('idle', current_time_ms) # Pass current_time_ms, calls player_state_handler's set_player_state
                
                return True # This change takes precedence for this frame.
        # --- END MODIFICATION ---

        # Petrified/Smashed checks
        if self.is_stone_smashed:
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                if not self.death_animation_finished: self.death_animation_finished = True
                self.kill() # Mark as fully gone
            # Smashed animation is handled by main animate call if this returns True
            return True # Smashed overrides everything else

        if self.is_petrified: # Implicitly not smashed if this block is reached
            # Player is a statue. Most logic is inert.
            # Gravity for petrified (if airborne when petrified) is handled by PlayerMovementPhysics.
            # Animation is static 'petrified' frame.
            return True # Petrified overrides other active effects like fire/freeze

        # Frozen/Defrost checks
        if self.is_frozen:
            if current_time_ms - self.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
                self.set_state('defrost', current_time_ms) # Calls player_state_handler
            return True # Frozen overrides other movement/actions
        elif self.is_defrosting:
            if current_time_ms - self.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
                # is_defrosting flag will be cleared by set_player_state when transitioning to idle/fall
                self.set_state('idle' if self.on_ground else 'fall', current_time_ms) # Calls player_state_handler
                # Fall through to allow normal logic if defrost just ended this frame.
            else:
                return True # Defrosting still overrides other movement/actions

        # Aflame/Deflame cycle (will only run if the 5s overall timer hasn't forced 'idle' yet)
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                # Player has been aflame for 3s, transition to deflame.
                # overall_fire_effect_start_time is NOT reset here, it continues.
                if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"aflame_to_deflame_{self.player_id}"):
                    debug(f"Player ({player_id_log}): Aflame duration ({C.PLAYER_AFLAME_DURATION_MS}ms) ended. Transitioning to 'deflame'.")
                self.set_state('deflame_crouch' if self.is_crouching else 'deflame', current_time_ms) # Calls player_state_handler
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                if hasattr(self, 'take_damage'): # Ensure method exists
                    self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
                self.aflame_damage_last_tick = current_time_ms
            # Aflame allows controlled movement, so don't return True; let core logic run.
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
                # Deflame duration (another 3s) ended. This path is taken if the 5s overall timer didn't fire first.
                if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"deflame_to_normal_{self.player_id}"):
                    debug(f"Player ({player_id_log}): Deflame duration ({C.PLAYER_DEFLAME_DURATION_MS}ms) ended. Transitioning to normal state.")
                
                player_state_on_deflame_end = 'crouch' if self.is_crouching else ('idle' if self.on_ground else 'fall')
                
                # Explicitly clear flags and overall timer here as this is the natural end of the fire cycle
                self.is_aflame = False # Should already be false
                self.is_deflaming = False
                self.overall_fire_effect_start_time = 0 # Reset 5s timer too
                
                self.set_state(player_state_on_deflame_end, current_time_ms) # Calls player_state_handler
            # Deflaming also allows controlled movement.

        # Standard death animation handling (if not petrified, etc.)
        if self.is_dead and not self.death_animation_finished:
            # This is for normal deaths, not petrified/smashed which are handled above.
            # Player.animate() should set self.death_animation_finished when done.
            if self.death_animation_finished: # Check again in case animate() just finished it
                 self.kill() # Mark as fully gone for game loop
            return True # Death animation is playing, overrides normal AI/physics

        return False # No status effect fully overrode the update that wasn't handled by an early return.

    def draw_pyside(self, painter: QPainter, camera: 'CameraClass_TYPE'):
        # Drawing logic remains the same, uses self.image and self.rect
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return

        should_draw = self.alive() or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      self.is_petrified # Petrified players (as stone) are drawn

        if not should_draw:
            return

        collision_rect_on_screen: QRectF = camera.apply(self.rect) # Camera must have 'apply' method
        
        # Basic culling: only draw if the collision rect (which is smaller) might be visible
        if not painter.window().intersects(collision_rect_on_screen.toRect()):
            return

        # Visual sprite might be larger than collision rect, calculate its screen position
        visual_sprite_width = float(self.image.width())
        visual_sprite_height = float(self.image.height())
        
        # Anchor visual sprite's bottom-center to collision_rect's bottom-center for visual consistency
        draw_x_visual = collision_rect_on_screen.center().x() - (visual_sprite_width / 2.0)
        draw_y_visual = collision_rect_on_screen.bottom() - visual_sprite_height # Align bottom edges
        
        draw_pos_visual = QPointF(draw_x_visual, draw_y_visual)
        painter.drawPixmap(draw_pos_visual, self.image)


    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any], platforms_list_ref: List[Any]):
        """Stores references to game element lists needed for projectile creation."""
        if self.game_elements_ref_for_projectiles is None:
            self.game_elements_ref_for_projectiles = {}
        self.game_elements_ref_for_projectiles["projectiles_list"] = projectile_list
        self.game_elements_ref_for_projectiles["all_renderable_objects"] = all_elements_list
        self.game_elements_ref_for_projectiles["platforms_list"] = platforms_list_ref

    # Network Data Handling (Delegated)
    def get_network_data(self) -> Dict[str, Any]: return get_player_network_data(self)
    def set_network_data(self, network_data: Dict[str, Any]): set_player_network_data(self, network_data)
    def handle_network_input(self, received_input_data_dict: Dict[str, Any]): handle_player_network_input(self, received_input_data_dict)

# Note: player_status_effects.py file might become largely obsolete if all its logic
# is now contained within Player.update_status_effects or Player.apply_..._effect methods.
# For now, I've moved update_player_status_effects into the Player class.
# apply_aflame_effect and apply_freeze_effect remain standalone in player_status_effects.py
# but are now called directly by Player instance (self.apply_aflame_effect()) after being moved.
# Let's ensure apply_aflame_effect etc. are indeed methods of Player:

    # --- Status Effect Application Methods (now part of Player class) ---
    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_aflame_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: apply_aflame_effect blocked by existing conflicting state.")
            return
        
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_aflame_success_{self.player_id}"):
            debug(f"Player {self.player_id} Log: Applying aflame effect.")
        
        # The set_state call below (which goes to player_state_handler)
        # is now responsible for setting self.overall_fire_effect_start_time if it's a new fire sequence.
        self.set_state('aflame_crouch' if self.is_crouching else 'aflame', get_current_ticks_monotonic())
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_freeze_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: apply_freeze_effect blocked by existing conflicting state.")
            return
        
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_freeze_success_{self.player_id}"):
            debug(f"Player {self.player_id} Log: Applying freeze effect.")
        
        # frozen_effect_timer will be set by set_player_state
        self.set_state('frozen', get_current_ticks_monotonic())
        self.is_attacking = False; self.attack_type = 0
        if hasattr(self.vel, 'setX') and hasattr(self.vel, 'setY'):
            self.vel.setX(0); self.vel.setY(0)
        if hasattr(self.acc, 'setX'): self.acc.setX(0)

    def petrify(self): # Assumes game_elements is accessible if needed for statue creation
        if self.is_petrified or (self.is_dead and not self.is_petrified):
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"petrify_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: petrify called but already petrified or truly dead. Ignoring.")
            return
        
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"petrify_success_{self.player_id}"):
            debug(f"Player {self.player_id}: Petrifying.")
        
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        
        # Force clear fire states before petrifying
        self.is_aflame = False
        self.is_deflaming = False
        self.overall_fire_effect_start_time = 0

        self.set_state('petrified', get_current_ticks_monotonic()) # This sets is_petrified, is_dead, etc.

        # Note: Statue creation logic from player_status_effects.petrify_player
        # would need to be replicated here or called if this player instance
        # is to be replaced by a Statue object in game_elements.
        # For simplicity, this method now just sets the player's state to petrified.
        # The game loop or a higher-level manager would handle replacing player with Statue.
        # However, if petrify_player from player_status_effects.py is still called,
        # this internal Player.petrify() method might become redundant or just for flag setting.
        # For now, let's assume this method is the primary way petrification state is set on the Player object.

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"smash_petrify_success_{self.player_id}"):
                debug(f"Player {self.player_id}: Smashing petrification.")
            self.set_state('smashed', get_current_ticks_monotonic()) # Sets is_stone_smashed, is_dead, timers