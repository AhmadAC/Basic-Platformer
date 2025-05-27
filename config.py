# config.py
# -*- coding: utf-8 -*-
###############################
"""
Configuration for game settings, primarily controls.
Handles Pygame joystick detection and assignment.
The controller_settings/controller_mappings.json is used for Pygame control mappings
and selected input devices/enabled flags for P1-P4.
MODIFIED: Ensured KbdEn/CtrlEn flags are correctly set if a device assignment
          is reverted to keyboard due to missing controller or conflict.
MODIFIED: More robust auto-assignment if config file is missing/new.
MODIFIED: Force KbdEn=True/CtrlEn=False (and vice-versa) if device type changes during load_config
          due to unavailability or conflict resolution.
"""
# version 2.3.9 (Stricter KbdEn/CtrlEn enforcement on device changes)
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
        try:
            pygame.init()
            _pygame_initialized_globally = True
            print("Config: Pygame globally initialized.")
        except Exception as e:
            print(f"Config CRITICAL: Pygame global init failed: {e}")
            return

    if not _joystick_initialized_globally or force_rescan:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try:
            pygame.joystick.init()
            _joystick_initialized_globally = True
            print("Config: Pygame Joystick globally initialized (or re-initialized).")
        except Exception as e:
            print(f"Config CRITICAL: Pygame Joystick global init failed: {e}")
            _joystick_initialized_globally = False
            return

    current_count = pygame.joystick.get_count() if _joystick_initialized_globally else 0
    
    if force_rescan or current_count != _detected_joystick_count_global or \
       (force_rescan and not _joystick_objects_global and current_count > 0) or \
       (not _joystick_objects_global and current_count > 0): # Also rescan if list is empty but joysticks detected
        
        print(f"Config: Rescanning joysticks. Prev count: {_detected_joystick_count_global}, Current: {current_count}, Force: {force_rescan}")
        _detected_joystick_count_global = current_count
        
        for old_joy in _joystick_objects_global:
            if old_joy and old_joy.get_init(): 
                try: old_joy.quit()
                except pygame.error: pass 
        _joystick_objects_global = [] 
        _detected_joystick_names_global = []

        for i in range(_detected_joystick_count_global):
            try:
                joy = pygame.joystick.Joystick(i)
                _detected_joystick_names_global.append(joy.get_name())
                _joystick_objects_global.append(joy)
            except pygame.error as e:
                print(f"Config Warn: Error accessing joystick {i}: {e}")
                _detected_joystick_names_global.append(f"ErrorJoystick{i}")
                _joystick_objects_global.append(None)
        print(f"Config: Joystick rescan complete. Found: {_detected_joystick_count_global}, Names: {_detected_joystick_names_global}")

# Call init at module load to ensure joystick list is populated at least once.
init_pygame_and_joystick_globally() 

# --- File Paths ---
CONTROLLER_SETTINGS_SUBDIR = "controller_settings"
MAPPINGS_AND_DEVICE_CHOICES_FILENAME = "controller_mappings.json"
_CONFIG_PY_DIR = os.path.dirname(os.path.abspath(__file__)) 
MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(_CONFIG_PY_DIR, CONTROLLER_SETTINGS_SUBDIR, MAPPINGS_AND_DEVICE_CHOICES_FILENAME)

# --- Device IDs and Defaults ---
UNASSIGNED_DEVICE_ID = "unassigned"
UNASSIGNED_DEVICE_NAME = "Unassigned"

DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = False
DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = True; DEFAULT_P2_CONTROLLER_ENABLED = False
DEFAULT_P3_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
DEFAULT_P4_INPUT_DEVICE = UNASSIGNED_DEVICE_ID; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False

# --- Current Player Settings (will be loaded/saved) ---
CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED

KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", UNASSIGNED_DEVICE_ID] 
KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (Unassigned)"] 

AXIS_THRESHOLD_DEFAULT = 0.7
GAME_ACTIONS = [
    "left", "right", "up", "down", "jump", "crouch",
    "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset",
    "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"
]
EXTERNAL_TO_INTERNAL_ACTION_MAP = {
    "MOVE_UP": "up", "MOVE_LEFT": "left", "MOVE_DOWN": "down", "MOVE_RIGHT": "right",
    "JUMP_ACTION": "jump", "PRIMARY_ATTACK": "attack1",
    "W": "up", "A": "left", "S": "down", "D": "right", "V": "attack1", "B": "attack2", "SHIFT": "dash"
}

DEFAULT_KEYBOARD_P1_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_A, "right": Qt.Key.Key_D, "up": Qt.Key.Key_W, "down": Qt.Key.Key_S,
    "jump": Qt.Key.Key_W, "crouch": Qt.Key.Key_S, "attack1": Qt.Key.Key_V, "attack2": Qt.Key.Key_B,
    "dash": Qt.Key.Key_Shift, "roll": Qt.Key.Key_Control, "interact": Qt.Key.Key_E,
    "projectile1": Qt.Key.Key_1, "projectile2": Qt.Key.Key_2, "projectile3": Qt.Key.Key_3, "projectile4": Qt.Key.Key_4,
    "projectile5": Qt.Key.Key_5, "projectile6": Qt.Key.Key_6, "projectile7": Qt.Key.Key_7,
    "reset": Qt.Key.Key_Q, "pause": Qt.Key.Key_Escape,
    "menu_confirm": Qt.Key.Key_Return, "menu_cancel": Qt.Key.Key_Escape,
    "menu_up": Qt.Key.Key_Up, "menu_down": Qt.Key.Key_Down, "menu_left": Qt.Key.Key_Left, "menu_right": Qt.Key.Key_Right
}
DEFAULT_KEYBOARD_P2_MAPPINGS: Dict[str, Qt.Key] = {
    "left": Qt.Key.Key_J, "right": Qt.Key.Key_L, "up": Qt.Key.Key_I, "down": Qt.Key.Key_K,
    "jump": Qt.Key.Key_I, "crouch": Qt.Key.Key_K, "attack1": Qt.Key.Key_O, "attack2": Qt.Key.Key_P,
    "dash": Qt.Key.Key_Semicolon, "roll": Qt.Key.Key_Apostrophe, "interact": Qt.Key.Key_Backslash,
    "projectile1": Qt.Key.Key_8, "projectile2": Qt.Key.Key_9, "projectile3": Qt.Key.Key_0, "projectile4": Qt.Key.Key_Minus,
    "projectile5": Qt.Key.Key_Equal, "projectile6": Qt.Key.Key_BracketLeft, "projectile7": Qt.Key.Key_BracketRight,
    "reset": Qt.Key.Key_Period, "pause": Qt.Key.Key_F12,
    "menu_confirm": Qt.Key.Key_Enter, "menu_cancel": Qt.Key.Key_Delete,
    "menu_up": Qt.Key.Key_PageUp, "menu_down": Qt.Key.Key_PageDown, "menu_left": Qt.Key.Key_Home, "menu_right": Qt.Key.Key_End
}
DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {
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
    "interact": {"type": "button", "id": 10}, 
    "projectile1": {"type": "hat", "id": 0, "value": (0, 1)}, 
    "projectile2": {"type": "hat", "id": 0, "value": (1, 0)}, 
    "projectile3": {"type": "hat", "id": 0, "value": (0, -1)}, 
    "projectile4": {"type": "hat", "id": 0, "value": (-1, 0)}, 
    "reset": {"type": "button", "id": 6}, 
    "pause": {"type": "button", "id": 7}, 
    "menu_confirm": {"type": "button", "id": 0},
    "menu_cancel": {"type": "button", "id": 1},
    "menu_up": {"type": "hat", "id": 0, "value": (0, 1)}, 
    "menu_down": {"type": "hat", "id": 0, "value": (0, -1)}, 
    "menu_left": {"type": "hat", "id": 0, "value": (-1, 0)}, 
    "menu_right": {"type": "hat", "id": 0, "value": (1, 0)} 
}

LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}
P1_MAPPINGS: Dict[str, Any] = {}; P2_MAPPINGS: Dict[str, Any] = {}
P3_MAPPINGS: Dict[str, Any] = {}; P4_MAPPINGS: Dict[str, Any] = {}

def _translate_gui_map_to_runtime(gui_map_for_single_controller: Dict[str, Any]) -> Dict[str, Any]:
    runtime_mappings: Dict[str, Any] = {}
    if not isinstance(gui_map_for_single_controller, dict): return {}
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
                    runtime_entry["id"] = int(axis_id); runtime_entry["value"] = int(direction); runtime_entry["threshold"] = float(threshold); valid_entry = True
            elif event_type == "hat":
                hat_id = details.get("hat_id"); value = details.get("value") 
                if hat_id is not None and isinstance(value, list) and len(value) == 2:
                    runtime_entry["id"] = int(hat_id); runtime_entry["value"] = tuple(map(int, value)); valid_entry = True
        except (ValueError, TypeError) as e: print(f"Config Error (_translate): Invalid data for action '{action_name}', type '{event_type}': {details} - Error: {e}")
        if valid_entry: runtime_mappings[action_name] = runtime_entry
    return runtime_mappings

_translate_and_validate_gui_json_to_pygame_mappings = _translate_gui_map_to_runtime

def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]:
    devices: List[Tuple[str, str, Optional[str], int]] = []
    if not _joystick_initialized_globally:
        print("Config Warn: get_available_joystick_names_with_indices_and_guids called but joystick system not init.")
        return devices
    for i in range(_detected_joystick_count_global):
        joy_obj = _joystick_objects_global[i] if i < len(_joystick_objects_global) else None
        joy_name = _detected_joystick_names_global[i] if i < len(_detected_joystick_names_global) else f"UnknownJoystick{i}"
        guid_str: Optional[str] = None
        if joy_obj: 
            was_originally_init = joy_obj.get_init()
            try:
                if not was_originally_init: joy_obj.init() 
                guid_str = joy_obj.get_guid()
            except pygame.error as e_guid: print(f"Config Warn: Error getting GUID for joystick {i} ('{joy_name}'): {e_guid}")
            finally:
                if not was_originally_init and joy_obj.get_init(): 
                    try: joy_obj.quit() 
                    except pygame.error: pass 
        else: print(f"Config Warn: No joystick object at index {i} in _joystick_objects_global while expected.")
        internal_id_for_assignment = f"joystick_pygame_{i}"; display_name = f"Joy {i}: {joy_name.split(' (GUID:')[0]}" 
        devices.append((display_name, internal_id_for_assignment, guid_str, i))
    return devices

def get_joystick_objects() -> List[Optional[pygame.joystick.Joystick]]: return _joystick_objects_global

def save_config() -> bool:
    player_settings: Dict[str, Any] = {}
    for i in range(1, 5): 
        player_num_str = f"P{i}"
        player_settings[f"player{i}_settings"] = {
            "input_device": globals().get(f"CURRENT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID),
            "keyboard_enabled": globals().get(f"{player_num_str}_KEYBOARD_ENABLED", False),
            "controller_enabled": globals().get(f"{player_num_str}_CONTROLLER_ENABLED", False)
        }
    data_to_save = {"config_version": "2.3.9", **player_settings, "joystick_mappings": LOADED_PYGAME_JOYSTICK_MAPPINGS}
    try:
        settings_subdir = os.path.dirname(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH)
        if not os.path.exists(settings_subdir): os.makedirs(settings_subdir); print(f"Config: Created directory {settings_subdir}")
        with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'w') as f: json.dump(data_to_save, f, indent=4)
        print(f"Config: Settings saved to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        # update_player_mappings_from_config() # Called by UI or after load_config
        return True
    except IOError as e: print(f"Config Error: Could not save settings to {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}"); return False

def load_config() -> bool:
    global LOADED_PYGAME_JOYSTICK_MAPPINGS, CURRENT_P1_INPUT_DEVICE, P1_KEYBOARD_ENABLED, P1_CONTROLLER_ENABLED
    global CURRENT_P2_INPUT_DEVICE, P2_KEYBOARD_ENABLED, P2_CONTROLLER_ENABLED
    global CURRENT_P3_INPUT_DEVICE, P3_KEYBOARD_ENABLED, P3_CONTROLLER_ENABLED
    global CURRENT_P4_INPUT_DEVICE, P4_KEYBOARD_ENABLED, P4_CONTROLLER_ENABLED
    
    init_pygame_and_joystick_globally(force_rescan=True) 
    
    raw_data_from_file: Dict[str, Any] = {}
    if os.path.exists(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH):
        try:
            with open(MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH, 'r') as f: raw_data_from_file = json.load(f)
            print(f"Config: Loaded settings from {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Config Error: Failed to load or parse {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH}: {e}. Using defaults.")
            raw_data_from_file = {} 
    else:
        print(f"Config: File {MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH} not found. Using defaults and auto-assignment.")
        raw_data_from_file = {} 

    # --- Initial load or auto-assignment of player device settings ---
    if not raw_data_from_file.get("player1_settings"): # If file is new or player settings section is missing
        print("Config: No player settings in JSON. Performing auto-assignment for P1-P4.")
        auto_assignments = {
            "P1": {"device": DEFAULT_P1_INPUT_DEVICE, "kbd_en": DEFAULT_P1_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P1_CONTROLLER_ENABLED},
            "P2": {"device": DEFAULT_P2_INPUT_DEVICE, "kbd_en": DEFAULT_P2_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P2_CONTROLLER_ENABLED},
            "P3": {"device": DEFAULT_P3_INPUT_DEVICE, "kbd_en": DEFAULT_P3_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P3_CONTROLLER_ENABLED},
            "P4": {"device": DEFAULT_P4_INPUT_DEVICE, "kbd_en": DEFAULT_P4_KEYBOARD_ENABLED, "ctrl_en": DEFAULT_P4_CONTROLLER_ENABLED}
        }
        available_joy_indices = list(range(_detected_joystick_count_global))
        used_keyboard_layouts = set()

        # Priority 1: Assign controllers if available
        for p_idx_plus_1 in range(1, 5): 
            player_num_str = f"P{p_idx_plus_1}"
            if available_joy_indices:
                assigned_joy_idx = available_joy_indices.pop(0) 
                auto_assignments[player_num_str]["device"] = f"joystick_pygame_{assigned_joy_idx}"
                auto_assignments[player_num_str]["ctrl_en"] = True; auto_assignments[player_num_str]["kbd_en"] = False
        
        # Priority 2: Assign keyboards if no controller was assigned
        for p_idx_plus_1 in range(1, 5):
            player_num_str = f"P{p_idx_plus_1}"
            # Only assign keyboard if no controller was assigned and it's P1 or P2 (who have default kbd layouts)
            if auto_assignments[player_num_str]["device"] == UNASSIGNED_DEVICE_ID or \
               auto_assignments[player_num_str]["device"].startswith("keyboard_") : # If its default was already keyboard
                
                target_kbd_layout = globals().get(f"DEFAULT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
                if target_kbd_layout.startswith("keyboard_") and target_kbd_layout not in used_keyboard_layouts:
                    auto_assignments[player_num_str]["device"] = target_kbd_layout
                    auto_assignments[player_num_str]["kbd_en"] = True; auto_assignments[player_num_str]["ctrl_en"] = False
                    used_keyboard_layouts.add(target_kbd_layout)
                # If P1's default kbd_p1 is free, use it (even for P2 if P2's specific is taken)
                elif DEFAULT_P1_INPUT_DEVICE not in used_keyboard_layouts and player_num_str in ["P1","P2"]:
                    auto_assignments[player_num_str]["device"] = DEFAULT_P1_INPUT_DEVICE
                    auto_assignments[player_num_str]["kbd_en"] = True; auto_assignments[player_num_str]["ctrl_en"] = False
                    used_keyboard_layouts.add(DEFAULT_P1_INPUT_DEVICE)
                # If P2's default kbd_p2 is free, use it (even for P1 if P1's specific is taken)
                elif DEFAULT_P2_INPUT_DEVICE not in used_keyboard_layouts and player_num_str in ["P1","P2"]:
                    auto_assignments[player_num_str]["device"] = DEFAULT_P2_INPUT_DEVICE
                    auto_assignments[player_num_str]["kbd_en"] = True; auto_assignments[player_num_str]["ctrl_en"] = False
                    used_keyboard_layouts.add(DEFAULT_P2_INPUT_DEVICE)
                else: # If specific layouts taken, or for P3/P4 with no controllers, default to unassigned
                    if player_num_str not in ["P1","P2"]: # P3/P4 default to unassigned if no controller
                        auto_assignments[player_num_str]["device"] = UNASSIGNED_DEVICE_ID
                        auto_assignments[player_num_str]["kbd_en"] = False; auto_assignments[player_num_str]["ctrl_en"] = False
        
        for i in range(1, 5):
            player_num_str = f"P{i}"
            globals()[f"CURRENT_{player_num_str}_INPUT_DEVICE"] = auto_assignments[player_num_str]["device"]
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = auto_assignments[player_num_str]["kbd_en"]
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = auto_assignments[player_num_str]["ctrl_en"]
    else: # Load from file
        for i in range(1, 5): 
            player_num_str = f"P{i}"
            player_settings_from_file = raw_data_from_file.get(f"player{i}_settings", {})
            default_dev = globals().get(f"DEFAULT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
            default_kbd_en = globals().get(f"DEFAULT_{player_num_str}_KEYBOARD_ENABLED", False)
            default_ctrl_en = globals().get(f"DEFAULT_{player_num_str}_CONTROLLER_ENABLED", False)

            loaded_device = player_settings_from_file.get("input_device", default_dev)
            loaded_kbd_en = player_settings_from_file.get("keyboard_enabled", default_kbd_en)
            loaded_ctrl_en = player_settings_from_file.get("controller_enabled", default_ctrl_en)
            
            globals()[f"CURRENT_{player_num_str}_INPUT_DEVICE"] = loaded_device
            globals()[f"{player_num_str}_KEYBOARD_ENABLED"] = loaded_kbd_en
            globals()[f"{player_num_str}_CONTROLLER_ENABLED"] = loaded_ctrl_en


    # --- Validate and Correct device assignments and enabled flags ---
    available_pygame_joy_device_ids = [f"joystick_pygame_{j}" for j in range(_detected_joystick_count_global)]
    assigned_pygame_joystick_indices: Dict[int, str] = {} # Tracks which pygame_idx is assigned to which P_str

    for i in range(1, 5):
        player_num_str = f"P{i}"
        current_device_for_player_var_name = f"CURRENT_{player_num_str}_INPUT_DEVICE"
        kbd_enabled_var_name = f"{player_num_str}_KEYBOARD_ENABLED"
        ctrl_enabled_var_name = f"{player_num_str}_CONTROLLER_ENABLED"
        default_device_for_player_val = globals().get(f"DEFAULT_{player_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)

        current_assigned_device_value = globals()[current_device_for_player_var_name]
        
        if current_assigned_device_value.startswith("keyboard_"):
            globals()[kbd_enabled_var_name] = True
            globals()[ctrl_enabled_var_name] = False
        elif current_assigned_device_value.startswith("joystick_pygame_"):
            try:
                joy_idx_part = current_assigned_device_value.split('_')[-1]
                if joy_idx_part.isdigit():
                    py_idx = int(joy_idx_part)
                    if current_assigned_device_value in available_pygame_joy_device_ids:
                        if py_idx in assigned_pygame_joystick_indices: # Conflict with another player
                            conflicting_player = assigned_pygame_joystick_indices[py_idx]
                            print(f"Config Conflict: {player_num_str} joystick '{current_assigned_device_value}' already assigned to {conflicting_player}. Reverting {player_num_str} to default '{default_device_for_player_val}'.")
                            globals()[current_device_for_player_var_name] = default_device_for_player_val
                            if default_device_for_player_val.startswith("keyboard_"):
                                globals()[kbd_enabled_var_name] = True; globals()[ctrl_enabled_var_name] = False
                            else: # default is unassigned or another joystick
                                globals()[kbd_enabled_var_name] = False; globals()[ctrl_enabled_var_name] = (default_device_for_player_val != UNASSIGNED_DEVICE_ID)
                        else: # No conflict, assign it
                            assigned_pygame_joystick_indices[py_idx] = player_num_str
                            globals()[kbd_enabled_var_name] = False
                            globals()[ctrl_enabled_var_name] = True
                    else: # Joystick not detected
                        print(f"Config Warn: {player_num_str}'s assigned joystick '{current_assigned_device_value}' not detected. Reverting to default '{default_device_for_player_val}'.")
                        globals()[current_device_for_player_var_name] = default_device_for_player_val
                        if default_device_for_player_val.startswith("keyboard_"):
                            globals()[kbd_enabled_var_name] = True; globals()[ctrl_enabled_var_name] = False
                        else:
                            globals()[kbd_enabled_var_name] = False; globals()[ctrl_enabled_var_name] = (default_device_for_player_val != UNASSIGNED_DEVICE_ID)
                else: # Malformed ID
                     raise ValueError("Malformed joystick ID suffix")
            except (ValueError, IndexError) as e_joy_id: # Catch malformed ID or split error
                print(f"Config Error: Error processing joystick ID '{current_assigned_device_value}' for {player_num_str}: {e_joy_id}. Reverting to default.")
                globals()[current_device_for_player_var_name] = default_device_for_player_val
                if default_device_for_player_val.startswith("keyboard_"):
                    globals()[kbd_enabled_var_name] = True; globals()[ctrl_enabled_var_name] = False
                else:
                    globals()[kbd_enabled_var_name] = False; globals()[ctrl_enabled_var_name] = (default_device_for_player_val != UNASSIGNED_DEVICE_ID)
        
        elif current_assigned_device_value == UNASSIGNED_DEVICE_ID:
            globals()[kbd_enabled_var_name] = False
            globals()[ctrl_enabled_var_name] = False
        else: # Unknown device string, treat as unassigned for safety
            print(f"Config Warn: {player_num_str} has unknown device '{current_assigned_device_value}'. Treating as unassigned.")
            globals()[current_device_for_player_var_name] = UNASSIGNED_DEVICE_ID
            globals()[kbd_enabled_var_name] = False
            globals()[ctrl_enabled_var_name] = False
            
    LOADED_PYGAME_JOYSTICK_MAPPINGS = raw_data_from_file.get("joystick_mappings", {})
    update_player_mappings_from_config()
    
    for i in range(1, 5):
        player_num_str = f"P{i}"
        print(f"Config Loaded Final (after all checks): {player_num_str} Dev='{globals().get(f'CURRENT_{player_num_str}_INPUT_DEVICE')}', "
              f"KbdEn={globals().get(f'{player_num_str}_KEYBOARD_ENABLED')}, CtrlEn={globals().get(f'{player_num_str}_CONTROLLER_ENABLED')}")
    return True

def update_player_mappings_from_config():
    global P1_MAPPINGS, P2_MAPPINGS, P3_MAPPINGS, P4_MAPPINGS, LOADED_PYGAME_JOYSTICK_MAPPINGS
    default_runtime_joystick_map = DEFAULT_GENERIC_JOYSTICK_MAPPINGS.copy()
    available_joys_data = get_available_joystick_names_with_indices_and_guids() 

    for i in range(1, 5): 
        player_id_str = f"P{i}"
        current_input_device_for_player = globals().get(f"CURRENT_{player_id_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
        player_mappings_var_name = f"{player_id_str}_MAPPINGS"; target_runtime_map_for_player: Dict[str, Any] = {} 
        if current_input_device_for_player == "keyboard_p1": target_runtime_map_for_player = DEFAULT_KEYBOARD_P1_MAPPINGS.copy()
        elif current_input_device_for_player == "keyboard_p2": target_runtime_map_for_player = DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
        elif current_input_device_for_player and current_input_device_for_player.startswith("joystick_pygame_"):
            assigned_pygame_idx_str = current_input_device_for_player.split('_')[-1]
            target_guid_for_player: Optional[str] = None; assigned_pygame_idx: Optional[int] = None
            try:
                assigned_pygame_idx = int(assigned_pygame_idx_str)
                for _, _, guid, py_idx in available_joys_data:
                    if py_idx == assigned_pygame_idx: target_guid_for_player = guid; break
            except (ValueError, IndexError): print(f"  {player_id_str} Error: Could not parse Pygame index from '{current_input_device_for_player}' for map update.")
            if target_guid_for_player and target_guid_for_player in LOADED_PYGAME_JOYSTICK_MAPPINGS:
                gui_format_map_for_guid = LOADED_PYGAME_JOYSTICK_MAPPINGS[target_guid_for_player]
                runtime_map_translated = _translate_gui_map_to_runtime(gui_format_map_for_guid)
                if runtime_map_translated: target_runtime_map_for_player = runtime_map_translated
                else: target_runtime_map_for_player = default_runtime_joystick_map.copy(); print(f"  {player_id_str}: Translation FAILED for GUID '{target_guid_for_player}'. Using default generic joystick map.")
            else:
                target_runtime_map_for_player = default_runtime_joystick_map.copy()
                no_map_reason = f"No specific map found for GUID '{target_guid_for_player}'" if target_guid_for_player else (f"No GUID found for Pygame index {assigned_pygame_idx}" if assigned_pygame_idx is not None else "Invalid joystick assignment")
                print(f"  {player_id_str}: {no_map_reason}. Using default generic joystick map for runtime.")
        elif current_input_device_for_player == UNASSIGNED_DEVICE_ID: target_runtime_map_for_player = {} 
        else: target_runtime_map_for_player = {}; print(f"  {player_id_str}: Device '{current_input_device_for_player}' is unrecognized. Assigning empty map.")
        globals()[player_mappings_var_name] = target_runtime_map_for_player
    
if __name__ != "__main__": load_config()

if __name__ == "__main__":
    print("--- Running config.py directly for testing ---")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try: pygame.quit()
        except pygame.error: pass
        _pygame_initialized_globally = False; _joystick_initialized_globally = False
        print("  (Standalone Test: Pygame system reset for fresh init by config.py itself)")
    load_config() 
    print(f"\n--- After test load_config(): ---")
    print(f"  Detected Joysticks ({_detected_joystick_count_global}): {_detected_joystick_names_global}")
    for i in range(1, 5): 
        player_num_str = f"P{i}"
        print(f"  {player_num_str} Dev: {globals().get(f'CURRENT_{player_num_str}_INPUT_DEVICE')}, KbdEn: {globals().get(f'{player_num_str}_KEYBOARD_ENABLED')}, CtrlEn: {globals().get(f'{player_num_str}_CONTROLLER_ENABLED')}")
        current_player_mappings = globals().get(f'{player_num_str}_MAPPINGS', {})
        jump_map_info = current_player_mappings.get('jump', 'N/A'); attack_map_info = current_player_mappings.get('attack1', 'N/A')
        left_map_info = current_player_mappings.get('left', 'N/A'); interact_map_info = current_player_mappings.get('interact', 'N/A')
        print(f"  {player_num_str} Runtime Maps -> Jump: {jump_map_info}, Attack1: {attack_map_info}, Left: {left_map_info}, Interact: {interact_map_info}")
    if _pygame_initialized_globally:
        if _joystick_initialized_globally:
            try: pygame.joystick.quit()
            except pygame.error: pass
        try: pygame.quit()
        except pygame.error: pass
        print("  (Standalone Test: Pygame quit at end of test)")
    print("\n--- config.py direct test finished ---")