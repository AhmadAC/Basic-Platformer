# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects for enemies using PySide6.
"""
# version 2.0.1 (PySide6 Refactor - Added missing Any import)

from typing import List, Optional, Any, TYPE_CHECKING # Added TYPE_CHECKING

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, QSize, Qt

# Game imports
import constants as C
# from enemy import Enemy # For type hinting and isinstance checks # <--- REMOVE THIS LINE (Original line 18)

if TYPE_CHECKING:
    from enemy import Enemy # For type hinting and isinstance checks # <--- ADD THIS LINE

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'):
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL ENEMY_STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATUS_EFFECTS: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_status = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_status) * 1000)


# --- Functions to APPLY status effects ---

# Optionally, if type hints are desired for functions:
# def apply_aflame_effect(enemy: 'Enemy'):
def apply_aflame_effect(enemy): # Original signature
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or \
       enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False
    set_enemy_state(enemy, 'aflame')
    enemy.is_attacking = False; enemy.attack_type = 0

# def apply_freeze_effect(enemy: 'Enemy'):
def apply_freeze_effect(enemy): # Original signature
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_dead or \
       enemy.is_petrified or enemy.is_aflame or enemy.is_deflaming:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen')
    enemy.vel = QPointF(0,0); enemy.acc.setX(0.0) 
    enemy.is_attacking = False; enemy.attack_type = 0

# def petrify_enemy(enemy: 'Enemy'):
def petrify_enemy(enemy): # Original signature
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}) is being petrified.")
    enemy.facing_at_petrification = enemy.facing_right
    set_enemy_state(enemy, 'petrified')
    enemy.vel.setX(0.0); enemy.acc.setX(0.0) 

# def smash_petrified_enemy(enemy: 'Enemy'):
def smash_petrified_enemy(enemy): # Original signature
    if enemy.is_petrified and not enemy.is_stone_smashed:
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}) is being smashed.")
        set_enemy_state(enemy, 'smashed')
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but not in smashable state (Petrified: {enemy.is_petrified}, Smashed: {enemy.is_stone_smashed}).")

# def stomp_kill_enemy(enemy: 'Enemy'):
def stomp_kill_enemy(enemy): # Original signature
    if enemy.is_dead or enemy.is_stomp_dying or enemy.is_petrified or \
       enemy.is_aflame or enemy.is_frozen:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}): Stomp kill initiated.")
    
    enemy.is_stomp_dying = True
    enemy.stomp_death_start_time = get_current_ticks()
    enemy.original_stomp_facing_right = enemy.facing_right
    
    if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
        enemy.original_stomp_death_image = enemy.image.copy()
    else:
        w = enemy.rect.width() if hasattr(enemy, 'rect') and enemy.rect.width() > 0 else getattr(C, 'TILE_SIZE', 30)
        h = enemy.rect.height() if hasattr(enemy, 'rect') and enemy.rect.height() > 0 else int(getattr(C, 'TILE_SIZE', 30) * 1.5)
        enemy.original_stomp_death_image = QPixmap(int(w), int(h))
        enemy.original_stomp_death_image.fill(Qt.GlobalColor.transparent)
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Could not copy valid image for stomp; using transparent placeholder.")

    enemy.is_dead = True; enemy.current_health = 0
    enemy.vel = QPointF(0,0); enemy.acc = QPointF(0,0) 
    enemy.death_animation_finished = False 
    set_enemy_state(enemy, 'stomp_death')


# --- Function to UPDATE status effects ---

# def update_enemy_status_effects(enemy: 'Enemy', current_time_ms: int, platforms_list: List[Any]) -> bool:
def update_enemy_status_effects(enemy, current_time_ms: int, platforms_list: List[Any]) -> bool: # Original signature
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    an_effect_is_overriding_updates = False

    if enemy.is_stomp_dying:
        an_effect_is_overriding_updates = True
        elapsed_stomp_time = current_time_ms - enemy.stomp_death_start_time
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400)

        if elapsed_stomp_time >= stomp_squash_duration:
            if not enemy.death_animation_finished:
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ended.")
                enemy.death_animation_finished = True
            if enemy.alive(): enemy.kill()
        else:
            if enemy.original_stomp_death_image and not enemy.original_stomp_death_image.isNull():
                progress_ratio = elapsed_stomp_time / stomp_squash_duration
                scale_y_factor = 1.0 - progress_ratio
                
                original_width = enemy.original_stomp_death_image.width()
                original_height = enemy.original_stomp_death_image.height()
                
                new_height = max(1, int(original_height * scale_y_factor))
                new_width = original_width

                if new_width > 0 and new_height > 0:
                    base_image_to_scale = enemy.original_stomp_death_image.copy()
                    if not enemy.original_stomp_facing_right:
                        q_img = base_image_to_scale.toImage()
                        if not q_img.isNull():
                             base_image_to_scale = QPixmap.fromImage(q_img.mirrored(True, False))
                    
                    squashed_pixmap = base_image_to_scale.scaled(new_width, new_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom())
                    enemy.image = squashed_pixmap
                    if hasattr(enemy, '_update_rect_from_image_and_pos'):
                        enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
                else:
                    min_fallback_width = original_width if original_width > 0 else 1
                    enemy.image = QPixmap(min_fallback_width, 1)
                    enemy.image.fill(Qt.GlobalColor.transparent)
                    if hasattr(enemy, '_update_rect_from_image_and_pos'):
                         enemy._update_rect_from_image_and_pos()
            
            enemy.vel = QPointF(0,0); enemy.acc = QPointF(0,0)
            enemy.on_ground = True
        return an_effect_is_overriding_updates

    if enemy.is_stone_smashed:
        an_effect_is_overriding_updates = True
        if enemy.death_animation_finished or \
           (current_time_ms - enemy.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS):
            if enemy.alive(): enemy.kill()
        return an_effect_is_overriding_updates 

    if enemy.is_petrified:
        an_effect_is_overriding_updates = True
        if not enemy.on_ground:
            enemy.vel.setY(enemy.vel.y() + getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)))
            enemy.vel.setY(min(enemy.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
            enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
            if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            
            for platform_obj in platforms_list:
                 if hasattr(platform_obj, 'rect') and enemy.rect.intersects(platform_obj.rect):
                     if enemy.vel.y() > 0 and enemy.rect.bottom() > platform_obj.rect.top() and \
                        (enemy.pos.y() - enemy.vel.y()) <= platform_obj.rect.top() + 1:
                          enemy.rect.moveBottom(platform_obj.rect.top())
                          enemy.on_ground = True; enemy.vel.setY(0.0); enemy.acc.setY(0.0)
                          enemy.pos.setY(enemy.rect.bottom()); break
        return an_effect_is_overriding_updates

    processed_aflame_or_deflame_this_tick = False
    if enemy.is_aflame:
        processed_aflame_or_deflame_this_tick = True
        if current_time_ms - enemy.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
            set_enemy_state(enemy, 'deflame')
        elif current_time_ms - enemy.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'):
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms

    if enemy.is_deflaming:
        processed_aflame_or_deflame_this_tick = True
        if current_time_ms - enemy.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
            set_enemy_state(enemy, 'idle')

    if enemy.is_frozen:
        an_effect_is_overriding_updates = True
        enemy.vel = QPointF(0,0); enemy.acc.setX(0.0)
        if current_time_ms - enemy.frozen_effect_timer > C.ENEMY_FROZEN_DURATION_MS:
            set_enemy_state(enemy, 'defrost')
        return an_effect_is_overriding_updates 

    if enemy.is_defrosting:
        an_effect_is_overriding_updates = True
        enemy.vel = QPointF(0,0); enemy.acc.setX(0.0)
        if current_time_ms - enemy.frozen_effect_timer > (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            set_enemy_state(enemy, 'idle')
            return False
        return an_effect_is_overriding_updates 

    if enemy.is_dead:
        an_effect_is_overriding_updates = True
        if enemy.alive() and enemy.death_animation_finished:
            enemy.kill()
        return an_effect_is_overriding_updates 

    if processed_aflame_or_deflame_this_tick:
        return False 

    return False