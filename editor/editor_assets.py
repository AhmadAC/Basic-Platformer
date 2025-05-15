# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.2 (Added extensive debug prints and error handling for asset loading)
Handles loading and managing assets for the editor's palette.
"""
import pygame
import os
import sys
import traceback # ADDED for detailed error reporting
from typing import Optional # ADDED for type hinting

# --- Add parent directory to sys.path for assets module ---
# This assumes 'editor' is a subfolder of the project root where 'assets.py' resides.
current_dir = os.path.dirname(os.path.abspath(__file__)) # Should be /path/to/project/editor
parent_dir = os.path.dirname(current_dir)                 # Should be /path/to/project
print(f"DEBUG ASSETS: current_dir (editor_assets.py location): {current_dir}")
print(f"DEBUG ASSETS: parent_dir (project root attempt): {parent_dir}")

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"DEBUG ASSETS: Added '{parent_dir}' to sys.path for 'assets' module import.")
else:
    print(f"DEBUG ASSETS: '{parent_dir}' already in sys.path for 'assets' module.")

try:
    from assets import load_gif_frames, resource_path
    print("DEBUG ASSETS: Successfully imported 'load_gif_frames' and 'resource_path' from assets.py")
except ImportError as e:
    print(f"CRITICAL ASSETS ERROR: Failed to import from 'assets.py' (expected in '{parent_dir}'). Error: {e}")
    # Define dummy functions if import fails, so editor can limp along with errors.
    def load_gif_frames(path: str) -> list:
        print(f"DUMMY load_gif_frames called for {path} due to import error.")
        return []
    def resource_path(relative_path: str) -> str:
        print(f"DUMMY resource_path called for {relative_path} due to import error.")
        # Attempt a basic join from current parent, might not be correct but better than nothing.
        return os.path.join(parent_dir, relative_path)
    print("CRITICAL ASSETS ERROR: Using dummy asset loading functions. Asset loading will likely fail.")
except Exception as e_gen:
    print(f"CRITICAL ASSETS ERROR: Unexpected error importing from 'assets.py': {e_gen}")
    traceback.print_exc()
    sys.exit("Failed to initialize assets module in editor_assets.py")

import editor_config as ED_CONFIG # Direct import, should work if editor_config.py is in the same 'editor' dir
from editor_state import EditorState


def load_editor_palette_assets(editor_state: EditorState):
    """
    Loads images for the asset palette based on EDITOR_PALETTE_ASSETS in config.
    Populates editor_state.assets_palette.
    Calculates editor_state.total_asset_palette_content_height.
    """
    editor_state.assets_palette.clear()
    print("DEBUG ASSETS: Starting load_editor_palette_assets...")
    successful_loads = 0
    failed_loads = 0

    for asset_key, asset_info in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        print(f"\nDEBUG ASSETS: Processing asset_key: '{asset_key}', Info: {asset_info}")
        surf: Optional[pygame.Surface] = None # Changed to Optional[pygame.Surface]
        tooltip = asset_info.get("tooltip", asset_key)
        game_type_id = asset_info.get("game_type_id", asset_key)
        category = asset_info.get("category", "unknown")

        if "source_file" in asset_info:
            source_file_path = asset_info["source_file"]
            print(f"DEBUG ASSETS: Asset '{asset_key}' uses source_file: '{source_file_path}'")
            try:
                # resource_path should convert the relative path from project root
                # e.g., "characters/player1/__Idle.gif" to "C:/.../Project/characters/player1/__Idle.gif"
                full_path = resource_path(source_file_path)
                print(f"DEBUG ASSETS: Resolved path by resource_path for '{source_file_path}': '{full_path}'")
                
                if not os.path.exists(full_path):
                    print(f"Assets Error: File NOT FOUND at resolved path: '{full_path}' for asset '{asset_key}' (source: '{source_file_path}')")
                    # This is the error you were seeing, indicating `resource_path` or the base path for it is incorrect.
                    # `resource_path` in your game's assets.py might be using `os.path.join(os.path.dirname(__file__), relative_path)`
                    # which, if `assets.py` is in the project root, would correctly resolve `characters/...`
                    # However, if `resource_path` is called from `editor_assets.py` and uses `__file__` from `editor_assets.py`,
                    # it would look inside the `editor` folder.
                    # The current fix of adding parent_dir to sys.path and importing `resource_path` from the root `assets.py`
                    # should ensure `resource_path` uses its *own* `__file__` (from root `assets.py`) as its base if it's designed that way.
                
                frames = load_gif_frames(full_path)
                if frames:
                    surf = frames[0]
                    print(f"DEBUG ASSETS: Successfully loaded {len(frames)} frames for '{asset_key}' from '{full_path}'. Using first frame.")
                else:
                    print(f"Warning ASSETS: load_gif_frames returned empty list for '{asset_key}' from '{full_path}'.")
            except Exception as e:
                print(f"Error ASSETS: Exception loading palette asset '{asset_key}' (source: '{source_file_path}'): {e}")
                traceback.print_exc()

        elif "surface_params" in asset_info:
            print(f"DEBUG ASSETS: Asset '{asset_key}' uses surface_params: {asset_info['surface_params']}")
            try:
                w, h, color = asset_info["surface_params"]
                surf = pygame.Surface((max(1, w), max(1, h))) # Ensure min 1x1
                surf.fill(color)
                print(f"DEBUG ASSETS: Created surface for '{asset_key}' with params ({w},{h},{color}).")
            except Exception as e:
                print(f"Error ASSETS: Exception creating surface for palette asset '{asset_key}': {e}")
                traceback.print_exc()
        
        if not surf:
            print(f"Warning ASSETS: Surface for '{asset_key}' is None. Creating fallback placeholder.")
            surf = pygame.Surface((ED_CONFIG.DEFAULT_GRID_SIZE, ED_CONFIG.DEFAULT_GRID_SIZE))
            surf.fill(ED_CONFIG.C.RED)
            pygame.draw.line(surf, ED_CONFIG.C.BLACK, (0,0), surf.get_size(), 1)
            pygame.draw.line(surf, ED_CONFIG.C.BLACK, (0,surf.get_height()-1), (surf.get_width()-1,0), 1) # Adjusted line
            tooltip += " (Load Error)"
            failed_loads += 1
        else:
            successful_loads +=1


        original_w, original_h = surf.get_size()
        scaled_surf = surf
        if original_w > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h > ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT:
            print(f"DEBUG ASSETS: Asset '{asset_key}' original size ({original_w}x{original_h}) exceeds thumbnail max. Scaling...")
            ratio_w = ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH / original_w if original_w > 0 else 1
            ratio_h = ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT / original_h if original_h > 0 else 1
            ratio = min(ratio_w, ratio_h)
            
            new_w = max(1, int(original_w * ratio))
            new_h = max(1, int(original_h * ratio))
            print(f"DEBUG ASSETS: Scaling '{asset_key}' to ({new_w}x{new_h}) with ratio {ratio:.2f}.")
            try:
                scaled_surf = pygame.transform.scale(surf, (new_w, new_h))
            except pygame.error as e:
                print(f"Error ASSETS: Pygame error scaling asset '{asset_key}': {e}. Using original.")
                scaled_surf = surf 
            except Exception as e_scale:
                print(f"Error ASSETS: Generic error scaling asset '{asset_key}': {e_scale}. Using original.")
                traceback.print_exc()
                scaled_surf = surf
        
        # Ensure surface is converted correctly for performance and alpha handling
        try:
            final_surf_to_store = scaled_surf.convert_alpha() if scaled_surf.get_flags() & pygame.SRCALPHA else scaled_surf.convert()
        except pygame.error as e_convert:
            print(f"Error ASSETS: Pygame error converting surface for '{asset_key}': {e_convert}. Storing as is.")
            final_surf_to_store = scaled_surf # Store unconverted if error

        editor_state.assets_palette[asset_key] = {
            "image": final_surf_to_store,
            "game_type_id": game_type_id,
            "tooltip": tooltip,
            "category": category,
            "original_size_pixels": (original_w, original_h)
        }
        print(f"DEBUG ASSETS: Stored asset '{asset_key}' in palette. Tooltip: '{tooltip}', Category: '{category}'.")
    
    print(f"DEBUG ASSETS: Finished loading palette. Successful: {successful_loads}, Failed/Fallback: {failed_loads}. Total in config: {len(ED_CONFIG.EDITOR_PALETTE_ASSETS)}")
    _calculate_asset_palette_total_height(editor_state)


def _calculate_asset_palette_total_height(editor_state: EditorState):
    """
    Calculates the total vertical space needed to display all assets in the palette.
    """
    print("DEBUG ASSETS: Starting _calculate_asset_palette_total_height...")
    total_height = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING 

    font_category = ED_CONFIG.FONT_CONFIG.get("medium")
    font_tooltip = ED_CONFIG.FONT_CONFIG.get("small")

    if not font_category:
        print("Warning ASSETS: Medium font (for category titles) not available for palette height calculation. Using estimate.")
        font_category_height_estimate = 28 # Estimate
    else:
        font_category_height_estimate = font_category.get_height()

    if not font_tooltip:
        print("Warning ASSETS: Small font (for item tooltips) not available for palette height calculation. Using estimate.")
        font_tooltip_height_estimate = 20 # Estimate
    else:
        font_tooltip_height_estimate = font_tooltip.get_height()
    
    # Use the defined order from editor_config if available, otherwise a sensible default
    categories_in_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER', 
                                  ["tile", "hazard", "item", "enemy", "spawn", "unknown"])
    print(f"DEBUG ASSETS: Calculating height using category order: {categories_in_order}")

    # Group assets by their category first
    categorized_assets_view = {}
    for cat_name in categories_in_order:
        categorized_assets_view[cat_name] = []
    
    for asset_key, data in editor_state.assets_palette.items():
        category_name = data.get("category", "unknown")
        if category_name not in categorized_assets_view: # Handle case where an asset has a category not in defined order
            if "unknown" not in categorized_assets_view: # Should be there from init
                 categorized_assets_view["unknown"] = []
            categorized_assets_view["unknown"].append(data)
            print(f"Warning ASSETS: Asset '{asset_key}' has category '{category_name}' not in defined order. Added to 'unknown'.")
        else:
            categorized_assets_view[category_name].append(data)


    for category_name in categories_in_order:
        assets_in_this_category = categorized_assets_view.get(category_name, [])
        if not assets_in_this_category:
            # print(f"DEBUG ASSETS: No assets in category '{category_name}' for height calculation.")
            continue

        print(f"DEBUG ASSETS: Calculating height for category '{category_name}' with {len(assets_in_this_category)} items.")
        total_height += font_category_height_estimate + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Space for category title
        
        for asset_data in assets_in_this_category:
            asset_img = asset_data.get("image")
            if not asset_img:
                print(f"Warning ASSETS: Asset data missing 'image' in category '{category_name}' during height calc. Skipping item height.")
                continue
            
            total_height += asset_img.get_height() # Image height
            total_height += font_tooltip_height_estimate # Space for the tooltip text below image
            total_height += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Padding below item text
        
        total_height += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Extra padding after all items in a category

    editor_state.total_asset_palette_content_height = total_height + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Final bottom padding
    print(f"DEBUG ASSETS: Calculated total_asset_palette_content_height: {editor_state.total_asset_palette_content_height}")