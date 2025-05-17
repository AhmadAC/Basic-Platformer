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
MAPPABLE_KEYS = ["W", "A", "S", "D", "1", "2", "3", "4", "5", "Q", "E", "V", "B", "SPACE", "SHIFT", "CTRL", "ALT"]
AXIS_THRESHOLD = 0.7

# --- Path Configuration (Scenario 1: JSON in same dir as script) ---
# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = SCRIPT_DIR # Mappings file will be in the same directory as the script
MAPPINGS_FILE = os.path.join(SETTINGS_DIR, "controller_mappings.json")

logging.info(f"Script directory (and effective settings directory): {SCRIPT_DIR}")
logging.info(f"Mappings file path: {MAPPINGS_FILE}")


# Helper to convert pynput special keys (same as before)
def get_pynput_key(key_str):
    if key_str == "SPACE": return Key.space
    if key_str == "SHIFT": return Key.shift
    if key_str == "CTRL": return Key.ctrl
    if key_str == "ALT": return Key.alt
    if len(key_str) == 1: return key_str.lower()
    logging.warning(f"get_pynput_key: Unknown key string '{key_str}'")
    return None

# PygameControllerThread class (largely unchanged, ensure logging is consistent)
class PygameControllerThread(QThread):
    controllerEventCaptured = Signal(dict, str)
    mappedEventTriggered = Signal(str, bool)
    controllerHotplug = Signal(str)

    def __init__(self, mappings_ref):
        super().__init__()
        self.joystick = None
        self.is_listening_for_mapping = False
        self.stop_flag = threading.Event()
        self.mappings = mappings_ref
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
                            self.controllerHotplug.emit(f"Controller connected: {name}")
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
                        if value > AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis_id, "direction": 1}
                            raw_event_str = f"Axis {axis_id} > {AXIS_THRESHOLD:.1f}"
                        elif value < -AXIS_THRESHOLD:
                            event_details = {"type": "axis", "axis_id": axis_id, "direction": -1}
                            raw_event_str = f"Axis {axis_id} < -{AXIS_THRESHOLD:.1f}"
                        else:
                            for keyboard_key, mapping_info in list(self.mappings.items()):
                                if mapping_info and mapping_info["event_type"] == "axis" and \
                                   mapping_info["details"]["axis_id"] == axis_id:
                                    if self.active_axis_keys.get(keyboard_key) == mapping_info["details"]["direction"]:
                                        self.mappedEventTriggered.emit(keyboard_key, False)
                                        if keyboard_key in self.active_axis_keys:
                                            del self.active_axis_keys[keyboard_key]
                    elif event.type == pygame.JOYBUTTONDOWN:
                        event_details = {"type": "button", "button_id": event.button}
                        raw_event_str = f"Button {event.button} Down"
                    elif event.type == pygame.JOYBUTTONUP:
                        for keyboard_key, mapping_info in self.mappings.items():
                            if mapping_info and mapping_info["event_type"] == "button" and \
                               mapping_info["details"]["button_id"] == event.button:
                                self.mappedEventTriggered.emit(keyboard_key, False)
                                break
                    elif event.type == pygame.JOYHATMOTION:
                        hat_id = event.hat
                        hat_value_tuple = event.value
                        for keyboard_key, mapping_info in list(self.mappings.items()):
                            if mapping_info and mapping_info["event_type"] == "hat" and \
                               mapping_info["details"]["hat_id"] == hat_id:
                                active_hat_val_tuple = tuple(self.active_hat_keys.get(keyboard_key, (0,0)))
                                mapped_hat_val_tuple = tuple(mapping_info["details"]["value"])
                                if active_hat_val_tuple == mapped_hat_val_tuple and hat_value_tuple != mapped_hat_val_tuple:
                                    self.mappedEventTriggered.emit(keyboard_key, False)
                                    if keyboard_key in self.active_hat_keys:
                                        del self.active_hat_keys[keyboard_key]
                        if hat_value_tuple != (0,0):
                            event_details = {"type": "hat", "hat_id": hat_id, "value": list(hat_value_tuple)}
                            raw_event_str = f"Hat {hat_id} {hat_value_tuple}"
                    if self.is_listening_for_mapping and event_details:
                        logging.info(f"Event captured for mapping: {raw_event_str} -> {event_details}")
                        self.controllerEventCaptured.emit(event_details, raw_event_str)
                        self.is_listening_for_mapping = False
                    elif not self.is_listening_for_mapping and event_details:
                        for keyboard_key, mapping_info in self.mappings.items():
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
                                if mapping_info["event_type"] == "axis":
                                    if self.active_axis_keys.get(keyboard_key) != mapping_info["details"]["direction"]:
                                        self.mappedEventTriggered.emit(keyboard_key, True)
                                        self.active_axis_keys[keyboard_key] = mapping_info["details"]["direction"]
                                elif mapping_info["event_type"] == "hat":
                                    if tuple(self.active_hat_keys.get(keyboard_key, ())) != tuple(event_details["value"]):
                                        self.mappedEventTriggered.emit(keyboard_key, True)
                                        self.active_hat_keys[keyboard_key] = list(event_details["value"])
                                else: # Button
                                    self.mappedEventTriggered.emit(keyboard_key, True)
                                break
                time.sleep(0.01)
            except pygame.error as e:
                logging.error(f"Pygame error in controller loop: {e}")
                self.controllerHotplug.emit(f"Pygame error: {e}. Trying to recover...")
                self.joystick = None
                pygame.joystick.quit()
                pygame.joystick.init()
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
        self.setWindowTitle("Controller to Keyboard Mapper v0.4 (Path & Init Fix)")
        self.setGeometry(100, 100, 800, 600)

        self.keyboard = KeyboardController()
        self.currently_pressed_keys = set()
        self.mappings = {}
        logging.info("MainWindow initializing...")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Initialize GUI elements that might be used by load_mappings FIRST ---
        self.status_label = QLabel("Initializing...")
        main_layout.addWidget(self.status_label)

        self.debug_console = QTextEdit() # Create debug_console
        self.debug_console.setReadOnly(True)
        self.debug_console.setFixedHeight(100)
        # It will be added to layout later, but must exist for log_to_debug_console

        # --- Now load mappings as status_label and debug_console exist ---
        self.load_mappings()

        # --- Remaining GUI Element Setup ---
        mapping_controls_layout = QHBoxLayout()
        self.key_to_map_combo = QComboBox()
        self.key_to_map_combo.addItems(MAPPABLE_KEYS)
        mapping_controls_layout.addWidget(QLabel("Keyboard Key:"))
        mapping_controls_layout.addWidget(self.key_to_map_combo)
        self.listen_button = QPushButton("Listen for Controller Input to Map")
        self.listen_button.clicked.connect(self.start_listening_for_map)
        mapping_controls_layout.addWidget(self.listen_button)
        main_layout.addLayout(mapping_controls_layout)

        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(5)
        self.mappings_table.setHorizontalHeaderLabels(["Key", "Controller Input", "Friendly Name", "Rename", "Clear"])
        self.mappings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.mappings_table.setColumnWidth(1, 150)
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
        main_layout.addLayout(file_buttons_layout)

        # Add the debug console to the layout now
        main_layout.addWidget(QLabel("Debug Log:"))
        main_layout.addWidget(self.debug_console)

        # --- Controller Thread ---
        self.controller_thread = PygameControllerThread(self.mappings)
        self.controller_thread.controllerEventCaptured.connect(self.on_controller_event_captured)
        self.controller_thread.mappedEventTriggered.connect(self.on_mapped_event_triggered)
        self.controller_thread.controllerHotplug.connect(self.update_status_and_log)
        self.controller_thread.start()

        self.refresh_mappings_table()
        logging.info("MainWindow initialized and controller thread started.")

    # update_status_and_log, log_to_debug_console (same as before)
    def update_status_and_log(self, message):
        self.status_label.setText(message)
        self.log_to_debug_console(message)
        if "error" in message.lower() or "lost" in message.lower() or "no controller" in message.lower():
            logging.warning(f"Status Update: {message}")
        else:
            logging.info(f"Status Update: {message}")

    def log_to_debug_console(self, message):
        if hasattr(self, 'debug_console'): # Check if it exists
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.debug_console.append(f"[{timestamp}] {message}")
            self.debug_console.ensureCursorVisible()
        else: # Fallback if somehow called too early (shouldn't happen with new init order)
            logging.warning(f"Debug console not ready for message: {message}")


    # start_listening_for_map, on_controller_event_captured, on_mapped_event_triggered (same as before)
    def start_listening_for_map(self):
        self.current_listening_key = self.key_to_map_combo.currentText()
        logging.debug(f"start_listening_for_map called for key: {self.current_listening_key}")
        if not self.current_listening_key:
            QMessageBox.warning(self, "No Key Selected", "Please select a keyboard key to map.")
            return
        self.controller_thread.start_listening()
        self.update_status_and_log(f"Listening for controller input for '{self.current_listening_key}'...")
        self.listen_button.setText("Listening... (Press Controller Input)")
        self.listen_button.setEnabled(False)
        self.key_to_map_combo.setEnabled(False)

    def on_controller_event_captured(self, event_details, raw_event_str):
        logging.info(f"on_controller_event_captured: Key='{self.current_listening_key}', Raw='{raw_event_str}', Details={event_details}")
        existing_key_for_this_controller_input = None
        for key, mapping_info in self.mappings.items():
            if mapping_info and mapping_info["raw_str"] == raw_event_str:
                if key != self.current_listening_key:
                    existing_key_for_this_controller_input = key
                break
        if existing_key_for_this_controller_input:
            reply = QMessageBox.question(self, "Input Already Mapped",
                                         f"The controller input '{raw_event_str}' is already mapped to key '{existing_key_for_this_controller_input}'.\n"
                                         f"Do you want to unmap it from '{existing_key_for_this_controller_input}' and map it to '{self.current_listening_key}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.update_status_and_log(f"Mapping for '{self.current_listening_key}' cancelled.")
                self.listen_button.setText("Listen for Controller Input to Map")
                self.listen_button.setEnabled(True)
                self.key_to_map_combo.setEnabled(True)
                self.current_listening_key = None
                self.controller_thread.stop_listening()
                return
            else:
                if existing_key_for_this_controller_input in self.mappings:
                    logging.info(f"Unmapping '{raw_event_str}' from old key '{existing_key_for_this_controller_input}'")
                    del self.mappings[existing_key_for_this_controller_input]
        if self.current_listening_key:
            self.mappings[self.current_listening_key] = {
                "event_type": event_details["type"],
                "details": event_details,
                "raw_str": raw_event_str,
                "friendly_name": f"{raw_event_str}"
            }
            self.update_status_and_log(f"Mapped '{raw_event_str}' to '{self.current_listening_key}'.")
            logging.info(f"New mapping: {self.current_listening_key} -> {self.mappings[self.current_listening_key]}")
            self.refresh_mappings_table()
            self.current_listening_key = None
        self.listen_button.setText("Listen for Controller Input to Map")
        self.listen_button.setEnabled(True)
        self.key_to_map_combo.setEnabled(True)
        self.controller_thread.stop_listening()

    def on_mapped_event_triggered(self, keyboard_key_str, is_press_event):
        pynput_key = get_pynput_key(keyboard_key_str)
        if not pynput_key:
            logging.warning(f"Could not get pynput_key for '{keyboard_key_str}'")
            return
        try:
            if is_press_event:
                if pynput_key not in self.currently_pressed_keys:
                    self.keyboard.press(pynput_key)
                    self.currently_pressed_keys.add(pynput_key)
            else:
                if pynput_key in self.currently_pressed_keys:
                    self.keyboard.release(pynput_key)
                    self.currently_pressed_keys.remove(pynput_key)
        except Exception as e:
            logging.error(f"Pynput error for key '{keyboard_key_str}' (Press={is_press_event}): {e}")


    # refresh_mappings_table (same as before)
    def refresh_mappings_table(self):
        logging.debug("Refreshing mappings table...")
        self.mappings_table.setRowCount(0)
        for keyboard_key in MAPPABLE_KEYS:
            mapping_info = self.mappings.get(keyboard_key)
            row_position = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row_position)
            self.mappings_table.setItem(row_position, 0, QTableWidgetItem(keyboard_key))
            if mapping_info:
                self.mappings_table.setItem(row_position, 1, QTableWidgetItem(mapping_info["raw_str"]))
                self.mappings_table.setItem(row_position, 2, QTableWidgetItem(mapping_info["friendly_name"]))
                rename_button = QPushButton("Rename")
                rename_button.clicked.connect(lambda checked, k=keyboard_key: self.rename_friendly_name_prompt_button(k))
                self.mappings_table.setCellWidget(row_position, 3, rename_button)
                clear_button = QPushButton("Clear")
                clear_button.clicked.connect(lambda checked, k=keyboard_key: self.clear_mapping(k))
                self.mappings_table.setCellWidget(row_position, 4, clear_button)
            else:
                self.mappings_table.setItem(row_position, 1, QTableWidgetItem("Not Mapped"))
                self.mappings_table.setItem(row_position, 2, QTableWidgetItem(""))
                empty_rename_button = QPushButton("---")
                empty_rename_button.setEnabled(False)
                self.mappings_table.setCellWidget(row_position, 3, empty_rename_button)
                empty_clear_button = QPushButton("---")
                empty_clear_button.setEnabled(False)
                self.mappings_table.setCellWidget(row_position, 4, empty_clear_button)
        logging.debug("Mappings table refresh complete.")


    # handle_table_double_click, change_keyboard_key_assignment_prompt (same as before)
    def handle_table_double_click(self, row, column):
        current_keyboard_key_item = self.mappings_table.item(row, 0)
        if not current_keyboard_key_item: return
        current_keyboard_key = current_keyboard_key_item.text()
        logging.debug(f"Table double-clicked: Row={row}, Col={column}, Key='{current_keyboard_key}'")
        if column == 0:
            self.change_keyboard_key_assignment_prompt(current_keyboard_key)
        elif column == 2:
            if self.mappings.get(current_keyboard_key):
                self.rename_friendly_name_prompt_button(current_keyboard_key)

    def change_keyboard_key_assignment_prompt(self, old_keyboard_key):
        logging.debug(f"change_keyboard_key_assignment_prompt for '{old_keyboard_key}'")
        current_mapping_data = self.mappings.get(old_keyboard_key)
        if not current_mapping_data:
            QMessageBox.information(self, "Not Mapped", f"Key '{old_keyboard_key}' is not currently mapped.")
            return
        available_keys_for_reassign = [k for k in MAPPABLE_KEYS if k not in self.mappings or k == old_keyboard_key]
        available_keys_for_reassign.sort()
        try: current_selection_index = available_keys_for_reassign.index(old_keyboard_key)
        except ValueError: current_selection_index = 0
        new_key, ok = QInputDialog.getItem(self, "Change Keyboard Key Assignment",
                                           f"Select new keyboard key for controller input:\n'{current_mapping_data['raw_str']}' (currently '{old_keyboard_key}')",
                                           available_keys_for_reassign, current_selection_index, False)
        if ok and new_key and new_key != old_keyboard_key:
            logging.info(f"Attempting to reassign mapping from '{old_keyboard_key}' to '{new_key}'")
            del self.mappings[old_keyboard_key]
            self.mappings[new_key] = current_mapping_data
            self.refresh_mappings_table()
            self.update_status_and_log(f"Mapping for '{current_mapping_data['raw_str']}' moved from '{old_keyboard_key}' to '{new_key}'.")
        elif ok and new_key == old_keyboard_key: logging.debug("Keyboard key assignment unchanged.")
        else: logging.debug("Keyboard key assignment cancelled.")

    # rename_friendly_name_prompt_button, clear_mapping (same as before)
    def rename_friendly_name_prompt_button(self, keyboard_key):
        logging.debug(f"rename_friendly_name_prompt_button for key '{keyboard_key}'")
        mapping_info = self.mappings.get(keyboard_key)
        if mapping_info:
            current_name = mapping_info.get("friendly_name", mapping_info.get("raw_str", ""))
            text, ok = QInputDialog.getText(self, "Rename Mapping",
                                            f"Enter new friendly name for '{keyboard_key}' (mapped to {mapping_info['raw_str']}):",
                                            QLineEdit.Normal, current_name)
            if ok and text:
                mapping_info["friendly_name"] = text
                self.refresh_mappings_table()
                self.update_status_and_log(f"Renamed mapping for '{keyboard_key}'.")
                logging.info(f"Mapping for '{keyboard_key}' renamed to '{text}'. Current mapping: {self.mappings[keyboard_key]}")

    def clear_mapping(self, keyboard_key):
        logging.debug(f"clear_mapping for key '{keyboard_key}'")
        if keyboard_key in self.mappings:
            del self.mappings[keyboard_key]
            self.refresh_mappings_table()
            self.update_status_and_log(f"Cleared mapping for '{keyboard_key}'.")
            logging.info(f"Mapping for '{keyboard_key}' cleared.")


    # save_mappings (ensure directory exists)
    def save_mappings(self):
        logging.info(f"Attempting to save mappings to {MAPPINGS_FILE}")
        # Ensure the settings directory exists (SETTINGS_DIR is now SCRIPT_DIR, so it should exist)
        # However, if SETTINGS_DIR were a sub-folder, this would be crucial:
        # if not os.path.exists(SETTINGS_DIR):
        #     try:
        #         os.makedirs(SETTINGS_DIR)
        #         logging.info(f"Created settings directory: {SETTINGS_DIR}")
        #     except OSError as e:
        #         logging.exception(f"Could not create settings directory {SETTINGS_DIR}:")
        #         QMessageBox.critical(self, "Save Error", f"Could not create settings directory: {e}")
        #         self.update_status_and_log(f"Error creating settings directory: {e}")
        #         return

        logging.debug(f"Mappings to save: {json.dumps(self.mappings, indent=2)}")
        try:
            with open(MAPPINGS_FILE, 'w') as f:
                json.dump(self.mappings, f, indent=4)
            self.update_status_and_log(f"Mappings saved to {MAPPINGS_FILE}")
        except Exception as e:
            logging.exception(f"Could not save mappings to {MAPPINGS_FILE}:")
            QMessageBox.critical(self, "Save Error", f"Could not save mappings: {e}")
            self.update_status_and_log(f"Error saving mappings: {e}")

    # load_mappings (same as before, path is now corrected globally)
    def load_mappings(self):
        logging.info(f"Attempting to load mappings from {MAPPINGS_FILE}")
        temp_loaded_mappings = {}
        file_found = False
        try:
            with open(MAPPINGS_FILE, 'r') as f:
                temp_loaded_mappings = json.load(f)
                file_found = True
                logging.debug(f"Raw loaded mappings from file: {json.dumps(temp_loaded_mappings, indent=2)}")
            self.mappings.clear()
            loaded_count = 0
            skipped_count = 0
            for key_from_mappable_list in MAPPABLE_KEYS:
                if key_from_mappable_list in temp_loaded_mappings:
                    loaded_entry = temp_loaded_mappings[key_from_mappable_list]
                    if isinstance(loaded_entry, dict) and \
                       all(k_check in loaded_entry for k_check in ["event_type", "details", "raw_str", "friendly_name"]) and \
                       isinstance(loaded_entry.get("details"), dict) and \
                       isinstance(loaded_entry.get("event_type"), str) and \
                       isinstance(loaded_entry.get("raw_str"), str) and \
                       isinstance(loaded_entry.get("friendly_name"), str):
                        valid_structure = False
                        event_type = loaded_entry["event_type"]
                        details = loaded_entry["details"]
                        if event_type == "button" and "button_id" in details: valid_structure = True
                        elif event_type == "axis" and "axis_id" in details and "direction" in details: valid_structure = True
                        elif event_type == "hat" and "hat_id" in details and "value" in details and isinstance(details["value"], list): valid_structure = True
                        if valid_structure:
                            self.mappings[key_from_mappable_list] = loaded_entry
                            loaded_count += 1
                        else:
                            logging.warning(f"Entry for '{key_from_mappable_list}' in {MAPPINGS_FILE} has invalid 'details' or 'event_type' structure. Skipping. Entry: {loaded_entry}")
                            skipped_count += 1
                    else:
                        logging.warning(f"Entry for '{key_from_mappable_list}' in {MAPPINGS_FILE} is malformed or missing required keys. Skipping. Entry: {loaded_entry}")
                        skipped_count += 1
            logging.info(f"Load complete. Loaded {loaded_count} valid mappings. Skipped {skipped_count} malformed/invalid entries.")
            logging.debug(f"Final self.mappings after load: {json.dumps(self.mappings, indent=2)}")
            if hasattr(self, 'status_label') and self.status_label: # Ensure status_label exists
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

    # load_mappings_and_refresh, closeEvent (same as before)
    def load_mappings_and_refresh(self):
        logging.info("load_mappings_and_refresh called.")
        self.load_mappings()
        self.refresh_mappings_table()
        self.update_status_and_log("Mappings reloaded and GUI updated.")

    def closeEvent(self, event):
        logging.info("Close event received. Shutting down.")
        self.update_status_and_log("Stopping controller thread...")
        if hasattr(self, 'controller_thread') and self.controller_thread.isRunning():
            self.controller_thread.stop()
            self.controller_thread.wait(1500)
        for pynput_key in list(self.currently_pressed_keys):
            try:
                self.keyboard.release(pynput_key)
                logging.debug(f"Released key {pynput_key} on close.")
            except Exception as e:
                logging.warning(f"Error releasing key {pynput_key} on close: {e}")
        self.save_mappings()
        event.accept()
        logging.info("Application closed.")


if __name__ == "__main__":
    logging.info("Application starting...")
    # For Scenario 1, SETTINGS_DIR is SCRIPT_DIR. The directory the script is in must exist.
    # No need to os.makedirs(SCRIPT_DIR) as it inherently exists if the script is running.
    # If you had a deeper SETTINGS_SUBDIR, then os.makedirs(SETTINGS_DIR, exist_ok=True) here would be good.
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())