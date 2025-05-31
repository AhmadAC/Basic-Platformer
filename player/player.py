# player/player.py
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
MODIFIED: Asset folder paths updated for player animations and common status assets
          to reflect the new `assets/` top-level structure.
MODIFIED: `_init_common_status_assets` now correctly uses the updated `player_asset_folder`
          for potentially player-specific status effect animations (like `__Zapped.gif`).
MODIFIED: Corrected logger import path from `main_game.logger`.
"""
# version 2.1.17 (Corrected logger import path)

import os
import sys # Added sys for path manipulation if run standalone
import math
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage, QKeyEvent
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# --- Project Root Setup for Standalone Testing/Linting ---
# This helps if player.py is run/linted directly.
# It assumes player.py is in Project_Root/player/
_PLAYER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_PLAYER_PY = os.path.dirname(_PLAYER_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_PLAYER_PY not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_PLAYER_PY)
# --- End Project Root Setup ---

# Game-specific imports
from main_game.assets import load_all_player_animations, load_gif_frames, resource_path
from main_game.utils import PrintLimiter
import main_game.constants as C
import main_game.config as game_config

# Handler modules
try:
    # Assuming these handlers are in the same 'player' package or accessible via sys.path
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
    from player_status_effects import petrify_player, update_player_status_effects

    from player.projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    # --- UPDATED LOGGER IMPORT ---
    from main_game.logger import info, debug, warning, error, critical
    # --- END UPDATED LOGGER IMPORT ---
except ImportError as e:
    print(f"CRITICAL PLAYER.PY IMPORT ERROR: {e}. Some functionalities might be broken.")
    # Define fallback loggers if logger fails
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}") # Line 58 from original error context
    # Define fallback for set_player_state if player_state_handler fails
    if 'set_player_state' not in globals():
        def set_player_state(player, new_state, current_game_time_ms_param=None): # Add param
            if hasattr(player, 'state'): player.state = new_state
            warning("Fallback set_player_state used.")
    if 'petrify_player' not in globals():
        def petrify_player(player, game_elements): # type: ignore
            warning("Fallback petrify_player used.")
            if hasattr(player, 'facing_right'): player.facing_at_petrification = player.facing_right
            if hasattr(player, 'is_crouching'): player.was_crouching_when_petrified = player.is_crouching
            player.is_aflame = False; player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
            player.is_frozen = False; player.is_defrosting = False
            player.is_petrified = True; player.is_stone_smashed = False
            player.is_dead = True; player.current_health = 0
            if hasattr(player, 'set_state'): player.set_state('petrified', get_current_ticks_monotonic())
            if hasattr(player, 'kill'): player.kill()
    if 'update_player_status_effects' not in globals():
        def update_player_status_effects(player, current_time_ms): # type: ignore
            warning("Fallback update_player_status_effects used.")
            return False


if TYPE_CHECKING:
    from main_game.app_core import MainWindow
    from main_game.camera import Camera as CameraClass_TYPE

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

        # Player-specific asset folder, relative to project root
        player_asset_folder_relative_to_project_root = os.path.join('assets', 'playable_characters', f'player{self.player_id}')

        self.animations: Optional[Dict[str, List[QPixmap]]] = None
        try:
            self.animations = load_all_player_animations(relative_asset_folder=player_asset_folder_relative_to_project_root)
        except Exception as e_anim_load:
            critical(f"Player {self.player_id}: Exception during load_all_player_animations from '{player_asset_folder_relative_to_project_root}': {e_anim_load}", exc_info=True)
            self._valid_init = False
        if self.animations is None:
            critical(f"Player Init Error (ID: {self.player_id}): Failed loading animations from '{player_asset_folder_relative_to_project_root}'. Player invalid.")
            self._valid_init = False

        self.is_crouching: bool = False
        self.on_ground: bool = False
        self.on_ladder: bool = False
        self.can_grab_ladder: bool = False
        self.touching_wall: int = 0
        self.can_wall_jump: bool = False
        self.is_dead: bool = False
        self._alive: bool = True

        self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6)
        self.base_crouch_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.7)
        self.standing_collision_height: float = 60.0
        self.crouching_collision_height: float = 30.0
        self.standard_height: float = 60.0

        self.is_tipping: bool = False
        self.tipping_angle: float = 0.0
        self.tipping_direction: int = 0
        self.tipping_pivot_x_world: float = 0.0

        self.image: Optional[QPixmap] = None
        self.rect = QRectF()
        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.state: str = 'idle'
        self.current_frame: int = 0
        self.last_anim_update: int = 0
        self._last_facing_right: bool = True
        self.facing_right: bool = True

        self.is_dashing: bool = False; self.dash_timer: int = 0
        self.dash_duration: int = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling: bool = False; self.roll_timer: int = 0
        self.roll_duration: int = int(getattr(C, 'PLAYER_ROLL_DURATION', 300))
        self.is_sliding: bool = False; self.slide_timer: int = 0
        self.slide_duration: int = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = int(getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300))
        self.attack_type: int = 0
        self.can_combo: bool = False
        self.combo_window: int = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))
        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600))

        self.death_animation_finished: bool = False
        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'PLAYER_MAX_HEALTH', 100)))
        self.current_health: int = self.max_health

        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0)

        self.is_trying_to_move_left: bool = False
        self.is_trying_to_move_right: bool = False
        self.is_holding_climb_ability_key: bool = False
        self.is_holding_crouch_ability_key: bool = False

        current_time_for_init_cooldown = get_current_ticks_monotonic()
        self.fireball_cooldown_timer: int = current_time_for_init_cooldown - C.FIREBALL_COOLDOWN
        self.poison_cooldown_timer: int = current_time_for_init_cooldown - C.POISON_COOLDOWN
        self.bolt_cooldown_timer: int = current_time_for_init_cooldown - C.BOLT_COOLDOWN
        self.blood_cooldown_timer: int = current_time_for_init_cooldown - C.BLOOD_COOLDOWN
        self.ice_cooldown_timer: int = current_time_for_init_cooldown - C.ICE_COOLDOWN
        self.shadow_cooldown_timer: int = current_time_for_init_cooldown - C.SHADOW_PROJECTILE_COOLDOWN
        self.grey_cooldown_timer: int = current_time_for_init_cooldown - C.GREY_PROJECTILE_COOLDOWN
        self.fireball_last_input_dir = QPointF(1.0, 0.0)

        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.overall_fire_effect_start_time: int = 0

        self.is_frozen: bool = False; self.is_defrosting: bool = False
        self.frozen_effect_timer: int = 0

        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = True
        self.was_crouching_when_petrified: bool = False

        self.is_zapped: bool = False
        self.zapped_timer_start: int = 0
        self.zapped_damage_last_tick: int = 0
        self.zapped_gif_path: Optional[str] = None

        self.state_timer: int = 0
        self._prev_discrete_axis_hat_state: Dict[Tuple[str, int, Tuple[int, int]], bool] = {}
        self._first_joystick_input_poll_done: bool = False

        if self._valid_init and self.animations:
            try:
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                    self.standing_collision_height = float(idle_frames[0].height() * 0.85)
                    self.base_standing_collision_width = float(idle_frames[0].width() * 0.5)
                crouch_frames = self.animations.get('crouch')
                if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                    self.crouching_collision_height = float(crouch_frames[0].height() * 0.9)
                    self.base_crouch_collision_width = float(crouch_frames[0].width() * 0.7)

                if not (1e-6 < self.standing_collision_height < 1000 and \
                        1e-6 < self.crouching_collision_height < self.standing_collision_height + 1e-6) :
                    critical(f"Player {self.player_id}: Invalid collision heights. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                    self.standing_collision_height = float(getattr(C, 'TILE_SIZE', 40) * 1.5)
                    self.crouching_collision_height = self.standing_collision_height * 0.55
                    self.base_standing_collision_width = float(getattr(C, 'TILE_SIZE', 40) * 0.6)
                    self.base_crouch_collision_width = self.base_standing_collision_width * 1.1
                self.standard_height = self.standing_collision_height

                initial_idle_frames = self.animations.get('idle')
                if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
                    self.image = initial_idle_frames[0]
                else:
                    self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'RED', (255,0,0))), "NoIdle")
                    self._valid_init = False
            except Exception as e_col_h:
                error(f"Player {self.player_id} Exception setting collision heights: {e_col_h}", exc_info=True)
                self._valid_init = False
        elif not self._valid_init: # If animations failed to load
            self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "AnimFail")

        self._update_rect_from_image_and_pos()
        self._assign_projectile_keys()
        # Pass the player-specific asset folder (relative to project root)
        self._init_common_status_assets(player_asset_folder_relative_to_project_root)

        if not self._valid_init:
            self.is_dead = True; self._alive = False; self.current_health = 0
            warning(f"Player {self.player_id}: Initialization completed with _valid_init as False.")
        else:
            self.last_anim_update = get_current_ticks_monotonic()
            debug(f"Player {self.player_id} initialized. Valid: {self._valid_init}. CollisionRect: W{self.rect.width():.1f} H{self.rect.height():.1f}")


    def reset_for_new_game_or_round(self):
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

    def _init_common_status_assets(self, player_asset_folder_relative_to_project_root: str):
        # Paths for shared stone assets (relative to project root)
        stone_common_folder_relative_to_project_root = os.path.join('assets', 'shared', 'Stone')
        qcolor_gray = QColor(*getattr(C,'GRAY', (128,128,128)))
        qcolor_dark_gray = QColor(*getattr(C,'DARK_GRAY', (50,50,50)))

        def load_or_placeholder(path_suffix_from_base: str, default_placeholder_color: QColor,
                                default_placeholder_text: str,
                                is_list: bool = False,
                                base_asset_folder_relative_to_project: Optional[str] = None,
                                anim_key_check: Optional[str] = None) -> Any:
            # Check player's own animations first if anim_key_check is provided
            if anim_key_check and self.animations:
                player_specific_frames = self.animations.get(anim_key_check)
                if player_specific_frames and not self._is_placeholder_qpixmap(player_specific_frames[0]):
                    debug(f"Player {self.player_id} StatusAsset: Using player's own '{anim_key_check}' anim for '{path_suffix_from_base}'.")
                    return [f.copy() for f in player_specific_frames] if is_list else player_specific_frames[0].copy()

            effective_base_folder = base_asset_folder_relative_to_project if base_asset_folder_relative_to_project else stone_common_folder_relative_to_project_root
            # Construct the full path relative to the project root for resource_path
            full_path_relative_to_project = os.path.join(effective_base_folder, path_suffix_from_base)
            absolute_path = resource_path(full_path_relative_to_project)

            frames = load_gif_frames(absolute_path)
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]
            warning(f"Player {self.player_id} StatusAsset: Failed to load '{path_suffix_from_base}' (from '{effective_base_folder}', abs: '{absolute_path}'). Using placeholder.")
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        # Load stone assets (common folder)
        self.stone_image_frame_original = load_or_placeholder('__Stone.png', qcolor_gray, "StoneP", anim_key_check='petrified')
        self.stone_image_frame = self.stone_image_frame_original.copy()
        self.stone_smashed_frames_original = load_or_placeholder('__StoneSmashed.gif', qcolor_dark_gray, "SmashP", is_list=True, anim_key_check='smashed')
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]
        self.stone_crouch_image_frame_original = load_or_placeholder('__StoneCrouch.png', qcolor_gray, "SCrouchP", anim_key_check='petrified')
        if self._is_placeholder_qpixmap(self.stone_crouch_image_frame_original) and not self._is_placeholder_qpixmap(self.stone_image_frame_original):
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy()
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()
        self.stone_crouch_smashed_frames_original = load_or_placeholder('__StoneCrouchSmashed.gif', qcolor_dark_gray, "SCSmashP", is_list=True, anim_key_check='smashed')
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]) and \
           not (len(self.stone_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_smashed_frames_original[0])):
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original]
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]

        # Set Zapped GIF path using the player's specific asset folder (relative to project root)
        self.zapped_gif_path = os.path.join(player_asset_folder_relative_to_project_root, "__Zapped.gif")
        # The actual loading of zapped frames happens in `load_all_player_animations`.
        # This path is stored for reference or if specific individual loading logic was ever needed.
        if not (self.animations and self.animations.get('zapped') and not self._is_placeholder_qpixmap(self.animations['zapped'][0])):
             warning(f"Player {self.player_id}: Player-specific zapped animation not found or is placeholder at '{resource_path(self.zapped_gif_path)}'.")

    def _assign_projectile_keys(self):
        if self.player_id == 1: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P1_FIREBALL_KEY, C.P1_POISON_KEY, C.P1_BOLT_KEY, C.P1_BLOOD_KEY, C.P1_ICE_KEY, C.P1_SHADOW_PROJECTILE_KEY, C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P2_FIREBALL_KEY, C.P2_POISON_KEY, C.P2_BOLT_KEY, C.P2_BLOOD_KEY, C.P2_ICE_KEY, C.P2_SHADOW_PROJECTILE_KEY, C.P2_GREY_PROJECTILE_KEY
        elif self.player_id == 3: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P3_FIREBALL_KEY, C.P3_POISON_KEY, C.P3_BOLT_KEY, C.P3_BLOOD_KEY, C.P3_ICE_KEY, C.P3_SHADOW_PROJECTILE_KEY, C.P3_GREY_PROJECTILE_KEY
        elif self.player_id == 4: self.fireball_key_str, self.poison_key_str, self.bolt_key_str, self.blood_key_str, self.ice_key_str, self.shadow_key_str, self.grey_key_str = C.P4_FIREBALL_KEY, C.P4_POISON_KEY, C.P4_BOLT_KEY, C.P4_BLOOD_KEY, C.P4_ICE_KEY, C.P4_SHADOW_PROJECTILE_KEY, C.P4_GREY_PROJECTILE_KEY

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        h = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        if h <= 1e-6 : h = self.standard_height
        if h <= 1e-6 : h = 60.0
        w = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width
        if w <= 1e-6 : w = h * 0.5
        pixmap = QPixmap(max(10, int(w)), max(10, int(h)))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0))))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e:
            log_func = error if 'error' in globals() and callable(error) else lambda msg, *a, **kw: print(f"ERROR: {msg}", file=sys.stderr)
            log_func(f"PLAYER PlaceholderFontError (P{self.player_id}): {e}", exc_info=True)
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() in [QSize(30,40), QSize(30,60), QSize(10,10)]: # Common placeholder sizes
            qimage = pixmap.toImage()
            if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_magenta = QColor(*getattr(C, 'MAGENTA', (255,0,255)))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue or color_at_origin == qcolor_magenta:
                    return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF):
            target_pos = self.pos if isinstance(self.pos, QPointF) else QPointF(self.initial_spawn_pos)

        current_collision_height = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        current_collision_width = self.base_crouch_collision_width if self.is_crouching else self.base_standing_collision_width

        if current_collision_height <= 1e-6: current_collision_height = self.standard_height
        if current_collision_width <= 1e-6: current_collision_width = current_collision_height * 0.5

        rect_x = target_pos.x() - current_collision_width / 2.0
        rect_y = target_pos.y() - current_collision_height
        if not hasattr(self, 'rect') or self.rect is None: # Initialize if not present
            self.rect = QRectF(rect_x, rect_y, current_collision_width, current_collision_height)
        else:
            self.rect.setRect(rect_x, rect_y, current_collision_width, current_collision_height)

    def alive(self) -> bool: return self._alive
    def kill(self):
        if self._alive: debug(f"Player {self.player_id} kill() called.")
        self._alive = False

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True # Already effectively standing height

        current_crouch_rect = self.rect
        current_feet_y = current_crouch_rect.bottom()
        current_center_x = current_crouch_rect.center().x()

        potential_standing_width = self.base_standing_collision_width
        potential_standing_height = self.standing_collision_height

        potential_standing_rect_left = current_center_x - (potential_standing_width / 2.0)
        potential_standing_rect_top = current_feet_y - potential_standing_height
        potential_standing_rect = QRectF(potential_standing_rect_left, potential_standing_rect_top,
                                         potential_standing_width, potential_standing_height)

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF):
                if potential_standing_rect.intersects(platform_obj.rect):
                    # Check if the platform is actually *above* the crouched head space
                    if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                       platform_obj.rect.top() < current_crouch_rect.top(): # Platform is at least partially above crouched head
                        if self.print_limiter.can_log(f"cannot_stand_p{self.player_id}"):
                             debug(f"Player {self.player_id} cannot stand: Blocked by platform {platform_obj.rect}")
                        return False
        if self.print_limiter.can_log(f"can_stand_p{self.player_id}"):
             debug(f"Player {self.player_id} can stand up.")
        return True

    def set_state(self, new_state: str, current_game_time_ms_param: Optional[int] = None): set_player_state(self, new_state, current_game_time_ms_param)
    def animate(self): update_player_animation(self)
    def process_input(self, qt_keys_held_snapshot: Dict[Qt.Key, bool], qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
                      platforms_list: List[Any], joystick_data_for_handler: Optional[Dict[str, Any]] = None ) -> Dict[str, bool]:
        active_mappings = {}
        player_id_for_map_get = self.player_id
        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_pygame_"):
            active_mappings = getattr(game_config, f"P{player_id_for_map_get}_MAPPINGS", game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS)
        else: # Fallback
            active_mappings = game_config.P1_MAPPINGS if self.player_id == 1 else game_config.P2_MAPPINGS # Default to P1 map if unknown
            if Player.print_limiter.can_log(f"p_input_scheme_fallback_{self.player_id}"):
                warning(f"Player {self.player_id}: Unrecognized control_scheme '{self.control_scheme}'. Using default keyboard map.")
        return process_player_input_logic(self, qt_keys_held_snapshot, qt_key_event_data_this_frame, active_mappings, platforms_list, joystick_data_for_handler)

    def _generic_fire_projectile(self, projectile_class: type, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting: return
        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_log(f"proj_fire_no_game_elements_{self.player_id}"):
                warning(f"Player {self.player_id}: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return
        projectiles_list_ref: Optional[List[Any]] = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref: Optional[List[Any]] = self.game_elements_ref_for_projectiles.get("all_renderable_objects")
        if projectiles_list_ref is None or all_renderables_ref is None:
            if Player.print_limiter.can_log(f"proj_fire_list_missing_{self.player_id}"):
                warning(f"Player {self.player_id}: Projectile or renderable list missing. Cannot fire {projectile_config_name}.")
            return
        current_time_ms = get_current_ticks_monotonic(); last_fire_time = getattr(self, cooldown_attr_name, 0)
        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)
            if self.rect.isNull(): self._update_rect_from_image_and_pos() # Ensure rect is valid
            if self.rect.isNull(): error(f"Player {self.player_id}: Rect is null, cannot fire projectile."); return
            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6): # Default aim if none set
                aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0)
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0))
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0 # Spawn slightly ahead
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): # If aiming mostly up/down
                offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0
            norm_x, norm_y = 0.0, 0.0; length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length
            spawn_x += norm_x * offset_dist; spawn_y += norm_y * offset_dist
            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles
            projectiles_list_ref.append(new_projectile); all_renderables_ref.append(new_projectile)
            if Player.print_limiter.can_log(f"fired_{projectile_config_name}_{self.player_id}"):
                debug(f"Player {self.player_id} fired {projectile_config_name} at ({spawn_x:.1f},{spawn_y:.1f}) dir ({aim_dir.x():.1f},{aim_dir.y():.1f})")
            if projectile_config_name == 'blood' and self.current_health > 0:
                self.current_health -= self.current_health * 0.05 # Example: 5% health cost
                if self.current_health <= 0 and not self.is_dead: self.set_state('death', get_current_ticks_monotonic())

    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')

    def check_attack_collisions(self, list_of_targets: List[Any]): check_player_attack_collisions(self, list_of_targets)
    def take_damage(self, damage_amount_taken: int): player_take_damage(self, damage_amount_taken)
    def self_inflict_damage(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)
    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]) -> bool: return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    def insta_kill(self):
        if not self._valid_init or self.is_dead or not self._alive: return
        info(f"Player P{self.player_id}: insta_kill() called.")
        self.current_health = 0; self.is_dead = True
        self.set_state('death', get_current_ticks_monotonic()) # Ensure state transition
        if hasattr(self, 'animate'): self.animate() # Update visual to death frame

    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
               hazards_list: List[Any], other_players_list: List[Any], hittable_targets_by_player_melee: List[Any]):
        if not self._valid_init or not self._alive: return
        current_time_ms = get_current_ticks_monotonic()
        status_overrode_update = self.update_status_effects(current_time_ms)
        if status_overrode_update:
            if hasattr(self, 'animate'): self.animate()
            return
        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, hittable_targets_by_player_melee)

    def update_status_effects(self, current_time_ms: int) -> bool: return update_player_status_effects(self, current_time_ms)
    def draw_pyside(self, painter: QPainter, camera: 'CameraClass_TYPE'):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            if hasattr(self, 'pos') and isinstance(self.pos, QPointF) and camera:
                temp_fallback_rect = QRectF(self.pos.x()-5, self.pos.y()-10, 10,10) # Small fallback visual
                screen_fb_rect = camera.apply(temp_fallback_rect)
                painter.fillRect(screen_fb_rect, QColor(255,0,255)) # Magenta
            return

        should_draw = self.alive() or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      self.is_petrified # Draw petrified players

        if not should_draw: return

        collision_rect_on_screen: QRectF = camera.apply(self.rect)
        if not painter.window().intersects(collision_rect_on_screen.toRect()):
            return # Player is off-screen

        # Visual sprite might be larger than collision rect, adjust draw position
        visual_sprite_width = float(self.image.width())
        visual_sprite_height = float(self.image.height())

        # Align visual sprite's bottom-center with collision rect's bottom-center for better footing
        draw_x_visual = collision_rect_on_screen.center().x() - (visual_sprite_width / 2.0)
        draw_y_visual = collision_rect_on_screen.bottom() - visual_sprite_height
        draw_pos_visual = QPointF(draw_x_visual, draw_y_visual)

        if self.is_tipping and abs(self.tipping_angle) > 0.1:
            painter.save()
            # Pivot point for tipping should be relative to the visual sprite, aligned with collision rect's pivot
            pivot_in_sprite_x = self.tipping_pivot_x_world - self.rect.left() # How far from collision rect's left is the pivot
            pivot_visual_x = draw_pos_visual.x() + pivot_in_sprite_x
            pivot_visual_y = draw_pos_visual.y() + visual_sprite_height # Pivot around bottom edge
            painter.translate(pivot_visual_x, pivot_visual_y)
            painter.rotate(self.tipping_angle)
            painter.translate(-pivot_visual_x, -pivot_visual_y)
            painter.drawPixmap(draw_pos_visual, self.image)
            painter.restore()
        else:
            painter.drawPixmap(draw_pos_visual, self.image)

    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any], platforms_list_ref: List[Any]):
        if self.game_elements_ref_for_projectiles is None: self.game_elements_ref_for_projectiles = {}
        self.game_elements_ref_for_projectiles["projectiles_list"] = projectile_list
        self.game_elements_ref_for_projectiles["all_renderable_objects"] = all_elements_list
        self.game_elements_ref_for_projectiles["platforms_list"] = platforms_list_ref

    def get_network_data(self) -> Dict[str, Any]: return get_player_network_data(self)
    def set_network_data(self, network_data: Dict[str, Any]): set_player_network_data(self, network_data)
    def handle_network_input(self, received_input_data_dict: Dict[str, Any]): handle_player_network_input(self, received_input_data_dict)

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting or self.is_zapped:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_aflame_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: apply_aflame_effect blocked by existing conflicting state.")
            return
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_aflame_success_{self.player_id}"):
            debug(f"Player {self.player_id} Log: Applying aflame effect.")
        self.set_state('aflame_crouch' if self.is_crouching else 'aflame', get_current_ticks_monotonic())
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming or self.is_zapped:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_freeze_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: apply_freeze_effect blocked by existing conflicting state.")
            return
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_freeze_success_{self.player_id}"):
            debug(f"Player {self.player_id} Log: Applying freeze effect.")
        self.set_state('frozen', get_current_ticks_monotonic())
        self.is_attacking = False; self.attack_type = 0
        if hasattr(self.vel, 'setX') and hasattr(self.vel, 'setY'): self.vel.setX(0); self.vel.setY(0)
        if hasattr(self.acc, 'setX'): self.acc.setX(0)

    def apply_zapped_effect(self):
        if self.is_zapped or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting or self.is_aflame or self.is_deflaming:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_zapped_blocked_{self.player_id}"):
                debug(f"Player {self.player_id}: apply_zapped_effect blocked by existing conflicting state.")
            return
        if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"apply_zapped_success_{self.player_id}"):
            debug(f"Player {self.player_id} Log: Applying ZAPPED effect.")
        self.set_state('zapped', get_current_ticks_monotonic())
        self.is_attacking = False; self.attack_type = 0

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified) or self.is_zapped:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"petrify_blocked_internal_{self.player_id}"):
                debug(f"Player {self.player_id}: Internal petrify() blocked by conflicting state (petrified: {self.is_petrified}, dead: {self.is_dead}, zapped: {self.is_zapped}).")
            return
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        self.is_aflame = False; self.is_deflaming = False
        if hasattr(self, 'overall_fire_effect_start_time'): self.overall_fire_effect_start_time = 0
        self.is_frozen = False; self.is_defrosting = False; self.is_zapped = False
        self.is_petrified = True; self.is_stone_smashed = False
        self.is_dead = True; self.current_health = 0

        if self.game_elements_ref_for_projectiles is not None:
            petrify_player(self, self.game_elements_ref_for_projectiles)
        else:
            error(f"Player {self.player_id}: game_elements_ref_for_projectiles is None. Cannot create statue. Player will be petrified in-place (visuals only).")
            self.set_state('petrified', get_current_ticks_monotonic())
            self.kill()
            info(f"Player {self.player_id}: Petrified in-place (no statue object created due to missing game_elements_ref).")

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"smash_petrify_success_{self.player_id}"):
                debug(f"Player {self.player_id}: Smashing petrification.")
            self.set_state('smashed', get_current_ticks_monotonic())