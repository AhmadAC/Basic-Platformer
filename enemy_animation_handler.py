# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
# version 1.0.0.1
Handles animation selection and frame updates for Enemy instances.
Ensures correct visual representation based on logical state and manages
animation frame cycling and transitions.
"""
import pygame
import constants as C # For ANIM_FRAME_DURATION

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_ANIM_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

# It's assumed enemy_state_handler.set_enemy_state will be available
# For now, to avoid circular dependencies if this is created before enemy_state_handler fully,
# we'll assume the main Enemy class or another handler calls set_enemy_state.
# If this module needs to call it, the import will be:
# from enemy_state_handler import set_enemy_state

def determine_enemy_animation_key(enemy):
    """
    Determines the correct animation key based on the enemy's current logical state and flags.
    Returns the animation key string.
    """
    # Start with the enemy's logical state as the base for the animation key
    animation_key = enemy.state

    if enemy.is_petrified:
        if enemy.is_stone_smashed:
            animation_key = 'stone_smashed'  # This will use enemy.stone_smashed_frames
        else:
            animation_key = 'stone'          # This will use enemy.stone_image_frame
    elif enemy.is_dead: # Regular (non-petrified) death
        is_still_nm = abs(enemy.vel.x) < 0.1 and abs(enemy.vel.y) < 0.1
        key_variant = 'death_nm' if is_still_nm and enemy.animations.get('death_nm') else 'death'
        if enemy.animations.get(key_variant):
            animation_key = key_variant
        elif enemy.animations.get('death'): # Fallback to regular death if _nm variant not found
            animation_key = 'death'
        else: # Ultimate fallback for death
            animation_key = 'idle'
    elif enemy.state == 'aflame':
        animation_key = 'aflame'
    elif enemy.state == 'deflame':
        animation_key = 'deflame'
    elif enemy.state == 'frozen':
        animation_key = 'frozen'
    elif enemy.state == 'defrost':
        animation_key = 'defrost'
    elif enemy.post_attack_pause_timer > 0 and pygame.time.get_ticks() < enemy.post_attack_pause_timer:
        animation_key = 'idle' # Show idle during post-attack pause
    elif enemy.is_attacking:
        # Attack animations are usually set directly by set_state, but this can be a fallback
        # For example, if ai_state implies attack but state wasn't set quickly enough
        determined_attack_key = 'attack_nm' if enemy.animations.get('attack_nm') else 'attack'
        if enemy.animations.get(determined_attack_key):
            animation_key = determined_attack_key
        else: # Fallback if no attack animations
            animation_key = 'idle'
    elif enemy.is_taking_hit:
        animation_key = 'hit' if enemy.animations.get('hit') else 'idle'
    elif enemy.ai_state == 'chasing' or (enemy.ai_state == 'patrolling' and abs(enemy.vel.x) > 0.1):
        animation_key = 'run'
    elif enemy.ai_state == 'patrolling' and abs(enemy.vel.x) <= 0.1:
        animation_key = 'idle'
    # Add any other specific state-to-animation-key mappings here
    # Default to 'idle' if no other condition is met or if state is 'idle'
    elif enemy.state == 'idle':
        animation_key = 'idle'
    else: # Fallback for unhandled states or if current state is directly an animation key
        animation_key = enemy.state # e.g. if state was already set to 'run'


    # Validate if the determined animation key exists and is not a placeholder
    # (except for 'stone' and 'stone_smashed' which use direct image attributes from enemy_base)
    if animation_key not in ['stone', 'stone_smashed']:
        frames_for_key = enemy.animations.get(animation_key)
        is_placeholder = False
        if not frames_for_key:
            is_placeholder = True
        elif len(frames_for_key) == 1:
            frame_surf = frames_for_key[0]
            if frame_surf.get_size() == (30, 40) and \
               (frame_surf.get_at((0,0)) == C.RED or frame_surf.get_at((0,0)) == C.BLUE):
                is_placeholder = True
        
        if is_placeholder:
            if animation_key != 'idle': # Don't warn if 'idle' itself is the placeholder
                warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                        f"Animation for key '{animation_key}' (state: {enemy.state}) is missing or a placeholder. "
                        f"Falling back to 'idle'.")
            return 'idle' # Fallback to 'idle'
            
    return animation_key


def advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames_list, current_time_ms, current_animation_key):
    """
    Advances animation frame for the enemy and handles state transitions for non-looping animations.
    Modifies enemy.current_frame and can call set_enemy_state (via enemy instance).
    """
    animation_frame_duration_ms = getattr(C, 'ANIM_FRAME_DURATION', 100)

    # Petrified (not smashed) state uses a single frame, no advancement needed here.
    if enemy.is_petrified and not enemy.is_stone_smashed:
        enemy.current_frame = 0
        return

    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            if enemy.is_dead and not enemy.is_petrified: # Regular death animation (includes stomp_death visuals if they use 'death' key)
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True # Signal that the visual part is done
                # The enemy.kill() is usually called in the main update loop after this flag is set.
                return # Stay on last frame
            elif enemy.is_stone_smashed: # Smashed animation
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True # Smashed animation has visually completed
                return # Stay on last frame
            elif enemy.state == 'hit': # Hit animation finished
                # Transitioning out of 'hit' should be handled by enemy_state_handler or AI logic
                # based on hit_cooldown, not just animation end.
                # For now, we assume it goes to idle or fall, but this might be too simple.
                # Better: enemy_combat_handler sets is_taking_hit = False after cooldown,
                # then AI or base update loop transitions to idle/patrol.
                # This function just resets frame for looping if state doesn't change.
                from enemy_state_handler import set_enemy_state # Local import to avoid top-level circular
                set_enemy_state(enemy, 'idle' if enemy.on_ground else 'fall') # Example transition
                return # State changed, new animation will be handled
            elif enemy.is_attacking: # Attack animation finished
                # Transitioning out of attack is handled by AI logic (post_attack_pause_timer)
                # This means the attack animation should loop or hold last frame if AI keeps it in attack state.
                # For simplicity, we'll loop it if not handled by AI state change.
                enemy.current_frame = 0 # Loop attack anim if AI doesn't change state
            else: # Loop other animations
                enemy.current_frame = 0
    
    # Final boundary check for current_frame
    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy):
    """
    Updates the enemy's current image based on its state, frame, and facing direction.
    """
    if not enemy._valid_init or not hasattr(enemy, 'animations'):
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.MAGENTA)
        return

    # Only animate if alive OR if dead but death animation isn't finished OR if petrified (for stone visuals)
    can_animate_now = enemy.alive() or \
                      (enemy.is_dead and not enemy.death_animation_finished) or \
                      enemy.is_petrified

    if not can_animate_now:
        return

    current_time_ms = pygame.time.get_ticks()
    logical_animation_key = determine_enemy_animation_key(enemy)
    current_animation_frames = None

    # Fetch frames based on the determined key
    if logical_animation_key == 'stone':
        current_animation_frames = [enemy.stone_image_frame] if enemy.stone_image_frame else []
    elif logical_animation_key == 'stone_smashed':
        current_animation_frames = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
    else:
        current_animation_frames = enemy.animations.get(logical_animation_key)

    if not current_animation_frames:
        warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                f"No animation frames found for key '{logical_animation_key}' (State: {enemy.state}). "
                f"This shouldn't happen if determine_enemy_animation_key has proper fallbacks.")
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.BLUE)
        return

    # Advance frame and handle looping/transitions for non-looping animations
    advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames, current_time_ms, logical_animation_key)

    # Ensure current_frame is valid after potential state changes in advance_enemy_frame
    if logical_animation_key != enemy.state: # If state changed, re-determine frames
        logical_animation_key = determine_enemy_animation_key(enemy)
        if logical_animation_key == 'stone': current_animation_frames = [enemy.stone_image_frame]
        elif logical_animation_key == 'stone_smashed': current_animation_frames = enemy.stone_smashed_frames
        else: current_animation_frames = enemy.animations.get(logical_animation_key, [])
        if not current_animation_frames: # Should be very rare
            if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.BLUE); return
        # player.current_frame should have been reset by set_state if it was called

    if not current_animation_frames: # Final safety for frame list
         if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.YELLOW); return
    if enemy.current_frame < 0 or enemy.current_frame >= len(current_animation_frames):
        enemy.current_frame = 0 # Safeguard if state change didn't reset frame correctly

    image_for_this_frame = current_animation_frames[enemy.current_frame]

    # Determine facing direction for display
    current_display_facing_right = enemy.facing_right
    if enemy.is_petrified: # Petrified enemies use facing direction at time of petrification
        current_display_facing_right = enemy.facing_at_petrification

    # Flip image if necessary (stone images are already pre-oriented by set_state)
    if not enemy.is_petrified and not current_display_facing_right:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # Update image and rect only if necessary
    if enemy.image is not image_for_this_frame or enemy._last_facing_right != current_display_facing_right:
        old_enemy_midbottom_pos = enemy.rect.midbottom
        enemy.image = image_for_this_frame
        enemy.rect = enemy.image.get_rect(midbottom=old_enemy_midbottom_pos)
        enemy._last_facing_right = current_display_facing_right