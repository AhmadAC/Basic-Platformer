# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.7 (Adjust palette height calculation for minimap)
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
    # print(f"INFO ASSETS: Added '{parent_dir}' to sys.path for 'assets' module import.")
# try:
    # from assets import load_gif_frames, resource_path
    # print("INFO ASSETS: Imported 'load_gif_frames' and 'resource_path' from assets.py")
# except ImportError as e:
    # print(f"CRITICAL ASSETS ERROR: Failed to import from 'assets.py': {e}")
    # def load_gif_frames(path: str) -> list:
        # print(f"CRITICAL ASSETS ERROR: Using DUMMY load_gif_frames for path: {path}")
        # return []
    # def resource_path(relative_path: str) -> str:
        # resolved_path = os.path.join(parent_dir, relative_path)
        # print(f"CRITICAL ASSETS ERROR: Using DUMMY resource_path. Input: '{relative_path}', Output: '{resolved_path}'")
        # return resolved_path
    # print("CRITICAL ASSETS ERROR: Using dummy asset loading functions.")
# except Exception as e_gen:
    # print(f"CRITICAL ASSETS ERROR: Unexpected error importing from 'assets.py': {e_gen}"); traceback.print_exc()
    # sys.exit("Failed to initialize assets module in editor_assets.py")

# Simplified import for brevity in this example, ensure your actual import works
try:
    from assets import load_gif_frames, resource_path # Assuming this is in your project root/assets.py
except ImportError:
    print("CRITICAL: 'assets' module not found. Using dummy functions.")
    def load_gif_frames(path): return []
    def resource_path(path): return os.path.join(parent_dir, path) # Basic fallback


import editor_config as ED_CONFIG
from editor_state import EditorState


def load_editor_palette_assets(editor_state: EditorState):
    editor_state.assets_palette.clear()
    # print("INFO ASSETS: Loading editor palette assets...")
    successful_loads = 0; failed_loads = 0
    ts = ED_CONFIG.DEFAULT_GRID_SIZE

    for asset_key, asset_info in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        surf: Optional[pygame.Surface] = None
        tooltip = asset_info.get("tooltip", asset_key)
        game_type_id = asset_info.get("game_type_id", asset_key)
        category = asset_info.get("category", "unknown")
        original_w, original_h = ts, ts

        if "source_file" in asset_info:
            source_file_path = asset_info["source_file"]
            try:
                full_path = resource_path(source_file_path)
                if not os.path.exists(full_path):
                    print(f"Assets Error: File NOT FOUND at '{full_path}' for asset '{asset_key}'")
                else:
                    frames = load_gif_frames(full_path)
                    if frames: surf = frames[0]
                    # else: print(f"Warning ASSETS: load_gif_frames returned empty list for '{asset_key}' from '{full_path}'.")
            except Exception as e: print(f"Error ASSETS: Loading '{asset_key}' from '{source_file_path}': {e}");
        elif "surface_params" in asset_info:
            try:
                w, h, color = asset_info["surface_params"]
                original_w, original_h = w, h
                surf = pygame.Surface((max(1, w), max(1, h))); surf.fill(color)
            except Exception as e: print(f"Error ASSETS: Creating surface for '{asset_key}': {e}");
        elif "render_mode" in asset_info and asset_info["render_mode"] == "half_tile":
            try:
                surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
                surf.fill((0,0,0,0))
                color = asset_info.get("base_color_tuple", getattr(ED_CONFIG.C, "MAGENTA", (255,0,255)))
                half_type = asset_info.get("half_type", "left")
                rect_to_draw = pygame.Rect(0,0,0,0)
                if half_type == "left": rect_to_draw = pygame.Rect(0, 0, ts // 2, ts)
                elif half_type == "right": rect_to_draw = pygame.Rect(ts // 2, 0, ts // 2, ts)
                elif half_type == "top": rect_to_draw = pygame.Rect(0, 0, ts, ts // 2)
                elif half_type == "bottom": rect_to_draw = pygame.Rect(0, ts // 2, ts, ts // 2)
                pygame.draw.rect(surf, color, rect_to_draw)
                original_w, original_h = ts, ts
            except Exception as e: print(f"Error ASSETS: Creating half_tile surface for '{asset_key}': {e}");
        elif "icon_type" in asset_info:
            try:
                surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
                surf.fill((0,0,0,0))
                color = asset_info.get("base_color_tuple", getattr(ED_CONFIG.C, "YELLOW", (255,255,0)))
                icon_type = asset_info["icon_type"]
                if icon_type == "2x2_placer":
                    pygame.draw.rect(surf, color, (ts*0.1, ts*0.1, ts*0.35, ts*0.35))
                    pygame.draw.rect(surf, color, (ts*0.55, ts*0.1, ts*0.35, ts*0.35))
                    pygame.draw.rect(surf, color, (ts*0.1, ts*0.55, ts*0.35, ts*0.35))
                    pygame.draw.rect(surf, color, (ts*0.55, ts*0.55, ts*0.35, ts*0.35))
                    pygame.draw.rect(surf, getattr(ED_CONFIG.C, "BLACK", (0,0,0)), (0,0,ts,ts), 1)
                elif icon_type == "triangle_tool":
                    points = [(ts*0.5, ts*0.1), (ts*0.1, ts*0.9), (ts*0.9, ts*0.9)]
                    pygame.draw.polygon(surf, color, points)
                    pygame.draw.polygon(surf, getattr(ED_CONFIG.C, "BLACK", (0,0,0)), points, 2)
                original_w, original_h = ts, ts
            except Exception as e: print(f"Error ASSETS: Creating icon surface for '{asset_key}': {e}");

        if not surf:
            # print(f"Warning ASSETS: Surface for '{asset_key}' is None. Creating fallback.")
            surf = pygame.Surface((ts, ts))
            surf.fill(getattr(ED_CONFIG.C, 'RED', (255,0,0)))
            pygame.draw.line(surf, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), (0,0), surf.get_size(), 1)
            pygame.draw.line(surf, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), (0,surf.get_height()-1), (surf.get_width()-1,0), 1)
            tooltip += " (Load Error)"; failed_loads += 1
        else:
            if asset_info.get("source_file"):
                 original_w, original_h = surf.get_size()
            successful_loads +=1

        scaled_surf = surf
        if (asset_info.get("source_file") and (original_w > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h > ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT)) or \
           (not asset_info.get("source_file") and (original_w != ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h != ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT) and \
            (original_w > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h > ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT)):
            if original_w > ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH or original_h > ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT:
                ratio = min(ED_CONFIG.ASSET_THUMBNAIL_MAX_WIDTH / original_w if original_w > 0 else 1,
                            ED_CONFIG.ASSET_THUMBNAIL_MAX_HEIGHT / original_h if original_h > 0 else 1)
                new_w, new_h = max(1, int(original_w * ratio)), max(1, int(original_h * ratio))
                try:
                    scaled_surf = pygame.transform.smoothscale(surf, (new_w, new_h))
                except Exception:
                    # print(f"Error ASSETS: Scaling '{asset_key}' failed. Using original.");
                    scaled_surf = surf
        try:
            final_surf_to_store = scaled_surf.convert_alpha() if scaled_surf.get_flags() & pygame.SRCALPHA else scaled_surf.convert()
        except pygame.error as e:
            # print(f"Error ASSETS: Converting surface for '{asset_key}' failed: {e}. Using unoptimized surface.");
            final_surf_to_store = scaled_surf

        editor_state.assets_palette[asset_key] = {
            "image": final_surf_to_store, "game_type_id": game_type_id,
            "tooltip": tooltip, "category": category,
            "original_size_pixels": (original_w, original_h),
            "places_asset_key": asset_info.get("places_asset_key"),
            "colorable": asset_info.get("colorable", False),
            "render_mode": asset_info.get("render_mode"),
            "half_type": asset_info.get("half_type"),
            "base_color_tuple": asset_info.get("base_color_tuple"),
            "surface_params_dims_color": asset_info.get("surface_params")
        }
    # print(f"INFO ASSETS: Palette loading done. Success: {successful_loads}, Failed: {failed_loads}.")
    _calculate_asset_palette_total_height(editor_state)


def _calculate_asset_palette_total_height(editor_state: EditorState):
    # This calculates the height of the *scrollable content* below the minimap
    current_calc_y = ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Start padding for the first category

    font_category = ED_CONFIG.FONT_CONFIG.get("medium")
    font_tooltip = ED_CONFIG.FONT_CONFIG.get("small")
    cat_font_h = font_category.get_height() if font_category else 28
    tip_font_h = font_tooltip.get_height() if font_tooltip else 20

    tooltip_text_v_offset = getattr(ED_CONFIG, 'ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET', 2)

    categories_in_order = getattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER',
                                  ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"])

    categorized_assets_present: Dict[str, List[Dict[str, Any]]] = {cat_name: [] for cat_name in categories_in_order}
    # Ensure all expected keys exist
    for cat_name in ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"]:
        if cat_name not in categorized_assets_present:
            categorized_assets_present[cat_name] = []


    for asset_key, data in editor_state.assets_palette.items():
        category_name = data.get("category", "unknown")
        categorized_assets_present.get(category_name, categorized_assets_present["unknown"]).append(data)

    for category_name in categories_in_order:
        assets_in_this_category = categorized_assets_present.get(category_name, [])
        if not assets_in_this_category:
            continue

        current_calc_y += cat_font_h + ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Height for category title

        if category_name == "spawn" and \
           any(d.get("game_type_id") == "player1_spawn" for d in assets_in_this_category) and \
           any(d.get("game_type_id") == "player2_spawn" for d in assets_in_this_category):
            # ... (spawn specific layout logic, already uses asset_data["image"].get_height()) ...
            p1_data = next((d for d in assets_in_this_category if d.get("game_type_id") == "player1_spawn"), None)
            p2_data = next((d for d in assets_in_this_category if d.get("game_type_id") == "player2_spawn"), None)
            max_img_h = 0
            if p1_data and p1_data.get("image"): max_img_h = max(max_img_h, p1_data["image"].get_height())
            if p2_data and p2_data.get("image"): max_img_h = max(max_img_h, p2_data["image"].get_height())

            if max_img_h > 0:
                current_calc_y += max_img_h
                current_calc_y += tip_font_h + tooltip_text_v_offset
                current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING
            assets_in_this_category = [d for d in assets_in_this_category if d.get("game_type_id") not in ["player1_spawn", "player2_spawn"]]


        for asset_data in assets_in_this_category: # Process remaining or all other items
            asset_img = asset_data.get("image")
            if not asset_img:
                continue
            current_calc_y += asset_img.get_height()
            current_calc_y += tip_font_h + tooltip_text_v_offset
            current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING

        current_calc_y += ED_CONFIG.ASSET_PALETTE_ITEM_PADDING # Extra padding after the entire category block

    asset_palette_bottom_overhang_px = getattr(ED_CONFIG, 'ASSET_PALETTE_BOTTOM_OVERHANG_PX', 72)
    current_calc_y += asset_palette_bottom_overhang_px

    editor_state.total_asset_palette_content_height = current_calc_y # This is for the scrollable part
    # print(f"INFO ASSETS: Calculated total asset palette SCROLLABLE content height: {editor_state.total_asset_palette_content_height}")