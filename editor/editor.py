#################### START OF FILE: editor\editor.py ####################

# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.13 (Corrected import logic for standalone vs package)
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
_IMPORTS_SUCCESSFUL_METHOD = "Unknown"
_critical_import_failed = False
_import_errors_list = []

try:
    if not _IS_STANDALONE_EXECUTION and __package__: # Running as part of a package (e.g. from app_core)
        logger_init_pygame.info(f"Attempting relative imports for editor modules (as package '{__package__}')...")
        from . import editor_config as ED_CONFIG
        from .editor_state import EditorState
        from . import editor_assets
        from . import editor_map_utils
        from . import editor_history
        from .map_view_widget import MapViewWidget, MapObjectItem
        from .editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
        from .editor_actions import * 
        if ED_CONFIG.MINIMAP_ENABLED:
            from .minimap_widget import MinimapWidget
        if _PYGAME_AVAILABLE:
            # This assumes 'config' is in the parent directory of 'editor' package
            from .. import config as main_game_config 
            init_pygame_and_joystick_globally = main_game_config.init_pygame_and_joystick_globally
            get_joystick_objects = main_game_config.get_joystick_objects
        _IMPORTS_SUCCESSFUL_METHOD = "Relative (as package)"
        logger_init_pygame.info("Editor modules imported successfully using RELATIVE paths (as package).")
    else: # Standalone execution or no package context (direct run of editor.py)
        logger_init_pygame.info("Attempting absolute imports for editor modules (standalone or no package context)...")
        # This assumes project_root is in sys.path, which it should be for standalone
        from editor import editor_config as ED_CONFIG
        from editor.editor_state import EditorState
        from editor import editor_assets
        from editor import editor_map_utils
        from editor import editor_history
        from editor.map_view_widget import MapViewWidget, MapObjectItem
        from editor.editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
        from editor.editor_actions import *
        if ED_CONFIG.MINIMAP_ENABLED:
            from editor.minimap_widget import MinimapWidget
        if _PYGAME_AVAILABLE:
            import config as main_game_config # Import from project root
            init_pygame_and_joystick_globally = main_game_config.init_pygame_and_joystick_globally
            get_joystick_objects = main_game_config.get_joystick_objects
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (editor.*)"
        logger_init_pygame.info("Editor modules imported successfully using ABSOLUTE paths (editor.*).")

except ImportError as e:
    _critical_import_failed = True
    err_msg = f"CRITICAL IMPORT ERROR: {e}"
    _import_errors_list.append(err_msg)
    logger_init_pygame.critical(err_msg, exc_info=True)
    logger_init_pygame.critical(f"  Current sys.path: {sys.path}")
    logger_init_pygame.critical(f"  __name__: {__name__}, __package__: {__package__}, _IS_STANDALONE_EXECUTION: {_IS_STANDALONE_EXECUTION}")
except AttributeError as e_attr: 
    _critical_import_failed = True
    err_msg = f"CRITICAL ATTRIBUTE ERROR during import (likely ED_CONFIG issue or main_game_config): {e_attr}"
    _import_errors_list.append(err_msg)
    logger_init_pygame.critical(err_msg, exc_info=True)

if _critical_import_failed:
    combined_errors = "\n".join(_import_errors_list)
    raise ImportError(f"Failed to import critical editor modules. Errors:\n{combined_errors}")


# --- Logger Setup (now that ED_CONFIG is expected to be loaded) ---
logger: Optional[logging.Logger] = None 
log_file_path_for_error_msg = "editor_qt_debug.log" 
try:
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs') 
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    
    log_file_name = ED_CONFIG.LOG_FILE_NAME # type: ignore
    log_file_path_for_error_msg = os.path.join(logs_dir, log_file_name)
    
    log_level_str = ED_CONFIG.LOG_LEVEL.upper() # type: ignore
    numeric_log_level = getattr(logging, log_level_str, logging.DEBUG)
    
    log_format_str = ED_CONFIG.LOG_FORMAT # type: ignore

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
SWITCH_A_BTN = 0; SWITCH_B_BTN = 1; SWITCH_X_BTN = 2; SWITCH_Y_BTN = 3
SWITCH_L_BTN = 4; SWITCH_R_BTN = 5; SWITCH_ZL_BTN = 6; SWITCH_ZR_BTN = 7
SWITCH_MINUS_BTN = 8; SWITCH_PLUS_BTN = 9
SWITCH_L_STICK_BTN = 10; SWITCH_R_STICK_BTN = 11
SWITCH_L_STICK_X_AXIS = 0; SWITCH_L_STICK_Y_AXIS = 1
SWITCH_R_STICK_X_AXIS = 2; SWITCH_R_STICK_Y_AXIS = 3
SWITCH_ZL_AXIS = 4; SWITCH_ZR_AXIS = 5
SWITCH_DPAD_HAT_ID = 0


class EditorMainWindow(QMainWindow):
    controller_action_dispatched = Signal(str, object) 

    def __init__(self, parent: Optional[QWidget] = None, embed_mode: bool = False):
        super().__init__(parent) 
        self._is_embedded = embed_mode 
        logger.info(f"Initializing EditorMainWindow... Embedded: {self._is_embedded}")

        self.editor_state = EditorState()
        self.settings = QSettings("MyPlatformerGame", "LevelEditor_Qt")
        
        self.init_ui() 
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

        self._current_focused_panel_index: int = 0 
        self._controller_input_timer: Optional[QTimer] = None
        self._joysticks: List[pygame.joystick.Joystick] = [] # type: ignore
        self._primary_joystick: Optional[pygame.joystick.Joystick] = None # type: ignore
        
        self._controller_axis_deadzone = 0.4 
        self._controller_axis_last_event_time: Dict[Tuple[int, int, int], float] = {} 
        self._controller_axis_repeat_delay = 0.3 
        self._controller_axis_repeat_interval = 0.1 
        self._last_dpad_value: Optional[Tuple[int, int]] = None
        self._button_last_state: Dict[int, bool] = {} 

        if _PYGAME_AVAILABLE:
            self._init_controller_system()
            self.controller_action_dispatched.connect(self._dispatch_controller_action_to_panel)

        if not self._is_embedded:
            restored_successfully = self.restore_geometry_and_state()
            if restored_successfully: self.show() 
            else:
                primary_screen = QApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    default_w, default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                    pos_x, pos_y = screen_geo.x() + (screen_geo.width() - default_w)//2, screen_geo.y() + (screen_geo.height() - default_h)//2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                else: self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
                self.showMaximized() 
        else: self.restore_geometry_and_state()

        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
            err_msg_maps_dir = f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}" # type: ignore
            logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox)" if self._is_embedded else err_msg_maps_dir)
            if not self._is_embedded: QMessageBox.critical(self, "Error", err_msg_maps_dir)
        
        logger.info("EditorMainWindow initialized.")
        self.show_status_message("Editor started.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore

        if self._focusable_panels:
            focus_target = self._focusable_panels[0]
            if _PYGAME_AVAILABLE and self._primary_joystick: self._set_panel_controller_focus(0)
            else: focus_target.setFocus(Qt.FocusReason.OtherFocusReason)


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
            self.minimap_dock = None; self.minimap_widget = None # type: ignore

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
            init_pygame_and_joystick_globally(force_rescan=True) # Uses imported function
            self._joysticks = get_joystick_objects() # Uses imported function
            
            if not self._joysticks or all(joy is None for joy in self._joysticks):
                logger.info("No joysticks detected by Pygame or all are None.")
                self._primary_joystick = None; return

            for i, joy in enumerate(self._joysticks):
                if joy:
                    try:
                        if not joy.get_init(): joy.init()
                        self._primary_joystick = joy
                        logger.info(f"Primary joystick set to: {joy.get_name()} (Index: {i}, GUID: {joy.get_guid()})")
                        break
                    except pygame.error as e: logger.warning(f"Could not initialize joystick {i} ({joy.get_name()}): {e}")
            
            if not self._primary_joystick: logger.warning("No valid joystick could be initialized as primary."); return
            
            self._controller_input_timer = QTimer(self)
            self._controller_input_timer.setInterval(ED_CONFIG.CONTROLLER_POLL_INTERVAL_MS) # type: ignore
            self._controller_input_timer.timeout.connect(self._poll_controller_input)
            self._controller_input_timer.start()
            logger.info("Controller input polling timer started.")
        except Exception as e: logger.error(f"Error initializing controller system: {e}", exc_info=True); self._primary_joystick = None


    def _poll_controller_input(self):
        if not _PYGAME_AVAILABLE or not self._primary_joystick: return
        
        pygame.event.pump(); current_time = time.monotonic()
        joy = self._primary_joystick
        if not joy.get_init():
            try: joy.init()
            except pygame.error: return

        button_map = {
            SWITCH_B_BTN: ACTION_UI_ACCEPT, SWITCH_A_BTN: ACTION_UI_CANCEL,
            SWITCH_Y_BTN: ACTION_MAP_TOOL_PRIMARY, SWITCH_X_BTN: ACTION_MAP_TOOL_SECONDARY,
            SWITCH_L_BTN: ACTION_UI_TAB_PREV, SWITCH_R_BTN: ACTION_UI_TAB_NEXT,
            SWITCH_ZL_BTN: ACTION_MAP_ZOOM_OUT, SWITCH_ZR_BTN: ACTION_MAP_ZOOM_IN,
            SWITCH_PLUS_BTN: ACTION_UI_MENU, SWITCH_MINUS_BTN: ACTION_UI_FOCUS_NEXT, 
        }
        for btn_id, action in button_map.items():
            if btn_id >= joy.get_numbuttons(): continue
            pressed = joy.get_button(btn_id)
            if pressed and not self._button_last_state.get(btn_id, False):
                self.controller_action_dispatched.emit(action, True) 
            self._button_last_state[btn_id] = pressed

        if joy.get_numhats() > 0:
            hat_value = joy.get_hat(SWITCH_DPAD_HAT_ID)
            if hat_value != self._last_dpad_value: 
                if hat_value == (0,1): self.controller_action_dispatched.emit(ACTION_UI_UP, None)
                elif hat_value == (0,-1): self.controller_action_dispatched.emit(ACTION_UI_DOWN, None)
                elif hat_value == (-1,0): self.controller_action_dispatched.emit(ACTION_UI_LEFT, None)
                elif hat_value == (1,0): self.controller_action_dispatched.emit(ACTION_UI_RIGHT, None)
                self._last_dpad_value = hat_value
        
        axis_map = {
            SWITCH_L_STICK_X_AXIS: (ACTION_UI_LEFT, ACTION_UI_RIGHT),
            SWITCH_L_STICK_Y_AXIS: (ACTION_UI_UP, ACTION_UI_DOWN), 
            SWITCH_R_STICK_Y_AXIS: (ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN),
        }
        for axis_id, actions in axis_map.items():
            if axis_id >= joy.get_numaxes(): continue
            axis_val = joy.get_axis(axis_id); direction_sign = 0
            if axis_val < -self._controller_axis_deadzone: direction_sign = -1
            elif axis_val > self._controller_axis_deadzone: direction_sign = 1
            key = (joy.get_id(), axis_id, direction_sign)
            action_to_emit = actions[0] if direction_sign == -1 else (actions[1] if direction_sign == 1 else None)
            if action_to_emit:
                if action_to_emit.startswith("CAMERA_PAN_"):
                    self.controller_action_dispatched.emit(action_to_emit, axis_val)
                else: 
                    last_event_time = self._controller_axis_last_event_time.get(key, 0)
                    if current_time - last_event_time > self._controller_axis_repeat_delay or \
                       current_time - last_event_time > self._controller_axis_repeat_interval:
                        self.controller_action_dispatched.emit(action_to_emit, axis_val)
                        self._controller_axis_last_event_time[key] = current_time
            else: 
                 for ds in [-1, 1]: self._controller_axis_last_event_time[(joy.get_id(), axis_id, ds)] = 0


    @Slot(str, object)
    def _dispatch_controller_action_to_panel(self, action: str, value: Any):
        logger.debug(f"Controller action to dispatch: {action}, Value: {value}")
        if action == ACTION_UI_FOCUS_NEXT: self._cycle_panel_focus_next(); return
        elif action == ACTION_UI_FOCUS_PREV: self._cycle_panel_focus_prev(); return
        elif action == ACTION_UI_MENU:
            if self.menu_bar and self.menu_bar.actions():
                first_menu = self.menu_bar.actions()[0].menu()
                if first_menu: first_menu.popup(self.mapToGlobal(self.menu_bar.pos() + QPoint(0, self.menu_bar.height())))
            return
        elif action.startswith("CAMERA_PAN_"):
            if hasattr(self.map_view_widget, "handle_controller_camera_pan"):
                try: self.map_view_widget.handle_controller_camera_pan(action, value)
                except Exception as e: logger.error(f"Error in MapViewWidget.handle_controller_camera_pan for '{action}': {e}", exc_info=True)
            else: logger.warning(f"MapViewWidget has no handle_controller_camera_pan for '{action}'.")
            return
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
            focused_widget = self._focusable_panels[self._current_focused_panel_index]
            if hasattr(focused_widget, "handle_controller_action"):
                try: focused_widget.handle_controller_action(action, value) # type: ignore
                except Exception as e: logger.error(f"Error in {type(focused_widget).__name__}.handle_controller_action for '{action}': {e}", exc_info=True)
            else: logger.warning(f"Focused panel {type(focused_widget).__name__} has no handle_controller_action.")
        else: logger.warning(f"No panel focused or index out of bounds: {self._current_focused_panel_index}")


    def _set_panel_controller_focus(self, new_index: int):
        if not self._focusable_panels or not (0 <= new_index < len(self._focusable_panels)): return
        old_index = self._current_focused_panel_index
        if 0 <= old_index < len(self._focusable_panels) and old_index != new_index:
            old_panel = self._focusable_panels[old_index]
            if hasattr(old_panel, "on_controller_focus_lost"):
                try: old_panel.on_controller_focus_lost() # type: ignore
                except Exception as e: logger.error(f"Error in {type(old_panel).__name__}.on_controller_focus_lost: {e}", exc_info=True)
            parent_dock_old = old_panel.parent()
            while parent_dock_old and not isinstance(parent_dock_old, QDockWidget): parent_dock_old = parent_dock_old.parent()
            if isinstance(parent_dock_old, QDockWidget): parent_dock_old.setStyleSheet("") 
        self._current_focused_panel_index = new_index
        new_panel = self._focusable_panels[new_index]
        new_panel.setFocus(Qt.FocusReason.OtherFocusReason) 
        if hasattr(new_panel, "on_controller_focus_gained"):
            try: new_panel.on_controller_focus_gained() # type: ignore
            except Exception as e: logger.error(f"Error in {type(new_panel).__name__}.on_controller_focus_gained: {e}", exc_info=True)
        panel_name = type(new_panel).__name__
        parent_dock_new = new_panel.parent()
        while parent_dock_new and not isinstance(parent_dock_new, QDockWidget): parent_dock_new = parent_dock_new.parent()
        if isinstance(parent_dock_new, QDockWidget):
            panel_name = parent_dock_new.windowTitle()
            focus_color_str = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER.split(' ')[-1] if isinstance(new_panel, PropertiesEditorDockWidget) \
                else ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER.split(' ')[-1] if isinstance(new_panel, AssetPaletteWidget) \
                else QColor(*ED_CONFIG.MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE[:3]).name() # type: ignore
            parent_dock_new.setStyleSheet(f"QDockWidget::title {{ background-color: {focus_color_str}; color: black; border: 1px solid black; padding: 2px; }}")
        elif isinstance(new_panel, MapViewWidget): panel_name = "Map View"
        self.show_status_message(f"Ctrl Focus: {panel_name}", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        logger.info(f"Ctrl focus: {panel_name} (Idx:{new_index})")

    def _cycle_panel_focus_next(self):
        if self._focusable_panels: self._set_panel_controller_focus((self._current_focused_panel_index + 1) % len(self._focusable_panels))
    def _cycle_panel_focus_prev(self):
        if self._focusable_panels: self._set_panel_controller_focus((self._current_focused_panel_index - 1 + len(self._focusable_panels)) % len(self._focusable_panels))

    def create_actions(self):
        self.new_map_action=QAction("&New...",self,triggered=self.new_map,shortcut=QKeySequence.StandardKey.New,statusTip="New map")
        self.load_map_action=QAction("&Load...",self,triggered=self.load_map,shortcut=QKeySequence.StandardKey.Open,statusTip="Load map")
        self.save_map_action=QAction("&Save JSON",self,triggered=self.save_map_json,shortcut=QKeySequence.StandardKey.Save,statusTip="Save map editor data")
        self.export_map_action=QAction("&Export PY",self,triggered=self.export_map_py,shortcut="Ctrl+E",statusTip="Export to game format")
        self.save_all_action=QAction("Save &All",self,triggered=self.save_all,shortcut="Ctrl+Shift+S",statusTip="Save JSON & export PY")
        self.export_map_as_image_action=QAction("Export as &Image...",self,triggered=self.export_map_as_image,shortcut="Ctrl+Shift+P",statusTip="Export map as PNG")
        self.exit_action=QAction("E&xit",self,triggered=self.close,shortcut=QKeySequence.StandardKey.Quit,statusTip="Exit")
        self.undo_action=QAction("&Undo",self,triggered=self.undo,shortcut=QKeySequence.StandardKey.Undo,statusTip="Undo")
        self.redo_action=QAction("&Redo",self,triggered=self.redo,shortcut=QKeySequence.StandardKey.Redo,statusTip="Redo")
        self.toggle_grid_action=QAction("Toggle &Grid",self,triggered=self.toggle_grid,shortcut="Ctrl+G",statusTip="Show/Hide grid",checkable=True)
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.change_bg_color_action=QAction("Change B&G Color...",self,triggered=self.change_background_color,statusTip="Change background color")
        self.zoom_in_action=QAction("Zoom &In",self,triggered=self.map_view_widget.zoom_in,shortcut=QKeySequence.StandardKey.ZoomIn,statusTip="Zoom in")
        self.zoom_out_action=QAction("Zoom &Out",self,triggered=self.map_view_widget.zoom_out,shortcut=QKeySequence.StandardKey.ZoomOut,statusTip="Zoom out")
        self.zoom_reset_action=QAction("Reset &Zoom",self,triggered=self.map_view_widget.reset_zoom,shortcut="Ctrl+0",statusTip="Reset zoom")
        self.rename_map_action=QAction("&Rename Map...",self,triggered=self.rename_map,statusTip="Rename current map files")
        self.delete_map_file_action=QAction("&Delete Map File...",self,triggered=self.delete_map_file,statusTip="Delete map JSON & PY files")
    def create_menus(self):
        self.menu_bar=self.menuBar();file_menu=self.menu_bar.addMenu("&File");edit_menu=self.menu_bar.addMenu("&Edit");view_menu=self.menu_bar.addMenu("&View");help_menu=self.menu_bar.addMenu("&Help")
        for act in [self.new_map_action,self.load_map_action,self.rename_map_action,self.delete_map_file_action,None,self.save_map_action,self.export_map_action,self.save_all_action,None,self.export_map_as_image_action,None,self.exit_action]: file_menu.addSeparator() if act is None else file_menu.addAction(act)
        for act in [self.undo_action,self.redo_action,None,self.change_bg_color_action]: edit_menu.addSeparator() if act is None else edit_menu.addAction(act)
        for act in [self.toggle_grid_action,None,self.zoom_in_action,self.zoom_out_action,self.zoom_reset_action,None,self.asset_palette_dock.toggleViewAction(),self.properties_editor_dock.toggleViewAction()]: view_menu.addSeparator() if act is None else view_menu.addAction(act)
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self,'minimap_dock') and self.minimap_dock: view_menu.addAction(self.minimap_dock.toggleViewAction()) # type: ignore
        help_menu.addAction(QAction("&About",self,triggered=self.about_dialog,statusTip="Show editor info"))
    def create_status_bar(self):
        self.status_bar=self.statusBar();self.status_bar.showMessage("Ready",ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        self.map_coords_label=QLabel(" Map:(0,0) Tile:(0,0) Zoom:1.00x ");self.map_coords_label.setMinimumWidth(250);self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
    @Slot(str)
    def show_status_message(self,message:str,timeout:int=ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT): # type: ignore
        if hasattr(self,'status_bar') and self.status_bar: self.status_bar.showMessage(message,timeout)
        logger.info(f"Status: {message}")
    @Slot(tuple)
    def update_map_coords_status(self,coords:tuple): wx,wy,tx,ty,zoom=coords;self.map_coords_label.setText(f" Map:({int(wx)},{int(wy)}) Tile:({tx},{ty}) Zoom:{zoom:.2f}x ")
    @Slot()
    def handle_map_content_changed(self):
        if not self.editor_state.unsaved_changes: logger.debug("Map content changed, unsaved_changes was False, now True.")
        self.editor_state.unsaved_changes=True
        if not self._is_embedded: self.update_window_title()
        self.update_edit_actions_enabled_state()
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self,'minimap_widget') and self.minimap_widget: self.minimap_widget.schedule_map_content_redraw() # type: ignore
    def update_window_title(self):
        if self._is_embedded: return
        title="Platformer Editor";map_name=self.editor_state.map_name_for_function
        if map_name and map_name!="untitled_map": title+=f" - {map_name}"; json_fn=self.editor_state.current_json_filename; title+=f" [{os.path.basename(json_fn)}]" if json_fn else ""
        if self.editor_state.unsaved_changes: title+="*"
        self.setWindowTitle(title)
    def update_edit_actions_enabled_state(self):
        loaded_or_named=bool(self.editor_state.current_json_filename or (self.editor_state.map_name_for_function!="untitled_map" and self.editor_state.placed_objects))
        can_save=loaded_or_named and self.editor_state.unsaved_changes;map_active=bool(self.editor_state.map_name_for_function!="untitled_map" or self.editor_state.placed_objects)
        map_has_content=bool(self.editor_state.placed_objects or self.editor_state.current_json_filename)
        self.save_map_action.setEnabled(can_save);self.export_map_action.setEnabled(loaded_or_named);self.save_all_action.setEnabled(loaded_or_named)
        self.rename_map_action.setEnabled(bool(self.editor_state.current_json_filename));self.undo_action.setEnabled(len(self.editor_state.undo_stack)>0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack)>0);self.change_bg_color_action.setEnabled(map_active)
        self.toggle_grid_action.setEnabled(map_active);self.zoom_in_action.setEnabled(map_active);self.zoom_out_action.setEnabled(map_active)
        self.zoom_reset_action.setEnabled(map_active);self.export_map_as_image_action.setEnabled(map_has_content)
    def confirm_unsaved_changes(self,action_desc="perform this action") -> bool:
        if self.editor_state.unsaved_changes:
            reply=QMessageBox.question(self,"Unsaved Changes",f"Unsaved changes. Save before {action_desc}?",QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
            if reply==QMessageBox.StandardButton.Save: return self.save_all()
            elif reply==QMessageBox.StandardButton.Cancel: return False
        return True
    @Slot()
    def new_map(self):
        if not self.confirm_unsaved_changes("new map"): return
        map_name,ok=QInputDialog.getText(self,"New Map","Map name (e.g. level_1):")
        if ok and map_name:
            clean_name=map_name.strip().lower().replace(" ","_").replace("-","_")
            if not clean_name or any(c in clean_name for c in '/\\:*?"<>|.'): QMessageBox.warning(self,"Invalid Name","Map name invalid."); return
            maps_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
            if not editor_map_utils.ensure_maps_directory_exists(): QMessageBox.critical(self,"Error",f"Maps dir error: {maps_dir}");return # type: ignore
            if os.path.exists(os.path.join(maps_dir,clean_name+ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)): QMessageBox.warning(self,"Name Exists","Map JSON exists.");return # type: ignore
            size_str,ok_size=QInputDialog.getText(self,"Map Size","Width,Height (tiles):",text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}") # type: ignore
            if ok_size and size_str:
                try:
                    w_s,h_s=size_str.split(',');w_t,h_t=int(w_s.strip()),int(h_s.strip())
                    max_w,max_h=getattr(ED_CONFIG,"MAX_MAP_WIDTH_TILES",1000),getattr(ED_CONFIG,"MAX_MAP_HEIGHT_TILES",1000) # type: ignore
                    if not (1<=w_t<=max_w and 1<=h_t<=max_h): raise ValueError(f"Dims must be 1-{max_w}x{max_h}.")
                    editor_map_utils.init_new_map_state(self.editor_state,clean_name,w_t,h_t);self.map_view_widget.load_map_from_state() # type: ignore
                    self.asset_palette_widget.clear_selection();self.properties_editor_widget.clear_display()
                    if not self._is_embedded: self.update_window_title()
                    self.show_status_message(f"New map '{clean_name}'. Save to create files.",ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT*2) # type: ignore
                    editor_history.push_undo_state(self.editor_state);self.update_edit_actions_enabled_state() # type: ignore
                except Exception as e: QMessageBox.critical(self,"Error",f"Map creation error: {e}");logger.error(f"New map error: {e}",exc_info=True)
        else: self.show_status_message("New map cancelled.")
    @Slot()
    def load_map(self):
        if not self.confirm_unsaved_changes("load map"): return
        maps_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        if not editor_map_utils.ensure_maps_directory_exists(): QMessageBox.critical(self,"Error",f"Maps dir error: {maps_dir}");return # type: ignore
        f_path,_=QFileDialog.getOpenFileName(self,"Load Map",maps_dir,f"Editor Map (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})") # type: ignore
        if f_path:
            if editor_map_utils.load_map_from_json(self.editor_state,f_path): # type: ignore
                self.map_view_widget.load_map_from_state();self.asset_palette_widget.clear_selection();self.properties_editor_widget.clear_display()
                if not self._is_embedded: self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.");editor_history.push_undo_state(self.editor_state);self.update_edit_actions_enabled_state() # type: ignore
            else: QMessageBox.critical(self,"Load Error",f"Failed to load map: {os.path.basename(f_path)}")
        else: self.show_status_message("Load map cancelled.")
    @Slot()
    def save_map_json(self)->bool:
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function=="untitled_map": return self.save_all()
        if editor_map_utils.save_map_to_json(self.editor_state): # type: ignore
            self.show_status_message(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename or '?.json')}.")
            self.editor_state.unsaved_changes=False; self.update_window_title() if not self._is_embedded else None; self.update_edit_actions_enabled_state(); return True
        QMessageBox.critical(self,"Save Error","Failed to save JSON. Check logs.");return False
    @Slot()
    def export_map_py(self)->bool:
        if not self.editor_state.current_json_filename: QMessageBox.warning(self,"Cannot Export","Save map (JSON) first.");return False
        if editor_map_utils.export_map_to_game_python_script(self.editor_state): self.show_status_message(f"Map exported: {os.path.basename(self.editor_state.current_map_filename or '?.py')}");return True # type: ignore
        QMessageBox.critical(self,"Export Error","Failed to export PY. Check logs.");return False
    @Slot()
    def save_all(self)->bool:
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function=="untitled_map":
            name,ok=QInputDialog.getText(self,"Save Map As","Map name (e.g. level_default):")
            if ok and name:
                clean_name=name.strip().lower().replace(" ","_").replace("-","_")
                if not clean_name or any(c in clean_name for c in '/\\:*?"<>|.'): QMessageBox.warning(self,"Invalid Name","Map name invalid.");return False
                self.editor_state.map_name_for_function=clean_name
                maps_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
                if not editor_map_utils.ensure_maps_directory_exists(): QMessageBox.critical(self,"Error",f"Maps dir error: {maps_dir}");return False # type: ignore
                self.editor_state.current_json_filename=os.path.join(maps_dir,clean_name+ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION) # type: ignore
                self.editor_state.current_map_filename=os.path.join(maps_dir,clean_name+ED_CONFIG.GAME_LEVEL_FILE_EXTENSION) # type: ignore
                if not self._is_embedded: self.update_window_title()
            else: self.show_status_message("Save All cancelled: name not provided.");return False
        if self.save_map_json() and self.export_map_py(): self.show_status_message("Map saved (JSON & PY).");return True
        self.show_status_message("Save All failed. Check logs.");return False
    @Slot()
    def rename_map(self):
        if not self.editor_state.current_json_filename: QMessageBox.information(self,"Rename Map","Load/save a map first.");return
        old_name=self.editor_state.map_name_for_function
        new_name,ok=QInputDialog.getText(self,"Rename Map",f"New name for '{old_name}':",text=old_name)
        if ok and new_name:
            clean_new=new_name.strip().lower().replace(" ","_").replace("-","_")
            if not clean_new or any(c in clean_new for c in '/\\:*?"<>|.'): QMessageBox.warning(self,"Invalid Name","New name invalid.");return
            if clean_new==old_name: self.show_status_message("Rename cancelled: name unchanged.");return
            maps_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
            if not editor_map_utils.ensure_maps_directory_exists(): QMessageBox.critical(self,"Error",f"Maps dir error: {maps_dir}");return # type: ignore
            new_json=os.path.join(maps_dir,clean_new+ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION) # type: ignore
            if os.path.exists(new_json) and os.path.normcase(new_json)!=os.path.normcase(self.editor_state.current_json_filename): QMessageBox.warning(self,"Rename Error",f"JSON '{os.path.basename(new_json)}' exists.");return
            old_json,old_py=self.editor_state.current_json_filename,self.editor_state.current_map_filename
            new_py=os.path.join(maps_dir,clean_new+ED_CONFIG.GAME_LEVEL_FILE_EXTENSION) # type: ignore
            try:
                if old_json and os.path.exists(old_json): os.rename(old_json,new_json)
                self.editor_state.map_name_for_function,self.editor_state.current_json_filename,self.editor_state.current_map_filename=clean_new,new_json,new_py
                if not editor_map_utils.save_map_to_json(self.editor_state): QMessageBox.critical(self,"Rename Error","Failed to save to new JSON.");return # type: ignore
                if old_py and os.path.exists(old_py) and os.path.normcase(old_py)!=os.path.normcase(new_py): os.remove(old_py)
                if editor_map_utils.export_map_to_game_python_script(self.editor_state): self.show_status_message(f"Map renamed to '{clean_new}'.") # type: ignore
                else: QMessageBox.warning(self,"Rename Warning","Renamed JSON, but new PY export failed. Try 'Save All'.");self.editor_state.unsaved_changes=True
                if not self._is_embedded: self.update_window_title();self.update_edit_actions_enabled_state()
            except Exception as e: QMessageBox.critical(self,"Rename Error",f"Rename error: {e}");logger.error(f"Rename error: {e}",exc_info=True)
        else: self.show_status_message("Rename map cancelled.")
    @Slot()
    def delete_map_file(self):
        maps_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        if not editor_map_utils.ensure_maps_directory_exists(): QMessageBox.critical(self,"Error",f"Maps dir error: {maps_dir}");return # type: ignore
        f_path,_=QFileDialog.getOpenFileName(self,"Select Map to Delete",maps_dir,f"Editor Map (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})") # type: ignore
        if f_path:
            map_name_del=os.path.splitext(os.path.basename(f_path))[0]
            reply=QMessageBox.warning(self,"Confirm Delete",f"Delete ALL files (JSON & PY) for '{map_name_del}'?\nCANNOT BE UNDONE.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if reply==QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state,f_path): # type: ignore
                    self.show_status_message(f"Map '{map_name_del}' files deleted.")
                    if self.editor_state.current_json_filename and os.path.normcase(self.editor_state.current_json_filename)==os.path.normcase(f_path):
                        self.editor_state.reset_map_context();self.map_view_widget.load_map_from_state()
                        self.asset_palette_widget.clear_selection();self.properties_editor_widget.clear_display()
                        if not self._is_embedded: self.update_window_title();self.update_edit_actions_enabled_state()
                else: QMessageBox.critical(self,"Delete Error",f"Failed to delete files for '{map_name_del}'.")
            else: self.show_status_message("Delete map cancelled.")
        else: self.show_status_message("Delete map selection cancelled.")
    @Slot()
    def export_map_as_image(self):
        if not self.editor_state.placed_objects and not self.editor_state.current_json_filename: QMessageBox.information(self,"Export Error","No map content.");return
        def_name=self.editor_state.map_name_for_function if self.editor_state.map_name_for_function!="untitled_map" else "untitled_export"
        sugg_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"map_exports")
        if not os.path.exists(sugg_dir):
            try: os.makedirs(sugg_dir)
            except OSError: sugg_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),ED_CONFIG.MAPS_DIRECTORY) # type: ignore
        f_path,_=QFileDialog.getSaveFileName(self,"Export Map as Image",os.path.join(sugg_dir,def_name+".png"),"PNG (*.png);;All (*)")
        if not f_path: self.show_status_message("Export image cancelled.");return
        try:
            scene=self.map_view_widget.scene();
            if not scene: QMessageBox.critical(self,"Export Error","No scene.");return
            target_rect=scene.itemsBoundingRect()
            if target_rect.isEmpty(): QMessageBox.information(self,"Export Error","Map empty.");return
            pad=20;target_rect.adjust(-pad,-pad,pad,pad);img_w,img_h=int(target_rect.width()),int(target_rect.height())
            if img_w<=0 or img_h<=0: QMessageBox.critical(self,"Export Error",f"Invalid image dims: {img_w}x{img_h}");return
            img=QImage(img_w,img_h,QImage.Format.Format_ARGB32_Premultiplied);img.fill(Qt.GlobalColor.transparent)
            painter=QPainter(img);painter.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.SmoothPixmapTransform,False)
            scene.render(painter,QRectF(img.rect()),target_rect);painter.end()
            if img.save(f_path,"PNG"): self.show_status_message(f"Map exported as image: {os.path.basename(f_path)}")
            else: QMessageBox.critical(self,"Export Error",f"Failed to save image:\n{f_path}")
        except Exception as e: QMessageBox.critical(self,"Export Error",f"Image export error:\n{e}");logger.error(f"Export image error: {e}",exc_info=True)
    @Slot()
    def undo(self):
        if editor_history.undo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state();self.update_edit_actions_enabled_state()
            sel_items=self.map_view_widget.map_scene.selectedItems()
            if len(sel_items)==1 and isinstance(sel_items[0],MapObjectItem): self.properties_editor_widget.display_map_object_properties(sel_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful."); self.update_window_title() if not self._is_embedded else None
        else: self.show_status_message("Nothing to undo.")
    @Slot()
    def redo(self):
        if editor_history.redo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state();self.update_edit_actions_enabled_state()
            sel_items=self.map_view_widget.map_scene.selectedItems()
            if len(sel_items)==1 and isinstance(sel_items[0],MapObjectItem): self.properties_editor_widget.display_map_object_properties(sel_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful."); self.update_window_title() if not self._is_embedded else None
        else: self.show_status_message("Nothing to redo.")
    @Slot()
    def toggle_grid(self): self.editor_state.show_grid=not self.editor_state.show_grid;self.toggle_grid_action.setChecked(self.editor_state.show_grid);self.map_view_widget.update_grid_visibility();self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")
    @Slot()
    def change_background_color(self):
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function=="untitled_map":
            if not self.editor_state.placed_objects: pass
        new_q_color=QColorDialog.getColor(QColor(*self.editor_state.background_color),self,"Select Background Color")
        if new_q_color.isValid():
            self.editor_state.background_color=(new_q_color.red(),new_q_color.green(),new_q_color.blue())
            self.map_view_widget.update_background_color();self.handle_map_content_changed()
            self.show_status_message(f"BG color: {self.editor_state.background_color}.")
        else: self.show_status_message("BG color change cancelled.")
    @Slot()
    def about_dialog(self): QMessageBox.about(self,"About Editor","Platformer Level Editor (PySide6)")
    def keyPressEvent(self,event:QKeyEvent):
        key,active_panel=event.key(),next((p for i,p in enumerate(self._focusable_panels) if i==self._current_focused_panel_index),None) if self._focusable_panels else None
        if active_panel and hasattr(active_panel,'handle_key_event_for_controller_nav') and active_panel.handle_key_event_for_controller_nav(event): event.accept();return # type: ignore
        
        if key==Qt.Key.Key_Escape and not self._is_embedded: 
            self.close();event.accept()
        # MODIFIED: Corrected syntax for conditional return
        elif self.map_view_widget.hasFocus() and hasattr(self.map_view_widget,'keyPressEvent'): 
            self.map_view_widget.keyPressEvent(event) # type: ignore
            if event.isAccepted(): 
                return 
        super().keyPressEvent(event)
    def closeEvent(self,event):
        if self.confirm_unsaved_changes("exit editor"):
            if self._controller_input_timer and self._controller_input_timer.isActive(): self._controller_input_timer.stop()
            if _PYGAME_AVAILABLE and self._joysticks:
                for joy in self._joysticks: 
                    if joy and joy.get_init(): joy.quit()
            for dock_attr_name in ["asset_palette_dock", "properties_editor_dock", "minimap_dock"]:
                dock = getattr(self, dock_attr_name, None)
                if dock and not dock.objectName(): dock.setObjectName(dock_attr_name.title().replace("_", ""))
            self.settings.setValue("geometry",self.saveGeometry());self.settings.setValue("windowState",self.saveState());event.accept()
        else: event.ignore()
    def save_geometry_and_state(self):
        for dock_attr_name in ["asset_palette_dock", "properties_editor_dock", "minimap_dock"]:
            dock=getattr(self,dock_attr_name,None)
            if dock and not dock.objectName(): dock.setObjectName(dock_attr_name.title().replace("_",""))
        self.settings.setValue("geometry",self.saveGeometry());self.settings.setValue("windowState",self.saveState())
    def restore_geometry_and_state(self)->bool:
        geom,state=self.settings.value("geometry"),self.settings.value("windowState")
        restored_geom,restored_state=False,False
        try:
            if geom is not None: self.restoreGeometry(geom);restored_geom=True
            if state is not None: self.restoreState(state);restored_state=True
            return restored_geom or restored_state
        except Exception as e:
            logger.error(f"Error restoring window geom/state: {e}. Resetting if standalone.",exc_info=True)
            if not self._is_embedded:
                primary_screen = QApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    dw,dh=ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH,ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                    px,py=screen_geo.x()+(screen_geo.width()-dw)//2,screen_geo.y()+(screen_geo.height()-dh)//2
                    self.setGeometry(px,py,dw,dh)
                else: self.setGeometry(50,50,ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH,ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
            return False

def editor_main(parent_app_instance: Optional[QApplication]=None, embed_mode:bool=False):
    if _IS_STANDALONE_EXECUTION: 
        try: os.chdir(os.path.dirname(os.path.abspath(__file__))); logger.info(f"Standalone CWD: {os.getcwd()}") if logger else None
        except Exception as e_chdir: logger.error(f"Standalone CWD change error: {e_chdir}") if logger else None

    logger.info(f"editor_main(). Embed:{embed_mode}, StandaloneCtx:{_IS_STANDALONE_EXECUTION}") if logger else None
    app=QApplication.instance()
    if app is None:
        if parent_app_instance: app=parent_app_instance
        elif _IS_STANDALONE_EXECUTION: app=QApplication(sys.argv)
        else: raise RuntimeError("Editor needs QApplication instance, especially in embed_mode.")
    
    main_window=EditorMainWindow(embed_mode=embed_mode)
    if not embed_mode:
        exit_code=0
        try: exit_code=app.exec()
        except Exception as e_loop:
            log_path=log_file_path_for_error_msg if 'log_file_path_for_error_msg' in globals() and log_file_path_for_error_msg else "editor_debug.log"
            QMessageBox.critical(None,"Editor Critical Error",f"Error: {e_loop}\nLog: {log_path}")
            logger.critical(f"QApp exec error: {e_loop}",exc_info=True) if logger else None; exit_code=1
        finally:
            if hasattr(main_window,'isVisible') and main_window.isVisible(): main_window.save_geometry_and_state()
            if _PYGAME_AVAILABLE and pygame.get_init(): pygame.quit()
            logger.info(f"Editor standalone session ended. Exit: {exit_code}") if logger else None
        return exit_code
    return main_window

if __name__ == "__main__":
    print("--- editor.py standalone execution ---")
    if _PYGAME_AVAILABLE and not pygame.get_init():
        try: pygame.init(); pygame.joystick.init() if not pygame.joystick.get_init() else None; print("INFO: Pygame init for standalone.")
        except Exception as e_py_main: print(f"WARN: Pygame init failed in main: {e_py_main}")
    sys.exit(editor_main(embed_mode=False))

#################### END OF FILE: editor\editor.py ####################