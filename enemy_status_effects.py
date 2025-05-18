# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.1
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
            print(f"CRITICAL STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found for P{enemy.enemy_id}")


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
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or enemy.is_petrified:
        debug(f"Enemy {enemy.enemy_id}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return

    debug(f"Enemy {enemy.enemy_id} ({enemy.color_name}): Applying aflame effect.")
    # The set_enemy_state function will handle setting flags and timers.
    set_enemy_state(enemy, 'aflame')
    # Additional direct effects if needed (e.g., immediate slowdown)
    enemy.vel.x *= 0.5
    enemy.is_attacking = False # Interrupt current attack
    enemy.attack_type = 0


def apply_freeze_effect(enemy):
    """Applies the 'frozen' status effect to the enemy."""
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_dead or enemy.is_petrified:
        debug(f"Enemy {enemy.enemy_id}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return

    debug(f"Enemy {enemy.enemy_id} ({enemy.color_name}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen')
    # Additional direct effects
    enemy.vel.xy = 0,0
    enemy.acc.x = 0
    enemy.is_attacking = False
    enemy.attack_type = 0


def petrify_enemy(enemy):
    """Applies the 'petrified' status effect to the enemy."""
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {enemy.enemy_id}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
    debug(f"Enemy {enemy.enemy_id} is being petrified by petrify_enemy.")
    # facing_at_petrification should be set before calling set_enemy_state
    enemy.facing_at_petrification = enemy.facing_right
    set_enemy_state(enemy, 'petrified')
    # Additional direct effects
    enemy.vel.x = 0
    enemy.acc.x = 0
    # Gravity is handled by physics update if petrified


def smash_petrified_enemy(enemy):
    """Transitions a petrified enemy to the 'smashed' state."""
    if enemy.is_petrified and not enemy.is_stone_smashed:
        debug(f"Petrified Enemy {enemy.enemy_id} is being smashed by smash_petrified_enemy.")
        set_enemy_state(enemy, 'smashed')
    else:
        debug(f"Enemy {enemy.enemy_id}: smash_petrified_enemy called but not petrified or already smashed.")


def stomp_kill_enemy(enemy):
    """Initiates the stomp death sequence for the enemy."""
    if enemy.is_dead or enemy.is_stomp_dying or enemy.is_petrified:
        debug(f"Enemy {enemy.enemy_id}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
    debug(f"Enemy {enemy.enemy_id}: Stomp kill initiated by stomp_kill_enemy.")
    # set_enemy_state('stomp_death') will handle flags and timers.
    set_enemy_state(enemy, 'stomp_death')
    # Additional direct effects
    enemy.current_health = 0 # Ensure health is 0
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

    # --- Petrified and Smashed State Handling (Highest Priority) ---
    if enemy.is_stone_smashed:
        if enemy.death_animation_finished or \
           (current_time_ms - enemy.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS):
            debug(f"Smashed stone Enemy {enemy.enemy_id} duration/animation ended. Killing sprite.")
            enemy.kill() # Remove from sprite groups
        # Animation is handled by enemy_animation_handler
        return True # Smashed state takes precedence

    if enemy.is_petrified: # Is petrified but not smashed
        # Gravity for petrified enemies is handled in the main physics update
        # enemy_physics_handler will check is_petrified and apply gravity if true.
        # Animation is handled by enemy_animation_handler
        return True # Petrified state takes precedence

    # --- Aflame/Deflame Handling ---
    if enemy.is_aflame:
        if current_time_ms - enemy.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
            debug(f"Enemy {enemy.enemy_id}: Aflame duration ended. Transitioning to deflame.")
            set_enemy_state(enemy, 'deflame')
            return True # State changed, deflame will be handled next relevant update
        elif current_time_ms - enemy.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): # Ensure method exists
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms
        # Movement/AI for aflame is handled in enemy_ai_handler
        return True # Aflame processing is active

    elif enemy.is_deflaming:
        if current_time_ms - enemy.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
            debug(f"Enemy {enemy.enemy_id}: Deflame duration ended. Transitioning to idle.")
            set_enemy_state(enemy, 'idle')
            return False # Deflame finished, allow normal processing
        # Movement/AI for deflaming is handled in enemy_ai_handler
        return True # Deflaming processing is active

    # --- Stomp Death Animation Handling ---
    if enemy.is_stomp_dying:
        # The visual scaling is handled in enemy_animation_handler.
        # Here we just check if it should be considered "finished" for game logic.
        if enemy.death_animation_finished: # This flag is set by the animation handler
            debug(f"Enemy {enemy.enemy_id}: Stomp death animation reported as finished. Killing sprite.")
            enemy.kill()
        return True # Stomp dying takes precedence

    # --- Frozen/Defrost Handling ---
    if enemy.is_frozen:
        enemy.vel.xy = 0,0; enemy.acc.x = 0 # Ensure no movement
        if current_time_ms - enemy.frozen_effect_timer > C.ENEMY_FROZEN_DURATION_MS:
            debug(f"Enemy {enemy.enemy_id}: Frozen duration ended. Transitioning to defrost.")
            set_enemy_state(enemy, 'defrost')
        return True # Frozen processing is active

    if enemy.is_defrosting:
        enemy.vel.xy = 0,0; enemy.acc.x = 0 # Ensure no movement
        # Defrost duration is relative to when freeze started
        if current_time_ms - enemy.frozen_effect_timer > (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            debug(f"Enemy {enemy.enemy_id}: Defrost duration ended. Transitioning to idle.")
            set_enemy_state(enemy, 'idle')
            return False # Defrost finished, allow normal processing
        return True # Defrosting processing is active

    # --- Regular Death Animation Handling (if not any of the above special deaths) ---
    if enemy.is_dead: # and not any of the above special states
        if enemy.alive(): # Check if sprite is still in groups
            if enemy.death_animation_finished:
                debug(f"Enemy {enemy.enemy_id}: Regular death animation finished. Killing sprite.")
                enemy.kill()
            # Physics for falling while dead (if applicable) can be in enemy_physics_handler
            # or simplified here if death state implies no complex physics
        return True # Dead processing takes precedence

    return False # No overriding status effect was actively managed this frame