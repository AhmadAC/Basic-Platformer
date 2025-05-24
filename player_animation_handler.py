#################### START OF FILE: player_animation_handler.py ####################

# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles player animation selection and frame updates for PySide6.
Correctly anchors the player's rect when height changes.
"""
# version 2.0.3 

from typing import List, Optional
import time # For get_current_ticks fallback

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt

# Game imports
import constants as C
from utils import PrintLimiter

try:
    from player_state_handler import set_player_state
except ImportError:
    def set_player_state(player, new_state):
        if hasattr(player, 'set_state'):
            player.set_state(new_state)
        else:
            print(f"CRITICAL PLAYER_ANIM_HANDLER: player_state_handler.set_player_state not found for Player ID {getattr(player, 'player_id', 'N/A')}")


_start_time_player_anim = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.
 
    """
    return int((time.monotonic() - _start_time_player_anim) * 1000)


def determine_animation_key(player) -> str:
    animation_key = player.state
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    if player.is_petrified:
        return 'smashed' if player.is_stone_smashed else 'petrified'
    if player.is_dead:
        is_still_nm = abs(player.vel.x()) < 0.5 and abs(player.vel.y()) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        return key_variant if player.animations and player.animations.get(key_variant) else \
               ('death' if player.animations and player.animations.get('death') else 'idle')

    if player.is_aflame:
        if player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch'] and \
           player.animations and player.animations.get(player.state):
            return player.state
        if player.is_crouching:
            return 'burning_crouch' if player.animations and player.animations.get('burning_crouch') else \
                   ('aflame_crouch' if player.animations and player.animations.get('aflame_crouch') else 'aflame')
        else:
            return 'burning' if player.animations and player.animations.get('burning') else 'aflame'
    if player.is_deflaming:
        if player.state in ['deflame', 'deflame_crouch'] and \
           player.animations and player.animations.get(player.state):
            return player.state
        return 'deflame_crouch' if player.is_crouching and player.animations and player.animations.get('deflame_crouch') else \
               ('deflame' if player.animations and player.animations.get('deflame') else 'idle')
    if player.is_frozen and player.animations and player.animations.get('frozen'): return 'frozen'
    if player.is_defrosting and player.animations and player.animations.get('defrost'): return 'defrost'

    if player.is_attacking:
        base_key = ''
        if player.attack_type == 1: base_key = 'attack'
        elif player.attack_type == 2: base_key = 'attack2'
        elif player.attack_type == 3: base_key = 'attack_combo'
        elif player.attack_type == 4: base_key = 'crouch_attack'

        if base_key == 'crouch_attack' and player.animations and player.animations.get(base_key):
            animation_key = base_key
        elif base_key:
            nm_variant = f"{base_key}_nm"; moving_variant = base_key
            if player_is_intending_to_move_lr and player.animations and player.animations.get(moving_variant):
                animation_key = moving_variant
            elif player.animations and player.animations.get(nm_variant): animation_key = nm_variant
            elif player.animations and player.animations.get(moving_variant): animation_key = moving_variant
    elif player.state == 'wall_climb':
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y() - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if player.animations and player.animations.get(key_variant): animation_key = key_variant
        elif player.animations and player.animations.get('wall_climb'): animation_key = 'wall_climb'
    elif player.state == 'hit': animation_key = 'hit'
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0):
        animation_key = 'fall'
    elif player.on_ladder:
        animation_key = 'ladder_climb' if abs(player.vel.y()) > 0.1 else 'ladder_idle'
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
            if player.animations and player.animations.get(key_variant): animation_key = key_variant
            elif player.animations and player.animations.get('crouch'): animation_key = 'crouch'
        elif player_is_intending_to_move_lr: animation_key = 'run'
        else: animation_key = 'idle'
    else:
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             animation_key = 'fall' if player.animations and player.animations.get('fall') else 'idle'

    if animation_key not in ['petrified', 'smashed']:
        if not player.animations or not player.animations.get(animation_key):
            if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
                print(f"ANIM_HANDLER Warning (P{player.player_id}): Final animation key '{animation_key}' (State: '{player.state}') missing. Falling back to 'idle'.")
            return 'idle'
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    if not current_animation_frames_list: return

    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0; return

    non_looping_anim_keys_with_transitions = [
        'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
        'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
        'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end',
        'aflame', 'aflame_crouch'
    ]
    non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost']

    can_advance = not (player.is_dead and player.death_animation_finished and not player.is_petrified) or player.is_stone_smashed
    if can_advance and (current_time_ms - player.last_anim_update > ms_per_frame):
        player.last_anim_update = current_time_ms
        player.current_frame += 1

        if player.current_frame >= len(current_animation_frames_list):
            if player.is_dead and not player.is_petrified:
                player.current_frame = len(current_animation_frames_list) - 1
                player.death_animation_finished = True; return
            elif player.is_stone_smashed:
                player.current_frame = len(current_animation_frames_list) - 1; return

            is_trans = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold = current_animation_key in non_looping_hold_last_frame_keys

            if is_trans:
                next_state = player.state
                player_is_moving = player.is_trying_to_move_left or player.is_trying_to_move_right

                if current_animation_key == 'aflame': next_state = 'burning_crouch' if player.is_crouching else 'burning'
                elif current_animation_key == 'aflame_crouch': next_state = 'burning' if not player.is_crouching else 'burning_crouch'
                elif current_animation_key == 'jump': next_state = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans': next_state = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False
                    if player.is_aflame: next_state = 'burning_crouch' if player.is_crouching else 'burning'
                    elif player.is_deflaming: next_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                    else: next_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                elif current_animation_key == 'turn': next_state = 'run' if player_is_moving else 'idle'
                elif 'attack' in current_animation_key:
                    player.is_attacking = False; player.attack_type = 0
                    if player.on_ladder: next_state = 'ladder_idle'
                    elif player.is_crouching: next_state = 'crouch'
                    elif not player.on_ground: next_state = 'fall'
                    else: next_state = 'run' if player_is_moving else 'idle'
                elif current_animation_key == 'crouch_trans': next_state = 'crouch_walk' if player_is_moving else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                    player.is_sliding = False; next_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                elif current_animation_key == 'slide_trans_start': next_state = 'slide'
                elif current_animation_key == 'dash': player.is_dashing = False; next_state = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll': player.is_rolling = False; next_state = 'idle' if player.on_ground else 'fall'

                if player.state == current_animation_key and next_state != player.state:
                    set_player_state(player, next_state); return
                else: player.current_frame = 0
            elif is_hold:
                player.current_frame = len(current_animation_frames_list) - 1
            else: player.current_frame = 0

    if player.is_petrified and not player.is_stone_smashed: player.current_frame = 0
    elif not current_animation_frames_list or player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))

    if not player._valid_init:
        if not hasattr(player, 'animations') or not player.animations:
             if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return
             return

    if not player.alive() and not (player.is_dead and not player.death_animation_finished and not player.is_petrified):
        return

    current_time_ms = get_current_ticks()
    determined_animation_key = determine_animation_key(player)

    current_animation_frames: Optional[List[QPixmap]] = None
    if determined_animation_key == 'petrified':
        current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_animation_key == 'smashed':
        current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations:
        current_animation_frames = player.animations.get(determined_animation_key)

    if not current_animation_frames or not current_animation_frames[0] or current_animation_frames[0].isNull():
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{determined_animation_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{determined_animation_key}' (State: {player.state}) missing/null AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_red); return
        return

    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, determined_animation_key)

    render_animation_key = determined_animation_key
    if player.state != determined_animation_key:
        new_key_for_render = determine_animation_key(player)
        if new_key_for_render != determined_animation_key:
            render_animation_key = new_key_for_render
            if render_animation_key == 'petrified':
                current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_animation_key == 'smashed':
                current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations:
                new_frames_for_render = player.animations.get(render_animation_key)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_animation_frames = new_frames_for_render
                elif not (current_animation_frames and current_animation_frames[0] and not current_animation_frames[0].isNull()):
                    current_animation_frames = player.animations.get('idle', [player.image] if player.image and not player.image.isNull() else [])


    if not current_animation_frames or not current_animation_frames[0] or current_animation_frames[0].isNull():
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_blue); return

    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0
        if not current_animation_frames: # Should be caught by above
            if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_yellow); return

    image_for_this_frame = current_animation_frames[player.current_frame]
    if image_for_this_frame.isNull():
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return

    should_flip = not player.facing_right
    if render_animation_key == 'petrified' or render_animation_key == 'smashed':
        should_flip = not player.facing_at_petrification

    final_image_to_set = image_for_this_frame
    if should_flip:
        q_img = image_for_this_frame.toImage()
        if not q_img.isNull():
            final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
        # else: final_image_to_set remains image_for_this_frame (original) if conversion fails

    image_content_changed = (player.image is None) or \
                            (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (player.image is not final_image_to_set) # Fallback if cacheKey not reliable

    facing_direction_for_flip_check = player.facing_at_petrification if (render_animation_key in ['petrified', 'smashed']) else player.facing_right

    if image_content_changed or (player._last_facing_right != facing_direction_for_flip_check):
        # Use QPointF methods for midbottom calculation
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom())

        player.image = final_image_to_set
        # _update_rect_from_image_and_pos must exist on player and handle QPointF
        if hasattr(player, '_update_rect_from_image_and_pos'):
            player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else: # Fallback if method missing (should not happen if player.py is refactored)
            player.rect = QRectF(old_rect_midbottom_qpointf - QPointF(player.image.width()/2, player.image.height()),
                                 player.image.size())


        player._last_facing_right = facing_direction_for_flip_check

#################### END OF FILE: player_animation_handler.py ####################