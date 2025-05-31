#################### START OF FILE: player\player_movement_physics.py ####################
# player/player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
MODIFIED: Ensures gravity is applied to a dead player while their death animation is playing.
MODIFIED: Added logic for player "tipping" off ledges (with gap check).
MODIFIED: Corrected import paths for logger and relative imports for other player handlers.
"""
# version 2.0.11 (Corrected import paths)

from typing import List, Any, Optional, TYPE_CHECKING
import time
import math

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# --- Project Root Setup ---
import os
import sys
_PLAYER_MOVEMENT_PHYSICS_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_PLAYER_MOVEMENT_PHYSICS = os.path.dirname(_PLAYER_MOVEMENT_PHYSICS_PY_FILE_DIR) # Up one level to 'player'
if _PROJECT_ROOT_FOR_PLAYER_MOVEMENT_PHYSICS not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_PLAYER_MOVEMENT_PHYSICS) # Add 'player' package's parent
_PROJECT_ROOT_GRANDPARENT_MOVEMENT = os.path.dirname(_PROJECT_ROOT_FOR_PLAYER_MOVEMENT_PHYSICS) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_MOVEMENT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_MOVEMENT) # Add actual project root
# --- End Project Root Setup ---

# Game imports
import main_game.constants as C
from main_game.items import Chest # Assuming items.py is in main_game
from player.statue import Statue  # Assuming statue.py is in player.statue

# --- Handler Imports (relative within 'player' package) ---
_HANDLERS_PHYSICS_AVAILABLE = True
try:
    from .player_collision_handler import (
        check_player_platform_collisions,
        check_player_ladder_collisions,
        check_player_character_collisions,
        check_player_hazard_collisions
    )
    from .player_state_handler import set_player_state
except ImportError as e_handler_phys_import:
    print(f"CRITICAL PLAYER_MOVEMENT_PHYSICS: Failed to import one or more player handlers: {e_handler_phys_import}")
    _HANDLERS_PHYSICS_AVAILABLE = False
    # Define stubs for critical missing handlers
    def check_player_platform_collisions(*_args, **_kwargs): pass
    def check_player_ladder_collisions(*_args, **_kwargs): pass
    def check_player_character_collisions(*_args, **_kwargs): return False
    def check_player_hazard_collisions(*_args, **_kwargs): pass
    def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(player, 'state'): player.state = new_state
        print(f"WARNING PLAYER_MOVEMENT_PHYSICS (Fallback): set_player_state used for P{getattr(player, 'player_id', 'N/A')} to '{new_state}'")
# --- End Handler Imports ---


# --- Logger Setup ---
import logging
_player_movement_logger_instance = logging.getLogger(__name__ + "_player_movement_internal_fallback")
if not _player_movement_logger_instance.hasHandlers():
    _handler_pm_fb = logging.StreamHandler(sys.stdout)
    _formatter_pm_fb = logging.Formatter('PLAYER_MOVEMENT (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_pm_fb.setFormatter(_formatter_pm_fb)
    _player_movement_logger_instance.addHandler(_handler_pm_fb)
    _player_movement_logger_instance.setLevel(logging.DEBUG)
    _player_movement_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _player_movement_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _player_movement_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _player_movement_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _player_movement_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _player_movement_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

_ENABLE_DETAILED_PHYSICS_LOGS_HERE = False # Local toggle for this file's physics logging
_PHYSICS_FILE_LOG_PLAYER_PHYSICS_FUNC = None

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical, \
                               ENABLE_DETAILED_PHYSICS_LOGS as _PROJECT_LOG_PHYSICS_ENABLED, \
                               log_player_physics as _PROJECT_LOG_PLAYER_PHYSICS_FUNC
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    _ENABLE_DETAILED_PHYSICS_LOGS_HERE = _PROJECT_LOG_PHYSICS_ENABLED
    _PHYSICS_FILE_LOG_PLAYER_PHYSICS_FUNC = _PROJECT_LOG_PLAYER_PHYSICS_FUNC
    debug("PlayerMovementPhysics: Successfully aliased project's logger and physics log settings.")
except ImportError:
    critical("CRITICAL PLAYER_MOVEMENT_PHYSICS: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_pm:
    critical(f"CRITICAL PLAYER_MOVEMENT_PHYSICS: Unexpected error during logger setup from main_game.logger: {e_logger_init_pm}. Using internal fallback.")

# --- End Logger Setup ---

if TYPE_CHECKING:
    from .player import Player as PlayerClass_TYPE # Relative import for Player type hint


_physics_file_rate_limiter = time.monotonic() # Simplified rate limiter for file-level logs
_PHYSICS_FILE_LOG_INTERVAL = 1.0

def _can_log_from_this_file_internal() -> bool:
    global _physics_file_rate_limiter
    now = time.monotonic()
    if now - _physics_file_rate_limiter >= _PHYSICS_FILE_LOG_INTERVAL:
        _physics_file_rate_limiter = now
        return True
    return False

def _file_debug(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): debug(message, *args, **kwargs)
def _file_info(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): info(message, *args, **kwargs)
def _file_log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    if _ENABLE_DETAILED_PHYSICS_LOGS_HERE and _PHYSICS_FILE_LOG_PLAYER_PHYSICS_FUNC and _can_log_from_this_file_internal():
        _PHYSICS_FILE_LOG_PLAYER_PHYSICS_FUNC(player, message_tag, extra_info)


_start_time_player_physics = time.monotonic()
def get_current_ticks() -> int: return int((time.monotonic() - _start_time_player_physics) * 1000)

def manage_player_state_timers_and_cooldowns(player: 'PlayerClass_TYPE'):
    if not _HANDLERS_PHYSICS_AVAILABLE: return # Skip if state handler is missing
    current_time_ms = get_current_ticks()
    player_id_str = f"P{player.player_id}"
    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        _file_debug(f"{player_id_str} Physics Timers: Dash timer expired. is_dashing -> False.")
        player.is_dashing = False; set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)
    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        _file_debug(f"{player_id_str} Physics Timers: Roll timer expired. is_rolling -> False.")
        player.is_rolling = False; set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)
    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide':
            _file_debug(f"{player_id_str} Physics Timers: Slide timer expired. is_sliding -> False.")
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key: set_player_state(player, slide_end_anim_key, current_time_ms)
            else: set_player_state(player, 'crouch' if player.is_crouching else 'idle', current_time_ms)
    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        _file_debug(f"{player_id_str} Physics Timers: Hit cooldown expired. is_taking_hit -> False.")
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead: set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)

def apply_player_movement_and_physics(player: 'PlayerClass_TYPE', platforms_list: List[Any]):
    if not _HANDLERS_PHYSICS_AVAILABLE: return # Skip if state handler or others are missing
    player_id_str = f"P{player.player_id}"
    if player.is_tipping:
        tipping_angle_increment = 2.0; max_tipping_angle = 35.0; horizontal_nudge_per_frame = 0.7
        player.tipping_angle += player.tipping_direction * tipping_angle_increment
        player.tipping_angle = max(-max_tipping_angle, min(max_tipping_angle, player.tipping_angle))
        player.pos.setX(player.pos.x() + player.tipping_direction * horizontal_nudge_per_frame)
        if abs(player.tipping_angle) >= max_tipping_angle:
            _file_debug(f"{player_id_str} Physics: Tipping angle limit reached. Falling.")
            player.is_tipping = False; player.on_ground = False
            player.vel.setX(player.tipping_direction * C.PLAYER_RUN_SPEED_LIMIT * 0.3); player.vel.setY(1.0)
            set_player_state(player, 'fall', get_current_ticks()); return
        player.vel.setY(0); player.acc.setY(0); player.acc.setX(0)
        _file_log_player_physics(player, "TIPPING_ACTIVE", f"Angle:{player.tipping_angle:.1f}"); return

    should_apply_gravity_this_frame = True
    if player.on_ladder or player.state == 'wall_hang' or player.is_dashing or player.is_frozen or player.is_defrosting:
        should_apply_gravity_this_frame = False
    if player.is_petrified and not getattr(player, 'is_stone_smashed', False):
        if player.on_ground: should_apply_gravity_this_frame = False; player.acc.setY(0.0)
        else: player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7))); should_apply_gravity_this_frame = True
    elif player.is_dead and not player.is_petrified and not player.death_animation_finished:
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7))); should_apply_gravity_this_frame = True
    elif not player.on_ladder and not (player.is_petrified and player.on_ground):
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
    if should_apply_gravity_this_frame: player.vel.setY(player.vel.y() + player.acc.y())

    base_player_accel = C.PLAYER_ACCEL; base_player_run_speed_limit = C.PLAYER_RUN_SPEED_LIMIT
    if player.is_aflame: base_player_accel *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0); base_player_run_speed_limit *= getattr(C, 'PLAYER_AFLAME_SPEED_MULTIPLIER', 1.0)
    elif player.is_deflaming: base_player_accel *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0); base_player_run_speed_limit *= getattr(C, 'PLAYER_DEFLAME_SPEED_MULTIPLIER', 1.0)
    if player.is_rolling:
        roll_control_accel_magnitude = base_player_accel * C.PLAYER_ROLL_CONTROL_ACCEL_FACTOR; nudge_accel_x = 0.0
        if player.is_trying_to_move_left and not player.is_trying_to_move_right: nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left: nudge_accel_x = roll_control_accel_magnitude
        player.vel.setX(player.vel.x() + nudge_accel_x)
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15; min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4
        current_vel_x = player.vel.x()
        if current_vel_x > 0: current_vel_x = min(current_vel_x, max_roll_speed_cap);
        if player.facing_right: current_vel_x = max(current_vel_x, min_roll_speed_cap)
        elif current_vel_x < 0: current_vel_x = max(current_vel_x, -max_roll_speed_cap);
        if not player.facing_right: current_vel_x = min(current_vel_x, -min_roll_speed_cap)
        player.vel.setX(current_vel_x)
        if nudge_accel_x == 0 and abs(player.vel.x()) > 0.1: player.vel.setX(player.vel.x() * 0.99);
        if abs(player.vel.x()) < 0.5: player.vel.setX(0.0)
    else:
        should_apply_horizontal_physics = not (player.is_dashing or player.on_ladder or player.is_frozen or player.is_defrosting or (player.is_petrified and not getattr(player, 'is_stone_smashed', False)) or (player.is_dead and not player.is_petrified) )
        if should_apply_horizontal_physics: player.vel.setX(player.vel.x() + player.acc.x())
        friction_coeff = 0.0
        if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide': friction_coeff = C.PLAYER_FRICTION
        elif not player.on_ground and not player.is_attacking and player.state not in ['wall_slide','wall_hang']: friction_coeff = C.PLAYER_FRICTION * 0.2
        elif player.is_sliding or player.state == 'slide': friction_coeff = C.PLAYER_FRICTION * 0.7
        if friction_coeff != 0:
             friction_force_per_frame = player.vel.x() * friction_coeff
             if abs(player.vel.x()) > 0.1: player.vel.setX(player.vel.x() + friction_force_per_frame)
             else: player.vel.setX(0.0)
             if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                 player.is_sliding = False
                 slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                 if slide_end_key: set_player_state(player, slide_end_key, get_current_ticks())
                 else: set_player_state(player, 'crouch' if player.is_crouching else 'idle', get_current_ticks())
        current_h_speed_limit = base_player_run_speed_limit
        if player.is_crouching and player.state == 'crouch_walk': current_h_speed_limit *= 0.6
        if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide': player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))
        if player.is_dead and not player.is_petrified: player.acc.setX(0.0)
        elif player.is_frozen or player.is_defrosting or (player.is_petrified and not getattr(player, 'is_stone_smashed', False)): player.vel.setX(0.0); player.acc.setX(0.0)
    if player.vel.y() > 0 and not player.on_ladder: player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))

def check_and_initiate_tipping(player: 'PlayerClass_TYPE', platforms_list: List[Any]):
    if not _HANDLERS_PHYSICS_AVAILABLE: return False # Skip if state handler is missing
    if not player.on_ground or player.is_tipping or player.on_ladder or \
       player.is_frozen or player.is_petrified or player.is_dead or \
       player.is_dashing or player.is_rolling or player.is_sliding:
        return False

    player_collision_rect = player.rect
    player_center_x = player_collision_rect.center().x()
    player_bottom_y = player_collision_rect.bottom()
    supporting_platform: Optional[Any] = None
    min_vertical_dist_to_support = float('inf')

    for plat in platforms_list:
        if not hasattr(plat, 'rect') or not isinstance(plat.rect, QRectF): continue
        if isinstance(plat, Statue) and plat.is_smashed: continue
        horizontal_overlap = max(0, min(player_collision_rect.right(), plat.rect.right()) - max(player_collision_rect.left(), plat.rect.left()))
        if horizontal_overlap < player_collision_rect.width() * 0.1: continue
        vertical_dist = abs(player_bottom_y - plat.rect.top())
        if vertical_dist < 5.0 :
            if vertical_dist < min_vertical_dist_to_support:
                min_vertical_dist_to_support = vertical_dist; supporting_platform = plat
            elif vertical_dist == min_vertical_dist_to_support and supporting_platform:
                dist_to_current_support_center = abs(player_center_x - supporting_platform.rect.center().x())
                dist_to_new_support_center = abs(player_center_x - plat.rect.center().x())
                if dist_to_new_support_center < dist_to_current_support_center: supporting_platform = plat
    if not supporting_platform:
        if player.on_ground: player.on_ground = False; set_player_state(player, 'fall', get_current_ticks()); _file_debug(f"P{player.player_id} No supporting platform found while on_ground=True. Transitioning to fall.")
        return False

    support_left_edge = supporting_platform.rect.left(); support_right_edge = supporting_platform.rect.right()
    player_half_width_for_tip_check = player.rect.width() * 0.55
    tip_direction = 0; pivot_x = 0.0

    if player.rect.left() < support_left_edge and player.rect.right() < support_right_edge:
        amount_hanging_off_left = support_left_edge - player.rect.left()
        if amount_hanging_off_left > player_half_width_for_tip_check: tip_direction = -1; pivot_x = support_left_edge
    elif player.rect.right() > support_right_edge and player.rect.left() > support_left_edge:
        amount_hanging_off_right = player.rect.right() - support_right_edge
        if amount_hanging_off_right > player_half_width_for_tip_check: tip_direction = 1; pivot_x = support_right_edge

    if tip_direction != 0:
        is_gap_present = True
        gap_check_rect_width = player.rect.width() * 0.5; gap_check_rect_height = player.rect.height() * 0.5
        gap_check_rect_y = supporting_platform.rect.top() - gap_check_rect_height
        gap_check_rect_x = pivot_x - gap_check_rect_width if tip_direction == -1 else pivot_x
        potential_landing_rect = QRectF(gap_check_rect_x, gap_check_rect_y, gap_check_rect_width, gap_check_rect_height)
        for plat_check_gap in platforms_list:
            if plat_check_gap is supporting_platform: continue
            if not hasattr(plat_check_gap, 'rect') or not isinstance(plat_check_gap.rect, QRectF): continue
            if isinstance(plat_check_gap, Statue) and plat_check_gap.is_smashed: continue
            if potential_landing_rect.intersects(plat_check_gap.rect):
                if abs(plat_check_gap.rect.top() - supporting_platform.rect.top()) < C.TILE_SIZE / 2:
                    is_gap_present = False; _file_debug(f"P{player.player_id} Tipping ({tip_direction}) PREVENTED by adjacent platform: {plat_check_gap.rect}"); break
        if is_gap_present:
            player.is_tipping = True; player.tipping_direction = tip_direction
            player.tipping_angle = 0.0; player.tipping_pivot_x_world = pivot_x
            player.vel.setX(0); player.acc.setX(0)
            _file_info(f"P{player.player_id} Initiated tipping. Dir: {tip_direction}, PivotX: {pivot_x:.1f}. GAP CONFIRMED.")
            _file_log_player_physics(player, "TIPPING_START", f"Dir:{tip_direction}, PivotX:{pivot_x:.1f}")
            return True
        else: _file_debug(f"P{player.player_id} Tipping ({tip_direction}) attempt, but no gap found. PivotX: {pivot_x:.1f}"); return False
    return False


def update_player_core_logic(player: 'PlayerClass_TYPE', dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    player_id_str = f"P{player.player_id}"
    if not player._valid_init: _file_debug(f"{player_id_str} CoreLogic: Update skipped due to _valid_init={player._valid_init}."); return
    if not _HANDLERS_PHYSICS_AVAILABLE:
        if _can_log_from_this_file_internal():
            warning(f"{player_id_str} CoreLogic: Update skipped due to missing handlers (collision, state).")
        return

    _file_log_player_physics(player, "UPDATE_START")

    is_dying_with_anim = player.is_dead and not player.is_petrified and not player.death_animation_finished
    is_petrified_airborne_or_smashed_falling = player.is_petrified and (not player.on_ground or (player.is_stone_smashed and not player.death_animation_finished))

    if not player.alive() and not is_dying_with_anim and not is_petrified_airborne_or_smashed_falling:
        _file_debug(f"{player_id_str} CoreLogic: Update skipped. Not alive and not in physics-relevant death/petrified state.")
        if hasattr(player, 'animate'): player.animate()
        return

    if is_dying_with_anim or is_petrified_airborne_or_smashed_falling:
        _file_log_player_physics(player, "DYING/PETRI_PHYSICS_START")
        apply_player_movement_and_physics(player, platforms_list) # Applies gravity, updates vel from acc
        # Position update based on velocity (dt_sec effectively scales this to units/frame if vel is units/sec)
        # If vel is already units/frame, dt_sec * C.FPS = 1.0
        scaled_vel_y_dying = player.vel.y() #* dt_sec * C.FPS;
        player.pos.setY(player.pos.y() + scaled_vel_y_dying)
        if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
        check_player_platform_collisions(player, 'y', platforms_list)
        player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from rect
        if hasattr(player, 'animate'): player.animate()
        _file_log_player_physics(player, "UPDATE_END_LIMITED_PHYSICS", f"State: {player.state}"); return

    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list)
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False; set_player_state(player, 'fall' if not player.on_ground else 'idle', get_current_ticks())
    if player.on_ground and not player.is_tipping: check_and_initiate_tipping(player, platforms_list)
    apply_player_movement_and_physics(player, platforms_list)
    player.touching_wall = 0; player.on_ground = False # Reset before collision checks

    # --- X-axis Movement and Collision ---
    scaled_vel_x = player.vel.x() #* dt_sec * C.FPS;
    player.pos.setX(player.pos.x() + scaled_vel_x)
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "X_MOVE_APPLIED")
    check_player_platform_collisions(player, 'x', platforms_list)
    _file_log_player_physics(player, "X_PLAT_COLL_DONE")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    if player.game_elements_ref_for_projectiles:
        for item in player.game_elements_ref_for_projectiles.get("collectible_list", []):
            if isinstance(item, Chest) and item.alive() and item.state == 'closed': all_other_char_sprites.append(item)

    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        _file_log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) # Sync pos from resolved rect
        check_player_platform_collisions(player, 'x', platforms_list) # Re-check platform after char push
        _file_log_player_physics(player, "X_PLAT_RECHECK_POST_CHAR")

    # --- Y-axis Movement and Collision ---
    scaled_vel_y = player.vel.y() #* dt_sec * C.FPS;
    player.pos.setY(player.pos.y() + scaled_vel_y)
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "Y_MOVE_APPLIED")
    check_player_platform_collisions(player, 'y', platforms_list)
    _file_log_player_physics(player, "Y_PLAT_COLL_DONE")
    if not collided_horizontally_char: # Only do Y char collision if no X char collision occurred (to avoid double processing complex interactions)
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            _file_log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from resolved rect
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check platform
            _file_log_player_physics(player, "Y_PLAT_RECHECK_POST_CHAR")

    player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Final pos sync from rect
    _file_log_player_physics(player, "FINAL_POS_SYNC")

    check_player_hazard_collisions(player, hazards_list)

    # Attack if player is alive, not dead, and attacking
    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        # Add statues to the list of hittable targets for player melee
        statues_list_for_attack = player.game_elements_ref_for_projectiles.get("statue_objects", []) if player.game_elements_ref_for_projectiles else []
        targets_for_player_attack.extend([s for s in statues_list_for_attack if isinstance(s, Statue) and s.alive()]) # Statues are hittable

        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    if hasattr(player, 'animate'): player.animate()
    _file_log_player_physics(player, "UPDATE_END")

#################### END OF FILE: player/player_movement_physics.py ####################