# app_input_manager.py
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

import pygame # For Pygame joystick data

# Game-specific imports
import config as game_config
from player import Player # For type hinting
# player_input_handler is the core logic for translating raw input to game actions
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
from logger import warning # Assuming logger is set up elsewhere and accessible

# Global state for Qt key events, managed by app_core.py's event handlers
_qt_keys_pressed_snapshot_global: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame_global: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []

def update_qt_key_press(key: Qt.Key, is_auto_repeat: bool):
    """Called by MainWindow.keyPressEvent"""
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = True
        _qt_key_events_this_frame_global.append((QKeyEvent.Type.KeyPress, key, is_auto_repeat))

def update_qt_key_release(key: Qt.Key, is_auto_repeat: bool):
    """Called by MainWindow.keyReleaseEvent"""
    if not is_auto_repeat:
        _qt_keys_pressed_snapshot_global[key] = False
        # KeyRelease events are not typically added to _qt_key_events_this_frame
        # as process_player_input_logic usually focuses on "just pressed"

def clear_qt_key_events_this_frame():
    """Called after processing input for a frame"""
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Player,
    player_id: int,
    pygame_joysticks_list: List[pygame.joystick.Joystick], # Pass the list of Pygame joysticks
    pygame_joy_button_prev_state_list: List[Dict[int, bool]], # Pass the list of prev states
    game_elements_ref: Dict[str, Any] # Pass game_elements for platforms_list
    ) -> Dict[str, bool]:
    """
    Gets input snapshot for a specific player.
    Now takes Pygame joystick objects directly.
    """
    if not player_instance or not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
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
        # Pygame events should be pumped by the main loop (or a dedicated Pygame event poller if preferred)
        # For this specific input snapshot, we assume Pygame's state is current.
        # pygame.event.pump() # Call this in the main game loop timer instead of here for efficiency

        current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
        
        # Ensure the prev_state list has an entry for this joystick
        while len(pygame_joy_button_prev_state_list) <= joystick_pygame_idx_for_player:
            pygame_joy_button_prev_state_list.append({})
        
        prev_buttons_state = pygame_joy_button_prev_state_list[joystick_pygame_idx_for_player]

        joystick_data_for_handler = {
            'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
            'buttons_current': current_buttons_state,
            'buttons_prev': prev_buttons_state.copy(), # Pass a copy
            'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
        }
        # Update the stored previous state for the next frame for this joystick
        pygame_joy_button_prev_state_list[joystick_pygame_idx_for_player] = current_buttons_state.copy()
    
    platforms_list = game_elements_ref.get("platforms_list", [])
    if not isinstance(platforms_list, list): platforms_list = []

    action_events = process_player_input_logic(
        player_instance,
        _qt_keys_pressed_snapshot_global,
        list(_qt_key_events_this_frame_global), # Pass a copy
        active_mappings,
        platforms_list,
        joystick_data=joystick_data_for_handler
    )
    # Key events are cleared by the main loop after all players' inputs are processed
    return action_events