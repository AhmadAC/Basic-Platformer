#################### START OF FILE: editor\editor_state.py ####################

# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 2.0.1 (PySide6 Conversion - No Tooltips)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor, adapted for PySide6.
"""
import logging
from typing import Optional, Dict, List, Tuple, Any, Callable

from . import editor_config as ED_CONFIG # Use relative import

logger = logging.getLogger(__name__)

class EditorState:
    def __init__(self):
        logger.debug("Initializing EditorState for PySide6...")
        # --- Map Data ---
        self.current_map_filename: Optional[str] = None 
        self.current_json_filename: Optional[str] = None 
        self.map_name_for_function: str = "untitled_map"
        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.BASE_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE

        # --- Placed Objects and Properties ---
        self.placed_objects: List[Dict[str, Any]] = []
        self.asset_specific_variables: Dict[str, Dict[str, Any]] = {} 

        # --- Asset Palette State ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {} 
        self._selected_asset_editor_key: Optional[str] = None 
        self.current_selected_asset_paint_color: Optional[Tuple[int,int,int]] = None # NEW: For pre-setting color of next placed asset

        # --- Camera, View, and Tool State ---
        self.camera_offset_x: float = 0.0 
        self.camera_offset_y: float = 0.0 
        self.zoom_level: float = 1.0 
        self.show_grid: bool = True

        self.current_tool_mode: str = "place" 
        self.current_tile_paint_color: Optional[Tuple[int,int,int]] = None # For the dedicated Color Picker Tool operation

        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None
        self.last_colored_tile_coords: Optional[Tuple[int, int]] = None

        self._current_editor_mode: str = "editing_map" 
        self.unsaved_changes: bool = False
        self.status_message: Optional[str] = None
        self.undo_stack: List[Dict[str, Any]] = [] 
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
            
    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        if self._selected_asset_editor_key != value:
            self._selected_asset_editor_key = value
            logger.info(f"selected_asset_editor_key changed to: '{value}'")
            
    def get_map_pixel_width(self) -> int:
        return self.map_width_tiles * self.grid_size

    def get_map_pixel_height(self) -> int:
        return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration_ignored: float = 0): 
        self.status_message = message
        logger.info(f"Status message set internally: '{message}'")

    def reset_map_context(self):
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
        self.current_tool_mode = "place" 
        self.current_tile_paint_color = None
        # self.current_selected_asset_paint_color remains, as it's a palette-level setting, not map-specific context.

        self.last_painted_tile_coords = None
        self.last_erased_tile_coords = None
        self.last_colored_tile_coords = None

        self.undo_stack.clear()
        self.redo_stack.clear()
        logger.debug(f"Map context reset complete. Current map name: '{self.map_name_for_function}'.")

#################### END OF FILE: editor\editor_state.py ####################