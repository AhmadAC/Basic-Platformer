#################### START OF FILE: editor_main_window.py ####################

# editor/editor_main_window.py (renamed from editor.py)
# -*- coding: utf-8 -*-
"""
Main Window for the Platformer Level Editor (PySide6 Version).
Orchestrates UI components and top-level editor actions.
"""
import sys
import os
import logging
import traceback
import time
# shutil import removed as it's now in editor_file_operations
from typing import Optional, Tuple, List, Any, Dict

_IS_STANDALONE_EXECUTION = (__name__ == "__main__") # This check might need adjustment if not run directly
_EDITOR_MODULE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
_PROJECT_ROOT_DIR = os.path.dirname(_EDITOR_MODULE_DIR)

if _IS_STANDALONE_EXECUTION:
    print(f"INFO: editor_main_window.py running in standalone mode from: {_EDITOR_MODULE_DIR}")
    if _PROJECT_ROOT_DIR not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT_DIR)
        print(f"INFO: Added project root '{_PROJECT_ROOT_DIR}' to sys.path for standalone execution.")
else:
    print(f"INFO: editor_main_window.py running as a module (package: {__package__})")


from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, # QFileDialog removed
    QColorDialog, # QInputDialog removed (now in file_ops)
    QLabel, QSizePolicy, QMenu, QGraphicsScene
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
    from .asset_palette_widget import AssetPaletteWidget # Updated import
    from .properties_editor_widget import PropertiesEditorDockWidget # Updated import
    from .editor_selection_pane import SelectionPaneWidget 
    from .editor_actions import *
    from . import editor_file_operations as EFO # NEW IMPORT

    if ED_CONFIG.MINIMAP_ENABLED: 
        from .minimap_widget import MinimapWidget
    if _PYGAME_AVAILABLE:
        from config import init_pygame_and_joystick_globally, get_joystick_objects
    _IMPORTS_SUCCESSFUL_METHOD = "Relative"
    logger_init_pygame.info("Editor modules imported successfully using RELATIVE paths.")
except ImportError as e_relative_import:
    logger_init_pygame.warning(f"Relative import failed: {e_relative_import}. Attempting absolute imports.")
    try:
        from editor import editor_config as ED_CONFIG 
        from editor.editor_state import EditorState 
        from editor import editor_assets 
        from editor import editor_map_utils 
        from editor import editor_history 
        from editor.map_view_widget import MapViewWidget 
        from editor.asset_palette_widget import AssetPaletteWidget # Updated import
        from editor.properties_editor_widget import PropertiesEditorDockWidget # Updated import
        from editor.editor_selection_pane import SelectionPaneWidget 
        from editor.editor_actions import * 
        from editor import editor_file_operations as EFO # NEW IMPORT

        if ED_CONFIG.MINIMAP_ENABLED: 
            from editor.minimap_widget import MinimapWidget 
        if _PYGAME_AVAILABLE:
            from config import init_pygame_and_joystick_globally, get_joystick_objects 
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (from editor.*)"
        logger_init_pygame.info("Editor modules imported successfully using ABSOLUTE paths (from editor.*).")
    except ImportError as e_absolute_import:
        logger_init_pygame.critical(f"CRITICAL: Both relative and absolute imports for editor modules failed: {e_absolute_import}")
        raise ImportError(f"Failed to import critical editor modules. Relative: {e_relative_import}. Absolute: {e_absolute_import}") from e_absolute_import

logger: Optional[logging.Logger] = None
log_file_path_for_error_msg = "editor_qt_debug.log" # Default
try:
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_file_name = getattr(ED_CONFIG, "LOG_FILE_NAME", "editor_qt_debug.log")
    log_file_path_for_error_msg = os.path.join(logs_dir, log_file_name)
    numeric_log_level = getattr(logging, getattr(ED_CONFIG, "LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)
    log_format_str = getattr(ED_CONFIG, "LOG_FORMAT", '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s')
    
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
        
    logging.basicConfig(
        level=numeric_log_level,
        format=log_format_str,
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w', encoding='utf-8')]
    )
    logger = logging.getLogger("EditorMainWindowLogger") # Unique name for this logger
    logger.info(f"Editor session started. Logging initialized. Imports via: {_IMPORTS_SUCCESSFUL_METHOD}")

except Exception as e_log_setup: # Fallback if logging setup fails
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE FALLBACK (editor.py logger setup): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("EditorMainWindowLogger_Fallback") # Fallback logger
    logger.error(f"CRITICAL ERROR DURING FILE LOGGING SETUP (editor.py): {e_log_setup}. Using console.", exc_info=True)


SWITCH_A_BTN = 0; SWITCH_B_BTN = 1; SWITCH_X_BTN = 2; SWITCH_Y_BTN = 3
SWITCH_L_BTN = 4; SWITCH_R_BTN = 5; SWITCH_ZL_BTN = 6; SWITCH_ZR_BTN = 7
SWITCH_MINUS_BTN = 8; SWITCH_PLUS_BTN = 9; SWITCH_L_STICK_BTN = 10; SWITCH_R_STICK_BTN = 11
SWITCH_L_STICK_X_AXIS = 0; SWITCH_L_STICK_Y_AXIS = 1; SWITCH_R_STICK_X_AXIS = 2; SWITCH_R_STICK_Y_AXIS = 3
SWITCH_ZL_AXIS = 4; SWITCH_ZR_AXIS = 5; SWITCH_DPAD_HAT_ID = 0

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
        self.selection_pane_dock.setObjectName("SelectionPaneDock") 
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock:
            self.minimap_dock.setObjectName("MinimapDock")

        editor_assets.load_editor_palette_assets(self.editor_state, self)
        self.asset_palette_widget.populate_assets()
        self.selection_pane_widget.populate_items() 

        if not self._is_embedded:
            self.update_window_title()
        self.update_edit_actions_enabled_state() 

        self._current_focused_panel_index: int = 0
        self._controller_input_timer: Optional[QTimer] = None
        self._joysticks: List[pygame.joystick.Joystick] = []
        self._primary_joystick: Optional[pygame.joystick.Joystick] = None
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
            else: # Default sizing and positioning if restore fails or no settings
                primary_screen = QGuiApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH
                    default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
                    pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                    pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                    self.showMaximized() # Or self.show() if maximized is not desired
                else: # Fallback if no primary screen info
                    self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)
                    self.showMaximized()
        else: # Embedded mode
            if logger: logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            # Still try to restore dock/splitter states for consistency if part of a larger app
            self.restore_geometry_and_state() 

        if not editor_map_utils.ensure_maps_directory_exists():
            err_msg_maps_dir = f"Base maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}"
            if not self._is_embedded:
                QMessageBox.critical(self, "Error", err_msg_maps_dir)
            elif logger:
                logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox)")
        
        if logger: logger.info("EditorMainWindow initialized.")
        if hasattr(self, 'status_bar') and self.status_bar: # Check if status_bar was created
            self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)

        # Set initial focus
        if self._focusable_panels and _PYGAME_AVAILABLE and self._primary_joystick:
            self._set_panel_controller_focus(0) # Default to first panel if controller is active
        elif self._focusable_panels:
            self._focusable_panels[0].setFocus(Qt.FocusReason.OtherFocusReason)


    def init_ui(self):
        if logger: logger.debug("Initializing UI components...")
        self._focusable_panels: List[QWidget] = []
        
        self.map_view_widget = MapViewWidget(self.editor_state, self)
        self.setCentralWidget(self.map_view_widget)
        self._focusable_panels.append(self.map_view_widget)
        self.map_view_widget.map_scene.selectionChanged.connect(self.update_delete_selection_action_enabled_state)

        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self)
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(max(200, ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50))
        self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 100)
        self._focusable_panels.append(self.asset_palette_widget)

        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self)
        self.properties_editor_dock.setWidget(self.properties_editor_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_editor_dock)
        self.properties_editor_dock.setMinimumWidth(280)
        self._focusable_panels.append(self.properties_editor_widget)

        self.selection_pane_dock = QDockWidget("Selection Pane", self)
        self.selection_pane_widget = SelectionPaneWidget(self.editor_state, self)
        self.selection_pane_dock.setWidget(self.selection_pane_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.selection_pane_dock)
        self._focusable_panels.append(self.selection_pane_widget) 

        self.tabifyDockWidget(self.properties_editor_dock, self.selection_pane_dock)
        self.properties_editor_dock.raise_() 

        if ED_CONFIG.MINIMAP_ENABLED:
            self.minimap_dock = QDockWidget("Minimap", self)
            self.minimap_widget = MinimapWidget(self.editor_state, self.map_view_widget, self)
            self.minimap_dock.setWidget(self.minimap_widget)
            if self.properties_editor_dock.parentWidget() == self: # Ensure it's a top-level dock
                 self.splitDockWidget(self.properties_editor_dock, self.minimap_dock, Qt.Orientation.Vertical)
            self.minimap_dock.setFixedHeight(ED_CONFIG.MINIMAP_DEFAULT_HEIGHT + 35) # Account for title bar
        else:
            self.minimap_dock = None 
            self.minimap_widget = None

        # --- Signal Connections ---
        self.asset_palette_widget.asset_selected_for_placement.connect(self.map_view_widget.on_asset_selected_for_placement)
        self.asset_palette_widget.asset_info_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)
        self.asset_palette_widget.paint_color_changed_for_status.connect(self.show_status_message)
        self.asset_palette_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)

        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)
        self.map_view_widget.map_content_changed.connect(self.selection_pane_widget.populate_items) 
        self.map_view_widget.map_scene.selectionChanged.connect(self.selection_pane_widget.sync_selection_from_map) 
        self.map_view_widget.context_menu_requested_for_item.connect(self.show_map_item_context_menu)

        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed) # For undo and title update
        self.properties_editor_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)
        self.properties_editor_widget.upload_image_for_trigger_requested.connect(self.handle_upload_image_for_trigger_dialog) # Changed

        self.selection_pane_widget.select_map_object_via_pane_requested.connect(self._handle_select_map_object_from_pane) 
        self.selection_pane_widget.item_visibility_toggled_in_pane.connect(self._toggle_item_visibility)
        self.selection_pane_widget.item_lock_toggled_in_pane.connect(self._toggle_item_lock)


        if self.minimap_widget:
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs)
        if logger: logger.debug("UI components initialized.")

    @Slot(object)
    def _handle_select_map_object_from_pane(self, obj_data_ref: Dict[str, Any]):
        if logger: logger.debug(f"MainWin: Request to select object from pane: ID {id(obj_data_ref)}")
        
        item_to_select = self.map_view_widget._map_object_items.get(id(obj_data_ref))
        
        if not item_to_select:
            logger.warning(f"MainWin: Could not find QGraphicsItem by direct ID {id(obj_data_ref)}. Attempting content reference lookup.")
            for item_id_scan, scene_item_scan in self.map_view_widget._map_object_items.items():
                if hasattr(scene_item_scan, 'map_object_data_ref') and scene_item_scan.map_object_data_ref is obj_data_ref:
                    item_to_select = scene_item_scan
                    logger.info(f"MainWin: Found item by content reference for ID {id(obj_data_ref)}.")
                    break
        
        if item_to_select:
            self.map_view_widget.map_scene.blockSignals(True)
            self.map_view_widget.map_scene.clearSelection() 
            item_to_select.setSelected(True)
            self.map_view_widget.map_scene.blockSignals(False)
            
            self.map_view_widget.on_scene_selection_changed() 

            item_to_select.setVisible(not obj_data_ref.get("editor_hidden", False)) 
            self.map_view_widget.ensureVisible(item_to_select, 50, 50)
            self.map_view_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            logger.info(f"MainWin: Selected item '{type(item_to_select).__name__}' from pane. Data ID: {id(obj_data_ref)}")
        else:
            logger.warning(f"MainWin: Could not find QGraphicsItem for object data ID {id(obj_data_ref)} to select from pane (even after content check).")
            self.map_view_widget.map_scene.clearSelection() 
            self.properties_editor_widget.clear_display() 


    @Slot(object, bool)
    def _toggle_item_visibility(self, obj_data_ref: Dict[str, Any], new_visible_state: bool):
        if logger: logger.debug(f"MainWin: Toggle visibility for obj ID {id(obj_data_ref)} to {new_visible_state}")
        if obj_data_ref:
            editor_history.push_undo_state(self.editor_state)
            obj_data_ref["editor_hidden"] = not new_visible_state 
            self.map_view_widget.update_specific_object_visuals(obj_data_ref)
            self.handle_map_content_changed() 

    @Slot(object, bool)
    def _toggle_item_lock(self, obj_data_ref: Dict[str, Any], new_lock_state: bool):
        if logger: logger.debug(f"MainWin: Toggle lock for obj ID {id(obj_data_ref)} to {new_lock_state}")
        if obj_data_ref:
            editor_history.push_undo_state(self.editor_state)
            obj_data_ref["editor_locked"] = new_lock_state
            self.map_view_widget.update_specific_object_visuals(obj_data_ref) 
            self.handle_map_content_changed() 

    # --- Controller related methods remain in EditorMainWindow ---
    # _init_controller_system, _poll_controller_input, _dispatch_controller_action_to_panel,
    # _set_panel_controller_focus, _cycle_panel_focus_next, _cycle_panel_focus_prev

    def _init_controller_system(self): # ... (implementation as before)
        if logger: logger.info("Initializing controller system...")
        try:
            init_pygame_and_joystick_globally(force_rescan=True) 
            self._joysticks = get_joystick_objects() 
            if not self._joysticks or all(joy is None for joy in self._joysticks):
                self._primary_joystick = None
                if logger: logger.info("No joysticks detected.")
                return
            for i, joy in enumerate(self._joysticks): 
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
            self._controller_input_timer.setInterval(getattr(ED_CONFIG, "CONTROLLER_POLL_INTERVAL_MS", 16))
            self._controller_input_timer.timeout.connect(self._poll_controller_input)
            self._controller_input_timer.start()
            if logger: logger.info("Controller input polling started.")
        except Exception as e:
            if logger: logger.error(f"Error initializing controller system: {e}", exc_info=True)
            self._primary_joystick = None
            
    def _poll_controller_input(self): # ... (implementation as before)
        if not _PYGAME_AVAILABLE or not self._primary_joystick:
            return
        pygame.event.pump()
        current_time = time.monotonic()
        joy = self._primary_joystick
        if not joy.get_init():
            try: joy.init()
            except pygame.error: return
        
        button_map = {
            SWITCH_B_BTN: ACTION_UI_ACCEPT, SWITCH_A_BTN: ACTION_UI_CANCEL,
            SWITCH_Y_BTN: ACTION_MAP_TOOL_PRIMARY, SWITCH_X_BTN: ACTION_MAP_TOOL_SECONDARY,
            SWITCH_L_BTN: ACTION_UI_TAB_PREV, SWITCH_R_BTN: ACTION_UI_TAB_NEXT,
            SWITCH_ZL_BTN: ACTION_MAP_ZOOM_OUT, SWITCH_ZR_BTN: ACTION_MAP_ZOOM_IN,
            SWITCH_PLUS_BTN: ACTION_UI_MENU, SWITCH_MINUS_BTN: ACTION_UI_FOCUS_NEXT
        }
        for btn_id, action in button_map.items():
            if btn_id >= joy.get_numbuttons(): continue
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

        axis_map = {
            SWITCH_L_STICK_X_AXIS: (ACTION_UI_LEFT, ACTION_UI_RIGHT),
            SWITCH_L_STICK_Y_AXIS: (ACTION_UI_UP, ACTION_UI_DOWN)
        }
        for axis_id, (neg_action, pos_action) in axis_map.items():
            if axis_id >= joy.get_numaxes(): continue
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
                elif (current_time - last_event_time_for_key_dir > self._controller_axis_repeat_interval and
                      self._controller_axis_last_event_time.get(key, 0) != 0) :
                         can_emit = True

                if can_emit:
                    self.controller_action_dispatched.emit(action_to_emit, axis_val)
                    self._controller_axis_last_event_time[key] = current_time
            else: 
                # Reset timers for both directions of this axis when it returns to neutral
                key_neg = (joy.get_id(), axis_id, -1)
                key_pos = (joy.get_id(), axis_id, 1)
                if key_neg in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_neg] = 0 
                if key_pos in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_pos] = 0

    @Slot(str, object)
    def _dispatch_controller_action_to_panel(self, action: str, value: Any): # ... (implementation as before)
        if logger: logger.debug(f"Controller action received: {action}, Value: {value}")
        if action == ACTION_UI_FOCUS_NEXT: self._cycle_panel_focus_next(); return
        elif action == ACTION_UI_FOCUS_PREV: self._cycle_panel_focus_prev(); return
        elif action == ACTION_UI_MENU:
            if self.menu_bar and self.menu_bar.actions():
                first_menu = self.menu_bar.actions()[0].menu()
                if first_menu:
                    first_menu.popup(self.mapToGlobal(self.menu_bar.pos() + QPoint(0, self.menu_bar.height())))
            return
        
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
            focused_widget = self._focusable_panels[self._current_focused_panel_index]
            if hasattr(focused_widget, "handle_controller_action"):
                try: focused_widget.handle_controller_action(action, value)
                except Exception as e:
                    if logger: logger.error(f"Error in {type(focused_widget).__name__}.handle_controller_action: {e}", exc_info=True)
            elif logger: logger.warning(f"Focused panel {type(focused_widget).__name__} has no handle_controller_action.")
        elif logger: logger.warning(f"No panel focused or index out of bounds: {self._current_focused_panel_index}")

    def _set_panel_controller_focus(self, new_index: int): # ... (implementation as before)
        if not self._focusable_panels or not (0 <= new_index < len(self._focusable_panels)):
            if logger: logger.warning(f"Attempt to set focus to invalid index {new_index}")
            return
        
        old_index = self._current_focused_panel_index
        if 0 <= old_index < len(self._focusable_panels) and old_index != new_index :
            old_panel = self._focusable_panels[old_index]
            if hasattr(old_panel, "on_controller_focus_lost"):
                try: old_panel.on_controller_focus_lost()
                except Exception as e:
                    if logger: logger.error(f"Error in {type(old_panel).__name__}.on_controller_focus_lost: {e}", exc_info=True)
            parent_dock_old = old_panel.parent()
            while parent_dock_old and not isinstance(parent_dock_old, QDockWidget):
                parent_dock_old = parent_dock_old.parent()
            if isinstance(parent_dock_old, QDockWidget): parent_dock_old.setStyleSheet("")
                
        self._current_focused_panel_index = new_index
        new_panel = self._focusable_panels[new_index]
        new_panel.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(new_panel, "on_controller_focus_gained"):
            try: new_panel.on_controller_focus_gained()
            except Exception as e:
                if logger: logger.error(f"Error in {type(new_panel).__name__}.on_controller_focus_gained: {e}", exc_info=True)

        panel_name_for_status = type(new_panel).__name__
        parent_dock_new = new_panel.parent()
        while parent_dock_new and not isinstance(parent_dock_new, QDockWidget):
            parent_dock_new = parent_dock_new.parent()
        if isinstance(parent_dock_new, QDockWidget):
            panel_name_for_status = parent_dock_new.windowTitle()
            focus_border_color = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER.split(' ')[-1] if ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER else 'lightblue'
            parent_dock_new.setStyleSheet(f"QDockWidget::title {{ background-color: {focus_border_color}; color: black; border: 1px solid black; padding: 2px; }}")
        elif isinstance(new_panel, MapViewWidget):
            panel_name_for_status = "Map View"
        self.show_status_message(f"Controller Focus: {panel_name_for_status}", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        if logger: logger.info(f"Controller focus set to: {panel_name_for_status} (Index: {new_index})")

    def _cycle_panel_focus_next(self): # ... (implementation as before)
        if not self._focusable_panels: return
        new_index = (self._current_focused_panel_index + 1) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def _cycle_panel_focus_prev(self): # ... (implementation as before)
        if not self._focusable_panels: return
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

    def create_menus(self): # ... (implementation as before)
        if logger: logger.debug("Creating menus...")
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("&File")
        file_menu.addAction(self.new_map_action); file_menu.addAction(self.load_map_action)
        file_menu.addAction(self.rename_map_action); file_menu.addAction(self.delete_map_folder_action)
        file_menu.addSeparator(); file_menu.addAction(self.save_map_action); file_menu.addSeparator()
        file_menu.addAction(self.export_map_as_image_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        
        edit_menu = self.menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action); edit_menu.addAction(self.redo_action); edit_menu.addSeparator()
        edit_menu.addAction(self.delete_selection_action); edit_menu.addSeparator()
        edit_menu.addAction(self.change_bg_color_action); edit_menu.addSeparator()
        edit_menu.addAction(self.upload_image_action)
        
        view_menu = self.menu_bar.addMenu("&View")
        view_menu.addAction(self.toggle_grid_action); view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_action); view_menu.addAction(self.zoom_out_action); view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(self.asset_palette_dock.toggleViewAction())
        view_menu.addAction(self.properties_editor_dock.toggleViewAction())
        view_menu.addAction(self.selection_pane_dock.toggleViewAction())
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock:
            view_menu.addAction(self.minimap_dock.toggleViewAction())
        
        help_menu = self.menu_bar.addMenu("&Help")
        help_menu.addAction(QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog))
        if logger: logger.debug("Menus created.")

    def create_status_bar(self): # ... (implementation as before)
        if logger: logger.debug("Creating status bar...")
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250) # Ensure it has enough space
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        if logger: logger.debug("Status bar created.")

    @Slot(str, int)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT): # ... (as before)
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage(message, timeout)
        if logger: logger.info(f"Status: {message}")

    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple): # ... (as before)
        world_x, world_y, tile_x, tile_y, zoom_val = coords
        self.map_coords_label.setText(f" Map:({int(world_x)},{int(world_y)}) Tile:({tile_x},{tile_y}) Zoom:{zoom_val:.2f}x ")

    @Slot()
    def handle_map_content_changed(self): # ... (as before)
        if logger and not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes: False -> True.")
        self.editor_state.unsaved_changes = True
        if not self._is_embedded: self.update_window_title()
        self.update_edit_actions_enabled_state()
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_widget') and self.minimap_widget:
            if logger: logger.debug("Notifying minimap to redraw content due to map change.")
            self.minimap_widget.schedule_map_content_redraw()
        self.selection_pane_widget.populate_items() # Ensure selection pane updates on any content change
        if logger: logger.debug(f"handle_map_content_changed done. Unsaved: {self.editor_state.unsaved_changes}")

    def update_window_title(self): # ... (as before)
        if self._is_embedded: return
        title = "Platformer Level Editor"
        map_name = self.editor_state.map_name_for_function
        if map_name and map_name != "untitled_map": title += f" - {map_name}"
        if self.editor_state.unsaved_changes: title += "*"
        self.setWindowTitle(title)

    @Slot()
    def update_delete_selection_action_enabled_state(self): # ... (as before)
        can_delete = False
        if hasattr(self, 'map_view_widget') and hasattr(self.map_view_widget, 'map_scene'):
            can_delete = bool(self.map_view_widget.map_scene.selectedItems())
        if hasattr(self, 'delete_selection_action'): 
            self.delete_selection_action.setEnabled(can_delete)

    def update_edit_actions_enabled_state(self): # ... (as before)
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
        self.update_delete_selection_action_enabled_state()

    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool: # ... (as before)
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes", f"Unsaved changes. Save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save: return self.save_map()
            elif reply == QMessageBox.StandardButton.Cancel: return False
        return True

    # --- File Operations Delegated ---
    @Slot()
    def new_map(self): EFO.new_map_action(self)
    @Slot()
    def load_map(self): EFO.load_map_action(self)
    @Slot()
    def save_map(self) -> bool: return EFO.save_map_action(self)
    @Slot()
    def rename_map(self): EFO.rename_map_action(self)
    @Slot()
    def delete_map_folder(self): EFO.delete_map_folder_action(self)
    @Slot()
    def export_map_as_image(self): EFO.export_map_as_image_action(self)
    @Slot()
    def upload_image_to_map(self): EFO.upload_image_to_map_action(self)
    @Slot(dict) # Renamed to clarify it's the dialog handler
    def handle_upload_image_for_trigger_dialog(self, trigger_object_data_ref: Dict[str, Any]):
        EFO.handle_upload_image_for_trigger_dialog(self, trigger_object_data_ref)
    # --- End File Operations ---

    @Slot(object, QPoint)
    def show_map_item_context_menu(self, map_object_data_ref: Dict[str, Any], global_pos: QPoint): # ... (as before)
        if not map_object_data_ref: return
        asset_key = map_object_data_ref.get("asset_editor_key")
        if asset_key not in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]: return
        
        context_menu = QMenu(self)
        actions_map = {"Bring to Front": "front", "Send to Back": "back", 
                       "Bring Forward": "forward", "Send Backward": "backward"}
        for text, direction_key in actions_map.items():
            action = context_menu.addAction(text)
            action.triggered.connect(lambda checked=False, d=direction_key, ref=map_object_data_ref: 
                                     self.handle_map_item_layer_action(ref, d))
        context_menu.exec(global_pos)

    def handle_map_item_layer_action(self, map_object_data_ref: Dict[str, Any], direction: str): # ... (as before)
        if not map_object_data_ref: return
        editor_history.push_undo_state(self.editor_state)
        all_z_orders = sorted(list(set(obj.get("layer_order", 0) for obj in self.editor_state.placed_objects)))
        current_z = map_object_data_ref.get("layer_order", 0); new_z = current_z
        
        if direction == "front": new_z = (all_z_orders[-1] + 1) if all_z_orders else 0
        elif direction == "back": new_z = (all_z_orders[0] - 1) if all_z_orders else 0
        elif direction == "forward":
            try:
                current_idx = all_z_orders.index(current_z); new_z = all_z_orders[min(len(all_z_orders) - 1, current_idx + 1)]
                if new_z == current_z and len(all_z_orders) > current_idx + 1: new_z = all_z_orders[current_idx + 1]
                elif new_z == current_z: new_z += 1
            except ValueError: new_z = (all_z_orders[-1] + 1) if all_z_orders else current_z + 1
        elif direction == "backward":
            try:
                current_idx = all_z_orders.index(current_z); new_z = all_z_orders[max(0, current_idx - 1)]
                if new_z == current_z and current_idx > 0: new_z = all_z_orders[current_idx -1]
                elif new_z == current_z: new_z -=1
            except ValueError: new_z = (all_z_orders[0] -1) if all_z_orders else current_z -1
        
        map_object_data_ref["layer_order"] = new_z
        self.map_view_widget.draw_placed_objects(); self.handle_map_content_changed()
        self.show_status_message(f"Object layer order changed.")

    @Slot()
    def undo(self): # ... (as before)
        if logger: logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful.")
            if not self._is_embedded: self.update_window_title()
            self.asset_palette_widget.populate_assets(); self.selection_pane_widget.populate_items()
        else: self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self): # ... (as before)
        if logger: logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful.")
            if not self._is_embedded: self.update_window_title()
            self.asset_palette_widget.populate_assets(); self.selection_pane_widget.populate_items()
        else: self.show_status_message("Nothing to redo or redo failed.")

    @Slot()
    def toggle_grid(self): # ... (as before)
        self.editor_state.show_grid = not self.editor_state.show_grid
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.map_view_widget.update_grid_visibility()
        self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")

    @Slot()
    def change_background_color(self): # ... (as before)
        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")
        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color()
            self.handle_map_content_changed() # BG color change is an unsaved change
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else: self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self): # ... (as before)
        QMessageBox.about(self, "About Platformer Level Editor", 
                          "Platformer Level Editor by Ahmad Cooper 2025\n\nCreate and edit levels for the platformer game.")

    def keyPressEvent(self, event: QKeyEvent): # ... (as before)
        key = event.key(); modifiers = event.modifiers()
        active_panel: Optional[QWidget] = None
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
             active_panel = self._focusable_panels[self._current_focused_panel_index]
        
        if active_panel and hasattr(active_panel, 'handle_key_event_for_controller_nav') and active_panel.handle_key_event_for_controller_nav(event):
             event.accept(); return
        if self.map_view_widget.hasFocus() and hasattr(self.map_view_widget, 'keyPressEvent'):
             self.map_view_widget.keyPressEvent(event)
             if event.isAccepted(): return
        if key == Qt.Key.Key_Escape and not self._is_embedded:
            if logger: logger.info("Escape key pressed in standalone mode, attempting to close window.")
            self.close(); event.accept(); return
        super().keyPressEvent(event)

    def closeEvent(self, eventQCloseEvent): # ... (as before)
        if logger: logger.info(f"Close event triggered. Embedded: {self._is_embedded}")
        if self.confirm_unsaved_changes("exit the editor"):
            if self._controller_input_timer and self._controller_input_timer.isActive():
                self._controller_input_timer.stop()
                if logger: logger.info("Controller input timer stopped.")
            if _PYGAME_AVAILABLE and self._joysticks:
                for joy in self._joysticks:
                    if joy and joy.get_init(): joy.quit()
                if logger: logger.info("Pygame joysticks un-initialized.")
            self.save_geometry_and_state()
            eventQCloseEvent.accept()
        else: eventQCloseEvent.ignore()

    def save_geometry_and_state(self): # ... (as before)
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if not self.selection_pane_dock.objectName(): self.selection_pane_dock.setObjectName("SelectionPaneDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName():
            self.minimap_dock.setObjectName("MinimapDock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        if logger: logger.debug("Window geometry and dock state explicitly saved.")

    def restore_geometry_and_state(self) -> bool: # ... (as before)
        geom = self.settings.value("geometry"); state = self.settings.value("windowState")
        restored_geom = False; restored_state = False
        try:
            if geom is not None: self.restoreGeometry(geom); restored_geom = True
            if state is not None: self.restoreState(state); restored_state = True
            if logger: logger.debug(f"Window geometry restored: {restored_geom}, state restored: {restored_state}.")
            return restored_geom or restored_state
        except Exception as e_restore:
            if logger: logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting.", exc_info=True)
            if not self._is_embedded:
                 primary_screen = QGuiApplication.primaryScreen()
                 if primary_screen:
                     screen_geo = primary_screen.availableGeometry()
                     default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH; default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
                     self.setGeometry(screen_geo.x() + (screen_geo.width() - default_w) // 2,
                                      screen_geo.y() + (screen_geo.height() - default_h) // 2,
                                      default_w, default_h)
                 else: self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)
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
        elif _IS_STANDALONE_EXECUTION: # Only create a new QApplication if truly standalone and none exists
            app = QApplication(sys.argv)
        else: # In an embedded scenario where no app is passed, this is an issue
            raise RuntimeError("Editor needs a QApplication instance, especially in embed_mode if not run as __main__.")

    main_window = EditorMainWindow(embed_mode=embed_mode)

    if not embed_mode: # Standalone execution with its own event loop
        exit_code = 0
        try:
            exit_code = app.exec()
        except Exception as e_main_loop:
            if logger: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
            exit_code = 1 # Indicate error
        finally:
            # Ensure state is saved if window was visible
            if hasattr(main_window, 'isVisible') and main_window.isVisible():
                main_window.save_geometry_and_state()
            if logger: logger.info("Editor session (standalone) ended.")
        # Clean up Pygame only if it was initialized by this standalone run
        if _PYGAME_AVAILABLE and pygame.get_init():
            pygame.quit()
            if logger: logger.info("Pygame quit globally at end of editor_main (standalone).")
        return exit_code
    else: # Embedded mode: return the main window instance
        if logger: logger.info("EditorMainWindow instance created for embedding. Returning instance to caller.")
        return main_window

if __name__ == "__main__": # This block is for when editor_main_window.py is run directly
    print("--- editor_main_window.py execution started as __main__ (standalone) ---")
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
            if pygame.joystick and not pygame.joystick.get_init(): 
                 try:
                     pygame.joystick.init()
                     print("INFO: Pygame joystick module initialized (Pygame was already init).")
                 except Exception as e_pygame_joystick_init:
                     print(f"WARNING: Pygame joystick init failed (Pygame was already init): {e_pygame_joystick_init}")
    
    return_code_standalone = editor_main(embed_mode=False)
    print(f"--- editor_main_window.py standalone execution finished (exit code: {return_code_standalone}) ---")
    sys.exit(return_code_standalone)

#################### END OF FILE: editor_main_window.py ####################