# config.py
# -*- coding: utf-8 -*-
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1-P4.
"""
# version 2.3.5 (Ultra-debug for Px_MAPPINGS content)
from typing import Dict, Optional, Any, List, Tuple
import json
import os
import pygame
from PySide6.QtCore import Qt

# --- Global Pygame State Variables ---
_pygame_initialized_globally = False
_joystick_initialized_globally = False
_detected_joystick_count_global = 0
_detected_joystick_names_global: List[str] = []
_joystick_objects_global: List[Optional[pygame.joystick.Joystick]] = []

def init_pygame_and_joystick_globally(force_rescan=False):
    global _pygame_initialized_globally, _joystick_initialized_globally, _detected_joystick_count_global
    global _detected_joystick_names_global, _joystick_objects_global
    if not _pygame_initialized_globally:
        try: pygame.init(); _pygame_initialized_globally = True; print("Config: Pygame globally initialized.")
        except Exception as e: print(f"Config CRITICAL: Pygame global init failed: {e}"); return
    if not _joystick_initialized_globally:
        try: pygame.joystick.init(); _joystick_initialized_globally = True; print("Config: Pygame Joystick globally initialized.")
        except Exception as e: print(f"Config CRITICAL: Pygame Joystick global init failed: {e}"); return
    current_count = pygame.joystick.get_count()
    if force_rescan or current_count != _detected_joystick_count_global:
        print(f"Config: Joystick scan. Force:{force_rescan}, Old:{_detected_joystick_count_global}, New:{current_count}")
        _detected_joystick_count_global = current_count; _detected_joystick_names_global = []
        for old_joy in _joystick_objects_global:
            if old_joy and old_joy.get_init():
                try: old_joy.quit()
                except pygame.error: pass
        _joystick_objects_global = []
        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i); _detected_joystick_names_global.append(joy.get_name())
                _joystick_objects_global.append(joy)
            except pygame.error as e:
                print(f"Config Warn: Error joystick {i}: {e}"); _detected_joystick_names_global.append(f"ErrJoy{i}")
                _joystick_objects_global.append(None)
        print(f"Config: Scan found {_detected_joystick_count_global} joysticks: {_detected_joystick_names_global}")

init_pygame_and_joystick_globally()

CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONTROLLER_SETTINGS_SUBDIR, MAPPINGS_AND_DEVICE_CHOICES_FILENAME)
print(f"DEBUG config.py: Expecting JSON at: {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = True
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = True; DEFAULT_P2_CONTROLLER_ENABLED = True
DEFAULT_P3_INPUT_DEVICE = "unassigned"; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
DEFAULT_P4_INPUT_DEVICE = "unassigned"; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False
UNASSIGNED_DEVICE_ID = "unassigned"; UNASSIGNED_DEVICE_NAME = "Unassigned"

CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"]
AXIS_THRESHOLD_DEFAULT = 0.7
GAME_ACTIONS = ["left", "right", "up", "down", "jump", "crouch", "attack1", "attack2", "dash", "roll", "interact", "projectile1", "projectile2", "projectile3", "projectile4", "projectile5", "projectile6", "projectile7", "pause", "reset", "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"]
EXTERNAL_TO_INTERNAL_ACTION_MAP = {"MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right", "JUMP_ACTION": "jump", "PRIMARY_ATTACK": "attack1", "W": "up", "A": "left", "S": "down", "D": "right", "SPACE": "jump", "V": "attack1", "B": "attack2", "SHIFT": "dash"}

DEFAULT_KEYBOARD_P1_MAPPINGS = {"left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S, "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B, "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E, "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4, "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7, "reset": Qt.Key.Key_Q, "pause": Qt.Key.Key_Escape, "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape, "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right}
DEFAULT_KEYBOARD_P2_MAPPINGS = {"left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K, "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K, "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P, "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash, "projectile1": Qt.Key.Key_8, "projectile2": Qt.Key.Key_9, "projectile3": Qt.Key.Key_0, "projectile4": Qt.Key.Key_Minus, "projectile5": Qt.Key.Key_Equal, "projectile6": Qt.Key.Key_BracketLeft, "projectile7": Qt.Key.Key_BracketRight, "reset": Qt.Key.Key_Period, "pause": Qt.Key.Key_F12, "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete, "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End}
DEFAULT_GENERIC_JOYSTICK_MAPPINGS = {"left": {"type": "axis", "id": 0, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT}, "right": {"type": "axis", "id": 0, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, "up": {"type": "axis", "id": 1, "value": -1, "threshold": AXIS_THRESHOLD_DEFAULT}, "down": {"type": "axis", "id": 1, "value": 1, "threshold": AXIS_THRESHOLD_DEFAULT}, "jump": {"type": "button", "id": 0}, "crouch": {"type": "button", "id": 1}, "attack1": {"type": "button", "id": 2}, "attack2": {"type": "button", "id": 3}, "dash": {"type": "button", "id": 5}, "roll": {"type": "button", "id": 4}, "interact": {"type": "button", "id": 10}, "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, "projectile2": {"type": "hat", "id": 0, "value": (1, 0)}, "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)}, "reset": {"type": "button", "id": 6}, "pause": {"type": "button", "id": 7}, "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1}, "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, "menu_down": {"type": "hat", "id": 0, "value": (0, -1)}, "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, "menu_right": {"type": "hat", "id": 0, "value": (1, 0)}}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}
P1_MAPPINGS: Dict[str, Any] = {}; P2_MAPPINGS: Dict[str, Any] = {}; P3_MAPPINGS: Dict[str, Any] = {}; P4_MAPPINGS: Dict[str, Any] = {}

def _translate_gui_map_to_runtime(gui_map_for_single_controller: Dict[str, Any]) -> Dict[str, Any]:
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(gui_map_for_single_controller, dict): return {}
    # print(f"DEBUG _translate_gui_map_to_runtime: INPUT_GUI_MAP = {json.dumps(gui_map_for_single_controller, indent=2)}")
    for action_name, mapping_entry_gui_format in gui_map_for_single_controller.items():
        if action_name not in GAME_ACTIONS: continue
        if not isinstance(mapping_entry_gui_format, dict): continue
        event_type = mapping_entry_gui_format.get("event_type"); details = mapping_entry_gui_format.get("details")
        if not event_type or not isinstance(details, dict): continue
        runtime_entry: Dict[str, Any] = {"type": event_type}; valid_entry = False
        try:
            if event_type == "button":
                button_id = details.get("button_id")
                if button_id is not None: runtime_entry["id"] = int(button_id); valid_entry = True
            elif event_type == "axis":
                axis_id = details.get("axis_id"); direction = details.get("direction"); threshold = details.get("threshold", AXIS_THRESHOLD_DEFAULT)
                if axis_id is not None and direction is not None:
                    runtime_entry["id"] = int(axis_id); runtime_entry["value"] = int(direction)
                    runtime_entry["threshold"] = float(threshold); valid_entry = True
            elif event_type == "hat":
                hat_id = details.get("hat_id"); value = details.get("value")
                if hat_id is not None and isinstance(value, list) and len(value) == 2:
                    runtime_entry["id"] = int(hat_id); runtime_entry["value"] = tuple(map(int, value)); valid_entry = True
        except (ValueError, TypeError) as e: print(f"Config Error (_translate): Invalid data for {action_name}, type {event_type}: {details} - Error: {e}")
        if valid_entry: runtime_mappings[action_name] = runtime_entry
    print(f"DEBUG _translate_gui_map_to_runtime: OUTPUT_RUNTIME_MAP for one controller = {json.dumps(runtime_mappings, indent=2)}")
    return runtime_mappings

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    devices = []
    if not _joystick_initialized_globally: return devices
    for i in range(_detected_joystick_count_global):
        joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_n = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"UnkJoy{i}"
        guid_s: Optional[str] = None
        if joy_obj:
            init_state = joy_obj.get_init()
            try:
                if not init_state: joy_obj.init()
                guid_s = joy_obj.get_guid()
            except pygame.error as e: print(f"Config Warn: GUID error joy {i} ('{joy_n}'): {e}")
            finally:
                if not init_state and joy_obj.get_init(): joy_obj.quit()
        internal_id = f"joystick_pygame_{i}"; display_n = f"Joy {i}: {joy_n.split(' (GUID:')[0]}"
        devices.append((display_n, internal_id, guid_s, i))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]: return _joystick_objects_global

def save_config():
    player_settings = {}
    for i in range(1, 5):
        player_settings[f"player{i}_settings"] = {"input_device": globals().get(f"CURRENT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID), "keyboard_enabled": globals().get(f"P{i}_KEYBOARD_ENABLED", False), "controller_enabled": globals().get(f"P{i}_CONTROLLER_ENABLED", False)}
    data = {"config_version": "2.3.5", **player_settings, "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS}
    try:
        subdir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(subdir): os.makedirs(subdir)
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        update_player_mappings_from_config(); return True
    except IOError as e: print(f"Config Error: Saving settings: {e}"); return False

def load_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    init_pygame_and_joystick_globally(force_rescan=True)
    raw_data = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_data = json.load(f)
            print(f"Config: Loaded from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e: print(f"Config Error: Loading JSON: {e}. Using defaults."); raw_data = {}
    else: print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults."); raw_data = {}

    for i in range(1, 5):
        p_set = raw_data.get(f"player{i}_settings", {})
        globals()[f"CURRENT_P{i}_INPUT_DEVICE"] = p_set.get("input_device", globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID))
        current_d = globals()[f"CURRENT_P{i}_INPUT_DEVICE"]
        kbd_en_file = p_set.get("keyboard_enabled", None); ctrl_en_file = p_set.get("controller_enabled", None)
        if kbd_en_file is None or ctrl_en_file is None:
            globals()[f"P{i}_KEYBOARD_ENABLED"] = current_d.startswith("keyboard_")
            globals()[f"P{i}_CONTROLLER_ENABLED"] = current_d.startswith("joystick_pygame_")
            if current_d.startswith("joystick_pygame_") and kbd_en_file is None:
                 globals()[f"P{i}_KEYBOARD_ENABLED"] = globals().get(f"DEFAULT_P{i}_KEYBOARD_ENABLED", True)
        else:
            globals()[f"P{i}_KEYBOARD_ENABLED"] = kbd_en_file; globals()[f"P{i}_CONTROLLER_ENABLED"] = ctrl_en_file
            if current_d.startswith("keyboard_") and ctrl_en_file: globals()[f"P{i}_CONTROLLER_ENABLED"] = False
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_data.get("joystick_mappings", {})
    print("--- LOAD_CONFIG DEBUG ---"); print(f"LOADED_PYGAME_JOYSTICK_MAPPINGS (GUID-keyed GUI format):"); print(json.dumps(LOADED_PYGAME_JOYSTICK_MAPPINGS, indent=2, default=lambda o: f"<not serializable: {type(o).__name__}>")); print("--- END LOAD_CONFIG DEBUG ---")

    if not raw_data: # Auto-assign if no config file
        print("Config: No valid config file, auto-assigning.")
        if _detected_joystick_count_global > 0:
            globals()["CURRENT_P1_INPUT_DEVICE"] = "joystick_pygame_0"; globals()["P1_CONTROLLER_ENABLED"] = True; globals()["P1_KEYBOARD_ENABLED"] = True
            if _detected_joystick_count_global > 1: globals()["CURRENT_P2_INPUT_DEVICE"] = "joystick_pygame_1"; globals()["P2_CONTROLLER_ENABLED"] = True; globals()["P2_KEYBOARD_ENABLED"] = True
            else: globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE; globals()["P2_CONTROLLER_ENABLED"] = False; globals()["P2_KEYBOARD_ENABLED"] = True
        else:
            globals()["CURRENT_P1_INPUT_DEVICE"] = DEFAULT_P1_INPUT_DEVICE; globals()["P1_CONTROLLER_ENABLED"] = False; globals()["P1_KEYBOARD_ENABLED"] = True
            globals()["CURRENT_P2_INPUT_DEVICE"] = DEFAULT_P2_INPUT_DEVICE; globals()["P2_CONTROLLER_ENABLED"] = False; globals()["P2_KEYBOARD_ENABLED"] = True

    available_joy_ids = [f"joystick_pygame_{j}" for j in range(_detected_joystick_count_global)]; assigned = {}
    for i in range(1, 5):
        curr_dev_var = f"CURRENT_P{i}_INPUT_DEVICE"; def_dev_val = globals().get(f"DEFAULT_P{i}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        curr_dev_val = globals().get(curr_dev_var, def_dev_val)
        if curr_dev_val.startswith("joystick_pygame_"):
            if curr_dev_val not in available_joy_ids: globals()[curr_dev_var] = def_dev_val; curr_dev_val = def_dev_val
            if curr_dev_val != UNASSIGNED_DEVICE_ID:
                if curr_dev_val in assigned: globals()[curr_dev_var] = def_dev_val
                else: assigned[curr_dev_val] = i
        elif curr_dev_val.startswith("keyboard_") and curr_dev_val != UNASSIGNED_DEVICE_ID:
            if curr_dev_val in assigned: print(f"Config Warn: P{i} & P{assigned[curr_dev_val]} same keyboard '{curr_dev_val}'.") # No auto-revert for kbd
            else: assigned[curr_dev_val] = i
    update_player_mappings_from_config()
    for i in range(1, 5): print(f"Config Loaded Final: P{i} Dev='{globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}', KbdEn={globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'P{i}_CONTROLLER_ENABLED')}")
    return True

def update_player_mappings_from_config():
    global LOADED_PYGAME_JOYSTICK_MAPPINGS
    default_runtime_joy_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy()
    print("\n--- CONFIG: Updating Player Mappings (Runtime) ---")
    available_joys = get_available_joystick_names_with_indices_and_guids()

    for i in range(1, 5):
        p_id_str = f"P{i}"; curr_dev_key = f"CURRENT_{p_id_str}_INPUT_DEVICE"; p_map_key = f"{p_id_str}_MAPPINGS"
        curr_input_dev = globals().get(curr_dev_key, UNASSIGNED_DEVICE_ID)
        print(f"  {p_id_str}: Current Device = '{curr_input_dev}'")
        target_runtime_map = {} # Default to empty

        if curr_input_dev == "keyboard_p1": target_runtime_map = DEFAULT_KEYBOARD_P1_MAPPINGS.copy(); print(f"  {p_id_str}: Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        elif curr_input_dev == "keyboard_p2": target_runtime_map = DEFAULT_KEYBOARD_P2_MAPPINGS.copy(); print(f"  {p_id_str}: Using DEFAULT_KEYBOARD_P2_MAPPINGS.")
        elif curr_input_dev and curr_input_dev.startswith("joystick_pygame_"):
            target_guid = None; joy_idx = -1
            try:
                joy_idx = int(curr_input_dev.split('_')[-1])
                for _, _, guid, idx_func in available_joys:
                    if idx_func == joy_idx: target_guid = guid; break
                if target_guid and target_guid in LOADED_PYGAME_JOYSTICK_MAPPINGS:
                    gui_map = LOADED_PYGAME_JOYSTICK_MAPPINGS[target_guid]
                    print(f"  {p_id_str}: Found GUI map for GUID '{target_guid}'. Translating...")
                    # print(f"  {p_id_str}: GUI map for translation: {json.dumps(gui_map, indent=2)}") # DEBUG
                    rt_map = _translate_gui_map_to_runtime(gui_map)
                    if rt_map: target_runtime_map = rt_map; print(f"  {p_id_str}: Translated mappings for GUID '{target_guid}'.")
                    else: target_runtime_map = default_runtime_joy_map; print(f"  {p_id_str}: Translation FAILED for GUID '{target_guid}'. Using default generic map.")
                else: target_runtime_map = default_runtime_joy_map; print(f"  {p_id_str}: No specific map for GUID '{target_guid}' (or GUID not found for index {joy_idx}). Using default generic map.")
            except Exception as e: target_runtime_map = default_runtime_joy_map; print(f"  {p_id_str} Error processing joystick map for '{curr_input_dev}': {e}. Using default generic map.")
        elif curr_input_dev == UNASSIGNED_DEVICE_ID or curr_input_dev == "unassigned_keyboard": print(f"  {p_id_str}: Device '{curr_input_dev}'. No mappings.")
        else: target_runtime_map = DEFAULT_KEYBOARD_P1_MAPPINGS.copy(); print(f"  {p_id_str}: Device '{curr_input_dev}' fallback. Using DEFAULT_KEYBOARD_P1_MAPPINGS.")
        
        globals()[p_map_key] = target_runtime_map
        print(f"  {p_id_str}: Final Runtime Mappings (jump): {target_runtime_map.get('jump', 'N/A')}, (attack1): {target_runtime_map.get('attack1', 'N/A')}")
    print("--- CONFIG: Finished Updating Player Mappings ---\n")

if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit(); _pygame_initialized_globally = False; _joystick_initialized_globally = False
    init_pygame_and_joystick_globally(force_rescan=True)
    print("\nTesting get_available_joystick_names_with_indices_and_guids():")
    joy_data = get_available_joystick_names_with_indices_and_guids()
    if joy_data: [print(f"  Joy {i}: Name='{d[0]}', ID='{d[1]}', GUID='{d[2]}', PyIdx={d[3]}") for i,d in enumerate(joy_data)]
    else: print("  No joysticks detected.")
    print("\n--- Simulating load_config() ---"); load_config()
    print(f"\n--- After test load_config(): ---")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i in range(1, 3): # P1 & P2
        print(f"  P{i} Dev: {globals().get(f'CURRENT_P{i}_INPUT_DEVICE')}, KbdEn: {globals().get(f'P{i}_KEYBOARD_ENABLED')}, CtrlEn: {globals().get(f'P{i}_CONTROLLER_ENABLED')}")
        maps = globals().get(f'P{i}_MAPPINGS',{})
        print(f"  P{i} Maps (jump): {maps.get('jump', 'N/A')}, (attack1): {maps.get('attack1', 'N/A')}, (left): {maps.get('left', 'N/A')}")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
    print("\n--- config.py direct test finished ---")