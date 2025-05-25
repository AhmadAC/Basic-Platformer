#################### START OF FILE: editor_state.py ####################

# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 2.2.1 (Asset Flip/Cycle State)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor, adapted for PySide6.
- Added state for palette asset orientation (flip) and wall variant cycling.
"""
import logging
from typing import Optional, Dict, List, Tuple, Any, Callable

from . import editor_config as ED_CONFIG

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
        # Each object includes "is_flipped_h": bool for standard assets.
        self.placed_objects: List[Dict[str, Any]] = []
        self.asset_specific_variables: Dict[str, Dict[str, Any]] = {} 

        # --- Asset Palette State ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {}
        self._selected_asset_editor_key: Optional[str] = None 
        self.current_selected_asset_paint_color: Optional[Tuple[int,int,int]] = None
        
        # New state for asset orientation/variant in palette
        self.palette_current_asset_key: Optional[str] = None # The asset key currently active in the palette for placement
        self.palette_asset_is_flipped_h: bool = False # If the palette_current_asset_key should be placed flipped
        self.palette_wall_variant_index: int = 0 # Index into ED_CONFIG.WALL_VARIANTS_CYCLE for current wall
        self.current_tool_mode: str = "place" # Default to "place" on startup, "select" will be a mode

        # --- Camera, View, and Tool State ---
        self.camera_offset_x: float = 0.0
        self.camera_offset_y: float = 0.0
        self.zoom_level: float = 1.0
        self.show_grid: bool = True

        # self.current_tool_mode: str = "place" # Now handled above with palette state
        self.current_tile_paint_color: Optional[Tuple[int,int,int]] = None

        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None
        self.last_colored_tile_coords: Optional[Tuple[int, int]] = None

        self._current_editor_mode: str = "editing_map"
        self.unsaved_changes: bool = False
        self.status_message: Optional[str] = None
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []

        self.controller_mode_active: bool = False
        self.is_game_preview_mode: bool = False


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
        """
        DEPRECATED: Use palette_current_asset_key, palette_asset_is_flipped_h,
        and palette_wall_variant_index for placement context.
        This property might still be used by PropertiesEditor to know what type's defaults to show.
        """
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        """
        DEPRECATED for placement context. Set palette_current_asset_key instead.
        This primarily signals the PropertiesEditor.
        """
        if self._selected_asset_editor_key != value:
            self._selected_asset_editor_key = value
            logger.info(f"DEPRECATED selected_asset_editor_key changed to: '{value}' (for properties panel, not placement)")
            # When a new asset is selected FOR THE PALETTE to show its details (not for placement intent)
            # reset the placement-specific states
            if value is not None: # If selecting a new asset type for info
                 self.palette_current_asset_key = value # It becomes the current base for potential placement
                 self.palette_asset_is_flipped_h = False
                 if value == ED_CONFIG.WALL_BASE_KEY:
                     self.palette_wall_variant_index = 0 # Reset to base wall
                 else: # For non-wall assets, the variant index is not used in the same way
                     self.palette_wall_variant_index = 0 # Or -1 to indicate not applicable for wall cycle


    def get_current_placing_asset_effective_key(self) -> Optional[str]:
        """
        Determines the actual asset key to be placed, considering wall variants.
        """
        if self.current_tool_mode != "place" or not self.palette_current_asset_key:
            return None
        
        if self.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
            if 0 <= self.palette_wall_variant_index < len(ED_CONFIG.WALL_VARIANTS_CYCLE):
                return ED_CONFIG.WALL_VARIANTS_CYCLE[self.palette_wall_variant_index]
            else: # Fallback if index is out of bounds
                logger.warning(f"palette_wall_variant_index {self.palette_wall_variant_index} out of bounds. Defaulting to base wall.")
                return ED_CONFIG.WALL_BASE_KEY
        return self.palette_current_asset_key


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
        
        self._selected_asset_editor_key = None # Info selection
        self.palette_current_asset_key = None # Placement selection
        self.palette_asset_is_flipped_h = False
        self.palette_wall_variant_index = 0

        self.current_tool_mode = "place" # Reset tool mode
        self.current_tile_paint_color = None
        
        self.last_painted_tile_coords = None
        self.last_erased_tile_coords = None
        self.last_colored_tile_coords = None

        self.undo_stack.clear()
        self.redo_stack.clear()
        logger.debug(f"Map context reset complete. Current map name: '{self.map_name_for_function}'.")

#################### END OF FILE: editor_state.py ####################