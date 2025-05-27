# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Enemy instances using PySide6.
Includes zapped animation.
"""
# version 2.0.3 (Added zapped animation, local import for state_handler)

import time
from typing import List, Optional, Any # Added Any

from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

import constants as C
# Removed: from utils import PrintLimiter (not used directly in this version)

# Logger
from logger import debug, warning, critical # Use global logger

# DO NOT do top-level import of enemy_state_handler here
# try:
# from enemy_state_handler import set_enemy_state
# except ImportError:
#    ... fallback

_start_time_enemy_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_anim_monotonic) * 1000)


def determine_enemy_animation_key(enemy: Any) -> str:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    current_state = getattr(enemy, 'state', 'idle')
    vel_x = getattr(getattr(enemy, 'vel', None), 'x', lambda: 0.0)()
    vel_y = getattr(getattr(enemy, 'vel', None), 'y', lambda: 0.0)()

    # --- Highest Priority: Terminal/Overriding Visual States ---
    if getattr(enemy, 'is_petrified', False):
        return 'smashed' if getattr(enemy, 'is_stone_smashed', False) else 'petrified'
    if getattr(enemy, 'is_dead', False):
        if getattr(enemy, 'is_stomp_dying', False): return 'stomp_death'
        is_still_nm = abs(vel_x) < 0.1 and abs(vel_y) < 0.1
        key_variant = 'death_nm' if is_still_nm and hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('death_nm') else 'death'
        return key_variant if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(key_variant) else \
               ('death' if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('death') else 'idle')

    # --- Next Priority: Other Major Status Effects ---
    if getattr(enemy, 'is_zapped', False): return 'zapped' # New zapped state
    if getattr(enemy, 'is_aflame', False): return 'aflame'
    if getattr(enemy, 'is_deflaming', False): return 'deflame'
    if getattr(enemy, 'is_frozen', False): return 'frozen'
    if getattr(enemy, 'is_defrosting', False): return 'defrost'

    # --- Action States ---
    if current_state == 'hit': return 'hit'

    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       get_current_ticks_monotonic() < enemy.post_attack_pause_timer:
        return 'idle'

    if getattr(enemy, 'is_attacking', False):
        if 'attack' in current_state and hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(current_state):
            return current_state # e.g. if state is already 'attack_nm'
        # Fallback to determine attack animation if current_state isn't specific enough
        default_attack_key = 'attack_nm' if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('attack_nm') else 'attack'
        return default_attack_key if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(default_attack_key) else 'idle'

    # --- Movement States based on AI and Physics ---
    ai_state = getattr(enemy, 'ai_state', 'patrolling')
    if ai_state == 'chasing' or (ai_state == 'patrolling' and abs(vel_x) > 0.1):
        return 'run'
    if ai_state == 'patrolling' and abs(vel_x) <= 0.1: # Patrolling but stopped (e.g. at target)
        return 'idle'

    # Fallback to current logical state if it has a direct animation
    if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(current_state):
        return current_state

    # Absolute fallback
    warning(f"ENEMY_ANIM_HANDLER Warning (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
            f"Could not determine specific animation for logical state '{current_state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    # LOCAL IMPORT for set_enemy_state
    try:
        from enemy_state_handler import set_enemy_state
    except ImportError:
        critical("ENEMY_ANIM_HANDLER (advance_frame): Failed to import set_enemy_state locally.")
        def set_enemy_state(enemy_arg: Any, new_state_arg: str): pass # Fallback dummy

    if not current_animation_frames_list: return

    animation_frame_duration_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 100))

    # Static frames for certain states
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        enemy.current_frame = 0; return
    if getattr(enemy, 'is_stomp_dying', False): # Stomp death visuals handled by status_effects
        return
    if getattr(enemy, 'is_frozen', False): # Frozen holds frame
        enemy.current_frame = 0 # Or last frame of 'frozen' if it's multi-frame
        if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen':
            enemy.current_frame = len(current_animation_frames_list) -1
        return
    if getattr(enemy, 'is_zapped', False): # Zapped might have its own anim loop or hold
        # If zapped is a looping animation:
        if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
            enemy.last_anim_update = current_time_ms
            enemy.current_frame = (enemy.current_frame + 1) % len(current_animation_frames_list)
        return


    # Frame advancement for other animations
    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            # Handle end of animation
            is_dead_no_petri_no_stomp = getattr(enemy, 'is_dead', False) and \
                                        not getattr(enemy, 'is_petrified', False) and \
                                        not getattr(enemy, 'is_stomp_dying', False)
            is_petrified_and_smashed = getattr(enemy, 'is_petrified', False) and \
                                       getattr(enemy, 'is_stone_smashed', False)

            if is_dead_no_petri_no_stomp or is_petrified_and_smashed:
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True; return
            elif current_animation_key == 'hit':
                set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall'); return
            elif 'attack' in current_animation_key:
                # Attack animation finished, state transition handled by AI or state timer
                enemy.current_frame = 0 # Could loop attack anim or transition (AI decides)
            elif current_animation_key in ['deflame', 'defrost']: # Hold last frame
                enemy.current_frame = len(current_animation_frames_list) - 1
            else: # Default: Loop animation
                enemy.current_frame = 0

    # Safeguard frame index
    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy: Any):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))

    if not getattr(enemy, '_valid_init', False) or not hasattr(enemy, 'animations') or not enemy.animations:
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(qcolor_magenta)
        return

    # Determine if animation should proceed
    can_animate_now = (hasattr(enemy, 'alive') and enemy.alive()) or \
                      (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
                      getattr(enemy, 'is_petrified', False) or \
                      getattr(enemy, 'is_zapped', False) # Zapped enemies animate

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic()
    determined_key = determine_enemy_animation_key(enemy)

    current_frames_list: Optional[List[QPixmap]] = None
    # --- Get frames based on determined key ---
    if determined_key == 'petrified':
        stone_frame = getattr(enemy, 'stone_image_frame', None)
        current_frames_list = [stone_frame] if stone_frame and not stone_frame.isNull() else []
    elif determined_key == 'smashed':
        current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
    elif determined_key == 'stomp_death':
        # Stomp death visual scaling is handled in status_effects, use original image as base
        stomp_img = getattr(enemy, 'original_stomp_death_image', None)
        current_frames_list = [stomp_img] if stomp_img and not stomp_img.isNull() else \
                              (enemy.animations.get('idle', []) if enemy.animations else [])
    elif enemy.animations:
        current_frames_list = enemy.animations.get(determined_key)

    # --- Validate frames, fallback to 'idle' if necessary ---
    animation_is_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        animation_is_valid = False
    # Check if it's a placeholder (red/blue 30x40 rect) for non-static states
    elif len(current_frames_list) == 1 and \
         determined_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'stomp_death', 'zapped']:
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40):
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue:
                    animation_is_valid = False

    if not animation_is_valid:
        if determined_key != 'idle':
             warning(f"ENEMY_ANIM_HANDLER Warning (ID: {getattr(enemy, 'enemy_id', 'N/A')}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
                   f"Animation for key '{determined_key}' (State: {getattr(enemy, 'state', 'N/A')}) missing/placeholder. Switching to 'idle'.")
        determined_key = 'idle' # Update the key being processed
        current_frames_list = enemy.animations.get('idle') if enemy.animations else None

        is_idle_still_invalid = not current_frames_list or \
                                not current_frames_list[0] or \
                                current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and \
                                 current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))
        if is_idle_still_invalid:
            critical(f"ENEMY_ANIM_HANDLER CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta)
            return

    if not current_frames_list: # Should be caught by above, but as a safeguard
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_blue); return

    # --- Advance frame and handle state transitions based on animation end ---
    # Stomp death visual scaling is special, don't advance frame here for it.
    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    # --- Re-determine animation key if logical state changed during advance_frame ---
    # This ensures the final image rendered matches the most up-to-date state.
    render_key_for_final_image = determined_key
    current_enemy_logical_state = getattr(enemy, 'state', 'idle')
    if current_enemy_logical_state != determined_key and \
       not (getattr(enemy, 'is_petrified', False) and determined_key in ['petrified', 'smashed']) and \
       determined_key != 'stomp_death':

        new_render_key_candidate = determine_enemy_animation_key(enemy)
        if new_render_key_candidate != determined_key:
            render_key_for_final_image = new_render_key_candidate
            # Update current_frames_list based on the new render_key
            if render_key_for_final_image == 'petrified':
                stone_frame_render = getattr(enemy, 'stone_image_frame', None)
                current_frames_list = [stone_frame_render] if stone_frame_render and not stone_frame_render.isNull() else []
            elif render_key_for_final_image == 'smashed':
                current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
            # Stomp death handled separately.
            elif enemy.animations:
                new_frames_for_render = enemy.animations.get(render_key_for_final_image, [])
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                elif not (current_frames_list and current_frames_list[0] and not current_frames_list[0].isNull()): # If previous was also bad
                    current_frames_list = enemy.animations.get('idle', [enemy.image] if enemy.image and not enemy.image.isNull() else [])

    # --- Final Safeguard and Image Assignment ---
    if determined_key == 'stomp_death': # Visuals handled by status_effects squash logic
        return

    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0 # Reset frame index if out of bounds
        if not current_frames_list: # Absolute fallback if list became empty
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_yellow); return

    image_this_frame = current_frames_list[enemy.current_frame]
    if image_this_frame.isNull(): # Should be caught earlier
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta); return

    # Determine facing for visual display
    display_facing_right = getattr(enemy, 'facing_right', True)
    if render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed':
        display_facing_right = getattr(enemy, 'facing_at_petrification', True)

    final_image_to_set = image_this_frame
    if not display_facing_right: # Flip if facing left
        # Don't flip static stone images here if they are pre-rendered for one direction
        if not (render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed'):
            q_img = image_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            # else: final_image_to_set remains original if conversion fails

    # Check if image content or facing direction actually changed before updating
    image_content_changed = (not hasattr(enemy, 'image') or enemy.image is None) or \
                            (hasattr(enemy.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             enemy.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (enemy.image is not final_image_to_set) # Fallback direct comparison

    if image_content_changed or getattr(enemy, '_last_facing_right_visual', None) != display_facing_right:
        # Store midbottom to re-anchor after image change if height differs
        old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else None

        enemy.image = final_image_to_set
        if hasattr(enemy, '_update_rect_from_image_and_pos'):
            enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)

        enemy._last_facing_right_visual = display_facing_right # Store the visual facing direction