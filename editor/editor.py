#################### START OF FILE: editor.py ####################

# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 2.2.2 (Initialize crop_rect for uploaded images)
Level Editor for the Platformer Game (PySide6 Version).
- Map files (.py, .json) now organized into named subfolders within /maps/.
- Supports uploading images to the editor for use as map objects.
- Images can be resized (Shift-drag for aspect ratio), layered, and set as background/obstacle.
- Added resizable Trigger Squares that can link to other maps, be colored, or display an image.
- "Save Map" (Ctrl+S) now saves both editor (.json) and game-ready (.py) files.
- Uses custom QGraphicsItem classes for images and triggers.
- Removed trailing semicolons and reviewed indentation.
- Added crop_rect initialization for newly uploaded custom images.
"""
import sys
import os
import logging
import traceback
import time
import shutil
from typing import Optional, Tuple, List, Any, Dict

_IS_STANDALONE_EXECUTION = (__name__ == "__main__")
_EDITOR_MODULE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
_PROJECT_ROOT_DIR = os.path.dirname(_EDITOR_MODULE_DIR)

if _IS_STANDALONE_EXECUTION:
    print(f"INFO: editor.py running in standalone mode from: {_EDITOR_MODULE_DIR}")
    if _PROJECT_ROOT_DIR not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT_DIR)
        print(f"INFO: Added project root '{_PROJECT_ROOT_DIR}' to sys.path for standalone execution.")
else:
    print(f"INFO: editor.py running as a module (package: {__package__})")

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, QFileDialog,
    QColorDialog, QInputDialog, QLabel, QSizePolicy, QMenu
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent, QImage, QPainter, QFont, QCursor, QGuiApplication
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF, Signal, QPoint, QFileInfo

try:
    import pygame
    _PYGAME_AVAILABLE = True
    logger_init_pygame = logging.getLogger("PygameInit")
    logger_init_pygame.info("Pygame imported successfully for controller support.")
except ImportError:
    _PYGAME_AVAILABLE = False
    logger_init_pygame = logging.getLogger("PygameInit")
    logger_init_pygame.warning("Pygame not found. Controller navigation will be unavailable.")

_IMPORTS_SUCCESSFUL_METHOD = "Unknown"
try:
    logger_init_pygame.info("Attempting relative imports for editor modules...")
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_assets
    from . import editor_map_utils
    from . import editor_history
    from .map_view_widget import MapViewWidget
    from .editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    from .editor_actions import *

    if ED_CONFIG.MINIMAP_ENABLED: # type: ignore
        from .minimap_widget import MinimapWidget
    if _PYGAME_AVAILABLE:
        from config import init_pygame_and_joystick_globally, get_joystick_objects
    _IMPORTS_SUCCESSFUL_METHOD = "Relative"
    logger_init_pygame.info("Editor modules imported successfully using RELATIVE paths.")
except ImportError as e_relative_import:
    logger_init_pygame.warning(f"Relative import failed: {e_relative_import}. Attempting absolute imports.")
    try:
        from editor import editor_config as ED_CONFIG # type: ignore
        from editor.editor_state import EditorState # type: ignore
        from editor import editor_assets # type: ignore
        from editor import editor_map_utils # type: ignore
        from editor import editor_history # type: ignore
        from editor.map_view_widget import MapViewWidget # type: ignore
        from editor.editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget # type: ignore
        from editor.editor_actions import * # type: ignore

        if ED_CONFIG.MINIMAP_ENABLED: # type: ignore
            from editor.minimap_widget import MinimapWidget # type: ignore
        if _PYGAME_AVAILABLE:
            from config import init_pygame_and_joystick_globally, get_joystick_objects # type: ignore
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (from editor.*)"
        logger_init_pygame.info("Editor modules imported successfully using ABSOLUTE paths (from editor.*).")
    except ImportError as e_absolute_import:
        logger_init_pygame.critical(f"CRITICAL: Both relative and absolute imports for editor modules failed: {e_absolute_import}")
        raise ImportError(f"Failed to import critical editor modules. Relative: {e_relative_import}. Absolute: {e_absolute_import}") from e_absolute_import

logger: Optional[logging.Logger] = None
log_file_path_for_error_msg = "editor_qt_debug.log"
try:
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_file_name = ED_CONFIG.LOG_FILE_NAME if hasattr(ED_CONFIG, "LOG_FILE_NAME") else "editor_qt_debug.log" # type: ignore
    log_file_path_for_error_msg = os.path.join(logs_dir, log_file_name)
    numeric_log_level = getattr(logging, ED_CONFIG.LOG_LEVEL.upper() if hasattr(ED_CONFIG, "LOG_LEVEL") else "DEBUG", logging.DEBUG) # type: ignore
    log_format_str = ED_CONFIG.LOG_FORMAT if hasattr(ED_CONFIG, "LOG_FORMAT") else '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s' # type: ignore
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
    logging.basicConfig(
        level=numeric_log_level,
        format=log_format_str,
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w', encoding='utf-8')]
    )
    logger = logging.getLogger("EditorMainWindowLogger")
    logger.info(f"Editor session started. Logging initialized. Imports via: {_IMPORTS_SUCCESSFUL_METHOD}")
except Exception as e_log_setup:
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE FALLBACK (editor.py logger setup): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("EditorMainWindowLogger_Fallback")
    logger.error(f"CRITICAL ERROR DURING FILE LOGGING SETUP (editor.py): {e_log_setup}. Using console.", exc_info=True)

SWITCH_A_BTN = 0
SWITCH_B_BTN = 1
SWITCH_X_BTN = 2
SWITCH_Y_BTN = 3
SWITCH_L_BTN = 4
SWITCH_R_BTN = 5
SWITCH_ZL_BTN = 6
SWITCH_ZR_BTN = 7
SWITCH_MINUS_BTN = 8
SWITCH_PLUS_BTN = 9
SWITCH_L_STICK_BTN = 10
SWITCH_R_STICK_BTN = 11
SWITCH_L_STICK_X_AXIS = 0
SWITCH_L_STICK_Y_AXIS = 1
SWITCH_R_STICK_X_AXIS = 2
SWITCH_R_STICK_Y_AXIS = 3
SWITCH_ZL_AXIS = 4
SWITCH_ZR_AXIS = 5
SWITCH_DPAD_HAT_ID = 0

class EditorMainWindow(QMainWindow):
    controller_action_dispatched = Signal(str, object)

    def __init__(self, parent: Optional[QWidget] = None, embed_mode: bool = False):
        super().__init__(parent)
        self._is_embedded = embed_mode
        if logger: logger.info(f"Initializing EditorMainWindow... Embedded: {self._is_embedded}")

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
        self.update_delete_selection_action_enabled_state() # Update for delete action

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
            if restored_successfully:
                self.show()
            else:
                primary_screen = QGuiApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH # type: ignore
                    default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                    pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                    pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                    self.showMaximized()
                else:
                    self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
                    self.showMaximized()
        else:
            if logger: logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            self.restore_geometry_and_state()

        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
            err_msg_maps_dir = f"Base maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}" # type: ignore
            if not self._is_embedded:
                QMessageBox.critical(self, "Error", err_msg_maps_dir)
            elif logger:
                logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox)")
        
        if logger: logger.info("EditorMainWindow initialized.")
        if hasattr(self, 'status_bar') and self.status_bar:
            self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore

        if self._focusable_panels and _PYGAME_AVAILABLE and self._primary_joystick:
            self._set_panel_controller_focus(0)
        elif self._focusable_panels:
            self._focusable_panels[0].setFocus(Qt.FocusReason.OtherFocusReason)

    def init_ui(self):
        if logger: logger.debug("Initializing UI components...")
        self._focusable_panels: List[QWidget] = []
        
        self.map_view_widget = MapViewWidget(self.editor_state, self)
        self.setCentralWidget(self.map_view_widget)
        self._focusable_panels.append(self.map_view_widget)

        # Connect scene selection changed to update delete action enabled state
        self.map_view_widget.map_scene.selectionChanged.connect(self.update_delete_selection_action_enabled_state)


        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self)
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(max(200, ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50)) # type: ignore
        self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 100) # type: ignore
        self._focusable_panels.append(self.asset_palette_widget)

        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self)
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
        self.map_view_widget.context_menu_requested_for_item.connect(self.show_map_item_context_menu)

        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed) # Ensure general content change signal
        self.properties_editor_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)
        self.properties_editor_widget.upload_image_for_trigger_requested.connect(self.handle_upload_image_for_trigger)

        if self.minimap_widget:
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs) # type: ignore
        if logger: logger.debug("UI components initialized.")

    def _init_controller_system(self):
        if logger: logger.info("Initializing controller system...")
        try:
            init_pygame_and_joystick_globally(force_rescan=True) # type: ignore
            self._joysticks = get_joystick_objects() # type: ignore
            if not self._joysticks or all(joy is None for joy in self._joysticks):
                self._primary_joystick = None
                if logger: logger.info("No joysticks detected.")
                return
            for i, joy in enumerate(self._joysticks): # type: ignore
                if joy:
                    try:
                        if not joy.get_init(): joy.init()
                        self._primary_joystick = joy
                        if logger: logger.info(f"Primary joystick: {joy.get_name()}")
                        break
                    except pygame.error as e:
                        if logger: logger.warning(f"Could not init joystick {i}: {e}")
            if not self._primary_joystick:
                if logger: logger.warning("No valid joystick initialized as primary.")
                return
            self._controller_input_timer = QTimer(self)
            self._controller_input_timer.setInterval(getattr(ED_CONFIG, "CONTROLLER_POLL_INTERVAL_MS", 16)) # type: ignore
            self._controller_input_timer.timeout.connect(self._poll_controller_input)
            self._controller_input_timer.start()
            if logger: logger.info("Controller input polling started.")
        except Exception as e:
            if logger: logger.error(f"Error initializing controller system: {e}", exc_info=True)
            self._primary_joystick = None

    def _poll_controller_input(self):
        if not _PYGAME_AVAILABLE or not self._primary_joystick:
            return
        pygame.event.pump()
        current_time = time.monotonic()
        joy = self._primary_joystick
        if not joy.get_init():
            try:
                joy.init()
            except pygame.error:
                return
        button_map = {SWITCH_B_BTN: ACTION_UI_ACCEPT, SWITCH_A_BTN: ACTION_UI_CANCEL, SWITCH_Y_BTN: ACTION_MAP_TOOL_PRIMARY, SWITCH_X_BTN: ACTION_MAP_TOOL_SECONDARY, SWITCH_L_BTN: ACTION_UI_TAB_PREV, SWITCH_R_BTN: ACTION_UI_TAB_NEXT, SWITCH_ZL_BTN: ACTION_MAP_ZOOM_OUT, SWITCH_ZR_BTN: ACTION_MAP_ZOOM_IN, SWITCH_PLUS_BTN: ACTION_UI_MENU, SWITCH_MINUS_BTN: ACTION_UI_FOCUS_NEXT}
        for btn_id, action in button_map.items():
            if btn_id >= joy.get_numbuttons():
                continue
            pressed = joy.get_button(btn_id)
            last_state = self._button_last_state.get(btn_id, False)
            if pressed and not last_state:
                self.controller_action_dispatched.emit(action, True)
            self._button_last_state[btn_id] = pressed
        if joy.get_numhats() > 0:
            hat_value = joy.get_hat(SWITCH_DPAD_HAT_ID)
            if hat_value != self._last_dpad_value:
                if hat_value == (0, 1): self.controller_action_dispatched.emit(ACTION_UI_UP, None)
                elif hat_value == (0, -1): self.controller_action_dispatched.emit(ACTION_UI_DOWN, None)
                elif hat_value == (-1, 0): self.controller_action_dispatched.emit(ACTION_UI_LEFT, None)
                elif hat_value == (1, 0): self.controller_action_dispatched.emit(ACTION_UI_RIGHT, None)
                self._last_dpad_value = hat_value
        axis_map = {SWITCH_L_STICK_X_AXIS: (ACTION_UI_LEFT, ACTION_UI_RIGHT), SWITCH_L_STICK_Y_AXIS: (ACTION_UI_UP, ACTION_UI_DOWN)}
        for axis_id, (neg_action, pos_action) in axis_map.items():
            if axis_id >= joy.get_numaxes():
                continue
            axis_val = joy.get_axis(axis_id)
            direction_sign = 0
            if axis_val < -self._controller_axis_deadzone: direction_sign = -1
            elif axis_val > self._controller_axis_deadzone: direction_sign = 1
            key = (joy.get_id(), axis_id, direction_sign)
            if direction_sign != 0:
                action_to_emit = neg_action if direction_sign == -1 else pos_action
                last_event_time_for_key_dir = self._controller_axis_last_event_time.get(key, 0)
                can_emit = False
                if current_time - last_event_time_for_key_dir > self._controller_axis_repeat_delay:
                    can_emit = True
                elif current_time - last_event_time_for_key_dir > self._controller_axis_repeat_interval:
                    can_emit = True # Allow repeat after initial delay + interval
                if can_emit:
                    self.controller_action_dispatched.emit(action_to_emit, axis_val)
                    self._controller_axis_last_event_time[key] = current_time
            else: # Reset timers if axis is centered
                key_neg = (joy.get_id(), axis_id, -1)
                key_pos = (joy.get_id(), axis_id, 1)
                if key_neg in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_neg] = 0 # Reset to allow immediate response next time
                if key_pos in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_pos] = 0


    @Slot(str, object)
    def _dispatch_controller_action_to_panel(self, action: str, value: Any):
        if logger: logger.debug(f"Controller action received: {action}, Value: {value}")
        if action == ACTION_UI_FOCUS_NEXT:
            self._cycle_panel_focus_next()
            return
        elif action == ACTION_UI_FOCUS_PREV:
            self._cycle_panel_focus_prev()
            return
        elif action == ACTION_UI_MENU:
            if self.menu_bar and self.menu_bar.actions():
                first_menu = self.menu_bar.actions()[0].menu()
                if first_menu:
                    first_menu.popup(self.mapToGlobal(self.menu_bar.pos() + QPoint(0, self.menu_bar.height())))
            return
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
            focused_widget = self._focusable_panels[self._current_focused_panel_index]
            if hasattr(focused_widget, "handle_controller_action"):
                try:
                    focused_widget.handle_controller_action(action, value) # type: ignore
                except Exception as e:
                    if logger: logger.error(f"Error in {type(focused_widget).__name__}.handle_controller_action: {e}", exc_info=True)
            elif logger:
                logger.warning(f"Focused panel {type(focused_widget).__name__} has no handle_controller_action.")
        elif logger:
            logger.warning(f"No panel focused or index out of bounds: {self._current_focused_panel_index}")


    def _set_panel_controller_focus(self, new_index: int):
        if not self._focusable_panels or not (0 <= new_index < len(self._focusable_panels)):
            if logger: logger.warning(f"Attempt to set focus to invalid index {new_index}")
            return
        old_index = self._current_focused_panel_index
        if 0 <= old_index < len(self._focusable_panels) and old_index != new_index :
            old_panel = self._focusable_panels[old_index]
            if hasattr(old_panel, "on_controller_focus_lost"):
                try:
                    old_panel.on_controller_focus_lost() # type: ignore
                except Exception as e:
                    if logger: logger.error(f"Error in {type(old_panel).__name__}.on_controller_focus_lost: {e}", exc_info=True)
            parent_dock_old = old_panel.parent()
            while parent_dock_old and not isinstance(parent_dock_old, QDockWidget):
                parent_dock_old = parent_dock_old.parent()
            if isinstance(parent_dock_old, QDockWidget):
                parent_dock_old.setStyleSheet("")
        self._current_focused_panel_index = new_index
        new_panel = self._focusable_panels[new_index]
        new_panel.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(new_panel, "on_controller_focus_gained"):
            try:
                new_panel.on_controller_focus_gained() # type: ignore
            except Exception as e:
                if logger: logger.error(f"Error in {type(new_panel).__name__}.on_controller_focus_gained: {e}", exc_info=True)
        panel_name_for_status = type(new_panel).__name__
        parent_dock_new = new_panel.parent()
        while parent_dock_new and not isinstance(parent_dock_new, QDockWidget):
            parent_dock_new = parent_dock_new.parent()
        if isinstance(parent_dock_new, QDockWidget):
            panel_name_for_status = parent_dock_new.windowTitle()
            focus_border_color = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER.split(' ')[-1] if ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER else 'lightblue' # type: ignore
            parent_dock_new.setStyleSheet(f"QDockWidget::title {{ background-color: {focus_border_color}; color: black; border: 1px solid black; padding: 2px; }}")
        elif isinstance(new_panel, MapViewWidget):
            panel_name_for_status = "Map View"
        self.show_status_message(f"Controller Focus: {panel_name_for_status}", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        if logger: logger.info(f"Controller focus set to: {panel_name_for_status} (Index: {new_index})")

    def _cycle_panel_focus_next(self):
        if not self._focusable_panels:
            return
        new_index = (self._current_focused_panel_index + 1) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def _cycle_panel_focus_prev(self):
        if not self._focusable_panels:
            return
        new_index = (self._current_focused_panel_index - 1 + len(self._focusable_panels)) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def create_actions(self):
        if logger: logger.debug("Creating actions...")
        self.new_map_action = QAction("&New Map...", self, shortcut=QKeySequence.StandardKey.New, statusTip="Create a new map", triggered=self.new_map)
        self.load_map_action = QAction("&Load Map...", self, shortcut=QKeySequence.StandardKey.Open, statusTip="Load an existing map or map folder", triggered=self.load_map)
        self.save_map_action = QAction("&Save Map", self, shortcut=QKeySequence.StandardKey.Save, statusTip="Save current map (editor data and game export)", triggered=self.save_map)
        self.rename_map_action = QAction("&Rename Current Map...", self, statusTip="Rename the current map's files and folder", triggered=self.rename_map)
        self.delete_map_folder_action = QAction("&Delete Map Folder...", self, statusTip="Delete the current map's folder and all its contents", triggered=self.delete_map_folder)
        self.export_map_as_image_action = QAction("Export Map as &Image...", self, shortcut="Ctrl+Shift+P", statusTip="Export map view as PNG", triggered=self.export_map_as_image)
        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit, statusTip="Exit the editor", triggered=self.close)
        
        self.undo_action = QAction("&Undo", self, shortcut=QKeySequence.StandardKey.Undo, statusTip="Undo last action", triggered=self.undo)
        self.redo_action = QAction("&Redo", self, shortcut=QKeySequence.StandardKey.Redo, statusTip="Redo last undone action", triggered=self.redo)
        
        # ADDED: Delete Selection Action
        self.delete_selection_action = QAction("Delete Selection", self, shortcut=QKeySequence.StandardKey.Delete, statusTip="Delete selected map objects", triggered=self.map_view_widget.delete_selected_map_objects)
        self.delete_selection_action.setEnabled(False) 

        self.toggle_grid_action = QAction("Toggle &Grid", self, shortcut="Ctrl+G", statusTip="Show/Hide grid", triggered=self.toggle_grid, checkable=True)
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.change_bg_color_action = QAction("Change &Background Color...", self, statusTip="Change map background color", triggered=self.change_background_color)
        self.zoom_in_action = QAction("Zoom &In", self, shortcut=QKeySequence.StandardKey.ZoomIn, statusTip="Zoom in", triggered=self.map_view_widget.zoom_in)
        self.zoom_out_action = QAction("Zoom &Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, statusTip="Zoom out", triggered=self.map_view_widget.zoom_out)
        self.zoom_reset_action = QAction("Reset &Zoom", self, shortcut="Ctrl+0", statusTip="Reset zoom", triggered=self.map_view_widget.reset_zoom)
        self.upload_image_action = QAction("&Upload Image to Map...", self, statusTip="Upload image as custom object", triggered=self.upload_image_to_map)
        self.upload_image_action.setEnabled(False)
        if logger: logger.debug("Actions created.")

    def create_menus(self):
        if logger: logger.debug("Creating menus...")
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("&File")
        file_menu.addAction(self.new_map_action)
        file_menu.addAction(self.load_map_action)
        file_menu.addAction(self.rename_map_action)
        file_menu.addAction(self.delete_map_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_map_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_map_as_image_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        
        edit_menu = self.menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_selection_action) # ADDED
        edit_menu.addSeparator()
        edit_menu.addAction(self.change_bg_color_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.upload_image_action)
        
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
        help_menu.addAction(QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog))
        if logger: logger.debug("Menus created.")

    def create_status_bar(self):
        if logger: logger.debug("Creating status bar...")
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # type: ignore
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250)
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        if logger: logger.debug("Status bar created.")

    @Slot(str, int)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT): # type: ignore
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage(message, timeout)
        if logger: logger.info(f"Status: {message}")

    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        world_x, world_y, tile_x, tile_y, zoom_val = coords
        self.map_coords_label.setText(f" Map:({int(world_x)},{int(world_y)}) Tile:({tile_x},{tile_y}) Zoom:{zoom_val:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        if logger and not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes: False -> True.")
        self.editor_state.unsaved_changes = True
        if not self._is_embedded:
            self.update_window_title()
        self.update_edit_actions_enabled_state()
        # self.update_delete_selection_action_enabled_state() # Selection state might not have changed
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_widget') and self.minimap_widget: # type: ignore
            if logger: logger.debug("Notifying minimap to redraw content due to map change.")
            self.minimap_widget.schedule_map_content_redraw()
        if logger: logger.debug(f"handle_map_content_changed done. Unsaved: {self.editor_state.unsaved_changes}")

    def update_window_title(self):
        if self._is_embedded:
            return
        title = "Platformer Level Editor"
        map_name = self.editor_state.map_name_for_function
        if map_name and map_name != "untitled_map":
            title += f" - {map_name}"
        if self.editor_state.unsaved_changes:
            title += "*"
        self.setWindowTitle(title)

    @Slot() # ADDED: Slot to update delete selection action state
    def update_delete_selection_action_enabled_state(self):
        if hasattr(self, 'map_view_widget') and hasattr(self.map_view_widget, 'map_scene'):
            can_delete = bool(self.map_view_widget.map_scene.selectedItems())
            self.delete_selection_action.setEnabled(can_delete)
        else:
            self.delete_selection_action.setEnabled(False)


    def update_edit_actions_enabled_state(self):
        map_is_named = bool(self.editor_state.map_name_for_function and self.editor_state.map_name_for_function != "untitled_map")
        map_has_file = bool(self.editor_state.current_json_filename)
        
        can_save_due_to_named_with_objects = map_is_named and bool(self.editor_state.placed_objects)
        map_is_properly_loaded_or_newly_named = map_has_file or can_save_due_to_named_with_objects
        
        self.save_map_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.rename_map_action.setEnabled(map_has_file)
        self.delete_map_folder_action.setEnabled(map_has_file)
        self.undo_action.setEnabled(len(self.editor_state.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack) > 0)
        
        map_active_for_view_edit = map_is_named or bool(self.editor_state.placed_objects)
        
        self.change_bg_color_action.setEnabled(map_active_for_view_edit)
        self.toggle_grid_action.setEnabled(map_active_for_view_edit)
        self.zoom_in_action.setEnabled(map_active_for_view_edit)
        self.zoom_out_action.setEnabled(map_active_for_view_edit)
        self.zoom_reset_action.setEnabled(map_active_for_view_edit)
        
        can_export_image = map_active_for_view_edit and (bool(self.editor_state.placed_objects) or map_has_file)
        self.export_map_as_image_action.setEnabled(can_export_image)
        
        self.upload_image_action.setEnabled(map_is_named)

        self.update_delete_selection_action_enabled_state() # Also update delete action here


    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool:
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes", f"Unsaved changes. Save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                return self.save_map()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

    @Slot()
    def new_map(self):
        if logger: logger.info("New Map action triggered.")
        if not self.confirm_unsaved_changes("create a new map"):
            return
        map_name, ok = QInputDialog.getText(self, "New Map", "Enter map name (e.g., level_1):")
        if ok and map_name:
            clean_map_name = editor_map_utils.sanitize_map_name(map_name) # type: ignore
            if not clean_map_name:
                QMessageBox.warning(self, "Invalid Name", "Map name is invalid or results in an empty name after sanitization."); return
            map_folder_path = editor_map_utils.get_map_specific_folder_path(self.editor_state, clean_map_name) # type: ignore
            if map_folder_path and os.path.exists(map_folder_path):
                QMessageBox.warning(self, "Name Exists", f"A map folder (or file) named '{clean_map_name}' already exists in the maps directory."); return
            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):", text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}") # type: ignore
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(',')
                    width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w, max_h = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 2000), getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 2000) # type: ignore
                    if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h):
                        raise ValueError(f"Dimensions must be between 1x1 and {max_w}x{max_h}.")
                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles) # type: ignore
                    self.map_view_widget.load_map_from_state()
                    self.asset_palette_widget.clear_selection()
                    self.asset_palette_widget.populate_assets()
                    self.properties_editor_widget.clear_display()
                    if not self._is_embedded:
                        self.update_window_title()
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore
                    editor_history.push_undo_state(self.editor_state) # type: ignore
                    self.update_edit_actions_enabled_state()
                except ValueError as e_size:
                    QMessageBox.warning(self, "Invalid Size", f"Invalid map size format or value: {e_size}")
                except Exception as e_new_map:
                    if logger: logger.error(f"Error during new map creation: {e_new_map}", exc_info=True)
                    QMessageBox.critical(self, "Error", f"Could not create new map: {e_new_map}")
        else:
            self.show_status_message("New map cancelled.")

    @Slot()
    def load_map(self):
        if logger: logger.info("Load Map action triggered.")
        if not self.confirm_unsaved_changes("load another map"):
            return
        maps_base_dir = editor_map_utils.get_maps_base_directory() # type: ignore
        if not editor_map_utils.ensure_maps_directory_exists(): # type: ignore
             QMessageBox.critical(self, "Error", f"Cannot access or create base maps directory: {maps_base_dir}")
             return
        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})" # type: ignore
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Map JSON file", maps_base_dir, json_filter)
        if file_path:
            if logger: logger.info(f"Attempting to load map from: {file_path}")
            if editor_map_utils.load_map_from_json(self.editor_state, file_path): # type: ignore
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.asset_palette_widget.populate_assets()
                self.properties_editor_widget.clear_display()
                if not self._is_embedded:
                    self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state) # type: ignore
                self.update_edit_actions_enabled_state()
            else:
                QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else:
            self.show_status_message("Load map cancelled.")

    def _internal_save_map_json(self) -> bool:
        if logger: logger.debug("Internal Save Map (JSON) called.")
        if editor_map_utils.save_map_to_json(self.editor_state): # type: ignore
            if logger: logger.info(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename or 'unknown.json')}.")
            return True
        else:
            QMessageBox.critical(self, "Save Error", "Failed to save map editor data (.json). Check logs.")
            return False

    def _internal_export_map_py(self) -> bool:
        if logger: logger.debug("Internal Export Map (PY) called.")
        if not self.editor_state.current_json_filename:
             if logger: logger.warning("Cannot Export PY: No JSON file path available (map likely not saved yet).")
             return False
        if editor_map_utils.export_map_to_game_python_script(self.editor_state): # type: ignore
            if logger: logger.info(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename or 'unknown.py')}.")
            return True
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export map for game (.py). Check logs.")
            return False

    @Slot()
    def save_map(self) -> bool:
        if logger: logger.info("Save Map (Unified JSON & PY) action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            map_name, ok = QInputDialog.getText(self, "Save Map As", "Enter map name (e.g., level_default):")
            if ok and map_name:
                clean_map_name = editor_map_utils.sanitize_map_name(map_name) # type: ignore
                if not clean_map_name:
                    QMessageBox.warning(self, "Invalid Name", "Map name is invalid or empty.")
                    return False
                
                map_folder_path_check = editor_map_utils.get_map_specific_folder_path(self.editor_state, clean_map_name) # type: ignore
                if map_folder_path_check and os.path.exists(map_folder_path_check): # type: ignore
                    reply = QMessageBox.question(self, "Map Exists",
                                                 f"A map folder named '{clean_map_name}' already exists. Overwrite its contents?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        self.show_status_message("Save cancelled: map name exists and not overwritten.")
                        return False
                
                editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, # type: ignore
                                                    self.editor_state.map_width_tiles,
                                                    self.editor_state.map_height_tiles,
                                                    preserve_objects=True)
                if not self._is_embedded:
                    self.update_window_title()
            else:
                self.show_status_message("Save cancelled: map name not provided.")
                return False
        
        map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function, ensure_exists=True) # type: ignore
        if not map_folder:
             QMessageBox.critical(self, "Error", f"Could not create map folder for '{self.editor_state.map_name_for_function}'. Save failed.")
             return False

        json_saved_ok = self._internal_save_map_json()
        py_exported_ok = False
        if json_saved_ok:
            py_exported_ok = self._internal_export_map_py()
        
        if json_saved_ok and py_exported_ok:
            self.editor_state.unsaved_changes = False
            if not self._is_embedded:
                self.update_window_title()
            self.update_edit_actions_enabled_state()
            self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' saved (JSON & PY).")
            return True
        elif json_saved_ok:
            self.editor_state.unsaved_changes = True
            self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' JSON saved, but PY export FAILED. Try saving again.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2) # type: ignore
            if not self._is_embedded:
                self.update_window_title()
            self.update_edit_actions_enabled_state()
            return False
        else:
            self.show_status_message("Save Map FAILED. Check logs.")
            return False

    @Slot()
    def rename_map(self):
        if logger: logger.info("Rename Map action triggered.")
        if not self.editor_state.current_json_filename or not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            QMessageBox.information(self, "Rename Map", "No map loaded or saved to rename.")
            return
        old_map_name = self.editor_state.map_name_for_function
        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"New name for map '{old_map_name}':", text=old_map_name)
        if ok and new_name_str:
            clean_new_name = editor_map_utils.sanitize_map_name(new_name_str) # type: ignore
            if not clean_new_name:
                QMessageBox.warning(self, "Invalid Name", "New map name is invalid.")
                return
            if clean_new_name == old_map_name:
                self.show_status_message("Rename cancelled: name unchanged.")
                return
            old_map_folder_path = editor_map_utils.get_map_specific_folder_path(self.editor_state, old_map_name) # type: ignore
            new_map_folder_path = editor_map_utils.get_map_specific_folder_path(self.editor_state, clean_new_name) # type: ignore
            if not old_map_folder_path or not new_map_folder_path: # type: ignore
                QMessageBox.critical(self, "Rename Error", "Could not determine folder paths for rename operation.")
                return
            if os.path.exists(new_map_folder_path): # type: ignore
                QMessageBox.warning(self, "Rename Error", f"A map folder named '{clean_new_name}' already exists.")
                return
            if not os.path.exists(old_map_folder_path): # type: ignore
                QMessageBox.warning(self, "Rename Error", f"Original map folder '{old_map_name}' not found. Cannot rename.")
                return
            try:
                if logger: logger.info(f"Attempting rename of map folder '{old_map_name}' to '{clean_new_name}'.")
                shutil.move(old_map_folder_path, new_map_folder_path) # type: ignore
                if logger: logger.info(f"Folder '{old_map_folder_path}' renamed to '{new_map_folder_path}'.")
                self.editor_state.map_name_for_function = clean_new_name
                editor_map_utils.init_new_map_state(self.editor_state, clean_new_name, self.editor_state.map_width_tiles, self.editor_state.map_height_tiles, preserve_objects=True) # type: ignore
                
                if not self.save_map():
                     QMessageBox.warning(self, "Rename Warning", "Folder renamed, but failed to save files with new name. Please try saving manually.")
                else:
                    self.show_status_message(f"Map renamed to '{clean_new_name}' and files updated.")
                
                if not self._is_embedded:
                    self.update_window_title()
                self.update_edit_actions_enabled_state()
                self.asset_palette_widget.populate_assets()
            except Exception as e_rename_map:
                if logger: logger.error(f"Error during map rename process: {e_rename_map}", exc_info=True)
                QMessageBox.critical(self, "Rename Error", f"An unexpected error occurred during map rename: {e_rename_map}")
        else:
            self.show_status_message("Rename map cancelled.")

    @Slot()
    def delete_map_folder(self):
        if logger: logger.info("Delete Map Folder action triggered.")
        if not self.editor_state.current_json_filename or not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
             QMessageBox.information(self, "Delete Map", "No map loaded or saved to delete.")
             return
        map_name_to_delete = self.editor_state.map_name_for_function
        reply = QMessageBox.warning(self, "Confirm Delete",
                                     f"Are you sure you want to delete the ENTIRE folder for map '{map_name_to_delete}' including all its contents (JSON, PY, Custom assets)?\nThis action CANNOT be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if editor_map_utils.delete_map_folder_and_contents(self.editor_state, map_name_to_delete): # type: ignore
                self.show_status_message(f"Map folder '{map_name_to_delete}' deleted.")
                if logger: logger.info(f"Deleted map '{map_name_to_delete}' was currently loaded. Resetting editor state.")
                self.editor_state.reset_map_context()
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.asset_palette_widget.populate_assets()
                self.properties_editor_widget.clear_display()
                if not self._is_embedded:
                    self.update_window_title()
                self.update_edit_actions_enabled_state()
            else:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete folder for map '{map_name_to_delete}'. Check logs.")
        else:
            self.show_status_message("Delete map folder cancelled.")
            
    @Slot()
    def upload_image_to_map(self):
        if logger: logger.info("Upload Image to Map action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            QMessageBox.warning(self, "Upload Error", "A map must be named and active to upload images to it.")
            return
        map_name = self.editor_state.map_name_for_function
        custom_asset_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, map_name, subfolder="Custom", ensure_exists=True) # type: ignore
        if not custom_asset_folder:
            QMessageBox.critical(self, "Upload Error", f"Could not create 'Custom' asset folder for map '{map_name}'.")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image to Upload to Map's Custom Assets", custom_asset_folder, "Images (*.png *.jpg *.jpeg *.gif)")
        
        if file_path:
            image_filename = os.path.basename(file_path)
            destination_image_path = os.path.join(custom_asset_folder, image_filename)
            try:
                if os.path.normpath(file_path) != os.path.normpath(destination_image_path):
                    if os.path.exists(destination_image_path):
                        reply = QMessageBox.question(self, "File Exists",
                                                     f"Image '{image_filename}' already exists in this map's Custom assets. Overwrite?",
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No:
                            self.show_status_message(f"Image '{image_filename}' not overwritten.")
                            return
                    shutil.copy2(file_path, destination_image_path)
                
                if logger: logger.info(f"Image '{file_path}' ensured at '{destination_image_path}'.")
                q_image = QImage(destination_image_path)
                if q_image.isNull():
                    QMessageBox.warning(self, "Image Error", f"Could not load uploaded image: {image_filename}")
                    return

                view_rect = self.map_view_widget.viewport().rect()
                center_scene_pos = self.map_view_widget.mapToScene(view_rect.center())
                
                # Default to full image size, no cropping initially
                img_original_width = q_image.width()
                img_original_height = q_image.height()

                new_image_obj_data = {
                    "asset_editor_key": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, # type: ignore
                    "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, # type: ignore
                    "world_x": int(center_scene_pos.x() - img_original_width / 2),
                    "world_y": int(center_scene_pos.y() - img_original_height / 2),
                    "source_file_path": f"Custom/{image_filename}",
                    "original_width": img_original_width,
                    "original_height": img_original_height,
                    "current_width": img_original_width,    # Initially, display full image
                    "current_height": img_original_height,  # Initially, display full image
                    "crop_rect": None,                      # No crop by default
                    "layer_order": 0,
                    "properties": ED_CONFIG.get_default_properties_for_asset(ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) # type: ignore
                }
                editor_history.push_undo_state(self.editor_state) # type: ignore
                self.editor_state.placed_objects.append(new_image_obj_data)
                self.map_view_widget.draw_placed_objects()
                self.handle_map_content_changed()
                
                if self.asset_palette_widget.category_filter_combo.currentText().lower() == "custom":
                    self.asset_palette_widget.populate_assets()
                self.show_status_message(f"Image '{image_filename}' uploaded and added to map.")
            except Exception as e_upload:
                if logger: logger.error(f"Error uploading image '{image_filename}': {e_upload}", exc_info=True)
                QMessageBox.critical(self, "Upload Error", f"Could not upload image: {e_upload}")
        else:
            self.show_status_message("Image upload cancelled.")

    @Slot(object, QPoint)
    def show_map_item_context_menu(self, map_object_data_ref: Dict[str, Any], global_pos: QPoint):
        if not map_object_data_ref:
            return
        asset_key = map_object_data_ref.get("asset_editor_key")
        # Context menu for layering applies to both custom images and triggers
        if asset_key not in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]: # type: ignore
            return
        context_menu = QMenu(self)
        actions_map = {"Bring to Front": "front", "Send to Back": "back", "Bring Forward": "forward", "Send Backward": "backward"}
        for text, direction_key in actions_map.items():
            action = context_menu.addAction(text)
            action.triggered.connect(lambda checked=False, d=direction_key, ref=map_object_data_ref: self.handle_map_item_layer_action(ref, d))
        context_menu.exec(global_pos)

    def handle_map_item_layer_action(self, map_object_data_ref: Dict[str, Any], direction: str):
        if not map_object_data_ref:
            return
        editor_history.push_undo_state(self.editor_state) # type: ignore
        all_z_orders = sorted(list(set(obj.get("layer_order", 0) for obj in self.editor_state.placed_objects)))
        current_z = map_object_data_ref.get("layer_order", 0)
        new_z = current_z
        if direction == "front":
            new_z = (all_z_orders[-1] + 1) if all_z_orders else 0
        elif direction == "back":
            new_z = (all_z_orders[0] - 1) if all_z_orders else 0
        elif direction == "forward":
            try:
                current_idx = all_z_orders.index(current_z)
                new_z = all_z_orders[min(len(all_z_orders) - 1, current_idx + 1)]
                if new_z == current_z and len(all_z_orders) > current_idx + 1:
                     new_z = all_z_orders[current_idx + 1]
                elif new_z == current_z: # If it's already the top or only one at this Z
                    new_z += 1 # Increment to ensure it's visibly "more forward"
            except ValueError: # Current Z not in existing distinct Z orders (e.g. newly added item)
                 new_z = (all_z_orders[-1] + 1) if all_z_orders else current_z + 1
        elif direction == "backward":
            try:
                current_idx = all_z_orders.index(current_z)
                new_z = all_z_orders[max(0, current_idx - 1)]
                if new_z == current_z and current_idx > 0:
                    new_z = all_z_orders[current_idx -1]
                elif new_z == current_z: # If it's already the bottom or only one at this Z
                    new_z -=1 # Decrement
            except ValueError:
                 new_z = (all_z_orders[0] -1) if all_z_orders else current_z -1
        
        map_object_data_ref["layer_order"] = new_z
        self.map_view_widget.draw_placed_objects() # Redraw to apply new Z order
        self.handle_map_content_changed() # Mark as unsaved
        self.show_status_message(f"Object layer order changed.")

    @Slot(dict)
    def handle_upload_image_for_trigger(self, trigger_object_data_ref: Dict[str, Any]):
        if logger: logger.info(f"Upload Image for Trigger action triggered for: {id(trigger_object_data_ref)}")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            QMessageBox.warning(self, "Upload Error", "A map must be named and active.")
            return
        map_name = self.editor_state.map_name_for_function
        custom_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, map_name, subfolder="Custom", ensure_exists=True) # type: ignore
        if not custom_folder:
            QMessageBox.critical(self, "Upload Error", f"Could not access/create 'Custom' folder for map '{map_name}'.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image for Trigger Square", custom_folder, "Images (*.png *.jpg *.jpeg *.gif)")
        if file_path:
            image_filename = os.path.basename(file_path)
            destination_image_path = os.path.join(custom_folder, image_filename)
            try:
                if os.path.normpath(file_path) != os.path.normpath(destination_image_path) :
                    if os.path.exists(destination_image_path):
                        reply = QMessageBox.question(self, "File Exists", f"Image '{image_filename}' already exists in Custom assets. Overwrite?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No:
                            self.show_status_message(f"Trigger image '{image_filename}' not overwritten.")
                            return
                    shutil.copy2(file_path, destination_image_path)
                
                relative_path = f"Custom/{image_filename}"
                editor_history.push_undo_state(self.editor_state) # type: ignore
                trigger_object_data_ref["properties"]["image_in_square"] = relative_path
                self.properties_editor_widget.update_property_field_value(trigger_object_data_ref, "image_in_square", relative_path)
                self.map_view_widget.update_specific_object_visuals(trigger_object_data_ref)
                self.handle_map_content_changed()
                self.show_status_message(f"Image '{image_filename}' set for trigger square.")
            except Exception as e_upload_trigger:
                if logger: logger.error(f"Error setting image for trigger '{image_filename}': {e_upload_trigger}", exc_info=True)
                QMessageBox.critical(self, "Upload Error", f"Could not set image for trigger: {e_upload_trigger}")

    @Slot()
    def export_map_as_image(self):
        if logger: logger.info("Export Map as Image action triggered.")
        if not self.editor_state.placed_objects and not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Export Error", "No map content to export as an image.")
            return
        default_map_name = self.editor_state.map_name_for_function if self.editor_state.map_name_for_function != "untitled_map" else "untitled_map_export"
        map_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function, ensure_exists=True) # type: ignore
        suggested_dir = map_folder if map_folder else os.path.join(_PROJECT_ROOT_DIR, "map_exports") # type: ignore
        if not map_folder and not os.path.exists(suggested_dir): # type: ignore
            try: os.makedirs(suggested_dir) # type: ignore
            except OSError as e: 
                if logger: logger.error(f"Could not create 'map_exports' dir: {e}")
                suggested_dir = editor_map_utils.get_maps_base_directory() # type: ignore
        
        suggested_path = os.path.join(suggested_dir, default_map_name + ".png") # type: ignore
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Map as Image", suggested_path, "PNG Images (*.png);;All Files (*)")
        if not file_path:
            self.show_status_message("Export map as image cancelled.")
            return
        try:
            scene = self.map_view_widget.scene()
            if not scene: QMessageBox.critical(self, "Export Error", "Cannot access map scene."); return
            target_rect = scene.itemsBoundingRect()
            if target_rect.isEmpty(): QMessageBox.information(self, "Export Error", "Map is empty."); return
            padding = 20
            target_rect.adjust(-padding, -padding, padding, padding)
            img_w, img_h = int(target_rect.width()), int(target_rect.height())
            if img_w <= 0 or img_h <= 0: QMessageBox.critical(self, "Export Error", f"Invalid image dims: {img_w}x{img_h}"); return
            image = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Keep false for pixel art style
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False) # Keep false
            bg_color = QColor(*self.editor_state.background_color)
            if bg_color.alpha() == 255: painter.fillRect(image.rect(), bg_color)
            scene.render(painter, QRectF(image.rect()), target_rect)
            painter.end()
            if image.save(file_path, "PNG"):
                self.show_status_message(f"Map exported as image: {os.path.basename(file_path)}")
            else:
                QMessageBox.critical(self, "Export Error", f"Failed to save image to:\n{file_path}")
        except Exception as e:
            if logger: logger.error(f"Error exporting map as image: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Unexpected error during image export:\n{e}")

    @Slot()
    def undo(self):
        if logger: logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state() # Reloads visuals based on restored state
            self.update_edit_actions_enabled_state()
            # Update properties panel if an item is selected after undo
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref) # type: ignore
            else:
                self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful.")
            if not self._is_embedded:
                self.update_window_title()
            self.asset_palette_widget.populate_assets() # In case custom assets changed
        else:
            self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self):
        if logger: logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state): # type: ignore
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref) # type: ignore
            else:
                self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful.")
            if not self._is_embedded:
                self.update_window_title()
            self.asset_palette_widget.populate_assets()
        else:
            self.show_status_message("Nothing to redo or redo failed.")

    @Slot()
    def toggle_grid(self):
        self.editor_state.show_grid = not self.editor_state.show_grid
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.map_view_widget.update_grid_visibility()
        self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")

    @Slot()
    def change_background_color(self):
        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")
        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color()
            self.handle_map_content_changed()
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else:
            self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self):
        QMessageBox.about(self, "About Platformer Level Editor", "Platformer Level Editor by Ahmad Cooper 2025\n\nCreate and edit levels for the platformer game.")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        active_panel: Optional[QWidget] = None
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
             active_panel = self._focusable_panels[self._current_focused_panel_index]
        
        if active_panel and hasattr(active_panel, 'handle_key_event_for_controller_nav') and active_panel.handle_key_event_for_controller_nav(event): # type: ignore
             event.accept()
             return

        # Pass to MapViewWidget first if it has focus, for its own key handling (like Shift+C)
        if self.map_view_widget.hasFocus() and hasattr(self.map_view_widget, 'keyPressEvent'):
             self.map_view_widget.keyPressEvent(event) # type: ignore
             if event.isAccepted():
                 return
        
        if key == Qt.Key.Key_Escape and not self._is_embedded:
            if logger: logger.info("Escape key pressed in standalone mode, attempting to close window.")
            self.close()
            event.accept()
        
        super().keyPressEvent(event)


    def closeEvent(self, eventQCloseEvent): # type: ignore
        if logger: logger.info(f"Close event triggered. Embedded: {self._is_embedded}")
        if self.confirm_unsaved_changes("exit the editor"):
            if self._controller_input_timer and self._controller_input_timer.isActive():
                self._controller_input_timer.stop()
                if logger: logger.info("Controller input timer stopped.")
            if _PYGAME_AVAILABLE and self._joysticks:
                for joy in self._joysticks:
                    if joy and joy.get_init():
                        joy.quit()
                if logger: logger.info("Pygame joysticks un-initialized.")
            self.save_geometry_and_state()
            eventQCloseEvent.accept()
        else:
            eventQCloseEvent.ignore()

    def save_geometry_and_state(self):
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName(): # type: ignore
            self.minimap_dock.setObjectName("MinimapDock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        if logger: logger.debug("Window geometry and dock state explicitly saved.")

    def restore_geometry_and_state(self) -> bool:
        geom = self.settings.value("geometry")
        state = self.settings.value("windowState")
        restored_geom = False
        restored_state = False
        try:
            if geom is not None:
                self.restoreGeometry(geom) # type: ignore
                restored_geom = True
            if state is not None:
                self.restoreState(state) # type: ignore
                restored_state = True
            if logger: logger.debug(f"Window geometry restored: {restored_geom}, state restored: {restored_state}.")
            return restored_geom or restored_state
        except Exception as e_restore:
            if logger: logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting.", exc_info=True)
            if not self._is_embedded:
                 primary_screen = QGuiApplication.primaryScreen()
                 if primary_screen:
                     screen_geo = primary_screen.availableGeometry()
                     default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH # type: ignore
                     default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT # type: ignore
                     self.setGeometry(screen_geo.x() + (screen_geo.width() - default_w) // 2,
                                      screen_geo.y() + (screen_geo.height() - default_h) // 2,
                                      default_w, default_h)
                 else:
                     self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT) # type: ignore
            return False


def editor_main(parent_app_instance: Optional[QApplication] = None, embed_mode: bool = False):
    if _IS_STANDALONE_EXECUTION:
        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__))) if '__file__' in globals() else os.chdir(os.getcwd())
            if logger: logger.info(f"Standalone mode: CWD set to: {os.getcwd()}")
        except Exception as e_chdir:
            if logger: logger.error(f"Could not change CWD in standalone mode: {e_chdir}")

    if logger: logger.info(f"editor_main() called. Embed mode: {embed_mode}, Standalone context: {_IS_STANDALONE_EXECUTION}")
    app = QApplication.instance()
    if app is None:
        if parent_app_instance:
            app = parent_app_instance
        elif _IS_STANDALONE_EXECUTION:
            app = QApplication(sys.argv)
        else:
            raise RuntimeError("Editor needs a QApplication instance, especially in embed_mode.")

    main_window = EditorMainWindow(embed_mode=embed_mode)

    if not embed_mode:
        exit_code = 0
        try:
            exit_code = app.exec() # type: ignore
        except Exception as e_main_loop:
            if logger: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
            exit_code = 1
        finally:
            if hasattr(main_window, 'isVisible') and main_window.isVisible():
                main_window.save_geometry_and_state()
            if logger: logger.info("Editor session (standalone) ended.")
        if _PYGAME_AVAILABLE and pygame.get_init():
            pygame.quit()
            if logger: logger.info("Pygame quit globally at end of editor_main (standalone).")
        return exit_code
    else:
        if logger: logger.info("EditorMainWindow instance created for embedding. Returning instance to caller.")
        return main_window

if __name__ == "__main__":
    print("--- editor.py execution started as __main__ (standalone) ---")
    if _PYGAME_AVAILABLE:
        if not pygame.get_init():
            try:
                pygame.init()
                print("INFO: Pygame initialized for standalone __main__ execution.")
                if not pygame.joystick.get_init():
                    pygame.joystick.init()
                    print("INFO: Pygame joystick module initialized.")
                else:
                    print("INFO: Pygame joystick module already initialized.")
            except Exception as e_pygame_main_init:
                print(f"WARNING: Pygame init or joystick init failed in __main__: {e_pygame_main_init}")
        else:
            print("INFO: Pygame already initialized.")
            if pygame.joystick and not pygame.joystick.get_init(): # type: ignore
                 try:
                     pygame.joystick.init()
                     print("INFO: Pygame joystick module initialized (Pygame was already init).")
                 except Exception as e_pygame_joystick_init:
                     print(f"WARNING: Pygame joystick init failed (Pygame was already init): {e_pygame_joystick_init}")
    return_code_standalone = editor_main(embed_mode=False)
    print(f"--- editor.py standalone execution finished (exit code: {return_code_standalone}) ---")
    sys.exit(return_code_standalone)

#################### END OF FILE: editor.py ####################