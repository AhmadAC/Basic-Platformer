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
import sys # Added sys for logger pathing
import os # Added os for logger pathing
import logging # Keep standard logging for fallback logger definition

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# --- Project Root Setup ---
# (This block is generally not needed if the project is run from the root correctly
# or if the calling module handles sys.path, but good for standalone testing/linting)
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
    # Use basic print for critical import error if logger isn't set up yet
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
# Define fallback logger functions FIRST
_module_fallback_logger = logging.getLogger(__name__ + "_fallback_pm") # Unique name
if not _module_fallback_logger.hasHandlers():
    _h = logging.StreamHandler(sys.stdout)
    _f = logging.Formatter(f'{__name__.split(".")[-1].upper()} (FallbackConsole): %(levelname)s - %(message)s')
    _h.setFormatter(_f)
    _module_fallback_logger.addHandler(_h)
    _module_fallback_logger.setLevel(logging.DEBUG)
    _module_fallback_logger.propagate = False

def _fb_debug(msg, *args, **kwargs): _module_fallback_logger.debug(msg, *args, **kwargs)
def _fb_info(msg, *args, **kwargs): _module_fallback_logger.info(msg, *args, **kwargs)
def _fb_warning(msg, *args, **kwargs): _module_fallback_logger.warning(msg, *args, **kwargs)
def _fb_error(msg, *args, **kwargs): _module_fallback_logger.error(msg, *args, **kwargs)
def _fb_critical(msg, *args, **kwargs): _module_fallback_logger.critical(msg, *args, **kwargs)

# Assign fallbacks, then try to override with project logger
debug = _fb_debug
info = _fb_info
warning = _fb_warning
error = _fb_error
critical = _fb_critical
ENABLE_DETAILED_PHYSICS_LOGS = False # Fallback value
def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""): pass # Fallback stub

try:
    from main_game.logger import ( # Import from your project's logger
        ENABLE_DETAILED_PHYSICS_LOGS as _project_ENABLE_DETAILED_PHYSICS_LOGS,
        log_player_physics as _project_log_player_physics,
        debug as _project_debug,
        info as _project_info,
        warning as _project_warning,
        error as _project_error,
        critical as _project_critical
    )
    ENABLE_DETAILED_PHYSICS_LOGS = _project_ENABLE_DETAILED_PHYSICS_LOGS
    log_player_physics = _project_log_player_physics
    debug = _project_debug
    info = _project_info
    warning = _project_warning
    error = _project_error
    critical = _project_critical
    debug(f"{__name__}: Successfully aliased project's logger and detailed physics log settings.")
except ImportError:
    critical(f"CRITICAL {__name__.upper()}: Failed to import logger/detailed physics settings from main_game.logger. Using fallbacks.")
# --- End Logger Setup ---

if TYPE_CHECKING:
    from .player import Player as PlayerClass_TYPE # Relative import for Player type hint


_physics_file_rate_limiter = time.monotonic() # Simplified rate limiter for file-level logs
_PHYSICS_FILE_LOG_INTERVAL = 1.0 # Default, can be overridden by constants if needed

def _can_log_from_this_file_internal() -> bool:
    global _physics_file_rate_limiter
    now = time.monotonic()
    if now - _physics_file_rate_limiter >= _PHYSICS_FILE_LOG_INTERVAL:
        _physics_file_rate_limiter = now
        return True
    return False

# --- Localized log functions using the file-level rate limiter ---
def _file_debug(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): debug(message, *args, **kwargs)
def _file_info(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): info(message, *args, **kwargs)
def _file_log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    # Use the globally configured ENABLE_DETAILED_PHYSICS_LOGS and log_player_physics function
    # The rate limiting for detailed physics logs is handled within log_player_physics itself.
    if ENABLE_DETAILED_PHYSICS_LOGS and callable(log_player_physics):
        log_player_physics(player, message_tag, extra_info)


_start_time_player_physics = time.monotonic()
def get_current_ticks() -> int:
    """Returns milliseconds since this module was loaded, for consistent timing."""
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def check_and_initiate_tipping(player: 'PlayerClass_TYPE', platforms_list: List[Any]) -> bool:
    if not _HANDLERS_PHYSICS_AVAILABLE: return False # Skip if state handler is missing
    if not player.on_ground or player.is_tipping or player.on_ladder or \
       player.is_frozen or player.is_petrified or player.is_dead or \
       player.is_dashing or player.is_rolling or player.is_sliding:
        return False # Cannot tip in these states

    player_collision_rect = player.rect
    player_center_x = player_collision_rect.center().x()
    player_bottom_y = player_collision_rect.bottom()

    # Find the platform the player is primarily standing on
    supporting_platform: Optional[Any] = None
    min_vertical_dist_to_support = float('inf')

    for plat in platforms_list:
        if not hasattr(plat, 'rect') or not isinstance(plat.rect, QRectF): continue
        if isinstance(plat, Statue) and plat.is_smashed: continue # Smashed statues don't support

        # Check for horizontal overlap
        horizontal_overlap = max(0, min(player_collision_rect.right(), plat.rect.right()) - max(player_collision_rect.left(), plat.rect.left()))
        if horizontal_overlap < player_collision_rect.width() * 0.1: # Need some minimal overlap
            continue

        # Check vertical distance (player's feet to platform's top)
        vertical_dist = abs(player_bottom_y - plat.rect.top())
        if vertical_dist < 5.0 : # Player is very close to or on this platform's top
            if vertical_dist < min_vertical_dist_to_support:
                min_vertical_dist_to_support = vertical_dist
                supporting_platform = plat
            elif vertical_dist == min_vertical_dist_to_support and supporting_platform:
                # If multiple platforms at same height, pick the one closer to player's center
                dist_to_current_support_center = abs(player_center_x - supporting_platform.rect.center().x())
                dist_to_new_support_center = abs(player_center_x - plat.rect.center().x())
                if dist_to_new_support_center < dist_to_current_support_center:
                    supporting_platform = plat

    if not supporting_platform:
        # This case should ideally be handled by player.on_ground becoming False through Y-collisions
        # if no supporting platform is found during that phase.
        if player.on_ground: # If somehow still on_ground but no support found
            player.on_ground = False # Correct the state
            set_player_state(player, 'fall', get_current_ticks()) # Transition to fall
            if _can_log_from_this_file_internal(): _file_debug(f"P{player.player_id} No supporting platform found while on_ground=True. Transitioning to fall.")
        return False

    # Check if player is hanging off an edge enough to tip
    support_left_edge = supporting_platform.rect.left()
    support_right_edge = supporting_platform.rect.right()
    player_half_width_for_tip_check = player.rect.width() * 0.55 # More than half hanging off

    tip_direction = 0 # -1 for left, 1 for right
    pivot_x = 0.0     # The x-coordinate of the edge they are tipping over

    if player.rect.left() < support_left_edge and player.rect.right() < support_right_edge: # Hanging off left edge
        amount_hanging_off_left = support_left_edge - player.rect.left()
        if amount_hanging_off_left > player_half_width_for_tip_check:
            tip_direction = -1
            pivot_x = support_left_edge
    elif player.rect.right() > support_right_edge and player.rect.left() > support_left_edge: # Hanging off right edge
        amount_hanging_off_right = player.rect.right() - support_right_edge
        if amount_hanging_off_right > player_half_width_for_tip_check:
            tip_direction = 1
            pivot_x = support_right_edge

    if tip_direction != 0:
        # Check for a gap below the tipping edge
        is_gap_present = True
        # Define a small rectangle below and to the side where player would fall
        gap_check_rect_width = player.rect.width() * 0.5
        gap_check_rect_height = player.rect.height() * 0.5 # Check slightly below
        gap_check_rect_y = supporting_platform.rect.top() - gap_check_rect_height # Y is above the platform surface for this check

        if tip_direction == -1: # Tipping left, check for platform to the left and below
            gap_check_rect_x = pivot_x - gap_check_rect_width
        else: # Tipping right
            gap_check_rect_x = pivot_x

        potential_landing_rect = QRectF(gap_check_rect_x, gap_check_rect_y, gap_check_rect_width, gap_check_rect_height)

        for plat_check_gap in platforms_list:
            if plat_check_gap is supporting_platform: continue # Don't check against self
            if not hasattr(plat_check_gap, 'rect') or not isinstance(plat_check_gap.rect, QRectF): continue
            if isinstance(plat_check_gap, Statue) and plat_check_gap.is_smashed: continue

            if potential_landing_rect.intersects(plat_check_gap.rect):
                # If there's another platform very close vertically, it's not a real gap
                if abs(plat_check_gap.rect.top() - supporting_platform.rect.top()) < C.TILE_SIZE / 2:
                    is_gap_present = False
                    if _can_log_from_this_file_internal(): _file_debug(f"P{player.player_id} Tipping ({tip_direction}) PREVENTED by adjacent platform: {plat_check_gap.rect}")
                    break
        
        if is_gap_present:
            player.is_tipping = True
            player.tipping_direction = tip_direction
            player.tipping_angle = 0.0 # Start with no angle
            player.tipping_pivot_x_world = pivot_x # Store world X of pivot

            # Stop horizontal input momentum during tip animation
            player.vel.setX(0)
            player.acc.setX(0)
            if _can_log_from_this_file_internal(): _file_info(f"P{player.player_id} Initiated tipping. Dir: {tip_direction}, PivotX: {pivot_x:.1f}. GAP CONFIRMED.")
            _file_log_player_physics(player, "TIPPING_START", f"Dir:{tip_direction}, PivotX:{pivot_x:.1f}")
            return True
        else:
            if _can_log_from_this_file_internal(): _file_debug(f"P{player.player_id} Tipping ({tip_direction}) attempt, but no gap found. PivotX: {pivot_x:.1f}")
            return False
    return False # Not tipping

def manage_player_state_timers_and_cooldowns(player: 'PlayerClass_TYPE'):
    if not _HANDLERS_PHYSICS_AVAILABLE: return # Skip if state handler is missing
    current_time_ms = get_current_ticks()
    player_id_str = f"P{player.player_id}"

    # Dash Timer
    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        if _can_log_from_this_file_internal(): debug(f"{player_id_str} Physics Timers: Dash timer expired. is_dashing -> False.")
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)

    # Roll Timer
    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        if _can_log_from_this_file_internal(): debug(f"{player_id_str} Physics Timers: Roll timer expired. is_rolling -> False.")
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)

    # Slide Timer and State Transition
    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide': # Only transition if still in main slide state
            if _can_log_from_this_file_internal(): debug(f"{player_id_str} Physics Timers: Slide timer expired. is_sliding -> False.")
            player.is_sliding = False
            # Prefer slide_trans_end if available, otherwise crouch/idle
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key, current_time_ms)
            else:
                set_player_state(player, 'crouch' if player.is_crouching else 'idle', current_time_ms)

    # Hit Cooldown (prevents player from being chain-stunned)
    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        if _can_log_from_this_file_internal(): debug(f"{player_id_str} Physics Timers: Hit cooldown expired. is_taking_hit -> False.")
        player.is_taking_hit = False # Cooldown ended, can be hit again
        # If still in 'hit' state logically, transition out
        if player.state == 'hit' and not player.is_dead: # Ensure not dead before idling
            set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)


def apply_player_movement_and_physics(player: 'PlayerClass_TYPE', platforms_list: List[Any]):
    if not _HANDLERS_PHYSICS_AVAILABLE: return # Skip if handlers are missing
    player_id_str = f"P{player.player_id}"

    # Tipping logic
    if player.is_tipping:
        tipping_angle_increment = 2.0 # Degrees per frame/update
        max_tipping_angle = 35.0
        horizontal_nudge_per_frame = 0.7 # Small push towards the tipping direction

        player.tipping_angle += player.tipping_direction * tipping_angle_increment
        player.tipping_angle = max(-max_tipping_angle, min(max_tipping_angle, player.tipping_angle))

        # Apply horizontal nudge
        player.pos.setX(player.pos.x() + player.tipping_direction * horizontal_nudge_per_frame)

        # If tipping angle limit reached, player falls
        if abs(player.tipping_angle) >= max_tipping_angle:
            if _can_log_from_this_file_internal(): debug(f"{player_id_str} Physics: Tipping angle limit reached. Falling.")
            player.is_tipping = False
            player.on_ground = False # No longer supported by ground
            # Give a slight push in the tipping direction when falling
            player.vel.setX(player.tipping_direction * C.PLAYER_RUN_SPEED_LIMIT * 0.3)
            player.vel.setY(1.0) # Start a gentle fall
            set_player_state(player, 'fall', get_current_ticks()) # Transition to fall state
            return # Tipping overrides other movement for this frame

        # While tipping, vertical velocity and acceleration are zeroed
        player.vel.setY(0); player.acc.setY(0)
        player.acc.setX(0) # No horizontal acceleration input while tipping
        _file_log_player_physics(player, "TIPPING_ACTIVE", f"Angle:{player.tipping_angle:.1f}")
        return # Tipping animation/logic takes precedence

    # Determine if gravity should apply
    should_apply_gravity_this_frame = True
    if player.on_ladder or \
       player.state == 'wall_hang' or \
       player.is_dashing or \
       player.is_frozen or player.is_defrosting: # These states negate gravity directly
        should_apply_gravity_this_frame = False
    
    # Special gravity cases for petrified or dead states
    if player.is_petrified and not getattr(player, 'is_stone_smashed', False):
        if player.on_ground: # Petrified and on ground: no gravity
            should_apply_gravity_this_frame = False
            player.acc.setY(0.0)
        else: # Petrified and airborne: normal gravity
            player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
            should_apply_gravity_this_frame = True
    elif player.is_dead and not player.is_petrified and not player.death_animation_finished:
        # Dead player (not stone) whose death animation is still playing should fall
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        should_apply_gravity_this_frame = True
    elif not player.on_ladder and not (player.is_petrified and player.on_ground): # General case for non-ladder, non-petrified-grounded
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))

    # Apply gravity if determined
    if should_apply_gravity_this_frame:
        player.vel.setY(player.vel.y() + player.acc.y()) # acc.y is gravity (units/frame^2)

    # --- Horizontal Movement Logic ---
    base_player_accel = C.PLAYER_ACCEL
    base_player_run_speed_limit = C.PLAYER_RUN_SPEED_LIMIT

    # Adjust accel/speed for status effects
    if player.is_aflame:
        base_player_accel *= float(getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0))
        base_player_run_speed_limit *= float(getattr(C, 'PLAYER_AFLAME_SPEED_MULTIPLIER', 1.0))
    elif player.is_deflaming:
        base_player_accel *= float(getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0))
        base_player_run_speed_limit *= float(getattr(C, 'PLAYER_DEFLAME_SPEED_MULTIPLIER', 1.0))


    if player.is_rolling:
        roll_control_accel_magnitude = base_player_accel * C.PLAYER_ROLL_CONTROL_ACCEL_FACTOR
        nudge_accel_x = 0.0
        if player.is_trying_to_move_left and not player.is_trying_to_move_right: nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left: nudge_accel_x = roll_control_accel_magnitude
        
        player.vel.setX(player.vel.x() + nudge_accel_x)
        
        # Cap and maintain minimum roll speed
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15 # Allow slight overshoot from nudge
        min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4  # Maintain some minimum speed while rolling
        current_vel_x = player.vel.x()
        if current_vel_x > 0: current_vel_x = min(current_vel_x, max_roll_speed_cap);
        if player.facing_right: current_vel_x = max(current_vel_x, min_roll_speed_cap) # Ensure min speed in roll dir
        elif current_vel_x < 0: current_vel_x = max(current_vel_x, -max_roll_speed_cap);
        if not player.facing_right: current_vel_x = min(current_vel_x, -min_roll_speed_cap) # Ensure min speed in roll dir
        player.vel.setX(current_vel_x)
        
        # Slight deceleration if no input during roll
        if nudge_accel_x == 0 and abs(player.vel.x()) > 0.1: player.vel.setX(player.vel.x() * 0.99);
        # If roll speed drops too low naturally, stop it (though duration usually ends it)
        if abs(player.vel.x()) < 0.5: player.vel.setX(0.0)
    else:
        # Standard horizontal acceleration and friction
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or player.is_frozen or player.is_defrosting or \
            (player.is_petrified and not getattr(player, 'is_stone_smashed', False)) or \
            (player.is_dead and not player.is_petrified) # Allow dead player to fall, but not move horizontally via input
        )
        if should_apply_horizontal_physics:
            player.vel.setX(player.vel.x() + player.acc.x()) # acc.x is from input_handler (units/frame^2)
        
        # Apply Friction
        friction_coeff = 0.0
        if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide':
            friction_coeff = C.PLAYER_FRICTION
        elif not player.on_ground and not player.is_attacking and player.state not in ['wall_slide','wall_hang']: # Air friction
            friction_coeff = C.PLAYER_FRICTION * 0.2 # Reduced air friction
        elif player.is_sliding or player.state == 'slide': # Sliding friction
            friction_coeff = C.PLAYER_FRICTION * 0.7 # More friction for slides

        if friction_coeff != 0:
             friction_force_per_frame = player.vel.x() * friction_coeff
             if abs(player.vel.x()) > 0.1: # Apply friction if moving
                 player.vel.setX(player.vel.x() + friction_force_per_frame)
             else: # If speed is very low, stop completely
                 player.vel.setX(0.0)
             
             # If sliding and friction stops movement, transition out of slide
             if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                 player.is_sliding = False
                 slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                 if slide_end_key: set_player_state(player, slide_end_key, get_current_ticks())
                 else: set_player_state(player, 'crouch' if player.is_crouching else 'idle', get_current_ticks())

        # Horizontal Speed Limit (apply if not dashing, rolling, or sliding - those have their own speeds)
        current_h_speed_limit = base_player_run_speed_limit
        if player.is_crouching and player.state == 'crouch_walk':
            current_h_speed_limit *= 0.6 # Crouch walk speed reduction
        
        if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
            player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))

        # Ensure dead/frozen/petrified players don't accelerate horizontally from input
        if player.is_dead and not player.is_petrified: player.acc.setX(0.0)
        elif player.is_frozen or player.is_defrosting or (player.is_petrified and not getattr(player, 'is_stone_smashed', False)):
            player.vel.setX(0.0); player.acc.setX(0.0)

    # Terminal Velocity (Vertical)
    if player.vel.y() > 0 and not player.on_ladder: # Only apply if moving down and not on ladder
        player.vel.setY(min(player.vel.y(), float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))))


def update_player_core_logic(player: 'PlayerClass_TYPE', dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]): # enemies_list is for hittable targets by player
    player_id_str = f"P{player.player_id}"
    if not player._valid_init:
        if _can_log_from_this_file_internal(): _file_debug(f"{player_id_str} CoreLogic: Update skipped due to _valid_init={player._valid_init}.")
        return
    if not _HANDLERS_PHYSICS_AVAILABLE:
        if _can_log_from_this_file_internal():
            warning(f"{player_id_str} CoreLogic: Update skipped due to missing handlers (collision, state).")
        return

    _file_log_player_physics(player, "UPDATE_START")

    # --- Check for critical "gone" states first ---
    is_dying_with_anim = player.is_dead and not player.is_petrified and not player.death_animation_finished
    is_petrified_airborne_or_smashed_falling = player.is_petrified and \
                                               (not player.on_ground or (player.is_stone_smashed and not player.death_animation_finished))

    if not player.alive() and not is_dying_with_anim and not is_petrified_airborne_or_smashed_falling:
        # Player is fully "gone" from the game simulation perspective (not just visually dead)
        if _can_log_from_this_file_internal(): _file_debug(f"{player_id_str} CoreLogic: Update skipped. Not alive and not in physics-relevant death/petrified state.")
        if hasattr(player, 'animate'): player.animate() # Still animate if needed (e.g. fade out)
        return

    # --- Handle Physics for "Dying" or "Petrified-Falling" states ---
    # These states primarily involve gravity and platform collision.
    if is_dying_with_anim or is_petrified_airborne_or_smashed_falling:
        _file_log_player_physics(player, "DYING/PETRI_PHYSICS_START")
        apply_player_movement_and_physics(player, platforms_list) # Applies gravity, updates vel from acc

        # Position update based on velocity (dt_sec effectively scales this to units/frame if vel is units/sec)
        # If vel is already units/frame, dt_sec * C.FPS = 1.0
        scaled_vel_y_dying = player.vel.y() #* dt_sec * C.FPS; # Assuming vel is already units/frame
        player.pos.setY(player.pos.y() + scaled_vel_y_dying)
        if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()

        check_player_platform_collisions(player, 'y', platforms_list) # Check Y-axis collisions
        player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from rect after collision
        
        # If horizontal movement is allowed during these states (e.g. pushed by explosion while dying)
        if not (player.is_petrified and player.on_ground): # Petrified on ground is stuck
            scaled_vel_x_dying = player.vel.x() #* dt_sec * C.FPS;
            player.pos.setX(player.pos.x() + scaled_vel_x_dying)
            if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
            check_player_platform_collisions(player, 'x', platforms_list)
            player.pos.setX(player.rect.center().x())


        if hasattr(player, 'animate'): player.animate() # Continue animation
        _file_log_player_physics(player, "UPDATE_END_LIMITED_PHYSICS", f"State: {player.state}"); return # Skip full update logic

    # --- Full Update Logic for Alive/Active Players ---
    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list)

    # If on ladder but can no longer grab (e.g., moved off), transition to fall/idle
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle', get_current_ticks())

    # Tipping logic (only if on ground and not already tipping or in prohibitive state)
    if player.on_ground and not player.is_tipping:
        check_and_initiate_tipping(player, platforms_list)
    
    apply_player_movement_and_physics(player, platforms_list) # Updates vel based on acc, applies friction, speed limits

    # Reset collision flags before checks
    player.touching_wall = 0 # -1 for left, 1 for right, 0 for none
    player.on_ground = False # Will be set true by Y-collision if landed

    # --- X-axis Movement and Collision ---
    # Velocity is now units/frame, so no dt_sec scaling here for position update
    scaled_vel_x = player.vel.x()
    player.pos.setX(player.pos.x() + scaled_vel_x)
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "X_MOVE_APPLIED")

    check_player_platform_collisions(player, 'x', platforms_list)
    _file_log_player_physics(player, "X_PLAT_COLL_DONE")

    # Character collisions (other players, enemies, chests)
    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and hasattr(e, '_valid_init') and e._valid_init and hasattr(e, 'alive') and e.alive()]
    # Add Chest to character collision list if it's active and closed
    current_chest_instance = player.game_elements_ref_for_projectiles.get("current_chest") if player.game_elements_ref_for_projectiles else None
    if current_chest_instance and isinstance(current_chest_instance, Chest) and current_chest_instance.alive() and current_chest_instance.state == 'closed':
        all_other_char_sprites.append(current_chest_instance)

    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        _file_log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) # Sync pos from resolved rect
        # Re-check platform collision after character push potentially moved player
        check_player_platform_collisions(player, 'x', platforms_list)
        _file_log_player_physics(player, "X_PLAT_RECHECK_POST_CHAR")


    # --- Y-axis Movement and Collision ---
    scaled_vel_y = player.vel.y()
    player.pos.setY(player.pos.y() + scaled_vel_y)
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "Y_MOVE_APPLIED")

    check_player_platform_collisions(player, 'y', platforms_list)
    _file_log_player_physics(player, "Y_PLAT_COLL_DONE")

    # Only do Y character collision if no X char collision occurred this frame
    # to avoid complex double-processing of interactions in a single frame.
    if not collided_horizontally_char:
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            _file_log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from resolved rect
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check platform
            _file_log_player_physics(player, "Y_PLAT_RECHECK_POST_CHAR")


    player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Final pos sync from rect
    _file_log_player_physics(player, "FINAL_POS_SYNC")

    # Hazard Collisions
    check_player_hazard_collisions(player, hazards_list)

    # Attack if player is alive, not dead, and in an attacking state
    if player.alive() and not player.is_dead and player.is_attacking:
        # Compile list of targets for player's attack
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and hasattr(e, '_valid_init') and e._valid_init and hasattr(e, 'alive') and e.alive()]
        # Add statues to the list of hittable targets for player melee
        statues_list_for_attack = player.game_elements_ref_for_projectiles.get("statue_objects", []) if player.game_elements_ref_for_projectiles else []
        targets_for_player_attack.extend([s for s in statues_list_for_attack if isinstance(s, Statue) and s.alive()]) # Statues are hittable

        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    # Update Animation
    if hasattr(player, 'animate'):
        player.animate()

    _file_log_player_physics(player, "UPDATE_END")