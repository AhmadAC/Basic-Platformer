import sys
import os
import traceback
import time # For monotonic timer if needed
from typing import Dict, Optional, Any, List, Tuple

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QColor, QPalette, QScreen, QKeySequence) # Added QScreen, QKeySequence
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QSize

# --- Add project root to sys.path for module imports ---
_maps_package_import_path_added = "None"
_maps_package_physical_location_debug = "Not determined"
_is_frozen = getattr(sys, 'frozen', False)
_bundle_dir_meipass = getattr(sys, '_MEIPASS', None)

if _is_frozen and _bundle_dir_meipass:
    _path_to_maps_in_bundle_root = os.path.join(_bundle_dir_meipass, 'maps')
    _maps_package_physical_location_debug = f"Bundled - Expected at: {_path_to_maps_in_bundle_root}"
    if os.path.isdir(_path_to_maps_in_bundle_root):
        if _bundle_dir_meipass not in sys.path:
            sys.path.insert(0, _bundle_dir_meipass)
            _maps_package_import_path_added = _bundle_dir_meipass
        _maps_package_physical_location_debug += " (Found, _MEIPASS in sys.path for 'maps' import)"
    else:
        _exe_parent_dir = os.path.dirname(sys.executable)
        _maps_next_to_exe_path = os.path.join(_exe_parent_dir, 'maps')
        _maps_package_physical_location_debug += f"; Alt check: {_maps_next_to_exe_path}"
        if os.path.isdir(_maps_next_to_exe_path):
            if _exe_parent_dir not in sys.path:
                sys.path.insert(0, _exe_parent_dir)
                _maps_package_import_path_added = _exe_parent_dir
            _maps_package_physical_location_debug += " (Found next to EXE, parent in sys.path for 'maps' import)"
        else:
            _maps_package_physical_location_debug += " (NOT found in _MEIPASS or next to EXE)"
else:
    _project_root = os.path.abspath(os.path.dirname(__file__))
    _dev_maps_package_path = os.path.join(_project_root, 'maps')
    _maps_package_physical_location_debug = f"Dev - Expected at: {_dev_maps_package_path}"
    if os.path.isdir(_dev_maps_package_path):
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
            _maps_package_import_path_added = _project_root
        _maps_package_physical_location_debug += " (Found, project root in sys.path for 'maps' import)"
    else:
        _maps_package_physical_location_debug += " (NOT found in project root)"

# --- Game Module Imports ---
try:
    from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
    info(f"MAIN PySide6: Path added to sys.path for 'maps' package import: {_maps_package_import_path_added}")
    info(f"MAIN PySide6: Physical location check for 'maps' package: {_maps_package_physical_location_debug}")

    import constants as C
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode, find_server_on_lan
    from couch_play_logic import run_couch_play_mode
    from game_ui import GameSceneWidget, SelectMapDialog, IPInputDialog
    import config as game_config
    import joystick_handler # Using 'inputs' library
    from player import Player
    # player_input_handler is refactored, process_player_input_logic is the main entry point
    from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
    info("MAIN PySide6: Platformer modules imported successfully.")
except ImportError as e:
    print(f"MAIN PySide6 FATAL: Failed to import a required platformer module: {e}")
    print(f"Current sys.path was: {sys.path}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"MAIN PySide6 FATAL: An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Pyperclip check ---
PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    info("MAIN PySide6: Pyperclip library found.")
except ImportError:
    warning("MAIN PySide6: Pyperclip library not found. Paste in UI may be limited.")

def get_clipboard_text_qt() -> Optional[str]:
    clipboard = QApplication.clipboard()
    return clipboard.text() if clipboard else None

def set_clipboard_text_qt(text: str):
    clipboard = QApplication.clipboard()
    if clipboard: clipboard.setText(text)

# --- Key Name to Qt.Key Mapping ---
QT_KEY_MAP = {
    "A": Qt.Key.Key_A, "D": Qt.Key.Key_D, "W": Qt.Key.Key_W, "S": Qt.Key.Key_S,
    "V": Qt.Key.Key_V, "B": Qt.Key.Key_B,
    "SHIFT": Qt.Key.Key_Shift, "LSHIFT": Qt.Key.Key_Shift,
    "CONTROL": Qt.Key.Key_Control, "LCONTROL": Qt.Key.Key_Control,
    "E": Qt.Key.Key_E,
    "1": Qt.Key.Key_1, "2": Qt.Key.Key_2, "3": Qt.Key.Key_3, "4": Qt.Key.Key_4,
    "5": Qt.Key.Key_5, "6": Qt.Key.Key_6, "7": Qt.Key.Key_7,
    "ESCAPE": Qt.Key.Key_Escape, "RETURN": Qt.Key.Key_Return, "ENTER": Qt.Key.Key_Enter,
    "UP": Qt.Key.Key_Up, "DOWN": Qt.Key.Key_Down, "LEFT": Qt.Key.Key_Left, "RIGHT": Qt.Key.Key_Right,
    "SPACE": Qt.Key.Key_Space,
    "J": Qt.Key.Key_J, "L": Qt.Key.Key_L, "I": Qt.Key.Key_I, "K": Qt.Key.Key_K,
    "O": Qt.Key.Key_O, "P": Qt.Key.Key_P,
    ";": Qt.Key.Key_Semicolon, "'": Qt.Key.Key_Apostrophe, "\\": Qt.Key.Key_Backslash,
    "NUM+1": Qt.Key.Key_1, "NUM+2": Qt.Key.Key_2, "NUM+3": Qt.Key.Key_3,
    "NUM+4": Qt.Key.Key_4, "NUM+5": Qt.Key.Key_5, "NUM+6": Qt.Key.Key_6,
    "NUM+7": Qt.Key.Key_7, "NUM+8": Qt.Key.Key_8, # For menu up on P2 numpad
    "NUM+ENTER": Qt.Key.Key_Enter, # Note: Qt.Key_Enter is often same as Return
    "DELETE": Qt.Key.Key_Delete,
    "PAUSE": Qt.Key.Key_Pause,
}

# --- Global App Status ---
class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        # Ensure QApplication also quits
        app_instance = QApplication.instance()
        if app_instance:
            debug("APP_STATUS: Requesting QApplication.quit().")
            app_instance.quit()

APP_STATUS = AppStatus()

_app_start_time = time.monotonic()
def get_current_game_ticks(): return int((time.monotonic() - _app_start_time) * 1000)

_qt_keys_pressed_snapshot: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame: List[QKeyEvent] = []

_joystick_axis_values_pyside: Dict[int, Dict[int, float]] = {}
_joystick_button_states_pyside: Dict[int, Dict[int, bool]] = {}
_joystick_hat_values_pyside: Dict[int, Dict[int, Tuple[int, int]]] = {}
_prev_joystick_button_states_pyside: Dict[int, Dict[int, bool]] = {} # For "just pressed"

# --- Network Operation Threads (from your existing code, ensure compatibility) ---
class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float) # title, message, progress
    operation_finished_signal = Signal(str) # Success/failure message or mode_ended

    def __init__(self, mode: str, game_elements_ref: Dict[str, Any], server_state_ref: Optional[ServerState] = None, client_state_ref: Optional[ClientState] = None, target_ip_port: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.game_elements = game_elements_ref
        self.server_state = server_state_ref
        self.client_state = client_state_ref
        self.target_ip_port = target_ip_port

    def _ui_status_update_callback(self, title: str, message: str, progress: float):
        self.status_update_signal.emit(title, message, progress)

    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any, platforms_list: List[Any]) -> Dict[str, bool]:
        return {} 

    def run(self):
        try:
            if self.mode == "host" and self.server_state:
                info("NetworkThread: Starting run_server_mode...")
                run_server_mode(
                    self.server_state, self.game_elements,
                    ui_status_update_callback=self._ui_status_update_callback,
                    get_p1_input_snapshot_callback=self._get_p1_input_snapshot_main_thread_passthrough,
                    process_qt_events_callback=lambda: QApplication.processEvents()
                )
                info("NetworkThread: run_server_mode finished.")
                self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state:
                info("NetworkThread: Starting run_client_mode...")
                run_client_mode(
                    self.client_state, self.game_elements,
                    ui_status_update_callback=self._ui_status_update_callback,
                    target_ip_port_str=self.target_ip_port,
                    get_input_snapshot_callback=MainWindow.get_p2_input_snapshot_for_client_thread, # Static method call
                    process_qt_events_callback=lambda: QApplication.processEvents()
                )
                info("NetworkThread: run_client_mode finished.")
                self.operation_finished_signal.emit("client_ended")
        except Exception as e:
            critical(f"NetworkThread: Exception in {self.mode} mode: {e}", exc_info=True)
            self.operation_finished_signal.emit(f"{self.mode}_error")

class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object)

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN (PySide6)") # Removed version for now
        
        screen_geo = QApplication.primaryScreen().availableGeometry()
        initial_width = max(800, min(1600, int(screen_geo.width() * 0.75)))
        initial_height = max(600, min(900, int(screen_geo.height() * 0.75)))
        self.setMinimumSize(QSize(800,600))
        self.resize(initial_width, initial_height)
        info(f"MAIN PySide6: Initial window size: {initial_width}x{initial_height}")

        self.fonts = {
            "small": QFont("Arial", 10), "medium": QFont("Arial", 14),
            "large": QFont("Arial", 24, QFont.Weight.Bold), "debug": QFont("Monospace", 9)
        }
        
        try:
            joystick_handler.init_joysticks()
            game_config.load_config()
            self._translate_config_key_mappings()
        except Exception as e_cfg: critical(f"Error during joystick/config init: {e_cfg}", exc_info=True)

        self.app_status = APP_STATUS
        self.game_elements: Dict[str, Any] = {}
        self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None
        self.lan_search_dialog: Optional[QDialog] = None

        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.game_tick)
        
        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = self._create_main_menu_widget()
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)
        
        self.stacked_widget.addWidget(self.main_menu_widget)
        self.stacked_widget.addWidget(self.game_scene_widget)
        
        self.setCentralWidget(self.stacked_widget)
        self.show_main_menu_ui()

        self.network_status_update.connect(self.on_network_status_update)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update)

        self.status_dialog: Optional[QDialog] = None
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None

    def _translate_config_key_mappings(self):
        info("Translating keyboard mappings from config strings to Qt.Key values.")
        # Translate default mappings first
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P1_MAPPINGS)
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P2_MAPPINGS)
        
        # After game_config.load_config(), P1_MAPPINGS and P2_MAPPINGS are set.
        # Re-translate these active mappings if they are keyboard-based.
        if game_config.CURRENT_P1_INPUT_DEVICE == "keyboard_p1" or game_config.CURRENT_P1_INPUT_DEVICE == "keyboard_p2":
            self._apply_qt_key_translation_to_map_definition(game_config.P1_MAPPINGS)
        if game_config.CURRENT_P2_INPUT_DEVICE == "keyboard_p1" or game_config.CURRENT_P2_INPUT_DEVICE == "keyboard_p2":
            self._apply_qt_key_translation_to_map_definition(game_config.P2_MAPPINGS)
        info("Keyboard mapping translation complete.")

    def _apply_qt_key_translation_to_map_definition(self, mapping_dict: Dict[str, Any]):
        """Helper to translate string key names in a given mapping dictionary to Qt.Key values."""
        keys_to_update = list(mapping_dict.keys())
        for action_name in keys_to_update:
            key_val = mapping_dict[action_name]
            if isinstance(key_val, str): # Only translate if it's a string (original format)
                qt_key_enum = QT_KEY_MAP.get(key_val.upper())
                if qt_key_enum is not None:
                    mapping_dict[action_name] = qt_key_enum
                elif len(key_val) == 1:
                    try:
                        # QKeySequence can parse single characters to Qt.Key
                        # Example: QKeySequence("A")[0].key() yields Qt.Key_A
                        key_from_seq = QKeySequence(key_val.upper())
                        if key_from_seq.count() > 0:
                             qt_enum_val = Qt.Key(key_from_seq[0].key())
                             if qt_enum_val != Qt.Key.Key_unknown:
                                mapping_dict[action_name] = qt_enum_val
                                if key_val.upper() not in QT_KEY_MAP: # Cache it
                                    QT_KEY_MAP[key_val.upper()] = qt_enum_val
                             else: warning(f"Config Translation: Key string '{key_val}' for '{action_name}' resolved to Key_unknown. Kept as string.")
                        else: warning(f"Config Translation: Key string '{key_val}' for '{action_name}' not parsable by QKeySequence. Kept as string.")
                    except Exception as e_seq:
                        warning(f"Config Translation: Error parsing key string '{key_val}' for '{action_name}': {e_seq}. Kept as string.")
                else:
                    warning(f"Config Translation: Key string '{key_val}' for '{action_name}' not in QT_KEY_MAP and not single char. Kept as string.")

    def _create_main_menu_widget(self) -> QWidget:
        menu_widget = QWidget()
        layout = QVBoxLayout(menu_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)

        title_label = QLabel("Platformer Adventure LAN")
        title_label.setFont(self.fonts["large"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        buttons_data = [
            ("Couch Co-op", self.on_start_couch_play),
            ("Host Game", self.on_start_host_game),
            ("Join LAN Game", self.on_start_join_lan),
            ("Join by IP", self.on_start_join_ip),
            ("Level Editor", self.on_launch_editor),
            ("Settings/Controls", self.on_show_settings),
            ("Quit", self.request_close_app) # Changed to use self.close()
        ]

        for text, slot_func in buttons_data:
            button = QPushButton(text)
            button.setFont(self.fonts["medium"])
            button.setMinimumHeight(40); button.setMinimumWidth(250) # Ensure buttons are reasonably sized
            button.clicked.connect(slot_func)
            layout.addWidget(button)
        return menu_widget
    
    def request_close_app(self):
        info("MAIN PySide6: Quit button pressed, requesting main window close via self.close().")
        self.close() # This will trigger MainWindow.closeEvent which calls APP_STATUS.quit_app()

    def on_launch_editor(self):
        editor_path = os.path.join(os.path.dirname(__file__), 'editor', 'editor.py')
        if os.path.exists(editor_path):
            info(f"MAIN PySide6: Attempting to launch Level Editor: {editor_path}")
            try:
                # This is a simple way to launch another Python script.
                # For a more integrated experience, the editor could be a QProcess or a module directly imported and run.
                import subprocess
                subprocess.Popen([sys.executable, editor_path]) # Launch as a separate process
                QMessageBox.information(self, "Level Editor", "Level Editor launched in a new window.")
            except Exception as e:
                error(f"MAIN PySide6: Failed to launch editor: {e}")
                QMessageBox.warning(self, "Launch Error", f"Could not launch editor: {e}")
        else:
            QMessageBox.warning(self, "Editor Not Found", f"Level Editor script not found at: {editor_path}")

    def on_show_settings(self):
        # Path to the controller mapper GUI
        mapper_path = os.path.join(os.path.dirname(__file__), 'controller_settings', 'controller_mapper_gui.py')
        if os.path.exists(mapper_path):
            info(f"MAIN PySide6: Attempting to launch Controller Mapper: {mapper_path}")
            try:
                import subprocess
                subprocess.Popen([sys.executable, mapper_path])
                QMessageBox.information(self, "Controller Settings", "Controller Mapper GUI launched in a new window.")
            except Exception as e:
                error(f"MAIN PySide6: Failed to launch controller mapper: {e}")
                QMessageBox.warning(self, "Launch Error", f"Could not launch controller mapper: {e}")
        else:
            QMessageBox.warning(self, "Mapper Not Found", f"Controller Mapper GUI script not found at: {mapper_path}")


    def show_main_menu_ui(self):
        self.current_game_mode = None
        if self.game_timer.isActive(): self.game_timer.stop()
        self.stacked_widget.setCurrentWidget(self.main_menu_widget)
        self.setWindowTitle("Platformer Adventure LAN - Main Menu")
        # Clear input states when returning to menu
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        _qt_keys_pressed_snapshot.clear()
        _qt_key_events_this_frame.clear()


    def keyPressEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        if not event.isAutoRepeat():
            qt_key = Qt.Key(event.key())
            _qt_keys_pressed_snapshot[qt_key] = True
            # Store event only if game is active, to avoid menu events polluting game logic
            if self.current_game_mode: 
                _qt_key_events_this_frame.append(event) 
            
            if event.key() == Qt.Key.Key_Escape:
                if self.current_game_mode is None: # On main menu
                    self.request_close_app()
                else: # In a game mode, Escape should pause or bring up in-game menu
                    info(f"Escape pressed in mode {self.current_game_mode}. Stopping mode.")
                    # This will effectively act as a pause and return to menu for now.
                    self.stop_current_game_mode(show_menu=True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot
        if not event.isAutoRepeat():
            qt_key = Qt.Key(event.key())
            _qt_keys_pressed_snapshot[qt_key] = False
            # Note: _qt_key_events_this_frame typically captures KeyDown.
            # If KeyUp events are needed for specific logic by player_input_handler, it might need those too.
        super().keyReleaseEvent(event)
    
    # --- Input Snapshot Helper ---
    def _get_input_snapshot(self, player_instance: Player, player_id: int) -> Dict[str, bool]:
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        if not player_instance or not player_instance._valid_init: return {}

        active_mappings = {}
        joystick_id_for_player: Optional[int] = None

        if player_id == 1:
            active_mappings = game_config.P1_MAPPINGS
            if game_config.CURRENT_P1_INPUT_DEVICE.startswith("joystick_"):
                try: joystick_id_for_player = int(game_config.CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                except ValueError: pass
        elif player_id == 2:
            active_mappings = game_config.P2_MAPPINGS
            if game_config.CURRENT_P2_INPUT_DEVICE.startswith("joystick_"):
                try: joystick_id_for_player = int(game_config.CURRENT_P2_INPUT_DEVICE.split('_')[-1])
                except ValueError: pass
        
        # Collect joystick state for this player IF a joystick is assigned
        joystick_data_for_handler: Optional[Dict[str,Any]] = None
        if joystick_id_for_player is not None:
            joystick_data_for_handler = {
                'axes': _joystick_axis_values_pyside.get(joystick_id_for_player, {}),
                'buttons_current': _joystick_button_states_pyside.get(joystick_id_for_player, {}),
                'buttons_prev': _prev_joystick_button_states_pyside.get(joystick_id_for_player, {}),
                'hats': _joystick_hat_values_pyside.get(joystick_id_for_player, {})
            }
            # Update previous button state for next frame's "just pressed"
            _prev_joystick_button_states_pyside[joystick_id_for_player] = _joystick_button_states_pyside.get(joystick_id_for_player, {}).copy()

        action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot, # Current held Qt keys
            _qt_key_events_this_frame, # Discrete Qt key events for this frame
            active_mappings,
            self.game_elements.get("platforms_list", []),
            joystick_data=joystick_data_for_handler # Pass joystick data
        )
        return action_events

    @staticmethod
    def get_p2_input_snapshot_for_client_thread(player_instance: Any) -> Dict[str, Any]:
        if MainWindow._instance:
            # This needs to be careful about thread safety if accessing global input state directly.
            # For now, assuming direct access for simplicity.
            # A more robust method would involve signals or a queue from main thread to network thread.
            global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
            return MainWindow._instance._get_input_snapshot(player_instance, 2)
        return {}

    # ... (Game Mode Start Slots, Network UI Callbacks, Dialogs - largely same, ensure they use request_close_app or self.close() for quitting) ...
    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
        
        current_width, current_height = self.game_scene_widget.width(), self.game_scene_widget.height()
        if current_width <=0 or current_height <=0 : 
            current_width, current_height = self.width(), self.height()

        initialized_elements = initialize_game_elements(
            current_width, current_height, for_game_mode=mode,
            existing_game_elements=None, map_module_name=map_name
        )

        if initialized_elements is None:
            QMessageBox.critical(self, "Error", f"Failed to initialize game elements for {mode}. Check logs.")
            self.show_main_menu_ui(); return

        self.game_elements.clear(); self.game_elements.update(initialized_elements)
        self.current_game_mode = mode
        self.setWindowTitle(f"Platformer Adventure LAN - {mode.replace('_',' ').title()}")

        camera = self.game_elements.get("camera")
        if camera:
            camera.set_screen_dimensions(self.game_scene_widget.width(), self.game_scene_widget.height())
            if "level_pixel_width" in self.game_elements:
                camera.set_level_dimensions(
                    self.game_elements["level_pixel_width"],
                    self.game_elements["level_min_y_absolute"],
                    self.game_elements["level_max_y_absolute"]
                )
        
        self.game_scene_widget.game_elements = self.game_elements
        self.stacked_widget.setCurrentWidget(self.game_scene_widget)

        if mode in ["host", "join_lan", "join_ip"]:
            self._start_network_mode(mode, target_ip_port)
        
        self.game_timer.start(1000 // C.FPS)
        info(f"Game mode '{mode}' started.")

    def on_start_couch_play(self):
        map_name = self._select_map_dialog()
        if map_name: self._prepare_and_start_game("couch_play", map_name=map_name)

    def on_start_host_game(self):
        map_name = self._select_map_dialog()
        if map_name: self._prepare_and_start_game("host", map_name=map_name)

    def on_start_join_lan(self): self._show_lan_search_dialog()

    def on_start_join_ip(self):
        dialog = IPInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.ip_port_string:
            self._prepare_and_start_game("join_ip", target_ip_port=dialog.ip_port_string)
        else: info("Join by IP cancelled."); self.show_main_menu_ui()
            
    def _select_map_dialog(self) -> Optional[str]:
        dialog = SelectMapDialog(self.fonts, self)
        return dialog.selected_map_name if dialog.exec() == QDialog.DialogCode.Accepted else None

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        if self.network_thread and self.network_thread.isRunning():
            warning("NetworkThread already running. Attempting to stop existing one."); self.network_thread.quit(); self.network_thread.wait(1000)

        if mode_name == "host":
            self.server_state = ServerState(); self.server_state.current_map_name = self.game_elements.get("loaded_map_name")
            self.server_state.app_running = self.app_status.app_running 
            self.network_thread = NetworkThread(mode="host", game_elements_ref=self.game_elements, server_state_ref=self.server_state, parent=self)
        elif mode_name in ["join_lan", "join_ip"]:
            self.client_state = ClientState(); self.client_state.app_running = self.app_status.app_running
            self.network_thread = NetworkThread(mode="join", game_elements_ref=self.game_elements, client_state_ref=self.client_state, target_ip_port=target_ip_port, parent=self)
        
        if self.network_thread:
            self.network_thread.status_update_signal.connect(self.on_network_status_update)
            self.network_thread.operation_finished_signal.connect(self.on_network_operation_finished)
            self.network_thread.start(); self._show_status_dialog("Network Operation", f"Initializing {mode_name} mode...")
        else: error(f"Failed to create NetworkThread for mode {mode_name}"); self.show_main_menu_ui()

    def _show_status_dialog(self, title: str, initial_message: str):
        if self.status_dialog is None:
            self.status_dialog = QDialog(self); self.status_dialog.setWindowTitle(title)
            layout = QVBoxLayout(self.status_dialog); self.status_label_in_dialog = QLabel(initial_message)
            self.status_label_in_dialog.setWordWrap(True); layout.addWidget(self.status_label_in_dialog)
            self.status_progress_bar_in_dialog = QProgressBar(); self.status_progress_bar_in_dialog.setRange(0,100)
            self.status_progress_bar_in_dialog.setTextVisible(True); layout.addWidget(self.status_progress_bar_in_dialog)
            self.status_dialog.setMinimumWidth(350)
        else:
            self.status_dialog.setWindowTitle(title)
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(initial_message)
        if self.status_progress_bar_in_dialog: self.status_progress_bar_in_dialog.setValue(0); self.status_progress_bar_in_dialog.setVisible(False)
        self.status_dialog.show(); QApplication.processEvents()

    def _update_status_dialog(self, message: str, progress: float = -1.0):
        if self.status_dialog and self.status_dialog.isVisible():
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(message)
            if self.status_progress_bar_in_dialog:
                if progress >= 0: self.status_progress_bar_in_dialog.setValue(int(progress)); self.status_progress_bar_in_dialog.setVisible(True)
                else: self.status_progress_bar_in_dialog.setVisible(False)
        QApplication.processEvents()

    def _close_status_dialog(self):
        if self.status_dialog: self.status_dialog.hide()

    @Slot(str, str, float)
    def on_network_status_update(self, title: str, message: str, progress: float):
        if not self.status_dialog or not self.status_dialog.isVisible(): self._show_status_dialog(title, message)
        self._update_status_dialog(message, progress)
        if title in ["game_starting", "game_active"] or (title == "Map Sync" and "ready" in message.lower() and progress >= 100):
             self._close_status_dialog()

    @Slot(str)
    def on_network_operation_finished(self, message: str):
        info(f"Network operation finished: {message}"); self._close_status_dialog()
        if "error" in message.lower() or "failed" in message.lower():
            QMessageBox.critical(self, "Network Error", f"Network operation ended with error: {message}")
            self.stop_current_game_mode(show_menu=True)
        elif "ended" in message.lower():
            info(f"Mode {self.current_game_mode} finished normally via network thread signal.")
            self.stop_current_game_mode(show_menu=True)

    def _show_lan_search_dialog(self):
        if self.lan_search_dialog is None:
            self.lan_search_dialog = QDialog(self); self.lan_search_dialog.setWindowTitle("Searching for LAN Games...")
            layout = QVBoxLayout(self.lan_search_dialog); self.lan_search_status_label = QLabel("Searching...")
            layout.addWidget(self.lan_search_status_label); self.lan_servers_list_widget = QListWidget()
            layout.addWidget(self.lan_servers_list_widget)
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
            button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False); button_box.accepted.connect(self._join_selected_lan_server)
            button_box.rejected.connect(self.lan_search_dialog.reject); button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self._start_lan_server_search_thread)
            layout.addWidget(button_box); self.lan_search_dialog.rejected.connect(lambda: self.show_main_menu_ui())
            self.lan_servers_list_widget.itemDoubleClicked.connect(self._join_selected_lan_server)
        self.lan_servers_list_widget.clear(); self.lan_search_status_label.setText("Searching..."); self.lan_search_dialog.show()
        self._start_lan_server_search_thread()

    def _start_lan_server_search_thread(self):
        if self.lan_servers_list_widget: self.lan_servers_list_widget.clear()
        if self.lan_search_status_label: self.lan_search_status_label.setText("Searching...")
        if self.lan_search_dialog: self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.lan_search_worker = QThread()
        class LanSearchRunner(QWidget):
            found_signal = Signal(object)
            def __init__(self, client_state): super().__init__(); self.cs = client_state
            def run_search(self):
                result = find_server_on_lan(self.cs, lambda key, data: self.found_signal.emit((key, data)))
                self.found_signal.emit(("final_result", result if result else None))
        temp_client_state_for_search = ClientState()
        self.lan_search_run_obj = LanSearchRunner(temp_client_state_for_search)
        self.lan_search_run_obj.moveToThread(self.lan_search_worker)
        self.lan_search_worker.started.connect(self.lan_search_run_obj.run_search)
        self.lan_search_run_obj.found_signal.connect(self.on_lan_server_search_status_update)
        self.lan_search_worker.finished.connect(self.lan_search_worker.deleteLater)
        self.lan_search_worker.finished.connect(self.lan_search_run_obj.deleteLater)
        self.lan_search_worker.start()

    @Slot(str, object)
    def on_lan_server_search_status_update(self, status_key: str, data: Any):
        if not self.lan_search_dialog or not self.lan_search_dialog.isVisible(): return
        if self.lan_search_status_label: self.lan_search_status_label.setText(f"Status: {status_key} - {str(data)[:50]}")
        if status_key == "found" and isinstance(data, tuple) and len(data)==2:
            ip, port = data; item_text = f"Server at {ip}:{port}"
            self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        elif status_key == "timeout" or status_key == "error" or (status_key == "final_result" and data is None):
            if self.lan_servers_list_widget.count() == 0:
                 self.lan_search_status_label.setText(f"Search {status_key}. No servers found.")
                 self.lan_servers_list_widget.addItem("No servers found. Retry or Cancel.")
        elif status_key == "final_result" and data is not None:
             ip, port = data; item_text = f"Server at {ip}:{port}"
             if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly):
                 self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
             if self.lan_servers_list_widget.count() > 0: self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _join_selected_lan_server(self):
        if not self.lan_servers_list_widget or not self.lan_search_dialog: return
        selected_items = self.lan_servers_list_widget.selectedItems()
        if selected_items:
            ip_port_str = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if ip_port_str: self.lan_search_dialog.accept(); self._prepare_and_start_game("join_lan", target_ip_port=ip_port_str); return
        QMessageBox.warning(self, "No Selection", "Please select a server from the list.")

    def game_tick(self):
        global _qt_key_events_this_frame # Important: clear discrete events each tick
        
        if not self.app_status.app_running or not self.current_game_mode:
            self.stop_current_game_mode(show_menu=True)
            return

        dt_sec = 1.0 / float(C.FPS)
        current_game_time = get_current_game_ticks()
        
        # Process local input for P1 (host/couch) or P2 (client)
        p1 = self.game_elements.get("player1")
        p1_input_actions: Dict[str,bool] = {}
        if p1 and p1._valid_init and self.current_game_mode in ["host", "couch_play"]:
            p1_input_actions = self._get_input_snapshot(p1, 1)
            if p1_input_actions.get("pause"):
                info(f"Main {self.current_game_mode}: P1 Pause. Stopping mode.")
                self.stop_current_game_mode(show_menu=True); return

        if self.current_game_mode == "couch_play":
            p2 = self.game_elements.get("player2")
            p2_input_actions_couch: Dict[str,bool] = {}
            if p2 and p2._valid_init: p2_input_actions_couch = self._get_input_snapshot(p2, 2)
            should_continue = run_couch_play_mode(
                self.game_elements, self.app_status,
                get_p1_input_callback=lambda _p, _plats: p1_input_actions,
                get_p2_input_callback=lambda _p, _plats: p2_input_actions_couch,
                process_qt_events_callback=lambda: QApplication.processEvents(),
                dt_sec_provider=lambda: dt_sec,
                show_status_message_callback=lambda msg: self.statusBar().showMessage(msg, 2000)
            )
            if not should_continue or not self.app_status.app_running:
                self.stop_current_game_mode(show_menu=True); return
        
        # For "host" and "join" modes, the primary game logic loop might be in the NetworkThread.
        # This game_tick in MainWindow would then primarily be for rendering and local input processing
        # that needs to be fed *into* the NetworkThread's logic (e.g., P1 input for host, P2 input for client).
        # The current structure has run_server_mode and run_client_mode as blocking calls in the thread.

        dl_msg, dl_prog = None, None
        if self.client_state and self.current_game_mode in ["join_lan", "join_ip"]:
            if self.client_state.map_download_status not in ["present", "unknown", "game_active"]:
                dl_msg = f"Map: {self.client_state.server_selected_map_name or '...'} - Status: {self.client_state.map_download_status}"
                dl_prog = self.client_state.map_download_progress
        
        self.game_scene_widget.update_game_state(current_game_time, dl_msg, dl_prog)
        _qt_key_events_this_frame.clear() # Clear discrete key events after they've been processed for this tick

    def stop_current_game_mode(self, show_menu: bool = True):
        mode_stopped = self.current_game_mode; info(f"Stopping game mode: {mode_stopped}")
        self.current_game_mode = None
        if self.game_timer.isActive(): self.game_timer.stop()
        if self.network_thread and self.network_thread.isRunning():
            info("Requesting network thread to stop...")
            if self.server_state: self.server_state.app_running = False
            if self.client_state: self.client_state.app_running = False
            self.network_thread.quit(); 
            if not self.network_thread.wait(2000): warning("Network thread did not stop gracefully. Terminating."); self.network_thread.terminate(); self.network_thread.wait()
            info("Network thread stopped.")
        self.network_thread = None; self.server_state = None; self.client_state = None
        self._close_status_dialog()
        if self.lan_search_dialog and self.lan_search_dialog.isVisible(): self.lan_search_dialog.reject()
        self.game_elements.clear(); self.game_scene_widget.game_elements = self.game_elements
        if show_menu: self.show_main_menu_ui()
        info(f"Game mode '{mode_stopped}' stopped.")

    def closeEvent(self, event: QCloseEvent):
        info("Close event received. Shutting down application.")
        self.app_status.quit_app() 
        self.stop_current_game_mode(show_menu=False)
        joystick_handler.quit_joysticks()
        info("MAIN PySide6: Application terminated via closeEvent.")
        event.accept()

def main():
    app = QApplication.instance()
    if app is None: app = QApplication(sys.argv)
    if not LOGGING_ENABLED: print("INFO: Main.py started, file logging is OFF or failed. Basic console prints active.")
    info("MAIN PySide6: Application starting...")
    main_window = MainWindow()
    main_window.show()
    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")
    # Explicitly call quit on AppStatus if loop exited for other reasons than self.close()
    if APP_STATUS.app_running: APP_STATUS.quit_app() # Ensure threads know to stop
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        critical(f"MAIN PySide6 CRITICAL UNHANDLED EXCEPTION: {e}", exc_info=True)
        try:
            error_app = QApplication.instance()
            if not error_app: error_app = QApplication(sys.argv)
            msg_box = QMessageBox(); msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred and the application must close.")
            msg_box.setInformativeText(f"{e}\n\nDetails in {LOG_FILE_PATH if LOGGING_ENABLED else 'console'}.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        except Exception as e_msgbox: print(f"FATAL: Could not display Qt error message box: {e_msgbox}")
        traceback.print_exc(); sys.exit(1)