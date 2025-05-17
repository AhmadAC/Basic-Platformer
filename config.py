########## START OF FILE: config.py ##########
# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Allows defining default keyboard and joystick mappings, and storing current selections.
Handles loading custom joystick mappings from controller_mappings.json.
"""
# version 1.0.5 (Added AXIS_THRESHOLD_DEFAULT)
import pygame
import json
import os
import joystick_handler # To check actual joystick count

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
AXIS_THRESHOLD_DEFAULT = 0.7  # ADDED THIS LINE - Default threshold for joystick axis operations

# --- Game Actions (Internal names the game logic uses) ---
GAME_ACTIONS = [
    "left", "right", "up", "down",
    "jump",
    "attack1", "attack2",
    "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]

# --- Mapping from controller_mappings.json keys to internal GAME_ACTIONS ---
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up",
    "MOVE_DOWN": "down",
    "MOVE_LEFT": "left",
    "MOVE_RIGHT": "right",
    "JUMP": "jump",
    "CROUCH": "down",
    "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1",
    "ATTACK_SECONDARY": "attack2",
    "DASH": "dash",
    "ROLL": "roll",
    "WEAPON_1": "projectile1",
    "WEAPON_2": "projectile2",
    "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", # Or map to its own if distinct, e.g. "projectile1"
    "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6",
    "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm",
    "MENU_CANCEL": "menu_cancel",
    "MENU_RETURN": "pause",
    # Add "MENU_UP", "MENU_DOWN", etc. if they are distinct in your JSON and map to internal menu actions
    # "MENU_NAV_UP": "menu_up",
    # "MENU_NAV_DOWN": "menu_down",
}


# --- Default Keyboard Mappings ---
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": pygame.K_a, "right": pygame.K_d, "up": pygame.K_w, "down": pygame.K_s,
    "jump": pygame.K_w, "attack1": pygame.K_v, "attack2": pygame.K_b, "dash": pygame.K_LSHIFT,
    "roll": pygame.K_LCTRL, "interact": pygame.K_e,
    "projectile1": pygame.K_1, "projectile2": pygame.K_2, "projectile3": pygame.K_3,
    "projectile4": pygame.K_4, "projectile5": pygame.K_5, "projectile6": pygame.K_6, "projectile7": pygame.K_7,
    "pause": pygame.K_ESCAPE, "menu_confirm": pygame.K_RETURN, "menu_cancel": pygame.K_ESCAPE,
    "menu_up": pygame.K_UP, "menu_down": pygame.K_DOWN, "menu_left": pygame.K_LEFT, "menu_right": pygame.K_RIGHT,
}

DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": pygame.K_j, "right": pygame.K_l, "up": pygame.K_i, "down": pygame.K_k,
    "jump": pygame.K_i, "attack1": pygame.K_o, "attack2": pygame.K_p, "dash": pygame.K_SEMICOLON,
    "roll": pygame.K_QUOTE, "interact": pygame.K_BACKSLASH,
    "projectile1": pygame.K_KP_1, "projectile2": pygame.K_KP_2, "projectile3": pygame.K_KP_3,
    "projectile4": pygame.K_KP_4, "projectile5": pygame.K_KP_5, "projectile6": pygame.K_KP_6, "projectile7": pygame.K_KP_7,
    "pause": pygame.K_PAUSE, "menu_confirm": pygame.K_KP_ENTER, "menu_cancel": pygame.K_DELETE,
    "menu_up": pygame.K_KP_8, "menu_down": pygame.K_KP_2, "menu_left": pygame.K_KP_4, "menu_right": pygame.K_KP_6,
}

DEFAULT_JOYSTICK_FALLBACK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "jump": {"type": "button", "id": 0},
    "attack1": {"type": "button", "id": 2},
    "attack2": {"type": "button", "id": 1},
    "dash": {"type": "button", "id": 3},
    "roll": {"type": "button", "id": 5},
    "interact": {"type": "button", "id": 4},
    "projectile1": {"type": "button", "id": 6},
    "projectile2": {"type": "button", "id": 7},
    "projectile3": {"type": "hat", "id": 0, "value": (0,-1)},
    "projectile4": {"type": "hat", "id": 0, "value": (0,1)},
    "projectile5": {"type": "hat", "id": 0, "value": (-1,0)},
    "projectile6": {"type": "hat", "id": 0, "value": (1,0)},
    "projectile7": {"type": "button", "id": 10}, # Example
    "pause": {"type": "button", "id": 9},
    "menu_confirm": {"type": "button", "id": 1},
    "menu_cancel": {"type": "button", "id": 0},
    "menu_up": {"type": "hat", "id": 0, "value": (0,1)}, # For menu nav specifically
    "menu_down": {"type": "hat", "id": 0, "value": (0,-1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1,0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1,0)},
}

LOADED_JOYSTICK_MAPPINGS = {}
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
            # print(f"Config Info: JSON key '{json_key}' not found in EXTERNAL_TO_INTERNAL_ACTION_MAP. Skipping.")
            continue
        if not isinstance(mapping_data_from_json, dict):
            # print(f"Config Warning: Mapping for JSON key '{json_key}' (internal: '{internal_action_name}') is not a dict. Skipping.")
            continue
        event_type_from_json = mapping_data_from_json.get("event_type")
        details_from_json = mapping_data_from_json.get("details")
        if not event_type_from_json or not isinstance(details_from_json, dict):
            # print(f"Config Warning: Invalid structure for '{json_key}' -> '{internal_action_name}'. Missing 'event_type' or 'details'. Skipping.")
            continue
        final_mapping_for_action = {"type": event_type_from_json}
        if event_type_from_json == "button":
            button_id = details_from_json.get("button_id")
            if button_id is None: continue
            final_mapping_for_action["id"] = button_id
        elif event_type_from_json == "axis":
            axis_id = details_from_json.get("axis_id")
            direction = details_from_json.get("direction")
            threshold = details_from_json.get("threshold", AXIS_THRESHOLD_DEFAULT) # Use defined default
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
    except Exception as e:
        print(f"Config Error: Error loading '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using fallback mappings.")
    LOADED_JOYSTICK_MAPPINGS = {}
    return False

def get_action_key_map(player_id: int, device_id_str: str):
    if device_id_str == "keyboard_p1": return P1_MAPPINGS
    elif device_id_str == "keyboard_p2": return P2_MAPPINGS
    elif device_id_str.startswith("joystick"):
        return LOADED_JOYSTICK_MAPPINGS if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
    return {}

def _get_config_filepath():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config():
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    config_data = {"p1_input_device": CURRENT_P1_INPUT_DEVICE, "p2_input_device": CURRENT_P2_INPUT_DEVICE}
    filepath = _get_config_filepath()
    try:
        with open(filepath, 'w') as f: json.dump(config_data, f, indent=4)
        print(f"Configuration saved to {filepath}")
        return True
    except IOError as e:
        print(f"Error saving configuration to {filepath}: {e}")
        return False

def load_config():
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    _load_external_joystick_mappings()

    filepath = _get_config_filepath()
    loaded_p1_d, loaded_p2_d = DEFAULT_P1_INPUT_DEVICE, DEFAULT_P2_INPUT_DEVICE
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f: config_data = json.load(f)
            loaded_p1_d = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2_d = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
            print(f"Config: Device choices loaded from {filepath}: P1='{loaded_p1_d}', P2='{loaded_p2_d}'")
        except (IOError, json.JSONDecodeError) as e: print(f"Config Error: Loading {filepath}: {e}. Using defaults.")
    else: print(f"Config Info: File {filepath} not found. Using defaults.")

    num_joysticks = joystick_handler.get_joystick_count()
    print(f"Config: Number of joysticks detected by joystick_handler: {num_joysticks}")

    if loaded_p1_d.startswith("joystick_"):
        try:
            p1_joy_idx = int(loaded_p1_d.split('_')[-1])
            if not (0 <= p1_joy_idx < num_joysticks):
                print(f"Config Warning: P1's saved joystick ID {p1_joy_idx} no longer available (found {num_joysticks}).")
                CURRENT_P1_INPUT_DEVICE = "joystick_0" if num_joysticks > 0 else "keyboard_p1"
            else: CURRENT_P1_INPUT_DEVICE = loaded_p1_d
        except: CURRENT_P1_INPUT_DEVICE = "joystick_0" if num_joysticks > 0 else "keyboard_p1"
    else: CURRENT_P1_INPUT_DEVICE = loaded_p1_d

    if loaded_p2_d.startswith("joystick_"):
        try:
            p2_joy_idx = int(loaded_p2_d.split('_')[-1])
            p1_curr_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1]) if CURRENT_P1_INPUT_DEVICE.startswith("joystick_") else -1
            if not (0 <= p2_joy_idx < num_joysticks):
                print(f"Config Warning: P2's saved joystick ID {p2_joy_idx} no longer available.")
                CURRENT_P2_INPUT_DEVICE = ("joystick_0" if p1_curr_joy_idx != 0 and num_joysticks > 0 else
                                     "joystick_1" if p1_curr_joy_idx == 0 and num_joysticks > 1 else
                                     "keyboard_p2")
            elif p2_joy_idx == p1_curr_joy_idx:
                print(f"Config Warning: P2 cannot use same joystick as P1 (ID {p1_curr_joy_idx}).")
                CURRENT_P2_INPUT_DEVICE = ("joystick_1" if p1_curr_joy_idx == 0 and num_joysticks > 1 else
                                     "joystick_0" if p1_curr_joy_idx != 0 and num_joysticks > 1 else # Corrected: check num_joysticks > 0 before num_joysticks > 1 for the second option
                                     "keyboard_p1" if num_joysticks == 1 else "keyboard_p2")
            else: CURRENT_P2_INPUT_DEVICE = loaded_p2_d
        except: CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
    else:
        CURRENT_P2_INPUT_DEVICE = "keyboard_p2" if loaded_p2_d == "keyboard_p1" and CURRENT_P1_INPUT_DEVICE == "keyboard_p1" else loaded_p2_d

    print(f"Config: Final device assignments: P1='{CURRENT_P1_INPUT_DEVICE}', P2='{CURRENT_P2_INPUT_DEVICE}'")
    update_player_mappings_from_device_choice()
    return True

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1": P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick"):
        P1_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        print(f"Config: P1 assigned joystick mappings {status_msg} for device '{CURRENT_P1_INPUT_DEVICE}'.")
    else: P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick"):
        P2_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        print(f"Config: P2 assigned joystick mappings {status_msg} for device '{CURRENT_P2_INPUT_DEVICE}'.")
    else: P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    print(f"Config: Player mappings updated. P1: {CURRENT_P1_INPUT_DEVICE}, P2: {CURRENT_P2_INPUT_DEVICE}")

if __name__ != "__main__":
    _load_external_joystick_mappings()
else:
    print("--- Running config.py directly for testing ---")
    pygame.init()
    joystick_handler.init_joysticks()
    print(f"\n--- Calling load_config() for test ---")
    load_config()
    print(f"After test load_config():")
    print(f"  AXIS_THRESHOLD_DEFAULT: {AXIS_THRESHOLD_DEFAULT}") # Test the new constant
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    joystick_handler.quit_joysticks()
    pygame.quit()
    print("--- config.py direct test finished ---")

########## END OF FILE: config.py ##########