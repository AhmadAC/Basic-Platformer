# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.8 (Added minimap state attributes)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor.
"""

import pygame
from typing import Optional, Dict, List, Tuple, Any, Callable
import traceback

import editor_config as ED_CONFIG

class EditorState:
    """
    Manages the current state of the level editor, including map data,
    UI selections, and editor modes.
    """
    def __init__(self):
        # print("DEBUG STATE: Initializing EditorState...")
        # --- Map Data & File ---
        self.current_map_data: Dict[str, Any] = {}
        self.current_map_filename: Optional[str] = None
        self.map_name_for_function: str = "untitled_map"

        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.DEFAULT_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR

        self.map_content_surface: Optional[pygame.Surface] = None

        # --- Minimap State ---
        self.minimap_surface: Optional[pygame.Surface] = None # The pre-rendered scaled down map
        self.minimap_needs_regeneration: bool = True        # Flag to trigger minimap redraw
        self.minimap_rect_in_palette: Optional[pygame.Rect] = None # Actual screen rect for minimap drawing

        # --- Placed Objects ---
        self.placed_objects: List[Dict[str, Any]] = []


        # --- Asset Palette & Selection ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {}
        self._selected_asset_editor_key: Optional[str] = None
        self.selected_asset_image_for_cursor: Optional[pygame.Surface] = None
        self.asset_palette_scroll_y: int = 0
        self.total_asset_palette_content_height: int = 0 # For the scrollable part below minimap

        # --- Map View & Camera ---
        self.camera_offset_x: int = 0
        self.camera_offset_y: int = 0
        self.show_grid: bool = True

        # --- Object Interaction ---
        self.dragging_object_index: Optional[int] = None
        self.drag_start_mouse_map_x: int = 0
        self.drag_start_mouse_map_y: int = 0
        self.drag_object_original_x: int = 0
        self.drag_object_original_y: int = 0

        # --- Tile Painting/Erasing State ---
        self.is_painting_tiles: bool = False
        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None
        self.is_erasing_tiles: bool = False
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None

        # --- Color Change Tool State ---
        self.color_change_target_info: Optional[Dict[str, Any]] = None

        # --- UI State ---
        self._current_editor_mode: str = "menu"
        self.unsaved_changes: bool = False
        self.hovered_tooltip_text: Optional[str] = None
        self.hovered_tooltip_pos: Optional[Tuple[int, int]] = None
        self.ui_elements_rects: Dict[str, Any] = {}

        # --- Dialogs and Input Fields ---
        self._active_dialog_type: Optional[str] = None
        self.dialog_input_text: str = ""
        self.dialog_prompt_message: str = ""
        self.dialog_input_default: str = ""
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

        # --- Status Messages ---
        self.status_message: Optional[str] = None
        self.status_message_timer: float = 0.0
        self.status_message_duration: float = 3.0

        # --- Final Initialization Steps ---
        self.recreate_map_content_surface()
        # print("DEBUG STATE: EditorState initialization complete.")

    @property
    def current_editor_mode(self) -> str:
        return self._current_editor_mode

    @current_editor_mode.setter
    def current_editor_mode(self, value: str):
        if self._current_editor_mode != value:
            # print(f"DEBUG STATE: current_editor_mode changed from '{self._current_editor_mode}' to '{value}'")
            self._current_editor_mode = value
            if value == "editing_map" and self.selected_asset_editor_key == "tool_color_change":
                 self.selected_asset_image_for_cursor = None # No cursor image for color tool
            if value == "editing_map":
                self.minimap_needs_regeneration = True # Ensure minimap is fresh when entering editor

    @property
    def active_dialog_type(self) -> Optional[str]:
        return self._active_dialog_type

    @active_dialog_type.setter
    def active_dialog_type(self, value: Optional[str]):
        if self._active_dialog_type != value:
            old_dialog_type = self._active_dialog_type
            # print(f"DEBUG STATE: active_dialog_type changed from '{old_dialog_type}' to '{value}'")
            self._active_dialog_type = value
            if value is None or (old_dialog_type is not None and old_dialog_type != value):
                keys_to_remove = []
                if old_dialog_type == "file_load":
                    keys_to_remove.extend(['dialog_file_item_rects', 'file_dialog_scrollbar_handle',
                                           'file_dialog_scrollbar_area', 'dialog_file_load_ok', 'dialog_file_load_cancel'])
                elif old_dialog_type == "color_picker": self.color_picker_rects.clear()
                removed_count = 0
                for key in keys_to_remove:
                    if key in self.ui_elements_rects:
                        try: del self.ui_elements_rects[key]; removed_count +=1
                        except KeyError: pass
                # if removed_count > 0: print(f"DEBUG STATE: Cleared {removed_count} UI rect(s) for dialog '{old_dialog_type}'.")
            if value is None: self.dialog_rect = None

    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        if self._selected_asset_editor_key != value:
            # print(f"DEBUG STATE: selected_asset_editor_key changed from '{self._selected_asset_editor_key}' to '{value}'")
            self._selected_asset_editor_key = value
            if value == "tool_color_change": # Match game_type_id from ED_CONFIG
                self.selected_asset_image_for_cursor = None
            elif value is None:
                 self.selected_asset_image_for_cursor = None
            # For other assets, the image is set in handle_editing_map_events when selected from palette

    def recreate_map_content_surface(self):
        map_pixel_width = self.map_width_tiles * self.grid_size
        map_pixel_height = self.map_height_tiles * self.grid_size
        safe_width, safe_height = max(1, map_pixel_width), max(1, map_pixel_height)
        try:
            self.map_content_surface = pygame.Surface((safe_width, safe_height))
            self.minimap_needs_regeneration = True # Trigger minimap regen
            # print(f"DEBUG STATE: Recreated map_content_surface: {safe_width}x{safe_height}")
        except pygame.error as e:
            print(f"ERROR STATE: Failed to create map_content_surface: {e}"); traceback.print_exc()
            try: self.map_content_surface = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE))
            except Exception as e_fallback: self.map_content_surface = None; print(f"CRITICAL STATE: Fallback surface failed: {e_fallback}")

    def get_map_pixel_width(self) -> int: return self.map_width_tiles * self.grid_size
    def get_map_pixel_height(self) -> int: return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration: float = 3.0):
        self.status_message, self.status_message_duration, self.status_message_timer = message, duration, duration
        # print(f"STATUS MSG: {message} (duration: {duration:.1f}s)")

    def update_status_message(self, dt: float):
        if self.status_message and self.status_message_timer > 0:
            self.status_message_timer -= dt
            if self.status_message_timer <= 0: self.status_message, self.status_message_timer = None, 0.0

    def reset_map_context(self):
        # print("DEBUG STATE: reset_map_context called.")
        self.map_name_for_function = "untitled_map"; self.current_map_filename = None
        self.placed_objects = []; self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES; self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.camera_offset_x, self.camera_offset_y = 0, 0; self.unsaved_changes = False
        self.selected_asset_editor_key, self.selected_asset_image_for_cursor = None, None
        self.is_painting_tiles, self.last_painted_tile_coords = False, None
        self.is_erasing_tiles, self.last_erased_tile_coords = False, None
        self.color_change_target_info = None
        self.minimap_needs_regeneration = True # Flag for minimap update
        # self.recreate_map_content_surface() # Typically called by init_new_map or load_map
        # print(f"DEBUG STATE: Map context reset. Map name: '{self.map_name_for_function}'.")