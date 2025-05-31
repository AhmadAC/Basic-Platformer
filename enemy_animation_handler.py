# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Enemy instances using PySide6.
Includes zapped animation.
MODIFIED: Added check for empty current_animation_frames_list in advance_enemy_frame_and_handle_transitions.
MODIFIED: Refined placeholder check and fallback logic in update_enemy_animation.
MODIFIED: Improved robustness for missing 'idle' animation and other animations.
MODIFIED: Ensure _last_facing_right_visual is initialized in EnemyBase, and checked here.
"""
# version 2.0.4 (Robustness for missing animations, placeholder checks)

import time
from typing import List, Optional, Any

from PySide6.QtGui import QPixmap, QImage, QTransform, QColor, QFont # Added QFont for potential placeholder text
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

import constants as C

# Logger
try:
    from logger import debug, warning, critical
except ImportError:
    print("CRITICAL ENEMY_ANIM_HANDLER: Failed to import logger.")
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
    
    animations_available = hasattr(enemy, 'animations') and enemy.animations is not None

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
    if getattr(enemy, 'is_zapped', False): return 'zapped'
    if getattr(enemy, 'is_aflame', False): return 'aflame'
    if getattr(enemy, 'is_deflaming', False): return 'deflame'
    if getattr(enemy, 'is_frozen', False): return 'frozen'
    if getattr(enemy, 'is_defrosting', False): return 'defrost'

    # --- Action States ---
    if current_state == 'hit': return 'hit'

    # Post-attack pause check
    post_attack_pause_timer_val = getattr(enemy, 'post_attack_pause_timer', 0)
    if post_attack_pause_timer_val > 0 and get_current_ticks_monotonic() < post_attack_pause_timer_val:
        return 'idle'

    # Attacking state
    if getattr(enemy, 'is_attacking', False):
        # EnemyKnight might set state to 'attack1', 'attack2', etc.
        # Generic enemy might set state to 'attack' or 'attack_nm'.
        # Try the current_state first if it's an attack variant and exists.
        if 'attack' in current_state and animations_available and enemy.animations.get(current_state):
            return current_state
        
        # Fallback for generic 'attack' or if current_state isn't specific enough
        attack_nm_exists = animations_available and enemy.animations.get('attack_nm')
        attack_exists = animations_available and enemy.animations.get('attack')
        default_attack_key = 'attack_nm' if attack_nm_exists else 'attack'
        
        if animations_available and enemy.animations.get(default_attack_key):
            return default_attack_key
        return 'idle' # Fallback if no attack animations

    # --- Movement States based on AI and Physics ---
    ai_state = getattr(enemy, 'ai_state', 'patrolling')
    # Check for Knight's jump state
    if enemy.__class__.__name__ == 'EnemyKnight' and getattr(enemy, '_is_mid_patrol_jump', False):
        return 'jump' # Knight uses 'jump' state for its patrol jump animation
    
    # Standard movement for non-jumping enemies or landed Knight
    if ai_state == 'chasing' or (ai_state == 'patrolling' and abs(vel_x) > 0.1):
        return 'run'
    if ai_state == 'patrolling' and abs(vel_x) <= 0.1: # Patrolling but stopped
        return 'idle'
    
    # If airborne and not in a specific jump/fall state, determine 'fall'
    if not getattr(enemy, 'on_ground', True) and current_state not in ['jump', 'fall']:
        return 'fall'

    # Fallback to current logical state if it has a direct animation and no other rule matched
    if animations_available and enemy.animations.get(current_state):
        return current_state

    # Absolute fallback
    warning(f"ENEMY_ANIM_HANDLER Warning (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
            f"Could not determine specific animation for logical state '{current_state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    try:
        from enemy_state_handler import set_enemy_state # Local import
    except ImportError:
        critical("ENEMY_ANIM_HANDLER (advance_frame): Failed to import set_enemy_state locally.")
        def set_enemy_state(enemy_arg: Any, new_state_arg: str, time_ms: Optional[int]=None): pass

    if not current_animation_frames_list or not current_animation_frames_list[0]: # Check if list is empty or first frame is bad
        warning(f"EnemyAnimHandler: advance_frame called with empty/invalid frames_list for key '{current_animation_key}'. ID: {getattr(enemy, 'enemy_id', 'N/A')}")
        enemy.current_frame = 0
        return

    animation_frame_duration_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 100))

    # --- Handle static or special-cased animations ---
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        enemy.current_frame = 0; return # Petrified (whole) holds first frame
    if getattr(enemy, 'is_stomp_dying', False): return # Stomp death visuals handled elsewhere
    if getattr(enemy, 'is_frozen', False):
        # Frozen holds last frame of 'frozen' animation if multi-frame, else first (0)
        enemy.current_frame = len(current_animation_frames_list) - 1 if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen' else 0
        return
    if getattr(enemy, 'is_zapped', False): # Zapped animation is a loop handled by frame advancement
        pass # Fall through to standard frame advancement

    # --- Standard Frame Advancement ---
    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            # --- Handle Animation End ---
            is_dead_not_petrified_not_stomp = getattr(enemy, 'is_dead', False) and \
                                        not getattr(enemy, 'is_petrified', False) and \
                                        not getattr(enemy, 'is_stomp_dying', False)
            is_petrified_and_smashed = getattr(enemy, 'is_petrified', False) and \
                                       getattr(enemy, 'is_stone_smashed', False)

            if is_dead_not_petrified_not_stomp or is_petrified_and_smashed:
                enemy.current_frame = len(current_animation_frames_list) - 1 # Hold last frame of death/smashed
                enemy.death_animation_finished = True
                return
            elif current_animation_key == 'hit':
                # Transition out of 'hit' state. state_handler should do this based on hit_duration.
                # This is a fallback if state handler missed it.
                set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms)
                return
            elif 'attack' in current_animation_key:
                # Attack animation finished. AI or state timer should transition state.
                # EnemyKnight's AI handles post-attack pause and cooldown.
                # Generic enemy AI also handles this.
                # For looping visual, set to 0. If it's meant to transition, AI handles it.
                enemy.current_frame = 0
            elif current_animation_key in ['deflame', 'defrost']: # Hold last frame of these transitions
                enemy.current_frame = len(current_animation_frames_list) - 1
            elif current_animation_key == 'jump': # For knight's jump
                # If still airborne, might loop jump anim or hold last frame.
                # If on_ground, AI/status_effects should transition state.
                # For a simple loop or hold last frame:
                enemy.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                # Or enemy.current_frame = 0 # Loop jump animation
            else: # Default: Loop animation
                enemy.current_frame = 0

    # Safeguard frame index again after logic
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
    determined_key = determine_enemy_animation_key(enemy) # This now considers Knight's jump

    current_frames_list: Optional[List[QPixmap]] = None
    # Get frames based on determined key
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

    # --- Validate frames, fallback to 'idle' if necessary ---
    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    # Placeholder check (red/blue 30x40 rect)
    elif len(current_frames_list) == 1 and \
         determined_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'stomp_death', 'zapped', 'jump']: # Added jump
        frame_pixmap = current_frames_list[0]
        qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
        qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
        if frame_pixmap.size() == QSize(30, 40): # Common placeholder size
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
        current_frames_list = enemy.animations.get('idle') if enemy.animations else None

        # Check if 'idle' itself is also invalid
        if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
            critical(f"EnemyAnimHandler CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Fallback 'idle' ALSO missing/invalid! Enemy visuals broken. Original key was '{original_determined_key_before_fallback}'.")
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
                enemy.image.fill(QColor(*getattr(C, 'MAGENTA', (255,0,255))))
            return # Cannot proceed if idle is broken

    if not current_frames_list: # Should be caught by above, but as a final safeguard
        critical(f"EnemyAnimHandler CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): current_frames_list is None even after fallbacks. Key: '{determined_key}'.")
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(QColor(*getattr(C, 'BLUE', (0,0,255))))
        return

    # Advance frame (except for stomp_death visual scaling)
    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    # Re-determine animation key if logical state might have changed during advance_frame
    # This is more for complex state transitions that might happen *within* an animation's end logic
    render_key_for_final_image = determined_key
    current_enemy_logical_state_after_advance = getattr(enemy, 'state', 'idle')
    if current_enemy_logical_state_after_advance != determined_key and \
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
            elif enemy.animations:
                new_frames_for_render = enemy.animations.get(render_key_for_final_image)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                elif not (current_frames_list and current_frames_list[0] and not current_frames_list[0].isNull()):
                    current_frames_list = enemy.animations.get('idle', [])

    # Final Safeguard and Image Assignment
    if determined_key == 'stomp_death': # Visuals handled by status_effects squash logic
        return # Do not set image here, status_effects handles it.

    # Re-check current_frames_list after potential re-determination.
    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0
        if not current_frames_list: # Absolute fallback if list became empty
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
                enemy.image.fill(QColor(*getattr(C, 'YELLOW', (255,255,0))))
            return

    image_this_frame = current_frames_list[enemy.current_frame]
    if image_this_frame.isNull(): # Should be caught earlier by validation
        critical(f"EnemyAnimHandler (ID: {getattr(enemy, 'enemy_id', 'N/A')}): image_this_frame is NULL for key '{render_key_for_final_image}', frame {enemy.current_frame}.")
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(QColor(*getattr(C, 'MAGENTA', (255,0,255))))
        return

    # Determine facing for visual display
    display_facing_right = getattr(enemy, 'facing_right', True)
    if render_key_for_final_image in ['petrified', 'smashed']:
        display_facing_right = getattr(enemy, 'facing_at_petrification', True)

    final_image_to_set = image_this_frame
    if not display_facing_right: # Flip if facing left
        # Don't flip static stone images here if they are pre-rendered for one direction
        if not (render_key_for_final_image in ['petrified', 'smashed']):
            q_img = image_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))

    # Check if image content or visual facing direction actually changed
    image_content_has_changed = (not hasattr(enemy, 'image') or enemy.image is None) or \
                                (hasattr(enemy.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                                 enemy.image.cacheKey() != final_image_to_set.cacheKey()) or \
                                (enemy.image is not final_image_to_set) # Direct ref check

    visual_facing_has_changed = getattr(enemy, '_last_facing_right_visual', None) != display_facing_right

    if image_content_has_changed or visual_facing_has_changed:
        old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else getattr(enemy, 'pos', None)
        
        enemy.image = final_image_to_set
        if hasattr(enemy, '_update_rect_from_image_and_pos'):
            enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
        
        enemy._last_facing_right_visual = display_facing_right # Store the visual facing