# player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
MODIFIED: Accepts current_game_time_ms_param to ensure timer consistency.
"""
# version 2.0.7 (Timer consistency via parameter)

import time # For monotonic timer
from typing import Optional, Any # Added Any

# PySide6 imports
from PySide6.QtCore import QPointF

# Game imports
import constants as C
from utils import PrintLimiter

# Logger is now imported directly
from logger import info, debug, warning, error, critical

try:
    from player_animation_handler import update_player_animation # Ensure this is PySide6 compatible
except ImportError:
    critical("PLAYER_STATE_HANDLER (AnimImportFail): player_animation_handler.update_player_animation not found.")
    def update_player_animation(player: Any): # Added type hint
        if hasattr(player, 'animate') and callable(player.animate):
            player.animate()
        else:
            critical(f"PLAYER_STATE_HANDLER (AnimImportFail-Fallback): Cannot call animate for Player ID {getattr(player, 'player_id', 'N/A')}")


_start_time_player_state_monotonic = time.monotonic() # This is player_state_handler's own start time
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since this module was initialized."""
    return int((time.monotonic() - _start_time_player_state_monotonic) * 1000)

# --- MODIFIED set_player_state signature ---
def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
    if not getattr(player, '_valid_init', False):
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_invalid_player_{getattr(player, 'player_id', 'unknown')}"):
            debug(f"PlayerStateHandler: Attempted to set state on invalid player {getattr(player, 'player_id', 'N/A')}. Ignoring.")
        return

    # --- MODIFIED: Use passed-in time if available, otherwise use this module's clock ---
    effective_current_time_ms = current_game_time_ms_param if current_game_time_ms_param is not None else get_current_ticks_monotonic()
    
    original_new_state_request = new_state
    player_id_str = f"P{getattr(player, 'player_id', 'N/A')}"
    current_player_state = getattr(player, 'state', 'idle')

    # Guard Clauses for Overriding States
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False) and \
       new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_petrified_{player.player_id}_{new_state}"):
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if getattr(player, 'is_stone_smashed', False) and new_state not in ['smashed', 'death', 'death_nm', 'idle']:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_smashed_{player.player_id}_{new_state}"):
            debug(f"PlayerStateHandler ({player_id_str}): Blocked state change from '{current_player_state}' to '{new_state}' due to being stone_smashed.")
        return
    if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
        if new_state in ['frozen', 'defrost', 'aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'hit']:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"set_state_block_petrified_status_{player.player_id}_{new_state}"):
                debug(f"PlayerStateHandler ({player_id_str}): Blocked status effect state change to '{new_state}' due to petrification.")
            return

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

    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    
    player_animations = getattr(player, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']:
        if not player_animations or animation_key_to_check not in player_animations or \
           not player_animations.get(animation_key_to_check):
            fallback_state_key = 'fall' if not getattr(player, 'on_ground', False) else 'idle'
            if player_animations and fallback_state_key in player_animations and player_animations.get(fallback_state_key):
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}_{new_state}"):
                    warning(f"Player Warning ({player_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else:
                first_available_anim_key = next((key for key, anim_list in player_animations.items() if anim_list), None) if player_animations else None
                if not first_available_anim_key:
                    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_no_anims_{player.player_id}"):
                        critical(f"Player CRITICAL ({player_id_str}): No animations loaded AT ALL. Requested state: '{original_new_state_request}'. Player invalid.")
                    player._valid_init = False; return
                new_state = first_available_anim_key
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                    critical(f"Player CRITICAL ({player_id_str}): State '{original_new_state_request}' & fallbacks missing. Using first available animation: '{new_state}'.")

    can_change_state_now = (current_player_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and current_player_state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch'])

    if getattr(player, 'is_dead', False) and getattr(player, 'death_animation_finished', False) and not getattr(player, 'is_stone_smashed', False):
         if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']:
            can_change_state_now = False

    if not can_change_state_now:
        if current_player_state == new_state and hasattr(player, 'print_limiter') and \
           player.print_limiter.can_log(f"set_state_no_change_{player_id_str}_{new_state}"):
             debug(f"PlayerStateHandler ({player_id_str}): State change to '{new_state}' not allowed or no actual change needed (current state already '{current_player_state}').")
        if current_player_state == new_state: 
            update_player_animation(player)
        return

    state_is_actually_changing = (current_player_state != new_state)
    if state_is_actually_changing:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"state_change_{player.player_id}_{current_player_state}_{new_state}"):
             debug(f"PlayerStateHandler ({player_id_str}): State changing from '{current_player_state}' to '{new_state}' (original request was '{original_new_state_request}')")
    
    setattr(player, '_last_state_for_debug', new_state)

    if 'attack' not in new_state and getattr(player, 'is_attacking', False):
        player.is_attacking = False; setattr(player, 'attack_type', 0)
    if new_state != 'hit' and getattr(player, 'is_taking_hit', False):
        if effective_current_time_ms - getattr(player, 'hit_timer', 0) >= getattr(player, 'hit_cooldown', C.PLAYER_HIT_COOLDOWN):
            player.is_taking_hit = False
    if new_state != 'dash' and getattr(player, 'is_dashing', False): player.is_dashing = False
    if new_state != 'roll' and getattr(player, 'is_rolling', False): player.is_rolling = False
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end'] and getattr(player, 'is_sliding', False): player.is_sliding = False

    # Status Effects Flags and Timers (use effective_current_time_ms)
    if new_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch']:
        if not getattr(player, 'is_aflame', False): 
            player.aflame_timer_start = effective_current_time_ms
            player.aflame_damage_last_tick = player.aflame_timer_start
        player.is_aflame = True; player.is_deflaming = False 
    elif new_state in ['deflame', 'deflame_crouch']:
        if not getattr(player, 'is_deflaming', False): 
            player.deflame_timer_start = effective_current_time_ms
        player.is_deflaming = True; player.is_aflame = False 
    else: 
        if getattr(player, 'is_aflame', False): player.is_aflame = False
        if getattr(player, 'is_deflaming', False): player.is_deflaming = False
        
    if new_state == 'frozen':
        if not getattr(player, 'is_frozen', False): 
            player.frozen_effect_timer = effective_current_time_ms
        player.is_frozen = True; player.is_defrosting = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False
    else: 
        if getattr(player, 'is_frozen', False): player.is_frozen = False
        if getattr(player, 'is_defrosting', False): player.is_defrosting = False
        
    if new_state == 'petrified':
        if not getattr(player, 'is_petrified', False): 
            player.facing_at_petrification = getattr(player, 'facing_right', True)
            player.was_crouching_when_petrified = getattr(player, 'is_crouching', False)
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True 
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False 
    elif new_state == 'smashed':
        if not getattr(player, 'is_stone_smashed', False): 
            player.stone_smashed_timer_start = effective_current_time_ms
        player.is_stone_smashed = True; player.is_petrified = True 
        player.is_dead = True; player.death_animation_finished = False 
    elif getattr(player, 'is_petrified', False) and new_state not in ['petrified', 'smashed']: 
        player.is_petrified = False; player.is_stone_smashed = False; player.was_crouching_when_petrified = False
        if getattr(player, 'is_dead', False) and getattr(player, 'current_health', 0) > 0: 
            player.is_dead = False; player.death_animation_finished = False

    player.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm', 'attack_combo', 'attack_combo_nm', 'crouch_attack', 'aflame', 'aflame_crouch', 'jump']:
        player.current_frame = 0
        player.last_anim_update = effective_current_time_ms # MODIFIED
    player.state_timer = effective_current_time_ms # MODIFIED

    # State-specific initializations
    if new_state == 'idle': player.is_crouching = False
    elif new_state == 'run': player.is_crouching = False
    elif new_state == 'crouch' or new_state == 'crouch_walk': player.is_crouching = True
    elif new_state == 'jump': player.is_crouching = False
    elif new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        player.is_crouching = False
        if hasattr(player, 'vel'): player.vel.setX(C.PLAYER_DASH_SPEED * (1 if getattr(player, 'facing_right', True) else -1)); player.vel.setY(0.0)
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        player.is_crouching = False
        if hasattr(player, 'vel'):
            current_vel_x = player.vel.x()
            target_roll_vel_x = C.PLAYER_ROLL_SPEED * (1 if getattr(player, 'facing_right', True) else -1)
            if abs(current_vel_x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(target_roll_vel_x)
            else: player.vel.setX(current_vel_x * 0.8 + target_roll_vel_x * 0.2)
            player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x())))
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        player.is_crouching = True
        if hasattr(player, 'vel') and abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5:
            player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if getattr(player, 'facing_right', True) else -1))
    elif 'attack' in new_state:
        player.is_attacking = True; player.attack_timer = player.state_timer
        anim_frames = player_animations.get(new_state, []) if player_animations else []
        num_frames = len(anim_frames)
        ms_per_frame_attack = C.ANIM_FRAME_DURATION
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
        if hasattr(player, 'acc') and not getattr(player, 'on_ground', False): player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        elif hasattr(player, 'acc') and getattr(player, 'on_ground', False): player.vel.setY(0.0); player.acc.setY(0.0)
        player.death_animation_finished = False 
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed']: 
        if hasattr(player, 'vel'): player.vel = QPointF(0,0)
        if hasattr(player, 'acc'): player.acc = QPointF(0,0)
        if new_state == 'petrified' and not getattr(player, 'on_ground', False) and hasattr(player, 'acc'):
                 player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
    
    update_player_animation(player)