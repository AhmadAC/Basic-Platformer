# app_input_manager.py
import os
import sys # Added sys for potential path manipulation if needed, though not directly used here
import json # For debug printing joystick maps
import time
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QPointF # Added QPointF

import pygame # For Pygame joystick data

# Ensure project root is in path for sibling imports if this file is run directly or by a test
_project_root_app_input = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if _project_root_app_input not in sys.path:
    sys.path.insert(0, _project_root_app_input)

import config as game_config
import constants as C # For JOYSTICK_AXIS/HAT_EVENT_ACTIONS if used
# Assuming process_player_input_logic_pyside is in player_input_handler.py at the same level
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
from logger import warning, debug, error # Added error
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
    # For releases, often only the snapshot update is needed.
    # If discrete release events are required for some game logic, they could be added to _qt_key_events_this_frame_global.

def clear_qt_key_events_this_frame():
    _qt_key_events_this_frame_global.clear()

def get_input_snapshot(
    player_instance: Any, # Should ideally be type hinted as 'Player' from player.py
    player_id: int,
    # This list from app_core should contain initialized Pygame Joystick objects
    pygame_joysticks_list_from_app_core: List[Optional[pygame.joystick.Joystick]],
    # This list from app_core should be indexed by joystick.instance_id()
    pygame_joy_button_prev_state_by_instance_id_list: List[Dict[int, bool]],
    game_elements_ref: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Processes input for a given player and returns a dictionary of action events.
    - Keyboard input uses Qt key events.
    - Joystick input uses Pygame polling and player-specific runtime mappings from config.
    """
    # Lazy import Player if needed for type checking to avoid circular dependencies
    # from player import Player # if isinstance(player_instance, Player) is needed

    if not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
        if _app_input_limiter.can_print(f"invalid_player_instance_input_{player_id}"):
            warning(f"APP_INPUT_MANAGER (P{player_id}): Player instance not validly initialized. Skipping input processing.")
        return {}

    final_action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}
    player_id_str_log = f"P{player_id}"

    # --- Determine Player-Specific Settings from game_config ---
    keyboard_actually_enabled = getattr(game_config, f"P{player_id}_KEYBOARD_ENABLED", False)
    controller_actually_enabled = getattr(game_config, f"P{player_id}_CONTROLLER_ENABLED", False)
    assigned_device_str = getattr(game_config, f"CURRENT_P{player_id}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
    
    # Get the correct RUNTIME mappings for this player (already translated by config.py)
    player_specific_runtime_mappings = getattr(game_config, f"P{player_id}_MAPPINGS", {})

    # --- 1. Process Keyboard Input ---
    if keyboard_actually_enabled and assigned_device_str.startswith("keyboard_"):
        # keyboard_map_to_use_for_qt should be the Qt.Key based map
        # If Px_MAPPINGS stores this for keyboard, use it. Otherwise, derive like before.
        keyboard_map_to_use_for_qt: Dict[str, Qt.Key]
        if assigned_device_str == "keyboard_p1":
            keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        elif assigned_device_str == "keyboard_p2":
            keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P2_MAPPINGS
        else: # Fallback or if P3/P4 have their own kbd layouts defined in config
            keyboard_map_to_use_for_qt = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS # Default to P1 layout
        
        keyboard_action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot_global,
            list(_qt_key_events_this_frame_global), # Pass current frame's discrete events
            keyboard_map_to_use_for_qt, # This is already Qt.Key format for keyboard
            game_elements_ref.get("platforms_list", []),
            joystick_data=None # No joystick data for keyboard path
        )
        for action, is_active in keyboard_action_events.items():
            if is_active: final_action_events[action] = True
        
        if _app_input_limiter.can_print(f"kbd_snapshot_events_{player_id_str_log}"):
            active_kbd_events = {k:v for k,v in keyboard_action_events.items() if v}
            if active_kbd_events:
                 debug(f"APP_INPUT_MANAGER ({player_id_str_log}) KBD Events: {active_kbd_events}")

    # --- 2. Process Controller Input ---
    elif controller_actually_enabled and assigned_device_str.startswith("joystick_pygame_"):
        joystick_data_for_handler: Optional[Dict[str, Any]] = None
        try:
            # The assigned_device_str is like "joystick_pygame_0"
            # This index '0' is the Pygame joystick index.
            joystick_py_idx = int(assigned_device_str.split('_')[-1])

            if 0 <= joystick_py_idx < len(pygame_joysticks_list_from_app_core) and \
               pygame_joysticks_list_from_app_core[joystick_py_idx] is not None:
                
                joy = pygame_joysticks_list_from_app_core[joystick_py_idx]
                assert joy is not None # Should be true due to above check

                if not joy.get_init():
                    try:
                        joy.init() # Ensure it's initialized for this game tick
                        debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Initialized Pygame joystick index {joystick_py_idx} ('{joy.get_name()}') for game input.")
                    except pygame.error as e_init:
                        if _app_input_limiter.can_print(f"joy_init_fail_ingame_{player_id_str_log}_{joystick_py_idx}"):
                            warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Failed to init joystick {joystick_py_idx} for game input: {e_init}")
                        return final_action_events # Cannot proceed with this joystick

                current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
                
                joy_instance_id = joy.get_instance_id()
                
                # Ensure pygame_joy_button_prev_state_by_instance_id_list is large enough
                if joy_instance_id >= len(pygame_joy_button_prev_state_by_instance_id_list):
                    if _app_input_limiter.can_print(f"prev_state_resize_{player_id_str_log}"):
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): prev_state list too small for instance_id {joy_instance_id}. List size: {len(pygame_joy_button_prev_state_by_instance_id_list)}. Input might be faulty this frame.")
                    # This indicates a problem with how app_core is sizing this list.
                    # For now, we'll try to avoid an error but log it.
                    prev_buttons_state_for_this_joy = {} # Empty prev state, all buttons will seem newly pressed
                else:
                    prev_buttons_state_for_this_joy = pygame_joy_button_prev_state_by_instance_id_list[joy_instance_id]

                joystick_data_for_handler = {
                    'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                    'buttons_current': current_buttons_state,
                    'buttons_prev': prev_buttons_state_for_this_joy.copy(), # Pass copy
                    'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
                }
                # Update the global previous state list (indexed by instance ID) for the next frame
                pygame_joy_button_prev_state_by_instance_id_list[joy_instance_id] = current_buttons_state.copy()
                
                # Use the player-specific RUNTIME mappings (P1_MAPPINGS, P2_MAPPINGS, etc.)
                active_runtime_joystick_map = player_specific_runtime_mappings
                if not active_runtime_joystick_map: # Fallback if Px_MAPPINGS was empty for some reason
                    if _app_input_limiter.can_print(f"joy_map_fallback_{player_id_str_log}"):
                        warning(f"APP_INPUT_MANAGER ({player_id_str_log}): Player-specific runtime map (P{player_id}_MAPPINGS) is empty. Falling back to DEFAULT_GENERIC_JOYSTICK_MAPPINGS.")
                    active_runtime_joystick_map = game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS

                if _app_input_limiter.can_print(f"joy_map_used_debug_{player_id_str_log}"):
                    debug(f"APP_INPUT_MANAGER ({player_id_str_log}): Using joystick map for Player {player_id} (Device: {assigned_device_str}):")
                    try: debug(json.dumps(active_runtime_joystick_map, indent=2))
                    except TypeError: debug(str(active_runtime_joystick_map)) # If not JSON serializable

                controller_action_events = process_player_input_logic(
                    player_instance,
                    {}, # Empty keyboard snapshot for joystick path
                    [], # Empty keyboard events for joystick path
                    active_runtime_joystick_map, # CRITICAL: Pass the correct runtime map
                    game_elements_ref.get("platforms_list", []),
                    joystick_data=joystick_data_for_handler
                )
                for action, is_active in controller_action_events.items():
                    if is_active: final_action_events[action] = True
                
                if _app_input_limiter.can_print(f"ctrl_snapshot_events_{player_id_str_log}"):
                    active_ctrl_events = {k:v for k,v in controller_action_events.items() if v}
                    if active_ctrl_events:
                        debug(f"APP_INPUT_MANAGER ({player_id_str_log}) CTRL Events (JoyIdx {joystick_py_idx}, InstID {joy_instance_id}): {active_ctrl_events}")
            else:
                if _app_input_limiter.can_print(f"joy_idx_unavailable_{player_id_str_log}"):
                    warning(f"APP_INPUT_MANAGER: {player_id_str_log} assigned joystick index {joystick_py_idx} but it's not available or None in app_core's list (list size: {len(pygame_joysticks_list_from_app_core)}).")
        except (ValueError, IndexError, AttributeError) as e:
            if _app_input_limiter.can_print(f"joy_process_err_{player_id_str_log}"):
                error(f"APP_INPUT_MANAGER: Error processing joystick for {player_id_str_log} from '{assigned_device_str}': {e}", exc_info=True)
    
    # --- Final Debug Print for Combined Actions ---
    if _app_input_limiter.can_print(f"final_actions_{player_id_str_log}"):
        active_final_events = {k:v for k,v in final_action_events.items() if v}
        if active_final_events:
            debug(f"APP_INPUT_MANAGER ({player_id_str_log}) Final Combined Action Events: {active_final_events}")

    return final_action_events