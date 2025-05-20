# player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
"""
# version 2.0.2 

import time # For monotonic timer
from typing import Optional

# PySide6 imports
from PySide6.QtCore import QPointF

# Game imports
import constants as C
from utils import PrintLimiter 

# --- Monotonic Timer ---
_start_time_player_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_player_state_monotonic) * 1000)
# --- End Monotonic Timer ---

try:
    from player_animation_handler import update_player_animation # Ensure this is PySide6 compatible
except ImportError:
    # Fallback if player_animation_handler is missing (should not happen in a stable build)
    def update_player_animation(player):
        if hasattr(player, 'animate') and callable(player.animate):
            player.animate()
        else:
            print(f"CRITICAL PLAYER_STATE_HANDLER: player_animation_handler.update_player_animation not found "
                  f"for Player ID {getattr(player, 'player_id', 'N/A')}")

try:
    from logger import info, debug, warning, error, critical # Define these for the module
except ImportError:
    print("CRITICAL PLAYER_STATE_HANDLER: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args): print(f"INFO: {msg}", *args) # Add *args for compatibility
    def debug(msg, *args): print(f"DEBUG: {msg}", *args)
    def warning(msg, *args): print(f"WARNING: {msg}", *args)
    def error(msg, *args): print(f"ERROR: {msg}", *args)
    def critical(msg, *args): print(f"CRITICAL: {msg}", *args)


def set_player_state(player, new_state: str):
    # Ensure player object and its critical attributes are valid
    if not getattr(player, '_valid_init', False):
        # Use a generic print if PrintLimiter might not be on player yet
        # Or, if PrintLimiter is a global utility, it can be used directly.
        # Assuming player might not have print_limiter if _valid_init is False.
        print(f"PlayerStateHandler: Attempted to set state on invalid player {getattr(player, 'player_id', 'N/A')}. Ignoring.")
        return

    current_ticks_ms = get_current_ticks_monotonic() # Use the monotonic timer
    original_new_state_request = new_state
    player_id_str = f"P{getattr(player, 'player_id', 'N/A')}"
    current_player_state = getattr(player, 'state', 'idle') # Safely get current state

    # Guard Clauses (using getattr for safety)
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False) and \
       new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"set_state_block_petrified_{player.player_id}_{new_state}"):
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if getattr(player, 'is_stone_smashed', False) and new_state not in ['smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"set_state_block_smashed_{player.player_id}_{new_state}"):
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being stone_smashed.")
        return

    # State adjustments based on current status effects
    is_crouching_flag = getattr(player, 'is_crouching', False)
    if getattr(player, 'is_aflame', False):
        if new_state not in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'burning_crouch' if is_crouching_flag else 'burning'
    elif getattr(player, 'is_deflaming', False):
        if new_state not in ['deflame', 'deflame_crouch', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'deflame_crouch' if is_crouching_flag else 'deflame'
    elif getattr(player, 'is_frozen', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'frozen'
    elif getattr(player, 'is_defrosting', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'defrost'

    # Animation Key Validation
    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run' # These are logical states, map to visual 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state # Covers attack, attack_nm, etc.
    
    player_animations = getattr(player, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']: # Stone assets handled differently
        if not player_animations or animation_key_to_check not in player_animations or \
           not player_animations.get(animation_key_to_check): # Check if key exists and has content
            fallback_state_key = 'fall' if not getattr(player, 'on_ground', False) else 'idle'
            if player_animations and fallback_state_key in player_animations and player_animations.get(fallback_state_key):
                if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}_{new_state}"):
                    warning(f"Player Warning ({player_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else: # Critical fallback if 'idle' or 'fall' are also missing
                first_available_anim_key = next((key for key, anim_list in player_animations.items() if anim_list), None) if player_animations else None
                if not first_available_anim_key:
                    if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                        critical(f"Player CRITICAL ({player_id_str}): No animations loaded at all. Requested: '{original_new_state_request}'. Player invalid.")
                    player._valid_init = False; return
                new_state = first_available_anim_key # Use literally the first animation found
                if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                    critical(f"Player CRITICAL ({player_id_str}): State '{original_new_state_request}' & preferred fallbacks missing. Using first available: '{new_state}'.")

    # Determine if State Can Change
    can_change_state_now = (current_player_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and current_player_state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch'])

    if getattr(player, 'is_dead', False) and getattr(player, 'death_animation_finished', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']: # Allow reset to idle
            can_change_state_now = False

    if not can_change_state_now:
        if current_player_state == new_state and hasattr(player, 'print_limiter') and \
           player.print_limiter.can_print(f"set_state_no_change_{player_id_str}_{new_state}"):
             debug(f"PlayerStateHandler ({player_id_str}): State change to '{new_state}' not allowed or no actual change needed.")
        if current_player_state == new_state: update_player_animation(player) # Refresh animation if state is the same
        return

    state_is_actually_changing = (current_player_state != new_state)
    if state_is_actually_changing:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_print(f"state_change_{player.player_id}_{current_player_state}_{new_state}"):
             debug(f"PlayerStateHandler ({player_id_str}): State changing from '{current_player_state}' to '{new_state}' (request was '{original_new_state_request}')")
    setattr(player, '_last_state_for_debug', new_state) # Use setattr for safety

    # Clear Conflicting Flags
    if 'attack' not in new_state and getattr(player, 'is_attacking', False):
        player.is_attacking = False; setattr(player, 'attack_type', 0)
    if new_state != 'hit' and getattr(player, 'is_taking_hit', False):
        if current_ticks_ms - getattr(player, 'hit_timer', 0) >= getattr(player, 'hit_cooldown', C.PLAYER_HIT_COOLDOWN):
            player.is_taking_hit = False
    if new_state != 'dash': setattr(player, 'is_dashing', False)
    if new_state != 'roll': setattr(player, 'is_rolling', False)
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: setattr(player, 'is_sliding', False)

    # Handle fire status effects
    if new_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch']:
        if not getattr(player, 'is_aflame', False): # Check if just started being aflame
            player.aflame_timer_start = current_ticks_ms
            player.aflame_damage_last_tick = player.aflame_timer_start
        player.is_aflame = True; player.is_deflaming = False
    elif new_state in ['deflame', 'deflame_crouch']:
        if not getattr(player, 'is_deflaming', False): player.deflame_timer_start = current_ticks_ms
        player.is_deflaming = True; player.is_aflame = False
    else: # Neither aflame nor deflaming
        player.is_aflame = False; player.is_deflaming = False
        
    # Handle frozen status effects
    if new_state == 'frozen':
        if not getattr(player, 'is_frozen', False): player.frozen_effect_timer = current_ticks_ms
        player.is_frozen = True; player.is_defrosting = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False
    else: # Neither frozen nor defrosting
        player.is_frozen = False; player.is_defrosting = False
        
    # Handle petrification status effects
    if new_state == 'petrified':
        if not getattr(player, 'is_petrified', False): # If just became petrified
            player.facing_at_petrification = getattr(player, 'facing_right', True)
            player.was_crouching_when_petrified = getattr(player, 'is_crouching', False)
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True # Petrified is a form of "death" with instant anim finish
        # Clear other major statuses
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False
    elif new_state == 'smashed':
        if not getattr(player, 'is_stone_smashed', False): player.stone_smashed_timer_start = current_ticks_ms
        player.is_stone_smashed = True; player.is_petrified = True # Smashed implies petrified
        player.is_dead = True; player.death_animation_finished = False # Smashed has its own "death" anim
    elif getattr(player, 'is_petrified', False) and new_state not in ['petrified', 'smashed']: # No longer petrified by new state
        player.is_petrified = False; player.is_stone_smashed = False; player.was_crouching_when_petrified = False
        if getattr(player, 'is_dead', False) and getattr(player, 'current_health', 0) > 0: # If was "dead" due to petrification but has health
            player.is_dead = False; player.death_animation_finished = False


    player.state = new_state # Set the new state
    # Reset animation frame if state actually changed or for specific re-triggerable states
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm', 'attack_combo', 'attack_combo_nm', 'crouch_attack', 'aflame', 'aflame_crouch']:
        player.current_frame = 0
        player.last_anim_update = current_ticks_ms # Use current_ticks_ms for consistency
    player.state_timer = current_ticks_ms # Timestamp for when this state began

    # State-Specific Initializations
    if new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        if hasattr(player, 'vel') and hasattr(player.vel, 'setX') and hasattr(player.vel, 'setY'):
            player.vel.setX(C.PLAYER_DASH_SPEED * (1 if getattr(player, 'facing_right', True) else -1))
            player.vel.setY(0.0)
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        if hasattr(player, 'vel') and hasattr(player.vel, 'x') and hasattr(player.vel, 'setX'):
            current_vel_x = player.vel.x()
            target_roll_vel_x = C.PLAYER_ROLL_SPEED * (1 if getattr(player, 'facing_right', True) else -1)
            if abs(current_vel_x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(target_roll_vel_x)
            else: player.vel.setX(current_vel_x * 0.8 + target_roll_vel_x * 0.2)
            player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x())))
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        if hasattr(player, 'vel') and hasattr(player.vel, 'x') and hasattr(player.vel, 'setX'):
            if abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: # Give a small initial slide speed if slow
                player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if getattr(player, 'facing_right', True) else -1))
    elif 'attack' in new_state:
        player.is_attacking = True; player.attack_timer = player.state_timer
        # Calculate attack duration based on animation frames
        animation_for_this_attack = player_animations.get(new_state, []) if player_animations else []
        num_attack_frames = len(animation_for_this_attack)
        base_ms_per_frame = C.ANIM_FRAME_DURATION
        ms_per_frame_for_attack = base_ms_per_frame
        if getattr(player, 'attack_type', 0) == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'): # attack_type 2 is usually 'attack2'
            ms_per_frame_for_attack = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
        player.attack_duration = num_attack_frames * ms_per_frame_for_attack if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
        
        if new_state.endswith('_nm') or new_state == 'crouch_attack': # No movement for these attacks
             if hasattr(player, 'vel') and hasattr(player.vel, 'setX'): player.vel.setX(0.0)
    elif new_state == 'hit':
        player.is_taking_hit = True; player.hit_timer = player.state_timer 
        if not getattr(player, 'on_ground', False) and hasattr(player, 'vel') and \
           hasattr(player.vel, 'y') and hasattr(player.vel, 'setY') and hasattr(player.vel, 'setX'):
            if player.vel.y() > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): # Only apply knockback if not strongly ascending
                player.vel.setX(player.vel.x() * -0.3) # Slight horizontal knockback
                player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.4) # Slight upward knockback
        player.is_attacking = False; setattr(player, 'attack_type', 0) # Cancel current attack
    elif new_state == 'death' or new_state == 'death_nm': # Handle 'death_nm' too
        player.is_dead = True
        if hasattr(player, 'vel') and hasattr(player.vel, 'setX') and hasattr(player.vel, 'setY'):
            player.vel.setX(0.0)
            if player.vel.y() < -1: player.vel.setY(1.0) # Prevent extreme upward velocity on death
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX') and hasattr(player.acc, 'setY'):
            player.acc.setX(0.0)
            if not getattr(player, 'on_ground', False): player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
            else: player.vel.setY(0.0); player.acc.setY(0.0) # If on ground, stop vertical movement/gravity
        player.death_animation_finished = False # Reset this flag
    elif new_state == 'wall_climb':
        player.wall_climb_timer = player.state_timer # Start of climb
        if hasattr(player, 'vel') and hasattr(player.vel, 'setY') and hasattr(player.vel, 'setX'):
            player.vel.setY(C.PLAYER_WALL_CLIMB_SPEED); player.vel.setX(0.0)
    elif new_state == 'wall_slide' or new_state == 'wall_hang':
        player.wall_climb_timer = 0 # Reset climb timer if sliding or hanging
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed']:
        if hasattr(player, 'vel'): player.vel = QPointF(0,0)
        if hasattr(player, 'acc'): player.acc = QPointF(0,0)
        if new_state == 'petrified' and not getattr(player, 'on_ground', False):
            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'):
                 player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7))) # Petrified objects fall
    elif new_state == 'idle':
        pass # No specific action needed for idle, just ensures the state is set

    update_player_animation(player) # Update animation based on the new state