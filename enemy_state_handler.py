# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.1
Handles enemy state transitions and associated logic, such as
initializing timers and flags for different states (aflame, frozen, etc.).
"""
import pygame
import constants as C # For durations and other constants

# It's assumed that enemy_animation_handler.update_enemy_animation exists
# and will be called after a state change.
try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    # Fallback if direct import fails (e.g., during early refactoring)
    def update_enemy_animation(enemy):
        if hasattr(enemy, 'animate'): # If the old method still exists on enemy
            enemy.animate()
        else:
            print(f"CRITICAL ENEMY_STATE_HANDLER: enemy_animation_handler.update_enemy_animation not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATE_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func


def set_enemy_state(enemy, new_state: str):
    """
    Sets the enemy's logical state, handling transitions and state-specific initializations.
    Calls update_enemy_animation to refresh visuals if the state changes.

    Args:
        enemy (EnemyBase derived class): The enemy instance.
        new_state (str): The new state to transition to.
    """
    if not enemy._valid_init:
        debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {enemy.enemy_id}. Ignoring.")
        return

    current_ticks_ms = pygame.time.get_ticks()
    original_requested_state = new_state

    # --- Guard Clauses for Overriding States ---
    if enemy.is_petrified and not enemy.is_stone_smashed and \
       new_state not in ['petrified', 'smashed', 'idle']: # 'idle' for reset
        debug(f"EnemyStateHandler (ID {enemy.enemy_id}): Blocked state change from '{enemy.state}' to '{new_state}' "
              f"due to being petrified (and not smashed).")
        return

    if enemy.is_stone_smashed and new_state not in ['smashed', 'idle']: # 'idle' for reset
        debug(f"EnemyStateHandler (ID {enemy.enemy_id}): Blocked state change from '{enemy.state}' to '{new_state}' "
              f"due to being stone_smashed.")
        return

    # Block other status effects if petrified (unless it's a reset to idle)
    if enemy.is_petrified and new_state not in ['petrified', 'smashed', 'idle']:
        if new_state in ['frozen', 'defrost', 'aflame', 'deflame', 'hit', 'stomp_death']:
            debug(f"EnemyStateHandler (ID {enemy.enemy_id}): Blocked state change from '{enemy.state}' to '{new_state}' due to petrification.")
            return

    # --- Animation Key Validation (Visual Fallback) ---
    # The actual animation key is determined by enemy_animation_handler,
    # but we do a basic check here to ensure the logical state itself has some animation.
    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state # e.g., 'attack', 'attack_nm'

    if animation_key_to_check not in ['stone', 'stone_smashed']: # stone/smashed use dedicated frames
        if animation_key_to_check not in enemy.animations or not enemy.animations[animation_key_to_check]:
            warning(f"EnemyStateHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                    f"Animation for logical state '{new_state}' (maps to key '{animation_key_to_check}') missing or invalid. "
                    f"State will be set, but animation might fallback in handler.")
            # We still set the logical state, animation handler will use 'idle' if specific anim fails.

    # --- Determine if State Can Change ---
    # Allow re-setting the same state for effects like 'aflame' if apply_aflame_effect is called again,
    # but be careful about resetting timers (handled below).
    can_change_state_now = True # Default to allow
    if enemy.is_dead and enemy.death_animation_finished: # If truly game-over dead
         if new_state not in ['idle']: # Allow reset to idle if it was dead and finished
            can_change_state_now = False

    if not can_change_state_now:
        debug(f"EnemyStateHandler (ID {enemy.enemy_id}): State change to '{new_state}' not allowed due to current conditions (e.g., fully dead).")
        return

    state_is_actually_changing = (enemy.state != new_state)

    if state_is_actually_changing:
        debug(f"EnemyStateHandler (ID {enemy.enemy_id}): State changing from '{enemy.state}' to '{new_state}'. Requested: '{original_requested_state}'.")
        enemy._last_state_for_debug = new_state
    # else:
        # debug(f"EnemyStateHandler (ID {enemy.enemy_id}): Re-setting state to '{new_state}'.")


    # --- Clear Conflicting Flags on State Change ---
    if state_is_actually_changing:
        if 'attack' not in new_state and enemy.is_attacking: enemy.is_attacking = False; enemy.attack_type = 0
        if new_state != 'hit': enemy.is_taking_hit = False # is_taking_hit is a flag, 'hit' is a state

        # If changing from a status effect state, clear its primary flag
        if enemy.state == 'frozen' and new_state != 'frozen': enemy.is_frozen = False
        if enemy.state == 'defrost' and new_state != 'defrost': enemy.is_defrosting = False
        if enemy.state == 'aflame' and new_state != 'aflame': enemy.is_aflame = False
        if enemy.state == 'deflame' and new_state != 'deflame': enemy.is_deflaming = False

        # If changing from petrified/smashed to something else (e.g. reset to 'idle'), clear these flags.
        if (enemy.is_petrified or enemy.is_stone_smashed) and new_state not in ['petrified', 'smashed']:
            enemy.is_petrified = False
            enemy.is_stone_smashed = False
            # If it was "stone dead" (health was 0), and now resetting (e.g. to idle),
            # the main reset logic in EnemyBase should handle health restoration.
            # Here we just ensure the visual/logic flags for petrification are off.
            if enemy.is_dead and new_state == 'idle': # Likely a full reset
                enemy.is_dead = False
                enemy.death_animation_finished = False


    # --- Set New State and Timers ---
    enemy.state = new_state
    if state_is_actually_changing: # Only reset frame/anim_update if it's a true state change
        enemy.current_frame = 0
        enemy.last_anim_update = current_ticks_ms
    enemy.state_timer = current_ticks_ms # Always update state_timer for the new (or re-set) state

    # --- State-Specific Initializations (Only if entering the state for the first time or re-triggering) ---
    # The goal is to set the controlling flag (e.g., is_aflame) and the start timer *only when the transition occurs*.
    # If set_enemy_state('aflame') is called while already is_aflame, we don't want to reset the timer.

    if new_state == 'frozen':
        if not enemy.is_frozen: # Initialize only if not already frozen
            enemy.frozen_effect_timer = current_ticks_ms
        enemy.is_frozen = True; enemy.is_defrosting = False; enemy.is_aflame = False; enemy.is_deflaming = False
        enemy.vel.xy = 0,0; enemy.acc.x = 0
    elif new_state == 'defrost':
        if not enemy.is_defrosting: # Initialize only if not already defrosting
            # frozen_effect_timer is used as the base for defrost duration too
            pass # Timer already set by 'frozen'
        enemy.is_defrosting = True; enemy.is_frozen = False; enemy.is_aflame = False; enemy.is_deflaming = False
        enemy.vel.xy = 0,0; enemy.acc.x = 0
    elif new_state == 'aflame':
        if not enemy.is_aflame: # Initialize only if not already aflame
            enemy.aflame_timer_start = current_ticks_ms
            enemy.aflame_damage_last_tick = current_ticks_ms
            enemy.has_ignited_another_enemy_this_cycle = False
        enemy.is_aflame = True; enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False
        # Note: apply_aflame_effect might also apply vel.x *= 0.5
    elif new_state == 'deflame':
        if not enemy.is_deflaming: # Initialize only if not already deflaming
            enemy.deflame_timer_start = current_ticks_ms
        enemy.is_deflaming = True; enemy.is_aflame = False; enemy.is_frozen = False; enemy.is_defrosting = False
    elif new_state == 'petrified':
        if not enemy.is_petrified: # Initialize only if not already petrified
            enemy.facing_at_petrification = enemy.facing_right # Store facing *before* setting flags
        enemy.is_petrified = True; enemy.is_stone_smashed = False
        enemy.vel.x = 0; enemy.acc.x = 0
        enemy.acc.y = getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8))
        # Prepare stone image (original is stored in enemy_base)
        enemy.stone_image_frame = enemy.stone_image_frame_original
        if not enemy.facing_at_petrification: # Flip the base stone image if needed for current display
            enemy.stone_image_frame = pygame.transform.flip(enemy.stone_image_frame_original, True, False)
    elif new_state == 'smashed':
        if not enemy.is_stone_smashed: # Initialize only if not already smashed
            enemy.stone_smashed_timer_start = current_ticks_ms
            enemy.death_animation_finished = False # Smashed animation needs to play
            # Prepare smashed frames based on facing direction at petrification
            enemy.stone_smashed_frames = []
            for frame in enemy.stone_smashed_frames_original:
                if not enemy.facing_at_petrification:
                    enemy.stone_smashed_frames.append(pygame.transform.flip(frame, True, False))
                else:
                    enemy.stone_smashed_frames.append(frame)
        enemy.is_stone_smashed = True; enemy.is_petrified = True
        enemy.is_dead = True
        enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
    elif 'attack' in new_state:
        if not enemy.is_attacking : # Only set attack timer if starting a new attack
            enemy.attack_timer = current_ticks_ms
        enemy.is_attacking = True
        # attack_type should be set by AI before calling set_state for attack
        enemy.vel.x = 0 # Typically attacks are stationary unless it's a moving attack animation
    elif new_state == 'hit':
        if not enemy.is_taking_hit: # Only set hit timer if newly hit
            enemy.hit_timer = enemy.state_timer # state_timer is current_ticks_ms
        enemy.is_taking_hit = True
        enemy.vel.x *= -0.5
        enemy.vel.y = getattr(C, 'ENEMY_HIT_BOUNCE_Y', getattr(C, 'PLAYER_JUMP_STRENGTH', -10) * 0.3)
        enemy.is_attacking = False
    elif new_state == 'death' or new_state == 'stomp_death':
        if not enemy.is_dead: # Initialize only if not already marked as dead
            enemy.is_dead = True; enemy.current_health = 0
            enemy.death_animation_finished = False
            # Clear other effects on death
            enemy.is_frozen = False; enemy.is_defrosting = False
            enemy.is_aflame = False; enemy.is_deflaming = False
            enemy.is_petrified = False; enemy.is_stone_smashed = False
            if new_state == 'stomp_death' and not enemy.is_stomp_dying: # is_stomp_dying flag controls visual
                from enemy_status_effects import stomp_kill_enemy # Local import
                stomp_kill_enemy(enemy) # This will re-call set_state('stomp_death') but guard will prevent recursion.
        enemy.vel.xy = 0,0; enemy.acc.xy = 0,0 # Ensure no movement on death
    elif new_state == 'idle':
        pass # No specific timer beyond state_timer

    # After state is set and timers initialized, update animation
    update_enemy_animation(enemy)