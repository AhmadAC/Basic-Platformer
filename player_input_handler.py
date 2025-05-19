#################### START OF FILE: player_state_handler.py ####################

# player_state_handler.py
# -*- coding: utf-8 -*-
"""
Handles player state transitions and state-specific initializations for PySide6.
"""
# version 2.0.2 (PySide6 Refactor - Corrected timer usage)

from typing import Optional

# PySide6 imports
from PySide6.QtCore import QPointF

# Game imports
import constants as C
from utils import PrintLimiter

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_player_state = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_player_state) * 1000)

try:
    from player_animation_handler import update_player_animation
except ImportError:
    def update_player_animation(player):
        if hasattr(player, 'animate'):
            player.animate()
        else:
            print(f"CRITICAL PLAYER_STATE_HANDLER: player_animation_handler.update_player_animation not found for Player ID {getattr(player, 'player_id', 'N/A')}")


def set_player_state(player, new_state: str):
    if not player._valid_init:
        if player.print_limiter.can_print(f"set_state_invalid_player_{player.player_id}"):
            print(f"PlayerStateHandler: Attempted to set state on invalid player {player.player_id}. Ignoring.")
        return

    original_new_state_request = new_state
    player_id_str = f"P{player.player_id}"
    current_ticks = get_current_ticks() # Use the defined function

    if player.is_petrified and not player.is_stone_smashed and \
       new_state not in ['petrified', 'smashed', 'death', 'death_nm', 'idle']:
        if player.print_limiter.can_print(f"set_state_block_petrified_{player.player_id}_{new_state}"):
            print(f"PlayerStateHandler (P{player_id_str}): Blocked state change from '{player.state}' to '{new_state}' due to being petrified (not smashed).")
        return
    if player.is_stone_smashed and new_state not in ['smashed', 'death', 'death_nm', 'idle']:
        if player.print_limiter.can_print(f"set_state_block_smashed_{player.player_id}_{new_state}"):
            print(f"PlayerStateHandler (P{player_id_str}): Blocked state change from '{player.state}' to '{new_state}' due to being stone_smashed.")
        return

    if player.is_aflame:
        if new_state not in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch',
                             'deflame', 'deflame_crouch',
                             'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'burning_crouch' if player.is_crouching else 'burning'
    elif player.is_deflaming:
        if new_state not in ['deflame', 'deflame_crouch', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'deflame_crouch' if player.is_crouching else 'deflame'
    elif player.is_frozen:
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'frozen'
    elif player.is_defrosting:
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'defrost'

    animation_key_to_check = new_state
    if new_state in ['chasing', 'patrolling']: animation_key_to_check = 'run'
    elif 'attack' in new_state: animation_key_to_check = new_state
    
    if animation_key_to_check not in ['petrified', 'smashed']:
        if not player.animations or animation_key_to_check not in player.animations or not player.animations[animation_key_to_check]:
            fallback_state_key = 'fall' if not player.on_ground else 'idle'
            if player.animations and fallback_state_key in player.animations and player.animations[fallback_state_key]:
                if player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}_{new_state}"):
                    print(f"Player Warning (P{player_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
                new_state = fallback_state_key
            else:
                first_available_anim_key = next((key for key, anim in player.animations.items() if anim), None) if player.animations else None
                if not first_available_anim_key:
                    if player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                        print(f"CRITICAL Player Error (P{player_id_str}): No animations loaded. Requested: '{original_new_state_request}'. Player invalid.")
                    player._valid_init = False; return
                new_state = first_available_anim_key
                if player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                    print(f"Player CRITICAL Warning (P{player_id_str}): State '{original_new_state_request}' and preferred fallbacks missing. Using first available: '{new_state}'.")

    can_change_state_now = (player.state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and player.state not in ['aflame', 'aflame_crouch', 'burning', 'burning_crouch'])

    if player.is_dead and player.death_animation_finished and not player.is_stone_smashed:
        if new_state not in ['death', 'death_nm', 'petrified', 'smashed', 'idle']:
            can_change_state_now = False

    if not can_change_state_now:
        if player.state == new_state and player.print_limiter.can_print(f"set_state_no_change_{player_id_str}_{new_state}"):
             print(f"PlayerStateHandler (P{player_id_str}): State change to '{new_state}' not allowed or no actual change needed.")
        if player.state == new_state: update_player_animation(player)
        return

    state_is_actually_changing = (player.state != new_state)
    if state_is_actually_changing:
        if player.print_limiter.can_print(f"state_change_{player.player_id}_{player.state}_{new_state}"):
             print(f"DEBUG P_STATE_H (P{player_id_str}): State changing from '{player.state}' to '{new_state}' (request was '{original_new_state_request}')")
    player._last_state_for_debug = new_state

    if 'attack' not in new_state and player.is_attacking: player.is_attacking = False; player.attack_type = 0
    if new_state != 'hit' and player.is_taking_hit:
        if current_ticks - player.hit_timer >= player.hit_cooldown: # Use current_ticks
            player.is_taking_hit = False
    if new_state != 'dash': player.is_dashing = False
    if new_state != 'roll': player.is_rolling = False
    if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: player.is_sliding = False

    if new_state == 'aflame' or new_state == 'burning' or new_state == 'aflame_crouch' or new_state == 'burning_crouch':
        if not player.is_aflame: player.aflame_timer_start = current_ticks; player.aflame_damage_last_tick = player.aflame_timer_start
        player.is_aflame = True; player.is_deflaming = False
    elif new_state == 'deflame' or new_state == 'deflame_crouch':
        if not player.is_deflaming: player.deflame_timer_start = current_ticks
        player.is_deflaming = True; player.is_aflame = False
    else: 
        player.is_aflame = False; player.is_deflaming = False
        
    if new_state == 'frozen':
        if not player.is_frozen: player.frozen_effect_timer = current_ticks
        player.is_frozen = True; player.is_defrosting = False
    elif new_state == 'defrost':
        player.is_defrosting = True; player.is_frozen = False
    else: 
        player.is_frozen = False; player.is_defrosting = False
        
    if new_state == 'petrified':
        if not player.is_petrified: player.facing_at_petrification = player.facing_right; player.was_crouching_when_petrified = player.is_crouching
        player.is_petrified = True; player.is_stone_smashed = False
        player.is_dead = True; player.death_animation_finished = True
        player.is_aflame = False; player.is_deflaming = False; player.is_frozen = False; player.is_defrosting = False
    elif new_state == 'smashed':
        if not player.is_stone_smashed: player.stone_smashed_timer_start = current_ticks
        player.is_stone_smashed = True; player.is_petrified = True
        player.is_dead = True; player.death_animation_finished = False
    elif player.is_petrified and new_state not in ['petrified', 'smashed']: 
        player.is_petrified = False; player.is_stone_smashed = False; player.was_crouching_when_petrified = False
        if player.is_dead and player.current_health > 0: player.is_dead = False; player.death_animation_finished = False

    player.state = new_state
    if state_is_actually_changing or new_state in ['hit', 'attack', 'attack_nm', 'aflame', 'aflame_crouch']:
        player.current_frame = 0
        player.last_anim_update = current_ticks
    player.state_timer = current_ticks

    if new_state == 'dash':
        player.is_dashing = True; player.dash_timer = player.state_timer
        player.vel.setX(C.PLAYER_DASH_SPEED * (1 if player.facing_right else -1))
        player.vel.setY(0.0)
    elif new_state == 'roll':
        player.is_rolling = True; player.roll_timer = player.state_timer
        if abs(player.vel.x()) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.setX(C.PLAYER_ROLL_SPEED * (1 if player.facing_right else -1))
        else: player.vel.setX(player.vel.x() * 0.8 + (C.PLAYER_ROLL_SPEED * 0.2 * (1 if player.facing_right else -1)))
        player.vel.setX(max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x())))
    elif new_state == 'slide' or new_state == 'slide_trans_start':
        player.is_sliding = True; player.slide_timer = player.state_timer
        if abs(player.vel.x()) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if player.facing_right else -1))
    elif 'attack' in new_state:
        player.is_attacking = True; player.attack_timer = player.state_timer
        animation_for_this_attack = player.animations.get(new_state, []) if player.animations else []
        num_attack_frames = len(animation_for_this_attack)
        base_ms_per_frame = C.ANIM_FRAME_DURATION
        ms_per_frame_for_attack = base_ms_per_frame
        if player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
            ms_per_frame_for_attack = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
        player.attack_duration = num_attack_frames * ms_per_frame_for_attack if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
        if new_state.endswith('_nm') or new_state == 'crouch_attack': player.vel.setX(0.0)
    elif new_state == 'hit':
        player.is_taking_hit = True; player.hit_timer = player.state_timer 
        if not player.on_ground and player.vel.y() > -abs(C.PLAYER_JUMP_STRENGTH * 0.5):
            player.vel.setX(player.vel.x() * -0.3)
            player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.4)
        player.is_attacking = False; player.attack_type = 0
    elif new_state == 'death' or new_state == 'death_nm':
        player.is_dead = True; player.vel.setX(0.0)
        if player.vel.y() < -1: player.vel.setY(1.0) 
        player.acc.setX(0.0)
        if not player.on_ground: player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        else: player.vel.setY(0.0); player.acc.setY(0.0)
        player.death_animation_finished = False
    elif new_state == 'wall_climb':
        player.wall_climb_timer = player.state_timer
        player.vel.setY(C.PLAYER_WALL_CLIMB_SPEED); player.vel.setX(0.0)
    elif new_state == 'wall_slide' or new_state == 'wall_hang': player.wall_climb_timer = 0
    elif new_state in ['frozen', 'defrost', 'petrified', 'smashed']:
        player.vel = QPointF(0,0); player.acc = QPointF(0,0)
        if new_state == 'petrified' and not player.on_ground:
            player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
    elif new_state == 'idle':
        pass

    update_player_animation(player)

#################### END OF FILE: player_state_handler.py ####################