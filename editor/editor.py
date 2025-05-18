# editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.2 (PySide6 Conversion - Start Maximized, Esc to Quit)
Level Editor for the Platformer Game (PySide6 Version).
Allows creating, loading, and saving game levels visually.
"""
import sys
import os
import logging
import traceback
from typing import Optional, Tuple
script_path = os.path.abspath(__file__)  # Absolute path to this script
script_dir = os.path.dirname(script_path) # Directory of this script
os.chdir(script_dir)


# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QMessageBox, QFileDialog,
    QColorDialog, QInputDialog, QLabel
)
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent # Added QKeyEvent
from PySide6.QtCore import Qt, Slot, QSettings, QTimer

# --- Logger Setup (assuming editor_logging.py is used or similar) ---
# For brevity, direct config here. In a real app, use editor_logging.py
logger = None
log_file_path_for_error_msg = "editor_qt_debug.log" # Simplified
try:
    import editor_config as ED_CONFIG
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir, 'logs')
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    log_file_path_for_error_msg = os.path.join(logs_dir, ED_CONFIG.LOG_FILE_NAME if hasattr(ED_CONFIG, "LOG_FILE_NAME") else "editor_qt_debug.log")

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler); handler.close()
    logging.basicConfig(
        level=getattr(logging, ED_CONFIG.LOG_LEVEL.upper(), logging.DEBUG) if hasattr(ED_CONFIG, "LOG_LEVEL") else logging.DEBUG,
        format=ED_CONFIG.LOG_FORMAT if hasattr(ED_CONFIG, "LOG_FORMAT") else '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')]
    )
    logger = logging.getLogger(__name__)
    logger.info("Editor session started. Logging initialized successfully.")
    print(f"LOGGING INITIALIZED. Log file at: {log_file_path_for_error_msg}")
except Exception as e_log:
    print(f"CRITICAL ERROR DURING LOGGING SETUP: {e_log}")
    traceback.print_exc()
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE LOG: %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("File logging setup failed.")
# --- End Logger Setup ---

# --- sys.path modification ---
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        if logger: logger.debug(f"Added project root '{project_root}' to sys.path.")
    if logger: logger.info(f"Project root setup in sys.path.")
except Exception as e_imp:
    if logger: logger.critical(f"Failed sys.path mod: {e_imp}", exc_info=True); sys.exit(1)
# --- End sys.path modification ---

# --- Editor module imports ---
try:
    from editor_state import EditorState
    import editor_assets
    import editor_map_utils
    import editor_history
    from map_view_widget import MapViewWidget
    from editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    if logger: logger.debug("Successfully imported all editor-specific modules.")
except ImportError as e_editor_mod:
    if logger: logger.critical(f"Failed to import an editor-specific module: {e_editor_mod}", exc_info=True)
    sys.exit(f"ImportError for editor module. Check log: {log_file_path_for_error_msg}")
# --- End Editor module imports ---

class EditorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing EditorMainWindow...")

        self.editor_state = EditorState() # Camera offset and zoom will be at default (0,0, 1.0)
        self.settings = QSettings("MyPlatformerGame", "LevelEditor_Qt")

        self.setWindowTitle("Platformer Level Editor (PySide6)")
        # Initial geometry set before maximizing, restore_geometry_and_state will override if settings exist
        self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)

        self.init_ui()
        self.create_actions()
        self.create_menus()
        self.create_status_bar()

        editor_assets.load_editor_palette_assets(self.editor_state, self)
        self.asset_palette_widget.populate_assets()
        self.update_window_title()

        if not self.restore_geometry_and_state(): # If no saved state, maximize
            self.showMaximized()
        else: # If state was restored, ensure it's visible
            self.show()


        if not editor_map_utils.ensure_maps_directory_exists():
            QMessageBox.critical(self, "Error", f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}")

        logger.info("EditorMainWindow initialized.")
        self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)


    def init_ui(self):
        logger.debug("Initializing UI components...")
        self.map_view_widget = MapViewWidget(self.editor_state, self)
        self.setCentralWidget(self.map_view_widget)

        self.asset_palette_dock = QDockWidget("Asset Palette", self)
        self.asset_palette_widget = AssetPaletteWidget(self.editor_state, self)
        self.asset_palette_dock.setWidget(self.asset_palette_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.asset_palette_dock)
        self.asset_palette_dock.setMinimumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH - 50)
        # Max width can be too restrictive, let user decide or set a larger sensible max
        # self.asset_palette_dock.setMaximumWidth(ED_CONFIG.ASSET_PALETTE_PREFERRED_WIDTH + 250)

        self.properties_editor_dock = QDockWidget("Properties", self)
        self.properties_editor_widget = PropertiesEditorDockWidget(self.editor_state, self)
        self.properties_editor_dock.setWidget(self.properties_editor_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_editor_dock)
        self.properties_editor_dock.setMinimumWidth(220)

        self.asset_palette_widget.asset_selected.connect(self.map_view_widget.on_asset_selected)
        self.asset_palette_widget.asset_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)
        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)
        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed)

        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks)
        self.map_view_widget.setFocus()
        logger.debug("UI components initialized.")

    def create_actions(self):
        logger.debug("Creating actions...")
        self.new_map_action = QAction("&New Map...", self, shortcut=QKeySequence.StandardKey.New, statusTip="Create a new map", triggered=self.new_map)
        self.load_map_action = QAction("&Load Map...", self, shortcut=QKeySequence.StandardKey.Open, statusTip="Load an existing map", triggered=self.load_map)
        self.save_map_action = QAction("&Save Map", self, shortcut=QKeySequence.StandardKey.Save, statusTip="Save the current map's editor data (.json)", triggered=self.save_map_json)
        self.export_map_action = QAction("&Export Map for Game...", self, shortcut=QKeySequence("Ctrl+E"), statusTip="Export map to game format (.py)", triggered=self.export_map_py)
        self.save_all_action = QAction("Save &All (JSON & PY)", self, shortcut=QKeySequence("Ctrl+Shift+S"), statusTip="Save editor data and export for game", triggered=self.save_all)
        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit, statusTip="Exit the editor", triggered=self.close) # close() will trigger closeEvent

        self.undo_action = QAction("&Undo", self, shortcut=QKeySequence.StandardKey.Undo, statusTip="Undo last action", triggered=self.undo)
        self.redo_action = QAction("&Redo", self, shortcut=QKeySequence.StandardKey.Redo, statusTip="Redo last undone action", triggered=self.redo)

        self.toggle_grid_action = QAction("Toggle &Grid", self, shortcut="Ctrl+G", statusTip="Show/Hide grid", triggered=self.toggle_grid, checkable=True)
        self.toggle_grid_action.setChecked(self.editor_state.show_grid) # Initialize from state
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
        self.menu_bar = self.menuBar() # Use self.menuBar() for QMainWindow

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

        view_menu = self.menu_bar.addMenu("&View")
        view_menu.addAction(self.toggle_grid_action)
        view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(self.asset_palette_dock.toggleViewAction())
        view_menu.addAction(self.properties_editor_dock.toggleViewAction())

        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog)
        help_menu.addAction(about_action)
        logger.debug("Menus created.")

    def create_status_bar(self):
        logger.debug("Creating status bar...")
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ") # Initial text
        self.map_coords_label.setMinimumWidth(250) # Give it some space
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT):
        self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")

    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        wx, wy, tx, ty, zl = coords
        self.map_coords_label.setText(f" Map:({int(wx)},{int(wy)}) Tile:({tx},{ty}) Zoom:{zl:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        if not self.editor_state.unsaved_changes: # Only log first time it becomes true for an action
            logger.debug("Map content changed, unsaved_changes set to True.")
        self.editor_state.unsaved_changes = True
        self.update_window_title()
        self.update_edit_actions_enabled_state()

    def update_window_title(self):
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
        map_is_properly_loaded_or_newly_named = bool(self.editor_state.current_json_filename or \
                                           (self.editor_state.map_name_for_function != "untitled_map" and \
                                            self.editor_state.placed_objects)) # Allow saving a new, named, non-empty map

        self.save_map_action.setEnabled(map_is_properly_loaded_or_newly_named and self.editor_state.unsaved_changes)
        self.export_map_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.save_all_action.setEnabled(map_is_properly_loaded_or_newly_named)
        self.rename_map_action.setEnabled(bool(self.editor_state.current_json_filename)) # Can only rename saved maps

        self.undo_action.setEnabled(len(self.editor_state.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.editor_state.redo_stack) > 0)
        
        # Map-dependent view/edit actions
        map_active = bool(self.editor_state.map_name_for_function != "untitled_map" or self.editor_state.placed_objects)
        self.change_bg_color_action.setEnabled(map_active)
        self.toggle_grid_action.setEnabled(map_active)
        self.zoom_in_action.setEnabled(map_active)
        self.zoom_out_action.setEnabled(map_active)
        self.zoom_reset_action.setEnabled(map_active)


    def confirm_unsaved_changes(self, action_description: str = "perform this action") -> bool:
        if self.editor_state.unsaved_changes:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         f"You have unsaved changes. Do you want to save before you {action_description}?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                return self.save_all()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

    @Slot()
    def new_map(self):
        logger.info("New Map action triggered.")
        if not self.confirm_unsaved_changes("create a new map"):
            return

        map_name, ok = QInputDialog.getText(self, "New Map", "Enter map name (e.g., level_1):")
        if ok and map_name:
            clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_map_name:
                QMessageBox.warning(self, "Invalid Name", "Map name cannot be empty after cleaning."); return
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.'] # Added dot
            if any(char in clean_map_name for char in invalid_chars):
                QMessageBox.warning(self, "Invalid Name", f"Map name '{clean_map_name}' contains invalid characters."); return

            potential_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(potential_json_path): # Only check JSON, PY is derived
                QMessageBox.warning(self, "Name Exists", f"A map JSON file named '{clean_map_name}{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION}' already exists."); return

            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):",
                                                     text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}")
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(',')
                    width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 1000) # Increased default max
                    max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 1000)
                    if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h):
                        raise ValueError(f"Dims must be >0 and <= max ({max_w}x{max_h})")

                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles)
                    self.map_view_widget.load_map_from_state()
                    self.asset_palette_widget.clear_selection()
                    self.properties_editor_widget.clear_display()
                    self.update_window_title() # Reflects new name, unsaved
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                    editor_history.push_undo_state(self.editor_state)
                    self.update_edit_actions_enabled_state()
                except ValueError as e: QMessageBox.warning(self, "Invalid Size", f"Invalid map size: {e}")
                except Exception as e_new: logger.error(f"Error creating new map: {e_new}", exc_info=True); QMessageBox.critical(self, "Error", f"Could not create new map: {e_new}")
        else: self.show_status_message("New map cancelled.")

    @Slot()
    def load_map(self):
        logger.info("Load Map action triggered.")
        if not self.confirm_unsaved_changes("load another map"): return

        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Map", ED_CONFIG.MAPS_DIRECTORY, json_filter)

        if file_path:
            if editor_map_utils.load_map_from_json(self.editor_state, file_path):
                self.map_view_widget.load_map_from_state()
                self.asset_palette_widget.clear_selection()
                self.properties_editor_widget.clear_display()
                self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state)
                self.update_edit_actions_enabled_state()
            else: QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else: self.show_status_message("Load map cancelled.")

    @Slot()
    def save_map_json(self) -> bool:
        logger.info("Save Map (JSON) action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            self.show_status_message("Map is untitled. Performing initial Save All.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
            return self.save_all()

        if editor_map_utils.save_map_to_json(self.editor_state):
            # unsaved_changes is NOT cleared here, only by export_map_py or save_all
            self.show_status_message(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename)}.")
            self.update_window_title() # Might change if it was first save and name was set
            self.update_edit_actions_enabled_state()
            return True
        else: QMessageBox.critical(self, "Save Error", "Failed to save map editor data (.json). Check logs."); return False

    @Slot()
    def export_map_py(self) -> bool:
        logger.info("Export Map (PY) action triggered.")
        if not self.editor_state.current_json_filename:
             QMessageBox.warning(self, "Cannot Export", "No map is currently loaded/saved. Save the map first (JSON)."); return False

        if editor_map_utils.export_map_to_game_python_script(self.editor_state):
            self.editor_state.unsaved_changes = False
            self.update_window_title()
            self.update_edit_actions_enabled_state()
            self.show_status_message(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename)}.")
            return True
        else: QMessageBox.critical(self, "Export Error", "Failed to export map for game (.py). Check logs."); return False

    @Slot()
    def save_all(self) -> bool:
        logger.info("Save All action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            map_name, ok = QInputDialog.getText(self, "Save Map As", "Enter map name for saving all files:")
            if ok and map_name:
                clean_map_name = map_name.strip().lower().replace(" ", "_").replace("-", "_")
                if not clean_map_name or any(c in clean_map_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']):
                    QMessageBox.warning(self, "Invalid Name", "Map name is invalid or empty."); return False
                self.editor_state.map_name_for_function = clean_map_name
                json_fn = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
                py_fn = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
                self.editor_state.current_json_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_fn)
                self.editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_fn)
                self.update_window_title()
            else: self.show_status_message("Save All cancelled: map name not provided."); return False

        if self.save_map_json():
            if self.export_map_py(): # This will set unsaved_changes to False
                self.show_status_message("Map saved (JSON & PY).")
                return True
        self.show_status_message("Save All failed. Check logs."); return False

    @Slot()
    def rename_map(self):
        # ... (Rename logic remains complex, ensure it calls save_map_to_json and export_map_to_game_python_script
        #      with the new name, and updates editor_state correctly. The previous version's logic for rename was okay.)
        logger.info("Rename Map action triggered.")
        if not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Rename Map", "No map is currently loaded to rename.")
            return

        old_base_name = self.editor_state.map_name_for_function
        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"Enter new name for '{old_base_name}':", text=old_base_name)

        if ok and new_name_str:
            clean_new_name = new_name_str.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_new_name or any(c in clean_new_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']):
                QMessageBox.warning(self, "Invalid Name", "New map name is invalid or empty."); return
            if clean_new_name == old_base_name:
                self.show_status_message("Rename cancelled: name unchanged."); return

            new_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_new_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(new_json_path) and os.path.normcase(new_json_path) != os.path.normcase(self.editor_state.current_json_filename):
                QMessageBox.warning(self, "Rename Error", f"A map JSON file named '{clean_new_name}{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION}' already exists."); return

            old_json_path = self.editor_state.current_json_filename
            old_py_path = self.editor_state.current_map_filename # Path based on old name
            new_py_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, clean_new_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)

            try:
                logger.info(f"Attempting to rename '{old_base_name}' to '{clean_new_name}'.")
                # 1. Rename JSON file on disk
                if old_json_path and os.path.exists(old_json_path):
                    os.rename(old_json_path, new_json_path)
                
                # 2. Update editor_state to new name BEFORE saving/exporting
                self.editor_state.map_name_for_function = clean_new_name
                self.editor_state.current_json_filename = new_json_path
                self.editor_state.current_map_filename = new_py_path # For export target

                # 3. Save the (potentially modified) content to the NEW JSON file, with NEW internal name
                if not editor_map_utils.save_map_to_json(self.editor_state):
                    QMessageBox.critical(self, "Rename Error", "Failed to save content to new JSON file. Operation aborted."); return
                
                # 4. Delete old PY file (if it exists)
                if old_py_path and os.path.exists(old_py_path) and os.path.normcase(old_py_path) != os.path.normcase(new_py_path):
                    os.remove(old_py_path)
                    logger.info(f"Old PY file '{os.path.basename(old_py_path)}' deleted.")

                # 5. Export to new PY file (this also sets unsaved_changes to False)
                if editor_map_utils.export_map_to_game_python_script(self.editor_state):
                    self.show_status_message(f"Map renamed to '{clean_new_name}' and all files updated.")
                else:
                    QMessageBox.warning(self, "Rename Warning", "Map files renamed, JSON updated, but new PY export failed. Please Save All manually.")
                    self.editor_state.unsaved_changes = True # Mark as unsaved due to export fail

                self.update_window_title()
                self.update_edit_actions_enabled_state()

            except Exception as e_rename:
                logger.error(f"Error during rename process: {e_rename}", exc_info=True)
                QMessageBox.critical(self, "Rename Error", f"An error occurred: {e_rename}")
                # Potentially try to revert filenames if complex error, or guide user.
        else: self.show_status_message("Rename map cancelled.")

    @Slot()
    def delete_map_file(self):
        # ... (Delete logic similar to before, ensure it handles current map state if deleted map was active) ...
        logger.info("Delete Map File action triggered.")
        json_filter = f"Editor Map Files (*{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Map to Delete", ED_CONFIG.MAPS_DIRECTORY, json_filter)

        if file_path:
            map_name_to_delete = os.path.splitext(os.path.basename(file_path))[0]
            reply = QMessageBox.warning(self, "Confirm Delete",
                                        f"Are you sure you want to permanently delete all files for map '{map_name_to_delete}'?\nThis cannot be undone.",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state, file_path):
                    self.show_status_message(f"Map '{map_name_to_delete}' files deleted.")
                    if self.editor_state.current_json_filename and \
                       os.path.normcase(self.editor_state.current_json_filename) == os.path.normcase(file_path):
                        self.editor_state.reset_map_context()
                        self.map_view_widget.load_map_from_state() # Will effectively clear and show empty state
                        self.asset_palette_widget.clear_selection()
                        self.properties_editor_widget.clear_display()
                        self.update_window_title()
                        self.update_edit_actions_enabled_state()
                else: QMessageBox.critical(self, "Delete Error", f"Failed to delete files for '{map_name_to_delete}'. Check logs.")
            else: self.show_status_message("Delete map cancelled.")
        else: self.show_status_message("Delete map selection cancelled.")


    @Slot()
    def undo(self):
        logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state): # undo now returns bool
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            # If properties panel was showing an object that might have changed/disappeared, refresh it
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem): # type: ignore
                 self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else:
                 self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful.")
            self.update_window_title() # Unsaved changes flag is set in editor_history
        else: self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self):
        logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state): # redo now returns bool
            self.map_view_widget.load_map_from_state()
            self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem): # type: ignore
                 self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else:
                 self.properties_editor_widget.clear_display()
            self.show_status_message("Redo successful.")
            self.update_window_title()
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
            if not self.editor_state.placed_objects: # No map data at all
                 QMessageBox.information(self, "Change Background Color", "Please load or create a map first.")
                 return

        current_qcolor = QColor(*self.editor_state.background_color)
        new_q_color = QColorDialog.getColor(current_qcolor, self, "Select Background Color")

        if new_q_color.isValid():
            self.editor_state.background_color = (new_q_color.red(), new_q_color.green(), new_q_color.blue())
            self.map_view_widget.update_background_color()
            self.handle_map_content_changed()
            self.show_status_message(f"Background color changed to {self.editor_state.background_color}.")
        else: self.show_status_message("Background color change cancelled.")

    @Slot()
    def about_dialog(self):
        QMessageBox.about(self, "About Platformer Level Editor",
                          "Platformer Level Editor (PySide6 Version)\n\n"
                          "Create and edit levels for your platformer game.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle global key presses, like Escape to quit."""
        if event.key() == Qt.Key.Key_Escape:
            logger.info("Escape key pressed, attempting to close window.")
            self.close() # This will trigger closeEvent for confirmation
            event.accept()
        else:
            super().keyPressEvent(event) # Pass to children or default handling

    def closeEvent(self, event): # event is QCloseEvent
        logger.info("Close event triggered for main window.")
        if self.confirm_unsaved_changes("exit the editor"):
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            logger.info("Window geometry and state saved.")
            event.accept()
        else:
            event.ignore()

    def save_geometry_and_state(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and state explicitly saved.")

    def restore_geometry_and_state(self) -> bool:
        geom = self.settings.value("geometry")
        state = self.settings.value("windowState")
        restored = False
        if geom:
            self.restoreGeometry(geom); restored = True
        if state:
            self.restoreState(state); restored = True
        if restored: logger.debug("Window geometry and/or state restored.")
        return restored


def editor_main():
    logger.info("editor_main() started for PySide6 application.")
    app = QApplication.instance()
    if app is None: app = QApplication(sys.argv); logger.debug("QApplication instance created.")
    else: logger.debug("QApplication instance already exists.")

    main_window = EditorMainWindow()
    # main_window.show() # Show is called after restore_geometry_and_state or showMaximized

    exit_code = 0
    try:
        exit_code = app.exec()
        logger.info(f"QApplication event loop finished with exit code: {exit_code}")
    except Exception as e_main_loop:
        logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
        QMessageBox.critical(None,"Editor Critical Error", f"{e_main_loop}\n\nCheck log:\n{log_file_path_for_error_msg}")
        exit_code = 1
    finally:
        if main_window.isVisible(): # Ensure settings are saved if window still exists
            main_window.save_geometry_and_state()
        logger.info("Editor session ended.")
    return exit_code


if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---")
    return_code = editor_main()
    print(f"--- editor.py execution finished (exit code: {return_code}) ---")
    sys.exit(return_code)