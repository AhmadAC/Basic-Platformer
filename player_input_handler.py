# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.6 (Block game actions if player is frozen/aflame/deflaming)
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

    # Game actions are blocked if player is dead, in hit stun, petrified, frozen, or actively deflaming/aflame (unless it's a specific interruptible anim)
    is_input_blocked_for_game_actions = player.is_dead or \
                                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                       getattr(player, 'is_petrified', False) or \
                                       getattr(player, 'is_frozen', False) or \
                                       (getattr(player, 'is_aflame', False) and player.state == 'aflame') or \
                                       (getattr(player, 'is_deflaming', False) and player.state == 'deflame') or \
                                       (getattr(player, 'is_defrosting', False) and player.state == 'defrost')


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

    # --- Part 1: Process universal events (reset, pause) regardless of player game action state ---
    for event in pygame_events:
        if not is_joystick_input_type: 
            if event.type == pygame.KEYDOWN:
                if (player.shadow_key and event.key == player.shadow_key) or \
                   (active_mappings.get("reset") == event.key):
                    action_events["reset"] = True
                    if input_print_limiter.can_print(f"kb_event_{player_id_str}_reset"):
                        print(f"INPUT_HANDLER ({player_id_str}): KB KeyDown '{pygame.key.name(event.key)}' -> Event 'reset'")
                elif active_mappings.get("pause") == event.key:
                    action_events["pause"] = True
                    if input_print_limiter.can_print(f"kb_event_{player_id_str}_pause"):
                        print(f"INPUT_HANDLER ({player_id_str}): KB KeyDown '{pygame.key.name(event.key)}' -> Event 'pause'")
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
                            if event.type == pygame.JOYBUTTONDOWN and mapping.get("type") == "button" and mapping.get("id") == event.button:
                                action_events[action_name_check] = True
                            elif event.type == pygame.JOYHATMOTION and mapping.get("type") == "hat" and mapping.get("id") == event.hat and mapping.get("value") == event.value:
                                action_events[action_name_check] = True
                            elif event.type == pygame.JOYAXISMOTION and mapping.get("type") == "axis" and mapping.get("id") == event.axis:
                                axis_val = event.value
                                m_val_prop = mapping.get("value")
                                m_thresh = mapping.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                passed_thresh = (isinstance(m_val_prop, (int,float)) and ((m_val_prop < 0 and axis_val < -m_thresh) or (m_val_prop > 0 and axis_val > m_thresh)))
                                axis_event_active_attr = f"_axis_event_active_{action_name_check}"
                                if passed_thresh and not getattr(player, axis_event_active_attr, False):
                                    action_events[action_name_check] = True
                                    setattr(player, axis_event_active_attr, True)
                                elif not passed_thresh:
                                    setattr(player, axis_event_active_attr, False)
                    if action_events["reset"] and input_print_limiter.can_print(f"joy_event_{player_id_str}_reset"):
                        print(f"INPUT_HANDLER ({player_id_str}): Joystick event -> 'reset'")
                    if action_events["pause"] and input_print_limiter.can_print(f"joy_event_{player_id_str}_pause"):
                        print(f"INPUT_HANDLER ({player_id_str}): Joystick event -> 'pause'")
    
    if is_input_blocked_for_game_actions:
        player.acc.x = 0
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- Part 2: Populate action_state (continuous held inputs) ---
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
                    m_value_prop = mapping_details.get("value")
                    m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                    if m_type == "axis" and m_id is not None and 0 <= m_id < joystick_instance.get_numaxes():
                        axis_val = joystick_instance.get_axis(m_id)
                        if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold: action_state[action_name] = True
                        elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold: action_state[action_name] = True
                    elif m_type == "hat" and m_id is not None and 0 <= m_id < joystick_instance.get_numhats():
                        if joystick_instance.get_hat(m_id) == m_value_prop: action_state[action_name] = True
    
    current_joystick_up_state_for_jump = action_state.get("up", False) if is_joystick_input_type else False

    # --- Part 3: Populate remaining action_events (pressed-once) ---
    for event in pygame_events:
        is_reset_or_pause_event_key = False
        if not is_joystick_input_type and event.type == pygame.KEYDOWN:
            if (player.shadow_key and event.key == player.shadow_key) or \
               active_mappings.get("reset") == event.key or \
               active_mappings.get("pause") == event.key:
                is_reset_or_pause_event_key = True
        elif is_joystick_input_type and joystick_instance:
            if event.type == pygame.JOYBUTTONDOWN:
                if (isinstance(active_mappings.get("reset"), dict) and active_mappings["reset"].get("type") == "button" and active_mappings["reset"].get("id") == event.button) or \
                   (isinstance(active_mappings.get("pause"), dict) and active_mappings["pause"].get("type") == "button" and active_mappings["pause"].get("id") == event.button):
                    is_reset_or_pause_event_key = True
        if is_reset_or_pause_event_key: continue

        if not is_joystick_input_type:
            if event.type == pygame.KEYDOWN:
                for action_name, key_code in active_mappings.items():
                    if isinstance(key_code, int) and event.key == key_code:
                        action_events[action_name] = True
                        if action_name == "up" and active_mappings.get("jump") == key_code: action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == key_code) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == key_code):
                             action_events["crouch"] = True
                        if input_print_limiter.can_print(f"kb_event_{player_id_str}_{action_name}_gameaction"):
                             print(f"INPUT_HANDLER ({player_id_str}): KB KeyDown '{pygame.key.name(event.key)}' -> Event '{action_name}' (Game Action)")
                        break
        else: 
            if joystick_instance:
                event_is_for_this_joystick = False
                if event.type in [pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION]:
                    if hasattr(event, 'instance_id') and event.instance_id == joystick_instance.get_id(): event_is_for_this_joystick = True
                    elif hasattr(event, 'joy') and event.joy == player.joystick_id_idx: event_is_for_this_joystick = True

                if event_is_for_this_joystick:
                    if event.type == pygame.JOYBUTTONDOWN:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="button" and map_details.get("id")==event.button:
                                action_events[action_name] = True
                                if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                                if input_print_limiter.can_print(f"joy_btn_{player_id_str}_{action_name}_{event.button}_gameaction"):
                                    print(f"INPUT_HANDLER ({player_id_str}): JoyButton {event.button} -> Event '{action_name}' (Game Action)")
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type")=="hat" and map_details.get("id")==event.hat and map_details.get("value")==event.value:
                                if action_name in C.JOYSTICK_HAT_EVENT_ACTIONS:
                                    action_events[action_name] = True
                                    if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                                    if input_print_limiter.can_print(f"joy_hat_{player_id_str}_{action_name}_gameaction"):
                                        print(f"INPUT_HANDLER ({player_id_str}): JoyHat {event.hat} Val {event.value} -> Event '{action_name}' (Game Action)")
                                break
                    elif event.type == pygame.JOYAXISMOTION:
                        for action_name, map_details in active_mappings.items():
                            if isinstance(map_details, dict) and map_details.get("type") == "axis" and map_details.get("id") == event.axis:
                                if action_name in C.JOYSTICK_AXIS_EVENT_ACTIONS:
                                    axis_val = event.value
                                    m_value_prop = map_details.get("value")
                                    m_threshold = map_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                                    passed_thresh = False
                                    if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold: passed_thresh = True
                                    elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold: passed_thresh = True
                                    
                                    axis_event_active_attr = f"_axis_event_active_{action_name}"
                                    if passed_thresh and not getattr(player, axis_event_active_attr, False):
                                        action_events[action_name] = True
                                        if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                                        setattr(player, axis_event_active_attr, True)
                                        if input_print_limiter.can_print(f"joy_axis_event_{player_id_str}_{action_name}_gameaction"):
                                            print(f"INPUT_HANDLER ({player_id_str}): JoyAxis {event.axis} Val {axis_val:.2f} -> Event '{action_name}' (Game Action, Thresh: {m_threshold})")
                                    elif not passed_thresh:
                                         setattr(player, axis_event_active_attr, False)
                                break

    # --- Part 4: Update player intention states ---
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]

    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching:
        aim_y = 1.0
    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.x, player.fireball_last_input_dir.y = aim_x, aim_y
    elif player.fireball_last_input_dir.length_squared() == 0:
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    # --- Part 5: Translate events and states into player logic/actions ---
    player.acc.x = 0
    player_intends_horizontal_move = False
    can_control_horizontal = not (player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
                                 (player.is_attacking and player.state.endswith('_nm')) or
                                 player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang',
                                                  'aflame', 'deflame', 'frozen', 'defrost']) # Add status effects
    if can_control_horizontal:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL; player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and player.state in ['idle','run']: player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL; player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and not player.is_attacking and player.state in ['idle','run']: player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
         player.vel.y = 0
         if player.is_holding_climb_ability_key: player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif action_state["down"]: player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    joystick_up_just_pressed_for_jump = is_joystick_input_type and current_joystick_up_state_for_jump and not getattr(player, '_prev_joystick_up_state', False)
    if action_events.get("jump") or joystick_up_just_pressed_for_jump:
        can_jump_now = not player.is_attacking and not player.is_rolling and not player.is_sliding and \
                       not player.is_dashing and player.state not in ['turn','hit','death','death_nm', 
                                                                     'aflame', 'deflame', 'frozen', 'defrost']
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

    if action_events.get("crouch"):
        if player.is_crouching:
            if player.can_stand_up(platforms_group):
                player.is_crouching = False
                player.set_state('run' if player_intends_horizontal_move else 'idle')
        else:
            can_slide_now = player.on_ground and player.state == 'run' and \
                                 abs(player.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                 not player.is_sliding and not player.is_attacking and \
                                 not player.is_rolling and not player.is_dashing and \
                                 not player.on_ladder and player.state not in ['turn','hit', 
                                                                               'aflame', 'deflame', 'frozen', 'defrost']
            if can_slide_now:
                player.set_state('slide_trans_start' if player.animations.get('slide_trans_start') else 'slide')
            else:
                can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                                   not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                        player.state in ['turn','hit','death','death_nm', 
                                                         'aflame', 'deflame', 'frozen', 'defrost'])
                if can_crouch_now:
                    player.is_crouching = True
                    player.set_state('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')
    
    if player.is_crouching and player_intends_horizontal_move and player.state == 'crouch': player.set_state('crouch_walk')
    elif player.is_crouching and not player_intends_horizontal_move and player.state == 'crouch_walk': player.set_state('crouch')

    if action_events.get("attack1"):
        can_attack_melee = not player.is_attacking and not player.is_dashing and not player.is_rolling and \
                           not player.is_sliding and not player.on_ladder and \
                           player.state not in ['turn','hit', 'aflame', 'deflame', 'frozen', 'defrost']
        if can_attack_melee:
            player.attack_type = 4 if player.is_crouching else 1
            anim_key_attack1 = 'crouch_attack' if player.is_crouching else \
                               ('attack' if player_intends_horizontal_move else 'attack_nm')
            player.set_state(anim_key_attack1)

    if action_events.get("attack2"):
        can_attack_melee2 = not player.is_dashing and not player.is_rolling and not player.is_sliding and \
                            not player.on_ladder and player.state not in ['turn','hit', 
                                                                         'aflame', 'deflame', 'frozen', 'defrost']
        if can_attack_melee2:
            is_moving_for_attack2 = player_intends_horizontal_move
            if player.is_crouching and not player.is_attacking :
                player.attack_type = 4; anim_key_attack2 = 'crouch_attack'
            elif not player.is_attacking:
                player.attack_type = 2; anim_key_attack2 = 'attack2' if is_moving_for_attack2 else 'attack2_nm'
            else: anim_key_attack2 = None
            if anim_key_attack2: player.set_state(anim_key_attack2)

    if action_events.get("dash"):
        if player.on_ground and not player.is_dashing and not player.is_rolling and not player.is_attacking and \
           not player.is_crouching and not player.on_ladder and \
           player.state not in ['turn','hit', 'aflame', 'deflame', 'frozen', 'defrost']:
            player.set_state('dash')

    if action_events.get("roll"):
        if player.on_ground and not player.is_rolling and not player.is_dashing and not player.is_attacking and \
           not player.is_crouching and not player.on_ladder and \
           player.state not in ['turn','hit', 'aflame', 'deflame', 'frozen', 'defrost']:
            player.set_state('roll')

    if action_events.get("interact"):
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.on_ladder = False; player.set_state('fall' if not player.on_ground else 'idle')

    can_fire_projectiles = not player.is_crouching and not player.is_attacking and not player.is_dashing and \
                           not player.is_rolling and not player.is_sliding and not player.on_ladder and \
                           player.state not in ['turn','hit','death','death_nm','wall_climb','wall_hang','wall_slide',
                                                'aflame', 'deflame', 'frozen', 'defrost']
    if can_fire_projectiles:
        if action_events.get("projectile1"): player.fire_fireball()
        elif action_events.get("projectile2"): player.fire_poison()
        elif action_events.get("projectile3"): player.fire_bolt()
        elif action_events.get("projectile4"): player.fire_blood()
        elif action_events.get("projectile5"): player.fire_ice()
        elif action_events.get("projectile7"): player.fire_grey()

    is_in_override_state_for_movement = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                        player.is_taking_hit or player.state in [
                                            'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                            'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                            'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                            'aflame', 'deflame', 'frozen', 'defrost'] 
    if not is_in_override_state_for_movement:
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching:
                 if player_intends_horizontal_move and player.animations.get('crouch_walk'):
                     if player.state != 'crouch_walk': player.set_state('crouch_walk')
                 else:
                     if player.state != 'crouch': player.set_state('crouch')
             elif player_intends_horizontal_move:
                 if player.state != 'run': player.set_state('run')
             else:
                 if player.state != 'idle': player.set_state('idle')
        else:
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling:
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
                  if player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall']:
                  if player.state != 'idle': player.set_state('idle')

    setattr(player, '_prev_joystick_up_state', current_joystick_up_state_for_jump)
    
    return action_events