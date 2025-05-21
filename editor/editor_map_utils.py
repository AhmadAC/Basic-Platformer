# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
VERSION 2.2.6 (Refined conditional imports for standalone execution)
"""
import sys
import os
import json
import traceback
import re # For fixing map files
from typing import Optional, Dict, List, Tuple, Any
import logging

# Conditional imports based on how the script is run
if __name__ == "__main__" or not __package__:
    # Script is run directly or `python -m editor.editor_map_utils` was not used
    # We need to adjust sys.path to find sibling modules in 'editor' and project root 'constants'
    current_script_dir_for_main = os.path.dirname(os.path.abspath(__file__))
    project_root_for_main = os.path.dirname(current_script_dir_for_main)
    
    if project_root_for_main not in sys.path:
        sys.path.insert(0, project_root_for_main)
    if current_script_dir_for_main not in sys.path and current_script_dir_for_main != project_root_for_main : # if editor is a subdir
        sys.path.insert(0, current_script_dir_for_main) # for editor_config etc. if needed by batch fix

    # Now attempt to import, these might still fail if structure is very different
    # but this gives a better chance for standalone utility execution.
    try:
        if not __package__ : # if run as script, relative imports won't work.
            import editor_config as ED_CONFIG
            from editor_state import EditorState # Not used by batch fix but part of original structure
            import editor_history # Not used by batch fix
        else: # if run as part of a package (e.g. python -m editor.editor_map_utils)
            from . import editor_config as ED_CONFIG
            from .editor_state import EditorState
            from . import editor_history
    except ImportError as e:
        print(f"WARNING (editor_map_utils standalone/module context): Could not perform some relative imports: {e}")
        # Minimal fallback for ED_CONFIG attributes needed by batch fix or export if called standalone
        class ED_CONFIG_FALLBACK:
            GAME_LEVEL_FILE_EXTENSION = ".py"
            LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
            BASE_GRID_SIZE = 40 # Example
            DEFAULT_MAP_WIDTH_TILES = 30
            DEFAULT_MAP_HEIGHT_TILES = 20
            DEFAULT_BACKGROUND_COLOR_TUPLE = (173,216,230)
            MAPS_DIRECTORY="maps"
        ED_CONFIG = ED_CONFIG_FALLBACK() # type: ignore
        # Define dummy EditorState and editor_history if they are truly needed by functions
        # called from __main__, but batch_fix should be self-contained or take simple args.
        class EditorState: pass
        class editor_history:
            @staticmethod
            def get_map_snapshot(state): return {}


    try:
        import constants as C
    except ImportError as e_proj_imp:
        print(f"EDITOR_MAP_UTILS CRITICAL Error importing project constants: {e_proj_imp}")
        class FallbackConstants:
            TILE_SIZE = 40; GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0)
            DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230); MAGENTA=(255,0,255)
            EDITOR_SCREEN_INITIAL_WIDTH=1000
            MAPS_DIR = "maps"
            LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
            GAME_LEVEL_FILE_EXTENSION = ".py"
        C = FallbackConstants()
        if not hasattr(ED_CONFIG, 'LEVEL_EDITOR_SAVE_FORMAT_EXTENSION'):
            ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = C.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # type: ignore
        if not hasattr(ED_CONFIG, 'GAME_LEVEL_FILE_EXTENSION'):
            ED_CONFIG.GAME_LEVEL_FILE_EXTENSION = C.GAME_LEVEL_FILE_EXTENSION # type: ignore

else:
    # Script is imported as part of a package (normal execution path)
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_history
    import constants as C


logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Ensure logger has a handler if not configured by parent
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO) # Default to INFO for this utility script if run alone
    logger.propagate = False


# --- Helper functions for creating data dictionaries ---
def _create_platform_data(x: float, y: float, w: float, h: float, color: Tuple[int,int,int], p_type: str, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'rect': (float(x), float(y), float(w), float(h)), 'color': color, 'type': p_type, 'properties': props or {}}

def _create_ladder_data(x: float, y: float, w: float, h: float) -> Dict[str, Any]:
    return {'rect': (float(x), float(y), float(w), float(h))}

def _create_hazard_data(h_type: str, x: float, y: float, w: float, h: float, color: Tuple[int,int,int]) -> Dict[str, Any]:
    return {'type': h_type, 'rect': (float(x), float(y), float(w), float(h)), 'color': color}

def _create_background_tile_data(x: float, y: float, w: float, h: float, color: Tuple[int,int,int], tile_type: str, image_path: Optional[str]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    data = {'rect': (float(x), float(y), float(w), float(h)), 'color': color, 'type': tile_type, 'properties': props or {}}
    if image_path:
        data['image_path'] = image_path
    return data

def _create_enemy_spawn_data(start_pos_tuple: Tuple[float,float], enemy_type_str: str, patrol_rect_data_dict: Optional[Dict[str,float]]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    data = {'start_pos': start_pos_tuple, 'type': enemy_type_str, 'properties': props or {}}
    if patrol_rect_data_dict:
        data['patrol_rect_data'] = patrol_rect_data_dict
    return data

def _create_item_spawn_data(item_type_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'type': item_type_str, 'pos': pos_tuple, 'properties': props or {}}

def _create_statue_spawn_data(statue_id_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'id': statue_id_str, 'pos': pos_tuple, 'properties': props or {}}
# --- End Helper functions ---


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
        # Corrected assumption: __file__ in editor_map_utils.py is inside 'editor' directory
        current_dir = os.path.dirname(os.path.abspath(__file__)) # .../project_root/editor
        project_root = os.path.dirname(current_dir)              # .../project_root
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)
        logger.debug(f"Derived absolute maps directory: {maps_abs_dir}")

    editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename)
    editor_state.current_json_filename = os.path.join(maps_abs_dir, json_filename)

    editor_state.undo_stack.clear(); editor_state.redo_stack.clear()
    logger.info(f"Editor state initialized for new map: '{editor_state.map_name_for_function}'. PY: '{editor_state.current_map_filename}', JSON: '{editor_state.current_json_filename}'")


def ensure_maps_directory_exists() -> bool:
    maps_dir_to_check = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_dir_to_check):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)      
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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)

    expected_json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    expected_json_filepath = os.path.join(maps_abs_dir, expected_json_filename)

    if os.path.normpath(str(json_filepath)) != os.path.normpath(expected_json_filepath): 
        json_filepath = expected_json_filepath
        editor_state.current_json_filename = json_filepath
        logger.warning(f"JSON filepath re-derived for save: '{json_filepath}'")
    
    if not json_filepath: 
        logger.error("JSON filepath is None after derivation. Cannot save."); return False
        
    logger.debug(f"Attempting to save JSON to: '{json_filepath}'")
    data_to_save = editor_history.get_map_snapshot(editor_state)

    try:
        with open(json_filepath, "w") as f: json.dump(data_to_save, f, indent=4)
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
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
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
    # ... (Implementation remains the same, no changes needed for this part based on the error) ...
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
        
        obj.setdefault('type', f'generic_{object_category_name}')
        working_objects.append(obj)

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
            'properties': current_block.get('properties', {}) 
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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)

    expected_py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    expected_py_filepath = os.path.join(maps_abs_dir, expected_py_filename)

    if py_filepath_to_use is None or os.path.normpath(str(py_filepath_to_use)) != os.path.normpath(expected_py_filepath):
        py_filepath_to_use = expected_py_filepath
        editor_state.current_map_filename = py_filepath_to_use 
        logger.warning(f"PY data filepath for export re-derived/set to: '{py_filepath_to_use}'")

    if not ensure_maps_directory_exists():
        logger.error(f"Maps directory issue. PY data export aborted."); return False

    game_function_name = f"load_map_{editor_state.map_name_for_function}"
    logger.debug(f"Exporting to function '{game_function_name}' in file '{py_filepath_to_use}'")

    platforms_data_raw: List[Dict[str, Any]] = []
    ladders_data_raw: List[Dict[str, Any]] = []
    hazards_data_raw: List[Dict[str, Any]] = []
    background_tiles_data_raw: List[Dict[str, Any]] = []
    
    enemies_list_export: List[Dict[str, Any]] = []
    items_list_export: List[Dict[str, Any]] = []
    statue_list_export: List[Dict[str, Any]] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts / 2.0
    default_spawn_world_y = (editor_state.map_height_tiles - 2) * ts 
    
    player_start_pos_p1: Optional[Tuple[float, float]] = None
    player_start_pos_p2: Optional[Tuple[float, float]] = None
    player1_spawn_props: Dict[str, Any] = {} 
    player2_spawn_props: Dict[str, Any] = {} 
    
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
             orig_w_tuple, orig_h_tuple = asset_entry["original_size_pixels"]
             obj_w, obj_h = float(orig_w_tuple), float(orig_h_tuple)
        
        final_color_for_export = tuple(override_color_tuple) if isinstance(override_color_tuple, list) else \
                                 (override_color_tuple if isinstance(override_color_tuple, tuple) else default_color_from_asset_tuple)
        export_x, export_y = float(wx), float(wy)
        
        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})
        
        is_platform_type = any(pt in game_id.lower() for pt in ["platform", "wall", "ground", "ledge"])
        is_ladder_type = "ladder" in game_id.lower()
        is_hazard_type = "hazard" in game_id.lower()
        is_statue_type = "object_stone" in game_id.lower()
        is_background_tile_type = asset_entry.get("category") == "background_tile"

        if is_platform_type:
            platform_game_type = game_id 
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
        elif is_background_tile_type:
            bg_tile_game_type = game_id
            bg_tile_image_path = asset_entry.get("source_file")
            background_tiles_data_raw.append({
                'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h,
                'color': final_color_for_export, 'type': bg_tile_game_type,
                'image_path': bg_tile_image_path,
                'properties': obj_props
            })
        elif is_statue_type:
            statue_id = obj_data.get("unique_id", f"statue_{len(statue_list_export)}")
            statue_pos = (export_x + obj_w / 2.0, export_y + obj_h / 2.0)
            statue_list_export.append(_create_statue_spawn_data(statue_id, statue_pos, props=obj_props))
        elif game_id == "player1_spawn":
            player_start_pos_p1 = (export_x + obj_w / 2.0, export_y + obj_h)
            player1_spawn_props = obj_props.copy() 
        elif game_id == "player2_spawn":
            player_start_pos_p2 = (export_x + obj_w / 2.0, export_y + obj_h)
            player2_spawn_props = obj_props.copy() 
        elif "enemy" in game_id.lower():
            enemy_type_for_game = game_id 
            spawn_pos = (export_x + obj_w / 2.0, export_y + obj_h)
            enemies_list_export.append(_create_enemy_spawn_data(spawn_pos, enemy_type_for_game, props=obj_props))
        elif any(item_key in game_id.lower() for item_key in ["chest", "item", "collectible"]):
            item_type_for_game = game_id
            item_pos = (export_x + obj_w / 2.0, export_y + obj_h / 2.0) 
            items_list_export.append(_create_item_spawn_data(item_type_for_game, item_pos, props=obj_props))

    if player_start_pos_p1 is None: player_start_pos_p1 = (default_spawn_world_x, default_spawn_world_y)
    if player_start_pos_p2 is None: player_start_pos_p2 = (player_start_pos_p1[0] + ts*2, player_start_pos_p1[1])


    platforms_list_export = _merge_rect_objects_to_data(platforms_data_raw, "platform")
    ladders_list_export = _merge_rect_objects_to_data(ladders_data_raw, "ladder")
    hazards_list_export = _merge_rect_objects_to_data(hazards_data_raw, "hazard")
    background_tiles_list_export: List[Dict[str, Any]] = []
    for bg_raw in background_tiles_data_raw:
        background_tiles_list_export.append(
            _create_background_tile_data(
                bg_raw['x'], bg_raw['y'], bg_raw['w'], bg_raw['h'],
                bg_raw['color'], bg_raw['type'], bg_raw.get('image_path'), bg_raw.get('properties', {})
            )
        )

    if not all_placed_objects_rect_data_for_bounds:
        map_min_x_content = 0.0; map_max_x_content = float(editor_state.map_width_tiles * ts)
        map_min_y_content = 0.0; map_max_y_content = float(editor_state.map_height_tiles * ts)
        logger.warning("Exporting an empty map. Using editor canvas dimensions for boundaries.")
    else:
        map_min_x_content = min(r['x'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_x_content = max(r['x'] + r['width'] for r in all_placed_objects_rect_data_for_bounds)
        map_min_y_content = min(r['y'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_y_content = max(r['y'] + r['height'] for r in all_placed_objects_rect_data_for_bounds)
    
    _boundary_thickness_val = float(getattr(C, 'TILE_SIZE', 40))
    visual_padding_around_content = float(C.TILE_SIZE) * 1.0 

    level_min_x_abs_for_camera = map_min_x_content - visual_padding_around_content - _boundary_thickness_val
    level_max_x_abs_for_camera = map_max_x_content + visual_padding_around_content + _boundary_thickness_val
    level_min_y_abs_for_camera = map_min_y_content - visual_padding_around_content - _boundary_thickness_val
    level_max_y_abs_for_camera = map_max_y_content + visual_padding_around_content + _boundary_thickness_val
    
    level_pixel_width_for_camera = level_max_x_abs_for_camera - level_min_x_abs_for_camera

    _boundary_color_tuple = getattr(C, 'DARK_GRAY', (50,50,50))
    
    boundary_platforms_data = [
        _create_platform_data(level_min_x_abs_for_camera, level_min_y_abs_for_camera, 
                              level_pixel_width_for_camera, _boundary_thickness_val, 
                              _boundary_color_tuple, "boundary_wall_top"),
        _create_platform_data(level_min_x_abs_for_camera, level_max_y_abs_for_camera - _boundary_thickness_val, 
                              level_pixel_width_for_camera, _boundary_thickness_val, 
                              _boundary_color_tuple, "boundary_wall_bottom"),
        _create_platform_data(level_min_x_abs_for_camera, level_min_y_abs_for_camera + _boundary_thickness_val, 
                              _boundary_thickness_val, level_max_y_abs_for_camera - level_min_y_abs_for_camera - 2 * _boundary_thickness_val, 
                              _boundary_color_tuple, "boundary_wall_left"),
        _create_platform_data(level_max_x_abs_for_camera - _boundary_thickness_val, level_min_y_abs_for_camera + _boundary_thickness_val, 
                              _boundary_thickness_val, level_max_y_abs_for_camera - level_min_y_abs_for_camera - 2 * _boundary_thickness_val, 
                              _boundary_color_tuple, "boundary_wall_right"),
    ]
    platforms_list_export.extend(boundary_platforms_data)

    main_ground_y_ref = map_max_y_content 
    ground_platform_height_ref = float(C.TILE_SIZE)
    all_platforms_for_ground_check = [p for p in platforms_list_export if "boundary" not in p.get('type', '')]
    if all_platforms_for_ground_check:
        lowest_platform_top_y = max(p['rect'][1] for p in all_platforms_for_ground_check)
        candidate_ground_platforms = [p for p in all_platforms_for_ground_check if abs(p['rect'][1] - lowest_platform_top_y) < (ts * 0.1)]
        if candidate_ground_platforms:
            widest_candidate = max(candidate_ground_platforms, key=lambda p: p['rect'][2])
            main_ground_y_ref = widest_candidate['rect'][1]
            ground_platform_height_ref = widest_candidate['rect'][3]
        elif all_platforms_for_ground_check: 
            main_ground_y_ref = lowest_platform_top_y 
            first_ground_plat = next((p for p in all_platforms_for_ground_check if abs(p['rect'][1] - main_ground_y_ref) < (ts*0.1)), None)
            if first_ground_plat: ground_platform_height_ref = first_ground_plat['rect'][3]


    final_game_data_for_script = {
        "level_name": editor_state.map_name_for_function,
        "background_color": editor_state.background_color,
        "player_start_pos_p1": player_start_pos_p1,
        "player1_spawn_props": player1_spawn_props,
        "player_start_pos_p2": player_start_pos_p2,
        "player2_spawn_props": player2_spawn_props,
        "platforms_list": platforms_list_export,
        "ladders_list": ladders_list_export,
        "hazards_list": hazards_list_export,
        "background_tiles_list": background_tiles_list_export, 
        "enemies_list": enemies_list_export,
        "items_list": items_list_export,
        "statues_list": statue_list_export,
        "level_pixel_width": level_pixel_width_for_camera,
        "level_min_x_absolute": level_min_x_abs_for_camera,
        "level_min_y_absolute": level_min_y_abs_for_camera,
        "level_max_y_absolute": level_max_y_abs_for_camera,
        "ground_level_y_ref": main_ground_y_ref,
        "ground_platform_height_ref": ground_platform_height_ref,
    }
    
    for key_default_list in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list", "enemies_list", "items_list", "statues_list"]:
        final_game_data_for_script.setdefault(key_default_list, [])

    script_content_parts = [
        f"# Level Data: {editor_state.map_name_for_function}",
        "# Generated by Platformer Level Editor",
        "",
        f"def {game_function_name}():",
        "    game_data = {"
    ]
    for data_key, data_value in final_game_data_for_script.items():
        script_content_parts.append(f"        {repr(data_key)}: {repr(data_value)},")
    
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
        with open(str(py_filepath_to_use), "w") as f: f.write(script_content) 
        logger.info(f"Map data exported to game script: {os.path.basename(str(py_filepath_to_use))}")
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


def batch_fix_map_files_repr_key_issue(maps_directory: str):
    """
    Scans all .py files in the maps_directory and attempts to fix the
    `repr(key): value` issue by changing it to `"key_string": value`.
    This is a one-time utility.
    """
    logger.info(f"Starting batch fix for map files in: {maps_directory}")
    fixed_count = 0
    error_count = 0

    if not os.path.isdir(maps_directory):
        logger.error(f"Provided maps directory does not exist: {maps_directory}")
        return

    for filename in os.listdir(maps_directory):
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = os.path.join(maps_directory, filename)
            logger.debug(f"Processing map file: {filename}")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pattern = r"repr\(([^)]+)\)\s*:"
                
                modified_content = content
                found_match = False

                def replace_func(match):
                    nonlocal found_match
                    captured_key_name = match.group(1).strip()
                    if (captured_key_name.startswith("'") and captured_key_name.endswith("'")) or \
                       (captured_key_name.startswith('"') and captured_key_name.endswith('"')):
                        key_as_string_literal = captured_key_name[1:-1] 
                    else:
                        key_as_string_literal = captured_key_name
                    
                    found_match = True
                    # Ensure the key is properly quoted as a string literal for the dictionary
                    return f'"{key_as_string_literal}":'

                modified_content = re.sub(pattern, replace_func, content)

                if found_match:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    logger.info(f"Fixed `repr(key)` issue in: {filename}")
                    fixed_count += 1
                else:
                    logger.debug(f"No `repr(key):` pattern found in: {filename} (or already correct)")

            except Exception as e:
                logger.error(f"Error processing or fixing file {filename}: {e}", exc_info=True)
                error_count += 1
    
    logger.info(f"Batch fix complete. Fixed: {fixed_count} files. Errors: {error_count} files.")


if __name__ == "__main__":
    # --- This block is for when editor_map_utils.py is run directly ---
    print("Running editor_map_utils.py directly...")

    # Adjust sys.path to allow imports from the parent directory (project root)
    # and from the 'editor' package if this script is inside it.
    current_script_dir_main = os.path.dirname(os.path.abspath(__file__))
    project_root_main = os.path.dirname(current_script_dir_main) 
    
    if project_root_main not in sys.path:
        sys.path.insert(0, project_root_main)
        print(f"__main__ in editor_map_utils: Added project root '{project_root_main}' to sys.path.")

    # For the batch fix to access ED_CONFIG and C, they need to be available.
    # The conditional import at the top handles this if __name__ == "__main__".
    # We also need to ensure the logger is minimally configured for standalone execution.
    if not logging.getLogger().hasHandlers(): # Basic logger config if not already set
        logging.basicConfig(level=logging.INFO, format='%(levelname)s (editor_map_utils utility): %(message)s')
    
    # Now, it's safe to call functions that might rely on these imports.
    maps_dir_to_fix = getattr(C, "MAPS_DIR", "maps") # Get from constants or fallback
    if not os.path.isabs(maps_dir_to_fix):
        maps_dir_to_fix = os.path.join(project_root_main, maps_dir_to_fix)

    if not os.path.isdir(maps_dir_to_fix):
        print(f"ERROR: The resolved maps directory does not exist: {maps_dir_to_fix}")
        print("Please ensure the path is correct or create the directory with your .py map files.")
    else:
        print(f"Attempting to batch fix map files in: {maps_dir_to_fix}")
        batch_fix_map_files_repr_key_issue(maps_dir_to_fix)
        print("Batch fixing process finished.")