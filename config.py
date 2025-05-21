# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1/P2.
"""
# version 2.3.1 (Refined joystick initialization and re-scan logic)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
from PySide6.QtCore import Qt # For Qt.Key enums

# --- Initialize Pygame Joystick ---
# This block ensures Pygame and its joystick module are initialized once globally.
_pygame_initialized_globally = False
_joystick_initialized_globally = False
_detected_joystick_count_global = 0
_detected_joystick_names_global: List[str] = []

def init_pygame_and_joystick_globally():
    global _pygame_initialized_globally, _joystick_initialized_globally
    global _detected_joystick_count_global, _detected_joystick_names_global

    if not _pygame_initialized_globally:
        try:
            pygame.init()
            _pygame_initialized_globally = True
            print("Config: Pygame globally initialized.")
        except Exception as e_pg_init:
            print(f"Config CRITICAL ERROR: Pygame global init failed: {e_pg_init}")
            return # Cannot proceed without pygame.init()

    if not _joystick_initialized_globally:
        try:
            pygame.joystick.init()
            _joystick_initialized_globally = True
            print("Config: Pygame Joystick globally initialized.")
        except Exception as e_joy_init:
            print(f"Config CRITICAL ERROR: Pygame Joystick global init failed: {e_joy_init}")
            # Pygame might be init, but joysticks won't work.
            _detected_joystick_count_global = 0
            _detected_joystick_names_global = []
            return

    # Scan for joysticks if joystick system is initialized
    if _joystick_initialized_globally:
        _detected_joystick_count_global = pygame.joystick.get_count()
        _detected_joystick_names_global = []
        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i) # Get reference, doesn't init the Joystick object fully
                _detected_joystick_names_global.append(joy.get_name())
            except pygame.error as e_joy_get:
                print(f"Config Warning: Error getting info for joystick {i}: {e_joy_get}")
        print(f"Config: Global scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally() # Call it once when config.py is imported

# --- File for saving/loading ALL settings ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME
)

# --- Default Control Schemes & Enabled Flags ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P1_KEYBOARD_ENABLED = True
DEFAULT_P1_CONTROLLER_ENABLED = True

DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
DEFAULT_P2_KEYBOARD_ENABLED = True
DEFAULT_P2_CONTROLLER_ENABLED = True

# --- Current Settings (will be updated by load_config) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED
P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED

CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED
P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED

# --- Joystick Axis Thresholds ---
AXIS_THRESHOLD_DEFAULT = 0.7

# --- Game Actions ---
GAME_ACTIONS = [
    "left", "right", "up", "down", "jump", "crouch", "attack1", "attack2",
    "dash", "roll", "interact", "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]

EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP": "jump", "CROUCH": "crouch", "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1", "ATTACK_SECONDARY": "attack2",
    "DASH": "dash", "ROLL": "roll", "RESET": "reset",
    "WEAPON_1": "projectile1", "WEAPON_2": "projectile2", "WEAPON_3": "projectile3", "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6", "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause",
    "W": "up", "A": "left", "S": "down", "D": "right",
    "1": "projectile1", "2": "projectile2", "3": "projectile3", "4": "projectile4", "5": "projectile5",
    "Q": "reset", "E": "interact", "V": "attack1", "B": "attack2",
    "SPACE": "jump", "SHIFT": "dash", "CTRL": "roll",
}

# --- Default Keyboard Mappings ---
DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3,
    "projectile4": Qt.Key.Key_4, "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7,
    "reset": Qt.Key.Key_Q, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K, "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_8, "projectile2": Qt.Key.Key_9, "projectile3": Qt.Key.Key_0,
    "projectile4": Qt.Key.Key_Minus, "projectile5": Qt.Key.Key_Equal,
    "projectile6": Qt.Key.Key_BracketLeft, "projectile7": Qt.Key.Key_BracketRight,
    "reset": Qt.Key.Key_Period, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete,
    "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End,
}

#button controls are here
# --- Default Pygame Joystick Mappings (Fallback) ---
DEFAULT_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, "crouch": {"type": "button", "id": 1},
    "attack1": {"type": "button", "id": 2}, "attack2": {"type": "button", "id": 3},
    "dash": {"type": "button", "id": 5}, "roll": {"type": "button", "id": 4},
    "interact": {"type": "button", "id": 10},
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)},
    "projectile5": {"type": "button", "id": 8}, "projectile6": {"type": "button", "id": 9},
    "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "reset": {"type": "button", "id": 6}, "pause": {"type": "button", "id": 7},
    "menu_confirm": {"type": "button", "id": 1}, "menu_cancel": {"type": "button", "id": 2},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {} # Stores raw GUI format joystick mappings
P1_MAPPINGS: Dict[str, Any] = {}
P2_MAPPINGS: Dict[str, Any] = {}

# This variable will hold the translated Pygame mappings for runtime use.
# It's populated when load_config runs or when settings are saved in the GUI.
_TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME: Dict[str, Any] = {}

def get_translated_pygame_joystick_mappings() -> Dict[str, Any]:
    """Returns the currently active translated Pygame joystick mappings."""
    return _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME

def _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_joystick_mappings: Any) -> Dict[str, Any]:
    INPUTS_STR_ID_TO_PYGAME_INT_ID_MAP = {
        "ABS_X": 0, "ABS_Y": 1, "ABS_RX": 3, "ABS_RY": 4, "ABS_Z": 2, "ABS_RZ": 5,
        "BTN_SOUTH": 0, "BTN_EAST": 1, "BTN_WEST": 2, "BTN_NORTH": 3,
        "BTN_TL": 4, "BTN_TR": 5, "BTN_SELECT": 6, "BTN_START": 7,
        "BTN_THUMBL": 8, "BTN_THUMBR": 9,
        "BTN_DPAD_UP": 11, "BTN_DPAD_DOWN": 12, "BTN_DPAD_LEFT": 13, "BTN_DPAD_RIGHT": 14,
    }
    translated_mappings: Dict[str, Any] = {}
    if not isinstance(raw_gui_json_joystick_mappings, dict):
        print("Config Error: Raw GUI JSON joystick mappings part is not a dictionary.")
        return {}

    for gui_action_key, mapping_entry in raw_gui_json_joystick_mappings.items():
        internal_action_name = EXTERNAL_TO_INTERNAL_ACTION_MAP.get(gui_action_key)
        if not internal_action_name:
            if gui_action_key in GAME_ACTIONS: internal_action_name = gui_action_key
            else: continue

        if not isinstance(mapping_entry, dict): continue
        pygame_event_type = mapping_entry.get("event_type")
        # IMPORTANT: The 'details' here comes from the structure saved by controller_mapper_gui.py
        # It should directly contain the "type-specific" details like "button_id", "axis_id", etc.
        details_from_gui = mapping_entry.get("details") # This is the event_details_from_thread
        if not isinstance(details_from_gui, dict): continue

        pygame_event_id_from_json = None
        if pygame_event_type == "button": pygame_event_id_from_json = details_from_gui.get("button_id")
        elif pygame_event_type == "axis": pygame_event_id_from_json = details_from_gui.get("axis_id")
        elif pygame_event_type == "hat": pygame_event_id_from_json = details_from_gui.get("hat_id")

        if pygame_event_type not in ["button", "axis", "hat"] or pygame_event_id_from_json is None: continue

        final_pygame_id_for_mapping: Optional[int] = None
        if isinstance(pygame_event_id_from_json, str): # This means it's likely an 'inputs' lib style string
            final_pygame_id_for_mapping = INPUTS_STR_ID_TO_PYGAME_INT_ID_MAP.get(pygame_event_id_from_json)
            if final_pygame_id_for_mapping is None:
                print(f"Config Warning: String ID '{pygame_event_id_from_json}' (action '{gui_action_key}') not in map. Skipping.")
                continue
        elif isinstance(pygame_event_id_from_json, int):
            final_pygame_id_for_mapping = pygame_event_id_from_json
        else:
            print(f"Config Warning: Invalid ID type '{type(pygame_event_id_from_json)}' (action '{gui_action_key}'). Skipping.")
            continue

        final_mapping_for_action: Dict[str, Any] = {"type": pygame_event_type, "id": final_pygame_id_for_mapping}
        if pygame_event_type == "axis":
            axis_direction = details_from_gui.get("direction")
            axis_threshold = details_from_gui.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_direction not in [-1, 1]: continue
            final_mapping_for_action["value"] = axis_direction
            final_mapping_for_action["threshold"] = float(axis_threshold)
        elif pygame_event_type == "hat":
            hat_value_from_details = details_from_gui.get("value")
            if not isinstance(hat_value_from_details, (tuple, list)) or len(hat_value_from_details) != 2: continue
            final_mapping_for_action["value"] = tuple(map(int, hat_value_from_details))

        translated_mappings[internal_action_name] = final_mapping_for_action
    return translated_mappings

def get_available_joystick_names_with_indices() -> List[Tuple[str, str]]:
    devices = []
    if _joystick_initialized_globally: # Use the global flag
        # Re-scan to get fresh list, as app_core might also init joysticks individually
        current_joy_count = pygame.joystick.get_count()
        current_joy_names = []
        for i in range(current_joy_count):
            try:
                joy = pygame.joystick.Joystick(i)
                current_joy_names.append(joy.get_name())
            except pygame.error:
                current_joy_names.append(f"Joystick {i} (Error)")

        for i in range(current_joy_count):
            joy_name = current_joy_names[i] if i < len(current_joy_names) else f"Joystick {i}"
            internal_id = f"joystick_pygame_{i}"
            display_name = f"Controller {i}: {joy_name}"
            devices.append((display_name, internal_id))
    return devices

def save_config():
    global CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global LOADED_PYGAME_JOYSTICK_MAPPINGS # This now stores the raw GUI format

    data_to_save = {
        "config_version": "2.3.1",
        "player1_settings": {
            "input_device": CURRENT_P1_INPUT_DEVICE,
            "keyboard_enabled": P1_KEYBOARD_ENABLED,
            "controller_enabled": P1_CONTROLLER_ENABLED,
        },
        "player2_settings": {
            "input_device": CURRENT_P2_INPUT_DEVICE,
            "keyboard_enabled": P2_KEYBOARD_ENABLED,
            "controller_enabled": P2_CONTROLLER_ENABLED,
        },
        "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS # Save the raw GUI format
    }
    try:
        if not os.path.exists(CONTROLLER_SETTINGS_SUBDIR):
            os.makedirs(CONTROLLER_SETTINGS_SUBDIR)
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        # After saving, ensure the runtime mappings are also updated
        global _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME
        _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME = _translate_and_validate_gui_json_to_pygame_mappings(LOADED_PYGAME_JOYSTICK_MAPPINGS)
        update_player_mappings_from_config() # This will use the new translated mappings for P1/P2_MAPPINGS
        return True
    except IOError as e:
        print(f"Config Error: Saving settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}")
        return False

def load_config():
    global CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global LOADED_PYGAME_JOYSTICK_MAPPINGS, _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME
    global P1_MAPPINGS, P2_MAPPINGS
    global _detected_joystick_count_global, _detected_joystick_names_global # Use global vars

    # Ensure Pygame joystick system is ready and rescan for current controllers
    if not _pygame_initialized_globally or not _joystick_initialized_globally:
        print("Config (load_config): Pygame/Joystick not globally initialized. Attempting now.")
        init_pygame_and_joystick_globally() # Try to initialize if not already

    # Re-scan joysticks to get the most current list
    if _joystick_initialized_globally:
        pygame.joystick.quit() # Quit to force a re-scan
        pygame.joystick.init()
        _detected_joystick_count_global = pygame.joystick.get_count()
        _detected_joystick_names_global = []
        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i)
                _detected_joystick_names_global.append(joy.get_name())
            except pygame.error:
                 _detected_joystick_names_global.append(f"Joystick {i} (Error on rescan)")
        print(f"Config (load_config): Refreshed joystick count: {_detected_joystick_count_global}, Names: {_detected_joystick_names_global}")
    else:
        print("Config (load_config): Joystick system not initialized, cannot refresh count.")
        _detected_joystick_count_global = 0
        _detected_joystick_names_global = []

    raw_config_data = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_config_data = json.load(f)
            print(f"Config: Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults."); raw_config_data = {}
    else:
        print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults/auto-detect.")

    p1_settings = raw_config_data.get("player1_settings", {})
    CURRENT_P1_INPUT_DEVICE = p1_settings.get("input_device", DEFAULT_P1_INPUT_DEVICE)
    P1_KEYBOARD_ENABLED = p1_settings.get("keyboard_enabled", DEFAULT_P1_KEYBOARD_ENABLED)
    P1_CONTROLLER_ENABLED = p1_settings.get("controller_enabled", DEFAULT_P1_CONTROLLER_ENABLED)

    p2_settings = raw_config_data.get("player2_settings", {})
    CURRENT_P2_INPUT_DEVICE = p2_settings.get("input_device", DEFAULT_P2_INPUT_DEVICE)
    P2_KEYBOARD_ENABLED = p2_settings.get("keyboard_enabled", DEFAULT_P2_KEYBOARD_ENABLED)
    P2_CONTROLLER_ENABLED = p2_settings.get("controller_enabled", DEFAULT_P2_CONTROLLER_ENABLED)

    # LOADED_PYGAME_JOYSTICK_MAPPINGS stores the raw GUI format from the JSON
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings", {})
    # Translate them for runtime use
    _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME = _translate_and_validate_gui_json_to_pygame_mappings(LOADED_PYGAME_JOYSTICK_MAPPINGS)

    if not _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME and LOADED_PYGAME_JOYSTICK_MAPPINGS:
        print("Config Warning: Joystick mappings translation failed. Using default joystick mappings for runtime.")
    elif not LOADED_PYGAME_JOYSTICK_MAPPINGS:
        print("Config Info: No joystick mappings found in file. Using default joystick mappings for runtime.")


    if not raw_config_data: # File didn't exist or was invalid
        print("Config: No valid config file found, attempting auto-assignment of controllers.")
        if _detected_joystick_count_global > 0:
            CURRENT_P1_INPUT_DEVICE = f"joystick_pygame_0"
            P1_CONTROLLER_ENABLED = True; P1_KEYBOARD_ENABLED = True # Default enables
            print(f"Config Auto-Assign: P1 to joystick_pygame_0 ({_detected_joystick_names_global[0] if _detected_joystick_names_global else 'N/A'}).")
            if _detected_joystick_count_global > 1:
                CURRENT_P2_INPUT_DEVICE = f"joystick_pygame_1"
                P2_CONTROLLER_ENABLED = True; P2_KEYBOARD_ENABLED = True
                print(f"Config Auto-Assign: P2 to joystick_pygame_1 ({_detected_joystick_names_global[1] if len(_detected_joystick_names_global) > 1 else 'N/A'}).")
            else:
                CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                print(f"Config Auto-Assign: P2 to {DEFAULT_P2_INPUT_DEVICE} (only one joystick).")
        else:
            CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
            print("Config Auto-Assign: No joysticks detected. P1 & P2 to default keyboards.")

    # Validate assigned joystick devices against currently detected ones
    for player_num_str, current_device_var_name, default_device_val in [("P1", "CURRENT_P1_INPUT_DEVICE", DEFAULT_P1_INPUT_DEVICE),
                                                                        ("P2", "CURRENT_P2_INPUT_DEVICE", DEFAULT_P2_INPUT_DEVICE)]:
        current_assigned_device = globals()[current_device_var_name]
        if current_assigned_device.startswith("joystick_pygame_"):
            try:
                joy_idx = int(current_assigned_device.split('_')[-1])
                if not (0 <= joy_idx < _detected_joystick_count_global):
                    print(f"Config Warning: {player_num_str}'s assigned joystick '{current_assigned_device}' not found (Count: {_detected_joystick_count_global}). Falling back.")
                    globals()[current_device_var_name] = default_device_val
            except (ValueError, IndexError):
                print(f"Config Warning: {player_num_str}'s joystick assignment '{current_assigned_device}' malformed. Falling back.")
                globals()[current_device_var_name] = default_device_val
    
    # Prevent P1 and P2 from using the EXACT SAME joystick_pygame_X device
    if CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_") and CURRENT_P1_INPUT_DEVICE == CURRENT_P2_INPUT_DEVICE:
        print(f"Config Warning: P1 and P2 assigned same joystick ('{CURRENT_P1_INPUT_DEVICE}'). Resetting P2 to default keyboard.")
        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # P2 gets keyboard

    # Prevent P1 and P2 from using the same keyboard layout if both are set to keyboard
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1" and CURRENT_P2_INPUT_DEVICE == "keyboard_p1":
        CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
    elif CURRENT_P1_INPUT_DEVICE == "keyboard_p2" and CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
         CURRENT_P1_INPUT_DEVICE = "keyboard_p1"

    update_player_mappings_from_config()

    print(f"Config Loaded: P1 Dev='{CURRENT_P1_INPUT_DEVICE}', KbdEn={P1_KEYBOARD_ENABLED}, CtrlEn={P1_CONTROLLER_ENABLED}")
    print(f"Config Loaded: P2 Dev='{CURRENT_P2_INPUT_DEVICE}', KbdEn={P2_KEYBOARD_ENABLED}, CtrlEn={P2_CONTROLLER_ENABLED}")
    return True

def update_player_mappings_from_config():
    """Sets P1_MAPPINGS and P2_MAPPINGS based on CURRENT_*_INPUT_DEVICE and the translated joystick mappings."""
    global P1_MAPPINGS, P2_MAPPINGS, _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME

    active_joy_mappings = _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME if _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()

    # Player 1 Mappings
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1": P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE == "keyboard_p2": P1_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_"): P1_MAPPINGS = active_joy_mappings
    else: P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy() # Fallback

    # Player 2 Mappings
    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick_pygame_"): P2_MAPPINGS = active_joy_mappings
    else: P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy() # Fallback

    print(f"Config: Player mappings updated. P1 using '{CURRENT_P1_INPUT_DEVICE}', P2 using '{CURRENT_P2_INPUT_DEVICE}'.")

if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    # Ensure Pygame is fully quit if run multiple times for testing
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
        _pygame_initialized_globally = False
        _joystick_initialized_globally = False
        print("Config Test: Pygame explicitly quit for re-initialization.")

    init_pygame_and_joystick_globally() # Re-initialize for the test run
    load_config()
    print(f"\nAfter test load_config():")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    print(f"  P1 Device: {CURRENT_P1_INPUT_DEVICE}, KbdEn: {P1_KEYBOARD_ENABLED}, CtrlEn: {P1_CONTROLLER_ENABLED}")
    print(f"  P1 Mappings sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  P2 Device: {CURRENT_P2_INPUT_DEVICE}, KbdEn: {P2_KEYBOARD_ENABLED}, CtrlEn: {P2_CONTROLLER_ENABLED}")
    print(f"  P2 Mappings sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")

    if _TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME:
        print(f"  RUNTIME Joystick Mappings (first 5 or all):")
        for i, (k, v) in enumerate(_TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME.items()):
            if i >= 5: print(f"    ... and {len(_TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME) - 5} more."); break
            print(f"    '{k}': {v}")
    else:
        print(f"  RUNTIME Joystick Mappings: Not loaded or empty. Default Pygame joystick mappings would be used if a joystick is selected.")

    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("--- config.py direct test finished ---")