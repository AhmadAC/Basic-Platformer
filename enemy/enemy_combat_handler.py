# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy combat mechanics for PySide6: checking attack collisions and processing damage.
MODIFIED: Ensure attack_type on enemy is set to "none" (string) after attack for Knight consistency.
MODIFIED: Uses get_current_ticks_monotonic() for consistent timing.
MODIFIED: Log enemy color during attack hit for better debugging.
"""
# version 2.0.5 (Knight attack_type consistency, monotonic time, log color on hit)

import time 
from typing import List, Any, TYPE_CHECKING, Optional

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# Game imports
import main_game.constants as C
from player.statue import Statue
# Avoid direct import of Enemy or EnemyKnight here to prevent cycles if possible.
# Use type hints and attribute checks.

if TYPE_CHECKING: 
    # from enemy import Enemy as EnemyClass_TYPE # This can cause circular if enemy imports this
    # For now, let's use Any for enemy type hint in function signatures
    pass

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    print("CRITICAL ENEMY_COMBAT_HANDLER: enemy_state_handler.set_enemy_state not found.")
    def set_enemy_state(enemy: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(enemy, 'state'): enemy.state = new_state
        print(f"CRITICAL ENEMY_COMBAT_HANDLER (Fallback): Cannot set state for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}. Directly set state to '{new_state}'.")

try:
    from logger import debug, warning # Added warning for safety
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_ECOMBAT: {msg}") # Added args
    def warning(msg, *args, **kwargs): print(f"WARNING_ECOMBAT: {msg}") # Added args

_start_time_enemy_combat_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_combat_monotonic) * 1000)


def check_enemy_attack_collisions(enemy: Any, hittable_targets_list: List[Any]):
    # Type hint 'enemy' as Any to accommodate both Enemy and EnemyKnight without direct import here.
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

    # Determine damage based on enemy type and current attack
    damage_to_target = 0
    # EnemyKnight stores attack_type as a string key (e.g., 'attack1')
    # Generic Enemy might use an integer or have a fixed damage
    current_attack_type_key = getattr(enemy, 'attack_type', "none") # Default to "none" string

    if enemy.__class__.__name__ == 'EnemyKnight' and hasattr(enemy, 'attack_damage_map'):
        damage_to_target = enemy.attack_damage_map.get(str(current_attack_type_key), 0) # Default to 0 if key not found
    else: # Generic enemy
        damage_to_target = int(getattr(enemy, 'attack_damage', getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)))
        # If generic enemy has multiple attacks differentiated by attack_type (int), add logic here.
        # For now, assume one damage value for generic enemy.

    if damage_to_target <= 0: # No damage for this attack type or enemy type
        return

    for target_sprite in hittable_targets_list:
        if not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
            continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    # Use the determined damage_to_target for consistency
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}, Attack: {current_attack_type_key}) hit Statue {getattr(target_sprite, 'statue_id', 'N/A')} for {damage_to_target} damage.")
                    target_sprite.take_damage(damage_to_target)
            continue 

        if not (hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and \
                hasattr(target_sprite, 'alive') and target_sprite.alive()):
            continue

        is_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                is_invincible = True
        if is_invincible: continue

        if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                 if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}, Attack: {current_attack_type_key}) hit petrified target {getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))}. Smashing.")
                    target_sprite.smash_petrification()
            continue

        if enemy.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                enemy_color_log = getattr(enemy, 'color_name', 'N/A')
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log}, Attack: {current_attack_type_key}) hit Target {target_id_log} for {damage_to_target} damage.")
                target_sprite.take_damage(damage_to_target)


def enemy_take_damage(enemy: Any, damage_amount: int):
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
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}) took {damage_amount} damage. Health: {enemy.current_health}/{enemy.max_health}.")

    if getattr(enemy, 'is_petrified', False):
        if enemy.current_health <= 0:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} health 0. Smashing.")
            from enemy_status_effects import smash_petrified_enemy
            smash_petrified_enemy(enemy)
        else:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} took damage but still >0 stone health.")
            enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
        return

    enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
    hit_duration = getattr(enemy, 'hit_duration', getattr(C, 'ENEMY_HIT_STUN_DURATION', 300))
    # hit_timer is now set, status effects or AI will check current_time_ms - hit_timer < hit_duration

    if enemy.current_health <= 0:
        if not getattr(enemy, 'is_dead', False):
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death', current_time_ms)
    else: # Still alive
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            if getattr(enemy, 'state', 'idle') != 'hit':
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not on fire. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit', current_time_ms)
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(enemy, 'state', 'N/A')}'")