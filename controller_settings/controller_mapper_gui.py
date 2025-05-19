#################### START OF FILE: controller_settings\controller_mapper_gui.py ####################

import sys
import json
import threading 
import time
import logging
import os
from typing import Dict, List, Optional, Tuple # For type hinting
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal, Slot

# Pynput for keyboard simulation
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

# Game-specific imports
current_dir_mapper = os.path.dirname(os.path.abspath(__file__))
project_root_mapper = os.path.dirname(current_dir_mapper)
if project_root_mapper not in sys.path:
    sys.path.insert(0, project_root_mapper)

import joystick_handler # Our refactored inputs-based handler

# 'inputs' library components, primarily for InputsControllerThread
try:
    from inputs import GamePad, UnpluggedError, EVENT_TYPES, KEY_MAX, ABS_MAX, SYN_MAX, FF_MAX
    # We can create a more specific mapping from inputs event codes if needed
    # For now, we'll use raw event.code strings like "BTN_SOUTH", "ABS_X"
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = True
except ImportError:
    INPUTS_LIB_AVAILABLE_FOR_MAPPER = False
    class GamePad:
        def __init__(self, gamepad_path=None, characterizing=False): self.name="DummyInputsGamePad"; self._Device__path = gamepad_path
        def read(self): return []
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
    class UnpluggedError(Exception): pass
    EVENT_TYPES = []; KEY_MAX=0; ABS_MAX=0; SYN_MAX=0; FF_MAX=0 # Dummies
    print("CONTROLLER_MAPPER_GUI: CRITICAL - 'inputs' library not found. Gamepad mapping will not function.")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

MAPPABLE_KEYS = [
    "MOVE_UP", "MOVE_LEFT", "MOVE_DOWN", "MOVE_RIGHT", "JUMP", "CROUCH", "INTERACT",
    "ATTACK_PRIMARY", "ATTACK_SECONDARY", "DASH", "ROLL", "RESET", "WEAPON_1", "WEAPON_2",
    "WEAPON_3", "WEAPON_4", "WEAPON_DPAD_UP", "WEAPON_DPAD_DOWN", "WEAPON_DPAD_LEFT",
    "WEAPON_DPAD_RIGHT", "MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN", "W", "A", "S", "D",
    "1", "2", "3", "4", "5", "Q", "E", "V", "B", "SPACE", "SHIFT", "CTRL", "ALT",
]
GAME_ACTIONS_FRIENDLY_NAMES = {
    "MOVE_UP": "Move UP/Aim Up", "MOVE_LEFT": "Move Left/Aim Left", # Adjusted for clarity
    "MOVE_DOWN": "Move DOWN/Aim Down", "MOVE_RIGHT": "Move Right/Aim Right",
    "JUMP": "Jump", "CROUCH": "Crouch/Toggle", "INTERACT": "Interact",
    "ATTACK_PRIMARY": "Primary Attack", "ATTACK_SECONDARY": "Secondary Attack",
    "DASH": "Dash", "ROLL": "Roll", "RESET": "Reset Action",
    "WEAPON_1": "Weapon 1", "WEAPON_2": "Weapon 2", "WEAPON_3": "Weapon 3", "WEAPON_4": "Weapon 4",
    "WEAPON_DPAD_UP": "Weapon D-Pad Up", "WEAPON_DPAD_DOWN": "Weapon D-Pad Down",
    "WEAPON_DPAD_LEFT": "Weapon D-Pad Left", "WEAPON_DPAD_RIGHT": "Weapon D-Pad Right",
    "MENU_CONFIRM": "Menu Confirm", "MENU_CANCEL": "Menu Cancel", "MENU_RETURN": "Menu/Pause",
    "W": "Key W", "A": "Key A", "S": "Key S", "D": "Key D", "1": "Key 1", "2": "Key 2", "3": "Key 3",
    "4": "Key 4", "5": "Key 5", "Q": "Key Q", "E": "Key E", "V": "Key V", "B": "Key B",
    "SPACE": "Key Space", "SHIFT": "Key Shift", "CTRL": "Key Ctrl", "ALT": "Key Alt",
}
EXCLUSIVE_ACTIONS = ["MENU_RETURN"]
AXIS_THRESHOLD = 0.7
SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPINGS_FILE = os.path.join(SETTINGS_DIR, "controller_mappings.json")

def get_pynput_key(key_str):
    if not PYNPUT_AVAILABLE: return None
    if key_str == "SPACE": return PynputKey.space
    if key_str == "SHIFT": return PynputKey.shift
    if key_str == "CTRL": return PynputKey.ctrl
    if key_str == "ALT": return PynputKey.alt
    friendly_name = GAME_ACTIONS_FRIENDLY_NAMES.get(key_str, "")
    if "(W)" in friendly_name and key_str == "MOVE_UP": return 'w'
    if "(A)" in friendly_name and key_str == "MOVE_LEFT": return 'a'
    if "(S)" in friendly_name and key_str == "MOVE_DOWN": return 's'
    if "(D)" in friendly_name and key_str == "MOVE_RIGHT": return 'd'
    if "(Q)" in friendly_name and key_str == "RESET": return 'q'
    if len(key_str) == 1 and key_str.isalnum(): return key_str.lower()
    return None

class InputsControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerStatusUpdate = Signal(str)

    def __init__(self, mappings_ref: Dict, gamepad_device_obj: Optional[GamePad] = None, parent=None): # Takes GamePad object
        super().__init__(parent)
        self.mappings = mappings_ref
        self.gamepad_instance = gamepad_device_obj # Store the passed GamePad object
        self.is_listening_for_mapping = False
        self._stop_requested = False
        self.active_axis_details: Dict[str, Dict] = {} 
        self.active_hat_values: Dict[int, Tuple[int,int]] = {} # Store hat_id -> (x,y)

    def run(self):
        if not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            self.controllerStatusUpdate.emit("Error: 'inputs' library not available.")
            return
        if not self.gamepad_instance:
            self.controllerStatusUpdate.emit("No gamepad instance provided to thread.")
            return

        gamepad_name = getattr(self.gamepad_instance, 'name', 'Unknown Gamepad')
        self.controllerStatusUpdate.emit(f"Listening on: {gamepad_name}")
        logging.info(f"InputsControllerThread: Started for gamepad: {gamepad_name}")

        try:
            while not self._stop_requested:
                try:
                    events = self.gamepad_instance.read()
                except UnpluggedError:
                    self.controllerStatusUpdate.emit(f"Gamepad disconnected: {gamepad_name}")
                    break
                except EOFError: # Can happen if device is gone
                    self.controllerStatusUpdate.emit(f"Gamepad EOF: {gamepad_name}")
                    break
                except Exception as e:
                    self.controllerStatusUpdate.emit(f"Error reading {gamepad_name}: {str(e)[:50]}")
                    logging.error(f"InputsControllerThread: Read error: {e}")
                    time.sleep(0.1) # Avoid tight loop on persistent read error
                    continue

                for event in events:
                    if self._stop_requested: break
                    
                    event_details: Optional[Dict] = None
                    raw_event_str = f"{event.ev_type} {event.code} {event.state}" # Basic raw string

                    if event.ev_type == "Key":
                        event_details = {"type": "button", "button_id": event.code, "state": event.state}
                        raw_event_str = f"Button {event.code} {'Pressed' if event.state == 1 else 'Released'}"
                    elif event.ev_type == "Absolute":
                        if "ABS_HAT" in event.code:
                            hat_id = int(event.code[7]) # ABS_HAT0X -> 0
                            axis = event.code[8] # X or Y
                            
                            current_x, current_y = self.active_hat_values.get(hat_id, (0,0))
                            if axis == 'X': current_x = event.state
                            else: current_y = event.state
                            new_hat_value = (current_x, current_y)
                            self.active_hat_values[hat_id] = new_hat_value

                            event_details = {"type": "hat", "hat_id": hat_id, "value": new_hat_value}
                            raw_event_str = f"Hat {hat_id} Value: {new_hat_value}"
                        else: # Analog stick
                            direction = 0
                            if event.state > AXIS_THRESHOLD: direction = 1
                            elif event.state < -AXIS_THRESHOLD: direction = -1
                            
                            active_axis_info = self.active_axis_details.get(event.code)
                            if direction != 0 or active_axis_info: # Process if passing threshold or returning to neutral
                                event_details = {"type": "axis", "axis_id": event.code, "direction": direction, "value": event.state, "threshold": AXIS_THRESHOLD}
                                raw_event_str = f"Axis {event.code} Val:{event.state:.2f} Dir:{direction}"
                    
                    if self.is_listening_for_mapping and event_details:
                        should_capture = False
                        if event_details["type"] == "button" and event_details.get("state") == 1: should_capture = True
                        elif event_details["type"] == "axis" and event_details.get("direction") != 0: should_capture = True
                        elif event_details["type"] == "hat" and event_details.get("value") != (0,0): should_capture = True
                        
                        if should_capture:
                            logging.info(f"Event captured for mapping: {raw_event_str} -> {event_details}")
                            self.controllerEventCaptured.emit(event_details, raw_event_str)
                            self.is_listening_for_mapping = False
                    elif not self.is_listening_for_mapping and event_details and self.mappings:
                        self.process_event_for_mapped_actions(event_details)
                
                if not events: time.sleep(0.005) # Tiny sleep if read() returned no events (non-blocking mode)
        finally:
            # Gamepad instance is typically managed by a context manager ('with') in 'inputs'.
            # If we opened it manually, we don't have an explicit close. It should close on GC.
            logging.info(f"InputsControllerThread: Event loop for {gamepad_name} stopped.")
            self.controllerStatusUpdate.emit(f"Controller thread for {gamepad_name} stopped.")

    def process_event_for_mapped_actions(self, event_details: Dict):
        # ... (logic as previously defined, ensuring it correctly uses event_details keys) ...
        # This part needs careful checking against the structure of event_details from inputs
        for internal_action_key, mapping_info in self.mappings.items():
            if not mapping_info: continue
            
            match = False
            stored_type = mapping_info.get("event_type")
            stored_details = mapping_info.get("details", {}) # This is what's saved in JSON

            # 'details' from JSON vs live 'event_details' from inputs
            # JSON 'details' for button: {"type": "button", "button_id": "BTN_SOUTH"}
            # JSON 'details' for axis: {"type": "axis", "axis_id": "ABS_X", "direction": -1, "threshold": 0.7}
            # JSON 'details' for hat: {"type": "hat", "hat_id": 0, "value": [0,1]}

            if stored_type == event_details.get("type"):
                if stored_type == "button" and stored_details.get("button_id") == event_details.get("button_id"):
                    is_press = event_details.get("state") == 1
                    self.mappedEventTriggered.emit(internal_action_key, is_press)
                    match = True
                
                elif stored_type == "axis" and stored_details.get("axis_id") == event_details.get("axis_id"):
                    event_direction = event_details.get("direction", 0)
                    mapped_direction = stored_details.get("direction")
                    active_axis_key_unique = f"axis_{event_details.get('axis_id')}_{mapped_direction}" # For tracking state

                    if event_direction == mapped_direction and mapped_direction != 0 : # Axis tilted in the mapped direction
                        if not self.active_axis_details.get(active_axis_key_unique):
                            self.mappedEventTriggered.emit(internal_action_key, True) # Press
                            self.active_axis_details[active_axis_key_unique] = True
                        match = True
                    elif event_direction != mapped_direction and self.active_axis_details.get(active_axis_key_unique): # Axis no longer in mapped direction
                        self.mappedEventTriggered.emit(internal_action_key, False) # Release
                        del self.active_axis_details[active_axis_key_unique]
                        match = True
                
                elif stored_type == "hat" and stored_details.get("hat_id") == event_details.get("hat_id"):
                    mapped_hat_value_tuple = tuple(stored_details.get("value", (0,0)))
                    current_event_hat_value_tuple = tuple(event_details.get("value", (0,0)))
                    active_hat_key_unique = f"hat_{event_details.get('hat_id')}_{mapped_hat_value_tuple}"

                    if current_event_hat_value_tuple == mapped_hat_value_tuple and mapped_hat_value_tuple != (0,0):
                        if not self.active_hat_details.get(active_hat_key_unique):
                            self.mappedEventTriggered.emit(internal_action_key, True)
                            self.active_hat_details[active_hat_key_unique] = True
                        match = True
                    elif self.active_hat_details.get(active_hat_key_unique) and current_event_hat_value_tuple != mapped_hat_value_tuple:
                        self.mappedEventTriggered.emit(internal_action_key, False)
                        del self.active_hat_details[active_hat_key_unique]
                        match = True
            
            if match and internal_action_key in EXCLUSIVE_ACTIONS: break 

    def stop_listening(self): self.is_listening_for_mapping = False
    def start_listening(self): self.is_listening_for_mapping = True
    def request_stop(self): self._stop_requested = True


class MainWindow(QMainWindow):
    # ... (init and other methods mostly as before, but changes in gamepad selection and thread start)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Mapper v1.1 (inputs lib)")
        self.setGeometry(100, 100, 850, 700)

        if PYNPUT_AVAILABLE: self.keyboard = KeyboardController()
        else: self.keyboard = None 
        
        self.currently_pressed_keys = set()
        self.mappings = {}
        self.current_listening_key: Optional[str] = None
        self.last_selected_row_for_mapping = -1
        
        self.selected_gamepad_instance: Optional[GamePad] = None # Store the live GamePad object

        logging.info("MainWindow initializing...")
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
        self.debug_console = QTextEdit(); self.debug_console.setReadOnly(True); self.debug_console.setFixedHeight(100)

        self.load_mappings() # Load saved mappings first

        # ... (rest of UI setup: key_to_map_combo, listen_button, mappings_table, file_buttons) ...
        mapping_controls_layout = QHBoxLayout()
        self.key_to_map_combo = QComboBox()
        for internal_key in MAPPABLE_KEYS:
            self.key_to_map_combo.addItem(GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key), userData=internal_key)
        mapping_controls_layout.addWidget(QLabel("Action to Map:"))
        mapping_controls_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Listen for Controller Input")
        self.listen_button.clicked.connect(self.start_listening_for_map_from_button)
        self.listen_button.setEnabled(False) # Disabled until a gamepad is active
        mapping_controls_layout.addWidget(self.listen_button)
        main_layout.addLayout(mapping_controls_layout)

        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(5)
        self.mappings_table.setHorizontalHeaderLabels(["Action/Key", "Controller Input", "Friendly Name", "Rename", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        # ... (other table settings)
        self.mappings_table.setColumnWidth(1, 200) # Wider for inputs raw_str
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click)
        main_layout.addWidget(self.mappings_table)
        
        file_buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save Mappings"); save_button.clicked.connect(self.save_mappings)
        load_button = QPushButton("Reload Mappings"); load_button.clicked.connect(self.load_mappings_and_refresh)
        reset_button = QPushButton("Reset All Mappings"); reset_button.clicked.connect(self.confirm_reset_all_mappings)
        file_buttons_layout.addWidget(save_button); file_buttons_layout.addWidget(load_button); file_buttons_layout.addWidget(reset_button)
        main_layout.addLayout(file_buttons_layout)
        main_layout.addWidget(QLabel("Debug Log:")); main_layout.addWidget(self.debug_console)

        self.controller_thread: Optional[InputsControllerThread] = None
        self.refresh_mappings_table()
        
        self.gamepad_combo.currentIndexChanged.connect(self.on_gamepad_selection_changed)
        # Initial population attempt
        QTimer.singleShot(100, self.populate_gamepad_combo) # Populate after UI is shown

        logging.info("MainWindow initialized.")

    def populate_gamepad_combo(self):
        self.log_to_debug_console("Attempting to detect gamepads...")
        self.gamepad_combo.blockSignals(True)
        self.gamepad_combo.clear()
        
        # Stop any existing controller thread before re-populating
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop()
            self.controller_thread.wait(300)
            self.controller_thread = None
        self.listen_button.setEnabled(False) # Disable listen button initially

        joystick_handler.init_joysticks() # This now does very little for `inputs`

        found_devices_for_combo = []
        if INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            try:
                # inputs.devices.gamepads is a generator. We iterate it.
                # This might still pick up non-gamepad event devices if they expose similar interfaces.
                # It's also blocking if a device is "stuck".
                # This part should ideally be in a worker thread if detection is slow.
                # For simplicity now, direct iteration.
                self.log_to_debug_console("Scanning with inputs.devices.gamepads...")
                # Store tuples of (name, device_object_or_path)
                # The `inputs` library doesn't give stable paths for all OS easily before opening.
                # So we might store the live GamePad object from the generator.
                # This means the GamePad objects are created here.
                
                # Clear joystick_handler's internal list, as we are re-detecting
                joystick_handler._gamepads_devices = []

                #inputs.DeviceManager is the way to get the list of devices and their paths
                device_manager = inputs.DeviceManager() # type: ignore
                for device in device_manager.gamepads: #This gets a list of GamePad objects
                     if device:
                        path = getattr(device, '_Device__path', f"uid_{id(device)}") # Try to get unique path or use object id
                        name = getattr(device, 'name', 'Unknown Gamepad')
                        found_devices_for_combo.append({'name': name, 'path': path, 'instance': device})
                        # Add to joystick_handler's list so get_joystick_count reflects this
                        joystick_handler._gamepads_devices.append({'name': name, 'path': path, 'instance': device})


                if found_devices_for_combo:
                    for i, dev_info in enumerate(found_devices_for_combo):
                        self.gamepad_combo.addItem(dev_info['name'], userData=dev_info) # Store the whole dict
                    self.log_to_debug_console(f"Found {len(found_devices_for_combo)} gamepad(s). Select one.")
                else:
                    self.gamepad_combo.addItem("No gamepads detected by 'inputs'", userData=None)
                    self.log_to_debug_console("No gamepads detected by 'inputs' library.")

            except RuntimeError as e: # Often "could not find a gamepad"
                 self.gamepad_combo.addItem("No gamepads found (RuntimeError)", userData=None)
                 self.log_to_debug_console(f"RuntimeError during gamepad detection: {e}")
            except NameError: # inputs not available
                 self.gamepad_combo.addItem("'inputs' lib error", userData=None)
                 self.log_to_debug_console("NameError: 'inputs' library likely not available.")
            except Exception as e:
                 self.gamepad_combo.addItem("Detection error", userData=None)
                 self.log_to_debug_console(f"Unexpected error during gamepad detection: {e}")
        else:
            self.gamepad_combo.addItem("Inputs library missing", userData=None)
            self.log_to_debug_console("'inputs' library not available for gamepad detection.")

        self.gamepad_combo.blockSignals(False)
        if self.gamepad_combo.count() > 0:
            self.on_gamepad_selection_changed(0) # Trigger for the first item
        else: # Should not happen if "No gamepads" item is added
            self.status_label.setText("No gamepads found.")


    @Slot(int)
    def on_gamepad_selection_changed(self, index: int):
        if self.controller_thread and self.controller_thread.isRunning():
            self.controller_thread.request_stop()
            self.controller_thread.wait(500)
            self.controller_thread = None
            self.selected_gamepad_instance = None

        device_info = self.gamepad_combo.itemData(index) # This is now a dict or None

        if not device_info or not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
            self.selected_gamepad_instance = None
            self.update_status_and_log("No gamepad selected or 'inputs' library missing.")
            self.listen_button.setEnabled(False)
            return
        
        self.selected_gamepad_instance = device_info.get('instance') # Get the GamePad object
        
        if not self.selected_gamepad_instance:
            self.update_status_and_log(f"Error: Could not get gamepad instance for {device_info.get('name')}.")
            self.listen_button.setEnabled(False)
            return

        self.update_status_and_log(f"Selected: {device_info.get('name')}. Starting listener thread.")
        self.listen_button.setEnabled(True)
        
        self.controller_thread = InputsControllerThread(self.mappings, gamepad_device_obj=self.selected_gamepad_instance)
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered)
        self.controller_thread.controllerStatusUpdate.connect(self.update_status_and_log)
        self.controller_thread.start()

    # ... (update_status_and_log, log_to_debug_console, start_listening_for_map_from_button as before)
    def update_status_and_log(self, message: str):
        self.status_label.setText(message)
        self.log_to_debug_console(message)
        if "error" in message.lower() or "unplugged" in message.lower() or "no gamepad" in message.lower():
            logging.warning(f"Status Update: {message}")
        else:
            logging.info(f"Status Update: {message}")

    def log_to_debug_console(self, message: str):
        if hasattr(self, 'debug_console'):
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()

    def start_listening_for_map_from_button(self):
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map:
            logging.error("Could not get internal key from ComboBox.")
            QMessageBox.critical(self, "Error", "Internal error: Could not determine action to map.")
            return
        self.initiate_listening_sequence(internal_key_to_map)

    def initiate_listening_sequence(self, internal_key_to_map_str: str, originating_row: int = -1):
        if not self.controller_thread or not self.controller_thread.isRunning():
            QMessageBox.warning(self, "No Controller", "Controller thread is not running. Select a gamepad and ensure it's connected.")
            self.reset_listening_ui()
            return
        # ... (rest of initiate_listening_sequence as before)
        if self.listen_button.text().startswith("Listening...") :
            if self.current_listening_key and self.current_listening_key != internal_key_to_map_str:
                 QMessageBox.information(self, "Already Listening", f"Already listening for input for '{GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)}'. Complete or cancel first.")
                 return
            elif not self.current_listening_key: self.reset_listening_ui() 

        self.current_listening_key = internal_key_to_map_str
        self.last_selected_row_for_mapping = originating_row
        index = self.key_to_map_combo.findData(self.current_listening_key)
        if index != -1 and self.key_to_map_combo.currentIndex() != index: self.key_to_map_combo.setCurrentIndex(index)
        self.controller_thread.start_listening()
        friendly_name_for_status = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        self.update_status_and_log(f"Listening for input for '{friendly_name_for_status}'...")
        self.listen_button.setText(f"Listening for: {friendly_name_for_status[:20]}...")
        self.listen_button.setEnabled(False); self.key_to_map_combo.setEnabled(False)


    @Slot(dict, str)
    def on_controller_event_captured(self, event_details: Dict, raw_event_str: str):
        # ... (conflict resolution, mapping storage logic as before, but ensure keys used are correct)
        friendly_name_current_key = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        logging.info(f"Captured for '{friendly_name_current_key}': {raw_event_str} -> {event_details}")
        
        # Create a consistent unique ID for the raw input event
        # This ID will be compared with the 'raw_str' (or a similar unique ID derived from it) stored in existing mappings
        captured_event_unique_id = f"{event_details['type']}_"
        if event_details['type'] == 'button': captured_event_unique_id += str(event_details.get('button_id'))
        elif event_details['type'] == 'axis': captured_event_unique_id += f"{event_details.get('axis_id')}_{event_details.get('direction')}"
        elif event_details['type'] == 'hat': captured_event_unique_id += f"{event_details.get('hat_id')}_{str(tuple(event_details.get('value', (0,0))))}"
        else: captured_event_unique_id += "unknown"


        keys_to_unmap_due_to_conflict = []
        is_current_key_exclusive = self.current_listening_key in EXCLUSIVE_ACTIONS

        for existing_internal_key, mapping_info in list(self.mappings.items()):
            if not mapping_info or not isinstance(mapping_info.get("details"), dict): continue
            
            # Reconstruct a unique ID from the stored mapping_info for comparison
            stored_event_details = mapping_info["details"]
            stored_unique_id = f"{stored_event_details['type']}_"
            if stored_event_details['type'] == 'button': stored_unique_id += str(stored_event_details.get('button_id'))
            elif stored_event_details['type'] == 'axis': stored_unique_id += f"{stored_event_details.get('axis_id')}_{stored_event_details.get('direction')}"
            elif stored_event_details['type'] == 'hat': stored_unique_id += f"{stored_event_details.get('hat_id')}_{str(tuple(stored_event_details.get('value',(0,0))))}"
            else: stored_unique_id += "unknown_stored"


            if stored_unique_id == captured_event_unique_id:
                if existing_internal_key == self.current_listening_key: continue # Remapping same action to same input
                
                is_existing_key_exclusive = existing_internal_key in EXCLUSIVE_ACTIONS
                friendly_name_existing_key = GAME_ACTIONS_FRIENDLY_NAMES.get(existing_internal_key, existing_internal_key)

                if is_current_key_exclusive or is_existing_key_exclusive : # If either new or existing is exclusive, it's a conflict that needs unmapping
                    keys_to_unmap_due_to_conflict.append(existing_internal_key)
                # If neither is exclusive, they can coexist on the same input (e.g. move and weapon on same stick direction)
                # However, the current logic of breaking after one match in process_event_for_mapped_actions
                # might prevent coexisting non-exclusive actions from triggering simultaneously.
                # This aspect of EXCLUSIVE_ACTIONS vs non-exclusive needs careful review in the trigger logic too.


        if keys_to_unmap_due_to_conflict:
            conflict_details_str = "\n".join([f"- {GAME_ACTIONS_FRIENDLY_NAMES.get(k, k)}" for k in keys_to_unmap_due_to_conflict])
            conflict_msg_text = (f"Input '{raw_event_str}' is used by:\n{conflict_details_str}\n\n"
                                 f"Map '{friendly_name_current_key}' to this input and unmap others?")
            reply = QMessageBox.question(self, "Confirm Reassignment", conflict_msg_text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                self.update_status_and_log(f"Mapping for '{friendly_name_current_key}' cancelled."); self.reset_listening_ui(preserve_scroll=True); return
            else:
                for key_to_remove in keys_to_unmap_due_to_conflict:
                    if key_to_remove in self.mappings: del self.mappings[key_to_remove]

        if self.current_listening_key:
            self.mappings[self.current_listening_key] = {
                "event_type": event_details["type"], "details": event_details,
                "raw_str": raw_event_str, "friendly_name": f"{raw_event_str}"
            }
            self.update_status_and_log(f"Mapped '{raw_event_str}' to '{friendly_name_current_key}'.")
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=self.current_listening_key)
        
        self.reset_listening_ui(preserve_scroll=True)


    # ... (on_mapped_event_triggered, refresh_mappings_table, table clicks, rename, clear, save, load, reset, closeEvent) ...
    # These methods should be largely okay but need to be tested with the new event structures if they parse `raw_str`.
    # refresh_mappings_table will display the new `raw_str` values.
    # on_mapped_event_triggered (pynput simulation) remains the same as it acts on internal_action_key_str.

    def closeEvent(self, event):
        logging.info("Close event received. Shutting down mapper GUI.")
        if self.controller_thread and self.controller_thread.isRunning():
            self.update_status_and_log("Stopping controller thread...")
            self.controller_thread.request_stop()
            if not self.controller_thread.wait(1000):
                logging.warning("Controller thread did not stop gracefully, terminating.")
                self.controller_thread.terminate()
                self.controller_thread.wait()
            self.controller_thread = None # Clear reference
            
        self.release_all_simulated_keys() 
        self.save_mappings() 
        event.accept()
        logging.info("Controller Mapper GUI closed.")


if __name__ == "__main__":
    if not INPUTS_LIB_AVAILABLE_FOR_MAPPER:
        # ... (error message as before) ...
        try:
            app_temp = QApplication(sys.argv) # sys needs to be imported
            QMessageBox.critical(None, "Missing Dependency", "The 'inputs' Python library is required.\nPlease install it: pip install inputs")
        except Exception as e: print(f"Could not show critical error dialog: {e}")
        sys.exit(1)
        
    logging.info("Controller Mapper GUI application starting...")
    app = QApplication(sys.argv)
    # joystick_handler.init_joysticks() # Called by populate_gamepad_combo
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    joystick_handler.quit_joysticks() # Clean up our simple handler
    logging.info(f"Controller Mapper GUI application finished with exit code: {exit_code}.")
    sys.exit(exit_code)

#################### END OF FILE: controller_settings\controller_mapper_gui.py ####################