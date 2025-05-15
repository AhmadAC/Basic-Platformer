# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.15 (Added dialog_input_text_selected flag)
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
        self.current_map_filename: Optional[str] = None
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
        self.assets_palette: Dict[str, Dict[str, Any]] = {}
        self._selected_asset_editor_key: Optional[str] = None
        self.selected_asset_image_for_cursor: Optional[pygame.Surface] = None 
        self.asset_palette_scroll_y: float = 0.0 
        self.asset_palette_scroll_momentum: float = 0.0 
        self.total_asset_palette_content_height: int = 0


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
        self.is_erasing_tiles: bool = False
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None

        self._current_editor_mode: str = "menu"
        self.unsaved_changes: bool = False
        self.hovered_tooltip_text: Optional[str] = None
        self.hovered_tooltip_pos: Optional[Tuple[int, int]] = None
        self.ui_elements_rects: Dict[str, Any] = {}
        self._active_dialog_type: Optional[str] = None
        self.dialog_input_text: str = ""
        self.dialog_prompt_message: str = ""
        self.dialog_input_default: str = ""
        self.dialog_input_text_selected: bool = False # New flag for text highlighting
        self.dialog_callback_confirm: Optional[Callable[..., None]] = None
        self.dialog_callback_cancel: Optional[Callable[[], None]] = None
        self.dialog_rect: Optional[pygame.Rect] = None
        self.color_picker_rects: Dict[str, pygame.Rect] = {} 
        self.dialog_file_list: List[str] = []
        self.dialog_file_scroll_y: int = 0
        self.dialog_selected_file_index: int = -1
        self.is_dragging_scrollbar: bool = False
        self.scrollbar_drag_mouse_offset_y: int = 0
        self.map_name_for_function_input: str = ""
        self.status_message: Optional[str] = None
        self.status_message_timer: float = 0.0
        self.status_message_duration: float = 3.0
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
            if value == "menu":
                self.camera_momentum_pan = (0.0, 0.0)
                self.asset_palette_scroll_momentum = 0.0 


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
                self.dialog_input_text_selected = False # Ensure deselected when any dialog closes

            if value is None or (old_dialog_type is not None and old_dialog_type != value):
                keys_to_remove = []
                if old_dialog_type == "file_load":
                    keys_to_remove.extend(['dialog_file_item_rects', 'file_dialog_scrollbar_handle',
                                           'file_dialog_scrollbar_area', 'dialog_file_load_ok', 'dialog_file_load_cancel'])
                elif old_dialog_type == "color_picker": self.color_picker_rects.clear()
                elif old_dialog_type == "text_input":
                    if 'dialog_text_input_box' in self.ui_elements_rects:
                        keys_to_remove.append('dialog_text_input_box')

                for key in keys_to_remove:
                    if key in self.ui_elements_rects:
                        try: del self.ui_elements_rects[key]
                        except KeyError: pass
            if value is None: self.dialog_rect = None

    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        logger.debug(f"Attempting to set selected_asset_editor_key from '{self._selected_asset_editor_key}' to '{value}'")
        if self._selected_asset_editor_key != value or \
           (value is not None and value in self.assets_palette and self.selected_asset_image_for_cursor is None):

            self._selected_asset_editor_key = value
            logger.info(f"selected_asset_editor_key changed to: '{value}'")

            if value is None:
                self.selected_asset_image_for_cursor = None
                logger.debug("No asset selected. selected_asset_image_for_cursor set to None.")
            elif value in self.assets_palette:
                asset_data = self.assets_palette[value]
                if "image" in asset_data and asset_data["image"] is not None:
                    self.selected_asset_image_for_cursor = asset_data["image"].copy()
                    logger.debug(f"Asset '{value}' selected. Cursor image set from palette.")
                else:
                    self.selected_asset_image_for_cursor = None
                    logger.warning(f"Asset '{value}' selected, but has no image in palette. Cursor image set to None.")
            else: 
                self.selected_asset_image_for_cursor = None
                logger.warning(f"Asset key '{value}' not found in assets_palette during selection. Cursor image set to None.")
        else:
            logger.debug(f"selected_asset_editor_key already '{value}', no change needed for key or cursor state.")


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
        self.map_name_for_function = "untitled_map"; self.current_map_filename = None
        self.placed_objects = []; self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES; self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.camera_offset_x, self.camera_offset_y = 0, 0; self.unsaved_changes = False
        self.selected_asset_editor_key, self.selected_asset_image_for_cursor = None, None
        self.is_painting_tiles, self.last_painted_tile_coords = False, None
        self.is_erasing_tiles, self.last_erased_tile_coords = False, None
        self.minimap_needs_regeneration = True
        self.last_mouse_pos_map_view = None
        self.mouse_velocity_map_view = (0.0, 0.0)
        self.camera_momentum_pan = (0.0, 0.0)
        self.asset_palette_scroll_momentum = 0.0 
        self.asset_palette_scroll_y = 0.0
        self.dialog_input_text_selected = False # Reset this flag
        self.is_mouse_over_map_view = False
        self.is_dragging_minimap_view = False
        logger.debug(f"Map context reset. Map name: '{self.map_name_for_function}'.")