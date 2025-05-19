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
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent, QCloseEvent, QColor, QPalette
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QSize # Added QSize for window


# --- Add project root to sys.path for module imports ---
# This logic is copied from the provided main.py to ensure consistency
# with how it handles paths for 'maps' package.
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
    # Assuming this script (main.py) is in the project root
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
# These modules are expected to be refactored for PySide6
try:
    from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
    info(f"MAIN PySide6: Path added to sys.path for 'maps' package import: {_maps_package_import_path_added}")
    info(f"MAIN PySide6: Physical location check for 'maps' package: {_maps_package_physical_location_debug}")

    import constants as C
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode, find_server_on_lan
    from couch_play_logic import run_couch_play_mode
    from game_ui import GameSceneWidget, SelectMapDialog, IPInputDialog # GameSceneWidget for rendering
    import config as game_config
    import joystick_handler # Refactored for 'inputs' library
    from player import Player # For type hinting and input processing
    from player_input_handler import process_player_input_logic # For direct use in input snapshot
    info("MAIN PySide6: Platformer modules imported successfully.")
except ImportError as e:
    # Basic print fallback if logger itself fails
    print(f"MAIN PySide6 FATAL: Failed to import a required platformer module: {e}")
    print(f"Current sys.path was: {sys.path}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"MAIN PySide6 FATAL: An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Pyperclip check and clipboard utility ---
PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    info("MAIN PySide6: Pyperclip library found.")
except ImportError:
    warning("MAIN PySide6: Pyperclip library not found. Paste in UI may be limited.")

def get_clipboard_text_qt() -> Optional[str]:
    clipboard = QApplication.clipboard()
    if clipboard: return clipboard.text()
    return None

def set_clipboard_text_qt(text: str):
    clipboard = QApplication.clipboard()
    if clipboard: clipboard.setText(text)

# --- Global App Status ---
class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self): self.app_running = False

APP_STATUS = AppStatus()

# --- Monotonic Timer for Game Logic ---
_app_start_time = time.monotonic()
def get_current_game_ticks(): # In milliseconds
    return int((time.monotonic() - _app_start_time) * 1000)

# --- Input State Management ---
MAX_JOYSTICKS_SUPPORTED = 2 # Example
_qt_keys_pressed: Dict[int, bool] = {}
_joystick_axis_state: List[Dict[int, float]] = [{} for _ in range(MAX_JOYSTICKS_SUPPORTED)]
_joystick_button_state: List[Dict[int, bool]] = [{} for _ in range(MAX_JOYSTICKS_SUPPORTED)]
_joystick_hat_state: List[Dict[int, Tuple[int, int]]] = [{} for _ in range(MAX_JOYSTICKS_SUPPORTED)]

# --- Network Operation Threads ---
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
        # This needs to be called from main thread context. For now, this is a placeholder.
        # The actual input snapshot for P1 (if host) will be done in MainWindow.game_tick
        # This callback is more for client/server logic if it directly needs to poll.
        # In our new structure, server's P1 input is local to main thread. Client's P2 input is local.
        return {} # Return empty, as P1 input for server is handled in main thread.

    def run(self):
        try:
            if self.mode == "host" and self.server_state:
                # run_server_mode is assumed to be a blocking call that runs the server loop.
                # It needs access to main thread's P1 input, which is tricky.
                # For now, it will process P2's input from network, and P1 plays "headless" from server's perspective.
                # Or, P1 input is handled in MainWindow.game_tick and server thread only sends state.
                # The run_server_mode needs to be adapted or simplified if P1 is fully local to MainWindow.
                # Let's assume run_server_mode internally handles P2 and game state updates.
                info("NetworkThread: Starting run_server_mode...")
                run_server_mode(
                    self.server_state, self.game_elements,
                    ui_status_update_callback=self._ui_status_update_callback,
                    get_p1_input_snapshot_callback=self._get_p1_input_snapshot_main_thread_passthrough, # P1 input is local to main window
                    process_qt_events_callback=lambda: QApplication.processEvents() # Allow some event processing
                )
                info("NetworkThread: run_server_mode finished.")
                self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state:
                # run_client_mode is also assumed to be blocking.
                # P2 input for client is local to MainWindow.
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


# --- Main Application Window ---
class MainWindow(QMainWindow):
    # Static member to hold a reference to the current MainWindow instance for callbacks from threads
    _instance: Optional['MainWindow'] = None

    # Signals for network UI updates
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object) # message, data (e.g., (ip,port) or None)

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN (PySide6) - v{C.FPS}") # Example version
        
        # Determine initial size based on screen
        screen_geo = QApplication.primaryScreen().availableGeometry()
        initial_width = max(800, min(1600, int(screen_geo.width() * 0.75)))
        initial_height = max(600, min(900, int(screen_geo.height() * 0.75)))
        self.setMinimumSize(QSize(800,600))
        self.resize(initial_width, initial_height)
        info(f"MAIN PySide6: Initial window size: {initial_width}x{initial_height}")

        self.fonts: Dict[str, QFont] = {
            "small": QFont("Arial", 10),
            "medium": QFont("Arial", 14),
            "large": QFont("Arial", 24, QFont.Weight.Bold),
            "debug": QFont("Monospace", 9)
        }
        
        joystick_handler.init_joysticks()
        game_config.load_config() # Loads device choices and joystick mappings

        self.app_status = APP_STATUS # Use the global instance
        self.game_elements: Dict[str, Any] = {}
        self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None
        self.lan_search_dialog: Optional[QDialog] = None # For LAN server search UI

        # --- Game Timer ---
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.game_tick)
        
        # --- Input State ---
        # Keyboard state is managed by _qt_keys_pressed global for simplicity here
        # Joystick state will be more complex if using 'inputs' library.
        # For now, QGamepad might be simpler if it works well enough on target platforms.
        # If using 'inputs', an InputsControllerThread similar to controller_mapper_gui.py would be needed.
        # Let's assume for now that joystick input will be integrated via QGamepad or a simplified direct poll
        # for the purpose of this main.py refactor.

        # --- UI Setup ---
        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = self._create_main_menu_widget()
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self) # Pass empty game_elements initially
        
        self.stacked_widget.addWidget(self.main_menu_widget)
        self.stacked_widget.addWidget(self.game_scene_widget)
        
        self.setCentralWidget(self.stacked_widget)
        self.show_main_menu_ui()

        # Connect network status signals
        self.network_status_update.connect(self.on_network_status_update)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update)

        self.status_dialog: Optional[QDialog] = None
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None

    def _create_main_menu_widget(self) -> QWidget:
        menu_widget = QWidget()
        layout = QVBoxLayout(menu_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)

        title_label = QLabel("Platformer Adventure LAN")
        title_label.setFont(self.fonts["large"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        buttons = [
            ("Couch Co-op", self.on_start_couch_play),
            ("Host Game", self.on_start_host_game),
            ("Join LAN Game", self.on_start_join_lan),
            ("Join by IP", self.on_start_join_ip),
            # ("Settings", self.on_show_settings), # Settings UI removed from this scope
            ("Quit", self.app_status.quit_app)
        ]

        for text, slot_func in buttons:
            button = QPushButton(text)
            button.setFont(self.fonts["medium"])
            button.setMinimumHeight(40)
            button.clicked.connect(slot_func)
            layout.addWidget(button)
        
        return menu_widget

    def show_main_menu_ui(self):
        self.current_game_mode = None
        if self.game_timer.isActive(): self.game_timer.stop()
        self.stacked_widget.setCurrentWidget(self.main_menu_widget)
        self.setWindowTitle("Platformer Adventure LAN - Main Menu")

    def keyPressEvent(self, event: QKeyEvent):
        if not event.isAutoRepeat():
            _qt_keys_pressed[event.key()] = True
            # Example: global escape to quit (might be better handled by specific widgets)
            if event.key() == Qt.Key.Key_Escape and self.current_game_mode is None: # Only from main menu
                 pass # self.app_status.quit_app() -> Handled by Quit button

    def keyReleaseEvent(self, event: QKeyEvent):
        if not event.isAutoRepeat():
            _qt_keys_pressed[event.key()] = False
    
    # --- Input Snapshot Helper ---
    def _get_input_snapshot(self, player_instance: Player, player_id: int) -> Dict[str, bool]:
        """
        Generates an action event dictionary for the given player based on current input state.
        This is a simplified version. A more robust solution would involve a dedicated InputManager.
        """
        if not player_instance or not player_instance._valid_init: return {}

        # Determine mappings (simplified)
        active_mappings = {}
        if player_id == 1:
            active_mappings = game_config.P1_MAPPINGS if game_config.CURRENT_P1_INPUT_DEVICE == "keyboard_p1" else \
                              (game_config.LOADED_JOYSTICK_MAPPINGS if game_config.CURRENT_P1_INPUT_DEVICE.startswith("joystick") and game_config.LOADED_JOYSTICK_MAPPINGS else game_config.DEFAULT_JOYSTICK_FALLBACK_MAPPINGS)
        elif player_id == 2:
            active_mappings = game_config.P2_MAPPINGS if game_config.CURRENT_P2_INPUT_DEVICE == "keyboard_p2" else \
                              (game_config.LOADED_JOYSTICK_MAPPINGS if game_config.CURRENT_P2_INPUT_DEVICE.startswith("joystick") and game_config.LOADED_JOYSTICK_MAPPINGS else game_config.DEFAULT_JOYSTICK_FALLBACK_MAPPINGS)
        
        # Call process_player_input_logic (from player_input_handler.py)
        # This function needs to be adapted to take PySide key codes and joystick data.
        # For now, we'll pass the global _qt_keys_pressed. Joystick needs proper integration.
        # The `qt_input_events` list is for discrete press/release events, which we are not
        # collecting in such a list in this simplified main.py yet.
        # We are mostly relying on the state of `_qt_keys_pressed`.
        
        # This function is now expected to be part of player.py or player_input_handler.py
        # and take the raw key state.
        # For now, let's assume a placeholder call.
        
        # The process_player_input_logic function in player_input_handler.py
        # is already designed to take key_map and key_states.
        # We need to adapt how _qt_keys_pressed is converted to match its expectations,
        # or adapt process_player_input_logic to understand Qt.Key enums.
        
        # For simplicity, let's assume process_player_input_logic can handle _qt_keys_pressed directly.
        # This implies that game_config key strings are mapped to Qt.Key values or vice-versa.
        # The provided config.py uses string key names ("A", "Return", "Space").
        # A mapping from these strings to Qt.Key enum values is needed.
        
        # This part is complex and depends heavily on how player_input_handler.py is meant to work
        # with PySide6 key events. The original code used pygame.key.get_pressed() and pygame event types.
        
        # Placeholder:
        action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed, # Pass the current Qt key state
            [], # Pass empty list for discrete events for now
            active_mappings,
            self.game_elements.get("platforms_list", [])
        )
        return action_events

    @staticmethod
    def get_p2_input_snapshot_for_client_thread(player_instance: Any) -> Dict[str, Any]:
        # This static method can be called by the client network thread.
        # It needs access to the main window's input state for P2.
        if MainWindow._instance:
            return MainWindow._instance._get_input_snapshot(player_instance, 2)
        return {}

    # --- Game Mode Start Slots ---
    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
        
        # Get current window size for game setup
        current_width, current_height = self.game_scene_widget.width(), self.game_scene_widget.height()
        if current_width <=0 or current_height <=0 : # If widget not shown yet
            current_width, current_height = self.width(), self.height()


        initialized_elements = initialize_game_elements(
            current_width, current_height,
            for_game_mode=mode,
            # Pass existing elements if needed for a soft reset, or None for full reset
            existing_game_elements=None, 
            map_module_name=map_name
        )

        if initialized_elements is None:
            QMessageBox.critical(self, "Error", f"Failed to initialize game elements for {mode}. Check logs.")
            self.show_main_menu_ui()
            return

        self.game_elements.clear()
        self.game_elements.update(initialized_elements)
        self.current_game_mode = mode
        self.setWindowTitle(f"Platformer Adventure LAN - {mode.replace('_',' ').title()}")

        # Configure camera based on new game_elements and current widget size
        camera = self.game_elements.get("camera")
        if camera:
            camera.set_screen_dimensions(self.game_scene_widget.width(), self.game_scene_widget.height())
            if "level_pixel_width" in self.game_elements:
                camera.set_level_dimensions(
                    self.game_elements["level_pixel_width"],
                    self.game_elements["level_min_y_absolute"],
                    self.game_elements["level_max_y_absolute"]
                )
        
        self.game_scene_widget.game_elements = self.game_elements # Update reference in scene widget
        self.stacked_widget.setCurrentWidget(self.game_scene_widget)

        if mode in ["host", "join_lan", "join_ip"]:
            self._start_network_mode(mode, target_ip_port)
        
        self.game_timer.start(1000 // C.FPS)
        info(f"Game mode '{mode}' started.")

    def on_start_couch_play(self):
        map_name = self._select_map_dialog()
        if map_name:
            self._prepare_and_start_game("couch_play", map_name=map_name)

    def on_start_host_game(self):
        map_name = self._select_map_dialog()
        if map_name:
            self._prepare_and_start_game("host", map_name=map_name)

    def on_start_join_lan(self):
        self._show_lan_search_dialog() # This will eventually call _prepare_and_start_game

    def on_start_join_ip(self):
        dialog = IPInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.ip_port_string:
            self._prepare_and_start_game("join_ip", target_ip_port=dialog.ip_port_string)
        else:
            info("Join by IP cancelled.")
            self.show_main_menu_ui()
            
    # def on_show_settings(self):
    #     QMessageBox.information(self, "Settings", "Settings UI not implemented in this version.")

    def _select_map_dialog(self) -> Optional[str]:
        dialog = SelectMapDialog(self.fonts, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_map_name
        return None

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        if self.network_thread and self.network_thread.isRunning():
            warning("NetworkThread already running. Attempting to stop existing one.")
            self.network_thread.quit() # Request quit
            self.network_thread.wait(1000) # Wait a bit

        if mode_name == "host":
            self.server_state = ServerState()
            self.server_state.current_map_name = self.game_elements.get("loaded_map_name")
            self.server_state.app_running = self.app_status.app_running # Link app status
            self.network_thread = NetworkThread(mode="host", game_elements_ref=self.game_elements, server_state_ref=self.server_state, parent=self)
        elif mode_name in ["join_lan", "join_ip"]:
            self.client_state = ClientState()
            self.client_state.app_running = self.app_status.app_running
            self.network_thread = NetworkThread(mode="join", game_elements_ref=self.game_elements, client_state_ref=self.client_state, target_ip_port=target_ip_port, parent=self)
        
        if self.network_thread:
            self.network_thread.status_update_signal.connect(self.on_network_status_update)
            self.network_thread.operation_finished_signal.connect(self.on_network_operation_finished)
            self.network_thread.start()
            self._show_status_dialog("Network Operation", f"Initializing {mode_name} mode...")
        else:
            error(f"Failed to create NetworkThread for mode {mode_name}")
            self.show_main_menu_ui()

    # --- Network UI Callbacks & Dialogs ---
    def _show_status_dialog(self, title: str, initial_message: str):
        if self.status_dialog is None:
            self.status_dialog = QDialog(self)
            self.status_dialog.setWindowTitle(title)
            layout = QVBoxLayout(self.status_dialog)
            self.status_label_in_dialog = QLabel(initial_message)
            self.status_label_in_dialog.setWordWrap(True)
            layout.addWidget(self.status_label_in_dialog)
            self.status_progress_bar_in_dialog = QProgressBar()
            self.status_progress_bar_in_dialog.setRange(0,100)
            self.status_progress_bar_in_dialog.setTextVisible(True)
            layout.addWidget(self.status_progress_bar_in_dialog)
            
            # Cancel button (might not be easy to implement true cancel for network ops)
            # button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
            # button_box.rejected.connect(self._cancel_network_operation) # Placeholder
            # layout.addWidget(button_box)
            self.status_dialog.setMinimumWidth(350)
        else:
            self.status_dialog.setWindowTitle(title)
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(initial_message)
        
        if self.status_progress_bar_in_dialog: self.status_progress_bar_in_dialog.setValue(0); self.status_progress_bar_in_dialog.setVisible(False)
        self.status_dialog.show()
        QApplication.processEvents() # Ensure dialog is shown

    def _update_status_dialog(self, message: str, progress: float = -1.0):
        if self.status_dialog and self.status_dialog.isVisible():
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(message)
            if self.status_progress_bar_in_dialog:
                if progress >= 0:
                    self.status_progress_bar_in_dialog.setValue(int(progress))
                    self.status_progress_bar_in_dialog.setVisible(True)
                else:
                    self.status_progress_bar_in_dialog.setVisible(False)
        QApplication.processEvents()

    def _close_status_dialog(self):
        if self.status_dialog:
            self.status_dialog.hide() # Or accept()/reject() depending on desired behavior

    @Slot(str, str, float)
    def on_network_status_update(self, title: str, message: str, progress: float):
        if not self.status_dialog or not self.status_dialog.isVisible():
            self._show_status_dialog(title, message)
        self._update_status_dialog(message, progress)
        
        # Logic for when game actually starts based on client_logic signals
        if title == "Map Sync" and "ready" in message.lower() and progress >= 100:
             pass # GameSceneWidget drawing will take over
        elif title == "game_starting" or title == "game_active":
             self._close_status_dialog()


    @Slot(str)
    def on_network_operation_finished(self, message: str):
        info(f"Network operation finished: {message}")
        self._close_status_dialog()
        if "error" in message.lower() or "failed" in message.lower():
            QMessageBox.critical(self, "Network Error", f"Network operation ended with error: {message}")
            self.stop_current_game_mode(show_menu=True) # Go back to menu on error
        elif "ended" in message.lower(): # e.g. "host_ended" or "client_ended"
            info(f"Mode {self.current_game_mode} finished normally via network thread signal.")
            # Game timer might still be running if this signal comes from thread exit
            # Stop_current_game_mode will handle timer.
            self.stop_current_game_mode(show_menu=True)


    def _show_lan_search_dialog(self):
        if self.lan_search_dialog is None:
            self.lan_search_dialog = QDialog(self)
            self.lan_search_dialog.setWindowTitle("Searching for LAN Games...")
            layout = QVBoxLayout(self.lan_search_dialog)
            self.lan_search_status_label = QLabel("Searching...")
            layout.addWidget(self.lan_search_status_label)
            self.lan_servers_list_widget = QListWidget()
            layout.addWidget(self.lan_servers_list_widget)
            
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
            button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False) # Enable on selection
            button_box.accepted.connect(self._join_selected_lan_server)
            button_box.rejected.connect(self.lan_search_dialog.reject)
            button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self._start_lan_server_search_thread)
            layout.addWidget(button_box)
            self.lan_search_dialog.rejected.connect(lambda: self.show_main_menu_ui()) # Go to menu on cancel
            self.lan_servers_list_widget.itemDoubleClicked.connect(self._join_selected_lan_server)
        
        self.lan_servers_list_widget.clear()
        self.lan_search_status_label.setText("Searching...")
        self.lan_search_dialog.show()
        self._start_lan_server_search_thread()

    def _start_lan_server_search_thread(self):
        if self.lan_servers_list_widget: self.lan_servers_list_widget.clear()
        if self.lan_search_status_label: self.lan_search_status_label.setText("Searching...")
        if self.lan_search_dialog: self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        # Run find_server_on_lan in a QThread to not block UI
        self.lan_search_worker = QThread() # Create new worker each time
        class LanSearchRunner(QWidget): # QObject for signals
            found_signal = Signal(object)
            def __init__(self, client_state): super().__init__(); self.cs = client_state
            def run_search(self):
                result = find_server_on_lan(self.cs, lambda key, data: self.found_signal.emit((key, data)))
                # This direct call to find_server_on_lan in a QObject method is not ideal for threading
                # It should be: worker moves to thread, then a signal triggers run_search in the worker.
                # For now, simpler:
                if result: self.found_signal.emit(("final_result", result))
                else: self.found_signal.emit(("final_result", None))
        
        temp_client_state_for_search = ClientState() # Temp state for search
        self.lan_search_run_obj = LanSearchRunner(temp_client_state_for_search)
        self.lan_search_run_obj.moveToThread(self.lan_search_worker)
        self.lan_search_worker.started.connect(self.lan_search_run_obj.run_search)
        self.lan_search_run_obj.found_signal.connect(self.on_lan_server_search_status_update)
        self.lan_search_worker.finished.connect(self.lan_search_worker.deleteLater) # Clean up thread
        self.lan_search_worker.finished.connect(self.lan_search_run_obj.deleteLater) # Clean up worker object
        self.lan_search_worker.start()

    @Slot(str, object) # Assuming data is 'object' for flexibility (tuple or str)
    def on_lan_server_search_status_update(self, status_key: str, data: Any):
        if not self.lan_search_dialog or not self.lan_search_dialog.isVisible(): return

        if self.lan_search_status_label: self.lan_search_status_label.setText(f"Status: {status_key} - {str(data)[:50]}")
        
        if status_key == "found" and isinstance(data, tuple) and len(data)==2:
            ip, port = data
            item_text = f"Server at {ip}:{port}"
            self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        elif status_key == "timeout" or status_key == "error" or status_key == "final_result" and data is None:
            if self.lan_servers_list_widget.count() == 0:
                 self.lan_search_status_label.setText(f"Search {status_key}. No servers found.")
                 self.lan_servers_list_widget.addItem("No servers found. Retry or Cancel.")
        elif status_key == "final_result" and data is not None: # If search thread returns final result
             ip, port = data
             item_text = f"Server at {ip}:{port}"
             # Avoid duplicates if already added by 'found' signal
             found_items = self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly)
             if not found_items:
                 self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
             if self.lan_servers_list_widget.count() > 0:
                 self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)


    def _join_selected_lan_server(self):
        if not self.lan_servers_list_widget or not self.lan_search_dialog: return
        selected_items = self.lan_servers_list_widget.selectedItems()
        if selected_items:
            ip_port_str = selected_items[0].data(Qt.ItemDataRole.UserRole) # data is the "ip:port" string
            if ip_port_str:
                self.lan_search_dialog.accept() # Close the search dialog
                self._prepare_and_start_game("join_lan", target_ip_port=ip_port_str)
                return
        QMessageBox.warning(self, "No Selection", "Please select a server from the list.")

    # --- Game Loop and Mode Management ---
    def game_tick(self):
        if not self.app_status.app_running or not self.current_game_mode:
            self.stop_current_game_mode(show_menu=True)
            return

        dt_sec = 1.0 / float(C.FPS)
        current_game_time = get_current_game_ticks()

        # Local P1 Input processing (always if P1 exists)
        p1 = self.game_elements.get("player1")
        p1_input_actions: Dict[str,bool] = {}
        if p1 and p1._valid_init:
            p1_input_actions = self._get_input_snapshot(p1, 1)
            # Check for P1 pause that might affect server/client mode running in this thread
            if p1_input_actions.get("pause") and self.current_game_mode in ["host", "couch_play"]:
                info(f"Main {self.current_game_mode}: P1 Pause. Stopping mode.")
                self.stop_current_game_mode(show_menu=True)
                return


        if self.current_game_mode == "couch_play":
            p2 = self.game_elements.get("player2")
            p2_input_actions_couch: Dict[str,bool] = {}
            if p2 and p2._valid_init:
                 p2_input_actions_couch = self._get_input_snapshot(p2, 2)
            
            # Pass input getting functions that return the already processed dicts
            should_continue = run_couch_play_mode(
                self.game_elements, self.app_status,
                get_p1_input_callback=lambda _p, _plats: p1_input_actions,
                get_p2_input_callback=lambda _p, _plats: p2_input_actions_couch,
                process_qt_events_callback=lambda: QApplication.processEvents(),
                dt_sec_provider=lambda: dt_sec,
                show_status_message_callback=lambda msg: self.statusBar().showMessage(msg, 2000)
            )
            if not should_continue or not self.app_status.app_running:
                self.stop_current_game_mode(show_menu=True)
                return
        
        elif self.current_game_mode == "host":
            # P1 input (local) is already processed via _get_input_snapshot
            # Server thread handles P2 input from network and game state updates.
            # Here, we mainly update P1 locally based on its input.
            # ServerThread is responsible for calling player.update for P2, enemies, etc.
            # This assumes the ServerThread's game loop is what drives the simulation.
            # The main thread's game_tick is mostly for local P1 rendering and input.
            # This model might need adjustment if server's game logic should be in main thread.
            if p1 and p1._valid_init:
                 other_players = [self.game_elements.get("player2")]
                 # P1 update is driven by the server logic, which happens in NetworkThread.
                 # This main game_tick for "host" mode is primarily for rendering its own view.
                 # So, no direct p1.update() here. It's handled by the server logic in the thread.
                 pass # P1's state is authoritative on the server thread.

        elif self.current_game_mode in ["join_lan", "join_ip"]:
            # Client logic: P2 input is local. P1 and game state from server.
            # ClientThread's run_client_mode handles receiving state and P2 input sending.
            # This game_tick is for local rendering of the client's view.
            # Player updates are driven by set_network_game_state.
            pass # Client's state is driven by server updates via NetworkThread.

        # Update game scene widget (common for all modes)
        dl_msg, dl_prog = None, None
        if self.client_state and self.current_game_mode in ["join_lan", "join_ip"]:
            if self.client_state.map_download_status not in ["present", "unknown", "game_active"]:
                dl_msg = f"Map: {self.client_state.server_selected_map_name or '...'} - Status: {self.client_state.map_download_status}"
                dl_prog = self.client_state.map_download_progress
        
        self.game_scene_widget.update_game_state(current_game_time, dl_msg, dl_prog)

    def stop_current_game_mode(self, show_menu: bool = True):
        mode_stopped = self.current_game_mode
        info(f"Stopping game mode: {mode_stopped}")
        self.current_game_mode = None
        if self.game_timer.isActive(): self.game_timer.stop()

        if self.network_thread and self.network_thread.isRunning():
            info("Requesting network thread to stop...")
            if self.server_state: self.server_state.app_running = False
            if self.client_state: self.client_state.app_running = False
            # QThread.quit() is a request. Wait for it to finish.
            self.network_thread.quit() 
            if not self.network_thread.wait(2000): # Wait up to 2 seconds
                warning("Network thread did not stop gracefully. Terminating.")
                self.network_thread.terminate()
                self.network_thread.wait() # Wait for termination
            info("Network thread stopped.")
        self.network_thread = None
        self.server_state = None
        self.client_state = None
        
        self._close_status_dialog()
        if self.lan_search_dialog and self.lan_search_dialog.isVisible():
            self.lan_search_dialog.reject()

        # Clear game elements to free resources
        self.game_elements.clear() 
        self.game_scene_widget.game_elements = self.game_elements # Update scene widget's ref

        if show_menu:
            self.show_main_menu_ui()
        info(f"Game mode '{mode_stopped}' stopped.")

    def closeEvent(self, event: QCloseEvent):
        info("Close event received. Shutting down application.")
        self.app_status.quit_app() # Signal all loops/threads
        self.stop_current_game_mode(show_menu=False) # Clean up current mode
        joystick_handler.quit_joysticks()
        # pygame.scrap is not used in PySide6
        info("MAIN PySide6: Application terminated.")
        event.accept()


# --- Main Execution ---
def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    if not LOGGING_ENABLED:
        # If file logging was disabled or failed, ensure console shows something for critical errors
        # This is a fallback if logger.py itself had issues.
        print("INFO: Main.py started, file logging is OFF or failed in logger.py. Basic console prints active for main.")

    info("MAIN PySide6: Application starting...")
    main_window = MainWindow()
    main_window.show()
    
    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        critical(f"MAIN PySide6 CRITICAL UNHANDLED EXCEPTION: {e}", exc_info=True)
        # Attempt to show a Qt message box for critical errors if possible
        try:
            error_app = QApplication.instance()
            if not error_app: error_app = QApplication(sys.argv) # Should not be needed if main() ran
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred and the application must close.")
            msg_box.setInformativeText(f"{e}\n\nDetails might be in {LOG_FILE_PATH if LOGGING_ENABLED else 'console output'}.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox:
            print(f"FATAL: Could not display Qt error message box: {e_msgbox}")
        traceback.print_exc()
        sys.exit(1)