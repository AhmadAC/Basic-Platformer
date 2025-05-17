########## START OF FILE: config.py ##########
# config.py
# -*- coding: utf-8 -*-
# version 1.0.6 (Menu cancel default to Y button (ID 3), refined external map loading)
import pygame
import json
import os
import joystick_handler
import constants as C

def _config_print(msg_type, msg): print(f"CONFIG {msg_type}: {msg}")
CONFIG_FILE_NAME = "game_config.json"
EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH = r"C:\Users\ahmad\OneDrive\Computer Files\Programming\Scripts\Github\Scripts\Python Scripts\Canvas Scripts\2024\Python Game\Platformer\controller_settings\controller_mappings.json"

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE

GAME_ACTIONS = [
    "left", "right", "up", "down", "jump",
    "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]
DEFAULT_KEYBOARD_P1_MAPPINGS = {
    "left": pygame.K_a, "right": pygame.K_d, "up": pygame.K_w, "down": pygame.K_s, "jump": pygame.K_w,
    "attack1": pygame.K_v, "attack2": pygame.K_b, "dash": pygame.K_LSHIFT, "roll": pygame.K_LCTRL, "interact": pygame.K_e,
    "projectile1": pygame.K_1, "projectile2": pygame.K_2, "projectile3": pygame.K_3, "projectile4": pygame.K_4,
    "projectile5": pygame.K_5, "projectile6": pygame.K_6, "projectile7": pygame.K_7,
    "pause": pygame.K_ESCAPE, "menu_confirm": pygame.K_RETURN, "menu_cancel": pygame.K_ESCAPE,
    "menu_up": pygame.K_UP, "menu_down": pygame.K_DOWN, "menu_left": pygame.K_LEFT, "menu_right": pygame.K_RIGHT,
}
DEFAULT_KEYBOARD_P2_MAPPINGS = {
    "left": pygame.K_j, "right": pygame.K_l, "up": pygame.K_i, "down": pygame.K_k, "jump": pygame.K_i,
    "attack1": pygame.K_o, "attack2": pygame.K_p, "dash": pygame.K_SEMICOLON, "roll": pygame.K_QUOTE, "interact": pygame.K_BACKSLASH,
    "projectile1": pygame.K_KP_1, "projectile2": pygame.K_KP_2, "projectile3": pygame.K_KP_3, "projectile4": pygame.K_KP_4,
    "projectile5": pygame.K_KP_5, "projectile6": pygame.K_KP_6, "projectile7": pygame.K_KP_7,
    "pause": pygame.K_PAUSE, "menu_confirm": pygame.K_KP_ENTER, "menu_cancel": pygame.K_DELETE,
    "menu_up": pygame.K_KP_8, "menu_down": pygame.K_KP_2, "menu_left": pygame.K_KP_4, "menu_right": pygame.K_KP_6,
}

AXIS_THRESHOLD_DEFAULT = getattr(C, "AXIS_THRESHOLD", 0.7)
DEFAULT_JOYSTICK_FALLBACK_MAPPINGS = {
    "left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT, "alt_type": "hat", "alt_id": 0, "alt_value": (-1,0)},
    "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT, "alt_type": "hat", "alt_id": 0, "alt_value": (1,0)},
    "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT, "alt_type": "hat", "alt_id": 0, "alt_value": (0,1)},
    "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT, "alt_type": "hat", "alt_id": 0, "alt_value": (0,-1)},
    "jump": {"type": "button", "id": 0},      # South button (A on Xbox, X on PS)
    "attack1": {"type": "button", "id": 2},   # West button (X on Xbox, Square on PS)
    "attack2": {"type": "button", "id": 1},   # East button (B on Xbox, Circle on PS)
    "dash": {"type": "button", "id": 3},      # North button (Y on Xbox, Triangle on PS) <--- THIS IS BUTTON 3
    "roll": {"type": "button", "id": 5},      # Right Bumper
    "interact": {"type": "button", "id": 4},  # Left Bumper
    "projectile1": {"type": "axis", "id": 4, "value": 1, "threshold": 0.5},
    "projectile2": {"type": "axis", "id": 5, "value": 1, "threshold": 0.5},
    "projectile3": {"type": "button", "id": 13},
    "projectile4": {"type": "button", "id": 14},
    "projectile5": {"type": "button", "id": 15},
    "projectile6": {"type": "button", "id": 16},
    "projectile7": {"type": "button", "id": 10},
    "pause": {"type": "button", "id": 9},
    "menu_confirm": {"type": "button", "id": 0}, # A / South button
    "menu_cancel": {"type": "button", "id": 3},  # Y / North button  <--- CHANGED FROM 1 to 3
    "menu_up": {"type": "hat", "id": 0, "value": (0,1)},
    "menu_down": {"type": "hat", "id": 0, "value": (0,-1)},
    "menu_left": {"type": "hat", "id": 0, "value": (-1,0)},
    "menu_right": {"type": "hat", "id": 0, "value": (1,0)},
}

GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP: dict = {}
P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

def load_external_controller_mappings(filepath=EXTERNAL_CONTROLLER_MAPPINGS_FILE_PATH):
    global GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP
    GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP = {}
    # This dictionary translates the KEY STRINGS from your
    # controller_mapper_gui.py's MAPPABLE_KEYS to your game's internal GAME_ACTIONS.
    # Example: If in your GUI, you map your controller's Y button to the "SHIFT" key,
    # and you want "menu_cancel" to be triggered by this, you'd have:
    # "SHIFT": "menu_cancel"
    gui_key_to_game_action = {
        "W": "up", "A": "left", "S": "down", "D": "right",
        "SPACE": "jump",    # Assuming SPACE in GUI maps to "jump" in game
        "V": "attack1",
        "B": "attack2",     # GUI "B" (keyboard B) maps to game action "attack2"
        "SHIFT": "dash",    # GUI "SHIFT" maps to game action "dash"
        "CTRL": "roll",
        "Q": "interact",
        "E": "pause",
        "1": "projectile1", "2": "projectile2", "3": "projectile3",
        "4": "projectile4", "5": "projectile5",
        "ALT": "projectile7", # Assuming ALT in GUI maps to projectile7

        # Explicitly map GUI keys to menu actions if you want to override defaults via JSON
        # For example, if you use the "Y" key in your GUI tool to map your controller's Y button:
        # "Y_GUI_KEY": "menu_cancel", # Replace "Y_GUI_KEY" with the actual string from MAPPABLE_KEYS
        # If not mapped here, menu actions will rely on DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.
        # Your current JSON maps controller buttons to "SHIFT", "ALT", etc. for gameplay actions.
        # To make controller Y cancel in menu via JSON:
        # 1. In controller_mapper_gui.py, add a key like "MENU_CANCEL_KEY" to MAPPABLE_KEYS.
        # 2. In gui_key_to_game_action here, add: "MENU_CANCEL_KEY": "menu_cancel".
        # 3. In the GUI tool, map your controller's Y button to "MENU_CANCEL_KEY".
        # For now, we will rely on DEFAULT_JOYSTICK_FALLBACK_MAPPINGS for menu_cancel.
    }
    # ... (rest of load_external_controller_mappings is the same)
    if not os.path.exists(filepath):
        _config_print("WARNING", f"External controller mapping file not found: '{filepath}'.")
        return False
    try:
        with open(filepath, 'r') as f: loaded_gui_mappings = json.load(f)
        successful_translations = 0
        for gui_key, controller_config in loaded_gui_mappings.items():
            game_action = gui_key_to_game_action.get(gui_key)
            if game_action and game_action in GAME_ACTIONS:
                event_type = controller_config.get("event_type")
                details = controller_config.get("details")
                if event_type and details:
                    map_entry = {"type": event_type}
                    if event_type == "button": map_entry["id"] = details.get("button_id")
                    elif event_type == "axis":
                        map_entry["id"] = details.get("axis_id")
                        map_entry["value"] = details.get("direction")
                        map_entry["threshold"] = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
                    elif event_type == "hat":
                        map_entry["id"] = details.get("hat_id")
                        map_entry["value"] = tuple(details.get("value", (0,0)))
                    valid_translated = False
                    if event_type == "button" and map_entry.get("id") is not None: valid_translated = True
                    elif event_type == "axis" and all(k in map_entry for k in ["id", "value", "threshold"]): valid_translated = True
                    elif event_type == "hat" and all(k in map_entry for k in ["id", "value"]): valid_translated = True
                    if valid_translated:
                        GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP[game_action] = map_entry
                        successful_translations += 1
                    else: _config_print("WARNING", f"Malformed details for GUI key '{gui_key}' (Action: '{game_action}'). Details: {details}")
                else: _config_print("WARNING", f"Missing event_type/details for GUI key '{gui_key}'.")
        if successful_translations > 0:
            _config_print("INFO", f"Loaded {successful_translations} external controller mappings from '{filepath}'.")
            return True
        _config_print("WARNING", f"Loaded external mappings from '{filepath}', but no valid translations made.")
        return False
    except Exception as e:
        _config_print("ERROR", f"Loading/parsing external controller mappings from '{filepath}': {e}")
        GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP = {}
        return False

def _get_config_filepath():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, CONFIG_FILE_NAME)

def save_config():
    config_data = {"p1_input_device": CURRENT_P1_INPUT_DEVICE, "p2_input_device": CURRENT_P2_INPUT_DEVICE}
    filepath = _get_config_filepath()
    try:
        with open(filepath, 'w') as f: json.dump(config_data, f, indent=4)
        _config_print("INFO", f"Game configuration (device choices) saved to {filepath}")
        return True
    except IOError as e: _config_print("ERROR", f"Saving game config to {filepath}: {e}"); return False

def update_player_mappings_from_device_choice():
    global P1_MAPPINGS, P2_MAPPINGS
    def get_merged_joystick_map(player_num_str):
        final_map = DEFAULT_JOYSTICK_FALLBACK_MAPPINGS.copy()
        if GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP:
            _config_print("INFO", f"{player_num_str} is joystick. Merging external map with defaults.")
            final_map.update(GAME_ACTION_TO_EXTERNAL_CONTROLLER_MAP)
        else:
            _config_print("INFO", f"{player_num_str} is joystick. No valid external map. Using defaults.")
        return final_map

    if CURRENT_P1_INPUT_DEVICE.startswith("joystick"): P1_MAPPINGS = get_merged_joystick_map("P1")
    elif CURRENT_P1_INPUT_DEVICE == "keyboard_p1": P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    else: P1_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()

    if CURRENT_P2_INPUT_DEVICE.startswith("joystick"): P2_MAPPINGS = get_merged_joystick_map("P2")
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p1": P2_MAPPINGS = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
    elif CURRENT_P2_INPUT_DEVICE == "keyboard_p2": P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
    else: P2_MAPPINGS = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()

    _config_print("DEBUG", f"P1 Mappings for '{CURRENT_P1_INPUT_DEVICE}'. menu_confirm: {P1_MAPPINGS.get('menu_confirm', 'N/A')}, menu_cancel: {P1_MAPPINGS.get('menu_cancel', 'N/A')}")
    _config_print("DEBUG", f"P2 Mappings for '{CURRENT_P2_INPUT_DEVICE}'. menu_confirm: {P2_MAPPINGS.get('menu_confirm', 'N/A')}, menu_cancel: {P2_MAPPINGS.get('menu_cancel', 'N/A')}")


def load_config():
    global CURRENT_P1_INPUT_DEVICE, CURRENT_P2_INPUT_DEVICE
    filepath = _get_config_filepath()
    loaded_p1, loaded_p2 = DEFAULT_P1_INPUT_DEVICE, DEFAULT_P2_INPUT_DEVICE
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f: config_data = json.load(f)
            loaded_p1 = config_data.get("p1_input_device", DEFAULT_P1_INPUT_DEVICE)
            loaded_p2 = config_data.get("p2_input_device", DEFAULT_P2_INPUT_DEVICE)
            _config_print("INFO", f"Device choices loaded from {filepath}: P1='{loaded_p1}', P2='{loaded_p2}'")
        except Exception as e: _config_print("ERROR", f"Loading {filepath}: {e}. Using defaults.")
    else: _config_print("INFO", f"{filepath} not found. Using default device choices.")

    num_joysticks = joystick_handler.get_joystick_count()
    if loaded_p1.startswith("joystick_"):
        try:
            idx = int(loaded_p1.split('_')[-1])
            CURRENT_P1_INPUT_DEVICE = loaded_p1 if 0 <= idx < num_joysticks else ("joystick_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE)
        except: CURRENT_P1_INPUT_DEVICE = ("joystick_0" if num_joysticks > 0 else DEFAULT_P1_INPUT_DEVICE)
    else: CURRENT_P1_INPUT_DEVICE = loaded_p1

    if loaded_p2.startswith("joystick_"):
        try:
            idx = int(loaded_p2.split('_')[-1])
            p1_joy_idx = -1
            if CURRENT_P1_INPUT_DEVICE.startswith("joystick_"): p1_joy_idx = int(CURRENT_P1_INPUT_DEVICE.split('_')[-1])
            if not (0 <= idx < num_joysticks) or idx == p1_joy_idx:
                if num_joysticks == 1 and p1_joy_idx != 0: CURRENT_P2_INPUT_DEVICE = "joystick_0"
                elif num_joysticks > 1 and p1_joy_idx == 0: CURRENT_P2_INPUT_DEVICE = "joystick_1"
                elif num_joysticks > 1 and p1_joy_idx != 0: CURRENT_P2_INPUT_DEVICE = "joystick_0"
                else: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
            else: CURRENT_P2_INPUT_DEVICE = loaded_p2
        except: CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE
    else:
        if loaded_p2 == "keyboard_p1" and CURRENT_P1_INPUT_DEVICE == "keyboard_p1":
            CURRENT_P2_INPUT_DEVICE = "keyboard_p2"
        else: CURRENT_P2_INPUT_DEVICE = loaded_p2
    update_player_mappings_from_device_choice()
    _config_print("INFO", f"Final active config: P1='{CURRENT_P1_INPUT_DEVICE}', P2='{CURRENT_P2_INPUT_DEVICE}'")
    return True

########## END OF FILE: config.py ##########