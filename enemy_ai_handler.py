#################### START OF FILE: enemy_ai_handler.py ####################

# enemy_ai_handler.py
# -*- coding: utf-8 -*-
"""
Handles AI logic for enemies using PySide6 types.
"""
# version 2.0.0 (PySide6 Refactor)

import random
import math
from typing import Optional # For Optional type hint

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF # For geometry types

# Game imports
import constants as C

# Logger
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_AI_HANDLER: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_ai = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_ai) * 1000)


ENABLE_ENEMY_AI_DEBUG_PRINTS = False

def log_enemy_state(enemy, message: str, current_time_ms: int):
    if ENABLE_ENEMY_AI_DEBUG_PRINTS:
        enemy_id_str = str(getattr(enemy, 'enemy_id', 'N/A'))
        pos_x_str = f"{enemy.pos.x():.2f}" if hasattr(enemy, 'pos') and enemy.pos else "N/A"
        pos_y_str = f"{enemy.pos.y():.2f}" if hasattr(enemy, 'pos') and enemy.pos else "N/A"

        print(f"[{current_time_ms/1000:.2f}s] Enemy AI (ID: {enemy_id_str}): {message}")
        print(f"    Flags: is_aflame={getattr(enemy, 'is_aflame', 'N/A')}, "
              f"is_frozen={getattr(enemy, 'is_frozen', 'N/A')}, "
              f"is_attacking={getattr(enemy, 'is_attacking', 'N/A')}")
        print(f"    State: current='{getattr(enemy, 'state', 'N/A')}', "
              f"ai_state='{getattr(enemy, 'ai_state', 'N/A')}'")
        print(f"    Pos:({pos_x_str}, {pos_y_str})")


def set_enemy_new_patrol_target(enemy):
    """
    Sets a new patrol target X-coordinate for the enemy instance using QRectF/QPointF.
    """
    current_x = 0.0
    if hasattr(enemy, 'pos') and enemy.pos:
        current_x = enemy.pos.x()
    elif hasattr(enemy, 'rect') and enemy.rect: # Fallback to rect center if pos not fully set
        current_x = enemy.rect.center().x()

    if hasattr(enemy, 'patrol_area') and enemy.patrol_area and isinstance(enemy.patrol_area, QRectF):
         # Ensure enemy rect width is available and valid for patrol bounds calculation
         enemy_width = enemy.rect.width() if hasattr(enemy, 'rect') and enemy.rect else getattr(C, 'TILE_SIZE', 40.0)
         
         min_x_patrol = enemy.patrol_area.left() + enemy_width / 2.0
         max_x_patrol = enemy.patrol_area.right() - enemy_width / 2.0
         
         if min_x_patrol < max_x_patrol: 
             enemy.patrol_target_x = random.uniform(min_x_patrol, max_x_patrol)
         else: # If area is too small, target center
             enemy.patrol_target_x = enemy.patrol_area.center().x()
    else: 
        patrol_direction = 1 if random.random() > 0.5 else -1
        enemy.patrol_target_x = current_x + patrol_direction * float(getattr(C, 'ENEMY_PATROL_DIST', 150.0))
    
    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        enemy.patrol_target_x = current_x


def enemy_ai_update(enemy, players_list_for_ai: list):
    """
    Updates the enemy's AI state and behavior using QRectF/QPointF.
    """
    current_time_ms = get_current_ticks()
    log_enemy_state(enemy, "Starting AI update.", current_time_ms)

    if not hasattr(enemy, '_valid_init') or not enemy._valid_init or \
       (hasattr(enemy, 'is_dead') and enemy.is_dead) or not (hasattr(enemy, 'alive') and enemy.alive()):
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
        log_enemy_state(enemy, "Entity invalid, dead, or not alive. No AI.", current_time_ms)
        return

    if (hasattr(enemy, 'is_frozen') and enemy.is_frozen) or \
       (hasattr(enemy, 'is_defrosting') and enemy.is_defrosting):
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
        # State setting for frozen/defrost is handled by status_effects or state_handler
        log_enemy_state(enemy, "Entity frozen/defrosting. No AI movement.", current_time_ms)
        return

    if hasattr(enemy, 'is_taking_hit') and enemy.is_taking_hit and \
       hasattr(enemy, 'hit_timer') and hasattr(enemy, 'hit_cooldown') and \
       current_time_ms - enemy.hit_timer < enemy.hit_cooldown:
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
        log_enemy_state(enemy, "Entity in hit stun/cooldown. No AI.", current_time_ms)
        return

    closest_target_player = None
    min_squared_distance_to_player = float('inf')
    if not hasattr(enemy, 'pos') or not enemy.pos:
        log_enemy_state(enemy, "Enemy has no 'pos' attribute. Cannot detect players.", current_time_ms)
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0); return

    for player_candidate in players_list_for_ai:
        is_targetable = (
            player_candidate and hasattr(player_candidate, '_valid_init') and player_candidate._valid_init and
            hasattr(player_candidate, 'pos') and player_candidate.pos and
            hasattr(player_candidate, 'rect') and player_candidate.rect and
            hasattr(player_candidate, 'alive') and player_candidate.alive() and
            not getattr(player_candidate, 'is_dead', True) and
            not getattr(player_candidate, 'is_petrified', False)
        )
        if is_targetable:
            dx = player_candidate.pos.x() - enemy.pos.x()
            dy = player_candidate.pos.y() - enemy.pos.y() # Using y() of pos (midbottom)
            squared_dist = dx*dx + dy*dy
            if squared_dist < min_squared_distance_to_player:
                min_squared_distance_to_player = squared_dist
                closest_target_player = player_candidate

    distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')
    enemy_attack_range = float(getattr(C, 'ENEMY_ATTACK_RANGE', 60.0))
    enemy_detection_range = float(getattr(C, 'ENEMY_DETECTION_RANGE', 200.0))
    enemy_standard_acceleration = float(getattr(C, 'ENEMY_ACCEL', 0.4))
    
    vertical_distance_to_player = float('inf')
    enemy_rect_height = enemy.rect.height() if hasattr(enemy, 'rect') and enemy.rect else getattr(C,'TILE_SIZE', 40.0) * 1.5
    if closest_target_player and hasattr(closest_target_player, 'rect') and closest_target_player.rect:
        vertical_distance_to_player = abs(closest_target_player.rect.center().y() - enemy.rect.center().y())
    
    has_vertical_los = vertical_distance_to_player < enemy_rect_height * 1.0
    is_player_in_attack_range = distance_to_target_player < enemy_attack_range and has_vertical_los
    is_player_in_detection_range = distance_to_target_player < enemy_detection_range and has_vertical_los

    # Aflame/Deflame Handling
    if hasattr(enemy, 'is_aflame') and enemy.is_aflame:
        log_enemy_state(enemy, "AFLAME logic active.", current_time_ms)
        if enemy.state != 'aflame': enemy.set_state('aflame') # State handler sets timer
        
        aflame_speed_mod = float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.0))
        current_accel_x = 0.0
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_aflame'
            should_face_right = (closest_target_player.pos.x() > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * aflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_aflame'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or \
               abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * 0.7 * aflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(current_accel_x)
        return
    elif hasattr(enemy, 'is_deflaming') and enemy.is_deflaming:
        log_enemy_state(enemy, "DEFLAME logic active.", current_time_ms)
        if enemy.state != 'deflame': enemy.set_state('deflame')

        deflame_speed_mod = float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.0))
        current_accel_x = 0.0
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_deflaming'
            should_face_right = (closest_target_player.pos.x() > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * deflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_deflaming'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or \
               abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x())
            current_accel_x = enemy_standard_acceleration * 0.7 * deflame_speed_mod * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(current_accel_x)
        return

    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       current_time_ms < enemy.post_attack_pause_timer:
        if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
        if enemy.state != 'idle': enemy.set_state('idle')
        log_enemy_state(enemy, "Post-attack pause.", current_time_ms); return

    if hasattr(enemy, 'is_attacking') and enemy.is_attacking:
        if not (hasattr(enemy, 'attack_timer') and hasattr(enemy, 'attack_duration')):
            enemy.is_attacking = False; enemy.acc.setX(0.0) if hasattr(enemy, 'acc') and enemy.acc else None
            log_enemy_state(enemy, "ATTACKING: Missing timer/duration. Failsafe.", current_time_ms); return
        if current_time_ms - enemy.attack_timer >= enemy.attack_duration:
            enemy.is_attacking = False
            if hasattr(enemy, 'attack_type'): enemy.attack_type = 0
            if hasattr(enemy, 'attack_cooldown_timer'): enemy.attack_cooldown_timer = current_time_ms
            if hasattr(enemy, 'post_attack_pause_timer') and hasattr(enemy, 'post_attack_pause_duration'):
                enemy.post_attack_pause_timer = current_time_ms + enemy.post_attack_pause_duration
            enemy.set_state('idle')
            if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: Finished. Transition to idle.", current_time_ms); return
        else:
            if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(0.0)
            log_enemy_state(enemy, "ATTACKING: In progress.", current_time_ms); return

    # Standard AI
    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None: set_enemy_new_patrol_target(enemy)

    enemy_attack_cooldown_dur = int(getattr(C, 'ENEMY_ATTACK_COOLDOWN', 1500))
    is_attack_off_cooldown = not hasattr(enemy, 'attack_cooldown_timer') or \
                             (current_time_ms - enemy.attack_cooldown_timer > enemy_attack_cooldown_dur)

    target_accel_x = 0.0
    target_facing_right = enemy.facing_right

    if not closest_target_player:
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['run', 'idle']: enemy.set_state('patrolling') # 'patrolling' often maps to 'run' visually
        if abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            if enemy.state == 'run': enemy.set_state('idle')
        target_facing_right = (enemy.patrol_target_x > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * 0.7 * (1 if target_facing_right else -1)
        if enemy.state == 'idle' and abs(target_accel_x) > 0.05 : enemy.set_state('run')
    elif is_player_in_attack_range and is_attack_off_cooldown:
        enemy.ai_state = 'attacking'
        target_facing_right = (closest_target_player.pos.x() > enemy.pos.x())
        anim_key_attack = 'attack_nm' if (enemy.animations and enemy.animations.get('attack_nm') and abs(enemy.vel.x()) < enemy_standard_acceleration * 1.5) else 'attack'
        enemy.set_state(anim_key_attack)
    elif is_player_in_detection_range:
        enemy.ai_state = 'chasing'
        target_facing_right = (closest_target_player.pos.x() > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * (1 if target_facing_right else -1)
        if enemy.state not in ['run']: enemy.set_state('run')
    else: # Player not in detection range, but exists -> patrol
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['run', 'idle']: enemy.set_state('patrolling')
        if abs(enemy.pos.x() - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            if enemy.state == 'run': enemy.set_state('idle')
        target_facing_right = (enemy.patrol_target_x > enemy.pos.x())
        target_accel_x = enemy_standard_acceleration * 0.7 * (1 if target_facing_right else -1)
        if enemy.state == 'idle' and abs(target_accel_x) > 0.05 : enemy.set_state('run')

    if hasattr(enemy, 'acc') and enemy.acc: enemy.acc.setX(target_accel_x)
    if not (hasattr(enemy, 'is_attacking') and enemy.is_attacking) and \
       enemy.facing_right != target_facing_right:
         enemy.facing_right = target_facing_right
    log_enemy_state(enemy, f"End of AI. Acc.x: {enemy.acc.x():.2f}, FacingRight: {enemy.facing_right}", current_time_ms)

#################### END OF FILE: enemy_ai_handler.py ####################