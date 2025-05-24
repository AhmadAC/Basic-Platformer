#################### START OF FILE: player_state_handler.py ####################

# player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
"""
# version 2.0.6 (Corrected PrintLimiter calls and removed logger try-except)

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

# Logger is now imported directly
from logger import info, debug, warning, error, critical

try:
    from player_animation_handler import update_player_animation # Ensure this is PySide6 compatible
except ImportError:
    critical("PLAYER_STATE_HANDLER (AnimImportFail): player_animation_handler.update_player_animation not found.")
    def update_player_animation(player):
        if hasattr(player, 'animate') and callable(player.animate):
            player.animate()
        else:
            critical(f"PLAYER_STATE_HANDLER (AnimImportFail-Fallback): Cannot call animate for Player ID {getattr(player, 'player_id', 'N/A')}")


def set_player_state(player, new_state: str):
    if not getattr(player, '_valid_init', False):
        debug(f"PlayerStateHandler: Attempted to set state on invalid player {getattr(player, 'player_id', 'N/A')}. Ignoring.")
        return

    current_ticks_ms = get_current_ticks_monotonic()
    original_new_state_request = new_state
    player_id_str = f"P{getattr(player, 'player_id', 'N/A')}"
    current_player_state = getattr(player, 'state', 'idle') # Get current state safely

    # --- Guard Clauses for Overriding States ---
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False) and \
       new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']: # Allow idle to clear petrified visually if needed
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_petrified_{player.player_id}_{new_state}"): # MODIFIED
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if getattr(player, 'is_stone_smashed', False) and new_state not in ['smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_smashed_{player.player_id}_{new_state}"): # MODIFIED
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being stone_smashed.")
        return
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state in ['frozen', 'defrost', 'aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'hit']:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_petrified_status_{player.player_id}_{new_state}"): # MODIFIED
                debug(f"PlayerStateHandler ({player_id_str}): Blocked status effect state change to '{new_state}' due to petrification.")
            return

    # --- State adjustments based on current status effects ---
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

    # --- Animation Key Validation ---
    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run' # These are AI states, map to visual 'run'
    # 'attack', 'attack2', etc. are already valid anim keys.

    player_animations = getattr(player, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']: # These have dedicated image attributes
        if not player_animations or animation_key_to_check not in player_animations or \
           not player_animations.get(animation_key_to_check): # If animation is missing
            
            # Determine a more logical fallback than just the first available
            fallback_state_key = 'fall' if not getattr(player, 'on_ground', False) else 'idle'
            
            if player_animations and fallback_state_key in player_animations and player_animations.get(fallback_state_key):
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}_{new_state}"): # MODIFIED
                    warning(f"Player Warning ({player_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key # Use this more logical fallback
            else: # If even 'idle' or 'fall' is missing, this is critical
                first_available_anim_key = next((key for key, anim_list in player_animations.items() if anim_list), None) if player_animations else None
                if not first_available_anim_key:
                    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_no_anims_{player.player_id}"): # MODIFIED
                        critical(f"Player CRITICAL ({player_id_str}): No animations loaded AT ALL. Requested state: '{original_new_state_request}'. Player invalid.")
                    player._valid_init = False; return # Cannot recover, make player invalid
                
                new_state = first_available_anim_key # Last resort: use *any* available animation
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"): # MODIFIED
                    critical(f"Player CRITICAL ({player_id_str}): State '{original_new_state_request}' & fallbacks missing. Using first available animation: '{new_state}'.")


    # --- Determine if State Can Change ---
    # Allow re-entering certain states like 'hit' or 'attack' to reset their timers/animations
    can_change_state_now = (current_player_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and current_player_state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch']) # Allow re-entering aflame from burning

    # If player is truly dead (animation finished, not just stone), only allow idle/death states
    if getattr(player, 'is_dead', False) and getattr(player, 'death_animation_finished', False) and not getattr(player, 'is_stone_smashed', False):
         if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']: # Allow idle to clear a finished death state if revived
            can_change_state_now = False

    if not can_change_state_now:
        if current_player_state == new_state and hasattr(player, 'print_limiter') and \
           player.print_limiter.can_log(f"set_state_no_change_{player_id_str}_{new_state}"): # MODIFIED
             debug(f"PlayerStateHandler ({player_id_str}): State change to '{new_state}' not allowed or no actual change needed (current state already '{current_player_state}').")
        # Still call animation update to ensure current frame is correct for the held state
        if current_player_state == new_state: 
            update_player_animation(player)
        return

    state_is_actually_changing = (current_player_state != new_state)
    if state_is_actually_changing:
        # This log is crucial for debugging state flow
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"state_change_{player.player_id}_{current_player_state}_{new_state}"): # MODIFIED
             debug(f"PlayerStateHandler ({player_id_str}): State changing from '{current_player_state}' to '{new_state}' (original request was '{original_new_state_request}')")
    
    setattr(player, '_last_state_for_debug', new_state) # Store the final state being set

    # --- Clear Conflicting Action Flags (e.g., can't be dashing and attacking simultaneously) ---
    if 'attack' not in new_state and getattr(player, 'is_attacking', False):
        player.is_attacking = False; setattr(player, 'attack_type', 0)
        debug(f"{player_id_str} StateClear: Cleared is_attacking due to new state '{new_state}'.")
    if new_state != 'hit' and getattr(player, 'is_taking_hit', False):
        if current_ticks_ms - getattr(player, 'hit_timer', 0) >= getattr(player, 'hit_cooldown', C.PLAYER_HIT_COOLDOWN):
            player.is_taking_hit = False
            debug(f"{player_id_str} StateClear: Cleared is_taking_hit (cooldown ended) due to new state '{new_state}'.")
    if new_state != 'dash' and getattr(player, 'is_dashing', False):
        player.is_dashing = False
        debug(f"{player_id_str} StateClear: Cleared is_dashing due to new state '{new_state}'.")
    if new_state != 'roll' and getattr(player, 'is_rolling', False):
        player.is_rolling = False
        debug(f"{player_id_str} StateClear: Cleared is_rolling due to new state '{new_state}'.")
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end'] and getattr(player, 'is_sliding', False):
        player.is_sliding = False
        debug(f"{player_id_str} StateClear: Cleared is_sliding due to new state '{new_state}'.")

    # --- Handle Status Effects Flags (Aflame, Frozen, Petrified) ---
    if new_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch']:
        if not getattr(player, 'is_aflame', False): 
            player.aflame_timer_start = current_ticks_ms
            player.aflame_damage_last_tick = player.aflame_timer_start
            debug(f"{player_id_str} StatusSet: is_aflame=True, timer_start={player.aflame_timer_start}")
        player.is_aflame = True; player.is_deflaming = False 
    elif new_state in ['deflame', 'deflame_crouch']:
        if not getattr(player, 'is_deflaming', False): 
            player.deflame_timer_start = current_ticks_ms
            debug(f"{player_id_str} StatusSet: is_deflaming=True, timer_start={player.deflame_timer_start}")
        player.is_deflaming = True; player.is_aflame = False 
    else: 
        if getattr(player, 'is_aflame', False): player.is_aflame = False; debug(f"{player_id_str} StatusClear: is_aflame=False")
        if getattr(player, 'is_deflaming', False): player.is_deflaming = False; debug(f"{player_id_str} StatusClear: is_deflaming=False")
        
    if new_state == 'frozen':
        if not getattr(player, 'is_frozen', False): 
            player.frozen_effect_timer = current_ticks_ms
            debug(f"{player_id_str} StatusSet: is_frozen=True, timer_start={player.frozen_effect_timer}")
        player.is_frozen = True; player.is_defrosting = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False
        debug(f"{player_id_str} StatusSet: is_defrosting=True (frozen_timer still {player.frozen_effect_timer})")
    else: 
        if getattr(player, 'is_frozen', False): player.is_frozen = False; debug(f"{player_id_str} StatusClear: is_frozen=False")
        if getattr(player, 'is_defrosting', False): player.is_defrosting = False; debug(f"{player_id_str} StatusClear: is_defrosting=False")
        
    if new_state == 'petrified':
        if not getattr(player, 'is_petrified', False): 
            player.facing_at_petrification = getattr(player, 'facing_right', True)
            player.was_crouching_when_petrified = getattr(player, 'is_crouching', False)
            debug(f"{player_id_str} StatusSet: PETRIFIED. FacingAtPetri={player.facing_at_petrification}, WasCrouching={player.was_crouching_when_petrified}")
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True 
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False 
    elif new_state == 'smashed':
        if not getattr(player, 'is_stone_smashed', False): 
            player.stone_smashed_timer_start = current_ticks_ms
            debug(f"{player_id_str} StatusSet: SMASHED. TimerStart={player.stone_smashed_timer_start}")
        player.is_stone_smashed = True; player.is_petrified = True 
        player.is_dead = True; player.death_animation_finished = False 
    elif getattr(player, 'is_petrified', False) and new_state not in ['petrified', 'smashed']: 
        debug(f"{player_id_str} StatusClear: Exiting petrified state due to new state '{new_state}'.")
        player.is_petrified = False; player.is_stone_smashed = False; player.was_crouching_when_petrified = False
        if getattr(player, 'is_dead', False) and getattr(player, 'current_health', 0) > 0: 
            player.is_dead = False; player.death_animation_finished = False

    player.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm', 'attack_combo', 'attack_combo_nm', 'crouch_attack', 'aflame', 'aflame_crouch', 'jump']:
        player.current_frame = 0
        player.last_anim_update = current_ticks_ms 
        debug(f"{player_id_str} AnimReset: Frame reset for new state '{new_state}' or re-triggerable state.")
    player.state_timer = current_ticks_ms 

    debug_state_init = True 

    if new_state == 'idle':
        player.is_crouching = False
        if debug_state_init: debug(f"{player_id_str} StateInit_idle: is_crouching={player.is_crouching}")
    elif new_state == 'run':
        player.is_crouching = False
        if debug_state_init: debug(f"{player_id_str} StateInit_run: is_crouching={player.is_crouching}")
    elif new_state == 'crouch':
        player.is_crouching = True
        if debug_state_init: debug(f"{player_id_str} StateInit_crouch: is_crouching={player.is_crouching}")
    elif new_state == 'crouch_walk':
        player.is_crouching = True
        if debug_state_init: debug(f"{player_id_str} StateInit_crouch_walk: is_crouching={player.is_crouching}")
    elif new_state == 'jump':
        player.is_crouching = False
        debug(f"{player_id_str} StateInit_jump: Player entered 'jump' state. current vel.y={player.vel.y():.2f}. OnGround={player.on_ground}")
    elif new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        player.is_crouching = False
        if hasattr(player, 'vel') and hasattr(player.vel, 'setX') and hasattr(player.vel, 'setY'):
            player.vel.setX(C.PLAYER_DASH_SPEED * (1 if getattr(player, 'facing_right', True) else -1))
            player.vel.setY(0.0)
            if debug_state_init: debug(f"{player_id_str} StateInit_dash: vel.x={player.vel.x():.2f}")
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        player.is_crouching = False
        if hasattr(player, 'vel') and hasattr(player.vel, 'x') and hasattr(player.vel, 'setX'):
            current_vel_x = player.vel.x()
            target_roll_vel_x = C.PLAYER_ROLL_SPEED * (1 if getattr(player, 'facing_right', True) else -1)
            if abs(current_vel_x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(target_roll_vel_x)
            else: player.vel.setX(current_vel_x * 0.8 + target_roll_vel_x * 0.2)
            player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x())))
            if debug_state_init: debug(f"{player_id_str} StateInit_roll: vel.x={player.vel.x():.2f}")
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        player.is_crouching = True
        if hasattr(player, 'vel') and hasattr(player.vel, 'x') and hasattr(player.vel, 'setX'):
            if abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5:
                player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if getattr(player, 'facing_right', True) else -1))
            if debug_state_init: debug(f"{player_id_str} StateInit_slide/trans_start: vel.x={player.vel.x():.2f}")
    elif 'attack' in new_state:
        player.is_attacking = True; player.attack_timer = player.state_timer
        animation_for_this_attack = player_animations.get(new_state, []) if player_animations else []
        num_attack_frames = len(animation_for_this_attack)
        base_ms_per_frame = C.ANIM_FRAME_DURATION
        ms_per_frame_for_attack = base_ms_per_frame
        if getattr(player, 'attack_type', 0) == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
            ms_per_frame_for_attack = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
        player.attack_duration = num_attack_frames * ms_per_frame_for_attack if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
        if new_state.endswith('_nm') or new_state == 'crouch_attack':
             if hasattr(player, 'vel') and hasattr(player.vel, 'setX'): player.vel.setX(0.0)
        if debug_state_init: debug(f"{player_id_str} StateInit_attack: type={player.attack_type}, duration={player.attack_duration}ms")
    elif new_state == 'hit':
        player.is_taking_hit = True; player.hit_timer = player.state_timer 
        if not getattr(player, 'on_ground', False) and hasattr(player, 'vel') and \
           hasattr(player.vel, 'y') and hasattr(player.vel, 'setY') and hasattr(player.vel, 'setX'):
            if player.vel.y() > -abs(C.PLAYER_JUMP_STRENGTH * 0.5):
                player.vel.setX(player.vel.x() * -0.3)
                player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.4)
        player.is_attacking = False; setattr(player, 'attack_type', 0) 
        if debug_state_init: debug(f"{player_id_str} StateInit_hit: vel=({player.vel.x():.1f},{player.vel.y():.1f})")
    elif new_state == 'death' or new_state == 'death_nm':
        player.is_dead = True
        if hasattr(player, 'vel') and hasattr(player.vel, 'setX') and hasattr(player.vel, 'setY'):
            player.vel.setX(0.0) 
            if player.vel.y() < -1: player.vel.setY(1.0) 
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX') and hasattr(player.acc, 'setY'):
            player.acc.setX(0.0) 
            if not getattr(player, 'on_ground', False): player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
            else: player.vel.setY(0.0); player.acc.setY(0.0)
        player.death_animation_finished = False 
        if debug_state_init: debug(f"{player_id_str} StateInit_death: vel.y={player.vel.y():.1f}, acc.y={player.acc.y():.1f}")
    elif new_state == 'wall_slide' or new_state == 'wall_hang':
        if debug_state_init: debug(f"{player_id_str} StateInit_{new_state}")
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed']: 
        if hasattr(player, 'vel'): player.vel = QPointF(0,0)
        if hasattr(player, 'acc'): player.acc = QPointF(0,0)
        if new_state == 'petrified' and not getattr(player, 'on_ground', False): 
            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'):
                 player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        if debug_state_init: debug(f"{player_id_str} StateInit_{new_state}: Movement stopped.")
    
    elif debug_state_init and new_state not in ['idle','run','crouch','crouch_walk']: 
        debug(f"{player_id_str} StateInit_{new_state}: No specific init logic beyond base state set.")

    update_player_animation(player) 

#################### END OF FILE: player_state_handler.py ####################