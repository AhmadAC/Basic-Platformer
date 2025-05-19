# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects for enemies using PySide6.
"""
# version 2.0.2

import time # For monotonic timer
from typing import List, Optional, Any, TYPE_CHECKING

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, QSize, Qt

# Game imports
import constants as C

if TYPE_CHECKING:
    from enemy import Enemy # For type hinting

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

# --- Monotonic Timer ---
_start_time_enemy_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_status_monotonic) * 1000)
# --- End Monotonic Timer ---


# --- Functions to APPLY status effects ---

def apply_aflame_effect(enemy: 'Enemy'):
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or \
       enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False
    set_enemy_state(enemy, 'aflame')
    enemy.is_attacking = False; enemy.attack_type = 0

def apply_freeze_effect(enemy: 'Enemy'):
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_dead or \
       enemy.is_petrified or enemy.is_aflame or enemy.is_deflaming:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen')
    if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX') and hasattr(enemy.vel, 'setY'): # Check methods
        enemy.vel.setX(0.0); enemy.vel.setY(0.0)
    if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): # Check method
        enemy.acc.setX(0.0)
    enemy.is_attacking = False; enemy.attack_type = 0

def petrify_enemy(enemy: 'Enemy'):
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being petrified.")
    enemy.facing_at_petrification = enemy.facing_right
    set_enemy_state(enemy, 'petrified')
    if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'setX'): enemy.vel.setX(0.0)
    if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)

def smash_petrified_enemy(enemy: 'Enemy'):
    if enemy.is_petrified and not enemy.is_stone_smashed:
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being smashed.")
        set_enemy_state(enemy, 'smashed')
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but not in smashable state (Petrified: {enemy.is_petrified}, Smashed: {enemy.is_stone_smashed}).")

def stomp_kill_enemy(enemy: 'Enemy'):
    if enemy.is_dead or getattr(enemy, 'is_stomp_dying', False) or enemy.is_petrified or \
       enemy.is_aflame or enemy.is_frozen:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}): Stomp kill initiated.")
    
    enemy.is_stomp_dying = True
    enemy.stomp_death_start_time = get_current_ticks_monotonic() # Use monotonic timer
    enemy.original_stomp_facing_right = enemy.facing_right
    
    if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
        enemy.original_stomp_death_image = enemy.image.copy()
    else:
        rect_w = enemy.rect.width() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'width') and enemy.rect.width() > 0 else getattr(C, 'TILE_SIZE', 30.0)
        rect_h = enemy.rect.height() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'height') and enemy.rect.height() > 0 else int(getattr(C, 'TILE_SIZE', 30.0) * 1.5)
        enemy.original_stomp_death_image = QPixmap(int(rect_w), int(rect_h))
        enemy.original_stomp_death_image.fill(Qt.GlobalColor.transparent)
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Could not copy valid image for stomp; using transparent placeholder.")

    enemy.is_dead = True; enemy.current_health = 0
    if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0) # Ensure vel is QPointF if it exists
    if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0) # Ensure acc is QPointF
    enemy.death_animation_finished = False 
    set_enemy_state(enemy, 'stomp_death')


# --- Function to UPDATE status effects ---

def update_enemy_status_effects(enemy: 'Enemy', current_time_ms: int, platforms_list: List[Any]) -> bool:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    an_effect_is_overriding_updates = False

    # --- is_stomp_dying ---
    if getattr(enemy, 'is_stomp_dying', False):
        an_effect_is_overriding_updates = True
        elapsed_stomp_time = current_time_ms - getattr(enemy, 'stomp_death_start_time', current_time_ms)
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400)

        if elapsed_stomp_time >= stomp_squash_duration:
            if not getattr(enemy, 'death_animation_finished', True):
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ended.")
                enemy.death_animation_finished = True
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        else:
            original_stomp_image = getattr(enemy, 'original_stomp_death_image', None)
            if original_stomp_image and not original_stomp_image.isNull():
                progress_ratio = elapsed_stomp_time / stomp_squash_duration
                scale_y_factor = max(0.0, 1.0 - progress_ratio) # Ensure non-negative
                
                original_width = original_stomp_image.width()
                original_height = original_stomp_image.height()
                new_height = max(1, int(original_height * scale_y_factor))
                new_width = original_width

                if new_width > 0 and new_height > 0:
                    base_image_to_scale = original_stomp_image.copy()
                    if not getattr(enemy, 'original_stomp_facing_right', True):
                        q_img = base_image_to_scale.toImage()
                        if not q_img.isNull():
                             base_image_to_scale = QPixmap.fromImage(q_img.mirrored(True, False))
                    
                    squashed_pixmap = base_image_to_scale.scaled(new_width, new_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else None
                    enemy.image = squashed_pixmap
                    if hasattr(enemy, '_update_rect_from_image_and_pos'):
                        enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
                else: # Fallback if scaled dimensions become invalid
                    fallback_width = original_width if original_width > 0 else 1
                    enemy.image = QPixmap(fallback_width, 1); enemy.image.fill(Qt.GlobalColor.transparent)
                    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            
            if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
            if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
            enemy.on_ground = True # Stomped enemies are on ground
        return an_effect_is_overriding_updates

    # --- is_stone_smashed ---
    if getattr(enemy, 'is_stone_smashed', False):
        an_effect_is_overriding_updates = True
        if getattr(enemy, 'death_animation_finished', False) or \
           (current_time_ms - getattr(enemy, 'stone_smashed_timer_start', current_time_ms) > C.STONE_SMASHED_DURATION_MS):
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        return an_effect_is_overriding_updates 

    # --- is_petrified (but not smashed) ---
    if getattr(enemy, 'is_petrified', False): # Implicitly not smashed due to above block
        an_effect_is_overriding_updates = True
        if not getattr(enemy, 'on_ground', True): # If petrified and not on ground, apply gravity
            if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'y') and hasattr(enemy.vel, 'setY') and \
               hasattr(enemy, 'acc') and hasattr(enemy.acc, 'y'):
                enemy.vel.setY(enemy.vel.y() + getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)))
                enemy.vel.setY(min(enemy.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
            if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'y') and hasattr(enemy.pos, 'setY') and \
               hasattr(enemy, 'vel') and hasattr(enemy.vel, 'y'):
                enemy.pos.setY(enemy.pos.y() + enemy.vel.y())
            
            if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            
            # Simplified platform collision for falling petrified enemy
            for platform_obj in platforms_list:
                 if hasattr(platform_obj, 'rect') and hasattr(enemy, 'rect') and enemy.rect.intersects(platform_obj.rect):
                     if hasattr(enemy, 'vel') and enemy.vel.y() > 0 and enemy.rect.bottom() > platform_obj.rect.top() and \
                        hasattr(enemy, 'pos') and (enemy.pos.y() - enemy.vel.y()) <= platform_obj.rect.top() + 1: # Check if was above
                          enemy.rect.moveBottom(platform_obj.rect.top())
                          enemy.on_ground = True; enemy.vel.setY(0.0)
                          if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setY'): enemy.acc.setY(0.0)
                          if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'setY'): enemy.pos.setY(enemy.rect.bottom())
                          break
        return an_effect_is_overriding_updates

    # --- Aflame / Deflaming ---
    processed_aflame_or_deflame_this_tick = False
    if getattr(enemy, 'is_aflame', False):
        processed_aflame_or_deflame_this_tick = True
        an_effect_is_overriding_updates = True # Aflame overrides normal AI movement
        if current_time_ms - getattr(enemy, 'aflame_timer_start', current_time_ms) > C.ENEMY_AFLAME_DURATION_MS:
            set_enemy_state(enemy, 'deflame')
        elif current_time_ms - getattr(enemy, 'aflame_damage_last_tick', 0) > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'):
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms

    if getattr(enemy, 'is_deflaming', False):
        processed_aflame_or_deflame_this_tick = True
        an_effect_is_overriding_updates = True # Deflaming also overrides normal AI movement
        if current_time_ms - getattr(enemy, 'deflame_timer_start', current_time_ms) > C.ENEMY_DEFLAME_DURATION_MS:
            set_enemy_state(enemy, 'idle') # Transition to idle after deflaming

    # --- Frozen / Defrosting ---
    if getattr(enemy, 'is_frozen', False):
        an_effect_is_overriding_updates = True
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > C.ENEMY_FROZEN_DURATION_MS:
            set_enemy_state(enemy, 'defrost')
        return an_effect_is_overriding_updates 

    if getattr(enemy, 'is_defrosting', False):
        an_effect_is_overriding_updates = True
        if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
        if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setX'): enemy.acc.setX(0.0)
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > \
           (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            set_enemy_state(enemy, 'idle')
            # Fall through to allow normal updates if defrosting finished this tick
        else:
            return an_effect_is_overriding_updates 

    # --- is_dead (normal death, not stomp or smashed) ---
    if getattr(enemy, 'is_dead', False): # If dead by other means
        an_effect_is_overriding_updates = True
        if hasattr(enemy, 'alive') and enemy.alive() and getattr(enemy, 'death_animation_finished', False):
            if hasattr(enemy, 'kill'): enemy.kill()
        return an_effect_is_overriding_updates 

    # If an overriding effect was processed and returned true, exit.
    # If only aflame/deflame was processed, they might not stop further AI logic if desired,
    # so their "return an_effect_is_overriding_updates" is removed.
    # The boolean return now signifies if the *entire* enemy update (AI, physics) should be skipped.
    # Aflame/Deflame enemies should still move, so they don't return True here.
    return an_effect_is_overriding_updates and not processed_aflame_or_deflame_this_tick