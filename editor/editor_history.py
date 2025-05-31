#################### START OF FILE: editor_history.py ####################
# editor/editor_history.py
# -*- coding: utf-8 -*-
"""
## version 2.2.3 (Robust Deepcopy for History)
Manages undo/redo functionality for the Level Editor.
Ensures custom object properties like dimensions, layer order, crop_rect,
rotation, flip state, and editor-specific hide/lock states are included.
Uses copy.deepcopy for placed_objects to ensure true snapshots and prevent reference issues.
"""
import json
import logging
from typing import List, Dict, Any, Optional, cast, Union
import copy # Import the copy module

from editor.editor_state import EditorState
from editor import editor_config as ED_CONFIG

logger = logging.getLogger(__name__)

MAX_HISTORY_STATES = 50

# _deep_copy_object_data is no longer strictly needed if we deepcopy the whole list,
# but it can be kept if there are specific per-object transformations desired during snapshotting
# that deepcopy alone wouldn't handle (e.g., converting tuples to lists for JSON).
# For now, let's rely on deepcopy for the main structure.

def get_map_snapshot(editor_state: EditorState) -> Dict[str, Any]:
    """Captures the current serializable state of the map using deepcopy."""
    snapshot = {
        "map_name_for_function": editor_state.map_name_for_function,
        "map_width_tiles": editor_state.map_width_tiles,
        "map_height_tiles": editor_state.map_height_tiles,
        "grid_size": editor_state.grid_size,
        "background_color": list(editor_state.background_color), # Convert tuple to list for JSON
        "placed_objects": copy.deepcopy(editor_state.placed_objects), # Deepcopy the entire list
        "camera_offset_x": editor_state.camera_offset_x,
        "camera_offset_y": editor_state.camera_offset_y,
        "zoom_level": editor_state.zoom_level,
        "show_grid": editor_state.show_grid,
        "asset_specific_variables": copy.deepcopy(editor_state.asset_specific_variables)
    }
    # Ensure color tuples within the deepcopied objects are lists for JSON
    for obj in snapshot["placed_objects"]:
        if "override_color" in obj and isinstance(obj["override_color"], tuple):
            obj["override_color"] = list(obj["override_color"])
        if "properties" in obj and isinstance(obj["properties"], dict):
            props = obj["properties"]
            if "fill_color_rgba" in props and isinstance(props["fill_color_rgba"], tuple):
                props["fill_color_rgba"] = list(props["fill_color_rgba"])
    return snapshot

def restore_map_from_snapshot(editor_state: EditorState, snapshot: Dict[str, Any]):
    """Restores the map state from a snapshot using deepcopy."""
    editor_state.map_name_for_function = snapshot.get("map_name_for_function", "untitled_map")
    editor_state.map_width_tiles = snapshot.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES) # type: ignore
    editor_state.map_height_tiles = snapshot.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES) # type: ignore
    editor_state.grid_size = snapshot.get("grid_size", ED_CONFIG.BASE_GRID_SIZE) # type: ignore

    bg_color_data = snapshot.get("background_color", list(ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE)) # type: ignore
    editor_state.background_color = tuple(cast(List[int], bg_color_data)) # type: ignore

    # Deepcopy when restoring to ensure the live state also consists of new, independent objects
    loaded_objects_raw = snapshot.get("placed_objects", [])
    editor_state.placed_objects = copy.deepcopy(loaded_objects_raw)


    game_id_to_palette_key_map: Dict[str, str] = {}
    if hasattr(ED_CONFIG, 'EDITOR_PALETTE_ASSETS'):
        for pk, p_data in ED_CONFIG.EDITOR_PALETTE_ASSETS.items(): # type: ignore
            gid = p_data.get("game_type_id")
            if gid: game_id_to_palette_key_map[gid] = pk
    else:
        logger.error("ED_CONFIG.EDITOR_PALETTE_ASSETS not found. Asset key remapping may fail.")

    # Post-deepcopy processing for specific fields (like ensuring tuples for colors)
    for obj_data in editor_state.placed_objects:
        obj_data.setdefault("rotation", 0)
        obj_data.setdefault("is_flipped_h", False)
        obj_data.setdefault("editor_hidden", False) 
        obj_data.setdefault("editor_locked", False) 

        if "override_color" in obj_data and isinstance(obj_data["override_color"], list):
            obj_data["override_color"] = tuple(obj_data["override_color"])
        
        if "properties" in obj_data and isinstance(obj_data["properties"], dict):
            props = obj_data["properties"]
            if "fill_color_rgba" in props and isinstance(props["fill_color_rgba"], list):
                props["fill_color_rgba"] = tuple(props["fill_color_rgba"])

        current_asset_editor_key = obj_data.get("asset_editor_key")
        game_id: Optional[str] = obj_data.get("game_type_id") # type: ignore

        is_custom_image = (current_asset_editor_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) # type: ignore
        is_trigger_square = (current_asset_editor_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY) # type: ignore

        if not is_custom_image and not is_trigger_square:
            if current_asset_editor_key not in ED_CONFIG.EDITOR_PALETTE_ASSETS and game_id: # type: ignore
                canonical_palette_key = game_id_to_palette_key_map.get(game_id)
                if canonical_palette_key:
                    logger.info(f"Remapping standard asset from '{current_asset_editor_key}' to '{canonical_palette_key}' (GameID: '{game_id}').")
                    obj_data["asset_editor_key"] = canonical_palette_key
                elif current_asset_editor_key:
                     logger.warning(f"Cannot find palette key for standard asset '{current_asset_editor_key}' (GameID: '{game_id}').")
        
        needs_props_dict = False
        if game_id and game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: # type: ignore
            needs_props_dict = True
        elif is_custom_image or is_trigger_square:
            needs_props_dict = True
        
        if needs_props_dict and ("properties" not in obj_data or not isinstance(obj_data.get("properties"), dict)):
            obj_data["properties"] = {}
            if game_id:
                 default_props = ED_CONFIG.get_default_properties_for_asset(game_id) # type: ignore
                 if default_props:
                     obj_data["properties"].update(default_props)
        
        if is_custom_image or is_trigger_square:
            default_w = ED_CONFIG.BASE_GRID_SIZE * 2 if is_trigger_square else ED_CONFIG.BASE_GRID_SIZE # type: ignore
            default_h = ED_CONFIG.BASE_GRID_SIZE * 2 if is_trigger_square else ED_CONFIG.BASE_GRID_SIZE # type: ignore
            
            obj_data.setdefault("current_width", default_w)
            obj_data.setdefault("current_height", default_h)
            obj_data.setdefault("layer_order", 0)
            if is_custom_image:
                obj_data.setdefault("original_width", obj_data["current_width"])
                obj_data.setdefault("original_height", obj_data["current_height"])

    editor_state.camera_offset_x = snapshot.get("camera_offset_x", 0.0)
    editor_state.camera_offset_y = snapshot.get("camera_offset_y", 0.0)
    editor_state.zoom_level = snapshot.get("zoom_level", 1.0)
    editor_state.show_grid = snapshot.get("show_grid", True)
    editor_state.asset_specific_variables = copy.deepcopy(snapshot.get("asset_specific_variables", {}))
    editor_state.unsaved_changes = True 
    logger.info(f"Map state restored from snapshot. Unsaved changes: {editor_state.unsaved_changes}")


def push_undo_state(editor_state: EditorState):
    if not hasattr(editor_state, 'undo_stack'): editor_state.undo_stack = []
    if not hasattr(editor_state, 'redo_stack'): editor_state.redo_stack = []

    # Get a snapshot of the current state BEFORE any modification that led to this call
    snapshot = get_map_snapshot(editor_state)
    
    try:
        current_snapshot_json = json.dumps(snapshot, sort_keys=True)
        if editor_state.undo_stack:
            # Compare with the JSON representation of the last state in the undo stack
            last_snapshot_on_stack_json = json.dumps(editor_state.undo_stack[-1], sort_keys=True)
            if last_snapshot_on_stack_json == current_snapshot_json:
                logger.debug("Skipped pushing identical state to undo stack (JSON match).")
                return
        
        editor_state.undo_stack.append(snapshot) # Append the deepcopied snapshot
    except TypeError as e:
        logger.error(f"Failed to create snapshot for undo (JSON dump error): {e}. Snapshot details problematic.", exc_info=True)
        return

    if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
        editor_state.undo_stack.pop(0)
    if editor_state.redo_stack: # If a new action is performed, clear the redo stack
        editor_state.redo_stack.clear() 
    logger.debug(f"Pushed state to undo stack. Size: {len(editor_state.undo_stack)}")

def undo(editor_state: EditorState) -> bool:
    if not hasattr(editor_state, 'undo_stack') or not editor_state.undo_stack: 
        logger.debug("Undo stack empty.")
        return False

    # Current state becomes a redo state
    current_snapshot_for_redo = get_map_snapshot(editor_state)
    try:
        if not hasattr(editor_state, 'redo_stack'): editor_state.redo_stack = []
        editor_state.redo_stack.append(current_snapshot_for_redo)
        if len(editor_state.redo_stack) > MAX_HISTORY_STATES: editor_state.redo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create snapshot for redo: {e}", exc_info=True)
        # Don't necessarily fail the undo operation if redo snapshot fails
    
    snapshot_to_restore = editor_state.undo_stack.pop()
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Undo successful. Undo: {len(editor_state.undo_stack)}, Redo: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Error during undo restore: {e}", exc_info=True)
        # Attempt to put the failed state back onto the undo stack? Or clear?
        # For now, let's assume the state might be corrupted, so we don't put it back.
        return False

def redo(editor_state: EditorState) -> bool:
    if not hasattr(editor_state, 'redo_stack') or not editor_state.redo_stack: 
        logger.debug("Redo stack empty.")
        return False

    # Current state becomes an undo state
    current_snapshot_for_undo = get_map_snapshot(editor_state)
    try:
        if not hasattr(editor_state, 'undo_stack'): editor_state.undo_stack = []
        editor_state.undo_stack.append(current_snapshot_for_undo)
        if len(editor_state.undo_stack) > MAX_HISTORY_STATES: editor_state.undo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create snapshot for undo (during redo): {e}", exc_info=True)
        # Don't necessarily fail the redo operation
        
    snapshot_to_restore = editor_state.redo_stack.pop()
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Redo successful. Undo: {len(editor_state.undo_stack)}, Redo: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Error during redo restore: {e}", exc_info=True)
        return False

#################### END OF FILE: editor_history.py ####################