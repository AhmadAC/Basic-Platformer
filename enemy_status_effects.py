#################### START OF MODIFIED FILE: enemy_status_effects.py ####################

# enemy_status_effects.py
# -*- coding: utf-8 -*-
"""
# version 1.0.5 (Refined stomp squash animation to be independent of animation handler)
Handles the application and management of status effects for enemies,
such as aflame, frozen, petrified, and stomp death.
"""
import pygame
import constants as C # For durations, damage values, etc.

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'):
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATUS_EFFECTS: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

# --- Functions to APPLY status effects ---

def apply_aflame_effect(enemy):
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False 
    set_enemy_state(enemy, 'aflame')
    enemy.is_attacking = False 
    enemy.attack_type = 0

def apply_freeze_effect(enemy):
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
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} is being petrified by petrify_enemy.")
    enemy.facing_at_petrification = enemy.facing_right
    set_enemy_state(enemy, 'petrified')
    enemy.vel.x = 0
    enemy.acc.x = 0

def smash_petrified_enemy(enemy):
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
    
    enemy.is_stomp_dying = True
    enemy.stomp_death_start_time = pygame.time.get_ticks()
    enemy.original_stomp_facing_right = enemy.facing_right # Save facing for consistent squash
    
    # Capture the exact current image for scaling
    # Ensure the image is not None and has a valid surface
    if hasattr(enemy, 'image') and enemy.image and isinstance(enemy.image, pygame.Surface):
        enemy.original_stomp_death_image = enemy.image.copy()
    else: # Fallback if image is bad
        enemy.original_stomp_death_image = pygame.Surface((enemy.rect.width if hasattr(enemy, 'rect') else 30, 
                                                           enemy.rect.height if hasattr(enemy, 'rect') else 40), 
                                                          pygame.SRCALPHA)
        enemy.original_stomp_death_image.fill((0,0,0,0)) # Transparent placeholder
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Could not copy image for stomp; using transparent placeholder.")

    enemy.is_dead = True
    enemy.current_health = 0 
    enemy.vel.xy = 0,0
    enemy.acc.xy = 0,0
    enemy.death_animation_finished = False
    set_enemy_state(enemy, 'stomp_death') # Mainly for logic, visual is handled by is_stomp_dying


# --- Function to UPDATE status effects (called each frame) ---

def update_enemy_status_effects(enemy, current_time_ms, platforms_group):
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    processed_aflame_or_deflame_this_tick = False

    # --- Stomp Death Animation Handling (High Priority if active) ---
    if enemy.is_stomp_dying:
        elapsed_stomp_time = current_time_ms - enemy.stomp_death_start_time
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400)

        if elapsed_stomp_time >= stomp_squash_duration:
            if not enemy.death_animation_finished:
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ({stomp_squash_duration}ms) ended.")
                enemy.death_animation_finished = True
            if enemy.alive():
                enemy.kill()
        else:
            if enemy.original_stomp_death_image:
                progress = elapsed_stomp_time / stomp_squash_duration
                scale_y = 1.0 - progress
                
                original_width = enemy.original_stomp_death_image.get_width()
                original_height = enemy.original_stomp_death_image.get_height()
                
                new_height = max(1, int(original_height * scale_y))
                new_width = original_width

                if new_width > 0 and new_height > 0:
                    try:
                        # Create a fresh copy from original for scaling to avoid cumulative errors/artifacts
                        base_image_to_scale = enemy.original_stomp_death_image.copy()
                        # Apply facing flip to the base image if needed *before* scaling
                        if not enemy.original_stomp_facing_right:
                            base_image_to_scale = pygame.transform.flip(base_image_to_scale, True, False)

                        squashed_image = pygame.transform.smoothscale(base_image_to_scale, (new_width, new_height))
                    except: 
                        base_image_to_scale = enemy.original_stomp_death_image.copy()
                        if not enemy.original_stomp_facing_right:
                            base_image_to_scale = pygame.transform.flip(base_image_to_scale, True, False)
                        squashed_image = pygame.transform.scale(base_image_to_scale, (new_width, new_height))
                    
                    old_midbottom = enemy.rect.midbottom
                    enemy.image = squashed_image
                    enemy.rect = enemy.image.get_rect(midbottom=old_midbottom)
                    enemy.pos = pygame.math.Vector2(enemy.rect.midbottom) # Update pos based on new rect
                else:
                    enemy.image = pygame.Surface((original_width if original_width > 0 else 1, 1), pygame.SRCALPHA) 
                    enemy.image.fill((0,0,0,0))
                    old_midbottom = enemy.rect.midbottom
                    enemy.rect = enemy.image.get_rect(midbottom=old_midbottom)
                    enemy.pos = pygame.math.Vector2(enemy.rect.midbottom)
            
            enemy.vel.xy = 0,0
            enemy.acc.xy = 0,0
            enemy.on_ground = True
        return True # Stomp death sequence is active and overrides other updates

    # --- Petrified and Smashed State Handling ---
    if enemy.is_stone_smashed:
        if enemy.death_animation_finished or \
           (current_time_ms - enemy.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS):
            debug(f"Smashed stone Enemy {enemy_id_log} duration/animation ended. Killing sprite.")
            enemy.kill() 
        return True 

    if enemy.is_petrified: 
        if not enemy.on_ground:
            enemy.vel.y += getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7))
            enemy.vel.y = min(enemy.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
            enemy.pos.y += enemy.vel.y
            enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y))
            for platform_sprite in pygame.sprite.spritecollide(enemy, platforms_group, False):
                 if enemy.vel.y > 0 and enemy.rect.bottom > platform_sprite.rect.top and \
                    (enemy.pos.y - enemy.vel.y) <= platform_sprite.rect.top + 1:
                      enemy.rect.bottom = platform_sprite.rect.top
                      enemy.on_ground = True; enemy.vel.y = 0; enemy.acc.y = 0
                      enemy.pos.y = enemy.rect.bottom; break
        return True

    # --- Aflame/Deflame Handling ---
    if enemy.is_aflame:
        processed_aflame_or_deflame_this_tick = True
        if current_time_ms - enemy.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Aflame duration ended. Transitioning to deflame.")
            set_enemy_state(enemy, 'deflame')
        elif current_time_ms - enemy.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): 
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK)
            enemy.aflame_damage_last_tick = current_time_ms

    if enemy.is_deflaming:
        processed_aflame_or_deflame_this_tick = True
        if current_time_ms - enemy.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Deflame duration ended. Transitioning to idle.")
            set_enemy_state(enemy, 'idle')

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

    # --- Regular Death Animation Handling ---
    if enemy.is_dead: 
        if enemy.alive(): 
            if enemy.death_animation_finished:
                debug(f"Enemy {enemy_id_log}: Regular death animation finished. Killing sprite.")
                enemy.kill()
        return True 

    if processed_aflame_or_deflame_this_tick:
        return False

    return False

#################### END OF MODIFIED FILE: enemy_status_effects.py ####################