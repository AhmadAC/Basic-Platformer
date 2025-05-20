import sys
import json
import threading 
import time
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtCore import Qt, Slot, QTimer, QRectF 
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit
)
from PySide6.QtGui import QIcon, QTextCursor 
from PySide6.QtCore import Qt, QThread, Signal, Slot 

try:
    from pynput.keyboard import Controller as KeyboardController, Key as PynputKey
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("CONTROLLER_MAPPER_GUI: pynput library not found. Keyboard simulation will be disabled.")
    class KeyboardController:
        def press(self, key): pass
        def release(self, key): pass
    class PynputKey: 
        space = "space_key"; shift = "shift_key"; ctrl = "ctrl_key"; alt = "alt_key"

current_dir_mapper = os.path.dirname(os.path.abspath(__file__))
project_root_mapper = os.path.dirname(current_dir_mapper)
if project_root_mapper not in sys.path:
    sys.path.insert(0, project_root_mapper)

import joystick_handler

try:
    import inputs  # <--- MODIFIED HERE
    from inputs import GamePad, UnpluggedError 
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = True
except ImportError:
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = False
    class GamePad: 
        def __init__(self, gamepad_path=None, characterizing=False): self.name="DummyInputsGamePad"; self._Device__path = gamepad_path
        def read(self): return []
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
    class UnpluggedError(Exception): pass
    print("CONTROLLER_MAPPER_GUI: CRITICAL - 'inputs' library not found. Gamepad mapping will not function.")

if not logging.getLogger().hasHandlers(): 
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__) 


MAPPABLE_KEYS = [
    "MOVE_UP", "MOVE_LEFT", "MOVE_DOWN", "MOVE_RIGHT", "JUMP", "CROUCH", "INTERACT",
    "ATTACK_PRIMARY", "ATTACK_SECONDARY", "DASH", "ROLL", "RESET", "WEAPON_1", "WEAPON_2",
    "WEAPON_3", "WEAPON_4", "WEAPON_DPAD_UP", "WEAPON_DPAD_DOWN", "WEAPON_DPAD_LEFT",
    "WEAPON_DPAD_RIGHT", "MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN", "W", "A", "S", "D",
    "1", "2", "3", "4", "5", "Q", "E", "V", "B", "SPACE", "SHIFT", "CTRL", "ALT",
]
GAME_ACTIONS_FRIENDLY_NAMES = {
    "MOVE_UP": "Move UP/Aim Up", "MOVE_LEFT": "Move Left/Aim Left",
    "MOVE_DOWN": "Move DOWN/Aim Down", "MOVE_RIGHT": "Move Right/Aim Right",
    "JUMP": "Jump", "CROUCH": "Crouch/Toggle", "INTERACT": "Interact",
    "ATTACK_PRIMARY": "Primary Attack", "ATTACK_SECONDARY": "Secondary Attack",
    "DASH": "Dash", "ROLL": "Roll", "RESET": "Reset Action",
    "WEAPON_1": "Weapon 1", "WEAPON_2": "Weapon 2", "WEAPON_3": "Weapon 3", "WEAPON_4": "Weapon 4",
    "WEAPON_DPAD_UP": "Weapon D-Pad Up", "WEAPON_DPAD_DOWN": "Weapon D-Pad Down",
    "WEAPON_DPAD_LEFT": "Weapon D-Pad Left", "WEAPON_DPAD_RIGHT": "Weapon D-Pad Right",
    "MENU_CONFIRM": "Menu Confirm", "MENU_CANCEL": "Menu Cancel", "MENU_RETURN": "Menu/Pause",
    "W": "Sim: Key W", "A": "Sim: Key A", "S": "Sim: Key S", "D": "Sim: Key D", 
    "1": "Sim: Key 1", "2": "Sim: Key 2", "3": "Sim: Key 3", "4": "Sim: Key 4", "5": "Sim: Key 5",
    "Q": "Sim: Key Q", "E": "Sim: Key E", "V": "Sim: Key V", "B": "Sim: Key B",
    "SPACE": "Sim: Key Space", "SHIFT": "Sim: Key Shift", "CTRL": "Sim: Key Ctrl", "ALT": "Sim: Key Alt",
}
EXCLUSIVE_ACTIONS = ["MENU_RETURN"] 
AXIS_THRESHOLD = 0.7 
SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_FILE = os.path.join(SETTINGS_DIR, "controller_mappings.json")

def get_pynput_key(key_str: str) -> Optional[Any]: 
    if not PYNPUT_AVAILABLE: return None
    if key_str == "SPACE": return PynputKey.space
    if key_str == "SHIFT": return PynputKey.shift
    if key_str == "CTRL": return PynputKey.ctrl
    if key_str == "ALT": return PynputKey.alt
    if len(key_str) == 1 and key_str.isalnum(): return key_str.lower()
    if key_str == "W": return 'w'
    if key_str == "A": return 'a'
    if key_str == "S": return 's'
    if key_str == "D": return 'd'
    return None

class InputsControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool) 
    controllerStatusUpdate = Signal(str) 

    def __init__(self, mappings_ref: Dict, gamepad_device_obj: Optional[GamePad] = None, parent=None):
        super().__init__(parent)
        self.mappings = mappings_ref 
        self.gamepad_instance = gamepad_device_obj
        self.is_listening_for_mapping = False
        self._stop_requested = False
        self.active_axis_details: Dict[str, bool] = {} 
        self.active_hat_details: Dict[str, bool] = {} 
        self.active_hat_values: Dict[int, Tuple[int, int]] = {} 

    def run(self):
        if not INPUTS_LIB_AVAILABLE_FOR_MAPPER or not self.gamepad_instance:
            self.controllerStatusUpdate.emit("Error: 'inputs' library or gamepad instance missing.")
            return
        gamepad_name = getattr(self.gamepad_instance, 'name', 'Unknown Gamepad')
        self.controllerStatusUpdate.emit(f"Listening on: {gamepad_name}")
        logger.info(f"InputsControllerThread: Started for gamepad: {gamepad_name}")
        try:
            while not self._stop_requested:
                try: events = self.gamepad_instance.read()
                except (UnpluggedError, EOFError, OSError) as e_read: 
                    self.controllerStatusUpdate.emit(f"Gamepad disconnected or read error: {gamepad_name} ({type(e_read).__name__})")
                    logger.warning(f"InputsControllerThread: Gamepad read issue for {gamepad_name}: {e_read}")
                    break
                except Exception as e: 
                    self.controllerStatusUpdate.emit(f"Unexpected error reading {gamepad_name}: {str(e)[:50]}")
                    logger.error(f"InputsControllerThread: Unexpected read error: {e}", exc_info=True)
                    time.sleep(0.1); continue

                for event in events:
                    if self._stop_requested: break
                    event_details: Optional[Dict] = None; raw_event_str = f"{event.ev_type} {event.code} {event.state}"
                    if event.ev_type == "Key": 
                        event_details = {"type": "button", "button_id": event.code, "state": event.state}
                        raw_event_str = f"Button {event.code} {'Pressed' if event.state == 1 else 'Released'}"
                    elif event.ev_type == "Absolute":
                        if "ABS_HAT" in event.code:
                            try: hat_id = int(event.code[7]); axis = event.code[8]
                            except (IndexError, ValueError): logger.warning(f"Could not parse hat event code: {event.code}"); continue
                            current_x, current_y = self.active_hat_values.get(hat_id, (0,0))
                            if axis == 'X': current_x = event.state
                            else: current_y = event.state 
                            new_hat_value = (current_x, current_y)
                            self.active_hat_values[hat_id] = new_hat_value
                            event_details = {"type": "hat", "hat_id": hat_id, "value": new_hat_value}
                            raw_event_str = f"Hat {hat_id} Value: {new_hat_value}"
                        else: 
                            direction = 0
                            if event.state > AXIS_THRESHOLD: direction = 1
                            elif event.state < -AXIS_THRESHOLD: direction = -1
                            if direction != 0 or self.active_axis_details.get(f"axis_{event.code}_{1}") or self.active_axis_details.get(f"axis_{event.code}_{-1}"):
                                event_details = {"type": "axis", "axis_id": event.code, "direction": direction, "value": event.state, "threshold": AXIS_THRESHOLD}
                                raw_event_str = f"Axis {event.code} Val:{event.state:.2f} Dir:{direction}"
                    
                    if self.is_listening_for_mapping and event_details:
                        should_capture = (event_details["type"] == "button" and event_details.get("state") == 1) or \
                                         (event_details["type"] == "axis" and event_details.get("direction") != 0) or \
                                         (event_details["type"] == "hat" and event_details.get("value") != (0,0))
                        if should_capture:
                            logger.info(f"Event captured for mapping: {raw_event_str} -> {event_details}")
                            self.controllerEventCaptured.emit(event_details.copy(), raw_event_str) 
                            self.is_listening_for_mapping = False 
                    elif not self.is_listening_for_mapping and event_details and self.mappings:
                        self.process_event_for_mapped_actions(event_details)
                if not events: time.sleep(0.005) 
        finally:
            logger.info(f"InputsControllerThread: Event loop for {gamepad_name} stopped.")
            self.controllerStatusUpdate.emit(f"Controller thread for {gamepad_name} stopped.")

    def process_event_for_mapped_actions(self, event_details: Dict):
        for internal_action_key, mapping_info in self.mappings.items():
            if not mapping_info: continue
            stored_event_type = mapping_info.get("event_type")
            stored_details = mapping_info.get("details", {})
            
            if stored_event_type == event_details.get("type"):
                if stored_event_type == "button" and stored_details.get("button_id") == event_details.get("button_id"):
                    is_press = (event_details.get("state") == 1)
                    self.mappedEventTriggered.emit(internal_action_key, is_press)
                    if internal_action_key in EXCLUSIVE_ACTIONS and is_press: break
                elif stored_event_type == "axis" and stored_details.get("axis_id") == event_details.get("axis_id"):
                    event_direction = event_details.get("direction", 0)
                    mapped_direction = stored_details.get("direction")
                    active_key = f"axis_{event_details.get('axis_id')}_{mapped_direction}"
                    if event_direction == mapped_direction and mapped_direction != 0:
                        if not self.active_axis_details.get(active_key):
                            self.mappedEventTriggered.emit(internal_action_key, True)
                            self.active_axis_details[active_key] = True
                            if internal_action_key in EXCLUSIVE_ACTIONS: break
                    elif self.active_axis_details.get(active_key): 
                        self.mappedEventTriggered.emit(internal_action_key, False)
                        del self.active_axis_details[active_key]
                elif stored_event_type == "hat" and stored_details.get("hat_id") == event_details.get("hat_id"):
                    mapped_hat_value = tuple(stored_details.get("value", (0,0)))
                    current_event_hat_value = tuple(event_details.get("value", (0,0)))
                    active_key = f"hat_{event_details.get('hat_id')}_{mapped_hat_value}"
                    if current_event_hat_value == mapped_hat_value and mapped_hat_value != (0,0):
                        if not self.active_hat_details.get(active_key):
                            self.mappedEventTriggered.emit(internal_action_key, True)
                            self.active_hat_details[active_key] = True
                            if internal_action_key in EXCLUSIVE_ACTIONS: break
                    elif self.active_hat_details.get(active_key) and current_event_hat_value != mapped_hat_value:
                        self.mappedEventTriggered.emit(internal_action_key, False)
                        del self.active_hat_details[active_key]

    def stop_listening(self): self.is_listening_for_mapping = False
    def start_listening(self): self.is_listening_for_mapping = True
    def request_stop(self): self._stop_requested = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Mapper v1.2 (inputs lib)") 
        self.setGeometry(100, 100, 850, 700)

        if PYNPUT_AVAILABLE: self.keyboard_simulator = KeyboardController()
        else: self.keyboard_simulator = None 
        
        self.currently_pressed_sim_keys: Dict[str, bool] = {} 
        self.mappings: Dict[str, Dict] = {} 
        self.current_listening_key: Optional[str] = None
        self.last_selected_row_for_mapping = -1
        self.selected_gamepad_instance: Optional[GamePad] = None

        logger.info("Controller Mapper MainWindow initializing...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        gamepad_selection_layout = QHBoxLayout()
        gamepad_selection_layout.addWidget(QLabel("Gamepad:"))
        self.gamepad_combo = QComboBox()
        gamepad_selection_layout.addWidget(self.gamepad_combo)
        refresh_gamepads_button = QPushButton("Refresh/Detect Gamepads")
        refresh_gamepads_button.clicked.connect(self.populate_gamepad_combo)
        gamepad_selection_layout.addWidget(refresh_gamepads_button)
        main_layout.addLayout(gamepad_selection_layout)
        
        self.status_label = QLabel("Initializing... Click 'Refresh/Detect Gamepads'.") 
        main_layout.addWidget(self.status_label)
        
        mapping_controls_layout = QHBoxLayout()
        self.key_to_map_combo = QComboBox()
        for internal_key in MAPPABLE_KEYS:
            self.key_to_map_combo.addItem(GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key), userData=internal_key)
        mapping_controls_layout.addWidget(QLabel("Action to Map:"))
        mapping_controls_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Listen for Controller Input")
        self.listen_button.clicked.connect(self.start_listening_for_map_from_button)
        self.listen_button.setEnabled(False)
        mapping_controls_layout.addWidget(self.listen_button)
        main_layout.addLayout(mapping_controls_layout)

        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(5) 
        self.mappings_table.setHorizontalHeaderLabels(["Action/Key", "Controller Input", "Current Friendly Name", "Rename", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        self.mappings_table.setColumnWidth(1, 220) 
        self.mappings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mappings_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click) 
        main_layout.addWidget(self.mappings_table)
        
        file_buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save Mappings"); save_button.clicked.connect(self.save_mappings_to_file) 
        load_button = QPushButton("Reload Mappings"); load_button.clicked.connect(self.load_mappings_and_refresh)
        reset_button = QPushButton("Reset All Mappings"); reset_button.clicked.connect(self.confirm_reset_all_mappings)
        file_buttons_layout.addWidget(save_button); file_buttons_layout.addWidget(load_button); file_buttons_layout.addWidget(reset_button)
        main_layout.addLayout(file_buttons_layout)

        main_layout.addWidget(QLabel("Debug Log:"))
        self.debug_console = QTextEdit(); self.debug_console.setReadOnly(True); self.debug_console.setFixedHeight(100) 
        main_layout.addWidget(self.debug_console)

        self.controller_thread: Optional[InputsControllerThread] = None
        
        self._load_mappings_from_file() 
        self.refresh_mappings_table()
        
        self.gamepad_combo.currentIndexChanged.connect(self.on_gamepad_selection_changed)
        QTimer.singleShot(100, self.populate_gamepad_combo)

        logger.info("Controller Mapper MainWindow initialized.")

    def log_to_debug_console(self, message: str):
        if hasattr(self, 'debug_console') and self.debug_console:
            try:
                current_time_str = time.strftime("%H:%M:%S", time.localtime())
                self.debug_console.append(f"[{current_time_str}] {message}")
                self.debug_console.moveCursor(QTextCursor.MoveOperation.End) 
            except Exception as e:
                print(f"ERROR appending to debug_console: {e}. Message: {message}")
                logger.error(f"Error appending to GUI debug_console: {e}", exc_info=True)
        else:
            print(f"DEBUG_CONSOLE_FALLBACK: {message}")
            logger.warning(f"log_to_debug_console called but self.debug_console not available. Message: {message}")

    def update_status_and_log(self, message: str, log_to_console: bool = True):
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(message)
        else:
            logger.warning(f"update_status_and_log: self.status_label not available. Message: {message}")
            
        if log_to_console:
            self.log_to_debug_console(message) 
        
        logger.info(f"GUI Status: {message}") 

    def _load_mappings_from_file(self): 
        self.mappings = {} 
        if os.path.exists(MAPPINGS_FILE):
            try:
                with open(MAPPINGS_FILE, 'r') as f:
                    loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    self.mappings = loaded_data
                    self.log_to_debug_console(f"Mappings loaded from {MAPPINGS_FILE}")
                else:
                    self.log_to_debug_console(f"Warning: Data in {MAPPINGS_FILE} is not a dictionary. Using empty mappings.")
            except json.JSONDecodeError:
                self.log_to_debug_console(f"Error: Could not decode JSON from {MAPPINGS_FILE}. Using empty mappings.")
                QMessageBox.warning(self, "Load Error", f"Could not parse {MAPPINGS_FILE}. Check file integrity.")
            except Exception as e:
                self.log_to_debug_console(f"Error loading mappings: {e}. Using empty mappings.")
        else:
            self.log_to_debug_console(f"Mappings file {MAPPINGS_FILE} not found. Starting with empty/default mappings.")
        self.refresh_mappings_table() 

    def load_mappings_and_refresh(self): 
        self._load_mappings_from_file() 
        if self.controller_thread and self.controller_thread.isRunning() and self.selected_gamepad_instance:
            self.update_status_and_log("Reloading mappings. Restarting controller listener...")
            self.on_gamepad_selection_changed(self.gamepad_combo.currentIndex()) 
        else:
            self.update_status_and_log("Mappings reloaded from file.")


    def save_mappings_to_file(self): 
        try:
            with open(MAPPINGS_FILE, 'w') as f:
                json.dump(self.mappings, f, indent=4)
            self.update_status_and_log(f"Mappings saved to {MAPPINGS_FILE}")
        except IOError as e:
            self.update_status_and_log(f"Error saving mappings: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save mappings to {MAPPINGS_FILE}:\n{e}")
    
    def refresh_mappings_table(self, preserve_scroll: bool = False, target_row_key: Optional[str] = None):
        current_scroll_v = self.mappings_table.verticalScrollBar().value() if preserve_scroll else 0
        current_scroll_h = self.mappings_table.horizontalScrollBar().value() if preserve_scroll else 0
        self.mappings_table.setRowCount(0) 
        
        row_to_select_after_refresh = -1

        for internal_key in MAPPABLE_KEYS: 
            mapping_info = self.mappings.get(internal_key)
            row_position = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row_position)

            action_item = QTableWidgetItem(GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key))
            action_item.setData(Qt.ItemDataRole.UserRole, internal_key) 
            self.mappings_table.setItem(row_position, 0, action_item)

            if mapping_info and isinstance(mapping_info, dict):
                raw_str_display = mapping_info.get("raw_str", "Not Set")
                controller_input_item = QTableWidgetItem(raw_str_display)
                self.mappings_table.setItem(row_position, 1, controller_input_item)

                friendly_name_display = mapping_info.get("friendly_name", raw_str_display) 
                friendly_name_item = QTableWidgetItem(friendly_name_display)
                self.mappings_table.setItem(row_position, 2, friendly_name_item)

                rename_button = QPushButton("Rename Friendly")
                rename_button.clicked.connect(lambda checked=False, k=internal_key: self.rename_friendly_name_for_action(k))
                self.mappings_table.setCellWidget(row_position, 3, rename_button)
                
                clear_button = QPushButton("Clear")
                clear_button.clicked.connect(lambda checked=False, k=internal_key: self.clear_mapping_for_action(k))
                self.mappings_table.setCellWidget(row_position, 4, clear_button)
            else:
                self.mappings_table.setItem(row_position, 1, QTableWidgetItem("Not Set"))
                self.mappings_table.setItem(row_position, 2, QTableWidgetItem("N/A"))
                map_button = QPushButton("Assign Input")
                map_button.clicked.connect(lambda checked=False, k=internal_key, r=row_position: self.initiate_listening_sequence(k, r))
                self.mappings_table.setCellWidget(row_position, 3, map_button) 
                self.mappings_table.setCellWidget(row_position, 4, QLabel("")) 

            if target_row_key and internal_key == target_row_key:
                row_to_select_after_refresh = row_position
        
        if row_to_select_after_refresh != -1:
            self.mappings_table.selectRow(row_to_select_after_refresh)
            self.mappings_table.scrollToItem(self.mappings_table.item(row_to_select_after_refresh, 0), QAbstractItemView.ScrollHint.PositionAtCenter)

        if preserve_scroll:
            QTimer.singleShot(0, lambda: self.mappings_table.verticalScrollBar().setValue(current_scroll_v))
            QTimer.singleShot(0, lambda: self.mappings_table.horizontalScrollBar().setValue(current_scroll_h))
        self.mappings_table.resizeColumnsToContents()
        self.mappings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
        self.mappings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 

    @Slot(str, bool)
    def on_mapped_event_triggered(self, internal_action_key_str: str, is_pressed: bool):
        if not self.keyboard_simulator: return
        pynput_target_key = get_pynput_key(internal_action_key_str)
        if not pynput_target_key: return
        
        logger.debug(f"Mapped event: {internal_action_key_str} ({pynput_target_key}), Pressed: {is_pressed}")
        try:
            if is_pressed:
                if not self.currently_pressed_sim_keys.get(internal_action_key_str):
                    self.keyboard_simulator.press(pynput_target_key)
                    self.currently_pressed_sim_keys[internal_action_key_str] = True
                    self.log_to_debug_console(f"Simulated PRESS: {internal_action_key_str} -> {pynput_target_key}")
            else:
                if self.currently_pressed_sim_keys.get(internal_action_key_str):
                    self.keyboard_simulator.release(pynput_target_key)
                    del self.currently_pressed_sim_keys[internal_action_key_str]
                    self.log_to_debug_console(f"Simulated RELEASE: {internal_action_key_str} -> {pynput_target_key}")
        except Exception as e: 
            logger.error(f"Pynput simulation error for key '{pynput_target_key}': {e}")
            self.log_to_debug_console(f"Pynput Error: {e}")
            if internal_action_key_str in self.currently_pressed_sim_keys:
                del self.currently_pressed_sim_keys[internal_action_key_str]

    def release_all_simulated_keys(self):
        if not self.keyboard_simulator: return
        for action_key, is_held in list(self.currently_pressed_sim_keys.items()): 
            if is_held:
                pynput_target_key = get_pynput_key(action_key)
                if pynput_target_key:
                    try:
                        self.keyboard_simulator.release(pynput_target_key)
                        logger.info(f"Released simulated key on exit: {action_key} -> {pynput_target_key}")
                    except Exception as e:
                        logger.warning(f"Error releasing simulated key {pynput_target_key} on exit: {e}")
            del self.currently_pressed_sim_keys[action_key]
        self.log_to_debug_console("All simulated keys released.")

    def reset_listening_ui(self, preserve_scroll=False):
        self.current_listening_key = None
        self.listen_button.setText("Listen for Controller Input")
        self.listen_button.setEnabled(self.selected_gamepad_instance is not None)
        self.key_to_map_combo.setEnabled(True)
        if self.controller_thread: self.controller_thread.stop_listening()
        if self.last_selected_row_for_mapping != -1 and preserve_scroll:
            self.mappings_table.selectRow(self.last_selected_row_for_mapping) 
            self.mappings_table.scrollToItem(self.mappings_table.item(self.last_selected_row_for_mapping,0), QAbstractItemView.ScrollHint.EnsureVisible)
        else: self.mappings_table.clearSelection()

    def handle_table_double_click(self, row: int, column: int):
        action_item = self.mappings_table.item(row, 0)
        if action_item:
            internal_key_to_map = action_item.data(Qt.ItemDataRole.UserRole)
            if internal_key_to_map and isinstance(internal_key_to_map, str):
                self.initiate_listening_sequence(internal_key_to_map, originating_row=row)

    def rename_friendly_name_for_action(self, internal_key: str):
        current_mapping = self.mappings.get(internal_key)
        if not current_mapping or not isinstance(current_mapping, dict):
            QMessageBox.information(self, "Rename Error", f"No mapping found for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'.")
            return
        
        current_friendly_name = current_mapping.get("friendly_name", current_mapping.get("raw_str", "Unnamed Input"))
        new_name, ok = QInputDialog.getText(self, "Rename Friendly Input Name", 
                                            f"Enter new friendly name for input mapped to:\n'{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'\n(Current: {current_friendly_name})", 
                                            QLineEdit.EchoMode.Normal, current_friendly_name)
        if ok and new_name:
            self.mappings[internal_key]["friendly_name"] = new_name.strip()
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.log_to_debug_console(f"Friendly name for '{internal_key}' updated to '{new_name.strip()}'.")

    def clear_mapping_for_action(self, internal_key: str):
        if internal_key in self.mappings:
            del self.mappings[internal_key]
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.update_status_and_log(f"Mapping cleared for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'.")
        else:
            self.update_status_and_log(f"No mapping to clear for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'.")

    def confirm_reset_all_mappings(self):
        reply = QMessageBox.question(self, "Confirm Reset", 
                                     "Are you sure you want to reset ALL controller mappings to empty?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.mappings.clear()
            self.refresh_mappings_table()
            self.update_status_and_log("All mappings have been reset.")

    def closeEvent(self, event):
        logger.info("Close event received. Shutting down mapper GUI.")
        if self.controller_thread and self.controller_thread.isRunning():
            self.update_status_and_log("Stopping controller thread...")
            self.controller_thread.request_stop()
            if not self.controller_thread.wait(1000): 
                logger.warning("Controller thread did not stop gracefully, terminating.")
                self.controller_thread.terminate() 
                self.controller_thread.wait() 
            self.controller_thread = None
            
        self.release_all_simulated_keys() 
        self.save_mappings_to_file() 
        
        super().closeEvent(event) 
        logger.info("Controller Mapper GUI closed.")

    def populate_gamepad_combo(self):
        self.log_to_debug_console("Attempting to detect gamepads...")
        self.gamepad_combo.blockSignals(True); self.gamepad_combo.clear()
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop(); self.controller_thread.wait(300); self.controller_thread = None
        self.listen_button.setEnabled(False)
        joystick_handler.init_joysticks() 
        
        found_devices_for_combo_internal = [] 
        if INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            try:
                self.log_to_debug_console("Scanning with inputs.DeviceManager().gamepads...")
                joystick_handler._gamepads_devices = [] 
                device_manager = inputs.DeviceManager() # type: ignore # This line needs 'inputs' module
                
                temp_instances_to_manage = []
                for device_input_obj in device_manager.gamepads:
                    if device_input_obj:
                        path = getattr(device_input_obj, '_Device__path', f"uid_{id(device_input_obj)}")
                        name = getattr(device_input_obj, 'name', f'Gamepad (Path: {os.path.basename(path)})')
                        dev_info_dict = {'name': name, 'path': path, 'instance': device_input_obj}
                        found_devices_for_combo_internal.append(dev_info_dict)
                        joystick_handler._gamepads_devices.append(dev_info_dict)
                        temp_instances_to_manage.append(device_input_obj) 
                
                if found_devices_for_combo_internal:
                    for dev_info in found_devices_for_combo_internal:
                        self.gamepad_combo.addItem(dev_info['name'], userData=dev_info)
                    self.log_to_debug_console(f"Found {len(found_devices_for_combo_internal)} gamepad(s). Select one.")
                else:
                    self.gamepad_combo.addItem("No gamepads detected by 'inputs'", userData=None)
                    self.log_to_debug_console("No gamepads detected by 'inputs' library.")
            except Exception as e:
                self.gamepad_combo.addItem("Gamepad detection error", userData=None)
                self.log_to_debug_console(f"Error during gamepad detection: {e}") # This will log the NameError if 'inputs' is not defined
        else: 
            self.gamepad_combo.addItem("'inputs' library missing", userData=None)
            self.log_to_debug_console("'inputs' library is not available for gamepad detection.")

        self.gamepad_combo.blockSignals(False)
        if self.gamepad_combo.count() > 0: 
            if self.gamepad_combo.itemData(0) is not None: 
                 self.on_gamepad_selection_changed(0)
            else: 
                 self.status_label.setText(self.gamepad_combo.itemText(0)) 
                 self.listen_button.setEnabled(False)
        else: 
            self.status_label.setText("No gamepads found to select.")


    @Slot(int)
    def on_gamepad_selection_changed(self, index: int):
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop()
            self.controller_thread.wait(500) 
            self.controller_thread = None
        self.selected_gamepad_instance = None 

        current_combo_data = self.gamepad_combo.itemData(index)
        if not current_combo_data or not isinstance(current_combo_data, dict):
            self.update_status_and_log("No valid gamepad data selected.")
            self.listen_button.setEnabled(False); return

        self.selected_gamepad_instance = current_combo_data.get('instance')
        if not self.selected_gamepad_instance or not isinstance(self.selected_gamepad_instance, GamePad): # GamePad class must be defined
            self.update_status_and_log(f"Error: Invalid gamepad instance for {current_combo_data.get('name')}.")
            self.listen_button.setEnabled(False); return
        
        self.update_status_and_log(f"Selected: {current_combo_data.get('name')}. Starting listener thread.")
        self.listen_button.setEnabled(True)
        
        self.controller_thread = InputsControllerThread(self.mappings, gamepad_device_obj=self.selected_gamepad_instance)
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered)
        self.controller_thread.controllerStatusUpdate.connect(self.update_status_and_log) 
        self.controller_thread.start()

    def start_listening_for_map_from_button(self):
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map:
            logger.error("Could not get internal key from ComboBox."); QMessageBox.critical(self, "Error", "Internal error: Could not determine action to map."); return
        self.initiate_listening_sequence(internal_key_to_map)

    def initiate_listening_sequence(self, internal_key_to_map_str: str, originating_row: int = -1):
        if not self.controller_thread or not self.controller_thread.isRunning():
            QMessageBox.warning(self, "No Controller", "Controller thread not running. Select & ensure gamepad is connected."); self.reset_listening_ui(); return
        if self.listen_button.text().startswith("Listening...") :
            if self.current_listening_key and self.current_listening_key != internal_key_to_map_str:
                 QMessageBox.information(self, "Busy", f"Already listening for '{GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)}'."); return
            elif not self.current_listening_key: self.reset_listening_ui() 
        self.current_listening_key = internal_key_to_map_str; self.last_selected_row_for_mapping = originating_row
        index = self.key_to_map_combo.findData(self.current_listening_key)
        if index != -1 and self.key_to_map_combo.currentIndex() != index: self.key_to_map_combo.setCurrentIndex(index)
        self.controller_thread.start_listening()
        friendly_name_for_status = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        self.update_status_and_log(f"Listening for input for '{friendly_name_for_status}'...")
        self.listen_button.setText(f"Listening for: {friendly_name_for_status[:20]}..."); self.listen_button.setEnabled(False); self.key_to_map_combo.setEnabled(False)

    @Slot(dict, str)
    def on_controller_event_captured(self, event_details: Dict, raw_event_str: str):
        if not self.current_listening_key: self.reset_listening_ui(); return 
        friendly_name_current_key = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        logger.info(f"Captured for '{friendly_name_current_key}': {raw_event_str} -> {event_details}")
        
        captured_event_unique_id = f"{event_details['type']}_"
        if event_details['type'] == 'button': captured_event_unique_id += str(event_details.get('button_id'))
        elif event_details['type'] == 'axis': captured_event_unique_id += f"{event_details.get('axis_id')}_{event_details.get('direction')}"
        elif event_details['type'] == 'hat': captured_event_unique_id += f"{event_details.get('hat_id')}_{str(tuple(event_details.get('value', (0,0))))}"
        else: captured_event_unique_id += "unknown_event"

        keys_to_unmap_due_to_conflict = []
        is_current_key_exclusive = self.current_listening_key in EXCLUSIVE_ACTIONS

        for existing_internal_key, mapping_info in list(self.mappings.items()):
            if not mapping_info or not isinstance(mapping_info.get("details"), dict): continue
            stored_event_details = mapping_info["details"]
            stored_unique_id = f"{stored_event_details.get('type', 'unknown_type')}_"
            if stored_event_details.get('type') == 'button': stored_unique_id += str(stored_event_details.get('button_id'))
            elif stored_event_details.get('type') == 'axis': stored_unique_id += f"{stored_event_details.get('axis_id')}_{stored_event_details.get('direction')}"
            elif stored_event_details.get('type') == 'hat': stored_unique_id += f"{stored_event_details.get('hat_id')}_{str(tuple(stored_event_details.get('value',(0,0))))}"
            else: stored_unique_id += "unknown_stored_event"

            if stored_unique_id == captured_event_unique_id: 
                if existing_internal_key == self.current_listening_key: continue 
                is_existing_key_exclusive = existing_internal_key in EXCLUSIVE_ACTIONS
                if is_current_key_exclusive or is_existing_key_exclusive:
                    keys_to_unmap_due_to_conflict.append(existing_internal_key)
        
        if keys_to_unmap_due_to_conflict:
            conflict_details_str = "\n".join([f"- {GAME_ACTIONS_FRIENDLY_NAMES.get(k, k)}" for k in keys_to_unmap_due_to_conflict])
            reply = QMessageBox.question(self, "Confirm Reassignment", f"Input '{raw_event_str}' is used by:\n{conflict_details_str}\n\nMap '{friendly_name_current_key}' to this input and unmap others?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self.update_status_and_log(f"Mapping for '{friendly_name_current_key}' cancelled."); self.reset_listening_ui(preserve_scroll=True); return
            for key_to_remove in keys_to_unmap_due_to_conflict:
                if key_to_remove in self.mappings: del self.mappings[key_to_remove]

        self.mappings[self.current_listening_key] = {
            "event_type": event_details["type"], "details": event_details.copy(), 
            "raw_str": raw_event_str, 
            "friendly_name": f"{raw_event_str}" 
        }
        self.update_status_and_log(f"Mapped '{raw_event_str}' to '{friendly_name_current_key}'.")
        self.refresh_mappings_table(preserve_scroll=True, target_row_key=self.current_listening_key)
        self.reset_listening_ui(preserve_scroll=True)


if __name__ == "__main__":
    if not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
        try:
            app_temp = QApplication(sys.argv)
            QMessageBox.critical(None, "Missing Dependency", "The 'inputs' Python library is required.\nPlease install it: pip install inputs")
        except Exception as e: print(f"Could not show critical error dialog: {e}")
        sys.exit(1)
        
    logger.info("Controller Mapper GUI application starting...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    joystick_handler.quit_joysticks()
    logger.info(f"Controller Mapper GUI application finished with exit code: {exit_code}.")
    sys.exit(exit_code)