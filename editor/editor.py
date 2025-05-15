# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.12 (Integrate continuous camera pan)
Level Editor for the Platformer Game (Pygame Only).
Allows creating, loading, and saving game levels visually.
"""
import pygame
import sys
import os
from typing import Tuple, Dict, Optional, Any, List, Callable
import traceback

# --- VERY EARLY DEBUGGING FOR IMPORTS ---
# print("--- EDITOR.PY START ---")
# print(f"Initial sys.path: {sys.path}")
# print(f"Initial current working directory (CWD): {os.getcwd()}")
# --- Add parent directory to sys.path ---
current_script_path = os.path.dirname(os.path.abspath(__file__))
# print(f"Current script path (__file__): {current_script_path}")
parent_directory = os.path.dirname(current_script_path)
# print(f"Calculated parent directory (project root attempt): {parent_directory}")
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)
    # print(f"Parent directory '{parent_directory}' was ADDED to sys.path.")
# else:
    # print(f"Parent directory '{parent_directory}' was ALREADY in sys.path.")
# print(f"Modified sys.path (should contain project root at index 0 or 1): {sys.path}")
# print(f"CWD after potential sys.path modification: {os.getcwd()}")
try:
    import constants as C_imported
    # print(f"Successfully imported 'constants as C_imported'. TILE_SIZE: {C_imported.TILE_SIZE}")
except ImportError as e:
    print(f"ERROR: Failed to import 'constants as C_imported'. ImportError: {e}")
    sys.exit("ImportError for constants.py - exiting.")
except Exception as e_gen:
    print(f"ERROR: An unexpected error occurred during 'constants' import: {e_gen}")
    traceback.print_exc()
    sys.exit("Generic error importing constants.py - exiting.")
# --- END OF EARLY DEBUGGING FOR IMPORTS ---


import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_ui
import editor_assets
import editor_map_utils
import editor_drawing
import editor_event_handlers


def editor_main():
    # print("DEBUG MAIN: editor_main() started.")
    try:
        pygame.init()
        # print("DEBUG MAIN: pygame.init() called.")
        if not pygame.font.get_init():
            # print("DEBUG MAIN: pygame.font not initialized, calling pygame.font.init()")
            pygame.font.init()
        # if not pygame.font.get_init():
             # print("CRITICAL MAIN: pygame.font.init() failed after explicit call! Fonts will not work.")
        # else:
            # print("DEBUG MAIN: pygame.font.init() confirmed or already initialized.")

        if not editor_map_utils.ensure_maps_directory_exists():
            print("CRITICAL MAIN: Maps directory issue. Exiting.")
            pygame.quit(); sys.exit(1)
        # print("DEBUG MAIN: Maps directory ensured.")

        editor_screen = pygame.display.set_mode(
            (ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT),
            pygame.RESIZABLE
        )
        # print(f"DEBUG MAIN: Editor screen created: {editor_screen.get_size()}")
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        editor_state = EditorState()
        # print("DEBUG MAIN: EditorState instance created.")
        editor_assets.load_editor_palette_assets(editor_state)
        # print("DEBUG MAIN: load_editor_palette_assets called successfully.")

        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"):
            print("CRITICAL MAIN: Essential editor fonts missing. Exiting.")
            pygame.quit(); sys.exit(1)
        # print(f"DEBUG MAIN: Fonts from ED_CONFIG.FONT_CONFIG loaded.")

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
        # print(f"DEBUG MAIN: Initial Layout - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")

        running = True
        # print("DEBUG MAIN: Entering main loop.")
        # loop_count = 0
        while running:
            # loop_count += 1
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            events = pygame.event.get()

            # Periodic debug log (optional)
            # if loop_count % ((ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) * 10) == 0: # Approx every 10 seconds
            #     print(f"\nDEBUG MAIN LOOP (Periodic Log @ frame {loop_count}, time ~{pygame.time.get_ticks()/1000:.1f}s):")
            #     print(f"  Mode: {editor_state.current_editor_mode}, Active Dialog: {editor_state.active_dialog_type}")
            #     # ... other debug prints ...
            #     print(f"  Minimap needs regen: {editor_state.minimap_needs_regeneration}")

            editor_state.update_status_message(dt)
            previous_mode = editor_state.current_editor_mode
            previous_dialog_type = editor_state.active_dialog_type
            layout_needs_recalc = False

            # --- Continuous Camera Pan Update (before event loop) ---
            if editor_state.current_editor_mode == "editing_map" and not editor_state.active_dialog_type:
                editor_event_handlers._update_continuous_camera_pan(editor_state, map_view_section_rect, mouse_pos, dt)


            for event_idx, event in enumerate(events):
                if event.type == pygame.VIDEORESIZE:
                    # print(f"DEBUG MAIN: VIDEORESIZE event to {event.w}x{event.h}")
                    current_screen_width, current_screen_height = event.w, event.h
                    try:
                        editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                        # print(f"DEBUG MAIN: Screen resized to {editor_screen.get_size()}")
                    except pygame.error as e_resize:
                        print(f"ERROR MAIN: Pygame error on resize to {current_screen_width}x{current_screen_height}: {e_resize}")
                    layout_needs_recalc = True
                    editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)

                if not editor_event_handlers.handle_global_events(event, editor_state, editor_screen):
                    # print("DEBUG MAIN: handle_global_events returned False (QUIT). Setting running=False.")
                    running = False; break
                if not running: break

                if editor_state.active_dialog_type:
                    editor_event_handlers.handle_dialog_events(event, editor_state)
                    if editor_state.active_dialog_type != previous_dialog_type:
                        if editor_state.current_editor_mode != previous_mode:
                            layout_needs_recalc = True
                else:
                    if editor_state.current_editor_mode == "menu":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue
                        editor_event_handlers.handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        editor_event_handlers.handle_editing_map_events(
                            event, editor_state,
                            asset_palette_section_rect, map_view_section_rect,
                            editor_screen # dt removed, handled in _update_continuous_camera_pan
                        )
                if editor_state.current_editor_mode != previous_mode:
                    layout_needs_recalc = True
            if not running: break

            if layout_needs_recalc:
                # print(f"DEBUG MAIN: Recalculating layout...")
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                # print(f"DEBUG MAIN: New Layout after recalc - Menu={menu_section_rect}, Assets={asset_palette_section_rect}, Map={map_view_section_rect}")
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w = editor_state.get_map_pixel_width()
                    map_px_h = editor_state.get_map_pixel_height()
                    view_w = map_view_section_rect.width
                    view_h = map_view_section_rect.height
                    if view_w > 0 and view_h > 0 :
                        max_cam_x = max(0, map_px_w - view_w)
                        max_cam_y = max(0, map_px_h - view_h)
                        prev_cam_x, prev_cam_y = editor_state.camera_offset_x, editor_state.camera_offset_y
                        editor_state.camera_offset_x = max(0, min(editor_state.camera_offset_x, max_cam_x))
                        editor_state.camera_offset_y = max(0, min(editor_state.camera_offset_y, max_cam_y))
                        # if prev_cam_x != editor_state.camera_offset_x or prev_cam_y != editor_state.camera_offset_y:
                            # print(f"DEBUG MAIN: Camera clamped after resize/layout change.")
                    # else:
                        # print(f"Warning MAIN: Map view rect has zero or negative W/H.")


            editor_screen.fill(ED_CONFIG.C.DARK_GRAY if hasattr(ED_CONFIG.C, 'DARK_GRAY') else (50,50,50))

            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                placeholder_rect = pygame.Rect(
                    menu_section_rect.right + ED_CONFIG.SECTION_PADDING,
                    ED_CONFIG.SECTION_PADDING,
                    current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING * 2,
                    current_screen_height - ED_CONFIG.SECTION_PADDING * 2
                )
                if placeholder_rect.width > 10 and placeholder_rect.height > 10:
                    pygame.draw.rect(editor_screen, (20,20,20), placeholder_rect)
                    font_large = fonts.get("large")
                    if font_large:
                        ph_text = font_large.render("Map Editor Area", True, (60,60,60))
                        editor_screen.blit(ph_text, ph_text.get_rect(center=placeholder_rect.center))

            elif editor_state.current_editor_mode == "editing_map":
                # Pass map_view_rect to draw_asset_palette_ui for minimap's camera rect calculation
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos, map_view_section_rect)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)

            if editor_state.active_dialog_type:
                editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)

            font_tooltip = fonts.get("tooltip")
            if font_tooltip: editor_ui.draw_tooltip(editor_screen, editor_state, font_tooltip)

            font_small = fonts.get("small")
            if font_small: editor_ui.draw_status_message(editor_screen, editor_state, font_small)

            pygame.display.flip()

    except Exception as e:
        print(f"CRITICAL ERROR in editor_main: {e}")
        traceback.print_exc()
    finally:
        # print("DEBUG MAIN: Exiting editor_main. Calling pygame.quit() and sys.exit().")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    # print("DEBUG MAIN: Script execution started (__name__ == '__main__').")
    editor_main()