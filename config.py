# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices for P1-P4.
"""
# version 2.3.8 (Further robustness in init and load_config)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Pygame import should be at the top
import sys
from PySide6.QtCore import Qt # Assuming Qt is used for keyboard mapping constants
import copy

# --- General App Config ---
MAX_UI_CONTROLLERS_FOR_NAV = 2
GRID_NAV_UP = 100; GRID_NAV_DOWN = 101; GRID_NAV_LEFT = 102; GRID_NAV_RIGHT = 103

_pygame_initialized_globally = False
_joystick_initialized_globally = False
_detected_joystick_count_global = 0
_detected_joystick_names_global: List[str] = []
_joystick_objects_global: List[Optional[pygame.joystick.Joystick]] = []

def init_pygame_and_joystick_globally(force_rescan=False):
    global _pygame_initialized_globally, _joystick_initialized_globally
    global _detected_joystick_count_global, _detected_joystick_names_global, _joystick_objects_global

    if not _pygame_initialized_globally:
        try:
            pygame.init() # Initializes all imported Pygame modules
            _pygame_initialized_globally = True
            print("Config: Pygame globally initialized.")
        except Exception as e_pg_init:
            print(f"Config CRITICAL ERROR: Pygame global init failed: {e_pg_init}")
            return

    # Joystick system initialization
    if force_rescan and _joystick_initialized_globally:
        print("Config: Forcing joystick rescan. Quitting existing joystick system.")
        try:
            pygame.joystick.quit() # Quit the Pygame joystick module
        except pygame.error as e_joy_quit:
            print(f"Config Warning: Error during pygame.joystick.quit() on rescan: {e_joy_quit}")
        _joystick_initialized_globally = False # Mark as not initialized to force re-init below
        # Joystick objects in _joystick_objects_global become invalid after system quit
        _joystick_objects_global.clear()
        _detected_joystick_names_global.clear()
        _detected_joystick_count_global = 0

    if not _joystick_initialized_globally:
        try:
            pygame.joystick.init() # Initialize/Re-initialize the joystick system
            _joystick_initialized_globally = True
            print("Config: Pygame Joystick system globally initialized/re-initialized.")
        except Exception as e_joy_init:
            print(f"Config CRITICAL ERROR: Pygame Joystick global init failed: {e_joy_init}")
            _joystick_initialized_globally = False
            return

    if _joystick_initialized_globally:
        current_count = pygame.joystick.get_count()
        # Rescan if forced, or if the count changed, or if it's the first time and lists are empty
        # Note: force_rescan=True already handled quitting and clearing above.
        if force_rescan or current_count != _detected_joystick_count_global or not _joystick_objects_global:
            print(f"Config: Scanning/Re-scanning joysticks. Previous count: {_detected_joystick_count_global}, Current Pygame count: {current_count}")

            # If not a forced rescan (where system was already quit), and lists are not empty,
            # it implies a hotplug event. We don't need to quit individual joysticks here
            # as we are about to rebuild the list from scratch based on pygame.joystick.get_count().
            _joystick_objects_global.clear()
            _detected_joystick_names_global.clear()

            _detected_joystick_count_global = current_count
            for i in range(_detected_joystick_count_global):
                try:
                    joy = pygame.joystick.Joystick(i) # Get new Joystick instance
                    # joy.init() is not strictly necessary here if pygame.joystick.init() succeeded,
                    # but it doesn't hurt to ensure it's ready if we access properties immediately.
                    if not joy.get_init():
                        joy.init() # Ensure this specific joystick instance is initialized
                    _detected_joystick_names_global.append(joy.get_name())
                    _joystick_objects_global.append(joy)
                except pygame.error as e_joy_get:
                    print(f"Config Warning: Error getting/initing joystick {i} ('{pygame.joystick.Joystick(i).get_name() if _detected_joystick_count_global > i else 'Unknown Name'}'): {e_joy_get}")
                    _joystick_objects_global.append(None)
            print(f"Config: Scan complete. Found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")
    else:
        _detected_joystick_count_global = 0
        _detected_joystick_names_global.clear()
        _joystick_objects_global.clear()
        print("Config: Joystick system is not initialized. Joystick count set to 0.")


CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME
)

UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Default)", "Keyboard (P2 Default)", "Keyboard (Unassigned)"]


DEFAULT_P1_KEYBOARD_DEVICE = KEYBOARD_DEVICE_IDS[0] # "keyboard_p1"
DEFAULT_P1_CONTROLLER_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P2_KEYBOARD_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P2_CONTROLLER_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P3_KEYBOARD_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P3_CONTROLLER_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P4_KEYBOARD_DEVICE = UNASSIGNED_DEVICE_ID
DEFAULT_P4_CONTROLLER_DEVICE = UNASSIGNED_DEVICE_ID

AXIS_THRESHOLD_DEFAULT = 0.7

CURRENT_P1_KEYBOARD_DEVICE = DEFAULT_P1_KEYBOARD_DEVICE
CURRENT_P1_CONTROLLER_DEVICE = DEFAULT_P1_CONTROLLER_DEVICE
CURRENT_P2_KEYBOARD_DEVICE = DEFAULT_P2_KEYBOARD_DEVICE
CURRENT_P2_CONTROLLER_DEVICE = DEFAULT_P2_CONTROLLER_DEVICE
CURRENT_P3_KEYBOARD_DEVICE = DEFAULT_P3_KEYBOARD_DEVICE
CURRENT_P3_CONTROLLER_DEVICE = DEFAULT_P3_CONTROLLER_DEVICE
CURRENT_P4_KEYBOARD_DEVICE = DEFAULT_P4_KEYBOARD_DEVICE
CURRENT_P4_CONTROLLER_DEVICE = DEFAULT_P4_CONTROLLER_DEVICE

P1_KEYBOARD_ENABLED = False; P1_CONTROLLER_ENABLED = False
P2_KEYBOARD_ENABLED = False; P2_CONTROLLER_ENABLED = False
P3_KEYBOARD_ENABLED = False; P3_CONTROLLER_ENABLED = False
P4_KEYBOARD_ENABLED = False; P4_CONTROLLER_ENABLED = False

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
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause", "PAUSE": "pause",
    "W": "up", "A": "left", "S": "down", "D": "right", "1": "projectile1", "2": "projectile2",
    "3": "projectile3", "4": "projectile4", "5": "projectile5", "Q": "reset", "E": "interact",
    "V": "attack1", "B": "attack2", "SPACE": "jump", "SHIFT": "dash", "CTRL": "roll", "ESCAPE": "pause"
}
DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4,
    "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7,
    "reset": Qt.Key.Key_R, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_Left, "right": Qt.Key.Key_Right, "up": Qt.Key.Key_Up, "down": Qt.Key.Key_Down,
    "jump": Qt.Key.Key_Up, "crouch": Qt.Key.Key_Down, "attack1": Qt.Key.Key_Comma, "attack2": Qt.Key.Key_Period,
    "dash": Qt.Key.Key_Slash, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_M,
    "projectile1": Qt.Key.Key_7, "projectile2": Qt.Key.Key_8, "projectile3": Qt.Key.Key_9, "projectile4": Qt.Key.Key_0,
    "projectile5": Qt.Key.Key_Minus, "projectile6": Qt.Key.Key_Equal, "projectile7": Qt.Key.Key_Backspace,
    "reset": Qt.Key.Key_Delete, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_F11,
    "menu_up": Qt.Key.Key_F5, "menu_down": Qt.Key.Key_F6, "menu_left": Qt.Key.Key_F7, "menu_right": Qt.Key.Key_F8,
}
DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, "crouch": {"type": "button", "id": 1},
    "attack1": {"type": "button", "id": 2}, "attack2": {"type": "button", "id": 3},
    "dash": {"type": "button", "id": 5}, "roll": {"type": "button", "id": 4},
    "interact": {"type": "button", "id": 3},
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)},
    "projectile5": {"type": "axis", "id": 4, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "projectile6": {"type": "axis", "id": 5, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "projectile7": {"type": "button", "id": 10},
    "reset": {"type": "button", "id": 6}, "pause": {"type": "button", "id": 7},
    "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}
_TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME: Dict[str, Any] = {}
P1_MAPPINGS: Dict[str, Any] = {}; P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}; P4_MAPPINGS: Dict[str, Any] = {}

def translate_mapping_for_runtime(gui_storage_mapping_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(gui_storage_mapping_entry, dict): return None
    pygame_event_type = gui_storage_mapping_entry.get("event_type")
    details_from_gui = gui_storage_mapping_entry.get("details")
    if not isinstance(details_from_gui, dict) or pygame_event_type not in ["button", "axis", "hat"]: return None
    pygame_event_id = None
    if pygame_event_type == "button": pygame_event_id = details_from_gui.get("button_id")
    elif pygame_event_type == "axis": pygame_event_id = details_from_gui.get("axis_id")
    elif pygame_event_type == "hat": pygame_event_id = details_from_gui.get("hat_id")
    if pygame_event_id is None or not isinstance(pygame_event_id, int): return None
    final_mapping: Dict[str, Any] = {"type": pygame_event_type, "id": pygame_event_id}
    if pygame_event_type == "axis":
        axis_direction = details_from_gui.get("direction")
        axis_threshold = details_from_gui.get("threshold", AXIS_THRESHOLD_DEFAULT)
        if axis_direction not in [-1, 1]: return None
        final_mapping["value"] = axis_direction
        final_mapping["threshold"] = float(axis_threshold)
    elif pygame_event_type == "hat":
        hat_value = details_from_gui.get("value")
        if not isinstance(hat_value, (list, tuple)) or len(hat_value) != 2: return None # Allow list from GUI
        final_mapping["value"] = tuple(map(int, hat_value))
    return final_mapping

def _translate_gui_mappings_for_guid_to_runtime(
    all_gui_mappings_by_guid: Dict[str, Dict[str, Any]],
    target_guid: Optional[str]
) -> Dict[str, Any]:
    if target_guid and target_guid in all_gui_mappings_by_guid:
        gui_mappings_for_target = all_gui_mappings_by_guid[target_guid]
        runtime_mappings: Dict[str, Any] = {}
        for action_key, gui_entry in gui_mappings_for_target.items():
            if action_key not in GAME_ACTIONS: continue
            translated_entry = translate_mapping_for_runtime(gui_entry)
            if translated_entry: runtime_mappings[action_key] = translated_entry
        if runtime_mappings:
            # print(f"Config Translator: Translated {len(runtime_mappings)} mappings for GUID {target_guid}.")
            return runtime_mappings
        # print(f"Config Translator: GUID {target_guid} translation empty. Using generic defaults.")
    # elif target_guid: print(f"Config Translator: GUID {target_guid} not in loaded mappings. Using generic defaults.")
    # else: print("Config Translator: No target GUID. Using generic defaults.")
    return copy.deepcopy(DEFAULT_GENERIC_JOYSTICK_MAPPINGS)

def get_active_runtime_joystick_mappings() -> Dict[str, Any]: # Primarily for UI/mapper simulation
    return _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME.copy()

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    devices = []
    if _joystick_initialized_globally:
        for i in range(_detected_joystick_count_global):
            joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) and _joystick_objects_global[i] is not None else None
            if joy_obj:
                try:
                    if not joy_obj.get_init(): joy_obj.init() # Ensure it's init before getting info
                    joy_name = joy_obj.get_name()
                    guid_str = joy_obj.get_guid() if hasattr(joy_obj, 'get_guid') else f"NO_GUID_IDX_{i}"
                    internal_id = f"joystick_pygame_{i}" # Used for assigning to player slots
                    display_name = f"Joy {i}: {joy_name}"
                    devices.append((display_name, internal_id, guid_str, i))
                except pygame.error as e:
                    print(f"Config Warning: Error accessing joystick {i} properties: {e}")
    return devices

def get_joystick_guid_by_pygame_index(pygame_index: int) -> Optional[str]:
    if 0 <= pygame_index < _detected_joystick_count_global:
        joy_obj = _joystick_objects_global[pygame_index] if pygame_index < len(_joystick_objects_global) else None
        if joy_obj:
            try:
                if not joy_obj.get_init(): joy_obj.init()
                if hasattr(joy_obj, 'get_guid'): return joy_obj.get_guid()
            except pygame.error: pass # Failed to init/get guid
        return f"NO_GUID_IDX_{pygame_index}" # Fallback if GUID not available
    return None

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    return _joystick_objects_global

def save_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    data_to_save = {
        "config_version": "2.3.8", # Incremented version
        "joystick_mappings_by_guid": LOADED_PYGAME_JOYSTICK_MAPPINGS
    }
    for i in range(1, 5):
        player_num_str = str(i)
        data_to_save[f"player{player_num_str}_devices"] = {
            "keyboard_device": globals()[f"CURRENT_P{player_num_str}_KEYBOARD_DEVICE"],
            "controller_device": globals()[f"CURRENT_P{player_num_str}_CONTROLLER_DEVICE"]
        }
    try:
        settings_dir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(settings_dir): os.makedirs(settings_dir)
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        load_config(called_from_save=True) # Reload to apply any derived states consistently
        return True
    except IOError as e:
        print(f"Config Error: Saving settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}")
        return False

def load_config(called_from_save=False):
    global LOADED_PYGAME_JOYSTICK_MAPPINGS, _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME
    # Player CURRENT_*_DEVICE and *_ENABLED flags are global and will be updated here

    if not called_from_save:
        init_pygame_and_joystick_globally(force_rescan=True)

    raw_config_data = {}
    config_file_found_and_parsed = False
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f:
                raw_config_data = json.load(f)
            print(f"Config: Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
            config_file_found_and_parsed = True
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults.")
    else:
        print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults.")

    # Load or default player device choices
    for i in range(1, 5):
        player_num_str = str(i)
        default_kbd_dev = globals()[f"DEFAULT_P{player_num_str}_KEYBOARD_DEVICE"]
        default_ctrl_dev = globals()[f"DEFAULT_P{player_num_str}_CONTROLLER_DEVICE"]

        if config_file_found_and_parsed:
            p_devices_settings = raw_config_data.get(f"player{player_num_str}_devices", {})
            globals()[f"CURRENT_P{player_num_str}_KEYBOARD_DEVICE"] = p_devices_settings.get("keyboard_device", default_kbd_dev)
            globals()[f"CURRENT_P{player_num_str}_CONTROLLER_DEVICE"] = p_devices_settings.get("controller_device", default_ctrl_dev)
        else: # No config file or parse error, apply full defaults
            globals()[f"CURRENT_P{player_num_str}_KEYBOARD_DEVICE"] = default_kbd_dev
            globals()[f"CURRENT_P{player_num_str}_CONTROLLER_DEVICE"] = default_ctrl_dev

    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings_by_guid", {}) if config_file_found_and_parsed else {}

    # Auto-assign joysticks if no config file was loaded (fresh start scenario)
    if not config_file_found_and_parsed:
        print("Config: Performing auto-assignment for joysticks (no config file).")
        available_joys_data = get_available_joystick_names_with_indices_and_guids()
        if available_joys_data:
            globals()["CURRENT_P1_CONTROLLER_DEVICE"] = available_joys_data[0][1] # P1 gets first joystick
            if globals()["CURRENT_P1_KEYBOARD_DEVICE"] == DEFAULT_P1_KEYBOARD_DEVICE : # if P1 kbd was default
                 globals()["CURRENT_P1_KEYBOARD_DEVICE"] = UNASSIGNED_DEVICE_ID # Prioritize controller
            if len(available_joys_data) > 1:
                globals()["CURRENT_P2_CONTROLLER_DEVICE"] = available_joys_data[1][1] # P2 gets second
                if globals()["CURRENT_P2_KEYBOARD_DEVICE"] == DEFAULT_P2_KEYBOARD_DEVICE:
                    globals()["CURRENT_P2_KEYBOARD_DEVICE"] = UNASSIGNED_DEVICE_ID

    # Conflict Resolution & Final Enabled Flag Derivation
    assigned_joystick_internal_ids: Dict[str, str] = {}
    assigned_keyboard_layout_ids: Dict[str, str] = {}

    for i in range(1, 5):
        player_prefix = f"P{i}"
        current_kbd_dev_var = f"CURRENT_{player_prefix}_KEYBOARD_DEVICE"
        current_ctrl_dev_var = f"CURRENT_{player_prefix}_CONTROLLER_DEVICE"

        current_kbd_val = globals()[current_kbd_dev_var]
        current_ctrl_val = globals()[current_ctrl_dev_var]

        # Validate and resolve controller conflicts
        if current_ctrl_val != UNASSIGNED_DEVICE_ID and current_ctrl_val.startswith("joystick_pygame_"):
            try:
                joy_idx = int(current_ctrl_val.split('_')[-1])
                is_valid_joystick = (0 <= joy_idx < _detected_joystick_count_global and
                                     _joystick_objects_global[joy_idx] is not None)
                if not is_valid_joystick:
                    print(f"Config Warning: {player_prefix}'s controller '{current_ctrl_val}' invalid/unavailable. Reverting to unassigned.")
                    globals()[current_ctrl_dev_var] = UNASSIGNED_DEVICE_ID
                elif current_ctrl_val in assigned_joystick_internal_ids:
                    other_player = assigned_joystick_internal_ids[current_ctrl_val]
                    print(f"Config Conflict: {player_prefix} and {other_player} assigned to same controller '{current_ctrl_val}'. Reverting {player_prefix}'s controller to unassigned.")
                    globals()[current_ctrl_dev_var] = UNASSIGNED_DEVICE_ID
                else:
                    assigned_joystick_internal_ids[current_ctrl_val] = player_prefix
            except (ValueError, IndexError): # Malformed ID
                print(f"Config Warning: {player_prefix}'s controller ID '{current_ctrl_val}' malformed. Reverting controller to unassigned.")
                globals()[current_ctrl_dev_var] = UNASSIGNED_DEVICE_ID

        # Validate and resolve keyboard conflicts (excluding "unassigned_keyboard" which is conceptual)
        if current_kbd_val != UNASSIGNED_DEVICE_ID and current_kbd_val != "unassigned_keyboard":
            if current_kbd_val in assigned_keyboard_layout_ids:
                other_player = assigned_keyboard_layout_ids[current_kbd_val]
                print(f"Config Conflict: {player_prefix} and {other_player} assigned to same keyboard layout '{current_kbd_val}'. Reverting {player_prefix}'s keyboard to unassigned.")
                globals()[current_kbd_dev_var] = UNASSIGNED_DEVICE_ID
            else:
                assigned_keyboard_layout_ids[current_kbd_val] = player_prefix

        # Derive enabled flags AFTER conflict resolution
        globals()[f"{player_prefix}_KEYBOARD_ENABLED"] = (globals()[current_kbd_dev_var] != UNASSIGNED_DEVICE_ID)
        globals()[f"{player_prefix}_CONTROLLER_ENABLED"] = (globals()[current_ctrl_dev_var] != UNASSIGNED_DEVICE_ID and
                                                          globals()[current_ctrl_dev_var].startswith("joystick_pygame_"))
        # print(f"Config Loaded/Resolved: {player_prefix} KbdDev='{globals()[current_kbd_dev_var]}', CtrlDev='{globals()[current_ctrl_dev_var]}', KbdEn={globals()[f'{player_prefix}_KEYBOARD_ENABLED']}, CtrlEn={globals()[f'{player_prefix}_CONTROLLER_ENABLED']}")


    # Determine the primary joystick GUID for runtime simulation mappings (used by GUI mapper)
    primary_joystick_guid_for_runtime_simulation: Optional[str] = None
    if globals()["CURRENT_P1_CONTROLLER_DEVICE"].startswith("joystick_pygame_") and globals()["P1_CONTROLLER_ENABLED"]:
        try:
            p1_sim_joy_idx = int(globals()["CURRENT_P1_CONTROLLER_DEVICE"].split('_')[-1])
            primary_joystick_guid_for_runtime_simulation = get_joystick_guid_by_pygame_index(p1_sim_joy_idx)
            # if primary_joystick_guid_for_runtime_simulation: print(f"Config: Using P1's controller (Idx {p1_sim_joy_idx}) for runtime simulation mappings.")
        except (ValueError, IndexError): pass
    if not primary_joystick_guid_for_runtime_simulation and _detected_joystick_count_global > 0 :
        if _joystick_objects_global[0] is not None: # Check if first joystick is valid
            primary_joystick_guid_for_runtime_simulation = get_joystick_guid_by_pygame_index(0)
        # if primary_joystick_guid_for_runtime_simulation: print(f"Config: Using first detected joystick (Idx 0) for runtime simulation mappings.")
    # if not primary_joystick_guid_for_runtime_simulation: print("Config: No suitable joystick for runtime simulation mappings. Will use generic defaults.")

    _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = _translate_gui_mappings_for_guid_to_runtime(
        LOADED_PYGAME_JOYSTICK_MAPPINGS, primary_joystick_guid_for_runtime_simulation
    )

    update_player_mappings_from_config()
    return True

def update_player_mappings_from_config():
    global P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS

    for i in range(1, 5):
        player_prefix = f"P{i}"
        mappings_var_name = f"{player_prefix}_MAPPINGS"
        current_mappings: Dict[str, Any] = {} # Start with empty mappings

        player_controller_device = globals()[f"CURRENT_{player_prefix}_CONTROLLER_DEVICE"]
        player_keyboard_device = globals()[f"CURRENT_{player_prefix}_KEYBOARD_DEVICE"]
        is_controller_enabled = globals()[f"{player_prefix}_CONTROLLER_ENABLED"]
        is_keyboard_enabled = globals()[f"{player_prefix}_KEYBOARD_ENABLED"]
        
        log_source = "unassigned"

        # Prioritize Controller if enabled and assigned
        if is_controller_enabled and player_controller_device != UNASSIGNED_DEVICE_ID and player_controller_device.startswith("joystick_pygame_"):
            try:
                joy_idx = int(player_controller_device.split('_')[-1])
                # Ensure joystick is valid before trying to get its GUID and mappings
                if 0 <= joy_idx < _detected_joystick_count_global and _joystick_objects_global[joy_idx] is not None:
                    guid = get_joystick_guid_by_pygame_index(joy_idx)
                    current_mappings = _translate_gui_mappings_for_guid_to_runtime(LOADED_PYGAME_JOYSTICK_MAPPINGS, guid)
                    log_source = f"controller '{player_controller_device}' (GUID: {guid})"
                else: # Controller assigned but not available
                    log_source = f"controller '{player_controller_device}' (unavailable)"
                    # Fall through to check keyboard if controller is not actually usable
            except (ValueError, IndexError) as e_joy:
                print(f"Config Error: Malformed controller ID '{player_controller_device}' for {player_prefix}: {e_joy}")
                log_source = f"controller '{player_controller_device}' (error)"
                # Fall through
        
        # If no controller mappings were set (or controller was invalid/unassigned), check keyboard
        if not current_mappings and is_keyboard_enabled and player_keyboard_device != UNASSIGNED_DEVICE_ID:
            if player_keyboard_device == "keyboard_p1":
                current_mappings = copy.deepcopy(DEFAULT_KEYBOARD_P1_MAPPINGS)
                log_source = f"keyboard '{player_keyboard_device}' (P1 default)"
            elif player_keyboard_device == "keyboard_p2":
                current_mappings = copy.deepcopy(DEFAULT_KEYBOARD_P2_MAPPINGS)
                log_source = f"keyboard '{player_keyboard_device}' (P2 default)"
            # Add more specific keyboard layouts if needed, e.g., "keyboard_generic_arrows"
            else: # Fallback for other named keyboard schemes, or default if "unassigned_keyboard" but enabled
                current_mappings = copy.deepcopy(DEFAULT_KEYBOARD_P1_MAPPINGS) # Default to P1 if unknown specific kbd
                log_source = f"keyboard '{player_keyboard_device}' (fallback/P1 default)"
        
        globals()[mappings_var_name] = current_mappings
        print(f"Config: {player_prefix} mappings updated from {log_source}. Count: {len(current_mappings)}")


# Initial load when module is imported
init_pygame_and_joystick_globally(force_rescan=True)
load_config()

if __name__ == "__main__":
    print("\n--- Running config.py directly for testing ---")
    print(f"\nDetected Joysticks ({_detected_joystick_count_global}):")
    for i_joy, name_joy in enumerate(_detected_joystick_names_global):
         joy_obj_test = _joystick_objects_global[i_joy] if i_joy < len(_joystick_objects_global) else None
         guid_test = "N/A"
         if joy_obj_test:
             try:
                 if not joy_obj_test.get_init(): joy_obj_test.init()
                 if hasattr(joy_obj_test, 'get_guid'): guid_test = joy_obj_test.get_guid()
             except pygame.error: pass
         print(f"    Idx {i_joy}: {name_joy} (GUID: {guid_test})")

    for i_player in range(1, 5):
        p_prefix = f"P{i_player}"
        print(f"{p_prefix}: KbdDev='{globals()[f'CURRENT_{p_prefix}_KEYBOARD_DEVICE']}', "
              f"CtrlDev='{globals()[f'CURRENT_{p_prefix}_CONTROLLER_DEVICE']}', "
              f"KbdEn={globals()[f'{p_prefix}_KEYBOARD_ENABLED']}, "
              f"CtrlEn={globals()[f'{p_prefix}_CONTROLLER_ENABLED']}, "
              f"JumpMap: {globals()[f'{p_prefix}_MAPPINGS'].get('jump', 'N/A')}, "
              f"MappingsCount: {len(globals()[f'{p_prefix}_MAPPINGS'])}")

    if _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME:
        print(f"Active Runtime Joystick Mappings (for GUI Sim): Count={len(_TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME)}")
    else: print("Active Runtime Joystick Mappings (for GUI Sim): Empty/Default Generic.")
    if LOADED_PYGAME_JOYSTICK_MAPPINGS: print(f"Loaded GUI Joystick Mappings (by GUID): {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} controller profile(s) mapped.")
    else: print("Loaded GUI Joystick Mappings: None.")

    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try: pygame.quit()
        except pygame.error: pass
    print("--- config.py direct test finished ---")