#################### START OF FILE: editor\editor_map_utils.py ####################

# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python scripts.
"""
# version 2.0.1 (PySide6 Refactor - Corrected f-string variable names in export)
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

# Main game constants and tile classes (as used by the *exported game map*)
try:
    import constants as C
except ImportError as e_proj_imp:
    print(f"EDITOR_MAP_UTILS CRITICAL Error importing project modules (constants/tiles): {e_proj_imp}")
    class FallbackConstants:
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

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)

    editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename)
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
        editor_state.unsaved_changes = False
        logger.info(f"Editor data saved to: {os.path.basename(json_filepath)}")
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
            editor_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            maps_abs_dir = os.path.join(editor_parent_dir, maps_abs_dir)
        
        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename_for_state)
        editor_state.current_json_filename = json_filepath
        editor_state.unsaved_changes = False
        logger.info(f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}.")
        return True
    except Exception as e:
        logger.error(f"Error loading map from JSON '{json_filepath}': {e}", exc_info=True); return False


def _merge_rect_objects(objects_raw: List[Dict[str, Any]], class_name_for_export: str, sprite_group_name: str) -> List[str]:
    if not objects_raw: return [f"    # No {class_name_for_export.lower()}s placed."]
    working_objects = []
    for obj_orig in objects_raw:
        obj = obj_orig.copy()
        obj['merged'] = False
        obj.setdefault('x', 0); obj.setdefault('y', 0)
        obj.setdefault('w', ED_CONFIG.BASE_GRID_SIZE); obj.setdefault('h', ED_CONFIG.BASE_GRID_SIZE)
        obj.setdefault('color', C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255))
        if class_name_for_export == "Platform": obj.setdefault('type', 'generic')
        working_objects.append(obj)

    horizontal_strips: List[Dict[str, Any]] = []
    key_func_h = lambda p: (str(p.get('type', '')), str(p['color']), p['y'], p['h'], p['x'])
    sorted_h = sorted(working_objects, key=key_func_h)
    for i, p_base in enumerate(sorted_h):
        if p_base['merged']: continue
        current_strip = p_base.copy(); p_base['merged'] = True
        for j in range(i + 1, len(sorted_h)):
            p_next = sorted_h[j]
            if p_next['merged']: continue
            if (str(p_next.get('type', '')) == str(current_strip.get('type', '')) and
                str(p_next['color']) == str(current_strip['color']) and
                p_next['y'] == current_strip['y'] and p_next['h'] == current_strip['h'] and
                p_next['x'] == current_strip['x'] + current_strip['w']):
                current_strip['w'] += p_next['w']; p_next['merged'] = True
            elif p_next['y'] != current_strip['y'] or p_next['h'] != current_strip['h'] or \
                 str(p_next.get('type', '')) != str(current_strip.get('type', '')) or \
                 str(p_next['color']) != str(current_strip['color']):
                break
        horizontal_strips.append(current_strip)

    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge: strip['merged'] = False
    key_func_v = lambda s: (str(s.get('type', '')), str(s['color']), s['x'], s['w'], s['y'])
    sorted_v = sorted(strips_to_merge, key=key_func_v)
    for i, s_base in enumerate(sorted_v):
        if s_base['merged']: continue
        current_block = s_base.copy(); s_base['merged'] = True
        for j in range(i + 1, len(sorted_v)):
            s_next = sorted_v[j]
            if s_next['merged']: continue
            if (str(s_next.get('type', '')) == str(current_block.get('type', '')) and
                str(s_next['color']) == str(current_block['color']) and
                s_next['x'] == current_block['x'] and s_next['w'] == current_block['w'] and
                s_next['y'] == current_block['y'] + current_block['h']):
                current_block['h'] += s_next['h']; s_next['merged'] = True
            elif s_next['x'] != current_block['x'] or s_next['w'] != current_block['w'] or \
                 str(s_next.get('type', '')) != str(current_block.get('type', '')) or \
                 str(s_next['color']) != str(current_block['color']):
                break
        final_blocks_data.append(current_block)
    
    code_lines = []
    if not final_blocks_data: return [f"    # No {class_name_for_export.lower()} objects after merge."]
    for block in final_blocks_data:
        color_val = block['color']
        if isinstance(color_val, list): color_val = tuple(color_val)
        color_str_export = str(color_val)
        if class_name_for_export == "Platform":
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {color_str_export}, platform_type='{block['type']}'))")
        else:
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {color_str_export}))")
    return code_lines if code_lines else [f"    # No {class_name_for_export.lower()}s placed."]


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map. Map name from state: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set. Cannot export .py."); return False
    
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
        logger.warning(f"PY filepath for export re-derived: '{py_filepath_to_use}'")

    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. PY export aborted."); return False

    function_name_str_for_map_file = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{function_name_str_for_map_file}' in file '{py_filepath_to_use}'")

    platform_objects_data: List[Dict[str, Any]] = []
    ladder_objects_data: List[Dict[str, Any]] = []
    hazards_code: List[str] = []
    enemy_spawns_code: List[str] = []
    collectible_spawns_code: List[str] = []
    statue_spawns_code: List[str] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts // 2
    default_spawn_world_y = (editor_state.map_height_tiles - 1) * ts 
    player1_spawn_pos_export = (default_spawn_world_x, default_spawn_world_y)
    player1_spawn_props_export = {}

    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []
    lava_occupied_coords = set()

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
        if not asset_entry: logger.warning(f"Asset key '{asset_key}' not found in palette for export. Skipping."); continue

        obj_w, obj_h = float(ts), float(ts)
        default_color_from_asset = getattr(C, 'MAGENTA', (255,0,255))
        if asset_entry.get("surface_params"):
            dims_color_tuple = asset_entry["surface_params"]
            if isinstance(dims_color_tuple, tuple) and len(dims_color_tuple) == 3:
                w_param, h_param, c_param = dims_color_tuple
                obj_w, obj_h = float(w_param), float(h_param); default_color_from_asset = c_param
        elif asset_entry.get("render_mode") == "half_tile":
            default_color_from_asset = asset_entry.get("base_color_tuple", default_color_from_asset)
            ht = asset_entry.get("half_type")
            if ht in ["left", "right"]: obj_w = ts / 2.0
            elif ht in ["top", "bottom"]: obj_h = ts / 2.0
        elif asset_entry.get("original_size_pixels"):
             orig_w, orig_h = asset_entry["original_size_pixels"]
             obj_w, obj_h = float(orig_w), float(orig_h)
        
        final_color_for_export = override_color_tuple or default_color_from_asset
        color_str_for_export = str(tuple(final_color_for_export) if isinstance(final_color_for_export, list) else final_color_for_export)
        export_x, export_y = float(wx), float(wy)
        if asset_entry.get("render_mode") == "half_tile":
            ht = asset_entry.get("half_type")
            if ht == "right": export_x = wx + ts / 2.0
            elif ht == "bottom": export_y = wy + ts / 2.0
        
        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})
        props_export_str = f"{{{', '.join([f'{repr(k)}: {repr(v)}' for k,v in obj_props.items()])}}}" if obj_props else "{}"
        is_platform_type = any(kw in game_id for kw in ["platform_wall", "platform_ledge"])
        if is_platform_type:
            if (wx, wy) in lava_occupied_coords: logger.warning(f"Skipping platform export for '{game_id}' at ({wx},{wy}) due to lava overlap."); continue
            plat_type_str = 'ledge' if "ledge" in game_id else ('wall' if "wall" in game_id else 'generic')
            platform_objects_data.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': plat_type_str})
        elif game_id == "hazard_lava": hazards_code.append(f"    hazards.add(Lava({export_x}, {export_y}, {obj_w}, {obj_h}, {color_str_for_export}))")
        elif game_id == "player1_spawn": player1_spawn_pos_export = (export_x + obj_w / 2.0, export_y + obj_h); player1_spawn_props_export = obj_props
        elif "enemy" in game_id:
            enemy_color_id_str = game_id.split('_')[-1]
            spawn_mid_x, spawn_mid_bottom_y = export_x + obj_w / 2.0, export_y + obj_h
            enemy_spawns_code.append(f"    enemy_spawns_data.append({{'pos': ({spawn_mid_x}, {spawn_mid_bottom_y}), 'patrol': None, 'enemy_color_id': '{enemy_color_id_str}', 'properties': {props_export_str}}})")
        elif game_id == "chest":
            spawn_mid_x, spawn_mid_bottom_y = export_x + obj_w / 2.0, export_y + obj_h
            collectible_spawns_code.append(f"    collectible_spawns_data.append({{'type': 'chest', 'pos': ({spawn_mid_x}, {spawn_mid_bottom_y}), 'properties': {props_export_str}}})")
        elif game_id.startswith("object_stone_"):
            statue_id_str = f"{asset_key}_{int(wx)}_{int(wy)}"
            statue_center_x_exp, statue_center_y_exp = export_x + obj_w / 2.0, export_y + obj_h / 2.0
            statue_spawns_code.append(f"    statue_spawns_data.append({{'id': '{statue_id_str}', 'pos': ({statue_center_x_exp}, {statue_center_y_exp}), 'properties': {props_export_str}}})")
        elif "ladder" in game_id: ladder_objects_data.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export})

    platforms_code_str = "\n".join(_merge_rect_objects(platform_objects_data, "Platform", "platforms"))
    ladders_code_str = "\n".join(_merge_rect_objects(ladder_objects_data, "Ladder", "ladders"))
    hazards_code_str = "\n".join(hazards_code) if hazards_code else "    # No hazards placed."
    enemy_spawns_code_str = "\n".join(enemy_spawns_code) if enemy_spawns_code else "    # No enemy spawns defined."
    collectible_spawns_code_str = "\n".join(collectible_spawns_code) if collectible_spawns_code else "    # No collectible spawns defined."
    statue_spawns_code_str = "\n".join(statue_spawns_code) if statue_spawns_code else "    # No statue spawns defined."
    player1_spawn_props_script_str = f"player1_spawn_props = {repr(player1_spawn_props_export)}"

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

    _boundary_thickness_val = float(getattr(C, 'TILE_SIZE', 40))
    _boundary_wall_height_val = (game_level_max_y_absolute_val - game_level_min_y_absolute_val) + (2 * _boundary_thickness_val)
    _boundary_wall_height_val = float(int(max(_boundary_thickness_val * 2, _boundary_wall_height_val)))
    _boundary_color_tuple = getattr(C, 'DARK_GRAY', (50,50,50))
    effective_min_x_for_bounds_val = float(int(min(0.0, map_min_x_content)))
    boundary_full_width_val = game_map_total_width_pixels_val - effective_min_x_for_bounds_val
    boundary_full_width_val = float(int(boundary_full_width_val))
    filler_wall_y_val = game_level_min_y_absolute_val - _boundary_thickness_val
    filler_wall_y_val = float(int(filler_wall_y_val))
    boundary_color_str = str(tuple(_boundary_color_tuple) if isinstance(_boundary_color_tuple, list) else _boundary_color_tuple)

    script_content = f"""\
# Level: {editor_state.map_name_for_function}
# Generated by Platformer Level Editor (PySide6 Version)
import pygame 
from tiles import Platform, Ladder, Lava 
from statue import Statue 
import constants as C 

LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color} 
player1_spawn_pos = {player1_spawn_pos_export} 
{player1_spawn_props_script_str} 

def {function_name_str_for_map_file}(initial_screen_width, initial_screen_height):
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []      
    collectible_spawns_data = []
    statue_spawns_data = []     

{platforms_code_str}
{ladders_code_str}
{hazards_code_str}
{enemy_spawns_code_str}
{collectible_spawns_code_str}
{statue_spawns_code_str}

    map_total_width_pixels = {game_map_total_width_pixels_val}
    level_min_y_absolute = {game_level_min_y_absolute_val} 
    level_max_y_absolute = {game_level_max_y_absolute_val} 
    main_ground_y_reference = {main_ground_y_reference_val} 
    main_ground_height_reference = {main_ground_height_reference_val}

    _boundary_thickness = {_boundary_thickness_val}
    _boundary_wall_height = {_boundary_wall_height_val}
    _boundary_color = {boundary_color_str} 
    _effective_min_x_for_bounds = {effective_min_x_for_bounds_val}
    _boundary_full_width = {boundary_full_width_val}
    _filler_wall_y = {filler_wall_y_val}
    _filler_wall_height = _boundary_wall_height 

    platforms.add(Platform(_effective_min_x_for_bounds, level_min_y_absolute - _boundary_thickness, _boundary_full_width, _boundary_thickness, _boundary_color, platform_type="boundary_wall_top"))
    platforms.add(Platform(_effective_min_x_for_bounds, level_max_y_absolute, _boundary_full_width, _boundary_thickness, _boundary_color, platform_type="boundary_wall_bottom"))
    platforms.add(Platform(_effective_min_x_for_bounds - _boundary_thickness, _filler_wall_y, _boundary_thickness, _filler_wall_height, _boundary_color, platform_type="boundary_wall_left"))
    platforms.add(Platform(map_total_width_pixels, _filler_wall_y, _boundary_thickness, _filler_wall_height, _boundary_color, platform_type="boundary_wall_right"))

    print(f"Map '{function_name_str_for_map_file}' loaded. Platforms: {{len(platforms)}}, Ladders: {{len(ladders)}}, Hazards: {{len(hazards)}}, Statues: {{len(statue_spawns_data)}}")
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn_pos, player1_spawn_props,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR,
            statue_spawns_data)
"""
    try:
        with open(py_filepath_to_use, "w") as f: f.write(script_content)
        logger.info(f"Map exported to game script: {os.path.basename(py_filepath_to_use)}")
        return True
    except Exception as e:
        logger.error(f"Error exporting map to .py '{py_filepath_to_use}': {e}", exc_info=True); return False


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

#################### END OF FILE: editor\editor_map_utils.py ####################