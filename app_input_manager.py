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
from logger import warning, debug, info
from utils import PrintLimiter

_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

_app_input_limiter = PrintLimiter(default_limit=5, default_period=2.0)


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
    pygame_joy_button_prev_state_list: List[Dict[int, bool]],
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:
    # Late import if needed to avoid circular dependencies, or ensure Player is imported at top
    # from player import Player # Already at top, but good practice for clarity

    if not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
        # Ensure player_instance is a valid Player object and initialized
        # This check depends on Player class structure
        return {}

    player_id_str_log = f"P{player_id}"
    if _app_input_limiter.can_print(f"input_snapshot_start_{player_id_str_log}"):
        held_keys_debug = {Qt.Key(k).name.replace('Key_', ''): v for k, v in _qt_keys_pressed_snapshot_global.items() if v}
        discrete_events_debug = [(Qt.Key(k).name.replace('Key_', ''), ev_type.name, ar) for ev_type, k, ar in _qt_key_events_this_frame_global]
        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) SNAPSHOT_START:"
              f" Held QtKeys: {held_keys_debug if held_keys_debug else 'None'} |"
              f" Discrete QtEvents: {discrete_events_debug if discrete_events_debug else 'None'}")


    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    # Get the already processed mappings for this player from config.py
    # config.py's update_player_mappings_from_config has already prioritized controller > keyboard
    # and selected the appropriate map (controller-specific, keyboard-specific, or generic default).
    current_player_mappings: Dict[str, Any] = {}
    is_player_controller_assigned_and_enabled = False
    is_player_keyboard_assigned_and_enabled = False
    assigned_controller_device_id: Optional[str] = None

    if player_id == 1:
        current_player_mappings = game_config.P1_MAPPINGS
        is_player_controller_assigned_and_enabled = game_config.P1_CONTROLLER_ENABLED
        is_player_keyboard_assigned_and_enabled = game_config.P1_KEYBOARD_ENABLED
        assigned_controller_device_id = game_config.CURRENT_P1_CONTROLLER_DEVICE if is_player_controller_assigned_and_enabled else None
    elif player_id == 2:
        current_player_mappings = game_config.P2_MAPPINGS
        is_player_controller_assigned_and_enabled = game_config.P2_CONTROLLER_ENABLED
        is_player_keyboard_assigned_and_enabled = game_config.P2_KEYBOARD_ENABLED
        assigned_controller_device_id = game_config.CURRENT_P2_CONTROLLER_DEVICE if is_player_controller_assigned_and_enabled else None
    elif player_id == 3:
        current_player_mappings = game_config.P3_MAPPINGS
        is_player_controller_assigned_and_enabled = game_config.P3_CONTROLLER_ENABLED
        is_player_keyboard_assigned_and_enabled = game_config.P3_KEYBOARD_ENABLED
        assigned_controller_device_id = game_config.CURRENT_P3_CONTROLLER_DEVICE if is_player_controller_assigned_and_enabled else None
    elif player_id == 4:
        current_player_mappings = game_config.P4_MAPPINGS
        is_player_controller_assigned_and_enabled = game_config.P4_CONTROLLER_ENABLED
        is_player_keyboard_assigned_and_enabled = game_config.P4_KEYBOARD_ENABLED
        assigned_controller_device_id = game_config.CURRENT_P4_CONTROLLER_DEVICE if is_player_controller_assigned_and_enabled else None
    else:
        if _app_input_limiter.can_print(f"unhandled_player_id_{player_id_str_log}"):
            warning(f"APP_INPUT_MANAGER: Input snapshot for unconfigured player ID {player_id}. No input.")
        return final_action_events # Return empty actions

    if not current_player_mappings:
        if _app_input_limiter.can_print(f"no_mappings_for_p{player_id_str_log}"):
            debug(f"APP_INPUT_MANAGER ({player_id_str_log}): No mappings found in game_config.P{player_id}_MAPPINGS. Player will have no input.")
        return final_action_events


    # Determine if the current_player_mappings are for keyboard or joystick
    # A simple check: if values are Qt.Key, it's keyboard. If dict with "type", it's joystick.
    is_keyboard_map = False
    is_joystick_map = False
    if current_player_mappings:
        first_mapping_value = next(iter(current_player_mappings.values()), None)
        if isinstance(first_mapping_value, Qt.Key):
            is_keyboard_map = True
        elif isinstance(first_mapping_value, dict) and "type" in first_mapping_value:
            is_joystick_map = True

    # --- Process Keyboard Input if active map is keyboard ---
    if is_keyboard_map and is_player_keyboard_assigned_and_enabled: # Double check keyboard is actually enabled
        current_frame_discrete_key_events = list(_qt_key_events_this_frame_global)
        keyboard_action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot_global, # Held keys
            current_frame_discrete_key_events,  # Discrete (press/release) events for this frame
            current_player_mappings,            # This is Dict[str, Qt.Key]
            game_elements_ref.get("platforms_list", []),
            joystick_data=None                  # No joystick data for this call
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True

        active_kbd_actions = {k:v for k,v in keyboard_action_events.items() if v}
        if _app_input_limiter.can_print(f"kbd_actions_p{player_id_str_log}") or active_kbd_actions:
            debug(f"APP_INPUT_MANAGER ({player_id_str_log}) KBD_ACTIONS: {active_kbd_actions if active_kbd_actions else 'None'}")

    # --- Process Controller Input if active map is joystick ---
    elif is_joystick_map and is_player_controller_assigned_and_enabled and assigned_controller_device_id:
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            if not assigned_controller_device_id.startswith("joystick_pygame_"):
                raise ValueError("Controller device ID is not a pygame joystick ID")

            joystick_idx = int(assigned_controller_device_id.split('_')[-1])

            if 0 <= joystick_idx < len(pygame_joysticks_list) and pygame_joysticks_list[joystick_idx] is not None:
                joy = pygame_joysticks_list[joystick_idx]
                assert joy is not None # Help Mypy

                if not joy.get_init():
                    if _app_input_limiter.can_print(f"joy_reinit_p{player_id_str_log}_{joystick_idx}"):
                        debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Initializing joystick {joystick_idx} ('{joy.get_name()}') for input reading.")
                    joy.init() # Ensure it's initialized

                # Check if joystick is still valid after init (e.g. was disconnected)
                if not joy.get_init():
                    if _app_input_limiter.can_print(f"joy_init_fail_p{player_id_str_log}_{joystick_idx}"):
                         warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Failed to initialize joystick {joystick_idx} ('{joy.get_name()}'). Skipping controller input.")
                    return final_action_events # No controller input if joy couldn't be init'd

                num_buttons = joy.get_numbuttons()
                current_buttons_state = {i: joy.get_button(i) for i in range(num_buttons)}

                while len(pygame_joy_button_prev_state_list) <= joystick_idx:
                    pygame_joy_button_prev_state_list.append({})
                prev_buttons_state_for_this_joy = pygame_joy_button_prev_state_list[joystick_idx]

                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state,
                    'buttons_prev': prev_buttons_state_for_this_joy.copy(),
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                pygame_joy_button_prev_state_list[joystick_idx] = current_buttons_state.copy()

                # current_player_mappings should already be the correct runtime joystick map from config.py
                controller_action_events = process_player_input_logic(
                    player_instance,
                    {},                               # No Qt held keys for joystick processing
                    [],                               # No Qt discrete events for joystick processing
                    current_player_mappings,          # This is Dict[str, Dict[str, Any]]
                    game_elements_ref.get("platforms_list", []),
                    joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True

                active_ctrl_actions = {k:v for k,v in controller_action_events.items() if v}
                if _app_input_limiter.can_print(f"ctrl_actions_p{player_id_str_log}") or active_ctrl_actions:
                    debug(f"APP_INPUT_MANAGER ({player_id_str_log}) CTRL_ACTIONS (Joy {joystick_idx}) : {active_ctrl_actions if active_ctrl_actions else 'None'}")
            else:
                if _app_input_limiter.can_print(f"joy_idx_invalid_p{player_id_str_log}"):
                    warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Assigned joystick index {joystick_idx} out of range or None (Total: {len(pygame_joysticks_list)}).")
        except (ValueError, IndexError, pygame.error) as e:
            if _app_input_limiter.can_print(f"joy_processing_error_p{player_id_str_log}"):
                warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Error processing joystick '{assigned_controller_device_id}': {e}")
    
    elif not is_player_keyboard_assigned_and_enabled and not is_player_controller_assigned_and_enabled:
        if _app_input_limiter.can_print(f"no_device_enabled_p{player_id_str_log}"):
            debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Neither keyboard nor controller is assigned/enabled.")


    active_final_actions = {k:v for k,v in final_action_events.items() if v}
    if _app_input_limiter.can_print(f"final_actions_p{player_id_str_log}") or active_final_actions:
        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) FINAL_COMBINED_ACTIONS: {active_final_actions if active_final_actions else 'None'}")

    return final_action_events