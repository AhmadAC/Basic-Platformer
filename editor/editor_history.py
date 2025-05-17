# editor/editor_history.py
# -*- coding: utf-8 -*-
"""
Manages undo/redo functionality for the Level Editor.
"""
import pygame
import json
import logging
from typing import List, Dict, Any, Optional, cast

from editor_state import EditorState
import editor_config as ED_CONFIG # For default values if needed on restore

logger = logging.getLogger(__name__)

MAX_HISTORY_STATES = 50

def get_map_snapshot(editor_state: EditorState) -> Dict[str, Any]:
    """Captures the current serializable state of the map."""
    snapshot = {
        "map_name_for_function": editor_state.map_name_for_function,
        "map_width_tiles": editor_state.map_width_tiles,
        "map_height_tiles": editor_state.map_height_tiles,
        "grid_size": editor_state.grid_size,
        "background_color": list(editor_state.background_color),
        "placed_objects": [obj.copy() for obj in editor_state.placed_objects], # Deep copy list of dicts
        "camera_offset_x": editor_state.camera_offset_x,
        "camera_offset_y": editor_state.camera_offset_y,
        "show_grid": editor_state.show_grid,
        # Ensure asset_specific_variables are deep copied if they contain mutable structures
        "asset_specific_variables": {k: v.copy() for k, v in editor_state.asset_specific_variables.items()}
    }
    # Convert Pygame color tuples in placed_objects to lists for JSON consistency
    for obj in snapshot["placed_objects"]:
        if "override_color" in obj and isinstance(obj["override_color"], tuple):
            obj["override_color"] = list(obj["override_color"])
    return snapshot

def restore_map_from_snapshot(editor_state: EditorState, snapshot: Dict[str, Any]):
    """Restores the map state from a snapshot."""
    editor_state.map_name_for_function = snapshot.get("map_name_for_function", "untitled_map")
    editor_state.map_width_tiles = snapshot.get("map_width_tiles", ED_CONFIG.DEFAULT_MAP_WIDTH_TILES)
    editor_state.map_height_tiles = snapshot.get("map_height_tiles", ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES)
    editor_state.grid_size = snapshot.get("grid_size", ED_CONFIG.DEFAULT_GRID_SIZE)
    
    bg_color_data = snapshot.get("background_color", list(ED_CONFIG.DEFAULT_BACKGROUND_COLOR))
    editor_state.background_color = tuple(cast(List[int], bg_color_data)) # type: ignore

    # Ensure override_color is a tuple after loading
    loaded_objects = snapshot.get("placed_objects", [])
    restored_objects = []
    for obj_data in loaded_objects:
        new_obj = obj_data.copy()
        if "override_color" in new_obj and isinstance(new_obj["override_color"], list):
            new_obj["override_color"] = tuple(new_obj["override_color"]) # type: ignore
        restored_objects.append(new_obj)
    editor_state.placed_objects = restored_objects

    editor_state.camera_offset_x = snapshot.get("camera_offset_x", 0)
    editor_state.camera_offset_y = snapshot.get("camera_offset_y", 0)
    editor_state.show_grid = snapshot.get("show_grid", True)
    
    # Restore asset_specific_variables
    editor_state.asset_specific_variables = {k: v.copy() for k, v in snapshot.get("asset_specific_variables", {}).items()}

    editor_state.recreate_map_content_surface()
    editor_state.minimap_needs_regeneration = True
    editor_state.unsaved_changes = True # Restoring state implies a change from current
    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
    logger.info(f"Map state restored. Unsaved changes: {editor_state.unsaved_changes}")


def push_undo_state(editor_state: EditorState):
    """Saves the current map state to the undo stack."""
    if not hasattr(editor_state, 'undo_stack'):
        editor_state.undo_stack = []
    if not hasattr(editor_state, 'redo_stack'):
        editor_state.redo_stack = []

    snapshot = get_map_snapshot(editor_state)
    try:
        serialized_snapshot = json.dumps(snapshot) # Test serialization
    except TypeError as e:
        logger.error(f"Failed to serialize map state for undo: {e}. Snapshot: {snapshot}", exc_info=True)
        editor_state.set_status_message("Error: Could not save undo state (serialization failed).", 3)
        return

    editor_state.undo_stack.append(serialized_snapshot)
    if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
        editor_state.undo_stack.pop(0)
    
    # Clear redo stack whenever a new action is performed
    if editor_state.redo_stack:
        editor_state.redo_stack.clear()
        logger.debug("Cleared redo stack due to new action.")
    logger.debug(f"Pushed state to undo stack. Size: {len(editor_state.undo_stack)}")

def undo(editor_state: EditorState):
    """Restores the previous map state from the undo stack."""
    if not hasattr(editor_state, 'undo_stack') or not editor_state.undo_stack:
        editor_state.set_status_message("Nothing to undo.", 2)
        logger.debug("Undo called, but undo stack is empty.")
        return

    # Save current state to redo stack before undoing
    current_snapshot_for_redo = get_map_snapshot(editor_state)
    try:
        serialized_current_snapshot = json.dumps(current_snapshot_for_redo)
    except TypeError as e:
        logger.error(f"Failed to serialize current map state for redo: {e}", exc_info=True)
        editor_state.set_status_message("Error: Could not save redo state (serialization failed).", 3)
        return

    if not hasattr(editor_state, 'redo_stack'):
        editor_state.redo_stack = []
    editor_state.redo_stack.append(serialized_current_snapshot)
    if len(editor_state.redo_stack) > MAX_HISTORY_STATES:
        editor_state.redo_stack.pop(0)

    # Pop from undo stack and restore
    serialized_snapshot_to_restore = editor_state.undo_stack.pop()
    try:
        snapshot_to_restore = json.loads(serialized_snapshot_to_restore)
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        editor_state.set_status_message("Undo successful.", 2)
        logger.info(f"Undo successful. Undo stack size: {len(editor_state.undo_stack)}, Redo stack size: {len(editor_state.redo_stack)}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode snapshot from undo stack: {e}", exc_info=True)
        editor_state.set_status_message("Error: Could not restore undo state (deserialization failed).", 3)
        # Attempt to put the problematic state back if something went wrong, or just log and lose it
        # For simplicity, we'll lose it from undo stack to prevent repeated errors. Redo stack still has previous current.
    except Exception as e:
        logger.error(f"Unexpected error during undo restore: {e}", exc_info=True)
        editor_state.set_status_message("Error: Unexpected error during undo.", 3)


def redo(editor_state: EditorState):
    """Restores the next map state from the redo stack."""
    if not hasattr(editor_state, 'redo_stack') or not editor_state.redo_stack:
        editor_state.set_status_message("Nothing to redo.", 2)
        logger.debug("Redo called, but redo stack is empty.")
        return

    # Save current state to undo stack before redoing
    current_snapshot_for_undo = get_map_snapshot(editor_state)
    try:
        serialized_current_snapshot = json.dumps(current_snapshot_for_undo)
    except TypeError as e:
        logger.error(f"Failed to serialize current map state for undo (during redo): {e}", exc_info=True)
        editor_state.set_status_message("Error: Could not save undo state for redo (serialization failed).", 3)
        return
        
    if not hasattr(editor_state, 'undo_stack'):
        editor_state.undo_stack = []
    editor_state.undo_stack.append(serialized_current_snapshot)
    if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
        editor_state.undo_stack.pop(0)

    # Pop from redo stack and restore
    serialized_snapshot_to_restore = editor_state.redo_stack.pop()
    try:
        snapshot_to_restore = json.loads(serialized_snapshot_to_restore)
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        editor_state.set_status_message("Redo successful.", 2)
        logger.info(f"Redo successful. Undo stack size: {len(editor_state.undo_stack)}, Redo stack size: {len(editor_state.redo_stack)}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode snapshot from redo stack: {e}", exc_info=True)
        editor_state.set_status_message("Error: Could not restore redo state (deserialization failed).", 3)
    except Exception as e:
        logger.error(f"Unexpected error during redo restore: {e}", exc_info=True)
        editor_state.set_status_message("Error: Unexpected error during redo.", 3)