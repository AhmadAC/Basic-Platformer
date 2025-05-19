# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
VERSION 2.1.0 
"""
import sys
import os
import json
import traceback
from typing import Optional, Dict, List, Tuple, Any
import logging

# Editor-specific config and state
import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history # For getting snapshots


try:
    import constants as C
except ImportError as e_proj_imp:
    print(f"EDITOR_MAP_UTILS CRITICAL Error importing project constants: {e_proj_imp}")
    class FallbackConstants: # Minimal fallback
        TILE_SIZE = 40; GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0)
        DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230); MAGENTA=(255,0,255)
        EDITOR_SCREEN_INITIAL_WIDTH=1000
    C = FallbackConstants()

logger = logging.getLogger(__name__)


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    logger.info(f"Initializing new map state. Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")
    clean_map_name = map_name_for_function.strip().lower().replace(" ", "_").replace("-", "_")
    if not clean_map_name: clean_map_name = "untitled_map"; logger.warning("map_name empty, defaulting to 'untitled_map'")

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.grid_size = ED_CONFIG.BASE_GRID_SIZE
    editor_state.placed_objects = []
    editor_state.asset_specific_variables.clear()
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE
    editor_state.camera_offset_x = 0.0; editor_state.camera_offset_y = 0.0
    editor_state.zoom_level = 1.0
    editor_state.unsaved_changes = True

    # File paths remain for JSON, but PY export changes format
    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)

    editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename) # Path to the .py data file
    editor_state.current_json_filename = os.path.join(maps_abs_dir, json_filename)

    editor_state.undo_stack.clear(); editor_state.redo_stack.clear()
    logger.info(f"Editor state initialized for new map: '{editor_state.map_name_for_function}'. JSON: '{editor_state.current_json_filename}'")


def ensure_maps_directory_exists() -> bool:
    maps_dir_to_check = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_dir_to_check):
        editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_dir_to_check = os.path.join(editor_parent_dir, maps_dir_to_check)

    if not os.path.exists(maps_dir_to_check):
        logger.info(f"Maps directory '{maps_dir_to_check}' does not exist. Attempting to create.")
        try:
            os.makedirs(maps_dir_to_check); logger.info(f"Created maps directory: {maps_dir_to_check}"); return True
        except OSError as e:
            logger.error(f"Error creating maps directory {maps_dir_to_check}: {e}", exc_info=True); return False
    elif not os.path.isdir(maps_dir_to_check):
        logger.error(f"Path '{maps_dir_to_check}' exists but is not a directory."); return False
    return True


def save_map_to_json(editor_state: EditorState) -> bool:
    # This function remains largely the same as it deals with editor-specific JSON.
    logger.info(f"Saving map to JSON. Map name from state: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set or 'untitled_map'. Cannot save JSON."); return False
    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. JSON save aborted."); return False

    json_filepath = editor_state.current_json_filename
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)

    if not json_filepath or os.path.dirname(os.path.normpath(json_filepath)) != os.path.normpath(maps_abs_dir) or \
       os.path.basename(json_filepath) != (editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
        json_filepath = os.path.join(maps_abs_dir, json_filename)
        editor_state.current_json_filename = json_filepath
        logger.warning(f"JSON filepath re-derived for save: '{json_filepath}'")
    
    logger.debug(f"Attempting to save JSON to: '{json_filepath}'")
    data_to_save = editor_history.get_map_snapshot(editor_state)

    try:
        with open(json_filepath, "w") as f: json.dump(data_to_save, f, indent=4)
        editor_state.unsaved_changes = False # Assuming export_map_py will also be called or this is the main save
        logger.info(f"Editor data saved to: {os.path.basename(json_filepath)}")
        return True
    except Exception as e:
        logger.error(f"Error saving map to JSON '{json_filepath}': {e}", exc_info=True); return False


def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    # This function remains largely the same.
    logger.info(f"Loading map from JSON: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        logger.error(f"JSON map file not found: '{json_filepath}'"); return False
    try:
        with open(json_filepath, 'r') as f: data_snapshot = json.load(f)
        editor_history.restore_map_from_snapshot(editor_state, data_snapshot)

        maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
        if not os.path.isabs(maps_abs_dir):
            editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)
        
        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename_for_state) # Path for .py data file
        editor_state.current_json_filename = json_filepath
        editor_state.unsaved_changes = False
        logger.info(f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}.")
        return True
    except Exception as e:
        logger.error(f"Error loading map from JSON '{json_filepath}': {e}", exc_info=True); return False


def _merge_rect_objects_to_data(objects_raw: List[Dict[str, Any]], object_category_name: str) -> List[Dict[str, Any]]:
    """
    Merges adjacent rectangular objects of the same type and color into larger rectangles.
    Returns a list of dictionaries representing the merged objects, suitable for PySide6 game elements.
    object_category_name is e.g., "platform", "ladder", "hazard_lava"
    """
    if not objects_raw:
        logger.debug(f"No raw objects provided for merging (category: {object_category_name}).")
        return []

    working_objects: List[Dict[str, Any]] = []
    for obj_orig in objects_raw:
        obj = obj_orig.copy() # Create a mutable copy
        obj['merged'] = False
        # Ensure essential keys exist with defaults
        obj.setdefault('x', 0.0)
        obj.setdefault('y', 0.0)
        obj.setdefault('w', float(ED_CONFIG.BASE_GRID_SIZE))
        obj.setdefault('h', float(ED_CONFIG.BASE_GRID_SIZE))
        
        # Color handling: ensure it's a tuple of 3 ints
        color_val = obj.get('color', C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255))
        if isinstance(color_val, list) and len(color_val) == 3: obj['color'] = tuple(color_val)
        elif not (isinstance(color_val, tuple) and len(color_val) == 3):
             obj['color'] = C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255) # Fallback color
        
        if object_category_name == "platform": obj.setdefault('type', 'generic') # Specific to platforms
        working_objects.append(obj)

    # Horizontal merge
    horizontal_strips: List[Dict[str, Any]] = []
    # Sort by type (if platform), color, y, height, then x for consistent merging
    key_func_h = lambda p: (str(p.get('type', '')) if object_category_name == "platform" else "",
                            str(p['color']), p['y'], p['h'], p['x'])
    sorted_h = sorted(working_objects, key=key_func_h)

    for i, p_base in enumerate(sorted_h):
        if p_base['merged']: continue
        current_strip = p_base.copy(); p_base['merged'] = True
        for j in range(i + 1, len(sorted_h)):
            p_next = sorted_h[j]
            if p_next['merged']: continue
            
            # Type check only for platforms
            type_match = True
            if object_category_name == "platform":
                type_match = (str(p_next.get('type', '')) == str(current_strip.get('type', '')))

            if type_match and str(p_next['color']) == str(current_strip['color']) and \
               abs(p_next['y'] - current_strip['y']) < 1e-3 and \
               abs(p_next['h'] - current_strip['h']) < 1e-3 and \
               abs(p_next['x'] - (current_strip['x'] + current_strip['w'])) < 1e-3: # Check adjacency
                current_strip['w'] += p_next['w']
                p_next['merged'] = True
            elif abs(p_next['y'] - current_strip['y']) >= 1e-3 or \
                 abs(p_next['h'] - current_strip['h']) >= 1e-3 or \
                 (object_category_name == "platform" and str(p_next.get('type', '')) != str(current_strip.get('type', ''))) or \
                 str(p_next['color']) != str(current_strip['color']):
                break # Break if different row, height, type, or color
        horizontal_strips.append(current_strip)

    # Vertical merge
    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips] # Copy again for vertical merge
    for strip in strips_to_merge: strip['merged'] = False # Reset merged flag

    key_func_v = lambda s: (str(s.get('type', '')) if object_category_name == "platform" else "",
                            str(s['color']), s['x'], s['w'], s['y'])
    sorted_v = sorted(strips_to_merge, key=key_func_v)

    for i, s_base in enumerate(sorted_v):
        if s_base['merged']: continue
        current_block = s_base.copy(); s_base['merged'] = True
        for j in range(i + 1, len(sorted_v)):
            s_next = sorted_v[j]
            if s_next['merged']: continue
            
            type_match_v = True
            if object_category_name == "platform":
                type_match_v = (str(s_next.get('type', '')) == str(current_block.get('type', '')))

            if type_match_v and str(s_next['color']) == str(current_block['color']) and \
               abs(s_next['x'] - current_block['x']) < 1e-3 and \
               abs(s_next['w'] - current_block['w']) < 1e-3 and \
               abs(s_next['y'] - (current_block['y'] + current_block['h'])) < 1e-3:
                current_block['h'] += s_next['h']
                s_next['merged'] = True
            elif abs(s_next['x'] - current_block['x']) >= 1e-3 or \
                 abs(s_next['w'] - current_block['w']) >= 1e-3 or \
                 (object_category_name == "platform" and str(s_next.get('type', '')) != str(current_block.get('type', ''))) or \
                 str(s_next['color']) != str(current_block['color']):
                break
        # Remove the 'merged' key before adding to final list
        current_block.pop('merged', None)
        final_blocks_data.append(current_block)
    
    logger.debug(f"Merged {len(objects_raw)} raw {object_category_name} objects into {len(final_blocks_data)} final blocks.")
    return final_blocks_data


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map data. Map name: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set. Cannot export .py data file."); return False
    
    py_filepath_to_use = editor_state.current_map_filename
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)

    if not py_filepath_to_use or os.path.dirname(os.path.normpath(py_filepath_to_use)) != os.path.normpath(maps_abs_dir) or \
       os.path.basename(py_filepath_to_use) != (editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION):
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        py_filepath_to_use = os.path.join(maps_abs_dir, py_filename)
        editor_state.current_map_filename = py_filepath_to_use
        logger.warning(f"PY data filepath for export re-derived: '{py_filepath_to_use}'")

    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. PY data export aborted."); return False

    function_name_str_for_map_file = f"get_map_data_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{function_name_str_for_map_file}' in file '{py_filepath_to_use}'")

    # --- Data Collection and Preparation ---
    platforms_data_raw: List[Dict[str, Any]] = []
    ladders_data_raw: List[Dict[str, Any]] = []
    hazards_data_raw: List[Dict[str, Any]] = [] # Specifically for lava, etc.
    
    enemy_spawns_data_export: List[Dict[str, Any]] = []
    collectible_spawns_data_export: List[Dict[str, Any]] = []
    statue_spawns_data_export: List[Dict[str, Any]] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts // 2
    default_spawn_world_y = (editor_state.map_height_tiles - 1) * ts 
    player1_spawn_pos_export: Tuple[float, float] = (default_spawn_world_x, default_spawn_world_y)
    player1_spawn_props_export: Dict[str, Any] = {}

    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []
    lava_occupied_coords = set() # To prevent platforms on lava

    for obj_data in editor_state.placed_objects:
        game_id = obj_data.get("game_type_id")
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        if game_id == "hazard_lava" and wx is not None and wy is not None:
            lava_occupied_coords.add((wx, wy))

    for obj_data in editor_state.placed_objects:
        game_id = str(obj_data.get("game_type_id", "unknown"))
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        asset_key = str(obj_data.get("asset_editor_key", ""))
        override_color_tuple = obj_data.get("override_color") 
        obj_props = obj_data.get("properties", {})
        if not all([game_id != "unknown", wx is not None, wy is not None, asset_key != ""]): continue
        
        asset_entry = editor_state.assets_palette.get(asset_key)
        if not asset_entry: logger.warning(f"Asset key '{asset_key}' not in palette for export. Skipping."); continue

        obj_w, obj_h = float(ts), float(ts)
        default_color_from_asset_tuple = getattr(C, 'MAGENTA', (255,0,255))
        if asset_entry.get("surface_params"):
            dims_color_tuple = asset_entry["surface_params"]
            if isinstance(dims_color_tuple, tuple) and len(dims_color_tuple) == 3:
                w_param, h_param, c_param = dims_color_tuple
                obj_w, obj_h = float(w_param), float(h_param); default_color_from_asset_tuple = c_param
        elif asset_entry.get("render_mode") == "half_tile":
            default_color_from_asset_tuple = asset_entry.get("base_color_tuple", default_color_from_asset_tuple)
            ht = asset_entry.get("half_type")
            if ht in ["left", "right"]: obj_w = ts / 2.0
            elif ht in ["top", "bottom"]: obj_h = ts / 2.0
        elif asset_entry.get("original_size_pixels"):
             orig_w, orig_h = asset_entry["original_size_pixels"]
             obj_w, obj_h = float(orig_w), float(orig_h)
        
        final_color_for_export = tuple(override_color_tuple) if isinstance(override_color_tuple, list) else \
                                 (override_color_tuple if isinstance(override_color_tuple, tuple) else default_color_from_asset_tuple)
        export_x, export_y = float(wx), float(wy)
        if asset_entry.get("render_mode") == "half_tile":
            ht = asset_entry.get("half_type")
            if ht == "right": export_x = wx + ts / 2.0
            elif ht == "bottom": export_y = wy + ts / 2.0
        
        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})
        
        is_platform_type = any(kw in game_id for kw in ["platform_wall", "platform_ledge"])
        is_ladder_type = "ladder" in game_id # Assuming ladders also use 'game_type_id'

        if is_platform_type:
            if (wx, wy) in lava_occupied_coords: logger.warning(f"Skipping platform export for '{game_id}' at ({wx},{wy}) due to lava overlap."); continue
            plat_type_str = 'ledge' if "ledge" in game_id else ('wall' if "wall" in game_id else 'generic')
            platforms_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': plat_type_str})
        elif is_ladder_type:
            ladders_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export})
        elif game_id == "hazard_lava":
            hazards_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': 'lava'})
        elif game_id == "player1_spawn":
            player1_spawn_pos_export = (export_x + obj_w / 2.0, export_y + obj_h)
            player1_spawn_props_export = obj_props
        elif "enemy" in game_id:
            enemy_color_id_str = game_id.split('_')[-1]
            spawn_mid_x, spawn_mid_bottom_y = export_x + obj_w / 2.0, export_y + obj_h
            enemy_spawns_data_export.append({'pos': (spawn_mid_x, spawn_mid_bottom_y), 'patrol': None, 'enemy_color_id': enemy_color_id_str, 'properties': obj_props})
        elif game_id == "chest":
            spawn_mid_x, spawn_mid_bottom_y = export_x + obj_w / 2.0, export_y + obj_h
            collectible_spawns_data_export.append({'type': 'chest', 'pos': (spawn_mid_x, spawn_mid_bottom_y), 'properties': obj_props})
        elif game_id.startswith("object_stone_"):
            statue_id_str = f"{asset_key}_{int(wx)}_{int(wy)}" # Unique ID for statue
            statue_center_x_exp, statue_center_y_exp = export_x + obj_w / 2.0, export_y + obj_h / 2.0
            statue_spawns_data_export.append({'id': statue_id_str, 'pos': (statue_center_x_exp, statue_center_y_exp), 'properties': obj_props})
    
    # Merge tile-like objects
    merged_platforms_data = _merge_rect_objects_to_data(platforms_data_raw, "platform")
    merged_ladders_data = _merge_rect_objects_to_data(ladders_data_raw, "ladder")
    merged_hazards_data = _merge_rect_objects_to_data(hazards_data_raw, "hazard_lava") # Assuming only lava for now

    # Calculate map boundaries and dimensions (same logic as before)
    map_min_x_content = 0.0; map_max_x_content = float(editor_state.get_map_pixel_width())
    map_min_y_content = 0.0; map_max_y_content = float(editor_state.get_map_pixel_height())
    if all_placed_objects_rect_data_for_bounds:
        map_min_x_content = min(r['x'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_x_content = max(r['x'] + r['width'] for r in all_placed_objects_rect_data_for_bounds)
        map_min_y_content = min(r['y'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_y_content = max(r['y'] + r['height'] for r in all_placed_objects_rect_data_for_bounds)

    padding_px = float(getattr(C, 'TILE_SIZE', 40) * 2)
    editor_initial_width_fallback = float(getattr(C, 'EDITOR_SCREEN_INITIAL_WIDTH', 1000))
    game_map_total_width_pixels_val = max(editor_initial_width_fallback, map_max_x_content - map_min_x_content + 2 * padding_px)
    if map_max_x_content + padding_px > game_map_total_width_pixels_val: game_map_total_width_pixels_val = map_max_x_content + padding_px
    if map_min_x_content < 0: game_map_total_width_pixels_val = max(game_map_total_width_pixels_val, map_max_x_content - map_min_x_content + padding_px)
    game_map_total_width_pixels_val = float(int(game_map_total_width_pixels_val))

    game_level_min_y_absolute_val = float(int(map_min_y_content - padding_px))
    game_level_max_y_absolute_val = float(int(map_max_y_content))
    main_ground_y_reference_val = game_level_max_y_absolute_val
    main_ground_height_reference_val = float(getattr(C, 'TILE_SIZE', 40))

    # Add boundary walls data
    _boundary_thickness_val = float(getattr(C, 'TILE_SIZE', 40))
    _boundary_wall_height_val = (game_level_max_y_absolute_val - game_level_min_y_absolute_val) + (2 * _boundary_thickness_val)
    _boundary_wall_height_val = float(int(max(_boundary_thickness_val * 2, _boundary_wall_height_val)))
    _boundary_color_tuple = getattr(C, 'DARK_GRAY', (50,50,50))
    effective_min_x_for_bounds_val = float(int(min(0.0, map_min_x_content)))
    boundary_full_width_val = game_map_total_width_pixels_val - effective_min_x_for_bounds_val
    boundary_full_width_val = float(int(boundary_full_width_val))
    filler_wall_y_val = game_level_min_y_absolute_val - _boundary_thickness_val
    filler_wall_y_val = float(int(filler_wall_y_val))

    boundary_platforms_data = [
        {'x': effective_min_x_for_bounds_val, 'y': game_level_min_y_absolute_val - _boundary_thickness_val, 'w': boundary_full_width_val, 'h': _boundary_thickness_val, 'color': _boundary_color_tuple, 'type': 'boundary_wall_top'},
        {'x': effective_min_x_for_bounds_val, 'y': game_level_max_y_absolute_val, 'w': boundary_full_width_val, 'h': _boundary_thickness_val, 'color': _boundary_color_tuple, 'type': 'boundary_wall_bottom'},
        {'x': effective_min_x_for_bounds_val - _boundary_thickness_val, 'y': filler_wall_y_val, 'w': _boundary_thickness_val, 'h': _boundary_wall_height_val, 'color': _boundary_color_tuple, 'type': 'boundary_wall_left'},
        {'x': game_map_total_width_pixels_val, 'y': filler_wall_y_val, 'w': _boundary_thickness_val, 'h': _boundary_wall_height_val, 'color': _boundary_color_tuple, 'type': 'boundary_wall_right'},
    ]
    # Add boundary platforms to the main platforms list
    merged_platforms_data.extend(boundary_platforms_data)

    # Prepare the data dictionary to be written to the .py file
    map_export_data = {
        "map_name": editor_state.map_name_for_function,
        "background_color": editor_state.background_color,
        "player1_spawn_pos": player1_spawn_pos_export,
        "player1_spawn_props": player1_spawn_props_export,
        "platforms": merged_platforms_data,
        "ladders": merged_ladders_data,
        "hazards": merged_hazards_data, # e.g., [{'type': 'lava', 'x': ..., 'y': ..., 'w': ..., 'h': ..., 'color': ...}]
        "enemy_spawns": enemy_spawns_data_export,
        "collectible_spawns": collectible_spawns_data_export,
        "statue_spawns": statue_spawns_data_export,
        "dimensions": {
            "map_total_width_pixels": game_map_total_width_pixels_val,
            "level_min_y_absolute": game_level_min_y_absolute_val,
            "level_max_y_absolute": game_level_max_y_absolute_val,
            "main_ground_y_reference": main_ground_y_reference_val,
            "main_ground_height_reference": main_ground_height_reference_val,
        }
    }

    # Generate the Python script content
    # We use repr() for robustly writing Python literals
    script_content = f"""\
# Level Data: {editor_state.map_name_for_function}
# Generated by Platformer Level Editor

# This file contains data structures that can be loaded by the game engine.
# It does not instantiate game objects directly.

def {function_name_str_for_map_file}():
    level_data = {{
        "map_name": {repr(map_export_data["map_name"])},
        "background_color": {repr(map_export_data["background_color"])},
        "player1_spawn_pos": {repr(map_export_data["player1_spawn_pos"])},
        "player1_spawn_props": {repr(map_export_data["player1_spawn_props"])},
        "platforms_data": {repr(map_export_data["platforms"])},
        "ladders_data": {repr(map_export_data["ladders"])},
        "hazards_data": {repr(map_export_data["hazards"])},
        "enemy_spawns_data": {repr(map_export_data["enemy_spawns"])},
        "collectible_spawns_data": {repr(map_export_data["collectible_spawns"])},
        "statue_spawns_data": {repr(map_export_data["statue_spawns"])},
        "dimensions_data": {repr(map_export_data["dimensions"])}
    }}
    return level_data

if __name__ == '__main__':
    # Example of how to load and print the data
    data = {function_name_str_for_map_file}()
    import json
    print(json.dumps(data, indent=4))
"""
    try:
        with open(py_filepath_to_use, "w") as f: f.write(script_content)
        logger.info(f"Map data exported to game script: {os.path.basename(py_filepath_to_use)}")
        # If JSON also saved, unsaved_changes should be false. If only exporting, it depends.
        # Typically, after exporting, the current state is considered "saved" or "exported".
        # editor_state.unsaved_changes = False # If export counts as a save action
        return True
    except Exception as e:
        logger.error(f"Error exporting map data to .py '{py_filepath_to_use}': {e}", exc_info=True); return False


def delete_map_files(editor_state: EditorState, json_filepath_to_delete: str) -> bool:
    # This function remains largely the same, as it deletes based on file names.
    logger.info(f"Attempting to delete map files. Base JSON path: {json_filepath_to_delete}")
    if not json_filepath_to_delete.endswith(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        logger.error(f"Invalid file type for deletion: {json_filepath_to_delete}."); return False

    map_name_base = os.path.splitext(os.path.basename(json_filepath_to_delete))[0]
    py_filename_to_delete = map_name_base + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    py_filepath_to_delete = os.path.join(os.path.dirname(json_filepath_to_delete), py_filename_to_delete)
    
    deleted_json, deleted_py = False, False
    try:
        if os.path.exists(json_filepath_to_delete): os.remove(json_filepath_to_delete); deleted_json = True; logger.info(f"Deleted: {json_filepath_to_delete}")
        else: logger.warning(f"Not found for deletion (JSON): {json_filepath_to_delete}")
        if os.path.exists(py_filepath_to_delete): os.remove(py_filepath_to_delete); deleted_py = True; logger.info(f"Deleted: {py_filepath_to_delete}")
        else: logger.warning(f"Not found for deletion (PY): {py_filepath_to_delete}")
        
        if deleted_json or deleted_py :
            logger.info(f"Map '{map_name_base}' files deletion process complete. JSON deleted: {deleted_json}, PY deleted: {deleted_py}")
            return True
        else: 
            logger.info(f"Map '{map_name_base}' files not found for deletion.")
            return True 
    except OSError as e:
        logger.error(f"Error deleting map files for '{map_name_base}': {e}", exc_info=True); return False