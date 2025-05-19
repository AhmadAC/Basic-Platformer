# enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy physics, movement, and collisions for PySide6.
Aflame enemies can ignite other characters.
"""
# version 2.0.0 (PySide6 Refactor)

from typing import List, Any, Optional, TYPE_CHECKING # Added Optional and TYPE_CHECKING

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF # For geometry

# Game imports
import constants as C
from tiles import Lava # Lava class now uses QRectF

# from enemy import Enemy as EnemyClass_TYPE # For isinstance, type hinting # <--- REMOVE THIS LINE (Original line 23)

if TYPE_CHECKING:
    from enemy import Enemy as EnemyClass_TYPE # For isinstance, type hinting # <--- ADD THIS LINE

try:
    from enemy_ai_handler import set_enemy_new_patrol_target # Already refactored
except ImportError:
    def set_enemy_new_patrol_target(enemy):
        print(f"WARNING ENEMY_PHYSICS: enemy_ai_handler.set_enemy_new_patrol_target not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_PHYSICS_HANDLER: logger.py not found. Falling back to print statements for logging.")
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
    _start_time_enemy_phys = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_phys) * 1000)

# --- Internal Helper Functions for Collision ---

# If EnemyClass_TYPE was used for type hinting in function signatures, change to string literal 'Enemy'.
# Example: def _check_enemy_platform_collisions(enemy: 'EnemyClass_TYPE', ...)
# However, the provided signatures don't use it, so this is not strictly necessary for them.

def _check_enemy_platform_collisions(enemy, direction: str, platforms_list: List[Any]):
    """
    Handles collisions between the enemy and solid platforms.
    Assumes enemy.rect, platform.rect are QRectF.
    Assumes enemy.vel, enemy.pos are QPointF.
    """
    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not enemy.rect.intersects(platform_obj.rect):
            continue

        if direction == 'x':
            original_vel_x = enemy.vel.x()
            if enemy.vel.x() > 0: enemy.rect.moveRight(platform_obj.rect.left())
            elif enemy.vel.x() < 0: enemy.rect.moveLeft(platform_obj.rect.right())
            enemy.vel.setX(0.0)
            if enemy.ai_state == 'patrolling' and abs(original_vel_x) > 0.1:
                if (abs(enemy.rect.right() - platform_obj.rect.left()) < 2 or \
                    abs(enemy.rect.left() - platform_obj.rect.right()) < 2):
                    set_enemy_new_patrol_target(enemy)
        elif direction == 'y':
            if enemy.vel.y() > 0: 
                if enemy.rect.bottom() > platform_obj.rect.top() and \
                   (enemy.pos.y() - enemy.vel.y()) <= platform_obj.rect.top() + 1: 
                     enemy.rect.moveBottom(platform_obj.rect.top())
                     enemy.on_ground = True
                     enemy.vel.setY(0.0)
            elif enemy.vel.y() < 0: 
                if hasattr(enemy, 'standard_height') and \
                   enemy.rect.top() < platform_obj.rect.bottom() and \
                   ((enemy.pos.y() - enemy.standard_height) - enemy.vel.y()) >= platform_obj.rect.bottom() - 1: 
                     enemy.rect.moveTop(platform_obj.rect.bottom())
                     enemy.vel.setY(0.0)
        
        if direction == 'x': enemy.pos.setX(enemy.rect.center().x())
        else: enemy.pos.setY(enemy.rect.bottom())


def _check_enemy_character_collision(enemy, direction: str, character_list: List[Any]) -> bool:
    """
    Handles collisions between the enemy and other characters.
    Returns True if a collision occurred.
    """
    collision_occurred = False
    for other_char in character_list:
        if other_char is enemy or not hasattr(other_char, 'rect') or not hasattr(other_char, 'alive') or not other_char.alive():
            continue
        
        if not (hasattr(other_char, '_valid_init') and other_char._valid_init and \
                hasattr(other_char, 'is_dead') and \
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False))):
            continue

        if enemy.rect.intersects(other_char.rect):
            collision_occurred = True
            is_other_petrified = getattr(other_char, 'is_petrified', False)
            is_other_aflame = getattr(other_char, 'is_aflame', False) or getattr(other_char, 'is_deflaming', False)
            is_other_frozen = getattr(other_char, 'is_frozen', False) or getattr(other_char, 'is_defrosting', False)

            if enemy.is_aflame and hasattr(other_char, 'apply_aflame_effect') and \
               not is_other_aflame and not is_other_frozen and \
               not enemy.has_ignited_another_enemy_this_cycle and not is_other_petrified:
                
                other_char_id_log = getattr(other_char, 'enemy_id', getattr(other_char, 'player_id', 'UnknownChar'))
                debug(f"Enemy {enemy.enemy_id} (aflame) touched Character {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                enemy.has_ignited_another_enemy_this_cycle = True 
                continue 

            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            if direction == 'x':
                push_dir_self = -1 if enemy.rect.center().x() < other_char.rect.center().x() else 1
                if push_dir_self == -1: enemy.rect.moveRight(other_char.rect.left())
                else: enemy.rect.moveLeft(other_char.rect.right())
                enemy.vel.setX(push_dir_self * bounce_vel)

                if not is_other_petrified: 
                    can_push_other = not (
                        (hasattr(other_char, 'is_attacking') and other_char.is_attacking) or
                        is_other_aflame or is_other_frozen or
                        (hasattr(other_char, 'is_dashing') and other_char.is_dashing) or
                        (hasattr(other_char, 'is_rolling') and other_char.is_rolling)
                    )
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other: # Check setX
                        other_char.vel.setX(-push_dir_self * bounce_vel)
                    if hasattr(other_char, 'pos') and hasattr(other_char.pos, 'setX') and can_push_other: # Check setX
                        other_char.pos.setX(other_char.pos.x() + (-push_dir_self * 1.5))
                        if hasattr(other_char, '_update_rect_from_image_and_pos'): other_char._update_rect_from_image_and_pos()
                        elif hasattr(other_char.rect, 'moveCenter'): other_char.rect.moveCenter(QPointF(other_char.pos.x(), other_char.rect.center().y()))


                enemy.pos.setX(enemy.rect.center().x())
            elif direction == 'y': 
                if enemy.vel.y() > 0 and enemy.rect.bottom() > other_char.rect.top() and \
                   enemy.rect.center().y() < other_char.rect.center().y():
                    enemy.rect.moveBottom(other_char.rect.top())
                    enemy.on_ground = True; enemy.vel.setY(0.0)
                elif enemy.vel.y() < 0 and enemy.rect.top() < other_char.rect.bottom() and \
                     enemy.rect.center().y() > other_char.rect.center().y():
                    enemy.rect.moveTop(other_char.rect.bottom())
                    enemy.vel.setY(0.0)
                enemy.pos.setY(enemy.rect.bottom())
    return collision_occurred


def _check_enemy_hazard_collisions(enemy, hazards_list: List[Any]):
    current_time_ms = get_current_ticks()
    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       (enemy.is_taking_hit and current_time_ms - enemy.hit_timer < enemy.hit_cooldown) or \
       enemy.is_petrified or enemy.is_frozen:
        return

    damage_taken_this_frame = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect'): continue

        if isinstance(hazard_obj, Lava) and enemy.rect.intersects(hazard_obj.rect):
            if not damage_taken_this_frame:
                if hasattr(enemy, 'apply_aflame_effect'): enemy.apply_aflame_effect()
                if getattr(C, 'LAVA_DAMAGE', 25) > 0 and hasattr(enemy, 'take_damage'):
                    enemy.take_damage(getattr(C, 'LAVA_DAMAGE', 25))
                damage_taken_this_frame = True
                if not enemy.is_dead: 
                    enemy.vel.setY(getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.3)
                    push_dir = 1 if enemy.rect.center().x() < hazard_obj.rect.center().x() else -1
                    enemy.vel.setX(-push_dir * 4.0)
                    enemy.on_ground = False 
                break 
        if damage_taken_this_frame: break 


def update_enemy_physics_and_collisions(enemy, dt_sec: float, platforms_list: List[Any],
                                        hazards_list: List[Any], all_other_characters_list: List[Any]):
    if not enemy._valid_init or not enemy.alive() or enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        if enemy.is_dead and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill() 
        return

    enemy.vel.setY(enemy.vel.y() + enemy.acc.y()) 

    enemy_friction = float(getattr(C, 'ENEMY_FRICTION', -0.12))
    current_speed_limit = float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0))
    if enemy.is_aflame: current_speed_limit *= float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.0))
    elif enemy.is_deflaming: current_speed_limit *= float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.0))
    
    terminal_velocity = float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))

    enemy.vel.setX(enemy.vel.x() + enemy.acc.x()) 

    if enemy.on_ground and enemy.acc.x() == 0: 
        friction_force = enemy.vel.x() * enemy_friction 
        if abs(enemy.vel.x()) > 0.1: enemy.vel.setX(enemy.vel.x() + friction_force)
        else: enemy.vel.setX(0.0)

    enemy.vel.setX(max(-current_speed_limit, min(current_speed_limit, enemy.vel.x())))
    enemy.vel.setY(min(enemy.vel.y(), terminal_velocity))

    enemy.on_ground = False 

    enemy.pos.setX(enemy.pos.x() + enemy.vel.x())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'x', platforms_list)
    collided_x_char = _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    if hasattr(enemy, 'rect'): enemy.pos.setX(enemy.rect.center().x())


    enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'y', platforms_list)
    if not collided_x_char: 
        _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    if hasattr(enemy, 'rect'): enemy.pos.setY(enemy.rect.bottom())

    _check_enemy_hazard_collisions(enemy, hazards_list)

    if hasattr(enemy, 'rect'):
        enemy.pos = QPointF(enemy.rect.center().x(), enemy.rect.bottom())