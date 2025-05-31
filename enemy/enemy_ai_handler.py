#################### START OF FILE: enemy\enemy_ai_handler.py ####################
# enemy/enemy_ai_handler.py
# -*- coding: utf-8 -*-
"""
Handles AI logic for generic enemies using PySide6 types.
EnemyKnight uses its own specific AI in enemy_knight.py.
MODIFIED: Passes current_time_ms to set_enemy_state.
MODIFIED: Simplifies aflame/deflame AI state checks, relying more on enemy_status_effects for transitions.
MODIFIED: Default attack range/detection and accel from C constants, not hardcoded.
MODIFIED: Consistent use of attack_type="none" (string) when not attacking or after an attack.
          The set_enemy_state with an attack key (e.g., 'attack' for generic enemy) should handle it.
MODIFIED: Corrected logger import path.
"""
# version 2.0.5 (Standardized attack_type="none", logger import path)

import random
import math
import time # For monotonic timer
from typing import Optional, Any

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# --- Project Root Setup ---
import os
import sys
_ENEMY_AI_HANDLER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_ENEMY_AI_HANDLER = os.path.dirname(_ENEMY_AI_HANDLER_PY_FILE_DIR) # Up one level to 'enemy'
if _PROJECT_ROOT_FOR_ENEMY_AI_HANDLER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_ENEMY_AI_HANDLER) # Add 'enemy' package's parent
_PROJECT_ROOT_GRANDPARENT = os.path.dirname(_PROJECT_ROOT_FOR_ENEMY_AI_HANDLER) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT) # Add actual project root
# --- End Project Root Setup ---

# Game imports
import main_game.constants as C

# Logger
# --- Logger Setup ---
import logging
_enemy_ai_logger_instance = logging.getLogger(__name__ + "_enemy_ai_internal_fallback")
if not _enemy_ai_logger_instance.hasHandlers():
    _handler_eai_fb = logging.StreamHandler(sys.stdout)
    _formatter_eai_fb = logging.Formatter('ENEMY_AI (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_eai_fb.setFormatter(_formatter_eai_fb)
    _enemy_ai_logger_instance.addHandler(_handler_eai_fb)
    _enemy_ai_logger_instance.setLevel(logging.DEBUG)
    _enemy_ai_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_ai_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_ai_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_ai_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_ai_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_ai_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("EnemyAIHandler: Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL ENEMY_AI_HANDLER: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_eai:
    critical(f"CRITICAL ENEMY_AI_HANDLER: Unexpected error during logger setup from main_game.logger: {e_logger_init_eai}. Using internal fallback.")
# --- End Logger Setup ---


# Ensure set_enemy_state is imported correctly (relative from within enemy package)
_ESH_AVAILABLE = True
try:
    from enemy.enemy_state_handler import set_enemy_state # Relative import
except ImportError as e_esh_import:
    critical(f"ENEMY_AI_HANDLER: Failed to import set_enemy_state from enemy.enemy_state_handler: {e_esh_import}")
    _ESH_AVAILABLE = False
    def set_enemy_state(enemy: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(enemy, 'state'): enemy.state = new_state
        warning(f"ENEMY_AI_HANDLER: Fallback set_enemy_state used for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')} to '{new_state}'")

_start_time_enemy_ai_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_ai_monotonic) * 1000)

ENABLE_ENEMY_AI_DEBUG_PRINTS = False

def log_enemy_state(enemy: Any, message: str, current_time_ms: int):
    if ENABLE_ENEMY_AI_DEBUG_PRINTS:
        enemy_id_str = str(getattr(enemy, 'enemy_id', 'N/A'))
        pos_x_str = f"{enemy.pos.x():.2f}" if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'x') else "N/A"
        pos_y_str = f"{enemy.pos.y():.2f}" if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'y') else "N/A"
        acc_x_val_for_log = getattr(getattr(enemy, 'acc', None), 'x', lambda: float('nan'))()
        acc_x_str = f"{acc_x_val_for_log:.2f}" if isinstance(acc_x_val_for_log, (int, float)) and not math.isnan(acc_x_val_for_log) else 'N/A'
        debug(f"[{current_time_ms/1000:.2f}s] Enemy AI (ID: {enemy_id_str}): {message} | "
              f"Flags: Aflame={getattr(enemy, 'is_aflame', 'N/A')}, Frozen={getattr(enemy, 'is_frozen', 'N/A')}, "
              f"Zapped={getattr(enemy, 'is_zapped', 'N/A')}, Attacking={getattr(enemy, 'is_attacking', 'N/A')} | "
              f"State: current='{getattr(enemy, 'state', 'N/A')}', ai_state='{getattr(enemy, 'ai_state', 'N/A')}' | "
              f"Pos:({pos_x_str}, {pos_y_str}) | Acc.X: {acc_x_str}")

def set_enemy_new_patrol_target(enemy: Any):
    current_x = 0.0
    if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'x'):
        current_x = enemy.pos.x()
    elif hasattr(enemy, 'rect') and hasattr(enemy.rect, 'center'):
        current_x = enemy.rect.center().x()

    if hasattr(enemy, 'patrol_area') and isinstance(enemy.patrol_area, QRectF) and not enemy.patrol_area.isNull():
         enemy_width = enemy.rect.width() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'width') else getattr(C, 'TILE_SIZE', 40.0)
         min_x_patrol = enemy.patrol_area.left() + enemy_width / 2.0
         max_x_patrol = enemy.patrol_area.right() - enemy_width / 2.0
         if min_x_patrol < max_x_patrol:
             enemy.patrol_target_x = random.uniform(min_x_patrol, max_x_patrol)
         else:
             enemy.patrol_target_x = enemy.patrol_area.center().x()
    else:
        patrol_range_from_props = float(enemy.properties.get("patrol_range_tiles", 5) * C.TILE_SIZE) if hasattr(enemy, 'properties') and isinstance(enemy.properties, dict) else float(getattr(C, 'ENEMY_PATROL_DIST', 150.0))
        patrol_direction = 1 if random.random() > 0.5 else -1
        enemy.patrol_target_x = current_x + patrol_direction * patrol_range_from_props

    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        enemy.patrol_target_x = current_x
    if ENABLE_ENEMY_AI_DEBUG_PRINTS:
        debug(f"EnemyAI (ID {getattr(enemy, 'enemy_id', 'N/A')}): New patrol target X: {enemy.patrol_target_x:.1f}")

def enemy_ai_update(enemy: Any, players_list_for_ai: list):
    # This function is now primarily for generic enemies.
    # EnemyKnight will use its own _knight_ai_update method.
    if enemy.__class__.__name__ == 'EnemyKnight':
        # Knight handles its own AI via its update method calling _knight_ai_update
        return

    if not _ESH_AVAILABLE: # Critical check if set_enemy_state is not available
        critical("ENEMY_AI_HANDLER: set_enemy_state function is not available. AI cannot function correctly.")
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        return

    current_time_ms = get_current_ticks_monotonic()
    log_enemy_state(enemy, "Starting AI update (Generic Enemy).", current_time_ms)

    if not hasattr(enemy, '_valid_init') or not enemy._valid_init or \
       (hasattr(enemy, 'is_dead') and enemy.is_dead) or not (hasattr(enemy, 'alive') and enemy.alive()):
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        return

    if hasattr(enemy, 'is_taking_hit') and enemy.is_taking_hit and \
       hasattr(enemy, 'hit_timer') and hasattr(enemy, 'hit_cooldown') and \
       current_time_ms - enemy.hit_timer < enemy.hit_cooldown:
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        log_enemy_state(enemy, "Entity in hit stun/cooldown. No AI.", current_time_ms)
        return

    closest_target_player = None
    min_squared_distance_to_player = float('inf')
    if not (hasattr(enemy, 'pos') and hasattr(enemy.pos, 'x') and hasattr(enemy.pos, 'y')):
        log_enemy_state(enemy, "Enemy 'pos' attribute or its x/y is invalid. Cannot detect players.", current_time_ms)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        return

    for player_candidate in players_list_for_ai:
        is_targetable = ( player_candidate and hasattr(player_candidate, '_valid_init') and player_candidate._valid_init and
                          hasattr(player_candidate, 'pos') and hasattr(player_candidate.pos, 'x') and hasattr(player_candidate.pos, 'y') and
                          hasattr(player_candidate, 'rect') and hasattr(player_candidate.rect, 'center') and
                          hasattr(player_candidate, 'alive') and player_candidate.alive() and not getattr(player_candidate, 'is_dead', True) and
                          not getattr(player_candidate, 'is_petrified', False) )
        if is_targetable:
            dx = player_candidate.pos.x() - enemy.pos.x(); dy = player_candidate.pos.y() - enemy.pos.y()
            squared_dist = dx*dx + dy*dy
            if squared_dist < min_squared_distance_to_player: min_squared_distance_to_player = squared_dist; closest_target_player = player_candidate

    distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')

    # Use properties if available, else constants
    enemy_properties = getattr(enemy, 'properties', {})
    enemy_attack_range = float(enemy_properties.get("attack_range_px", float(getattr(C, 'ENEMY_ATTACK_RANGE', 60.0))))
    enemy_detection_range = float(enemy_properties.get("detection_range_px", float(getattr(C, 'ENEMY_DETECTION_RANGE', 200.0))))
    enemy_base_speed = float(enemy_properties.get("move_speed", float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0)) * 50 )) # Speed is units/sec
    # Generic enemy acceleration derived from base_speed and a constant time-to-max-speed factor
    # accel = speed / time_to_reach_speed_from_rest (where time is in frames)
    # Assume time_to_reach_speed_from_rest is roughly 0.25 seconds (e.g., 15 frames at 60fps)
    time_to_max_speed_frames = 0.25 * C.FPS
    enemy_standard_acceleration = (enemy_base_speed / C.FPS) / time_to_max_speed_frames if time_to_max_speed_frames > 0 else getattr(C, 'ENEMY_ACCEL', 0.4)


    vertical_distance_to_player = float('inf')
    enemy_rect_height = enemy.rect.height() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'height') else getattr(C,'TILE_SIZE', 40.0) * 1.5
    if closest_target_player and hasattr(closest_target_player, 'rect') and hasattr(closest_target_player.rect, 'center'):
        vertical_distance_to_player = abs(closest_target_player.rect.center().y() - enemy.rect.center().y())

    has_vertical_los = vertical_distance_to_player < enemy_rect_height * 1.0
    is_player_in_attack_range = distance_to_target_player < enemy_attack_range and has_vertical_los
    is_player_in_detection_range = distance_to_target_player < enemy_detection_range and has_vertical_los

    # Aflame/Deflame movement logic (transitions handled by status_effects)
    if hasattr(enemy, 'is_aflame') and enemy.is_aflame:
        log_enemy_state(enemy, "AFLAME movement logic active.", current_time_ms)
        aflame_speed_mod = float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.3))
        current_accel_x = 0.0
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_aflame'
            should_face_right = (closest_target_player.pos.x() > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * aflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_aflame'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * 0.7 * aflame_speed_mod * (1 if should_face_right else -1) # Slower patrol when aflame
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(current_accel_x)
        return # Aflame movement overrides other AI for this tick
    elif hasattr(enemy, 'is_deflaming') and enemy.is_deflaming:
        log_enemy_state(enemy, "DEFLAME movement logic active.", current_time_ms)
        deflame_speed_mod = float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.2))
        current_accel_x = 0.0
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_deflaming'
            should_face_right = (closest_target_player.pos.x() > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * deflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_deflaming'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * 0.7 * deflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(current_accel_x)
        return

    # Post-attack pause
    post_attack_pause_duration = getattr(enemy, 'post_attack_pause_duration', getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200))
    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       current_time_ms < enemy.post_attack_pause_timer:
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        if enemy.state != 'idle': set_enemy_state(enemy, 'idle', current_time_ms)
        log_enemy_state(enemy, "Post-attack pause.", current_time_ms); return

    # Attack completion
    if hasattr(enemy, 'is_attacking') and enemy.is_attacking:
        current_attack_duration = getattr(enemy, 'attack_duration', getattr(C, 'ENEMY_ATTACK_STATE_DURATION', 500))
        if not (hasattr(enemy, 'attack_timer')):
            enemy.is_attacking = False; setattr(enemy, 'attack_type', "none") # Reset to "none" string
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: Missing timer. Failsafe.", current_time_ms); return
        if current_time_ms - enemy.attack_timer >= current_attack_duration:
            enemy.is_attacking = False
            setattr(enemy, 'attack_type', "none") # Reset to "none" string
            enemy.attack_cooldown_timer = current_time_ms
            enemy.post_attack_pause_timer = current_time_ms + post_attack_pause_duration
            set_enemy_state(enemy, 'idle', current_time_ms)
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: Finished. Transition to idle.", current_time_ms); return
        else:
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: In progress.", current_time_ms); return

    # Initialize patrol target if needed
    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        set_enemy_new_patrol_target(enemy)

    enemy_attack_cooldown_dur = getattr(enemy, 'attack_cooldown_duration', int(getattr(C, 'ENEMY_ATTACK_COOLDOWN', 1500)))
    is_attack_off_cooldown = not hasattr(enemy, 'attack_cooldown_timer') or \
                             (current_time_ms - enemy.attack_cooldown_timer > enemy_attack_cooldown_dur)

    target_accel_x = 0.0
    target_facing_right = enemy.facing_right

    # Generic Enemy AI State Machine
    if not closest_target_player: # Patrol if no player
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['run', 'idle']: set_enemy_state(enemy, 'idle', current_time_ms)
        if abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            if enemy.state == 'run': set_enemy_state(enemy, 'idle', current_time_ms)
        target_facing_right = (enemy.patrol_target_x > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * 0.7 * (1 if target_facing_right else -1)
        if enemy.state == 'idle' and abs(target_accel_x) > 0.05: set_enemy_state(enemy, 'run', current_time_ms)

    elif is_player_in_attack_range and is_attack_off_cooldown: # Attack
        enemy.ai_state = 'attacking'
        target_facing_right = (closest_target_player.pos.x() > enemy.pos.x())
        # Generic enemy uses 'attack' or 'attack_nm'
        attack_anim_key = 'attack_nm' if (hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('attack_nm') and \
                                         hasattr(enemy, 'vel') and hasattr(enemy.vel, 'x') and abs(enemy.vel.x()) < enemy_standard_acceleration * 1.5) \
                                      else 'attack'
        set_enemy_state(enemy, attack_anim_key, current_time_ms)
        # attack_type for generic enemy will be set to "attack" (or similar) by set_enemy_state if the new_state starts with "attack"
        # If set_enemy_state doesn't handle this, you might need:
        # setattr(enemy, 'attack_type', "standard_attack") # or a specific string key

    elif is_player_in_detection_range: # Chase
        enemy.ai_state = 'chasing'
        target_facing_right = (closest_target_player.pos.x() > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * (1 if target_facing_right else -1)
        if enemy.state not in ['run']: set_enemy_state(enemy, 'run', current_time_ms)

    else: # Player out of range -> patrol
        enemy.ai_state = 'patrolling_lost_target'
        if enemy.state not in ['run', 'idle']: set_enemy_state(enemy, 'idle', current_time_ms)
        if abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            if enemy.state == 'run': set_enemy_state(enemy, 'idle', current_time_ms)
        target_facing_right = (enemy.patrol_target_x > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * 0.7 * (1 if target_facing_right else -1)
        if enemy.state == 'idle' and abs(target_accel_x) > 0.05: set_enemy_state(enemy, 'run', current_time_ms)

    # Apply final acceleration and facing
    if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'):
        enemy.acc.setX(target_accel_x)
    if not (hasattr(enemy, 'is_attacking') and enemy.is_attacking) and \
       enemy.facing_right != target_facing_right:
         enemy.facing_right = target_facing_right

    log_enemy_state(enemy, "End of AI (Generic Enemy).", current_time_ms)

#################### END OF FILE: enemy/enemy_ai_handler.py ####################