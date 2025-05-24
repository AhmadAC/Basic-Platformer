#################### START OF FILE: editor\editor.py ####################

# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.12 (Circular import fix for editor_ui_panels)
Level Editor for the Platformer Game (PySide6 Version).
Allows creating, loading, and saving game levels visually.
Adds foundational support for Nintendo Switch controller navigation.
"""
import sys
import os
import logging
import traceback
import time # For controller axis repeat timing
from typing import Optional, Tuple, List, Any, Dict

# --- Determine execution context and adjust sys.path if run standalone ---
_IS_STANDALONE_EXECUTION = (__name__ == "__main__")
_EDITOR_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_DIR = os.path.dirname(_EDITOR_MODULE_DIR)

if _IS_STANDALONE_EXECUTION:
    print(f"INFO: editor.py running in standalone mode from: {_EDITOR_MODULE_DIR}")
    if _PROJECT_ROOT_DIR not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT_DIR)
        print(f"INFO: Added project root '{_PROJECT_ROOT_DIR}' to sys.path for standalone execution.")
    print(f"INFO: Current sys.path[0]: {sys.path[0]}")
else:
    print(f"INFO: editor.py running as a module (package: {__package__})")

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, QFileDialog,
    QColorDialog, QInputDialog, QLabel, QSizePolicy
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent, QImage, QPainter, QFont
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF,Signal, QPoint
# --- Game Controller Support (Pygame) ---
try:
    import pygame
    _PYGAME_AVAILABLE = True
    logger_init_pygame = logging.getLogger("PygameInit") # Temp logger before main one
    logger_init_pygame.info("Pygame imported successfully for controller support.")
except ImportError:
    _PYGAME_AVAILABLE = False
    logger_init_pygame = logging.getLogger("PygameInit")
    logger_init_pygame.warning("Pygame not found. Controller navigation will be unavailable.")


# --- Attempt to import editor-specific modules ---
# This block needs to come before logger setup if logger uses ED_CONFIG
_IMPORTS_SUCCESSFUL_METHOD = "Unknown"
try:
    # Attempt relative imports first
    logger_init_pygame.info("Attempting relative imports for editor modules...")
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_assets
    from . import editor_map_utils
    from . import editor_history
    from .map_view_widget import MapViewWidget, MapObjectItem
    from .editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    from .editor_actions import * # Import action constants


    if ED_CONFIG.MINIMAP_ENABLED: # type: ignore
        from .minimap_widget import MinimapWidget
    if _PYGAME_AVAILABLE:
        # Assuming config.py is in the project root, one level above 'editor'
        from config import init_pygame_and_joystick_globally, get_joystick_objects

    _IMPORTS_SUCCESSFUL_METHOD = "Relative"
    logger_init_pygame.info("Editor modules imported successfully using RELATIVE paths.")

except ImportError as e_relative_import:
    logger_init_pygame.warning(f"Relative import failed: {e_relative_import}. Attempting absolute imports.")
    if not _IS_STANDALONE_EXECUTION:
        logger_init_pygame.warning("Relative import failed even when run as a module. This might indicate a packaging issue.")
    
    try:
        from editor import editor_config as ED_CONFIG # type: ignore
        from editor.editor_state import EditorState # type: ignore
        from editor import editor_assets # type: ignore
        from editor import editor_map_utils # type: ignore
        from editor import editor_history # type: ignore
        from editor.map_view_widget import MapViewWidget, MapObjectItem # type: ignore
        from editor.editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget # type: ignore
        from editor.editor_actions import * # type: ignore

        if ED_CONFIG.MINIMAP_ENABLED: # type: ignore
            from editor.minimap_widget import MinimapWidget # type: ignore
        if _PYGAME_AVAILABLE:
            from config import init_pygame_and_joystick_globally, get_joystick_objects # type: ignore
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (from editor.*)"
        logger_init_pygame.info("Editor modules imported successfully using ABSOLUTE paths (from editor.*).")
    except ImportError as e_absolute_import:
        logger_init_pygame.critical(f"CRITICAL: Both relative and absolute imports for editor modules failed.")
        logger_init_pygame.critical(f"  Relative import error: {e_relative_import}")
        logger_init_pygame.critical(f"  Absolute import error: {e_absolute_import}")
        logger_init_pygame.critical(f"  Current sys.path: {sys.path}")
        raise ImportError(f"Failed to import critical editor modules. Relative: {e_relative_import}. Absolute: {e_absolute_import}") from e_absolute_import
    except AttributeError as e_attr_config_check: 
        logger_init_pygame.critical(f"CRITICAL: AttributeError during absolute import phase, likely ED_CONFIG not loaded: {e_attr_config_check}")
        raise AttributeError(f"Failed due to ED_CONFIG not being available: {e_attr_config_check}") from e_attr_config_check


# --- Logger Setup (now that ED_CONFIG is expected to be loaded) ---
logger: Optional[logging.Logger] = None 
log_file_path_for_error_msg = "editor_qt_debug.log" 
try:
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs') 
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    
    log_file_name = ED_CONFIG.LOG_FILE_NAME if hasattr(ED_CONFIG, "LOG_FILE_NAME") else "editor_qt_debug.log" # type: ignore
    log_file_path_for_error_msg = os.path.join(logs_dir, log_file_name)
    
    log_level_str = ED_CONFIG.LOG_LEVEL.upper() if hasattr(ED_CONFIG, "LOG_LEVEL") else "DEBUG" # type: ignore
    numeric_log_level = getattr(logging, log_level_str, logging.DEBUG)
    
    log_format_str = ED_CONFIG.LOG_FORMAT if hasattr(ED_CONFIG, "LOG_FORMAT") else \
                     '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s' # type: ignore

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close() 

    logging.basicConfig(
        level=numeric_log_level,
        format=log_format_str,
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')]
    )
    logger = logging.getLogger("EditorMainWindowLogger") 
    logger.info(f"Editor session started. Logging initialized successfully to '{log_file_path_for_error_msg}'. Imports via: {_IMPORTS_SUCCESSFUL_METHOD}")
except Exception as e_log_setup:
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE FALLBACK (editor.py logger setup): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("EditorMainWindowLogger_Fallback") 
    logger.error(f"CRITICAL ERROR DURING FILE LOGGING SETUP (editor.py): {e_log_setup}. Using console.", exc_info=True)
    logger.info(f"Imports were attempted via: {_IMPORTS_SUCCESSFUL_METHOD}")
# --- End Logger Setup ---

# Nintendo Switch Pro Controller (Common Pygame Button/Axis/Hat IDs) - Simplified
# Buttons (Indices for joy.get_button())
SWITCH_A_BTN = 0      # Typically 'A' on Switch, 'Cross' on PS, 'A' on Xbox
SWITCH_B_BTN = 1      # Typically 'B' on Switch, 'Circle' on PS, 'B' on Xbox
SWITCH_X_BTN = 2      # Typically 'X' on Switch, 'Square' on PS, 'X' on Xbox
SWITCH_Y_BTN = 3      # Typically 'Y' on Switch, 'Triangle' on PS, 'Y' on Xbox
SWITCH_L_BTN = 4      # L bumper
SWITCH_R_BTN = 5      # R bumper
SWITCH_ZL_BTN = 6     # ZL trigger (might also be an axis)
SWITCH_ZR_BTN = 7     # ZR trigger (might also be an axis)
SWITCH_MINUS_BTN = 8  # Minus / Select / Back
SWITCH_PLUS_BTN = 9   # Plus / Start
SWITCH_L_STICK_BTN = 10
SWITCH_R_STICK_BTN = 11
# Axes (Indices for joy.get_axis())
SWITCH_L_STICK_X_AXIS = 0
SWITCH_L_STICK_Y_AXIS = 1
SWITCH_R_STICK_X_AXIS = 2 # Often R stick X
SWITCH_R_STICK_Y_AXIS = 3 # Often R stick Y
SWITCH_ZL_AXIS = 4        # Sometimes ZL is an axis
SWITCH_ZR_AXIS = 5        # Sometimes ZR is an axis
# Hat (D-Pad) (Index for joy.get_hat())
SWITCH_DPAD_HAT_ID = 0


class EditorMainWindow(QMainWindow):
    controller_action_dispatched = Signal(str, object) # action_name, value (e.g., axis value or None for buttons)

    def __init__(self, parent: Optional[QWidget] = None, embed_mode: bool = False):
        super().__init__(parent) 
        self._is_embedded = embed_mode 
        logger.info(f"Initializing EditorMainWindow... Embedded: {self._is_embedded}")

        self.editor_state = EditorState()
        self.settings = QSettings("MyPlatformerGame", "LevelEditor_Qt")
        
        self.init_ui() # _focusable_panels populated here
        self.create_actions()
        self.create_menus()
        self.create_status_bar()

        self.asset_palette_dock.setObjectName("AssetPaletteDock")
        self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock: # type: ignore
            self.minimap_dock.setObjectName("MinimapDock")

        editor_assets.load_editor_palette_assets(self.editor_state, self) # type: ignore
        self.asset_palette_widget.populate_assets()

        if not self._is_embedded: 
            self.update_window_title()
        self.update_edit_actions_enabled_state()

        # --- Controller Navigation Setup ---
        self._current_focused_panel_index: int = 0 
        self._controller_input_timer: Optional[QTimer] = None
        self._joysticks: List[pygame.joystick.Joystick] = [] # type: ignore
        self._primary_joystick: Optional[pygame.joystick.Joystick] = None # type: ignore
        
        self._controller_axis_deadzone = 0.4 
        self._controller_axis_last_event_time: Dict[Tuple[int, int, int], float] = {} # (joy_idx, axis_idx, direction_sign) -> timestamp
        self._controller_axis_repeat_delay = 0.3 
        self._controller_axis_repeat_interval = 0.1 
        self._last_dpad_value: Optional[Tuple[int, int]] = None
        self._button_last_state: Dict[int, bool] = {} # joy_btn_id -> pressed_state


        if _PYGAME_AVAILABLE:
            self._init_controller_system()
            self.controller_action_dispatched.connect(self._dispatch_controller_action_to_panel)
        # --- End Controller Navigation Setup ---

        if not self._is_embedded:
            restored_successfully = self.restore_geometry_and_state()
            if restored_successfully:
                logger.info("Standalone mode: Restored geometry/state, showing window with restored settings.")
                self.show() 
            else:
                logger.info("Standalone mode: No saved geometry/state or restoration failed. Showing maximized.")
                primary_screen = QApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH # type: ignore
                    default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                    pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                    pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                else: 
                    self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
                self.showMaximized() 
        else: 
            logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            self.restore_geometry_and_state()

        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
            err_msg_maps_dir = f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}" # type: ignore
            logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox displayed by editor itself)")
            if not self._is_embedded: 
                QMessageBox.critical(self, "Error", err_msg_maps_dir)
        
        logger.info("EditorMainWindow initialized.")
        if hasattr(self, 'status_bar') and self.status_bar:
            self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore
        else:
            logger.info("Status: Editor started. Welcome! (Status bar not used or not yet available).")

        if self._focusable_panels and _PYGAME_AVAILABLE and self._primary_joystick:
            self._set_panel_controller_focus(0)
        elif self._focusable_panels: 
            self._focusable_panels[0].setFocus(Qt.FocusReason.OtherFocusReason)


    def init_ui(self):
        logger.debug("Initializing UI components...")
        self._focusable_panels: List[QWidget] = [] 
        
        self.map_view_widget = MapViewWidget(self.editor_state, self) # type: ignore
        self.setCentralWidget(self.map_view_widget)
        self._focusable_panels.append(self.map_view_widget)

        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self) # type: ignore
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(max(200, ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50)) # type: ignore
        self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 100) # type: ignore
        self._focusable_panels.append(self.asset_palette_widget)


        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self) # type: ignore
        self.properties_editor_dock.setWidget(self.properties_editor_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_editor_dock)
        self.properties_editor_dock.setMinimumWidth(280)
        self._focusable_panels.append(self.properties_editor_widget)

        if ED_CONFIG.MINIMAP_ENABLED: # type: ignore
            self.minimap_dock = QDockWidget("Minimap", self)
            self.minimap_widget = MinimapWidget(self.editor_state, self.map_view_widget, self) # type: ignore
            self.minimap_dock.setWidget(self.minimap_widget)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock) 
            self.splitDockWidget(self.minimap_dock, self.properties_editor_dock, Qt.Orientation.Vertical) 
            self.minimap_dock.setFixedHeight(ED_CONFIG.MINIMAP_DEFAULT_HEIGHT + 35) # type: ignore
        else:
            self.minimap_dock = None # type: ignore
            self.minimap_widget = None # type: ignore

        self.asset_palette_widget.asset_selected.connect(self.map_view_widget.on_asset_selected)
        self.asset_palette_widget.asset_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)
        self.asset_palette_widget.paint_color_changed_for_status.connect(self.show_status_message)
        self.asset_palette_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)


        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)

        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed) 
        self.properties_editor_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)


        if self.minimap_widget: 
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs)
        logger.debug("UI components initialized.")

    def _init_controller_system(self):
        logger.info("Initializing controller system...")
        try:
            init_pygame_and_joystick_globally(force_rescan=True)
            self._joysticks = get_joystick_objects() # type: ignore
            
            if not self._joysticks or all(joy is None for joy in self._joysticks): # type: ignore
                logger.info("No joysticks detected by Pygame or all are None.")
                self._primary_joystick = None
                return

            for i, joy in enumerate(self._joysticks): # type: ignore
                if joy:
                    try:
                        if not joy.get_init(): joy.init()
                        self._primary_joystick = joy
                        logger.info(f"Primary joystick set to: {joy.get_name()} (Index: {i}, GUID: {joy.get_guid()})")
                        break
                    except pygame.error as e:
                        logger.warning(f"Could not initialize joystick {i} ({joy.get_name()}): {e}")
            
            if not self._primary_joystick:
                logger.warning("No valid joystick could be initialized as primary.")
                return
            
            self._controller_input_timer = QTimer(self)
            self._controller_input_timer.setInterval(getattr(ED_CONFIG, "CONTROLLER_POLL_INTERVAL_MS", 16)) # type: ignore
            self._controller_input_timer.timeout.connect(self._poll_controller_input)
            self._controller_input_timer.start()
            logger.info("Controller input polling timer started.")

        except Exception as e:
            logger.error(f"Error initializing controller system: {e}", exc_info=True)
            self._primary_joystick = None


    def _poll_controller_input(self):
        if not _PYGAME_AVAILABLE or not self._primary_joystick:
            return
        
        pygame.event.pump() 
        current_time = time.monotonic()
        joy = self._primary_joystick
        if not joy.get_init():
            try: joy.init()
            except pygame.error: return

        # --- Buttons ---
        # Mapping for Switch Pro Controller (adjust button IDs if needed for other controllers)
        button_map = {
            SWITCH_B_BTN: ACTION_UI_ACCEPT,         # B for accept (like A on Xbox/PS)
            SWITCH_A_BTN: ACTION_UI_CANCEL,         # A for cancel (like B on Xbox/PS)
            SWITCH_Y_BTN: ACTION_MAP_TOOL_PRIMARY,  # Y
            SWITCH_X_BTN: ACTION_MAP_TOOL_SECONDARY, # X
            SWITCH_L_BTN: ACTION_UI_TAB_PREV,       
            SWITCH_R_BTN: ACTION_UI_TAB_NEXT,       
            SWITCH_ZL_BTN: ACTION_MAP_ZOOM_OUT,     
            SWITCH_ZR_BTN: ACTION_MAP_ZOOM_IN,      
            SWITCH_PLUS_BTN: ACTION_UI_MENU,        
            SWITCH_MINUS_BTN: ACTION_UI_FOCUS_NEXT, 
        }
        for btn_id, action in button_map.items():
            if btn_id >= joy.get_numbuttons(): continue
            pressed = joy.get_button(btn_id)
            last_state = self._button_last_state.get(btn_id, False)
            if pressed and not last_state: # Pressed just now
                self.controller_action_dispatched.emit(action, True) 
            self._button_last_state[btn_id] = pressed

        # --- D-Pad (Hat) ---
        if joy.get_numhats() > 0:
            hat_value = joy.get_hat(SWITCH_DPAD_HAT_ID)
            if hat_value != self._last_dpad_value: 
                # Using a simplified approach: any change in D-pad triggers one event
                # For continuous scrolling in lists, the receiving widget must handle repeated calls
                if hat_value == (0, 1): self.controller_action_dispatched.emit(ACTION_UI_UP, None)
                elif hat_value == (0, -1): self.controller_action_dispatched.emit(ACTION_UI_DOWN, None)
                elif hat_value == (-1, 0): self.controller_action_dispatched.emit(ACTION_UI_LEFT, None)
                elif hat_value == (1, 0): self.controller_action_dispatched.emit(ACTION_UI_RIGHT, None)
                self._last_dpad_value = hat_value
        
        # --- Analog Sticks (Left Stick for UI navigation, Right Stick for Camera) ---
        axis_map = {
            SWITCH_L_STICK_X_AXIS: (ACTION_UI_LEFT, ACTION_UI_RIGHT),
            SWITCH_L_STICK_Y_AXIS: (ACTION_UI_UP, ACTION_UI_DOWN), 
            SWITCH_R_STICK_Y_AXIS: (ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN), # Added right stick Y
            # SWITCH_R_STICK_X_AXIS: (ACTION_CAMERA_PAN_LEFT, ACTION_CAMERA_PAN_RIGHT), # For horizontal camera pan
        }
        for axis_id, actions in axis_map.items():
            if axis_id >= joy.get_numaxes(): continue
            
            axis_val = joy.get_axis(axis_id)
            direction_sign = 0
            if axis_val < -self._controller_axis_deadzone: direction_sign = -1
            elif axis_val > self._controller_axis_deadzone: direction_sign = 1
            
            key = (joy.get_id(), axis_id, direction_sign)
            
            action_to_emit: Optional[str] = None
            if direction_sign == -1: action_to_emit = actions[0]
            elif direction_sign == 1: action_to_emit = actions[1]

            if action_to_emit:
                # For camera pan actions, we might want to emit the continuous value.
                # For UI navigation, we use the repeat delay/interval.
                if action_to_emit.startswith("CAMERA_PAN_"):
                    self.controller_action_dispatched.emit(action_to_emit, axis_val)
                else: # UI Navigation actions
                    last_event_time_for_key_dir = self._controller_axis_last_event_time.get(key, 0)
                    can_emit = False
                    if current_time - last_event_time_for_key_dir > self._controller_axis_repeat_delay: 
                        can_emit = True
                    elif current_time - last_event_time_for_key_dir > self._controller_axis_repeat_interval: 
                        can_emit = True
                    if can_emit:
                        self.controller_action_dispatched.emit(action_to_emit, axis_val)
                        self._controller_axis_last_event_time[key] = current_time
            else: # Axis back in deadzone for this direction
                 key_neg = (joy.get_id(), axis_id, -1)
                 key_pos = (joy.get_id(), axis_id, 1)
                 if key_neg in self._controller_axis_last_event_time:
                     self._controller_axis_last_event_time[key_neg] = 0
                 if key_pos in self._controller_axis_last_event_time:
                     self._controller_axis_last_event_time[key_pos] = 0


    @Slot(str, object)
    def _dispatch_controller_action_to_panel(self, action: str, value: Any):
        logger.debug(f"Controller action received by MainWindow: {action}, Value: {value}")

        if action == ACTION_UI_FOCUS_NEXT:
            self._cycle_panel_focus_next()
            return
        elif action == ACTION_UI_FOCUS_PREV: # Not mapped currently, but for completeness
            self._cycle_panel_focus_prev()
            return
        elif action == ACTION_UI_MENU:
            if self.menu_bar and self.menu_bar.actions():
                first_menu = self.menu_bar.actions()[0].menu()
                if first_menu:
                    first_menu.popup(self.mapToGlobal(self.menu_bar.pos() + QPoint(0, self.menu_bar.height())))
            return
        # MODIFIED: Handle camera pan actions specifically targeting MapViewWidget
        elif action.startswith("CAMERA_PAN_"):
            if hasattr(self.map_view_widget, "handle_controller_camera_pan"):
                try:
                    self.map_view_widget.handle_controller_camera_pan(action, value)
                except Exception as e:
                    logger.error(f"Error in MapViewWidget.handle_controller_camera_pan for '{action}': {e}", exc_info=True)
            else:
                logger.warning(f"MapViewWidget has no handle_controller_camera_pan method for action '{action}'.")
            return

        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
            focused_widget = self._focusable_panels[self._current_focused_panel_index]
            if hasattr(focused_widget, "handle_controller_action"):
                try:
                    focused_widget.handle_controller_action(action, value) # type: ignore
                except Exception as e:
                    logger.error(f"Error in {type(focused_widget).__name__}.handle_controller_action for '{action}': {e}", exc_info=True)
            else:
                logger.warning(f"Focused panel {type(focused_widget).__name__} has no handle_controller_action method.")
        else:
            logger.warning(f"No panel focused or index out of bounds: {self._current_focused_panel_index}")


    def _set_panel_controller_focus(self, new_index: int):
        if not self._focusable_panels or not (0 <= new_index < len(self._focusable_panels)):
            logger.warning(f"Attempt to set focus to invalid index {new_index}")
            return

        old_index = self._current_focused_panel_index
        
        if 0 <= old_index < len(self._focusable_panels) and old_index != new_index :
            old_panel = self._focusable_panels[old_index]
            if hasattr(old_panel, "on_controller_focus_lost"):
                try: old_panel.on_controller_focus_lost() # type: ignore
                except Exception as e: logger.error(f"Error in {type(old_panel).__name__}.on_controller_focus_lost: {e}", exc_info=True)
            parent_dock_old = old_panel.parent()
            while parent_dock_old and not isinstance(parent_dock_old, QDockWidget):
                parent_dock_old = parent_dock_old.parent()
            if isinstance(parent_dock_old, QDockWidget):
                 parent_dock_old.setStyleSheet("") 


        self._current_focused_panel_index = new_index
        new_panel = self._focusable_panels[new_index]
        new_panel.setFocus(Qt.FocusReason.OtherFocusReason) 

        if hasattr(new_panel, "on_controller_focus_gained"):
            try: new_panel.on_controller_focus_gained() # type: ignore
            except Exception as e: logger.error(f"Error in {type(new_panel).__name__}.on_controller_focus_gained: {e}", exc_info=True)
        
        panel_name_for_status = type(new_panel).__name__
        parent_dock_new = new_panel.parent()
        while parent_dock_new and not isinstance(parent_dock_new, QDockWidget):
            parent_dock_new = parent_dock_new.parent()
        if isinstance(parent_dock_new, QDockWidget):
            panel_name_for_status = parent_dock_new.windowTitle()
            focus_border_color = getattr(ED_CONFIG, "PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER", "2px solid orange").split(' ')[-1] if isinstance(new_panel, PropertiesEditorDockWidget) \
                            else getattr(ED_CONFIG, "ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER", "2px solid lightgreen").split(' ')[-1] if isinstance(new_panel, AssetPaletteWidget) \
                            else getattr(ED_CONFIG, "MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE", (0,200,255,180)) # Fallback or MapView
            
            if isinstance(focus_border_color, tuple): # Convert QColor tuple to hex string
                focus_border_color = QColor(*focus_border_color[:3]).name()


            parent_dock_new.setStyleSheet(f"QDockWidget::title {{ background-color: {focus_border_color}; color: black; border: 1px solid black; padding: 2px; }}")
        elif isinstance(new_panel, MapViewWidget): 
            panel_name_for_status = "Map View"
            # MapView can have its own focus indicator, e.g., border on the QGraphicsView itself if desired
            # new_panel.setStyleSheet(f"QGraphicsView {{ border: 2px solid {QColor(*getattr(ED_CONFIG, 'MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE', (0,0,0,0))[:3]).name()}; }}")


        
        self.show_status_message(f"Controller Focus: {panel_name_for_status}", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        logger.info(f"Controller focus set to: {panel_name_for_status} (Index: {new_index})")

    def _cycle_panel_focus_next(self):
        if not self._focusable_panels: return
        new_index = (self._current_focused_panel_index + 1) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def _cycle_panel_focus_prev(self):
        if not self._focusable_panels: return
        new_index = (self._current_focused_panel_index - 1 + len(self._focusable_panels)) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def create_actions(self):
        logger.debug("Creating actions...")
        self.new_map_action = QAction("&New Map...", self, shortcut=QKeySequence.StandardKey.New, statusTip="Create a new map", triggered=self.new_map)
        self.load_map_action = QAction("&Load Map...", self, shortcut=QKeySequence.StandardKey.Open, statusTip="Load an existing map", triggered=self.load_map)
        self.save_map_action = QAction("&Save Map", self, shortcut=QKeySequence.StandardKey.Save, statusTip="Save the current map's editor data (.json)", triggered=self.save_map_json)
        self.export_map_action = QAction("&Export Map for Game...", self, shortcut=QKeySequence("Ctrl+E"), statusTip="Export map to game format (.py)", triggered=self.export_map_py)
        self.save_all_action = QAction("Save &All (JSON & PY)", self, shortcut=QKeySequence("Ctrl+Shift+S"), statusTip="Save editor data and export for game", triggered=self.save_all)

        self.export_map_as_image_action = QAction("Export Map as &Image...", self,
                                                  shortcut="Ctrl+Shift+P", 
                                                  statusTip="Export the current map view as a PNG image",
                                                  triggered=self.export_map_as_image)

        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit, statusTip="Exit the editor", triggered=self.close) 

        self.undo_action = QAction("&Undo", self, shortcut=QKeySequence.StandardKey.Undo, statusTip="Undo last action", triggered=self.undo)
        self.redo_action = QAction("&Redo", self, shortcut=QKeySequence.StandardKey.Redo, statusTip="Redo last undone action", triggered=self.redo)

        self.toggle_grid_action = QAction("Toggle &Grid", self, shortcut="Ctrl+G", statusTip="Show/Hide grid", triggered=self.toggle_grid, checkable=True)
        self.toggle_grid_action.setChecked(self.editor_state.show_grid) 
        self.change_bg_color_action = QAction("Change &Background Color...", self, statusTip="Change map background color", triggered=self.change_background_color)

        self.zoom_in_action = QAction("Zoom &In", self, shortcut=QKeySequence.StandardKey.ZoomIn, statusTip="Zoom in on the map", triggered=self.map_view_widget.zoom_in)
        self.zoom_out_action = QAction("Zoom &Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, statusTip="Zoom out of the map", triggered=self.map_view_widget.zoom_out)
        self.zoom_reset_action = QAction("Reset &Zoom", self, shortcut="Ctrl+0", statusTip="Reset map zoom to 100%", triggered=self.map_view_widget.reset_zoom)

        self.rename_map_action = QAction("&Rename Current Map...", self, statusTip="Rename the current map's files", triggered=self.rename_map)
        self.delete_map_file_action = QAction("&Delete Map File...", self, statusTip="Delete a map's .json and .py files", triggered=self.delete_map_file)
        logger.debug("Actions created.")

    def create_menus(self):
        logger.debug("Creating menus...")
        self.menu_bar = self.menuBar() 
        file_menu = self.menu_bar.addMenu("&File")
        file_menu.addAction(self.new_map_action)
        file_menu.addAction(self.load_map_action)
        file_menu.addAction(self.rename_map_action)
        file_menu.addAction(self.delete_map_file_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_map_action)
        file_menu.addAction(self.export_map_action)
        file_menu.addAction(self.save_all_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_map_as_image_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.change_bg_color_action)

        view_menu = self.menu_bar.addMenu("&View")
        view_menu.addAction(self.toggle_grid_action)
        view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(self.asset_palette_dock.toggleViewAction())
        view_menu.addAction(self.properties_editor_dock.toggleViewAction())
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock: # type: ignore
            view_menu.addAction(self.minimap_dock.toggleViewAction())

        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog)
        help_menu.addAction(about_action)
        logger.debug("Menus created.")

    def create_status_bar(self):
        logger.debug("Creating status bar...")
        self.status_bar = self.statusBar() 
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250) 
        self.status_bar.addPermanentWidget(self.map_coords_label)
        
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT): # type: ignore
        if hasattr(self, 'status_bar') and self.status_bar: 
            self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")


    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        world_x, world_y, tile_x, tile_y, zoom_val = coords
        self.map_coords_label.setText(f" Map:({int(world_x)},{int(world_y)}) Tile:({tile_x},{tile_y}) Zoom:{zoom_val:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        logger.debug("EditorMainWindow: handle_map_content_changed triggered.")
        if not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes was False, now set to True.")
        self.editor_state.unsaved_changes = True
        
        if not self._is_embedded: 
            self.update_window_title()
            
        self.update_edit_actions_enabled_state()

        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_widget') and self.minimap_widget: # type: ignore
             logger.debug("Notifying minimap to redraw content due to map change via handle_map_content_changed.")
             self.minimap_widget.schedule_map_content_redraw()

        logger.debug(f"EditorMainWindow: After handle_map_content_changed - unsaved_changes: {self.editor_state.unsaved_changes}, save_map_action enabled: {self.save_map_action.isEnabled()}")


    def update_window_title(self):
        if self._is_embedded: return
        
        title = "Platformer Level Editor (PySide6)"
        map_name = self.editor_state.map_name_for_function
        if map_name and map_name != "untitled_map":
            title += f" - {map_name}"
            if self.editor_state.current_json_filename:
                 title += f" [{os.path.basename(self.editor_state.current_json_filename)}]"
        if self.editor_state.unsaved_changes:
            title += "*" 
        self.setWindowTitle(title)


    def update_edit_actions_enabled_state(self):
        map_is_properly_loaded_or_newly_named = bool(
            self.editor_state.current_json_filename or \
            (self.editor_state.map_name_for_function != "untitled_map" and \
             self.editor_state.placed_objects) 
        )
        can_save = map_is_properly_loaded_or_newly_named and self.editor_state.unsaved_changes
        self.save_map_action.setEnabled(can_save)
        self.export_map_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.save_all_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.rename_map_action.setEnabled(bool(self.editor_state.current_json_filename))
        self.undo_action.setEnabled(len(self.editor_state.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack) > 0)
        map_active = bool(self.editor_state.map_name_for_function != "untitled_map" or self.editor_state.placed_objects)
        self.change_bg_color_action.setEnabled(map_active)
        self.toggle_grid_action.setEnabled(map_active)
        self.zoom_in_action.setEnabled(map_active)
        self.zoom_out_action.setEnabled(map_active)
        self.zoom_reset_action.setEnabled(map_active)
        map_has_content = bool(self.editor_state.placed_objects or self.editor_state.current_json_filename)
        self.export_map_as_image_action.setEnabled(map_has_content)


    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool:
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         f"You have unsaved changes. Do you want to save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                return self.save_all() 
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

    @Slot()
    def new_map(self):
        logger.info("New Map action triggered.")
        if not self.confirm_unsaved_changes("create a new map"): return
        map_name, ok = QInputDialog.getText(self, "New Map", "Enter map name (e.g., level_1 or level_default):")
        if ok and map_name:
            clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_map_name: QMessageBox.warning(self, "Invalid Name", "Map name cannot be empty."); return
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']
            if any(char in clean_map_name for char in invalid_chars): QMessageBox.warning(self, "Invalid Name", f"Map name '{clean_map_name}' contains invalid characters."); return
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
            if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return
            potential_json_path = os.path.join(maps_abs_dir, clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION) # type: ignore
            if os.path.exists(potential_json_path): QMessageBox.warning(self, "Name Exists", f"A map JSON file named '{os.path.basename(potential_json_path)}' already exists in the maps directory."); return
            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):", text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}") # type: ignore
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(',')
                    width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 1000); max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 1000) # type: ignore
                    if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h): raise ValueError(f"Dimensions must be between 1 and max ({max_w}x{max_h}).")
                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles) # type: ignore
                    self.map_view_widget.load_map_from_state()
                    self.asset_palette_widget.clear_selection()
                    self.properties_editor_widget.clear_display()
                    if not self._is_embedded: self.update_window_title()
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore
                    editor_history.push_undo_state(self.editor_state) # type: ignore
                    self.update_edit_actions_enabled_state()
                except ValueError as e_size: QMessageBox.warning(self, "Invalid Size", f"Invalid map size format or value: {e_size}")
                except Exception as e_new_map: logger.error(f"Error during new map creation: {e_new_map}", exc_info=True); QMessageBox.critical(self, "Error", f"Could not create new map: {e_new_map}")
        else: self.show_status_message("New map cancelled.")

    @Slot()
    def load_map(self):
        logger.info("Load Map action triggered.")
        if not self.confirm_unsaved_changes("load another map"): return
        project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
             QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return
        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})" # type: ignore
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Map", maps_abs_dir, json_filter)
        if file_path:
            logger.info(f"Attempting to load map from: {file_path}")
            if editor_map_utils.load_map_from_json(self.editor_state, file_path): # type: ignore
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.properties_editor_widget.clear_display()
                if not self._is_embedded: self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state) # type: ignore
                self.update_edit_actions_enabled_state()
            else: QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else: self.show_status_message("Load map cancelled.")

    @Slot()
    def save_map_json(self) -> bool:
        logger.info("Save Map (JSON) action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            self.show_status_message("Map is untitled. Performing initial Save All to set name and save files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore
            return self.save_all() 
        if editor_map_utils.save_map_to_json(self.editor_state): # type: ignore
            self.show_status_message(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename or 'unknown.json')}.")
            self.editor_state.unsaved_changes = False 
            if not self._is_embedded: self.update_window_title()
            self.update_edit_actions_enabled_state()
            return True
        else: QMessageBox.critical(self, "Save Error", "Failed to save map editor data (.json). Check logs."); return False

    @Slot()
    def export_map_py(self) -> bool:
        logger.info("Export Map (PY) action triggered.")
        if not self.editor_state.current_json_filename: 
             QMessageBox.warning(self, "Cannot Export", "No map is currently loaded/saved. Save the map first (JSON format)."); return False
        if editor_map_utils.export_map_to_game_python_script(self.editor_state): # type: ignore
            self.show_status_message(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename or 'unknown.py')}.")
            return True
        else: QMessageBox.critical(self, "Export Error", "Failed to export map for game (.py). Check logs."); return False

    @Slot()
    def save_all(self) -> bool:
        logger.info("Save All action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            map_name, ok = QInputDialog.getText(self, "Save Map As", "Enter map name for saving all files (e.g., level_default):")
            if ok and map_name:
                clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
                if not clean_map_name or any(c in clean_map_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']):
                    QMessageBox.warning(self, "Invalid Name", "Map name is invalid or empty."); return False
                self.editor_state.map_name_for_function = clean_map_name
                json_fn = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # type: ignore
                py_fn = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION # type: ignore
                project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
                if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
                    QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return False
                self.editor_state.current_json_filename = os.path.join(maps_abs_dir, json_fn)
                self.editor_state.current_map_filename = os.path.join(maps_abs_dir, py_fn)
                if not self._is_embedded: self.update_window_title()
            else: self.show_status_message("Save All cancelled: map name not provided."); return False
        if self.save_map_json(): 
            if self.export_map_py():
                self.show_status_message("Map saved (JSON & PY)."); return True
        self.show_status_message("Save All failed. Check logs."); return False

    @Slot()
    def rename_map(self):
        logger.info("Rename Map action triggered.")
        if not self.editor_state.current_json_filename: QMessageBox.information(self, "Rename Map", "No map loaded to rename. Please load or save a map first."); return
        old_base_name = self.editor_state.map_name_for_function
        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"Enter new name for map '{old_base_name}':", text=old_base_name)
        if ok and new_name_str:
            clean_new_name = new_name_str.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_new_name or any(c in clean_new_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']): QMessageBox.warning(self, "Invalid Name", "New map name invalid."); return
            if clean_new_name == old_base_name: self.show_status_message("Rename cancelled: name unchanged."); return
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
            if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return
            new_json_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION) # type: ignore
            if os.path.exists(new_json_path) and os.path.normcase(new_json_path) != os.path.normcase(self.editor_state.current_json_filename):
                QMessageBox.warning(self, "Rename Error", f"A map JSON file named '{os.path.basename(new_json_path)}' already exists."); return
            old_json_path = self.editor_state.current_json_filename
            old_py_path = self.editor_state.current_map_filename 
            new_py_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION) # type: ignore
            try:
                logger.info(f"Attempting rename of map '{old_base_name}' to '{clean_new_name}'.")
                if old_json_path and os.path.exists(old_json_path): os.rename(old_json_path, new_json_path)
                self.editor_state.map_name_for_function = clean_new_name
                self.editor_state.current_json_filename = new_json_path
                self.editor_state.current_map_filename = new_py_path 
                if not editor_map_utils.save_map_to_json(self.editor_state):  # type: ignore
                    QMessageBox.critical(self, "Rename Error", "Failed to save map data to the new JSON file after renaming the file. State might be inconsistent."); return
                if old_py_path and os.path.exists(old_py_path) and os.path.normcase(old_py_path) != os.path.normcase(new_py_path):
                    os.remove(old_py_path); logger.info(f"Old PY file '{os.path.basename(old_py_path)}' deleted after rename.")
                if editor_map_utils.export_map_to_game_python_script(self.editor_state): # type: ignore
                    self.show_status_message(f"Map renamed to '{clean_new_name}' and files updated.")
                else:
                    QMessageBox.warning(self, "Rename Warning", "Map files renamed (JSON updated), but exporting to the new PY file failed. Please try 'Save All' or 'Export' manually."); self.editor_state.unsaved_changes = True
                if not self._is_embedded: self.update_window_title()
                self.update_edit_actions_enabled_state()
            except Exception as e_rename_map: logger.error(f"Error during map rename process: {e_rename_map}", exc_info=True); QMessageBox.critical(self, "Rename Error", f"An unexpected error occurred during map rename: {e_rename_map}")
        else: self.show_status_message("Rename map cancelled.")

    @Slot()
    def delete_map_file(self):
        logger.info("Delete Map File action triggered.")
        project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
             QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return
        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})" # type: ignore
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Map to Delete", maps_abs_dir, json_filter)
        if file_path:
            map_name_to_delete = os.path.splitext(os.path.basename(file_path))[0]
            reply = QMessageBox.warning(self, "Confirm Delete", f"Are you sure you want to delete ALL files (JSON and PY) for map '{map_name_to_delete}'?\nThis action CANNOT be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state, file_path): # type: ignore
                    self.show_status_message(f"Map '{map_name_to_delete}' files deleted.")
                    if self.editor_state.current_json_filename and os.path.normcase(self.editor_state.current_json_filename) == os.path.normcase(file_path):
                        logger.info(f"Deleted map was currently loaded. Resetting editor state.")
                        self.editor_state.reset_map_context()
                        self.map_view_widget.load_map_from_state()
                        self.asset_palette_widget.clear_selection(); self.properties_editor_widget.clear_display()
                        if not self._is_embedded: self.update_window_title()
                        self.update_edit_actions_enabled_state()
                else: QMessageBox.critical(self, "Delete Error", f"Failed to delete some or all files for map '{map_name_to_delete}'. Check logs.")
            else: self.show_status_message("Delete map cancelled.")
        else: self.show_status_message("Delete map selection cancelled.")

    @Slot()
    def export_map_as_image(self):
        logger.info("Export Map as Image action triggered.")
        if not self.editor_state.placed_objects and not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Export Error", "No map content to export as an image. Create or load a map.")
            return
        default_map_name = self.editor_state.map_name_for_function if self.editor_state.map_name_for_function != "untitled_map" else "untitled_map_export"
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suggested_dir = os.path.join(project_root, "map_exports")
        if not os.path.exists(suggested_dir):
            try: os.makedirs(suggested_dir)
            except OSError as e_mkdir: logger.error(f"Could not create 'map_exports' directory: {e_mkdir}"); suggested_dir = os.path.join(project_root, ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        suggested_path = os.path.join(suggested_dir, default_map_name + ".png")
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Map as Image", suggested_path, "PNG Images (*.png);;All Files (*)")
        if not file_path: self.show_status_message("Export map as image cancelled."); logger.info("Export map as image cancelled by user."); return
        try:
            scene = self.map_view_widget.scene()
            if not scene: QMessageBox.critical(self, "Export Error", "Cannot access map scene for export."); return
            target_rect = scene.itemsBoundingRect() 
            if target_rect.isEmpty(): QMessageBox.information(self, "Export Error", "Map is empty, nothing to export as image."); return
            padding = 20; target_rect.adjust(-padding, -padding, padding, padding)
            image_size_width = int(target_rect.width())
            image_size_height = int(target_rect.height())
            if image_size_width <=0 or image_size_height <=0:
                QMessageBox.critical(self, "Export Error", f"Invalid image dimensions for export: {image_size_width}x{image_size_height}"); return
            image = QImage(image_size_width, image_size_height, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent) 
            painter = QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing, False); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            scene.render(painter, QRectF(image.rect()), target_rect); painter.end()
            if image.save(file_path, "PNG"): self.show_status_message(f"Map exported as image: {os.path.basename(file_path)}"); logger.info(f"Map successfully exported as PNG to: {file_path}")
            else: QMessageBox.critical(self, "Export Error", f"Failed to save image to:\n{file_path}"); logger.error(f"Failed to save map image to {file_path}")
        except Exception as e_export_img: logger.error(f"Error exporting map as image: {e_export_img}", exc_info=True); QMessageBox.critical(self, "Export Error", f"Unexpected error during image export:\n{e_export_img}")

    @Slot()
    def undo(self):
        logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful."); 
            if not self._is_embedded: self.update_window_title()
        else: self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self):
        logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful."); 
            if not self._is_embedded: self.update_window_title()
        else: self.show_status_message("Nothing to redo or redo failed.")

    @Slot()
    def toggle_grid(self):
        self.editor_state.show_grid = not self.editor_state.show_grid
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.map_view_widget.update_grid_visibility()
        self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")

    @Slot()
    def change_background_color(self):
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            if not self.editor_state.placed_objects: pass
        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")
        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color(); self.handle_map_content_changed()
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else: self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self):
        QMessageBox.about(self, "About Platformer Level Editor", "Platformer Level Editor (PySide6 Version)\n\nCreate and edit levels for your platformer game.")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        active_panel: Optional[QWidget] = None
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
             active_panel = self._focusable_panels[self._current_focused_panel_index]
        
        if active_panel and hasattr(active_panel, 'handle_key_event_for_controller_nav') and active_panel.handle_key_event_for_controller_nav(event): # type: ignore
             event.accept()
             return

        if key == Qt.Key.Key_Escape and not self._is_embedded: 
            logger.info("Escape key pressed in standalone mode, attempting to close window.")
            self.close(); event.accept()
        elif self.map_view_widget.hasFocus() and hasattr(self.map_view_widget, 'keyPressEvent'):
             self.map_view_widget.keyPressEvent(event) # type: ignore
             if event.isAccepted(): return
        super().keyPressEvent(event)


    def closeEvent(self, event): # type: ignore # QCloseEvent
        logger.info(f"Close event triggered for EditorMainWindow. Embedded: {self._is_embedded}")
        if self.confirm_unsaved_changes("exit the editor"):
            if self._controller_input_timer and self._controller_input_timer.isActive():
                self._controller_input_timer.stop()
                logger.info("Controller input timer stopped.")
            if _PYGAME_AVAILABLE and self._joysticks:
                for joy in self._joysticks: 
                    if joy and joy.get_init(): 
                        joy.quit() 
                logger.info("Pygame joysticks un-initialized.")
                # pygame.joystick.quit() # Defer this to editor_main's final Pygame quit

            if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
            if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
            if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName(): # type: ignore
                self.minimap_dock.setObjectName("MinimapDock")
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            logger.info("Window geometry and state saved on close.")
            event.accept()
        else: event.ignore()

    def save_geometry_and_state(self):
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName(): # type: ignore
            self.minimap_dock.setObjectName("MinimapDock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and dock state explicitly saved via save_geometry_and_state().")

    def restore_geometry_and_state(self) -> bool:
        geom = self.settings.value("geometry")
        state = self.settings.value("windowState")
        restored_geom = False; restored_state = False
        try:
            if geom is not None: self.restoreGeometry(geom); restored_geom = True
            if state is not None: self.restoreState(state); restored_state = True
            if restored_geom or restored_state: logger.debug(f"Window geometry restored: {restored_geom}, state restored: {restored_state}.")
            else: logger.debug("No geometry or state found in settings to restore.")
            return restored_geom or restored_state
        except Exception as e_restore:
            logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting to defaults if applicable.", exc_info=True)
            if not self._is_embedded:
                 primary_screen = QApplication.primaryScreen()
                 if primary_screen:
                     screen_geo = primary_screen.availableGeometry()
                     default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH; default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                     pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                     pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                     self.setGeometry(pos_x, pos_y, default_w, default_h)
                 else: self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
            return False 


def editor_main(parent_app_instance: Optional[QApplication] = None, embed_mode: bool = False):
    if _IS_STANDALONE_EXECUTION: 
        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            if logger: logger.info(f"Standalone mode: Changed CWD to: {os.getcwd()}")
        except Exception as e_chdir:
            if logger: logger.error(f"Could not change CWD in standalone mode: {e_chdir}")

    if logger: logger.info(f"editor_main() called. Embed mode: {embed_mode}, Standalone context: {_IS_STANDALONE_EXECUTION}")
    app = QApplication.instance() 
    if app is None:
        if parent_app_instance:
            app = parent_app_instance
            if logger: logger.debug("Using parent_app_instance for QApplication in editor_main.")
        elif _IS_STANDALONE_EXECUTION: 
            app = QApplication(sys.argv)
            if logger: logger.debug("New QApplication instance created for standalone editor.")
        else: 
            if logger: logger.critical("CRITICAL: embed_mode is True, but no QApplication instance found or provided. Editor cannot run.")
            raise RuntimeError("Editor needs a QApplication instance, especially in embed_mode.")
    else:
        if logger: logger.debug("QApplication instance already exists.")

    main_window = EditorMainWindow(embed_mode=embed_mode) 

    if not embed_mode: 
        exit_code = 0
        try:
            if not main_window.isVisible() and not main_window._is_embedded: 
                 if logger: logger.info("Standalone editor_main: main_window was not visible from init, calling show() (or showMaximized if preferred).")
            exit_code = app.exec()
            if logger: logger.info(f"QApplication event loop finished. Exit code: {exit_code}")
        except Exception as e_main_loop:
            if logger: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
            log_path_info = log_file_path_for_error_msg if 'log_file_path_for_error_msg' in globals() and log_file_path_for_error_msg else "editor_debug.log (path unknown)"
            QMessageBox.critical(None,"Editor Critical Error", f"A critical error occurred: {e_main_loop}\n\nCheck log for details:\n{log_path_info}")
            exit_code = 1 
        finally:
            if hasattr(main_window, 'isVisible') and main_window.isVisible(): 
                main_window.save_geometry_and_state() 
            if logger: logger.info("Editor session (standalone) ended.")
        
        # Ensure Pygame is quit if it was initialized
        if _PYGAME_AVAILABLE and pygame.get_init():
            pygame.quit()
            logger.info("Pygame quit globally at end of editor_main (standalone).")
        return exit_code 
    else: 
        if logger: logger.info("EditorMainWindow instance created for embedding. Returning instance to caller.")
        return main_window 


if __name__ == "__main__":
    print("--- editor.py execution started as __main__ (standalone) ---")
    if _PYGAME_AVAILABLE and not pygame.get_init():
        try:
            pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            print("INFO: Pygame initialized for standalone __main__ execution.")
        except Exception as e_pygame_main_init:
            print(f"WARNING: Pygame init failed in __main__: {e_pygame_main_init}")


    return_code_standalone = editor_main(embed_mode=False) 
    print(f"--- editor.py standalone execution finished (exit code: {return_code_standalone}) ---")
    sys.exit(return_code_standalone)

#################### END OF FILE: editor\editor.py ####################