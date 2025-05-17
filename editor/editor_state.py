# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.16 (Added undo/redo, asset properties state)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor.
"""
import pygame
from typing import Optional, Dict, List, Tuple, Any, Callable
import traceback
import logging

import editor_config as ED_CONFIG

logger = logging.getLogger(__name__)

class EditorState:
    def __init__(self):
        logger.debug("Initializing EditorState...")
        self.current_map_data: Dict[str, Any] = {}
        self.current_map_filename: Optional[str] = None # Full path to .py game level file
        self.current_json_filename: Optional[str] = None # Full path to .json editor save file
        self.map_name_for_function: str = "untitled_map"
        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.DEFAULT_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.map_content_surface: Optional[pygame.Surface] = None

        self.minimap_surface: Optional[pygame.Surface] = None
        self.minimap_needs_regeneration: bool = True
        self.minimap_rect_in_palette: Optional[pygame.Rect] = None
        self.is_dragging_minimap_view: bool = False

        self.placed_objects: List[Dict[str, Any]] = []
        # Stores custom properties for asset types within this map, e.g. {"player1_spawn": {"health":10}}
        self.asset_specific_variables: Dict[str, Dict[str, Any]] = {}


        self.assets_palette: Dict[str, Dict[str, Any]] = {}
        self._selected_asset_editor_key: Optional[str] = None
        self.selected_asset_image_for_cursor: Optional[pygame.Surface] = None
        self.asset_palette_scroll_y: float = 0.0
        self.asset_palette_scroll_momentum: float = 0.0
        self.total_asset_palette_content_height: int = 0

        # Asset Palette Options Dropdown
        self.asset_palette_options_dropdown_open: bool = False
        self.asset_palette_options_rects: Dict[str, pygame.Rect] = {} # "View Assets", "Asset Properties Editor"
        self.asset_palette_options_button_rect: Optional[pygame.Rect] = None


        self.camera_offset_x: int = 0
        self.camera_offset_y: int = 0
        self.show_grid: bool = True

        self.last_mouse_pos_map_view: Optional[Tuple[int, int]] = None
        self.mouse_velocity_map_view: Tuple[float, float] = (0.0, 0.0)
        self.camera_momentum_pan: Tuple[float, float] = (0.0, 0.0)
        self.is_mouse_over_map_view: bool = False

        self.dragging_object_index: Optional[int] = None
        self.drag_start_mouse_map_x: int = 0
        self.drag_start_mouse_map_y: int = 0
        self.drag_object_original_x: int = 0
        self.drag_object_original_y: int = 0
        self.is_painting_tiles: bool = False
        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None
        self.is_erasing_tiles: bool = False # For single right-click erase
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None
        self.is_multi_deleting: bool = False # For right-click-drag erase
        self.last_multi_deleted_grid_coords: Optional[Tuple[int, int]] = None


        self._current_editor_mode: str = "menu"
        self.unsaved_changes: bool = False
        self.hovered_tooltip_text: Optional[str] = None
        self.hovered_tooltip_pos: Optional[Tuple[int, int]] = None
        self.ui_elements_rects: Dict[str, Any] = {} # General UI rects cache
        
        # Dialog System State
        self._active_dialog_type: Optional[str] = None
        self.dialog_prompt_message: str = ""
        self.dialog_rect: Optional[pygame.Rect] = None
        self.dialog_callback_confirm: Optional[Callable[..., None]] = None
        self.dialog_callback_cancel: Optional[Callable[[], None]] = None
        
        # Text Input Dialog Specific
        self.dialog_input_text: str = ""
        self.dialog_input_default: str = ""
        self.dialog_input_text_selected: bool = False
        
        # Color Picker Dialog Specific
        self.color_picker_rects: Dict[str, pygame.Rect] = {}
        
        # File Load Dialog Specific
        self.dialog_file_list: List[str] = []
        self.dialog_file_scroll_y: int = 0
        self.dialog_selected_file_index: int = -1
        self.is_dragging_scrollbar: bool = False
        self.scrollbar_drag_mouse_offset_y: int = 0
        
        # Asset Properties Editor Dialog Specific
        self.dialog_asset_properties_selected_key: Optional[str] = None # Which asset type is selected in the dialog
        self.dialog_asset_properties_temp_values: Dict[str, Any] = {} # Temp values for the selected asset type's vars
        self.dialog_asset_properties_input_field_rects: Dict[str, pygame.Rect] = {} # Rects for var input fields
        self.dialog_asset_properties_scroll_y: float = 0.0
        self.dialog_asset_properties_dropdown_open: bool = False # For the dropdown within the dialog
        self.dialog_asset_properties_dropdown_rect: Optional[pygame.Rect] = None
        self.dialog_asset_properties_dropdown_option_rects: List[pygame.Rect] = []


        self.map_name_for_function_input: str = "" # Temp storage during new map creation flow
        self.status_message: Optional[str] = None
        self.status_message_timer: float = 0.0
        self.status_message_duration: float = 3.0

        # Undo/Redo Stacks
        self.undo_stack: List[str] = [] # Store serialized JSON strings of map states
        self.redo_stack: List[str] = []

        self.recreate_map_content_surface()
        logger.debug("EditorState initialized.")


    @property
    def current_editor_mode(self) -> str:
        return self._current_editor_mode

    @current_editor_mode.setter
    def current_editor_mode(self, value: str):
        if self._current_editor_mode != value:
            logger.debug(f"Changing editor mode from '{self._current_editor_mode}' to '{value}'")
            self._current_editor_mode = value
            if value == "editing_map":
                self.minimap_needs_regeneration = True
                self.camera_momentum_pan = (0.0, 0.0)
                self.asset_palette_scroll_momentum = 0.0
                # Close asset palette dropdown if open when switching mode (or handle appropriately)
                self.asset_palette_options_dropdown_open = False
            if value == "menu":
                self.camera_momentum_pan = (0.0, 0.0)
                self.asset_palette_scroll_momentum = 0.0
                self.asset_palette_options_dropdown_open = False


    @property
    def active_dialog_type(self) -> Optional[str]:
        return self._active_dialog_type

    @active_dialog_type.setter
    def active_dialog_type(self, value: Optional[str]):
        if self._active_dialog_type != value:
            logger.debug(f"Changing active_dialog_type from '{self._active_dialog_type}' to '{value}'")
            old_dialog_type = self._active_dialog_type
            self._active_dialog_type = value
            
            if value is not None: # If any dialog is opening
                self.camera_momentum_pan = (0.0, 0.0)
                self.asset_palette_scroll_momentum = 0.0
            else: # Dialog is closing
                self.dialog_input_text_selected = False
                # Reset specific dialog states when any dialog closes
                self.dialog_asset_properties_selected_key = None
                self.dialog_asset_properties_temp_values.clear()
                self.dialog_asset_properties_input_field_rects.clear()
                self.dialog_asset_properties_dropdown_open = False


            # Clean up UI elements rects for the closing dialog
            if old_dialog_type is not None and old_dialog_type != value:
                keys_to_remove = []
                if old_dialog_type == "file_load":
                    keys_to_remove.extend(['dialog_file_item_rects', 'file_dialog_scrollbar_handle',
                                           'file_dialog_scrollbar_area', 'dialog_file_load_ok', 'dialog_file_load_cancel'])
                elif old_dialog_type == "color_picker": self.color_picker_rects.clear()
                elif old_dialog_type == "text_input":
                    keys_to_remove.append('dialog_text_input_box')
                elif old_dialog_type == "asset_properties_editor":
                    keys_to_remove.extend(['dialog_asset_prop_dropdown_button',
                                           'dialog_asset_prop_save_button', 
                                           'dialog_asset_prop_close_button',
                                           'dialog_asset_prop_item_input_fields', # This might be a dict itself
                                           'dialog_asset_prop_scrollbar_handle',
                                           'dialog_asset_prop_scrollbar_area'])
                    self.dialog_asset_properties_input_field_rects.clear()


                for key in keys_to_remove:
                    if key in self.ui_elements_rects:
                        try: del self.ui_elements_rects[key]
                        except KeyError: pass
            
            if value is None: # Reset general dialog properties
                self.dialog_rect = None
                self.dialog_prompt_message = ""
                self.dialog_callback_confirm = None
                self.dialog_callback_cancel = None

    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        if self._selected_asset_editor_key != value or \
           (value is not None and value in self.assets_palette and self.selected_asset_image_for_cursor is None):

            self._selected_asset_editor_key = value
            logger.info(f"selected_asset_editor_key changed to: '{value}'")

            if value is None:
                self.selected_asset_image_for_cursor = None
            elif value in self.assets_palette:
                asset_data = self.assets_palette[value]
                original_image = asset_data.get("image")
                if original_image:
                    # Create a modifiable copy for the cursor
                    cursor_image = original_image.copy()
                    
                    # 1. Set 50% transparency
                    cursor_image.set_alpha(ED_CONFIG.CURSOR_ASSET_ALPHA)
                    
                    # 2. Apply red hue
                    # Create a red overlay surface
                    hue_overlay = pygame.Surface(cursor_image.get_size(), pygame.SRCALPHA)
                    hue_overlay.fill(ED_CONFIG.CURSOR_ASSET_HUE_COLOR) # (R, G, B, Alpha for hue strength)
                    
                    # Blit the hue overlay onto the cursor image
                    # BLEND_RGBA_MULT tends to darken, BLEND_RGBA_ADD tends to lighten.
                    # A common technique for tinting is to fill with color and then BLEND_MULT with original alpha.
                    # Or, for a hue shift, could manipulate pixels, but an overlay is simpler.
                    # Let's try a multiplicative blend for tinting.
                    cursor_image.blit(hue_overlay, (0,0), special_flags=pygame.BLEND_RGBA_ADD) # Experiment with blend modes

                    self.selected_asset_image_for_cursor = cursor_image
                    logger.debug(f"Asset '{value}' selected. Cursor image processed with transparency and hue.")
                else:
                    self.selected_asset_image_for_cursor = None
                    logger.warning(f"Asset '{value}' selected, but has no image in palette.")
            else: 
                self.selected_asset_image_for_cursor = None
                logger.warning(f"Asset key '{value}' not found in assets_palette during selection.")
        # else:
            # logger.debug(f"selected_asset_editor_key already '{value}', no change needed for key or cursor state.")


    def recreate_map_content_surface(self):
        map_pixel_width = self.map_width_tiles * self.grid_size
        map_pixel_height = self.map_height_tiles * self.grid_size
        safe_width, safe_height = max(1, map_pixel_width), max(1, map_pixel_height)
        try:
            self.map_content_surface = pygame.Surface((safe_width, safe_height))
            self.minimap_needs_regeneration = True
            logger.debug(f"Recreated map_content_surface: {safe_width}x{safe_height}")
        except pygame.error as e:
            logger.error(f"Failed to create map_content_surface: {e}", exc_info=True)
            try: self.map_content_surface = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE))
            except Exception as e_fallback: self.map_content_surface = None; logger.critical(f"Fallback surface failed: {e_fallback}", exc_info=True)


    def get_map_pixel_width(self) -> int: return self.map_width_tiles * self.grid_size
    def get_map_pixel_height(self) -> int: return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration: float = 3.0):
        self.status_message, self.status_message_duration, self.status_message_timer = message, duration, duration
        logger.info(f"Status message set: '{message}' for {duration}s")

    def update_status_message(self, dt: float):
        if self.status_message and self.status_message_timer > 0:
            self.status_message_timer -= dt
            if self.status_message_timer <= 0: self.status_message, self.status_message_timer = None, 0.0

    def reset_map_context(self):
        logger.debug("Resetting map context.")
        self.map_name_for_function = "untitled_map"
        self.current_map_filename = None
        self.current_json_filename = None
        self.placed_objects = []
        self.asset_specific_variables.clear()
        self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.camera_offset_x, self.camera_offset_y = 0, 0
        self.unsaved_changes = False
        self.selected_asset_editor_key, self.selected_asset_image_for_cursor = None, None
        self.is_painting_tiles, self.last_painted_tile_coords = False, None
        self.is_erasing_tiles, self.last_erased_tile_coords = False, None
        self.is_multi_deleting, self.last_multi_deleted_grid_coords = False, None
        self.minimap_needs_regeneration = True
        self.last_mouse_pos_map_view = None
        self.mouse_velocity_map_view = (0.0, 0.0)
        self.camera_momentum_pan = (0.0, 0.0)
        self.asset_palette_scroll_momentum = 0.0
        self.asset_palette_scroll_y = 0.0
        self.dialog_input_text_selected = False
        self.is_mouse_over_map_view = False
        self.is_dragging_minimap_view = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.asset_palette_options_dropdown_open = False
        logger.debug(f"Map context reset. Map name: '{self.map_name_for_function}'.")