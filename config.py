########## START OF FILE: config.py ##########
# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Allows defining default keyboard and joystick mappings, and storing current selections.
"""
# version 1.0.2 (Improved joystick ID handling on load, fallback to joystick_0)
import pygame
import json
import os
import joystick_handler # To check actual joystick count

# --- File for saving/loading config ---
CONFIG_FILE_NAME = "game_config.json"

# --- Default Control Schemes ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"  # "keyboard_p1", "joystick_0", "joystick_1", etc.
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"  # "keyboard_p2", "joystick_0", "joystick_1", etc.

# --- Current Control Scheme (These will be updated by settings_ui and loaded from file) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE

# --- Game Actions ---
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

DEFAULT_SWITCH_PRO_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": 0.7, "alt_type": "hat", "alt_id": 0, "alt_value": (-1,0)},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": 0.7, "alt_type": "hat", "alt_id": 0, "alt_value": (1,0)},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": 0.7, "alt_type": "hat", "alt_id": 0, "alt_value": (0,1)},  
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": 0.7, "alt_type": "hat", "alt_id": 0, "alt_value": (0,-1)},
    "jump": {"type": "button", "id": 0},      
    "attack1": {"type": "button", "id": 2},   
    "attack2": {"type": "button", "id": 1},   
    "dash": {"type": "button", "id": 3},      
    "roll": {"type": "button", "id": 5},      
    "interact": {"type": "button", "id": 4},  
    "projectile1": {"type": "button", "id": 6}, 
    "projectile2": {"type": "button", "id": 7}, 
    "pause": {"type": "button", "id": 9},     
    "menu_confirm": {"type": "button", "id": 1}, 
    "menu_cancel": {"type": "button", "id": 0},  
    "menu_up": {"type": "hat", "id": 0, "value": (0,1), "alt_type": "axis", "alt_id": 1, "alt_value": -1, "alt_threshold": 0.7},    
    "menu_down": {"type": "hat", "id": 0, "value": (0,-1), "alt_type": "axis", "alt_id": 1, "alt_value": 1, "alt_threshold": 0.7},  
    "menu_left": {"type": "hat", "id": 0, "value": (-1,0), "alt_type": "axis", "alt_id": 0, "alt_value": -1, "alt_threshold": 0.7},  
    "menu_right": {"type": "hat", "id": 0, "value": (1,0), "alt_type": "axis", "alt_id": 0, "alt_value": 1, "alt_threshold": 0.7}, 
}

P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def get_action_key_map(player_id: int, device_id_str: str):
    if device_id_str == "keyboard_p1":
        return P1_MAPPINGS 
    elif device_id_str == "keyboard_p2":
        return P2_MAPPINGS 
    elif "joystick" in device_id_str:
        if player_id == 1 and CURRENT_P1_INPUT_DEVICE == device_id_str:
            return P1_MAPPINGS
        elif player_id == 2 and CURRENT_P2_INPUT_DEVICE == device_id_str:
            return P2_MAPPINGS
        return DEFAULT_SWITCH_PRO_MAPPINGS 
    return {}


def _get_config_filepath():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config():
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    config_data = {
        "p1_input_device": CURRENT_P1_INPUT_DEVICE,
        "p2_input_device": CURRENT_P2_INPUT_DEVICE,
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
    filepath = _get_config_filepath()
    
    loaded_p1_device = DEFAULT_P1_INPUT_DEVICE
    loaded_p2_device = DEFAULT_P2_INPUT_DEVICE

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)
            
            loaded_p1_device = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2_device = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
            print(f"Configuration loaded from {filepath}: P1='{loaded_p1_device}', P2='{loaded_p2_device}'")

        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading configuration from {filepath}: {e}. Using defaults.")
            # Defaults are already set above
    else:
        print(f"Configuration file {filepath} not found. Using defaults.")

    # --- Validate and adjust joystick assignments based on currently connected joysticks ---
    num_joysticks = joystick_handler.get_joystick_count()

    # Validate P1 device
    if loaded_p1_device.startswith("joystick_"):
        try:
            p1_joy_idx = int(loaded_p1_device.split('_')[-1])
            if not (0 <= p1_joy_idx < num_joysticks):
                print(f"Config Warning: P1's configured joystick ID {p1_joy_idx} is not available (found {num_joysticks}).")
                if num_joysticks > 0:
                    print("Config: Falling back P1 to joystick_0.")
                    CURRENT_P1_INPUT_DEVICE = "joystick_0"
                else:
                    print("Config: No joysticks available. Falling back P1 to keyboard_p1.")
                    CURRENT_P1_INPUT_DEVICE = "keyboard_p1"
            else:
                CURRENT_P1_INPUT_DEVICE = loaded_p1_device
        except (ValueError, IndexError):
            print(f"Config Warning: Could not parse P1 joystick ID from '{loaded_p1_device}'. Falling back.")
            CURRENT_P1_INPUT_DEVICE = "keyboard_p1" if num_joysticks == 0 else "joystick_0"
    else:
        CURRENT_P1_INPUT_DEVICE = loaded_p1_device # It's a keyboard type

    # Validate P2 device (considering P1's assignment)
    if loaded_p2_device.startswith("joystick_"):
        try:
            p2_joy_idx = int(loaded_p2_device.split('_')[-1])
            p1_current_joy_idx = -1
            if CURRENT_P1_INPUT_DEVICE.startswith("joystick_"):
                 p1_current_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])

            if not (0 <= p2_joy_idx < num_joysticks):
                print(f"Config Warning: P2's configured joystick ID {p2_joy_idx} is not available.")
                if num_joysticks > 0 and (num_joysticks == 1 and p1_current_joy_idx != 0): # P2 can use joy 0 if P1 isn't
                    CURRENT_P2_INPUT_DEVICE = "joystick_0"
                elif num_joysticks > 1 and p1_current_joy_idx == 0 : # P1 is joy 0, P2 can be joy 1
                     CURRENT_P2_INPUT_DEVICE = "joystick_1"
                else: # Fallback to keyboard for P2
                    CURRENT_P2_INPUT_DEVICE = "keyboard_p2" if CURRENT_P1_INPUT_DEVICE != "keyboard_p1" else "keyboard_p1"
            elif p2_joy_idx == p1_current_joy_idx : # P2 cannot use the same joystick as P1
                print(f"Config Warning: P2 cannot use the same joystick as P1 (ID {p1_current_joy_idx}).")
                if num_joysticks > 1: # If another joystick is available
                    new_p2_joy_idx = 1 if p1_current_joy_idx == 0 else 0
                    CURRENT_P2_INPUT_DEVICE = f"joystick_{new_p2_joy_idx}"
                    print(f"Config: Assigning P2 to joystick_{new_p2_joy_idx}.")
                else: # Only one joystick, and P1 has it
                    print(f"Config: P1 has the only joystick. P2 falls back to keyboard.")
                    CURRENT_P2_INPUT_DEVICE = "keyboard_p1" # P2 uses P1's keyboard keys
            else:
                CURRENT_P2_INPUT_DEVICE = loaded_p2_device
        except (ValueError, IndexError):
            print(f"Config Warning: Could not parse P2 joystick ID from '{loaded_p2_device}'. Falling back.")
            CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
    else: # P2 is keyboard
        if loaded_p2_device == "keyboard_p1" and CURRENT_P1_INPUT_DEVICE != "keyboard_p1":
            # P1 is on joystick, P2 can safely use "keyboard_p1" (P1's default keys)
            CURRENT_P2_INPUT_DEVICE = "keyboard_p1"
        elif loaded_p2_device == "keyboard_p1" and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            # Conflict: P1 is on keyboard_p1, P2 cannot also be keyboard_p1. Default P2 to keyboard_p2.
            print("Config Warning: P1 and P2 both configured for 'keyboard_p1'. Setting P2 to 'keyboard_p2'.")
            CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
        else:
            CURRENT_P2_INPUT_DEVICE = loaded_p2_device


    update_player_mappings_from_device_choice() 
    return True

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS

    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P1_INPUT_DEVICE.startswith("joystick"): 
        P1_MAPPINGS = DEFAULT_SWITCH_PRO_MAPPINGS.copy() 
    else: 
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": 
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": 
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE.startswith("joystick"):
        P2_MAPPINGS = DEFAULT_SWITCH_PRO_MAPPINGS.copy() 
    else: 
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

    print(f"Config: P1 Mappings updated for device '{CURRENT_P1_INPUT_DEVICE}'.")
    print(f"Config: P2 Mappings updated for device '{CURRENT_P2_INPUT_DEVICE}'.")

########## END OF FILE: config.py ##########