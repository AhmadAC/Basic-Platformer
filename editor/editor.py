# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 2.0.6 (Minimap docking order corrected)
## version 2.0.7 (Hide level_default from editor interactions)
## version 2.0.8 (Allow full editing of level_default in editor, still hidden from game UI)
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
from PySide6.QtGui import QAction, QKeySequence, QColor, QPalette, QScreen, QKeyEvent, QImage, QPainter
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, QRectF

# --- Logger Setup ---
logger = None
log_file_path_for_error_msg = "editor_qt_debug.log" # Default, might be overridden
try:
    from . import editor_config as ED_CONFIG # Use relative import
    current_script_dir_for_logs = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir_for_logs, 'logs')
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    log_file_path_for_error_msg = os.path.join(logs_dir, ED_CONFIG.LOG_FILE_NAME if hasattr(ED_CONFIG, "LOG_FILE_NAME") else "editor_qt_debug.log")

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close() 

    logging.basicConfig(
        level=getattr(logging, ED_CONFIG.LOG_LEVEL.upper(), logging.DEBUG) if hasattr(ED_CONFIG, "LOG_LEVEL") else logging.DEBUG,
        format=ED_CONFIG.LOG_FORMAT if hasattr(ED_CONFIG, "LOG_FORMAT") else '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')]
    )
    logger = logging.getLogger(__name__)
    logger.info("Editor session started. Logging initialized successfully.")
except Exception as e_log:
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE FALLBACK: %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__) 
    logger.error(f"CRITICAL ERROR DURING FILE LOGGING SETUP (editor.py): {e_log}. Using console.", exc_info=True)
# --- End Logger Setup ---

# --- sys.path modification ---
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        if logger: logger.debug(f"Added project root '{project_root}' to sys.path for editor.py context.")
    if logger: logger.info(f"Project root '{project_root}' setup in sys.path (from editor.py). Current sys.path[0]: {sys.path[0]}")
except Exception as e_imp:
    if logger: logger.critical(f"Failed sys.path modification in editor.py: {e_imp}", exc_info=True)
# --- End sys.path modification ---

# --- Editor module imports ---
try:
    from .editor_state import EditorState
    from . import editor_assets
    from . import editor_map_utils
    from . import editor_history
    from .map_view_widget import MapViewWidget, MapObjectItem
    from .editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
    if ED_CONFIG.MINIMAP_ENABLED: 
        from .minimap_widget import MinimapWidget
    if logger: logger.debug("Successfully imported all editor-specific modules (using relative imports).")
except ImportError as e_editor_mod_rel:
    if logger: logger.warning(f"Relative import failed for editor modules: {e_editor_mod_rel}. Trying absolute...")
    try:
        from editor_state import EditorState
        import editor_assets 
        import editor_map_utils
        import editor_history
        from map_view_widget import MapViewWidget, MapObjectItem
        from editor_ui_panels import AssetPaletteWidget, PropertiesEditorDockWidget
        if ED_CONFIG.MINIMAP_ENABLED: 
             from minimap_widget import MinimapWidget
        if logger: logger.debug("Successfully imported all editor-specific modules (using absolute imports as fallback).")
    except ImportError as e_editor_mod_abs:
        if logger: logger.critical(f"Failed to import an editor-specific module (both relative and absolute): {e_editor_mod_abs}", exc_info=True)
        # Avoid showing QMessageBox if no QApplication instance exists (e.g., during early import failures)
        app_instance_exists = isinstance(QApplication.instance(), QApplication)
        if app_instance_exists:
            QMessageBox.critical(None, "Editor Import Error", f"Failed to import critical editor module: {e_editor_mod_abs}\n\nCheck log: {log_file_path_for_error_msg}")
        sys.exit(f"ImportError for editor module. Check log: {log_file_path_for_error_msg}")
except AttributeError as e_attr_edcfg: 
    if logger: logger.critical(f"AttributeError related to ED_CONFIG: {e_attr_edcfg}. ED_CONFIG might not be fully loaded.", exc_info=True)
    app_instance_exists = isinstance(QApplication.instance(), QApplication)
    if app_instance_exists:
        QMessageBox.critical(None, "Editor Config Error", f"Configuration error: {e_attr_edcfg}\n\nCheck log: {log_file_path_for_error_msg}")
    sys.exit(f"Configuration error. Check log: {log_file_path_for_error_msg}")
# --- End Editor module imports ---


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
                logger.info("Standalone mode: No saved geometry/state or restoration failed, showing maximized.")
                self.showMaximized()
            else:
                logger.info("Standalone mode: Restored geometry/state, showing window.")
                self.show()
        else:
            logger.info("Embedded mode: EditorMainWindow will not show itself. Parent is responsible.")
            # Still try to restore state (dock positions etc.) even if not showing the main window itself.
            self.restore_geometry_and_state()


        if not editor_map_utils.ensure_maps_directory_exists():
            if not self._is_embedded: 
                QMessageBox.critical(self, "Error", f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY}")
            else:
                logger.error(f"Maps directory issue: {ED_CONFIG.MAPS_DIRECTORY} (Embedded mode, no QMessageBox)")

        logger.info("EditorMainWindow initialized.")
        # Ensure status bar exists before showing message if it's created conditionally
        if hasattr(self, 'status_bar') and self.status_bar:
            self.show_status_message("Editor started. Welcome!", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
        else:
            logger.info("Status: Editor started. Welcome! (Status bar not yet available or not used in this context).")


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
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock) 
            self.splitDockWidget(self.minimap_dock, self.properties_editor_dock, Qt.Orientation.Vertical) 
            self.minimap_dock.setFixedHeight(ED_CONFIG.MINIMAP_DEFAULT_HEIGHT + 35) 
        else:
            self.minimap_dock = None
            self.minimap_widget = None

        self.asset_palette_widget.asset_selected.connect(self.map_view_widget.on_asset_selected)
        self.asset_palette_widget.asset_selected.connect(self.properties_editor_widget.display_asset_properties)
        self.asset_palette_widget.tool_selected.connect(self.map_view_widget.on_tool_selected)
        self.asset_palette_widget.paint_color_changed_for_status.connect(self.show_status_message)

        self.map_view_widget.map_object_selected_for_properties.connect(self.properties_editor_widget.display_map_object_properties)
        self.map_view_widget.map_content_changed.connect(self.handle_map_content_changed)

        self.properties_editor_widget.properties_changed.connect(self.map_view_widget.on_object_properties_changed)
        self.properties_editor_widget.properties_changed.connect(self.handle_map_content_changed) 

        if self.minimap_widget:
            self.map_view_widget.view_changed.connect(self.minimap_widget.schedule_view_rect_update_and_repaint)
        
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.VerticalTabs)
        self.map_view_widget.setFocus()
        logger.debug("UI components initialized.")

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
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock:
            view_menu.addAction(self.minimap_dock.toggleViewAction())

        help_menu = self.menu_bar.addMenu("&Help")
        about_action = QAction("&About", self, statusTip="Show editor information", triggered=self.about_dialog)
        help_menu.addAction(about_action)
        logger.debug("Menus created.")

    def create_status_bar(self):
        logger.debug("Creating status bar...")
        self.status_bar = self.statusBar() 
        self.status_bar.showMessage("Ready", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT)
        self.map_coords_label = QLabel(" Map: (0,0) Tile: (0,0) Zoom: 1.00x ")
        self.map_coords_label.setMinimumWidth(250)
        self.status_bar.addPermanentWidget(self.map_coords_label)
        self.map_view_widget.mouse_moved_on_map.connect(self.update_map_coords_status)
        logger.debug("Status bar created.")

    @Slot(str)
    def show_status_message(self, message: str, timeout: int = ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT):
        if hasattr(self, 'status_bar') and self.status_bar: 
            self.status_bar.showMessage(message, timeout)
        logger.info(f"Status: {message}")


    @Slot(tuple)
    def update_map_coords_status(self, coords: tuple):
        wx, wy, tx, ty, zl = coords
        self.map_coords_label.setText(f" Map:({int(wx)},{int(wy)}) Tile:({tx},{ty}) Zoom:{zl:.2f}x ")

    @Slot()
    def handle_map_content_changed(self):
        logger.debug("EditorMainWindow: handle_map_content_changed triggered.")
        if not self.editor_state.unsaved_changes:
            logger.debug("Map content changed, unsaved_changes was False, now set to True.")
        self.editor_state.unsaved_changes = True
        if not self._is_embedded: self.update_window_title() # Only update title if standalone
        self.update_edit_actions_enabled_state()

        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_widget') and self.minimap_widget:
             logger.debug("Notifying minimap to redraw content due to map change via handle_map_content_changed.")
             self.minimap_widget.schedule_map_content_redraw()

        logger.debug(f"EditorMainWindow: After handle_map_content_changed - unsaved_changes: {self.editor_state.unsaved_changes}, save_map_action enabled: {self.save_map_action.isEnabled()}")

    def update_window_title(self):
        if self._is_embedded: 
            return
        
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
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
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
            if any(char in clean_map_name for char in invalid_chars): QMessageBox.warning(self, "Invalid Name", f"Map name '{clean_map_name}' has invalid chars."); return
            
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
            if not editor_map_utils.ensure_maps_directory_exists():
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

            potential_json_path = os.path.join(maps_abs_dir, clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(potential_json_path): QMessageBox.warning(self, "Name Exists", f"JSON '{os.path.basename(potential_json_path)}' exists."); return
            
            size_str, ok_size = QInputDialog.getText(self, "Map Size", "Enter map size (Width,Height in tiles):", text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}")
            if ok_size and size_str:
                try:
                    w_str, h_str = size_str.split(','); width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                    max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 1000); max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 1000)
                    if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h): raise ValueError(f"Dims must be >0 and <= max ({max_w}x{max_h})")
                    editor_map_utils.init_new_map_state(self.editor_state, clean_map_name, width_tiles, height_tiles)
                    self.map_view_widget.load_map_from_state(); self.asset_palette_widget.clear_selection()
                    self.properties_editor_widget.clear_display()
                    if not self._is_embedded: self.update_window_title()
                    self.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                    editor_history.push_undo_state(self.editor_state); self.update_edit_actions_enabled_state()
                except ValueError as e: QMessageBox.warning(self, "Invalid Size", f"Invalid map size: {e}")
                except Exception as e_new: logger.error(f"Error new map: {e_new}", exc_info=True); QMessageBox.critical(self, "Error", f"Could not create new map: {e_new}")
        else: self.show_status_message("New map cancelled.")

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
            if editor_map_utils.load_map_from_json(self.editor_state, file_path):
                self.map_view_widget.load_map_from_state(); self.asset_palette_widget.clear_selection()
                self.properties_editor_widget.clear_display()
                if not self._is_embedded: self.update_window_title()
                self.show_status_message(f"Map '{self.editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(self.editor_state); self.update_edit_actions_enabled_state()
            else: QMessageBox.critical(self, "Load Error", f"Failed to load map from: {os.path.basename(file_path)}")
        else: self.show_status_message("Load map cancelled.")

    @Slot()
    def save_map_json(self) -> bool:
        logger.info("Save Map (JSON) action triggered.")
        if not self.editor_state.map_name_for_function or self.editor_state.map_name_for_function == "untitled_map":
            self.show_status_message("Map is untitled. Performing initial Save All.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
            return self.save_all() 
        if editor_map_utils.save_map_to_json(self.editor_state):
            self.show_status_message(f"Editor data saved: {os.path.basename(self.editor_state.current_json_filename)}.")
            self.editor_state.unsaved_changes = False 
            if not self._is_embedded: self.update_window_title()
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
            if not self._is_embedded: self.update_window_title()
            self.update_edit_actions_enabled_state()
            self.show_status_message(f"Map exported for game: {os.path.basename(self.editor_state.current_map_filename)}.")
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
                json_fn = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
                py_fn = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
                
                project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
                if not editor_map_utils.ensure_maps_directory_exists():
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
        if not self.editor_state.current_json_filename: QMessageBox.information(self, "Rename Map", "No map loaded to rename."); return
        old_base_name = self.editor_state.map_name_for_function

        new_name_str, ok = QInputDialog.getText(self, "Rename Map", f"Enter new name for '{old_base_name}':", text=old_base_name)
        if ok and new_name_str:
            clean_new_name = new_name_str.strip().lower().replace(" ", "_").replace("-", "_")
            if not clean_new_name or any(c in clean_new_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '.']): QMessageBox.warning(self, "Invalid Name", "New map name invalid."); return
            if clean_new_name == old_base_name: self.show_status_message("Rename cancelled: name unchanged."); return
            
            project_root_for_maps = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(project_root_for_maps, ED_CONFIG.MAPS_DIRECTORY)
            if not editor_map_utils.ensure_maps_directory_exists():
                 QMessageBox.critical(self, "Error", f"Cannot access or create maps directory: {maps_abs_dir}"); return

            new_json_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
            if os.path.exists(new_json_path) and os.path.normcase(new_json_path) != os.path.normcase(self.editor_state.current_json_filename):
                QMessageBox.warning(self, "Rename Error", f"JSON '{os.path.basename(new_json_path)}' already exists."); return
            
            old_json_path = self.editor_state.current_json_filename
            old_py_path = self.editor_state.current_map_filename 
            new_py_path = os.path.join(maps_abs_dir, clean_new_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)
            try:
                logger.info(f"Attempting rename '{old_base_name}' to '{clean_new_name}'.")
                if old_json_path and os.path.exists(old_json_path): os.rename(old_json_path, new_json_path)
                
                self.editor_state.map_name_for_function = clean_new_name
                self.editor_state.current_json_filename = new_json_path
                self.editor_state.current_map_filename = new_py_path 
                
                if not editor_map_utils.save_map_to_json(self.editor_state): 
                    QMessageBox.critical(self, "Rename Error", "Failed to save to new JSON after renaming file."); return
                
                if old_py_path and os.path.exists(old_py_path) and os.path.normcase(old_py_path) != os.path.normcase(new_py_path):
                    os.remove(old_py_path); logger.info(f"Old PY file '{os.path.basename(old_py_path)}' deleted.")
                
                if editor_map_utils.export_map_to_game_python_script(self.editor_state):
                    self.show_status_message(f"Map renamed to '{clean_new_name}' and files updated.")
                else:
                    QMessageBox.warning(self, "Rename Warning", "Map renamed, JSON updated, but new PY export failed. Save All manually."); self.editor_state.unsaved_changes = True
                
                if not self._is_embedded: self.update_window_title()
                self.update_edit_actions_enabled_state()
            except Exception as e_rename: logger.error(f"Error during rename: {e_rename}", exc_info=True); QMessageBox.critical(self, "Rename Error", f"An error occurred: {e_rename}")
        else: self.show_status_message("Rename map cancelled.")

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
            reply = QMessageBox.warning(self, "Confirm Delete", f"Delete all files for map '{map_name_to_delete}'?\nCannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if editor_map_utils.delete_map_files(self.editor_state, file_path):
                    self.show_status_message(f"Map '{map_name_to_delete}' files deleted.")
                    if self.editor_state.current_json_filename and os.path.normcase(self.editor_state.current_json_filename) == os.path.normcase(file_path):
                        self.editor_state.reset_map_context(); self.map_view_widget.load_map_from_state()
                        self.asset_palette_widget.clear_selection(); self.properties_editor_widget.clear_display()
                        if not self._is_embedded: self.update_window_title()
                        self.update_edit_actions_enabled_state()
                else: QMessageBox.critical(self, "Delete Error", f"Failed to delete files for '{map_name_to_delete}'.")
            else: self.show_status_message("Delete map cancelled.")
        else: self.show_status_message("Delete map selection cancelled.")

    @Slot()
    def export_map_as_image(self):
        logger.info("Export Map as Image action triggered.")
        if not self.editor_state.placed_objects and not self.editor_state.current_json_filename:
            QMessageBox.information(self, "Export Error", "No map content to export as an image.")
            return
        default_map_name = self.editor_state.map_name_for_function if self.editor_state.map_name_for_function != "untitled_map" else "untitled_map_export"
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suggested_dir = os.path.join(project_root, "map_exports")
        if not os.path.exists(suggested_dir):
            try: os.makedirs(suggested_dir)
            except OSError as e: logger.error(f"Could not create map_exports directory: {e}"); suggested_dir = os.path.join(project_root, ED_CONFIG.MAPS_DIRECTORY)
        
        suggested_path = os.path.join(suggested_dir, default_map_name + ".png")
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Map as Image", suggested_path, "PNG Images (*.png);;All Files (*)")
        if not file_path: self.show_status_message("Export map as image cancelled."); logger.info("Export map as image cancelled."); return
        
        try:
            scene = self.map_view_widget.scene()
            if not scene: QMessageBox.critical(self, "Export Error", "Cannot access map scene."); return
            
            target_rect = scene.itemsBoundingRect() 
            if target_rect.isEmpty():
                 QMessageBox.information(self, "Export Error", "Map is empty, nothing to export as image.")
                 return

            padding = 20 
            target_rect.adjust(-padding, -padding, padding, padding)


            image = QImage(target_rect.size().toSize(), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent) 
            
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) 
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

            scene.render(painter, QRectF(image.rect()), target_rect)
            painter.end()
            
            if image.save(file_path, "PNG"):
                self.show_status_message(f"Map exported as image: {os.path.basename(file_path)}")
                logger.info(f"Map successfully exported as PNG to: {file_path}")
            else: QMessageBox.critical(self, "Export Error", f"Failed to save image to:\n{file_path}"); logger.error(f"Failed to save map image to {file_path}")
        except Exception as e: logger.error(f"Error exporting map as image: {e}", exc_info=True); QMessageBox.critical(self, "Export Error", f"Unexpected error during image export:\n{e}")

    @Slot()
    def undo(self):
        logger.info("Undo action triggered.")
        if editor_history.undo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem): self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
            else: self.properties_editor_widget.clear_display()
            self.show_status_message("Undo successful."); 
            if not self._is_embedded: self.update_window_title()
        else: self.show_status_message("Nothing to undo or undo failed.")

    @Slot()
    def redo(self):
        logger.info("Redo action triggered.")
        if editor_history.redo(self.editor_state):
            self.map_view_widget.load_map_from_state(); self.update_edit_actions_enabled_state()
            selected_map_items = self.map_view_widget.map_scene.selectedItems()
            if len(selected_map_items) == 1 and isinstance(selected_map_items[0], MapObjectItem): self.properties_editor_widget.display_map_object_properties(selected_map_items[0].map_object_data_ref)
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
            if not self.editor_state.placed_objects: QMessageBox.information(self, "Change Background Color", "Please load or create a map first."); return
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
        if event.key() == Qt.Key.Key_Escape and not self._is_embedded: # Only handle Esc if standalone
            logger.info("Escape key pressed, attempting to close window.")
            self.close(); event.accept()
        else: super().keyPressEvent(event)

    def closeEvent(self, event):
        # This closeEvent is for the QMainWindow itself.
        # If embedded, the parent container (ActualEditorWindow's page) would control its lifecycle.
        logger.info(f"Close event triggered for EditorMainWindow. Embedded: {self._is_embedded}")
        
        if self.confirm_unsaved_changes("exit the editor"):
            if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
            if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
            if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName():
                self.minimap_dock.setObjectName("MinimapDock")

            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            logger.info("Window geometry and state saved.")
            event.accept() # Allow the window to close
        else:
            event.ignore() # Prevent the window from closing


    def save_geometry_and_state(self):
        if not self.asset_palette_dock.objectName(): self.asset_palette_dock.setObjectName("AssetPaletteDock")
        if not self.properties_editor_dock.objectName(): self.properties_editor_dock.setObjectName("PropertiesEditorDock")
        if ED_CONFIG.MINIMAP_ENABLED and hasattr(self, 'minimap_dock') and self.minimap_dock and not self.minimap_dock.objectName():
            self.minimap_dock.setObjectName("MinimapDock")

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.debug("Window geometry and state explicitly saved.")

    def restore_geometry_and_state(self) -> bool:
        geom = self.settings.value("geometry")
        state = self.settings.value("windowState")
        restored = False
        try:
            if geom is not None: self.restoreGeometry(geom); restored = True
            if state is not None: self.restoreState(state); restored = True
            if restored: logger.debug("Window geometry and/or state restored.")
        except Exception as e_restore:
            logger.error(f"Error restoring window geometry/state: {e_restore}. Resetting to defaults.", exc_info=True)
            if not self._is_embedded: # Only set default geometry if standalone
                 self.setGeometry(50, 50, ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT)
            return False 
        return restored

def editor_main(parent_app_instance: Optional[QApplication] = None, embed_mode: bool = False):
    if not embed_mode: 
        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            if logger: logger.info(f"Standalone mode: Changed CWD to: {os.getcwd()}")
        except Exception as e_chdir:
            if logger: logger.error(f"Could not change CWD in standalone mode: {e_chdir}")

    if logger: logger.info(f"editor_main() started. Embed mode: {embed_mode}")
    
    app = QApplication.instance() 
    if app is None:
        if parent_app_instance:
            app = parent_app_instance
            if logger: logger.debug("Using parent_app_instance for QApplication.")
        elif not embed_mode: 
            app = QApplication(sys.argv)
            if logger: logger.debug("QApplication instance created for standalone editor.")
        else: 
            if logger: logger.critical("CRITICAL: embed_mode is True, but no QApplication instance found or provided. Editor cannot run.")
            sys.exit("CRITICAL: No QApplication for embedded editor.")
    else:
        if logger: logger.debug("QApplication instance already exists.")

    main_window = EditorMainWindow(embed_mode=embed_mode) 

    if not embed_mode: 
        exit_code = 0
        try:
            if not main_window.isVisible() and not main_window._is_embedded: 
                 if logger: logger.info("Standalone editor_main: main_window not visible, calling show().")
                 main_window.show()

            exit_code = app.exec()
            if logger: logger.info(f"QApplication event loop finished with exit code: {exit_code}")
        except Exception as e_main_loop:
            if logger: logger.critical(f"CRITICAL ERROR in QApplication exec: {e_main_loop}", exc_info=True)
            QMessageBox.critical(None,"Editor Critical Error", f"{e_main_loop}\n\nCheck log:\n{log_file_path_for_error_msg}")
            exit_code = 1
        finally:
            if hasattr(main_window, 'isVisible') and main_window.isVisible():
                main_window.save_geometry_and_state() 
            if logger: logger.info("Editor session (standalone) ended.")
        return exit_code
    else:
        if logger: logger.info("EditorMainWindow instance created for embedding. Returning instance.")
        return main_window


if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---")
    return_code = editor_main(embed_mode=False) 
    print(f"--- editor.py execution finished (exit code: {return_code}) ---")
    sys.exit(return_code)