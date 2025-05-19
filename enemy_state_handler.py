# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy state transitions and associated logic for PySide6.
"""
# version 2.0.1 

import time # For monotonic timer
from typing import Optional

# PySide6 imports
from PySide6.QtCore import QPointF

# Game imports
import constants as C

try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    def update_enemy_animation(enemy):
        if hasattr(enemy, 'animate'):
            enemy.animate()
        else:
            print(f"CRITICAL ENEMY_STATE_HANDLER: enemy_animation_handler.update_enemy_animation not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# Logger import
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATE_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# --- Monotonic Timer ---
_start_time_enemy_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_state_monotonic) * 1000)
# --- End Monotonic Timer ---


def set_enemy_state(enemy, new_state: str):
    """
    Sets the enemy's logical state, handling transitions and state-specific initializations.
    Calls update_enemy_animation to refresh visuals if the state changes.
    """
    if not getattr(enemy, '_valid_init', False): # Safer check
        debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {getattr(enemy, 'enemy_id', 'N/A')}. Ignoring.")
        return

    current_ticks_ms = get_current_ticks_monotonic() # Use monotonic timer
    original_requested_state = new_state
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    current_enemy_state = getattr(enemy, 'state', 'idle') # Get current state safely

    # Guard Clauses for Overriding States
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False) and \
       new_state not in ['petrified', 'smashed', 'idle']:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if getattr(enemy, 'is_stone_smashed', False) and new_state not in ['smashed', 'idle']:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being stone_smashed.")
        return
    # Corrected logic for petrified blocking other status effects
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False): # If petrified (and not yet smashed)
        if new_state in ['frozen', 'defrost', 'aflame', 'deflame', 'hit', 'stomp_death']:
            debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to petrification.")
            return

    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state

    enemy_animations = getattr(enemy, 'animations', None)
    if animation_key_to_check not in ['stone', 'stone_smashed']:
        if not enemy_animations or animation_key_to_check not in enemy_animations or not enemy_animations.get(animation_key_to_check):
            warning(f"EnemyStateHandler (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
                    f"Animation for logical state '{new_state}' (maps to key '{animation_key_to_check}') potentially missing. Animation handler will attempt fallback.")

    can_change_state_now = (current_enemy_state != new_state or
                            new_state in ['death', 'stomp_death', 'frozen', 'defrost',
                                          'aflame', 'deflame', 'petrified', 'smashed', 'hit'])
    if getattr(enemy, 'is_dead', False) and getattr(enemy, 'death_animation_finished', False) and not getattr(enemy, 'is_stone_smashed', False):
         if new_state not in ['idle']: can_change_state_now = False

    if not can_change_state_now:
        if current_enemy_state == new_state: update_enemy_animation(enemy)
        return

    state_is_actually_changing = (current_enemy_state != new_state)
    if state_is_actually_changing:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): State changing from '{current_enemy_state}' to '{new_state}'. Requested: '{original_requested_state}'.")
    
    # Using setattr for _last_state_for_debug in case it's not pre-defined
    setattr(enemy, '_last_state_for_debug', new_state)

    # Clear Conflicting Flags (using setattr for safety if attributes don't exist, though they should for an Enemy)
    if new_state != 'aflame': setattr(enemy, 'is_aflame', False)
    if new_state != 'deflame': setattr(enemy, 'is_deflaming', False)
    if new_state != 'frozen': setattr(enemy, 'is_frozen', False)
    if new_state != 'defrost': setattr(enemy, 'is_defrosting', False)
    if new_state not in ['petrified', 'smashed']:
        if getattr(enemy, 'is_petrified', False): setattr(enemy, 'is_petrified', False)
        if getattr(enemy, 'is_stone_smashed', False): setattr(enemy, 'is_stone_smashed', False)
    if new_state != 'stomp_death': setattr(enemy, 'is_stomp_dying', False)
    if 'attack' not in new_state:
        setattr(enemy, 'is_attacking', False); setattr(enemy, 'attack_type', 0)
    if new_state != 'hit' and getattr(enemy, 'is_taking_hit', False):
        if current_ticks_ms - getattr(enemy, 'hit_timer', 0) >= getattr(enemy, 'hit_cooldown', 500):
            setattr(enemy, 'is_taking_hit', False)

    enemy.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm']: # attack_nm was missing
        enemy.current_frame = 0
        enemy.last_anim_update = current_ticks_ms
    enemy.state_timer = current_ticks_ms

    # State-Specific Initializations
    if new_state == 'aflame':
        if not getattr(enemy, 'is_aflame', False): # Check if already aflame to avoid resetting timers
            enemy.aflame_timer_start = current_ticks_ms
            enemy.aflame_damage_last_tick = current_ticks_ms
            enemy.has_ignited_another_enemy_this_cycle = False
        enemy.is_aflame = True
    elif new_state == 'deflame':
        if not getattr(enemy, 'is_deflaming', False): enemy.deflame_timer_start = current_ticks_ms
        enemy.is_deflaming = True
    elif new_state == 'frozen':
        if not getattr(enemy, 'is_frozen', False): enemy.frozen_effect_timer = current_ticks_ms
        enemy.is_frozen = True
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
    elif new_state == 'defrost':
        enemy.is_defrosting = True
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
    elif new_state == 'petrified':
        if not getattr(enemy, 'is_petrified', False): enemy.facing_at_petrification = enemy.facing_right
        enemy.is_petrified = True
        if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX') and hasattr(enemy.acc, 'setY'):
            enemy.acc.setX(0.0)
            enemy.acc.setY(float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8))))
    elif new_state == 'smashed':
        if not getattr(enemy, 'is_stone_smashed', False):
            enemy.stone_smashed_timer_start = current_ticks_ms
            enemy.death_animation_finished = False
        enemy.is_stone_smashed = True; enemy.is_petrified = True # Smashed implies petrified
        enemy.is_dead = True
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
    elif 'attack' in new_state:
        if not getattr(enemy, 'is_attacking', False): enemy.attack_timer = current_ticks_ms
        enemy.is_attacking = True
        if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0)
    elif new_state == 'hit':
        if not getattr(enemy, 'is_taking_hit', False): enemy.hit_timer = enemy.state_timer # Use state_timer if just entering hit
        enemy.is_taking_hit = True
        setattr(enemy, 'is_attacking', False); setattr(enemy, 'attack_type', 0)
    elif new_state == 'death' or new_state == 'stomp_death': # Ensure 'death_nm' also handled if it's a separate key
        if not getattr(enemy, 'is_dead', False):
            enemy.is_dead = True; enemy.current_health = 0
            enemy.death_animation_finished = False
            # Clear other conflicting statuses
            setattr(enemy, 'is_frozen', False); setattr(enemy, 'is_defrosting', False)
            setattr(enemy, 'is_aflame', False); setattr(enemy, 'is_deflaming', False)
            setattr(enemy, 'is_petrified', False); setattr(enemy, 'is_stone_smashed', False)
            if new_state == 'stomp_death' and not getattr(enemy, 'is_stomp_dying', False):
                # Lazy import to break potential cycles if enemy_status_effects imports this module
                from enemy_status_effects import stomp_kill_enemy 
                stomp_kill_enemy(enemy)
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
    elif new_state == 'idle':
        pass # No specific action for idle, just sets the state

    update_enemy_animation(enemy)