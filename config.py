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
AXIS_THRESHOLD_DEFAULT = 0.7

# --- Game Actions (Internal names the game logic uses) ---
GAME_ACTIONS = [
    "left", "right", "up", "down", # "down" for aiming/ladder, "crouch" for toggle event
    "jump", "crouch", # "crouch" is the action for the toggle event
    "attack1", "attack2",
    "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", # projectile6 is now effectively reset if keyboard mapped
    "pause", "reset", # Added "reset"
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]

# --- Mapping from controller_mappings.json keys to internal GAME_ACTIONS ---
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up",
    "MOVE_DOWN": "down",       # For aiming down / ladder down continuously
    "MOVE_LEFT": "left",
    "MOVE_RIGHT": "right",
    "JUMP": "jump",
    "CROUCH": "crouch",        # Dedicated crouch button event (toggle)
    "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1",
    "ATTACK_SECONDARY": "attack2",
    "DASH": "dash",
    "ROLL": "roll",
    "WEAPON_1": "projectile1",
    "WEAPON_2": "projectile2",
    "WEAPON_3": "projectile3",
    "WEAPON_4": "projectile4",
    "WEAPON_DPAD_UP": "projectile4", # Often DPad Up is same as a weapon slot
    "WEAPON_DPAD_DOWN": "projectile5",
    "WEAPON_DPAD_LEFT": "projectile6",  # CORRECTED: Was "reset", now likely "projectile6"
    "WEAPON_DPAD_RIGHT": "projectile7",
    "MENU_CONFIRM": "menu_confirm",
    "MENU_CANCEL": "menu_cancel",
    "MENU_RETURN": "pause",
    "RESET": "reset", # For direct mapping from controller_mapper_gui.py "RESET" action
    # Add "RESET_ACTION": "reset" if controller_mapper_gui saves "RESET_ACTION" to JSON
}


# --- Default Keyboard Mappings ---
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": pygame.K_a, "right": pygame.K_d, "up": pygame.K_w, "down": pygame.K_s,
    "jump": pygame.K_w, # "up" key also serves as jump
    "crouch": pygame.K_s, # "down" key also serves as crouch toggle event
    "attack1": pygame.K_v, "attack2": pygame.K_b, "dash": pygame.K_LSHIFT,
    "roll": pygame.K_LCTRL, "interact": pygame.K_e,
    "projectile1": pygame.K_1, "projectile2": pygame.K_2, "projectile3": pygame.K_3,
    "projectile4": pygame.K_4, "projectile5": pygame.K_5,
    "reset": pygame.K_6, # Key 6 for P1 (was projectile6)
    "projectile7": pygame.K_7,
    "pause": pygame.K_ESCAPE, "menu_confirm": pygame.K_RETURN, "menu_cancel": pygame.K_ESCAPE,
    "menu_up": pygame.K_UP, "menu_down": pygame.K_DOWN, "menu_left": pygame.K_LEFT, "menu_right": pygame.K_RIGHT,
}

DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": pygame.K_j, "right": pygame.K_l, "up": pygame.K_i, "down": pygame.K_k,
    "jump": pygame.K_i, # "up" key also serves as jump
    "crouch": pygame.K_k, # "down" key also serves as crouch toggle event
    "attack1": pygame.K_o, "attack2": pygame.K_p, "dash": pygame.K_SEMICOLON,
    "roll": pygame.K_QUOTE, "interact": pygame.K_BACKSLASH,
    "projectile1": pygame.K_KP_1, "projectile2": pygame.K_KP_2, "projectile3": pygame.K_KP_3,
    "projectile4": pygame.K_KP_4, "projectile5": pygame.K_KP_5,
    "reset": pygame.K_KP_6, # Keypad 6 for P2 (was projectile6)
    "projectile7": pygame.K_KP_7,
    "pause": pygame.K_PAUSE, "menu_confirm": pygame.K_KP_ENTER, "menu_cancel": pygame.K_DELETE,
    "menu_up": pygame.K_KP_8, "menu_down": pygame.K_KP_2, "menu_left": pygame.K_KP_4, "menu_right": pygame.K_KP_6,
}

DEFAULT_JOYSTICK_FALLBACK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Continuous up for ladders/aim
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Continuous down for ladders/aim
    "jump": {"type": "button", "id": 0}, # Typically A/Cross
    "crouch": {"type": "button", "id": 1}, # Typically B/Circle - for crouch toggle event
    "attack1": {"type": "button", "id": 2}, # Typically X/Square
    "attack2": {"type": "button", "id": 3}, # Typically Y/Triangle
    "dash": {"type": "button", "id": 5}, # Typically RB/R1
    "roll": {"type": "button", "id": 4}, # Typically LB/L1
    "interact": {"type": "button", "id": 10}, # Example: L3/LSB
    "projectile1": {"type": "hat", "id": 0, "value": (0,1)},    # Dpad Up
    "projectile2": {"type": "hat", "id": 0, "value": (1,0)},    # Dpad Right
    "projectile3": {"type": "hat", "id": 0, "value": (0,-1)},   # Dpad Down
    "projectile4": {"type": "hat", "id": 0, "value": (-1,0)},   # Dpad Left (often this is projectile4 or some other distinct weapon)
    "projectile5": {"type": "button", "id": 6},                 # Example: Back/Select (could be projectile5)
    "projectile6": {"type": "button", "id": 11},                # Example: R3/RSB (could be projectile6)
    "reset": {"type": "button", "id": 7},                       # Example: Start/Options (could be reset) - this is just a fallback example
    "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Example LT/L2 (could be projectile7)
    "pause": {"type": "button", "id": 9}, # Typically Start/Options button (often ID 9 for Xbox, 7 for others)
    "menu_confirm": {"type": "button", "id": 0}, # A/Cross also confirms
    "menu_cancel": {"type": "button", "id": 1},  # B/Circle also cancels
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
            if button_id is None: continue # Skip if button_id is missing
            final_mapping_for_action["id"] = button_id
        elif event_type_from_json == "axis":
            axis_id = details_from_json.get("axis_id")
            direction = details_from_json.get("direction")
            threshold = details_from_json.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_id is None or direction is None: continue # Skip if axis_id or direction missing
            final_mapping_for_action["id"] = axis_id
            final_mapping_for_action["value"] = direction
            final_mapping_for_action["threshold"] = threshold
        elif event_type_from_json == "hat":
            hat_id = details_from_json.get("hat_id")
            hat_value_tuple = details_from_json.get("value")
            if hat_id is None or hat_value_tuple is None: continue # Skip if hat_id or value missing
            final_mapping_for_action["id"] = hat_id
            final_mapping_for_action["value"] = tuple(hat_value_tuple) if isinstance(hat_value_tuple, list) else hat_value_tuple
        else:
            # print(f"Config Info: Unknown event_type '{event_type_from_json}' for '{json_key}'. Skipping.")
            continue # Skip unknown event types
        
        # If an internal action is already mapped, this will overwrite it.
        # This is how "WEAPON_DPAD_LEFT" was overwriting "RESET" if both mapped to "reset".
        # With the fix, they map to different internal actions ("projectile6" and "reset"), so no overwrite.
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
            if "reset" in LOADED_JOYSTICK_MAPPINGS:
                print(f"  -> 'reset' action is mapped to: {LOADED_JOYSTICK_MAPPINGS['reset']}")
            if "projectile6" in LOADED_JOYSTICK_MAPPINGS:
                print(f"  -> 'projectile6' action is mapped to: {LOADED_JOYSTICK_MAPPINGS['projectile6']}")
            return True
        else:
            print(f"Config Warning: Loaded JSON from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}' but resulted in empty or invalid mappings after translation.")
    except Exception as e:
        print(f"Config Error: Error loading '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using fallback mappings.")
    LOADED_JOYSTICK_MAPPINGS = {} # Ensure it's empty on failure
    return False

def get_action_key_map(player_id: int, device_id_str: str):
    """
    Returns the appropriate key/button mapping dictionary for a player and device.
    Used by Player class for input processing.
    """
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick"):
        # Use loaded external mappings if available, otherwise fallback
        return LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
    return {} # Should not happen if device_id_str is valid

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

    num_joysticks = joystick_handler.get_joystick_count()
    print(f"Config: Number of joysticks detected by joystick_handler: {num_joysticks}")

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
    else:
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick"):
        P2_MAPPINGS = LOADED_JOYSTICK_MAPPINGS.copy() if LOADED_JOYSTICK_MAPPINGS else DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        status_msg_p2 = "from controller_mappings.json" if LOADED_JOYSTICK_MAPPINGS else "using FALLBACK joystick mappings"
        print(f"Config: P2 assigned joystick mappings {status_msg_p2} for device '{CURRENT_P2_INPUT_DEVICE}'.")
    else:
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        
    print(f"Config: Player mappings updated. P1 using: {CURRENT_P1_INPUT_DEVICE}, P2 using: {CURRENT_P2_INPUT_DEVICE}")

if __name__ != "__main__":
    pass
else:
    print("--- Running config.py directly for testing ---")
    pygame.init()
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
    pygame.quit()
    print("--- config.py direct test finished ---")