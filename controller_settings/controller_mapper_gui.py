import sys
import json
import threading 
import time
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from PySide6.QtCore import Qt, Slot, QTimer 
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit
)
from PySide6.QtGui import QIcon, QCloseEvent
from PySide6.QtCore import QThread, Signal 

# Pynput for keyboard simulation
try:
    from pynput.keyboard import Controller as KeyboardController, Key as PynputKey
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("CONTROLLER_MAPPER_GUI: pynput library not found. Keyboard simulation will be disabled.")
    class KeyboardController: # Dummy
        def press(self, key: Any): pass
        def release(self, key: Any): pass
    class PynputKey: # Dummy
        space = "space_key"; shift = "shift_key"; ctrl = "ctrl_key"; alt = "alt_key"

# Game-specific imports
current_dir_mapper = os.path.dirname(os.path.abspath(__file__))
project_root_mapper = os.path.dirname(current_dir_mapper)
if project_root_mapper not in sys.path:
    sys.path.insert(0, project_root_mapper)

import joystick_handler # Your refactored inputs-based handler
import inputs # Ensure inputs is imported here if used by joystick_handler or directly below

# 'inputs' library components
try:
    # from inputs import GamePad, UnpluggedError # Already imported via 'import inputs' implicitly
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = True
except ImportError: # This specific check for inputs.GamePad might not be needed if 'import inputs' fails first
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = False
    class GamePad: # Dummy
        def __init__(self, gamepad_path: Optional[str]=None, characterizing: bool=False): self.name="DummyInputsGamePad"; self._Device__path = gamepad_path
        def read(self) -> List[Any]: return []
        def __enter__(self) -> 'GamePad': return self
        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any): pass
    class UnpluggedError(Exception): pass # Dummy
    if 'inputs' not in sys.modules: # If the main 'inputs' import failed
        print("CONTROLLER_MAPPER_GUI: CRITICAL - 'inputs' library not found. Gamepad mapping will not function.")


# Configure logging
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__) # Use a named logger


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
    # Simple direct mapping for simulated keys based on their string representation
    sim_keys = {"W":'w', "A":'a', "S":'s', "D":'d', "Q":'q', "E":'e', "V":'v', "B":'b',
                "1":'1', "2":'2', "3":'3', "4":'4', "5":'5'}
    if key_str in sim_keys: return sim_keys[key_str]
    logger.warning(f"get_pynput_key: Unhandled key_str '{key_str}' for pynput simulation.")
    return None

class InputsControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerStatusUpdate = Signal(str)

    def __init__(self, mappings_ref: Dict[str, Any], gamepad_device_obj: Optional[inputs.GamePad] = None, parent: Optional[QWidget]=None): # type: ignore
        super().__init__(parent)
        self.mappings = mappings_ref
        self.gamepad_instance = gamepad_device_obj
        self.is_listening_for_mapping = False
        self._stop_requested = threading.Event() # Use threading.Event for safer stop request
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
            while not self._stop_requested.is_set():
                try:
                    events = self.gamepad_instance.read()
                except (inputs.UnpluggedError, EOFError, OSError) as e_read: # type: ignore
                    self.controllerStatusUpdate.emit(f"Gamepad disconnected or read error: {gamepad_name} ({type(e_read).__name__})")
                    logger.warning(f"InputsControllerThread: Gamepad read issue for {gamepad_name}: {e_read}")
                    break 
                except Exception as e:
                    self.controllerStatusUpdate.emit(f"Unexpected error reading {gamepad_name}: {str(e)[:50]}")
                    logger.error(f"InputsControllerThread: Unexpected read error: {e}", exc_info=True)
                    if not self._stop_requested.wait(0.1): continue # Small pause, then re-check stop
                    else: break

                for event in events:
                    if self._stop_requested.is_set(): break
                    event_details: Optional[Dict[str, Any]] = None
                    raw_event_str = f"{event.ev_type} {event.code} {event.state}"
                    
                    if event.ev_type == "Key":
                        event_details = {"type": "button", "button_id": event.code, "state": event.state}
                        raw_event_str = f"Button {event.code} {'Pressed' if event.state == 1 else 'Released'}"
                    elif event.ev_type == "Absolute":
                        if "ABS_HAT" in event.code and len(event.code) > 7:
                            try: hat_id = int(event.code[7]); axis_char = event.code[8]
                            except (IndexError, ValueError): logger.warning(f"Could not parse hat event code: {event.code}"); continue
                            current_x, current_y = self.active_hat_values.get(hat_id, (0,0))
                            if axis_char == 'X': current_x = event.state
                            elif axis_char == 'Y': current_y = event.state
                            else: logger.warning(f"Unknown hat axis: {axis_char} in {event.code}"); continue
                            new_hat_value = (current_x, current_y)
                            self.active_hat_values[hat_id] = new_hat_value
                            event_details = {"type": "hat", "hat_id": hat_id, "value": new_hat_value}
                            raw_event_str = f"Hat {hat_id} Value: {new_hat_value}"
                        else: # Analog stick
                            direction = 0
                            if event.state > AXIS_THRESHOLD: direction = 1
                            elif event.state < -AXIS_THRESHOLD: direction = -1
                            active_key_plus = f"axis_{event.code}_{1}"
                            active_key_minus = f"axis_{event.code}_{-1}"
                            if direction != 0 or self.active_axis_details.get(active_key_plus) or self.active_axis_details.get(active_key_minus) :
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
                
                if not events and not self._stop_requested.wait(0.005): continue # Non-blocking sleep
                elif self._stop_requested.is_set(): break
        finally:
            logger.info(f"InputsControllerThread: Event loop for {gamepad_name} stopped.")
            self.controllerStatusUpdate.emit(f"Controller thread for {gamepad_name} stopped.")

    def process_event_for_mapped_actions(self, event_details: Dict[str, Any]):
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
    def request_stop(self): self._stop_requested.set()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Mapper v1.2 (inputs lib)")
        self.setGeometry(100, 100, 850, 700)

        if PYNPUT_AVAILABLE: self.keyboard_simulator = KeyboardController()
        else: self.keyboard_simulator = None 
        
        self.currently_pressed_sim_keys: Dict[str, bool] = {}
        self.mappings: Dict[str, Dict[str, Any]] = {}
        self.current_listening_key: Optional[str] = None
        self.last_selected_row_for_mapping = -1
        self.selected_gamepad_instance: Optional[inputs.GamePad] = None # type: ignore

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
        # self.mappings_table.setColumnWidth(1, 220) # Let stretch handle it
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
        if hasattr(self, 'debug_console') and isinstance(self.debug_console, QTextEdit):
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()
        else:
            logger.info(f"DebugConsole (fallback during init?): {message}")

    def _load_mappings_from_file(self):
        self.mappings = {} 
        if os.path.exists(MAPPINGS_FILE):
            try:
                with open(MAPPINGS_FILE, 'r') as f: loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    self.mappings = loaded_data
                    self.log_to_debug_console(f"Mappings loaded from {MAPPINGS_FILE}")
                else: self.log_to_debug_console(f"Warning: Data in {MAPPINGS_FILE} is not a dictionary.")
            except json.JSONDecodeError:
                self.log_to_debug_console(f"Error: Could not decode JSON from {MAPPINGS_FILE}.")
                QMessageBox.warning(self, "Load Error", f"Could not parse {MAPPINGS_FILE}.")
            except Exception as e: self.log_to_debug_console(f"Error loading mappings: {e}.")
        else: self.log_to_debug_console(f"Mappings file {MAPPINGS_FILE} not found.")

    def load_mappings_and_refresh(self):
        self._load_mappings_from_file()
        self.refresh_mappings_table()
        if self.controller_thread and self.controller_thread.isRunning() and self.selected_gamepad_instance:
            self.update_status_and_log("Reloading mappings. Restarting controller listener...")
            self.on_gamepad_selection_changed(self.gamepad_combo.currentIndex())
        else: self.update_status_and_log("Mappings reloaded from file.")

    def save_mappings_to_file(self):
        try:
            with open(MAPPINGS_FILE, 'w') as f: json.dump(self.mappings, f, indent=4)
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
            row = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row)
            action_item = QTableWidgetItem(GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key))
            action_item.setData(Qt.ItemDataRole.UserRole, internal_key)
            self.mappings_table.setItem(row, 0, action_item)

            if mapping_info and isinstance(mapping_info, dict):
                raw_str = mapping_info.get("raw_str", "Not Set")
                self.mappings_table.setItem(row, 1, QTableWidgetItem(raw_str))
                self.mappings_table.setItem(row, 2, QTableWidgetItem(mapping_info.get("friendly_name", raw_str)))
                rename_btn = QPushButton("Rename"); rename_btn.clicked.connect(lambda c, k=internal_key: self.rename_friendly_name_for_action(k))
                clear_btn = QPushButton("Clear"); clear_btn.clicked.connect(lambda c, k=internal_key: self.clear_mapping_for_action(k))
                self.mappings_table.setCellWidget(row, 3, rename_btn)
                self.mappings_table.setCellWidget(row, 4, clear_btn)
            else:
                self.mappings_table.setItem(row, 1, QTableWidgetItem("Not Set"))
                self.mappings_table.setItem(row, 2, QTableWidgetItem("N/A"))
                assign_btn = QPushButton("Assign"); assign_btn.clicked.connect(lambda c, k=internal_key, r=row: self.initiate_listening_sequence(k,r))
                self.mappings_table.setCellWidget(row, 3, assign_btn) # Assign button in rename column for unassigned
                self.mappings_table.setCellWidget(row, 4, QLabel("")) # Empty in clear column
            if target_row_key and internal_key == target_row_key: row_to_select_after_refresh = row
        
        if row_to_select_after_refresh != -1:
            self.mappings_table.selectRow(row_to_select_after_refresh)
            self.mappings_table.scrollToItem(self.mappings_table.item(row_to_select_after_refresh, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        
        # Adjust column sizes after populating
        self.mappings_table.resizeColumnToContents(0) 
        self.mappings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.mappings_table.resizeColumnToContents(3)
        self.mappings_table.resizeColumnToContents(4)
        
        if preserve_scroll:
            QTimer.singleShot(0, lambda: self.mappings_table.verticalScrollBar().setValue(current_scroll_v))
            QTimer.singleShot(0, lambda: self.mappings_table.horizontalScrollBar().setValue(current_scroll_h))


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
            if internal_action_key_str in self.currently_pressed_sim_keys: del self.currently_pressed_sim_keys[internal_action_key_str]

    def release_all_simulated_keys(self):
        if not self.keyboard_simulator: return
        for action_key in list(self.currently_pressed_sim_keys.keys()):
            if self.currently_pressed_sim_keys.get(action_key):
                pynput_target_key = get_pynput_key(action_key)
                if pynput_target_key:
                    try: self.keyboard_simulator.release(pynput_target_key); logger.info(f"Released sim key on exit: {action_key}")
                    except Exception as e: logger.warning(f"Error releasing sim key {pynput_target_key} on exit: {e}")
            del self.currently_pressed_sim_keys[action_key]
        self.log_to_debug_console("All simulated keys released.")

    def reset_listening_ui(self, preserve_scroll: bool = False):
        self.current_listening_key = None
        self.listen_button.setText("Listen for Controller Input")
        self.listen_button.setEnabled(self.selected_gamepad_instance is not None)
        self.key_to_map_combo.setEnabled(True)
        if self.controller_thread: self.controller_thread.stop_listening()
        if self.last_selected_row_for_mapping != -1 and preserve_scroll:
            self.mappings_table.selectRow(self.last_selected_row_for_mapping)
            self.mappings_table.scrollToItem(self.mappings_table.item(self.last_selected_row_for_mapping,0), QAbstractItemView.ScrollHint.EnsureVisible)
        else: self.mappings_table.clearSelection()
        self.last_selected_row_for_mapping = -1 

    def handle_table_double_click(self, row: int, column: int):
        action_item = self.mappings_table.item(row, 0)
        if action_item:
            internal_key_to_map = action_item.data(Qt.ItemDataRole.UserRole)
            if internal_key_to_map and isinstance(internal_key_to_map, str):
                self.initiate_listening_sequence(internal_key_to_map, originating_row=row)

    def rename_friendly_name_for_action(self, internal_key: str):
        current_mapping = self.mappings.get(internal_key)
        if not current_mapping or not isinstance(current_mapping, dict):
            QMessageBox.information(self, "Rename Error", f"No mapping found for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'."); return
        current_friendly_name = current_mapping.get("friendly_name", current_mapping.get("raw_str", "Unnamed Input"))
        new_name, ok = QInputDialog.getText(self, "Rename Friendly Input Name", 
                                            f"Action: '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'\nInput: {current_mapping.get('raw_str', 'N/A')}\n\nEnter new friendly name:", 
                                            QLineEdit.EchoMode.Normal, current_friendly_name)
        if ok and new_name.strip():
            self.mappings[internal_key]["friendly_name"] = new_name.strip()
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.log_to_debug_console(f"Friendly name for '{internal_key}' updated to '{new_name.strip()}'.")

    def clear_mapping_for_action(self, internal_key: str):
        if internal_key in self.mappings:
            del self.mappings[internal_key]
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.update_status_and_log(f"Mapping cleared for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'.")
        else: self.update_status_and_log(f"No mapping to clear for '{GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)}'.")

    def confirm_reset_all_mappings(self):
        reply = QMessageBox.question(self, "Confirm Reset", "Reset ALL controller mappings to empty?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.mappings.clear(); self.refresh_mappings_table(); self.update_status_and_log("All mappings have been reset.")

    def closeEvent(self, event: Optional[QCloseEvent]): 
        logger.info("Close event received for Controller Mapper GUI.")
        if self.controller_thread and self.controller_thread.isRunning():
            self.update_status_and_log("Stopping controller thread...")
            self.controller_thread.request_stop()
            if not self.controller_thread.wait(1000):
                logger.warning("Controller thread did not stop gracefully, terminating."); self.controller_thread.terminate(); self.controller_thread.wait()
            self.controller_thread = None
        self.release_all_simulated_keys()
        self.save_mappings_to_file()
        if event: super().closeEvent(event) 
        logger.info("Controller Mapper GUI closed/cleaned up.")

    def populate_gamepad_combo(self):
        self.log_to_debug_console("Attempting to detect gamepads...")
        self.gamepad_combo.blockSignals(True); self.gamepad_combo.clear()
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop(); self.controller_thread.wait(300); self.controller_thread = None
        self.listen_button.setEnabled(False)
        joystick_handler.init_joysticks() # Ensure joystick_handler is aware (might be redundant if it's singleton)
        
        detected_devices_info = []
        if INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            try:
                logger.debug("Scanning with inputs.DeviceManager().gamepads...")
                # Ensure joystick_handler internal list is also managed if it's a shared source of truth
                # This direct manipulation is okay if this GUI is the primary user of this part of joystick_handler
                if hasattr(joystick_handler, '_gamepads_devices'): joystick_handler._gamepads_devices = [] 
                
                device_manager = inputs.DeviceManager() # type: ignore
                for device_instance in device_manager.gamepads: # type: ignore
                    if device_instance:
                        path = getattr(device_instance, '_Device__path', f"uid_{id(device_instance)}")
                        name = getattr(device_instance, 'name', f'Gamepad (Path: {os.path.basename(path)})')
                        dev_info = {'name': name, 'path': path, 'instance': device_instance}
                        detected_devices_info.append(dev_info)
                        if hasattr(joystick_handler, '_gamepads_devices'): joystick_handler._gamepads_devices.append(dev_info)
                
                if detected_devices_info:
                    for dev_info in detected_devices_info: self.gamepad_combo.addItem(dev_info['name'], userData=dev_info)
                    self.log_to_debug_console(f"Found {len(detected_devices_info)} gamepad(s). Select one.")
                else: self.gamepad_combo.addItem("No gamepads detected by 'inputs'", userData=None)
            except RuntimeError as e: self.gamepad_combo.addItem("No gamepads (RuntimeError)", userData=None); self.log_to_debug_console(f"RuntimeError: {e}")
            except Exception as e: self.gamepad_combo.addItem("Detection error", userData=None); self.log_to_debug_console(f"Error detecting gamepads: {e}")
        else: self.gamepad_combo.addItem("'inputs' library missing", userData=None)

        self.gamepad_combo.blockSignals(False)
        if self.gamepad_combo.count() > 0 and self.gamepad_combo.itemData(0) is not None: 
            self.on_gamepad_selection_changed(0)
        elif self.gamepad_combo.count() > 0: 
             self.status_label.setText("No gamepads available for selection.")
        else:
             self.status_label.setText("No gamepads found.")

    @Slot(int)
    def on_gamepad_selection_changed(self, index: int):
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop(); self.controller_thread.wait(500); self.controller_thread = None
        self.selected_gamepad_instance = None

        device_info = self.gamepad_combo.itemData(index)
        if not device_info or not isinstance(device_info, dict) or not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            self.update_status_and_log("No valid gamepad selected or 'inputs' library missing."); self.listen_button.setEnabled(False); return
        
        self.selected_gamepad_instance = device_info.get('instance')
        if not self.selected_gamepad_instance or not isinstance(self.selected_gamepad_instance, inputs.GamePad): # type: ignore
            self.update_status_and_log(f"Error: Invalid gamepad instance for {device_info.get('name')}."); self.listen_button.setEnabled(False); return
        
        self.update_status_and_log(f"Selected: {device_info.get('name')}. Starting listener thread.")
        self.listen_button.setEnabled(True)
        self.controller_thread = InputsControllerThread(self.mappings, gamepad_device_obj=self.selected_gamepad_instance)
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered)
        self.controller_thread.controllerStatusUpdate.connect(self.update_status_and_log)
        self.controller_thread.start()

    def update_status_and_log(self, message: str):
        self.status_label.setText(message)
        self.log_to_debug_console(message) 
        if "error" in message.lower() or "unplugged" in message.lower() or "no gamepad" in message.lower(): logger.warning(f"MapperStatus: {message}")
        else: logger.info(f"MapperStatus: {message}")

    def start_listening_for_map_from_button(self):
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map: logger.error("Could not get internal key from ComboBox."); QMessageBox.critical(self, "Error", "Internal error: Could not determine action to map."); return
        self.initiate_listening_sequence(internal_key_to_map)

    def initiate_listening_sequence(self, internal_key_to_map_str: str, originating_row: int = -1):
        if not self.controller_thread or not self.controller_thread.isRunning():
            QMessageBox.warning(self, "No Controller", "Controller thread not running."); self.reset_listening_ui(); return
        if self.listen_button.text().startswith("Listening...") :
            if self.current_listening_key and self.current_listening_key != internal_key_to_map_str:
                 QMessageBox.information(self, "Busy", f"Already listening for '{GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)}'."); return
            elif not self.current_listening_key: self.reset_listening_ui() 
        self.current_listening_key = internal_key_to_map_str; self.last_selected_row_for_mapping = originating_row
        index = self.key_to_map_combo.findData(self.current_listening_key)
        if index != -1 and self.key_to_map_combo.currentIndex() != index: self.key_to_map_combo.setCurrentIndex(index)
        self.controller_thread.start_listening()
        friendly_name = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        self.update_status_and_log(f"Listening for input for '{friendly_name}'...")
        self.listen_button.setText(f"Listening: {friendly_name[:20]}..."); self.listen_button.setEnabled(False); self.key_to_map_combo.setEnabled(False)

    @Slot(dict, str)
    def on_controller_event_captured(self, event_details: Dict[str, Any], raw_event_str: str):
        if not self.current_listening_key: self.reset_listening_ui(preserve_scroll=True); return
        friendly_name_current_key = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        logger.info(f"Captured for '{friendly_name_current_key}': {raw_event_str} -> {event_details}")
        
        captured_event_uid = f"{event_details['type']}_"
        if event_details['type'] == 'button': captured_event_uid += str(event_details.get('button_id'))
        elif event_details['type'] == 'axis': captured_event_uid += f"{event_details.get('axis_id')}_{event_details.get('direction')}"
        elif event_details['type'] == 'hat': captured_event_uid += f"{event_details.get('hat_id')}_{str(tuple(event_details.get('value', (0,0))))}"
        else: captured_event_uid += "unknown_event"

        conflicting_keys = []
        is_new_exclusive = self.current_listening_key in EXCLUSIVE_ACTIONS
        for existing_key, map_info in list(self.mappings.items()):
            if not map_info or not isinstance(map_info.get("details"), dict): continue
            stored_details = map_info["details"]
            stored_uid = f"{stored_details.get('type', 'na')}_"
            if stored_details.get('type') == 'button': stored_uid += str(stored_details.get('button_id'))
            elif stored_details.get('type') == 'axis': stored_uid += f"{stored_details.get('axis_id')}_{stored_details.get('direction')}"
            elif stored_details.get('type') == 'hat': stored_uid += f"{stored_details.get('hat_id')}_{str(tuple(stored_details.get('value',(0,0))))}"
            else: stored_uid += "unknown_stored"
            
            if stored_uid == captured_event_uid and existing_key != self.current_listening_key:
                if is_new_exclusive or existing_key in EXCLUSIVE_ACTIONS: conflicting_keys.append(existing_key)
        
        if conflicting_keys:
            conflicts_str = "\n".join([f"- {GAME_ACTIONS_FRIENDLY_NAMES.get(k, k)}" for k in conflicting_keys])
            reply = QMessageBox.question(self, "Confirm Reassignment", f"Input '{raw_event_str}' is used by:\n{conflicts_str}\n\nMap '{friendly_name_current_key}' to this input and unmap others?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: self.update_status_and_log(f"Mapping for '{friendly_name_current_key}' cancelled."); self.reset_listening_ui(preserve_scroll=True); return
            for key_to_del in conflicting_keys:
                if key_to_del in self.mappings: del self.mappings[key_to_del]

        self.mappings[self.current_listening_key] = {"event_type": event_details["type"], "details": event_details.copy(), "raw_str": raw_event_str, "friendly_name": raw_event_str}
        self.update_status_and_log(f"Mapped '{raw_event_str}' to '{friendly_name_current_key}'.")
        self.refresh_mappings_table(preserve_scroll=True, target_row_key=self.current_listening_key)
        self.reset_listening_ui(preserve_scroll=True)


# NEW main function for importability and standalone execution
def main(embed_mode: bool = False) -> Any: # Returns MainWindow or int or None
    """
    Initializes and runs the Controller Mapper GUI.

    Args:
        embed_mode (bool): If True, the function returns the MainWindow instance
                           without starting its own event loop, for embedding in another app.
                           The parent application must have already created a QApplication instance.
    Returns:
        Optional[MainWindow]: The MainWindow instance if embed_mode is True.
        int: The application exit code if embed_mode is False and the event loop is run.
        None: If a critical error occurs (e.g., 'inputs' missing).
    """
    if not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
        app_for_msg = QApplication.instance()
        temp_app_created = False
        if not app_for_msg and not embed_mode:
            app_for_msg = QApplication(sys.argv)
            temp_app_created = True
        
        if app_for_msg and not embed_mode: # Only show message box if running standalone and app exists
            QMessageBox.critical(None, "Missing Dependency", "The 'inputs' Python library is required for the Controller Mapper.\nPlease install it: pip install inputs")
        elif embed_mode:
             logger.error("CONTROLLER_MAPPER_GUI (embed mode): 'inputs' library missing. Cannot initialize.")
        else: # Standalone, but no app to show message box
            print("CONTROLLER_MAPPER_GUI: CRITICAL - 'inputs' library not found and no GUI context to show error.")

        if temp_app_created: # If we made a temp app just for the message box
            # This is tricky, as exec() wasn't called.
            # For standalone, sys.exit(1) will be called by __main__
            pass
        return None 

    logger.info(f"Controller Mapper GUI {'embedding process' if embed_mode else 'application'} starting...")

    app_to_use = QApplication.instance()
    if not app_to_use:
        if embed_mode:
            logger.error("CONTROLLER_MAPPER_GUI (embed_mode): QApplication instance not found. It should be created by the host application.")
            return None 
        logger.info("CONTROLLER_MAPPER_GUI (standalone): No QApplication instance found, creating new one.")
        app_to_use = QApplication(sys.argv)
    
    if not app_to_use: 
        logger.critical("CONTROLLER_MAPPER_GUI: QApplication instance could not be obtained or created.")
        return None

    # Initialize joystick_handler (it's lightweight)
    joystick_handler.init_joysticks()
    
    window_instance = MainWindow()

    if embed_mode:
        logger.info("Controller Mapper GUI MainWindow instance created for embedding.")
        return window_instance # Return the instance to be embedded
    else:
        # Standalone mode
        window_instance.show()
        exit_code = app_to_use.exec()
        
        # joystick_handler.quit_joysticks() # Cleanup handled by MainWindow.closeEvent or here for symmetry
        # Let's keep it here for explicit standalone cleanup after app loop
        joystick_handler.quit_joysticks()
        logger.info(f"Controller Mapper GUI application finished with exit code: {exit_code}.")
        return exit_code


if __name__ == "__main__":
    # This block is for running the controller_mapper_gui.py standalone
    # Ensure a QApplication instance exists for main() in standalone mode
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    result = main(embed_mode=False)
    
    if isinstance(result, int): # main() returned an exit code
        sys.exit(result)
    elif result is None: # main() indicated a critical failure (e.g., 'inputs' missing)
        logger.error("Controller Mapper GUI failed to initialize in standalone mode. Exiting.")
        sys.exit(1)
    # If result is a MainWindow instance, it means embed_mode was True, which shouldn't happen here.
    # However, if main() for standalone somehow returned the window, the app loop didn't run in main().
    # This path should ideally not be hit with the current main() logic for embed_mode=False.
    else:
        logger.error(f"Unexpected return from main() in standalone: {type(result)}. Exiting.")
        sys.exit(1)