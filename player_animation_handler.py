# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.4 (Corrected rect anchoring using consistent midbottom)
Handles player animation selection and frame updates.
Correctly anchors the player's rect when height changes (e.g., crouching),
ensuring the player's feet (midbottom) remain consistent, and updates player.pos.
"""
import pygame
import constants as C
from utils import PrintLimiter # Assuming PrintLimiter is accessible for debug prints

# This module relies on player.animations, player.state, player.current_frame,
# player.last_anim_update, player.facing_right, player.vel, player.on_ground, etc.

def determine_animation_key(player):
    """
    Helper function to determine the correct animation key based on player state.
    Returns the animation key string.
    """
    animation_key = player.state # Default to current logical state
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    if player.is_dead:
        is_still_nm = abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        if key_variant in player.animations and player.animations[key_variant]:
            animation_key = key_variant
        elif 'death' in player.animations and player.animations['death']:
            animation_key = 'death'
        # If 'death' itself is missing, it will be caught by the final fallback
    elif player.is_attacking:
        base_key = ''
        if player.attack_type == 1: base_key = 'attack'
        elif player.attack_type == 2: base_key = 'attack2'
        elif player.attack_type == 3: base_key = 'attack_combo'
        elif player.attack_type == 4: base_key = 'crouch_attack' # Crouching attack

        if base_key == 'crouch_attack':
            animation_key = base_key # Crouch attack usually has one variant
        elif base_key:
            nm_variant = f"{base_key}_nm" # Non-moving variant
            moving_variant = base_key     # Moving variant

            # Prioritize moving variant if intending to move AND it exists
            if player_is_intending_to_move_lr and player.animations.get(moving_variant):
                animation_key = moving_variant
            # Else, use non-moving variant if it exists
            elif player.animations.get(nm_variant):
                animation_key = nm_variant
            # Fallback to moving variant if _nm is missing but moving exists
            elif player.animations.get(moving_variant):
                animation_key = moving_variant
            # If all specified variants fail, it's caught by the final fallback to 'idle'
    elif player.state == 'wall_climb':
        # Check if actively climbing up vs. just holding onto the wall without upward input
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1 # More precise check for actual climb speed
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if key_variant in player.animations and player.animations[key_variant]:
            animation_key = key_variant
        elif 'wall_climb' in player.animations and player.animations['wall_climb']:
            animation_key = 'wall_climb' # Fallback to the base wall_climb if _nm is missing
    elif player.state == 'hit':
        animation_key = 'hit'
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0):
        animation_key = 'fall'
    elif player.on_ladder:
        animation_key = 'ladder_climb' if abs(player.vel.y) > 0.1 else 'ladder_idle'
    elif player.is_dashing: animation_key = 'dash'
    elif player.is_rolling: animation_key = 'roll'
    elif player.is_sliding: animation_key = 'slide' # Assumes 'slide' is the looping part
    elif player.state == 'slide_trans_start': animation_key = 'slide_trans_start'
    elif player.state == 'slide_trans_end': animation_key = 'slide_trans_end'
    elif player.state == 'crouch_trans': animation_key = 'crouch_trans'
    # elif player.state == 'stand_up_trans': animation_key = 'stand_up_trans' # If you add this
    elif player.state == 'turn': animation_key = 'turn'
    elif player.state == 'jump': animation_key = 'jump'
    elif player.state == 'jump_fall_trans': animation_key = 'jump_fall_trans'
    elif player.state == 'wall_slide': animation_key = 'wall_slide'
    elif player.state == 'wall_hang': animation_key = 'wall_hang'
    elif player.on_ground: # Must be on ground and not in any of the above specific states
        if player.is_crouching:
            key_variant = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
            if key_variant in player.animations and player.animations[key_variant]:
                animation_key = key_variant
            elif 'crouch' in player.animations and player.animations['crouch']:
                animation_key = 'crouch' # Fallback if crouch_walk is missing
        elif player_is_intending_to_move_lr:
            animation_key = 'run'
        else: # Not crouching, not moving horizontally
            animation_key = 'idle'
    else: # Default for in-air if no other specific air state matched (e.g., just after jump peak but before MIN_SIGNIFICANT_FALL_VEL)
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             animation_key = 'fall' if 'fall' in player.animations and player.animations['fall'] else 'idle'


    # Final validation: if the determined key is invalid, fallback to 'idle'
    if animation_key not in player.animations or not player.animations[animation_key]:
        if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
            print(f"ANIM_HANDLER Warning (P{player.player_id}): Animation key '{animation_key}' (derived from state '{player.state}') "
                  f"is invalid or has no frames. Falling back to 'idle'.")
        return 'idle'
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list, current_time_ms, current_animation_key):
    """
    Advances animation frame and handles state transitions for non-looping animations.
    Modifies player.current_frame and can call player.set_state().
    """
    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if not (player.is_dead and player.death_animation_finished): # Don't advance frame if death anim is done
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame += 1

            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead: # Death animation finished
                    player.current_frame = len(current_animation_frames_list) - 1 # Stay on last frame
                    player.death_animation_finished = True
                    return # Stop further processing for this animation update

                # List of animations that should not loop
                non_looping_animation_keys = [
                    'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                    'crouch_attack','dash','roll','slide','hit','turn','jump',
                    'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end'
                    # 'stand_up_trans' # Add if you implement it
                ]

                if current_animation_key in non_looping_animation_keys:
                    next_logical_state = None # Determine what state to go to next
                    player_is_intending_to_move = player.is_trying_to_move_left or player.is_trying_to_move_right

                    if current_animation_key == 'jump':
                        next_logical_state = 'jump_fall_trans' if player.animations.get('jump_fall_trans') else 'fall'
                    elif current_animation_key == 'jump_fall_trans':
                        next_logical_state = 'fall'
                    elif current_animation_key == 'hit':
                        player.is_taking_hit = False # Hit stun period ends
                        next_logical_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                    elif current_animation_key == 'turn':
                        next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif 'attack' in current_animation_key:
                        player.is_attacking = False; player.attack_type = 0
                        if player.on_ladder: next_logical_state = 'ladder_idle' # Or climb if moving on ladder
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif current_animation_key == 'crouch_trans':
                        # Assumes player.is_crouching is still true
                        next_logical_state = 'crouch_walk' if player_is_intending_to_move else 'crouch'
                    # elif current_animation_key == 'stand_up_trans':
                        # player.is_crouching = False
                        # next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif current_animation_key == 'slide_trans_start':
                        next_logical_state = 'slide' # Transition to the looping slide animation
                    elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                        player.is_sliding = False
                        # After slide, if still holding crouch, go to crouch, else idle/run
                        next_logical_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                    else: # For 'dash', 'roll' (which finish their own flags internally)
                        if current_animation_key == 'dash': player.is_dashing = False
                        if current_animation_key == 'roll': player.is_rolling = False
                        if player.on_ladder: next_logical_state = 'ladder_idle'
                        elif player.is_crouching: next_logical_state = 'crouch' # Should not happen if dash/roll from crouch isn't allowed
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'

                    if next_logical_state:
                        # Only change state if the current logical state hasn't already been
                        # changed by another system (e.g., input immediately setting a new attack).
                        # This is a safety check. player.set_state handles its own internal logic.
                        if player.state == current_animation_key or current_animation_key == 'slide': # 'slide' can auto-transition to 'slide_trans_end' or others
                            player.set_state(next_logical_state)
                            return # set_state will call update_player_animation again, so exit this instance.
                        else: # State was already changed by other logic, reset frame for current (new) state
                            player.current_frame = 0
                    else: # Animation is non-looping but no specific next state defined, loop it (or go to idle if more robust)
                        player.current_frame = 0 # Default to looping the non-looping (e.g. if 'fall' was non-looping by mistake)
                else: # Looping animation (like idle, run, crouch, fall)
                    player.current_frame = 0

    # Ensure current_frame is valid for the current_animation_frames_list
    # This might be needed if a state transition occurred and the new animation is shorter.
    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    """
    Updates the player's current image based on its state, frame, and facing direction.
    Correctly anchors the player's rect when height changes by maintaining the midbottom point.
    """
    if not player._valid_init or not hasattr(player, 'animations') or not player.animations:
        if hasattr(player, 'image') and player.image: player.image.fill(C.MAGENTA) # Visual error
        return

    # Allow death animation to play even if player.alive() is False (sprite not yet killed)
    if not player.alive() and not (player.is_dead and not player.death_animation_finished):
        return

    current_time_ms = pygame.time.get_ticks()
    animation_key = determine_animation_key(player) # Get the animation key for the current state
    current_animation_frames = player.animations.get(animation_key)

    if not current_animation_frames: # Should be caught by determine_animation_key's fallback
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{animation_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{animation_key}' (State: {player.state}) are missing AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        return

    # Advance frame and handle non-looping animation state transitions
    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, animation_key)

    # Re-evaluate animation_key and current_animation_frames if state was changed by advance_frame...
    # This ensures we use the frames for the *new* state if a transition just occurred.
    if player.state != animation_key: # Check if logical state diverged from playing animation key
        new_animation_key_after_transition = determine_animation_key(player)
        new_current_animation_frames = player.animations.get(new_animation_key_after_transition)
        if new_current_animation_frames:
            animation_key = new_animation_key_after_transition # Update to the actual current animation
            current_animation_frames = new_current_animation_frames
            # player.current_frame should have been reset to 0 by set_player_state when it was called
        # else: # This case should be rare if determine_animation_key and set_state have fallbacks
            # Fallback already handled in determine_animation_key

    # Ensure current_frame is valid for the (potentially new) current_animation_frames
    # This is a safeguard, especially after state transitions.
    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0

    # Get the image for the current frame of the (potentially new) animation
    image_for_this_frame = current_animation_frames[player.current_frame]

    # Flip if necessary based on player's facing direction
    if not player.facing_right:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # Update image and rect only if necessary, and correctly anchor the rect
    if player.image is not image_for_this_frame or player._last_facing_right != player.facing_right:
        old_rect_midbottom = player.rect.midbottom # Store old anchor point (feet position and horizontal center)
        old_rect_height_for_debug = player.rect.height # For debug print

        player.image = image_for_this_frame       # Set the new image
        player.rect = player.image.get_rect()     # Get new rect based on new image (initially at 0,0)
        player.rect.midbottom = old_rect_midbottom # Re-anchor the new rect to the old midbottom point

        # Sync player.pos (the source of truth for physics) to the newly anchored rect's midbottom.
        # This ensures player.pos always reflects the current visual and collision rect's base.
        player.pos = pygame.math.Vector2(player.rect.midbottom)

        new_rect_height_for_debug = player.rect.height
        if old_rect_height_for_debug != new_rect_height_for_debug:
            if player.print_limiter.can_print(f"anim_height_change_{player.player_id}_{animation_key}"):
                print(f"DEBUG ANIM_H (P{player.player_id}): Height Change. Key:'{animation_key}'. "
                      f"OldH:{old_rect_height_for_debug}, NewH:{new_rect_height_for_debug}. "
                      f"Rect anchored to old_midbottom: {old_rect_midbottom}. New player.pos: {player.pos}")

        player._last_facing_right = player.facing_right # Update last facing direction