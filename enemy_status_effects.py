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
    # Fallback if direct import fails (e.g., during early refactoring stages)
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): # Check if the old method might still exist on the enemy instance
            enemy.set_state(new_state)
        else:
            # This critical print is better than crashing if the handler isn't found during dev
            print(f"CRITICAL ENEMY_STATUS_EFFECTS: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# Assuming logger is set up and accessible
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_STATUS_EFFECTS: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Defined error for fallback
    def critical(msg): print(f"CRITICAL: {msg}")

# --- Functions to APPLY status effects ---

def apply_aflame_effect(enemy):
    """
    Applies the 'aflame' status effect to the enemy if not already in a conflicting state.
    """
    # Prevent applying if already aflame/deflaming, dead, petrified, or frozen/defrosting
    if enemy.is_aflame or enemy.is_deflaming or enemy.is_dead or \
       enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying aflame effect.")
    enemy.has_ignited_another_enemy_this_cycle = False # Reset ignition flag for this new aflame cycle
    set_enemy_state(enemy, 'aflame') # This will set is_aflame=True and timers via state_handler
    
    # Stop current actions
    enemy.is_attacking = False 
    enemy.attack_type = 0
    # Physics handler will adjust speed based on is_aflame flag

def apply_freeze_effect(enemy):
    """
    Applies the 'frozen' status effect to the enemy if not already in a conflicting state.
    """
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_dead or \
       enemy.is_petrified or enemy.is_aflame or enemy.is_deflaming:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} ({getattr(enemy, 'color_name', 'N/A')}): Applying freeze effect.")
    set_enemy_state(enemy, 'frozen') # state_handler sets is_frozen=True and timers, stops movement
    
    # Ensure movement and attacks are stopped
    enemy.vel.xy = 0,0
    enemy.acc.x = 0
    enemy.is_attacking = False
    enemy.attack_type = 0

def petrify_enemy(enemy):
    """
    Turns the enemy into stone if not already petrified or truly dead.
    """
    # Prevent petrifying if already petrified OR if truly dead (not just "petrified dead")
    if enemy.is_petrified or (enemy.is_dead and not enemy.is_petrified):
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: petrify_enemy called but already petrified or truly dead. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}) is being petrified by petrify_enemy.")
    enemy.facing_at_petrification = enemy.facing_right # Store facing direction for consistent visuals
    set_enemy_state(enemy, 'petrified') # state_handler manages flags (is_petrified=True, is_dead=True), stops movement
    
    # Ensure movement is stopped
    enemy.vel.x = 0 # Redundant if state_handler does it, but safe
    enemy.acc.x = 0

def smash_petrified_enemy(enemy):
    """
    Smashes a petrified enemy if it's currently petrified and not already smashed.
    """
    if enemy.is_petrified and not enemy.is_stone_smashed: # Can only smash if petrified AND not yet smashed
        debug(f"Petrified Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}) is being smashed by smash_petrified_enemy.")
        set_enemy_state(enemy, 'smashed') # state_handler sets is_stone_smashed=True, timers, and handles animation
    else:
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: smash_petrified_enemy called but enemy not in a smashable state (Petrified: {enemy.is_petrified}, Smashed: {enemy.is_stone_smashed}).")

def stomp_kill_enemy(enemy):
    """
    Initiates the stomp death sequence for the enemy.
    Sets flags and captures the current image for the squash animation.
    """
    # Prevent stomp if already dead/stomp_dying or in an overriding state
    if enemy.is_dead or enemy.is_stomp_dying or enemy.is_petrified or \
       enemy.is_aflame or enemy.is_frozen: # Cannot stomp if on fire or frozen
        debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: stomp_kill_enemy called but already in conflicting state. Ignoring.")
        return
        
    debug(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')} (Color: {enemy.color_name}): Stomp kill initiated by stomp_kill_enemy.")
    
    enemy.is_stomp_dying = True # Primary flag for stomp visual effect
    enemy.stomp_death_start_time = pygame.time.get_ticks() # Timer for squash duration
    enemy.original_stomp_facing_right = enemy.facing_right # Save facing for consistent squash visual
    
    # Capture the exact current image for scaling (before state changes to 'stomp_death')
    # Ensure the image is not None and has a valid surface
    if hasattr(enemy, 'image') and enemy.image and isinstance(enemy.image, pygame.Surface):
        enemy.original_stomp_death_image = enemy.image.copy() # Use a copy
    else: # Fallback if image is bad or missing
        # Create a transparent placeholder based on rect size if available
        width_ph = enemy.rect.width if hasattr(enemy, 'rect') else getattr(C, 'TILE_SIZE', 30)
        height_ph = enemy.rect.height if hasattr(enemy, 'rect') else int(getattr(C, 'TILE_SIZE', 30) * 1.5)
        enemy.original_stomp_death_image = pygame.Surface((width_ph, height_ph), pygame.SRCALPHA)
        enemy.original_stomp_death_image.fill((0,0,0,0)) # Fully transparent
        warning(f"Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Could not copy valid image for stomp squash animation; using transparent placeholder.")

    # Set logical death state properties
    enemy.is_dead = True      # Logically dead
    enemy.current_health = 0  # No health
    enemy.vel.xy = 0,0        # Stop movement
    enemy.acc.xy = 0,0        # Stop acceleration
    enemy.death_animation_finished = False # Stomp squash animation needs to play
    
    # Set logical state to 'stomp_death'. Animation handler might use this,
    # but the primary visual is the scaling transform handled in update_enemy_status_effects.
    set_enemy_state(enemy, 'stomp_death')


# --- Function to UPDATE status effects (called each frame from Enemy.update) ---

def update_enemy_status_effects(enemy, current_time_ms, platforms_group):
    """
    Manages timers and transitions for active status effects on the enemy.
    Also handles visual updates for effects like stomp squash.
    Returns True if a status effect is active and overriding normal updates, False otherwise.
    """
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    an_effect_is_overriding_updates = False # Flag to indicate if normal AI/physics should be skipped

    # --- Stomp Death Animation Handling (High Priority if active) ---
    if enemy.is_stomp_dying:
        an_effect_is_overriding_updates = True # Stomp death overrides everything
        elapsed_stomp_time = current_time_ms - enemy.stomp_death_start_time
        stomp_squash_duration = getattr(C, 'ENEMY_STOMP_SQUASH_DURATION_MS', 400) # Duration of squash

        if elapsed_stomp_time >= stomp_squash_duration: # Squash animation finished
            if not enemy.death_animation_finished:
                debug(f"Enemy {enemy_id_log}: Stomp squash duration ({stomp_squash_duration}ms) ended.")
                enemy.death_animation_finished = True # Mark as visually "done"
            if enemy.alive(): # If still in sprite groups
                enemy.kill() # Remove from all groups
        else: # Squash animation is in progress
            if enemy.original_stomp_death_image: # Ensure we have an image to scale
                progress_ratio = elapsed_stomp_time / stomp_squash_duration # 0.0 to 1.0
                scale_y_factor = 1.0 - progress_ratio # Height shrinks from 1.0 down to 0.0
                
                original_width = enemy.original_stomp_death_image.get_width()
                original_height = enemy.original_stomp_death_image.get_height()
                
                # Calculate new dimensions for squash effect
                new_height = max(1, int(original_height * scale_y_factor)) # Ensure at least 1px height
                new_width = original_width # Width usually doesn't change, or could bulge slightly

                if new_width > 0 and new_height > 0: # Valid dimensions for scaling
                    try:
                        # Create a fresh copy from original for scaling to avoid cumulative errors/artifacts
                        base_image_to_scale = enemy.original_stomp_death_image.copy()
                        # Apply facing flip to the base image if needed *before* scaling
                        if not enemy.original_stomp_facing_right: # Use facing at time of stomp
                            base_image_to_scale = pygame.transform.flip(base_image_to_scale, True, False)

                        squashed_image = pygame.transform.smoothscale(base_image_to_scale, (new_width, new_height))
                    except (pygame.error, ValueError): # Fallback to simple scale if smoothscale fails (e.g., 0-dim)
                        base_image_to_scale = enemy.original_stomp_death_image.copy() # Fresh copy
                        if not enemy.original_stomp_facing_right:
                            base_image_to_scale = pygame.transform.flip(base_image_to_scale, True, False)
                        squashed_image = pygame.transform.scale(base_image_to_scale, (new_width, new_height))
                    
                    old_midbottom_pos = enemy.rect.midbottom # Preserve position
                    enemy.image = squashed_image
                    enemy.rect = enemy.image.get_rect(midbottom=old_midbottom_pos) # Re-anchor
                    enemy.pos = pygame.math.Vector2(enemy.rect.midbottom) # Sync pos
                else: # Fallback if new dimensions are invalid (e.g., height becomes 0)
                    # Create a minimal (e.g., 1x1 transparent) surface to avoid errors
                    min_fallback_width = original_width if original_width > 0 else 1
                    enemy.image = pygame.Surface((min_fallback_width, 1), pygame.SRCALPHA) 
                    enemy.image.fill((0,0,0,0)) # Transparent
                    old_midbottom_pos = enemy.rect.midbottom
                    enemy.rect = enemy.image.get_rect(midbottom=old_midbottom_pos)
                    enemy.pos = pygame.math.Vector2(enemy.rect.midbottom)
            
            # Ensure stomped enemy doesn't move and stays on ground (visually)
            enemy.vel.xy = 0,0
            enemy.acc.xy = 0,0
            enemy.on_ground = True # Visually, it's squashed onto the ground
        return an_effect_is_overriding_updates # True because stomp death is happening

    # --- Petrified and Smashed State Handling ---
    if enemy.is_stone_smashed: # If smashed, it's an overriding state until duration ends
        an_effect_is_overriding_updates = True
        if enemy.death_animation_finished or \
           (current_time_ms - enemy.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS):
            debug(f"Smashed stone Enemy {enemy_id_log} duration/animation ended. Killing sprite.")
            if enemy.alive(): enemy.kill() # Remove from all groups
        # Animation itself (frame cycling for smashed GIF) is handled by enemy_animation_handler
        return an_effect_is_overriding_updates 

    if enemy.is_petrified: # If petrified (but not smashed), it's also overriding
        an_effect_is_overriding_updates = True
        # Petrified enemies might fall if not on ground
        if not enemy.on_ground:
            enemy.vel.y += getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)) # Apply gravity
            enemy.vel.y = min(enemy.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18)) # Terminal velocity
            enemy.pos.y += enemy.vel.y # Update position
            enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y)) # Update rect
            # Basic platform collision for falling stone
            for platform_sprite in pygame.sprite.spritecollide(enemy, platforms_group, False):
                 if enemy.vel.y > 0 and enemy.rect.bottom > platform_sprite.rect.top and \
                    (enemy.pos.y - enemy.vel.y) <= platform_sprite.rect.top + 1: # Landed
                      enemy.rect.bottom = platform_sprite.rect.top
                      enemy.on_ground = True; enemy.vel.y = 0; enemy.acc.y = 0 # Stop on ground
                      enemy.pos.y = enemy.rect.bottom; break # Update pos
        # Static petrified image is handled by enemy_animation_handler
        return an_effect_is_overriding_updates

    # --- Aflame/Deflame Handling (These don't fully override physics/AI, but manage timers/damage) ---
    processed_aflame_or_deflame_this_tick = False # To track if aflame/deflame logic ran
    if enemy.is_aflame:
        processed_aflame_or_deflame_this_tick = True
        # Check if aflame duration has ended
        if current_time_ms - enemy.aflame_timer_start > C.ENEMY_AFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Aflame duration ended. Transitioning to deflame state.")
            set_enemy_state(enemy, 'deflame') # Transition to deflaming state
        # Apply damage over time if aflame
        elif current_time_ms - enemy.aflame_damage_last_tick > C.ENEMY_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(enemy, 'take_damage'): # Ensure method exists
                enemy.take_damage(C.ENEMY_AFLAME_DAMAGE_PER_TICK) # Apply damage
            enemy.aflame_damage_last_tick = current_time_ms # Reset damage tick timer

    if enemy.is_deflaming: # Separate check, could transition from aflame to deflame in one tick
        processed_aflame_or_deflame_this_tick = True
        # Check if deflame duration has ended
        if current_time_ms - enemy.deflame_timer_start > C.ENEMY_DEFLAME_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Deflame duration ended. Transitioning to idle state.")
            set_enemy_state(enemy, 'idle') # Transition to idle state

    # --- Frozen/Defrost Handling (These ARE overriding states) ---
    if enemy.is_frozen:
        an_effect_is_overriding_updates = True
        enemy.vel.xy = 0,0; enemy.acc.x = 0 # Ensure no movement
        # Check if frozen duration has ended
        if current_time_ms - enemy.frozen_effect_timer > C.ENEMY_FROZEN_DURATION_MS:
            debug(f"Enemy {enemy_id_log}: Frozen duration ended. Transitioning to defrost state.")
            set_enemy_state(enemy, 'defrost') # Transition to defrosting state
        return an_effect_is_overriding_updates 

    if enemy.is_defrosting:
        an_effect_is_overriding_updates = True
        enemy.vel.xy = 0,0; enemy.acc.x = 0 # Still no movement during defrost
        # Check if total (frozen + defrost) duration has passed
        if current_time_ms - enemy.frozen_effect_timer > (C.ENEMY_FROZEN_DURATION_MS + C.ENEMY_DEFROST_DURATION_MS):
            debug(f"Enemy {enemy_id_log}: Defrost duration ended. Transitioning to idle state.")
            set_enemy_state(enemy, 'idle') # Transition to idle state
            return False # No longer overriding after transition to idle
        return an_effect_is_overriding_updates 

    # --- Regular Death Animation Handling (if not petrified/stomp_dying) ---
    # This handles the case where an enemy dies from normal damage and plays its 'death' animation.
    if enemy.is_dead: # And not handled by stomp, petrify, smash, frozen, aflame logic above
        an_effect_is_overriding_updates = True
        if enemy.alive(): # If still in sprite groups
            if enemy.death_animation_finished: # If the 'death' animation is visually complete
                debug(f"Enemy {enemy_id_log}: Regular death animation finished. Killing sprite.")
                enemy.kill() # Remove from all groups
        # Animation itself is handled by enemy_animation_handler
        return an_effect_is_overriding_updates 

    # If aflame/deflame was processed but didn't result in an overriding state (like freeze/death)
    # return False to allow normal AI/physics to proceed (with aflame speed modifiers).
    if processed_aflame_or_deflame_this_tick:
        return False # Aflame/Deflame modify behavior but don't fully stop updates like freeze does

    # If no overriding status effect is active
    return False