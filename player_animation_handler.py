# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles player animation selection and frame updates for PySide6.
Correctly anchors the player's rect when height changes.
Includes handling for 'zapped' animation.
"""
# version 2.0.4 (Integrated zapped animation, local import for state_handler)

from typing import List, Optional, Any
import time

from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

import constants as C
from utils import PrintLimiter
from logger import debug, warning, critical

# LOCAL IMPORT for set_player_state in advance_frame_and_handle_state_transitions
# from player_state_handler import set_player_state # MOVED

_start_time_player_anim = time.monotonic()
def get_current_ticks():
    return int((time.monotonic() - _start_time_player_anim) * 1000)


def determine_animation_key(player: Any) -> str:
    # ... (This function remains the same as provided in my previous "update the entire player_animation_handler" response)
    # Ensure it includes the 'zapped' key check:
    # if player.is_zapped: return 'zapped'
    animation_key = player.state
    player_id_log = f"P{player.player_id}"
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    if player.is_petrified:
        return 'smashed' if player.is_stone_smashed else 'petrified'
    if player.is_dead:
        is_still_nm = abs(player.vel.x()) < 0.5 and abs(player.vel.y()) < 1.0
        key_variant = 'death_nm' if is_still_nm else 'death'
        if player.animations and player.animations.get(key_variant): return key_variant
        if player.animations and player.animations.get('death'): return 'death'
        return 'idle'

    if player.is_zapped: return 'zapped' # Added zapped check

    if player.is_aflame:
        if player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch'] and player.animations and player.animations.get(player.state): return player.state
        if player.is_crouching: return 'burning_crouch' if player.animations and player.animations.get('burning_crouch') else ('aflame_crouch' if player.animations and player.animations.get('aflame_crouch') else 'aflame')
        else: return 'burning' if player.animations and player.animations.get('burning') else 'aflame'
    if player.is_deflaming:
        if player.state in ['deflame', 'deflame_crouch'] and player.animations and player.animations.get(player.state): return player.state
        return 'deflame_crouch' if player.is_crouching and player.animations and player.animations.get('deflame_crouch') else ('deflame' if player.animations and player.animations.get('deflame') else 'idle')
    if player.is_frozen and player.animations and player.animations.get('frozen'): return 'frozen'
    if player.is_defrosting and player.animations and player.animations.get('defrost'): return 'defrost'
    if player.state == 'hit': return 'hit'
    if hasattr(player, 'post_attack_pause_timer') and player.post_attack_pause_timer > 0 and get_current_ticks() < player.post_attack_pause_timer: return 'idle'
    if player.is_attacking:
        base_key = ''; attack_type = getattr(player, 'attack_type', 0)
        if attack_type == 1: base_key = 'attack'
        elif attack_type == 2: base_key = 'attack2'
        elif attack_type == 3: base_key = 'attack_combo'
        elif attack_type == 4: base_key = 'crouch_attack'
        if base_key:
            if base_key == 'crouch_attack' and player.animations and player.animations.get(base_key): return base_key
            nm_variant = f"{base_key}_nm"; moving_variant = base_key
            if player_is_intending_to_move_lr and player.animations and player.animations.get(moving_variant): return moving_variant
            elif player.animations and player.animations.get(nm_variant): return nm_variant
            elif player.animations and player.animations.get(moving_variant): return moving_variant
    if not player.on_ground and not player.on_ladder and player.touching_wall == 0 and player.state not in ['jump', 'jump_fall_trans'] and player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0): return 'fall'
    if player.on_ladder: return 'ladder_climb' if abs(player.vel.y()) > 0.1 else 'ladder_idle'
    if player.is_dashing: return 'dash'
    if player.is_rolling: return 'roll'
    if player.is_sliding: return 'slide'
    if player.state == 'slide_trans_start': return 'slide_trans_start'
    if player.state == 'slide_trans_end': return 'slide_trans_end'
    if player.state == 'crouch_trans': return 'crouch_trans'
    if player.state == 'turn': return 'turn'
    if player.state == 'jump': return 'jump'
    if player.state == 'jump_fall_trans': return 'jump_fall_trans'
    if player.state == 'wall_slide': return 'wall_slide'
    if player.state == 'wall_hang': return 'wall_hang'
    if player.on_ground:
        if player.is_crouching:
            key_variant = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
            if player.animations and player.animations.get(key_variant): return key_variant
            if player.animations and player.animations.get('crouch'): return 'crouch'
        elif player_is_intending_to_move_lr: return 'run'
        else: return 'idle'
    else:
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'hit', 'dash', 'roll']: return 'fall' if player.animations and player.animations.get('fall') else 'idle'
    if player.animations and player.animations.get(player.state): return player.state
    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_key_abs_fallback_{player_id_log}_{player.state}"): warning(f"ANIM_HANDLER Warning ({player_id_log}): Could not determine specific animation for logical state '{player.state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_frame_and_handle_state_transitions(player: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    # LOCAL IMPORT for set_player_state
    try:
        from player_state_handler import set_player_state
    except ImportError:
        critical("PLAYER_ANIM_HANDLER (advance_frame): Failed to import set_player_state locally.")
        def set_player_state(p_arg: Any, ns_arg: str): pass # Fallback dummy

    if not current_animation_frames_list: return

    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if player.is_petrified and not player.is_stone_smashed: player.current_frame = 0; return
    
    # Zapped animation might loop or hold, depending on desired effect and asset.
    # If it should loop while zapped effect is active:
    if current_animation_key == 'zapped' and getattr(player, 'is_zapped', False) :
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame = (player.current_frame + 1) % len(current_animation_frames_list)
        return # Don't proceed to other transition logic if zapped and looping/holding

    can_advance_frame = not (player.is_dead and player.death_animation_finished and not player.is_petrified) or player.is_stone_smashed
    if can_advance_frame and (current_time_ms - player.last_anim_update > ms_per_frame):
        player.last_anim_update = current_time_ms
        player.current_frame += 1
        if player.current_frame >= len(current_animation_frames_list):
            if player.is_dead and not player.is_petrified: player.current_frame = len(current_animation_frames_list) - 1; player.death_animation_finished = True; return
            elif player.is_stone_smashed: player.current_frame = len(current_animation_frames_list) - 1; return
            non_looping_anim_keys_with_transitions = [
                'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end',
                'aflame', 'aflame_crouch' 
                # Removed 'zapped' from here; its duration is managed by status_effects, animation might loop
            ]
            non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost', 'frozen']
            is_transition_anim = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold_last_frame_anim = current_animation_key in non_looping_hold_last_frame_keys

            if is_transition_anim:
                next_state = player.state; player_is_moving = player.is_trying_to_move_left or player.is_trying_to_move_right
                if current_animation_key == 'aflame': next_state = 'burning_crouch' if player.is_crouching else 'burning'
                elif current_animation_key == 'aflame_crouch': next_state = 'burning' if not player.is_crouching else 'burning_crouch'
                elif current_animation_key == 'jump': next_state = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans': next_state = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False
                    if player.is_aflame: next_state = 'burning_crouch' if player.is_crouching else 'burning'
                    elif player.is_deflaming: next_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                    elif player.is_zapped: next_state = 'zapped' # Should remain zapped if effect is active
                    else: next_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                elif current_animation_key == 'turn': next_state = 'run' if player_is_moving else 'idle'
                elif 'attack' in current_animation_key:
                    player.is_attacking = False; player.attack_type = 0
                    if player.on_ladder: next_state = 'ladder_idle'
                    elif player.is_crouching: next_state = 'crouch'
                    elif not player.on_ground: next_state = 'fall'
                    else: next_state = 'run' if player_is_moving else 'idle'
                elif current_animation_key == 'crouch_trans': next_state = 'crouch_walk' if player_is_moving else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end': player.is_sliding = False; next_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                elif current_animation_key == 'slide_trans_start': next_state = 'slide'
                elif current_animation_key == 'dash': player.is_dashing = False; next_state = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll': player.is_rolling = False; next_state = 'idle' if player.on_ground else 'fall'
                if player.state == current_animation_key and next_state != player.state: set_player_state(player, next_state); return
                else: player.current_frame = 0
            elif is_hold_last_frame_anim: player.current_frame = len(current_animation_frames_list) - 1
            else: player.current_frame = 0
    if player.is_petrified and not player.is_stone_smashed: player.current_frame = 0
    elif not current_animation_frames_list or player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list): player.current_frame = 0


def update_player_animation(player: Any):
    # ... (qcolor definitions remain the same)
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))
    player_id_log = f"P{player.player_id}"

    if not player._valid_init:
        if not hasattr(player, 'animations') or not player.animations:
             if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return
             return

    can_animate_now = player.alive() or \
                      (player.is_dead and not player.death_animation_finished and not player.is_petrified) or \
                      (player.is_petrified) or \
                      (player.is_zapped) # Zapped players animate

    if not can_animate_now: return

    current_time_ms = get_current_ticks()
    determined_animation_key = determine_animation_key(player)
    current_animation_frames: Optional[List[QPixmap]] = None
    if determined_animation_key == 'petrified': current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_animation_key == 'smashed': current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations: current_animation_frames = player.animations.get(determined_animation_key)

    animation_is_valid = True
    if not current_animation_frames or not current_animation_frames[0] or current_animation_frames[0].isNull(): animation_is_valid = False
    elif len(current_animation_frames) == 1 and determined_animation_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'zapped']: # Allow single-frame for these
        frame_pixmap = current_animation_frames[0]
        if frame_pixmap.size() == QSize(30, 40):
            qimg = frame_pixmap.toImage();
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue: animation_is_valid = False
    if not animation_is_valid:
        if determined_animation_key != 'idle':
             if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_key_invalid_update_{player_id_log}_{determined_animation_key}"): warning(f"ANIM_HANDLER Warning ({player_id_log}): Animation for key '{determined_animation_key}' (State: {player.state}) missing/placeholder. Switching to 'idle'.")
        determined_animation_key = 'idle'
        current_animation_frames = player.animations.get('idle') if player.animations else None
        is_idle_still_invalid = not current_animation_frames or not current_animation_frames[0] or current_animation_frames[0].isNull() or \
                                (len(current_animation_frames) == 1 and current_animation_frames[0].size() == QSize(30,40) and \
                                 (current_animation_frames[0].toImage().pixelColor(0,0) == qcolor_red or current_animation_frames[0].toImage().pixelColor(0,0) == qcolor_blue))
        if is_idle_still_invalid:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_idle_critical_fail_{player_id_log}"): critical(f"ANIM_HANDLER CRITICAL ({player_id_log}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta)
            return
    if not current_animation_frames:
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_blue); return

    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, determined_animation_key)
    render_animation_key = determined_animation_key
    current_player_logical_state = getattr(player, 'state', 'idle')
    if current_player_logical_state != determined_animation_key and not (player.is_petrified and determined_animation_key in ['petrified', 'smashed']):
        new_key_for_render = determine_animation_key(player)
        if new_key_for_render != determined_animation_key:
            render_animation_key = new_key_for_render
            if render_animation_key == 'petrified': current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_animation_key == 'smashed': current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations:
                new_frames_for_render = player.animations.get(render_animation_key, [])
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull(): current_animation_frames = new_frames_for_render
                elif not (current_animation_frames and current_animation_frames[0] and not current_animation_frames[0].isNull()): current_animation_frames = player.animations.get('idle', [player.image] if player.image and not player.image.isNull() else [])
    if not current_animation_frames or player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0
        if not current_animation_frames:
            if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_yellow); return
    image_for_this_frame = current_animation_frames[player.current_frame]
    if image_for_this_frame.isNull():
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return
    should_flip_visual = not player.facing_right
    if render_animation_key == 'petrified' or render_animation_key == 'smashed': should_flip_visual = not player.facing_at_petrification
    final_image_to_set = image_for_this_frame
    if should_flip_visual:
        q_img = image_for_this_frame.toImage()
        if not q_img.isNull(): final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
    image_content_has_changed = (player.image is None) or \
                                (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                                (player.image is not final_image_to_set)
    current_visual_facing_direction = player.facing_at_petrification if (render_animation_key in ['petrified', 'smashed']) else player.facing_right
    if image_content_has_changed or (player._last_facing_right != current_visual_facing_direction):
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom())
        player.image = final_image_to_set
        if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else:
            warning(f"ANIM_HANDLER Warning ({player_id_log}): Player missing '_update_rect_from_image_and_pos' method. Rect update might be incorrect.")
            new_rect_center = old_rect_midbottom_qpointf - QPointF(0, player.rect.height()/2)
            player.rect = QRectF(new_rect_center - QPointF(player.image.width()/2, player.image.height()/2), player.image.size())
        player._last_facing_right = current_visual_facing_direction