# app_core.py
# -*- coding: utf-8 -*-
"""
Main application core for the PySide6 platformer game.
Handles window creation, UI views, game loop, input management,
and game mode orchestration.
Map loading now uses map_name_folder/map_name_file.py structure.
MODIFIED: Statue physics and lifecycle management in game loop.
MODIFIED: Chest insta-kill logic for P1 in host_waiting mode.
"""
# version 2.1.4 (Chest Insta-Kill in host_waiting)

import sys
import os
import traceback
import time
import math # Added for chest crush logic
from typing import Dict, Optional, Any, List, Tuple, cast

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy, QScrollArea
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QScreen, QKeySequence)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize, QTimer, QRectF # Added QRectF for type hinting

import pygame # For joystick input and event pump

# --- Project Root Setup ---
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# --- End Project Root Setup ---

# --- Game-Specific Imports (after sys.path modification) ---
try:
    from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
    from utils import PrintLimiter
    import constants as C
    from game_ui import GameSceneWidget, IPInputDialog
    import config as game_config
    from player import Player
    from statue import Statue
    from items import Chest # Import Chest

    from app_ui_creator import (
        _create_main_menu_widget, _create_map_select_widget,
        _populate_map_list_for_selection, _create_view_page_with_back_button,
        _ensure_editor_instance, _ensure_controls_settings_instance,
        _add_placeholder_to_content_area,
        _show_status_dialog, _update_status_dialog, _close_status_dialog,
        _show_lan_search_dialog, _update_lan_search_list_focus, _update_ip_dialog_button_focus,
        _poll_pygame_joysticks_for_ui_navigation,
        _navigate_current_menu_pygame_joy, _activate_current_menu_selected_button_pygame_joy,
        _update_current_menu_button_focus, _reset_all_prev_press_flags, _activate_ip_dialog_button,
        _create_couch_coop_player_select_dialog,
        _navigate_couch_coop_player_select_dialog,
        _activate_couch_coop_player_select_dialog_button,
        _update_couch_coop_player_select_dialog_focus
    )
    import app_game_modes

    from app_input_manager import (
        get_input_snapshot, update_qt_key_press, update_qt_key_release,
        clear_qt_key_events_this_frame
    )

    try:
        from server_logic import ServerState
    except ImportError:
        warning("AppCore: server_logic.ServerState not found. Using stub.")
        class ServerState:
            def __init__(self): self.app_running = True; self.client_ready = False; self.current_map_name = None
    try:
        from client_logic import ClientState
    except ImportError:
        warning("AppCore: client_logic.ClientState not found. Using stub.")
        class ClientState:
             def __init__(self): self.app_running = True; self.map_download_status = "unknown"
    try:
        from couch_play_logic import run_couch_play_mode
    except ImportError:
        error("AppCore CRITICAL: couch_play_logic.run_couch_play_mode not found! Stubbing.")
        def run_couch_play_mode(*args: Any, **kwargs: Any) -> bool: return False

    try:
        from game_state_manager import reset_game_state
        from game_setup import initialize_game_elements
    except ImportError:
        error("AppCore CRITICAL: game_state_manager.reset_game_state or game_setup.initialize_game_elements not found! Reset will fail.")
        def reset_game_state(*args: Any, **kwargs: Any): pass
        def initialize_game_elements(*args: Any, **kwargs: Any) -> bool: return False

except ImportError as e_core_imports:
    print(f"APP_CORE CRITICAL IMPORT ERROR: {e_core_imports}")
    print(f"  Attempted project root: {_project_root}")
    print(f"  Current sys.path[0]: {sys.path[0] if sys.path else 'EMPTY'}")
    print("  Ensure app_core.py is in the correct project structure and all sibling modules are present.")
    sys.exit(f"AppCore critical import failure: {e_core_imports}")
# --- End Game-Specific Imports ---


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

class AppStatus:
    def __init__(self):
        self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        app_instance = QApplication.instance()
        if app_instance:
            debug("APP_STATUS: Requesting QApplication.quit().")
            QApplication.quit()

APP_STATUS = AppStatus()

class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float)
    operation_finished_signal = Signal(str)
    client_fully_synced_signal = Signal()

    def __init__(self, mode: str, game_elements_ref: Dict[str, Any],
                 server_state_ref: Optional[ServerState] = None,
                 client_state_ref: Optional[ClientState] = None,
                 target_ip_port: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mode = mode
        self.game_elements = game_elements_ref
        self.server_state = server_state_ref
        self.client_state = client_state_ref
        self.target_ip_port = target_ip_port
        debug(f"NetworkThread initialized for mode: {mode}")

    def _ui_status_update_callback(self, title: str, message: str, progress: float):
        self.status_update_signal.emit(title, message, progress)

    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any) -> Dict[str, Any]:
        if MainWindow._instance:
            return MainWindow._instance.get_p1_input_snapshot_for_logic(player_instance)
        return {}

    def _get_p2_input_snapshot_main_thread_passthrough(self, player_instance: Any) -> Dict[str, Any]:
        if MainWindow._instance:
            return MainWindow._instance.get_p2_input_snapshot_for_logic(player_instance)
        return {}

    def run(self):
        from server_logic import run_server_mode
        from client_logic import run_client_mode
        try:
            main_window_instance = MainWindow._instance
            if self.mode == "host" and self.server_state and main_window_instance:
                debug("NetworkThread running host mode.")
                run_server_mode(self.server_state, self.game_elements,
                                self._ui_status_update_callback,
                                self._get_p1_input_snapshot_main_thread_passthrough,
                                lambda: QApplication.processEvents(),
                                lambda: self.client_fully_synced_signal.emit())
                self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state and main_window_instance:
                debug("NetworkThread running join mode.")
                run_client_mode(self.client_state, self.game_elements, self._ui_status_update_callback,
                                self.target_ip_port, self._get_p2_input_snapshot_main_thread_passthrough,
                                lambda: QApplication.processEvents())
                self.operation_finished_signal.emit("client_ended")
        except Exception as e_thread:
            critical(f"NetworkThread: Exception in {self.mode} mode: {e_thread}", exc_info=True)
            self.operation_finished_signal.emit(f"{self.mode}_error")


class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object)

    actual_editor_module_instance: Optional[Any] = None
    actual_controls_settings_instance: Optional[Any] = None

    _pygame_joysticks: List[pygame.joystick.Joystick]
    _pygame_joy_button_prev_state: List[Dict[int, bool]]

    _keyboard_selected_button_idx: int
    _controller0_selected_button_idx: int; _controller1_selected_button_idx: int
    _controller2_selected_button_idx: int; _controller3_selected_button_idx: int
    _last_active_input_source: str
    _ui_nav_focus_controller_index: int

    _keyboard_ui_focus_color_str: str = "orange"
    _p1_ui_focus_color_str: str = "yellow"
    _p2_ui_focus_color_str: str = "red"
    _p3_ui_focus_color_str: str = "lime"
    _p4_ui_focus_color_str: str = "#8A2BE2"

    _map_selection_selected_button_idx: int
    _lan_search_list_selected_idx: int
    _ip_dialog_selected_button_idx: int

    _couch_coop_player_select_dialog: Optional[QDialog] = None
    _couch_coop_player_select_dialog_buttons_ref: List[QPushButton] = []
    _couch_coop_player_select_dialog_selected_idx: int = 1
    selected_couch_coop_players: int = 2

    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: Dict[str, bool]; _pygame_joy_axis_was_active_pos: Dict[str, bool]
    _main_menu_buttons_ref: List[QPushButton]; _map_selection_buttons_ref: List[QPushButton]
    _ip_dialog_buttons_ref: List[QPushButton]; _current_active_menu_buttons: List[QPushButton]

    map_select_scroll_area: Optional[QScrollArea]; map_select_title_label: Optional[QLabel]
    map_buttons_container: Optional[QWidget]; map_buttons_layout: Optional[QGridLayout]
    lan_search_dialog: Optional[QDialog]; lan_search_status_label: Optional[QLabel]
    lan_servers_list_widget: Optional[QListWidget];
    ip_input_dialog: Optional[IPInputDialog]
    ip_input_dialog_class_ref: Optional[type] = IPInputDialog
    current_modal_dialog: Optional[str] = None

    editor_content_container: QWidget; settings_content_container: QWidget
    editor_view_page: QWidget; settings_view_page: QWidget

    status_dialog: Optional[QDialog] = None
    status_label_in_dialog: Optional[QLabel] = None
    status_progress_bar_in_dialog: Optional[QProgressBar] = None

    NUM_MAP_COLUMNS = 3
    NetworkThread = NetworkThread
    render_print_limiter = PrintLimiter(default_limit=1, default_period=3.0)


    def __init__(self):
        super().__init__()
        if MainWindow._instance is not None:
            critical("MainWindow already instantiated! This class is a singleton.")
            return
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN")
        debug("MainWindow.__init__ started.")

        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            warning("AppCore Init: Pygame/Joystick system not globally initialized. Attempting init via game_config.")
            game_config.init_pygame_and_joystick_globally(force_rescan=True)
            if not game_config._joystick_initialized_globally:
                critical("AppCore Init: FAILED to initialize Pygame Joystick system globally via config.")

        self._pygame_joysticks = []
        self._pygame_joy_button_prev_state = []
        self._keyboard_selected_button_idx = 0
        self._controller0_selected_button_idx = 0; self._controller1_selected_button_idx = 0
        self._controller2_selected_button_idx = 0; self._controller3_selected_button_idx = 0
        self._last_active_input_source = "keyboard"
        self._ui_nav_focus_controller_index = -1
        self._map_selection_selected_button_idx = 0
        self._lan_search_list_selected_idx = -1; self._ip_dialog_selected_button_idx = 0
        self._couch_coop_player_select_dialog = None
        self._couch_coop_player_select_dialog_buttons_ref = []
        self._couch_coop_player_select_dialog_selected_idx = 1 # Default to "2 Players" button (index 1)
        self.selected_couch_coop_players = 2

        self._last_pygame_joy_nav_time = 0.0
        self._pygame_joy_axis_was_active_neg = {}; self._pygame_joy_axis_was_active_pos = {}
        _reset_all_prev_press_flags(self)
        self._main_menu_buttons_ref = []; self._map_selection_buttons_ref = []; self._ip_dialog_buttons_ref = []
        self._current_active_menu_buttons = self._main_menu_buttons_ref

        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen_geo = primary_screen.availableGeometry()
            self.initial_main_window_width = max(800, min(int(screen_geo.width() * 0.75), 1600))
            self.initial_main_window_height = max(600, min(int(screen_geo.height() * 0.75), 900))
        else:
            self.initial_main_window_width = 1280; self.initial_main_window_height = 720
            warning("AppCore Init: No primary screen detected. Using default window dimensions.")
        self.setMinimumSize(QSize(800,600)); self.resize(self.initial_main_window_width, self.initial_main_window_height)

        self.fonts = {
            "small": QFont("Arial", 10),
            "medium": QFont("Arial", 20),
            "large": QFont("Arial", 24, QFont.Weight.Bold),
            "debug": QFont("Monospace", 9)
        }

        try:
            game_config.load_config()
            self._refresh_appcore_joystick_list()
        except Exception as e_cfg:
            critical(f"Error during game_config.load_config() or joystick refresh: {e_cfg}", exc_info=True)
            self._handle_config_load_failure()

        self.app_status = APP_STATUS
        self.game_elements: Dict[str, Any] = {}
        self.current_view_name: Optional[str] = None
        self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None

        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = _create_main_menu_widget(self)
        self.map_select_widget = _create_map_select_widget(self)
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)

        self.editor_content_container = QWidget(); self.editor_content_container.setLayout(QVBoxLayout())
        cast(QVBoxLayout, self.editor_content_container.layout()).setContentsMargins(0,0,0,0)
        self.settings_content_container = QWidget(); self.settings_content_container.setLayout(QVBoxLayout())
        cast(QVBoxLayout, self.settings_content_container.layout()).setContentsMargins(0,0,0,0)

        self.editor_view_page = _create_view_page_with_back_button(self, "Level Editor", self.editor_content_container, self.on_return_to_menu_from_sub_view)
        self.settings_view_page = _create_view_page_with_back_button(self, "Settings & Controls", self.settings_content_container, self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget)
        self.stacked_widget.addWidget(self.map_select_widget)
        self.stacked_widget.addWidget(self.game_scene_widget)
        self.stacked_widget.addWidget(self.editor_view_page)
        self.stacked_widget.addWidget(self.settings_view_page)

        self.setCentralWidget(self.stacked_widget)
        self.show_view("menu")

        self.network_status_update.connect(self.on_network_status_update_slot)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update_slot)

        self.game_update_timer = QTimer(self)
        self.game_update_timer.timeout.connect(self.update_game_loop)
        fps_val = getattr(C, 'FPS', 60)
        self.game_update_timer.start(1000 // max(1, fps_val))

        info("MainWindow initialization complete.")
        debug("MainWindow.__init__ finished.")


    def _refresh_appcore_joystick_list(self):
        debug("_refresh_appcore_joystick_list called.")
        self._pygame_joysticks.clear()

        if game_config._joystick_initialized_globally:
            all_detected_joysticks_from_config = game_config.get_joystick_objects()
            num_total_joysticks = len(all_detected_joysticks_from_config)
            debug(f"Total Pygame joysticks detected by config: {num_total_joysticks}")

            max_instance_id = -1
            if all_detected_joysticks_from_config:
                valid_joy_objects = [j for j in all_detected_joysticks_from_config if j is not None]
                if valid_joy_objects:
                    try:
                        for joy_obj_init_check in valid_joy_objects:
                             if not joy_obj_init_check.get_init(): joy_obj_init_check.init()
                        max_instance_id = max(j.get_instance_id() for j in valid_joy_objects if hasattr(j, 'get_instance_id'))
                    except pygame.error as e_instance_id:
                        warning(f"Error getting max instance ID during joystick refresh: {e_instance_id}")

            required_prev_state_size = max(max_instance_id + 1, C.MAX_JOYSTICK_INSTANCE_IDS_FOR_PREV_STATE)

            if len(self._pygame_joy_button_prev_state) < required_prev_state_size:
                self._pygame_joy_button_prev_state.extend([{}] * (required_prev_state_size - len(self._pygame_joy_button_prev_state)))
            elif len(self._pygame_joy_button_prev_state) > required_prev_state_size and required_prev_state_size > 0:
                 self._pygame_joy_button_prev_state = self._pygame_joy_button_prev_state[:required_prev_state_size]


            ui_joy_count = 0
            for joy_obj in all_detected_joysticks_from_config:
                if joy_obj is None: continue
                try:
                    if not joy_obj.get_init(): joy_obj.init()
                except pygame.error as e_init:
                    warning(f"AppCore Refresh: Failed to init joystick for UI/game. Name: '{getattr(joy_obj, 'name', 'N/A')}', Error: {e_init}")
                    continue

                if ui_joy_count < 4:
                    self._pygame_joysticks.append(joy_obj)
                    joy_name_ui = getattr(joy_obj, 'name', f"UnknownJoy{ui_joy_count}")
                    debug(f"Added joystick '{joy_name_ui}' (Pygame Index: {joy_obj.get_id()}, Instance ID: {joy_obj.get_instance_id()}) to UI joysticks list (for UI nav).")
                    ui_joy_count += 1

            info(f"AppCore: UI Joystick list (for UI nav) refreshed. Count: {len(self._pygame_joysticks)}.")
            info(f"AppCore: prev_button_state list (for game input) size: {len(self._pygame_joy_button_prev_state)} (to handle max instance ID).")
        else:
            info("AppCore Refresh: Pygame joystick system not globally initialized. No joysticks for AppCore.")
            self._pygame_joysticks.clear()
            self._pygame_joy_button_prev_state.clear()


    def _handle_config_load_failure(self):
        warning("MainWindow: Game config loading issue. Defaults will be used, joystick list refreshed.")
        for i in range(1, 5):
            player_num_str = f"P{i}"
            if hasattr(game_config, f"DEFAULT_{player_num_str}_INPUT_DEVICE"):
                setattr(game_config, f"CURRENT_{player_num_str}_INPUT_DEVICE", getattr(game_config, f"DEFAULT_{player_num_str}_INPUT_DEVICE"))
                setattr(game_config, f"{player_num_str}_KEYBOARD_ENABLED", getattr(game_config, f"DEFAULT_{player_num_str}_KEYBOARD_ENABLED", False))
                setattr(game_config, f"{player_num_str}_CONTROLLER_ENABLED", getattr(game_config, f"DEFAULT_{player_num_str}_CONTROLLER_ENABLED", False))

        game_config.update_player_mappings_from_config()
        info("MainWindow: Fallback to default config player settings applied due to load failure.")
        self._refresh_appcore_joystick_list()


    # --- Game Mode Launchers (delegated to app_game_modes) ---
    def _on_map_selected_for_couch_coop(self, map_name: str): app_game_modes.start_couch_play_logic(self, map_name)
    def _on_map_selected_for_host_game(self, map_name: str): app_game_modes.start_host_game_logic(self, map_name)

    def on_start_couch_play(self):
        info("GAME_MODES: Initiating Player Selection for Couch Co-op.")
        if self._couch_coop_player_select_dialog is None:
            self._couch_coop_player_select_dialog = _create_couch_coop_player_select_dialog(self)
            self._couch_coop_player_select_dialog.accepted.connect(self._on_couch_coop_players_selected)
            self._couch_coop_player_select_dialog.rejected.connect(lambda: (
                self.show_view("menu"),
                setattr(self, 'current_modal_dialog', None)
            ))

        num_controllers = len(self._pygame_joysticks)
        for i, btn in enumerate(self._couch_coop_player_select_dialog_buttons_ref):
            players_option = i + 1
            if players_option <= 2:
                btn.setEnabled(True)
            elif players_option == 3:
                btn.setEnabled(num_controllers >= 1)
            elif players_option == 4:
                btn.setEnabled(num_controllers >= 2)

        self.current_modal_dialog = "couch_coop_player_select"
        self._couch_coop_player_select_dialog_selected_idx = 1 # Default to "2 Players" button
        _update_couch_coop_player_select_dialog_focus(self)
        self._couch_coop_player_select_dialog.show()

    def _on_couch_coop_players_selected(self):
        if self._couch_coop_player_select_dialog and hasattr(self._couch_coop_player_select_dialog, 'selected_players'):
            self.selected_couch_coop_players = self._couch_coop_player_select_dialog.selected_players # type: ignore
            info(f"Couch Co-op: {self.selected_couch_coop_players} players selected.")
            self.current_modal_dialog = None
            app_game_modes.initiate_couch_play_map_selection(self)
        else:
            error("Couch Co-op player selection dialog did not return selected_players.")
            self.show_view("menu")

    def on_start_host_game(self): app_game_modes.initiate_host_game_map_selection(self)
    def on_start_join_lan(self): app_game_modes.initiate_join_lan_dialog(self)
    def on_start_join_ip(self): app_game_modes.initiate_join_ip_dialog(self)

    # --- Network Signal Slots (delegated to app_game_modes) ---
    @Slot()
    def on_client_fully_synced_for_host(self): app_game_modes.on_client_fully_synced_for_host_logic(self)
    @Slot(str, str, float)
    def on_network_status_update_slot(self, title: str, message: str, progress: float): app_game_modes.on_network_status_update_logic(self, title, message, progress)
    @Slot(str)
    def on_network_operation_finished_slot(self, message: str): app_game_modes.on_network_operation_finished_logic(self, message)
    @Slot(str, object)
    def on_lan_server_search_status_update_slot(self, status_key: str, data_obj: Optional[object] = None):
        app_game_modes.on_lan_server_search_status_update_logic(self, (status_key, data_obj))

    # --- LAN Search Helpers (delegated to app_game_modes) ---
    def _start_lan_server_search_thread(self): app_game_modes.start_lan_server_search_thread_logic(self)
    def _join_selected_lan_server_from_dialog(self): app_game_modes.join_selected_lan_server_from_dialog_logic(self)

    # --- Game Management ---
    def stop_current_game_mode(self, show_menu: bool = True):
        app_game_modes.stop_current_game_mode_logic(self, show_menu)

    def _populate_map_list_for_selection(self, purpose: str):
        _populate_map_list_for_selection(self, purpose)

    def request_close_app(self):
        info("MainWindow: request_close_app called. Initiating close sequence.")
        self.close()

    def on_return_to_menu_from_sub_view(self):
        source_view = self.current_view_name
        info(f"MainWindow: Returning to menu from: {source_view}")
        debug(f"Returning to menu from {source_view}")
        should_return_to_menu = True

        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and \
               callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"):
                    should_return_to_menu = False
            if should_return_to_menu and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'):
                self.actual_editor_module_instance.save_geometry_and_state()
            if should_return_to_menu and self.actual_editor_module_instance.parent() is not None:
                self.actual_editor_module_instance.setParent(None)

        elif source_view == "settings" and self.actual_controls_settings_instance:
            if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and \
               callable(self.actual_controls_settings_instance.save_all_settings):
                self.actual_controls_settings_instance.save_all_settings()
            if hasattr(self.actual_controls_settings_instance, 'deactivate_controller_monitoring'):
                debug("Deactivating controller monitoring from settings.")
                self.actual_controls_settings_instance.deactivate_controller_monitoring()
            game_config.load_config()
            self._refresh_appcore_joystick_list()
            game_config.update_player_mappings_from_config()
            info("AppCore: Settings saved, config reloaded, joysticks refreshed, player mappings updated after returning from Settings.")
            if should_return_to_menu and self.actual_controls_settings_instance.parent() is not None:
                self.actual_controls_settings_instance.setParent(None)

        if should_return_to_menu:
            self.show_view("menu")
        else:
            info("Return to menu cancelled by sub-view confirmation.")


    def show_view(self, view_name: str):
        info(f"MainWindow: Switching UI view to: {view_name}")
        debug(f"show_view called for: {view_name}")

        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode:
            self.stop_current_game_mode(show_menu=False)

        self.current_view_name = view_name
        target_page: Optional[QWidget] = None
        window_title_suffix = ""
        if self.current_modal_dialog != "couch_coop_player_select":
            self.current_modal_dialog = None

        if view_name in ["menu", "map_select"]:
            debug(f"Resetting UI nav state for view: {view_name}")
            self._last_active_input_source = "keyboard"
            self._ui_nav_focus_controller_index = -1
            self._keyboard_selected_button_idx = 0
            self._controller0_selected_button_idx = 0; self._controller1_selected_button_idx = 0
            self._controller2_selected_button_idx = 0; self._controller3_selected_button_idx = 0
            if view_name == "map_select": self._map_selection_selected_button_idx = 0

        view_config_map = {
            "menu": (self.main_menu_widget, " - Main Menu", self._main_menu_buttons_ref),
            "map_select": (self.map_select_widget, " - Map Selection", self._map_selection_buttons_ref),
            "game_scene": (self.game_scene_widget, f" - {(self.current_game_mode or 'Game').replace('_',' ').title()}", []),
            "editor": (self.editor_view_page, " - Level Editor", []),
            "settings": (self.settings_view_page, " - Settings & Controls", [])
        }

        if view_name in view_config_map:
            target_page, window_title_suffix, buttons_ref_for_nav = view_config_map[view_name]
            self._current_active_menu_buttons = buttons_ref_for_nav

            if view_name == "editor":
                _ensure_editor_instance(self)
            elif view_name == "settings":
                _ensure_controls_settings_instance(self)
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to main menu.")
            target_page, window_title_suffix, self._current_active_menu_buttons = view_config_map["menu"]
            self._keyboard_selected_button_idx = 0

        if target_page:
            self.stacked_widget.setCurrentWidget(target_page)
            self.setWindowTitle(f"Platformer Adventure LAN{window_title_suffix}")

            focus_target_widget = target_page
            if view_name == "editor" and self.actual_editor_module_instance:
                focus_target_widget = self.actual_editor_module_instance
            elif view_name == "settings" and self.actual_controls_settings_instance:
                focus_target_widget = self.actual_controls_settings_instance
            elif view_name == "game_scene":
                focus_target_widget = self.game_scene_widget

            focus_target_widget.setFocus(Qt.FocusReason.OtherFocusReason)

            if view_name in ["menu", "map_select"]:
                _update_current_menu_button_focus(self)

        clear_qt_key_events_this_frame()


    def keyPressEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key())
        update_qt_key_press(qt_key_enum, event.isAutoRepeat())

        active_ui_element = self.current_modal_dialog if self.current_modal_dialog else self.current_view_name
        navigated_by_keyboard_this_event = False

        if active_ui_element in ["menu", "map_select"] and not event.isAutoRepeat():
            key_pressed = event.key()
            nav_direction = 0
            is_activation_key = key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]

            if not is_activation_key:
                if key_pressed == Qt.Key.Key_Up or key_pressed == Qt.Key.Key_W: nav_direction = -1
                elif key_pressed == Qt.Key.Key_Down or key_pressed == Qt.Key.Key_S: nav_direction = 1
                elif key_pressed == Qt.Key.Key_Left or key_pressed == Qt.Key.Key_A:
                    nav_direction = -2 if active_ui_element == "map_select" else -1
                elif key_pressed == Qt.Key.Key_Right or key_pressed == Qt.Key.Key_D:
                    nav_direction = 2 if active_ui_element == "map_select" else 1

            if nav_direction != 0:
                _navigate_current_menu_pygame_joy(self, nav_direction, input_source="keyboard")
                navigated_by_keyboard_this_event = True
            elif is_activation_key:
                _activate_current_menu_selected_button_pygame_joy(self, input_source="keyboard")
                navigated_by_keyboard_this_event = True

        elif active_ui_element == "lan_search" and self.lan_search_dialog and self.lan_servers_list_widget and not event.isAutoRepeat():
            key_pressed = event.key()
            if key_pressed == Qt.Key.Key_Up or key_pressed == Qt.Key.Key_W:
                self._lan_search_list_selected_idx = max(0, self._lan_search_list_selected_idx - 1)
                _update_lan_search_list_focus(self); navigated_by_keyboard_this_event = True
            elif key_pressed == Qt.Key.Key_Down or key_pressed == Qt.Key.Key_S:
                self._lan_search_list_selected_idx = min(self.lan_servers_list_widget.count() - 1, self._lan_search_list_selected_idx + 1)
                _update_lan_search_list_focus(self); navigated_by_keyboard_this_event = True
            elif key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                self._join_selected_lan_server_from_dialog(); navigated_by_keyboard_this_event = True

        elif active_ui_element == "ip_input" and self.ip_input_dialog and not event.isAutoRepeat():
            if self.ip_input_dialog_class_ref and isinstance(self.ip_input_dialog, self.ip_input_dialog_class_ref) and \
               hasattr(self.ip_input_dialog, 'line_edit') and self.ip_input_dialog.line_edit and \
               self.ip_input_dialog.line_edit.hasFocus() and \
               not event.key() in [Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape]:
                super().keyPressEvent(event); return

            key_pressed = event.key()
            if key_pressed in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_Tab, Qt.Key.Key_Backtab]:
                self._ip_dialog_selected_button_idx = 1 - self._ip_dialog_selected_button_idx
                _update_ip_dialog_button_focus(self); navigated_by_keyboard_this_event = True
            elif key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                _activate_ip_dialog_button(self); navigated_by_keyboard_this_event = True

        elif active_ui_element == "couch_coop_player_select" and self._couch_coop_player_select_dialog and not event.isAutoRepeat():
            key_pressed = event.key()
            nav_dir_couch = 0
            if key_pressed == Qt.Key.Key_Up or key_pressed == Qt.Key.Key_W: nav_dir_couch = -1
            elif key_pressed == Qt.Key.Key_Down or key_pressed == Qt.Key.Key_S: nav_dir_couch = 1

            if nav_dir_couch != 0:
                _navigate_couch_coop_player_select_dialog(self, nav_dir_couch, "keyboard")
                navigated_by_keyboard_this_event = True
            elif key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                _activate_couch_coop_player_select_dialog_button(self, "keyboard")
                navigated_by_keyboard_this_event = True


        if navigated_by_keyboard_this_event:
            self._last_active_input_source = "keyboard"
            self._ui_nav_focus_controller_index = -1
            if active_ui_element in ["menu", "map_select"]:
                 _update_current_menu_button_focus(self)
            elif active_ui_element == "couch_coop_player_select":
                 _update_couch_coop_player_select_dialog_focus(self)
            event.accept(); return

        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat():
            if active_ui_element == "menu": self.request_close_app()
            elif active_ui_element == "map_select": self.show_view("menu")
            elif active_ui_element == "lan_search" and self.lan_search_dialog:
                self.lan_search_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
            elif active_ui_element == "ip_input" and self.ip_input_dialog:
                self.ip_input_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
            elif active_ui_element == "couch_coop_player_select" and self._couch_coop_player_select_dialog:
                self._couch_coop_player_select_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
            elif self.current_view_name == "game_scene" and self.current_game_mode:
                self.stop_current_game_mode(show_menu=True)
            elif self.current_view_name in ["editor", "settings"]:
                self.on_return_to_menu_from_sub_view()
            else:
                self.show_view("menu")
            event.accept(); return

        if not event.isAccepted():
            super().keyPressEvent(event)


    def keyReleaseEvent(self, event: QKeyEvent):
        qt_key_enum = Qt.Key(event.key())
        update_qt_key_release(qt_key_enum, event.isAutoRepeat())
        if not event.isAccepted():
            super().keyReleaseEvent(event)

    def get_p1_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 1, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p2_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 2, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p3_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 3, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p4_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 4, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)


    @Slot()
    def update_game_loop(self):
        _poll_pygame_joysticks_for_ui_navigation(self)

        uses_pygame_joy_for_gameplay = False
        for i in range(1, 5):
            if getattr(game_config, f"P{i}_CONTROLLER_ENABLED", False) and \
               getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", "").startswith("joystick_pygame_"):
                uses_pygame_joy_for_gameplay = True; break

        if self.current_game_mode and uses_pygame_joy_for_gameplay:
            if game_config._joystick_initialized_globally and pygame.joystick.get_init():
                try: pygame.event.pump()
                except pygame.error as e_pump:
                    if self.render_print_limiter.can_log("joy_pump_fail_game_loop"):
                        warning(f"AppCore GameLoop: Pygame event pump error: {e_pump}")
            elif self.render_print_limiter.can_log("joy_sys_not_init_game_loop"):
                warning("AppCore GameLoop: Pygame joystick not globally init. Cannot pump events for gameplay.")

        game_is_ready_for_logic = self.game_elements.get('game_ready_for_logic', False)
        init_is_in_progress = self.game_elements.get('initialization_in_progress', True)

        dt_sec = 1.0 / max(1, getattr(C, 'FPS', 60))

        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            if game_is_ready_for_logic and not init_is_in_progress:
                continue_game = run_couch_play_mode(
                    self.game_elements,
                    self.app_status,
                    self.get_p1_input_snapshot_for_logic,
                    self.get_p2_input_snapshot_for_logic,
                    self.get_p3_input_snapshot_for_logic,
                    self.get_p4_input_snapshot_for_logic,
                    lambda: QApplication.processEvents(),
                    lambda: dt_sec,
                    lambda msg, prog=0.0: self.game_scene_widget.update_game_state(0, download_msg=msg, download_prog=prog)
                )
                if not continue_game: self.stop_current_game_mode(show_menu=True)

        elif self.current_game_mode == "host_active" and self.app_status.app_running and \
             self.server_state and self.server_state.client_ready:
             if game_is_ready_for_logic and not init_is_in_progress:
                # Logic for host_active is primarily in server_logic.py (NetworkThread)
                # AppCore handles local P1 input snapshot which is passed to server_logic.
                pass

        elif self.current_game_mode == "host_waiting" and self.app_status.app_running and self.server_state:
            if game_is_ready_for_logic and not init_is_in_progress:
                p1: Optional[Player] = self.game_elements.get("player1")
                p1_actions: Dict[str, bool] = {}
                if p1 and isinstance(p1, Player):
                    p1_actions = self.get_p1_input_snapshot_for_logic(p1)
                    if p1_actions.get("pause"): self.stop_current_game_mode(show_menu=True); return

                    if p1_actions.get("reset"):
                        info("AppCore (host_waiting): Player 1 initiated game reset.")
                        screen_w = self.game_scene_widget.width() if self.game_scene_widget.width() > 1 else self.width()
                        screen_h = self.game_scene_widget.height() if self.game_scene_widget.height() > 1 else self.height()
                        map_name_to_reload = self.game_elements.get("map_name", self.game_elements.get("loaded_map_name"))
                        if map_name_to_reload:
                            reset_ok = initialize_game_elements(
                                current_width=screen_w, current_height=screen_h,
                                game_elements_ref=self.game_elements,
                                for_game_mode=self.current_game_mode,
                                map_module_name=map_name_to_reload
                            )
                            if reset_ok:
                                info("AppCore (host_waiting): Game reset successful.")
                                p1_after_reset = self.game_elements.get("player1") # Re-fetch p1
                                camera_after_reset = self.game_elements.get("camera")
                                if p1_after_reset and camera_after_reset: camera_after_reset.update(p1_after_reset)
                                elif camera_after_reset: camera_after_reset.static_update()
                                if self.server_state: self.server_state.current_map_name = map_name_to_reload
                            else: error("AppCore (host_waiting): Game reset FAILED.")
                        else: error("AppCore (host_waiting) Reset: Cannot determine map to reload.")
                    
                    # Re-fetch p1 after potential reset
                    p1 = self.game_elements.get("player1")
                    if p1 and isinstance(p1, Player): # Check again
                        other_players_for_p1_local: List[Player] = []
                        p1.update(dt_sec,
                                  self.game_elements.get("platforms_list", []),
                                  self.game_elements.get("ladders_list", []),
                                  self.game_elements.get("hazards_list", []),
                                  other_players_for_p1_local,
                                  self.game_elements.get("enemy_list", [])
                                  )

                    active_players_for_ai_host_wait = [p1] if p1 and p1.alive() else []
                    for enemy in list(self.game_elements.get("enemy_list",[])):
                        if hasattr(enemy, 'update'):
                            enemy.update(dt_sec, active_players_for_ai_host_wait,
                                         self.game_elements.get("platforms_list",[]),
                                         self.game_elements.get("hazards_list",[]),
                                         self.game_elements.get("enemy_list",[]))

                    current_statues_list_appcore = list(self.game_elements.get("statue_objects", []))
                    platforms_list_appcore = self.game_elements.get("platforms_list", [])
                    statues_to_keep_appcore = []
                    statues_killed_this_frame_appcore = []

                    for statue_instance_ac in current_statues_list_appcore:
                        if hasattr(statue_instance_ac, 'alive') and statue_instance_ac.alive():
                            if hasattr(statue_instance_ac, 'apply_physics_step') and not statue_instance_ac.is_smashed:
                                statue_instance_ac.apply_physics_step(dt_sec, platforms_list_appcore)
                            if hasattr(statue_instance_ac, 'update'):
                                statue_instance_ac.update(dt_sec)
                            if statue_instance_ac.alive():
                                statues_to_keep_appcore.append(statue_instance_ac)
                            else:
                                statues_killed_this_frame_appcore.append(statue_instance_ac)
                                debug(f"AppCore (host_waiting): Statue {statue_instance_ac.statue_id} no longer alive.")
                    self.game_elements["statue_objects"] = statues_to_keep_appcore
                    if statues_killed_this_frame_appcore:
                        current_platforms = self.game_elements.get("platforms_list", [])
                        new_platforms_list_ac = [
                            p_plat for p_plat in current_platforms
                            if not (isinstance(p_plat, Statue) and p_plat in statues_killed_this_frame_appcore)
                        ]
                        if len(new_platforms_list_ac) != len(current_platforms):
                            self.game_elements["platforms_list"] = new_platforms_list_ac
                            debug(f"AppCore (host_waiting): Updated platforms_list after statue removal.")

                    projectiles_current_list = self.game_elements.get("projectiles_list", [])
                    for proj_obj in list(projectiles_current_list):
                        if hasattr(proj_obj, 'update'):
                            proj_targets = [e for e in self.game_elements.get("enemy_list",[]) if hasattr(e, 'alive') and e.alive()]
                            proj_targets.extend([s for s in self.game_elements.get("statue_objects", []) if hasattr(s, 'alive') and s.alive() and not getattr(s, 'is_smashed', False)])
                            if p1 and p1.alive(): proj_targets.insert(0,p1)
                            proj_obj.update(dt_sec, self.game_elements.get("platforms_list",[]), proj_targets)
                        if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                            projectiles_list_ref = self.game_elements.get("projectiles_list");
                            if proj_obj in projectiles_list_ref: projectiles_list_ref.remove(proj_obj)
                    
                    # --- CHEST LOGIC FOR host_waiting (MODIFIED) ---
                    current_chest_server: Optional[Chest] = self.game_elements.get("current_chest")
                    if current_chest_server and isinstance(current_chest_server, Chest) and hasattr(current_chest_server, 'alive') and current_chest_server.alive():
                        current_chest_server.apply_physics_step(dt_sec) # Physics updated

                        chest_landed_on_p1_and_killed = False
                        if not current_chest_server.is_collected_flag_internal and current_chest_server.state == 'closed' and \
                           p1 and hasattr(p1, '_valid_init') and p1._valid_init and \
                           hasattr(p1, 'alive') and p1.alive() and \
                           not getattr(p1, 'is_dead', True) and not getattr(p1, 'is_petrified', False):
                            
                            if current_chest_server.rect.intersects(p1.rect):
                                is_chest_falling_meaningfully_server = hasattr(current_chest_server, 'vel_y') and current_chest_server.vel_y > 1.0
                                vertical_overlap_landing_server = current_chest_server.rect.bottom() >= p1.rect.top() and \
                                                                  current_chest_server.rect.top() < p1.rect.bottom()
                                is_landing_on_head_area_server = vertical_overlap_landing_server and \
                                                              current_chest_server.rect.bottom() <= p1.rect.top() + (p1.rect.height() * 0.6)
                                min_h_overlap_crush_server = current_chest_server.rect.width() * 0.3
                                actual_h_overlap_crush_server = min(current_chest_server.rect.right(), p1.rect.right()) - \
                                                                max(current_chest_server.rect.left(), p1.rect.left())
                                has_sufficient_h_overlap_server = actual_h_overlap_crush_server >= min_h_overlap_crush_server

                                if is_chest_falling_meaningfully_server and is_landing_on_head_area_server and has_sufficient_h_overlap_server:
                                    player_height_for_calc_server = getattr(p1, 'standing_collision_height', float(C.TILE_SIZE) * 1.5)
                                    if player_height_for_calc_server <= 0: player_height_for_calc_server = 60.0
                                    required_fall_distance_server = 2.0 * player_height_for_calc_server
                                    
                                    try:
                                        gravity_val_server = float(C.PLAYER_GRAVITY)
                                        if gravity_val_server <= 0: gravity_val_server = 0.7
                                        if required_fall_distance_server <=0: required_fall_distance_server = 1.0
                                        min_vel_y_for_kill_sq_server = 2 * gravity_val_server * required_fall_distance_server
                                        vel_y_kill_thresh_server = math.sqrt(min_vel_y_for_kill_sq_server) if min_vel_y_for_kill_sq_server > 0 else 0.0
                                    except ValueError:
                                        vel_y_kill_thresh_server = 10.0
                                        error(f"AppCore(host_waiting) Math error calc vel_y_kill_thresh. Grav: {C.PLAYER_GRAVITY}, ReqDist: {required_fall_distance_server}")

                                    has_fallen_with_kill_velocity_server = current_chest_server.vel_y >= vel_y_kill_thresh_server
                                    
                                    if has_fallen_with_kill_velocity_server:
                                        if hasattr(p1, 'insta_kill'):
                                            info(f"CRUSH AppCore(host_waiting): Chest landed on P1 with kill velocity. Insta-killing.")
                                            p1.insta_kill()
                                        else:
                                            warning(f"CRUSH_FAIL AppCore(host_waiting): P1 missing insta_kill(). Overkilling.")
                                            p1.take_damage(p1.max_health * 10) # Overkill
                                        
                                        current_chest_server.rect.moveBottom(p1.rect.top())
                                        if hasattr(current_chest_server, 'pos_midbottom'): current_chest_server.pos_midbottom.setY(current_chest_server.rect.bottom())
                                        current_chest_server.vel_y = 0.0
                                        current_chest_server.on_ground = True
                                        chest_landed_on_p1_and_killed = True
                                        if hasattr(current_chest_server, '_update_rect_from_image_and_pos'):
                                            current_chest_server._update_rect_from_image_and_pos()
                        
                        current_chest_server.on_ground = False # Reset before platform check
                        if chest_landed_on_p1_and_killed:
                            current_chest_server.on_ground = True # It landed on player
                        
                        # Platform collision for chest (if not landed on player)
                        if not chest_landed_on_p1_and_killed and \
                           not current_chest_server.is_collected_flag_internal and current_chest_server.state == 'closed':
                            for plat_chest in self.game_elements.get("platforms_list", []):
                                if isinstance(plat_chest, Statue) and plat_chest.is_smashed: continue
                                if hasattr(plat_chest, 'rect') and current_chest_server.rect.intersects(plat_chest.rect):
                                     # For vel units/frame: scaled_vel_y_chest = current_chest_server.vel_y
                                     # For vel units/sec: scaled_vel_y_chest = current_chest_server.vel_y * dt_sec
                                     # Current usage: vel * dt_sec * C.FPS suggests vel is units/ref_tick
                                     scaled_vel_y_chest = current_chest_server.vel_y * dt_sec * C.FPS
                                     previous_chest_bottom_y_estimate = current_chest_server.rect.bottom() - scaled_vel_y_chest
                                     
                                     if current_chest_server.vel_y >=0 and current_chest_server.rect.bottom() >= plat_chest.rect.top() and \
                                        previous_chest_bottom_y_estimate <= plat_chest.rect.top() + C.GROUND_SNAP_THRESHOLD :
                                         min_overlap_ratio_chest = 0.1
                                         min_horizontal_overlap_chest = current_chest_server.rect.width() * min_overlap_ratio_chest
                                         actual_overlap_width_chest = min(current_chest_server.rect.right(), plat_chest.rect.right()) - \
                                                                      max(current_chest_server.rect.left(), plat_chest.rect.left())
                                         if actual_overlap_width_chest >= min_horizontal_overlap_chest:
                                             current_chest_server.rect.moveBottom(plat_chest.rect.top())
                                             if hasattr(current_chest_server, 'pos_midbottom'): current_chest_server.pos_midbottom.setY(current_chest_server.rect.bottom())
                                             current_chest_server.vel_y = 0.0
                                             current_chest_server.on_ground = True; break
                            if hasattr(current_chest_server, '_update_rect_from_image_and_pos'): # Sync rect after all potential moves
                                current_chest_server._update_rect_from_image_and_pos()
                        
                        current_chest_server.update(dt_sec) # Animation/state logic

                        if current_chest_server.state == 'closed' and not current_chest_server.is_collected_flag_internal and \
                           p1 and p1.alive() and not p1.is_dead and not getattr(p1, 'is_petrified', False) and \
                           p1_actions.get("interact", False) and \
                           hasattr(p1,'rect') and p1.rect.colliderect(current_chest_server.rect):
                           current_chest_server.collect(p1)
                           info(f"AppCore(host_waiting): P1 collected chest.")
                    # --- END CHEST LOGIC FOR host_waiting ---

                    camera = self.game_elements.get("camera")
                    if camera:
                        p1_for_cam_host_wait = self.game_elements.get("player1") # Re-fetch in case of reset or other changes
                        if p1_for_cam_host_wait and p1_for_cam_host_wait.alive():
                            camera.update(p1_for_cam_host_wait)
                        else:
                            camera.static_update()


        elif self.current_game_mode == "join_active" and self.app_status.app_running and \
             self.client_state and self.client_state.map_download_status == "present":
            pass

        if self.current_view_name == "game_scene":
            if self.game_elements:
                 self.game_scene_widget.update_game_state(0)

        clear_qt_key_events_this_frame()


    def closeEvent(self, event: QCloseEvent):
        info("MainWindow: Close event received. Shutting down application.")
        debug("closeEvent called.")

        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow):
                if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and \
                   callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                    if not self.actual_editor_module_instance.confirm_unsaved_changes("exit"):
                        can_close_editor = False
            if not can_close_editor:
                event.ignore(); return
            else:
                if hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'):
                    self.actual_editor_module_instance.save_geometry_and_state()
                if self.actual_editor_module_instance.parent() is not None:
                    self.actual_editor_module_instance.setParent(None)
                self.actual_editor_module_instance.deleteLater()
                self.actual_editor_module_instance = None
                debug("Editor instance cleaned up.")

        if self.actual_controls_settings_instance:
            if hasattr(self.actual_controls_settings_instance, 'controller_thread') and \
               self.actual_controls_settings_instance.controller_thread is not None and \
               hasattr(self.actual_controls_settings_instance.controller_thread, 'isRunning') and \
               self.actual_controls_settings_instance.controller_thread.isRunning():
                debug("Stopping ControllerSettingsWindow's PygameControllerThread on app close...")
                if hasattr(self.actual_controls_settings_instance.controller_thread, 'stop'):
                    self.actual_controls_settings_instance.controller_thread.stop()
                if hasattr(self.actual_controls_settings_instance.controller_thread, 'wait') and \
                   not self.actual_controls_settings_instance.controller_thread.wait(500):
                    warning("AppCore Close: ControllerSettingsWindow's thread did not finish in 500ms.")

            if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and \
               callable(self.actual_controls_settings_instance.save_all_settings):
                 self.actual_controls_settings_instance.save_all_settings()
            if self.actual_controls_settings_instance.parent() is not None :
                 self.actual_controls_settings_instance.setParent(None)
            self.actual_controls_settings_instance.deleteLater()
            self.actual_controls_settings_instance = None
            debug("Controls settings instance cleaned up.")

        self.app_status.quit_app()
        app_game_modes.stop_current_game_mode_logic(self, show_menu=False)

        if game_config._pygame_initialized_globally:
            if game_config._joystick_initialized_globally:
                try:
                    if pygame.joystick.get_init(): pygame.joystick.quit()
                except pygame.error as e_joy_quit: error(f"Error quitting pygame.joystick: {e_joy_quit}")
                info("MainWindow: Pygame Joystick system quit.")
            try:
                if pygame.get_init(): pygame.quit()
            except pygame.error as e_pygame_quit: error(f"Error quitting pygame: {e_pygame_quit}")
            info("MainWindow: Pygame system quit.")

        info("MainWindow: Application shutdown sequence complete.");
        super().closeEvent(event)


def main():
    if not game_config._pygame_initialized_globally:
        game_config.init_pygame_and_joystick_globally(force_rescan=True)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    info("Application starting via app_core.main()...")
    debug("Application main() started.")

    main_window = MainWindow()
    main_window.showMaximized()

    exit_code = app.exec()

    info(f"QApplication event loop finished. Exit code: {exit_code}")
    if APP_STATUS.app_running:
        APP_STATUS.app_running = False

    info("Application fully terminated.");
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e_main_outer:
        log_func = critical if 'critical' in globals() and callable(critical) and LOGGING_ENABLED else print
        log_func(f"APP_CORE MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True)

        try:
            error_app = QApplication.instance()
            if error_app is None: error_app = QApplication(sys.argv)

            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")

            log_path_info_str = ""
            if LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH:
                 log_path_info_str = f"Please check the log file for details:\n{LOG_FILE_PATH}"
                 if not os.path.exists(LOG_FILE_PATH):
                     log_path_info_str += " (Log file may not have been created if error was very early)."
            else:
                 log_path_info_str = "Logging to file is disabled or path not set. Check console output."

            msg_box.setInformativeText(f"Error: {str(e_main_outer)[:1000]}\n\n{log_path_info_str}")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox:
            print(f"FATAL: Could not display Qt error dialog: {e_msgbox}")
            traceback.print_exc()

        sys.exit(1)