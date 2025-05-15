# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.5 (Added bottom overhang for palette, configurable text offset)
Handles loading and managing assets for the editor's palette.
"""
import pygame
import os
import sys
import traceback 
from typing import Optional, List, Dict, Any

# --- (Sys.path manipulation and assets import - keeping essential prints) ---
current_dir = os.path.dirname(os.path.abspath(__file__)) 
parent_dir = os.path.dirname(current_dir)                 
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"INFO ASSETS: Added '{parent_dir}' to sys.path for 'assets' module import.")
try:
    from assets import load_gif_frames, resource_path
    print("INFO ASSETS: Imported 'load_gif_frames' and 'resource_path' from assets.py")
except ImportError as e:
    print(f"CRITICAL ASSETS ERROR: Failed to import from 'assets.py': {e}")
    # Provide dummy functions if import fails, to allow editor to potentially run with limited functionality
    def load_gif_frames(path: str) -> list: # Matches original type hint
        print(f"CRITICAL ASSETS ERROR: Using DUMMY load_gif_frames for path: {path}")
        return []
    def resource_path(relative_path: str) -> str: # Matches original type hint
        # This dummy might not be robust enough if used, but it's a fallback.
        resolved_path = os.path.join(parent_dir, relative_path)
        print(f"CRITICAL ASSETS ERROR: Using DUMMY resource_path. Input: '{relative_path}', Output: '{resolved_path}'")
        return resolved_path
    print("CRITICAL ASSETS ERROR: Using dummy asset loading functions.")
except Exception as e_gen:
    print(f"CRITICAL ASSETS ERROR: Unexpected error importing from 'assets.py': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize assets module in editor_assets.py")

import editor_config as ED_CONFIG 
from editor_state import EditorState


def load_editor_palette_assets(editor_state: EditorState):
    editor_state.assets_palette.clear()
    print("INFO ASSETS: Loading editor palette assets...")
    successful_loads = 0; failed_loads = 0

    for asset_key, asset_info in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        surf: Optional[pygame.Surface] = None
        tooltip = asset_info.get("tooltip", asset_key)
        game_type_id = asset_info.get("game_type_id", asset_key)
        category = asset_info.get("category", "unknown")

        if "source_file" in asset_info:
            source_file_path = asset_info["source_file"]
            try:
                full_path = resource_path(source_file_path)
                if not os.path.exists(full_path):
                    print(f"Assets Error: File NOT FOUND at '{full_path}' for asset '{asset_key}'")
                    # Don't try to load if not found, surf will remain None
                else:
                    frames = load_gif_frames(full_path)
                    if frames: surf = frames[0]
                    else: print(f"Warning ASSETS: load_gif_frames returned empty list for '{asset_key}' from '{full_path}'.")
            except Exception as e: print(f"Error ASSETS: Loading '{asset_key}' from '{source_file_path}': {e}"); # traceback.print_exc() # Less verbose
        elif "surface_params" in asset_info:
            try:
                w, h, color = asset_info["surface_params"]
                surf = pygame.Surface((max(1, w), max(1, h))); surf.fill(color)
            except Exception as e: print(f"Error ASSETS: Creating surface for '{asset_key}': {e}"); # traceback.print_exc()

        if not surf:
            print(f"Warning ASSETS: Surface for '{asset_key}' is None. Creating fallback.")
            surf = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE))
            surf.fill(getattr(ED_CONFIG.C, 'RED', (255,0,0))) # Use ED_CONFIG.C for colors if available
            pygame.draw.line(surf, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), (0,0), surf.get_size(), 1)
            pygame.draw.line(surf, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), (0,surf.get_height()-1), (surf.get_width()-1,0), 1)
            tooltip += " (Load Error)"; failed_loads += 1
        else: successful_loads +=1

        original_w, original_h = surf.get_size()
        scaled_surf = surf
        if original_w > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h > ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT:
            ratio = min(ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH / original_w if original_w > 0 else 1,
                        ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT / original_h if original_h > 0 else 1)
            new_w, new_h = max(1, int(original_w * ratio)), max(1, int(original_h * ratio))
            try: 
                scaled_surf = pygame.transform.smoothscale(surf, (new_w, new_h)) # Use smoothscale for better quality
            except Exception: 
                print(f"Error ASSETS: Scaling '{asset_key}' failed. Using original."); scaled_surf = surf # Fallback to original if scaling fails
        
        try:
            # Ensure conversion for consistent pixel formats
            final_surf_to_store = scaled_surf.convert_alpha() if scaled_surf.get_flags() & pygame.SRCALPHA else scaled_surf.convert()
        except pygame.error as e: 
            print(f"Error ASSETS: Converting surface for '{asset_key}' failed: {e}. Using unoptimized surface."); 
            final_surf_to_store = scaled_surf # Fallback to unoptimized surface

        editor_state.assets_palette[asset_key] = {
            "image": final_surf_to_store, "game_type_id": game_type_id,
            "tooltip": tooltip, "category": category,
            "original_size_pixels": (original_w, original_h)
        }
    print(f"INFO ASSETS: Palette loading done. Success: {successful_loads}, Failed: {failed_loads}.")
    _calculate_asset_palette_total_height(editor_state)


def _calculate_asset_palette_total_height(editor_state: EditorState):
    current_calc_y = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING 
    
    font_category = ED_CONFIG.FONT_CONFIG.get("medium")
    font_tooltip = ED_CONFIG.FONT_CONFIG.get("small")
    # Provide default heights if font objects are None (e.g., font file not found)
    cat_font_h = font_category.get_height() if font_category else 28 
    tip_font_h = font_tooltip.get_height() if font_tooltip else 20
    
    # Configurable vertical offset for tooltip text (space between image and text)
    tooltip_text_v_offset = getattr(ED_CONFIG, 'ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET', 2) # Default to 2px
    
    categories_in_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER', 
                                  ["tile", "hazard", "item", "enemy", "spawn", "unknown"]) # Default order
    
    # Initialize dictionary to hold categorized assets
    categorized_assets_present: Dict[str, List[Dict[str, Any]]] = {cat_name: [] for cat_name in categories_in_order}
    if "unknown" not in categorized_assets_present: # Ensure "unknown" key exists if not in categories_in_order
        categorized_assets_present["unknown"] = []
    
    # Sort assets into categories
    for asset_key, data in editor_state.assets_palette.items():
        category_name = data.get("category", "unknown")
        # If category_name is not in pre-defined categories_in_order, add to "unknown"
        categorized_assets_present.get(category_name, categorized_assets_present["unknown"]).append(data)

    for category_name in categories_in_order:
        assets_in_this_category = categorized_assets_present.get(category_name, [])
        if not assets_in_this_category: 
            continue # Skip this category if it has no assets

        # Add height for category title and padding below it
        current_calc_y += cat_font_h + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
        
        # Special handling for side-by-side spawn items (player1_spawn, player2_spawn)
        if category_name == "spawn" and \
           any(d.get("game_type_id") == "player1_spawn" for d in assets_in_this_category) and \
           any(d.get("game_type_id") == "player2_spawn" for d in assets_in_this_category):
            
            p1_data = next((d for d in assets_in_this_category if d.get("game_type_id") == "player1_spawn"), None)
            p2_data = next((d for d in assets_in_this_category if d.get("game_type_id") == "player2_spawn"), None)
            
            max_img_h = 0
            if p1_data and p1_data.get("image"): max_img_h = max(max_img_h, p1_data["image"].get_height())
            if p2_data and p2_data.get("image"): max_img_h = max(max_img_h, p2_data["image"].get_height())
            
            if max_img_h > 0: # If at least one spawn item has an image
                current_calc_y += max_img_h # Height of the row of images
                current_calc_y += tip_font_h + tooltip_text_v_offset # Height for one line of text below, using configurable offset
                current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding after this row
            
            # Remove P1 and P2 spawn from list so they are not processed again in the loop below
            # This rebinds `assets_in_this_category` to a new list for the subsequent loop;
            # it does not modify the list in `categorized_assets_present`.
            assets_in_this_category = [d for d in assets_in_this_category if d.get("game_type_id") not in ["player1_spawn", "player2_spawn"]]
            # Fallthrough to process any OTHER spawn items normally (if any)
        
        # Process remaining items in the category (or all if not "spawn" with P1/P2 handled above)
        for asset_data in assets_in_this_category:
            asset_img = asset_data.get("image")
            if not asset_img: 
                continue # Skip if asset has no image (e.g., load error)
            current_calc_y += asset_img.get_height() # Height of the asset image
            current_calc_y += tip_font_h + tooltip_text_v_offset # Height for tooltip text below, using configurable offset
            current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding after this item
        
        # Add extra padding after the entire category block
        current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
            
    # Add a final overhang (e.g., ~1 inch in pixels) at the bottom of the palette content.
    # This ensures there's ample blank space, preventing potential UI elements at the
    # bottom of the palette (like a "bg color button") from obscuring the last asset items.
    asset_palette_bottom_overhang_px = getattr(ED_CONFIG, 'ASSET_PALETTE_BOTTOM_OVERHANG_PX', 72) # Default to 72 pixels (common for 1 inch at 72 DPI)
    current_calc_y += asset_palette_bottom_overhang_px
            
    editor_state.total_asset_palette_content_height = current_calc_y
    print(f"INFO ASSETS: Calculated total asset palette content height (incl. {asset_palette_bottom_overhang_px}px overhang): {editor_state.total_asset_palette_content_height}")