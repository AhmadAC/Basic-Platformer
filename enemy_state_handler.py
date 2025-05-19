#################### START OF FILE: enemy_state_handler.py ####################

# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy state transitions and associated logic for PySide6.
"""
# version 2.0.0 (PySide6 Refactor)

from typing import Optional # For type hinting if needed

# PySide6 imports
from PySide6.QtCore import QPointF # For QPointF type usage

# Game imports
import constants as C
# from utils import PrintLimiter # If needed for enemy-specific logging limits

try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    def update_enemy_animation(enemy):
        if hasattr(enemy, 'animate'):
            enemy.animate()
        else:
            print(f"CRITICAL ENEMY_STATE_HANDLER: enemy_animation_handler.update_enemy_animation not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# Logger import (assuming logger.py is accessible and refactored if needed)
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATE_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_state = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_state) * 1000)


def set_enemy_state(enemy, new_state: str):
    """
    Sets the enemy's logical state, handling transitions and state-specific initializations.
    Calls update_enemy_animation to refresh visuals if the state changes.
    """
    if not enemy._valid_init:
        debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {getattr(enemy, 'enemy_id', 'N/A')}. Ignoring.")
        return

    current_ticks_ms = get_current_ticks()
    original_requested_state = new_state
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # Guard Clauses for Overriding States
    if enemy.is_petrified and not enemy.is_stone_smashed and \
       new_state not in ['petrified', 'smashed', 'idle']: # Allow reset to idle
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if enemy.is_stone_smashed and new_state not in ['smashed', 'idle']: # Allow reset to idle
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' due to being stone_smashed.")
        return
    if enemy.is_petrified and new_state not in ['petrified', 'smashed', 'idle']:
        if new_state in ['frozen', 'defrost', 'aflame', 'deflame', 'hit', 'stomp_death']:
            debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' due to petrification.")
            return

    # Animation Key Validation (for logging/warning)
    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state

    if animation_key_to_check not in ['stone', 'stone_smashed']: # These are special, handled by enemy_base loading
        if not enemy.animations or animation_key_to_check not in enemy.animations or not enemy.animations[animation_key_to_check]:
            warning(f"EnemyStateHandler (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
                    f"Animation for logical state '{new_state}' (maps to key '{animation_key_to_check}') potentially missing. Animation handler will attempt fallback.")

    # Determine if State Can Change
    can_change_state_now = (enemy.state != new_state or
                            new_state in ['death', 'stomp_death', 'frozen', 'defrost',
                                          'aflame', 'deflame', 'petrified', 'smashed', 'hit'])
    if enemy.is_dead and enemy.death_animation_finished and not enemy.is_stone_smashed:
         if new_state not in ['idle']: can_change_state_now = False

    if not can_change_state_now:
        if enemy.state == new_state: update_enemy_animation(enemy) # Refresh animation
        return

    state_is_actually_changing = (enemy.state != new_state)
    if state_is_actually_changing:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): State changing from '{enemy.state}' to '{new_state}'. Requested: '{original_requested_state}'.")
    enemy._last_state_for_debug = new_state

    # Clear Conflicting Flags
    if new_state != 'aflame': enemy.is_aflame = False
    if new_state != 'deflame': enemy.is_deflaming = False
    if new_state != 'frozen': enemy.is_frozen = False
    if new_state != 'defrost': enemy.is_defrosting = False
    if new_state not in ['petrified', 'smashed']:
        if enemy.is_petrified: enemy.is_petrified = False
        if enemy.is_stone_smashed: enemy.is_stone_smashed = False
    if new_state != 'stomp_death': enemy.is_stomp_dying = False
    if 'attack' not in new_state: enemy.is_attacking = False; enemy.attack_type = 0
    if new_state != 'hit' and enemy.is_taking_hit:
        if current_ticks_ms - enemy.hit_timer >= enemy.hit_cooldown:
            enemy.is_taking_hit = False

    enemy.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm']:
        enemy.current_frame = 0
        enemy.last_anim_update = current_ticks_ms
    enemy.state_timer = current_ticks_ms

    # State-Specific Initializations
    if new_state == 'aflame':
        if not enemy.is_aflame:
            enemy.aflame_timer_start = current_ticks_ms
            enemy.aflame_damage_last_tick = current_ticks_ms
            enemy.has_ignited_another_enemy_this_cycle = False
        enemy.is_aflame = True
    elif new_state == 'deflame':
        if not enemy.is_deflaming: enemy.deflame_timer_start = current_ticks_ms
        enemy.is_deflaming = True
    elif new_state == 'frozen':
        if not enemy.is_frozen: enemy.frozen_effect_timer = current_ticks_ms
        enemy.is_frozen = True
        enemy.vel = QPointF(0,0); enemy.acc.setX(0.0)
    elif new_state == 'defrost':
        enemy.is_defrosting = True
        enemy.vel = QPointF(0,0); enemy.acc.setX(0.0)
    elif new_state == 'petrified':
        if not enemy.is_petrified: enemy.facing_at_petrification = enemy.facing_right
        enemy.is_petrified = True
        enemy.vel.setX(0.0); enemy.acc.setX(0.0)
        enemy.acc.setY(float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8))))
        # Stone image assignment (original or flipped) happens in animation_handler based on facing_at_petrification
    elif new_state == 'smashed':
        if not enemy.is_stone_smashed:
            enemy.stone_smashed_timer_start = current_ticks_ms
            enemy.death_animation_finished = False
        enemy.is_stone_smashed = True; enemy.is_petrified = True
        enemy.is_dead = True
        enemy.vel = QPointF(0,0); enemy.acc = QPointF(0,0)
    elif 'attack' in new_state:
        if not enemy.is_attacking: enemy.attack_timer = current_ticks_ms
        enemy.is_attacking = True
        enemy.vel.setX(0.0) # Most enemy attacks are stationary
    elif new_state == 'hit':
        if not enemy.is_taking_hit: enemy.hit_timer = enemy.state_timer
        enemy.is_taking_hit = True
        enemy.is_attacking = False; enemy.attack_type = 0
    elif new_state == 'death' or new_state == 'stomp_death':
        if not enemy.is_dead:
            enemy.is_dead = True; enemy.current_health = 0
            enemy.death_animation_finished = False
            enemy.is_frozen = False; enemy.is_defrosting = False # Clear other statuses on death
            enemy.is_aflame = False; enemy.is_deflaming = False
            enemy.is_petrified = False; enemy.is_stone_smashed = False
            if new_state == 'stomp_death' and not enemy.is_stomp_dying:
                from enemy_status_effects import stomp_kill_enemy # Avoid circular import at top level
                stomp_kill_enemy(enemy)
        enemy.vel = QPointF(0,0); enemy.acc = QPointF(0,0)
    elif new_state == 'idle':
        pass

    update_enemy_animation(enemy)

#################### END OF FILE: enemy_state_handler.py ####################