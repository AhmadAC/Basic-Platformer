# app_input_manager.py
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

import pygame # For Pygame joystick data

import config as game_config
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
    _qt_keys_pressed_snapshot_global[key] = False 
    _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyRelease, key, is_auto_repeat))


def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any,
    player_id: int,
    pygame_joysticks_list: List[pygame.joystick.Joystick],
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], 
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:
    from player import Player 
    if not isinstance(player_instance, Player) or not player_instance._valid_init:
        return {}

    player_id_str_log = f"P{player_id}"

    if _app_input_limiter.can_print(f"qt_key_state_P{player_id_str_log}"):
        held_keys_debug = {Qt.Key(k).name.replace('Key_', ''): v for k, v in _qt_keys_pressed_snapshot_global.items() if v}
        discrete_events_debug = [(Qt.Key(k).name.replace('Key_', ''), ev_type.name, ar) for ev_type, k, ar in _qt_key_events_this_frame_global]
        
        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) GET_SNAPSHOT_START:"
              f" Held QtKeys: {held_keys_debug if held_keys_debug else 'None'} |"
              f" Discrete QtEventsThisFrame: {discrete_events_debug if discrete_events_debug else 'None'}")

    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    if player_id == 1:
        keyboard_actually_enabled = game_config.P1_KEYBOARD_ENABLED
        controller_actually_enabled = game_config.P1_CONTROLLER_ENABLED
        assigned_device_str = game_config.CURRENT_P1_INPUT_DEVICE
        default_keyboard_map_for_player = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        player_specific_controller_map_source = game_config.P1_MAPPINGS
    elif player_id == 2:
        keyboard_actually_enabled = game_config.P2_KEYBOARD_ENABLED
        controller_actually_enabled = game_config.P2_CONTROLLER_ENABLED
        assigned_device_str = game_config.CURRENT_P2_INPUT_DEVICE
        default_keyboard_map_for_player = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        player_specific_controller_map_source = game_config.P2_MAPPINGS
    # Extend with P3, P4 specific config lookups if they have their own CURRENT_PX_INPUT_DEVICE etc.
    elif player_id == 3:
        keyboard_actually_enabled = getattr(game_config, "P3_KEYBOARD_ENABLED", False)
        controller_actually_enabled = getattr(game_config, "P3_CONTROLLER_ENABLED", False)
        assigned_device_str = getattr(game_config, "CURRENT_P3_INPUT_DEVICE", "unassigned")
        default_keyboard_map_for_player = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS # Or a P3 default
        player_specific_controller_map_source = getattr(game_config, "P3_MAPPINGS", {})
    elif player_id == 4:
        keyboard_actually_enabled = getattr(game_config, "P4_KEYBOARD_ENABLED", False)
        controller_actually_enabled = getattr(game_config, "P4_CONTROLLER_ENABLED", False)
        assigned_device_str = getattr(game_config, "CURRENT_P4_INPUT_DEVICE", "unassigned")
        default_keyboard_map_for_player = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS # Or a P4 default
        player_specific_controller_map_source = getattr(game_config, "P4_MAPPINGS", {})
    else:
        if _app_input_limiter.can_print(f"unhandled_player_id_{player_id_str_log}"):
            warning(f"APP_INPUT_MANAGER: Input snapshot for unconfigured player ID {player_id}. No input.")
        return final_action_events

    # --- 1. Process Keyboard Input ---
    if keyboard_actually_enabled:
        keyboard_map_to_use: Dict[str, Qt.Key]
        if assigned_device_str == "keyboard_p1":
            keyboard_map_to_use = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        elif assigned_device_str == "keyboard_p2": # Could also be P3/P4 default kbd if they exist
            keyboard_map_to_use = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        else: 
            keyboard_map_to_use = default_keyboard_map_for_player
            if _app_input_limiter.can_print(f"kbd_fallback_map_{player_id_str_log}"):
                debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Using kbd map '{str(keyboard_map_to_use)[:50]}...' for P{player_id} (assigned_dev='{assigned_device_str}').")
        
        current_frame_discrete_events = list(_qt_key_events_this_frame_global)

        keyboard_action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot_global,
            current_frame_discrete_events, 
            keyboard_map_to_use,
            game_elements_ref.get("platforms_list", []),
            joystick_data=None
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
        
        active_kbd_actions = {k:v for k,v in keyboard_action_events.items() if v}
        if _app_input_limiter.can_print(f"kbd_actions_result_{player_id_str_log}") or active_kbd_actions:
            debug(f"APP_INPUT_MANAGER ({player_id_str_log}) KBD_ACTIONS from process_player_input_logic: {active_kbd_actions if active_kbd_actions else 'None'}")


    # --- 2. Process Controller Input ---
    if controller_actually_enabled and assigned_device_str.startswith("joystick_pygame_"):
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            joystick_idx = int(assigned_device_str.split('_')[-1])
            if 0 <= joystick_idx < len(pygame_joysticks_list) and pygame_joysticks_list[joystick_idx] is not None:
                joy = pygame_joysticks_list[joystick_idx]
                assert joy is not None # Make mypy happy after check
                if not joy.get_init(): joy.init() 

                current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
                
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
                
                controller_map_to_use = player_specific_controller_map_source
                
                is_valid_joystick_runtime_map = False
                if controller_map_to_use and isinstance(controller_map_to_use, dict) and controller_map_to_use:
                    first_value = next(iter(controller_map_to_use.values()), None)
                    if isinstance(first_value, dict) and 'type' in first_value:
                        is_valid_joystick_runtime_map = True
                
                if not is_valid_joystick_runtime_map:
                    if _app_input_limiter.can_print(f"ctrl_map_invalid_fallback_{player_id_str_log}"):
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Player-specific map for {assigned_device_str} invalid. Re-translating or using generic.")
                    active_guid = game_config.get_joystick_guid_by_pygame_index(joystick_idx)
                    controller_map_to_use = game_config._translate_gui_mappings_for_guid_to_runtime(
                        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS, active_guid
                    )
                    if not controller_map_to_use: 
                         controller_map_to_use = game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS
                
                controller_action_events = process_player_input_logic(
                    player_instance, {}, [], controller_map_to_use,
                    game_elements_ref.get("platforms_list", []),
                    joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
                
                active_ctrl_actions = {k:v for k,v in controller_action_events.items() if v}
                if _app_input_limiter.can_print(f"ctrl_actions_result_{player_id_str_log}") or active_ctrl_actions:
                    debug(f"APP_INPUT_MANAGER ({player_id_str_log}) CTRL_ACTIONS (Joy {joystick_idx}) from process_player_input_logic: {active_ctrl_actions if active_ctrl_actions else 'None'}")

            else:
                if _app_input_limiter.can_print(f"joy_idx_unavailable_{player_id_str_log}"):
                    warning(f"APP_INPUT_MANAGER: {player_id_str_log} assigned joystick {joystick_idx} unavailable (total: {len(pygame_joysticks_list)}, obj: {pygame_joysticks_list[joystick_idx] if 0 <= joystick_idx < len(pygame_joysticks_list) else 'OOB'}).")
        except (ValueError, IndexError, pygame.error) as e: # Added pygame.error
            if _app_input_limiter.can_print(f"joy_processing_err_{player_id_str_log}"):
                warning(f"APP_INPUT_MANAGER: Error processing joystick for {player_id_str_log} ('{assigned_device_str}'): {e}")
    
    active_final_actions = {k:v for k,v in final_action_events.items() if v}
    if _app_input_limiter.can_print(f"final_actions_combined_{player_id_str_log}") or active_final_actions:
        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) FINAL_ACTIONS_COMBINED: {active_final_actions if active_final_actions else 'None'}")

    return final_action_events