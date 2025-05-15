# player_state_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.1
Handles player state transitions and state-specific initializations.
"""
import pygame
import constants as C
from utils import PrintLimiter # Assuming PrintLimiter is accessible

# This will be used by the Player class instance for its PrintLimiter
# Player.print_limiter should be passed or accessed if needed here,
# or we make a new one specific to this module if independent logging is desired.
# For simplicity, we'll assume Player.print_limiter is accessible via the 'player' instance.

def set_player_state(player, new_state: str):
    """
    Sets the player's logical and animation state, handling transitions and
    state-specific initializations. Operates on the 'player' instance.
    """
    if not player._valid_init: return
    
    original_new_state_request = new_state

    animation_frames_for_new_state = player.animations.get(new_state)
    if not animation_frames_for_new_state:
        fallback_state_key = 'fall' if not player.on_ground else 'idle'
        if fallback_state_key in player.animations and player.animations[fallback_state_key]:
            new_state = fallback_state_key
            if player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player Warning ({player.player_id}): State '{original_new_state_request}' anim missing. Fallback to '{new_state}'.")
        else:
            first_available_anim_key = next((key for key, anim in player.animations.items() if anim), None)
            if not first_available_anim_key:
                if player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                    print(f"CRITICAL Player Error ({player.player_id}): No animations available in set_state. Requested: '{original_new_state_request}'. Player invalid.")
                player._valid_init = False; return
            new_state = first_available_anim_key
            if player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}"):
                print(f"Player CRITICAL Warning ({player.player_id}): State '{original_new_state_request}' and fallbacks missing. Using first available: '{new_state}'.")
    
    can_change_state_now = (player.state != new_state or new_state == 'death') and \
                           not (player.is_dead and player.death_animation_finished and new_state != 'death')

    if can_change_state_now:
        player._last_state_for_debug = new_state
        
        if 'attack' not in new_state and player.is_attacking: player.is_attacking = False; player.attack_type = 0
        if new_state != 'hit': player.is_taking_hit = False
        if new_state != 'dash': player.is_dashing = False
        if new_state != 'roll': player.is_rolling = False
        if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: player.is_sliding = False

        player.state = new_state
        player.current_frame = 0
        player.last_anim_update = pygame.time.get_ticks()
        player.state_timer = pygame.time.get_ticks()

        if new_state == 'dash':
            player.is_dashing = True; player.dash_timer = player.state_timer
            player.vel.x = C.PLAYER_DASH_SPEED * (1 if player.facing_right else -1)
            player.vel.y = 0
        elif new_state == 'roll':
             player.is_rolling = True; player.roll_timer = player.state_timer
             if abs(player.vel.x) < C.PLAYER_ROLL_SPEED / 2: player.vel.x = C.PLAYER_ROLL_SPEED * (1 if player.facing_right else -1)
             elif abs(player.vel.x) < C.PLAYER_ROLL_SPEED: player.vel.x += (C.PLAYER_ROLL_SPEED / 3) * (1 if player.facing_right else -1)
             player.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x))
        elif new_state == 'slide' or new_state == 'slide_trans_start':
             player.is_sliding = True; player.slide_timer = player.state_timer
             if abs(player.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5:
                 player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if player.facing_right else -1)
        elif 'attack' in new_state:
            player.is_attacking = True; player.attack_timer = player.state_timer
            animation_for_this_attack = player.animations.get(new_state)
            num_attack_frames = len(animation_for_this_attack) if animation_for_this_attack else 0
            base_ms_per_frame = C.ANIM_FRAME_DURATION
            if player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
                player.attack_duration = num_attack_frames * int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER) if num_attack_frames > 0 else 300
            else:
                player.attack_duration = num_attack_frames * base_ms_per_frame if num_attack_frames > 0 else 300
            if new_state.endswith('_nm') or new_state == 'crouch_attack':
                player.vel.x = 0
        elif new_state == 'hit':
             player.is_taking_hit = True; player.hit_timer = player.state_timer
             if not player.on_ground and player.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5):
                player.vel.x *= -0.3
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4
             player.is_attacking = False; player.attack_type = 0
        elif new_state == 'death' or new_state == 'death_nm':
             player.is_dead = True; player.vel.x = 0
             if player.vel.y < -1: player.vel.y = 1
             player.acc.x = 0
             if not player.on_ground: player.acc.y = C.PLAYER_GRAVITY
             else: player.vel.y = 0; player.acc.y = 0
             player.death_animation_finished = False
        elif new_state == 'wall_climb':
             player.wall_climb_timer = player.state_timer
             player.vel.y = C.PLAYER_WALL_CLIMB_SPEED
        elif new_state == 'wall_slide' or new_state == 'wall_hang':
             player.wall_climb_timer = 0

        from player_animation_handler import update_player_animation # Local import to avoid circular dependency at module level
        update_player_animation(player)
    
    elif not player.is_dead:
         player._last_state_for_debug = player.state