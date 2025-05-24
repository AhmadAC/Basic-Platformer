# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes and delegating state,
animation, physics, collisions, input, combat, network handling, and status effects
to respective handler modules. Refactored for PySide6.
"""
# version 2.1.9 (Integrated zapped effect and full status effect handling)

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
    from logger import info, debug, warning, error, critical, log_player_physics
    from player_state_handler import set_player_state
    from player_animation_handler import update_player_animation
    from player_movement_physics import update_player_core_logic
    from player_collision_handler import (
        check_player_platform_collisions, check_player_ladder_collisions,
        check_player_character_collisions, check_player_hazard_collisions
    )
    # player_input_handler.process_player_input_logic is usually called by app_core/game_modes
    # and its results (intent flags, discrete events) are used to call Player methods.
    # For clarity, we can assume input flags like is_trying_to_move_left are set before Player.update()
    from player_combat_handler import (
        check_player_attack_collisions, player_take_damage,
        player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input # If P2's input directly modifies P2 instance server-side
    )
    from player_status_effects import update_player_status_effects # Centralized status update logic
    from projectiles import ( # For type hinting and direct instantiation
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
except ImportError as e:
    print(f"CRITICAL PLAYER.PY IMPORT ERROR: {e}. Some functionalities might be broken.")
    # Define dummy functions if logger or critical handlers fail, to prevent NameErrors
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")
    def log_player_physics(player, tag, extra_info=""): pass
    if 'set_player_state' not in globals():
        def set_player_state(player, new_state):
            if hasattr(player, 'state'): player.state = new_state
            warning("Fallback set_player_state used in player.py.")
    # Define dummy projectile classes if needed
    class Fireball: pass; 
    class PoisonShot: pass; 
    class BoltProjectile: pass;
    class BloodShot: pass; 
    class IceShard: pass; 
    class ShadowProjectile: pass; 
    class GreyProjectile: pass


if TYPE_CHECKING:
    from camera import Camera as CameraClass_TYPE

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
        self.control_scheme: Optional[str] = None # Set by game_setup
        self.joystick_id_idx: Optional[int] = None # Pygame index for assigned joystick
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None # Set by game_setup

        self.initial_spawn_pos = QPointF(float(start_x), float(start_y))
        self.pos = QPointF(self.initial_spawn_pos) # Current position (midbottom)

        # Determine asset folder based on player_id
        if self.player_id == 1: asset_folder = 'characters/player1'
        elif self.player_id == 2: asset_folder = 'characters/player2'
        elif self.player_id == 3: asset_folder = 'characters/player3'
        elif self.player_id == 4: asset_folder = 'characters/player4'
        else: asset_folder = 'characters/player1' # Fallback

        self.animations: Optional[Dict[str, List[QPixmap]]] = None
        try:
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        except Exception as e_anim_load:
            critical(f"Player {self.player_id}: Exception during load_all_player_animations from '{asset_folder}': {e_anim_load}", exc_info=True)
            self._valid_init = False
        if self.animations is None:
            critical(f"Player Init Error (ID: {self.player_id}): Failed loading animations from '{asset_folder}'. Player invalid.")
            self._valid_init = False

        # Collision dimensions (updated after animations load)
        self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6)
        self.base_crouch_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.7)
        self.standing_collision_height: float = 60.0
        self.crouching_collision_height: float = 30.0

        # Core attributes
        self.image: Optional[QPixmap] = None
        self.rect = QRectF() # Collision rectangle
        self.vel = QPointF(0.0, 0.0) # Velocity
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7))) # Acceleration
        self.state: str = 'idle'
        self.current_frame: int = 0
        self.last_anim_update: int = 0 # Timestamp of last animation frame change
        self._last_facing_right: bool = True # For detecting facing change for animation
        self.facing_right: bool = True
        self.on_ground: bool = False
        self.on_ladder: bool = False
        self.can_grab_ladder: bool = False
        self.touching_wall: int = 0 # -1 for left, 1 for right, 0 for none
        self.can_wall_jump: bool = False
        self.is_crouching: bool = False

        # Action states and timers
        self.is_dashing: bool = False; self.dash_timer: int = 0
        self.dash_duration: int = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling: bool = False; self.roll_timer: int = 0
        self.roll_duration: int = int(getattr(C, 'PLAYER_ROLL_DURATION', 300))
        self.is_sliding: bool = False; self.slide_timer: int = 0
        self.slide_duration: int = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = int(getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300))
        self.attack_type: int = 0 # 1 for primary, 2 for secondary, 3 for combo, 4 for crouch
        self.can_combo: bool = False # Flag if player is in a window to perform a combo
        self.combo_window: int = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))

        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600)) # Invulnerability after hit

        self.is_dead: bool = False
        self.death_animation_finished: bool = False
        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'PLAYER_MAX_HEALTH', 100)))
        self.current_health: int = self.max_health
        self._alive: bool = True # Primary flag for "active in game"

        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0) # Default size, adjust as needed
        self.standard_height: float = 60.0 # Default if animations fail

        # Input intent flags (set by input processing before Player.update)
        self.is_trying_to_move_left: bool = False
        self.is_trying_to_move_right: bool = False
        self.is_holding_climb_ability_key: bool = False # For ladders or future climbing
        self.is_holding_crouch_ability_key: bool = False

        # Projectile cooldowns (initialized to allow immediate firing)
        current_time_for_init_cooldown = get_current_ticks_monotonic()
        self.fireball_cooldown_timer: int = current_time_for_init_cooldown - C.FIREBALL_COOLDOWN
        self.poison_cooldown_timer: int = current_time_for_init_cooldown - C.POISON_COOLDOWN
        self.bolt_cooldown_timer: int = current_time_for_init_cooldown - C.BOLT_COOLDOWN
        self.blood_cooldown_timer: int = current_time_for_init_cooldown - C.BLOOD_COOLDOWN
        self.ice_cooldown_timer: int = current_time_for_init_cooldown - C.ICE_COOLDOWN
        self.shadow_cooldown_timer: int = current_time_for_init_cooldown - C.SHADOW_PROJECTILE_COOLDOWN
        self.grey_cooldown_timer: int = current_time_for_init_cooldown - C.GREY_PROJECTILE_COOLDOWN
        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aim direction

        # Status effects
        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.is_frozen: bool = False; self.is_defrosting: bool = False
        self.frozen_effect_timer: int = 0
        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = True
        self.was_crouching_when_petrified: bool = False
        self.is_zapped: bool = False # New zapped state
        self.zapped_timer_start: int = 0
        self.zapped_damage_last_tick: int = 0

        self.state_timer: int = 0 # Time when current state began
        self._prev_discrete_axis_hat_state: Dict[Tuple[str, int, Tuple[int, int]], bool] = {} # For joystick event priming
        self._first_joystick_input_poll_done: bool = False # Flag for joystick input priming

        if self._valid_init and self.animations:
            try:
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                    self.standing_collision_height = float(idle_frames[0].height() * 0.85)
                    self.base_standing_collision_width = float(idle_frames[0].width() * 0.5)
                else: # Fallback if 'idle' frames are missing/invalid
                    self.standing_collision_height = float(getattr(C, 'TILE_SIZE', 40) * 1.5)
                    self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6)

                crouch_frames = self.animations.get('crouch')
                if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                    self.crouching_collision_height = float(crouch_frames[0].height() * 0.9)
                    self.base_crouch_collision_width = float(crouch_frames[0].width() * 0.7)
                else: # Fallback for crouch dimensions
                    self.crouching_collision_height = self.standing_collision_height * 0.55
                    self.base_crouch_collision_width = self.base_standing_collision_width * 1.1

                # Validate calculated collision heights
                if not (1e-6 < self.standing_collision_height < 1000 and \
                        1e-6 < self.crouching_collision_height < self.standing_collision_height):
                    critical(f"Player {self.player_id}: Invalid collision heights. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                    self._valid_init = False
                self.standard_height = self.standing_collision_height # Used as a general reference

                initial_idle_frames_for_image = self.animations.get('idle')
                if initial_idle_frames_for_image and initial_idle_frames_for_image[0] and not initial_idle_frames_for_image[0].isNull():
                    self.image = initial_idle_frames_for_image[0]
                else: # Critical if no idle image
                    self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'RED', (255,0,0))), "NoIdle")
                    self._valid_init = False
                    critical(f"Player {self.player_id}: CRITICAL - 'idle' animation missing or invalid. Player initialization failed.")

            except Exception as e_col_h:
                error(f"Player {self.player_id} Exception setting collision heights or initial image: {e_col_h}", exc_info=True)
                self._valid_init = False
        elif not self._valid_init: # If animations failed to load entirely
            self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "AnimFail")

        self._update_rect_from_image_and_pos() # Set initial rect based on image and collision height
        self._assign_projectile_keys() # Set projectile key strings based on player ID
        self._init_stone_assets()      # Load common stone/smashed assets

        if not self._valid_init:
            self.is_dead = True; self._alive = False; self.current_health = 0
            warning(f"Player {self.player_id}: Initialization failed or animations are missing critical frames.")
        else:
            self.last_anim_update = get_current_ticks_monotonic() # Set after successful init
            debug(f"Player {self.player_id} initialized. Valid: {self._valid_init}. "
                  f"CollisionRect: W{self.rect.width():.1f} H{self.rect.height():.1f} "
                  f"at ({self.rect.x():.1f},{self.rect.y():.1f})")

    def reset_for_new_game_or_round(self):
        """Resets flags related to input priming and cooldowns for a new game/map session."""
        debug(f"Player {self.player_id}: Resetting input priming and cooldowns for new game/round.")
        self._first_joystick_input_poll_done = False
        self._prev_discrete_axis_hat_state.clear()

        current_time_reset = get_current_ticks_monotonic()
        # Reset cooldowns to allow immediate action.
        self.fireball_cooldown_timer = current_time_reset - C.FIREBALL_COOLDOWN
        self.poison_cooldown_timer = current_time_reset - C.POISON_COOLDOWN
        self.bolt_cooldown_timer = current_time_reset - C.BOLT_COOLDOWN
        self.blood_cooldown_timer = current_time_reset - C.BLOOD_COOLDOWN
        self.ice_cooldown_timer = current_time_reset - C.ICE_COOLDOWN
        self.shadow_cooldown_timer = current_time_reset - C.SHADOW_PROJECTILE_COOLDOWN
        self.grey_cooldown_timer = current_time_reset - C.GREY_PROJECTILE_COOLDOWN
        debug(f"Player {self.player_id}: Projectile cooldowns reset for immediate use.")

    def _init_stone_assets(self):
        """Loads common stone/smashed assets, potentially falling back to player-specific if available."""
        qcolor_gray = QColor(*getattr(C,'GRAY', (128,128,128)))
        qcolor_dark_gray = QColor(*getattr(C,'DARK_GRAY', (50,50,50)))

        def load_or_placeholder(common_path_suffix: str, player_anim_key: Optional[str],
                                default_placeholder_color: QColor, default_placeholder_text: str,
                                is_list: bool = False) -> Any: # Returns QPixmap or List[QPixmap]
            # 1. Try common path
            full_common_path = resource_path(os.path.join(C.STONE_ASSET_FOLDER, common_path_suffix))
            frames = load_gif_frames(full_common_path)
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]

            # 2. Try player-specific animation as fallback
            if player_anim_key and self.animations:
                player_specific_frames = self.animations.get(player_anim_key, [])
                if player_specific_frames and not self._is_placeholder_qpixmap(player_specific_frames[0]):
                    debug(f"Player {self.player_id} StoneAsset: Using player's own '{player_anim_key}' anim for stone effect '{common_path_suffix}'.")
                    return player_specific_frames if is_list else player_specific_frames[0]

            # 3. Use placeholder
            warning(f"Player {self.player_id} StoneAsset: Failed to load '{common_path_suffix}' (and player-specific '{player_anim_key}'). Using placeholder.")
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        self.stone_image_frame_original = load_or_placeholder("__Stone.png", "petrified", qcolor_gray, "StoneP")
        self.stone_image_frame = self.stone_image_frame_original.copy()

        self.stone_smashed_frames_original = load_or_placeholder("__StoneSmashed.gif", "smashed", qcolor_dark_gray, "SmashP", is_list=True)
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        self.stone_crouch_image_frame_original = load_or_placeholder("__StoneCrouch.png", None, qcolor_gray, "SCrouchP") # No direct "petrified_crouch" anim key
        if self._is_placeholder_qpixmap(self.stone_crouch_image_frame_original) and not self._is_placeholder_qpixmap(self.stone_image_frame_original):
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy() # Fallback to standing stone if crouch stone fails
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()

        self.stone_crouch_smashed_frames_original = load_or_placeholder("__StoneCrouchSmashed.gif", None, qcolor_dark_gray, "SCSmashP", is_list=True)
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]) and \
           not (len(self.stone_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_smashed_frames_original[0])):
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original] # Fallback to standing smash if crouch smash fails
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]


    def _assign_projectile_keys(self):
        # These are string representations used by input handler to know which constant to check
        # Actual key codes/bindings are in config.py and processed by input_handler
        if self.player_id == 1: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P1_FIREBALL_KEY, C.P1_POISON_KEY, C.P1_BOLT_KEY, C.P1_BLOOD_KEY, C.P1_ICE_KEY, C.P1_SHADOW_PROJECTILE_KEY, C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P2_FIREBALL_KEY, C.P2_POISON_KEY, C.P2_BOLT_KEY, C.P2_BLOOD_KEY, C.P2_ICE_KEY, C.P2_SHADOW_PROJECTILE_KEY, C.P2_GREY_PROJECTILE_KEY
        elif self.player_id == 3: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P3_FIREBALL_KEY, C.P3_POISON_KEY, C.P3_BOLT_KEY, C.P3_BLOOD_KEY, C.P3_ICE_KEY, C.P3_SHADOW_PROJECTILE_KEY, C.P3_GREY_PROJECTILE_KEY
        elif self.player_id == 4: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P4_FIREBALL_KEY, C.P4_POISON_KEY, C.P4_BOLT_KEY, C.P4_BLOOD_KEY, C.P4_ICE_KEY, C.P4_SHADOW_PROJECTILE_KEY, C.P4_GREY_PROJECTILE_KEY

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        h = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        if h <= 1e-6 : h = self.standard_height # Use standard_height if current collision height is bad
        if h <= 1e-6 : h = 60.0 # Absolute fallback
        w = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width
        if w <= 1e-6 : w = h * 0.5 # Approximate width
        pixmap = QPixmap(max(10, int(w)), max(10, int(h))); pixmap.fill(q_color)
        painter = QPainter(pixmap); painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0)))); painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try: font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font); painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: error(f"PLAYER PlaceholderFontError (P{self.player_id}): {e}", exc_info=True)
        painter.end(); return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        # Simplified check, assumes placeholder might be small and of specific colors
        if pixmap.size() in [QSize(30,40), QSize(30,60), QSize(10,10)]: # Common placeholder sizes
            qimage = pixmap.toImage()
            if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_magenta = QColor(*getattr(C, 'MAGENTA', (255,0,255))) # Another common error color
                if color_at_origin in [qcolor_red, qcolor_blue, qcolor_magenta]:
                    return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        """Updates self.rect (collision rect) based on self.pos (midbottom) and current collision height/width."""
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF): # Ensure target_pos is valid
            target_pos = self.pos if isinstance(self.pos, QPointF) else QPointF(self.initial_spawn_pos)

        # Determine collision dimensions based on current state (crouching or standing)
        current_collision_height = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        current_collision_width = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width

        # Fallbacks if calculated dimensions are invalid
        if current_collision_height <= 1e-6: current_collision_height = self.standard_height
        if current_collision_width <= 1e-6: current_collision_width = current_collision_height * 0.5 # Approx aspect ratio

        rect_x = target_pos.x() - current_collision_width / 2.0
        rect_y = target_pos.y() - current_collision_height # Player pos is midbottom

        if not hasattr(self, 'rect') or self.rect is None: # Should have been initialized
            self.rect = QRectF(rect_x, rect_y, current_collision_width, current_collision_height)
        else:
            self.rect.setRect(rect_x, rect_y, current_collision_width, current_collision_height)

    def alive(self) -> bool: return self._alive
    def kill(self):
        if self._alive: debug(f"Player {self.player_id} kill() called.")
        self._alive = False # Primary flag to stop updates and rendering

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True # Can "stand" if not crouching or invalid
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True # No height change

        current_crouch_rect = self.rect # Current collision rect while crouching
        current_feet_y = current_crouch_rect.bottom()
        current_center_x = current_crouch_rect.center().x()

        # Potential rect if standing
        potential_standing_width = self.base_standing_collision_width
        potential_standing_height = self.standing_collision_height

        potential_standing_rect_left = current_center_x - (potential_standing_width / 2.0)
        potential_standing_rect_top = current_feet_y - potential_standing_height # Anchored by feet
        potential_standing_rect = QRectF(potential_standing_rect_left, potential_standing_rect_top,
                                         potential_standing_width, potential_standing_height)

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF):
                if potential_standing_rect.intersects(platform_obj.rect):
                    # Check if the intersection is meaningful (i.e., platform is above the player's crouched head)
                    if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                       platform_obj.rect.top() < current_crouch_rect.top(): # Platform is between potential standing top and current crouch top
                        debug(f"Player {self.player_id} cannot stand: Blocked by platform {platform_obj.rect} "
                              f"(Pot. Stand Rect: {potential_standing_rect}, Crouch Top: {current_crouch_rect.top()})")
                        return False
        debug(f"Player {self.player_id} can stand up. (Pot. Stand Rect: {potential_standing_rect})")
        return True

    # --- Delegated Methods ---
    def set_state(self, new_state: str): set_player_state(self, new_state)
    def animate(self): update_player_animation(self)
    # process_input is called externally by app_core/game_modes

    def check_attack_collisions(self, list_of_targets: List[Any]): check_player_attack_collisions(self, list_of_targets)
    def take_damage(self, damage_amount_taken: int): player_take_damage(self, damage_amount_taken)
    def self_inflict_damage(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)

    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]) -> bool: return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting or self.is_zapped: return
        debug(f"Player {self.player_id} Log: Applying aflame effect.")
        self.is_aflame = True; self.is_deflaming = False
        self.aflame_timer_start = get_current_ticks_monotonic(); self.aflame_damage_last_tick = self.aflame_timer_start
        set_player_state(self, 'aflame_crouch' if self.is_crouching else 'aflame'); self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming or self.is_zapped: return
        debug(f"Player {self.player_id} Log: Applying freeze effect.")
        set_player_state(self, 'frozen'); self.is_attacking = False; self.attack_type = 0; self.vel = QPointF(0,0); self.acc.setX(0)

    def apply_zapped_effect(self):
        if self.is_zapped or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting or self.is_aflame or self.is_deflaming:
            debug(f"Player {self.player_id} Log: Apply zapped effect called but already in conflicting state. Ignoring.")
            return
        debug(f"Player {self.player_id} Log: Applying ZAPPED effect.")
        # is_zapped and timers will be set by set_player_state when it transitions to 'zapped'
        set_player_state(self, 'zapped')
        self.is_attacking = False; self.attack_type = 0 # Ensure attack stops

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified): return
        debug(f"Player {self.player_id}: Petrifying.");
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        self.is_petrified = True; self.is_stone_smashed = False
        self.is_dead = True; self.current_health = 0 # Petrified implies "defeated"
        self.vel = QPointF(0,0); self.acc = QPointF(0,0) # Stop all movement
        self.is_attacking = False; self.is_dashing = False; self.is_rolling = False
        self.is_sliding = False; self.on_ladder = False; self.is_taking_hit = False
        self.is_aflame = False; self.is_deflaming = False
        self.is_frozen = False; self.is_defrosting = False
        self.is_zapped = False # Petrify overrides zapped
        self.death_animation_finished = True # No separate death anim for petrified state itself
        set_player_state(self, 'petrified')

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            debug(f"Player {self.player_id}: Smashing petrification.");
            self.is_stone_smashed = True
            self.stone_smashed_timer_start = get_current_ticks_monotonic()
            self.death_animation_finished = False # Smashed animation needs to play
            set_player_state(self, 'smashed')

    # --- Projectile Firing ---
    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any], platforms_list_ref: List[Any]):
        if self.game_elements_ref_for_projectiles is None: self.game_elements_ref_for_projectiles = {}
        self.game_elements_ref_for_projectiles["projectiles_list"] = projectile_list
        self.game_elements_ref_for_projectiles["all_renderable_objects"] = all_elements_list
        self.game_elements_ref_for_projectiles["platforms_list"] = platforms_list_ref

    def _generic_fire_projectile(self, projectile_class: type, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        # Check if player can fire (not dead, petrified, frozen, zapped, etc.)
        if not self._valid_init or self.is_dead or not self._alive or \
           self.is_petrified or self.is_frozen or self.is_defrosting or self.is_zapped:
            return

        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_log(f"proj_fire_no_game_elements_{self.player_id}"):
                warning(f"Player {self.player_id}: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return

        projectiles_list_ref = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref = self.game_elements_ref_for_projectiles.get("all_renderable_objects")

        if projectiles_list_ref is None or all_renderables_ref is None:
            if Player.print_limiter.can_log(f"proj_fire_list_missing_{self.player_id}"):
                warning(f"Player {self.player_id}: Projectile or renderable list missing. Cannot fire {projectile_config_name}.")
            return

        current_time_ms = get_current_ticks_monotonic()
        last_fire_time = getattr(self, cooldown_attr_name, 0)

        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)

            if self.rect.isNull(): self._update_rect_from_image_and_pos()
            if self.rect.isNull(): error(f"Player {self.player_id}: Rect is null, cannot fire."); return

            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6): # Fallback aim direction
                aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0)

            # Offset projectile spawn slightly from player center based on aim direction
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0))
            # Effective radius of player + projectile to avoid immediate self-collision
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0 # Small adjustment
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): # If aiming more vertically
                 offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0

            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length

            spawn_x += norm_x * offset_dist
            spawn_y += norm_y * offset_dist

            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles # Pass reference

            projectiles_list_ref.append(new_projectile)
            all_renderables_ref.append(new_projectile)

            if Player.print_limiter.can_log(f"fired_{projectile_config_name}_{self.player_id}"):
                debug(f"Player {self.player_id} fired {projectile_config_name} at ({spawn_x:.1f},{spawn_y:.1f}) dir ({aim_dir.x():.1f},{aim_dir.y():.1f})")

            # Special effect for blood magic
            if projectile_config_name == 'blood' and self.current_health > 0:
                self.current_health -= self.current_health * 0.05 # Example: 5% health cost
                if self.current_health <= 0 and not self.is_dead:
                    set_player_state(self, 'death')

    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')

    # --- Update and Draw ---
    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
               hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):

        if not self._valid_init or not self._alive: # Primary check if player object itself is active
            return

        current_time_ms = get_current_ticks_monotonic()
        log_player_physics(self, "PLAYER_UPDATE_START")

        # 1. Update Status Effects (petrified, frozen, aflame, zapped, etc.)
        # This function returns True if a status effect overrides normal updates.
        status_overrode_update = update_player_status_effects(self, current_time_ms)

        if status_overrode_update:
            # If a status effect like frozen, petrified (not smashed), or zapped is active,
            # it often dictates immobilization or specific behaviors.
            # The physics might still apply gravity if petrified/zapped mid-air.
            # The update_player_core_logic might still be called for these minimal physics.
            # If petrified and not on ground, core logic will apply gravity.
            if self.is_petrified and not self.is_stone_smashed and not self.on_ground:
                 update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)
            elif self.is_zapped and not self.on_ground: # Zapped and falling
                 update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)
            
            self.animate() # Animation still runs for visual status
            log_player_physics(self, "STATUS_OVERRIDE_END", f"EffectState: {self.state}")
            return # Skip normal input processing and physics application for this frame

        # 2. Handle "Normal" Death (if not petrified/smashed)
        if self.is_dead: # Normal death, not petrified
            if not self.death_animation_finished: # Death animation playing
                if not self.on_ground: # Apply gravity to dead body
                    # Simplified gravity for dead body (already handled more comprehensively in core_logic if needed)
                    self.vel.setY(self.vel.y() + self.acc.y())
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                    self.pos.setY(self.pos.y() + self.vel.y() * dt_sec * C.FPS)
                    self._update_rect_from_image_and_pos()
                    check_player_platform_collisions(self, 'y', platforms_list) # Minimal collision
                    self.pos = QPointF(self.rect.center().x(), self.rect.bottom())
                self.animate()
            else: # Death animation finished
                self.kill() # Set self._alive to False
            log_player_physics(self, "UPDATE_END", "Player is normally dead")
            return

        # 3. Core Logic (Movement Physics, Collisions, State Timers)
        # Input processing (setting intent flags) is assumed to happen *before* this Player.update()
        update_player_core_logic(self, dt_sec, platforms_list, ladders_list,
                                 hazards_list, other_players_list, enemies_list)

        # 4. Animation
        self.animate()

        # 5. Post-update checks (e.g., if is_dead and death animation finished after core logic)
        if self.is_dead and self.death_animation_finished and not self.is_petrified: # Don't kill if petrified unless smashed
            self.kill() # Sets self._alive = False

        log_player_physics(self, "PLAYER_UPDATE_END")


    def draw_pyside(self, painter: QPainter, camera: 'CameraClass_TYPE'):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            if Player.print_limiter.can_log(f"draw_invalid_{self.player_id}"):
                warning(f"Player {self.player_id}: Draw called but invalid state or image. Valid: {self._valid_init}, ImageNull: {self.image.isNull() if self.image else 'NoImage'}, RectValid: {self.rect.isValid()}")
            return

        # Determine if the player should be drawn
        should_draw_this_frame = self._alive or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      (self.is_petrified) # Always draw petrified/smashed until their own duration ends

        if not should_draw_this_frame:
            return

        # Calculate screen position for the visual sprite.
        # The player's self.rect is the collision rect. The visual sprite might be larger.
        # For simplicity, we'll draw the current self.image centered on the collision rect's center,
        # and anchored by its bottom matching the collision rect's bottom.

        collision_rect_on_screen: QRectF = camera.apply(self.rect)

        # Basic viewport culling
        if not painter.window().intersects(collision_rect_on_screen.toRect()):
            # If visual sprite is much larger than collision, this culling might be too aggressive.
            # For now, assume collision rect is a good proxy for culling.
            return

        visual_sprite_width = float(self.image.width())
        visual_sprite_height = float(self.image.height())

        # Anchor point for drawing: mid-bottom of the collision rect.
        # The visual sprite will be drawn such that its bottom edge aligns with this,
        # and it's horizontally centered.
        draw_x_visual = collision_rect_on_screen.center().x() - (visual_sprite_width / 2.0)
        draw_y_visual = collision_rect_on_screen.bottom() - visual_sprite_height # Align bottom of visual with bottom of collision

        draw_pos_visual = QPointF(draw_x_visual, draw_y_visual)

        current_opacity = 1.0
        if self.state == 'deflame' or self.state == 'deflame_crouch' or \
           self.state == 'defrost' or self.is_sliding or \
           (self.is_stone_smashed and get_current_ticks_monotonic() - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS * 0.6):
            # Example fade out for these states
            elapsed_in_state = get_current_ticks_monotonic() - self.state_timer
            fade_total_duration = 0
            if self.state == 'deflame' or self.state == 'deflame_crouch': fade_total_duration = C.PLAYER_DEFLAME_DURATION_MS
            elif self.state == 'defrost': fade_total_duration = C.PLAYER_DEFROST_DURATION_MS
            elif self.is_sliding : fade_total_duration = self.slide_duration
            elif self.is_stone_smashed: fade_total_duration = C.STONE_SMASHED_DURATION_MS * 0.4 # Fade over last 40%

            if fade_total_duration > 0:
                fade_start_time = self.state_timer if not self.is_stone_smashed else self.stone_smashed_timer_start + C.STONE_SMASHED_DURATION_MS * 0.6
                elapsed_fade = get_current_ticks_monotonic() - fade_start_time
                current_opacity = max(0.0, 1.0 - (elapsed_fade / fade_total_duration))

        if current_opacity < 1.0:
            painter.setOpacity(current_opacity)
            painter.drawPixmap(draw_pos_visual, self.image)
            painter.setOpacity(1.0) # Reset opacity
        else:
            painter.drawPixmap(draw_pos_visual, self.image)


    # --- Network Methods ---
    def get_network_data(self) -> Dict[str, Any]: return get_player_network_data(self)
    def set_network_data(self, network_data: Dict[str, Any]): set_player_network_data(self, network_data)
    def handle_network_input(self, received_input_data_dict: Dict[str, Any]):
        # This is typically called on the server for P2, or on client for P1 if server sends P1 input
        # It should update intent flags and trigger actions based on received events.
        # The actual 'process_player_input_logic' is more for local input.
        # This method directly applies the *results* of remote input processing.
        handle_player_network_input(self, received_input_data_dict)