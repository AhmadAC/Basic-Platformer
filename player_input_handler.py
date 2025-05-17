# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.4 (Crouch toggle logic, reset action event)
Handles processing of player input and translating it to actions.
"""
import pygame
import constants as C
import config as game_config
import joystick_handler
from utils import PrintLimiter

input_print_limiter = PrintLimiter(default_limit=20, default_period=5.0)

def process_player_input_logic(player, keys_pressed_from_pygame, pygame_events,
                               active_mappings, platforms_group):
    if not player._valid_init: return {}

    current_time_ms = pygame.time.get_ticks()
    player_id_str = f"P{player.player_id}"

    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                       getattr(player, 'is_petrified', False)

    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS} # Events trigger once

    prev_joystick_up_state = getattr(player, '_prev_joystick_up_state', False)
    # prev_joystick_down_state no longer needed for crouch hold

    if is_input_blocked:
        player.acc.x = 0
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        # player.is_holding_climb_ability_key = False # Keep for continuous states if needed
        # player.is_holding_crouch_ability_key is managed by toggle logic now
        setattr(player, '_prev_joystick_up_state', False)
        # setattr(player, '_prev_joystick_down_state', False) # Not strictly needed anymore
        return action_events # Return empty events if blocked

    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")
    joystick_instance = None

    if is_joystick_input_type and player.joystick_id_idx is not None:
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if not joystick_instance:
            if input_print_limiter.can_print(f"joy_missing_{player_id_str}"):
                print(f"INPUT_HANDLER ({player_id_str}): Joystick instance for ID {player.joystick_id_idx} not found.")
            is_joystick_input_type = False

    # --- Part 1: Populate action_state (continuous held inputs like movement and aiming) ---
    if not is_joystick_input_type: # Keyboard
        for action_name in ["left", "right", "up", "down"]: # "down" can still be used for aiming/ladders
            key_code = active_mappings.get(action_name)
            if key_code is not None and isinstance(key_code, int):
                action_state[action_name] = keys_pressed_from_pygame[key_code]
    else: # Joystick
        if joystick_instance:
            for action_name in ["left", "right", "up", "down"]: # "down" for aiming/ladders
                mapping_details = active_mappings.get(action_name)
                if isinstance(mapping_details, dict):
                    m_type, m_id = mapping_details.get("type"), mapping_details.get("id")
                    m_value_prop = mapping_details.get("value") # Expected direction/value for axis/hat
                    m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                    if m_type == "axis" and m_id is not None and 0 <= m_id < joystick_instance.get_numaxes():
                        axis_val = joystick_instance.get_axis(m_id)
                        if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold: action_state[action_name] = True
                        elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold: action_state[action_name] = True
                    elif m_type == "hat" and m_id is not None and 0 <= m_id < joystick_instance.get_numhats():
                        if joystick_instance.get_hat(m_id) == m_value_prop: action_state[action_name] = True
    
    current_joystick_up_state_for_jump = action_state.get("up", False) if is_joystick_input_type else False


    # --- Part 2: Populate action_events (pressed-once this frame) ---
    for event in pygame_events:
        if not is_joystick_input_type: # Keyboard events
            if event.type == pygame.KEYDOWN:
                # Special handling for player-specific reset key (e.g., Key 6)
                if player.shadow_key and event.key == player.shadow_key: # P1: K_6, P2: K_KP_6
                    action_events["reset"] = True
                    if input_print_limiter.can_print(f"kb_event_{player_id_str}_reset_from_shadowkey"):
                        print(f"INPUT_HANDLER ({player_id_str}): KB KeyDown '{pygame.key.name(event.key)}' (Shadow/Reset Key) -> Event 'reset'")
                    continue # Event handled

                for action_name, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action_name] = True
                        # Special handling for jump via "up" key (if "up" is also "jump")
                        if action_name == "up" and active_mappings.get("jump") == key_code:
                            action_events["jump"] = True
                        # "down" key press generates "crouch" event for toggle
                        # Also check if "crouch" action is directly mapped to this key
                        if (action_name == "down" and active_mappings.get("down") == key_code) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == key_code):
                             action_events["crouch"] = True
                        if input_print_limiter.can_print(f"kb_event_{player_id_str}_{action_name}"):
                             print(f"INPUT_HANDLER ({player_id_str}): KB KeyDown '{pygame.key.name(event.key)}' -> Event '{action_name}'")
                        break
        else: # Joystick events
            if joystick_instance:
                event_is_for_this_joystick = False
                if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                    if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                    elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True # Fallback for older pygame

                if event_is_for_this_joystick:
                    if event.type == pygame.JOYBUTTONDOWN:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="button" and map_details.get("id")==event.button:
                                action_events[action_name] = True
                                # If button mapped to "down" (continuous aim) or "crouch" (toggle event)
                                if action_name == "down" or action_name == "crouch":
                                    action_events["crouch"] = True # Generate crouch toggle event
                                if input_print_limiter.can_print(f"joy_btn_{player_id_str}_{action_name}_{event.button}"):
                                    print(f"INPUT_HANDLER ({player_id_str}): JoyButton {event.button} -> Event '{action_name}'")
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="hat" and map_details.get("id")==event.hat and map_details.get("value")==event.value:
                                if action_name in C.JOYSTICK_HAT_EVENT_ACTIONS:
                                    action_events[action_name] = True
                                    if action_name == "down" or action_name == "crouch":
                                        action_events["crouch"] = True
                                    if input_print_limiter.can_print(f"joy_hat_{player_id_str}_{action_name}"):
                                        print(f"INPUT_HANDLER ({player_id_str}): JoyHat {event.hat} Val {event.value} -> Event '{action_name}'")
                                break
                    elif event.type == pygame.JOYAXISMOTION: # For axes mapped to event-like actions
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type") == "axis" and map_details.get("id") == event.axis:
                                if action_name in C.JOYSTICK_AXIS_EVENT_ACTIONS:
                                    axis_val = event.value
                                    m_value_prop = map_details.get("value")
                                    m_threshold = map_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                    passed_thresh = False
                                    if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold: passed_thresh = True
                                    elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold: passed_thresh = True
                                    
                                    axis_event_active_attr = f"_axis_event_active_{action_name}" # e.g. _axis_event_active_jump
                                    if passed_thresh and not getattr(player, axis_event_active_attr, False):
                                        action_events[action_name] = True
                                        if action_name == "down" or action_name == "crouch":
                                            action_events["crouch"] = True
                                        setattr(player, axis_event_active_attr, True)
                                        if input_print_limiter.can_print(f"joy_axis_event_{player_id_str}_{action_name}"):
                                            print(f"INPUT_HANDLER ({player_id_str}): JoyAxis {event.axis} Val {axis_val:.2f} -> Event '{action_name}' (Thresh: {m_threshold})")
                                    elif not passed_thresh: # Axis returned to neutral for this action
                                         setattr(player, axis_event_active_attr, False)
                                break
    
    # --- Part 3: Update player intention states (continuous states for movement/aiming) ---
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    # player.is_holding_crouch_ability_key is no longer the primary driver for player.is_crouching.
    # It's used for:
    #   1. Aiming down (along with player.is_crouching if toggle is on).
    #   2. Transitioning from slide_end to crouch if held.
    player.is_holding_crouch_ability_key = action_state["down"]

    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching: # Aim down if holding down OR if crouch is toggled on
        aim_y = 1.0

    if aim_x != 0.0 or aim_y != 0.0: # Update aim direction if there's input
        player.fireball_last_input_dir.x, player.fireball_last_input_dir.y = aim_x, aim_y
    elif player.fireball_last_input_dir.length_squared() == 0: # Fallback if no input and no prior aim
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0


    # --- Part 4: Translate events and states into player logic/actions ---
    player.acc.x = 0 # Reset horizontal acceleration each frame
    player_intends_horizontal_move = False
    can_control_horizontal = not (player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
                                 (player.is_attacking and player.state.endswith('_nm')) or # No movement during no-movement attacks
                                 player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang'])

    if can_control_horizontal:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL; player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and player.state in ['idle','run']: player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL; player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and player.state in ['idle','run']: player.set_state('turn')
            player.facing_right = True

    # Ladder movement
    if player.on_ladder:
         player.vel.y = 0 # Stop gravity/falling on ladder
         if player.is_holding_climb_ability_key: # Continuous "up" state
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif action_state["down"]: # Continuous "down" state for ladder down
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED


    # JUMP LOGIC:
    joystick_up_just_pressed_for_jump = is_joystick_input_type and current_joystick_up_state_for_jump and not prev_joystick_up_state
    if action_events.get("jump") or joystick_up_just_pressed_for_jump:
        if input_print_limiter.can_print(f"jump_attempt_{player_id_str}"):
            print(f"INPUT_HANDLER ({player_id_str}): Jump attempt. Event: {action_events.get('jump')}, JoyUpJustPressed: {joystick_up_just_pressed_for_jump}. OnGround: {player.on_ground}, State: {player.state}")
        
        can_jump_now = not player.is_attacking and not player.is_rolling and not player.is_sliding and \
                       not player.is_dashing and player.state not in ['turn','hit','death','death_nm']
        
        if can_jump_now:
            # If crouching, try to stand up first. If cannot stand, cannot jump.
            if player.is_crouching:
                if player.can_stand_up(platforms_group): # platforms_group is now passed
                    player.is_crouching = False # Stand up
                    # State will be set to 'jump' below if conditions met
                else: # Cannot stand, so cannot jump from crouch
                    can_jump_now = False # Prevent jump
            
            if can_jump_now: # Re-check after potential stand-up attempt
                if player.on_ground:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH; player.set_state('jump'); player.on_ground = False
                elif player.on_ladder:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8
                    player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)
                    player.on_ladder = False; player.set_state('jump')
                elif player.can_wall_jump and player.touching_wall != 0:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH
                    player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall) # Push away from wall
                    player.facing_right = not player.facing_right; player.set_state('jump')
                    player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0

    # CROUCH TOGGLE / SLIDE LOGIC
    if action_events.get("crouch"): # "crouch" event now drives the toggle
        if input_print_limiter.can_print(f"crouch_event_toggle_check_{player_id_str}"):
             print(f"INPUT_HANDLER ({player_id_str}): Crouch TOGGLE event. IsCrouching: {player.is_crouching}, OnGround: {player.on_ground}, State: {player.state}, VelX: {player.vel.x:.2f}")

        if player.is_crouching: # If already crouching, stand up
            if player.can_stand_up(platforms_group): # platforms_group is now passed
                player.is_crouching = False
                player.set_state('run' if player_intends_horizontal_move else 'idle')
            else:
                if input_print_limiter.can_print(f"cant_stand_{player_id_str}"):
                    print(f"INPUT_HANDLER ({player_id_str}): Cannot stand, blocked.")
        else: # Not crouching, try to crouch or slide
            can_slide_now = player.on_ground and player.state == 'run' and \
                                 abs(player.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                 not player.is_sliding and not player.is_attacking and \
                                 not player.is_rolling and not player.is_dashing and \
                                 not player.on_ladder and player.state not in ['turn','hit']
            if can_slide_now:
                player.set_state('slide_trans_start' if player.animations.get('slide_trans_start') else 'slide')
            else: # Try to crouch
                can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                                   not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                        player.state in ['turn','hit','death','death_nm'])
                if can_crouch_now:
                    player.is_crouching = True
                    player.set_state('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')
    
    # If player.is_crouching (toggled on) and tries to move, transition from 'crouch' to 'crouch_walk'
    if player.is_crouching and player_intends_horizontal_move and player.state == 'crouch':
        player.set_state('crouch_walk')
    # If player.is_crouching, was in 'crouch_walk' but stops moving, transition to 'crouch'
    elif player.is_crouching and not player_intends_horizontal_move and player.state == 'crouch_walk':
        player.set_state('crouch')


    # ATTACK1 / ATTACK2
    if action_events.get("attack1"):
        if input_print_limiter.can_print(f"atk1_event_{player_id_str}"): print(f"INPUT_HANDLER ({player_id_str}): Attack1 event.")
        can_attack_melee = not player.is_attacking and not player.is_dashing and not player.is_rolling and \
                           not player.is_sliding and not player.on_ladder and player.state not in ['turn','hit']
        if can_attack_melee:
            player.attack_type = 4 if player.is_crouching else 1 # 4 is crouch_attack, 1 is standing primary
            anim_key_attack1 = 'crouch_attack' if player.is_crouching else \
                               ('attack' if player_intends_horizontal_move else 'attack_nm')
            player.set_state(anim_key_attack1)

    if action_events.get("attack2"):
        if input_print_limiter.can_print(f"atk2_event_{player_id_str}"): print(f"INPUT_HANDLER ({player_id_str}): Attack2 event.")
        can_attack_melee2 = not player.is_dashing and not player.is_rolling and not player.is_sliding and \
                            not player.on_ladder and player.state not in ['turn','hit']
        if can_attack_melee2:
            is_moving_for_attack2 = player_intends_horizontal_move
            if player.is_crouching and not player.is_attacking : # If crouched and not already attacking
                player.attack_type = 4; anim_key_attack2 = 'crouch_attack' # Re-use crouch_attack
            elif not player.is_attacking: # Standing/running attack2
                player.attack_type = 2; anim_key_attack2 = 'attack2' if is_moving_for_attack2 else 'attack2_nm'
            else: # Already attacking (e.g. combo) - this part might need more complex combo logic
                anim_key_attack2 = None # Or transition to combo state if applicable
            if anim_key_attack2: player.set_state(anim_key_attack2)

    # DASH / ROLL
    if action_events.get("dash"):
        if player.on_ground and not player.is_dashing and not player.is_rolling and not player.is_attacking and \
           not player.is_crouching and not player.on_ladder and player.state not in ['turn','hit']:
            player.set_state('dash')

    if action_events.get("roll"):
        if player.on_ground and not player.is_rolling and not player.is_dashing and not player.is_attacking and \
           not player.is_crouching and not player.on_ladder and player.state not in ['turn','hit']:
            player.set_state('roll')

    # INTERACT LOGIC
    if action_events.get("interact"):
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder: # Get off ladder
            player.on_ladder = False; player.set_state('fall' if not player.on_ground else 'idle')

    # PROJECTILE LOGIC (Excluding Key 6/Shadow as it's now Reset for keyboard)
    # For joystick, if "projectile6" is mapped to "reset", it will also be handled by "reset" event.
    can_fire_projectiles = not player.is_crouching and not player.is_attacking and not player.is_dashing and \
                           not player.is_rolling and not player.is_sliding and not player.on_ladder and \
                           player.state not in ['turn','hit','death','death_nm','wall_climb','wall_hang','wall_slide']
    if can_fire_projectiles:
        if action_events.get("projectile1"): player.fire_fireball()
        elif action_events.get("projectile2"): player.fire_poison()
        elif action_events.get("projectile3"): player.fire_bolt()
        elif action_events.get("projectile4"): player.fire_blood()
        elif action_events.get("projectile5"): player.fire_ice()
        # No "projectile6" here as it's handled by "reset" for keyboard
        elif action_events.get("projectile7"): player.fire_grey()


    # --- Part 5: Update state based on continuous movement if no overriding action/event occurred ---
    is_in_override_state_for_movement = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                        player.is_taking_hit or player.state in [
                                            'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                            'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                            'wall_hang','wall_slide', 'ladder_idle','ladder_climb']
    if not is_in_override_state_for_movement:
        if player.on_ladder: # Already handled by continuous input check above
            if abs(player.vel.y) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: # If crouch is toggled on
                 if player_intends_horizontal_move and player.animations.get('crouch_walk'):
                     if player.state != 'crouch_walk': player.set_state('crouch_walk')
                 else: # Not moving or no crouch_walk anim
                     if player.state != 'crouch': player.set_state('crouch')
             elif player_intends_horizontal_move: # Standing and moving
                 if player.state != 'run': player.set_state('run')
             else: # Standing and idle
                 if player.state != 'idle': player.set_state('idle')
        else: # In air
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling:
                 wall_time = pygame.time.get_ticks()
                 climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and \
                                  wall_time - player.wall_climb_timer > player.wall_climb_duration)
                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and not climb_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else: # Default to wall_slide if conditions for climb not met but touching wall
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                  if player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall']: # Not significantly falling, default to idle (might be a small hop)
                  if player.state != 'idle': player.set_state('idle')

    # Update previous joystick state for next frame's "just pressed" detection
    setattr(player, '_prev_joystick_up_state', current_joystick_up_state_for_jump)
    
    return action_events # Return all events processed this frame