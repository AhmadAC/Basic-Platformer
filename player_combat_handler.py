#################### START OF FILE: player_combat_handler.py ####################

# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles player combat: attacks, damage dealing/taking, healing for PySide6.
"""
# version 2.0.1 

from typing import List, Any # For type hints
import time # For get_current_ticks fallback

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game imports
import constants as C
# Projectiles are instantiated by Player class, not directly here, so no projectile class imports needed in this file.
from statue import Statue # Import Statue for type checking
from enemy import Enemy # Import Enemy for type checking (though not explicitly used for instanceof here currently)

try:
    from logger import debug, info # Assuming these are sufficient
except ImportError:
    def debug(msg): print(f"DEBUG_PCOMBAT: {msg}")
    def info(msg): print(f"INFO_PCOMBAT: {msg}")

_start_time_pcombat = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.

    """
    return int((time.monotonic() - _start_time_pcombat) * 1000)


def check_player_attack_collisions(player, targets_list: List[Any]):
    """
    Checks if the player's current attack hits any target in the list.
    Targets can be Enemies or Statues. Assumes player.rect, target.rect are QRectF.
    """
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive() or player.is_petrified:
        return

    # Position the attack hitbox (which is a QRectF attribute of player)
    # Player's rect center is player.rect.center() which returns a QPointF
    # Player's rect midright would be player.rect.right(), player.rect.center().y()

    if player.facing_right:
        player.attack_hitbox.moveTopLeft(player.rect.right(), player.rect.center().y() - player.attack_hitbox.height() / 2.0)
    else:
        player.attack_hitbox.moveTopRight(player.rect.left(), player.rect.center().y() - player.attack_hitbox.height() / 2.0)

    vertical_offset_for_crouch_attack = 0.0
    if player.is_crouching and player.attack_type == 4: # Assuming attack_type 4 is crouch_attack
        vertical_offset_for_crouch_attack = 10.0 # Pixels downwards

    # Adjust vertical position of hitbox based on player's center + offset
    new_hitbox_centery = player.rect.center().y() + vertical_offset_for_crouch_attack
    player.attack_hitbox.moveCenter(QPointF(player.attack_hitbox.center().x(), new_hitbox_centery))


    current_time_ms = get_current_ticks()

    for target_sprite in targets_list:
        if target_sprite is player or not hasattr(target_sprite, 'rect'): continue

        is_statue = isinstance(target_sprite, Statue)

        if is_statue:
            if player.attack_hitbox.intersects(target_sprite.rect): # QRectF.intersects()
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                    damage_to_inflict_on_statue = 0
                    if player.attack_type == 1: damage_to_inflict_on_statue = C.PLAYER_ATTACK1_DAMAGE
                    elif player.attack_type == 2: damage_to_inflict_on_statue = C.PLAYER_ATTACK2_DAMAGE
                    elif player.attack_type == 3: damage_to_inflict_on_statue = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif player.attack_type == 4: damage_to_inflict_on_statue = C.PLAYER_CROUCH_ATTACK_DAMAGE

                    if damage_to_inflict_on_statue > 0:
                        debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Statue {getattr(target_sprite, 'statue_id', 'Unknown')} for {damage_to_inflict_on_statue} damage.")
                        target_sprite.take_damage(damage_to_inflict_on_statue)
            continue

        # For other characters (Enemies, other Players)
        if not (hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and \
                hasattr(target_sprite, 'alive') and target_sprite.alive()):
            continue

        target_is_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                target_is_invincible = True
        if target_is_invincible: continue

        if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
            if player.attack_hitbox.intersects(target_sprite.rect):
                 if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    debug(f"Player {player.player_id} hit petrified target {getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))}. Smashing.")
                    target_sprite.smash_petrification()
            continue

        if player.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE

                if damage_to_inflict > 0:
                    target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Target {target_id_log} for {damage_to_inflict} damage.")
                    target_sprite.take_damage(damage_to_inflict)


def player_take_damage(player, damage_amount: int):
    current_time_ms = get_current_ticks()
    player_id_log = f"P{player.player_id}"

    if not player._valid_init or player.is_dead or not player.alive(): return
    if player.is_petrified:
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player is petrified/smashed.")
        return
    if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_cooldown):
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player in hit cooldown.")
        return

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health)
    debug(f"PlayerCombatHandler ({player_id_log}): Took {damage_amount} damage. Health: {player.current_health}/{player.max_health}")

    player.is_taking_hit = True
    player.hit_timer = current_time_ms

    if player.current_health <= 0:
        if not player.is_dead:
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            if hasattr(player, 'set_state'): player.set_state('death')
    else:
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        if not is_in_fire_visual_state:
            if player.state != 'hit':
                 if hasattr(player, 'set_state'): player.set_state('hit')
        else:
            if player.print_limiter.can_print(f"player_hit_while_on_fire_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Took damage while on fire. State remains '{player.state}'. is_taking_hit=True.")


def player_self_inflict_damage(player, damage_amount: int):
    if not player._valid_init or player.is_dead or not player.alive(): return
    player_take_damage(player, damage_amount) # Allow normal cooldown to apply for consistency

def player_heal_to_full(player):
    if not player._valid_init: return
    if player.is_petrified or player.is_stone_smashed:
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified/smashed.")
        return
    if player.is_dead and player.current_health <=0 :
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Setting health.")

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    if player.is_taking_hit: player.is_taking_hit = False
    if player.state == 'hit' and not player.is_dead:
        if hasattr(player, 'set_state'): player.set_state('idle')

#################### END OF FILE: player_combat_handler.py ####################