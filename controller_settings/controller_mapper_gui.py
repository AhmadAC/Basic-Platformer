import sys
import json
import threading
import time
import logging
import os

import pygame
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QLabel, QLineEdit, QInputDialog, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal
from pynput.keyboard import Controller as KeyboardController, Key

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# --- Configuration ---
# Internal keys used for saving and processing
MAPPABLE_KEYS = [
    "MOVE_UP", "MOVE_LEFT", "MOVE_DOWN", "MOVE_RIGHT", # WASD typically
    "JUMP", "CROUCH", "INTERACT",
    "ATTACK_PRIMARY", "ATTACK_SECONDARY", "DASH", "ROLL",
    "RESET", # <-- ADDED RESET ACTION
    "WEAPON_1", "WEAPON_2", "WEAPON_3", "WEAPON_4", # Number keys
    "WEAPON_DPAD_UP", "WEAPON_DPAD_DOWN", "WEAPON_DPAD_LEFT", "WEAPON_DPAD_RIGHT", # D-Pad weapons
    "MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN",
    # For direct key mappings if still desired alongside abstract actions:
    "W", "A", "S", "D", "1", "2", "3", "4", "5", "Q", "E", "V", "B",
    "SPACE", "SHIFT", "CTRL", "ALT",
]

# User-friendly names for display in the UI
GAME_ACTIONS_FRIENDLY_NAMES = {
    "MOVE_UP": "Move UP/JUMP (W)",
    "MOVE_LEFT": "Move Left (A)",
    "MOVE_DOWN": "Move DOWN/Crouch (S)", # Assuming S might be crouch or move back
    "MOVE_RIGHT": "Move Right (D)",
    "JUMP": "Jump (L-Stick Up / Space)",
    "CROUCH": "Crouch (L-Stick Down / Ctrl)", # More explicit crouch
    "INTERACT": "Interact (E)",
    "ATTACK_PRIMARY": "Primary Attack (LMB / V)",
    "ATTACK_SECONDARY": "Secondary Attack (RMB / B)",
    "DASH": "Dash (Shift)",
    "ROLL": "Roll (Ctrl - if not crouch)",
    "RESET": "Reset Action (Q)", # <-- ADDED FRIENDLY NAME FOR RESET
    "WEAPON_1": "Weapon Slot 1 (1)",
    "WEAPON_2": "Weapon Slot 2 (2)",
    "WEAPON_3": "Weapon Slot 3 (3)",
    "WEAPON_4": "Weapon Slot 4 (4)",
    "WEAPON_DPAD_UP": "Weapon D-Pad Up",
    "WEAPON_DPAD_DOWN": "Weapon D-Pad Down",
    "WEAPON_DPAD_LEFT": "Weapon D-Pad Left",
    "WEAPON_DPAD_RIGHT": "Weapon D-Pad Right",
    "MENU_CONFIRM": "Menu Confirm (Enter)",
    "MENU_CANCEL": "Menu Cancel (Esc)",
    "MENU_RETURN": "Return to Menu",
    # Direct key mappings (can be kept for flexibility or specific needs)
    "W": "Key W", "A": "Key A", "S": "Key S", "D": "Key D",
    "1": "Key 1", "2": "Key 2", "3": "Key 3", "4": "Key 4", "5": "Key 5",
    "Q": "Key Q", "E": "Key E", "V": "Key V", "B": "Key B",
    "SPACE": "Key Space", "SHIFT": "Key Shift", "CTRL": "Key Ctrl", "ALT": "Key Alt",
}


EXCLUSIVE_ACTIONS = ["MENU_RETURN"] # Add other exclusive actions like "JUMP" if a controller input for jump shouldn't also fire a weapon
AXIS_THRESHOLD = 0.7

# --- Path Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = SCRIPT_DIR
MAPPINGS_FILE = os.path.join(SETTINGS_DIR, "controller_mappings.json")

logging.info(f"Script directory (and effective settings directory): {SCRIPT_DIR}")
logging.info(f"Mappings file path: {MAPPINGS_FILE}")


# Helper to convert pynput special keys
def get_pynput_key(key_str):
    # These direct key mappings are for when the MAPPABLE_KEY itself is a keyboard key
    if key_str == "SPACE": return Key.space
    if key_str == "SHIFT": return Key.shift
    if key_str == "CTRL": return Key.ctrl
    if key_str == "ALT": return Key.alt

    # Abstract actions do not directly map to a single pynput key via this function.
    # Their corresponding keyboard keys (like 'W' for 'MOVE_UP') are simulated based on the action.
    if key_str in ["MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN",
                   "MOVE_UP", "MOVE_LEFT", "MOVE_BDOWN", "MOVE_RIGHT",
                   "JUMP", "CROUCH", "INTERACT", "ATTACK_PRIMARY", "ATTACK_SECONDARY",
                   "DASH", "ROLL", "RESET", # Added RESET here as well for consistency if this logic is ever used, though primary handling is in on_mapped_event_triggered
                   "WEAPON_1", "WEAPON_2", "WEAPON_3", "WEAPON_4",
                   "WEAPON_DPAD_UP", "WEAPON_DPAD_DOWN", "WEAPON_DPAD_LEFT", "WEAPON_DPAD_RIGHT"]:
        friendly_name = GAME_ACTIONS_FRIENDLY_NAMES.get(key_str, "")
        if "(W)" in friendly_name: return 'w'
        if "(A)" in friendly_name: return 'a'
        if "(S)" in friendly_name: return 's'
        if "(D)" in friendly_name: return 'd'
        if "(Space)" in friendly_name: return Key.space
        if "(Q)" in friendly_name and key_str == "RESET": return 'q' # Explicit for RESET if parsed here
        # ... add more for other abstract actions if they have a single key equivalent for pynput
        return None # Abstract actions without a direct single key simulation

    if len(key_str) == 1 and key_str.isalnum(): # Single alphanumeric keys
        return key_str.lower()

    logging.warning(f"get_pynput_key: Unknown or non-simulatable key string '{key_str}'")
    return None

# PygameControllerThread class
class PygameControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerHotplug = Signal(str)

    def __init__(self, mappings_ref):
        super().__init__()
        self.joystick = None
        self.is_listening_for_mapping = False
        self.stop_flag = threading.Event()
        self.mappings = mappings_ref # This is a reference to MainWindow.mappings
        self.active_axis_keys = {}
        self.active_hat_keys = {}
        self._last_joystick_count = -1
        logging.debug("PygameControllerThread initialized.")

    def run(self):
        logging.info("PygameControllerThread started.")
        try:
            pygame.init()
            pygame.joystick.init()
            self.controllerHotplug.emit("Pygame Initialized. Waiting for controller...")
        except pygame.error as e:
            logging.error(f"Pygame initialization failed: {e}")
            self.controllerHotplug.emit(f"Pygame init error: {e}")
            return

        while not self.stop_flag.is_set():
            try:
                current_joystick_count = pygame.joystick.get_count()

                if self.joystick is None:
                    if current_joystick_count > 0:
                        try:
                            self.joystick = pygame.joystick.Joystick(0)
                            self.joystick.init()
                            name = self.joystick.get_name()
                            self.controllerHotplug.emit(f"Controller connected: {name} (GUID: {self.joystick.guid if hasattr(self.joystick, 'guid') else 'N/A'})")
                            logging.info(f"Controller connected: {name}")
                        except pygame.error as e:
                            logging.error(f"Error initializing joystick: {e}")
                            self.joystick = None
                            self.controllerHotplug.emit(f"Joystick init error. Retrying...")
                            time.sleep(1)
                            continue
                    else:
                        if self._last_joystick_count != 0:
                            self.controllerHotplug.emit("No controller detected. Waiting...")
                            logging.info("No controller detected.")
                        self._last_joystick_count = 0
                        time.sleep(1)
                        continue
                elif not self.joystick.get_init() or (current_joystick_count == 0 and self.joystick is not None):
                    name = "Unknown"
                    try: name = self.joystick.get_name()
                    except: pass
                    logging.warning(f"Controller '{name}' connection lost. Attempting to re-initialize.")
                    self.controllerHotplug.emit(f"Controller '{name}' lost. Reconnecting...")
                    self.joystick = None
                    self.active_axis_keys.clear() # Clear active states on disconnect
                    self.active_hat_keys.clear()
                    pygame.joystick.quit()
                    pygame.joystick.init()
                    self._last_joystick_count = 0
                    time.sleep(1)
                    continue
                self._last_joystick_count = current_joystick_count

                for event in pygame.event.get():
                    if self.stop_flag.is_set(): break
                    event_details = None
                    raw_event_str = ""
                    if event.type == pygame.JOYAXISMOTION:
                        axis_id = event.axis
                        value = event.value
                        # Check for axis release
                        for internal_action_key, mapping_info in list(self.mappings.items()): # Use internal_action_key
                            if mapping_info and mapping_info["event_type"] == "axis" and \
                               mapping_info["details"]["axis_id"] == axis_id:
                                mapped_direction = mapping_info["details"]["direction"]
                                # Release if axis returns to neutral or moves significantly away from active direction
                                if (mapped_direction == 1 and value < 0.1) or \
                                   (mapped_direction == -1 and value > -0.1) or \
                                   (abs(value) < AXIS_THRESHOLD * 0.5 and self.active_axis_keys.get(internal_action_key) == mapped_direction): # More robust release
                                    if self.active_axis_keys.get(internal_action_key) == mapped_direction:
                                        self.mappedEventTriggered.emit(internal_action_key, False)
                                        if internal_action_key in self.active_axis_keys:
                                            del self.active_axis_keys[internal_action_key]
                        # Check for axis press
                        if value > AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis_id, "direction": 1, "threshold": AXIS_THRESHOLD}
                            raw_event_str = f"Axis {axis_id} > {AXIS_THRESHOLD:.1f}"
                        elif value < -AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis_id, "direction": -1, "threshold": AXIS_THRESHOLD}
                            raw_event_str = f"Axis {axis_id} < -{AXIS_THRESHOLD:.1f}"
                    elif event.type == pygame.JOYBUTTONDOWN:
                        event_details = {"type": "button", "button_id": event.button}
                        raw_event_str = f"Button {event.button} Down"
                    elif event.type == pygame.JOYBUTTONUP:
                        for internal_action_key, mapping_info in self.mappings.items(): # Use internal_action_key
                            if mapping_info and mapping_info["event_type"] == "button" and \
                               mapping_info["details"]["button_id"] == event.button:
                                self.mappedEventTriggered.emit(internal_action_key, False)
                    elif event.type == pygame.JOYHATMOTION:
                        hat_id = event.hat
                        hat_value_tuple = event.value
                        # Check for hat release
                        for internal_action_key, mapping_info in list(self.mappings.items()): # Use internal_action_key
                            if mapping_info and mapping_info["event_type"] == "hat" and \
                               mapping_info["details"]["hat_id"] == hat_id:
                                active_hat_val_tuple = tuple(self.active_hat_keys.get(internal_action_key, (0,0)))
                                mapped_hat_val_tuple = tuple(mapping_info["details"]["value"])
                                if active_hat_val_tuple == mapped_hat_val_tuple and hat_value_tuple != mapped_hat_val_tuple:
                                    self.mappedEventTriggered.emit(internal_action_key, False)
                                    if internal_action_key in self.active_hat_keys:
                                        del self.active_hat_keys[internal_action_key]
                        # Check for hat press
                        if hat_value_tuple != (0,0):
                            event_details = {"type": "hat", "hat_id": hat_id, "value": list(hat_value_tuple)}
                            raw_event_str = f"Hat {hat_id} {hat_value_tuple}"
                        elif hat_value_tuple == (0,0): 
                            for internal_action_key, mapping_info in list(self.mappings.items()):
                                if mapping_info and mapping_info["event_type"] == "hat" and \
                                   mapping_info["details"]["hat_id"] == hat_id:
                                    if tuple(self.active_hat_keys.get(internal_action_key, ())) == tuple(mapping_info["details"]["value"]):
                                        self.mappedEventTriggered.emit(internal_action_key, False)
                                        if internal_action_key in self.active_hat_keys:
                                            del self.active_hat_keys[internal_action_key]


                    if self.is_listening_for_mapping and event_details:
                        logging.info(f"Event captured for mapping: {raw_event_str} -> {event_details}")
                        self.controllerEventCaptured.emit(event_details, raw_event_str)
                        self.is_listening_for_mapping = False 
                    elif not self.is_listening_for_mapping and event_details:
                        triggered_exclusive_action_this_event = False
                        for internal_action_key, mapping_info in self.mappings.items():
                            if not mapping_info: continue 
                            match = False
                            if mapping_info["event_type"] == event_details.get("type"):
                                stored_details = mapping_info["details"]
                                current_details = event_details 
                                if mapping_info["event_type"] == "button" and stored_details["button_id"] == current_details["button_id"]:
                                    match = True
                                elif mapping_info["event_type"] == "axis" and \
                                     stored_details["axis_id"] == current_details["axis_id"] and \
                                     stored_details["direction"] == current_details["direction"]:
                                    match = True
                                elif mapping_info["event_type"] == "hat" and \
                                     stored_details["hat_id"] == current_details["hat_id"] and \
                                     tuple(stored_details["value"]) == tuple(current_details["value"]):
                                    match = True
                            if match:
                                if triggered_exclusive_action_this_event and internal_action_key not in EXCLUSIVE_ACTIONS:
                                    continue 
                                if internal_action_key in EXCLUSIVE_ACTIONS and triggered_exclusive_action_this_event and self.mappings.get(internal_action_key) != mapping_info :
                                     continue

                                if mapping_info["event_type"] == "axis":
                                    if self.active_axis_keys.get(internal_action_key) != mapping_info["details"]["direction"]:
                                        self.mappedEventTriggered.emit(internal_action_key, True) 
                                        self.active_axis_keys[internal_action_key] = mapping_info["details"]["direction"]
                                elif mapping_info["event_type"] == "hat":
                                    if tuple(self.active_hat_keys.get(internal_action_key, ())) != tuple(event_details["value"]):
                                        self.mappedEventTriggered.emit(internal_action_key, True) 
                                        self.active_hat_keys[internal_action_key] = list(event_details["value"])
                                else: 
                                    self.mappedEventTriggered.emit(internal_action_key, True) 

                                if internal_action_key in EXCLUSIVE_ACTIONS:
                                    triggered_exclusive_action_this_event = True
                                    break 
                time.sleep(0.01)
            except pygame.error as e:
                logging.error(f"Pygame error in controller loop: {e}")
                self.controllerHotplug.emit(f"Pygame error: {e}. Trying to recover...")
                self.joystick = None
                self.active_axis_keys.clear()
                self.active_hat_keys.clear()
                try:
                    pygame.joystick.quit()
                    pygame.joystick.init()
                except pygame.error: pass
                time.sleep(1)
            except Exception as e:
                logging.exception("Unhandled exception in controller thread loop:")
                time.sleep(1) 

        pygame.joystick.quit()
        pygame.quit()
        self.controllerHotplug.emit("Controller thread stopped.")
        logging.info("PygameControllerThread stopped.")

    def stop(self):
        logging.debug("PygameControllerThread stop called.")
        self.stop_flag.set()

    def start_listening(self):
        logging.debug("PygameControllerThread start_listening called.")
        self.is_listening_for_mapping = True

    def stop_listening(self):
        logging.debug("PygameControllerThread stop_listening called.")
        self.is_listening_for_mapping = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Mapper v0.9.1 (Reset Button)") # <-- UPDATED WINDOW TITLE
        self.setGeometry(100, 100, 850, 700)

        self.keyboard = KeyboardController()
        self.currently_pressed_keys = set()
        self.mappings = {}
        self.current_listening_key = None
        self.last_selected_row_for_mapping = -1
        logging.info("MainWindow initializing...")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Initializing...")
        main_layout.addWidget(self.status_label)

        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setFixedHeight(100)

        self.load_mappings()

        mapping_controls_layout = QHBoxLayout()
        self.key_to_map_combo = QComboBox()
        for internal_key in MAPPABLE_KEYS:
            friendly_name = GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)
            self.key_to_map_combo.addItem(friendly_name, userData=internal_key)
        mapping_controls_layout.addWidget(QLabel("Action/Key to Map:"))
        mapping_controls_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Listen for Controller Input to Map")
        self.listen_button.clicked.connect(self.start_listening_for_map_from_button)
        mapping_controls_layout.addWidget(self.listen_button)
        main_layout.addLayout(mapping_controls_layout)

        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(5)
        self.mappings_table.setHorizontalHeaderLabels(["Action/Key", "Controller Input", "Friendly Name", "Rename", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.mappings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.mappings_table.setColumnWidth(1, 150)
        self.mappings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.mappings_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.mappings_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.mappings_table.cellDoubleClicked.connect(self.handle_table_double_click)
        main_layout.addWidget(self.mappings_table)

        file_buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save Mappings")
        save_button.clicked.connect(self.save_mappings)
        file_buttons_layout.addWidget(save_button)
        load_button = QPushButton("Reload Mappings")
        load_button.clicked.connect(self.load_mappings_and_refresh)
        file_buttons_layout.addWidget(load_button)
        
        self.reset_mappings_button = QPushButton("Reset All Mappings")
        self.reset_mappings_button.clicked.connect(self.confirm_reset_all_mappings)
        file_buttons_layout.addWidget(self.reset_mappings_button)
        
        main_layout.addLayout(file_buttons_layout)

        main_layout.addWidget(QLabel("Debug Log:"))
        main_layout.addWidget(self.debug_console)

        self.controller_thread = PygameControllerThread(self.mappings)
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log)
        self.controller_thread.start()

        self.refresh_mappings_table()
        logging.info("MainWindow initialized and controller thread started.")

    def update_status_and_log(self, message):
        self.status_label.setText(message)
        self.log_to_debug_console(message)
        if "error" in message.lower() or "lost" in message.lower() or "no controller" in message.lower():
            logging.warning(f"Status Update: {message}")
        else:
            logging.info(f"Status Update: {message}")

    def log_to_debug_console(self, message):
        if hasattr(self, 'debug_console'):
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()
        else:
            logging.warning(f"Debug console not ready for message: {message}")

    def start_listening_for_map_from_button(self):
        internal_key_to_map = self.key_to_map_combo.currentData()
        if not internal_key_to_map:
            friendly_name = self.key_to_map_combo.currentText()
            logging.error(f"Could not get internal key for friendly name '{friendly_name}' from ComboBox.")
            QMessageBox.critical(self, "Error", "Internal error: Could not determine action to map.")
            return
        self.initiate_listening_sequence(internal_key_to_map)

    def initiate_listening_sequence(self, internal_key_to_map_str, originating_row=-1):
        if self.listen_button.text() == "Listening... (Press Controller Input)":
            if self.current_listening_key and self.current_listening_key != internal_key_to_map_str:
                 QMessageBox.information(self, "Already Listening", f"Already listening for input for '{GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)}'. Complete or cancel first.")
                 return
            elif not self.current_listening_key:
                 self.reset_listening_ui() 

        self.current_listening_key = internal_key_to_map_str
        self.last_selected_row_for_mapping = originating_row

        logging.debug(f"initiate_listening_sequence for internal key: {self.current_listening_key}")
        if not self.current_listening_key:
            QMessageBox.warning(self, "No Action Selected", "Please select an action to map.")
            self.reset_listening_ui()
            return

        index = self.key_to_map_combo.findData(self.current_listening_key)
        if index != -1:
            if self.key_to_map_combo.currentIndex() != index:
                self.key_to_map_combo.setCurrentIndex(index)
        else:
            logging.warning(f"Internal key '{self.current_listening_key}' not found in combo box data during initiate_listening.")

        self.controller_thread.start_listening()
        friendly_name_for_status = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        self.update_status_and_log(f"Listening for controller input for '{friendly_name_for_status}'...")
        self.listen_button.setText("Listening... (Press Controller Input)")
        self.listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(False)


    def on_controller_event_captured(self, event_details, raw_event_str):
        friendly_name_current_key = GAME_ACTIONS_FRIENDLY_NAMES.get(self.current_listening_key, self.current_listening_key)
        logging.info(f"on_controller_event_captured: Action='{friendly_name_current_key}' (Internal: {self.current_listening_key}), Raw='{raw_event_str}', Details={event_details}")

        keys_to_unmap_due_to_conflict = []
        is_current_key_exclusive = self.current_listening_key in EXCLUSIVE_ACTIONS

        for existing_internal_key, mapping_info in list(self.mappings.items()):
            if mapping_info and mapping_info["raw_str"] == raw_event_str:
                if existing_internal_key == self.current_listening_key:
                    continue
                is_existing_key_exclusive = existing_internal_key in EXCLUSIVE_ACTIONS
                friendly_name_existing_key = GAME_ACTIONS_FRIENDLY_NAMES.get(existing_internal_key, existing_internal_key)

                if is_current_key_exclusive and is_existing_key_exclusive:
                    keys_to_unmap_due_to_conflict.append(existing_internal_key)
                elif is_current_key_exclusive and not is_existing_key_exclusive:
                    keys_to_unmap_due_to_conflict.append(existing_internal_key)
                elif not is_current_key_exclusive and is_existing_key_exclusive:
                    QMessageBox.warning(self, "Mapping Conflict",
                                        f"Controller input '{raw_event_str}' is already mapped to the exclusive action '{friendly_name_existing_key}'.\n"
                                        f"Cannot map non-exclusive action '{friendly_name_current_key}' to this input.\n"
                                        f"Clear the mapping for '{friendly_name_existing_key}' first.")
                    self.reset_listening_ui(preserve_scroll=True)
                    return

        if keys_to_unmap_due_to_conflict:
            conflict_details = "\n".join([f"- {GAME_ACTIONS_FRIENDLY_NAMES.get(k, k)}" for k in keys_to_unmap_due_to_conflict])
            conflict_msg = (f"The controller input '{raw_event_str}' conflicts with existing mappings for '{friendly_name_current_key}'. "
                            f"The following will be unmapped:\n{conflict_details}"
                            f"\n\nProceed with mapping '{friendly_name_current_key}' to this input?")

            reply = QMessageBox.question(self, "Confirm Reassignment", conflict_msg,
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.update_status_and_log(f"Mapping for '{friendly_name_current_key}' cancelled due to conflict.")
                self.reset_listening_ui(preserve_scroll=True)
                return
            else:
                for key_to_remove in keys_to_unmap_due_to_conflict:
                    if key_to_remove in self.mappings:
                        logging.info(f"Unmapping '{GAME_ACTIONS_FRIENDLY_NAMES.get(key_to_remove, key_to_remove)}' (Internal: {key_to_remove}) due to conflict with '{friendly_name_current_key}'.")
                        del self.mappings[key_to_remove]

        if self.current_listening_key:
            self.mappings[self.current_listening_key] = {
                "event_type": event_details["type"],
                "details": event_details,
                "raw_str": raw_event_str,
                "friendly_name": f"{raw_event_str}"
            }
            self.update_status_and_log(f"Mapped '{raw_event_str}' to '{friendly_name_current_key}'.")
            logging.info(f"New mapping: {friendly_name_current_key} (Internal: {self.current_listening_key}) -> {self.mappings[self.current_listening_key]}")
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=self.current_listening_key)
        self.reset_listening_ui(preserve_scroll=True)


    def reset_listening_ui(self, preserve_scroll=False):
        self.listen_button.setText("Listen for Controller Input to Map")
        self.listen_button.setEnabled(True)
        self.key_to_map_combo.setEnabled(True)
        self.controller_thread.stop_listening()
        if self.current_listening_key: 
            self.current_listening_key = None
        if not preserve_scroll:
            self.last_selected_row_for_mapping = -1


    def on_mapped_event_triggered(self, internal_action_key_str, is_press_event):
        action_display_name = GAME_ACTIONS_FRIENDLY_NAMES.get(internal_action_key_str, internal_action_key_str)

        if internal_action_key_str in ["MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN"]:
            if is_press_event:
                self.log_to_debug_console(f"{action_display_name} action triggered by controller.")
                logging.info(f"{action_display_name} action triggered by controller.")
            return

        pynput_key_to_simulate = None
        if internal_action_key_str == "MOVE_UP": pynput_key_to_simulate = 'w'
        elif internal_action_key_str == "MOVE_LEFT": pynput_key_to_simulate = 'a'
        elif internal_action_key_str == "MOVE_DOWN": pynput_key_to_simulate = 's'
        elif internal_action_key_str == "MOVE_RIGHT": pynput_key_to_simulate = 'd'
        elif internal_action_key_str == "JUMP": pynput_key_to_simulate = Key.space
        elif internal_action_key_str == "CROUCH": pynput_key_to_simulate = Key.ctrl
        elif internal_action_key_str == "RESET": pynput_key_to_simulate = 'q' # <-- ADDED RESET ACTION HANDLING
        elif internal_action_key_str in ["W","A","S","D","SPACE","SHIFT","CTRL","ALT","1","2","3","4","5","Q","E","V","B"]:
            pynput_key_to_simulate = get_pynput_key(internal_action_key_str)

        if pynput_key_to_simulate:
            try:
                if is_press_event:
                    if pynput_key_to_simulate not in self.currently_pressed_keys:
                        self.keyboard.press(pynput_key_to_simulate)
                        self.currently_pressed_keys.add(pynput_key_to_simulate)
                        self.log_to_debug_console(f"Simulating Press: {action_display_name} -> Key {str(pynput_key_to_simulate)}")
                else:
                    if pynput_key_to_simulate in self.currently_pressed_keys:
                        self.keyboard.release(pynput_key_to_simulate)
                        self.currently_pressed_keys.remove(pynput_key_to_simulate)
                        self.log_to_debug_console(f"Simulating Release: {action_display_name} -> Key {str(pynput_key_to_simulate)}")
            except Exception as e:
                logging.error(f"Pynput error for action '{action_display_name}' (Simulating: {pynput_key_to_simulate}, Press: {is_press_event}): {e}")
        elif internal_action_key_str not in ["MENU_CONFIRM", "MENU_CANCEL", "MENU_RETURN"]:
             if is_press_event:
                self.log_to_debug_console(f"Action Triggered (No Key Sim): {action_display_name}")


    def refresh_mappings_table(self, preserve_scroll=False, target_row_key=None):
        logging.debug(f"Refreshing mappings table... Preserve scroll: {preserve_scroll}, Target internal key: {target_row_key}")
        current_v_scroll_value = self.mappings_table.verticalScrollBar().value() if preserve_scroll else -1
        target_row_to_ensure_visible = -1

        self.mappings_table.setRowCount(0)
        for i, internal_key in enumerate(MAPPABLE_KEYS):
            friendly_display_name = GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)
            if target_row_key and internal_key == target_row_key:
                target_row_to_ensure_visible = i
            elif preserve_scroll and self.last_selected_row_for_mapping == i and not target_row_key :
                 target_row_to_ensure_visible = i

            mapping_info = self.mappings.get(internal_key)
            row_position = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row_position)

            action_item = QTableWidgetItem(friendly_display_name)
            action_item.setData(Qt.UserRole, internal_key)
            self.mappings_table.setItem(row_position, 0, action_item)

            if mapping_info:
                self.mappings_table.setItem(row_position, 1, QTableWidgetItem(mapping_info["raw_str"]))
                self.mappings_table.setItem(row_position, 2, QTableWidgetItem(mapping_info["friendly_name"]))
                rename_button = QPushButton("Rename")
                rename_button.clicked.connect(lambda checked, k_internal=internal_key: self.rename_friendly_name_prompt_button(k_internal))
                self.mappings_table.setCellWidget(row_position, 3, rename_button)
                clear_button = QPushButton("Clear")
                clear_button.clicked.connect(lambda checked, k_internal=internal_key: self.clear_mapping(k_internal))
                self.mappings_table.setCellWidget(row_position, 4, clear_button)
            else:
                self.mappings_table.setItem(row_position, 1, QTableWidgetItem("Not Mapped"))
                self.mappings_table.setItem(row_position, 2, QTableWidgetItem(""))
                empty_rename_button = QPushButton("---"); empty_rename_button.setEnabled(False)
                self.mappings_table.setCellWidget(row_position, 3, empty_rename_button)
                empty_clear_button = QPushButton("---"); empty_clear_button.setEnabled(False)
                self.mappings_table.setCellWidget(row_position, 4, empty_clear_button)

        if target_row_to_ensure_visible != -1:
            self.mappings_table.scrollToItem(self.mappings_table.item(target_row_to_ensure_visible, 0), QAbstractItemView.PositionAtCenter)
            logging.debug(f"Scrolled to ensure row for internal key '{MAPPABLE_KEYS[target_row_to_ensure_visible]}' is visible.")
        elif preserve_scroll and current_v_scroll_value != -1:
            self.mappings_table.verticalScrollBar().setValue(current_v_scroll_value)
            logging.debug(f"Restored vertical scroll to {current_v_scroll_value}")

        if not preserve_scroll and not target_row_key:
             self.last_selected_row_for_mapping = -1
        logging.debug("Mappings table refresh complete.")


    def handle_table_double_click(self, row, column):
        action_item = self.mappings_table.item(row, 0)
        if not action_item: return
        internal_key_clicked = action_item.data(Qt.UserRole)
        friendly_name_clicked = action_item.text()

        if not internal_key_clicked:
            logging.error(f"Internal key not found for clicked row {row} (Display: {friendly_name_clicked})")
            return

        logging.debug(f"Table double-clicked: Row={row}, Col={column}, Action='{friendly_name_clicked}' (Internal: '{internal_key_clicked}')")

        if column == 0 or column == 1:
            if self.listen_button.text() == "Listening... (Press Controller Input)" and self.current_listening_key == internal_key_clicked:
                logging.debug(f"Already listening for '{friendly_name_clicked}', double-click ignored.")
                return
            self.initiate_listening_sequence(internal_key_clicked, originating_row=row)
        elif column == 2:
            if self.mappings.get(internal_key_clicked):
                self.rename_friendly_name_prompt_button(internal_key_clicked)


    def change_keyboard_key_assignment_prompt(self, old_internal_key):
        friendly_name_old_key = GAME_ACTIONS_FRIENDLY_NAMES.get(old_internal_key, old_internal_key)
        logging.debug(f"change_keyboard_key_assignment_prompt for '{friendly_name_old_key}' (Internal: '{old_internal_key}')")
        current_mapping_data = self.mappings.get(old_internal_key)

        if not current_mapping_data:
            QMessageBox.information(self, "Not Mapped", f"Action '{friendly_name_old_key}' is not currently mapped. Double-click its row to map it.")
            return

        available_actions_for_reassign_data = []
        for ik in MAPPABLE_KEYS:
            if ik not in self.mappings or ik == old_internal_key:
                available_actions_for_reassign_data.append(
                    (GAME_ACTIONS_FRIENDLY_NAMES.get(ik, ik), ik)
                )
        available_actions_for_reassign_data.sort(key=lambda x: x[0])
        
        display_texts_for_dialog = [item[0] for item in available_actions_for_reassign_data]
        internal_keys_ordered = [item[1] for item in available_actions_for_reassign_data]
        
        current_selection_index_dialog = 0
        try:
            current_selection_index_dialog = internal_keys_ordered.index(old_internal_key)
        except ValueError:
            logging.warning(f"Old internal key '{old_internal_key}' not found in sorted available keys for dialog.")

        new_friendly_name_selected, ok = QInputDialog.getItem(self, "Change Action Assignment",
            f"Controller input '{current_mapping_data['raw_str']}' is currently mapped to:\n'{friendly_name_old_key}'.\n\nMove this controller input to a new Action:",
            display_texts_for_dialog, current_selection_index_dialog, False)

        if ok and new_friendly_name_selected:
            selected_dialog_idx = display_texts_for_dialog.index(new_friendly_name_selected)
            new_internal_key = internal_keys_ordered[selected_dialog_idx]
            friendly_name_new_key = GAME_ACTIONS_FRIENDLY_NAMES.get(new_internal_key, new_internal_key)

            if new_internal_key != old_internal_key:
                if new_internal_key in EXCLUSIVE_ACTIONS:
                    for k_existing, v_existing in self.mappings.items():
                        if v_existing['raw_str'] == current_mapping_data['raw_str'] and \
                           k_existing != old_internal_key and k_existing in EXCLUSIVE_ACTIONS:
                            QMessageBox.critical(self, "Exclusivity Conflict",
                                f"Cannot reassign to exclusive action '{friendly_name_new_key}'.\n"
                                f"The controller input '{current_mapping_data['raw_str']}' is already mapped to another exclusive action: '{GAME_ACTIONS_FRIENDLY_NAMES.get(k_existing, k_existing)}'.\n"
                                f"Please clear that mapping first.")
                            return

                logging.info(f"Attempting to reassign mapping from '{friendly_name_old_key}' (Internal: {old_internal_key}) to '{friendly_name_new_key}' (Internal: {new_internal_key})")
                del self.mappings[old_internal_key]
                self.mappings[new_internal_key] = current_mapping_data
                self.refresh_mappings_table(preserve_scroll=True, target_row_key=new_internal_key)
                self.update_status_and_log(f"Mapping for '{current_mapping_data['raw_str']}' moved from '{friendly_name_old_key}' to '{friendly_name_new_key}'.")
        else:
            logging.debug("Action assignment cancelled or unchanged.")


    def rename_friendly_name_prompt_button(self, internal_key):
        action_display_name = GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)
        logging.debug(f"rename_friendly_name_prompt_button for action '{action_display_name}' (Internal: '{internal_key}')")
        mapping_info = self.mappings.get(internal_key)
        if mapping_info:
            current_ctrl_input_friendly_name = mapping_info.get("friendly_name", mapping_info.get("raw_str", ""))
            text, ok = QInputDialog.getText(self, "Rename Controller Input Label",
                f"Enter new label for controller input '{mapping_info['raw_str']}'\n(currently mapped to Action: '{action_display_name}'):",
                QLineEdit.Normal, current_ctrl_input_friendly_name)
            if ok and text:
                mapping_info["friendly_name"] = text
                self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
                self.update_status_and_log(f"Label for controller input mapped to '{action_display_name}' renamed.")
                logging.info(f"Controller input for '{action_display_name}' (Internal: {internal_key}) relabeled to '{text}'.")


    def clear_mapping(self, internal_key):
        action_display_name = GAME_ACTIONS_FRIENDLY_NAMES.get(internal_key, internal_key)
        logging.debug(f"clear_mapping for action '{action_display_name}' (Internal: '{internal_key}')")
        if internal_key in self.mappings:
            del self.mappings[internal_key]
            self.refresh_mappings_table(preserve_scroll=True, target_row_key=internal_key)
            self.update_status_and_log(f"Cleared mapping for '{action_display_name}'.")
            logging.info(f"Mapping for '{action_display_name}' (Internal: {internal_key}) cleared.")


    def save_mappings(self):
        logging.info(f"Attempting to save mappings to {MAPPINGS_FILE}")
        logging.debug(f"Mappings to save (using internal keys): {json.dumps(self.mappings, indent=2)}")
        try:
            with open(MAPPINGS_FILE, 'w') as f:
                json.dump(self.mappings, f, indent=4)
            self.update_status_and_log(f"Mappings saved to {MAPPINGS_FILE}")
        except Exception as e:
            logging.exception(f"Could not save mappings to {MAPPINGS_FILE}:")
            QMessageBox.critical(self, "Save Error", f"Could not save mappings: {e}")
            self.update_status_and_log(f"Error saving mappings: {e}")


    def load_mappings(self):
        logging.info(f"Attempting to load mappings from {MAPPINGS_FILE}")
        temp_loaded_mappings = {}
        file_found = False
        try:
            with open(MAPPINGS_FILE, 'r') as f:
                temp_loaded_mappings = json.load(f)
                file_found = True
                logging.debug(f"Raw loaded mappings from file (should use internal keys): {json.dumps(temp_loaded_mappings, indent=2)}")
            self.mappings.clear()
            loaded_count = 0
            skipped_count = 0
            for internal_key_from_mappable_list in MAPPABLE_KEYS:
                if internal_key_from_mappable_list in temp_loaded_mappings:
                    loaded_entry = temp_loaded_mappings[internal_key_from_mappable_list]
                    if isinstance(loaded_entry, dict) and \
                       all(k_check in loaded_entry for k_check in ["event_type", "details", "raw_str"]) and \
                       isinstance(loaded_entry.get("details"), dict) and \
                       isinstance(loaded_entry.get("event_type"), str) and \
                       isinstance(loaded_entry.get("raw_str"), str):
                        if "friendly_name" not in loaded_entry or not isinstance(loaded_entry["friendly_name"], str):
                            loaded_entry["friendly_name"] = loaded_entry["raw_str"]

                        valid_structure = False
                        event_type = loaded_entry["event_type"]
                        details = loaded_entry["details"]
                        if event_type == "button" and "button_id" in details: valid_structure = True
                        elif event_type == "axis" and "axis_id" in details and "direction" in details: valid_structure = True
                        elif event_type == "hat" and "hat_id" in details and "value" in details and isinstance(details["value"], list): valid_structure = True
                        
                        if valid_structure:
                            self.mappings[internal_key_from_mappable_list] = loaded_entry
                            loaded_count += 1
                        else:
                            logging.warning(f"Entry for '{internal_key_from_mappable_list}' in {MAPPINGS_FILE} has invalid 'details' or 'event_type' structure. Skipping. Entry: {loaded_entry}")
                            skipped_count += 1
                    else:
                        logging.warning(f"Entry for '{internal_key_from_mappable_list}' in {MAPPINGS_FILE} is malformed or missing required keys. Skipping. Entry: {loaded_entry}")
                        skipped_count += 1
            logging.info(f"Load complete. Loaded {loaded_count} valid mappings. Skipped {skipped_count} malformed/invalid entries.")
            logging.debug(f"Final self.mappings after load (internal keys): {json.dumps(self.mappings, indent=2)}")
            if hasattr(self, 'status_label') and self.status_label:
                if file_found:
                    self.update_status_and_log(f"Loaded {loaded_count} mappings from {MAPPINGS_FILE}. Skipped {skipped_count}.")
        except FileNotFoundError:
            logging.info(f"Mappings file '{MAPPINGS_FILE}' not found. Starting fresh.")
            self.mappings.clear()
            if hasattr(self, 'status_label') and self.status_label:
                self.update_status_and_log(f"No mappings file ({MAPPINGS_FILE}). Starting fresh.")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from '{MAPPINGS_FILE}': {e}")
            self.mappings.clear()
            QMessageBox.warning(self, "Load Error", f"Error decoding mappings file '{MAPPINGS_FILE}': {e}. Starting with fresh mappings.")
            if hasattr(self, 'status_label') and self.status_label:
                self.update_status_and_log(f"Error in '{MAPPINGS_FILE}'. Starting fresh.")
        except Exception as e:
            logging.exception(f"An unexpected error occurred while loading mappings from {MAPPINGS_FILE}:")
            self.mappings.clear()
            QMessageBox.critical(self, "Load Error", f"Could not load mappings: {e}")
            if hasattr(self, 'status_label') and self.status_label:
                self.update_status_and_log(f"Error loading mappings: {e}")

    def load_mappings_and_refresh(self):
        logging.info("load_mappings_and_refresh called.")
        current_v_scroll_value = self.mappings_table.verticalScrollBar().value()
        self.load_mappings()
        self.refresh_mappings_table()
        self.mappings_table.verticalScrollBar().setValue(current_v_scroll_value)
        self.update_status_and_log("Mappings reloaded and GUI updated.")

    def confirm_reset_all_mappings(self):
        reply = QMessageBox.question(self, "Confirm Reset",
                                     "Are you sure you want to reset all controller mappings?\n"
                                     "This will clear all current mappings in memory.\n"
                                     "Changes will be permanent if you save afterwards.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.perform_reset_mappings()

    def perform_reset_mappings(self):
        logging.info("Performing reset of all mappings.")
        
        if self.listen_button.text() != "Listen for Controller Input to Map":
            self.reset_listening_ui()

        self.mappings.clear()
        
        if hasattr(self, 'controller_thread'):
            self.controller_thread.active_axis_keys.clear()
            self.controller_thread.active_hat_keys.clear()
            
        self.release_all_simulated_keys()

        self.refresh_mappings_table() 
        self.update_status_and_log("All controller mappings have been reset. Save to make changes permanent.")

    def release_all_simulated_keys(self):
        logging.debug("Releasing all currently simulated pynput keys.")
        for pynput_key in list(self.currently_pressed_keys):
            try:
                self.keyboard.release(pynput_key)
                logging.debug(f"Released simulated key {pynput_key}.")
            except Exception as e:
                logging.warning(f"Error releasing simulated key {pynput_key} during reset: {e}")
        self.currently_pressed_keys.clear()

    def closeEvent(self, event):
        logging.info("Close event received. Shutting down.")
        self.update_status_and_log("Stopping controller thread...")
        if hasattr(self, 'controller_thread') and self.controller_thread.isRunning():
            self.controller_thread.stop()
            self.controller_thread.wait(2000) 
        
        self.release_all_simulated_keys() 
        self.save_mappings() 
        
        event.accept()
        logging.info("Application closed.")

if __name__ == "__main__":
    logging.info("Application starting...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())