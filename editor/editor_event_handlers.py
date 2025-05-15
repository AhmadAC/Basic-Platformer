# editor_event_handlers.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.15 (Corrected MOUSEMOTION for painting/erasing, general cleanup)
Handles Pygame events for different modes and UI elements
of the Platformer Level Editor.
"""
import pygame
import os
from typing import Optional, Dict, Tuple, Any, Callable, List
import traceback

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_text_input_dialog, start_color_picker_dialog, start_file_load_dialog
from editor_map_utils import (init_new_map_state, save_map_to_json,
                              load_map_from_json, export_map_to_game_python_script)

def handle_global_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface) -> bool:
    if event.type == pygame.QUIT:
        print("DEBUG GLOBAL_EVENT: pygame.QUIT event received.")
        if editor_state.unsaved_changes:
            if not getattr(editor_state, '_quit_attempted_with_unsaved_changes', False):
                editor_state.set_status_message("Unsaved changes! Quit again to exit without saving, or save your map.", 5.0)
                editor_state._quit_attempted_with_unsaved_changes = True
                return True 
            else: 
                print("DEBUG GLOBAL_EVENT: Second quit attempt with unsaved changes. Proceeding to quit.")
                if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                    del editor_state._quit_attempted_with_unsaved_changes
                return False
        else: 
            if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                del editor_state._quit_attempted_with_unsaved_changes
            return False

    if event.type == pygame.VIDEORESIZE:
        print(f"DEBUG GLOBAL_EVENT: pygame.VIDEORESIZE to {event.w}x{event.h}")
        editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
    
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
    elif event.type == pygame.MOUSEBUTTONDOWN: # event.pos is valid
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
        elif dialog_type_being_processed != "text_input": cancelled = True
    elif event.type == pygame.MOUSEBUTTONUP: # event.pos is valid
        if event.button == 1 and editor_state.is_dragging_scrollbar: editor_state.is_dragging_scrollbar = False
    elif event.type == pygame.MOUSEMOTION: # event.pos is valid
        if editor_state.is_dragging_scrollbar:
            scrollbar_area = editor_state.ui_elements_rects.get('file_dialog_scrollbar_area'); scrollbar_handle = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
            if scrollbar_area and scrollbar_handle and editor_state.dialog_file_list:
                mouse_y_in_area = event.pos[1] - scrollbar_area.top; handle_pos_y = mouse_y_in_area - editor_state.scrollbar_drag_mouse_offset_y
                item_font = ED_CONFIG.FONT_CONFIG.get("small"); item_h = (item_font.get_height() + 6) if item_font else 22
                content_h = len(editor_state.dialog_file_list) * item_h; display_h = scrollbar_area.height
                track_h = max(1, display_h - scrollbar_handle.height); scroll_px = max(0, content_h - display_h)
                if track_h > 0 and scroll_px > 0: clamped_y = max(0, min(handle_pos_y, track_h)); ratio = clamped_y / track_h; editor_state.dialog_file_scroll_y = ratio * scroll_px
    elif event.type == pygame.MOUSEWHEEL: # event.y is valid, event.pos might not be relevant for wheel itself
        if dialog_type_being_processed == "file_load" and editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(pygame.mouse.get_pos()): # check mouse over dialog
            font_small = ED_CONFIG.FONT_CONFIG.get("small"); item_h = (font_small.get_height() + 6) if font_small else 22
            scroll_val = event.y * item_h; content_h = len(editor_state.dialog_file_list) * item_h
            font_medium = ED_CONFIG.FONT_CONFIG.get("medium"); prompt_h = (font_medium.get_height() + 25) if font_medium else 55
            buttons_h = 40; display_h = editor_state.dialog_rect.height - prompt_h - buttons_h - 10
            max_s = max(0, content_h - display_h); editor_state.dialog_file_scroll_y -= scroll_val; editor_state.dialog_file_scroll_y = max(0, min(editor_state.dialog_file_scroll_y, max_s))

    if confirmed:
        print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' outcome: CONFIRMED.")
        active_dialog_type_before_cb = editor_state.active_dialog_type
        original_confirm_cb = editor_state.dialog_callback_confirm
        original_cancel_cb = editor_state.dialog_callback_cancel
        original_prompt = editor_state.dialog_prompt_message
        
        if confirm_cb_to_call := editor_state.dialog_callback_confirm: # Python 3.8+ walrus operator
            try:
                value_to_pass = selected_value_from_dialog if selected_value_from_dialog is not None else editor_state.dialog_input_text
                print(f"DEBUG DIALOG_EVENT: Calling confirm_callback for '{dialog_type_being_processed}' with value: '{value_to_pass}'")
                confirm_cb_to_call(value_to_pass) 
            except Exception as e: print(f"ERROR: Confirm CB Exception: {e}"); traceback.print_exc()
        
        new_dialog_was_started = False
        if editor_state.active_dialog_type is not None: # If a dialog is still set
            # Check if it's a *different* dialog than the one we just processed the confirm for,
            # or if its core properties (callbacks, prompt) changed, indicating re-initialization.
            if (editor_state.active_dialog_type != active_dialog_type_before_cb or
                editor_state.dialog_callback_confirm != original_confirm_cb or
                editor_state.dialog_callback_cancel != original_cancel_cb or
                editor_state.dialog_prompt_message != original_prompt):
                new_dialog_was_started = True
        
        if new_dialog_was_started:
            print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' confirmed. Callback started a NEW dialog: '{editor_state.active_dialog_type}'.")
        else: # No new dialog took over, or callback explicitly cleared active_dialog_type
            print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' confirmed. No new dialog active. Cleaning up.")
            editor_state.active_dialog_type = None 
            editor_state.dialog_callback_confirm = None; editor_state.dialog_callback_cancel = None
            editor_state.dialog_input_text = ""; editor_state.dialog_selected_file_index = -1
            editor_state.is_dragging_scrollbar = False

    elif cancelled:
        print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' outcome: CANCELLED.")
        active_dialog_type_before_cb = editor_state.active_dialog_type
        original_confirm_cb = editor_state.dialog_callback_confirm
        original_cancel_cb = editor_state.dialog_callback_cancel
        original_prompt = editor_state.dialog_prompt_message

        if cancel_cb_to_call := editor_state.dialog_callback_cancel:
            try:
                print(f"DEBUG DIALOG_EVENT: Calling cancel_callback for '{dialog_type_being_processed}'.")
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
             print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' cancelled. Callback started a NEW dialog: '{editor_state.active_dialog_type}'.")
        else:
            print(f"DEBUG DIALOG_EVENT: Dialog '{dialog_type_being_processed}' cancelled. No new dialog active. Cleaning up.")
            editor_state.active_dialog_type = None
            editor_state.dialog_callback_confirm = None; editor_state.dialog_callback_cancel = None
            editor_state.dialog_input_text = ""; editor_state.dialog_selected_file_index = -1
            editor_state.is_dragging_scrollbar = False


def handle_menu_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos # Safe here
        ui_rects = editor_state.ui_elements_rects 
        
        if ui_rects.get("menu_new_map") and ui_rects["menu_new_map"].collidepoint(mouse_pos):
            print("DEBUG MENU_EVENT: 'New Map' button clicked.")
            def on_new_map_name_confirm(map_name: str):
                map_name = map_name.strip()
                if not map_name:
                    editor_state.set_status_message("Map name cannot be empty.", 3)
                    start_text_input_dialog(editor_state, "Name:", "", on_new_map_name_confirm, lambda: print("DEBUG MENU_EVENT: Name re-prompt cancelled"))
                    return
                editor_state.map_name_for_function_input = map_name
                def on_map_size_confirm(size_str: str):
                    try:
                        parts = [s.strip() for s in size_str.split(',')]
                        if len(parts) != 2 or not all(s.isdigit() for s in parts): raise ValueError("Format: W,H (numbers)")
                        w, h = int(parts[0]), int(parts[1])
                        if not (w > 0 and h > 0): raise ValueError("Dimensions > 0")
                        
                        init_new_map_state(editor_state, editor_state.map_name_for_function_input, w, h)
                        print(f"DEBUG MENU_EVENT: Auto-saving new map '{editor_state.map_name_for_function}'")
                        if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state):
                            editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' auto-saved.", 3)
                            # unsaved_changes is set False by export_map_to_game_python_script
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                        else:
                            editor_state.set_status_message(f"Auto-save failed for '{editor_state.map_name_for_function}'.", 4)
                            # Ensure unsaved_changes is true if save failed
                            editor_state.unsaved_changes = True 
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        editor_state.current_editor_mode = "editing_map"
                    except Exception as e:
                        editor_state.set_status_message(f"Invalid size: {e}", 3.5)
                        start_text_input_dialog(editor_state, "Size (W,H):", f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}", on_map_size_confirm, lambda: print("DEBUG MENU_EVENT: Size re-prompt cancelled"))
                start_text_input_dialog(editor_state, "Size (W,H):", f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}", on_map_size_confirm, lambda: print("DEBUG MENU_EVENT: Size dialog cancelled"))
            start_text_input_dialog(editor_state, "New Map Name:", "my_map", on_new_map_name_confirm, lambda: print("DEBUG MENU_EVENT: Name dialog cancelled"))
            return

        elif ui_rects.get("menu_load_map") and ui_rects["menu_load_map"].collidepoint(mouse_pos):
            print("DEBUG MENU_EVENT: 'Load Map' button clicked.")
            def on_file_selected(fp: str):
                if load_map_from_json(editor_state, fp):
                    editor_state.current_editor_mode = "editing_map"; pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            start_file_load_dialog(editor_state, on_confirm=on_file_selected, on_cancel=lambda: print("DEBUG MENU_EVENT: Load dialog cancelled"))
            return

        elif ui_rects.get("menu_quit") and ui_rects["menu_quit"].collidepoint(mouse_pos):
            pygame.event.post(pygame.event.Event(pygame.QUIT))


def _place_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    if not editor_state.selected_asset_editor_key: return
    grid_world_x = grid_coords[0] * editor_state.grid_size
    grid_world_y = grid_coords[1] * editor_state.grid_size
    asset_data = editor_state.assets_palette[editor_state.selected_asset_editor_key]
    new_obj_game_type_id = asset_data["game_type_id"]
    is_spawn_item = asset_data.get("category") == "spawn"

    if not is_spawn_item:
        for obj in editor_state.placed_objects:
            if obj.get("world_x") == grid_world_x and \
               obj.get("world_y") == grid_world_y and \
               obj.get("game_type_id") == new_obj_game_type_id:
                return 
    elif is_spawn_item: # Only one of each spawn type allowed
        editor_state.placed_objects = [obj for obj in editor_state.placed_objects if obj.get("game_type_id") != new_obj_game_type_id]

    new_obj = {"asset_editor_key": editor_state.selected_asset_editor_key, "world_x": grid_world_x, "world_y": grid_world_y, "game_type_id": new_obj_game_type_id}
    editor_state.placed_objects.append(new_obj)
    if not editor_state.unsaved_changes: editor_state.unsaved_changes = True # Mark unsaved if not already
    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")


def _erase_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    grid_world_x = grid_coords[0] * editor_state.grid_size
    grid_world_y = grid_coords[1] * editor_state.grid_size
    
    obj_erased = False
    for i in range(len(editor_state.placed_objects) - 1, -1, -1):
        obj = editor_state.placed_objects[i]
        # Simple check: if object's origin is in this grid cell.
        # More precise would be checking if any part of object's rect intersects grid cell.
        if obj.get("world_x") == grid_world_x and obj.get("world_y") == grid_world_y:
            asset_info = editor_state.assets_palette.get(obj.get("asset_editor_key"))
            tooltip = asset_info['tooltip'] if asset_info else "Object"
            print(f"DEBUG EDIT_MAP_EVENT: Erasing '{tooltip}' at grid ({grid_coords[0]},{grid_coords[1]}).")
            editor_state.placed_objects.pop(i)
            if not editor_state.unsaved_changes: editor_state.unsaved_changes = True
            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
            obj_erased = True
            break # Erase one object per erase action at a grid spot
    if obj_erased:
        editor_state.set_status_message(f"Erased tile at ({grid_coords[0]},{grid_coords[1]})", 1.5)


def handle_editing_map_events(event: pygame.event.Event, editor_state: EditorState,
                              palette_section_rect: pygame.Rect, map_view_rect: pygame.Rect,
                              main_screen: pygame.Surface):
    general_mouse_pos = pygame.mouse.get_pos() 

    if event.type == pygame.MOUSEWHEEL:
        if palette_section_rect.collidepoint(general_mouse_pos):
            font_small = ED_CONFIG.FONT_CONFIG.get("small"); scroll_speed = (font_small.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING) if font_small else 20
            editor_state.asset_palette_scroll_y -= event.y * scroll_speed 
            max_scroll = max(0, editor_state.total_asset_palette_content_height - palette_section_rect.height)
            editor_state.asset_palette_scroll_y = max(0, min(editor_state.asset_palette_scroll_y, max_scroll))
    
    elif event.type == pygame.MOUSEBUTTONDOWN:
        mouse_pos_for_click = event.pos
        if palette_section_rect.collidepoint(mouse_pos_for_click) and event.button == 1:
            bg_btn = editor_state.ui_elements_rects.get("palette_bg_color_button")
            if bg_btn and bg_btn.collidepoint(mouse_pos_for_click):
                def on_bg_sel(nc: Tuple[int,int,int]):
                    if nc: editor_state.background_color = nc; editor_state.unsaved_changes = True; pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*"); editor_state.set_status_message(f"BG: {nc}")
                start_color_picker_dialog(editor_state, on_confirm=on_bg_sel, on_cancel=lambda: None); return
            for key, rect in editor_state.ui_elements_rects.get('asset_palette_items', {}).items():
                if rect.collidepoint(mouse_pos_for_click):
                    data = editor_state.assets_palette[key]; editor_state.selected_asset_editor_key = key
                    editor_state.selected_asset_image_for_cursor = data["image"].copy(); editor_state.set_status_message(f"Selected: {data['tooltip']}"); return
        elif map_view_rect.collidepoint(mouse_pos_for_click):
            map_world_mx = mouse_pos_for_click[0]-map_view_rect.left+editor_state.camera_offset_x; map_world_my = mouse_pos_for_click[1]-map_view_rect.top+editor_state.camera_offset_y
            tile_x, tile_y = map_world_mx//editor_state.grid_size, map_world_my//editor_state.grid_size
            if event.button == 1:
                if editor_state.selected_asset_editor_key:
                    editor_state.is_painting_tiles = True; editor_state.last_painted_tile_coords = (tile_x,tile_y); _place_tile_at_grid(editor_state, (tile_x,tile_y))
                else: 
                    editor_state.dragging_object_index = None
                    for i, obj in reversed(list(enumerate(editor_state.placed_objects))):
                        info = editor_state.assets_palette.get(obj.get("asset_editor_key"));
                        if info and "original_size_pixels" in info:
                            obj_w,obj_h=info["original_size_pixels"]; obj_r=pygame.Rect(obj["world_x"],obj["world_y"],obj_w,obj_h)
                            if obj_r.collidepoint(map_world_mx, map_world_my):
                                editor_state.dragging_object_index=i; editor_state.drag_start_mouse_map_x=map_world_mx; editor_state.drag_start_mouse_map_y=map_world_my
                                editor_state.drag_object_original_x=obj["world_x"]; editor_state.drag_object_original_y=obj["world_y"]; editor_state.set_status_message(f"Dragging {info['tooltip']}"); break
            elif event.button == 3:
                if pygame.key.get_mods() & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT): 
                    if editor_state.map_name_for_function and editor_state.map_name_for_function != "untitled_map": # Check for valid map name
                        if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state): pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                    else: editor_state.set_status_message("Cannot save: Map not named.", 4)
                else: 
                    editor_state.is_erasing_tiles = True; editor_state.last_erased_tile_coords = (tile_x,tile_y); _erase_tile_at_grid(editor_state, (tile_x,tile_y))
    
    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1: 
            editor_state.is_painting_tiles = False
            editor_state.last_painted_tile_coords = None
            if editor_state.dragging_object_index is not None: 
                editor_state.dragging_object_index = None; editor_state.set_status_message("Drag complete")
        elif event.button == 3: 
            editor_state.is_erasing_tiles = False
            editor_state.last_erased_tile_coords = None
        if editor_state.is_dragging_scrollbar: editor_state.is_dragging_scrollbar = False # General scrollbar release
    
    elif event.type == pygame.MOUSEMOTION:
        mouse_pos_motion = event.pos
        if editor_state.dragging_object_index is not None and \
           0 <= editor_state.dragging_object_index < len(editor_state.placed_objects): # Dragging object
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
                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        elif map_view_rect.collidepoint(mouse_pos_motion): # Painting or Erasing
            map_world_mx = mouse_pos_motion[0] - map_view_rect.left + editor_state.camera_offset_x
            map_world_my = mouse_pos_motion[1] - map_view_rect.top + editor_state.camera_offset_y
            curr_tx, curr_ty = map_world_mx // editor_state.grid_size, map_world_my // editor_state.grid_size
            curr_grid_coords = (curr_tx, curr_ty)
            
            mouse_buttons_pressed = pygame.mouse.get_pressed() # (left, middle, right)
            if editor_state.is_painting_tiles and mouse_buttons_pressed[0] and \
               editor_state.selected_asset_editor_key and curr_grid_coords != editor_state.last_painted_tile_coords:
                _place_tile_at_grid(editor_state, curr_grid_coords)
                editor_state.last_painted_tile_coords = curr_grid_coords
            elif editor_state.is_erasing_tiles and mouse_buttons_pressed[2] and \
                 curr_grid_coords != editor_state.last_erased_tile_coords:
                _erase_tile_at_grid(editor_state, curr_grid_coords)
                editor_state.last_erased_tile_coords = curr_grid_coords
        # If mouse moves outside map view while a drag-paint/erase was active, stop it.
        elif not map_view_rect.collidepoint(mouse_pos_motion):
            if editor_state.is_painting_tiles:
                editor_state.is_painting_tiles = False; editor_state.last_painted_tile_coords = None
            if editor_state.is_erasing_tiles:
                editor_state.is_erasing_tiles = False; editor_state.last_erased_tile_coords = None

    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            if editor_state.selected_asset_editor_key:
                editor_state.selected_asset_editor_key, editor_state.selected_asset_image_for_cursor = None, None
                editor_state.set_status_message("Asset deselected")
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
            editor_state.set_status_message(f"Grid {'ON' if editor_state.show_grid else 'OFF'}")
        
        pan = ED_CONFIG.MAP_VIEW_CAMERA_PAN_SPEED
        if map_view_rect.width > 0 and map_view_rect.height > 0:
            map_w, map_h = editor_state.get_map_pixel_width(), editor_state.get_map_pixel_height()
            cam_moved = False
            if event.key == pygame.K_a: editor_state.camera_offset_x = max(0, editor_state.camera_offset_x - pan); cam_moved = True
            elif event.key == pygame.K_d: editor_state.camera_offset_x = min(max(0,map_w-map_view_rect.width), editor_state.camera_offset_x+pan); cam_moved = True
            elif event.key == pygame.K_w: editor_state.camera_offset_y = max(0, editor_state.camera_offset_y - pan); cam_moved = True
            elif event.key == pygame.K_s and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                editor_state.camera_offset_y = min(max(0,map_h-map_view_rect.height), editor_state.camera_offset_y+pan); cam_moved = True
            if cam_moved: print(f"DEBUG EDIT_MAP_EVENT: Camera panned to ({editor_state.camera_offset_x},{editor_state.camera_offset_y})")

        if event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            if editor_state.map_name_for_function and editor_state.map_name_for_function != "untitled_map":
                if save_map_to_json(editor_state) and export_map_to_game_python_script(editor_state): 
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            else: editor_state.set_status_message("Cannot save: Map not named.", 4)