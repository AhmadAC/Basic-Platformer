#################### START OF FILE: enemy\enemy_combat_handler.py ####################
# enemy/enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy combat mechanics for PySide6: checking attack collisions and processing damage.
MODIFIED: Ensure attack_type on enemy is set to "none" (string) after attack for Knight consistency.
MODIFIED: Uses get_current_ticks_monotonic() for consistent timing.
MODIFIED: Log enemy color during attack hit for better debugging.
MODIFIED: Corrected logger import path.
MODIFIED: `set_enemy_state` import is now relative.
"""
# version 2.0.6 (Relative set_enemy_state import, consistent logging)

import time
from typing import List, Any, TYPE_CHECKING, Optional

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# --- Project Root Setup ---
import os
import sys
_ENEMY_COMBAT_HANDLER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_ENEMY_COMBAT_HANDLER = os.path.dirname(_ENEMY_COMBAT_HANDLER_PY_FILE_DIR) # Up one level to 'enemy'
if _PROJECT_ROOT_FOR_ENEMY_COMBAT_HANDLER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_ENEMY_COMBAT_HANDLER) # Add 'enemy' package's parent
_PROJECT_ROOT_GRANDPARENT_COMBAT = os.path.dirname(_PROJECT_ROOT_FOR_ENEMY_COMBAT_HANDLER) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_COMBAT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_COMBAT) # Add actual project root
# --- End Project Root Setup ---


# Game imports
import main_game.constants as C
from player.statue import Statue

if TYPE_CHECKING:
    # from .enemy import Enemy as EnemyClass_TYPE # Use relative import if type hinting Enemy
    pass

# --- Logger Setup ---
import logging
_enemy_combat_logger_instance = logging.getLogger(__name__ + "_enemy_combat_internal_fallback")
if not _enemy_combat_logger_instance.hasHandlers():
    _handler_ec_fb = logging.StreamHandler(sys.stdout)
    _formatter_ec_fb = logging.Formatter('ENEMY_COMBAT (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_ec_fb.setFormatter(_formatter_ec_fb)
    _enemy_combat_logger_instance.addHandler(_handler_ec_fb)
    _enemy_combat_logger_instance.setLevel(logging.DEBUG)
    _enemy_combat_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_combat_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_combat_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_combat_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_combat_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_combat_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("EnemyCombatHandler: Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL ENEMY_COMBAT_HANDLER: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_ec:
    critical(f"CRITICAL ENEMY_COMBAT_HANDLER: Unexpected error during logger setup from main_game.logger: {e_logger_init_ec}. Using internal fallback.")
# --- End Logger Setup ---


_ESH_COMBAT_AVAILABLE = True
try:
    from .enemy_state_handler import set_enemy_state # Relative import
except ImportError as e_esh_combat_import:
    critical(f"ENEMY_COMBAT_HANDLER: Failed to import set_enemy_state from .enemy_state_handler: {e_esh_combat_import}")
    _ESH_COMBAT_AVAILABLE = False
    def set_enemy_state(enemy: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(enemy, 'state'): enemy.state = new_state
        warning(f"ENEMY_COMBAT_HANDLER: Fallback set_enemy_state used for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')} to '{new_state}'")


_start_time_enemy_combat_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_combat_monotonic) * 1000)


def check_enemy_attack_collisions(enemy: Any, hittable_targets_list: List[Any]):
    if not getattr(enemy, '_valid_init', False) or \
       not getattr(enemy, 'is_attacking', False) or \
       getattr(enemy, 'is_dead', True) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_petrified', False):
        return

    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and
            hasattr(enemy, 'attack_hitbox') and isinstance(enemy.attack_hitbox, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing rect or attack_hitbox for collision check.")
        return

    if not all(hasattr(obj, method_name) for obj in [enemy.rect, enemy.attack_hitbox] for method_name in ['center', 'height', 'width', 'right', 'left', 'moveTopLeft']):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: rect or attack_hitbox missing critical QRectF methods.")
        return

    # Position the attack hitbox
    hitbox_half_height = enemy.attack_hitbox.height() / 2.0
    enemy_center_y = enemy.rect.center().y()

    if getattr(enemy, 'facing_right', True):
        top_left_x = enemy.rect.right()
        top_left_y = enemy_center_y - hitbox_half_height
        enemy.attack_hitbox.moveTopLeft(QPointF(top_left_x, top_left_y))
    else: # Facing left
        top_left_x_facing_left = enemy.rect.left() - enemy.attack_hitbox.width()
        top_left_y_facing_left = enemy_center_y - hitbox_half_height
        enemy.attack_hitbox.moveTopLeft(QPointF(top_left_x_facing_left, top_left_y_facing_left))

    current_time_ms = get_current_ticks_monotonic()
    damage_to_target = 0
    current_attack_type_key = str(getattr(enemy, 'attack_type', "none")) # Ensure string, default to "none"

    # Determine damage based on enemy type and current attack
    if enemy.__class__.__name__ == 'EnemyKnight' and hasattr(enemy, 'attack_damage_map'):
        damage_to_target = enemy.attack_damage_map.get(current_attack_type_key, 0)
    else: # Generic enemy
        # If generic enemy uses specific string keys for its one attack type (e.g., "attack"), map it here
        if current_attack_type_key in ["attack", "attack_nm", "standard_attack"]: # Example keys
            damage_to_target = int(enemy.properties.get("attack_damage", getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)))
        else: # If attack_type is "none" or unrecognized string, no damage
            damage_to_target = 0
    
    if damage_to_target <= 0: return

    for target_sprite in hittable_targets_list:
        if not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF): continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    statue_id_log = getattr(target_sprite, 'statue_id', 'N/A')
                    enemy_color_log_statue = getattr(enemy, 'color_name', 'N/A')
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log_statue}, Attack: {current_attack_type_key}) hit Statue {statue_id_log} for {damage_to_target} damage.")
                    target_sprite.take_damage(damage_to_target)
            continue

        if not (hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and \
                hasattr(target_sprite, 'alive') and target_sprite.alive()): continue

        is_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                is_invincible = True
        if is_invincible: continue

        if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                 if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    target_id_log_petri = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownPetrified'))
                    enemy_color_log_petri = getattr(enemy, 'color_name', 'N/A')
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log_petri}, Attack: {current_attack_type_key}) hit petrified target {target_id_log_petri}. Smashing.")
                    target_sprite.smash_petrification()
            continue

        if enemy.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                target_id_log_gen = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                enemy_color_log_gen = getattr(enemy, 'color_name', 'N/A')
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log_gen}, Attack: {current_attack_type_key}) hit Target {target_id_log_gen} for {damage_to_target} damage.")
                target_sprite.take_damage(damage_to_target)


def enemy_take_damage(enemy: Any, damage_amount: int):
    if not _ESH_COMBAT_AVAILABLE:
        critical("ENEMY_COMBAT_HANDLER: set_enemy_state function is not available. Cannot process enemy_take_damage correctly.")
        return

    current_time_ms = get_current_ticks_monotonic()
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    if not getattr(enemy, '_valid_init', False) or not (hasattr(enemy, 'alive') and enemy.alive()): return
    if getattr(enemy, 'is_dead', False) and not getattr(enemy, 'is_petrified', False) : return
    if getattr(enemy, 'is_stone_smashed', False): return

    if not getattr(enemy, 'is_petrified', False):
        hit_cooldown = getattr(enemy, 'hit_cooldown', getattr(C, 'ENEMY_HIT_COOLDOWN', 500))
        if getattr(enemy, 'is_taking_hit', False) and \
           (current_time_ms - getattr(enemy, 'hit_timer', 0) < hit_cooldown):
            return

    if getattr(enemy, 'is_frozen', False) or getattr(enemy, 'is_defrosting', False): return

    was_aflame_before_hit = getattr(enemy, 'is_aflame', False)
    was_deflaming_before_hit = getattr(enemy, 'is_deflaming', False)

    if not hasattr(enemy, 'current_health') or not hasattr(enemy, 'max_health'):
        warning(f"Enemy {enemy_id_log} missing health attributes. Cannot take damage.")
        return

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health)
    enemy_color_for_log = getattr(enemy, 'color_name', 'N/A')
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {enemy_color_for_log}) took {damage_amount} damage. Health: {enemy.current_health}/{enemy.max_health}.")

    if getattr(enemy, 'is_petrified', False):
        if enemy.current_health <= 0:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} health 0. Smashing.")
            # Import locally or ensure it's globally available (might cause circular if not careful)
            try:
                from .enemy_status_effects import smash_petrified_enemy
                smash_petrified_enemy(enemy)
            except ImportError:
                error(f"ENEMY_COMBAT_HANDLER Critical: Could not import smash_petrified_enemy for P{enemy_id_log}.")
                setattr(enemy, 'is_stone_smashed', True) # Fallback
        else:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} took damage but still >0 stone health.")
            enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
        return

    enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
    hit_duration = getattr(enemy, 'hit_duration', getattr(C, 'ENEMY_HIT_STUN_DURATION', 300))

    if enemy.current_health <= 0:
        if not getattr(enemy, 'is_dead', False):
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death', current_time_ms)
    else:
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            if getattr(enemy, 'state', 'idle') != 'hit':
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not on fire. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit', current_time_ms)
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(enemy, 'state', 'N/A')}'")

#################### END OF FILE: enemy/enemy_combat_handler.py ####################