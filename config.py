# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Assumes Pygame is the SOLE library for controller/joystick input for its own purposes.
The external controller_mappings.json is used for Pygame control mappings.
"""
# version 2.1.5 (Direct Pygame use, robust JSON translation)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
from PySide6.QtCore import Qt # <<< ADD THIS IMPORT

# --- Initialize Pygame Joystick (Required before calling its functions within this module) ---
try:
    pygame.init() # General Pygame init
    pygame.joystick.init() # Specifically init joysticks for this module's needs (e.g., get_count)
    print("Config: Pygame and Pygame Joystick initialized successfully by config.py.")
except Exception as e:
    print(f"Config Error: Failed to initialize Pygame/Pygame Joystick in config.py: {e}.")


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
    "MOVE_UP": "up", "MOVE_DOWN": "down", "MOVE_LEFT": "left", "MOVE_RIGHT": "right",
    "JUMP": "jump", "CROUCH": "crouch", "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1", "ATTACK_SECONDARY": "attack2",
    "DASH": "dash", "ROLL": "roll", "RESET": "reset",
    "WEAPON_1": "projectile1", "WEAPON_2": "projectile2", "WEAPON_3": "projectile3", "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4",
    "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6",
    "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause",
    "W": "up", "A": "left", "S": "down", "D": "right",
    "1": "projectile1", "2": "projectile2", "3": "projectile3", "4": "projectile4", "5": "projectile5",
    "Q": "reset", "E": "interact", "V": "attack1", "B": "attack2",
    "SPACE": "jump", "SHIFT": "dash", "CTRL": "roll", # Example, could be crouch too
    # Note: "ALT" is not directly mapped to a game action here, but was in MAPPABLE_KEYS
}


# --- Default Keyboard Mappings ---
# MODIFIED TO USE Qt.Key enums
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, # Often 'up' also serves as jump
    "crouch": Qt.Key.Key_S, # Often 'down' also serves as crouch
    "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3,
    "projectile4": Qt.Key.Key_4, "projectile5": Qt.Key.Key_5,
    "reset": Qt.Key.Key_Q, # "projectile6" was "Num+6", "projectile7" was "7" - check consistency or remove if not used.
                           # Assuming projectile6 and 7 are not standard for P1 keyboard or will be mapped via GUI
    "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down,
    "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right,
}

DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K,
    "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_unknown, # Placeholder, Qt doesn't have direct Num+1. Use specific number keys.
    "projectile2": Qt.Key.Key_unknown, # Consider mapping to 7,8,9,0,-,= for P2 if numpad isn't ideal
    "projectile3": Qt.Key.Key_unknown,
    "projectile4": Qt.Key.Key_unknown,
    "projectile5": Qt.Key.Key_unknown,
    "reset": Qt.Key.Key_unknown,
    "pause": Qt.Key.Key_Pause,
    "menu_confirm": Qt.Key.Key_Enter, # Often Numpad Enter is also mapped to general Enter
    "menu_cancel": Qt.Key.Key_Delete,
    "menu_up": Qt.Key.Key_PageUp,    # Example alternative for Numpad 8
    "menu_down": Qt.Key.Key_PageDown,  # Example alternative for Numpad 2
    "menu_left": Qt.Key.Key_Home,    # Example alternative for Numpad 4
    "menu_right": Qt.Key.Key_End,     # Example alternative for Numpad 6
}
# Note on P2 Numpad: Qt.Key doesn't distinguish well between numpad numbers and top-row numbers
# when NumLock is on. Qt.Key_0 to Qt.Key_9 usually refer to top-row.
# For distinct numpad keys, you might need to check event.nativeScanCode() or event.text()
# if NumLock is on/off, which is more complex.
# Using other distinct keys for P2 is safer if full numpad distinction is crucial.
# For now, I've put Qt.Key_unknown for P2 projectile keys that were "Num+X".
# These would need to be remapped in your controller_mapper_gui or to other keys.
# A common P2 setup might use U,H,J,K for movement and surrounding keys for actions.

# --- Default Pygame Joystick Mappings (Fallback if JSON load fails or is incomplete) ---
DEFAULT_PYGAME_JOYSTICK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0},
    "crouch": {"type": "button", "id": 1},
    "attack1": {"type": "button", "id": 2},
    "attack2": {"type": "button", "id": 3},
    "dash": {"type": "button", "id": 5},
    "roll": {"type": "button", "id": 4},
    "interact": {"type": "button", "id": 10}, # Often 'Y' or Triangle
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)},  # D-Pad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},  # D-Pad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, # D-Pad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)}, # D-Pad Left
    "projectile5": {"type": "button", "id": 8}, # Example: Left Bumper
    "projectile6": {"type": "button", "id": 9}, # Example: Right Bumper
    "projectile7": {"type": "button", "id": 11},# Often 'Start' or 'Options' but can vary
    "reset": {"type": "button", "id": 6}, # Often 'Back' or 'Select'
    "pause": {"type": "button", "id": 7}, # Often 'Start' or 'Options'
    "menu_confirm": {"type": "button", "id": 0}, # Pygame Button 0 (A/Cross)
    "menu_cancel": {"type": "button", "id": 1},  # Pygame Button 1 (B/Circle)
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {}
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

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
                continue

        if not isinstance(mapping_entry, dict):
            print(f"Config Warning: Mapping entry for '{gui_action_key}' in JSON is not a dict. Skipping.")
            continue

        pygame_event_type = mapping_entry.get("event_type") # e.g., "button", "axis", "hat"
        details = mapping_entry.get("details") # This is the sub-dictionary from the GUI JSON

        if not isinstance(details, dict):
            print(f"Config Warning: 'details' sub-dictionary missing or not a dict for '{gui_action_key}'. Skipping.")
            continue
        
        # Get the Pygame ID based on the type within 'details'
        pygame_event_id = None
        if pygame_event_type == "button":
            pygame_event_id = details.get("button_id")
        elif pygame_event_type == "axis":
            pygame_event_id = details.get("axis_id")
        elif pygame_event_type == "hat":
            pygame_event_id = details.get("hat_id")

        if pygame_event_type not in ["button", "axis", "hat"] or pygame_event_id is None:
            # print(f"Config Warning: Invalid event_type ('{pygame_event_type}') or missing ID for '{gui_action_key}'. Skipping.")
            continue

        final_mapping_for_action: Dict[str, Any] = {"type": pygame_event_type, "id": int(pygame_event_id)}

        if pygame_event_type == "axis":
            axis_direction = details.get("direction") # Expected -1 or 1 from GUI's "details"
            axis_threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_direction not in [-1, 1]:
                print(f"Config Warning: Invalid axis 'direction' ({axis_direction}) in details for '{gui_action_key}'. Skipping.")
                continue
            final_mapping_for_action["value"] = axis_direction # Pygame mapping uses 'value' for direction
            final_mapping_for_action["threshold"] = float(axis_threshold)
        elif pygame_event_type == "hat":
            hat_value_from_details = details.get("value") # Expected list/tuple [x, y] from GUI's "details"
            if not isinstance(hat_value_from_details, (tuple, list)) or len(hat_value_from_details) != 2:
                print(f"Config Warning: Invalid hat 'value' ({hat_value_from_details}) in details for '{gui_action_key}'. Skipping.")
                continue
            final_mapping_for_action["value"] = tuple(hat_value_from_details)
        
        translated_mappings[internal_action_name] = final_mapping_for_action
        # print(f"Config Debug: Translated '{gui_action_key}' to internal '{internal_action_name}': {final_mapping_for_action}")

    return translated_mappings


def _load_external_pygame_joystick_mappings() -> bool:
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    LOADED_PYGAME_JOYSTICK_MAPPINGS = {} # Reset before loading
    if not os.path.exists(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH):
        print(f"Config Info: Controller mappings file (GUI output) '{EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH}' not found. Will use default Pygame joystick mappings.")
        return False
    try:
        with open(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH, 'r') as f:
            raw_gui_json_mappings = json.load(f)

        LOADED_PYGAME_JOYSTICK_MAPPINGS = _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_mappings)

        if LOADED_PYGAME_JOYSTICK_MAPPINGS:
            print(f"Config: Successfully loaded and translated {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} Pygame joystick mappings from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}'.")
            return True
        else:
            print(f"Config Warning: Loaded JSON from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}' (GUI output) but resulted in empty/invalid mappings after translation. Will use default Pygame joystick mappings.")
            return False
    except Exception as e:
        print(f"Config Error: Error loading/translating Pygame mappings (GUI output) from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Will use default Pygame joystick mappings.")
        LOADED_PYGAME_JOYSTICK_MAPPINGS = {} # Ensure it's empty on error
        return False

def get_action_key_map(player_id: int, device_id_str: str) -> Dict[str, Any]:
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick_pygame_"):
        # Use loaded mappings if available, otherwise default Pygame mappings
        return LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
    print(f"Config Warning: get_action_key_map called with unknown device_id_str: {device_id_str}")
    return {} # Return empty dict for unknown device

def _get_config_filepath() -> str:
    # Ensure this path is correct relative to your project structure
    # If config.py is in the root, this is fine. If in a subdir, adjust.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config() -> bool:
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    config_data = {
        "p1_input_device": CURRENT_P1_INPUT_DEVICE,
        "p2_input_device": CURRENT_P2_INPUT_DEVICE
    }
    filepath = _get_config_filepath()
    try:
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Config: Configuration saved to {filepath}")
        return True
    except IOError as e:
        print(f"Config Error: Error saving configuration to {filepath}: {e}")
        return False

def load_config() -> bool:
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE, P1_MAPPINGS, P2_MAPPINGS

    # Load external Pygame joystick mappings first
    _load_external_pygame_joystick_mappings() # This populates LOADED_PYGAME_JOYSTICK_MAPPINGS

    filepath = _get_config_filepath()
    loaded_p1_device_choice = DEFAULT_P1_INPUT_DEVICE
    loaded_p2_device_choice = DEFAULT_P2_INPUT_DEVICE

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)
            loaded_p1_device_choice = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2_device_choice = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {filepath}: {e}. Using default device choices.")

    # Use direct Pygame functions for joystick count
    try:
        num_joysticks = pygame.joystick.get_count()
    except pygame.error as e_joy_count:
        print(f"Config Warning: Pygame error getting joystick count: {e_joy_count}. Assuming 0 joysticks.")
        num_joysticks = 0
        
    print(f"Config: Pygame reported {num_joysticks} joysticks available for assignment.")

    # Player 1 Device Assignment Logic (no change needed here from your original)
    if loaded_p1_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            print(f"Config Info: P1 saved Pygame joystick '{loaded_p1_device_choice}' but no joysticks detected. Falling back to P1 keyboard.")
            CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
        else: # Joysticks are available
            try:
                p1_joy_idx = int(loaded_p1_device_choice.split('_')[-1])
                if not (0 <= p1_joy_idx < num_joysticks):
                    print(f"Config Warning: P1's saved Pygame joystick ID {p1_joy_idx} no longer available (found {num_joysticks}). Assigning joystick_pygame_0.")
                    CURRENT_P1_INPUT_DEVICE = f"joystick_pygame_0" # Assumes at least one joystick if num_joysticks > 0
                else:
                    CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice
            except (ValueError, IndexError): # Malformed ID string
                print(f"Config Warning: Malformed Pygame joystick ID for P1: '{loaded_p1_device_choice}'. Assigning joystick_pygame_0 if available.")
                CURRENT_P1_INPUT_DEVICE = "joystick_pygame_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
    else: # Keyboard
        CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice

    # Player 2 Device Assignment Logic (no change needed here from your original)
    if loaded_p2_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            print(f"Config Info: P2 saved Pygame joystick '{loaded_p2_device_choice}' but no joysticks detected. Falling back to P2 keyboard.")
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
        else: # Joysticks available
            try:
                p2_joy_idx = int(loaded_p2_device_choice.split('_')[-1])
                p1_is_pygame_joystick = CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_")
                p1_current_joy_idx_val = -1
                if p1_is_pygame_joystick:
                    try: p1_current_joy_idx_val = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                    except (ValueError, IndexError): p1_is_pygame_joystick = False # Treat as keyboard if ID bad

                if not (0 <= p2_joy_idx < num_joysticks): # P2's saved joystick ID is invalid
                    print(f"Config Warning: P2's saved Pygame joystick ID {p2_joy_idx} no longer available (found {num_joysticks}).")
                    # Attempt to assign a different joystick than P1 if possible
                    if num_joysticks == 1 and p1_is_pygame_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # Only one joy, P1 has it
                    elif num_joysticks > 0 and (not p1_is_pygame_joystick or p1_current_joy_idx_val != 0): CURRENT_P2_INPUT_DEVICE = "joystick_pygame_0" # P1 not on joy0, or P1 on keyboard
                    elif num_joysticks > 1 and p1_is_pygame_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = "joystick_pygame_1" # P1 on joy0, assign joy1 to P2
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # Fallback
                elif p1_is_pygame_joystick and p2_joy_idx == p1_current_joy_idx_val: # Conflict: P2 wants same joystick as P1
                    print(f"Config Warning: P2 cannot use same Pygame joystick as P1 (ID {p1_current_joy_idx_val}). Attempting to assign another.")
                    if num_joysticks > 1: # If more than one joystick, try to assign the other one
                        CURRENT_P2_INPUT_DEVICE = f"joystick_pygame_{1 if p1_current_joy_idx_val == 0 else 0}" # Assign 0 if P1 is on 1, else assign 1
                    else: # Only one joystick, P1 has it, P2 falls back to keyboard
                        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                else: # P2's saved joystick ID is valid and different from P1's (if P1 is on joystick)
                    CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
            except (ValueError, IndexError): # Malformed P2 joystick ID string
                print(f"Config Warning: Malformed Pygame joystick ID for P2: '{loaded_p2_device_choice}'. Assigning default.")
                CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    else: # P2 is keyboard
        # Ensure P2 doesn't use same keyboard config as P1 if P1 is also keyboard
        if loaded_p2_device_choice == CURRENT_P1_INPUT_DEVICE and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            print("Config Warning: P1 and P2 attempted to use 'keyboard_p1'. Assigning 'keyboard_p2' to P2.")
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # This assigns "keyboard_p2"
        else:
            CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice

    print(f"Config: Final device assignments: P1='{CURRENT_P1_INPUT_DEVICE}', P2='{CURRENT_P2_INPUT_DEVICE}'")
    update_player_mappings_from_device_choice() # Update P1_MAPPINGS and P2_MAPPINGS
    return True

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS

    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_"):
        P1_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_msg_p1 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK"
        print(f"Config: P1 assigned Pygame joystick mappings {status_msg_p1} ({len(P1_MAPPINGS)} actions).")
    else: # Fallback for P1 if device string is unrecognized
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": # If P2 is explicitly set to use P1's keyboard scheme
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick_pygame_"):
        # For network/couch co-op, P2 usually uses the same joystick mapping profile as P1 if both are joysticks
        # unless you have specific P2 joystick profiles.
        P2_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_msg_p2 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK"
        print(f"Config: P2 assigned Pygame joystick mappings {status_msg_p2} ({len(P2_MAPPINGS)} actions).")
    else: # Fallback for P2
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

    print(f"Config: Player mappings updated. P1 using '{CURRENT_P1_INPUT_DEVICE}', P2 using '{CURRENT_P2_INPUT_DEVICE}'.")

# Initialize by loading config when module is imported
# load_config() # This is typically called by the main application (app_core.py) at startup.

if __name__ == "__main__":
    print("--- Running config.py directly for testing (Pygame Joystick Mode) ---")
    # Pygame init is called at the top.

    print(f"\n--- Calling load_config() for test ---")
    load_config()

    print(f"\nAfter test load_config():")
    print(f"  AXIS_THRESHOLD_DEFAULT: {AXIS_THRESHOLD_DEFAULT}")
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  P1_MAPPINGS sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  P1_MAPPINGS sample (menu_confirm): {P1_MAPPINGS.get('menu_confirm', 'Not Found')}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    print(f"  P2_MAPPINGS sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")

    if LOADED_PYGAME_JOYSTICK_MAPPINGS:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS (first few entries or all if less than 5):")
        for i, (k, v) in enumerate(LOADED_PYGAME_JOYSTICK_MAPPINGS.items()):
            if i >= 5:
                print(f"    ... and {len(LOADED_PYGAME_JOYSTICK_MAPPINGS) - 5} more.")
                break
            print(f"    '{k}': {v}")
    else:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS: Not loaded, using defaults.")
        print(f"  DEFAULT_PYGAME_JOYSTICK_MAPPINGS (example - jump): {DEFAULT_PYGAME_JOYSTICK_MAPPINGS.get('jump')}")
        print(f"  DEFAULT_PYGAME_JOYSTICK_MAPPINGS (example - menu_confirm): {DEFAULT_PYGAME_JOYSTICK_MAPPINGS.get('menu_confirm')}")

    try:
        pygame.joystick.quit()
    except pygame.error: pass
    pygame.quit()
    print("--- config.py direct test finished ---")