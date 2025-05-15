# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.5 (Added cleanup for UI rects in active_dialog_type setter)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor.
"""

import pygame
from typing import Optional, Dict, List, Tuple, Any, Callable # Ensure Callable is imported
import traceback # Added for robust error handling

# Assuming editor_config.py is in the same 'editor' package
import editor_config as ED_CONFIG
# constants.py (via ED_CONFIG.C) should be accessible from project root
# Relies on main editor.py correctly setting up sys.path

class EditorState:
    """
    Manages the current state of the level editor, including map data,
    UI selections, and editor modes.
    """
    def __init__(self):
        print("DEBUG STATE: Initializing EditorState...")
        # --- Map Data & File ---
        self.current_map_data: Dict[str, Any] = {}
        self.current_map_filename: Optional[str] = None
        self.map_name_for_function: str = "untitled_map"

        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.DEFAULT_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR

        self.map_content_surface: Optional[pygame.Surface] = None

        # --- Placed Objects ---
        self.placed_objects: List[Dict[str, Any]] = []

        # --- Asset Palette & Selection ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {}
        self._selected_asset_editor_key: Optional[str] = None
        self.selected_asset_image_for_cursor: Optional[pygame.Surface] = None
        self.asset_palette_scroll_y: int = 0
        self.total_asset_palette_content_height: int = 0

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

        # --- UI State ---
        self._current_editor_mode: str = "menu"
        self.unsaved_changes: bool = False
        self.hovered_tooltip_text: Optional[str] = None
        self.hovered_tooltip_pos: Optional[Tuple[int, int]] = None
        self.ui_elements_rects: Dict[str, Any] = {} # Stores rects of active UI elements

        # --- Dialogs and Input Fields ---
        self._active_dialog_type: Optional[str] = None
        self.dialog_input_text: str = ""
        self.dialog_prompt_message: str = ""
        self.dialog_input_default: str = ""
        self.dialog_callback_confirm: Optional[Callable[..., None]] = None
        self.dialog_callback_cancel: Optional[Callable[[], None]] = None
        self.dialog_rect: Optional[pygame.Rect] = None # Screen rect of the current dialog

        self.color_picker_rects: Dict[str, pygame.Rect] = {} # Relative rects for color swatches
        self.dialog_file_list: List[str] = []
        self.dialog_file_scroll_y: int = 0
        self.dialog_selected_file_index: int = -1
        self.is_dragging_scrollbar: bool = False
        self.scrollbar_drag_mouse_offset_y: int = 0

        self.map_name_for_function_input: str = "" # For chained dialogs (new map name -> size)

        # --- Status Messages ---
        self.status_message: Optional[str] = None
        self.status_message_timer: float = 0.0
        self.status_message_duration: float = 3.0 # Default display time

        # --- Final Initialization Steps ---
        self.recreate_map_content_surface() # Create initial map surface
        print("DEBUG STATE: EditorState initialization complete.")

    # --- Properties with Setters for Debugging State Changes ---
    @property
    def current_editor_mode(self) -> str:
        return self._current_editor_mode

    @current_editor_mode.setter
    def current_editor_mode(self, value: str):
        if self._current_editor_mode != value:
            print(f"DEBUG STATE: current_editor_mode changed from '{self._current_editor_mode}' to '{value}'")
            self._current_editor_mode = value
            # When mode changes, clear general UI rects that might be mode-specific
            # More specific clearing might be needed if rects persist inappropriately
            # self.ui_elements_rects.clear() # Too broad, will clear palette items too
            # print("DEBUG STATE: Cleared ui_elements_rects due to mode change.")


    @property
    def active_dialog_type(self) -> Optional[str]:
        return self._active_dialog_type

    @active_dialog_type.setter
    def active_dialog_type(self, value: Optional[str]):
        if self._active_dialog_type != value:
            old_dialog_type = self._active_dialog_type # Store previous type for cleanup
            print(f"DEBUG STATE: active_dialog_type changed from '{old_dialog_type}' to '{value}'")
            self._active_dialog_type = value

            # Clean up UI rects associated with the dialog that is closing or changing
            if value is None or (old_dialog_type is not None and old_dialog_type != value):
                keys_to_remove = []
                if old_dialog_type == "file_load":
                    keys_to_remove.extend([
                        'dialog_file_item_rects', # This is a list of dicts, but key is the list itself
                        'file_dialog_scrollbar_handle',
                        'file_dialog_scrollbar_area',
                        'dialog_file_load_ok',
                        'dialog_file_load_cancel'
                    ])
                elif old_dialog_type == "text_input":
                    # Text input might not store specific rects in ui_elements_rects beyond the main dialog_rect
                    pass 
                elif old_dialog_type == "color_picker":
                    # Color picker stores swatch rects in self.color_picker_rects, not ui_elements_rects
                    self.color_picker_rects.clear() # Clear its specific storage
                    print(f"DEBUG STATE: Cleared color_picker_rects for closed/changed dialog '{old_dialog_type}'.")

                removed_count = 0
                for key in keys_to_remove:
                    if key in self.ui_elements_rects:
                        try:
                            del self.ui_elements_rects[key]
                            removed_count +=1
                        except KeyError: # Should not happen if key in check passes
                            print(f"Warning STATE: KeyError trying to delete UI rect '{key}' (already removed?).")
                if removed_count > 0:
                    print(f"DEBUG STATE: Cleared {removed_count} UI rect(s) for closed/changed dialog '{old_dialog_type}'.")
            
            if value is None: # If dialog is closing completely
                self.dialog_rect = None # Clear the main dialog rect as well
                print("DEBUG STATE: Cleared dialog_rect as dialog is closing.")


    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        if self._selected_asset_editor_key != value:
            print(f"DEBUG STATE: selected_asset_editor_key changed from '{self._selected_asset_editor_key}' to '{value}'")
            self._selected_asset_editor_key = value

    def recreate_map_content_surface(self):
        map_pixel_width = self.map_width_tiles * self.grid_size
        map_pixel_height = self.map_height_tiles * self.grid_size
        
        safe_width = max(1, map_pixel_width)
        safe_height = max(1, map_pixel_height)
        
        try:
            self.map_content_surface = pygame.Surface((safe_width, safe_height))
            print(f"DEBUG STATE: Recreated map_content_surface: {safe_width}x{safe_height} (target: {map_pixel_width}x{map_pixel_height})")
        except pygame.error as e:
            print(f"ERROR STATE: Failed to create map_content_surface ({safe_width}x{safe_height}). Pygame error: {e}")
            traceback.print_exc()
            try:
                self.map_content_surface = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE)) # Minimal fallback
                print(f"ERROR STATE: Falling back to minimal {ED_CONFIG.DEFAULT_GRID_SIZE}x{ED_CONFIG.DEFAULT_GRID_SIZE} map_content_surface.")
            except Exception as e_fallback:
                print(f"CRITICAL STATE: Failed to create even fallback map_content_surface: {e_fallback}")
                self.map_content_surface = None # Cannot create any surface
                traceback.print_exc()


    def get_map_pixel_width(self) -> int:
        return self.map_width_tiles * self.grid_size

    def get_map_pixel_height(self) -> int:
        return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration: float = 3.0):
        self.status_message = message
        self.status_message_duration = duration
        self.status_message_timer = duration 
        print(f"STATUS MSG: {message} (duration: {duration:.1f}s)")

    def update_status_message(self, dt: float):
        if self.status_message and self.status_message_timer > 0:
            self.status_message_timer -= dt
            if self.status_message_timer <= 0:
                self.status_message = None
                self.status_message_timer = 0.0

    def reset_map_context(self):
        """Resets map-specific attributes, typically when returning to menu or after creating/loading a new map."""
        print("DEBUG STATE: reset_map_context called.")
        self.map_name_for_function = "untitled_map"
        self.current_map_filename = None
        self.placed_objects = []
        self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.camera_offset_x = 0
        self.camera_offset_y = 0
        self.unsaved_changes = False
        self.selected_asset_editor_key = None # Deselect any asset
        self.selected_asset_image_for_cursor = None
        # self.recreate_map_content_surface() # Usually called by the function that triggers the reset (e.g. init_new_map)
        print(f"DEBUG STATE: Map context reset complete. Map name: '{self.map_name_for_function}', Unsaved changes: {self.unsaved_changes}")