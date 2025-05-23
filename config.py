# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1-P4.
"""
# version 2.3.4 (Enhanced debugging for mapping load & translation)
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

def init_pygame_and_joystick_globally(force_rescan=False):
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
                _detected_joystick_names_global.append(joy.get_name()) # get_name() doesn't require init
                _joystick_objects_global.append(joy)
            except pygame.error as e_joy_get:
                print(f"Config Warning: Error getting info for joystick {i}: {e_joy_get}")
                _detected_joystick_names_global.append(f"Errored Joystick {i}")
                _joystick_objects_global.append(None)
        print(f"Config: Global scan/re-scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally()

# --- File for saving/loading ALL settings ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME
)
print(f"DEBUG config.py: Expecting JSON at: {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")

# --- Default Control Schemes & Enabled Flags ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P1_KEYBOARD_ENABLED = True
DEFAULT_P1_CONTROLLER_ENABLED = True

DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
DEFAULT_P2_KEYBOARD_ENABLED = True
DEFAULT_P2_CONTROLLER_ENABLED = True

DEFAULT_P3_INPUT_DEVICE = "unassigned"
DEFAULT_P3_KEYBOARD_ENABLED = False
DEFAULT_P3_CONTROLLER_ENABLED = False

DEFAULT_P4_INPUT_DEVICE = "unassigned"
DEFAULT_P4_KEYBOARD_ENABLED = False
DEFAULT_P4_CONTROLLER_ENABLED = False

UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

# --- Current Settings (will be updated by load_config) ---
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

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"]

AXIS_THRESHOLD_DEFAULT = 0.7

GAME_ACTIONS = [
    "left", "right", "up", "down", "jump", "crouch", "attack1", "attack2",
    "dash", "roll", "interact", "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]

EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP_ACTION": "jump", "CROUCH_ACTION": "crouch", "INTERACT_ACTION": "interact",
    "PRIMARY_ATTACK": "attack1", "SECONDARY_ATTACK": "attack2",
    "W": "up", "A": "left", "S": "down", "D": "right", "SPACE": "jump",
    "V": "attack1", "B": "attack2", "SHIFT": "dash",
}

DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4,
    "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7,
    "reset": Qt.Key.Key_Q, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K, "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_8, "projectile2": Qt.Key.Key_9, "projectile3": Qt.Key.Key_0, "projectile4": Qt.Key.Key_Minus,
    "projectile5": Qt.Key.Key_Equal, "projectile6": Qt.Key.Key_BracketLeft, "projectile7": Qt.Key.Key_BracketRight,
    "reset": Qt.Key.Key_Period, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete,
    "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End,
}

DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = { # RUNTIME format
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
    "reset": {"type": "button", "id": 6}, "pause": {"type": "button", "id": 7},
    "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {} # GUID-keyed, GUI format

P1_MAPPINGS: Dict[str, Any] = {} # Runtime format
P2_MAPPINGS: Dict[str, Any] = {} # Runtime format
P3_MAPPINGS: Dict[str, Any] = {} # Runtime format
P4_MAPPINGS: Dict[str, Any] = {} # Runtime format

def _translate_gui_map_to_runtime(gui_map_for_single_controller: Dict[str, Any]) -> Dict[str, Any]:
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(gui_map_for_single_controller, dict):
        print("Config Error (_translate_gui_map_to_runtime): Input is not a dictionary.")
        return {}

    # print(f"DEBUG _translate_gui_map_to_runtime: Input GUI map: {json.dumps(gui_map_for_single_controller, indent=2)}")

    for action_name, mapping_entry_gui_format in gui_map_for_single_controller.items():
        if action_name not in GAME_ACTIONS:
            # print(f"Config Warning (_translate_gui_map_to_runtime): Action '{action_name}' not in GAME_ACTIONS. Skipping.")
            continue
        if not isinstance(mapping_entry_gui_format, dict):
            # print(f"Config Warning (_translate_gui_map_to_runtime): Mapping entry for '{action_name}' not a dict: {mapping_entry_gui_format}")
            continue

        event_type = mapping_entry_gui_format.get("event_type")
        details = mapping_entry_gui_format.get("details")

        if not event_type or not isinstance(details, dict):
            # print(f"Config Warning (_translate_gui_map_to_runtime): Missing event_type or details for '{action_name}': {mapping_entry_gui_format}")
            continue

        runtime_entry: Dict[str, Any] = {"type": event_type}
        valid_entry = False

        if event_type == "button":
            button_id = details.get("button_id")
            if button_id is not None:
                try: runtime_entry["id"] = int(button_id); valid_entry = True
                except ValueError: print(f"Config Error (_translate_gui_map_to_runtime): Invalid button_id '{button_id}' for {action_name}")
        elif event_type == "axis":
            axis_id = details.get("axis_id")
            direction = details.get("direction")
            threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_id is not None and direction is not None:
                try:
                    runtime_entry["id"] = int(axis_id)
                    runtime_entry["value"] = int(direction)
                    runtime_entry["threshold"] = float(threshold)
                    valid_entry = True
                except ValueError: print(f"Config Error (_translate_gui_map_to_runtime): Invalid axis params for {action_name}: id={axis_id}, dir={direction}")
        elif event_type == "hat":
            hat_id = details.get("hat_id")
            value = details.get("value")
            if hat_id is not None and isinstance(value, list) and len(value) == 2:
                try:
                    runtime_entry["id"] = int(hat_id)
                    runtime_entry["value"] = tuple(map(int, value))
                    valid_entry = True
                except ValueError: print(f"Config Error (_translate_gui_map_to_runtime): Invalid hat params for {action_name}: id={hat_id}, val={value}")
        
        if valid_entry:
            runtime_mappings[action_name] = runtime_entry
        # else:
            # print(f"Config Warning (_translate_gui_map_to_runtime): Could not form valid runtime entry for '{action_name}'. GUI Details: {details}")
    # print(f"DEBUG _translate_gui_map_to_runtime: Output runtime map: {json.dumps(runtime_mappings, indent=2)}")
    return runtime_mappings

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    devices = []
    if not _joystick_initialized_globally: return devices
    for i in range(_detected_joystick_count_global):
        joy_object = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_name = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"Unknown Joystick {i}"
        guid_str: Optional[str] = None
        if joy_object:
            original_init_state = joy_object.get_init()
            try:
                if not original_init_state: joy_object.init()
                guid_str = joy_object.get_guid()
            except pygame.error as e_guid: print(f"Config Warning: Error processing GUID for joystick {i} ('{joy_name}'): {e_guid}")
            finally:
                if not original_init_state and joy_object.get_init(): joy_object.quit()
        internal_id_for_assignment = f"joystick_pygame_{i}" 
        display_name_for_combo = f"Joy {i}: {joy_name.split(' (GUID:')[0]}"
        devices.append((display_name_for_combo, internal_id_for_assignment, guid_str, i))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    return _joystick_objects_global

def save_config():
    player_settings_to_save = {}
    for i in range(1, 5):
        player_settings_to_save[f"player{i}_settings"] = {
            "input_device": globals().get(f"CURRENT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID),
            "keyboard_enabled": globals().get(f"P{i}_KEYBOARD_ENABLED", False),
            "controller_enabled": globals().get(f"P{i}_CONTROLLER_ENABLED", False),
        }
    data_to_save = {"config_version": "2.3.4", **player_settings_to_save, "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS}
    try:
        subdir_path = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(subdir_path): os.makedirs(subdir_path); print(f"Config: Created directory {subdir_path}")
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        update_player_mappings_from_config()
        return True
    except IOError as e: print(f"Config Error: Saving settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}"); return False

def load_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    init_pygame_and_joystick_globally(force_rescan=True)
    raw_config_data = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_config_data = json.load(f)
            print(f"Config: Successfully loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e: print(f"Config Error: Loading {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults."); raw_config_data = {}
    else: print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults/auto-detect.")

    for i in range(1, 5):
        p_settings = raw_config_data.get(f"player{i}_settings", {})
        globals()[f"CURRENT_P{i}_INPUT_DEVICE"] = p_settings.get("input_device", globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID))
        # Explicitly set enabled flags based on device type if not specified or if inconsistent
        current_dev = globals()[f"CURRENT_P{i}_INPUT_DEVICE"]
        kbd_enabled_from_file = p_settings.get("keyboard_enabled", None)
        ctrl_enabled_from_file = p_settings.get("controller_enabled", None)

        if kbd_enabled_from_file is None or ctrl_enabled_from_file is None: # If flags missing, derive them
            globals()[f"P{i}_KEYBOARD_ENABLED"] = current_dev.startswith("keyboard_")
            globals()[f"P{i}_CONTROLLER_ENABLED"] = current_dev.startswith("joystick_pygame_")
            # If it's a joystick device, allow keyboard too by default from original settings unless file explicitly disables it
            if current_dev.startswith("joystick_pygame_") and kbd_enabled_from_file is None: # If kbd_enabled not in file for a joystick user
                 globals()[f"P{i}_KEYBOARD_ENABLED"] = globals().get(f"DEFAULT_P{i}_KEYBOARD_ENABLED", True) # True or whatever default is
        else: # Flags are present, use them
            globals()[f"P{i}_KEYBOARD_ENABLED"] = kbd_enabled_from_file
            globals()[f"P{i}_CONTROLLER_ENABLED"] = ctrl_enabled_from_file
            # Sanity check: if device is kbd, ctrl_enabled should be false, and vice-versa (unless dual input is a feature)
            if current_dev.startswith("keyboard_") and ctrl_enabled_from_file:
                print(f"Config Warning: P{i} device is keyboard but controller_enabled=True in file. Setting controller_enabled=False.")
                globals()[f"P{i}_CONTROLLER_ENABLED"] = False
            if current_dev.startswith("joystick_pygame_") and not ctrl_enabled_from_file and kbd_enabled_from_file:
                 # This is okay, user might want only keyboard with a joystick plugged in but not used by this player.
                 # Or, if controller_enabled is false for a joystick device, maybe it means "don't use this joystick for this player"
                 # For now, trust the file if both flags are present. The GUI should manage these consistently.
                 pass


    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings", {})
    print("--- LOAD_CONFIG DEBUG ---")
    print(f"LOADED_PYGAME_JOYSTICK_MAPPINGS (GUID-keyed GUI format from JSON):")
    print(json.dumps(LOADED_PYGAME_JOYSTICK_MAPPINGS, indent=2)) # Max depth for print
    print("--- END LOAD_CONFIG DEBUG ---")

    if not raw_config_data:
        print("Config: No valid config file, attempting auto-assignment.")
        if _detected_joystick_count_global > 0:
            globals()["CURRENT_P1_INPUT_DEVICE"] = f"joystick_pygame_0"
            globals()["P1_CONTROLLER_ENABLED"] = True; globals()["P1_KEYBOARD_ENABLED"] = True
            print(f"Config Auto-Assign: P1 to joystick_pygame_0.")
            if _detected_joystick_count_global > 1:
                globals()["CURRENT_P2_INPUT_DEVICE"] = f"joystick_pygame_1"
                globals()["P2_CONTROLLER_ENABLED"] = True; globals()["P2_KEYBOARD_ENABLED"] = True
                print(f"Config Auto-Assign: P2 to joystick_pygame_1.")
            else: globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE; globals()["P2_CONTROLLER_ENABLED"]=False; globals()["P2_KEYBOARD_ENABLED"]=True
        else:
            globals()["CURRENT_P1_INPUT_DEVICE"] = DEFAULT_P1_INPUT_DEVICE; globals()["P1_CONTROLLER_ENABLED"]=False; globals()["P1_KEYBOARD_ENABLED"]=True
            globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE; globals()["P2_CONTROLLER_ENABLED"]=False; globals()["P2_KEYBOARD_ENABLED"]=True

    available_joy_device_ids = [f"joystick_pygame_{i}" for i in range(_detected_joystick_count_global)]
    assigned_devices = {}
    for i in range(1, 5):
        current_device_var = f"CURRENT_P{i}_INPUT_DEVICE"; default_device_val = globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        current_device_val = globals().get(current_device_var, default_device_val)
        if current_device_val.startswith("joystick_pygame_"):
            if current_device_val not in available_joy_device_ids:
                print(f"Config Warn: P{i}'s joystick '{current_device_val}' not found. Reverting to {default_device_val}.")
                globals()[current_device_var] = default_device_val; current_device_val = default_device_val
            if current_device_val != UNASSIGNED_DEVICE_ID:
                if current_device_val in assigned_devices:
                    colliding_player = assigned_devices[current_device_val]
                    print(f"Config Warn: P{i} and P{colliding_player} assigned same joystick '{current_device_val}'. Reverting P{i} to {default_device_val}.")
                    globals()[current_device_var] = default_device_val
                else: assigned_devices[current_device_val] = i
        elif current_device_val.startswith("keyboard_") and current_device_val != UNASSIGNED_DEVICE_ID:
            if current_device_val in assigned_devices:
                colliding_player = assigned_devices[current_device_val]
                print(f"Config Warn: P{i} and P{colliding_player} assigned same keyboard '{current_device_val}'. This might be intended or an issue.")
            else: assigned_devices[current_device_val] = i
    update_player_mappings_from_config()
    for i in range(1, 5): print(f"Config Loaded Final: P{i} Dev='{globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}', KbdEn={globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'P{i}_CONTROLLER_ENABLED')}")
    return True

def update_player_mappings_from_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    default_runtime_joystick_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy()
    print("\n--- CONFIG: Updating Player Mappings (Runtime) ---")
    available_joys_data = get_available_joystick_names_with_indices_and_guids() # Get this once

    for i in range(1, 5):
        player_id_str = f"P{i}"
        current_device_key = f"CURRENT_{player_id_str}_INPUT_DEVICE"
        player_mappings_key = f"{player_id_str}_MAPPINGS"
        current_input_device = globals().get(current_device_key, UNASSIGNED_DEVICE_ID)
        print(f"{player_id_str}: Current Device = '{current_input_device}'")

        if current_input_device == "keyboard_p1":
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
            print(f"{player_id_str}: Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        elif current_input_device == "keyboard_p2":
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
            print(f"{player_id_str}: Using DEFAULT_KEYBOARD_P2_MAPPINGS.")
        elif current_input_device and current_input_device.startswith("joystick_pygame_"):
            target_guid_for_player = None
            joystick_idx_for_player = -1
            try:
                joystick_idx_for_player = int(current_input_device.split('_')[-1])
                for _, _, guid, idx_from_func in available_joys_data:
                    if idx_from_func == joystick_idx_for_player:
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
                    print(f"{player_id_str}: No specific map in JSON for GUID '{target_guid_for_player}' (or GUID not found for index {joystick_idx_for_player}). Using default generic joystick map.")
            except ValueError:
                globals()[player_mappings_key] = default_runtime_joystick_map
                print(f"{player_id_str} Error: Could not parse joystick index from '{current_input_device}'. Using default generic map.")
            except Exception as e:
                globals()[player_mappings_key] = default_runtime_joystick_map
                print(f"{player_id_str} Error during map processing for '{current_input_device}': {e}. Using default generic map.")
        elif current_input_device == UNASSIGNED_DEVICE_ID or current_input_device == "unassigned_keyboard":
            globals()[player_mappings_key] = {}
            print(f"{player_id_str}: Device is '{current_input_device}'. No mappings assigned.")
        else:
            globals()[player_mappings_key] = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
            print(f"{player_id_str}: Device '{current_input_device}' fallback. Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        # print(f"DEBUG: {player_id_str} Mappings (jump): {globals()[player_mappings_key].get('jump', 'N/A')}")
    print("--- CONFIG: Finished Updating Player Mappings ---\n")

if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit(); _pygame_initialized_globally = False; _joystick_initialized_globally = False
        print("Config Test: Pygame explicitly quit for fresh re-initialization.")
    init_pygame_and_joystick_globally(force_rescan=True)
    print("\nTesting get_available_joystick_names_with_indices_and_guids():")
    joystick_data_list = get_available_joystick_names_with_indices_and_guids()
    if joystick_data_list:
        for i, data_item in enumerate(joystick_data_list): print(f"  Joystick {i}: Name='{data_item[0]}', InternalID='{data_item[1]}', GUID='{data_item[2]}', PygameIdx={data_item[3]}")
    else: print("  No joysticks detected or error during detection.")
    print("\n--- Simulating load_config() ---"); load_config()
    print(f"\n--- After test load_config(): ---")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i in range(1, 3):
        print(f"  P{i} Device: {globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}, KbdEn: {globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn: {globals().get(f'P{i}_CONTROLLER_ENABLED')}")
        print(f"  P{i} Mappings (jump): {globals().get(f'P{i}_MAPPINGS',{}).get('jump', 'N/A')}, (attack1): {globals().get(f'P{i}_MAPPINGS',{}).get('attack1', 'N/A')}")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("\n--- config.py direct test finished ---")