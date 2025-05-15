# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.18 (Modular event handlers and updates)
Level Editor for the Platformer Game (Pygame Only).
Allows creating, loading, and saving game levels visually.
"""
import pygame
import sys
import os
from typing import Tuple, Dict, Optional, Any, List, Callable
import traceback
import math
import logging

# --- Logger Setup ---
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

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path_for_error_msg, mode='w'),
        ],
    )
    logger = logging.getLogger(__name__)
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
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE LOG (File log failed): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("File logging setup failed. Switched to console logging only for this session.")
# --- End Logger Setup ---

# --- sys.path modification and constants import ---
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logger.debug(f"Added project root '{project_root}' to sys.path.")
    else:
        logger.debug(f"Project root '{project_root}' already in sys.path.")

    import constants as C_imported 
    logger.info(f"Successfully imported 'constants as C_imported'. TILE_SIZE: {getattr(C_imported, 'TILE_SIZE', 'NOT FOUND')}")

except ImportError as e_imp:
    logger.critical(f"Failed to import 'constants'. Error: {e_imp}", exc_info=True)
    logger.critical(f"Current sys.path: {sys.path}")
    logger.critical(f"Calculated project_root: {project_root if 'project_root' in locals() else 'Not calculated'}")
    print("ERROR: Could not import 'constants.py'. Ensure it is in the project root directory, one level above the 'editor' directory.")
    sys.exit("ImportError for constants.py")
except Exception as e_gen_imp:
    logger.critical(f"An unexpected error occurred during constants import: {e_gen_imp}", exc_info=True)
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
    # Import the new handler and update modules
    from editor_handlers_global import handle_global_events
    from editor_handlers_dialog import handle_dialog_events
    from editor_handlers_menu import handle_menu_events
    from editor_handlers_map_editing import handle_editing_map_events 
    from editor_updates import update_continuous_camera_pan, update_asset_palette_scroll_momentum
    logger.debug("Successfully imported all editor-specific modules including new handlers.")
except ImportError as e_editor_mod:
    logger.critical(f"Failed to import an editor-specific module. Error: {e_editor_mod}", exc_info=True)
    print(f"ERROR: Failed to import an editor module. Check sys.path and module names. Current sys.path: {sys.path}")
    sys.exit("ImportError for editor module - exiting.")
# --- End Editor module imports ---


def editor_main():
    logger.info("editor_main() started.")
    try:
        pygame.init()
        logger.debug("pygame.init() called.")
        if not pygame.font.get_init():
            logger.debug("pygame.font not initialized, calling pygame.font.init()")
            pygame.font.init()
        if not pygame.font.get_init():
             logger.critical("pygame.font.init() failed after explicit call! Fonts will not work.")
        else:
            logger.debug("pygame.font.init() confirmed or already initialized.")

        if not editor_map_utils.ensure_maps_directory_exists():
            logger.critical("Maps directory issue. Exiting.")
            pygame.quit(); sys.exit(1)

        editor_screen = pygame.display.set_mode(
            (ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT),
            pygame.RESIZABLE
        )
        logger.info(f"Editor screen created: {editor_screen.get_size()}")
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        editor_state = EditorState() 
        editor_assets.load_editor_palette_assets(editor_state) 

        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"):
            logger.critical("Essential editor fonts (small, medium, or large) are None. Exiting.")
            pygame.quit(); sys.exit(1)
        logger.debug(f"Fonts from ED_CONFIG.FONT_CONFIG loaded: small={fonts['small'] is not None}, medium={fonts['medium'] is not None}, large={fonts['large'] is not None}, tooltip={fonts['tooltip'] is not None}")

        def calculate_layout_rects(screen_width: int, screen_height: int, current_mode: str) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
            menu_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                     ED_CONFIG.MENU_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            menu_rect.width = max(ED_CONFIG.BUTTON_WIDTH_STANDARD + ED_CONFIG.SECTION_PADDING * 2, menu_rect.width) 
            menu_rect.height = max(menu_rect.height, ED_CONFIG.MENU_SECTION_HEIGHT) 

            asset_palette_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                            ED_CONFIG.ASSET_PALETTE_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2)) 
            map_view_x_start = ED_CONFIG.SECTION_PADDING
            map_view_width_available = screen_width - (ED_CONFIG.SECTION_PADDING * 2)

            if current_mode == "menu":
                map_view_x_start = menu_rect.right + ED_CONFIG.SECTION_PADDING
                map_view_width_available = screen_width - map_view_x_start - ED_CONFIG.SECTION_PADDING
            elif current_mode == "editing_map":
                asset_palette_rect.left = ED_CONFIG.SECTION_PADDING
                map_view_x_start = asset_palette_rect.right + ED_CONFIG.SECTION_PADDING
                map_view_width_available = screen_width - map_view_x_start - ED_CONFIG.SECTION_PADDING

            map_view_rect = pygame.Rect(map_view_x_start, ED_CONFIG.SECTION_PADDING,
                                        map_view_width_available, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            map_view_rect.width = max(map_view_rect.width, ED_CONFIG.DEFAULT_GRID_SIZE * 10)
            map_view_rect.height = max(map_view_rect.height, ED_CONFIG.DEFAULT_GRID_SIZE * 10)
            return menu_rect, asset_palette_rect, map_view_rect

        current_screen_width, current_screen_height = editor_screen.get_size()
        menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
            current_screen_width, current_screen_height, editor_state.current_editor_mode
        )
        logger.debug(f"Initial Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")

        running = True
        logger.info("Entering main loop.")
        loop_count = 0
        while running:
            loop_count += 1
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0
            dt = min(dt, 0.1) 

            mouse_pos = pygame.mouse.get_pos()
            events = pygame.event.get()

            editor_state.update_status_message(dt)
            previous_mode = editor_state.current_editor_mode
            previous_dialog_type = editor_state.active_dialog_type
            layout_needs_recalc = False

            # --- Continuous Updates (called every frame) ---
            if editor_state.current_editor_mode == "editing_map" and not editor_state.active_dialog_type:
                update_continuous_camera_pan(editor_state, map_view_section_rect, mouse_pos, dt)
                
                asset_list_visible_height = (
                    asset_palette_section_rect.height 
                    - ED_CONFIG.MINIMAP_AREA_HEIGHT 
                    - (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2) 
                )
                update_asset_palette_scroll_momentum(
                    editor_state,
                    dt, 
                    asset_list_visible_height,
                    editor_state.total_asset_palette_content_height
                )
            # --- End Continuous Updates ---


            # --- Event Processing ---
            for event_idx, event in enumerate(events):
                if event.type == pygame.VIDEORESIZE: 
                    logger.info(f"VIDEORESIZE event to {event.w}x{event.h}")
                    current_screen_width, current_screen_height = event.w, event.h
                    try: 
                        editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                    except pygame.error as e_resize: 
                        logger.error(f"Pygame error on resize to {current_screen_width}x{current_screen_height}: {e_resize}", exc_info=True)
                    layout_needs_recalc = True
                    editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
                    editor_state.minimap_needs_regeneration = True 
                
                if not handle_global_events(event, editor_state, editor_screen): 
                    logger.info("handle_global_events returned False (QUIT). Setting running=False.")
                    running = False; break
                if not running: break 

                if editor_state.active_dialog_type:
                    handle_dialog_events(event, editor_state)
                    if editor_state.active_dialog_type != previous_dialog_type: 
                        logger.debug(f"Dialog type changed from '{previous_dialog_type}' to '{editor_state.active_dialog_type}' after handle_dialog_events.")
                        if editor_state.current_editor_mode != previous_mode: 
                            logger.debug(f"Mode changed (likely via dialog callback) from '{previous_mode}' to '{editor_state.current_editor_mode}'. Triggering layout recalc.")
                            layout_needs_recalc = True
                else: # No active dialog
                    if editor_state.current_editor_mode == "menu":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            logger.info("Escape pressed in menu. Posting QUIT event.")
                            pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue 
                        handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        handle_editing_map_events(event, editor_state, asset_palette_section_rect, map_view_section_rect, editor_screen)
                
                if editor_state.current_editor_mode != previous_mode: 
                    logger.debug(f"Mode changed from '{previous_mode}' to '{editor_state.current_editor_mode}' after specific event handlers. Triggering layout recalc.")
                    layout_needs_recalc = True
            if not running: break 
            # --- End Event Processing ---


            # --- Camera Momentum (if not handled by direct input/edge scroll) ---
            if editor_state.current_editor_mode == "editing_map" and \
               not editor_state.active_dialog_type and \
               not editor_state.is_mouse_over_map_view and \
               (abs(editor_state.camera_momentum_pan[0]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or \
                abs(editor_state.camera_momentum_pan[1]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD) and \
                not pygame.key.get_pressed()[pygame.K_a] and not pygame.key.get_pressed()[pygame.K_d] and \
                not pygame.key.get_pressed()[pygame.K_w] and not pygame.key.get_pressed()[pygame.K_s] :

                cam_vx, cam_vy = editor_state.camera_momentum_pan
                damping_this_frame = ED_CONFIG.CAMERA_MOMENTUM_DAMPING_FACTOR ** (dt * 60.0) 
                cam_vx *= damping_this_frame
                cam_vy *= damping_this_frame
                editor_state.camera_offset_x += cam_vx * dt
                editor_state.camera_offset_y += cam_vy * dt
                
                max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_section_rect.width)
                max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_section_rect.height)
                boundary_hit = False
                if editor_state.camera_offset_x <= 0:
                    editor_state.camera_offset_x = 0; cam_vx = 0; boundary_hit = True
                elif editor_state.camera_offset_x >= max_cam_x:
                    editor_state.camera_offset_x = max_cam_x; cam_vx = 0; boundary_hit = True
                if editor_state.camera_offset_y <= 0:
                    editor_state.camera_offset_y = 0; cam_vy = 0; boundary_hit = True
                elif editor_state.camera_offset_y >= max_cam_y:
                    editor_state.camera_offset_y = max_cam_y; cam_vy = 0; boundary_hit = True
                
                editor_state.camera_offset_x = int(editor_state.camera_offset_x)
                editor_state.camera_offset_y = int(editor_state.camera_offset_y)

                if math.sqrt(cam_vx**2 + cam_vy**2) < ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or boundary_hit:
                    editor_state.camera_momentum_pan = (0.0, 0.0)
                else:
                    editor_state.camera_momentum_pan = (cam_vx, cam_vy)
            # --- End Camera Momentum ---
            
            if layout_needs_recalc:
                logger.debug(f"Recalculating layout. Current Mode: '{editor_state.current_editor_mode}', Screen: {current_screen_width}x{current_screen_height}")
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                logger.debug(f"New Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w = editor_state.get_map_pixel_width(); map_px_h = editor_state.get_map_pixel_height()
                    view_w = map_view_section_rect.width; view_h = map_view_section_rect.height
                    if view_w > 0 and view_h > 0 :
                        max_cx = max(0, map_px_w - view_w); max_cy = max(0, map_px_h - view_h)
                        prev_cx, prev_cy = editor_state.camera_offset_x, editor_state.camera_offset_y
                        editor_state.camera_offset_x = max(0,min(editor_state.camera_offset_x,max_cx))
                        editor_state.camera_offset_y = max(0,min(editor_state.camera_offset_y,max_cy))
                        if prev_cx!=editor_state.camera_offset_x or prev_cy!=editor_state.camera_offset_y:
                            logger.debug(f"Camera clamped after resize/layout from ({prev_cx},{prev_cy}) to ({editor_state.camera_offset_x},{editor_state.camera_offset_y}). Max: ({max_cx},{max_cy})")
                    else: 
                        logger.warning(f"Map view rect zero/negative W/H ({view_w}x{view_h}). Camera not adjusted.")

            # --- Drawing ---
            editor_screen.fill(ED_CONFIG.C.DARK_GRAY if hasattr(ED_CONFIG.C, 'DARK_GRAY') else (50,50,50)) 

            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                ph_rect = pygame.Rect(menu_section_rect.right + ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                      current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING*2,
                                      current_screen_height - ED_CONFIG.SECTION_PADDING*2)
                if ph_rect.width > 10 and ph_rect.height > 10:
                    pygame.draw.rect(editor_screen, (20,20,20), ph_rect)
                    f_large = fonts.get("large");
                    if f_large: 
                        editor_screen.blit(f_large.render("Map Editor Area",True,(60,60,60)), 
                                           f_large.render("Map Editor Area",True,(60,60,60)).get_rect(center=ph_rect.center))
            elif editor_state.current_editor_mode == "editing_map":
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos, map_view_section_rect)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)

            if editor_state.active_dialog_type: 
                editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)
            
            f_tooltip = fonts.get("tooltip");
            if f_tooltip: 
                editor_ui.draw_tooltip(editor_screen, editor_state, f_tooltip)
            
            f_small = fonts.get("small");
            if f_small: 
                editor_ui.draw_status_message(editor_screen, editor_state, f_small)
            
            pygame.display.flip()
            # --- End Drawing ---

    except Exception as e:
        if logger: logger.critical(f"CRITICAL ERROR in editor_main: {e}", exc_info=True)
        else: print(f"CRITICAL ERROR in editor_main (logger not available): {e}")
        traceback.print_exc()
    finally:
        if logger: logger.info("Exiting editor_main. Calling pygame.quit().")
        else: print("Exiting editor_main. Calling pygame.quit().")
        pygame.quit()
        if logger: logger.info("Editor session ended.")
        else: print("Editor session ended.")
        sys.exit()

if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---") 
    editor_main()