# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy combat mechanics for PySide6: checking attack collisions and processing damage.
"""
# version 2.0.4 (Ensured QPointF passed to moveTopLeft, refined logic slightly)

import time 
from typing import List, Any, TYPE_CHECKING, Optional # Added Optional

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# Game imports
import constants as C
from statue import Statue

if TYPE_CHECKING: 
    from enemy import Enemy as EnemyClass_TYPE

# It's better to import set_enemy_state locally within functions that need it
# if there's a risk of circular dependencies, or ensure it's always available.
# For now, assuming it's safe at module level or player_state_handler doesn't import this.
try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state): # Fallback
        if hasattr(enemy, 'set_state') and callable(enemy.set_state): 
            enemy.set_state(new_state)
        elif hasattr(enemy, 'state'): # Direct assignment if set_state missing
            enemy.state = new_state
            print(f"CRITICAL ENEMY_COMBAT_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}. Directly set state.")
        else:
            print(f"CRITICAL ENEMY_COMBAT_HANDLER: Cannot set state for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}. Missing 'set_state' and 'state'.")


try:
    from logger import debug, warning # Added warning for safety
except ImportError:
    def debug(msg): print(f"DEBUG_ECOMBAT: {msg}")
    def warning(msg): print(f"WARNING_ECOMBAT: {msg}")


_start_time_enemy_combat_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_combat_monotonic) * 1000)


def check_enemy_attack_collisions(enemy: 'EnemyClass_TYPE', hittable_targets_list: List[Any]):
    if not getattr(enemy, '_valid_init', False) or \
       not getattr(enemy, 'is_attacking', False) or \
       getattr(enemy, 'is_dead', True) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_petrified', False): # Petrified enemies usually don't attack
        return

    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and
            hasattr(enemy, 'attack_hitbox') and isinstance(enemy.attack_hitbox, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing rect or attack_hitbox for collision check.")
        return
    
    # Ensure methods exist before calling
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

    for target_sprite in hittable_targets_list:
        if not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
            continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    damage_to_statue = int(getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)) # Ensure int
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} hit Statue {getattr(target_sprite, 'statue_id', 'N/A')} for {damage_to_statue} damage.")
                    target_sprite.take_damage(damage_to_statue)
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
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} hit petrified target {getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))}. Smashing.")
                    target_sprite.smash_petrification()
            continue

        if enemy.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_target = int(getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)) # Ensure int
                target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                enemy_color_log = getattr(enemy, 'color_name', 'N/A')
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log}) hit Target {target_id_log} for {damage_to_target} damage.")
                target_sprite.take_damage(damage_to_target)


def enemy_take_damage(enemy: 'EnemyClass_TYPE', damage_amount: int):
    current_time_ms = get_current_ticks_monotonic()
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    if not getattr(enemy, '_valid_init', False) or not (hasattr(enemy, 'alive') and enemy.alive()): return
    if getattr(enemy, 'is_dead', False) and not getattr(enemy, 'is_petrified', False) : return # Already dead and not just a stone
    if getattr(enemy, 'is_stone_smashed', False): return # Smashed stone cannot take more damage
    
    # Check hit cooldown only if not petrified (petrified things can be repeatedly hit to break)
    if not getattr(enemy, 'is_petrified', False):
        if getattr(enemy, 'is_taking_hit', False) and \
           (current_time_ms - getattr(enemy, 'hit_timer', 0) < getattr(enemy, 'hit_cooldown', 500)):
            return
    
    if getattr(enemy, 'is_frozen', False) or getattr(enemy, 'is_defrosting', False): return # Frozen things don't take damage this way

    was_aflame_before_hit = getattr(enemy, 'is_aflame', False)
    was_deflaming_before_hit = getattr(enemy, 'is_deflaming', False)

    # Ensure current_health and max_health exist
    if not hasattr(enemy, 'current_health') or not hasattr(enemy, 'max_health'):
        warning(f"Enemy {enemy_id_log} missing health attributes. Cannot take damage.")
        return

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health)
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}) took {damage_amount} damage. Health: {enemy.current_health}/{enemy.max_health}.")

    if getattr(enemy, 'is_petrified', False): # Not smashed yet, but petrified
        if enemy.current_health <= 0:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} health 0. Smashing.")
            from enemy_status_effects import smash_petrified_enemy # Lazy import for potential circularity
            smash_petrified_enemy(enemy)
        else: # Petrified but still has "stone health"
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} took damage but still >0 stone health.")
            enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms # Can still show a "hit" effect on stone
        return

    enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
    if enemy.current_health <= 0:
        if not getattr(enemy, 'is_dead', False): # Only trigger death state once
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death') # This should handle is_dead = True
    else: # Still alive
        if not was_aflame_before_hit and not was_deflaming_before_hit: # If not on fire, go to hit state
            if getattr(enemy, 'state', 'idle') != 'hit':
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not on fire. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit')
        # If was on fire, it remains visually on fire but is in hit stun duration
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(enemy, 'state', 'N/A')}'")