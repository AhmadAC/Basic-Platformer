import sys
import os
import traceback
import time
from typing import Dict, Optional, Any, List, Tuple

# PySide6 imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy
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
from game_setup import initialize_game_elements
from server_logic import ServerState, run_server_mode
from client_logic import ClientState, run_client_mode, find_server_on_lan
from couch_play_logic import run_couch_play_mode
from game_ui import GameSceneWidget, SelectMapDialog, IPInputDialog # game_ui.py will NOT use pygame for its UI elements
import config as game_config
import joystick_handler # This uses 'inputs' library, primarily for controller_mapper_gui
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


class JoystickPollingThread(QThread): # This thread might be less relevant if Pygame polling is in main timer
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        info("JoystickPollingThread: Started.")
        while self.running:
            # Removed: joystick_handler.poll_joysticks_and_update_globals()
            self.msleep(30) 
        info("JoystickPollingThread: Stopped.")

    def stop(self):
        self.running = False
        info("JoystickPollingThread: Stop requested.")


class NetworkThread(QThread):
    status_update_signal = Signal(str, str, float)
    operation_finished_signal = Signal(str)
    def __init__(self, mode: str, game_elements_ref: Dict[str, Any], server_state_ref: Optional[ServerState] = None, client_state_ref: Optional[ClientState] = None, target_ip_port: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.mode = mode; self.game_elements = game_elements_ref; self.server_state = server_state_ref; self.client_state = client_state_ref; self.target_ip_port = target_ip_port
    def _ui_status_update_callback(self, title: str, message: str, progress: float): self.status_update_signal.emit(title, message, progress)
    def _get_p1_input_snapshot_main_thread_passthrough(self, player_instance: Any, platforms_list: List[Any]) -> Dict[str, bool]: return {}
    
    def run(self):
        try:
            main_window_instance = MainWindow._instance
            if self.mode == "host" and self.server_state and main_window_instance:
                info("NetworkThread: Starting run_server_mode...")
                run_server_mode(self.server_state, self.game_elements, self._ui_status_update_callback, main_window_instance.get_p1_input_snapshot_for_server_thread, lambda: QApplication.processEvents())
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

    # Pygame joystick specific attributes for menu navigation
    _pygame_joysticks: List[pygame.joystick.Joystick]
    _menu_selected_button_idx: int
    _last_pygame_joy_nav_time: float
    _pygame_joy_axis_was_active_neg: bool
    _pygame_joy_axis_was_active_pos: bool
    _main_menu_buttons_ref: List[QPushButton] # To simulate clicks

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer")

        # Pygame initialization for joystick
        try:
            pygame.init() # Initialize all Pygame modules
            pygame.joystick.init() # Initialize only the joystick module
            self._pygame_joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
            if self._pygame_joysticks:
                info(f"MAIN PySide6: Pygame found {len(self._pygame_joysticks)} joysticks for menu navigation.")
                for joy in self._pygame_joysticks:
                    joy.init() # Initialize each joystick instance
                    info(f"  - Pygame Joystick: {joy.get_name()}")
            else:
                info("MAIN PySide6: Pygame found no joysticks for menu navigation.")
        except pygame.error as e:
            warning(f"MAIN PySide6: Pygame joystick initialization error: {e}. Menu joystick navigation disabled.")
            self._pygame_joysticks = []
        
        self._menu_selected_button_idx = 0
        self._last_pygame_joy_nav_time = 0.0
        self._pygame_joy_axis_was_active_neg = False
        self._pygame_joy_axis_was_active_pos = False
        self._main_menu_buttons_ref = []


        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.initial_main_window_width = max(800, min(int(screen_geo.width() * 0.75), 1600))
        self.initial_main_window_height = max(600, min(int(screen_geo.height() * 0.75), 900))
        self.setMinimumSize(QSize(800,600))
        self.resize(self.initial_main_window_width, self.initial_main_window_height)
        info(f"MAIN PySide6: Initial normal window size: {self.size().width()}x{self.size().height()}")

        self.fonts = {
            "small": QFont("Arial", 10), "medium": QFont("Arial", 14),
            "large": QFont("Arial", 24, QFont.Weight.Bold), "debug": QFont("Monospace", 9)
        }

        try:
            if not joystick_handler.init_joysticks(): # 'inputs' library handler
                warning("MAIN PySide6: 'inputs' joystick_handler failed to initialize. This affects controller_mapper_gui.")
            else:
                info("MAIN PySide6: 'inputs' joystick_handler initialized successfully for controller_mapper_gui.")
            
            game_config.load_config()
            self._translate_config_key_mappings()
        except Exception as e_cfg:
            critical(f"Error during 'inputs' joystick/config init in MainWindow: {e_cfg}", exc_info=True)

        self.app_status = APP_STATUS
        self.game_elements: Dict[str, Any] = {}
        self.current_view_name: Optional[str] = None
        self.current_game_mode: Optional[str] = None

        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None
        self.lan_search_dialog: Optional[QDialog] = None

        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = self._create_main_menu_widget() # Buttons are added to self._main_menu_buttons_ref here
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)

        self.editor_content_container = QWidget()
        self.editor_content_container.setLayout(QVBoxLayout())
        self.editor_content_container.layout().setContentsMargins(0,0,0,0)

        self.controls_content_container = QWidget()
        self.controls_content_container.setLayout(QVBoxLayout())
        self.controls_content_container.layout().setContentsMargins(0,0,0,0)

        self.editor_view_page = self._create_view_page_with_back_button("Level Editor", self.editor_content_container, self.on_return_to_menu_from_sub_view)
        self.settings_view_page = self._create_view_page_with_back_button("Settings/Controls", self.controls_content_container, self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget)
        self.stacked_widget.addWidget(self.game_scene_widget)
        self.stacked_widget.addWidget(self.editor_view_page)
        self.stacked_widget.addWidget(self.settings_view_page)

        self.setCentralWidget(self.stacked_widget)
        self.show_view("menu")

        self.network_status_update.connect(self.on_network_status_update)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update)
        self.status_dialog: Optional[QDialog] = None
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None
        
        self.joystick_poll_thread = JoystickPollingThread(self) # May not be needed if polling is done in game_update_timer
        self.joystick_poll_thread.start()
        
        self.game_update_timer = QTimer(self)
        self.game_update_timer.timeout.connect(self.update_game_loop)
        self.game_update_timer.start(1000 // C.FPS) # Approx 60 FPS for game logic and menu polling


    def _create_view_page_with_back_button(self, title_text: str, content_widget_to_embed: QWidget, back_slot: Slot) -> QWidget:
        # ... (definition remains the same)
        page_widget = QWidget()
        page_layout = QVBoxLayout(page_widget)
        page_layout.setContentsMargins(10, 10, 10, 10)
        title_label = QLabel(title_text)
        title_label.setFont(self.fonts["large"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_layout.addWidget(title_label)
        page_layout.addWidget(content_widget_to_embed, 1)
        back_button = QPushButton("Back to Main Menu")
        back_button.setFont(self.fonts["medium"])
        back_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        back_button.clicked.connect(back_slot)
        
        button_layout_wrapper = QHBoxLayout()
        button_layout_wrapper.addStretch()
        button_layout_wrapper.addWidget(back_button)
        button_layout_wrapper.addStretch()
        page_layout.addLayout(button_layout_wrapper)
        return page_widget

    def _clear_container_content(self, container_widget: QWidget):
        # ... (definition remains the same)
        layout = container_widget.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()

    def _ensure_editor_instance(self):
        # ... (definition remains the same)
        if self.actual_editor_module_instance and self.actual_editor_module_instance.parent() is self.editor_content_container:
            return
        
        self._clear_container_content(self.editor_content_container)
        
        if self.actual_editor_module_instance is None:
            info("MAIN PySide6: Creating and embedding editor instance.")
            try:
                from editor.editor import editor_main
                instance = editor_main(parent_app_instance=QApplication.instance(), embed_mode=True)
                if not instance or not isinstance(instance, QMainWindow):
                    error("Failed to get QMainWindow editor instance.")
                    self._add_placeholder_to_content_area(self.editor_content_container, "Error: Editor load failed.")
                    return
                self.actual_editor_module_instance = instance
            except Exception as e:
                error(f"Exception creating editor: {e}", exc_info=True)
                self._add_placeholder_to_content_area(self.editor_content_container, f"Error loading editor: {e}")
                self.actual_editor_module_instance = None
                return
        
        if self.actual_editor_module_instance:
            if self.actual_editor_module_instance.parent() is not None:
                self.actual_editor_module_instance.setParent(None)
            self.editor_content_container.layout().addWidget(self.actual_editor_module_instance)
            info("MAIN PySide6: Editor instance embedded.")

    def _ensure_controls_mapper_instance(self):
        # ... (definition remains the same)
        if self.actual_controls_module_instance and self.actual_controls_module_instance.parent() is self.controls_content_container:
            return

        self._clear_container_content(self.controls_content_container)

        if self.actual_controls_module_instance is None:
            info("MAIN PySide6: Creating and embedding controls mapper instance.")
            try:
                from controller_settings.controller_mapper_gui import MainWindow as ControlsMapperWindow
                instance = ControlsMapperWindow() 
                
                if not instance or not isinstance(instance, QWidget): # Check if it's a QWidget
                    error("Failed to get QWidget controls instance.")
                    self._add_placeholder_to_content_area(self.controls_content_container, "Error: Controls UI load failed (instance type).")
                    return
                self.actual_controls_module_instance = instance
            except ImportError as e_imp:
                error(f"ImportError creating controls mapper (likely 'inputs' lib issue for GUI): {e_imp}", exc_info=True)
                self._add_placeholder_to_content_area(self.controls_content_container, f"Error importing controls UI: {e_imp}")
                self.actual_controls_module_instance = None
                return
            except Exception as e:
                error(f"Exception creating controls mapper: {e}", exc_info=True)
                self._add_placeholder_to_content_area(self.controls_content_container, f"Error loading controls UI: {e}")
                self.actual_controls_module_instance = None
                return

        if self.actual_controls_module_instance:
            if self.actual_controls_module_instance.parent() is not None:
                self.actual_controls_module_instance.setParent(None)
            self.controls_content_container.layout().addWidget(self.actual_controls_module_instance)
            info("MAIN PySide6: Controls mapper instance embedded/handled.")

    def _add_placeholder_to_content_area(self, container: QWidget, msg: str):
        # ... (definition remains the same)
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            container.setLayout(layout)
        else:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(self.fonts["medium"])
        layout.addWidget(lbl)

    def _translate_config_key_mappings(self):
        # ... (definition remains the same)
        info("Translating keyboard mappings to Qt.Key values.")
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P1_MAPPINGS)
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P2_MAPPINGS)
        if game_config.CURRENT_P1_INPUT_DEVICE.startswith("keyboard"):
            self._apply_qt_key_translation_to_map_definition(game_config.P1_MAPPINGS)
        if game_config.CURRENT_P2_INPUT_DEVICE.startswith("keyboard"):
            self._apply_qt_key_translation_to_map_definition(game_config.P2_MAPPINGS)
        info("Keyboard mapping translation complete.")

    def _apply_qt_key_translation_to_map_definition(self, mapping_dict: Dict[str, Any]):
        # ... (definition remains the same)
        for action, key_val_str in list(mapping_dict.items()):
            if isinstance(key_val_str, str):
                qt_key = QT_KEY_MAP.get(key_val_str.upper())
                if qt_key is None and len(key_val_str) == 1:
                    try:
                        seq = QKeySequence(key_val_str.upper())
                        if seq.count() > 0:
                            qt_key_from_seq = seq[0].key()
                            if qt_key_from_seq != 0: 
                                qt_key = Qt.Key(qt_key_from_seq)
                    except Exception: pass 
                
                if qt_key is not None and qt_key != Qt.Key.Key_unknown :
                    mapping_dict[action] = qt_key

    def _create_main_menu_widget(self) -> QWidget:
        self._main_menu_buttons_ref = [] # Clear previous button references
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
            ("Level Editor", lambda: self.show_view("editor")),
            ("Settings/Controls", lambda: self.show_view("settings")),
            ("Quit", self.request_close_app)
        ]

        for text, slot_func in buttons_data:
            button = QPushButton(text)
            button.setFont(self.fonts["medium"])
            button.setMinimumHeight(40)
            button.setMinimumWidth(250)
            button.clicked.connect(slot_func)
            layout.addWidget(button)
            self._main_menu_buttons_ref.append(button) # Store reference for joystick nav
        
        self._update_main_menu_button_focus() # Initial focus
        return menu_widget

    def _update_main_menu_button_focus(self):
        if not self._main_menu_buttons_ref:
            return
        for i, button in enumerate(self._main_menu_buttons_ref):
            is_selected = (i == self._menu_selected_button_idx)
            # Update visual style for selection (e.g., border, background)
            # PySide6 doesn't have a direct "hover" state equivalent from code for QPushButtons easily
            # without stylesheets or custom painting. For simplicity, we'll just set focus.
            if is_selected:
                button.setStyleSheet("QPushButton { border: 2px solid yellow; }")
                button.setFocus(Qt.FocusReason.OtherFocusReason) # Give it keyboard focus
            else:
                button.setStyleSheet("") # Reset style
    
    def _navigate_main_menu_pygame_joy(self, direction: int): # direction: -1 for up, 1 for down
        if not self._main_menu_buttons_ref:
            return
        
        num_buttons = len(self._main_menu_buttons_ref)
        self._menu_selected_button_idx = (self._menu_selected_button_idx + direction + num_buttons) % num_buttons
        self._update_main_menu_button_focus()
        info(f"Menu Joystick: Navigated to button index {self._menu_selected_button_idx}")

    def _activate_main_menu_selected_button_pygame_joy(self):
        if not self._main_menu_buttons_ref or \
           not (0 <= self._menu_selected_button_idx < len(self._main_menu_buttons_ref)):
            return
        
        selected_button = self._main_menu_buttons_ref[self._menu_selected_button_idx]
        info(f"Menu Joystick: Activating button '{selected_button.text()}'")
        selected_button.click() # Simulate a click

    def _poll_pygame_joysticks_for_menu(self):
        if self.current_view_name != "menu" or not self._pygame_joysticks:
            return

        pygame.event.pump() # Process Pygame's internal event queue (needed for joystick state updates)

        joy = self._pygame_joysticks[0] # For simplicity, use the first detected Pygame joystick for menu
        
        # --- Get effective Pygame key mappings for menu actions ---
        # We'll use a simplified default or try to read from config.py's joystick mapping
        # This part is a bit tricky as config.py is geared towards the 'inputs' library format.
        # For Pygame menu nav, we usually look for specific button IDs (e.g., A=0, B=1) or D-pad.

        # Simplified: Button 0 (often A/Cross) for select, Button 1 (often B/Circle) for back/quit
        # D-pad or Left Stick Y for up/down.
        JOY_MENU_CONFIRM_BTN_ID = 0 # Typically A/Cross
        JOY_MENU_CANCEL_BTN_ID = 1  # Typically B/Circle
        JOY_MENU_NAV_AXIS_ID = 1    # Typically Left Stick Y
        JOY_MENU_NAV_HAT_ID = 0     # D-Pad

        current_time = time.monotonic()
        if current_time - self._last_pygame_joy_nav_time < 0.2: # 200ms cooldown
            return

        # Check D-pad/Hat for up/down
        if joy.get_numhats() > JOY_MENU_NAV_HAT_ID:
            hat_x, hat_y = joy.get_hat(JOY_MENU_NAV_HAT_ID)
            if hat_y > 0.5: # Hat down
                self._navigate_main_menu_pygame_joy(1)
                self._last_pygame_joy_nav_time = current_time
                return
            elif hat_y < -0.5: # Hat up
                self._navigate_main_menu_pygame_joy(-1)
                self._last_pygame_joy_nav_time = current_time
                return

        # Check Axis for up/down
        if joy.get_numaxes() > JOY_MENU_NAV_AXIS_ID:
            axis_val = joy.get_axis(JOY_MENU_NAV_AXIS_ID)
            if axis_val > 0.7: # Axis pushed down
                if not self._pygame_joy_axis_was_active_pos:
                    self._navigate_main_menu_pygame_joy(1)
                    self._last_pygame_joy_nav_time = current_time
                self._pygame_joy_axis_was_active_pos = True
                return # Prioritize axis over next checks if active
            else:
                self._pygame_joy_axis_was_active_pos = False

            if axis_val < -0.7: # Axis pushed up
                if not self._pygame_joy_axis_was_active_neg:
                    self._navigate_main_menu_pygame_joy(-1)
                    self._last_pygame_joy_nav_time = current_time
                self._pygame_joy_axis_was_active_neg = True
                return
            else:
                self._pygame_joy_axis_was_active_neg = False
        
        # Check buttons for confirm/cancel
        # We need to check button presses (down event), not just held state.
        # Pygame's event queue is better for this, but we're polling.
        # A simple way is to track previous button states for polling.
        # For now, this will trigger on hold, which is not ideal for confirm.
        # A proper solution would involve Pygame event loop integration or more complex polling.
        
        # This part would be better with pygame.event.get() and JOYBUTTONDOWN
        # but since PySide6 has the event loop, we are restricted.
        # Let's assume this is called frequently enough that button presses will be caught.
        # (This is a known limitation of polling for discrete button presses without an event queue)
        if joy.get_numbuttons() > JOY_MENU_CONFIRM_BTN_ID and joy.get_button(JOY_MENU_CONFIRM_BTN_ID):
            self._activate_main_menu_selected_button_pygame_joy()
            self._last_pygame_joy_nav_time = current_time # Add cooldown after action too
            return
        
        if joy.get_numbuttons() > JOY_MENU_CANCEL_BTN_ID and joy.get_button(JOY_MENU_CANCEL_BTN_ID):
            # In main menu, cancel usually means quit
            self.request_close_app()
            self._last_pygame_joy_nav_time = current_time
            return


    def request_close_app(self):
        # ... (definition remains the same)
        info("MAIN PySide6: Quit action triggered from UI.")
        self.close()

    def on_return_to_menu_from_sub_view(self):
        # ... (definition remains the same, ensure _update_main_menu_button_focus is called if returning to menu)
        source_view = self.current_view_name
        info(f"Returning to menu from: {source_view}")
        should_return_to_menu = True

        if source_view == "editor" and self.actual_editor_module_instance:
            if hasattr(self.actual_editor_module_instance, 'confirm_unsaved_changes') and \
               callable(self.actual_editor_module_instance.confirm_unsaved_changes):
                if not self.actual_editor_module_instance.confirm_unsaved_changes("return to menu"):
                    should_return_to_menu = False
            if should_return_to_menu and hasattr(self.actual_editor_module_instance, 'save_geometry_and_state') and \
               callable(self.actual_editor_module_instance.save_geometry_and_state):
                self.actual_editor_module_instance.save_geometry_and_state()
            if should_return_to_menu and self.actual_editor_module_instance.parent() is not None:
                 self.actual_editor_module_instance.setParent(None)

        elif source_view == "settings" and self.actual_controls_module_instance:
            if should_return_to_menu and self.actual_controls_module_instance.parent() is not None:
                self.actual_controls_module_instance.setParent(None)

        if should_return_to_menu:
            self.show_view("menu") # This will call _update_main_menu_button_focus
        else:
            info("Return to menu cancelled by sub-view.")

    def show_view(self, view_name: str):
        # ... (definition remains the same, added call to _update_main_menu_button_focus if view is menu)
        info(f"Switching UI view to: {view_name}")
        if self.current_view_name == "game_scene" and view_name != "game_scene" and self.current_game_mode:
            self.stop_current_game_mode(show_menu=False)

        self.current_view_name = view_name
        
        target_widget_page: Optional[QWidget] = None
        window_title = "Platformer"

        if view_name == "menu":
            target_widget_page = self.main_menu_widget
            window_title += " - Main Menu"
            self._menu_selected_button_idx = 0 # Reset menu selection
            self._update_main_menu_button_focus() # Ensure focus is correct when showing menu
        elif view_name == "game_scene":
            target_widget_page = self.game_scene_widget
            window_title += f" - {self.current_game_mode.replace('_',' ').title() if self.current_game_mode else 'Game'}"
        elif view_name == "editor":
            self._ensure_editor_instance()
            target_widget_page = self.editor_view_page
            window_title += " - Level Editor"
        elif view_name == "settings":
            self._ensure_controls_mapper_instance()
            target_widget_page = self.settings_view_page
            window_title += " - Settings/Controls"

        if target_widget_page:
            self.stacked_widget.setCurrentWidget(target_widget_page)
            self.setWindowTitle(window_title)
            if view_name == "editor" and self.actual_editor_module_instance:
                self.actual_editor_module_instance.setFocus()
            elif view_name == "settings" and self.actual_controls_module_instance:
                self.actual_controls_module_instance.setFocus()
            elif target_widget_page:
                target_widget_page.setFocus()
        else:
            warning(f"show_view: Unknown view '{view_name}'. Defaulting to menu.")
            self.stacked_widget.setCurrentWidget(self.main_menu_widget)
            self.setWindowTitle("Platformer Adventure LAN - Main Menu")
            self.main_menu_widget.setFocus()
            self._menu_selected_button_idx = 0 
            self._update_main_menu_button_focus()
        
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        _qt_keys_pressed_snapshot.clear()
        _qt_key_events_this_frame.clear()

    def keyPressEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        is_auto_repeat = event.isAutoRepeat()
        qt_key_enum = Qt.Key(event.key())

        if not is_auto_repeat:
            _qt_keys_pressed_snapshot[qt_key_enum] = True
            _qt_key_events_this_frame.append((QKeyEvent.Type.KeyPress, qt_key_enum, is_auto_repeat))
        
        # Keyboard menu navigation
        if self.current_view_name == "menu" and not is_auto_repeat:
            if event.key() == Qt.Key.Key_Up:
                self._navigate_main_menu_pygame_joy(-1) # Re-use logic, -1 for up
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Down:
                self._navigate_main_menu_pygame_joy(1)  # Re-use logic, 1 for down
                event.accept()
                return
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space]:
                self._activate_main_menu_selected_button_pygame_joy()
                event.accept()
                return

        if event.key() == Qt.Key.Key_Escape and not is_auto_repeat:
            if self.current_view_name == "menu":
                self.request_close_app()
            elif self.current_view_name in ["editor", "settings"]:
                self.on_return_to_menu_from_sub_view()
            elif self.current_view_name == "game_scene" and self.current_game_mode:
                info(f"Escape in game mode '{self.current_game_mode}'. Stopping.")
                self.stop_current_game_mode(show_menu=True)
            event.accept()
            return
        
        if not event.isAccepted():
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        # ... (definition remains the same)
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        is_auto_repeat = event.isAutoRepeat()
        qt_key_enum = Qt.Key(event.key())

        if not is_auto_repeat:
            _qt_keys_pressed_snapshot[qt_key_enum] = False
        
        if not event.isAccepted():
            super().keyReleaseEvent(event)

    def _get_input_snapshot(self, player_instance: Player, player_id: int) -> Dict[str, bool]:
        # ... (definition remains the same, it uses config.py which relies on 'inputs' or keyboard)
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        
        if not player_instance or not hasattr(player_instance, '_valid_init') or not player_instance._valid_init:
             warning(f"_get_input_snapshot: Invalid player_instance for player_id {player_id}.")
             return {}
        
        active_mappings = {}
        joystick_internal_id_for_player: Optional[int] = None # This refers to ID for 'inputs' lib via config

        if player_id == 1:
            active_mappings = game_config.P1_MAPPINGS
            if game_config.CURRENT_P1_INPUT_DEVICE.startswith("joystick_"):
                try: 
                    # This ID is for the 'inputs' library system, not Pygame's indexing
                    joystick_internal_id_for_player = int(game_config.CURRENT_P1_INPUT_DEVICE.split('_')[-1])
                except (ValueError, IndexError): 
                    joystick_internal_id_for_player = None
        elif player_id == 2:
            active_mappings = game_config.P2_MAPPINGS
            if game_config.CURRENT_P2_INPUT_DEVICE.startswith("joystick_"):
                try:
                    joystick_internal_id_for_player = int(game_config.CURRENT_P2_INPUT_DEVICE.split('_')[-1])
                except (ValueError, IndexError):
                    joystick_internal_id_for_player = None

        joystick_data_for_handler: Optional[Dict[str,Any]] = None
        # This block is for IN-GAME joystick input via the 'inputs' library (via controller_mapper_gui)
        if joystick_internal_id_for_player is not None:
             # The joystick_handler here is the 'inputs' based one.
             # Its get_joystick_count() might not align with Pygame's.
            if 0 <= joystick_internal_id_for_player < joystick_handler.get_joystick_count(): 
                joystick_data_for_handler = {
                    'axes': joystick_handler.get_axis_values(joystick_internal_id_for_player),
                    'buttons_current': joystick_handler.get_button_states(joystick_internal_id_for_player),
                    'buttons_prev': joystick_handler.get_prev_button_states(joystick_internal_id_for_player),
                    'hats': joystick_handler.get_hat_values(joystick_internal_id_for_player)
                }
        
        platforms_list = self.game_elements.get("platforms_list", [])
        if not isinstance(platforms_list, list): platforms_list = []

        action_events = process_player_input_logic(
            player_instance,
            _qt_keys_pressed_snapshot,
            list(_qt_key_events_this_frame),
            active_mappings,
            platforms_list,
            joystick_data=joystick_data_for_handler # This is 'inputs' lib data if joystick chosen in config
        )
        
        _qt_key_events_this_frame.clear()
        return action_events

    @staticmethod
    def get_p1_input_snapshot_for_server_thread(player_instance: Any, platforms_list: List[Any]) -> Dict[str, Any]:
        # ... (definition remains the same)
        if MainWindow._instance:
            return MainWindow._instance._get_input_snapshot(player_instance, 1)
        return {}

    @staticmethod
    def get_p2_input_snapshot_for_client_thread(player_instance: Any) -> Dict[str, Any]:
        # ... (definition remains the same)
        platforms_list = []
        if MainWindow._instance and MainWindow._instance.game_elements:
            platforms_list = MainWindow._instance.game_elements.get("platforms_list", [])

        if MainWindow._instance:
            return MainWindow._instance._get_input_snapshot(player_instance, 2)
        return {}

    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        # ... (definition mostly same, camera line updated)
        info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
        main_window_size = self.size()
        current_width, current_height = main_window_size.width(), main_window_size.height()
        
        if current_width <= 100 or current_height <= 100: 
            current_width, current_height = self.initial_main_window_width, self.initial_main_window_height
            info(f"MainWindow size too small or invalid ({main_window_size.width()}x{main_window_size.height()}), using defaults for game init: {current_width}x{current_height}")
        else:
            info(f"MainWindow current size for game init: {current_width}x{current_height}")

        if map_name is None and mode in ["host", "join_lan", "join_ip", "couch_play"]:
            map_name = getattr(C, 'DEFAULT_LEVEL_MODULE_NAME', "level_default")

        initialized_elements = initialize_game_elements(current_width, current_height, mode, None, map_name)
        
        if initialized_elements is None:
            QMessageBox.critical(self, "Error", f"Failed to initialize game elements for {mode}, map '{map_name}'. Check logs.")
            self.show_view("menu")
            return

        self.game_elements.clear(); self.game_elements.update(initialized_elements)
        self.game_elements['current_game_mode'] = mode 
        
        self.current_game_mode = mode
        self.setWindowTitle(f"Platformer Adventure LAN - {mode.replace('_',' ').title()}")

        camera = self.game_elements.get("camera")
        if camera and hasattr(camera, 'set_screen_dimensions') and hasattr(camera, 'set_level_dimensions'):
            game_scene_render_width = self.game_scene_widget.width()
            game_scene_render_height = self.game_scene_widget.height()
            if game_scene_render_width <=1 or game_scene_render_height <=1 : 
                game_scene_render_width = current_width
                game_scene_render_height = current_height

            camera.set_screen_dimensions(float(game_scene_render_width), float(game_scene_render_height))
            if "level_pixel_width" in self.game_elements:
                camera.set_level_dimensions(
                    self.game_elements["level_pixel_width"],
                    self.game_elements.get("level_min_x_absolute", 0.0), # MODIFIED: Added min_x
                    self.game_elements.get("level_min_y_absolute", 0.0),
                    self.game_elements.get("level_max_y_absolute", game_scene_render_height)
                )
            player1_for_cam = self.game_elements.get("player1")
            if player1_for_cam and hasattr(camera, 'update'):
                 camera.update(player1_for_cam)

        self.show_view("game_scene")
        QApplication.processEvents() 
        self.game_scene_widget.update_game_state(0) 
        
        if mode in ["host", "join_lan", "join_ip"]: self._start_network_mode(mode, target_ip_port)
        elif mode == "couch_play": info("Preparing for couch play. Game loop handled by update_game_loop.")

        info(f"Game mode '{mode}' display prepared. Active game loop/updates depend on mode-specific logic.")

    def update_game_loop(self):
        # Poll Pygame joysticks for menu if menu is active
        if self.current_view_name == "menu" and self._pygame_joysticks:
            self._poll_pygame_joysticks_for_menu()

        if self.current_game_mode == "couch_play" and self.app_status.app_running:
            dt_sec = 1.0 / C.FPS 
            if not run_couch_play_mode(
                self.game_elements,
                self.app_status,
                lambda p, plat: self._get_input_snapshot(p, 1),
                lambda p, plat: self._get_input_snapshot(p, 2),
                lambda: QApplication.processEvents(),
                lambda: dt_sec,
                lambda msg: self.game_scene_widget.update_game_state(0, download_msg=msg) 
            ):
                self.stop_current_game_mode(show_menu=True)
        
        if self.current_view_name == "game_scene":
            self.game_scene_widget.update_game_state(0)


    def on_start_couch_play(self):
        # ... (definition remains the same)
        map_name = self._select_map_dialog()
        if map_name is not None:
            self._prepare_and_start_game("couch_play", map_name=map_name)
        else:
            info("Couch play map selection cancelled."); self.show_view("menu")

    def on_start_host_game(self):
        # ... (definition remains the same)
        map_name = self._select_map_dialog()
        if map_name is not None:
            self._prepare_and_start_game("host", map_name=map_name)
        else:
            info("Host game map selection cancelled."); self.show_view("menu")

    def on_start_join_lan(self): 
        # ... (definition remains the same)
        self._show_lan_search_dialog()

    def on_start_join_ip(self):
        # ... (definition remains the same)
        dialog = IPInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.ip_port_string:
            self._prepare_and_start_game("join_ip", target_ip_port=dialog.ip_port_string)
        else:
            info("Join by IP cancelled or no IP entered."); self.show_view("menu")

    def _select_map_dialog(self) -> Optional[str]:
        # ... (definition remains the same)
        dialog = SelectMapDialog(self.fonts, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: return dialog.selected_map_name
        return None

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        # ... (definition remains the same)
        if self.network_thread and self.network_thread.isRunning():
            warning("NetworkThread already running. Attempting to stop old one first.")
            self.network_thread.quit(); self.network_thread.wait(1000)
            self.network_thread = None

        if mode_name == "host":
            self.server_state = ServerState()
            self.server_state.current_map_name = self.game_elements.get("loaded_map_name", "unknown_map")
            self.network_thread = NetworkThread("host", self.game_elements, self.server_state, parent=self)
        elif mode_name in ["join_lan", "join_ip"]:
            self.client_state = ClientState()
            self.network_thread = NetworkThread("join", self.game_elements, client_state_ref=self.client_state, target_ip_port=target_ip_port, parent=self)
        
        if self.network_thread:
            self.network_thread.status_update_signal.connect(self.on_network_status_update)
            self.network_thread.operation_finished_signal.connect(self.on_network_operation_finished)
            self.network_thread.start()
            self._show_status_dialog("Network Operation", f"Initializing {mode_name} mode...")
        else:
            error(f"Failed to create NetworkThread for {mode_name}")
            QMessageBox.critical(self, "Network Error", f"Could not start {mode_name} mode.")
            self.show_view("menu")

    def _show_status_dialog(self, title: str, initial_message: str):
        # ... (definition remains the same)
        if self.status_dialog is None:
            self.status_dialog = QDialog(self); self.status_dialog.setWindowTitle(title)
            layout = QVBoxLayout(self.status_dialog)
            self.status_label_in_dialog = QLabel(initial_message); self.status_label_in_dialog.setWordWrap(True)
            layout.addWidget(self.status_label_in_dialog)
            self.status_progress_bar_in_dialog = QProgressBar(); self.status_progress_bar_in_dialog.setRange(0,100)
            self.status_progress_bar_in_dialog.setTextVisible(True); layout.addWidget(self.status_progress_bar_in_dialog)
            self.status_dialog.setMinimumWidth(350)
        else: self.status_dialog.setWindowTitle(title)
        if self.status_label_in_dialog: self.status_label_in_dialog.setText(initial_message)
        if self.status_progress_bar_in_dialog: self.status_progress_bar_in_dialog.setValue(0); self.status_progress_bar_in_dialog.setVisible(False)
        self.status_dialog.show(); QApplication.processEvents()

    def _update_status_dialog(self, message: str, progress: float = -1.0):
        # ... (definition remains the same)
        if self.status_dialog and self.status_dialog.isVisible():
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(message)
            if self.status_progress_bar_in_dialog:
                if 0 <= progress <= 100: self.status_progress_bar_in_dialog.setValue(int(progress)); self.status_progress_bar_in_dialog.setVisible(True)
                else: self.status_progress_bar_in_dialog.setVisible(False)
        QApplication.processEvents()

    def _close_status_dialog(self):
        # ... (definition remains the same)
        if self.status_dialog: self.status_dialog.hide()

    @Slot(str, str, float)
    def on_network_status_update(self, title: str, message: str, progress: float):
        # ... (definition remains the same)
        if not self.status_dialog or not self.status_dialog.isVisible(): self._show_status_dialog(title, message) 
        self._update_status_dialog(message, progress)
        if title in ["game_starting", "game_active"] or (title == "Map Sync" and "ready" in message.lower() and progress >= 99.9): self._close_status_dialog()

    @Slot(str)
    def on_network_operation_finished(self, message: str):
        # ... (definition remains the same)
        info(f"Network operation finished: {message}")
        self._close_status_dialog()
        if "error" in message.lower() or "failed" in message.lower():
            QMessageBox.critical(self, "Network Error", f"Network operation ended with an error: {message}")
            self.stop_current_game_mode(show_menu=True)
        elif "ended" in message.lower() and self.current_game_mode:
            info(f"Mode {self.current_game_mode} finished normally via network signal.")
            self.stop_current_game_mode(show_menu=True)

    def _show_lan_search_dialog(self):
        # ... (definition remains the same)
        if self.lan_search_dialog is None:
            self.lan_search_dialog = QDialog(self); self.lan_search_dialog.setWindowTitle("Searching for LAN Games...")
            layout = QVBoxLayout(self.lan_search_dialog); self.lan_search_status_label = QLabel("Initializing search...")
            layout.addWidget(self.lan_search_status_label); self.lan_servers_list_widget = QListWidget()
            self.lan_servers_list_widget.itemDoubleClicked.connect(self._join_selected_lan_server_from_dialog); layout.addWidget(self.lan_servers_list_widget)
            self.lan_search_dialog.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Join Selected"); self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            self.lan_search_dialog.button_box.accepted.connect(self._join_selected_lan_server_from_dialog); self.lan_search_dialog.button_box.rejected.connect(self.lan_search_dialog.reject)
            self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self._start_lan_server_search_thread); layout.addWidget(self.lan_search_dialog.button_box)
            self.lan_search_dialog.rejected.connect(lambda: self.show_view("menu")); self.lan_search_dialog.setMinimumSize(400, 300)
        self.lan_servers_list_widget.clear(); self.lan_search_status_label.setText("Searching for LAN games...")
        self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.lan_search_dialog.show(); self._start_lan_server_search_thread()

    def _start_lan_server_search_thread(self):
        # ... (definition remains the same)
        if hasattr(self, 'lan_search_worker') and self.lan_search_worker and self.lan_search_worker.isRunning():
            warning("LAN search worker already running. Requesting stop for restart."); self.lan_search_worker.quit()
            if not self.lan_search_worker.wait(500): self.lan_search_worker.terminate(); self.lan_search_worker.wait(100)
        if self.lan_servers_list_widget: self.lan_servers_list_widget.clear()
        if self.lan_search_status_label: self.lan_search_status_label.setText("Searching...")
        if self.lan_search_dialog and hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.lan_search_worker = QThread(self)
        class LanSearchRunner(QWidget): # QWidget for signal/slot compatibility
            found_signal = Signal(object); search_finished_signal = Signal()
            def __init__(self, parent=None): super().__init__(parent); self.client_state_for_search = ClientState()
            @Slot()
            def run_search(self):
                info("LanSearchRunner: Starting find_server_on_lan.")
                try:
                    def on_server_found_callback(key: str, data: Any): self.found_signal.emit((key, data))
                    result_server_info = find_server_on_lan(self.client_state_for_search, on_server_found_callback)
                    self.found_signal.emit(("final_result", result_server_info))
                except Exception as e: critical(f"LanSearchRunner: Error during LAN search: {e}", exc_info=True); self.found_signal.emit(("error", f"Search failed: {e}"))
                finally: self.search_finished_signal.emit(); info("LanSearchRunner: run_search finished.")
        self.lan_search_run_obj = LanSearchRunner(); self.lan_search_run_obj.moveToThread(self.lan_search_worker)
        self.lan_search_worker.started.connect(self.lan_search_run_obj.run_search); self.lan_search_run_obj.found_signal.connect(self.on_lan_server_search_status_update)
        self.lan_search_worker.finished.connect(self.lan_search_worker.deleteLater); self.lan_search_run_obj.search_finished_signal.connect(self.lan_search_worker.quit)
        self.lan_search_run_obj.search_finished_signal.connect(self.lan_search_run_obj.deleteLater); self.lan_search_worker.start()
        info("LAN server search thread started.")

    @Slot(object)
    def on_lan_server_search_status_update(self, data_tuple: Any):
        # ... (definition remains the same)
        if not self.lan_search_dialog or not self.lan_search_dialog.isVisible(): info("LAN search status update received, but dialog is not visible. Ignoring."); return
        if not isinstance(data_tuple, tuple) or len(data_tuple) != 2: warning(f"Invalid data_tuple received in on_lan_server_search_status_update: {data_tuple}"); return
        status_key, data = data_tuple; debug(f"LAN Search Status: Key='{status_key}', Data='{str(data)[:100]}'")
        if self.lan_search_status_label: self.lan_search_status_label.setText(f"Status: {status_key}")
        if status_key == "found" and isinstance(data, tuple) and len(data)==2:
            ip, port = data; item_text = f"Server at {ip}:{port}"
            if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly):
                list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}")
                self.lan_servers_list_widget.addItem(list_item)
            if hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        elif status_key == "timeout" or status_key == "error" or (status_key == "final_result" and data is None and self.lan_servers_list_widget.count() == 0):
            if self.lan_servers_list_widget.count() == 0 and self.lan_search_status_label: self.lan_search_status_label.setText(f"Search {status_key}. No servers found.")
        elif status_key == "final_result" and data is not None:
             ip, port = data; item_text = f"Server at {ip}:{port} (Recommended)"
             if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly):
                list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}")
                self.lan_servers_list_widget.addItem(list_item); self.lan_servers_list_widget.setCurrentItem(list_item)
             if hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _join_selected_lan_server_from_dialog(self):
        # ... (definition remains the same)
        if not self.lan_servers_list_widget or not self.lan_search_dialog: warning("Attempt to join LAN server, but list widget or dialog is missing."); return
        selected_items = self.lan_servers_list_widget.selectedItems()
        if selected_items:
            selected_item = selected_items[0]; ip_port_str = selected_item.data(Qt.ItemDataRole.UserRole)
            if ip_port_str and isinstance(ip_port_str, str):
                info(f"Joining selected LAN server: {ip_port_str}"); self.lan_search_dialog.accept()
                self._prepare_and_start_game("join_lan", target_ip_port=ip_port_str); return
            else: warning(f"Selected LAN server item has invalid data: {ip_port_str}")
        QMessageBox.warning(self, "No Server Selected", "Please select a server from the list to join, or Cancel.")

    def stop_current_game_mode(self, show_menu: bool = True):
        # ... (definition remains the same)
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
        if self.lan_search_dialog and self.lan_search_dialog.isVisible(): self.lan_search_dialog.reject()
        self.game_elements.clear()
        self.game_scene_widget.update_game_state(0) 
        if show_menu: self.show_view("menu")
        info(f"Game mode '{mode_stopped}' stopped and cleaned up.")

    def closeEvent(self, event: QCloseEvent):
        # ... (definition remains the same)
        info("MAIN PySide6: Close event received. Initiating shutdown sequence.")
        if self.actual_editor_module_instance:
            can_close_editor = True
            if isinstance(self.actual_editor_module_instance, QMainWindow):
                if hasattr(self.actual_editor_module_instance, 'request_close'): 
                     if not self.actual_editor_module_instance.request_close(): can_close_editor = False
                elif not self.actual_editor_module_instance.close(): 
                     can_close_editor = False 
            if not can_close_editor: info("Editor prevented application close."); event.ignore(); return
            else: self.actual_editor_module_instance.deleteLater(); self.actual_editor_module_instance = None; info("Editor instance scheduled for deletion.")
        
        if self.actual_controls_module_instance:
            self.actual_controls_module_instance.deleteLater(); self.actual_controls_module_instance = None; info("Controls mapper instance scheduled for deletion.")

        self.app_status.quit_app(); self.stop_current_game_mode(show_menu=False)
        if self.joystick_poll_thread and self.joystick_poll_thread.isRunning():
            info("Stopping joystick polling thread..."); self.joystick_poll_thread.stop()
            if not self.joystick_poll_thread.wait(1000): warning("Joystick polling thread did not stop gracefully. Terminating."); self.joystick_poll_thread.terminate(); self.joystick_poll_thread.wait(100)
            info("Joystick polling thread stopped.")
        
        joystick_handler.quit_joysticks(); info("MAIN PySide6: 'inputs' joystick_handler.quit_joysticks() called.")
        pygame.joystick.quit() # Quit Pygame joystick module
        pygame.quit() # Quit all Pygame modules
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
    if APP_STATUS.app_running: 
        APP_STATUS.app_running = False
    info("MAIN PySide6: Application fully terminated."); sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e_main_outer:
        if 'critical' in globals() and callable(critical) and _project_root: 
            critical(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}", exc_info=True)
        else: 
            print(f"MAIN CRITICAL UNHANDLED EXCEPTION: {e_main_outer}")
            traceback.print_exc()
        
        try:
            error_app = QApplication.instance()
            if error_app is None: error_app = QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Critical Application Error")
            msg_box.setText("A critical error occurred, and the application must close.")
            
            log_path_info_str = ""
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
            print(f"FATAL: Could not display Qt error dialog: {e_msgbox}")
            traceback.print_exc()
        sys.exit(1)