#################### START OF MODIFIED FILE: player_input_handler.py ####################

# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.8 (Allow movement if on fire, even during hit stun)
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
    is_stunned_or_busy = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                         player.is_attacking or player.is_dashing or player.is_rolling or \
                         player.is_sliding or player.state == 'turn'


    action_state = {action: False for action in game_config.GAME_ACTIONS}
    action_events = {action: False for action in game_config.GAME_ACTIONS}

    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")
    joystick_instance = None
    # ... (joystick instance fetching logic - no changes here)
    if is_joystick_input_type and player.joystick_id_idx is not None:
        joystick_instance = joystick_handler.get_joystick_instance(player.joystick_id_idx)
        if not joystick_instance:
            if input_print_limiter.can_print(f"joy_missing_{player_id_str}"):
                print(f"INPUT_HANDLER ({player_id_str}): Joystick instance for ID {player.joystick_id_idx} not found.")
            is_joystick_input_type = False


    # --- Part 1: Process universal events (reset, pause) ---
    # ... (reset/pause event processing - no changes here) ...
    for event in pygame_events:
        if not is_joystick_input_type:
            if event.type == pygame.KEYDOWN:
                if (player.shadow_key and event.key == player.shadow_key) or \
                   (active_mappings.get("reset") == event.key):
                    action_events["reset"] = True
                elif active_mappings.get("pause") == event.key:
                    action_events["pause"] = True
        else:
            if joystick_instance:
                event_is_for_this_joystick = False
                if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                    if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                    elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True
                if event_is_for_this_joystick:
                    for action_name_check in ["reset", "pause"]:
                        mapping = active_mappings.get(action_name_check)
                        if isinstance(mapping, dict):
                            if event.type == pygame.JOYBUTTONDOWN and mapping.get("type") == "button" and mapping.get("id") == event.button: action_events[action_name_check] = True
                            elif event.type == pygame.JOYHATMOTION and mapping.get("type") == "hat" and mapping.get("id") == event.hat and mapping.get("value") == event.value: action_events[action_name_check] = True
                            elif event.type == pygame.JOYAXISMOTION and mapping.get("type") == "axis" and mapping.get("id") == event.axis:
                                axis_val = event.value; m_val_prop = mapping.get("value"); m_thresh = mapping.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                passed_thresh = (isinstance(m_val_prop, (int,float)) and ((m_val_prop < 0 and axis_val < -m_thresh) or (m_val_prop > 0 and axis_val > m_thresh)))
                                axis_event_active_attr = f"_axis_event_active_{action_name_check}"
                                if passed_thresh and not getattr(player, axis_event_active_attr, False): action_events[action_name_check] = True; setattr(player, axis_event_active_attr, True)
                                elif not passed_thresh: setattr(player, axis_event_active_attr, False)


    # --- Part 2: Populate action_state (continuous held inputs for movement/aiming) ---
    # This IS NOT BLOCKED by is_fully_action_blocked or is_on_fire.
    if not is_joystick_input_type:
        for action_name in ["left", "right", "up", "down"]:
            key_code = active_mappings.get(action_name)
            if key_code is not None and isinstance(key_code, int):
                action_state[action_name] = keys_pressed_from_pygame[key_code]
    else:
        if joystick_instance:
            for action_name in ["left", "right", "up", "down"]:
                mapping_details = active_mappings.get(action_name)
                if isinstance(mapping_details, dict):
                    m_type, m_id = mapping_details.get("type"), mapping_details.get("id")
                    m_value_prop = mapping_details.get("value"); m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                    if m_type == "axis" and m_id is not None and 0 <= m_id < joystick_instance.get_numaxes():
                        axis_val = joystick_instance.get_axis(m_id)
                        if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold: action_state[action_name] = True
                        elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold: action_state[action_name] = True
                    elif m_type == "hat" and m_id is not None and 0 <= m_id < joystick_instance.get_numhats():
                        if joystick_instance.get_hat(m_id) == m_value_prop: action_state[action_name] = True

    current_joystick_up_state_for_jump = action_state.get("up", False) if is_joystick_input_type else False

    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]
    # ... (aiming logic - no change) ...
    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching: aim_y = 1.0
    if aim_x != 0.0 or aim_y != 0.0: player.fireball_last_input_dir.x, player.fireball_last_input_dir.y = aim_x, aim_y
    elif player.fireball_last_input_dir.length_squared() == 0:
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0


    if is_fully_action_blocked:
        player.acc.x = 0
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- Part 3: Populate remaining action_events (pressed-once for game actions) ---
    # Only process these if not fully blocked.
    # Individual actions will be further gated by `is_on_fire` or `is_stunned_or_busy`.
    for event in pygame_events:
        # ... (skip reset/pause events already handled) ...
        if not is_joystick_input_type and event.type == pygame.KEYDOWN:
            if not ((player.shadow_key and event.key == player.shadow_key) or active_mappings.get("reset") == event.key or active_mappings.get("pause") == event.key):
                for action_name, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action_name] = True
                        if action_name == "up" and active_mappings.get("jump") == key_code: action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == key_code) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == key_code):
                             action_events["crouch"] = True
                        break
        elif is_joystick_input_type and joystick_instance:
            # ... (joystick event processing - no changes here, it populates action_events based on mappings) ...
            event_is_for_this_joystick = False
            if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True
            if event_is_for_this_joystick:
                is_universal_joy_event = False
                if event.type == pygame.JOYBUTTONDOWN:
                    if (isinstance(active_mappings.get("reset"), dict) and active_mappings["reset"].get("type") == "button" and active_mappings["reset"].get("id") == event.button) or \
                       (isinstance(active_mappings.get("pause"), dict) and active_mappings["pause"].get("type") == "button" and active_mappings["pause"].get("id") == event.button):
                        is_universal_joy_event = True
                if not is_universal_joy_event:
                    if event.type == pygame.JOYBUTTONDOWN:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="button" and map_details.get("id")==event.button:
                                action_events[action_name] = True
                                if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="hat" and map_details.get("id")==event.hat and map_details.get("value")==event.value:
                                if action_name in C.JOYSTICK_HAT_EVENT_ACTIONS:
                                    action_events[action_name] = True
                                    if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                                break
                    elif event.type == pygame.JOYAXISMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type") == "axis" and map_details.get("id") == event.axis:
                                if action_name in C.JOYSTICK_AXIS_EVENT_ACTIONS:
                                    axis_val = event.value; m_value_prop = map_details.get("value"); m_threshold = map_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                    passed_thresh = (isinstance(m_value_prop, (int,float)) and ((m_value_prop < 0 and axis_val < -m_threshold) or (m_value_prop > 0 and axis_val > m_threshold)))
                                    axis_event_active_attr = f"_axis_event_active_{action_name}"
                                    if passed_thresh and not getattr(player, axis_event_active_attr, False): action_events[action_name] = True; setattr(player, axis_event_active_attr, True)
                                    elif not passed_thresh: setattr(player, axis_event_active_attr, False)
                                break


    # --- Part 4: Translate events and states into player logic/actions ---
    player.acc.x = 0 # Reset horizontal acceleration
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right
    
    # MODIFIED: can_control_horizontal is now less restrictive if on fire
    can_control_horizontal = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang', 'frozen', 'defrost']
    )
    # If player is on fire but also taking a hit (briefly), movement might still be blocked by 'hit' state if not overridden above.
    # However, if *only* on fire, can_control_horizontal should now be true.
    if player.is_taking_hit and not is_on_fire_visual: # If hit and NOT on fire, no horizontal control
        can_control_horizontal = False

    if can_control_horizontal:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            # Turn animation is only triggered if not already in a fire animation that implies movement
            if player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and \
               player.state in ['idle','run'] and not is_on_fire_visual: # Don't 'turn' if burning
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            if not player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and \
               player.state in ['idle','run'] and not is_on_fire_visual: # Don't 'turn' if burning
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
        # ... (ladder movement logic) ...
        pass

    # CROUCH LOGIC - Allow crouching/uncrouching even if on fire
    if action_events.get("crouch"):
        if player.is_crouching: # Trying to uncrouch
            if player.can_stand_up(platforms_group):
                player.is_crouching = False
                if player.is_aflame: player.set_state('burning') # Transition to standing fire
                elif player.is_deflaming: player.set_state('deflame')
                else: player.set_state('run' if player_intends_horizontal_move else 'idle')
        else: # Trying to crouch
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost'])
            if can_crouch_now:
                player.is_crouching = True
                if player.is_aflame: player.set_state('aflame_crouch') # Transition to (intro) crouched fire
                elif player.is_deflaming: player.set_state('deflame_crouch')
                else: player.set_state('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')

    # Visual state update if crouching and moving (even if on fire)
    if player.is_crouching and player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch': player.set_state('crouch_walk')
    elif player.is_crouching and not player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch_walk': player.set_state('crouch')


    # MODIFIED: Gate other actions if on fire OR stunned/busy (unless it's crouch)
    can_perform_other_actions = not is_on_fire_visual and not is_stunned_or_busy

    joystick_up_just_pressed_for_jump = is_joystick_input_type and current_joystick_up_state_for_jump and not getattr(player, '_prev_joystick_up_state', False)
    if (action_events.get("jump") or joystick_up_just_pressed_for_jump) and can_perform_other_actions:
        # ... (jump logic - no change from previous correct version) ...
        can_jump_now = not player.is_attacking and not player.is_rolling and not player.is_sliding and \
                       not player.is_dashing and player.state not in ['turn','hit','death','death_nm', 'frozen', 'defrost']
        if can_jump_now:
            if player.is_crouching:
                if player.can_stand_up(platforms_group): player.is_crouching = False
                else: can_jump_now = False
            if can_jump_now:
                if player.on_ground:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH; player.set_state('jump'); player.on_ground = False
                elif player.on_ladder:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8
                    player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)
                    player.on_ladder = False; player.set_state('jump')
                elif player.can_wall_jump and player.touching_wall != 0:
                    player.vel.y = C.PLAYER_JUMP_STRENGTH
                    player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)
                    player.facing_right = not player.facing_right; player.set_state('jump')
                    player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0


    if action_events.get("attack1") and can_perform_other_actions:
        # ... (attack1 logic) ...
        player.attack_type = 4 if player.is_crouching else 1
        anim_key_attack1 = 'crouch_attack' if player.is_crouching else \
                           ('attack' if player_intends_horizontal_move else 'attack_nm')
        player.set_state(anim_key_attack1)

    if action_events.get("attack2") and can_perform_other_actions:
        # ... (attack2 logic) ...
        is_moving_for_attack2 = player_intends_horizontal_move
        if player.is_crouching and not player.is_attacking :
            player.attack_type = 4; anim_key_attack2 = 'crouch_attack'
        elif not player.is_attacking:
            player.attack_type = 2; anim_key_attack2 = 'attack2' if is_moving_for_attack2 else 'attack2_nm'
        else: anim_key_attack2 = None
        if anim_key_attack2: player.set_state(anim_key_attack2)


    if action_events.get("dash") and can_perform_other_actions:
        if player.on_ground: player.set_state('dash') # Simplified dash condition

    if action_events.get("roll") and can_perform_other_actions:
        if player.on_ground: player.set_state('roll') # Simplified roll condition

    if action_events.get("interact") and not is_on_fire_visual: # Interact is not a high-intensity action, might be allowed while hitstun (if desired)
        # ... (interact logic) ...
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.on_ladder = False; player.set_state('fall' if not player.on_ground else 'idle')


    # Projectile firing also blocked if on fire or stunned/busy
    if can_perform_other_actions:
        if action_events.get("projectile1"): player.fire_fireball()
        elif action_events.get("projectile2"): player.fire_poison()
        elif action_events.get("projectile3"): player.fire_bolt()
        elif action_events.get("projectile4"): player.fire_blood()
        elif action_events.get("projectile5"): player.fire_ice()
        elif action_events.get("projectile7"): player.fire_grey() # Assuming projectile7 is grey

    # Auto-state updates based on physics (if not in an overriding action/status state)
    # This needs to respect the fire states as well.
    is_in_non_interruptible_state = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost',
                                       'aflame', 'burning', 'aflame_crouch', 'burning_crouch', # Fire states are "interruptible" by movement intent
                                       'deflame', 'deflame_crouch' # but they dictate the visual
                                   ]
    
    if not is_in_non_interruptible_state or is_on_fire_visual: # Allow auto state update if on fire to switch to correct fire move/idle
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching:
                 if player_intends_horizontal_move:
                     if player.is_aflame and player.state != 'burning_crouch': player.set_state('burning_crouch')
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch_walk': player.set_state('crouch_walk')
                 else: # Crouching, not moving
                     if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch') # or aflame_crouch if intro
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch': player.set_state('crouch')
             elif player_intends_horizontal_move:
                 if player.is_aflame and player.state != 'burning': player.set_state('burning')
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'run': player.set_state('run')
             else: # Standing, not moving
                 if player.is_aflame and player.state not in ['aflame', 'burning']: player.set_state('burning') # or 'aflame' if intro
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'idle': player.set_state('idle')
        else: # In air
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual: # Wall interactions usually not while on fire
                 # ... (wall slide/climb auto-state logic from before) ...
                 wall_time = pygame.time.get_ticks()
                 climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and \
                                  wall_time - player.wall_climb_timer > player.wall_climb_duration)
                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and not climb_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                  if player.is_aflame and player.state != 'burning': player.set_state('burning')
                  elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                  elif not (player.is_aflame or player.is_deflaming) and player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual: # If not specifically falling/jumping/onfire
                  if player.state != 'idle': player.set_state('idle')


    setattr(player, '_prev_joystick_up_state', current_joystick_up_state_for_jump)

    return action_events

#################### END OF MODIFIED FILE: player_input_handler.py ####################