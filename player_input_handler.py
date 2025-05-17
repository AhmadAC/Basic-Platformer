########## START OF FILE: player_input_handler.py ##########
# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.0 (Improved joystick event handling and debug for button actions)
Handles processing of player input and translating it to actions.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C
import config as game_config
import joystick_handler
from utils import PrintLimiter # Assuming PrintLimiter is in utils.py

# Initialize a print limiter for this module if needed
input_print_limiter = PrintLimiter(default_limit=10, default_period=5.0)


def process_player_input_logic(player, keys_pressed_from_pygame, pygame_events,
                               active_mappings):
    """
    Core logic for processing raw Pygame input (keyboard or joystick)
    into player actions and state changes.
    Modifies the 'player' instance directly based on the input and active_mappings.
    Returns a dictionary of action events that occurred this frame.
    """
    if not player._valid_init: return {}

    current_time_ms = pygame.time.get_ticks()
    player_id_str = f"P{player.player_id}"

    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                       getattr(player, 'is_petrified', False)

    # Initialize action_state for continuous (held) actions
    # and action_events for pressed-once (event-driven) actions
    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS}

    if is_input_blocked:
        player.acc.x = 0
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        player.is_holding_crouch_ability_key = False
        return action_events

    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")
    joystick_instance = None

    if is_joystick_input_type and player.joystick_id_idx is not None:
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if not joystick_instance:
            if input_print_limiter.can_print(f"joy_missing_{player_id_str}"):
                print(f"INPUT_HANDLER ({player_id_str}): Joystick instance for ID {player.joystick_id_idx} not found. Input will fail.")
            is_joystick_input_type = False # Fallback to no input or keyboard if primary fails

    # --- Part 1: Process continuous (held) inputs for action_state ---
    if not is_joystick_input_type: # Keyboard
        for action_name in ["left", "right", "up", "down"]:
            key_code = active_mappings.get(action_name)
            if key_code is not None and isinstance(key_code, int): # Ensure it's a keycode
                action_state[action_name] = keys_pressed_from_pygame[key_code]
    else: # Joystick
        if joystick_instance:
            for action_name in ["left", "right", "up", "down"]: # Typically analog/dpad movement
                mapping_details = active_mappings.get(action_name)
                if isinstance(mapping_details, dict):
                    m_type = mapping_details.get("type")
                    m_id = mapping_details.get("id")
                    m_value_prop = mapping_details.get("value") # Expected direction/hat_value
                    m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)

                    if m_type == "axis" and m_id is not None and 0 <= m_id < joystick_instance.get_numaxes():
                        axis_val = joystick_instance.get_axis(m_id)
                        if isinstance(m_value_prop, (int, float)): # Should be -1 or 1 for axes
                            if m_value_prop < 0 and axis_val < -m_threshold: action_state[action_name] = True
                            elif m_value_prop > 0 and axis_val > m_threshold: action_state[action_name] = True
                    elif m_type == "hat" and m_id is not None and 0 <= m_id < joystick_instance.get_numhats():
                        hat_val_current = joystick_instance.get_hat(m_id)
                        if hat_val_current == m_value_prop: # m_value_prop is a tuple like (x,y)
                            action_state[action_name] = True
    # Debug print for held states
    # if input_print_limiter.can_print(f"action_state_{player_id_str}"):
    #     held_actions = {k:v for k,v in action_state.items() if v}
    #     if held_actions: print(f"INPUT_HANDLER ({player_id_str}): Held states: {held_actions}")


    # --- Part 2: Process event-driven inputs (key/button presses) for action_events ---
    for event in pygame_events:
        if not is_joystick_input_type: # Keyboard events
            if event.type == pygame.KEYDOWN:
                for action_name, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action_name] = True
                        # Special handling: if 'up' key is also 'jump'
                        if action_name == "up" and active_mappings.get("jump") == key_code:
                            action_events["jump"] = True
                        # if input_print_limiter.can_print(f"kb_event_{player_id_str}_{action_name}"):
                        #     print(f"INPUT_HANDLER ({player_id_str}): Keyboard event PRESSED for '{action_name}' (Key: {pygame.key.name(event.key)})")
                        break
        else: # Joystick events
            if joystick_instance and event.type == pygame.JOYBUTTONDOWN and event.joy == player.joystick_id_idx:
                for action_name, mapping_details in active_mappings.items():
                    if isinstance(mapping_details, dict) and mapping_details.get("type") == "button":
                        if mapping_details.get("id") == event.button:
                            action_events[action_name] = True
                            # Special handling: if an 'up' button (if mapped) also means 'jump'
                            if action_name == "up" and active_mappings.get("jump") == mapping_details:
                                action_events["jump"] = True
                            if input_print_limiter.can_print(f"joy_event_{player_id_str}_{action_name}"):
                                print(f"INPUT_HANDLER ({player_id_str}): Joystick event BUTTON {event.button} PRESSED for '{action_name}'")
                            break
            elif joystick_instance and event.type == pygame.JOYHATMOTION and event.joy == player.joystick_id_idx:
                for action_name, mapping_details in active_mappings.items():
                    if isinstance(mapping_details, dict) and mapping_details.get("type") == "hat":
                        if mapping_details.get("id") == event.hat and mapping_details.get("value") == event.value:
                            # Hat events can sometimes be treated as one-shot presses for actions like projectiles
                            # Check if the action is one of the event-driven ones (like projectiles)
                            if action_name in ["projectile1", "projectile2", "projectile3", "projectile4", "projectile5", "projectile6", "projectile7",
                                               "menu_up", "menu_down", "menu_left", "menu_right", "menu_confirm", "menu_cancel", "pause"]: # Add other event-like hat actions
                                action_events[action_name] = True
                                if input_print_limiter.can_print(f"joy_event_hat_{player_id_str}_{action_name}"):
                                    print(f"INPUT_HANDLER ({player_id_str}): Joystick event HAT {event.hat} VALUE {event.value} for '{action_name}'")
                            break
            elif joystick_instance and event.type == pygame.JOYAXISMOTION and event.joy == player.joystick_id_idx :
                # Handle event-driven actions mapped to AXES (like your WEAPON_1, WEAPON_2 from JSON)
                # These are tricky because an axis can stay beyond threshold.
                # We need to detect the *transition* past the threshold.
                # This requires storing the previous state of these axes.
                # For simplicity now, we'll make them event-like if they pass threshold.
                # A more robust solution would track if it *was* below threshold and *now* is above.
                for action_name, mapping_details in active_mappings.items():
                    if isinstance(mapping_details, dict) and mapping_details.get("type") == "axis":
                        m_id = mapping_details.get("id")
                        m_value_prop = mapping_details.get("value") # Expected direction
                        m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                        if m_id == event.axis: # Check if it's the axis that moved
                            axis_val = event.value
                            # Trigger event if it crosses threshold in the correct direction
                            # This basic check will fire repeatedly if held; true event needs state tracking
                            passed_threshold_this_frame = False
                            if isinstance(m_value_prop, (int, float)):
                                if m_value_prop < 0 and axis_val < -m_threshold: passed_threshold_this_frame = True
                                elif m_value_prop > 0 and axis_val > m_threshold: passed_threshold_this_frame = True

                            if passed_threshold_this_frame:
                                # Only trigger for actions intended to be events (e.g., projectiles)
                                if action_name in ["projectile1", "projectile2", "projectile3", "projectile4", "projectile5", "projectile6", "projectile7"]:
                                    # This still needs a "once per press" mechanism if axis is held
                                    # For now, let it be true. Player fire methods have cooldowns.
                                    action_events[action_name] = True
                                    if input_print_limiter.can_print(f"joy_event_axis_{player_id_str}_{action_name}"):
                                        print(f"INPUT_HANDLER ({player_id_str}): Joystick event AXIS {event.axis} VALUE {axis_val:.2f} for '{action_name}' (Threshold: {m_threshold})")
                                break


    # --- Part 3: Update player intention states based on action_state ---
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"] # This will be true if "CROUCH" or "MOVE_DOWN" (from json) is active

    # Update aim direction
    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if action_state["left"]: fireball_aim_x_input = -1.0
    elif action_state["right"]: fireball_aim_x_input = 1.0
    if action_state["up"]: fireball_aim_y_input = -1.0
    elif action_state["down"]: fireball_aim_y_input = 1.0

    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0: # Fallback if no aim input
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    # --- Part 4: Translate action_events and continuous states into player logic ---
    player.acc.x = 0
    player_intends_horizontal_move = False

    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )

    if can_player_control_horizontal_movement:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
         player.vel.y = 0
         if player.is_holding_climb_ability_key: # 'up' state
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif player.is_holding_crouch_ability_key: # 'down' state
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    # Jump action (event-driven)
    if action_events.get("jump"): # "jump" is the internal action name
        if input_print_limiter.can_print(f"jump_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Jump event triggered.")
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

    # Attack1 action (event-driven)
    if action_events.get("attack1"):
        if input_print_limiter.can_print(f"attack1_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Attack1 event triggered.")
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

    # Attack2 action (event-driven)
    if action_events.get("attack2"):
        if input_print_limiter.can_print(f"attack2_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Attack2 event triggered.")
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
                    'attack' in player.animations and player.animations['attack']:
                # If attack2 is pressed without a prior attack1, treat as attack1
                player.attack_type = 1
                selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim and player.animations.get('attack') else 'attack_nm'

            if selected_attack2_anim_key and player.animations.get(selected_attack2_anim_key):
                player.set_state(selected_attack2_anim_key)
            elif selected_attack2_anim_key: # Fallback if specific (e.g. _nm) variant missing
                player.set_state('attack_nm' if 'attack_nm' in player.animations else 'attack')


    # Dash action (event-driven)
    if action_events.get("dash"):
        if input_print_limiter.can_print(f"dash_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Dash event triggered.")
        if player.on_ground and not player.is_dashing and not player.is_rolling and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('dash')

    # Roll action (event-driven)
    if action_events.get("roll"):
        if input_print_limiter.can_print(f"roll_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Roll event triggered.")
        if player.on_ground and not player.is_rolling and not player.is_dashing and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('roll')

    # Crouch/Slide action (event-driven for slide initiation, state for crouch)
    if action_events.get("down"): # "down" is the internal action from JSON's "CROUCH"
        if input_print_limiter.can_print(f"down_action_event_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Down event triggered (from JSON 'CROUCH' or 'MOVE_DOWN').")
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
                player.is_crouching = False # Slide is not crouch
        else: # Not sliding, so consider crouching
            can_player_toggle_crouch = player.on_ground and not player.on_ladder and \
                                        not player.is_sliding and \
                                        not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                            player.state in ['turn','hit','death','death_nm'])
            if can_player_toggle_crouch:
                if not player.is_crouching: # If not already crouching, start crouching
                    player.is_crouching = True
                    player.is_sliding = False # Ensure sliding is off
                    # Transition to crouch animation
                    if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
                        player.state not in ['crouch','crouch_walk','crouch_trans']:
                        player.set_state('crouch_trans')
                    elif player.state not in ['crouch', 'crouch_walk', 'crouch_trans']: # Directly to crouch if no transition
                        player.set_state('crouch')
                # If already crouching, holding "down" keeps crouching (handled by is_holding_crouch_ability_key)

    # Interact action (event-driven)
    if action_events.get("interact"):
        if input_print_limiter.can_print(f"interact_action_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Interact event triggered.")
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False
            player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder: # If on ladder and interact is pressed again, drop off
            player.on_ladder = False
            player.set_state('fall' if not player.on_ground else 'idle')

    # Projectile firing (event-driven)
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


    # --- Part 5: Update state based on continuous movement if no overriding action/event occurred ---
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
            if abs(player.vel.y) > 0.1 : # Moving on ladder
                if player.state != 'ladder_climb': player.set_state('ladder_climb')
            else: # Stationary on ladder
                if player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: # This state is set by holding "down"
                 target_crouch_state_key = 'crouch_walk' if player_intends_horizontal_move and \
                                             player.animations.get('crouch_walk') \
                                             else 'crouch'
                 if player.state != target_crouch_state_key:
                    player.set_state(target_crouch_state_key)
             elif player_intends_horizontal_move: # Standing and moving
                 if player.state != 'run': player.set_state('run')
             else: # Standing and still
                 if player.state != 'idle': player.set_state('idle')
        else: # In air, not on ladder
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling: # Wall interaction
                 current_wall_time_ms = pygame.time.get_ticks()
                 is_wall_climb_duration_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and
                                                   current_wall_time_ms - player.wall_climb_timer > player.wall_climb_duration)

                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or is_wall_climb_duration_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and \
                      not is_wall_climb_duration_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else: # Default to wall slide if conditions for climb aren't met but touching wall
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']: # Falling
                  if player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall']: # Default to idle if in air but not specifically jumping/falling (e.g. just after jump peak)
                  if player.state != 'idle': player.set_state('idle')

    return action_events
########## END OF FILE: player_input_handler.py ##########