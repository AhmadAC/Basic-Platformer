# editor_history.py
# -*- coding: utf-8 -*-
"""
## version 2.0.0 (PySide6 Conversion)
Manages undo/redo functionality for the Level Editor.
Core logic remains largely UI-agnostic.
"""
# import pygame # No longer needed for set_caption here
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
        "placed_objects": [obj.copy() for obj in editor_state.placed_objects],
        "camera_offset_x": editor_state.camera_offset_x, # Still relevant for QGraphicsView scene coords
        "camera_offset_y": editor_state.camera_offset_y, # Still relevant for QGraphicsView scene coords
        "zoom_level": editor_state.zoom_level, # NEW: Store zoom level for Qt MapView
        "show_grid": editor_state.show_grid,
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
    editor_state.grid_size = snapshot.get("grid_size", ED_CONFIG.BASE_GRID_SIZE) # Use BASE_GRID_SIZE

    bg_color_data = snapshot.get("background_color", list(ED_CONFIG.DEFAULT_BACKGROUND_COLOR_TUPLE))
    editor_state.background_color = tuple(cast(List[int], bg_color_data))

    loaded_objects = snapshot.get("placed_objects", [])
    restored_objects = []
    for obj_data in loaded_objects:
        new_obj = obj_data.copy()
        if "override_color" in new_obj and isinstance(new_obj["override_color"], list):
            new_obj["override_color"] = tuple(new_obj["override_color"])
        # Ensure 'properties' key exists if asset has editable vars, even if empty
        game_id = new_obj.get("game_type_id")
        if game_id and game_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES and "properties" not in new_obj:
            new_obj["properties"] = {} # Initialize if missing
        restored_objects.append(new_obj)
    editor_state.placed_objects = restored_objects

    editor_state.camera_offset_x = snapshot.get("camera_offset_x", 0)
    editor_state.camera_offset_y = snapshot.get("camera_offset_y", 0)
    editor_state.zoom_level = snapshot.get("zoom_level", 1.0) # NEW: Restore zoom level
    editor_state.show_grid = snapshot.get("show_grid", True)

    editor_state.asset_specific_variables = {k: v.copy() for k, v in snapshot.get("asset_specific_variables", {}).items()}

    # UI updates are now triggered by the caller of undo/redo (e.g., EditorMainWindow)
    # This includes refreshing the MapViewWidget, minimap, and window title.
    # editor_state.recreate_map_content_surface() # Pygame specific
    # editor_state.minimap_needs_regeneration = True # Minimap refresh signal would be handled by Qt minimap widget
    editor_state.unsaved_changes = True # Restoring state implies a change from current
    # pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*") # Handled by EditorMainWindow

    logger.info(f"Map state restored from snapshot. Unsaved changes: {editor_state.unsaved_changes}")


def push_undo_state(editor_state: EditorState):
    """Saves the current map state to the undo stack."""
    if not hasattr(editor_state, 'undo_stack'): # Should be initialized in EditorState.__init__
        editor_state.undo_stack = []
    if not hasattr(editor_state, 'redo_stack'): # Should be initialized in EditorState.__init__
        editor_state.redo_stack = []

    snapshot = get_map_snapshot(editor_state)
    try:
        # Test serialization (optional, but good for catching issues early)
        # json.dumps(snapshot)
        # Store the Python dict directly; serialization to string is only for file saving.
        # Storing dicts avoids repeated dumps/loads for undo/redo.
        editor_state.undo_stack.append(snapshot) # Store the dict, not JSON string
    except TypeError as e:
        logger.error(f"Failed to create map state snapshot for undo: {e}. Snapshot: {snapshot}", exc_info=True)
        # editor_state.set_status_message("Error: Could not save undo state (snapshot failed).", 3) # Handled by MainWindow
        return

    if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
        editor_state.undo_stack.pop(0)

    if editor_state.redo_stack:
        editor_state.redo_stack.clear()
        logger.debug("Cleared redo stack due to new action.")
    logger.debug(f"Pushed state to undo stack. Size: {len(editor_state.undo_stack)}")

def undo(editor_state: EditorState) -> bool:
    """
    Restores the previous map state from the undo stack.
    Returns True if undo was performed, False otherwise.
    """
    if not hasattr(editor_state, 'undo_stack') or not editor_state.undo_stack:
        logger.debug("Undo called, but undo stack is empty.")
        return False

    current_snapshot_for_redo = get_map_snapshot(editor_state)
    try:
        # json.dumps(current_snapshot_for_redo) # Test serialization (optional)
        if not hasattr(editor_state, 'redo_stack'): editor_state.redo_stack = []
        editor_state.redo_stack.append(current_snapshot_for_redo) # Store dict
        if len(editor_state.redo_stack) > MAX_HISTORY_STATES:
            editor_state.redo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create current map state snapshot for redo: {e}", exc_info=True)
        return False # Cannot proceed if current state can't be saved for redo

    snapshot_to_restore = editor_state.undo_stack.pop() # This is a dict
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Undo successful. Undo stack size: {len(editor_state.undo_stack)}, Redo stack size: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error during undo restore: {e}", exc_info=True)
        # Attempt to put the problematic state back onto undo stack if restore failed mid-way?
        # Or just log and lose it. For simplicity, we'll consider it popped.
        # The redo stack still has the state *before* this failed undo.
        return False


def redo(editor_state: EditorState) -> bool:
    """
    Restores the next map state from the redo stack.
    Returns True if redo was performed, False otherwise.
    """
    if not hasattr(editor_state, 'redo_stack') or not editor_state.redo_stack:
        logger.debug("Redo called, but redo stack is empty.")
        return False

    current_snapshot_for_undo = get_map_snapshot(editor_state)
    try:
        # json.dumps(current_snapshot_for_undo) # Test serialization (optional)
        if not hasattr(editor_state, 'undo_stack'): editor_state.undo_stack = []
        editor_state.undo_stack.append(current_snapshot_for_undo) # Store dict
        if len(editor_state.undo_stack) > MAX_HISTORY_STATES:
            editor_state.undo_stack.pop(0)
    except TypeError as e:
        logger.error(f"Failed to create current map state for undo (during redo): {e}", exc_info=True)
        return False

    snapshot_to_restore = editor_state.redo_stack.pop() # This is a dict
    try:
        restore_map_from_snapshot(editor_state, snapshot_to_restore)
        logger.info(f"Redo successful. Undo stack size: {len(editor_state.undo_stack)}, Redo stack size: {len(editor_state.redo_stack)}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error during redo restore: {e}", exc_info=True)
        return False