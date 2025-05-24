#################### START OF FILE: enemy_state_handler.py ####################

# enemy_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles enemy state transitions and state-specific initializations.
"""
import time
from typing import Any

# Game imports
import constants as C
from utils import PrintLimiter 

# Logger
from logger import debug, warning, critical # Use global logger

# Animation handler - potential circular import if it imports this module back
# To be safe, if enemy_animation_handler needs set_enemy_state, it should import it locally within functions.
try:
    from enemy_animation_handler import update_enemy_animation
except ImportError:
    critical("ENEMY_STATE_HANDLER: Failed to import update_enemy_animation.")
    def update_enemy_animation(enemy: Any): pass # Fallback

_state_limiter = PrintLimiter(default_limit=5, default_period=2.0)

_start_time_enemy_state_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_state_monotonic) * 1000)

def set_enemy_state(enemy: Any, new_state: str):
    if not hasattr(enemy, '_valid_init') or not enemy._valid_init:
        if _state_limiter.can_log(f"set_state_invalid_enemy_{getattr(enemy, 'enemy_id', 'unknown')}"):
            debug(f"EnemyStateHandler: Attempted to set state on invalid enemy {getattr(enemy, 'enemy_id', 'N/A')}. Ignoring.")
        return

    current_state = getattr(enemy, 'state', 'idle')
    enemy_id_str = f"E{getattr(enemy, 'enemy_id', 'N/A')}"
    current_time_ms = get_current_ticks_monotonic()

    # Basic guard: if state is the same, don't do much unless it's a re-triggerable state
    if current_state == new_state and new_state not in ['hit', 'attack', 'attack_nm']: # Add other re-triggerable states
        update_enemy_animation(enemy) # Still update animation
        return

    if _state_limiter.can_log(f"enemy_state_change_{enemy_id_str}_{current_state}_{new_state}"):
        debug(f"EnemyStateHandler ({enemy_id_str}): State changing from '{current_state}' to '{new_state}'")

    enemy.state = new_state
    enemy.current_frame = 0
    enemy.last_anim_update = current_time_ms
    enemy.state_timer = current_time_ms # Timer for how long in current state

    # State-specific initializations
    if new_state == 'idle':
        enemy.is_attacking = False
    elif new_state == 'run':
        enemy.is_attacking = False
    elif new_state == 'attack' or new_state == 'attack_nm':
        enemy.is_attacking = True
        enemy.attack_timer = current_time_ms 
    elif new_state == 'hit':
        enemy.is_taking_hit = True 
        enemy.hit_timer = current_time_ms 
        enemy.is_attacking = False 
    elif new_state == 'death' or new_state == 'death_nm':
        enemy.is_dead = True
        enemy.death_animation_finished = False
        if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0) 
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
    elif new_state == 'aflame':
        enemy.is_aflame = True
        enemy.aflame_timer_start = current_time_ms
        enemy.aflame_damage_last_tick = current_time_ms
    elif new_state == 'deflame':
        enemy.is_deflaming = True
        enemy.deflame_timer_start = current_time_ms
        enemy.is_aflame = False 
    elif new_state == 'frozen':
        enemy.is_frozen = True
        enemy.frozen_effect_timer = current_time_ms
    elif new_state == 'defrost':
        enemy.is_defrosting = True
        enemy.is_frozen = False
    elif new_state == 'petrified':
        enemy.is_petrified = True
    elif new_state == 'smashed':
        enemy.is_stone_smashed = True
    elif new_state == 'stomp_death':
        pass # Most flags set by stomp_kill_enemy in status_effects
    
    update_enemy_animation(enemy)

#################### END OF FILE: enemy_state_handler.py ####################