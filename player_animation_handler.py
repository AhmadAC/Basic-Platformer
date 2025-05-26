# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles player animation selection and frame updates for PySide6.
Correctly anchors the player's rect when height changes.
MODIFIED: Corrected animation priority for frozen/aflame states.
"""
# version 2.0.4 (Frozen/Aflame animation priority fix)

from typing import List, Optional, Any # Added Any
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
    from player_state_handler import set_player_state
except ImportError:
    print("CRITICAL PLAYER_ANIM_HANDLER: Failed to import logger or player_state_handler.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PANIM: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PANIM: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_PANIM: {msg}")
    def set_player_state(player, new_state, current_game_time_ms_param=None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used in player_animation_handler for P{getattr(player, 'player_id', '?')}")


_start_time_player_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_anim_monotonic) * 1000)


def determine_animation_key(player: Any) -> str:
    player_id_log = getattr(player, 'player_id', 'Unknown')
    current_logical_state = getattr(player, 'state', 'idle') # The player's current logical state machine state
    
    # For easier access to player attributes, reducing multiple getattr calls
    is_petrified = getattr(player, 'is_petrified', False)
    is_stone_smashed = getattr(player, 'is_stone_smashed', False)
    is_dead = getattr(player, 'is_dead', False)
    is_frozen = getattr(player, 'is_frozen', False)
    is_defrosting = getattr(player, 'is_defrosting', False)
    is_aflame = getattr(player, 'is_aflame', False)
    is_deflaming = getattr(player, 'is_deflaming', False)
    is_attacking = getattr(player, 'is_attacking', False)
    is_crouching = getattr(player, 'is_crouching', False)
    on_ground = getattr(player, 'on_ground', False)
    on_ladder = getattr(player, 'on_ladder', False)
    touching_wall = getattr(player, 'touching_wall', 0)
    
    vel_x = getattr(getattr(player, 'vel', None), 'x', lambda: 0.0)()
    vel_y = getattr(getattr(player, 'vel', None), 'y', lambda: 0.0)()
    animations = getattr(player, 'animations', None)

    # --- HIGHEST PRIORITY: Terminal Visual States ---
    if is_petrified:
        return 'smashed' if is_stone_smashed else 'petrified'
    
    if is_dead: # Includes normal death (not petrified)
        is_still_nm = abs(vel_x) < 0.5 and abs(vel_y) < 1.0 # Check if mostly still for "No Movement" death anim
        key_variant = 'death_nm' if is_still_nm and animations and animations.get('death_nm') else 'death'
        return key_variant if animations and animations.get(key_variant) else \
               ('death' if animations and animations.get('death') else 'idle') # Fallback to 'death' then 'idle'

    # --- Next Priority: Overriding Status Effects (Frozen before Fire) ---
    if is_frozen:
        return 'frozen' if animations and animations.get('frozen') else 'idle' # Fallback if no frozen anim
    if is_defrosting:
        return 'defrost' if animations and animations.get('defrost') else \
               ('frozen' if animations and animations.get('frozen') else 'idle') # Fallback

    # --- Fire Status Effects ---
    if is_aflame:
        # Check if current logical state IS a specific fire animation (e.g., "aflame", "burning")
        # The logical state should ideally drive this if different fire phases have different animations.
        # For now, assuming 'aflame' and 'aflame_crouch' are the primary visual keys for being on fire.
        if current_logical_state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch'] and animations and animations.get(current_logical_state):
            return current_logical_state
        # Fallback based on crouch status if specific fire state animation isn't set/found
        return 'aflame_crouch' if is_crouching and animations and animations.get('aflame_crouch') else \
               ('aflame' if animations and animations.get('aflame') else 'idle') # Fallback to idle if no aflame anims

    if is_deflaming:
        if current_logical_state in ['deflame', 'deflame_crouch'] and animations and animations.get(current_logical_state):
            return current_logical_state
        return 'deflame_crouch' if is_crouching and animations and animations.get('deflame_crouch') else \
               ('deflame' if animations and animations.get('deflame') else 'idle') # Fallback to idle


    # --- Action States (Hit, Attack) ---
    # 'hit' state should have high priority as it visually interrupts other actions.
    if current_logical_state == 'hit':
        return 'hit' if animations and animations.get('hit') else 'idle'

    if is_attacking:
        base_key = ''
        attack_type = getattr(player, 'attack_type', 0)
        if attack_type == 1: base_key = 'attack'
        elif attack_type == 2: base_key = 'attack2'
        elif attack_type == 3: base_key = 'attack_combo'
        elif attack_type == 4: base_key = 'crouch_attack'

        if base_key == 'crouch_attack': # Crouch attack doesn't usually have NM variant
            return base_key if animations and animations.get(base_key) else 'crouch'
        elif base_key:
            # Determine if a "No Movement" (_nm) variant should be used
            # Player might be "attacking" but visually should be "attack_nm" if not intending to move or velocity is low
            is_intentionally_moving_lr_anim = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
            is_actually_moving_slow_anim = abs(vel_x) < 0.5 # Threshold for considering "no movement"

            nm_variant = f"{base_key}_nm"
            moving_variant = base_key

            if not is_intentionally_moving_lr_anim and is_actually_moving_slow_anim and animations and animations.get(nm_variant):
                return nm_variant
            elif animations and animations.get(moving_variant): # Fallback to moving variant if NM not available or conditions not met
                return moving_variant
            # If neither, one more fallback if nm variant was primary
            elif animations and animations.get(nm_variant) and not animations.get(moving_variant):
                return nm_variant
            else: # Fallback to idle if attack anims are missing
                return 'idle'
    
    # --- Other Action States (Dash, Roll, Slide, Turn) ---
    # These are typically driven by the logical player.state
    if current_logical_state in ['dash', 'roll', 'slide', 'slide_trans_start', 'slide_trans_end', 'turn', 'crouch_trans']:
        return current_logical_state if animations and animations.get(current_logical_state) else 'idle' # Fallback to idle

    # --- Contextual Movement (Ladder, Wall Interactions) ---
    if on_ladder:
        return 'ladder_climb' if abs(vel_y) > 0.1 else 'ladder_idle'
    
    if touching_wall != 0 and not on_ground: # Player is against a wall and airborne
        if current_logical_state == 'wall_slide': # Specific state for sliding down
            return 'wall_slide' if animations and animations.get('wall_slide') else 'fall'
        # No 'wall_climb' logic as it was removed from player.py
        # If player is just touching a wall airborne but not sliding, it's usually 'fall' or 'jump'
    
    # --- Basic Movement & Idle (Jump, Fall, Run, Crouch, Idle) ---
    if not on_ground: # Airborne
        if current_logical_state == 'jump': # Just jumped
            return 'jump' if animations and animations.get('jump') else 'fall'
        if current_logical_state == 'jump_fall_trans': # Transitioning from jump to fall
            return 'jump_fall_trans' if animations and animations.get('jump_fall_trans') else 'fall'
        # Default airborne state if not jumping or wall interacting
        return 'fall' if animations and animations.get('fall') else 'idle' # Fallback to idle if no fall anim
    
    # On Ground
    if is_crouching:
        player_is_intending_to_move_lr_crouch = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
        key_variant = 'crouch_walk' if player_is_intending_to_move_lr_crouch else 'crouch'
        return key_variant if animations and animations.get(key_variant) else \
               ('crouch' if animations and animations.get('crouch') else 'idle') # Fallback

    player_is_intending_to_move_lr_stand = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)
    if player_is_intending_to_move_lr_stand:
        return 'run' if animations and animations.get('run') else 'idle' # Fallback

    # Default to idle if on ground and not moving/crouching/acting
    return 'idle' if animations and animations.get('idle') else 'idle' # Ensure 'idle' is always a valid fallback.


def advance_frame_and_handle_state_transitions(player: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    if not current_animation_frames_list: return

    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    # --- Static Frame States (Petrified, Frozen, Smashed - end frame) ---
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0; return # Petrified holds frame 0
    if player.is_frozen:
        player.current_frame = 0 # Frozen holds frame 0 (or last frame if 'frozen' is an animation)
        if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen':
            player.current_frame = len(current_animation_frames_list) -1
        return
    if player.is_stone_smashed and player.death_animation_finished: # Smashed and animation done
        player.current_frame = len(current_animation_frames_list) - 1 if current_animation_frames_list else 0
        return

    # --- Frame Advancement Logic ---
    can_advance_frame = not (player.is_dead and player.death_animation_finished and not player.is_petrified)

    if can_advance_frame and (current_time_ms - player.last_anim_update > ms_per_frame):
        player.last_anim_update = current_time_ms
        player.current_frame += 1

        if player.current_frame >= len(current_animation_frames_list):
            # Handle end of non-looping animations
            if player.is_dead and not player.is_petrified: # Normal death animation ended
                player.current_frame = len(current_animation_frames_list) - 1
                player.death_animation_finished = True; return
            elif player.is_stone_smashed: # Smashed animation (might loop or hold last frame based on needs)
                player.current_frame = len(current_animation_frames_list) - 1
                # player.death_animation_finished might be set by update_status_effects based on timer
                return

            # Non-looping animations that transition to other states
            non_looping_anim_keys_with_transitions = [
                'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end'
            ]
            # Animations that hold their last frame after finishing once
            non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost', 'aflame', 'aflame_crouch'] # Aflame transitions to burning, but initial anim might just play once

            is_transitional_anim = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold_last_frame_anim = current_animation_key in non_looping_hold_last_frame_keys

            if is_transitional_anim:
                next_state = player.state # Default to current logical state if no specific transition
                player_is_intending_to_move_lr = getattr(player, 'is_trying_to_move_left', False) or getattr(player, 'is_trying_to_move_right', False)

                if current_animation_key == 'jump':
                    next_state = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans':
                    next_state = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False # Hit stun duration might still be active, but animation ends
                    if player.is_aflame: next_state = 'aflame_crouch' if player.is_crouching else 'aflame' # Or 'burning' if that's a distinct visual
                    elif player.is_deflaming: next_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                    else: next_state = 'idle' if player.on_ground and not player.on_ladder else 'fall'
                elif current_animation_key == 'turn':
                    next_state = 'run' if player_is_intending_to_move_lr else 'idle'
                elif 'attack' in current_animation_key:
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    if player.on_ladder: next_state = 'ladder_idle'
                    elif player.is_crouching: next_state = 'crouch'
                    elif not player.on_ground: next_state = 'fall'
                    else: next_state = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_trans':
                    next_state = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                    player.is_sliding = False
                    next_state = 'crouch' if player.is_holding_crouch_ability_key or player.is_crouching else 'idle'
                elif current_animation_key == 'slide_trans_start':
                    next_state = 'slide'
                elif current_animation_key == 'dash': player.is_dashing = False; next_state = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll': player.is_rolling = False; next_state = 'idle' if player.on_ground else 'fall'

                # Only set state if the animation key matched the current logical state
                # AND the determined next state is different.
                # This avoids state flapping if, e.g., player.state was already 'fall' but 'jump' anim finished.
                if player.state == current_animation_key and next_state != player.state:
                    # Pass current time to set_player_state
                    set_player_state(player, next_state, get_current_ticks_monotonic())
                    return # State changed, animation will be re-evaluated next frame
                else: # If no state transition, loop or hold this animation's first frame
                    player.current_frame = 0
            
            elif is_hold_last_frame_anim:
                player.current_frame = len(current_animation_frames_list) - 1
                # For 'aflame' type animations, the logical state might change to 'burning'
                # which is handled by player_status_effects or set_player_state.
                # Here, we just ensure the visual holds.
                if current_animation_key == 'aflame' and not player.is_deflaming:
                     # If 'aflame' animation finishes, and player is still logically aflame,
                     # they might transition to a 'burning' (looping) visual state.
                     # This assumes player_state_handler or status_effects handles this logic.
                     # For now, just hold frame. If 'burning' is a different animation, this needs adjustment.
                     pass
            
            else: # Default: Loop animation
                player.current_frame = 0
    
    # Final safeguard for frame index
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

    # Determine if animation should proceed
    can_animate_now = (hasattr(player, 'alive') and player.alive()) or \
                      (getattr(player, 'is_dead', False) and not getattr(player, 'death_animation_finished', True) and not getattr(player, 'is_petrified', False)) or \
                      getattr(player, 'is_petrified', False) # Petrified players (stone/smashed) animate

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic()
    determined_key_for_logic = determine_animation_key(player) # Key based on current logical state

    current_frames_list: Optional[List[QPixmap]] = None
    # --- Get frames based on determined_key_for_logic ---
    if determined_key_for_logic == 'petrified':
        current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_key_for_logic == 'smashed':
        current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations: # Regular animations from player's sheet
        current_frames_list = player.animations.get(determined_key_for_logic)

    # --- Validate frames, fallback to 'idle' if necessary ---
    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    elif len(current_frames_list) == 1 and \
         determined_key_for_logic not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'crouch', 'ladder_idle', 'wall_hang']: # Static states can be 1 frame
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40): # Check for placeholder size
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue:
                    is_current_animation_valid = False

    if not is_current_animation_valid:
        if determined_key_for_logic != 'idle':
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_frames_missing_final_{player.player_id}_{determined_key_for_logic}"):
                warning(f"PlayerAnimHandler Warning (P{player.player_id}): Animation for key '{determined_key_for_logic}' (State: {player.state}) missing/placeholder. Switching to 'idle'.")
        
        determined_key_for_logic = 'idle' # Update the key being processed
        current_frames_list = player.animations.get('idle') if player.animations else None

        is_idle_still_invalid = not current_frames_list or \
                                not current_frames_list[0] or \
                                current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and \
                                 current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))
        if is_idle_still_invalid:
            critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta)
            return

    if not current_frames_list: # Should be caught by above, but as a safeguard
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_blue); return

    # --- Advance frame and handle state transitions based on animation end ---
    advance_frame_and_handle_state_transitions(player, current_frames_list, current_time_ms, determined_key_for_logic)

    # --- Re-determine animation key if logical state changed during advance_frame ---
    # This ensures the final image rendered matches the most up-to-date state.
    render_key_for_final_image = determined_key_for_logic
    current_player_logical_state_after_advance = getattr(player, 'state', 'idle')
    
    if current_player_logical_state_after_advance != determined_key_for_logic and \
       not (getattr(player, 'is_petrified', False) and determined_key_for_logic in ['petrified', 'smashed']): # Don't re-eval if petrified

        new_render_key_candidate = determine_animation_key(player) # Re-determine based on potentially new state
        if new_render_key_candidate != determined_key_for_logic:
            render_key_for_final_image = new_render_key_candidate
            # Update current_frames_list based on the new render_key for the final image selection
            if render_key_for_final_image == 'petrified':
                current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_key_for_final_image == 'smashed':
                current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations:
                new_frames_for_render = player.animations.get(render_key_for_final_image)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                # If new render key is also invalid, keep the current_frames_list from determined_key_for_logic (which was already validated or defaulted to idle)

    # --- Final Safeguard and Image Assignment ---
    if not current_frames_list or player.current_frame < 0 or player.current_frame >= len(current_frames_list):
        player.current_frame = 0 # Reset frame index if out of bounds
        if not current_frames_list: # Absolute fallback if list became empty (shouldn't happen with prior checks)
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0))))
            return

    image_for_this_frame = current_frames_list[player.current_frame]
    if image_for_this_frame.isNull(): # Should be caught earlier
        if hasattr(player, 'image') and player.image and not player.image.isNull(): player.image.fill(qcolor_magenta); return

    # Determine facing for visual display (petrified state uses facing_at_petrification)
    display_facing_right = player.facing_right
    if render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed':
        display_facing_right = player.facing_at_petrification

    final_image_to_set = image_for_this_frame
    if not display_facing_right: # Flip if facing left
        # Don't flip static stone images if they are pre-rendered for one direction
        # (This check might be redundant if stone_image_frame itself is chosen based on facing_at_petrification)
        if not (render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed'):
            q_img = image_for_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            # else: final_image_to_set remains image_for_this_frame (original) if conversion fails

    # Check if image content or facing direction actually changed before updating
    # This avoids unnecessary QPixmap object creation and rect updates.
    image_content_changed = (not hasattr(player, 'image') or player.image is None) or \
                            (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (player.image is not final_image_to_set) # Fallback direct QPixmap object comparison

    if image_content_changed or (getattr(player, '_last_facing_right_visual_for_anim', True) != display_facing_right):
        # Store midbottom to re-anchor after image change if height differs
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom()) if hasattr(player, 'rect') and player.rect else player.pos

        player.image = final_image_to_set
        # _update_rect_from_image_and_pos must exist on player and handle QPointF
        if hasattr(player, '_update_rect_from_image_and_pos') and callable(player._update_rect_from_image_and_pos):
            player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else: # Fallback if method missing (should not happen if player.py is refactored)
            player.rect = QRectF(old_rect_midbottom_qpointf - QPointF(player.image.width()/2.0, float(player.image.height())),
                                 player.image.size())

        player._last_facing_right_visual_for_anim = display_facing_right # Store the visual facing direction used for animation