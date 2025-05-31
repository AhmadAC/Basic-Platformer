#################### START OF FILE: player\player_combat_handler.py ####################
# player/player_combat_handler.py
# -*- coding: utf-8 -*-
"""
Handles player combat: attacks, damage dealing/taking, healing for PySide6.
Statues are now destructible by player attacks if their health allows.
MODIFIED: Corrected import path for logger and relative import for set_player_state.
"""
# version 2.0.5 (Corrected import paths)

from typing import List, Any, Optional, TYPE_CHECKING
import time

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor

# --- Project Root Setup ---
import os
import sys
_PLAYER_COMBAT_HANDLER_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_PLAYER_COMBAT_HANDLER = os.path.dirname(_PLAYER_COMBAT_HANDLER_PY_FILE_DIR) # Up one level to 'player'
if _PROJECT_ROOT_FOR_PLAYER_COMBAT_HANDLER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_PLAYER_COMBAT_HANDLER) # Add 'player' package's parent
_PROJECT_ROOT_GRANDPARENT_COMBAT_PLAYER = os.path.dirname(_PROJECT_ROOT_FOR_PLAYER_COMBAT_HANDLER) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_COMBAT_PLAYER not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_COMBAT_PLAYER) # Add actual project root
# --- End Project Root Setup ---


# Game imports
import main_game.constants as C
from player.statue import Statue # Assuming Statue is in player.statue
from enemy import Enemy         # Assuming Enemy is in enemy package at project root

if TYPE_CHECKING:
    from .player import Player as PlayerClass_TYPE # Relative import for Player type hint

# --- Logger Setup ---
import logging
_player_combat_logger_instance = logging.getLogger(__name__ + "_player_combat_internal_fallback")
if not _player_combat_logger_instance.hasHandlers():
    _handler_pc_fb = logging.StreamHandler(sys.stdout)
    _formatter_pc_fb = logging.Formatter('PLAYER_COMBAT (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_pc_fb.setFormatter(_formatter_pc_fb)
    _player_combat_logger_instance.addHandler(_handler_pc_fb)
    _player_combat_logger_instance.setLevel(logging.DEBUG)
    _player_combat_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _player_combat_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _player_combat_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _player_combat_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _player_combat_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _player_combat_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("PlayerCombatHandler: Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL PLAYER_COMBAT_HANDLER: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_pc:
    critical(f"CRITICAL PLAYER_COMBAT_HANDLER: Unexpected error during logger setup from main_game.logger: {e_logger_init_pc}. Using internal fallback.")
# --- End Logger Setup ---


_PSH_COMBAT_AVAILABLE = True
try:
    from .player_state_handler import set_player_state # Relative import
except ImportError as e_psh_combat_import:
    critical(f"PLAYER_COMBAT_HANDLER: Failed to import set_player_state from .player_state_handler: {e_psh_combat_import}")
    _PSH_COMBAT_AVAILABLE = False
    def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"PLAYER_COMBAT_HANDLER: Fallback set_player_state used for P{getattr(player, 'player_id', 'N/A')} to '{new_state}'")


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
    if player.is_crouching and player.attack_type == 4:
        vertical_offset_for_crouch_attack = 10.0

    if vertical_offset_for_crouch_attack != 0.0:
        current_hitbox_center_x = player.attack_hitbox.center().x()
        new_hitbox_center_y_with_offset = player.attack_hitbox.center().y() + vertical_offset_for_crouch_attack
        player.attack_hitbox.moveCenter(QPointF(current_hitbox_center_x, new_hitbox_center_y_with_offset))

    current_time_ms = get_current_ticks_monotonic()

    for target_sprite in targets_list:
        if target_sprite is player or not hasattr(target_sprite, 'rect') or not isinstance(target_sprite.rect, QRectF):
             continue

        is_statue = isinstance(target_sprite, Statue)
        if is_statue:
            if player.attack_hitbox.intersects(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False):
                    damage_to_inflict_on_statue = 0
                    if player.attack_type == 1: damage_to_inflict_on_statue = C.PLAYER_ATTACK1_DAMAGE
                    elif player.attack_type == 2: damage_to_inflict_on_statue = C.PLAYER_ATTACK2_DAMAGE
                    elif player.attack_type == 3: damage_to_inflict_on_statue = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif player.attack_type == 4: damage_to_inflict_on_statue = C.PLAYER_CROUCH_ATTACK_DAMAGE
                    if damage_to_inflict_on_statue > 0:
                        statue_id_log = getattr(target_sprite, 'statue_id', 'UnknownStatue')
                        debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Statue {statue_id_log} for {damage_to_inflict_on_statue} damage.")
                        target_sprite.take_damage(damage_to_inflict_on_statue)
            continue

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
                    target_id_log_petri = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownPetrified'))
                    debug(f"Player {player.player_id} hit petrified target {target_id_log_petri}. Smashing.")
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
                    target_id_log_gen = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'UnknownTarget'))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Target {target_id_log_gen} for {damage_to_inflict} damage.")
                    target_sprite.take_damage(damage_to_inflict)


def player_take_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    if not _PSH_COMBAT_AVAILABLE:
        critical("PLAYER_COMBAT_HANDLER: set_player_state function is not available. Cannot process player_take_damage correctly.")
        return

    current_time_ms = get_current_ticks_monotonic()
    player_id_log = f"P{player.player_id}"

    if not player._valid_init or player.is_dead or not player.alive(): return
    if player.is_petrified:
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
        if not player.is_dead:
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            set_player_state(player, 'death', current_time_ms) # Use imported handler
    else:
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        if not is_in_fire_visual_state:
            if player.state != 'hit':
                 set_player_state(player, 'hit', current_time_ms) # Use imported handler
        else:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_hit_while_on_fire_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Was aflame/deflaming. Took damage, in hit cooldown, remains visually on fire. State: '{getattr(player, 'state', 'N/A')}'")


def player_self_inflict_damage(player: 'PlayerClass_TYPE', damage_amount: int):
    if not player._valid_init or player.is_dead or not player.alive(): return
    player_take_damage(player, damage_amount)

def player_heal_to_full(player: 'PlayerClass_TYPE'):
    if not _PSH_COMBAT_AVAILABLE:
        critical("PLAYER_COMBAT_HANDLER: set_player_state function is not available. Cannot process player_heal_to_full correctly.")
        return

    if not player._valid_init: return
    if player.is_petrified or player.is_stone_smashed:
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified/smashed.")
        return

    if player.is_dead and player.current_health <=0 :
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Reviving and setting health.")
        player.is_dead = False
        player.death_animation_finished = False

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    if player.is_taking_hit: player.is_taking_hit = False

    if player.state in ['hit', 'death', 'death_nm'] and not player.is_dead:
        next_state = 'idle' if player.on_ground else 'fall'
        set_player_state(player, next_state, get_current_ticks_monotonic()) # Use imported handler

#################### END OF FILE: player/player_combat_handler.py ####################