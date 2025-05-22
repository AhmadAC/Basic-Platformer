# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1/P2.
"""
# version 2.3.4 (Corrected NoneType check order in load_config)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
from PySide6.QtCore import Qt # For Qt.Key enums
import copy # For deepcopy

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
                    _detected_joystick_names_global.append(joy.get_name())
                    _joystick_objects_global.append(joy) 
                except pygame.error as e_joy_get:
                    print(f"Config Warning: Error getting info for joystick {i}: {e_joy_get}")
                    _joystick_objects_global.append(None)
            print(f"Config: Global scan/re-scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally(force_rescan=True)

# --- File Paths ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    MAPPINGS_AND_DEVICE_CHOICES_FILENAME
)

# --- Defaults ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P1_KEYBOARD_ENABLED = True
DEFAULT_P1_CONTROLLER_ENABLED = False

DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
DEFAULT_P2_KEYBOARD_ENABLED = False
DEFAULT_P2_CONTROLLER_ENABLED = False

AXIS_THRESHOLD_DEFAULT = 0.7

# --- Current Settings (Loaded from file or defaults) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED
P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED

CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED
P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED

# --- Game Actions & Mappings ---
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
    "jump": Qt.Key.Key_Space, "crouch": Qt.Key.Key_Control, "attack1": Qt.Key.Key_J, "attack2": Qt.Key.Key_K,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_L, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4,
    "projectile5": Qt.Key.Key_R, "projectile6": Qt.Key.Key_F, "projectile7": Qt.Key.Key_G,
    "reset": Qt.Key.Key_Backspace, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_4, "right": Qt.Key.Key_6, "up": Qt.Key.Key_8, "down": Qt.Key.Key_5,
    "jump": Qt.Key.Key_8, "crouch": Qt.Key.Key_2, "attack1": Qt.Key.Key_7, "attack2": Qt.Key.Key_9,
    "dash": Qt.Key.Key_Plus, "roll": Qt.Key.Key_Minus, "interact": Qt.Key.Key_Period,
    "projectile1": Qt.Key.Key_Home, "projectile2": Qt.Key.Key_End, "projectile3": Qt.Key.Key_PageUp,
    "projectile4": Qt.Key.Key_PageDown, "projectile5": Qt.Key.Key_Insert,
    "projectile6": Qt.Key.Key_ScrollLock, "projectile7": Qt.Key.Key_Pause,
    "reset": Qt.Key.Key_Delete, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_F11,
    "menu_up": Qt.Key.Key_F5, "menu_down": Qt.Key.Key_F6, "menu_left": Qt.Key.Key_F7, "menu_right": Qt.Key.Key_F8,
}

DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = { # RUNTIME Format
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

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {} # GUID -> {action: gui_storage_format}
_TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME: Dict[str, Any] = {} # {action: runtime_format} for primary joy
P1_MAPPINGS: Dict[str, Any] = {}
P2_MAPPINGS: Dict[str, Any] = {}

# --- Translation & Helper Functions ---
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
                joy_name = joy_obj.get_name()
                guid_str = joy_obj.get_guid() if hasattr(joy_obj, 'get_guid') else f"NO_GUID_IDX_{i}"
                internal_id = f"joystick_pygame_{i}"
                display_name = f"Joy {i}: {joy_name}"
                devices.append((display_name, internal_id, guid_str, i))
    return devices

def get_joystick_guid_by_pygame_index(pygame_index: int) -> Optional[str]:
    if 0 <= pygame_index < _detected_joystick_count_global:
        joy_obj = _joystick_objects_global[pygame_index]
        if joy_obj and hasattr(joy_obj, 'get_guid'): return joy_obj.get_guid()
        return f"NO_GUID_IDX_{pygame_index}"
    return None

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]:
    return _joystick_objects_global

# --- Load/Save ---
def save_config():
    global CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global LOADED_PYGAME_JOYSTICK_MAPPINGS

    data_to_save = {
        "config_version": "2.3.4",
        "player1_settings": {"input_device": CURRENT_P1_INPUT_DEVICE, "keyboard_enabled": P1_KEYBOARD_ENABLED, "controller_enabled": P1_CONTROLLER_ENABLED},
        "player2_settings": {"input_device": CURRENT_P2_INPUT_DEVICE, "keyboard_enabled": P2_KEYBOARD_ENABLED, "controller_enabled": P2_CONTROLLER_ENABLED},
        "joystick_mappings_by_guid": LOADED_PYGAME_JOYSTICK_MAPPINGS 
    }
    try:
        if not os.path.exists(CONTROLLER_SETTINGS_SUBDIR): os.makedirs(CONTROLLER_SETTINGS_SUBDIR)
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

    # Player 1 Settings
    p1_settings = raw_config_data.get("player1_settings", {})
    CURRENT_P1_INPUT_DEVICE = p1_settings.get("input_device", DEFAULT_P1_INPUT_DEVICE)
    if CURRENT_P1_INPUT_DEVICE is None: # Immediate None check
        print(f"Config Warning: P1 input_device was None. Reverting to default: {DEFAULT_P1_INPUT_DEVICE}")
        CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
    P1_KEYBOARD_ENABLED = p1_settings.get("keyboard_enabled", DEFAULT_P1_KEYBOARD_ENABLED)
    P1_CONTROLLER_ENABLED = p1_settings.get("controller_enabled", DEFAULT_P1_CONTROLLER_ENABLED)

    # Player 2 Settings
    p2_settings = raw_config_data.get("player2_settings", {})
    CURRENT_P2_INPUT_DEVICE = p2_settings.get("input_device", DEFAULT_P2_INPUT_DEVICE)
    if CURRENT_P2_INPUT_DEVICE is None: # Immediate None check
        print(f"Config Warning: P2 input_device was None. Reverting to default: {DEFAULT_P2_INPUT_DEVICE}")
        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    P2_KEYBOARD_ENABLED = p2_settings.get("keyboard_enabled", DEFAULT_P2_KEYBOARD_ENABLED)
    P2_CONTROLLER_ENABLED = p2_settings.get("controller_enabled", DEFAULT_P2_CONTROLLER_ENABLED)
    
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_config_data.get("joystick_mappings_by_guid", {})

    # Determine primary joystick GUID for runtime (e.g., P1's or first detected if P1 on kbd)
    primary_joystick_guid_for_runtime: Optional[str] = None
    if CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_") and P1_CONTROLLER_ENABLED:
        try:
            p1_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
            primary_joystick_guid_for_runtime = get_joystick_guid_by_pygame_index(p1_joy_idx)
        except (ValueError, IndexError): pass # Handled by validation later
    elif _detected_joystick_count_global > 0: # If P1 not on joystick, but one exists, use first one for general UI
        primary_joystick_guid_for_runtime = get_joystick_guid_by_pygame_index(0)
        
    _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = _translate_gui_mappings_for_guid_to_runtime(
        LOADED_PYGAME_JOYSTICK_MAPPINGS, primary_joystick_guid_for_runtime
    )

    # Auto-assignment and Validation (if no config file was found)
    if not raw_config_data:
        print("Config: No config file found. Attempting auto-assignment.")
        if _detected_joystick_count_global > 0:
            p1_idx = 0; p1_guid = get_joystick_guid_by_pygame_index(p1_idx)
            CURRENT_P1_INPUT_DEVICE = f"joystick_pygame_{p1_idx}"; P1_CONTROLLER_ENABLED = True
            _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = _translate_gui_mappings_for_guid_to_runtime(LOADED_PYGAME_JOYSTICK_MAPPINGS, p1_guid)
            if _detected_joystick_count_global > 1:
                CURRENT_P2_INPUT_DEVICE = f"joystick_pygame_1"; P2_CONTROLLER_ENABLED = True
            else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # P2 to kbd
        else: # No joysticks
            _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME = copy.deepcopy(DEFAULT_GENERIC_JOYSTICK_MAPPINGS)
            # P1/P2 already on defaults

    # Final validation and conflict resolution for device assignments
    for player_prefix, dev_var, ctrl_en_var, kbd_en_var, default_dev in [
        ("P1", "CURRENT_P1_INPUT_DEVICE", "P1_CONTROLLER_ENABLED", "P1_KEYBOARD_ENABLED", DEFAULT_P1_INPUT_DEVICE),
        ("P2", "CURRENT_P2_INPUT_DEVICE", "P2_CONTROLLER_ENABLED", "P2_KEYBOARD_ENABLED", DEFAULT_P2_INPUT_DEVICE)
    ]:
        current_dev = globals()[dev_var]
        if current_dev.startswith("joystick_pygame_"):
            try:
                joy_idx = int(current_dev.split('_')[-1])
                if not (0 <= joy_idx < _detected_joystick_count_global):
                    print(f"Config Warning: {player_prefix}'s joystick '{current_dev}' invalid. Reverting to default.")
                    globals()[dev_var] = default_dev
                    globals()[ctrl_en_var] = False; globals()[kbd_en_var] = True # Default to kbd enabled
            except: # Malformed
                globals()[dev_var] = default_dev
                globals()[ctrl_en_var] = False; globals()[kbd_en_var] = True
        
    if CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_") and CURRENT_P1_INPUT_DEVICE == CURRENT_P2_INPUT_DEVICE:
        print(f"Config Warning: P1 & P2 on same joystick '{CURRENT_P1_INPUT_DEVICE}'. P2 to default kbd.")
        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_CONTROLLER_ENABLED = False; P2_KEYBOARD_ENABLED = True
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1" and CURRENT_P2_INPUT_DEVICE == "keyboard_p1": CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
    elif CURRENT_P1_INPUT_DEVICE == "keyboard_p2" and CURRENT_P2_INPUT_DEVICE == "keyboard_p2": CURRENT_P1_INPUT_DEVICE = "keyboard_p1"

    update_player_mappings_from_config()
    print(f"Config Loaded: P1 Dev='{CURRENT_P1_INPUT_DEVICE}', KbdEn={P1_KEYBOARD_ENABLED}, CtrlEn={P1_CONTROLLER_ENABLED}")
    print(f"Config Loaded: P2 Dev='{CURRENT_P2_INPUT_DEVICE}', KbdEn={P2_KEYBOARD_ENABLED}, CtrlEn={P2_CONTROLLER_ENABLED}")
    return True

def update_player_mappings_from_config():
    global P1_MAPPINGS, P2_MAPPINGS
    
    def get_mappings_for_player(player_device_id: str, player_controller_enabled: bool, player_kbd_enabled: bool, default_kbd_map: Dict) -> Dict[str, Any]:
        if player_device_id.startswith("keyboard_") and player_kbd_enabled:
            if player_device_id == "keyboard_p1": return copy.deepcopy(DEFAULT_KEYBOARD_P1_MAPPINGS)
            if player_device_id == "keyboard_p2": return copy.deepcopy(DEFAULT_KEYBOARD_P2_MAPPINGS)
            return copy.deepcopy(default_kbd_map) # Fallback for "unassigned_keyboard"
        elif player_device_id.startswith("joystick_pygame_") and player_controller_enabled:
            try:
                joy_idx = int(player_device_id.split('_')[-1])
                guid = get_joystick_guid_by_pygame_index(joy_idx)
                return _translate_gui_mappings_for_guid_to_runtime(LOADED_PYGAME_JOYSTICK_MAPPINGS, guid)
            except: return copy.deepcopy(DEFAULT_GENERIC_JOYSTICK_MAPPINGS) # Fallback
        # If controller not enabled or kbd not enabled for kbd assignment, or unknown device
        if player_kbd_enabled: return copy.deepcopy(default_kbd_map) # Fallback to a keyboard map if kbd is allowed
        return {} # No valid input source

    P1_MAPPINGS = get_mappings_for_player(CURRENT_P1_INPUT_DEVICE, P1_CONTROLLER_ENABLED, P1_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P1_MAPPINGS)
    P2_MAPPINGS = get_mappings_for_player(CURRENT_P2_INPUT_DEVICE, P2_CONTROLLER_ENABLED, P2_KEYBOARD_ENABLED, DEFAULT_KEYBOARD_P2_MAPPINGS)
    
    print(f"Config: Player mappings updated. P1: '{CURRENT_P1_INPUT_DEVICE}', P2: '{CURRENT_P2_INPUT_DEVICE}'.")
    if not P1_MAPPINGS: print("Config Warning: P1 has no active mappings.")
    if not P2_MAPPINGS: print("Config Warning: P2 has no active mappings.")


# --- Initial Load ---
load_config()

# --- Test Block ---
if __name__ == "__main__":
    print("\n--- Running config.py directly for testing ---")
    init_pygame_and_joystick_globally(force_rescan=True) 
    load_config() 
    
    print(f"\nDetected Joysticks ({_detected_joystick_count_global}):")
    for i, name in enumerate(_detected_joystick_names_global):
        print(f"    Idx {i}: {name} (GUID: {get_joystick_guid_by_pygame_index(i)})")

    print(f"P1: Dev='{CURRENT_P1_INPUT_DEVICE}', KbdEn={P1_KEYBOARD_ENABLED}, CtrlEn={P1_CONTROLLER_ENABLED}, JumpMap: {P1_MAPPINGS.get('jump', 'N/A')}")
    print(f"P2: Dev='{CURRENT_P2_INPUT_DEVICE}', KbdEn={P2_KEYBOARD_ENABLED}, CtrlEn={P2_CONTROLLER_ENABLED}, JumpMap: {P2_MAPPINGS.get('jump', 'N/A')}")

    if _TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME:
        print(f"Active Runtime Joystick Mappings (Primary/Fallback): Count={len(_TRANSLATED_ACTIVE_JOYSTICK_MAPPINGS_RUNTIME)}")
    else: print("Active Runtime Joystick Mappings: Empty/Default.")
    
    if LOADED_PYGAME_JOYSTICK_MAPPINGS: print(f"Loaded GUI Joystick Mappings (by GUID): {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} controller(s) mapped.")
    else: print("Loaded GUI Joystick Mappings: None.")

    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("--- config.py direct test finished ---")