# controller_settings/controller_mapper_gui.py
import sys
import json
import threading
import time
import logging
import os
from typing import Dict, Optional, Any, List, Tuple
import copy

import pygame
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit,
    QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from pynput.keyboard import Controller as KeyboardController, Key # type: ignore

# Assuming config.py is in the parent directory
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"ControllerMapperGUI (Standalone): Added '{parent_dir}' to sys.path.")

try:
    import config as game_config
except ImportError:
    print("CRITICAL ERROR in controller_mapper_gui.py: Could not import 'config as game_config'. Using fallback.")
    class GameConfigFallback: # Simplified, ensure your actual config.py is robust
        GAME_ACTIONS = ["jump", "attack1", "left", "right", "up", "down", 
                        "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right",
                        "special1", "special2", "pause"]
        EXTERNAL_TO_INTERNAL_ACTION_MAP = {
            "JUMP_ACTION": "jump", "ATTACK_ACTION": "attack1", "MOVE_LEFT": "left", "MOVE_RIGHT": "right",
            "MOVE_UP": "up", "MOVE_DOWN": "down", 
            "CONFIRM": "menu_confirm", "CANCEL": "menu_cancel",
            "MENU_NAV_UP": "menu_up", "MENU_NAV_DOWN": "menu_down", 
            "MENU_NAV_LEFT": "menu_left", "MENU_NAV_RIGHT": "menu_right", "PAUSE_GAME": "pause"
        }
        AXIS_THRESHOLD_DEFAULT = 0.7
        MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = "controller_mappings_fallback.json"
        _pygame_initialized_globally = False; _joystick_initialized_globally = False
        LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}
        DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = True
        DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = True; DEFAULT_P2_CONTROLLER_ENABLED = True
        DEFAULT_P3_INPUT_DEVICE = "keyboard_p3"; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
        DEFAULT_P4_INPUT_DEVICE = "keyboard_p4"; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False
        CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
        CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
        CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED
        KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "keyboard_p3", "keyboard_p4", "unassigned_keyboard"]
        KEYBOARD_DEVICE_NAMES = ["Keyboard (P1 Layout)", "Keyboard (P2 Layout)", "Keyboard (P3 Layout)", "Keyboard (P4 Layout)", "Keyboard (Unassigned)"]
        DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = { # Must be in RUNTIME format
            "jump": {"type": "button", "id": 0}, "attack1": {"type": "button", "id": 2},
            "left": {"type": "axis", "id": 0, "value": -1, "threshold": 0.7},
            "right": {"type": "axis", "id": 0, "value": 1, "threshold": 0.7},
            "up": {"type": "axis", "id": 1, "value": -1, "threshold": 0.7},
            "down": {"type": "axis", "id": 1, "value": 1, "threshold": 0.7},
            "menu_confirm": {"type": "button", "id": 0}, "menu_cancel": {"type": "button", "id": 1},
            "pause": {"type": "button", "id": 7}
        }
        @staticmethod
        def init_pygame_and_joystick_globally():print("Fallback: Pygame Init")
        @staticmethod
        def get_available_joystick_names_with_indices() -> List[Tuple[str, str, Optional[str]]]: return []
        @staticmethod
        def save_config(): print("Fallback save_config called"); return False
        @staticmethod
        def load_config(): print("Fallback load_config called"); GameConfigFallback.LOADED_PYGAME_JOYSTICK_MAPPINGS = {}; GameConfigFallback.CURRENT_P1_INPUT_DEVICE = GameConfigFallback.DEFAULT_P1_INPUT_DEVICE; GameConfigFallback.P1_KEYBOARD_ENABLED = GameConfigFallback.DEFAULT_P1_KEYBOARD_ENABLED; GameConfigFallback.P1_CONTROLLER_ENABLED = GameConfigFallback.DEFAULT_P1_CONTROLLER_ENABLED; GameConfigFallback.CURRENT_P2_INPUT_DEVICE = GameConfigFallback.DEFAULT_P2_INPUT_DEVICE; GameConfigFallback.P2_KEYBOARD_ENABLED = GameConfigFallback.DEFAULT_P2_KEYBOARD_ENABLED; GameConfigFallback.P2_CONTROLLER_ENABLED = GameConfigFallback.DEFAULT_P2_CONTROLLER_ENABLED; GameConfigFallback.CURRENT_P3_INPUT_DEVICE = GameConfigFallback.DEFAULT_P3_INPUT_DEVICE; GameConfigFallback.P3_KEYBOARD_ENABLED = GameConfigFallback.DEFAULT_P3_KEYBOARD_ENABLED; GameConfigFallback.P3_CONTROLLER_ENABLED = GameConfigFallback.DEFAULT_P3_CONTROLLER_ENABLED; GameConfigFallback.CURRENT_P4_INPUT_DEVICE = GameConfigFallback.DEFAULT_P4_INPUT_DEVICE; GameConfigFallback.P4_KEYBOARD_ENABLED = GameConfigFallback.DEFAULT_P4_KEYBOARD_ENABLED; GameConfigFallback.P4_CONTROLLER_ENABLED = GameConfigFallback.DEFAULT_P4_CONTROLLER_ENABLED; return False
        @staticmethod
        def update_player_mappings_from_config(): print("Fallback update_player_mappings called")
        @staticmethod
        def translate_mapping_for_runtime(mapping_info: Dict[str, Any]) -> Optional[Dict[str, Any]]: return None
    game_config = GameConfigFallback()

logger_cmg = logging.getLogger("CM_GUI")
if not logger_cmg.hasHandlers():
    _cmg_handler = logging.StreamHandler(sys.stdout)
    _cmg_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _cmg_handler.setFormatter(_cmg_formatter)
    logger_cmg.addHandler(_cmg_handler)
    logger_cmg.setLevel(logging.INFO)
    logger_cmg.propagate = False

MAPPABLE_KEYS = game_config.GAME_ACTIONS
INTERNAL_TO_FRIENDLY_ACTION_DISPLAY = {v: k for k, v in game_config.EXTERNAL_TO_INTERNAL_ACTION_MAP.items() if v in game_config.GAME_ACTIONS}
for action in game_config.GAME_ACTIONS:
    if action not in INTERNAL_TO_FRIENDLY_ACTION_DISPLAY:
        INTERNAL_TO_FRIENDLY_ACTION_DISPLAY[action] = action.replace("_", " ").title()

MENU_SPECIFIC_ACTIONS = ["menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right", "pause"]
EXCLUSIVE_ACTIONS = ["pause", "menu_cancel"]
AXIS_THRESHOLD = game_config.AXIS_THRESHOLD_DEFAULT
MAPPINGS_FILE = game_config.MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH
logger_cmg.info(f"Mappings file path from game_config: {MAPPINGS_FILE}")

def get_pynput_key(key_str):
    if key_str == "SPACE": return Key.space;
    if key_str == "SHIFT": return Key.shift;    
    if key_str == "CTRL": return Key.ctrl
    if key_str == "ALT": return Key.alt;    
    if key_str == "up": return 'w'
    if key_str == "left": return 'a';    
    if key_str == "down": return 's'
    if key_str == "right": return 'd';    
    if key_str == "jump": return Key.space
    if key_str == "attack1": return 'v'
    if len(key_str) == 1 and key_str.isalnum(): return key_str.lower()
    return None

def _convert_runtime_default_to_gui_storage(action: str, runtime_map: Dict[str, Any], joy_idx_for_raw_str: int) -> Optional[Dict[str, Any]]:
    gui_storage_map: Dict[str, Any] = {}
    details: Dict[str, Any] = {"type": runtime_map.get("type")}
    raw_str_parts = [f"Joy{joy_idx_for_raw_str}"]
    map_type = runtime_map.get("type"); map_id = runtime_map.get("id")
    if map_type == "button":
        gui_storage_map["event_type"] = "button"; details["button_id"] = map_id
        raw_str_parts.append(f"Btn {map_id}")
    elif map_type == "axis":
        gui_storage_map["event_type"] = "axis"; details["axis_id"] = map_id
        details["direction"] = runtime_map.get("value"); details["threshold"] = runtime_map.get("threshold", AXIS_THRESHOLD)
        if details["direction"] is None: return None
        raw_str_parts.append(f"Axis {map_id} {'Pos' if details['direction'] == 1 else 'Neg'}")
    elif map_type == "hat":
        gui_storage_map["event_type"] = "hat"; details["hat_id"] = map_id
        details["value"] = list(runtime_map.get("value", (0,0)))
        raw_str_parts.append(f"Hat {map_id} {tuple(details['value'])}")
    else: return None
    gui_storage_map["details"] = details
    gui_storage_map["raw_str"] = " ".join(raw_str_parts)
    return gui_storage_map

class PygameControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerHotplug = Signal(str)
    def __init__(self):
        super().__init__()
        self.joystick: Optional[pygame.joystick.Joystick] = None; self.is_listening_for_mapping = False
        self.stop_flag = threading.Event(); self._translated_mappings_for_triggering: Dict[str, Any] = {}
        self.active_axis_keys: Dict[Tuple[int, int], str] = {}; self.active_hat_keys: Dict[Tuple[int, Tuple[int,int]], str] = {}
        self._last_joystick_count = -1; self.joystick_idx_to_monitor = -1; self.joystick_instance_id_to_monitor: Optional[int] = None
        logger_cmg.debug("PygameControllerThread initialized.")
    @property
    def translated_mappings_for_triggering(self) -> Dict[str, Any]: return self._translated_mappings_for_triggering
    @translated_mappings_for_triggering.setter
    def translated_mappings_for_triggering(self, new_mappings: Dict[str, Any]):
        self._translated_mappings_for_triggering = new_mappings; self.active_axis_keys.clear(); self.active_hat_keys.clear()
        # logger_cmg.debug(f"PygameControllerThread mappings updated. Count: {len(new_mappings)}") # Can be verbose
    def set_joystick_to_monitor(self, index: int):
        if self.joystick_idx_to_monitor != index:
            self.joystick_idx_to_monitor = index
            if self.joystick:
                try: self.joystick.quit()
                except pygame.error: pass
            self.joystick = None; self.joystick_instance_id_to_monitor = None
            self.active_axis_keys.clear(); self.active_hat_keys.clear()
            logger_cmg.info(f"PygameControllerThread set to monitor joystick index: {index}")
    def start_listening(self): self.is_listening_for_mapping = True
    def stop_listening(self): self.is_listening_for_mapping = False
    def stop(self): self.stop_flag.set()
    def run(self):
        logger_cmg.info("PygameControllerThread started.")
        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            logger_cmg.error("Pygame or Joystick system not globally initialized! Thread cannot run reliably.")
            self.controllerHotplug.emit("Error: Pygame Joystick system not ready."); return
        while not self.stop_flag.is_set():
            try:
                current_joystick_count = pygame.joystick.get_count()
                if self._last_joystick_count != current_joystick_count:
                    self.controllerHotplug.emit(f"Joystick count changed: {current_joystick_count}")
                    if self.joystick: self.joystick.quit()
                    self.joystick = None; self.joystick_instance_id_to_monitor = None
                if self.joystick is None:
                    if 0 <= self.joystick_idx_to_monitor < current_joystick_count:
                        try:
                            temp_joy = pygame.joystick.Joystick(self.joystick_idx_to_monitor); temp_joy.init()
                            self.joystick = temp_joy; self.joystick_instance_id_to_monitor = self.joystick.get_instance_id()
                            name = self.joystick.get_name()
                            self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} ({name}) ready for mapping/simulation.")
                        except pygame.error as e:
                            logger_cmg.error(f"Error initializing joystick {self.joystick_idx_to_monitor}: {e}")
                            self.joystick = None; self.joystick_instance_id_to_monitor = None
                            self.controllerHotplug.emit(f"Joystick {self.joystick_idx_to_monitor} init error. Retrying...")
                    else:
                        if self.joystick_idx_to_monitor != -1 : self.controllerHotplug.emit(f"Joystick {self.joystick_idx_to_monitor} unavailable (Count: {current_joystick_count}). Not monitoring.")
                        self.joystick = None; self.joystick_instance_id_to_monitor = None
                    self._last_joystick_count = current_joystick_count; time.sleep(0.5); continue
                if not self.joystick or not self.joystick.get_init():
                    logger_cmg.warning(f"Monitored joystick {self.joystick_idx_to_monitor} (Instance ID: {self.joystick_instance_id_to_monitor}) no longer initialized or lost.")
                    self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} lost.")
                    self.joystick = None; self.joystick_instance_id_to_monitor = None
                    self.active_axis_keys.clear(); self.active_hat_keys.clear(); time.sleep(0.5); continue
                for event in pygame.event.get():
                    if self.stop_flag.is_set(): break
                    if not hasattr(event, 'instance_id') or event.instance_id != self.joystick_instance_id_to_monitor: continue
                    event_details_for_gui: Optional[Dict[str, Any]] = None; raw_event_str_for_gui = ""
                    if event.type == pygame.JOYAXISMOTION:
                        axis_id = event.axis; value = event.value; raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Axis {axis_id}: {value:.2f}"
                        if self.is_listening_for_mapping:
                            if abs(value) > AXIS_THRESHOLD: event_details_for_gui = {"type": "axis", "axis_id": axis_id, "direction": 1 if value > 0 else -1, "threshold": AXIS_THRESHOLD}
                        else:
                            for (map_axis_id, map_direction), action_key in list(self.active_axis_keys.items()):
                                if map_axis_id == axis_id:
                                    current_thresh = self.translated_mappings_for_triggering.get(action_key, {}).get("threshold", AXIS_THRESHOLD) * 0.5
                                    if (map_direction == 1 and value < current_thresh) or (map_direction == -1 and value > -current_thresh) or (abs(value) < current_thresh):
                                        self.mappedEventTriggered.emit(action_key, False)
                                        if (map_axis_id, map_direction) in self.active_axis_keys: del self.active_axis_keys[(map_axis_id, map_direction)]
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "axis" and mapping_info.get("id") == axis_id:
                                    map_val_dir = mapping_info.get("value"); map_thresh = mapping_info.get("threshold", AXIS_THRESHOLD)
                                    is_active_now = (map_val_dir == 1 and value > map_thresh) or (map_val_dir == -1 and value < -map_thresh)
                                    if is_active_now and (axis_id, map_val_dir) not in self.active_axis_keys:
                                        self.mappedEventTriggered.emit(action_key, True); self.active_axis_keys[(axis_id, map_val_dir)] = action_key
                    elif event.type == pygame.JOYBUTTONDOWN:
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Down"
                        if self.is_listening_for_mapping: event_details_for_gui = {"type": "button", "button_id": event.button}
                        else:
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "button" and mapping_info.get("id") == event.button: self.mappedEventTriggered.emit(action_key, True); break
                    elif event.type == pygame.JOYBUTTONUP:
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Up"
                        if not self.is_listening_for_mapping:
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "button" and mapping_info.get("id") == event.button: self.mappedEventTriggered.emit(action_key, False); break
                    elif event.type == pygame.JOYHATMOTION:
                        hat_id = event.hat; hat_value_tuple = event.value; raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Hat {hat_id} {hat_value_tuple}"
                        if self.is_listening_for_mapping:
                            if hat_value_tuple != (0,0): event_details_for_gui = {"type": "hat", "hat_id": hat_id, "value": list(hat_value_tuple)}
                        else:
                            for (map_hat_id, map_hat_val), action_key in list(self.active_hat_keys.items()):
                                if map_hat_id == hat_id and map_hat_val != hat_value_tuple:
                                    self.mappedEventTriggered.emit(action_key, False)
                                    if (map_hat_id, map_hat_val) in self.active_hat_keys: del self.active_hat_keys[(map_hat_id, map_hat_val)]
                            if hat_value_tuple != (0,0):
                                for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                    if mapping_info.get("type") == "hat" and mapping_info.get("id") == hat_id and tuple(mapping_info.get("value",(9,9))) == hat_value_tuple:
                                        if (hat_id, hat_value_tuple) not in self.active_hat_keys:
                                            self.mappedEventTriggered.emit(action_key, True); self.active_hat_keys[(hat_id, hat_value_tuple)] = action_key; break
                    if self.is_listening_for_mapping and event_details_for_gui:
                        self.controllerEventCaptured.emit(event_details_for_gui, raw_event_str_for_gui); self.is_listening_for_mapping = False
                time.sleep(0.01)
            except pygame.error as e:
                logger_cmg.error(f"Pygame error in controller loop (joystick {self.joystick_idx_to_monitor}): {e}")
                self.controllerHotplug.emit(f"Pygame error with Joy {self.joystick_idx_to_monitor}. Re-scanning...")
                if self.joystick: self.joystick.quit()
                self.joystick = None; self.joystick_instance_id_to_monitor = None
                self.active_axis_keys.clear(); self.active_hat_keys.clear()
                try:
                    if pygame.joystick.get_init(): pygame.joystick.quit(); pygame.joystick.init()
                except pygame.error: pass
                time.sleep(1)
            except Exception: logger_cmg.exception("Unhandled exception in controller thread loop:"); time.sleep(1)
        if self.joystick:
            try: self.joystick.quit()
            except pygame.error: pass
        self.controllerHotplug.emit("Controller thread stopped."); logger_cmg.info("PygameControllerThread stopped.")

class ControllerSettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = KeyboardController(); self.currently_pressed_keys = set()
        self.all_joystick_mappings_by_guid: Dict[str, Dict[str, Any]] = {}
        self.current_translated_mappings_for_thread_sim: Dict[str, Any] = {}
        self.current_listening_key_for_joystick_map: Optional[str] = None
        self.last_selected_row_for_joystick_mapping = -1
        main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Initializing Input Settings...")
        main_layout.addWidget(self.status_label)
        config_area_group = QGroupBox("Player Input Configuration")
        self.config_grid_layout = QGridLayout(config_area_group)
        self.player_device_combos: List[QComboBox] = []
        self.player_kbd_enable_checks: List[QCheckBox] = []
        self.player_ctrl_enable_checks: List[QCheckBox] = []
        for i in range(4):
            player_num = i + 1; row_offset = i * 2
            self.config_grid_layout.addWidget(QLabel(f"<b>Player {player_num}:</b>"), row_offset, 0, 1, 4)
            self.config_grid_layout.addWidget(QLabel("Input Device:"), row_offset + 1, 0)
            device_combo = QComboBox(); self.player_device_combos.append(device_combo)
            self.config_grid_layout.addWidget(device_combo, row_offset + 1, 1)
            kbd_check = QCheckBox("Keyboard Enabled"); self.player_kbd_enable_checks.append(kbd_check)
            self.config_grid_layout.addWidget(kbd_check, row_offset + 1, 2)
            ctrl_check = QCheckBox("Controller Enabled"); self.player_ctrl_enable_checks.append(ctrl_check)
            self.config_grid_layout.addWidget(ctrl_check, row_offset + 1, 3)
        main_layout.addWidget(config_area_group)
        joystick_map_group = QGroupBox("Controller Button/Axis Mapping (for selected controller below)")
        joystick_map_layout = QVBoxLayout(joystick_map_group)
        mapping_controls_layout = QHBoxLayout()
        mapping_controls_layout.addWidget(QLabel("Monitor & Map Controller:"))
        self.joystick_select_combo_for_mapping = QComboBox()
        self.joystick_select_combo_for_mapping.currentIndexChanged.connect(self.on_monitor_joystick_changed)
        mapping_controls_layout.addWidget(self.joystick_select_combo_for_mapping, 1)
        joystick_map_layout.addLayout(mapping_controls_layout)
        table_controls_layout = QHBoxLayout()
        table_controls_layout.addWidget(QLabel("Action to Map (select then click button, or double-click in table):"))
        self.key_to_map_combo = QComboBox()
        for internal_key in MAPPABLE_KEYS:
            self.key_to_map_combo.addItem(INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key), userData=internal_key)
        table_controls_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Map Selected Action to Input")
        self.listen_button.clicked.connect(self.start_listening_for_joystick_map_from_button)
        table_controls_layout.addWidget(self.listen_button)
        joystick_map_layout.addLayout(table_controls_layout)
        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(8)
        self.mappings_table.setHorizontalHeaderLabels(["Action", "Input", "Rename", "Clear", "Action", "Input", "Rename", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for col_idx in [0, 4]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        for col_idx in [1, 5]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Stretch)
        for col_idx in [2, 3, 6, 7]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click)
        joystick_map_layout.addWidget(self.mappings_table)
        main_layout.addWidget(joystick_map_group)
        file_buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save All Settings"); save_button.clicked.connect(self.save_all_settings)
        file_buttons_layout.addWidget(save_button)
        self.reset_all_settings_button = QPushButton("Reset All Settings to Default")
        self.reset_all_settings_button.clicked.connect(self.confirm_reset_all_settings)
        file_buttons_layout.addWidget(self.reset_all_settings_button)
        main_layout.addLayout(file_buttons_layout)
        main_layout.addWidget(QLabel("Event Log:"))
        self.debug_console = QTextEdit(); self.debug_console.setReadOnly(True); self.debug_console.setFixedHeight(100)
        main_layout.addWidget(self.debug_console)
        self.controller_thread = PygameControllerThread()
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured_for_mapping)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered_for_simulation)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log_and_joystick_combos)
        self.controller_thread.start()
        self.load_settings_into_ui()
        logger_cmg.info("ControllerSettingsWindow initialized.")

    def log_to_debug_console(self, message: str):
        if hasattr(self, 'debug_console') and self.debug_console:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()

    def update_status_and_log(self, message: str):
        if hasattr(self, 'status_label') and self.status_label: self.status_label.setText(message)
        self.log_to_debug_console(message)
        level = logging.WARNING if "error" in message.lower() or "lost" in message.lower() else logging.INFO
        logger_cmg.log(level, f"Settings Status Update: {message}")

    def update_status_and_log_and_joystick_combos(self, message: str):
        self.update_status_and_log(message)
        self.populate_joystick_device_combos()

    def get_current_mapping_joystick_guid(self) -> Optional[str]:
        if self.joystick_select_combo_for_mapping.currentIndex() == -1: return None
        joy_data = self.joystick_select_combo_for_mapping.currentData()
        return joy_data.get("guid") if joy_data else None

    def get_joystick_display_name_by_guid(self, target_guid: str) -> str:
        for i in range(self.joystick_select_combo_for_mapping.count()):
            data = self.joystick_select_combo_for_mapping.itemData(i)
            if data and data.get("guid") == target_guid:
                return self.joystick_select_combo_for_mapping.itemText(i)
        return f"Controller (GUID: ...{target_guid[-6:]})" if target_guid else "Unknown Controller"

    def populate_joystick_device_combos(self):
        if not game_config._joystick_initialized_globally:
            logger_cmg.warning("Populate Combos: Pygame joystick not globally initialized.")
        available_joysticks_data = game_config.get_available_joystick_names_with_indices()
        # logger_cmg.debug(f"Populating joystick combos with: {available_joysticks_data}")
        current_player_device_ids = [combo.currentData() for combo in self.player_device_combos]
        prev_selected_mapping_guid = self.get_current_mapping_joystick_guid()
        all_combos_to_clear = self.player_device_combos + [self.joystick_select_combo_for_mapping]
        for combo in all_combos_to_clear:
            combo.blockSignals(True); combo.clear(); combo.blockSignals(False)
        for i, player_combo in enumerate(self.player_device_combos):
            player_combo.blockSignals(True)
            if hasattr(game_config, 'KEYBOARD_DEVICE_IDS') and hasattr(game_config, 'KEYBOARD_DEVICE_NAMES'):
                for k_idx, k_id in enumerate(game_config.KEYBOARD_DEVICE_IDS):
                    k_name = game_config.KEYBOARD_DEVICE_NAMES[k_idx] if k_idx < len(game_config.KEYBOARD_DEVICE_NAMES) else k_id
                    player_combo.addItem(k_name, k_id)
            else: player_combo.addItem(f"Keyboard (P{i+1} Default)", f"keyboard_p{i+1}")
            for joy_display_name, joy_guid_id, _ in available_joysticks_data:
                player_combo.addItem(joy_display_name, joy_guid_id)
            player_combo.blockSignals(False)
            idx = player_combo.findData(current_player_device_ids[i])
            player_combo.setCurrentIndex(idx if idx != -1 else 0)
        new_mapping_combo_selection_idx = -1
        self.joystick_select_combo_for_mapping.blockSignals(True)
        for i, (joy_display_name, _, joy_guid_str) in enumerate(available_joysticks_data):
            map_display_name = f"Joy {i}: {joy_display_name.split(': ', 1)[-1]}"
            self.joystick_select_combo_for_mapping.addItem(map_display_name, {"index": i, "guid": joy_guid_str, "name": map_display_name})
            if joy_guid_str == prev_selected_mapping_guid:
                new_mapping_combo_selection_idx = self.joystick_select_combo_for_mapping.count() - 1
        self.joystick_select_combo_for_mapping.blockSignals(False)
        if new_mapping_combo_selection_idx != -1:
            self.joystick_select_combo_for_mapping.setCurrentIndex(new_mapping_combo_selection_idx)
        elif self.joystick_select_combo_for_mapping.count() > 0:
            self.joystick_select_combo_for_mapping.setCurrentIndex(0)
        if self.joystick_select_combo_for_mapping.count() > 0 :
            self.on_monitor_joystick_changed(self.joystick_select_combo_for_mapping.currentIndex())
        else:
            self.controller_thread.set_joystick_to_monitor(-1)
            self.update_simulation_thread_mappings({})
            self.refresh_joystick_mappings_table(None)
            self.listen_button.setEnabled(False)

    def on_monitor_joystick_changed(self, index: int):
        if index == -1 or self.joystick_select_combo_for_mapping.count() == 0:
            self.controller_thread.set_joystick_to_monitor(-1)
            self.update_status_and_log("No controller selected for mapping/monitoring.")
            self.update_simulation_thread_mappings({})
            self.refresh_joystick_mappings_table(None)
            self.listen_button.setEnabled(False)
            return

        joy_data = self.joystick_select_combo_for_mapping.itemData(index)
        current_joy_text = self.joystick_select_combo_for_mapping.itemText(index)
        
        if joy_data and isinstance(joy_data, dict):
            joy_idx_to_monitor = joy_data.get("index")
            current_guid = joy_data.get("guid")

            if joy_idx_to_monitor is not None and current_guid:
                self.controller_thread.set_joystick_to_monitor(joy_idx_to_monitor)
                self.update_status_and_log(f"Monitoring '{current_joy_text}' for mapping and simulation.")
                self.listen_button.setEnabled(True)

                if current_guid not in self.all_joystick_mappings_by_guid:
                    source_guid_for_fallback = None
                    if self.all_joystick_mappings_by_guid:
                        for guid_iter, maps in self.all_joystick_mappings_by_guid.items():
                            if maps and guid_iter != current_guid: 
                                source_guid_for_fallback = guid_iter; break
                        if not source_guid_for_fallback and any(g != current_guid for g in self.all_joystick_mappings_by_guid):
                            source_guid_for_fallback = next(iter(g for g in self.all_joystick_mappings_by_guid if g != current_guid), None)
                    
                    if source_guid_for_fallback:
                        self.all_joystick_mappings_by_guid[current_guid] = copy.deepcopy(self.all_joystick_mappings_by_guid[source_guid_for_fallback])
                        source_name = self.get_joystick_display_name_by_guid(source_guid_for_fallback)
                        self.update_status_and_log(f"Applied fallback mappings from '{source_name}' to '{current_joy_text}'. Edit to make specific.")
                        logger_cmg.info(f"Fallback: Copied mappings from GUID {source_guid_for_fallback} to GUID {current_guid}")
                    else:
                        default_mappings_gui_format = {}
                        if hasattr(game_config, 'DEFAULT_GENERIC_JOYSTICK_MAPPINGS') and \
                           isinstance(game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS, dict): # type: ignore
                            for action, runtime_map in game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS.items(): # type: ignore
                                if action in MAPPABLE_KEYS:
                                    gui_map = _convert_runtime_default_to_gui_storage(action, runtime_map, joy_idx_to_monitor)
                                    if gui_map:
                                        default_mappings_gui_format[action] = gui_map
                        if default_mappings_gui_format:
                            self.all_joystick_mappings_by_guid[current_guid] = default_mappings_gui_format
                            self.update_status_and_log(f"Applied default generic mappings to '{current_joy_text}'. Edit to make specific.")
                            logger_cmg.info(f"Applied game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS to GUID {current_guid}")
                        else:
                            self.all_joystick_mappings_by_guid[current_guid] = {}
                            self.update_status_and_log(f"No specific, fallback, or generic default mappings for '{current_joy_text}'. Ready for new mapping.")
                            logger_cmg.info(f"No specific mappings for GUID {current_guid}. Initialized empty set.")
                
                current_mappings_for_selected_joy = self.all_joystick_mappings_by_guid.get(current_guid, {})
                self.update_simulation_thread_mappings(current_mappings_for_selected_joy)
                self.refresh_joystick_mappings_table(current_guid)
            else: 
                self.controller_thread.set_joystick_to_monitor(-1)
                self.update_status_and_log("Error: Invalid data for selected controller.")
                self.update_simulation_thread_mappings({})
                self.refresh_joystick_mappings_table(None)
                self.listen_button.setEnabled(False)
        else: 
            self.controller_thread.set_joystick_to_monitor(-1)
            self.listen_button.setEnabled(False)
            if self.joystick_select_combo_for_mapping.count() > 0 :
                 self.update_status_and_log("Please select a valid controller to map.")
            self.update_simulation_thread_mappings({})
            self.refresh_joystick_mappings_table(None)

    def update_simulation_thread_mappings(self, raw_gui_mappings_for_current_guid: Dict[str, Any]):
        self.current_translated_mappings_for_thread_sim.clear()
        for action_key, map_info in raw_gui_mappings_for_current_guid.items():
            if hasattr(game_config, 'translate_mapping_for_runtime'):
                translated = game_config.translate_mapping_for_runtime(map_info)
            else:
                details = map_info.get("details"); event_type = map_info.get("event_type")
                if not details: continue; translated = {}
                if event_type == "button": translated = {"type": "button", "id": details.get("button_id")}
                elif event_type == "axis": translated = {"type": "axis", "id": details.get("axis_id"), "value": details.get("direction"), "threshold": details.get("threshold", AXIS_THRESHOLD)}
                elif event_type == "hat": translated = {"type": "hat", "id": details.get("hat_id"), "value": tuple(details.get("value", (0,0)))}
            if translated:
                self.current_translated_mappings_for_thread_sim[action_key] = translated
        self.controller_thread.translated_mappings_for_triggering = self.current_translated_mappings_for_thread_sim

    def load_settings_into_ui(self):
        game_config.load_config()
        if isinstance(game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS, dict):
             self.all_joystick_mappings_by_guid = copy.deepcopy(game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS)
        else:
            logger_cmg.warning("LOADED_PYGAME_JOYSTICK_MAPPINGS is not Dict[str, Dict]. Initializing empty.")
            self.all_joystick_mappings_by_guid = {}
        self.populate_joystick_device_combos()
        for i in range(4):
            player_idx = i
            current_device_val = getattr(game_config, f"CURRENT_P{player_idx+1}_INPUT_DEVICE", getattr(game_config, f"DEFAULT_P{player_idx+1}_INPUT_DEVICE", "keyboard_p1"))
            kbd_enabled_val = getattr(game_config, f"P{player_idx+1}_KEYBOARD_ENABLED", getattr(game_config, f"DEFAULT_P{player_idx+1}_KEYBOARD_ENABLED", False))
            ctrl_enabled_val = getattr(game_config, f"P{player_idx+1}_CONTROLLER_ENABLED", getattr(game_config, f"DEFAULT_P{player_idx+1}_CONTROLLER_ENABLED", False))
            combo = self.player_device_combos[player_idx]
            idx = combo.findData(current_device_val)
            combo.setCurrentIndex(idx if idx != -1 else 0)
            self.player_kbd_enable_checks[player_idx].setChecked(kbd_enabled_val)
            self.player_ctrl_enable_checks[player_idx].setChecked(ctrl_enabled_val)
        self.update_status_and_log("Settings loaded into UI.")

    def save_all_settings(self):
        for i in range(4):
            player_idx = i
            setattr(game_config, f"CURRENT_P{player_idx+1}_INPUT_DEVICE", self.player_device_combos[player_idx].currentData())
            setattr(game_config, f"P{player_idx+1}_KEYBOARD_ENABLED", self.player_kbd_enable_checks[player_idx].isChecked())
            setattr(game_config, f"P{player_idx+1}_CONTROLLER_ENABLED", self.player_ctrl_enable_checks[player_idx].isChecked())
        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS = copy.deepcopy(self.all_joystick_mappings_by_guid)
        if game_config.save_config():
            self.update_status_and_log("All settings saved.")
        else:
            QMessageBox.critical(self, "Save Error", "Could not save settings.")
            self.update_status_and_log("Error saving settings.")

    def confirm_reset_all_settings(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Reset all input settings to default values (including all controller mappings)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.perform_reset_all_settings()

    def perform_reset_all_settings(self):
        for i in range(4):
            player_idx = i
            default_device = getattr(game_config, f"DEFAULT_P{player_idx+1}_INPUT_DEVICE", f"keyboard_p{player_idx+1}")
            default_kbd_enabled = getattr(game_config, f"DEFAULT_P{player_idx+1}_KEYBOARD_ENABLED", False)
            default_ctrl_enabled = getattr(game_config, f"DEFAULT_P{player_idx+1}_CONTROLLER_ENABLED", False)
            setattr(game_config, f"CURRENT_P{player_idx+1}_INPUT_DEVICE", default_device)
            setattr(game_config, f"P{player_idx+1}_KEYBOARD_ENABLED", default_kbd_enabled)
            setattr(game_config, f"P{player_idx+1}_CONTROLLER_ENABLED", default_ctrl_enabled)
        self.all_joystick_mappings_by_guid.clear()
        if hasattr(game_config, 'LOADED_PYGAME_JOYSTICK_MAPPINGS'):
            game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.clear()
        self.load_settings_into_ui()
        self.update_status_and_log("All settings reset to default. Save to make changes permanent.")

    def start_listening_for_joystick_map_from_button(self):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid: self.update_status_and_log("Error: No controller selected to map to."); return
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map: self.update_status_and_log("Error: No action selected to map."); return
        self.initiate_listening_sequence_for_joystick_map(internal_key_to_map)

    def initiate_listening_sequence_for_joystick_map(self, internal_key_to_map_str, originating_row_idx_in_table=-1):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or self.controller_thread.joystick_idx_to_monitor == -1:
            self.update_status_and_log("Cannot listen: No controller selected or controller not ready."); return
        self.current_listening_key_for_joystick_map = internal_key_to_map_str
        self.last_selected_row_for_joystick_mapping = originating_row_idx_in_table
        self.controller_thread.start_listening()
        friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key_to_map_str, internal_key_to_map_str)
        monitor_joy_text = self.joystick_select_combo_for_mapping.currentText()
        self.update_status_and_log(f"Listening for '{friendly_name}' on {monitor_joy_text}...")
        self.listen_button.setText("Listening..."); self.listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(False); self.joystick_select_combo_for_mapping.setEnabled(False)

    def on_controller_event_captured_for_mapping(self, event_details_from_thread: dict, raw_event_str: str):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        action_being_mapped = self.current_listening_key_for_joystick_map
        if not action_being_mapped or not current_mapping_guid:
            self.reset_listening_ui_for_joystick_map(); return
        if current_mapping_guid not in self.all_joystick_mappings_by_guid:
            self.all_joystick_mappings_by_guid[current_mapping_guid] = {}
        current_controller_mappings = self.all_joystick_mappings_by_guid[current_mapping_guid]
        perform_conflict_check = action_being_mapped not in MENU_SPECIFIC_ACTIONS
        if perform_conflict_check:
            for existing_key, mapping_info in list(current_controller_mappings.items()):
                if existing_key in MENU_SPECIFIC_ACTIONS: continue
                if mapping_info and mapping_info.get("raw_str") == raw_event_str and existing_key != action_being_mapped:
                    reply = QMessageBox.question(self, "Conflict",
                                                 f"Input '{raw_event_str}' is already mapped to game action '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(existing_key, existing_key)}' on this controller. Overwrite?",
                                                 QMessageBox.Yes | QMessageBox.No)
                    if reply == QMessageBox.No:
                        self.reset_listening_ui_for_joystick_map(); return
                    del current_controller_mappings[existing_key]; break
        current_controller_mappings[action_being_mapped] = {
            "event_type": event_details_from_thread["type"], "details": event_details_from_thread, "raw_str": raw_event_str
        }
        action_friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(action_being_mapped, action_being_mapped)
        self.log_to_debug_console(f"Mapped '{raw_event_str}' to '{action_friendly_name}' for current controller.")
        self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=action_being_mapped)
        self.update_simulation_thread_mappings(current_controller_mappings)
        self.reset_listening_ui_for_joystick_map(preserve_scroll=True)

    def reset_listening_ui_for_joystick_map(self, preserve_scroll=False):
        self.listen_button.setText("Map Selected Action to Input")
        self.listen_button.setEnabled(self.joystick_select_combo_for_mapping.currentIndex() != -1)
        self.key_to_map_combo.setEnabled(True); self.joystick_select_combo_for_mapping.setEnabled(True)
        self.controller_thread.stop_listening()
        if not preserve_scroll: self.last_selected_row_for_joystick_mapping = -1

    def on_mapped_event_triggered_for_simulation(self, internal_action_key_str, is_press_event):
        action_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_action_key_str, internal_action_key_str)
        should_simulate_pynput = True
        if internal_action_key_str in EXCLUSIVE_ACTIONS and not is_press_event:
            should_simulate_pynput = False
        log_msg = f"Simulated Event: '{action_display_name}' {'Pressed' if is_press_event else 'Released'}"
        if should_simulate_pynput:
            pynput_key_to_simulate = get_pynput_key(internal_action_key_str)
            if pynput_key_to_simulate:
                try:
                    if is_press_event:
                        if pynput_key_to_simulate not in self.currently_pressed_keys:
                            self.keyboard.press(pynput_key_to_simulate); self.currently_pressed_keys.add(pynput_key_to_simulate)
                            log_msg += f" (Keyboard Sim: {str(pynput_key_to_simulate)} Press)"
                    else:
                        if pynput_key_to_simulate in self.currently_pressed_keys:
                            self.keyboard.release(pynput_key_to_simulate); self.currently_pressed_keys.remove(pynput_key_to_simulate)
                            log_msg += f" (Keyboard Sim: {str(pynput_key_to_simulate)} Release)"
                except Exception as e:
                    logger_cmg.error(f"Pynput error for '{action_display_name}': {e}"); log_msg += " (Pynput Error)"
        self.log_to_debug_console(log_msg)

    def refresh_joystick_mappings_table(self, current_controller_guid: Optional[str], preserve_scroll=False, target_row_action_key: Optional[str] = None):
        current_v_scroll_value = self.mappings_table.verticalScrollBar().value() if preserve_scroll else -1
        self.mappings_table.setRowCount(0)
        if not current_controller_guid: return
        mappings_to_display = self.all_joystick_mappings_by_guid.get(current_controller_guid, {})
        num_actions = len(MAPPABLE_KEYS); num_rows_needed = (num_actions + 1) // 2
        self.mappings_table.setRowCount(num_rows_needed)
        target_table_row_to_ensure_visible = -1
        for i in range(num_rows_needed):
            for col_group in range(2):
                action_idx = i * 2 + col_group
                if action_idx >= num_actions: continue
                internal_key = MAPPABLE_KEYS[action_idx]
                friendly_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key)
                if target_row_action_key and internal_key == target_row_action_key: target_table_row_to_ensure_visible = i
                base_col = col_group * 4
                action_item = QTableWidgetItem(friendly_display_name); action_item.setData(Qt.UserRole, internal_key)
                self.mappings_table.setItem(i, base_col + 0, action_item)
                mapping_info = mappings_to_display.get(internal_key)
                if mapping_info:
                    self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem(mapping_info.get("raw_str", "N/A")))
                    rename_btn = QPushButton("Rename"); rename_btn.setProperty("internal_key", internal_key)
                    rename_btn.clicked.connect(lambda checked=False, k=internal_key: self.rename_joystick_mapping_friendly_name_prompt(k))
                    self.mappings_table.setCellWidget(i, base_col + 2, rename_btn)
                    clear_btn = QPushButton("Clear"); clear_btn.setProperty("internal_key", internal_key)
                    clear_btn.clicked.connect(lambda checked=False, k=internal_key: self.clear_joystick_mapping(k))
                    self.mappings_table.setCellWidget(i, base_col + 3, clear_btn)
                else:
                    self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem("Not Mapped"))
                    ph_rename = QPushButton("---"); ph_rename.setEnabled(False); ph_clear = QPushButton("---"); ph_clear.setEnabled(False)
                    self.mappings_table.setCellWidget(i, base_col + 2, ph_rename); self.mappings_table.setCellWidget(i, base_col + 3, ph_clear)
        if target_table_row_to_ensure_visible != -1: self.mappings_table.scrollToItem(self.mappings_table.item(target_table_row_to_ensure_visible, 0), QAbstractItemView.PositionAtCenter)
        elif preserve_scroll and current_v_scroll_value != -1: self.mappings_table.verticalScrollBar().setValue(current_v_scroll_value)
        if self.current_listening_key_for_joystick_map == target_row_action_key : self.current_listening_key_for_joystick_map = None

    def handle_table_double_click(self, row, column):
        col_group = 0 if column < 4 else 1; item_column_index = col_group * 4 + 0
        action_item = self.mappings_table.item(row, item_column_index)
        if not action_item: return
        internal_key_clicked = action_item.data(Qt.UserRole)
        if not internal_key_clicked: return
        relevant_column_in_group = column % 4
        if relevant_column_in_group <= 1: self.initiate_listening_sequence_for_joystick_map(internal_key_clicked, originating_row_idx_in_table=row)

    def rename_joystick_mapping_friendly_name_prompt(self, internal_key: str):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or internal_key not in self.all_joystick_mappings_by_guid.get(current_mapping_guid, {}): return
        mapping_info = self.all_joystick_mappings_by_guid[current_mapping_guid][internal_key]
        current_label = mapping_info.get("raw_str", "")
        text, ok = QInputDialog.getText(self, "Rename Input Label", f"Label for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key,internal_key)}':", QLineEdit.Normal, current_label)
        if ok and text:
            mapping_info["raw_str"] = text
            self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=internal_key)
            self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid[current_mapping_guid])

    def clear_joystick_mapping(self, internal_key: str):
        current_mapping_guid = self.get_current_mapping_joystick_guid()
        if not current_mapping_guid or internal_key not in self.all_joystick_mappings_by_guid.get(current_mapping_guid, {}): return
        del self.all_joystick_mappings_by_guid[current_mapping_guid][internal_key]
        self.refresh_joystick_mappings_table(current_mapping_guid, preserve_scroll=True, target_row_action_key=internal_key)
        self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid[current_mapping_guid])
        self.log_to_debug_console(f"Cleared joystick mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key)}' on current controller.")

    def closeEvent(self, event):
        logger_cmg.info("ControllerSettingsWindow closeEvent. Shutting down thread.")
        if hasattr(self, 'controller_thread') and self.controller_thread.isRunning():
            self.controller_thread.stop(); self.controller_thread.wait(750)
        super().closeEvent(event)

if __name__ == "__main__":
    logger_cmg.info("ControllerSettingsWindow application starting (standalone)...")
    if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
        print("Standalone GUI: Pygame/Joystick not globally initialized. Attempting init now.")
        game_config.init_pygame_and_joystick_globally()
        if not game_config._joystick_initialized_globally:
            QMessageBox.critical(None, "Init Error", "Failed to initialize Pygame Joystick system. Controller functionality will be limited.")
            logger_cmg.critical("Standalone GUI: FAILED to initialize Pygame Joystick system.")
    app = QApplication(sys.argv)
    try: game_config.load_config()
    except Exception as e: logger_cmg.error(f"Standalone GUI: Error loading game_config: {e}")
    main_window_for_testing = QMainWindow()
    settings_widget = ControllerSettingsWindow()
    main_window_for_testing.setCentralWidget(settings_widget)
    main_window_for_testing.setWindowTitle("Controller & Input Settings (Up to 4 Players)")
    main_window_for_testing.setGeometry(100, 100, 1050, 850)
    main_window_for_testing.show()
    exit_code = app.exec()
    if hasattr(settings_widget, 'controller_thread') and settings_widget.controller_thread.isRunning():
        settings_widget.controller_thread.stop(); settings_widget.controller_thread.wait(500)
    if game_config._pygame_initialized_globally:
        if game_config._joystick_initialized_globally: pygame.joystick.quit()
        pygame.quit()
        logger_cmg.info("Standalone GUI: Pygame quit.")
    sys.exit(exit_code)