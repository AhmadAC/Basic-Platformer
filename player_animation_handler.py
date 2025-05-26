# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles player animation selection and frame updates for PySide6.
Correctly anchors the player's rect when height changes.
MODIFIED: Corrected animation priority for frozen/aflame states.
NOTE: Gravity for dead players is handled by the physics simulation.
MODIFIED: Improved crouch animation logic and attack animation selection.
"""
# version 2.0.6 (Crouch animation refinement and attack logic)

from typing import List, Optional, Any 
import time 

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

# Game imports
import constants as C
from utils import PrintLimiter

# Logger
try:
    from logger import debug, warning, critical
    # CRITICAL: This import must succeed for proper state transitions.
    from player_state_handler import set_player_state
except ImportError:
    print("CRITICAL PLAYER_ANIM_HANDLER: Failed to import logger or player_state_handler.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PANIM: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PANIM: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_PANIM: {msg}")
    # Fallback set_player_state (will cause issues if used, as it won't update flags like is_crouching)
    def set_player_state(player, new_state, current_game_time_ms_param=None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"FALLBACK set_player_state used in player_animation_handler for P{getattr(player, 'player_id', '?')} to {new_state}. CROUCH WILL BE BROKEN.")


_start_time_player_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_anim_monotonic) * 1000)


def determine_animation_key(player: Any) -> str:
    player_id_log = getattr(player, 'player_id', 'Unknown')
    current_logical_state = getattr(player, 'state', 'idle')
    
    is_petrified = getattr(player, 'is_petrified', False)
    is_stone_smashed = getattr(player, 'is_stone_smashed', False)
    is_dead = getattr(player, 'is_dead', False)
    is_frozen = getattr(player, 'is_frozen', False)
    is_defrosting = getattr(player, 'is_defrosting', False)
    is_aflame = getattr(player, 'is_aflame', False)
    is_deflaming = getattr(player, 'is_deflaming', False)
    is_attacking = getattr(player, 'is_attacking', False)
    is_crouching = getattr(player, 'is_crouching', False) # This flag is now key
    on_ground = getattr(player, 'on_ground', False)
    on_ladder = getattr(player, 'on_ladder', False)
    touching_wall = getattr(player, 'touching_wall', 0)
    
    vel_x = getattr(getattr(player, 'vel', None), 'x', lambda: 0.0)()
    vel_y = getattr(getattr(player, 'vel', None), 'y', lambda: 0.0)()
    animations = getattr(player, 'animations', None)

    # --- HIGHEST PRIORITY: Terminal Visual States ---
    if is_petrified:
        return 'smashed' if is_stone_smashed else 'petrified'
    if is_dead:
        is_still_nm = abs(vel_x) < 0.5 and abs(vel_y) < 1.0
        key_variant = 'death_nm' if is_still_nm and animations and animations.get('death_nm') else 'death'
        return key_variant if animations and animations.get(key_variant) else \
               ('death' if animations and animations.get('death') else 'idle')

    # --- Next Priority: Overriding Status Effects (Frozen before Fire) ---
    if is_frozen: return 'frozen' if animations and animations.get('frozen') else 'idle'
    if is_defrosting: return 'defrost' if animations and animations.get('defrost') else \
                             ('frozen' if animations and animations.get('frozen') else 'idle')

    # --- Fire Status Effects (Consider crouch) ---
    if is_aflame:
        if is_crouching: return 'aflame_crouch' if animations and animations.get('aflame_crouch') else \
                                 ('aflame' if animations and animations.get('aflame') else 'idle') # Fallback to standing aflame
        return 'aflame' if animations and animations.get('aflame') else 'idle'
    if is_deflaming:
        if is_crouching: return 'deflame_crouch' if animations and animations.get('deflame_crouch') else \
                                  ('deflame' if animations and animations.get('deflame') else 'idle')
        return 'deflame' if animations and animations.get('deflame') else 'idle'

    # --- Action States (Hit, Attack - consider crouch for attack) ---
    if current_logical_state == 'hit':
        return 'hit' if animations and animations.get('hit') else 'idle'

    if is_attacking:
        attack_type = getattr(player, 'attack_type', 0)
        # If attack_type is 4 (crouch_attack), or if the logical state IS 'crouch_attack'
        if attack_type == 4 or current_logical_state == 'crouch_attack':
            return 'crouch_attack' if animations and animations.get('crouch_attack') else \
                   ('crouch' if is_crouching and animations and animations.get('crouch') else 'idle') # Fallback if no crouch_attack anim
        
        # Standard attacks (not crouch_attack)
        base_key = ''
        if attack_type == 1: base_key = 'attack'
        elif attack_type == 2: base_key = 'attack2'
        elif attack_type == 3: base_key = 'attack_combo'
        
        if base_key:
            is_intentionally_moving_lr_anim = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
            # Velocity check for attack_nm is more about if the *animation itself* should show movement,
            # not if the player has a tiny residual velocity from friction.
            # If player INTENDS to stand still or their current state suggests a non-moving attack, use _nm.
            use_nm_variant = (not is_intentionally_moving_lr_anim and player.state.endswith("_nm")) or \
                             (abs(vel_x) < 0.5 and not is_intentionally_moving_lr_anim)

            nm_variant_key = f"{base_key}_nm"
            moving_variant_key = base_key

            if use_nm_variant and animations and animations.get(nm_variant_key): return nm_variant_key
            elif animations and animations.get(moving_variant_key): return moving_variant_key
            elif animations and animations.get(nm_variant_key): return nm_variant_key # Fallback to NM if moving is missing
            else: return 'idle' # Fallback if all attack anims missing
    
    # --- Other Action States (Dash, Roll, Slide, Turn, Crouch Transition) ---
    if current_logical_state in ['dash', 'roll', 'slide', 'slide_trans_start', 'slide_trans_end', 'turn', 'crouch_trans']:
        return current_logical_state if animations and animations.get(current_logical_state) else 'idle'

    # --- Contextual Movement (Ladder, Wall Interactions) ---
    if on_ladder: return 'ladder_climb' if abs(vel_y) > 0.1 else 'ladder_idle'
    if touching_wall != 0 and not on_ground:
        if current_logical_state == 'wall_slide': return 'wall_slide' if animations and animations.get('wall_slide') else 'fall'
    
    # --- Basic Movement & Idle (Jump, Fall, Run, Crouch, Idle) ---
    if not on_ground: # Airborne
        if current_logical_state == 'jump': return 'jump' if animations and animations.get('jump') else 'fall'
        if current_logical_state == 'jump_fall_trans': return 'jump_fall_trans' if animations and animations.get('jump_fall_trans') else 'fall'
        return 'fall' if animations and animations.get('fall') else 'idle'
    
    # On Ground
    if is_crouching: # Check the is_crouching flag
        # If logical state is already 'crouch' or 'crouch_walk', prefer it
        if current_logical_state in ['crouch', 'crouch_walk'] and animations and animations.get(current_logical_state):
            return current_logical_state
        # Fallback for is_crouching=True
        player_is_intending_to_move_lr_crouch = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
        crouch_key_variant = 'crouch_walk' if player_is_intending_to_move_lr_crouch else 'crouch'
        return crouch_key_variant if animations and animations.get(crouch_key_variant) else \
               ('crouch' if animations and animations.get('crouch') else 'idle')

    # Standing on ground
    player_is_intending_to_move_lr_stand = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
    if player_is_intending_to_move_lr_stand:
        return 'run' if animations and animations.get('run') else 'idle'

    return 'idle' if animations and animations.get('idle') else 'idle'


def advance_frame_and_handle_state_transitions(player: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    if not current_animation_frames_list: return

    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if player.is_petrified and not player.is_stone_smashed: player.current_frame = 0; return
    if player.is_frozen:
        player.current_frame = 0 
        if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen':
            player.current_frame = len(current_animation_frames_list) -1
        return
    if player.is_stone_smashed and player.death_animation_finished:
        player.current_frame = len(current_animation_frames_list) - 1 if current_animation_frames_list else 0
        return

    can_advance_frame = not (player.is_dead and player.death_animation_finished and not player.is_petrified)

    if can_advance_frame and (current_time_ms - player.last_anim_update > ms_per_frame):
        player.last_anim_update = current_time_ms
        player.current_frame += 1

        if player.current_frame >= len(current_animation_frames_list):
            if player.is_dead and not player.is_petrified:
                player.current_frame = len(current_animation_frames_list) - 1
                player.death_animation_finished = True; return
            elif player.is_stone_smashed:
                player.current_frame = len(current_animation_frames_list) - 1
                return

            non_looping_anim_keys_with_transitions = [
                'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end'
            ]
            non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost', 'aflame', 'aflame_crouch']

            is_transitional_anim = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold_last_frame_anim = current_animation_key in non_looping_hold_last_frame_keys

            if is_transitional_anim:
                next_state = player.state 
                player_is_intending_to_move_lr = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
                if current_animation_key == 'jump': next_state = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans': next_state = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False 
                    if player.is_aflame: next_state = 'aflame_crouch' if player.is_crouching else 'aflame'
                    elif player.is_deflaming: next_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                    else: next_state = 'idle' if player.on_ground and not player.on_ladder else 'fall'
                elif current_animation_key == 'turn': next_state = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_attack': # Specific transition for crouch_attack
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    # Stay crouching if still holding crouch or if that's the desired behavior post-attack
                    next_state = 'crouch' # Or 'crouch_walk' if moving
                elif 'attack' in current_animation_key: # For non-crouch attacks
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    if player.on_ladder: next_state = 'ladder_idle'
                    # elif player.is_crouching: next_state = 'crouch' # Should not happen if attack logic is correct
                    elif not player.on_ground: next_state = 'fall'
                    else: next_state = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_trans':
                    next_state = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                    player.is_sliding = False
                    next_state = 'crouch' # Always transition to crouch after slide finishes for toggle behavior
                elif current_animation_key == 'slide_trans_start': next_state = 'slide'
                elif current_animation_key == 'dash': player.is_dashing = False; next_state = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll': player.is_rolling = False; next_state = 'idle' if player.on_ground else 'fall'
                
                if player.state == current_animation_key and next_state != player.state:
                    set_player_state(player, next_state, get_current_ticks_monotonic())
                    return 
                else: player.current_frame = 0
            
            elif is_hold_last_frame_anim:
                player.current_frame = len(current_animation_frames_list) - 1
            else: player.current_frame = 0
    
    if not current_animation_frames_list or player.current_frame < 0 or \
       player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player: Any):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    
    if not getattr(player, '_valid_init', False) or not hasattr(player, 'animations') or not player.animations:
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_magenta)
        return

    can_animate_now = (hasattr(player, 'alive') and player.alive()) or \
                      (getattr(player, 'is_dead', False) and not getattr(player, 'death_animation_finished', True) and not getattr(player, 'is_petrified', False)) or \
                      getattr(player, 'is_petrified', False)

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic()
    determined_key_for_logic = determine_animation_key(player)

    current_frames_list: Optional[List[QPixmap]] = None
    if determined_key_for_logic == 'petrified':
        current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_key_for_logic == 'smashed':
        current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations:
        current_frames_list = player.animations.get(determined_key_for_logic)

    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    elif len(current_frames_list) == 1 and \
         determined_key_for_logic not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'crouch', 'crouch_attack', 'ladder_idle', 'wall_hang']: # Added crouch_attack
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40):
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue:
                    is_current_animation_valid = False

    if not is_current_animation_valid:
        if determined_key_for_logic != 'idle':
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_frames_missing_final_{player.player_id}_{determined_key_for_logic}"):
                warning(f"PlayerAnimHandler Warning (P{player.player_id}): Animation for key '{determined_key_for_logic}' (State: {player.state}) missing/placeholder. Switching to 'idle'.")
        determined_key_for_logic = 'idle'; current_frames_list = player.animations.get('idle') if player.animations else None
        is_idle_still_invalid = not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))
        if is_idle_still_invalid:
            critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta)
            return

    if not current_frames_list:
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_blue); return

    advance_frame_and_handle_state_transitions(player, current_frames_list, current_time_ms, determined_key_for_logic)

    render_key_for_final_image = determined_key_for_logic
    current_player_logical_state_after_advance = getattr(player, 'state', 'idle')
    if current_player_logical_state_after_advance != determined_key_for_logic and \
       not (getattr(player, 'is_petrified', False) and determined_key_for_logic in ['petrified', 'smashed']):
        new_render_key_candidate = determine_animation_key(player)
        if new_render_key_candidate != determined_key_for_logic:
            render_key_for_final_image = new_render_key_candidate
            if render_key_for_final_image == 'petrified':
                current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_key_for_final_image == 'smashed':
                current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations:
                new_frames_for_render = player.animations.get(render_key_for_final_image)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render

    if not current_frames_list or player.current_frame < 0 or player.current_frame >= len(current_frames_list):
        player.current_frame = 0
        if not current_frames_list:
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0))))
            return

    image_for_this_frame = current_frames_list[player.current_frame]
    if image_for_this_frame.isNull():
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return

    display_facing_right = player.facing_right
    if render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed':
        display_facing_right = player.facing_at_petrification

    final_image_to_set = image_for_this_frame
    if not display_facing_right:
        if not (render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed'):
            q_img = image_for_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))

    image_content_changed = (not hasattr(player, 'image') or player.image is None) or \
                            (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (player.image is not final_image_to_set)

    if image_content_changed or (getattr(player, '_last_facing_right_visual_for_anim', True) != display_facing_right):
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom()) if hasattr(player, 'rect') and player.rect else player.pos
        player.image = final_image_to_set
        if hasattr(player, '_update_rect_from_image_and_pos') and callable(player._update_rect_from_image_and_pos):
            player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else: 
            player.rect = QRectF(old_rect_midbottom_qpointf - QPointF(player.image.width()/2.0, float(player.image.height())), player.image.size())
        player._last_facing_right_visual_for_anim = display_facing_right