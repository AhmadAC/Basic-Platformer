#################### START OF FILE: editor_map_utils.py ####################

# editor_map_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for map operations in the Level Editor (PySide6 version).
Handles saving/loading editor JSON and exporting game-compatible Python data scripts.
Manages map-specific folders.
VERSION 2.4.1 (Fixed _PROJECT_ROOT_DIR definition)
"""
import sys
import os
import json
import traceback
import re
import shutil # For folder deletion
from typing import Optional, Dict, List, Tuple, Any
import logging

# --- Determine project root for this module ---
# Assuming editor_map_utils.py is in 'editor/' which is in the project root.
_MODULE_FILE_PATH = os.path.abspath(__file__) if '__file__' in globals() else os.getcwd()
_EDITOR_MODULE_DIR_LOCAL = os.path.dirname(_MODULE_FILE_PATH)
_PROJECT_ROOT_DIR = os.path.dirname(_EDITOR_MODULE_DIR_LOCAL) # Go up one level

# Conditional imports
if __name__ == "__main__" or not __package__:
    # If run directly, or if package context is lost, ensure project root is in sys.path
    # This _PROJECT_ROOT_DIR is the one defined just above.
    if _PROJECT_ROOT_DIR not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT_DIR)
    try:
        if not __package__: # Running as script
            import editor_config as ED_CONFIG
            from editor_state import EditorState
            import editor_history
        else: # Imported as part of a package
            from . import editor_config as ED_CONFIG
            from .editor_state import EditorState
            from . import editor_history
        import constants as C
    except ImportError as e:
        print(f"ERROR (editor_map_utils import block): Could not perform imports: {e}")
        # Fallback classes (as before)
        class ED_CONFIG_FALLBACK:
            GAME_LEVEL_FILE_EXTENSION = ".py"; LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
            BASE_GRID_SIZE = 40; DEFAULT_MAP_WIDTH_TILES = 30; DEFAULT_MAP_HEIGHT_TILES = 20
            DEFAULT_BACKGROUND_COLOR_TUPLE = (173,216,230); MAPS_DIRECTORY="maps"
            EDITOR_PALETTE_ASSETS = {"platform_wall_gray": {"game_type_id": "platform_wall_gray", "base_color_tuple": (128,128,128)},
                                     "player1_spawn": {"game_type_id": "player1_spawn"}}
            CUSTOM_IMAGE_ASSET_KEY="custom_image_object"; TRIGGER_SQUARE_ASSET_KEY="trigger_square"
        ED_CONFIG = ED_CONFIG_FALLBACK()
        class EditorState: pass 
        class editor_history: 
            @staticmethod
            def get_map_snapshot(state): return {}
        class FallbackConstants: TILE_SIZE = 40; GRAY = (128,128,128); MAPS_DIR = "maps"
        C = FallbackConstants()
else: # Normal package import
    from . import editor_config as ED_CONFIG
    from .editor_state import EditorState
    from . import editor_history
    import constants as C

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def sanitize_map_name(map_name: str) -> str:
    """Cleans a map name for use in filenames and folder names."""
    if not map_name: return ""
    name = map_name.strip()
    name = name.replace(" ", "_").replace("-", "_")
    name = re.sub(r'[^\w_]', '', name)
    name = name.lower()
    if not name.strip("_"): return ""
    return name

def get_maps_base_directory() -> str:
    """Returns the absolute path to the base 'maps' directory using the locally defined _PROJECT_ROOT_DIR."""
    maps_dir_name = getattr(C, 'MAPS_DIR', getattr(ED_CONFIG, 'MAPS_DIRECTORY', 'maps'))
    # Uses _PROJECT_ROOT_DIR defined at the top of this specific module
    return os.path.normpath(os.path.join(_PROJECT_ROOT_DIR, maps_dir_name))

def get_map_specific_folder_path(editor_state_or_map_name: Any, map_name_override: Optional[str] = None, subfolder: Optional[str] = None, ensure_exists: bool = False) -> Optional[str]:
    """
    Gets the path to a map's specific folder (e.g., /maps/my_level/).
    Can also get paths to subfolders within it (e.g., /maps/my_level/Custom/).
    """
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
            logger.debug(f"Ensured directory exists: {map_folder_path}")
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
    existing_bg_color = editor_state.background_color if preserve_objects else ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE

    editor_state.map_name_for_function = clean_map_name
    editor_state.map_width_tiles = map_width_tiles
    editor_state.map_height_tiles = map_height_tiles
    editor_state.grid_size = ED_CONFIG.BASE_GRID_SIZE
    editor_state.background_color = existing_bg_color
    editor_state.camera_offset_x = 0.0
    editor_state.camera_offset_y = 0.0
    editor_state.zoom_level = 1.0
    editor_state.unsaved_changes = True 

    map_folder = get_map_specific_folder_path(editor_state, ensure_exists=False) 
    if map_folder:
        py_filename = clean_map_name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
        json_filename = clean_map_name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
        editor_state.current_map_filename = os.path.join(map_folder, py_filename)
        editor_state.current_json_filename = os.path.join(map_folder, json_filename)
    else: 
        editor_state.current_map_filename = None
        editor_state.current_json_filename = None
        logger.error(f"Could not determine map folder for '{clean_map_name}' during init_new_map_state.")

    if preserve_objects:
        editor_state.placed_objects = existing_objects
    else: 
        editor_state.placed_objects = []
        gs = float(editor_state.grid_size)
        border_asset_key = "platform_wall_gray"
        border_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(border_asset_key)
        if border_asset_data:
            border_game_type_id = border_asset_data.get("game_type_id", border_asset_key)
            border_color_tuple = border_asset_data.get("base_color_tuple", getattr(C, 'GRAY', (128,128,128)))
            # Simplified border for brevity
            for i in range(map_width_tiles): 
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": 0, "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int(i * gs), "world_y": int((map_height_tiles - 1) * gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
            for i in range(1, map_height_tiles - 1):
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": 0, "world_y": int(i*gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})
                editor_state.placed_objects.append({"asset_editor_key": border_asset_key, "world_x": int((map_width_tiles - 1)*gs), "world_y": int(i*gs), "game_type_id": border_game_type_id, "override_color": border_color_tuple, "properties": {"is_boundary": True}})

        spawn_y = int((map_height_tiles - 3) * gs)
        spawn_keys_default = ["player1_spawn"] 
        for i, p_spawn_key in enumerate(spawn_keys_default):
            spawn_asset_data = ED_CONFIG.EDITOR_PALETTE_ASSETS.get(p_spawn_key)
            if spawn_asset_data:
                spawn_game_type_id = spawn_asset_data.get("game_type_id", p_spawn_key)
                default_props = ED_CONFIG.get_default_properties_for_asset(spawn_game_type_id) # type: ignore
                editor_state.placed_objects.append({
                    "asset_editor_key": p_spawn_key, "world_x": int((2 + i*2) * gs), "world_y": spawn_y,
                    "game_type_id": spawn_game_type_id, "properties": default_props, "layer_order": 10 # Spawns typically on top
                })

    editor_state.undo_stack.clear()
    editor_state.redo_stack.clear()

def ensure_maps_directory_exists() -> bool:
    maps_base_dir = get_maps_base_directory()
    if not os.path.exists(maps_base_dir):
        try:
            os.makedirs(maps_base_dir)
            logger.info(f"Base maps directory created: {maps_base_dir}")
            return True
        except OSError as e:
            logger.error(f"Error creating base maps directory {maps_base_dir}: {e}", exc_info=True)
            return False
    return os.path.isdir(maps_base_dir)

def save_map_to_json(editor_state: EditorState) -> bool:
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        logger.error("SaveMapJSON: Map is untitled. Cannot save.")
        return False
    
    map_folder = get_map_specific_folder_path(editor_state, ensure_exists=True)
    if not map_folder:
        logger.error(f"SaveMapJSON: Could not get/create map folder for '{editor_state.map_name_for_function}'.")
        return False

    json_filename = editor_state.map_name_for_function + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    json_filepath = os.path.join(map_folder, json_filename)
    editor_state.current_json_filename = json_filepath 

    data_to_save = editor_history.get_map_snapshot(editor_state)
    try:
        with open(json_filepath, "w", encoding='utf-8') as f: # Added encoding
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

    map_name_from_file = sanitize_map_name(os.path.splitext(os.path.basename(chosen_json_filepath))[0])
    base_maps_dir = get_maps_base_directory()
    
    # Determine the correct folder the map *should* be in
    # This might involve reading the map_name_for_function from the JSON first if it's an old file.
    # For now, assume map_name_from_file is a good starting point.
    expected_map_folder_for_this_map_name = get_map_specific_folder_path(editor_state, map_name_from_file) # Uses map_name_from_file
    
    actual_json_filepath_to_load = chosen_json_filepath

    # Migration logic:
    if os.path.normpath(os.path.dirname(chosen_json_filepath)) == os.path.normpath(base_maps_dir):
        if not expected_map_folder_for_this_map_name:
             logger.error(f"LoadMapJSON: Migration error - could not determine target folder for '{map_name_from_file}'.")
             return False
        logger.info(f"LoadMapJSON: Migrating old-style map '{map_name_from_file}' to folder '{expected_map_folder_for_this_map_name}'.")
        try:
            os.makedirs(expected_map_folder_for_this_map_name, exist_ok=True)
            
            new_json_path = os.path.join(expected_map_folder_for_this_map_name, os.path.basename(chosen_json_filepath))
            if os.path.normpath(chosen_json_filepath) != os.path.normpath(new_json_path): # Avoid moving if already correct
                shutil.move(chosen_json_filepath, new_json_path)
                logger.info(f"Moved '{chosen_json_filepath}' to '{new_json_path}'")
            actual_json_filepath_to_load = new_json_path

            old_py_filename = map_name_from_file + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
            old_py_path = os.path.join(base_maps_dir, old_py_filename)
            if os.path.exists(old_py_path):
                new_py_path = os.path.join(expected_map_folder_for_this_map_name, old_py_filename)
                if os.path.normpath(old_py_path) != os.path.normpath(new_py_path):
                    shutil.move(old_py_path, new_py_path)
                    logger.info(f"Moved '{old_py_path}' to '{new_py_path}'")
        except Exception as e_migrate:
            logger.error(f"Error migrating map files for '{map_name_from_file}': {e_migrate}", exc_info=True)
            # Attempt to load from original if critical error during move
            actual_json_filepath_to_load = chosen_json_filepath # Revert to original if move failed

    try:
        with open(actual_json_filepath_to_load, 'r', encoding='utf-8') as f: # Added encoding
            data_snapshot = json.load(f)
        
        editor_history.restore_map_from_snapshot(editor_state, data_snapshot)
        
        # After restore, editor_state.map_name_for_function has the name from JSON.
        # Ensure file paths are based on this name and its correct folder.
        map_name_from_json = sanitize_map_name(editor_state.map_name_for_function)
        final_map_folder = get_map_specific_folder_path(editor_state, map_name_from_json)

        if not final_map_folder:
            logger.error(f"LoadMapJSON: Critical error - could not determine final map folder for '{map_name_from_json}' after loading JSON.")
            # This state is problematic. Perhaps revert to an empty map or re-initialize.
            editor_state.reset_map_context()
            return False

        editor_state.current_json_filename = os.path.join(final_map_folder, map_name_from_json + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
        editor_state.current_map_filename = os.path.join(final_map_folder, map_name_from_json + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)

        # Verify that the loaded JSON file actually matches the final path (after potential migration and name correction)
        if os.path.normpath(actual_json_filepath_to_load) != os.path.normpath(editor_state.current_json_filename):
            logger.warning(f"LoadMapJSON: Path loaded from ('{actual_json_filepath_to_load}') "
                           f"differs from expected final path ('{editor_state.current_json_filename}'). "
                           f"This might happen if map name in JSON was different from filename during migration.")
            # Consider if a re-save is implicitly needed or if user should be notified to save.

        editor_state.unsaved_changes = False
        logger.info(f"Map '{editor_state.map_name_for_function}' loaded from: {editor_state.current_json_filename}")
        return True
    except Exception as e:
        logger.error(f"Error loading map from JSON '{actual_json_filepath_to_load}': {e}", exc_info=True)
        return False

# _merge_rect_objects_to_data (remains the same)
def _merge_rect_objects_to_data(objects_raw: List[Dict[str, Any]], object_category_name: str) -> List[Dict[str, Any]]:
    # ... (Previous implementation is generally fine) ...
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
            if str(p_next.get('type')) == str(current_strip.get('type')) and \
               str(p_next.get('color')) == str(current_strip.get('color')) and \
               abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) < 1e-3 and \
               abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) < 1e-3 and \
               abs(p_next.get('x', 0.0) - (current_strip.get('x', 0.0) + current_strip.get('w', 0.0))) < 1e-3 and \
               str(p_next.get('image_path', '')) == str(current_strip.get('image_path', '')):
                current_strip['w'] += p_next.get('w', 0.0); p_next['merged'] = True
            elif abs(p_next.get('y', 0.0) - current_strip.get('y', 0.0)) >= 1e-3 or \
                 abs(p_next.get('h', 0.0) - current_strip.get('h', 0.0)) >= 1e-3 or \
                 str(p_next.get('type')) != str(current_strip.get('type')) or \
                 str(p_next.get('color')) != str(current_strip.get('color')) or \
                 str(p_next.get('image_path', '')) != str(current_strip.get('image_path', '')):
                break
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
            if str(s_next.get('type')) == str(current_block.get('type')) and \
               str(s_next.get('color')) == str(current_block.get('color')) and \
               abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) < 1e-3 and \
               abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) < 1e-3 and \
               abs(s_next.get('y', 0.0) - (current_block.get('y', 0.0) + current_block.get('h', 0.0))) < 1e-3 and \
               str(s_next.get('image_path', '')) == str(current_block.get('image_path', '')):
                current_block['h'] += s_next.get('h', 0.0); s_next['merged'] = True
            elif abs(s_next.get('x', 0.0) - current_block.get('x', 0.0)) >= 1e-3 or \
                 abs(s_next.get('w', 0.0) - current_block.get('w', 0.0)) >= 1e-3 or \
                 str(s_next.get('type')) != str(current_block.get('type')) or \
                 str(s_next.get('color')) != str(current_block.get('color')) or \
                 str(s_next.get('image_path', '')) != str(current_block.get('image_path', '')):
                break
        current_block.pop('merged', None)
        final_entry = {'rect': (current_block.get('x'), current_block.get('y'), current_block.get('w'), current_block.get('h')),
                       'type': current_block.get('type'), 'color': current_block.get('color'),
                       'properties': current_block.get('properties', {})}
        if 'image_path' in current_block: final_entry['image_path'] = current_block['image_path']
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

    py_filename = editor_state.map_name_for_function + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION
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
    # ... player 2,3,4 spawn vars

    all_placed_objects_rect_data_for_bounds: List[Dict[str, float]] = []

    for obj_data in editor_state.placed_objects:
        asset_key = str(obj_data.get("asset_editor_key", ""))
        game_type_id = str(obj_data.get("game_type_id", "unknown"))
        wx, wy = obj_data.get("world_x"), obj_data.get("world_y")
        obj_props = obj_data.get("properties", {})
        
        if wx is None or wy is None or not asset_key: continue

        export_x, export_y = float(wx), float(wy)
        obj_w = float(obj_data.get("current_width", ts)) 
        obj_h = float(obj_data.get("current_height", ts))
        
        final_color_for_export = obj_data.get("override_color") 
        
        asset_entry_from_palette = editor_state.assets_palette.get(asset_key) 
        category = asset_entry_from_palette.get("category", "unknown") if asset_entry_from_palette else "custom" 

        if asset_key != ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY and asset_key != ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: # type: ignore
            if asset_entry_from_palette and asset_entry_from_palette.get("original_size_pixels"):
                obj_w, obj_h = asset_entry_from_palette["original_size_pixels"]
            elif asset_entry_from_palette and asset_entry_from_palette.get("surface_params"):
                sp = asset_entry_from_palette["surface_params"]
                if isinstance(sp, tuple) and len(sp) >=2: obj_w, obj_h = sp[0], sp[1]
            else: 
                obj_w, obj_h = float(ts), float(ts)
            
            if not final_color_for_export and asset_entry_from_palette: 
                final_color_for_export = asset_entry_from_palette.get("base_color_tuple")
                if not final_color_for_export and asset_entry_from_palette.get("surface_params"):
                    sp = asset_entry_from_palette["surface_params"]
                    if isinstance(sp, tuple) and len(sp) == 3: final_color_for_export = sp[2]
            final_color_for_export = final_color_for_export or getattr(C, 'GRAY', (128,128,128))

        all_placed_objects_rect_data_for_bounds.append({'x': export_x, 'y': export_y, 'width': obj_w, 'height': obj_h})

        if asset_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY:
            custom_images_export.append({
                'rect': (export_x, export_y, obj_w, obj_h),
                'source_file_path': obj_data.get("source_file_path", ""), 
                'layer_order': obj_data.get("layer_order", 0),
                'properties': obj_props
            })
        elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: # type: ignore
            trigger_squares_export.append({
                'rect': (export_x, export_y, obj_w, obj_h),
                'layer_order': obj_data.get("layer_order", 0),
                'properties': obj_props 
            })
        elif category == "spawn":
            spawn_pos = (export_x + obj_w / 2.0, export_y + obj_h) 
            p1_spawn_def = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player1_spawn",{})
            if game_type_id == p1_spawn_def.get("game_type_id"): 
                player_start_pos_p1 = spawn_pos
                player1_spawn_props = obj_props.copy() if obj_props else ED_CONFIG.get_default_properties_for_asset(game_type_id) # type: ignore
            # ... similarly for P2, P3, P4
        elif category == "tile" or "platform" in game_type_id.lower():
             platforms_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': game_type_id, 'properties': obj_props})
        elif category == "enemy":
             enemies_list_export.append({'start_pos': (export_x + obj_w / 2.0, export_y + obj_h), 'type': game_type_id, 'properties': obj_props})
        elif "ladder" in game_type_id.lower(): ladders_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': 'ladder', 'properties': obj_props})
        elif "hazard" in game_type_id.lower(): hazards_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': game_type_id, 'properties': obj_props})
        elif category == "item": items_list_export.append({'pos': (export_x + obj_w / 2.0, export_y + obj_h / 2.0), 'type': game_type_id, 'properties': obj_props})
        elif "object_stone" in game_type_id.lower(): statue_list_export.append({'id': obj_data.get("unique_id", f"statue_{len(statue_list_export)}"), 'pos': (export_x + obj_w / 2.0, export_y + obj_h / 2.0), 'properties': obj_props})
        elif category == "background_tile": background_tiles_data_raw.append({'x': export_x, 'y': export_y, 'w': obj_w, 'h': obj_h, 'color': final_color_for_export, 'type': game_type_id, 'image_path': asset_entry_from_palette.get("source_file") if asset_entry_from_palette else None, 'properties': obj_props})

    if not player_start_pos_p1: # Default P1 spawn if none placed
        p1_spawn_def = ED_CONFIG.EDITOR_PALETTE_ASSETS.get("player1_spawn",{})
        p1_game_id = p1_spawn_def.get("game_type_id")
        if p1_game_id: player1_spawn_props = ED_CONFIG.get_default_properties_for_asset(p1_game_id) # type: ignore
        player_start_pos_p1 = (ts * 2.5, editor_state.map_height_tiles * ts - ts * 3) # Example default

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
    # ... (ground level ref logic)

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
    for key_default_list in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list", 
                             "enemies_list", "items_list", "statues_list", "custom_images_list", "trigger_squares_list"]:
        final_game_data_for_script.setdefault(key_default_list, [])


    script_content_parts = [f"# Level Data: {editor_state.map_name_for_function}", "# Generated by Platformer Level Editor", "", f"def {game_function_name}():", "    game_data = {"]
    for data_key, data_value in final_game_data_for_script.items(): script_content_parts.append(f"        '{data_key}': {repr(data_value)},") 
    script_content_parts.extend(["    }", "    return game_data", "", "if __name__ == '__main__':", f"    data = {game_function_name}()", "    import json", "    print(json.dumps(data, indent=4))"])
    script_content = "\n".join(script_content_parts)
    try:
        with open(str(py_filepath_to_use), "w", encoding='utf-8') as f: f.write(script_content) # Added encoding
        logger.info(f"Map data exported to game script: {os.path.basename(str(py_filepath_to_use))}")
        return True
    except Exception as e:
        logger.error(f"Error exporting map data to .py '{py_filepath_to_use}': {e}", exc_info=True)
        return False

def delete_map_folder_and_contents(editor_state: EditorState, map_name_to_delete: str) -> bool:
    """Deletes the entire folder for the given map name."""
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
    print("Running editor_map_utils.py directly (e.g., for batch fixing if needed).")

#################### END OF FILE: editor\editor_map_utils.py ####################