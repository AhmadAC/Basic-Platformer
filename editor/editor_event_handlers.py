# editor_event_handlers.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.20 (Ensure color tool doesn't place itself)
Handles Pygame events for different modes and UI elements
of the Platformer Level Editor.
"""
import pygame
import os
from typing import Optional, Dict, Tuple, Any, Callable, List
import traceback
import collections

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_text_input_dialog, start_color_picker_dialog, start_file_load_dialog
from editor_map_utils import (init_new_map_state, save_map_to_json,
                              load_map_from_json, export_map_to_game_python_script)

# (handle_global_events and handle_dialog_events remain the same as previous correct version)
def handle_global_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface) -> bool:
    if event.type == pygame.QUIT:
        if editor_state.unsaved_changes:
            if not getattr(editor_state, '_quit_attempted_with_unsaved_changes', False):
                editor_state.set_status_message("Unsaved changes! Quit again to exit without saving, or save your map.", 5.0)
                setattr(editor_state, '_quit_attempted_with_unsaved_changes', True)
                return True
            else:
                if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                    delattr(editor_state, '_quit_attempted_with_unsaved_changes')
                return False
        else:
            if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                delattr(editor_state, '_quit_attempted_with_unsaved_changes')
            return False
    if event.type == pygame.VIDEORESIZE:
        editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
        editor_state.minimap_needs_regeneration = True
    if event.type != pygame.QUIT and hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
        delattr(editor_state, '_quit_attempted_with_unsaved_changes')
    return True

def handle_dialog_events(event: pygame.event.Event, editor_state: EditorState):
    if not editor_state.active_dialog_type: return
    confirmed, cancelled, selected_value = False, False, None
    dialog_type = editor_state.active_dialog_type
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE: cancelled = True
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            if dialog_type=="text_input": confirmed=True; selected_value=editor_state.dialog_input_text
            elif dialog_type=="file_load" and -1!=editor_state.dialog_selected_file_index < len(editor_state.dialog_file_list): # type: ignore
                confirmed=True; selected_value=os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index]) # type: ignore
            elif dialog_type=="file_load": editor_state.set_status_message("No file selected.", 2.5)
        if dialog_type=="text_input":
            if event.key==pygame.K_BACKSPACE: editor_state.dialog_input_text=editor_state.dialog_input_text[:-1]
            elif event.unicode.isprintable()and(event.unicode.isalnum()or event.unicode in ['.','_','-',' ',',','/','\\']): editor_state.dialog_input_text+=event.unicode
        elif dialog_type=="file_load" and editor_state.dialog_file_list:
            ll=len(editor_state.dialog_file_list)
            if ll>0:
                if event.key==pygame.K_UP: editor_state.dialog_selected_file_index=(editor_state.dialog_selected_file_index-1+ll)%ll
                elif event.key==pygame.K_DOWN: editor_state.dialog_selected_file_index=(editor_state.dialog_selected_file_index+1)%ll
            else: editor_state.dialog_selected_file_index=-1
            editor_state.dialog_input_text = editor_state.dialog_file_list[editor_state.dialog_selected_file_index] if editor_state.dialog_selected_file_index!=-1 else "" # type: ignore
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos):
            if dialog_type=="color_picker":
                for name,rect in editor_state.color_picker_rects.items():
                    abs_rect=rect.move(editor_state.dialog_rect.left,editor_state.dialog_rect.top)
                    if abs_rect.collidepoint(event.pos): selected_value=ED_CONFIG.COLOR_PICKER_PRESETS.get(name); confirmed=bool(selected_value); break
            elif dialog_type=="file_load":
                ok,cancel=editor_state.ui_elements_rects.get("dialog_file_load_ok"), editor_state.ui_elements_rects.get("dialog_file_load_cancel")
                if ok and ok.collidepoint(event.pos)and editor_state.dialog_selected_file_index!=-1:
                    confirmed=True; selected_value=os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index]) # type: ignore
                elif cancel and cancel.collidepoint(event.pos): cancelled=True
                else:
                    for item in editor_state.ui_elements_rects.get('dialog_file_item_rects',[]): # type: ignore
                        if item["rect"].collidepoint(event.pos): editor_state.dialog_selected_file_index=item["index"]; editor_state.dialog_input_text=item["text"]; break
                    scroll_h=editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
                    if scroll_h and scroll_h.collidepoint(event.pos): editor_state.is_dragging_scrollbar=True; editor_state.scrollbar_drag_mouse_offset_y=event.pos[1]-scroll_h.top
        elif dialog_type!="text_input":
            if not (editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos)):
                 cancelled = True
    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1: editor_state.is_dragging_scrollbar=False
    elif event.type == pygame.MOUSEMOTION and editor_state.is_dragging_scrollbar:
        area,handle=editor_state.ui_elements_rects.get('file_dialog_scrollbar_area'), editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
        if area and handle and editor_state.dialog_file_list:
            my_area=event.pos[1]-area.top; h_pos_y=my_area-editor_state.scrollbar_drag_mouse_offset_y
            font=ED_CONFIG.FONT_CONFIG.get("small"); item_h=(font.get_height()+6)if font else 22 # type: ignore
            content_h=len(editor_state.dialog_file_list)*item_h; display_h=area.height # type: ignore
            track_h=max(1,display_h-handle.height); scroll_px=max(0,content_h-display_h) # type: ignore
            if track_h>0 and scroll_px>0: clamped_y=max(0,min(h_pos_y,track_h)); ratio=clamped_y/track_h; editor_state.dialog_file_scroll_y=ratio*scroll_px
    elif event.type == pygame.MOUSEWHEEL and dialog_type=="file_load" and editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(pygame.mouse.get_pos()):
        font_s=ED_CONFIG.FONT_CONFIG.get("small");item_h=(font_s.get_height()+6)if font_s else 22 # type: ignore
        scroll_v=event.y*item_h;content_h=len(editor_state.dialog_file_list)*item_h # type: ignore
        font_m=ED_CONFIG.FONT_CONFIG.get("medium");prompt_h=(font_m.get_height()+25)if font_m else 55 # type: ignore
        btns_h=40;display_h=editor_state.dialog_rect.height-prompt_h-btns_h-10
        max_s=max(0,content_h-display_h);editor_state.dialog_file_scroll_y-=scroll_v;editor_state.dialog_file_scroll_y=max(0,min(editor_state.dialog_file_scroll_y,max_s))

    if confirmed or cancelled:
        cb_confirm, cb_cancel = editor_state.dialog_callback_confirm, editor_state.dialog_callback_cancel
        editor_state.active_dialog_type = None
        if confirmed and cb_confirm:
            val_pass = selected_value
            try: cb_confirm(val_pass)
            except Exception as e:print(f"Err Confirm CB:{e}");traceback.print_exc()
        elif cancelled and cb_cancel:
            try: cb_cancel()
            except Exception as e:print(f"Err Cancel CB:{e}");traceback.print_exc()
        if editor_state.active_dialog_type is None: # If callback didn't start a new one
            editor_state.dialog_callback_confirm, editor_state.dialog_callback_cancel = None,None
            editor_state.dialog_input_text, editor_state.dialog_selected_file_index = "",-1
            editor_state.is_dragging_scrollbar = False
            editor_state.color_change_target_info = None

def handle_menu_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos; ui_rects = editor_state.ui_elements_rects
        if ui_rects.get("menu_new_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            def on_new_map_name(name:str):
                name=name.strip()
                if not name: editor_state.set_status_message("Map name empty.",3); start_text_input_dialog(editor_state,"Name:","",on_new_map_name,lambda:None); return
                editor_state.map_name_for_function_input=name
                def on_map_size(size_str:str):
                    try:
                        w,h=map(int,size_str.replace(" ","").split(','))
                        if not(w>0 and h>0): raise ValueError("Dims>0")
                        init_new_map_state(editor_state,editor_state.map_name_for_function_input,w,h)
                        if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):
                            editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' auto-saved.",3);pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                        else: editor_state.set_status_message(f"Auto-save fail for '{editor_state.map_name_for_function}'.",4);editor_state.unsaved_changes=True;pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        editor_state.current_editor_mode="editing_map"
                    except Exception as e: editor_state.set_status_message(f"Invalid size:{e}",3.5);start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None)
                start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None)
            start_text_input_dialog(editor_state,"New Map Name:","my_map",on_new_map_name,lambda:None)
        elif ui_rects.get("menu_load_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            def on_file_sel(fp:str):
                if load_map_from_json(editor_state,fp): editor_state.current_editor_mode="editing_map";pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            start_file_load_dialog(editor_state,on_confirm=on_file_sel,on_cancel=lambda:None)
        elif ui_rects.get("menu_quit",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos): pygame.event.post(pygame.event.Event(pygame.QUIT))

def _place_single_tile_at_grid(editor_state: EditorState, asset_key_to_place: str, grid_coords: Tuple[int, int]):
    gx, gy = grid_coords; wx, wy = gx * editor_state.grid_size, gy * editor_state.grid_size
    asset_data = editor_state.assets_palette.get(asset_key_to_place)
    if not asset_data: print(f"ERR PlaceSingle: No asset data for {asset_key_to_place}"); return
    game_id = asset_data["game_type_id"]; is_spawn = asset_data.get("category")=="spawn"
    if not is_spawn:
        for obj in editor_state.placed_objects:
            if obj.get("world_x")==wx and obj.get("world_y")==wy and obj.get("game_type_id")==game_id: return
    if is_spawn: editor_state.placed_objects = [o for o in editor_state.placed_objects if o.get("game_type_id")!=game_id]
    editor_state.placed_objects.append({"asset_editor_key":asset_key_to_place,"world_x":wx,"world_y":wy,"game_type_id":game_id})
    editor_state.unsaved_changes=True; editor_state.minimap_needs_regeneration=True
    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")

def _place_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    sel_key = editor_state.selected_asset_editor_key
    if not sel_key or sel_key == "tool_color_change": return # Do not place the color tool itself
    sel_info = editor_state.assets_palette.get(sel_key)
    if not sel_info: return
    if sel_key == "platform_wall_gray_2x2_placer":
        base_key = sel_info.get("places_asset_key")
        if not base_key: print("ERR PlaceTile: 2x2 placer no base key"); return
        for ro in range(2):
            for co in range(2): _place_single_tile_at_grid(editor_state,base_key,(grid_coords[0]+co,grid_coords[1]+ro))
        return
    _place_single_tile_at_grid(editor_state, sel_key, grid_coords)

def _erase_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    wx,wy = grid_coords[0]*editor_state.grid_size, grid_coords[1]*editor_state.grid_size; erased=False
    for i in range(len(editor_state.placed_objects)-1,-1,-1):
        obj=editor_state.placed_objects[i]
        if obj.get("world_x")==wx and obj.get("world_y")==wy:
            editor_state.placed_objects.pop(i); erased=True
            editor_state.unsaved_changes=True; editor_state.minimap_needs_regeneration=True
            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*"); break
    if erased: editor_state.set_status_message(f"Erased @ ({grid_coords[0]},{grid_coords[1]})",1.5)

def _is_asset_colorable(editor_state: EditorState, asset_editor_key: Optional[str]) -> bool:
    if not asset_editor_key: return False
    props = editor_state.assets_palette.get(asset_editor_key)
    return props.get("colorable",False) if props else False

def _perform_flood_fill_color_change(editor_state: EditorState, start_gx: int, start_gy: int,
                                     target_game_type_id: str, new_color: Tuple[int,int,int]):
    if not editor_state.color_change_target_info or \
       not _is_asset_colorable(editor_state, editor_state.color_change_target_info.get("asset_editor_key")):
        editor_state.set_status_message("Initial tile not colorable or target info missing.", 2.0)
        return

    queue = collections.deque([(start_gx, start_gy)]); visited = set([(start_gx,start_gy)]); colored_count = 0
    while queue:
        gx,gy=queue.popleft(); cell_colored_this_iter=False
        for i, obj in enumerate(editor_state.placed_objects):
            obj_gx, obj_gy = obj.get("world_x")//editor_state.grid_size, obj.get("world_y")//editor_state.grid_size
            current_obj_asset_key = obj.get("asset_editor_key")
            if obj_gx==gx and obj_gy==gy and obj.get("game_type_id")==target_game_type_id and _is_asset_colorable(editor_state, current_obj_asset_key):
                editor_state.placed_objects[i]["override_color"] = new_color
                if not cell_colored_this_iter: colored_count+=1; cell_colored_this_iter=True
        for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            next_gx,next_gy = gx+dx,gy+dy
            if (next_gx,next_gy) not in visited:
                neighbor_exists_and_colorable_and_same_type = False
                for obj_n in editor_state.placed_objects:
                    if obj_n.get("world_x")//editor_state.grid_size == next_gx and \
                       obj_n.get("world_y")//editor_state.grid_size == next_gy and \
                       obj_n.get("game_type_id")==target_game_type_id and \
                       _is_asset_colorable(editor_state, obj_n.get("asset_editor_key")):
                        neighbor_exists_and_colorable_and_same_type = True; break
                if neighbor_exists_and_colorable_and_same_type: visited.add((next_gx,next_gy)); queue.append((next_gx,next_gy))
    if colored_count>0:
        editor_state.unsaved_changes=True; editor_state.minimap_needs_regeneration=True
        pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        editor_state.set_status_message(f"Colored {colored_count} '{target_game_type_id}' tiles.",3)

def _update_continuous_camera_pan(editor_state: EditorState, map_view_rect: pygame.Rect, mouse_pos: Tuple[int,int], dt: float):
    if editor_state.active_dialog_type: editor_state.camera_momentum_pan=(0,0); return

    keys = pygame.key.get_pressed(); pan_px_sec = ED_CONFIG.KEY_PAN_SPEED_PIXELS_PER_SECOND
    edge_pan_px_sec = ED_CONFIG.EDGE_SCROLL_SPEED_PIXELS_PER_SECOND
    pan_amount, edge_pan_amount = pan_px_sec * dt, edge_pan_px_sec * dt
    cam_moved_by_direct_input = False

    dx, dy = 0.0, 0.0
    if keys[pygame.K_a]: dx -= pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_d]: dx += pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_w]: dy -= pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_s] and not (keys[pygame.K_LCTRL]or keys[pygame.K_RCTRL]): dy+=pan_amount; cam_moved_by_direct_input=True

    prev_is_mouse_over_map = editor_state.is_mouse_over_map_view
    editor_state.is_mouse_over_map_view = map_view_rect.collidepoint(mouse_pos)

    if editor_state.is_mouse_over_map_view:
        editor_state.camera_momentum_pan = (0.0, 0.0)
        if editor_state.last_mouse_pos_map_view and dt > 0.0001:
            vel_x = (mouse_pos[0] - editor_state.last_mouse_pos_map_view[0]) / dt
            vel_y = (mouse_pos[1] - editor_state.last_mouse_pos_map_view[1]) / dt
            editor_state.mouse_velocity_map_view = (vel_x, vel_y)
        else: editor_state.mouse_velocity_map_view = (0.0, 0.0)
        editor_state.last_mouse_pos_map_view = mouse_pos
        if not cam_moved_by_direct_input:
            zone=ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS
            if mouse_pos[0]<map_view_rect.left+zone: dx-=edge_pan_amount; cam_moved_by_direct_input=True
            elif mouse_pos[0]>map_view_rect.right-zone: dx+=edge_pan_amount; cam_moved_by_direct_input=True
            if mouse_pos[1]<map_view_rect.top+zone: dy-=edge_pan_amount; cam_moved_by_direct_input=True
            elif mouse_pos[1]>map_view_rect.bottom-zone: dy+=edge_pan_amount; cam_moved_by_direct_input=True
    elif prev_is_mouse_over_map and not editor_state.is_mouse_over_map_view:
        if not cam_moved_by_direct_input and (abs(editor_state.mouse_velocity_map_view[0]) > 1 or abs(editor_state.mouse_velocity_map_view[1]) > 1) :
            fling_vx = editor_state.mouse_velocity_map_view[0] * ED_CONFIG.CAMERA_MOMENTUM_INITIAL_MULTIPLIER
            fling_vy = editor_state.mouse_velocity_map_view[1] * ED_CONFIG.CAMERA_MOMENTUM_INITIAL_MULTIPLIER
            editor_state.camera_momentum_pan = (fling_vx, fling_vy)
        editor_state.last_mouse_pos_map_view = None
        editor_state.mouse_velocity_map_view = (0.0,0.0)

    if cam_moved_by_direct_input:
        editor_state.camera_momentum_pan = (0.0, 0.0)
        editor_state.camera_offset_x += dx
        editor_state.camera_offset_y += dy
    
    max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_rect.width)
    max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_rect.height)
    editor_state.camera_offset_x = max(0, min(editor_state.camera_offset_x, max_cam_x))
    editor_state.camera_offset_y = max(0, min(editor_state.camera_offset_y, max_cam_y))

def _pan_camera_via_minimap_click(editor_state: EditorState, screen_click_pos: Tuple[int,int],
                                  map_view_rect: pygame.Rect, asset_palette_rect: pygame.Rect):
    if not editor_state.minimap_rect_in_palette or not editor_state.minimap_surface: return
    click_x_rel = screen_click_pos[0] - editor_state.minimap_rect_in_palette.left
    click_y_rel = screen_click_pos[1] - editor_state.minimap_rect_in_palette.top
    minimap_w = editor_state.minimap_surface.get_width(); minimap_h = editor_state.minimap_surface.get_height()
    if minimap_w == 0 or minimap_h == 0: return
    click_x_rel = max(0, min(click_x_rel, minimap_w -1)); click_y_rel = max(0, min(click_y_rel, minimap_h -1))
    map_px_w, map_px_h = editor_state.get_map_pixel_width(), editor_state.get_map_pixel_height()
    target_world_x = (click_x_rel / minimap_w) * map_px_w; target_world_y = (click_y_rel / minimap_h) * map_px_h
    new_cam_x = target_world_x - map_view_rect.width / 2; new_cam_y = target_world_y - map_view_rect.height / 2
    max_cam_x = max(0, map_px_w - map_view_rect.width); max_cam_y = max(0, map_px_h - map_view_rect.height)
    editor_state.camera_offset_x = int(max(0, min(new_cam_x, max_cam_x)))
    editor_state.camera_offset_y = int(max(0, min(new_cam_y, max_cam_y)))
    editor_state.camera_momentum_pan = (0.0, 0.0)

def handle_editing_map_events(event: pygame.event.Event, editor_state: EditorState,
                              palette_section_rect: pygame.Rect, map_view_rect: pygame.Rect,
                              main_screen: pygame.Surface):
    general_mouse_pos = pygame.mouse.get_pos()

    if event.type == pygame.MOUSEWHEEL: # Asset palette scroll
        asset_list_rect = pygame.Rect(palette_section_rect.left, palette_section_rect.top + ED_CONFIG.MINIMAP_AREA_HEIGHT,
                                      palette_section_rect.width, palette_section_rect.height - ED_CONFIG.MINIMAP_AREA_HEIGHT - (ED_CONFIG.BUTTON_HEIGHT_STANDARD*0.8+ED_CONFIG.ASSET_PALETTE_ITEM_PADDING*2)) # type: ignore
        if asset_list_rect.collidepoint(general_mouse_pos):
            font_s = ED_CONFIG.FONT_CONFIG.get("small"); speed = (font_s.get_height()+ED_CONFIG.ASSET_PALETTE_ITEM_PADDING) if font_s else 20 # type: ignore
            editor_state.asset_palette_scroll_y -= event.y * speed
            max_scroll = max(0, editor_state.total_asset_palette_content_height - asset_list_rect.height)
            editor_state.asset_palette_scroll_y = max(0, min(editor_state.asset_palette_scroll_y, max_scroll))
    
    elif event.type == pygame.MOUSEBUTTONDOWN:
        mouse_pos_click = event.pos
        if event.button == 1: # Left Click
            # 1. Minimap Navigation Click
            if editor_state.minimap_rect_in_palette and editor_state.minimap_rect_in_palette.collidepoint(mouse_pos_click):
                editor_state.is_dragging_minimap_view = True
                _pan_camera_via_minimap_click(editor_state, mouse_pos_click, map_view_rect, palette_section_rect)
                return # Minimap click handled, no further processing for this click

            # 2. Asset Palette Click (BG color button or asset item)
            elif palette_section_rect.collidepoint(mouse_pos_click):
                bg_btn = editor_state.ui_elements_rects.get("palette_bg_color_button")
                if bg_btn and bg_btn.collidepoint(mouse_pos_click): # BG Color button
                    def on_bg_sel(nc:Tuple[int,int,int]):
                        if nc: editor_state.background_color=nc; editor_state.unsaved_changes=True; editor_state.minimap_needs_regeneration=True; pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*"); editor_state.set_status_message(f"BG:{nc}")
                    start_color_picker_dialog(editor_state,on_confirm=on_bg_sel,on_cancel=lambda:None); return
                
                for key,rect in editor_state.ui_elements_rects.get('asset_palette_items',{}).items(): # Asset item
                    if rect.collidepoint(mouse_pos_click):
                        editor_state.selected_asset_editor_key=key # This setter handles selected_asset_image_for_cursor
                        asset_data=editor_state.assets_palette[key]
                        editor_state.set_status_message(f"Selected: {asset_data['tooltip']}{'. Click tile on map.' if key=='tool_color_change' else ''}"); return
            
            # 3. Map View Click (Color Tool, Painting, or Dragging)
            elif map_view_rect.collidepoint(mouse_pos_click):
                wx,wy=mouse_pos_click[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_click[1]-map_view_rect.top+editor_state.camera_offset_y
                tx,ty=wx//editor_state.grid_size, wy//editor_state.grid_size

                if editor_state.selected_asset_editor_key=="tool_color_change": # COLOR TOOL ACTIVE
                    target_info_for_color_tool = None
                    for i, obj_iter in reversed(list(enumerate(editor_state.placed_objects))):
                        obj_asset_key = obj_iter.get("asset_editor_key")
                        if obj_iter.get("world_x")//editor_state.grid_size==tx and obj_iter.get("world_y")//editor_state.grid_size==ty and _is_asset_colorable(editor_state,obj_asset_key):
                            target_info_for_color_tool = {"asset_editor_key": obj_asset_key, "game_type_id": obj_iter["game_type_id"], "grid_x":tx, "grid_y":ty}
                            break
                    if target_info_for_color_tool:
                        editor_state.color_change_target_info = target_info_for_color_tool
                        def on_color_selected_for_flood_fill(new_color:Tuple[int,int,int]):
                            t_info = editor_state.color_change_target_info
                            if t_info and new_color: _perform_flood_fill_color_change(editor_state, t_info["grid_x"],t_info["grid_y"],t_info["game_type_id"],new_color)
                        start_color_picker_dialog(editor_state,on_confirm=on_color_selected_for_flood_fill,on_cancel=lambda: [editor_state.set_status_message("Color change cancelled."), setattr(editor_state, 'color_change_target_info', None)])
                    else: editor_state.set_status_message("Clicked non-colorable or empty tile.",2);
                    return # Color tool click processed

                elif editor_state.selected_asset_editor_key: # ASSET SELECTED FOR PLACEMENT
                    editor_state.is_painting_tiles=True; editor_state.last_painted_tile_coords=(tx,ty); _place_tile_at_grid(editor_state,(tx,ty))
                
                else: # NO ASSET SELECTED (try dragging object)
                    editor_state.dragging_object_index=None
                    for i,obj in reversed(list(enumerate(editor_state.placed_objects))):
                        info=editor_state.assets_palette.get(obj.get("asset_editor_key"))
                        if info and "original_size_pixels" in info:
                            obj_w,obj_h=info["original_size_pixels"]; obj_r=pygame.Rect(obj["world_x"],obj["world_y"],obj_w,obj_h) # type: ignore
                            if obj_r.collidepoint(wx,wy):
                                editor_state.dragging_object_index=i;editor_state.drag_start_mouse_map_x=wx;editor_state.drag_start_mouse_map_y=wy
                                editor_state.drag_object_original_x=obj["world_x"];editor_state.drag_object_original_y=obj["world_y"];editor_state.set_status_message(f"Dragging {info['tooltip']}");break
        
        elif event.button == 3: # Right Click (map view only for erase/save)
            if map_view_rect.collidepoint(mouse_pos_click):
                wx,wy=mouse_pos_click[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_click[1]-map_view_rect.top+editor_state.camera_offset_y
                tx,ty=wx//editor_state.grid_size, wy//editor_state.grid_size
                if pygame.key.get_mods()&(pygame.KMOD_LSHIFT|pygame.KMOD_RSHIFT): # Save All
                    if editor_state.map_name_for_function and editor_state.map_name_for_function!="untitled_map":
                        if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                    else: editor_state.set_status_message("Cannot save: Map not named.",4)
                else: # Erase
                    editor_state.is_erasing_tiles=True;editor_state.last_erased_tile_coords=(tx,ty);_erase_tile_at_grid(editor_state,(tx,ty))

    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button==1: # Left mouse up
            editor_state.is_painting_tiles=False;editor_state.last_painted_tile_coords=None
            if editor_state.dragging_object_index is not None: editor_state.dragging_object_index=None;editor_state.set_status_message("Drag complete")
            editor_state.is_dragging_minimap_view = False # Stop minimap drag
        elif event.button==3: # Right mouse up
            editor_state.is_erasing_tiles=False;editor_state.last_erased_tile_coords=None
        if editor_state.is_dragging_scrollbar:editor_state.is_dragging_scrollbar=False # General scrollbar release
    
    elif event.type == pygame.MOUSEMOTION:
        mouse_pos_motion = event.pos
        if editor_state.is_dragging_minimap_view: # If dragging minimap view
            _pan_camera_via_minimap_click(editor_state, mouse_pos_motion, map_view_rect, palette_section_rect)
            return # Minimap drag motion handled

        if editor_state.dragging_object_index is not None and 0<=editor_state.dragging_object_index<len(editor_state.placed_objects): # If dragging an object
            obj_drag=editor_state.placed_objects[editor_state.dragging_object_index]
            map_mx,map_my = mouse_pos_motion[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_motion[1]-map_view_rect.top+editor_state.camera_offset_y
            new_x,new_y = editor_state.drag_object_original_x+(map_mx-editor_state.drag_start_mouse_map_x), editor_state.drag_object_original_y+(map_my-editor_state.drag_start_mouse_map_y)
            snap_x,snap_y=(new_x//editor_state.grid_size)*editor_state.grid_size, (new_y//editor_state.grid_size)*editor_state.grid_size
            if obj_drag["world_x"]!=snap_x or obj_drag["world_y"]!=snap_y:
                obj_drag["world_x"],obj_drag["world_y"]=snap_x,snap_y
                editor_state.unsaved_changes=True;editor_state.minimap_needs_regeneration=True;pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        
        elif map_view_rect.collidepoint(mouse_pos_motion): # If mouse is over map view (for painting/erasing by dragging)
            map_mx,map_my = mouse_pos_motion[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_motion[1]-map_view_rect.top+editor_state.camera_offset_y
            curr_tx,curr_ty=map_mx//editor_state.grid_size, map_my//editor_state.grid_size; curr_grid=(curr_tx,curr_ty)
            btns=pygame.mouse.get_pressed(); not_color_tool = editor_state.selected_asset_editor_key!="tool_color_change"
            
            if editor_state.is_painting_tiles and btns[0] and editor_state.selected_asset_editor_key and not_color_tool and curr_grid!=editor_state.last_painted_tile_coords:
                _place_tile_at_grid(editor_state,curr_grid); editor_state.last_painted_tile_coords=curr_grid
            elif editor_state.is_erasing_tiles and btns[2] and not_color_tool and curr_grid!=editor_state.last_erased_tile_coords: # Erasing by RMB drag
                _erase_tile_at_grid(editor_state,curr_grid); editor_state.last_erased_tile_coords=curr_grid
        
        elif not map_view_rect.collidepoint(mouse_pos_motion): # Mouse left map view while painting/erasing
            if editor_state.is_painting_tiles: editor_state.is_painting_tiles=False; editor_state.last_painted_tile_coords=None
            if editor_state.is_erasing_tiles: editor_state.is_erasing_tiles=False; editor_state.last_erased_tile_coords=None

    elif event.type == pygame.KEYDOWN: # Discrete key presses
        if event.key==pygame.K_ESCAPE:
            if editor_state.selected_asset_editor_key: editor_state.selected_asset_editor_key=None;editor_state.set_status_message("Asset/Tool deselected")
            else:
                if editor_state.unsaved_changes:
                    if not getattr(editor_state,'_esc_exit_attempted',False): editor_state.set_status_message("Unsaved! Esc again to discard.",4);setattr(editor_state,'_esc_exit_attempted',True)
                    else: editor_state.current_editor_mode="menu";editor_state.reset_map_context();pygame.display.set_caption("Editor - Menu");SicherDelAttr(editor_state,'_esc_exit_attempted')
                else: editor_state.current_editor_mode="menu";editor_state.reset_map_context();pygame.display.set_caption("Editor - Menu");SicherDelAttr(editor_state,'_esc_exit_attempted')
        elif event.key!=pygame.K_ESCAPE and hasattr(editor_state,'_esc_exit_attempted'): SicherDelAttr(editor_state,'_esc_exit_attempted')
        elif event.key==pygame.K_g: editor_state.show_grid = not editor_state.show_grid; editor_state.minimap_needs_regeneration=True; editor_state.set_status_message(f"Grid {'ON'if editor_state.show_grid else 'OFF'}")
        elif event.key==pygame.K_s and (pygame.key.get_mods()&pygame.KMOD_CTRL):
            if editor_state.map_name_for_function and editor_state.map_name_for_function!="untitled_map":
                if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            else:editor_state.set_status_message("Cannot save: Map not named.",4)

def SicherDelAttr(obj, name):
    if hasattr(obj, name): delattr(obj, name)