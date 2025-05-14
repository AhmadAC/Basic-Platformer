# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles processing of player input and translating it to actions.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C

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
    
    # Check if input processing should be blocked (e.g., player is dead or stunned)
    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) 

    if is_input_blocked:
        player.acc.x = 0 # Ensure no accidental movement if input is blocked
        return

    # --- Update Player's Input Intention Flags (based on held keys) ---
    player.is_trying_to_move_left = keys_pressed[key_config_map['left']]
    player.is_trying_to_move_right = keys_pressed[key_config_map['right']]
    player.is_holding_climb_ability_key = keys_pressed[key_config_map['up']] # Often 'up' for climb/jump
    player.is_holding_crouch_ability_key = keys_pressed[key_config_map['down']] # Often 'down' for crouch/slide

    # --- Update Fireball Aim Direction (based on current directional input) ---
    # This ensures the fireball aims correctly even if fired without simultaneous movement.
    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if keys_pressed[key_config_map['left']]: fireball_aim_x_input = -1.0
    elif keys_pressed[key_config_map['right']]: fireball_aim_x_input = 1.0
    
    if keys_pressed[key_config_map['up']]: fireball_aim_y_input = -1.0
    elif keys_pressed[key_config_map['down']]: fireball_aim_y_input = 1.0
    
    # Only update aim if there's active directional input
    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0: # Ensure a default aim if none active
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    # --- Horizontal Movement Acceleration and Facing Direction ---
    player.acc.x = 0 # Reset horizontal acceleration each frame
    player_intends_horizontal_move = False

    # Determine if horizontal movement input is allowed by current player state
    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or 
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )
    
    if can_player_control_horizontal_movement:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            # If facing right but trying to move left (and on ground, not in special state), initiate turn
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = False # Update facing direction
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = True

    # --- Crouching Logic (based on holding 'down' key) ---
    can_player_initiate_crouch = player.on_ground and not player.on_ladder and \
                                 not (player.is_dashing or player.is_rolling or player.is_sliding or \
                                      player.is_attacking or player.state in ['turn','hit','death'])
    
    if player.is_holding_crouch_ability_key and can_player_initiate_crouch:
        if not player.is_crouching: # Transition to crouch state
            player.is_crouching = True
            player.is_sliding = False # Crouching overrides sliding
            # Use crouch transition animation if available and not already in a crouch-related state
            if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
               player.state not in ['crouch','crouch_walk','crouch_trans']:
                player.set_state('crouch_trans')
            # else: player.set_state('crouch') # Optionally, go directly to crouch if no transition
    elif not player.is_holding_crouch_ability_key and player.is_crouching: # Released crouch key
        player.is_crouching = False
        # Transition out of crouch will be handled by general state logic if not attacking/sliding, etc.
        # e.g., if idle and crouch released, will go to 'idle'.

    # --- Ladder Movement (overrides normal vertical movement) ---
    if player.on_ladder:
         player.vel.y = 0 # Stop falling/jumping momentum
         if player.is_holding_climb_ability_key: # Holding 'up' on ladder
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif player.is_holding_crouch_ability_key: # Holding 'down' on ladder
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    # --- Process Event-Based Actions (KEYDOWN for discrete actions) ---
    for event in pygame_events:
        if event.type == pygame.KEYDOWN:
            # Jump / Wall Jump / Ladder Jump (triggered by 'up' key press)
            if event.key == key_config_map['up']:
                  can_perform_jump_action = not player.is_crouching and not player.is_attacking and \
                                            not player.is_rolling and not player.is_sliding and \
                                            not player.is_dashing and player.state not in ['turn','hit']
                  if player.on_ground and can_perform_jump_action: # Standard jump from ground
                      player.vel.y = C.PLAYER_JUMP_STRENGTH
                      player.set_state('jump')
                      player.on_ground = False # Important: set immediately to prevent re-jump in same frame
                  elif player.on_ladder and can_perform_jump_action: # Jump off ladder
                      player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8 # Slightly weaker ladder jump
                      player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1) # Horizontal push
                      player.on_ladder = False # Leave ladder
                      player.set_state('jump')
                  elif player.can_wall_jump and player.touching_wall != 0 and can_perform_jump_action: # Wall jump
                      player.vel.y = C.PLAYER_JUMP_STRENGTH # Full jump strength
                      player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall) # Jump away from wall
                      player.facing_right = not player.facing_right # Turn to face away from wall
                      player.set_state('jump')
                      # Reset wall interaction state after wall jump
                      player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0
            
            # Attack 1 (Primary Attack)
            if event.key == key_config_map['attack1']:
                  can_perform_attack_action = not player.is_attacking and not player.is_dashing and \
                                              not player.is_rolling and not player.is_sliding and \
                                              not player.on_ladder and player.state not in ['turn','hit']
                  if can_perform_attack_action:
                       player.attack_type = 1 # Set attack type for damage calculation and animation
                       # Determine if attack is with movement or stationary
                       is_moving_for_attack_anim = (player.acc.x !=0 or abs(player.vel.x) > 1.0)
                       attack_animation_key = 'attack' if is_moving_for_attack_anim and \
                                              'attack' in player.animations and player.animations['attack'] \
                                              else 'attack_nm'
                       if player.is_crouching: # If crouching, perform crouch attack
                           player.attack_type = 4 # Crouch attack type
                           attack_animation_key = 'crouch_attack'
                       player.set_state(attack_animation_key) # Set appropriate attack state
            
            # Attack 2 (Secondary / Combo Attack)
            if event.key == key_config_map['attack2']:
                  can_perform_attack2_action = not player.is_dashing and not player.is_rolling and \
                                               not player.is_sliding and not player.on_ladder and \
                                               player.state not in ['turn','hit']
                  # Combo logic: Allow initiating attack2 even if attack1 is in recovery (within combo window)
                  if can_perform_attack2_action:
                       is_moving_for_attack2_anim = (player.acc.x != 0 or abs(player.vel.x) > 1.0)
                       
                       # Check if eligible for a combo (Attack 3)
                       time_since_attack1_ended = current_time_ms - (player.attack_timer + player.attack_duration)
                       is_in_combo_window_for_attack3 = (player.attack_type == 1 and not player.is_attacking and 
                                                         time_since_attack1_ended < player.combo_window)
                       
                       selected_attack2_anim_key = ''
                       if is_in_combo_window_for_attack3 and \
                          'attack_combo' in player.animations and player.animations['attack_combo']:
                           player.attack_type = 3 # Combo attack
                           selected_attack2_anim_key = 'attack_combo' if is_moving_for_attack2_anim and \
                                                       'attack_combo' in player.animations and player.animations['attack_combo'] \
                                                       else 'attack_combo_nm'
                       elif player.is_crouching and 'crouch_attack' in player.animations and \
                            player.animations['crouch_attack'] and not player.is_attacking :
                           # Standard crouch attack if not comboing (usually attack1 key handles this, but can be backup)
                           player.attack_type = 4 
                           selected_attack2_anim_key = 'crouch_attack'
                       elif not player.is_attacking and 'attack2' in player.animations and \
                            player.animations['attack2']: # Standard Attack 2
                           player.attack_type = 2 
                           selected_attack2_anim_key = 'attack2' if is_moving_for_attack2_anim and \
                                                       'attack2' in player.animations and player.animations['attack2'] \
                                                       else 'attack2_nm'
                       elif not player.is_attacking and player.attack_type == 0 and \
                            'attack' in player.animations and player.animations['attack']: 
                           # Fallback to Attack 1 if no other attack type is suitable (e.g., first attack in a sequence)
                           player.attack_type = 1
                           selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim else 'attack_nm'
                       
                       if selected_attack2_anim_key : player.set_state(selected_attack2_anim_key)

            # Dash Action
            if event.key == key_config_map['dash']:
                  if player.on_ground and not player.is_dashing and not player.is_rolling and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('dash') # Initiate dash state

            # Roll Action
            if event.key == key_config_map['roll']:
                  if player.on_ground and not player.is_rolling and not player.is_dashing and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('roll') # Initiate roll state
            
            # Slide Action (initiated by 'down' key press *while running*)
            if event.key == key_config_map['down']: # This is KEYDOWN event, not just holding 'down'
                  can_initiate_slide_action = player.on_ground and player.state == 'run' and \
                                              abs(player.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                              not player.is_sliding and not player.is_crouching and \
                                              not player.is_attacking and not player.is_rolling and \
                                              not player.is_dashing and not player.on_ladder and \
                                              player.state not in ['turn','hit']
                  if can_initiate_slide_action:
                       # Use slide transition animation if available
                       slide_start_anim_key = 'slide_trans_start' if 'slide_trans_start' in player.animations and \
                                                player.animations['slide_trans_start'] else 'slide'
                       if slide_start_anim_key in player.animations and player.animations[slide_start_anim_key]:
                           player.set_state(slide_start_anim_key)
            
            # Interact Action (e.g., grab/release ladders)
            if event.key == key_config_map['interact']:
                  if player.can_grab_ladder and not player.on_ladder: # Grab ladder
                      player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
                      player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
                      player.set_state('ladder_idle') # Go to ladder idle state
                  elif player.on_ladder: # Release from ladder
                      player.on_ladder = False
                      player.set_state('fall' if not player.on_ground else 'idle') # Fall or go to idle
            
            # Fireball Action (using player-specific fireball_key)
            if player.fireball_key and event.key == player.fireball_key:
                 # The actual firing logic is in player_combat_handler, called via player's method
                 if hasattr(player, 'fire_fireball'):
                     player.fire_fireball()


    # --- Determine Player's Logical State Based on Current Conditions (if not in a manually set state) ---
    # This section updates the player's state if no specific action (like attack, dash) took precedence.
    # It handles transitions like idle to run, run to fall, etc.
    is_in_manual_override_or_transition_state = player.is_attacking or player.is_dashing or \
                                                player.is_rolling or player.is_sliding or \
                                                player.is_taking_hit or \
                                                player.state in [
                                                    'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                    'crouch_trans','slide_trans_start','slide_trans_end',
                                                    'wall_climb','wall_climb_nm','wall_hang','wall_slide',
                                                    'ladder_idle','ladder_climb'
                                                ]
    
    if not is_in_manual_override_or_transition_state: # If not in a special state, determine general state
        if player.on_ladder: # Ladder states
            if abs(player.vel.y) > 0.1 : # Moving on ladder
                player.set_state('ladder_climb' if 'ladder_climb' in player.animations and \
                                 player.animations['ladder_climb'] else 'idle')
            else: # Stationary on ladder
                player.set_state('ladder_idle' if 'ladder_idle' in player.animations and \
                                 player.animations['ladder_idle'] else 'idle')
        elif player.on_ground: # Grounded states
             if player.is_crouching: # Crouching (either still or walking)
                 target_crouch_state_key = 'crouch_walk' if player_intends_horizontal_move and \
                                             'crouch_walk' in player.animations and player.animations['crouch_walk'] \
                                             else 'crouch'
                 # Only set if not already in a crouch state (or if changing between crouch/crouch_walk)
                 if player.state not in ['crouch', 'crouch_walk'] or player.state != target_crouch_state_key:
                    player.set_state(target_crouch_state_key if target_crouch_state_key in player.animations and \
                                     player.animations[target_crouch_state_key] else 'idle')
             elif player_intends_horizontal_move: # Running
                 player.set_state('run' if 'run' in player.animations and player.animations['run'] else 'idle')
             else: # Idle on ground
                 player.set_state('idle')
        else: # In Air states (not on ladder, not on ground)
             if player.touching_wall != 0: # Interacting with a wall
                 current_wall_time_ms = pygame.time.get_ticks()
                 is_wall_climb_duration_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and
                                                   current_wall_time_ms - player.wall_climb_timer > player.wall_climb_duration)
                 
                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or is_wall_climb_duration_expired:
                     # If sliding down fast enough or climb time expired, transition to wall_slide
                     player.set_state('wall_slide')
                     player.can_wall_jump = True # Can jump off a wall slide
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and \
                      not is_wall_climb_duration_expired and 'wall_climb' in player.animations and \
                      player.animations['wall_climb']:
                     # If holding climb key, slow horizontal movement, and climb time not up, try to wall_climb
                     player.set_state('wall_climb')
                     player.can_wall_jump = False # Cannot wall jump while actively climbing up
                 else: # Default wall interaction is wall_slide
                     player.set_state('wall_slide')
                     player.can_wall_jump = True
             elif player.vel.y > 1.0 and player.state not in ['jump','jump_fall_trans']: # Standard falling
                  player.set_state('fall' if 'fall' in player.animations and player.animations['fall'] else 'idle')
             elif player.state not in ['jump','jump_fall_trans','fall']: # If in air but not jumping/falling (e.g., after air dash ends)
                  # Could also transition to 'fall' if vel.y is positive.
                  player.set_state('idle') # Or a more specific air_idle if available.