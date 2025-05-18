# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.21 (Call handle_dialog_key_repeat and reset its flag)
Level Editor for the Platformer Game (Pygame Only).
Allows creating, loading, and saving game levels visually.
"""
import pygame
import sys
import os
from typing import Tuple, Dict, Optional, Any, List, Callable # Keep these
import traceback
import math # For sqrt in camera momentum
import logging

# --- Logger Setup ---
# (Your existing logger setup remains unchanged)
logger = None
log_file_path_for_error_msg = "Not determined"
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir, 'logs')

    if not os.path.exists(logs_dir):
        print(f"Attempting to create logs directory: {logs_dir}")
        os.makedirs(logs_dir)
        print(f"Logs directory created (or already existed at {logs_dir}).")
    else:
        print(f"Logs directory already exists at: {logs_dir}")

    log_file_path_for_error_msg = os.path.join(logs_dir, 'editor_debug.log')
    print(f"Attempting to configure logging to file: {log_file_path_for_error_msg}")

    for handler in logging.root.handlers[:]: # Remove any pre-existing handlers
        logging.root.removeHandler(handler)
        handler.close() # Close handler before removing

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path_for_error_msg, mode='w'), # Overwrite log file each run
        ],
    )
    logger = logging.getLogger(__name__) # Use a named logger for your editor
    logger.info("Editor session started. Logging initialized successfully to file.")
    print(f"LOGGING INITIALIZED. Log file should be at: {log_file_path_for_error_msg}")

except Exception as e_log:
    print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(f"CRITICAL ERROR DURING LOGGING SETUP: {e_log}")
    print(f"Traceback for logging error:")
    traceback.print_exc()
    print(f"Log file might not be created due to this error.")
    print(f"Attempted log file path was: {log_file_path_for_error_msg}")
    print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    # Fallback to console logging if file logging fails
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE LOG (File log failed): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("File logging setup failed. Switched to console logging only for this session.")
# --- End Logger Setup ---

# --- sys.path modification and constants import ---
try:
    # Dynamically add the project root to sys.path to find 'constants.py'
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Goes up one level from 'editor'
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        if logger: logger.debug(f"Added project root '{project_root}' to sys.path for module imports.")
    else:
        if logger: logger.debug(f"Project root '{project_root}' already in sys.path.")

    import constants as C_imported # Import your main game constants
    if logger: logger.info(f"Successfully imported 'constants as C_imported'. TILE_SIZE: {getattr(C_imported, 'TILE_SIZE', 'NOT FOUND')}")

except ImportError as e_imp:
    if logger:
        logger.critical(f"Failed to import 'constants'. Error: {e_imp}", exc_info=True)
        logger.critical(f"Current sys.path: {sys.path}")
        logger.critical(f"Calculated project_root: {project_root if 'project_root' in locals() else 'Not calculated'}")
    print("ERROR: Could not import 'constants.py'. Ensure it is in the project root directory, one level above the 'editor' directory.")
    sys.exit("ImportError for constants.py")
except Exception as e_gen_imp:
    if logger: logger.critical(f"An unexpected error occurred during constants import: {e_gen_imp}", exc_info=True)
    sys.exit("Generic error during constants import.")
# --- End sys.path modification and constants import ---

# --- Editor module imports ---
try:
    import editor_config as ED_CONFIG
    from editor_state import EditorState
    import editor_ui
    import editor_assets
    import editor_map_utils
    import editor_drawing
    import editor_history # For Undo/Redo functionality
    from editor_handlers_global import handle_global_events
    from editor_handlers_dialog import handle_dialog_events, handle_dialog_key_repeat # MODIFIED: Import new function
    from editor_handlers_menu import handle_menu_events # start_rename_map_flow is called from here
    from editor_handlers_map_editing import handle_editing_map_events
    from editor_updates import update_continuous_camera_pan, update_asset_palette_scroll_momentum
    if logger: logger.debug("Successfully imported all editor-specific modules including new handlers and history.")
except ImportError as e_editor_mod:
    if logger: logger.critical(f"Failed to import an editor-specific module. Error: {e_editor_mod}", exc_info=True)
    print(f"ERROR: Failed to import an editor module. Check sys.path and module names. Current sys.path: {sys.path}")
    sys.exit("ImportError for editor module - exiting.")
# --- End Editor module imports ---


def editor_main():
    if logger: logger.info("editor_main() started.")
    try:
        pygame.init()
        if logger: logger.debug("pygame.init() called.")
        
        # Ensure Pygame font module is initialized
        if not pygame.font.get_init():
            if logger: logger.debug("pygame.font not initialized, calling pygame.font.init()")
            pygame.font.init()
        if not pygame.font.get_init(): # Check again
             if logger: logger.critical("pygame.font.init() failed after explicit call! Fonts will not work.")
             # Optionally, exit if fonts are absolutely critical for basic operation
        else:
            if logger: logger.debug("pygame.font.init() confirmed or already initialized.")

        # Ensure maps directory exists
        if not editor_map_utils.ensure_maps_directory_exists():
            if logger: logger.critical("Maps directory issue. Exiting editor.")
            pygame.quit(); sys.exit(1)

        # Create editor screen
        editor_screen = pygame.display.set_mode(
            (ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT),
            pygame.RESIZABLE
        )
        if logger: logger.info(f"Editor screen created: {editor_screen.get_size()}")
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        
        # Initialize editor state and load assets
        editor_state = EditorState()
        editor_assets.load_editor_palette_assets(editor_state) # Load assets for the palette

        # Load fonts (defined in editor_config)
        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"): # Check essential fonts
            if logger: logger.critical("Essential editor fonts (small, medium, or large) are None. Exiting.")
            pygame.quit(); sys.exit(1)
        if logger: logger.debug(f"Fonts from ED_CONFIG.FONT_CONFIG loaded: "
                                f"small={fonts['small'] is not None}, "
                                f"medium={fonts['medium'] is not None}, "
                                f"large={fonts['large'] is not None}, "
                                f"tooltip={fonts['tooltip'] is not None}")

        # Function to calculate UI layout rects based on screen size and mode
        def calculate_layout_rects(screen_width: int, screen_height: int, current_mode: str) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
            # Menu section (left side in "menu" mode)
            menu_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                     ED_CONFIG.MENU_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            menu_rect.width = max(ED_CONFIG.BUTTON_WIDTH_STANDARD + ED_CONFIG.SECTION_PADDING * 2, menu_rect.width) # Ensure min width for buttons
            menu_rect.height = max(menu_rect.height, ED_CONFIG.MENU_SECTION_HEIGHT) # Ensure min height

            # Asset palette section (left side in "editing_map" mode)
            asset_palette_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                            ED_CONFIG.ASSET_PALETTE_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            
            # Map view section (main area)
            map_view_x_start = ED_CONFIG.SECTION_PADDING # Default start
            map_view_width_available = screen_width - (ED_CONFIG.SECTION_PADDING * 2) # Default width

            if current_mode == "menu":
                map_view_x_start = menu_rect.right + ED_CONFIG.SECTION_PADDING
                map_view_width_available = screen_width - map_view_x_start - ED_CONFIG.SECTION_PADDING
            elif current_mode == "editing_map":
                asset_palette_rect.left = ED_CONFIG.SECTION_PADDING # Palette on left
                map_view_x_start = asset_palette_rect.right + ED_CONFIG.SECTION_PADDING
                map_view_width_available = screen_width - map_view_x_start - ED_CONFIG.SECTION_PADDING

            map_view_rect = pygame.Rect(map_view_x_start, ED_CONFIG.SECTION_PADDING,
                                        map_view_width_available, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            map_view_rect.width = max(map_view_rect.width, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Ensure min map view width
            map_view_rect.height = max(map_view_rect.height, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Ensure min map view height
            return menu_rect, asset_palette_rect, map_view_rect

        # Initial layout calculation
        current_screen_width, current_screen_height = editor_screen.get_size()
        menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
            current_screen_width, current_screen_height, editor_state.current_editor_mode
        )
        if logger: logger.debug(f"Initial Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")

        # --- Main Editor Loop ---
        running = True
        if logger: logger.info("Entering main editor loop.")
        loop_count = 0 # For debugging if needed
        while running:
            loop_count += 1
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0 # Delta time in seconds
            dt = min(dt, 0.1) # Cap dt to prevent large jumps if frame rate drops significantly

            mouse_pos = pygame.mouse.get_pos() # Get current mouse position once per frame
            
            # MODIFIED: Reset key repeat action flag at the start of each frame if a dialog is active
            if editor_state.active_dialog_type:
                editor_state.key_repeat_action_performed_this_frame = False 

            events = pygame.event.get() # Get all events for this frame

            editor_state.update_status_message(dt) # Update timer for status messages
            previous_mode = editor_state.current_editor_mode # For detecting mode changes
            previous_dialog_type = editor_state.active_dialog_type # For detecting dialog changes
            layout_needs_recalc = False # Flag to recalculate UI layout if screen resizes or mode changes

            # --- Continuous Updates (called every frame, independent of events) ---
            if editor_state.current_editor_mode == "editing_map" and not editor_state.active_dialog_type:
                update_continuous_camera_pan(editor_state, map_view_section_rect, mouse_pos, dt) # For WASD/edge pan

                # Calculate available height for the scrollable asset list in the palette
                asset_list_visible_height = (
                    asset_palette_section_rect.height
                    - ED_CONFIG.ASSET_PALETTE_HEADER_AREA_HEIGHT # Space for "Palette Options" dropdown
                    - ED_CONFIG.MINIMAP_AREA_HEIGHT # Space for the minimap
                    - (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2) # Space for BG Color button
                )
                asset_list_visible_height = max(0, asset_list_visible_height) # Ensure non-negative

                update_asset_palette_scroll_momentum( # For smooth scrolling of asset list
                    editor_state, dt,
                    asset_list_visible_height,
                    editor_state.total_asset_palette_content_height
                )
            # --- End Continuous Updates ---


            # --- Event Processing Loop ---
            for event_idx, event in enumerate(events):
                # Handle screen resize
                if event.type == pygame.VIDEORESIZE:
                    if logger: logger.info(f"VIDEORESIZE event to {event.w}x{event.h}")
                    current_screen_width, current_screen_height = event.w, event.h
                    try:
                        editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                    except pygame.error as e_resize:
                        if logger: logger.error(f"Pygame error on resize to {current_screen_width}x{current_screen_height}: {e_resize}", exc_info=True)
                    layout_needs_recalc = True
                    editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
                    editor_state.minimap_needs_regeneration = True # Minimap needs to be redrawn for new size

                # Handle global events (like QUIT)
                if not handle_global_events(event, editor_state, editor_screen):
                    if logger: logger.info("handle_global_events returned False (QUIT). Setting running=False.")
                    running = False; break # Exit main loop if QUIT processed
                if not running: break # Exit event loop if running is false

                # Handle events based on whether a dialog is active
                if editor_state.active_dialog_type:
                    handle_dialog_events(event, editor_state) # Pass event to dialog handler
                    # Check if dialog action changed the dialog type or editor mode
                    if editor_state.active_dialog_type != previous_dialog_type:
                        if logger: logger.debug(f"Dialog type changed from '{previous_dialog_type}' to '{editor_state.active_dialog_type}' after handle_dialog_events.")
                        if editor_state.current_editor_mode != previous_mode: # If dialog also changed mode
                            if logger: logger.debug(f"Mode changed (likely via dialog callback) from '{previous_mode}' to '{editor_state.current_editor_mode}'. Triggering layout recalc.")
                            layout_needs_recalc = True
                else: # No active dialog, process mode-specific events
                    if editor_state.current_editor_mode == "menu":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: # Esc in menu quits editor
                            if logger: logger.info("Escape pressed in menu mode. Posting QUIT event.")
                            pygame.event.post(pygame.event.Event(pygame.QUIT)) # Post QUIT to be handled by global_events
                            continue # Skip other menu handlers for this event
                        handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        handle_editing_map_events(event, editor_state, asset_palette_section_rect, map_view_section_rect, editor_screen)

                # If mode changed during event processing, flag for layout recalculation
                if editor_state.current_editor_mode != previous_mode:
                    if logger: logger.debug(f"Mode changed from '{previous_mode}' to '{editor_state.current_editor_mode}' after specific event handlers. Triggering layout recalc.")
                    layout_needs_recalc = True
            
            if not running: break # Exit main loop if running became false during event processing
            # --- End Event Processing Loop ---

            # --- Handle Key Repeat for Dialogs (called every frame if dialog is active) ---
            if editor_state.active_dialog_type:
                handle_dialog_key_repeat(editor_state) # MODIFIED: Call the key repeat handler
            # --- End Key Repeat Handling ---

            # --- Camera Momentum (fling) ---
            # Apply if in editing mode, no dialog, mouse NOT over map, and momentum exists, and no WASD pan
            if editor_state.current_editor_mode == "editing_map" and \
               not editor_state.active_dialog_type and \
               not editor_state.is_mouse_over_map_view and \
               (abs(editor_state.camera_momentum_pan[0]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or \
                abs(editor_state.camera_momentum_pan[1]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD) and \
                not (pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_d] or \
                     pygame.key.get_pressed()[pygame.K_w] or pygame.key.get_pressed()[pygame.K_s]):

                cam_vx, cam_vy = editor_state.camera_momentum_pan
                # Dampen momentum (frame-rate independent)
                damping_this_frame = ED_CONFIG.CAMERA_MOMENTUM_DAMPING_FACTOR ** (dt * 60.0) # Scale damping as if 60fps
                cam_vx *= damping_this_frame
                cam_vy *= damping_this_frame
                
                # Apply momentum to camera offset
                editor_state.camera_offset_x += cam_vx * dt
                editor_state.camera_offset_y += cam_vy * dt

                # Clamp camera to map boundaries
                max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_section_rect.width)
                max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_section_rect.height)
                boundary_hit_momentum = False # Flag if momentum hits a boundary
                if editor_state.camera_offset_x <= 0:
                    editor_state.camera_offset_x = 0; cam_vx = 0; boundary_hit_momentum = True
                elif editor_state.camera_offset_x >= max_cam_x:
                    editor_state.camera_offset_x = max_cam_x; cam_vx = 0; boundary_hit_momentum = True
                if editor_state.camera_offset_y <= 0:
                    editor_state.camera_offset_y = 0; cam_vy = 0; boundary_hit_momentum = True
                elif editor_state.camera_offset_y >= max_cam_y:
                    editor_state.camera_offset_y = max_cam_y; cam_vy = 0; boundary_hit_momentum = True

                editor_state.camera_offset_x = int(editor_state.camera_offset_x) # Ensure integer offsets
                editor_state.camera_offset_y = int(editor_state.camera_offset_y)

                # Stop momentum if speed is too low or boundary hit
                if math.sqrt(cam_vx**2 + cam_vy**2) < ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or boundary_hit_momentum:
                    editor_state.camera_momentum_pan = (0.0, 0.0)
                else:
                    editor_state.camera_momentum_pan = (cam_vx, cam_vy)
            # --- End Camera Momentum ---

            # --- Recalculate Layout if Needed ---
            if layout_needs_recalc:
                if logger: logger.debug(f"Recalculating layout. Current Mode: '{editor_state.current_editor_mode}', Screen: {current_screen_width}x{current_screen_height}")
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                if logger: logger.debug(f"New Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                
                # Adjust camera offset if map view size changed and camera goes out of bounds
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w = editor_state.get_map_pixel_width(); map_px_h = editor_state.get_map_pixel_height()
                    view_w = map_view_section_rect.width; view_h = map_view_section_rect.height
                    if view_w > 0 and view_h > 0 : # Ensure view dimensions are valid
                        max_cam_x_after_resize = max(0, map_px_w - view_w)
                        max_cam_y_after_resize = max(0, map_px_h - view_h)
                        prev_cx_resize, prev_cy_resize = editor_state.camera_offset_x, editor_state.camera_offset_y
                        editor_state.camera_offset_x = max(0,min(editor_state.camera_offset_x, max_cam_x_after_resize))
                        editor_state.camera_offset_y = max(0,min(editor_state.camera_offset_y, max_cam_y_after_resize))
                        if prev_cx_resize!=editor_state.camera_offset_x or prev_cy_resize!=editor_state.camera_offset_y:
                            if logger: logger.debug(f"Camera clamped after resize/layout from ({prev_cx_resize},{prev_cy_resize}) to ({editor_state.camera_offset_x},{editor_state.camera_offset_y}). Max: ({max_cam_x_after_resize},{max_cam_y_after_resize})")
                    else:
                        if logger: logger.warning(f"Map view rect has zero/negative W/H ({view_w}x{view_h}) after layout. Camera not adjusted.")
            # --- End Layout Recalculation ---

            # --- Drawing Phase ---
            editor_screen.fill(ED_CONFIG.C.DARK_GRAY if hasattr(ED_CONFIG.C, 'DARK_GRAY') else (50,50,50)) # Background

            # Draw based on current editor mode
            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                # Draw a placeholder for the map area when in menu mode
                placeholder_map_area_rect = pygame.Rect(menu_section_rect.right + ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                      current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING*2,
                                      current_screen_height - ED_CONFIG.SECTION_PADDING*2)
                if placeholder_map_area_rect.width > 10 and placeholder_map_area_rect.height > 10: 
                    pygame.draw.rect(editor_screen, (20,20,20), placeholder_map_area_rect) # Dark placeholder bg
                    font_large_for_placeholder = fonts.get("large")
                    if font_large_for_placeholder:
                        placeholder_text_surf = font_large_for_placeholder.render("Map Editor Area",True,(60,60,60)) # Dim text
                        editor_screen.blit(placeholder_text_surf,
                                           placeholder_text_surf.get_rect(center=placeholder_map_area_rect.center))
            elif editor_state.current_editor_mode == "editing_map":
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos, map_view_section_rect)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)

            # Draw active dialog (if any) on top of everything else
            if editor_state.active_dialog_type:
                editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)

            # Draw tooltip (if any)
            font_tooltip_for_draw = fonts.get("tooltip")
            if font_tooltip_for_draw:
                editor_ui.draw_tooltip(editor_screen, editor_state, font_tooltip_for_draw)

            # Draw status message (if any)
            font_small_for_status = fonts.get("small")
            if font_small_for_status:
                editor_ui.draw_status_message(editor_screen, editor_state, font_small_for_status)

            pygame.display.flip() # Update the full screen
            # --- End Drawing Phase ---

    except Exception as e_main_loop: # Catch any unhandled exceptions in the main loop
        if logger: logger.critical(f"CRITICAL ERROR in editor_main loop: {e_main_loop}", exc_info=True)
        else: print(f"CRITICAL ERROR in editor_main loop (logger not available): {e_main_loop}")
        traceback.print_exc() # Print traceback to console
    finally: # Cleanup always runs
        if logger: logger.info("Exiting editor_main. Calling pygame.quit().")
        else: print("Exiting editor_main. Calling pygame.quit().")
        pygame.quit()
        if logger: logger.info("Editor session ended.")
        else: print("Editor session ended.")
        sys.exit() # Ensure application exits

if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---")
    editor_main()