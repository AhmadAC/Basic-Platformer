# enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy physics, movement, and collisions for PySide6.
Ensures robust platform (wall/floor/ceiling) collision resolution.
"""
# version 2.0.5 (Corrected ground check, lava bounce, enemy pushback)

import time
from typing import List, Any, Optional, TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF

import constants as C
from tiles import Lava # For type hinting if needed, ensure Platform is also available if used

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
    def info(msg, *args, **kwargs): print(f"INFO: {msg}", *args)
    def debug(msg, *args, **kwargs): print(f"DEBUG ENEMY_PHYSICS: {msg}", *args) # Added prefix
    def warning(msg, *args, **kwargs): print(f"WARNING ENEMY_PHYSICS: {msg}", *args)
    def error(msg, *args, **kwargs): print(f"ERROR ENEMY_PHYSICS: {msg}", *args)
    def critical(msg, *args, **kwargs): print(f"CRITICAL ENEMY_PHYSICS: {msg}", *args)

_start_time_enemy_phys_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_phys_monotonic) * 1000)


def _check_enemy_platform_collisions(enemy: 'EnemyClass_TYPE', direction: str, platforms_list: List[Any], dt_sec: float): # Added dt_sec for estimate
    """
    Checks and resolves collisions between the enemy and platforms for a given axis.
    Assumes enemy.rect has already been moved by velocity for this axis.
    Modifies enemy.rect and enemy.vel in place.
    """
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and \
            hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF)):
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing essential attributes for platform collision. Skipping.")
        return

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or not platform_obj.rect.isValid():
            warning(f"Enemy Collision: Platform object {platform_obj} missing valid rect. Skipping.")
            continue

        if not enemy.rect.intersects(platform_obj.rect):
            continue

        original_vel_x_for_ai_reaction = enemy.vel.x() # Store before it's zeroed for AI reaction

        # --- Horizontal Collision (Walls) ---
        if direction == 'x':
            if enemy.vel.x() > 0: # Moving right, collided with platform's left edge
                overlap_x = enemy.rect.right() - platform_obj.rect.left()
                if overlap_x > 0:
                    enemy.rect.translate(-overlap_x, 0) # Move enemy left by overlap
                    enemy.vel.setX(0.0)
            elif enemy.vel.x() < 0: # Moving left, collided with platform's right edge
                overlap_x = platform_obj.rect.right() - enemy.rect.left()
                if overlap_x > 0:
                    enemy.rect.translate(overlap_x, 0) # Move enemy right by overlap
                    enemy.vel.setX(0.0)

            # AI reaction to wall bump if patrolling
            if getattr(enemy, 'ai_state', None) == 'patrolling' and \
               abs(original_vel_x_for_ai_reaction) > 0.05 and enemy.vel.x() == 0.0:
                # Ensure it was a side collision, not a corner snag
                vertical_overlap_for_patrol_turn = min(enemy.rect.bottom(), platform_obj.rect.bottom()) - \
                                                   max(enemy.rect.top(), platform_obj.rect.top())
                if vertical_overlap_for_patrol_turn > enemy.rect.height() * 0.5: # Need significant vertical overlap
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} hit wall while patrolling. Turning around.")
                    set_enemy_new_patrol_target(enemy)

        # --- Vertical Collision (Floor/Ceiling) ---
        elif direction == 'y':
            if enemy.vel.y() >= 0: # Moving down or stationary and intersecting from above
                overlap_y = enemy.rect.bottom() - platform_obj.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio = 0.1 # Requires at least 10% horizontal overlap to land
                    min_h_overlap_pixels = enemy.rect.width() * min_h_overlap_ratio
                    actual_h_overlap = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                       max(enemy.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap >= min_h_overlap_pixels:
                        # Corrected: previous_enemy_bottom_y_estimate calculation
                        # Uses dt_sec if vel is speed, assumes vel is displacement per frame if dt_sec is not used.
                        # The main physics update uses: enemy.pos.setY(enemy.pos.y() + enemy.vel.y() * dt_sec * C.FPS)
                        # So displacement_y_this_frame should be enemy.vel.y() * dt_sec * C.FPS
                        displacement_y_this_frame = enemy.vel.y() * dt_sec * getattr(C, 'FPS', 60.0)
                        previous_enemy_bottom_y_estimate = enemy.rect.bottom() - displacement_y_this_frame

                        was_above_or_at_surface_epsilon = 1.0
                        was_truly_above_or_at_surface = previous_enemy_bottom_y_estimate <= platform_obj.rect.top() + was_above_or_at_surface_epsilon

                        can_snap_down_from_current = enemy.rect.bottom() > platform_obj.rect.top() and \
                                                     enemy.rect.bottom() <= platform_obj.rect.top() + getattr(C, 'GROUND_SNAP_THRESHOLD', 5.0)

                        # Corrected: getattr(enemy, 'on_ground', False)
                        if was_truly_above_or_at_surface or (getattr(enemy, 'on_ground', False) and can_snap_down_from_current):
                            # just_landed = not getattr(enemy, 'on_ground', False) # Check before setting
                            enemy.rect.translate(0, -overlap_y) # Move enemy up by overlap
                            setattr(enemy, 'on_ground', True)
                            enemy.vel.setY(0.0)
                            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setY'): enemy.acc.setY(0.0)

            elif enemy.vel.y() < 0: # Moving up, collided with platform's bottom edge (ceiling)
                overlap_y = platform_obj.rect.bottom() - enemy.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio_ceil = 0.1
                    min_h_overlap_pixels_ceil = enemy.rect.width() * min_h_overlap_ratio_ceil
                    actual_h_overlap_ceil = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                            max(enemy.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap_ceil >= min_h_overlap_pixels_ceil:
                        enemy.rect.translate(0, overlap_y) # Move enemy down by overlap
                        enemy.vel.setY(0.0) # Stop upward movement


def _check_enemy_character_collision(enemy: 'EnemyClass_TYPE', direction: str, character_list: List[Any]) -> bool:
    """Checks and resolves basic pushback collisions with other characters."""
    collision_occurred = False
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and \
            hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and \
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF)):
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing attributes for char collision. Skipping.")
        return False

    for other_char in character_list:
        if other_char is enemy or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()): # Check if other character is active
            continue
        # Ensure other_char is a valid game entity for collision (simplified check)
        if not (hasattr(other_char, '_valid_init') and other_char._valid_init and
                hasattr(other_char, 'is_dead') and
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False)) ): # Can collide with petrified but not "truly" dead
            continue

        if enemy.rect.intersects(other_char.rect):
            collision_occurred = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)

            # Aflame interaction (effect-based, might not involve pushback)
            is_other_target_susceptible_to_fire = not (getattr(other_char, 'is_aflame', False) or \
                                                     getattr(other_char, 'is_frozen', False) or \
                                                     getattr(other_char, 'is_petrified', False))
            if getattr(enemy, 'is_aflame', False) and \
               hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               is_other_target_susceptible_to_fire and \
               not getattr(enemy, 'has_ignited_another_enemy_this_cycle', True) :

                other_char_id_log = getattr(other_char, 'enemy_id', getattr(other_char, 'player_id', 'UnknownChar'))
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (aflame) touched Character {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                enemy.has_ignited_another_enemy_this_cycle = True

            # Physical pushback logic
            bounce_vel_char = float(getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)) * 0.7 # Enemies might bounce less aggressively

            if direction == 'x':
                overlap_x_char = 0.0
                push_dir_self = 0 # Direction 'enemy' will be pushed/move away
                # Determine who pushes whom based on relative positions and movement
                if enemy.vel.x() > 0: # Enemy moving right
                    overlap_x_char = enemy.rect.right() - other_char.rect.left()
                    if overlap_x_char > 0:
                        enemy.rect.translate(-overlap_x_char, 0)
                        push_dir_self = -1 # Enemy was pushed left
                elif enemy.vel.x() < 0: # Enemy moving left
                    overlap_x_char = other_char.rect.right() - enemy.rect.left()
                    if overlap_x_char > 0:
                        enemy.rect.translate(overlap_x_char, 0)
                        push_dir_self = 1 # Enemy was pushed right
                else: # Enemy might be stationary, or pushed into other_char by another force
                    if enemy.rect.center().x() < other_char.rect.center().x(): # Enemy is to the left of other_char
                        overlap_x_char = enemy.rect.right() - other_char.rect.left()
                        if overlap_x_char > 0:
                            enemy.rect.translate(-overlap_x_char / 2.0, 0) # Both move apart
                            if hasattr(other_char, 'rect') and hasattr(other_char.rect, 'translate'): other_char.rect.translate(overlap_x_char / 2.0, 0)
                            push_dir_self = -1
                    else: # Enemy is to the right
                        overlap_x_char = other_char.rect.right() - enemy.rect.left()
                        if overlap_x_char > 0:
                            enemy.rect.translate(overlap_x_char / 2.0, 0)
                            if hasattr(other_char, 'rect') and hasattr(other_char.rect, 'translate'): other_char.rect.translate(-overlap_x_char / 2.0, 0)
                            push_dir_self = 1

                if overlap_x_char > 0 and push_dir_self != 0: # If a push occurred
                    enemy.vel.setX(push_dir_self * bounce_vel_char) # Enemy bounces

                    can_push_other_char = not (getattr(other_char, 'is_attacking', False) or \
                                         is_other_petrified_solid or \
                                         getattr(other_char, 'is_dashing', False) or \
                                         getattr(other_char, 'is_rolling', False) or \
                                         getattr(other_char, 'is_aflame', False) or \
                                         getattr(other_char, 'is_frozen', False) )

                    if hasattr(other_char, 'vel') and isinstance(other_char.vel, QPointF) and can_push_other_char:
                        other_char_push_direction = -push_dir_self # other_char pushed opposite to enemy's bounce
                        other_char.vel.setX(other_char_push_direction * bounce_vel_char)

            elif direction == 'y': # Vertical collision with another character
                overlap_y_char = 0.0
                if enemy.vel.y() > 0 and enemy.rect.bottom() > other_char.rect.top() and enemy.rect.center().y() < other_char.rect.center().y():
                    overlap_y_char = enemy.rect.bottom() - other_char.rect.top()
                    if overlap_y_char > 0: enemy.rect.translate(0, -overlap_y_char); setattr(enemy, 'on_ground', True); enemy.vel.setY(0.0)
                elif enemy.vel.y() < 0 and enemy.rect.top() < other_char.rect.bottom() and enemy.rect.center().y() > other_char.rect.center().y():
                    overlap_y_char = other_char.rect.bottom() - enemy.rect.top()
                    if overlap_y_char > 0: enemy.rect.translate(0, overlap_y_char); enemy.vel.setY(0.0)
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
            enemy_feet_in_lava = enemy.rect.bottom() > hazard_obj.rect.top() + (enemy.rect.height() * 0.2)
            min_h_overlap = enemy.rect.width() * 0.20
            actual_h_overlap = min(enemy.rect.right(), hazard_obj.rect.right()) - max(enemy.rect.left(), hazard_obj.rect.left())
            if enemy_feet_in_lava and actual_h_overlap >= min_h_overlap:
                if not damage_taken_this_frame:
                    if hasattr(enemy, 'apply_aflame_effect') and callable(enemy.apply_aflame_effect) and not enemy.is_aflame:
                        enemy.apply_aflame_effect()
                    lava_damage = int(getattr(C, 'LAVA_DAMAGE', 25))
                    if lava_damage > 0 and hasattr(enemy, 'take_damage') and callable(enemy.take_damage):
                        enemy.take_damage(lava_damage)
                    damage_taken_this_frame = True
                    # Removed bounce logic from here as per Issue #1 Fix #2
                    break
        if damage_taken_this_frame:
            break


def update_enemy_physics_and_collisions(enemy: 'EnemyClass_TYPE', dt_sec: float, platforms_list: List[Any],
                                        hazards_list: List[Any], all_other_characters_list: List[Any]):
    # Handle cases where enemy should not have physics updates
    if not getattr(enemy, '_valid_init', False) or \
       not (hasattr(enemy, 'alive') and enemy.alive()):
        # If dead but animation not finished, or smashed but anim not finished, might need minimal physics (e.g. falling)
        if (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
           (getattr(enemy, 'is_stone_smashed', False) and not getattr(enemy, 'death_animation_finished', True) ):
            if not getattr(enemy, 'on_ground', True) and hasattr(enemy, 'vel') and hasattr(enemy, 'acc') and hasattr(enemy, 'pos') and hasattr(enemy, 'rect'):
                enemy.vel.setY(enemy.vel.y() + enemy.acc.y()) # Gravity
                enemy.vel.setY(min(enemy.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                # Position update uses scaled velocity
                enemy.pos.setY(enemy.pos.y() + enemy.vel.y() * dt_sec * getattr(C, 'FPS', 60.0))
                if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
                _check_enemy_platform_collisions(enemy, 'y', platforms_list, dt_sec) # Minimal collision for falling body
                if hasattr(enemy, 'pos'): enemy.pos.setY(enemy.rect.bottom()) # Sync pos
        return # Main physics update skipped

    if (getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False) and getattr(enemy, 'on_ground', True)) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) :
        # If petrified AND on ground, or frozen/defrosting, skip most physics
        if hasattr(enemy, 'vel'): enemy.vel.setX(0); enemy.vel.setY(0) # Ensure stopped
        if hasattr(enemy, 'acc'): enemy.acc.setX(0); # Y acc (gravity) might still be there if needed for unfreeze fall
        return

    if not (hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and
            hasattr(enemy, 'acc') and isinstance(enemy.acc, QPointF) and
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF) and
            hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing physics attributes. Skipping update.")
        return

    # --- Apply Physics (Gravity, Friction, AI-driven Acceleration) ---
    # AI sets enemy.acc.x. Gravity is usually in enemy.acc.y.
    if not getattr(enemy, 'on_ground', False): # Apply gravity if not on ground
        if not (getattr(enemy, 'can_fly', False) and getattr(enemy, 'ai_state', '') == 'chasing'): # Simple check if enemy can fly and is chasing
            enemy.vel.setY(enemy.vel.y() + enemy.acc.y()) # acc.y is gravity

    # Horizontal movement based on AI-set acceleration
    enemy.vel.setX(enemy.vel.x() + enemy.acc.x())

    # Apply friction if on ground and no horizontal acceleration input from AI
    if getattr(enemy, 'on_ground', False) and abs(enemy.acc.x()) < 1e-6:
        friction_coeff = float(getattr(C, 'ENEMY_FRICTION', -0.12))
        friction_force = enemy.vel.x() * friction_coeff
        if abs(enemy.vel.x()) > 0.1: enemy.vel.setX(enemy.vel.x() + friction_force)
        else: enemy.vel.setX(0.0)

    # Clamp velocities
    speed_limit = float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0))
    if getattr(enemy, 'is_aflame', False): speed_limit *= float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.3))
    elif getattr(enemy, 'is_deflaming', False): speed_limit *= float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.2))

    enemy.vel.setX(max(-speed_limit, min(speed_limit, enemy.vel.x())))
    enemy.vel.setY(min(enemy.vel.y(), float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))))

    # --- Collision Detection and Resolution ---
    # Reset on_ground before Y collision checks for this frame
    setattr(enemy, 'on_ground', False)

    # Horizontal movement and collision
    enemy.pos.setX(enemy.pos.x() + enemy.vel.x() * dt_sec * getattr(C, 'FPS', 60.0)) # Scale velocity by frame time
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'x', platforms_list, dt_sec)
    _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    # Sync logical pos from rect AFTER all X-axis resolutions
    if hasattr(enemy, 'pos') and hasattr(enemy.rect, 'center'): enemy.pos.setX(enemy.rect.center().x())


    # Vertical movement and collision
    enemy.pos.setY(enemy.pos.y() + enemy.vel.y() * dt_sec * getattr(C, 'FPS', 60.0)) # Scale velocity by frame time
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'y', platforms_list, dt_sec)
    _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    # Sync logical pos from rect AFTER all Y-axis resolutions
    if hasattr(enemy, 'pos') and hasattr(enemy.rect, 'bottom'): enemy.pos.setY(enemy.rect.bottom())

    # Hazard collisions
    _check_enemy_hazard_collisions(enemy, hazards_list)

    # Final position sync if _update_rect_from_image_and_pos isn't the sole authority for rect from pos
    if hasattr(enemy, '_update_rect_from_image_and_pos'):
        enemy._update_rect_from_image_and_pos()
    else: # Fallback if the method is missing: sync rect based on pos (midbottom anchor)
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull() and hasattr(enemy, 'rect'):
            img_w = float(enemy.image.width()); img_h = float(enemy.image.height())
            enemy.rect.setRect(enemy.pos.x() - img_w / 2.0, enemy.pos.y() - img_h, img_w, img_h)