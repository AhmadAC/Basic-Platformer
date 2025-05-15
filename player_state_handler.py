# player_state_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.2 (Clarified interaction with animation handler)
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

    # Ensure the requested state has animations, or fallback
    animation_frames_for_new_state = player.animations.get(new_state)
    if not animation_frames_for_new_state:
        fallback_state_key = 'fall' if not player.on_ground else 'idle'
        if fallback_state_key in player.animations and player.animations[fallback_state_key]:
            new_state = fallback_state_key
            if player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player Warning (P{player.player_id}): State '{original_new_state_request}' anim missing. Fallback to '{new_state}'.")
        else: # Critical fallback if even idle/fall are missing
            first_available_anim_key = next((key for key, anim in player.animations.items() if anim), None)
            if not first_available_anim_key:
                if player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                    print(f"CRITICAL Player Error (P{player.player_id}): No animations loaded. Requested: '{original_new_state_request}'. Player invalid.")
                player._valid_init = False; return # Cannot proceed
            new_state = first_available_anim_key
            if player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player CRITICAL Warning (P{player.player_id}): State '{original_new_state_request}' and preferred fallbacks missing. Using first available: '{new_state}'.")

    # Determine if state can actually change
    can_change_state_now = (player.state != new_state or new_state in getattr(player, 'allow_state_reset_list', ['death'])) and \
                           not (player.is_dead and player.death_animation_finished and new_state != 'death')


    if can_change_state_now:
        # Debug info
        if player.state != new_state and player.print_limiter.can_print(f"state_change_{player.player_id}_{player.state}_{new_state}"):
             print(f"DEBUG P_STATE_H (P{player.player_id}): State changing from '{player.state}' to '{new_state}' (request was '{original_new_state_request}')")
        player._last_state_for_debug = new_state # For external debug viewing

        # Reset general boolean flags based on new state
        if 'attack' not in new_state and player.is_attacking: player.is_attacking = False; player.attack_type = 0
        if new_state != 'hit': player.is_taking_hit = False
        if new_state != 'dash': player.is_dashing = False
        if new_state != 'roll': player.is_rolling = False
        if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: player.is_sliding = False
        # Note: player.is_crouching is managed by input_handler based on toggle,
        # this function just sets the visual state (e.g. 'crouch', 'crouch_trans')

        # Set the new state and reset animation/state timers
        player.state = new_state
        player.current_frame = 0 # Always reset frame for new state
        player.last_anim_update = pygame.time.get_ticks()
        player.state_timer = pygame.time.get_ticks() # Timer for how long player is in this state

        # State-specific initializations (velocities, timers, specific flags)
        if new_state == 'dash':
            player.is_dashing = True
            player.dash_timer = player.state_timer # Store start time of dash
            player.vel.x = C.PLAYER_DASH_SPEED * (1 if player.facing_right else -1)
            player.vel.y = 0 # Dash is horizontal
        elif new_state == 'roll':
            player.is_rolling = True
            player.roll_timer = player.state_timer
            # Give a speed boost if rolling from standstill or slow
            if abs(player.vel.x) < C.PLAYER_ROLL_SPEED * 0.7:
                player.vel.x = C.PLAYER_ROLL_SPEED * (1 if player.facing_right else -1)
            else: # Maintain some existing momentum if already fast
                player.vel.x = player.vel.x * 0.8 + (C.PLAYER_ROLL_SPEED * 0.2 * (1 if player.facing_right else -1))
            player.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x))
        elif new_state == 'slide' or new_state == 'slide_trans_start':
            player.is_sliding = True
            player.slide_timer = player.state_timer
            if abs(player.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: # Ensure some speed for slide
                 player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if player.facing_right else -1)
        elif 'attack' in new_state: # Covers 'attack', 'attack_nm', 'crouch_attack', etc.
            player.is_attacking = True
            player.attack_timer = player.state_timer
            # Calculate attack duration based on animation frames
            animation_for_this_attack = player.animations.get(new_state, [])
            num_attack_frames = len(animation_for_this_attack)
            base_ms_per_frame = C.ANIM_FRAME_DURATION
            if player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
                ms_per_frame = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
            else:
                ms_per_frame = base_ms_per_frame
            player.attack_duration = num_attack_frames * ms_per_frame if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)

            if new_state.endswith('_nm') or new_state == 'crouch_attack': # Non-moving attacks
                player.vel.x = 0 # Stop horizontal movement for stationary attacks
        elif new_state == 'hit':
            player.is_taking_hit = True
            player.hit_timer = player.state_timer
            # Simple knockback example
            if not player.on_ground and player.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5): # If in air and not already moving up fast
                player.vel.x *= -0.3 # Reverse and reduce horizontal
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4 # Small pop-up
            player.is_attacking = False; player.attack_type = 0 # Cancel attacks
        elif new_state == 'death' or new_state == 'death_nm':
            player.is_dead = True
            player.vel.x = 0
            if player.vel.y < -1: player.vel.y = 1 # Don't fly up on death
            player.acc.x = 0
            if not player.on_ground: player.acc.y = C.PLAYER_GRAVITY # Fall if in air
            else: player.vel.y = 0; player.acc.y = 0 # Stay on ground
            player.death_animation_finished = False
        elif new_state == 'wall_climb':
            player.wall_climb_timer = player.state_timer # For climb duration limit
            player.vel.y = C.PLAYER_WALL_CLIMB_SPEED # Move up wall
            player.vel.x = 0 # Stop horizontal movement against wall
        elif new_state == 'wall_slide' or new_state == 'wall_hang':
            player.wall_climb_timer = 0 # Reset climb duration timer

        # Update animation immediately to reflect the new state's first frame
        # This call will handle correct rect anchoring.
        from player_animation_handler import update_player_animation # Local import is good practice here
        update_player_animation(player)

    elif not player.is_dead: # If state didn't change, but for debug
         player._last_state_for_debug = player.state