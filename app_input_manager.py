# app_input_manager.py
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

import pygame # For Pygame joystick data

# Game-specific imports
import config as game_config
# from player import Player # <<< COMMENT OUT or REMOVE this line
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
from logger import warning

_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = True
        _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = False

def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any, # Changed type hint to Any temporarily
    player_id: int,
    pygame_joysticks_list: List[pygame.joystick.Joystick],
    pygame_joy_button_prev_state_list: List[Dict[int, bool]],
    game_elements_ref: Dict[str, Any]
    ) -> Dict[str, bool]:
    """
    Gets input snapshot for a specific player.
    """
    from player import Player # <<< IMPORT Player HERE, inside the function

    if not player_instance or not isinstance(player_instance, Player) or \
       not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
        warning(f"APP_INPUT_MANAGER: Invalid player_instance for player_id {player_id}.")
        return {}

    active_mappings = {}
    joystick_pygame_idx_for_player: Optional[int] = None
    player_device_str = game_config.CURRENT_P1_INPUT_DEVICE if player_id == 1 else game_config.CURRENT_P2_INPUT_DEVICE
    active_mappings = game_config.P1_MAPPINGS if player_id == 1 else game_config.P2_MAPPINGS

    if player_device_str.startswith("joystick_pygame_"):
        try:
            joystick_pygame_idx_for_player = int(player_device_str.split('_')[-1])
        except (ValueError, IndexError):
            joystick_pygame_idx_for_player = None
            warning(f"APP_INPUT_MANAGER: Could not parse Pygame joystick index from '{player_device_str}' for P{player_id}")

    joystick_data_for_handler: Optional[Dict[str,Any]] = None
    if joystick_pygame_idx_for_player is not None and \
       0 <= joystick_pygame_idx_for_player < len(pygame_joysticks_list):
        joy = pygame_joysticks_list[joystick_pygame_idx_for_player]
        
        current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
        
        while len(pygame_joy_button_prev_state_list) <= joystick_pygame_idx_for_player:
            pygame_joy_button_prev_state_list.append({})
        
        prev_buttons_state = pygame_joy_button_prev_state_list[joystick_pygame_idx_for_player]

        joystick_data_for_handler = {
            'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
            'buttons_current': current_buttons_state,
            'buttons_prev': prev_buttons_state.copy(),
            'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
        }
        pygame_joy_button_prev_state_list[joystick_pygame_idx_for_player] = current_buttons_state.copy()
    
    platforms_list = game_elements_ref.get("platforms_list", [])
    if not isinstance(platforms_list, list): platforms_list = []

    action_events = process_player_input_logic(
        player_instance,
        _qt_keys_pressed_snapshot_global,
        list(_qt_key_events_this_frame_global),
        active_mappings,
        platforms_list,
        joystick_data=joystick_data_for_handler
    )
    return action_events