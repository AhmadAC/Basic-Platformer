# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.16 (Corrected looping logic for animations)
Handles player animation selection and frame updates.
Correctly anchors the player's rect when height changes (e.g., crouching),
ensuring the player's feet (midbottom) remain consistent, and updates player.pos.
"""
import pygame
import constants as C
from utils import PrintLimiter # Assuming PrintLimiter is accessible

# It's good practice to import specific functions if the module is large
# or to avoid circular dependencies if player_state_handler also imports from here.
# For now, a direct import is fine if player_state_handler does not import this module.
try:
    from player_state_handler import set_player_state
except ImportError:
    # Fallback or error handling if direct import fails
    def set_player_state(player, new_state):
        if hasattr(player, 'set_state'): # Check for direct method on player
            player.set_state(new_state)
        else:
            print(f"CRITICAL PLAYER_ANIM_HANDLER: player_state_handler.set_player_state not found for Player ID {getattr(player, 'player_id', 'N/A')}")


def determine_animation_key(player):
    """
    Determines the correct animation key based on the player's current logical state and flags.
    This function prioritizes certain states over others (e.g., status effects over movement).
    """
    animation_key = player.state # Start with the current logical state as a base
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    # Highest priority: Petrified / Smashed states
    if player.is_petrified:
        return 'smashed' if player.is_stone_smashed else 'petrified'

    # Next priority: Death states (if not petrified)
    if player.is_dead:
        is_still_nm = abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0 # Check if "no movement" for death
        key_variant = 'death_nm' if is_still_nm else 'death'
        return key_variant if player.animations.get(key_variant) else \
               ('death' if player.animations.get('death') else 'idle') # Fallback to idle if specific death anims missing

    # Status effects like aflame, frozen (these override most other actions visually)
    if player.is_aflame: # This flag is true for initial 'aflame' and looping 'burning' states
        # player.state should correctly be 'aflame', 'burning', 'aflame_crouch', or 'burning_crouch'
        # if apply_aflame_effect and player state updates are working correctly.
        # We trust player.state here if it's already a fire state.
        if player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch'] and \
           player.animations.get(player.state):
            return player.state
        # Fallback if state isn't a specific fire anim, but is_aflame is true
        if player.is_crouching:
            return 'burning_crouch' if player.animations.get('burning_crouch') else \
                   ('aflame_crouch' if player.animations.get('aflame_crouch') else 'aflame') # Default to standing if crouch burn missing
        else:
            return 'burning' if player.animations.get('burning') else 'aflame'

    if player.is_deflaming: # This flag is true for 'deflame' and 'deflame_crouch'
        if player.state in ['deflame', 'deflame_crouch'] and \
           player.animations.get(player.state):
            return player.state
        # Fallback
        return 'deflame_crouch' if player.is_crouching and player.animations.get('deflame_crouch') else \
               ('deflame' if player.animations.get('deflame') else 'idle') # Default to standing if crouch deflame missing

    if player.is_frozen and player.animations.get('frozen'):
        return 'frozen'
    if player.is_defrosting and player.animations.get('defrost'):
        return 'defrost'

    # Action states
    if player.is_attacking:
        base_key = ''
        if player.attack_type == 1: base_key = 'attack'
        elif player.attack_type == 2: base_key = 'attack2'
        elif player.attack_type == 3: base_key = 'attack_combo' # Combo hit
        elif player.attack_type == 4: base_key = 'crouch_attack' # Crouch attack

        if base_key == 'crouch_attack' and player.animations.get(base_key):
            animation_key = base_key
        elif base_key: # For standing attacks
            nm_variant = f"{base_key}_nm"       # No-movement variant
            moving_variant = base_key           # Standard (moving) variant

            # Prioritize moving variant if intending to move and it exists
            if player_is_intending_to_move_lr and player.animations.get(moving_variant):
                animation_key = moving_variant
            # Else, try no-movement variant if it exists
            elif player.animations.get(nm_variant):
                animation_key = nm_variant
            # Else, fall back to standard (moving) variant if it exists
            elif player.animations.get(moving_variant):
                animation_key = moving_variant
            # Else, if no specific attack anim found, keep current player.state (might be an error or default)
            else: animation_key = player.state
        # If base_key was empty (e.g., attack_type not set), animation_key remains player.state
    elif player.state == 'wall_climb': # Specific handling for wall_climb sub-states
        # Check if actively pressing UP (or mapped climb key) and velocity matches climb speed
        is_actively_climbing = player.is_holding_climb_ability_key and \
                               abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1 # Allow small tolerance
        key_variant = 'wall_climb' if is_actively_climbing else 'wall_climb_nm'
        if player.animations.get(key_variant): animation_key = key_variant
        elif player.animations.get('wall_climb'): animation_key = 'wall_climb' # Fallback if _nm missing
    elif player.state == 'hit':
        animation_key = 'hit' # 'hit' state is usually set explicitly
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0):
        animation_key = 'fall' # General falling state
    elif player.on_ladder:
        animation_key = 'ladder_climb' if abs(player.vel.y) > 0.1 else 'ladder_idle'
    elif player.is_dashing:
        animation_key = 'dash'
    elif player.is_rolling:
        animation_key = 'roll'
    elif player.is_sliding: # This handles the main sliding loop
        animation_key = 'slide'
    elif player.state == 'slide_trans_start': # Transition into slide
        animation_key = 'slide_trans_start'
    elif player.state == 'slide_trans_end': # Transition out of slide
        animation_key = 'slide_trans_end'
    elif player.state == 'crouch_trans': # Transition into crouch
        animation_key = 'crouch_trans'
    elif player.state == 'turn': # Turning around
        animation_key = 'turn'
    elif player.state == 'jump': # Initial jump phase
        animation_key = 'jump'
    elif player.state == 'jump_fall_trans': # Transition from jump peak to fall
        animation_key = 'jump_fall_trans'
    elif player.state == 'wall_slide':
        animation_key = 'wall_slide'
    elif player.state == 'wall_hang':
        animation_key = 'wall_hang'
    elif player.on_ground: # Grounded states (default to these if no other override)
        if player.is_crouching:
            key_variant = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
            if player.animations.get(key_variant): animation_key = key_variant
            elif player.animations.get('crouch'): animation_key = 'crouch' # Fallback if crouch_walk missing
        elif player_is_intending_to_move_lr:
            animation_key = 'run'
        else: # Not moving, not crouching
            animation_key = 'idle'
    else: # In air, but not specifically jumping, falling, or wall interacting
        # This is a general "in-air" fallback if no other conditions met.
        # Could be after a dash/roll ends in air.
        if player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang', 'wall_climb', 'wall_climb_nm', 'hit', 'dash', 'roll']:
             animation_key = 'fall' if player.animations.get('fall') else 'idle' # Fallback to idle if 'fall' missing

    # Final check: if the determined key is not in animations (and not a special stone state), fallback to 'idle'
    if animation_key not in ['petrified', 'smashed']: # These use dedicated image attributes, not player.animations
        if not player.animations.get(animation_key):
            if player.print_limiter.can_print(f"anim_key_final_fallback_{player.player_id}_{animation_key}_{player.state}"):
                print(f"ANIM_HANDLER Warning (P{player.player_id}): Final animation key '{animation_key}' (State: '{player.state}') "
                      f"is invalid/missing. Falling back to 'idle'.")
            return 'idle'
    return animation_key


def advance_frame_and_handle_state_transitions(player, current_animation_frames_list, current_time_ms, current_animation_key):
    """
    Advances the animation frame for the player.
    Handles state transitions for animations that play once and then change state.
    """
    ms_per_frame = C.ANIM_FRAME_DURATION
    # Adjust animation speed for specific attacks if needed
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    # Petrified (non-smashed) state uses a single frame, no advancement needed here.
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0 # Ensure it's on the first (only) frame
        return

    # Define animations that play once and then trigger a state change.
    non_looping_anim_keys_with_transitions = [
        'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
        'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
        'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end',
        'aflame',           # Initial standing fire animation
        'aflame_crouch'     # Initial crouched fire animation
    ]
    # Define animations that play once and then hold their last frame visually.
    # The actual logical state change for these is handled by timers in player.py (update_status_effects).
    non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost'] # 'frozen' also holds, but it's a continuous state.


    # Only advance frame if not dead & finished, or if petrified and smashed (smashed has an animation)
    if not (player.is_dead and player.death_animation_finished and not player.is_petrified) or player.is_stone_smashed:
        if current_time_ms - player.last_anim_update > ms_per_frame:
            player.last_anim_update = current_time_ms
            player.current_frame += 1

            # Check if animation has finished
            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead and not player.is_petrified: # For regular death animations
                    player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame of death
                    player.death_animation_finished = True
                    return # No further state change from here for normal death
                elif player.is_stone_smashed: # For smashed petrification
                    # Smashed animation might loop or hold last frame depending on GIF content.
                    # For now, assume it holds last frame visually until timer in player.py kills the sprite.
                    player.current_frame = len(current_animation_frames_list) -1
                    # player.death_animation_finished can be set here if the anim is truly "done"
                    # but the object persists due to STONE_SMASHED_DURATION_MS
                    return

                # Determine if current animation is one that transitions OR holds its last frame
                is_non_looping_with_transition = current_animation_key in non_looping_anim_keys_with_transitions
                is_non_looping_hold_frame = current_animation_key in non_looping_hold_last_frame_keys

                if is_non_looping_with_transition:
                    # Logic to determine the next state after a non-looping animation completes
                    next_logical_state = player.state # Default to no change if conditions below aren't met
                    player_is_intending_to_move = player.is_trying_to_move_left or player.is_trying_to_move_right

                    if current_animation_key == 'aflame': # Initial standing fire done
                        if player.is_aflame: # Check if still logically aflame
                            next_logical_state = 'burning_crouch' if player.is_crouching else 'burning'
                    elif current_animation_key == 'aflame_crouch': # Initial crouched fire done
                        if player.is_aflame:
                            next_logical_state = 'burning' if not player.is_crouching else 'burning_crouch'
                    elif current_animation_key == 'jump':
                        next_logical_state = 'jump_fall_trans' if player.animations.get('jump_fall_trans') else 'fall'
                    elif current_animation_key == 'jump_fall_trans':
                        next_logical_state = 'fall'
                    elif current_animation_key == 'hit':
                        player.is_taking_hit = False # Hit stun visual animation is over
                        # Next state depends on fire status or regular idle/fall
                        if player.is_aflame: next_logical_state = 'burning_crouch' if player.is_crouching else 'burning'
                        elif player.is_deflaming: next_logical_state = 'deflame_crouch' if player.is_crouching else 'deflame'
                        else: next_logical_state = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                    elif current_animation_key == 'turn':
                        next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif 'attack' in current_animation_key: # Covers attack, attack_nm, attack2, etc.
                        player.is_attacking = False; player.attack_type = 0 # Reset attack flags
                        if player.on_ladder: next_logical_state = 'ladder_idle'
                        elif player.is_crouching: next_logical_state = 'crouch'
                        elif not player.on_ground: next_logical_state = 'fall'
                        else: next_logical_state = 'run' if player_is_intending_to_move else 'idle'
                    elif current_animation_key == 'crouch_trans':
                        next_logical_state = 'crouch_walk' if player_is_intending_to_move else 'crouch'
                    elif current_animation_key == 'slide_trans_start':
                        next_logical_state = 'slide'
                    elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                        player.is_sliding = False # Slide action is over
                        next_logical_state = 'crouch' if player.is_holding_crouch_ability_key else 'idle'
                    elif current_animation_key == 'dash':
                        player.is_dashing = False; next_logical_state = 'idle' if player.on_ground else 'fall'
                    elif current_animation_key == 'roll':
                        player.is_rolling = False; next_logical_state = 'idle' if player.on_ground else 'fall'

                    # If a state transition is determined, set it
                    if player.state == current_animation_key and next_logical_state != player.state : # Ensure it's a real change
                        set_player_state(player, next_logical_state) # Use the handler to set state
                        return # State changed, animation will be updated in next call
                    else:
                        # If no specific transition, default to looping the current anim or resetting to frame 0
                        # This path might be hit if, e.g., an attack animation finishes but player.state was already changed by external logic.
                        player.current_frame = 0
                
                elif is_non_looping_hold_frame:
                    player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                    # State change for these (like deflame -> idle) is triggered by timers in player.update_status_effects
                
                else: # Otherwise, it's a looping animation
                    player.current_frame = 0

    # Final boundary check for frame index, especially important if current_animation_frames_list is empty or short.
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0 # Always frame 0 for static petrified
    elif not current_animation_frames_list or player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player):
    """
    Updates the player's current animation frame and image.
    Also handles changes in player height due to crouching/standing.
    """
    if not player._valid_init:
        # If animations failed to load entirely, player.animations might be None
        if not hasattr(player, 'animations') or not player.animations:
             if hasattr(player, 'image') and player.image: player.image.fill(C.MAGENTA) # Visual error indicator
             return

    # Only animate if alive, or if dead but death animation isn't finished (and not petrified)
    if not player.alive() and not (player.is_dead and not player.death_animation_finished and not player.is_petrified):
        return

    current_time_ms = pygame.time.get_ticks()
    determined_animation_key = determine_animation_key(player)
    
    current_animation_frames = None
    if determined_animation_key == 'petrified':
        if player.was_crouching_when_petrified:
            current_animation_frames = [player.stone_crouch_image_frame] if player.stone_crouch_image_frame else []
        else:
            current_animation_frames = [player.stone_image_frame] if player.stone_image_frame else []
    elif determined_animation_key == 'smashed':
        if player.was_crouching_when_petrified:
            current_animation_frames = player.stone_crouch_smashed_frames if player.stone_crouch_smashed_frames else []
        else:
            current_animation_frames = player.stone_smashed_frames if player.stone_smashed_frames else []
    else:
        current_animation_frames = player.animations.get(determined_animation_key)

    # Fallback if the determined animation is missing or invalid
    if not current_animation_frames:
        if player.print_limiter.can_print(f"anim_frames_missing_update_{player.player_id}_{determined_animation_key}"):
            print(f"CRITICAL ANIM_HANDLER (P{player.player_id}): Frames for key '{determined_animation_key}' (State: {player.state}) are missing AT UPDATE. Using RED.")
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED) # Visual error
        return # Cannot proceed without frames

    # --- Advance frame and handle transitions based on the CURRENT animation key ---
    # This call might change player.state if an animation sequence ends.
    key_used_for_advance = determined_animation_key # Store the key used for frame advancement logic
    advance_frame_and_handle_state_transitions(player, current_animation_frames, current_time_ms, key_used_for_advance)

    # --- Re-determine animation key for RENDERING if state changed during advance_frame ---
    # This ensures the visual animation immediately reflects any new state.
    render_animation_key = determined_animation_key
    if player.state != determined_animation_key: # If player.state was changed by advance_frame...
        new_key_for_render = determine_animation_key(player) # ...get the new key based on the new state.
        if new_key_for_render != determined_animation_key: # If it's actually different...
            render_animation_key = new_key_for_render
            # Update current_animation_frames to the frames for the new render_animation_key
            if render_animation_key == 'petrified':
                current_animation_frames = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_animation_key == 'smashed':
                current_animation_frames = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            else:
                new_frames_for_render = player.animations.get(render_animation_key)
                if new_frames_for_render:
                    current_animation_frames = new_frames_for_render
                else: # Fallback if new render key has no frames
                    if player.print_limiter.can_print(f"anim_frames_missing_render_post_trans_{player.player_id}_{render_animation_key}"):
                         print(f"ANIM_HANDLER Warning (P{player.player_id}): Frames for re-determined render key '{render_animation_key}' missing. Image may be inconsistent.")
                    # Keep current_animation_frames as is (from before state change) or fallback further if needed
                    if not current_animation_frames: # If it somehow became None
                        current_animation_frames = player.animations.get('idle', [player.image]) # Last resort

    # Ensure current_animation_frames is valid before indexing
    if not current_animation_frames: # Should be caught by earlier checks, but safeguard
        if hasattr(player, 'image') and player.image: player.image.fill(C.BLUE); return

    # Ensure player.current_frame is valid for current_animation_frames
    if player.current_frame < 0 or player.current_frame >= len(current_animation_frames):
        player.current_frame = 0 # Reset to first frame if index is out of bounds
        if not current_animation_frames: # Extremely defensive
            if hasattr(player, 'image') and player.image: player.image.fill(C.YELLOW); return

    # Get the actual image surface for this frame
    image_for_this_frame = current_animation_frames[player.current_frame]

    # Determine if image needs flipping based on facing direction
    # For petrified/smashed, use facing_at_petrification
    should_flip = not player.facing_right
    if render_animation_key == 'petrified' or render_animation_key == 'smashed':
        should_flip = not player.facing_at_petrification

    if should_flip:
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)

    # --- Apply the new image and handle rect adjustments ---
    # Only update if the image surface itself changes OR if the facing direction that affects flip changes
    if player.image is not image_for_this_frame or \
       (render_animation_key not in ['petrified', 'smashed'] and player._last_facing_right != player.facing_right) or \
       ((render_animation_key == 'petrified' or render_animation_key == 'smashed') and player._last_facing_right != player.facing_at_petrification):
        
        old_rect_midbottom = player.rect.midbottom # Preserve the feet position
        old_rect_height_for_debug = player.rect.height # For debugging height changes

        player.image = image_for_this_frame
        player.rect = player.image.get_rect(midbottom=old_rect_midbottom) # Anchor to old midbottom

        # CRITICAL: Update player.pos to match the new rect's midbottom after potential height change.
        # This ensures physics calculations use the correct reference point.
        player.pos = pygame.math.Vector2(player.rect.midbottom)

        # Debugging for height changes
        new_rect_height_for_debug = player.rect.height
        if old_rect_height_for_debug != new_rect_height_for_debug:
            if player.print_limiter.can_print(f"anim_height_change_{player.player_id}_{render_animation_key}"):
                print(f"DEBUG ANIM_H (P{player.player_id}): Height Change. Key:'{render_animation_key}'. "
                      f"OldH:{old_rect_height_for_debug}, NewH:{new_rect_height_for_debug}. "
                      f"Rect anchored to old_midbottom: {old_rect_midbottom}. New player.pos: {player.pos}")

        # Update _last_facing_right based on the direction used for flipping this frame
        if render_animation_key == 'petrified' or render_animation_key == 'smashed':
            player._last_facing_right = player.facing_at_petrification
        else:
            player._last_facing_right = player.facing_right