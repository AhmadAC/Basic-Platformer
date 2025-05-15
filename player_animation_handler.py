# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.3 (Implemented correct rect anchoring for height changes)
Handles player animation selection and frame updates.
Correctly anchors the player's rect when height changes (e.g., crouching).
"""
import pygame
import constants as C

def determine_animation_key(player):
    """Helper function to determine the correct animation key based on player state."""
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
        elif player.attack_type == 4: base_key = 'crouch_attack'

        if base_key == 'crouch_attack': # Crouch attack typically has only one variant
            animation_key = base_key
        elif base_key: # For standing/moving attacks, check for _nm (non-moving) variant
            nm_variant = f"{base_key}_nm"
            moving_variant = base_key
            # Prioritize moving variant if intending to move and it exists
            if player_is_intending_to_move_lr and moving_variant in player.animations and player.animations[moving_variant]:
                animation_key = moving_variant
            # Else, use non-moving variant if it exists
            elif nm_variant in player.animations and player.animations[nm_variant]:
                animation_key = nm_variant
            # Fallback to moving variant if _nm is missing but moving exists
            elif moving_variant in player.animations and player.animations[moving_variant]:
                animation_key = moving_variant
            # If all fail, it's caught by the final fallback
    elif player.state == 'wall_climb':
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.01 # More precise check
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if key_variant in player.animations and player.animations[key_variant]:
            animation_key = key_variant
        elif 'wall_climb' in player.animations and player.animations['wall_climb']: # Fallback
            animation_key = 'wall_climb'
    elif player.state == 'hit':
        animation_key = 'hit'
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y > getattr(C, 'MIN_Y_VEL_FOR_FALL_ANIM', 1.0):
        animation_key = 'fall'
    elif player.on_ladder:
        animation_key = 'ladder_climb' if abs(player.vel.y) > 0.1 else 'ladder_idle'
    elif player.is_dashing: animation_key = 'dash'
    elif player.is_rolling: animation_key = 'roll'
    elif player.is_sliding: animation_key = 'slide' # Assumes 'slide' is the looping part
    elif player.state == 'slide_trans_start': animation_key = 'slide_trans_start'
    elif player.state == 'slide_trans_end': animation_key = 'slide_trans_end'
    elif player.state == 'crouch_trans': animation_key = 'crouch_trans'
    # Add stand_up_trans if you have it for visual transition from crouch to idle/run
    # elif player.state == 'stand_up_trans': animation_key = 'stand_up_trans'
    elif player.state == 'turn': animation_key = 'turn'
    elif player.state == 'jump': animation_key = 'jump'
    elif player.state == 'jump_fall_trans': animation_key = 'jump_fall_trans'
    elif player.state == 'wall_slide': animation_key = 'wall_slide'
    elif player.state == 'wall_hang': animation_key = 'wall_hang'
    elif player.on_ground:
        if player.is_crouching: # Current state could be 'crouch' or 'crouch_walk'
            key_variant = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
            if key_variant in player.animations and player.animations[key_variant]:
                animation_key = key_variant
            elif 'crouch' in player.animations and player.animations['crouch']: # Fallback if specific (e.g. crouch_walk) missing
                animation_key = 'crouch'
        elif player_is_intending_to_move_lr:
            animation_key = 'run'
        else:
            animation_key = 'idle'
    else: # Default if in air and no other more specific air state matched
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             # If current state isn't an expected air state, might default to idle (looks weird) or fall
             animation_key = 'fall' if 'fall' in player.animations else 'idle'


    # Final validation of the determined key and its animation frames
    if animation_key not in player.animations or not player.animations[animation_key]:
        if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
            print(f"ANIM_HANDLER Warning (P{player.player_id}): Anim key '{animation_key}' (derived from state '{player.state}') invalid. Fallback to 'idle'.")
        return 'idle' # Return the key to be used
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list, current_time_ms, current_animation_key):
    """Advances animation frame and handles state transitions for non-looping animations."""
    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if not (player.is_dead and player.death_animation_finished):
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame += 1

            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead: # Death animation finished
                    player.current_frame = len(current_animation_frames_list) - 1
                    player.death_animation_finished = True
                    # The image for the final death frame will be set outside this advancement logic
                    return # Stop further processing for dead, finished animation

                # Check if current animation key (derived from player.state) is non-looping
                non_looping_animation_keys = [
                    'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                    'crouch_attack','dash','roll','slide','hit','turn','jump',
                    'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end'
                    # Add 'stand_up_trans' if you implement it
                ]
                # Use current_animation_key which is the one actually playing
                if current_animation_key in non_looping_animation_keys:
                    next_logical_state = None
                    player_is_intending_to_move = player.is_trying_to_move_left or player.is_trying_to_move_right

                    # Determine next state based on the animation that just finished
                    if current_animation_key == 'jump':
                        next_logical_state = 'jump_fall_trans' if 'jump_fall_trans' in player.animations and player.animations['jump_fall_trans'] else 'fall'
                    elif current_animation_key == 'jump_fall_trans':
                        next_logical_state = 'fall'
                    elif current_animation_key == 'hit':
                        player.is_taking_hit = False # Hit stun ends
                        next_logical_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                    elif current_animation_key == 'turn':
                        next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif 'attack' in current_animation_key: # Covers all attack types
                        player.is_attacking = False; player.attack_type = 0
                        if player.on_ladder: pass # Stay on ladder, will revert to ladder_idle/climb
                        elif player.is_crouching: next_logical_state = 'crouch' # Stay crouched
                        elif not player.on_ground: next_logical_state = 'fall'
                        elif player_is_intending_to_move: next_logical_state = 'run'
                        else: next_logical_state = 'idle'
                    elif current_animation_key == 'crouch_trans':
                        # Finished transitioning into crouch. player.is_crouching should be True.
                        # The actual state will be 'crouch' or 'crouch_walk' handled by input_handler/core_logic.
                        # So, if still is_crouching, go to 'crouch', otherwise 'idle' (if uncrouch key pressed during trans).
                        next_logical_state = 'crouch' if player.is_crouching else 'idle'
                    # elif current_animation_key == 'stand_up_trans': # If you add this
                        # player.is_crouching = False # Ensure flag is false
                        # next_logical_state = 'idle' # Or run if moving
                    elif current_animation_key == 'slide_trans_start':
                        next_logical_state = 'slide' # Transition to looping slide
                    elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                        player.is_sliding = False
                        # After slide, player might be crouching or standing depending on input
                        next_logical_state = 'crouch' if player.is_crouching else 'idle'
                    else: # For 'dash', 'roll'
                        if current_animation_key == 'dash': player.is_dashing = False
                        if current_animation_key == 'roll': player.is_rolling = False

                        if player.on_ladder: pass
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        elif player_is_intending_to_move: next_logical_state = 'run'
                        else: next_logical_state = 'idle'

                    if next_logical_state:
                        # Import locally to break potential circular import issues at module load time,
                        # and to avoid calling set_state if this function itself was called from set_state
                        # without an intervening game loop tick.
                        # This can be tricky. Ideally, player.update() manages these transitions.
                        from player_state_handler import set_player_state
                        # Check if the current logical state (player.state) has already changed
                        # (e.g. by input during this animation). If so, don't override with this purely anim-driven one.
                        # This logic might need to be in Player.update() for better control flow.
                        # For now, we assume if a non-looping anim finishes, it dictates the next state.
                        if player.state == current_animation_key: # Only set if state hasn't already been changed by something else
                            set_player_state(player, next_logical_state)
                            # Since set_player_state calls update_player_animation again,
                            # we must return here to prevent current instance from continuing.
                            return
                        else: # State was already changed by other logic, reset frame for current (new) state
                            player.current_frame = 0
                    else: # Animation is non-looping but no specific next state, so loop it (or go to idle)
                        player.current_frame = 0
                else: # Looping animation
                    player.current_frame = 0

    # Ensure current_frame is valid after advancement logic.
    # This can happen if a state change occurred and the new animation has fewer frames.
    if player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    """
    Updates the player's current image based on its state, frame, and facing direction.
    Correctly anchors the player's rect when height changes.
    """
    if not player._valid_init or not hasattr(player, 'animations') or not player.animations:
        return
    # Allow death animation to play even if player.alive() is False
    if not player.alive() and not (player.is_dead and not player.death_animation_finished):
        return

    current_time_ms = pygame.time.get_ticks()
    # 1. Determine the correct animation key to use based on current player state
    animation_key = determine_animation_key(player)
    current_animation_frames = player.animations.get(animation_key)

    if not current_animation_frames:
        if player.print_limiter.can_print(f"anim_frames_missing_final_{player.player_id}_{animation_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for FINAL key '{animation_key}' (State: {player.state}) are missing! Using fallback RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        return

    # 2. Advance the animation frame and handle transitions for non-looping animations
    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, animation_key)

    # Re-fetch animation_key and frames if state changed during advance_frame_and_handle_state_transitions
    # This happens if a non-looping animation finished and set_player_state was called.
    if player.state != animation_key: # Check if logical state diverged from playing animation key
        new_animation_key_after_transition = determine_animation_key(player)
        new_current_animation_frames = player.animations.get(new_animation_key_after_transition)
        if new_current_animation_frames:
            animation_key = new_animation_key_after_transition
            current_animation_frames = new_current_animation_frames
            # player.current_frame should have been reset to 0 by set_player_state
        else: # Should not happen if set_player_state has fallbacks
            if player.print_limiter.can_print(f"anim_frames_missing_post_trans_{player.player_id}_{new_animation_key_after_transition}"):
                print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{new_animation_key_after_transition}' (post-transition) missing!")
            if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
            return

    # Ensure current_frame is valid for the (potentially new) current_animation_frames
    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0 # Safeguard


    # 3. Get the image for the current frame
    image_for_this_frame = current_animation_frames[player.current_frame]

    # 4. Flip if necessary
    if not player.facing_right:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # --- CRITICAL SECTION: Update image and rect, with correct anchoring ---
    # Only proceed if the visual representation needs to change
    if player.image is not image_for_this_frame or player._last_facing_right != player.facing_right:
        old_rect_height = player.rect.height
        old_rect_midbottom = player.rect.midbottom # Player class uses midbottom for pos

        player.image = image_for_this_frame
        # Get new rect based on the new image, initially at (0,0) or image's internal rect pos
        player.rect = player.image.get_rect()

        new_rect_height = player.rect.height
        height_changed = (old_rect_height != new_rect_height)

        # Anchor the new rect
        if player.on_ground and height_changed:
            # If on ground and height changes (crouch/stand), keep FEET (bottom) planted.
            # Horizontal position is maintained via midbottom's X.
            player.rect.bottom = old_rect_midbottom[1] # Keep original Y of feet
            player.rect.centerx = old_rect_midbottom[0] # Keep original X of midbottom
            if player.print_limiter.can_print(f"anim_anchor_ground_{player.player_id}_{animation_key}"):
                print(f"DEBUG ANIM (P{player.player_id}): Ground anchor. Key:{animation_key}. OldH:{old_rect_height}, NewH:{new_rect_height}. OldB:{old_rect_midbottom[1]}, NewB:{player.rect.bottom}")

        else:
            # If in air, or on ground but no height change (e.g., idle to run, or just flipping)
            # maintain midbottom position.
            player.rect.midbottom = old_rect_midbottom
            if height_changed and player.print_limiter.can_print(f"anim_anchor_air_{player.player_id}_{animation_key}"):
                 print(f"DEBUG ANIM (P{player.player_id}): Air/NoHeightChange anchor. Key:{animation_key}. OldH:{old_rect_height}, NewH:{new_rect_height}")


        # Sync player.pos to the newly anchored player.rect.midbottom
        # This is crucial because player.pos is the source of truth for physics before collisions.
        player.pos = pygame.math.Vector2(player.rect.midbottom)

        player._last_facing_right = player.facing_right