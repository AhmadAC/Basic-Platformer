# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Enemy instances using PySide6.
"""
# version 2.0.2 

import time # For monotonic timer
from typing import List, Optional

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

# Game imports
import constants as C

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'):
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL ENEMY_ANIM_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# --- Monotonic Timer ---
_start_time_enemy_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_anim_monotonic) * 1000)
# --- End Monotonic Timer ---


def determine_enemy_animation_key(enemy) -> str:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    # Ensure enemy.state and enemy.vel are accessible and have x, y for vel
    current_state = getattr(enemy, 'state', 'idle')
    vel_x = getattr(getattr(enemy, 'vel', None), 'x', lambda: 0.0)() # Call if method, access if property
    vel_y = getattr(getattr(enemy, 'vel', None), 'y', lambda: 0.0)()

    animation_key = current_state

    if getattr(enemy, 'is_petrified', False):
        return 'smashed' if getattr(enemy, 'is_stone_smashed', False) else 'petrified'
    if getattr(enemy, 'is_dead', False):
        if getattr(enemy, 'is_stomp_dying', False):
            return 'stomp_death'
        else:
            is_still_nm = abs(vel_x) < 0.1 and abs(vel_y) < 0.1
            key_variant = 'death_nm' if is_still_nm and hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('death_nm') else 'death'
            return key_variant if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(key_variant) else \
                   ('death' if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('death') else 'idle')

    if getattr(enemy, 'is_aflame', False): return 'aflame'
    if getattr(enemy, 'is_deflaming', False): return 'deflame'
    if getattr(enemy, 'is_frozen', False): return 'frozen'
    if getattr(enemy, 'is_defrosting', False): return 'defrost'
    if current_state == 'hit': return 'hit'

    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       get_current_ticks_monotonic() < enemy.post_attack_pause_timer: # Use monotonic timer
        return 'idle'

    if getattr(enemy, 'is_attacking', False):
        if 'attack' in current_state and hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(current_state):
            return current_state
        default_attack_key = 'attack_nm' if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get('attack_nm') else 'attack'
        return default_attack_key if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(default_attack_key) else 'idle'

    ai_state = getattr(enemy, 'ai_state', 'patrolling')
    if ai_state == 'chasing' or (ai_state == 'patrolling' and abs(vel_x) > 0.1):
        return 'run'
    if ai_state == 'patrolling' and abs(vel_x) <= 0.1:
        return 'idle'
    
    if not getattr(enemy, 'on_ground', False) and current_state not in ['jump', 'jump_fall_trans']:
        return 'fall'
    
    if hasattr(enemy, 'animations') and enemy.animations and enemy.animations.get(current_state):
        return current_state

    print(f"ENEMY_ANIM_HANDLER Warning (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
          f"Could not determine specific animation for logical state '{current_state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    if not current_animation_frames_list: return

    animation_frame_duration_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 100))

    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        enemy.current_frame = 0; return
    if getattr(enemy, 'is_stomp_dying', False): return

    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
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
                enemy.current_frame = 0 
            else: 
                enemy.current_frame = 0

    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))

    if not getattr(enemy, '_valid_init', False) or not hasattr(enemy, 'animations') or not enemy.animations:
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(qcolor_magenta)
        return

    if getattr(enemy, 'is_stomp_dying', False): return

    can_animate_now = (hasattr(enemy, 'alive') and enemy.alive()) or \
                      (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
                      getattr(enemy, 'is_petrified', False)

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic() # Use monotonic timer
    determined_key = determine_enemy_animation_key(enemy)
    
    current_frames_list: Optional[List[QPixmap]] = None
    if determined_key == 'petrified':
        stone_frame = getattr(enemy, 'stone_image_frame', None)
        current_frames_list = [stone_frame] if stone_frame and not stone_frame.isNull() else []
    elif determined_key == 'smashed':
        current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
    elif determined_key == 'stomp_death':
        stomp_img = getattr(enemy, 'original_stomp_death_image', None)
        current_frames_list = [stomp_img] if stomp_img and not stomp_img.isNull() else \
                              (enemy.animations.get('idle', []) if enemy.animations else [])
    elif enemy.animations:
        current_frames_list = enemy.animations.get(determined_key)

    animation_is_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        animation_is_valid = False
    elif len(current_frames_list) == 1 and determined_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'stomp_death']:
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40): 
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue: 
                    animation_is_valid = False

    if not animation_is_valid:
        if determined_key != 'idle':
             print(f"ENEMY_ANIM_HANDLER Warning (ID: {getattr(enemy, 'enemy_id', 'N/A')}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
                   f"Animation for key '{determined_key}' (State: {getattr(enemy, 'state', 'N/A')}) missing/placeholder. Switching to 'idle'.")
        determined_key = 'idle'
        current_frames_list = enemy.animations.get('idle') if enemy.animations else None
        
        is_idle_still_invalid = not current_frames_list or \
                                not current_frames_list[0] or \
                                current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and \
                                 current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))

        if is_idle_still_invalid:
            print(f"ENEMY_ANIM_HANDLER CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta)
            return

    if not current_frames_list: # Should be caught by above, but as a safeguard
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_blue); return

    if determined_key != 'stomp_death': # Stomp death scaling is handled elsewhere
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    # Re-determine animation key if state changed during advance_frame
    render_key = determined_key
    current_enemy_state = getattr(enemy, 'state', 'idle')
    if current_enemy_state != determined_key and \
       not (getattr(enemy, 'is_petrified', False) and determined_key in ['petrified', 'smashed']) and \
       determined_key != 'stomp_death':
        
        new_render_key = determine_enemy_animation_key(enemy) # Re-evaluate based on new state
        if new_render_key != determined_key:
            render_key = new_render_key
            # Update current_frames_list based on the new render_key
            if render_key == 'petrified':
                stone_frame_render = getattr(enemy, 'stone_image_frame', None)
                current_frames_list = [stone_frame_render] if stone_frame_render and not stone_frame_render.isNull() else []
            elif render_key == 'smashed':
                current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
            elif render_key == 'stomp_death': # Should not happen here if already handled
                stomp_img_render = getattr(enemy, 'original_stomp_death_image', None)
                current_frames_list = [stomp_img_render] if stomp_img_render and not stomp_img_render.isNull() else []
            elif enemy.animations:
                current_frames_list = enemy.animations.get(render_key, [])
            
            if not current_frames_list: # Still no valid frames after re-determination
                print(f"ENEMY_ANIM_HANDLER Warning (ID: {getattr(enemy, 'enemy_id', 'N/A')}): No frames for re-determined key '{render_key}'.")
                if hasattr(enemy, '_create_placeholder_qpixmap') and callable(enemy._create_placeholder_qpixmap):
                     enemy.image = enemy._create_placeholder_qpixmap(qcolor_yellow, "AnimErr")
                     if hasattr(enemy, 'pos') and hasattr(enemy, '_update_rect_from_image_and_pos'):
                         enemy._update_rect_from_image_and_pos()
                return

    if determined_key == 'stomp_death': return # Visuals handled by status_effects

    # Ensure current_frame is valid for the (potentially updated) current_frames_list
    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0
        if not current_frames_list: # Absolute fallback if list became empty
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_yellow); return

    image_this_frame = current_frames_list[enemy.current_frame]
    if image_this_frame.isNull():
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta); return

    display_facing_right = getattr(enemy, 'facing_right', True)
    if getattr(enemy, 'is_petrified', False): display_facing_right = getattr(enemy, 'facing_at_petrification', True)

    final_image_to_set = image_this_frame
    if not display_facing_right:
        if not (render_key == 'petrified' or render_key == 'smashed'): # Don't flip static stone images here
            q_img = image_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            # else: final_image_to_set remains original if conversion fails

    # Check if image content or facing direction actually changed before updating
    image_content_changed = (not hasattr(enemy, 'image') or enemy.image is None) or \
                            (hasattr(enemy.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             enemy.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (enemy.image is not final_image_to_set) # Fallback direct comparison
    
    if image_content_changed or getattr(enemy, '_last_facing_right', None) != display_facing_right:
        old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else None
        
        enemy.image = final_image_to_set
        if hasattr(enemy, '_update_rect_from_image_and_pos'):
            enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
        
        enemy._last_facing_right = display_facing_right