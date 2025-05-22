# app_input_manager.py
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent # QKeyEvent is for event type, Qt.Key for actual key
from PySide6.QtCore import Qt

import pygame # For Pygame joystick data

import config as game_config
# Assuming process_player_input_logic is designed to handle either
# keyboard mappings (Dict[str, Qt.Key]) OR joystick mappings (Dict[str, Dict[str, Any]])
# based on the type of the mapping_data it receives.
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
from logger import warning, debug, info # Assuming logger.py is correctly set up
from utils import PrintLimiter

_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

_app_input_limiter = PrintLimiter(default_limit=10, default_period=1.0)


def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = True
    _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    _qt_keys_pressed_snapshot_global.pop(key, None) # Use pop to remove, default to None if not present
    _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyRelease, key, is_auto_repeat))


def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any, # Should be type hint Player if possible
    player_id: int,
    pygame_joysticks_list: List[Optional[pygame.joystick.Joystick]], # Can contain None
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], # This is MainWindow's list, indexed by joy_idx
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:

    if not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
        return {}

    player_id_str_log = f"P{player_id}"
    if _app_input_limiter.can_print(f"input_snapshot_start_{player_id_str_log}"):
        held_keys_debug = {Qt.Key(k).name.replace('Key_', ''): v for k, v in _qt_keys_pressed_snapshot_global.items() if v}
        discrete_events_debug = [(Qt.Key(k).name.replace('Key_', ''), ev_type.name, ar) for ev_type, k, ar in _qt_key_events_this_frame_global]
        # debug(f"AIM ({player_id_str_log}) SNAPSHOT_START:"
        #       f" Held QtKeys: {held_keys_debug if held_keys_debug else 'None'} |"
        #       f" Discrete QtEvents: {discrete_events_debug if discrete_events_debug else 'None'}")

    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    # Get the already processed mappings and device status for this player from config.py
    current_player_mappings: Dict[str, Any] = {}
    is_player_controller_active = False
    is_player_keyboard_active = False
    assigned_controller_device_id_str: Optional[str] = None # Pygame device ID string, e.g., "joystick_pygame_0"

    if player_id == 1:
        current_player_mappings = game_config.P1_MAPPINGS
        is_player_controller_active = game_config.P1_CONTROLLER_ENABLED
        is_player_keyboard_active = game_config.P1_KEYBOARD_ENABLED
        assigned_controller_device_id_str = game_config.CURRENT_P1_CONTROLLER_DEVICE if is_player_controller_active else None
    elif player_id == 2:
        current_player_mappings = game_config.P2_MAPPINGS
        is_player_controller_active = game_config.P2_CONTROLLER_ENABLED
        is_player_keyboard_active = game_config.P2_KEYBOARD_ENABLED
        assigned_controller_device_id_str = game_config.CURRENT_P2_CONTROLLER_DEVICE if is_player_controller_active else None
    elif player_id == 3:
        current_player_mappings = game_config.P3_MAPPINGS
        is_player_controller_active = game_config.P3_CONTROLLER_ENABLED
        is_player_keyboard_active = game_config.P3_KEYBOARD_ENABLED
        assigned_controller_device_id_str = game_config.CURRENT_P3_CONTROLLER_DEVICE if is_player_controller_active else None
    elif player_id == 4:
        current_player_mappings = game_config.P4_MAPPINGS
        is_player_controller_active = game_config.P4_CONTROLLER_ENABLED
        is_player_keyboard_active = game_config.P4_KEYBOARD_ENABLED
        assigned_controller_device_id_str = game_config.CURRENT_P4_CONTROLLER_DEVICE if is_player_controller_active else None
    else:
        if _app_input_limiter.can_print(f"unhandled_player_id_{player_id_str_log}"):
            warning(f"AIM: Input snapshot for unconfigured player ID {player_id}. No input.")
        return final_action_events

    if not current_player_mappings:
        if _app_input_limiter.can_print(f"no_mappings_for_p{player_id_str_log}"):
            debug(f"AIM ({player_id_str_log}): No mappings found in game_config.P{player_id}_MAPPINGS. Player will have no input.")
        return final_action_events

    # Determine if the current_player_mappings are for keyboard or joystick
    # This check relies on config.py correctly populating P_X_MAPPINGS
    is_map_for_keyboard = False
    is_map_for_joystick = False
    first_mapping_value = next(iter(current_player_mappings.values()), None)
    if isinstance(first_mapping_value, Qt.Key):
        is_map_for_keyboard = True
    elif isinstance(first_mapping_value, dict) and "type" in first_mapping_value:
        is_map_for_joystick = True

    # --- Process Keyboard Input if active map is keyboard AND keyboard is enabled for this player ---
    if is_map_for_keyboard and is_player_keyboard_active:
        if _app_input_limiter.can_print(f"processing_kbd_p{player_id_str_log}"):
            debug(f"AIM ({player_id_str_log}): Processing as KEYBOARD.")
        current_frame_discrete_key_events = list(_qt_key_events_this_frame_global)
        keyboard_action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot_global,
            current_frame_discrete_key_events,
            current_player_mappings, # This is Dict[str, Qt.Key]
            game_elements_ref.get("platforms_list", []),
            joystick_data=None
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
    
    # --- Process Controller Input if active map is joystick AND controller is enabled for this player ---
    elif is_map_for_joystick and is_player_controller_active and assigned_controller_device_id_str:
        if _app_input_limiter.can_print(f"processing_joy_p{player_id_str_log}"):
            debug(f"AIM ({player_id_str_log}): Processing as JOYSTICK (Device ID: {assigned_controller_device_id_str}).")
        
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            if not assigned_controller_device_id_str.startswith("joystick_pygame_"):
                raise ValueError(f"Controller device ID '{assigned_controller_device_id_str}' is not a valid pygame joystick ID string.")

            joystick_idx = int(assigned_controller_device_id_str.split('_')[-1])

            if 0 <= joystick_idx < len(pygame_joysticks_list) and pygame_joysticks_list[joystick_idx] is not None:
                joy = pygame_joysticks_list[joystick_idx] # This is the actual Pygame Joystick object
                
                if not joy.get_init():
                    if _app_input_limiter.can_print(f"joy_reinit_p{player_id_str_log}_{joystick_idx}"):
                        debug(f"AIM ({player_id_str_log}): Re-initializing joystick {joystick_idx} ('{joy.get_name()}') for input reading.")
                    joy.init()
                
                if not joy.get_init():
                    if _app_input_limiter.can_print(f"joy_init_fail_p{player_id_str_log}_{joystick_idx}"):
                         warning(f"AIM ({player_id_str_log}): Failed to initialize joystick {joystick_idx} ('{joy.get_name()}'). Skipping controller input.")
                    return final_action_events

                # --- Read raw joystick state ---
                num_buttons = joy.get_numbuttons()
                current_buttons_state = {i: joy.get_button(i) for i in range(num_buttons)}
                
                # Ensure prev_state list is large enough for this joystick_idx
                while len(pygame_joy_button_prev_state_list) <= joystick_idx:
                    pygame_joy_button_prev_state_list.append({})
                prev_buttons_state_for_this_joy = pygame_joy_button_prev_state_list[joystick_idx]

                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state,
                    'buttons_prev': prev_buttons_state_for_this_joy.copy(),
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                # Update the persistent previous state list for the next frame
                pygame_joy_button_prev_state_list[joystick_idx] = current_buttons_state.copy()
                
                # DEBUG: Print raw joystick data
                if _app_input_limiter.can_print(f"raw_joy_data_p{player_id_str_log}"):
                    debug_axes = {k: round(v, 2) for k,v in joystick_data_for_handler['axes'].items() if abs(v) > 0.05}
                    debug_buttons = {k:v for k,v in joystick_data_for_handler['buttons_current'].items() if v}
                    debug_hats = {k:v for k,v in joystick_data_for_handler['hats'].items() if v != (0,0)}
                    if debug_axes or debug_buttons or debug_hats:
                        debug(f"AIM ({player_id_str_log}) RAW JOY DATA: Axes={debug_axes}, Btns={debug_buttons}, Hats={debug_hats}")


                controller_action_events = process_player_input_logic(
                    player_instance, {}, [], current_player_mappings,
                    game_elements_ref.get("platforms_list", []),
                    joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
            else:
                if _app_input_limiter.can_print(f"joy_idx_invalid_p{player_id_str_log}"):
                    warning(f"AIM ({player_id_str_log}): Assigned joystick index {joystick_idx} out of range or None (Total Pygame Joysticks: {len(pygame_joysticks_list)}).")
        except (ValueError, IndexError, pygame.error) as e:
            if _app_input_limiter.can_print(f"joy_processing_error_p{player_id_str_log}"):
                warning(f"AIM ({player_id_str_log}): Error processing joystick '{assigned_controller_device_id_str}': {e}")
    
    elif not is_player_keyboard_active and not is_player_controller_active:
        if _app_input_limiter.can_print(f"no_device_enabled_p{player_id_str_log}"):
            debug(f"AIM ({player_id_str_log}): Neither keyboard nor controller is enabled for this player.")

    active_final_actions = {k:v for k,v in final_action_events.items() if v}
    if _app_input_limiter.can_print(f"final_actions_p{player_id_str_log}") or active_final_actions:
        debug(f"AIM ({player_id_str_log}) FINAL_COMBINED_ACTIONS: {active_final_actions if active_final_actions else 'None'}")

    return final_action_events