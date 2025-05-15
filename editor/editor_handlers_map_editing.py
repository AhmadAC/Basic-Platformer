# editor/editor_handlers_map_editing.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events specifically for the map editing mode.
"""
import pygame
import os
import logging
from typing import Optional, Tuple

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_color_picker_dialog # For BG color
from editor_map_utils import save_map_to_json, export_map_to_game_python_script
# _is_asset_colorable and _perform_flood_fill_color_change are not needed as tile color tool is removed

logger = logging.getLogger(__name__)

def SicherDelAttr(obj, name): # Utility
    if hasattr(obj, name): delattr(obj, name)

# --- Helper functions for map editing actions ---
def _place_single_tile_at_grid(editor_state: EditorState, asset_key_to_place: str, grid_coords: Tuple[int, int]):
    logger.debug(f"_place_single_tile_at_grid: Placing '{asset_key_to_place}' at {grid_coords}")
    gx, gy = grid_coords; wx, wy = gx * editor_state.grid_size, gy * editor_state.grid_size
    asset_data = editor_state.assets_palette.get(asset_key_to_place)
    if not asset_data: 
        logger.error(f"ERR PlaceSingle: No asset data for {asset_key_to_place}"); return
    
    game_id = asset_data["game_type_id"]
    is_spawn = asset_data.get("category")=="spawn"

    # Prevent duplicate non-spawn items at the same grid cell (based on game_type_id)
    if not is_spawn:
        for obj in editor_state.placed_objects:
            if obj.get("world_x")==wx and obj.get("world_y")==wy and obj.get("game_type_id")==game_id:
                logger.debug(f"Duplicate tile '{game_id}' at {grid_coords}, not placing.")
                return
    
    # If placing a spawn point, remove any existing spawn point of the same type
    if is_spawn: 
        editor_state.placed_objects = [o for o in editor_state.placed_objects if o.get("game_type_id")!=game_id]

    editor_state.placed_objects.append({
        "asset_editor_key":asset_key_to_place,
        "world_x":wx, "world_y":wy,
        "game_type_id":game_id
    })
    editor_state.unsaved_changes=True
    editor_state.minimap_needs_regeneration=True
    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")

def _place_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    sel_key = editor_state.selected_asset_editor_key
    logger.debug(f"_place_tile_at_grid: current selected_asset_editor_key = '{sel_key}' for grid {grid_coords}")

    if not sel_key:
        logger.debug(f"_place_tile_at_grid: Bailing out. sel_key is None.")
        return

    sel_info = editor_state.assets_palette.get(sel_key)
    if not sel_info:
        logger.error(f"_place_tile_at_grid: No asset info for selected key '{sel_key}'")
        return

    # Handle special placer tools
    if sel_info.get("places_asset_key"): # e.g., 2x2 placer
        base_key_to_place = sel_info["places_asset_key"]
        if not base_key_to_place: 
            logger.error(f"ERR PlaceTile: Placer tool '{sel_key}' has no 'places_asset_key' defined."); return
        
        # Example for a 2x2 placer, can be generalized if more placers exist
        if sel_key == "platform_wall_gray_2x2_placer": # Example specific ID
            logger.debug(f"_place_tile_at_grid: Handling 2x2 placer for base_key '{base_key_to_place}' at {grid_coords}")
            for row_offset in range(2):
                for col_offset in range(2):
                    _place_single_tile_at_grid(editor_state, base_key_to_place, (grid_coords[0]+col_offset, grid_coords[1]+row_offset))
            return # Placer handled
        # Add other placer logic here if needed
    
    # Default: place the selected asset itself
    logger.debug(f"_place_tile_at_grid: Proceeding to place single tile for '{sel_key}' at {grid_coords}")
    _place_single_tile_at_grid(editor_state, sel_key, grid_coords)


def _erase_tile_at_grid(editor_state: EditorState, grid_coords: Tuple[int, int]):
    wx,wy = grid_coords[0]*editor_state.grid_size, grid_coords[1]*editor_state.grid_size
    erased_count = 0
    
    # Iterate backwards to safely remove items from the list
    for i in range(len(editor_state.placed_objects)-1,-1,-1):
        obj=editor_state.placed_objects[i]
        # Check if the object's bounding box (approximated by grid cell for simplicity here) contains the click
        # For more precise erase of larger objects, you'd need actual object dimensions
        if obj.get("world_x")==wx and obj.get("world_y")==wy:
            logger.info(f"Erasing object at {grid_coords}: {obj}")
            editor_state.placed_objects.pop(i)
            erased_count += 1
            # For now, erase only the first found object in a cell. 
            # If multiple objects can stack and need individual erase, this logic would need adjustment.
            break 
            
    if erased_count > 0:
        editor_state.unsaved_changes=True
        editor_state.minimap_needs_regeneration=True
        pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        editor_state.set_status_message(f"Erased {erased_count} object(s) @ ({grid_coords[0]},{grid_coords[1]})",1.5)


def _pan_camera_via_minimap_click(editor_state: EditorState, screen_click_pos: Tuple[int,int],
                                  map_view_rect: pygame.Rect, asset_palette_rect: pygame.Rect): # asset_palette_rect might not be needed
    if not editor_state.minimap_rect_in_palette or not editor_state.minimap_surface: return
    
    click_x_rel = screen_click_pos[0] - editor_state.minimap_rect_in_palette.left
    click_y_rel = screen_click_pos[1] - editor_state.minimap_rect_in_palette.top
    
    minimap_w = editor_state.minimap_surface.get_width(); minimap_h = editor_state.minimap_surface.get_height()
    if minimap_w == 0 or minimap_h == 0: return

    # Clamp click to be within the minimap surface dimensions
    click_x_rel = max(0, min(click_x_rel, minimap_w -1))
    click_y_rel = max(0, min(click_y_rel, minimap_h -1))

    map_px_w, map_px_h = editor_state.get_map_pixel_width(), editor_state.get_map_pixel_height()
    
    target_world_x = (click_x_rel / minimap_w) * map_px_w
    target_world_y = (click_y_rel / minimap_h) * map_px_h
    
    # Center the map view on the clicked world position
    new_cam_x = target_world_x - map_view_rect.width / 2
    new_cam_y = target_world_y - map_view_rect.height / 2
    
    max_cam_x = max(0, map_px_w - map_view_rect.width)
    max_cam_y = max(0, map_px_h - map_view_rect.height)
    
    editor_state.camera_offset_x = int(max(0, min(new_cam_x, max_cam_x)))
    editor_state.camera_offset_y = int(max(0, min(new_cam_y, max_cam_y)))
    editor_state.camera_momentum_pan = (0.0, 0.0) # Stop any existing camera pan momentum
    logger.debug(f"Minimap click: Panned camera to center around world ({target_world_x:.0f},{target_world_y:.0f}). New offset: ({editor_state.camera_offset_x},{editor_state.camera_offset_y})")


# --- Main event handler for map editing mode ---
def handle_editing_map_events(event: pygame.event.Event, editor_state: EditorState,
                              palette_section_rect: pygame.Rect, map_view_rect: pygame.Rect,
                              main_screen: pygame.Surface): # main_screen might not be needed
    general_mouse_pos = pygame.mouse.get_pos()

    if event.type == pygame.MOUSEWHEEL:
        asset_list_rect = pygame.Rect(
            palette_section_rect.left, 
            palette_section_rect.top + ED_CONFIG.MINIMAP_AREA_HEIGHT,
            palette_section_rect.width, 
            palette_section_rect.height - ED_CONFIG.MINIMAP_AREA_HEIGHT - (ED_CONFIG.BUTTON_HEIGHT_STANDARD*0.8+ED_CONFIG.ASSET_PALETTE_ITEM_PADDING*2) 
        )
        if asset_list_rect.collidepoint(general_mouse_pos):
            kick_value = -event.y * ED_CONFIG.ASSET_PALETTE_SCROLL_KICK_MULTIPLIER
            editor_state.asset_palette_scroll_momentum += kick_value
            
            current_momentum = editor_state.asset_palette_scroll_momentum
            max_momentum = ED_CONFIG.ASSET_PALETTE_MAX_MOMENTUM
            editor_state.asset_palette_scroll_momentum = max(-max_momentum, min(current_momentum, max_momentum))
            
            logger.debug(f"Asset palette MOUSEWHEEL: event.y={event.y}, kick={kick_value}, new momentum={editor_state.asset_palette_scroll_momentum}")

    elif event.type == pygame.MOUSEBUTTONDOWN:
        mouse_pos_click = event.pos
        logger.debug(f"MOUSEBUTTONDOWN event.button={event.button} at {mouse_pos_click}. Selected asset: '{editor_state.selected_asset_editor_key}'")
        
        if palette_section_rect.collidepoint(mouse_pos_click):
            editor_state.asset_palette_scroll_momentum = 0.0 # Stop fling on click in palette

        if event.button == 1: # Left Mouse Button
            if editor_state.minimap_rect_in_palette and editor_state.minimap_rect_in_palette.collidepoint(mouse_pos_click):
                logger.debug("Left click on minimap area.")
                editor_state.is_dragging_minimap_view = True
                _pan_camera_via_minimap_click(editor_state, mouse_pos_click, map_view_rect, palette_section_rect)
                return # Minimap click handled
            
            elif palette_section_rect.collidepoint(mouse_pos_click):
                logger.debug("Left click in asset palette section.")
                bg_btn = editor_state.ui_elements_rects.get("palette_bg_color_button")
                if bg_btn and bg_btn.collidepoint(mouse_pos_click):
                    logger.info("BG Color button clicked.")
                    def on_bg_sel(nc:Optional[Tuple[int,int,int]]):
                        if nc: 
                            editor_state.background_color=nc
                            editor_state.unsaved_changes=True
                            editor_state.minimap_needs_regeneration=True
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                            editor_state.set_status_message(f"BG Color set to: {nc}")
                        else:
                            editor_state.set_status_message("BG Color selection cancelled.")
                    start_color_picker_dialog(editor_state,on_confirm=on_bg_sel,on_cancel=lambda: editor_state.set_status_message("BG Color selection cancelled."))
                    return # BG Color button handled
                
                # Check asset palette item clicks
                for key,rect in editor_state.ui_elements_rects.get('asset_palette_items',{}).items():
                    if rect.collidepoint(mouse_pos_click):
                        logger.info(f"Asset palette item '{key}' clicked.")
                        editor_state.selected_asset_editor_key = key
                        asset_data = editor_state.assets_palette.get(key)
                        if asset_data:
                             editor_state.set_status_message(f"Selected: {asset_data['tooltip']}")
                        else:
                             logger.error(f"Could not find asset data for key '{key}' in palette after selection.")
                        return # Asset selected
            
            elif map_view_rect.collidepoint(mouse_pos_click):
                logger.debug("Left click in map view section.")
                wx,wy=mouse_pos_click[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_click[1]-map_view_rect.top+editor_state.camera_offset_y
                tx,ty=wx//editor_state.grid_size, wy//editor_state.grid_size
                logger.debug(f"Map click at grid ({tx},{ty}). Current asset: '{editor_state.selected_asset_editor_key}'")
                
                if editor_state.selected_asset_editor_key: 
                    logger.debug(f"Attempting to place asset '{editor_state.selected_asset_editor_key}' at grid ({tx},{ty})")
                    editor_state.is_painting_tiles=True; editor_state.last_painted_tile_coords=(tx,ty); _place_tile_at_grid(editor_state,(tx,ty))
                
                else: # No asset selected, try dragging an existing object
                    logger.debug("No asset selected, attempting to drag object.")
                    editor_state.dragging_object_index=None
                    for i,obj in reversed(list(enumerate(editor_state.placed_objects))):
                        info=editor_state.assets_palette.get(obj.get("asset_editor_key"))
                        if info and "original_size_pixels" in info:
                            obj_w,obj_h=info["original_size_pixels"]; obj_r=pygame.Rect(obj["world_x"],obj["world_y"],obj_w,obj_h) 
                            if obj_r.collidepoint(wx,wy):
                                editor_state.dragging_object_index=i;editor_state.drag_start_mouse_map_x=wx;editor_state.drag_start_mouse_map_y=wy
                                editor_state.drag_object_original_x=obj["world_x"];editor_state.drag_object_original_y=obj["world_y"];editor_state.set_status_message(f"Dragging {info['tooltip']}");break
        
        elif event.button == 3: # Right Mouse Button
            if map_view_rect.collidepoint(mouse_pos_click):
                wx,wy=mouse_pos_click[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_click[1]-map_view_rect.top+editor_state.camera_offset_y
                tx,ty=wx//editor_state.grid_size, wy//editor_state.grid_size
                if pygame.key.get_mods()&(pygame.KMOD_LSHIFT|pygame.KMOD_RSHIFT):
                    logger.info("Shift+RMB click on map: Save All attempt.")
                    if editor_state.map_name_for_function and editor_state.map_name_for_function!="untitled_map":
                        if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                    else: 
                        editor_state.set_status_message("Cannot save: Map not named.",4)
                else:
                    logger.info(f"RMB click on map at grid ({tx},{ty}): Erase attempt.")
                    editor_state.is_erasing_tiles=True;editor_state.last_erased_tile_coords=(tx,ty);_erase_tile_at_grid(editor_state,(tx,ty))

    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button==1:
            editor_state.is_painting_tiles=False;editor_state.last_painted_tile_coords=None
            if editor_state.dragging_object_index is not None: 
                editor_state.dragging_object_index=None;editor_state.set_status_message("Drag complete")
            if editor_state.is_dragging_minimap_view: 
                logger.debug("Minimap drag released."); editor_state.is_dragging_minimap_view = False
        elif event.button==3: 
            editor_state.is_erasing_tiles=False;editor_state.last_erased_tile_coords=None
        
        if editor_state.is_dragging_scrollbar: # This is for file dialog scrollbar
            editor_state.is_dragging_scrollbar=False

    elif event.type == pygame.MOUSEMOTION:
        mouse_pos_motion = event.pos
        if editor_state.is_dragging_minimap_view:
            _pan_camera_via_minimap_click(editor_state, mouse_pos_motion, map_view_rect, palette_section_rect)
            return # Minimap drag motion handled
        
        if editor_state.dragging_object_index is not None and 0<=editor_state.dragging_object_index<len(editor_state.placed_objects):
            obj_drag=editor_state.placed_objects[editor_state.dragging_object_index]
            map_mx,map_my = mouse_pos_motion[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_motion[1]-map_view_rect.top+editor_state.camera_offset_y
            new_x,new_y = editor_state.drag_object_original_x+(map_mx-editor_state.drag_start_mouse_map_x), editor_state.drag_object_original_y+(map_my-editor_state.drag_start_mouse_map_y)
            snap_x,snap_y=(new_x//editor_state.grid_size)*editor_state.grid_size, (new_y//editor_state.grid_size)*editor_state.grid_size
            if obj_drag["world_x"]!=snap_x or obj_drag["world_y"]!=snap_y:
                obj_drag["world_x"],obj_drag["world_y"]=snap_x,snap_y
                editor_state.unsaved_changes=True;editor_state.minimap_needs_regeneration=True;pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
        elif map_view_rect.collidepoint(mouse_pos_motion): # Mouse is over map view (but not dragging an object)
            map_mx,map_my = mouse_pos_motion[0]-map_view_rect.left+editor_state.camera_offset_x, mouse_pos_motion[1]-map_view_rect.top+editor_state.camera_offset_y
            curr_tx,curr_ty=map_mx//editor_state.grid_size, map_my//editor_state.grid_size; curr_grid=(curr_tx,curr_ty)
            btns=pygame.mouse.get_pressed()
            
            if editor_state.is_painting_tiles and btns[0] and editor_state.selected_asset_editor_key and curr_grid!=editor_state.last_painted_tile_coords:
                _place_tile_at_grid(editor_state,curr_grid); editor_state.last_painted_tile_coords=curr_grid
            elif editor_state.is_erasing_tiles and btns[2] and curr_grid!=editor_state.last_erased_tile_coords:
                _erase_tile_at_grid(editor_state,curr_grid); editor_state.last_erased_tile_coords=curr_grid
        elif not map_view_rect.collidepoint(mouse_pos_motion): # Mouse moved out of map view
            if editor_state.is_painting_tiles: 
                editor_state.is_painting_tiles=False; editor_state.last_painted_tile_coords=None
            if editor_state.is_erasing_tiles: 
                editor_state.is_erasing_tiles=False; editor_state.last_erased_tile_coords=None

    elif event.type == pygame.KEYDOWN:
        if event.key==pygame.K_ESCAPE:
            if editor_state.selected_asset_editor_key: 
                logger.info("Escape pressed: Deselecting asset."); 
                editor_state.selected_asset_editor_key=None
                editor_state.set_status_message("Asset deselected")
            else: # No asset selected, try to go to menu
                logger.info("Escape pressed: No asset selected, attempting to go to menu.")
                if editor_state.unsaved_changes:
                    if not getattr(editor_state,'_esc_exit_attempted',False): 
                        editor_state.set_status_message("Unsaved! Esc again to discard.",4)
                        setattr(editor_state,'_esc_exit_attempted',True)
                    else: 
                        editor_state.current_editor_mode="menu"
                        editor_state.reset_map_context()
                        pygame.display.set_caption("Editor - Menu")
                        SicherDelAttr(editor_state,'_esc_exit_attempted')
                else: 
                    editor_state.current_editor_mode="menu"
                    editor_state.reset_map_context()
                    pygame.display.set_caption("Editor - Menu")
                    SicherDelAttr(editor_state,'_esc_exit_attempted')
        elif event.key!=pygame.K_ESCAPE and hasattr(editor_state,'_esc_exit_attempted'): 
            SicherDelAttr(editor_state,'_esc_exit_attempted')
        elif event.key==pygame.K_g: 
            logger.info("G key pressed: Toggling grid."); 
            editor_state.show_grid = not editor_state.show_grid
            editor_state.minimap_needs_regeneration=True
            editor_state.set_status_message(f"Grid {'ON'if editor_state.show_grid else 'OFF'}")
        elif event.key==pygame.K_s and (pygame.key.get_mods()&pygame.KMOD_CTRL):
            logger.info("Ctrl+S pressed: Save All attempt.")
            if editor_state.map_name_for_function and editor_state.map_name_for_function!="untitled_map":
                if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            else:
                editor_state.set_status_message("Cannot save: Map not named.",4)