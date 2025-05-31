# controller_settings/controller_mapper_gui.py
# -*- coding: utf-8 -*-
"""
## version 1.0.2 (Refactored for main_game.config decoupling and simplified fallback)
GUI for mapping game controller inputs to game actions and GUI navigation.
- Saves mappings and device choices by interacting with main_game.config.
- Simulates keyboard events using pynput if available.
- Handles Pygame joystick events for mapping and GUI control.
- GUI navigation actions are now defined locally and merged with game_config actions.
- GameConfigFallback is simplified, GUI handles its own Pygame init if fallback active.
"""
import sys
import json
import threading
import time
import logging
import os
from typing import Dict, Optional, Any, List, Tuple, cast
import copy

import pygame
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit,
    QGroupBox, QSizePolicy, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QByteArray, QTimer
from PySide6.QtGui import QKeyEvent,QCloseEvent

try:
    from pynput.keyboard import Controller as KeyboardController, Key # type: ignore
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("WARNING in controller_mapper_gui.py: pynput.keyboard not found. Keyboard simulation will not work.")
    class Key: # type: ignore
        shift = 'stub_shift'; ctrl = 'stub_ctrl'; alt = 'stub_alt'
        enter = 'stub_enter'; tab = 'stub_tab'; esc = 'stub_esc'
        up = 'stub_up'; down = 'stub_down'; left = 'stub_left'; right = 'stub_right'
    class KeyboardController: # type: ignore
        def press(self, key: Any): pass
        def release(self, key: Any): pass
        def __enter__(self): return self
        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any): pass

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"ControllerMapperGUI (Standalone): Added '{parent_dir}' to sys.path to find 'main_game'.")

# --- GUI Navigation Actions (defined locally for this module) ---
GUI_NAV_UP = "gui_nav_up"
GUI_NAV_DOWN = "gui_nav_down"
GUI_NAV_LEFT = "gui_nav_left"
GUI_NAV_RIGHT = "gui_nav_right"
GUI_NAV_CONFIRM = "gui_nav_confirm"
GUI_NAV_CANCEL = "gui_nav_cancel"
GUI_NAV_TAB_NEXT = "gui_nav_tab_next" # Added for consistency if used
GUI_NAV_TAB_PREV = "gui_nav_tab_prev" # Added for consistency if used

GUI_NAV_ACTIONS_INTERNAL_KEYS: List[str] = [
    GUI_NAV_UP, GUI_NAV_DOWN, GUI_NAV_LEFT, GUI_NAV_RIGHT,
    GUI_NAV_CONFIRM, GUI_NAV_CANCEL, GUI_NAV_TAB_NEXT, GUI_NAV_TAB_PREV
]
GUI_NAV_ACTIONS_FRIENDLY_NAMES: Dict[str, str] = {
    GUI_NAV_UP: "GUI Up", GUI_NAV_DOWN: "GUI Down", GUI_NAV_LEFT: "GUI Left",
    GUI_NAV_RIGHT: "GUI Right", GUI_NAV_CONFIRM: "GUI Confirm/Activate", GUI_NAV_CANCEL: "GUI Cancel/Back",
    GUI_NAV_TAB_NEXT: "GUI Tab Next", GUI_NAV_TAB_PREV: "GUI Tab Prev"
}

# Attempt to import the real game_config
GAME_CONFIG_MODULE_AVAILABLE = False
game_config_module_error_message = ""
try:
    import main_game.config as game_config
    GAME_CONFIG_MODULE_AVAILABLE = True
    print("Successfully imported 'main_game.config as game_config'")
except ImportError as e_import_config:
    game_config_module_error_message = str(e_import_config)
    print(f"CRITICAL ERROR in controller_mapper_gui.py: Could not import 'main_game.config'. Error: {e_import_config}. Using GameConfigFallback.")
    class GameConfigFallback: # Simplified Fallback
        GAME_ACTIONS = ["jump", "attack1", "left", "right", "up", "down", "menu_confirm", "menu_cancel", "pause"] # Base game actions
        EXTERNAL_TO_INTERNAL_ACTION_MAP = {
            "JUMP": "jump", "ATTACK": "attack1", "LEFT": "left", "RIGHT": "right", "UP": "up", "DOWN": "down",
            "CONFIRM": "menu_confirm", "CANCEL": "menu_cancel", "PAUSE": "pause",
        }
        AXIS_THRESHOLD_DEFAULT = 0.7
        MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controller_mappings_fallback.json") # Path only
        KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
        KEYBOARD_DEVICE_NAMES = ["Keyboard (P1)", "Keyboard (P2)", "Keyboard (Unassigned)"]
        UNASSIGNED_DEVICE_ID = "unassigned"; UNASSIGNED_DEVICE_NAME = "Unassigned"
        DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = { # Runtime format for fallback
            "jump": {"type": "button", "id": 0}, "attack1": {"type": "button", "id": 1},
            "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1},
            "pause": {"type": "button", "id": 9},
            "left": {"type": "hat", "id": 0, "value": (-1, 0)}, "right": {"type": "hat", "id": 0, "value": (1, 0)},
            "up": {"type": "hat", "id": 0, "value": (0, 1)}, "down": {"type": "hat", "id": 0, "value": (0, -1)},
            GUI_NAV_UP: {"type": "axis", "id": 1, "value": -1, "threshold": 0.7}, # Example for fallback GUI Nav
            GUI_NAV_DOWN: {"type": "axis", "id": 1, "value": 1, "threshold": 0.7},
            GUI_NAV_CONFIRM: {"type": "button", "id": 0},
        }
        LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {} # GUID -> {action: gui_storage_map_entry}
        # Player device choices - fallback will reflect its own limited knowledge
        CURRENT_P1_INPUT_DEVICE = "keyboard_p1"; P1_KEYBOARD_ENABLED = True; P1_CONTROLLER_ENABLED = False
        CURRENT_P2_INPUT_DEVICE = "unassigned"; P2_KEYBOARD_ENABLED = False; P2_CONTROLLER_ENABLED = False
        CURRENT_P3_INPUT_DEVICE = "unassigned"; P3_KEYBOARD_ENABLED = False; P3_CONTROLLER_ENABLED = False
        CURRENT_P4_INPUT_DEVICE = "unassigned"; P4_KEYBOARD_ENABLED = False; P4_CONTROLLER_ENABLED = False
        DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P2_INPUT_DEVICE = "keyboard_p2";
        DEFAULT_P3_INPUT_DEVICE = "unassigned"; DEFAULT_P4_INPUT_DEVICE = "unassigned";

        # These methods are stubs or simplified for fallback
        @staticmethod
        def init_pygame_and_joystick_globally(force_rescan=False): print("GameConfigFallback: init_pygame_and_joystick_globally STUB called.")
        @staticmethod
        def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]: print("GameConfigFallback: get_available_joystick_names_with_indices_and_guids STUB called."); return []
        @staticmethod
        def get_joystick_objects() -> List[Any]: print("GameConfigFallback: get_joystick_objects STUB called."); return []
        @staticmethod
        def save_config(): print("GameConfigFallback: save_config STUB called. Config not saved as main_game.config is missing."); return False
        @staticmethod
        def load_config(): print("GameConfigFallback: load_config STUB called. Using fallback defaults."); return False
        @staticmethod
        def update_player_mappings_from_config(): print("GameConfigFallback: update_player_mappings_from_config STUB called.")
        
        @staticmethod
        def _translate_and_validate_gui_json_to_pygame_mappings(raw_gui_json_joystick_mappings: Dict[str, Any]) -> Dict[str, Any]:
            translated_mappings: Dict[str, Any] = {}
            if not isinstance(raw_gui_json_joystick_mappings, dict): return {}
            for action_key, mapping_info in raw_gui_json_joystick_mappings.items():
                if not isinstance(mapping_info, dict): continue
                details = mapping_info.get("details"); event_type = mapping_info.get("event_type")
                if not details or not event_type: continue
                runtime_map_entry: Dict[str, Any] = {"type": event_type}
                if event_type == "button": runtime_map_entry["id"] = details.get("button_id")
                elif event_type == "axis":
                    runtime_map_entry["id"] = details.get("axis_id"); runtime_map_entry["value"] = details.get("direction")
                    runtime_map_entry["threshold"] = details.get("threshold", GameConfigFallback.AXIS_THRESHOLD_DEFAULT)
                elif event_type == "hat":
                    runtime_map_entry["id"] = details.get("hat_id"); runtime_map_entry["value"] = tuple(details.get("value", (0,0)))
                else: continue
                if runtime_map_entry.get("id") is None: continue
                if event_type == "axis" and runtime_map_entry.get("value") is None: continue
                translated_mappings[action_key] = runtime_map_entry
            return translated_mappings

    game_config = GameConfigFallback() # type: ignore Assign fallback instance

# --- Logger ---
logger_cmg = logging.getLogger("CM_GUI")
if not logger_cmg.hasHandlers():
    _cmg_handler = logging.StreamHandler(sys.stdout)
    _cmg_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _cmg_handler.setFormatter(_cmg_formatter); logger_cmg.addHandler(_cmg_handler)
    logger_cmg.setLevel(logging.INFO); logger_cmg.propagate = False

# --- Construct Mappable Actions and Friendly Names for GUI ---
GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS: List[str] = []
INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI: Dict[str, str] = {}

if hasattr(game_config, 'GAME_ACTIONS') and isinstance(game_config.GAME_ACTIONS, list):
    GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS.extend(game_config.GAME_ACTIONS)
GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS.extend(key for key in GUI_NAV_ACTIONS_INTERNAL_KEYS if key not in GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS)

if hasattr(game_config, 'EXTERNAL_TO_INTERNAL_ACTION_MAP') and isinstance(game_config.EXTERNAL_TO_INTERNAL_ACTION_MAP, dict):
    for friendly, internal in game_config.EXTERNAL_TO_INTERNAL_ACTION_MAP.items():
        if internal in GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS: # Only include if it's a game action we expect
            INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI[internal] = friendly
# Add GUI nav friendly names
for internal_nav_key, friendly_nav_name in GUI_NAV_ACTIONS_FRIENDLY_NAMES.items():
    if internal_nav_key not in INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI: # Avoid overwriting if game_config already has it
        INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI[internal_nav_key] = friendly_nav_name
# Ensure all mappable keys have at least a default friendly name
for action_key_internal in GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS:
    if action_key_internal not in INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI:
        INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI[action_key_internal] = action_key_internal.replace("_", " ").title()
# --- End Mappable Actions Setup ---

# --- Other Constants based on game_config or fallbacks ---
MENU_SPECIFIC_ACTIONS_BASE = ["menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right", "pause"]
MENU_SPECIFIC_ACTIONS_GUI = MENU_SPECIFIC_ACTIONS_BASE + GUI_NAV_ACTIONS_INTERNAL_KEYS
EXCLUSIVE_ACTIONS = ["pause", "menu_cancel"] + [GUI_NAV_CANCEL] # Add GUI_NAV_CANCEL if it's exclusive
AXIS_THRESHOLD = getattr(game_config, 'AXIS_THRESHOLD_DEFAULT', 0.7)
MAPPINGS_FILE_PATH_FROM_CONFIG = getattr(game_config, 'MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH',
                                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "controller_mappings_gui_fallback.json"))
UNASSIGNED_DEVICE_ID_CONST = getattr(game_config, "UNASSIGNED_DEVICE_ID", "unassigned")
UNASSIGNED_DEVICE_NAME_CONST = getattr(game_config, "UNASSIGNED_DEVICE_NAME", "Unassigned")


# --- Helper Functions (Pynput, _convert_runtime_default_to_gui_storage) ---
def get_pynput_key(key_str: str) -> Optional[Any]:
    # ... (pynput key mapping, unchanged) ...
    if not PYNPUT_AVAILABLE: return None
    key_map = {
        "SHIFT": Key.shift, "CTRL": Key.ctrl, "ALT": Key.alt, "ENTER": Key.enter, "RETURN": Key.enter,
        "TAB": Key.tab, "ESC": Key.esc, "UP_ARROW": Key.up, "DOWN_ARROW": Key.down,
        "LEFT_ARROW": Key.left, "RIGHT_ARROW": Key.right,
        "up": 'w', "left": 'a', "down": 's', "right": 'd', "jump": 'w', "attack1": 'v',
        "pause": Key.esc, "menu_confirm": Key.enter,
        GUI_NAV_UP: Key.up, GUI_NAV_DOWN: Key.down, GUI_NAV_LEFT: Key.left, GUI_NAV_RIGHT: Key.right,
        GUI_NAV_CONFIRM: Key.enter, GUI_NAV_CANCEL: Key.esc
    }
    if key_str in key_map: return key_map[key_str]
    if len(key_str) == 1 and key_str.isalnum(): return key_str.lower()
    try:
        if key_str.lower().startswith('f') and key_str[1:].isdigit(): return getattr(Key, key_str.lower())
    except AttributeError: pass
    if key_str not in GUI_NAV_ACTIONS_INTERNAL_KEYS: logger_cmg.warning(f"Pynput key for game action '{key_str}' not found or not typically simulated.")
    return None

def _convert_runtime_default_to_gui_storage(action: str, runtime_map: Dict[str, Any], joy_idx_for_raw_str: int) -> Optional[Dict[str, Any]]:
    # ... (this function logic remains largely the same, operates on input dicts) ...
    gui_storage_map: Dict[str, Any] = {}; details: Dict[str, Any] = {}
    raw_str_parts = [f"Joy{joy_idx_for_raw_str}"]
    map_type = runtime_map.get("type"); map_id = runtime_map.get("id")
    if map_type == "button":
        gui_storage_map["event_type"] = "button"; details["button_id"] = map_id; details["type"] = "button"
        raw_str_parts.append(f"Btn {map_id}")
    elif map_type == "axis":
        gui_storage_map["event_type"] = "axis"; details["axis_id"] = map_id
        details["direction"] = runtime_map.get("value"); details["threshold"] = runtime_map.get("threshold", AXIS_THRESHOLD)
        details["type"] = "axis"
        if details["direction"] is None: logger_cmg.warning(f"Axis map for '{action}' (runtime default) missing direction."); return None
        raw_str_parts.append(f"Axis {map_id} {'Pos' if details['direction'] == 1 else 'Neg'}")
    elif map_type == "hat":
        gui_storage_map["event_type"] = "hat"; details["hat_id"] = map_id
        details["value"] = list(runtime_map.get("value", (0,0))); details["type"] = "hat"
        raw_str_parts.append(f"Hat {map_id} {tuple(details['value'])}")
    else: logger_cmg.warning(f"Unknown map type '{map_type}' for action '{action}' in runtime default."); return None
    gui_storage_map["details"] = details; gui_storage_map["raw_str"] = " ".join(raw_str_parts)
    return gui_storage_map


class PygameControllerThread(QThread):
    # ... (PygameControllerThread class remains largely the same, but its initialization check for Pygame needs care) ...
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    guiNavigationRequested = Signal(str, bool)
    controllerHotplug = Signal(str)

    def __init__(self):
        super().__init__()
        self.joystick: Optional[pygame.joystick.Joystick] = None
        self.is_listening_for_mapping = False
        self.stop_flag = threading.Event()
        self._translated_mappings_for_triggering: Dict[str, Any] = {}
        self.active_axis_keys: Dict[Tuple[int, int], str] = {}
        self.active_hat_keys: Dict[Tuple[int, Tuple[int, int]], str] = {}
        self._last_joystick_count = -1
        self.joystick_idx_to_monitor = -1
        self.joystick_instance_id_to_monitor: Optional[int] = None
        logger_cmg.debug("PygameControllerThread initialized.")

    @property
    def translated_mappings_for_triggering(self) -> Dict[str, Any]: return self._translated_mappings_for_triggering
    @translated_mappings_for_triggering.setter
    def translated_mappings_for_triggering(self, new_mappings: Dict[str, Any]):
        self._translated_mappings_for_triggering = new_mappings
        self.active_axis_keys.clear(); self.active_hat_keys.clear()

    def set_joystick_to_monitor(self, pygame_index: int):
        if self.joystick_idx_to_monitor != pygame_index:
            logger_cmg.info(f"PygameControllerThread: Target monitor index changed from {self.joystick_idx_to_monitor} to {pygame_index}")
            self.joystick_idx_to_monitor = pygame_index
            if self.joystick:
                try: self.joystick.quit()
                except pygame.error: pass
            self.joystick = None; self.joystick_instance_id_to_monitor = None
            self.active_axis_keys.clear(); self.active_hat_keys.clear()
            if pygame_index == -1: logger_cmg.info("PygameControllerThread: Monitoring disabled (index set to -1).")

    def start_listening(self): self.is_listening_for_mapping = True; logger_cmg.debug("PygameControllerThread: Started listening for mapping event.")
    def stop_listening(self): self.is_listening_for_mapping = False; logger_cmg.debug("PygameControllerThread: Stopped listening for mapping event.")
    def stop(self): self.stop_flag.set(); logger_cmg.debug("PygameControllerThread: Stop flag set.")

    def run(self):
        logger_cmg.info("PygameControllerThread started running.")
        # This check is now more critical. The GUI must ensure Pygame is ready before starting this thread.
        if not pygame.get_init() or not pygame.joystick.get_init():
            logger_cmg.error("Pygame or Joystick system not globally initialized by GUI or config! Thread cannot run reliably.")
            self.controllerHotplug.emit("Error: Pygame Joystick system not ready."); return
        # ... (rest of run method is complex but should mostly work, assuming Pygame is init'd by the GUI itself if config is fallback)
        # The core logic for event.instance_id, event types, and emitting signals is sound.
        # The key is that pygame.joystick.get_count() and Joystick(idx).init() work.

        while not self.stop_flag.is_set():
            try:
                pygame.event.pump()
                current_joystick_count = pygame.joystick.get_count()
                if self._last_joystick_count != current_joystick_count:
                    self.controllerHotplug.emit(f"Joystick count changed: {current_joystick_count}")
                    logger_cmg.info(f"Joystick count changed from {self._last_joystick_count} to {current_joystick_count}.")
                    if self.joystick:
                        try: self.joystick.quit()
                        except pygame.error: pass
                    self.joystick = None; self.joystick_instance_id_to_monitor = None
                self._last_joystick_count = current_joystick_count

                if self.joystick is None:
                    if 0 <= self.joystick_idx_to_monitor < current_joystick_count:
                        try:
                            temp_joy = pygame.joystick.Joystick(self.joystick_idx_to_monitor); temp_joy.init()
                            self.joystick = temp_joy; self.joystick_instance_id_to_monitor = self.joystick.get_instance_id()
                            name = self.joystick.get_name()
                            logger_cmg.info(f"PygameControllerThread: Monitoring '{name}' (Idx:{self.joystick_idx_to_monitor}, InstID:{self.joystick_instance_id_to_monitor}).")
                            self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} ({name}) ready for mapping/simulation.")
                        except pygame.error as e:
                            logger_cmg.error(f"Run loop: Error initializing joystick {self.joystick_idx_to_monitor}: {e}")
                            self.joystick = None; self.joystick_instance_id_to_monitor = None
                            self.controllerHotplug.emit(f"Joystick {self.joystick_idx_to_monitor} init error. Retrying...")

                if not self.joystick or not self.joystick.get_init():
                    if self.joystick and not self.joystick.get_init():
                        logger_cmg.warning(f"Monitored joystick {self.joystick_idx_to_monitor} (Instance ID: {self.joystick_instance_id_to_monitor}) no longer initialized or lost.")
                        self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} lost.")
                        try: self.joystick.quit()
                        except pygame.error: pass
                        self.joystick = None; self.joystick_instance_id_to_monitor = None
                        self.active_axis_keys.clear(); self.active_hat_keys.clear()
                    time.sleep(0.1); continue

                for event in pygame.event.get():
                    if self.stop_flag.is_set(): break
                    if not hasattr(event, 'instance_id') or event.instance_id != self.joystick_instance_id_to_monitor: continue

                    event_details: Optional[Dict[str, Any]] = None; raw_str = ""
                    if event.type == pygame.JOYAXISMOTION:
                        axis, value = event.axis, event.value
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Axis {axis}: {value:.2f}"
                        if self.is_listening_for_mapping and abs(value) > AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis, "direction": 1 if value > 0 else -1, "threshold": AXIS_THRESHOLD}
                        elif not self.is_listening_for_mapping:
                            for (ax_id, direction), act_key in list(self.active_axis_keys.items()):
                                if ax_id == axis:
                                    map_info_for_thresh = self.translated_mappings_for_triggering.get(act_key, {})
                                    release_thresh = map_info_for_thresh.get("threshold", AXIS_THRESHOLD) * 0.5
                                    if (direction == 1 and value < release_thresh) or \
                                       (direction == -1 and value > -release_thresh) or \
                                       (abs(value) < release_thresh):
                                        if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, False)
                                        else: self.mappedEventTriggered.emit(act_key, False)
                                        if (ax_id, direction) in self.active_axis_keys: del self.active_axis_keys[(ax_id, direction)]
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type") == "axis" and map_info.get("id") == axis:
                                    map_val_dir = map_info.get("value"); map_thresh = map_info.get("threshold", AXIS_THRESHOLD)
                                    active = (map_val_dir == 1 and value > map_thresh) or \
                                             (map_val_dir == -1 and value < -map_thresh)
                                    if active and (axis, map_val_dir) not in self.active_axis_keys:
                                        if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, True)
                                        else: self.mappedEventTriggered.emit(act_key, True)
                                        self.active_axis_keys[(axis, map_val_dir)] = act_key
                    elif event.type == pygame.JOYBUTTONDOWN:
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Down"
                        if self.is_listening_for_mapping:
                            event_details = {"type": "button", "button_id": event.button}
                        else:
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type") == "button" and map_info.get("id") == event.button:
                                    if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, True)
                                    else: self.mappedEventTriggered.emit(act_key, True)
                                    break
                    elif event.type == pygame.JOYBUTTONUP:
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Up"
                        if not self.is_listening_for_mapping:
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type") == "button" and map_info.get("id") == event.button:
                                    if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, False)
                                    else: self.mappedEventTriggered.emit(act_key, False)
                                    break
                    elif event.type == pygame.JOYHATMOTION:
                        hat, value_tuple = event.hat, event.value
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Hat {hat} {value_tuple}"
                        if self.is_listening_for_mapping and value_tuple != (0, 0):
                            event_details = {"type": "hat", "hat_id": hat, "value": list(value_tuple)}
                        elif not self.is_listening_for_mapping:
                            for (h_id, h_val_active), act_key in list(self.active_hat_keys.items()):
                                if h_id == hat and h_val_active != value_tuple:
                                    if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, False)
                                    else: self.mappedEventTriggered.emit(act_key, False)
                                    if (h_id, h_val_active) in self.active_hat_keys: del self.active_hat_keys[(h_id, h_val_active)]
                            if value_tuple != (0, 0):
                                for act_key, map_info in self.translated_mappings_for_triggering.items():
                                    if map_info.get("type") == "hat" and \
                                       map_info.get("id") == hat and \
                                       tuple(map_info.get("value", (9,9))) == value_tuple:
                                        if (hat, value_tuple) not in self.active_hat_keys:
                                            if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, True)
                                            else: self.mappedEventTriggered.emit(act_key, True)
                                            self.active_hat_keys[(hat, value_tuple)] = act_key
                                        break
                            if value_tuple == (0,0):
                                for (h_id, h_val_active), act_key in list(self.active_hat_keys.items()):
                                    if h_id == hat:
                                        if act_key in GUI_NAV_ACTIONS_INTERNAL_KEYS: self.guiNavigationRequested.emit(act_key, False)
                                        else: self.mappedEventTriggered.emit(act_key, False)
                                        if (h_id, h_val_active) in self.active_hat_keys: del self.active_hat_keys[(h_id, h_val_active)]
                    if self.is_listening_for_mapping and event_details:
                        event_details["type"] = event_details.get("type")
                        self.controllerEventCaptured.emit(event_details, raw_str)
                        self.stop_listening()
                time.sleep(0.01)
            except pygame.error as e:
                logger_cmg.error(f"Pygame error in controller loop (joystick {self.joystick_idx_to_monitor}): {e}")
                self.controllerHotplug.emit(f"Pygame error with Joy {self.joystick_idx_to_monitor}. Re-scanning...")
                if self.joystick:
                    try: self.joystick.quit()
                    except pygame.error: pass
                self.joystick = None; self.joystick_instance_id_to_monitor = None
                self.active_axis_keys.clear(); self.active_hat_keys.clear()
                try:
                    if pygame.joystick.get_init(): pygame.joystick.quit()
                    pygame.joystick.init(); self._last_joystick_count = -1
                    logger_cmg.info("Pygame joystick subsystem re-initialized after error.")
                except pygame.error as reinit_e: logger_cmg.error(f"Failed to re-initialize pygame.joystick: {reinit_e}")
                time.sleep(1)
            except Exception as e_unhandled:
                logger_cmg.exception(f"Unhandled exception in controller thread loop (joystick {self.joystick_idx_to_monitor}): {e_unhandled}")
                time.sleep(1)
        if self.joystick:
            try: self.joystick.quit()
            except pygame.error: pass
        self.controllerHotplug.emit("Controller thread stopped.")
        logger_cmg.info("PygameControllerThread finished running.")


class ControllerSettingsWindow(QWidget):
    # ... (ControllerSettingsWindow class) ...
    # Key changes will be in:
    # - __init__ (Pygame init)
    # - activate_controller_monitoring (Pygame init)
    # - load_settings_into_ui (Use game_config.load_config())
    # - save_all_settings (Use game_config.save_config())
    # - populate_joystick_device_combos (Use game_config or local Pygame)
    # - _setup_ui to use GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS and INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI
    # - on_monitor_joystick_changed uses _translate_and_validate_gui_json_to_pygame_mappings from game_config
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = KeyboardController() if PYNPUT_AVAILABLE else None
        self.currently_pressed_keys = set()
        self.all_joystick_mappings_by_guid: Dict[str, Dict[str, Any]] = {}
        self.current_translated_mappings_for_thread_sim: Dict[str, Any] = {}
        self.current_listening_key_for_joystick_map: Optional[str] = None
        self.last_selected_row_for_joystick_mapping = -1
        self.ui_settings_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controller_gui_ui_settings.ini")
        self.ui_settings = QSettings(self.ui_settings_file_path, QSettings.Format.IniFormat)
        self._focusable_widgets: List[QWidget] = []
        self._current_focus_index: int = -1
        self._combo_box_open: Optional[QComboBox] = None

        # --- GUI-Managed Pygame Initialization (if necessary) ---
        self._gui_pygame_initialized = False
        self._gui_joystick_initialized = False
        if not GAME_CONFIG_MODULE_AVAILABLE: # If using fallback, GUI manages its own Pygame
            self._initialize_pygame_for_gui()
        # --- End GUI-Managed Pygame Initialization ---

        self._setup_ui() # Uses the now globally defined GUI_MAPPABLE_ACTIONS etc.

        self.controller_thread = PygameControllerThread()
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured_for_mapping)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered_for_simulation)
        self.controller_thread.guiNavigationRequested.connect(self.handle_gui_navigation)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log_and_joystick_combos)

        QTimer.singleShot(0, self._populate_focusable_widgets_list)
        logger_cmg.info("ControllerSettingsWindow initialized.")
        self.setStyleSheet("QWidget:focus { border: 2px solid #0078D7; } QComboBox::item:selected { background-color: #0078D7; color: white; }")

        if parent is None:
            self.load_settings_into_ui()
            self.activate_controller_monitoring() # This will start the thread which needs Pygame

    def _initialize_pygame_for_gui(self, force_rescan=False):
        """Initializes Pygame and Joystick specifically for the GUI's needs if main_game.config is not available."""
        if not self._gui_pygame_initialized:
            try:
                pygame.init()
                self._gui_pygame_initialized = True
                logger_cmg.info("GUI: Pygame initialized by ControllerSettingsWindow (fallback active).")
            except Exception as e:
                logger_cmg.error(f"GUI: Pygame init failed in ControllerSettingsWindow: {e}")
                return False

        if not self._gui_joystick_initialized or force_rescan:
            if self._gui_joystick_initialized:
                try: pygame.joystick.quit()
                except pygame.error: pass
            try:
                pygame.joystick.init()
                self._gui_joystick_initialized = True
                logger_cmg.info("GUI: Pygame Joystick initialized by ControllerSettingsWindow (fallback active).")
            except Exception as e:
                logger_cmg.error(f"GUI: Pygame Joystick init failed in ControllerSettingsWindow: {e}")
                self._gui_joystick_initialized = False
                return False
        return True

    def _get_gui_joystick_data(self) -> List[Tuple[str, str, Optional[str], int]]:
        """Gets joystick data using direct Pygame calls, for when GameConfigFallback is active."""
        if not self._gui_joystick_initialized:
             logger_cmg.warning("GUI joystick data requested but Pygame joystick not initialized by GUI.")
             return []
        joysticks_data = []
        for i in range(pygame.joystick.get_count()):
            try:
                joy = pygame.joystick.Joystick(i)
                # Ensure joystick is init'd before getting name/guid if not already
                was_init = joy.get_init()
                if not was_init: joy.init()

                name = joy.get_name()
                guid = joy.get_guid() if hasattr(joy, 'get_guid') else f"noguid_idx{i}"
                internal_id_for_assignment = f"joystick_pygame_{i}"
                display_name = f"Joy {i}: {name}"
                joysticks_data.append((display_name, internal_id_for_assignment, guid, i))

                if not was_init and joy.get_init(): joy.quit() # Quit if we init'd it just for this
            except pygame.error as e:
                logger_cmg.error(f"GUI: Error getting joystick {i} data: {e}")
                continue
        return joysticks_data

    def _setup_ui(self):
        # ... (UI setup uses GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS and INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI)
        main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Initializing...")
        main_layout.addWidget(self.status_label)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter, 1)

        player_config_group = QGroupBox("Player Input Configuration")
        player_config_v_layout = QVBoxLayout(player_config_group)
        self.config_grid_layout = QGridLayout()
        self.player_device_combos: List[QComboBox] = []
        for i in range(4):
            player_num = i + 1; player_row_layout = QHBoxLayout()
            player_label = QLabel(f"<b>Player {player_num}:</b>")
            player_row_layout.addWidget(player_label, 0, Qt.AlignmentFlag.AlignLeft); dev_combo = QComboBox()
            dev_combo.setMinimumWidth(180); dev_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            dev_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.player_device_combos.append(dev_combo); player_row_layout.addWidget(dev_combo, 1)
            self.config_grid_layout.addLayout(player_row_layout, i, 0)
        player_config_v_layout.addLayout(self.config_grid_layout); player_config_v_layout.addStretch(1)
        self.main_splitter.addWidget(player_config_group)

        joy_map_group = QGroupBox("Controller Button/Axis Mapping (for selected controller)")
        joy_map_table_v_layout = QVBoxLayout(joy_map_group)
        self.mappings_table = QTableWidget(); self.mappings_table.setColumnCount(8)
        self.mappings_table.setHorizontalHeaderLabels(["Action", "Input", "", "", "Action", "Input", "", ""])
        self.mappings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mappings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.mappings_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.mappings_table.horizontalHeader()
        for col_idx in [0, 4]: header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
        for col_idx in [1, 5]: header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
        for col_idx in [2, 3, 6, 7]: header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click)
        self.mappings_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        joy_map_table_v_layout.addWidget(self.mappings_table); self.main_splitter.addWidget(joy_map_group)

        monitor_and_log_group = QGroupBox("Monitoring & Event Log")
        monitor_log_v_layout = QVBoxLayout(monitor_and_log_group)
        map_ctrl_h_layout = QHBoxLayout(); map_ctrl_h_layout.addWidget(QLabel("Monitor & Map Controller:"))
        self.joystick_select_combo_for_mapping = QComboBox()
        self.joystick_select_combo_for_mapping.currentIndexChanged.connect(self.on_monitor_joystick_changed)
        self.joystick_select_combo_for_mapping.setMinimumWidth(180)
        self.joystick_select_combo_for_mapping.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.joystick_select_combo_for_mapping.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        map_ctrl_h_layout.addWidget(self.joystick_select_combo_for_mapping, 1); monitor_log_v_layout.addLayout(map_ctrl_h_layout)

        tbl_ctrl_h_layout = QHBoxLayout(); tbl_ctrl_h_layout.addWidget(QLabel("Action to Map:"))
        self.key_to_map_combo = QComboBox(); self.key_to_map_combo.setMinimumWidth(130)
        self.key_to_map_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.key_to_map_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Use the GUI-specific mappable actions and friendly names
        for ik_idx, ik_internal_key in enumerate(GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS):
             friendly_name_for_combo = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(ik_internal_key, ik_internal_key)
             self.key_to_map_combo.addItem(friendly_name_for_combo, userData=ik_internal_key)
             if ik_internal_key in GUI_NAV_ACTIONS_INTERNAL_KEYS:
                 self.key_to_map_combo.setItemData(ik_idx, Qt.ItemDataRole.UserRole + 1, True)
                 font = self.key_to_map_combo.font(); font.setItalic(True)
                 self.key_to_map_combo.setItemData(ik_idx, font, Qt.ItemDataRole.FontRole)
        tbl_ctrl_h_layout.addWidget(self.key_to_map_combo, 1); monitor_log_v_layout.addLayout(tbl_ctrl_h_layout)

        listen_buttons_layout = QHBoxLayout()
        self.listen_button = QPushButton("Map Selected Action to Input")
        self.listen_button.clicked.connect(self.start_listening_for_joystick_map_from_button)
        self.listen_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        listen_buttons_layout.addWidget(self.listen_button)
        self.cancel_listen_button = QPushButton("Cancel Listening")
        self.cancel_listen_button.clicked.connect(self.cancel_listening_manually)
        self.cancel_listen_button.setVisible(False); self.cancel_listen_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        listen_buttons_layout.addWidget(self.cancel_listen_button)
        monitor_log_v_layout.addLayout(listen_buttons_layout)
        self.clear_current_mappings_button = QPushButton("Clear Mappings for Selected Controller")
        self.clear_current_mappings_button.clicked.connect(self.confirm_clear_current_controller_mappings)
        self.clear_current_mappings_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        monitor_log_v_layout.addWidget(self.clear_current_mappings_button)
        monitor_log_v_layout.addWidget(QLabel("Event Log:"))
        self.debug_console = QTextEdit(); self.debug_console.setReadOnly(True)
        self.debug_console.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        monitor_log_v_layout.addWidget(self.debug_console, 1); self.main_splitter.addWidget(monitor_and_log_group)
        self.main_splitter.setStretchFactor(0, 2); self.main_splitter.setStretchFactor(1, 5); self.main_splitter.setStretchFactor(2, 2)
        self.load_splitter_sizes()

        file_btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save All Settings")
        self.save_btn.clicked.connect(self.save_all_settings_and_ui)
        self.save_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        file_btn_layout.addWidget(self.save_btn)
        self.reset_btn = QPushButton("Reset All Settings to Default")
        self.reset_btn.clicked.connect(self.confirm_reset_all_settings)
        self.reset_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        file_btn_layout.addWidget(self.reset_btn)
        main_layout.addLayout(file_btn_layout)
    
    def _populate_focusable_widgets_list(self):
        # ... (unchanged) ...
        self._focusable_widgets = []
        for combo in self.player_device_combos: self._focusable_widgets.append(combo)
        self._focusable_widgets.append(self.save_btn)
        self._focusable_widgets.append(self.reset_btn)
        self._focusable_widgets.append(self.joystick_select_combo_for_mapping)
        self._focusable_widgets.append(self.key_to_map_combo)
        self._focusable_widgets.append(self.listen_button)
        self._focusable_widgets.append(self.cancel_listen_button)
        self._focusable_widgets.append(self.clear_current_mappings_button)
        self._focusable_widgets.append(self.mappings_table)
        if self.joystick_select_combo_for_mapping.count() > 0 and self.joystick_select_combo_for_mapping.itemData(0) is not None:
            self.set_current_focus_widget(self.joystick_select_combo_for_mapping)
        elif self._focusable_widgets:
             first_valid_widget = next((w for w in self._focusable_widgets if w.isVisible() and w.isEnabled()), None)
             if first_valid_widget: self.set_current_focus_widget(first_valid_widget)
    
    def keyPressEvent(self, event: QKeyEvent):
        # ... (unchanged) ...
        if event.key() == Qt.Key.Key_Tab: self.navigate_focus(True); event.accept()
        elif event.key() == Qt.Key.Key_Backtab: self.navigate_focus(False); event.accept()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            focused_widget = QApplication.focusWidget()
            if focused_widget: self.activate_widget(focused_widget)
            event.accept()
        else: super().keyPressEvent(event)

    def on_monitor_joystick_changed(self, index_in_combo: int):
        logger_cmg.debug(f"Monitor joystick changed. Combo index: {index_in_combo}")
        if self.controller_thread.is_listening_for_mapping: self.cancel_listening_manually()

        if index_in_combo == -1 or self.joystick_select_combo_for_mapping.count() == 0:
            self.controller_thread.set_joystick_to_monitor(-1); self.update_status_and_log("No controller selected for mapping.")
            self.listen_button.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
            self.update_simulation_thread_mappings({}); self.refresh_joystick_mappings_table(None); return

        joy_data = self.joystick_select_combo_for_mapping.itemData(index_in_combo)
        if not isinstance(joy_data, dict):
            self.controller_thread.set_joystick_to_monitor(-1); self.update_status_and_log("No valid controller selected (data error).")
            self.listen_button.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
            self.update_simulation_thread_mappings({}); self.refresh_joystick_mappings_table(None); return

        pygame_joy_idx = joy_data.get("index"); current_guid = joy_data.get("guid")
        current_joy_text = self.joystick_select_combo_for_mapping.itemText(index_in_combo)
        if pygame_joy_idx is not None and current_guid:
            self.controller_thread.set_joystick_to_monitor(pygame_joy_idx)
            self.update_status_and_log(f"Monitoring '{current_joy_text}' for mapping and simulation.")
            self.listen_button.setEnabled(True); self.clear_current_mappings_button.setEnabled(True)
            
            # Mappings loading / fallback logic
            if current_guid not in self.all_joystick_mappings_by_guid:
                logger_cmg.info(f"No specific GUI mappings for GUID {current_guid}. Attempting fallback/default.")
                source_guid_for_fallback = next((g for g, m in self.all_joystick_mappings_by_guid.items() if m and g != current_guid), None)
                if source_guid_for_fallback:
                    self.all_joystick_mappings_by_guid[current_guid] = copy.deepcopy(self.all_joystick_mappings_by_guid[source_guid_for_fallback])
                    self.update_status_and_log(f"Applied fallback GUI mappings from '{self.get_joystick_display_name_by_guid(source_guid_for_fallback)}' to '{current_joy_text}'.")
                elif hasattr(game_config, 'DEFAULT_GENERIC_JOYSTICK_MAPPINGS') and isinstance(getattr(game_config, 'DEFAULT_GENERIC_JOYSTICK_MAPPINGS'), dict):
                    defaults_in_gui_format = {}
                    default_runtime_maps_to_use = getattr(game_config, 'DEFAULT_GENERIC_JOYSTICK_MAPPINGS')
                    for action, runtime_map_entry in default_runtime_maps_to_use.items():
                        if action in GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS:
                            gui_map_entry = _convert_runtime_default_to_gui_storage(action, runtime_map_entry, pygame_joy_idx)
                            if gui_map_entry: defaults_in_gui_format[action] = gui_map_entry
                    if defaults_in_gui_format:
                        self.all_joystick_mappings_by_guid[current_guid] = defaults_in_gui_format
                        self.update_status_and_log(f"Applied default generic joystick mappings (converted to GUI format) to '{current_joy_text}'.")
                    else: self.all_joystick_mappings_by_guid[current_guid] = {}
                else: self.all_joystick_mappings_by_guid[current_guid] = {}

            current_gui_mappings = self.all_joystick_mappings_by_guid.get(current_guid, {})
            self.update_simulation_thread_mappings(current_gui_mappings)
            self.refresh_joystick_mappings_table(current_guid)
        else:
            self.controller_thread.set_joystick_to_monitor(-1); self.update_status_and_log("Error: Invalid data for selected controller.")
            self.listen_button.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
            self.update_simulation_thread_mappings({}); self.refresh_joystick_mappings_table(None)
    
    def update_simulation_thread_mappings(self, raw_gui_mappings: Dict[str, Any]):
        self.current_translated_mappings_for_thread_sim.clear()
        # Use the method from the (potentially fallback) game_config object
        if hasattr(game_config, '_translate_and_validate_gui_json_to_pygame_mappings'):
            translated_runtime_mappings = game_config._translate_and_validate_gui_json_to_pygame_mappings(raw_gui_mappings) # type: ignore
            if isinstance(translated_runtime_mappings, dict):
                self.current_translated_mappings_for_thread_sim = translated_runtime_mappings
            else: logger_cmg.error("Translation from GUI to runtime mappings failed or returned invalid type.")
        else:
             logger_cmg.critical("Config module is missing '_translate_and_validate_gui_json_to_pygame_mappings' method. Simulation thread will not have correct mappings.")
        self.controller_thread.translated_mappings_for_triggering = self.current_translated_mappings_for_thread_sim

    def save_splitter_sizes(self):
        # ... (unchanged) ...
        if hasattr(self, 'main_splitter') and self.main_splitter:
            self.ui_settings.setValue("splitter_sizes", [int(s) for s in self.main_splitter.sizes()])

    def load_splitter_sizes(self):
        # ... (unchanged) ...
        if hasattr(self, 'main_splitter') and self.main_splitter and self.main_splitter.count() == 3:
            default_sizes = [int(self.main_splitter.width() * 0.25), int(self.main_splitter.width() * 0.5), int(self.main_splitter.width() * 0.25)]
            saved_value = self.ui_settings.value("splitter_sizes"); sizes_to_apply = []
            if isinstance(saved_value, list) and len(saved_value) == 3:
                try: sizes_to_apply = [int(s) for s in saved_value]
                except (ValueError, TypeError): sizes_to_apply = default_sizes
            elif isinstance(saved_value, str):
                 try:
                    str_list = saved_value.strip('[]').split(',')
                    if len(str_list) == 3: sizes_to_apply = [int(s.strip()) for s in str_list]
                    else: sizes_to_apply = default_sizes
                 except: sizes_to_apply = default_sizes
            else: sizes_to_apply = default_sizes
            if sizes_to_apply and sum(sizes_to_apply) > 50 : self.main_splitter.setSizes(sizes_to_apply)

    def save_all_settings_and_ui(self): self.save_all_settings(); self.save_splitter_sizes()

    def refresh_joystick_mappings_table(self, current_controller_guid: Optional[str], preserve_scroll=False, target_row_action_key: Optional[str] = None):
        # ... (uses GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS and INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI) ...
        current_v_scroll_value = self.mappings_table.verticalScrollBar().value() if preserve_scroll else -1
        self.mappings_table.setRowCount(0)
        if not current_controller_guid: self.log_to_debug_console("Mapping table cleared (no controller)."); return
        mappings_to_display = self.all_joystick_mappings_by_guid.get(current_controller_guid, {})
        num_actions = len(GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS); num_rows_needed = (num_actions + 1) // 2
        self.mappings_table.setRowCount(num_rows_needed); target_table_row_to_ensure_visible = -1
        min_button_width = 70
        for i in range(num_rows_needed):
            for col_group in range(2):
                action_idx = i * 2 + col_group;
                if action_idx >= num_actions: continue
                internal_key = GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS[action_idx]
                friendly_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_key, internal_key)
                if target_row_action_key and internal_key == target_row_action_key: target_table_row_to_ensure_visible = i
                base_col = col_group * 4
                action_item = QTableWidgetItem(friendly_display_name); action_item.setData(Qt.ItemDataRole.UserRole, internal_key)
                self.mappings_table.setItem(i, base_col + 0, action_item)
                mapping_info = mappings_to_display.get(internal_key)
                if mapping_info:
                    self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem(mapping_info.get("raw_str", "N/A")))
                    rename_btn = QPushButton("Rename"); rename_btn.setMinimumWidth(min_button_width)
                    rename_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
                    rename_btn.setProperty("internal_key", internal_key); rename_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    rename_btn.clicked.connect(lambda checked=False, k=internal_key: self.rename_joystick_mapping_friendly_name_prompt(k))
                    self.mappings_table.setCellWidget(i, base_col + 2, rename_btn)
                    clear_btn = QPushButton("Clear"); clear_btn.setMinimumWidth(min_button_width)
                    clear_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
                    clear_btn.setProperty("internal_key", internal_key); clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    clear_btn.clicked.connect(lambda checked=False, k=internal_key: self.clear_joystick_mapping(k))
                    self.mappings_table.setCellWidget(i, base_col + 3, clear_btn)
                else: self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem("Not Mapped"))
        if target_table_row_to_ensure_visible != -1: self.mappings_table.scrollToItem(self.mappings_table.item(target_table_row_to_ensure_visible, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        elif preserve_scroll and current_v_scroll_value != -1: self.mappings_table.verticalScrollBar().setValue(current_v_scroll_value)
        if self.current_listening_key_for_joystick_map == target_row_action_key : self.current_listening_key_for_joystick_map = None

    def closeEvent(self, event: QKeyEvent):
        logger_cmg.info("ControllerSettingsWindow closeEvent. Shutting down thread and saving UI state.")
        self.save_splitter_sizes(); self.deactivate_controller_monitoring(); super().closeEvent(event)

    def save_all_settings(self):
        logger_cmg.info("Saving game configuration settings.")
        if not GAME_CONFIG_MODULE_AVAILABLE:
            QMessageBox.warning(self, "Save Error", f"Cannot save settings: main_game.config module not loaded (Error: {game_config_module_error_message}). Settings will not persist.")
            self.update_status_and_log("Error: Could not save game settings (config module missing).")
            return

        for i in range(4):
            player_idx = i
            selected_device_id = self.player_device_combos[player_idx].currentData() if player_idx < len(self.player_device_combos) else UNASSIGNED_DEVICE_ID_CONST
            
            setattr(game_config, f"CURRENT_P{player_idx+1}_INPUT_DEVICE", selected_device_id)
            is_keyboard_device = selected_device_id and selected_device_id.startswith("keyboard_")
            is_joystick_device = selected_device_id and selected_device_id.startswith("joystick_pygame_")
            setattr(game_config, f"P{player_idx+1}_KEYBOARD_ENABLED", is_keyboard_device)
            setattr(game_config, f"P{player_idx+1}_CONTROLLER_ENABLED", is_joystick_device)
        
        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS = copy.deepcopy(self.all_joystick_mappings_by_guid)
        if game_config.save_config(): self.update_status_and_log("All game settings saved successfully via main_game.config.")
        else: QMessageBox.critical(self, "Save Error", "Could not save game settings to file via main_game.config."); self.update_status_and_log("Error: Could not save game settings.")
        
        # Update runtime player mappings in game_config after saving
        if hasattr(game_config, 'update_player_mappings_from_config'):
            game_config.update_player_mappings_from_config()
            logger_cmg.info("Called game_config.update_player_mappings_from_config() after save.")

    def load_settings_into_ui(self):
        logger_cmg.info("Loading settings into UI...");
        if not GAME_CONFIG_MODULE_AVAILABLE:
            self.update_status_and_log(f"Warning: main_game.config not loaded. Using fallback defaults. Cannot load persisted settings. Error: {game_config_module_error_message}")
        else:
            game_config.load_config() # This will load from file into game_config attributes

        # Populate GUI from the current state of game_config (real or fallback)
        self.all_joystick_mappings_by_guid = copy.deepcopy(getattr(game_config, 'LOADED_PYGAME_JOYSTICK_MAPPINGS', {}))
        
        self.populate_joystick_device_combos() # This uses game_config or local Pygame calls

        for i in range(len(self.player_device_combos)):
            player_idx = i
            current_device_val = getattr(game_config, f"CURRENT_P{player_idx+1}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID_CONST)
            combo = self.player_device_combos[player_idx]
            idx = combo.findData(current_device_val)
            combo.setCurrentIndex(idx if idx != -1 else 0)
        
        if self.joystick_select_combo_for_mapping.currentIndex() != -1 and self.joystick_select_combo_for_mapping.currentData():
            self.on_monitor_joystick_changed(self.joystick_select_combo_for_mapping.currentIndex())
        else:
            self.refresh_joystick_mappings_table(None)
            self.update_simulation_thread_mappings({})
            self.listen_button.setEnabled(False)
            self.clear_current_mappings_button.setEnabled(False)
        self.update_status_and_log("Settings loaded into UI.")

    def confirm_reset_all_settings(self):
        # ... (unchanged) ...
        if QMessageBox.question(self, "Confirm Reset", "Reset all input settings to default values (including all controller mappings and UI layout)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.perform_reset_all_settings()

    def perform_reset_all_settings(self):
        # ... (This now sets defaults on the game_config object) ...
        logger_cmg.info("Resetting all settings to default values (on game_config object).")
        if not GAME_CONFIG_MODULE_AVAILABLE:
            self.update_status_and_log("Cannot reset settings: main_game.config module not loaded. Using fallback values.")
            # Apply fallback defaults to the GameConfigFallback instance for UI refresh
            for i in range(1, 5):
                p_num_str = f"P{i}"
                setattr(game_config, f"CURRENT_{p_num_str}_INPUT_DEVICE", getattr(game_config, f"DEFAULT_{p_num_str}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID_CONST))
                setattr(game_config, f"{p_num_str}_KEYBOARD_ENABLED", getattr(game_config, f"DEFAULT_{p_num_str}_KEYBOARD_ENABLED", i<=2))
                setattr(game_config, f"{p_num_str}_CONTROLLER_ENABLED", getattr(game_config, f"DEFAULT_{p_num_str}_CONTROLLER_ENABLED", False))
            game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.clear()
        else: # Real game_config available
            for i in range(1, 5):
                player_idx = i -1
                p_num_str = f"P{i}"
                default_device_attr_key = f"DEFAULT_{p_num_str}_INPUT_DEVICE"
                default_kbd_en_key = f"DEFAULT_{p_num_str}_KEYBOARD_ENABLED"
                default_ctrl_en_key = f"DEFAULT_{p_num_str}_CONTROLLER_ENABLED"

                setattr(game_config, f"CURRENT_{p_num_str}_INPUT_DEVICE", getattr(game_config, default_device_attr_key, UNASSIGNED_DEVICE_ID_CONST))
                setattr(game_config, f"{p_num_str}_KEYBOARD_ENABLED", getattr(game_config, default_kbd_en_key, i<=2))
                setattr(game_config, f"{p_num_str}_CONTROLLER_ENABLED", getattr(game_config, default_ctrl_en_key, False))
            game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.clear() # Clear mappings on the game_config object

        self.all_joystick_mappings_by_guid.clear() # Clear GUI's copy too
        self.ui_settings.remove("splitter_sizes"); self.ui_settings.remove("main_window_geometry")
        logger_cmg.info("Cleared UI settings (splitter sizes, window geometry) from .ini file.")
        
        self.load_settings_into_ui(); # Reload (which will now pick up defaults from game_config)
        self.load_splitter_sizes()
        self.update_status_and_log("All settings reset to default. Save to make changes permanent.")

    def confirm_clear_current_controller_mappings(self):
        # ... (unchanged) ...
        current_guid = self.get_current_mapping_joystick_guid()
        if not current_guid: QMessageBox.information(self, "No Controller", "No controller selected to clear mappings for.", QMessageBox.StandardButton.Ok); return
        controller_name = self.joystick_select_combo_for_mapping.currentText()
        reply = QMessageBox.question(self, "Confirm Clear", f"Are you sure you want to clear all mappings for '{controller_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.perform_clear_current_controller_mappings(current_guid, controller_name)

    def perform_clear_current_controller_mappings(self, guid_to_clear: str, controller_name_for_log: str):
        # ... (unchanged) ...
        if guid_to_clear in self.all_joystick_mappings_by_guid:
            self.all_joystick_mappings_by_guid[guid_to_clear].clear()
            self.refresh_joystick_mappings_table(guid_to_clear)
            self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid.get(guid_to_clear, {}))
            self.update_status_and_log(f"Cleared all mappings for '{controller_name_for_log}'. Save to make permanent.")
        else: self.update_status_and_log(f"No mappings found to clear for '{controller_name_for_log}'.")

    def activate_controller_monitoring(self):
        logger_cmg.info("Activating controller monitoring thread.")
        # Ensure Pygame is ready for the thread
        if GAME_CONFIG_MODULE_AVAILABLE:
            if not hasattr(game_config, '_pygame_initialized_globally') or not game_config._pygame_initialized_globally or \
               not hasattr(game_config, '_joystick_initialized_globally') or not game_config._joystick_initialized_globally:
                game_config.init_pygame_and_joystick_globally(force_rescan=True)
        else: # Fallback, GUI manages its own Pygame
            if not self._gui_pygame_initialized or not self._gui_joystick_initialized:
                self._initialize_pygame_for_gui(force_rescan=True)
        
        if (GAME_CONFIG_MODULE_AVAILABLE and hasattr(game_config, '_joystick_initialized_globally') and game_config._joystick_initialized_globally) or \
           (not GAME_CONFIG_MODULE_AVAILABLE and self._gui_joystick_initialized):
            if not self.controller_thread.isRunning():
                self.controller_thread.stop_flag.clear(); self.controller_thread.start()
            self.update_status_and_log_and_joystick_combos("Controller monitoring activated.")
        else:
            self.update_status_and_log("Error: Pygame Joystick not ready. Controller monitoring NOT activated.")

    def deactivate_controller_monitoring(self):
        # ... (unchanged) ...
        logger_cmg.info("Deactivating controller monitoring thread.")
        if self.controller_thread.isRunning():
            self.controller_thread.stop()
            if not self.controller_thread.wait(1000): logger_cmg.warning("Controller thread did not stop gracefully.")
            else: logger_cmg.info("Controller thread stopped successfully.")
        if self.keyboard and self.currently_pressed_keys:
            logger_cmg.debug(f"Releasing simulated keys: {self.currently_pressed_keys}")
            for key_to_release in list(self.currently_pressed_keys):
                try: self.keyboard.release(key_to_release)
                except Exception as e: logger_cmg.error(f"Error releasing key {key_to_release}: {e}")
            self.currently_pressed_keys.clear()

    def log_to_debug_console(self, message: str):
        # ... (unchanged) ...
        if hasattr(self, 'debug_console'):
            self.debug_console.append(f"[{time.strftime('%H:%M:%S')}] {message}"); self.debug_console.ensureCursorVisible()

    def update_status_and_log(self, message: str):
        # ... (unchanged) ...
        if hasattr(self, 'status_label'): self.status_label.setText(message)
        self.log_to_debug_console(message)
        level = logging.WARNING if "error" in message.lower() or "lost" in message.lower() else logging.INFO
        logger_cmg.log(level, f"Settings GUI Status: {message}")

    def update_status_and_log_and_joystick_combos(self, message: str):
        # ... (unchanged) ...
        self.update_status_and_log(message); self.populate_joystick_device_combos()

    def get_current_mapping_joystick_guid(self) -> Optional[str]:
        # ... (unchanged) ...
        if self.joystick_select_combo_for_mapping.currentIndex() == -1: return None
        joy_data = self.joystick_select_combo_for_mapping.currentData()
        return joy_data.get("guid") if isinstance(joy_data, dict) else None

    def get_joystick_display_name_by_guid(self, target_guid: str) -> str:
        # ... (unchanged) ...
        for i in range(self.joystick_select_combo_for_mapping.count()):
            data = self.joystick_select_combo_for_mapping.itemData(i)
            if isinstance(data, dict) and data.get("guid") == target_guid:
                return self.joystick_select_combo_for_mapping.itemText(i)
        return f"Ctrl (GUID:...{target_guid[-6:]})" if target_guid else "Unknown Ctrl"

    def populate_joystick_device_combos(self):
        logger_cmg.debug("Populating all joystick device comboboxes...")
        available_joysticks_full_data: List[Tuple[str, str, Optional[str], int]]
        
        if GAME_CONFIG_MODULE_AVAILABLE:
            if not hasattr(game_config, '_joystick_initialized_globally') or not game_config._joystick_initialized_globally:
                logger_cmg.warning("Populate Combos: Pygame joystick not globally initialized by config. Attempting init.")
                game_config.init_pygame_and_joystick_globally(force_rescan=True)
            available_joysticks_full_data = game_config.get_available_joystick_names_with_indices_and_guids() # type: ignore
        else: # Fallback: GUI manages its own Pygame for joystick listing
            if not self._gui_joystick_initialized:
                self._initialize_pygame_for_gui(force_rescan=True)
            available_joysticks_full_data = self._get_gui_joystick_data()

        logger_cmg.debug(f"Available joysticks for combos: {available_joysticks_full_data}")
        current_player_dev_selections = [combo.currentData() for combo in self.player_device_combos]
        prev_selected_mapping_guid = self.get_current_mapping_joystick_guid()
        all_combos_to_clear = self.player_device_combos + [self.joystick_select_combo_for_mapping]
        for combo in all_combos_to_clear: combo.blockSignals(True); combo.clear(); combo.blockSignals(False)

        for i, player_combo in enumerate(self.player_device_combos):
            player_combo.blockSignals(True); player_combo.addItem(UNASSIGNED_DEVICE_NAME_CONST, UNASSIGNED_DEVICE_ID_CONST)
            # Use keyboard device lists from game_config (real or fallback)
            kbd_ids = getattr(game_config, 'KEYBOARD_DEVICE_IDS', ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"])
            kbd_names = getattr(game_config, 'KEYBOARD_DEVICE_NAMES', ["Keyboard (P1)", "Keyboard (P2)", "Keyboard (Unassigned)"])
            for k_idx, k_id in enumerate(kbd_ids):
                if k_id == UNASSIGNED_DEVICE_ID_CONST: continue
                k_name = kbd_names[k_idx] if k_idx < len(kbd_names) else k_id
                player_combo.addItem(k_name, k_id)
            for joy_display_name, internal_id_for_assignment, _, _ in available_joysticks_full_data:
                player_combo.addItem(joy_display_name, internal_id_for_assignment)
            player_combo.blockSignals(False)
            idx_to_set = player_combo.findData(current_player_dev_selections[i] if i < len(current_player_dev_selections) else UNASSIGNED_DEVICE_ID_CONST)
            player_combo.setCurrentIndex(idx_to_set if idx_to_set != -1 else 0)

        new_mapping_combo_selection_idx = -1
        self.joystick_select_combo_for_mapping.blockSignals(True)
        if not available_joysticks_full_data:
            self.joystick_select_combo_for_mapping.addItem("No Controllers Detected", None)
            self.listen_button.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
        else:
            for joy_display_name, _, joy_guid_str, pygame_joy_idx in available_joysticks_full_data:
                name_part = joy_display_name.split(': ', 1)[-1].split(' (GUID:')[0]
                map_combo_display_name = f"Joy {pygame_joy_idx}: {name_part}"
                self.joystick_select_combo_for_mapping.addItem(map_combo_display_name, {"index": pygame_joy_idx, "guid": joy_guid_str, "name": map_combo_display_name})
                if joy_guid_str == prev_selected_mapping_guid: new_mapping_combo_selection_idx = self.joystick_select_combo_for_mapping.count() - 1
        self.joystick_select_combo_for_mapping.blockSignals(False)

        if new_mapping_combo_selection_idx != -1: self.joystick_select_combo_for_mapping.setCurrentIndex(new_mapping_combo_selection_idx)
        elif self.joystick_select_combo_for_mapping.count() > 0: self.joystick_select_combo_for_mapping.setCurrentIndex(0)
        
        if self.joystick_select_combo_for_mapping.count() > 0 and self.joystick_select_combo_for_mapping.currentData() is not None:
            self.on_monitor_joystick_changed(self.joystick_select_combo_for_mapping.currentIndex())
        else:
            self.controller_thread.set_joystick_to_monitor(-1); self.update_simulation_thread_mappings({})
            self.refresh_joystick_mappings_table(None);
            self.listen_button.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
            if not available_joysticks_full_data: self.update_status_and_log("No controllers available for mapping.")
        logger_cmg.debug("All joystick device comboboxes populated.")

    # ... (Rest of the methods like start_listening_for_joystick_map_from_button,
    #      initiate_listening_sequence_for_joystick_map, on_controller_event_captured_for_mapping,
    #      reset_listening_ui_for_joystick_map, on_mapped_event_triggered_for_simulation,
    #      handle_table_double_click, rename_joystick_mapping_friendly_name_prompt,
    #      clear_joystick_mapping, set_current_focus_widget, navigate_focus,
    #      activate_widget, handle_gui_navigation remain largely the same in their core logic.
    #      They will now use the GUI-specific action lists and friendly names,
    #      and the on_monitor_joystick_changed will use game_config for translation.)

    # start_listening_for_joystick_map_from_button, initiate_listening_sequence_for_joystick_map, cancel_listening_manually
    # on_controller_event_captured_for_mapping, reset_listening_ui_for_joystick_map:
    # These interact with self.key_to_map_combo which now uses GUI_MAPPABLE_ACTIONS_INTERNAL_KEYS.
    # The logic for conflict checks (MENU_SPECIFIC_ACTIONS_GUI) and display names (INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI) is now based on the GUI-constructed lists.

    # on_mapped_event_triggered_for_simulation:
    # Checks against GUI_NAV_ACTIONS_INTERNAL_KEYS.

    # handle_gui_navigation:
    # Uses GUI_NAV_ACTION constants.

    # The methods below were largely correct and mostly just needed to use the refined constant names
    # or ensure they use the active `game_config` object where appropriate.

    def start_listening_for_joystick_map_from_button(self):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid: self.update_status_and_log("Error: No controller selected to map to."); return
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map: self.update_status_and_log("Error: No action selected to map."); return
        self.initiate_listening_sequence_for_joystick_map(str(internal_key_to_map)) # Cast to str for safety

    def initiate_listening_sequence_for_joystick_map(self, internal_key_to_map_str: str, originating_row_idx_in_table:int = -1):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or self.controller_thread.joystick_idx_to_monitor == -1 or self.controller_thread.joystick is None:
            self.update_status_and_log("Cannot listen: No controller selected or controller not ready/active."); return
        self.current_listening_key_for_joystick_map = internal_key_to_map_str
        self.last_selected_row_for_joystick_mapping = originating_row_idx_in_table
        self.controller_thread.start_listening()
        friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_key_to_map_str, internal_key_to_map_str)
        monitor_joy_text = self.joystick_select_combo_for_mapping.currentText()
        self.update_status_and_log(f"Listening for '{friendly_name}' on {monitor_joy_text}... Press input or '{GUI_NAV_ACTIONS_FRIENDLY_NAMES.get(GUI_NAV_CANCEL, GUI_NAV_CANCEL)}' to cancel.")
        self.listen_button.setText("Listening..."); self.listen_button.setEnabled(False)
        self.cancel_listen_button.setVisible(True); self.cancel_listen_button.setEnabled(True); self.set_current_focus_widget(self.cancel_listen_button)
        self.key_to_map_combo.setEnabled(False); self.joystick_select_combo_for_mapping.setEnabled(False)
        self.mappings_table.setEnabled(False); self.clear_current_mappings_button.setEnabled(False)
        self.save_btn.setEnabled(False); self.reset_btn.setEnabled(False)

    def cancel_listening_manually(self):
        if self.controller_thread.is_listening_for_mapping:
            self.controller_thread.stop_listening()
            action_being_mapped = self.current_listening_key_for_joystick_map
            friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(action_being_mapped, action_being_mapped) if action_being_mapped else "action"
            self.update_status_and_log(f"Listening for '{friendly_name}' cancelled by user.")
            self.reset_listening_ui_for_joystick_map()

    def on_controller_event_captured_for_mapping(self, event_details_from_thread: dict, raw_event_str: str):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        action_being_mapped = self.current_listening_key_for_joystick_map
        if not action_being_mapped or not current_mapping_guid:
            logger_cmg.warning("Controller event captured but no action or GUID. Resetting UI.")
            self.reset_listening_ui_for_joystick_map(); return
        if current_mapping_guid not in self.all_joystick_mappings_by_guid:
            self.all_joystick_mappings_by_guid[current_mapping_guid] = {}
        current_controller_mappings_gui_format = self.all_joystick_mappings_by_guid[current_mapping_guid]
        perform_conflict_check = action_being_mapped not in MENU_SPECIFIC_ACTIONS_GUI
        if perform_conflict_check:
            for existing_key, mapping_info in list(current_controller_mappings_gui_format.items()):
                if existing_key in MENU_SPECIFIC_ACTIONS_GUI: continue
                if mapping_info and mapping_info.get("raw_str") == raw_event_str and existing_key != action_being_mapped:
                    reply = QMessageBox.question(self, "Input Conflict", f"Input '{raw_event_str}' is already mapped to '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(existing_key, existing_key)}'. Overwrite?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        self.update_status_and_log(f"Mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(action_being_mapped,action_being_mapped)}' cancelled due to conflict.")
                        self.reset_listening_ui_for_joystick_map(); return
                    del current_controller_mappings_gui_format[existing_key]
                    self.log_to_debug_console(f"Overwriting mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(existing_key, existing_key)}'."); break
        current_controller_mappings_gui_format[action_being_mapped] = { "event_type": event_details_from_thread["type"], "details": event_details_from_thread, "raw_str": raw_event_str }
        action_friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(action_being_mapped, action_being_mapped)
        self.log_to_debug_console(f"Mapped '{raw_event_str}' to '{action_friendly_name}' for current controller (GUI Format).")
        self.update_status_and_log(f"Mapped '{raw_event_str}' to '{action_friendly_name}'.")
        self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=action_being_mapped)
        self.update_simulation_thread_mappings(current_controller_mappings_gui_format)
        self.reset_listening_ui_for_joystick_map(preserve_scroll=True)

    def reset_listening_ui_for_joystick_map(self, preserve_scroll=False):
        self.listen_button.setText("Map Selected Action to Input")
        can_listen_and_map = (self.joystick_select_combo_for_mapping.currentIndex() != -1 and \
                              self.joystick_select_combo_for_mapping.currentData() is not None)
        self.listen_button.setEnabled(can_listen_and_map)
        self.cancel_listen_button.setVisible(False); self.cancel_listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(True); self.joystick_select_combo_for_mapping.setEnabled(True)
        self.mappings_table.setEnabled(True); self.clear_current_mappings_button.setEnabled(can_listen_and_map)
        self.save_btn.setEnabled(True); self.reset_btn.setEnabled(True)
        self.controller_thread.stop_listening()
        if not preserve_scroll: self.last_selected_row_for_joystick_mapping = -1
        if self.key_to_map_combo.isEnabled(): self.set_current_focus_widget(self.key_to_map_combo)
        elif self.listen_button.isEnabled(): self.set_current_focus_widget(self.listen_button)

    def on_mapped_event_triggered_for_simulation(self, internal_action_key_str: str, is_press_event: bool):
        if internal_action_key_str in GUI_NAV_ACTIONS_INTERNAL_KEYS: return
        action_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_action_key_str, internal_action_key_str)
        should_simulate_pynput = not (internal_action_key_str in EXCLUSIVE_ACTIONS and not is_press_event)
        log_msg = f"Simulated Game Event: '{action_display_name}' {'Pressed' if is_press_event else 'Released'}"
        if should_simulate_pynput and self.keyboard:
            pynput_key_to_simulate = get_pynput_key(internal_action_key_str)
            if pynput_key_to_simulate:
                try:
                    if is_press_event and pynput_key_to_simulate not in self.currently_pressed_keys:
                        self.keyboard.press(pynput_key_to_simulate); self.currently_pressed_keys.add(pynput_key_to_simulate)
                        log_msg += f" (Keyboard Sim: {str(pynput_key_to_simulate)} Press)"
                    elif not is_press_event and pynput_key_to_simulate in self.currently_pressed_keys:
                        self.keyboard.release(pynput_key_to_simulate); self.currently_pressed_keys.remove(pynput_key_to_simulate)
                        log_msg += f" (Keyboard Sim: {str(pynput_key_to_simulate)} Release)"
                except Exception as e: logger_cmg.error(f"Pynput error for '{action_display_name}': {e}"); log_msg += " (Pynput Error)"
            else: log_msg += " (Pynput sim skipped - no key)"
        elif should_simulate_pynput and not self.keyboard: log_msg += " (Pynput sim skipped - lib not available)"
        self.log_to_debug_console(log_msg)

    def handle_table_double_click(self, row: int, column: int):
        # ... (unchanged) ...
        col_group = 0 if column < 4 else 1
        item_column_index_in_table = col_group * 4 + 0
        action_item = self.mappings_table.item(row, item_column_index_in_table)
        if not action_item: return
        internal_key_clicked = action_item.data(Qt.ItemDataRole.UserRole)
        if not internal_key_clicked: return
        if (column % 4) <= 1:
            self.key_to_map_combo.setCurrentIndex(self.key_to_map_combo.findData(internal_key_clicked))
            self.initiate_listening_sequence_for_joystick_map(str(internal_key_clicked), originating_row_idx_in_table=row) # Cast

    def rename_joystick_mapping_friendly_name_prompt(self, internal_key: str):
        # ... (unchanged, uses INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI for prompt) ...
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or current_mapping_guid not in self.all_joystick_mappings_by_guid or \
           internal_key not in self.all_joystick_mappings_by_guid[current_mapping_guid]:
            self.update_status_and_log("Cannot rename: Mapping not found."); return
        mapping_info = self.all_joystick_mappings_by_guid[current_mapping_guid][internal_key]
        current_label = mapping_info.get("raw_str", "")
        text, ok = QInputDialog.getText(self, "Rename Input Label", f"Custom label for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_key,internal_key)}' (current: {current_label}):", QLineEdit.EchoMode.Normal, current_label)
        if ok and text:
            mapping_info["raw_str"] = text
            self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=internal_key)
            self.log_to_debug_console(f"Relabeled input for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_key,internal_key)}' to '{text}'.")

    def clear_joystick_mapping(self, internal_key: str):
        # ... (unchanged, uses INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI for log) ...
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or current_mapping_guid not in self.all_joystick_mappings_by_guid or \
           internal_key not in self.all_joystick_mappings_by_guid[current_mapping_guid]:
            self.update_status_and_log("Cannot clear: Mapping not found."); return
        del self.all_joystick_mappings_by_guid[current_mapping_guid][internal_key]
        self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=internal_key)
        self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid.get(current_mapping_guid, {}))
        self.log_to_debug_console(f"Cleared joystick mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY_FOR_GUI.get(internal_key, internal_key)}'.")

    def set_current_focus_widget(self, widget: Optional[QWidget]):
        # ... (unchanged) ...
        if widget and widget in self._focusable_widgets and widget.isVisible() and widget.isEnabled():
            self._current_focus_index = self._focusable_widgets.index(widget)
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            if widget == self.mappings_table and self.mappings_table.rowCount() > 0 and self.mappings_table.columnCount() > 0:
                 if self.mappings_table.currentItem() is None: self.mappings_table.setCurrentCell(0,0)
        elif self._focusable_widgets:
            first_valid_widget = next((w for w in self._focusable_widgets if w.isVisible() and w.isEnabled()), None)
            if first_valid_widget:
                self._current_focus_index = self._focusable_widgets.index(first_valid_widget)
                first_valid_widget.setFocus(Qt.FocusReason.OtherFocusReason)
                if first_valid_widget == self.mappings_table and self.mappings_table.rowCount() > 0 and self.mappings_table.columnCount() > 0:
                    if self.mappings_table.currentItem() is None: self.mappings_table.setCurrentCell(0,0)

    def navigate_focus(self, forward: bool):
        # ... (unchanged) ...
        if not self._focusable_widgets: return
        if self._combo_box_open:
            current_idx = self._combo_box_open.currentIndex(); count = self._combo_box_open.count()
            if forward: self._combo_box_open.setCurrentIndex(min(count - 1, current_idx + 1))
            else: self._combo_box_open.setCurrentIndex(max(0, current_idx - 1))
            return
        start_index = self._current_focus_index; num_widgets = len(self._focusable_widgets)
        for i in range(num_widgets):
            if forward: self._current_focus_index = (start_index + 1 + i) % num_widgets
            else: self._current_focus_index = (start_index - 1 - i + num_widgets) % num_widgets
            next_widget = self._focusable_widgets[self._current_focus_index]
            if next_widget.isVisible() and next_widget.isEnabled() and next_widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                self.set_current_focus_widget(next_widget); return
        current_focus_widget = QApplication.focusWidget()
        if current_focus_widget and current_focus_widget in self._focusable_widgets: self._current_focus_index = self._focusable_widgets.index(current_focus_widget)
        elif self._focusable_widgets: self.set_current_focus_widget(self._focusable_widgets[0])

    def activate_widget(self, widget: Optional[QWidget]):
        # ... (unchanged) ...
        if not widget: widget = QApplication.focusWidget()
        if not widget: return
        if self._combo_box_open:
            if widget == self._combo_box_open: self._combo_box_open.hidePopup(); self._combo_box_open = None; self.log_to_debug_console(f"ComboBox '{widget.objectName()}' item selected/closed.")
            return
        if isinstance(widget, QPushButton): widget.click(); self.log_to_debug_console(f"Button '{widget.text()}' activated.")
        elif isinstance(widget, QComboBox): widget.showPopup(); self._combo_box_open = widget; self.log_to_debug_console(f"ComboBox '{widget.objectName()}' opened.")
        elif isinstance(widget, QTableWidget) and widget == self.mappings_table:
            row, col = widget.currentRow(), widget.currentColumn()
            if row >=0 and col >= 0:
                cell_widget = widget.cellWidget(row, col)
                if isinstance(cell_widget, QPushButton): cell_widget.click(); self.log_to_debug_console(f"Table button at ({row},{col}) clicked.")
                else: self.handle_table_double_click(row, col); self.log_to_debug_console(f"Table cell ({row},{col}) activated for mapping.")
            else: self.log_to_debug_console("Table activated, but no cell selected.")

    def handle_gui_navigation(self, gui_action_key: str, is_press: bool):
        # ... (unchanged, uses GUI_NAV_ACTION constants) ...
        if not is_press:
            if gui_action_key == GUI_NAV_CANCEL and self._combo_box_open: pass
            return
        focused_widget = QApplication.focusWidget()
        if self.controller_thread.is_listening_for_mapping:
            if gui_action_key == GUI_NAV_CANCEL: self.cancel_listening_manually()
            return
        if gui_action_key == GUI_NAV_CONFIRM: self.activate_widget(focused_widget)
        elif gui_action_key == GUI_NAV_CANCEL:
            if self._combo_box_open:
                self._combo_box_open.hidePopup(); self.set_current_focus_widget(self._combo_box_open); self._combo_box_open = None; self.log_to_debug_console("ComboBox popup cancelled.")
            else: self.log_to_debug_console("GUI Cancel received, no active context to cancel.")
        elif gui_action_key == GUI_NAV_UP:
            if self._combo_box_open: self.navigate_focus(False)
            elif focused_widget == self.mappings_table: new_row = max(0, self.mappings_table.currentRow() - 1); self.mappings_table.setCurrentCell(new_row, self.mappings_table.currentColumn())
            else: self.navigate_focus(False)
        elif gui_action_key == GUI_NAV_DOWN:
            if self._combo_box_open: self.navigate_focus(True)
            elif focused_widget == self.mappings_table: new_row = min(self.mappings_table.rowCount() - 1, self.mappings_table.currentRow() + 1);
            if new_row >=0 : self.mappings_table.setCurrentCell(new_row, self.mappings_table.currentColumn())
            else: self.navigate_focus(True)
        elif gui_action_key == GUI_NAV_LEFT:
            if focused_widget == self.mappings_table: new_col = max(0, self.mappings_table.currentColumn() - 1); self.mappings_table.setCurrentCell(self.mappings_table.currentRow(), new_col)
            elif not self._combo_box_open : self.navigate_focus(False)
        elif gui_action_key == GUI_NAV_RIGHT:
            if focused_widget == self.mappings_table: new_col = min(self.mappings_table.columnCount() - 1, self.mappings_table.currentColumn() + 1);
            if new_col >= 0: self.mappings_table.setCurrentCell(self.mappings_table.currentRow(), new_col)
            elif not self._combo_box_open : self.navigate_focus(True)

# Standalone execution part
if __name__ == "__main__":
    QApplication.setOrganizationName("YourAppNameOrOrg"); QApplication.setApplicationName("ControllerMapperStandalone")
    logger_cmg.info("ControllerSettingsWindow application starting (standalone)...")

    # --- Standalone Pygame Initialization (moved from GameConfigFallback) ---
    standalone_pygame_init_ok = False; standalone_joystick_init_ok = False
    try:
        pygame.init()
        standalone_pygame_init_ok = True
        logger_cmg.info("Standalone GUI: Pygame initialized by __main__.")
        try:
            pygame.joystick.init()
            standalone_joystick_init_ok = True
            logger_cmg.info(f"Standalone GUI: Pygame Joystick initialized by __main__. Count: {pygame.joystick.get_count()}")
        except pygame.error as e_joy:
            logger_cmg.critical(f"Standalone GUI: FAILED to initialize Pygame Joystick system: {e_joy}")
    except pygame.error as e_main:
        logger_cmg.critical(f"Standalone GUI: FAILED to initialize Pygame system: {e_main}")

    if not standalone_joystick_init_ok:
        _temp_app_for_msg_standalone = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Joystick Initialization Error",
                             "Failed to initialize Pygame Joystick system. Controller functionality will be severely limited or unavailable in standalone mode.")

    app = QApplication.instance() or QApplication(sys.argv)
    main_window_for_testing = QMainWindow()
    settings_widget = ControllerSettingsWindow(parent=None)
    main_window_for_testing.setCentralWidget(settings_widget)
    main_window_for_testing.setWindowTitle("Controller & Input Settings (Standalone Test)")

    main_window_ui_settings = QSettings(settings_widget.ui_settings_file_path, QSettings.Format.IniFormat)
    geom = main_window_ui_settings.value("main_window_geometry")
    if geom and isinstance(geom, QByteArray): main_window_for_testing.restoreGeometry(geom); logger_cmg.info("Restored main window geometry.")
    else: main_window_for_testing.setGeometry(100, 100, 1250, 800); logger_cmg.info(f"Using default main window geometry. Loaded geom: {geom}")
    main_window_for_testing.show()

    def on_main_window_close_standalone(eventQCloseEvent: QCloseEvent): # Added type hint
        logger_cmg.info("Main test window closing, saving geometry.")
        current_geometry = main_window_for_testing.saveGeometry()
        if current_geometry: main_window_ui_settings.setValue("main_window_geometry", current_geometry)
        else: logger_cmg.warning("Could not save main window geometry.")
        settings_widget.closeEvent(eventQCloseEvent)
        eventQCloseEvent.accept()
    main_window_for_testing.closeEvent = on_main_window_close_standalone
    exit_code = app.exec()

    if hasattr(settings_widget, 'controller_thread') and settings_widget.controller_thread.isRunning():
        logger_cmg.info("Main app exit: Ensuring controller thread is stopped.")
        settings_widget.deactivate_controller_monitoring()
    
    # --- Standalone Pygame Quit ---
    if standalone_pygame_init_ok: # Only quit if we init'd it
        if standalone_joystick_init_ok:
            try: pygame.joystick.quit()
            except Exception as e: logger_cmg.error(f"Error quitting pygame.joystick (standalone): {e}")
        try: pygame.quit()
        except Exception as e: logger_cmg.error(f"Error quitting pygame (standalone): {e}")
        logger_cmg.info("Standalone GUI: Pygame quit by __main__.")
    sys.exit(exit_code)