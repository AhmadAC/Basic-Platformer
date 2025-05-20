# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
VERSION 2.2.1
"""
import sys
import os
import json
import traceback
from typing import Optional, Dict, List, Tuple, Any
import logging

# Editor-specific config and state
from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_history


try:
    import constants as C
except ImportError as e_proj_imp:
    print(f"EDITOR_MAP_UTILS CRITICAL Error importing project constants: {e_proj_imp}")
    class FallbackConstants: # Minimal fallback
        TILE_SIZE = 40; GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0)
        DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230); MAGENTA=(255,0,255)
        EDITOR_SCREEN_INITIAL_WIDTH=1000
        MAPS_DIR = "maps"
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

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)
        logger.debug(f"Derived absolute maps directory: {maps_abs_dir}")

    editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename)
    editor_state.current_json_filename = os.path.join(maps_abs_dir, json_filename)

    editor_state.undo_stack.clear(); editor_state.redo_stack.clear()
    logger.info(f"Editor state initialized for new map: '{editor_state.map_name_for_function}'. PY: '{editor_state.current_map_filename}', JSON: '{editor_state.current_json_filename}'")


def ensure_maps_directory_exists() -> bool:
    maps_dir_to_check = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_dir_to_check):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_dir_to_check = os.path.join(project_root, maps_dir_to_check)

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
    logger.info(f"Saving map to JSON. Map name from state: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set or 'untitled_map'. Cannot save JSON."); return False
    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. JSON save aborted."); return False

    json_filepath = editor_state.current_json_filename
    
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)

    expected_json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    expected_json_filepath = os.path.join(maps_abs_dir, expected_json_filename)

    if os.path.normpath(json_filepath) != os.path.normpath(expected_json_filepath):
        json_filepath = expected_json_filepath
        editor_state.current_json_filename = json_filepath
        logger.warning(f"JSON filepath re-derived for save: '{json_filepath}'")
    
    logger.debug(f"Attempting to save JSON to: '{json_filepath}'")
    data_to_save = editor_history.get_map_snapshot(editor_state)

    try:
        with open(json_filepath, "w") as f: json.dump(data_to_save, f, indent=4)
        logger.info(f"Editor data saved to: {os.path.basename(json_filepath)}")
        # Consider setting unsaved_changes to True if PY export is the primary "save"
        # For now, JSON save is a distinct step.
        return True
    except Exception as e:
        logger.error(f"Error saving map to JSON '{json_filepath}': {e}", exc_info=True); return False


def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    logger.info(f"Loading map from JSON: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        logger.error(f"JSON map file not found: '{json_filepath}'"); return False
    try:
        with open(json_filepath, 'r') as f: data_snapshot = json.load(f)
        editor_history.restore_map_from_snapshot(editor_state, data_snapshot)

        maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
        if not os.path.isabs(maps_abs_dir):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(project_root, maps_abs_dir)
        
        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename_for_state)
        editor_state.current_json_filename = json_filepath
        editor_state.unsaved_changes = False
        logger.info(f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}.")
        return True
    except Exception as e:
        logger.error(f"Error loading map from JSON '{json_filepath}': {e}", exc_info=True); return False


def _merge_rect_objects_to_data(objects_raw: List[Dict[str, Any]], object_category_name: str) -> List[Dict[str, Any]]:
    if not objects_raw:
        logger.debug(f"No raw objects provided for merging (category: {object_category_name}).")
        return []

    working_objects: List[Dict[str, Any]] = []
    for obj_orig in objects_raw:
        obj = obj_orig.copy()
        obj['merged'] = False
        obj.setdefault('x', 0.0)
        obj.setdefault('y', 0.0)
        obj.setdefault('w', float(ED_CONFIG.BASE_GRID_SIZE))
        obj.setdefault('h', float(ED_CONFIG.BASE_GRID_SIZE))
        
        color_val = obj.get('color', getattr(C, 'MAGENTA', (255,0,255)))
        if isinstance(color_val, list) and len(color_val) == 3: obj['color'] = tuple(color_val)
        elif not (isinstance(color_val, tuple) and len(color_val) == 3):
             obj['color'] = getattr(C, 'MAGENTA', (255,0,255))
        
        # Ensure 'type' is present for consistent sorting and processing
        obj.setdefault('type', f'generic_{object_category_name}')
        working_objects.append(obj)

    # Horizontal merge
    horizontal_strips: List[Dict[str, Any]] = []
    key_func_h = lambda p: (str(p['type']), str(p['color']), p['y'], p['h'], p['x'])
    sorted_h = sorted(working_objects, key=key_func_h)

    for i, p_base in enumerate(sorted_h):
        if p_base['merged']: continue
        current_strip = p_base.copy(); p_base['merged'] = True
        for j in range(i + 1, len(sorted_h)):
            p_next = sorted_h[j]
            if p_next['merged']: continue
            
            if str(p_next['type']) == str(current_strip['type']) and \
               str(p_next['color']) == str(current_strip['color']) and \
               abs(p_next['y'] - current_strip['y']) < 1e-3 and \
               abs(p_next['h'] - current_strip['h']) < 1e-3 and \
               abs(p_next['x'] - (current_strip['x'] + current_strip['w'])) < 1e-3:
                current_strip['w'] += p_next['w']
                p_next['merged'] = True
            elif abs(p_next['y'] - current_strip['y']) >= 1e-3 or \
                 abs(p_next['h'] - current_strip['h']) >= 1e-3 or \
                 str(p_next['type']) != str(current_strip['type']) or \
                 str(p_next['color']) != str(current_strip['color']):
                break
        horizontal_strips.append(current_strip)

    # Vertical merge
    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge: strip['merged'] = False

    key_func_v = lambda s: (str(s['type']), str(s['color']), s['x'], s['w'], s['y'])
    sorted_v = sorted(strips_to_merge, key=key_func_v)

    for i, s_base in enumerate(sorted_v):
        if s_base['merged']: continue
        current_block = s_base.copy(); s_base['merged'] = True
        for j in range(i + 1, len(sorted_v)):
            s_next = sorted_v[j]
            if s_next['merged']: continue
            
            if str(s_next['type']) == str(current_block['type']) and \
               str(s_next['color']) == str(current_block['color']) and \
               abs(s_next['x'] - current_block['x']) < 1e-3 and \
               abs(s_next['w'] - current_block['w']) < 1e-3 and \
               abs(s_next['y'] - (current_block['y'] + current_block['h'])) < 1e-3:
                current_block['h'] += s_next['h']
                s_next['merged'] = True
            elif abs(s_next['x'] - current_block['x']) >= 1e-3 or \
                 abs(s_next['w'] - current_block['w']) >= 1e-3 or \
                 str(s_next['type']) != str(current_block['type']) or \
                 str(s_next['color']) != str(current_block['color']):
                break
        current_block.pop('merged', None)
        final_blocks_data.append({
            'rect': (current_block['x'], current_block['y'], current_block['w'], current_block['h']),
            'type': current_block['type'],
            'color': current_block.get('color'),
            'properties': current_block.get('properties', {}) # Preserve properties
        })
    
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
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)

    expected_py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    expected_py_filepath = os.path.join(maps_abs_dir, expected_py_filename)

    if os.path.normpath(py_filepath_to_use) != os.path.normpath(expected_py_filepath):
        py_filepath_to_use = expected_py_filepath
        editor_state.current_map_filename = py_filepath_to_use
        logger.warning(f"PY data filepath for export re-derived: '{py_filepath_to_use}'")

    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. PY data export aborted."); return False

    game_function_name = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{game_function_name}' in file '{py_filepath_to_use}'")

    platforms_data_raw: List[Dict[str, Any]] = []
    ladders_data_raw: List[Dict[str, Any]] = []
    hazards_data_raw: List[Dict[str, Any]] = []
    
    enemies_list_export: List[Dict[str, Any]] = []
    items_list_export: List[Dict[str, Any]] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts / 2.0
    default_spawn_world_y = (editor_state.map_height_tiles - 2) * ts 
    
    player_start_pos_p1: Optional[Tuple[float, float]] = None
    player_start_pos_p2: Optional[Tuple[float, float]] = None
    
    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []

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
        default_color_from_asset_tuple = getattr(C, 'GRAY', (128,128,128))
        
        if asset_entry.get("surface_params"):
            dims_color_tuple = asset_entry["surface_params"]
            if isinstance(dims_color_tuple, tuple) and len(dims_color_tuple) == 3:
                w_param, h_param, c_param = dims_color_tuple
                obj_w, obj_h = float(w_param), float(h_param)
                default_color_from_asset_tuple = c_param
        elif asset_entry.get("original_size_pixels"):
             orig_w, orig_h = asset_entry["original_size_pixels"]
             obj_w, obj_h = float(orig_w), float(orig_h)
        
        final_color_for_export = tuple(override_color_tuple) if isinstance(override_color_tuple, list) else \
                                 (override_color_tuple if isinstance(override_color_tuple, tuple) else default_color_from_asset_tuple)
        export_x, export_y = float(wx), float(wy)
        
        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})
        
        is_platform_type = any(pt in game_id.lower() for pt in ["platform", "wall", "ground", "ledge"])
        is_ladder_type = "ladder" in game_id.lower()
        is_hazard_type = "hazard" in game_id.lower()

        if is_platform_type:
            platform_game_type = game_id # Use the editor's game_type_id directly
            platforms_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 
                                       'color': final_color_for_export, 'type': platform_game_type, 
                                       'properties': obj_props})
        elif is_ladder_type:
            ladders_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 
                                     'color': final_color_for_export, 'type': 'ladder', 
                                     'properties': obj_props})
        elif is_hazard_type:
            hazards_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 
                                     'color': final_color_for_export, 'type': game_id, 
                                     'properties': obj_props})
        elif game_id == "player1_spawn":
            player_start_pos_p1 = (export_x + obj_w / 2.0, export_y + obj_h) 
        elif game_id == "player2_spawn":
            player_start_pos_p2 = (export_x + obj_w / 2.0, export_y + obj_h)
        elif "enemy" in game_id.lower():
            enemy_type_for_game = game_id 
            spawn_pos = (export_x + obj_w / 2.0, export_y + obj_h)
            enemies_list_export.append({'type': enemy_type_for_game, 'start_pos': spawn_pos, 
                                        'properties': obj_props})
        elif any(item_key in game_id.lower() for item_key in ["chest", "item", "collectible"]):
            item_type_for_game = game_id
            item_pos = (export_x + obj_w / 2.0, export_y + obj_h / 2.0) 
            items_list_export.append({'type': item_type_for_game, 'pos': item_pos, 
                                      'properties': obj_props})

    if player_start_pos_p1 is None: player_start_pos_p1 = (default_spawn_world_x, default_spawn_world_y)

    platforms_list_export = _merge_rect_objects_to_data(platforms_data_raw, "platform")
    ladders_list_export = _merge_rect_objects_to_data(ladders_data_raw, "ladder")
    hazards_list_export = _merge_rect_objects_to_data(hazards_data_raw, "hazard")

    map_min_x_content = 0.0; map_max_x_content = float(editor_state.map_width_tiles * ts)
    map_min_y_content = 0.0; map_max_y_content = float(editor_state.map_height_tiles * ts)
    if all_placed_objects_rect_data_for_bounds:
        map_min_x_content = min(r['x'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_x_content = max(r['x'] + r['width'] for r in all_placed_objects_rect_data_for_bounds)
        map_min_y_content = min(r['y'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_y_content = max(r['y'] + r['height'] for r in all_placed_objects_rect_data_for_bounds)

    padding_px = float(getattr(C, 'TILE_SIZE', 40) * 2)
    game_level_pixel_width = float(int(max(float(editor_state.map_width_tiles * ts), map_max_x_content) + padding_px))
    
    # Assuming Y increases downwards. Min Y is higher on screen.
    game_level_min_y_absolute = float(int(map_min_y_content - padding_px)) 
    game_level_max_y_absolute = float(int(map_max_y_content + padding_px)) 

    _boundary_thickness_val = float(getattr(C, 'TILE_SIZE', 40))
    _boundary_color_tuple = getattr(C, 'DARK_GRAY', (50,50,50))
    
    # Calculate effective map extents for boundary walls
    # These should encompass all content including padding
    eff_min_x = map_min_x_content - padding_px
    eff_max_x = map_max_x_content + padding_px
    eff_min_y = map_min_y_content - padding_px
    eff_max_y = map_max_y_content + padding_px

    # Ensure game_level_pixel_width covers from 0 (or eff_min_x if negative) to eff_max_x
    world_origin_x = min(0.0, eff_min_x)
    game_level_pixel_width = eff_max_x - world_origin_x
    
    # The min/max_y_absolute are effectively the content boundaries for the camera,
    # not necessarily the visual extent if Y=0 is top of screen.
    # game_level_min_y_absolute is the "highest" Y value of content.
    # game_level_max_y_absolute is the "lowest" Y value of content.

    boundary_platforms_data = [
        # Top boundary: Starts above the highest content (eff_min_y)
        {'rect': (eff_min_x, eff_min_y - _boundary_thickness_val, eff_max_x - eff_min_x, _boundary_thickness_val), 'type': 'boundary_wall_top', 'color': _boundary_color_tuple, 'properties': {}},
        # Bottom boundary: Starts at the lowest content (eff_max_y)
        {'rect': (eff_min_x, eff_max_y, eff_max_x - eff_min_x, _boundary_thickness_val), 'type': 'boundary_wall_bottom', 'color': _boundary_color_tuple, 'properties': {}},
        # Left boundary
        {'rect': (eff_min_x - _boundary_thickness_val, eff_min_y - _boundary_thickness_val, _boundary_thickness_val, eff_max_y - eff_min_y + 2*_boundary_thickness_val), 'type': 'boundary_wall_left', 'color': _boundary_color_tuple, 'properties': {}},
        # Right boundary
        {'rect': (eff_max_x, eff_min_y - _boundary_thickness_val, _boundary_thickness_val, eff_max_y - eff_min_y + 2*_boundary_thickness_val), 'type': 'boundary_wall_right', 'color': _boundary_color_tuple, 'properties': {}},
    ]
    platforms_list_export.extend(boundary_platforms_data)

    final_game_data_for_script = {
        "level_name": editor_state.map_name_for_function,
        "background_color": editor_state.background_color,
        "player_start_pos_p1": player_start_pos_p1,
        "platforms_list": platforms_list_export,
        "ladders_list": ladders_list_export,
        "hazards_list": hazards_list_export,
        "enemies_list": enemies_list_export,
        "items_list": items_list_export,
        "level_pixel_width": game_level_pixel_width,
        "level_min_y_absolute": game_level_min_y_absolute,
        "level_max_y_absolute": game_level_max_y_absolute,
    }
    if player_start_pos_p2:
        final_game_data_for_script["player_start_pos_p2"] = player_start_pos_p2
    
    # Ensure all keys expected by game_setup are present, even if empty
    for key in ["platforms_list", "ladders_list", "hazards_list", "enemies_list", "items_list"]:
        final_game_data_for_script.setdefault(key, [])


    script_content_parts = [
        f"# Level Data: {editor_state.map_name_for_function}",
        "# Generated by Platformer Level Editor",
        "",
        f"def {game_function_name}():", # Correct function name
        "    game_data = {"
    ]
    for key, value in final_game_data_for_script.items():
        script_content_parts.append(f"        {repr(key)}: {repr(value)},")
    
    script_content_parts.extend([
        "    }",
        "    return game_data",
        "",
        "if __name__ == '__main__':",
        f"    data = {game_function_name}()",
        "    import json",
        "    print(json.dumps(data, indent=4))"
    ])
    script_content = "\n".join(script_content_parts)

    try:
        with open(py_filepath_to_use, "w") as f: f.write(script_content)
        logger.info(f"Map data exported to game script: {os.path.basename(py_filepath_to_use)}")
        editor_state.unsaved_changes = False 
        return True
    except Exception as e:
        logger.error(f"Error exporting map data to .py '{py_filepath_to_use}': {e}", exc_info=True); return False


def delete_map_files(editor_state: EditorState, json_filepath_to_delete: str) -> bool:
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