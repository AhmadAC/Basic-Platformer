# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
## version 1.0.2.1 (Fixed NameError for level_min_y_absolute in export, refined filler wall logic)
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

import editor_config as ED_CONFIG
from editor_state import EditorState

import constants as C
from tiles import Platform, Ladder, Lava # Assuming Ladder might be used later

logger = logging.getLogger(__name__)


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int):
    logger.info(f"Initializing new map state. Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")

    clean_map_name = map_name_for_function.lower().replace(" ", "_").replace("-", "_")
    if not clean_map_name:
        clean_map_name = "untitled_map"
        logger.warning(f"map_name_for_function was empty after cleaning, defaulting to '{clean_map_name}'")

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.placed_objects = []
    editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
    editor_state.camera_offset_x = 0
    editor_state.camera_offset_y = 0
    editor_state.unsaved_changes = True

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)

    editor_state.recreate_map_content_surface()

    logger.info(f"Editor state initialized for new map. map_name_for_function='{editor_state.map_name_for_function}', "
                f"current_map_filename='{editor_state.current_map_filename}', unsaved_changes={editor_state.unsaved_changes}")


def ensure_maps_directory_exists() -> bool:
    maps_dir = ED_CONFIG.MAPS_DIRECTORY
    if not os.path.exists(maps_dir):
        logger.info(f"Maps directory '{maps_dir}' does not exist. Attempting to create.")
        try:
            os.makedirs(maps_dir)
            logger.info(f"Successfully created directory: {maps_dir}")
            return True
        except OSError as e:
            logger.error(f"Error creating directory {maps_dir}: {e}", exc_info=True)
            return False
    return True


def save_map_to_json(editor_state: EditorState) -> bool:
    logger.info(f"Saving map to JSON. Map name: '{editor_state.map_name_for_function}'")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name is not set or is 'untitled_map'. Cannot save JSON."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(msg)
        return False

    if not ensure_maps_directory_exists():
        msg = "Could not create or access maps directory."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(f"{msg} JSON save aborted.")
        return False

    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    json_filepath = os.path.join(ED_CONFIG.MAPS_DIRECTORY, json_filename)
    logger.debug(f"Attempting to save JSON to: '{json_filepath}'")

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
        if override_color:
            s_obj["override_color"] = list(override_color)

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
    logger.debug(f"Data to save (first object example): {serializable_objects[0] if serializable_objects else 'No objects'}")

    try:
        with open(json_filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        success_msg = f"Editor data saved to: {json_filename}"
        logger.info(success_msg)
        editor_state.set_status_message(success_msg)
        return True
    except IOError as e:
        error_msg = f"IOError saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error saving map to JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc()

    editor_state.set_status_message(error_msg, 4)
    return False


def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
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

        editor_state.map_name_for_function = data.get("map_name_for_function", "loaded_map_error_name")
        editor_state.map_width_tiles = data.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES)
        editor_state.map_height_tiles = data.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES)
        editor_state.grid_size = data.get("grid_size", ED_CONFIG.DEFAULT_GRID_SIZE)

        bg_color_data = data.get("background_color", ED_CONFIG.DEFAULT_BACKGROUND_COLOR)
        if isinstance(bg_color_data, list) and len(bg_color_data) == 3:
            editor_state.background_color = tuple(bg_color_data) # type: ignore
        else:
            editor_state.background_color = ED_CONFIG.DEFAULT_BACKGROUND_COLOR
            logger.warning(f"Invalid background_color format in JSON, using default. Got: {bg_color_data}")

        temp_placed_objects_from_json: List[Dict[str, Any]] = []
        loaded_placed_objects_data = data.get("placed_objects", [])
        logger.debug(f"Loading {len(loaded_placed_objects_data)} objects from JSON.")
        for i, obj_data in enumerate(loaded_placed_objects_data):
            asset_key = obj_data.get("asset_editor_key")
            game_type_id_from_json = obj_data.get("game_type_id")
            world_x = obj_data.get("world_x")
            world_y = obj_data.get("world_y")
            override_color_data = obj_data.get("override_color")

            if not all([asset_key, game_type_id_from_json is not None, world_x is not None, world_y is not None]):
                logger.warning(f"Loaded object at index {i} has missing core data, skipping: {obj_data}")
                continue

            if asset_key in ED_CONFIG.EDITOR_PALETTE_ASSETS:
                new_obj = {
                    "asset_editor_key": asset_key,
                    "world_x": world_x,
                    "world_y": world_y,
                    "game_type_id": game_type_id_from_json
                }
                if override_color_data and isinstance(override_color_data, list) and len(override_color_data) == 3:
                    new_obj["override_color"] = tuple(override_color_data) # type: ignore
                temp_placed_objects_from_json.append(new_obj)
            else:
                logger.warning(f"Asset key '{asset_key}' from loaded object (JSON type: '{game_type_id_from_json}') "
                               f"not found in current ED_CONFIG.EDITOR_PALETTE_ASSETS. Object at ({world_x},{world_y}) skipped.")

        corrected_objects: List[Dict[str, Any]] = []
        lava_coords_to_check = set()
        corrections_made = False

        for obj in temp_placed_objects_from_json:
            if obj.get("game_type_id") == "hazard_lava":
                if obj.get("world_x") is not None and obj.get("world_y") is not None:
                    lava_coords_to_check.add((obj["world_x"], obj["world_y"]))

        logger.debug(f"Auto-correction: Found {len(lava_coords_to_check)} lava coordinates for checking: {lava_coords_to_check}")

        for obj in temp_placed_objects_from_json:
            obj_wx, obj_wy = obj.get("world_x"), obj.get("world_y")
            obj_game_type_id = obj.get("game_type_id", "")

            solid_platform_game_types = {
                "platform_wall_gray", "platform_ledge_green",
            }
            is_solid_platform_game_type = (
                obj_game_type_id in solid_platform_game_types or
                ( ("platform_wall_gray_" in obj_game_type_id or "platform_ledge_green_" in obj_game_type_id) and
                  "_half" in obj_game_type_id )
            )

            if is_solid_platform_game_type and obj_wx is not None and obj_wy is not None and (obj_wx, obj_wy) in lava_coords_to_check:
                logger.info(f"Auto-correcting: Removing solid platform '{obj.get('asset_editor_key')}' ({obj_game_type_id}) "
                            f"at lava location ({obj_wx},{obj_wy}).")
                corrections_made = True
            else:
                corrected_objects.append(obj)

        editor_state.placed_objects = corrected_objects
        if corrections_made:
            editor_state.unsaved_changes = True
            editor_state.set_status_message("Map auto-corrected: Removed solid platforms under lava.", 4.0)
            logger.info("Map auto-corrected due to lava/platform conflict. Unsaved changes flag set.")

        editor_state.camera_offset_x = data.get("camera_offset_x", 0)
        editor_state.camera_offset_y = data.get("camera_offset_y", 0)
        editor_state.show_grid = data.get("show_grid", True)

        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)

        editor_state.recreate_map_content_surface()
        if not corrections_made:
            editor_state.unsaved_changes = False

        success_msg = f"Map '{editor_state.map_name_for_function}' loaded from {os.path.basename(json_filepath)}."
        if corrections_made: success_msg += " (Auto-corrected)"

        logger.info(f"{success_msg}. unsaved_changes={editor_state.unsaved_changes}, current_map_filename='{editor_state.current_map_filename}'")
        editor_state.set_status_message(success_msg)
        return True

    except json.JSONDecodeError as e:
        error_msg = f"Error: Could not decode JSON from map file '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error loading map from JSON '{json_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc()

    editor_state.set_status_message(error_msg, 4)
    return False


def _merge_rect_objects(objects_raw: List[Dict[str, Any]], class_name_for_export: str, sprite_group_name: str) -> List[str]:
    if not objects_raw:
        return [f"    # No {class_name_for_export.lower()}s placed."]

    working_objects = [obj.copy() for obj in objects_raw]
    for obj in working_objects:
        obj['merged'] = False

    horizontal_strips: List[Dict[str, Any]] = []
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
            
            if (p_next.get('type', '') == current_strip.get('type', '') and
                p_next['color'] == current_strip['color'] and
                p_next['y'] == current_strip['y'] and
                p_next['h'] == current_strip['h'] and
                p_next['x'] == current_strip['x'] + current_strip['w']):
                current_strip['w'] += p_next['w']
                p_next['merged'] = True
            elif (p_next.get('type', '') != current_strip.get('type', '') or
                  p_next['color'] != current_strip['color'] or
                  p_next['y'] != current_strip['y'] or
                  p_next['h'] != current_strip['h']):
                  break
            elif p_next['x'] != current_strip['x'] + current_strip['w']:
                break
        horizontal_strips.append(current_strip)

    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge:
        strip['merged'] = False

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
            if (s_next.get('type', '') == current_block.get('type', '') and
                s_next['color'] == current_block['color'] and
                s_next['x'] == current_block['x'] and
                s_next['w'] == current_block['w'] and
                s_next['y'] == current_block['y'] + current_block['h']):
                current_block['h'] += s_next['h']
                s_next['merged'] = True
            elif (s_next.get('type', '') != current_block.get('type', '') or
                  s_next['color'] != current_block['color'] or
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
        if class_name_for_export == "Platform":
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {block['color']}, platform_type='{block['type']}'))")
        else:
            code_lines.append(f"    {sprite_group_name}.add({class_name_for_export}({block['x']}, {block['y']}, {block['w']}, {block['h']}, {block['color']}))")
            
    if not code_lines:
        return [f"    # No {class_name_for_export.lower()}s placed."]
    return code_lines


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map '{editor_state.map_name_for_function}' to Python script.")
    ts = editor_state.grid_size

    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        msg = "Map name not set or is 'untitled_map'. Cannot export .py."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(msg)
        return False

    if not editor_state.current_map_filename:
        py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(ED_CONFIG.MAPS_DIRECTORY, py_filename)
        logger.warning(f"current_map_filename was not set, derived as '{editor_state.current_map_filename}' for export.")

    if not ensure_maps_directory_exists():
        msg = "Could not create or access maps directory for .py export."
        editor_state.set_status_message(f"Error: {msg}", 3)
        logger.error(f"{msg} PY export aborted.")
        return False

    function_name = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{function_name}' in file '{editor_state.current_map_filename}'")

    platform_objects_raw: List[Dict[str, Any]] = []
    hazards_code_lines: List[str] = []
    enemy_spawns_code_lines: List[str] = []
    collectible_spawns_code_lines: List[str] = []

    default_spawn_tile_x = editor_state.map_width_tiles // 2
    default_spawn_tile_y = editor_state.map_height_tiles // 2
    default_spawn_world_x = default_spawn_tile_x * ts + ts // 2
    default_spawn_world_y = (default_spawn_tile_y + 1) * ts
    player1_spawn_str = f"player1_spawn = ({default_spawn_world_x}, {default_spawn_world_y}) # Default P1 Spawn"

    all_placed_world_rects_for_bounds: List[pygame.Rect] = []
    logger.debug(f"Processing {len(editor_state.placed_objects)} objects for .py export.")

    lava_occupied_coords = set()
    for obj_data_lava_check in editor_state.placed_objects:
        if obj_data_lava_check.get("game_type_id") == "hazard_lava":
            world_x = obj_data_lava_check.get("world_x")
            world_y = obj_data_lava_check.get("world_y")
            if world_x is not None and world_y is not None:
                lava_occupied_coords.add((world_x, world_y))
    logger.debug(f"Export: Identified {len(lava_occupied_coords)} lava-occupied coordinates for check: {lava_occupied_coords}")

    for i, obj_data in enumerate(editor_state.placed_objects):
        game_type_id = obj_data.get("game_type_id")
        world_x = obj_data.get("world_x")
        world_y = obj_data.get("world_y")
        asset_editor_key = obj_data.get("asset_editor_key")
        override_color = obj_data.get("override_color")

        if not all([game_type_id, world_x is not None, world_y is not None, asset_editor_key]):
             logger.warning(f"Export - Object at index {i} missing data, skipping: {obj_data}")
             continue

        asset_palette_entry = editor_state.assets_palette.get(asset_editor_key)
        if not asset_palette_entry:
            logger.warning(f"Asset key '{asset_editor_key}' not in palette. Skipping object export for obj: {obj_data}")
            continue

        obj_w_px, obj_h_px = ts, ts
        default_color_tuple = getattr(C, 'MAGENTA', (255,0,255))

        if asset_palette_entry.get("surface_params_dims_color"):
            w, h, c = asset_palette_entry["surface_params_dims_color"]
            obj_w_px, obj_h_px = w, h
            default_color_tuple = c
        elif asset_palette_entry.get("render_mode") == "half_tile":
            half_type = asset_palette_entry.get("half_type")
            default_color_tuple = asset_palette_entry.get("base_color_tuple", default_color_tuple)
            if half_type in ["left", "right"]: obj_w_px = ts // 2; obj_h_px = ts
            elif half_type in ["top", "bottom"]: obj_w_px = ts; obj_h_px = ts // 2
        elif asset_palette_entry.get("original_size_pixels"):
             obj_w_px, obj_h_px = asset_palette_entry["original_size_pixels"]

        current_color_tuple = override_color if override_color else default_color_tuple
        current_color_str = f"({current_color_tuple[0]},{current_color_tuple[1]},{current_color_tuple[2]})" if isinstance(current_color_tuple, (list, tuple)) else str(current_color_tuple)

        export_x, export_y = world_x, world_y
        if asset_palette_entry.get("render_mode") == "half_tile":
            half_type = asset_palette_entry.get("half_type")
            if half_type == "right": export_x = world_x + ts // 2
            elif half_type == "bottom": export_y = world_y + ts // 2

        current_obj_rect = pygame.Rect(export_x, export_y, obj_w_px, obj_h_px)
        all_placed_world_rects_for_bounds.append(current_obj_rect)

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
            spawn_mid_x = world_x + obj_w_px // 2
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
            if not game_type_id.startswith("tool_"):
                logger.warning(f"Unknown game_type_id '{game_type_id}' for object at ({world_x},{world_y}). Not exported to .py.")

    platforms_code_lines = _merge_rect_objects(platform_objects_raw, "Platform", "platforms")
    ladders_code_lines = [f"    # No ladders placed."]
    platforms_code_str = "\n".join(platforms_code_lines)
    ladders_code_str = "\n".join(ladders_code_lines)
    hazards_code_str = "\n".join(hazards_code_lines) if hazards_code_lines else "    # No hazards placed."
    enemy_spawns_code_str = "\n".join(enemy_spawns_code_lines) if enemy_spawns_code_lines else "    # No enemy spawns defined."
    collectible_spawns_code_str = "\n".join(collectible_spawns_code_lines) if collectible_spawns_code_lines else "    # No collectible spawns defined."

    logger.debug(f"Generated code lines - Platforms (merged): {len(platforms_code_lines)}, Hazards: {len(hazards_code_lines)}, Enemies: {len(enemy_spawns_code_lines)}, Collectibles: {len(collectible_spawns_code_lines)}")

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

    padding_px = C.TILE_SIZE * 2
    
    content_span_x = map_max_x_content - map_min_x_content
    game_map_total_width_pixels = int(max(ED_CONFIG.EDITOR_SCREEN_INITIAL_WIDTH, content_span_x + 2 * padding_px))
    
    if map_max_x_content + padding_px > game_map_total_width_pixels:
         game_map_total_width_pixels = int(map_max_x_content + padding_px)

    # These are Python variables in the exporter's scope
    game_level_min_y_absolute = int(map_min_y_content - padding_px)
    game_level_max_y_absolute = int(map_max_y_content) 
    game_main_ground_y_reference = int(map_max_y_content)
    game_main_ground_height_reference = int(C.TILE_SIZE)

    if game_level_min_y_absolute >= game_level_max_y_absolute:
        logger.warning(f"Calculated min_y_abs ({game_level_min_y_absolute}) >= max_y_abs ({game_level_max_y_absolute}). Adjusting max_y_abs.")
        game_level_max_y_absolute = game_level_min_y_absolute + C.TILE_SIZE * 5

    logger.debug(f"Export boundaries - map_min_x_content: {map_min_x_content}, map_max_x_content: {map_max_x_content}")
    logger.debug(f"Export boundaries - TotalWidthPx: {game_map_total_width_pixels}, MinYAbs: {game_level_min_y_absolute}, MaxYAbs: {game_level_max_y_absolute}")

    script_content_parts = [
        f"# Level: {editor_state.map_name_for_function}",
        "# Generated by Platformer Level Editor (Optimized Export)",
        "import pygame",
        "from tiles import Platform, Ladder, Lava",
        "import constants as C",
        "",
        f"LEVEL_SPECIFIC_BACKGROUND_COLOR = {editor_state.background_color}",
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
        f"    {player1_spawn_str}",
        "",
        "    # --- Placed Objects (merged where possible) ---",
        platforms_code_str,
        ladders_code_str,
        hazards_code_str,
        enemy_spawns_code_str,
        collectible_spawns_code_str,
        "",
        "    # --- Level Dimensions for Game Camera & Boundaries ---",
        # Values from exporter's Python variables are written into the generated script
        f"    map_total_width_pixels = {game_map_total_width_pixels}",
        f"    level_min_y_absolute = {game_level_min_y_absolute}",
        f"    level_max_y_absolute = {game_level_max_y_absolute}",
        f"    main_ground_y_reference = {game_main_ground_y_reference}",
        f"    main_ground_height_reference = {game_main_ground_height_reference}",
        "",
        # These define variables *within the generated script*
        "    _boundary_thickness = C.TILE_SIZE * 2",
        "    _boundary_wall_height = level_max_y_absolute - level_min_y_absolute + (2 * _boundary_thickness)",
        "    _boundary_color = getattr(C, 'DARK_GRAY', (50,50,50))",
        "",
    ]

    # --- Add filler wall for the right side if content doesn't span the full map width ---
    # These calculations use Python variables from the exporter's scope
    filler_wall_x_start = map_max_x_content 
    filler_wall_width = game_map_total_width_pixels - filler_wall_x_start
    
    if filler_wall_width > 0:
        # These are string expressions that will be embedded into the generated code.
        # They refer to variables that will be defined IN THE GENERATED SCRIPT
        # (level_min_y_absolute, _boundary_thickness, _boundary_wall_height, _boundary_color).
        filler_wall_y_expr_str = "level_min_y_absolute - _boundary_thickness"
        filler_wall_height_expr_str = "_boundary_wall_height" 
        
        script_content_parts.extend([
            "    # Filler wall on the right to ensure no empty background padding",
            f"    platforms.add(Platform({filler_wall_x_start}, {filler_wall_y_expr_str}, {filler_wall_width}, {filler_wall_height_expr_str}, _boundary_color, platform_type='wall'))"
        ])
        
        # For logging, calculate approximate values based on exporter's context for reference
        # These use constants C available in the exporter.
        log_calculated_boundary_thickness = C.TILE_SIZE * 2
        log_calculated_filler_wall_y = game_level_min_y_absolute - log_calculated_boundary_thickness
        log_calculated_filler_wall_height = (game_level_max_y_absolute - game_level_min_y_absolute) + (2 * log_calculated_boundary_thickness)
        log_boundary_color_value_for_debug = getattr(C, 'DARK_GRAY', (50,50,50))

        logger.debug(f"Code for right-side filler wall generated: x={filler_wall_x_start}, "
                     f"y_expr='{filler_wall_y_expr_str}', w={filler_wall_width}, "
                     f"h_expr='{filler_wall_height_expr_str}', color_var_name='_boundary_color'")
        logger.debug(f"Approximate calculated values for filler wall (for logging ref): "
                     f"y_val_approx={log_calculated_filler_wall_y}, h_val_approx={log_calculated_filler_wall_height}, color_val_approx={log_boundary_color_value_for_debug}")
    
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
    py_filepath = editor_state.current_map_filename
    logger.debug(f"Final .py script content (first 500 chars):\n{script_content[:500]}...")

    try:
        with open(py_filepath, "w") as f:
            f.write(script_content)
        success_msg = f"Map exported to game script: {os.path.basename(py_filepath)}"
        logger.info(success_msg)
        editor_state.set_status_message(success_msg)
        editor_state.unsaved_changes = False
        logger.debug("unsaved_changes set to False after .py export.")
        return True
    except IOError as e:
        error_msg = f"IOError exporting map to .py '{py_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error during .py export to '{py_filepath}': {e}"
        logger.error(error_msg, exc_info=True)
        traceback.print_exc()

    editor_state.set_status_message(error_msg, 4)
    return False


def delete_map_files(editor_state: EditorState, json_filepath: str) -> bool:
    logger.info(f"Attempting to delete map files for: {json_filepath}")
    if not json_filepath.endswith(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION):
        msg = f"Invalid file type for deletion: {json_filepath}. Expected .json"
        logger.error(msg)
        editor_state.set_status_message(msg, 3)
        return False

    map_name_base = os.path.basename(json_filepath).replace(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION, "")
    py_filename = map_name_base + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    py_filepath = os.path.join(os.path.dirname(json_filepath), py_filename)

    deleted_json = False
    deleted_py = False
    action_performed_json = False
    action_performed_py = False

    try:
        if os.path.exists(json_filepath):
            action_performed_json = True
            os.remove(json_filepath)
            logger.info(f"Deleted editor map file: {json_filepath}")
            deleted_json = True
        else:
            logger.warning(f"Editor map file not found for deletion: {json_filepath}")
    except OSError as e:
        action_performed_json = True 
        msg = f"Error deleting editor map file '{json_filepath}': {e}"
        logger.error(msg, exc_info=True)
        editor_state.set_status_message(msg, 4)

    try:
        if os.path.exists(py_filepath):
            action_performed_py = True
            os.remove(py_filepath)
            logger.info(f"Deleted game level file: {py_filepath}")
            deleted_py = True
        else:
            logger.warning(f"Game level file not found for deletion: {py_filepath}")
    except OSError as e:
        action_performed_py = True
        msg = f"Error deleting game level file '{py_filepath}': {e}"
        logger.error(msg, exc_info=True)
        editor_state.set_status_message(msg, 4)


    if deleted_json and deleted_py:
        editor_state.set_status_message(f"Map '{map_name_base}' JSON and PY files deleted.", 3)
        return True
    elif deleted_json:
        editor_state.set_status_message(f"Map '{map_name_base}' JSON file deleted. PY not found or failed to delete.", 3)
        return True 
    elif deleted_py:
         editor_state.set_status_message(f"Map '{map_name_base}' PY file deleted. JSON not found or failed to delete.", 3)
         return True 
    elif not action_performed_json and not action_performed_py: 
        editor_state.set_status_message(f"Map '{map_name_base}' files not found.", 2)
        return True 
    elif (action_performed_json and not deleted_json) or \
         (action_performed_py and not deleted_py): 
        editor_state.set_status_message(f"Failed to delete one or more files for map '{map_name_base}'. Check logs.", 4)
        return False
    else: 
        editor_state.set_status_message(f"Deletion status unclear for map '{map_name_base}'. Check logs.", 3)
        return False