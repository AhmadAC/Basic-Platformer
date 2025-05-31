# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects for enemies using PySide6.
MODIFIED: Added apply_zapped_effect and zapped state handling in update.
MODIFIED: Passes current_time_ms to set_enemy_state for timer consistency.
MODIFIED: Implements 5-second overall fire effect timeout to force 'idle'.
MODIFIED: Correctly uses enemy constants for status effect durations.
MODIFIED: Ensures zapped effect also prevents other status applications and is cleared.
MODIFIED: Zapped effect is applied if target is not already in a conflicting state.
MODIFIED: Ensures EnemyKnight specific states like 'jump' are considered when transitioning from effects.
"""
# version 2.0.6 (Knight jump state awareness for effect end transitions)

import time # For monotonic timer
from typing import List, Optional, Any, TYPE_CHECKING

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor
from PySide6.QtCore import QPointF, QRectF, QSize, Qt

# Game imports
import constants as C # Use C directly for constants

if TYPE_CHECKING:
    from enemy import Enemy # For type hinting
    # from enemy_knight import EnemyKnight # Avoid direct import if possible

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
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

_start_time_enemy_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_status_monotonic) * 1000)

def _get_next_state_after_effect(enemy: Any) -> str:
    """Determines the appropriate next state after a status effect ends."""
    if not getattr(enemy, 'on_ground', False):
        # Check if it's a knight and was mid-jump; if so, 'fall' is usually more appropriate than 'jump' state after an effect.
        if enemy.__class__.__name__ == 'EnemyKnight' and getattr(enemy, '_is_mid_patrol_jump', False):
            return 'fall' # Or 'jump' if the jump animation should resume, but fall is safer.
        return 'fall'
    # If on ground, default to idle. Knight AI will transition to run if needed.
    return 'idle'


# --- Functions to APPLY status effects ---
def apply_aflame_effect(enemy: Any): # Changed type hint for flexibility
    current_time_ms = get_current_ticks_monotonic() 
    if getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_deflaming', False) or \
       getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_zapped', False):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False
    set_enemy_state(enemy, 'aflame', current_time_ms)
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): setattr(enemy, 'attack_type', "none") # Use string for consistency

def apply_freeze_effect(enemy: Any):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_defrosting', False) or \
       getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_deflaming', False) or \
       getattr(enemy, 'is_zapped', False):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen', current_time_ms)
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): setattr(enemy, 'attack_type', "none")

def apply_zapped_effect(enemy: Any):
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
    set_enemy_state(enemy, 'zapped', current_time_ms)
    if hasattr(enemy, 'is_attacking'): enemy.is_attacking = False
    if hasattr(enemy, 'attack_type'): setattr(enemy, 'attack_type', "none")

def petrify_enemy(enemy: Any):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_petrified', False) or \
       (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'is_petrified', False)) or \
       getattr(enemy, 'is_zapped', False):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified, truly dead, or zapped. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being petrified.")
    if hasattr(enemy, 'facing_right'):
        enemy.facing_at_petrification = enemy.facing_right
    else: enemy.facing_at_petrification = True
    set_enemy_state(enemy, 'petrified', current_time_ms)

def smash_petrified_enemy(enemy: Any):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_petrified', False) and not getattr(enemy, 'is_stone_smashed', False):
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}) is being smashed.")
        set_enemy_state(enemy, 'smashed', current_time_ms)
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but not in smashable state (Petrified: {getattr(enemy, 'is_petrified', False)}, Smashed: {getattr(enemy, 'is_stone_smashed', False)}).")

def stomp_kill_enemy(enemy: Any):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(enemy, 'is_dead', False) or \
       getattr(enemy, 'is_stomp_dying', False) or \
       getattr(enemy, 'is_petrified', False) or \
       getattr(enemy, 'is_aflame', False) or \
       getattr(enemy, 'is_frozen', False) or \
       getattr(enemy, 'is_zapped', False):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {getattr(enemy, 'color_name', 'N/A')}): Stomp kill initiated.")
    
    enemy.is_stomp_dying = True
    enemy.stomp_death_start_time = current_time_ms
    if hasattr(enemy, 'facing_right'): enemy.original_stomp_facing_right = enemy.facing_right
    else: enemy.original_stomp_facing_right = True

    if hasattr(enemy, 'image') and enemy.image and not enemy.image.isNull():
        enemy.original_stomp_death_image = enemy.image.copy()
    else: # Create a placeholder if image is bad
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
    set_enemy_state(enemy, 'stomp_death', current_time_ms)


# --- Function to UPDATE status effects ---
def update_enemy_status_effects(enemy: Any, current_time_ms: int, platforms_list: List[Any]) -> bool:
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # Overall 5-second fire effect timeout
    if (getattr(enemy, 'is_aflame', False) or getattr(enemy, 'is_deflaming', False)) and \
       hasattr(enemy, 'overall_fire_effect_start_time') and \
       getattr(enemy, 'overall_fire_effect_start_time', 0) > 0:
        
        if current_time_ms - getattr(enemy, 'overall_fire_effect_start_time', current_time_ms) > 5000:
            debug(f"EnemyStatusEffects ({enemy_id_log}): Overall 5s fire effect duration met. Forcing state to '{_get_next_state_after_effect(enemy)}'.")
            set_enemy_state(enemy, _get_next_state_after_effect(enemy), current_time_ms)
            return True # Update was overridden by this status logic

    # Stomp Dying
    if getattr(enemy, 'is_stomp_dying', False):
        elapsed_stomp_time = current_time_ms - getattr(enemy, 'stomp_death_start_time', current_time_ms)
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400)
        if elapsed_stomp_time >= stomp_squash_duration:
            if not getattr(enemy, 'death_animation_finished', True):
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ended.")
                enemy.death_animation_finished = True
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        else: # Squash animation
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
                else: # Fallback if dimensions become zero
                    fallback_width = original_width if original_width > 0 else 1
                    enemy.image = QPixmap(fallback_width, 1); 
                    if not enemy.image.isNull(): enemy.image.fill(Qt.GlobalColor.transparent)
                    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
            if hasattr(enemy, 'vel'): enemy.vel = QPointF(0,0)
            if hasattr(enemy, 'acc'): enemy.acc = QPointF(0,0)
            enemy.on_ground = True # Stomped enemies are flat on the ground
        return True # Stomp dying overrides other logic

    # Smashed Stone
    if getattr(enemy, 'is_stone_smashed', False):
        if getattr(enemy, 'death_animation_finished', False) or \
           (current_time_ms - getattr(enemy, 'smashed_timer_start', current_time_ms) > C.STONE_SMASHED_DURATION_MS):
            if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        # Smashed stone might still fall if not on ground (handled by physics)
        return True # Smashed state overrides AI

    # Petrified (not smashed)
    if getattr(enemy, 'is_petrified', False):
        # Petrified enemies fall if airborne, but don't move otherwise.
        # Their physics (gravity, landing) is handled in update_enemy_physics_and_collisions.
        # This status effect primarily blocks AI and other actions.
        return True # Petrified state overrides AI

    # Zapped
    if getattr(enemy, 'is_zapped', False):
        if current_time_ms - getattr(enemy, 'zapped_timer_start', current_time_ms) > C.ENEMY_ZAPPED_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Zapped duration ended.")
            set_enemy_state(enemy, _get_next_state_after_effect(enemy), current_time_ms)
            # Fall through this frame if zapped just ended, allowing other logic if any
        else: # Still zapped
            if C.ENEMY_ZAPPED_DAMAGE_PER_TICK > 0 and \
               current_time_ms - getattr(enemy, 'zapped_damage_last_tick', 0) > C.ENEMY_ZAPPED_DAMAGE_INTERVAL_MS:
                debug(f"Enemy {enemy_id_log}: Taking zapped damage.")
                if hasattr(enemy, 'take_damage'): enemy.take_damage(C.ENEMY_ZAPPED_DAMAGE_PER_TICK)
                enemy.zapped_damage_last_tick = current_time_ms
            if hasattr(enemy, 'vel'): enemy.vel.setX(0) # Zapped enemies are stunned horizontally
            if getattr(enemy,'on_ground', False) and hasattr(enemy,'vel'): enemy.vel.setY(0) # Stop vertical if on ground
            return True # Zapped state overrides other movement/action logic

    # Frozen / Defrosting
    if getattr(enemy, 'is_frozen', False):
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > C.ENEMY_FROZEN_DURATION_MS:
            set_enemy_state(enemy, 'defrost', current_time_ms)
        return True 
    elif getattr(enemy, 'is_defrosting', False):
        if current_time_ms - getattr(enemy, 'frozen_effect_timer', current_time_ms) > \
           (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            set_enemy_state(enemy, _get_next_state_after_effect(enemy), current_time_ms)
        else:
            return True 

    # Aflame / Deflaming
    if getattr(enemy, 'is_aflame', False):
        if current_time_ms - getattr(enemy, 'aflame_timer_start', current_time_ms) > C.ENEMY_AFLAME_DURATION_MS:
            set_enemy_state(enemy, 'deflame', current_time_ms)
        elif C.ENEMY_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - getattr(enemy, 'aflame_damage_last_tick', 0) > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms
        # Aflame does not return True here, as AI should still run (modified movement)
    elif getattr(enemy, 'is_deflaming', False):
        if current_time_ms - getattr(enemy, 'deflame_timer_start', current_time_ms) > C.ENEMY_DEFLAME_DURATION_MS:
            set_enemy_state(enemy, _get_next_state_after_effect(enemy), current_time_ms)
        # Deflaming also does not return True, AI still runs

    # If dead but animation not finished (and not one of the above terminal states)
    if getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', False):
        # If death animation finishes, kill() will be called by the main update loop.
        # This return True means other AI/physics logic won't run while death anim plays.
        return True 

    return False # No status effect overrode the update this frame