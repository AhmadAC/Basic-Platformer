# enemy/enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Enemy instances using PySide6.
Includes zapped animation.
MODIFIED: Added check for empty current_animation_frames_list in advance_enemy_frame_and_handle_transitions.
MODIFIED: Refined placeholder check and fallback logic in update_enemy_animation.
MODIFIED: Improved robustness for missing 'idle' animation and other animations.
MODIFIED: Ensure _last_facing_right_visual is initialized in EnemyBase, and checked here.
MODIFIED: Changed local import of set_enemy_state to use enemy.set_state() method.
"""
# version 2.0.5 (Use enemy.set_state() method)

import time
import sys
import os # Not strictly needed for this file's logic, but often included.
from typing import List, Optional, Any

from PySide6.QtGui import QPixmap, QImage, QTransform, QColor, QFont # Added QFont for potential placeholder text
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

import main_game.constants as C

# Logger
try:
    from main_game.logger import debug, warning, critical
except ImportError:
    print("CRITICAL ENEMY_ANIM_HANDLER: Failed to import logger.")
    # Basic fallback logger
    def debug(msg, *args, **kwargs): print(f"DEBUG_EANIM: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_EANIM: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_EANIM: {msg}")

_start_time_enemy_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_anim_monotonic) * 1000)


def determine_enemy_animation_key(enemy: Any) -> str:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    current_state = getattr(enemy, 'state', 'idle')
    # Safely get velocities, defaulting to 0 if attributes are missing
    vel_x = 0.0
    if hasattr(enemy, 'vel') and enemy.vel is not None and hasattr(enemy.vel, 'x') and callable(enemy.vel.x):
        vel_x = enemy.vel.x()
    vel_y = 0.0
    if hasattr(enemy, 'vel') and enemy.vel is not None and hasattr(enemy.vel, 'y') and callable(enemy.vel.y):
        vel_y = enemy.vel.y()
    
    animations_dict = getattr(enemy, 'animations', None)
    animations_available = isinstance(animations_dict, dict) and animations_dict

    # --- Highest Priority: Terminal/Overriding Visual States ---
    if getattr(enemy, 'is_petrified', False):
        return 'smashed' if getattr(enemy, 'is_stone_smashed', False) else 'petrified'
    if getattr(enemy, 'is_dead', False):
        if getattr(enemy, 'is_stomp_dying', False): return 'stomp_death'
        is_still_nm = abs(vel_x) < 0.1 and abs(vel_y) < 0.1
        death_nm_exists = animations_available and enemy.animations.get('death_nm')
        death_exists = animations_available and enemy.animations.get('death')
        
        key_variant = 'death_nm' if is_still_nm and death_nm_exists else 'death'
        if animations_available and enemy.animations.get(key_variant): return key_variant
        if death_exists: return 'death'
        return 'idle' # Fallback if no death animations

    # --- Next Priority: Other Major Status Effects ---
    if getattr(enemy, 'is_zapped', False): return 'zapped' if animations_available and animations_available.get('zapped') else 'idle'
    if getattr(enemy, 'is_aflame', False): return 'aflame' if animations_available and animations_available.get('aflame') else 'idle'
    if getattr(enemy, 'is_deflaming', False): return 'deflame' if animations_available and animations_available.get('deflame') else \
                                               ('aflame' if animations_available and animations_available.get('aflame') else 'idle') # Fallback to aflame if deflame missing
    if getattr(enemy, 'is_frozen', False): return 'frozen' if animations_available and animations_available.get('frozen') else 'idle'
    if getattr(enemy, 'is_defrosting', False): return 'defrost' if animations_available and animations_available.get('defrost') else \
                             ('frozen' if animations_available and animations_available.get('frozen') else 'idle')

    # --- Action States ---
    if current_state == 'hit': return 'hit' if animations_available and animations_available.get('hit') else 'idle'

    # Post-attack pause check
    post_attack_pause_timer_val = getattr(enemy, 'post_attack_pause_timer', 0)
    if post_attack_pause_timer_val > 0 and get_current_ticks_monotonic() < post_attack_pause_timer_val:
        return 'idle'

    # Attacking state
    if getattr(enemy, 'is_attacking', False):
        if 'attack' in current_state and animations_available and animations_available.get(current_state):
            return current_state
        
        attack_nm_exists = animations_available and enemy.animations.get('attack_nm')
        attack_exists = animations_available and enemy.animations.get('attack')
        default_attack_key = 'attack_nm' if attack_nm_exists else 'attack'
        
        if animations_available and enemy.animations.get(default_attack_key):
            return default_attack_key
        return 'idle' # Fallback if no attack animations

    # --- Movement States based on AI and Physics ---
    ai_state = getattr(enemy, 'ai_state', 'patrolling')
    if enemy.__class__.__name__ == 'EnemyKnight' and getattr(enemy, '_is_mid_patrol_jump', False):
        return 'jump'
    
    if ai_state == 'chasing' or (ai_state == 'patrolling' and abs(vel_x) > 0.1):
        return 'run'
    if ai_state == 'patrolling' and abs(vel_x) <= 0.1:
        return 'idle'
    
    if not getattr(enemy, 'on_ground', True) and current_state not in ['jump', 'fall']:
        return 'fall'

    if animations_available and animations_available.get(current_state):
        return current_state

    warning(f"ENEMY_ANIM_HANDLER Warning (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
            f"Could not determine specific animation for logical state '{current_state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    # Removed local import of set_enemy_state. Will use enemy.set_state() instead.

    if not current_animation_frames_list or not current_animation_frames_list[0] or current_animation_frames_list[0].isNull():
        warning(f"EnemyAnimHandler: advance_frame called with empty/invalid frames_list for key '{current_animation_key}'. ID: {getattr(enemy, 'enemy_id', 'N/A')}")
        enemy.current_frame = 0
        return

    animation_frame_duration_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 100))

    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        enemy.current_frame = 0; return
    if getattr(enemy, 'is_stomp_dying', False): return
    if getattr(enemy, 'is_frozen', False):
        enemy.current_frame = len(current_animation_frames_list) - 1 if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen' else 0
        return
    if getattr(enemy, 'is_zapped', False):
        pass

    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            is_dead_not_petrified_not_stomp = getattr(enemy, 'is_dead', False) and \
                                        not getattr(enemy, 'is_petrified', False) and \
                                        not getattr(enemy, 'is_stomp_dying', False)
            is_petrified_and_smashed = getattr(enemy, 'is_petrified', False) and \
                                       getattr(enemy, 'is_stone_smashed', False)

            if is_dead_not_petrified_not_stomp or is_petrified_and_smashed:
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True
                return
            elif current_animation_key == 'hit':
                enemy.set_state('idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms) # USE enemy.set_state()
                return
            elif 'attack' in current_animation_key:
                enemy.current_frame = 0
            elif current_animation_key in ['deflame', 'defrost']:
                enemy.current_frame = len(current_animation_frames_list) - 1
            elif current_animation_key == 'jump':
                enemy.current_frame = len(current_animation_frames_list) - 1
            else:
                enemy.current_frame = 0

    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy: Any):
    if not getattr(enemy, '_valid_init', False) or not hasattr(enemy, 'animations') or not enemy.animations:
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(QColor(*getattr(C, 'MAGENTA', (255,0,255))))
        return

    can_animate_now = (hasattr(enemy, 'alive') and enemy.alive()) or \
                      (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
                      getattr(enemy, 'is_petrified', False) or \
                      getattr(enemy, 'is_zapped', False)

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic()
    determined_key = determine_enemy_animation_key(enemy)

    current_frames_list: Optional[List[QPixmap]] = None
    animations_dict = getattr(enemy, 'animations', None) # Re-fetch for safety

    if determined_key == 'petrified':
        stone_frame = getattr(enemy, 'stone_image_frame', None)
        current_frames_list = [stone_frame] if stone_frame and not stone_frame.isNull() else []
    elif determined_key == 'smashed':
        current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
    elif determined_key == 'stomp_death':
        stomp_img = getattr(enemy, 'original_stomp_death_image', None)
        current_frames_list = [stomp_img] if stomp_img and not stomp_img.isNull() else \
                              (animations_dict.get('idle', []) if animations_dict else [])
    elif animations_dict:
        current_frames_list = animations_dict.get(determined_key)

    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    elif len(current_frames_list) == 1 and \
         determined_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'stomp_death', 'zapped', 'jump']:
        frame_pixmap = current_frames_list[0]
        qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
        qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255)))) # Corrected QColor init
        if frame_pixmap.size() == QSize(30, 40):
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue:
                    is_current_animation_valid = False

    if not is_current_animation_valid:
        original_determined_key_before_fallback = determined_key
        if determined_key != 'idle':
            warning(f"EnemyAnimHandler (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Anim for key '{determined_key}' (State: {getattr(enemy, 'state', 'N/A')}) missing/placeholder. Using 'idle'.")
        determined_key = 'idle'
        current_frames_list = animations_dict.get('idle') if animations_dict else None

        is_idle_still_invalid = not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))

        if is_idle_still_invalid:
            critical(f"EnemyAnimHandler CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Fallback 'idle' ALSO missing/invalid! Enemy visuals broken. Original key was '{original_determined_key_before_fallback}'.")
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
                enemy.image.fill(QColor(*getattr(C, 'MAGENTA', (255,0,255))))
            return

    if not current_frames_list:
        critical(f"EnemyAnimHandler CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): current_frames_list is None even after fallbacks. Key: '{determined_key}'.")
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(QColor(*(getattr(C, 'BLUE', (0,0,255))))) # Corrected QColor init
        return

    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    render_key_for_final_image = determined_key
    current_enemy_logical_state_after_advance = getattr(enemy, 'state', 'idle')
    if current_enemy_logical_state_after_advance != determined_key and \
       not (getattr(enemy, 'is_petrified', False) and determined_key in ['petrified', 'smashed']) and \
       determined_key != 'stomp_death':
        new_render_key_candidate = determine_enemy_animation_key(enemy)
        if new_render_key_candidate != determined_key:
            render_key_for_final_image = new_render_key_candidate
            if render_key_for_final_image == 'petrified':
                stone_frame_render = getattr(enemy, 'stone_image_frame', None)
                current_frames_list = [stone_frame_render] if stone_frame_render and not stone_frame_render.isNull() else []
            elif render_key_for_final_image == 'smashed':
                current_frames_list = getattr(enemy, 'stone_smashed_frames', [])
            elif animations_dict:
                new_frames_for_render = animations_dict.get(render_key_for_final_image)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                elif not (current_frames_list and current_frames_list[0] and not current_frames_list[0].isNull()):
                    current_frames_list = animations_dict.get('idle', [enemy.image] if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull() else [])

    if determined_key == 'stomp_death': return

    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0
        if not current_frames_list:
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
                enemy.image.fill(QColor(*(getattr(C, 'YELLOW', (255,255,0)))))
            return

    image_this_frame = current_frames_list[enemy.current_frame]
    if image_this_frame.isNull():
        critical(f"EnemyAnimHandler (ID: {getattr(enemy, 'enemy_id', 'N/A')}): image_this_frame is NULL for key '{render_key_for_final_image}', frame {enemy.current_frame}.")
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(QColor(*getattr(C, 'MAGENTA', (255,0,255))))
        return

    display_facing_right = getattr(enemy, 'facing_right', True)
    if render_key_for_final_image in ['petrified', 'smashed']:
        display_facing_right = getattr(enemy, 'facing_at_petrification', True)

    final_image_to_set = image_this_frame
    if not display_facing_right:
        if not (render_key_for_final_image in ['petrified', 'smashed']):
            q_img = image_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            
    image_content_has_changed = (not hasattr(enemy, 'image') or enemy.image is None) or \
                                (hasattr(enemy.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                                 enemy.image.cacheKey() != final_image_to_set.cacheKey()) or \
                                (enemy.image is not final_image_to_set)

    visual_facing_has_changed = getattr(enemy, '_last_facing_right_visual', None) != display_facing_right

    if image_content_has_changed or visual_facing_has_changed:
        old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else getattr(enemy, 'pos', None)
        
        enemy.image = final_image_to_set
        if hasattr(enemy, '_update_rect_from_image_and_pos'):
            enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
        
        enemy._last_facing_right_visual = display_facing_right