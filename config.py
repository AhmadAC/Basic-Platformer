#################### START OF FILE: config.py ####################

# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Allows defining default keyboard and joystick mappings, and storing current selections.
Handles loading custom joystick mappings from controller_mappings.json.
"""
# version 2.0.0 (PySide6 Refactor - Removed pygame constants and joystick init)
import json
import os
# joystick_handler will be refactored later for PySide6
import joystick_handler # Still imported for function signatures, actual implementation will change

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
AXIS_THRESHOLD_DEFAULT = 0.7 # This remains a general concept

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
    "MOVE_UP": "up",
    "MOVE_DOWN": "down",
    "MOVE_LEFT": "left",
    "MOVE_RIGHT": "right",
    "JUMP": "jump",
    "CROUCH": "crouch",
    "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1",
    "ATTACK_SECONDARY": "attack2",
    "DASH": "dash",
    "ROLL": "roll",
    "WEAPON_1": "projectile1",
    "WEAPON_2": "projectile2",
    "WEAPON_3": "projectile3",
    "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", # Example: DPad Up might share a weapon slot
    "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6",
    "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm",
    "MENU_CANCEL": "menu_cancel",
    "MENU_RETURN": "pause", # Often Start/Menu button
    "RESET": "reset",
}


# --- Default Keyboard Mappings (Using string representations for keys) ---
# These strings will be mapped to Qt.Key enums or QKeySequence later.
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": "A", "right": "D", "up": "W", "down": "S",
    "jump": "W", # 'W' also serves as jump
    "crouch": "S", # 'S' also serves as crouch toggle
    "attack1": "V", "attack2": "B", "dash": "Shift", # "LShift" or just "Shift"
    "roll": "Control", "interact": "E", # "LControl" or just "Control"
    "projectile1": "1", "projectile2": "2", "projectile3": "3",
    "projectile4": "4", "projectile5": "5",
    "reset": "6", # Key 6 for P1 for reset
    "projectile7": "7",
    "pause": "Escape", "menu_confirm": "Return", "menu_cancel": "Escape",
    "menu_up": "Up", "menu_down": "Down", "menu_left": "Left", "menu_right": "Right",
}

DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": "J", "right": "L", "up": "I", "down": "K",
    "jump": "I",
    "crouch": "K",
    "attack1": "O", "attack2": "P", "dash": ";", # Semicolon
    "roll": "'", # Quote
    "interact": "\\", # Backslash
    "projectile1": "Num+1", "projectile2": "Num+2", "projectile3": "Num+3", # Keypad numbers
    "projectile4": "Num+4", "projectile5": "Num+5",
    "reset": "Num+6", # Keypad 6 for P2 for reset
    "projectile7": "Num+7",
    "pause": "Pause", "menu_confirm": "Num+Enter", "menu_cancel": "Delete",
    "menu_up": "Num+8", "menu_down": "Num+2", "menu_left": "Num+4", "menu_right": "Num+6",
}

# Joystick mapping structure remains the same conceptually
DEFAULT_JOYSTICK_FALLBACK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0}, # Typically A/Cross
    "crouch": {"type": "button", "id": 1}, # Typically B/Circle
    "attack1": {"type": "button", "id": 2}, # Typically X/Square
    "attack2": {"type": "button", "id": 3}, # Typically Y/Triangle
    "dash": {"type": "button", "id": 5}, # Typically RB/R1
    "roll": {"type": "button", "id": 4}, # Typically LB/L1
    "interact": {"type": "button", "id": 10}, # Example: L3/LSB
    "projectile1": {"type": "hat", "id": 0, "value": (0,1)},    # Dpad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1,0)},    # Dpad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0,-1)},   # Dpad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1,0)},   # Dpad Left
    "projectile5": {"type": "button", "id": 6},                 # Example: Back/Select
    "projectile6": {"type": "button", "id": 11},                # Example: R3/RSB
    "reset": {"type": "button", "id": 7},                       # Example: Start/Options
    "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Example LT/L2
    "pause": {"type": "button", "id": 9}, # Typically Start/Options
    "menu_confirm": {"type": "button", "id": 0},
    "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0,1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0,-1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1,0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1,0)},
}

LOADED_JOYSTICK_MAPPINGS = {} # Stores mappings translated from controller_mappings.json
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def _translate_and_validate_joystick_mappings(raw_json_mappings):
    translated_mappings = {}
    if not isinstance(raw_json_mappings, dict):
        print("Config Error: Raw JSON mappings is not a dictionary. Cannot translate.")
        return {}
    for json_key, mapping_data_from_json in raw_json_mappings.items():
        internal_action_name = EXTERNAL_TO_INTERNAL_ACTION_MAP.get(json_key)
        if not internal_action_name:
            continue
        if not isinstance(mapping_data_from_json, dict):
            continue
        event_type_from_json = mapping_data_from_json.get("event_type")
        details_from_json = mapping_data_from_json.get("details")
        if not event_type_from_json or not isinstance(details_from_json, dict):
            continue
        final_mapping_for_action = {"type": event_type_from_json}
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
            continue
        translated_mappings[internal_action_name] = final_mapping_for_action
    return translated_mappings

def _load_external_joystick_mappings():
    global LOADED_JOYSTICK_MAPPINGS
    LOADED_JOYSTICK_MAPPINGS = {} # Reset before loading
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
    except Exception as e:
        print(f"Config Error: Error loading '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using fallback mappings.")
    LOADED_JOYSTICK_MAPPINGS = {} # Ensure it's empty on failure
    return False

def get_action_key_map(player_id: int, device_id_str: str):
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick"):
        return LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
    return {}

def _get_config_filepath():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config():
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    config_data = {
        "p1_input_device": CURRENT_P1_INPUT_DEVICE,
        "p2_input_device": CURRENT_P2_INPUT_DEVICE
    }
    filepath = _get_config_filepath()
    try:
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Configuration saved to {filepath}")
        return True
    except IOError as e:
        print(f"Error saving configuration to {filepath}: {e}")
        return False

def load_config():
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
            print(f"Config: Device choices loaded from {filepath}: P1='{loaded_p1_device_choice}', P2='{loaded_p2_device_choice}'")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Loading {filepath}: {e}. Using default device choices.")
    else:
        print(f"Config Info: File {filepath} not found. Using default device choices.")

    # Joystick count will now come from the refactored joystick_handler
    num_joysticks = joystick_handler.get_joystick_count() # This function's implementation will change
    print(f"Config: Number of joysticks detected by joystick_handler: {num_joysticks}")

    # Logic for assigning CURRENT_P1_INPUT_DEVICE and CURRENT_P2_INPUT_DEVICE based on
    # loaded_choices and num_joysticks remains conceptually the same.
    if loaded_p1_device_choice.startswith("joystick_"):
        try:
            p1_joy_idx = int(loaded_p1_device_choice.split('_')[-1])
            if not (0 <= p1_joy_idx < num_joysticks):
                print(f"Config Warning: P1's saved joystick ID {p1_joy_idx} no longer available (found {num_joysticks}).")
                CURRENT_P1_INPUT_DEVICE = "joystick_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
            else:
                CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice
        except ValueError:
            CURRENT_P1_INPUT_DEVICE = "joystick_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
    else:
        CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice

    if loaded_p2_device_choice.startswith("joystick_"):
        try:
            p2_joy_idx = int(loaded_p2_device_choice.split('_')[-1])
            p1_current_joy_idx = -1
            if CURRENT_P1_INPUT_DEVICE.startswith("joystick_"):
                try: p1_current_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                except ValueError: pass

            if not (0 <= p2_joy_idx < num_joysticks):
                print(f"Config Warning: P2's saved joystick ID {p2_joy_idx} no longer available.")
                if num_joysticks == 1 and p1_current_joy_idx == 0:
                    CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                elif num_joysticks > 0 and p1_current_joy_idx != 0:
                    CURRENT_P2_INPUT_DEVICE = "joystick_0"
                elif num_joysticks > 1 and p1_current_joy_idx == 0:
                    CURRENT_P2_INPUT_DEVICE = "joystick_1"
                else:
                    CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
            elif p2_joy_idx == p1_current_joy_idx:
                print(f"Config Warning: P2 cannot use same joystick as P1 (ID {p1_current_joy_idx}).")
                if num_joysticks > 1:
                    CURRENT_P2_INPUT_DEVICE = "joystick_1" if p1_current_joy_idx == 0 else "joystick_0"
                else:
                    CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
            else:
                CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
        except ValueError:
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    else:
        if loaded_p2_device_choice == CURRENT_P1_INPUT_DEVICE and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
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
        print(f"Config: P1 assigned joystick mappings {status_msg_p1} for device '{CURRENT_P1_INPUT_DEVICE}'.")
    else: # Fallback or keyboard_p2 assigned to P1 (less common)
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick"):
        P2_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg_p2 = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        print(f"Config: P2 assigned joystick mappings {status_msg_p2} for device '{CURRENT_P2_INPUT_DEVICE}'.")
    else: # Fallback for P2
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        
    print(f"Config: Player mappings updated. P1 using: {CURRENT_P1_INPUT_DEVICE}, P2 using: {CURRENT_P2_INPUT_DEVICE}")

if __name__ == "__main__":
    # Pygame is not initialized here for direct testing of this module
    print("--- Running config.py directly for testing (PySide6 refactor - No Pygame init) ---")
    
    # Simulate joystick_handler being initialized if you want to test joystick count logic
    # For a true test, joystick_handler.py would need its PySide6-compatible version.
    # For now, we can mock its behavior:
    class MockJoystickHandler:
        def __init__(self): self._joystick_count = 0
        def init_joysticks(self): print("MockJoystickHandler: init_joysticks called.")
        def get_joystick_count(self): return self._joystick_count
        def set_joystick_count(self, count): self._joystick_count = count
        def quit_joysticks(self): print("MockJoystickHandler: quit_joysticks called.")

    original_joystick_handler_module = joystick_handler # Save original
    joystick_handler = MockJoystickHandler() # Replace with mock
    
    # Simulate finding 1 joystick for testing logic
    joystick_handler.set_joystick_count(1)
    joystick_handler.init_joysticks()

    print(f"\n--- Calling load_config() for test ---")
    load_config()

    print(f"\nAfter test load_config():")
    print(f"  AXIS_THRESHOLD_DEFAULT: {AXIS_THRESHOLD_DEFAULT}")
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  P1_MAPPINGS sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  P1_MAPPINGS sample (reset): {P1_MAPPINGS.get('reset', 'Not Found')}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    print(f"  P2_MAPPINGS sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  P2_MAPPINGS sample (reset): {P2_MAPPINGS.get('reset', 'Not Found')}")
    
    if LOADED_JOYSTICK_MAPPINGS:
        print(f"  LOADED_JOYSTICK_MAPPINGS (example - jump): {LOADED_JOYSTICK_MAPPINGS.get('jump')}")
        print(f"  LOADED_JOYSTICK_MAPPINGS (example - reset): {LOADED_JOYSTICK_MAPPINGS.get('reset')}")
        print(f"  LOADED_JOYSTICK_MAPPINGS (example - projectile6): {LOADED_JOYSTICK_MAPPINGS.get('projectile6')}")

    joystick_handler.quit_joysticks()
    joystick_handler = original_joystick_handler_module # Restore original module
    print("--- config.py direct test finished ---")

#################### END OF FILE: config.py ####################