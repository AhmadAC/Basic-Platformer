# enemy_animation_handler.py
# -*- coding: utf-8 -*-
"""
# version 1.0.3 (Stomp death visual handled by status_effects scaler)
Handles animation selection and frame updates for Enemy instances.
Ensures correct visual representation based on logical state and manages
animation frame cycling and transitions.
"""
import pygame
import constants as C

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_ANIM_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Defined error for fallback
    def critical(msg): print(f"CRITICAL: {msg}")

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    # Fallback if direct import fails
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): # Check if the old method might still exist on the enemy instance
            enemy.set_state(new_state)
        else:
            critical(f"CRITICAL ENEMY_ANIM_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


def determine_enemy_animation_key(enemy):
    """
    Determines the correct animation key based on the enemy's current logical state and flags.
    Prioritizes status effect visuals (petrified, aflame, frozen) over transient states like 'hit'.
    Returns the animation key string.
    """
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    # Start with the enemy's current logical state as the default animation key
    animation_key = enemy.state 

    # Highest priority: Petrified / Smashed states
    if enemy.is_petrified: # This flag is true for both 'petrified' and 'smashed' states
        return 'smashed' if enemy.is_stone_smashed else 'petrified' # Visual key maps to 'stone' or 'stone_smashed'

    # Next priority: Death states (if not petrified)
    if enemy.is_dead:
        # If stomp_dying, the visual is a scaled version of its original_stomp_death_image.
        # The animation handler doesn't cycle frames for this; it's a transform.
        # We return a key that can correspond to this single image if needed, or 'idle' as a fallback
        # if the image assignment logic elsewhere expects a valid key from player.animations.
        if enemy.is_stomp_dying:
            return 'stomp_death' # This key can be used to fetch enemy.original_stomp_death_image
        else: # Regular death (not stomp, not petrified)
            is_still_nm = abs(enemy.vel.x) < 0.1 and abs(enemy.vel.y) < 0.1 # Check for no movement
            # Prefer 'death_nm' if available and no movement
            key_variant = 'death_nm' if is_still_nm and enemy.animations.get('death_nm') else 'death'
            if enemy.animations.get(key_variant): return key_variant
            if enemy.animations.get('death'): return 'death' # Fallback to standard 'death'
            return 'idle' # Ultimate fallback if no death animations

    # Status effects (aflame, frozen) - these override most other action visuals
    if enemy.is_aflame: return 'aflame' # Looping burn animation
    if enemy.is_deflaming: return 'deflame' # Fire going out animation
    if enemy.is_frozen: return 'frozen' # Static frozen image/animation
    if enemy.is_defrosting: return 'defrost' # Defrosting animation

    # Transient states like 'hit' (flinch animation)
    if enemy.state == 'hit': # Logical state is 'hit'
        return 'hit'

    # If in post-attack pause, usually show 'idle'
    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       pygame.time.get_ticks() < enemy.post_attack_pause_timer:
        return 'idle'

    # Attacking state
    if enemy.is_attacking:
        # enemy.state should be 'attack' or 'attack_nm' if set correctly by AI/state handler
        if 'attack' in enemy.state and enemy.animations.get(enemy.state):
            return enemy.state # Use the specific attack animation (e.g., 'attack_nm')
        # Fallback if enemy.state isn't a valid attack animation key
        default_attack_key = 'attack_nm' if enemy.animations.get('attack_nm') else 'attack'
        return default_attack_key if enemy.animations.get(default_attack_key) else 'idle'

    # Movement states (patrolling, chasing)
    if enemy.ai_state == 'chasing' or (enemy.ai_state == 'patrolling' and abs(enemy.vel.x) > 0.1):
        return 'run' # Use 'run' animation for movement
    if enemy.ai_state == 'patrolling' and abs(enemy.vel.x) <= 0.1: # Patrolling but currently still
        return 'idle'
    
    # In-air state (if not covered by other states like attack, hit, status effects)
    if not enemy.on_ground and enemy.state not in ['jump', 'jump_fall_trans']: # Assuming enemies don't typically 'jump'
        return 'fall'
    
    # Default to the enemy's current logical state if a specific animation exists for it
    if enemy.animations.get(enemy.state):
        return enemy.state

    # Ultimate fallback if no other specific animation key could be determined
    warning(f"EnemyAnimHandler (ID: {enemy_id_log}, Color: {enemy.color_name}): "
            f"Could not determine specific animation for logical state '{enemy.state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames_list, current_time_ms, current_animation_key):
    """
    Advances the enemy's animation frame.
    Handles transitions for animations that play once (e.g., 'hit', 'attack').
    """
    animation_frame_duration_ms = getattr(C, 'ANIM_FRAME_DURATION', 100) # Default anim speed

    # Petrified (non-smashed) uses a single static frame. No advancement needed.
    if enemy.is_petrified and not enemy.is_stone_smashed:
        enemy.current_frame = 0 # Ensure it's on the first (only) frame
        return
        
    # Stomp dying visual is a scale transform, not frame cycling. Handled by status_effects.
    if enemy.is_stomp_dying:
        return # No frame advancement here

    # Advance frame if enough time has passed
    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        # Check if animation sequence has finished
        if enemy.current_frame >= len(current_animation_frames_list):
            # --- Handle end of non-looping animations ---
            # Death animations (regular or smashed)
            if (enemy.is_dead and not enemy.is_petrified and not enemy.is_stomp_dying) or \
               (enemy.is_petrified and enemy.is_stone_smashed):
                enemy.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                enemy.death_animation_finished = True # Mark animation as visually complete
                return # No further state change from here; removal is handled by timer/main loop

            # 'hit' animation finished
            elif current_animation_key == 'hit':
                debug(f"Enemy {enemy.enemy_id}: 'hit' animation finished. Transitioning based on ground state.")
                # After hit, transition to idle if on ground, or fall if in air
                # Status effects like aflame will override this in determine_enemy_animation_key
                set_enemy_state(enemy, 'idle' if enemy.on_ground else 'fall')
                return # State changed, animation will be re-evaluated

            # 'attack' animation finished
            elif 'attack' in current_animation_key: # Covers 'attack', 'attack_nm'
                enemy.current_frame = 0 # Reset frame for potential next attack or other state
                # AI/State handler will determine next logical state after attack completes
                # (e.g., post-attack pause, then back to patrolling/chasing)
                debug(f"Enemy {enemy.enemy_id}: Attack animation '{current_animation_key}' looped/ended. AI will decide next state.")
                # No explicit state change here, is_attacking flag will be reset by AI or state handler
            
            # Default for other (looping) animations
            else:
                enemy.current_frame = 0 # Loop animation

    # Ensure current_frame is always valid for the current list
    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0 # Default to first frame if out of bounds


def update_enemy_animation(enemy):
    """
    Updates the enemy's current animation frame and image based on its state.
    """
    if not enemy._valid_init or not hasattr(enemy, 'animations'): # Check for valid init and animations dict
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.MAGENTA) # Visual error
        return

    # If stomp_dying, visuals are handled by scaling in update_enemy_status_effects.
    # The image is already being transformed there. We should not interfere here.
    if enemy.is_stomp_dying:
        # Optional: Ensure rect is synced with pos if anything external might have moved it,
        # but status_effects should already handle this.
        # enemy.rect.midbottom = round(enemy.pos.x), round(enemy.pos.y)
        return # Visuals handled elsewhere

    # Determine if enemy should be animating (alive, or dead but animation not finished, or petrified)
    can_animate_now = enemy.alive() or \
                      (enemy.is_dead and not enemy.death_animation_finished) or \
                      enemy.is_petrified # Petrified (smashed or not) has a visual state

    if not can_animate_now: # If truly gone or death animation fully complete and not petrified
        return

    current_time_ms = pygame.time.get_ticks()
    determined_key = determine_enemy_animation_key(enemy) # Get the animation key for the current state
    
    # Get the list of frames for the determined animation key
    current_frames_list = None
    if determined_key == 'petrified': # Special handling for single-frame petrified state
        current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame else []
    elif determined_key == 'smashed': # Special handling for multi-frame smashed animation
        current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
    elif determined_key == 'stomp_death': # Should be caught by is_stomp_dying check above
        # Fallback if somehow reached here for stomp_death: use the captured image
        current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image else enemy.animations.get('idle', [])
    else: # Standard animations from the enemy's dictionary
        current_frames_list = enemy.animations.get(determined_key)

    # --- Validate the chosen animation frames ---
    animation_is_actually_valid = True
    if not current_frames_list: # No frames found for the key
        animation_is_actually_valid = False
    elif len(current_frames_list) == 1 and determined_key not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'stomp_death']:
        # If it's a single-frame animation for a non-static state, check if it's a placeholder
        frame_surf = current_frames_list[0]
        if frame_surf.get_size() == (30, 40): # Common placeholder size
            pixel_color = frame_surf.get_at((0,0))
            if pixel_color == C.RED or pixel_color == C.BLUE: # Placeholder colors
                animation_is_actually_valid = False
                debug(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                      f"Animation for key '{determined_key}' is a RED/BLUE placeholder. Will use idle.")

    # If animation is not valid, fall back to 'idle'
    if not animation_is_actually_valid:
        if determined_key != 'idle': # Avoid redundant warning if already trying idle
            warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                    f"Animation for determined key '{determined_key}' (logical state: {enemy.state}) is missing or a placeholder. "
                    f"Switching to 'idle' animation.")
        determined_key = 'idle' # Update key to 'idle'
        current_frames_list = enemy.animations.get('idle') # Get idle frames
        
        # Critical check: if even 'idle' is missing/placeholder, then visuals are broken
        if not current_frames_list or \
           (len(current_frames_list) == 1 and current_frames_list[0].get_size() == (30,40) and \
            (current_frames_list[0].get_at((0,0)) == C.RED or current_frames_list[0].get_at((0,0)) == C.BLUE)):
            critical(f"EnemyAnimHandler CRITICAL (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                     f"Fallback 'idle' animation is ALSO missing/placeholder! Enemy visuals will be broken.")
            if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.MAGENTA) # Magenta error
            return # Cannot proceed

    if not current_frames_list: # Should be caught by above, but defensive check
        critical(f"EnemyAnimHandler CRITICAL (ID: {enemy.enemy_id}): No frames for '{determined_key}' after all checks.")
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.BLUE) # Blue error
        return
    
    # --- Advance frame and handle state transitions (if not stomp_death, which is handled by scaling) ---
    # Stomp death visual is a scale transform, not frame cycling.
    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    # --- Re-determine animation key for RENDERING if state changed during advance_frame ---
    # This is important if an animation finishes and transitions the enemy to a new logical state.
    # Skip if it's stomp_death, as that state and visual are tightly coupled.
    if enemy.state != determined_key and \
       not (enemy.is_petrified and determined_key in ['petrified', 'smashed']) and \
       determined_key != 'stomp_death':
        
        new_determined_key_after_transition = determine_enemy_animation_key(enemy)
        if new_determined_key_after_transition != determined_key: # If key actually changed
            determined_key = new_determined_key_after_transition # Update key for rendering
            # Update current_frames_list based on the new key
            if determined_key == 'petrified': current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame else []
            elif determined_key == 'smashed': current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
            elif determined_key == 'stomp_death': current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image else []
            else: current_frames_list = enemy.animations.get(determined_key, []) # Get frames for new key
            
            # Fallback if new key has no frames (should be rare if determine_enemy_animation_key has good fallbacks)
            if not current_frames_list:
                 warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}): No frames for re-determined key '{determined_key}' after state transition. Using last valid image or placeholder.")
                 # If image attribute exists, it will retain the last valid frame. If not, create placeholder.
                 if not (hasattr(enemy, 'image') and enemy.image):
                     enemy.image = enemy._create_placeholder_surface(C.YELLOW, "AnimErr") # Assuming _create_placeholder_surface exists
                     if hasattr(enemy, 'pos'): # Try to position placeholder correctly
                         enemy.rect = enemy.image.get_rect(midbottom=enemy.pos)
                 return # Stop further animation update this frame if frames are missing for new state
    
    # If it IS stomp_death, the image is ALREADY set and scaled by update_enemy_status_effects.
    # We should skip the standard image assignment logic below.
    if determined_key == 'stomp_death':
        # Rect and pos should be managed by the scaling logic in status_effects.
        # If needed, ensure rect is synced: enemy.rect.midbottom = round(enemy.pos.x), round(enemy.pos.y)
        return

    # --- Final check on frame index and get the image for this frame ---
    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0 # Reset to first frame if index is out of bounds
        # if not current_frames_list: # Should be impossible if earlier checks passed, but very defensive
            #  if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.CYAN); return # 


    image_for_this_frame = current_frames_list[enemy.current_frame]

    # --- Handle image flipping based on facing direction ---
    # For petrified states, use the direction enemy was facing when petrified.
    current_display_facing_right = enemy.facing_right
    if enemy.is_petrified: # Covers both 'petrified' and 'smashed' states
        current_display_facing_right = enemy.facing_at_petrification

    # Flip image if not facing right (and not petrified, as petrified images are pre-oriented)
    # Actually, petrified images from common assets might also need flipping.
    # The stone_image_frame and stone_smashed_frames on the enemy instance should be
    # the correctly oriented versions.
    if not current_display_facing_right:
        # This assumes that `enemy.stone_image_frame` and `enemy.stone_smashed_frames`
        # are already correctly flipped if `facing_at_petrification` was False.
        # So, if `image_for_this_frame` comes directly from those, it's already oriented.
        # If it comes from `enemy.animations`, then flip is needed.
        if not (determined_key == 'petrified' or determined_key == 'smashed'):
            image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # --- Update enemy's image and rect if changed ---
    # Only update if the image surface itself is different OR if the facing direction (that affects flip) has changed.
    if enemy.image is not image_for_this_frame or enemy._last_facing_right != current_display_facing_right:
        old_enemy_midbottom_pos = enemy.rect.midbottom # Preserve position
        
        enemy.image = image_for_this_frame
        enemy.rect = enemy.image.get_rect(midbottom=old_enemy_midbottom_pos) # Re-anchor
        
        # Update pos based on new rect to ensure consistency (physics uses pos)
        enemy.pos = pygame.math.Vector2(enemy.rect.midbottom)
        
        enemy._last_facing_right = current_display_facing_right # Store facing for next frame's check