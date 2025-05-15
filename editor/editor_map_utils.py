# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.5 (Added extensive debug prints for saving/loading and export)
Utility functions for map operations in the Level Editor,
including initializing new maps, saving/loading editor-specific
map data (JSON), and exporting maps to game-compatible Python scripts.
"""
import pygame
import sys
import os
import json
import traceback # For detailed error reporting
from typing import Optional, Dict, List, Tuple, Any

# --- Add parent directory to sys.path for editor_config & editor_state if this file is run standalone (unlikely here) ---
# This is more robustly handled in the main editor.py script.
# current_script_path_map_utils = os.path.dirname(os.path.abspath(__file__))
# parent_directory_map_utils = os.path.dirname(current_script_path_map_utils) # This should be 'editor'
# project_root_map_utils = os.path.dirname(parent_directory_map_utils) # This should be 'Platformer'
# if project_root_map_utils not in sys.path:
#     sys.path.insert(0, project_root_map_utils)
# if parent_directory_map_utils not in sys.path: # If editor_config is in 'editor' not project root
#    sys.path.insert(0, parent_directory_map_utils)

import editor_config as ED_CONFIG
from editor_state import EditorState

# constants.py and tiles.py should be accessible from the project root.
# This setup relies on editor.py correctly setting up sys.path.
import constants as C
from tiles import Platform, Ladder, Lava # Assuming these are used in export


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    """
    Initializes the editor_state for a new, empty map.
    Sets up dimensions, clears objects, prepares the map_content_surface.
    """
    print(f"DEBUG MAP_UTILS: init_new_map_state called. Map Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")
    
    clean_map_name = map_name_for_function.lower().replace(" ", "_").replace("-", "_")
    if not clean_map_name:
        clean_map_name = "untitled_map" # Fallback if name becomes empty
        print(f"DEBUG MAP_UTILS: map_name_for_function was empty after cleaning, defaulting to '{clean_map_name}'")
    
    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.placed_objects = []
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
    editor_state.camera_offset_x = 0
    editor_state.camera_offset_y = 0
    editor_state.unsaved_changes = True # A new map inherently has unsaved changes until first save
    
    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
    
    editor_state.recreate_map_content_surface() # This also prints a debug message
    
    print(f"DEBUG MAP_UTILS: Editor state initialized for new map. "
          f"map_name_for_function='{editor_state.map_name_for_function}', "
          f"current_map_filename='{editor_state.current_map_filename}', "
          f"unsaved_changes={editor_state.unsaved_changes}")

def ensure_maps_directory_exists() -> bool:
    """Checks if the MAPS_DIRECTORY exists, creates it if not. Returns success."""
    maps_dir = ED_CONFIG.MAPS_DIRECTORY
    # print(f"DEBUG MAP_UTILS: Checking if maps directory '{maps_dir}' exists.") # Can be verbose
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
    # print(f"DEBUG MAP_UTILS: Maps directory '{maps_dir}' already exists.")
    return True

def save_map_to_json(editor_state: EditorState) -> bool:
    """
    Saves the current editor state to a JSON file for editor reloading.
    Returns True on success, False on failure.
    """
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

        if not all([asset_key, game_id is not None, world_x is not None, world_y is not None]):
             print(f"Warning MAP_UTILS: Object at index {i} has missing data, skipping for JSON: {obj}")
             continue

        s_obj = {
            "asset_editor_key": asset_key,
            "world_x": world_x,
            "world_y": world_y,
            "game_type_id": game_id
        }
        serializable_objects.append(s_obj)

    data_to_save = {
        "map_name_for_function": editor_state.map_name_for_function,
        "map_width_tiles": editor_state.map_width_tiles,
        "map_height_tiles": editor_state.map_height_tiles,
        "grid_size": editor_state.grid_size,
        "background_color": list(editor_state.background_color), # Convert tuple to list for JSON
        "placed_objects": serializable_objects,
        "camera_offset_x": editor_state.camera_offset_x,
        "camera_offset_y": editor_state.camera_offset_y,
        "show_grid": editor_state.show_grid
    }
    print(f"DEBUG MAP_UTILS: Data to save to JSON: {json.dumps(data_to_save, indent=2)}") # Log the data

    try:
        with open(json_filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        success_msg = f"Editor data saved to: {json_filename}"
        print(f"DEBUG MAP_UTILS: {success_msg}")
        editor_state.set_status_message(success_msg)
        # editor_state.unsaved_changes = False # This should be set False AFTER .py export if successful
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
    """
    Loads map data from a JSON file into the editor_state.
    Returns True on success, False on failure.
    """
    print(f"DEBUG MAP_UTILS: load_map_from_json called. Filepath: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        error_msg = f"JSON map file not found or is not a file: '{json_filepath}'"
        print(f"ERROR MAP_UTILS: {error_msg}")
        editor_state.set_status_message(error_msg, 3)
        return False
        
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
        print(f"DEBUG MAP_UTILS: Successfully read JSON data from '{json_filepath}'. Content snapshot: { {k: (type(v) if k != 'placed_objects' else f'{len(v)} items') for k,v in data.items()} }")
        
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
            game_type_id_from_json = obj_data.get("game_type_id") # Get game_type_id from JSON
            world_x = obj_data.get("world_x")
            world_y = obj_data.get("world_y")

            if not all([asset_key, game_type_id_from_json is not None, world_x is not None, world_y is not None]):
                print(f"Warning MAP_UTILS: Loaded object at index {i} has missing core data, skipping: {obj_data}")
                continue

            if asset_key in ED_CONFIG.EDITOR_PALETTE_ASSETS:
                # It's generally safer to trust the game_type_id from the JSON file if it exists,
                # as the config might change. However, for consistency if asset_key is primary link:
                # game_type_id_from_config = ED_CONFIG.EDITOR_PALETTE_ASSETS[asset_key].get("game_type_id", asset_key)
                editor_state.placed_objects.append({
                    "asset_editor_key": asset_key,
                    "world_x": world_x,
                    "world_y": world_y,
                    "game_type_id": game_type_id_from_json # Use the one from the file
                })
            else:
                print(f"Warning MAP_UTILS: Asset key '{asset_key}' from loaded object (JSON type: '{game_type_id_from_json}') "
                      f"not found in current ED_CONFIG.EDITOR_PALETTE_ASSETS. Object at ({world_x},{world_y}) skipped.")

        editor_state.camera_offset_x = data.get("camera_offset_x", 0)
        editor_state.camera_offset_y = data.get("camera_offset_y", 0)
        editor_state.show_grid = data.get("show_grid", True)
        
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
        
        editor_state.recreate_map_content_surface()
        editor_state.unsaved_changes = False # Freshly loaded map has no unsaved changes
        
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
    """
    Generates and saves the Python level script compatible with the main game.
    Returns True on success, False on failure.
    """
    print(f"DEBUG MAP_UTILS: export_map_to_game_python_script called. Map func name: '{editor_state.map_name_for_function}'")
    
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name not set or is 'untitled_map'. Cannot export .py."
        editor_state.set_status_message(f"Error: {msg}", 3)
        print(f"ERROR MAP_UTILS: {msg}")
        return False
        
    if not editor_state.current_map_filename: # Should be set by init_new_map or load_map
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
    ladders_code_lines = [] # Ensure ladders are handled if you add them
    hazards_code_lines = []
    enemy_spawns_code_lines = []
    collectible_spawns_code_lines = []

    # Default player spawn - will be overridden if a player spawn object is placed
    default_spawn_tile_x = editor_state.map_width_tiles // 2
    default_spawn_tile_y = editor_state.map_height_tiles // 2 
    default_spawn_world_x = default_spawn_tile_x * editor_state.grid_size + editor_state.grid_size // 2 # Mid of tile
    default_spawn_world_y = (default_spawn_tile_y + 1) * editor_state.grid_size # Bottom of tile
    player1_spawn_str = f"player1_spawn = ({default_spawn_world_x}, {default_spawn_world_y}) # Default P1 Spawn (midbottom of tile {default_spawn_tile_x},{default_spawn_tile_y})"

    all_placed_world_rects_for_bounds: List[pygame.Rect] = []
    print(f"DEBUG MAP_UTILS: Processing {len(editor_state.placed_objects)} objects for .py export.")

    for i, obj_data in enumerate(editor_state.placed_objects):
        game_type_id = obj_data.get("game_type_id")
        world_x = obj_data.get("world_x")
        world_y = obj_data.get("world_y")
        asset_editor_key = obj_data.get("asset_editor_key")

        if not all([game_type_id, world_x is not None, world_y is not None, asset_editor_key]):
            print(f"Warning MAP_UTILS: Export - Object at index {i} missing data, skipping: {obj_data}")
            continue
        
        asset_config = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(asset_editor_key)
        
        # Determine object size for bounds calculation and export
        obj_width_px = editor_state.grid_size # Default
        obj_height_px = editor_state.grid_size # Default

        if asset_config:
            if "surface_params" in asset_config: # For simple colored rects
                obj_width_px = asset_config["surface_params"][0]
                obj_height_px = asset_config["surface_params"][1]
            elif asset_editor_key in editor_state.assets_palette: # For image-based assets
                palette_asset_data = editor_state.assets_palette[asset_editor_key]
                original_size = palette_asset_data.get("original_size_pixels")
                if original_size and len(original_size) == 2:
                    obj_width_px, obj_height_px = original_size
                else:
                    print(f"Warning MAP_UTILS: Asset '{asset_editor_key}' missing valid 'original_size_pixels' in assets_palette. Using grid_size for export bounds.")
        else:
             print(f"Warning MAP_UTILS: Asset key '{asset_editor_key}' for object (type '{game_type_id}') not in ED_CONFIG. Using grid_size for export bounds.")
        
        current_obj_rect = pygame.Rect(world_x, world_y, obj_width_px, obj_height_px)
        all_placed_world_rects_for_bounds.append(current_obj_rect)

        # --- Object type to code generation ---
        if game_type_id == "platform_wall_gray":
            platforms_code_lines.append(f"    platforms.add(Platform({world_x}, {world_y}, {obj_width_px}, {obj_height_px}, C.GRAY, platform_type='wall'))")
        elif game_type_id == "platform_ledge_green":
            platforms_code_lines.append(f"    platforms.add(Platform({world_x}, {world_y}, {obj_width_px}, {obj_height_px}, C.DARK_GREEN, platform_type='ledge'))")
        elif game_type_id == "hazard_lava": # Assuming Lava takes full tile size (or its original pixel size)
            hazards_code_lines.append(f"    hazards.add(Lava({world_x}, {world_y}, {obj_width_px}, {obj_height_px}, C.ORANGE_RED))")
        elif game_type_id == "player1_spawn":
            # Player spawn point is usually midbottom of the visual representation
            spawn_mid_x = world_x + obj_width_px // 2
            spawn_bottom_y = world_y + obj_height_px 
            player1_spawn_str = f"player1_spawn = ({spawn_mid_x}, {spawn_bottom_y})"
        elif "enemy" in game_type_id: # Generic enemy handling
            specific_enemy_color_id = game_type_id.split('_')[-1] if '_' in game_type_id else "unknown_enemy_color"
            # Enemy spawn point is usually midbottom
            spawn_mid_x = world_x + obj_width_px // 2
            spawn_bottom_y = world_y + obj_height_px
            enemy_spawns_code_lines.append(f"    enemy_spawns_data.append({{'pos': ({spawn_mid_x}, {spawn_bottom_y}), 'patrol': None, 'enemy_color_id': '{specific_enemy_color_id}'}})")
        elif game_type_id == "chest":
            # Chest spawn point is usually midbottom
            chest_spawn_x_midbottom = world_x + obj_width_px // 2
            chest_spawn_y_midbottom = world_y + obj_height_px
            collectible_spawns_code_lines.append(f"    collectible_spawns_data.append({{'type': 'chest', 'pos': ({chest_spawn_x_midbottom}, {chest_spawn_y_midbottom})}})")
        # Add other object types here (e.g., ladders)
        # elif game_type_id == "ladder":
        #     ladders_code_lines.append(f"    ladders.add(Ladder({world_x}, {world_y}, {obj_width_px}, {obj_height_px}))")
        else:
            print(f"Warning MAP_UTILS: Unknown game_type_id '{game_type_id}' for object at ({world_x},{world_y}). Not exported to .py.")


    platforms_code_str = "\n".join(platforms_code_lines)
    ladders_code_str = "\n".join(ladders_code_lines)
    hazards_code_str = "\n".join(hazards_code_lines)
    enemy_spawns_code_str = "\n".join(enemy_spawns_code_lines)
    collectible_spawns_code_str = "\n".join(collectible_spawns_code_lines)
    print(f"DEBUG MAP_UTILS: Generated code lines - Platforms: {len(platforms_code_lines)}, Ladders: {len(ladders_code_lines)}, etc.")

    # --- Calculate Map Boundaries for Game ---
    if not all_placed_world_rects_for_bounds: # Empty map
        print("DEBUG MAP_UTILS: No objects placed, using default map dimensions for export boundaries.")
        map_min_x_content = 0
        map_max_x_content = editor_state.get_map_pixel_width()
        map_min_y_content = 0
        map_max_y_content = editor_state.get_map_pixel_height()
    else:
        map_min_x_content = min(r.left for r in all_placed_world_rects_for_bounds)
        map_max_x_content = max(r.right for r in all_placed_world_rects_for_bounds)
        map_min_y_content = min(r.top for r in all_placed_world_rects_for_bounds)
        map_max_y_content = max(r.bottom for r in all_placed_world_rects_for_bounds)
    
    # Add padding around content for camera movement and player safety
    padding_px = C.TILE_SIZE * 2 
    game_map_total_width_pixels = int(max(ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, (map_max_x_content - map_min_x_content) + 2 * padding_px))
    # Ensure total width covers at least the editor's view of the map or the content width + padding

    # Absolute Y coordinates for the game camera system and boundaries
    game_level_min_y_absolute = int(map_min_y_content - padding_px) 
    game_level_max_y_absolute = int(map_max_y_content + padding_px) 
    
    # Reference for ground, typically where player stands or bottom of lowest platform
    game_main_ground_y_reference = int(map_max_y_content) 
    game_main_ground_height_reference = int(C.TILE_SIZE) # Typical tile height

    if game_level_min_y_absolute >= game_level_max_y_absolute :
        print(f"Warning MAP_UTILS: Calculated min_y_abs ({game_level_min_y_absolute}) >= max_y_abs ({game_level_max_y_absolute}) for map '{editor_state.map_name_for_function}'. Adjusting max_y_abs.")
        game_level_max_y_absolute = game_level_min_y_absolute + C.TILE_SIZE * 5 # Ensure some height

    print(f"DEBUG MAP_UTILS: Export boundaries - TotalWidthPx: {game_map_total_width_pixels}, MinYAbs: {game_level_min_y_absolute}, MaxYAbs: {game_level_max_y_absolute}")

    script_content = f"""# Level: {editor_state.map_name_for_function}
# Generated by Platformer Level Editor on {pygame.time.get_ticks()}
import pygame
from tiles import Platform, Ladder, Lava # Ensure all used tile types are imported by game
import constants as C

# Optional: Define level-specific background color if your game supports it
LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color}

def {function_name}(initial_screen_width, initial_screen_height):
    \"\"\"
    Loads the '{editor_state.map_name_for_function}' level.
    Generated by the level editor.
    \"\"\"
    print(f"Loading map: {function_name}...") # Game-side log
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
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
    level_min_y_absolute = {game_level_min_y_absolute} # Top-most Y coordinate for camera/content
    level_max_y_absolute = {game_level_max_y_absolute} # Bottom-most Y coordinate for camera/content (e.g., death plane below this)
    
    main_ground_y_reference = {game_main_ground_y_reference} # Y-value of the main 'floor' surface
    main_ground_height_reference = {game_main_ground_height_reference} # Height of typical ground tiles

    # --- Auto-generated Boundary Walls (Invisible in game unless styled) ---
    # These ensure entities cannot go outside the defined level space.
    _boundary_thickness = C.TILE_SIZE * 2 # Make them thick enough
    _boundary_wall_height = level_max_y_absolute - level_min_y_absolute + (2 * _boundary_thickness) # Span slightly beyond min/max_y

    # Top boundary (ceiling) - place its bottom edge at level_min_y_absolute
    platforms.add(Platform(0, level_min_y_absolute - _boundary_thickness, map_total_width_pixels, _boundary_thickness, C.DARK_GRAY, platform_type="boundary_wall_top"))
    # Bottom boundary (floor/kill plane) - place its top edge at level_max_y_absolute
    platforms.add(Platform(0, level_max_y_absolute, map_total_width_pixels, _boundary_thickness, C.DARK_GRAY, platform_type="boundary_wall_bottom"))
    # Left boundary wall
    platforms.add(Platform(-_boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, C.DARK_GRAY, platform_type="boundary_wall_left"))
    # Right boundary wall
    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, C.DARK_GRAY, platform_type="boundary_wall_right"))

    print(f"Map '{function_name}' loaded with: {{len(platforms)}} platforms, {{len(ladders)}} ladders, {{len(hazards)}} hazards.") # Game-side log
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR) # Return background color
"""
    py_filepath = editor_state.current_map_filename 
    print(f"DEBUG MAP_UTILS: Final .py script content to write to '{py_filepath}':\n{script_content[:500]}...") # Log start of content

    try:
        with open(py_filepath, "w") as f:
            f.write(script_content)
        success_msg = f"Map exported to game script: {os.path.basename(py_filepath)}"
        print(f"DEBUG MAP_UTILS: {success_msg}")
        editor_state.set_status_message(success_msg)
        editor_state.unsaved_changes = False # Crucial: set unsaved to false AFTER successful .py export
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