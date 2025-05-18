# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.2 (Ensure aflame/deflame also return True from main update)
Handles the application and management of status effects for enemies,
such as aflame, frozen, petrified, and stomp death.
"""
import pygame
import constants as C # For durations, damage values, etc.

# Assumed: EnemyBase has attributes like is_aflame, aflame_timer_start, etc.
# Assumed: enemy_state_handler.set_enemy_state(enemy, new_state) exists.
try:
    from enemy_state_handler import set_enemy_state # Or however you name it
except ImportError:
    # Fallback if direct import fails (e.g., during early refactoring)
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): # If the old method still exists on enemy
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATUS_EFFECTS: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

# --- Functions to APPLY status effects ---

def apply_aflame_effect(enemy):
    """Applies the 'aflame' status effect to the enemy."""
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return

    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    
    enemy.has_ignited_another_enemy_this_cycle = False 
    set_enemy_state(enemy, 'aflame')
    # Speed change is handled by AI handler checking is_aflame flag.
    # Interrupt current attack
    enemy.is_attacking = False 
    enemy.attack_type = 0


def apply_freeze_effect(enemy):
    """Applies the 'frozen' status effect to the enemy."""
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_dead or enemy.is_petrified or enemy.is_aflame or enemy.is_deflaming:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return

    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen')
    enemy.vel.xy = 0,0
    enemy.acc.x = 0
    enemy.is_attacking = False
    enemy.attack_type = 0


def petrify_enemy(enemy):
    """Applies the 'petrified' status effect to the enemy."""
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} is being petrified by petrify_enemy.")
    enemy.facing_at_petrification = enemy.facing_right
    set_enemy_state(enemy, 'petrified')
    enemy.vel.x = 0
    enemy.acc.x = 0


def smash_petrified_enemy(enemy):
    """Transitions a petrified enemy to the 'smashed' state."""
    if enemy.is_petrified and not enemy.is_stone_smashed:
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} is being smashed by smash_petrified_enemy.")
        set_enemy_state(enemy, 'smashed')
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but not petrified or already smashed.")


def stomp_kill_enemy(enemy):
    """Initiates the stomp death sequence for the enemy."""
    if enemy.is_dead or enemy.is_stomp_dying or enemy.is_petrified or enemy.is_aflame or enemy.is_frozen:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Stomp kill initiated by stomp_kill_enemy.")
    set_enemy_state(enemy, 'stomp_death')
    enemy.current_health = 0 
    enemy.vel.xy = 0,0
    enemy.acc.xy = 0,0


# --- Function to UPDATE status effects (called each frame) ---

def update_enemy_status_effects(enemy, current_time_ms, platforms_group):
    """
    Manages the timers and transitions for active status effects.
    This function should be called early in the enemy's main update loop.
    Returns True if a status effect is active and handling the update (blocking further AI/physics),
    False otherwise.
    """
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # --- Petrified and Smashed State Handling (Highest Priority) ---
    if enemy.is_stone_smashed:
        if enemy.death_animation_finished or \
           (current_time_ms - enemy.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS):
            debug(f"Smashed stone Enemy {enemy_id_log} duration/animation ended. Killing sprite.")
            enemy.kill() 
        return True 

    if enemy.is_petrified: 
        # Apply gravity if not on ground
        if not enemy.on_ground:
            enemy.vel.y += getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)) # Use enemy gravity, fallback to player
            enemy.vel.y = min(enemy.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
            enemy.pos.y += enemy.vel.y
            enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y))
            # Basic ground collision for falling stone
            for platform_sprite in pygame.sprite.spritecollide(enemy, platforms_group, False):
                 if enemy.vel.y > 0 and enemy.rect.bottom > platform_sprite.rect.top and \
                    (enemy.pos.y - enemy.vel.y) <= platform_sprite.rect.top + 1:
                      enemy.rect.bottom = platform_sprite.rect.top
                      enemy.on_ground = True; enemy.vel.y = 0; enemy.acc.y = 0
                      enemy.pos.y = enemy.rect.bottom; break
        return True

    # --- Aflame/Deflame Handling ---
    if enemy.is_aflame:
        if current_time_ms - enemy.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Aflame duration ended. Transitioning to deflame.")
            set_enemy_state(enemy, 'deflame')
            return True # State changed, deflame will be handled by its own block or next update
        elif current_time_ms - enemy.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): 
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms
        # AI handler will manage movement speed for aflame enemies.
        return True # Aflame processing is active, blocks normal AI/physics (handled by AI instead)

    if enemy.is_deflaming: # Changed to 'if' from 'elif' to allow processing even if just transitioned from aflame
        if current_time_ms - enemy.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Deflame duration ended. Transitioning to idle.")
            set_enemy_state(enemy, 'idle') # Default to idle after deflame
            return False # Deflame finished, allow normal processing
        # AI handler will manage movement speed for deflaming enemies.
        return True # Deflaming processing is active, blocks normal AI/physics (handled by AI instead)

    # --- Stomp Death Animation Handling ---
    if enemy.is_stomp_dying:
        if enemy.death_animation_finished: 
            debug(f"Enemy {enemy_id_log}: Stomp death animation reported as finished. Killing sprite.")
            enemy.kill()
        return True 

    # --- Frozen/Defrost Handling ---
    if enemy.is_frozen:
        enemy.vel.xy = 0,0; enemy.acc.x = 0 
        if current_time_ms - enemy.frozen_effect_timer > C.ENEMY_FROZEN_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Frozen duration ended. Transitioning to defrost.")
            set_enemy_state(enemy, 'defrost')
        return True 

    if enemy.is_defrosting:
        enemy.vel.xy = 0,0; enemy.acc.x = 0 
        if current_time_ms - enemy.frozen_effect_timer > (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            debug(f"Enemy {enemy_id_log}: Defrost duration ended. Transitioning to idle.")
            set_enemy_state(enemy, 'idle')
            return False 
        return True 

    # --- Regular Death Animation Handling (if not any of the above special deaths) ---
    if enemy.is_dead: 
        if enemy.alive(): 
            if enemy.death_animation_finished:
                debug(f"Enemy {enemy_id_log}: Regular death animation finished. Killing sprite.")
                enemy.kill()
        return True 

    return False