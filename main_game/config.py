# main_game/config.py
# -*- coding: utf-8 -*-
###############################
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1-P4.
MODIFIED: Removed direct modification of GAME_ACTIONS by controller_mapper_gui.
          GUI Nav actions are now defined in controller_mapper_gui and merged there.
MODIFIED: Strengthened fallback logic for default keyboard/controller assignments if file is missing or corrupt.
MODIFIED: Added a more explicit check for 'keyboard_p1' and 'keyboard_p2' assignment during auto-config.
"""
# version 2.4.0 (GUI Nav Actions decoupled from this file, strengthened auto-assignment)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Pygame is always imported for its constants and joystick capabilities
from PySide6.QtCore import Qt # For Qt.Key enum

# --- Logger ---
# Basic print-based logger for config.py itself, as it's a low-level module.
# The main application logger will handle more extensive logging.
def _config_log(level: str, message: str):
    print(f"CONFIG.PY ({level}): {message}")
# --- End Logger ---

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
        try:
            pygame.init()
            _pygame_initialized_globally = True
            _config_log("INFO", "Pygame globally initialized.")
        except Exception as e:
            _config_log("CRITICAL", f"Pygame global init failed: {e}")
            return

    if not _joystick_initialized_globally or force_rescan:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try:
            pygame.joystick.init()
            _joystick_initialized_globally = True
            _config_log("INFO", "Pygame Joystick globally initialized (or re-initialized).")
        except Exception as e:
            _config_log("CRITICAL", f"Pygame Joystick global init failed: {e}")
            _joystick_initialized_globally = False
            return

    current_count = pygame.joystick.get_count() if _joystick_initialized_globally else 0

    if force_rescan or current_count != _detected_joystick_count_global or \
       (not _joystick_objects_global and current_count > 0):

        _config_log("INFO", f"Rescanning joysticks. Prev count: {_detected_joystick_count_global}, Current: {current_count}, Force: {force_rescan}")
        _detected_joystick_count_global = current_count

        for old_joy in _joystick_objects_global:
            if old_joy and old_joy.get_init():
                try: old_joy.quit()
                except pygame.error: pass
        _joystick_objects_global = []
        _detected_joystick_names_global = []

        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i)
                _detected_joystick_names_global.append(joy.get_name())
                _joystick_objects_global.append(joy)
            except pygame.error as e:
                _config_log("WARN", f"Error accessing joystick {i}: {e}")
                _detected_joystick_names_global.append(f"ErrorJoystick{i}")
                _joystick_objects_global.append(None)
        _config_log("INFO", f"Joystick rescan complete. Found: {_detected_joystick_count_global}, Names: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally()

# --- File Paths ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
_CONFIG_PY_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(_CONFIG_PY_DIR, CONTROLLER_SETTINGS_SUBDIR, MAPPINGS_AND_DEVICE_CHOICES_FILENAME)

# --- Device IDs and Defaults ---
UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = False
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = True; DEFAULT_P2_CONTROLLER_ENABLED = False
DEFAULT_P3_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
DEFAULT_P4_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False

CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", UNASSIGNED_DEVICE_ID]
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"]

AXIS_THRESHOLD_DEFAULT = 0.7
# GAME_ACTIONS is the definitive list of *gameplay* actions.
# GUI navigation actions are handled by controller_mapper_gui.py locally and merged there for its UI.
GAME_ACTIONS: List[str] = [
    "left", "right", "up", "down", "jump", "crouch",
    "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]
# EXTERNAL_TO_INTERNAL_ACTION_MAP maps friendly names (potentially from older configs or UI elements)
# to the internal GAME_ACTIONS keys.
EXTERNAL_TO_INTERNAL_ACTION_MAP: Dict[str, str] = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP_ACTION": "jump", "PRIMARY_ATTACK": "attack1",
    # Direct Qt Key names to actions (primarily for default keyboard mappings if not using full action names)
    "W": "up", "A": "left", "S": "down", "D": "right", "V": "attack1", "B": "attack2", "SHIFT": "dash"
    # GUI-specific friendly names for GUI Nav actions will be managed by controller_mapper_gui.py
    # e.g., "GUI Up": "gui_nav_up"
}

DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = { # Internal Action Name -> Qt.Key
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
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete, # Using Enter/Delete for P2 menu
    "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End
}
# This is the RUNTIME format for default generic joystick mappings.
# Controller GUI will convert its storage format to this before passing to game logic.
DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Left Stick X Left
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Left Stick X Right
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},   # Left Stick Y Up
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Left Stick Y Down
    "jump": {"type": "button", "id": 0},      # Typically A/Cross
    "crouch": {"type": "button", "id": 1},    # Typically B/Circle (or could be Right Stick Click)
    "attack1": {"type": "button", "id": 2},   # Typically X/Square
    "attack2": {"type": "button", "id": 3},   # Typically Y/Triangle
    "dash": {"type": "button", "id": 5},      # Typically Right Bumper
    "roll": {"type": "button", "id": 4},      # Typically Left Bumper
    "interact": {"type": "button", "id": 10}, # Example: Left Stick Click
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)},   # D-Pad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},   # D-Pad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)},  # D-Pad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)},  # D-Pad Left
    "reset": {"type": "button", "id": 6},     # Typically Back/Select/View
    "pause": {"type": "button", "id": 7},     # Typically Start/Options/Menu
    # --- Menu Actions (can mirror game actions or be separate) ---
    "menu_confirm": {"type": "button", "id": 0}, # Mirror Jump
    "menu_cancel": {"type": "button", "id": 1},  # Mirror Crouch/B button
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)},     # Mirror D-Pad Up
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},   # Mirror D-Pad Down
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)},   # Mirror D-Pad Left
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)}    # Mirror D-Pad Right
}

# This stores mappings loaded FROM the GUI's JSON file format.
# Key is GUID, value is a dict of {action_name: gui_mapping_details}.
LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}

# Player-specific runtime mappings (populated by update_player_mappings_from_config)
P1_MAPPINGS: Dict[str, Any] = {}
P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}
P4_MAPPINGS: Dict[str, Any] = {}


def _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_joystick_mappings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates joystick mappings from the GUI's JSON storage format to the runtime Pygame format.
    Args:
        raw_gui_json_joystick_mappings: A dictionary where keys are internal action names
                                         and values are dicts from the GUI JSON for that action.
                                         Example: {"jump": {"event_type": "button", "details": {"button_id": 0, ...}}}
    Returns:
        A dictionary in the runtime Pygame format.
        Example: {"jump": {"type": "button", "id": 0}}
    """
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(raw_gui_json_joystick_mappings, dict):
        _config_log("ERROR", "_translate_gui_json: Input 'raw_gui_json_joystick_mappings' is not a dict.")
        return {}

    for action_name, mapping_entry_gui_format in raw_gui_json_joystick_mappings.items():
        if action_name not in GAME_ACTIONS: # Only process recognized game actions
            # This filters out GUI-specific nav actions if they were somehow in the joystick_mappings part
            continue
        if not isinstance(mapping_entry_gui_format, dict):
            _config_log("WARN", f"_translate_gui_json: Mapping entry for '{action_name}' is not a dict. Skipping.")
            continue

        event_type = mapping_entry_gui_format.get("event_type")
        details = mapping_entry_gui_format.get("details")

        if not event_type or not isinstance(details, dict):
            _config_log("WARN", f"_translate_gui_json: Missing 'event_type' or 'details' for action '{action_name}'. Skipping.")
            continue

        runtime_entry: Dict[str, Any] = {"type": event_type}
        valid_entry = False
        try:
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
                    runtime_entry["value"] = int(direction) # -1 or 1
                    runtime_entry["threshold"] = float(threshold)
                    valid_entry = True
            elif event_type == "hat":
                hat_id = details.get("hat_id")
                value = details.get("value") # Expected to be a list [x, y]
                if hat_id is not None and isinstance(value, list) and len(value) == 2:
                    runtime_entry["id"] = int(hat_id)
                    runtime_entry["value"] = tuple(map(int, value)) # Convert to tuple (x,y)
                    valid_entry = True
        except (ValueError, TypeError) as e_cast:
            _config_log("ERROR", f"_translate_gui_json: Invalid data type in details for action '{action_name}', type '{event_type}': {details}. Error: {e_cast}")

        if valid_entry:
            runtime_mappings[action_name] = runtime_entry
        else:
            _config_log("WARN", f"_translate_gui_json: Could not create valid runtime entry for action '{action_name}' with details: {details}")
    return runtime_mappings


def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    """
    Returns a list of tuples for available joysticks: (display_name, internal_id, guid, pygame_index).
    Ensures joysticks are initialized if necessary.
    """
    devices: List[Tuple[str, str, Optional[str], int]] = []
    if not _joystick_initialized_globally:
        _config_log("WARN", "get_available_joystick_names called but joystick system not initialized. Attempting init.")
        init_pygame_and_joystick_globally(force_rescan=True) # Force a rescan if not init'd
        if not _joystick_initialized_globally: return devices # Still failed

    for i in range(_detected_joystick_count_global):
        joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_name_from_global_list = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"UnknownJoystick{i}"
        guid_str: Optional[str] = None

        if joy_obj:
            was_originally_init_by_pygame = joy_obj.get_init()
            actual_name_from_obj = joy_name_from_global_list # Default to list name
            try:
                if not was_originally_init_by_pygame: joy_obj.init() # Init if not already to get info
                actual_name_from_obj = joy_obj.get_name() # Get fresh name
                guid_str = joy_obj.get_guid()
            except pygame.error as e_joy_info:
                _config_log("WARN", f"Error getting info for joystick {i} ('{actual_name_from_obj}'): {e_joy_info}")
            finally:
                # If we initialized it just to get info, quit it to restore original state
                if not was_originally_init_by_pygame and joy_obj.get_init():
                    try: joy_obj.quit()
                    except pygame.error: pass
        else:
             _config_log("WARN", f"No joystick object at index {i} in _joystick_objects_global, but expected one.")

        internal_id_for_assignment = f"joystick_pygame_{i}" # Used for CURRENT_Px_INPUT_DEVICE
        display_name_for_ui = f"Joy {i}: {actual_name_from_obj.split(' (GUID:')[0]}" # Cleaner display name
        devices.append((display_name_for_ui, internal_id_for_assignment, guid_str, i))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    """Returns the globally managed list of Pygame Joystick objects."""
    return _joystick_objects_global

def save_config() -> bool:
    # ... (save_config logic remains the same, but it now reads from the global module vars) ...
    player_settings_to_save: Dict[str, Any] = {}
    for i in range(1, 5):
        player_num_str = f"P{i}"
        player_settings_to_save[f"player{i}_settings"] = {
            "input_device": globals().get(f"CURRENT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID),
            "keyboard_enabled": globals().get(f"{player_num_str}_KEYBOARD_ENABLED", False),
            "controller_enabled": globals().get(f"{player_num_str}_CONTROLLER_ENABLED", False)
        }
    data_to_save = {"config_version": "2.4.0", **player_settings_to_save, "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS}
    try:
        settings_subdir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(settings_subdir): os.makedirs(settings_subdir); _config_log("INFO", f"Created directory {settings_subdir}")
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data_to_save, f, indent=4)
        _config_log("INFO", f"Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        return True
    except IOError as e: _config_log("ERROR", f"Could not save settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}"); return False

def load_config() -> bool:
    # ... (load_config logic remains similar, but ensures stronger auto-assignment and flag consistency) ...
    global LOADED_PYGAME_JOYSTICK_MAPPINGS, CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global CURRENT_P3_INPUT_DEVICE, P3_KEYBOARD_ENABLED, P3_CONTROLLER_ENABLED
    global CURRENT_P4_INPUT_DEVICE, P4_KEYBOARD_ENABLED, P4_CONTROLLER_ENABLED
    
    init_pygame_and_joystick_globally(force_rescan=True)
    raw_data_from_file: Dict[str, Any] = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_data_from_file = json.load(f)
            _config_log("INFO", f"Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            _config_log("ERROR", f"Failed to load or parse {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults/auto-assign.")
            raw_data_from_file = {}
    else:
        _config_log("INFO", f"File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults and auto-assignment.")
        raw_data_from_file = {}

    player_settings_section_exists = any(key.startswith("player") and key.endswith("_settings") for key in raw_data_from_file)

    if not player_settings_section_exists:
        _config_log("INFO", "No player settings in JSON or file missing. Performing auto-assignment for P1-P4.")
        auto_assignments: Dict[str, Dict[str, Any]] = {
            f"P{i}": {"device": globals()[f"DEFAULT_P{i}_INPUT_DEVICE"], "kbd_en": globals()[f"DEFAULT_P{i}_KEYBOARD_ENABLED"], "ctrl_en": globals()[f"DEFAULT_P{i}_CONTROLLER_ENABLED"]} for i in range(1, 5)
        }
        available_joy_indices = list(range(_detected_joystick_count_global))
        used_keyboard_layouts = set() # To prevent assigning the same kbd layout to multiple players if possible
        
        # Priority 1: Controllers
        for p_num_ctrl in range(1, 5):
            p_str_ctrl = f"P{p_num_ctrl}"
            if available_joy_indices:
                assigned_joy_idx = available_joy_indices.pop(0)
                auto_assignments[p_str_ctrl]["device"] = f"joystick_pygame_{assigned_joy_idx}"
                auto_assignments[p_str_ctrl]["kbd_en"] = False; auto_assignments[p_str_ctrl]["ctrl_en"] = True
            # Else, keep its default (which might be keyboard or unassigned) for now

        # Priority 2: Keyboards (for those not assigned a controller, prioritizing P1/P2)
        # First, try to assign specific default keyboard layouts (keyboard_p1, keyboard_p2)
        for p_num_kbd_specific in range(1, 3): # P1, P2
            p_str_kbd_specific = f"P{p_num_kbd_specific}"
            if not auto_assignments[p_str_kbd_specific]["ctrl_en"]: # If P1/P2 didn't get a controller
                default_kbd_for_this_player = globals()[f"DEFAULT_{p_str_kbd_specific}_INPUT_DEVICE"]
                if default_kbd_for_this_player not in used_keyboard_layouts:
                    auto_assignments[p_str_kbd_specific]["device"] = default_kbd_for_this_player
                    auto_assignments[p_str_kbd_specific]["kbd_en"] = True; auto_assignments[p_str_kbd_specific]["ctrl_en"] = False
                    used_keyboard_layouts.add(default_kbd_for_this_player)
        
        # Second pass for keyboards if specific defaults were taken or for P3/P4 if still unassigned
        for p_num_kbd_general in range(1, 5):
            p_str_kbd_general = f"P{p_num_kbd_general}"
            if not auto_assignments[p_str_kbd_general]["ctrl_en"] and \
               (auto_assignments[p_str_kbd_general]["device"] == UNASSIGNED_DEVICE_ID or \
                auto_assignments[p_str_kbd_general]["device"] in used_keyboard_layouts and # If its current assignment is a KBD already used
                 auto_assignments[p_str_kbd_general]["device"] != globals()[f"DEFAULT_{p_str_kbd_general}_INPUT_DEVICE"]): # And it wasn't its primary default
                
                # Try assigning keyboard_p1 if free and P1 or P2
                if "keyboard_p1" not in used_keyboard_layouts and p_num_kbd_general in [1,2]:
                    auto_assignments[p_str_kbd_general]["device"] = "keyboard_p1"
                    auto_assignments[p_str_kbd_general]["kbd_en"] = True; auto_assignments[p_str_kbd_general]["ctrl_en"] = False
                    used_keyboard_layouts.add("keyboard_p1")
                # Try assigning keyboard_p2 if free and P1 or P2
                elif "keyboard_p2" not in used_keyboard_layouts and p_num_kbd_general in [1,2]:
                    auto_assignments[p_str_kbd_general]["device"] = "keyboard_p2"
                    auto_assignments[p_str_kbd_general]["kbd_en"] = True; auto_assignments[p_str_kbd_general]["ctrl_en"] = False
                    used_keyboard_layouts.add("keyboard_p2")
                else: # Fallback to UNASSIGNED if no suitable keyboard available
                    if p_num_kbd_general > 2 : # P3/P4 default to unassigned if no controller/kbd
                        auto_assignments[p_str_kbd_general]["device"] = UNASSIGNED_DEVICE_ID
                        auto_assignments[p_str_kbd_general]["kbd_en"] = False; auto_assignments[p_str_kbd_general]["ctrl_en"] = False
        
        for i_auto in range(1, 5):
            p_str_auto = f"P{i_auto}"; settings_auto = auto_assignments[p_str_auto]
            globals()[f"CURRENT_{p_str_auto}_INPUT_DEVICE"] = settings_auto["device"]
            globals()[f"{p_str_auto}_KEYBOARD_ENABLED"] = settings_auto["kbd_en"]
            globals()[f"{p_str_auto}_CONTROLLER_ENABLED"] = settings_auto["ctrl_en"]
    else: # Load player settings from file
        for i in range(1, 5):
            player_num_str = f"P{i}"; settings_from_file = raw_data_from_file.get(f"player{i}_settings", {})
            globals()[f"CURRENT_{player_num_str}_INPUT_DEVICE"] = settings_from_file.get("input_device", globals()[f"DEFAULT_{player_num_str}_INPUT_DEVICE"])
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = settings_from_file.get("keyboard_enabled", globals()[f"DEFAULT_{player_num_str}_KEYBOARD_ENABLED"])
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = settings_from_file.get("controller_enabled", globals()[f"DEFAULT_{player_num_str}_CONTROLLER_ENABLED"])

    # --- Validate and Correct device assignments and enabled flags POST-LOAD/AUTO-ASSIGN ---
    available_pygame_joy_device_ids = [f"joystick_pygame_{j}" for j in range(_detected_joystick_count_global)]
    assigned_pygame_joystick_indices: Dict[int, str] = {} # py_idx -> P_str
    assigned_keyboard_layouts: Dict[str, str] = {} # keyboard_id -> P_str

    for i_validate in range(1, 5):
        player_num_str_val = f"P{i_validate}"; current_device_var = f"CURRENT_{player_num_str_val}_INPUT_DEVICE"
        kbd_en_var = f"{player_num_str_val}_KEYBOARD_ENABLED"; ctrl_en_var = f"{player_num_str_val}_CONTROLLER_ENABLED"
        default_device_val = globals()[f"DEFAULT_{player_num_str_val}_INPUT_DEVICE"]
        assigned_dev = globals()[current_device_var]

        if assigned_dev.startswith("keyboard_"):
            if assigned_dev in assigned_keyboard_layouts and assigned_keyboard_layouts[assigned_dev] != player_num_str_val:
                _config_log("WARN", f"Keyboard conflict: '{assigned_dev}' for {player_num_str_val} already used by {assigned_keyboard_layouts[assigned_dev]}. Reverting {player_num_str_val} to default.")
                globals()[current_device_var] = default_device_val # Revert to its own default
                # Re-evaluate enabled flags based on new default
                if default_device_val.startswith("keyboard_"): globals()[kbd_en_var] = True; globals()[ctrl_en_var] = False
                elif default_device_val.startswith("joystick_pygame_"): globals()[kbd_en_var] = False; globals()[ctrl_en_var] = True # This case should not happen if logic is correct
                else: globals()[kbd_en_var] = False; globals()[ctrl_en_var] = False
            else: # No conflict, or it's its own assignment
                assigned_keyboard_layouts[assigned_dev] = player_num_str_val
                globals()[kbd_en_var] = True; globals()[ctrl_en_var] = False
        elif assigned_dev.startswith("joystick_pygame_"):
            try:
                joy_idx_part_val = assigned_dev.split('_')[-1]
                if not joy_idx_part_val.isdigit(): raise ValueError("Non-numeric joystick index suffix")
                py_idx_val = int(joy_idx_part_val)
                if assigned_dev in available_pygame_joy_device_ids:
                    if py_idx_val in assigned_pygame_joystick_indices and assigned_pygame_joystick_indices[py_idx_val] != player_num_str_val:
                        _config_log("WARN", f"Joystick conflict: '{assigned_dev}' for {player_num_str_val} already used by {assigned_pygame_joystick_indices[py_idx_val]}. Reverting {player_num_str_val} to default.")
                        globals()[current_device_var] = default_device_val
                        if default_device_val.startswith("keyboard_"): globals()[kbd_en_var] = True; globals()[ctrl_en_var] = False
                        else: globals()[kbd_en_var] = False; globals()[ctrl_en_var] = (default_device_val != UNASSIGNED_DEVICE_ID)
                    else:
                        assigned_pygame_joystick_indices[py_idx_val] = player_num_str_val
                        globals()[kbd_en_var] = False; globals()[ctrl_en_var] = True
                else: # Joystick not detected
                    _config_log("WARN", f"{player_num_str_val}'s joystick '{assigned_dev}' NOT detected. Reverting to default.")
                    globals()[current_device_var] = default_device_val
                    if default_device_val.startswith("keyboard_"): globals()[kbd_en_var] = True; globals()[ctrl_en_var] = False
                    else: globals()[kbd_en_var] = False; globals()[ctrl_en_var] = (default_device_val != UNASSIGNED_DEVICE_ID)
            except (ValueError, IndexError) as e_parse:
                _config_log("ERROR", f"Error parsing joystick ID '{assigned_dev}' for {player_num_str_val}: {e_parse}. Reverting to default.")
                globals()[current_device_var] = default_device_val
                if default_device_val.startswith("keyboard_"): globals()[kbd_en_var] = True; globals()[ctrl_en_var] = False
                else: globals()[kbd_en_var] = False; globals()[ctrl_en_var] = (default_device_val != UNASSIGNED_DEVICE_ID)
        elif assigned_dev == UNASSIGNED_DEVICE_ID:
            globals()[kbd_en_var] = False; globals()[ctrl_en_var] = False
        else: # Unknown device type
            _config_log("WARN", f"{player_num_str_val} has unknown device '{assigned_dev}'. Setting to UNASSIGNED.")
            globals()[current_device_var] = UNASSIGNED_DEVICE_ID; globals()[kbd_en_var] = False; globals()[ctrl_en_var] = False

    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_data_from_file.get("joystick_mappings", {})
    update_player_mappings_from_config()
    _config_log("INFO", "Config loaded and validated.")
    for i_final in range(1, 5):
        p_str_final = f"P{i_final}"; _config_log("INFO", f"  Final {p_str_final} Dev='{globals().get(f'CURRENT_{p_str_final}_INPUT_DEVICE')}', KbdEn={globals().get(f'{p_str_final}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'{p_str_final}_CONTROLLER_ENABLED')}")
    return True


def update_player_mappings_from_config():
    # ... (unchanged, but now uses the globally available `_translate_and_validate_gui_json_to_pygame_mappings`)
    global P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS, LOADED_PYGAME_JOYSTICK_MAPPINGS
    default_runtime_joystick_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy()
    available_joys_data_for_map_update = get_available_joystick_names_with_indices_and_guids()

    for i in range(1, 5):
        player_id_str_map = f"P{i}"
        current_input_device_for_player_map = globals().get(f"CURRENT_{player_id_str_map}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        player_mappings_var_name_map = f"{player_id_str_map}_MAPPINGS"; target_runtime_map_for_player_update: Dict[str, Any] = {}

        if current_input_device_for_player_map == "keyboard_p1": target_runtime_map_for_player_update = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
        elif current_input_device_for_player_map == "keyboard_p2": target_runtime_map_for_player_update = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        elif current_input_device_for_player_map and current_input_device_for_player_map.startswith("joystick_pygame_"):
            assigned_pygame_idx_str_map = current_input_device_for_player_map.split('_')[-1]
            target_guid_for_player_map: Optional[str] = None; assigned_pygame_idx_map: Optional[int] = None
            try:
                assigned_pygame_idx_map = int(assigned_pygame_idx_str_map)
                for _, _, guid_map, py_idx_map in available_joys_data_for_map_update:
                    if py_idx_map == assigned_pygame_idx_map: target_guid_for_player_map = guid_map; break
            except (ValueError, IndexError): _config_log("ERROR", f"  {player_id_str_map} (MapUpdate): Invalid Pygame index '{assigned_pygame_idx_str_map}'.")
            if target_guid_for_player_map and target_guid_for_player_map in LOADED_PYGAME_JOYSTICK_MAPPINGS:
                gui_format_map_for_guid = LOADED_PYGAME_JOYSTICK_MAPPINGS[target_guid_for_player_map]
                runtime_map_translated = _translate_and_validate_gui_json_to_pygame_mappings(gui_format_map_for_guid)
                if runtime_map_translated: target_runtime_map_for_player_update = runtime_map_translated
                else: target_runtime_map_for_player_update = default_runtime_joystick_map.copy(); _config_log("WARN", f"  {player_id_str_map}: Translation FAILED for GUID '{target_guid_for_player_map}'. Using default generic joystick map.")
            else:
                target_runtime_map_for_player_update = default_runtime_joystick_map.copy()
                _config_log("INFO", f"  {player_id_str_map}: No specific map for GUID '{target_guid_for_player_map}' (or GUID not found for index {assigned_pygame_idx_map}). Using default generic map.")
        elif current_input_device_for_player_map == UNASSIGNED_DEVICE_ID: target_runtime_map_for_player_update = {}
        else: target_runtime_map_for_player_update = {}; _config_log("WARN", f"  {player_id_str_map}: Device '{current_input_device_for_player_map}' unrecognized. Assigning empty map.")
        globals()[player_mappings_var_name_map] = target_runtime_map_for_player_update
    _config_log("INFO", "Player runtime mappings updated from config.")

# Initial load when this module is imported
if __name__ != "__main__":
    _config_log("INFO", "config.py imported. Calling load_config().")
    load_config()
else: # Standalone execution
    _config_log("INFO", "--- Running config.py directly for testing ---")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try: pygame.quit()
        except pygame.error: pass
        _pygame_initialized_globally = False; _joystick_initialized_globally = False
        _config_log("INFO", "  (Standalone Test: Pygame system reset for fresh init by config.py itself)")
    load_config()
    _config_log("INFO", f"\n--- After test load_config(): ---")
    _config_log("INFO", f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i_main in range(1, 5):
        p_str_main = f"P{i_main}"
        _config_log("INFO", f"  {p_str_main} Dev: {globals().get(f'CURRENT_{p_str_main}_INPUT_DEVICE')}, KbdEn: {globals().get(f'{p_str_main}_KEYBOARD_ENABLED')}, CtrlEn: {globals().get(f'{p_str_main}_CONTROLLER_ENABLED')}")
        maps_main = globals().get(f'{p_str_main}_MAPPINGS', {})
        _config_log("INFO", f"    Jump: {maps_main.get('jump', 'N/A')}, Attack1: {maps_main.get('attack1', 'N/A')}, Left: {maps_main.get('left', 'N/A')}")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try: pygame.quit()
        except pygame.error: pass
        _config_log("INFO", "  (Standalone Test: Pygame quit at end of test)")
    _config_log("INFO", "\n--- config.py direct test finished ---")