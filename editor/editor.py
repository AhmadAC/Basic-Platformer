# editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.1 (PySide6 Conversion - No Tooltips)
Level Editor for the Platformer Game (PySide6 Version).
Allows creating, loading, and saving game levels visually.
"""
import sys
import os
import logging
import traceback
from typing import Optional, Tuple

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, QFileDialog,
    QColorDialog, QInputDialog, QLabel
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen
from PySide6.QtCore import Qt, Slot, QSettings, QTimer

# --- Logger Setup ---
logger = None
log_file_path_for_error_msg = "Not determined"
try:
    import editor_config as ED_CONFIG # For LOG_LEVEL, LOG_FORMAT, LOG_FILE_NAME
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir, 'logs')
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    log_file_path_for_error_msg = os.path.join(logs_dir, ED_CONFIG.LOG_FILE_NAME)

    # Clear previous handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()

    logging.basicConfig(
        level=getattr(logging, ED_CONFIG.LOG_LEVEL.upper(), logging.DEBUG),
        format=ED_CONFIG.LOG_FORMAT,
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')]
    )
    logger = logging.getLogger(__name__)
    logger.info("Editor session started. Logging initialized successfully.")
    print(f"LOGGING INITIALIZED. Log file at: {log_file_path_for_error_msg}")
except Exception as e_log:
    print(f"CRITICAL ERROR DURING LOGGING SETUP: {e_log}")
    traceback.print_exc()
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE LOG (File log failed): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("File logging setup failed. Switched to console logging for this session.")
# --- End Logger Setup ---

# --- sys.path modification and constants import ---
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        if logger: logger.debug(f"Added project root '{project_root}' to sys.path.")
    # import constants as C_imported # No longer directly needed in editor.py, but other modules might
    if logger: logger.info(f"Project root added to sys.path.")
except Exception as e_imp:
    if logger: logger.critical(f"Failed during sys.path modification. Error: {e_imp}", exc_info=True)
    sys.exit("Error setting up sys.path.")
# --- End sys.path modification ---

# --- Editor module imports ---
try:
    # editor_config already imported for logging
    from editor_state import EditorState
    import editor_assets
    import editor_map_utils
    import editor_history
    from map_view_widget import MapViewWidget
    from editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    if logger: logger.debug("Successfully imported all editor-specific modules.")
except ImportError as e_editor_mod:
    if logger: logger.critical(f"Failed to import an editor-specific module. Error: {e_editor_mod}", exc_info=True)
    sys.exit(f"ImportError for editor module - exiting. Check {log_file_path_for_error_msg} for details.")
# --- End Editor module imports ---

class EditorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing EditorMainWindow...")

        self.editor_state = EditorState()
        self.settings = QSettings("MyPlatformerGame", "LevelEditor") # For saving window state

        self.setWindowTitle("Platformer Level Editor (PySide6)")
        self.setGeometry(
            100, 100,
            ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH,
            ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT
        )
        # Center window on screen
        center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())


        self.init_ui()
        self.create_actions()
        self.create_menus()
        self.create_status_bar()

        # Load assets (needs QPixmap, so QApplication must exist)
        editor_assets.load_editor_palette_assets(self.editor_state, self) # Pass self if needed by asset loader for context

        self.asset_palette_widget.populate_assets()
        self.update_window_title()

        # Restore window state
        self.restore_geometry_and_state()

        # Initial check for maps directory
        if not editor_map_utils.ensure_maps_directory_exists():
            QMessageBox.critical(self, "Error", f"Could not create or access maps directory: {ED_CONFIG.MAPS_DIRECTORY}")
            # Consider closing or disabling map operations

        logger.info("EditorMainWindow initialized.")
        self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)


    def init_ui(self):
        logger.debug("Initializing UI components...")
        # --- Central Widget (Map View) ---
        self.map_view_widget = MapViewWidget(self.editor_state, self)
        self.setCentralWidget(self.map_view_widget)

        # --- Asset Palette Dock ---
        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self)
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50)
        self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 150)


        # --- Properties Editor Dock ---
        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self)
        self.properties_editor_dock.setWidget(self.properties_editor_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_editor_dock)
        self.properties_editor_dock.setMinimumWidth(200)

        # Connect signals from palette to map view and properties editor
        self.asset_palette_widget.asset_selected.connect(self.map_view_widget.on_asset_selected)
        self.asset_palette_widget.asset_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)

        # Connect signals from map view (e.g., when an object is selected on map for properties)
        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)

        # Connect signal from properties editor back to map view if properties change
        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed)

        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks)

        # Initial focus
        self.map_view_widget.setFocus()
        logger.debug("UI components initialized.")


    def create_actions(self):
        logger.debug("Creating actions...")
        self.new_map_action = QAction("&New Map...", self, shortcut=QKeySequence.StandardKey.New, statusTip="Create a new map", triggered=self.new_map)
        self.load_map_action = QAction("&Load Map...", self, shortcut=QKeySequence.StandardKey.Open, statusTip="Load an existing map", triggered=self.load_map)
        self.save_map_action = QAction("&Save Map", self, shortcut=QKeySequence.StandardKey.Save, statusTip="Save the current map's editor data (.json)", triggered=self.save_map_json)
        self.export_map_action = QAction("&Export Map for Game...", self, shortcut=QKeySequence("Ctrl+E"), statusTip="Export map to game format (.py)", triggered=self.export_map_py)
        self.save_all_action = QAction("Save &All (JSON & PY)", self, shortcut=QKeySequence("Ctrl+Shift+S"), statusTip="Save editor data and export for game", triggered=self.save_all)
        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit, statusTip="Exit the editor", triggered=self.close)

        self.undo_action = QAction("&Undo", self, shortcut=QKeySequence.StandardKey.Undo, statusTip="Undo last action", triggered=self.undo)
        self.redo_action = QAction("&Redo", self, shortcut=QKeySequence.StandardKey.Redo, statusTip="Redo last undone action", triggered=self.redo)

        self.toggle_grid_action = QAction("Toggle &Grid", self, shortcut="Ctrl+G", statusTip="Show/Hide grid", triggered=self.toggle_grid, checkable=True, checked=self.editor_state.show_grid)
        self.change_bg_color_action = QAction("Change &Background Color...", self, statusTip="Change map background color", triggered=self.change_background_color)

        self.zoom_in_action = QAction("Zoom &In", self, shortcut=QKeySequence.StandardKey.ZoomIn, statusTip="Zoom in on the map", triggered=self.map_view_widget.zoom_in)
        self.zoom_out_action = QAction("Zoom &Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, statusTip="Zoom out of the map", triggered=self.map_view_widget.zoom_out)
        self.zoom_reset_action = QAction("Reset &Zoom", self, shortcut="Ctrl+0", statusTip="Reset map zoom to 100%", triggered=self.map_view_widget.reset_zoom)

        self.rename_map_action = QAction("&Rename Current Map...", self, statusTip="Rename the current map's files", triggered=self.rename_map)
        self.delete_map_file_action = QAction("&Delete Map File...", self, statusTip="Delete a map's .json and .py files", triggered=self.delete_map_file)

        self.update_edit_actions_enabled_state()
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
        file_menu.addAction(self.exit_action)

        edit_menu = self.menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.change_bg_color_action)
        # Add more edit actions (copy, paste, select all) if implemented

        view_menu = self.menu_bar.addMenu("&View")
        view_menu.addAction(self.toggle_grid_action)
        view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        # Add dock widget view toggles
        view_menu.addAction(self.asset_palette_dock.toggleViewAction())
        view_menu.addAction(self.properties_editor_dock.toggleViewAction())

        # Tools menu (can be populated by tools from asset palette or specific editor tools)
        # tools_menu = self.menu_bar.addMenu("&Tools")

        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog)
        help_menu.addAction(about_action)
        logger.debug("Menus created.")

    def create_status_bar(self):
        logger.debug("Creating status bar...")
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT) # Initial message
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) ")
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT):
        self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")

    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        # coords expected to be (world_x, world_y, tile_x, tile_y, zoom_level)
        wx, wy, tx, ty, zl = coords
        self.map_coords_label.setText(f" Map:({int(wx)},{int(wy)}) Tile:({tx},{ty}) Zoom:{zl:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        self.editor_state.unsaved_changes = True
        self.update_window_title()
        self.update_edit_actions_enabled_state() # Update undo/redo availability
        logger.debug("Map content changed, unsaved_changes set to True.")

    def update_window_title(self):
        title = "Platformer Level Editor (PySide6)"
        if self.editor_state.map_name_for_function and self.editor_state.map_name_for_function != "untitled_map":
            title += f" - {self.editor_state.map_name_for_function}"
            if self.editor_state.current_json_filename:
                 title += f" [{os.path.basename(self.editor_state.current_json_filename)}]"
        if self.editor_state.unsaved_changes:
            title += "*"
        self.setWindowTitle(title)

    def update_edit_actions_enabled_state(self):
        map_loaded = bool(self.editor_state.current_json_filename)
        self.save_map_action.setEnabled(map_loaded and self.editor_state.unsaved_changes)
        self.export_map_action.setEnabled(map_loaded)
        self.save_all_action.setEnabled(map_loaded) # Could also check unsaved_changes
        self.rename_map_action.setEnabled(map_loaded)

        self.undo_action.setEnabled(len(self.editor_state.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack) > 0)
        self.change_bg_color_action.setEnabled(map_loaded)
        self.toggle_grid_action.setEnabled(map_loaded)
        self.zoom_in_action.setEnabled(map_loaded)
        self.zoom_out_action.setEnabled(map_loaded)
        self.zoom_reset_action.setEnabled(map_loaded)


    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool:
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Do you want to save before you " + action_description + "?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                return self.save_all() # Returns True if save successful
            elif reply == QMessageBox.StandardButton.Cancel:
                return False # User cancelled
            # If Discard, proceed (return True)
        return True # No unsaved changes, or user chose to discard

    @Slot()
    def new_map(self):
        logger.info("New Map action triggered.")
        if not self.confirm_unsaved_changes("create a new map"):
            return

        map_name, ok = QInputDialog.getText(self, "New Map", "Enter map name (e.g., level_1):")
        if ok and map_name:
            clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_map_name:
                QMessageBox.warning(self, "Invalid Name", "Map name cannot be empty after cleaning.")
                return
            
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in clean_map_name for char in invalid_chars):
                QMessageBox.warning(self, "Invalid Name", f"Map name '{clean_map_name}' contains invalid characters.")
                return

            potential_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            potential_py_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)
            if os.path.exists(potential_json_path) or os.path.exists(potential_py_path):
                QMessageBox.warning(self, "Name Exists", f"A map named '{clean_map_name}' already exists.")
                return

            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):",
                                                     text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}")
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(',')
                    width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 500)
                    max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 500)
                    if not (width_tiles > 0 and height_tiles > 0 and width_tiles <= max_w and height_tiles <= max_h):
                        raise ValueError(f"Dimensions must be >0 and <= max ({max_w}x{max_h})")

                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles)
                    self.map_view_widget.load_map_from_state() # Update QGraphicsScene
                    self.asset_palette_widget.clear_selection() # Deselect any asset
                    self.properties_editor_widget.clear_display() # Clear properties
                    self.update_window_title()
                    self.update_edit_actions_enabled_state()
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                    # New map is unsaved by definition
                    self.editor_state.unsaved_changes = True
                    editor_history.push_undo_state(self.editor_state) # Initial state for undo
                    self.update_edit_actions_enabled_state()

                except ValueError as e:
                    QMessageBox.warning(self, "Invalid Size", f"Invalid map size format: {e}")
                except Exception as e_new:
                    logger.error(f"Error creating new map: {e_new}", exc_info=True)
                    QMessageBox.critical(self, "Error", f"Could not create new map: {e_new}")
        else:
            self.show_status_message("New map cancelled.")

    @Slot()
    def load_map(self):
        logger.info("Load Map action triggered.")
        if not self.confirm_unsaved_changes("load another map"):
            return

        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Map", ED_CONFIG.MAPS_DIRECTORY, json_filter)

        if file_path:
            if editor_map_utils.load_map_from_json(self.editor_state, file_path):
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.properties_editor_widget.clear_display()
                self.update_window_title()
                # load_map_from_json now handles unsaved_changes based on auto-correction
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state) # Initial loaded state for undo
                self.update_edit_actions_enabled_state()
            else:
                QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else:
            self.show_status_message("Load map cancelled.")

    @Slot()
    def save_map_json(self) -> bool:
        logger.info("Save Map (JSON) action triggered.")
        if not self.editor_state.current_json_filename: # Should not happen if map is loaded/new and named
            # This could happen if a new map was created but not yet saved for the first time.
            # Prompt for a name if it's an "untitled_map" or no JSON filename is set.
            if self.editor_state.map_name_for_function == "untitled_map" or not self.editor_state.current_json_filename:
                self.show_status_message("Map is untitled. Performing initial Save All.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                return self.save_all() # Trigger save_all to get name and save both files

        if editor_map_utils.save_map_to_json(self.editor_state):
            # JSON save doesn't clear unsaved_changes; only export or save_all does
            self.show_status_message(f"Map editor data saved to {os.path.basename(self.editor_state.current_json_filename)}.")
            self.update_window_title() # Title might change if it was first save
            self.update_edit_actions_enabled_state()
            return True
        else:
            QMessageBox.critical(self, "Save Error", "Failed to save map editor data (.json). Check logs.")
            return False

    @Slot()
    def export_map_py(self) -> bool:
        logger.info("Export Map (PY) action triggered.")
        if not self.editor_state.current_json_filename: # Implying map is not properly loaded/saved
             QMessageBox.warning(self, "Cannot Export", "No map is currently loaded or saved with a name. Save the map first.")
             return False

        if editor_map_utils.export_map_to_game_python_script(self.editor_state):
            self.editor_state.unsaved_changes = False # Exporting clears this
            self.update_window_title()
            self.update_edit_actions_enabled_state()
            self.show_status_message(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename)}.")
            return True
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export map for game (.py). Check logs.")
            return False

    @Slot()
    def save_all(self) -> bool:
        logger.info("Save All action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            # If map is new and unnamed, need to get a name first
            map_name, ok = QInputDialog.getText(self, "Save Map As", "Enter map name for saving files:")
            if ok and map_name:
                clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
                if not clean_map_name:
                    QMessageBox.warning(self, "Invalid Name", "Map name cannot be empty.")
                    return False
                # Update editor_state with the new name to proceed with saving
                self.editor_state.map_name_for_function = clean_map_name
                # Derive and set current_json_filename and current_map_filename
                json_fn = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
                py_fn = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
                self.editor_state.current_json_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_fn)
                self.editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_fn)
                self.update_window_title() # Reflect new name immediately
            else:
                self.show_status_message("Save All cancelled: map name not provided.")
                return False

        if self.save_map_json():
            if self.export_map_py():
                self.show_status_message("Map saved (JSON & PY).")
                return True
        self.show_status_message("Save All failed. Check logs.")
        return False

    @Slot()
    def rename_map(self):
        logger.info("Rename Map action triggered.")
        if not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Rename Map", "No map is currently loaded to rename.")
            return

        old_base_name = self.editor_state.map_name_for_function
        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"Enter new name for '{old_base_name}':", text=old_base_name)

        if ok and new_name_str:
            # --- This logic should ideally be in editor_map_utils.rename_map_files ---
            # --- Simplified here for brevity, but robust path/name handling is crucial ---
            # For a full implementation, you'd call a utility function that handles
            # renaming both .json and .py, updating internal JSON content, and re-exporting.
            # The Pygame version's _handle_rename_get_new_name has this complex logic.

            clean_new_name = new_name_str.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_new_name:
                QMessageBox.warning(self, "Invalid Name", "New name cannot be empty after cleaning.")
                return
            if clean_new_name == old_base_name:
                self.show_status_message("Rename cancelled: name unchanged.")
                return

            # Check for existing files with the new name (simplified)
            new_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_new_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(new_json_path):
                QMessageBox.warning(self, "Rename Error", f"A map named '{clean_new_name}' already exists.")
                return

            # Perform rename (conceptual - needs full implementation from editor_map_utils)
            # This would involve:
            # 1. os.rename for JSON
            # 2. os.rename for PY (if exists)
            # 3. Update map_name_for_function in the new JSON file's content
            # 4. Update editor_state with new names
            # 5. Re-export PY with new internal name

            # Placeholder for actual rename logic:
            old_json_path = self.editor_state.current_json_filename
            old_py_path = self.editor_state.current_map_filename
            new_py_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_new_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)

            try:
                logger.info(f"Attempting to rename '{old_base_name}' to '{clean_new_name}'.")
                # This is where you'd call a more robust rename function from editor_map_utils
                # For now, simulate part of it:
                if os.path.exists(old_json_path): os.rename(old_json_path, new_json_path)
                if old_py_path and os.path.exists(old_py_path): os.rename(old_py_path, new_py_path)

                self.editor_state.map_name_for_function = clean_new_name
                self.editor_state.current_json_filename = new_json_path
                self.editor_state.current_map_filename = new_py_path

                # Re-save JSON with updated internal name and re-export PY
                if editor_map_utils.save_map_to_json(self.editor_state): # Saves with new name internally
                    if editor_map_utils.export_map_to_game_python_script(self.editor_state): # Exports with new name
                        self.show_status_message(f"Map renamed to '{clean_new_name}'.")
                        self.editor_state.unsaved_changes = False
                    else:
                        QMessageBox.warning(self, "Rename Warning", "Map files renamed, but PY export failed. Please Save All.")
                        self.editor_state.unsaved_changes = True
                else:
                    QMessageBox.warning(self, "Rename Error", "Failed to update renamed JSON file.")
                    self.editor_state.unsaved_changes = True


                self.update_window_title()
                self.update_edit_actions_enabled_state()

            except Exception as e_rename:
                logger.error(f"Error during rename process: {e_rename}", exc_info=True)
                QMessageBox.critical(self, "Rename Error", f"An error occurred: {e_rename}")
                # Attempt to revert state if possible, or guide user.
        else:
            self.show_status_message("Rename map cancelled.")


    @Slot()
    def delete_map_file(self):
        logger.info("Delete Map File action triggered.")
        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Map to Delete", ED_CONFIG.MAPS_DIRECTORY, json_filter)

        if file_path:
            map_name_to_delete = os.path.splitext(os.path.basename(file_path))[0]
            reply = QMessageBox.warning(self, "Confirm Delete",
                                        f"Are you sure you want to permanently delete all files for map '{map_name_to_delete}'?\n({os.path.basename(file_path)} and corresponding .py)",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state, file_path): # editor_state for status messages
                    self.show_status_message(f"Map '{map_name_to_delete}' files deleted.")
                    # If the deleted map was the one currently loaded
                    if self.editor_state.current_json_filename and \
                       os.path.normcase(self.editor_state.current_json_filename) == os.path.normcase(file_path):
                        self.editor_state.reset_map_context()
                        self.map_view_widget.clear_scene()
                        self.asset_palette_widget.clear_selection()
                        self.properties_editor_widget.clear_display()
                        self.update_window_title()
                        self.update_edit_actions_enabled_state()
                else:
                    QMessageBox.critical(self, "Delete Error", f"Failed to delete map files for '{map_name_to_delete}'. Check logs.")
            else:
                self.show_status_message("Delete map cancelled.")
        else:
            self.show_status_message("Delete map selection cancelled.")


    @Slot()
    def undo(self):
        logger.info("Undo action triggered.")
        if self.editor_state.undo_stack:
            editor_history.undo(self.editor_state)
            self.map_view_widget.load_map_from_state() # Refresh map view
            self.update_edit_actions_enabled_state()
            self.show_status_message("Undo successful.")
            self.editor_state.unsaved_changes = True # Undoing is a change
            self.update_window_title()
        else:
            self.show_status_message("Nothing to undo.")

    @Slot()
    def redo(self):
        logger.info("Redo action triggered.")
        if self.editor_state.redo_stack:
            editor_history.redo(self.editor_state)
            self.map_view_widget.load_map_from_state() # Refresh map view
            self.update_edit_actions_enabled_state()
            self.show_status_message("Redo successful.")
            self.editor_state.unsaved_changes = True # Redoing is a change
            self.update_window_title()
        else:
            self.show_status_message("Nothing to redo.")

    @Slot()
    def toggle_grid(self):
        self.editor_state.show_grid = not self.editor_state.show_grid
        self.toggle_grid_action.setChecked(self.editor_state.show_grid)
        self.map_view_widget.update_grid_visibility()
        self.show_status_message(f"Grid {'ON' if self.editor_state.show_grid else 'OFF'}.")
        # Toggling grid is a visual preference, not an unsaved change to map data itself.

    @Slot()
    def change_background_color(self):
        if not self.editor_state.current_json_filename: # Ensure a map is loaded
            QMessageBox.information(self, "Change Background Color", "Please load or create a map first.")
            return

        current_qcolor = QColor(*self.editor_state.background_color)
        new_qcolor = QColorDialog.getColor(current_qcolor, self, "Select Background Color")

        if new_qcolor.isValid():
            self.editor_state.background_color = (new_qcolor.red(), new_qcolor.green(), new_qcolor.blue())
            self.map_view_widget.update_background_color()
            self.handle_map_content_changed() # BG color is part of map data
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else:
            self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self):
        QMessageBox.about(self, "About Platformer Level Editor",
                          "Platformer Level Editor (PySide6 Version)\n\n"
                          "Create and edit levels for your platformer game.")

    def closeEvent(self, event):
        logger.info("Close event triggered.")
        if self.confirm_unsaved_changes("exit the editor"):
            # Save window state
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            logger.info("Window geometry and state saved.")
            event.accept() # Proceed with closing
        else:
            event.ignore() # User cancelled closing

    def save_geometry_and_state(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and state explicitly saved via method call.")

    def restore_geometry_and_state(self):
        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        logger.debug("Window geometry and state restored.")


def editor_main():
    logger.info("editor_main() started for PySide6 application.")
    # QApplication instance should be created only once.
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        logger.debug("QApplication instance created.")
    else:
        logger.debug("QApplication instance already exists.")

    # Apply a basic style (optional)
    # app.setStyle("Fusion")
    # Or load a stylesheet
    # try:
    #     with open("stylesheet.qss", "r") as f:
    #         app.setStyleSheet(f.read())
    # except FileNotFoundError:
    #     logger.warning("stylesheet.qss not found. Using default style.")


    main_window = EditorMainWindow()
    main_window.show()

    exit_code = 0
    try:
        exit_code = app.exec()
        logger.info(f"QApplication event loop finished with exit code: {exit_code}")
    except Exception as e_main_loop:
        logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
        # Fallback error display if logging to file fails or isn't visible
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setText("A critical error occurred in the editor.")
        error_dialog.setInformativeText(f"{e_main_loop}\n\nCheck the log file for details:\n{log_file_path_for_error_msg}")
        error_dialog.setWindowTitle("Editor Critical Error")
        error_dialog.exec() # Show modal error dialog
        exit_code = 1 # Indicate error
    finally:
        # Make sure settings are saved if window closes unexpectedly
        if main_window.isVisible(): # Check if it was closed normally or crashed
            main_window.save_geometry_and_state()

        logger.info("Editor session ended.")
    return exit_code


if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---")
    # Ensure Pygame is not initialized if it's not needed for UI
    # (It might still be used by editor_config for font loading, or by assets for some fallback)
    # If Pygame is strictly for non-UI, its init might be fine.
    # If it tries to create a display, it can conflict with Qt.
    # pygame.quit() # Ensure Pygame display is not active if previously initialized
    return_code = editor_main()
    print(f"--- editor.py execution finished (exit code: {return_code}) ---")
    sys.exit(return_code)