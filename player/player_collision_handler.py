# player/player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution for PySide6.
MODIFIED: Player stomp destroys statues. Smashed statues are not solid.
MODIFIED: Statue stomp detection is more lenient on the top surface.
MODIFIED: Lava instant death property check.
MODIFIED: Character collision does not include solid Statues.
MODIFIED: Added extensive logging for Y-platform collision.
"""
# version 2.0.15 (Enhanced Y-platform collision logging)

from typing import List, Any, Optional, TYPE_CHECKING
import time
import sys # Added sys for logger pathing
import os # Added os for logger pathing
import logging # Keep standard logging for fallback logger definition

from PySide6.QtCore import QRectF, QPointF

# --- Project Root Setup ---
# (This block is generally not needed if the project is run from the root correctly
# or if the calling module handles sys.path, but good for standalone testing/linting)
_PLAYER_COLLISION_HANDLER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_PLAYER_COLLISION_HANDLER = os.path.dirname(_PLAYER_COLLISION_HANDLER_PY_FILE_DIR) # Up one level to 'player'
if _PROJECT_ROOT_FOR_PLAYER_COLLISION_HANDLER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_PLAYER_COLLISION_HANDLER) # Add 'player' package's parent
_PROJECT_ROOT_GRANDPARENT_COLLISION = os.path.dirname(_PROJECT_ROOT_FOR_PLAYER_COLLISION_HANDLER) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_COLLISION not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_COLLISION) # Add actual project root
# --- End Project Root Setup ---


import main_game.constants as C
from main_game.tiles import Lava # Assuming tiles.py is in main_game
from enemy import Enemy         # Assuming Enemy is in enemy package
from player.statue import Statue  # Assuming statue.py is in player.statue
from main_game.items import Chest # Assuming items.py is in main_game

if TYPE_CHECKING:
    from .player import Player as PlayerClass_TYPE # Relative import for Player type hint

# --- Logger Setup ---
# Define fallback logger functions FIRST
_module_fallback_logger = logging.getLogger(__name__ + "_fallback") # Unique name
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


_start_time_pcollision = time.monotonic()
def get_current_ticks_monotonic():
    """Returns milliseconds since this module was loaded, for consistent timing."""
    return int((time.monotonic() - _start_time_pcollision) * 1000)


def check_player_platform_collisions(player: 'PlayerClass_TYPE', direction: str, platforms_list: List[Any]):
    if not player._valid_init: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF) or not player.rect.isValid():
        if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"Player {player.player_id}: Invalid player rect for platform collision. Skipping.")
        return
    if not hasattr(player, 'vel') or not isinstance(player.vel, QPointF):
        if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"Player {player.player_id}: Missing vel attribute. Skipping platform collision.")
        return
    if not hasattr(player, 'pos') or not isinstance(player.pos, QPointF):
        if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"Player {player.player_id}: Missing pos attribute. Skipping platform collision.")
        return

    collided_with_wall_on_side_this_frame = 0 # 0: no, -1: left, 1: right
    player_id_log_collision = f"P{player.player_id} Coll"


    for platform_idx, platform_obj in enumerate(platforms_list):
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or not platform_obj.rect.isValid():
             if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"{player_id_log_collision}: Platform object {platform_idx} missing valid rect. Skipping.")
             continue

        # Ignore collisions with smashed statues (they are no longer solid platforms)
        if isinstance(platform_obj, Statue) and platform_obj.is_smashed:
            if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_ignore_smashed_{player.player_id}_{platform_obj.statue_id}"):
                log_player_physics(player, "PLAT_IGNORE_SMASH", f"StatueID: {platform_obj.statue_id}")
            continue

        if not player.rect.intersects(platform_obj.rect):
            continue

        # Intersection detected
        plat_type_debug = getattr(platform_obj, 'platform_type', getattr(platform_obj, 'tile_type', type(platform_obj).__name__))
        # if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED and player.print_limiter.can_log(f"plat_intersect_{player.player_id}_{platform_idx}_{direction}"):
        #     log_player_physics(player, f"INTERSECT DIR:{direction}",
        #                        (f"PlatIdx:{platform_idx} Type:{plat_type_debug} PRect:({platform_obj.rect.x():.1f},{platform_obj.rect.y():.1f} {platform_obj.rect.width():.0f}x{platform_obj.rect.height():.0f})",
        #                         f"PlayerRect:({player.rect.x():.1f},{player.rect.y():.1f} {player.rect.width():.0f}x{player.rect.height():.0f})"))


        original_vel_x_for_ai_reaction = player.vel.x() # Not used by player, but kept if this was generic

        if direction == 'x':
            if player.vel.x() > 0: # Moving right, collided with left edge of platform
                overlap_x = player.rect.right() - platform_obj.rect.left()
                if overlap_x > 0:
                    player.rect.translate(-overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder: # Potential wall interaction
                        min_v_overlap_for_wall = player.rect.height() * 0.3 # Must overlap at least 30% vertically
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = 1 # Hit wall on right
            elif player.vel.x() < 0: # Moving left, collided with right edge of platform
                overlap_x = platform_obj.rect.right() - player.rect.left()
                if overlap_x > 0:
                    player.rect.translate(overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder: # Potential wall interaction
                        min_v_overlap_for_wall = player.rect.height() * 0.3
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = -1 # Hit wall on left

            player.pos.setX(player.rect.center().x()) # Sync pos X from resolved rect center
            # if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED and player.print_limiter.can_log(f"plat_coll_x_res_{player.player_id}_{platform_idx}"):
            #      log_player_physics(player, f"PLAT_COLL_RESOLVED_X", f"PlatIdx:{platform_idx} Rect: {player.rect.x():.1f},{player.rect.y():.1f} {player.rect.width():.0f}x{player.rect.height():.0f}, VelX: {player.vel.x():.1f}")

        elif direction == 'y':
            if player.vel.y() >= 0: # Moving downwards or on ground and snapping
                overlap_y = player.rect.bottom() - platform_obj.rect.top()
                if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_coll_y_detail_P{player.player_id}_Plat{platform_idx}"):
                    debug(f"{player_id_log_collision} Y-DOWN INTERSECT PlatIdx:{platform_idx} ({plat_type_debug} at {platform_obj.rect.topLeft().y():.1f}) OverlapY:{overlap_y:.2f} PlayerBottom:{player.rect.bottom():.2f} PlayerVelY:{player.vel.y():.2f} PlayerOnGround:{player.on_ground}")

                if overlap_y > 0: # Potential collision with top surface of platform
                    min_h_overlap_ratio = float(getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.1))
                    min_h_overlap_pixels = player.rect.width() * min_h_overlap_ratio
                    actual_h_overlap = min(player.rect.right(), platform_obj.rect.right()) - \
                                       max(player.rect.left(), platform_obj.rect.left())

                    if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_coll_y_horiz_overlap_P{player.player_id}_Plat{platform_idx}"):
                        debug(f"{player_id_log_collision} Y-DOWN HorizOverlap Check PlatIdx:{platform_idx}: ActualHOverlap:{actual_h_overlap:.2f}, MinHPixels:{min_h_overlap_pixels:.2f} (PlayerW:{player.rect.width():.1f})")

                    if actual_h_overlap >= min_h_overlap_pixels:
                        # Stomp Logic (for statues)
                        if isinstance(platform_obj, Statue) and not platform_obj.is_smashed and player.vel.y() > 0.5: # Player moving down with some speed
                            # Estimate previous bottom based on current frame's velocity change
                            previous_player_bottom_y_for_stomp_calc = player.rect.bottom() - player.vel.y() # Approximation
                            statue_top_surface_for_check = platform_obj.rect.top()
                            can_stomp_this_statue = False
                            # Check if player was above or nearly at the statue's top in the previous "physics moment"
                            # and is now overlapping, with the player's feet penetrating the top part of the statue.
                            if previous_player_bottom_y_for_stomp_calc <= statue_top_surface_for_check + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX + 1.0 and \
                               player.rect.bottom() >= statue_top_surface_for_check and \
                               player.rect.bottom() <= statue_top_surface_for_check + (platform_obj.rect.height() * 0.75): # Allow some penetration for stomp registration
                                can_stomp_this_statue = True

                            if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"stomp_statue_check_P{player.player_id}_Statue{platform_obj.statue_id}"):
                                debug(f"{player_id_log_collision} StompStatue Check: CanStomp:{can_stomp_this_statue}, PrevPlayerBottom:{previous_player_bottom_y_for_stomp_calc:.1f}, StatueTop:{statue_top_surface_for_check:.1f}")

                            if can_stomp_this_statue:
                                if hasattr(platform_obj, 'get_stomped') and callable(platform_obj.get_stomped):
                                    platform_obj.get_stomped(player) # Statue handles its own smashing/state change
                                    player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH) # Player bounces
                                    player.on_ground = False
                                    if hasattr(player, 'set_state'): player.set_state('jump')
                                    # Move player slightly above the platform to avoid re-collision
                                    player.rect.moveBottom(platform_obj.rect.top() - 1.0)
                                    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                                    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "STOMPED_STATUE", f"StatueID: {platform_obj.statue_id}")
                                    continue # Processed stomp, skip rest for this platform

                        # Regular landing / snapping to ground
                        # Estimate where player's feet were before Y-velocity was applied this frame
                        previous_player_bottom_y_estimate = player.rect.bottom() - player.vel.y()
                        was_above_or_at_surface_epsilon = 1.0 # Small tolerance
                        was_truly_above_or_at_surface = previous_player_bottom_y_estimate <= platform_obj.rect.top() + was_above_or_at_surface_epsilon

                        # Check if player is already on ground and very close (within snap threshold)
                        can_snap_down_from_current = player.on_ground and \
                                                     player.rect.bottom() > platform_obj.rect.top() and \
                                                     player.rect.bottom() <= platform_obj.rect.top() + float(getattr(C, 'GROUND_SNAP_THRESHOLD', 5.0))

                        if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_coll_y_snap_check_P{player.player_id}_Plat{platform_idx}"):
                            debug(f"{player_id_log_collision} Y-DOWN SnapCheck PlatIdx:{platform_idx}: WasAbove:{was_truly_above_or_at_surface}, CanSnap:{can_snap_down_from_current}, PrevPlayerBottomEst:{previous_player_bottom_y_estimate:.1f}, PlatTop:{platform_obj.rect.top():.1f}")

                        if was_truly_above_or_at_surface or can_snap_down_from_current:
                            just_landed = not player.on_ground # Was player airborne before this?
                            player.rect.moveBottom(platform_obj.rect.top())
                            player.on_ground = True
                            player.vel.setY(0.0)
                            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'): player.acc.setY(0.0) # Stop gravity accumulation
                            
                            if just_landed:
                                player.can_wall_jump = False # Reset wall jump ability on landing
                                # Apply landing friction if not sliding or in a slide transition
                                if not player.is_sliding and not (hasattr(player, 'state') and str(player.state).startswith('slide_trans')):
                                    player.vel.setX(player.vel.x() * C.LANDING_FRICTION_MULTIPLIER)
                            if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_coll_y_land_P{player.player_id}_Plat{platform_idx}"):
                                 log_player_physics(player, f"PLAT_COLL_Y_LANDED", f"PlatIdx:{platform_idx} JustLand:{just_landed}")

            elif player.vel.y() < 0: # Moving upwards, collided with bottom surface of platform
                overlap_y = platform_obj.rect.bottom() - player.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio_ceil = float(getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.1))
                    min_h_overlap_pixels_ceil = player.rect.width() * min_h_overlap_ratio_ceil
                    actual_h_overlap_ceil = min(player.rect.right(), platform_obj.rect.right()) - \
                                            max(player.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap_ceil >= min_h_overlap_pixels_ceil:
                        if player.on_ladder: player.on_ladder = False # Knock off ladder if head hits ceiling
                        player.rect.translate(0, overlap_y) # Move player down
                        player.vel.setY(0.0) # Stop upward movement
                        if ENABLE_DETAILED_PHYSICS_LOGS and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"plat_coll_y_ceil_P{player.player_id}_Plat{platform_idx}"):
                            log_player_physics(player, f"PLAT_COLL_Y_CEILING", f"PlatIdx:{platform_idx}")
            
            player.pos.setY(player.rect.bottom()) # Sync pos Y from resolved rect bottom

    # Update player's wall interaction state after all X-collisions are resolved for this frame
    if direction == 'x':
        if collided_with_wall_on_side_this_frame != 0:
            player.touching_wall = collided_with_wall_on_side_this_frame
            # Allow setting can_wall_jump unless currently in a wall climb and holding the climb key
            can_set_wall_jump_now = not (hasattr(player, 'state') and player.state == 'wall_climb' and \
                                         hasattr(player, 'is_holding_climb_ability_key') and player.is_holding_climb_ability_key)
            if can_set_wall_jump_now:
                player.can_wall_jump = True
        else:
            # If no wall collision was registered in X, but player is not on ladder, clear touching_wall
            if not player.on_ladder:
                player.touching_wall = 0


def check_player_ladder_collisions(player: 'PlayerClass_TYPE', ladders_list: List[Any]):
    if not player._valid_init: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    # Use a smaller rect for ladder detection, centered on player
    ladder_check_rect = QRectF(player.rect)
    ladder_check_rect.setWidth(player.rect.width() * 0.4) # Narrower for less picky grabbing
    ladder_check_rect.setHeight(player.rect.height() * 0.9) # Slightly shorter
    ladder_check_rect.moveCenter(player.rect.center())

    player.can_grab_ladder = False
    for ladder_obj in ladders_list:
        if not hasattr(ladder_obj, 'rect') or not isinstance(ladder_obj.rect, QRectF):
             if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"Player Collision: Ladder object {ladder_obj} missing valid rect. Skipping.")
             continue
        if ladder_check_rect.intersects(ladder_obj.rect):
            # Check if player's center is roughly aligned with ladder's center horizontally
            # and player's vertical center is within ladder's vertical span
            if abs(player.rect.center().x() - ladder_obj.rect.center().x()) < ladder_obj.rect.width() * 0.7 and \
               ladder_obj.rect.top() < player.rect.center().y() < ladder_obj.rect.bottom():
                  player.can_grab_ladder = True
                  break # Found a grabbable ladder


def check_player_character_collisions(player: 'PlayerClass_TYPE', direction: str, characters_list: List[Any]) -> bool:
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: return False
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return False

    collision_occurred_this_axis = False
    rect_before_char_coll_resolve = QRectF(player.rect) # Store rect before any potential resolution

    for other_char in characters_list:
        # Basic validity checks for the other character
        if other_char is player or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()):
            continue

        # Special handling for Statues: they are not "characters" for push/bounce physics if not smashed
        if isinstance(other_char, Statue) and not other_char.is_smashed:
            continue # Solid statues are handled by platform collisions

        # For other characters (Enemies, other Players, smashed Statues if they were characters)
        is_chest = isinstance(other_char, Chest)
        is_enemy = isinstance(other_char, Enemy)

        if not is_chest: # General characters (Players, Enemies)
            is_other_valid_target = (hasattr(other_char, '_valid_init') and other_char._valid_init and
                                     hasattr(other_char, 'is_dead') and
                                     # Target is valid if not dead, OR if petrified but not smashed (can be interacted with)
                                     (not other_char.is_dead or
                                      (getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)) )
                                    )
            if not is_other_valid_target:
                continue

        if player.rect.intersects(other_char.rect):
            collision_occurred_this_axis = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)

            if is_chest:
                chest_obj = other_char # type: Chest
                if chest_obj.state == 'closed': # Only interact with closed chests
                    if direction == 'x':
                        push_force_dir = 0; overlap_x_chest = 0.0
                        if player.vel.x() > 0 and player.rect.right() > chest_obj.rect.left() and player.rect.center().x() < chest_obj.rect.center().x():
                            overlap_x_chest = player.rect.right() - chest_obj.rect.left()
                            player.rect.translate(-overlap_x_chest, 0); push_force_dir = 1
                        elif player.vel.x() < 0 and player.rect.left() < chest_obj.rect.right() and player.rect.center().x() > chest_obj.rect.center().x():
                            overlap_x_chest = chest_obj.rect.right() - player.rect.left()
                            player.rect.translate(overlap_x_chest, 0); push_force_dir = -1
                        
                        if push_force_dir != 0 and hasattr(chest_obj, 'acc_x') and hasattr(player, 'vel') and hasattr(player.vel, 'x'):
                            chest_obj.acc_x = C.CHEST_PUSH_ACCEL_BASE * push_force_dir * (abs(player.vel.x()) / C.PLAYER_RUN_SPEED_LIMIT if C.PLAYER_RUN_SPEED_LIMIT > 0 else 1.0)
                            player.vel.setX(0) # Player stops when pushing chest
                        if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())
                    elif direction == 'y': # Player landing on chest or hitting it from below
                        if player.vel.y() > 0 and player.rect.bottom() > chest_obj.rect.top() and rect_before_char_coll_resolve.bottom() <= chest_obj.rect.top() + 1: # Landed on top
                            player.rect.moveBottom(chest_obj.rect.top()); player.on_ground = True; player.vel.setY(0)
                        elif player.vel.y() < 0 and player.rect.top() < chest_obj.rect.bottom() and rect_before_char_coll_resolve.top() >= chest_obj.rect.bottom() -1 : # Hit from below
                            player.rect.moveTop(chest_obj.rect.bottom()); player.vel.setY(0)
                        if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())
                continue # Processed chest, move to next character

            # Player-Enemy / Player-Player Interactions
            is_other_susceptible_to_fire = not (getattr(other_char, 'is_aflame', False) or \
                                                getattr(other_char, 'is_frozen', False) or \
                                                getattr(other_char, 'is_petrified', False))

            if is_enemy and getattr(player, 'is_aflame', False) and \
               hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               is_other_susceptible_to_fire and not is_other_petrified_solid:
                other_char.apply_aflame_effect()

            # Stomp logic
            is_enemy_stompable = is_enemy and not other_char.is_dead and \
                                 not getattr(other_char, 'is_stomp_dying', False) and \
                                 not getattr(other_char, 'is_aflame', False) and \
                                 not getattr(other_char, 'is_frozen', False) and \
                                 not is_other_petrified_solid

            if is_enemy_stompable and direction == 'y' and player.vel.y() > 0.5: # Player moving down
                # Estimate where player's feet were before Y-velocity was applied this frame
                previous_player_bottom_y_for_stomp_calc = rect_before_char_coll_resolve.bottom() - player.vel.y() # Approximation
                stomp_head_grace_enemy = C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                target_stomp_effective_top_y_enemy = other_char.rect.top() + stomp_head_grace_enemy

                # Check if player was above or nearly at the enemy's effective top in the previous "physics moment"
                # and is now overlapping, with the player's feet penetrating the top part of the enemy.
                if previous_player_bottom_y_for_stomp_calc <= target_stomp_effective_top_y_enemy + 1.0 and \
                   player.rect.bottom() >= other_char.rect.top() and \
                   player.rect.bottom() <= other_char.rect.top() + (other_char.rect.height() * 0.65): # Allow some penetration for stomp
                    if hasattr(other_char, 'stomp_kill'): # Enemy specific stomp handler
                        other_char.stomp_kill()
                        player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH) # Player bounces
                        player.on_ground = False # Player is airborne after stomp
                        if hasattr(player, 'set_state'): player.set_state('jump')
                        player.rect.moveBottom(other_char.rect.top() - 1.0) # Move slightly above
                        if hasattr(player, 'pos'): player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                        return True # Stomp occurred, character collision handled for this interaction

            # Generic character bounce/push logic (if not stomping and not attacking a petrified solid target)
            if direction == 'x':
                if getattr(player, 'is_attacking', False) and not is_other_petrified_solid: # Player is attacking
                    # Light knockback to other character if player attacks
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX'):
                        push_dir_other = 1 if player.rect.center().x() < other_char.rect.center().x() else -1
                        other_char.vel.setX(push_dir_other * C.CHARACTER_BOUNCE_VELOCITY * 0.5)
                else: # Player is not attacking, standard bounce
                    bounce_vel = C.CHARACTER_BOUNCE_VELOCITY
                    push_dir_self = 0; overlap_x_char = 0.0
                    if player.rect.center().x() < other_char.rect.center().x(): # Player is to the left
                        overlap_x_char = player.rect.right() - other_char.rect.left()
                        player.rect.translate(-overlap_x_char, 0.0); push_dir_self = -1
                    else: # Player is to the right
                        overlap_x_char = other_char.rect.right() - player.rect.left()
                        player.rect.translate(overlap_x_char, 0.0); push_dir_self = 1

                    player.vel.setX(push_dir_self * bounce_vel)
                    # Other character also gets pushed if not in an uninterruptible state
                    can_push_other = not (getattr(other_char, 'is_attacking', False) or \
                                     is_other_petrified_solid or \
                                     getattr(other_char, 'is_dashing', False) or \
                                     getattr(other_char, 'is_rolling', False) or \
                                     getattr(other_char, 'is_aflame', False) or \
                                     getattr(other_char, 'is_frozen', False) )
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other:
                        other_char.vel.setX(-push_dir_self * bounce_vel)
                if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())

            elif direction == 'y': # Vertical collision with another character (less common for players unless stacked)
                overlap_y_char = 0.0
                if player.vel.y() > 0 and player.rect.bottom() > other_char.rect.top() and player.rect.center().y() < other_char.rect.center().y(): # Player landed on other
                    overlap_y_char = player.rect.bottom() - other_char.rect.top()
                    player.rect.translate(0, -overlap_y_char); player.on_ground = True; player.vel.setY(0.0)
                elif player.vel.y() < 0 and player.rect.top() < other_char.rect.bottom() and player.rect.center().y() > other_char.rect.center().y(): # Player hit other from below
                    overlap_y_char = other_char.rect.bottom() - player.rect.top()
                    player.rect.translate(0, overlap_y_char); player.vel.setY(0.0)
                if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())

    return collision_occurred_this_axis


def check_player_hazard_collisions(player: 'PlayerClass_TYPE', hazards_list: List[Any]):
    current_time_ms = get_current_ticks_monotonic()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or \
       player.is_petrified or player.is_frozen:
        return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    damaged_this_frame_by_hazard = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF):
            if ENABLE_DETAILED_PHYSICS_LOGS: warning(f"Player Collision: Hazard object {hazard_obj} missing valid rect. Skipping.");
            continue

        if not player.rect.intersects(hazard_obj.rect):
            continue

        if isinstance(hazard_obj, Lava):
            # Check if player's feet are substantially in lava
            player_feet_in_lava = player.rect.bottom() > hazard_obj.rect.top() + (player.rect.height() * 0.2)
            # Ensure some horizontal overlap too
            min_h_overlap = player.rect.width() * 0.20 # Need at least 20% horizontal overlap
            actual_h_overlap = min(player.rect.right(), hazard_obj.rect.right()) - max(player.rect.left(), hazard_obj.rect.left())

            if player_feet_in_lava and actual_h_overlap >= min_h_overlap:
                # Check for instant death property
                if hasattr(hazard_obj, 'properties') and hazard_obj.properties.get("is_instant_death", False):
                    if hasattr(player, 'insta_kill'):
                        player.insta_kill()
                        info(f"Player {player.player_id} insta-killed by lava hazard (property).")
                    else: # Fallback if insta_kill is missing
                        player.take_damage(player.max_health * 10) # Massive damage
                    damaged_this_frame_by_hazard = True
                    # Small knock-up if not already dead (or if insta_kill doesn't handle it)
                    if not player.is_dead:
                        player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75) # Pop out of lava
                        # Push away horizontally slightly
                        push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1
                        player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6)
                        player.on_ground = False; player.on_ladder = False
                    break # Processed this hazard

                # Standard lava damage (if not instant death)
                elif not damaged_this_frame_by_hazard: # Only take damage once per frame from hazards
                    if hasattr(player, 'apply_aflame_effect'): player.apply_aflame_effect()
                    lava_damage = int(getattr(C, 'LAVA_DAMAGE', 25))
                    if lava_damage > 0 and hasattr(player, 'take_damage'):
                        player.take_damage(lava_damage)
                    damaged_this_frame_by_hazard = True

                    # Apply knockback from lava
                    if not player.is_dead: # Don't apply knockback if damage killed player
                        player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75) # Pop out of lava
                        # Push away horizontally slightly
                        push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1
                        player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6)
                        player.on_ground = False; player.on_ladder = False
                    break # Processed this hazard

        if damaged_this_frame_by_hazard:
            break # Player took damage from a hazard, no need to check others this frame

#################### END OF FILE: player/player_collision_handler.py ####################