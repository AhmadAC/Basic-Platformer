# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy state transitions and state-specific initializations.
MODIFIED: Accepts current_game_time_ms_param for consistent timing.
MODIFIED: Manages overall_fire_effect_start_time for 5s fire cycle.
MODIFIED: Clears conflicting status effects more robustly on state transitions.
"""
# version 2.0.9 (Robust status clearing and 5s fire timer management)

import time
from typing import Any, Optional

# Game imports
import constants as C
from utils import PrintLimiter

# Logger is now imported directly
from logger import info, debug, warning, error, critical # Use global logger

try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    critical("ENEMY_STATE_HANDLER (AnimImportFail): enemy_animation_handler.update_enemy_animation not found.")
    def update_enemy_animation(enemy: Any):
        if hasattr(enemy, 'animate') and callable(enemy.animate):
            enemy.animate()
        else:
            critical(f"ENEMY_STATE_HANDLER (AnimImportFail-Fallback): Cannot call animate for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


_state_limiter = PrintLimiter(default_limit=5, default_period=2.0)

_start_time_enemy_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_state_monotonic) * 1000)

def set_enemy_state(enemy: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
    if not hasattr(enemy, '_valid_init') or not enemy._valid_init:
        if _state_limiter.can_log(f"set_state_invalid_enemy_{getattr(enemy, 'enemy_id', 'unknown')}"):
            debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {getattr(enemy, 'enemy_id', 'N/A')}. Ignoring.")
        return

    effective_current_time_ms = current_game_time_ms_param if current_game_time_ms_param is not None else get_current_ticks_monotonic()
    
    original_new_state_request = new_state
    enemy_id_str = f"E{getattr(enemy, 'enemy_id', 'N/A')}"
    current_enemy_state = getattr(enemy, 'state', 'idle')

    # --- Guard Clauses for Overriding States (Petrified, Smashed, Zapped, Frozen) ---
    # These states should typically prevent transitions to "lesser" states unless it's a reset or a specific un-effecting transition.
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        if new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']: # 'idle' might be used for a forced reset
            if _state_limiter.can_log(f"set_state_block_petrified_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being petrified (not smashed).")
            return
    if getattr(enemy, 'is_stone_smashed', False):
        if new_state not in ['smashed', 'death', 'death_nm', 'idle']:
            if _state_limiter.can_log(f"set_state_block_smashed_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being stone_smashed.")
            return
    if getattr(enemy, 'is_zapped', False):
        if new_state not in ['zapped', 'death', 'death_nm', 'idle', 'fall']: # Allow fall if zapped mid-air and gravity applies
             if _state_limiter.can_log(f"set_state_block_zapped_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being zapped.")
             return
    if getattr(enemy, 'is_frozen', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'idle']:
             if _state_limiter.can_log(f"set_state_block_frozen_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being frozen.")
             return
    if getattr(enemy, 'is_defrosting', False):
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'idle', 'fall']:
             if _state_limiter.can_log(f"set_state_block_defrost_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being defrosted.")
             return


    # --- Automatic state adjustments based on current conditions (e.g., if aflame, switch to burning if moving) ---
    # This part should be minimal if enemy_ai_handler is correctly determining states.
    # It's more for ensuring visual consistency if a general state is requested while a sub-state is active.
    # For enemies, their AI usually directly sets 'run' or 'idle', 'attack', so this might be less critical than for player.

    # --- Animation Key Validation (crucial) ---
    animation_key_to_check = new_state
    enemy_animations = getattr(enemy, 'animations', None)
    if animation_key_to_check not in ['petrified', 'smashed']: # Stone states have dedicated frames
        if not enemy_animations or animation_key_to_check not in enemy_animations or \
           not enemy_animations.get(animation_key_to_check):
            fallback_state_key = 'fall' if not getattr(enemy, 'on_ground', False) else 'idle'
            if enemy_animations and fallback_state_key in enemy_animations and enemy_animations.get(fallback_state_key):
                if _state_limiter.can_log(f"enemy_set_state_fallback_{enemy_id_str}_{original_new_state_request}_{new_state}"):
                    warning(f"EnemyStateHandler Warning ({enemy_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else:
                first_available_anim_key = next((key for key, anim_list in enemy_animations.items() if anim_list), None) if enemy_animations else None
                if not first_available_anim_key:
                    if _state_limiter.can_log(f"enemy_set_state_no_anims_{enemy_id_str}"):
                        critical(f"EnemyStateHandler CRITICAL ({enemy_id_str}): No animations loaded AT ALL. Requested state: '{original_new_state_request}'. Enemy invalid.")
                    enemy._valid_init = False; return
                new_state = first_available_anim_key
                if _state_limiter.can_log(f"enemy_set_state_critical_fallback_{enemy_id_str}_{original_new_state_request}"):
                    critical(f"EnemyStateHandler CRITICAL ({enemy_id_str}): State '{original_new_state_request}' & fallbacks missing. Using first available animation: '{new_state}'.")

    # --- Determine if state can actually change ---
    can_change_state_now = (current_enemy_state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state == 'attack' or new_state == 'attack_nm') or \
                           (new_state == 'zapped' and not getattr(enemy, 'is_zapped', False)) or \
                           (new_state == 'aflame' and not getattr(enemy, 'is_aflame', False) and not getattr(enemy, 'is_deflaming', False))

    # Prevent changing state if dead and animation finished (unless petrified/smashed logic handles it)
    if getattr(enemy, 'is_dead', False) and getattr(enemy, 'death_animation_finished', False) and \
       not getattr(enemy, 'is_stone_smashed', False) and not getattr(enemy, 'is_petrified', False):
         if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']: # 'idle' allowed for forced reset
            can_change_state_now = False

    if not can_change_state_now:
        if current_enemy_state == new_state and _state_limiter.can_log(f"set_state_no_change_{enemy_id_str}_{new_state}"):
             debug(f"EnemyStateHandler ({enemy_id_str}): State change to '{new_state}' not allowed or no actual change needed (current state already '{current_enemy_state}').")
        if current_enemy_state == new_state: # Still call animation if state hasn't changed but this function was called
            update_enemy_animation(enemy)
        return

    state_is_actually_changing = (current_enemy_state != new_state)
    if state_is_actually_changing:
        if _state_limiter.can_log(f"state_change_{enemy_id_str}_{current_enemy_state}_{new_state}"):
             debug(f"EnemyStateHandler ({enemy_id_str}): State changing from '{current_enemy_state}' to '{new_state}' (original request was '{original_new_state_request}')")
    
    setattr(enemy, '_last_state_for_debug', new_state)

    # --- Clear Action/Status Flags based on the NEW state ---
    # This is crucial for correctly managing status effects and actions.

    # Always clear attacking if the new state is not an attack state
    if 'attack' not in new_state and getattr(enemy, 'is_attacking', False):
        enemy.is_attacking = False; setattr(enemy, 'attack_type', 0)

    # Clear hit stun if the new state is not 'hit' AND hit cooldown has passed
    if new_state != 'hit' and getattr(enemy, 'is_taking_hit', False):
        if effective_current_time_ms - getattr(enemy, 'hit_timer', 0) >= getattr(enemy, 'hit_cooldown', C.ENEMY_HIT_COOLDOWN):
            enemy.is_taking_hit = False

    # --- Status Effect Flag Management (use effective_current_time_ms) ---
    # This section sets flags when *entering* a status effect state.
    # And clears flags when transitioning *out* of status effect states to normal states.

    if new_state == 'aflame':
        if not enemy.is_aflame and not enemy.is_deflaming: # Starting a new fire cycle
            enemy.overall_fire_effect_start_time = effective_current_time_ms
            debug(f"EnemyStateHandler ({enemy_id_str}): Starting 5s overall fire timer due to state 'aflame'. Time: {effective_current_time_ms}")
        enemy.is_aflame = True; enemy.aflame_timer_start = effective_current_time_ms
        enemy.aflame_damage_last_tick = enemy.aflame_timer_start
        enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False
        
    elif new_state == 'deflame':
        enemy.is_deflaming = True; enemy.deflame_timer_start = effective_current_time_ms
        enemy.is_aflame = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False
        # overall_fire_effect_start_time continues from when 'aflame' started.
    
    elif new_state == 'frozen':
        if not enemy.is_frozen: enemy.frozen_effect_timer = effective_current_time_ms
        enemy.is_frozen = True; enemy.is_defrosting = False
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.overall_fire_effect_start_time = 0; enemy.is_zapped = False
    elif new_state == 'defrost':
        enemy.is_defrosting = True; enemy.is_frozen = False
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.overall_fire_effect_start_time = 0; enemy.is_zapped = False
        
    elif new_state == 'zapped':
        if not getattr(enemy, 'is_zapped', False):
            enemy.zapped_timer_start = effective_current_time_ms
            enemy.zapped_damage_last_tick = enemy.zapped_timer_start
        enemy.is_zapped = True
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.overall_fire_effect_start_time = 0
        enemy.is_frozen = False; enemy.is_defrosting = False
        
    elif new_state == 'petrified':
        if not enemy.is_petrified: 
            enemy.facing_at_petrification = getattr(enemy, 'facing_right', True)
        enemy.is_petrified = True; enemy.is_stone_smashed = False
        enemy.is_dead = True; enemy.death_animation_finished = True 
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False; enemy.overall_fire_effect_start_time = 0
    elif new_state == 'smashed':
        if not enemy.is_stone_smashed: 
            enemy.smashed_timer_start = effective_current_time_ms
        enemy.is_stone_smashed = True; enemy.is_petrified = True 
        enemy.is_dead = True; enemy.death_animation_finished = False 
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False; enemy.overall_fire_effect_start_time = 0
    
    # Clear all temporary status effects if transitioning to a "normal" state (not a status itself)
    # or if the new state is 'hit' (which implies other statuses should be interrupted unless it's petrified/smashed).
    elif new_state in ['idle', 'run', 'patrolling', 'chasing', 'fall', 'hit', 'death', 'death_nm']:
        was_on_fire_cycle = getattr(enemy, 'is_aflame', False) or getattr(enemy, 'is_deflaming', False)
        
        enemy.is_aflame = False
        enemy.is_deflaming = False
        enemy.is_frozen = False
        enemy.is_defrosting = False
        enemy.is_zapped = False
        
        if was_on_fire_cycle and hasattr(enemy, 'overall_fire_effect_start_time') and enemy.overall_fire_effect_start_time != 0:
            enemy.overall_fire_effect_start_time = 0
            debug(f"EnemyStateHandler ({enemy_id_str}): Cleared 5s overall fire timer as enemy transitioned to non-fire state '{new_state}'.")
        
        # For petrified/smashed, only clear if the new state is not one of them (e.g., forced 'idle' from reset)
        if new_state not in ['petrified', 'smashed']:
            if getattr(enemy, 'is_petrified', False): enemy.is_petrified = False
            if getattr(enemy, 'is_stone_smashed', False): enemy.is_stone_smashed = False

    # --- End of Status Effect Flag Management ---

    enemy.state = new_state # Final state assignment

    # Reset animation frame and timers if state actually changed or if it's a re-triggerable action state
    if state_is_actually_changing or \
       new_state in ['hit', 'attack', 'attack_nm', 'aflame', 'zapped']: # Added zapped
        enemy.current_frame = 0
        enemy.last_anim_update = effective_current_time_ms
    
    enemy.state_timer = effective_current_time_ms

    # --- State-Specific Initializations ---
    if new_state == 'attack' or new_state == 'attack_nm':
        enemy.is_attacking = True
        enemy.attack_timer = effective_current_time_ms # Use effective time
        # Note: attack_duration might be set by animation handler if it depends on frames
    elif new_state == 'hit':
        enemy.is_taking_hit = True
        enemy.hit_timer = effective_current_time_ms # Use effective time
        enemy.is_attacking = False # Cancel attack if hit
    elif new_state == 'death' or new_state == 'death_nm':
        enemy.is_dead = True
        enemy.death_animation_finished = False
        if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        if hasattr(enemy, 'vel'): enemy.vel.setX(0);
        if hasattr(enemy, 'acc'): enemy.acc.setX(0);
        # Allow gravity for petrified/zapped if airborne, disable for frozen/defrost
        if new_state in ['petrified', 'zapped'] and not getattr(enemy, 'on_ground', True) and hasattr(enemy, 'acc'):
            enemy.acc.setY(float(getattr(C, 'ENEMY_GRAVITY', 0.7)))
        elif new_state in ['frozen', 'defrost', 'smashed'] and hasattr(enemy, 'vel'):
            enemy.vel.setY(0) # Ensure Y velocity is zeroed too for these
            if hasattr(enemy, 'acc'): enemy.acc.setY(0)
    
    update_enemy_animation(enemy)