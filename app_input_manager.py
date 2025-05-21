# app_input_manager.py
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

import pygame # For Pygame joystick data

import config as game_config
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
from logger import warning, debug # Added debug
from utils import PrintLimiter

_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

_app_input_limiter = PrintLimiter(default_limit=5, default_period=2.0)


def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    if not is_auto_repeat: # Only track initial presses for events
        _qt_keys_pressed_snapshot_global[key] = True
    # Store all events for processing discrete presses, even repeats if needed by some logic later (though usually not)
    _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    _qt_keys_pressed_snapshot_global[key] = False # Held state is false
    # Release events are not typically stored for discrete processing unless specific logic needs it.
    # For now, just updating the held snapshot is enough.

def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any,
    player_id: int,
    pygame_joysticks_list: List[pygame.joystick.Joystick],
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], # This is per-joystick index
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:
    from player import Player # Local import
    if not isinstance(player_instance, Player) or not player_instance._valid_init:
        return {}

    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}
    player_id_str_log = f"P{player_id}"

    is_p1 = (player_id == 1)
    keyboard_actually_enabled = game_config.P1_KEYBOARD_ENABLED if is_p1 else game_config.P2_KEYBOARD_ENABLED
    controller_actually_enabled = game_config.P1_CONTROLLER_ENABLED if is_p1 else game_config.P2_CONTROLLER_ENABLED
    assigned_device_str = game_config.CURRENT_P1_INPUT_DEVICE if is_p1 else game_config.CURRENT_P2_INPUT_DEVICE
    
    # --- 1. Process Keyboard Input ---
    if keyboard_actually_enabled:
        # Determine which keyboard mapping set to use
        keyboard_map_to_use: Dict[str, Qt.Key]
        if assigned_device_str == "keyboard_p1":
            keyboard_map_to_use = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        elif assigned_device_str == "keyboard_p2":
            keyboard_map_to_use = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        else: # Player is assigned a controller, but keyboard is also enabled.
              # Decide which keyboard layout they get as secondary. Default to their player number.
            keyboard_map_to_use = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS if is_p1 else game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
            if _app_input_limiter.can_print(f"kbd_fallback_map_{player_id_str_log}"):
                debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Controller assigned ('{assigned_device_str}'), but keyboard enabled. Using default kbd map for P{player_id}.")

        keyboard_action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot_global,
            list(_qt_key_events_this_frame_global), # Pass current frame's discrete events
            keyboard_map_to_use,
            game_elements_ref.get("platforms_list", []),
            joystick_data=None
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
        if _app_input_limiter.can_print(f"kbd_snapshot_events_{player_id_str_log}") and any(keyboard_action_events.values()):
             debug(f"APP_INPUT_MANAGER ({player_id_str_log}) KBD Events: { {k:v for k,v in keyboard_action_events.items() if v} }")


    # --- 2. Process Controller Input ---
    if controller_actually_enabled and assigned_device_str.startswith("joystick_pygame_"):
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            joystick_idx = int(assigned_device_str.split('_')[-1])
            if 0 <= joystick_idx < len(pygame_joysticks_list):
                joy = pygame_joysticks_list[joystick_idx]
                if not joy.get_init(): joy.init() # Ensure joystick is initialized

                current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
                
                # Ensure prev_state_list is long enough
                while len(pygame_joy_button_prev_state_list) <= joystick_idx:
                    pygame_joy_button_prev_state_list.append({})
                
                prev_buttons_state_for_this_joy = pygame_joy_button_prev_state_list[joystick_idx]

                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state,
                    'buttons_prev': prev_buttons_state_for_this_joy.copy(), # Pass copy for this frame
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                # Update the global previous state for the next frame
                pygame_joy_button_prev_state_list[joystick_idx] = current_buttons_state.copy()
                
                controller_action_events = process_player_input_logic(
                    player_instance,
                    {}, # Empty keyboard snapshot for this path
                    [], # Empty keyboard events for this path
                    game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS if game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS else game_config.DEFAULT_PYGAME_JOYSTICK_MAPPINGS,
                    game_elements_ref.get("platforms_list", []),
                    joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
                if _app_input_limiter.can_print(f"ctrl_snapshot_events_{player_id_str_log}") and any(controller_action_events.values()):
                     debug(f"APP_INPUT_MANAGER ({player_id_str_log}) CTRL Events (Joy {joystick_idx}): { {k:v for k,v in controller_action_events.items() if v} }")

            else:
                if _app_input_limiter.can_print(f"joy_idx_unavailable_{player_id_str_log}"):
                    warning(f"APP_INPUT_MANAGER: {player_id_str_log} assigned joystick {joystick_idx} but it's not available (total detected: {len(pygame_joysticks_list)}).")
        except (ValueError, IndexError) as e:
            if _app_input_limiter.can_print(f"joy_idx_parse_err_{player_id_str_log}"):
                warning(f"APP_INPUT_MANAGER: Could not parse joystick index for {player_id_str_log} from '{assigned_device_str}': {e}")
    
    if _app_input_limiter.can_print(f"final_actions_{player_id_str_log}") and any(final_action_events.values()):
        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) Final Combined Action Events: { {k:v for k,v in final_action_events.items() if v} }")

    return final_action_events