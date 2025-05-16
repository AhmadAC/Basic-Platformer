########## START OF FILE: player_state_handler.py ##########
# player_state_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.3 (Added petrified and smashed states)
Handles player state transitions and state-specific initializations.
"""
import pygame
import constants as C
from utils import PrintLimiter # Assuming PrintLimiter is accessible

def set_player_state(player, new_state: str):
    """
    Sets the player's logical state, handling transitions and
    state-specific initializations. Calls update_player_animation to refresh visuals.
    Operates on the 'player' instance.
    """
    if not player._valid_init: return

    original_new_state_request = new_state

    # Petrified/Smashed states override other state changes unless it's a death-like state
    if player.is_petrified and new_state not in ['petrified', 'smashed', 'death', 'death_nm']:
        if player.print_limiter.can_print(f"player_set_state_blocked_petrified_{player.player_id}_{new_state}"):
            print(f"Player (P{player.player_id}): Blocked state change to '{new_state}' because player is petrified.")
        return # Don't change state if petrified, unless it's to 'smashed' or an explicit death

    # Ensure the requested state has animations, or fallback
    animation_frames_for_new_state = player.animations.get(new_state)
    if not animation_frames_for_new_state and new_state not in ['petrified', 'smashed']: # 'petrified' and 'smashed' use specific images
        fallback_state_key = 'fall' if not player.on_ground else 'idle'
        if fallback_state_key in player.animations and player.animations[fallback_state_key]:
            new_state = fallback_state_key
            if player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player Warning (P{player.player_id}): State '{original_new_state_request}' anim missing. Fallback to '{new_state}'.")
        else: 
            first_available_anim_key = next((key for key, anim in player.animations.items() if anim), None)
            if not first_available_anim_key:
                if player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                    print(f"CRITICAL Player Error (P{player.player_id}): No animations loaded. Requested: '{original_new_state_request}'. Player invalid.")
                player._valid_init = False; return 
            new_state = first_available_anim_key
            if player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player CRITICAL Warning (P{player.player_id}): State '{original_new_state_request}' and preferred fallbacks missing. Using first available: '{new_state}'.")

    can_change_state_now = (player.state != new_state or new_state in getattr(player, 'allow_state_reset_list', ['death', 'petrified', 'smashed'])) and \
                           not (player.is_dead and player.death_animation_finished and new_state not in ['death', 'petrified', 'smashed'])


    if can_change_state_now:
        if player.state != new_state and player.print_limiter.can_print(f"state_change_{player.player_id}_{player.state}_{new_state}"):
             print(f"DEBUG P_STATE_H (P{player.player_id}): State changing from '{player.state}' to '{new_state}' (request was '{original_new_state_request}')")
        player._last_state_for_debug = new_state 

        if 'attack' not in new_state and player.is_attacking: player.is_attacking = False; player.attack_type = 0
        if new_state != 'hit': player.is_taking_hit = False
        if new_state != 'dash': player.is_dashing = False
        if new_state != 'roll': player.is_rolling = False
        if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: player.is_sliding = False
        
        # If changing from petrified/smashed to something else (e.g. reset), clear flags
        if (player.is_petrified or player.is_stone_smashed) and new_state not in ['petrified', 'smashed']:
            player.is_petrified = False
            player.is_stone_smashed = False
            if player.is_dead: # If it was "stone dead", and now changing state, might not be dead anymore if health allows
                if player.current_health > 0: # Or if a reset is happening
                    player.is_dead = False
                    player.death_animation_finished = False


        player.state = new_state
        player.current_frame = 0 
        player.last_anim_update = pygame.time.get_ticks()
        player.state_timer = pygame.time.get_ticks() 

        if new_state == 'dash':
            player.is_dashing = True
            player.dash_timer = player.state_timer 
            player.vel.x = C.PLAYER_DASH_SPEED * (1 if player.facing_right else -1)
            player.vel.y = 0 
        elif new_state == 'roll':
            player.is_rolling = True
            player.roll_timer = player.state_timer
            if abs(player.vel.x) < C.PLAYER_ROLL_SPEED * 0.7:
                player.vel.x = C.PLAYER_ROLL_SPEED * (1 if player.facing_right else -1)
            else: 
                player.vel.x = player.vel.x * 0.8 + (C.PLAYER_ROLL_SPEED * 0.2 * (1 if player.facing_right else -1))
            player.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x))
        elif new_state == 'slide' or new_state == 'slide_trans_start':
            player.is_sliding = True
            player.slide_timer = player.state_timer
            if abs(player.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: 
                 player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if player.facing_right else -1)
        elif 'attack' in new_state: 
            player.is_attacking = True
            player.attack_timer = player.state_timer
            animation_for_this_attack = player.animations.get(new_state, [])
            num_attack_frames = len(animation_for_this_attack)
            base_ms_per_frame = C.ANIM_FRAME_DURATION
            if player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
                ms_per_frame = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
            else:
                ms_per_frame = base_ms_per_frame
            player.attack_duration = num_attack_frames * ms_per_frame if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)

            if new_state.endswith('_nm') or new_state == 'crouch_attack': 
                player.vel.x = 0 
        elif new_state == 'hit':
            player.is_taking_hit = True
            player.hit_timer = player.state_timer
            if not player.on_ground and player.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): 
                player.vel.x *= -0.3 
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4 
            player.is_attacking = False; player.attack_type = 0 
        elif new_state == 'death' or new_state == 'death_nm':
            player.is_dead = True
            player.vel.x = 0
            if player.vel.y < -1: player.vel.y = 1 
            player.acc.x = 0
            if not player.on_ground: player.acc.y = C.PLAYER_GRAVITY 
            else: player.vel.y = 0; player.acc.y = 0 
            player.death_animation_finished = False
        elif new_state == 'wall_climb':
            player.wall_climb_timer = player.state_timer 
            player.vel.y = C.PLAYER_WALL_CLIMB_SPEED 
            player.vel.x = 0 
        elif new_state == 'wall_slide' or new_state == 'wall_hang':
            player.wall_climb_timer = 0 
        elif new_state == 'petrified':
            player.is_petrified = True; player.is_stone_smashed = False
            player.is_dead = True; player.death_animation_finished = True # Instantly "dead" visually
            player.vel.xy = 0,0; player.acc.xy = 0,0
        elif new_state == 'smashed':
            player.is_stone_smashed = True; player.is_petrified = True
            player.stone_smashed_timer_start = player.state_timer # Record when smashing starts
            player.vel.xy = 0,0; player.acc.xy = 0,0


        from player_animation_handler import update_player_animation 
        update_player_animation(player)

    elif not player.is_dead: 
         player._last_state_for_debug = player.state
########## END OF FILE: player_state_handler.py ##########