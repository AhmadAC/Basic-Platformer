# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy state transitions and state-specific initializations.
MODIFIED: Accepts current_game_time_ms_param for consistent timing.
MODIFIED: Manages overall_fire_effect_start_time for 5s fire cycle.
MODIFIED: Clears conflicting status effects more robustly on state transitions.
MODIFIED: Added guard clauses for EnemyKnight's 'jump' state.
"""
# version 2.1.0 (EnemyKnight jump state guard)

import time
from typing import Any, Optional

# Game imports
import constants as C
from utils import PrintLimiter
from enemy_knight import EnemyKnight # Import EnemyKnight for type checking

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
    
    # --- EnemyKnight specific guard for jump state ---
    if isinstance(enemy, EnemyKnight) and getattr(enemy, '_is_mid_patrol_jump', False):
        allowed_states_mid_jump = ['jump', 'fall', 'hit', 'death', 'death_nm', 'idle', 'patrolling'] # 'idle'/'patrolling' set on landing
        # Status effects can also interrupt a jump
        allowed_states_mid_jump.extend(['aflame', 'frozen', 'zapped', 'petrified', 'smashed'])
        if new_state not in allowed_states_mid_jump:
            if _state_limiter.can_log(f"set_state_block_knight_jump_{enemy_id_str}_{new_state}"):
                debug(f"EnemyStateHandler ({enemy_id_str}, Knight): Blocked state change from '{current_enemy_state}' to '{new_state}' due to being mid-patrol-jump.")
            return
    # --- End EnemyKnight specific guard ---


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
                first_available_anim_key = next((key for key, anim_list in enemy_animations.items() if anim_list and anim_list[0] and not anim_list[0].isNull()), None) if enemy_animations else None
                if not first_available_anim_key:
                    if _state_limiter.can_log(f"enemy_set_state_no_anims_{enemy_id_str}"):
                        critical(f"EnemyStateHandler CRITICAL ({enemy_id_str}): No animations loaded AT ALL. Requested state: '{original_new_state_request}'. Enemy invalid.")
                    enemy._valid_init = False; return
                new_state = first_available_anim_key
                if _state_limiter.can_log(f"enemy_set_state_critical_fallback_{enemy_id_str}_{original_new_state_request}"):
                    critical(f"EnemyStateHandler CRITICAL ({enemy_id_str}): State '{original_new_state_request}' & fallbacks missing. Using first available animation: '{new_state}'.")

    # --- Determine if state can actually change ---
    # Added 'jump' to re-triggerable action states for Knight
    can_change_state_now = (current_enemy_state != new_state) or \
                           (new_state == 'hit') or \
                           ('attack' in new_state and not current_enemy_state.startswith('attack')) or \
                           (new_state == 'zapped' and not getattr(enemy, 'is_zapped', False)) or \
                           (new_state == 'aflame' and not getattr(enemy, 'is_aflame', False) and not getattr(enemy, 'is_deflaming', False)) or \
                           (new_state == 'jump' and current_enemy_state != 'jump') # Allow transition to jump

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
    # Always clear attacking if the new state is not an attack state
    if 'attack' not in new_state and getattr(enemy, 'is_attacking', False):
        enemy.is_attacking = False; setattr(enemy, 'attack_type', 0)

    # Clear hit stun if the new state is not 'hit' AND hit cooldown has passed
    if new_state != 'hit' and getattr(enemy, 'is_taking_hit', False):
        hit_cooldown_val = getattr(enemy, 'hit_cooldown', getattr(C, 'ENEMY_HIT_COOLDOWN', 500))
        if effective_current_time_ms - getattr(enemy, 'hit_timer', 0) >= hit_cooldown_val:
            enemy.is_taking_hit = False

    # --- Status Effect Flag Management (use effective_current_time_ms) ---
    if new_state == 'aflame':
        if not enemy.is_aflame and not enemy.is_deflaming: 
            enemy.overall_fire_effect_start_time = effective_current_time_ms
        enemy.is_aflame = True; enemy.aflame_timer_start = effective_current_time_ms
        enemy.aflame_damage_last_tick = enemy.aflame_timer_start
        enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False
    elif new_state == 'deflame':
        enemy.is_deflaming = True; enemy.deflame_timer_start = effective_current_time_ms
        enemy.is_aflame = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False
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
    elif new_state in ['idle', 'run', 'patrolling', 'chasing', 'fall', 'hit', 'death', 'death_nm', 'jump']: # Added jump
        was_on_fire_cycle = getattr(enemy, 'is_aflame', False) or getattr(enemy, 'is_deflaming', False)
        enemy.is_aflame = False; enemy.is_deflaming = False
        enemy.is_frozen = False; enemy.is_defrosting = False
        enemy.is_zapped = False
        if was_on_fire_cycle and hasattr(enemy, 'overall_fire_effect_start_time') and enemy.overall_fire_effect_start_time != 0:
            enemy.overall_fire_effect_start_time = 0
        if new_state not in ['petrified', 'smashed']:
            if getattr(enemy, 'is_petrified', False): enemy.is_petrified = False
            if getattr(enemy, 'is_stone_smashed', False): enemy.is_stone_smashed = False
    # --- End of Status Effect Flag Management ---

    enemy.state = new_state # Final state assignment

    if state_is_actually_changing or \
       new_state in ['hit', 'attack', 'attack_nm', 'aflame', 'zapped', 'jump']: # Added 'jump'
        enemy.current_frame = 0
        enemy.last_anim_update = effective_current_time_ms
    
    enemy.state_timer = effective_current_time_ms

    # --- State-Specific Initializations ---
    if 'attack' in new_state: # Covers attack, attack_nm, run_attack, etc. for Knight
        enemy.is_attacking = True
        enemy.attack_timer = effective_current_time_ms
        # Attack duration might be set by specific enemy type (e.g., Knight's attack_duration_map)
        # or by animation handler if duration depends on frames.
        # For generic Enemy, attack_duration is from EnemyBase.
        # For EnemyKnight, its AI should set a specific attack_type (string)
        # and the is_attacking loop in _knight_ai_update will use attack_duration_map.
        if isinstance(enemy, EnemyKnight) and hasattr(enemy, 'attack_duration_map') and hasattr(enemy, 'attack_type') and \
           str(enemy.attack_type) in enemy.attack_duration_map:
            enemy.attack_duration = enemy.attack_duration_map[str(enemy.attack_type)]
        elif hasattr(enemy, 'attack_duration') and not isinstance(enemy, EnemyKnight): # Generic enemy
            pass # Already set from EnemyBase or properties
        else: # Fallback duration if knight-specific is missing
            enemy.attack_duration = getattr(C, 'ENEMY_ATTACK_STATE_DURATION', 500)

    elif new_state == 'hit':
        enemy.is_taking_hit = True
        enemy.hit_timer = effective_current_time_ms
        enemy.is_attacking = False
    elif new_state == 'death' or new_state == 'death_nm':
        enemy.is_dead = True
        enemy.death_animation_finished = False
        if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
    elif new_state == 'jump': # Knight specific state
        if isinstance(enemy, EnemyKnight):
            enemy.on_ground = False # Ensure this is false when jump state starts
            # enemy.vel.y is set by AI when initiating jump
            # acc.y should remain gravity for jump
            if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setY'):
                enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)))
                enemy.acc.setY(enemy_gravity)
    elif new_state == 'fall':
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setY'):
            enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)))
            enemy.acc.setY(enemy_gravity)
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed', 'zapped']:
        if hasattr(enemy, 'vel'): enemy.vel.setX(0);
        if hasattr(enemy, 'acc'): enemy.acc.setX(0);
        if new_state in ['petrified', 'zapped'] and not getattr(enemy, 'on_ground', True) and hasattr(enemy, 'acc'):
            enemy.acc.setY(float(getattr(C, 'ENEMY_GRAVITY', 0.7)))
        elif new_state in ['frozen', 'defrost', 'smashed'] and hasattr(enemy, 'vel'):
            enemy.vel.setY(0) 
            if hasattr(enemy, 'acc'): enemy.acc.setY(0)
    
    update_enemy_animation(enemy)