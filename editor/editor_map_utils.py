# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.6 (Handle override_color, half-tiles export)
Utility functions for map operations in the Level Editor,
including initializing new maps, saving/loading editor-specific
map data (JSON), and exporting maps to game-compatible Python scripts.
"""
import pygame
import sys
import os
import json
import traceback
from typing import Optional, Dict, List, Tuple, Any

import editor_config as ED_CONFIG
from editor_state import EditorState

import constants as C
from tiles import Platform, Ladder, Lava


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    print(f"DEBUG MAP_UTILS: init_new_map_state called. Map Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")

    clean_map_name = map_name_for_function.lower().replace(" ", "_").replace("-", "_")
    if not clean_map_name:
        clean_map_name = "untitled_map"
        print(f"DEBUG MAP_UTILS: map_name_for_function was empty after cleaning, defaulting to '{clean_map_name}'")

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.placed_objects = []
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
    editor_state.camera_offset_x = 0
    editor_state.camera_offset_y = 0
    editor_state.unsaved_changes = True
    editor_state.color_change_target_info = None # Reset color tool state

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)

    editor_state.recreate_map_content_surface()

    print(f"DEBUG MAP_UTILS: Editor state initialized for new map. "
          f"map_name_for_function='{editor_state.map_name_for_function}', "
          f"current_map_filename='{editor_state.current_map_filename}', "
          f"unsaved_changes={editor_state.unsaved_changes}")

def ensure_maps_directory_exists() -> bool:
    maps_dir = ED_CONFIG.MAPS_DIRECTORY
    if not os.path.exists(maps_dir):
        print(f"DEBUG MAP_UTILS: Maps directory '{maps_dir}' does not exist. Attempting to create.")
        try:
            os.makedirs(maps_dir)
            print(f"DEBUG MAP_UTILS: Successfully created directory: {maps_dir}")
            return True
        except OSError as e:
            print(f"ERROR MAP_UTILS: Error creating directory {maps_dir}: {e}")
            traceback.print_exc()
            return False
    return True

def save_map_to_json(editor_state: EditorState) -> bool:
    print(f"DEBUG MAP_UTILS: save_map_to_json called. Map name func: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot save JSON."
        editor_state.set_status_message(f"Error: {msg}", 3)
        print(f"ERROR MAP_UTILS: {msg}")
        return False

    if not ensure_maps_directory_exists():
        msg = "Could not create or access maps directory."
        editor_state.set_status_message(f"Error: {msg}", 3)
        print(f"ERROR MAP_UTILS: {msg} JSON save aborted.")
        return False

    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    json_filepath = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_filename)
    print(f"DEBUG MAP_UTILS: Attempting to save JSON to: '{json_filepath}'")

    serializable_objects = []
    for i, obj in enumerate(editor_state.placed_objects):
        asset_key = obj.get("asset_editor_key")
        game_id = obj.get("game_type_id")
        world_x = obj.get("world_x")
        world_y = obj.get("world_y")
        override_color = obj.get("override_color") # Get override_color

        if not all([asset_key, game_id is not None, world_x is not None, world_y is not None]):
             print(f"Warning MAP_UTILS: Object at index {i} has missing data, skipping for JSON: {obj}")
             continue

        s_obj = {
            "asset_editor_key": asset_key,
            "world_x": world_x,
            "world_y": world_y,
            "game_type_id": game_id
        }
        if override_color: # Only add if it exists
            s_obj["override_color"] = list(override_color) # Convert tuple to list for JSON

        serializable_objects.append(s_obj)

    data_to_save = {
        "map_name_for_function": editor_state.map_name_for_function,
        "map_width_tiles": editor_state.map_width_tiles,
        "map_height_tiles": editor_state.map_height_tiles,
        "grid_size": editor_state.grid_size,
        "background_color": list(editor_state.background_color),
        "placed_objects": serializable_objects,
        "camera_offset_x": editor_state.camera_offset_x,
        "camera_offset_y": editor_state.camera_offset_y,
        "show_grid": editor_state.show_grid
    }
    print(f"DEBUG MAP_UTILS: Data to save to JSON (first object example): {serializable_objects[0] if serializable_objects else 'No objects'}")

    try:
        with open(json_filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        success_msg = f"Editor data saved to: {json_filename}"
        print(f"DEBUG MAP_UTILS: {success_msg}")
        editor_state.set_status_message(success_msg)
        # unsaved_changes set False by export_map_to_game_python_script
        return True
    except IOError as e:
        error_msg = f"IOError saving map to JSON '{json_filepath}': {e}"
    except Exception as e:
        error_msg = f"Unexpected error saving map to JSON '{json_filepath}': {e}"
        traceback.print_exc()

    print(f"ERROR MAP_UTILS: {error_msg}")
    editor_state.set_status_message(error_msg, 4)
    return False

def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    print(f"DEBUG MAP_UTILS: load_map_from_json called. Filepath: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        error_msg = f"JSON map file not found or is not a file: '{json_filepath}'"
        print(f"ERROR MAP_UTILS: {error_msg}")
        editor_state.set_status_message(error_msg, 3)
        return False

    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
        print(f"DEBUG MAP_UTILS: Successfully read JSON data from '{json_filepath}'.")

        editor_state.map_name_for_function = data.get("map_name_for_function", "loaded_map_error_name")
        editor_state.map_width_tiles = data.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES)
        editor_state.map_height_tiles = data.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES)
        editor_state.grid_size = data.get("grid_size", ED_CONFIG.DEFAULT_GRID_SIZE)

        bg_color_data = data.get("background_color", ED_CONFIG.DEFAULT_BACKGROUND_COLOR)
        if isinstance(bg_color_data, list) and len(bg_color_data) == 3:
            editor_state.background_color = tuple(bg_color_data) # type: ignore
        else:
            editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
            print(f"Warning MAP_UTILS: Invalid background_color format in JSON, using default. Got: {bg_color_data}")


        editor_state.placed_objects = []
        loaded_placed_objects = data.get("placed_objects", [])
        print(f"DEBUG MAP_UTILS: Loading {len(loaded_placed_objects)} objects from JSON.")
        for i, obj_data in enumerate(loaded_placed_objects):
            asset_key = obj_data.get("asset_editor_key")
            game_type_id_from_json = obj_data.get("game_type_id")
            world_x = obj_data.get("world_x")
            world_y = obj_data.get("world_y")
            override_color_data = obj_data.get("override_color") # Get override_color

            if not all([asset_key, game_type_id_from_json is not None, world_x is not None, world_y is not None]):
                print(f"Warning MAP_UTILS: Loaded object at index {i} has missing core data, skipping: {obj_data}")
                continue

            if asset_key in ED_CONFIG.EDITOR_PALETTE_ASSETS: # Check against current config
                new_obj = {
                    "asset_editor_key": asset_key,
                    "world_x": world_x,
                    "world_y": world_y,
                    "game_type_id": game_type_id_from_json
                }
                if override_color_data and isinstance(override_color_data, list) and len(override_color_data) == 3:
                    new_obj["override_color"] = tuple(override_color_data) # type: ignore
                editor_state.placed_objects.append(new_obj)
            else:
                print(f"Warning MAP_UTILS: Asset key '{asset_key}' from loaded object (JSON type: '{game_type_id_from_json}') "
                      f"not found in current ED_CONFIG.EDITOR_PALETTE_ASSETS. Object at ({world_x},{world_y}) skipped.")

        editor_state.camera_offset_x = data.get("camera_offset_x", 0)
        editor_state.camera_offset_y = data.get("camera_offset_y", 0)
        editor_state.show_grid = data.get("show_grid", True)
        editor_state.color_change_target_info = None # Reset color tool state

        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)

        editor_state.recreate_map_content_surface()
        editor_state.unsaved_changes = False
        success_msg = f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}"
        print(f"DEBUG MAP_UTILS: {success_msg}. unsaved_changes={editor_state.unsaved_changes}, current_map_filename='{editor_state.current_map_filename}'")
        editor_state.set_status_message(success_msg)
        return True

    except json.JSONDecodeError as e:
        error_msg = f"Error: Could not decode JSON from map file '{json_filepath}': {e}"
    except Exception as e:
        error_msg = f"Unexpected error loading map from JSON '{json_filepath}': {e}"
        traceback.print_exc()

    print(f"ERROR MAP_UTILS: {error_msg}")
    editor_state.set_status_message(error_msg, 4)
    return False

def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    print(f"DEBUG MAP_UTILS: export_map_to_game_python_script called. Map func name: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size # Tile Size convenience

    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name not set or is 'untitled_map'. Cannot export .py."
        editor_state.set_status_message(f"Error: {msg}", 3)
        print(f"ERROR MAP_UTILS: {msg}")
        return False

    if not editor_state.current_map_filename:
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
        print(f"Warning MAP_UTILS: current_map_filename was not set, derived as '{editor_state.current_map_filename}' for export.")

    if not ensure_maps_directory_exists():
        msg = "Could not create or access maps directory for .py export."
        editor_state.set_status_message(f"Error: {msg}", 3)
        print(f"ERROR MAP_UTILS: {msg} PY export aborted.")
        return False

    function_name = f"load_map_{editor_state.map_name_for_function}"
    print(f"DEBUG MAP_UTILS: Exporting to function '{function_name}' in file '{editor_state.current_map_filename}'")

    platforms_code_lines = []
    ladders_code_lines = []
    hazards_code_lines = []
    enemy_spawns_code_lines = []
    collectible_spawns_code_lines = []

    default_spawn_tile_x = editor_state.map_width_tiles // 2
    default_spawn_tile_y = editor_state.map_height_tiles // 2
    default_spawn_world_x = default_spawn_tile_x * ts + ts // 2
    default_spawn_world_y = (default_spawn_tile_y + 1) * ts
    player1_spawn_str = f"player1_spawn = ({default_spawn_world_x}, {default_spawn_world_y}) # Default P1 Spawn"

    all_placed_world_rects_for_bounds: List[pygame.Rect] = []
    print(f"DEBUG MAP_UTILS: Processing {len(editor_state.placed_objects)} objects for .py export.")

    for i, obj_data in enumerate(editor_state.placed_objects):
        game_type_id = obj_data.get("game_type_id")
        world_x = obj_data.get("world_x")
        world_y = obj_data.get("world_y")
        asset_editor_key = obj_data.get("asset_editor_key")
        override_color = obj_data.get("override_color")

        if not all([game_type_id, world_x is not None, world_y is not None, asset_editor_key]):
            print(f"Warning MAP_UTILS: Export - Object at index {i} missing data, skipping: {obj_data}")
            continue

        asset_palette_entry = editor_state.assets_palette.get(asset_editor_key)
        if not asset_palette_entry:
            print(f"Warning MAP_UTILS: Asset key '{asset_editor_key}' not in palette. Skipping object export.")
            continue
        
        # Determine object size and default color for export
        obj_w_px, obj_h_px = ts, ts # Default to full tile
        default_color_tuple = getattr(C, 'MAGENTA', (255,0,255)) # Fallback color

        if asset_palette_entry.get("surface_params_dims_color"):
            w, h, c = asset_palette_entry["surface_params_dims_color"]
            obj_w_px, obj_h_px = w, h
            default_color_tuple = c
        elif asset_palette_entry.get("render_mode") == "half_tile":
            # Half tiles' palette image is full tsxts, but actual collision geom is half
            half_type = asset_palette_entry.get("half_type")
            default_color_tuple = asset_palette_entry.get("base_color_tuple", default_color_tuple)
            if half_type in ["left", "right"]: obj_w_px = ts // 2; obj_h_px = ts
            elif half_type in ["top", "bottom"]: obj_w_px = ts; obj_h_px = ts // 2
        elif asset_palette_entry.get("original_size_pixels"): # For GIFs etc.
             obj_w_px, obj_h_px = asset_palette_entry["original_size_pixels"]
        
        current_color_tuple = override_color if override_color else default_color_tuple
        current_color_str = f"({current_color_tuple[0]},{current_color_tuple[1]},{current_color_tuple[2]})" if isinstance(current_color_tuple, (list, tuple)) else str(current_color_tuple)


        # Adjust world_x/y for right_half and bottom_half for Platform constructor
        export_x, export_y = world_x, world_y
        if asset_palette_entry.get("render_mode") == "half_tile":
            half_type = asset_palette_entry.get("half_type")
            if half_type == "right": export_x = world_x + ts // 2
            elif half_type == "bottom": export_y = world_y + ts // 2
        
        current_obj_rect = pygame.Rect(export_x, export_y, obj_w_px, obj_h_px) # Use adjusted coords/dims for bounds
        all_placed_world_rects_for_bounds.append(current_obj_rect)

        # Object type to code generation
        if game_type_id == "platform_wall_gray" or "platform_wall_gray_" in game_type_id and "_half" in game_type_id:
            platforms_code_lines.append(f"    platforms.add(Platform({export_x}, {export_y}, {obj_w_px}, {obj_h_px}, {current_color_str}, platform_type='wall'))")
        elif game_type_id == "platform_ledge_green" or "platform_ledge_green_" in game_type_id and "_half" in game_type_id:
            # Original thin ledge was ts, ts // 4. Half-square ledges are blockier.
            if game_type_id == "platform_ledge_green": # Standard thin ledge
                 platforms_code_lines.append(f"    platforms.add(Platform({export_x}, {export_y}, {obj_w_px}, {obj_h_px}, {current_color_str}, platform_type='ledge'))")
            else: # Half-square blocky ledges
                 platforms_code_lines.append(f"    platforms.add(Platform({export_x}, {export_y}, {obj_w_px}, {obj_h_px}, {current_color_str}, platform_type='ledge'))")

        elif game_type_id == "hazard_lava":
            hazards_code_lines.append(f"    hazards.add(Lava({export_x}, {export_y}, {obj_w_px}, {obj_h_px}, {current_color_str}))")
        elif game_type_id == "player1_spawn":
            spawn_mid_x = world_x + obj_w_px // 2 # Original world_x for spawn point, not export_x
            spawn_bottom_y = world_y + obj_h_px
            player1_spawn_str = f"player1_spawn = ({spawn_mid_x}, {spawn_bottom_y})"
        elif "enemy" in game_type_id:
            specific_enemy_color_id = game_type_id.split('_')[-1] if '_' in game_type_id else "unknown_enemy_color"
            spawn_mid_x = world_x + obj_w_px // 2
            spawn_bottom_y = world_y + obj_h_px
            enemy_spawns_code_lines.append(f"    enemy_spawns_data.append({{'pos': ({spawn_mid_x}, {spawn_bottom_y}), 'patrol': None, 'enemy_color_id': '{specific_enemy_color_id}'}})")
        elif game_type_id == "chest":
            chest_spawn_x_midbottom = world_x + obj_w_px // 2
            chest_spawn_y_midbottom = world_y + obj_h_px
            collectible_spawns_code_lines.append(f"    collectible_spawns_data.append({{'type': 'chest', 'pos': ({chest_spawn_x_midbottom}, {chest_spawn_y_midbottom})}})")
        else:
            # Silently ignore unknown types or tool types for export to game script
            if not game_type_id.startswith("tool_"): # Don't warn for tools
                print(f"Warning MAP_UTILS: Unknown game_type_id '{game_type_id}' for object at ({world_x},{world_y}). Not exported to .py.")


    platforms_code_str = "\n".join(platforms_code_lines)
    ladders_code_str = "\n".join(ladders_code_lines)
    hazards_code_str = "\n".join(hazards_code_lines)
    enemy_spawns_code_str = "\n".join(enemy_spawns_code_lines)
    collectible_spawns_code_str = "\n".join(collectible_spawns_code_lines)
    print(f"DEBUG MAP_UTILS: Generated code lines - Platforms: {len(platforms_code_lines)}, Hazards: {len(hazards_code_lines)}, etc.")

    # Calculate Map Boundaries for Game
    if not all_placed_world_rects_for_bounds:
        print("DEBUG MAP_UTILS: No objects placed, using default map dimensions for export boundaries.")
        map_min_x_content, map_max_x_content = 0, editor_state.get_map_pixel_width()
        map_min_y_content, map_max_y_content = 0, editor_state.get_map_pixel_height()
    else:
        map_min_x_content = min(r.left for r in all_placed_world_rects_for_bounds)
        map_max_x_content = max(r.right for r in all_placed_world_rects_for_bounds)
        map_min_y_content = min(r.top for r in all_placed_world_rects_for_bounds)
        map_max_y_content = max(r.bottom for r in all_placed_world_rects_for_bounds)

    padding_px = C.TILE_SIZE * 2
    game_map_total_width_pixels = int(max(ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, (map_max_x_content - map_min_x_content) + 2 * padding_px))
    game_level_min_y_absolute = int(map_min_y_content - padding_px)
    game_level_max_y_absolute = int(map_max_y_content + padding_px)
    game_main_ground_y_reference = int(map_max_y_content)
    game_main_ground_height_reference = int(C.TILE_SIZE)

    if game_level_min_y_absolute >= game_level_max_y_absolute:
        print(f"Warning MAP_UTILS: Calculated min_y_abs ({game_level_min_y_absolute}) >= max_y_abs ({game_level_max_y_absolute}). Adjusting max_y_abs.")
        game_level_max_y_absolute = game_level_min_y_absolute + C.TILE_SIZE * 5

    print(f"DEBUG MAP_UTILS: Export boundaries - TotalWidthPx: {game_map_total_width_pixels}, MinYAbs: {game_level_min_y_absolute}, MaxYAbs: {game_level_max_y_absolute}")

    script_content = f"""# Level: {editor_state.map_name_for_function}
# Generated by Platformer Level Editor version X.Y.Z # Consider adding a version
import pygame
from tiles import Platform, Ladder, Lava # Ensure all used tile types are imported
import constants as C

LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color}

def {function_name}(initial_screen_width, initial_screen_height):
    \"\"\"
    Loads the '{editor_state.map_name_for_function}' level.
    \"\"\"
    print(f"Loading map: {function_name}...")
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group() # Ensure ladders group is there if you add ladders
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    collectible_spawns_data = []

    {player1_spawn_str}

    # --- Placed Objects ---
{platforms_code_str if platforms_code_str else "    # No platforms placed."}
{ladders_code_str if ladders_code_str else "    # No ladders placed."}
{hazards_code_str if hazards_code_str else "    # No hazards placed."}
{enemy_spawns_code_str if enemy_spawns_code_str else "    # No enemy spawns defined."}
{collectible_spawns_code_str if collectible_spawns_code_str else "    # No collectible spawns defined."}

    # --- Level Dimensions for Game Camera & Boundaries ---
    map_total_width_pixels = {game_map_total_width_pixels}
    level_min_y_absolute = {game_level_min_y_absolute}
    level_max_y_absolute = {game_level_max_y_absolute}
    main_ground_y_reference = {game_main_ground_y_reference}
    main_ground_height_reference = {game_main_ground_height_reference}

    # --- Auto-generated Boundary Walls ---
    _boundary_thickness = C.TILE_SIZE * 2
    _boundary_wall_height = level_max_y_absolute - level_min_y_absolute + (2 * _boundary_thickness)
    _boundary_color = getattr(C, 'DARK_GRAY', (50,50,50)) # Use a defined boundary color

    # Top boundary
    platforms.add(Platform(0, level_min_y_absolute - _boundary_thickness, map_total_width_pixels, _boundary_thickness, _boundary_color, platform_type="boundary_wall_top"))
    # Bottom boundary
    platforms.add(Platform(0, level_max_y_absolute, map_total_width_pixels, _boundary_thickness, _boundary_color, platform_type="boundary_wall_bottom"))
    # Left boundary
    platforms.add(Platform(-_boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_left"))
    # Right boundary
    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_right"))

    print(f"Map '{function_name}' loaded with: {{len(platforms)}} platforms, {{len(ladders)}} ladders, {{len(hazards)}} hazards.")
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR)
"""
    py_filepath = editor_state.current_map_filename
    print(f"DEBUG MAP_UTILS: Final .py script content to write to '{py_filepath}' (first 500 chars):\n{script_content[:500]}...")

    try:
        with open(py_filepath, "w") as f:
            f.write(script_content)
        success_msg = f"Map exported to game script: {os.path.basename(py_filepath)}"
        print(f"DEBUG MAP_UTILS: {success_msg}")
        editor_state.set_status_message(success_msg)
        editor_state.unsaved_changes = False
        print(f"DEBUG MAP_UTILS: unsaved_changes set to False after .py export.")
        return True
    except IOError as e:
        error_msg = f"IOError exporting map to .py '{py_filepath}': {e}"
    except Exception as e:
        error_msg = f"Unexpected error during .py export to '{py_filepath}': {e}"
        traceback.print_exc()

    print(f"ERROR MAP_UTILS: {error_msg}")
    editor_state.set_status_message(error_msg, 4)
    return False