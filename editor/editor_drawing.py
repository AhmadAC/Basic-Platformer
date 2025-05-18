# editor_drawing.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.20 (Multi-column asset palette, QColorDialog integration)
Contains functions for drawing the different sections and elements
of the Platformer Level Editor UI using Pygame.
"""
import pygame
from typing import Dict, Tuple, Any, Optional, List # Added List
import traceback

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import draw_button # Assuming draw_button is in editor_ui

# Attempt to import PySide6 for QColorDialog if you implement that feature later
# For now, this file doesn't directly use it, but editor_ui.py would.

# Logger setup (assuming logger is initialized in editor.py and accessible)
import logging
logger = logging.getLogger(__name__)


def draw_menu_ui(surface: pygame.Surface, editor_state: EditorState, menu_section_rect: pygame.Rect,
                 fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int]):
    try:
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), menu_section_rect) # Menu background
        title_font = fonts.get("large") or ED_CONFIG.FONT_CONFIG.get("large")
        button_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")

        if title_font:
            title_surf = title_font.render("Level Editor", True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
            title_rect = title_surf.get_rect(centerx=menu_section_rect.centerx, top=menu_section_rect.top + 20)
            surface.blit(title_surf, title_rect)

        # Button layout
        button_w = ED_CONFIG.BUTTON_WIDTH_STANDARD
        button_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD
        spacing = 12 # Vertical spacing between buttons
        num_buttons = 5 # New Map, Load, Rename, Delete, Quit
        total_button_h = (num_buttons * button_h) + ((num_buttons - 1) * spacing)
        
        title_h_approx = title_font.get_height() if title_font else 40
        content_start_y = menu_section_rect.top + title_h_approx + 30 # Y where button area starts

        # Center buttons vertically if space allows, otherwise start near top
        if menu_section_rect.height < total_button_h + (content_start_y - menu_section_rect.top) + 20 :
             start_y_buttons = content_start_y # Not enough space, stack from top
        else:
             remaining_h_for_buttons = menu_section_rect.height - (content_start_y - menu_section_rect.top)
             start_y_buttons = content_start_y + (remaining_h_for_buttons - total_button_h) // 2 # Center
        start_y_buttons = max(start_y_buttons, menu_section_rect.top + title_h_approx + 20) # Ensure below title

        # Ensure ui_elements_rects is initialized and clear old menu button rects
        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
            editor_state.ui_elements_rects = {}
        for k_menu_btn in [key for key in editor_state.ui_elements_rects if key.startswith("menu_")]:
            del editor_state.ui_elements_rects[k_menu_btn]

        if button_font:
            button_definitions = [
                (start_y_buttons, "menu_new_map", "New Map"),
                (start_y_buttons + button_h + spacing, "menu_load_map", "Load Map"),
                (start_y_buttons + 2 * (button_h + spacing), "menu_rename_map", "Rename Map"),
                (start_y_buttons + 3 * (button_h + spacing), "menu_delete_map", "Delete Map"),
                (start_y_buttons + 4 * (button_h + spacing), "menu_quit", "Quit Editor")
            ]
            for top_y_btn, key_btn, text_btn in button_definitions:
                btn_rect_menu = pygame.Rect(0,0,button_w,button_h)
                btn_rect_menu.centerx = menu_section_rect.centerx
                btn_rect_menu.top = top_y_btn
                editor_state.ui_elements_rects[key_btn] = btn_rect_menu # Store rect for click detection
                draw_button(surface, btn_rect_menu, text_btn, button_font, mouse_pos)
        else:
            if logger: logger.warning("Menu button font missing. Buttons not drawn.")
    except Exception as e:
        if logger: logger.error(f"Exception in draw_menu_ui: {e}", exc_info=True)
        # Optionally draw an error message on the menu itself

# --- (Minimap drawing functions _regenerate_minimap_surface and _draw_minimap remain UNCHANGED from your last version) ---
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
            except TypeError: # Fallback if color is somehow invalid
                 pygame.draw.rect(minimap_content_surf, getattr(ED_CONFIG.C, "MAGENTA", (255,0,255)), obj_rect_on_map)
        elif asset_palette_info.get("image"): # For image-based assets (like GIFs)
            # Draw a generic placeholder color for image assets on minimap if no override/specific color defined
            if not (is_colorable and obj_color_override) and \
               not asset_palette_info.get("surface_params_dims_color") and \
               not asset_palette_info.get("base_color_tuple"):
                pygame.draw.rect(minimap_content_surf, getattr(ED_CONFIG.C, "GRAY", (128,128,128)), obj_rect_on_map)


    if editor_state.show_grid:
        grid_color_minimap = (50,50,50) # Darker grid for minimap
        for x_coord in range(0, map_px_w, ts):
            pygame.draw.line(minimap_content_surf, grid_color_minimap, (x_coord,0), (x_coord, map_px_h))
        for y_coord in range(0, map_px_h, ts):
            pygame.draw.line(minimap_content_surf, grid_color_minimap, (0, y_coord), (map_px_w, y_coord))


    try:
        editor_state.minimap_surface = pygame.transform.smoothscale(minimap_content_surf, (minimap_w, minimap_h))
    except (pygame.error, ValueError) as e_smooth:
        if logger: logger.warning(f"Minimap smoothscale failed: {e_smooth}. Using simple scale.")
        try:
            editor_state.minimap_surface = pygame.transform.scale(minimap_content_surf, (minimap_w, minimap_h))
        except (pygame.error, ValueError) as e_simple:
            if logger: logger.error(f"Minimap simple scale also failed: {e_simple}.")
            # Create a minimal fallback surface
            editor_state.minimap_surface = pygame.Surface((minimap_w if minimap_w > 0 else 1, minimap_h if minimap_h > 0 else 1))
            editor_state.minimap_surface.fill(ED_CONFIG.MINIMAP_BG_COLOR)

    editor_state.minimap_needs_regeneration = False


def _draw_minimap(surface: pygame.Surface, editor_state: EditorState, minimap_area_rect_on_surface: pygame.Rect, map_view_rect: pygame.Rect):
    if not editor_state.map_content_surface: return

    pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BG_COLOR, minimap_area_rect_on_surface) # BG for the whole minimap block

    minimap_content_draw_width = minimap_area_rect_on_surface.width - (ED_CONFIG.MINIMAP_PADDING * 2)
    minimap_content_draw_height = minimap_area_rect_on_surface.height - (ED_CONFIG.MINIMAP_PADDING * 2)

    if editor_state.minimap_needs_regeneration:
        _regenerate_minimap_surface(editor_state, minimap_content_draw_width, minimap_content_draw_height)

    if editor_state.minimap_surface:
        minimap_blit_x = minimap_area_rect_on_surface.left + ED_CONFIG.MINIMAP_PADDING + \
                         (minimap_content_draw_width - editor_state.minimap_surface.get_width()) // 2
        minimap_blit_y = minimap_area_rect_on_surface.top + ED_CONFIG.MINIMAP_PADDING + \
                         (minimap_content_draw_height - editor_state.minimap_surface.get_height()) // 2

        actual_minimap_on_screen_rect = editor_state.minimap_surface.get_rect(topleft=(minimap_blit_x, minimap_blit_y))
        editor_state.minimap_rect_in_palette = actual_minimap_on_screen_rect

        surface.blit(editor_state.minimap_surface, actual_minimap_on_screen_rect.topleft)
        pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BORDER_COLOR, actual_minimap_on_screen_rect, 1)

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
                s_cam_view = pygame.Surface(cam_view_on_minimap.size, pygame.SRCALPHA)
                s_cam_view.fill((*ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_COLOR, ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_ALPHA))
                surface.blit(s_cam_view, cam_view_on_minimap.topleft)
                pygame.draw.rect(surface, ED_CONFIG.MINIMAP_CAMERA_VIEW_RECT_COLOR, cam_view_on_minimap, 1)
    
    pygame.draw.rect(surface, ED_CONFIG.MINIMAP_BORDER_COLOR, minimap_area_rect_on_surface, 1) # Border for whole block

# --- MODIFIED: Asset Palette Drawing for Multi-Column Layout ---
def _draw_palette_item_grid(scroll_surf: pygame.Surface,
                            editor_state: EditorState,
                            palette_section_rect: pygame.Rect, # Main palette section on screen
                            asset_key: str, asset_data: Dict[str, Any],
                            item_draw_x_on_scroll_surf: int, # X position on the scrollable surface
                            item_draw_y_on_scroll_surf: int, # Y position on the scrollable surface
                            tip_font: Optional[pygame.font.Font],
                            mouse_pos_screen: Tuple[int, int], # Mouse pos relative to main screen
                            scrollable_assets_area_on_screen: pygame.Rect # The visible part of the scrollable area
                           ) -> Tuple[int, int]: # Returns (width_taken_by_item, height_taken_by_item)
    """
    Draws a single asset palette item at a given x, y on the scrollable surface.
    Handles hover, selection visuals, and tooltip updates.
    Returns the total width and height this item occupies (image + text + padding).
    """
    img = asset_data.get("image")
    tooltip_text = asset_data.get("tooltip", asset_key)
    if not img: return (0, 0) # No image, takes no space

    # Calculate the item's absolute rect on the main screen for hover/click detection
    item_rect_on_screen = pygame.Rect(
        scrollable_assets_area_on_screen.left + item_draw_x_on_scroll_surf, # X relative to scrollable area start
        scrollable_assets_area_on_screen.top + item_draw_y_on_scroll_surf - int(editor_state.asset_palette_scroll_y), # Y adjusted by scroll
        img.get_width(), img.get_height()
    )
    editor_state.ui_elements_rects.setdefault('asset_palette_items', {})[asset_key] = item_rect_on_screen

    # Check for hover and selection
    is_hovered = item_rect_on_screen.collidepoint(mouse_pos_screen) and \
                 scrollable_assets_area_on_screen.collidepoint(mouse_pos_screen) # Must also be over visible area
    is_selected = editor_state.selected_asset_editor_key == asset_key

    item_total_width = img.get_width()
    item_total_height = img.get_height()

    # Draw hover background (slightly larger than image)
    if is_hovered:
        editor_state.hovered_tooltip_text = tooltip_text # Set tooltip for main draw loop
        editor_state.hovered_tooltip_pos = mouse_pos_screen
        hover_bg_rect = pygame.Rect(item_draw_x_on_scroll_surf - 2, item_draw_y_on_scroll_surf - 2,
                                    img.get_width() + 4, img.get_height() + 4)
        pygame.draw.rect(scroll_surf, ED_CONFIG.ASSET_PALETTE_HOVER_BG_COLOR, hover_bg_rect, border_radius=2)
    
    # Draw selection border (slightly larger again)
    if is_selected:
        select_border_rect = pygame.Rect(item_draw_x_on_scroll_surf - 3, item_draw_y_on_scroll_surf - 3,
                                         img.get_width() + 6, img.get_height() + 6)
        pygame.draw.rect(scroll_surf, getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)), select_border_rect, 2, border_radius=3)

    # Draw the asset image itself onto the scrollable surface
    scroll_surf.blit(img, (item_draw_x_on_scroll_surf, item_draw_y_on_scroll_surf))

    # Draw tooltip text below the image
    if tip_font:
        name_surface = tip_font.render(tooltip_text, True, ED_CONFIG.ASSET_PALETTE_TOOLTIP_COLOR)
        # Center text below the image, or align left if text wider than image
        text_x_on_scroll_surf = item_draw_x_on_scroll_surf + (img.get_width() - name_surface.get_width()) // 2
        text_x_on_scroll_surf = max(item_draw_x_on_scroll_surf, text_x_on_scroll_surf) # Don't let it go left of image start
        
        text_y_on_scroll_surf = item_draw_y_on_scroll_surf + img.get_height() + ED_CONFIG.ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET
        scroll_surf.blit(name_surface, (text_x_on_scroll_surf, text_y_on_scroll_surf))
        
        item_total_height += name_surface.get_height() + ED_CONFIG.ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET
        # Item total width is primarily image width, text can overflow but doesn't push next item unless very wide
        item_total_width = max(item_total_width, name_surface.get_width()) 
    
    return (item_total_width, item_total_height)


def draw_asset_palette_ui(surface: pygame.Surface, editor_state: EditorState, palette_section_rect: pygame.Rect,
                          fonts: Dict[str, Optional[pygame.font.Font]], mouse_pos: Tuple[int, int],
                          map_view_rect: pygame.Rect): # map_view_rect needed for minimap camera view
    try:
        # --- Draw Palette Header (Options Dropdown) ---
        # (This part remains the same as your existing code)
        header_rect = pygame.Rect(
            palette_section_rect.left, palette_section_rect.top,
            palette_section_rect.width, ED_CONFIG.ASSET_PALETTE_HEADER_AREA_HEIGHT
        )
        pygame.draw.rect(surface, (40,40,45), header_rect) # Header background
        pygame.draw.line(surface, (60,60,65), header_rect.bottomleft, header_rect.bottomright, 2) # Separator line

        options_button_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if options_button_font:
            options_button_text = "Palette Options ▼" # Or "Palette Options ▲" if open
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
                dropdown_items = ["View Assets", "Asset Properties Editor"] # Example items
                dropdown_x = editor_state.asset_palette_options_button_rect.left
                dropdown_y_start = editor_state.asset_palette_options_button_rect.bottom + 2

                editor_state.asset_palette_options_rects.clear() # Clear old dropdown rects

                for i, item_text_dd in enumerate(dropdown_items):
                    item_rect_dd = pygame.Rect(
                        dropdown_x,
                        dropdown_y_start + i * (options_btn_height + 2), # +2 for spacing
                        options_btn_width,
                        options_btn_height
                    )
                    editor_state.asset_palette_options_rects[item_text_dd] = item_rect_dd
                    draw_button(surface, item_rect_dd, item_text_dd, options_button_font, mouse_pos,
                                button_color_normal=(50,50,60), button_color_hover=(70,70,80),
                                border_width=1)
        # --- End Palette Header ---

        # --- Draw Minimap (below header) ---
        minimap_y_start_on_screen = header_rect.bottom
        minimap_area_in_palette_rect = pygame.Rect(
            palette_section_rect.left, minimap_y_start_on_screen,
            palette_section_rect.width, ED_CONFIG.MINIMAP_AREA_HEIGHT
        )
        _draw_minimap(surface, editor_state, minimap_area_in_palette_rect, map_view_rect)
        # --- End Minimap ---

        # --- Draw Scrollable Assets List (below minimap) ---
        scrollable_assets_y_start_on_screen = minimap_area_in_palette_rect.bottom
        # Height available for the BG Color button at the very bottom
        bg_color_button_area_height = (ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2)
        
        # Calculate height available for the scrollable list itself
        scrollable_assets_list_visible_height = palette_section_rect.bottom - scrollable_assets_y_start_on_screen - bg_color_button_area_height
        scrollable_assets_list_visible_height = max(0, scrollable_assets_list_visible_height) # Ensure non-negative

        # This is the rectangle on the main screen where the *visible part* of the scrollable list will be.
        scrollable_assets_area_on_screen = pygame.Rect(
            palette_section_rect.left, scrollable_assets_y_start_on_screen,
            palette_section_rect.width, scrollable_assets_list_visible_height
        )
        pygame.draw.rect(surface, ED_CONFIG.ASSET_PALETTE_BG_COLOR, scrollable_assets_area_on_screen) # BG for scrollable area

        # Handle case where no assets are loaded or defined
        if editor_state.total_asset_palette_content_height <= 0: # total_asset_palette_content_height is calculated in editor_assets
            font_small_no_assets = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
            if font_small_no_assets:
                no_assets_text_str = "Assets Loading..."
                if not ED_CONFIG.EDITOR_PALETTE_ASSETS: no_assets_text_str = "No assets defined in config."
                elif not editor_state.assets_palette : no_assets_text_str = "Asset palette is empty."
                msg_surf_no_assets = font_small_no_assets.render(no_assets_text_str, True, getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
                surface.blit(msg_surf_no_assets, msg_surf_no_assets.get_rect(center=scrollable_assets_area_on_screen.center))

        # If there is content and visible space, draw the scrollable items
        if editor_state.total_asset_palette_content_height > 0 and scrollable_assets_list_visible_height > 0:
            # Create a larger surface to draw all asset items onto (this surface will be scrolled)
            # Width is palette width, height is total calculated content height
            scroll_surface_for_assets = pygame.Surface((palette_section_rect.width, editor_state.total_asset_palette_content_height), pygame.SRCALPHA)
            scroll_surface_for_assets.fill((0,0,0,0)) # Transparent background for the scroll surface

            current_y_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Start Y for first category title
            
            category_title_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
            item_tooltip_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")

            # Ensure mouse hover for tooltip is cleared if mouse isn't over the asset list area
            if not scrollable_assets_area_on_screen.collidepoint(mouse_pos):
                 editor_state.hovered_tooltip_text = None

            # Initialize or clear asset item rects for click detection
            if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
                editor_state.ui_elements_rects = {}
            editor_state.ui_elements_rects['asset_palette_items'] = {} # Will store {asset_key: screen_rect}
            
            # --- MODIFIED: Multi-column layout logic ---
            available_width_for_items = palette_section_rect.width - (ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2) # Width inside padding
            
            categories_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER',
                                    ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"])

            for category_name_iter in categories_order:
                assets_in_this_category = [(k, d) for k, d in editor_state.assets_palette.items() if d.get("category", "unknown") == category_name_iter]
                if not assets_in_this_category: continue # Skip empty categories

                # Draw category title
                if category_title_font:
                    category_title_surf = category_title_font.render(category_name_iter.title(), True, ED_CONFIG.ASSET_PALETTE_CATEGORY_TEXT_COLOR)
                    scroll_surface_for_assets.blit(category_title_surf, (ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, current_y_on_scroll_surf))
                    current_y_on_scroll_surf += category_title_surf.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                
                # --- Grid layout for items within this category ---
                current_x_in_row_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                max_height_in_current_row = 0

                # Special handling for "spawn" category to place P1 and P2 side-by-side if possible
                if category_name_iter == "spawn":
                    p1_spawn_data = next(((k,d) for k,d in assets_in_this_category if k == "player1_spawn"), None)
                    p2_spawn_data = next(((k,d) for k,d in assets_in_this_category if k == "player2_spawn"), None)
                    other_spawns = [item_tuple for item_tuple in assets_in_this_category if item_tuple[0] not in ["player1_spawn", "player2_spawn"]]
                    
                    temp_spawn_items_ordered = []
                    if p1_spawn_data: temp_spawn_items_ordered.append(p1_spawn_data)
                    if p2_spawn_data: temp_spawn_items_ordered.append(p2_spawn_data)
                    temp_spawn_items_ordered.extend(other_spawns) # Add any other spawn types after P1/P2
                    assets_to_draw_in_grid = temp_spawn_items_ordered
                else:
                    assets_to_draw_in_grid = assets_in_this_category

                for asset_key_iter, asset_data_iter in assets_to_draw_in_grid:
                    item_img = asset_data_iter.get("image")
                    if not item_img: continue

                    # Estimate width taken by item (image + padding for next item)
                    # Actual width used for drawing is item_img.get_width()
                    # For layout, consider a potential max width or a fixed cell width if desired.
                    # Here, we use actual image width + padding.
                    estimated_item_width_with_padding = item_img.get_width() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                    
                    # If current item doesn't fit in the current row, move to next row
                    if current_x_in_row_on_scroll_surf + estimated_item_width_with_padding > available_width_for_items + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING and \
                       current_x_in_row_on_scroll_surf > ED_CONFIG.ASSET_PALETTE_ITEM_PADDING : # Check if not first item in row
                        current_x_in_row_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Reset X to start of new row
                        current_y_on_scroll_surf += max_height_in_current_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Move Y down by height of previous row
                        max_height_in_current_row = 0 # Reset max height for new row
                    
                    # Draw the item and get its dimensions (image + text)
                    item_width_drawn, item_height_drawn = _draw_palette_item_grid(
                        scroll_surface_for_assets, editor_state, palette_section_rect,
                        asset_key_iter, asset_data_iter,
                        current_x_in_row_on_scroll_surf, current_y_on_scroll_surf,
                        item_tooltip_font, mouse_pos, scrollable_assets_area_on_screen
                    )
                    
                    if item_width_drawn > 0: # If item was actually drawn
                        current_x_in_row_on_scroll_surf += item_width_drawn + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                        max_height_in_current_row = max(max_height_in_current_row, item_height_drawn)
                
                # After processing all items in a category, move Y down by the height of the last row
                if max_height_in_current_row > 0:
                    current_y_on_scroll_surf += max_height_in_current_row + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                
                current_y_on_scroll_surf += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Extra padding after the entire category block
            # --- End Multi-column layout logic ---

            # Blit the visible part of the scroll_surface_for_assets onto the main screen
            surface.blit(scroll_surface_for_assets, scrollable_assets_area_on_screen.topleft,
                        (0, int(editor_state.asset_palette_scroll_y), # Source X,Y (scrolled Y)
                         scrollable_assets_area_on_screen.width, scrollable_assets_area_on_screen.height)) # Source W,H

        # Draw border around the scrollable asset list area
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'GRAY', (128,128,128)), scrollable_assets_area_on_screen, 1)

        # --- Draw BG Color Button at the bottom of the palette ---
        # (This part remains the same as your existing code)
        bg_color_btn_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if bg_color_btn_font:
            bg_color_btn_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD*0.8
            bg_color_btn_rect = pygame.Rect(
                palette_section_rect.left + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING,
                palette_section_rect.bottom - bg_color_btn_h - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, # Position at bottom
                palette_section_rect.width - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING*2, # Full width minus padding
                int(bg_color_btn_h)
            )
            editor_state.ui_elements_rects["palette_bg_color_button"] = bg_color_btn_rect
            
            # Determine text color based on background color brightness for readability
            current_bg_color = editor_state.background_color if editor_state.background_color else ED_CONFIG.BUTTON_COLOR_NORMAL
            bg_luminance = sum(current_bg_color)/3 if current_bg_color else 0
            text_color_for_bg_btn = getattr(ED_CONFIG.C, 'BLACK', (0,0,0)) if bg_luminance > 192 else getattr(ED_CONFIG.C, 'WHITE', (255,255,255))
            
            # Button hover color (slightly lighter version of current BG color)
            try:
                hover_bg_button_color = pygame.Color(current_bg_color).lerp(getattr(ED_CONFIG.C, 'WHITE', (255,255,255)),0.3)
            except: # Fallback if lerp fails (e.g., color is not a valid Pygame Color object initially)
                hover_bg_button_color = (min(255,current_bg_color[0]+30), min(255,current_bg_color[1]+30), min(255,current_bg_color[2]+30))


            draw_button(surface, bg_color_btn_rect, "BG Color", bg_color_btn_font, mouse_pos,
                        text_color=text_color_for_bg_btn, button_color_normal=current_bg_color,
                        button_color_hover=hover_bg_button_color,
                        border_color=getattr(ED_CONFIG.C, 'BLACK', (0,0,0)))
        # --- End BG Color Button ---

        # Draw border for the whole asset palette section
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'DARK_GRAY', (50,50,50)), palette_section_rect, 2) 
    except Exception as e:
        if logger: logger.error(f"Exception in draw_asset_palette_ui: {e}", exc_info=True)
        # Optionally draw an error message on the palette itself

# --- (draw_map_view_ui, _draw_map_view_info_text, draw_grid_on_map_surface remain UNCHANGED from your last version) ---
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
                if current_color_tuple: # Apply tint if color override exists
                    tinted_surf = image_to_draw_from_palette.copy()
                    color_surface = pygame.Surface(tinted_surf.get_size(), pygame.SRCALPHA)
                    color_surface.fill((*current_color_tuple, 128)) # RGBA with alpha for tint strength
                    tinted_surf.blit(color_surface, (0,0), special_flags=pygame.BLEND_RGBA_MULT) # type: ignore
                    final_image_for_map = tinted_surf
                else: # Use original image from palette
                    final_image_for_map = image_to_draw_from_palette

            if final_image_for_map:
                editor_state.map_content_surface.blit(final_image_for_map, (world_x, world_y))
            else: # Fallback if no image could be determined
                 pygame.draw.rect(editor_state.map_content_surface, getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)), (world_x,world_y,ts,ts),1)

        if editor_state.show_grid:
            draw_grid_on_map_surface(editor_state.map_content_surface, editor_state)

        # Blit the visible portion of the map_content_surface to the screen
        surface.blit(editor_state.map_content_surface, map_view_rect.topleft, 
                     (int(editor_state.camera_offset_x), int(editor_state.camera_offset_y), 
                      map_view_rect.width, map_view_rect.height))
        pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2) # Border for map view

        # Draw the selected asset at cursor (semi-transparent with hue)
        if editor_state.selected_asset_image_for_cursor:
            img_at_cursor = editor_state.selected_asset_image_for_cursor
            pos_on_screen: Tuple[int, int]

            if map_view_rect.collidepoint(mouse_pos): # If mouse is over map view
                # Snap to grid
                world_mouse_x = mouse_pos[0] - map_view_rect.left + editor_state.camera_offset_x
                world_mouse_y = mouse_pos[1] - map_view_rect.top + editor_state.camera_offset_y
                grid_world_x = (world_mouse_x // editor_state.grid_size) * editor_state.grid_size
                grid_world_y = (world_mouse_y // editor_state.grid_size) * editor_state.grid_size
                
                # Convert snapped world coordinates back to screen coordinates for drawing
                pos_on_screen = (
                    grid_world_x - int(editor_state.camera_offset_x) + map_view_rect.left,
                    grid_world_y - int(editor_state.camera_offset_y) + map_view_rect.top
                )
            else: # If mouse is outside map view, asset follows mouse directly
                pos_on_screen = (mouse_pos[0], mouse_pos[1]) # Top-left of image at mouse

            # Clip drawing of cursor asset to the map_view_rect if it's intended for placement there
            original_clip_cursor = surface.get_clip()
            asset_rect_at_cursor_preview = img_at_cursor.get_rect(topleft=pos_on_screen)
            if map_view_rect.colliderect(asset_rect_at_cursor_preview) and map_view_rect.collidepoint(mouse_pos):
                 surface.set_clip(map_view_rect) # Clip to map view boundaries
            
            surface.blit(img_at_cursor, pos_on_screen)
            surface.set_clip(original_clip_cursor) # Restore original clip

        _draw_map_view_info_text(surface, editor_state, map_view_rect, fonts, mouse_pos) # Draw info like coords
    except Exception as e:
        if logger: logger.error(f"Exception in draw_map_view_ui: {e}", exc_info=True)

def _draw_map_view_info_text(surface: pygame.Surface, editor_state: EditorState, map_view_rect: pygame.Rect,
                             fonts: Dict[str, Optional[pygame.font.Font]], general_mouse_pos: Tuple[int, int]):
    info_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if not info_font: return

    coords_text_str = f"Cam:({int(editor_state.camera_offset_x)},{int(editor_state.camera_offset_y)})"
    if map_view_rect.collidepoint(general_mouse_pos): # If mouse is over map view
        world_mouse_x_info = general_mouse_pos[0]-map_view_rect.left+editor_state.camera_offset_x
        world_mouse_y_info = general_mouse_pos[1]-map_view_rect.top+editor_state.camera_offset_y
        tile_x_info, tile_y_info = world_mouse_x_info//editor_state.grid_size, world_mouse_y_info//editor_state.grid_size
        coords_text_str += f" MouseW:({int(world_mouse_x_info)},{int(world_mouse_y_info)}) Tile:({tile_x_info},{tile_y_info})"

    coords_surf_info = info_font.render(coords_text_str,True,getattr(ED_CONFIG.C, 'WHITE', (255,255,255)))
    coords_x_pos_info = map_view_rect.left + 5

    # Try to position above map view, fallback to below or bottom of screen
    coords_y_pos_info = map_view_rect.top - coords_surf_info.get_height() - 4
    if coords_y_pos_info < 5: # If too close to top of screen
        coords_y_pos_info = map_view_rect.bottom + 4
        if coords_y_pos_info + coords_surf_info.get_height() > surface.get_height() - 5: # If still too low
            coords_y_pos_info = surface.get_height() - 5 - coords_surf_info.get_height() # Pin to bottom

    surface.blit(coords_surf_info, (coords_x_pos_info, coords_y_pos_info))

def draw_grid_on_map_surface(map_content_surface: pygame.Surface, editor_state: EditorState):
    if not (editor_state.show_grid and editor_state.map_content_surface and editor_state.grid_size > 0): return
    
    map_width_px = editor_state.get_map_pixel_width()
    map_height_px = editor_state.get_map_pixel_height()
    grid_s = editor_state.grid_size
    grid_lines_color = getattr(ED_CONFIG, 'MAP_VIEW_GRID_COLOR', (128,128,128))
    
    try:
        # Draw vertical grid lines
        for x_coord_grid in range(0, map_width_px + grid_s, grid_s): # +gs to ensure last line is drawn if map edge aligns
            pygame.draw.line(map_content_surface, grid_lines_color, (x_coord_grid,0), (x_coord_grid, map_height_px))
        # Draw horizontal grid lines
        for y_coord_grid in range(0, map_height_px + grid_s, grid_s):
            pygame.draw.line(map_content_surface, grid_lines_color, (0, y_coord_grid), (map_width_px, y_coord_grid))
    except Exception as e_grid:
        if logger: logger.error(f"Exception in draw_grid_on_map_surface: {e_grid}", exc_info=True)