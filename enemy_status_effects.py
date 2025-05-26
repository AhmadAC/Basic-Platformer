# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects for enemies using PySide6.
MODIFIED: Added apply_zapped_effect and zapped state handling in update.
MODIFIED: Passes current_time_ms to set_enemy_state for timer consistency.
MODIFIED: Implements 5-second overall fire effect timeout to force 'idle'.
MODIFIED: Correctly uses enemy constants for status effect durations.
MODIFIED: Ensures zapped effect also prevents other status applications and is cleared.
"""
# version 2.0.4 (Corrected constants, pass time, 5s fire, zapped handling)

import time # For monotonic timer
from typing import List, Optional, Any, TYPE_CHECKING

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, QSize, Qt

# Game imports
import constants as C # Use C directly for constants

if TYPE_CHECKING:
    from enemy import Enemy # For type hinting

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    # This fallback is critical if the import fails
    print("CRITICAL ENEMY_STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found.")
    def set_enemy_state(enemy, new_state, current_game_time_ms_param=None): # Add param for consistency
        if hasattr(enemy, 'state'): enemy.state = new_state
        else: print(f"CRITICAL ENEMY_STATUS_EFFECTS (Fallback): Cannot set state for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}.")


try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATUS_EFFECTS: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

# --- Monotonic Timer ---
_start_time_enemy_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_status_monotonic) * 1000)
# --- End Monotonic Timer ---


# --- Functions to APPLY status effects ---

def apply_aflame_effect(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic() # Get current time for set_enemy_state
    if getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_deflaming', False) or \
       getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_zapped', False): # Check zapped
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False
    set_enemy_state(enemy, 'aflame', current_time_ms) # Pass time
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): enemy.attack_type = 0

def apply_freeze_effect(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_deflaming', False) or \
       getattr(enemy, 'is_zapped', False): # Check zapped
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen', current_time_ms) # Pass time
    # Immobilization handled by set_enemy_state for 'frozen'
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): enemy.attack_type = 0

def apply_zapped_effect(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_zapped', False) or \
       getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_deflaming', False):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_zapped_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying ZAPPED effect.")
    set_enemy_state(enemy, 'zapped', current_time_ms) # Pass time. This will set is_zapped, timers, and initial immobilization.
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): enemy.attack_type = 0

def petrify_enemy(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_petrified', False) or \
       (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'is_petrified', False)) or \
       getattr(enemy, 'is_zapped', False): # Check zapped
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified, truly dead, or zapped. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being petrified.")
    if hasattr(enemy, 'facing_right'): # Ensure facing_right exists before assigning
        enemy.facing_at_petrification = enemy.facing_right
    else: enemy.facing_at_petrification = True # Default if missing
    
    set_enemy_state(enemy, 'petrified', current_time_ms) # Pass time

def smash_petrified_enemy(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being smashed.")
        set_enemy_state(enemy, 'smashed', current_time_ms) # Pass time
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but not in smashable state (Petrified: {getattr(enemy, 'is_petrified', False)}, Smashed: {getattr(enemy, 'is_stone_smashed', False)}).")

def stomp_kill_enemy(enemy: 'Enemy'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_stomp_dying', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_zapped', False): # Check zapped
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}): Stomp kill initiated.")
    
    enemy.is_stomp_dying = True
    enemy.stomp_death_start_time = current_time_ms
    if hasattr(enemy, 'facing_right'): enemy.original_stomp_facing_right = enemy.facing_right
    else: enemy.original_stomp_facing_right = True

    if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
        enemy.original_stomp_death_image = enemy.image.copy()
    else:
        rect_w = enemy.rect.width() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'width') and enemy.rect.width() > 0 else getattr(C, 'TILE_SIZE', 30.0)
        rect_h = enemy.rect.height() if hasattr(enemy, 'rect') and hasattr(enemy.rect, 'height') and enemy.rect.height() > 0 else int(getattr(C, 'TILE_SIZE', 30.0) * 1.5)
        enemy.original_stomp_death_image = QPixmap(int(rect_w), int(rect_h))
        if not enemy.original_stomp_death_image.isNull():
            enemy.original_stomp_death_image.fill(Qt.GlobalColor.transparent)
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Could not copy valid image for stomp; using transparent placeholder.")

    enemy.is_dead = True; enemy.current_health = 0
    if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
    if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
    enemy.death_animation_finished = False 
    set_enemy_state(enemy, 'stomp_death', current_time_ms) # Pass time


# --- Function to UPDATE status effects ---

def update_enemy_status_effects(enemy: 'Enemy', current_time_ms: int, platforms_list: List[Any]) -> bool:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # --- MODIFIED: Overall 5-second fire effect timeout ---
    if (getattr(enemy, 'is_aflame', False) or getattr(enemy, 'is_deflaming', False)) and \
       hasattr(enemy, 'overall_fire_effect_start_time') and \
       getattr(enemy, 'overall_fire_effect_start_time', 0) > 0: # Check if timer is active
        
        if current_time_ms - getattr(enemy, 'overall_fire_effect_start_time', current_time_ms) > 5000: # 5 seconds
            debug(f"EnemyStatusEffects ({enemy_id_log}): Overall 5s fire effect duration met. Forcing state to 'idle'.")
            
            # Flags are cleared by set_enemy_state when transitioning to a non-fire state
            set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms)
            return True # Override complete for this frame
    # --- END MODIFICATION ---

    if getattr(enemy, 'is_stomp_dying', False):
        elapsed_stomp_time = current_time_ms - getattr(enemy, 'stomp_death_start_time', current_time_ms)
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400)
        if elapsed_stomp_time >= stomp_squash_duration:
            if not getattr(enemy, 'death_animation_finished', True):
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ended.")
                enemy.death_animation_finished = True
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        else: # Stomp animation in progress
            original_stomp_image = getattr(enemy, 'original_stomp_death_image', None)
            if original_stomp_image and not original_stomp_image.isNull():
                progress_ratio = elapsed_stomp_time / stomp_squash_duration
                scale_y_factor = max(0.0, 1.0 - progress_ratio)
                original_width = original_stomp_image.width(); original_height = original_stomp_image.height()
                new_height = max(1, int(original_height * scale_y_factor)); new_width = original_width
                if new_width > 0 and new_height > 0:
                    base_image_to_scale = original_stomp_image.copy()
                    if not getattr(enemy, 'original_stomp_facing_right', True):
                        q_img = base_image_to_scale.toImage()
                        if not q_img.isNull(): base_image_to_scale = QPixmap.fromImage(q_img.mirrored(True, False))
                    squashed_pixmap = base_image_to_scale.scaled(new_width, new_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    old_midbottom_qpointf = QPointF(enemy.rect.center().x(), enemy.rect.bottom()) if hasattr(enemy, 'rect') and enemy.rect else None
                    enemy.image = squashed_pixmap
                    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos(old_midbottom_qpointf)
                else:
                    fallback_width = original_width if original_width > 0 else 1
                    enemy.image = QPixmap(fallback_width, 1); 
                    if not enemy.image.isNull(): enemy.image.fill(Qt.GlobalColor.transparent)
                    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
            if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
            enemy.on_ground = True
        return True 

    if getattr(enemy, 'is_stone_smashed', False):
        if getattr(enemy, 'death_animation_finished', False) or \
           (current_time_ms - getattr(enemy, 'smashed_timer_start', current_time_ms) > C.STONE_SMASHED_DURATION_MS):
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        return True 

    if getattr(enemy, 'is_petrified', False):
        if not getattr(enemy, 'on_ground', True):
            if hasattr(enemy, 'vel') and hasattr(enemy.vel, 'y') and hasattr(enemy.vel, 'setY') and \
               hasattr(enemy, 'acc') and hasattr(enemy.acc, 'y'):
                enemy.vel.setY(enemy.vel.y() + getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)))
                enemy.vel.setY(min(enemy.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
            if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'y') and hasattr(enemy.pos, 'setY') and \
               hasattr(enemy, 'vel') and hasattr(enemy.vel, 'y'):
                enemy.pos.setY(enemy.pos.y() + enemy.vel.y()) 
            if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            for platform_obj in platforms_list:
                 if hasattr(platform_obj, 'rect') and hasattr(enemy, 'rect') and enemy.rect.intersects(platform_obj.rect):
                     if hasattr(enemy, 'vel') and enemy.vel.y() > 0 and enemy.rect.bottom() > platform_obj.rect.top() and \
                        hasattr(enemy, 'pos') and (enemy.pos.y() - enemy.vel.y()) <= platform_obj.rect.top() + 1:
                          enemy.rect.moveBottom(platform_obj.rect.top())
                          enemy.on_ground = True; enemy.vel.setY(0.0)
                          if hasattr(enemy, 'acc') and hasattr(enemy.acc, 'setY'): enemy.acc.setY(0.0)
                          if hasattr(enemy, 'pos') and hasattr(enemy.pos, 'setY'): enemy.pos.setY(enemy.rect.bottom())
                          break
        return True 

    if getattr(enemy, 'is_zapped', False): # ZAPPED LOGIC
        if current_time_ms - getattr(enemy, 'zapped_timer_start', current_time_ms) > C.ENEMY_ZAPPED_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Zapped duration ended.")
            set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms)
            # Fall through this frame if zapped just ended
        else:
            if C.ENEMY_ZAPPED_DAMAGE_PER_TICK > 0 and \
               current_time_ms - getattr(enemy, 'zapped_damage_last_tick', 0) > C.ENEMY_ZAPPED_DAMAGE_INTERVAL_MS:
                debug(f"Enemy {enemy_id_log}: Taking zapped damage.")
                if hasattr(enemy, 'take_damage'): enemy.take_damage(C.ENEMY_ZAPPED_DAMAGE_PER_TICK)
                enemy.zapped_damage_last_tick = current_time_ms
            # Zapped effect is active and overrides further AI/Physics for this frame
            # (unless airborne, then physics handler might apply gravity if 'zapped' state doesn't zero Y acc)
            if hasattr(enemy, 'vel'): enemy.vel.setX(0) # Zero X movement
            if getattr(enemy,'on_ground', False) and hasattr(enemy,'vel'): enemy.vel.setY(0) # Zero Y if on ground
            return True 

    if getattr(enemy, 'is_frozen', False):
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > C.ENEMY_FROZEN_DURATION_MS:
            set_enemy_state(enemy, 'defrost', current_time_ms)
        return True 
    elif getattr(enemy, 'is_defrosting', False):
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > \
           (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms)
        else:
            return True 

    # Aflame/Deflame cycle (will only run if the 5s overall timer hasn't forced 'idle' yet)
    if getattr(enemy, 'is_aflame', False):
        if current_time_ms - getattr(enemy, 'aflame_timer_start', current_time_ms) > C.ENEMY_AFLAME_DURATION_MS:
            set_enemy_state(enemy, 'deflame', current_time_ms)
        elif C.ENEMY_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - getattr(enemy, 'aflame_damage_last_tick', 0) > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms
    elif getattr(enemy, 'is_deflaming', False):
        if current_time_ms - getattr(enemy, 'deflame_timer_start', current_time_ms) > C.ENEMY_DEFLAME_DURATION_MS:
            set_enemy_state(enemy, 'idle' if getattr(enemy, 'on_ground', False) else 'fall', current_time_ms)

    if getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', False):
        if hasattr(enemy, 'alive') and enemy.alive() and getattr(enemy, 'death_animation_finished', False): # Re-check after anim might finish
             if hasattr(enemy, 'kill'): enemy.kill()
        return True 

    return False