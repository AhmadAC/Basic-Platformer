#################### START OF MODIFIED FILE: enemy_animation_handler.py ####################

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
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): # Fallback to old direct method if new handler isn't imported yet
            enemy.set_state(new_state)
        else:
            print(f"CRITICAL ENEMY_ANIM_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


def determine_enemy_animation_key(enemy):
    """
    Determines the correct animation key based on the enemy's current logical state and flags.
    Prioritizes status effect visuals (petrified, aflame, frozen) over transient states like 'hit'.
    Returns the animation key string.
    """
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')
    animation_key = enemy.state 

    if enemy.is_petrified:
        return 'stone_smashed' if enemy.is_stone_smashed else 'stone'

    if enemy.is_dead:
        # MODIFIED: If stomp_dying, the visual is the scaled original image.
        # We can return 'idle' or a specific placeholder key if needed, but the image
        # itself is handled by the status effect. Let's make it return a key that
        # can correspond to the single original_stomp_death_image if used by `current_frames_list`.
        if enemy.is_stomp_dying:
            return 'stomp_death' # This key will be used to fetch enemy.original_stomp_death_image
        else: # Regular death
            is_still_nm = abs(enemy.vel.x) < 0.1 and abs(enemy.vel.y) < 0.1
            key_variant = 'death_nm' if is_still_nm and enemy.animations.get('death_nm') else 'death'
            if enemy.animations.get(key_variant): return key_variant
            if enemy.animations.get('death'): return 'death'
            return 'idle'

    if enemy.is_aflame: return 'aflame'
    if enemy.is_deflaming: return 'deflame'
    if enemy.is_frozen: return 'frozen'
    if enemy.is_defrosting: return 'defrost'

    if enemy.state == 'hit':
        return 'hit'

    if enemy.post_attack_pause_timer > 0 and pygame.time.get_ticks() < enemy.post_attack_pause_timer:
        return 'idle'

    if enemy.is_attacking:
        if 'attack' in enemy.state and enemy.animations.get(enemy.state):
            return enemy.state
        default_attack_key = 'attack_nm' if enemy.animations.get('attack_nm') else 'attack'
        return default_attack_key if enemy.animations.get(default_attack_key) else 'idle'

    if enemy.ai_state == 'chasing' or (enemy.ai_state == 'patrolling' and abs(enemy.vel.x) > 0.1):
        return 'run'
    if enemy.ai_state == 'patrolling' and abs(enemy.vel.x) <= 0.1:
        return 'idle'
    if not enemy.on_ground and enemy.state not in ['jump', 'jump_fall_trans']:
        return 'fall'
    
    if enemy.animations.get(enemy.state):
        return enemy.state

    warning(f"EnemyAnimHandler (ID: {enemy_id_log}, Color: {enemy.color_name}): "
            f"Could not determine specific animation for state '{enemy.state}'. Defaulting to 'idle'.")
    return 'idle'


def advance_enemy_frame_and_handle_transitions(enemy, current_animation_frames_list, current_time_ms, current_animation_key):
    animation_frame_duration_ms = getattr(C, 'ANIM_FRAME_DURATION', 100)

    if enemy.is_petrified and not enemy.is_stone_smashed:
        enemy.current_frame = 0
        return
        
    # MODIFIED: Stomp dying visual is handled by scaling, no frame cycling here.
    if enemy.is_stomp_dying:
        return

    if current_time_ms - enemy.last_anim_update > animation_frame_duration_ms:
        enemy.last_anim_update = current_time_ms
        enemy.current_frame += 1

        if enemy.current_frame >= len(current_animation_frames_list):
            if (enemy.is_dead and not enemy.is_petrified and not enemy.is_stomp_dying) or enemy.is_stone_smashed:
                enemy.current_frame = len(current_animation_frames_list) - 1
                enemy.death_animation_finished = True
                return
            elif current_animation_key == 'hit':
                debug(f"Enemy {enemy.enemy_id}: 'hit' animation finished. Transitioning based on ground state.")
                set_enemy_state(enemy, 'idle' if enemy.on_ground else 'fall')
                return
            elif 'attack' in current_animation_key:
                enemy.current_frame = 0
                debug(f"Enemy {enemy.enemy_id}: Attack animation '{current_animation_key}' looped/ended. AI will decide next state.")
            else:
                enemy.current_frame = 0

    if not current_animation_frames_list or enemy.current_frame < 0 or \
       enemy.current_frame >= len(current_animation_frames_list):
        enemy.current_frame = 0


def update_enemy_animation(enemy):
    if not enemy._valid_init or not hasattr(enemy, 'animations'):
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.MAGENTA)
        return

    # MODIFIED: If stomp_dying, visuals are handled by update_enemy_status_effects.
    # The image is already being scaled there. We should not interfere here.
    if enemy.is_stomp_dying:
        # We could potentially update enemy.rect.midbottom = enemy.pos if needed,
        # but the scaling function in status_effects should already be doing that.
        return

    can_animate_now = enemy.alive() or \
                      (enemy.is_dead and not enemy.death_animation_finished) or \
                      enemy.is_petrified

    if not can_animate_now:
        return

    current_time_ms = pygame.time.get_ticks()
    determined_key = determine_enemy_animation_key(enemy)
    
    current_frames_list = None
    if determined_key == 'stone':
        current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame else []
    elif determined_key == 'stone_smashed':
        current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
    # Stomp death frames are not used for cycling here; image is scaled by status_effects
    elif determined_key == 'stomp_death': 
        # This case should ideally not be normally processed here if is_stomp_dying is true
        # and update_enemy_status_effects is handling it.
        # If for some reason we reach here with stomp_death, use the captured image.
        current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image else enemy.animations.get('idle', [])
    else:
        current_frames_list = enemy.animations.get(determined_key)

    animation_is_actually_valid = True
    # ... (rest of animation_is_actually_valid check, fallback to 'idle' if needed) ...
    if not current_frames_list:
        animation_is_actually_valid = False
    elif len(current_frames_list) == 1 and determined_key not in ['stone', 'idle', 'run', 'fall', 'stomp_death']:
        frame_surf = current_frames_list[0]
        if frame_surf.get_size() == (30, 40): 
            pixel_color = frame_surf.get_at((0,0))
            if pixel_color == C.RED or pixel_color == C.BLUE: 
                animation_is_actually_valid = False
                debug(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                      f"Animation for key '{determined_key}' is a RED/BLUE placeholder. Will use idle.")

    if not animation_is_actually_valid:
        if determined_key != 'idle':
            warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                    f"Animation for determined key '{determined_key}' (logical state: {enemy.state}) is missing or a placeholder. "
                    f"Switching to 'idle' animation.")
        determined_key = 'idle'
        current_frames_list = enemy.animations.get('idle')
        if not current_frames_list or \
           (len(current_frames_list) == 1 and current_frames_list[0].get_size() == (30,40) and \
            (current_frames_list[0].get_at((0,0)) == C.RED or current_frames_list[0].get_at((0,0)) == C.BLUE)):
            critical(f"EnemyAnimHandler CRITICAL (ID: {enemy.enemy_id}, Color: {enemy.color_name}): "
                     f"Fallback 'idle' animation is ALSO missing/placeholder! Enemy visuals will be broken.")
            if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.MAGENTA)
            return

    if not current_frames_list: 
        critical(f"EnemyAnimHandler CRITICAL (ID: {enemy.enemy_id}): No frames for '{determined_key}' after all checks.")
        if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.BLUE)
        return
    
    # No frame advancement needed if it's a stomp_death visual (handled by scaling)
    if determined_key != 'stomp_death':
        advance_enemy_frame_and_handle_transitions(enemy, current_frames_list, current_time_ms, determined_key)

    # Re-determination of key if state changed, only if not stomp_death
    if enemy.state != determined_key and not (enemy.is_petrified and determined_key in ['stone', 'stone_smashed']) and determined_key != 'stomp_death':
        new_determined_key_after_transition = determine_enemy_animation_key(enemy)
        if new_determined_key_after_transition != determined_key:
            determined_key = new_determined_key_after_transition
            if determined_key == 'stone': current_frames_list = [enemy.stone_image_frame] if enemy.stone_image_frame else []
            elif determined_key == 'stone_smashed': current_frames_list = enemy.stone_smashed_frames if enemy.stone_smashed_frames else []
            elif determined_key == 'stomp_death': current_frames_list = [enemy.original_stomp_death_image] if enemy.original_stomp_death_image else []
            else: current_frames_list = enemy.animations.get(determined_key, [])
            
            if not current_frames_list:
                 warning(f"EnemyAnimHandler (ID: {enemy.enemy_id}): No frames for re-determined key '{determined_key}' after state transition. Using last valid image or placeholder.")
                 if not (hasattr(enemy, 'image') and enemy.image):
                     enemy.image = enemy._create_placeholder_surface(C.YELLOW, "AnimErr")
                     enemy.rect = enemy.image.get_rect(midbottom=enemy.pos)
                 return
    
    # If it is stomp_death, the image is ALREADY set by update_enemy_status_effects, so we skip image assignment here.
    if determined_key == 'stomp_death':
        # Optional: just ensure rect is synced with pos if anything external might have moved it
        # enemy.rect.midbottom = round(enemy.pos.x), round(enemy.pos.y)
        return

    if not current_frames_list or enemy.current_frame < 0 or enemy.current_frame >= len(current_frames_list):
        enemy.current_frame = 0
        if not current_frames_list:
             if hasattr(enemy, 'image') and enemy.image: enemy.image.fill(C.CYAN); return


    image_for_this_frame = current_frames_list[enemy.current_frame]

    current_display_facing_right = enemy.facing_right
    if enemy.is_petrified:
        current_display_facing_right = enemy.facing_at_petrification

    if not enemy.is_petrified and not current_display_facing_right:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # Debug print as before
    # if enemy.state == 'deflame' or (enemy.is_aflame and determined_key == 'aflame'):
    #     print(f"ENEMY_ANIMATE_DEBUG (ID {enemy.enemy_id}, Color {enemy.color_name}): "
    #           f"LogicState='{enemy.state}', AnimKey='{determined_key}', "
    #           f"FramesOK={current_frames_list is not None and len(current_frames_list) > 0 and animation_is_actually_valid}, "
    #           f"FrameIdx={enemy.current_frame}, is_aflame={enemy.is_aflame}, is_deflaming={enemy.is_deflaming}")

    # Update image only if it has actually changed or facing changed
    if enemy.image is not image_for_this_frame or enemy._last_facing_right != current_display_facing_right:
        old_enemy_midbottom_pos = enemy.rect.midbottom
        enemy.image = image_for_this_frame
        enemy.rect = enemy.image.get_rect(midbottom=old_enemy_midbottom_pos)
        enemy._last_facing_right = current_display_facing_right

#################### END OF MODIFIED FILE: enemy_animation_handler.py ####################