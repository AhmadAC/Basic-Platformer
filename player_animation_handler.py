# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.7 (Integrated player aflame/frozen/defrost animations)
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
    if player.is_petrified:
        return 'smashed' if player.is_stone_smashed else 'petrified'
    if player.is_dead: # Normal death (not petrified/smashed)
        is_still_nm = abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        if key_variant in player.animations and player.animations[key_variant]: return key_variant
        elif 'death' in player.animations and player.animations['death']: return 'death'
        else: return 'idle' # Fallback if no death animation

    # --- Next Priority: Persistent Status Effect Visuals ---
    if player.is_aflame and 'aflame' in player.animations and player.animations['aflame']:
        return 'aflame'
    if player.is_deflaming and 'deflame' in player.animations and player.animations['deflame']:
        return 'deflame'
    if player.is_frozen and 'frozen' in player.animations and player.animations['frozen']:
        return 'frozen'
    if player.is_defrosting and 'defrost' in player.animations and player.animations['defrost']:
        return 'defrost'

    # --- Then, standard actions/movement states ---
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

    if animation_key not in ['petrified', 'smashed']:
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

    if player.is_petrified and not player.is_stone_smashed: 
        player.current_frame = 0
        return
    
    if player.is_frozen or player.is_defrosting: # Animation might cycle for these states
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame = (player.current_frame + 1) % len(current_animation_frames_list)
        return # No state transitions driven by animation end for frozen/defrost

    if not (player.is_dead and player.death_animation_finished and not player.is_petrified) or player.is_stone_smashed: 
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame += 1

            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead and not player.is_petrified: 
                    player.current_frame = len(current_animation_frames_list) - 1 
                    player.death_animation_finished = True
                    return 
                elif player.is_stone_smashed: 
                    player.current_frame = len(current_animation_frames_list) -1
                    # death_animation_finished will be handled by timer in player.update
                    return 

                non_looping_animation_keys = [
                    'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                    'crouch_attack','dash','roll','slide','hit','turn','jump',
                    'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end',
                    'deflame', 'defrost' # Add deflame and defrost as non-looping
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
                    elif current_animation_key == 'deflame' or current_animation_key == 'defrost':
                        # These flags are cleared by player.update_status_effects when duration ends
                        # Here, we just ensure the animation stops and transitions to a sensible state.
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
                            player.set_state(next_logical_state)
                            return 
                        else: 
                            player.current_frame = 0
                    else: 
                        player.current_frame = 0 
                else: # Looping animations (e.g., idle, run, fall, aflame, frozen)
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
    if logical_state_key == 'petrified': 
        current_animation_frames = [player.stone_image_frame] if player.stone_image_frame else []
    elif logical_state_key == 'smashed': 
        current_animation_frames = player.stone_smashed_frames if player.stone_smashed_frames else []
    else: 
        current_animation_frames = player.animations.get(logical_state_key)

    if not current_animation_frames: 
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{logical_state_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{logical_state_key}' (State: {player.state}) are missing AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        return

    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, logical_state_key)

    if player.state != logical_state_key: 
        new_logical_key_after_transition = determine_animation_key(player)
        if new_logical_key_after_transition == 'petrified':
            current_animation_frames = [player.stone_image_frame] if player.stone_image_frame else []
        elif new_logical_key_after_transition == 'smashed':
            current_animation_frames = player.stone_smashed_frames if player.stone_smashed_frames else []
        else:
            new_current_animation_frames = player.animations.get(new_logical_key_after_transition)
            if new_current_animation_frames:
                current_animation_frames = new_current_animation_frames
        
    if not current_animation_frames: 
        if hasattr(player, 'image') and player.image: player.image.fill(C.BLUE)
        return

    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0 

    image_for_this_frame = current_animation_frames[player.current_frame]

    should_flip = not player.facing_right
    if logical_state_key == 'petrified': # Petrified state uses facing_at_petrification
        should_flip = not player.facing_at_petrification
    elif logical_state_key == 'smashed':
        # Smashed animation usually doesn't need flipping, or flips based on facing_at_petrification
        # For now, assume no flip for smashed, or base it on facing_at_petrification if frames are directional
        should_flip = not player.facing_at_petrification if hasattr(player, 'facing_at_petrification') else False


    if should_flip:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # Determine if image or facing direction has changed
    image_changed = (player.image is not image_for_this_frame)
    facing_changed = (player._last_facing_right != player.facing_right and logical_state_key not in ['petrified', 'smashed']) or \
                     (logical_state_key == 'petrified' and player._last_facing_right != player.facing_at_petrification)
    
    # Special check for stone states as their image source is different
    is_currently_displaying_stone = (player.is_petrified and not player.is_stone_smashed and player.image is player.stone_image_frame)
    is_currently_displaying_smashed = (player.is_stone_smashed and player.image in player.stone_smashed_frames)

    needs_image_update = image_changed or facing_changed
    if logical_state_key == 'petrified' and not is_currently_displaying_stone: needs_image_update = True
    if logical_state_key == 'smashed' and not is_currently_displaying_smashed: needs_image_update = True


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

        player._last_facing_right = player.facing_right if logical_state_key not in ['petrified', 'smashed'] else player.facing_at_petrification