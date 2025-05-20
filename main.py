import sys
import os
import traceback
import time
from typing import Dict, Optional, Any, List, Tuple

# PySide6 imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, # Added QGridLayout
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy, QScrollArea
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QColor, QPalette, QScreen, QKeySequence)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize,QTimer

# Pygame import for controller menu navigation
import pygame

_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH

import constants as C
from game_setup import initialize_game_elements, reset_game_state # Added reset_game_state
from server_logic import ServerState, run_server_mode
from client_logic import ClientState, run_client_mode, find_server_on_lan
from couch_play_logic import run_couch_play_mode
from game_ui import GameSceneWidget, SelectMapDialog, IPInputDialog
import config as game_config
import joystick_handler # This is the 'inputs' library based handler
from player import Player
from player_input_handler import process_player_input_logic_pyside as process_player_input_logic

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

QT_KEY_MAP = {
    "A": Qt.Key.Key_A, "D": Qt.Key.Key_D, "W": Qt.Key.Key_W, "S": Qt.Key.Key_S,
    "V": Qt.Key.Key_V, "B": Qt.Key.Key_B,
    "SHIFT": Qt.Key.Key_Shift, "LSHIFT": Qt.Key.Key_Shift,
    "CONTROL": Qt.Key.Key_Control, "LCONTROL": Qt.Key.Key_Control,
    "E": Qt.Key.Key_E, "Q": Qt.Key.Key_Q,
    "1": Qt.Key.Key_1, "2": Qt.Key.Key_2, "3": Qt.Key.Key_3, "4": Qt.Key.Key_4,
    "5": Qt.Key.Key_5, "6": Qt.Key.Key_6, "7": Qt.Key.Key_7,
    "ESCAPE": Qt.Key.Key_Escape, "RETURN": Qt.Key.Key_Return, "ENTER": Qt.Key.Key_Enter,
    "UP": Qt.Key.Key_Up, "DOWN": Qt.Key.Key_Down, "LEFT": Qt.Key.Key_Left, "RIGHT": Qt.Key.Key_Right,
    "SPACE": Qt.Key.Key_Space,
    "J": Qt.Key.Key_J, "L": Qt.Key.Key_L, "I": Qt.Key.Key_I, "K": Qt.Key.Key_K,
    "O": Qt.Key.Key_O, "P": Qt.Key.Key_P,
    ";": Qt.Key.Key_Semicolon, "'": Qt.Key.Key_Apostrophe, "\\": Qt.Key.Key_Backslash,
    "NUM+0": Qt.Key.Key_0, "NUM+1": Qt.Key.Key_1, "NUM+2": Qt.Key.Key_2,
    "NUM+3": Qt.Key.Key_3, "NUM+4": Qt.Key.Key_4, "NUM+5": Qt.Key.Key_5,
    "NUM+6": Qt.Key.Key_6, "NUM+7": Qt.Key.Key_7, "NUM+8": Qt.Key.Key_8,
    "NUM+9": Qt.Key.Key_9,
    "NUMPAD0": Qt.Key.Key_0, "NUMPAD1": Qt.Key.Key_1,
    "NUM+ENTER": Qt.Key.Key_Enter,
    "DELETE": Qt.Key.Key_Delete,
    "PAUSE": Qt.Key.Key_Pause,
}

class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        app_instance = QApplication.instance()
        if app_instance: debug("APP_STATUS: Requesting QApplication.quit()."); QApplication.quit()

APP_STATUS = AppStatus()

_qt_keys_pressed_snapshot: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]] = []


class JoystickPollingThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        info("JoystickPollingThread: Started.")
        while self.running:
            if hasattr(joystick_handler, 'poll_joysticks_and_update_globals') and callable(joystick_handler.poll_joysticks_and_update_globals):
                try:
                    joystick_handler.poll_joysticks_and_update_globals()
                except Exception as e_poll:
                    warning(f"JoystickPollingThread: Error polling 'inputs' joystick_handler: {e_poll}")
            self.msleep(16)
        info("JoystickPollingThread: Stopped.")

    def stop(self):
        self.running = False
        info("JoystickPollingThread: Stop requested.")


class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float)
    operation_finished_signal = Signal(str)
    client_fully_synced_signal = Signal() # New signal for host mode

    def __init__(self, mode: str, game_elements_ref: Dict[str, Any], server_state_ref: Optional[ServerState] = None, client_state_ref: Optional[ClientState] = None, target_ip_port: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.mode = mode; self.game_elements = game_elements_ref; self.server_state = server_state_ref; self.client_state = client_state_ref; self.target_ip_port = target_ip_port
    def _ui_status_update_callback(self, title: str, message: str, progress: float): self.status_update_signal.emit(title, message, progress)
    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any, platforms_list: List[Any]) -> Dict[str, bool]: return {}

    def run(self):
        try:
            main_window_instance = MainWindow._instance
            if self.mode == "host" and self.server_state and main_window_instance: # Changed from "host_pre_game" to "host"
                info("NetworkThread: Starting run_server_mode (will handle pre-game and active game)...")
                # Pass the client_fully_synced_signal emitter to run_server_mode
                run_server_mode(
                    self.server_state,
                    self.game_elements,
                    self._ui_status_update_callback,
                    main_window_instance.get_p1_input_snapshot_for_server_thread,
                    lambda: QApplication.processEvents(),
                    lambda: self.client_fully_synced_signal.emit() # Callback for when client is ready
                )
                info("NetworkThread: run_server_mode finished."); self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state and main_window_instance:
                info("NetworkThread: Starting run_client_mode...")
                run_client_mode(self.client_state, self.game_elements, self._ui_status_update_callback, self.target_ip_port, main_window_instance.get_p2_input_snapshot_for_client_thread, lambda: QApplication.processEvents())
                info("NetworkThread: run_client_mode finished."); self.operation_finished_signal.emit("client_ended")
        except Exception as e_thread: critical(f"NetworkThread: Exception in {self.mode} mode: {e_thread}", exc_info=True); self.operation_finished_signal.emit(f"{self.mode}_error")


class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object)

    actual_editor_module_instance: Optional[Any] = None
    actual_controls_module_instance: Optional[Any] = None
    joystick_poll_thread: Optional[JoystickPollingThread] = None

    _pygame_joysticks: List[pygame.joystick.Joystick]
    _menu_selected_button_idx: int
    _map_selection_selected_button_idx: int
    _lan_search_list_selected_idx: int
    _ip_dialog_selected_button_idx: int
    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: bool
    _pygame_joy_axis_was_active_pos: bool
    _main_menu_buttons_ref: List[QPushButton]
    _map_selection_buttons_ref: List[QPushButton]
    _ip_dialog_buttons_ref: List[QPushButton]
    _current_active_menu_buttons: List[QPushButton]
    _current_active_menu_selected_idx_ref: str
    map_select_scroll_area: Optional[QScrollArea] = None
    current_modal_dialog: Optional[str] = None

    _prev_menu_confirm_pressed: bool
    _prev_menu_cancel_pressed: bool
    _prev_lan_confirm_pressed: bool
    _prev_lan_cancel_pressed: bool
    _prev_lan_retry_pressed: bool
    _prev_ip_dialog_confirm_pressed: bool
    _prev_ip_dialog_cancel_pressed: bool


    NUM_MAP_COLUMNS = 3

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN")

        try:
            pygame.init(); pygame.joystick.init()
            self._pygame_joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
            if self._pygame_joysticks: info(f"MAIN PySide6: Pygame found {len(self._pygame_joysticks)} joysticks."); [j.init() for j in self._pygame_joysticks]; [info(f"  - Pygame Joystick: {j.get_name()}") for j in self._pygame_joysticks]
            else: info("MAIN PySide6: Pygame found no joysticks.")
        except pygame.error as e: warning(f"MAIN PySide6: Pygame joystick init error: {e}."); self._pygame_joysticks = []

        self._menu_selected_button_idx = 0; self._map_selection_selected_button_idx = 0; self._lan_search_list_selected_idx = 0; self._ip_dialog_selected_button_idx = 0
        self._last_pygame_joy_nav_time = 0.0; self._pygame_joy_axis_was_active_neg = False; self._pygame_joy_axis_was_active_pos = False
        self._main_menu_buttons_ref = []; self._map_selection_buttons_ref = []; self._ip_dialog_buttons_ref = []
        self._current_active_menu_buttons = self._main_menu_buttons_ref; self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"
        self._prev_menu_confirm_pressed = False; self._prev_menu_cancel_pressed = False
        self._prev_lan_confirm_pressed = False; self._prev_lan_cancel_pressed = False; self._prev_lan_retry_pressed = False
        self._prev_ip_dialog_confirm_pressed = False; self._prev_ip_dialog_cancel_pressed = False

        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.initial_main_window_width = max(800, min(int(screen_geo.width() * 0.75), 1600))
        self.initial_main_window_height = max(600, min(int(screen_geo.height() * 0.75), 900))
        self.setMinimumSize(QSize(800,600)); self.resize(self.initial_main_window_width, self.initial_main_window_height)
        info(f"MAIN PySide6: Initial window size: {self.size().width()}x{self.size().height()}")
        self.fonts = {"small": QFont("Arial", 10), "medium": QFont("Arial", 14), "large": QFont("Arial", 24, QFont.Weight.Bold), "debug": QFont("Monospace", 9)}

        try:
            if hasattr(joystick_handler, 'init_joysticks') and callable(joystick_handler.init_joysticks):
                if not joystick_handler.init_joysticks(): warning("MAIN PySide6: 'inputs' joystick_handler failed to initialize.")
                else: info("MAIN PySide6: 'inputs' joystick_handler initialized.")
            else: warning("MAIN PySide6: 'joystick_handler' module missing 'init_joysticks'.")
            game_config.load_config(); self._translate_config_key_mappings()
        except AttributeError as e_attr: critical(f"Error during 'inputs' joystick/config init: {e_attr} (Likely 'joystick_handler' API issue)", exc_info=True); self._handle_config_load_failure()
        except Exception as e_cfg: critical(f"Error during general config init: {e_cfg}", exc_info=True); self._handle_config_load_failure()

        self.app_status = APP_STATUS; self.game_elements: Dict[str, Any] = {}; self.current_view_name: Optional[str] = None; self.current_game_mode: Optional[str] = None
        self.server_state: Optional[ServerState] = None; self.client_state: Optional[ClientState] = None; self.network_thread: Optional[NetworkThread] = None; self.lan_search_dialog: Optional[QDialog] = None

        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = self._create_main_menu_widget()
        self.map_select_widget = self._create_map_select_widget() # Renamed for clarity
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)
        self.editor_content_container = QWidget(); self.editor_content_container.setLayout(QVBoxLayout()); self.editor_content_container.layout().setContentsMargins(0,0,0,0)
        self.controls_content_container = QWidget(); self.controls_content_container.setLayout(QVBoxLayout()); self.controls_content_container.layout().setContentsMargins(0,0,0,0)
        self.editor_view_page = self._create_view_page_with_back_button("Level Editor", self.editor_content_container, self.on_return_to_menu_from_sub_view)
        self.settings_view_page = self._create_view_page_with_back_button("Settings/Controls", self.controls_content_container, self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget); self.stacked_widget.addWidget(self.map_select_widget); self.stacked_widget.addWidget(self.game_scene_widget)
        self.stacked_widget.addWidget(self.editor_view_page); self.stacked_widget.addWidget(self.settings_view_page)
        self.setCentralWidget(self.stacked_widget); self.show_view("menu")

        self.network_status_update.connect(self.on_network_status_update); self.lan_server_search_status.connect(self.on_lan_server_search_status_update)
        self.status_dialog: Optional[QDialog] = None; self.status_label_in_dialog: Optional[QLabel] = None; self.status_progress_bar_in_dialog: Optional[QProgressBar] = None
        self.joystick_poll_thread = JoystickPollingThread(self); self.joystick_poll_thread.start()
        self.game_update_timer = QTimer(self); self.game_update_timer.timeout.connect(self.update_game_loop); self.game_update_timer.start(1000 // C.FPS)

    def _handle_config_load_failure(self):
        warning("MAIN PySide6: Attempting to load config or translate mappings even after 'inputs' joystick_handler failure.")
        try:
            if not hasattr(game_config, 'P1_MAPPINGS'): # Check if config was loaded at all
                game_config.load_config() # This might re-raise if underlying issue persists
            self._translate_config_key_mappings()
        except Exception as e_cfg_fallback:
            critical(f"Error during fallback game_config.load_config() or _translate_config_key_mappings(): {e_cfg_fallback}", exc_info=True)
            QMessageBox.critical(self, "Config Error", "Failed to load critical game configurations. Application might not work correctly.")

    def _create_view_page_with_back_button(self, title_text: str, content_widget_to_embed: QWidget, back_slot: Slot) -> QWidget:
        page_widget = QWidget(); page_layout = QVBoxLayout(page_widget); page_layout.setContentsMargins(10,10,10,10); page_layout.setSpacing(10)
        title_label = QLabel(title_text); title_label.setFont(self.fonts["large"]); title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); page_layout.addWidget(title_label)
        page_layout.addWidget(content_widget_to_embed, 1)
        back_button = QPushButton("Back to Main Menu"); back_button.setFont(self.fonts["medium"]); back_button.setMinimumHeight(40); back_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed); back_button.clicked.connect(back_slot)
        button_layout_wrapper = QHBoxLayout(); button_layout_wrapper.addStretch(); button_layout_wrapper.addWidget(back_button); button_layout_wrapper.addStretch(); page_layout.addLayout(button_layout_wrapper)
        return page_widget

    def _create_map_select_widget(self) -> QWidget: # Renamed from _create_couch_coop_map_select_widget
        from PySide6.QtWidgets import QGridLayout
        page_widget = QWidget()
        main_layout = QVBoxLayout(page_widget); main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.setSpacing(10)
        self.map_select_title_label = QLabel("Select Map") # Generic title
        self.map_select_title_label.setFont(self.fonts["large"]); self.map_select_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(self.map_select_title_label)
        self.map_select_scroll_area = QScrollArea(); self.map_select_scroll_area.setWidgetResizable(True)
        self.map_select_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.map_select_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.map_buttons_container = QWidget()
        self.map_buttons_layout = QGridLayout(self.map_buttons_container); self.map_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter); self.map_buttons_layout.setSpacing(10)
        self.map_select_scroll_area.setWidget(self.map_buttons_container); main_layout.addWidget(self.map_select_scroll_area, 1)
        back_button = QPushButton("Back to Main Menu"); back_button.setFont(self.fonts["medium"]); back_button.setMinimumHeight(40); back_button.setMinimumWidth(250); back_button.clicked.connect(lambda: self.show_view("menu"))
        button_layout_wrapper = QHBoxLayout(); button_layout_wrapper.addStretch(); button_layout_wrapper.addWidget(back_button); button_layout_wrapper.addStretch(); main_layout.addLayout(button_layout_wrapper)
        return page_widget

    def _populate_map_list_for_selection(self, purpose: str): # 'couch_coop' or 'host_game'
        from PySide6.QtWidgets import QGridLayout # Ensure import
        if not isinstance(self.map_buttons_layout, QGridLayout):
            error("Map buttons layout is not QGridLayout in _populate_map_list_for_selection"); return
        while self.map_buttons_layout.count():
            child = self.map_buttons_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self._map_selection_buttons_ref.clear()
        maps_dir = getattr(C, "MAPS_DIR", "maps")
        if not os.path.isabs(maps_dir): maps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), maps_dir)
        available_maps = []
        if os.path.exists(maps_dir) and os.path.isdir(maps_dir):
            try:
                map_files = sorted([f[:-3] for f in os.listdir(maps_dir) if f.endswith(".py") and f != "__init__.py" and f[:-3] != "level_default"])
                prio = ["original", "lava", "cpu_extended", "noenemy", "bigmap1"]
                available_maps = [m for m in prio if m in map_files] + [m for m in map_files if m not in prio]
            except OSError as e: self.map_buttons_layout.addWidget(QLabel(f"Error: {e}"),0,0,1,self.NUM_MAP_COLUMNS); return
        else: self.map_buttons_layout.addWidget(QLabel(f"Maps dir not found: {maps_dir}"),0,0,1,self.NUM_MAP_COLUMNS); return
        if not available_maps: self.map_buttons_layout.addWidget(QLabel("No maps found."),0,0,1,self.NUM_MAP_COLUMNS); return

        for idx, map_name in enumerate(available_maps):
            button = QPushButton(map_name.replace("_", " ").title())
            button.setFont(self.fonts["medium"]); button.setMinimumHeight(40); button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if purpose == "couch_coop": button.clicked.connect(lambda checked=False, mn=map_name: self._on_map_selected_for_couch_coop(mn))
            elif purpose == "host_game": button.clicked.connect(lambda checked=False, mn=map_name: self._on_map_selected_for_host_game(mn))
            row, col = divmod(idx, self.NUM_MAP_COLUMNS)
            self.map_buttons_layout.addWidget(button, row, col)
            self._map_selection_buttons_ref.append(button)

    def _on_map_selected_for_couch_coop(self, map_name: str):
        info(f"Map '{map_name}' selected for Couch Co-op."); self._prepare_and_start_game("couch_play", map_name=map_name)
    def _on_map_selected_for_host_game(self, map_name: str):
        info(f"Map '{map_name}' selected for Hosting."); self._prepare_and_start_game("host_waiting", map_name=map_name) # Start in waiting mode

    def _create_main_menu_widget(self) -> QWidget:
        self._main_menu_buttons_ref = []
        menu_widget = QWidget(); layout = QVBoxLayout(menu_widget); layout.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.setSpacing(15)
        title_label = QLabel("Platformer Adventure LAN"); title_label.setFont(self.fonts["large"]); title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title_label)
        buttons_data = [
            ("Couch Co-op", self.on_start_couch_play), ("Host Game", self.on_start_host_game),
            ("Join LAN Game", self.on_start_join_lan), ("Join by IP", self.on_start_join_ip),
            ("Level Editor", lambda: self.show_view("editor")), ("Settings/Controls", lambda: self.show_view("settings")),
            ("Quit", self.request_close_app)
        ]
        for text, slot_func in buttons_data:
            button = QPushButton(text); button.setFont(self.fonts["medium"]); button.setMinimumHeight(40)
            button.setMinimumWidth(250); button.clicked.connect(slot_func); layout.addWidget(button)
            self._main_menu_buttons_ref.append(button)
        return menu_widget

    def _update_current_menu_button_focus(self):
        buttons_to_update = self._current_active_menu_buttons
        selected_idx_attr_name = self._current_active_menu_selected_idx_ref
        if not buttons_to_update or not hasattr(self, selected_idx_attr_name): return
        current_selected_idx = getattr(self, selected_idx_attr_name)
        selected_button_widget = None
        for i, button in enumerate(buttons_to_update):
            is_selected = (i == current_selected_idx)
            if is_selected:
                button.setStyleSheet("QPushButton { border: 2px solid yellow; background-color: #555; color: white; } QPushButton:focus { outline: none; }")
                button.setFocus(Qt.FocusReason.OtherFocusReason); selected_button_widget = button
            else: button.setStyleSheet("")
        if selected_button_widget and self.current_view_name == "map_select" and self.map_select_scroll_area:
            self.map_select_scroll_area.ensureWidgetVisible(selected_button_widget, 50, 50) # Ensure 50px margin

    def _navigate_current_menu_pygame_joy(self, direction: int):
        buttons_to_nav = self._current_active_menu_buttons
        selected_idx_attr_name = self._current_active_menu_selected_idx_ref
        if not buttons_to_nav or not hasattr(self, selected_idx_attr_name): return
        num_buttons = len(buttons_to_nav)
        if num_buttons == 0: return
        current_idx = getattr(self, selected_idx_attr_name)
        if self.current_view_name == "map_select": # Grid navigation
            row, col = divmod(current_idx, self.NUM_MAP_COLUMNS)
            if direction == -1 : # Up
                row = max(0, row - 1)
            elif direction == 1: # Down
                row = min((num_buttons - 1) // self.NUM_MAP_COLUMNS, row + 1)
            elif direction == -2: # Left
                col = max(0, col - 1)
            elif direction == 2: # Right
                col = min(self.NUM_MAP_COLUMNS - 1, col + 1)
            new_idx = row * self.NUM_MAP_COLUMNS + col
            new_idx = min(num_buttons - 1, max(0, new_idx)) # Clamp
        else: # Linear navigation
            new_idx = (current_idx + direction + num_buttons) % num_buttons
        setattr(self, selected_idx_attr_name, new_idx)
        self._update_current_menu_button_focus()
        info(f"Menu Joystick: Navigated to button index {new_idx} in view '{self.current_view_name}'")

    def _activate_current_menu_selected_button_pygame_joy(self):
        buttons_to_activate = self._current_active_menu_buttons
        selected_idx_attr_name = self._current_active_menu_selected_idx_ref
        if not buttons_to_activate or not hasattr(self, selected_idx_attr_name): return
        current_idx = getattr(self, selected_idx_attr_name)
        if not (0 <= current_idx < len(buttons_to_activate)): return
        selected_button = buttons_to_activate[current_idx]
        info(f"Menu Joystick: Activating button '{selected_button.text()}' in view '{self.current_view_name}'")
        selected_button.click()

    def _poll_pygame_joysticks_for_ui_navigation(self):
        active_ui_element = self.current_view_name
        if self.current_modal_dialog: active_ui_element = self.current_modal_dialog
        if active_ui_element not in ["menu", "map_select", "lan_search", "ip_input"] or not self._pygame_joysticks:
            self._prev_menu_confirm_pressed = False; self._prev_menu_cancel_pressed = False
            self._prev_lan_confirm_pressed = False; self._prev_lan_cancel_pressed = False; self._prev_lan_retry_pressed = False
            self._prev_ip_dialog_confirm_pressed = False; self._prev_ip_dialog_cancel_pressed = False
            return
        pygame.event.pump(); joy = self._pygame_joysticks[0]
        JOY_NAV_AXIS_ID = 1; JOY_NAV_HAT_ID = 0
        current_time = time.monotonic()
        if current_time - self._last_pygame_joy_nav_time < 0.22: return
        confirm_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("menu_confirm")
        cancel_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("menu_cancel")
        
        # Hat Navigation (Up/Down/Left/Right)
        if joy.get_numhats() > JOY_NAV_HAT_ID:
            hat_x, hat_y = joy.get_hat(JOY_NAV_HAT_ID); navigated_by_hat = False
            if active_ui_element in ["menu", "map_select", "lan_search"]:
                if hat_y > 0.5: self._navigate_current_menu_pygame_joy(1); navigated_by_hat = True       # Down
                elif hat_y < -0.5: self._navigate_current_menu_pygame_joy(-1); navigated_by_hat = True    # Up
            if active_ui_element == "map_select" or (active_ui_element == "ip_input" and self._ip_dialog_buttons_ref):
                if hat_x > 0.5: self._navigate_current_menu_pygame_joy(2); navigated_by_hat = True     # Right
                elif hat_x < -0.5: self._navigate_current_menu_pygame_joy(-2); navigated_by_hat = True  # Left
            if navigated_by_hat: self._last_pygame_joy_nav_time = current_time; self._reset_prev_press_flags(); return

        # Axis Navigation (Up/Down/Left/Right)
        nav_threshold = 0.65; navigated_by_axis = False
        if joy.get_numaxes() > JOY_NAV_AXIS_ID: # Vertical axis (usually Y)
            axis_y_val = joy.get_axis(JOY_NAV_AXIS_ID)
            if active_ui_element in ["menu", "map_select", "lan_search"]:
                if axis_y_val > nav_threshold:
                    if not self._pygame_joy_axis_was_active_pos: self._navigate_current_menu_pygame_joy(1); navigated_by_axis = True
                    self._pygame_joy_axis_was_active_pos = True
                else: self._pygame_joy_axis_was_active_pos = False
                if axis_y_val < -nav_threshold:
                    if not self._pygame_joy_axis_was_active_neg: self._navigate_current_menu_pygame_joy(-1); navigated_by_axis = True
                    self._pygame_joy_axis_was_active_neg = True
                else: self._pygame_joy_axis_was_active_neg = False
        if joy.get_numaxes() > 0: # Horizontal axis (usually X, ID 0)
             axis_x_val = joy.get_axis(0)
             if active_ui_element == "map_select" or (active_ui_element == "ip_input" and self._ip_dialog_buttons_ref):
                if axis_x_val > nav_threshold:
                    # Assuming axis 0, positive direction has not been continuously active for this specific purpose
                    # This needs more state if mixing axis for up/down and left/right on same stick
                    self._navigate_current_menu_pygame_joy(2); navigated_by_axis = True 
                elif axis_x_val < -nav_threshold:
                    self._navigate_current_menu_pygame_joy(-2); navigated_by_axis = True
        if navigated_by_axis: self._last_pygame_joy_nav_time = current_time; self._reset_prev_press_flags(); return


        # Confirm/Cancel Button Actions
        confirm_held = False; cancel_held = False
        if confirm_mapping and confirm_mapping.get("type") == "button":
            btn_id = confirm_mapping.get("id"); confirm_held = joy.get_numbuttons() > btn_id and joy.get_button(btn_id)
        if cancel_mapping and cancel_mapping.get("type") == "button":
            btn_id = cancel_mapping.get("id"); cancel_held = joy.get_numbuttons() > btn_id and joy.get_button(btn_id)

        prev_confirm_flag_attr = f"_prev_{active_ui_element}_confirm_pressed" if active_ui_element != "menu" and active_ui_element != "map_select" else "_prev_menu_confirm_pressed"
        prev_cancel_flag_attr = f"_prev_{active_ui_element}_cancel_pressed" if active_ui_element != "menu" and active_ui_element != "map_select" else "_prev_menu_cancel_pressed"

        if confirm_held and not getattr(self, prev_confirm_flag_attr, False):
            if active_ui_element in ["menu", "map_select"]: self._activate_current_menu_selected_button_pygame_joy()
            elif active_ui_element == "lan_search": self._join_selected_lan_server_from_dialog()
            elif active_ui_element == "ip_input": self._activate_ip_dialog_button()
            self._last_pygame_joy_nav_time = current_time; setattr(self, prev_confirm_flag_attr, True); self._reset_other_prev_press_flags(prev_confirm_flag_attr); return
        if not confirm_held: setattr(self, prev_confirm_flag_attr, False)

        if cancel_held and not getattr(self, prev_cancel_flag_attr, False):
            if active_ui_element == "menu": self.request_close_app()
            elif active_ui_element == "map_select": self.show_view("menu")
            elif active_ui_element == "lan_search" and self.lan_search_dialog: self.lan_search_dialog.reject()
            elif active_ui_element == "ip_input" and self.ip_input_dialog: self.ip_input_dialog.reject()
            self._last_pygame_joy_nav_time = current_time; setattr(self, prev_cancel_flag_attr, True); self._reset_other_prev_press_flags(prev_cancel_flag_attr); return
        if not cancel_held: setattr(self, prev_cancel_flag_attr, False)
        
        # Retry for LAN search (Example: map to a different button if needed)
        if active_ui_element == "lan_search":
            retry_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("reset") # Example: Using 'reset' action for retry
            retry_held = False
            if retry_mapping and retry_mapping.get("type") == "button":
                btn_id = retry_mapping.get("id"); retry_held = joy.get_numbuttons() > btn_id and joy.get_button(btn_id)
            if retry_held and not self._prev_lan_retry_pressed:
                if self.lan_search_dialog and hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).click()
                self._last_pygame_joy_nav_time = current_time; self._prev_lan_retry_pressed = True; self._reset_other_prev_press_flags("_prev_lan_retry_pressed"); return
            if not retry_held: self._prev_lan_retry_pressed = False
    
    def _reset_prev_press_flags(self):
        self._prev_menu_confirm_pressed = False; self._prev_menu_cancel_pressed = False
        self._prev_lan_confirm_pressed = False; self._prev_lan_cancel_pressed = False; self._prev_lan_retry_pressed = False
        self._prev_ip_dialog_confirm_pressed = False; self._prev_ip_dialog_cancel_pressed = False

    def _reset_other_prev_press_flags(self, just_pressed_flag_name: str):
        flags_to_reset = ["_prev_menu_confirm_pressed", "_prev_menu_cancel_pressed",
                          "_prev_lan_confirm_pressed", "_prev_lan_cancel_pressed", "_prev_lan_retry_pressed",
                          "_prev_ip_dialog_confirm_pressed", "_prev_ip_dialog_cancel_pressed"]
        for flag_name in flags_to_reset:
            if flag_name != just_pressed_flag_name:
                setattr(self, flag_name, False)

    def _activate_ip_dialog_button(self):
        if self.ip_input_dialog and self._ip_dialog_buttons_ref:
            if 0 <= self._ip_dialog_selected_button_idx < len(self._ip_dialog_buttons_ref):
                self._ip_dialog_buttons_ref[self._ip_dialog_selected_button_idx].click()

    def request_close_app(self): info("MAIN PySide6: Quit action triggered from UI."); self.close()

    def on_return_to_menu_from_sub_view(self):
        source_view = self.current_view_name; info(f"Returning to menu from: {source_view}"); should_return = True
        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"): should_return = False
            if should_return and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state') and callable(self.actual_editor_module_instance.save_geometry_and_state): self.actual_editor_module_instance.save_geometry_and_state()
            if should_return and self.actual_editor_module_instance.parent() is not None: self.actual_editor_module_instance.setParent(None)
        elif source_view == "settings" and self.actual_controls_module_instance:
            if should_return and self.actual_controls_module_instance.parent() is not None: self.actual_controls_module_instance.setParent(None)
        if should_return: self.show_view("menu")
        else: info("Return to menu cancelled by sub-view.")

    def show_view(self, view_name: str):
        info(f"Switching UI view to: {view_name}")
        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode: self.stop_current_game_mode(show_menu=False)
        self.current_view_name = view_name; target_page: Optional[QWidget] = None; title = "Platformer Adventure LAN"
        self.current_modal_dialog = None # Clear modal dialog context when switching main views

        if view_name == "menu": target_page = self.main_menu_widget; title += " - Main Menu"; self._current_active_menu_buttons = self._main_menu_buttons_ref; self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"; self._menu_selected_button_idx = 0
        elif view_name == "map_select": # Generic map select view
            target_page = self.map_select_widget;
            # Title and purpose set by caller (on_start_couch_play or on_start_host_game)
            self._current_active_menu_buttons = self._map_selection_buttons_ref; self._current_active_menu_selected_idx_ref = "_map_selection_selected_button_idx"; self._map_selection_selected_button_idx = 0
        elif view_name == "game_scene": target_page = self.game_scene_widget; title += f" - {self.current_game_mode.replace('_',' ').title() if self.current_game_mode else 'Game'}"; self._current_active_menu_buttons = []
        elif view_name == "editor": self._ensure_editor_instance(); target_page = self.editor_view_page; title += " - Level Editor"; self._current_active_menu_buttons = []
        elif view_name == "settings": self._ensure_controls_mapper_instance(); target_page = self.settings_view_page; title += " - Settings/Controls"; self._current_active_menu_buttons = []
        
        if target_page:
            self.stacked_widget.setCurrentWidget(target_page); self.setWindowTitle(title)
            if view_name in ["menu", "map_select"]: self._update_current_menu_button_focus()
            focus_target = target_page
            if view_name == "editor" and self.actual_editor_module_instance: focus_target = self.actual_editor_module_instance
            elif view_name == "settings" and self.actual_controls_module_instance: focus_target = self.actual_controls_module_instance
            focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to menu."); self.stacked_widget.setCurrentWidget(self.main_menu_widget)
            self.setWindowTitle("Platformer Adventure LAN - Main Menu"); self._current_active_menu_buttons = self._main_menu_buttons_ref
            self._current_active_menu_selected_idx_ref = "_menu_selected_button_idx"; self._menu_selected_button_idx = 0
            self._update_current_menu_button_focus(); self.main_menu_widget.setFocus()
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame; _qt_keys_pressed_snapshot.clear(); _qt_key_events_this_frame.clear()

    def keyPressEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame; is_auto_repeat = event.isAutoRepeat(); qt_key_enum = Qt.Key(event.key())
        if not is_auto_repeat: _qt_keys_pressed_snapshot[qt_key_enum] = True; _qt_key_events_this_frame.append((QKeyEvent.Type.KeyPress, qt_key_enum, is_auto_repeat))
        
        active_ui_element = self.current_modal_dialog if self.current_modal_dialog else self.current_view_name
        
        if active_ui_element in ["menu", "map_select"] and not is_auto_repeat:
            if event.key() == Qt.Key.Key_Up: self._navigate_current_menu_pygame_joy(-1); event.accept(); return
            elif event.key() == Qt.Key.Key_Down: self._navigate_current_menu_pygame_joy(1); event.accept(); return
            elif event.key() == Qt.Key.Key_Left and active_ui_element == "map_select": self._navigate_current_menu_pygame_joy(-2); event.accept(); return # Grid left
            elif event.key() == Qt.Key.Key_Right and active_ui_element == "map_select": self._navigate_current_menu_pygame_joy(2); event.accept(); return # Grid right
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: self._activate_current_menu_selected_button_pygame_joy(); event.accept(); return
        elif active_ui_element == "lan_search" and not is_auto_repeat:
            if event.key() == Qt.Key.Key_Up: self._lan_search_list_selected_idx = max(0, self._lan_search_list_selected_idx - 1); self._update_lan_search_list_focus(); event.accept(); return
            elif event.key() == Qt.Key.Key_Down: self._lan_search_list_selected_idx = min(self.lan_servers_list_widget.count() - 1, self._lan_search_list_selected_idx + 1); self._update_lan_search_list_focus(); event.accept(); return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]: self._join_selected_lan_server_from_dialog(); event.accept(); return
        elif active_ui_element == "ip_input" and not is_auto_repeat:
            if event.key() in [Qt.Key.Key_Left, Qt.Key.Key_Right]:
                self._ip_dialog_selected_button_idx = 1 - self._ip_dialog_selected_button_idx # Toggle 0 and 1
                self._update_ip_dialog_button_focus(); event.accept(); return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                self._activate_ip_dialog_button(); event.accept(); return
        
        if event.key() == Qt.Key.Key_Escape and not is_auto_repeat:
            if active_ui_element == "menu": self.request_close_app()
            elif active_ui_element == "map_select": self.show_view("menu")
            elif active_ui_element == "lan_search" and self.lan_search_dialog: self.lan_search_dialog.reject()
            elif active_ui_element == "ip_input" and self.ip_input_dialog: self.ip_input_dialog.reject()
            elif self.current_view_name in ["editor", "settings"]: self.on_return_to_menu_from_sub_view()
            elif self.current_view_name == "game_scene" and self.current_game_mode: info(f"Escape in game mode '{self.current_game_mode}'. Stopping."); self.stop_current_game_mode(show_menu=True)
            event.accept(); return
        if not event.isAccepted(): super().keyPressEvent(event)

    # ... (rest of methods like keyReleaseEvent, _get_input_snapshot, etc. mostly unchanged but review them for current_modal_dialog if needed) ...

    def _get_input_snapshot(self, player_instance: Player, player_id: int) -> Dict[str, bool]:
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        if not player_instance or not hasattr(player_instance, '_valid_init') or not player_instance._valid_init: warning(f"_get_input_snapshot: Invalid player_instance for player_id {player_id}."); return {}
        active_mappings = {}; joystick_pygame_idx_for_player: Optional[int] = None
        player_device_str = game_config.CURRENT_P1_INPUT_DEVICE if player_id == 1 else game_config.CURRENT_P2_INPUT_DEVICE
        active_mappings = game_config.P1_MAPPINGS if player_id == 1 else game_config.P2_MAPPINGS
        if player_device_str.startswith("joystick_pygame_"):
            try: joystick_pygame_idx_for_player = int(player_device_str.split('_')[-1])
            except (ValueError, IndexError): joystick_pygame_idx_for_player = None
        joystick_data_for_handler: Optional[Dict[str,Any]] = None
        if joystick_pygame_idx_for_player is not None and 0 <= joystick_pygame_idx_for_player < len(self._pygame_joysticks):
            joy = self._pygame_joysticks[joystick_pygame_idx_for_player]; pygame.event.pump() 
            current_buttons_state = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
            # TODO: Implement proper prev_buttons_state tracking for Pygame joysticks for "just pressed" events.
            # For now, player_input_handler needs to be robust or actions might fire continuously.
            joystick_data_for_handler = {
                'axes': {i: joy.get_axis(i) for i in range(joy.get_numaxes())},
                'buttons_current': current_buttons_state, 'buttons_prev': current_buttons_state, 
                'hats': {i: joy.get_hat(i) for i in range(joy.get_numhats())}
            }
        platforms_list = self.game_elements.get("platforms_list", [])
        if not isinstance(platforms_list, list): platforms_list = []
        action_events = process_player_input_logic(player_instance, _qt_keys_pressed_snapshot, list(_qt_key_events_this_frame), active_mappings, platforms_list, joystick_data=joystick_data_for_handler)
        _qt_key_events_this_frame.clear(); return action_events

    @staticmethod
    def get_p1_input_snapshot_for_server_thread(player_instance: Any, platforms_list: List[Any]) -> Dict[str, Any]:
        if MainWindow._instance: return MainWindow._instance._get_input_snapshot(player_instance, 1)
        return {}
    @staticmethod
    def get_p2_input_snapshot_for_client_thread(player_instance: Any) -> Dict[str, Any]:
        platforms_list = []
        if MainWindow._instance and MainWindow._instance.game_elements: platforms_list = MainWindow._instance.game_elements.get("platforms_list", [])
        if MainWindow._instance: return MainWindow._instance._get_input_snapshot(player_instance, 2)
        return {}

    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
        main_window_size = self.size(); current_width, current_height = main_window_size.width(), main_window_size.height()
        if current_width <= 100 or current_height <= 100: current_width, current_height = self.initial_main_window_width, self.initial_main_window_height; info(f"Window size small, using defaults: {current_width}x{current_height}")
        else: info(f"Window size for game init: {current_width}x{current_height}")
        
        if map_name is None and mode != "join_ip" and mode != "join_lan": # join modes get map from server
             map_name = getattr(C, 'DEFAULT_LEVEL_MODULE_NAME', "level_default")

        initialized_elements = initialize_game_elements(current_width, current_height, mode, None, map_name if mode != "join_ip" and mode != "join_lan" else None)
        if initialized_elements is None: QMessageBox.critical(self, "Error", f"Failed to init game elements for {mode}, map '{map_name}'."); self.show_view("menu"); return
        self.game_elements.clear(); self.game_elements.update(initialized_elements); self.game_elements['current_game_mode'] = mode; self.current_game_mode = mode
        self.setWindowTitle(f"Platformer - {mode.replace('_',' ').title()}")
        
        camera = self.game_elements.get("camera")
        if camera and hasattr(camera, 'set_screen_dimensions') and hasattr(camera, 'set_level_dimensions'):
            game_scene_w = self.game_scene_widget.width(); game_scene_h = self.game_scene_widget.height()
            if game_scene_w <=1 or game_scene_h <=1 : game_scene_w = current_width; game_scene_h = current_height
            camera.set_screen_dimensions(float(game_scene_w), float(game_scene_h))
            if "level_pixel_width" in self.game_elements: camera.set_level_dimensions(self.game_elements["level_pixel_width"], self.game_elements.get("level_min_x_absolute", 0.0), self.game_elements.get("level_min_y_absolute", 0.0), self.game_elements.get("level_max_y_absolute", game_scene_h))
            p1_cam = self.game_elements.get("player1")
            if p1_cam and hasattr(camera, 'update'): camera.update(p1_cam)
        
        self.show_view("game_scene"); QApplication.processEvents(); self.game_scene_widget.update_game_state(0)
        
        if mode == "host_waiting": self._start_network_mode("host_listen_only") # Start server listening, but P1 plays locally
        elif mode in ["host", "join_lan", "join_ip"]: self._start_network_mode(mode, target_ip_port) # For direct join or if host transitions after client ready
        info(f"Game mode '{mode}' prepared.")

    @Slot()
    def on_client_fully_synced_for_host(self):
        info("MAIN: Client is fully synced with Host. Resetting game state for multiplayer.")
        if self.current_game_mode == "host_waiting":
            reset_game_state(self.game_elements) # game_setup.reset_game_state
            self.current_game_mode = "host" # Transition to active multiplayer host mode
            # The NetworkThread (run_server_mode) will now take over the full game simulation.
            # MainWindow's update_game_loop will no longer run local P1 logic for "host_waiting".
            info("MAIN: Game state reset. Host mode now active for multiplayer.")
            # Optionally update window title or UI elements here
            self.setWindowTitle(f"Platformer Adventure LAN - Host (Multiplayer)")
        else:
            warning("on_client_fully_synced_for_host called but not in 'host_waiting' mode.")

    def update_game_loop(self):
        self._poll_pygame_joysticks_for_ui_navigation()
        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            dt_sec = 1.0 / C.FPS 
            if not run_couch_play_mode(self.game_elements, self.app_status, lambda p, plat: self._get_input_snapshot(p, 1), lambda p, plat: self._get_input_snapshot(p, 2), lambda: QApplication.processEvents(), lambda: dt_sec, lambda msg: self.game_scene_widget.update_game_state(0, download_msg=msg)):
                self.stop_current_game_mode(show_menu=True)
        elif self.current_game_mode == "host_waiting" and self.app_status.app_running: # Host plays solo
            dt_sec = 1.0 / C.FPS
            # Simulate P1 only
            p1 = self.game_elements.get("player1")
            if p1:
                p1_actions = self._get_input_snapshot(p1, 1)
                if p1_actions.get("pause"): self.stop_current_game_mode(show_menu=True); return
                if p1_actions.get("reset"): reset_game_state(self.game_elements)

                # Simplified update for P1 only
                p1.update(dt_sec, self.game_elements.get("platforms_list", []), 
                          self.game_elements.get("ladders_list", []), 
                          self.game_elements.get("hazards_list", []), 
                          [], # No other players for P1 solo
                          self.game_elements.get("enemy_list", []))
                # Update enemies, items etc. if the host should interact with them solo
                active_players_for_ai = [p1] if p1.alive() else []
                for enemy in list(self.game_elements.get("enemy_list",[])): enemy.update(dt_sec, active_players_for_ai, self.game_elements.get("platforms_list",[]), self.game_elements.get("hazards_list",[]), self.game_elements.get("enemy_list",[])); #... prune dead enemies
                # ... update other game elements like projectiles, items, statues as needed for solo host play ...
                camera = self.game_elements.get("camera")
                if camera and p1.alive(): camera.update(p1)
        if self.current_view_name == "game_scene": self.game_scene_widget.update_game_state(0)

    def on_start_couch_play(self): self.map_select_title_label.setText("Select Map for Couch Co-op"); self._populate_map_list_for_selection("couch_coop"); self.show_view("map_select")
    def on_start_host_game(self): self.map_select_title_label.setText("Select Map to Host"); self._populate_map_list_for_selection("host_game"); self.show_view("map_select")

    def on_start_join_lan(self): self._show_lan_search_dialog()
    def on_start_join_ip(self):
        self.ip_input_dialog = IPInputDialog(parent=self) # Store reference
        self._ip_dialog_buttons_ref = [self.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok), self.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)]
        self._ip_dialog_selected_button_idx = 0
        self.current_modal_dialog = "ip_input"
        self._update_ip_dialog_button_focus()
        if self.ip_input_dialog.exec() == QDialog.DialogCode.Accepted and self.ip_input_dialog.ip_port_string:
            self._prepare_and_start_game("join_ip", target_ip_port=self.ip_input_dialog.ip_port_string)
        else: info("Join by IP cancelled or no IP entered."); self.show_view("menu")
        self.current_modal_dialog = None; self._ip_dialog_buttons_ref.clear()

    def _update_ip_dialog_button_focus(self):
        if not self.ip_input_dialog or not self._ip_dialog_buttons_ref: return
        for i, button in enumerate(self._ip_dialog_buttons_ref):
            is_selected = (i == self._ip_dialog_selected_button_idx)
            button.setStyleSheet("QPushButton { border: 2px solid yellow; background-color: #555; color: white; } QPushButton:focus { outline: none; }" if is_selected else "")
            if is_selected: button.setFocus(Qt.FocusReason.OtherFocusReason)
            
    def _select_map_dialog(self) -> Optional[str]: # Only for legacy "Host Game" if direct map selection is re-enabled
        dialog = SelectMapDialog(self.fonts, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: return dialog.selected_map_name
        return None

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        if self.network_thread and self.network_thread.isRunning(): warning("NetworkThread already running."); self.network_thread.quit(); self.network_thread.wait(1000); self.network_thread = None
        if mode_name == "host_listen_only": # For host waiting for client
            self.server_state = ServerState(); self.server_state.current_map_name = self.game_elements.get("loaded_map_name", "unknown_map")
            self.network_thread = NetworkThread("host", self.game_elements, self.server_state, parent=self) # NetworkThread runs full server logic
            self.network_thread.client_fully_synced_signal.connect(self.on_client_fully_synced_for_host) # Connect new signal
        elif mode_name == "host": # This would be after client already synced and game is reset
            # This case might not be directly called if logic transitions from host_waiting correctly
            if not self.server_state: self.server_state = ServerState(); self.server_state.current_map_name = self.game_elements.get("loaded_map_name", "unknown_map")
            self.network_thread = NetworkThread("host", self.game_elements, self.server_state, parent=self)
        elif mode_name in ["join_lan", "join_ip"]:
            self.client_state = ClientState(); self.network_thread = NetworkThread("join", self.game_elements, client_state_ref=self.client_state, target_ip_port=target_ip_port, parent=self)
        if self.network_thread:
            self.network_thread.status_update_signal.connect(self.on_network_status_update); self.network_thread.operation_finished_signal.connect(self.on_network_operation_finished)
            self.network_thread.start()
            if mode_name != "host_listen_only": # Don't show status dialog for host just listening
                self._show_status_dialog("Network Operation", f"Initializing {mode_name} mode...")
        else: error(f"Failed to create NetworkThread for {mode_name}"); QMessageBox.critical(self, "Network Error", f"Could not start {mode_name} mode."); self.show_view("menu")

    def _show_status_dialog(self, title: str, initial_message: str):
        if self.status_dialog is None:
            self.status_dialog = QDialog(self); self.status_dialog.setWindowTitle(title); layout = QVBoxLayout(self.status_dialog); self.status_label_in_dialog = QLabel(initial_message); self.status_label_in_dialog.setWordWrap(True); layout.addWidget(self.status_label_in_dialog)
            self.status_progress_bar_in_dialog = QProgressBar(); self.status_progress_bar_in_dialog.setRange(0,100); self.status_progress_bar_in_dialog.setTextVisible(True); layout.addWidget(self.status_progress_bar_in_dialog); self.status_dialog.setMinimumWidth(350)
        else: self.status_dialog.setWindowTitle(title)
        if self.status_label_in_dialog: self.status_label_in_dialog.setText(initial_message)
        if self.status_progress_bar_in_dialog: self.status_progress_bar_in_dialog.setValue(0); self.status_progress_bar_in_dialog.setVisible(False)
        self.status_dialog.show(); QApplication.processEvents()
    def _update_status_dialog(self, message: str, progress: float = -1.0):
        if self.status_dialog and self.status_dialog.isVisible():
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(message)
            if self.status_progress_bar_in_dialog:
                if 0 <= progress <= 100: self.status_progress_bar_in_dialog.setValue(int(progress)); self.status_progress_bar_in_dialog.setVisible(True)
                else: self.status_progress_bar_in_dialog.setVisible(False)
        QApplication.processEvents()
    def _close_status_dialog(self):
        if self.status_dialog: self.status_dialog.hide()
    @Slot(str, str, float)
    def on_network_status_update(self, title: str, message: str, progress: float):
        if not self.status_dialog or not self.status_dialog.isVisible():
             if self.current_game_mode == "host_waiting" and "Player 2 needs" in message: # Show dialog for host when client starts map sync
                self._show_status_dialog(title, message)
             elif self.current_game_mode != "host_waiting": # Show for other modes as before
                self._show_status_dialog(title, message)

        if self.status_dialog and self.status_dialog.isVisible(): # Update if visible
            self._update_status_dialog(message, progress)
        
        if title in ["game_starting", "game_active"] or (title == "Map Sync" and "Player 2 has" in message and "Ready" in message and progress >= 99.9):
             self._close_status_dialog() # Close when game is truly starting or map fully synced

    @Slot(str)
    def on_network_operation_finished(self, message: str):
        info(f"Network operation finished: {message}"); self._close_status_dialog()
        if "error" in message.lower() or "failed" in message.lower(): QMessageBox.critical(self, "Network Error", f"Network op error: {message}"); self.stop_current_game_mode(show_menu=True)
        elif "ended" in message.lower() and self.current_game_mode and self.current_game_mode != "host_waiting": # Don't stop host_waiting from here
            info(f"Mode {self.current_game_mode} finished via network signal."); self.stop_current_game_mode(show_menu=True)

    def _show_lan_search_dialog(self):
        if self.lan_search_dialog is None:
            self.lan_search_dialog = QDialog(self); self.lan_search_dialog.setWindowTitle("Searching for LAN Games..."); layout = QVBoxLayout(self.lan_search_dialog); self.lan_search_status_label = QLabel("Initializing search...")
            layout.addWidget(self.lan_search_status_label); self.lan_servers_list_widget = QListWidget(); self.lan_servers_list_widget.itemDoubleClicked.connect(self._join_selected_lan_server_from_dialog); layout.addWidget(self.lan_servers_list_widget)
            self.lan_search_dialog.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Join Selected"); self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            self.lan_search_dialog.button_box.accepted.connect(self._join_selected_lan_server_from_dialog); self.lan_search_dialog.button_box.rejected.connect(self.lan_search_dialog.reject)
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self._start_lan_server_search_thread); layout.addWidget(self.lan_search_dialog.button_box)
            self.lan_search_dialog.rejected.connect(lambda: (self.show_view("menu"), setattr(self, 'current_modal_dialog', None))); self.lan_search_dialog.setMinimumSize(400, 300)
        self.lan_servers_list_widget.clear(); self.lan_search_status_label.setText("Searching for LAN games..."); self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.current_modal_dialog = "lan_search"; self._lan_search_list_selected_idx = 0; self._update_lan_search_list_focus()
        self.lan_search_dialog.show(); self._start_lan_server_search_thread()

    def _update_lan_search_list_focus(self):
        if not self.lan_search_dialog or not self.lan_servers_list_widget: return
        if self.lan_servers_list_widget.count() > 0:
            self.lan_servers_list_widget.setCurrentRow(self._lan_search_list_selected_idx)
            selected_item = self.lan_servers_list_widget.item(self._lan_search_list_selected_idx)
            if selected_item: self.lan_servers_list_widget.scrollToItem(selected_item)
            if hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        elif hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _start_lan_server_search_thread(self):
        if hasattr(self, 'lan_search_worker') and self.lan_search_worker and self.lan_search_worker.isRunning(): warning("LAN search worker already running."); self.lan_search_worker.quit(); self.lan_search_worker.wait(500)
        if self.lan_servers_list_widget: self.lan_servers_list_widget.clear()
        if self.lan_search_status_label: self.lan_search_status_label.setText("Searching...")
        if self.lan_search_dialog and hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.lan_search_worker = QThread(self)
        class LanSearchRunner(QWidget):
            found_signal = Signal(object); search_finished_signal = Signal()
            def __init__(self, parent=None): super().__init__(parent); self.client_state_for_search = ClientState()
            @Slot()
            def run_search(self):
                info("LanSearchRunner: Starting find_server_on_lan.")
                try:
                    def cb(key: str, data: Any): self.found_signal.emit((key,data))
                    res = find_server_on_lan(self.client_state_for_search, cb)
                    self.found_signal.emit(("final_result", res))
                except Exception as e: critical(f"LanSearchRunner Error: {e}", exc_info=True); self.found_signal.emit(("error",f"Search failed: {e}"))
                finally: self.search_finished_signal.emit(); info("LanSearchRunner: run_search finished.")
        self.lan_search_run_obj = LanSearchRunner(); self.lan_search_run_obj.moveToThread(self.lan_search_worker)
        self.lan_search_worker.started.connect(self.lan_search_run_obj.run_search); self.lan_search_run_obj.found_signal.connect(self.on_lan_server_search_status_update)
        self.lan_search_worker.finished.connect(self.lan_search_worker.deleteLater); self.lan_search_run_obj.search_finished_signal.connect(self.lan_search_worker.quit)
        self.lan_search_run_obj.search_finished_signal.connect(self.lan_search_run_obj.deleteLater); self.lan_search_worker.start(); info("LAN server search thread started.")

    @Slot(object)
    def on_lan_server_search_status_update(self, data_tuple: Any):
        if not self.lan_search_dialog or not self.lan_search_dialog.isVisible(): info("LAN search status update received, but dialog is not visible. Ignoring."); return
        if not isinstance(data_tuple, tuple) or len(data_tuple) != 2: warning(f"Invalid data_tuple received in on_lan_server_search_status_update: {data_tuple}"); return
        status_key, data = data_tuple; debug(f"LAN Search Status: Key='{status_key}', Data='{str(data)[:100]}'")
        if self.lan_search_status_label: self.lan_search_status_label.setText(f"Status: {status_key}")
        if status_key == "found" and isinstance(data, tuple) and len(data)==2:
            ip, port = data; item_text = f"Server at {ip}:{port}"
            if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly): list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}"); self.lan_servers_list_widget.addItem(list_item)
            self._update_lan_search_list_focus() # Update focus potentially enabling OK
        elif status_key == "timeout" or status_key == "error" or (status_key == "final_result" and data is None and self.lan_servers_list_widget.count() == 0):
            if self.lan_servers_list_widget.count() == 0 and self.lan_search_status_label: self.lan_search_status_label.setText(f"Search {status_key}. No servers found.")
            self._update_lan_search_list_focus()
        elif status_key == "final_result" and data is not None:
             ip, port = data; item_text = f"Server at {ip}:{port} (Recommended)"
             if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly): list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}"); self.lan_servers_list_widget.addItem(list_item); self.lan_servers_list_widget.setCurrentItem(list_item)
             self._update_lan_search_list_focus()

    def _join_selected_lan_server_from_dialog(self):
        if not self.lan_servers_list_widget or not self.lan_search_dialog: warning("Attempt to join LAN server, but list widget or dialog is missing."); return
        selected_item = self.lan_servers_list_widget.currentItem() # Use currentItem for single selection lists
        if selected_item:
            ip_port_str = selected_item.data(Qt.ItemDataRole.UserRole)
            if ip_port_str and isinstance(ip_port_str, str):
                info(f"Joining selected LAN server: {ip_port_str}"); self.lan_search_dialog.accept(); self.current_modal_dialog = None
                self._prepare_and_start_game("join_lan", target_ip_port=ip_port_str); return
            else: warning(f"Selected LAN server item has invalid data: {ip_port_str}")
        QMessageBox.warning(self, "No Server Selected", "Please select a server from the list to join, or Cancel.")

    def stop_current_game_mode(self, show_menu: bool = True):
        mode_stopped = self.current_game_mode; info(f"Stopping game mode: {mode_stopped}")
        self.current_game_mode = None
        if self.network_thread and self.network_thread.isRunning():
            info("Requesting network thread to stop...")
            if self.server_state: self.server_state.app_running = False
            if self.client_state: self.client_state.app_running = False
            self.network_thread.quit()
            if not self.network_thread.wait(1500): warning("Network thread did not stop gracefully. Terminating."); self.network_thread.terminate(); self.network_thread.wait(500)
            info("Network thread stopped.")
        self.network_thread = None; self.server_state = None; self.client_state = None
        self._close_status_dialog()
        if self.lan_search_dialog and self.lan_search_dialog.isVisible(): self.lan_search_dialog.reject(); self.current_modal_dialog = None
        self.game_elements.clear(); self.game_scene_widget.update_game_state(0)
        if show_menu: self.show_view("menu")
        info(f"Game mode '{mode_stopped}' stopped and cleaned up.")

    def closeEvent(self, event: QCloseEvent):
        info("MAIN PySide6: Close event received. Initiating shutdown sequence.")
        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow):
                if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                    if not self.actual_editor_module_instance.confirm_unsaved_changes("exit the application"): can_close_editor = False
            if not can_close_editor: info("Editor prevented application close."); event.ignore(); return
            else:
                if hasattr(self.actual_editor_module_instance, 'save_geometry_and_state'): self.actual_editor_module_instance.save_geometry_and_state()
                self.actual_editor_module_instance.deleteLater(); self.actual_editor_module_instance = None; info("Editor instance scheduled for deletion.")
        if self.actual_controls_module_instance:
             if hasattr(self.actual_controls_module_instance, 'save_mappings'): self.actual_controls_module_instance.save_mappings()
             self.actual_controls_module_instance.deleteLater(); self.actual_controls_module_instance = None; info("Controls mapper instance scheduled for deletion.")
        self.app_status.quit_app(); self.stop_current_game_mode(show_menu=False)
        if self.joystick_poll_thread and self.joystick_poll_thread.isRunning():
            info("Stopping joystick polling thread..."); self.joystick_poll_thread.stop()
            if not self.joystick_poll_thread.wait(1000): warning("Joystick polling thread did not stop gracefully. Terminating."); self.joystick_poll_thread.terminate(); self.joystick_poll_thread.wait(100)
            info("Joystick polling thread stopped.")
        
        # Safely attempt to quit the 'inputs' library joystick_handler
        if hasattr(joystick_handler, 'quit_joysticks') and callable(joystick_handler.quit_joysticks):
            try: joystick_handler.quit_joysticks(); info("MAIN PySide6: 'inputs' joystick_handler.quit_joysticks() called.")
            except Exception as e_jq: warning(f"MAIN PySide6: Error calling 'inputs' joystick_handler.quit_joysticks(): {e_jq}")
        else: warning("MAIN PySide6: 'inputs' joystick_handler.quit_joysticks() not found or not callable.")
        
        pygame.joystick.quit(); pygame.quit()
        info("MAIN PySide6: Pygame quit.")
        info("MAIN PySide6: Application shutdown sequence complete. Accepting close event."); super().closeEvent(event)

def main():
    app = QApplication.instance()
    if app is None: app = QApplication(sys.argv)
    info("MAIN PySide6: Application starting...")
    main_window = MainWindow()
    main_window.showMaximized()
    exit_code = app.exec()
    info(f"MAIN PySide6: QApplication event loop finished. Exit code: {exit_code}")
    if APP_STATUS.app_running: APP_STATUS.app_running = False
    info("MAIN PySide6: Application fully terminated."); sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e_main_outer:
        if 'critical' in globals() and callable(critical) and _project_root: critical(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True)
        else: print(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}"); traceback.print_exc()
        try:
            error_app = QApplication.instance(); 
            if error_app is None: error_app = QApplication(sys.argv)
            msg_box = QMessageBox(); msg_box.setIcon(QMessageBox.Icon.Critical); msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")
            log_path_info_str = ""
            if LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH and os.path.exists(LOG_FILE_PATH): log_path_info_str = f"Please check the log file for details:\n{LOG_FILE_PATH}"
            elif LOGGING_ENABLED and 'LOG_FILE_PATH' in globals() and LOG_FILE_PATH: log_path_info_str = f"Log file configured at: {LOG_FILE_PATH} (may not exist or have details if error was early)."
            else: log_path_info_str = "Logging to file is disabled or path not set. Check console output."
            msg_box.setInformativeText(f"Error: {str(e_main_outer)[:1000]}\n\n{log_path_info_str}"); msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        except Exception as e_msgbox: print(f"FATAL: Could not display Qt error dialog: {e_msgbox}"); traceback.print_exc()
        sys.exit(1)