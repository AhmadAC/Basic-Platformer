# editor_drawing.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.19 (Added Asset Palette Options Dropdown Drawing)
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
        spacing = 12
        num_buttons = 5
        total_button_h = (num_buttons * button_h) + ((num_buttons - 1) * spacing)
        title_h_approx = title_font.get_height() if title_font else 40
        content_start_y = menu_section_rect.top + title_h_approx + 30

        if menu_section_rect.height < total_button_h + (content_start_y - menu_section_rect.top) + 20 :
             start_y = content_start_y
        else:
             remaining_h = menu_section_rect.height - (content_start_y - menu_section_rect.top)
             start_y = content_start_y + (remaining_h - total_button_h) // 2
        start_y = max(start_y, menu_section_rect.top + title_h_approx + 20)


        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
            editor_state.ui_elements_rects = {}
        for k in [key for key in editor_state.ui_elements_rects if key.startswith("menu_")]:
            del editor_state.ui_elements_rects[k]

        if button_font:
            rect_params = [
                (start_y, "menu_new_map", "New Map"),
                (start_y + button_h + spacing, "menu_load_map", "Load Map"),
                (start_y + 2 * (button_h + spacing), "menu_rename_map", "Rename Map"),
                (start_y + 3 * (button_h + spacing), "menu_delete_map", "Delete Map"),
                (start_y + 4 * (button_h + spacing), "menu_quit", "Quit Editor")
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

def _regenerate_minimap_surface(editor_state: EditorState, available_width: int, available_height: int):
    if not editor_state.map_content_surface:
        editor_state.minimap_surface = None
        return

    map_px_w = editor_state.get_map_pixel_width()
    map_px_h = editor_state.get_map_pixel_height()

    if map_px_w <= 0 or map_px_h <= 0:
        editor_state.minimap_surface = None
        return

    scale_w = available_width / map_px_w if map_px_w > 0 else 0
    scale_h = available_height / map_px_h if map_px_h > 0 else 0
    scale = min(scale_w, scale_h) if scale_w > 0 and scale_h > 0 else 0

    minimap_w = int(map_px_w * scale)
    minimap_h = int(map_px_h * scale)

    if minimap_w <=0 or minimap_h <=0:
        editor_state.minimap_surface = pygame.Surface((1,1))
        editor_state.minimap_surface.fill(ED_CONFIG.MINIMAP_BG_COLOR)
        return

    minimap_content_surf = pygame.Surface((map_px_w, map_px_h))
    minimap_content_surf.fill(editor_state.background_color)

    ts = editor_state.grid_size
    for obj in editor_state.placed_objects:
        asset_key = obj.get("asset_editor_key")
        world_x, world_y = obj.get("world_x"), obj.get("world_y")
        if asset_key is None or world_x is None or world_y is None: continue

        asset_palette_info = editor_state.assets_palette.get(asset_key)
        if not asset_palette_info: continue

        obj_color_override = obj.get("override_color")

        final_color_for_minimap_obj = getattr(ED_CONFIG.C, "LIGHT_GRAY", (200,200,200))
        is_colorable = asset_palette_info.get("colorable", False)

        if is_colorable and obj_color_override:
            final_color_for_minimap_obj = obj_color_override
        elif asset_palette_info.get("surface_params_dims_color"):
            final_color_for_minimap_obj = asset_palette_info["surface_params_dims_color"][2]
        elif asset_palette_info.get("base_color_tuple"):
            final_color_for_minimap_obj = asset_palette_info["base_color_tuple"]

        draw_w, draw_h = ts, ts
        draw_x, draw_y = world_x, world_y

        original_dims = asset_palette_info.get("original_size_pixels")
        if original_dims:
            draw_w, draw_h = original_dims[0], original_dims[1]

        if asset_palette_info.get("render_mode") == "half_tile":
            half_type = asset_palette_info.get("half_type")
            if half_type == "left": draw_w = ts // 2
            elif half_type == "right": draw_x = world_x + ts // 2; draw_w = ts // 2
            elif half_type == "top": draw_h = ts // 2
            elif half_type == "bottom": draw_y = world_y + ts // 2; draw_h = ts // 2

        obj_rect_on_map = pygame.Rect(draw_x, draw_y, max(1,draw_w), max(1,draw_h))


        if asset_palette_info.get("surface_params_dims_color") or \
           asset_palette_info.get("render_mode") == "half_tile" or \
           (is_colorable and obj_color_override):
            try:
                pygame.draw.rect(minimap_content_surf, final_color_for_minimap_obj, obj_rect_on_map)
            except TypeError:
                 pygame.draw.rect(minimap_content_surf, getattr(ED_CONFIG.C, "MAGENTA", (255,0,255)), obj_rect_on_map)
        elif asset_palette_info.get("image"):
            if not (is_colorable and obj_color_override) and \
               not asset_palette_info.get("surface_params_dims_color") and \
               not asset_palette_info.get("base_color_tuple"):
                pygame.draw.rect(minimap_content_surf, getattr(ED_CONFIG.C, "GRAY", (128,128,128)), obj_rect_on_map)


    if editor_state.show_grid:
        grid_color_minimap = (50,50,50)
        for x_coord in range(0, map_px_w, ts):
            pygame.draw.line(minimap_content_surf, grid_color_minimap, (x_coord,0), (x_coord, map_px_h))
        for y_coord in range(0, map_px_h, ts):
            pygame.draw.line(minimap_content_surf, grid_color_minimap, (0, y_coord), (map_px_w, y_coord))


    try:
        editor_state.minimap_surface = pygame.transform.smoothscale(minimap_content_surf, (minimap_w, minimap_h))
    except (pygame.error, ValueError) as e:
        print(f"ERROR DRAW: Minimap smoothscale failed: {e}. Using simple scale.")
        try:
            editor_state.minimap_surface = pygame.transform.scale(minimap_content_surf, (minimap_w, minimap_h))
        except (pygame.error, ValueError) as e_simple:
            print(f"ERROR DRAW: Minimap simple scale also failed: {e_simple}.")
            editor_state.minimap_surface = pygame.Surface((minimap_w if minimap_w > 0 else 1, minimap_h if minimap_h > 0 else 1))
            editor_state.minimap_surface.fill(ED_CONFIG.MINIMAP_BG_COLOR)

    editor_state.minimap_needs_regeneration = False


def _draw_minimap(surface: pygame.Surface, editor_state: EditorState, minimap_area_rect_on_surface: pygame.Rect, map_view_rect: pygame.Rect):
    """
    Draws the minimap within the provided minimap_area_rect_on_surface.
    Args:
        surface: The main editor surface.
        editor_state: The current editor state.
        minimap_area_rect_on_surface: The pygame.Rect defining the area where the minimap (including padding) should be drawn on the main surface.
        map_view_rect: The rect of the main map view area.
    """
    if not editor_state.map_content_surface: return

    # The minimap_area_rect_on_surface already defines the outer bounds for the minimap block.
    # We draw the BG and border directly into this.
    pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BG_COLOR, minimap_area_rect_on_surface)

    # Calculate the actual drawing area for the minimap content (inside padding)
    minimap_content_draw_width = minimap_area_rect_on_surface.width - (ED_CONFIG.MINIMAP_PADDING * 2)
    minimap_content_draw_height = minimap_area_rect_on_surface.height - (ED_CONFIG.MINIMAP_PADDING * 2)

    if editor_state.minimap_needs_regeneration:
        _regenerate_minimap_surface(editor_state, minimap_content_draw_width, minimap_content_draw_height)

    if editor_state.minimap_surface:
        # Center the scaled minimap_surface within the padded area
        minimap_blit_x = minimap_area_rect_on_surface.left + ED_CONFIG.MINIMAP_PADDING + \
                         (minimap_content_draw_width - editor_state.minimap_surface.get_width()) // 2
        minimap_blit_y = minimap_area_rect_on_surface.top + ED_CONFIG.MINIMAP_PADDING + \
                         (minimap_content_draw_height - editor_state.minimap_surface.get_height()) // 2

        actual_minimap_on_screen_rect = editor_state.minimap_surface.get_rect(topleft=(minimap_blit_x, minimap_blit_y))
        editor_state.minimap_rect_in_palette = actual_minimap_on_screen_rect # This is the rect of the scaled map image itself

        surface.blit(editor_state.minimap_surface, actual_minimap_on_screen_rect.topleft)
        pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BORDER_COLOR, actual_minimap_on_screen_rect, 1) # Border around the map image

        map_px_w = editor_state.get_map_pixel_width()
        map_px_h = editor_state.get_map_pixel_height()
        if map_px_w > 0 and map_px_h > 0 and \
           editor_state.minimap_surface.get_width() > 0 and editor_state.minimap_surface.get_height() > 0:
            
            scale_x = editor_state.minimap_surface.get_width() / map_px_w
            scale_y = editor_state.minimap_surface.get_height() / map_px_h
            cam_rect_mm_x = editor_state.camera_offset_x * scale_x
            cam_rect_mm_y = editor_state.camera_offset_y * scale_y
            cam_rect_mm_w = map_view_rect.width * scale_x
            cam_rect_mm_h = map_view_rect.height * scale_y

            cam_view_on_minimap = pygame.Rect(
                actual_minimap_on_screen_rect.left + cam_rect_mm_x,
                actual_minimap_on_screen_rect.top + cam_rect_mm_y,
                max(1, cam_rect_mm_w), max(1, cam_rect_mm_h)
            )
            if cam_view_on_minimap.width > 0 and cam_view_on_minimap.height > 0:
                s = pygame.Surface(cam_view_on_minimap.size, pygame.SRCALPHA)
                s.fill((*ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_COLOR, ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_ALPHA))
                surface.blit(s, cam_view_on_minimap.topleft)
                pygame.draw.rect(surface, ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_COLOR, cam_view_on_minimap, 1)
    
    # Draw border around the entire minimap block (including padding)
    pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BORDER_COLOR, minimap_area_rect_on_surface, 1)


def _draw_single_palette_item(scroll_surf: pygame.Surface,
                              editor_state: EditorState,
                              palette_section_rect: pygame.Rect,
                              asset_key: str, asset_data: Dict[str, Any],
                              item_x: int, item_y_on_scroll: int,
                              tip_font: Optional[pygame.font.Font],
                              mouse_pos: Tuple[int, int],
                              scrollable_assets_rect_on_screen: pygame.Rect
                              ) -> int:
    img = asset_data.get("image")
    tooltip_text = asset_data.get("tooltip", asset_key)
    if not img: return 0

    item_rect_on_screen = pygame.Rect(
        scrollable_assets_rect_on_screen.left + item_x,
        scrollable_assets_rect_on_screen.top + item_y_on_scroll - int(editor_state.asset_palette_scroll_y),
        img.get_width(), img.get_height()
    )
    editor_state.ui_elements_rects['asset_palette_items'][asset_key] = item_rect_on_screen

    is_hovered = item_rect_on_screen.collidepoint(mouse_pos) and scrollable_assets_rect_on_screen.collidepoint(mouse_pos)
    is_selected = editor_state.selected_asset_editor_key == asset_key

    if is_hovered:
        editor_state.hovered_tooltip_text = tooltip_text
        editor_state.hovered_tooltip_pos = mouse_pos
        hover_bg_r = pygame.Rect(item_x - 2, item_y_on_scroll - 2, img.get_width() + 4, img.get_height() + 4)
        pygame.draw.rect(scroll_surf, ED_CONFIG.ASSET_PALETTE_HOVER_BG_COLOR, hover_bg_r, border_radius=2)
    if is_selected:
        select_b_r = pygame.Rect(item_x - 3, item_y_on_scroll - 3, img.get_width() + 6, img.get_height() + 6)
        pygame.draw.rect(scroll_surf, ED_CONFIG.C.YELLOW, select_b_r, 2, border_radius=3) # type: ignore

    scroll_surf.blit(img, (item_x, item_y_on_scroll))
    current_item_total_height = img.get_height()

    if tip_font:
        name_s = tip_font.render(tooltip_text, True, ED_CONFIG.ASSET_PALETTE_TOOLTIP_COLOR)
        text_x = item_x + (img.get_width() - name_s.get_width()) // 2
        scroll_surf.blit(name_s, (max(item_x, text_x), item_y_on_scroll + img.get_height() + ED_CONFIG.ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET))
        current_item_total_height += name_s.get_height() + ED_CONFIG.ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET
    return current_item_total_height


def draw_asset_palette_ui(surface: pygame.Surface, editor_state: EditorState, palette_section_rect: pygame.Rect,
                          fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int],
                          map_view_rect: pygame.Rect):
    try:
        # --- Draw Palette Header (Options Dropdown) ---
        header_rect = pygame.Rect(
            palette_section_rect.left, palette_section_rect.top,
            palette_section_rect.width, ED_CONFIG.ASSET_PALETTE_HEADER_AREA_HEIGHT
        )
        pygame.draw.rect(surface, (40,40,45), header_rect) # Slightly different bg for header
        pygame.draw.line(surface, (60,60,65), header_rect.bottomleft, header_rect.bottomright, 2)


        options_button_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if options_button_font:
            options_button_text = "Palette Options ▼"
            options_btn_width = ED_CONFIG.ASSET_PALETTE_OPTIONS_DROPDOWN_WIDTH
            options_btn_height = ED_CONFIG.ASSET_PALETTE_OPTIONS_DROPDOWN_ITEM_HEIGHT

            editor_state.asset_palette_options_button_rect = pygame.Rect(
                header_rect.centerx - options_btn_width // 2,
                header_rect.centery - options_btn_height // 2,
                options_btn_width, options_btn_height
            )
            draw_button(surface, editor_state.asset_palette_options_button_rect, options_button_text,
                        options_button_font, mouse_pos,
                        button_color_normal=(60,60,70), button_color_hover=(80,80,90))

            if editor_state.asset_palette_options_dropdown_open and editor_state.asset_palette_options_button_rect:
                dropdown_items = ["View Assets", "Asset Properties Editor"] # Could be from ED_CONFIG
                dropdown_x = editor_state.asset_palette_options_button_rect.left
                dropdown_y_start = editor_state.asset_palette_options_button_rect.bottom + 2

                editor_state.asset_palette_options_rects.clear()

                for i, item_text in enumerate(dropdown_items):
                    item_rect = pygame.Rect(
                        dropdown_x,
                        dropdown_y_start + i * (options_btn_height + 2), # +2 for spacing
                        options_btn_width,
                        options_btn_height
                    )
                    editor_state.asset_palette_options_rects[item_text] = item_rect
                    draw_button(surface, item_rect, item_text, options_button_font, mouse_pos,
                                button_color_normal=(50,50,60), button_color_hover=(70,70,80),
                                border_width=1)

        # --- Draw Minimap (below header) ---
        minimap_y_start = header_rect.bottom
        minimap_area_in_palette_rect = pygame.Rect(
            palette_section_rect.left, minimap_y_start,
            palette_section_rect.width, ED_CONFIG.MINIMAP_AREA_HEIGHT
        )
        _draw_minimap(surface, editor_state, minimap_area_in_palette_rect, map_view_rect)

        # --- Draw Scrollable Assets List (below minimap) ---
        scrollable_assets_y_start = minimap_area_in_palette_rect.bottom
        bg_button_area_height = (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2)
        
        scrollable_assets_height = palette_section_rect.bottom - scrollable_assets_y_start - bg_button_area_height
        scrollable_assets_height = max(0, scrollable_assets_height) # Ensure non-negative


        scrollable_assets_rect_on_screen = pygame.Rect(
            palette_section_rect.left, scrollable_assets_y_start,
            palette_section_rect.width, scrollable_assets_height
        )
        pygame.draw.rect(surface, ED_CONFIG.ASSET_PALETTE_BG_COLOR, scrollable_assets_rect_on_screen)

        if editor_state.total_asset_palette_content_height <= 0:
            font_small = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
            if font_small:
                no_assets_text = "Assets Loading..."
                if not ED_CONFIG.EDITOR_PALETTE_ASSETS: no_assets_text = "No assets defined."
                elif not editor_state.assets_palette : no_assets_text = "Asset palette empty."
                msg_surf = font_small.render(no_assets_text, True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
                surface.blit(msg_surf, msg_surf.get_rect(center=scrollable_assets_rect_on_screen.center))

        if editor_state.total_asset_palette_content_height > 0 and scrollable_assets_height > 0:
            scroll_surf = pygame.Surface((palette_section_rect.width, editor_state.total_asset_palette_content_height), pygame.SRCALPHA)
            scroll_surf.fill((0,0,0,0))
            current_y_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
            cat_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
            tip_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")

            if not scrollable_assets_rect_on_screen.collidepoint(mouse_pos):
                 editor_state.hovered_tooltip_text = None

            if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
                editor_state.ui_elements_rects = {}
            editor_state.ui_elements_rects['asset_palette_items'] = {}
            
            categories_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER',
                                    ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"])
            for cat_name in categories_order:
                assets_in_category_tuples = [(k, d) for k, d in editor_state.assets_palette.items() if d.get("category", "unknown") == cat_name]
                if not assets_in_category_tuples: continue
                if cat_font:
                    cat_surf = cat_font.render(cat_name.title(), True, ED_CONFIG.ASSET_PALETTE_CATEGORY_TEXT_COLOR)
                    scroll_surf.blit(cat_surf, (ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, current_y_on_scroll_surf))
                    current_y_on_scroll_surf += cat_surf.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                
                row_start_y_for_current_items = current_y_on_scroll_surf
                if cat_name == "spawn": # Special layout for spawns
                    p1 = next(((k,d) for k,d in assets_in_category_tuples if k == "player1_spawn"), None)
                    p2 = next(((k,d) for k,d in assets_in_category_tuples if k == "player2_spawn"), None)
                    other = [i for i in assets_in_category_tuples if i[0] not in ["player1_spawn", "player2_spawn"]]
                    curr_x, max_h_in_row = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, 0
                    if p1:
                        h = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, p1[0], p1[1], curr_x, row_start_y_for_current_items, tip_font, mouse_pos, scrollable_assets_rect_on_screen)
                        max_h_in_row = max(max_h_in_row, h); curr_x += (p1[1]["image"].get_width() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING) if p1[1].get("image") else 0
                    if p2:
                        p2_img = p2[1].get("image")
                        if p2_img and curr_x + p2_img.get_width() > palette_section_rect.width - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING: # Wrap if no space
                            current_y_on_scroll_surf = row_start_y_for_current_items + max_h_in_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                            row_start_y_for_current_items = current_y_on_scroll_surf; curr_x = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING; max_h_in_row = 0
                        h = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, p2[0], p2[1], curr_x, row_start_y_for_current_items, tip_font, mouse_pos, scrollable_assets_rect_on_screen)
                        max_h_in_row = max(max_h_in_row, h)
                    if max_h_in_row > 0: current_y_on_scroll_surf = row_start_y_for_current_items + max_h_in_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                    assets_to_draw_this_category_loop = other
                else:
                    assets_to_draw_this_category_loop = assets_in_category_tuples
                
                for asset_key, asset_data in assets_to_draw_this_category_loop: # Draw remaining or all items in column
                    item_h = _draw_single_palette_item(scroll_surf, editor_state, palette_section_rect, asset_key, asset_data, ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, current_y_on_scroll_surf, tip_font, mouse_pos, scrollable_assets_rect_on_screen)
                    current_y_on_scroll_surf += item_h + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                if assets_in_category_tuples: current_y_on_scroll_surf += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding after category

            surface.blit(scroll_surf, scrollable_assets_rect_on_screen.topleft,
                        (0, int(editor_state.asset_palette_scroll_y), scrollable_assets_rect_on_screen.width, scrollable_assets_rect_on_screen.height))

        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'GRAY', (128,128,128)), scrollable_assets_rect_on_screen, 1)

        # --- Draw BG Color Button at the bottom of the palette ---
        btn_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if btn_font:
            btn_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD*0.8
            cp_btn_r = pygame.Rect(palette_section_rect.left+ED_CONFIG.ASSET_PALETTE_ITEM_PADDING,
                                   palette_section_rect.bottom-btn_h-ED_CONFIG.ASSET_PALETTE_ITEM_PADDING,
                                   palette_section_rect.width-ED_CONFIG.ASSET_PALETTE_ITEM_PADDING*2, int(btn_h))
            editor_state.ui_elements_rects["palette_bg_color_button"] = cp_btn_r
            bg_lum = sum(editor_state.background_color)/3 if editor_state.background_color else 0
            txt_col = getattr(ED_CONFIG.C, 'BLACK', (0,0,0)) if bg_lum > 192 else getattr(ED_CONFIG.C, 'WHITE', (255,255,255))
            current_bg_button_color = editor_state.background_color if editor_state.background_color else ED_CONFIG.BUTTON_COLOR_NORMAL
            hover_bg_button_color = pygame.Color(current_bg_button_color).lerp(getattr(ED_CONFIG.C, 'WHITE', (255,255,255)),0.3)

            draw_button(surface,cp_btn_r,"BG Color",btn_font,mouse_pos,
                        text_color=txt_col,button_color_normal=current_bg_button_color,
                        button_color_hover=hover_bg_button_color,
                        border_color=getattr(ED_CONFIG.C, 'BLACK', (0,0,0)))

        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'DARK_GRAY', (50,50,50)), palette_section_rect, 2) # Border for whole palette
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
        ts = editor_state.grid_size
        for obj in editor_state.placed_objects:
            asset_key = obj.get("asset_editor_key")
            world_x, world_y = obj.get("world_x"), obj.get("world_y")
            if asset_key is None or world_x is None or world_y is None: continue
            asset_palette_info = editor_state.assets_palette.get(asset_key)
            if not asset_palette_info:
                pygame.draw.rect(editor_state.map_content_surface, getattr(ED_CONFIG.C, 'RED', (255,0,0)), (world_x,world_y,ts,ts),1)
                continue

            image_to_draw_from_palette = asset_palette_info.get("image")
            override_color = obj.get("override_color")
            final_image_for_map = None

            is_colorable = asset_palette_info.get("colorable", False)
            current_color_tuple = override_color if is_colorable and override_color else None

            if asset_palette_info.get("render_mode") == "half_tile":
                color_to_use = current_color_tuple if current_color_tuple else asset_palette_info.get("base_color_tuple")
                if color_to_use:
                    temp_half_surf = pygame.Surface((ts, ts), pygame.SRCALPHA); temp_half_surf.fill((0,0,0,0))
                    half_type = asset_palette_info.get("half_type", "left")
                    rect_to_draw = pygame.Rect(0,0,0,0)
                    if half_type == "left": rect_to_draw = pygame.Rect(0, 0, ts // 2, ts)
                    elif half_type == "right": rect_to_draw = pygame.Rect(ts // 2, 0, ts // 2, ts)
                    elif half_type == "top": rect_to_draw = pygame.Rect(0, 0, ts, ts // 2)
                    elif half_type == "bottom": rect_to_draw = pygame.Rect(0, ts // 2, ts, ts // 2)
                    pygame.draw.rect(temp_half_surf, color_to_use, rect_to_draw)
                    final_image_for_map = temp_half_surf
            elif asset_palette_info.get("surface_params_dims_color"):
                w, h, default_color_from_def = asset_palette_info["surface_params_dims_color"]
                color_to_use = current_color_tuple if current_color_tuple else default_color_from_def
                temp_param_surf = pygame.Surface((w,h)); temp_param_surf.fill(color_to_use) # type: ignore
                final_image_for_map = temp_param_surf
            elif image_to_draw_from_palette :
                if current_color_tuple:
                    tinted_surf = image_to_draw_from_palette.copy()
                    color_surface = pygame.Surface(tinted_surf.get_size(), pygame.SRCALPHA)
                    color_surface.fill((*current_color_tuple, 128))
                    tinted_surf.blit(color_surface, (0,0), special_flags=pygame.BLEND_RGBA_MULT) # type: ignore
                    final_image_for_map = tinted_surf
                else:
                    final_image_for_map = image_to_draw_from_palette

            if final_image_for_map:
                editor_state.map_content_surface.blit(final_image_for_map, (world_x, world_y))
            else:
                 pygame.draw.rect(editor_state.map_content_surface, getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)), (world_x,world_y,ts,ts),1)

        if editor_state.show_grid:
            draw_grid_on_map_surface(editor_state.map_content_surface, editor_state)

        surface.blit(editor_state.map_content_surface, map_view_rect.topleft, (int(editor_state.camera_offset_x), int(editor_state.camera_offset_y), map_view_rect.width, map_view_rect.height))
        pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2)

        # Draw the selected asset at cursor (already processed for transparency and hue in EditorState)
        if editor_state.selected_asset_image_for_cursor:
            img_at_cursor = editor_state.selected_asset_image_for_cursor
            pos_on_screen: Tuple[int, int]

            if map_view_rect.collidepoint(mouse_pos):
                # Snap to grid if inside map view
                world_mx = mouse_pos[0] - map_view_rect.left + editor_state.camera_offset_x
                world_my = mouse_pos[1] - map_view_rect.top + editor_state.camera_offset_y
                grid_wx = (world_mx // editor_state.grid_size) * editor_state.grid_size
                grid_wy = (world_my // editor_state.grid_size) * editor_state.grid_size
                
                pos_on_screen = (
                    grid_wx - int(editor_state.camera_offset_x) + map_view_rect.left,
                    grid_wy - int(editor_state.camera_offset_y) + map_view_rect.top
                )
            else:
                # If outside map view, just follow mouse (top-left of image at mouse)
                pos_on_screen = (mouse_pos[0], mouse_pos[1])

            # Clip drawing to map_view_rect if the calculated pos_on_screen is within it or mouse is over it
            original_clip = surface.get_clip()
            # A more robust check: if the intended placement (pos_on_screen) of the asset overlaps with map_view_rect
            asset_rect_at_cursor = img_at_cursor.get_rect(topleft=pos_on_screen)
            if map_view_rect.colliderect(asset_rect_at_cursor) and map_view_rect.collidepoint(mouse_pos):
                 surface.set_clip(map_view_rect)
            
            surface.blit(img_at_cursor, pos_on_screen)
            surface.set_clip(original_clip)

        _draw_map_view_info_text(surface, editor_state, map_view_rect, fonts, mouse_pos)
    except Exception as e:
        print(f"ERROR DRAW: draw_map_view_ui: {e}")
        traceback.print_exc()

def _draw_map_view_info_text(surface: pygame.Surface, editor_state: EditorState, map_view_rect: pygame.Rect,
                             fonts: Dict[str, Optional[pygame.font.Font]], general_mouse_pos: Tuple[int, int]):
    info_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if not info_font: return

    coords_text_str = f"Cam:({int(editor_state.camera_offset_x)},{int(editor_state.camera_offset_y)})"
    if map_view_rect.collidepoint(general_mouse_pos):
        world_mx = general_mouse_pos[0]-map_view_rect.left+editor_state.camera_offset_x
        world_my = general_mouse_pos[1]-map_view_rect.top+editor_state.camera_offset_y
        tx,ty = world_mx//editor_state.grid_size, world_my//editor_state.grid_size
        coords_text_str += f" MouseW:({int(world_mx)},{int(world_my)}) Tile:({tx},{ty})"

    coords_surf = info_font.render(coords_text_str,True,getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
    coords_x_pos = map_view_rect.left + 5

    coords_y_pos = map_view_rect.top - coords_surf.get_height() - 4
    if coords_y_pos < 5:
        coords_y_pos = map_view_rect.bottom + 4
        if coords_y_pos + coords_surf.get_height() > surface.get_height() - 5:
            coords_y_pos = surface.get_height() - 5 - coords_surf.get_height()

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