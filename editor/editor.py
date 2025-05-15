# editor/editor.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.14 (Momentum stops at boundary)
Level Editor for the Platformer Game (Pygame Only).
Allows creating, loading, and saving game levels visually.
"""
import pygame
import sys
import os
from typing import Tuple, Dict, Optional, Any, List, Callable
import traceback
import math

# --- Setup sys.path ---
current_script_path = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_script_path)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)
try:
    import constants as C_imported
except ImportError:
    print("ERROR: Failed to import 'constants'. Ensure it's in the project root.")
    sys.exit("ImportError for constants.py - exiting.")

import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_ui
import editor_assets
import editor_map_utils
import editor_drawing
import editor_event_handlers


def editor_main():
    try:
        pygame.init()
        if not pygame.font.get_init(): pygame.font.init()
        if not editor_map_utils.ensure_maps_directory_exists():
            print("CRITICAL MAIN: Maps directory issue. Exiting."); pygame.quit(); sys.exit(1)

        editor_screen = pygame.display.set_mode((ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, ED_CONFIG.EDITOR_SCREEN_INITIAL_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Platformer Level Editor - Menu")
        editor_clock = pygame.time.Clock()
        editor_state = EditorState()
        editor_assets.load_editor_palette_assets(editor_state)

        fonts: Dict[str, Optional[pygame.font.Font]] = ED_CONFIG.FONT_CONFIG
        if not fonts.get("small") or not fonts.get("medium") or not fonts.get("large"):
            print("CRITICAL MAIN: Essential editor fonts missing. Exiting."); pygame.quit(); sys.exit(1)

        def calculate_layout_rects(screen_width: int, screen_height: int, current_mode: str) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
            menu_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                     ED_CONFIG.MENU_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2))
            menu_rect.width = max(ED_CONFIG.BUTTON_WIDTH_STANDARD + ED_CONFIG.SECTION_PADDING * 2, menu_rect.width) # type: ignore
            menu_rect.height = max(menu_rect.height, ED_CONFIG.MENU_SECTION_HEIGHT) # type: ignore

            asset_palette_rect = pygame.Rect(ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                            ED_CONFIG.ASSET_PALETTE_SECTION_WIDTH, screen_height - (ED_CONFIG.SECTION_PADDING * 2)) # type: ignore
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

        running = True
        while running:
            dt = editor_clock.tick(ED_CONFIG.C.FPS if hasattr(ED_CONFIG.C, 'FPS') else 60) / 1000.0
            # Prevent dt from becoming too large if the game hangs for a moment (e.g., during window drag)
            # which could cause extreme jumps in physics/movement.
            dt = min(dt, 0.1) # Cap dt at 100ms (equivalent to 10 FPS)

            mouse_pos = pygame.mouse.get_pos()
            events = pygame.event.get()

            editor_state.update_status_message(dt)
            previous_mode = editor_state.current_editor_mode
            previous_dialog_type = editor_state.active_dialog_type
            layout_needs_recalc = False

            if editor_state.current_editor_mode == "editing_map" and not editor_state.active_dialog_type:
                editor_event_handlers._update_continuous_camera_pan(editor_state, map_view_section_rect, mouse_pos, dt)

            for event_idx, event in enumerate(events):
                if event.type == pygame.VIDEORESIZE:
                    current_screen_width, current_screen_height = event.w, event.h
                    try: editor_screen = pygame.display.set_mode((current_screen_width, current_screen_height), pygame.RESIZABLE)
                    except pygame.error as e_resize: print(f"ERROR MAIN: Pygame error on resize: {e_resize}")
                    layout_needs_recalc = True; editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
                if not editor_event_handlers.handle_global_events(event, editor_state, editor_screen): running = False; break
                if not running: break
                if editor_state.active_dialog_type:
                    editor_event_handlers.handle_dialog_events(event, editor_state)
                    if editor_state.active_dialog_type != previous_dialog_type and editor_state.current_editor_mode != previous_mode:
                        layout_needs_recalc = True
                else:
                    if editor_state.current_editor_mode == "menu":
                        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.event.post(pygame.event.Event(pygame.QUIT)); continue
                        editor_event_handlers.handle_menu_events(event, editor_state, editor_screen)
                    elif editor_state.current_editor_mode == "editing_map":
                        editor_event_handlers.handle_editing_map_events(event, editor_state, asset_palette_section_rect, map_view_section_rect, editor_screen)
                if editor_state.current_editor_mode != previous_mode: layout_needs_recalc = True
            if not running: break

            # --- Apply Camera Momentum (after all event-driven direct input) ---
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

                # --- MODIFIED BOUNDARY HANDLING ---
                boundary_hit = False
                if editor_state.camera_offset_x <= 0:
                    editor_state.camera_offset_x = 0
                    cam_vx = 0 # Stop horizontal momentum
                    boundary_hit = True
                elif editor_state.camera_offset_x >= max_cam_x:
                    editor_state.camera_offset_x = max_cam_x
                    cam_vx = 0 # Stop horizontal momentum
                    boundary_hit = True

                if editor_state.camera_offset_y <= 0:
                    editor_state.camera_offset_y = 0
                    cam_vy = 0 # Stop vertical momentum
                    boundary_hit = True
                elif editor_state.camera_offset_y >= max_cam_y:
                    editor_state.camera_offset_y = max_cam_y
                    cam_vy = 0 # Stop vertical momentum
                    boundary_hit = True
                # --- END OF MODIFIED BOUNDARY HANDLING ---
                
                editor_state.camera_offset_x = int(editor_state.camera_offset_x)
                editor_state.camera_offset_y = int(editor_state.camera_offset_y)

                if math.sqrt(cam_vx**2 + cam_vy**2) < ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or boundary_hit:
                    editor_state.camera_momentum_pan = (0.0, 0.0) # Stop if too slow or boundary hit
                else:
                    editor_state.camera_momentum_pan = (cam_vx, cam_vy)
            
            if layout_needs_recalc:
                menu_section_rect, asset_palette_section_rect, map_view_section_rect = calculate_layout_rects(
                    current_screen_width, current_screen_height, editor_state.current_editor_mode
                )
                if editor_state.current_editor_mode == "editing_map" and editor_state.map_content_surface:
                    map_px_w, map_px_h = editor_state.get_map_pixel_width(), editor_state.get_map_pixel_height()
                    view_w, view_h = map_view_section_rect.width, map_view_section_rect.height
                    if view_w > 0 and view_h > 0:
                        max_cx = max(0, map_px_w - view_w); max_cy = max(0, map_px_h - view_h)
                        editor_state.camera_offset_x = max(0,min(editor_state.camera_offset_x,max_cx))
                        editor_state.camera_offset_y = max(0,min(editor_state.camera_offset_y,max_cy))

            editor_screen.fill(ED_CONFIG.C.DARK_GRAY if hasattr(ED_CONFIG.C, 'DARK_GRAY') else (50,50,50)) # type: ignore

            if editor_state.current_editor_mode == "menu":
                editor_drawing.draw_menu_ui(editor_screen, editor_state, menu_section_rect, fonts, mouse_pos)
                ph_rect = pygame.Rect(menu_section_rect.right + ED_CONFIG.SECTION_PADDING, ED_CONFIG.SECTION_PADDING,
                                      current_screen_width - menu_section_rect.right - ED_CONFIG.SECTION_PADDING*2,
                                      current_screen_height - ED_CONFIG.SECTION_PADDING*2)
                if ph_rect.width > 10 and ph_rect.height > 10:
                    pygame.draw.rect(editor_screen, (20,20,20), ph_rect)
                    f_large = fonts.get("large");
                    if f_large: editor_screen.blit(f_large.render("Map Editor Area",True,(60,60,60)), f_large.render("Map Editor Area",True,(60,60,60)).get_rect(center=ph_rect.center))
            elif editor_state.current_editor_mode == "editing_map":
                editor_drawing.draw_asset_palette_ui(editor_screen, editor_state, asset_palette_section_rect, fonts, mouse_pos, map_view_section_rect)
                editor_drawing.draw_map_view_ui(editor_screen, editor_state, map_view_section_rect, fonts, mouse_pos)

            if editor_state.active_dialog_type: editor_ui.draw_active_dialog(editor_screen, editor_state, fonts)
            f_tooltip = fonts.get("tooltip");
            if f_tooltip: editor_ui.draw_tooltip(editor_screen, editor_state, f_tooltip)
            f_small = fonts.get("small");
            if f_small: editor_ui.draw_status_message(editor_screen, editor_state, f_small)
            pygame.display.flip()

    except Exception as e:
        print(f"CRITICAL ERROR in editor_main: {e}"); traceback.print_exc()
    finally:
        pygame.quit(); sys.exit()

if __name__ == "__main__":
    editor_main()