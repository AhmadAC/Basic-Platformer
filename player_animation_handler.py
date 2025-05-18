
# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.9 (Handle crouched petrification visuals)
Handles player animation selection and frame updates.
Correctly anchors the player's rect when height changes (e.g., crouching),
ensuring the player's feet (midbottom) remain consistent, and updates player.pos.
"""
import pygame
import constants as C
from utils import PrintLimiter

def determine_animation_key(player):
    """
    Helper function to determine the correct animation key based on player state.
    Returns the animation key string.
    """
    animation_key = player.state
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    # --- Highest Priority: Visual Overrides for Special States ---
    if player.is_petrified: # This flag covers both 'petrified' and 'smashed' logical states
        return 'smashed' if player.is_stone_smashed else 'petrified' # Visual distinction handled in update_player_animation

    if player.is_dead:
        is_still_nm = abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        if key_variant in player.animations and player.animations[key_variant]: return key_variant
        elif 'death' in player.animations and player.animations['death']: return 'death'
        else: return 'idle'

    # --- Next Priority: Persistent Status Effect Visuals (including new fire states) ---
    if player.is_aflame:
        if player.state == 'aflame_crouch' and 'aflame_crouch' in player.animations and player.animations['aflame_crouch']:
            return 'aflame_crouch'
        elif player.is_crouching and 'burning_crouch' in player.animations and player.animations['burning_crouch']:
            return 'burning_crouch'
        elif not player.is_crouching and 'burning' in player.animations and player.animations['burning']:
            return 'burning'
        elif 'aflame' in player.animations and player.animations['aflame']:
             return 'aflame'
    if player.is_deflaming:
        if player.is_crouching and 'deflame_crouch' in player.animations and player.animations['deflame_crouch']:
            return 'deflame_crouch'
        elif not player.is_crouching and 'deflame' in player.animations and player.animations['deflame']:
            return 'deflame'

    if player.is_frozen and 'frozen' in player.animations and player.animations['frozen']:
        return 'frozen'
    if player.is_defrosting and 'defrost' in player.animations and player.animations['defrost']:
        return 'defrost'

    # --- Then, standard actions/movement states ---
    # ... (rest of the existing logic for attacks, wall climb, hit, fall, ladder, dash, roll, slide etc.) ...
    if player.is_attacking:
        base_key = ''
        if player.attack_type == 1: base_key = 'attack'
        elif player.attack_type == 2: base_key = 'attack2'
        elif player.attack_type == 3: base_key = 'attack_combo'
        elif player.attack_type == 4: base_key = 'crouch_attack'
        if base_key == 'crouch_attack': animation_key = base_key
        elif base_key:
            nm_variant = f"{base_key}_nm"; moving_variant = base_key
            if player_is_intending_to_move_lr and player.animations.get(moving_variant): animation_key = moving_variant
            elif player.animations.get(nm_variant): animation_key = nm_variant
            elif player.animations.get(moving_variant): animation_key = moving_variant
    elif player.state == 'wall_climb':
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if key_variant in player.animations and player.animations[key_variant]: animation_key = key_variant
        elif 'wall_climb' in player.animations and player.animations['wall_climb']: animation_key = 'wall_climb'
    elif player.state == 'hit': animation_key = 'hit'
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0):
        animation_key = 'fall'
    elif player.on_ladder:
        animation_key = 'ladder_climb' if abs(player.vel.y) > 0.1 else 'ladder_idle'
    elif player.is_dashing: animation_key = 'dash'
    elif player.is_rolling: animation_key = 'roll'
    elif player.is_sliding: animation_key = 'slide'
    elif player.state == 'slide_trans_start': animation_key = 'slide_trans_start'
    elif player.state == 'slide_trans_end': animation_key = 'slide_trans_end'
    elif player.state == 'crouch_trans': animation_key = 'crouch_trans'
    elif player.state == 'turn': animation_key = 'turn'
    elif player.state == 'jump': animation_key = 'jump'
    elif player.state == 'jump_fall_trans': animation_key = 'jump_fall_trans'
    elif player.state == 'wall_slide': animation_key = 'wall_slide'
    elif player.state == 'wall_hang': animation_key = 'wall_hang'
    elif player.on_ground:
        if player.is_crouching:
            key_variant = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
            if key_variant in player.animations and player.animations[key_variant]: animation_key = key_variant
            elif 'crouch' in player.animations and player.animations['crouch']: animation_key = 'crouch'
        elif player_is_intending_to_move_lr: animation_key = 'run'
        else: animation_key = 'idle'
    else:
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             animation_key = 'fall' if 'fall' in player.animations and player.animations['fall'] else 'idle'


    # MODIFIED: Removed check for 'petrified', 'smashed' here as they are handled by top-level check.
    # The new fire states are normal animation keys that should exist in player.animations.
    if animation_key not in ['burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch', 'frozen', 'defrost']:
        if animation_key not in player.animations or not player.animations[animation_key]:
            if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
                print(f"ANIM_HANDLER Warning (P{player.player_id}): Animation key '{animation_key}' (derived from state '{player.state}') "
                      f"is invalid or has no frames. Falling back to 'idle'.")
            return 'idle'
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list, current_time_ms, current_animation_key):
    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    # MODIFIED: For petrified states, animation is static (single frame)
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0 # Stone image is always frame 0
        return

    if player.is_frozen or player.is_defrosting:
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame = (player.current_frame + 1) % len(current_animation_frames_list)
        return

    if not (player.is_dead and player.death_animation_finished and not player.is_petrified) or player.is_stone_smashed:
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame += 1

            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead and not player.is_petrified:
                    player.current_frame = len(current_animation_frames_list) - 1
                    player.death_animation_finished = True
                    return
                elif player.is_stone_smashed: # Handles both standing and crouched smashed
                    player.current_frame = len(current_animation_frames_list) -1
                    # death_animation_finished for smashed stone is handled by timer in player.update
                    return

                non_looping_animation_keys = [
                    'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                    'crouch_attack','dash','roll','slide','hit','turn','jump',
                    'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end',
                    'deflame', 'defrost',
                    'aflame_crouch', 'deflame_crouch'
                ]

                if current_animation_key in non_looping_animation_keys:
                    next_logical_state = None
                    player_is_intending_to_move = player.is_trying_to_move_left or player.is_trying_to_move_right

                    if current_animation_key == 'jump':
                        next_logical_state = 'jump_fall_trans' if player.animations.get('jump_fall_trans') else 'fall'
                    elif current_animation_key == 'jump_fall_trans':
                        next_logical_state = 'fall'
                    elif current_animation_key == 'hit':
                        player.is_taking_hit = False
                        next_logical_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                    elif current_animation_key == 'turn':
                        next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif 'attack' in current_animation_key:
                        player.is_attacking = False; player.attack_type = 0
                        if player.on_ladder: next_logical_state = 'ladder_idle'
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif current_animation_key == 'crouch_trans':
                        next_logical_state = 'crouch_walk' if player_is_intending_to_move else 'crouch'
                    elif current_animation_key == 'slide_trans_start':
                        next_logical_state = 'slide'
                    elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                        player.is_sliding = False
                        next_logical_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                    elif current_animation_key == 'aflame_crouch':
                        next_logical_state = 'burning_crouch' # Transition to looping burning crouch
                    elif current_animation_key == 'deflame_crouch':
                        # player.is_deflaming flag is cleared by timer in player.update_status_effects
                        next_logical_state = 'crouch' # End in normal crouch
                    elif current_animation_key == 'deflame' or current_animation_key == 'defrost':
                        next_logical_state = 'idle' if player.on_ground else 'fall'
                    else:
                        if current_animation_key == 'dash': player.is_dashing = False
                        if current_animation_key == 'roll': player.is_rolling = False
                        if player.on_ladder: next_logical_state = 'ladder_idle'
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'

                    if next_logical_state:
                        if player.state == current_animation_key or current_animation_key == 'slide':
                            player.set_state(next_logical_state) # This will re-trigger animation choice
                            return
                        else:
                            player.current_frame = 0 # Loop if state didn't change (e.g. interrupted)
                    else:
                        player.current_frame = 0 # Default loop if no next state determined
                else: # Looping animations (e.g., idle, run, fall, burning, burning_crouch, frozen)
                    player.current_frame = 0

    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0
    elif player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    if not player._valid_init:
        if not hasattr(player, 'animations') or not player.animations:
             if hasattr(player, 'image') and player.image: player.image.fill(C.MAGENTA)
             return

    if not player.alive() and not (player.is_dead and not player.death_animation_finished and not player.is_petrified):
        return

    current_time_ms = pygame.time.get_ticks()
    logical_state_key = determine_animation_key(player)

    current_animation_frames = None
    # MODIFIED: Handle selection of correct stone frames based on crouching status
    if logical_state_key == 'petrified':
        if player.was_crouching_when_petrified:
            current_animation_frames = [player.stone_crouch_image_frame] if player.stone_crouch_image_frame else []
        else:
            current_animation_frames = [player.stone_image_frame] if player.stone_image_frame else []
    elif logical_state_key == 'smashed':
        if player.was_crouching_when_petrified:
            current_animation_frames = player.stone_crouch_smashed_frames if player.stone_crouch_smashed_frames else []
        else:
            current_animation_frames = player.stone_smashed_frames if player.stone_smashed_frames else []
    else:
        current_animation_frames = player.animations.get(logical_state_key)

    if not current_animation_frames:
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{logical_state_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{logical_state_key}' (State: {player.state}) are missing AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        return

    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, logical_state_key)

    # If state changed during advance_frame, re-fetch frames
    if player.state != logical_state_key: # The logical_state_key was for the *start* of this update
        new_logical_key_after_transition = determine_animation_key(player)
        if new_logical_key_after_transition != logical_state_key:
            logical_state_key = new_logical_key_after_transition
            if logical_state_key == 'petrified':
                current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif logical_state_key == 'smashed':
                current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            else:
                new_current_animation_frames = player.animations.get(logical_state_key)
                if new_current_animation_frames: current_animation_frames = new_current_animation_frames

    if not current_animation_frames:
        if hasattr(player, 'image') and player.image: player.image.fill(C.BLUE)
        return

    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0

    if not current_animation_frames:
        if hasattr(player, 'image') and player.image: player.image.fill(C.YELLOW)
        return

    image_for_this_frame = current_animation_frames[player.current_frame]

    should_flip = not player.facing_right
    if logical_state_key == 'petrified' or logical_state_key == 'smashed': # MODIFIED: Apply to smashed as well
        should_flip = not player.facing_at_petrification


    if should_flip:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    image_changed = (player.image is not image_for_this_frame)
    facing_changed = (player._last_facing_right != player.facing_right and logical_state_key not in ['petrified', 'smashed']) or \
                     ((logical_state_key == 'petrified' or logical_state_key == 'smashed') and player._last_facing_right != player.facing_at_petrification)


    # MODIFIED: Check if the displayed image matches the expected stone/smashed (crouch or stand)
    expected_stone_image_now = None
    if logical_state_key == 'petrified':
        expected_stone_image_now = player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame
    elif logical_state_key == 'smashed':
        expected_frame_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
        if expected_frame_list and 0 <= player.current_frame < len(expected_frame_list):
            expected_stone_image_now = expected_frame_list[player.current_frame]

    is_currently_displaying_correct_stone_variant = False
    if expected_stone_image_now:
         # Need to account for flipping when comparing
        current_image_to_compare = player.image
        if should_flip and player.image.get_size() == expected_stone_image_now.get_size(): # If current is flipped, unflip for compare
            # This is tricky without pixel comparison. For now, assume if logical_state_key matches and facing is correct, it's good.
            # A simpler check might be needed if image objects are different despite content.
            is_currently_displaying_correct_stone_variant = (player.state == logical_state_key) # Approximation
        elif not should_flip:
             is_currently_displaying_correct_stone_variant = (player.image is expected_stone_image_now)


    needs_image_update = image_changed or facing_changed
    if (logical_state_key == 'petrified' or logical_state_key == 'smashed') and not is_currently_displaying_correct_stone_variant:
         needs_image_update = True


    if needs_image_update:
        old_rect_midbottom = player.rect.midbottom
        old_rect_height_for_debug = player.rect.height

        player.image = image_for_this_frame
        player.rect = player.image.get_rect()
        player.rect.midbottom = old_rect_midbottom

        player.pos = pygame.math.Vector2(player.rect.midbottom)

        new_rect_height_for_debug = player.rect.height
        if old_rect_height_for_debug != new_rect_height_for_debug:
            if player.print_limiter.can_print(f"anim_height_change_{player.player_id}_{logical_state_key}"):
                print(f"DEBUG ANIM_H (P{player.player_id}): Height Change. Key:'{logical_state_key}'. "
                      f"OldH:{old_rect_height_for_debug}, NewH:{new_rect_height_for_debug}. "
                      f"Rect anchored to old_midbottom: {old_rect_midbottom}. New player.pos: {player.pos}")

        if logical_state_key == 'petrified' or logical_state_key == 'smashed':
            player._last_facing_right = player.facing_at_petrification
        else:
            player._last_facing_right = player.facing_right