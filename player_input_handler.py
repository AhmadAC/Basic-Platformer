# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 2.0.2 (Added Q for reset if mapped, and W to uncrouch logic)
Handles processing of player input (Qt events) and translating it to actions.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

import constants as C
import config as game_config
from utils import PrintLimiter

input_print_limiter = PrintLimiter(default_limit=20, default_period=5.0)

_input_handler_start_time = time.monotonic()
def get_input_handler_ticks():
    return int((time.monotonic() - _input_handler_start_time) * 1000)


def process_player_input_logic_pyside(
    player: Any,
    qt_keys_held_snapshot: Dict[Qt.Key, bool],
    qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
    active_mappings: Dict[str, Any],
    platforms_list: List[Any],
    joystick_data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:

    if not player._valid_init: return {}

    current_time_ms = get_input_handler_ticks()
    player_id_str = f"P{player.player_id}"

    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    is_stunned_or_busy_general = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                  player.is_attacking or player.is_dashing or player.is_rolling or \
                                  player.is_sliding or player.state == 'turn'

    action_state: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}
    action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")

    # --- Part 1: Process universal events (reset, pause) from DISCRETE key event data ---
    for event_type, key_code, _ in qt_key_event_data_this_frame:
        if event_type == QKeyEvent.Type.KeyPress:
            if not is_joystick_input_type:
                if active_mappings.get("reset") == key_code: action_events["reset"] = True
                if active_mappings.get("pause") == key_code: action_events["pause"] = True

    if is_joystick_input_type and joystick_data:
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {})
        for action_name_check in ["reset", "pause"]:
            mapping = active_mappings.get(action_name_check)
            if isinstance(mapping, dict):
                if mapping.get("type") == "button":
                    btn_id = mapping.get("id")
                    if current_buttons.get(btn_id, False) and not prev_buttons.get(btn_id, False):
                        action_events[action_name_check] = True
                elif mapping.get("type") == "hat":
                    hat_id = mapping.get("id")
                    hat_val_target = tuple(mapping.get("value", (0,0)))
                    current_hat_val = tuple(joystick_data.get('hats', {}).get(hat_id, (0,0)))
                    if current_hat_val == hat_val_target and hat_val_target != (0,0):
                         action_events[action_name_check] = True

    # --- Part 2: Populate action_state (continuous HELD inputs for movement/aiming) ---
    if not is_joystick_input_type: # Keyboard
        for action_name in ["left", "right", "up", "down"]:
            key_code = active_mappings.get(action_name)
            if isinstance(key_code, Qt.Key) and qt_keys_held_snapshot.get(key_code, False):
                action_state[action_name] = True
    elif joystick_data: # Joystick
        current_axes = joystick_data.get('axes', {})
        current_hats = joystick_data.get('hats', {})
        current_buttons_held = joystick_data.get('buttons_current', {})

        for action_name in ["left", "right", "up", "down"]:
            mapping_details = active_mappings.get(action_name)
            if isinstance(mapping_details, dict):
                m_type, m_id = mapping_details.get("type"), mapping_details.get("id")
                m_value_prop = mapping_details.get("value")
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)

                if m_type == "axis" and m_id is not None:
                    axis_val = current_axes.get(m_id, 0.0)
                    if isinstance(m_value_prop, (int,float)) and m_value_prop < 0 and axis_val < -m_threshold:
                        action_state[action_name] = True
                    elif isinstance(m_value_prop, (int,float)) and m_value_prop > 0 and axis_val > m_threshold:
                        action_state[action_name] = True
                elif m_type == "hat" and m_id is not None:
                    hat_val_target = tuple(m_value_prop)
                    if tuple(current_hats.get(m_id, (0,0))) == hat_val_target and hat_val_target != (0,0):
                        action_state[action_name] = True
                elif m_type == "button" and m_id is not None:
                    if current_buttons_held.get(m_id, False):
                        action_state[action_name] = True

    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]

    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching: aim_y = 1.0

    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.setX(aim_x); player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (player.fireball_last_input_dir.x() == 0 and player.fireball_last_input_dir.y() == 0):
        player.fireball_last_input_dir.setX(1.0 if player.facing_right else -1.0)
        player.fireball_last_input_dir.setY(0.0)

    if is_fully_action_blocked:
        if hasattr(player, 'acc'): player.acc.setX(0)
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- Part 3: Populate remaining action_events from DISCRETE key event data ---
    for event_type, key_code, _ in qt_key_event_data_this_frame:
        if event_type == QKeyEvent.Type.KeyPress:
            if not (active_mappings.get("reset") == key_code or active_mappings.get("pause") == key_code):
                for action_name, mapped_val in active_mappings.items():
                    if isinstance(mapped_val, Qt.Key) and key_code == mapped_val:
                        action_events[action_name] = True
                        if action_name == "up" and active_mappings.get("jump") == key_code: action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == key_code) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == key_code):
                             action_events["crouch"] = True
                        break

    if is_joystick_input_type and joystick_data:
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {})
        current_hats = joystick_data.get('hats',{})
        current_axes = joystick_data.get('axes',{})

        for action_name, map_details in active_mappings.items():
            if action_name in ["reset", "pause"]: continue
            if isinstance(map_details, dict):
                m_type, m_id = map_details.get("type"), map_details.get("id")
                if m_type == "button":
                    if current_buttons.get(m_id, False) and not prev_buttons.get(m_id, False):
                        action_events[action_name] = True
                        if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                elif m_type == "hat":
                    hat_val_target = tuple(map_details.get("value", (0,0)))
                    if tuple(current_hats.get(m_id, (0,0))) == hat_val_target and hat_val_target != (0,0):
                        if action_name in C.JOYSTICK_HAT_EVENT_ACTIONS:
                            action_events[action_name] = True
                            if action_name == "down" or action_name == "crouch": action_events["crouch"] = True
                elif m_type == "axis":
                    axis_val = current_axes.get(m_id, 0.0)
                    m_value_prop = map_details.get("value")
                    m_threshold = map_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                    passed_thresh_now = (isinstance(m_value_prop, (int,float)) and
                                          ((m_value_prop < 0 and axis_val < -m_threshold) or
                                           (m_value_prop > 0 and axis_val > m_threshold)))
                    if passed_thresh_now and action_name in C.JOYSTICK_AXIS_EVENT_ACTIONS:
                        action_events[action_name] = True

    # --- Part 4: Translate events and states into player logic/actions ---
    if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0)
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right

    can_control_horizontal = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang', 'frozen', 'defrost']
    )
    if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit':
        can_control_horizontal = False

    if can_control_horizontal:
        accel_val = C.PLAYER_ACCEL
        if player.is_aflame: accel_val *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
        elif player.is_deflaming: accel_val *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)

        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.setX(-accel_val)
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.setX(accel_val)
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
        player.acc.setX(0)
        if player.is_holding_climb_ability_key: player.vel.setY(-C.PLAYER_LADDER_CLIMB_SPEED)
        elif player.is_holding_crouch_ability_key: player.vel.setY(C.PLAYER_LADDER_CLIMB_SPEED)
        else: player.vel.setY(0)

    # CROUCH LOGIC
    if action_events.get("crouch"): # This is the "S" key by default
        if player.is_crouching:
            if player.can_stand_up(platforms_list):
                player.is_crouching = False
                next_f_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else ('run' if player_intends_horizontal_move else 'idle')
                player.set_state(next_f_state)
        else: # Not crouching, try to crouch
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                player.is_crouching = True
                next_f_state = ('aflame_crouch' if player.is_aflame else 'deflame_crouch') if (player.is_aflame or player.is_deflaming) else ('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')
                player.set_state(next_f_state)
    
    # Uncrouch with "W" (up key) if player is crouching and "up" event occurred
    # This is separate from the "crouch" toggle event.
    if action_events.get("up") and not is_joystick_input_type: # Keyboard specific 'W' for uncrouch
        if player.is_crouching and player.can_stand_up(platforms_list):
            player.is_crouching = False
            player_intends_horizontal_move_after_uncrouch = action_state["left"] or action_state["right"]
            next_f_state_after_uncrouch = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else ('run' if player_intends_horizontal_move_after_uncrouch else 'idle')
            player.set_state(next_f_state_after_uncrouch)
            action_events["up"] = False # Consume the "up" event if it was used for uncrouching
            action_events["jump"] = False # And also don't let it trigger a jump

    # Visual state for crouching movement
    if player.is_crouching and player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch': player.set_state('crouch_walk')
    elif player.is_crouching and not player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch_walk': player.set_state('crouch')

    # JUMP LOGIC
    joystick_jump_pressed = False
    if is_joystick_input_type and joystick_data:
        current_buttons = joystick_data.get('buttons_current',{})
        prev_buttons = joystick_data.get('buttons_prev',{})
        jump_mapping = active_mappings.get("jump")
        if isinstance(jump_mapping, dict) and jump_mapping.get("type") == "button":
            btn_id = jump_mapping.get("id")
            if current_buttons.get(btn_id,False) and not prev_buttons.get(btn_id,False):
                joystick_jump_pressed = True

    can_initiate_jump_action = not (player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding) and \
                               player.state not in ['turn', 'death', 'death_nm', 'frozen', 'defrost']
    if not is_on_fire_visual:
        if player.state == 'hit': can_initiate_jump_action = False
        if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration): can_initiate_jump_action = False

    if (action_events.get("jump") or joystick_jump_pressed) and can_initiate_jump_action: # "jump" event often comes from "up"
        can_actually_execute_jump = not player.is_crouching # If already crouching, "up" might uncrouch first
        if player.is_crouching: # If "up" was used to uncrouch, don't jump immediately unless jump is a separate button
             # This condition is a bit tricky. If "up" and "jump" are the same key,
             # and "up" just uncrouched the player, we might not want to immediately jump.
             # However, if jump is a dedicated button, then this is fine.
             # The current logic for keyboard maps "W" to both "up" and "jump".
             # The added "uncrouch with W" logic above sets action_events["jump"] = False
             # if "up" was used to uncrouch.
             pass
        
        if can_actually_execute_jump:
            if player.on_ground: player.vel.setY(C.PLAYER_JUMP_STRENGTH); player.set_state('jump'); player.on_ground = False
            elif player.on_ladder:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8); player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1))
                player.on_ladder = False; player.set_state('jump')
            elif player.can_wall_jump and player.touching_wall != 0:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH); player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall))
                player.facing_right = not player.facing_right; player.set_state('jump')
                player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0

    can_perform_other_abilities = not is_on_fire_visual and not is_stunned_or_busy_general
    if action_events.get("attack1") and can_perform_other_abilities:
        player.attack_type = 4 if player.is_crouching else 1
        player.set_state('crouch_attack' if player.is_crouching else ('attack' if player_intends_horizontal_move else 'attack_nm'))
    if action_events.get("attack2") and can_perform_other_abilities:
        if player.is_crouching and not player.is_attacking: player.attack_type = 4; player.set_state('crouch_attack')
        elif not player.is_attacking: player.attack_type = 2; player.set_state('attack2' if player_intends_horizontal_move else 'attack2_nm')
    if action_events.get("dash") and can_perform_other_abilities and player.on_ground: player.set_state('dash')
    if action_events.get("roll") and can_perform_other_abilities and player.on_ground: player.set_state('roll')
    if action_events.get("interact") and not is_on_fire_visual:
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching=False; player.on_ladder=True; player.vel.setY(0); player.vel.setX(0); player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder: player.on_ladder=False; player.set_state('fall' if not player.on_ground else 'idle')

    if can_perform_other_abilities:
        if action_events.get("projectile1"): player.fire_fireball()
        if action_events.get("projectile2"): player.fire_poison()
        if action_events.get("projectile3"): player.fire_bolt()
        if action_events.get("projectile4"): player.fire_blood()
        if action_events.get("projectile5"): player.fire_ice()
        if action_events.get("projectile6"): player.fire_shadow()
        if action_events.get("projectile7"): player.fire_grey()

    is_in_non_interruptible_state = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost'
                                   ]
    if not is_in_non_interruptible_state or is_on_fire_visual:
        if player.on_ladder:
            if abs(player.vel.y()) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y()) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
            if player.is_crouching:
                crouch_state_suffix = '_crouch' if (player.is_aflame or player.is_deflaming) else ''
                fire_prefix = 'burning' if player.is_aflame else ('deflame' if player.is_deflaming else '')
                target_crouch_state = (fire_prefix + ('_crouch' if fire_prefix else 'crouch_walk')) if player_intends_horizontal_move else (fire_prefix + ('_crouch' if fire_prefix else 'crouch'))
                if player.state != target_crouch_state and player.animations.get(target_crouch_state): player.set_state(target_crouch_state)

            elif player_intends_horizontal_move:
                target_run_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'run'
                if player.state != target_run_state and player.animations.get(target_run_state): player.set_state(target_run_state)
            else:
                target_idle_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'idle'
                if player.state != target_idle_state and player.animations.get(target_idle_state): player.set_state(target_idle_state)
        else: # In air
            if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                wall_time = get_input_handler_ticks()
                climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and wall_time - player.wall_climb_timer > player.wall_climb_duration)
                if player.vel.y() > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                elif player.is_holding_climb_ability_key and abs(player.vel.x()) < 1.0 and not climb_expired and player.animations.get('wall_climb'):
                    if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                else:
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
            elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                target_fall_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'fall'
                if player.state != target_fall_state and player.animations.get(target_fall_state): player.set_state(target_fall_state)
            elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual and player.state != 'idle':
                player.set_state('idle')

    return action_events