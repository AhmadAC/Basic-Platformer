# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
VERSION 2.3.5 (Semicolons removed, identical logic to 2.3.4)
"""
import sys
import os
import json
import traceback
import re
from typing import Optional, Dict, List, Tuple, Any
import logging

# Conditional imports
if __name__ == "__main__" or not __package__:
    current_script_dir_for_main = os.path.dirname(os.path.abspath(__file__))
    project_root_for_main = os.path.dirname(current_script_dir_for_main)
    if project_root_for_main not in sys.path:
        sys.path.insert(0, project_root_for_main)
    try:
        if not __package__:
            import editor_config as ED_CONFIG
            from editor_state import EditorState
            import editor_history
        else:
            # This block executes when editor_map_utils is imported as part of the 'editor' package
            from . import editor_config as ED_CONFIG
            from .editor_state import EditorState
            from . import editor_history
        import constants as C # Assumes constants.py is in the project root
    except ImportError as e:
        print(f"ERROR (editor_map_utils import block): Could not perform imports: {e}")
        print(f"  Current sys.path: {sys.path}")
        print(f"  __package__ value: {__package__}")
        print(f"  __name__ value: {__name__}")
        # Fallback classes
        class ED_CONFIG_FALLBACK:
            GAME_LEVEL_FILE_EXTENSION = ".py"
            LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
            BASE_GRID_SIZE = 40
            DEFAULT_MAP_WIDTH_TILES = 30
            DEFAULT_MAP_HEIGHT_TILES = 20
            DEFAULT_BACKGROUND_COLOR_TUPLE = (173,216,230)
            MAPS_DIRECTORY="maps"
            EDITOR_PALETTE_ASSETS = {
                "platform_wall_gray": {"game_type_id": "platform_wall_gray", "base_color_tuple": (128,128,128)},
                "player1_spawn": {"game_type_id": "player1_spawn"}, "player2_spawn": {"game_type_id": "player2_spawn"},
                "player3_spawn": {"game_type_id": "player3_spawn"}, "player4_spawn": {"game_type_id": "player4_spawn"}
            }
        ED_CONFIG = ED_CONFIG_FALLBACK()
        class EditorState: pass # type: ignore
        class editor_history: # type: ignore
            @staticmethod
            def get_map_snapshot(state): return {}
        class FallbackConstants: # type: ignore
            TILE_SIZE = 40; GRAY = (128,128,128); DARK_GREEN=(0,100,0); ORANGE_RED=(255,69,0)
            DARK_GRAY=(50,50,50); LIGHT_BLUE=(173,216,230); MAGENTA=(255,0,255)
            EDITOR_SCREEN_INITIAL_WIDTH=1000; MAPS_DIR = "maps"
            LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"; GAME_LEVEL_FILE_EXTENSION = ".py"
        C = FallbackConstants()
        if not hasattr(ED_CONFIG, 'LEVEL_EDITOR_SAVE_FORMAT_EXTENSION'): ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = C.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # type: ignore
        if not hasattr(ED_CONFIG, 'GAME_LEVEL_FILE_EXTENSION'): ED_CONFIG.GAME_LEVEL_FILE_EXTENSION = C.GAME_LEVEL_FILE_EXTENSION # type: ignore
else: # This path should be taken when imported as part of the 'editor' package
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_history
    import constants as C # Assumes constants.py is in the project root

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# --- Helper functions ---
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
    if not clean_map_name:
        clean_map_name = "untitled_map"
        logger.warning("map_name empty, defaulting to 'untitled_map'")

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

    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        maps_abs_dir = os.path.join(project_root, maps_abs_dir)
        logger.debug(f"Derived absolute maps directory: {maps_abs_dir}")

    editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename)
    editor_state.current_json_filename = os.path.join(maps_abs_dir, json_filename)

    gs = float(editor_state.grid_size)

    border_asset_key = "platform_wall_gray"
    border_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(border_asset_key)
    if border_asset_data:
        border_game_type_id = border_asset_data.get("game_type_id", border_asset_key)
        border_color_tuple = border_asset_data.get("base_color_tuple", getattr(C, 'GRAY', (128,128,128)))
        for i in range(map_width_tiles):
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": 0, "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": int(gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
        for i in range(map_width_tiles):
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": int((map_height_tiles - 1) * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": int((map_height_tiles - 2) * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
        for i in range(2, map_height_tiles - 2):
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": 0, "world_y": int(i * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(gs), "world_y": int(i * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
        for i in range(2, map_height_tiles - 2):
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int((map_width_tiles - 1) * gs), "world_y": int(i * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
            editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int((map_width_tiles - 2) * gs), "world_y": int(i * gs),"game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
    else:
        logger.error(f"Asset key '{border_asset_key}' for default border not found. Border not added.")

    spawn_y = int((map_height_tiles - 3) * gs)
    spawn_keys_default = ["player1_spawn", "player2_spawn"]
    for i, p_spawn_key in enumerate(spawn_keys_default):
        spawn_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(p_spawn_key)
        if spawn_asset_data:
            spawn_game_type_id = spawn_asset_data.get("game_type_id", p_spawn_key)
            default_props = {}
            if spawn_game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
                default_props = {k: v_def["default"] for k, v_def in ED_CONFIG.EDITABLE_ASSET_VARIABLES[spawn_game_type_id].items()}
            editor_state.placed_objects.append({
                "asset_editor_key": p_spawn_key, "world_x": int((2 + i*2) * gs), "world_y": spawn_y,
                "game_type_id": spawn_game_type_id, "properties": default_props
            })
        else:
            logger.warning(f"Default spawn asset key '{p_spawn_key}' not found. Player {i+1} spawn not added by default.")
    editor_state.undo_stack.clear()
    editor_state.redo_stack.clear()

def ensure_maps_directory_exists() -> bool:
    maps_dir_to_check = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_dir_to_check):
        maps_dir_to_check = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), maps_dir_to_check)
    if not os.path.exists(maps_dir_to_check):
        try:
            os.makedirs(maps_dir_to_check)
            return True
        except OSError as e:
            logger.error(f"Error creating maps directory {maps_dir_to_check}: {e}", exc_info=True)
            return False
    return os.path.isdir(maps_dir_to_check)

def save_map_to_json(editor_state: EditorState) -> bool:
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map": return False
    if not ensure_maps_directory_exists(): return False
    json_filepath = editor_state.current_json_filename
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir): maps_abs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), maps_abs_dir)
    expected_json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    expected_json_filepath = os.path.join(maps_abs_dir, expected_json_filename)
    if os.path.normpath(str(json_filepath)) != os.path.normpath(expected_json_filepath):
        json_filepath = expected_json_filepath
        editor_state.current_json_filename = json_filepath
    if not json_filepath: return False
    data_to_save = editor_history.get_map_snapshot(editor_state)
    try:
        with open(json_filepath, "w") as f: json.dump(data_to_save, f, indent=4)
        return True
    except Exception as e: logger.error(f"Error saving map to JSON '{json_filepath}': {e}", exc_info=True); return False

def load_map_from_json(editor_state: EditorState, json_filepath: str) -> bool:
    if not os.path.exists(json_filepath) or not os.path.isfile(json_filepath): return False
    try:
        with open(json_filepath, 'r') as f: data_snapshot = json.load(f)
        editor_history.restore_map_from_snapshot(editor_state, data_snapshot)
        maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
        if not os.path.isabs(maps_abs_dir): maps_abs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), maps_abs_dir)
        py_filename_for_state = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        editor_state.current_map_filename = os.path.join(maps_abs_dir, py_filename_for_state)
        editor_state.current_json_filename = json_filepath
        editor_state.unsaved_changes = False
        return True
    except Exception as e: logger.error(f"Error loading map from JSON '{json_filepath}': {e}", exc_info=True); return False

def _merge_rect_objects_to_data(objects_raw: List[Dict[str, Any]], object_category_name: str) -> List[Dict[str, Any]]:
    if not objects_raw: return []
    working_objects: List[Dict[str, Any]] = []
    for obj_orig in objects_raw:
        obj = obj_orig.copy()
        obj['merged'] = False
        obj.setdefault('x', 0.0); obj.setdefault('y', 0.0)
        obj.setdefault('w', float(ED_CONFIG.BASE_GRID_SIZE)); obj.setdefault('h', float(ED_CONFIG.BASE_GRID_SIZE))
        color_val = obj.get('color', getattr(C, 'MAGENTA', (255,0,255)))
        if isinstance(color_val, list) and len(color_val) == 3: obj['color'] = tuple(color_val)
        elif not (isinstance(color_val, tuple) and len(color_val) == 3): obj['color'] = getattr(C, 'MAGENTA', (255,0,255))
        obj.setdefault('type', f'generic_{object_category_name}')
        if 'image_path' in obj_orig: obj['image_path'] = obj_orig['image_path']
        working_objects.append(obj)
    horizontal_strips: List[Dict[str, Any]] = []
    key_func_h = lambda p: (str(p.get('type')), str(p.get('color')), p.get('y'), p.get('h'), str(p.get('image_path', '')), p.get('x'))
    sorted_h = sorted(working_objects, key=key_func_h)
    for i, p_base in enumerate(sorted_h):
        if p_base.get('merged'): continue
        current_strip = p_base.copy(); p_base['merged'] = True
        for j in range(i + 1, len(sorted_h)):
            p_next = sorted_h[j]
            if p_next.get('merged'): continue
            if str(p_next.get('type')) == str(current_strip.get('type')) and str(p_next.get('color')) == str(current_strip.get('color')) and \
               abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) < 1e-3 and abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) < 1e-3 and \
               abs(p_next.get('x', 0.0) - (current_strip.get('x', 0.0) + current_strip.get('w', 0.0))) < 1e-3 and \
               str(p_next.get('image_path', '')) == str(current_strip.get('image_path', '')):
                current_strip['w'] += p_next.get('w', 0.0); p_next['merged'] = True
            elif abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) >= 1e-3 or abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) >= 1e-3 or \
                 str(p_next.get('type')) != str(current_strip.get('type')) or str(p_next.get('color')) != str(current_strip.get('color')) or \
                 str(p_next.get('image_path', '')) != str(current_strip.get('image_path', '')): break
        horizontal_strips.append(current_strip)
    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge: strip['merged'] = False
    key_func_v = lambda s: (str(s.get('type')), str(s.get('color')), s.get('x'), s.get('w'), str(s.get('image_path', '')), s.get('y'))
    sorted_v = sorted(strips_to_merge, key=key_func_v)
    for i, s_base in enumerate(sorted_v):
        if s_base.get('merged'): continue
        current_block = s_base.copy(); s_base['merged'] = True
        for j in range(i + 1, len(sorted_v)):
            s_next = sorted_v[j]
            if s_next.get('merged'): continue
            if str(s_next.get('type')) == str(current_block.get('type')) and str(s_next.get('color')) == str(current_block.get('color')) and \
               abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) < 1e-3 and abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) < 1e-3 and \
               abs(s_next.get('y', 0.0) - (current_block.get('y', 0.0) + current_block.get('h', 0.0))) < 1e-3 and \
               str(s_next.get('image_path', '')) == str(current_block.get('image_path', '')):
                current_block['h'] += s_next.get('h', 0.0); s_next['merged'] = True
            elif abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) >= 1e-3 or abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) >= 1e-3 or \
                 str(s_next.get('type')) != str(current_block.get('type')) or str(s_next.get('color')) != str(current_block.get('color')) or \
                 str(s_next.get('image_path', '')) != str(current_block.get('image_path', '')): break
        current_block.pop('merged', None)
        final_entry = {'rect': (current_block.get('x'), current_block.get('y'), current_block.get('w'), current_block.get('h')), 'type': current_block.get('type'), 'color': current_block.get('color'), 'properties': current_block.get('properties', {})}
        if 'image_path' in current_block: final_entry['image_path'] = current_block['image_path']
        final_blocks_data.append(final_entry)
    return final_blocks_data

def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map data. Map name: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set. Cannot export .py data file.")
        return False

    py_filepath_to_use = editor_state.current_map_filename
    maps_abs_dir = getattr(C, "MAPS_DIR", ED_CONFIG.MAPS_DIRECTORY)
    if not os.path.isabs(maps_abs_dir): maps_abs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), maps_abs_dir)
    expected_py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    expected_py_filepath = os.path.join(maps_abs_dir, expected_py_filename)
    if py_filepath_to_use is None or os.path.normpath(str(py_filepath_to_use)) != os.path.normpath(expected_py_filepath):
        py_filepath_to_use = expected_py_filepath
        editor_state.current_map_filename = py_filepath_to_use
    if not ensure_maps_directory_exists(): logger.error(f"Maps directory issue. PY data export aborted."); return False
    game_function_name = f"load_map_{editor_state.map_name_for_function}"

    platforms_data_raw: List[Dict[str, Any]] = []
    ladders_data_raw: List[Dict[str, Any]] = []
    hazards_data_raw: List[Dict[str, Any]] = []
    background_tiles_data_raw: List[Dict[str, Any]] = []
    enemies_list_export: List[Dict[str, Any]] = []
    items_list_export: List[Dict[str, Any]] = []
    statue_list_export: List[Dict[str, Any]] = []

    default_spawn_world_x = (editor_state.map_width_tiles // 2) * ts + ts / 2.0
    default_spawn_world_y = (editor_state.map_height_tiles - 3) * ts

    player_start_pos_p1: Optional[Tuple[float, float]] = None; player1_spawn_props: Dict[str, Any] = {}
    player_start_pos_p2: Optional[Tuple[float, float]] = None; player2_spawn_props: Dict[str, Any] = {}
    player_start_pos_p3: Optional[Tuple[float, float]] = None; player3_spawn_props: Dict[str, Any] = {}
    player_start_pos_p4: Optional[Tuple[float, float]] = None; player4_spawn_props: Dict[str, Any] = {}

    p1_spawn_game_type_id = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player1_spawn", {}).get("game_type_id", "player1_spawn")
    p2_spawn_game_type_id = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player2_spawn", {}).get("game_type_id", "player2_spawn")
    p3_spawn_game_type_id = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player3_spawn", {}).get("game_type_id", "player3_spawn")
    p4_spawn_game_type_id = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player4_spawn", {}).get("game_type_id", "player4_spawn")

    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []
    for obj_data in editor_state.placed_objects:
        object_game_type_id = str(obj_data.get("game_type_id", "unknown"))
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        asset_key = str(obj_data.get("asset_editor_key", ""))
        override_color_tuple = obj_data.get("override_color")
        obj_props = obj_data.get("properties", {})
        if not all([object_game_type_id != "unknown", wx is not None, wy is not None, asset_key != ""]): continue
        asset_entry = editor_state.assets_palette.get(asset_key)
        if not asset_entry: continue
        obj_w, obj_h = float(ts), float(ts); default_color_from_asset_tuple = getattr(C, 'GRAY', (128,128,128))
        if asset_entry.get("surface_params"):
            dims_color_tuple = asset_entry["surface_params"]
            if isinstance(dims_color_tuple, tuple) and len(dims_color_tuple) == 3: w_param, h_param, c_param = dims_color_tuple; obj_w, obj_h = float(w_param), float(h_param); default_color_from_asset_tuple = c_param
        elif asset_entry.get("original_size_pixels"): orig_w_tuple_val, orig_h_tuple_val = asset_entry["original_size_pixels"]; obj_w, obj_h = float(orig_w_tuple_val), float(orig_h_tuple_val)
        final_color_for_export = tuple(override_color_tuple) if isinstance(override_color_tuple, list) else (override_color_tuple if isinstance(override_color_tuple, tuple) else default_color_from_asset_tuple)
        export_x, export_y = float(wx), float(wy)
        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})
        is_platform_type = any(pt in object_game_type_id.lower() for pt in ["platform", "wall", "ground", "ledge"]); is_ladder_type = "ladder" in object_game_type_id.lower()
        is_hazard_type = "hazard" in object_game_type_id.lower(); is_statue_type = "object_stone" in object_game_type_id.lower(); is_background_tile_type = asset_entry.get("category") == "background_tile"

        if is_platform_type: platforms_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': object_game_type_id, 'properties': obj_props})
        elif is_ladder_type: ladders_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': 'ladder', 'properties': obj_props})
        elif is_hazard_type: hazard_color_to_export = getattr(C, 'ORANGE_RED', (255, 69, 0)) if "lava" in object_game_type_id.lower() else final_color_for_export; hazards_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': hazard_color_to_export, 'type': object_game_type_id, 'properties': obj_props})
        elif is_background_tile_type: background_tiles_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': object_game_type_id, 'image_path': asset_entry.get("source_file"), 'properties': obj_props})
        elif is_statue_type: statue_list_export.append(_create_statue_spawn_data(obj_data.get("unique_id", f"statue_{len(statue_list_export)}"), (export_x + obj_w / 2.0, export_y + obj_h / 2.0), props=obj_props))
        elif object_game_type_id == p1_spawn_game_type_id: player_start_pos_p1 = (export_x + obj_w / 2.0, export_y + obj_h); player1_spawn_props = obj_props.copy()
        elif object_game_type_id == p2_spawn_game_type_id: player_start_pos_p2 = (export_x + obj_w / 2.0, export_y + obj_h); player2_spawn_props = obj_props.copy()
        elif object_game_type_id == p3_spawn_game_type_id: player_start_pos_p3 = (export_x + obj_w / 2.0, export_y + obj_h); player3_spawn_props = obj_props.copy()
        elif object_game_type_id == p4_spawn_game_type_id: player_start_pos_p4 = (export_x + obj_w / 2.0, export_y + obj_h); player4_spawn_props = obj_props.copy()
        elif "enemy" in object_game_type_id.lower(): enemies_list_export.append(_create_enemy_spawn_data((export_x + obj_w / 2.0, export_y + obj_h), object_game_type_id, props=obj_props))
        elif any(item_key in object_game_type_id.lower() for item_key in ["chest", "item", "collectible"]): items_list_export.append(_create_item_spawn_data(object_game_type_id, (export_x + obj_w / 2.0, export_y + obj_h / 2.0), props=obj_props))

    if player_start_pos_p1 is None: player_start_pos_p1 = (default_spawn_world_x, default_spawn_world_y); logger.warning("Player 1 spawn not found, using default.")
    if player_start_pos_p2 is None: player_start_pos_p2 = (player_start_pos_p1[0] + ts*2 if player_start_pos_p1 else default_spawn_world_x + ts*2, player_start_pos_p1[1] if player_start_pos_p1 else default_spawn_world_y); logger.warning("Player 2 spawn not found, using default relative to P1.")
    if player_start_pos_p3 is None: logger.info("Player 3 spawn not found on map. Exporting as None.")
    if player_start_pos_p4 is None: logger.info("Player 4 spawn not found on map. Exporting as None.")

    platforms_list_export = _merge_rect_objects_to_data(platforms_data_raw, "platform")
    ladders_list_export = _merge_rect_objects_to_data(ladders_data_raw, "ladder")
    hazards_list_export = _merge_rect_objects_to_data(hazards_data_raw, "hazard")
    background_tiles_list_export = _merge_rect_objects_to_data(background_tiles_data_raw, "background_tile")

    map_max_y_content: float
    if not all_placed_objects_rect_data_for_bounds:
        level_min_x_abs_for_camera, level_max_x_abs_for_camera = 0.0, float(editor_state.map_width_tiles * ts)
        level_min_y_abs_for_camera, level_max_y_abs_for_camera = 0.0, float(editor_state.map_height_tiles * ts)
        map_max_y_content = level_max_y_abs_for_camera
    else:
        level_min_x_abs_for_camera = min(r['x'] for r in all_placed_objects_rect_data_for_bounds); level_max_x_abs_for_camera = max(r['x'] + r['width'] for r in all_placed_objects_rect_data_for_bounds)
        level_min_y_abs_for_camera = min(r['y'] for r in all_placed_objects_rect_data_for_bounds); level_max_y_abs_for_camera = max(r['y'] + r['height'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_y_content = level_max_y_abs_for_camera
    level_pixel_width_for_camera = level_max_x_abs_for_camera - level_min_x_abs_for_camera
    main_ground_y_ref = map_max_y_content; ground_platform_height_ref = float(C.TILE_SIZE)
    all_non_boundary_platforms = [p for p in platforms_list_export if "boundary" not in p.get('type', '')]
    if all_non_boundary_platforms:
        lowest_platform_top_y = max(p['rect'][1] for p in all_non_boundary_platforms)
        candidate_ground_platforms = [p for p in all_non_boundary_platforms if abs(p['rect'][1] - lowest_platform_top_y) < (ts * 0.1)]
        if candidate_ground_platforms: widest_candidate = max(candidate_ground_platforms, key=lambda p: p['rect'][2]); main_ground_y_ref = widest_candidate['rect'][1]; ground_platform_height_ref = widest_candidate['rect'][3]
        elif all_non_boundary_platforms:
            main_ground_y_ref = lowest_platform_top_y; first_ground_plat = next((p for p in all_non_boundary_platforms if abs(p['rect'][1] - main_ground_y_ref) < (ts*0.1)), None)
            if first_ground_plat: ground_platform_height_ref = first_ground_plat['rect'][3]

    final_game_data_for_script = {
        "level_name": editor_state.map_name_for_function, "background_color": editor_state.background_color,
        "player_start_pos_p1": player_start_pos_p1, "player1_spawn_props": player1_spawn_props,
        "player_start_pos_p2": player_start_pos_p2, "player2_spawn_props": player2_spawn_props,
        "player_start_pos_p3": player_start_pos_p3, "player3_spawn_props": player3_spawn_props,
        "player_start_pos_p4": player_start_pos_p4, "player4_spawn_props": player4_spawn_props,
        "platforms_list": platforms_list_export, "ladders_list": ladders_list_export,
        "hazards_list": hazards_list_export, "background_tiles_list": background_tiles_list_export,
        "enemies_list": enemies_list_export, "items_list": items_list_export,
        "statues_list": statue_list_export, "level_pixel_width": level_pixel_width_for_camera,
        "level_min_x_absolute": level_min_x_abs_for_camera, "level_min_y_absolute": level_min_y_abs_for_camera,
        "level_max_y_absolute": level_max_y_abs_for_camera, "ground_level_y_ref": main_ground_y_ref,
        "ground_platform_height_ref": ground_platform_height_ref,
    }
    for key_default_list in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list", "enemies_list", "items_list", "statues_list"]:
        final_game_data_for_script.setdefault(key_default_list, [])

    script_content_parts = [f"# Level Data: {editor_state.map_name_for_function}", "# Generated by Platformer Level Editor", "", f"def {game_function_name}():", "    game_data = {"]
    for data_key, data_value in final_game_data_for_script.items(): script_content_parts.append(f"        {repr(data_key)}: {repr(data_value)},")
    script_content_parts.extend(["    }", "    return game_data", "", "if __name__ == '__main__':", f"    data = {game_function_name}()", "    import json", "    print(json.dumps(data, indent=4))"])
    script_content = "\n".join(script_content_parts)
    try:
        with open(str(py_filepath_to_use), "w") as f: f.write(script_content)
        logger.info(f"Map data exported to game script: {os.path.basename(str(py_filepath_to_use))}")
        editor_state.unsaved_changes = False
        return True
    except Exception as e: logger.error(f"Error exporting map data to .py '{py_filepath_to_use}': {e}", exc_info=True); return False

def delete_map_files(editor_state: EditorState, json_filepath_to_delete: str) -> bool: # (Unchanged)
    if not json_filepath_to_delete.endswith(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION): return False
    map_name_base = os.path.splitext(os.path.basename(json_filepath_to_delete))[0]
    py_filename_to_delete = map_name_base + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
    py_filepath_to_delete = os.path.join(os.path.dirname(json_filepath_to_delete), py_filename_to_delete)
    deleted_json, deleted_py = False, False
    try:
        if os.path.exists(json_filepath_to_delete): os.remove(json_filepath_to_delete); deleted_json = True
        if os.path.exists(py_filepath_to_delete): os.remove(py_filepath_to_delete); deleted_py = True
        return deleted_json or deleted_py
    except OSError as e: logger.error(f"Error deleting map files for '{map_name_base}': {e}", exc_info=True); return False

def batch_fix_map_files_repr_key_issue(maps_directory: str): # (Unchanged)
    if not os.path.isdir(maps_directory): return
    fixed_count = 0; error_count = 0
    for filename in os.listdir(maps_directory):
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = os.path.join(maps_directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
                pattern = r"repr\(([^)]+)\)\s*:"
                modified_content = content; found_match = False
                def replace_func(match):
                    nonlocal found_match; captured_key_name = match.group(1).strip()
                    key_as_string_literal = captured_key_name[1:-1] if (captured_key_name.startswith("'") and captured_key_name.endswith("'")) or (captured_key_name.startswith('"') and captured_key_name.endswith('"')) else captured_key_name
                    found_match = True; return f'"{key_as_string_literal}":'
                modified_content = re.sub(pattern, replace_func, content)
                if found_match:
                    with open(filepath, 'w', encoding='utf-8') as f: f.write(modified_content)
                    fixed_count += 1
            except Exception as e: logger.error(f"Error processing file {filename}: {e}", exc_info=True); error_count += 1
    logger.info(f"Batch fix complete. Fixed: {fixed_count} files. Errors: {error_count} files.")

if __name__ == "__main__": # (Unchanged)
    print("Running editor_map_utils.py directly for batch map file fixing...")
    if not logging.getLogger().hasHandlers(): logging.basicConfig(level=logging.INFO, format='%(levelname)s (editor_map_utils utility): %(message)s')
    _current_script_dir = os.path.dirname(os.path.abspath(__file__)); _project_root_for_main_script = os.path.dirname(_current_script_dir)
    maps_dir_name_from_const = getattr(C, "MAPS_DIR", "maps"); maps_dir_to_fix = maps_dir_name_from_const
    if not os.path.isabs(maps_dir_to_fix): maps_dir_to_fix = os.path.join(_project_root_for_main_script, maps_dir_to_fix)
    if not os.path.isdir(maps_dir_to_fix): print(f"ERROR: Maps directory does not exist: {maps_dir_to_fix}")
    else: print(f"Attempting to batch fix map files in: {maps_dir_to_fix}"); batch_fix_map_files_repr_key_issue(maps_dir_to_fix); print("Batch fixing process finished.")