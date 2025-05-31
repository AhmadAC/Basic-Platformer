# player/player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
Version 2.0.13 (Corrected logic, removed enemy-specific checks, robust crouch flag)
"""
import time
from typing import Optional, Any

from PySide6.QtCore import QPointF

import main_game.constants as C
from main_game.utils import PrintLimiter # Corrected import path for utils

# Logger import
try:
    from main_game.logger import info, debug, warning, error, critical # Corrected import path
except ImportError:
    print("CRITICAL PLAYER_STATE_HANDLER: Failed to import logger from main_game.logger. Using fallback print.")
    def info(msg, *args, **kwargs): print(f"INFO_PSTATE: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATE: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATE: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PSTATE: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_PSTATE: {msg}")

# DO NOT import player_animation_handler at the top level here.

_state_limiter = PrintLimiter(default_limit=5, default_period_sec=2.0)

_start_time_player_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns milliseconds since this module was loaded, for consistent timing."""
    return int((time.monotonic() - _start_time_player_state_monotonic) * 1000)


def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
    # --- LOCAL IMPORT to break circular dependency ---
    try:
        from player.player_animation_handler import update_player_animation
    except ImportError:
        critical("PLAYER_STATE_HANDLER (set_player_state): Failed to import update_player_animation locally.")
        def update_player_animation(player_arg: Any): # Fallback dummy
            if hasattr(player_arg, 'animate') and callable(player_arg.animate): player_arg.animate()
            else: critical(f"PLAYER_STATE_HANDLER (Fallback): Cannot call animate for P{getattr(player_arg, 'player_id', 'N/A')}")
    # --- END LOCAL IMPORT ---

    if not getattr(player, '_valid_init', False):
        if _state_limiter.can_log(f"set_state_invalid_player_{getattr(player, 'player_id', 'unknown')}"):
            debug(f"PlayerStateHandler: Skip set state on invalid P{getattr(player, 'player_id', 'N/A')}.")
        return

    effective_current_time_ms = current_game_time_ms_param if current_game_time_ms_param is not None else get_current_ticks_monotonic()
    
    original_new_state_request = new_state
    player_id_str = f"P{getattr(player, 'player_id', 'N/A')}"
    current_player_state = getattr(player, 'state', 'idle')

    # --- Guard Clauses for Overriding States (Petrified, Smashed, Zapped, Frozen, Defrost) ---
    # These checks prevent unwanted state changes when the player is in a "hard-locked" status.
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']: # Allow idle as a reset
            if _state_limiter.can_log(f"set_state_block_petrified_{player_id_str}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being petrified.")
            return
    if getattr(player, 'is_stone_smashed', False):
        if new_state not in ['smashed', 'death', 'death_nm', 'idle']: # Allow idle as a reset
            if _state_limiter.can_log(f"set_state_block_smashed_{player_id_str}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being stone_smashed.")
            return
    if getattr(player, 'is_zapped', False):
        allowed_states_while_zapped = ['zapped', 'death', 'death_nm', 'idle', 'fall']
        if new_state not in allowed_states_while_zapped:
             if _state_limiter.can_log(f"set_state_block_zapped_{player_id_str}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being zapped.")
             return
    if getattr(player, 'is_frozen', False):
        allowed_states_while_frozen = ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit', 'idle', 'zapped']
        if new_state not in allowed_states_while_frozen:
             if _state_limiter.can_log(f"set_state_block_frozen_{player_id_str}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being frozen.")
             return
    if getattr(player, 'is_defrosting', False):
        allowed_states_while_defrosting = ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit', 'idle', 'fall', 'zapped']
        if new_state not in allowed_states_while_defrosting:
             if _state_limiter.can_log(f"set_state_block_defrost_{player_id_str}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being defrosted.")
             return
    
    # Petrified state also blocks other status effects from being applied as a new state
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state in ['frozen', 'defrost', 'aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'hit', 'zapped']:
            if _state_limiter.can_log(f"block_petri_status_P{player.player_id}_{new_state}"):
                debug(f"PSH (P{player.player_id}): Blocked status '{new_state}' due to petrification.")
            return


    # --- Automatic state adjustments based on current conditions (e.g., fire + crouch) ---
    is_crouching_flag_before_auto_adjust = getattr(player, 'is_crouching', False) 
    if getattr(player, 'is_aflame', False) and new_state not in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        # If aflame, and new state isn't a conflicting major status, adjust for crouch
        if new_state not in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'death', 'death_nm', 'hit', 'idle']:
            new_state = 'burning_crouch' if is_crouching_flag_before_auto_adjust else 'burning'
    elif getattr(player, 'is_deflaming', False) and new_state not in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        if new_state not in ['deflame', 'deflame_crouch', 'death', 'death_nm', 'hit', 'idle']:
            new_state = 'deflame_crouch' if is_crouching_flag_before_auto_adjust else 'deflame'

    # --- Animation Key Validation (ensure the new_state has a valid animation) ---
    animation_key_to_check = new_state
    player_animations = getattr(player, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']: # Stone states have dedicated frames managed by Player class
        if not player_animations or animation_key_to_check not in player_animations or \
           not player_animations.get(animation_key_to_check) or \
           (player_animations.get(animation_key_to_check) and not player_animations[animation_key_to_check][0]): # Check if first frame is valid
            
            fallback_state_key = 'fall' if not getattr(player, 'on_ground', False) else 'idle'
            # Check if fallback animation exists and is valid
            if player_animations and fallback_state_key in player_animations and \
               player_animations.get(fallback_state_key) and player_animations[fallback_state_key][0]:
                if _state_limiter.can_log(f"player_set_state_fallback_{player_id_str}_{original_new_state_request}_{new_state}"):
                    warning(f"PlayerStateHandler Warning ({player_id_str}): State '{original_new_state_request}' (to '{new_state}') anim missing/invalid. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else: # If primary fallback also fails, try any valid animation
                first_available_anim_key = next((key for key, anim_list in player_animations.items() if anim_list and anim_list[0] and not anim_list[0].isNull()), None) if player_animations else None
                if not first_available_anim_key:
                    if _state_limiter.can_log(f"player_set_state_no_anims_{player_id_str}"):
                        critical(f"PlayerStateHandler CRITICAL ({player_id_str}): No animations loaded AT ALL. Requested state: '{original_new_state_request}'. Player invalid.")
                    player._valid_init = False; return
                new_state = first_available_anim_key
                if _state_limiter.can_log(f"player_set_state_critical_fallback_{player_id_str}_{original_new_state_request}"):
                    critical(f"PlayerStateHandler CRITICAL ({player_id_str}): State '{original_new_state_request}' & standard fallbacks missing. Using first available animation: '{new_state}'.")

    # --- Determine if state can actually change ---
    can_change_state_now = (current_player_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and current_player_state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch']) or \
                           (new_state == 'zapped' and not getattr(player, 'is_zapped', False))

    # Prevent state changes if dead and animation finished (unless becoming petrified/smashed or resetting to idle)
    if getattr(player, 'is_dead', False) and getattr(player, 'death_animation_finished', False) and \
       not getattr(player, 'is_stone_smashed', False) and not getattr(player, 'is_petrified', False):
         if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']:
            can_change_state_now = False

    if not can_change_state_now:
        if current_player_state == new_state and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_no_change_P{player.player_id}_{new_state}"):
             debug(f"PSH (P{player.player_id}): State change to '{new_state}' not allowed or no actual change needed (already in state).")
        # Still call animation update if state is the same, as frame might need to advance.
        if current_player_state == new_state:
            update_player_animation(player)
        return

    state_is_actually_changing = (current_player_state != new_state)
    if state_is_actually_changing:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"state_change_P{player.player_id}_{current_player_state}_{new_state}"):
             debug(f"PSH (P{player.player_id}): State changing from '{current_player_state}' to '{new_state}' (original req '{original_new_state_request}')")
    
    setattr(player, '_last_state_for_debug', new_state) # For debugging

    # --- Clear Action/Status Flags based on the NEW state ---
    # These flags are typically set by input or specific events, and state transitions clear them.
    if 'attack' not in new_state and getattr(player, 'is_attacking', False):
        player.is_attacking = False; setattr(player, 'attack_type', 0) # Attack type 0 = no attack
    if new_state != 'hit' and getattr(player, 'is_taking_hit', False):
        # Only clear is_taking_hit if hit cooldown has passed
        if effective_current_time_ms - getattr(player, 'hit_timer', 0) >= getattr(player, 'hit_cooldown', C.PLAYER_HIT_COOLDOWN):
            player.is_taking_hit = False
    if new_state != 'dash' and getattr(player, 'is_dashing', False): player.is_dashing = False
    if new_state != 'roll' and getattr(player, 'is_rolling', False): player.is_rolling = False
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end'] and getattr(player, 'is_sliding', False): player.is_sliding = False

    # --- Player Crouching Flag Management (Crucial for collision rect and animation) ---
    if new_state in ['crouch', 'crouch_walk', 'crouch_attack', 'crouch_trans', 
                     'aflame_crouch', 'burning_crouch', 'deflame_crouch',
                     'slide', 'slide_trans_start', 'slide_trans_end']:
        player.is_crouching = True
    elif new_state not in ['petrified', 'smashed']: # Don't uncrouch if becoming stone (petrified state uses was_crouching_when_petrified)
        player.is_crouching = False

    # --- Status Effects Flags and Timers (based on new_state) ---
    # These flags control visual effects and status-specific logic in player.update_status_effects()
    if new_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch']:
        if not getattr(player, 'is_aflame', False) and not getattr(player, 'is_deflaming', False): 
            # If starting a new fire cycle
            player.overall_fire_effect_start_time = effective_current_time_ms
        player.is_aflame = True; player.aflame_timer_start = effective_current_time_ms
        player.aflame_damage_last_tick = player.aflame_timer_start # Reset damage tick for new aflame state
        player.is_deflaming = False # Cannot be both aflame and deflaming
        player.is_frozen = False; player.is_defrosting = False # Fire melts ice
        player.is_zapped = False # Fire might supersede zap or vice-versa (current: fire supersedes)
    elif new_state in ['deflame', 'deflame_crouch']:
        if not getattr(player, 'is_deflaming', False): player.deflame_timer_start = effective_current_time_ms
        player.is_deflaming = True; player.is_aflame = False # Cannot be both
        player.is_frozen = False; player.is_defrosting = False; player.is_zapped = False
    elif new_state == 'frozen':
        if not getattr(player, 'is_frozen', False): player.frozen_effect_timer = effective_current_time_ms
        player.is_frozen = True; player.is_defrosting = False
        # Frozen extinguishes fire
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"frozen_extinguishes_fire_P{player.player_id}"):
                debug(f"PSH (P{player.player_id}): Player transitioned to 'frozen'. Extinguishing active fire/deflame state.")
        player.is_aflame = False; player.is_deflaming = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_zapped = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False # Cannot be both
        # Ensure fire is still out if defrosting
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
            player.is_aflame = False; player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_zapped = False
    elif new_state == 'zapped': # ADDED ZAPPED
        if not getattr(player, 'is_zapped', False): # If not already zapped, start timers
            player.zapped_timer_start = effective_current_time_ms
            player.zapped_damage_last_tick = player.zapped_timer_start
        player.is_zapped = True
        # Zapped extinguishes fire and cancels freeze/defrost
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"zapped_extinguishes_fire_P{player.player_id}"):
                debug(f"PSH (P{player.player_id}): Player transitioned to 'zapped'. Extinguishing active fire/deflame state.")
        player.is_aflame = False; player.is_deflaming = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_frozen = False; player.is_defrosting = False
    elif new_state == 'petrified': # Petrified is a major overriding state
        if not getattr(player, 'is_petrified', False): # If just becoming petrified
            player.facing_at_petrification = getattr(player, 'facing_right', True)
            player.was_crouching_when_petrified = getattr(player, 'is_crouching', False) # Correctly use current crouch state
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True # Visually static, effectively "finished" death anim
        # Clear all other conflicting statuses
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False; player.is_zapped = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
    elif new_state == 'smashed': # Smashed is also overriding
        if not getattr(player, 'is_stone_smashed', False): player.stone_smashed_timer_start = effective_current_time_ms
        player.is_stone_smashed = True; player.is_petrified = True # Smashed implies petrified
        player.is_dead = True; player.death_animation_finished = False # Smashed has its own "death" animation
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False; player.is_zapped = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
    else: # For 'idle', 'run', 'fall', 'hit', 'death', 'jump' etc. - clear transient status flags
        flags_were_cleared_in_else_block = False
        if getattr(player, 'is_aflame', False): player.is_aflame = False; flags_were_cleared_in_else_block = True
        if getattr(player, 'is_deflaming', False): player.is_deflaming = False; flags_were_cleared_in_else_block = True
        if flags_were_cleared_in_else_block and getattr(player, 'overall_fire_effect_start_time', 0) != 0 :
            player.overall_fire_effect_start_time = 0 # Reset 5s fire cycle if transitioning to non-fire state
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"clear_overall_fire_timer_final_else_P{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Cleared 5s fire timer because player transitioned to non-fire state '{new_state}'.")
        
        if new_state not in ['frozen', 'defrost']: # Don't clear if becoming frozen/defrost
            if getattr(player, 'is_frozen', False): player.is_frozen = False
            if getattr(player, 'is_defrosting', False): player.is_defrosting = False
        
        if new_state not in ['zapped']: # Don't clear if becoming zapped
            if getattr(player, 'is_zapped', False): player.is_zapped = False

        if new_state not in ['petrified', 'smashed']: # Don't clear if becoming stone
            if getattr(player, 'is_petrified', False): player.is_petrified = False
            if getattr(player, 'is_stone_smashed', False): player.is_stone_smashed = False
            if getattr(player, 'was_crouching_when_petrified', False): player.was_crouching_when_petrified = False # Reset this flag too

    # --- Final state assignment and timer resets ---
    player.state = new_state 
    # Reset animation frame if state actually changed OR if it's a re-triggerable action state
    if state_is_actually_changing or \
       new_state in ['hit', 'attack', 'attack_nm', 'attack_combo', 'attack_combo_nm', 'crouch_attack', 'aflame', 'aflame_crouch', 'jump', 'zapped']:
        player.current_frame = 0
        player.last_anim_update = effective_current_time_ms # Reset animation timer
    player.state_timer = effective_current_time_ms # Always reset state timer

    # --- State-Specific Initializations (e.g., setting action flags, velocities) ---
    if new_state == 'idle' or new_state == 'run' or new_state == 'jump':
        pass # Basic states, movement controlled by input/physics
    elif new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        if hasattr(player, 'vel'): player.vel.setX(C.PLAYER_DASH_SPEED * (1 if getattr(player, 'facing_right', True) else -1)); player.vel.setY(0.0)
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        if hasattr(player, 'vel'):
            current_vel_x = player.vel.x(); target_roll_vel_x = C.PLAYER_ROLL_SPEED * (1 if getattr(player, 'facing_right', True) else -1)
            if abs(current_vel_x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(target_roll_vel_x)
            else: player.vel.setX(current_vel_x * 0.8 + target_roll_vel_x * 0.2) # Blend if already moving fast
            player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x()))) # Cap roll speed
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        if hasattr(player, 'vel') and abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: # If not already sliding fast
            player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if getattr(player, 'facing_right', True) else -1))
    elif 'attack' in new_state: # Covers all attack variations
        player.is_attacking = True; player.attack_timer = player.state_timer
        # Attack duration is calculated based on animation frames for more precision
        anim_frames = player_animations.get(new_state, []) if player_animations else []
        num_frames = len(anim_frames); ms_per_frame_attack = C.ANIM_FRAME_DURATION
        if getattr(player, 'attack_type', 0) == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'): # If type is attack2
            ms_per_frame_attack = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
        player.attack_duration = num_frames * ms_per_frame_attack if num_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
        if new_state.endswith('_nm') or new_state == 'crouch_attack': # No movement for these
            if hasattr(player, 'vel'): player.vel.setX(0.0)
    elif new_state == 'hit':
        player.is_taking_hit = True; player.hit_timer = player.state_timer # hit_timer is used for cooldown
        # Apply knockback if airborne and not already heavily knocked
        if not getattr(player, 'on_ground', False) and hasattr(player, 'vel'): 
            if player.vel.y() > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): # Don't override strong upward knockback
                player.vel.setX(player.vel.x() * -0.3); player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.4) # Small pop-up
        player.is_attacking = False; setattr(player, 'attack_type', 0) # Cancel attack
    elif new_state == 'death' or new_state == 'death_nm':
        player.is_dead = True # Mark as logically dead
        if hasattr(player, 'vel'): player.vel.setX(0.0); # Stop horizontal movement
        if hasattr(player, 'vel') and player.vel.y() < -1: player.vel.setY(1.0) # Prevent upward float if dying in air
        if hasattr(player, 'acc'): player.acc.setX(0.0) # Stop horizontal acceleration
        player.death_animation_finished = False # Start death animation
    elif new_state == 'jump':
        if hasattr(player, 'on_ground'): player.on_ground = False # Crucial for jump physics
        if hasattr(player, 'acc') and hasattr(player.acc, 'setY'):
            player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
            player.acc.setY(player_gravity) # Ensure gravity is active for jump
    elif new_state == 'fall': # Ensure gravity is active if state transitions to fall
        if hasattr(player, 'acc') and hasattr(player.acc, 'setY'):
            player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
            player.acc.setY(player_gravity)
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']: # Halt movement for these
        if hasattr(player, 'vel'): player.vel = QPointF(0,0)
        if hasattr(player, 'acc'): player.acc = QPointF(0,0)
        if new_state == 'petrified' and not getattr(player, 'on_ground', False) and hasattr(player, 'acc'): # Petrified objects fall
                 player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
                 player.acc.setY(player_gravity)
        # Zapped might allow gravity if airborne, similar to petrified
        elif new_state == 'zapped' and not getattr(player, 'on_ground', False) and hasattr(player, 'acc'):
                 player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
                 player.acc.setY(player_gravity)
        # Frozen, Defrost, Smashed (on ground or fully animated) should have no Y velocity/accel
        elif new_state in ['frozen', 'defrost', 'smashed'] and hasattr(player, 'vel'):
            player.vel.setY(0) 
            if hasattr(player, 'acc'): player.acc.setY(0)
    
    update_player_animation(player) # Update animation to reflect the new state