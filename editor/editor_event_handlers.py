# editor_event_handlers.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.17 (Fluid camera pan, edge scroll, minimap regen triggers)
Handles Pygame events for different modes and UI elements
of the Platformer Level Editor.
"""
import pygame
import os
from typing import Optional, Dict, Tuple, Any, Callable, List
import traceback
import collections # For deque in flood fill

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_text_input_dialog, start_color_picker_dialog, start_file_load_dialog
from editor_map_utils import (init_new_map_state, save_map_to_json,
                              load_map_from_json, export_map_to_game_python_script)

def handle_global_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface) -> bool:
    if event.type == pygame.QUIT:
        # print("DEBUG GLOBAL_EVENT: pygame.QUIT event received.")
        if editor_state.unsaved_changes:
            if not getattr(editor_state, '_quit_attempted_with_unsaved_changes', False):
                editor_state.set_status_message("Unsaved changes! Quit again to exit without saving, or save your map.", 5.0)
                editor_state._quit_attempted_with_unsaved_changes = True
                return True
            else:
                # print("DEBUG GLOBAL_EVENT: Second quit attempt with unsaved changes. Proceeding to quit.")
                if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                    del editor_state._quit_attempted_with_unsaved_changes
                return False
        else:
            if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                del editor_state._quit_attempted_with_unsaved_changes
            return False

    if event.type == pygame.VIDEORESIZE:
        # print(f"DEBUG GLOBAL_EVENT: pygame.VIDEORESIZE to {event.w}x{event.h}")
        editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
        editor_state.minimap_needs_regeneration = True


    if event.type != pygame.QUIT and hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
        del editor_state._quit_attempted_with_unsaved_changes

    return True


def handle_dialog_events(event: pygame.event.Event, editor_state: EditorState):
    if not editor_state.active_dialog_type:
        return

    confirmed = False
    cancelled = False
    selected_value_from_dialog: Any = None
    dialog_type_being_processed = editor_state.active_dialog_type

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE: cancelled = True
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            if dialog_type_being_processed == "text_input":
                confirmed = True; selected_value_from_dialog = editor_state.dialog_input_text
            elif dialog_type_being_processed == "file_load" and editor_state.dialog_selected_file_index != -1 and \
                 0 <= editor_state.dialog_selected_file_index < len(editor_state.dialog_file_list):
                confirmed = True; selected_value_from_dialog = os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
            elif dialog_type_being_processed == "file_load": editor_state.set_status_message("No file selected.", 2.5)
        if dialog_type_being_processed == "text_input":
            if event.key == pygame.K_BACKSPACE: editor_state.dialog_input_text = editor_state.dialog_input_text[:-1]
            elif event.unicode.isprintable() and (event.unicode.isalnum() or event.unicode in ['.', '_', '-', ' ', ',', '/', '\\']): editor_state.dialog_input_text += event.unicode
        elif dialog_type_being_processed == "file_load" and editor_state.dialog_file_list:
            list_len = len(editor_state.dialog_file_list)
            if list_len > 0:
                if event.key == pygame.K_UP: editor_state.dialog_selected_file_index = (editor_state.dialog_selected_file_index - 1 + list_len) % list_len
                elif event.key == pygame.K_DOWN: editor_state.dialog_selected_file_index = (editor_state.dialog_selected_file_index + 1) % list_len
            else: editor_state.dialog_selected_file_index = -1
            if editor_state.dialog_selected_file_index != -1: editor_state.dialog_input_text = editor_state.dialog_file_list[editor_state.dialog_selected_file_index]
            else: editor_state.dialog_input_text = ""
    elif event.type == pygame.MOUSEBUTTONDOWN:
        if editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos) and event.button == 1:
            if dialog_type_being_processed == "color_picker":
                for color_name, swatch_rect_relative in editor_state.color_picker_rects.items():
                    absolute_swatch_rect = swatch_rect_relative.move(editor_state.dialog_rect.left, editor_state.dialog_rect.top)
                    if absolute_swatch_rect.collidepoint(event.pos):
                        selected_value_from_dialog = ED_CONFIG.COLOR_PICKER_PRESETS.get(color_name);
                        if selected_value_from_dialog: confirmed = True
                        break
            elif dialog_type_being_processed == "file_load":
                ok_rect, cancel_rect = editor_state.ui_elements_rects.get("dialog_file_load_ok"), editor_state.ui_elements_rects.get("dialog_file_load_cancel")
                if ok_rect and ok_rect.collidepoint(event.pos) and editor_state.dialog_selected_file_index != -1:
                    confirmed = True; selected_value_from_dialog = os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
                elif cancel_rect and cancel_rect.collidepoint(event.pos): cancelled = True
                else:
                    for item_info in editor_state.ui_elements_rects.get('dialog_file_item_rects', []):
                        if item_info["rect"].collidepoint(event.pos): editor_state.dialog_selected_file_index = item_info["index"]; editor_state.dialog_input_text = item_info["text"]; break
                    scrollbar_handle_rect = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
                    if scrollbar_handle_rect and scrollbar_handle_rect.collidepoint(event.pos): editor_state.is_dragging_scrollbar = True; editor_state.scrollbar_drag_mouse_offset_y = event.pos[1] - scrollbar_handle_rect.top
        elif dialog_type_being_processed != "text_input":
            is_confirm_button_click = False
            if dialog_type_being_processed == "file_load":
                ok_rect = editor_state.ui_elements_rects.get("dialog_file_load_ok")
                if ok_rect and ok_rect.collidepoint(event.pos): is_confirm_button_click = True
            if not is_confirm_button_click: cancelled = True
    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1 and editor_state.is_dragging_scrollbar: editor_state.is_dragging_scrollbar = False
    elif event.type == pygame.MOUSEMOTION:
        if editor_state.is_dragging_scrollbar:
            scrollbar_area = editor_state.ui_elements_rects.get('file_dialog_scrollbar_area'); scrollbar_handle = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
            if scrollbar_area and scrollbar_handle and editor_state.dialog_file_list:
                mouse_y_in_area = event.pos[1] - scrollbar_area.top; handle_pos_y = mouse_y_in_area - editor_state.scrollbar_drag_mouse_offset_y
                item_font = ED_CONFIG.FONT_CONFIG.get("small"); item_h = (item_font.get_height() + 6) if item_font else 22
                content_h = len(editor_state.dialog_file_list) * item_h; display_h = scrollbar_area.height
                track_h = max(1, display_h - scrollbar_handle.height); scroll_px = max(0, content_h - display_h)
                if track_h > 0 and scroll_px > 0: clamped_y = max(0, min(handle_pos_y, track_h)); ratio = clamped_y / track_h; editor_state.dialog_file_scroll_y = ratio * scroll_px
    elif event.type == pygame.MOUSEWHEEL:
        if dialog_type_being_processed == "file_load" and editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(pygame.mouse.get_pos()):
            font_small = ED_CONFIG.FONT_CONFIG.get("small"); item_h = (font_small.get_height() + 6) if font_small else 22
            scroll_val = event.y * item_h; content_h = len(editor_state.dialog_file_list) * item_h
            font_medium = ED_CONFIG.FONT_CONFIG.get("medium"); prompt_h = (font_medium.get_height() + 25) if font_medium else 55
            buttons_h = 40; display_h = editor_state.dialog_rect.height - prompt_h - buttons_h - 10 # type: ignore
            max_s = max(0, content_h - display_h); editor_state.dialog_file_scroll_y -= scroll_val; editor_state.dialog_file_scroll_y = max(0, min(editor_state.dialog_file_scroll_y, max_s))

    if confirmed:
        # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' outcome: CONFIRMED.")
        active_dialog_type_before_cb = editor_state.active_dialog_type
        original_confirm_cb = editor_state.dialog_callback_confirm
        original_cancel_cb = editor_state.dialog_callback_cancel
        original_prompt = editor_state.dialog_prompt_message
        if confirm_cb_to_call := editor_state.dialog_callback_confirm:
            try:
                value_to_pass = selected_value_from_dialog if selected_value_from_dialog is not None else editor_state.dialog_input_text
                if dialog_type_being_processed == "color_picker" and selected_value_from_dialog is None:
                    print(f"Warning DIALOG_EVENT: Color picker confirmed without selected_value.")
                else:
                    # print(f"DEBUG DIALOG_EVENT: Calling confirm_callback for '{dialog_type_being_processed}' with value: '{value_to_pass}'")
                    confirm_cb_to_call(value_to_pass)
            except Exception as e: print(f"ERROR: Confirm CB Exception: {e}"); traceback.print_exc()
        new_dialog_was_started = False
        if editor_state.active_dialog_type is not None:
            if (editor_state.active_dialog_type != active_dialog_type_before_cb or
                editor_state.dialog_callback_confirm != original_confirm_cb or
                editor_state.dialog_callback_cancel != original_cancel_cb or
                editor_state.dialog_prompt_message != original_prompt):
                new_dialog_was_started = True
        if new_dialog_was_started:
            pass # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' confirmed. Callback started a NEW dialog: '{editor_state.active_dialog_type}'.")
        else:
            # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' confirmed. No new dialog active. Cleaning up.")
            editor_state.active_dialog_type = None
            editor_state.dialog_callback_confirm = None; editor_state.dialog_callback_cancel = None
            editor_state.dialog_input_text = ""; editor_state.dialog_selected_file_index = -1
            editor_state.is_dragging_scrollbar = False
    elif cancelled:
        # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' outcome: CANCELLED.")
        active_dialog_type_before_cb = editor_state.active_dialog_type
        original_confirm_cb = editor_state.dialog_callback_confirm
        original_cancel_cb = editor_state.dialog_callback_cancel
        original_prompt = editor_state.dialog_prompt_message
        if cancel_cb_to_call := editor_state.dialog_callback_cancel:
            try:
                # print(f"DEBUG DIALOG_EVENT: Calling cancel_callback for '{dialog_type_being_processed}'.")
                cancel_cb_to_call()
            except Exception as e: print(f"ERROR: Cancel CB Exception: {e}"); traceback.print_exc()
        new_dialog_was_started = False
        if editor_state.active_dialog_type is not None:
            if (editor_state.active_dialog_type != active_dialog_type_before_cb or
                editor_state.dialog_callback_confirm != original_confirm_cb or
                editor_state.dialog_callback_cancel != original_cancel_cb or
                editor_state.dialog_prompt_message != original_prompt):
                new_dialog_was_started = True
        if new_dialog_was_started:
            pass # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' cancelled. Callback started a NEW dialog: '{editor_state.active_dialog_type}'.")
        else:
            # print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' cancelled. No new dialog active. Cleaning up.")
            editor_state.active_dialog_type = None
            editor_state.dialog_callback_confirm = None; editor_state.dialog_callback_cancel = None
            editor_state.dialog_input_text = ""; editor_state.dialog_selected_file_index = -1
            editor_state.is_dragging_scrollbar = False

def handle_menu_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos
        ui_rects = editor_state.ui_elements_rects
        if ui_rects.get("menu_new_map") and ui_rects["menu_new_map"].collidepoint(mouse_pos):
            # print("DEBUG MENU_EVENT: 'New Map' button clicked.")
            def on_new_map_name_confirm(map_name: str):
                map_name = map_name.strip()
                if not map_name:
                    editor_state.set_status_message("Map name cannot be empty.", 3)
                    start_text_input_dialog(editor_state, "Name:", "", on_new_map_name_confirm, lambda: None) # print("DEBUG MENU_EVENT: Name re-prompt cancelled"))
                    return
                editor_state.map_name_for_function_input = map_name
                def on_map_size_confirm(size_str: str):
                    try:
                        parts = [s.strip() for s in size_str.split(',')]
                        if len(parts) != 2 or not all(s.isdigit() for s in parts): raise ValueError("Format: W,H (numbers)")
                        w, h = int(parts[0]), int(parts[1])
                        if not (w > 0 and h > 0): raise ValueError("Dimensions > 0")
                        init_new_map_state(editor_state, editor_state.map_name_for_function_input, w, h)
                        # print(f"DEBUG MENU_EVENT: Auto-saving new map '{editor_state.map_name_for_function}'")
                        if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state):
                            editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' auto-saved.", 3)
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                        else:
                            editor_state.set_status_message(f"Auto-save failed for '{editor_state.map_name_for_function}'.", 4)
                            editor_state.unsaved_changes = True
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        editor_state.current_editor_mode = "editing_map"
                    except Exception as e:
                        editor_state.set_status_message(f"Invalid size: {e}", 3.5)
                        start_text_input_dialog(editor_state, "Size (W,H):", f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}", on_map_size_confirm, lambda: None) # print("DEBUG MENU_EVENT: Size re-prompt cancelled"))
                start_text_input_dialog(editor_state, "Size (W,H):", f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}", on_map_size_confirm, lambda: None) # print("DEBUG MENU_EVENT: Size dialog cancelled"))
            start_text_input_dialog(editor_state, "New Map Name:", "my_map", on_new_map_name_confirm, lambda: None) # print("DEBUG MENU_EVENT: Name dialog cancelled"))
            return
        elif ui_rects.get("menu_load_map") and ui_rects["menu_load_map"].collidepoint(mouse_pos):
            # print("DEBUG MENU_EVENT: 'Load Map' button clicked.")
            def on_file_selected(fp: str):
                if load_map_from_json(editor_state, fp):
                    editor_state.current_editor_mode = "editing_map"; pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            start_file_load_dialog(editor_state, on_confirm=on_file_selected, on_cancel=lambda: None) # print("DEBUG MENU_EVENT: Load dialog cancelled"))
            return
        elif ui_rects.get("menu_quit") and ui_rects["menu_quit"].collidepoint(mouse_pos):
            pygame.event.post(pygame.event.Event(pygame.QUIT))

def _place_single_tile_at_grid(editor_state: EditorState, asset_key_to_place: str, grid_coords: Tuple[int, int]):
    grid_world_x = grid_coords[0] * editor_state.grid_size
    grid_world_y = grid_coords[1] * editor_state.grid_size
    asset_data = editor_state.assets_palette.get(asset_key_to_place)
    if not asset_data:
        print(f"ERROR _place_single_tile: Asset key '{asset_key_to_place}' not found in palette.")
        return
    new_obj_game_type_id = asset_data["game_type_id"]
    is_spawn_item = asset_data.get("category") == "spawn"
    if not is_spawn_item:
        for obj in editor_state.placed_objects:
            if obj.get("world_x") == grid_world_x and \
               obj.get("world_y") == grid_world_y and \
               obj.get("game_type_id") == new_obj_game_type_id:
                return
    if is_spawn_item:
        editor_state.placed_objects = [
            obj for obj in editor_state.placed_objects if obj.get("game_type_id") != new_obj_game_type_id
        ]
    new_obj = {
        "asset_editor_key": asset_key_to_place,
        "world_x": grid_world_x,
        "world_y": grid_world_y,
        "game_type_id": new_obj_game_type_id
    }
    editor_state.placed_objects.append(new_obj)
    if not editor_state.unsaved_changes: editor_state.unsaved_changes = True
    editor_state.minimap_needs_regeneration = True
    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")

def _place_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    if not editor_state.selected_asset_editor_key: return
    selected_asset_info = editor_state.assets_palette.get(editor_state.selected_asset_editor_key)
    if not selected_asset_info: return
    if editor_state.selected_asset_editor_key == "platform_wall_gray_2x2_placer":
        base_wall_asset_key = selected_asset_info.get("places_asset_key")
        if not base_wall_asset_key:
            print("ERROR: 2x2 placer has no 'places_asset_key' defined.")
            return
        for r_offset in range(2):
            for c_offset in range(2):
                current_grid_coords = (grid_coords[0] + c_offset, grid_coords[1] + r_offset)
                _place_single_tile_at_grid(editor_state, base_wall_asset_key, current_grid_coords)
        return
    _place_single_tile_at_grid(editor_state, editor_state.selected_asset_editor_key, grid_coords)

def _erase_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    grid_world_x = grid_coords[0] * editor_state.grid_size
    grid_world_y = grid_coords[1] * editor_state.grid_size
    obj_erased = False
    for i in range(len(editor_state.placed_objects) - 1, -1, -1):
        obj = editor_state.placed_objects[i]
        if obj.get("world_x") == grid_world_x and obj.get("world_y") == grid_world_y:
            asset_info = editor_state.assets_palette.get(obj.get("asset_editor_key"))
            tooltip = asset_info['tooltip'] if asset_info else "Object" # type: ignore
            # print(f"DEBUG EDIT_MAP_EVENT: Erasing '{tooltip}' at grid ({grid_coords[0]},{grid_coords[1]}).")
            editor_state.placed_objects.pop(i)
            if not editor_state.unsaved_changes: editor_state.unsaved_changes = True
            editor_state.minimap_needs_regeneration = True
            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
            obj_erased = True
            break
    if obj_erased:
        editor_state.set_status_message(f"Erased tile at ({grid_coords[0]},{grid_coords[1]})", 1.5)

def _is_asset_colorable(editor_state: EditorState, asset_editor_key: Optional[str]) -> bool:
    if not asset_editor_key: return False
    asset_props = editor_state.assets_palette.get(asset_editor_key)
    if not asset_props: return False
    return asset_props.get("colorable", False)

def _perform_flood_fill_color_change(editor_state: EditorState, start_gx: int, start_gy: int,
                                     target_game_type_id: str, new_color: Tuple[int,int,int]):
    queue = collections.deque([(start_gx, start_gy)])
    visited_coords = set([(start_gx, start_gy)])
    objects_colored_count = 0
    initial_obj_at_start = None
    for obj_test in editor_state.placed_objects:
        if obj_test.get("world_x") // editor_state.grid_size == start_gx and \
           obj_test.get("world_y") // editor_state.grid_size == start_gy and \
           obj_test.get("game_type_id") == target_game_type_id:
            initial_obj_at_start = obj_test
            break
    if not initial_obj_at_start or not _is_asset_colorable(editor_state, initial_obj_at_start.get("asset_editor_key")):
        editor_state.set_status_message("Initial tile type not colorable.", 2.0)
        return
    while queue:
        gx, gy = queue.popleft()
        colored_in_this_cell = False
        for obj in editor_state.placed_objects:
            obj_gx = obj.get("world_x") // editor_state.grid_size
            obj_gy = obj.get("world_y") // editor_state.grid_size
            if obj_gx == gx and obj_gy == gy and obj.get("game_type_id") == target_game_type_id:
                if _is_asset_colorable(editor_state, obj.get("asset_editor_key")):
                    obj["override_color"] = new_color
                    if not colored_in_this_cell:
                        objects_colored_count += 1
                        colored_in_this_cell = True
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            next_gx, next_gy = gx + dx, gy + dy
            if (next_gx, next_gy) not in visited_coords:
                found_neighbor_of_type = False
                for obj_neighbor in editor_state.placed_objects:
                    obj_ngx = obj_neighbor.get("world_x") // editor_state.grid_size
                    obj_ngy = obj_neighbor.get("world_y") // editor_state.grid_size
                    if obj_ngx == next_gx and obj_ngy == next_gy and \
                       obj_neighbor.get("game_type_id") == target_game_type_id and \
                       _is_asset_colorable(editor_state, obj_neighbor.get("asset_editor_key")):
                        found_neighbor_of_type = True
                        break
                if found_neighbor_of_type:
                    visited_coords.add((next_gx, next_gy))
                    queue.append((next_gx, next_gy))
    if objects_colored_count > 0:
        editor_state.unsaved_changes = True
        editor_state.minimap_needs_regeneration = True
        pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        editor_state.set_status_message(f"Colored {objects_colored_count} tiles to RGB{new_color}", 3.0)
    else:
        editor_state.set_status_message(f"No tiles of type '{target_game_type_id}' found or colorable.", 2.5)


def _update_continuous_camera_pan(editor_state: EditorState, map_view_rect: pygame.Rect, mouse_pos: Tuple[int,int], dt: float):
    if editor_state.active_dialog_type: return # No camera movement if a dialog is active

    keys = pygame.key.get_pressed()
    pan_amount_pixels = ED_CONFIG.KEY_PAN_SPEED_PIXELS_PER_SECOND * dt
    cam_moved = False

    # Keyboard Panning
    if keys[pygame.K_a]:
        editor_state.camera_offset_x = max(0, editor_state.camera_offset_x - pan_amount_pixels)
        cam_moved = True
    if keys[pygame.K_d]:
        max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_rect.width)
        editor_state.camera_offset_x = min(max_cam_x, editor_state.camera_offset_x + pan_amount_pixels)
        cam_moved = True
    if keys[pygame.K_w]:
        editor_state.camera_offset_y = max(0, editor_state.camera_offset_y - pan_amount_pixels)
        cam_moved = True
    if keys[pygame.K_s] and not (keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]): # Avoid conflict with Ctrl+S
        max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_rect.height)
        editor_state.camera_offset_y = min(max_cam_y, editor_state.camera_offset_y + pan_amount_pixels)
        cam_moved = True

    # Edge Scroll Panning (only if no key panning happened, or allow both?)
    # Allowing both might feel weird. Let's prioritize key panning.
    if not cam_moved and map_view_rect.collidepoint(mouse_pos):
        edge_pan_amount = ED_CONFIG.EDGE_SCROLL_SPEED_PIXELS_PER_SECOND * dt
        zone = ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS

        if mouse_pos[0] < map_view_rect.left + zone : # Left edge
            editor_state.camera_offset_x = max(0, editor_state.camera_offset_x - edge_pan_amount)
            cam_moved = True
        elif mouse_pos[0] > map_view_rect.right - zone: # Right edge
            max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_rect.width)
            editor_state.camera_offset_x = min(max_cam_x, editor_state.camera_offset_x + edge_pan_amount)
            cam_moved = True

        if mouse_pos[1] < map_view_rect.top + zone: # Top edge
            editor_state.camera_offset_y = max(0, editor_state.camera_offset_y - edge_pan_amount)
            cam_moved = True
        elif mouse_pos[1] > map_view_rect.bottom - zone: # Bottom edge
            max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_rect.height)
            editor_state.camera_offset_y = min(max_cam_y, editor_state.camera_offset_y + edge_pan_amount)
            cam_moved = True
    
    if cam_moved:
        # Ensure camera_offset_x and y are integers after calculations
        editor_state.camera_offset_x = int(editor_state.camera_offset_x)
        editor_state.camera_offset_y = int(editor_state.camera_offset_y)
        # Minimap camera rect will update automatically due to changed camera_offset


def handle_editing_map_events(event: pygame.event.Event, editor_state: EditorState,
                              palette_section_rect: pygame.Rect, map_view_rect: pygame.Rect,
                              main_screen: pygame.Surface): # dt is not passed here, get from clock in main
    general_mouse_pos = pygame.mouse.get_pos()

    if event.type == pygame.MOUSEWHEEL:
        # Check if mouse is over the scrollable asset list area, not the minimap
        asset_list_content_rect_on_screen = pygame.Rect(
            palette_section_rect.left,
            palette_section_rect.top + ED_CONFIG.MINIMAP_AREA_HEIGHT,
            palette_section_rect.width,
            palette_section_rect.height - ED_CONFIG.MINIMAP_AREA_HEIGHT - (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2)
        )
        if asset_list_content_rect_on_screen.collidepoint(general_mouse_pos):
            font_small = ED_CONFIG.FONT_CONFIG.get("small"); scroll_speed = (font_small.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING) if font_small else 20 # type: ignore
            editor_state.asset_palette_scroll_y -= event.y * scroll_speed
            max_scroll = max(0, editor_state.total_asset_palette_content_height - asset_list_content_rect_on_screen.height)
            editor_state.asset_palette_scroll_y = max(0, min(editor_state.asset_palette_scroll_y, max_scroll))
    elif event.type == pygame.MOUSEBUTTONDOWN:
        mouse_pos_for_click = event.pos
        if palette_section_rect.collidepoint(mouse_pos_for_click) and event.button == 1:
            # Check if click is on minimap area (if we add clicking on minimap to pan) - Not implemented yet
            # For now, clicks in palette section are for assets or BG button
            bg_btn = editor_state.ui_elements_rects.get("palette_bg_color_button")
            if bg_btn and bg_btn.collidepoint(mouse_pos_for_click):
                def on_bg_sel(nc: Tuple[int,int,int]):
                    if nc:
                        editor_state.background_color = nc; editor_state.unsaved_changes = True
                        editor_state.minimap_needs_regeneration = True
                        pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*"); editor_state.set_status_message(f"BG: {nc}")
                start_color_picker_dialog(editor_state, on_confirm=on_bg_sel, on_cancel=lambda: None); return

            for key, rect in editor_state.ui_elements_rects.get('asset_palette_items', {}).items():
                if rect.collidepoint(mouse_pos_for_click): # rects are screen coordinates
                    asset_data_from_palette = editor_state.assets_palette[key]
                    editor_state.selected_asset_editor_key = key
                    if key == "tool_color_change":
                        editor_state.selected_asset_image_for_cursor = None
                        editor_state.set_status_message(f"Selected: {asset_data_from_palette['tooltip']}. Click tile on map.")
                    else:
                        editor_state.selected_asset_image_for_cursor = asset_data_from_palette["image"].copy()
                        editor_state.set_status_message(f"Selected: {asset_data_from_palette['tooltip']}")
                    return
        elif map_view_rect.collidepoint(mouse_pos_for_click):
            map_world_mx = mouse_pos_for_click[0]-map_view_rect.left+editor_state.camera_offset_x; map_world_my = mouse_pos_for_click[1]-map_view_rect.top+editor_state.camera_offset_y
            tile_x, tile_y = map_world_mx//editor_state.grid_size, map_world_my//editor_state.grid_size
            if event.button == 1:
                if editor_state.selected_asset_editor_key == "tool_color_change":
                    clicked_obj_data_for_color_change = None
                    for obj in reversed(editor_state.placed_objects):
                        obj_asset_key = obj.get("asset_editor_key")
                        obj_gx = obj.get("world_x") // editor_state.grid_size
                        obj_gy = obj.get("world_y") // editor_state.grid_size
                        if obj_gx == tile_x and obj_gy == tile_y and _is_asset_colorable(editor_state, obj_asset_key):
                            clicked_obj_data_for_color_change = { "game_type_id": obj["game_type_id"], "grid_x": tile_x, "grid_y": tile_y }
                            break
                    if clicked_obj_data_for_color_change:
                        editor_state.color_change_target_info = clicked_obj_data_for_color_change
                        def on_color_picked_for_flood_fill(new_color_tuple: Tuple[int,int,int]):
                            target_info = editor_state.color_change_target_info
                            if target_info and new_color_tuple:
                                _perform_flood_fill_color_change(editor_state, target_info["grid_x"], target_info["grid_y"], target_info["game_type_id"], new_color_tuple)
                            editor_state.color_change_target_info = None
                        start_color_picker_dialog(editor_state, on_confirm=on_color_picked_for_flood_fill, on_cancel=lambda: editor_state.set_status_message("Color change cancelled."))
                    else: editor_state.set_status_message("Clicked on empty space or non-colorable tile.", 2.0)
                    return
                elif editor_state.selected_asset_editor_key:
                    editor_state.is_painting_tiles = True; editor_state.last_painted_tile_coords = (tile_x,tile_y); _place_tile_at_grid(editor_state, (tile_x,tile_y))
                else:
                    editor_state.dragging_object_index = None
                    for i, obj in reversed(list(enumerate(editor_state.placed_objects))):
                        info = editor_state.assets_palette.get(obj.get("asset_editor_key"));
                        if info and "original_size_pixels" in info:
                            obj_w,obj_h=info["original_size_pixels"]; obj_r=pygame.Rect(obj["world_x"],obj["world_y"],obj_w,obj_h) # type: ignore
                            if obj_r.collidepoint(map_world_mx, map_world_my):
                                editor_state.dragging_object_index=i; editor_state.drag_start_mouse_map_x=map_world_mx; editor_state.drag_start_mouse_map_y=map_world_my
                                editor_state.drag_object_original_x=obj["world_x"]; editor_state.drag_object_original_y=obj["world_y"]; editor_state.set_status_message(f"Dragging {info['tooltip']}"); break
            elif event.button == 3:
                if pygame.key.get_mods() & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT):
                    if editor_state.map_name_for_function and editor_state.map_name_for_function != "untitled_map":
                        if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state): pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                    else: editor_state.set_status_message("Cannot save: Map not named.", 4)
                else:
                    editor_state.is_erasing_tiles = True; editor_state.last_erased_tile_coords = (tile_x,tile_y); _erase_tile_at_grid(editor_state, (tile_x,tile_y))
    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1:
            editor_state.is_painting_tiles = False; editor_state.last_painted_tile_coords = None
            if editor_state.dragging_object_index is not None:
                editor_state.dragging_object_index = None; editor_state.set_status_message("Drag complete")
        elif event.button == 3:
            editor_state.is_erasing_tiles = False; editor_state.last_erased_tile_coords = None
        if editor_state.is_dragging_scrollbar: editor_state.is_dragging_scrollbar = False
    elif event.type == pygame.MOUSEMOTION:
        mouse_pos_motion = event.pos
        if editor_state.dragging_object_index is not None and \
           0 <= editor_state.dragging_object_index < len(editor_state.placed_objects):
            obj_to_drag = editor_state.placed_objects[editor_state.dragging_object_index]
            map_world_mx = mouse_pos_motion[0] - map_view_rect.left + editor_state.camera_offset_x
            map_world_my = mouse_pos_motion[1] - map_view_rect.top + editor_state.camera_offset_y
            new_x = editor_state.drag_object_original_x + (map_world_mx - editor_state.drag_start_mouse_map_x)
            new_y = editor_state.drag_object_original_y + (map_world_my - editor_state.drag_start_mouse_map_y)
            snapped_x = (new_x // editor_state.grid_size) * editor_state.grid_size
            snapped_y = (new_y // editor_state.grid_size) * editor_state.grid_size
            if obj_to_drag["world_x"] != snapped_x or obj_to_drag["world_y"] != snapped_y:
                obj_to_drag["world_x"], obj_to_drag["world_y"] = snapped_x, snapped_y
                if not editor_state.unsaved_changes: editor_state.unsaved_changes = True
                editor_state.minimap_needs_regeneration = True # Object moved
                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        elif map_view_rect.collidepoint(mouse_pos_motion):
            map_world_mx = mouse_pos_motion[0] - map_view_rect.left + editor_state.camera_offset_x
            map_world_my = mouse_pos_motion[1] - map_view_rect.top + editor_state.camera_offset_y
            curr_tx, curr_ty = map_world_mx // editor_state.grid_size, map_world_my // editor_state.grid_size
            curr_grid_coords = (curr_tx, curr_ty)
            mouse_buttons_pressed = pygame.mouse.get_pressed()
            is_not_color_tool_active = editor_state.selected_asset_editor_key != "tool_color_change"
            if editor_state.is_painting_tiles and mouse_buttons_pressed[0] and \
               editor_state.selected_asset_editor_key and is_not_color_tool_active and \
               curr_grid_coords != editor_state.last_painted_tile_coords:
                _place_tile_at_grid(editor_state, curr_grid_coords)
                editor_state.last_painted_tile_coords = curr_grid_coords
            elif editor_state.is_erasing_tiles and mouse_buttons_pressed[2] and \
                 is_not_color_tool_active and \
                 curr_grid_coords != editor_state.last_erased_tile_coords:
                _erase_tile_at_grid(editor_state, curr_grid_coords)
                editor_state.last_erased_tile_coords = curr_grid_coords
        elif not map_view_rect.collidepoint(mouse_pos_motion):
            if editor_state.is_painting_tiles: editor_state.is_painting_tiles = False; editor_state.last_painted_tile_coords = None
            if editor_state.is_erasing_tiles: editor_state.is_erasing_tiles = False; editor_state.last_erased_tile_coords = None
    elif event.type == pygame.KEYDOWN: # Discrete key presses
        if event.key == pygame.K_ESCAPE:
            if editor_state.selected_asset_editor_key:
                editor_state.selected_asset_editor_key = None
                editor_state.set_status_message("Asset/Tool deselected")
            else:
                if editor_state.unsaved_changes:
                    if not getattr(editor_state, '_esc_exit_attempted', False):
                        editor_state.set_status_message("Unsaved changes! Save or Esc again to discard.", 4); editor_state._esc_exit_attempted = True
                    else:
                        editor_state.current_editor_mode = "menu"; editor_state.reset_map_context()
                        pygame.display.set_caption("Platformer Level Editor - Menu")
                        if hasattr(editor_state, '_esc_exit_attempted'): del editor_state._esc_exit_attempted
                else:
                    editor_state.current_editor_mode = "menu"; editor_state.reset_map_context()
                    pygame.display.set_caption("Platformer Level Editor - Menu")
                    if hasattr(editor_state, '_esc_exit_attempted'): del editor_state._esc_exit_attempted
        elif event.key != pygame.K_ESCAPE and hasattr(editor_state, '_esc_exit_attempted'):
            del editor_state._esc_exit_attempted
        elif event.key == pygame.K_g:
            editor_state.show_grid = not editor_state.show_grid
            editor_state.minimap_needs_regeneration = True # Grid visibility changes minimap look
            editor_state.set_status_message(f"Grid {'ON' if editor_state.show_grid else 'OFF'}")
        # Keydown WASD for single pan is removed, handled by continuous pan
        if event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            if editor_state.map_name_for_function and editor_state.map_name_for_function != "untitled_map":
                if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state):
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            else: editor_state.set_status_message("Cannot save: Map not named.", 4)