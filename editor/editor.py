# -*- coding: utf-8 -*-
"""
## version 1.0.0.22 (Correct QApplication initialization timing for PySide6)
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

# Attempt to import PySide6 QApplication first
PYSIDE6_QAPP_AVAILABLE = False
QApplication = None
try:
    from PySide6.QtWidgets import QApplication as PySideQApplication
    QApplication = PySideQApplication # Assign to a common name
    PYSIDE6_QAPP_AVAILABLE = True
    print("MAIN: PySide6 QApplication imported successfully.")
except ImportError:
    print("MAIN WARNING: PySide6 QApplication not found. QColorDialog will not work.")
    # Define a dummy QApplication if not available, so calls don't crash immediately
    # although the dialog won't function.
    class _DummyQApplication:
        _instance = None
        def __init__(self, args=None):
            if _DummyQApplication._instance is None:
                _DummyQApplication._instance = self
                print("MAIN: Dummy QApplication initialized.")
        @staticmethod
        def instance():
            return _DummyQApplication._instance
        def exec(self): pass # Dummy exec
        def quit(self): pass # Dummy quit
    QApplication = _DummyQApplication # type: ignore


# --- Logger Setup ---
logger = None
log_file_path_for_error_msg = "Not determined"
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_script_dir, 'logs')
    if not os.path.exists(logs_dir): os.makedirs(logs_dir)
    log_file_path_for_error_msg = os.path.join(logs_dir, 'editor_debug.log')
    for handler in logging.root.handlers[:]: logging.root.removeHandler(handler); handler.close()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
        handlers=[logging.FileHandler(log_file_path_for_error_msg, mode='w')],
    )
    logger = logging.getLogger(__name__)
    logger.info("Editor session started. Logging initialized successfully to file.")
    print(f"LOGGING INITIALIZED. Log file should be at: {log_file_path_for_error_msg}")
except Exception as e_log:
    print(f"CRITICAL ERROR DURING LOGGING SETUP: {e_log}"); traceback.print_exc()
    logging.basicConfig(level=logging.DEBUG, format='CONSOLE LOG (File log failed): %(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("File logging setup failed. Switched to console logging only for this session.")
# --- End Logger Setup ---

# --- sys.path modification and constants import ---
try:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        if logger: logger.debug(f"Added project root '{project_root}' to sys.path.")
    import constants as C_imported
    if logger: logger.info(f"Successfully imported 'constants as C_imported'.")
except ImportError as e_imp:
    if logger: logger.critical(f"Failed to import 'constants'. Error: {e_imp}", exc_info=True)
    sys.exit("ImportError for constants.py")
# --- End sys.path modification ---


# --- Editor module imports ---
try:
    import editor_config as ED_CONFIG
    from editor_state import EditorState
    import editor_ui
    import editor_assets
    import editor_map_utils
    import editor_drawing
    import editor_history
    from editor_handlers_global import handle_global_events
    from editor_handlers_dialog import handle_dialog_events, handle_dialog_key_repeat
    from editor_handlers_menu import handle_menu_events
    from editor_handlers_map_editing import handle_editing_map_events
    from editor_updates import update_continuous_camera_pan, update_asset_palette_scroll_momentum
    if logger: logger.debug("Successfully imported all editor-specific modules.")
except ImportError as e_editor_mod:
    if logger: logger.critical(f"Failed to import an editor-specific module. Error: {e_editor_mod}", exc_info=True)
    sys.exit("ImportError for editor module - exiting.")
# --- End Editor module imports ---


q_application_instance = None 

def editor_main():
    global q_application_instance # Make sure to use/modify the global instance

    # Initialize QApplication at the VERY BEGINNING of editor_main
    if PYSIDE6_QAPP_AVAILABLE and QApplication is not None: # Check if real QApplication was imported
        q_application_instance = QApplication.instance() # Check if an instance already exists
        if q_application_instance is None:
            # Pass sys.argv. If sys.argv is not available, an empty list is often acceptable.
            app_args = sys.argv if hasattr(sys, 'argv') else []
            q_application_instance = QApplication(app_args)
            if logger: logger.debug("QApplication instance created for PySide6 dialogs.")
        else:
            if logger: logger.debug("QApplication instance already exists.")
    elif QApplication is not None: # This means _DummyQApplication was assigned
        q_application_instance = QApplication() # Create dummy instance
        if logger: logger.warning("Using dummy QApplication as PySide6 is not fully available.")
    else:
        if logger: logger.error("QApplication class (real or dummy) is None. Cannot proceed with Qt dialogs.")

    if logger: logger.info("editor_main() started (after QApplication init attempt).")
    try:
        pygame.init() # Initialize Pygame *after* QApplication
        if logger: logger.debug("pygame.init() called.")
        
        if not pygame.font.get_init():
            if logger: logger.debug("pygame.font not initialized, calling pygame.font.init()")
            pygame.font.init()
        if not pygame.font.get_init():
             if logger: logger.critical("pygame.font.init() failed after explicit call! Fonts will not work.")
        else:
            if logger: logger.debug("pygame.font.init() confirmed or already initialized.")

        if not editor_map_utils.ensure_maps_directory_exists():
            if logger: logger.critical("Maps directory issue. Exiting editor.")
            pygame.quit(); sys.exit(1)

        editor_screen = pygame.display.set_mode(
            (ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT),
            pygame.RESIZABLE
        )
        if logger: logger.info(f"Editor screen created: {editor_screen.get_size()}")
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        
        editor_state = EditorState()
        editor_assets.load_editor_palette_assets(editor_state)

        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"):
            if logger: logger.critical("Essential editor fonts (small, medium, or large) are None. Exiting.")
            pygame.quit(); sys.exit(1)
        if logger: logger.debug(f"Fonts from ED_CONFIG.FONT_CONFIG loaded.")

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
                asset_palette_rect.left = ED_CONFIG.SECTION_PADDING # Asset palette on the left
                map_view_x_start = asset_palette_rect.right + ED_CONFIG.SECTION_PADDING
                map_view_width_available = screen_width - map_view_x_start - ED_CONFIG.SECTION_PADDING
            
            map_view_rect = pygame.Rect(map_view_x_start, ED_CONFIG.SECTION_PADDING,
                                        map_view_width_available, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            
            map_view_rect.width = max(map_view_rect.width, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Ensure min width
            map_view_rect.height = max(map_view_rect.height, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Ensure min height
            
            return menu_rect, asset_palette_rect, map_view_rect

        current_screen_width, current_screen_height = editor_screen.get_size()
        menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
            current_screen_width, current_screen_height, editor_state.current_editor_mode
        )
        if logger: logger.debug(f"Initial Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")

        running = True
        if logger: logger.info("Entering main editor loop.")
        
        while running:
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0
            dt = min(dt, 0.1) # Cap dt to prevent large jumps

            mouse_pos = pygame.mouse.get_pos()
            
            if editor_state.active_dialog_type:
                editor_state.key_repeat_action_performed_this_frame = False 
            
            events = pygame.event.get()

            editor_state.update_status_message(dt)
            previous_mode = editor_state.current_editor_mode
            previous_dialog_type = editor_state.active_dialog_type
            layout_needs_recalc = False

            # --- Continuous Updates ---
            if editor_state.current_editor_mode == "editing_map" and not editor_state.active_dialog_type:
                update_continuous_camera_pan(editor_state, map_view_section_rect, mouse_pos, dt)
                asset_list_visible_height = (
                    asset_palette_section_rect.height
                    - ED_CONFIG.ASSET_PALETTE_HEADER_AREA_HEIGHT 
                    - ED_CONFIG.MINIMAP_AREA_HEIGHT 
                    - (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2) # Approx height of sort buttons
                )
                asset_list_visible_height = max(0, asset_list_visible_height)
                update_asset_palette_scroll_momentum(
                    editor_state, dt,
                    asset_list_visible_height,
                    editor_state.total_asset_palette_content_height
                )
            
            # --- Event Processing ---
            for event_idx, event in enumerate(events):
                if event.type == pygame.VIDEORESIZE:
                    if logger: logger.info(f"VIDEORESIZE event to {event.w}x{event.h}")
                    current_screen_width, current_screen_height = event.w, event.h
                    try:
                        editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                    except pygame.error as e_resize:
                        if logger: logger.error(f"Pygame error on resize: {e_resize}", exc_info=True)
                    layout_needs_recalc = True
                    editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
                    editor_state.minimap_needs_regeneration = True # Minimap needs to be redrawn with new aspect ratio

                if not handle_global_events(event, editor_state, editor_screen):
                    if logger: logger.info("handle_global_events returned False (QUIT).")
                    running = False; break
                if not running: break # Exit event loop if running is false

                if editor_state.active_dialog_type:
                    handle_dialog_events(event, editor_state) 
                    if editor_state.active_dialog_type != previous_dialog_type: # Dialog closed or changed
                        if logger: logger.debug(f"Dialog type changed from '{previous_dialog_type}' to '{editor_state.active_dialog_type}'.")
                        if editor_state.current_editor_mode != previous_mode: # Mode might change after dialog (e.g. New Map)
                            if logger: logger.debug(f"Mode changed via dialog from '{previous_mode}' to '{editor_state.current_editor_mode}'.")
                            layout_needs_recalc = True
                else: # No active dialog
                    if editor_state.current_editor_mode == "menu":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            if logger: logger.info("Escape in menu -> QUIT.")
                            pygame.event.post(pygame.event.Event(pygame.QUIT)) # Post QUIT to be handled by global_events
                            continue 
                        handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        handle_editing_map_events(event, editor_state, asset_palette_section_rect, map_view_section_rect, editor_screen)

                # Check if mode changed outside of dialog context (e.g. from menu to editor)
                if editor_state.current_editor_mode != previous_mode and not editor_state.active_dialog_type:
                    if logger: logger.debug(f"Mode changed from '{previous_mode}' to '{editor_state.current_editor_mode}'.")
                    layout_needs_recalc = True
            if not running: break # Exit main loop if running is false
            
            # --- Handle Key Repeat for Dialogs ---
            if editor_state.active_dialog_type:
                handle_dialog_key_repeat(editor_state)
            
            # --- Camera Momentum ---
            if editor_state.current_editor_mode == "editing_map" and \
               not editor_state.active_dialog_type and \
               not editor_state.is_mouse_over_map_view and \
               (abs(editor_state.camera_momentum_pan[0]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or \
                abs(editor_state.camera_momentum_pan[1]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD) and \
                not (pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_d] or \
                     pygame.key.get_pressed()[pygame.K_w] or pygame.key.get_pressed()[pygame.K_s]): # Don't apply momentum if keys are pressed
                
                cam_vx, cam_vy = editor_state.camera_momentum_pan
                damping_this_frame = ED_CONFIG.CAMERA_MOMENTUM_DAMPING_FACTOR ** (dt * 60.0) # Frame-rate independent damping
                cam_vx *= damping_this_frame
                cam_vy *= damping_this_frame

                editor_state.camera_offset_x += cam_vx * dt
                editor_state.camera_offset_y += cam_vy * dt
                
                max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_section_rect.width)
                max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_section_rect.height)
                
                boundary_hit_momentum = False
                if editor_state.camera_offset_x <= 0: 
                    editor_state.camera_offset_x = 0
                    cam_vx = 0 # Stop momentum in this direction
                    boundary_hit_momentum = True
                elif editor_state.camera_offset_x >= max_cam_x:
                    editor_state.camera_offset_x = max_cam_x
                    cam_vx = 0
                    boundary_hit_momentum = True
                
                if editor_state.camera_offset_y <= 0:
                    editor_state.camera_offset_y = 0
                    cam_vy = 0
                    boundary_hit_momentum = True
                elif editor_state.camera_offset_y >= max_cam_y:
                    editor_state.camera_offset_y = max_cam_y
                    cam_vy = 0
                    boundary_hit_momentum = True

                editor_state.camera_offset_x = int(editor_state.camera_offset_x)
                editor_state.camera_offset_y = int(editor_state.camera_offset_y)

                if math.sqrt(cam_vx**2 + cam_vy**2) < ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or boundary_hit_momentum and (cam_vx == 0 and cam_vy == 0) :
                    editor_state.camera_momentum_pan = (0.0, 0.0)
                else:
                    editor_state.camera_momentum_pan = (cam_vx, cam_vy)

            # --- Recalculate Layout if Needed ---
            if layout_needs_recalc:
                if logger: logger.debug(f"Recalculating layout. Mode: '{editor_state.current_editor_mode}', Screen: {current_screen_width}x{current_screen_height}")
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                if logger: logger.debug(f"New Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                
                # Adjust camera if map view size changed to keep map in bounds
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w = editor_state.get_map_pixel_width()
                    map_px_h = editor_state.get_map_pixel_height()
                    view_w = map_view_section_rect.width
                    view_h = map_view_section_rect.height

                    if view_w > 0 and view_h > 0 : # Ensure view dimensions are positive
                        max_cx_recalc = max(0, map_px_w - view_w)
                        max_cy_recalc = max(0, map_px_h - view_h)
                        
                        prev_cx_recalc, prev_cy_recalc = editor_state.camera_offset_x, editor_state.camera_offset_y
                        
                        editor_state.camera_offset_x = max(0, min(editor_state.camera_offset_x, max_cx_recalc))
                        editor_state.camera_offset_y = max(0, min(editor_state.camera_offset_y, max_cy_recalc))
                        
                        if prev_cx_recalc != editor_state.camera_offset_x or prev_cy_recalc != editor_state.camera_offset_y:
                            if logger: logger.debug(f"Camera clamped after resize/layout change: from ({prev_cx_recalc},{prev_cy_recalc}) to ({editor_state.camera_offset_x},{editor_state.camera_offset_y}). Max possible: ({max_cx_recalc},{max_cy_recalc})")
                    else:
                        if logger: logger.warning(f"Map view rect has zero or negative W/H ({view_w}x{view_h}) during layout recalc. Camera not adjusted.")
            
            # --- Drawing Phase ---
            editor_screen.fill(ED_CONFIG.C.DARK_GRAY if hasattr(ED_CONFIG.C, 'DARK_GRAY') else (50,50,50))

            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                # Draw placeholder for map area in menu mode
                ph_rect_menu = pygame.Rect(menu_section_rect.right + ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                      current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING*2,
                                      current_screen_height - ED_CONFIG.SECTION_PADDING*2)
                if ph_rect_menu.width > 10 and ph_rect_menu.height > 10: # Only draw if reasonably sized
                    pygame.draw.rect(editor_screen, (20,20,20), ph_rect_menu) # Darker placeholder background
                    f_large_menu = fonts.get("large")
                    if f_large_menu:
                        text_surf = f_large_menu.render("Map Editor Area", True, (60,60,60))
                        editor_screen.blit(text_surf, text_surf.get_rect(center=ph_rect_menu.center))

            elif editor_state.current_editor_mode == "editing_map":
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos, map_view_section_rect)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)

            # Draw dialogs on top of everything else (if active and not a Qt dialog)
            if editor_state.active_dialog_type and editor_state.active_dialog_type != "color_picker_q":
                editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)

            # Draw tooltips and status messages last
            f_tooltip_draw = fonts.get("tooltip")
            if f_tooltip_draw: editor_ui.draw_tooltip(editor_screen, editor_state, f_tooltip_draw)
            
            f_small_draw = fonts.get("small")
            if f_small_draw: editor_ui.draw_status_message(editor_screen, editor_state, f_small_draw)

            pygame.display.flip()
            # --- End Drawing ---

    except Exception as e_main_loop:
        if logger: logger.critical(f"CRITICAL ERROR in editor_main loop: {e_main_loop}", exc_info=True)
        else: print(f"CRITICAL ERROR in editor_main loop (logger not available): {e_main_loop}")
        traceback.print_exc()
    finally:
        if logger: logger.info("Exiting editor_main. Calling pygame.quit().")
        else: print("Exiting editor_main. Calling pygame.quit().")
        pygame.quit()
        
        # q_application_instance is already global in this function's scope
        if q_application_instance is not None and PYSIDE6_QAPP_AVAILABLE:
            if logger: logger.debug("QApplication instance exists. For standalone scripts, explicit quit is often not strictly necessary as Python's exit handles it. No explicit q_application_instance.quit() will be called here to avoid issues if run in an integrated Qt environment.")
            # If running as a standalone script that solely manages the Qt app,
            # q_application_instance.quit() could be called, but it's often safer
            # to let Python's cleanup handle it, especially if the script might
            # be part of a larger Qt application in some contexts.
        
        if logger: logger.info("Editor session ended.")
        else: print("Editor session ended.")
        # sys.exit() # sys.exit() is implicitly called when main function ends if not an imported module.
                   # If this script is the main entry point, Python will exit.
                   # Explicitly calling it can be good practice for clarity or if there's cleanup code after this block.
                   # For now, let's allow natural exit after editor_main finishes. If issues arise, it can be reinstated.


if __name__ == "__main__":
    print("--- editor.py execution started (__name__ == '__main__') ---")
    editor_main()
    print("--- editor.py execution finished ---") # This line will be reached if sys.exit() is not called in finally
    sys.exit(0) # Ensure a clean exit code 0 on successful completion.