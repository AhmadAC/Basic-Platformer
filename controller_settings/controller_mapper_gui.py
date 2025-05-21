# controller_settings/controller_mapper_gui.py
import sys
import json
import threading
import time
import logging
import os
from typing import Dict, Optional, Any, List, Tuple

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
# This is important for standalone execution.
# For when embedded, app_core will handle sys.path.
if __name__ == "__main__":
    # If running standalone, ensure the parent directory (project root) is in sys.path
    # so 'import config as game_config' works.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        print(f"ControllerMapperGUI (Standalone): Added '{parent_dir}' to sys.path.")

try:
    import config as game_config
except ImportError:
    # Fallback if config can't be imported (e.g., path issue when running standalone)
    print("CRITICAL ERROR in controller_mapper_gui.py: Could not import 'config as game_config'. Ensure parent directory is in sys.path.")
    # Define minimal fallbacks for critical game_config attributes if needed for basic GUI structure
    class GameConfigFallback:
        GAME_ACTIONS = ["jump", "attack1", "left", "right"] # Minimal set
        EXTERNAL_TO_INTERNAL_ACTION_MAP = {"JUMP_ACTION": "jump"}
        AXIS_THRESHOLD_DEFAULT = 0.7
        MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH = "controller_mappings_fallback.json"
        DEFAULT_P1_INPUT_DEVICE = "keyboard_p1"
        DEFAULT_P1_KEYBOARD_ENABLED = True
        DEFAULT_P1_CONTROLLER_ENABLED = True
        DEFAULT_P2_INPUT_DEVICE = "keyboard_p2"
        DEFAULT_P2_KEYBOARD_ENABLED = True
        DEFAULT_P2_CONTROLLER_ENABLED = True
        # Dummy methods that might be called by the GUI
        @staticmethod
        def get_available_joystick_names_with_indices(): return []
        @staticmethod
        def save_config(): print("Fallback save_config called"); return False
        @staticmethod
        def load_config(): print("Fallback load_config called"); return False
        @staticmethod
        def update_player_mappings_from_config(): print("Fallback update_player_mappings called")
        # Add other attributes/methods if the GUI initialization crashes without them
        CURRENT_P1_INPUT_DEVICE = "keyboard_p1"; P1_KEYBOARD_ENABLED = True; P1_CONTROLLER_ENABLED = True
        CURRENT_P2_INPUT_DEVICE = "keyboard_p2"; P2_KEYBOARD_ENABLED = True; P2_CONTROLLER_ENABLED = True
        LOADED_PYGAME_JOYSTICK_MAPPINGS = {}

    game_config = GameConfigFallback() # type: ignore

# --- Logging Setup ---
# Basic logging if not already configured by a higher-level module
logger_cmg = logging.getLogger(__name__)
if not logger_cmg.hasHandlers():
    _cmg_handler = logging.StreamHandler(sys.stdout)
    _cmg_formatter = logging.Formatter('%(asctime)s - CM_GUI - %(levelname)s - %(message)s')
    _cmg_handler.setFormatter(_cmg_formatter)
    logger_cmg.addHandler(_cmg_handler)
    logger_cmg.setLevel(logging.INFO)
    logger_cmg.propagate = False

# --- Configuration from game_config ---
MAPPABLE_KEYS = game_config.GAME_ACTIONS
INTERNAL_TO_FRIENDLY_ACTION_DISPLAY = {v: k for k, v in game_config.EXTERNAL_TO_INTERNAL_ACTION_MAP.items() if v in game_config.GAME_ACTIONS}
for action in game_config.GAME_ACTIONS:
    if action not in INTERNAL_TO_FRIENDLY_ACTION_DISPLAY:
        INTERNAL_TO_FRIENDLY_ACTION_DISPLAY[action] = action.replace("_", " ").title()

EXCLUSIVE_ACTIONS = ["MENU_RETURN"] # Example
AXIS_THRESHOLD = game_config.AXIS_THRESHOLD_DEFAULT
MAPPINGS_FILE = game_config.MAPPINGS_AND_DEVICE_CHOICES_FILE_PATH

logger_cmg.info(f"Mappings file path from game_config: {MAPPINGS_FILE}")

def get_pynput_key(key_str):
    if key_str == "SPACE": return Key.space
    if key_str == "SHIFT": return Key.shift
    if key_str == "CTRL": return Key.ctrl
    if key_str == "ALT": return Key.alt
    # Map abstract actions to example keys for simulation (customize as needed)
    if key_str == "up": return 'w'
    if key_str == "left": return 'a'
    if key_str == "down": return 's'
    if key_str == "right": return 'd'
    if key_str == "jump": return Key.space # Simulate jump as space
    if key_str == "attack1": return 'v'
    # Add more mappings if pynput simulation is important for other abstract actions
    if len(key_str) == 1 and key_str.isalnum():
        return key_str.lower()
    logger_cmg.warning(f"get_pynput_key: Unknown or non-simulatable key string '{key_str}'")
    return None

class PygameControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str) # event_details (raw GUI format), raw_event_str
    mappedEventTriggered = Signal(str, bool)    # internal_action_key, is_press
    controllerHotplug = Signal(str)             # status_message

    def __init__(self, translated_mappings_ref: Dict[str,Any]): # Takes translated mappings for triggering
        super().__init__()
        self.joystick: Optional[pygame.joystick.Joystick] = None
        self.is_listening_for_mapping = False
        self.stop_flag = threading.Event()
        self.translated_mappings_for_triggering = translated_mappings_ref
        self.active_axis_keys: Dict[Tuple[int, int], str] = {} # (axis_id, direction_value) -> internal_action_key
        self.active_hat_keys: Dict[Tuple[int, Tuple[int,int]], str] = {} # (hat_id, hat_value_tuple) -> internal_action_key
        self._last_joystick_count = -1
        self.joystick_idx_to_monitor = 0
        self.joystick_instance_id_to_monitor: Optional[int] = None
        logger_cmg.debug("PygameControllerThread initialized.")

    def set_joystick_to_monitor(self, index: int):
        self.joystick_idx_to_monitor = index
        self.joystick = None # Force re-initialization
        self.joystick_instance_id_to_monitor = None
        logger_cmg.info(f"PygameControllerThread set to monitor joystick index: {index}")

    def run(self):
        logger_cmg.info("PygameControllerThread started.")
        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            logger_cmg.error("Pygame or Joystick system not globally initialized! Thread cannot run reliably.")
            self.controllerHotplug.emit("Error: Pygame Joystick system not ready.")
            return

        while not self.stop_flag.is_set():
            try:
                current_joystick_count = pygame.joystick.get_count()
                if self.joystick is None: # Try to acquire/re-acquire joystick
                    if 0 <= self.joystick_idx_to_monitor < current_joystick_count:
                        try:
                            temp_joy = pygame.joystick.Joystick(self.joystick_idx_to_monitor)
                            temp_joy.init() # IMPORTANT: Init the joystick object
                            self.joystick = temp_joy
                            self.joystick_instance_id_to_monitor = self.joystick.get_instance_id()
                            name = self.joystick.get_name()
                            self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} ({name}) ready.")
                            logger_cmg.info(f"Controller {self.joystick_idx_to_monitor} ({name}) acquired. Instance ID: {self.joystick_instance_id_to_monitor}")
                        except pygame.error as e:
                            logger_cmg.error(f"Error initializing joystick {self.joystick_idx_to_monitor}: {e}")
                            self.joystick = None; self.joystick_instance_id_to_monitor = None
                            self.controllerHotplug.emit(f"Joystick {self.joystick_idx_to_monitor} init error. Retrying...")
                    else:
                        if self.joystick_instance_id_to_monitor is not None or self._last_joystick_count != current_joystick_count : # Only message if it was previously connected or count changed
                            self.controllerHotplug.emit(f"Joystick {self.joystick_idx_to_monitor} unavailable (Count: {current_joystick_count}).")
                        self.joystick = None; self.joystick_instance_id_to_monitor = None
                    self._last_joystick_count = current_joystick_count
                    time.sleep(1); continue

                # Check if the acquired joystick is still valid
                if not self.joystick.get_init(): # Joystick has been uninitialized (e.g. disconnected)
                    logger_cmg.warning(f"Monitored joystick {self.joystick_idx_to_monitor} (Instance ID: {self.joystick_instance_id_to_monitor}) no longer initialized.")
                    self.controllerHotplug.emit(f"Controller {self.joystick_idx_to_monitor} lost.")
                    self.joystick = None; self.joystick_instance_id_to_monitor = None
                    self.active_axis_keys.clear(); self.active_hat_keys.clear()
                    time.sleep(1); continue

                for event in pygame.event.get():
                    if self.stop_flag.is_set(): break
                    
                    # Filter events by instance ID of the monitored joystick
                    if not hasattr(event, 'instance_id') or event.instance_id != self.joystick_instance_id_to_monitor:
                        continue

                    event_details_for_gui: Optional[Dict[str, Any]] = None
                    raw_event_str_for_gui = ""

                    if event.type == pygame.JOYAXISMOTION:
                        axis_id = event.axis; value = event.value
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Axis {axis_id}: {value:.2f}"
                        # For mapping capture:
                        if self.is_listening_for_mapping:
                            if value > AXIS_THRESHOLD:
                                event_details_for_gui = {"type": "axis", "axis_id": axis_id, "direction": 1, "threshold": AXIS_THRESHOLD}
                            elif value < -AXIS_THRESHOLD:
                                event_details_for_gui = {"type": "axis", "axis_id": axis_id, "direction": -1, "threshold": AXIS_THRESHOLD}
                        # For triggering mapped actions:
                        else:
                            for (map_axis_id, map_direction), action_key in list(self.active_axis_keys.items()):
                                if map_axis_id == axis_id:
                                    if (map_direction == 1 and value < 0.1) or \
                                       (map_direction == -1 and value > -0.1) or \
                                       (abs(value) < AXIS_THRESHOLD * 0.5):
                                        self.mappedEventTriggered.emit(action_key, False)
                                        del self.active_axis_keys[(map_axis_id, map_direction)]
                            
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "axis" and mapping_info.get("id") == axis_id:
                                    map_val = mapping_info.get("value")
                                    map_thresh = mapping_info.get("threshold", AXIS_THRESHOLD)
                                    is_active_now = (map_val == 1 and value > map_thresh) or \
                                                    (map_val == -1 and value < -map_thresh)
                                    if is_active_now and (axis_id, map_val) not in self.active_axis_keys:
                                        self.mappedEventTriggered.emit(action_key, True)
                                        self.active_axis_keys[(axis_id, map_val)] = action_key


                    elif event.type == pygame.JOYBUTTONDOWN:
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Down"
                        if self.is_listening_for_mapping:
                            event_details_for_gui = {"type": "button", "button_id": event.button}
                        else:
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "button" and mapping_info.get("id") == event.button:
                                    self.mappedEventTriggered.emit(action_key, True); break 

                    elif event.type == pygame.JOYBUTTONUP:
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Btn {event.button} Up"
                        # No mapping capture for button up.
                        if not self.is_listening_for_mapping:
                            for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                if mapping_info.get("type") == "button" and mapping_info.get("id") == event.button:
                                    self.mappedEventTriggered.emit(action_key, False); break

                    elif event.type == pygame.JOYHATMOTION:
                        hat_id = event.hat; hat_value_tuple = event.value
                        raw_event_str_for_gui = f"Joy{self.joystick_idx_to_monitor} Hat {hat_id} {hat_value_tuple}"
                        if self.is_listening_for_mapping:
                            if hat_value_tuple != (0,0): # Capture non-neutral hat positions
                                event_details_for_gui = {"type": "hat", "hat_id": hat_id, "value": list(hat_value_tuple)}
                        else:
                            # Release previously active hat actions if hat moves away or to neutral
                            for (map_hat_id, map_hat_val), action_key in list(self.active_hat_keys.items()):
                                if map_hat_id == hat_id and map_hat_val != hat_value_tuple:
                                    self.mappedEventTriggered.emit(action_key, False)
                                    del self.active_hat_keys[(map_hat_id, map_hat_val)]
                            
                            # Activate new hat actions
                            if hat_value_tuple != (0,0):
                                for action_key, mapping_info in self.translated_mappings_for_triggering.items():
                                    if mapping_info.get("type") == "hat" and mapping_info.get("id") == hat_id and \
                                       tuple(mapping_info.get("value",(9,9))) == hat_value_tuple: # (9,9) unlikely value
                                        if (hat_id, hat_value_tuple) not in self.active_hat_keys:
                                            self.mappedEventTriggered.emit(action_key, True)
                                            self.active_hat_keys[(hat_id, hat_value_tuple)] = action_key
                                        break


                    if self.is_listening_for_mapping and event_details_for_gui:
                        logger_cmg.info(f"Event captured for mapping: {raw_event_str_for_gui} -> {event_details_for_gui}")
                        self.controllerEventCaptured.emit(event_details_for_gui, raw_event_str_for_gui)
                        self.is_listening_for_mapping = False
                
                time.sleep(0.01) # Reduce CPU usage
            except pygame.error as e:
                logger_cmg.error(f"Pygame error in controller loop (joystick {self.joystick_idx_to_monitor}): {e}")
                self.controllerHotplug.emit(f"Pygame error with Joy {self.joystick_idx_to_monitor}. Re-scanning...")
                self.joystick = None; self.joystick_instance_id_to_monitor = None
                self.active_axis_keys.clear(); self.active_hat_keys.clear()
                try: # Attempt to re-init joystick system to recover from some errors
                    if pygame.joystick.get_init(): pygame.joystick.quit()
                    pygame.joystick.init()
                except pygame.error: pass
                time.sleep(1)
            except Exception as e:
                logger_cmg.exception("Unhandled exception in controller thread loop:")
                time.sleep(1)

        if self.joystick: # Ensure joystick is quit if it was initialized
            try: self.joystick.quit()
            except: pass
        # pygame.joystick.quit() and pygame.quit() should happen in main app thread
        self.controllerHotplug.emit("Controller thread stopped.")
        logger_cmg.info("PygameControllerThread stopped.")


class ControllerSettingsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = KeyboardController()
        self.currently_pressed_keys = set()
        self.joystick_mappings_from_gui: Dict[str, Any] = {}
        self.current_listening_key_for_joystick_map: Optional[str] = None
        self.last_selected_row_for_joystick_mapping = -1

        main_layout = QVBoxLayout(self)
        self.status_label = QLabel("Initializing Input Settings...")
        main_layout.addWidget(self.status_label)

        config_area_group = QGroupBox("Player Input Configuration")
        config_grid_layout = QGridLayout(config_area_group)
        config_grid_layout.addWidget(QLabel("<b>Player 1:</b>"), 0, 0, 1, 4)
        config_grid_layout.addWidget(QLabel("Input Device:"), 1, 0)
        self.p1_device_combo = QComboBox(); config_grid_layout.addWidget(self.p1_device_combo, 1, 1)
        self.p1_kbd_enable_check = QCheckBox("Keyboard Enabled"); config_grid_layout.addWidget(self.p1_kbd_enable_check, 1, 2)
        self.p1_ctrl_enable_check = QCheckBox("Controller Enabled"); config_grid_layout.addWidget(self.p1_ctrl_enable_check, 1, 3)
        config_grid_layout.addWidget(QLabel("<b>Player 2:</b>"), 2, 0, 1, 4)
        config_grid_layout.addWidget(QLabel("Input Device:"), 3, 0)
        self.p2_device_combo = QComboBox(); config_grid_layout.addWidget(self.p2_device_combo, 3, 1)
        self.p2_kbd_enable_check = QCheckBox("Keyboard Enabled"); config_grid_layout.addWidget(self.p2_kbd_enable_check, 3, 2)
        self.p2_ctrl_enable_check = QCheckBox("Controller Enabled"); config_grid_layout.addWidget(self.p2_ctrl_enable_check, 3, 3)
        main_layout.addWidget(config_area_group)

        joystick_map_group = QGroupBox("Joystick Button/Axis Mapping (Applied to selected controller)")
        joystick_map_layout = QVBoxLayout(joystick_map_group)
        mapping_controls_layout = QHBoxLayout()
        mapping_controls_layout.addWidget(QLabel("Action to Map:"))
        self.key_to_map_combo = QComboBox()
        for internal_key in MAPPABLE_KEYS:
            self.key_to_map_combo.addItem(INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key), userData=internal_key)
        mapping_controls_layout.addWidget(self.key_to_map_combo)
        mapping_controls_layout.addWidget(QLabel("Monitor Joystick:"))
        self.joystick_select_combo_for_mapping = QComboBox()
        self.joystick_select_combo_for_mapping.currentIndexChanged.connect(self.on_monitor_joystick_changed)
        mapping_controls_layout.addWidget(self.joystick_select_combo_for_mapping)
        self.listen_button = QPushButton("Listen for Controller Input")
        self.listen_button.clicked.connect(self.start_listening_for_joystick_map_from_button)
        mapping_controls_layout.addWidget(self.listen_button)
        joystick_map_layout.addLayout(mapping_controls_layout)
        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(4)
        self.mappings_table.setHorizontalHeaderLabels(["Action", "Controller Input", "Rename Label", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.mappings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.mappings_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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

        # Pass the TRANSLATED mappings for the thread to use for triggering events
        self.controller_thread = PygameControllerThread(game_config.get_translated_pygame_joystick_mappings())
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured_for_mapping)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered_for_simulation)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log_and_joystick_combos)
        self.controller_thread.start()

        self.load_settings_into_ui()
        self.refresh_joystick_mappings_table()
        logger_cmg.info("ControllerSettingsWindow initialized.")

    def log_to_debug_console(self, message: str): # Re-added
        if hasattr(self, 'debug_console') and self.debug_console:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()
        else:
            logger_cmg.warning(f"Debug console not ready for message (from log_to_debug_console): {message}")

    def update_status_and_log(self, message: str): # Re-added
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(message)
        self.log_to_debug_console(message)
        if "error" in message.lower() or "lost" in message.lower() or "no controller" in message.lower():
            logging.warning(f"Settings Status Update: {message}")
        else:
            logging.info(f"Settings Status Update: {message}")


    def update_status_and_log_and_joystick_combos(self, message: str):
        self.update_status_and_log(message) # Call the re-added method
        self.populate_joystick_device_combos()

    def populate_joystick_device_combos(self):
        # Ensure config.py's joystick list is fresh if possible, or use its global one
        # This might require a function in config.py like `refresh_detected_joysticks()`
        # For now, assuming get_available_joystick_names_with_indices() gives current list
        if not game_config._joystick_initialized_globally:
            logger_cmg.warning("Populate Combos: Pygame joystick not globally initialized. Combos might be empty.")
            game_config.init_pygame_and_joystick_globally() # Attempt to ensure it is

        available_joysticks = game_config.get_available_joystick_names_with_indices()
        logger_cmg.debug(f"Populating joystick combos with: {available_joysticks}")

        current_p1_device = self.p1_device_combo.currentData()
        current_p2_device = self.p2_device_combo.currentData()
        current_monitor_joy_idx_data = self.joystick_select_combo_for_mapping.currentData() # This is int or None

        for combo in [self.p1_device_combo, self.p2_device_combo, self.joystick_select_combo_for_mapping]:
            combo.blockSignals(True); combo.clear(); combo.blockSignals(False)

        self.p1_device_combo.addItem("Keyboard (Layout 1)", "keyboard_p1")
        self.p1_device_combo.addItem("Keyboard (Layout 2)", "keyboard_p2")
        self.p2_device_combo.addItem("Keyboard (Layout 1)", "keyboard_p1")
        self.p2_device_combo.addItem("Keyboard (Layout 2)", "keyboard_p2")

        for i, (display_name, internal_id) in enumerate(available_joysticks):
            self.p1_device_combo.addItem(display_name, internal_id)
            self.p2_device_combo.addItem(display_name, internal_id)
            self.joystick_select_combo_for_mapping.addItem(f"Joy {i}: {display_name.split(': ', 1)[-1]}", i) # Store index as data

        # Restore selections
        idx = self.p1_device_combo.findData(current_p1_device)
        self.p1_device_combo.setCurrentIndex(idx if idx != -1 else 0)
        idx = self.p2_device_combo.findData(current_p2_device)
        self.p2_device_combo.setCurrentIndex(idx if idx != -1 else 0)

        if current_monitor_joy_idx_data is not None:
             idx = self.joystick_select_combo_for_mapping.findData(current_monitor_joy_idx_data)
             self.joystick_select_combo_for_mapping.setCurrentIndex(idx if idx != -1 else 0)
        elif self.joystick_select_combo_for_mapping.count() > 0:
            self.joystick_select_combo_for_mapping.setCurrentIndex(0)
        
        if self.joystick_select_combo_for_mapping.count() > 0 :
             self.on_monitor_joystick_changed(self.joystick_select_combo_for_mapping.currentIndex())
        else: # No joysticks, ensure thread knows not to monitor.
            self.controller_thread.set_joystick_to_monitor(-1) # Or an invalid index


    def on_monitor_joystick_changed(self, index: int):
        joy_idx_data = self.joystick_select_combo_for_mapping.itemData(index)
        if joy_idx_data is not None and isinstance(joy_idx_data, int):
            self.controller_thread.set_joystick_to_monitor(joy_idx_data)
        elif self.joystick_select_combo_for_mapping.count() == 0:
             self.controller_thread.set_joystick_to_monitor(-1) # Signal no joystick to monitor

    def load_settings_into_ui(self):
        game_config.load_config() # Ensure game_config module has the latest from file
        self.populate_joystick_device_combos() # Populates and then sets current from game_config

        idx = self.p1_device_combo.findData(game_config.CURRENT_P1_INPUT_DEVICE)
        self.p1_device_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.p1_kbd_enable_check.setChecked(game_config.P1_KEYBOARD_ENABLED)
        self.p1_ctrl_enable_check.setChecked(game_config.P1_CONTROLLER_ENABLED)

        idx = self.p2_device_combo.findData(game_config.CURRENT_P2_INPUT_DEVICE)
        self.p2_device_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.p2_kbd_enable_check.setChecked(game_config.P2_KEYBOARD_ENABLED)
        self.p2_ctrl_enable_check.setChecked(game_config.P2_CONTROLLER_ENABLED)

        # LOADED_PYGAME_JOYSTICK_MAPPINGS from config.py now holds the raw GUI format
        self.joystick_mappings_from_gui = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.copy()
        self.refresh_joystick_mappings_table()
        self.update_status_and_log("Settings loaded into UI.")

    def save_all_settings(self):
        game_config.CURRENT_P1_INPUT_DEVICE = self.p1_device_combo.currentData()
        game_config.P1_KEYBOARD_ENABLED = self.p1_kbd_enable_check.isChecked()
        game_config.P1_CONTROLLER_ENABLED = self.p1_ctrl_enable_check.isChecked()
        game_config.CURRENT_P2_INPUT_DEVICE = self.p2_device_combo.currentData()
        game_config.P2_KEYBOARD_ENABLED = self.p2_kbd_enable_check.isChecked()
        game_config.P2_CONTROLLER_ENABLED = self.p2_ctrl_enable_check.isChecked()
        
        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS = self.joystick_mappings_from_gui.copy()

        if game_config.save_config():
            self.update_status_and_log("All settings saved.")
            # The PygameControllerThread's mappings_ref needs to point to the *translated* version
            # So after saving, we should update the reference it holds.
            self.controller_thread.translated_mappings_for_triggering = game_config.get_translated_pygame_joystick_mappings()
        else:
            QMessageBox.critical(self, "Save Error", "Could not save settings.")
            self.update_status_and_log("Error saving settings.")

    def confirm_reset_all_settings(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Reset all input settings to default values?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.perform_reset_all_settings()

    def perform_reset_all_settings(self):
        game_config.CURRENT_P1_INPUT_DEVICE = game_config.DEFAULT_P1_INPUT_DEVICE
        game_config.P1_KEYBOARD_ENABLED = game_config.DEFAULT_P1_KEYBOARD_ENABLED
        game_config.P1_CONTROLLER_ENABLED = game_config.DEFAULT_P1_CONTROLLER_ENABLED
        game_config.CURRENT_P2_INPUT_DEVICE = game_config.DEFAULT_P2_INPUT_DEVICE
        game_config.P2_KEYBOARD_ENABLED = game_config.DEFAULT_P2_KEYBOARD_ENABLED
        game_config.P2_CONTROLLER_ENABLED = game_config.DEFAULT_P2_CONTROLLER_ENABLED
        self.joystick_mappings_from_gui.clear() # Clear local GUI store
        game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.clear() # Clear the one that will be saved
        game_config._TRANSLATED_PYGAME_JOYSTICK_MAPPINGS_RUNTIME.clear() # Clear runtime translated one
        self.load_settings_into_ui()
        self.update_status_and_log("All settings reset to default. Save to make changes permanent.")

    def start_listening_for_joystick_map_from_button(self):
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map: return
        self.initiate_listening_sequence_for_joystick_map(internal_key_to_map)

    def initiate_listening_sequence_for_joystick_map(self, internal_key_to_map_str, originating_row=-1):
        self.current_listening_key_for_joystick_map = internal_key_to_map_str
        self.last_selected_row_for_joystick_mapping = originating_row
        self.controller_thread.start_listening()
        friendly_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key_to_map_str, internal_key_to_map_str)
        monitor_joy_text = self.joystick_select_combo_for_mapping.currentText()
        self.update_status_and_log(f"Listening for '{friendly_name}' on {monitor_joy_text}...")
        self.listen_button.setText("Listening..."); self.listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(False); self.joystick_select_combo_for_mapping.setEnabled(False)

    def on_controller_event_captured_for_mapping(self, event_details_from_thread: dict, raw_event_str: str):
        if not self.current_listening_key_for_joystick_map:
            self.reset_listening_ui_for_joystick_map(); return
        
        # Conflict checking logic (simplified example)
        for existing_key, mapping_info in list(self.joystick_mappings_from_gui.items()):
            if mapping_info and mapping_info.get("raw_str") == raw_event_str and existing_key != self.current_listening_key_for_joystick_map:
                # Basic conflict: same raw input string for a different action
                reply = QMessageBox.question(self, "Conflict", f"Input '{raw_event_str}' is already mapped to '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(existing_key, existing_key)}'. Overwrite?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    self.reset_listening_ui_for_joystick_map(); return
                del self.joystick_mappings_from_gui[existing_key] # Remove old mapping
                break
        
        self.joystick_mappings_from_gui[self.current_listening_key_for_joystick_map] = {
            "event_type": event_details_from_thread["type"],
            "details": event_details_from_thread, # Store the raw event details from thread
            "raw_str": raw_event_str,
            "friendly_name": raw_event_str # Default friendly name, can be changed by user
        }
        self.log_to_debug_console(f"Mapped '{raw_event_str}' to '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(self.current_listening_key_for_joystick_map, self.current_listening_key_for_joystick_map)}'")
        self.refresh_joystick_mappings_table(preserve_scroll=True, target_row_key=self.current_listening_key_for_joystick_map)
        self.reset_listening_ui_for_joystick_map(preserve_scroll=True)

    def reset_listening_ui_for_joystick_map(self, preserve_scroll=False):
        self.listen_button.setText("Listen for Controller Input")
        self.listen_button.setEnabled(True); self.key_to_map_combo.setEnabled(True)
        self.joystick_select_combo_for_mapping.setEnabled(True)
        self.controller_thread.stop_listening()
        self.current_listening_key_for_joystick_map = None
        if not preserve_scroll: self.last_selected_row_for_joystick_mapping = -1
        
    def on_mapped_event_triggered_for_simulation(self, internal_action_key_str, is_press_event):
        action_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_action_key_str, internal_action_key_str)
        pynput_key_to_simulate = get_pynput_key(internal_action_key_str)
        if pynput_key_to_simulate:
            try:
                if is_press_event:
                    if pynput_key_to_simulate not in self.currently_pressed_keys:
                        self.keyboard.press(pynput_key_to_simulate); self.currently_pressed_keys.add(pynput_key_to_simulate)
                        self.log_to_debug_console(f"Sim Press: {action_display_name} -> Key {str(pynput_key_to_simulate)}")
                else:
                    if pynput_key_to_simulate in self.currently_pressed_keys:
                        self.keyboard.release(pynput_key_to_simulate); self.currently_pressed_keys.remove(pynput_key_to_simulate)
                        self.log_to_debug_console(f"Sim Release: {action_display_name} -> Key {str(pynput_key_to_simulate)}")
            except Exception as e: logger_cmg.error(f"Pynput error for '{action_display_name}': {e}")
        elif internal_action_key_str not in EXCLUSIVE_ACTIONS and is_press_event:
             self.log_to_debug_console(f"Action Triggered (No Key Sim): {action_display_name}")

    def refresh_joystick_mappings_table(self, preserve_scroll=False, target_row_key=None):
        current_v_scroll_value = self.mappings_table.verticalScrollBar().value() if preserve_scroll else -1
        target_row_to_ensure_visible = -1
        self.mappings_table.setRowCount(0)
        for i, internal_key in enumerate(MAPPABLE_KEYS):
            friendly_display_name = INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key)
            if target_row_key and internal_key == target_row_key: target_row_to_ensure_visible = i
            mapping_info = self.joystick_mappings_from_gui.get(internal_key)
            row_pos = self.mappings_table.rowCount(); self.mappings_table.insertRow(row_pos)
            action_item = QTableWidgetItem(friendly_display_name); action_item.setData(Qt.UserRole, internal_key)
            self.mappings_table.setItem(row_pos, 0, action_item)
            if mapping_info:
                self.mappings_table.setItem(row_pos, 1, QTableWidgetItem(mapping_info.get("raw_str", "N/A")))
                rename_btn = QPushButton("Rename"); rename_btn.clicked.connect(lambda c, k=internal_key: self.rename_joystick_mapping_friendly_name_prompt(k))
                self.mappings_table.setCellWidget(row_pos, 2, rename_btn)
                clear_btn = QPushButton("Clear"); clear_btn.clicked.connect(lambda c, k=internal_key: self.clear_joystick_mapping(k))
                self.mappings_table.setCellWidget(row_pos, 3, clear_btn)
            else:
                self.mappings_table.setItem(row_pos, 1, QTableWidgetItem("Not Mapped"))
                self.mappings_table.setCellWidget(row_pos, 2, QPushButton("---", enabled=False))
                self.mappings_table.setCellWidget(row_pos, 3, QPushButton("---", enabled=False))
        if target_row_to_ensure_visible != -1: self.mappings_table.scrollToItem(self.mappings_table.item(target_row_to_ensure_visible, 0), QAbstractItemView.PositionAtCenter)
        elif preserve_scroll and current_v_scroll_value != -1: self.mappings_table.verticalScrollBar().setValue(current_v_scroll_value)
        if not preserve_scroll and not target_row_key: self.last_selected_row_for_joystick_mapping = -1

    def handle_table_double_click(self, row, column):
        action_item = self.mappings_table.item(row, 0)
        if not action_item: return
        internal_key_clicked = action_item.data(Qt.UserRole)
        if not internal_key_clicked: return
        if column <= 1: self.initiate_listening_sequence_for_joystick_map(internal_key_clicked, originating_row=row)

    def rename_joystick_mapping_friendly_name_prompt(self, internal_key):
        mapping_info = self.joystick_mappings_from_gui.get(internal_key)
        if mapping_info:
            current_label = mapping_info.get("raw_str", "") # Or use a separate "display_label" field
            text, ok = QInputDialog.getText(self, "Rename Input Label", f"Label for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key,internal_key)}':", QLineEdit.Normal, current_label)
            if ok and text:
                mapping_info["raw_str"] = text
                self.refresh_joystick_mappings_table(preserve_scroll=True, target_row_key=internal_key)

    def clear_joystick_mapping(self, internal_key):
        if internal_key in self.joystick_mappings_from_gui:
            del self.joystick_mappings_from_gui[internal_key]
            self.refresh_joystick_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.log_to_debug_console(f"Cleared joystick mapping for '{INTERNAL_TO_FRIENDLY_ACTION_DISPLAY.get(internal_key, internal_key)}'.")

    def closeEvent(self, event):
        logger_cmg.info("ControllerSettingsWindow closeEvent. Shutting down thread.")
        if hasattr(self, 'controller_thread') and self.controller_thread.isRunning():
            self.controller_thread.stop()
            if not self.controller_thread.wait(750):
                 logger_cmg.warning("Controller thread did not stop gracefully on close. May terminate.")
                 self.controller_thread.terminate()
                 self.controller_thread.wait(250)
        super().closeEvent(event)

if __name__ == "__main__":
    logger_cmg.info("ControllerSettingsWindow application starting (standalone)...")
    
    # Ensure Pygame is initialized for standalone run
    if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
        print("Standalone GUI: Pygame/Joystick not globally initialized by config.py on import. Attempting init now.")
        game_config.init_pygame_and_joystick_globally()
        if not game_config._joystick_initialized_globally:
            print("Standalone GUI: FAILED to initialize Pygame Joystick system. Controller functionality will be limited.")

    app = QApplication(sys.argv)
    
    # Load game config to make its values available to the GUI
    try:
        game_config.load_config() # This will populate game_config.CURRENT_* variables
    except Exception as e:
        logger_cmg.error(f"Standalone GUI: Error loading game_config: {e}")
        # GUI might still run with defaults or fallbacks from game_config.

    main_window_for_testing = QMainWindow()
    settings_widget = ControllerSettingsWindow()
    main_window_for_testing.setCentralWidget(settings_widget)
    main_window_for_testing.setWindowTitle("Test - Controller & Input Settings")
    main_window_for_testing.setGeometry(100, 100, 950, 800) # Increased height slightly
    main_window_for_testing.show()
    
    exit_code = app.exec()
    
    # Gracefully stop the thread if the window is closed
    if hasattr(settings_widget, 'controller_thread') and settings_widget.controller_thread.isRunning():
        settings_widget.controller_thread.stop()
        settings_widget.controller_thread.wait(500) # Brief wait

    # pygame.quit() should be called by the main application (app_core) usually.
    # If running this standalone, and pygame was initialized, quit it.
    if game_config._pygame_initialized_globally:
        if game_config._joystick_initialized_globally:
            pygame.joystick.quit()
        pygame.quit()
        logger_cmg.info("Standalone GUI: Pygame quit.")
        
    sys.exit(exit_code)