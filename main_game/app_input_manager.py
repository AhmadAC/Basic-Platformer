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

import main_game.config as game_config
import main_game.constants as C
from player.player_input_handler import process_player_input_logic 
from main_game.logger import warning, debug, error 
from main_game.utils import PrintLimiter


_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

_app_input_limiter = PrintLimiter(default_limit=10, default_period_sec=1.0) # Shortened period for more frequent logs


def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    _qt_keys_pressed_snapshot_global[key] = True
    if not is_auto_repeat:
        _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    _qt_keys_pressed_snapshot_global[key] = False

def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any, 
    player_id: int,
    pygame_joysticks_list_from_app_core: List[Optional[pygame.joystick.Joystick]],
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], # This IS self._pygame_joy_button_prev_state from app_core
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

    if _app_input_limiter.can_log(f"input_snapshot_start_{player_id_str_log}"):
        debug(f"APP_INPUT_MGR ({player_id_str_log}): get_input_snapshot. Device: {assigned_device_str}, KbdEn: {keyboard_actually_enabled}, CtrlEn: {controller_actually_enabled}")

    if keyboard_actually_enabled and assigned_device_str.startswith("keyboard_"):
        # ... (keyboard logic remains the same)
        keyboard_map_to_use_for_qt: Dict[str, Qt.Key]
        if assigned_device_str == "keyboard_p1": keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        elif assigned_device_str == "keyboard_p2": keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        else: keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        
        keyboard_action_events = process_player_input_logic(
            player_instance, 
            dict(_qt_keys_pressed_snapshot_global), 
            list(_qt_key_events_this_frame_global), 
            keyboard_map_to_use_for_qt, 
            game_elements_ref.get("platforms_list", []), 
            joystick_data=None
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
        
        if _app_input_limiter.can_log(f"kbd_snapshot_events_final_{player_id_str_log}"): 
            active_kbd_events = {k:v for k,v in final_action_events.items() if v} # Log final_action_events after potential merge
            if active_kbd_events: debug(f"APP_INPUT_MGR ({player_id_str_log}) KBD Final Action Events: {active_kbd_events}")


    elif controller_actually_enabled and assigned_device_str.startswith("joystick_pygame_"):
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            joystick_py_idx_str = assigned_device_str.split('_')[-1]
            if not joystick_py_idx_str.isdigit():
                 if _app_input_limiter.can_log(f"joy_idx_parse_fail_{player_id_str_log}"):
                    warning(f"APP_INPUT_MGR: {player_id_str_log} assigned joystick '{assigned_device_str}' has non-numeric index part. Skipping.")
                 return final_action_events
            joystick_py_idx = int(joystick_py_idx_str)

            if 0 <= joystick_py_idx < len(pygame_joysticks_list_from_app_core) and \
               pygame_joysticks_list_from_app_core[joystick_py_idx] is not None:
                joy = pygame_joysticks_list_from_app_core[joystick_py_idx]
                assert joy is not None
                if not joy.get_init():
                    try: joy.init(); debug(f"APP_INPUT_MGR ({player_id_str_log}): Initialized Pygame joystick index {joystick_py_idx} ('{joy.get_name()}') for game input.")
                    except pygame.error as e_init:
                        if _app_input_limiter.can_log(f"joy_init_fail_ingame_{player_id_str_log}_{joystick_py_idx}"): 
                            warning(f"APP_INPUT_MGR ({player_id_str_log}): Failed to init joystick {joystick_py_idx} for game input: {e_init}")
                        return final_action_events
                
                current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
                joy_instance_id = joy.get_instance_id()
                
                # --- DEBUG: Log raw joystick states before processing ---
                if _app_input_limiter.can_log(f"joy_raw_states_{player_id_str_log}_{joy_instance_id}"):
                    debug(f"APP_INPUT_MGR ({player_id_str_log}) Joy InstID: {joy_instance_id}, PygameJoyIdx: {joystick_py_idx}")
                    debug(f"  Raw current_buttons_state: {current_buttons_state}")
                    if 0 <= joy_instance_id < len(pygame_joy_button_prev_state_list):
                        debug(f"  Raw prev_buttons_state from list (before copy): {pygame_joy_button_prev_state_list[joy_instance_id]}")
                    else:
                        debug(f"  Prev button state for InstID {joy_instance_id} is OUT OF BOUNDS for list (len: {len(pygame_joy_button_prev_state_list)}).")
                # --- END DEBUG ---
                
                prev_buttons_state_for_this_joy: Dict[int, bool] = {} 
                if 0 <= joy_instance_id < len(pygame_joy_button_prev_state_list):
                    button_state_dict_at_instance_id = pygame_joy_button_prev_state_list[joy_instance_id]
                    if button_state_dict_at_instance_id is not None: 
                        prev_buttons_state_for_this_joy = button_state_dict_at_instance_id.copy() # Use a copy for safety
                else:
                     if _app_input_limiter.can_log(f"prev_state_missing_instanceid_{player_id_str_log}_{joy_instance_id}"):
                        warning(f"APP_INPUT_MGR ({player_id_str_log}): Instance ID {joy_instance_id} out of bounds for prev_state_list (len {len(pygame_joy_button_prev_state_list)}). Using empty prev_buttons.")
                
                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state, 
                    'buttons_prev': prev_buttons_state_for_this_joy, # Pass the copied (or empty) previous state
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                
                active_runtime_joystick_map = player_specific_runtime_mappings
                if not active_runtime_joystick_map:
                    if _app_input_limiter.can_log(f"joy_map_fallback_{player_id_str_log}"): 
                        warning(f"APP_INPUT_MGR ({player_id_str_log}): Player-specific runtime map empty. Falling back to DEFAULT_GENERIC_JOYSTICK_MAPPINGS.")
                    active_runtime_joystick_map = game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS
                
                # --- DEBUG: Before calling process_player_input_logic for joystick ---
                if _app_input_limiter.can_log(f"joy_before_process_logic_{player_id_str_log}_{joy_instance_id}"):
                    debug(f"APP_INPUT_MGR ({player_id_str_log}) PRE-CALL process_player_input_logic (Joystick):")
                    debug(f"  Joystick Data for Handler: {joystick_data_for_handler}")
                    debug(f"  Active Runtime Map: {active_runtime_joystick_map.get('interact', 'No interact map')}") # Log interact mapping
                # --- END DEBUG ---

                controller_action_events = process_player_input_logic(
                    player_instance, {}, [], active_runtime_joystick_map,
                    game_elements_ref.get("platforms_list", []), joystick_data=joystick_data_for_handler
                )

                # --- DEBUG: After calling process_player_input_logic for joystick ---
                if _app_input_limiter.can_log(f"joy_post_process_logic_{player_id_str_log}_{joy_instance_id}"):
                    active_ctrl_events_debug = {k:v for k,v in controller_action_events.items() if v}
                    debug(f"APP_INPUT_MGR ({player_id_str_log}) POST-CALL process_player_input_logic. Actions Detected: {active_ctrl_events_debug}")
                # --- END DEBUG ---

                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
                
                # This is where the shared prev_state_list is updated with the current state for the *next* frame.
                if 0 <= joy_instance_id < len(pygame_joy_button_prev_state_list):
                    if _app_input_limiter.can_log(f"joy_prev_state_update_{player_id_str_log}_{joy_instance_id}"):
                        debug(f"APP_INPUT_MGR ({player_id_str_log}) Updating prev_button_state_list[{joy_instance_id}] for NEXT frame to: {current_buttons_state}")
                    pygame_joy_button_prev_state_list[joy_instance_id] = current_buttons_state.copy() # Update the list passed from app_core
                else:
                    if _app_input_limiter.can_log(f"prev_state_update_fail_instanceid_{player_id_str_log}_{joy_instance_id}"):
                        warning(f"APP_INPUT_MGR ({player_id_str_log}): Failed to update prev_state_list. Instance ID {joy_instance_id} out of bounds (len {len(pygame_joy_button_prev_state_list)}).")
            else:
                if _app_input_limiter.can_log(f"joy_idx_unavailable_{player_id_str_log}"): 
                    warning(f"APP_INPUT_MGR: {player_id_str_log} assigned joystick index {joystick_py_idx} but it's not available or None in app_core's list (size: {len(pygame_joysticks_list_from_app_core)}).")
        except (ValueError, IndexError, AttributeError) as e:
            if _app_input_limiter.can_log(f"joy_process_err_{player_id_str_log}"): 
                error(f"APP_INPUT_MGR: Error processing joystick for {player_id_str_log} from '{assigned_device_str}': {e}", exc_info=True)
    
    if _app_input_limiter.can_log(f"final_actions_return_{player_id_str_log}"): 
        active_final_events_to_return = {k:v for k,v in final_action_events.items() if v}
        if active_final_events_to_return: 
            debug(f"APP_INPUT_MGR ({player_id_str_log}) Final Combined Action Events TO RETURN: {active_final_events_to_return}")
        elif assigned_device_str.startswith("joystick_pygame_"): # Log even if empty for joystick to confirm
             debug(f"APP_INPUT_MGR ({player_id_str_log}) Final Combined Action Events TO RETURN: {{}} (Joystick Input)")


    return final_action_events