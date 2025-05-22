# app_core.py
import sys
import os
import traceback
import time
from typing import Dict, Optional, Any, List, Tuple, cast

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy, QScrollArea
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QScreen, QKeySequence)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize, QTimer

import pygame

_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
from utils import PrintLimiter
import constants as C # Keep for C.FPS if used, or replace C.FPS with direct value
from game_ui import GameSceneWidget
import config as game_config
from player import Player

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

try:
    from server_logic import ServerState
except ImportError:
    print("MERGE_DEBUG: ServerState stub used.")
    class ServerState:
        def __init__(self): self.app_running = True; self.client_ready = False; self.current_map_name = None
try:
    from client_logic import ClientState
except ImportError:
    print("MERGE_DEBUG: ClientState stub used.")
    class ClientState:
         def __init__(self): self.app_running = True; self.map_download_status = "unknown"
try:
    from couch_play_logic import run_couch_play_mode
except ImportError:
    error("CRITICAL: couch_play_logic.run_couch_play_mode not found! Stubbing.")
    print("MERGE_DEBUG: run_couch_play_mode stub used.")
    def run_couch_play_mode(*args: Any, **kwargs: Any) -> bool: return False
try:
    from game_state_manager import reset_game_state
except ImportError:
    error("CRITICAL: game_state_manager.reset_game_state not found! Stubbing.")
    print("MERGE_DEBUG: reset_game_state stub used.")
    def reset_game_state(*args: Any, **kwargs: Any): pass


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
        print(f"MERGE_DEBUG: NetworkThread initialized for mode: {mode}")

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
                print("MERGE_DEBUG: NetworkThread running host mode.")
                run_server_mode(self.server_state, self.game_elements, self._ui_status_update_callback,
                                self._get_p1_input_snapshot_main_thread_passthrough,
                                lambda: QApplication.processEvents(),
                                lambda: self.client_fully_synced_signal.emit())
                self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state and main_window_instance:
                print("MERGE_DEBUG: NetworkThread running join mode.")
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
    _controller0_selected_button_idx: int
    _controller1_selected_button_idx: int
    _controller2_selected_button_idx: int
    _controller3_selected_button_idx: int
    _last_active_input_source: str
    _ui_nav_focus_controller_index: int

    _keyboard_ui_focus_color_str: str = "orange"
    _p1_ui_focus_color_str: str = "yellow"
    _p2_ui_focus_color_str: str = "red"
    _p3_ui_focus_color_str: str = "lime"
    _p4_ui_focus_color_str: str = "#8A2BE2" # BlueViolet

    _map_selection_selected_button_idx: int
    _lan_search_list_selected_idx: int
    _ip_dialog_selected_button_idx: int

    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: Dict[str, bool]; _pygame_joy_axis_was_active_pos: Dict[str, bool]
    _main_menu_buttons_ref: List[QPushButton]; _map_selection_buttons_ref: List[QPushButton]
    _ip_dialog_buttons_ref: List[QPushButton]; _current_active_menu_buttons: List[QPushButton]

    map_select_scroll_area: Optional[QScrollArea]; map_select_title_label: Optional[QLabel]
    map_buttons_container: Optional[QWidget]; map_buttons_layout: Optional[QGridLayout]

    lan_search_dialog: Optional[QDialog]; lan_search_status_label: Optional[QLabel]
    lan_servers_list_widget: Optional[QListWidget];
    ip_input_dialog: Optional[Any]
    ip_input_dialog_class_ref: Optional[type] = None
    current_modal_dialog: Optional[str] = None

    editor_content_container: QWidget; settings_content_container: QWidget
    editor_view_page: QWidget; settings_view_page: QWidget

    status_dialog: Optional[QDialog] = None
    status_label_in_dialog: Optional[QLabel] = None
    status_progress_bar_in_dialog: Optional[QProgressBar] = None

    NUM_MAP_COLUMNS = 3 # Default, can be overridden by map selection logic
    NetworkThread = NetworkThread
    render_print_limiter = PrintLimiter(default_limit=1, default_period=3.0)
    FPS = getattr(C, "FPS", 60) # Get FPS from constants or default to 60

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN")
        print("MERGE_DEBUG: MainWindow.__init__ started.")

        if not game_config._pygame_initialized_globally or not game_config._joystick_initialized_globally:
            warning("AppCore Init: Pygame/Joystick system not globally initialized. Attempting init via config.")
            game_config.init_pygame_and_joystick_globally(force_rescan=True)
            if not game_config._joystick_initialized_globally:
                critical("AppCore Init: FAILED to initialize Pygame Joystick system globally.")

        self._pygame_joysticks = []
        self._pygame_joy_button_prev_state = []

        self._keyboard_selected_button_idx = 0
        self._controller0_selected_button_idx = 0; self._controller1_selected_button_idx = 0
        self._controller2_selected_button_idx = 0; self._controller3_selected_button_idx = 0
        self._last_active_input_source = "keyboard"
        self._ui_nav_focus_controller_index = -1

        self._map_selection_selected_button_idx = 0
        self._lan_search_list_selected_idx = -1; self._ip_dialog_selected_button_idx = 0
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
        self.fonts = {"small": QFont("Arial", 10), "medium": QFont("Arial", 14),
                      "large": QFont("Arial", 24, QFont.Weight.Bold), "debug": QFont("Monospace", 9)}

        try:
            game_config.load_config()
            self._refresh_appcore_joystick_list()
        except Exception as e_cfg:
            critical(f"Error during game_config.load_config(): {e_cfg}", exc_info=True)
            self._handle_config_load_failure()

        self.app_status = APP_STATUS; self.game_elements: Dict[str, Any] = {}
        self.current_view_name: Optional[str] = None; self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None; self.client_state: Optional[ClientState] = None
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
        self.stacked_widget.addWidget(self.main_menu_widget); self.stacked_widget.addWidget(self.map_select_widget)
        self.stacked_widget.addWidget(self.game_scene_widget); self.stacked_widget.addWidget(self.editor_view_page)
        self.stacked_widget.addWidget(self.settings_view_page)
        self.setCentralWidget(self.stacked_widget); self.show_view("menu")

        self.network_status_update.connect(self.on_network_status_update_slot)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update_slot)
        
        try:
            from game_ui import IPInputDialog # game_ui might be better place for this if it's purely UI
            self.ip_input_dialog_class_ref = IPInputDialog
            print("MERGE_DEBUG: IPInputDialog imported successfully.")
        except ImportError:
            warning("MERGE_DEBUG: FAILED to import IPInputDialog. IP Input dialog will not work.")
            self.ip_input_dialog_class_ref = None
        
        self.game_update_timer = QTimer(self)
        self.game_update_timer.timeout.connect(self.update_game_loop)
        self.game_update_timer.start(1000 // self.FPS) # Use self.FPS
        info("MainWindow initialization complete.")
        print("MERGE_DEBUG: MainWindow.__init__ finished.")


    def _refresh_appcore_joystick_list(self):
        print("MERGE_DEBUG: _refresh_appcore_joystick_list called.")
        # Quit previously held joystick objects before clearing list
        for joy_obj in self._pygame_joysticks:
            if joy_obj and joy_obj.get_init():
                try: joy_obj.quit()
                except pygame.error: pass # Ignore errors on quit, joystick might be disconnected
        self._pygame_joysticks.clear() 

        if game_config._joystick_initialized_globally:
            all_detected_joysticks_from_config = game_config.get_joystick_objects()
            num_total_joysticks_from_pygame = pygame.joystick.get_count() # Direct count from Pygame
            
            print(f"MERGE_DEBUG: Total joysticks from config.get_joystick_objects(): {len(all_detected_joysticks_from_config)}")
            print(f"MERGE_DEBUG: Total joysticks from pygame.joystick.get_count(): {num_total_joysticks_from_pygame}")

            # Resize prev_state based on the maximum possible joysticks (e.g., instance IDs can be > count)
            # A safer approach is to use a dictionary for prev_state keyed by instance_id.
            # For now, ensure it's large enough for num_total_joysticks_from_pygame.
            max_expected_joysticks = max(num_total_joysticks_from_pygame, 8) # Pad for safety up to 8, or use a defined C.MAX_JOYSTICKS
            
            if len(self._pygame_joy_button_prev_state) < max_expected_joysticks:
                self._pygame_joy_button_prev_state.extend([{}] * (max_expected_joysticks - len(self._pygame_joy_button_prev_state)))
            # No need to shrink if fewer joysticks, as instance IDs might still be high.

            ui_joy_count = 0
            # Iterate using game_config.get_joystick_objects() as it holds the Joystick instances from config.py's scan
            for joy_obj in all_detected_joysticks_from_config: 
                if ui_joy_count >= game_config.MAX_UI_CONTROLLERS_FOR_NAV: # Use constant
                    print(f"MERGE_DEBUG: Max UI joysticks ({game_config.MAX_UI_CONTROLLERS_FOR_NAV}) reached for UI navigation.")
                    break
                if joy_obj is not None: # Check if the object from the list is not None
                    try:
                        if not joy_obj.get_init(): joy_obj.init() # Ensure initialized for UI use
                        self._pygame_joysticks.append(joy_obj)
                        print(f"MERGE_DEBUG: Added joystick '{getattr(joy_obj, 'name', 'N/A')}' (Instance ID: {joy_obj.get_instance_id()}, Pygame Idx: {joy_obj.get_id()}) to UI joysticks list.")
                        ui_joy_count += 1
                    except pygame.error as e_init:
                        warning(f"AppCore Refresh: Failed to init joystick '{getattr(joy_obj, 'name', 'N/A')}' for UI. Error: {e_init}")
            
            info(f"AppCore: UI Joystick list refreshed. Count: {len(self._pygame_joysticks)} (from {num_total_joysticks_from_pygame} total).")
            info(f"AppCore: Full prev_button_state list size for game input: {len(self._pygame_joy_button_prev_state)}")
        else:
            info("AppCore Refresh: Pygame joystick system not globally initialized. No joysticks for AppCore.")
            self._pygame_joysticks.clear()
            self._pygame_joy_button_prev_state.clear()


    def _handle_config_load_failure(self):
        warning("MAIN PySide6: Game config loading issue. Defaults will be used.")
        for i in range(1, 5): 
            p_prefix = f"P{i}"
            default_input_device_var = f"DEFAULT_{p_prefix}_INPUT_DEVICE"
            current_input_device_var = f"CURRENT_{p_prefix}_INPUT_DEVICE"
            keyboard_enabled_var = f"{p_prefix}_KEYBOARD_ENABLED"
            default_keyboard_enabled_var = f"DEFAULT_{p_prefix}_KEYBOARD_ENABLED"
            controller_enabled_var = f"{p_prefix}_CONTROLLER_ENABLED"
            default_controller_enabled_var = f"DEFAULT_{p_prefix}_CONTROLLER_ENABLED"

            if hasattr(game_config, default_input_device_var):
                setattr(game_config, current_input_device_var, getattr(game_config, default_input_device_var))
            if hasattr(game_config, default_keyboard_enabled_var):
                setattr(game_config, keyboard_enabled_var, getattr(game_config, default_keyboard_enabled_var))
            if hasattr(game_config, default_controller_enabled_var):
                setattr(game_config, controller_enabled_var, getattr(game_config, default_controller_enabled_var))
        
        game_config.update_player_mappings_from_config()
        info("MAIN PySide6: Fallback to default config settings due to load failure.")
        self._refresh_appcore_joystick_list()

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
    def on_lan_server_search_status_update_slot(self, status_key: str, data_obj: Optional[object] = None):
        print(f"MERGE_DEBUG: on_lan_server_search_status_update_slot received: key='{status_key}', data='{data_obj}'")
        app_game_modes.on_lan_server_search_status_update_logic(self, (status_key, data_obj))

    def _start_lan_server_search_thread(self): app_game_modes.start_lan_server_search_thread_logic(self)
    def _join_selected_lan_server_from_dialog(self): app_game_modes.join_selected_lan_server_from_dialog_logic(self)
    def stop_current_game_mode(self, show_menu: bool = True): app_game_modes.stop_current_game_mode_logic(self, show_menu)
    def _populate_map_list_for_selection(self, purpose: str): _populate_map_list_for_selection(self, purpose)
    def request_close_app(self): self.close()

    def on_return_to_menu_from_sub_view(self):
        source_view = self.current_view_name; info(f"Returning to menu from: {source_view}"); should_return = True
        print(f"MERGE_DEBUG: on_return_to_menu_from_sub_view from {source_view}")
        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"): should_return = False
            if should_return and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'): self.actual_editor_module_instance.save_geometry_and_state()
            if should_return and self.actual_editor_module_instance.parent() is not None: self.actual_editor_module_instance.setParent(None)
        elif source_view == "settings" and self.actual_controls_settings_instance:
            if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and callable(self.actual_controls_settings_instance.save_all_settings):
                self.actual_controls_settings_instance.save_all_settings()
            
            if hasattr(self.actual_controls_settings_instance, 'deactivate_controller_monitoring'):
                print("MERGE_DEBUG: Deactivating controller monitoring from settings.")
                self.actual_controls_settings_instance.deactivate_controller_monitoring()
            
            game_config.load_config() 
            self._refresh_appcore_joystick_list() 
            game_config.update_player_mappings_from_config() 
            info("AppCore: Settings saved, config reloaded, joysticks refreshed, player mappings updated.")
            
            if should_return and self.actual_controls_settings_instance.parent() is not None: self.actual_controls_settings_instance.setParent(None)
        
        if should_return: self.show_view("menu")
        else: info("Return to menu cancelled by sub-view.")

    def show_view(self, view_name: str):
        info(f"Switching UI view to: {view_name}")
        print(f"MERGE_DEBUG: show_view called for: {view_name}")
        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode:
            self.stop_current_game_mode(show_menu=False)
        
        self.current_view_name = view_name; target_page: Optional[QWidget] = None
        window_title = "Platformer Adventure LAN"; self.current_modal_dialog = None
        
        if view_name in ["menu", "map_select"]:
            print(f"MERGE_DEBUG: Resetting UI nav state for view: {view_name}")
            self._last_active_input_source = "keyboard"
            self._ui_nav_focus_controller_index = -1 
            self._keyboard_selected_button_idx = 0
            self._controller0_selected_button_idx = 0; self._controller1_selected_button_idx = 0
            self._controller2_selected_button_idx = 0; self._controller3_selected_button_idx = 0
            if view_name == "map_select": self._map_selection_selected_button_idx = 0 
        
        view_map = {
            "menu": (self.main_menu_widget, " - Main Menu", self._main_menu_buttons_ref),
            "map_select": (self.map_select_widget, " - Map Selection", self._map_selection_buttons_ref),
            "game_scene": (self.game_scene_widget, f" - {self.current_game_mode.replace('_',' ').title() if self.current_game_mode else 'Game'}", []),
            "editor": (self.editor_view_page, " - Level Editor", []),
            "settings": (self.settings_view_page, " - Settings & Controls", [])
        }
        if view_name in view_map:
            target_page, title_suffix, buttons_ref = view_map[view_name]
            window_title += title_suffix; self._current_active_menu_buttons = buttons_ref
            
            if view_name == "editor": _ensure_editor_instance(self)
            elif view_name == "settings":
                _ensure_controls_settings_instance(self)
                if self.actual_controls_settings_instance and \
                   hasattr(self.actual_controls_settings_instance, 'activate_controller_monitoring'):
                    print("MERGE_DEBUG: Activating controller monitoring for settings view.")
                    self.actual_controls_settings_instance.activate_controller_monitoring()
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to menu.")
            target_page = self.main_menu_widget; window_title += " - Main Menu"
            self._current_active_menu_buttons = self._main_menu_buttons_ref
            self._keyboard_selected_button_idx = 0 

        if target_page:
            self.stacked_widget.setCurrentWidget(target_page); self.setWindowTitle(window_title)
            if view_name in ["menu", "map_select"]: _update_current_menu_button_focus(self) 
            focus_target = target_page
            if view_name == "editor" and self.actual_editor_module_instance: focus_target = self.actual_editor_module_instance
            elif view_name == "settings" and self.actual_controls_settings_instance: focus_target = self.actual_controls_settings_instance
            elif view_name == "game_scene": focus_target = self.game_scene_widget
            
            # Set focus, important for GameSceneWidget to receive key events
            focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
            debug(f"MainWindow.show_view: Set focus to {type(focus_target).__name__}")

        clear_qt_key_events_this_frame() # Clear after switching view and setting focus


    def keyPressEvent(self, event: QKeyEvent):
        qt_key_enum_press = Qt.Key(event.key())
        # ALWAYS update the global input state for app_input_manager
        update_qt_key_press(qt_key_enum_press, event.isAutoRepeat())
        
        # --- UI Navigation Logic ---
        active_ui_element = self.current_modal_dialog if self.current_modal_dialog else self.current_view_name
        navigated_by_keyboard_this_event = False

        # Handle UI navigation if not in game_scene, editor, or settings (where game/sub-app handles input)
        if active_ui_element not in ["game_scene", "editor", "settings"]:
            if active_ui_element in ["menu", "map_select"] and not event.isAutoRepeat():
                key_pressed = event.key() 
                nav_direction = 0 # 0=none, -1=Up, 1=Down, -2=Left, 2=Right (for list-like menus)
                                  # For grid menus, map_select uses GRID_NAV constants
                is_activation_key = key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]

                if not is_activation_key: 
                    if key_pressed == Qt.Key.Key_Up or key_pressed == Qt.Key.Key_W: nav_direction = -1
                    elif key_pressed == Qt.Key.Key_Down or key_pressed == Qt.Key.Key_S: nav_direction = 1
                    elif key_pressed == Qt.Key.Key_Left or key_pressed == Qt.Key.Key_A:
                        nav_direction = game_config.GRID_NAV_LEFT if active_ui_element == "map_select" else -2
                    elif key_pressed == Qt.Key.Key_Right or key_pressed == Qt.Key.Key_D:
                        nav_direction = game_config.GRID_NAV_RIGHT if active_ui_element == "map_select" else 2
                
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
                is_line_edit_focused = self.ip_input_dialog_class_ref and \
                                     isinstance(self.ip_input_dialog, self.ip_input_dialog_class_ref) and \
                                     self.ip_input_dialog.line_edit and self.ip_input_dialog.line_edit.hasFocus()

                key_pressed = event.key()
                
                if is_line_edit_focused and key_pressed not in [Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape]:
                    super().keyPressEvent(event) # Let line edit handle character input
                    return 
                
                # Handle Tab/Backtab or L/R/A/D for button navigation, or Enter/Space for activation
                if key_pressed in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_Tab, Qt.Key.Key_Backtab]:
                    if not is_line_edit_focused or key_pressed in [Qt.Key.Key_Tab, Qt.Key.Key_Backtab]: # Allow Tab to navigate buttons if line_edit not focused
                        self._ip_dialog_selected_button_idx = 1 - self._ip_dialog_selected_button_idx
                        _update_ip_dialog_button_focus(self); navigated_by_keyboard_this_event = True
                elif key_pressed in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                    _activate_ip_dialog_button(self); navigated_by_keyboard_this_event = True

        # Handle Escape key universally (except when line edit in IP dialog has focus and needs it)
        if event.key() == Qt.Key.Key_Escape and not event.isAutoRepeat():
            is_ip_line_edit_focused_for_esc = self.current_modal_dialog == "ip_input" and \
                                           self.ip_input_dialog_class_ref and \
                                           isinstance(self.ip_input_dialog, self.ip_input_dialog_class_ref) and \
                                           self.ip_input_dialog.line_edit and self.ip_input_dialog.line_edit.hasFocus()
            
            if not is_ip_line_edit_focused_for_esc: # If Esc is not for line edit, process it for UI
                if active_ui_element == "menu": self.request_close_app()
                elif active_ui_element == "map_select": self.show_view("menu")
                elif active_ui_element == "lan_search" and self.lan_search_dialog: self.lan_search_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
                elif active_ui_element == "ip_input" and self.ip_input_dialog: self.ip_input_dialog.reject(); self.current_modal_dialog = None; self.show_view("menu")
                elif self.current_view_name == "game_scene" and self.current_game_mode: self.stop_current_game_mode(show_menu=True)
                elif self.current_view_name in ["editor", "settings"]: self.on_return_to_menu_from_sub_view()
                else: self.show_view("menu") 
                event.accept(); return

        if navigated_by_keyboard_this_event:
            self._last_active_input_source = "keyboard" 
            self._ui_nav_focus_controller_index = -1    
            if active_ui_element in ["menu", "map_select"]:
                 _update_current_menu_button_focus(self) 
            event.accept(); return
        
        # If the event hasn't been accepted by UI navigation or specific Escape logic,
        # and it's not for a sub-app that handles its own input (like GameSceneWidget should),
        # then call super(). This ensures standard Qt behavior (like text input in QLineEdit) works.
        if not event.isAccepted():
            # For views like GameSceneWidget, editor, settings, their own event handlers
            # (like GameSceneWidget.keyPressEvent) should be primary.
            # MainWindow's super().keyPressEvent is a fallback.
            if self.current_view_name not in ["game_scene", "editor", "settings"] or \
               (self.current_view_name == "ip_input" and self.ip_input_dialog and self.ip_input_dialog.line_edit and self.ip_input_dialog.line_edit.hasFocus()):
                 super().keyPressEvent(event)
            # If it's game_scene, editor, or settings, their specific keyPressEvent (which now calls update_qt_key_press)
            # will have run. We don't necessarily want MainWindow's super() to run again for those keys
            # unless the sub-widget explicitly calls super() itself.


    def keyReleaseEvent(self, event: QKeyEvent):
        qt_key_enum_release = Qt.Key(event.key())
        update_qt_key_release(qt_key_enum_release, event.isAutoRepeat())
        
        if not event.isAccepted():
            # Similar logic to keyPressEvent for super call
            if self.current_view_name not in ["game_scene", "editor", "settings"] or \
               (self.current_view_name == "ip_input" and self.ip_input_dialog and self.ip_input_dialog.line_edit and self.ip_input_dialog.line_edit.hasFocus()):
                super().keyReleaseEvent(event)

    def get_p1_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 1, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p2_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 2, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p3_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 3, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)
    def get_p4_input_snapshot_for_logic(self, player_instance: Any) -> Dict[str, Any]:
        return get_input_snapshot(player_instance, 4, game_config.get_joystick_objects(), self._pygame_joy_button_prev_state, self.game_elements)


    def update_game_loop(self):
        _poll_pygame_joysticks_for_ui_navigation(self)
        
        uses_pygame_joy_for_gameplay = False
        for i in range(1, 5): # Max 4 players
            if getattr(game_config, f"P{i}_CONTROLLER_ENABLED", False) and \
               getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", "").startswith("joystick_"):
                uses_pygame_joy_for_gameplay = True; break
        
        if self.current_game_mode and uses_pygame_joy_for_gameplay:
            if game_config._joystick_initialized_globally and pygame.joystick.get_init():
                try: pygame.event.pump()
                except pygame.error as e:
                    if self.render_print_limiter.can_print("joy_pump_fail_game_loop"): warning(f"AppCore GameLoop: Pygame event pump error: {e}")
            elif self.render_print_limiter.can_print("joy_sys_not_init_game_loop"):
                warning("AppCore GameLoop: Pygame joystick not globally init. Cannot pump events for gameplay.")
        
        game_is_ready = self.game_elements.get('game_ready_for_logic', False)
        init_in_progress = self.game_elements.get('initialization_in_progress', True)

        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            if game_is_ready and not init_in_progress:
                dt_sec = 1.0 / self.FPS
                
                p_getters = [
                    self.get_p1_input_snapshot_for_logic, self.get_p2_input_snapshot_for_logic,
                    self.get_p3_input_snapshot_for_logic, self.get_p4_input_snapshot_for_logic
                ]
                num_configured_players = 0 
                for i in range(1, 5):
                    dev_key = f"CURRENT_P{i}_INPUT_DEVICE"
                    kbd_en_key = f"P{i}_KEYBOARD_ENABLED"
                    ctrl_en_key = f"P{i}_CONTROLLER_ENABLED"
                    
                    is_assigned = getattr(game_config, dev_key, "unassigned") != "unassigned"
                    is_input_enabled = getattr(game_config, kbd_en_key, False) or \
                                       (getattr(game_config, ctrl_en_key, False) and \
                                        getattr(game_config, dev_key, "").startswith("joystick_"))

                    if is_assigned and is_input_enabled:
                        num_configured_players = i 
                    elif not is_assigned and num_configured_players < i-1 : 
                        break
                
                # Limit actual players for couch_play_logic based on its known support (e.g., 2 players)
                # This can be adjusted if couch_play_logic is updated for more players.
                max_players_for_couch_logic = 2 # Assume couch_play_logic currently supports max 2
                actual_players_for_couch_logic = min(num_configured_players, max_players_for_couch_logic)

                input_getter_args = [p_getters[j] for j in range(actual_players_for_couch_logic)]
                
                # Pad with dummy getters if couch_play_logic expects more than available/configured
                # For example, if it always expects 2, but only 1 is configured and active.
                # The current run_couch_play_mode call takes exactly 2 player input functions.
                while len(input_getter_args) < 2: # Ensure at least 2 for the hardcoded call below
                    input_getter_args.append(lambda p_inst: {})


                continue_game = run_couch_play_mode(
                    self.game_elements,                      
                    self.app_status,                         
                    input_getter_args[0], # P1 input (or dummy)
                    input_getter_args[1], # P2 input (or dummy)
                    lambda: QApplication.processEvents(),    
                    lambda: dt_sec,                          
                    lambda msg: self.game_scene_widget.update_game_state(0, download_msg=msg) 
                )
                if not continue_game: self.stop_current_game_mode(show_menu=True)

        elif self.current_game_mode == "host_active" and self.app_status.app_running and self.server_state and self.server_state.client_ready:
             if game_is_ready and not init_in_progress:
                 pass # Server logic handles updates for host_active

        elif self.current_game_mode == "host_waiting" and self.app_status.app_running and self.server_state:
            if game_is_ready and not init_in_progress:
                dt_sec = 1.0 / self.FPS
                p1 = self.game_elements.get("player1")
                
                if p1:
                    p1_actions = self.get_p1_input_snapshot_for_logic(p1)
                    if p1_actions.get("pause"): self.stop_current_game_mode(show_menu=True); return
                    if p1_actions.get("reset"): reset_game_state(self.game_elements)
                    
                    p1.update(dt_sec, self.game_elements.get("platforms_list", []),
                              self.game_elements.get("ladders_list", []),
                              self.game_elements.get("hazards_list", []),
                              [], 
                              self.game_elements.get("enemy_list", [])
                              )

                    active_players_for_ai = [p1] if p1 and p1.alive() else []
                    for enemy in list(self.game_elements.get("enemy_list",[])):
                        if hasattr(enemy, 'update'):
                            enemy.update(dt_sec, active_players_for_ai,
                                         self.game_elements.get("platforms_list",[]),
                                         self.game_elements.get("hazards_list",[]),
                                         self.game_elements.get("enemy_list",[]))
                    
                    projectiles_current_list = self.game_elements.get("projectiles_list", [])
                    for proj_obj in list(projectiles_current_list):
                        if hasattr(proj_obj, 'update'):
                            proj_targets = [e for e in self.game_elements.get("enemy_list",[]) if hasattr(e, 'alive') and e.alive()]
                            if p1 and p1.alive(): proj_targets.insert(0,p1) 
                            proj_obj.update(dt_sec, self.game_elements.get("platforms_list",[]), proj_targets)
                        if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                            if proj_obj in projectiles_current_list: projectiles_current_list.remove(proj_obj)
                    
                    camera = self.game_elements.get("camera")
                    if camera and p1 and p1.alive(): camera.update(p1)

        elif self.current_game_mode == "join_active" and self.app_status.app_running and self.client_state and self.client_state.map_download_status == "present":
            pass # Client logic handles updates

        if self.current_view_name == "game_scene":
            if self.game_elements:
                 self.game_scene_widget.update_game_state(0) # game_time_ticks is ignored by widget
        
        # CRITICAL: Clear discrete key events *after* all logic for the frame has used them.
        clear_qt_key_events_this_frame()


    def closeEvent(self, event: QCloseEvent):
        info("MAIN PySide6: Close event. Shutting down.")
        print("MERGE_DEBUG: closeEvent called.")
        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow): # or QWidget if editor is simpler
                if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                    if not self.actual_editor_module_instance.confirm_unsaved_changes("exit"): can_close_editor = False
            if not can_close_editor: event.ignore(); return
            else:
                if hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'): self.actual_editor_module_instance.save_geometry_and_state()
                if self.actual_editor_module_instance.parent() is not None: self.actual_editor_module_instance.setParent(None)
                self.actual_editor_module_instance.deleteLater(); self.actual_editor_module_instance = None

        if self.actual_controls_settings_instance:
            if hasattr(self.actual_controls_settings_instance, 'controller_thread') and \
               self.actual_controls_settings_instance.controller_thread is not None and \
               hasattr(self.actual_controls_settings_instance.controller_thread, 'isRunning') and \
               self.actual_controls_settings_instance.controller_thread.isRunning():
                print("MERGE_DEBUG: Stopping ControllerSettingsWindow's PygameControllerThread on app close...")
                if hasattr(self.actual_controls_settings_instance.controller_thread, 'stop'):
                    self.actual_controls_settings_instance.controller_thread.stop()
                if hasattr(self.actual_controls_settings_instance.controller_thread, 'wait') and \
                   not self.actual_controls_settings_instance.controller_thread.wait(500):
                    warning("MERGE_DEBUG: ControllerSettingsWindow's thread did not finish in 500ms during app close.")

            if hasattr(self.actual_controls_settings_instance, 'save_all_settings') and callable(self.actual_controls_settings_instance.save_all_settings):
                 self.actual_controls_settings_instance.save_all_settings()
            if self.actual_controls_settings_instance.parent() is not None: self.actual_controls_settings_instance.setParent(None)
            self.actual_controls_settings_instance.deleteLater(); self.actual_controls_settings_instance = None

        self.app_status.quit_app()
        app_game_modes.stop_current_game_mode_logic(self, show_menu=False) # Clean up game modes
        
        if game_config._pygame_initialized_globally:
            if game_config._joystick_initialized_globally:
                try: 
                    if pygame.joystick.get_init(): pygame.joystick.quit()
                except pygame.error as e: error(f"Error quitting pygame.joystick: {e}")
                info("MAIN PySide6: Pygame Joystick system quit.")
            try: 
                if pygame.get_init(): pygame.quit()
            except pygame.error as e: error(f"Error quitting pygame: {e}")
            info("MAIN PySide6: Pygame quit.")
        
        info("MAIN PySide6: Application shutdown sequence complete."); super().closeEvent(event)


def main():
    if not game_config._pygame_initialized_globally: # Ensure Pygame is up before QApplication
        game_config.init_pygame_and_joystick_globally(force_rescan=True)

    app = QApplication.instance();
    if app is None: app = QApplication(sys.argv)
    info("MAIN PySide6: Application starting...")
    print("MERGE_DEBUG: Application main() started.")
    main_window = MainWindow(); main_window.showMaximized() # Or .show()
    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")
    if APP_STATUS.app_running: APP_STATUS.app_running = False # Ensure app_status reflects exit
    info("MAIN PySide6: Application fully terminated."); sys.exit(exit_code)

if __name__ == "__main__":
    try: main()
    except Exception as e_main_outer:
        log_func = critical if 'critical' in globals() and callable(critical) and globals().get('_project_root') else print
        log_func(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True) 
        print(f"MERGE_DEBUG_FATAL: MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}\n{traceback.format_exc()}")
        try:
            # Attempt to show a Qt error dialog even on catastrophic failure
            error_app = QApplication.instance(); 
            if error_app is None: error_app = QApplication(sys.argv) # Must exist for QMessageBox
            msg_box = QMessageBox(); msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")
            log_path_info_str = ""
            # Check LOGGING_ENABLED and LOG_FILE_PATH from logger.py if they are global or accessible via a config object
            # Assuming logger.py defines these or they are available via another means:
            try: 
                if LOGGING_ENABLED and LOG_FILE_PATH and os.path.exists(LOG_FILE_PATH): log_path_info_str = f"Please check the log file for details:\n{LOG_FILE_PATH}"
                elif LOGGING_ENABLED and LOG_FILE_PATH: log_path_info_str = f"Log file configured at: {LOG_FILE_PATH} (may not exist if error was early)."
                else: log_path_info_str = "Logging to file is disabled or path not set. Check console output."
            except NameError: # If LOGGING_ENABLED or LOG_FILE_PATH are not globally defined here
                log_path_info_str = "Log file path information unavailable."

            msg_box.setInformativeText(f"Error: {str(e_main_outer)[:1000]}\n\n{log_path_info_str}")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        except Exception as e_msgbox:
            print(f"FATAL: Could not display Qt error dialog: {e_msgbox}"); traceback.print_exc()
        sys.exit(1)