#################### START OF FILE: enemy_animation_handler.py ####################

# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Enemy instances using PySide6.
"""
# version 2.0.1 (PySide6 Refactor - Corrected enemy.current_frame usage)

from typing import List, Optional

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

# Game imports
import constants as C
# from utils import PrintLimiter # Assuming not used here, or import if needed

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'):
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL ENEMY_ANIM_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_anim = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_anim) * 1000)


def determine_enemy_animation_key(enemy) -> str:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    animation_key = enemy.state 

    if enemy.is_petrified:
        return 'smashed' if enemy.is_stone_smashed else 'petrified'
    if enemy.is_dead:
        if enemy.is_stomp_dying:
            return 'stomp_death' 
        else:
            is_still_nm = abs(enemy.vel.x()) < 0.1 and abs(enemy.vel.y()) < 0.1
            key_variant = 'death_nm' if is_still_nm and enemy.animations and enemy.animations.get('death_nm') else 'death'
            return key_variant if enemy.animations and enemy.animations.get(key_variant) else \
                   ('death' if enemy.animations and enemy.animations.get('death') else 'idle')

    if enemy.is_aflame: return 'aflame'
    if enemy.is_deflaming: return 'deflame'
    if enemy.is_frozen: return 'frozen'
    if enemy.is_defrosting: return 'defrost'
    if enemy.state == 'hit': return 'hit'

    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       get_current_ticks() < enemy.post_attack_pause_timer:
        return 'idle'

    if enemy.is_attacking:
        if 'attack' in enemy.state and enemy.animations and enemy.animations.get(enemy.state):
            return enemy.state
        default_attack_key = 'attack_nm' if enemy.animations and enemy.animations.get('attack_nm') else 'attack'
        return default_attack_key if enemy.animations and enemy.animations.get(default_attack_key) else 'idle'

    if enemy.ai_state == 'chasing' or (enemy.ai_state == 'patrolling' and abs(enemy.vel.x()) > 0.1):
        return 'run'
    if enemy.ai_state == 'patrolling' and abs(enemy.vel.x()) <= 0.1:
        return 'idle'
    
    if not enemy.on_ground and enemy.state not in ['jump', 'jump_fall_trans']:
        return 'fall'
    
    if enemy.animations and enemy.animations.get(enemy.state):
        return enemy.state

    print(f"ENEMY_ANIM_HANDLER Warning (ID: {enemy_id_log}, Color: {getattr(enemy, 'color_name', 'N/A')}): "
          f"Could not determine specific animation for logical state '{enemy.state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    if not current_animation_frames_list: return

    animation_frame_duration_ms = int(getattr(C, 'ANIM_FRAME_DURATION', 100))

    if enemy.is_petrified and not enemy.is_stone_smashed:
        enemy.current_frame = 0; return
    if enemy.is_stomp_dying: return

    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            if (enemy.is_dead and not enemy.is_petrified and not enemy.is_stomp_dying) or \
               (enemy.is_petrified and enemy.is_stone_smashed):
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True; return
            elif current_animation_key == 'hit':
                set_enemy_state(enemy, 'idle' if enemy.on_ground else 'fall'); return
            elif 'attack' in current_animation_key:
                enemy.current_frame = 0 
            else: 
                enemy.current_frame = 0

    # Corrected: Use enemy.current_frame instead of player.current_frame
    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))


    if not enemy._valid_init or not hasattr(enemy, 'animations') or not enemy.animations:
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
            enemy.image.fill(qcolor_magenta)
        return

    if enemy.is_stomp_dying: return

    can_animate_now = enemy.alive() or \
                      (enemy.is_dead and not enemy.death_animation_finished) or \
                      enemy.is_petrified

    if not can_animate_now: return

    current_time_ms = get_current_ticks()
    determined_key = determine_enemy_animation_key(enemy)
    
    current_frames_list: Optional[List[QPixmap]] = None
    if determined_key == 'petrified':
        current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame and not enemy.stone_image_frame.isNull() else []
    elif determined_key == 'smashed':
        current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
    elif determined_key == 'stomp_death': 
        current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image and not enemy.original_stomp_death_image.isNull() else \
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
                   f"Animation for key '{determined_key}' (State: {enemy.state}) missing/placeholder. Switching to 'idle'.")
        determined_key = 'idle'
        current_frames_list = enemy.animations.get('idle') if enemy.animations else None
        
        if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull() or \
           (len(current_frames_list) == 1 and current_frames_list[0].size() == QSize(30,40) and \
            (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
             current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue)):
            print(f"ENEMY_ANIM_HANDLER CRITICAL (ID: {getattr(enemy, 'enemy_id', 'N/A')}): Fallback 'idle' ALSO missing/placeholder! Visuals broken.")
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta)
            return

    if not current_frames_list: 
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_blue); return

    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    render_key = determined_key
    if enemy.state != determined_key and \
       not (enemy.is_petrified and determined_key in ['petrified', 'smashed']) and \
       determined_key != 'stomp_death':
        
        new_render_key = determine_enemy_animation_key(enemy)
        if new_render_key != determined_key:
            render_key = new_render_key
            if render_key == 'petrified': current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame and not enemy.stone_image_frame.isNull() else []
            elif render_key == 'smashed': current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
            elif render_key == 'stomp_death': current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image and not enemy.original_stomp_death_image.isNull() else []
            elif enemy.animations: current_frames_list = enemy.animations.get(render_key, [])
            
            if not current_frames_list:
                print(f"ENEMY_ANIM_HANDLER Warning (ID: {getattr(enemy, 'enemy_id', 'N/A')}): No frames for re-determined key '{render_key}'.")
                if not (hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull()):
                    enemy.image = enemy._create_placeholder_qpixmap(qcolor_yellow, "AnimErr") # Assuming _create_placeholder_qpixmap exists on enemy
                    if hasattr(enemy, 'pos') and hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
                return

    if determined_key == 'stomp_death': return 

    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0
        if not current_frames_list:
            if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_yellow); return

    image_this_frame = current_frames_list[enemy.current_frame]
    if image_this_frame.isNull():
        if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull(): enemy.image.fill(qcolor_magenta); return

    display_facing_right = enemy.facing_right
    if enemy.is_petrified: display_facing_right = enemy.facing_at_petrification

    final_image_to_set = image_this_frame
    if not display_facing_right:
        if not (render_key == 'petrified' or render_key == 'smashed'): 
            q_img = image_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))

    image_content_changed = (enemy.image is None) or \
                            (hasattr(enemy.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                             enemy.image.cacheKey() != final_image_to_set.cacheKey()) or \
                            (enemy.image is not final_image_to_set)
    
    if image_content_changed or enemy._last_facing_right != display_facing_right:
        old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom())
        
        enemy.image = final_image_to_set
        if hasattr(enemy, '_update_rect_from_image_and_pos'):
            enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
        
        enemy._last_facing_right = display_facing_right

#################### END OF FILE: enemy_animation_handler.py ####################