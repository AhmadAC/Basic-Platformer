# app_core.py
import sys
import os
import traceback
import time
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy, QScrollArea
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QColor, QPalette, QScreen, QKeySequence)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize,QTimer

import pygame

_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
import constants as C
from game_ui import GameSceneWidget, IPInputDialog # SelectMapDialog no longer used here directly
import config as game_config
from player import Player # For type hinting if needed, not strictly necessary for this file structure

# Import the split modules
from app_ui_creator import (
    _create_main_menu_widget, _create_map_select_widget,
    _populate_map_list_for_selection, _create_view_page_with_back_button,
    _ensure_editor_instance, _ensure_controls_mapper_instance, _add_placeholder_to_content_area,
    _show_status_dialog, _update_status_dialog, _close_status_dialog,
    _show_lan_search_dialog, _update_lan_search_list_focus, _update_ip_dialog_button_focus,
    _poll_pygame_joysticks_for_ui_navigation,
    _navigate_current_menu_pygame_joy, _activate_current_menu_selected_button_pygame_joy,
    _update_current_menu_button_focus, _reset_all_prev_press_flags, _activate_ip_dialog_button
)
# Import app_game_modes to call its logic functions
import app_game_modes

from app_input_manager import (
    get_input_snapshot, update_qt_key_press, update_qt_key_release,
    clear_qt_key_events_this_frame
)

from server_logic import ServerState # For NetworkThread type hint
from client_logic import ClientState # For NetworkThread type hint
from couch_play_logic import run_couch_play_mode
from game_state_manager import reset_game_state


PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
except ImportError:
    pass

def get_clipboard_text_qt() -> Optional[str]:
    clipboard = QApplication.clipboard()
    return clipboard.text() if clipboard else None

def set_clipboard_text_qt(text: str):
    clipboard = QApplication.clipboard()
    if clipboard: clipboard.setText(text)

# QT_KEY_MAP is no longer needed here if config.py uses Qt.Key enums directly for keyboard mappings
# and player_input_handler.py compares Qt.Key enums.

class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        app_instance = QApplication.instance()
        if app_instance: debug("APP_STATUS: Requesting QApplication.quit()."); QApplication.quit()

APP_STATUS = AppStatus()

class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float)
    operation_finished_signal = Signal(str)
    client_fully_synced_signal = Signal() # For host to know when client is ready

    def __init__(self, mode: str, game_elements_ref: Dict[str, Any],
                 server_state_ref: Optional[ServerState] = None,
                 client_state_ref: Optional[ClientState] = None,
                 target_ip_port: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.mode = mode
        self.game_elements = game_elements_ref
        self.server_state = server_state_ref
        self.client_state = client_state_ref
        self.target_ip_port = target_ip_port

    def _ui_status_update_callback(self, title: str, message: str, progress: float):
        self.status_update_signal.emit(title, message, progress)
    
    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any, platforms_list: List[Any]) -> Dict[str, Any]:
        # This callback is for the server_logic thread to get P1's input from the main thread.
        if MainWindow._instance:
            return MainWindow._instance.get_p1_input_snapshot_for_server_thread(player_instance, platforms_list)
        return {}
        
    def _get_p2_input_snapshot_main_thread_passthrough(self, player_instance: Any) -> Dict[str, Any]:
        # This callback is for the client_logic thread to get P2's input from the main thread.
        if MainWindow._instance:
            return MainWindow._instance.get_p2_input_snapshot_for_client_thread(player_instance)
        return {}

    def run(self):
        from server_logic import run_server_mode as rs_mode
        from client_logic import run_client_mode as rc_mode
        try:
            main_window_instance = MainWindow._instance
            if self.mode == "host" and self.server_state and main_window_instance:
                info("NetworkThread: Starting run_server_mode...")
                rs_mode(
                    self.server_state,
                    self.game_elements,
                    self._ui_status_update_callback,
                    self._get_p1_input_snapshot_main_thread_passthrough,
                    lambda: QApplication.processEvents(), # Callback to process Qt events
                    lambda: self.client_fully_synced_signal.emit() # Callback for when client is fully synced
                )
                info("NetworkThread: run_server_mode finished."); self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state and main_window_instance:
                info("NetworkThread: Starting run_client_mode...")
                rc_mode(
                    self.client_state,
                    self.game_elements,
                    self._ui_status_update_callback,
                    self.target_ip_port,
                    self._get_p2_input_snapshot_main_thread_passthrough,
                    lambda: QApplication.processEvents() # Callback to process Qt events
                )
                info("NetworkThread: run_client_mode finished."); self.operation_finished_signal.emit("client_ended")
        except Exception as e_thread:
            critical(f"NetworkThread: Exception in {self.mode} mode: {e_thread}", exc_info=True)
            self.operation_finished_signal.emit(f"{self.mode}_error")


class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None # Singleton instance for easy access
    network_status_update = Signal(str, str, float) # title, message, progress
    lan_server_search_status = Signal(str, object) # message, data_tuple or status_string

    actual_editor_module_instance: Optional[Any] = None
    actual_controls_module_instance: Optional[Any] = None

    # Pygame Joystick related attributes for UI navigation
    _pygame_joysticks: List[pygame.joystick.Joystick]
    _pygame_joy_button_prev_state: List[Dict[int, bool]] # List of dicts, one per joystick

    _menu_selected_button_idx: int
    _map_selection_selected_button_idx: int
    _lan_search_list_selected_idx: int
    _ip_dialog_selected_button_idx: int
    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: Dict[Any, bool] # Key can be int (axis_id) or str (joy_idx_axis_id)
    _pygame_joy_axis_was_active_pos: Dict[Any, bool]
    _main_menu_buttons_ref: List[QPushButton]
    _map_selection_buttons_ref: List[QPushButton]
    _ip_dialog_buttons_ref: List[QPushButton]
    _current_active_menu_buttons: List[QPushButton]
    _current_active_menu_selected_idx_ref: str # Name of the attribute holding the current index
    map_select_scroll_area: Optional[QScrollArea] = None
    map_select_title_label: Optional[QLabel] = None
    lan_search_dialog: Optional[QDialog] = None
    lan_search_status_label: Optional[QLabel] = None
    lan_servers_list_widget: Optional[QListWidget] = None
    ip_input_dialog: Optional[IPInputDialog] = None
    current_modal_dialog: Optional[str] = None # Tracks if a modal like "lan_search" or "ip_input" is active

    _prev_menu_confirm_pressed: bool; _prev_menu_cancel_pressed: bool
    _prev_lan_confirm_pressed: bool; _prev_lan_cancel_pressed: bool; _prev_lan_retry_pressed: bool
    _prev_ip_dialog_confirm_pressed: bool; _prev_ip_dialog_cancel_pressed: bool

    NUM_MAP_COLUMNS = 3 # For map selection grid layout
    NetworkThread = NetworkThread # Make the class accessible as an attribute for app_game_modes

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN")

        # Initialize Pygame and Joysticks
        try:
            pygame.init(); pygame.joystick.init()
            self._pygame_joysticks = []
            self._pygame_joy_button_prev_state = []
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                joy.init()
                self._pygame_joysticks.append(joy)
                self._pygame_joy_button_prev_state.append({}) # Initialize prev state dict for this joystick
                info(f"  - Pygame Joystick {i}: {joy.get_name()}")
            if self._pygame_joysticks:
                info(f"MAIN PySide6: Pygame found {len(self._pygame_joysticks)} joysticks.")
            else:
                info("MAIN PySide6: Pygame found no joysticks.")
        except pygame.error as e:
            warning(f"MAIN PySide6: Pygame joystick init error: {e}. Joysticks might not be available.")
            self._pygame_joysticks = []
            self._pygame_joy_button_prev_state = []


        self._menu_selected_button_idx = 0
        self._map_selection_selected_button_idx = 0
        self._lan_search_list_selected_idx = 0
        self._ip_dialog_selected_button_idx = 0
        self._last_pygame_joy_nav_time = 0.0
        self._pygame_joy_axis_was_active_neg = {}
        self._pygame_joy_axis_was_active_pos = {}
        self._main_menu_buttons_ref = []
        self._map_selection_buttons_ref = []
        self._ip_dialog_buttons_ref = [] # For OK/Cancel in IP dialog
        self._current_active_menu_buttons = self._main_menu_buttons_ref # Default to main menu
        self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"
        self._prev_menu_confirm_pressed = False; self._prev_menu_cancel_pressed = False
        self._prev_lan_confirm_pressed = False; self._prev_lan_cancel_pressed = False; self._prev_lan_retry_pressed = False
        self._prev_ip_dialog_confirm_pressed = False; self._prev_ip_dialog_cancel_pressed = False

        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.initial_main_window_width = max(800, min(int(screen_geo.width() * 0.75), 1600))
        self.initial_main_window_height = max(600, min(int(screen_geo.height() * 0.75), 900))
        self.setMinimumSize(QSize(800,600))
        self.resize(self.initial_main_window_width, self.initial_main_window_height)
        info(f"MAIN PySide6: Initial window size: {self.size().width()}x{self.size().height()}")
        self.fonts = {
            "small": QFont("Arial", 10),
            "medium": QFont("Arial", 14),
            "large": QFont("Arial", 24, QFont.Weight.Bold),
            "debug": QFont("Monospace", 9)
        }

        try:
            game_config.load_config() # Load game config (controls, etc.)
        except Exception as e_cfg:
            critical(f"Error during game_config.load_config(): {e_cfg}", exc_info=True)
            self._handle_config_load_failure()

        self.app_status = APP_STATUS # Central app running status
        self.game_elements: Dict[str, Any] = {} # Holds all game objects (players, enemies, map data, etc.)
        self.current_view_name: Optional[str] = None
        self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None # For server or client operations

        # Create UI Widgets (using helpers from app_ui_creator)
        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = _create_main_menu_widget(self)
        self.map_select_widget = _create_map_select_widget(self)
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self) # Pass fonts
        
        self.editor_content_container = QWidget()
        self.editor_content_container.setLayout(QVBoxLayout())
        self.editor_content_container.layout().setContentsMargins(0,0,0,0)
        
        self.controls_content_container = QWidget()
        self.controls_content_container.setLayout(QVBoxLayout())
        self.controls_content_container.layout().setContentsMargins(0,0,0,0)

        self.editor_view_page = _create_view_page_with_back_button(self, "Level Editor", self.editor_content_container, self.on_return_to_menu_from_sub_view)
        self.settings_view_page = _create_view_page_with_back_button(self, "Settings/Controls", self.controls_content_container, self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget)
        self.stacked_widget.addWidget(self.map_select_widget)
        self.stacked_widget.addWidget(self.game_scene_widget)
        self.stacked_widget.addWidget(self.editor_view_page)
        self.stacked_widget.addWidget(self.settings_view_page)
        
        self.setCentralWidget(self.stacked_widget)
        self.show_view("menu") # Start with the main menu

        # Connect signals for network status updates
        self.network_status_update.connect(self.on_network_status_update_slot)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update_slot)
        self.status_dialog: Optional[QDialog] = None # For status messages (connecting, loading, etc.)
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None
        
        # Main game loop timer
        self.game_update_timer = QTimer(self)
        self.game_update_timer.timeout.connect(self.update_game_loop)
        self.game_update_timer.start(1000 // C.FPS) # Target FPS

    def _handle_config_load_failure(self):
        warning("MAIN PySide6: Game config loading encountered an issue. Default keyboard mappings might be used. Check logs from config.py.")
        # Potentially show a non-critical QMessageBox to the user if desired
        # QMessageBox.warning(self, "Configuration Warning", "Could not load saved game configuration. Using defaults.")

    # --- Slot Methods for UI Interactions (delegated to app_game_modes) ---
    def _on_map_selected_for_couch_coop(self, map_name: str):
        info(f"MAIN: Map '{map_name}' selected for Couch Co-op via _on_map_selected.")
        app_game_modes.start_couch_play_logic(self, map_name)

    def _on_map_selected_for_host_game(self, map_name: str):
        info(f"MAIN: Map '{map_name}' selected for Hosting via _on_map_selected.")
        app_game_modes.start_host_game_logic(self, map_name)

    def on_start_couch_play(self):
        app_game_modes.initiate_couch_play_map_selection(self)

    def on_start_host_game(self):
        app_game_modes.initiate_host_game_map_selection(self)

    def on_start_join_lan(self):
        app_game_modes.initiate_join_lan_dialog(self)

    def on_start_join_ip(self):
        app_game_modes.initiate_join_ip_dialog(self)
        
    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        # This is the central function called after mode/map selection
        app_game_modes.prepare_and_start_game_logic(self, mode, map_name, target_ip_port)

    @Slot()
    def on_client_fully_synced_for_host(self):
        app_game_modes.on_client_fully_synced_for_host_logic(self)

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        app_game_modes.start_network_mode_logic(self, mode_name, target_ip_port)

    @Slot(str, str, float)
    def on_network_status_update_slot(self, title: str, message: str, progress: float):
        app_game_modes.on_network_status_update_logic(self, title, message, progress)

    @Slot(str) # This slot receives signals from NetworkThread.operation_finished_signal
    def on_network_operation_finished_slot(self, message: str):
        app_game_modes.on_network_operation_finished_logic(self, message)

    @Slot(object) # Receives from LANServerSearchThread via self.lan_server_search_status Signal
    def on_lan_server_search_status_update_slot(self, data_tuple_or_str: Any):
        app_game_modes.on_lan_server_search_status_update_logic(self, data_tuple_or_str)

    def _start_lan_server_search_thread(self):
         app_game_modes.start_lan_server_search_thread_logic(self)

    def _join_selected_lan_server_from_dialog(self):
        app_game_modes.join_selected_lan_server_from_dialog_logic(self)

    def stop_current_game_mode(self, show_menu: bool = True):
        app_game_modes.stop_current_game_mode_logic(self, show_menu)
    # --- End Slot Methods ---

    def _populate_map_list_for_selection(self, purpose: str):
        _populate_map_list_for_selection(self, purpose) # Helper from app_ui_creator

    def request_close_app(self):
        info("MAIN PySide6: Quit action triggered from UI (request_close_app called).")
        self.close() # Triggers closeEvent

    def on_return_to_menu_from_sub_view(self):
        source_view = self.current_view_name
        info(f"Returning to menu from: {source_view}")
        should_return = True
        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and \
               callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"):
                    should_return = False
            if should_return and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state') and \
               callable(self.actual_editor_module_instance.save_geometry_and_state):
                self.actual_editor_module_instance.save_geometry_and_state()
            if should_return and self.actual_editor_module_instance.parent() is not None:
                # Detach from layout before setting parent to None and potentially deleting
                self.actual_editor_module_instance.setParent(None)
        elif source_view == "settings" and self.actual_controls_module_instance:
            if should_return and self.actual_controls_module_instance.parent() is not None:
                self.actual_controls_module_instance.setParent(None)
        
        if should_return:
            self.show_view("menu")
        else:
            info("Return to menu cancelled by sub-view.")

    def show_view(self, view_name: str):
        info(f"Switching UI view to: {view_name}")
        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode:
            # If leaving game scene for any other view, stop the current game mode
            self.stop_current_game_mode(show_menu=False) # Don't show menu yet, show_view will handle it

        self.current_view_name = view_name
        target_page: Optional[QWidget] = None
        window_title = "Platformer Adventure LAN"
        self.current_modal_dialog = None # Reset modal dialog tracker
        
        if view_name == "menu":
            target_page = self.main_menu_widget
            window_title += " - Main Menu"
            self._current_active_menu_buttons = self._main_menu_buttons_ref
            self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"
            self._menu_selected_button_idx = 0 # Reset selection
        elif view_name == "map_select":
            target_page = self.map_select_widget
            # Title for map_select is typically set by the calling function (on_start_couch_play, etc.)
            # It might be good to have a default here if show_view("map_select") is called directly
            if self.map_select_title_label and not self.map_select_title_label.text().startswith("Select Map"):
                 self.map_select_title_label.setText("Select Map") # Generic default
            window_title += " - Map Selection" # Generic title
            self._current_active_menu_buttons = self._map_selection_buttons_ref
            self._current_active_menu_selected_idx_ref = "_map_selection_selected_button_idx"
            self._map_selection_selected_button_idx = 0 # Reset selection
        elif view_name == "game_scene":
            target_page = self.game_scene_widget
            game_mode_display = self.current_game_mode.replace('_',' ').title() if self.current_game_mode else 'Game'
            window_title += f" - {game_mode_display}"
            self._current_active_menu_buttons = [] # No menu buttons in game scene for joystick nav
        elif view_name == "editor":
            _ensure_editor_instance(self) # Helper from app_ui_creator
            target_page = self.editor_view_page
            window_title += " - Level Editor"
            self._current_active_menu_buttons = []
        elif view_name == "settings":
            _ensure_controls_mapper_instance(self) # Helper from app_ui_creator
            target_page = self.settings_view_page
            window_title += " - Settings/Controls"
            self._current_active_menu_buttons = []
        
        if target_page:
            self.stacked_widget.setCurrentWidget(target_page)
            self.setWindowTitle(window_title)
            if view_name in ["menu", "map_select"]:
                _update_current_menu_button_focus(self)
            
            # Set focus appropriately
            focus_target = target_page # Default to the page itself
            if view_name == "editor" and self.actual_editor_module_instance:
                focus_target = self.actual_editor_module_instance
            elif view_name == "settings" and self.actual_controls_module_instance:
                focus_target = self.actual_controls_module_instance
            elif view_name == "game_scene": # GameSceneWidget itself or its viewport for game input
                focus_target = self.game_scene_widget 
            
            focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to menu.")
            self.stacked_widget.setCurrentWidget(self.main_menu_widget)
            self.setWindowTitle("Platformer Adventure LAN - Main Menu")
            self._current_active_menu_buttons = self._main_menu_buttons_ref
            self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"
            self._menu_selected_button_idx = 0
            _update_current_menu_button_focus(self)
            self.main_menu_widget.setFocus()
        
        clear_qt_key_events_this_frame() # Clear stale key events from previous view

    def keyPressEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key())
        update_qt_key_press(qt_key_enum, event.isAutoRepeat()) # From app_input_manager

        active_ui_element = self.current_modal_dialog if self.current_modal_dialog else self.current_view_name

        # UI Navigation with Keyboard (Arrows/Enter/Space)
        if active_ui_element in ["menu", "map_select"] and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Up: _navigate_current_menu_pygame_joy(self, -1); event.accept(); return
            elif event.key() == Qt.Key.Key_Down: _navigate_current_menu_pygame_joy(self, 1); event.accept(); return
            # Map selection specific left/right for grid navigation
            elif event.key() == Qt.Key.Key_Left and active_ui_element == "map_select": _navigate_current_menu_pygame_joy(self, -2); event.accept(); return
            elif event.key() == Qt.Key.Key_Right and active_ui_element == "map_select": _navigate_current_menu_pygame_joy(self, 2); event.accept(); return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: _activate_current_menu_selected_button_pygame_joy(self); event.accept(); return
        elif active_ui_element == "lan_search" and self.lan_search_dialog and self.lan_servers_list_widget and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Up: self._lan_search_list_selected_idx = max(0, self._lan_search_list_selected_idx - 1); _update_lan_search_list_focus(self); event.accept(); return
            elif event.key() == Qt.Key.Key_Down: self._lan_search_list_selected_idx = min(self.lan_servers_list_widget.count() - 1, self._lan_search_list_selected_idx + 1); _update_lan_search_list_focus(self); event.accept(); return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: self._join_selected_lan_server_from_dialog(); event.accept(); return
        elif active_ui_element == "ip_input" and self.ip_input_dialog and not event.isAutoRepeat():
            if event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right]: # Navigate Ok/Cancel
                self._ip_dialog_selected_button_idx = 1 - self._ip_dialog_selected_button_idx; _update_ip_dialog_button_focus(self); event.accept(); return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: _activate_ip_dialog_button(self); event.accept(); return
        
        # Escape Key Handling
        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat():
            info(f"Escape key pressed. Active UI: '{active_ui_element}', Current View: '{self.current_view_name}', Modal: '{self.current_modal_dialog}'")
            if active_ui_element == "menu":
                self.request_close_app()
            elif active_ui_element == "map_select":
                self.show_view("menu")
            elif active_ui_element == "lan_search" and self.lan_search_dialog:
                self.lan_search_dialog.reject() # This will trigger its rejected signal
            elif active_ui_element == "ip_input" and self.ip_input_dialog:
                self.ip_input_dialog.reject() # Triggers rejected signal
            elif self.current_view_name == "game_scene" and self.current_game_mode:
                info(f"Escape in game mode '{self.current_game_mode}'. Stopping game and returning to menu.")
                self.stop_current_game_mode(show_menu=True)
            elif self.current_view_name in ["editor", "settings"]:
                self.on_return_to_menu_from_sub_view()
            else: # Fallback if a view doesn't explicitly handle Escape
                info(f"Escape pressed in unhandled view '{self.current_view_name}'. Returning to menu.")
                self.show_view("menu")
            event.accept(); return

        if not event.isAccepted():
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key())
        update_qt_key_release(qt_key_enum, event.isAutoRepeat()) # From app_input_manager
        if not event.isAccepted():
            super().keyReleaseEvent(event)

    def get_p1_input_snapshot_for_server_thread(self, player_instance: Any, platforms_list: List[Any]) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 1, self._pygame_joysticks, self._pygame_joy_button_prev_state, self.game_elements)

    def get_p2_input_snapshot_for_client_thread(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 2, self._pygame_joysticks, self._pygame_joy_button_prev_state, self.game_elements)

    def update_game_loop(self):
        # Poll Pygame joysticks for UI navigation (if any are connected)
        _poll_pygame_joysticks_for_ui_navigation(self) # Helper from app_ui_creator

        # Pump Pygame events if any joystick is configured for game input
        # This ensures joystick state (axes, buttons) is up-to-date for get_input_snapshot
        if self.current_game_mode and \
           ( (game_config.CURRENT_P1_INPUT_DEVICE and "joystick_pygame_" in game_config.CURRENT_P1_INPUT_DEVICE) or \
             (game_config.CURRENT_P2_INPUT_DEVICE and "joystick_pygame_" in game_config.CURRENT_P2_INPUT_DEVICE) ):
            pygame.event.pump() # Get latest Pygame joystick states

        # --- Couch Play Game Loop Logic ---
        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            dt_sec = 1.0 / C.FPS # Fixed delta time for couch play
            
            # The show_status_message_callback lambda is a bit of a hack if it's for general game messages.
            # GameSceneWidget.update_game_state's download_msg is specific.
            # If couch_play_logic needs to show "Game Over", it should ideally do so via a more generic
            # UI update mechanism or a signal that GameSceneWidget can interpret.
            # For now, it's passed as is.
            continue_game = run_couch_play_mode(
                self.game_elements, self.app_status,
                self.get_p1_input_snapshot_for_server_thread,
                self.get_p2_input_snapshot_for_client_thread,
                lambda: QApplication.processEvents(),
                lambda: dt_sec, # Pass dt_sec provider
                lambda msg: self.game_scene_widget.update_game_state(0, download_msg=msg) # Status msg callback
            )
            if not continue_game: # run_couch_play_mode returned False (e.g., game over, pause)
                self.stop_current_game_mode(show_menu=True)
        
        # --- Host Waiting Game Loop Logic (Simplified local updates for P1 while waiting for client) ---
        elif self.current_game_mode == "host_waiting" and self.app_status.app_running:
            dt_sec = 1.0 / C.FPS
            p1 = self.game_elements.get("player1")
            if p1:
                # Get P1 input for local simulation (and for when client connects)
                p1_actions = self.get_p1_input_snapshot_for_server_thread(p1, self.game_elements.get("platforms_list", []))
                
                if p1_actions.get("pause"): # Host pauses while waiting
                    self.stop_current_game_mode(show_menu=True)
                    return # Exit update_game_loop for this frame
                if p1_actions.get("reset"): # Host resets local game state
                    reset_game_state(self.game_elements)

                # Update P1 locally
                p1.update(dt_sec, self.game_elements.get("platforms_list", []), 
                          self.game_elements.get("ladders_list", []), 
                          self.game_elements.get("hazards_list", []),
                          [], # No other players locally for collision
                          self.game_elements.get("enemy_list", []))
                
                # Update enemies locally (they don't interact with P2 yet)
                active_players_for_ai = [p1] if p1.alive() else []
                for enemy in list(self.game_elements.get("enemy_list",[])):
                    enemy.update(dt_sec, active_players_for_ai,
                                 self.game_elements.get("platforms_list",[]),
                                 self.game_elements.get("hazards_list",[]),
                                 self.game_elements.get("enemy_list",[]))

                # Update projectiles locally
                projectiles_current_list = self.game_elements.get("projectiles_list", [])
                for proj_obj in list(projectiles_current_list):
                    if hasattr(proj_obj, 'update'):
                        # Targets for projectiles in host_waiting: only P1 and enemies
                        proj_targets = ([p1] if p1.alive() else []) + [e for e in self.game_elements.get("enemy_list",[]) if e.alive()]
                        proj_obj.update(dt_sec, self.game_elements.get("platforms_list",[]), proj_targets)
                    if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                        if proj_obj in projectiles_current_list:
                            projectiles_current_list.remove(proj_obj)
                
                # Update camera for P1
                camera = self.game_elements.get("camera")
                if camera and p1.alive():
                    camera.update(p1)
        
        # --- Client Active Game Loop Logic (Handled by NetworkThread and GameSceneWidget updates) ---
        # No direct game logic for "join_active" or "host_active" in this QTimer loop.
        # Those are driven by network updates received in their respective threads (client_logic, server_logic)
        # which then update game_elements. GameSceneWidget.update_game_state() handles rendering.

        # Update the game scene widget if it's the current view
        if self.current_view_name == "game_scene":
            self.game_scene_widget.update_game_state(0) # Pass dummy time, real timing handled by QTimer

        clear_qt_key_events_this_frame() # Clear input manager's frame events

    def closeEvent(self, event: QCloseEvent):
        info("MAIN PySide6: Close event received. Initiating shutdown sequence.")
        
        # Handle Editor unsaved changes and save geometry
        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow): # Editor is a QMainWindow
                if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and \
                   callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                    if not self.actual_editor_module_instance.confirm_unsaved_changes("exit the application"):
                        can_close_editor = False
            
            if not can_close_editor:
                info("Editor prevented application close.")
                event.ignore()
                return
            else:
                if hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'):
                    self.actual_editor_module_instance.save_geometry_and_state()
                # Important: Detach before deleteLater if it's part of a layout
                if self.actual_editor_module_instance.parent() is not None:
                    self.actual_editor_module_instance.setParent(None)
                self.actual_editor_module_instance.deleteLater()
                self.actual_editor_module_instance = None
                info("Editor instance scheduled for deletion.")

        # Handle Controls Mapper save
        if self.actual_controls_module_instance:
             if hasattr(self.actual_controls_module_instance, 'save_mappings'):
                 self.actual_controls_module_instance.save_mappings()
             if self.actual_controls_module_instance.parent() is not None:
                self.actual_controls_module_instance.setParent(None)
             self.actual_controls_module_instance.deleteLater()
             self.actual_controls_module_instance = None
             info("Controls mapper instance scheduled for deletion.")

        # Stop any active game mode and network threads
        self.app_status.quit_app() # Signals threads to stop
        app_game_modes.stop_current_game_mode_logic(self, show_menu=False) # Call the logic function

        # Quit Pygame
        pygame.joystick.quit()
        pygame.quit()
        info("MAIN PySide6: Pygame quit.")
        
        info("MAIN PySide6: Application shutdown sequence complete. Accepting close event.")
        super().closeEvent(event)


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    info("MAIN PySide6: Application starting...")
    main_window = MainWindow()
    main_window.showMaximized() # Or main_window.show() for default size

    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")

    # Ensure app_running is false if not already (e.g., if loop exited for other reasons)
    if APP_STATUS.app_running:
        APP_STATUS.app_running = False

    info("MAIN PySide6: Application fully terminated.")
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e_main_outer:
        # Log critical error if logger is available and project root can be determined
        if 'critical' in globals() and callable(critical) and _project_root:
            critical(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True)
        else: # Fallback to print if logger isn't set up or _project_root is missing
            print(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}")
            traceback.print_exc()
        
        # Attempt to show a Qt QMessageBox for critical errors
        try:
            error_app = QApplication.instance() # Check if an app instance exists
            if error_app is None: # If not, create one to show the dialog
                error_app = QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")
            
            log_path_info_str = ""
            # Check if logging was enabled and LOG_FILE_PATH is defined and exists
            if LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH and os.path.exists(LOG_FILE_PATH):
                log_path_info_str = f"Please check the log file for details:\n{LOG_FILE_PATH}"
            elif LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH:
                log_path_info_str = f"Log file configured at: {LOG_FILE_PATH} (may not exist or have details if error was early)."
            else:
                log_path_info_str = "Logging to file is disabled or path not set. Check console output."

            msg_box.setInformativeText(f"Error: {str(e_main_outer)[:1000]}\n\n{log_path_info_str}")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox:
            # If even the Qt message box fails, print to console
            print(f"FATAL: Could not display Qt error dialog: {e_msgbox}")
            traceback.print_exc()
            
        sys.exit(1) # Exit with error code