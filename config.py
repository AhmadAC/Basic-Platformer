# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Assumes Pygame is the SOLE library for controller/joystick input.
Handles loading custom joystick mappings from a JSON file (format adapted for Pygame).
"""
# version 2.1.1 (Pygame Joystick Integration - Refined Mappings)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame # Import Pygame for joystick functions
import joystick_handler # Your Pygame-based joystick_handler

# --- Initialize Pygame Joystick (Required before calling its functions) ---
# This is crucial. joystick_handler.init_joysticks() should handle pygame.joystick.init()
# For safety, we can ensure it's called here too.
if not pygame.get_init(): # Checks if Pygame (general) is initialized
    print("Config: Pygame not initialized, initializing now...")
    pygame.init()
if not pygame.joystick.get_init(): # Checks if joystick subsystem is initialized
    print("Config: Pygame joystick module not initialized, initializing now...")
    try:
        pygame.joystick.init()
        print("Config: Pygame joystick module initialized successfully.")
    except pygame.error as e:
        print(f"Config Warning: Pygame joystick module failed to initialize: {e}. Joysticks will not be available.")

# Now that Pygame joystick is initialized, initialize our handler which populates the joysticks list
joystick_handler.init_joysticks()


# --- File for saving/loading game config (selected devices) ---
CONFIG_FILE_NAME = "game_config_pygame.json" # Changed name to avoid conflict if old config exists

# --- Path for external controller mappings ---
# This file's format will be geared towards Pygame's button/axis/hat IDs.
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
EXTERNAL_CONTROLLER_MAPPINGS_FILENAME = "pygame_controller_mappings.json"
EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONTROLLER_SETTINGS_SUBDIR,
    EXTERNAL_CONTROLLER_MAPPINGS_FILENAME
)

# --- Default Control Schemes ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1" # Remains the same
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2" # Remains the same

# --- Current Control Scheme ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE

# --- Joystick Axis Thresholds ---
AXIS_THRESHOLD_DEFAULT = 0.7 # This is a general concept, applicable to Pygame axes too

# --- Game Actions (Internal names the game logic uses) ---
# These remain the same as they are abstract game actions.
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
# This map translates abstract names from a potential JSON file to internal game actions.
# The JSON file itself would now contain Pygame-specific IDs.
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    # Example: If your JSON uses "DPAD_UP" for Pygame hat (0,1)
    # "DPAD_UP": "up", # If you want 'up' to also be triggered by this
    "MOVE_UP": "up", "MOVE_DOWN": "down", "MOVE_LEFT": "left", "MOVE_RIGHT": "right",
    "JUMP": "jump", "CROUCH": "crouch", "INTERACT": "interact",
    "ATTACK_PRIMARY": "attack1", "ATTACK_SECONDARY": "attack2",
    "DASH": "dash", "ROLL": "roll", "RESET": "reset",
    "WEAPON_1": "projectile1", "WEAPON_2": "projectile2", "WEAPON_3": "projectile3", "WEAPON_4": "projectile4",
    # For Pygame, D-Pad is typically a Hat.
    "WEAPON_DPAD_UP": "projectile4", # e.g. map to Hat 0, (0,1) in JSON
    "WEAPON_DPAD_DOWN": "projectile5",# e.g. map to Hat 0, (0,-1) in JSON
    "WEAPON_DPAD_LEFT": "projectile6", # e.g. map to Hat 0, (-1,0) in JSON
    "WEAPON_DPAD_RIGHT": "projectile7",# e.g. map to Hat 0, (1,0) in JSON
    "MENU_CONFIRM": "menu_confirm", "MENU_CANCEL": "menu_cancel", "MENU_RETURN": "pause",
}

# --- Default Keyboard Mappings (Using string representations for keys) ---
# These remain unchanged as they are for keyboard.
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

# --- Default Pygame Joystick Mappings (Conceptual - based on common XInput-like layouts) ---
# 'id' refers to Pygame's button/axis/hat index.
# 'value' for axis: -1 for negative direction (e.g., left/up), 1 for positive (e.g., right/down).
# 'value' for hat: tuple (x, y) e.g., (0,1) for D-Pad Up.
DEFAULT_PYGAME_JOYSTICK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},    # Left Stick X neg
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},   # Left Stick X pos
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT},      # Left Stick Y neg (often up)
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT},    # Left Stick Y pos (often down)
    
    "jump": {"type": "button", "id": 0},          # Typically A / Cross
    "crouch": {"type": "button", "id": 1},        # Typically B / Circle (or Right Stick Click if available)
    "attack1": {"type": "button", "id": 2},       # Typically X / Square
    "attack2": {"type": "button", "id": 3},       # Typically Y / Triangle
    
    "dash": {"type": "button", "id": 5},          # Typically RB / R1
    "roll": {"type": "button", "id": 4},          # Typically LB / L1
    "interact": {"type": "button", "id": 10},      # Example: Right Stick Click (R3)
    
    # Projectiles might map to D-Pad or other buttons
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)},   # D-Pad Up (Hat 0, Y=1)
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)},   # D-Pad Right (Hat 0, X=1)
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)},  # D-Pad Down (Hat 0, Y=-1)
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)},  # D-Pad Left (Hat 0, X=-1)
    
    "projectile5": {"type": "button", "id": 6},       # Example: Back/Select button
    "projectile6": {"type": "button", "id": 11},      # Example: Left Stick Click (L3)
    "reset": {"type": "button", "id": 7},         # Example: Start button
    "projectile7": {"type": "axis", "id": 2, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, # Example: Right Trigger (often axis 2 or 5)

    "pause": {"type": "button", "id": 7},         # Start button also for pause
    
    # Menu Navigation (could be same as game or different)
    "menu_confirm": {"type": "button", "id": 0},  # A / Cross
    "menu_cancel": {"type": "button", "id": 1},   # B / Circle
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)},
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Any] = {} # Store loaded Pygame-specific mappings
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def _translate_and_validate_pygame_joystick_mappings(raw_json_mappings: Any) -> Dict[str, Any]:
    """
    Translates raw JSON (expected to be in Pygame-friendly format) to internal mappings.
    The JSON keys should map to `EXTERNAL_TO_INTERNAL_ACTION_MAP`.
    The values should be dicts like: {"type": "button", "id": 0} or {"type": "axis", "id": 1, "value": -1}
    """
    translated_mappings: Dict[str, Any] = {}
    if not isinstance(raw_json_mappings, dict):
        print("Config Error: Raw Pygame JSON mappings is not a dictionary.")
        return {}

    for json_action_key, pygame_mapping_details in raw_json_mappings.items():
        internal_action_name = EXTERNAL_TO_INTERNAL_ACTION_MAP.get(json_action_key)
        if not internal_action_name:
            # Allow direct mapping if json_action_key is already an internal game action
            if json_action_key in GAME_ACTIONS:
                internal_action_name = json_action_key
            else:
                # print(f"Config Warning: JSON key '{json_action_key}' not in EXTERNAL_TO_INTERNAL_ACTION_MAP or GAME_ACTIONS. Skipping.")
                continue
        
        if not isinstance(pygame_mapping_details, dict):
            print(f"Config Warning: Mapping details for '{json_action_key}' is not a dict. Skipping.")
            continue

        event_type = pygame_mapping_details.get("type")
        event_id = pygame_mapping_details.get("id")

        if event_type not in ["button", "axis", "hat"] or event_id is None:
            print(f"Config Warning: Invalid type/id for '{json_action_key}': {pygame_mapping_details}. Skipping.")
            continue

        final_mapping_for_action: Dict[str, Any] = {"type": event_type, "id": event_id}

        if event_type == "axis":
            axis_value_direction = pygame_mapping_details.get("value") # Should be -1 or 1
            axis_threshold = pygame_mapping_details.get("threshold", AXIS_THRESHOLD_DEFAULT)
            if axis_value_direction not in [-1, 1]:
                print(f"Config Warning: Invalid axis 'value' for '{json_action_key}': {axis_value_direction}. Skipping.")
                continue
            final_mapping_for_action["value"] = axis_value_direction
            final_mapping_for_action["threshold"] = axis_threshold
        elif event_type == "hat":
            hat_value_tuple_or_list = pygame_mapping_details.get("value") # Should be (x,y) tuple/list
            if not isinstance(hat_value_tuple_or_list, (tuple, list)) or len(hat_value_tuple_or_list) != 2:
                print(f"Config Warning: Invalid hat 'value' for '{json_action_key}': {hat_value_tuple_or_list}. Skipping.")
                continue
            final_mapping_for_action["value"] = tuple(hat_value_tuple_or_list)
        
        translated_mappings[internal_action_name] = final_mapping_for_action
        
    return translated_mappings


def _load_external_pygame_joystick_mappings() -> bool:
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    LOADED_PYGAME_JOYSTICK_MAPPINGS = {} 
    if not os.path.exists(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH):
        print(f"Config Info: Pygame controller mappings file not found at '{EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH}'. Will use Pygame default fallback.")
        return False
    try:
        with open(EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH, 'r') as f:
            raw_mappings = json.load(f)
        LOADED_PYGAME_JOYSTICK_MAPPINGS = _translate_and_validate_pygame_joystick_mappings(raw_mappings)
        if LOADED_PYGAME_JOYSTICK_MAPPINGS:
            print(f"Config: Successfully loaded and translated {len(LOADED_PYGAME_JOYSTICK_MAPPINGS)} Pygame joystick mappings from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}'.")
            return True
        else:
            print(f"Config Warning: Loaded JSON from '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}' for Pygame but resulted in empty/invalid mappings.")
            return False
    except Exception as e:
        print(f"Config Error: Error loading Pygame mappings '{EXTERNAL_CONTROLLER_MAPPINGS_FILENAME}': {e}. Using Pygame default fallback.")
        LOADED_PYGAME_JOYSTICK_MAPPINGS = {}
        return False

# This function is less relevant now if joystick_handler directly uses Pygame
# but kept for structure if player_input_handler still expects this format.
def get_action_key_map(player_id: int, device_id_str: str) -> Dict[str, Any]:
    if device_id_str == "keyboard_p1": return DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif device_id_str == "keyboard_p2": return DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif device_id_str.startswith("joystick_pygame_"): # New prefix for Pygame joysticks
        return LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
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
    
    _load_external_pygame_joystick_mappings() # Load Pygame-specific mappings

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

    # Use joystick_handler (which should now be Pygame-based) for joystick count
    num_joysticks = joystick_handler.get_joystick_count()
    print(f"Config: Pygame detected {num_joysticks} joysticks.")

    # Player 1 Device Assignment
    # For Pygame, device ID will be like "joystick_pygame_0", "joystick_pygame_1", etc.
    if loaded_p1_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
        else:
            try:
                p1_joy_idx = int(loaded_p1_device_choice.split('_')[-1])
                if not (0 <= p1_joy_idx < num_joysticks):
                    print(f"Config Warning: P1's saved Pygame joystick ID {p1_joy_idx} no longer available (found {num_joysticks}). Assigning joystick_pygame_0 or keyboard.")
                    CURRENT_P1_INPUT_DEVICE = "joystick_pygame_0" 
                else:
                    CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice
            except ValueError: 
                CURRENT_P1_INPUT_DEVICE = "joystick_pygame_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE
    else: # Keyboard
        CURRENT_P1_INPUT_DEVICE = loaded_p1_device_choice

    # Player 2 Device Assignment
    if loaded_p2_device_choice.startswith("joystick_pygame_"):
        if num_joysticks == 0:
            CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
        else:
            try:
                p2_joy_idx = int(loaded_p2_device_choice.split('_')[-1])
                p1_is_pygame_joystick = CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_")
                p1_current_joy_idx_val = -1
                if p1_is_pygame_joystick:
                    try: p1_current_joy_idx_val = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                    except ValueError: p1_is_pygame_joystick = False

                if not (0 <= p2_joy_idx < num_joysticks):
                    print(f"Config Warning: P2's saved Pygame joystick ID {p2_joy_idx} no longer available.")
                    if num_joysticks == 1 and p1_is_pygame_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                    elif num_joysticks > 0 and (not p1_is_pygame_joystick or p1_current_joy_idx_val != 0): CURRENT_P2_INPUT_DEVICE = "joystick_pygame_0"
                    elif num_joysticks > 1 and p1_is_pygame_joystick and p1_current_joy_idx_val == 0: CURRENT_P2_INPUT_DEVICE = "joystick_pygame_1"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                elif p1_is_pygame_joystick and p2_joy_idx == p1_current_joy_idx_val:
                    print(f"Config Warning: P2 cannot use same Pygame joystick as P1 (ID {p1_current_joy_idx_val}).")
                    if num_joysticks > 1: CURRENT_P2_INPUT_DEVICE = f"joystick_pygame_{1 if p1_current_joy_idx_val == 0 else 0}"
                    else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
                else:
                    CURRENT_P2_INPUT_DEVICE = loaded_p2_device_choice
            except ValueError:
                CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE 
    else: # P2 is keyboard
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
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_"):
        P1_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_msg_p1 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK joystick mappings"
        print(f"Config: P1 assigned Pygame joystick mappings {status_msg_p1} for device '{CURRENT_P1_INPUT_DEVICE}'.")
    else: 
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick_pygame_"):
        P2_MAPPINGS = LOADED_PYGAME_JOYSTICK_MAPPINGS.copy() if LOADED_PYGAME_JOYSTICK_MAPPINGS else DEFAULT_PYGAME_JOYSTICK_MAPPINGS.copy()
        status_msg_p2 = "from JSON" if LOADED_PYGAME_JOYSTICK_MAPPINGS else "using Pygame FALLBACK joystick mappings"
        print(f"Config: P2 assigned Pygame joystick mappings {status_msg_p2} for device '{CURRENT_P2_INPUT_DEVICE}'.")
    else:
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        
    print(f"Config: Player mappings updated. P1 using: {CURRENT_P1_INPUT_DEVICE}, P2 using: {CURRENT_P2_INPUT_DEVICE}")

if __name__ == "__main__":
    print("--- Running config.py directly for testing (Pygame Joystick Mode) ---")
    
    # joystick_handler.init_joysticks() is called at the top of this script now.
    
    print(f"\n--- Calling load_config() for test ---")
    load_config()

    print(f"\nAfter test load_config():")
    print(f"  AXIS_THRESHOLD_DEFAULT: {AXIS_THRESHOLD_DEFAULT}")
    print(f"  CURRENT_P1_INPUT_DEVICE: {CURRENT_P1_INPUT_DEVICE}")
    print(f"  P1_MAPPINGS sample (jump): {P1_MAPPINGS.get('jump', 'Not Found')}")
    print(f"  CURRENT_P2_INPUT_DEVICE: {CURRENT_P2_INPUT_DEVICE}")
    print(f"  P2_MAPPINGS sample (jump): {P2_MAPPINGS.get('jump', 'Not Found')}")
    
    if LOADED_PYGAME_JOYSTICK_MAPPINGS:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS (example - jump): {LOADED_PYGAME_JOYSTICK_MAPPINGS.get('jump')}")
    else:
        print(f"  LOADED_PYGAME_JOYSTICK_MAPPINGS: Not loaded, using defaults.")
        print(f"  DEFAULT_PYGAME_JOYSTICK_MAPPINGS (example - jump): {DEFAULT_PYGAME_JOYSTICK_MAPPINGS.get('jump')}")


    joystick_handler.quit_joysticks()
    pygame.quit() # Quit Pygame itself
    print("--- config.py direct test finished ---")