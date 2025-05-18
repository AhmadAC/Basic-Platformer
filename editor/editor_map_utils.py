# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
## version 1.0.3 (Improved rename logic for consistency)
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
import logging

# --- Project-Specific Imports ---
# Assuming editor_config and editor_state are in the same 'editor' package directory
import editor_config as ED_CONFIG # Contains MAPS_DIRECTORY, TILE_SIZE, default colors, etc.
from editor_state import EditorState   # Holds the current state of the map being edited

# Assuming constants.py and tiles.py are in the parent directory (project root)
# The sys.path manipulation in editor.py should handle making these importable.
try:
    import constants as C # For TILE_SIZE, colors, etc., used in export
    from tiles import Platform, Ladder, Lava # Game-specific tile classes for export
except ImportError as e_proj_imp:
    print(f"EDITOR_MAP_UTILS CRITICAL Error importing project modules (constants/tiles): {e_proj_imp}")
    # Fallback constants if needed, or allow to fail if these are essential
    class FallbackConstants: TILE_SIZE = 32; GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0); DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230)
    C = FallbackConstants()
    class Platform: pass
    class Ladder: pass
    class Lava: pass
# --- End Project-Specific Imports ---

logger = logging.getLogger(__name__)


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    """
    Initializes the editor_state for a new, empty map with the given parameters.
    Sets unsaved_changes to True.

    Args:
        editor_state (EditorState): The editor's state object to modify.
        map_name_for_function (str): The base name for the map (e.g., "my_level").
        map_width_tiles (int): Width of the new map in tiles.
        map_height_tiles (int): Height of the new map in tiles.
    """
    logger.info(f"Initializing new map state. Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")

    # map_name_for_function should already be cleaned by the caller (editor_handlers_menu)
    clean_map_name = map_name_for_function
    if not clean_map_name: # Should not happen if caller validates, but safeguard
        clean_map_name = "untitled_map"
        logger.warning(f"map_name_for_function was empty during init, defaulting to '{clean_map_name}'")

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.placed_objects = [] # Clear any existing objects
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
    editor_state.camera_offset_x = 0
    editor_state.camera_offset_y = 0
    editor_state.unsaved_changes = True # New map is inherently unsaved until first save/export

    # Derive filenames based on the (potentially cleaned) map name
    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION

    # ED_CONFIG.MAPS_DIRECTORY should be an absolute path from constants.py
    editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
    editor_state.current_json_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_filename)

    editor_state.recreate_map_content_surface() # Create the drawing surface for the map

    logger.info(f"Editor state initialized for new map. "
                f"map_name_for_function='{editor_state.map_name_for_function}', "
                f"current_map_filename (py)='{editor_state.current_map_filename}', "
                f"current_json_filename='{editor_state.current_json_filename}', "
                f"unsaved_changes={editor_state.unsaved_changes}")


def ensure_maps_directory_exists() -> bool:
    """
    Checks if the MAPS_DIRECTORY (defined in editor_config, sourced from C.MAPS_DIR)
    exists. If not, attempts to create it.

    Returns:
        bool: True if the directory exists or was successfully created, False otherwise.
    """
    maps_dir = ED_CONFIG.MAPS_DIRECTORY # This is an absolute path
    if not os.path.exists(maps_dir):
        logger.info(f"Maps directory '{maps_dir}' does not exist. Attempting to create.")
        try:
            os.makedirs(maps_dir)
            logger.info(f"Successfully created maps directory: {maps_dir}")
            return True
        except OSError as e:
            logger.error(f"Error creating maps directory {maps_dir}: {e}", exc_info=True)
            return False
    return True


def save_map_to_json(editor_state: EditorState) -> bool:
    """
    Saves the current map data from editor_state to a JSON file.
    The filename is derived from editor_state.map_name_for_function.
    Uses ED_CONFIG.MAPS_DIRECTORY for the save location.

    Args:
        editor_state (EditorState): The current state of the editor.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    logger.info(f"Saving map to JSON. Map name from state: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot save JSON."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(msg)
        return False

    if not ensure_maps_directory_exists(): # Uses ED_CONFIG.MAPS_DIRECTORY
        msg = f"Could not create or access maps directory: {ED_CONFIG.MAPS_DIRECTORY}"
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(f"{msg} JSON save aborted.")
        return False

    # Use the map_name_for_function from editor_state to construct filename
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    json_filepath = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_filename) # ED_CONFIG.MAPS_DIRECTORY is absolute
    logger.debug(f"Attempting to save JSON to: '{json_filepath}' using map name '{editor_state.map_name_for_function}'")

    serializable_objects = []
    for i, obj in enumerate(editor_state.placed_objects):
        asset_key = obj.get("asset_editor_key")
        game_id = obj.get("game_type_id")
        world_x = obj.get("world_x")
        world_y = obj.get("world_y")
        override_color = obj.get("override_color")

        if not all([asset_key, game_id is not None, world_x is not None, world_y is not None]):
             logger.warning(f"Object at index {i} has missing data, skipping for JSON: {obj}")
             continue

        s_obj = {
            "asset_editor_key": asset_key,
            "world_x": world_x,
            "world_y": world_y,
            "game_type_id": game_id
        }
        if override_color: # Only add if it exists and is not None
            s_obj["override_color"] = list(override_color) # Ensure it's a list for JSON

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
    logger.debug(f"Data to save (first object example): {serializable_objects[0] if serializable_objects else 'No objects'}")

    try:
        with open(json_filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        success_msg = f"Editor data saved to: {json_filename}"
        logger.info(success_msg)
        editor_state.set_status_message(success_msg)
        # NOTE: save_map_to_json itself does not set unsaved_changes to False.
        # This is typically handled by export_map_to_game_python_script or a "Save All" operation.
        editor_state.current_json_filename = json_filepath # Update the current JSON filename state
        return True
    except IOError as e:
        error_msg = f"IOError saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc() # Keep for detailed error

    editor_state.set_status_message(error_msg, 4)
    return False


def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    """
    Loads map data from a specified JSON file into the editor_state.
    Updates editor_state.map_name_for_function, current_map_filename (for .py),
    and current_json_filename.

    Args:
        editor_state (EditorState): The editor's state object to populate.
        json_filepath (str): The absolute path to the JSON map file to load.

    Returns:
        bool: True if loading was successful, False otherwise.
    """
    logger.info(f"Loading map from JSON: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        error_msg = f"JSON map file not found or is not a file: '{json_filepath}'"
        logger.error(error_msg)
        editor_state.set_status_message(error_msg, 3)
        return False

    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
        logger.debug(f"Successfully read JSON data from '{json_filepath}'.")

        # Crucially, set editor_state.map_name_for_function from the JSON file's content
        loaded_map_name = data.get("map_name_for_function")
        if not loaded_map_name:
            # Fallback: derive from filename if missing in JSON (less ideal, but robust)
            loaded_map_name = os.path.splitext(os.path.basename(json_filepath))[0]
            logger.warning(f"'map_name_for_function' missing in JSON, derived as '{loaded_map_name}' from filename.")
        editor_state.map_name_for_function = loaded_map_name # This is the definitive name now

        editor_state.map_width_tiles = data.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES)
        editor_state.map_height_tiles = data.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES)
        editor_state.grid_size = data.get("grid_size", ED_CONFIG.DEFAULT_GRID_SIZE) # Ensure grid size is loaded

        bg_color_data = data.get("background_color", ED_CONFIG.DEFAULT_BACKGROUND_COLOR)
        if isinstance(bg_color_data, list) and len(bg_color_data) == 3:
            editor_state.background_color = tuple(bg_color_data) # type: ignore
        else:
            editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR # Fallback
            logger.warning(f"Invalid background_color format in JSON, using default. Got: {bg_color_data}")

        temp_placed_objects_from_json: List[Dict[str, Any]] = []
        loaded_placed_objects_data = data.get("placed_objects", [])
        logger.debug(f"Loading {len(loaded_placed_objects_data)} objects from JSON.")
        for i, obj_data in enumerate(loaded_placed_objects_data):
            asset_key = obj_data.get("asset_editor_key")
            game_type_id_from_json = obj_data.get("game_type_id") # This is the "true" game type ID
            world_x = obj_data.get("world_x")
            world_y = obj_data.get("world_y")
            override_color_data = obj_data.get("override_color")

            if not all([asset_key, game_type_id_from_json is not None, world_x is not None, world_y is not None]):
                logger.warning(f"Loaded object at index {i} has missing core data, skipping: {obj_data}")
                continue

            # Check if the asset_editor_key still exists in the current editor palette
            if asset_key in ED_CONFIG.EDITOR_PALETTE_ASSETS:
                new_obj = {
                    "asset_editor_key": asset_key,
                    "world_x": world_x,
                    "world_y": world_y,
                    "game_type_id": game_type_id_from_json # Store the game_type_id from JSON
                }
                if override_color_data and isinstance(override_color_data, list) and len(override_color_data) == 3:
                    new_obj["override_color"] = tuple(override_color_data) # type: ignore
                temp_placed_objects_from_json.append(new_obj)
            else:
                logger.warning(f"Asset key '{asset_key}' from loaded object (JSON type: '{game_type_id_from_json}') "
                               f"not found in current ED_CONFIG.EDITOR_PALETTE_ASSETS. Object at ({world_x},{world_y}) skipped.")

        # Auto-correction logic (e.g., lava under platforms)
        corrected_objects: List[Dict[str, Any]] = []
        lava_coords_to_check = set() # Store (x,y) of lava tiles
        corrections_made = False

        # First pass: identify all lava tile locations
        for obj in temp_placed_objects_from_json:
            if obj.get("game_type_id") == "hazard_lava": # Assuming "hazard_lava" is the game_type_id
                if obj.get("world_x") is not None and obj.get("world_y") is not None:
                    lava_coords_to_check.add((obj["world_x"], obj["world_y"]))
        logger.debug(f"Auto-correction: Found {len(lava_coords_to_check)} lava coordinates for checking: {lava_coords_to_check}")

        # Second pass: check platforms against lava locations
        for obj in temp_placed_objects_from_json:
            obj_wx, obj_wy = obj.get("world_x"), obj.get("world_y")
            obj_game_type_id = obj.get("game_type_id", "") # The true game type ID from JSON

            # Define which game_type_ids are considered solid platforms that shouldn't be on lava
            solid_platform_game_types = {
                "platform_wall_gray", "platform_ledge_green",
                # Add half-tile platform game_type_ids if they are solid
                "platform_wall_gray_left_half", "platform_wall_gray_right_half",
                "platform_wall_gray_top_half", "platform_wall_gray_bottom_half",
                "platform_ledge_green_left_half", "platform_ledge_green_right_half",
                "platform_ledge_green_top_half", "platform_ledge_green_bottom_half"
            }

            if obj_game_type_id in solid_platform_game_types:
                if obj_wx is not None and obj_wy is not None and (obj_wx, obj_wy) in lava_coords_to_check:
                    logger.info(f"Auto-correcting: Removing solid platform '{obj.get('asset_editor_key')}' (Type: {obj_game_type_id}) "
                                f"at lava location ({obj_wx},{obj_wy}).")
                    corrections_made = True # Mark that a correction was made
                    continue # Skip adding this conflicting platform
            corrected_objects.append(obj) # Add if not a conflicting platform or not a platform at all

        editor_state.placed_objects = corrected_objects
        if corrections_made:
            editor_state.unsaved_changes = True # If corrections were made, mark as unsaved
            editor_state.set_status_message("Map auto-corrected: Removed solid platforms under lava.", 4.0)
            logger.info("Map auto-corrected due to lava/platform conflict. Unsaved changes flag set.")

        editor_state.camera_offset_x = data.get("camera_offset_x", 0)
        editor_state.camera_offset_y = data.get("camera_offset_y", 0)
        editor_state.show_grid = data.get("show_grid", True)

        # Set current_map_filename (for .py) and current_json_filename based on the loaded map_name_for_function
        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename_for_state)
        editor_state.current_json_filename = json_filepath # Store the path of the JSON it was loaded from

        editor_state.recreate_map_content_surface()
        if not corrections_made: # Only set to False if no corrections were made during load
            editor_state.unsaved_changes = False # Map loaded, no unsaved changes yet

        success_msg = f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}."
        if corrections_made: success_msg += " (Auto-corrected)"

        logger.info(f"{success_msg}. map_name_for_function='{editor_state.map_name_for_function}', "
                    f"current_map_filename (py)='{editor_state.current_map_filename}', "
                    f"current_json_filename='{editor_state.current_json_filename}', "
                    f"unsaved_changes={editor_state.unsaved_changes}")
        editor_state.set_status_message(success_msg)
        return True

    except json.JSONDecodeError as e:
        error_msg = f"Error: Could not decode JSON from map file '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error loading map from JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc() # Keep for detailed error

    editor_state.set_status_message(error_msg, 4)
    return False


def _merge_rect_objects(objects_raw: List[Dict[str, Any]], class_name_for_export: str, sprite_group_name: str) -> List[str]:
    """
    Merges adjacent rectangular objects of the same type and color into larger rectangles.
    Used to optimize platform/hazard generation in exported Python scripts.

    Args:
        objects_raw (List[Dict[str, Any]]): List of object dictionaries.
            Each dict must contain 'x', 'y', 'w', 'h', 'color', and optionally 'type'.
        class_name_for_export (str): The Python class name for these objects (e.g., "Platform").
        sprite_group_name (str): The name of the sprite group to add to (e.g., "platforms").

    Returns:
        List[str]: A list of Python code lines for creating the merged objects.
    """
    if not objects_raw:
        return [f"    # No {class_name_for_export.lower()}s placed."]

    # Ensure all objects have a 'merged' flag and a 'type' if relevant (for Platforms)
    working_objects = [obj.copy() for obj in objects_raw]
    for obj in working_objects:
        obj['merged'] = False
        if class_name_for_export == "Platform" and 'type' not in obj:
            obj['type'] = 'generic' # Default platform type if not specified

    # --- Phase 1: Merge Horizontally ---
    horizontal_strips: List[Dict[str, Any]] = []
    # Sort primarily by type, color, y, h, then x to group potential horizontal merges
    key_func_horizontal = lambda p: (p.get('type', ''), p['color'], p['y'], p['h'], p['x'])
    
    sorted_objects_for_horizontal_merge = sorted(working_objects, key=key_func_horizontal)
    
    for i, p_base in enumerate(sorted_objects_for_horizontal_merge):
        if p_base['merged']:
            continue
        current_strip = p_base.copy()
        p_base['merged'] = True
        
        for j in range(i + 1, len(sorted_objects_for_horizontal_merge)):
            p_next = sorted_objects_for_horizontal_merge[j]
            if p_next['merged']:
                continue
            
            # Check for merge conditions
            if (p_next.get('type', '') == current_strip.get('type', '') and
                p_next['color'] == current_strip['color'] and
                p_next['y'] == current_strip['y'] and
                p_next['h'] == current_strip['h'] and
                p_next['x'] == current_strip['x'] + current_strip['w']): # Adjacent horizontally
                current_strip['w'] += p_next['w'] # Extend width
                p_next['merged'] = True
            # If properties change or not adjacent, break inner loop for this p_base
            elif (p_next.get('type', '') != current_strip.get('type', '') or
                  p_next['color'] != current_strip['color'] or
                  p_next['y'] != current_strip['y'] or
                  p_next['h'] != current_strip['h']):
                  break # Different kind of object or different row
            elif p_next['x'] != current_strip['x'] + current_strip['w']:
                break # Not adjacent (gap or already past)
        horizontal_strips.append(current_strip)

    # --- Phase 2: Merge Vertically (using the horizontal strips) ---
    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips] # Work with copies
    for strip in strips_to_merge:
        strip['merged'] = False # Reset merged flag for vertical pass

    # Sort primarily by type, color, x, w, then y to group potential vertical merges
    key_func_vertical = lambda s: (s.get('type', ''), s['color'], s['x'], s['w'], s['y'])
    sorted_strips_for_vertical_merge = sorted(strips_to_merge, key=key_func_vertical)
    
    for i, s_base in enumerate(sorted_strips_for_vertical_merge):
        if s_base['merged']:
            continue
        current_block = s_base.copy()
        s_base['merged'] = True
        
        for j in range(i + 1, len(sorted_strips_for_vertical_merge)):
            s_next = sorted_strips_for_vertical_merge[j]
            if s_next['merged']:
                continue
            # Check for merge conditions
            if (s_next.get('type', '') == current_block.get('type', '') and
                s_next['color'] == current_block['color'] and
                s_next['x'] == current_block['x'] and
                s_next['w'] == current_block['w'] and
                s_next['y'] == current_block['y'] + current_block['h']): # Adjacent vertically
                current_block['h'] += s_next['h'] # Extend height
                s_next['merged'] = True
            # If properties change or not adjacent, break inner loop
            elif (s_next.get('type', '') != current_block.get('type', '') or
                  s_next['color'] != current_block['color'] or
                  s_next['x'] != current_block['x'] or
                  s_next['w'] != current_block['w']):
                  break # Different kind of object or different column
            elif s_next['y'] != current_block['y'] + current_block['h']:
                break # Not adjacent (gap or already past)
        final_blocks_data.append(current_block)
    
    # --- Generate Code Lines ---
    code_lines = []
    if not final_blocks_data:
         return [f"    # No {class_name_for_export.lower()} objects placed (empty after merge attempt)."]

    for block in final_blocks_data:
        # Platform class specifically uses platform_type
        if class_name_for_export == "Platform":
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {block['color']}, platform_type='{block['type']}'))")
        else: # For other rect-based objects like Lava
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {block['color']}))")
            
    if not code_lines: # Should be redundant given the check for final_blocks_data
        return [f"    # No {class_name_for_export.lower()}s placed."]
    return code_lines


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    """
    Exports the current map data from editor_state to a game-compatible Python script.
    The script will contain a function `load_map_<map_name>()` that recreates the level.
    Filename is derived from editor_state.map_name_for_function.
    Uses ED_CONFIG.MAPS_DIRECTORY for save location.

    Args:
        editor_state (EditorState): The current state of the editor.

    Returns:
        bool: True if export was successful, False otherwise.
    """
    logger.info(f"Exporting map. Map name from state: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size # Tile size from editor state

    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot export .py."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(msg)
        return False

    # Use editor_state.current_map_filename if set (it should be by init_new_map or load_map)
    # This ensures consistency, especially after a rename operation.
    py_filepath_to_use = editor_state.current_map_filename
    if not py_filepath_to_use or \
       os.path.basename(py_filepath_to_use) != (editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION):
        # This is a safeguard or if the state wasn't perfectly synced.
        logger.warning(f"PY filepath for export re-derived. State name: '{editor_state.map_name_for_function}', "
                       f"Stored py_filepath: '{py_filepath_to_use}'.")
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        py_filepath_to_use = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename) # ED_CONFIG.MAPS_DIRECTORY is absolute
        editor_state.current_map_filename = py_filepath_to_use # Ensure state is updated

    if not ensure_maps_directory_exists(): # Uses ED_CONFIG.MAPS_DIRECTORY
        msg = f"Could not create or access maps directory: {ED_CONFIG.MAPS_DIRECTORY} for .py export."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(f"{msg} PY export aborted.")
        return False

    # function_name in the Python script is derived from the current map_name_for_function
    function_name = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{function_name}' in file '{py_filepath_to_use}'")

    # --- Prepare data for export ---
    platform_objects_raw: List[Dict[str, Any]] = [] # For platforms that can be merged
    hazards_code_lines: List[str] = []
    enemy_spawns_code_lines: List[str] = []
    collectible_spawns_code_lines: List[str] = []

    # Default player spawn if not placed; use midbottom for consistency with game entities
    default_spawn_tile_x = editor_state.map_width_tiles // 2
    default_spawn_tile_y = editor_state.map_height_tiles - 2 # A bit above bottom
    default_spawn_world_x = default_spawn_tile_x * ts + ts // 2 # Mid-point of the tile
    default_spawn_world_y = (default_spawn_tile_y + 1) * ts     # Bottom of the tile
    player1_spawn_str = f"player1_spawn = ({default_spawn_world_x}, {default_spawn_world_y}) # Default P1 Spawn"

    all_placed_world_rects_for_bounds: List[pygame.Rect] = [] # For calculating content bounds
    logger.debug(f"Processing {len(editor_state.placed_objects)} objects for .py export.")

    # Pre-scan for lava locations to handle platform overlaps correctly
    lava_occupied_coords = set()
    for obj_data_lava_check in editor_state.placed_objects:
        if obj_data_lava_check.get("game_type_id") == "hazard_lava":
            world_x = obj_data_lava_check.get("world_x")
            world_y = obj_data_lava_check.get("world_y")
            if world_x is not None and world_y is not None:
                lava_occupied_coords.add((world_x, world_y))
    logger.debug(f"Export: Identified {len(lava_occupied_coords)} lava-occupied coordinates for platform check: {lava_occupied_coords}")


    for i, obj_data in enumerate(editor_state.placed_objects):
        game_type_id = obj_data.get("game_type_id") # This is the true game type ID
        world_x = obj_data.get("world_x")
        world_y = obj_data.get("world_y")
        asset_editor_key = obj_data.get("asset_editor_key") # Key used in editor palette
        override_color = obj_data.get("override_color")     # Tuple (R,G,B) or None

        if not all([game_type_id, world_x is not None, world_y is not None, asset_editor_key]):
             logger.warning(f"Export - Object at index {i} missing data, skipping: {obj_data}")
             continue

        asset_palette_entry = editor_state.assets_palette.get(asset_editor_key)
        if not asset_palette_entry:
            logger.warning(f"Asset key '{asset_editor_key}' not in palette. Skipping object export for obj: {obj_data}")
            continue

        # Determine object dimensions and default color from palette definition
        obj_w_px, obj_h_px = ts, ts # Default to grid size
        
        # General default color, used if asset has no inherent color (like a GIF) or if specific defaults aren't met
        default_color_tuple_for_this_asset = getattr(C, 'MAGENTA', (255,0,255)) 

        if asset_palette_entry.get("surface_params_dims_color"): # For basic colored rects
            w, h, c = asset_palette_entry["surface_params_dims_color"]
            obj_w_px, obj_h_px = w, h
            default_color_tuple_for_this_asset = c
        elif asset_palette_entry.get("render_mode") == "half_tile": # For half-tiles
            half_type = asset_palette_entry.get("half_type")
            default_color_tuple_for_this_asset = asset_palette_entry.get("base_color_tuple", default_color_tuple_for_this_asset)
            if half_type in ["left", "right"]: obj_w_px = ts // 2; obj_h_px = ts
            elif half_type in ["top", "bottom"]: obj_w_px = ts; obj_h_px = ts // 2
        elif asset_palette_entry.get("original_size_pixels"): # For image-based assets (like the new lava GIF)
             obj_w_px, obj_h_px = asset_palette_entry["original_size_pixels"]
             # For GIF based assets, if no override_color is set, specific game_type_id defaults will be used below.
        # Note: If none of these, it defaults to ts x ts, and default_color_tuple_for_this_asset remains MAGENTA.

        # Determine the color to export (override or specific default or general default)
        final_color_tuple_for_export = None
        if override_color: # User explicitly set a color for this instance
            final_color_tuple_for_export = override_color
        elif game_type_id == "hazard_lava": # Specific default for lava if no override
            final_color_tuple_for_export = getattr(C, 'ORANGE_RED', (255,69,0))
        else: # General default from palette (if applicable) or magenta
            final_color_tuple_for_export = default_color_tuple_for_this_asset
        
        current_color_str = f"({final_color_tuple_for_export[0]},{final_color_tuple_for_export[1]},{final_color_tuple_for_export[2]})" if isinstance(final_color_tuple_for_export, (list, tuple)) and len(final_color_tuple_for_export)==3 else str(getattr(C, 'MAGENTA', (255,0,255)))


        # Adjust spawn position for half-tiles if necessary
        export_x, export_y = world_x, world_y
        if asset_palette_entry.get("render_mode") == "half_tile":
            half_type = asset_palette_entry.get("half_type")
            if half_type == "right": export_x = world_x + ts // 2
            elif half_type == "bottom": export_y = world_y + ts // 2
        
        # Store rect for calculating overall map content boundaries
        current_obj_rect = pygame.Rect(export_x, export_y, obj_w_px, obj_h_px)
        all_placed_world_rects_for_bounds.append(current_obj_rect)

        # --- Categorize and generate code based on game_type_id ---
        platform_game_type_keywords = {"platform_wall_gray", "platform_ledge_green"}
        is_platform_type = any(keyword in game_type_id for keyword in platform_game_type_keywords)

        if is_platform_type and (world_x, world_y) in lava_occupied_coords:
            logger.info(f"Export: Skipping platform '{game_type_id}' at ({world_x},{world_y}) because it's occupied by lava.")
            continue 

        if "platform_wall_gray" in game_type_id or "platform_ledge_green" in game_type_id:
            platform_export_type = 'ledge' if "ledge" in game_type_id else 'wall'
            platform_objects_raw.append({
                'x': export_x, 'y': export_y, 'w': obj_w_px, 'h': obj_h_px,
                'color': current_color_str, 'type': platform_export_type
            })
        elif game_type_id == "hazard_lava":
            hazards_code_lines.append(f"    hazards.add(Lava({export_x}, {export_y}, {obj_w_px}, {obj_h_px}, {current_color_str}))")
        elif game_type_id == "player1_spawn":
            spawn_mid_x = export_x + obj_w_px // 2
            spawn_bottom_y = export_y + obj_h_px
            player1_spawn_str = f"player1_spawn = ({spawn_mid_x}, {spawn_bottom_y})"
        elif "enemy" in game_type_id: 
            specific_enemy_color_id = game_type_id.split('_')[-1] if '_' in game_type_id else "unknown_enemy_color"
            spawn_mid_x = export_x + obj_w_px // 2
            spawn_bottom_y = export_y + obj_h_px
            enemy_spawns_code_lines.append(f"    enemy_spawns_data.append({{'pos': ({spawn_mid_x}, {spawn_bottom_y}), 'patrol': None, 'enemy_color_id': '{specific_enemy_color_id}'}})")
        elif game_type_id == "chest":
            chest_spawn_x_midbottom = export_x + obj_w_px // 2
            chest_spawn_y_midbottom = export_y + obj_h_px
            collectible_spawns_code_lines.append(f"    collectible_spawns_data.append({{'type': 'chest', 'pos': ({chest_spawn_x_midbottom}, {chest_spawn_y_midbottom})}})")
        else:
            if not game_type_id.startswith("tool_"): 
                logger.warning(f"Unknown game_type_id '{game_type_id}' for object at ({world_x},{world_y}). Not exported to .py.")


    # Merge platforms and generate code lines
    platforms_code_lines = _merge_rect_objects(platform_objects_raw, "Platform", "platforms")
    ladders_code_lines = [f"    # No ladders placed."]# Example if you add ladders

    platforms_code_str = "\n".join(platforms_code_lines)
    ladders_code_str = "\n".join(ladders_code_lines)
    hazards_code_str = "\n".join(hazards_code_lines) if hazards_code_lines else "    # No hazards placed."
    enemy_spawns_code_str = "\n".join(enemy_spawns_code_lines) if enemy_spawns_code_lines else "    # No enemy spawns defined."
    collectible_spawns_code_str = "\n".join(collectible_spawns_code_lines) if collectible_spawns_code_lines else "    # No collectible spawns defined."

    logger.debug(f"Generated code lines - Platforms (merged): {len(platforms_code_lines)}, Hazards: {len(hazards_code_lines)}, Enemies: {len(enemy_spawns_code_lines)}, Collectibles: {len(collectible_spawns_code_lines)}")


    # --- Calculate level boundaries for camera and physics ---
    map_min_x_content, map_max_x_content = 0, 0
    map_min_y_content, map_max_y_content = 0, 0

    if not all_placed_world_rects_for_bounds:
        logger.debug("No objects placed, using editor map dimensions for export boundaries.")
        map_min_x_content = 0
        map_max_x_content = editor_state.get_map_pixel_width()
        map_min_y_content = 0
        map_max_y_content = editor_state.get_map_pixel_height()
    else:
        map_min_x_content = min(r.left for r in all_placed_world_rects_for_bounds)
        map_max_x_content = max(r.right for r in all_placed_world_rects_for_bounds)
        map_min_y_content = min(r.top for r in all_placed_world_rects_for_bounds)
        map_max_y_content = max(r.bottom for r in all_placed_world_rects_for_bounds)

    # Define padding around content for camera and boundaries
    padding_px = C.TILE_SIZE * 2 # Two tiles padding
    
    # Determine total map width for the game
    content_span_x = map_max_x_content - map_min_x_content
    game_map_total_width_pixels = int(max(ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, content_span_x + 2 * padding_px))
    if map_max_x_content + padding_px > game_map_total_width_pixels:
         game_map_total_width_pixels = int(map_max_x_content + padding_px)
    if map_min_x_content > 0 : 
        if game_map_total_width_pixels < map_max_x_content + padding_px:
             game_map_total_width_pixels = int(map_max_x_content + padding_px)
    elif game_map_total_width_pixels < map_max_x_content : 
        game_map_total_width_pixels = int(map_max_x_content + padding_px)


    # Define absolute Y boundaries for the level (camera limits, kill planes)
    game_level_min_y_absolute = int(map_min_y_content - padding_px) # Sky limit
    game_level_max_y_absolute = int(map_max_y_content) # Bottom of lowest content, becomes kill plane start
    game_main_ground_y_reference = int(map_max_y_content) # Reference for where "ground" is considered
    game_main_ground_height_reference = int(C.TILE_SIZE) # Thickness of the ground boundary

    if game_level_min_y_absolute >= game_level_max_y_absolute:
        logger.warning(f"Calculated min_y_abs ({game_level_min_y_absolute}) >= max_y_abs ({game_level_max_y_absolute}). Adjusting max_y_abs.")
        game_level_max_y_absolute = game_level_min_y_absolute + C.TILE_SIZE * 5 # Ensure some height

    logger.debug(f"Export boundaries - map_min_x_content: {map_min_x_content}, map_max_x_content: {map_max_x_content}")
    logger.debug(f"Export boundaries - TotalWidthPx: {game_map_total_width_pixels}, MinYAbs: {game_level_min_y_absolute}, MaxYAbs: {game_level_max_y_absolute}")

    # --- Construct the Python script content ---
    script_content_parts = [
        f"# Level: {editor_state.map_name_for_function}",
        "# Generated by Platformer Level Editor (Optimized Export)",
        "import pygame",
        "from tiles import Platform, Ladder, Lava", # Ensure these are correct
        "import constants as C", # Game constants
        "",
        f"LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color}", # Export BG color
        "",
        f"def {function_name}(initial_screen_width, initial_screen_height):",
        f"    \"\"\"",
        f"    Loads the '{editor_state.map_name_for_function}' level.",
        f"    \"\"\"",
        f"    print(f\"Loading map: {function_name}...\")",
        "    platforms = pygame.sprite.Group()",
        "    ladders = pygame.sprite.Group()",
        "    hazards = pygame.sprite.Group()",
        "    enemy_spawns_data = []",
        "    collectible_spawns_data = []",
        "",
        f"    {player1_spawn_str}", # Player 1 spawn position
        "",
        "    # --- Placed Objects (merged where possible) ---",
        platforms_code_str,
        ladders_code_str,
        hazards_code_str,
        enemy_spawns_code_str,
        collectible_spawns_code_str,
        "",
        "    # --- Level Dimensions for Game Camera & Boundaries ---",
        f"    map_total_width_pixels = {game_map_total_width_pixels}",
        f"    level_min_y_absolute = {game_level_min_y_absolute}",
        f"    level_max_y_absolute = {game_level_max_y_absolute}",
        f"    main_ground_y_reference = {game_main_ground_y_reference}", 
        f"    main_ground_height_reference = {game_main_ground_height_reference}", 
        "",
        "    _boundary_thickness = C.TILE_SIZE * 2", 
        "    _boundary_wall_height = level_max_y_absolute - level_min_y_absolute + (2 * _boundary_thickness)",
        "    _boundary_color = getattr(C, 'DARK_GRAY', (50,50,50))", 
        "",
    ]
    
    filler_wall_x_start = map_max_x_content 
    filler_wall_width = game_map_total_width_pixels - filler_wall_x_start
    
    if filler_wall_width > 0:
        filler_wall_y_expr_str = "level_min_y_absolute - _boundary_thickness" 
        filler_wall_height_expr_str = "_boundary_wall_height" 
        script_content_parts.extend([
            "    # Filler wall on the right to ensure no empty background padding",
            f"    platforms.add(Platform({filler_wall_x_start}, {filler_wall_y_expr_str}, {filler_wall_width}, {filler_wall_height_expr_str}, _boundary_color, platform_type='wall'))"
        ])
        log_calculated_boundary_thickness = C.TILE_SIZE * 2
        log_calculated_filler_wall_y = game_level_min_y_absolute - log_calculated_boundary_thickness
        log_calculated_filler_wall_height = (game_level_max_y_absolute - game_level_min_y_absolute) + (2 * log_calculated_boundary_thickness)
        log_boundary_color_value_for_debug = getattr(C, 'DARK_GRAY', (50,50,50))
        logger.debug(f"Code for right-side filler wall generated: x={filler_wall_x_start}, y_expr='{filler_wall_y_expr_str}', w={filler_wall_width}, h_expr='{filler_wall_height_expr_str}', color_var_name='_boundary_color'")
        logger.debug(f"Approximate calculated values for filler wall (for logging ref): y_val_approx={log_calculated_filler_wall_y}, h_val_approx={log_calculated_filler_wall_height}, color_val_approx={log_boundary_color_value_for_debug}")
    
    script_content_parts.extend([
        "",
        "    # Boundary platforms (these define the absolute edges of the level area)",
        "    # Top boundary (ceiling)",
        f"    platforms.add(Platform(0, level_min_y_absolute - _boundary_thickness, map_total_width_pixels, _boundary_thickness, _boundary_color, platform_type=\"boundary_wall_top\"))",
        "    # Bottom boundary (floor/kill plane)",
        f"    platforms.add(Platform(0, level_max_y_absolute, map_total_width_pixels, _boundary_thickness, _boundary_color, platform_type=\"boundary_wall_bottom\"))",
        "    # Left boundary",
        f"    platforms.add(Platform(-_boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type=\"boundary_wall_left\"))",
        "    # Right boundary (placed at the very edge of map_total_width_pixels)",
        f"    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type=\"boundary_wall_right\"))",
        "",
        f"    print(f\"Map '{function_name}' loaded with: {{len(platforms)}} platforms, {{len(ladders)}} ladders, {{len(hazards)}} hazards.\")",
        "    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,",
        "            player1_spawn,",
        "            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,",
        "            main_ground_y_reference, main_ground_height_reference,",
        "            LEVEL_SPECIFIC_BACKGROUND_COLOR)", 
        ])

    script_content = "\n".join(script_content_parts)
    logger.debug(f"Final .py script content (first 500 chars):\n{script_content[:500]}...")

    try:
        with open(py_filepath_to_use, "w") as f:
            f.write(script_content)
        success_msg = f"Map exported to game script: {os.path.basename(py_filepath_to_use)}"
        logger.info(success_msg)
        editor_state.set_status_message(success_msg)
        editor_state.unsaved_changes = False 
        logger.debug(f"unsaved_changes set to False after .py export to '{py_filepath_to_use}'.")
        return True
    except IOError as e:
        error_msg = f"IOError exporting map to .py '{py_filepath_to_use}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error during .py export to '{py_filepath_to_use}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc() 

    editor_state.set_status_message(error_msg, 4)
    return False


def delete_map_files(editor_state: EditorState, json_filepath_to_delete: str) -> bool:
    """
    Deletes both the JSON editor save file and its corresponding Python game level script.
    Args:
        editor_state (EditorState): The current editor state (for status messages).
        json_filepath_to_delete (str): Absolute path to the .json file to delete.
    Returns:
        bool: True if relevant files were deleted or didn't exist, False if an error occurred during deletion.
    """
    logger.info(f"Attempting to delete map files. Base JSON path: {json_filepath_to_delete}")
    if not json_filepath_to_delete.endswith(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        msg = f"Invalid file type for deletion: {json_filepath_to_delete}. Expected {ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION}"
        logger.error(msg)
        editor_state.set_status_message(msg, 3)
        return False

    map_name_base = os.path.splitext(os.path.basename(json_filepath_to_delete))[0]
    py_filename_to_delete = map_name_base + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    py_filepath_to_delete = os.path.join(os.path.dirname(json_filepath_to_delete), py_filename_to_delete)

    deleted_json = False
    deleted_py = False
    action_performed_json = False 
    action_performed_py = False   

    try:
        if os.path.exists(json_filepath_to_delete):
            action_performed_json = True
            os.remove(json_filepath_to_delete)
            logger.info(f"Deleted editor map file: {json_filepath_to_delete}")
            deleted_json = True
        else:
            logger.warning(f"Editor map file not found for deletion: {json_filepath_to_delete}")
    except OSError as e:
        action_performed_json = True 
        msg = f"Error deleting editor map file '{json_filepath_to_delete}': {e}"
        logger.error(msg, exc_info=True)
        editor_state.set_status_message(msg, 4) 

    try:
        if os.path.exists(py_filepath_to_delete):
            action_performed_py = True
            os.remove(py_filepath_to_delete)
            logger.info(f"Deleted game level file: {py_filepath_to_delete}")
            deleted_py = True
        else:
            logger.warning(f"Game level file not found for deletion: {py_filepath_to_delete}")
    except OSError as e:
        action_performed_py = True 
        msg = f"Error deleting game level file '{py_filepath_to_delete}': {e}"
        logger.error(msg, exc_info=True)
        editor_state.set_status_message(msg, 4) 


    final_status_message = ""
    operation_successful = False

    if deleted_json and deleted_py:
        final_status_message = f"Map '{map_name_base}' JSON and PY files deleted."
        operation_successful = True
    elif deleted_json: 
        final_status_message = f"Map '{map_name_base}' JSON file deleted. PY not found or failed to delete."
        operation_successful = True 
    elif deleted_py: 
         final_status_message = f"Map '{map_name_base}' PY file deleted. JSON not found or failed to delete."
         operation_successful = True 
    elif not action_performed_json and not action_performed_py: 
        final_status_message = f"Map '{map_name_base}' files not found."
        operation_successful = True 
    elif (action_performed_json and not deleted_json) or \
         (action_performed_py and not deleted_py): 
        final_status_message = f"Failed to delete one or more files for map '{map_name_base}'. Check logs."
        operation_successful = False 
    else: 
        final_status_message = f"Deletion status unclear for map '{map_name_base}'. Check logs."
        operation_successful = False

    editor_state.set_status_message(final_status_message, 3 if operation_successful else 4)
    return operation_successful