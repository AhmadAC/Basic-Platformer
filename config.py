# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1/P2.
"""
# version 2.3.6 (Added MAX_UI_CONTROLLERS_FOR_NAV and GRID_NAV constants)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame
from PySide6.QtCore import Qt
import copy

# --- General App Config ---
MAX_UI_CONTROLLERS_FOR_NAV = 2 # Max joysticks that can navigate UI (0, 1)
# For grid navigation in map select, using distinct values
# (Can also be defined in constants.py and imported if preferred)
GRID_NAV_UP = 100
GRID_NAV_DOWN = 101
GRID_NAV_LEFT = 102
GRID_NAV_RIGHT = 103


# --- Global Pygame State Variables (Managed by this module) ---
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

    if _joystick_initialized_globally:
        current_count = pygame.joystick.get_count()
        if force_rescan or current_count != _detected_joystick_count_global:
            print(f"Config: Joystick count changed or forced re-scan. Old: {_detected_joystick_count_global}, New: {current_count}")
            
            for joy_obj in _joystick_objects_global:
                if joy_obj and joy_obj.get_init():
                    try: joy_obj.quit()
                    except pygame.error: pass
            _joystick_objects_global.clear()
            _detected_joystick_names_global.clear()

            _detected_joystick_count_global = current_count
            for i in range(_detected_joystick_count_global):
                try:
                    joy = pygame.joystick.Joystick(i)
                    if not joy.get_init():
                        joy.init()
                    _detected_joystick_names_global.append(joy.get_name())
                    _joystick_objects_global.append(joy) 
                except pygame.error as e_joy_get:
                    print(f"Config Warning: Error getting info for joystick {i}: {e_joy_get}")
                    _joystick_objects_global.append(None) 
            print(f"Config: Global scan/re-scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally(force_rescan=True)

CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME
)

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P1_KEYBOARD_ENABLED = True
DEFAULT_P1_CONTROLLER_ENABLED = False

DEFAULT_P2_INPUT_DEVICE = "unassigned" 
DEFAULT_P2_KEYBOARD_ENABLED = False
DEFAULT_P2_CONTROLLER_ENABLED = False

DEFAULT_P3_INPUT_DEVICE = "unassigned"
DEFAULT_P3_KEYBOARD_ENABLED = False
DEFAULT_P3_CONTROLLER_ENABLED = False

DEFAULT_P4_INPUT_DEVICE = "unassigned"
DEFAULT_P4_KEYBOARD_ENABLED = False
DEFAULT_P4_CONTROLLER_ENABLED = False

AXIS_THRESHOLD_DEFAULT = 0.7

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

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Default)", "Keyboard (P2 Default)", "Keyboard (Unassigned)"]

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
P1_MAPPINGS: Dict[str, Any] = {}
P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}
P4_MAPPINGS: Dict[str, Any] = {}


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
        if not isinstance(hat_value, (tuple, list)) or len(hat_value) != 2: return None
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
            print(f"Config Translator: Translated {len(runtime_mappings)} mappings for GUID {target_guid}.")
            return runtime_mappings
        print(f"Config Translator: GUID {target_guid} translation empty. Using generic defaults.")
    elif target_guid: print(f"Config Translator: GUID {target_guid} not in loaded mappings. Using generic defaults.")
    else: print("Config Translator: No target GUID. Using generic defaults.")
    return copy.deepcopy(DEFAULT_GENERIC_JOYSTICK_MAPPINGS)

def get_active_runtime_joystick_mappings() -> Dict[str, Any]:
    return _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME.copy()

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    devices = []
    if _joystick_initialized_globally:
        for i in range(_detected_joystick_count_global):
            joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
            if joy_obj:
                if not joy_obj.get_init():
                    try: joy_obj.init()
                    except pygame.error: pass 

                joy_name = joy_obj.get_name()
                guid_str = None
                if joy_obj.get_init() and hasattr(joy_obj, 'get_guid'): 
                    guid_str = joy_obj.get_guid() 
                else:
                    guid_str = f"NO_GUID_IDX_{i}" 
                
                internal_id = f"joystick_pygame_{i}"
                display_name = f"Joy {i}: {joy_name}"
                devices.append((display_name, internal_id, guid_str, i))
    return devices

def get_joystick_guid_by_pygame_index(pygame_index: int) -> Optional[str]:
    if 0 <= pygame_index < _detected_joystick_count_global:
        joy_obj = _joystick_objects_global[pygame_index]
        if joy_obj :
            if not joy_obj.get_init(): 
                try: joy_obj.init()
                except pygame.error: pass
            if joy_obj.get_init() and hasattr(joy_obj, 'get_guid'): 
                return joy_obj.get_guid()
        return f"NO_GUID_IDX_{pygame_index}" 
    return None

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    return _joystick_objects_global


def save_config():
    global CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global CURRENT_P3_INPUT_DEVICE, P3_KEYBOARD_ENABLED, P3_CONTROLLER_ENABLED
    global CURRENT_P4_INPUT_DEVICE, P4_KEYBOARD_ENABLED, P4_CONTROLLER_ENABLED
    global LOADED_PYGAME_JOYSTICK_MAPPINGS

    data_to_save = {
        "config_version": "2.3.6", 
        "player1_settings": {"input_device": CURRENT_P1_INPUT_DEVICE, "keyboard_enabled": P1_KEYBOARD_ENABLED, "controller_enabled": P1_CONTROLLER_ENABLED},
        "player2_settings": {"input_device": CURRENT_P2_INPUT_DEVICE, "keyboard_enabled": P2_KEYBOARD_ENABLED, "controller_enabled": P2_CONTROLLER_ENABLED},
        "player3_settings": {"input_device": CURRENT_P3_INPUT_DEVICE, "keyboard_enabled": P3_KEYBOARD_ENABLED, "controller_enabled": P3_CONTROLLER_ENABLED},
        "player4_settings": {"input_device": CURRENT_P4_INPUT_DEVICE, "keyboard_enabled": P4_KEYBOARD_ENABLED, "controller_enabled": P4_CONTROLLER_ENABLED},
        "joystick_mappings_by_guid": LOADED_PYGAME_JOYSTICK_MAPPINGS 
    }
    try:
        settings_dir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(settings_dir): 
            os.makedirs(settings_dir)
            print(f"Config: Created directory {settings_dir}")

        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        load_config(called_from_save=True) 
        return True
    except IOError as e:
        print(f"Config Error: Saving settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}")
        return False

def load_config(called_from_save=False):
    global CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global CURRENT_P3_INPUT_DEVICE, P3_KEYBOARD_ENABLED, P3_CONTROLLER_ENABLED
    global CURRENT_P4_INPUT_DEVICE, P4_KEYBOARD_ENABLED, P4_CONTROLLER_ENABLED
    global LOADED_PYGAME_JOYSTICK_MAPPINGS, _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME

    if not called_from_save: init_pygame_and_joystick_globally(force_rescan=True)

    raw_config_data = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_config_data = json.load(f)
            print(f"Config: Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults."); raw_config_data = {}
    else: print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults.")

    def _load_player_setting(p_settings: Dict, key: str, default_val: Any) -> Any:
        val = p_settings.get(key, default_val)
        if val is None: 
            print(f"Config Warning: Loaded '{key}' as None. Reverting to default: {default_val}")
            return default_val
        return val

    player_vars_config = [
        ("player1_settings", "CURRENT_P1_INPUT_DEVICE", "P1_KEYBOARD_ENABLED", "P1_CONTROLLER_ENABLED", DEFAULT_P1_INPUT_DEVICE, DEFAULT_P1_KEYBOARD_ENABLED, DEFAULT_P1_CONTROLLER_ENABLED, "P1"),
        ("player2_settings", "CURRENT_P2_INPUT_DEVICE", "P2_KEYBOARD_ENABLED", "P2_CONTROLLER_ENABLED", DEFAULT_P2_INPUT_DEVICE, DEFAULT_P2_KEYBOARD_ENABLED, DEFAULT_P2_CONTROLLER_ENABLED, "P2"),
        ("player3_settings", "CURRENT_P3_INPUT_DEVICE", "P3_KEYBOARD_ENABLED", "P3_CONTROLLER_ENABLED", DEFAULT_P3_INPUT_DEVICE, DEFAULT_P3_KEYBOARD_ENABLED, DEFAULT_P3_CONTROLLER_ENABLED, "P3"),
        ("player4_settings", "CURRENT_P4_INPUT_DEVICE", "P4_KEYBOARD_ENABLED", "P4_CONTROLLER_ENABLED", DEFAULT_P4_INPUT_DEVICE, DEFAULT_P4_KEYBOARD_ENABLED, DEFAULT_P4_CONTROLLER_ENABLED, "P4"),
    ]

    for settings_key, dev_var_name, kbd_en_var_name, ctrl_en_var_name, \
        def_dev, def_kbd_en, def_ctrl_en, player_log_prefix in player_vars_config:
        
        p_settings = raw_config_data.get(settings_key, {})
        globals()[dev_var_name] = _load_player_setting(p_settings, "input_device", def_dev)
        globals()[kbd_en_var_name] = _load_player_setting(p_settings, "keyboard_enabled", def_kbd_en)
        globals()[ctrl_en_var_name] = _load_player_setting(p_settings, "controller_enabled", def_ctrl_en)
        print(f"Config Loaded: {player_log_prefix} Dev='{globals()[dev_var_name]}', KbdEn={globals()[kbd_en_var_name]}, CtrlEn={globals()[ctrl_en_var_name]}")


    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings_by_guid", {})

    primary_joystick_guid_for_runtime: Optional[str] = None
    if CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_") and P1_CONTROLLER_ENABLED:
        try:
            p1_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
            primary_joystick_guid_for_runtime = get_joystick_guid_by_pygame_index(p1_joy_idx)
        except (ValueError, IndexError): pass 
    elif _detected_joystick_count_global > 0: 
        primary_joystick_guid_for_runtime = get_joystick_guid_by_pygame_index(0)
        
    _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = _translate_gui_mappings_for_guid_to_runtime(
        LOADED_PYGAME_JOYSTICK_MAPPINGS, primary_joystick_guid_for_runtime
    )

    if not raw_config_data: 
        print("Config: No config file found. Performing auto-assignment.")
        available_joys = get_available_joystick_names_with_indices_and_guids()
        
        # P1 default: keyboard
        globals()["CURRENT_P1_INPUT_DEVICE"] = DEFAULT_P1_INPUT_DEVICE
        globals()["P1_KEYBOARD_ENABLED"] = DEFAULT_P1_KEYBOARD_ENABLED
        globals()["P1_CONTROLLER_ENABLED"] = DEFAULT_P1_CONTROLLER_ENABLED
        
        # P2 default: unassigned
        globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE
        globals()["P2_KEYBOARD_ENABLED"] = DEFAULT_P2_KEYBOARD_ENABLED
        globals()["P2_CONTROLLER_ENABLED"] = DEFAULT_P2_CONTROLLER_ENABLED
        
        # P3, P4 default: unassigned
        globals()["CURRENT_P3_INPUT_DEVICE"] = DEFAULT_P3_INPUT_DEVICE; globals()["P3_KEYBOARD_ENABLED"] = DEFAULT_P3_KEYBOARD_ENABLED; globals()["P3_CONTROLLER_ENABLED"] = DEFAULT_P3_CONTROLLER_ENABLED
        globals()["CURRENT_P4_INPUT_DEVICE"] = DEFAULT_P4_INPUT_DEVICE; globals()["P4_KEYBOARD_ENABLED"] = DEFAULT_P4_KEYBOARD_ENABLED; globals()["P4_CONTROLLER_ENABLED"] = DEFAULT_P4_CONTROLLER_ENABLED

        if available_joys:
            # If a joystick is present, P1 gets it IN ADDITION to keyboard if KbdEn is True
            # But the PRIMARY assignment changes.
            p1_joy_data = available_joys[0]
            CURRENT_P1_INPUT_DEVICE = p1_joy_data[1] 
            P1_CONTROLLER_ENABLED = True
            # P1_KEYBOARD_ENABLED remains as per its default (True)
            
            if len(available_joys) > 1:
                p2_joy_data = available_joys[1]
                CURRENT_P2_INPUT_DEVICE = p2_joy_data[1]
                P2_CONTROLLER_ENABLED = True
                P2_KEYBOARD_ENABLED = False # Default P2 kbd to False if joy assigned
        
        _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = _translate_gui_mappings_for_guid_to_runtime(
            LOADED_PYGAME_JOYSTICK_MAPPINGS, get_joystick_guid_by_pygame_index(0) if available_joys else None
        )


    assigned_joystick_indices: Dict[int, str] = {} 
    assigned_keyboard_layouts: Dict[str, str] = {} 

    for i in range(1, 5):
        player_prefix = f"P{i}"
        dev_var_name = f"CURRENT_{player_prefix}_INPUT_DEVICE"
        ctrl_en_var_name = f"{player_prefix}_CONTROLLER_ENABLED"
        kbd_en_var_name = f"{player_prefix}_KEYBOARD_ENABLED"
        default_dev_val = globals()[f"DEFAULT_{player_prefix}_INPUT_DEVICE"]
        default_kbd_en_val = globals()[f"DEFAULT_{player_prefix}_KEYBOARD_ENABLED"]
        
        current_dev = globals()[dev_var_name]
        
        is_ctrl_enabled = globals()[ctrl_en_var_name]
        is_kbd_enabled = globals()[kbd_en_var_name]

        if current_dev.startswith("joystick_pygame_"):
            if not is_ctrl_enabled: # Device is joystick, but controller not enabled for player
                print(f"Config Warning: {player_prefix} assigned joystick '{current_dev}' but controller use is disabled. Reverting {player_prefix} to default keyboard.")
                globals()[dev_var_name] = default_dev_val # e.g. "keyboard_p1" or "unassigned"
                globals()[kbd_en_var_name] = True # Enable keyboard for them
                current_dev = globals()[dev_var_name] # update current_dev for next checks

            try:
                joy_idx = int(current_dev.split('_')[-1])
                if not (0 <= joy_idx < _detected_joystick_count_global and _joystick_objects_global[joy_idx] is not None):
                    print(f"Config Warning: {player_prefix}'s joystick '{current_dev}' invalid/unavailable. Reverting to default.")
                    globals()[dev_var_name] = default_dev_val
                    globals()[ctrl_en_var_name] = False 
                    globals()[kbd_en_var_name] = default_kbd_en_val 
                    current_dev = globals()[dev_var_name]
                elif joy_idx in assigned_joystick_indices:
                    other_player = assigned_joystick_indices[joy_idx]
                    print(f"Config Conflict: {player_prefix} and {other_player} assigned to same joystick index {joy_idx}. Reverting {player_prefix} to default.")
                    globals()[dev_var_name] = default_dev_val
                    globals()[ctrl_en_var_name] = False
                    globals()[kbd_en_var_name] = default_kbd_en_val
                    current_dev = globals()[dev_var_name]
                else:
                    assigned_joystick_indices[joy_idx] = player_prefix
            except (ValueError, IndexError): # Malformed joystick_pygame_X string
                print(f"Config Warning: {player_prefix}'s joystick ID '{current_dev}' malformed. Reverting to default.")
                globals()[dev_var_name] = default_dev_val; globals()[ctrl_en_var_name] = False; globals()[kbd_en_var_name] = default_kbd_en_val
                current_dev = globals()[dev_var_name]

        if current_dev.startswith("keyboard_"):
            if not is_kbd_enabled and current_dev != "unassigned": # Device is kbd, but kbd not enabled
                 print(f"Config Warning: {player_prefix} assigned keyboard '{current_dev}' but keyboard use is disabled. Reverting {player_prefix} to 'unassigned'.")
                 globals()[dev_var_name] = f"DEFAULT_{player_prefix}_INPUT_DEVICE" # This should be 'unassigned' for P2,P3,P4
                 if player_prefix == "P1": globals()[kbd_en_var_name] = True # P1 kbd usually always available
                 current_dev = globals()[dev_var_name]

            if current_dev in assigned_keyboard_layouts:
                other_player = assigned_keyboard_layouts[current_dev]
                print(f"Config Conflict: {player_prefix} and {other_player} assigned to same keyboard layout '{current_dev}'.")
                # Attempt to assign P2 layout to current player if P1 took P1 default, and current is P2
                if current_dev == "keyboard_p1" and player_prefix != "P1": # Someone else took kbd_p1
                    if "keyboard_p2" not in assigned_keyboard_layouts:
                        print(f"Config Conflict Resolution: Assigning 'keyboard_p2' to {player_prefix}.")
                        globals()[dev_var_name] = "keyboard_p2"
                        assigned_keyboard_layouts["keyboard_p2"] = player_prefix
                    else: # keyboard_p2 also taken
                        print(f"Config Conflict Resolution: Reverting {player_prefix} to unassigned.")
                        globals()[dev_var_name] = DEFAULT_P2_INPUT_DEVICE # or PX_INPUT_DEVICE
                        globals()[kbd_en_var_name] = DEFAULT_P2_KEYBOARD_ENABLED
                # Similar logic if P2 took P2 default, and current is P1 etc.
                # For now, simpler: if conflict and not resolved, revert player with lower P number or just current
                elif player_prefix > assigned_keyboard_layouts[current_dev]: # Crude way to decide who keeps it
                     print(f"Config Conflict Resolution: Reverting {player_prefix} to default device.")
                     globals()[dev_var_name] = default_dev_val
                     globals()[kbd_en_var_name] = default_kbd_en_val
            elif current_dev != "unassigned_keyboard" and current_dev != "unassigned":
                assigned_keyboard_layouts[current_dev] = player_prefix
    
    update_player_mappings_from_config()
    return True

def update_player_mappings_from_config():
    global P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS # Include P3/P4
    
    player_configs = [
        (CURRENT_P1_INPUT_DEVICE, P1_CONTROLLER_ENABLED, P1_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P1_MAPPINGS, "P1"),
        (CURRENT_P2_INPUT_DEVICE, P2_CONTROLLER_ENABLED, P2_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P2_MAPPINGS, "P2"),
        (CURRENT_P3_INPUT_DEVICE, P3_CONTROLLER_ENABLED, P3_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P1_MAPPINGS, "P3"), # P3 defaults to P1 kbd layout for now
        (CURRENT_P4_INPUT_DEVICE, P4_CONTROLLER_ENABLED, P4_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P2_MAPPINGS, "P4")  # P4 defaults to P2 kbd layout for now
    ]
    
    player_map_vars = [P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS]

    for i, (player_device_id, player_controller_enabled, player_kbd_enabled, default_kbd_map, p_log_prefix) in enumerate(player_configs):
        mappings: Dict[str, Any] = {}
        log_msg_suffix = ""

        if player_device_id.startswith("keyboard_") and player_kbd_enabled:
            if player_device_id == "keyboard_p1": mappings = copy.deepcopy(DEFAULT_KEYBOARD_P1_MAPPINGS)
            elif player_device_id == "keyboard_p2": mappings = copy.deepcopy(DEFAULT_KEYBOARD_P2_MAPPINGS)
            else: mappings = copy.deepcopy(default_kbd_map) 
            log_msg_suffix = f" (kbd map: {player_device_id})"
        elif player_device_id.startswith("joystick_pygame_") and player_controller_enabled:
            try:
                joy_idx = int(player_device_id.split('_')[-1])
                guid = get_joystick_guid_by_pygame_index(joy_idx)
                mappings = _translate_gui_mappings_for_guid_to_runtime(LOADED_PYGAME_JOYSTICK_MAPPINGS, guid)
                log_msg_suffix = f" (joy map for GUID: {guid})"
            except: 
                mappings = copy.deepcopy(DEFAULT_GENERIC_JOYSTICK_MAPPINGS) 
                log_msg_suffix = " (joy map: generic default due to error)"
        elif player_device_id == "unassigned":
            log_msg_suffix = " (unassigned)"
            # If KBD is enabled even if device is unassigned, provide a default keyboard map
            # This primarily benefits P1 if it somehow becomes "unassigned" but keyboard is still true.
            if player_kbd_enabled:
                mappings = copy.deepcopy(default_kbd_map)
                log_msg_suffix += f" but kbd enabled, using default kbd map"

        globals()[f"P{i+1}_MAPPINGS"] = mappings # P1_MAPPINGS, P2_MAPPINGS etc.
        
        print(f"Config: {p_log_prefix} mappings updated. Device: '{player_device_id}'{log_msg_suffix}.")
        if not mappings and player_device_id != "unassigned": 
            print(f"Config Warning: {p_log_prefix} has no active mappings despite assignment.")


init_pygame_and_joystick_globally(force_rescan=True) # Initial scan
load_config()

if __name__ == "__main__":
    print("\n--- Running config.py directly for testing ---")
    
    print(f"\nDetected Joysticks ({_detected_joystick_count_global}):")
    for i, name in enumerate(_detected_joystick_names_global):
         joy_obj_test = _joystick_objects_global[i]
         guid_test = "N/A"
         if joy_obj_test:
             if not joy_obj_test.get_init(): joy_obj_test.init() # Ensure init for GUID
             if joy_obj_test.get_init() and hasattr(joy_obj_test, 'get_guid'): guid_test = joy_obj_test.get_guid()
         print(f"    Idx {i}: {name} (GUID: {guid_test})")

    print(f"P1: Dev='{CURRENT_P1_INPUT_DEVICE}', KbdEn={P1_KEYBOARD_ENABLED}, CtrlEn={P1_CONTROLLER_ENABLED}, JumpMap: {P1_MAPPINGS.get('jump', 'N/A')}")
    print(f"P2: Dev='{CURRENT_P2_INPUT_DEVICE}', KbdEn={P2_KEYBOARD_ENABLED}, CtrlEn={P2_CONTROLLER_ENABLED}, JumpMap: {P2_MAPPINGS.get('jump', 'N/A')}")
    print(f"P3: Dev='{CURRENT_P3_INPUT_DEVICE}', KbdEn={P3_KEYBOARD_ENABLED}, CtrlEn={P3_CONTROLLER_ENABLED}, JumpMap: {P3_MAPPINGS.get('jump', 'N/A')}")
    print(f"P4: Dev='{CURRENT_P4_INPUT_DEVICE}', KbdEn={P4_KEYBOARD_ENABLED}, CtrlEn={P4_CONTROLLER_ENABLED}, JumpMap: {P4_MAPPINGS.get('jump', 'N/A')}")


    if _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME:
        print(f"Active Runtime Joystick Mappings (Primary/Fallback): Count={len(_TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME)}")
    else: print("Active Runtime Joystick Mappings: Empty/Default.")
    
    if LOADED_PYGAME_JOYSTICK_MAPPINGS: print(f"Loaded GUI Joystick Mappings (by GUID): {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} controller(s) mapped.")
    else: print("Loaded GUI Joystick Mappings: None.")

    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("--- config.py direct test finished ---")