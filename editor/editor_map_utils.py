# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
## version 2.0.1 (PySide6 Conversion - Corrected Import)
## version 2.0.2 (NameError fix for effective_min_x_for_bounds in export)
## version 2.0.3 (Refined f-string evaluation for boundary variables)
Utility functions for map operations in the Level Editor,
including initializing new maps, saving/loading editor-specific
map data (JSON), and exporting maps to game-compatible Python scripts.
"""
import pygame # Still used for Rect/Color in _merge_rect_objects and constants
import sys
import os
import json
import traceback
from typing import Optional, Dict, List, Tuple, Any
import logging

import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history

try:
    import constants as C
    # Ensure tiles.py has the correct game object classes
    from tiles import Platform, Ladder, Lava # Or whatever your game tile classes are
except ImportError as e_proj_imp:
    print(f"EDITOR_MAP_UTILS CRITICAL Error importing project modules (constants/tiles): {e_proj_imp}")
    class FallbackConstants:
        TILE_SIZE = 32
        GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0)
        DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230); MAGENTA=(255,0,255)
        EDITOR_SCREEN_INITIAL_WIDTH=1000 # Example fallback
    C = FallbackConstants()
    # Define dummy classes if tiles import fails
    class Platform: pass
    class Ladder: pass
    class Lava: pass

logger = logging.getLogger(__name__)


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    """
    Initializes the editor_state for a new, empty map with the given parameters.
    """
    logger.info(f"Initializing new map state. Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")

    clean_map_name = map_name_for_function # Assumed cleaned by caller
    if not clean_map_name:
        clean_map_name = "untitled_map"
        logger.warning(f"map_name_for_function was empty during init, defaulting to '{clean_map_name}'")

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.grid_size = ED_CONFIG.BASE_GRID_SIZE
    editor_state.placed_objects = []
    editor_state.asset_specific_variables.clear()
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE
    editor_state.camera_offset_x = 0.0
    editor_state.camera_offset_y = 0.0
    editor_state.zoom_level = 1.0
    editor_state.unsaved_changes = True

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    
    maps_base_dir = ED_CONFIG.MAPS_DIRECTORY 

    editor_state.current_map_filename = os.path.join(maps_base_dir, py_filename)
    editor_state.current_json_filename = os.path.join(maps_base_dir, json_filename)

    editor_state.undo_stack.clear()
    editor_state.redo_stack.clear()

    logger.info(f"Editor state initialized for new map. "
                f"map_name_for_function='{editor_state.map_name_for_function}', "
                f"current_map_filename (py)='{editor_state.current_map_filename}', "
                f"current_json_filename='{editor_state.current_json_filename}', "
                f"unsaved_changes={editor_state.unsaved_changes}")


def ensure_maps_directory_exists() -> bool:
    maps_dir_abs = ED_CONFIG.MAPS_DIRECTORY
    if not os.path.exists(maps_dir_abs):
        logger.info(f"Maps directory '{maps_dir_abs}' does not exist. Attempting to create.")
        try:
            os.makedirs(maps_dir_abs)
            logger.info(f"Successfully created maps directory: {maps_dir_abs}")
            return True
        except OSError as e:
            logger.error(f"Error creating maps directory {maps_dir_abs}: {e}", exc_info=True)
            return False
    elif not os.path.isdir(maps_dir_abs):
        logger.error(f"Path '{maps_dir_abs}' exists but is not a directory.")
        return False
    return True


def save_map_to_json(editor_state: EditorState) -> bool:
    logger.info(f"Saving map to JSON. Map name from state: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot save JSON."
        logger.error(msg)
        return False

    if not ensure_maps_directory_exists():
        msg = f"Could not create or access maps directory: {ED_CONFIG.MAPS_DIRECTORY}"
        logger.error(f"{msg} JSON save aborted.")
        return False

    json_filepath = editor_state.current_json_filename
    if not json_filepath or \
       os.path.basename(json_filepath) != (editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        logger.warning(f"JSON filepath re-derived for save. State name: '{editor_state.map_name_for_function}', Stored: '{json_filepath}'.")
        json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
        json_filepath = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_filename)
        editor_state.current_json_filename = json_filepath

    logger.debug(f"Attempting to save JSON to: '{json_filepath}' using map name '{editor_state.map_name_for_function}'")

    data_to_save = editor_history.get_map_snapshot(editor_state)
    for i, obj_in_snapshot in enumerate(data_to_save["placed_objects"]):
        if i < len(editor_state.placed_objects):
            obj_from_state = editor_state.placed_objects[i]
            if "properties" in obj_from_state:
                 obj_in_snapshot["properties"] = obj_from_state["properties"].copy()
            elif "properties" in obj_in_snapshot: 
                 del obj_in_snapshot["properties"]

    logger.debug(f"Data to save (first object example from snapshot): {data_to_save['placed_objects'][0] if data_to_save['placed_objects'] else 'No objects'}")
    error_msg = "" 

    try:
        with open(json_filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        success_msg = f"Editor data saved to: {os.path.basename(json_filepath)}"
        logger.info(success_msg)
        return True
    except IOError as e:
        error_msg = f"IOError saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    return False


def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    logger.info(f"Loading map from JSON: '{json_filepath}'")
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath):
        error_msg = f"JSON map file not found or is not a file: '{json_filepath}'"
        logger.error(error_msg)
        return False
    
    error_msg = "" 

    try:
        with open(json_filepath, 'r') as f:
            data_snapshot = json.load(f)
        logger.debug(f"Successfully read JSON data from '{json_filepath}'.")

        editor_history.restore_map_from_snapshot(editor_state, data_snapshot)

        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename_for_state)
        editor_state.current_json_filename = json_filepath

        if not editor_state.unsaved_changes: 
            editor_state.unsaved_changes = False 

        success_msg = f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}."
        logger.info(f"{success_msg}. map_name_for_function='{editor_state.map_name_for_function}', "
                    f"current_map_filename (py)='{editor_state.current_map_filename}', "
                    f"current_json_filename='{editor_state.current_json_filename}', "
                    f"unsaved_changes={editor_state.unsaved_changes}")
        return True

    except json.JSONDecodeError as e:
        error_msg = f"Error: Could not decode JSON from map file '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error loading map from JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    return False


def _merge_rect_objects(objects_raw: List[Dict[str, Any]], class_name_for_export: str, sprite_group_name: str) -> List[str]:
    if not objects_raw:
        return [f"    # No {class_name_for_export.lower()}s placed."]

    working_objects = [obj.copy() for obj in objects_raw]
    for obj in working_objects:
        obj['merged'] = False
        if class_name_for_export == "Platform" and 'type' not in obj:
            obj['type'] = 'generic'

    horizontal_strips: List[Dict[str, Any]] = []
    key_func_horizontal = lambda p: (str(p.get('type', '')), str(p['color']), p['y'], p['h'], p['x']) 
    sorted_objects_for_horizontal_merge = sorted(working_objects, key=key_func_horizontal)

    for i, p_base in enumerate(sorted_objects_for_horizontal_merge):
        if p_base['merged']: continue
        current_strip = p_base.copy()
        p_base['merged'] = True
        for j in range(i + 1, len(sorted_objects_for_horizontal_merge)):
            p_next = sorted_objects_for_horizontal_merge[j]
            if p_next['merged']: continue
            if (str(p_next.get('type', '')) == str(current_strip.get('type', '')) and
                str(p_next['color']) == str(current_strip['color']) and 
                p_next['y'] == current_strip['y'] and
                p_next['h'] == current_strip['h'] and
                p_next['x'] == current_strip['x'] + current_strip['w']):
                current_strip['w'] += p_next['w']
                p_next['merged'] = True
            elif (str(p_next.get('type', '')) != str(current_strip.get('type', '')) or
                  str(p_next['color']) != str(current_strip['color']) or
                  p_next['y'] != current_strip['y'] or
                  p_next['h'] != current_strip['h']):
                  break
            elif p_next['x'] != current_strip['x'] + current_strip['w']:
                break
        horizontal_strips.append(current_strip)

    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge: strip['merged'] = False
    key_func_vertical = lambda s: (str(s.get('type', '')), str(s['color']), s['x'], s['w'], s['y'])
    sorted_strips_for_vertical_merge = sorted(strips_to_merge, key=key_func_vertical)

    for i, s_base in enumerate(sorted_strips_for_vertical_merge):
        if s_base['merged']: continue
        current_block = s_base.copy()
        s_base['merged'] = True
        for j in range(i + 1, len(sorted_strips_for_vertical_merge)):
            s_next = sorted_strips_for_vertical_merge[j]
            if s_next['merged']: continue
            if (str(s_next.get('type', '')) == str(current_block.get('type', '')) and 
                str(s_next['color']) == str(current_block['color']) and 
                s_next['x'] == current_block['x'] and
                s_next['w'] == current_block['w'] and
                s_next['y'] == current_block['y'] + current_block['h']):
                current_block['h'] += s_next['h']
                s_next['merged'] = True
            elif (str(s_next.get('type', '')) != str(current_block.get('type', '')) or
                  str(s_next['color']) != str(current_block['color']) or
                  s_next['x'] != current_block['x'] or
                  s_next['w'] != current_block['w']):
                  break
            elif s_next['y'] != current_block['y'] + current_block['h']:
                break
        final_blocks_data.append(current_block)

    code_lines = []
    if not final_blocks_data:
         return [f"    # No {class_name_for_export.lower()} objects placed (empty after merge attempt)."]
    for block in final_blocks_data:
        color_str = str(block['color'])
        if not (color_str.startswith('(') and color_str.endswith(')')):
            try:
                parsed_color = eval(color_str)
                if isinstance(parsed_color, tuple) and len(parsed_color) == 3:
                    color_str = str(parsed_color)
                else:
                    color_str = str(getattr(C, 'MAGENTA', (255,0,255)))
            except:
                color_str = str(getattr(C, 'MAGENTA', (255,0,255)))

        if class_name_for_export == "Platform":
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {color_str}, platform_type='{block['type']}'))")
        else:
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {color_str}))")

    if not code_lines:
        return [f"    # No {class_name_for_export.lower()}s placed."]
    return code_lines


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map. Map name from state: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size

    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot export .py."
        logger.error(msg)
        return False

    py_filepath_to_use = editor_state.current_map_filename
    if not py_filepath_to_use or \
       os.path.basename(py_filepath_to_use) != (editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION):
        logger.warning(f"PY filepath for export re-derived. State name: '{editor_state.map_name_for_function}', Stored: '{py_filepath_to_use}'.")
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        py_filepath_to_use = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
        editor_state.current_map_filename = py_filepath_to_use

    if not ensure_maps_directory_exists():
        msg = f"Could not create/access maps directory: {ED_CONFIG.MAPS_DIRECTORY} for .py export."
        logger.error(f"{msg} PY export aborted.")
        return False

    function_name = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{function_name}' in file '{py_filepath_to_use}'")

    platform_objects_raw: List[Dict[str, Any]] = []
    ladder_objects_raw: List[Dict[str, Any]] = []
    hazards_code_lines: List[str] = []
    enemy_spawns_code_lines: List[str] = []
    collectible_spawns_code_lines: List[str] = []
    statue_spawns_code_lines: List[str] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts // 2
    default_spawn_world_y = (editor_state.map_height_tiles - 2 + 1) * ts
    player1_spawn_pos_str = f"player1_spawn_pos = ({default_spawn_world_x}, {default_spawn_world_y})"
    player1_spawn_props_str = "player1_spawn_props = {}" 

    all_placed_world_rects_for_bounds: List[pygame.Rect] = []
    lava_occupied_coords = set()
    for obj in editor_state.placed_objects: 
        if obj.get("game_type_id") == "hazard_lava":
            wx, wy = obj.get("world_x"), obj.get("world_y")
            if wx is not None and wy is not None: lava_occupied_coords.add((wx, wy))

    for obj_data in editor_state.placed_objects:
        game_id = obj_data.get("game_type_id")
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        asset_key = obj_data.get("asset_editor_key")
        override_color = obj_data.get("override_color")
        obj_props = obj_data.get("properties", {})

        if not all([game_id, wx is not None, wy is not None, asset_key]): continue
        asset_entry = editor_state.assets_palette.get(asset_key)
        if not asset_entry: continue

        obj_w, obj_h = ts, ts
        default_color = getattr(C, 'MAGENTA', (255,0,255))
        if asset_entry.get("surface_params"):
            dims_color_tuple = asset_entry["surface_params"]
            if isinstance(dims_color_tuple, tuple) and len(dims_color_tuple) == 3:
                w, h, c = dims_color_tuple; obj_w, obj_h = w, h; default_color = c
        elif asset_entry.get("render_mode") == "half_tile":
            default_color = asset_entry.get("base_color_tuple", default_color)
            ht = asset_entry.get("half_type")
            if ht in ["left", "right"]: obj_w = ts // 2
            elif ht in ["top", "bottom"]: obj_h = ts // 2
        elif asset_entry.get("original_size_pixels"):
            obj_w, obj_h = asset_entry["original_size_pixels"]

        final_color_export = override_color or \
                             (getattr(C, 'ORANGE_RED', (255,69,0)) if game_id == "hazard_lava" else default_color)
        color_str_export = str(final_color_export)

        ex, ey = wx, wy
        if asset_entry.get("render_mode") == "half_tile":
            ht = asset_entry.get("half_type")
            if ht == "right": ex = wx + ts // 2
            elif ht == "bottom": ey = wy + ts // 2

        all_placed_world_rects_for_bounds.append(pygame.Rect(ex, ey, obj_w, obj_h))
        props_export_str = f"{{{', '.join([f'{repr(k)}: {repr(v)}' for k,v in obj_props.items()])}}}"

        platform_kws = {"platform_wall", "platform_ledge"}
        is_platform = any(kw in game_id for kw in platform_kws)
        
        if is_platform and (wx, wy) in lava_occupied_coords:
            logger.warning(f"Skipping platform '{game_id}' at ({wx},{wy}) due to lava overlap.")
            continue
        
        if is_platform:
            plat_type = 'ledge' if "ledge" in game_id else ('wall' if "wall" in game_id else 'generic')
            platform_objects_raw.append({'x': ex, 'y': ey, 'w': obj_w, 'h': obj_h,
                                         'color': final_color_export, 'type': plat_type})
        elif game_id == "hazard_lava":
            hazards_code_lines.append(f"    hazards.add(Lava({ex}, {ey}, {obj_w}, {obj_h}, {color_str_export}))")
        elif game_id == "player1_spawn":
            spawn_mid_x, spawn_bot_y = ex + obj_w // 2, ey + obj_h
            player1_spawn_pos_str = f"player1_spawn_pos = ({spawn_mid_x}, {spawn_bot_y})"
            player1_spawn_props_str = f"player1_spawn_props = {props_export_str}"
        elif game_id == "player2_spawn": pass 
        elif "enemy" in game_id:
            col_id = game_id.split('_')[-1]
            smx, sby = ex + obj_w // 2, ey + obj_h
            enemy_spawns_code_lines.append(f"    enemy_spawns_data.append({{'pos': ({smx}, {sby}), 'patrol': None, 'enemy_color_id': '{col_id}', 'properties': {props_export_str}}})")
        elif game_id == "chest":
            smx, sby = ex + obj_w // 2, ey + obj_h
            collectible_spawns_code_lines.append(f"    collectible_spawns_data.append({{'type': 'chest', 'pos': ({smx}, {sby}), 'properties': {props_export_str}}})")
        elif game_id.startswith("object_stone_"):
            statue_id = f"{asset_key}_{wx}_{wy}"
            statue_center_x_export = ex + obj_w / 2
            statue_center_y_export = ey + obj_h / 2
            statue_spawns_code_lines.append(f"    statue_spawns_data.append({{'id': '{statue_id}', 'pos': ({statue_center_x_export}, {statue_center_y_export}), 'properties': {props_export_str}}})")
        elif "ladder" in game_id:
             ladder_objects_raw.append({'x': ex, 'y': ey, 'w': obj_w, 'h': obj_h, 'color': final_color_export})

    platforms_code_str = "\n".join(_merge_rect_objects(platform_objects_raw, "Platform", "platforms"))
    ladders_code_str = "\n".join(_merge_rect_objects(ladder_objects_raw, "Ladder", "ladders"))
    hazards_code_str = "\n".join(hazards_code_lines) if hazards_code_lines else "    # No hazards placed."
    enemy_spawns_code_str = "\n".join(enemy_spawns_code_lines) if enemy_spawns_code_lines else "    # No enemy spawns defined."
    collectible_spawns_code_str = "\n".join(collectible_spawns_code_lines) if collectible_spawns_code_lines else "    # No collectible spawns defined."
    statue_spawns_code_str = "\n".join(statue_spawns_code_lines) if statue_spawns_code_lines else "    # No statue spawns defined."

    map_min_x_content, map_max_x_content = 0, editor_state.get_map_pixel_width()
    map_min_y_content, map_max_y_content = 0, editor_state.get_map_pixel_height()

    if all_placed_world_rects_for_bounds:
        map_min_x_content = min(r.left for r in all_placed_world_rects_for_bounds)
        map_max_x_content = max(r.right for r in all_placed_world_rects_for_bounds)
        map_min_y_content = min(r.top for r in all_placed_world_rects_for_bounds)
        map_max_y_content = max(r.bottom for r in all_placed_world_rects_for_bounds)

    padding_px = ED_CONFIG.C.TILE_SIZE * 2
    # Use a fallback for EDITOR_SCREEN_INITIAL_WIDTH if C is the fallback class
    editor_initial_width_fallback = ED_CONFIG.C.EDITOR_SCREEN_INITIAL_WIDTH if hasattr(ED_CONFIG.C, 'EDITOR_SCREEN_INITIAL_WIDTH') else 1000
    
    game_map_total_width_pixels = int(max(editor_initial_width_fallback, map_max_x_content - map_min_x_content + 2 * padding_px))
    if map_max_x_content + padding_px > game_map_total_width_pixels:
         game_map_total_width_pixels = int(map_max_x_content + padding_px)
    if map_min_x_content < 0:
        game_map_total_width_pixels = int(max(game_map_total_width_pixels, map_max_x_content - map_min_x_content + padding_px))

    game_level_min_y_absolute = int(map_min_y_content - padding_px)
    game_level_max_y_absolute = int(map_max_y_content)
    game_main_ground_y_reference = int(map_max_y_content)
    game_main_ground_height_reference = int(ED_CONFIG.C.TILE_SIZE)

    if game_level_min_y_absolute >= game_level_max_y_absolute:
        game_level_max_y_absolute = game_level_min_y_absolute + ED_CONFIG.C.TILE_SIZE * 5

    # *** CRUCIAL FIX AREA ***
    # These values must be computed *before* being used in the f-string for script_content
    # so that their numeric results are embedded, not their variable names.
    _boundary_thickness_val = ED_CONFIG.C.TILE_SIZE * 2
    _boundary_wall_height_val = game_level_max_y_absolute - game_level_min_y_absolute + (2 * _boundary_thickness_val)
    _boundary_wall_height_val = max(_boundary_thickness_val * 2, _boundary_wall_height_val)
    _boundary_color_val = getattr(C, 'DARK_GRAY', (50,50,50)) # Get the actual tuple

    effective_min_x_for_bounds_val = min(0, map_min_x_content) # The *value*
    
    # This is the width of the top/bottom boundary walls
    boundary_full_width_val = game_map_total_width_pixels - effective_min_x_for_bounds_val 

    filler_wall_y_val = game_level_min_y_absolute - _boundary_thickness_val
    filler_wall_height_val = game_level_max_y_absolute - game_level_min_y_absolute + (2 * _boundary_thickness_val)
    filler_wall_height_val = max(_boundary_thickness_val * 2, filler_wall_height_val)


    script_content = f"""\
# Level: {editor_state.map_name_for_function}
# Generated by Platformer Level Editor (PySide6 Version - Optimized Export)
import pygame
from tiles import Platform, Ladder, Lava # Make sure these match your game's tile classes
from statue import Statue # For statue objects
import constants as C

LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color}
{player1_spawn_pos_str}
{player1_spawn_props_str}
# Note: P2 spawn is derived by game_setup.py from P1 spawn and level width.

def {function_name}(initial_screen_width, initial_screen_height):
    \"\"\"Loads the '{editor_state.map_name_for_function}' level.\"\"\"
    print(f"Loading map: {function_name}...")
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    collectible_spawns_data = []
    statue_spawns_data = [] # For Statues

    # --- Placed Objects (merged where possible) ---
{platforms_code_str}
{ladders_code_str}
{hazards_code_str}
{enemy_spawns_code_str}
{collectible_spawns_code_str}
{statue_spawns_code_str}

    # --- Level Dimensions for Game Camera & Boundaries ---
    map_total_width_pixels = {game_map_total_width_pixels}
    level_min_y_absolute = {game_level_min_y_absolute}
    level_max_y_absolute = {game_level_max_y_absolute}
    main_ground_y_reference = {game_main_ground_y_reference}
    main_ground_height_reference = {game_main_ground_height_reference}

    # Using pre-calculated values for boundary dimensions and colors
    _boundary_thickness = {_boundary_thickness_val}
    _boundary_wall_height = {_boundary_wall_height_val}
    _boundary_color = {_boundary_color_val}
"""
    
    # Filler walls (using pre-calculated values)
    if map_max_x_content < game_map_total_width_pixels:
        filler_wall_right_x_start_val = map_max_x_content
        filler_wall_right_width_val = game_map_total_width_pixels - filler_wall_right_x_start_val
        if filler_wall_right_width_val > 0:
            script_content += f"""
    # Filler wall on the far right
    platforms.add(Platform({filler_wall_right_x_start_val}, {filler_wall_y_val}, {filler_wall_right_width_val}, {filler_wall_height_val}, _boundary_color, platform_type='wall'))
"""
    if effective_min_x_for_bounds_val > 0: # If content starts to the right of origin
        filler_wall_left_width_val = effective_min_x_for_bounds_val
        script_content += f"""
    # Filler wall on the far left
    platforms.add(Platform(0, {filler_wall_y_val}, {filler_wall_left_width_val}, {filler_wall_height_val}, _boundary_color, platform_type='wall'))
"""

    script_content += f"""
    # Boundary platforms (ensure these use effective_min_x_for_bounds if map doesn't start at 0)
    platforms.add(Platform({effective_min_x_for_bounds_val}, level_min_y_absolute - _boundary_thickness, {boundary_full_width_val}, _boundary_thickness, _boundary_color, platform_type="boundary_wall_top"))
    platforms.add(Platform({effective_min_x_for_bounds_val}, level_max_y_absolute, {boundary_full_width_val}, _boundary_thickness, _boundary_color, platform_type="boundary_wall_bottom"))
    platforms.add(Platform({effective_min_x_for_bounds_val} - _boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_left"))
    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_right"))

    print(f"Map '{{function_name}}' loaded with: {{len(platforms)}} platforms, {{len(ladders)}} ladders, {{len(hazards)}} hazards, {{len(statue_spawns_data)}} statues.")
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn_pos, player1_spawn_props,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR,
            statue_spawns_data) # Return statue data as well
"""
    error_msg = "" 
    try:
        with open(py_filepath_to_use, "w") as f:
            f.write(script_content)
        success_msg = f"Map exported to game script: {os.path.basename(py_filepath_to_use)}"
        logger.info(success_msg)
        editor_state.unsaved_changes = False
        logger.debug(f"unsaved_changes set to False after .py export to '{py_filepath_to_use}'.")
        return True
    except IOError as e:
        error_msg = f"IOError exporting map to .py '{py_filepath_to_use}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error during .py export to '{py_filepath_to_use}': {e}"
        logger.error(error_msg, exc_info=True)
    return False


def delete_map_files(editor_state: EditorState, json_filepath_to_delete: str) -> bool:
    logger.info(f"Attempting to delete map files. Base JSON path: {json_filepath_to_delete}")
    if not json_filepath_to_delete.endswith(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        msg = f"Invalid file type for deletion: {json_filepath_to_delete}."
        logger.error(msg)
        return False

    map_name_base = os.path.splitext(os.path.basename(json_filepath_to_delete))[0]
    py_filename_to_delete = map_name_base + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    py_filepath_to_delete = os.path.join(os.path.dirname(json_filepath_to_delete), py_filename_to_delete)

    deleted_json, deleted_py = False, False
    action_json, action_py = False, False 

    try:
        if os.path.exists(json_filepath_to_delete):
            action_json = True; os.remove(json_filepath_to_delete)
            logger.info(f"Deleted: {json_filepath_to_delete}"); deleted_json = True
        else: logger.warning(f"Not found for deletion: {json_filepath_to_delete}")
    except OSError as e:
        action_json = True; msg = f"Error deleting '{json_filepath_to_delete}': {e}"
        logger.error(msg, exc_info=True)

    try:
        if os.path.exists(py_filepath_to_delete):
            action_py = True; os.remove(py_filepath_to_delete)
            logger.info(f"Deleted: {py_filepath_to_delete}"); deleted_py = True
        else: logger.warning(f"Not found for deletion: {py_filepath_to_delete}")
    except OSError as e:
        action_py = True; msg = f"Error deleting '{py_filepath_to_delete}': {e}"
        logger.error(msg, exc_info=True)

    success = False
    final_msg = ""
    if deleted_json and deleted_py: final_msg = f"Map '{map_name_base}' JSON & PY deleted."; success = True
    elif deleted_json: final_msg = f"Map '{map_name_base}' JSON deleted. PY missing/error."; success = True
    elif deleted_py: final_msg = f"Map '{map_name_base}' PY deleted. JSON missing/error."; success = True
    elif not action_json and not action_py: final_msg = f"Map '{map_name_base}' files not found."; success = True
    else: final_msg = f"Failed to delete one or more files for '{map_name_base}'. Check logs."
    return success