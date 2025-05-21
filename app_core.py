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

import pygame # For joystick interaction

# --- Project Root Setup ---
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# --- Local Imports ---
from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
from utils import PrintLimiter
import constants as C
from game_ui import GameSceneWidget, IPInputDialog
import config as game_config # config.py handles global Pygame init
from player import Player # Keep for type hints if needed

from app_ui_creator import (
    _create_main_menu_widget, _create_map_select_widget,
    _populate_map_list_for_selection, _create_view_page_with_back_button,
    _ensure_editor_instance, _ensure_controls_settings_instance,
    _add_placeholder_to_content_area,
    _show_status_dialog, _update_status_dialog, _close_status_dialog,
    _show_lan_search_dialog, _update_lan_search_list_focus, _update_ip_dialog_button_focus,
    _poll_pygame_joysticks_for_ui_navigation,
    _navigate_current_menu_pygame_joy, _activate_current_menu_selected_button_pygame_joy,
    _update_current_menu_button_focus, _reset_all_prev_press_flags, _activate_ip_dialog_button
)
import app_game_modes

from app_input_manager import (
    get_input_snapshot, update_qt_key_press, update_qt_key_release,
    clear_qt_key_events_this_frame
)

from server_logic import ServerState
from client_logic import ClientState
from couch_play_logic import run_couch_play_mode
from game_state_manager import reset_game_state

# --- Pyperclip (Optional) ---
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

# --- App Status ---
class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        app_instance = QApplication.instance()
        if app_instance: debug("APP_STATUS: Requesting QApplication.quit()."); QApplication.quit()

APP_STATUS = AppStatus()

# --- Network Thread ---
class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float)
    operation_finished_signal = Signal(str)
    client_fully_synced_signal = Signal()

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
    
    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any) -> Dict[str, Any]:
        if MainWindow._instance:
            return MainWindow._instance.get_p1_input_snapshot_for_server_thread(player_instance)
        return {}
        
    def _get_p2_input_snapshot_main_thread_passthrough(self, player_instance: Any) -> Dict[str, Any]:
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
                    self.server_state, self.game_elements, self._ui_status_update_callback,
                    self._get_p1_input_snapshot_main_thread_passthrough,
                    lambda: QApplication.processEvents(), lambda: self.client_fully_synced_signal.emit()
                )
                info("NetworkThread: run_server_mode finished."); self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state and main_window_instance:
                info("NetworkThread: Starting run_client_mode...")
                rc_mode(
                    self.client_state, self.game_elements, self._ui_status_update_callback,
                    self.target_ip_port, self._get_p2_input_snapshot_main_thread_passthrough,
                    lambda: QApplication.processEvents()
                )
                info("NetworkThread: run_client_mode finished."); self.operation_finished_signal.emit("client_ended")
        except Exception as e_thread:
            critical(f"NetworkThread: Exception in {self.mode} mode: {e_thread}", exc_info=True)
            self.operation_finished_signal.emit(f"{self.mode}_error")

# --- Main Window ---
class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object)

    actual_editor_module_instance: Optional[Any] = None
    actual_controls_settings_instance: Optional[Any] = None

    _pygame_joysticks: List[pygame.joystick.Joystick]
    _pygame_joy_button_prev_state: List[Dict[int, bool]]

    _ui_nav_focus_controller_index: Optional[int] = None
    _p1_ui_focus_color_str: str = "yellow"
    _p2_ui_focus_color_str: str = "red"

    _menu_selected_button_idx: int
    _map_selection_selected_button_idx: int
    _lan_search_list_selected_idx: int
    _ip_dialog_selected_button_idx: int
    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: Dict[Any, bool]
    _pygame_joy_axis_was_active_pos: Dict[Any, bool]
    _main_menu_buttons_ref: List[QPushButton]
    _map_selection_buttons_ref: List[QPushButton]
    _ip_dialog_buttons_ref: List[QPushButton]
    _current_active_menu_buttons: List[QPushButton]
    _current_active_menu_selected_idx_ref: str
    map_select_scroll_area: Optional[QScrollArea] = None
    map_select_title_label: Optional[QLabel] = None
    lan_search_dialog: Optional[QDialog] = None
    lan_search_status_label: Optional[QLabel] = None
    lan_servers_list_widget: Optional[QListWidget] = None
    ip_input_dialog: Optional[IPInputDialog] = None
    current_modal_dialog: Optional[str] = None

    NUM_MAP_COLUMNS = 3
    NetworkThread = NetworkThread
    render_print_limiter = PrintLimiter(default_limit=1, default_period=3.0)

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN")

        # Ensure config.py has initialized Pygame and Joystick system
        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            warning("AppCore Init: Pygame or Joystick system not globally initialized by config.py. Attempting init.")
            game_config.init_pygame_and_joystick_globally() # Ensure it's called
            if not game_config._joystick_initialized_globally:
                critical("AppCore Init: FAILED to initialize Pygame Joystick system globally. Controller input will NOT work.")

        # Populate AppCore's joystick list from Pygame (which should be ready via config.py)
        self._pygame_joysticks = []
        self._pygame_joy_button_prev_state = []
        if game_config._joystick_initialized_globally:
            try:
                num_joys_detected = pygame.joystick.get_count()
                for i in range(num_joys_detected):
                    joy = pygame.joystick.Joystick(i)
                    joy.init() # Make sure this specific Joystick object is initialized
                    self._pygame_joysticks.append(joy)
                    self._pygame_joy_button_prev_state.append({})
                    info(f"AppCore Pygame Joystick {i} Acquired: {joy.get_name()} (Instance ID: {joy.get_instance_id()})")
                if self._pygame_joysticks: info(f"AppCore: Acquired {len(self._pygame_joysticks)} Pygame joysticks.")
                else: info("AppCore: No Pygame joysticks found/acquired.")
            except pygame.error as e_joy_acquire:
                warning(f"AppCore: Error acquiring Pygame joystick objects: {e_joy_acquire}")
        else:
            info("AppCore: Pygame joystick system not initialized globally. No joysticks available.")

        # UI navigation state
        self._menu_selected_button_idx = 0; self._map_selection_selected_button_idx = 0
        self._lan_search_list_selected_idx = -1; self._ip_dialog_selected_button_idx = 0
        self._last_pygame_joy_nav_time = 0.0
        self._pygame_joy_axis_was_active_neg = {}; self._pygame_joy_axis_was_active_pos = {}
        self._main_menu_buttons_ref = []; self._map_selection_buttons_ref = []; self._ip_dialog_buttons_ref = []
        self._current_active_menu_buttons = self._main_menu_buttons_ref
        self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"
        _reset_all_prev_press_flags(self)

        # Window and Font Setup
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.initial_main_window_width = max(800, min(int(screen_geo.width() * 0.75), 1600))
        self.initial_main_window_height = max(600, min(int(screen_geo.height() * 0.75), 900))
        self.setMinimumSize(QSize(800,600)); self.resize(self.initial_main_window_width, self.initial_main_window_height)
        self.fonts = {"small": QFont("Arial", 10), "medium": QFont("Arial", 14),
                      "large": QFont("Arial", 24, QFont.Weight.Bold), "debug": QFont("Monospace", 9)}

        # Load Game Configuration (device assignments, mappings, etc.)
        try:
            game_config.load_config()
        except Exception as e_cfg:
            critical(f"Error during game_config.load_config(): {e_cfg}", exc_info=True)
            self._handle_config_load_failure()

        # Application State and Game Logic Holders
        self.app_status = APP_STATUS; self.game_elements: Dict[str, Any] = {}
        self.current_view_name: Optional[str] = None; self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None; self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None

        # UI Widgets
        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = _create_main_menu_widget(self)
        self.map_select_widget = _create_map_select_widget(self)
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)
        self.editor_content_container = QWidget(); self.editor_content_container.setLayout(QVBoxLayout())
        self.editor_content_container.layout().setContentsMargins(0,0,0,0)
        self.settings_content_container = QWidget(); self.settings_content_container.setLayout(QVBoxLayout())
        self.settings_content_container.layout().setContentsMargins(0,0,0,0)
        self.editor_view_page = _create_view_page_with_back_button(self, "Level Editor", self.editor_content_container, self.on_return_to_menu_from_sub_view)
        self.settings_view_page = _create_view_page_with_back_button(self, "Settings & Controls", self.settings_content_container, self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget); self.stacked_widget.addWidget(self.map_select_widget)
        self.stacked_widget.addWidget(self.game_scene_widget); self.stacked_widget.addWidget(self.editor_view_page)
        self.stacked_widget.addWidget(self.settings_view_page)
        self.setCentralWidget(self.stacked_widget); self.show_view("menu")

        # Signals and Dialogs
        self.network_status_update.connect(self.on_network_status_update_slot)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update_slot)
        self.status_dialog: Optional[QDialog] = None
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None
        
        # Game Loop Timer
        self.game_update_timer = QTimer(self)
        self.game_update_timer.timeout.connect(self.update_game_loop)
        self.game_update_timer.start(1000 // C.FPS)
        info("MainWindow initialization complete.")

    def _handle_config_load_failure(self):
        warning("MAIN PySide6: Game config loading encountered an issue. Default mappings and device choices will be used.")
        game_config.CURRENT_P1_INPUT_DEVICE = game_config.DEFAULT_P1_INPUT_DEVICE
        game_config.P1_KEYBOARD_ENABLED = game_config.DEFAULT_P1_KEYBOARD_ENABLED
        game_config.P1_CONTROLLER_ENABLED = game_config.DEFAULT_P1_CONTROLLER_ENABLED
        game_config.CURRENT_P2_INPUT_DEVICE = game_config.DEFAULT_P2_INPUT_DEVICE
        game_config.P2_KEYBOARD_ENABLED = game_config.DEFAULT_P2_KEYBOARD_ENABLED
        game_config.P2_CONTROLLER_ENABLED = game_config.DEFAULT_P2_CONTROLLER_ENABLED
        game_config.update_player_mappings_from_config() # Apply defaults
        info("MAIN PySide6: Fallback to default config settings due to load failure.")

    def _on_map_selected_for_couch_coop(self, map_name: str): app_game_modes.start_couch_play_logic(self, map_name)
    def _on_map_selected_for_host_game(self, map_name: str): app_game_modes.start_host_game_logic(self, map_name)
    def on_start_couch_play(self): app_game_modes.initiate_couch_play_map_selection(self)
    def on_start_host_game(self): app_game_modes.initiate_host_game_map_selection(self)
    def on_start_join_lan(self): app_game_modes.initiate_join_lan_dialog(self)
    def on_start_join_ip(self): app_game_modes.initiate_join_ip_dialog(self)

    @Slot()
    def on_client_fully_synced_for_host(self): app_game_modes.on_client_fully_synced_for_host_logic(self)

    @Slot(str, str, float)
    def on_network_status_update_slot(self, title: str, message: str, progress: float): app_game_modes.on_network_status_update_logic(self, title, message, progress)
    
    @Slot(str)
    def on_network_operation_finished_slot(self, message: str): app_game_modes.on_network_operation_finished_logic(self, message)
    
    @Slot(str, object)
    def on_lan_server_search_status_update_slot(self, status_key_str_or_tuple: Any, data_obj: Optional[object] = None):
        if isinstance(status_key_str_or_tuple, tuple) and len(status_key_str_or_tuple) == 2:
            actual_status_key, actual_data = status_key_str_or_tuple
            app_game_modes.on_lan_server_search_status_update_logic(self, (actual_status_key, actual_data))
        elif isinstance(status_key_str_or_tuple, str) and data_obj is not None:
            app_game_modes.on_lan_server_search_status_update_logic(self, (status_key_str_or_tuple, data_obj))
        else:
            warning(f"AppCore: Received LAN search update in unexpected format: {status_key_str_or_tuple}, {data_obj}")

    def _start_lan_server_search_thread(self): app_game_modes.start_lan_server_search_thread_logic(self)
    def _join_selected_lan_server_from_dialog(self): app_game_modes.join_selected_lan_server_from_dialog_logic(self)
    def stop_current_game_mode(self, show_menu: bool = True): app_game_modes.stop_current_game_mode_logic(self, show_menu)
    def _populate_map_list_for_selection(self, purpose: str): _populate_map_list_for_selection(self, purpose)
    def request_close_app(self): self.close()

    def on_return_to_menu_from_sub_view(self):
        source_view = self.current_view_name; info(f"Returning to menu from: {source_view}"); should_return = True
        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"): should_return = False
            if should_return and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'): self.actual_editor_module_instance.save_geometry_and_state()
            if should_return and self.actual_editor_module_instance.parent() is not None: self.actual_editor_module_instance.setParent(None)
        elif source_view == "settings" and self.actual_controls_settings_instance:
            if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and callable(self.actual_controls_settings_instance.save_all_settings):
                self.actual_controls_settings_instance.save_all_settings()
                game_config.load_config()
                game_config.update_player_mappings_from_config()
                info("AppCore: Settings saved and reloaded from Controls/Settings view.")
            if should_return and self.actual_controls_settings_instance.parent() is not None: self.actual_controls_settings_instance.setParent(None)
        if should_return: self.show_view("menu")
        else: info("Return to menu cancelled by sub-view.")

    def show_view(self, view_name: str):
        info(f"Switching UI view to: {view_name}")
        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode:
            self.stop_current_game_mode(show_menu=False)
        self.current_view_name = view_name; target_page: Optional[QWidget] = None
        window_title = "Platformer Adventure LAN"; self.current_modal_dialog = None
        if view_name in ["menu", "map_select"]: self._ui_nav_focus_controller_index = None
        
        view_map = {
            "menu": (self.main_menu_widget, " - Main Menu", self._main_menu_buttons_ref, "_menu_selected_button_idx", 0),
            "map_select": (self.map_select_widget, " - Map Selection", self._map_selection_buttons_ref, "_map_selection_selected_button_idx", 0),
            "game_scene": (self.game_scene_widget, f" - {self.current_game_mode.replace('_',' ').title() if self.current_game_mode else 'Game'}", [], "", 0),
            "editor": (self.editor_view_page, " - Level Editor", [], "", 0),
            "settings": (self.settings_view_page, " - Settings & Controls", [], "", 0)
        }
        if view_name in view_map:
            target_page, title_suffix, buttons_ref, idx_attr, default_idx = view_map[view_name]
            window_title += title_suffix
            self._current_active_menu_buttons = buttons_ref
            if idx_attr: self._current_active_menu_selected_idx_ref = idx_attr; setattr(self, idx_attr, default_idx)
            if view_name == "editor": _ensure_editor_instance(self)
            elif view_name == "settings": _ensure_controls_settings_instance(self)
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to menu.")
            target_page = self.main_menu_widget; window_title += " - Main Menu"
            self._current_active_menu_buttons = self._main_menu_buttons_ref
            self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"; self._menu_selected_button_idx = 0

        if target_page:
            self.stacked_widget.setCurrentWidget(target_page); self.setWindowTitle(window_title)
            if view_name in ["menu", "map_select"]: _update_current_menu_button_focus(self)
            focus_target = target_page
            if view_name == "editor" and self.actual_editor_module_instance: focus_target = self.actual_editor_module_instance
            elif view_name == "settings" and self.actual_controls_settings_instance: focus_target = self.actual_controls_settings_instance
            elif view_name == "game_scene": focus_target = self.game_scene_widget
            focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        clear_qt_key_events_this_frame()

    def keyPressEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key()); update_qt_key_press(qt_key_enum, event.isAutoRepeat())
        active_ui_element = self.current_modal_dialog if self.current_modal_dialog else self.current_view_name
        navigated_by_keyboard_this_event = False
        if active_ui_element in ["menu", "map_select"] and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Up: _navigate_current_menu_pygame_joy(self, -1); navigated_by_keyboard_this_event = True
            elif event.key() == Qt.Key.Key_Down: _navigate_current_menu_pygame_joy(self, 1); navigated_by_keyboard_this_event = True
            elif event.key() == Qt.Key.Key_Left and active_ui_element == "map_select": _navigate_current_menu_pygame_joy(self, -self.NUM_MAP_COLUMNS); navigated_by_keyboard_this_event = True
            elif event.key() == Qt.Key.Key_Right and active_ui_element == "map_select": _navigate_current_menu_pygame_joy(self, self.NUM_MAP_COLUMNS); navigated_by_keyboard_this_event = True
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: _activate_current_menu_selected_button_pygame_joy(self); navigated_by_keyboard_this_event = True
        elif active_ui_element == "lan_search" and self.lan_search_dialog and self.lan_servers_list_widget and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Up: self._lan_search_list_selected_idx = max(0, self._lan_search_list_selected_idx - 1); _update_lan_search_list_focus(self); navigated_by_keyboard_this_event = True
            elif event.key() == Qt.Key.Key_Down: self._lan_search_list_selected_idx = min(self.lan_servers_list_widget.count() - 1, self._lan_search_list_selected_idx + 1); _update_lan_search_list_focus(self); navigated_by_keyboard_this_event = True
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: self._join_selected_lan_server_from_dialog(); navigated_by_keyboard_this_event = True
        elif active_ui_element == "ip_input" and self.ip_input_dialog and not event.isAutoRepeat():
            if event.key() not in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab]:
                if self.ip_input_dialog.line_edit.hasFocus(): super().keyPressEvent(event); return
            if event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Tab, Qt.Key.Key_Backtab]:
                self._ip_dialog_selected_button_idx = 1 - self._ip_dialog_selected_button_idx; _update_ip_dialog_button_focus(self); navigated_by_keyboard_this_event = True
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                _activate_ip_dialog_button(self); navigated_by_keyboard_this_event = True
        if navigated_by_keyboard_this_event:
            self._ui_nav_focus_controller_index = None
            if active_ui_element in ["menu", "map_select"]: _update_current_menu_button_focus(self)
            event.accept(); return
        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat():
            if active_ui_element == "menu": self.request_close_app()
            elif active_ui_element == "map_select": self.show_view("menu")
            elif active_ui_element == "lan_search" and self.lan_search_dialog: self.lan_search_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
            elif active_ui_element == "ip_input" and self.ip_input_dialog: self.ip_input_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
            elif self.current_view_name == "game_scene" and self.current_game_mode: self.stop_current_game_mode(show_menu=True)
            elif self.current_view_name in ["editor", "settings"]: self.on_return_to_menu_from_sub_view()
            else: self.show_view("menu")
            event.accept(); return
        if not event.isAccepted(): super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key()); update_qt_key_release(qt_key_enum, event.isAutoRepeat())
        if not event.isAccepted(): super().keyReleaseEvent(event)

    def get_p1_input_snapshot_for_server_thread(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 1, self._pygame_joysticks, self._pygame_joy_button_prev_state, self.game_elements)

    def get_p2_input_snapshot_for_client_thread(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 2, self._pygame_joysticks, self._pygame_joy_button_prev_state, self.game_elements)

    def update_game_loop(self):
        _poll_pygame_joysticks_for_ui_navigation(self)
        
        p1_uses_pygame_joy = game_config.P1_CONTROLLER_ENABLED and game_config.CURRENT_P1_INPUT_DEVICE.startswith("joystick_pygame_")
        p2_uses_pygame_joy = game_config.P2_CONTROLLER_ENABLED and game_config.CURRENT_P2_INPUT_DEVICE.startswith("joystick_pygame_")
        if self.current_game_mode and (p1_uses_pygame_joy or p2_uses_pygame_joy):
            if pygame.joystick.get_init(): pygame.event.pump() # Check init before pump
            else: warning("AppCore GameLoop: Pygame joystick not init, cannot pump events for gameplay.")

        game_is_ready = self.game_elements.get('game_ready_for_logic', False)
        init_in_progress = self.game_elements.get('initialization_in_progress', True)

        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            if game_is_ready and not init_in_progress:
                dt_sec = 1.0 / C.FPS
                continue_game = run_couch_play_mode(
                    self.game_elements, self.app_status,
                    self.get_p1_input_snapshot_for_server_thread, self.get_p2_input_snapshot_for_client_thread,
                    lambda: QApplication.processEvents(), lambda: dt_sec,
                    lambda msg: self.game_scene_widget.update_game_state(0, download_msg=msg)
                )
                if not continue_game: self.stop_current_game_mode(show_menu=True)
        # ... (rest of game mode logic as before, it was already quite clean) ...
        elif self.current_game_mode == "host_active" and self.app_status.app_running and self.server_state and self.server_state.client_ready:
             if game_is_ready and not init_in_progress: pass
        elif self.current_game_mode == "host_waiting" and self.app_status.app_running and self.server_state:
            if game_is_ready and not init_in_progress:
                dt_sec = 1.0 / C.FPS; p1 = self.game_elements.get("player1")
                if p1:
                    p1_actions = self.get_p1_input_snapshot_for_server_thread(p1)
                    if p1_actions.get("pause"): self.stop_current_game_mode(show_menu=True); return
                    if p1_actions.get("reset"): reset_game_state(self.game_elements)
                    p1.update(dt_sec, self.game_elements.get("platforms_list", []), self.game_elements.get("ladders_list", []), self.game_elements.get("hazards_list", []), [], self.game_elements.get("enemy_list", []))
                    active_players_for_ai = [p1] if p1 and p1.alive() else []
                    for enemy in list(self.game_elements.get("enemy_list",[])):
                        if hasattr(enemy, 'update'): enemy.update(dt_sec, active_players_for_ai, self.game_elements.get("platforms_list",[]), self.game_elements.get("hazards_list",[]), self.game_elements.get("enemy_list",[]))
                    projectiles_current_list = self.game_elements.get("projectiles_list", [])
                    for proj_obj in list(projectiles_current_list):
                        if hasattr(proj_obj, 'update'):
                            proj_targets = ([p1] if p1 and p1.alive() else []) + [e for e in self.game_elements.get("enemy_list",[]) if e.alive()]
                            proj_obj.update(dt_sec, self.game_elements.get("platforms_list",[]), proj_targets)
                        if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                            if proj_obj in projectiles_current_list: projectiles_current_list.remove(proj_obj)
                    camera = self.game_elements.get("camera")
                    if camera and p1 and p1.alive(): camera.update(p1)
        elif self.current_game_mode == "join_active" and self.app_status.app_running and self.client_state and self.client_state.map_download_status == "present": pass
        
        if self.current_view_name == "game_scene":
            if self.game_elements.get("platforms_list") is not None or self.game_elements.get("level_data") is not None:
                 self.game_scene_widget.update_game_state(0)
        clear_qt_key_events_this_frame()

    def closeEvent(self, event: QCloseEvent):
        info("MAIN PySide6: Close event. Shutting down.")
        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow):
                if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                    if not self.actual_editor_module_instance.confirm_unsaved_changes("exit"): can_close_editor = False
            if not can_close_editor: event.ignore(); return
            else:
                if hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'): self.actual_editor_module_instance.save_geometry_and_state()
                if self.actual_editor_module_instance.parent() is not None: self.actual_editor_module_instance.setParent(None)
                self.actual_editor_module_instance.deleteLater(); self.actual_editor_module_instance = None
        if self.actual_controls_settings_instance:
             if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and callable(self.actual_controls_settings_instance.save_all_settings):
                 self.actual_controls_settings_instance.save_all_settings()
             if self.actual_controls_settings_instance.parent() is not None: self.actual_controls_settings_instance.setParent(None)
             self.actual_controls_settings_instance.deleteLater(); self.actual_controls_settings_instance = None
        self.app_status.quit_app()
        app_game_modes.stop_current_game_mode_logic(self, show_menu=False)
        if game_config._joystick_initialized_globally: pygame.joystick.quit() # Quit joystick subsystem
        if game_config._pygame_initialized_globally: pygame.quit() # Quit Pygame itself
        info("MAIN PySide6: Pygame quit. Shutdown complete."); super().closeEvent(event)

# --- Main Execution ---
def main():
    # Ensure global Pygame init happens before QApplication, if not already done by config.py import
    if not game_config._pygame_initialized_globally:
        game_config.init_pygame_and_joystick_globally()

    app = QApplication.instance();
    if app is None: app = QApplication(sys.argv)
    info("MAIN PySide6: Application starting...")
    main_window = MainWindow(); main_window.showMaximized()
    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")
    if APP_STATUS.app_running: APP_STATUS.app_running = False
    info("MAIN PySide6: Application fully terminated."); sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e_main_outer:
        log_func = critical if 'critical' in globals() and callable(critical) and _project_root else print
        log_func(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True)
        try:
            error_app = QApplication.instance(); 
            if error_app is None: error_app = QApplication(sys.argv)
            msg_box = QMessageBox(); msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")
            log_path_info_str = ""
            if LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH and os.path.exists(LOG_FILE_PATH):
                log_path_info_str = f"Please check the log file for details:\n{LOG_FILE_PATH}"
            elif LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH:
                log_path_info_str = f"Log file configured at: {LOG_FILE_PATH} (may not exist if error was early)."
            else:
                log_path_info_str = "Logging to file is disabled or path not set. Check console output."
            msg_box.setInformativeText(f"Error: {str(e_main_outer)[:1000]}\n\n{log_path_info_str}")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        except Exception as e_msgbox:
            print(f"FATAL: Could not display Qt error dialog: {e_msgbox}"); traceback.print_exc()
        sys.exit(1)