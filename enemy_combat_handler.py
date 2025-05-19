#################### START OF FILE: enemy_combat_handler.py ####################

# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy combat mechanics for PySide6: checking attack collisions and processing damage.
"""
# version 2.0.1 (PySide6 Refactor - Corrected enemy.facing_right)

from typing import List, Any 

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF 

# Game imports
import constants as C
from statue import Statue 

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

try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_combat = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_combat) * 1000)


def check_enemy_attack_collisions(enemy, hittable_targets_list: List[Any]):
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_petrified: return
    if not enemy._valid_init or not enemy.is_attacking or enemy.is_dead or not enemy.alive(): return

    # Corrected: Use enemy.facing_right
    if enemy.facing_right:
        new_x = enemy.rect.right()
        new_y = enemy.rect.center().y() - enemy.attack_hitbox.height() / 2.0
        enemy.attack_hitbox.moveTopLeft(new_x, new_y)
    else: 
        new_x = enemy.rect.left() - enemy.attack_hitbox.width()
        new_y = enemy.rect.center().y() - enemy.attack_hitbox.height() / 2.0
        enemy.attack_hitbox.moveTopLeft(new_x, new_y)
    
    current_time_ms = get_current_ticks()

    for target_sprite in hittable_targets_list:
        if not hasattr(target_sprite, 'rect'): continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if enemy.attack_hitbox.intersects(target_sprite.rect): 
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    damage_to_statue = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                    debug(f"Enemy {enemy.enemy_id} hit Statue {target_sprite.statue_id} for {damage_to_statue} damage.")
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
        if getattr(target_sprite, 'is_petrified', False): continue

        if enemy.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_target = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                debug(f"Enemy {enemy.enemy_id} (Color: {enemy.color_name}) hit Target {target_id_log} for {damage_to_target} damage.")
                target_sprite.take_damage(damage_to_target)


def enemy_take_damage(enemy, damage_amount: int):
    current_time_ms = get_current_ticks()
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    
    if not enemy._valid_init or not enemy.alive(): return
    if enemy.is_dead and not enemy.is_petrified: return
    if enemy.is_stone_smashed: return
    if enemy.is_taking_hit and (current_time_ms - enemy.hit_timer < enemy.hit_cooldown): return
    if enemy.is_frozen or enemy.is_defrosting: return

    was_aflame_before_hit = enemy.is_aflame
    was_deflaming_before_hit = enemy.is_deflaming

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health)
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {enemy.color_name}) took {damage_amount} damage. Health: {enemy.current_health}/{enemy.max_health}.")

    if enemy.is_petrified:
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
        if not enemy.is_dead:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death')
    else:
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            if enemy.state != 'hit':
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not on fire. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit')
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire.")

#################### END OF FILE: enemy_combat_handler.py ####################