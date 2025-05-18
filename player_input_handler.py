#################### START OF MODIFIED FILE: player_input_handler.py ####################

# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.2.0 (Defined joystick_up_just_pressed_for_jump)
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

    # Player is on fire (any visual fire state)
    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    
    # Conditions that fully block most game actions (except crouch if on fire)
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')

    # Conditions that block actions but might allow movement if on fire
    # is_taking_hit flag is true for hit_duration after taking damage
    is_stunned_or_busy_general = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                  player.is_attacking or player.is_dashing or player.is_rolling or \
                                  player.is_sliding or player.state == 'turn'


    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS}

    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")
    joystick_instance = None
    if is_joystick_input_type and player.joystick_id_idx is not None:
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if not joystick_instance:
            if input_print_limiter.can_print(f"joy_missing_{player_id_str}"):
                print(f"INPUT_HANDLER ({player_id_str}): Joystick instance for ID {player.joystick_id_idx} not found.")
            is_joystick_input_type = False


    # --- Part 1: Process universal events (reset, pause) ---
    # These should be processed regardless of player state (unless truly dead/petrified?)
    for event in pygame_events:
        if not is_joystick_input_type: # Keyboard input
            if event.type == pygame.KEYDOWN:
                if (player.shadow_key and event.key == player.shadow_key) or \
                   (active_mappings.get("reset") == event.key):
                    action_events["reset"] = True
                elif active_mappings.get("pause") == event.key:
                    action_events["pause"] = True
        else: # Joystick input
            if joystick_instance:
                event_is_for_this_joystick = False
                if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                    if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                    elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True
                
                if event_is_for_this_joystick:
                    for action_name_check in ["reset", "pause"]: # Check "reset" and "pause" specifically
                        mapping = active_mappings.get(action_name_check)
                        if isinstance(mapping, dict): # Joystick mappings are dicts
                            if event.type == pygame.JOYBUTTONDOWN and mapping.get("type") == "button" and mapping.get("id") == event.button:
                                action_events[action_name_check] = True
                            elif event.type == pygame.JOYHATMOTION and mapping.get("type") == "hat" and mapping.get("id") == event.hat and mapping.get("value") == event.value:
                                action_events[action_name_check] = True
                            elif event.type == pygame.JOYAXISMOTION and mapping.get("type") == "axis" and mapping.get("id") == event.axis:
                                axis_val = event.value
                                m_val_prop = mapping.get("value") # Expected direction (-1 or 1)
                                m_thresh = mapping.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                passed_thresh = (isinstance(m_val_prop, (int,float)) and 
                                                 ((m_val_prop < 0 and axis_val < -m_thresh) or (m_val_prop > 0 and axis_val > m_thresh)))
                                
                                axis_event_active_attr = f"_axis_event_active_{action_name_check}"
                                if passed_thresh and not getattr(player, axis_event_active_attr, False):
                                    action_events[action_name_check] = True
                                    setattr(player, axis_event_active_attr, True)
                                elif not passed_thresh:
                                    setattr(player, axis_event_active_attr, False)


    # --- Part 2: Populate action_state (continuous held inputs for movement/aiming) ---
    # This is NOT BLOCKED by is_fully_action_blocked or is_on_fire.
    if not is_joystick_input_type: # Keyboard
        for action_name in ["left", "right", "up", "down"]:
            key_code = active_mappings.get(action_name)
            if key_code is not None and isinstance(key_code, int): # Check if it's an int (pygame key const)
                action_state[action_name] = keys_pressed_from_pygame[key_code]
    else: # Joystick
        if joystick_instance:
            for action_name in ["left", "right", "up", "down"]:
                mapping_details = active_mappings.get(action_name)
                if isinstance(mapping_details, dict): # Joystick mappings are dicts
                    m_type, m_id = mapping_details.get("type"), mapping_details.get("id")
                    m_value_prop = mapping_details.get("value") # Expected direction for axis/hat
                    m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)

                    if m_type == "axis" and m_id is not None and 0 <= m_id < joystick_instance.get_numaxes():
                        axis_val = joystick_instance.get_axis(m_id)
                        if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold:
                            action_state[action_name] = True
                        elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold:
                            action_state[action_name] = True
                    elif m_type == "hat" and m_id is not None and 0 <= m_id < joystick_instance.get_numhats():
                        if joystick_instance.get_hat(m_id) == m_value_prop: # m_value_prop is (x,y) tuple for hat
                            action_state[action_name] = True
                    # Buttons are typically events, not held states for movement, but could be mapped.
                    elif m_type == "button" and m_id is not None and 0 <= m_id < joystick_instance.get_numbuttons():
                        if joystick_instance.get_button(m_id):
                             action_state[action_name] = True


    current_joystick_up_state_for_jump = action_state.get("up", False) if is_joystick_input_type else False
    # ***** DEFINITION OF joystick_up_just_pressed_for_jump ADDED HERE *****
    joystick_up_just_pressed_for_jump = is_joystick_input_type and current_joystick_up_state_for_jump and not getattr(player, '_prev_joystick_up_state', False)


    # Update player's intent flags based on action_state
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]
    
    # Aiming logic
    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching: aim_y = 1.0 # Aim down if holding down OR if already crouching
    
    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.x, player.fireball_last_input_dir.y = aim_x, aim_y
    elif player.fireball_last_input_dir.length_squared() == 0: # If still zero (e.g. at start)
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0


    # --- If fully action blocked, only return reset/pause events ---
    if is_fully_action_blocked:
        player.acc.x = 0 # Ensure no movement if fully blocked
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- Part 3: Populate remaining action_events (pressed-once for game actions) ---
    # Only process these if not fully blocked.
    # Individual actions will be further gated by `is_on_fire_visual` or `is_stunned_or_busy_general`.
    for event in pygame_events:
        # Skip reset/pause events as they are already handled universally
        if not is_joystick_input_type and event.type == pygame.KEYDOWN:
            # Check if it's a reset or pause key already processed
            is_reset_key = (player.shadow_key and event.key == player.shadow_key) or \
                           (active_mappings.get("reset") == event.key)
            is_pause_key = active_mappings.get("pause") == event.key
            if not (is_reset_key or is_pause_key):
                for action_name, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action_name] = True
                        # Special handling for combined keys like up/jump or down/crouch
                        if action_name == "up" and active_mappings.get("jump") == key_code: action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == key_code) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == key_code):
                             action_events["crouch"] = True
                        break # Found the action for this key
        elif is_joystick_input_type and joystick_instance:
            event_is_for_this_joystick = False
            if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True
            
            if event_is_for_this_joystick:
                # Check if it's a universal joy event already processed
                is_universal_joy_event = False
                if event.type == pygame.JOYBUTTONDOWN:
                    if (isinstance(active_mappings.get("reset"), dict) and active_mappings["reset"].get("type") == "button" and active_mappings["reset"].get("id") == event.button) or \
                       (isinstance(active_mappings.get("pause"), dict) and active_mappings["pause"].get("type") == "button" and active_mappings["pause"].get("id") == event.button):
                        is_universal_joy_event = True
                
                if not is_universal_joy_event: # Process other game actions
                    if event.type == pygame.JOYBUTTONDOWN:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="button" and map_details.get("id")==event.button:
                                action_events[action_name] = True
                                if action_name == "down" or action_name == "crouch": action_events["crouch"] = True # Consolidate crouch
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="hat" and map_details.get("id")==event.hat and map_details.get("value")==event.value:
                                if action_name in C.JOYSTICK_HAT_EVENT_ACTIONS: # Only trigger event actions for hats
                                    action_events[action_name] = True
                                    if action_name == "down" or action_name == "crouch": action_events["crouch"] = True # Consolidate
                                break
                    elif event.type == pygame.JOYAXISMOTION: # Handle axis events for actions
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type") == "axis" and map_details.get("id") == event.axis:
                                if action_name in C.JOYSTICK_AXIS_EVENT_ACTIONS: # Only trigger event actions for axes
                                    axis_val = event.value; m_value_prop = map_details.get("value"); m_threshold = map_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                    passed_thresh = (isinstance(m_value_prop, (int,float)) and ((m_value_prop < 0 and axis_val < -m_threshold) or (m_value_prop > 0 and axis_val > m_threshold)))
                                    axis_event_active_attr = f"_axis_event_active_{action_name}"
                                    if passed_thresh and not getattr(player, axis_event_active_attr, False):
                                        action_events[action_name] = True
                                        setattr(player, axis_event_active_attr, True)
                                    elif not passed_thresh:
                                        setattr(player, axis_event_active_attr, False)
                                break


    # --- Part 4: Translate events and states into player logic/actions ---
    player.acc.x = 0 # Reset horizontal acceleration each frame before applying new
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right
    
    # Horizontal movement control
    can_control_horizontal = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or # No move if no-movement attack
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang', 'frozen', 'defrost']
    )
    # If player is on fire, but also taking a hit (briefly), movement might still be blocked by 'hit' state
    # If player is on fire and NOT in 'hit' state, this condition allows movement.
    if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit':
        can_control_horizontal = False

    if can_control_horizontal:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
        player.acc.x = 0 # No horizontal movement on ladder by default
        if player.is_holding_climb_ability_key: # Holding UP on ladder
            player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
        elif player.is_holding_crouch_ability_key: # Holding DOWN on ladder
            player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED
        else: player.vel.y = 0


    # CROUCH LOGIC - Allow crouching/uncrouching even if on fire
    if action_events.get("crouch"):
        if player.is_crouching: # Trying to uncrouch
            if player.can_stand_up(platforms_group):
                player.is_crouching = False
                # Determine next state based on fire status and movement intent
                if player.is_aflame or player.is_deflaming: # If was on fire
                    next_fire_state = 'burning' if player.is_aflame else 'deflame'
                    player.set_state(next_fire_state)
                else: # Not on fire
                    player.set_state('run' if player_intends_horizontal_move else 'idle')
            # else: cannot stand up, remain crouching
        else: # Trying to crouch
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                player.is_crouching = True
                # Determine next state based on fire status
                if player.is_aflame:
                    player.set_state('aflame_crouch') # Start with initial crouch fire anim
                elif player.is_deflaming:
                    player.set_state('deflame_crouch')
                else: # Not on fire
                    player.set_state('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')

    # Visual state update if crouching and moving (even if on fire)
    if player.is_crouching and player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch': player.set_state('crouch_walk')
    elif player.is_crouching and not player_intends_horizontal_move: # Crouching and idle
        if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch') # Default to looping if already aflame
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch_walk': player.set_state('crouch')


    # --- JUMP LOGIC - REVISED FOR CLARITY AND TO ENSURE IT'S ALLOWED WHEN ON FIRE ---
    can_initiate_jump_action = True # Start by assuming jump is possible

    # 1. Check for actions that always block jumping
    if (player.is_attacking or player.is_dashing or 
        player.is_rolling or player.is_sliding):
        can_initiate_jump_action = False

    # 2. Check for states that always block jumping (fire states are NOT in this list)
    if player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost']:
        can_initiate_jump_action = False
        
    # 3. Special handling for 'hit' state and 'is_taking_hit' flag:
    #    If player is stunned (either in 'hit' state or invulnerability period)
    #    AND is NOT on fire, then block the jump.
    #    If player IS on fire, this entire block is skipped, allowing the jump.
    if not is_on_fire_visual: # Only apply these hit-related blocks if NOT on fire
        if player.state == 'hit':
            can_initiate_jump_action = False
        # If player is in hit cooldown (is_taking_hit), but not visually on fire, block jump.
        # This covers the invulnerability window after taking a normal hit.
        if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration):
            can_initiate_jump_action = False
            
    if (action_events.get("jump") or joystick_up_just_pressed_for_jump) and can_initiate_jump_action:
        can_actually_execute_jump = not player.is_crouching or player.can_stand_up(platforms_group)
        if player.is_crouching and can_actually_execute_jump:
            player.is_crouching = False 
            if player.is_aflame: player.set_state('burning') # Transition to standing fire before jump
            elif player.is_deflaming: player.set_state('deflame')
            # If not on fire, player.set_state('idle'/'run') will happen implicitly if needed before 'jump' state

        if can_actually_execute_jump:
            if player.on_ground:
                player.vel.y = C.PLAYER_JUMP_STRENGTH
                player.set_state('jump') 
                player.on_ground = False
            elif player.on_ladder:
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)
                player.on_ladder = False
                player.set_state('jump')
            elif player.can_wall_jump and player.touching_wall != 0:
                player.vel.y = C.PLAYER_JUMP_STRENGTH
                player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall) 
                player.facing_right = not player.facing_right 
                player.set_state('jump')
                player.can_wall_jump = False
                player.touching_wall = 0
                player.wall_climb_timer = 0
    # --- END OF JUMP LOGIC ---


    # --- Other actions (Attack, Roll, Dash, Projectiles) - BLOCKED IF ON FIRE OR STUNNED/BUSY ---
    can_perform_other_abilities = not is_on_fire_visual and not is_stunned_or_busy_general

    if action_events.get("attack1") and can_perform_other_abilities:
        player.attack_type = 4 if player.is_crouching else 1
        anim_key_attack1 = 'crouch_attack' if player.is_crouching else \
                           ('attack' if player_intends_horizontal_move else 'attack_nm')
        player.set_state(anim_key_attack1)

    if action_events.get("attack2") and can_perform_other_abilities:
        is_moving_for_attack2 = player_intends_horizontal_move
        if player.is_crouching and not player.is_attacking : # Only if not already attacking
            player.attack_type = 4; anim_key_attack2 = 'crouch_attack'
        elif not player.is_attacking: # Only if not already attacking
            player.attack_type = 2; anim_key_attack2 = 'attack2' if is_moving_for_attack2 else 'attack2_nm'
        else: anim_key_attack2 = None # Don't change state if already attacking
        if anim_key_attack2: player.set_state(anim_key_attack2)


    if action_events.get("dash") and can_perform_other_abilities:
        if player.on_ground: player.set_state('dash') # Simplified dash condition

    if action_events.get("roll") and can_perform_other_abilities:
        if player.on_ground: player.set_state('roll') # Simplified roll condition

    # Interact is NOT blocked by is_stunned_or_busy_general, but IS blocked by fire
    if action_events.get("interact") and not is_on_fire_visual:
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.on_ladder = False
            player.set_state('fall' if not player.on_ground else 'idle')


    if can_perform_other_abilities: # Projectiles blocked if on fire or stunned/busy
        if action_events.get("projectile1"): player.fire_fireball()
        elif action_events.get("projectile2"): player.fire_poison()
        elif action_events.get("projectile3"): player.fire_bolt()
        elif action_events.get("projectile4"): player.fire_blood()
        elif action_events.get("projectile5"): player.fire_ice()
        # shadow_key is P1_SHADOW_PROJECTILE_KEY (K_6) or P2_SHADOW_PROJECTILE_KEY (K_KP_6)
        # These are also used for reset if mapped directly in keyboard settings.
        # The `action_events["reset"]` is handled separately.
        # If "projectile6" is mapped for joysticks, it triggers `action_events.get("projectile6")`.
        if action_events.get("projectile6"): player.fire_shadow()
        elif action_events.get("projectile7"): player.fire_grey()


    # --- Auto-state updates based on physics (if not in an overriding action/status state) ---
    is_in_non_interruptible_state_for_auto = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost'
                                       # Fire states ARE interruptible by movement for visual changes
                                   ]
    
    if not is_in_non_interruptible_state_for_auto or is_on_fire_visual:
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching: # Already handled crouch_walk / crouch above, ensure it stays consistent
                 if player_intends_horizontal_move:
                     if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch_walk': player.set_state('crouch_walk')
                 else: # Crouching, not moving
                     if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch')
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch': player.set_state('crouch')
             elif player_intends_horizontal_move: # Standing, moving
                 if player.is_aflame and player.state not in ['burning','aflame']: player.set_state('burning')
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'run': player.set_state('run')
             else: # Standing, not moving
                 if player.is_aflame and player.state not in ['aflame', 'burning']: player.set_state('burning')
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'idle': player.set_state('idle')
        else: # In air
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual: # Wall interactions generally not while on fire
                 wall_time = pygame.time.get_ticks()
                 climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and \
                                  wall_time - player.wall_climb_timer > player.wall_climb_duration)
                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and not climb_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else: # Not actively climbing up, but conditions for climb not met (e.g. not holding key), default to slide/hang
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                  # If significantly falling, and on fire, ensure correct fire animation
                  if player.is_aflame and player.state not in ['burning','aflame']: player.set_state('burning')
                  elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                  elif not (player.is_aflame or player.is_deflaming) and player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual: # If not specifically falling/jumping/onfire, and not already idle
                  if player.state != 'idle': player.set_state('idle')


    setattr(player, '_prev_joystick_up_state', current_joystick_up_state_for_jump)

    return action_events

#################### END OF MODIFIED FILE: player_input_handler.py ####################