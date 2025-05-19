# enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy physics, movement, and collisions for PySide6.
Aflame enemies can ignite other characters.
"""
# version 2.0.1 

import time # For monotonic timer
from typing import List, Any, Optional, TYPE_CHECKING

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C
from tiles import Lava # Assumed Qt-based

if TYPE_CHECKING:
    from enemy import Enemy as EnemyClass_TYPE # For isinstance, type hinting

try:
    from enemy_ai_handler import set_enemy_new_patrol_target
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

# --- Monotonic Timer ---
_start_time_enemy_phys_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_phys_monotonic) * 1000)
# --- End Monotonic Timer ---


def _check_enemy_platform_collisions(enemy: 'EnemyClass_TYPE', direction: str, platforms_list: List[Any]):
    if not (hasattr(enemy, 'rect') and hasattr(enemy, 'vel') and hasattr(enemy, 'pos')):
        return # Cannot perform collision without essential attributes

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or \
           not enemy.rect.intersects(platform_obj.rect):
            continue

        if direction == 'x':
            original_vel_x = enemy.vel.x()
            if enemy.vel.x() > 0: enemy.rect.moveRight(platform_obj.rect.left())
            elif enemy.vel.x() < 0: enemy.rect.moveLeft(platform_obj.rect.right())
            enemy.vel.setX(0.0)
            # Check ai_state safely
            if getattr(enemy, 'ai_state', None) == 'patrolling' and abs(original_vel_x) > 0.1:
                # Check if enemy actually bumped into a wall side clearly
                if (abs(enemy.rect.right() - platform_obj.rect.left()) < 2 or
                    abs(enemy.rect.left() - platform_obj.rect.right()) < 2):
                    set_enemy_new_patrol_target(enemy) # This function should handle if enemy can't patrol
        elif direction == 'y':
            if enemy.vel.y() > 0: # Moving down
                # Check if enemy was above or at the same level as platform top in previous frame state
                if enemy.rect.bottom() > platform_obj.rect.top() and \
                   (enemy.pos.y() - enemy.vel.y()) <= platform_obj.rect.top() + 1: # Approximation of previous bottom
                     enemy.rect.moveBottom(platform_obj.rect.top())
                     enemy.on_ground = True
                     enemy.vel.setY(0.0)
            elif enemy.vel.y() < 0: # Moving up
                standard_height = getattr(enemy, 'standard_height', enemy.rect.height()) # Use actual height if standard_height missing
                if enemy.rect.top() < platform_obj.rect.bottom() and \
                   ((enemy.pos.y() - standard_height) - enemy.vel.y()) >= platform_obj.rect.bottom() - 1: # Approx prev top
                     enemy.rect.moveTop(platform_obj.rect.bottom())
                     enemy.vel.setY(0.0)
        
        # Sync pos from rect after collision resolution
        if direction == 'x' and hasattr(enemy.pos, 'setX') and hasattr(enemy.rect, 'center'):
            enemy.pos.setX(enemy.rect.center().x())
        elif direction == 'y' and hasattr(enemy.pos, 'setY') and hasattr(enemy.rect, 'bottom'):
            enemy.pos.setY(enemy.rect.bottom())


def _check_enemy_character_collision(enemy: 'EnemyClass_TYPE', direction: str, character_list: List[Any]) -> bool:
    collision_occurred = False
    if not (hasattr(enemy, 'rect') and hasattr(enemy, 'vel') and hasattr(enemy, 'pos')):
        return False

    for other_char in character_list:
        if other_char is enemy or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()):
            continue
        
        # Ensure other_char has necessary attributes for checks
        if not (hasattr(other_char, '_valid_init') and other_char._valid_init and
                hasattr(other_char, 'is_dead') and
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False))):
            continue

        if enemy.rect.intersects(other_char.rect):
            collision_occurred = True
            is_other_petrified = getattr(other_char, 'is_petrified', False)
            is_other_aflame = getattr(other_char, 'is_aflame', False) or getattr(other_char, 'is_deflaming', False)
            is_other_frozen = getattr(other_char, 'is_frozen', False) or getattr(other_char, 'is_defrosting', False)

            if getattr(enemy, 'is_aflame', False) and hasattr(other_char, 'apply_aflame_effect') and \
               not is_other_aflame and not is_other_frozen and \
               not getattr(enemy, 'has_ignited_another_enemy_this_cycle', True) and not is_other_petrified:
                
                other_char_id_log = getattr(other_char, 'enemy_id', getattr(other_char, 'player_id', 'UnknownChar'))
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (aflame) touched Character {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                enemy.has_ignited_another_enemy_this_cycle = True 
                continue # Collision handled by ignition, no physical push for this specific interaction

            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            if direction == 'x':
                push_dir_self = -1 if enemy.rect.center().x() < other_char.rect.center().x() else 1
                if push_dir_self == -1: enemy.rect.moveRight(other_char.rect.left())
                else: enemy.rect.moveLeft(other_char.rect.right())
                if hasattr(enemy.vel, 'setX'): enemy.vel.setX(push_dir_self * bounce_vel)

                if not is_other_petrified: 
                    can_push_other = not (
                        (hasattr(other_char, 'is_attacking') and other_char.is_attacking) or
                        is_other_aflame or is_other_frozen or
                        (hasattr(other_char, 'is_dashing') and other_char.is_dashing) or
                        (hasattr(other_char, 'is_rolling') and other_char.is_rolling)
                    )
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other:
                        other_char.vel.setX(-push_dir_self * bounce_vel)
                    if hasattr(other_char, 'pos') and hasattr(other_char.pos, 'setX') and can_push_other:
                        other_char.pos.setX(other_char.pos.x() + (-push_dir_self * 1.5)) # Small displacement
                        if hasattr(other_char, '_update_rect_from_image_and_pos'): other_char._update_rect_from_image_and_pos()
                        elif hasattr(other_char.rect, 'center') and hasattr(other_char.rect.center, 'y'): # Check QPointF structure
                            other_char.rect.moveCenter(QPointF(other_char.pos.x(), other_char.rect.center().y()))

                if hasattr(enemy.pos, 'setX') and hasattr(enemy.rect, 'center'): enemy.pos.setX(enemy.rect.center().x())
            elif direction == 'y': 
                if enemy.vel.y() > 0 and enemy.rect.bottom() > other_char.rect.top() and \
                   hasattr(enemy.rect, 'center') and hasattr(other_char.rect, 'center') and \
                   enemy.rect.center().y() < other_char.rect.center().y(): # Enemy center is above other's center (landing on top)
                    enemy.rect.moveBottom(other_char.rect.top())
                    enemy.on_ground = True; enemy.vel.setY(0.0)
                elif enemy.vel.y() < 0 and enemy.rect.top() < other_char.rect.bottom() and \
                     hasattr(enemy.rect, 'center') and hasattr(other_char.rect, 'center') and \
                     enemy.rect.center().y() > other_char.rect.center().y(): # Enemy center is below other's center (hitting from below)
                    enemy.rect.moveTop(other_char.rect.bottom())
                    enemy.vel.setY(0.0)
                if hasattr(enemy.pos, 'setY') and hasattr(enemy.rect, 'bottom'): enemy.pos.setY(enemy.rect.bottom())
    return collision_occurred


def _check_enemy_hazard_collisions(enemy: 'EnemyClass_TYPE', hazards_list: List[Any]):
    current_time_ms = get_current_ticks_monotonic() # Use monotonic timer
    if not getattr(enemy, '_valid_init', False) or getattr(enemy, 'is_dead', True) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       (getattr(enemy, 'is_taking_hit', False) and \
        current_time_ms - getattr(enemy, 'hit_timer', 0) < getattr(enemy, 'hit_cooldown', 500)) or \
       getattr(enemy, 'is_petrified', False) or getattr(enemy, 'is_frozen', False):
        return

    damage_taken_this_frame = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF): continue
        if not (hasattr(enemy, 'rect') and enemy.rect.intersects(hazard_obj.rect)): continue

        if isinstance(hazard_obj, Lava):
            if not damage_taken_this_frame:
                if hasattr(enemy, 'apply_aflame_effect'): enemy.apply_aflame_effect()
                lava_damage = getattr(C, 'LAVA_DAMAGE', 25)
                if lava_damage > 0 and hasattr(enemy, 'take_damage'):
                    enemy.take_damage(lava_damage)
                damage_taken_this_frame = True
                if not getattr(enemy, 'is_dead', False): # If still alive after lava damage
                    if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX') and hasattr(enemy.vel, 'setY'):
                        enemy.vel.setY(getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.3) # Lava bounce
                        push_dir = 1 if (hasattr(enemy.rect,'center') and enemy.rect.center().x() < hazard_obj.rect.center().x()) else -1
                        enemy.vel.setX(-push_dir * 4.0)
                    enemy.on_ground = False 
                break 
        if damage_taken_this_frame: break 


def update_enemy_physics_and_collisions(enemy: 'EnemyClass_TYPE', dt_sec: float, platforms_list: List[Any],
                                        hazards_list: List[Any], all_other_characters_list: List[Any]):
    if not getattr(enemy, '_valid_init', False) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False):
        # If dead but somehow still in list and "alive", try to kill
        if getattr(enemy, 'is_dead', False) and (hasattr(enemy, 'alive') and enemy.alive()) and hasattr(enemy, 'kill'):
            enemy.kill() 
        return

    # Ensure vel and acc are QPointF and have necessary methods
    if not (hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and
            hasattr(enemy, 'acc') and isinstance(enemy.acc, QPointF) and
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing or invalid vel/acc/pos for physics update.")
        return

    enemy.vel.setY(enemy.vel.y() + enemy.acc.y())

    enemy_friction = float(getattr(C, 'ENEMY_FRICTION', -0.12))
    current_speed_limit = float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0))
    if getattr(enemy, 'is_aflame', False):
        current_speed_limit *= float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.0))
    elif getattr(enemy, 'is_deflaming', False):
        current_speed_limit *= float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.0))
    
    terminal_velocity = float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))

    enemy.vel.setX(enemy.vel.x() + enemy.acc.x())

    if getattr(enemy, 'on_ground', False) and abs(enemy.acc.x()) < 1e-6: # If no horizontal acceleration input
        friction_force = enemy.vel.x() * enemy_friction
        if abs(enemy.vel.x()) > 0.1: enemy.vel.setX(enemy.vel.x() + friction_force)
        else: enemy.vel.setX(0.0)

    enemy.vel.setX(max(-current_speed_limit, min(current_speed_limit, enemy.vel.x())))
    enemy.vel.setY(min(enemy.vel.y(), terminal_velocity))

    enemy.on_ground = False # Reset before collision checks

    # Horizontal movement and collision
    enemy.pos.setX(enemy.pos.x() + enemy.vel.x())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'x', platforms_list)
    collided_x_char = _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'center'): enemy.pos.setX(enemy.rect.center().x()) # Sync pos after potential collision adjustment

    # Vertical movement and collision
    enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'y', platforms_list)
    if not collided_x_char: # Only check vertical char collision if not already pushed horizontally
        _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'bottom'): enemy.pos.setY(enemy.rect.bottom()) # Sync pos after potential collision adjustment

    _check_enemy_hazard_collisions(enemy, hazards_list)

    # Final position sync from rect (midbottom is common anchor)
    if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'center') and hasattr(enemy.rect, 'bottom'):
        enemy.pos.setX(enemy.rect.center().x())
        enemy.pos.setY(enemy.rect.bottom())