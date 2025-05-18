# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.1
Handles enemy state transitions and associated logic, such as
initializing timers and flags for different states (aflame, frozen, etc.).
Ensures timers are not improperly reset if a state is re-applied.
"""
import pygame
import constants as C

try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    def update_enemy_animation(enemy):
        if hasattr(enemy, 'animate'):
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
    """
    if not enemy._valid_init:
        debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {getattr(enemy, 'enemy_id', 'N/A')}. Ignoring.")
        return

    current_ticks_ms = pygame.time.get_ticks()
    original_requested_state = new_state
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # --- Guard Clauses for Overriding States ---
    if enemy.is_petrified and not enemy.is_stone_smashed and \
       new_state not in ['petrified', 'smashed', 'idle']:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' "
              f"due to being petrified (and not smashed).")
        return

    if enemy.is_stone_smashed and new_state not in ['smashed', 'idle']:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' "
              f"due to being stone_smashed.")
        return

    # If petrified, block transitions to status effects unless it's a reset ('idle')
    if enemy.is_petrified and new_state not in ['petrified', 'smashed', 'idle']:
        if new_state in ['frozen', 'defrost', 'aflame', 'deflame', 'hit', 'stomp_death']:
            debug(f"EnemyStateHandler (ID {enemy_id_log}): Blocked state change from '{enemy.state}' to '{new_state}' due to petrification.")
            return

    # --- Animation Key Validation (for logging/warning, actual fallback in animation_handler) ---
    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state

    if animation_key_to_check not in ['stone', 'stone_smashed']:
        if animation_key_to_check not in enemy.animations or not enemy.animations[animation_key_to_check]:
            warning(f"EnemyStateHandler (ID: {enemy_id_log}, Color: {enemy.color_name}): "
                    f"Animation for logical state '{new_state}' (maps to key '{animation_key_to_check}') potentially missing or invalid. "
                    f"Animation handler will attempt fallback.")

    # --- Determine if State Can Change ---
    # Allow re-setting 'hit' for stun extension, or other specific states if needed.
    can_change_state_now = (enemy.state != new_state or
                            new_state in ['death', 'stomp_death', 'frozen', 'defrost',
                                          'aflame', 'deflame', 'petrified', 'smashed', 'hit'])
    if enemy.is_dead and enemy.death_animation_finished and not enemy.is_stone_smashed: # If fully "normal" dead
         if new_state not in ['idle']: # Allow reset to idle
            can_change_state_now = False

    if not can_change_state_now:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): State change to '{new_state}' not allowed or already effectively in state and no change needed.")
        if enemy.state == new_state: # If trying to set the same state, just ensure animation is current
            update_enemy_animation(enemy)
        return

    state_is_actually_changing = (enemy.state != new_state)

    if state_is_actually_changing:
        debug(f"EnemyStateHandler (ID {enemy_id_log}): State changing from '{enemy.state}' to '{new_state}'. Requested: '{original_requested_state}'.")
    enemy._last_state_for_debug = new_state # For debug tracking

    # --- Clear Conflicting Flags (based on the NEW state being set) ---
    # These flags control the core logic of status effects.
    # The visual animation is handled by enemy_animation_handler based on these flags and enemy.state.

    if new_state != 'aflame': enemy.is_aflame = False
    if new_state != 'deflame': enemy.is_deflaming = False
    if new_state != 'frozen': enemy.is_frozen = False
    if new_state != 'defrost': enemy.is_defrosting = False
    if new_state not in ['petrified', 'smashed'] : # If not transitioning to a stone state
        if enemy.is_petrified: enemy.is_petrified = False
        if enemy.is_stone_smashed: enemy.is_stone_smashed = False
    if new_state != 'stomp_death': enemy.is_stomp_dying = False # Stomp death visual flag

    # Action flags
    if 'attack' not in new_state: # If the new state is not an attack state
        enemy.is_attacking = False
        enemy.attack_type = 0
    # enemy.is_taking_hit is primarily managed by enemy_combat_handler based on hit_cooldown,
    # but if we transition to a state that *isn't* 'hit', it means the hit reaction is over.
    if new_state != 'hit' and enemy.is_taking_hit:
        # Only clear is_taking_hit if hit cooldown has actually expired
        if current_ticks_ms - enemy.hit_timer >= enemy.hit_cooldown:
            enemy.is_taking_hit = False


    # Update the main logical state
    enemy.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm']: # Reset frame if truly changing or re-attacking/hit
        enemy.current_frame = 0
        enemy.last_anim_update = current_ticks_ms
    enemy.state_timer = current_ticks_ms # Always update the timer for the current state

    # --- State-Specific Initializations (Timers, specific flags, and initial actions) ---
    # These are generally set when first entering the state.
    if new_state == 'aflame':
        if not enemy.is_aflame: # Only initialize if *just now* becoming aflame
            enemy.aflame_timer_start = current_ticks_ms
            enemy.aflame_damage_last_tick = current_ticks_ms
            enemy.has_ignited_another_enemy_this_cycle = False
        enemy.is_aflame = True # Ensure flag is set
        # Other flags should have been cleared above
    elif new_state == 'deflame':
        if not enemy.is_deflaming: # Only initialize if *just now* becoming deflaming
            enemy.deflame_timer_start = current_ticks_ms
        enemy.is_deflaming = True
    elif new_state == 'frozen':
        if not enemy.is_frozen:
            enemy.frozen_effect_timer = current_ticks_ms
        enemy.is_frozen = True
        enemy.vel.xy = 0,0; enemy.acc.x = 0
    elif new_state == 'defrost':
        if not enemy.is_defrosting: # Uses frozen_effect_timer as its base
            pass
        enemy.is_defrosting = True
        enemy.vel.xy = 0,0; enemy.acc.x = 0
    elif new_state == 'petrified':
        if not enemy.is_petrified: # Only set facing on initial petrification
            enemy.facing_at_petrification = enemy.facing_right
        enemy.is_petrified = True
        enemy.vel.x = 0; enemy.acc.x = 0
        enemy.acc.y = getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)) # Ensure gravity
        enemy.stone_image_frame = enemy.stone_image_frame_original
        if not enemy.facing_at_petrification:
            enemy.stone_image_frame = pygame.transform.flip(enemy.stone_image_frame_original, True, False)
    elif new_state == 'smashed':
        if not enemy.is_stone_smashed:
            enemy.stone_smashed_timer_start = current_ticks_ms
            enemy.death_animation_finished = False # Smashing animation needs to play
            # Prepare smashed frames (already oriented based on facing_at_petrification)
            enemy.stone_smashed_frames = [pygame.transform.flip(f, True, False) if not enemy.facing_at_petrification else f for f in enemy.stone_smashed_frames_original]
        enemy.is_stone_smashed = True; enemy.is_petrified = True # Smashed implies petrified
        enemy.is_dead = True # Smashed is a form of "death"
        enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
    elif 'attack' in new_state:
        if not enemy.is_attacking: enemy.attack_timer = current_ticks_ms # Start attack timer if not already
        enemy.is_attacking = True
        # attack_type is assumed to be set by AI logic before calling set_state for an attack
        enemy.vel.x = 0 # Most attacks are stationary unless specific animation logic handles movement
    elif new_state == 'hit':
        if not enemy.is_taking_hit: # If this 'hit' state is due to a new damage event starting invulnerability
            enemy.hit_timer = enemy.state_timer # Start invulnerability period
        enemy.is_taking_hit = True # Ensure this flag reflects hit reaction / cooldown
        enemy.is_attacking = False; enemy.attack_type = 0 # Interrupt attack
        # Note: is_aflame/is_deflaming are NOT cleared here by design.
        # The animation handler will prioritize showing aflame/deflame over 'hit' if those flags are true.
        debug(f"Enemy {enemy_id_log} entered 'hit' state. is_taking_hit={enemy.is_taking_hit}. is_aflame={enemy.is_aflame}, is_deflaming={enemy.is_deflaming}")
    elif new_state == 'death' or new_state == 'stomp_death':
        if not enemy.is_dead: # If transitioning to death for the first time
            enemy.is_dead = True; enemy.current_health = 0
            enemy.death_animation_finished = False
            # Ensure all other active status effects are cleared upon true death
            enemy.is_frozen = False; enemy.is_defrosting = False
            enemy.is_aflame = False; enemy.is_deflaming = False
            enemy.is_petrified = False; enemy.is_stone_smashed = False
            if new_state == 'stomp_death' and not enemy.is_stomp_dying:
                from enemy_status_effects import stomp_kill_enemy # Local import
                stomp_kill_enemy(enemy) # This will re-call set_state('stomp_death') but is_stomp_dying flag will prevent recursion
        enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
    elif new_state == 'idle':
        # No specific timer here beyond state_timer, flags should be cleared by transitions away from other states.
        pass

    update_enemy_animation(enemy) # Update visuals immediately after state change