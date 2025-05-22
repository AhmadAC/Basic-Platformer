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
if __name__ == "__main__": # Ensure this block only runs if script is executed directly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"ControllerMapperGUI (Standalone): Added '{parent_dir}' to sys.path.")

try:
    import config as game_config
except ImportError:
    print("CRITICAL ERROR in controller_mapper_gui.py: Could not import 'config as game_config'. Using fallback.")
    # Fallback game_config class
    class GameConfigFallback:
        GAME_ACTIONS = ["jump", "attack1", "left", "right", "up", "down", "menu_confirm", "menu_cancel", "pause"]
        EXTERNAL_TO_INTERNAL_ACTION_MAP = {"JUMP": "jump", "ATTACK": "attack1", "LEFT": "left", "RIGHT": "right", "UP": "up", "DOWN": "down", "CONFIRM": "menu_confirm", "CANCEL": "menu_cancel", "PAUSE": "pause"}
        AXIS_THRESHOLD_DEFAULT = 0.7
        MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = "controller_mappings_fallback.json"
        _pygame_initialized_globally = False; _joystick_initialized_globally = False
        LOADED_PYGAME_JOYSTICK_MAPPINGS: Dict[str, Dict[str, Any]] = {}
        DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"; DEFAULT_P1_KEYBOARD_ENABLED = True; DEFAULT_P1_CONTROLLER_ENABLED = False
        DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"; DEFAULT_P2_KEYBOARD_ENABLED = False; DEFAULT_P2_CONTROLLER_ENABLED = False
        DEFAULT_P3_INPUT_DEVICE = "unassigned"; DEFAULT_P3_KEYBOARD_ENABLED = False; DEFAULT_P3_CONTROLLER_ENABLED = False
        DEFAULT_P4_INPUT_DEVICE = "unassigned"; DEFAULT_P4_KEYBOARD_ENABLED = False; DEFAULT_P4_CONTROLLER_ENABLED = False
        CURRENT_P1_INPUT_DEVICE = DEFAULT_P1_INPUT_DEVICE; P1_KEYBOARD_ENABLED = DEFAULT_P1_KEYBOARD_ENABLED; P1_CONTROLLER_ENABLED = DEFAULT_P1_CONTROLLER_ENABLED
        CURRENT_P2_INPUT_DEVICE = DEFAULT_P2_INPUT_DEVICE; P2_KEYBOARD_ENABLED = DEFAULT_P2_KEYBOARD_ENABLED; P2_CONTROLLER_ENABLED = DEFAULT_P2_CONTROLLER_ENABLED
        CURRENT_P3_INPUT_DEVICE = DEFAULT_P3_INPUT_DEVICE; P3_KEYBOARD_ENABLED = DEFAULT_P3_KEYBOARD_ENABLED; P3_CONTROLLER_ENABLED = DEFAULT_P3_CONTROLLER_ENABLED
        CURRENT_P4_INPUT_DEVICE = DEFAULT_P4_INPUT_DEVICE; P4_KEYBOARD_ENABLED = DEFAULT_P4_KEYBOARD_ENABLED; P4_CONTROLLER_ENABLED = DEFAULT_P4_CONTROLLER_ENABLED
        KEYBOARD_DEVICE_IDS = ["keyboard_p1", "keyboard_p2", "unassigned_keyboard"]
        KEYBOARD_DEVICE_NAMES = ["Keyboard (P1)", "Keyboard (P2)", "Keyboard (Unassigned)"]
        DEFAULT_GENERIC_JOYSTICK_MAPPINGS: Dict[str, Any] = {"jump": {"type": "button", "id": 0}} # Simplified
        UNASSIGNED_DEVICE_ID = "unassigned" # Added for fallback
        UNASSIGNED_DEVICE_NAME = "Unassigned" # Added for fallback

        @staticmethod
        def init_pygame_and_joystick_globally(force_rescan=False): print("Fallback: Pygame Init")
        @staticmethod
        def get_available_joystick_names_with_indices_and_guids() -> List[Tuple[str, str, Optional[str], int]]: return []
        @staticmethod
        def get_joystick_objects() -> List[Any]: return []
        @staticmethod
        def save_config(): print("Fallback save_config called"); return False
        @staticmethod
        def load_config(): print("Fallback load_config called"); GameConfigFallback.LOADED_PYGAME_JOYSTICK_MAPPINGS = {}; # ... (rest of defaults)
        @staticmethod
        def update_player_mappings_from_config(): print("Fallback update_player_mappings called")
        @staticmethod
        def translate_mapping_for_runtime(mapping_info: Dict[str, Any]) -> Optional[Dict[str, Any]]: return None
    game_config = GameConfigFallback()

# --- Logger Setup ---
logger_cmg = logging.getLogger("CM_GUI")
if not logger_cmg.hasHandlers():
    _cmg_handler = logging.StreamHandler(sys.stdout)
    _cmg_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _cmg_handler.setFormatter(_cmg_formatter)
    logger_cmg.addHandler(_cmg_handler)
    logger_cmg.setLevel(logging.INFO)
    logger_cmg.propagate = False

# --- Constants and Mappings ---
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
UNASSIGNED_DEVICE_ID = getattr(game_config, "UNASSIGNED_DEVICE_ID", "unassigned")
UNASSIGNED_DEVICE_NAME = getattr(game_config, "UNASSIGNED_DEVICE_NAME", "Unassigned")


# --- Helper Functions ---
def get_pynput_key(key_str: str) -> Optional[Any]:
    key_map = {
        "SPACE": Key.space, "SHIFT": Key.shift, "CTRL": Key.ctrl, "ALT": Key.alt,
        "ENTER": Key.enter, "TAB": Key.tab, "ESC": Key.esc,
        "UP_ARROW": Key.up, "DOWN_ARROW": Key.down, "LEFT_ARROW": Key.left, "RIGHT_ARROW": Key.right,
        "up": 'w', "left": 'a', "down": 's', "right": 'd', "jump": Key.space, "attack1": 'v',
    }
    if key_str in key_map: return key_map[key_str]
    if len(key_str) == 1 and key_str.isalnum(): return key_str.lower()
    try:
        if key_str.lower().startswith('f') and key_str[1:].isdigit(): return getattr(Key, key_str.lower())
    except AttributeError: pass
    logger_cmg.warning(f"Pynput key for '{key_str}' not found.")
    return None

def _convert_runtime_default_to_gui_storage(action: str, runtime_map: Dict[str, Any], joy_idx_for_raw_str: int) -> Optional[Dict[str, Any]]:
    gui_storage_map: Dict[str, Any] = {}
    details: Dict[str, Any] = {"type": runtime_map.get("type")}
    raw_str_parts = [f"Joy{joy_idx_for_raw_str}"]
    map_type, map_id = runtime_map.get("type"), runtime_map.get("id")

    if map_type == "button":
        gui_storage_map["event_type"] = "button"; details["button_id"] = map_id; raw_str_parts.append(f"Btn {map_id}")
    elif map_type == "axis":
        gui_storage_map["event_type"] = "axis"; details["axis_id"] = map_id
        details["direction"] = runtime_map.get("value"); details["threshold"] = runtime_map.get("threshold", AXIS_THRESHOLD)
        if details["direction"] is None: logger_cmg.warning(f"Axis map for '{action}' missing direction."); return None
        raw_str_parts.append(f"Axis {map_id} {'Pos' if details['direction'] == 1 else 'Neg'}")
    elif map_type == "hat":
        gui_storage_map["event_type"] = "hat"; details["hat_id"] = map_id
        details["value"] = list(runtime_map.get("value", (0,0)))
        raw_str_parts.append(f"Hat {map_id} {tuple(details['value'])}")
    else: logger_cmg.warning(f"Unknown map type '{map_type}' for '{action}'."); return None
        
    gui_storage_map["details"] = details; gui_storage_map["raw_str"] = " ".join(raw_str_parts)
    return gui_storage_map

# --- PygameControllerThread ---
class PygameControllerThread(QThread): # (Contents mostly unchanged from your provided version)
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerHotplug = Signal(str)

    def __init__(self):
        super().__init__()
        self.joystick: Optional[pygame.joystick.Joystick] = None
        self.is_listening_for_mapping = False
        self.stop_flag = threading.Event()
        self._translated_mappings_for_triggering: Dict[str, Any] = {}
        self.active_axis_keys: Dict[Tuple[int, int], str] = {}
        self.active_hat_keys: Dict[Tuple[int, Tuple[int,int]], str] = {}
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
            logger_cmg.info(f"PygameControllerThread: Monitor change from idx {self.joystick_idx_to_monitor} to {pygame_index}")
            self.joystick_idx_to_monitor = pygame_index
            if self.joystick:
                try: self.joystick.quit()
                except pygame.error: pass
            self.joystick = None; self.joystick_instance_id_to_monitor = None
            self.active_axis_keys.clear(); self.active_hat_keys.clear()
            if 0 <= self.joystick_idx_to_monitor < pygame.joystick.get_count():
                try:
                    self.joystick = pygame.joystick.Joystick(self.joystick_idx_to_monitor)
                    self.joystick.init()
                    self.joystick_instance_id_to_monitor = self.joystick.get_instance_id()
                    logger_cmg.info(f"PygameControllerThread: Monitoring '{self.joystick.get_name()}' (Idx:{pygame_index}, InstID:{self.joystick_instance_id_to_monitor}).")
                except pygame.error as e:
                    logger_cmg.error(f"PygameControllerThread: Error init joystick idx {pygame_index}: {e}")
                    self.joystick = None
            elif self.joystick_idx_to_monitor != -1:
                 logger_cmg.warning(f"PygameControllerThread: Invalid joystick index {pygame_index} for monitoring.")

    def start_listening(self): self.is_listening_for_mapping = True
    def stop_listening(self): self.is_listening_for_mapping = False
    def stop(self): self.stop_flag.set()

    def run(self): # (Logic for run is mostly the same, ensure stop_flag is respected)
        logger_cmg.info("PygameControllerThread started running.")
        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            logger_cmg.error("Pygame/Joystick system not globally initialized! Thread cannot run."); return

        while not self.stop_flag.is_set():
            try:
                pygame.event.pump()
                current_joystick_count = pygame.joystick.get_count()
                if self._last_joystick_count != current_joystick_count:
                    self.controllerHotplug.emit(f"Joystick count changed: {current_joystick_count}")
                    logger_cmg.info(f"Joystick count changed: {self._last_joystick_count} -> {current_joystick_count}.")
                    if self.joystick: self.joystick.quit()
                    self.joystick = None; self.joystick_instance_id_to_monitor = None
                    self._last_joystick_count = current_joystick_count
                    if 0 <= self.joystick_idx_to_monitor < current_joystick_count:
                        self.set_joystick_to_monitor(self.joystick_idx_to_monitor)
                    else: self.set_joystick_to_monitor(-1)

                if self.joystick is None or not self.joystick.get_init():
                    if self.joystick_idx_to_monitor != -1 and 0 <= self.joystick_idx_to_monitor < current_joystick_count:
                        # logger_cmg.warning(f"Re-init joystick index {self.joystick_idx_to_monitor}")
                        self.set_joystick_to_monitor(self.joystick_idx_to_monitor)
                    else: # No valid joystick or index is -1
                        if self.joystick: self.joystick.quit(); self.joystick = None
                    time.sleep(0.1); continue

                for event in pygame.event.get():
                    if self.stop_flag.is_set(): break
                    if not hasattr(event, 'instance_id') or event.instance_id != self.joystick_instance_id_to_monitor: continue
                    
                    event_details: Optional[Dict[str, Any]] = None; raw_str = ""
                    if event.type == pygame.JOYAXISMOTION:
                        axis, value = event.axis, event.value; raw_str = f"Joy{self.joystick_idx_to_monitor} Axis {axis}: {value:.2f}"
                        if self.is_listening_for_mapping and abs(value) > AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis, "direction": 1 if value > 0 else -1, "threshold": AXIS_THRESHOLD}
                        elif not self.is_listening_for_mapping: # Simulate
                            for (ax_id, direction), act_key in list(self.active_axis_keys.items()):
                                if ax_id == axis:
                                    thresh = self.translated_mappings_for_triggering.get(act_key, {}).get("threshold", AXIS_THRESHOLD) * 0.5
                                    if (direction == 1 and value < thresh) or (direction == -1 and value > -thresh) or (abs(value) < thresh):
                                        self.mappedEventTriggered.emit(act_key, False); self.active_axis_keys.pop((ax_id, direction), None)
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type")=="axis" and map_info.get("id")==axis:
                                    active = (map_info["value"]==1 and value > map_info["threshold"]) or \
                                             (map_info["value"]==-1 and value < -map_info["threshold"])
                                    if active and (axis, map_info["value"]) not in self.active_axis_keys:
                                        self.mappedEventTriggered.emit(act_key, True); self.active_axis_keys[(axis, map_info["value"])] = act_key
                    elif event.type == pygame.JOYBUTTONDOWN:
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Down"
                        if self.is_listening_for_mapping: event_details = {"type": "button", "button_id": event.button}
                        else:
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type")=="button" and map_info.get("id")==event.button: self.mappedEventTriggered.emit(act_key,True); break
                    elif event.type == pygame.JOYBUTTONUP:
                        raw_str = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Up"
                        if not self.is_listening_for_mapping:
                            for act_key, map_info in self.translated_mappings_for_triggering.items():
                                if map_info.get("type")=="button" and map_info.get("id")==event.button: self.mappedEventTriggered.emit(act_key,False); break
                    elif event.type == pygame.JOYHATMOTION:
                        hat, value_tuple = event.hat, event.value; raw_str = f"Joy{self.joystick_idx_to_monitor} Hat {hat} {value_tuple}"
                        if self.is_listening_for_mapping and value_tuple != (0,0): event_details = {"type": "hat", "hat_id": hat, "value": list(value_tuple)}
                        elif not self.is_listening_for_mapping: # Simulate
                            for (h_id, h_val), act_key in list(self.active_hat_keys.items()):
                                if h_id == hat and h_val != value_tuple:
                                    self.mappedEventTriggered.emit(act_key, False); self.active_hat_keys.pop((h_id, h_val), None)
                            if value_tuple != (0,0):
                                for act_key, map_info in self.translated_mappings_for_triggering.items():
                                    if map_info.get("type")=="hat" and map_info.get("id")==hat and tuple(map_info.get("value",(9,9)))==value_tuple:
                                        if (hat, value_tuple) not in self.active_hat_keys:
                                            self.mappedEventTriggered.emit(act_key, True); self.active_hat_keys[(hat, value_tuple)] = act_key
                                        break
                    if self.is_listening_for_mapping and event_details:
                        self.controllerEventCaptured.emit(event_details, raw_str); self.is_listening_for_mapping = False
                time.sleep(0.01)
            except pygame.error as e: logger_cmg.error(f"Pygame error in controller loop (joy {self.joystick_idx_to_monitor}): {e}"); self.controllerHotplug.emit(f"Pygame error Joy {self.joystick_idx_to_monitor}"); time.sleep(0.5) # Basic retry logic implied by loop
            except Exception as e_unhandled: logger_cmg.exception(f"Unhandled exception in controller thread (joy {self.joystick_idx_to_monitor}): {e_unhandled}"); time.sleep(0.5)
        if self.joystick:
            try: self.joystick.quit()
            except pygame.error: pass
        self.controllerHotplug.emit("Controller thread stopped.")
        logger_cmg.info("PygameControllerThread finished running.")


# --- ControllerSettingsWindow ---
class ControllerSettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = KeyboardController()
        self.currently_pressed_keys = set()
        self.all_joystick_mappings_by_guid: Dict[str, Dict[str, Any]] = {}
        self.current_translated_mappings_for_thread_sim: Dict[str, Any] = {}
        self.current_listening_key_for_joystick_map: Optional[str] = None
        self.last_selected_row_for_joystick_mapping = -1

        main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Initializing...")
        main_layout.addWidget(self.status_label)

        config_area_group = QGroupBox("Player Input Configuration")
        self.config_grid_layout = QGridLayout(config_area_group)
        self.player_device_combos: List[QComboBox] = []
        self.player_kbd_enable_checks: List[QCheckBox] = []
        self.player_ctrl_enable_checks: List[QCheckBox] = []

        for i in range(4): # P1 to P4
            player_num = i + 1; row_offset = i * 2 
            self.config_grid_layout.addWidget(QLabel(f"<b>Player {player_num}:</b>"), row_offset, 0, 1, 4)
            self.config_grid_layout.addWidget(QLabel("Input Device:"), row_offset + 1, 0)
            dev_combo = QComboBox(); self.player_device_combos.append(dev_combo)
            self.config_grid_layout.addWidget(dev_combo, row_offset + 1, 1)
            kbd_chk = QCheckBox("Keyboard"); self.player_kbd_enable_checks.append(kbd_chk)
            self.config_grid_layout.addWidget(kbd_chk, row_offset + 1, 2)
            ctrl_chk = QCheckBox("Controller"); self.player_ctrl_enable_checks.append(ctrl_chk)
            self.config_grid_layout.addWidget(ctrl_chk, row_offset + 1, 3)
        main_layout.addWidget(config_area_group)

        joy_map_group = QGroupBox("Controller Button/Axis Mapping")
        joy_map_layout = QVBoxLayout(joy_map_group)
        map_ctrl_layout = QHBoxLayout()
        map_ctrl_layout.addWidget(QLabel("Monitor & Map Controller:"))
        self.joystick_select_combo_for_mapping = QComboBox()
        self.joystick_select_combo_for_mapping.currentIndexChanged.connect(self.on_monitor_joystick_changed)
        map_ctrl_layout.addWidget(self.joystick_select_combo_for_mapping, 1)
        joy_map_layout.addLayout(map_ctrl_layout)
        tbl_ctrl_layout = QHBoxLayout()
        tbl_ctrl_layout.addWidget(QLabel("Action to Map:"))
        self.key_to_map_combo = QComboBox()
        for ik in MAPPABLE_KEYS: self.key_to_map_combo.addItem(INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(ik, ik), userData=ik)
        tbl_ctrl_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Map Selected Action"); self.listen_button.clicked.connect(self.start_listening_for_joystick_map_from_button)
        tbl_ctrl_layout.addWidget(self.listen_button)
        joy_map_layout.addLayout(tbl_ctrl_layout)
        self.mappings_table = QTableWidget(); self.mappings_table.setColumnCount(8)
        self.mappings_table.setHorizontalHeaderLabels(["Action", "Input", "", "", "Action", "Input", "", ""]) # Simplified headers
        self.mappings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for col_idx in [0,4]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        for col_idx in [1,5]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Stretch)
        for col_idx in [2,3,6,7]: self.mappings_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click)
        joy_map_layout.addWidget(self.mappings_table)
        main_layout.addWidget(joy_map_group)

        file_btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save All Settings"); save_btn.clicked.connect(self.save_all_settings)
        file_btn_layout.addWidget(save_btn)
        reset_btn = QPushButton("Reset All to Default"); reset_btn.clicked.connect(self.confirm_reset_all_settings)
        file_btn_layout.addWidget(reset_btn)
        main_layout.addLayout(file_btn_layout)
        
        main_layout.addWidget(QLabel("Event Log:"))
        self.debug_console = QTextEdit(); self.debug_console.setReadOnly(True); self.debug_console.setFixedHeight(100)
        main_layout.addWidget(self.debug_console)

        self.controller_thread = PygameControllerThread()
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured_for_mapping)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered_for_simulation)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log_and_joystick_combos)
        
        logger_cmg.info("ControllerSettingsWindow initialized.")
        if not parent: self.load_settings_into_ui(); self.activate_controller_monitoring()

    def activate_controller_monitoring(self):
        logger_cmg.info("Activating controller monitoring.")
        if not self.controller_thread.isRunning():
            self.controller_thread.stop_flag.clear() # Ensure flag is cleared before start
            self.controller_thread.start()
        self.load_settings_into_ui()
        self.update_status_and_log_and_joystick_combos("Controller monitoring activated.")

    def deactivate_controller_monitoring(self):
        logger_cmg.info("Deactivating controller monitoring.")
        if self.controller_thread.isRunning():
            self.controller_thread.stop()
            if not self.controller_thread.wait(1000): logger_cmg.warning("Controller thread did not stop gracefully.")
            else: logger_cmg.info("Controller thread stopped.")
        for key_to_release in list(self.currently_pressed_keys):
            try: self.keyboard.release(key_to_release)
            except Exception: pass
        self.currently_pressed_keys.clear()

    def log_to_debug_console(self, message: str):
        if hasattr(self, 'debug_console'): self.debug_console.append(f"[{time.strftime('%H:%M:%S')}] {message}"); self.debug_console.ensureCursorVisible()

    def update_status_and_log(self, message: str):
        if hasattr(self, 'status_label'): self.status_label.setText(message)
        self.log_to_debug_console(message)
        logger_cmg.log(logging.INFO, f"Settings Status Update: {message}")

    def update_status_and_log_and_joystick_combos(self, message: str):
        self.update_status_and_log(message); self.populate_joystick_device_combos()

    def get_current_mapping_joystick_guid(self) -> Optional[str]:
        joy_data = self.joystick_select_combo_for_mapping.currentData()
        return joy_data.get("guid") if isinstance(joy_data, dict) else None

    def get_joystick_display_name_by_guid(self, target_guid: str) -> str:
        for i in range(self.joystick_select_combo_for_mapping.count()):
            data = self.joystick_select_combo_for_mapping.itemData(i)
            if isinstance(data, dict) and data.get("guid") == target_guid: return self.joystick_select_combo_for_mapping.itemText(i)
        return f"Ctrl (GUID:...{target_guid[-6:]})" if target_guid else "Unknown Ctrl"

    def populate_joystick_device_combos(self):
        logger_cmg.debug("Populating joystick combos...")
        available_joysticks_full_data: List[Tuple[str, str, Optional[str], int]] = game_config.get_available_joystick_names_with_indices_and_guids()
        
        current_player_dev_selections = [combo.currentData() for combo in self.player_device_combos]
        prev_mapping_guid = self.get_current_mapping_joystick_guid()
        
        for combo in self.player_device_combos + [self.joystick_select_combo_for_mapping]:
            combo.blockSignals(True); combo.clear(); combo.blockSignals(False)
        
        # Populate Player Device Combos
        for i, p_combo in enumerate(self.player_device_combos):
            p_combo.blockSignals(True)
            p_combo.addItem(UNASSIGNED_DEVICE_NAME, UNASSIGNED_DEVICE_ID) # Add "Unassigned" first
            if hasattr(game_config, 'KEYBOARD_DEVICE_IDS') and hasattr(game_config, 'KEYBOARD_DEVICE_NAMES'):
                for k_idx, k_id in enumerate(game_config.KEYBOARD_DEVICE_IDS):
                    if k_id == UNASSIGNED_DEVICE_ID: continue # Skip if already added "Unassigned"
                    k_name = game_config.KEYBOARD_DEVICE_NAMES[k_idx] if k_idx < len(game_config.KEYBOARD_DEVICE_NAMES) else k_id
                    p_combo.addItem(k_name, k_id)
            else: # Basic fallback
                p_combo.addItem("Keyboard P1", "keyboard_p1"); p_combo.addItem("Keyboard P2", "keyboard_p2")
            
            for joy_disp_name, internal_id_for_assignment, _, _ in available_joysticks_full_data:
                p_combo.addItem(joy_disp_name, internal_id_for_assignment)
            
            p_combo.blockSignals(False)
            idx_to_set = p_combo.findData(current_player_dev_selections[i] if i < len(current_player_dev_selections) else UNASSIGNED_DEVICE_ID)
            p_combo.setCurrentIndex(idx_to_set if idx_to_set != -1 else 0)

        # Populate Joystick Select Combo for Mapping (for editing mappings)
        new_map_combo_idx = -1
        self.joystick_select_combo_for_mapping.blockSignals(True)
        # Add a "No Controller" option for the mapping editor perhaps, or just leave empty if none.
        if not available_joysticks_full_data:
             self.joystick_select_combo_for_mapping.addItem("No Controllers Detected", None) # UserData is None
        else:
            for joy_disp_name, _, guid_str, pygame_joy_idx in available_joysticks_full_data:
                # Use a more descriptive name for mapping combo
                map_combo_display_name = f"Joy {pygame_joy_idx}: {joy_disp_name.split(': ', 1)[-1]}"
                self.joystick_select_combo_for_mapping.addItem(map_combo_display_name, {"index": pygame_joy_idx, "guid": guid_str, "name": map_combo_display_name})
                if guid_str == prev_mapping_guid: new_map_combo_idx = self.joystick_select_combo_for_mapping.count() - 1
        
        self.joystick_select_combo_for_mapping.blockSignals(False)
        if new_map_combo_idx != -1: self.joystick_select_combo_for_mapping.setCurrentIndex(new_map_combo_idx)
        elif self.joystick_select_combo_for_mapping.count() > 0: self.joystick_select_combo_for_mapping.setCurrentIndex(0)
        
        if self.joystick_select_combo_for_mapping.count() > 0 and self.joystick_select_combo_for_mapping.currentData() is not None:
            self.on_monitor_joystick_changed(self.joystick_select_combo_for_mapping.currentIndex())
        else:
            self.controller_thread.set_joystick_to_monitor(-1)
            self.update_simulation_thread_mappings({})
            self.refresh_joystick_mappings_table(None)
            self.listen_button.setEnabled(False)
            self.update_status_and_log("No controllers available for mapping.")
        logger_cmg.debug("Joystick device combos populated.")

    def on_monitor_joystick_changed(self, index_in_combo: int):
        logger_cmg.debug(f"Monitor joystick changed. Combo index: {index_in_combo}")
        if index_in_combo == -1 or self.joystick_select_combo_for_mapping.count() == 0:
            self.controller_thread.set_joystick_to_monitor(-1); self.update_status_and_log("No controller selected."); return

        joy_data = self.joystick_select_combo_for_mapping.itemData(index_in_combo)
        if not isinstance(joy_data, dict): # Handles "No Controllers Detected" case where itemData is None
            self.controller_thread.set_joystick_to_monitor(-1)
            self.update_status_and_log("No valid controller selected for mapping."); self.listen_button.setEnabled(False)
            self.update_simulation_thread_mappings({}); self.refresh_joystick_mappings_table(None)
            return
            
        pygame_joy_idx = joy_data.get("index"); current_guid = joy_data.get("guid")
        current_joy_text = self.joystick_select_combo_for_mapping.itemText(index_in_combo)

        if pygame_joy_idx is not None and current_guid:
            self.controller_thread.set_joystick_to_monitor(pygame_joy_idx)
            self.update_status_and_log(f"Monitoring '{current_joy_text}' for mapping."); self.listen_button.setEnabled(True)

            if current_guid not in self.all_joystick_mappings_by_guid:
                logger_cmg.info(f"No mappings for GUID {current_guid}. Trying fallback/default.")
                # (Fallback/default logic as before)
                source_guid_for_fallback = next((guid for guid, maps in self.all_joystick_mappings_by_guid.items() if maps and guid != current_guid), None)
                if source_guid_for_fallback:
                    self.all_joystick_mappings_by_guid[current_guid] = copy.deepcopy(self.all_joystick_mappings_by_guid[source_guid_for_fallback])
                elif hasattr(game_config, 'DEFAULT_GENERIC_JOYSTICK_MAPPINGS'):
                    defaults_gui = {act: gui_map for act, rt_map in game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS.items() if act in MAPPABLE_KEYS and (gui_map := _convert_runtime_default_to_gui_storage(act, rt_map, pygame_joy_idx))}
                    self.all_joystick_mappings_by_guid[current_guid] = defaults_gui if defaults_gui else {}
                else: self.all_joystick_mappings_by_guid[current_guid] = {}
            
            current_maps = self.all_joystick_mappings_by_guid.get(current_guid, {})
            self.update_simulation_thread_mappings(current_maps)
            self.refresh_joystick_mappings_table(current_guid)
        else: self.controller_thread.set_joystick_to_monitor(-1); self.update_status_and_log("Error with selected controller data."); self.listen_button.setEnabled(False)

    def update_simulation_thread_mappings(self, raw_gui_mappings: Dict[str, Any]):
        self.current_translated_mappings_for_thread_sim.clear()
        for action_key, map_info in raw_gui_mappings.items():
            translated = game_config.translate_mapping_for_runtime(map_info)
            if translated: self.current_translated_mappings_for_thread_sim[action_key] = translated
            else: logger_cmg.warning(f"Could not translate GUI mapping for '{action_key}': {map_info}")
        self.controller_thread.translated_mappings_for_triggering = self.current_translated_mappings_for_thread_sim

    def load_settings_into_ui(self):
        logger_cmg.info("Loading settings into UI...")
        game_config.load_config() 
        self.all_joystick_mappings_by_guid = copy.deepcopy(getattr(game_config, 'LOADED_PYGAME_JOYSTICK_MAPPINGS', {}))
        self.populate_joystick_device_combos()

        for i in range(4):
            dev_id = getattr(game_config, f"CURRENT_P{i+1}_INPUT_DEVICE", UNASSIGNED_DEVICE_ID)
            kbd_en = getattr(game_config, f"P{i+1}_KEYBOARD_ENABLED", False)
            ctrl_en = getattr(game_config, f"P{i+1}_CONTROLLER_ENABLED", False)
            idx = self.player_device_combos[i].findData(dev_id)
            self.player_device_combos[i].setCurrentIndex(idx if idx != -1 else 0)
            self.player_kbd_enable_checks[i].setChecked(kbd_en)
            self.player_ctrl_enable_checks[i].setChecked(ctrl_en)
        
        current_map_guid = self.get_current_mapping_joystick_guid()
        if current_map_guid:
            self.refresh_joystick_mappings_table(current_map_guid)
            self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid.get(current_map_guid,{}))
        elif self.joystick_select_combo_for_mapping.count() > 0 and self.joystick_select_combo_for_mapping.currentData() is not None:
             self.on_monitor_joystick_changed(0)
        self.update_status_and_log("Settings loaded into UI.")

    def save_all_settings(self):
        logger_cmg.info("Saving all settings...")
        for i in range(4):
            setattr(game_config, f"CURRENT_P{i+1}_INPUT_DEVICE", self.player_device_combos[i].currentData())
            setattr(game_config, f"P{i+1}_KEYBOARD_ENABLED", self.player_kbd_enable_checks[i].isChecked())
            setattr(game_config, f"P{i+1}_CONTROLLER_ENABLED", self.player_ctrl_enable_checks[i].isChecked())
        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS = copy.deepcopy(self.all_joystick_mappings_by_guid)
        if game_config.save_config(): self.update_status_and_log("All settings saved.")
        else: QMessageBox.critical(self, "Save Error", "Could not save settings."); self.update_status_and_log("Error saving settings.")

    def confirm_reset_all_settings(self):
        if QMessageBox.question(self, "Confirm Reset", "Reset all settings to default?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.perform_reset_all_settings()

    def perform_reset_all_settings(self):
        logger_cmg.info("Resetting all settings to default.")
        for i in range(4):
            setattr(game_config, f"CURRENT_P{i+1}_INPUT_DEVICE", getattr(game_config, f"DEFAULT_P{i+1}_INPUT_DEVICE"))
            setattr(game_config, f"P{i+1}_KEYBOARD_ENABLED", getattr(game_config, f"DEFAULT_P{i+1}_KEYBOARD_ENABLED"))
            setattr(game_config, f"P{i+1}_CONTROLLER_ENABLED", getattr(game_config, f"DEFAULT_P{i+1}_CONTROLLER_ENABLED"))
        self.all_joystick_mappings_by_guid.clear()
        if hasattr(game_config, 'LOADED_PYGAME_JOYSTICK_MAPPINGS'): game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.clear()
        self.load_settings_into_ui() 
        self.update_status_and_log("Settings reset. Save to make permanent.")

    def start_listening_for_joystick_map_from_button(self):
        guid = self.get_current_mapping_joystick_guid()
        action_key = self.key_to_map_combo.currentData()
        if not guid: self.update_status_and_log("No controller selected to map."); return
        if not action_key: self.update_status_and_log("No action selected to map."); return
        self.initiate_listening_sequence_for_joystick_map(action_key)

    def initiate_listening_sequence_for_joystick_map(self, key_to_map: str, row_idx:int = -1):
        if not self.get_current_mapping_joystick_guid() or self.controller_thread.joystick_idx_to_monitor == -1:
            self.update_status_and_log("Cannot listen: No controller selected/ready."); return
        self.current_listening_key_for_joystick_map = key_to_map; self.last_selected_row_for_joystick_mapping = row_idx
        self.controller_thread.start_listening()
        self.update_status_and_log(f"Listening for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(key_to_map,key_to_map)}' on {self.joystick_select_combo_for_mapping.currentText()}...")
        self.listen_button.setText("Listening..."); self.listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(False); self.joystick_select_combo_for_mapping.setEnabled(False); self.mappings_table.setEnabled(False)

    def on_controller_event_captured_for_mapping(self, event_details: dict, raw_event_str: str):
        guid = self.get_current_mapping_joystick_guid(); action_key = self.current_listening_key_for_joystick_map
        if not action_key or not guid: self.reset_listening_ui_for_joystick_map(); return
        if guid not in self.all_joystick_mappings_by_guid: self.all_joystick_mappings_by_guid[guid] = {}
        current_maps = self.all_joystick_mappings_by_guid[guid]
        if action_key not in MENU_SPECIFIC_ACTIONS: # Conflict check for non-menu actions
            for old_key, old_map in list(current_maps.items()):
                if old_key in MENU_SPECIFIC_ACTIONS: continue
                if old_map and old_map.get("raw_str") == raw_event_str and old_key != action_key:
                    if QMessageBox.question(self,"Conflict",f"Input '{raw_event_str}' is already for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(old_key,old_key)}'. Overwrite?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                        self.reset_listening_ui_for_joystick_map(); self.update_status_and_log(f"Mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(action_key,action_key)}' cancelled."); return
                    del current_maps[old_key]; break
        current_maps[action_key] = {"event_type": event_details["type"], "details": event_details, "raw_str": raw_event_str}
        self.log_to_debug_console(f"Mapped '{raw_event_str}' to '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(action_key,action_key)}'.")
        self.refresh_joystick_mappings_table(guid, True, action_key)
        self.update_simulation_thread_mappings(current_maps)
        self.reset_listening_ui_for_joystick_map(True)

    def reset_listening_ui_for_joystick_map(self, preserve_scroll=False):
        self.listen_button.setText("Map Selected Action"); self.listen_button.setEnabled(self.joystick_select_combo_for_mapping.currentIndex() != -1 and self.joystick_select_combo_for_mapping.currentData() is not None)
        self.key_to_map_combo.setEnabled(True); self.joystick_select_combo_for_mapping.setEnabled(True); self.mappings_table.setEnabled(True)
        self.controller_thread.stop_listening()
        if not preserve_scroll: self.last_selected_row_for_joystick_mapping = -1

    def on_mapped_event_triggered_for_simulation(self, action_key: str, is_pressed: bool):
        display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(action_key, action_key)
        simulate = not (action_key in EXCLUSIVE_ACTIONS and not is_pressed)
        log_msg = f"Sim Event: '{display_name}' {'Pressed' if is_pressed else 'Released'}"
        if simulate:
            pynput_key = get_pynput_key(action_key)
            if pynput_key:
                try:
                    if is_pressed and pynput_key not in self.currently_pressed_keys: self.keyboard.press(pynput_key); self.currently_pressed_keys.add(pynput_key); log_msg += f" (Sim Key: {pynput_key} Press)"
                    elif not is_pressed and pynput_key in self.currently_pressed_keys: self.keyboard.release(pynput_key); self.currently_pressed_keys.remove(pynput_key); log_msg += f" (Sim Key: {pynput_key} Release)"
                except Exception as e: logger_cmg.error(f"Pynput error for '{display_name}': {e}"); log_msg += " (Pynput Error)"
            else: log_msg += " (No pynput key)"
        else: log_msg += " (Pynput sim skipped)"
        self.log_to_debug_console(log_msg)

    def refresh_joystick_mappings_table(self, guid: Optional[str], preserve_scroll=False, target_action_key: Optional[str] = None):
        scroll_val = self.mappings_table.verticalScrollBar().value() if preserve_scroll else -1
        self.mappings_table.setRowCount(0)
        if not guid: self.log_to_debug_console("Mapping table cleared (no controller)."); return
        maps_to_disp = self.all_joystick_mappings_by_guid.get(guid, {})
        num_rows = (len(MAPPABLE_KEYS) + 1) // 2
        self.mappings_table.setRowCount(num_rows); target_row_vis = -1
        for i in range(num_rows):
            for col_grp in range(2):
                act_idx = i * 2 + col_grp; base_col = col_grp * 4
                if act_idx >= len(MAPPABLE_KEYS): continue
                internal_key = MAPPABLE_KEYS[act_idx]
                if target_action_key and internal_key == target_action_key: target_row_vis = i
                action_item = QTableWidgetItem(INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key)); action_item.setData(Qt.UserRole, internal_key)
                self.mappings_table.setItem(i, base_col, action_item)
                map_info = maps_to_disp.get(internal_key)
                if map_info:
                    self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem(map_info.get("raw_str", "N/A")))
                    rename_btn = QPushButton("Rename"); rename_btn.setProperty("internal_key", internal_key); rename_btn.clicked.connect(lambda c=False,k=internal_key:self.rename_joystick_mapping_friendly_name_prompt(k))
                    self.mappings_table.setCellWidget(i, base_col + 2, rename_btn)
                    clear_btn = QPushButton("Clear"); clear_btn.setProperty("internal_key", internal_key); clear_btn.clicked.connect(lambda c=False,k=internal_key:self.clear_joystick_mapping(k))
                    self.mappings_table.setCellWidget(i, base_col + 3, clear_btn)
                else: self.mappings_table.setItem(i, base_col + 1, QTableWidgetItem("Not Mapped"))
        if target_row_vis != -1: self.mappings_table.scrollToItem(self.mappings_table.item(target_row_vis,0), QAbstractItemView.ScrollHint.PositionAtCenter)
        elif preserve_scroll and scroll_val != -1: self.mappings_table.verticalScrollBar().setValue(scroll_val)
        if self.current_listening_key_for_joystick_map == target_action_key: self.current_listening_key_for_joystick_map = None

    def handle_table_double_click(self, row: int, col: int):
        col_grp = 0 if col < 4 else 1; act_item_col = col_grp*4
        act_item = self.mappings_table.item(row, act_item_col)
        if act_item and (col % 4) <= 1: # Clicked on Action or Input column
            internal_key = act_item.data(Qt.UserRole)
            if internal_key: self.initiate_listening_sequence_for_joystick_map(internal_key, row)

    def rename_joystick_mapping_friendly_name_prompt(self, key: str):
        guid = self.get_current_mapping_joystick_guid()
        if not guid or key not in self.all_joystick_mappings_by_guid.get(guid, {}): self.update_status_and_log("Cannot rename: Mapping not found."); return
        map_info = self.all_joystick_mappings_by_guid[guid][key]
        curr_lbl = map_info.get("raw_str", "")
        text, ok = QInputDialog.getText(self, "Rename Label", f"Label for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(key,key)}' (current: {curr_lbl}):", QLineEdit.Normal, curr_lbl)
        if ok and text:
            map_info["raw_str"] = text; self.refresh_joystick_mappings_table(guid, True, key)
            self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid[guid])
            self.log_to_debug_console(f"Relabeled input for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(key,key)}' to '{text}'.")

    def clear_joystick_mapping(self, key: str):
        guid = self.get_current_mapping_joystick_guid()
        if not guid or key not in self.all_joystick_mappings_by_guid.get(guid, {}): self.update_status_and_log("Cannot clear: Mapping not found."); return
        del self.all_joystick_mappings_by_guid[guid][key]
        self.refresh_joystick_mappings_table(guid, True, key)
        self.update_simulation_thread_mappings(self.all_joystick_mappings_by_guid[guid])
        self.log_to_debug_console(f"Cleared mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(key,key)}'.")

    def closeEvent(self, event):
        logger_cmg.info("ControllerSettingsWindow closeEvent. Shutting down thread.")
        self.deactivate_controller_monitoring()
        super().closeEvent(event)

# --- Main execution for standalone testing ---
if __name__ == "__main__":
    logger_cmg.info("ControllerSettingsWindow application starting (standalone)...")
    
    if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
        print("Standalone GUI: Pygame/Joystick not globally initialized. Attempting init now.")
        game_config.init_pygame_and_joystick_globally(force_rescan=True) # Force scan here for standalone
        if not game_config._joystick_initialized_globally:
            temp_app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Init Error", "Failed to initialize Pygame Joystick. Limited functionality.")
            logger_cmg.critical("Standalone GUI: FAILED to initialize Pygame Joystick system.")

    app = QApplication.instance() or QApplication(sys.argv)
    
    try: game_config.load_config()
    except Exception as e: logger_cmg.error(f"Standalone GUI: Error loading game_config: {e}")

    main_window_for_testing = QMainWindow()
    settings_widget = ControllerSettingsWindow()
    main_window_for_testing.setCentralWidget(settings_widget)
    main_window_for_testing.setWindowTitle("Controller & Input Settings (Standalone Test)")
    main_window_for_testing.setGeometry(100, 100, 1050, 850)
    main_window_for_testing.show()
    
    exit_code = app.exec()
    
    if hasattr(settings_widget, 'controller_thread') and settings_widget.controller_thread.isRunning():
        settings_widget.controller_thread.stop(); settings_widget.controller_thread.wait(500)
    if game_config._pygame_initialized_globally:
        if game_config._joystick_initialized_globally:
            try: pygame.joystick.quit()
            except: pass
        try: pygame.quit()
        except: pass
        logger_cmg.info("Standalone GUI: Pygame quit.")
    sys.exit(exit_code)