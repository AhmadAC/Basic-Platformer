# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.5 (Disabled fireball while crouching)
Handles processing of player input and translating it to actions.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C # For C.PLAYER_ACCEL, C.PLAYER_JUMP_STRENGTH etc.
# No direct need for player_state_handler here as set_state is a method of Player.

def process_player_input_logic(player, keys_pressed, pygame_events, key_config_map):
    """
    Core logic for processing raw Pygame input (held keys and events)
    into player actions and state changes.
    Modifies the 'player' instance directly based on the input and key configuration.

    Args:
        player (Player): The player instance to be controlled.
        keys_pressed (pygame.key.ScancodeWrapper): Snapshot of currently held keys
                                                   (from pygame.key.get_pressed()).
        pygame_events (list): List of Pygame events for the current frame
                              (from pygame.event.get()).
        key_config_map (dict): A dictionary mapping action strings
                               (e.g., 'left', 'attack1') to Pygame key constants
                               (e.g., pygame.K_a, pygame.K_v).
    """
    if not player._valid_init: return # Do nothing if player initialization failed

    current_time_ms = pygame.time.get_ticks() # For managing state timers and cooldowns

    # --- Determine if player input should be blocked ---
    # (e.g., player is dead, stunned, or in a non-interruptible animation)
    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration)

    if is_input_blocked:
        player.acc.x = 0 # Stop acceleration if input is blocked
        # Potentially reset other input intention flags if needed
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        # player.is_holding_crouch_ability_key = False # Keep this for now, as player might still be crouched
        return

    # --- Update Player Input Intention Flags (for continuous actions like movement/aiming) ---
    player.is_trying_to_move_left = keys_pressed[key_config_map['left']]
    player.is_trying_to_move_right = keys_pressed[key_config_map['right']]
    player.is_holding_climb_ability_key = keys_pressed[key_config_map['up']] # Used for ladder climb, wall climb intent
    player.is_holding_crouch_ability_key = keys_pressed[key_config_map['down']] # Used for ladder down, crouch toggle/hold, aim

    # Update fireball aim direction based on current held keys
    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if keys_pressed[key_config_map['left']]: fireball_aim_x_input = -1.0
    elif keys_pressed[key_config_map['right']]: fireball_aim_x_input = 1.0

    # Note: 'up' for aiming up, 'down' (is_holding_crouch_ability_key) for aiming down
    if keys_pressed[key_config_map['up']]: fireball_aim_y_input = -1.0
    elif player.is_holding_crouch_ability_key: fireball_aim_y_input = 1.0 # Aim down if crouch key is held

    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0: # Fallback if no directional input (shouldn't usually happen if aiming)
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    # --- Horizontal Movement Acceleration based on Input ---
    player.acc.x = 0 # Reset horizontal acceleration each frame
    player_intends_horizontal_move = False # Flag to see if player wants to move left/right

    # Determine if player can currently control horizontal movement
    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or # Non-moving attacks
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang'] # States that override movement
    )

    if can_player_control_horizontal_movement:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']: # Condition for turning
                player.set_state('turn')
            player.facing_right = False # Always update facing direction
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']: # Condition for turning
                player.set_state('turn')
            player.facing_right = True # Always update facing direction

    # --- Ladder Movement (overrides normal Y velocity if on ladder) ---
    if player.on_ladder:
         player.vel.y = 0 # Neutralize gravity/previous Y velocity
         if player.is_holding_climb_ability_key: # Holding 'up'
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif player.is_holding_crouch_ability_key: # Holding 'down'
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    # --- Process Discrete Key Presses (Events) for Actions ---
    for event in pygame_events:
        if event.type == pygame.KEYDOWN:
            # --- Jump Action ---
            if event.key == key_config_map['up']:
                  can_perform_jump_action = not player.is_attacking and \
                                            not player.is_rolling and not player.is_sliding and \
                                            not player.is_dashing and \
                                            player.state not in ['turn','hit','death','death_nm']
                  if can_perform_jump_action:
                      if player.on_ground:
                          if player.is_crouching: player.is_crouching = False # Stand up to jump
                          player.vel.y = C.PLAYER_JUMP_STRENGTH
                          player.set_state('jump')
                          player.on_ground = False
                      elif player.on_ladder: # Jump off ladder
                          player.is_crouching = False # Ensure not crouching
                          player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8 # Slightly weaker jump off ladder
                          player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1) # Small horizontal push
                          player.on_ladder = False
                          player.set_state('jump')
                      elif player.can_wall_jump and player.touching_wall != 0: # Wall Jump
                          player.is_crouching = False # Ensure not crouching
                          player.vel.y = C.PLAYER_JUMP_STRENGTH
                          player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall) # Push away from wall
                          player.facing_right = not player.facing_right # Turn around
                          player.set_state('jump')
                          player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0

            # --- Attack 1 Action ---
            if event.key == key_config_map['attack1']:
                  can_perform_attack_action = not player.is_attacking and not player.is_dashing and \
                                              not player.is_rolling and not player.is_sliding and \
                                              not player.on_ladder and player.state not in ['turn','hit']
                  if can_perform_attack_action:
                       player.attack_type = 1
                       is_moving_for_attack_anim = (player.acc.x !=0 or abs(player.vel.x) > 1.0)
                       # Determine animation based on movement and crouch state
                       if player.is_crouching:
                           player.attack_type = 4 # Specific type for crouch attack
                           attack_animation_key = 'crouch_attack'
                       elif is_moving_for_attack_anim and 'attack' in player.animations and player.animations['attack']:
                           attack_animation_key = 'attack'
                       else:
                           attack_animation_key = 'attack_nm' # Default to non-moving variant
                       player.set_state(attack_animation_key)

            # --- Attack 2 / Combo Action ---
            if event.key == key_config_map['attack2']:
                  can_perform_attack2_action = not player.is_dashing and not player.is_rolling and \
                                               not player.is_sliding and not player.on_ladder and \
                                               player.state not in ['turn','hit']
                  if can_perform_attack2_action:
                       is_moving_for_attack2_anim = (player.acc.x != 0 or abs(player.vel.x) > 1.0)
                       time_since_attack1_ended = current_time_ms - (player.attack_timer + player.attack_duration)
                       is_in_combo_window_for_attack3 = (player.attack_type == 1 and not player.is_attacking and
                                                         time_since_attack1_ended < player.combo_window)
                       selected_attack2_anim_key = ''

                       if is_in_combo_window_for_attack3 and \
                          'attack_combo' in player.animations and player.animations['attack_combo']:
                           player.attack_type = 3 # Combo attack
                           selected_attack2_anim_key = 'attack_combo' if is_moving_for_attack2_anim and player.animations.get('attack_combo') else 'attack_combo_nm'
                       elif player.is_crouching and 'crouch_attack' in player.animations and \
                            player.animations['crouch_attack'] and not player.is_attacking : # Can crouch attack with this key too
                           player.attack_type = 4; selected_attack2_anim_key = 'crouch_attack'
                       elif not player.is_attacking and 'attack2' in player.animations and player.animations['attack2']: # Standard Attack 2
                           player.attack_type = 2
                           selected_attack2_anim_key = 'attack2' if is_moving_for_attack2_anim and player.animations.get('attack2') else 'attack2_nm'
                       # Fallback: if no other attack state, Attack 2 key might initiate Attack 1
                       elif not player.is_attacking and player.attack_type == 0 and \
                            'attack' in player.animations and player.animations['attack']:
                           player.attack_type = 1
                           selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim and player.animations.get('attack') else 'attack_nm'

                       if selected_attack2_anim_key and player.animations.get(selected_attack2_anim_key):
                           player.set_state(selected_attack2_anim_key)
                       elif selected_attack2_anim_key: # Animation key chosen but frames missing
                           player.set_state('attack_nm') # Fallback to a base attack

            # --- Dash Action ---
            if event.key == key_config_map['dash']:
                  if player.on_ground and not player.is_dashing and not player.is_rolling and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('dash')

            # --- Roll Action ---
            if event.key == key_config_map['roll']:
                  if player.on_ground and not player.is_rolling and not player.is_dashing and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('roll')

            # --- Crouch / Slide Action (on 'down' key press) ---
            if event.key == key_config_map['down']:
                can_initiate_slide_action = player.on_ground and player.state == 'run' and \
                                            abs(player.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                            not player.is_sliding and not player.is_crouching and \
                                            not player.is_attacking and not player.is_rolling and \
                                            not player.is_dashing and not player.on_ladder and \
                                            player.state not in ['turn','hit']
                if can_initiate_slide_action:
                    slide_start_anim_key = 'slide_trans_start' if 'slide_trans_start' in player.animations and \
                                             player.animations['slide_trans_start'] else 'slide'
                    if slide_start_anim_key in player.animations and player.animations[slide_start_anim_key]:
                        player.set_state(slide_start_anim_key)
                        player.is_crouching = False # Sliding is not the same as being fully crouched for other logic
                else: # Not sliding, so this is a crouch toggle/initiation
                    can_player_toggle_crouch = player.on_ground and not player.on_ladder and \
                                               not player.is_sliding and \
                                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                                    player.state in ['turn','hit','death','death_nm'])
                    if can_player_toggle_crouch:
                        if not player.is_crouching: # Trying to crouch
                            player.is_crouching = True
                            player.is_sliding = False # Ensure sliding is off
                            # Transition to crouch animation
                            if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
                               player.state not in ['crouch','crouch_walk','crouch_trans']:
                                player.set_state('crouch_trans')
                            elif player.state not in ['crouch', 'crouch_walk', 'crouch_trans']: # No transition, go direct
                                player.set_state('crouch')
                        else: # Player is already crouching, 'down' key pressed again (for toggle systems)
                              # The actual uncrouching (setting player.is_crouching = False)
                              # will be handled in player_movement_physics.py after checking can_stand_up()
                              # This input just registers the intent if it's a toggle.
                              # If it's hold-to-crouch, this KEYDOWN while already crouching doesn't do much here.
                              pass # Let movement physics handle uncrouch on key release

            # --- Interact Action (Ladders) ---
            if event.key == key_config_map['interact']:
                  if player.can_grab_ladder and not player.on_ladder: # Player is near a ladder and not on it
                      player.is_crouching = False # Can't be on ladder and crouched
                      player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
                      player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
                      player.set_state('ladder_idle')
                  elif player.on_ladder: # Player is on a ladder and presses interact again
                      player.on_ladder = False
                      player.set_state('fall' if not player.on_ground else 'idle') # Fall off ladder

            # --- Weapon Firing Logic (Projectile Keys) ---
            can_fire_projectile = not player.is_crouching and \
                                  not player.is_attacking and \
                                  not player.is_dashing and \
                                  not player.is_rolling and \
                                  not player.is_sliding and \
                                  not player.on_ladder and \
                                  player.state not in ['turn', 'hit', 'death', 'death_nm', 'wall_climb', 'wall_hang', 'wall_slide']

            if can_fire_projectile:
                if player.fireball_key and event.key == player.fireball_key:
                    if hasattr(player, 'fire_fireball'): player.fire_fireball()
                elif player.poison_key and event.key == player.poison_key:
                    if hasattr(player, 'fire_poison'): player.fire_poison()
                elif player.bolt_key and event.key == player.bolt_key:
                    if hasattr(player, 'fire_bolt'): player.fire_bolt()
                elif player.blood_key and event.key == player.blood_key:
                    if hasattr(player, 'fire_blood'): player.fire_blood()
                elif player.ice_key and event.key == player.ice_key:
                    if hasattr(player, 'fire_ice'): player.fire_ice()

    # --- Determine Default/Fallback States based on Movement Intention and Environment ---
    # This runs every frame, after discrete actions are processed.
    # It sets states like 'idle', 'run', 'fall', 'wall_slide' if no other specific action state is active.
    is_in_manual_override_or_transition_state = player.is_attacking or player.is_dashing or \
                                                player.is_rolling or player.is_sliding or \
                                                player.is_taking_hit or \
                                                player.state in [ # States that manage their own duration or next state
                                                    'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                    'crouch_trans', # 'stand_up_trans', # Add if you implement stand_up_trans
                                                    'slide_trans_start','slide_trans_end',
                                                    'wall_climb','wall_climb_nm','wall_hang','wall_slide',
                                                    'ladder_idle','ladder_climb' # Ladder states are sticky until interact/jump
                                                ]

    if not is_in_manual_override_or_transition_state:
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 : # If moving on ladder
                if player.state != 'ladder_climb': player.set_state('ladder_climb')
            else: # Stationary on ladder
                if player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: # Player IS currently crouching (and not uncrouching this frame)
                 target_crouch_state_key = 'crouch_walk' if player_intends_horizontal_move and \
                                             player.animations.get('crouch_walk') \
                                             else 'crouch'
                 if player.state != target_crouch_state_key:
                    player.set_state(target_crouch_state_key)
             elif player_intends_horizontal_move: # Not crouching, on ground, trying to move
                 if player.state != 'run': player.set_state('run')
             else: # Not crouching, on ground, not trying to move
                 if player.state != 'idle': player.set_state('idle')
        else: # In Air (not on ladder, not on ground)
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling: # Wall interaction takes precedence
                 current_wall_time_ms = pygame.time.get_ticks()
                 is_wall_climb_duration_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and
                                                   current_wall_time_ms - player.wall_climb_timer > player.wall_climb_duration)

                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or is_wall_climb_duration_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and \
                      not is_wall_climb_duration_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else: # Default to wall_slide if not actively climbing or if climb animation missing
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']: # Falling
                  if player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall']: # Generic air state if not jumping or falling significantly
                  if player.state != 'idle': player.set_state('idle') # Or fall if idle doesn't make sense in air