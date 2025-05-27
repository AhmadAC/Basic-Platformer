# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles player combat: attacks, damage dealing/taking, healing for PySide6.
Statues are now destructible by player attacks if their health allows.
"""
# version 2.0.4 (Refined logging for statue interaction)

from typing import List, Any, Optional, TYPE_CHECKING
import time

from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor # Added QColor for type hinting

import constants as C
from statue import Statue
from enemy import Enemy

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE

try:
    from player_state_handler import set_player_state
except ImportError:
    print(f"CRITICAL PLAYER_COMBAT_HANDLER: player_state_handler.set_player_state not found.")
    def set_player_state(player, new_state):
        if hasattr(player, 'state'): player.state = new_state
        else: print(f"CRITICAL PLAYER_COMBAT_HANDLER (Fallback): Cannot set state for Player ID {getattr(player, 'player_id', 'N/A')}.")


try:
    from logger import debug, info
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_PCOMBAT: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PCOMBAT: {msg}")

_start_time_pcombat = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_pcombat) * 1000)


def check_player_attack_collisions(player: 'PlayerClass_TYPE', targets_list: List[Any]):
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive() or player.is_petrified:
        return

    if not (hasattr(player, 'rect') and isinstance(player.rect, QRectF) and
            hasattr(player, 'attack_hitbox') and isinstance(player.attack_hitbox, QRectF)):
        debug(f"Player {player.player_id}: Missing or invalid rect/attack_hitbox for collision.")
        return
    if not hasattr(player.rect, 'right') or not hasattr(player.rect, 'center') or \
       not hasattr(player.attack_hitbox, 'height') or not hasattr(player.attack_hitbox, 'width'):
        debug(f"Player {player.player_id}: rect or attack_hitbox missing necessary methods (right, center, height, width).")
        return

    # Position the attack hitbox based on player facing and state
    hitbox_half_height = player.attack_hitbox.height() / 2.0
    player_center_y = player.rect.center().y()
    
    if player.facing_right:
        top_left_x = player.rect.right()
        top_left_y = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x, top_left_y))
    else: # Facing left
        top_left_x_facing_left = player.rect.left() - player.attack_hitbox.width()
        top_left_y_facing_left = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x_facing_left, top_left_y_facing_left))

    # Adjust hitbox vertically for crouch attack
    vertical_offset_for_crouch_attack = 0.0
    if player.is_crouching and player.attack_type == 4: # Assuming attack_type 4 is crouch_attack
        vertical_offset_for_crouch_attack = 10.0 # Example offset, adjust as needed

    if vertical_offset_for_crouch_attack != 0.0:
        current_hitbox_center_x = player.attack_hitbox.center().x()
        new_hitbox_center_y_with_offset = player.attack_hitbox.center().y() + vertical_offset_for_crouch_attack
        player.attack_hitbox.moveCenter(QPointF(current_hitbox_center_x, new_hitbox_center_y_with_offset))

    current_time_ms = get_current_ticks_monotonic()

    for target_sprite in targets_list:
        # Basic validity checks for the target
        if target_sprite is player or not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
             continue

        is_statue = isinstance(target_sprite, Statue)

        if is_statue:
            if player.attack_hitbox.intersects(target_sprite.rect):
                # Check if the statue can take damage and isn't already smashed
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False): # Statues are "alive" until smashed

                    damage_to_inflict_on_statue = 0
                    if player.attack_type == 1: damage_to_inflict_on_statue = C.PLAYER_ATTACK1_DAMAGE
                    elif player.attack_type == 2: damage_to_inflict_on_statue = C.PLAYER_ATTACK2_DAMAGE
                    elif player.attack_type == 3: damage_to_inflict_on_statue = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif player.attack_type == 4: damage_to_inflict_on_statue = C.PLAYER_CROUCH_ATTACK_DAMAGE

                    if damage_to_inflict_on_statue > 0:
                        statue_id_log = getattr(target_sprite, 'statue_id', 'UnknownStatue')
                        debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Statue {statue_id_log} for {damage_to_inflict_on_statue} damage.")
                        target_sprite.take_damage(damage_to_inflict_on_statue)
            continue # Processed statue, move to next char in targets_list

        # For other characters (Enemies, other Players)
        if not (hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and \
                hasattr(target_sprite, 'alive') and target_sprite.alive()):
            continue # Skip invalid or already "truly" dead targets

        # Invincibility check (hit cooldown)
        target_is_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                target_is_invincible = True
        if target_is_invincible: continue

        # Petrified target handling
        if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
            if player.attack_hitbox.intersects(target_sprite.rect):
                 if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    target_id_log_petri = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownPetrified'))
                    debug(f"Player {player.player_id} hit petrified target {target_id_log_petri}. Smashing.")
                    target_sprite.smash_petrification()
            continue # Processed petrified target

        # General target damage
        if player.attack_hitbox.intersects(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE

                if damage_to_inflict > 0:
                    target_id_log_gen = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Target {target_id_log_gen} for {damage_to_inflict} damage.")
                    target_sprite.take_damage(damage_to_inflict)


def player_take_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    current_time_ms = get_current_ticks_monotonic()
    player_id_log = f"P{player.player_id}"

    if not player._valid_init or player.is_dead or not player.alive(): return # Already dead
    if player.is_petrified: # Petrified players are immune to normal damage
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player is petrified.")
        return
    if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_cooldown):
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player in hit cooldown.")
        return

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health) # Clamp health at 0
    debug(f"PlayerCombatHandler ({player_id_log}): Took {damage_amount} damage. Health: {player.current_health}/{player.max_health}")

    player.is_taking_hit = True # Start hit stun
    player.hit_timer = current_time_ms # Record time of hit

    if player.current_health <= 0:
        if not player.is_dead: # Only trigger death state once
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            if hasattr(player, 'set_state'): player.set_state('death') # Player.set_state handles setting is_dead
    else: # Still alive
        # If not on fire, go to 'hit' state. If on fire, it stays visually on fire but is in hit stun.
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        if not is_in_fire_visual_state: # If not on fire, go to hit state
            if player.state != 'hit': # Only change to hit if not already in hit state
                 if hasattr(player, 'set_state'): player.set_state('hit')
        else: # Was on fire, took damage, remains visually on fire but is in hit cooldown
            if player.print_limiter.can_log(f"player_hit_while_on_fire_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(player, 'state', 'N/A')}'")


def player_self_inflict_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    if not player._valid_init or player.is_dead or not player.alive(): return
    # Self-inflicted damage might bypass normal hit stun/cooldown if desired,
    # but for now, it uses the standard take_damage logic.
    player_take_damage(player, damage_amount) # This will apply hit stun etc.

def player_heal_to_full(player: 'PlayerClass_TYPE'):
    if not player._valid_init: return
    if player.is_petrified or player.is_stone_smashed:
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified/smashed.")
        return
    
    if player.is_dead and player.current_health <=0 :
        # If healing can revive, reset death flags
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Reviving and setting health.")
        player.is_dead = False # No longer dead
        player.death_animation_finished = False # Reset death animation flag

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    # Clear hit stun if healing occurs
    if player.is_taking_hit: player.is_taking_hit = False 
    
    # If was in a death or hit state, transition to a neutral state if not dead anymore
    if player.state in ['hit', 'death', 'death_nm'] and not player.is_dead: 
        if hasattr(player, 'set_state'):
            next_state = 'idle' if player.on_ground else 'fall'
            player.set_state(next_state)