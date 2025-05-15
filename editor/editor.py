# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.10 (Refined debug logs, ensure C is from constants)
Level Editor for the Platformer Game (Pygame Only).
Allows creating, loading, and saving game levels visually.
"""
import pygame
import sys
import os
from typing import Tuple, Dict, Optional, Any, List, Callable
import traceback

# --- VERY EARLY DEBUGGING FOR IMPORTS ---
print("--- EDITOR.PY START ---")
print(f"Initial sys.path: {sys.path}")
print(f"Initial current working directory (CWD): {os.getcwd()}")

# --- Add parent directory to sys.path ---
current_script_path = os.path.dirname(os.path.abspath(__file__))
print(f"Current script path (__file__): {current_script_path}")
parent_directory = os.path.dirname(current_script_path) # This should be the project root
print(f"Calculated parent directory (project root attempt): {parent_directory}")

if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)
    print(f"Parent directory '{parent_directory}' was ADDED to sys.path.")
else:
    print(f"Parent directory '{parent_directory}' was ALREADY in sys.path.")

print(f"Modified sys.path (should contain project root at index 0 or 1): {sys.path}")
print(f"CWD after potential sys.path modification: {os.getcwd()}")

# Now try to import constants
try:
    import constants as C_imported # Use a different alias to avoid potential clashes
    print(f"Successfully imported 'constants as C_imported'. TILE_SIZE: {C_imported.TILE_SIZE}")
except ImportError as e:
    print(f"ERROR: Failed to import 'constants as C_imported'. ImportError: {e}")
    print("Please check:")
    print(f"1. Is '{parent_directory}' the correct project root where 'constants.py' is located?")
    print(f"2. Does '{os.path.join(parent_directory, 'constants.py')}' actually exist?")
    print(f"3. Is 'constants.py' a valid Python module (no syntax errors)?")
    sys.exit("ImportError for constants.py - exiting.")
except Exception as e_gen:
    print(f"ERROR: An unexpected error occurred during 'constants' import: {e_gen}")
    traceback.print_exc()
    sys.exit("Generic error importing constants.py - exiting.")
# --- END OF EARLY DEBUGGING FOR IMPORTS ---


import editor_config as ED_CONFIG # ED_CONFIG itself imports constants as C
from editor_state import EditorState
import editor_ui
import editor_assets
import editor_map_utils
import editor_drawing
import editor_event_handlers
# constants as C is imported by editor_config and other modules, ensure it's the correct one.
# We can use ED_CONFIG.C to be explicit that we're using the one constants resolved by editor_config.


def editor_main():
    print("DEBUG MAIN: editor_main() started.")
    try:
        pygame.init()
        print("DEBUG MAIN: pygame.init() called.")
        if not pygame.font.get_init(): # Check if font module is initialized
            print("DEBUG MAIN: pygame.font not initialized, calling pygame.font.init()")
            pygame.font.init()
        if not pygame.font.get_init():
             print("CRITICAL MAIN: pygame.font.init() failed after explicit call! Fonts will not work.")
        else:
            print("DEBUG MAIN: pygame.font.init() confirmed or already initialized.")


        if not editor_map_utils.ensure_maps_directory_exists():
            print("CRITICAL MAIN: Maps directory issue. Exiting.")
            pygame.quit(); sys.exit(1)
        print("DEBUG MAIN: Maps directory ensured.")

        editor_screen = pygame.display.set_mode(
            (ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT),
            pygame.RESIZABLE
        )
        print(f"DEBUG MAIN: Editor screen created: {editor_screen.get_size()}")
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        editor_state = EditorState() # This initializes and prints its own debugs
        print("DEBUG MAIN: EditorState instance created.")
        editor_assets.load_editor_palette_assets(editor_state) # This also prints debugs
        print("DEBUG MAIN: load_editor_palette_assets called successfully.")

        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"):
            print("CRITICAL MAIN: Essential editor fonts (small, medium, or large) are None after ED_CONFIG load. Exiting.")
            pygame.quit(); sys.exit(1)
        print(f"DEBUG MAIN: Fonts from ED_CONFIG.FONT_CONFIG loaded: small={fonts['small'] is not None}, medium={fonts['medium'] is not None}, large={fonts['large'] is not None}, tooltip={fonts['tooltip'] is not None}")

        def calculate_layout_rects(screen_width: int, screen_height: int, current_mode: str) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
            # print(f"DEBUG LAYOUT: calculate_layout_rects called. Screen: {screen_width}x{screen_height}, Mode: '{current_mode}'") # Verbose
            menu_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                     ED_CONFIG.MENU_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            menu_rect.width = max(ED_CONFIG.BUTTON_WIDTH_STANDARD + ED_CONFIG.SECTION_PADDING * 2, menu_rect.width)
            menu_rect.height = max(menu_rect.height, ED_CONFIG.MENU_SECTION_HEIGHT) # Ensure min height

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
            map_view_rect.width = max(map_view_rect.width, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Min sensible width
            map_view_rect.height = max(map_view_rect.height, ED_CONFIG.DEFAULT_GRID_SIZE * 10) # Min sensible height
            
            # print(f"DEBUG LAYOUT: Calculated rects - Menu={menu_rect}, Assets={asset_palette_rect}, Map={map_view_rect}") # Verbose
            return menu_rect, asset_palette_rect, map_view_rect

        current_screen_width, current_screen_height = editor_screen.get_size()
        menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
            current_screen_width, current_screen_height, editor_state.current_editor_mode
        )
        print(f"DEBUG MAIN: Initial Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")


        running = True
        print("DEBUG MAIN: Entering main loop.")
        loop_count = 0 
        while running:
            loop_count += 1
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            events = pygame.event.get()
            
            if loop_count % ( (ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) * 5) == 0: # Approx every 5 seconds
                print(f"\nDEBUG MAIN LOOP (Periodic Log @ frame {loop_count}, time ~{pygame.time.get_ticks()/1000:.1f}s): ----")
                print(f"  Mode: {editor_state.current_editor_mode}, Active Dialog: {editor_state.active_dialog_type}")
                print(f"  Unsaved Changes: {editor_state.unsaved_changes}, Map Name Func: '{editor_state.map_name_for_function}'")
                print(f"  Current Map File: '{editor_state.current_map_filename}'")
                print(f"  Selected Asset: '{editor_state.selected_asset_editor_key}'")
                print(f"  Num Placed Objects: {len(editor_state.placed_objects)}")
                print(f"  Camera: ({editor_state.camera_offset_x}, {editor_state.camera_offset_y})")
                print(f"  Screen: {current_screen_width}x{current_screen_height}")
                print(f"  Layout Rects: Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                print(f"DEBUG MAIN LOOP ---- END ----\n")

            editor_state.update_status_message(dt)

            previous_mode = editor_state.current_editor_mode
            previous_dialog_type = editor_state.active_dialog_type # For detecting dialog closure
            layout_needs_recalc = False

            for event_idx, event in enumerate(events):
                if event.type == pygame.VIDEORESIZE:
                    print(f"DEBUG MAIN: VIDEORESIZE event to {event.w}x{event.h}")
                    current_screen_width, current_screen_height = event.w, event.h
                    try:
                        editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                        print(f"DEBUG MAIN: Screen resized to {editor_screen.get_size()}")
                    except pygame.error as e_resize:
                        print(f"ERROR MAIN: Pygame error on resize to {current_screen_width}x{current_screen_height}: {e_resize}")
                        # Potentially try to fall back to a default size or handle gracefully
                    layout_needs_recalc = True
                    editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
                
                if not editor_event_handlers.handle_global_events(event, editor_state, editor_screen):
                    print("DEBUG MAIN: handle_global_events returned False. Setting running=False.")
                    running = False; break
                if not running: break 

                # --- MODAL DIALOG EVENT PROCESSING ---
                if editor_state.active_dialog_type:
                    editor_event_handlers.handle_dialog_events(event, editor_state)
                    # If dialog was closed (active_dialog_type became None or changed)
                    if editor_state.active_dialog_type != previous_dialog_type:
                        print(f"DEBUG MAIN: Dialog type changed from '{previous_dialog_type}' to '{editor_state.active_dialog_type}' after handle_dialog_events.")
                        # If mode also changed, it was likely due to a dialog callback
                        if editor_state.current_editor_mode != previous_mode:
                            print(f"DEBUG MAIN: Mode changed (likely via dialog callback) from '{previous_mode}' to '{editor_state.current_editor_mode}'. Triggering layout recalc.")
                            layout_needs_recalc = True
                else: # No active dialog, process mode-specific events
                    if editor_state.current_editor_mode == "menu":
                        editor_event_handlers.handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        editor_event_handlers.handle_editing_map_events(
                            event, editor_state,
                            asset_palette_section_rect, map_view_section_rect,
                            editor_screen
                        )
                
                # Check if mode changed from any event handler (dialog or mode-specific)
                if editor_state.current_editor_mode != previous_mode:
                    print(f"DEBUG MAIN: Mode changed from '{previous_mode}' to '{editor_state.current_editor_mode}' after specific event handlers. Triggering layout recalc.")
                    layout_needs_recalc = True
            if not running: break 
            
            if layout_needs_recalc:
                print(f"DEBUG MAIN: Recalculating layout. Current Mode: '{editor_state.current_editor_mode}', Screen: {current_screen_width}x{current_screen_height}")
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                print(f"DEBUG MAIN: New Layout after recalc - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                
                # If in editing mode and map surface exists, adjust camera to new view bounds
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w = editor_state.get_map_pixel_width()
                    map_px_h = editor_state.get_map_pixel_height()
                    view_w = map_view_section_rect.width
                    view_h = map_view_section_rect.height
                    
                    if view_w > 0 and view_h > 0 : # Ensure view rect has positive dimensions
                        max_cam_x = max(0, map_px_w - view_w)
                        max_cam_y = max(0, map_px_h - view_h)
                        
                        prev_cam_x, prev_cam_y = editor_state.camera_offset_x, editor_state.camera_offset_y
                        editor_state.camera_offset_x = max(0, min(editor_state.camera_offset_x, max_cam_x))
                        editor_state.camera_offset_y = max(0, min(editor_state.camera_offset_y, max_cam_y))
                        if prev_cam_x != editor_state.camera_offset_x or prev_cam_y != editor_state.camera_offset_y:
                            print(f"DEBUG MAIN: Camera clamped after resize/layout change from ({prev_cam_x},{prev_cam_y}) to ({editor_state.camera_offset_x},{editor_state.camera_offset_y}). Max cam: ({max_cam_x},{max_cam_y})")
                    else:
                        print(f"Warning MAIN: Map view rect has zero or negative W/H ({view_w}x{view_h}) after layout recalc. Camera not adjusted.")


            # --- Drawing ---
            editor_screen.fill(ED_CONFIG.C.DARK_GRAY) # Use ED_CONFIG.C for constants

            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                # Draw placeholder for map area in menu mode
                placeholder_rect = pygame.Rect(
                    menu_section_rect.right + ED_CONFIG.SECTION_PADDING, 
                    ED_CONFIG.SECTION_PADDING,
                    current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING * 2,
                    current_screen_height - ED_CONFIG.SECTION_PADDING * 2
                )
                if placeholder_rect.width > 10 and placeholder_rect.height > 10: # Only draw if reasonably sized
                    pygame.draw.rect(editor_screen, (20,20,20), placeholder_rect) # Darker placeholder bg
                    font_large = fonts.get("large")
                    if font_large:
                        ph_text = font_large.render("Map Editor Area", True, (60,60,60)) # Dim text
                        editor_screen.blit(ph_text, ph_text.get_rect(center=placeholder_rect.center))

            elif editor_state.current_editor_mode == "editing_map":
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)
            
            if editor_state.active_dialog_type: # Draw dialogs on top of everything else
                editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)

            font_tooltip = fonts.get("tooltip") # Use specific tooltip font from ED_CONFIG
            if font_tooltip: editor_ui.draw_tooltip(editor_screen, editor_state, font_tooltip)
            
            font_small = fonts.get("small") # Use specific small font
            if font_small: editor_ui.draw_status_message(editor_screen, editor_state, font_small)

            pygame.display.flip()

    except Exception as e:
        print(f"CRITICAL ERROR in editor_main: {e}")
        traceback.print_exc()
    finally:
        print("DEBUG MAIN: Exiting editor_main. Calling pygame.quit() and sys.exit().")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    print("DEBUG MAIN: Script execution started (__name__ == '__main__').")
    editor_main()