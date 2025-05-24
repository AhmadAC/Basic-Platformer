#################### START OF FILE: app_input_manager.py ####################

# app_input_manager.py
import os
import sys 
import json 
import time
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QPointF

import pygame 

_project_root_app_input = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if _project_root_app_input not in sys.path:
    sys.path.insert(0, _project_root_app_input)

import config as game_config
import constants as C
from player_input_handler import process_player_input_logic 
from logger import warning, debug, error 
from utils import PrintLimiter


_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

_app_input_limiter = PrintLimiter(default_limit=5, default_period=2.0)


def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = True
    _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    _qt_keys_pressed_snapshot_global[key] = False

def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any, 
    player_id: int,
    pygame_joysticks_list_from_app_core: List[Optional[pygame.joystick.Joystick]],
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], # MODIFIED: Renamed and type hint corrected
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:
    
    if not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
        if _app_input_limiter.can_log(f"invalid_player_instance_input_{player_id}"): 
            warning(f"APP_INPUT_MANAGER (P{player_id}): Player instance not validly initialized. Skipping input processing.")
        return {}

    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}
    player_id_str_log = f"P{player_id}"

    keyboard_actually_enabled = getattr(game_config, f"P{player_id}_KEYBOARD_ENABLED", False)
    controller_actually_enabled = getattr(game_config, f"P{player_id}_CONTROLLER_ENABLED", False)
    assigned_device_str = getattr(game_config, f"CURRENT_P{player_id}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
    player_specific_runtime_mappings = getattr(game_config, f"P{player_id}_MAPPINGS", {})

    if keyboard_actually_enabled and assigned_device_str.startswith("keyboard_"):
        keyboard_map_to_use_for_qt: Dict[str, Qt.Key]
        if assigned_device_str == "keyboard_p1": keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        elif assigned_device_str == "keyboard_p2": keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        else: keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        
        keyboard_action_events = process_player_input_logic(
            player_instance, _qt_keys_pressed_snapshot_global, list(_qt_key_events_this_frame_global),
            keyboard_map_to_use_for_qt, game_elements_ref.get("platforms_list", []), joystick_data=None
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
        
        if _app_input_limiter.can_log(f"kbd_snapshot_events_{player_id_str_log}"): 
            active_kbd_events = {k:v for k,v in keyboard_action_events.items() if v}
            if active_kbd_events: debug(f"APP_INPUT_MANAGER ({player_id_str_log}) KBD Events: {active_kbd_events}")

    elif controller_actually_enabled and assigned_device_str.startswith("joystick_pygame_"):
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            joystick_py_idx_str = assigned_device_str.split('_')[-1]
            if not joystick_py_idx_str.isdigit():
                 if _app_input_limiter.can_log(f"joy_idx_parse_fail_{player_id_str_log}"):
                    warning(f"APP_INPUT_MANAGER: {player_id_str_log} assigned joystick '{assigned_device_str}' has non-numeric index part. Skipping.")
                 return final_action_events
            joystick_py_idx = int(joystick_py_idx_str)

            if 0 <= joystick_py_idx < len(pygame_joysticks_list_from_app_core) and \
               pygame_joysticks_list_from_app_core[joystick_py_idx] is not None:
                joy = pygame_joysticks_list_from_app_core[joystick_py_idx]
                assert joy is not None
                if not joy.get_init():
                    try: joy.init(); debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Initialized Pygame joystick index {joystick_py_idx} ('{joy.get_name()}') for game input.")
                    except pygame.error as e_init:
                        if _app_input_limiter.can_log(f"joy_init_fail_ingame_{player_id_str_log}_{joystick_py_idx}"): 
                            warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Failed to init joystick {joystick_py_idx} for game input: {e_init}")
                        return final_action_events
                
                current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
                joy_instance_id = joy.get_instance_id()
                
                prev_buttons_state_for_this_joy: Dict[int, bool] = {} # Default to empty
                if 0 <= joy_instance_id < len(pygame_joy_button_prev_state_list):
                    button_state_dict_at_instance_id = pygame_joy_button_prev_state_list[joy_instance_id]
                    if button_state_dict_at_instance_id is not None: # Should be {}, not None
                        prev_buttons_state_for_this_joy = button_state_dict_at_instance_id
                else:
                     if _app_input_limiter.can_log(f"prev_state_missing_instanceid_{player_id_str_log}_{joy_instance_id}"):
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Instance ID {joy_instance_id} out of bounds for prev_state_list (len {len(pygame_joy_button_prev_state_list)}). Using empty prev_buttons.")
                
                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state, 
                    'buttons_prev': prev_buttons_state_for_this_joy.copy(), 
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                
                if 0 <= joy_instance_id < len(pygame_joy_button_prev_state_list):
                    pygame_joy_button_prev_state_list[joy_instance_id] = current_buttons_state.copy()
                else:
                    if _app_input_limiter.can_log(f"prev_state_update_fail_instanceid_{player_id_str_log}_{joy_instance_id}"):
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Failed to update prev_state_list. Instance ID {joy_instance_id} out of bounds (len {len(pygame_joy_button_prev_state_list)}).")


                active_runtime_joystick_map = player_specific_runtime_mappings
                if not active_runtime_joystick_map:
                    if _app_input_limiter.can_log(f"joy_map_fallback_{player_id_str_log}"): 
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Player-specific runtime map (P{player_id}_MAPPINGS) is empty. Falling back to DEFAULT_GENERIC_JOYSTICK_MAPPINGS.")
                    active_runtime_joystick_map = game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS
                
                # Optional: Deep log of map being used
                # if _app_input_limiter.can_log(f"joy_map_used_debug_{player_id_str_log}"): 
                #     debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Using joystick map for Player {player_id} (Device: {assigned_device_str}):")
                #     try: debug(json.dumps(active_runtime_joystick_map, indent=2))
                #     except TypeError: debug(str(active_runtime_joystick_map))
                
                controller_action_events = process_player_input_logic(
                    player_instance, {}, [], active_runtime_joystick_map,
                    game_elements_ref.get("platforms_list", []), joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
                
                if _app_input_limiter.can_log(f"ctrl_snapshot_events_{player_id_str_log}"): 
                    active_ctrl_events = {k:v for k,v in controller_action_events.items() if v}
                    if active_ctrl_events: debug(f"APP_INPUT_MANAGER ({player_id_str_log}) CTRL Events (JoyIdx {joystick_py_idx}, InstID {joy_instance_id}): {active_ctrl_events}")
            else:
                if _app_input_limiter.can_log(f"joy_idx_unavailable_{player_id_str_log}"): 
                    warning(f"APP_INPUT_MANAGER: {player_id_str_log} assigned joystick index {joystick_py_idx} but it's not available or None in app_core's list (list size: {len(pygame_joysticks_list_from_app_core)}).")
        except (ValueError, IndexError, AttributeError) as e:
            if _app_input_limiter.can_log(f"joy_process_err_{player_id_str_log}"): 
                error(f"APP_INPUT_MANAGER: Error processing joystick for {player_id_str_log} from '{assigned_device_str}': {e}", exc_info=True)
    
    if _app_input_limiter.can_log(f"final_actions_{player_id_str_log}"): 
        active_final_events = {k:v for k,v in final_action_events.items() if v}
        if active_final_events: debug(f"APP_INPUT_MANAGER ({player_id_str_log}) Final Combined Action Events: {active_final_events}")

    return final_action_events

#################### END OF FILE: app_input_manager.py ####################