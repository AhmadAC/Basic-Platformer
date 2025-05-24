# config.py
# -*- coding: utf-8 -*-
###############################33
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1-P4.
"""
# version 2.3.6 (4-player support, refined auto-assignment)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame
from PySide6.QtCore import Qt

# --- Global Pygame State Variables ---
_pygame_initialized_globally = False
_joystick_initialized_globally = False
_detected_joystick_count_global = 0
_detected_joystick_names_global: List[str] = []
_joystick_objects_global: List[Optional[pygame.joystick.Joystick]] = []

def init_pygame_and_joystick_globally(force_rescan=False):
    global _pygame_initialized_globally, _joystick_initialized_globally, _detected_joystick_count_global
    global _detected_joystick_names_global, _joystick_objects_global
    if not _pygame_initialized_globally:
        try: pygame.init(); _pygame_initialized_globally = True; print("Config: Pygame globally initialized.")
        except Exception as e: print(f"Config CRITICAL: Pygame global init failed: {e}"); return
    if not _joystick_initialized_globally:
        try: pygame.joystick.init(); _joystick_initialized_globally = True; print("Config: Pygame Joystick globally initialized.")
        except Exception as e: print(f"Config CRITICAL: Pygame Joystick global init failed: {e}"); return
    
    current_count = pygame.joystick.get_count()
    if force_rescan or current_count != _detected_joystick_count_global:
        print(f"Config: Joystick scan. Force:{force_rescan}, Old:{_detected_joystick_count_global}, New:{current_count}")
        _detected_joystick_count_global = current_count
        _detected_joystick_names_global = []
        
        # Properly quit old joystick objects before re-populating
        for old_joy in _joystick_objects_global:
            if old_joy and old_joy.get_init(): # Only quit if initialized
                try: old_joy.quit()
                except pygame.error: pass # Ignore errors if already quit or other issue
        _joystick_objects_global = [] # Clear the list

        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i)
                # No need to joy.init() here, just get name. AppCore/InputManager will init for use.
                _detected_joystick_names_global.append(joy.get_name())
                _joystick_objects_global.append(joy)
            except pygame.error as e:
                print(f"Config Warn: Error accessing joystick {i}: {e}")
                _detected_joystick_names_global.append(f"ErrorJoystick{i}")
                _joystick_objects_global.append(None)
        print(f"Config: Scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally() # Initial scan

# --- File Paths ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONTROLLER_SETTINGS_SUBDIR, MAPPINGS_AND_DEVICE_CHOICES_FILENAME)
print(f"DEBUG config.py: Expecting JSON at: {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")

# --- Device IDs and Defaults ---
UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = True
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = True; DEFAULT_P2_CONTROLLER_ENABLED = True
DEFAULT_P3_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
DEFAULT_P4_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False

# --- Current Player Settings (will be loaded/saved) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED

# --- Keyboard Device Info (expand if P3/P4 get unique layouts) ---
KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", UNASSIGNED_DEVICE_ID] # "unassigned_keyboard" was there, but "unassigned" is general
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"] # Matched with IDs

# --- General Game and Mapping Config ---
AXIS_THRESHOLD_DEFAULT = 0.7
GAME_ACTIONS = [
    "left", "right", "up", "down", "jump", "crouch",
    "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]
# This map helps if action names from external sources (like editor) differ from internal game action names.
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP_ACTION": "jump", "PRIMARY_ATTACK": "attack1",
    # Example internal mappings if Qt key names were used as external keys (these are more for documentation now)
    "W": "up", "A": "left", "S": "down", "D": "right", "SPACE": "jump", "V": "attack1", "B": "attack2", "SHIFT": "dash"
}

# --- Default Keyboard Mappings (Qt.Key format) ---
DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4,
    "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7,
    "reset": Qt.Key.Key_Q, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K, "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_8, "projectile2": Qt.Key.Key_9, "projectile3": Qt.Key.Key_0, "projectile4": Qt.Key.Key_Minus,
    "projectile5": Qt.Key.Key_Equal, "projectile6": Qt.Key.Key_BracketLeft, "projectile7": Qt.Key.Key_BracketRight,
    "reset": Qt.Key.Key_Period, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete,
    "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End
}
# --- Default Joystick Mapping (Runtime Format - used if no specific map for a GUID) ---
DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Commonly left stick Y
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, # Often A (Xbox) or X (PS)
    "crouch": {"type": "button", "id": 1}, # Often B (Xbox) or O (PS)
    "attack1": {"type": "button", "id": 2}, # Often X (Xbox) or Square (PS)
    "attack2": {"type": "button", "id": 3}, # Often Y (Xbox) or Triangle (PS)
    "dash": {"type": "button", "id": 5}, # Often RB (Xbox) or R1 (PS)
    "roll": {"type": "button", "id": 4}, # Often LB (Xbox) or L1 (PS)
    "interact": {"type": "button", "id": 10}, # Example: Right Stick Press
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, # Hat Up
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)}, # Hat Right
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, # Hat Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)}, # Hat Left
    "reset": {"type": "button", "id": 6}, # Often Back/Select
    "pause": {"type": "button", "id": 7}, # Often Start
    "menu_confirm": {"type": "button", "id": 0},
    "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, # D-pad Up
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)}, # D-pad Down
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, # D-pad Left
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)}  # D-pad Right
}

# --- Loaded Joystick Mappings (GUID-keyed, GUI storage format) ---
LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}

# --- Per-Player Runtime Mappings ---
P1_MAPPINGS: Dict[str, Any] = {}; P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}; P4_MAPPINGS: Dict[str, Any] = {}


def _translate_gui_map_to_runtime(gui_map_for_single_controller: Dict[str, Any]) -> Dict[str, Any]:
    """Translates a single controller's GUI-format mapping to runtime format."""
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(gui_map_for_single_controller, dict):
        print("Config Error (_translate): Input gui_map_for_single_controller is not a dict.")
        return {}

    for action_name, mapping_entry_gui_format in gui_map_for_single_controller.items():
        if action_name not in GAME_ACTIONS:
            # print(f"Config Info (_translate): Skipping unknown action '{action_name}' during translation.")
            continue
        if not isinstance(mapping_entry_gui_format, dict):
            # print(f"Config Warn (_translate): Mapping entry for '{action_name}' is not a dict, skipping.")
            continue

        event_type = mapping_entry_gui_format.get("event_type")
        details = mapping_entry_gui_format.get("details")

        if not event_type or not isinstance(details, dict):
            # print(f"Config Warn (_translate): Missing 'event_type' or 'details' for action '{action_name}'.")
            continue

        runtime_entry: Dict[str, Any] = {"type": event_type}
        valid_entry = False
        try:
            if event_type == "button":
                button_id = details.get("button_id")
                if button_id is not None:
                    runtime_entry["id"] = int(button_id); valid_entry = True
            elif event_type == "axis":
                axis_id = details.get("axis_id")
                direction = details.get("direction")
                threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
                if axis_id is not None and direction is not None:
                    runtime_entry["id"] = int(axis_id)
                    runtime_entry["value"] = int(direction) # This should be -1 or 1
                    runtime_entry["threshold"] = float(threshold)
                    valid_entry = True
            elif event_type == "hat":
                hat_id = details.get("hat_id")
                value = details.get("value") # Expects a list like [0, 1] from GUI
                if hat_id is not None and isinstance(value, list) and len(value) == 2:
                    runtime_entry["id"] = int(hat_id)
                    runtime_entry["value"] = tuple(map(int, value)) # Convert to tuple for runtime
                    valid_entry = True
        except (ValueError, TypeError) as e:
            print(f"Config Error (_translate): Invalid data for action '{action_name}', type '{event_type}': {details} - Error: {e}")
        
        if valid_entry:
            runtime_mappings[action_name] = runtime_entry
        # else:
            # print(f"Config Warn (_translate): Could not create valid runtime entry for action '{action_name}' with details {details}.")

    # If debug prints were added inside this function for GUI map, they should be removed or conditional.
    # print(f"DEBUG _translate_gui_map_to_runtime: OUTPUT_RUNTIME_MAP for one controller = {json.dumps(runtime_mappings, indent=2)}")
    return runtime_mappings

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    """
    Returns a list of tuples: (display_name, internal_id, guid_string, pygame_index).
    Pygame joystick objects are temporarily initialized if needed to get GUID.
    """
    devices: List[Tuple[str, str, Optional[str], int]] = []
    if not _joystick_initialized_globally:
        print("Config Warn: get_available_joystick_names_with_indices_and_guids called but joystick system not init.")
        return devices

    for i in range(_detected_joystick_count_global):
        # Get the joystick object from our globally managed list
        joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_name = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"UnknownJoystick{i}"
        
        guid_str: Optional[str] = None
        if joy_obj: # If we have a pre-existing joystick object
            was_originally_init = joy_obj.get_init()
            try:
                if not was_originally_init: joy_obj.init() # Init only if not already
                guid_str = joy_obj.get_guid()
            except pygame.error as e_guid:
                print(f"Config Warn: Error getting GUID for joystick {i} ('{joy_name}'): {e_guid}")
            finally:
                if not was_originally_init and joy_obj.get_init(): # If we init'd it, quit it
                    joy_obj.quit()
        else: # Should not happen if _joystick_objects_global is synced
            print(f"Config Warn: No joystick object at index {i} in _joystick_objects_global while expected.")

        # Construct IDs and display names
        internal_id_for_assignment = f"joystick_pygame_{i}" # Used by AppCore/InputManager to pick by index
        display_name = f"Joy {i}: {joy_name.split(' (GUID:')[0]}" # Cleaner name for UI

        devices.append((display_name, internal_id_for_assignment, guid_str, i))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    """Returns the list of globally managed Pygame Joystick objects."""
    return _joystick_objects_global

def save_config() -> bool:
    """Saves current player device choices and all joystick mappings to JSON."""
    player_settings: Dict[str, Any] = {}
    for i in range(1, 5): # P1 to P4
        player_num_str = f"P{i}"
        player_settings[f"player{i}_settings"] = {
            "input_device": globals().get(f"CURRENT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID),
            "keyboard_enabled": globals().get(f"{player_num_str}_KEYBOARD_ENABLED", False),
            "controller_enabled": globals().get(f"{player_num_str}_CONTROLLER_ENABLED", False)
        }

    data_to_save = {
        "config_version": "2.3.6", # Update version string
        **player_settings,
        "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS # This is GUID-keyed, GUI storage format
    }

    try:
        settings_subdir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(settings_subdir):
            os.makedirs(settings_subdir)
            print(f"Config: Created directory {settings_subdir}")
        
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        update_player_mappings_from_config() # Refresh runtime maps after saving
        return True
    except IOError as e:
        print(f"Config Error: Could not save settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}")
        return False

def load_config() -> bool:
    """Loads player device choices and joystick mappings from JSON. Handles defaults and auto-assignment."""
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    
    # Ensure Pygame and joysticks are fresh for this load operation
    init_pygame_and_joystick_globally(force_rescan=True)
    
    raw_data_from_file: Dict[str, Any] = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f:
                raw_data_from_file = json.load(f)
            print(f"Config: Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Failed to load or parse {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults.")
            raw_data_from_file = {} # Ensure it's an empty dict on error
    else:
        print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults and auto-assignment.")
        raw_data_from_file = {} # Ensure it's an empty dict if file not found

    # --- Load Player Device Choices and Enabled Flags (P1-P4) ---
    for i in range(1, 5): # Iterate for P1, P2, P3, P4
        player_num_str = f"P{i}"
        player_settings_from_file = raw_data_from_file.get(f"player{i}_settings", {}) # Get settings for this player, or empty dict

        # Set CURRENT_Px_INPUT_DEVICE
        default_input_device_val = globals().get(f"DEFAULT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        loaded_input_device = player_settings_from_file.get("input_device", default_input_device_val)
        globals()[f"CURRENT_{player_num_str}_INPUT_DEVICE"] = loaded_input_device
        
        # Set Px_KEYBOARD_ENABLED and Px_CONTROLLER_ENABLED
        # These flags indicate if a player *can* use keyboard/controller, not necessarily their primary device.
        # If JSON has explicit values, use them. Otherwise, derive smartly.
        kbd_enabled_from_file = player_settings_from_file.get("keyboard_enabled", None)
        ctrl_enabled_from_file = player_settings_from_file.get("controller_enabled", None)

        default_kbd_enabled_val = globals().get(f"DEFAULT_{player_num_str}_KEYBOARD_ENABLED", False)
        default_ctrl_enabled_val = globals().get(f"DEFAULT_{player_num_str}_CONTROLLER_ENABLED", False)

        if kbd_enabled_from_file is not None:
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = kbd_enabled_from_file
        else: # Not in file, derive from current device or default
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = loaded_input_device.startswith("keyboard_") or default_kbd_enabled_val

        if ctrl_enabled_from_file is not None:
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = ctrl_enabled_from_file
        else: # Not in file, derive
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = loaded_input_device.startswith("joystick_pygame_") or default_ctrl_enabled_val

    # Load Joystick Mappings (GUID-keyed, GUI storage format)
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_data_from_file.get("joystick_mappings", {})
    print("--- LOAD_CONFIG DEBUG (Raw Loaded Mappings) ---")
    print(f"LOADED_PYGAME_JOYSTICK_MAPPINGS (GUID-keyed GUI format):")
    print(json.dumps(LOADED_PYGAME_JOYSTICK_MAPPINGS, indent=2, default=lambda o: f"<not serializable: {type(o).__name__}>"))
    print("--- END LOAD_CONFIG DEBUG ---")

    # --- Auto-assignment if config file was missing/empty (no player settings loaded) ---
    if not raw_data_from_file.get("player1_settings"): # Check if P1 settings are missing as a proxy for empty config
        print("Config: No player settings in JSON or file was empty/new. Performing auto-assignment for P1-P4.")
        
        # Default assignments (can be overridden by joystick availability)
        auto_assignments = {
            "P1": {"device": DEFAULT_P1_INPUT_DEVICE, "kbd_en": DEFAULT_P1_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P1_CONTROLLER_ENABLED},
            "P2": {"device": DEFAULT_P2_INPUT_DEVICE, "kbd_en": DEFAULT_P2_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P2_CONTROLLER_ENABLED},
            "P3": {"device": DEFAULT_P3_INPUT_DEVICE, "kbd_en": DEFAULT_P3_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P3_CONTROLLER_ENABLED},
            "P4": {"device": DEFAULT_P4_INPUT_DEVICE, "kbd_en": DEFAULT_P4_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P4_CONTROLLER_ENABLED}
        }
        
        available_joy_indices = list(range(_detected_joystick_count_global))
        
        # Assign Joysticks first
        for p_idx_plus_1 in range(1, 5): # P1, P2, P3, P4
            player_num_str = f"P{p_idx_plus_1}"
            if available_joy_indices:
                assigned_joy_idx = available_joy_indices.pop(0) # Take the next available joystick
                auto_assignments[player_num_str]["device"] = f"joystick_pygame_{assigned_joy_idx}"
                auto_assignments[player_num_str]["ctrl_en"] = True
                # Keep keyboard enabled true by default for joystick players for flexibility, unless it's P3/P4 default
                auto_assignments[player_num_str]["kbd_en"] = globals().get(f"DEFAULT_{player_num_str}_KEYBOARD_ENABLED", False) if p_idx_plus_1 > 2 else True
            # If no more joysticks, P1/P2 default to keyboard, P3/P4 default to unassigned
            elif p_idx_plus_1 == 1: # P1 defaults to keyboard_p1 if no joysticks
                auto_assignments[player_num_str]["device"] = DEFAULT_P1_INPUT_DEVICE
                auto_assignments[player_num_str]["kbd_en"] = True; auto_assignments[player_num_str]["ctrl_en"] = False
            elif p_idx_plus_1 == 2: # P2 defaults to keyboard_p2 if no joysticks
                auto_assignments[player_num_str]["device"] = DEFAULT_P2_INPUT_DEVICE
                auto_assignments[player_num_str]["kbd_en"] = True; auto_assignments[player_num_str]["ctrl_en"] = False
            # P3/P4 will keep their UNASSIGNED_DEVICE_ID default if no joysticks left for them
        
        # Apply auto_assignments
        for i in range(1, 5):
            player_num_str = f"P{i}"
            globals()[f"CURRENT_{player_num_str}_INPUT_DEVICE"] = auto_assignments[player_num_str]["device"]
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = auto_assignments[player_num_str]["kbd_en"]
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = auto_assignments[player_num_str]["ctrl_en"]

    # --- Validate joystick assignments (ensure no duplicates, joystick exists) ---
    # This is important if loading from a file where joystick indices might be stale.
    available_pygame_joy_device_ids = [f"joystick_pygame_{j}" for j in range(_detected_joystick_count_global)]
    assigned_devices_map: Dict[str, int] = {} # device_id -> player_number (1-4)

    for i in range(1, 5): # P1 to P4
        player_num_str = f"P{i}"
        current_device_var_name = f"CURRENT_{player_num_str}_INPUT_DEVICE"
        default_device_for_player = globals().get(f"DEFAULT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        
        current_assigned_device_val = globals().get(current_device_var_name, default_device_for_player)

        if current_assigned_device_val.startswith("joystick_pygame_"):
            if current_assigned_device_val not in available_pygame_joy_device_ids:
                # Assigned joystick is not currently detected
                print(f"Config Warn: {player_num_str}'s assigned joystick '{current_assigned_device_val}' not detected. Reverting to default '{default_device_for_player}'.")
                globals()[current_device_var_name] = default_device_for_player
                current_assigned_device_val = default_device_for_player
            
            if current_assigned_device_val != UNASSIGNED_DEVICE_ID:
                if current_assigned_device_val in assigned_devices_map:
                    # This joystick is already assigned to another player
                    other_player_num = assigned_devices_map[current_assigned_device_val]
                    print(f"Config Warn: {player_num_str} and P{other_player_num} assigned to same joystick '{current_assigned_device_val}'. Reverting {player_num_str} to default.")
                    globals()[current_device_var_name] = default_device_for_player
                else:
                    assigned_devices_map[current_assigned_device_val] = i # Assign it
        
        elif current_assigned_device_val.startswith("keyboard_") and current_assigned_device_val != UNASSIGNED_DEVICE_ID :
            # Allow multiple players on same keyboard layout, but log if it happens for different players
            if current_assigned_device_val in assigned_devices_map:
                other_player_num = assigned_devices_map[current_assigned_device_val]
                # This is not necessarily an error, just an observation.
                # print(f"Config Info: {player_num_str} and P{other_player_num} sharing keyboard layout '{current_assigned_device_val}'.")
            else:
                 assigned_devices_map[current_assigned_device_val] = i

    # Update runtime mappings based on the (potentially modified) loaded config
    update_player_mappings_from_config()
    
    # Final print of loaded config for verification
    for i in range(1, 5):
        player_num_str = f"P{i}"
        print(f"Config Loaded Final: {player_num_str} Dev='{globals().get(f'CURRENT_{player_num_str}_INPUT_DEVICE')}', "
              f"KbdEn={globals().get(f'{player_num_str}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'{player_num_str}_CONTROLLER_ENABLED')}")
    return True

def update_player_mappings_from_config():
    """
    Updates the P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS global variables
    based on the current device assignments and loaded joystick mappings.
    Keyboard mappings are taken from defaults directly.
    Joystick mappings are translated from LOADED_PYGAME_JOYSTICK_MAPPINGS (GUI format) to runtime format.
    """
    global P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS, LOADED_PYGAME_JOYSTICK_MAPPINGS

    default_runtime_joystick_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy()
    print("\n--- CONFIG: Updating Player Runtime Mappings ---")
    
    available_joys_data = get_available_joystick_names_with_indices_and_guids() # List of (display_name, internal_id, guid, pygame_idx)

    for i in range(1, 5): # P1 to P4
        player_id_str = f"P{i}"
        current_input_device_for_player = globals().get(f"CURRENT_{player_id_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        player_mappings_var_name = f"{player_id_str}_MAPPINGS"
        
        print(f"  {player_id_str}: Assigned Device = '{current_input_device_for_player}'")
        
        target_runtime_map_for_player: Dict[str, Any] = {} # Default to empty map

        if current_input_device_for_player == "keyboard_p1":
            target_runtime_map_for_player = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
            print(f"  {player_id_str}: Using DEFAULT_KEYBOARD_P1_MAPPINGS (Qt.Key format).")
        elif current_input_device_for_player == "keyboard_p2":
            target_runtime_map_for_player = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
            print(f"  {player_id_str}: Using DEFAULT_KEYBOARD_P2_MAPPINGS (Qt.Key format).")
        elif current_input_device_for_player and current_input_device_for_player.startswith("joystick_pygame_"):
            assigned_pygame_idx_str = current_input_device_for_player.split('_')[-1]
            target_guid_for_player: Optional[str] = None
            assigned_pygame_idx: Optional[int] = None
            try:
                assigned_pygame_idx = int(assigned_pygame_idx_str)
                # Find the GUID for this Pygame index from the available_joys_data
                for _, _, guid, py_idx in available_joys_data:
                    if py_idx == assigned_pygame_idx:
                        target_guid_for_player = guid
                        break
            except (ValueError, IndexError):
                print(f"  {player_id_str} Error: Could not parse Pygame index from '{current_input_device_for_player}'.")
            
            if target_guid_for_player and target_guid_for_player in LOADED_PYGAME_JOYSTICK_MAPPINGS:
                gui_format_map_for_guid = LOADED_PYGAME_JOYSTICK_MAPPINGS[target_guid_for_player]
                # print(f"  {player_id_str}: Found GUI-format map for GUID '{target_guid_for_player}'. Translating...")
                # print(f"  {player_id_str}: GUI map for translation: {json.dumps(gui_format_map_for_guid, indent=2)}")
                
                runtime_map_translated = _translate_gui_map_to_runtime(gui_format_map_for_guid)
                if runtime_map_translated:
                    target_runtime_map_for_player = runtime_map_translated
                    print(f"  {player_id_str}: Successfully translated mappings for GUID '{target_guid_for_player}'.")
                else:
                    target_runtime_map_for_player = default_runtime_joystick_map.copy()
                    print(f"  {player_id_str}: Translation FAILED for GUID '{target_guid_for_player}'. Using default generic joystick map.")
            else:
                target_runtime_map_for_player = default_runtime_joystick_map.copy()
                no_map_reason = f"No specific map found for GUID '{target_guid_for_player}'" if target_guid_for_player else \
                                f"No GUID found for Pygame index {assigned_pygame_idx}" if assigned_pygame_idx is not None else \
                                "Invalid joystick assignment"
                print(f"  {player_id_str}: {no_map_reason}. Using default generic joystick map.")
        
        elif current_input_device_for_player == UNASSIGNED_DEVICE_ID:
            print(f"  {player_id_str}: Device is '{UNASSIGNED_DEVICE_ID}'. No mappings assigned.")
            target_runtime_map_for_player = {} # Empty map for unassigned
        
        else: # Fallback for unknown device types (should ideally not happen)
            target_runtime_map_for_player = {} # Default to empty if truly unknown
            print(f"  {player_id_str}: Device '{current_input_device_for_player}' is unrecognized. Assigning empty map.")

        globals()[player_mappings_var_name] = target_runtime_map_for_player
        # Debug print a couple of key mappings for verification
        jump_map_info = target_runtime_map_for_player.get('jump', 'N/A')
        attack_map_info = target_runtime_map_for_player.get('attack1', 'N/A')
        print(f"  {player_id_str}: Final Runtime Mappings -> Jump: {jump_map_info}, Attack1: {attack_map_info}")
    
    print("--- CONFIG: Finished Updating Player Runtime Mappings ---\n")

# --- Initial Load on Script Import ---
# This ensures config is loaded once when the module is first imported.
# Subsequent explicit calls to load_config() can refresh it.
if __name__ != "__main__": # Avoid loading if script is run directly for testing
    load_config()


# --- Standalone Test Block ---
if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    
    # Reset Pygame if it was initialized by module-level call, to simulate clean test
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            pygame.joystick.quit()
        pygame.quit()
        _pygame_initialized_globally = False
        _joystick_initialized_globally = False
        print("  (Standalone Test: Pygame system reset for fresh init)")
    
    init_pygame_and_joystick_globally(force_rescan=True) # Test fresh init

    print("\nTesting get_available_joystick_names_with_indices_and_guids():")
    joy_data_list = get_available_joystick_names_with_indices_and_guids()
    if joy_data_list:
        for i, joy_data_tuple in enumerate(joy_data_list):
            print(f"  Joy {i}: Name='{joy_data_tuple[0]}', AssignID='{joy_data_tuple[1]}', GUID='{joy_data_tuple[2]}', PyIdx={joy_data_tuple[3]}")
    else:
        print("  No joysticks detected by Pygame.")

    print("\n--- Simulating load_config() ---")
    load_config() # This will print its own "Final Loaded Config" lines

    print(f"\n--- After test load_config(): ---")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i in range(1, 5): # P1, P2, P3, P4
        player_num_str = f"P{i}"
        print(f"  {player_num_str} Dev: {globals().get(f'CURRENT_{player_num_str}_INPUT_DEVICE')}, "
              f"KbdEn: {globals().get(f'{player_num_str}_KEYBOARD_ENABLED')}, "
              f"CtrlEn: {globals().get(f'{player_num_str}_CONTROLLER_ENABLED')}")
        
        current_player_mappings = globals().get(f'{player_num_str}_MAPPINGS', {})
        jump_map_info = current_player_mappings.get('jump', 'N/A')
        attack_map_info = current_player_mappings.get('attack1', 'N/A')
        left_map_info = current_player_mappings.get('left', 'N/A')
        print(f"  {player_num_str} Runtime Maps -> Jump: {jump_map_info}, Attack1: {attack_map_info}, Left: {left_map_info}")

    # Clean up Pygame at the end of the test
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            pygame.joystick.quit()
        pygame.quit()
        print("  (Standalone Test: Pygame quit at end of test)")
    
    print("\n--- config.py direct test finished ---")