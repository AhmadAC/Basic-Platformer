# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles player combat: attacks, damage dealing/taking, healing for PySide6.
"""
# version 2.0.2 (Fixed QRectF.moveTopLeft/Right argument to QPointF)

from typing import List, Any, Optional, TYPE_CHECKING # Added Optional, TYPE_CHECKING
import time 

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF, QSize, Qt # QSize, Qt not directly used but good for context

# Game imports
import constants as C
from statue import Statue 
from enemy import Enemy 

if TYPE_CHECKING: # To avoid circular import issues at runtime but allow type hinting
    from player import Player as PlayerClass_TYPE # If Player class is in player.py

try:
    from logger import debug, info 
except ImportError:
    def debug(msg): print(f"DEBUG_PCOMBAT: {msg}")
    def info(msg): print(f"INFO_PCOMBAT: {msg}")

_start_time_pcombat = time.monotonic()
def get_current_ticks_monotonic(): # Renamed for clarity
    """
    Returns the number of milliseconds since this module was initialized.
    """
    return int((time.monotonic() - _start_time_pcombat) * 1000)


def check_player_attack_collisions(player: 'PlayerClass_TYPE', targets_list: List[Any]):
    """
    Checks if the player's current attack hits any target in the list.
    Targets can be Enemies or Statues. Assumes player.rect, target.rect are QRectF.
    """
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive() or player.is_petrified:
        return

    # Ensure rect and attack_hitbox are valid QRectF instances
    if not (hasattr(player, 'rect') and isinstance(player.rect, QRectF) and
            hasattr(player, 'attack_hitbox') and isinstance(player.attack_hitbox, QRectF)):
        debug(f"Player {player.player_id}: Missing or invalid rect/attack_hitbox for collision.")
        return
    if not hasattr(player.rect, 'right') or not hasattr(player.rect, 'center') or \
       not hasattr(player.attack_hitbox, 'height') or not hasattr(player.attack_hitbox, 'width'):
        debug(f"Player {player.player_id}: rect or attack_hitbox missing necessary methods (right, center, height, width).")
        return


    # Position the attack hitbox
    # The y-coordinate for the top-left/top-right should center the hitbox vertically relative to the player's rect center.
    hitbox_half_height = player.attack_hitbox.height() / 2.0
    player_center_y = player.rect.center().y()
    
    if player.facing_right:
        top_left_x = player.rect.right()
        top_left_y = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x, top_left_y))
    else: # Facing left
        # moveTopRight moves the top-right corner to the specified QPointF
        # So, the x for top-right is player.rect.left()
        # The y for top-right is still player_center_y - hitbox_half_height
        # Alternatively, calculate top-left and use moveTopLeft for consistency:
        top_left_x_facing_left = player.rect.left() - player.attack_hitbox.width()
        top_left_y_facing_left = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x_facing_left, top_left_y_facing_left))


    # Further adjust hitbox vertically for crouch attack
    vertical_offset_for_crouch_attack = 0.0
    if player.is_crouching and player.attack_type == 4: # Assuming attack_type 4 is crouch_attack
        vertical_offset_for_crouch_attack = 10.0 # Pixels downwards, adjust as needed

    if vertical_offset_for_crouch_attack != 0.0:
        # moveCenter expects a QPointF for the new center.
        # Only adjust the Y center if there's an offset.
        current_hitbox_center_x = player.attack_hitbox.center().x()
        new_hitbox_center_y_with_offset = player.attack_hitbox.center().y() + vertical_offset_for_crouch_attack
        player.attack_hitbox.moveCenter(QPointF(current_hitbox_center_x, new_hitbox_center_y_with_offset))


    current_time_ms = get_current_ticks_monotonic()

    for target_sprite in targets_list:
        if target_sprite is player or not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
             continue # Skip self or invalid targets

        is_statue = isinstance(target_sprite, Statue)

        if is_statue:
            if player.attack_hitbox.intersects(target_sprite.rect): 
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False): # Don't damage already smashed statues
                    damage_to_inflict_on_statue = 0
                    if player.attack_type == 1: damage_to_inflict_on_statue = C.PLAYER_ATTACK1_DAMAGE
                    elif player.attack_type == 2: damage_to_inflict_on_statue = C.PLAYER_ATTACK2_DAMAGE
                    elif player.attack_type == 3: damage_to_inflict_on_statue = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif player.attack_type == 4: damage_to_inflict_on_statue = C.PLAYER_CROUCH_ATTACK_DAMAGE

                    if damage_to_inflict_on_statue > 0:
                        debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Statue {getattr(target_sprite, 'statue_id', 'Unknown')} for {damage_to_inflict_on_statue} damage.")
                        target_sprite.take_damage(damage_to_inflict_on_statue)
            continue # Move to next target after processing statue

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


def player_take_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    current_time_ms = get_current_ticks_monotonic()
    player_id_log = f"P{player.player_id}"

    if not player._valid_init or player.is_dead or not player.alive(): return
    if player.is_petrified: # Smashed state is handled by is_dead or not alive()
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player is petrified.")
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
        if not player.is_dead: # Only set to death state once
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            if hasattr(player, 'set_state'): player.set_state('death') # set_state handles is_dead = True
    else: # Player still has health
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        if not is_in_fire_visual_state: # Don't interrupt fire animation with hit animation
            if player.state != 'hit': # Only transition to 'hit' if not already in it
                 if hasattr(player, 'set_state'): player.set_state('hit')
        else: # Player is on fire and took damage
            if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"player_hit_while_on_fire_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Took damage while on fire. State remains '{player.state}'. is_taking_hit=True.")


def player_self_inflict_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    if not player._valid_init or player.is_dead or not player.alive(): return
    player_take_damage(player, damage_amount) 

def player_heal_to_full(player: 'PlayerClass_TYPE'):
    if not player._valid_init: return
    if player.is_petrified or player.is_stone_smashed:
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified/smashed.")
        return
    # If player was "dead" (health 0) but not petrified/smashed, healing revives them.
    if player.is_dead and player.current_health <=0 :
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Reviving and setting health.")
        player.is_dead = False # Revive
        player.death_animation_finished = False # Reset death animation flag

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    if player.is_taking_hit: player.is_taking_hit = False # Clear hit stun
    
    # If player was in 'hit' or 'death' state visually, transition to appropriate idle/fall state
    if player.state in ['hit', 'death', 'death_nm'] and not player.is_dead: # Check is_dead again as it was just reset
        if hasattr(player, 'set_state'):
            next_state = 'idle' if player.on_ground else 'fall'
            player.set_state(next_state)