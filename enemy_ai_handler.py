# enemy_ai_handler.py
# -*- coding: utf-8 -*-
"""
Handles AI logic for enemies using PySide6 types.
MODIFIED: Passes current_time_ms to set_enemy_state.
MODIFIED: Simplifies aflame/deflame AI state checks, relying more on enemy_status_effects for transitions.
MODIFIED: Default attack range/detection and accel from C constants, not hardcoded.
MODIFIED: Removed direct setting of enemy.attack_type (int) as Knight uses string keys.
          The set_enemy_state with an attack key (e.g., 'attack1') should handle it.
"""
# version 2.0.4 (Standardized constants usage, attack_type handling refined)

import random
import math
import time # For monotonic timer
from typing import Optional, Any # Added Any

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C

# Logger
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_AI_HANDLER: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

# Ensure set_enemy_state is imported
try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    critical("ENEMY_AI_HANDLER: Failed to import set_enemy_state from enemy_state_handler.")
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
        patrol_direction = 1 if random.random() > 0.5 else -1
        enemy.patrol_target_x = current_x + patrol_direction * float(getattr(C, 'ENEMY_PATROL_DIST', 150.0))
    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        enemy.patrol_target_x = current_x

def enemy_ai_update(enemy: Any, players_list_for_ai: list):
    # This function is now primarily for generic enemies.
    # EnemyKnight will use its own _knight_ai_update method.
    if enemy.__class__.__name__ == 'EnemyKnight':
        # Knight handles its own AI via its update method calling _knight_ai_update
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
    enemy_attack_range = getattr(enemy, 'attack_range', float(getattr(C, 'ENEMY_ATTACK_RANGE', 60.0)))
    enemy_detection_range = getattr(enemy, 'detection_range', float(getattr(C, 'ENEMY_DETECTION_RANGE', 200.0)))
    # Generic enemy acceleration, might be overridden by properties if enemy.base_speed is used to derive it
    enemy_standard_acceleration = getattr(C, 'ENEMY_ACCEL', 0.4) 

    vertical_distance_to_player = float('inf')
    enemy_rect_height = enemy.rect.height() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'height') else getattr(C,'TILE_SIZE', 40.0) * 1.5
    if closest_target_player and hasattr(closest_target_player, 'rect') and hasattr(closest_target_player.rect, 'center'):
        vertical_distance_to_player = abs(closest_target_player.rect.center().y() - enemy.rect.center().y())

    has_vertical_los = vertical_distance_to_player < enemy_rect_height * 1.0
    is_player_in_attack_range = distance_to_target_player < enemy_attack_range and has_vertical_los
    is_player_in_detection_range = distance_to_target_player < enemy_detection_range and has_vertical_los

    # Aflame/Deflame movement logic (transitions handled by status_effects)
    if hasattr(enemy, 'is_aflame') and enemy.is_aflame:
        # ... (aflame logic as before) ...
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
            current_accel_x = enemy_standard_acceleration * 0.7 * aflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(current_accel_x)
        return
    elif hasattr(enemy, 'is_deflaming') and enemy.is_deflaming:
        # ... (deflame logic as before) ...
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
        # Generic enemy attack duration might be from EnemyBase or properties
        # Knight's attack_duration is set by its state handler from its attack_duration_map
        current_attack_duration = getattr(enemy, 'attack_duration', getattr(C, 'ENEMY_ATTACK_STATE_DURATION', 500))
        if not (hasattr(enemy, 'attack_timer')): # Safety check
            enemy.is_attacking = False; setattr(enemy, 'attack_type', 0) # Use 0 for generic attack type
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: Missing timer. Failsafe.", current_time_ms); return
        if current_time_ms - enemy.attack_timer >= current_attack_duration:
            enemy.is_attacking = False
            setattr(enemy, 'attack_type', 0) # Reset generic attack type
            enemy.attack_cooldown_timer = current_time_ms
            enemy.post_attack_pause_timer = current_time_ms + post_attack_pause_duration
            set_enemy_state(enemy, 'idle', current_time_ms)
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: Finished. Transition to idle.", current_time_ms); return
        else:
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0) # No movement during attack
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
        if enemy.state not in ['run', 'idle']: set_enemy_state(enemy, 'idle', current_time_ms) # Start patrol idle
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
        # For generic enemy, attack_type might be an int (e.g., 1 for standard attack)
        # This is set by set_enemy_state if new_state starts with 'attack'
        # Or could be set explicitly here if needed: setattr(enemy, 'attack_type', 1)

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