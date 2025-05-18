# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 2.0.1 (PySide6 Conversion - No Tooltips)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor, adapted for PySide6.
"""
import logging
from typing import Optional, Dict, List, Tuple, Any, Callable

import editor_config as ED_CONFIG

logger = logging.getLogger(__name__)

class EditorState:
    def __init__(self):
        logger.debug("Initializing EditorState for PySide6...")
        # --- Map Data ---
        self.current_map_filename: Optional[str] = None # Full path to .py game level file
        self.current_json_filename: Optional[str] = None # Full path to .json editor save file
        self.map_name_for_function: str = "untitled_map"
        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.BASE_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE

        # --- Placed Objects and Properties ---
        self.placed_objects: List[Dict[str, Any]] = []
        self.asset_specific_variables: Dict[str, Dict[str, Any]] = {} # Custom properties per map object instance

        # --- Asset Palette State ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {} # Loaded assets with QPixmaps
        self._selected_asset_editor_key: Optional[str] = None # Key of the selected asset/tool

        # --- Camera, View, and Tool State ---
        # These are primarily for the QGraphicsView (MapViewWidget) to interpret
        self.camera_offset_x: float = 0.0 # Top-left X of the visible map area (in scene coordinates)
        self.camera_offset_y: float = 0.0 # Top-left Y of the visible map area (in scene coordinates)
        self.zoom_level: float = 1.0 # Current zoom factor of the map view
        self.show_grid: bool = True

        # Current tool/action state for MapViewWidget
        self.current_tool_mode: str = "place" # e.g., "place", "erase", "select", "color_pick"
        self.current_tile_paint_color: Optional[Tuple[int,int,int]] = None # For tile coloring tool

        # For continuous paint/erase, to avoid re-acting on the same grid cell during a drag
        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None
        self.last_colored_tile_coords: Optional[Tuple[int, int]] = None


        # --- Editor Mode and General UI State ---
        self._current_editor_mode: str = "editing_map" # "menu" mode is less distinct now; actions drive state
                                                       # Could be "loading", "idle", etc. if needed.
                                                       # For now, assume mostly in "editing_map" once a map is open/new.
        self.unsaved_changes: bool = False

        # --- Status Message State (for QStatusBar) ---
        self.status_message: Optional[str] = None
        # Timer/duration for status messages will be handled by QTimer in EditorMainWindow

        # --- Undo/Redo Stacks ---
        self.undo_stack: List[Dict[str, Any]] = [] # Stores direct dictionary snapshots
        self.redo_stack: List[Dict[str, Any]] = []

        logger.debug("EditorState initialized.")

    @property
    def current_editor_mode(self) -> str:
        return self._current_editor_mode

    @current_editor_mode.setter
    def current_editor_mode(self, value: str):
        if self._current_editor_mode != value:
            logger.debug(f"Changing editor mode from '{self._current_editor_mode}' to '{value}'")
            self._current_editor_mode = value
            # Add any mode-specific state resets if necessary

    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        if self._selected_asset_editor_key != value:
            self._selected_asset_editor_key = value
            logger.info(f"selected_asset_editor_key changed to: '{value}'")
            # The MapViewWidget will observe this change (or be told via signal)
            # and update its hover preview based on the QPixmap in assets_palette.

    def get_map_pixel_width(self) -> int:
        """Returns the current map width in pixels based on grid_size."""
        return self.map_width_tiles * self.grid_size

    def get_map_pixel_height(self) -> int:
        """Returns the current map height in pixels based on grid_size."""
        return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration_ignored: float = 0): # Duration handled by Qt
        """Sets a status message. Duration is now handled by QStatusBar/QTimer."""
        self.status_message = message
        # In Qt, usually a signal would be emitted here, or MainWindow polls this.
        logger.info(f"Status message set internally: '{message}'")

    def reset_map_context(self):
        """Resets all map-specific data to defaults."""
        logger.debug("Resetting map context.")
        self.map_name_for_function = "untitled_map"
        self.current_map_filename = None
        self.current_json_filename = None
        self.placed_objects = []
        self.asset_specific_variables.clear()
        self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size = ED_CONFIG.BASE_GRID_SIZE
        self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE
        self.camera_offset_x, self.camera_offset_y = 0.0, 0.0
        self.zoom_level = 1.0
        self.unsaved_changes = False
        self.selected_asset_editor_key = None
        self.current_tool_mode = "place" # Default tool
        self.current_tile_paint_color = None

        self.last_painted_tile_coords = None
        self.last_erased_tile_coords = None
        self.last_colored_tile_coords = None

        self.undo_stack.clear()
        self.redo_stack.clear()
        logger.debug(f"Map context reset complete. Current map name: '{self.map_name_for_function}'.")