# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.9 (Robust imports for standalone and module execution)
Level Editor for the Platformer Game (PySide6 Version).
Allows creating, loading, and saving game levels visually.
"""

import sys
import os
import logging
import traceback
from typing import Optional, Tuple

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
    # This allows imports like 'from editor import editor_config'
else:
    print(f"INFO: editor.py running as a module (package: {__package__})")

# --- PySide6 Imports (can be here, as they don't depend on local project structure yet) ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, QFileDialog,
    QColorDialog, QInputDialog, QLabel,QSizePolicy
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent, QImage, QPainter
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF


# --- Attempt to import editor-specific modules ---
# This block needs to come before logger setup if logger uses ED_CONFIG
_IMPORTS_SUCCESSFUL_METHOD = "Unknown"
try:
    # Attempt relative imports first (for when 'editor' is imported as a package)
    print("INFO: Attempting relative imports for editor modules...")
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_assets
    from . import editor_map_utils
    from . import editor_history
    from .map_view_widget import MapViewWidget, MapObjectItem
    from .editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    # Conditional import for minimap based on ED_CONFIG
    # ED_CONFIG should be available at this point if relative imports work
    if ED_CONFIG.MINIMAP_ENABLED:
        from .minimap_widget import MinimapWidget
    _IMPORTS_SUCCESSFUL_METHOD = "Relative"
    print("INFO: Editor modules imported successfully using RELATIVE paths.")

except ImportError as e_relative_import:
    print(f"WARNING: Relative import failed: {e_relative_import}. Attempting absolute imports (expected for standalone execution or flatter structure).")
    if not _IS_STANDALONE_EXECUTION:
        print("WARNING: Relative import failed even when run as a module. This might indicate a packaging issue.")
    
    # Fallback to absolute imports (for standalone execution or if project structure allows)
    # This assumes 'editor' package is findable in sys.path (e.g., project root added)
    try:
        from editor import editor_config as ED_CONFIG
        from editor.editor_state import EditorState
        from editor import editor_assets
        from editor import editor_map_utils
        from editor import editor_history
        from editor.map_view_widget import MapViewWidget, MapObjectItem
        from editor.editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
        # ED_CONFIG should be available here too for the conditional import
        if ED_CONFIG.MINIMAP_ENABLED:
            from editor.minimap_widget import MinimapWidget
        _IMPORTS_SUCCESSFUL_METHOD = "Absolute (from editor.*)"
        print("INFO: Editor modules imported successfully using ABSOLUTE paths (from editor.*).")
    except ImportError as e_absolute_import:
        print(f"CRITICAL: Both relative and absolute imports for editor modules failed.")
        print(f"  Relative import error: {e_relative_import}")
        print(f"  Absolute import error: {e_absolute_import}")
        print(f"  Current sys.path: {sys.path}")
        print("  Ensure the project root is in sys.path and the 'editor' directory can be found as a package.")
        # A simple QMessageBox might not work if QApplication isn't up yet.
        # For now, just re-raise, which will likely terminate the script.
        raise ImportError(f"Failed to import critical editor modules. Relative error: {e_relative_import}. Absolute error: {e_absolute_import}") from e_absolute_import
    except AttributeError as e_attr_config_check: # Catch if ED_CONFIG wasn't loaded for MINIMAP_ENABLED check
        print(f"CRITICAL: AttributeError during absolute import phase, likely ED_CONFIG not loaded: {e_attr_config_check}")
        raise AttributeError(f"Failed due to ED_CONFIG not being available for MINIMAP_ENABLED check: {e_attr_config_check}") from e_attr_config_check


# --- Logger Setup (now that ED_CONFIG is expected to be loaded) ---
logger: Optional[logging.Logger] = None # Type hint for logger
log_file_path_for_error_msg = "editor_qt_debug.log" # Default
try:
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs') # Store logs inside editor/logs
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    
    # Use ED_CONFIG for log file name and level if available
    log_file_name = ED_CONFIG.LOG_FILE_NAME if hasattr(ED_CONFIG, "LOG_FILE_NAME") else "editor_qt_debug.log"
    log_file_path_for_error_msg = os.path.join(logs_dir, log_file_name)
    
    log_level_str = ED_CONFIG.LOG_LEVEL.upper() if hasattr(ED_CONFIG, "LOG_LEVEL") else "DEBUG"
    numeric_log_level = getattr(logging, log_level_str, logging.DEBUG)
    
    log_format_str = ED_CONFIG.LOG_FORMAT if hasattr(ED_CONFIG, "LOG_FORMAT") else \
                     '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'

    # Clear existing handlers from root logger to prevent duplicate logs
    # This is important if the script/module might be reloaded or run multiple times in a session
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close() 

    logging.basicConfig(
        level=numeric_log_level,
        format=log_format_str,
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')]
    )
    logger = logging.getLogger("EditorMainWindowLogger") # Use a more specific logger name
    logger.info(f"Editor session started. Logging initialized successfully to '{log_file_path_for_error_msg}'. Imports via: {_IMPORTS_SUCCESSFUL_METHOD}")
except Exception as e_log_setup:
    # Fallback basic console logging if file logger setup fails
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE FALLBACK (editor.py logger setup): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("EditorMainWindowLogger_Fallback") # Fallback logger name
    logger.error(f"CRITICAL ERROR DURING FILE LOGGING SETUP (editor.py): {e_log_setup}. Using console.", exc_info=True)
    logger.info(f"Imports were attempted via: {_IMPORTS_SUCCESSFUL_METHOD}")
# --- End Logger Setup ---


class EditorMainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None, embed_mode: bool = False): 
        super().__init__(parent) 
        self._is_embedded = embed_mode 
        logger.info(f"Initializing EditorMainWindow... Embedded: {self._is_embedded}")

        self.editor_state = EditorState()
        self.settings = QSettings("MyPlatformerGame", "LevelEditor_Qt")

        if not self._is_embedded: 
            self.setWindowTitle("Platformer Level Editor (PySide6)")
            # Set initial geometry only if standalone and no saved geometry
            if not self.settings.value("geometry"):
                # Try to center on primary screen if QScreen is available
                primary_screen = QApplication.primaryScreen()
                if primary_screen:
                    screen_geo = primary_screen.availableGeometry()
                    default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH
                    default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
                    pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                    pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                    self.setGeometry(pos_x, pos_y, default_w, default_h)
                else: # Fallback if no screen info
                    self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)


        self.init_ui()
        self.create_actions()
        self.create_menus()
        self.create_status_bar()

        self.asset_palette_dock.setObjectName("AssetPaletteDock")
        self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock:
            self.minimap_dock.setObjectName("MinimapDock")

        editor_assets.load_editor_palette_assets(self.editor_state, self)
        self.asset_palette_widget.populate_assets()

        if not self._is_embedded: 
            self.update_window_title()
        self.update_edit_actions_enabled_state()

        if not self._is_embedded:
            if not self.restore_geometry_and_state():
                logger.info("Standalone mode: No saved geometry/state or restoration failed, showing with default/calculated geometry.")
                # self.showMaximized() # User might prefer not maximized by default
            else:
                logger.info("Standalone mode: Restored geometry/state, showing window.")
            self.show() # Ensure show is called for standalone
        else:
            logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            self.restore_geometry_and_state()


        if not editor_map_utils.ensure_maps_directory_exists():
            err_msg_maps_dir = f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}"
            logger.error(err_msg_maps_dir + " (Embedded mode, no QMessageBox displayed by editor itself)")
            if not self._is_embedded: 
                QMessageBox.critical(self, "Error", err_msg_maps_dir)
            # For embedded mode, the parent application might need to handle this failure.

        logger.info("EditorMainWindow initialized.")
        if hasattr(self, 'status_bar') and self.status_bar:
            self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
        else:
            logger.info("Status: Editor started. Welcome! (Status bar not used or not yet available).")


    def init_ui(self):
        logger.debug("Initializing UI components...")
        
        self.map_view_widget = MapViewWidget(self.editor_state, self)
        self.setCentralWidget(self.map_view_widget)

        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self)
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(max(200, ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50))
        self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 100)

        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self)
        self.properties_editor_dock.setWidget(self.properties_editor_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_editor_dock)
        self.properties_editor_dock.setMinimumWidth(280)

        if ED_CONFIG.MINIMAP_ENABLED:
            self.minimap_dock = QDockWidget("Minimap", self)
            self.minimap_widget = MinimapWidget(self.editor_state, self.map_view_widget, self)
            self.minimap_dock.setWidget(self.minimap_widget)
            # Docking order: Add minimap first, then split it with properties to have properties below minimap
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock) 
            self.splitDockWidget(self.minimap_dock, self.properties_editor_dock, Qt.Orientation.Vertical) 
            # Set fixed height for minimap after it's part of a layout to allow properties to fill remaining space
            self.minimap_dock.setFixedHeight(ED_CONFIG.MINIMAP_DEFAULT_HEIGHT + 35) # +35 for title bar etc.
        else:
            self.minimap_dock = None # type: ignore
            self.minimap_widget = None # type: ignore

        # Connect signals
        self.asset_palette_widget.asset_selected.connect(self.map_view_widget.on_asset_selected)
        self.asset_palette_widget.asset_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)
        self.asset_palette_widget.paint_color_changed_for_status.connect(self.show_status_message)

        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)

        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed) # Properties change is map content change

        if self.minimap_widget: # Check if minimap_widget was created
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs)
        self.map_view_widget.setFocus() # Give focus to map view initially
        logger.debug("UI components initialized.")

    def create_actions(self):
        logger.debug("Creating actions...")
        self.new_map_action = QAction("&New Map...", self, shortcut=QKeySequence.StandardKey.New, statusTip="Create a new map", triggered=self.new_map)
        self.load_map_action = QAction("&Load Map...", self, shortcut=QKeySequence.StandardKey.Open, statusTip="Load an existing map", triggered=self.load_map)
        self.save_map_action = QAction("&Save Map", self, shortcut=QKeySequence.StandardKey.Save, statusTip="Save the current map's editor data (.json)", triggered=self.save_map_json)
        self.export_map_action = QAction("&Export Map for Game...", self, shortcut=QKeySequence("Ctrl+E"), statusTip="Export map to game format (.py)", triggered=self.export_map_py)
        self.save_all_action = QAction("Save &All (JSON & PY)", self, shortcut=QKeySequence("Ctrl+Shift+S"), statusTip="Save editor data and export for game", triggered=self.save_all)

        self.export_map_as_image_action = QAction("Export Map as &Image...", self,
                                                  shortcut="Ctrl+Shift+P", # Common shortcut for print/export image
                                                  statusTip="Export the current map view as a PNG image",
                                                  triggered=self.export_map_as_image)

        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit, statusTip="Exit the editor", triggered=self.close) # self.close will trigger closeEvent

        self.undo_action = QAction("&Undo", self, shortcut=QKeySequence.StandardKey.Undo, statusTip="Undo last action", triggered=self.undo)
        self.redo_action = QAction("&Redo", self, shortcut=QKeySequence.StandardKey.Redo, statusTip="Redo last undone action", triggered=self.redo)

        self.toggle_grid_action = QAction("Toggle &Grid", self, shortcut="Ctrl+G", statusTip="Show/Hide grid", triggered=self.toggle_grid, checkable=True)
        self.toggle_grid_action.setChecked(self.editor_state.show_grid) # Init from state
        self.change_bg_color_action = QAction("Change &Background Color...", self, statusTip="Change map background color", triggered=self.change_background_color)

        self.zoom_in_action = QAction("Zoom &In", self, shortcut=QKeySequence.StandardKey.ZoomIn, statusTip="Zoom in on the map", triggered=self.map_view_widget.zoom_in)
        self.zoom_out_action = QAction("Zoom &Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, statusTip="Zoom out of the map", triggered=self.map_view_widget.zoom_out)
        self.zoom_reset_action = QAction("Reset &Zoom", self, shortcut="Ctrl+0", statusTip="Reset map zoom to 100%", triggered=self.map_view_widget.reset_zoom)

        self.rename_map_action = QAction("&Rename Current Map...", self, statusTip="Rename the current map's files", triggered=self.rename_map)
        self.delete_map_file_action = QAction("&Delete Map File...", self, statusTip="Delete a map's .json and .py files", triggered=self.delete_map_file)
        logger.debug("Actions created.")

    def create_menus(self):
        logger.debug("Creating menus...")
        self.menu_bar = self.menuBar() # Ensure menu bar exists
        # If embedded, the parent application might provide its own menu system.
        # For simplicity, the editor will always create its own menu bar.
        # If truly embedded without its own menu bar desired, this could be conditional.

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
        file_menu.addAction(self.exit_action) # This will call self.close()

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
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock:
            view_menu.addAction(self.minimap_dock.toggleViewAction())

        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog)
        help_menu.addAction(about_action)
        logger.debug("Menus created.")

    def create_status_bar(self):
        logger.debug("Creating status bar...")
        # If embedded, status bar might not be desired, or parent handles it.
        # For now, always create it. Can be made conditional on self._is_embedded.
        self.status_bar = self.statusBar() 
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250) # Give it some space
        self.status_bar.addPermanentWidget(self.map_coords_label)
        
        # Connect signal for map coordinates update
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT):
        if hasattr(self, 'status_bar') and self.status_bar: # Check if status_bar exists
            self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")


    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        # coords is expected to be (world_x, world_y, tile_x, tile_y, zoom_level)
        world_x, world_y, tile_x, tile_y, zoom_val = coords
        self.map_coords_label.setText(f" Map:({int(world_x)},{int(world_y)}) Tile:({tile_x},{tile_y}) Zoom:{zoom_val:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        logger.debug("EditorMainWindow: handle_map_content_changed triggered.")
        if not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes was False, now set to True.")
        self.editor_state.unsaved_changes = True
        
        if not self._is_embedded: # Only update QMainWindow title if standalone
            self.update_window_title()
            
        self.update_edit_actions_enabled_state()

        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_widget') and self.minimap_widget:
             logger.debug("Notifying minimap to redraw content due to map change via handle_map_content_changed.")
             self.minimap_widget.schedule_map_content_redraw()

        logger.debug(f"EditorMainWindow: After handle_map_content_changed - unsaved_changes: {self.editor_state.unsaved_changes}, save_map_action enabled: {self.save_map_action.isEnabled()}")


    def update_window_title(self):
        if self._is_embedded: # Don't change title if embedded
            return
        
        title = "Platformer Level Editor (PySide6)"
        map_name = self.editor_state.map_name_for_function
        if map_name and map_name != "untitled_map":
            title += f" - {map_name}"
            if self.editor_state.current_json_filename:
                 # Add the actual filename in brackets for clarity
                 title += f" [{os.path.basename(self.editor_state.current_json_filename)}]"
        if self.editor_state.unsaved_changes:
            title += "*" # Indicate unsaved changes
        self.setWindowTitle(title)


    def update_edit_actions_enabled_state(self):
        # A map is considered "active" or "valid" for saving/exporting if it has a name
        # (other than the default "untitled_map") OR if it has content.
        # Current JSON filename is a stronger indicator of a saved/loaded map.
        map_is_properly_loaded_or_newly_named = bool(
            self.editor_state.current_json_filename or \
            (self.editor_state.map_name_for_function != "untitled_map" and \
             self.editor_state.placed_objects) # Consider if empty named map can be saved
        )

        # Can save if there are unsaved changes AND the map is either loaded or has a name & content
        can_save = map_is_properly_loaded_or_newly_named and self.editor_state.unsaved_changes
        self.save_map_action.setEnabled(can_save)

        # Can export or save_all if map is loaded or named (content not strictly required for export placeholder)
        self.export_map_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.save_all_action.setEnabled(map_is_properly_loaded_or_newly_named) # Save All implies saving JSON first
        self.rename_map_action.setEnabled(bool(self.editor_state.current_json_filename)) # Can only rename if a file exists

        # Undo/Redo based on stack sizes
        self.undo_action.setEnabled(len(self.editor_state.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack) > 0)

        # View/Edit actions that depend on having any map context (even an empty new one)
        map_active = bool(self.editor_state.map_name_for_function != "untitled_map" or self.editor_state.placed_objects)
        self.change_bg_color_action.setEnabled(map_active)
        self.toggle_grid_action.setEnabled(map_active)
        self.zoom_in_action.setEnabled(map_active)
        self.zoom_out_action.setEnabled(map_active)
        self.zoom_reset_action.setEnabled(map_active)

        map_has_content = bool(self.editor_state.placed_objects or self.editor_state.current_json_filename)
        self.export_map_as_image_action.setEnabled(map_has_content)


    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool:
        """
        Checks for unsaved changes and prompts the user to save, discard, or cancel.
        Returns True if the action can proceed, False if cancelled.
        """
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         f"You have unsaved changes. Do you want to save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel) # Default to Cancel
            if reply == QMessageBox.StandardButton.Save:
                return self.save_all() # save_all returns True on success
            elif reply == QMessageBox.StandardButton.Cancel:
                return False # Action cancelled
            # If Discard, fall through to return True (proceed without saving)
        return True # No unsaved changes, or user chose to discard

    @Slot()
    def new_map(self):
        logger.info("New Map action triggered.")
        if not self.confirm_unsaved_changes("create a new map"): return
        
        map_name, ok = QInputDialog.getText(self, "New Map", "Enter map name (e.g., level_1 or level_default):")
        if ok and map_name:
            clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_map_name:
                QMessageBox.warning(self, "Invalid Name", "Map name cannot be empty."); return
            
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.'] # Common invalid filename chars
            if any(char in clean_map_name for char in invalid_chars):
                QMessageBox.warning(self, "Invalid Name", f"Map name '{clean_map_name}' contains invalid characters."); return
            
            # Check if map files already exist (relative to project root/maps)
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
            if not editor_map_utils.ensure_maps_directory_exists():
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

            potential_json_path = os.path.join(maps_abs_dir, clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            # potential_py_path = os.path.join(maps_abs_dir, clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION) # Not strictly needed to check py yet

            if os.path.exists(potential_json_path):
                QMessageBox.warning(self, "Name Exists", f"A map JSON file named '{os.path.basename(potential_json_path)}' already exists in the maps directory."); return
            
            # Get map size
            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):", text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}")
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(',')
                    width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 1000); max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 1000)
                    if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h):
                        raise ValueError(f"Dimensions must be between 1 and max ({max_w}x{max_h}).")
                    
                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles)
                    self.map_view_widget.load_map_from_state()
                    self.asset_palette_widget.clear_selection()
                    self.properties_editor_widget.clear_display()
                    if not self._is_embedded: self.update_window_title()
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                    editor_history.push_undo_state(self.editor_state) # Push initial state
                    self.update_edit_actions_enabled_state()
                except ValueError as e_size:
                    QMessageBox.warning(self, "Invalid Size", f"Invalid map size format or value: {e_size}")
                except Exception as e_new_map:
                    logger.error(f"Error during new map creation: {e_new_map}", exc_info=True)
                    QMessageBox.critical(self, "Error", f"Could not create new map: {e_new_map}")
        else:
            self.show_status_message("New map cancelled.")

    @Slot()
    def load_map(self):
        logger.info("Load Map action triggered.")
        if not self.confirm_unsaved_changes("load another map"): return
        
        project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
        if not editor_map_utils.ensure_maps_directory_exists():
             QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Map", maps_abs_dir, json_filter)
        
        if file_path:
            logger.info(f"Attempting to load map from: {file_path}")
            if editor_map_utils.load_map_from_json(self.editor_state, file_path):
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.properties_editor_widget.clear_display()
                if not self._is_embedded: self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state) # Push loaded state as first undo
                self.update_edit_actions_enabled_state()
            else:
                QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else:
            self.show_status_message("Load map cancelled.")

    @Slot()
    def save_map_json(self) -> bool:
        logger.info("Save Map (JSON) action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            # If map is untitled, it means it's a new map that hasn't been saved yet.
            # Trigger Save All to get the name and save both files.
            self.show_status_message("Map is untitled. Performing initial Save All to set name and save files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
            return self.save_all() 
            
        if editor_map_utils.save_map_to_json(self.editor_state):
            self.show_status_message(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename or 'unknown.json')}.")
            self.editor_state.unsaved_changes = False 
            if not self._is_embedded: self.update_window_title()
            self.update_edit_actions_enabled_state()
            return True
        else:
            QMessageBox.critical(self, "Save Error", "Failed to save map editor data (.json). Check logs.")
            return False

    @Slot()
    def export_map_py(self) -> bool:
        logger.info("Export Map (PY) action triggered.")
        if not self.editor_state.current_json_filename: # PY export depends on a saved JSON
             QMessageBox.warning(self, "Cannot Export", "No map is currently loaded/saved. Save the map first (JSON format)."); return False
        
        if editor_map_utils.export_map_to_game_python_script(self.editor_state):
            # Exporting to PY might not necessarily clear unsaved changes if JSON wasn't just saved
            # self.editor_state.unsaved_changes = False # Only if save_all was used or if we consider export a "save"
            # if not self._is_embedded: self.update_window_title()
            # self.update_edit_actions_enabled_state()
            self.show_status_message(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename or 'unknown.py')}.")
            return True
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export map for game (.py). Check logs.")
            return False

    @Slot()
    def save_all(self) -> bool:
        logger.info("Save All action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            # Prompt for map name if it's the first save or "untitled_map"
            map_name, ok = QInputDialog.getText(self, "Save Map As", "Enter map name for saving all files (e.g., level_default):")
            if ok and map_name:
                clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
                if not clean_map_name or any(c in clean_map_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']):
                    QMessageBox.warning(self, "Invalid Name", "Map name is invalid or empty."); return False
                
                # Update editor state with the new name and file paths
                self.editor_state.map_name_for_function = clean_map_name
                json_fn = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
                py_fn = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
                
                project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
                if not editor_map_utils.ensure_maps_directory_exists(): # Ensure maps dir exists
                    QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return False

                self.editor_state.current_json_filename = os.path.join(maps_abs_dir, json_fn)
                self.editor_state.current_map_filename = os.path.join(maps_abs_dir, py_fn)
                if not self._is_embedded: self.update_window_title() # Update title with new name
            else: # User cancelled name input
                self.show_status_message("Save All cancelled: map name not provided."); return False

        # Now proceed with saving JSON and then PY
        if self.save_map_json(): # save_map_json will now use the (potentially new) name
            if self.export_map_py():
                self.show_status_message("Map saved (JSON & PY)."); return True
        
        # If either save_map_json or export_map_py failed (they show their own error messages)
        self.show_status_message("Save All failed. Check logs."); return False


    @Slot()
    def rename_map(self):
        logger.info("Rename Map action triggered.")
        if not self.editor_state.current_json_filename: # Can only rename an existing, saved map
            QMessageBox.information(self, "Rename Map", "No map loaded to rename. Please load or save a map first."); return
        
        old_base_name = self.editor_state.map_name_for_function # This should be valid if current_json_filename exists

        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"Enter new name for map '{old_base_name}':", text=old_base_name)
        if ok and new_name_str:
            clean_new_name = new_name_str.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_new_name or any(c in clean_new_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']):
                QMessageBox.warning(self, "Invalid Name", "New map name is invalid or contains forbidden characters."); return
            
            if clean_new_name == old_base_name:
                self.show_status_message("Rename cancelled: name unchanged."); return
            
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
            if not editor_map_utils.ensure_maps_directory_exists():
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

            # Check if new name would conflict with existing files (other than the one being renamed)
            new_json_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(new_json_path) and os.path.normcase(new_json_path) != os.path.normcase(self.editor_state.current_json_filename): # type: ignore
                QMessageBox.warning(self, "Rename Error", f"A map JSON file named '{os.path.basename(new_json_path)}' already exists."); return
            
            old_json_path = self.editor_state.current_json_filename
            old_py_path = self.editor_state.current_map_filename 
            new_py_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)

            try:
                logger.info(f"Attempting rename of map '{old_base_name}' to '{clean_new_name}'.")
                # Rename the JSON file on disk
                if old_json_path and os.path.exists(old_json_path):
                    os.rename(old_json_path, new_json_path)
                
                # Update editor state to reflect new name and paths
                self.editor_state.map_name_for_function = clean_new_name
                self.editor_state.current_json_filename = new_json_path
                self.editor_state.current_map_filename = new_py_path 
                
                # Save the (potentially modified in memory) map data to the NEW JSON file path
                # This ensures the map_name_for_function inside the JSON is also updated.
                if not editor_map_utils.save_map_to_json(self.editor_state): 
                    QMessageBox.critical(self, "Rename Error", "Failed to save map data to the new JSON file after renaming the file. State might be inconsistent."); return
                
                # Delete old .py file if it exists and is different from new .py path
                if old_py_path and os.path.exists(old_py_path) and os.path.normcase(old_py_path) != os.path.normcase(new_py_path):
                    os.remove(old_py_path)
                    logger.info(f"Old PY file '{os.path.basename(old_py_path)}' deleted after rename.")
                
                # Export to new .py file
                if editor_map_utils.export_map_to_game_python_script(self.editor_state):
                    self.show_status_message(f"Map renamed to '{clean_new_name}' and files updated.")
                else:
                    # JSON was renamed and saved, but PY export failed. Data is safe in new JSON.
                    QMessageBox.warning(self, "Rename Warning", "Map files renamed (JSON updated), but exporting to the new PY file failed. Please try 'Save All' or 'Export' manually.");
                    self.editor_state.unsaved_changes = True # Mark as unsaved due to PY export failure
                
                if not self._is_embedded: self.update_window_title()
                self.update_edit_actions_enabled_state()

            except Exception as e_rename_map:
                logger.error(f"Error during map rename process: {e_rename_map}", exc_info=True)
                QMessageBox.critical(self, "Rename Error", f"An unexpected error occurred during map rename: {e_rename_map}")
        else:
            self.show_status_message("Rename map cancelled.")

    @Slot()
    def delete_map_file(self):
        logger.info("Delete Map File action triggered.")
        project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
        if not editor_map_utils.ensure_maps_directory_exists():
             QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Map to Delete", maps_abs_dir, json_filter)
        
        if file_path:
            map_name_to_delete = os.path.splitext(os.path.basename(file_path))[0]
            # Double-check against deleting "level_default" unless explicitly typed by user (or handle this based on policy)
            # if map_name_to_delete == "level_default":
            #     QMessageBox.warning(self, "Cannot Delete", "'level_default' is a special map and cannot be deleted through this interface."); return

            reply = QMessageBox.warning(self, "Confirm Delete", 
                                        f"Are you sure you want to delete ALL files (JSON and PY) for map '{map_name_to_delete}'?\nThis action CANNOT be undone.",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No) # Default to No
            if reply == QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state, file_path): # Pass JSON path to delete util
                    self.show_status_message(f"Map '{map_name_to_delete}' files deleted.")
                    # If the deleted map was the currently loaded one, reset the editor state
                    if self.editor_state.current_json_filename and \
                       os.path.normcase(self.editor_state.current_json_filename) == os.path.normcase(file_path):
                        logger.info(f"Deleted map was currently loaded. Resetting editor state.")
                        self.editor_state.reset_map_context()
                        self.map_view_widget.load_map_from_state() # Will show empty state
                        self.asset_palette_widget.clear_selection()
                        self.properties_editor_widget.clear_display()
                        if not self._is_embedded: self.update_window_title()
                        self.update_edit_actions_enabled_state()
                else:
                    QMessageBox.critical(self, "Delete Error", f"Failed to delete some or all files for map '{map_name_to_delete}'. Check logs.")
            else:
                self.show_status_message("Delete map cancelled.")
        else:
            self.show_status_message("Delete map selection cancelled.")

    @Slot()
    def export_map_as_image(self):
        logger.info("Export Map as Image action triggered.")
        if not self.editor_state.placed_objects and not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Export Error", "No map content to export as an image. Create or load a map.")
            return

        default_map_name = self.editor_state.map_name_for_function if self.editor_state.map_name_for_function != "untitled_map" else "untitled_map_export"
        
        # Suggest saving in a 'map_exports' subdirectory of the project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suggested_dir = os.path.join(project_root, "map_exports")
        if not os.path.exists(suggested_dir):
            try:
                os.makedirs(suggested_dir)
            except OSError as e_mkdir:
                logger.error(f"Could not create 'map_exports' directory: {e_mkdir}. Defaulting to maps directory.")
                suggested_dir = os.path.join(project_root, ED_CONFIG.MAPS_DIRECTORY) # Fallback
        
        suggested_path = os.path.join(suggested_dir, default_map_name + ".png")
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Map as Image", suggested_path, "PNG Images (*.png);;All Files (*)")
        
        if not file_path:
            self.show_status_message("Export map as image cancelled.")
            logger.info("Export map as image cancelled by user.")
            return
        
        try:
            scene = self.map_view_widget.scene()
            if not scene:
                QMessageBox.critical(self, "Export Error", "Cannot access map scene for export."); return
            
            # Determine the bounding box of all items in the scene
            target_rect = scene.itemsBoundingRect() # This is in scene coordinates
            if target_rect.isEmpty():
                 QMessageBox.information(self, "Export Error", "Map is empty, nothing to export as image.")
                 return

            # Add some padding around the content
            padding = 20 # Pixels in scene coordinates
            target_rect.adjust(-padding, -padding, padding, padding)


            # Create an QImage with the size of the target_rect
            # QRectF.size() returns QSizeF, QImage constructor wants QSize (int width, int height)
            image_size = QSizePolicy(int(target_rect.width()), int(target_rect.height()))
            if image_size.width() <=0 or image_size.height() <=0:
                QMessageBox.critical(self, "Export Error", f"Invalid image dimensions for export: {image_size.width()}x{image_size.height()}"); return

            image = QImage(image_size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent) # Start with a transparent background
            
            painter = QPainter(image)
            # Important: Set render hints for quality, especially if not using default QGraphicsView rendering
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Usually False for pixel art
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

            # Render the scene onto the QImage.
            # The sourceRect (target_rect) is in scene coordinates.
            # The targetRectForPainter (image.rect()) is in painter (image) coordinates.
            scene.render(painter, QRectF(image.rect()), target_rect)
            painter.end()
            
            if image.save(file_path, "PNG"): # Save as PNG
                self.show_status_message(f"Map exported as image: {os.path.basename(file_path)}")
                logger.info(f"Map successfully exported as PNG to: {file_path}")
            else:
                QMessageBox.critical(self, "Export Error", f"Failed to save image to:\n{file_path}")
                logger.error(f"Failed to save map image to {file_path}")

        except Exception as e_export_img:
            logger.error(f"Error exporting map as image: {e_export_img}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"An unexpected error occurred during image export:\n{e_export_img}")


    @Slot()
    def undo(self):
        logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state):
            self.map_view_widget.load_map_from_state() # Reload view with undone state
            self.update_edit_actions_enabled_state()
            # Update properties panel if a single item is selected after undo
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else:
                self.properties_editor_widget.clear_display() # Clear if no/multiple selection
            self.show_status_message("Undo successful."); 
            if not self._is_embedded: self.update_window_title() # Title might change (unsaved status)
        else:
            self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self):
        logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state):
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem):
                self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else:
                self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful."); 
            if not self._is_embedded: self.update_window_title()
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
        # Allow changing BG color even for an empty "untitled" map before first save
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            if not self.editor_state.placed_objects: # And no objects placed yet
                 # Allow for a new, empty map. User might want to set BG first.
                 pass # QMessageBox.information(self, "Change Background Color", "Please load or create a map first."); return

        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")
        
        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color() # MapViewWidget will update its scene BG
            self.handle_map_content_changed() # Changing BG color is an unsaved change
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else:
            self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self):
        QMessageBox.about(self, "About Platformer Level Editor", 
                          "Platformer Level Editor (PySide6 Version)\n\n"
                          "Create and edit levels for your platformer game.")

    def keyPressEvent(self, event: QKeyEvent):
        # Only handle Esc for closing if in standalone mode
        if event.key() == Qt.Key.Key_Escape and not self._is_embedded:
            logger.info("Escape key pressed in standalone mode, attempting to close window.")
            self.close() # This will trigger the closeEvent
            event.accept()
        else:
            # Pass to MapViewWidget if it has focus and might handle keys (e.g., for panning, tool shortcuts)
            if self.map_view_widget.hasFocus():
                 self.map_view_widget.keyPressEvent(event)
                 if event.isAccepted(): return # Don't pass to super if map_view handled it
            super().keyPressEvent(event)


    def closeEvent(self, event):
        logger.info(f"Close event triggered for EditorMainWindow. Embedded: {self._is_embedded}")
        
        if self.confirm_unsaved_changes("exit the editor"):
            # Ensure dock widgets have object names for state saving
            if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
            if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
            if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName():
                self.minimap_dock.setObjectName("MinimapDock")

            # Save geometry and state
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            logger.info("Window geometry and state saved on close.")
            
            # If running standalone, QApplication.quit() might be called by app.exec() implicitly.
            # If embedded, the parent is responsible for true cleanup.
            event.accept() # Allow the window to close
        else:
            event.ignore() # Prevent the window from closing

    # These methods are for explicit saving/restoring, e.g., when embedded.
    def save_geometry_and_state(self):
        """Saves window geometry and dock state. Useful for embedding context."""
        # Ensure dock widgets have object names before saving state
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName():
            self.minimap_dock.setObjectName("MinimapDock")

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and dock state explicitly saved via save_geometry_and_state().")

    def restore_geometry_and_state(self) -> bool:
        """Restores window geometry and dock state."""
        geom = self.settings.value("geometry")
        state = self.settings.value("windowState")
        restored_geom = False
        restored_state = False
        
        try:
            if geom is not None:
                self.restoreGeometry(geom)
                restored_geom = True
            if state is not None:
                self.restoreState(state)
                restored_state = True
            
            if restored_geom or restored_state:
                logger.debug(f"Window geometry restored: {restored_geom}, state restored: {restored_state}.")
            else:
                logger.debug("No geometry or state found in settings to restore.")
            return restored_geom or restored_state
        except Exception as e_restore:
            logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting to defaults if applicable.", exc_info=True)
            # If standalone and restoration fails, reset to default size/pos
            if not self._is_embedded:
                 primary_screen = QApplication.primaryScreen()
                 if primary_screen:
                     screen_geo = primary_screen.availableGeometry()
                     default_w = ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH; default_h = ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
                     pos_x = screen_geo.x() + (screen_geo.width() - default_w) // 2
                     pos_y = screen_geo.y() + (screen_geo.height() - default_h) // 2
                     self.setGeometry(pos_x, pos_y, default_w, default_h)
                 else: self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)
            return False 


def editor_main(parent_app_instance: Optional[QApplication] = None, embed_mode: bool = False):
    """
    Main entry point for the editor. Can be run standalone or create an instance for embedding.
    """
    if _IS_STANDALONE_EXECUTION: # Double check with global flag
        try:
            # Change CWD to script's directory for standalone, helps with relative asset paths if any are missed by resource_path
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            if logger: logger.info(f"Standalone mode: Changed CWD to: {os.getcwd()}")
        except Exception as e_chdir:
            if logger: logger.error(f"Could not change CWD in standalone mode: {e_chdir}")

    if logger: logger.info(f"editor_main() called. Embed mode: {embed_mode}, Standalone context: {_IS_STANDALONE_EXECUTION}")
    
    # QApplication instance management
    app = QApplication.instance() 
    if app is None:
        if parent_app_instance: # If main game provides an app instance
            app = parent_app_instance
            if logger: logger.debug("Using parent_app_instance for QApplication in editor_main.")
        elif _IS_STANDALONE_EXECUTION: # Only create a new app if truly standalone
            app = QApplication(sys.argv)
            if logger: logger.debug("New QApplication instance created for standalone editor.")
        else: # Embedded mode but no app instance provided or existing
            if logger: logger.critical("CRITICAL: embed_mode is True, but no QApplication instance found or provided. Editor cannot run.")
            # This situation should ideally be caught by the caller of editor_main.
            # For robustness, we could raise an exception here.
            raise RuntimeError("Editor needs a QApplication instance, especially in embed_mode.")
    else:
        if logger: logger.debug("QApplication instance already exists.")

    main_window = EditorMainWindow(embed_mode=embed_mode) 

    if not embed_mode: # Standalone execution path
        exit_code = 0
        try:
            # The show() call is now inside __init__ for standalone, so this check might be redundant
            # but kept for safety if __init__ logic changes.
            if not main_window.isVisible() and not main_window._is_embedded: 
                 if logger: logger.info("Standalone editor_main: main_window was not visible from init, calling show() now.")
                 main_window.show()

            exit_code = app.exec()
            if logger: logger.info(f"QApplication event loop finished. Exit code: {exit_code}")
        except Exception as e_main_loop:
            if logger: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
            # Ensure log_file_path_for_error_msg is defined (it should be by logger setup)
            log_path_info = log_file_path_for_error_msg if 'log_file_path_for_error_msg' in globals() and log_file_path_for_error_msg else "editor_debug.log (path unknown)"
            QMessageBox.critical(None,"Editor Critical Error", f"A critical error occurred: {e_main_loop}\n\nCheck log for details:\n{log_path_info}")
            exit_code = 1 # Indicate error
        finally:
            # Save geometry on exit if standalone and window was visible
            if hasattr(main_window, 'isVisible') and main_window.isVisible(): # Check if main_window is still valid
                main_window.save_geometry_and_state() 
            if logger: logger.info("Editor session (standalone) ended.")
        return exit_code # Return the exit code from app.exec() or error code
    else: # Embed_mode path
        if logger: logger.info("EditorMainWindow instance created for embedding. Returning instance to caller.")
        return main_window # Return the instance to be embedded


if __name__ == "__main__":
    # This block is executed only when editor.py is run directly.
    # The _IS_STANDALONE_EXECUTION flag will be True.
    print("--- editor.py execution started as __main__ (standalone) ---")
    
    # Call editor_main for standalone mode. It will handle QApplication creation.
    return_code_standalone = editor_main(embed_mode=False) 
    
    print(f"--- editor.py standalone execution finished (exit code: {return_code_standalone}) ---")
    sys.exit(return_code_standalone)