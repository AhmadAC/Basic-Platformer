# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Assumes Pygame is the SOLE library for controller/joystick input for its own purposes.
The external controller_mappings.json is used for Pygame control mappings.
"""
# version 2.1.5 (Direct Pygame use, robust JSON translation)
# version 2.1.6 (Ensure Pygame init is robust, fix P2 keyboard projectile keys)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
from PySide6.QtCore import Qt # For Qt.Key enums

# --- Initialize Pygame Joystick (Required before calling its functions within this module) ---
_pygame_initialized = False
_joystick_initialized = False
try:
    pygame.init()
    _pygame_initialized = True
    pygame.joystick.init()
    _joystick_initialized = True
    print("Config: Pygame and Pygame Joystick initialized successfully by config.py.")
except Exception as e:
    print(f"Config Error: Failed to initialize Pygame/Pygame Joystick in config.py: {e}.")
    if _pygame_initialized and not _joystick_initialized:
        print("Config Warning: Pygame general init succeeded, but joystick init failed.")
    # Application will continue, but joystick functionality might be impaired.

# --- File for saving/loading game config (selected devices) ---
CONFIG_FILE_NAME = "game_config_pygame.json"

# --- Path for external controller mappings (Pygame specific) ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
EXTERNAL_CONTROLLER_MAPPINGS_FILENAME = "controller_mappings.json" # This is the GUI's output
EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    EXTERNAL_CONTROLLER_MAPPINGS_FILENAME
)

# --- Default Control Schemes ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"

# --- Current Control Scheme ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE

# --- Joystick Axis Thresholds ---
AXIS_THRESHOLD_DEFAULT = 0.7

# --- Game Actions (Internal names the game logic uses) ---
GAME_ACTIONS = [
    "left", "right", "up", "down",
    "jump", "crouch",
    "attack1", "attack2",
    "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]

# --- Mapping from controller_mappings.json keys (MAPPABLE_KEYS from GUI) to internal GAME_ACTIONS ---
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP": "jump", "CROUCH": "crouch", "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1", "ATTACK_SECONDARY": "attack2",
    "DASH": "dash", "ROLL": "roll", "RESET": "reset",
    "WEAPON_1": "projectile1", "WEAPON_2": "projectile2", "WEAPON_3": "projectile3", "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", # Example: DPad Up can also be Weapon 4
    "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6",
    "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause",
    # Direct keyboard key to action (if GUI allows mapping raw keys, though abstract actions are preferred)
    "W": "up", "A": "left", "S": "down", "D": "right",
    "1": "projectile1", "2": "projectile2", "3": "projectile3", "4": "projectile4", "5": "projectile5",
    "Q": "reset", "E": "interact", "V": "attack1", "B": "attack2",
    "SPACE": "jump", "SHIFT": "dash", "CTRL": "roll", # Note: Roll and Crouch might share Ctrl
}


# --- Default Keyboard Mappings using Qt.Key enums ---
DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W,
    "crouch": Qt.Key.Key_S,
    "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3,
    "projectile4": Qt.Key.Key_4, "projectile5": Qt.Key.Key_5,
    "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7, # Added 6 and 7
    "reset": Qt.Key.Key_Q,
    "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down,
    "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}

DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I,
    "crouch": Qt.Key.Key_K,
    "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_8, # Mapped to 8, 9, 0, -, = as examples for P2
    "projectile2": Qt.Key.Key_9,
    "projectile3": Qt.Key.Key_0,
    "projectile4": Qt.Key.Key_Minus,
    "projectile5": Qt.Key.Key_Equal,
    "projectile6": Qt.Key.Key_BracketLeft, # Example for P2 projectile 6
    "projectile7": Qt.Key.Key_BracketRight, # Example for P2 projectile 7
    "reset": Qt.Key.Key_Period, # Example for P2 reset
    "pause": Qt.Key.Key_Pause,
    "menu_confirm": Qt.Key.Key_Enter, # Qt.Key_Enter can represent main or numpad enter
    "menu_cancel": Qt.Key.Key_Delete, # Could also use another key
    "menu_up": Qt.Key.Key_PageUp,
    "menu_down": Qt.Key.Key_PageDown,
    "menu_left": Qt.Key.Key_Home,
    "menu_right": Qt.Key.Key_End,
}

# --- Default Pygame Joystick Mappings (Fallback if JSON load fails or is incomplete) ---
DEFAULT_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, # Typically A/Cross
    "crouch": {"type": "button", "id": 1}, # Typically B/Circle
    "attack1": {"type": "button", "id": 2}, # Typically X/Square
    "attack2": {"type": "button", "id": 3}, # Typically Y/Triangle
    "dash": {"type": "button", "id": 5}, # Typically Right Bumper
    "roll": {"type": "button", "id": 4}, # Typically Left Bumper
    "interact": {"type": "button", "id": 10}, # Could be Right Stick Button (R3) or other
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)},  # D-Pad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},  # D-Pad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, # D-Pad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)}, # D-Pad Left
    "projectile5": {"type": "button", "id": 8}, # Example: Left Trigger (often an axis, check GUI output)
    "projectile6": {"type": "button", "id": 9}, # Example: Right Trigger (often an axis)
    "projectile7": {"type": "button", "id": 11},# Example: Right Stick Button (R3)
    "reset": {"type": "button", "id": 6}, # Often 'Back' or 'Select' or 'Share'
    "pause": {"type": "button", "id": 7}, # Often 'Start' or 'Options' or 'Menu'
    "menu_confirm": {"type": "button", "id": 0},
    "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {}
P1_MAPPINGS: Dict[str, Any] = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS: Dict[str, Any] = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_mappings: Any) -> Dict[str, Any]:
    translated_mappings: Dict[str, Any] = {}
    if not isinstance(raw_gui_json_mappings, dict):
        print("Config Error: Raw GUI JSON mappings from controller_mappings.json is not a dictionary.")
        return {}

    for gui_action_key, mapping_entry in raw_gui_json_mappings.items():
        internal_action_name = EXTERNAL_TO_INTERNAL_ACTION_MAP.get(gui_action_key)
        if not internal_action_name:
            if gui_action_key in GAME_ACTIONS: # If the GUI key is already an internal game action name
                internal_action_name = gui_action_key
            else:
                # print(f"Config Debug: Skipping unknown GUI action key '{gui_action_key}' during translation.")
                continue # Skip unmappable GUI keys

        if not isinstance(mapping_entry, dict):
            print(f"Config Warning: Mapping entry for '{gui_action_key}' in JSON is not a dict. Skipping.")
            continue

        pygame_event_type = mapping_entry.get("event_type") # e.g., "button", "axis", "hat"
        details = mapping_entry.get("details") # This is the sub-dictionary from the GUI JSON

        if not isinstance(details, dict):
            print(f"Config Warning: 'details' sub-dictionary missing or not a dict for '{gui_action_key}'. Skipping.")
            continue
        
        pygame_event_id = None
        if pygame_event_type == "button": pygame_event_id = details.get("button_id")
        elif pygame_event_type == "axis": pygame_event_id = details.get("axis_id")
        elif pygame_event_type == "hat": pygame_event_id = details.get("hat_id")

        if pygame_event_type not in ["button", "axis", "hat"] or pygame_event_id is None:
            # print(f"Config Warning: Invalid event_type ('{pygame_event_type}') or missing ID for '{gui_action_key}'. Skipping.")
            continue

        try:
            final_mapping_for_action: Dict[str, Any] = {"type": pygame_event_type, "id": int(pygame_event_id)}
        except ValueError:
            print(f"Config Warning: Invalid non-integer ID '{pygame_event_id}' for '{gui_action_key}' of type '{pygame_event_type}'. Skipping.")
            continue


        if pygame_event_type == "axis":
            axis_direction = details.get("direction") # Expected -1 or 1
            axis_threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_direction not in [-1, 1]:
                print(f"Config Warning: Invalid axis 'direction' ({axis_direction}) for '{gui_action_key}'. Skipping.")
                continue
            final_mapping_for_action["value"] = axis_direction
            final_mapping_for_action["threshold"] = float(axis_threshold)
        elif pygame_event_type == "hat":
            hat_value_from_details = details.get("value") # Expected list/tuple [x, y]
            if not isinstance(hat_value_from_details, (tuple, list)) or len(hat_value_from_details) != 2:
                print(f"Config Warning: Invalid hat 'value' ({hat_value_from_details}) for '{gui_action_key}'. Skipping.")
                continue
            final_mapping_for_action["value"] = tuple(map(int, hat_value_from_details)) # Ensure int tuple
        
        translated_mappings[internal_action_name] = final_mapping_for_action
    return translated_mappings


def _load_external_pygame_joystick_mappings() -> bool:
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    LOADED_PYGAME_JOYSTICK_MAPPINGS = {} # Reset
    if not os.path.exists(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH):
        print(f"Config Info: Controller mappings file '{EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH}' not found. Using default Pygame joystick mappings.")
        return False
    try:
        with open(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH, 'r') as f:
            raw_gui_json_mappings = json.load(f)
        LOADED_PYGAME_JOYSTICK_MAPPINGS = _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_mappings)
        if LOADED_PYGAME_JOYSTICK_MAPPINGS:
            print(f"Config: Loaded {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} Pygame joystick mappings from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}'.")
            return True
        else:
            print(f"Config Warning: JSON from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}' resulted in empty/invalid mappings. Using defaults.")
            return False
    except Exception as e:
        print(f"Config Error: Loading/translating Pygame mappings from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using defaults.")
        LOADED_PYGAME_JOYSTICK_MAPPINGS = {}
        return False

def get_action_key_map(player_id: int, device_id_str: str) -> Dict[str, Any]:
    # This function is kept for potential direct calls but primary update is via update_player_mappings_from_device_choice
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick_pygame_"):
        return LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
    print(f"Config Warning: get_action_key_map called with unknown device_id_str: {device_id_str}")
    return {}

def _get_config_filepath() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config() -> bool:
    config_data = {
        "p1_input_device": CURRENT_P1_INPUT_DEVICE,
        "p2_input_device": CURRENT_P2_INPUT_DEVICE
    }
    filepath = _get_config_filepath()
    try:
        with open(filepath, 'w') as f: json.dump(config_data, f, indent=4)
        print(f"Config: Configuration saved to {filepath}")
        return True
    except IOError as e:
        print(f"Config Error: Saving configuration to {filepath}: {e}")
        return False

def load_config() -> bool:
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE

    _load_external_pygame_joystick_mappings() # Populates LOADED_PYGAME_JOYSTICK_MAPPINGS

    filepath = _get_config_filepath()
    loaded_p1_device_choice = DEFAULT_P1_INPUT_DEVICE
    loaded_p2_device_choice = DEFAULT_P2_INPUT_DEVICE

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f: config_data = json.load(f)
            loaded_p1_device_choice = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2_device_choice = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
            print(f"Config: Loaded device choices from {filepath}: P1='{loaded_p1_device_choice}', P2='{loaded_p2_device_choice}'")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {filepath}: {e}. Using default device choices.")
    else:
        print(f"Config: Config file {filepath} not found. Using default device choices.")


    num_joysticks = 0
    if _joystick_initialized: # Only attempt to get count if joystick system initialized
        try: num_joysticks = pygame.joystick.get_count()
        except pygame.error as e_joy_count:
            print(f"Config Warning: Pygame error getting joystick count: {e_joy_count}. Assuming 0 joysticks.")
    else: print("Config Info: Pygame joystick system not initialized. Assuming 0 joysticks.")
        
    print(f"Config: Pygame reported {num_joysticks} joysticks available for assignment.")

    # Player 1 Device Assignment Logic
    if loaded_p1_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            print(f"Config Info: P1 saved '{loaded_p1_device_choice}' but no joysticks. Fallback to P1 keyboard.")
            CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
        else:
            try:
                p1_joy_idx = int(loaded_p1_device_choice.split('_')[-1])
                if not (0 <= p1_joy_idx < num_joysticks):
                    print(f"Config Warn: P1 joystick ID {p1_joy_idx} unavailable (max {num_joysticks-1}). Assigning joystick_pygame_0.")
                    CURRENT_P1_INPUT_DEVICE = "joystick_pygame_0"
                else: CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice
            except (ValueError, IndexError):
                print(f"Config Warn: Malformed P1 joystick ID '{loaded_p1_device_choice}'. Assigning joystick_pygame_0 if available.")
                CURRENT_P1_INPUT_DEVICE = "joystick_pygame_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
    else: CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice

    # Player 2 Device Assignment Logic
    if loaded_p2_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            print(f"Config Info: P2 saved '{loaded_p2_device_choice}' but no joysticks. Fallback to P2 keyboard.")
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
        else:
            try:
                p2_joy_idx = int(loaded_p2_device_choice.split('_')[-1])
                p1_is_pygame_joy = CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_")
                p1_current_joy_idx = -1
                if p1_is_pygame_joy:
                    try: p1_current_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                    except: p1_is_pygame_joy = False

                if not (0 <= p2_joy_idx < num_joysticks): # P2's saved ID invalid
                    print(f"Config Warn: P2 joystick ID {p2_joy_idx} unavailable. Auto-assigning.")
                    if num_joysticks == 1 and p1_is_pygame_joy and p1_current_joy_idx == 0: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                    elif num_joysticks > 0 and (not p1_is_pygame_joy or p1_current_joy_idx != 0): CURRENT_P2_INPUT_DEVICE = "joystick_pygame_0"
                    elif num_joysticks > 1 and p1_is_pygame_joy and p1_current_joy_idx == 0: CURRENT_P2_INPUT_DEVICE = "joystick_pygame_1"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                elif p1_is_pygame_joy and p2_joy_idx == p1_current_joy_idx: # Conflict
                    print(f"Config Warn: P2 cannot use same joystick as P1 (ID {p1_current_joy_idx}). Auto-assigning.")
                    if num_joysticks > 1: CURRENT_P2_INPUT_DEVICE = f"joystick_pygame_{1 if p1_current_joy_idx == 0 else 0}"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                else: CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
            except (ValueError, IndexError):
                print(f"Config Warn: Malformed P2 joystick ID '{loaded_p2_device_choice}'. Assigning default.")
                CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    else: # P2 is keyboard
        if loaded_p2_device_choice == CURRENT_P1_INPUT_DEVICE and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            print("Config Warn: P1 & P2 want 'keyboard_p1'. Assigning 'keyboard_p2' to P2.")
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # Default P2 keyboard
        else: CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice

    print(f"Config: Final device assignments: P1='{CURRENT_P1_INPUT_DEVICE}', P2='{CURRENT_P2_INPUT_DEVICE}'")
    update_player_mappings_from_device_choice()
    return True

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS

    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_"):
        P1_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_p1 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK"
        print(f"Config: P1 assigned Pygame joystick mappings {status_p1} ({len(P1_MAPPINGS)} actions).")
    else: P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick_pygame_"):
        P2_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_p2 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK"
        print(f"Config: P2 assigned Pygame joystick mappings {status_p2} ({len(P2_MAPPINGS)} actions).")
    else: P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

    print(f"Config: Player mappings updated. P1 using '{CURRENT_P1_INPUT_DEVICE}' with {len(P1_MAPPINGS)} mappings, P2 using '{CURRENT_P2_INPUT_DEVICE}' with {len(P2_MAPPINGS)} mappings.")

if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    load_config()
    print(f"\nAfter test load_config():")
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  P1_MAPPINGS sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    print(f"  P2_MAPPINGS sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")

    if LOADED_PYGAME_JOYSTICK_MAPPINGS:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS (first 5 or all):")
        for i, (k, v) in enumerate(LOADED_PYGAME_JOYSTICK_MAPPINGS.items()):
            if i >= 5: print(f"    ... and {len(LOADED_PYGAME_JOYSTICK_MAPPINGS) - 5} more."); break
            print(f"    '{k}': {v}")
    else:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS: Not loaded. Using defaults.")
        print(f"  DEFAULT_PYGAME_JOYSTICK_MAPPINGS (jump): {DEFAULT_PYGAME_JOYSTICK_MAPPINGS.get('jump')}")

    if _pygame_initialized:
        if _joystick_initialized: pygame.joystick.quit()
        pygame.quit()
    print("--- config.py direct test finished ---")