#################### START OF MODIFIED FILE: player_animation_handler.py ####################

# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.16 (Corrected looping logic for animations)
Handles player animation selection and frame updates.
Correctly anchors the player's rect when height changes (e.g., crouching),
ensuring the player's feet (midbottom) remain consistent, and updates player.pos.
"""
import pygame
import constants as C
from utils import PrintLimiter # Assuming PrintLimiter is accessible

def determine_animation_key(player):
    # ... (This function remains the same as the previous correct version)
    animation_key = player.state
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    if player.is_petrified:
        return 'smashed' if player.is_stone_smashed else 'petrified'
    if player.is_dead:
        is_still_nm = abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        return key_variant if player.animations.get(key_variant) else \
               ('death' if player.animations.get('death') else 'idle')

    if player.is_aflame: 
        if player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch'] and \
           player.animations.get(player.state):
            return player.state
        if player.is_crouching:
            return 'burning_crouch' if player.animations.get('burning_crouch') else \
                   ('aflame_crouch' if player.animations.get('aflame_crouch') else 'aflame')
        else:
            return 'burning' if player.animations.get('burning') else 'aflame'

    if player.is_deflaming: 
        if player.state in ['deflame', 'deflame_crouch'] and \
           player.animations.get(player.state):
            return player.state
        return 'deflame_crouch' if player.is_crouching and player.animations.get('deflame_crouch') else \
               ('deflame' if player.animations.get('deflame') else 'idle')

    if player.is_frozen and player.animations.get('frozen'):
        return 'frozen'
    if player.is_defrosting and player.animations.get('defrost'):
        return 'defrost'

    if player.is_attacking:
        base_key = ''
        if player.attack_type == 1: base_key = 'attack'
        elif player.attack_type == 2: base_key = 'attack2'
        elif player.attack_type == 3: base_key = 'attack_combo'
        elif player.attack_type == 4: base_key = 'crouch_attack'
        if base_key == 'crouch_attack' and player.animations.get(base_key): animation_key = base_key
        elif base_key:
            nm_variant = f"{base_key}_nm"; moving_variant = base_key
            if player_is_intending_to_move_lr and player.animations.get(moving_variant): animation_key = moving_variant
            elif player.animations.get(nm_variant): animation_key = nm_variant
            elif player.animations.get(moving_variant): animation_key = moving_variant
            else: animation_key = player.state
    elif player.state == 'wall_climb':
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if player.animations.get(key_variant): animation_key = key_variant
        elif player.animations.get('wall_climb'): animation_key = 'wall_climb'
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
            if player.animations.get(key_variant): animation_key = key_variant
            elif player.animations.get('crouch'): animation_key = 'crouch'
        elif player_is_intending_to_move_lr: animation_key = 'run'
        else: animation_key = 'idle'
    else:
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             animation_key = 'fall' if player.animations.get('fall') else 'idle'

    if animation_key not in ['petrified', 'smashed']:
        if not player.animations.get(animation_key):
            if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
                print(f"ANIM_HANDLER Warning (P{player.player_id}): Final animation key '{animation_key}' (State: '{player.state}') "
                      f"is invalid/missing. Falling back to 'idle'.")
            return 'idle'
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list, current_time_ms, current_animation_key):
    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0
        return

    # Define animations that play once and then trigger a state change.
    non_looping_anim_keys_with_transitions = [
        'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
        'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
        'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end',
        'aflame',           # Initial standing fire
        'aflame_crouch'     # Initial crouched fire
    ]
    # Define animations that play once and then hold their last frame visually.
    # The actual logical state change is handled by timers in player.py (update_status_effects).
    non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost']


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
                    return

                # Determine if current animation is one that transitions OR holds its last frame
                is_non_looping_with_transition = current_animation_key in non_looping_anim_keys_with_transitions
                is_non_looping_hold_frame = current_animation_key in non_looping_hold_last_frame_keys

                if is_non_looping_with_transition:
                    next_logical_state = player.state # Default to no change if conditions below aren't met
                    player_is_intending_to_move = player.is_trying_to_move_left or player.is_trying_to_move_right

                    if current_animation_key == 'aflame':
                        if player.is_aflame:
                            next_logical_state = 'burning_crouch' if player.is_crouching else 'burning'
                    elif current_animation_key == 'aflame_crouch':
                        if player.is_aflame:
                            next_logical_state = 'burning' if not player.is_crouching else 'burning_crouch'
                    elif current_animation_key == 'jump': next_logical_state = 'jump_fall_trans' if player.animations.get('jump_fall_trans') else 'fall'
                    elif current_animation_key == 'jump_fall_trans': next_logical_state = 'fall'
                    elif current_animation_key == 'hit':
                        player.is_taking_hit = False
                        if player.is_aflame: next_logical_state = 'burning_crouch' if player.is_crouching else 'burning'
                        elif player.is_deflaming: next_logical_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                        else: next_logical_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                    elif current_animation_key == 'turn': next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif 'attack' in current_animation_key:
                        player.is_attacking = False; player.attack_type = 0
                        if player.on_ladder: next_logical_state = 'ladder_idle'
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif current_animation_key == 'crouch_trans': next_logical_state = 'crouch_walk' if player_is_intending_to_move else 'crouch'
                    elif current_animation_key == 'slide_trans_start': next_logical_state = 'slide'
                    elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                        player.is_sliding = False
                        next_logical_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                    elif current_animation_key == 'dash': player.is_dashing = False; next_logical_state = 'idle' if player.on_ground else 'fall'
                    elif current_animation_key == 'roll': player.is_rolling = False; next_logical_state = 'idle' if player.on_ground else 'fall'

                    if player.state == current_animation_key and next_logical_state != player.state :
                        player.set_state(next_logical_state)
                        return
                    else:
                        player.current_frame = 0 # Default to loop/restart if no transition happened as expected
                
                elif is_non_looping_hold_frame:
                    player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                    # State change will be triggered by timers in player.update_status_effects
                
                else: # Otherwise, it's a looping animation
                    player.current_frame = 0

    # Final boundary check
    if player.is_petrified and not player.is_stone_smashed: player.current_frame = 0
    elif not current_animation_frames_list or player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    # ... (This function remains the same as the previous correct version) ...
    if not player._valid_init:
        if not hasattr(player, 'animations') or not player.animations:
             if hasattr(player, 'image') and player.image: player.image.fill(C.MAGENTA)
             return

    if not player.alive() and not (player.is_dead and not player.death_animation_finished and not player.is_petrified):
        return

    current_time_ms = pygame.time.get_ticks()
    determined_animation_key = determine_animation_key(player)

    current_animation_frames = None
    if determined_animation_key == 'petrified':
        if player.was_crouching_when_petrified:
            current_animation_frames = [player.stone_crouch_image_frame] if player.stone_crouch_image_frame else []
        else:
            current_animation_frames = [player.stone_image_frame] if player.stone_image_frame else []
    elif determined_animation_key == 'smashed':
        if player.was_crouching_when_petrified:
            current_animation_frames = player.stone_crouch_smashed_frames if player.stone_crouch_smashed_frames else []
        else:
            current_animation_frames = player.stone_smashed_frames if player.stone_smashed_frames else []
    else:
        current_animation_frames = player.animations.get(determined_animation_key)

    if not current_animation_frames:
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{determined_animation_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{determined_animation_key}' (State: {player.state}) are missing AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        return

    key_used_for_advance = determined_animation_key
    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, key_used_for_advance)

    render_animation_key = determined_animation_key
    if player.state != determined_animation_key:
        new_key_for_render = determine_animation_key(player)
        if new_key_for_render != determined_animation_key:
            render_animation_key = new_key_for_render
            if render_animation_key == 'petrified':
                current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_animation_key == 'smashed':
                current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            else:
                new_frames_for_render = player.animations.get(render_animation_key)
                if new_frames_for_render:
                    current_animation_frames = new_frames_for_render
                else: 
                    if player.print_limiter.can_print(f"anim_frames_missing_render_post_trans_{player.player_id}_{render_animation_key}"):
                         print(f"ANIM_HANDLER Warning (P{player.player_id}): Frames for re-determined render key '{render_animation_key}' missing. Image may be inconsistent.")
                    if not current_animation_frames: current_animation_frames = player.animations.get('idle', [player.image])


    if not current_animation_frames: 
        if hasattr(player, 'image') and player.image: player.image.fill(C.BLUE); return

    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0
        if not current_animation_frames:
            if hasattr(player, 'image') and player.image: player.image.fill(C.YELLOW); return

    image_for_this_frame = current_animation_frames[player.current_frame]

    should_flip = not player.facing_right
    if render_animation_key == 'petrified' or render_animation_key == 'smashed':
        should_flip = not player.facing_at_petrification

    if should_flip:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    if player.image is not image_for_this_frame or \
       (render_animation_key not in ['petrified', 'smashed'] and player._last_facing_right != player.facing_right) or \
       ((render_animation_key == 'petrified' or render_animation_key == 'smashed') and player._last_facing_right != player.facing_at_petrification):
        
        old_rect_midbottom = player.rect.midbottom
        old_rect_height_for_debug = player.rect.height

        player.image = image_for_this_frame
        player.rect = player.image.get_rect(midbottom=old_rect_midbottom)
        player.pos = pygame.math.Vector2(player.rect.midbottom)

        new_rect_height_for_debug = player.rect.height
        if old_rect_height_for_debug != new_rect_height_for_debug:
            if player.print_limiter.can_print(f"anim_height_change_{player.player_id}_{render_animation_key}"):
                print(f"DEBUG ANIM_H (P{player.player_id}): Height Change. Key:'{render_animation_key}'. "
                      f"OldH:{old_rect_height_for_debug}, NewH:{new_rect_height_for_debug}. "
                      f"Rect anchored to old_midbottom: {old_rect_midbottom}. New player.pos: {player.pos}")

        if render_animation_key == 'petrified' or render_animation_key == 'smashed':
            player._last_facing_right = player.facing_at_petrification
        else:
            player._last_facing_right = player.facing_right

#################### END OF MODIFIED FILE: player_animation_handler.py ####################