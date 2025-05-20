# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy combat mechanics for PySide6: checking attack collisions and processing damage.
"""
# version 2.0.3 (Fixed QRectF.moveTopLeft() argument)

import time # For monotonic timer
from typing import List, Any, TYPE_CHECKING

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# Game imports
import constants as C
from statue import Statue

if TYPE_CHECKING: # To avoid circular import issues at runtime but allow type hinting
    from enemy import Enemy as EnemyClass_TYPE

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): enemy.set_state(new_state)
        else: print(f"CRITICAL ENEMY_COMBAT_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

try:
    from logger import debug
except ImportError:
    def debug(msg): print(f"DEBUG_ECOMBAT: {msg}")

# --- Monotonic Timer ---
_start_time_enemy_combat_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_combat_monotonic) * 1000)
# --- End Monotonic Timer ---


def check_enemy_attack_collisions(enemy: 'EnemyClass_TYPE', hittable_targets_list: List[Any]):
    # Ensure enemy object and its attributes are valid before proceeding
    if not getattr(enemy, '_valid_init', False) or \
       not getattr(enemy, 'is_attacking', False) or \
       getattr(enemy, 'is_dead', True) or \
       not (hasattr(enemy, 'alive') and enemy.alive()) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_petrified', False):
        return

    # Ensure rect and attack_hitbox are QRectF and have necessary methods
    if not (hasattr(enemy, 'rect') and isinstance(enemy.rect, QRectF) and
            hasattr(enemy, 'attack_hitbox') and isinstance(enemy.attack_hitbox, QRectF)):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Missing rect or attack_hitbox for collision check.")
        return

    # Correctly position the attack hitbox based on enemy's facing direction and current rect
    # enemy.rect.center().y() gives the y-coordinate of the center of the enemy's main rect
    # enemy.attack_hitbox.height() is the height of the attack hitbox itself
    if getattr(enemy, 'facing_right', True):
        new_x = enemy.rect.right() # Hitbox starts at the right edge of the enemy
        # Vertically align the hitbox's center with the enemy's main rect's center
        new_y = enemy.rect.center().y() - (enemy.attack_hitbox.height() / 2.0)
        enemy.attack_hitbox.moveTopLeft(QPointF(new_x, new_y)) # Pass QPointF
    else: # Facing left
        # Hitbox starts at the left edge of the enemy, minus its own width
        new_x = enemy.rect.left() - enemy.attack_hitbox.width()
        new_y = enemy.rect.center().y() - (enemy.attack_hitbox.height() / 2.0)
        enemy.attack_hitbox.moveTopLeft(QPointF(new_x, new_y)) # Pass QPointF

    current_time_ms = get_current_ticks_monotonic()

    for target_sprite in hittable_targets_list:
        if not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
            continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if enemy.attack_hitbox.intersects(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    damage_to_statue = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} hit Statue {getattr(target_sprite, 'statue_id', 'N/A')} for {damage_to_statue} damage.")
                    target_sprite.take_damage(damage_to_statue)
            continue # Process next target

        # Check for general character validity
        if not (hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and \
                hasattr(target_sprite, 'alive') and target_sprite.alive()):
            continue

        # Check for invincibility or petrification
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
                damage_to_target = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                enemy_color_log = getattr(enemy, 'color_name', 'N/A')
                debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy_color_log}) hit Target {target_id_log} for {damage_to_target} damage.")
                target_sprite.take_damage(damage_to_target)


def enemy_take_damage(enemy: 'EnemyClass_TYPE', damage_amount: int):
    current_time_ms = get_current_ticks_monotonic()
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    if not getattr(enemy, '_valid_init', False) or not (hasattr(enemy, 'alive') and enemy.alive()): return
    if getattr(enemy, 'is_dead', False) and not getattr(enemy, 'is_petrified', False) : return
    if getattr(enemy, 'is_stone_smashed', False): return
    if getattr(enemy, 'is_taking_hit', False) and \
       (current_time_ms - getattr(enemy, 'hit_timer', 0) < getattr(enemy, 'hit_cooldown', 500)): return
    if getattr(enemy, 'is_frozen', False) or getattr(enemy, 'is_defrosting', False): return

    was_aflame_before_hit = getattr(enemy, 'is_aflame', False)
    was_deflaming_before_hit = getattr(enemy, 'is_deflaming', False)

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health)
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}) took {damage_amount} damage. Health: {enemy.current_health}/{getattr(enemy, 'max_health', 0)}.")

    if getattr(enemy, 'is_petrified', False):
        if enemy.current_health <= 0:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} health 0. Smashing.")
            from enemy_status_effects import smash_petrified_enemy
            smash_petrified_enemy(enemy)
        else:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} took damage but still >0 health.")
            enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
        return

    enemy.is_taking_hit = True; enemy.hit_timer = current_time_ms
    if enemy.current_health <= 0:
        if not getattr(enemy, 'is_dead', False):
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death')
    else:
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            if getattr(enemy, 'state', 'idle') != 'hit':
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not on fire. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit')
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(enemy, 'state', 'N/A')}'")