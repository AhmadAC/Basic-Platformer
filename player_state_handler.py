#################### START OF FILE: player_state_handler.py ####################

# player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
MODIFIED: Accepts current_game_time_ms_param to ensure timer consistency.
MODIFIED: Manages overall_fire_effect_start_time for 5s fire cycle.
MODIFIED: Ensures fire is extinguished when player becomes frozen.
MODIFIED: Correctly sets/unsets is_crouching flag for all relevant states.
MODIFIED: Uses local import for update_player_animation to prevent circular dependency.
MODIFIED: Added ZAPPED state handling, including guard clauses, flag setting, and effect clearing.
"""
# version 2.0.12 (Zapped state integration)

import time 
from typing import Optional, Any

from PySide6.QtCore import QPointF

import constants as C
from utils import PrintLimiter

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    # Fallback logger
    def info(msg, *args, **kwargs): print(f"INFO_PSTATE: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATE: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATE: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PSTATE: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_PSTATE: {msg}")

# DO NOT import player_animation_handler at the top level here.

_start_time_player_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_state_monotonic) * 1000)

def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
    # --- LOCAL IMPORT to break circular dependency ---
    try:
        from player_animation_handler import update_player_animation
    except ImportError:
        critical("PLAYER_STATE_HANDLER (set_player_state): Failed to import update_player_animation locally.")
        def update_player_animation(player_arg: Any): # Fallback dummy
            if hasattr(player_arg, 'animate') and callable(player_arg.animate): player_arg.animate()
            else: critical(f"PLAYER_STATE_HANDLER (Fallback): Cannot call animate for P{getattr(player_arg, 'player_id', 'N/A')}")
    # --- END LOCAL IMPORT ---

    if not getattr(player, '_valid_init', False):
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_invalid_player_{getattr(player, 'player_id', 'unknown')}"):
            debug(f"PlayerStateHandler: Skip set state on invalid P{getattr(player, 'player_id', 'N/A')}.")
        return

    effective_current_time_ms = current_game_time_ms_param if current_game_time_ms_param is not None else get_current_ticks_monotonic()
    original_new_state_request = new_state
    player_id_str = f"P{getattr(player, 'player_id', 'N/A')}"
    current_player_state = getattr(player, 'state', 'idle')

    # --- Guard Clauses for Overriding States (Petrified, Smashed, Zapped, Frozen) ---
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False) and \
       new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_petrified_{player.player_id}_{new_state}"):
            debug(f"PSH ({player_id_str}): Blocked '{new_state}' due to petrified.")
        return
    if getattr(player, 'is_stone_smashed', False) and new_state not in ['smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_smashed_{player.player_id}_{new_state}"):
            debug(f"PSH ({player_id_str}): Blocked '{new_state}' due to smashed.")
        return
    
    # Zapped Guard: If player is zapped, most state changes are blocked unless it's to clear zapped or a terminal state.
    if getattr(player, 'is_zapped', False):
        allowed_states_while_zapped = ['zapped', 'death', 'death_nm', 'idle', 'fall'] # 'idle'/'fall' typically set by status_effects when zapped ends
        if new_state not in allowed_states_while_zapped:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_zapped_{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being zapped.")
            return

    if getattr(player, 'is_frozen', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit', 'idle', 'zapped']: # Allow zapped to override frozen
             if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_frozen_{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being frozen.")
             return
    if getattr(player, 'is_defrosting', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit', 'idle', 'fall', 'zapped']: # Allow zapped to override defrost
             if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_defrost_{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being defrosted.")
             return

    # Petrified state check for certain incoming states
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state in ['frozen', 'defrost', 'aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'hit', 'zapped']:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"block_petri_status_{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Blocked status '{new_state}' due to petrification.")
            return

    # --- Automatic state adjustments based on current conditions ---
    is_crouching_flag_before_auto_adjust = getattr(player, 'is_crouching', False) 
    if getattr(player, 'is_aflame', False) and new_state not in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        if new_state not in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'death', 'death_nm', 'hit', 'idle']:
            new_state = 'burning_crouch' if is_crouching_flag_before_auto_adjust else 'burning'
    elif getattr(player, 'is_deflaming', False) and new_state not in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        if new_state not in ['deflame', 'deflame_crouch', 'death', 'death_nm', 'hit', 'idle']:
            new_state = 'deflame_crouch' if is_crouching_flag_before_auto_adjust else 'deflame'
    # Frozen/Defrost/Zapped adjustments are implicitly handled by their guard clauses or by the incoming new_state.

    # --- Validate animation key ---
    animation_key_to_check = new_state
    player_animations = getattr(player, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']: # Stone states have dedicated frames
        if not player_animations or animation_key_to_check not in player_animations or not player_animations.get(animation_key_to_check):
            fallback_state_key = 'fall' if not getattr(player, 'on_ground', False) else 'idle'
            if player_animations and fallback_state_key in player_animations and player_animations.get(fallback_state_key):
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_fallback_{player.player_id}_{original_new_state_request}_{new_state}"):
                    warning(f"Player Warning ({player_id_str}): State '{original_new_state_request}' (to '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else:
                first_available_anim_key = next((k for k, al in player_animations.items() if al), None) if player_animations else None
                if not first_available_anim_key:
                    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"no_anims_{player.player_id}"):
                        critical(f"Player CRITICAL ({player_id_str}): No anims loaded! Req state: '{original_new_state_request}'. Invalid.")
                    player._valid_init = False; return
                new_state = first_available_anim_key
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"critical_fallback_{player.player_id}_{original_new_state_request}"):
                    critical(f"Player CRITICAL ({player_id_str}): State '{original_new_state_request}' & fallbacks missing. Using first anim: '{new_state}'.")

    # --- Check if state change is allowed or needed ---
    can_change_state_now = (current_player_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and current_player_state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch']) or \
                           (new_state == 'zapped' and not getattr(player, 'is_zapped', False)) # Allow transition to 'zapped' if not already zapped

    if getattr(player, 'is_dead', False) and getattr(player, 'death_animation_finished', False) and not getattr(player, 'is_stone_smashed', False):
         if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']: can_change_state_now = False

    if not can_change_state_now:
        if current_player_state == new_state and hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"no_change_{player_id_str}_{new_state}"):
             debug(f"PSH ({player_id_str}): State change to '{new_state}' not allowed or no change needed.")
        if current_player_state == new_state: update_player_animation(player)
        return

    state_is_actually_changing = (current_player_state != new_state)
    if state_is_actually_changing:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"state_change_{player.player_id}_{current_player_state}_{new_state}"):
             debug(f"PSH ({player_id_str}): State changing from '{current_player_state}' to '{new_state}' (original req '{original_new_state_request}')")
    
    setattr(player, '_last_state_for_debug', new_state)

    # Clear action flags terminated by a new state
    if 'attack' not in new_state and getattr(player, 'is_attacking', False):
        player.is_attacking = False; setattr(player, 'attack_type', 0)
    if new_state != 'hit' and getattr(player, 'is_taking_hit', False):
        if effective_current_time_ms - getattr(player, 'hit_timer', 0) >= getattr(player, 'hit_cooldown', C.PLAYER_HIT_COOLDOWN):
            player.is_taking_hit = False
    if new_state != 'dash' and getattr(player, 'is_dashing', False): player.is_dashing = False
    if new_state != 'roll' and getattr(player, 'is_rolling', False): player.is_rolling = False
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end'] and getattr(player, 'is_sliding', False): player.is_sliding = False

    # --- Player Crouching Flag Management ---
    if new_state in ['crouch', 'crouch_walk', 'crouch_attack', 'crouch_trans', 
                     'aflame_crouch', 'burning_crouch', 'deflame_crouch',
                     'slide', 'slide_trans_start', 'slide_trans_end']:
        player.is_crouching = True
    elif new_state not in ['petrified', 'smashed']: 
        player.is_crouching = False

    # --- Status Effects Flags and Timers (based on new_state) ---
    if new_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch']:
        if not getattr(player, 'is_aflame', False): 
            player.aflame_timer_start = effective_current_time_ms
            player.aflame_damage_last_tick = player.aflame_timer_start
            if not getattr(player, 'is_deflaming', False) and \
               (not hasattr(player, 'overall_fire_effect_start_time') or player.overall_fire_effect_start_time == 0):
                player.overall_fire_effect_start_time = effective_current_time_ms
        player.is_aflame = True; player.is_deflaming = False 
        player.is_frozen = False; player.is_defrosting = False; player.is_zapped = False
    elif new_state in ['deflame', 'deflame_crouch']:
        if not getattr(player, 'is_deflaming', False): player.deflame_timer_start = effective_current_time_ms
        player.is_deflaming = True; player.is_aflame = False
        player.is_frozen = False; player.is_defrosting = False; player.is_zapped = False
    elif new_state == 'frozen':
        if not getattr(player, 'is_frozen', False): player.frozen_effect_timer = effective_current_time_ms
        player.is_frozen = True; player.is_defrosting = False
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"frozen_ext_fire_P{player.player_id}"):
                debug(f"PSH (P{player.player_id}): To 'frozen'. Extinguishing fire.")
        player.is_aflame = False; player.is_deflaming = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_zapped = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
            player.is_aflame = False; player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_zapped = False
    elif new_state == 'zapped': # ADDED ZAPPED HANDLING
        if not getattr(player, 'is_zapped', False): # If not already zapped, start timers
            player.zapped_timer_start = effective_current_time_ms
            player.zapped_damage_last_tick = player.zapped_timer_start
        player.is_zapped = True
        # Zapped extinguishes fire and cancels freeze
        if getattr(player, 'is_aflame', False) or getattr(player, 'is_deflaming', False):
             if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"zapped_ext_fire_P{player.player_id}"):
                debug(f"PSH (P{player.player_id}): To 'zapped'. Extinguishing fire.")
        player.is_aflame = False; player.is_deflaming = False
        if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0
        player.is_frozen = False; player.is_defrosting = False
    elif new_state == 'petrified':
        if not getattr(player, 'is_petrified', False): 
            player.facing_at_petrification = getattr(player, 'facing_right', True)
            player.was_crouching_when_petrified = getattr(player, 'is_crouching', False) 
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True 
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False; player.overall_fire_effect_start_time = 0; player.is_zapped = False
    elif new_state == 'smashed':
        if not getattr(player, 'is_stone_smashed', False): player.stone_smashed_timer_start = effective_current_time_ms
        player.is_stone_smashed = True; player.is_petrified = True 
        player.is_dead = True; player.death_animation_finished = False 
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False; player.overall_fire_effect_start_time = 0; player.is_zapped = False
    else: 
        flags_were_cleared_in_else = False
        if getattr(player, 'is_aflame', False): player.is_aflame = False; flags_were_cleared_in_else = True
        if getattr(player, 'is_deflaming', False): player.is_deflaming = False; flags_were_cleared_in_else = True
        if flags_were_cleared_in_else and getattr(player, 'overall_fire_effect_start_time', 0) != 0 :
            player.overall_fire_effect_start_time = 0
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"clear_overall_fire_final_else_{player.player_id}_{new_state}"):
                debug(f"PSH ({player_id_str}): Cleared 5s fire timer from final else to non-fire state '{new_state}'.")
        
        if new_state not in ['frozen', 'defrost']:
            if getattr(player, 'is_frozen', False): player.is_frozen = False
            if getattr(player, 'is_defrosting', False): player.is_defrosting = False
        if new_state not in ['zapped']: # Clear zapped if transitioning to a non-zapped state
            if getattr(player, 'is_zapped', False): player.is_zapped = False

        if new_state not in ['petrified', 'smashed']:
            if getattr(player, 'is_petrified', False): player.is_petrified = False
            if getattr(player, 'is_stone_smashed', False): player.is_stone_smashed = False
            if getattr(player, 'was_crouching_when_petrified', False): player.was_crouching_when_petrified = False

    player.state = new_state 
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm', 'attack_combo', 'attack_combo_nm', 'crouch_attack', 'aflame', 'aflame_crouch', 'jump', 'zapped']:
        player.current_frame = 0
        player.last_anim_update = effective_current_time_ms
    player.state_timer = effective_current_time_ms

    # Final state-specific actions (mostly movement related)
    if new_state == 'idle' or new_state == 'run' or new_state == 'jump':
        pass 
    elif new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        if hasattr(player, 'vel'): player.vel.setX(C.PLAYER_DASH_SPEED * (1 if getattr(player, 'facing_right', True) else -1)); player.vel.setY(0.0)
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        if hasattr(player, 'vel'):
            current_vel_x = player.vel.x(); target_roll_vel_x = C.PLAYER_ROLL_SPEED * (1 if getattr(player, 'facing_right', True) else -1)
            if abs(current_vel_x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(target_roll_vel_x)
            else: player.vel.setX(current_vel_x * 0.8 + target_roll_vel_x * 0.2)
            player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x())))
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        if hasattr(player, 'vel') and abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5:
            player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if getattr(player, 'facing_right', True) else -1))
    elif 'attack' in new_state: 
        player.is_attacking = True; player.attack_timer = player.state_timer
        anim_frames = player_animations.get(new_state, []) if player_animations else []
        num_frames = len(anim_frames); ms_per_frame_attack = C.ANIM_FRAME_DURATION
        if getattr(player, 'attack_type', 0) == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
            ms_per_frame_attack = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
        player.attack_duration = num_frames * ms_per_frame_attack if num_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
        if new_state.endswith('_nm') or new_state == 'crouch_attack':
            if hasattr(player, 'vel'): player.vel.setX(0.0)
    elif new_state == 'hit':
        player.is_taking_hit = True; player.hit_timer = player.state_timer 
        if not getattr(player, 'on_ground', False) and hasattr(player, 'vel'): 
            if player.vel.y() > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): 
                player.vel.setX(player.vel.x() * -0.3); player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.4)
        player.is_attacking = False; setattr(player, 'attack_type', 0) 
    elif new_state == 'death' or new_state == 'death_nm':
        player.is_dead = True 
        if hasattr(player, 'vel'): player.vel.setX(0.0); 
        if hasattr(player, 'vel') and player.vel.y() < -1: player.vel.setY(1.0) 
        if hasattr(player, 'acc'): player.acc.setX(0.0) 
        player.death_animation_finished = False 
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']: # Added zapped
        if hasattr(player, 'vel'): player.vel = QPointF(0,0)
        if hasattr(player, 'acc'): player.acc = QPointF(0,0)
        if new_state == 'petrified' and not getattr(player, 'on_ground', False) and hasattr(player, 'acc'):
                 player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        # Zapped might allow gravity if airborne, similar to petrified
        elif new_state == 'zapped' and not getattr(player, 'on_ground', False) and hasattr(player, 'acc'):
                 player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
    
    update_player_animation(player)

#################### END OF FILE: player_state_handler.py ####################