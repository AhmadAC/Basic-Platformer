import sys
import os
import traceback
import time
from typing import Dict, Optional, Any, List, Tuple

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy
)
from PySide6.QtGui import (QFont, QKeyEvent, QMouseEvent, QCloseEvent, QColor, QPalette, QScreen, QKeySequence)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QSize

# --- Add project root to sys.path for module imports ---
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
    # print(f"INFO: Added project root '{_project_root}' to sys.path for module imports.")

# --- Game Module Imports ---
try:
    from logger import info, debug, warning, critical, error, LOGGING_ENABLED, LOG_FILE_PATH
    # info(f"MAIN PySide6: Project root '{_project_root}' is in sys.path.")

    import constants as C
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode, find_server_on_lan
    from couch_play_logic import run_couch_play_mode
    from game_ui import GameSceneWidget, SelectMapDialog, IPInputDialog
    import config as game_config
    import joystick_handler # Using 'inputs' library
    from player import Player
    from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
    
    # For full integration of editor and controls UI:
    # from editor.editor import EditorMainWindow as ActualEditorWindow
    # from controller_settings.controller_mapper_gui import MainWindow as ActualControlsWindow

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
    "SPACE": Qt.Key.Key_Space, "J": Qt.Key.Key_J, "L": Qt.Key.Key_L, "I": Qt.Key.Key_I,
    "K": Qt.Key.Key_K, "O": Qt.Key.Key_O, "P": Qt.Key.Key_P,
    ";": Qt.Key.Key_Semicolon, "'": Qt.Key.Key_Apostrophe, "\\": Qt.Key.Key_Backslash,
    # Numpad keys should map to specific Qt.Key_KeypadX enums if Qt distinguishes them
    # For simplicity, mapping to regular numbers for now if not found, but proper mapping is better.
    "NUM+0": Qt.Key.Key_0, "NUM+1": Qt.Key.Key_1, "NUM+2": Qt.Key.Key_2,
    "NUM+3": Qt.Key.Key_3, "NUM+4": Qt.Key.Key_4, "NUM+5": Qt.Key.Key_5,
    "NUM+6": Qt.Key.Key_6, "NUM+7": Qt.Key.Key_7, "NUM+8": Qt.Key.Key_8,
    "NUM+9": Qt.Key.Key_9,
    "NUM+ENTER": Qt.Key.Key_Enter, # Often same as main Enter
    "DELETE": Qt.Key.Key_Delete, "PAUSE": Qt.Key.Key_Pause,
}

# --- Global App Status & Timer ---
class AppStatus:
    def __init__(self): self.app_running = True
    def quit_app(self):
        info("APP_STATUS: quit_app() called.")
        self.app_running = False
        app_instance = QApplication.instance()
        if app_instance: debug("APP_STATUS: Requesting QApplication.quit()."); app_instance.quit()

APP_STATUS = AppStatus()
_app_start_time = time.monotonic()
def get_current_game_ticks(): return int((time.monotonic() - _app_start_time) * 1000)

_qt_keys_pressed_snapshot: Dict[Qt.Key, bool] = {}
_qt_key_events_this_frame: List[QKeyEvent] = []
_joystick_axis_values_pyside: Dict[int, Dict[int, float]] = {}
_joystick_button_states_pyside: Dict[int, Dict[int, bool]] = {}
_joystick_hat_values_pyside: Dict[int, Dict[int, Tuple[int, int]]] = {}
_prev_joystick_button_states_pyside: Dict[int, Dict[int, bool]] = {}


# --- NetworkThread (No changes from previous version, assuming it's fine) ---
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
            if self.mode == "host" and self.server_state:
                info("NetworkThread: Starting run_server_mode...")
                run_server_mode(self.server_state, self.game_elements, self._ui_status_update_callback, self._get_p1_input_snapshot_main_thread_passthrough, lambda: QApplication.processEvents())
                info("NetworkThread: run_server_mode finished."); self.operation_finished_signal.emit("host_ended")
            elif self.mode == "join" and self.client_state:
                info("NetworkThread: Starting run_client_mode...")
                run_client_mode(self.client_state, self.game_elements, self._ui_status_update_callback, self.target_ip_port, MainWindow.get_p2_input_snapshot_for_client_thread, lambda: QApplication.processEvents())
                info("NetworkThread: run_client_mode finished."); self.operation_finished_signal.emit("client_ended")
        except Exception as e: critical(f"NetworkThread: Exception in {self.mode} mode: {e}", exc_info=True); self.operation_finished_signal.emit(f"{self.mode}_error")


class MainWindow(QMainWindow):
    _instance: Optional['MainWindow'] = None
    network_status_update = Signal(str, str, float)
    lan_server_search_status = Signal(str, object)

    # --- Placeholder for actual editor/settings windows ---
    actual_editor_window_instance: Optional[QWidget] = None
    actual_controls_window_instance: Optional[QWidget] = None

    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle(f"Platformer Adventure LAN (PySide6)")
        
        screen_geo = QApplication.primaryScreen().availableGeometry()
        initial_width = max(800, min(1600, int(screen_geo.width() * 0.85)))
        initial_height = max(600, min(900, int(screen_geo.height() * 0.85)))
        self.setMinimumSize(QSize(800,600))
        self.resize(initial_width, initial_height)
        info(f"MAIN PySide6: Initial window size: {self.size().width()}x{self.size().height()}")

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
        self.current_view_name: Optional[str] = None # Tracks the active view in stacked_widget
        self.current_game_mode: Optional[str] = None # Tracks if a "game" (couch, host, client) is running

        self.server_state: Optional[ServerState] = None
        self.client_state: Optional[ClientState] = None
        self.network_thread: Optional[NetworkThread] = None
        self.lan_search_dialog: Optional[QDialog] = None

        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.game_tick)
        
        self.stacked_widget = QStackedWidget(self)
        self.main_menu_widget = self._create_main_menu_widget()
        self.game_scene_widget = GameSceneWidget(self.game_elements, self.fonts, self)
        
        self.editor_widget_container = self._create_view_container("Level Editor", "editor_view", self.on_return_to_menu_from_sub_view)
        self.settings_widget_container = self._create_view_container("Settings/Controls", "settings_view", self.on_return_to_menu_from_sub_view)

        self.stacked_widget.addWidget(self.main_menu_widget)           # Index 0: "menu"
        self.stacked_widget.addWidget(self.game_scene_widget)          # Index 1: "game_scene"
        self.stacked_widget.addWidget(self.editor_widget_container)    # Index 2: "editor"
        self.stacked_widget.addWidget(self.settings_widget_container)  # Index 3: "settings"
        
        self.setCentralWidget(self.stacked_widget)
        self.show_view("menu")

        self.network_status_update.connect(self.on_network_status_update)
        self.lan_server_search_status.connect(self.on_lan_server_search_status_update)
        self.status_dialog: Optional[QDialog] = None
        self.status_label_in_dialog: Optional[QLabel] = None
        self.status_progress_bar_in_dialog: Optional[QProgressBar] = None

    def _create_view_container(self, title_text: str, view_name_debug: str, back_slot: Slot) -> QWidget:
        container = QWidget()
        container.setObjectName(view_name_debug)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel(title_text)
        title_label.setFont(self.fonts["large"])
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # This is where the actual editor/settings widget will be added
        self.content_area_layout = QVBoxLayout() # Store this layout to add content later
        layout.addLayout(self.content_area_layout, 1) # Add with stretch factor

        # Add a "Back to Main Menu" button at the bottom
        back_button = QPushButton("Back to Main Menu")
        back_button.setFont(self.fonts["medium"])
        back_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        back_button.clicked.connect(back_slot)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(back_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return container
    
    def _ensure_editor_instance(self):
        if self.actual_editor_window_instance is None:
            try:
                from editor.editor import editor_main as launch_editor_module_func
                # This is tricky. editor_main() typically runs its own QApplication.
                # For integration, we need to instantiate its main window class.
                from editor.editor import EditorMainWindow as ActualEditorWindow
                
                # Critical: The EditorMainWindow might need its own QApplication if it wasn't designed
                # to be embedded. This can cause issues. For now, assume it can be a QWidget.
                # If EditorMainWindow creates its own app, this will fail or behave unexpectedly.
                self.actual_editor_window_instance = ActualEditorWindow() # This might need QApp management
                
                # Add the editor's central widget (or the window itself if it's a QWidget)
                # to the content area of our editor_widget_container
                editor_content_layout = self.editor_widget_container.layout().itemAt(1).layout() # QVBoxLayout
                if isinstance(self.actual_editor_window_instance, QMainWindow):
                     # If it's a QMainWindow, we take its central widget.
                     # This is a common pattern for embedding QMainWindows if they are complex.
                     editor_main_content = self.actual_editor_window_instance.centralWidget()
                     if editor_main_content:
                         self.actual_editor_window_instance.setParent(self.editor_widget_container) # Re-parent
                         editor_content_layout.addWidget(editor_main_content)
                     else: # Or add the whole QMainWindow if it's simple enough (less ideal)
                          editor_content_layout.addWidget(self.actual_editor_window_instance)
                elif isinstance(self.actual_editor_window_instance, QWidget):
                    editor_content_layout.addWidget(self.actual_editor_window_instance)
                else:
                    error("Editor window is not a QWidget or QMainWindow, cannot embed.")
                    self.actual_editor_window_instance = QLabel("Failed to load editor content.") # Fallback
                    editor_content_layout.addWidget(self.actual_editor_window_instance)

            except ImportError as e_imp:
                error(f"Failed to import editor modules for integration: {e_imp}")
                self.actual_editor_window_instance = QLabel(f"Error loading editor: Import failed.\n{e_imp}")
                self.editor_widget_container.layout().itemAt(1).layout().addWidget(self.actual_editor_window_instance)
            except Exception as e:
                error(f"Exception creating editor instance: {e}", exc_info=True)
                self.actual_editor_window_instance = QLabel(f"Error creating editor instance.\n{e}")
                self.editor_widget_container.layout().itemAt(1).layout().addWidget(self.actual_editor_window_instance)

    def _ensure_controls_mapper_instance(self):
        if self.actual_controls_window_instance is None:
            try:
                from controller_settings.controller_mapper_gui import MainWindow as ActualControlsWindow
                self.actual_controls_window_instance = ActualControlsWindow() # This also might manage its own app loop if run standalone
                
                controls_content_layout = self.settings_widget_container.layout().itemAt(1).layout()
                if isinstance(self.actual_controls_window_instance, QMainWindow):
                     controls_main_content = self.actual_controls_window_instance.centralWidget()
                     if controls_main_content:
                         self.actual_controls_window_instance.setParent(self.settings_widget_container)
                         controls_content_layout.addWidget(controls_main_content)
                     else: controls_content_layout.addWidget(self.actual_controls_window_instance)
                elif isinstance(self.actual_controls_window_instance, QWidget):
                    controls_content_layout.addWidget(self.actual_controls_window_instance)
                else:
                    error("Controls mapper window is not a QWidget or QMainWindow.")
                    self.actual_controls_window_instance = QLabel("Failed to load controls content.")
                    controls_content_layout.addWidget(self.actual_controls_window_instance)

            except ImportError as e_imp:
                error(f"Failed to import controls mapper modules for integration: {e_imp}")
                self.actual_controls_window_instance = QLabel(f"Error loading controls mapper: Import failed.\n{e_imp}")
                self.settings_widget_container.layout().itemAt(1).layout().addWidget(self.actual_controls_window_instance)
            except Exception as e:
                error(f"Exception creating controls mapper instance: {e}", exc_info=True)
                self.actual_controls_window_instance = QLabel(f"Error creating controls mapper instance.\n{e}")
                self.settings_widget_container.layout().itemAt(1).layout().addWidget(self.actual_controls_window_instance)


    def _translate_config_key_mappings(self):
        # ... (implementation from previous response)
        info("Translating keyboard mappings from config strings to Qt.Key values.")
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P1_MAPPINGS)
        self._apply_qt_key_translation_to_map_definition(game_config.DEFAULT_KEYBOARD_P2_MAPPINGS)
        if game_config.CURRENT_P1_INPUT_DEVICE.startswith("keyboard"): self._apply_qt_key_translation_to_map_definition(game_config.P1_MAPPINGS)
        if game_config.CURRENT_P2_INPUT_DEVICE.startswith("keyboard"): self._apply_qt_key_translation_to_map_definition(game_config.P2_MAPPINGS)
        info("Keyboard mapping translation complete.")

    def _apply_qt_key_translation_to_map_definition(self, mapping_dict: Dict[str, Any]):
        # ... (implementation from previous response)
        keys_to_update = list(mapping_dict.keys())
        for action_name in keys_to_update:
            key_val = mapping_dict.get(action_name)
            if isinstance(key_val, str):
                qt_key_enum = QT_KEY_MAP.get(key_val.upper())
                if qt_key_enum is not None: mapping_dict[action_name] = qt_key_enum
                elif len(key_val) == 1:
                    try:
                        key_from_seq = QKeySequence(key_val.upper())
                        if key_from_seq.count() > 0:
                             qt_enum_val = Qt.Key(key_from_seq[0].key())
                             if qt_enum_val != Qt.Key.Key_unknown: mapping_dict[action_name] = qt_enum_val; QT_KEY_MAP.setdefault(key_val.upper(), qt_enum_val)
                             # else: warning(f"ConfigTrans: '{key_val}' for '{action_name}' -> Key_unknown.") # Reduce noise
                        # else: warning(f"ConfigTrans: '{key_val}' for '{action_name}' not QKeySequence parsable.")
                    except Exception: pass # warning(f"ConfigTrans: Error parsing '{key_val}' for '{action_name}': {e_seq}.")
                # else: warning(f"ConfigTrans: Key str '{key_val}' for '{action_name}' not in QT_KEY_MAP & not single char.")


    def _create_main_menu_widget(self) -> QWidget:
        # ... (implementation from previous response, ensure Quit button calls self.request_close_app)
        menu_widget = QWidget(); layout = QVBoxLayout(menu_widget); layout.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.setSpacing(15)
        title_label = QLabel("Platformer Adventure LAN"); title_label.setFont(self.fonts["large"]); title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title_label)
        buttons_data = [
            ("Couch Co-op", self.on_start_couch_play), ("Host Game", self.on_start_host_game),
            ("Join LAN Game", self.on_start_join_lan), ("Join by IP", self.on_start_join_ip),
            ("Level Editor", lambda: self.show_view("editor")), ("Settings/Controls", lambda: self.show_view("settings")),
            ("Quit", self.request_close_app)
        ]
        for text, slot_func in buttons_data:
            button = QPushButton(text); button.setFont(self.fonts["medium"]); button.setMinimumHeight(40); button.setMinimumWidth(250)
            button.clicked.connect(slot_func); layout.addWidget(button)
        return menu_widget
    
    def request_close_app(self):
        info("MAIN PySide6: Quit action triggered, requesting main window close via self.close().")
        self.close()

    def on_return_to_menu_from_sub_view(self):
        # Potentially close/hide the editor/settings actual windows if they were managed
        if self.current_view_name == "editor" and self.actual_editor_window_instance:
            # self.actual_editor_window_instance.close() # Or hide() if it's a top-level window
            # If embedded, just switching the stack is enough.
            pass
        elif self.current_view_name == "settings" and self.actual_controls_window_instance:
            # self.actual_controls_window_instance.close() # Or hide()
            pass
        self.show_view("menu")

    def show_view(self, view_name: str):
        info(f"Switching view to: {view_name}")
        self.current_view_name = view_name # Track the UI view
        
        # If switching away from a game mode, ensure current_game_mode is cleared
        if view_name in ["menu", "editor", "settings"] and self.current_game_mode not in [None, "menu", "editor", "settings"]:
            self.stop_current_game_mode(show_menu=False) # Stop game logic but don't switch stack yet
        
        if self.game_timer.isActive() and view_name not in ["game_scene"]: # Game modes use "game_scene"
            debug(f"Stopping game timer as view switches to '{view_name}'")
            self.game_timer.stop()

        if view_name == "menu":
            self.stacked_widget.setCurrentWidget(self.main_menu_widget)
            self.setWindowTitle("Platformer Adventure LAN - Main Menu")
        elif view_name == "game_scene": # This is set by _prepare_and_start_game
            self.stacked_widget.setCurrentWidget(self.game_scene_widget)
            # Window title is set by _prepare_and_start_game
        elif view_name == "editor":
            self._ensure_editor_instance() # Load/create editor UI on demand
            self.stacked_widget.setCurrentWidget(self.editor_widget_container)
            self.setWindowTitle("Platformer - Level Editor")
        elif view_name == "settings":
            self._ensure_controls_mapper_instance() # Load/create settings UI on demand
            self.stacked_widget.setCurrentWidget(self.settings_widget_container)
            self.setWindowTitle("Platformer - Settings/Controls")
        
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        _qt_keys_pressed_snapshot.clear(); _qt_key_events_this_frame.clear()


    def show_main_menu_ui(self): self.show_view("menu")

    def keyPressEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame
        if not event.isAutoRepeat():
            qt_key = Qt.Key(event.key())
            _qt_keys_pressed_snapshot[qt_key] = True
            if self.current_game_mode in ["couch_play", "host", "join_lan", "join_ip"]: _qt_key_events_this_frame.append(event)
            if event.key() == Qt.Key.Key_Escape:
                if self.current_view_name == "menu": self.request_close_app()
                elif self.current_view_name in ["editor", "settings"]: self.show_view("menu")
                elif self.current_game_mode: info(f"Escape pressed in mode {self.current_game_mode}. Stopping mode."); self.stop_current_game_mode(show_menu=True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        global _qt_keys_pressed_snapshot
        if not event.isAutoRepeat(): _qt_keys_pressed_snapshot[Qt.Key(event.key())] = False
        super().keyReleaseEvent(event)
    
    def _get_input_snapshot(self, player_instance: Player, player_id: int) -> Dict[str, bool]:
        # ... (implementation from previous response)
        global _qt_keys_pressed_snapshot, _qt_key_events_this_frame, _joystick_axis_values_pyside, _joystick_button_states_pyside, _joystick_hat_values_pyside, _prev_joystick_button_states_pyside
        if not player_instance or not player_instance._valid_init: return {}
        active_mappings = {}; joystick_id_for_player: Optional[int] = None
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
        joystick_data_for_handler: Optional[Dict[str,Any]] = None
        if joystick_id_for_player is not None:
            joystick_data_for_handler = {
                'axes': _joystick_axis_values_pyside.get(joystick_id_for_player, {}),
                'buttons_current': _joystick_button_states_pyside.get(joystick_id_for_player, {}),
                'buttons_prev': _prev_joystick_button_states_pyside.get(joystick_id_for_player, {}),
                'hats': _joystick_hat_values_pyside.get(joystick_id_for_player, {})
            }
        action_events = process_player_input_logic(player_instance, _qt_keys_pressed_snapshot, _qt_key_events_this_frame, active_mappings, self.game_elements.get("platforms_list", []), joystick_data=joystick_data_for_handler)
        if joystick_id_for_player is not None: _prev_joystick_button_states_pyside[joystick_id_for_player] = _joystick_button_states_pyside.get(joystick_id_for_player, {}).copy()
        return action_events


    @staticmethod
    def get_p2_input_snapshot_for_client_thread(player_instance: Any) -> Dict[str, Any]:
        # ... (implementation from previous response)
        if MainWindow._instance:
            global _qt_keys_pressed_snapshot, _qt_key_events_this_frame # Need to access the globals
            return MainWindow._instance._get_input_snapshot(player_instance, 2)
        return {}

    def _prepare_and_start_game(self, mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
        info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
        current_width = self.game_scene_widget.width() or self.width()
        current_height = self.game_scene_widget.height() or self.height()

        # Use a default map if none is provided, especially for network modes
        if map_name is None and mode in ["host", "join_lan", "join_ip"]:
            map_name = C.DEFAULT_LEVEL_MODULE_NAME if hasattr(C, 'DEFAULT_LEVEL_MODULE_NAME') else "level_default"
            info(f"No map specified for network mode, defaulting to: {map_name}")

        initialized_elements = initialize_game_elements(current_width, current_height, mode, None, map_name)
        if initialized_elements is None:
            QMessageBox.critical(self, "Error", f"Failed to initialize game elements for {mode} with map '{map_name}'. Check logs.")
            self.show_view("menu"); return

        self.game_elements.clear(); self.game_elements.update(initialized_elements)
        self.current_game_mode = mode # This tracks the logical game mode (couch, host, etc.)
        self.setWindowTitle(f"Platformer Adventure LAN - {mode.replace('_',' ').title()}")
        camera = self.game_elements.get("camera")
        if camera:
            camera.set_screen_dimensions(self.game_scene_widget.width(), self.game_scene_widget.height())
            if "level_pixel_width" in self.game_elements:
                camera.set_level_dimensions( self.game_elements["level_pixel_width"], self.game_elements["level_min_y_absolute"], self.game_elements["level_max_y_absolute"])
        
        self.game_scene_widget.game_elements = self.game_elements # Update scene's reference
        self.show_view("game_scene") # Switch QStackedWidget to show the game scene

        if mode in ["host", "join_lan", "join_ip"]: self._start_network_mode(mode, target_ip_port)
        
        if not self.game_timer.isActive(): # Start timer only if not already running
            self.game_timer.start(1000 // C.FPS)
        info(f"Game mode '{mode}' started.")

    def on_start_couch_play(self): map_name = self._select_map_dialog(); self._prepare_and_start_game("couch_play", map_name=map_name if map_name else "level_default")
    def on_start_host_game(self): map_name = self._select_map_dialog(); self._prepare_and_start_game("host", map_name=map_name if map_name else "level_default")
    def on_start_join_lan(self): self._show_lan_search_dialog() # This will call _prepare_and_start_game
    def on_start_join_ip(self):
        dialog = IPInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.ip_port_string:
            self._prepare_and_start_game("join_ip", target_ip_port=dialog.ip_port_string) # Map chosen by server
        else: info("Join by IP cancelled."); self.show_view("menu")
            
    def _select_map_dialog(self) -> Optional[str]:
        dialog = SelectMapDialog(self.fonts, self)
        return dialog.selected_map_name if dialog.exec() == QDialog.DialogCode.Accepted else None

    def _start_network_mode(self, mode_name: str, target_ip_port: Optional[str] = None):
        # ... (implementation from previous response)
        if self.network_thread and self.network_thread.isRunning(): warning("NetworkThread already running. Stopping old one."); self.network_thread.quit(); self.network_thread.wait(1000)
        if mode_name == "host": self.server_state = ServerState(); self.server_state.current_map_name = self.game_elements.get("loaded_map_name"); self.server_state.app_running = self.app_status.app_running; self.network_thread = NetworkThread("host", self.game_elements, self.server_state, parent=self)
        elif mode_name in ["join_lan", "join_ip"]: self.client_state = ClientState(); self.client_state.app_running = self.app_status.app_running; self.network_thread = NetworkThread("join", self.game_elements, client_state_ref=self.client_state, target_ip_port=target_ip_port, parent=self)
        if self.network_thread: self.network_thread.status_update_signal.connect(self.on_network_status_update); self.network_thread.operation_finished_signal.connect(self.on_network_operation_finished); self.network_thread.start(); self._show_status_dialog("Network Operation", f"Initializing {mode_name} mode...")
        else: error(f"Failed to create NetworkThread for {mode_name}"); self.show_view("menu")


    def _show_status_dialog(self, title: str, initial_message: str):
        # ... (implementation from previous response)
        if self.status_dialog is None:
            self.status_dialog = QDialog(self); self.status_dialog.setWindowTitle(title); layout = QVBoxLayout(self.status_dialog); self.status_label_in_dialog = QLabel(initial_message)
            self.status_label_in_dialog.setWordWrap(True); layout.addWidget(self.status_label_in_dialog); self.status_progress_bar_in_dialog = QProgressBar(); self.status_progress_bar_in_dialog.setRange(0,100)
            self.status_progress_bar_in_dialog.setTextVisible(True); layout.addWidget(self.status_progress_bar_in_dialog); self.status_dialog.setMinimumWidth(350)
        else: self.status_dialog.setWindowTitle(title);
        if self.status_label_in_dialog: self.status_label_in_dialog.setText(initial_message)
        if self.status_progress_bar_in_dialog: self.status_progress_bar_in_dialog.setValue(0); self.status_progress_bar_in_dialog.setVisible(False)
        self.status_dialog.show(); QApplication.processEvents()

    def _update_status_dialog(self, message: str, progress: float = -1.0):
        # ... (implementation from previous response)
        if self.status_dialog and self.status_dialog.isVisible():
            if self.status_label_in_dialog: self.status_label_in_dialog.setText(message)
            if self.status_progress_bar_in_dialog:
                if progress >= 0: self.status_progress_bar_in_dialog.setValue(int(progress)); self.status_progress_bar_in_dialog.setVisible(True)
                else: self.status_progress_bar_in_dialog.setVisible(False)
        QApplication.processEvents()


    def _close_status_dialog(self):
        # ... (implementation from previous response)
        if self.status_dialog: self.status_dialog.hide()


    @Slot(str, str, float)
    def on_network_status_update(self, title: str, message: str, progress: float):
        # ... (implementation from previous response)
        if not self.status_dialog or not self.status_dialog.isVisible(): self._show_status_dialog(title, message)
        self._update_status_dialog(message, progress)
        if title in ["game_starting", "game_active"] or (title == "Map Sync" and "ready" in message.lower() and progress >= 100): self._close_status_dialog()


    @Slot(str)
    def on_network_operation_finished(self, message: str):
        # ... (implementation from previous response)
        info(f"Network operation finished: {message}"); self._close_status_dialog()
        if "error" in message.lower() or "failed" in message.lower(): QMessageBox.critical(self, "Network Error", f"Network op ended with error: {message}"); self.stop_current_game_mode(show_menu=True)
        elif "ended" in message.lower(): info(f"Mode {self.current_game_mode} finished normally via network."); self.stop_current_game_mode(show_menu=True)


    def _show_lan_search_dialog(self):
        # ... (implementation from previous response)
        if self.lan_search_dialog is None:
            self.lan_search_dialog = QDialog(self); self.lan_search_dialog.setWindowTitle("Searching for LAN Games..."); layout = QVBoxLayout(self.lan_search_dialog); self.lan_search_status_label = QLabel("Searching...")
            layout.addWidget(self.lan_search_status_label); self.lan_servers_list_widget = QListWidget(); layout.addWidget(self.lan_servers_list_widget)
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
            button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False); button_box.accepted.connect(self._join_selected_lan_server)
            button_box.rejected.connect(self.lan_search_dialog.reject); button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self._start_lan_server_search_thread)
            layout.addWidget(button_box); self.lan_search_dialog.rejected.connect(lambda: self.show_view("menu")); self.lan_servers_list_widget.itemDoubleClicked.connect(self._join_selected_lan_server)
        self.lan_servers_list_widget.clear(); self.lan_search_status_label.setText("Searching..."); self.lan_search_dialog.show(); self._start_lan_server_search_thread()


    def _start_lan_server_search_thread(self):
        # ... (implementation from previous response)
        if self.lan_servers_list_widget: self.lan_servers_list_widget.clear()
        if self.lan_search_status_label: self.lan_search_status_label.setText("Searching...")
        if self.lan_search_dialog and hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.lan_search_worker = QThread()
        class LanSearchRunner(QWidget): # Needs to be QObject for signals if methods are slots
            found_signal = Signal(object)
            def __init__(self, client_state): super().__init__(); self.cs = client_state
            @Slot() # Make it a slot if connected to thread.started
            def run_search(self):
                result = find_server_on_lan(self.cs, lambda key, data: self.found_signal.emit((key, data)))
                # Emit even if result is None to signal completion
                self.found_signal.emit(("final_result", result)) # Ensure always emits final_result
        temp_client_state_for_search = ClientState()
        self.lan_search_run_obj = LanSearchRunner(temp_client_state_for_search)
        self.lan_search_run_obj.moveToThread(self.lan_search_worker)
        self.lan_search_worker.started.connect(self.lan_search_run_obj.run_search)
        self.lan_search_run_obj.found_signal.connect(self.on_lan_server_search_status_update) # This slot is in MainWindow
        self.lan_search_worker.finished.connect(self.lan_search_worker.deleteLater); self.lan_search_worker.finished.connect(self.lan_search_run_obj.deleteLater)
        self.lan_search_worker.start()


    @Slot(object) # Changed from (str, object) to just object as emit is (key,data) tuple
    def on_lan_server_search_status_update(self, data_tuple: Any): # data_tuple is (key, data)
        if not self.lan_search_dialog or not self.lan_search_dialog.isVisible(): return
        if not isinstance(data_tuple, tuple) or len(data_tuple) != 2: return # Basic validation
        status_key, data = data_tuple

        if self.lan_search_status_label: self.lan_search_status_label.setText(f"Status: {status_key} - {str(data)[:50]}")
        if status_key == "found" and isinstance(data, tuple) and len(data)==2:
            ip, port = data; item_text = f"Server at {ip}:{port}"
            self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
            if hasattr(self.lan_search_dialog, 'button_box'): self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        elif status_key == "timeout" or status_key == "error" or (status_key == "final_result" and data is None):
            if self.lan_servers_list_widget.count() == 0:
                 self.lan_search_status_label.setText(f"Search ended: {status_key}. No servers found.")
                 self.lan_servers_list_widget.addItem("No servers found. Retry or Cancel.")
        elif status_key == "final_result" and data is not None: # Search thread finished with a result
             ip, port = data; item_text = f"Server at {ip}:{port}"
             if not self.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly):
                 self.lan_servers_list_widget.addItem(QListWidgetItem(item_text, data=f"{ip}:{port}"))
             if self.lan_servers_list_widget.count() > 0 and hasattr(self.lan_search_dialog, 'button_box'):
                 self.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        if status_key == "final_result": # Search is complete
            if self.lan_search_worker and self.lan_search_worker.isRunning():
                self.lan_search_worker.quit() # Request thread to stop
                self.lan_search_worker.wait(500) # Wait a bit


    def _join_selected_lan_server(self):
        # ... (implementation from previous response)
        if not self.lan_servers_list_widget or not self.lan_search_dialog: return
        selected_items = self.lan_servers_list_widget.selectedItems()
        if selected_items:
            ip_port_str = selected_items[0].data(Qt.ItemDataRole.UserRole) # data is the "ip:port" string
            if ip_port_str: self.lan_search_dialog.accept(); self._prepare_and_start_game("join_lan", target_ip_port=ip_port_str); return
        QMessageBox.warning(self, "No Selection", "Please select a server from the list.")


    def game_tick(self):
        global _qt_key_events_this_frame
        
        # Stop game logic if not in an active game mode shown on game_scene_widget
        if self.current_view_name != "game_scene" or not self.app_status.app_running or not self.current_game_mode:
            if self.game_timer.isActive(): self.game_timer.stop() # Stop timer if not in game scene
            # If current_game_mode is set but view is not game_scene, it means we switched away
            if self.current_game_mode and self.current_game_mode not in ["menu", "editor", "settings"]:
                self.stop_current_game_mode(show_menu=False) # Stop logic but don't switch UI
            _qt_key_events_this_frame.clear()
            return

        dt_sec = 1.0 / float(C.FPS)
        current_game_time = get_current_game_ticks()
        
        p1 = self.game_elements.get("player1"); p1_input_actions: Dict[str,bool] = {}
        if p1 and p1._valid_init and self.current_game_mode in ["host", "couch_play"]:
            p1_input_actions = self._get_input_snapshot(p1, 1)
            if p1_input_actions.get("pause"):
                info(f"Main {self.current_game_mode}: P1 Pause. Stopping mode."); self.stop_current_game_mode(show_menu=True); return

        if self.current_game_mode == "couch_play":
            p2 = self.game_elements.get("player2"); p2_input_actions_couch: Dict[str,bool] = {}
            if p2 and p2._valid_init: p2_input_actions_couch = self._get_input_snapshot(p2, 2)
            should_continue = run_couch_play_mode(self.game_elements, self.app_status, lambda _p, _plats: p1_input_actions, lambda _p, _plats: p2_input_actions_couch, lambda: QApplication.processEvents(), lambda: dt_sec, lambda msg: self.statusBar().showMessage(msg, 2000))
            if not should_continue or not self.app_status.app_running: self.stop_current_game_mode(show_menu=True); return
        
        dl_msg, dl_prog = None, None
        if self.client_state and self.current_game_mode in ["join_lan", "join_ip"]:
            if self.client_state.map_download_status not in ["present", "unknown", "game_active"]:
                dl_msg = f"Map: {self.client_state.server_selected_map_name or '...'} - Status: {self.client_state.map_download_status}"
                dl_prog = self.client_state.map_download_progress
        
        self.game_scene_widget.update_game_state(current_game_time, dl_msg, dl_prog)
        _qt_key_events_this_frame.clear()

    def stop_current_game_mode(self, show_menu: bool = True):
        mode_stopped = self.current_game_mode; info(f"Stopping game mode: {mode_stopped}")
        self.current_game_mode = None # Clear logical game mode
        if self.game_timer.isActive(): self.game_timer.stop()
        if self.network_thread and self.network_thread.isRunning():
            info("Requesting network thread to stop...");
            if self.server_state: self.server_state.app_running = False
            if self.client_state: self.client_state.app_running = False
            self.network_thread.quit(); 
            if not self.network_thread.wait(1500): warning("Network thread did not stop gracefully. Terminating."); self.network_thread.terminate(); self.network_thread.wait(500)
            info("Network thread stopped.")
        self.network_thread = None; self.server_state = None; self.client_state = None
        self._close_status_dialog()
        if self.lan_search_dialog and self.lan_search_dialog.isVisible(): self.lan_search_dialog.reject()
        self.game_elements.clear(); self.game_scene_widget.game_elements = self.game_elements
        if show_menu: self.show_view("menu") # Use show_view to handle UI transition
        info(f"Game mode '{mode_stopped}' stopped and cleaned.")

    def closeEvent(self, event: QCloseEvent):
        info("Close event received. Shutting down application.")
        self.app_status.quit_app() # This now also calls QApplication.quit()
        self.stop_current_game_mode(show_menu=False)
        joystick_handler.quit_joysticks()
        # Ensure actual editor/settings are closed if they were instantiated
        if self.actual_editor_window_instance and hasattr(self.actual_editor_window_instance, 'close'):
            self.actual_editor_window_instance.close()
        if self.actual_controls_window_instance and hasattr(self.actual_controls_window_instance, 'close'):
            self.actual_controls_window_instance.close()
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
    if APP_STATUS.app_running: APP_STATUS.quit_app() # Final safety net
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        critical(f"MAIN PySide6 CRITICAL UNHANDLED EXCEPTION: {e}", exc_info=True)
        try:
            error_app = QApplication.instance();
            if not error_app: error_app = QApplication(sys.argv)
            msg_box = QMessageBox(); msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred and the application must close.")
            msg_box.setInformativeText(f"{e}\n\nDetails in {LOG_FILE_PATH if LOGGING_ENABLED else 'console'}.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok); msg_box.exec()
        except Exception as e_msgbox: print(f"FATAL: Could not display Qt error message box: {e_msgbox}")
        traceback.print_exc(); sys.exit(1)