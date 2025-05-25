#################### START OF FILE: editor_map_utils.py ####################
# editor/editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
Manages map-specific folders.
VERSION 2.4.7 (Simplified Logging and Guaranteed EditorState Type Hint)
- Removed local logger setup; assumes logger is configured externally.
- Ensures EditorState is defined for type hinting even in import error scenarios.
- Ensures `is_flipped_h` is included in the exported map data.
"""
import sys
import os
import json
import traceback
import re
import shutil 
from typing import Optional, Dict, List, Tuple, Any
import logging # Keep the import for logging.getLogger

# --- Get a logger instance. It's assumed to be configured by the main application. ---
logger = logging.getLogger(__name__)

# --- Forward Declaration/Type Stub for EditorState ---
if 'EditorState' not in globals(): 
    class EditorState: 
        map_name_for_function: str
        placed_objects: List[Dict[str, Any]]
        background_color: Tuple[int,int,int]
        map_width_tiles: int
        map_height_tiles: int
        grid_size: int
        camera_offset_x: float
        camera_offset_y: float
        zoom_level: float
        show_grid: bool
        asset_specific_variables: Dict[str, Dict[str, Any]]
        current_map_filename: Optional[str]
        current_json_filename: Optional[str]
        unsaved_changes: bool
        undo_stack: List[Dict[str, Any]]
        redo_stack: List[Dict[str, Any]]
        assets_palette: Dict[str, Dict[str, Any]]
        palette_current_asset_key: Optional[str]
        palette_asset_is_flipped_h: bool
        palette_wall_variant_index: int
        current_selected_asset_paint_color: Optional[Tuple[int,int,int]]
        current_tool_mode: str
        def get_map_pixel_width(self) -> int: return self.map_width_tiles * self.grid_size
        def get_map_pixel_height(self) -> int: return self.map_height_tiles * self.grid_size
        def reset_map_context(self): pass
        def get_current_placing_asset_effective_key(self) -> Optional[str]: return None

# --- Actual Module Imports ---
_IS_STANDALONE_EXECUTION_MAP_UTILS = (__name__ == "__main__")
_CURRENT_FILE_DIR_MAP_UTILS = os.path.dirname(os.path.abspath(__file__))

# Initialize with fallbacks for ED_CONFIG, C, and editor_history
class _ED_CONFIG_FALLBACK_MU:
    GAME_LEVEL_FILE_EXTENSION = ".py"; LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
    BASE_GRID_SIZE = 40; DEFAULT_MAP_WIDTH_TILES = 30; DEFAULT_MAP_HEIGHT_TILES = 20
    DEFAULT_BACKGROUND_COLOR_TUPLE = (173,216,230); MAPS_DIRECTORY="maps"
    EDITOR_PALETTE_ASSETS = {"platform_wall_gray": {"game_type_id": "platform_wall_gray", "base_color_tuple": (128,128,128)},
                             "player1_spawn": {"game_type_id": "player1_spawn"}}
    CUSTOM_IMAGE_ASSET_KEY="custom_image_object"; TRIGGER_SQUARE_ASSET_KEY="trigger_square"
    WALL_BASE_KEY = "platform_wall_gray"; WALL_VARIANTS_CYCLE = ["platform_wall_gray"]
    def get_default_properties_for_asset(self, game_type_id: str) -> Dict[str, Any]: return {}
class _C_FALLBACK_MU:
    TILE_SIZE = 40; GRAY = (128,128,128); MAPS_DIR = "maps"; LIGHT_BLUE = (173,216,230)
    DARK_GRAY = (50,50,50); MAGENTA = (255,0,255); PROJECT_ROOT = ""
class _editor_history_FALLBACK_MU:
    @staticmethod
    def get_map_snapshot(state): return {}
    @staticmethod
    def restore_map_from_snapshot(state, snapshot): pass
    @staticmethod
    def push_undo_state(state): pass
    @staticmethod
    def _deep_copy_object_data(obj_data: Dict[str, Any]) -> Dict[str, Any]: return obj_data.copy() 

ED_CONFIG = _ED_CONFIG_FALLBACK_MU()
C = _C_FALLBACK_MU()
editor_history = _editor_history_FALLBACK_MU()

try:
    if _IS_STANDALONE_EXECUTION_MAP_UTILS:
        _PROJECT_ROOT_MAP_UTILS = os.path.dirname(_CURRENT_FILE_DIR_MAP_UTILS)
        if _PROJECT_ROOT_MAP_UTILS not in sys.path:
            sys.path.insert(0, _PROJECT_ROOT_MAP_UTILS)
        
        import editor_config as ED_CONFIG_actual
        from editor_state import EditorState as EditorState_actual 
        import editor_history as editor_history_actual
        import constants as C_actual
        logger.info("editor_map_utils: Standalone execution - imports successful.")
    else: 
        from . import editor_config as ED_CONFIG_actual
        from .editor_state import EditorState as EditorState_actual 
        from . import editor_history as editor_history_actual
        import constants as C_actual 
        logger.info("editor_map_utils: Package execution - imports successful.")

    ED_CONFIG = ED_CONFIG_actual
    EditorState = EditorState_actual # Override the stub with the actual class
    editor_history = editor_history_actual # type: ignore
    C = C_actual

except ImportError as e:
    logger.error(f"editor_map_utils: Import failed using {'standalone' if _IS_STANDALONE_EXECUTION_MAP_UTILS else 'package'} path: {e}")
    logger.warning("editor_map_utils: Using fallback definitions for ED_CONFIG, C, editor_history. EditorState type hint stub will be used.")
    if not hasattr(ED_CONFIG, 'BASE_GRID_SIZE'): 
        logger.critical("editor_map_utils: Fallback ED_CONFIG is missing essential attributes.")


def sanitize_map_name(map_name: str) -> str:
    if not map_name: return ""
    name = map_name.strip()
    name = name.replace(" ", "_").replace("-", "_")
    name = re.sub(r'[^\w_]', '', name)
    name = name.lower()
    if not name.strip("_"): return ""
    return name

def get_maps_base_directory() -> str:
    maps_dir_const = getattr(C, 'MAPS_DIR', 'maps') 
    project_root_const = getattr(C, 'PROJECT_ROOT', None)

    if project_root_const is None or project_root_const == "": 
        project_root_for_maps = os.path.dirname(_CURRENT_FILE_DIR_MAP_UTILS)
    else:
        project_root_for_maps = project_root_const
        
    if not os.path.isabs(maps_dir_const):
        return os.path.normpath(os.path.join(project_root_for_maps, maps_dir_const))
    return os.path.normpath(maps_dir_const)


def get_map_specific_folder_path(editor_state_or_map_name: Any, map_name_override: Optional[str] = None, subfolder: Optional[str] = None, ensure_exists: bool = False) -> Optional[str]:
    actual_map_name = ""
    if isinstance(editor_state_or_map_name, EditorState): 
        actual_map_name = editor_state_or_map_name.map_name_for_function
    elif isinstance(editor_state_or_map_name, str):
        actual_map_name = editor_state_or_map_name
    
    if map_name_override: 
        actual_map_name = map_name_override

    actual_map_name = sanitize_map_name(actual_map_name)
    if not actual_map_name or actual_map_name == "untitled_map":
        logger.warning(f"get_map_specific_folder_path: Invalid or untitled map name '{actual_map_name}'. Cannot determine folder path.")
        return None

    base_maps_dir = get_maps_base_directory()
    map_folder_path = os.path.join(base_maps_dir, actual_map_name)

    if subfolder:
        map_folder_path = os.path.join(map_folder_path, subfolder)

    if ensure_exists:
        try:
            os.makedirs(map_folder_path, exist_ok=True)
            
            map_specific_init_py = os.path.join(os.path.join(base_maps_dir, actual_map_name), "__init__.py")
            if not os.path.exists(map_specific_init_py):
                with open(map_specific_init_py, "w") as f_init:
                    f_init.write(f"# __init__.py for map sub-package '{actual_map_name}'\n")
                logger.debug(f"Created __init__.py in map folder: {map_specific_init_py}")

        except OSError as e:
            logger.error(f"Error creating directory {map_folder_path}: {e}", exc_info=True)
            return None
    return os.path.normpath(map_folder_path)


def init_new_map_state(editor_state: EditorState, map_name_for_function: str,
                       map_width_tiles: int, map_height_tiles: int, preserve_objects: bool = False):
    logger.info(f"Initializing new map state. Name: '{map_name_for_function}', Size: {map_width_tiles}x{map_height_tiles}")
    clean_map_name = sanitize_map_name(map_name_for_function)
    if not clean_map_name:
        clean_map_name = "untitled_map" 
    
    existing_objects = list(editor_state.placed_objects) if preserve_objects else []
    existing_bg_color = editor_state.background_color if preserve_objects else ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE # type: ignore

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.grid_size = ED_CONFIG.BASE_GRID_SIZE # type: ignore
    editor_state.background_color = existing_bg_color
    editor_state.camera_offset_x = 0.0
    editor_state.camera_offset_y = 0.0
    editor_state.zoom_level = 1.0
    editor_state.unsaved_changes = True 

    map_folder = get_map_specific_folder_path(editor_state, ensure_exists=True) 
    if map_folder:
        py_filename = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION # type: ignore
        json_filename = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # type: ignore
        editor_state.current_map_filename = os.path.join(map_folder, py_filename)
        editor_state.current_json_filename = os.path.join(map_folder, json_filename)
    else: 
        editor_state.current_map_filename = None
        editor_state.current_json_filename = None
        logger.error(f"Could not determine or create map folder for '{clean_map_name}' during init_new_map_state.")

    if preserve_objects:
        editor_state.placed_objects = [editor_history._deep_copy_object_data(obj) for obj in existing_objects] # type: ignore
    else: 
        editor_state.placed_objects = []
        gs = float(editor_state.grid_size)
        border_asset_key = "platform_wall_gray"
        border_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(border_asset_key) # type: ignore
        if border_asset_data:
            border_game_type_id = border_asset_data.get("game_type_id", border_asset_key)
            border_color_tuple = border_asset_data.get("base_color_tuple", getattr(C, 'GRAY', (128,128,128)))
            border_props = ED_CONFIG.get_default_properties_for_asset(border_game_type_id) # type: ignore
            border_props["is_boundary"] = True 
            for i in range(map_width_tiles): 
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": 0, "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": border_props.copy(), "is_flipped_h": False})
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": int((map_height_tiles - 1) * gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": border_props.copy(), "is_flipped_h": False})
            for i in range(1, map_height_tiles - 1):
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": 0, "world_y": int(i*gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": border_props.copy(), "is_flipped_h": False})
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int((map_width_tiles - 1)*gs), "world_y": int(i*gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": border_props.copy(), "is_flipped_h": False})

        spawn_y = int((map_height_tiles - 3) * gs)
        for player_num in range(1, 5):
            p_spawn_key = f"player{player_num}_spawn"
            spawn_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(p_spawn_key) # type: ignore
            if spawn_asset_data:
                spawn_game_type_id = spawn_asset_data.get("game_type_id", p_spawn_key)
                default_props = ED_CONFIG.get_default_properties_for_asset(spawn_game_type_id) # type: ignore
                spawn_x_offset = (2 + (player_num - 1) * 2) * gs
                editor_state.placed_objects.append({
                    "asset_editor_key": p_spawn_key, 
                    "world_x": int(spawn_x_offset), 
                    "world_y": spawn_y,
                    "game_type_id": spawn_game_type_id, 
                    "properties": default_props, 
                    "layer_order": 10,
                    "is_flipped_h": False 
                })

    editor_state.undo_stack.clear()
    editor_state.redo_stack.clear()
    editor_state.palette_current_asset_key = None
    editor_state.palette_asset_is_flipped_h = False
    editor_state.palette_wall_variant_index = 0


def ensure_maps_directory_exists() -> bool:
    maps_base_dir = get_maps_base_directory()
    if not os.path.exists(maps_base_dir):
        try:
            os.makedirs(maps_base_dir)
            logger.info(f"Base maps directory created: {maps_base_dir}")
            base_init_py = os.path.join(maps_base_dir, "__init__.py")
            if not os.path.exists(base_init_py):
                with open(base_init_py, "w") as f_init:
                    f_init.write("# Base maps package __init__.py\n")
                logger.info(f"Created __init__.py in base maps directory: {base_init_py}")
            return True
        except OSError as e:
            logger.error(f"Error creating base maps directory {maps_base_dir}: {e}", exc_info=True)
            return False
    
    base_init_py_check = os.path.join(maps_base_dir, "__init__.py")
    if not os.path.exists(base_init_py_check):
        try:
            with open(base_init_py_check, "w") as f_init_check:
                f_init_check.write("# Base maps package __init__.py (auto-created)\n")
            logger.info(f"Created missing __init__.py in existing base maps directory: {base_init_py_check}")
        except OSError as e_init_check:
            logger.error(f"Error creating __init__.py in existing base maps directory {maps_base_dir}: {e_init_check}")
            
    return os.path.isdir(maps_base_dir)


def save_map_to_json(editor_state: EditorState) -> bool:
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("SaveMapJSON: Map is untitled. Cannot save.")
        return False
    
    map_folder = get_map_specific_folder_path(editor_state, ensure_exists=True)
    if not map_folder:
        logger.error(f"SaveMapJSON: Could not get/create map folder for '{editor_state.map_name_for_function}'.")
        return False

    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # type: ignore
    json_filepath = os.path.join(map_folder, json_filename)
    editor_state.current_json_filename = json_filepath 

    data_to_save = editor_history.get_map_snapshot(editor_state) # type: ignore
    try:
        with open(json_filepath, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4)
        logger.info(f"Map editor data saved to: {json_filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving map to JSON '{json_filepath}': {e}", exc_info=True)
        return False

def load_map_from_json(editor_state: EditorState, chosen_json_filepath: str) -> bool:
    if not os.path.exists(chosen_json_filepath) or not os.path.isfile(chosen_json_filepath):
        logger.error(f"LoadMapJSON: File not found or not a file: {chosen_json_filepath}")
        return False

    map_name_from_file_stem = sanitize_map_name(os.path.splitext(os.path.basename(chosen_json_filepath))[0])
    base_maps_dir = get_maps_base_directory() 
    
    actual_json_folder = os.path.dirname(chosen_json_filepath)
    actual_json_filepath_to_load = chosen_json_filepath

    if os.path.normpath(actual_json_folder) == os.path.normpath(base_maps_dir):
        logger.info(f"LoadMapJSON: Detected old-style map '{map_name_from_file_stem}' in base maps directory.")
        new_map_folder_path = get_map_specific_folder_path(map_name_from_file_stem, ensure_exists=True) 
        if not new_map_folder_path:
             logger.error(f"LoadMapJSON: Migration error - could not create target folder for '{map_name_from_file_stem}'.")
             return False
        
        logger.info(f"LoadMapJSON: Migrating old-style map '{map_name_from_file_stem}' to folder '{new_map_folder_path}'.")
        try:
            new_json_path = os.path.join(new_map_folder_path, os.path.basename(chosen_json_filepath))
            if os.path.normpath(chosen_json_filepath) != os.path.normpath(new_json_path):
                shutil.move(chosen_json_filepath, new_json_path)
                logger.info(f"Moved JSON '{chosen_json_filepath}' to '{new_json_path}'")
            actual_json_filepath_to_load = new_json_path

            old_py_filename = map_name_from_file_stem + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION # type: ignore
            old_py_path = os.path.join(base_maps_dir, old_py_filename)
            if os.path.exists(old_py_path):
                new_py_path = os.path.join(new_map_folder_path, old_py_filename)
                if os.path.normpath(old_py_path) != os.path.normpath(new_py_path):
                    shutil.move(old_py_path, new_py_path)
                    logger.info(f"Moved PY '{old_py_path}' to '{new_py_path}'")
        except Exception as e_migrate:
            logger.error(f"Error migrating map files for '{map_name_from_file_stem}': {e_migrate}", exc_info=True)
            actual_json_filepath_to_load = chosen_json_filepath 

    try:
        with open(actual_json_filepath_to_load, 'r', encoding='utf-8') as f:
            data_snapshot = json.load(f)
        
        editor_history.restore_map_from_snapshot(editor_state, data_snapshot) # type: ignore
        
        map_name_from_json_content = sanitize_map_name(editor_state.map_name_for_function)
        final_map_folder_stem_for_paths = map_name_from_file_stem 
        if map_name_from_json_content != map_name_from_file_stem:
            logger.warning(f"LoadMapJSON: Map name in JSON ('{map_name_from_json_content}') differs from filename stem ('{map_name_from_file_stem}'). "
                           f"Using filename stem for pathing. Consider renaming the map in editor to match.")
            editor_state.map_name_for_function = final_map_folder_stem_for_paths
        
        final_map_folder_path = get_map_specific_folder_path(final_map_folder_stem_for_paths, ensure_exists=False) 

        if not final_map_folder_path or not os.path.isdir(final_map_folder_path): 
            logger.error(f"LoadMapJSON: Critical error - map folder for '{final_map_folder_stem_for_paths}' not found at '{final_map_folder_path}' after loading JSON.")
            editor_state.reset_map_context()
            return False

        editor_state.current_json_filename = os.path.join(final_map_folder_path, final_map_folder_stem_for_paths + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION) # type: ignore
        editor_state.current_map_filename = os.path.join(final_map_folder_path, final_map_folder_stem_for_paths + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION) # type: ignore

        if os.path.normpath(actual_json_filepath_to_load) != os.path.normpath(str(editor_state.current_json_filename)):
            logger.warning(f"LoadMapJSON: Final JSON path ('{editor_state.current_json_filename}') "
                           f"differs from the path it was loaded from ('{actual_json_filepath_to_load}'). "
                           f"This is unusual after migration logic. Please check map file consistency.")

        editor_state.unsaved_changes = False
        logger.info(f"Map '{editor_state.map_name_for_function}' loaded from: {editor_state.current_json_filename}")
        return True
    except Exception as e:
        logger.error(f"Error loading map from JSON '{actual_json_filepath_to_load}': {e}", exc_info=True)
        return False


def _merge_rect_objects_to_data(objects_raw: List[Dict[str, Any]], object_category_name: str) -> List[Dict[str, Any]]:
    if not objects_raw: return []
    working_objects: List[Dict[str, Any]] = []
    for obj_orig in objects_raw:
        obj = obj_orig.copy()
        obj['merged'] = False
        obj.setdefault('x', 0.0); obj.setdefault('y', 0.0)
        obj.setdefault('w', float(ED_CONFIG.BASE_GRID_SIZE)); obj.setdefault('h', float(ED_CONFIG.BASE_GRID_SIZE)) # type: ignore
        color_val = obj.get('color', getattr(C, 'MAGENTA', (255,0,255)))
        if isinstance(color_val, list) and len(color_val) == 3: obj['color'] = tuple(color_val)
        elif not (isinstance(color_val, tuple) and len(color_val) == 3): obj['color'] = getattr(C, 'MAGENTA', (255,0,255))
        obj.setdefault('type', f'generic_{object_category_name}')
        if 'image_path' in obj_orig: obj['image_path'] = obj_orig['image_path']
        if 'crop_rect' in obj_orig: obj['crop_rect'] = obj_orig['crop_rect']
        obj.setdefault('is_flipped_h', False) 
        working_objects.append(obj)

    horizontal_strips: List[Dict[str, Any]] = []
    key_func_h = lambda p: (str(p.get('type')), str(p.get('color')), p.get('y'), p.get('h'), 
                            str(p.get('image_path', '')), str(p.get('crop_rect')), p.get('is_flipped_h'), p.get('x'))
    sorted_h = sorted(working_objects, key=key_func_h)

    for i, p_base in enumerate(sorted_h):
        if p_base.get('merged'): continue
        current_strip = p_base.copy(); p_base['merged'] = True
        for j in range(i + 1, len(sorted_h)):
            p_next = sorted_h[j]
            if p_next.get('merged'): continue
            if str(p_next.get('type')) == str(current_strip.get('type')) and \
               str(p_next.get('color')) == str(current_strip.get('color')) and \
               abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) < 1e-3 and \
               abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) < 1e-3 and \
               abs(p_next.get('x', 0.0) - (current_strip.get('x', 0.0) + current_strip.get('w', 0.0))) < 1e-3 and \
               str(p_next.get('image_path', '')) == str(current_strip.get('image_path', '')) and \
               str(p_next.get('crop_rect')) == str(current_strip.get('crop_rect')) and \
               p_next.get('is_flipped_h') == current_strip.get('is_flipped_h'):
                current_strip['w'] += p_next.get('w', 0.0); p_next['merged'] = True
            elif abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) >= 1e-3 or \
                 abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) >= 1e-3 or \
                 str(p_next.get('type')) != str(current_strip.get('type')) or \
                 str(p_next.get('color')) != str(current_strip.get('color')) or \
                 str(p_next.get('image_path', '')) != str(current_strip.get('image_path', '')) or \
                 str(p_next.get('crop_rect')) != str(current_strip.get('crop_rect')) or \
                 p_next.get('is_flipped_h') != current_strip.get('is_flipped_h'):
                break
        horizontal_strips.append(current_strip)

    final_blocks_data: List[Dict[str, Any]] = []
    strips_to_merge = [strip.copy() for strip in horizontal_strips]
    for strip in strips_to_merge: strip['merged'] = False
    key_func_v = lambda s: (str(s.get('type')), str(s.get('color')), s.get('x'), s.get('w'), 
                            str(s.get('image_path', '')), str(s.get('crop_rect')), s.get('is_flipped_h'), s.get('y'))
    sorted_v = sorted(strips_to_merge, key=key_func_v)

    for i, s_base in enumerate(sorted_v):
        if s_base.get('merged'): continue
        current_block = s_base.copy(); s_base['merged'] = True
        for j in range(i + 1, len(sorted_v)):
            s_next = sorted_v[j]
            if s_next.get('merged'): continue
            if str(s_next.get('type')) == str(current_block.get('type')) and \
               str(s_next.get('color')) == str(current_block.get('color')) and \
               abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) < 1e-3 and \
               abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) < 1e-3 and \
               abs(s_next.get('y', 0.0) - (current_block.get('y', 0.0) + current_block.get('h', 0.0))) < 1e-3 and \
               str(s_next.get('image_path', '')) == str(current_block.get('image_path', '')) and \
               str(s_next.get('crop_rect')) == str(current_block.get('crop_rect')) and \
               s_next.get('is_flipped_h') == current_block.get('is_flipped_h'):
                current_block['h'] += s_next.get('h', 0.0); s_next['merged'] = True
            elif abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) >= 1e-3 or \
                 abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) >= 1e-3 or \
                 str(s_next.get('type')) != str(current_block.get('type')) or \
                 str(s_next.get('color')) != str(current_block.get('color')) or \
                 str(s_next.get('image_path', '')) != str(current_strip.get('image_path', '')) or \
                 str(s_next.get('crop_rect')) != str(current_block.get('crop_rect')) or \
                 s_next.get('is_flipped_h') != current_block.get('is_flipped_h'):
                break
        current_block.pop('merged', None)
        final_entry = {'rect': (current_block.get('x'), current_block.get('y'), current_block.get('w'), current_block.get('h')),
                       'type': current_block.get('type'), 'color': current_block.get('color'),
                       'properties': current_block.get('properties', {}),
                       'is_flipped_h': current_block.get('is_flipped_h', False)} 
        if 'image_path' in current_block: final_entry['image_path'] = current_block['image_path']
        if 'crop_rect' in current_block and current_block['crop_rect'] is not None: 
            final_entry['crop_rect'] = current_block['crop_rect'] 
        final_blocks_data.append(final_entry)
    return final_blocks_data


def export_map_to_game_python_script(editor_state: EditorState) -> bool:
    logger.info(f"Exporting map data. Map name: '{editor_state.map_name_for_function}'")
    ts = editor_state.grid_size
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("Map name not set. Cannot export .py data file.")
        return False

    map_folder = get_map_specific_folder_path(editor_state, ensure_exists=True) 
    if not map_folder:
        logger.error(f"Export PY: Could not get/create map folder for '{editor_state.map_name_for_function}'.")
        return False

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION # type: ignore
    py_filepath_to_use = os.path.join(map_folder, py_filename)
    editor_state.current_map_filename = py_filepath_to_use 

    game_function_name = f"load_map_{editor_state.map_name_for_function}"

    platforms_data_raw: List[Dict[str, Any]] = []; ladders_data_raw: List[Dict[str, Any]] = []
    hazards_data_raw: List[Dict[str, Any]] = []; background_tiles_data_raw: List[Dict[str, Any]] = []
    enemies_list_export: List[Dict[str, Any]] = []; items_list_export: List[Dict[str, Any]] = []
    statue_list_export: List[Dict[str, Any]] = []
    custom_images_export: List[Dict[str, Any]] = [] 
    trigger_squares_export: List[Dict[str, Any]] = [] 

    player_start_pos_p1: Optional[Tuple[float, float]] = None; player1_spawn_props: Dict[str, Any] = {}
    player_start_pos_p2: Optional[Tuple[float, float]] = None; player2_spawn_props: Dict[str, Any] = {}
    player_start_pos_p3: Optional[Tuple[float, float]] = None; player3_spawn_props: Dict[str, Any] = {}
    player_start_pos_p4: Optional[Tuple[float, float]] = None; player4_spawn_props: Dict[str, Any] = {}

    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []

    for obj_data in editor_state.placed_objects:
        asset_key = str(obj_data.get("asset_editor_key", ""))
        game_type_id = str(obj_data.get("game_type_id", "unknown"))
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        obj_props = obj_data.get("properties", {})
        is_flipped_h = obj_data.get("is_flipped_h", False)
        
        if wx is None or wy is None or not asset_key: continue

        export_x, export_y = float(wx), float(wy)
        obj_w = float(obj_data.get("current_width", ts)) 
        obj_h = float(obj_data.get("current_height", ts))
        
        final_color_for_export = obj_data.get("override_color") 
        
        asset_entry_from_palette = editor_state.assets_palette.get(asset_key) 
        category = asset_entry_from_palette.get("category", "unknown") if asset_entry_from_palette else "custom" 

        is_custom_image_type = (asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) # type: ignore
        is_trigger_square_type = (asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY) # type: ignore

        if not is_custom_image_type and not is_trigger_square_type:
            if asset_entry_from_palette and asset_entry_from_palette.get("original_size_pixels"):
                obj_w_orig, obj_h_orig = asset_entry_from_palette["original_size_pixels"]
                obj_w, obj_h = float(obj_w_orig), float(obj_h_orig)
            elif asset_entry_from_palette and asset_entry_from_palette.get("surface_params"):
                sp = asset_entry_from_palette["surface_params"]
                if isinstance(sp, tuple) and len(sp) >=2: obj_w, obj_h = float(sp[0]), float(sp[1])
            else: 
                obj_w, obj_h = float(ts), float(ts) 
            
            if not final_color_for_export and asset_entry_from_palette: 
                final_color_for_export = asset_entry_from_palette.get("base_color_tuple")
                if not final_color_for_export and asset_entry_from_palette.get("surface_params"):
                    sp = asset_entry_from_palette["surface_params"]
                    if isinstance(sp, tuple) and len(sp) == 3: final_color_for_export = sp[2]
            final_color_for_export = final_color_for_export or getattr(C, 'GRAY', (128,128,128))

        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})

        if is_custom_image_type:
            image_export_data = {
                'rect': (export_x, export_y, obj_w, obj_h),
                'source_file_path': obj_data.get("source_file_path", ""), 
                'original_width': obj_data.get("original_width"),
                'original_height': obj_data.get("original_height"),
                'crop_rect': obj_data.get("crop_rect"), 
                'layer_order': obj_data.get("layer_order", 0),
                'properties': obj_props,
                'is_flipped_h': is_flipped_h
            }
            if image_export_data['original_width'] is None: del image_export_data['original_width']
            if image_export_data['original_height'] is None: del image_export_data['original_height']
            if image_export_data['crop_rect'] is None: del image_export_data['crop_rect']
            custom_images_export.append(image_export_data)
        elif is_trigger_square_type:
            trigger_squares_export.append({
                'rect': (export_x, export_y, obj_w, obj_h),
                'layer_order': obj_data.get("layer_order", 0),
                'properties': obj_props,
                'is_flipped_h': is_flipped_h 
            })
        elif category == "spawn":
            spawn_pos = (export_x + obj_w / 2.0, export_y + obj_h)
            spawn_props_to_export = {**obj_props, "is_flipped_h": is_flipped_h}
            for p_num in range(1,5):
                p_spawn_def_key = f"player{p_num}_spawn"
                p_spawn_def_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(p_spawn_def_key,{}) # type: ignore
                if game_type_id == p_spawn_def_data.get("game_type_id"):
                    if p_num == 1: player_start_pos_p1 = spawn_pos; player1_spawn_props = spawn_props_to_export.copy()
                    elif p_num == 2: player_start_pos_p2 = spawn_pos; player2_spawn_props = spawn_props_to_export.copy()
                    elif p_num == 3: player_start_pos_p3 = spawn_pos; player3_spawn_props = spawn_props_to_export.copy()
                    elif p_num == 4: player_start_pos_p4 = spawn_pos; player4_spawn_props = spawn_props_to_export.copy()
                    break 
        elif category == "tile" or "platform" in game_type_id.lower():
             platforms_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': game_type_id, 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif category == "enemy":
             enemies_list_export.append({'start_pos': (export_x + obj_w / 2.0, export_y + obj_h), 'type': game_type_id, 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif "ladder" in game_type_id.lower(): ladders_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': 'ladder', 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif "hazard" in game_type_id.lower(): hazards_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': game_type_id, 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif category == "item": items_list_export.append({'pos': (export_x + obj_w / 2.0, export_y + obj_h / 2.0), 'type': game_type_id, 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif "object_stone" in game_type_id.lower(): statue_list_export.append({'id': obj_data.get("unique_id", f"statue_{len(statue_list_export)}"), 'pos': (export_x + obj_w / 2.0, export_y + obj_h / 2.0), 'properties': obj_props, 'is_flipped_h': is_flipped_h})
        elif category == "background_tile": 
            bg_tile_export_data = {'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 
                                   'color': final_color_for_export, 'type': game_type_id, 
                                   'image_path': asset_entry_from_palette.get("source_file") if asset_entry_from_palette else None,
                                   'crop_rect': obj_data.get("crop_rect"), 
                                   'properties': obj_props,
                                   'is_flipped_h': is_flipped_h} 
            if bg_tile_export_data['crop_rect'] is None: del bg_tile_export_data['crop_rect']
            background_tiles_data_raw.append(bg_tile_export_data)

    if not player_start_pos_p1:
        p1_spawn_def = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player1_spawn",{}) # type: ignore
        p1_game_id = p1_spawn_def.get("game_type_id")
        if p1_game_id: player1_spawn_props = {**ED_CONFIG.get_default_properties_for_asset(p1_game_id), "is_flipped_h": False} # type: ignore
        player_start_pos_p1 = (ts * 2.5, editor_state.map_height_tiles * ts - ts * 3)

    platforms_list_export = _merge_rect_objects_to_data(platforms_data_raw, "platform")
    ladders_list_export = _merge_rect_objects_to_data(ladders_data_raw, "ladder")
    hazards_list_export = _merge_rect_objects_to_data(hazards_data_raw, "hazard")
    background_tiles_list_export = _merge_rect_objects_to_data(background_tiles_data_raw, "background_tile")

    level_min_x_abs_for_camera, level_max_x_abs_for_camera = 0.0, float(editor_state.map_width_tiles * ts)
    level_min_y_abs_for_camera, level_max_y_abs_for_camera = 0.0, float(editor_state.map_height_tiles * ts)
    map_max_y_content = level_max_y_abs_for_camera
    if all_placed_objects_rect_data_for_bounds:
        level_min_x_abs_for_camera = min(r['x'] for r in all_placed_objects_rect_data_for_bounds); level_max_x_abs_for_camera = max(r['x'] + r['width'] for r in all_placed_objects_rect_data_for_bounds)
        level_min_y_abs_for_camera = min(r['y'] for r in all_placed_objects_rect_data_for_bounds); level_max_y_abs_for_camera = max(r['y'] + r['height'] for r in all_placed_objects_rect_data_for_bounds)
        map_max_y_content = level_max_y_abs_for_camera
    level_pixel_width_for_camera = level_max_x_abs_for_camera - level_min_x_abs_for_camera
    main_ground_y_ref = map_max_y_content; ground_platform_height_ref = float(C.TILE_SIZE) # type: ignore

    final_game_data_for_script = {
        "level_name": editor_state.map_name_for_function, "background_color": editor_state.background_color,
        "player_start_pos_p1": player_start_pos_p1, "player1_spawn_props": player1_spawn_props,
        "platforms_list": platforms_list_export, "ladders_list": ladders_list_export,
        "hazards_list": hazards_list_export, "background_tiles_list": background_tiles_list_export,
        "enemies_list": enemies_list_export, "items_list": items_list_export,
        "statues_list": statue_list_export, 
        "custom_images_list": custom_images_export, 
        "trigger_squares_list": trigger_squares_export, 
        "level_pixel_width": level_pixel_width_for_camera,
        "level_min_x_absolute": level_min_x_abs_for_camera, 
        "level_min_y_absolute": level_min_y_abs_for_camera,
        "level_max_y_absolute": level_max_y_abs_for_camera, 
        "ground_level_y_ref": main_ground_y_ref,
        "ground_platform_height_ref": ground_platform_height_ref,
    }
    if player_start_pos_p2: final_game_data_for_script["player_start_pos_p2"] = player_start_pos_p2
    if player2_spawn_props: final_game_data_for_script["player2_spawn_props"] = player2_spawn_props
    if player_start_pos_p3: final_game_data_for_script["player_start_pos_p3"] = player_start_pos_p3
    if player3_spawn_props: final_game_data_for_script["player3_spawn_props"] = player3_spawn_props
    if player_start_pos_p4: final_game_data_for_script["player_start_pos_p4"] = player_start_pos_p4
    if player4_spawn_props: final_game_data_for_script["player4_spawn_props"] = player4_spawn_props

    for key_default_list in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list", 
                             "enemies_list", "items_list", "statues_list", "custom_images_list", "trigger_squares_list"]:
        final_game_data_for_script.setdefault(key_default_list, [])

    script_content_parts = [f"# Level Data: {editor_state.map_name_for_function}", "# Generated by Platformer Level Editor", "", f"def {game_function_name}():", "    game_data = {"]
    for data_key, data_value in final_game_data_for_script.items(): script_content_parts.append(f"        '{data_key}': {repr(data_value)},") 
    script_content_parts.extend(["    }", "    return game_data", "", "if __name__ == '__main__':", f"    data = {game_function_name}()", "    import json", "    print(json.dumps(data, indent=4))"])
    script_content = "\n".join(script_content_parts)
    try:
        with open(str(py_filepath_to_use), "w", encoding='utf-8') as f: f.write(script_content)
        logger.info(f"Map data exported to game script: {os.path.basename(str(py_filepath_to_use))}")
        return True
    except Exception as e:
        logger.error(f"Error exporting map data to .py '{py_filepath_to_use}': {e}", exc_info=True)
        return False

def delete_map_folder_and_contents(editor_state: EditorState, map_name_to_delete: str) -> bool:
    map_folder_path = get_map_specific_folder_path(editor_state, map_name_to_delete)
    if not map_folder_path or not os.path.exists(map_folder_path) or not os.path.isdir(map_folder_path):
        logger.warning(f"delete_map_folder: Map folder for '{map_name_to_delete}' not found at '{map_folder_path}'.")
        return False
    try:
        shutil.rmtree(map_folder_path)
        logger.info(f"Successfully deleted map folder: {map_folder_path}")
        return True
    except OSError as e:
        logger.error(f"Error deleting map folder '{map_folder_path}': {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("Running editor_map_utils.py directly.")
    if ED_CONFIG and hasattr(ED_CONFIG, 'BASE_GRID_SIZE'):
        print(f"ED_CONFIG.BASE_GRID_SIZE: {ED_CONFIG.BASE_GRID_SIZE}") # type: ignore
    else:
        print("ED_CONFIG.BASE_GRID_SIZE not found or ED_CONFIG is fallback.")
    
    if C and hasattr(C, 'TILE_SIZE'):
        print(f"C.TILE_SIZE: {C.TILE_SIZE}") # type: ignore
    else:
        print("C.TILE_SIZE not found or C is fallback.")

    print(f"Base maps directory: {get_maps_base_directory()}")

#################### END OF FILE: editor_map_utils.py ####################