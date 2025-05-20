#################### START OF FILE: config.py ####################

# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Allows defining default keyboard and joystick mappings, and storing current selections.
Handles loading custom joystick mappings from controller_mappings.json.
"""
# version 2.0.1 (Graceful fallback for joystick detection failure, quieter warnings)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import joystick_handler # Using joystick_handler v3.0.4+

# --- File for saving/loading game config (selected devices) ---
CONFIG_FILE_NAME = "game_config.json"

# --- Path for external controller mappings ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
EXTERNAL_CONTROLLER_MAPPINGS_FILENAME = "controller_mappings.json"
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

# --- Mapping from controller_mappings.json keys to internal GAME_ACTIONS ---
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_DOWN": "down", "MOVE_LEFT": "left", "MOVE_RIGHT": "right",
    "JUMP": "jump", "CROUCH": "crouch", "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1", "ATTACK_SECONDARY": "attack2",
    "DASH": "dash", "ROLL": "roll", "RESET": "reset",
    "WEAPON_1": "projectile1", "WEAPON_2": "projectile2", "WEAPON_3": "projectile3", "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6", "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause",
}

# --- Default Keyboard Mappings (Using string representations for keys) ---
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": "A", "right": "D", "up": "W", "down": "S", "jump": "W", "crouch": "S",
    "attack1": "V", "attack2": "B", "dash": "Shift", "roll": "Control", "interact": "E",
    "projectile1": "1", "projectile2": "2", "projectile3": "3", "projectile4": "4",
    "projectile5": "5", "reset": "Q", "projectile7": "7",
    "pause": "Escape", "menu_confirm": "Return", "menu_cancel": "Escape",
    "menu_up": "Up", "menu_down": "Down", "menu_left": "Left", "menu_right": "Right",
}

DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": "J", "right": "L", "up": "I", "down": "K", "jump": "I", "crouch": "K",
    "attack1": "O", "attack2": "P", "dash": ";", "roll": "'", "interact": "\\",
    "projectile1": "Num+1", "projectile2": "Num+2", "projectile3": "Num+3", "projectile4": "Num+4",
    "projectile5": "Num+5", "reset": "Num+6", "projectile7": "Num+7",
    "pause": "Pause", "menu_confirm": "Num+Enter", "menu_cancel": "Delete",
    "menu_up": "Num+8", "menu_down": "Num+2", "menu_left": "Num+4", "menu_right": "Num+6",
}

DEFAULT_JOYSTICK_FALLBACK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, "crouch": {"type": "button", "id": 1},
    "attack1": {"type": "button", "id": 2}, "attack2": {"type": "button", "id": 3},
    "dash": {"type": "button", "id": 5}, "roll": {"type": "button", "id": 4},
    "interact": {"type": "button", "id": 10},
    "projectile1": {"type": "hat", "id": 0, "value": (0,1)}, "projectile2": {"type": "hat", "id": 0, "value": (1,0)},
    "projectile3": {"type": "hat", "id": 0, "value": (0,-1)}, "projectile4": {"type": "hat", "id": 0, "value": (-1,0)},
    "projectile5": {"type": "button", "id": 6}, "projectile6": {"type": "button", "id": 11},
    "reset": {"type": "button", "id": 7},
    "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "pause": {"type": "button", "id": 9},
    "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0,1)}, "menu_down": {"type": "hat", "id": 0, "value": (0,-1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1,0)}, "menu_right": {"type": "hat", "id": 0, "value": (1,0)},
}

LOADED_JOYSTICK_MAPPINGS: Dict[str, Any] = {}
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def _translate_and_validate_joystick_mappings(raw_json_mappings: Any) -> Dict[str, Any]:
    translated_mappings: Dict[str, Any] = {}
    if not isinstance(raw_json_mappings, dict):
        print("Config Error: Raw JSON mappings is not a dictionary. Cannot translate.")
        return {}
    for json_key, mapping_data_from_json in raw_json_mappings.items():
        internal_action_name = EXTERNAL_TO_INTERNAL_ACTION_MAP.get(json_key)
        if not internal_action_name: continue
        if not isinstance(mapping_data_from_json, dict): continue
        
        event_type_from_json = mapping_data_from_json.get("event_type")
        details_from_json = mapping_data_from_json.get("details")
        if not event_type_from_json or not isinstance(details_from_json, dict): continue
            
        final_mapping_for_action: Dict[str, Any] = {"type": event_type_from_json}
        if event_type_from_json == "button":
            button_id = details_from_json.get("button_id")
            if button_id is None: continue
            final_mapping_for_action["id"] = button_id
        elif event_type_from_json == "axis":
            axis_id = details_from_json.get("axis_id")
            direction = details_from_json.get("direction")
            threshold = details_from_json.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_id is None or direction is None: continue
            final_mapping_for_action["id"] = axis_id
            final_mapping_for_action["value"] = direction
            final_mapping_for_action["threshold"] = threshold
        elif event_type_from_json == "hat":
            hat_id = details_from_json.get("hat_id")
            hat_value_tuple = details_from_json.get("value")
            if hat_id is None or hat_value_tuple is None: continue
            final_mapping_for_action["id"] = hat_id
            final_mapping_for_action["value"] = tuple(hat_value_tuple) if isinstance(hat_value_tuple, list) else hat_value_tuple
        else:
            continue # Unknown event_type
        translated_mappings[internal_action_name] = final_mapping_for_action
    return translated_mappings

def _load_external_joystick_mappings() -> bool:
    global LOADED_JOYSTICK_MAPPINGS
    LOADED_JOYSTICK_MAPPINGS = {} 
    if not os.path.exists(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH):
        print(f"Config Info: External controller mappings file not found at '{EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH}'. Joystick will use fallback mappings.")
        return False
    try:
        with open(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH, 'r') as f:
            raw_mappings = json.load(f)
        LOADED_JOYSTICK_MAPPINGS = _translate_and_validate_joystick_mappings(raw_mappings)
        if LOADED_JOYSTICK_MAPPINGS:
            print(f"Config: Successfully loaded and translated {len(LOADED_JOYSTICK_MAPPINGS)} joystick mappings from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}'.")
            return True
        else:
            print(f"Config Warning: Loaded JSON from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}' but resulted in empty or invalid mappings after translation.")
            return False
    except Exception as e:
        print(f"Config Error: Error loading '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using fallback mappings.")
        LOADED_JOYSTICK_MAPPINGS = {}
        return False

def get_action_key_map(player_id: int, device_id_str: str) -> Dict[str, Any]:
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick"):
        return LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
    return {}

def _get_config_filepath() -> str:
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
    
    _load_external_joystick_mappings()

    filepath = _get_config_filepath()
    loaded_p1_device_choice = DEFAULT_P1_INPUT_DEVICE
    loaded_p2_device_choice = DEFAULT_P2_INPUT_DEVICE

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)
            loaded_p1_device_choice = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2_device_choice = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
            # print(f"Config: Device choices loaded from {filepath}: P1='{loaded_p1_device_choice}', P2='{loaded_p2_device_choice}'") # Less verbose
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {filepath}: {e}. Using default device choices.")
    # else: # Less verbose if file not found, just use defaults
        # print(f"Config Info: File {filepath} not found. Using default device choices.")

    num_joysticks = joystick_handler.get_joystick_count()
    if num_joysticks > 0: # Only print if joysticks were expected or found
        print(f"Config: Number of joysticks known to handler: {num_joysticks}")

    # Player 1 Device Assignment
    if loaded_p1_device_choice.startswith("joystick_"):
        if num_joysticks == 0:
            # print(f"Config Info: P1 saved joystick '{loaded_p1_device_choice}' but no joysticks detected. Falling back to P1 keyboard.") # Quieter
            CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
        else:
            try:
                p1_joy_idx = int(loaded_p1_device_choice.split('_')[-1])
                if not (0 <= p1_joy_idx < num_joysticks):
                    print(f"Config Warning: P1's saved joystick ID {p1_joy_idx} no longer available (found {num_joysticks}). Assigning joystick_0 or keyboard.")
                    CURRENT_P1_INPUT_DEVICE = "joystick_0" # Try to assign first available
                else:
                    CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice
            except ValueError: # Invalid format like "joystick_abc"
                CURRENT_P1_INPUT_DEVICE = "joystick_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
    else:
        CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice

    # Player 2 Device Assignment
    if loaded_p2_device_choice.startswith("joystick_"):
        if num_joysticks == 0:
            # print(f"Config Info: P2 saved joystick '{loaded_p2_device_choice}' but no joysticks detected. Falling back to P2 keyboard.") # Quieter
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
        else:
            try:
                p2_joy_idx = int(loaded_p2_device_choice.split('_')[-1])
                p1_is_joystick = CURRENT_P1_INPUT_DEVICE.startswith("joystick_")
                p1_current_joy_idx_val = -1
                if p1_is_joystick:
                    try: p1_current_joy_idx_val = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                    except ValueError: p1_is_joystick = False # Treat as non-joystick if ID is bad

                if not (0 <= p2_joy_idx < num_joysticks):
                    print(f"Config Warning: P2's saved joystick ID {p2_joy_idx} no longer available.")
                    if num_joysticks == 1 and p1_is_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                    elif num_joysticks > 0 and (not p1_is_joystick or p1_current_joy_idx_val != 0): CURRENT_P2_INPUT_DEVICE = "joystick_0"
                    elif num_joysticks > 1 and p1_is_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = "joystick_1"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                elif p1_is_joystick and p2_joy_idx == p1_current_joy_idx_val:
                    print(f"Config Warning: P2 cannot use same joystick as P1 (ID {p1_current_joy_idx_val}).")
                    if num_joysticks > 1: CURRENT_P2_INPUT_DEVICE = "joystick_1" if p1_current_joy_idx_val == 0 else "joystick_0"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                else:
                    CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
            except ValueError:
                CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # Fallback for malformed P2 joystick string
    else: # P2 is keyboard
        if loaded_p2_device_choice == CURRENT_P1_INPUT_DEVICE and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE # Avoid P1 and P2 using same P1 keyboard mappings
        else:
            CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
            
    print(f"Config: Final device assignments: P1='{CURRENT_P1_INPUT_DEVICE}', P2='{CURRENT_P2_INPUT_DEVICE}'")
    update_player_mappings_from_device_choice()
    return True

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS
    
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick"):
        P1_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg_p1 = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        # print(f"Config: P1 assigned joystick mappings {status_msg_p1} for device '{CURRENT_P1_INPUT_DEVICE}'.") # Quieter
    else: 
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick"):
        P2_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg_p2 = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        # print(f"Config: P2 assigned joystick mappings {status_msg_p2} for device '{CURRENT_P2_INPUT_DEVICE}'.") # Quieter
    else:
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        
    # print(f"Config: Player mappings updated. P1 using: {CURRENT_P1_INPUT_DEVICE}, P2 using: {CURRENT_P2_INPUT_DEVICE}") # Quieter

if __name__ == "__main__":
    print("--- Running config.py directly for testing (PySide6) ---")
    
    class MockJoystickHandler:
        def __init__(self): self._joystick_count = 0
        def init_joysticks(self): print("MockJoystickHandler: init_joysticks called.")
        def get_joystick_count(self): return self._joystick_count
        # def set_joystick_count(self, count): self._joystick_count = count # Removed set, count comes from handler
        def add_known_gamepad_device(self, dev_info): self._joystick_count +=1 # Simulate adding
        def quit_joysticks(self): print("MockJoystickHandler: quit_joysticks called.")

    original_joystick_handler_module = joystick_handler
    joystick_handler = MockJoystickHandler() # type: ignore
    
    # Simulate a scenario where a mapper might have found one joystick
    # joystick_handler.add_known_gamepad_device({'name':'TestController', 'path':'/dev/test0'})
    # Or simulate no joysticks found by default if not using add_known_gamepad_device
    
    joystick_handler.init_joysticks() # Call init

    print(f"\n--- Calling load_config() for test ---")
    load_config()

    print(f"\nAfter test load_config():")
    print(f"  AXIS_THRESHOLD_DEFAULT: {AXIS_THRESHOLD_DEFAULT}")
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  P1_MAPPINGS sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    print(f"  P2_MAPPINGS sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")
    
    if LOADED_JOYSTICK_MAPPINGS:
        print(f"  LOADED_JOYSTICK_MAPPINGS (example - jump): {LOADED_JOYSTICK_MAPPINGS.get('jump')}")

    joystick_handler.quit_joysticks() # type: ignore
    joystick_handler = original_joystick_handler_module # type: ignore
    print("--- config.py direct test finished ---")

#################### END OF FILE: config.py ####################