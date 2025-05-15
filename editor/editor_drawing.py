# editor_drawing.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.13 (Removed all semicolons again, verified side-by-side spawn)
Contains functions for drawing the different sections and elements
of the Platformer Level Editor UI using Pygame.
"""
import pygame
from typing import Dict, Tuple, Any, Optional 
import traceback 

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import draw_button


def draw_menu_ui(surface: pygame.Surface, editor_state: EditorState, menu_section_rect: pygame.Rect,
                 fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int]):
    try:
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), menu_section_rect) 
        title_font = fonts.get("large") or ED_CONFIG.FONT_CONFIG.get("large")
        button_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")

        if title_font:
            title_surf = title_font.render("Level Editor", True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
            title_rect = title_surf.get_rect(centerx=menu_section_rect.centerx, top=menu_section_rect.top + 20)
            surface.blit(title_surf, title_rect)
        
        button_w = ED_CONFIG.BUTTON_WIDTH_STANDARD
        button_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD
        spacing = 20
        num_buttons = 3
        total_button_h = (num_buttons * button_h) + ((num_buttons - 1) * spacing)
        title_h_approx = title_font.get_height() if title_font else 40
        content_start_y = menu_section_rect.top + title_h_approx + 30
        remaining_h = menu_section_rect.height - (content_start_y - menu_section_rect.top)
        start_y = max(content_start_y + (remaining_h - total_button_h) // 2, content_start_y)

        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
            editor_state.ui_elements_rects = {}
        for k in [key for key in editor_state.ui_elements_rects if key.startswith("menu_")]:
            del editor_state.ui_elements_rects[k]
        
        if button_font:
            rect_params = [
                (start_y, "menu_new_map", "New Map"), 
                (start_y + button_h + spacing, "menu_load_map", "Load Map (.json)"),
                (start_y + 2 * (button_h + spacing), "menu_quit", "Quit Editor")
            ]
            for top_y, key, text in rect_params:
                btn_r = pygame.Rect(0,0,button_w,button_h)
                btn_r.centerx = menu_section_rect.centerx
                btn_r.top = top_y
                editor_state.ui_elements_rects[key] = btn_r
                draw_button(surface, btn_r, text, button_font, mouse_pos)
        else: 
            print("Warning DRAW: Menu button font missing.")
    except Exception as e: 
        print(f"ERROR DRAW: Exception in draw_menu_ui: {e}")
        traceback.print_exc()


def _draw_single_palette_item(scroll_surf: pygame.Surface, 
                              editor_state: EditorState, 
                              palette_section_rect: pygame.Rect, 
                              asset_key: str, asset_data: Dict[str, Any], 
                              item_x: int, item_y_on_scroll: int, 
                              tip_font: Optional[pygame.font.Font], 
                              mouse_pos: Tuple[int, int]) -> int:
    img = asset_data.get("image")
    tooltip_text = asset_data.get("tooltip", asset_key)
    if not img: return 0 

    item_rect_on_screen = pygame.Rect(
        palette_section_rect.left + item_x,
        palette_section_rect.top + item_y_on_scroll - editor_state.asset_palette_scroll_y,
        img.get_width(), img.get_height()
    )
    editor_state.ui_elements_rects['asset_palette_items'][asset_key] = item_rect_on_screen

    is_hovered = item_rect_on_screen.collidepoint(mouse_pos) and palette_section_rect.collidepoint(mouse_pos)
    is_selected = editor_state.selected_asset_editor_key == asset_key

    if is_hovered:
        editor_state.hovered_tooltip_text = tooltip_text
        editor_state.hovered_tooltip_pos = mouse_pos
        hover_bg_r = pygame.Rect(item_x - 2, item_y_on_scroll - 2, img.get_width() + 4, img.get_height() + 4)
        pygame.draw.rect(scroll_surf, ED_CONFIG.ASSET_PALETTE_HOVER_BG_COLOR, hover_bg_r, border_radius=2)
    if is_selected:
        select_b_r = pygame.Rect(item_x - 3, item_y_on_scroll - 3, img.get_width() + 6, img.get_height() + 6)
        pygame.draw.rect(scroll_surf, ED_CONFIG.C.YELLOW, select_b_r, 2, border_radius=3)
    
    scroll_surf.blit(img, (item_x, item_y_on_scroll))
    current_item_total_height = img.get_height()

    if tip_font:
        name_s = tip_font.render(tooltip_text, True, ED_CONFIG.ASSET_PALETTE_TOOLTIP_COLOR)
        text_x = item_x + (img.get_width() - name_s.get_width()) // 2
        scroll_surf.blit(name_s, (max(item_x, text_x), item_y_on_scroll + img.get_height() + 2))
        current_item_total_height += name_s.get_height() + 2
    
    return current_item_total_height


def draw_asset_palette_ui(surface: pygame.Surface, editor_state: EditorState, palette_section_rect: pygame.Rect,
                          fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int]):
    try:
        pygame.draw.rect(surface, ED_CONFIG.ASSET_PALETTE_BG_COLOR, palette_section_rect)
        if editor_state.total_asset_palette_content_height <= 0:
            font_small = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
            if font_small:
                no_assets_text = "Assets Loading/Error..."
                if not ED_CONFIG.EDITOR_PALETTE_ASSETS: no_assets_text = "No assets defined."
                elif not editor_state.assets_palette : no_assets_text = "Asset palette empty."
                msg_surf = font_small.render(no_assets_text, True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
                surface.blit(msg_surf, msg_surf.get_rect(center=palette_section_rect.center))
            return

        scroll_surf = pygame.Surface((palette_section_rect.width, editor_state.total_asset_palette_content_height), pygame.SRCALPHA)
        scroll_surf.fill((0,0,0,0)) 
        current_y_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
        cat_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
        tip_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        
        editor_state.hovered_tooltip_text = None
        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None: editor_state.ui_elements_rects = {}
        editor_state.ui_elements_rects['asset_palette_items'] = {}
        
        categories_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER', 
                                   ["tile", "hazard", "item", "enemy", "spawn", "unknown"])

        for cat_name in categories_order:
            assets_in_category_tuples = [(k, d) for k, d in editor_state.assets_palette.items() if d.get("category", "unknown") == cat_name]
            if not assets_in_category_tuples: continue

            if cat_font:
                cat_surf = cat_font.render(cat_name.title(), True, ED_CONFIG.ASSET_PALETTE_CATEGORY_TEXT_COLOR)
                scroll_surf.blit(cat_surf, (ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, current_y_on_scroll_surf))
                current_y_on_scroll_surf += cat_surf.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
            
            row_start_y_for_current_items = current_y_on_scroll_surf 
            
            if cat_name == "spawn":
                p1_item_tuple = next(((k,d) for k,d in assets_in_category_tuples if k == "player1_spawn"), None)
                p2_item_tuple = next(((k,d) for k,d in assets_in_category_tuples if k == "player2_spawn"), None)
                other_items_in_this_category = [item for item in assets_in_category_tuples if item[0] not in ["player1_spawn", "player2_spawn"]]
                
                current_x_in_row = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                max_h_for_this_row = 0

                if p1_item_tuple:
                    h = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, p1_item_tuple[0], p1_item_tuple[1], current_x_in_row, row_start_y_for_current_items, tip_font, mouse_pos)
                    max_h_for_this_row = max(max_h_for_this_row, h)
                    if p1_item_tuple[1].get("image"):
                        current_x_in_row += p1_item_tuple[1]["image"].get_width() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING 
                
                if p2_item_tuple:
                    p2_img = p2_item_tuple[1].get("image")
                    if p2_img and current_x_in_row + p2_img.get_width() > palette_section_rect.width - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING:
                        # Not enough horizontal space for P2 on the same line, advance Y
                        current_y_on_scroll_surf = row_start_y_for_current_items + max_h_for_this_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                        row_start_y_for_current_items = current_y_on_scroll_surf # Update row_start_y for P2
                        current_x_in_row = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Reset X for P2
                        max_h_for_this_row = 0 # Reset max height for this new "row" (which only has P2)

                    h = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, p2_item_tuple[0], p2_item_tuple[1], current_x_in_row, row_start_y_for_current_items, tip_font, mouse_pos)
                    max_h_for_this_row = max(max_h_for_this_row, h)
                
                if max_h_for_this_row > 0:
                    current_y_on_scroll_surf = row_start_y_for_current_items + max_h_for_this_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                
                assets_to_draw_this_category_loop = other_items_in_this_category
            else:
                assets_to_draw_this_category_loop = assets_in_category_tuples

            for asset_key, asset_data in assets_to_draw_this_category_loop:
                item_x_vertical = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                item_y_vertical = current_y_on_scroll_surf
                
                item_total_height = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, asset_key, asset_data, item_x_vertical, item_y_vertical, tip_font, mouse_pos)
                current_y_on_scroll_surf = item_y_vertical + item_total_height + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
            
            if assets_in_category_tuples : 
                current_y_on_scroll_surf += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING

        surface.blit(scroll_surf, palette_section_rect.topleft, (0, editor_state.asset_palette_scroll_y, palette_section_rect.width, palette_section_rect.height))
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'GRAY', (128,128,128)), palette_section_rect, 2)
        btn_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if btn_font:
            btn_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD*0.8
            cp_btn_r = pygame.Rect(palette_section_rect.left+ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, palette_section_rect.bottom-btn_h-ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, palette_section_rect.width-ED_CONFIG.ASSET_PALETTE_ITEM_PADDING*2, int(btn_h))
            editor_state.ui_elements_rects["palette_bg_color_button"] = cp_btn_r
            bg_lum = sum(editor_state.background_color)/3
            txt_col = getattr(ED_CONFIG.C, 'BLACK', (0,0,0)) if bg_lum > 128*1.5 else getattr(ED_CONFIG.C, 'WHITE', (255,255,255))
            draw_button(surface,cp_btn_r,"BG Color",btn_font,mouse_pos,text_color=txt_col,button_color_normal=editor_state.background_color,button_color_hover=pygame.Color(editor_state.background_color).lerp(getattr(ED_CONFIG.C, 'WHITE', (255,255,255)),0.3),border_color=getattr(ED_CONFIG.C, 'BLACK', (0,0,0)))
    except Exception as e: 
        print(f"ERROR DRAW: draw_asset_palette_ui: {e}")
        traceback.print_exc()


def draw_map_view_ui(surface: pygame.Surface, editor_state: EditorState, map_view_rect: pygame.Rect,
                     fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int]):
    try:
        if not editor_state.map_content_surface:
            pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'DARK_GRAY', (50,50,50)), map_view_rect) 
            ph_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
            if ph_font: 
                txt_surf = ph_font.render("No Map/Surface Error", True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
                surface.blit(txt_surf, txt_surf.get_rect(center=map_view_rect.center))
            pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2)
            return

        editor_state.map_content_surface.fill(editor_state.background_color)
        for obj in editor_state.placed_objects:
            key,wx,wy=obj.get("asset_editor_key"),obj.get("world_x"),obj.get("world_y")
            if wx is None or wy is None: continue
            info = editor_state.assets_palette.get(key) if key else None
            if info and info.get("image"): 
                editor_state.map_content_surface.blit(info["image"], (wx,wy))
            else: 
                pygame.draw.rect(editor_state.map_content_surface, getattr(ED_CONFIG.C, 'RED', (255,0,0)), (wx,wy,editor_state.grid_size,editor_state.grid_size),1)
        
        if editor_state.show_grid: 
            draw_grid_on_map_surface(editor_state.map_content_surface, editor_state)
        
        surface.blit(editor_state.map_content_surface, map_view_rect.topleft, (editor_state.camera_offset_x, editor_state.camera_offset_y, map_view_rect.width, map_view_rect.height))
        pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2)
        
        if editor_state.selected_asset_image_for_cursor:
            img = editor_state.selected_asset_image_for_cursor
            pos = img.get_rect(center=mouse_pos).topleft
            if map_view_rect.collidepoint(mouse_pos):
                world_mx = mouse_pos[0]-map_view_rect.left+editor_state.camera_offset_x
                world_my = mouse_pos[1]-map_view_rect.top+editor_state.camera_offset_y
                grid_wx = (world_mx//editor_state.grid_size)*editor_state.grid_size
                grid_wy = (world_my//editor_state.grid_size)*editor_state.grid_size
                pos = (grid_wx-editor_state.camera_offset_x+map_view_rect.left, grid_wy-editor_state.camera_offset_y+map_view_rect.top)
            
            clip_orig = surface.get_clip()
            surface.set_clip(map_view_rect)
            surface.blit(img,pos)
            surface.set_clip(clip_orig)
        
        _draw_map_view_info_text(surface, editor_state, map_view_rect, fonts, mouse_pos)
    except Exception as e: 
        print(f"ERROR DRAW: draw_map_view_ui: {e}")
        traceback.print_exc()

def _draw_map_view_info_text(surface: pygame.Surface, editor_state: EditorState, map_view_rect: pygame.Rect, 
                             fonts: Dict[str, Optional[pygame.font.Font]], general_mouse_pos: Tuple[int, int]):
    info_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if not info_font: return

    lines = ["LMB Drag: Paint, RMB Drag: Erase", "WASD: Pan, G: Grid, ESC: Deselect/Menu", "Shift+RMB(Map): Save All", "Ctrl+S: Save All"]
    line_h = info_font.get_height()+3
    y_start = map_view_rect.bottom+7
    
    for i,line_text in enumerate(lines):
        txt_surf = info_font.render(line_text,True,getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)))
        y_draw = y_start + i*line_h
        if y_draw + line_h > surface.get_height()-5: 
            y_draw = surface.get_height()-5 - line_h*(len(lines)-i)
        if i==0: y_draw = max(5, y_draw) 
        surface.blit(txt_surf, (map_view_rect.left+5, y_draw))
        
    coords_text_str = f"Cam:({editor_state.camera_offset_x},{editor_state.camera_offset_y})"
    if map_view_rect.collidepoint(general_mouse_pos):
        world_mx = general_mouse_pos[0]-map_view_rect.left+editor_state.camera_offset_x
        world_my = general_mouse_pos[1]-map_view_rect.top+editor_state.camera_offset_y
        tx,ty = world_mx//editor_state.grid_size, world_my//editor_state.grid_size
        coords_text_str += f" MouseW:({world_mx},{world_my}) Tile:({tx},{ty})"
    
    coords_surf = info_font.render(coords_text_str,True,getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
    coords_y_pos = map_view_rect.top-coords_surf.get_height()-4
    coords_x_pos = map_view_rect.left+5
    if coords_y_pos < 5: 
        coords_y_pos = y_start + len(lines)*line_h + 5 
        if coords_y_pos + coords_surf.get_height() > surface.get_height()-5: 
             coords_y_pos = surface.get_height()-5-coords_surf.get_height()
    surface.blit(coords_surf, (coords_x_pos, coords_y_pos))

def draw_grid_on_map_surface(map_content_surface: pygame.Surface, editor_state: EditorState):
    if not (editor_state.show_grid and editor_state.map_content_surface and editor_state.grid_size > 0): return
    w,h,gs = editor_state.get_map_pixel_width(), editor_state.get_map_pixel_height(), editor_state.grid_size
    gc = getattr(ED_CONFIG, 'MAP_VIEW_GRID_COLOR', (128,128,128)) 
    try:
        for x_coord in range(0, w + gs, gs): 
            pygame.draw.line(map_content_surface,gc,(x_coord,0),(x_coord,h)) 
        for y_coord in range(0, h + gs, gs): 
            pygame.draw.line(map_content_surface,gc,(0,y_coord),(w,y_coord)) 
    except Exception as e: 
        print(f"ERROR DRAW: draw_grid_on_map_surface: {e}")
        traceback.print_exc()