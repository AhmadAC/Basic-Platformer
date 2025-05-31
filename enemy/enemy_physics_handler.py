#################### START OF FILE: enemy\enemy_physics_handler.py ####################
# enemy/enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy physics, movement, and collisions for PySide6.
Ensures robust platform (wall/floor/ceiling) collision resolution.
MODIFIED: Enemies respect statue solidity (ignore smashed statues).
MODIFIED: Corrected gravity application logic by not nullifying acc.y on landing.
MODIFIED: Standardized position updates to be based on velocity per frame,
          assuming dt_sec passed to main update is effectively 1/FPS.
MODIFIED: Corrected logger import path and relative import for set_enemy_new_patrol_target.
"""
# version 2.0.9 (Corrected import paths)

import time
from typing import List, Any, Optional, TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF

# --- Project Root Setup ---
import os
import sys
_ENEMY_PHYSICS_HANDLER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_ENEMY_PHYSICS_HANDLER = os.path.dirname(_ENEMY_PHYSICS_HANDLER_PY_FILE_DIR) # Up one level to 'enemy'
if _PROJECT_ROOT_FOR_ENEMY_PHYSICS_HANDLER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_ENEMY_PHYSICS_HANDLER) # Add 'enemy' package's parent
_PROJECT_ROOT_GRANDPARENT_PHYSICS = os.path.dirname(_PROJECT_ROOT_FOR_ENEMY_PHYSICS_HANDLER) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_PHYSICS not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_PHYSICS) # Add actual project root
# --- End Project Root Setup ---

import main_game.constants as C
from main_game.tiles import Lava # Assuming tiles.py is in main_game
from player.statue import Statue # Assuming statue.py is in player.statue

if TYPE_CHECKING:
    from .enemy import Enemy as EnemyClass_TYPE # Use relative import if type hinting Enemy

# --- Logger Setup ---
import logging
_enemy_physics_logger_instance = logging.getLogger(__name__ + "_enemy_physics_internal_fallback")
if not _enemy_physics_logger_instance.hasHandlers():
    _handler_eph_fb = logging.StreamHandler(sys.stdout)
    _formatter_eph_fb = logging.Formatter('ENEMY_PHYSICS (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_eph_fb.setFormatter(_formatter_eph_fb)
    _enemy_physics_logger_instance.addHandler(_handler_eph_fb)
    _enemy_physics_logger_instance.setLevel(logging.DEBUG)
    _enemy_physics_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_physics_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_physics_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_physics_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_physics_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_physics_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("EnemyPhysicsHandler: Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL ENEMY_PHYSICS_HANDLER: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_eph:
    critical(f"CRITICAL ENEMY_PHYSICS_HANDLER: Unexpected error during logger setup from main_game.logger: {e_logger_init_eph}. Using internal fallback.")
# --- End Logger Setup ---

# --- Import from sibling module within 'enemy' package ---
try:
    from .enemy_ai_handler import set_enemy_new_patrol_target # Relative import
except ImportError as e_ai_import:
    critical(f"ENEMY_PHYSICS_HANDLER: Failed to import set_enemy_new_patrol_target from .enemy_ai_handler: {e_ai_import}")
    def set_enemy_new_patrol_target(enemy: Any):
        enemy_id_log = getattr(enemy, 'enemy_id', 'N/A')
        warning(f"ENEMY_PHYSICS_HANDLER (Fallback): set_enemy_new_patrol_target not found for Enemy ID {enemy_id_log}")
# --- End Import ---


_start_time_enemy_phys_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_phys_monotonic) * 1000)


def _check_enemy_platform_collisions(enemy: 'EnemyClass_TYPE', direction: str, platforms_list: List[Any]):
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and \
            hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF)):
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing essential attributes for platform collision. Skipping.")
        return

    for platform_idx, platform_obj in enumerate(platforms_list):
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or not platform_obj.rect.isValid():
             warning(f"Enemy Collision: Platform object {platform_idx} missing valid rect. Skipping.")
             continue

        if isinstance(platform_obj, Statue) and platform_obj.is_smashed:
            continue

        if not enemy.rect.intersects(platform_obj.rect):
            continue

        original_vel_x_for_ai_reaction = enemy.vel.x()

        if direction == 'x':
            if enemy.vel.x() > 0:
                overlap_x = enemy.rect.right() - platform_obj.rect.left()
                if overlap_x > 0: enemy.rect.translate(-overlap_x, 0); enemy.vel.setX(0.0)
            elif enemy.vel.x() < 0:
                overlap_x = platform_obj.rect.right() - enemy.rect.left()
                if overlap_x > 0: enemy.rect.translate(overlap_x, 0); enemy.vel.setX(0.0)

            if getattr(enemy, 'ai_state', None) == 'patrolling' and \
               abs(original_vel_x_for_ai_reaction) > 0.05 and enemy.vel.x() == 0.0:
                vertical_overlap_for_patrol_turn = min(enemy.rect.bottom(), platform_obj.rect.bottom()) - \
                                                   max(enemy.rect.top(), platform_obj.rect.top())
                if vertical_overlap_for_patrol_turn > enemy.rect.height() * 0.5:
                    set_enemy_new_patrol_target(enemy)

        elif direction == 'y':
            if enemy.vel.y() >= 0:
                overlap_y = enemy.rect.bottom() - platform_obj.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio = float(getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15))
                    min_h_overlap_pixels = enemy.rect.width() * min_h_overlap_ratio
                    actual_h_overlap = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                       max(enemy.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap >= min_h_overlap_pixels:
                        displacement_y_this_frame = enemy.vel.y()
                        previous_enemy_bottom_y_estimate = enemy.rect.bottom() - displacement_y_this_frame
                        was_above_or_at_surface_epsilon = 1.0
                        was_truly_above_or_at_surface = previous_enemy_bottom_y_estimate <= platform_obj.rect.top() + was_above_or_at_surface_epsilon
                        can_snap_down_from_current = enemy.on_ground and \
                                                     enemy.rect.bottom() > platform_obj.rect.top() and \
                                                     enemy.rect.bottom() <= platform_obj.rect.top() + float(getattr(C, 'GROUND_SNAP_THRESHOLD', 5.0))
                        if was_truly_above_or_at_surface or can_snap_down_from_current:
                            enemy.rect.translate(0, -overlap_y); enemy.on_ground = True; enemy.vel.setY(0.0)
            elif enemy.vel.y() < 0:
                overlap_y = platform_obj.rect.bottom() - enemy.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio_ceil = float(getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15))
                    min_h_overlap_pixels_ceil = enemy.rect.width() * min_h_overlap_ratio_ceil
                    actual_h_overlap_ceil = min(enemy.rect.right(), platform_obj.rect.right()) - \
                                            max(enemy.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap_ceil >= min_h_overlap_pixels_ceil:
                        enemy.rect.translate(0, overlap_y); enemy.vel.setY(0.0)


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
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False)) ):
            continue

        if enemy.rect.intersects(other_char.rect):
            collision_occurred = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)
            is_other_target_susceptible_to_fire = not (getattr(other_char, 'is_aflame', False) or \
                                                     getattr(other_char, 'is_frozen', False) or \
                                                     getattr(other_char, 'is_petrified', False))
            if getattr(enemy, 'is_aflame', False) and \
               hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               is_other_target_susceptible_to_fire and \
               not getattr(enemy, 'has_ignited_another_enemy_this_cycle', True) :
                other_char.apply_aflame_effect()
                enemy.has_ignited_another_enemy_this_cycle = True

            bounce_vel_char = float(getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)) * 0.7

            if direction == 'x':
                overlap_x_char = 0.0; push_dir_self = 0
                if enemy.vel.x() > 0:
                    overlap_x_char = enemy.rect.right() - other_char.rect.left()
                    if overlap_x_char > 0: enemy.rect.translate(-overlap_x_char, 0); push_dir_self = -1
                elif enemy.vel.x() < 0:
                    overlap_x_char = other_char.rect.right() - enemy.rect.left()
                    if overlap_x_char > 0: enemy.rect.translate(overlap_x_char, 0); push_dir_self = 1
                else:
                    if enemy.rect.center().x() < other_char.rect.center().x():
                        overlap_x_char = enemy.rect.right() - other_char.rect.left()
                        if overlap_x_char > 0:
                            enemy.rect.translate(-overlap_x_char / 2.0, 0)
                            if hasattr(other_char, 'rect') and hasattr(other_char.rect, 'translate'): other_char.rect.translate(overlap_x_char / 2.0, 0)
                            push_dir_self = -1
                    else:
                        overlap_x_char = other_char.rect.right() - enemy.rect.left()
                        if overlap_x_char > 0:
                            enemy.rect.translate(overlap_x_char / 2.0, 0)
                            if hasattr(other_char, 'rect') and hasattr(other_char.rect, 'translate'): other_char.rect.translate(-overlap_x_char / 2.0, 0)
                            push_dir_self = 1
                if overlap_x_char > 0 and push_dir_self != 0:
                    enemy.vel.setX(push_dir_self * bounce_vel_char)
                    can_push_other_char = not (getattr(other_char, 'is_attacking', False) or \
                                         is_other_petrified_solid or \
                                         getattr(other_char, 'is_dashing', False) or \
                                         getattr(other_char, 'is_rolling', False) or \
                                         getattr(other_char, 'is_aflame', False) or \
                                         getattr(other_char, 'is_frozen', False) )
                    if hasattr(other_char, 'vel') and isinstance(other_char.vel, QPointF) and can_push_other_char:
                        other_char.vel.setX(-push_dir_self * bounce_vel_char)
            elif direction == 'y':
                overlap_y_char = 0.0
                if enemy.vel.y() > 0 and enemy.rect.bottom() > other_char.rect.top() and enemy.rect.center().y() < other_char.rect.center().y():
                    overlap_y_char = enemy.rect.bottom() - other_char.rect.top()
                    if overlap_y_char > 0: enemy.rect.translate(0, -overlap_y_char); enemy.on_ground = True; enemy.vel.setY(0.0)
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
                    break
        if damage_taken_this_frame: break


def update_enemy_physics_and_collisions(enemy: 'EnemyClass_TYPE', dt_sec: float, platforms_list: List[Any],
                                        hazards_list: List[Any], all_other_characters_list: List[Any]):
    if not getattr(enemy, '_valid_init', False): return # Skip if not validly initialized

    # Handle physics for dead but still animating/falling enemies
    if not (hasattr(enemy, 'alive') and enemy.alive()):
        if (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
           (getattr(enemy, 'is_stone_smashed', False) and not getattr(enemy, 'death_animation_finished', True) ):
            
            if not getattr(enemy, 'on_ground', True) and hasattr(enemy, 'vel') and hasattr(enemy, 'acc') and hasattr(enemy, 'pos') and hasattr(enemy, 'rect'):
                enemy.vel.setY(enemy.vel.y() + enemy.acc.y())
                enemy.vel.setY(min(enemy.vel.y(), float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))))
                enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
                if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
                _check_enemy_platform_collisions(enemy, 'y', platforms_list)
                if hasattr(enemy, 'pos') and hasattr(enemy.rect, 'bottom'): enemy.pos.setY(enemy.rect.bottom()) # Sync pos after collision
                if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos() # Final rect update
        return # No further physics/logic if not alive (or if dead and fully finished animation)

    # Skip physics for certain overriding states (petrified, frozen, etc.)
    if (getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False) and getattr(enemy, 'on_ground', True)) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) :
        if hasattr(enemy, 'vel'): enemy.vel.setX(0); enemy.vel.setY(0)
        if hasattr(enemy, 'acc'): enemy.acc.setX(0);
        return

    # Ensure essential physics attributes exist
    if not (hasattr(enemy, 'vel') and isinstance(enemy.vel, QPointF) and
            hasattr(enemy, 'acc') and isinstance(enemy.acc, QPointF) and
            hasattr(enemy, 'pos') and isinstance(enemy.pos, QPointF) and
            hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing physics attributes. Skipping update.")
        return

    # Apply Gravity if not on ground (and not in a state that negates gravity)
    if not getattr(enemy, 'on_ground', False):
        if not (getattr(enemy, 'can_fly', False) and getattr(enemy, 'ai_state', '') == 'chasing'): # Example: flying enemies ignore gravity when chasing
            enemy.vel.setY(enemy.vel.y() + enemy.acc.y()) # acc.y is gravity (units/frame^2)

    # Apply Horizontal Acceleration
    enemy.vel.setX(enemy.vel.x() + enemy.acc.x()) # acc.x is from AI (units/frame^2)

    # Apply Friction if on ground and no horizontal acceleration input from AI
    if getattr(enemy, 'on_ground', False) and abs(enemy.acc.x()) < 1e-6:
        friction_coeff = float(getattr(C, 'ENEMY_FRICTION', -0.12))
        friction_force_per_frame = enemy.vel.x() * friction_coeff
        if abs(enemy.vel.x()) > 0.1: enemy.vel.setX(enemy.vel.x() + friction_force_per_frame)
        else: enemy.vel.setX(0.0)

    # Speed Limits
    speed_limit_x = float(enemy.properties.get("move_speed", getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 50.0) / C.FPS) if hasattr(enemy,'properties') and isinstance(enemy.properties,dict) else float(getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0))
    if getattr(enemy, 'is_aflame', False): speed_limit_x *= float(getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.3))
    elif getattr(enemy, 'is_deflaming', False): speed_limit_x *= float(getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.2))

    enemy.vel.setX(max(-speed_limit_x, min(speed_limit_x, enemy.vel.x())))
    enemy.vel.setY(min(enemy.vel.y(), float(getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))))

    # Reset on_ground flag before Y-axis collision checks
    enemy.on_ground = False

    # --- X-axis Movement and Collision ---
    enemy.pos.setX(enemy.pos.x() + enemy.vel.x())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'x', platforms_list)
    _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    if hasattr(enemy, 'pos') and hasattr(enemy.rect, 'center'): enemy.pos.setX(enemy.rect.center().x()) # Sync pos from resolved rect

    # --- Y-axis Movement and Collision ---
    enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    _check_enemy_platform_collisions(enemy, 'y', platforms_list)
    _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    if hasattr(enemy, 'pos') and hasattr(enemy.rect, 'bottom'): enemy.pos.setY(enemy.rect.bottom()) # Sync pos from resolved rect

    # Hazard Collisions
    _check_enemy_hazard_collisions(enemy, hazards_list)

    # Final rect update based on final position
    if hasattr(enemy, '_update_rect_from_image_and_pos'):
        enemy._update_rect_from_image_and_pos()
    elif hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull() and hasattr(enemy, 'rect'):
        # Fallback rect update if _update_rect_from_image_and_pos is missing
        img_w = float(enemy.image.width()); img_h = float(enemy.image.height())
        enemy.rect.setRect(enemy.pos.x() - img_w / 2.0, enemy.pos.y() - img_h, img_w, img_h)

#################### END OF FILE: enemy/enemy_physics_handler.py ####################