# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1/P2.
"""
# version 2.3.3 (Improved joystick mapping loading and translation logic)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
from PySide6.QtCore import Qt # For Qt.Key enums

# --- Global Pygame State Variables (Managed by this module) ---
_pygame_initialized_globally = False
_joystick_initialized_globally = False
_detected_joystick_count_global = 0
_detected_joystick_names_global: List[str] = []
_joystick_objects_global: List[Optional[pygame.joystick.Joystick]] = [] # Store actual joystick objects

def init_pygame_and_joystick_globally(force_rescan=False): # Added force_rescan
    global _pygame_initialized_globally, _joystick_initialized_globally
    global _detected_joystick_count_global, _detected_joystick_names_global, _joystick_objects_global

    if not _pygame_initialized_globally:
        try:
            pygame.init()
            _pygame_initialized_globally = True
            print("Config: Pygame globally initialized.")
        except Exception as e_pg_init:
            print(f"Config CRITICAL ERROR: Pygame global init failed: {e_pg_init}")
            return

    if not _joystick_initialized_globally:
        try:
            pygame.joystick.init()
            _joystick_initialized_globally = True
            print("Config: Pygame Joystick globally initialized.")
        except Exception as e_joy_init:
            print(f"Config CRITICAL ERROR: Pygame Joystick global init failed: {e_joy_init}")
            return

    current_count = pygame.joystick.get_count()
    if force_rescan or current_count != _detected_joystick_count_global:
        print(f"Config: Joystick scan/re-scan initiated. Force: {force_rescan}, Old count: {_detected_joystick_count_global}, New count: {current_count}")
        _detected_joystick_count_global = current_count
        _detected_joystick_names_global = []

        for old_joy in _joystick_objects_global:
            if old_joy and old_joy.get_init():
                try: old_joy.quit()
                except pygame.error: pass
        _joystick_objects_global = []

        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i)
                _detected_joystick_names_global.append(joy.get_name())
                _joystick_objects_global.append(joy)
            except pygame.error as e_joy_get:
                print(f"Config Warning: Error getting info for joystick {i}: {e_joy_get}")
                _detected_joystick_names_global.append(f"Errored Joystick {i}")
                _joystick_objects_global.append(None)
        print(f"Config: Global scan/re-scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally() # Call it once when config.py is imported

# --- File for saving/loading ALL settings ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), # This is Platformer/
    CONTROLLER_SETTINGS_SUBDIR,                 # Platformer/controller_settings/
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME        # Platformer/controller_settings/controller_mappings.json
)
print(f"DEBUG config.py: Expecting JSON at: {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")


# --- Default Control Schemes & Enabled Flags ---
# For up to 4 players, if your game supports it
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P1_KEYBOARD_ENABLED = True
DEFAULT_P1_CONTROLLER_ENABLED = True # Allow both by default if device is joystick

DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
DEFAULT_P2_KEYBOARD_ENABLED = True
DEFAULT_P2_CONTROLLER_ENABLED = True

DEFAULT_P3_INPUT_DEVICE = "unassigned" # Assuming unassigned means no active input
DEFAULT_P3_KEYBOARD_ENABLED = False
DEFAULT_P3_CONTROLLER_ENABLED = False

DEFAULT_P4_INPUT_DEVICE = "unassigned"
DEFAULT_P4_KEYBOARD_ENABLED = False
DEFAULT_P4_CONTROLLER_ENABLED = False

UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

# --- Current Settings (will be updated by load_config) ---
# Initialize for 4 players to avoid AttributeErrors if game scales
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED
P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED

CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED
P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED

CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE
P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED
P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED

CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE
P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED
P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED

# --- Keyboard Device IDs for GUI selection ---
KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"] # Add more if you have more layouts
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"]


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
    # This map is more for external systems sending abstract actions
    # For GUI mapping, the internal action names (from GAME_ACTIONS) are primary.
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP_ACTION": "jump", "CROUCH_ACTION": "crouch", "INTERACT_ACTION": "interact", # Example of more abstract keys
    "PRIMARY_ATTACK": "attack1", "SECONDARY_ATTACK": "attack2",
    # ... other abstract mappings if needed ...
    # Direct key to action for some default keyboard setups (can be overridden)
    "W": "up", "A": "left", "S": "down", "D": "right",
    "SPACE": "jump", "V": "attack1", "B": "attack2", "SHIFT": "dash",
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

# --- Default Pygame Joystick Mappings (Fallback for runtime if no JSON map for a controller) ---
# This is in RUNTIME format
DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, "crouch": {"type": "button", "id": 1}, # Example: A=0, B=1 (Xbox)
    "attack1": {"type": "button", "id": 2}, "attack2": {"type": "button", "id": 3}, # X=2, Y=3
    "dash": {"type": "button", "id": 5}, "roll": {"type": "button", "id": 4}, # RB=5, LB=4
    "interact": {"type": "button", "id": 10}, # Example: Left Stick Press
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, # D-pad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)}, # D-pad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)},# D-pad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)},# D-pad Left
    # "projectile5": {"type": "button", "id": 8}, # Example: Back/Select
    # "projectile6": {"type": "button", "id": 9}, # Example: Start
    # "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Example: LT/RT as axis
    "reset": {"type": "button", "id": 6}, # Example: Back/Select
    "pause": {"type": "button", "id": 7}, # Example: Start
    "menu_confirm": {"type": "button", "id": 0}, # Usually A button
    "menu_cancel": {"type": "button", "id": 1},  # Usually B button
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

# This will store the raw GUI format joystick mappings loaded from JSON, keyed by GUID.
# Example: {"guid1": {"jump": {"event_type":..., "details":...}, ...}, "guid2": {...}}
LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}

# These will store the RUNTIME-TRANSLATED mappings for each player
P1_MAPPINGS: Dict[str, Any] = {}
P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}
P4_MAPPINGS: Dict[str, Any] = {}


def _translate_gui_map_to_runtime(gui_map_for_single_controller: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates a single controller's mappings from GUI storage format to runtime format.
    Input: {'action1': {'event_type':..., 'details':...}, 'action2': ...}
    Output: {'action1': {'type':..., 'id':...}, 'action2': ...}
    """
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(gui_map_for_single_controller, dict):
        print("Config Error: _translate_gui_map_to_runtime expects a dictionary for a single controller.")
        return {}

    for action_name, mapping_entry_gui_format in gui_map_for_single_controller.items():
        if action_name not in GAME_ACTIONS:
            # print(f"Config Warning (translate): Action '{action_name}' from GUI map not in GAME_ACTIONS. Skipping.")
            continue

        if not isinstance(mapping_entry_gui_format, dict):
            # print(f"Config Warning (translate): Mapping entry for '{action_name}' is not a dict. Skipping: {mapping_entry_gui_format}")
            continue

        event_type = mapping_entry_gui_format.get("event_type")
        details = mapping_entry_gui_format.get("details")

        if not event_type or not isinstance(details, dict):
            # print(f"Config Warning (translate): Missing event_type or details for '{action_name}'. Skipping: {mapping_entry_gui_format}")
            continue

        runtime_entry: Dict[str, Any] = {"type": event_type}
        valid_entry = False

        if event_type == "button":
            button_id = details.get("button_id")
            if button_id is not None:
                runtime_entry["id"] = int(button_id)
                valid_entry = True
        elif event_type == "axis":
            axis_id = details.get("axis_id")
            direction = details.get("direction")
            threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_id is not None and direction is not None:
                runtime_entry["id"] = int(axis_id)
                runtime_entry["value"] = int(direction)
                runtime_entry["threshold"] = float(threshold)
                valid_entry = True
        elif event_type == "hat":
            hat_id = details.get("hat_id")
            value = details.get("value") # Should be a list like [x, y] from GUI
            if hat_id is not None and isinstance(value, list) and len(value) == 2:
                runtime_entry["id"] = int(hat_id)
                runtime_entry["value"] = tuple(map(int, value)) # Convert to tuple of ints for runtime
                valid_entry = True
        
        if valid_entry:
            runtime_mappings[action_name] = runtime_entry
        # else:
            # print(f"Config Warning (translate): Could not form valid runtime entry for '{action_name}'. Details: {details}")

    return runtime_mappings


def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    """Returns a list of (display_name, internal_id_string, guid_string, pygame_index) for available joysticks."""
    devices = []
    if not _joystick_initialized_globally:
        print("Config Warn: get_available_joystick_names called but joystick system not init.")
        return devices

    for i in range(_detected_joystick_count_global):
        joy_object = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_name = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"Unknown Joystick {i}"
        guid_str: Optional[str] = None

        if joy_object:
            original_init_state = joy_object.get_init()
            try:
                if not original_init_state: joy_object.init()
                guid_str = joy_object.get_guid()
                if guid_str == "00000000000000000000000000000000": # Generic GUID
                    # print(f"Config Info: Joystick {i} ('{joy_name}') has a generic GUID. May rely on index for uniqueness if multiple such devices exist.")
                    pass # guid_str remains the generic one, or you could set to None/index-based
            except pygame.error as e_guid:
                print(f"Config Warning: Error processing GUID for joystick {i} ('{joy_name}'): {e_guid}")
            finally:
                if not original_init_state and joy_object.get_init(): joy_object.quit()
        else:
            print(f"Config Info: Skipping GUID for joystick {i} ('{joy_name}') as object is not available (was errored).")

        # For player device assignment, an ID like "joystick_pygame_INDEX" is often simpler
        # The GUI uses this for the QComboBox data.
        internal_id_for_assignment = f"joystick_pygame_{i}" 
        display_name_for_combo = f"Joy {i}: {joy_name.split(' (GUID:')[0]}" # Cleaner name for combo
        pygame_device_index = i
        
        devices.append((display_name_for_combo, internal_id_for_assignment, guid_str, pygame_device_index))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    return _joystick_objects_global

def save_config():
    # Collect current settings from global vars for P1-P4
    player_settings_to_save = {}
    for i in range(1, 5): # P1 to P4
        player_settings_to_save[f"player{i}_settings"] = {
            "input_device": globals().get(f"CURRENT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID),
            "keyboard_enabled": globals().get(f"P{i}_KEYBOARD_ENABLED", False),
            "controller_enabled": globals().get(f"P{i}_CONTROLLER_ENABLED", False),
        }

    data_to_save = {
        "config_version": "2.3.3",
        **player_settings_to_save, # Unpack player1_settings, player2_settings etc.
        "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS # This is already GUID-keyed GUI format
    }
    try:
        subdir_path = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(subdir_path):
            os.makedirs(subdir_path)
            print(f"Config: Created directory {subdir_path}")
            
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        # After saving, ensure the internal runtime maps are also updated for current session
        update_player_mappings_from_config() # This will re-translate based on new settings
        return True
    except IOError as e:
        print(f"Config Error: Saving settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}")
        return False

def load_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS # This will hold the raw GUID-keyed GUI format maps

    init_pygame_and_joystick_globally(force_rescan=True) # Crucial: rescan joysticks BEFORE loading config
    
    raw_config_data = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f:
                raw_config_data = json.load(f)
            print(f"Config: Successfully loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults."); raw_config_data = {}
    else:
        print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults/auto-detect.")

    # Load player settings (P1-P4)
    for i in range(1, 5):
        p_settings = raw_config_data.get(f"player{i}_settings", {})
        globals()[f"CURRENT_P{i}_INPUT_DEVICE"] = p_settings.get("input_device", globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID))
        globals()[f"P{i}_KEYBOARD_ENABLED"] = p_settings.get("keyboard_enabled", globals().get(f"DEFAULT_P{i}_KEYBOARD_ENABLED", False))
        globals()[f"P{i}_CONTROLLER_ENABLED"] = p_settings.get("controller_enabled", globals().get(f"DEFAULT_P{i}_CONTROLLER_ENABLED", False))

    # This loads the GUID-keyed structure from JSON into the global var
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings", {})
    print("--- LOAD_CONFIG DEBUG ---")
    print(f"LOADED_PYGAME_JOYSTICK_MAPPINGS (GUID-keyed GUI format from JSON):")
    print(json.dumps(LOADED_PYGAME_JOYSTICK_MAPPINGS, indent=2))
    print("--- END LOAD_CONFIG DEBUG ---")

    if not raw_config_data: # File not found or parsing error
        print("Config: No valid config file, attempting auto-assignment.")
        # Simplified auto-assignment for P1/P2
        if _detected_joystick_count_global > 0:
            globals()["CURRENT_P1_INPUT_DEVICE"] = f"joystick_pygame_0"
            globals()["P1_CONTROLLER_ENABLED"] = True; globals()["P1_KEYBOARD_ENABLED"] = True # Default to allowing keyboard as well
            print(f"Config Auto-Assign: P1 to joystick_pygame_0.")
            if _detected_joystick_count_global > 1:
                globals()["CURRENT_P2_INPUT_DEVICE"] = f"joystick_pygame_1"
                globals()["P2_CONTROLLER_ENABLED"] = True; globals()["P2_KEYBOARD_ENABLED"] = True
                print(f"Config Auto-Assign: P2 to joystick_pygame_1.")
            else:
                globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE
                print(f"Config Auto-Assign: P2 to default ({DEFAULT_P2_INPUT_DEVICE}).")
        else: # No joysticks
            globals()["CURRENT_P1_INPUT_DEVICE"] = DEFAULT_P1_INPUT_DEVICE
            globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE
            print("Config Auto-Assign: No joysticks. P1/P2 to default keyboards.")

    # Validate assigned joystick devices and handle conflicts
    available_joy_device_ids = [f"joystick_pygame_{i}" for i in range(_detected_joystick_count_global)]
    assigned_devices = {} # To check for duplicates

    for i in range(1, 5): # P1-P4
        current_device_var = f"CURRENT_P{i}_INPUT_DEVICE"
        default_device_val = globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        current_device_val = globals().get(current_device_var, default_device_val)

        if current_device_val.startswith("joystick_pygame_"):
            if current_device_val not in available_joy_device_ids:
                print(f"Config Warn: P{i}'s joystick '{current_device_val}' not found. Reverting to {default_device_val}.")
                globals()[current_device_var] = default_device_val
                current_device_val = default_device_val # Update for duplicate check
            
            if current_device_val != UNASSIGNED_DEVICE_ID:
                if current_device_val in assigned_devices:
                    colliding_player = assigned_devices[current_device_val]
                    print(f"Config Warn: P{i} and P{colliding_player} assigned same joystick '{current_device_val}'. Reverting P{i} to {default_device_val}.")
                    globals()[current_device_var] = default_device_val
                else:
                    assigned_devices[current_device_val] = i
        elif current_device_val.startswith("keyboard_"):
            if current_device_val != UNASSIGNED_DEVICE_ID: # Assuming "unassigned_keyboard" is a valid distinct ID
                if current_device_val in assigned_devices and current_device_val != "unassigned_keyboard": # Allow multiple "unassigned_keyboard"
                    colliding_player = assigned_devices[current_device_val]
                    print(f"Config Warn: P{i} and P{colliding_player} assigned same keyboard layout '{current_device_val}'. Consider changing one.")
                    # Not automatically reverting keyboard, as it's less critical than joystick conflict
                else:
                     assigned_devices[current_device_val] = i


    update_player_mappings_from_config() # This translates for P1-P4 based on final CURRENT_P*_INPUT_DEVICE
    
    for i in range(1, 5):
        print(f"Config Loaded: P{i} Dev='{globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}', KbdEn={globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'P{i}_CONTROLLER_ENABLED')}")
    return True


def update_player_mappings_from_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS # GUID-keyed GUI format maps

    default_runtime_joystick_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy() # Use generic if specific fails
    print("\n--- CONFIG: Updating Player Mappings (Runtime) ---")

    for i in range(1, 5): # P1 to P4
        player_id_str = f"P{i}"
        current_device_key = f"CURRENT_{player_id_str}_INPUT_DEVICE"
        player_mappings_key = f"{player_id_str}_MAPPINGS" # e.g., P1_MAPPINGS

        current_input_device = globals().get(current_device_key)
        print(f"{player_id_str}: Current Device = '{current_input_device}'")

        if current_input_device == "keyboard_p1":
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
            print(f"{player_id_str}: Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        elif current_input_device == "keyboard_p2": # Assuming you might have a P2 keyboard layout
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
            print(f"{player_id_str}: Using DEFAULT_KEYBOARD_P2_MAPPINGS.")
        elif current_input_device and current_input_device.startswith("joystick_pygame_"):
            target_guid_for_player = None
            try:
                joystick_idx = int(current_input_device.split('_')[-1])
                available_joys = get_available_joystick_names_with_indices_and_guids()
                for _, _, guid, idx_from_func in available_joys:
                    if idx_from_func == joystick_idx:
                        target_guid_for_player = guid
                        break
                
                if target_guid_for_player and target_guid_for_player in LOADED_PYGAME_JOYSTICK_MAPPINGS:
                    gui_map_for_this_controller = LOADED_PYGAME_JOYSTICK_MAPPINGS[target_guid_for_player]
                    print(f"{player_id_str}: Found GUI map for GUID '{target_guid_for_player}'. Translating...")
                    
                    runtime_map = _translate_gui_map_to_runtime(gui_map_for_this_controller)
                    
                    if runtime_map:
                        globals()[player_mappings_key] = runtime_map
                        print(f"{player_id_str}: Successfully translated mappings for GUID '{target_guid_for_player}'.")
                    else:
                        globals()[player_mappings_key] = default_runtime_joystick_map
                        print(f"{player_id_str}: Translation FAILED for GUID '{target_guid_for_player}'. Using default generic joystick map.")
                else:
                    globals()[player_mappings_key] = default_runtime_joystick_map
                    print(f"{player_id_str}: No specific map in JSON for GUID '{target_guid_for_player}' (or GUID not found for index {joystick_idx}). Using default generic joystick map.")
            except ValueError:
                globals()[player_mappings_key] = default_runtime_joystick_map
                print(f"{player_id_str} Error: Could not parse joystick index from '{current_input_device}'. Using default generic map.")
            except Exception as e:
                globals()[player_mappings_key] = default_runtime_joystick_map
                print(f"{player_id_str} Error during joystick map processing for '{current_input_device}': {e}. Using default generic map.")
        elif current_input_device == UNASSIGNED_DEVICE_ID:
            globals()[player_mappings_key] = {} # No mappings for unassigned
            print(f"{player_id_str}: Device is '{UNASSIGNED_DEVICE_ID}'. No mappings assigned.")
        else: # Fallback for unknown or other keyboard layouts (e.g., "unassigned_keyboard")
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P1_MAPPINGS.copy() # Default to P1 kbd
            print(f"{player_id_str}: Device '{current_input_device}' unrecognized or unassigned kbd. Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        
        # print(f"{player_id_str}: Final Mappings (sample 'jump'): {globals()[player_mappings_key].get('jump', 'Not set')}")
    print("--- CONFIG: Finished Updating Player Mappings ---\n")


if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    # Ensure Pygame is freshly initialized for this test context
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
        _pygame_initialized_globally = False; _joystick_initialized_globally = False
        print("Config Test: Pygame explicitly quit for fresh re-initialization.")
    
    init_pygame_and_joystick_globally(force_rescan=True)
    
    print("\nTesting get_available_joystick_names_with_indices_and_guids():")
    joystick_data_list = get_available_joystick_names_with_indices_and_guids()
    if joystick_data_list:
        for i, data_tuple_item in enumerate(joystick_data_list):
            print(f"  Joystick {i}: Name='{data_tuple_item[0]}', InternalID='{data_tuple_item[1]}', GUID='{data_tuple_item[2]}', PygameIdx={data_tuple_item[3]}")
    else:
        print("  No joysticks detected or an error occurred during joystick detection.")

    # Simulate loading config (this will call init_pygame_and_joystick_globally again, which is fine)
    print("\n--- Simulating load_config() ---")
    load_config()
    print(f"\n--- After test load_config(): ---")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i in range(1, 3): # Just P1, P2 for concise test output
        print(f"  P{i} Device: {globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}, KbdEn: {globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn: {globals().get(f'P{i}_CONTROLLER_ENABLED')}")
        print(f"  P{i} Mappings sample (jump): {globals().get(f'P{i}_MAPPINGS',{}).get('jump', 'Not Found / Not Mapped')}")
        print(f"  P{i} Mappings sample (attack1): {globals().get(f'P{i}_MAPPINGS',{}).get('attack1', 'Not Found / Not Mapped')}")


    # Test saving (optional, be careful not to overwrite good config unless intended)
    # print("\n--- Simulating save_config() ---")
    # save_config()

    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("\n--- config.py direct test finished ---")