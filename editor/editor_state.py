# editor_state.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.17 (Added key repeat state for dialogs)
Defines the EditorState class, which holds all the dynamic state
and data for the level editor.
"""
import pygame
from typing import Optional, Dict, List, Tuple, Any, Callable
import traceback # Keep for potential debugging elsewhere if needed
import logging

import editor_config as ED_CONFIG

logger = logging.getLogger(__name__)

class EditorState:
    def __init__(self):
        logger.debug("Initializing EditorState...")
        # --- Map Data ---
        self.current_map_data: Dict[str, Any] = {} # Can store raw loaded JSON for reference
        self.current_map_filename: Optional[str] = None # Full path to .py game level file being edited/saved
        self.current_json_filename: Optional[str] = None # Full path to .json editor save file being edited/saved
        self.map_name_for_function: str = "untitled_map" # Base name used in Python function calls, no extension
        self.map_width_tiles: int = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles: int = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.grid_size: int = ED_CONFIG.DEFAULT_GRID_SIZE
        self.background_color: Tuple[int, int, int] = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.map_content_surface: Optional[pygame.Surface] = None # Surface for drawing the map content

        # --- Minimap State ---
        self.minimap_surface: Optional[pygame.Surface] = None # Scaled surface for the minimap display
        self.minimap_needs_regeneration: bool = True # Flag to trigger minimap redraw
        self.minimap_rect_in_palette: Optional[pygame.Rect] = None # Actual rect of minimap on screen
        self.is_dragging_minimap_view: bool = False # If user is dragging the camera view box on minimap

        # --- Placed Objects and Properties ---
        self.placed_objects: List[Dict[str, Any]] = [] # List of all objects placed on the map
        self.asset_specific_variables: Dict[str, Dict[str, Any]] = {} # For custom properties per asset type

        # --- Asset Palette State ---
        self.assets_palette: Dict[str, Dict[str, Any]] = {} # Loaded assets for the palette UI
        self._selected_asset_editor_key: Optional[str] = None # Key of the currently selected asset for placement
        self.selected_asset_image_for_cursor: Optional[pygame.Surface] = None # Semi-transparent image at cursor
        self.asset_palette_scroll_y: float = 0.0 # Current scroll position of the asset list
        self.asset_palette_scroll_momentum: float = 0.0 # For smooth scrolling/fling
        self.total_asset_palette_content_height: int = 0 # Calculated total height of scrollable asset items

        # Asset Palette Options Dropdown
        self.asset_palette_options_dropdown_open: bool = False
        self.asset_palette_options_rects: Dict[str, pygame.Rect] = {} # Rects for dropdown items
        self.asset_palette_options_button_rect: Optional[pygame.Rect] = None # Rect for the main options button

        # --- Camera and View State ---
        self.camera_offset_x: int = 0 # Top-left X of the visible map area
        self.camera_offset_y: int = 0 # Top-left Y of the visible map area
        self.show_grid: bool = True # If grid lines should be drawn on map

        # Mouse and Camera Momentum (for map view panning)
        self.last_mouse_pos_map_view: Optional[Tuple[int, int]] = None # Last mouse pos when over map view
        self.mouse_velocity_map_view: Tuple[float, float] = (0.0, 0.0) # Calculated mouse speed
        self.camera_momentum_pan: Tuple[float, float] = (0.0, 0.0) # For smooth camera panning after drag/fling
        self.is_mouse_over_map_view: bool = False # If mouse is currently over the map editing area

        # --- Editing Tool State ---
        self.dragging_object_index: Optional[int] = None # Index of object being dragged from placed_objects
        self.drag_start_mouse_map_x: int = 0 # World X where drag started
        self.drag_start_mouse_map_y: int = 0 # World Y where drag started
        self.drag_object_original_x: int = 0 # Original X of object being dragged
        self.drag_object_original_y: int = 0 # Original Y of object being dragged
        self.is_painting_tiles: bool = False # If left mouse is held for continuous placement
        self.last_painted_tile_coords: Optional[Tuple[int, int]] = None # Last grid cell painted to avoid duplicates
        self.is_erasing_tiles: bool = False # If right mouse is held for continuous erase
        self.last_erased_tile_coords: Optional[Tuple[int, int]] = None # Last grid cell erased
        self.is_multi_deleting: bool = False # Legacy or alternative erase flag (check usage)
        self.last_multi_deleted_grid_coords: Optional[Tuple[int, int]] = None # Legacy

        # --- Editor Mode and UI State ---
        self._current_editor_mode: str = "menu" # "menu" or "editing_map"
        self.unsaved_changes: bool = False # If there are changes not saved to JSON/PY
        self.hovered_tooltip_text: Optional[str] = None # Text for current tooltip
        self.hovered_tooltip_pos: Optional[Tuple[int, int]] = None # Position for tooltip
        self.ui_elements_rects: Dict[str, Any] = {} # Cache for various UI element rects (buttons, etc.)
        
        # --- Dialog System State ---
        self._active_dialog_type: Optional[str] = None # e.g., "text_input", "color_picker", "file_load"
        self.dialog_prompt_message: str = "" # Message displayed at the top of the dialog
        self.dialog_rect: Optional[pygame.Rect] = None # Calculated rect of the active dialog
        self.dialog_callback_confirm: Optional[Callable[..., None]] = None # Function to call on dialog confirm
        self.dialog_callback_cancel: Optional[Callable[[], None]] = None # Function to call on dialog cancel
        
        # Text Input Dialog Specific
        self.dialog_input_text: str = "" # Current text in the input box
        self.dialog_input_default: str = "" # Default text provided when dialog opened
        self.dialog_input_text_selected: bool = False # If all text in input box is selected (for overwrite)
        
        # Color Picker Dialog Specific
        self.color_picker_rects: Dict[str, pygame.Rect] = {} # Rects for color swatches
        
        # File Load Dialog Specific
        self.dialog_file_list: List[str] = [] # List of actual filenames (with extension)
        self.dialog_file_display_list: List[str] = [] # List of filenames for display (without extension)
        self.dialog_file_scroll_y: int = 0 # Scroll position for the file list
        self.dialog_selected_file_index: int = -1 # Index of the currently selected file in the list
        self.is_dragging_scrollbar: bool = False # If scrollbar handle is being dragged
        self.scrollbar_drag_mouse_offset_y: int = 0 # Offset for smoother scrollbar dragging
        
        # Asset Properties Editor Dialog Specific (if you add this feature)
        self.dialog_asset_properties_selected_key: Optional[str] = None
        self.dialog_asset_properties_temp_values: Dict[str, Any] = {}
        self.dialog_asset_properties_input_field_rects: Dict[str, pygame.Rect] = {}
        self.dialog_asset_properties_scroll_y: float = 0.0
        self.dialog_asset_properties_dropdown_open: bool = False
        self.dialog_asset_properties_dropdown_rect: Optional[pygame.Rect] = None
        self.dialog_asset_properties_dropdown_option_rects: List[pygame.Rect] = []

        # --- Key Repeat State for Dialogs (e.g., Backspace) ---
        self.key_repeat_delay_ms: int = 400  # Initial delay (ms) before repeat starts for a held key
        self.key_repeat_interval_ms: int = 50 # Interval (ms) between subsequent repeats
        self.key_held_down: Optional[int] = None # Stores the pygame.K_ key code of the key being held for repeat
        self.key_held_down_timer_start: float = 0.0 # pygame.time.get_ticks() when key was pressed/last repeat
        # This flag indicates if a repeat action has already happened *within the current key_repeat_interval_ms*
        # or if the *initial* action from KEYDOWN has occurred for the current hold.
        # It helps differentiate the first action (from KEYDOWN or initial delay) from subsequent interval-based repeats.
        self.key_repeat_action_performed_this_frame: bool = False 
        self._key_repeat_initial_delay_passed: bool = False # Tracks if the initial longer delay has passed for current key hold

        # --- Miscellaneous State ---
        self.map_name_for_function_input: str = "" # Temporary storage for map name during new map creation flow
        self.status_message: Optional[str] = None # Message displayed at bottom of screen
        self.status_message_timer: float = 0.0 # Countdown for status message display
        self.status_message_duration: float = 3.0 # Default duration for status messages

        # --- Undo/Redo Stacks ---
        self.undo_stack: List[str] = [] # Stores serialized JSON strings of map states for undo
        self.redo_stack: List[str] = [] # Stores serialized JSON strings for redo

        self.recreate_map_content_surface() # Initialize the map drawing surface
        logger.debug("EditorState initialized.")


    @property
    def current_editor_mode(self) -> str:
        return self._current_editor_mode

    @current_editor_mode.setter
    def current_editor_mode(self, value: str):
        if self._current_editor_mode != value:
            logger.debug(f"Changing editor mode from '{self._current_editor_mode}' to '{value}'")
            self._current_editor_mode = value
            # Reset mode-specific states when changing modes
            if value == "editing_map":
                self.minimap_needs_regeneration = True
                self.camera_momentum_pan = (0.0, 0.0) # Stop camera fling
                self.asset_palette_scroll_momentum = 0.0 # Stop palette fling
                self.asset_palette_options_dropdown_open = False # Close dropdown
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
                # Stop any ongoing editor interactions that might conflict with dialog
                self.camera_momentum_pan = (0.0, 0.0)
                self.asset_palette_scroll_momentum = 0.0
                self.key_held_down = None # Reset key repeat when a new dialog opens/type changes
                self.key_repeat_action_performed_this_frame = False
                self._key_repeat_initial_delay_passed = False
            else: # Dialog is closing (value is None)
                self.dialog_input_text_selected = False # Reset text selection state
                # Reset specific dialog states when *any* dialog closes to ensure clean slate
                self.dialog_asset_properties_selected_key = None
                self.dialog_asset_properties_temp_values.clear()
                self.dialog_asset_properties_input_field_rects.clear()
                self.dialog_asset_properties_dropdown_open = False
                self.key_held_down = None # Reset key repeat state
                self.key_repeat_action_performed_this_frame = False
                self._key_repeat_initial_delay_passed = False


            # Clean up UI element rects associated with the closing dialog
            if old_dialog_type is not None and old_dialog_type != value: # If a dialog was actually closed
                keys_to_remove = []
                if old_dialog_type == "file_load":
                    keys_to_remove.extend(['dialog_file_item_rects', 'file_dialog_scrollbar_handle',
                                           'file_dialog_scrollbar_area', 'dialog_file_load_ok', 'dialog_file_load_cancel'])
                elif old_dialog_type == "color_picker":
                    self.color_picker_rects.clear() # Specific handling for color_picker_rects
                elif old_dialog_type == "text_input":
                    keys_to_remove.append('dialog_text_input_box')
                elif old_dialog_type == "asset_properties_editor": # Example for a future dialog
                    keys_to_remove.extend(['dialog_asset_prop_dropdown_button',
                                           'dialog_asset_prop_save_button', 
                                           'dialog_asset_prop_close_button',
                                           'dialog_asset_prop_item_input_fields',
                                           'dialog_asset_prop_scrollbar_handle',
                                           'dialog_asset_prop_scrollbar_area'])
                    self.dialog_asset_properties_input_field_rects.clear() # Clear specific dict


                for key in keys_to_remove: # Remove from general UI rects cache
                    if key in self.ui_elements_rects:
                        try: del self.ui_elements_rects[key]
                        except KeyError: pass # Ignore if already removed
            
            if value is None: # Reset general dialog properties if no new dialog is opening
                self.dialog_rect = None
                self.dialog_prompt_message = ""
                self.dialog_callback_confirm = None
                self.dialog_callback_cancel = None

    @property
    def selected_asset_editor_key(self) -> Optional[str]:
        return self._selected_asset_editor_key

    @selected_asset_editor_key.setter
    def selected_asset_editor_key(self, value: Optional[str]):
        # Update only if value changes OR if image for cursor needs recreation
        if self._selected_asset_editor_key != value or \
           (value is not None and value in self.assets_palette and self.selected_asset_image_for_cursor is None):

            self._selected_asset_editor_key = value
            logger.info(f"selected_asset_editor_key changed to: '{value}'")

            if value is None: # No asset selected
                self.selected_asset_image_for_cursor = None
            elif value in self.assets_palette: # Valid asset selected
                asset_data = self.assets_palette[value]
                original_image = asset_data.get("image")
                if original_image:
                    # Create a modifiable copy for the cursor visual
                    cursor_image = original_image.copy()
                    
                    # 1. Apply transparency to cursor image
                    cursor_image.set_alpha(ED_CONFIG.CURSOR_ASSET_ALPHA)
                    
                    # 2. Apply hue overlay for visual distinction
                    hue_overlay = pygame.Surface(cursor_image.get_size(), pygame.SRCALPHA)
                    hue_overlay.fill(ED_CONFIG.CURSOR_ASSET_HUE_COLOR) # (R, G, B, Alpha_for_hue_strength)
                    
                    cursor_image.blit(hue_overlay, (0,0), special_flags=pygame.BLEND_RGBA_ADD) # Blend hue onto image

                    self.selected_asset_image_for_cursor = cursor_image
                    logger.debug(f"Asset '{value}' selected. Cursor image processed with transparency and hue.")
                else: # Selected asset has no image in palette (should not happen if palette loaded correctly)
                    self.selected_asset_image_for_cursor = None
                    logger.warning(f"Asset '{value}' selected, but has no image in palette.")
            else: # Asset key not found in palette
                self.selected_asset_image_for_cursor = None
                logger.warning(f"Asset key '{value}' not found in assets_palette during selection.")


    def recreate_map_content_surface(self):
        """Creates or recreates the main surface where map content is drawn."""
        map_pixel_width = self.map_width_tiles * self.grid_size
        map_pixel_height = self.map_height_tiles * self.grid_size
        # Ensure surface dimensions are at least 1x1
        safe_width, safe_height = max(1, map_pixel_width), max(1, map_pixel_height)
        try:
            self.map_content_surface = pygame.Surface((safe_width, safe_height))
            self.minimap_needs_regeneration = True # New surface means minimap needs update
            logger.debug(f"Recreated map_content_surface: {safe_width}x{safe_height}")
        except pygame.error as e:
            logger.error(f"Failed to create map_content_surface ({safe_width}x{safe_height}): {e}", exc_info=True)
            # Fallback to a tiny surface if creation fails
            try:
                self.map_content_surface = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE))
                logger.warning("Created fallback map_content_surface.")
            except Exception as e_fallback: # If even fallback fails
                self.map_content_surface = None
                logger.critical(f"Fallback map_content_surface creation also failed: {e_fallback}", exc_info=True)


    def get_map_pixel_width(self) -> int:
        """Returns the current map width in pixels."""
        return self.map_width_tiles * self.grid_size

    def get_map_pixel_height(self) -> int:
        """Returns the current map height in pixels."""
        return self.map_height_tiles * self.grid_size

    def set_status_message(self, message: str, duration: float = 3.0):
        """Sets a status message to be displayed temporarily."""
        self.status_message = message
        self.status_message_duration = duration
        self.status_message_timer = duration # Reset timer
        logger.info(f"Status message set: '{message}' for {duration}s")

    def update_status_message(self, dt: float):
        """Updates the timer for the status message. dt is delta time in seconds."""
        if self.status_message and self.status_message_timer > 0:
            self.status_message_timer -= dt
            if self.status_message_timer <= 0: # Timer expired
                self.status_message = None
                self.status_message_timer = 0.0

    def reset_map_context(self):
        """Resets all map-specific data to defaults, e.g., when creating a new map or exiting editor mode."""
        logger.debug("Resetting map context (for new map or exiting edit mode).")
        self.map_name_for_function = "untitled_map"
        self.current_map_filename = None
        self.current_json_filename = None
        self.placed_objects = []
        self.asset_specific_variables.clear() # Clear any custom properties
        self.map_width_tiles = ED_CONFIG.DEFAULT_MAP_WIDTH_TILES
        self.map_height_tiles = ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES
        self.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
        self.camera_offset_x, self.camera_offset_y = 0, 0
        self.unsaved_changes = False # New/reset map has no unsaved changes initially
        self.selected_asset_editor_key, self.selected_asset_image_for_cursor = None, None
        # Reset editing tool states
        self.is_painting_tiles, self.last_painted_tile_coords = False, None
        self.is_erasing_tiles, self.last_erased_tile_coords = False, None
        self.is_multi_deleting, self.last_multi_deleted_grid_coords = False, None
        self.dragging_object_index = None
        # Reset view and interaction states
        self.minimap_needs_regeneration = True
        self.last_mouse_pos_map_view = None
        self.mouse_velocity_map_view = (0.0, 0.0)
        self.camera_momentum_pan = (0.0, 0.0)
        self.asset_palette_scroll_momentum = 0.0
        self.asset_palette_scroll_y = 0.0
        self.dialog_input_text_selected = False
        self.is_mouse_over_map_view = False
        self.is_dragging_minimap_view = False
        # Clear history
        self.undo_stack.clear()
        self.redo_stack.clear()
        # Reset UI elements related to specific map editing
        self.asset_palette_options_dropdown_open = False
        # Reset key repeat state
        self.key_held_down = None
        self.key_repeat_action_performed_this_frame = False
        self._key_repeat_initial_delay_passed = False
        
        logger.debug(f"Map context reset complete. Current map name: '{self.map_name_for_function}'.")