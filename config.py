########## START OF FILE: config.py ##########
# config.py
# version 1.0.0.1
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Allows defining default keyboard and joystick mappings, and storing current selections.
"""
import pygame
import json
import os

# --- File for saving/loading config ---
CONFIG_FILE_NAME = "game_config.json"

# --- Default Control Schemes ---
DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"  # "keyboard_p1", "joystick_0", "joystick_1", etc.
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"  # "keyboard_p2", "joystick_0", "joystick_1", etc.

# --- Current Control Scheme (These will be updated by settings_ui and loaded from file) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE

# --- Game Actions ---
# These are the abstract actions the game understands.
# They will be mapped to specific keys or joystick buttons/axes.
GAME_ACTIONS = [
    "left", "right", "up", "down",  # Movement
    "jump",                         # Typically 'up' or a dedicated button
    "attack1", "attack2",           # Primary/Secondary attacks
    "dash", "roll", "interact",     # Abilities
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", # Weapon slots
    "pause", "menu_confirm", "menu_cancel" # UI Navigation (examples)
]

# --- Default Keyboard Mappings ---
# Player 1 Keyboard
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": pygame.K_a,
    "right": pygame.K_d,
    "up": pygame.K_w,         # Used for jump, climb_up
    "down": pygame.K_s,       # Used for crouch, climb_down
    "jump": pygame.K_w,       # Explicit jump, can be same as 'up'
    "attack1": pygame.K_v,
    "attack2": pygame.K_b,
    "dash": pygame.K_LSHIFT,
    "roll": pygame.K_LCTRL,
    "interact": pygame.K_e,
    "projectile1": pygame.K_1,
    "projectile2": pygame.K_2,
    "projectile3": pygame.K_3,
    "projectile4": pygame.K_4,
    "projectile5": pygame.K_5,
    "projectile6": pygame.K_6,
    "projectile7": pygame.K_7,
    "pause": pygame.K_ESCAPE, # Example pause key
}

# Player 2 Keyboard (distinct from P1)
DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": pygame.K_j,
    "right": pygame.K_l,
    "up": pygame.K_i,
    "down": pygame.K_k,
    "jump": pygame.K_i,
    "attack1": pygame.K_o,
    "attack2": pygame.K_p,
    "dash": pygame.K_SEMICOLON,
    "roll": pygame.K_QUOTE,
    "interact": pygame.K_BACKSLASH,
    "projectile1": pygame.K_KP_1,
    "projectile2": pygame.K_KP_2,
    "projectile3": pygame.K_KP_3,
    "projectile4": pygame.K_KP_4,
    "projectile5": pygame.K_KP_5,
    "projectile6": pygame.K_KP_6,
    "projectile7": pygame.K_KP_7,
    "pause": pygame.K_PAUSE, # Example, might not be used directly by P2
}

# --- Default Nintendo Switch Pro Controller Mappings (Generic Button/Axis Numbers) ---
# These are common mappings. Actual numbers might vary based on OS and drivers (e.g., BetterJoy).
# Buttons: A=0, B=1, X=2, Y=3, L=4, R=5, ZL=6, ZR=7, Minus=8, Plus=9, LStick=10, RStick=11, Home=12, Capture=13
# DPad (often comes as HAT 0): (x, y) -> (0,1) up, (0,-1) down, (-1,0) left, (1,0) right
# Axes: LeftX=0, LeftY=1, RightX=2 (or 3), RightY=3 (or 4), ZL_axis=~4, ZR_axis=~5 (often -1.0 to 1.0)
# For simplicity, we'll map DPad directions as separate actions if needed by game or map them to "up", "down", "left", "right".

DEFAULT_SWITCH_PRO_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": 0.5}, # Left Stick X < -0.5
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": 0.5}, # Left Stick X > 0.5
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": 0.5},   # Left Stick Y < -0.5 (Pygame Y-axis is often inverted)
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": 0.5}, # Left Stick Y > 0.5
    # OR DPad:
    # "left": {"type": "hat", "id": 0, "value": (-1,0)},
    # "right": {"type": "hat", "id": 0, "value": (1,0)},
    # "up": {"type": "hat", "id": 0, "value": (0,1)}, # Hat Y can be inverted too depending on Pygame
    # "down": {"type": "hat", "id": 0, "value": (0,-1)},

    "jump": {"type": "button", "id": 0},      # 'A' button (Nintendo layout 'B') or 'B' (Xbox layout 'A')
    "attack1": {"type": "button", "id": 2},   # 'X' button (Nintendo layout 'Y')
    "attack2": {"type": "button", "id": 1},   # 'B' button (Nintendo layout 'A') or 'Y' (Xbox layout 'X')
    "dash": {"type": "button", "id": 3},      # 'Y' button (Nintendo layout 'X')
    "roll": {"type": "button", "id": 5},      # 'R' bumper
    "interact": {"type": "button", "id": 4},  # 'L' bumper

    # Example for projectiles - these would need careful thought on a controller
    "projectile1": {"type": "button", "id": 6}, # ZL
    "projectile2": {"type": "button", "id": 7}, # ZR
    # "projectile_next": {"type": "button", "id": PLUS_BUTTON_ID_HERE},
    # "projectile_prev": {"type": "button", "id": MINUS_BUTTON_ID_HERE},

    "pause": {"type": "button", "id": 9},     # '+' (Plus) button
}

# --- Mappings Storage ---
# These will hold the actual pygame key/joystick codes after loading/setting.
# Initialized with defaults.
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
# If a player is set to joystick, their P1_MAPPINGS/P2_MAPPINGS will be populated
# from DEFAULT_SWITCH_PRO_MAPPINGS (or another joystick config).


def get_action_key_map(player_id: int, device_type: str):
    """
    Returns the appropriate key/button mapping dictionary for the player.
    For keyboard, it's direct. For joystick, it would be more complex
    as joystick events are handled differently (axis, button, hat).

    This function might be simplified or expanded based on how input processing is done.
    For now, it helps settings_ui display current keyboard keys.
    """
    if device_type == "keyboard_p1":
        return P1_MAPPINGS # Or a fresh copy of DEFAULT_KEYBOARD_P1_MAPPINGS
    elif device_type == "keyboard_p2":
        return P2_MAPPINGS # Or a fresh copy of DEFAULT_KEYBOARD_P2_MAPPINGS
    elif "joystick" in device_type:
        # This is a placeholder. Displaying joystick mappings directly as keys is not straightforward.
        # The settings UI will need a different way to show these.
        # For now, return the default joystick abstract mapping for reference.
        return DEFAULT_SWITCH_PRO_MAPPINGS
    return {}


def _get_config_filepath():
    """Gets the absolute path to the config file."""
    # Place it in the same directory as this config.py file for simplicity
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config():
    """Saves the current control schemes to a JSON file."""
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    # In a more complex scenario, you'd save P1_MAPPINGS and P2_MAPPINGS if they were remappable.
    config_data = {
        "p1_input_device": CURRENT_P1_INPUT_DEVICE,
        "p2_input_device": CURRENT_P2_INPUT_DEVICE,
        # "p1_key_mappings": P1_MAPPINGS, # If keyboard keys are remappable
        # "p2_key_mappings": P2_MAPPINGS, # If keyboard keys are remappable
        # "joystick_mappings": P1_MAPPINGS if "joystick" in CURRENT_P1_INPUT_DEVICE else (P2_MAPPINGS if "joystick" in CURRENT_P2_INPUT_DEVICE else DEFAULT_SWITCH_PRO_MAPPINGS)
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
    """Loads control schemes from a JSON file. If file doesn't exist or is invalid, uses defaults."""
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE, P1_MAPPINGS, P2_MAPPINGS
    filepath = _get_config_filepath()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                config_data = json.load(f)
            
            CURRENT_P1_INPUT_DEVICE = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            CURRENT_P2_INPUT_DEVICE = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)

            # If P1_MAPPINGS etc. were saved, load them here.
            # For now, they just stick to defaults unless explicitly changed by settings UI.
            # P1_MAPPINGS = config_data.get("p1_key_mappings", DEFAULT_KEYBOARD_P1_MAPPINGS.copy())
            # P2_MAPPINGS = config_data.get("p2_key_mappings", DEFAULT_KEYBOARD_P2_MAPPINGS.copy())

            print(f"Configuration loaded from {filepath}")
            # Apply the loaded device choice to the active mappings
            update_player_mappings_from_device_choice()
            return True
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading configuration from {filepath}: {e}. Using defaults.")
    else:
        print(f"Configuration file {filepath} not found. Using defaults.")
    
    # Set to defaults if load failed or file not found
    CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
    CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    update_player_mappings_from_device_choice() # Ensure mappings reflect default devices
    return False

def update_player_mappings_from_device_choice():
    """
    Updates P1_MAPPINGS and P2_MAPPINGS based on CURRENT_P1_INPUT_DEVICE and CURRENT_P2_INPUT_DEVICE.
    This is crucial after loading config or when settings are changed in the UI.
    """
    global P1_MAPPINGS, P2_MAPPINGS

    # Player 1 Mappings
    if CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif "joystick" in CURRENT_P1_INPUT_DEVICE: # e.g., "joystick_0"
        P1_MAPPINGS = DEFAULT_SWITCH_PRO_MAPPINGS.copy() # Or specific joystick config
    else: # Fallback
        P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    # Player 2 Mappings
    if CURRENT_P2_INPUT_DEVICE == "keyboard_p1": # P2 using P1 keyboard keys
        P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": # P2 using P2 keyboard keys
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    elif "joystick" in CURRENT_P2_INPUT_DEVICE:
        P2_MAPPINGS = DEFAULT_SWITCH_PRO_MAPPINGS.copy() # Or specific joystick config
    else: # Fallback
        P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

    print(f"Config: P1 Mappings updated for device '{CURRENT_P1_INPUT_DEVICE}'.")
    print(f"Config: P2 Mappings updated for device '{CURRENT_P2_INPUT_DEVICE}'.")


# --- Initialize by loading config ---
# load_config() # Call this in main.py after pygame.init() and joystick_init()
                # and before entering the main game loop or settings screen.
                # For now, settings_ui will call it.
########## END OF FILE: config.py ##########