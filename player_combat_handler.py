# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles player combat: attacks, damage dealing/taking, healing for PySide6.
Now includes logic for smashing petrified targets.
"""
# version 2.0.4 (Added smashing petrified targets)

from typing import List, Any, Optional, TYPE_CHECKING
import time

from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor

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
    from logger import debug, info, warning # Added warning
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_PCOMBAT: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PCOMBAT: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PCOMBAT: {msg}")


_start_time_pcombat = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_pcombat) * 1000)


def check_player_attack_collisions(player: 'PlayerClass_TYPE', targets_list: List[Any]):
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive() or player.is_petrified: # Petrified players cannot attack
        return

    if not (hasattr(player, 'rect') and isinstance(player.rect, QRectF) and
            hasattr(player, 'attack_hitbox') and isinstance(player.attack_hitbox, QRectF)):
        debug(f"Player {player.player_id}: Missing or invalid rect/attack_hitbox for collision.")
        return
    if not hasattr(player.rect, 'right') or not hasattr(player.rect, 'center') or \
       not hasattr(player.attack_hitbox, 'height') or not hasattr(player.attack_hitbox, 'width'):
        debug(f"Player {player.player_id}: rect or attack_hitbox missing necessary methods (right, center, height, width).")
        return

    # Position the attack hitbox
    hitbox_half_height = player.attack_hitbox.height() / 2.0
    player_center_y = player.rect.center().y()

    if player.facing_right:
        top_left_x = player.rect.right()
        top_left_y = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x, top_left_y))
    else:
        top_left_x_facing_left = player.rect.left() - player.attack_hitbox.width()
        top_left_y_facing_left = player_center_y - hitbox_half_height
        player.attack_hitbox.moveTopLeft(QPointF(top_left_x_facing_left, top_left_y_facing_left))

    vertical_offset_for_crouch_attack = 0.0
    if player.is_crouching and player.attack_type == 4: # Assuming attack_type 4 is crouch attack
        vertical_offset_for_crouch_attack = 10.0 # Example offset, adjust as needed

    if vertical_offset_for_crouch_attack != 0.0:
        current_hitbox_center_x = player.attack_hitbox.center().x()
        new_hitbox_center_y_with_offset = player.attack_hitbox.center().y() + vertical_offset_for_crouch_attack
        player.attack_hitbox.moveCenter(QPointF(current_hitbox_center_x, new_hitbox_center_y_with_offset))

    current_time_ms = get_current_ticks_monotonic()

    for target_sprite in targets_list:
        if target_sprite is player or not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
             continue

        is_statue = isinstance(target_sprite, Statue)
        is_enemy_target = isinstance(target_sprite, Enemy) # To differentiate from other players

        # Check if target is generally valid for interaction (alive, initialized)
        # Statues have their own logic, other character types (players, enemies) need these checks.
        if not is_statue and not (
            hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and
            hasattr(target_sprite, 'is_dead') and # is_dead might be True for petrified things that aren't "gone"
            hasattr(target_sprite, 'alive') and target_sprite.alive()
        ):
            continue

        # --- Collision with the target's main rectangle ---
        if player.attack_hitbox.intersects(target_sprite.rect):
            # --- Handle Smashing Petrified Targets FIRST ---
            if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
                if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    target_id_log_petri = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', getattr(target_sprite, 'statue_id', 'UnknownPetrified')))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit PETRIFIED target {target_id_log_petri}. Smashing.")
                    target_sprite.smash_petrification()
                # Once smashed, skip normal damage for this attack hit on this target
                continue # Move to the next target in targets_list

            # --- Normal Damage and Hit Cooldown Logic (if not petrified or already smashed) ---
            target_is_invincible = False
            if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and hasattr(target_sprite, 'hit_cooldown'):
                if target_sprite.is_taking_hit and (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                    target_is_invincible = True
            
            if target_is_invincible:
                continue # Target is in hit cooldown

            # Deal damage
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE

                if damage_to_inflict > 0:
                    target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', getattr(target_sprite, 'statue_id', 'UnknownTarget')))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Target {target_id_log} for {damage_to_inflict} damage.")
                    target_sprite.take_damage(damage_to_inflict)

def player_take_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    current_time_ms = get_current_ticks_monotonic()
    player_id_log = f"P{player.player_id}"

    if not player._valid_init or not player.alive(): return # No damage if not valid or already "killed"

    # Petrified players (not smashed) effectively have stone "health" until smashed, so damage leads to smashing.
    # If already smashed, they are effectively gone.
    if player.is_petrified:
        if not player.is_stone_smashed:
            debug(f"PlayerCombatHandler ({player_id_log}): Petrified player took {damage_amount} damage. Triggering smash.")
            if hasattr(player, 'smash_petrification'):
                player.smash_petrification()
        else:
            debug(f"PlayerCombatHandler ({player_id_log}): Smashed player took {damage_amount} damage. Ignoring further damage.")
        return

    # Zapped, Frozen, Defrosting players might still take health damage but their state/animation takes precedence
    # over a standard 'hit' state unless the hit kills them.
    if player.is_zapped or player.is_frozen or player.is_defrosting:
        if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_cooldown):
            debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player zapped/frozen and in hit cooldown.")
            return # Still respect hit cooldown
    elif player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_cooldown):
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player in standard hit cooldown.")
        return

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health)
    debug(f"PlayerCombatHandler ({player_id_log}): Took {damage_amount} damage. Health: {player.current_health}/{player.max_health}")

    if not player.is_petrified: # Only set hit state if not petrified (petrified handles its own visuals)
        player.is_taking_hit = True
        player.hit_timer = current_time_ms

    if player.current_health <= 0:
        if not player.is_dead: # Only trigger death state once
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            if hasattr(player, 'set_state'): player.set_state('death')
    else: # Still alive
        is_in_interrupting_status_state = player.is_aflame or player.is_deflaming or \
                                          player.is_frozen or player.is_defrosting or \
                                          player.is_zapped # Zapped player shows zapped animation, not hit

        if not is_in_interrupting_status_state and not player.is_petrified:
            if player.state != 'hit':
                 if hasattr(player, 'set_state'): player.set_state('hit')
        else:
             if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_hit_while_status_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Took damage while in status state ('{player.state}'). In hit cooldown, but visual state prioritized.")


def player_self_inflict_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    if not player._valid_init or player.is_dead or not player.alive(): return
    # Self-inflicted damage usually bypasses hit cooldowns
    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health)
    debug(f"PlayerCombatHandler (P{player.player_id}): Self-inflicted {damage_amount} damage. Health: {player.current_health}/{player.max_health}")
    if player.current_health <= 0 and not player.is_dead:
        if hasattr(player, 'set_state'): player.set_state('death')

def player_heal_to_full(player: 'PlayerClass_TYPE'):
    if not player._valid_init: return
    if player.is_petrified: # Can't heal if petrified
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified.")
        return

    if player.is_dead and player.current_health <=0 :
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Reviving and setting health.")
        player.is_dead = False
        player.death_animation_finished = False
        # Player might still be in a status effect like aflame/frozen/zapped, healing doesn't clear those.

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    if player.is_taking_hit: player.is_taking_hit = False

    # If healed while in hit or death anim (but not truly "gone"), transition to a more appropriate state
    if player.state in ['hit', 'death', 'death_nm'] and not player.is_dead:
        # Determine next state based on current conditions, respecting status effects
        next_state_after_heal = 'idle'
        if player.is_aflame: next_state_after_heal = 'burning_crouch' if player.is_crouching else 'burning'
        elif player.is_deflaming: next_state_after_heal = 'deflame_crouch' if player.is_crouching else 'deflame'
        elif player.is_frozen: next_state_after_heal = 'frozen' # Remain frozen visually
        elif player.is_defrosting: next_state_after_heal = 'defrost' # Remain defrosting
        elif player.is_zapped: next_state_after_heal = 'zapped' # Remain zapped
        elif not player.on_ground: next_state_after_heal = 'fall'
        elif player.is_crouching: next_state_after_heal = 'crouch'

        if hasattr(player, 'set_state'):
            player.set_state(next_state_after_heal)