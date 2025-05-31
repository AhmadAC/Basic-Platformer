# editor/editor_main_window.py
# -*- coding: utf-8 -*-
"""
Main Window for the Platformer Level Editor (PySide6 Version).
Orchestrates UI components and top-level editor actions.
Version 2.2.8 (Refined controller focus, _add_placeholder call, and _current_active_menu_buttons access)
MODIFIED: Connects and handles opacity toggle signals from SelectionPane.
MODIFIED: Handles `_handle_item_opacity_toggled` to manage `last_visible_opacity`.
"""
import sys
import os
import logging # Use standard logging for this module
import traceback
import time
from typing import Optional, Tuple, List, Any, Dict

_IS_STANDALONE_EXECUTION = (__name__ == "__main__")
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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QGraphicsItem,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox,
    QColorDialog,
    QLabel, QSizePolicy, QMenu, QGraphicsScene
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent, QImage, QPainter, QFont, QCursor, QGuiApplication, QCloseEvent, QContextMenuEvent
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF, Signal, QPointF, QFileInfo, QEvent

# Setup logger for this module
logger = logging.getLogger(__name__) # Use this module's name for its logger

try:
    import pygame
    _PYGAME_AVAILABLE = True
    logger.info("Pygame imported successfully for controller support.")
except ImportError:
    _PYGAME_AVAILABLE = False
    logger.warning("Pygame not found. Controller navigation will be unavailable.")

_IMPORTS_SUCCESSFUL_METHOD = "Unknown"
try:
    logger.info("Attempting relative imports for editor modules...")
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_assets
    from . import editor_map_utils
    from . import editor_history
    from .map_view_widget import MapViewWidget
    from .asset_palette_widget import AssetPaletteWidget
    from .properties_editor_widget import PropertiesEditorDockWidget
    from .editor_selection_pane import SelectionPaneWidget
    from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                                 ACTION_UI_ACCEPT, ACTION_UI_CANCEL, ACTION_UI_MENU,
                                 ACTION_UI_FOCUS_NEXT, ACTION_UI_FOCUS_PREV, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV,
                                 ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                                 ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY,
                                 ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN) # Ensure all are listed
    from . import editor_file_operations as EFO

    if ED_CONFIG.MINIMAP_ENABLED:
        from .minimap_widget import MinimapWidget
    if _PYGAME_AVAILABLE:
        # Assuming main_game.config is accessible from the project root path added earlier
        from main_game.config import init_pygame_and_joystick_globally, get_joystick_objects
    _IMPORTS_SUCCESSFUL_METHOD = "Relative"
    logger.info("Editor modules imported successfully using RELATIVE paths.")
except ImportError as e_relative_import:
    logger.warning(f"Relative import failed: {e_relative_import}. Attempting absolute imports.")
    try:
        from editor import editor_config as ED_CONFIG
        from editor.editor_state import EditorState
        from editor import editor_assets
        from editor import editor_map_utils
        from editor import editor_history
        from editor.map_view_widget import MapViewWidget
        from editor.asset_palette_widget import AssetPaletteWidget
        from editor.properties_editor_widget import PropertiesEditorDockWidget
        from editor.editor_selection_pane import SelectionPaneWidget
        from editor.editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                                 ACTION_UI_ACCEPT, ACTION_UI_CANCEL, ACTION_UI_MENU,
                                 ACTION_UI_FOCUS_NEXT, ACTION_UI_FOCUS_PREV, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV,
                                 ACTION_MAP_ZOOM_IN, ACTION_MAP_ZOOM_OUT,
                                 ACTION_MAP_TOOL_PRIMARY, ACTION_MAP_TOOL_SECONDARY,
                                 ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN)
        from editor import editor_file_operations as EFO

        if ED_CONFIG.MINIMAP_ENABLED:
            from editor.minimap_widget import MinimapWidget
        if _PYGAME_AVAILABLE:
            from main_game.config import init_pygame_and_joystick_globally, get_joystick_objects
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (from editor.*)"
        logger.info("Editor modules imported successfully using ABSOLUTE paths (from editor.*).")
    except ImportError as e_absolute_import:
        logger.critical(f"CRITICAL: Both relative and absolute imports for editor modules failed: {e_absolute_import}")
        raise ImportError(f"Failed to import critical editor modules. Relative: {e_relative_import}. Absolute: {e_absolute_import}") from e_absolute_import

# Configure logging if not already configured by a higher-level module (e.g., a main app entry point)
if not logger.hasHandlers() and not logging.getLogger().hasHandlers(): # Check root logger too
    _main_win_fallback_handler = logging.StreamHandler(sys.stdout)
    _main_win_fallback_formatter = logging.Formatter('EDITOR_MAIN_WINDOW (FallbackConsole - %(filename)s:%(lineno)d): %(levelname)s - %(message)s')
    _main_win_fallback_handler.setFormatter(_main_win_fallback_formatter)
    logger.addHandler(_main_win_fallback_handler)
    logger.setLevel(logging.DEBUG) # Or INFO for less verbosity
    logger.propagate = False
    logger.warning("EditorMainWindow: Using isolated fallback logger for this module.")

logger.info(f"Editor session started. Logging for editor_main_window.py active. Imports via: {_IMPORTS_SUCCESSFUL_METHOD}")


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
        logger.info(f"Initializing EditorMainWindow... Embedded: {self._is_embedded}")

        self.editor_state = EditorState()
        self.settings = QSettings("MyPlatformerGame", "LevelEditor_Qt")
        
        # Initialize UI elements before trying to access them
        self.map_view_widget: MapViewWidget
        self.asset_palette_dock: QDockWidget
        self.asset_palette_widget: AssetPaletteWidget
        self.properties_editor_dock: QDockWidget
        self.properties_editor_widget: PropertiesEditorDockWidget
        self.selection_pane_dock: QDockWidget
        self.selection_pane_widget: SelectionPaneWidget
        self.minimap_dock: Optional[QDockWidget] = None
        self.minimap_widget: Optional[Any] = None # MinimapWidget type if MINIMAP_ENABLED
        self.menu_bar: QMenuBar # Will be set by self.menuBar()
        self.status_bar: QStatusBar # Will be set by self.statusBar()
        self.map_coords_label: QLabel

        self.init_ui() # This initializes the widgets above
        self.create_actions()
        self.create_menus() # This uses self.menuBar()
        self.create_status_bar() # This uses self.statusBar()

        # Set object names for docks AFTER they are created in init_ui
        self.asset_palette_dock.setObjectName("AssetPaletteDock")
        self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        self.selection_pane_dock.setObjectName("SelectionPaneDock")
        if ED_CONFIG.MINIMAP_ENABLED and self.minimap_dock:
            self.minimap_dock.setObjectName("MinimapDock")

        editor_assets.load_editor_palette_assets(self.editor_state, self)
        self.asset_palette_widget.populate_assets()
        self.selection_pane_widget.populate_items()

        if not self._is_embedded:
            self.update_window_title()
        self.update_edit_actions_enabled_state()

        self._current_focused_panel_index: int = 0 # Default to first panel (MapViewWidget)
        self._controller_input_timer: Optional[QTimer] = None
        self._joysticks: List[pygame.joystick.Joystick] = []
        self._primary_joystick: Optional[pygame.joystick.Joystick] = None
        self._controller_axis_deadzone = 0.4
        self._controller_axis_last_event_time: Dict[Tuple[int, int, int], float] = {} # (joy_id, axis_id, direction_sign) -> time
        self._controller_axis_repeat_delay = 0.3
        self._controller_axis_repeat_interval = 0.1
        self._last_dpad_value: Optional[Tuple[int, int]] = None
        self._button_last_state: Dict[int, bool] = {} # button_id -> is_pressed

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
                    default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH
                    default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
                    pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                    pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                    self.showMaximized()
                else:
                    self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)
                    self.showMaximized()
        else:
            logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            self.restore_geometry_and_state()

        if not editor_map_utils.ensure_maps_directory_exists():
            err_msg_maps_dir = f"Base maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}"
            if not self._is_embedded: QMessageBox.critical(self, "Error", err_msg_maps_dir)
            else: logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox)")
        
        logger.info("EditorMainWindow initialized.")
        self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)

        # Initial focus setting
        if self._focusable_panels:
            self._set_panel_controller_focus(0) # Set initial focus to MapViewWidget


    def init_ui(self):
        logger.debug("Initializing UI components...")
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
            if self.properties_editor_dock.parentWidget() == self:
                 self.splitDockWidget(self.properties_editor_dock, self.minimap_dock, Qt.Orientation.Vertical)
            self.minimap_dock.setFixedHeight(ED_CONFIG.MINIMAP_DEFAULT_HEIGHT + 35)
        else:
            self.minimap_dock = None
            self.minimap_widget = None

        # Connect signals
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
        self.map_view_widget.object_graphically_moved_signal.connect(self._handle_internal_object_move_for_unsaved_changes)


        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed)
        self.properties_editor_widget.controller_focus_requested_elsewhere.connect(self._cycle_panel_focus_next)
        self.properties_editor_widget.upload_image_for_trigger_requested.connect(self.handle_upload_image_for_trigger_dialog)

        self.selection_pane_widget.select_map_object_via_pane_requested.connect(self._handle_select_map_object_from_pane)
        self.selection_pane_widget.item_opacity_toggled_in_pane.connect(self._handle_item_opacity_toggled)
        self.selection_pane_widget.item_lock_toggled_in_pane.connect(self._toggle_item_lock)

        if self.minimap_widget:
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs)
        logger.debug("UI components initialized and connected.")

    @Slot(object)
    def _handle_select_map_object_from_pane(self, obj_data_ref_from_pane: Dict[str, Any]):
        logger.debug(f"MainWin: Request to select object from pane (obj_data_ref ID: {id(obj_data_ref_from_pane)}).")
        
        item_to_select: Optional[QGraphicsItem] = None
        found_match = False

        # Search for the QGraphicsItem whose map_object_data_ref matches (by identity) the one from the pane
        for scene_item_candidate in self.map_view_widget._map_object_items.values():
            if hasattr(scene_item_candidate, 'map_object_data_ref') and \
               scene_item_candidate.map_object_data_ref is obj_data_ref_from_pane: # type: ignore
                item_to_select = scene_item_candidate
                found_match = True
                break
        
        if found_match and item_to_select:
            self.map_view_widget.map_scene.blockSignals(True)
            self.map_view_widget.map_scene.clearSelection()
            item_to_select.setSelected(True)
            self.map_view_widget.map_scene.blockSignals(False)
            
            # Manually trigger selection changed logic if needed, as signals were blocked
            self.map_view_widget.on_scene_selection_changed()
            self.selection_pane_widget.sync_selection_from_map() # Ensure pane reflects selection

            # Ensure item is visible if it's being selected (unless explicitly hidden)
            if hasattr(item_to_select, 'map_object_data_ref'):
                item_data = item_to_select.map_object_data_ref # type: ignore
                is_editor_hidden_flag = item_data.get("editor_hidden", False)
                opacity_prop = item_data.get("properties", {}).get("opacity", 100)
                item_to_select.setVisible(not is_editor_hidden_flag and opacity_prop > 0)
            
            self.map_view_widget.ensureVisible(item_to_select, 50, 50) # Scroll to item
            # Optionally, set focus to map view if it makes sense for workflow
            # self.map_view_widget.setFocus(Qt.FocusReason.OtherFocusReason)

            # Logging
            display_name = obj_data_ref_from_pane.get("asset_editor_key", "Unknown")
            if hasattr(item_to_select, 'map_object_data_ref'):
                 obj_data_current = item_to_select.map_object_data_ref # type: ignore
                 palette_asset_info = self.editor_state.assets_palette.get(str(obj_data_current.get("asset_editor_key")))
                 if palette_asset_info:
                    display_name = palette_asset_info.get("name_in_palette", obj_data_current.get("asset_editor_key", "Unknown"))
            logger.info(f"MainWin: Selected item '{display_name}' from pane. Data ID in Scene: {id(getattr(item_to_select, 'map_object_data_ref', None))}")
        else:
            logger.warning(f"MainWin: Could not find matching QGraphicsItem for object from pane (Data ID from pane: {id(obj_data_ref_from_pane)}). Clearing selection.")
            self.map_view_widget.map_scene.clearSelection()
            self.properties_editor_widget.clear_display()
            self.selection_pane_widget.sync_selection_from_map() # Ensure pane reflects cleared selection

    @Slot(object, int)
    def _handle_item_opacity_toggled(self, obj_data_ref: Dict[str, Any], new_target_opacity: int):
        if logger: logger.debug(f"MainWin: Opacity toggle for obj ID {id(obj_data_ref)} to target {new_target_opacity}")
        if obj_data_ref:
            editor_history.push_undo_state(self.editor_state)
            
            props = obj_data_ref.setdefault('properties', {})
            current_opacity = props.get('opacity', 100)

            if new_target_opacity == 0: # Logic to hide
                if current_opacity != 0: props['last_visible_opacity'] = current_opacity
                props['opacity'] = 0
            else: # Logic to make visible
                props['opacity'] = new_target_opacity

            final_opacity = props['opacity']
            self.map_view_widget.update_specific_object_visuals(obj_data_ref)
            self.handle_map_content_changed()

            if self.properties_editor_widget.current_object_data_ref is obj_data_ref:
                self.properties_editor_widget.update_property_field_value(obj_data_ref, "opacity", final_opacity)
            
            # Explicitly update visibility of the QGraphicsItem
            item_graphics = self.map_view_widget._map_object_items.get(id(obj_data_ref))
            if item_graphics:
                is_editor_hidden_flag = obj_data_ref.get("editor_hidden", False)
                item_graphics.setVisible(not is_editor_hidden_flag and final_opacity > 0)
            
            self.selection_pane_widget.populate_items() # Repopulate to update icon

    @Slot(object, bool)
    def _toggle_item_lock(self, obj_data_ref: Dict[str, Any], new_lock_state: bool):
        if logger: logger.debug(f"MainWin: Toggle lock for obj ID {id(obj_data_ref)} to {new_lock_state}")
        if obj_data_ref:
            # Undo state is pushed by SelectionPaneWidget
            obj_data_ref["editor_locked"] = new_lock_state # This should already be done by SelectionPane
            self.map_view_widget.update_specific_object_visuals(obj_data_ref)
            self.handle_map_content_changed() # This will trigger SelectionPane repopulate

    def _init_controller_system(self):
        logger.info("Initializing controller system...")
        try:
            init_pygame_and_joystick_globally(force_rescan=True)
            self._joysticks = get_joystick_objects() # This now returns List[Optional[pygame.joystick.Joystick]]
            
            # Filter out None objects and then get valid, initialized joysticks
            valid_joysticks = [joy for joy in self._joysticks if joy is not None]
            
            if not valid_joysticks:
                self._primary_joystick = None
                logger.info("No joysticks detected or initialized by config.")
                return

            # Attempt to set primary joystick
            self._primary_joystick = None
            for i, joy in enumerate(valid_joysticks):
                try:
                    if not joy.get_init(): joy.init()
                    self._primary_joystick = joy
                    logger.info(f"Primary joystick set: {joy.get_name()} (Pygame Index: {joy.get_id()})")
                    break
                except pygame.error as e:
                    logger.warning(f"Could not initialize joystick at config index {i} (Pygame ID {joy.get_id()}): {e}")
            
            if not self._primary_joystick:
                logger.warning("No valid joystick could be initialized as primary from the detected list.")
                return

            self._controller_input_timer = QTimer(self)
            self._controller_input_timer.setInterval(ED_CONFIG.CONTROLLER_POLL_INTERVAL_MS)
            self._controller_input_timer.timeout.connect(self._poll_controller_input)
            self._controller_input_timer.start()
            logger.info(f"Controller input polling started (Interval: {ED_CONFIG.CONTROLLER_POLL_INTERVAL_MS}ms).")
        except Exception as e:
            logger.error(f"Error initializing controller system: {e}", exc_info=True)
            self._primary_joystick = None
            
    def _poll_controller_input(self):
        if not _PYGAME_AVAILABLE or not self._primary_joystick:
            return
        
        try:
            pygame.event.pump()
        except pygame.error as e_pump:
            logger.warning(f"EditorMainWindow: Pygame event pump error: {e_pump}. Controller input may be lost.")
            return
            
        current_time = time.monotonic()
        joy = self._primary_joystick
        if not joy.get_init():
            try: joy.init()
            except pygame.error: return

        # Define a button map for standard UI actions (example: Switch Pro mapping)
        # This should ideally come from a user-configurable mapping, but here's a basic one.
        # Values are Pygame button IDs.
        button_map = {
            SWITCH_B_BTN: ACTION_UI_ACCEPT,    # Often 'A' on Xbox, Cross on PS
            SWITCH_A_BTN: ACTION_UI_CANCEL,    # Often 'B' on Xbox, Circle on PS
            SWITCH_Y_BTN: ACTION_MAP_TOOL_PRIMARY, # Example tool action
            SWITCH_X_BTN: ACTION_MAP_TOOL_SECONDARY,# Example tool action
            SWITCH_L_BTN: ACTION_UI_TAB_PREV,  # Cycle focus backward
            SWITCH_R_BTN: ACTION_UI_TAB_NEXT,  # Cycle focus forward
            SWITCH_PLUS_BTN: ACTION_UI_MENU,   # Open context menu or main menu
            SWITCH_MINUS_BTN: ACTION_UI_FOCUS_NEXT, # Or map to something like toggle grid
            SWITCH_ZL_BTN: ACTION_MAP_ZOOM_OUT,
            SWITCH_ZR_BTN: ACTION_MAP_ZOOM_IN
        }

        for btn_id_pygame, action_key_editor in button_map.items():
            if btn_id_pygame >= joy.get_numbuttons(): continue # Safety
            
            pressed_now = joy.get_button(btn_id_pygame)
            pressed_last_frame = self._button_last_state.get(btn_id_pygame, False)
            
            if pressed_now and not pressed_last_frame: # Button just pressed (rising edge)
                self.controller_action_dispatched.emit(action_key_editor, True) # True for press
            # Optional: Emit False for release if any actions need release events
            # elif not pressed_now and pressed_last_frame:
            #     self.controller_action_dispatched.emit(action_key_editor, False)
            self._button_last_state[btn_id_pygame] = pressed_now

        # D-Pad (Hat)
        if joy.get_numhats() > SWITCH_DPAD_HAT_ID:
            hat_value_tuple = joy.get_hat(SWITCH_DPAD_HAT_ID) # (x, y)
            if hat_value_tuple != self._last_dpad_value: # Only emit on change
                if hat_value_tuple == (0, 1): self.controller_action_dispatched.emit(ACTION_UI_UP, None)
                elif hat_value_tuple == (0, -1): self.controller_action_dispatched.emit(ACTION_UI_DOWN, None)
                elif hat_value_tuple == (-1, 0): self.controller_action_dispatched.emit(ACTION_UI_LEFT, None)
                elif hat_value_tuple == (1, 0): self.controller_action_dispatched.emit(ACTION_UI_RIGHT, None)
                self._last_dpad_value = hat_value_tuple
        
        # Analog Sticks (Example: Left stick for UI navigation, Right stick for map panning)
        axis_map_for_ui_nav = { # (neg_action, pos_action)
            SWITCH_L_STICK_X_AXIS: (ACTION_UI_LEFT, ACTION_UI_RIGHT),
            SWITCH_L_STICK_Y_AXIS: (ACTION_UI_UP, ACTION_UI_DOWN),
        }
        axis_map_for_camera_pan = {
            SWITCH_R_STICK_X_AXIS: (ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN), # Note: Axis names here are illustrative
            SWITCH_R_STICK_Y_AXIS: (ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN)
        }

        for axis_id_pygame, (neg_action_key, pos_action_key) in {**axis_map_for_ui_nav, **axis_map_for_camera_pan}.items():
            if axis_id_pygame >= joy.get_numaxes(): continue # Safety
            
            axis_value_current = joy.get_axis(axis_id_pygame)
            direction_sign_current = 0 # 0 for neutral, -1 for negative, 1 for positive
            if axis_value_current < -self._controller_axis_deadzone: direction_sign_current = -1
            elif axis_value_current > self._controller_axis_deadzone: direction_sign_current = 1
            
            # Key for tracking this specific axis direction's timer
            timer_key_for_axis_dir = (joy.get_id(), axis_id_pygame, direction_sign_current)

            if direction_sign_current != 0: # Axis is active beyond deadzone
                action_to_emit_this_axis = neg_action_key if direction_sign_current == -1 else pos_action_key
                last_event_time_for_this_axis_dir = self._controller_axis_last_event_time.get(timer_key_for_axis_dir, 0.0)
                
                can_emit_event_now = False
                # First event after delay, or subsequent events after repeat interval
                if current_time - last_event_time_for_this_axis_dir > self._controller_axis_repeat_delay:
                    can_emit_event_now = True
                elif (last_event_time_for_this_axis_dir != 0.0 and # Ensure it's not the very first un-delayed event
                      current_time - last_event_time_for_this_axis_dir > self._controller_axis_repeat_interval):
                    can_emit_event_now = True

                if can_emit_event_now:
                    self.controller_action_dispatched.emit(action_to_emit_this_axis, axis_value_current) # Pass raw axis value
                    self._controller_axis_last_event_time[timer_key_for_axis_dir] = current_time
            else: # Axis is neutral for this specific direction, reset its timer
                # Reset timers for BOTH directions of this axis when it returns to neutral
                key_neg_to_reset = (joy.get_id(), axis_id_pygame, -1)
                key_pos_to_reset = (joy.get_id(), axis_id_pygame, 1)
                if key_neg_to_reset in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_neg_to_reset] = 0.0 # Mark as ready for next press
                if key_pos_to_reset in self._controller_axis_last_event_time:
                    self._controller_axis_last_event_time[key_pos_to_reset] = 0.0


    @Slot(str, object)
    def _dispatch_controller_action_to_panel(self, action_key: str, value: Any):
        logger.debug(f"Controller action received: {action_key}, Value: {value}")
        
        # --- Handle camera panning directly if it's a camera action ---
        if action_key in [ACTION_CAMERA_PAN_UP, ACTION_CAMERA_PAN_DOWN]: # Assuming X maps to vertical pan, Y to horizontal
            pan_speed_pixels_from_config = getattr(ED_CONFIG, 'CONTROLLER_CAMERA_PAN_SPEED_PIXELS', 20)
            pan_amount = pan_speed_pixels_from_config * float(value) # Value is axis value
            
            current_zoom = self.editor_state.zoom_level
            if current_zoom <= 0: current_zoom = 1.0 # Avoid division by zero or negative zoom issues
            
            # Scale pan amount by inverse of zoom so panning feels consistent regardless of zoom
            scaled_pan_amount = pan_amount / current_zoom

            if action_key == ACTION_CAMERA_PAN_UP: # Assuming right stick Y-axis, value < 0 is up
                self.map_view_widget.pan_view_by_scrollbars(0, int(scaled_pan_amount)) # Y pan maps to vertical scroll
            elif action_key == ACTION_CAMERA_PAN_DOWN: # Assuming right stick X-axis, value < 0 is left
                self.map_view_widget.pan_view_by_scrollbars(int(scaled_pan_amount), 0) # X pan maps to horizontal scroll
            return # Consumed by camera panning

        # --- Panel focus cycling (top-level actions) ---
        if action_key == ACTION_UI_FOCUS_NEXT: self._cycle_panel_focus_next(); return
        elif action_key == ACTION_UI_FOCUS_PREV: self._cycle_panel_focus_prev(); return
        elif action_key == ACTION_UI_MENU:
            if self.menu_bar and self.menu_bar.actions():
                first_menu = self.menu_bar.actions()[0].menu()
                if first_menu:
                    first_menu.popup(self.mapToGlobal(self.menu_bar.pos() + QPointF(0, self.menu_bar.height())))
            return
        
        # --- Dispatch to currently focused panel ---
        active_panel_for_dispatch: Optional[QWidget] = None
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
            active_panel_for_dispatch = self._focusable_panels[self._current_focused_panel_index]
        
        qt_focused_widget = QApplication.focusWidget()
        # Ensure our internally tracked focused panel matches or is an ancestor of the Qt focused widget
        is_our_panel_or_ancestor_focused = False
        if active_panel_for_dispatch and qt_focused_widget:
            temp_widget = qt_focused_widget
            while temp_widget:
                if temp_widget == active_panel_for_dispatch:
                    is_our_panel_or_ancestor_focused = True; break
                temp_widget = temp_widget.parentWidget()

        if not is_our_panel_or_ancestor_focused and qt_focused_widget in self._focusable_panels:
            # If Qt's focus is on a different one of our panels, update our internal tracking.
            try:
                new_focus_idx = self._focusable_panels.index(qt_focused_widget)
                self._set_panel_controller_focus(new_focus_idx) # This will update _current_focused_panel_index
                active_panel_for_dispatch = self._focusable_panels[self._current_focused_panel_index]
                logger.info(f"Controller focus internally synced to Qt focused panel: {type(active_panel_for_dispatch).__name__}")
            except ValueError:
                logger.warning("Qt focused widget is one of our panels, but not found in _focusable_panels by index(). This should not happen.")
        
        if active_panel_for_dispatch and hasattr(active_panel_for_dispatch, "handle_controller_action"):
            try: active_panel_for_dispatch.handle_controller_action(action_key, value) # type: ignore
            except Exception as e_panel_action:
                logger.error(f"Error in {type(active_panel_for_dispatch).__name__}.handle_controller_action for '{action_key}': {e_panel_action}", exc_info=True)
        elif active_panel_for_dispatch:
            logger.warning(f"Controller-focused panel {type(active_panel_for_dispatch).__name__} has no handle_controller_action method for action '{action_key}'.")
        else:
            logger.warning(f"No panel has controller focus or index ({self._current_focused_panel_index}) is out of bounds for action '{action_key}'. Qt Focus: {type(qt_focused_widget).__name__ if qt_focused_widget else 'None'}")


    def _set_panel_controller_focus(self, new_index: int):
        if not self._focusable_panels or not (0 <= new_index < len(self._focusable_panels)):
            logger.warning(f"Attempt to set panel focus to invalid index {new_index}")
            return
        
        old_index = self._current_focused_panel_index
        # Notify old panel of focus loss
        if 0 <= old_index < len(self._focusable_panels) and old_index != new_index :
            old_panel = self._focusable_panels[old_index]
            if hasattr(old_panel, "on_controller_focus_lost"):
                try: old_panel.on_controller_focus_lost()
                except Exception as e_focus_lost: logger.error(f"Error in {type(old_panel).__name__}.on_controller_focus_lost: {e_focus_lost}", exc_info=True)
            
            # Reset style of the dock widget containing the old panel
            parent_dock_old = old_panel.parent()
            while parent_dock_old and not isinstance(parent_dock_old, QDockWidget):
                parent_dock_old = parent_dock_old.parent()
            if isinstance(parent_dock_old, QDockWidget): parent_dock_old.setStyleSheet("") # Clear specific focus style
                
        self._current_focused_panel_index = new_index
        new_panel = self._focusable_panels[new_index]
        
        # Notify new panel of focus gain (this panel might then set Qt's setFocus itself)
        if hasattr(new_panel, "on_controller_focus_gained"):
            try: new_panel.on_controller_focus_gained()
            except Exception as e_focus_gained: logger.error(f"Error in {type(new_panel).__name__}.on_controller_focus_gained: {e_focus_gained}", exc_info=True)
        else: # If panel doesn't handle its own Qt focus, set it here
            new_panel.setFocus(Qt.FocusReason.OtherFocusReason)


        panel_name_for_status = type(new_panel).__name__
        parent_dock_new = new_panel.parent()
        while parent_dock_new and not isinstance(parent_dock_new, QDockWidget):
            parent_dock_new = parent_dock_new.parent()
        
        # Apply focus style to the dock widget containing the new panel
        if isinstance(parent_dock_new, QDockWidget):
            panel_name_for_status = parent_dock_new.windowTitle()
            # Using a bright, distinct color for controller focus on the dock title
            focus_border_color = getattr(ED_CONFIG, 'CONTROLLER_DOCK_FOCUS_COLOR', 'cyan') # Example, define in ED_CONFIG
            parent_dock_new.setStyleSheet(f"QDockWidget::title {{ background-color: {focus_border_color}; color: black; border: 1px solid black; padding: 2px; }}")
        elif isinstance(new_panel, MapViewWidget): # MapViewWidget is not in a dock
            panel_name_for_status = "Map View" 
            # Optionally, MapViewWidget could draw its own focus border if self._controller_has_focus is true
        
        self.show_status_message(f"Controller Focus: {panel_name_for_status}", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        logger.info(f"Controller focus set to: {panel_name_for_status} (Index: {new_index})")

    def _cycle_panel_focus_next(self):
        if not self._focusable_panels: return
        new_index = (self._current_focused_panel_index + 1) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def _cycle_panel_focus_prev(self):
        if not self._focusable_panels: return
        new_index = (self._current_focused_panel_index - 1 + len(self._focusable_panels)) % len(self._focusable_panels)
        self._set_panel_controller_focus(new_index)

    def create_actions(self): # No changes, assume it's fine
        logger.debug("Creating actions...")
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
        self.upload_image_action.setEnabled(False) # Enabled based on map state
        logger.debug("Actions created.")

    def create_menus(self): # No changes, assume it's fine
        logger.debug("Creating menus...")
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
        if ED_CONFIG.MINIMAP_ENABLED and self.minimap_dock:
            view_menu.addAction(self.minimap_dock.toggleViewAction())
        
        help_menu = self.menu_bar.addMenu("&Help")
        help_menu.addAction(QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog))
        logger.debug("Menus created.")

    def create_status_bar(self): # No changes, assume it's fine
        logger.debug("Creating status bar...")
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250)
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str, int)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT): # No changes
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")

    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple): # No changes
        world_x, world_y, tile_x, tile_y, zoom_val = coords
        self.map_coords_label.setText(f" Map:({int(world_x)},{int(world_y)}) Tile:({tile_x},{tile_y}) Zoom:{zoom_val:.2f}x ")

    @Slot()
    def handle_map_content_changed(self): # No changes
        if not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes: False -> True.")
        self.editor_state.unsaved_changes = True
        if not self._is_embedded: self.update_window_title()
        self.update_edit_actions_enabled_state()
        if ED_CONFIG.MINIMAP_ENABLED and self.minimap_widget:
            logger.debug("Notifying minimap to redraw content due to map change.")
            self.minimap_widget.schedule_map_content_redraw()
        self.selection_pane_widget.populate_items()
        logger.debug(f"handle_map_content_changed done. Unsaved: {self.editor_state.unsaved_changes}")

    def update_window_title(self): # No changes
        if self._is_embedded: return
        title = "Platformer Level Editor"
        map_name = self.editor_state.map_name_for_function
        if map_name and map_name != "untitled_map": title += f" - {map_name}"
        if self.editor_state.unsaved_changes: title += "*"
        self.setWindowTitle(title)

    @Slot()
    def update_delete_selection_action_enabled_state(self): # No changes
        can_delete = bool(self.map_view_widget.map_scene.selectedItems())
        if hasattr(self, 'delete_selection_action'): self.delete_selection_action.setEnabled(can_delete)

    def update_edit_actions_enabled_state(self): # No changes
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

    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool: # No changes
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes", f"Unsaved changes. Save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save: return self.save_map()
            elif reply == QMessageBox.StandardButton.Cancel: return False
        return True

    # --- File Operations (delegated to EFO) ---
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
    @Slot(dict)
    def handle_upload_image_for_trigger_dialog(self, trigger_object_data_ref: Dict[str, Any]):
        EFO.handle_upload_image_for_trigger_dialog(self, trigger_object_data_ref)

    # --- Context Menu and Layering Actions ---
    @Slot(object, QPointF) 
    def show_map_item_context_menu(self, map_object_data_ref: Dict[str, Any], global_pos_qpointf: QPointF): # No changes
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
        context_menu.exec(QEvent.globalPos() if isinstance(global_pos_qpointf, QContextMenuEvent) else global_pos_qpointf.toPoint())


    def handle_map_item_layer_action(self, map_object_data_ref: Dict[str, Any], direction: str): # No changes
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
        self.show_status_message(f"Object layer order changed to {new_z}.")

    # --- Undo/Redo, View, and Misc Actions ---
    @Slot()
    def undo(self): # No changes
        logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref) # type: ignore
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful.")
            if not self._is_embedded: self.update_window_title()
            self.asset_palette_widget.populate_assets(); self.selection_pane_widget.populate_items()
        else: self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self): # No changes
        logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and hasattr(selected_map_items[0], 'map_object_data_ref'):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref) # type: ignore
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful.")
            if not self._is_embedded: self.update_window_title()
            self.asset_palette_widget.populate_assets(); self.selection_pane_widget.populate_items()
        else: self.show_status_message("Nothing to redo or redo failed.")

    @Slot()
    def toggle_grid(self): # No changes
        self.editor_state.show_grid = not self.editor_state.show_grid
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.map_view_widget.update_grid_visibility()
        self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")

    @Slot()
    def change_background_color(self): # No changes
        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")
        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color()
            self.handle_map_content_changed()
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else: self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self): # No changes
        QMessageBox.about(self, "About Platformer Level Editor", 
                          "Platformer Level Editor by Ahmad Cooper 2025\n\nCreate and edit levels for the platformer game.")

    # --- Event Handlers ---
    def keyPressEvent(self, event: QKeyEvent): # No changes needed here based on previous review
        key = event.key(); modifiers = event.modifiers()
        active_panel: Optional[QWidget] = None
        if self._focusable_panels and 0 <= self._current_focused_panel_index < len(self._focusable_panels):
             active_panel = self._focusable_panels[self._current_focused_panel_index]
        
        # Give focused panel first chance to handle key (for controller-like navigation)
        if active_panel and hasattr(active_panel, 'handle_key_event_for_controller_nav') and \
           active_panel.handle_key_event_for_controller_nav(event): # type: ignore
             event.accept(); return
        
        # If not handled by panel's controller nav, give to MapViewWidget if it has focus
        if self.map_view_widget.hasFocus() and hasattr(self.map_view_widget, 'keyPressEvent'):
             self.map_view_widget.keyPressEvent(event)
             if event.isAccepted(): return
        
        # Global key actions
        if key == Qt.Key.Key_Escape and not self._is_embedded:
            logger.info("Escape key pressed in standalone mode, attempting to close window.")
            self.close(); event.accept(); return
        
        # Standard key events for menus if not handled
        super().keyPressEvent(event)

    def closeEvent(self, eventQCloseEvent: QCloseEvent): # Corrected type hint
        logger.info(f"Close event triggered. Embedded: {self._is_embedded}")
        if self.confirm_unsaved_changes("exit the editor"):
            if self._controller_input_timer and self._controller_input_timer.isActive():
                self._controller_input_timer.stop()
                logger.info("Controller input timer stopped.")
            if _PYGAME_AVAILABLE and self._joysticks:
                for joy in self._joysticks:
                    if joy and joy.get_init():
                        try: joy.quit()
                        except pygame.error as e_joyquit: logger.warning(f"Error quitting joystick on close: {e_joyquit}")
                logger.info("Pygame joysticks un-initialized.")
            self.save_geometry_and_state()
            eventQCloseEvent.accept()
        else: eventQCloseEvent.ignore()

    def save_geometry_and_state(self): # No changes needed based on previous review
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if not self.selection_pane_dock.objectName(): self.selection_pane_dock.setObjectName("SelectionPaneDock")
        if ED_CONFIG.MINIMAP_ENABLED and self.minimap_dock and not self.minimap_dock.objectName():
            self.minimap_dock.setObjectName("MinimapDock")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and dock state explicitly saved.")

    def restore_geometry_and_state(self) -> bool: # No changes needed based on previous review
        geom = self.settings.value("geometry"); state = self.settings.value("windowState")
        restored_geom = False; restored_state = False
        try:
            if geom is not None: self.restoreGeometry(geom); restored_geom = True
            if state is not None: self.restoreState(state); restored_state = True
            logger.debug(f"Window geometry restored: {restored_geom}, state restored: {restored_state}.")
            return restored_geom or restored_state
        except Exception as e_restore:
            logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting.", exc_info=True)
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
            # Change CWD to the script's directory IF running standalone
            # This helps ensure relative paths for assets, logs, etc., work correctly from there.
            script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
            os.chdir(script_dir)
            logger.info(f"Standalone mode: CWD set to: {os.getcwd()}")
        except Exception as e_chdir:
            logger.error(f"Could not change CWD in standalone mode: {e_chdir}")

    logger.info(f"editor_main() called. Embed mode: {embed_mode}, Standalone context: {_IS_STANDALONE_EXECUTION}")
    app = QApplication.instance()
    if app is None:
        if parent_app_instance: app = parent_app_instance
        elif _IS_STANDALONE_EXECUTION: app = QApplication(sys.argv)
        else: raise RuntimeError("Editor needs a QApplication instance, especially in embed_mode if not run as __main__.")

    main_window = EditorMainWindow(embed_mode=embed_mode)

    if not embed_mode:
        exit_code = 0
        try: exit_code = app.exec()
        except Exception as e_main_loop: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True); exit_code = 1
        finally:
            if hasattr(main_window, 'isVisible') and main_window.isVisible(): main_window.save_geometry_and_state()
            logger.info("Editor session (standalone) ended.")
        if _PYGAME_AVAILABLE and pygame.get_init():
            try: pygame.quit()
            except pygame.error as e_pg_quit: logger.warning(f"Error quitting Pygame on exit: {e_pg_quit}")
            logger.info("Pygame quit globally at end of editor_main (standalone).")
        return exit_code
    else:
        logger.info("EditorMainWindow instance created for embedding. Returning instance to caller.")
        return main_window

if __name__ == "__main__":
    print("--- editor_main_window.py execution started as __main__ (standalone) ---")
    if _PYGAME_AVAILABLE:
        if not pygame.get_init():
            try:
                pygame.init()
                print("INFO: Pygame initialized for standalone __main__ execution.")
                if not pygame.joystick.get_init():
                    pygame.joystick.init()
                    print("INFO: Pygame joystick module initialized.")
                else: print("INFO: Pygame joystick module already initialized.")
            except Exception as e_pygame_main_init: print(f"WARNING: Pygame init or joystick init failed in __main__: {e_pygame_main_init}")
        else:
            print("INFO: Pygame already initialized.")
            if pygame.joystick and not pygame.joystick.get_init():
                 try: pygame.joystick.init(); print("INFO: Pygame joystick module initialized (Pygame was already init).")
                 except Exception as e_pygame_joystick_init: print(f"WARNING: Pygame joystick init failed (Pygame was already init): {e_pygame_joystick_init}")
    
    # Ensure the module-level logger is configured before calling editor_main
    if not logger.hasHandlers(): # Re-check, might have been set by project's logger if imported as module
        _main_win_standalone_handler = logging.StreamHandler(sys.stdout)
        _main_win_standalone_formatter = logging.Formatter('EDITOR_MAIN_WINDOW (StandaloneFallback - %(filename)s:%(lineno)d): %(levelname)s - %(message)s')
        _main_win_standalone_handler.setFormatter(_main_win_standalone_formatter)
        logger.addHandler(_main_win_standalone_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False # Don't let root logger also handle if it gets configured
        logger.info("EditorMainWindow (__main__): Using standalone fallback logger configuration.")

    return_code_standalone = editor_main(embed_mode=False)
    print(f"--- editor_main_window.py standalone execution finished (exit code: {return_code_standalone}) ---")
    sys.exit(return_code_standalone)