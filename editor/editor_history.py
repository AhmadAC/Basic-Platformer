#################### START OF FILE: editor_history.py ####################

# editor/editor_history.py
# -*- coding: utf-8 -*-
"""
## version 2.2.1 (Rotation and Flip Aware Snapshot/Restore)
Manages undo/redo functionality for the Level Editor.
Ensures custom object properties like dimensions, layer order, crop_rect,
rotation, and flip state are included.
Refined deep copying for placed_objects.
"""
import json
import logging
from typing import List, Dict, Any, Optional, cast, Union

from .editor_state import EditorState
from . import editor_config as ED_CONFIG

logger = logging.getLogger(__name__)

MAX_HISTORY_STATES = 50

def _deep_copy_object_data(obj_data: Dict[str, Any]) -> Dict[str, Any]:
    """Performs a deeper copy of an object's data dictionary."""
    copied_obj = {}
    for k, v in obj_data.items():
        if isinstance(v, dict):
            copied_obj[k] = v.copy() # Shallow copy for sub-dictionaries like 'properties', 'crop_rect'
        elif isinstance(v, list):
            copied_obj[k] = v[:]    # Shallow copy for lists
        else:
            copied_obj[k] = v       # Direct assignment for simple types
    return copied_obj

def get_map_snapshot(editor_state: EditorState) -> Dict[str, Any]:
    """Captures the current serializable state of the map."""
    snapshot = {
        "map_name_for_function": editor_state.map_name_for_function,
        "map_width_tiles": editor_state.map_width_tiles,
        "map_height_tiles": editor_state.map_height_tiles,
        "grid_size": editor_state.grid_size,
        "background_color": list(editor_state.background_color),
        "placed_objects": [_deep_copy_object_data(obj) for obj in editor_state.placed_objects],
        "camera_offset_x": editor_state.camera_offset_x,
        "camera_offset_y": editor_state.camera_offset_y,
        "zoom_level": editor_state.zoom_level,
        "show_grid": editor_state.show_grid,
        "asset_specific_variables": {k: v.copy() for k, v in editor_state.asset_specific_variables.items()}
    }
    # Ensure all necessary fields are present in each object for the snapshot
    for obj in snapshot["placed_objects"]:
        obj.setdefault("rotation", 0)
        obj.setdefault("is_flipped_h", False)
        if "override_color" in obj and isinstance(obj["override_color"], tuple):
            obj["override_color"] = list(obj["override_color"])
        if "properties" in obj and isinstance(obj["properties"], dict):
            props = obj["properties"]
            if "fill_color_rgba" in props and isinstance(props["fill_color_rgba"], tuple):
                props["fill_color_rgba"] = list(props["fill_color_rgba"])
    return snapshot

def restore_map_from_snapshot(editor_state: EditorState, snapshot: Dict[str, Any]):
    """Restores the map state from a snapshot."""
    editor_state.map_name_for_function = snapshot.get("map_name_for_function", "untitled_map")
    editor_state.map_width_tiles = snapshot.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES) # type: ignore
    editor_state.map_height_tiles = snapshot.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES) # type: ignore
    editor_state.grid_size = snapshot.get("grid_size", ED_CONFIG.BASE_GRID_SIZE) # type: ignore

    bg_color_data = snapshot.get("background_color", list(ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE)) # type: ignore
    editor_state.background_color = tuple(cast(List[int], bg_color_data)) # type: ignore

    loaded_objects_raw = snapshot.get("placed_objects", [])
    restored_objects: List[Dict[str,Any]] = []

    game_id_to_palette_key_map: Dict[str, str] = {}
    if hasattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS'):
        for pk, p_data in ED_CONFIG.EDITOR_PALETTE_ASSETS.items(): # type: ignore
            gid = p_data.get("game_type_id")
            if gid: game_id_to_palette_key_map[gid] = pk
    else:
        logger.error("ED_CONFIG.EDITOR_PALETTE_ASSETS not found. Asset key remapping may fail.")

    for obj_data_raw in loaded_objects_raw:
        new_obj = _deep_copy_object_data(obj_data_raw)

        # Ensure orientation fields exist, defaulting if from older save
        new_obj.setdefault("rotation", 0)
        new_obj.setdefault("is_flipped_h", False)

        if "override_color" in new_obj and isinstance(new_obj["override_color"], list):
            new_obj["override_color"] = tuple(new_obj["override_color"])
        
        if "properties" in new_obj and isinstance(new_obj["properties"], dict):
            props = new_obj["properties"]
            if "fill_color_rgba" in props and isinstance(props["fill_color_rgba"], list):
                props["fill_color_rgba"] = tuple(props["fill_color_rgba"])

        current_asset_editor_key = new_obj.get("asset_editor_key")
        game_id: Optional[str] = new_obj.get("game_type_id") # type: ignore

        is_custom_image = (current_asset_editor_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) # type: ignore
        is_trigger_square = (current_asset_editor_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY) # type: ignore

        if not is_custom_image and not is_trigger_square:
            if current_asset_editor_key not in ED_CONFIG.EDITOR_PALETTE_ASSETS and game_id: # type: ignore
                canonical_palette_key = game_id_to_palette_key_map.get(game_id)
                if canonical_palette_key:
                    logger.info(f"Remapping standard asset from '{current_asset_editor_key}' to '{canonical_palette_key}' (GameID: '{game_id}').")
                    new_obj["asset_editor_key"] = canonical_palette_key
                elif current_asset_editor_key:
                     logger.warning(f"Cannot find palette key for standard asset '{current_asset_editor_key}' (GameID: '{game_id}').")
        
        needs_props_dict = False
        if game_id and game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: # type: ignore
            needs_props_dict = True
        elif is_custom_image or is_trigger_square:
            needs_props_dict = True
        
        if needs_props_dict and ("properties" not in new_obj or not isinstance(new_obj.get("properties"), dict)):
            new_obj["properties"] = {}
            if game_id:
                 default_props = ED_CONFIG.get_default_properties_for_asset(game_id) # type: ignore
                 if default_props:
                     new_obj["properties"].update(default_props)
        
        if is_custom_image or is_trigger_square:
            default_w = ED_CONFIG.BASE_GRID_SIZE * 2 if is_trigger_square else ED_CONFIG.BASE_GRID_SIZE # type: ignore
            default_h = ED_CONFIG.BASE_GRID_SIZE * 2 if is_trigger_square else ED_CONFIG.BASE_GRID_SIZE # type: ignore
            
            new_obj.setdefault("current_width", default_w)
            new_obj.setdefault("current_height", default_h)
            new_obj.setdefault("layer_order", 0)
            if is_custom_image:
                new_obj.setdefault("original_width", new_obj["current_width"])
                new_obj.setdefault("original_height", new_obj["current_height"])

        restored_objects.append(new_obj)
    editor_state.placed_objects = restored_objects

    editor_state.camera_offset_x = snapshot.get("camera_offset_x", 0.0)
    editor_state.camera_offset_y = snapshot.get("camera_offset_y", 0.0)
    editor_state.zoom_level = snapshot.get("zoom_level", 1.0)
    editor_state.show_grid = snapshot.get("show_grid", True)
    editor_state.asset_specific_variables = {k: v.copy() for k, v in snapshot.get("asset_specific_variables", {}).items()}
    editor_state.unsaved_changes = True # Restoring a snapshot implies it's a change from current file state
    logger.info(f"Map state restored from snapshot. Unsaved changes: {editor_state.unsaved_changes}")


def push_undo_state(editor_state: EditorState):
    if not hasattr(editor_state, 'undo_stack'): editor_state.undo_stack = []
    if not hasattr(editor_state, 'redo_stack'): editor_state.redo_stack = []

    snapshot = get_map_snapshot(editor_state)
    try:
        # Avoid pushing identical consecutive states
        if editor_state.undo_stack and json.dumps(editor_state.undo_stack[-1], sort_keys=True) == json.dumps(snapshot, sort_keys=True):
            logger.debug("Skipped pushing identical state to undo stack.")
            return
        editor_state.undo_stack.append(snapshot)
    except TypeError as e:
        logger.error(f"Failed to create snapshot for undo: {e}. Snapshot details problematic.", exc_info=True)
        return

    if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
        editor_state.undo_stack.pop(0)
    if editor_state.redo_stack:
        editor_state.redo_stack.clear() # Clear redo stack on new action
    logger.debug(f"Pushed state to undo stack. Size: {len(editor_state.undo_stack)}")

def undo(editor_state: EditorState) -> bool:
    if not hasattr(editor_state, 'undo_stack') or not editor_state.undo_stack: 
        logger.debug("Undo stack empty.")
        return False

    current_snapshot_for_redo = get_map_snapshot(editor_state)
    try:
        if not hasattr(editor_state, 'redo_stack'): editor_state.redo_stack = []
        editor_state.redo_stack.append(current_snapshot_for_redo)
        if len(editor_state.redo_stack) > MAX_HISTORY_STATES: editor_state.redo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create snapshot for redo: {e}", exc_info=True)
        return False

    snapshot_to_restore = editor_state.undo_stack.pop()
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Undo successful. Undo: {len(editor_state.undo_stack)}, Redo: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Error during undo restore: {e}", exc_info=True)
        # If restore fails, try to put the state back onto the redo stack if it was valid
        # This is tricky, as the current state is now polluted.
        # Best to signal failure and let user save/reload if needed.
        return False

def redo(editor_state: EditorState) -> bool:
    if not hasattr(editor_state, 'redo_stack') or not editor_state.redo_stack: 
        logger.debug("Redo stack empty.")
        return False

    current_snapshot_for_undo = get_map_snapshot(editor_state)
    try:
        if not hasattr(editor_state, 'undo_stack'): editor_state.undo_stack = []
        editor_state.undo_stack.append(current_snapshot_for_undo)
        if len(editor_state.undo_stack) > MAX_HISTORY_STATES: editor_state.undo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create snapshot for undo (during redo): {e}", exc_info=True)
        return False

    snapshot_to_restore = editor_state.redo_stack.pop()
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Redo successful. Undo: {len(editor_state.undo_stack)}, Redo: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Error during redo restore: {e}", exc_info=True)
        return False

#################### END OF FILE: editor_history.py ####################