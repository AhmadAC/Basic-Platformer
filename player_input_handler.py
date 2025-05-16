# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.7 (Conceptual outline for joystick input)
Handles processing of player input and translating it to actions.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C 
import config as game_config # For accessing defined mappings
import joystick_handler # For getting joystick instances

def process_player_input_logic(player, keys_pressed_from_pygame, pygame_events, 
                               # key_config_map is no longer directly used if player has scheme
                               _unused_key_config_map_arg=None): 
    """
    Core logic for processing input (keyboard or joystick) into player actions.
    Modifies the 'player' instance directly.
    """
    if not player._valid_init: return 

    current_time_ms = pygame.time.get_ticks() 

    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                       getattr(player, 'is_petrified', False) # Block input if petrified

    if is_input_blocked:
        player.acc.x = 0 
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        player.is_holding_crouch_ability_key = False
        return

    # --- Determine active input mappings based on player's control scheme ---
    active_mappings = {}
    is_joystick_input = False
    joystick_instance = None

    if "keyboard" in player.control_scheme:
        if player.control_scheme == "keyboard_p1":
            active_mappings = game_config.P1_MAPPINGS # This should be the keyboard dict
        elif player.control_scheme == "keyboard_p2":
            active_mappings = game_config.P2_MAPPINGS # This should be the keyboard dict
    elif "joystick" in player.control_scheme and player.joystick_id_idx is not None:
        is_joystick_input = True
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if joystick_instance:
            if player.player_id == 1: # Assuming P1 joystick maps to P1_MAPPINGS if joystick
                active_mappings = game_config.P1_MAPPINGS
            elif player.player_id == 2:
                active_mappings = game_config.P2_MAPPINGS
        else:
            # Fallback if joystick disconnected or invalid ID
            print(f"Warning: Player {player.player_id} set to joystick {player.joystick_id_idx} but instance not found. Reverting to P1 KB.")
            active_mappings = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
            player.control_scheme = "keyboard_p1" # Fallback

    # --- Read Abstracted Inputs (will be populated by either keyboard or joystick) ---
    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS} # For pressed-once events

    # --- Populate action_state and action_events based on input type ---
    if not is_joystick_input: # KEYBOARD
        # Held keys for movement/crouch/climb
        action_state["left"] = keys_pressed_from_pygame[active_mappings.get("left", -1)]
        action_state["right"] = keys_pressed_from_pygame[active_mappings.get("right", -1)]
        action_state["up"] = keys_pressed_from_pygame[active_mappings.get("up", -1)] # For climb
        action_state["down"] = keys_pressed_from_pygame[active_mappings.get("down", -1)] # For crouch/climb_down
        
        # Keydown events for actions
        for event in pygame_events:
            if event.type == pygame.KEYDOWN:
                for action, key_code in active_mappings.items():
                    if event.key == key_code:
                        action_events[action] = True
                        # Special case for jump if 'up' is also jump
                        if action == "up" and active_mappings.get("jump") == key_code:
                            action_events["jump"] = True 
                        break 
    else: # JOYSTICK
        if joystick_instance:
            # This is where you'd poll joystick_instance.get_axis(), .get_button(), .get_hat()
            # and compare with definitions in active_mappings (which holds joystick button/axis IDs)
            # For example:
            # if joystick_instance.get_button(active_mappings.get("jump", {}).get("id", -1)):
            #    action_events["jump"] = True # Or action_state if jump can be held
            
            # Polling for held states (axes for movement, could be buttons too)
            # Example for left/right axis:
            move_x_axis_id = active_mappings.get("left", {}).get("id", -1) # Assume left/right share axis
            if move_x_axis_id != -1:
                axis_val = joystick_instance.get_axis(move_x_axis_id)
                left_thresh = active_mappings.get("left", {}).get("threshold", 0.5)
                right_thresh = active_mappings.get("right", {}).get("threshold", 0.5)
                if axis_val < -left_thresh: action_state["left"] = True
                if axis_val > right_thresh: action_state["right"] = True

            # Example for up/down axis:
            move_y_axis_id = active_mappings.get("up", {}).get("id", -1) # Assume up/down share axis
            if move_y_axis_id != -1:
                axis_val = joystick_instance.get_axis(move_y_axis_id)
                up_thresh = active_mappings.get("up", {}).get("threshold", 0.5)
                down_thresh = active_mappings.get("down", {}).get("threshold", 0.5)
                if axis_val < -up_thresh: action_state["up"] = True   # For climb
                if axis_val > down_thresh: action_state["down"] = True # For crouch/climb_down

            # Handle joystick button events from pygame_events
            for event in pygame_events:
                if event.type == pygame.JOYBUTTONDOWN and event.joy == player.joystick_id_idx:
                    for action, mapping_details in active_mappings.items():
                        if mapping_details.get("type") == "button" and mapping_details.get("id") == event.button:
                            action_events[action] = True
                            break
                # Add JOYAXISMOTION and JOYHATMOTION handling if needed for discrete events,
                # though polling is often simpler for continuous actions like movement.

    # --- Now use action_state and action_events for game logic ---
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]

    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if action_state["left"]: fireball_aim_x_input = -1.0
    elif action_state["right"]: fireball_aim_x_input = 1.0
    if action_state["up"]: fireball_aim_y_input = -1.0
    elif action_state["down"]: fireball_aim_y_input = 1.0 

    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0: 
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    player.acc.x = 0 
    player_intends_horizontal_move = False 

    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or 
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang'] 
    )

    if can_player_control_horizontal_movement:
        if action_state["left"] and not action_state["right"]:
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']: 
                player.set_state('turn')
            player.facing_right = False 
        elif action_state["right"] and not action_state["left"]:
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']: 
                player.set_state('turn')
            player.facing_right = True 

    if player.on_ladder:
         player.vel.y = 0 
         if action_state["up"]: # Holding up on ladder
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif action_state["down"]: # Holding down on ladder
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    # --- Process Action Events (Jump, Attack, Abilities, Projectiles) ---
    # These use action_events which are true for one frame on key/button press
    
    # JUMP
    if action_events.get("jump") or action_events.get("up"): # 'up' can also trigger jump
        can_perform_jump_action = not player.is_attacking and \
                                  not player.is_rolling and not player.is_sliding and \
                                  not player.is_dashing and \
                                  player.state not in ['turn','hit','death','death_nm']
        if can_perform_jump_action:
            if player.on_ground:
                if player.is_crouching: player.is_crouching = False 
                player.vel.y = C.PLAYER_JUMP_STRENGTH
                player.set_state('jump')
                player.on_ground = False
            elif player.on_ladder: 
                player.is_crouching = False 
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8 
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1) 
                player.on_ladder = False
                player.set_state('jump')
            elif player.can_wall_jump and player.touching_wall != 0: 
                player.is_crouching = False 
                player.vel.y = C.PLAYER_JUMP_STRENGTH
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall) 
                player.facing_right = not player.facing_right 
                player.set_state('jump')
                player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0
    
    # ATTACK 1
    if action_events.get("attack1"):
        can_perform_attack_action = not player.is_attacking and not player.is_dashing and \
                                    not player.is_rolling and not player.is_sliding and \
                                    not player.on_ladder and player.state not in ['turn','hit']
        if can_perform_attack_action:
            player.attack_type = 1
            is_moving_for_attack_anim = (player.acc.x !=0 or abs(player.vel.x) > 1.0)
            if player.is_crouching:
                player.attack_type = 4 
                attack_animation_key = 'crouch_attack'
            elif is_moving_for_attack_anim and 'attack' in player.animations and player.animations['attack']:
                attack_animation_key = 'attack'
            else:
                attack_animation_key = 'attack_nm' 
            player.set_state(attack_animation_key)

    # ATTACK 2 / COMBO
    if action_events.get("attack2"):
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
                player.attack_type = 3 
                selected_attack2_anim_key = 'attack_combo' if is_moving_for_attack2_anim and player.animations.get('attack_combo') else 'attack_combo_nm'
            elif player.is_crouching and 'crouch_attack' in player.animations and \
                    player.animations['crouch_attack'] and not player.is_attacking : 
                player.attack_type = 4; selected_attack2_anim_key = 'crouch_attack'
            elif not player.is_attacking and 'attack2' in player.animations and player.animations['attack2']: 
                player.attack_type = 2
                selected_attack2_anim_key = 'attack2' if is_moving_for_attack2_anim and player.animations.get('attack2') else 'attack2_nm'
            elif not player.is_attacking and player.attack_type == 0 and \
                    'attack' in player.animations and player.animations['attack']: # Default to attack1 if no other condition met
                player.attack_type = 1
                selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim and player.animations.get('attack') else 'attack_nm'

            if selected_attack2_anim_key and player.animations.get(selected_attack2_anim_key):
                player.set_state(selected_attack2_anim_key)
            elif selected_attack2_anim_key: # Fallback if specific (e.g. _nm) is missing but base exists
                player.set_state('attack_nm') 

    # DASH
    if action_events.get("dash"):
        if player.on_ground and not player.is_dashing and not player.is_rolling and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('dash')

    # ROLL
    if action_events.get("roll"):
        if player.on_ground and not player.is_rolling and not player.is_dashing and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('roll')
    
    # CROUCH / SLIDE (Initiated by "down" key event)
    if action_events.get("down"): # Using the "down" abstract action for initiating crouch/slide
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
                player.is_crouching = False 
        else: 
            can_player_toggle_crouch = player.on_ground and not player.on_ladder and \
                                        not player.is_sliding and \
                                        not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                            player.state in ['turn','hit','death','death_nm'])
            if can_player_toggle_crouch:
                if not player.is_crouching: 
                    player.is_crouching = True
                    player.is_sliding = False 
                    if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
                        player.state not in ['crouch','crouch_walk','crouch_trans']:
                        player.set_state('crouch_trans')
                    elif player.state not in ['crouch', 'crouch_walk', 'crouch_trans']: 
                        player.set_state('crouch')
                else: 
                      pass # Already crouching, holding key maintains it. Release is handled in core_physics

    # INTERACT (LADDER)
    if action_events.get("interact"):
        if player.can_grab_ladder and not player.on_ladder: 
            player.is_crouching = False 
            player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder: 
            player.on_ladder = False
            player.set_state('fall' if not player.on_ground else 'idle') 

    # PROJECTILES
    can_fire_projectile = not player.is_crouching and \
                            not player.is_attacking and \
                            not player.is_dashing and \
                            not player.is_rolling and \
                            not player.is_sliding and \
                            not player.on_ladder and \
                            player.state not in ['turn', 'hit', 'death', 'death_nm', 'wall_climb', 'wall_hang', 'wall_slide']

    if can_fire_projectile:
        if action_events.get("projectile1"): player.fire_fireball()
        elif action_events.get("projectile2"): player.fire_poison()
        elif action_events.get("projectile3"): player.fire_bolt()
        elif action_events.get("projectile4"): player.fire_blood()
        elif action_events.get("projectile5"): player.fire_ice()
        elif action_events.get("projectile6"): player.fire_shadow()
        elif action_events.get("projectile7"): player.fire_grey()


    # --- Determine logical state based on continuous inputs if not in an override state ---
    is_in_manual_override_or_transition_state = player.is_attacking or player.is_dashing or \
                                                player.is_rolling or player.is_sliding or \
                                                player.is_taking_hit or \
                                                player.state in [ 
                                                    'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                    'crouch_trans', 
                                                    'slide_trans_start','slide_trans_end',
                                                    'wall_climb','wall_climb_nm','wall_hang','wall_slide',
                                                    'ladder_idle','ladder_climb' 
                                                ]

    if not is_in_manual_override_or_transition_state:
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 : 
                if player.state != 'ladder_climb': player.set_state('ladder_climb')
            else: 
                if player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: 
                 target_crouch_state_key = 'crouch_walk' if player_intends_horizontal_move and \
                                             player.animations.get('crouch_walk') \
                                             else 'crouch'
                 if player.state != target_crouch_state_key:
                    player.set_state(target_crouch_state_key)
             elif player_intends_horizontal_move: 
                 if player.state != 'run': player.set_state('run')
             else: 
                 if player.state != 'idle': player.set_state('idle')
        else: # In air
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling: 
                 current_wall_time_ms = pygame.time.get_ticks()
                 is_wall_climb_duration_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and
                                                   current_wall_time_ms - player.wall_climb_timer > player.wall_climb_duration)

                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or is_wall_climb_duration_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and \
                      not is_wall_climb_duration_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else: 
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']: 
                  if player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall']: # Not significantly falling, not on wall
                  if player.state != 'idle': player.set_state('idle') # Or 'fall' if no 'idle' air anim