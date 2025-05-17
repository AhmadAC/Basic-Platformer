# player_input_handler.py
import pygame
import constants as C
import config as game_config # For GAME_ACTIONS
import joystick_handler      # For get_joystick_instance

def process_player_input_logic(player, keys_pressed_from_pygame, pygame_events,
                               active_mappings): # active_mappings now comes from game_config.P1/P2_MAPPINGS
    if not player._valid_init: return {}

    current_time_ms = pygame.time.get_ticks()
    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                       getattr(player, 'is_petrified', False)

    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS}

    if is_input_blocked:
        player.acc.x = 0
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        player.is_holding_crouch_ability_key = False
        return action_events

    # Determine input type (keyboard or joystick) based on the structure of active_mappings
    # A simple check: if a known action like "left" maps to an int, it's keyboard. If dict, it's joystick.
    left_mapping_example = active_mappings.get("left")
    is_joystick_input_type = isinstance(left_mapping_example, dict)
    joystick_instance = None

    if is_joystick_input_type and player.joystick_id_idx is not None:
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if not joystick_instance:
            if player.print_limiter.can_print(f"joy_missing_handler_{player.player_id}"):
                print(f"PlayerInput (P{player.player_id}): Joystick instance for ID {player.joystick_id_idx} not found by handler. Input for joystick will fail.")
            is_joystick_input_type = False # Fallback to no input effectively if joystick obj is missing

    # --- Populate action_state (held down) ---
    if not is_joystick_input_type: # KEYBOARD
        for action, key_code in active_mappings.items():
            if isinstance(key_code, int): # Ensure it's a keycode
                action_state[action] = keys_pressed_from_pygame[key_code]
    else: # JOYSTICK
        if joystick_instance:
            for action, mapping_details in active_mappings.items():
                if not isinstance(mapping_details, dict): continue # Skip if not a joystick mapping dict

                m_type = mapping_details.get("type")
                m_id = mapping_details.get("id")
                m_val_expected = mapping_details.get("value") # For axis (+1/-1) or hat ((x,y) tuple)
                m_threshold = mapping_details.get("threshold", C.AXIS_THRESHOLD if hasattr(C,'AXIS_THRESHOLD') else 0.7) # Use constant from your game if available

                if m_type == "button" and m_id is not None:
                    if 0 <= m_id < joystick_instance.get_numbuttons():
                        action_state[action] = joystick_instance.get_button(m_id)
                elif m_type == "axis" and m_id is not None and m_val_expected is not None:
                    if 0 <= m_id < joystick_instance.get_numaxes():
                        axis_current_val = joystick_instance.get_axis(m_id)
                        if m_val_expected < 0 and axis_current_val < -m_threshold:
                            action_state[action] = True
                        elif m_val_expected > 0 and axis_current_val > m_threshold:
                            action_state[action] = True
                elif m_type == "hat" and m_id is not None and m_val_expected is not None:
                    if 0 <= m_id < joystick_instance.get_numhats():
                        hat_current_val = joystick_instance.get_hat(m_id) # Returns tuple (x,y)
                        if hat_current_val == tuple(m_val_expected): # Ensure m_val_expected is a tuple for hats
                            action_state[action] = True
                
                # Handle alt_mappings if primary not triggered (e.g. D-pad for movement if analog stick is neutral)
                alt_type = mapping_details.get("alt_type")
                if not action_state.get(action) and alt_type: # Only check alt if primary didn't set it
                    alt_id = mapping_details.get("alt_id")
                    alt_val_expected = mapping_details.get("alt_value")
                    alt_threshold = mapping_details.get("alt_threshold", m_threshold)
                    if alt_type == "hat" and alt_id is not None and alt_val_expected is not None:
                        if 0 <= alt_id < joystick_instance.get_numhats():
                             if joystick_instance.get_hat(alt_id) == tuple(alt_val_expected): action_state[action] = True
                    elif alt_type == "axis" and alt_id is not None and alt_val_expected is not None:
                        if 0 <= alt_id < joystick_instance.get_numaxes():
                            axis_val = joystick_instance.get_axis(alt_id)
                            if alt_val_expected < 0 and axis_val < -alt_threshold: action_state[action] = True
                            elif alt_val_expected > 0 and axis_val > alt_threshold: action_state[action] = True


    # --- Populate action_events (pressed once) ---
    for event in pygame_events:
        if not is_joystick_input_type: # KEYBOARD events
            if event.type == pygame.KEYDOWN:
                for action, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action] = True
                        # Special case: if 'up' key is also 'jump' key
                        if action == "up" and active_mappings.get("jump") == key_code:
                            action_events["jump"] = True
                        break
        else: # JOYSTICK events
            if joystick_instance and hasattr(event, 'joy') and event.joy == player.joystick_id_idx:
                if event.type == pygame.JOYBUTTONDOWN:
                    for action, mapping_details in active_mappings.items():
                        if isinstance(mapping_details, dict) and \
                           mapping_details.get("type") == "button" and \
                           mapping_details.get("id") == event.button:
                            action_events[action] = True
                            # Example: if jump is mapped to a button that also means "up" in menu context
                            if action == "jump": # Assume jump is a primary action
                                pass
                            elif action == "up" and active_mappings.get("jump") == mapping_details:
                                action_events["jump"] = True # If 'up' can also trigger 'jump'
                            break
                elif event.type == pygame.JOYHATMOTION:
                    for action, mapping_details in active_mappings.items():
                        if isinstance(mapping_details, dict) and \
                           mapping_details.get("type") == "hat" and \
                           mapping_details.get("id") == event.hat and \
                           tuple(mapping_details.get("value", (None,None))) == event.value:
                            # Typically, hat events are for menus or discrete D-pad presses
                            # If a hat direction is directly mapped to an action like "jump", it would trigger here.
                            # For now, assume only menu actions get event status from hats, gameplay states are preferred for held.
                            if action.startswith("menu_") or action == "jump": # Example if hat can jump
                                action_events[action] = True
                            break
                # JOYAXISMOTION events are usually for continuous state (action_state),
                # but you could define some to be one-shot events if an axis *crosses* a threshold.
                # For simplicity, this example doesn't make axis movements into one-shot action_events.

    # --- Apply actions based on state and events ---
    # (This part of your logic using player.is_trying_to_move_left, etc., can remain similar,
    # as those flags are now set based on action_state correctly for both keyboard and joystick)

    player.is_trying_to_move_left = action_state.get("left", False)
    player.is_trying_to_move_right = action_state.get("right", False)
    player.is_holding_climb_ability_key = action_state.get("up", False) # Or map a specific "climb_hold" action
    player.is_holding_crouch_ability_key = action_state.get("down", False)

    # Update fireball aim direction based on *held* directionals
    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if action_state.get("left", False): fireball_aim_x_input = -1.0
    elif action_state.get("right", False): fireball_aim_x_input = 1.0
    if action_state.get("up", False): fireball_aim_y_input = -1.0
    elif action_state.get("down", False): fireball_aim_y_input = 1.0

    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0: # Fallback if no directional input
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    # ... (rest of your input processing logic using action_state and action_events) ...
    # Example:
    # if action_events.get("jump"):
    #     player.jump_action() # Call a method on player
    # if action_state.get("attack1"): # Or action_events.get("attack1") if it's a press-once
    #     player.attack1_action()

    # This is where your existing logic for player.acc.x, set_state, firing projectiles etc. goes,
    # but now it uses action_state for held inputs and action_events for pressed-once inputs.

    player.acc.x = 0
    player_intends_horizontal_move = False

    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )

    if can_player_control_horizontal_movement:
        if action_state.get("left") and not action_state.get("right"): # Use .get for safety
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = False
        elif action_state.get("right") and not action_state.get("left"):
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
         player.vel.y = 0
         if action_state.get("up"): player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif action_state.get("down"): player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    # Jump action based on event
    if action_events.get("jump"): # "jump" is now a distinct game action
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
                # ... (ladder jump logic)
                player.is_crouching = False
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)
                player.on_ladder = False
                player.set_state('jump')
            elif player.can_wall_jump and player.touching_wall != 0:
                # ... (wall jump logic)
                player.is_crouching = False
                player.vel.y = C.PLAYER_JUMP_STRENGTH
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)
                player.facing_right = not player.facing_right
                player.set_state('jump')
                player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0


    # Attack1
    if action_events.get("attack1"):
        # ... (your existing attack1 logic) ...
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


    # Attack2 / Combo
    if action_events.get("attack2"):
        # ... (your existing attack2/combo logic) ...
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
                player.attack_type = 1
                selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim and player.animations.get('attack') else 'attack_nm'

            if selected_attack2_anim_key and player.animations.get(selected_attack2_anim_key):
                player.set_state(selected_attack2_anim_key)
            elif selected_attack2_anim_key: # Fallback if specific (nm) variant not found
                player.set_state('attack_nm' if 'attack_nm' in player.animations else 'attack') # Simplified fallback


    # Dash
    if action_events.get("dash"):
        # ... (your dash logic) ...
        if player.on_ground and not player.is_dashing and not player.is_rolling and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('dash')

    # Roll
    if action_events.get("roll"):
        # ... (your roll logic) ...
        if player.on_ground and not player.is_rolling and not player.is_dashing and \
            not player.is_attacking and not player.is_crouching and not player.on_ladder and \
            player.state not in ['turn','hit']:
            player.set_state('roll')


    # Interact (e.g., ladders)
    if action_events.get("interact"):
        # ... (your interact logic) ...
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False
            player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.on_ladder = False
            player.set_state('fall' if not player.on_ground else 'idle')


    # Projectiles
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


    # Logic for initiating slide from 'down' event if conditions are met
    if action_events.get("down"): # 'down' here means the down key/button was pressed *this frame*
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
                player.is_crouching = False # Slide implies not just stationary crouching
        else:
            # If not sliding, then a "down" event might toggle crouch
            can_player_toggle_crouch = player.on_ground and not player.on_ladder and \
                                        not player.is_sliding and \
                                        not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                            player.state in ['turn','hit','death','death_nm'])
            if can_player_toggle_crouch:
                if not player.is_crouching: # If was not crouching, start crouching
                    player.is_crouching = True
                    player.is_sliding = False
                    if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
                        player.state not in ['crouch','crouch_walk','crouch_trans']:
                        player.set_state('crouch_trans')
                    elif player.state not in ['crouch', 'crouch_walk', 'crouch_trans']:
                        player.set_state('crouch')
                # If already crouching, a "down" event doesn't toggle it off.
                # Toggling off crouch happens when 'down' is *not* held (handled by player.is_holding_crouch_ability_key elsewhere)


    # Update states based on *held* inputs (if not in a overriding state)
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
            if abs(player.vel.y) > 0.1 : # vel.y is set by up/down state for ladders
                if player.state != 'ladder_climb': player.set_state('ladder_climb')
            else:
                if player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: # This flag is set if 'down' is held
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
                 # ... (wall slide/climb logic based on player.is_holding_climb_ability_key)
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
             elif player.state not in ['jump','jump_fall_trans','fall']: # Not falling significantly, not on wall
                  if player.state != 'idle': player.set_state('idle') # Default to idle if in air but not moving much vertically

    return action_events