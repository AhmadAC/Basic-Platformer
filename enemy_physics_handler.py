# enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy physics, movement, and collisions for PySide6.
Aflame enemies can ignite other characters.
"""
# version 2.0.2 (Refined collision checks and position syncing)

import time 
from typing import List, Any, Optional, TYPE_CHECKING

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C
from tiles import Lava 

if TYPE_CHECKING:
    from enemy import Enemy as EnemyClass_TYPE 

try:
    from enemy_ai_handler import set_enemy_new_patrol_target
except ImportError:
    def set_enemy_new_patrol_target(enemy): # Fallback
        enemy_id_log = getattr(enemy, 'enemy_id', 'N/A')
        print(f"WARNING ENEMY_PHYSICS: enemy_ai_handler.set_enemy_new_patrol_target not found for Enemy ID {enemy_id_log}")

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_PHYSICS_HANDLER: logger.py not found. Falling back to print statements for logging.")
    # Define dummy loggers
    def info(msg, *args, **kwargs): print(f"INFO: {msg}", *args)
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}", *args)
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}", *args)
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}", *args)
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}", *args)

# --- Monotonic Timer ---
_start_time_enemy_phys_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_phys_monotonic) * 1000)
# --- End Monotonic Timer ---


def _check_enemy_platform_collisions(enemy: 'EnemyClass_TYPE', direction: str, platforms_list: List[Any]):
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and \
            hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and \
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF)):
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing essential attributes for platform collision. Skipping.")
        return 

    # Store rect before this axis's potential move for accurate "was clear" check
    rect_before_resolution_this_axis = QRectF(enemy.rect)

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF):
            warning(f"Enemy Collision: Platform object {platform_obj} missing valid rect. Skipping.")
            continue
        
        if not enemy.rect.intersects(platform_obj.rect):
            continue

        if direction == 'x':
            original_vel_x = enemy.vel.x() # Store before modifying
            if enemy.vel.x() > 0: # Moving right
                # Check if enemy was to the left of or just touching the platform's left edge
                if enemy.rect.right() > platform_obj.rect.left() and \
                   rect_before_resolution_this_axis.right() <= platform_obj.rect.left() + 1.0:
                    enemy.rect.moveRight(platform_obj.rect.left())
                    enemy.vel.setX(0.0)
            elif enemy.vel.x() < 0: # Moving left
                if enemy.rect.left() < platform_obj.rect.right() and \
                   rect_before_resolution_this_axis.left() >= platform_obj.rect.right() - 1.0:
                    enemy.rect.moveLeft(platform_obj.rect.right())
                    enemy.vel.setX(0.0)
            
            # Sync pos.x after X collision (enemy pos is midbottom)
            enemy.pos.setX(enemy.rect.center().x())
            
            # AI reaction to wall bump
            if getattr(enemy, 'ai_state', None) == 'patrolling' and abs(original_vel_x) > 0.1 and enemy.vel.x() == 0.0:
                # Check if it's a clear side collision
                if (abs(enemy.rect.right() - platform_obj.rect.left()) < 2 and original_vel_x > 0) or \
                   (abs(enemy.rect.left() - platform_obj.rect.right()) < 2 and original_vel_x < 0):
                    set_enemy_new_patrol_target(enemy)
        
        elif direction == 'y':
            if enemy.vel.y() >= 0: # Moving down (or stationary and intersecting)
                # Check if enemy was above or at the same level as platform top
                if enemy.rect.bottom() >= platform_obj.rect.top() and \
                   rect_before_resolution_this_axis.bottom() <= platform_obj.rect.top() + 1.0:
                     # Check for sufficient horizontal overlap
                    min_overlap_ratio = 0.1 # Example: 10% of enemy width must overlap
                    min_horizontal_overlap = enemy.rect.width() * min_overlap_ratio
                    actual_overlap_width = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                           max(enemy.rect.left(), platform_obj.rect.left())

                    if actual_overlap_width >= min_horizontal_overlap:
                        enemy.rect.moveBottom(platform_obj.rect.top())
                        enemy.on_ground = True
                        enemy.vel.setY(0.0)
            elif enemy.vel.y() < 0: # Moving up
                if enemy.rect.top() <= platform_obj.rect.bottom() and \
                   rect_before_resolution_this_axis.top() >= platform_obj.rect.bottom() - 1.0:
                    min_overlap_ratio_ceil = 0.1 
                    min_horizontal_overlap_ceil = enemy.rect.width() * min_overlap_ratio_ceil
                    actual_overlap_width_ceil = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                                max(enemy.rect.left(), platform_obj.rect.left())
                    if actual_overlap_width_ceil >= min_horizontal_overlap_ceil:
                        enemy.rect.moveTop(platform_obj.rect.bottom())
                        enemy.vel.setY(0.0) # Stop upward movement
            # Sync pos.y after Y collision (enemy pos is midbottom)
            enemy.pos.setY(enemy.rect.bottom())


def _check_enemy_character_collision(enemy: 'EnemyClass_TYPE', direction: str, character_list: List[Any]) -> bool:
    collision_occurred = False
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and \
            hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and \
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF)):
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing attributes for char collision. Skipping.")
        return False

    for other_char in character_list:
        if other_char is enemy or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()):
            continue
        
        if not (hasattr(other_char, '_valid_init') and other_char._valid_init and
                hasattr(other_char, 'is_dead') and
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False))):
            continue

        if enemy.rect.intersects(other_char.rect):
            collision_occurred = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)
            is_other_aflame = getattr(other_char, 'is_aflame', False) or getattr(other_char, 'is_deflaming', False)
            is_other_frozen = getattr(other_char, 'is_frozen', False) or getattr(other_char, 'is_defrosting', False)

            # Enemy aflame ignites other non-petrified, non-frozen, non-aflame character
            if getattr(enemy, 'is_aflame', False) and hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               not is_other_aflame and not is_other_frozen and \
               not getattr(enemy, 'has_ignited_another_enemy_this_cycle', True) and not is_other_petrified_solid:
                
                other_char_id_log = getattr(other_char, 'enemy_id', getattr(other_char, 'player_id', 'UnknownChar'))
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (aflame) touched Character {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                enemy.has_ignited_another_enemy_this_cycle = True 
                continue # No physical pushback for this specific interaction

            bounce_vel = float(getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5))
            if direction == 'x':
                push_dir_self = -1 if enemy.rect.center().x() < other_char.rect.center().x() else 1
                if push_dir_self == -1: enemy.rect.moveRight(other_char.rect.left()) # Enemy is on left, moves right to resolve
                else: enemy.rect.moveLeft(other_char.rect.right()) # Enemy is on right, moves left
                enemy.vel.setX(push_dir_self * bounce_vel) # Enemy bounces away

                if not is_other_petrified_solid: # Only push other if it's not a solid petrified block
                    can_push_other = not (
                        (hasattr(other_char, 'is_attacking') and other_char.is_attacking) or
                        is_other_aflame or is_other_frozen or
                        (hasattr(other_char, 'is_dashing') and other_char.is_dashing) or
                        (hasattr(other_char, 'is_rolling') and other_char.is_rolling)
                    )
                    if hasattr(other_char, 'vel') and isinstance(other_char.vel, QPointF) and can_push_other:
                        other_char.vel.setX(-push_dir_self * bounce_vel) # Other char bounces in opposite dir
                    if hasattr(other_char, 'pos') and isinstance(other_char.pos, QPointF) and \
                       hasattr(other_char, 'rect') and isinstance(other_char.rect, QRectF) and can_push_other:
                        other_char.pos.setX(other_char.pos.x() + (-push_dir_self * 1.5)) # Small displacement
                        if hasattr(other_char, '_update_rect_from_image_and_pos') and callable(other_char._update_rect_from_image_and_pos):
                             other_char._update_rect_from_image_and_pos()
                        elif hasattr(other_char.rect, 'moveCenter'): 
                            other_char.rect.moveCenter(QPointF(other_char.pos.x(), other_char.rect.center().y()))
                enemy.pos.setX(enemy.rect.center().x()) # Sync pos from rect for enemy

            elif direction == 'y': # Vertical collision
                # Enemy lands on top of other_char
                if enemy.vel.y() > 0 and enemy.rect.bottom() > other_char.rect.top() and \
                   enemy.rect.center().y() < other_char.rect.center().y(): # Enemy center is above other's center
                    enemy.rect.moveBottom(other_char.rect.top())
                    enemy.on_ground = True; enemy.vel.setY(0.0)
                # Enemy hits other_char from below
                elif enemy.vel.y() < 0 and enemy.rect.top() < other_char.rect.bottom() and \
                     enemy.rect.center().y() > other_char.rect.center().y(): # Enemy center is below other's center
                    enemy.rect.moveTop(other_char.rect.bottom())
                    enemy.vel.setY(0.0)
                enemy.pos.setY(enemy.rect.bottom()) # Sync pos from rect for enemy
    return collision_occurred


def _check_enemy_hazard_collisions(enemy: 'EnemyClass_TYPE', hazards_list: List[Any]):
    current_time_ms = get_current_ticks_monotonic()
    if not getattr(enemy, '_valid_init', False) or getattr(enemy, 'is_dead', True) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       (getattr(enemy, 'is_taking_hit', False) and \
        current_time_ms - getattr(enemy, 'hit_timer', 0) < getattr(enemy, 'hit_cooldown', 500)) or \
       getattr(enemy, 'is_petrified', False) or getattr(enemy, 'is_frozen', False):
        return
    if not hasattr(enemy, 'rect') or not isinstance(enemy.rect, QRectF): return

    damage_taken_this_frame = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF):
            warning(f"Enemy Collision: Hazard object {hazard_obj} missing valid rect. Skipping."); continue
        
        if not enemy.rect.intersects(hazard_obj.rect): continue

        if isinstance(hazard_obj, Lava):
            # Check for significant overlap with lava
            enemy_feet_in_lava = enemy.rect.bottom() > hazard_obj.rect.top() + (enemy.rect.height() * 0.2)
            min_horizontal_hazard_overlap = enemy.rect.width() * 0.20
            actual_overlap_width = min(enemy.rect.right(), hazard_obj.rect.right()) - max(enemy.rect.left(), hazard_obj.rect.left())

            if enemy_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damage_taken_this_frame: # Apply damage only once per frame from hazards
                    if hasattr(enemy, 'apply_aflame_effect') and callable(enemy.apply_aflame_effect):
                        enemy.apply_aflame_effect() # Lava makes enemy aflame
                    
                    lava_damage = int(getattr(C, 'LAVA_DAMAGE', 25))
                    if lava_damage > 0 and hasattr(enemy, 'take_damage') and callable(enemy.take_damage):
                        enemy.take_damage(lava_damage)
                    damage_taken_this_frame = True
                    
                    if not getattr(enemy, 'is_dead', False): # If still alive after lava damage
                        if hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF):
                            enemy.vel.setY(float(getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0)) * 0.3) # Lava bounce (use float)
                            push_dir = 1 if enemy.rect.center().x() < hazard_obj.rect.center().x() else -1
                            enemy.vel.setX(-push_dir * 4.0)
                        enemy.on_ground = False 
                    break # Processed one lava collision, exit loop for this frame
        # Add other hazard types here if needed
        if damage_taken_this_frame: break 


def update_enemy_physics_and_collisions(enemy: 'EnemyClass_TYPE', dt_sec: float, platforms_list: List[Any],
                                        hazards_list: List[Any], all_other_characters_list: List[Any]):
    if not getattr(enemy, '_valid_init', False) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       (getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False)) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False):
        if getattr(enemy, 'is_dead', False) and (hasattr(enemy, 'alive') and enemy.alive()) and hasattr(enemy, 'kill'):
            enemy.kill() 
        return

    if not (hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and
            hasattr(enemy, 'acc') and isinstance(enemy.acc, QPointF) and
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF) and
            hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing or invalid physics attributes for update. Skipping.")
        return

    # Apply gravity
    enemy.vel.setY(enemy.vel.y() + enemy.acc.y()) # Assuming acc.y is gravity per frame/tick

    # Apply horizontal acceleration and friction
    enemy_friction = float(getattr(C, 'ENEMY_FRICTION', -0.12))
    current_speed_limit = float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0))
    if getattr(enemy, 'is_aflame', False):
        current_speed_limit *= float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.3)) # Corrected constant name
    elif getattr(enemy, 'is_deflaming', False):
        current_speed_limit *= float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.2)) # Corrected constant name
    
    terminal_velocity = float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))

    enemy.vel.setX(enemy.vel.x() + enemy.acc.x()) # Apply horizontal acceleration

    if getattr(enemy, 'on_ground', False) and abs(enemy.acc.x()) < 1e-6: # Apply friction if on ground and no input
        friction_force = enemy.vel.x() * enemy_friction
        if abs(enemy.vel.x()) > 0.1: enemy.vel.setX(enemy.vel.x() + friction_force)
        else: enemy.vel.setX(0.0)

    # Clamp velocities
    enemy.vel.setX(max(-current_speed_limit, min(current_speed_limit, enemy.vel.x())))
    enemy.vel.setY(min(enemy.vel.y(), terminal_velocity))

    enemy.on_ground = False # Reset before collision checks for this frame

    # --- Horizontal movement and collision ---
    # Update position by scaled velocity (if dt_sec and C.FPS are for frame-rate independence)
    # If vel is per-frame: enemy.pos.setX(enemy.pos.x() + enemy.vel.x())
    enemy.pos.setX(enemy.pos.x() + enemy.vel.x() * dt_sec * C.FPS) 
    if hasattr(enemy, '_update_rect_from_image_and_pos') and callable(enemy._update_rect_from_image_and_pos):
        enemy._update_rect_from_image_and_pos()
    
    _check_enemy_platform_collisions(enemy, 'x', platforms_list)
    collided_x_char = _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    # Re-sync pos from rect.center().x() if rect was moved by collision
    enemy.pos.setX(enemy.rect.center().x())


    # --- Vertical movement and collision ---
    # enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
    enemy.pos.setY(enemy.pos.y() + enemy.vel.y() * dt_sec * C.FPS)
    if hasattr(enemy, '_update_rect_from_image_and_pos') and callable(enemy._update_rect_from_image_and_pos):
        enemy._update_rect_from_image_and_pos()
        
    _check_enemy_platform_collisions(enemy, 'y', platforms_list)
    if not collided_x_char: 
        _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    # Re-sync pos from rect.bottom() if rect was moved by collision
    enemy.pos.setY(enemy.rect.bottom())

    # Hazard collisions
    _check_enemy_hazard_collisions(enemy, hazards_list)

    # Final position sync (anchor to midbottom of the rect)
    # This ensures the logical 'pos' (midbottom) matches the rendered 'rect' (topleft, w, h)
    enemy.pos.setX(enemy.rect.center().x())
    enemy.pos.setY(enemy.rect.bottom())
    # Call _update_rect_from_image_and_pos one last time if pos was adjusted,
    # though this might be redundant if all collision resolutions correctly update rect and then pos.
    # If pos was directly changed here, rect needs update.
    if hasattr(enemy, '_update_rect_from_image_and_pos') and callable(enemy._update_rect_from_image_and_pos):
        enemy._update_rect_from_image_and_pos()