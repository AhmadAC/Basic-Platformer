# editor_drawing.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.3 (Added debug prints, fixed category order, exception handling)
Contains functions for drawing the different sections and elements
of the Platformer Level Editor UI using Pygame.
"""
import pygame
from typing import Dict, Tuple, Any, Optional # Added Optional
import traceback # ADDED

# Assuming these are in the 'editor' package or accessible if editor.py is also in 'editor'
import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import draw_button # draw_tooltip, draw_status_message, draw_active_dialog are called from main

def draw_menu_ui(surface: pygame.Surface,
                 editor_state: EditorState,
                 menu_section_rect: pygame.Rect,
                 fonts: Dict[str, Optional[pygame.font.Font]], # Allow Optional[Font]
                 mouse_pos: Tuple[int, int]):
    """Draws the main menu UI elements within the given section_rect."""
    # print(f"DEBUG DRAW: draw_menu_ui called. Rect: {menu_section_rect}") # Can be verbose
    try:
        pygame.draw.rect(surface, ED_CONFIG.C.BLACK, menu_section_rect) # Menu background

        title_font = fonts.get("large") or ED_CONFIG.FONT_CONFIG.get("large")
        button_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")

        if title_font:
            title_surf = title_font.render("Level Editor", True, ED_CONFIG.C.WHITE)
            title_rect = title_surf.get_rect(centerx=menu_section_rect.centerx, top=menu_section_rect.top + 20)
            surface.blit(title_surf, title_rect)
        else:
            print("Warning DRAW: Menu title font not available.")

        button_w = ED_CONFIG.BUTTON_WIDTH_STANDARD
        button_h = ED_CONFIG.BUTTON_HEIGHT_STANDARD
        spacing = 20
        num_buttons = 3 # New, Load, Quit
        total_button_height = (num_buttons * button_h) + ((num_buttons - 1) * spacing)
        
        title_height_approx = title_font.get_height() if title_font else 40
        content_start_y = menu_section_rect.top + title_height_approx + 30 # Space below title

        # Center buttons in remaining vertical space if possible
        remaining_height = menu_section_rect.height - (content_start_y - menu_section_rect.top)
        start_y = content_start_y + (remaining_height - total_button_height) // 2
        
        # Ensure start_y is not too high (e.g., overlapping title if remaining_height is small)
        start_y = max(start_y, content_start_y)


        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
            editor_state.ui_elements_rects = {}
            print("DEBUG DRAW: Initialized editor_state.ui_elements_rects in draw_menu_ui")

        # Clear only menu-specific rects to avoid affecting other UI parts
        keys_to_remove = [k for k in editor_state.ui_elements_rects if k.startswith("menu_")]
        for k in keys_to_remove:
            del editor_state.ui_elements_rects[k]

        if button_font:
            new_rect = pygame.Rect(0, 0, button_w, button_h)
            new_rect.centerx = menu_section_rect.centerx
            new_rect.top = start_y
            editor_state.ui_elements_rects["menu_new_map"] = new_rect
            draw_button(surface, new_rect, "New Map", button_font, mouse_pos)
            # print(f"DEBUG DRAW: Stored menu_new_map rect: {new_rect}")

            load_rect = pygame.Rect(0, 0, button_w, button_h)
            load_rect.centerx = menu_section_rect.centerx
            load_rect.top = new_rect.bottom + spacing
            editor_state.ui_elements_rects["menu_load_map"] = load_rect
            draw_button(surface, load_rect, "Load Map (.json)", button_font, mouse_pos)
            # print(f"DEBUG DRAW: Stored menu_load_map rect: {load_rect}")

            quit_rect = pygame.Rect(0, 0, button_w, button_h)
            quit_rect.centerx = menu_section_rect.centerx
            quit_rect.top = load_rect.bottom + spacing
            editor_state.ui_elements_rects["menu_quit"] = quit_rect
            draw_button(surface, quit_rect, "Quit Editor", button_font, mouse_pos)
            # print(f"DEBUG DRAW: Stored menu_quit rect: {quit_rect}")
        else:
            print("Warning DRAW: Menu button font not available.")
    except Exception as e:
        print(f"ERROR DRAW: Exception in draw_menu_ui: {e}")
        traceback.print_exc()


def draw_asset_palette_ui(surface: pygame.Surface,
                          editor_state: EditorState,
                          palette_section_rect: pygame.Rect,
                          fonts: Dict[str, Optional[pygame.font.Font]],
                          mouse_pos: Tuple[int, int]):
    """Draws the scrollable asset palette."""
    # print(f"DEBUG DRAW: draw_asset_palette_ui called. Rect: {palette_section_rect}") # Verbose
    try:
        pygame.draw.rect(surface, ED_CONFIG.ASSET_PALETTE_BG_COLOR, palette_section_rect)
        
        if editor_state.total_asset_palette_content_height <= 0:
            font_small = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
            if font_small:
                loading_text = font_small.render("Assets Loading/Error...", True, ED_CONFIG.C.WHITE)
                surface.blit(loading_text, loading_text.get_rect(center=palette_section_rect.center))
            print("DEBUG DRAW: Asset palette content height <= 0, showing loading/error.")
            return

        # Surface for scrollable content (assets)
        scroll_content_surf_width = palette_section_rect.width # Use full width of the palette section
        scroll_content_surf = pygame.Surface(
            (scroll_content_surf_width, editor_state.total_asset_palette_content_height),
            pygame.SRCALPHA # Support transparency for items
        )
        scroll_content_surf.fill((0,0,0,0)) # Transparent background for the scrollable surface

        current_y_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
        
        category_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
        tooltip_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")

        editor_state.hovered_tooltip_text = None # Reset before checking hovers
        
        if not hasattr(editor_state, 'ui_elements_rects') or editor_state.ui_elements_rects is None:
            editor_state.ui_elements_rects = {}
        editor_state.ui_elements_rects['asset_palette_items'] = {} # Clear and repopulate palette item rects

        # Use a defined order for categories, similar to editor_assets.py
        defined_categories_order = ["tile", "hazard", "item", "enemy", "spawn", "unknown"]

        for category_name in defined_categories_order:
            assets_in_category = [
                (key, data) for key, data in editor_state.assets_palette.items() 
                if data.get("category", "unknown") == category_name
            ]
            if not assets_in_category:
                continue

            if category_font:
                cat_surf = category_font.render(category_name.title(), True, ED_CONFIG.ASSET_PALETTE_CATEGORY_TEXT_COLOR)
                scroll_content_surf.blit(cat_surf, (ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, current_y_on_scroll_surf))
                current_y_on_scroll_surf += cat_surf.get_height() + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING

            for asset_key, asset_data in assets_in_category:
                asset_img = asset_data.get("image")
                if not asset_img:
                    print(f"Warning DRAW: Asset '{asset_key}' has no image in palette. Skipping draw.")
                    continue

                item_x_on_scroll_surf = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
                # Center item horizontally if palette is wider than thumbnail max width + padding
                # if scroll_content_surf_width > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH + 2 * ED_CONFIG.ASSET_PALETTE_ITEM_PADDING:
                #     item_x_on_scroll_surf = (scroll_content_surf_width - asset_img.get_width()) // 2
                
                item_y_on_scroll_surf = current_y_on_scroll_surf
                
                # Calculate the on-screen rect for mouse collision
                item_rect_on_screen = pygame.Rect(
                    palette_section_rect.left + item_x_on_scroll_surf, # X position on screen
                    palette_section_rect.top + item_y_on_scroll_surf - editor_state.asset_palette_scroll_y, # Y on screen, adjusted by scroll
                    asset_img.get_width(),
                    asset_img.get_height()
                )
                editor_state.ui_elements_rects['asset_palette_items'][asset_key] = item_rect_on_screen

                is_hovered = item_rect_on_screen.collidepoint(mouse_pos) and \
                             palette_section_rect.collidepoint(mouse_pos) # Must be within palette bounds
                is_selected = editor_state.selected_asset_editor_key == asset_key

                # Draw hover/selection effects onto the scroll_content_surf
                if is_hovered:
                    editor_state.hovered_tooltip_text = asset_data.get("tooltip", asset_key)
                    editor_state.hovered_tooltip_pos = mouse_pos
                    # Hover background rect on the scrollable surface
                    hover_bg_rect_on_scroll = pygame.Rect(item_x_on_scroll_surf - 2, item_y_on_scroll_surf - 2,
                                                        asset_img.get_width() + 4, asset_img.get_height() + 4)
                    pygame.draw.rect(scroll_content_surf, ED_CONFIG.ASSET_PALETTE_HOVER_BG_COLOR, hover_bg_rect_on_scroll, border_radius=2)
                
                if is_selected:
                    # Selection border rect on the scrollable surface
                    select_border_rect_on_scroll = pygame.Rect(item_x_on_scroll_surf - 3, item_y_on_scroll_surf - 3,
                                                        asset_img.get_width() + 6, asset_img.get_height() + 6)
                    pygame.draw.rect(scroll_content_surf, ED_CONFIG.C.YELLOW, select_border_rect_on_scroll, 2, border_radius=3)

                scroll_content_surf.blit(asset_img, (item_x_on_scroll_surf, item_y_on_scroll_surf))
                current_y_on_scroll_surf += asset_img.get_height()
                
                if tooltip_font: # Draw asset name/tooltip below image
                    name_text = asset_data.get("tooltip", asset_key)
                    name_surf = tooltip_font.render(name_text, True, ED_CONFIG.ASSET_PALETTE_TOOLTIP_COLOR)
                    # Center text below image on scrollable surface
                    name_x_pos = item_x_on_scroll_surf + (asset_img.get_width() - name_surf.get_width()) // 2
                    name_x_pos = max(item_x_on_scroll_surf, name_x_pos) # Ensure not left of item start
                    
                    scroll_content_surf.blit(name_surf, (name_x_pos, current_y_on_scroll_surf + 2))
                    current_y_on_scroll_surf += name_surf.get_height() + 2 # Extra padding after text
                
                current_y_on_scroll_surf += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding below item group (image + text)
            
            current_y_on_scroll_surf += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding after category items

        # Blit the visible part of scroll_content_surf onto the main surface
        surface.blit(scroll_content_surf, palette_section_rect.topleft,
                     (0, editor_state.asset_palette_scroll_y, # Source rect X, Y (scroll offset)
                      palette_section_rect.width, palette_section_rect.height)) # Source rect W, H (visible area)
        
        # Draw border for the palette section itself
        pygame.draw.rect(surface, ED_CONFIG.C.GRAY, palette_section_rect, 2)

        # --- Draw "BG Color" button at the bottom of the palette ---
        btn_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
        if btn_font:
            # Calculate button rect based on palette_section_rect (fixed position on screen)
            button_height = ED_CONFIG.BUTTON_HEIGHT_STANDARD * 0.8 # Smaller button
            cp_button_rect = pygame.Rect(
                palette_section_rect.left + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING,
                palette_section_rect.bottom - button_height - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING, # At bottom
                palette_section_rect.width - ED_CONFIG.ASSET_PALETTE_ITEM_PADDING * 2, # Full width less padding
                button_height
            )
            editor_state.ui_elements_rects["palette_bg_color_button"] = cp_button_rect
            
            # Determine color for button text based on background_color brightness
            bg_lum = sum(editor_state.background_color) / 3
            text_col = ED_CONFIG.C.BLACK if bg_lum > 128 else ED_CONFIG.C.WHITE

            draw_button(surface, cp_button_rect, "BG Color", btn_font, mouse_pos,
                        text_color=text_col,
                        button_color_normal=editor_state.background_color, # Show current BG color on button
                        button_color_hover=pygame.Color(editor_state.background_color).lerp(ED_CONFIG.C.WHITE, 0.3), # type: ignore
                        border_color=ED_CONFIG.C.BLACK)
    except Exception as e:
        print(f"ERROR DRAW: Exception in draw_asset_palette_ui: {e}")
        traceback.print_exc()


def draw_map_view_ui(surface: pygame.Surface,
                     editor_state: EditorState,
                     map_view_rect: pygame.Rect,
                     fonts: Dict[str, Optional[pygame.font.Font]],
                     mouse_pos: Tuple[int, int]):
    """Draws the map editing area, including the grid, placed objects, and cursor asset."""
    # print(f"DEBUG DRAW: draw_map_view_ui called. Rect: {map_view_rect}") # Verbose
    try:
        if not editor_state.map_content_surface:
            pygame.draw.rect(surface, ED_CONFIG.C.DARK_SLATE_GRAY if hasattr(ED_CONFIG.C, 'DARK_SLATE_GRAY') else ED_CONFIG.C.DARK_GRAY, map_view_rect)
            placeholder_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
            if placeholder_font:
                text = placeholder_font.render("No Map Loaded/Created (or surface error)", True, ED_CONFIG.C.WHITE)
                surface.blit(text, text.get_rect(center=map_view_rect.center))
            pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2)
            print("DEBUG DRAW: map_content_surface is None. Drawing placeholder.")
            return

        # Fill map_content_surface with background color
        editor_state.map_content_surface.fill(editor_state.background_color)

        # Draw placed objects onto map_content_surface
        for i, obj_data in enumerate(editor_state.placed_objects):
            asset_key = obj_data.get("asset_editor_key")
            asset_info = editor_state.assets_palette.get(asset_key) if asset_key else None
            
            world_x = obj_data.get("world_x")
            world_y = obj_data.get("world_y")

            if world_x is None or world_y is None:
                print(f"Warning DRAW: Object at index {i} missing world_x/world_y: {obj_data}")
                continue
            
            if asset_info and asset_info.get("image"):
                obj_img_to_draw = asset_info["image"] # This is the thumbnail
                # For drawing on map, ideally, you'd use the original scale or a consistently scaled version.
                # If thumbnails are small, they will look small on the map.
                # If your game uses different sprites than editor palette, this needs more logic.
                editor_state.map_content_surface.blit(obj_img_to_draw, (world_x, world_y))
            else: # Fallback if asset or image is missing
                pygame.draw.rect(editor_state.map_content_surface, ED_CONFIG.C.RED,
                                 (world_x, world_y, editor_state.grid_size, editor_state.grid_size), 1)
                if asset_key:
                    print(f"Warning DRAW: Missing image for asset_key '{asset_key}' when drawing placed object.")

        if editor_state.show_grid:
            draw_grid_on_map_surface(editor_state.map_content_surface, editor_state)

        # Blit the visible part of map_content_surface to the main screen
        surface.blit(editor_state.map_content_surface, map_view_rect.topleft,
                     (editor_state.camera_offset_x, editor_state.camera_offset_y, # Source X, Y from map_content_surface
                      map_view_rect.width, map_view_rect.height)) # Size of area to blit
        
        # Draw border for the map view section
        pygame.draw.rect(surface, ED_CONFIG.MAP_VIEW_BORDER_COLOR, map_view_rect, 2)

        # Draw selected asset at cursor, snapped to grid if over map view
        if editor_state.selected_asset_image_for_cursor:
            cursor_img = editor_state.selected_asset_image_for_cursor
            
            # Default cursor position is just centered on mouse
            final_cursor_pos_on_screen = cursor_img.get_rect(center=mouse_pos).topleft

            if map_view_rect.collidepoint(mouse_pos): # Mouse is over the map view
                # Convert mouse screen coordinates to world coordinates on the map
                map_world_mouse_x = mouse_pos[0] - map_view_rect.left + editor_state.camera_offset_x
                map_world_mouse_y = mouse_pos[1] - map_view_rect.top + editor_state.camera_offset_y
                
                # Snap world coordinates to grid
                grid_snapped_world_x = (map_world_mouse_x // editor_state.grid_size) * editor_state.grid_size
                grid_snapped_world_y = (map_world_mouse_y // editor_state.grid_size) * editor_state.grid_size
                
                # Convert snapped world coordinates back to screen coordinates for drawing
                screen_snap_x = grid_snapped_world_x - editor_state.camera_offset_x + map_view_rect.left
                screen_snap_y = grid_snapped_world_y - editor_state.camera_offset_y + map_view_rect.top
                final_cursor_pos_on_screen = (screen_snap_x, screen_snap_y)

            # Blit cursor image, ensuring it's clipped to the map_view_rect
            original_clip = surface.get_clip()
            surface.set_clip(map_view_rect)
            surface.blit(cursor_img, final_cursor_pos_on_screen)
            surface.set_clip(original_clip)

        # --- Draw Info Text (Coordinates, Instructions) ---
        _draw_map_view_info_text(surface, editor_state, map_view_rect, fonts, mouse_pos)

    except Exception as e:
        print(f"ERROR DRAW: Exception in draw_map_view_ui: {e}")
        traceback.print_exc()

def _draw_map_view_info_text(surface: pygame.Surface, editor_state: EditorState,
                            map_view_rect: pygame.Rect, fonts: Dict[str, Optional[pygame.font.Font]],
                            mouse_pos: Tuple[int, int]):
    """Helper to draw informational text for the map view."""
    info_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if not info_font:
        print("Warning DRAW: Info font not available for map view.")
        return

    # Instructions text
    instr_text_lines = [
        "LMB: Place/Drag, RMB: Del",
        "G: Grid, ESC: Deselect/Menu",
        "Shift+RMB(Map): Save All (JSON & .PY)",
        "Ctrl+S: Save All (JSON & .PY)"
    ]
    
    line_height = info_font.get_height() + 2
    current_instr_y = map_view_rect.bottom + 5

    for i, line_text in enumerate(instr_text_lines):
        instr_surf = info_font.render(line_text, True, ED_CONFIG.C.YELLOW)
        instr_draw_y = current_instr_y + i * line_height
        
        # Basic check to keep text on screen vertically
        if instr_draw_y + line_height > surface.get_height() - 5:
            instr_draw_y = surface.get_height() - 5 - line_height * (len(instr_text_lines) - i)
        
        surface.blit(instr_surf, (map_view_rect.left + 5, instr_draw_y))

    # Coordinates text (above map view)
    coords_text = f"Cam:({editor_state.camera_offset_x},{editor_state.camera_offset_y})"
    if map_view_rect.collidepoint(mouse_pos):
        map_world_mouse_x = mouse_pos[0] - map_view_rect.left + editor_state.camera_offset_x
        map_world_mouse_y = mouse_pos[1] - map_view_rect.top + editor_state.camera_offset_y
        tile_x = map_world_mouse_x // editor_state.grid_size
        tile_y = map_world_mouse_y // editor_state.grid_size
        coords_text += f" MouseW:({map_world_mouse_x},{map_world_mouse_y}) Tile:({tile_x},{tile_y})"

    coords_surf = info_font.render(coords_text, True, ED_CONFIG.C.WHITE)
    coords_y_pos = map_view_rect.top - coords_surf.get_height() - 3 # Position above map_view_rect
    
    # Ensure coords text is on screen if map_view_rect is near the top
    if coords_y_pos < 5:
        coords_y_pos = 5 # Push down if too high
        # Alternative: move it below instructions if there's critical overlap, but above is preferred.

    surface.blit(coords_surf, (map_view_rect.left + 5, coords_y_pos))


def draw_grid_on_map_surface(map_content_surface: pygame.Surface, editor_state: EditorState):
    """Draws a grid directly onto the map_content_surface."""
    if not editor_state.show_grid or not editor_state.map_content_surface:
        return
    
    # print("DEBUG DRAW: Drawing grid on map_content_surface.") # Very verbose
    map_width_px = editor_state.get_map_pixel_width()
    map_height_px = editor_state.get_map_pixel_height()
    grid_size = editor_state.grid_size
    
    if grid_size <= 0:
        print(f"Warning DRAW: Invalid grid_size ({grid_size}) for drawing grid.")
        return

    grid_color = ED_CONFIG.MAP_VIEW_GRID_COLOR

    try:
        # Vertical lines
        for x in range(0, map_width_px + 1, grid_size): # +1 to ensure last line is drawn if map_width is multiple of grid_size
            pygame.draw.line(map_content_surface, grid_color, (x, 0), (x, map_height_px))
        # Horizontal lines
        for y in range(0, map_height_px + 1, grid_size):
            pygame.draw.line(map_content_surface, grid_color, (0, y), (map_width_px, y))
    except Exception as e:
        print(f"ERROR DRAW: Exception in draw_grid_on_map_surface: {e}")
        traceback.print_exc()