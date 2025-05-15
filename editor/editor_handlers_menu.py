# editor/editor_handlers_menu.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events for the main menu of the editor.
Ensures correct filename handling for rename operations.
"""
import pygame
import os
import logging
from typing import Optional

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_text_input_dialog, start_file_load_dialog
from editor_map_utils import (init_new_map_state, save_map_to_json,
                              load_map_from_json, export_map_to_game_python_script,
                              delete_map_files)

logger = logging.getLogger(__name__)

# --- Callbacks for the rename dialogs ---
def _handle_rename_get_new_name(new_name_str: str, old_base_filename_no_ext: str, editor_state: EditorState):
    """
    Called when the user confirms the new name in the text input dialog.
    old_base_filename_no_ext is the original filename without path and without .json extension (e.g., "my_map")
    """
    logger.info(f"Attempting to rename '{old_base_filename_no_ext}' to '{new_name_str}'")
    new_name_str = new_name_str.strip()

    if not new_name_str or new_name_str == old_base_filename_no_ext:
        editor_state.set_status_message("Rename cancelled or name unchanged/empty.", 2)
        logger.info("Rename cancelled: name unchanged or empty.")
        return

    # Basic validation for new_name_str
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(char in new_name_str for char in invalid_chars):
        editor_state.set_status_message("New name contains invalid characters.", 3)
        logger.warning(f"Invalid new name provided: '{new_name_str}'")
        # Re-open dialog for new name
        start_text_input_dialog(
            editor_state,
            prompt=f"Invalid name. New name for '{old_base_filename_no_ext}':",
            default_text=new_name_str, # Keep the invalid text for user to correct
            on_confirm=lambda new_val: _handle_rename_get_new_name(new_val, old_base_filename_no_ext, editor_state),
            on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
            is_initially_selected=True # Re-select the text
        )
        return

    # Construct full paths for old and new files
    old_json_filename = old_base_filename_no_ext + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    old_py_filename = old_base_filename_no_ext + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION

    old_full_path_json = os.path.join(ED_CONFIG.MAPS_DIRECTORY, old_json_filename)
    old_full_path_py = os.path.join(ED_CONFIG.MAPS_DIRECTORY, old_py_filename)

    new_json_filename = new_name_str + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    new_py_filename = new_name_str + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION

    new_full_path_json = os.path.join(ED_CONFIG.MAPS_DIRECTORY, new_json_filename)
    new_full_path_py = os.path.join(ED_CONFIG.MAPS_DIRECTORY, new_py_filename)


    if not os.path.exists(old_full_path_json):
        editor_state.set_status_message(f"Error: Original map JSON '{old_json_filename}' not found.", 3)
        logger.error(f"Original map JSON for rename not found: {old_full_path_json}")
        return

    # Check if new filenames already exist (excluding the old ones if name is just case change)
    if os.path.normcase(old_full_path_json) != os.path.normcase(new_full_path_json) and os.path.exists(new_full_path_json):
        editor_state.set_status_message(f"Error: JSON file '{new_json_filename}' already exists.", 3)
        logger.warning(f"Target JSON rename path already exists: {new_full_path_json}")
        start_text_input_dialog(
            editor_state,
            prompt=f"Name '{new_name_str}' (JSON) exists. New name for '{old_base_filename_no_ext}':",
            default_text=new_name_str,
            on_confirm=lambda new_val: _handle_rename_get_new_name(new_val, old_base_filename_no_ext, editor_state),
            on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
            is_initially_selected=True # Re-select the text
        )
        return

    if os.path.normcase(old_full_path_py) != os.path.normcase(new_full_path_py) and os.path.exists(new_full_path_py):
        editor_state.set_status_message(f"Error: Python file '{new_py_filename}' already exists.", 3)
        logger.warning(f"Target PY rename path already exists: {new_full_path_py}")
        start_text_input_dialog(
            editor_state,
            prompt=f"Name '{new_name_str}' (PY) exists. New name for '{old_base_filename_no_ext}':",
            default_text=new_name_str,
            on_confirm=lambda new_val: _handle_rename_get_new_name(new_val, old_base_filename_no_ext, editor_state),
            on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
            is_initially_selected=True # Re-select the text
        )
        return

    try:
        # Rename JSON file
        os.rename(old_full_path_json, new_full_path_json)
        logger.info(f"Successfully renamed '{old_full_path_json}' to '{new_full_path_json}'")

        # Rename corresponding PY file if it exists
        if os.path.exists(old_full_path_py):
            os.rename(old_full_path_py, new_full_path_py)
            logger.info(f"Successfully renamed '{old_full_path_py}' to '{new_full_path_py}'")
        else:
            logger.info(f"Original PY file '{old_full_path_py}' not found, skipping its rename.")

        editor_state.set_status_message(f"Map '{old_base_filename_no_ext}' renamed to '{new_name_str}'.", 3)

        # If the currently loaded map was renamed
        if editor_state.current_loaded_map_path and \
           os.path.normpath(editor_state.current_loaded_map_path) == os.path.normpath(old_full_path_json):
            editor_state.current_loaded_map_path = new_full_path_json
            editor_state.current_map_filename = new_py_filename # Update to new .py filename
            editor_state.map_name_for_function = new_name_str # This should be the base name
            if editor_state.current_editor_mode == "editing_map":
                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            logger.info(f"Updated current_loaded_map_path to new name: {new_full_path_json}")

    except OSError as e:
        editor_state.set_status_message(f"Error renaming map: {e}", 4)
        logger.error(f"OSError during rename: {e}", exc_info=True)
    finally:
        editor_state.active_dialog_type = None # Ensure dialog is closed

def _handle_rename_select_map(selected_path_from_dialog: str, editor_state: EditorState):
    """
    Called when the user selects a map to rename from the file dialog.
    selected_path_from_dialog is the path to the file (e.g., "maps/my_map.json")
    """
    logger.info(f"Map selected for rename (path from dialog): '{selected_path_from_dialog}'")

    if not selected_path_from_dialog:
        editor_state.set_status_message("Rename cancelled: No map selected.", 1)
        logger.info("Rename cancelled: no map selected from dialog.")
        return

    # Get the actual filename (e.g., "my_map.json") from the path
    filename_with_ext = os.path.basename(selected_path_from_dialog)

    # Get the name without the .json extension for the prompt and default text
    base_name_no_ext = os.path.splitext(filename_with_ext)[0]

    start_text_input_dialog(
        editor_state,
        prompt=f"Enter new name for '{base_name_no_ext}':",      # Use just the base name (e.g., 'yes')
        default_text=base_name_no_ext,                          # Use just the base name (e.g., 'yes')
        # Pass the original base name (without extension) to the next step
        on_confirm=lambda new_name: _handle_rename_get_new_name(new_name, base_name_no_ext, editor_state),
        on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
        is_initially_selected=True
    )

def start_rename_map_flow(editor_state: EditorState):
    """
    Initiates the map renaming process by showing the file selection dialog.
    """
    logger.info("Starting rename map flow.")
    start_file_load_dialog(
        editor_state,
        # The 'path_from_dialog' lambda parameter will receive the full path from the file dialog
        on_confirm=lambda path_from_dialog: _handle_rename_select_map(path_from_dialog, editor_state),
        on_cancel=lambda: editor_state.set_status_message("Rename map cancelled.", 1),
        prompt_override="Select Map to Rename",
        file_extension=ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION # Ensure we list .json files
    )

def handle_menu_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface):
    """
    Processes events when in the main menu mode.
    """
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos
        ui_rects = editor_state.ui_elements_rects

        if ui_rects.get("menu_new_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'New Map' button clicked.")
            def on_new_map_name(name:str):
                name=name.strip()
                if not name:
                    editor_state.set_status_message("Map name empty.",3)
                    start_text_input_dialog(editor_state,"Name:","",on_new_map_name,lambda:None, is_initially_selected=True)
                    return
                # Basic validation for new map name (similar to rename)
                invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                if any(char in name for char in invalid_chars):
                    editor_state.set_status_message("Map name contains invalid characters.", 3)
                    logger.warning(f"Invalid new map name provided: '{name}'")
                    start_text_input_dialog(editor_state, "Invalid Name. New Map Name:", name, on_new_map_name, lambda: None, is_initially_selected=True)
                    return

                # Check if map already exists
                potential_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, name + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
                potential_py_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, name + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)
                if os.path.exists(potential_json_path) or os.path.exists(potential_py_path):
                    editor_state.set_status_message(f"Map '{name}' already exists.", 3)
                    logger.warning(f"Attempt to create new map with existing name: '{name}'")
                    start_text_input_dialog(editor_state, f"Name '{name}' exists. New Map Name:", name, on_new_map_name, lambda:None, is_initially_selected=True)
                    return

                editor_state.map_name_for_function_input=name # Store the validated name
                def on_map_size(size_str:str):
                    try:
                        w,h=map(int,size_str.replace(" ","").split(','))
                        # Assuming MAX_MAP_WIDTH_TILES and MAX_MAP_HEIGHT_TILES are defined in ED_CONFIG
                        max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 500) 
                        max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 500)
                        if not(w>0 and h>0 and w <= max_w and h <= max_h):
                             raise ValueError(f"Dims must be >0 and <= max ({max_w}x{max_h})")
                        init_new_map_state(editor_state,editor_state.map_name_for_function_input,w,h)
                        if save_map_to_json(editor_state)and export_map_to_game_python_script(editor_state):
                            editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' auto-saved.",3)
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                        else:
                            editor_state.set_status_message(f"Auto-save fail for '{editor_state.map_name_for_function}'.",4)
                            editor_state.unsaved_changes=True
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        editor_state.current_editor_mode="editing_map"
                    except Exception as e:
                        editor_state.set_status_message(f"Invalid size:{e}",3.5)
                        start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None, is_initially_selected=True)
                start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None, is_initially_selected=True)
            start_text_input_dialog(editor_state,"New Map Name:","my_map",on_new_map_name,lambda:None, is_initially_selected=True)

        elif ui_rects.get("menu_load_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Load Map' button clicked.")
            def on_file_sel(path_from_dialog:str): # path_from_dialog is the full path (e.g., "maps/ok.json")
                # load_map_from_json expects the full path, so path_from_dialog is used directly.
                logger.debug(f"Attempting to load map from: {path_from_dialog}")
                if load_map_from_json(editor_state, path_from_dialog):
                    editor_state.current_editor_mode="editing_map"
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                else:
                    logger.error(f"Failed to load map from {path_from_dialog}")
                    # Status message is set within load_map_from_json on failure
            start_file_load_dialog(editor_state,on_confirm=on_file_sel,on_cancel=lambda:None)

        elif ui_rects.get("menu_rename_map", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Rename Map' button clicked.")
            start_rename_map_flow(editor_state) # This flow correctly handles paths now

        elif ui_rects.get("menu_delete_map", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Delete Map' button clicked.")
            def on_delete_file_selected(path_from_dialog: str): # path_from_dialog is full path e.g., "maps/ok.json"
                if path_from_dialog:
                    # delete_map_files expects the full path to the .json file
                    map_name_to_delete = os.path.splitext(os.path.basename(path_from_dialog))[0]
                    logger.info(f"Attempting deletion of map: {map_name_to_delete} (Path: {path_from_dialog})")

                    if delete_map_files(editor_state, path_from_dialog):
                        editor_state.set_status_message(f"Map '{map_name_to_delete}' deleted.", 3)
                        current_map_base_name_if_loaded = ""
                        if editor_state.current_loaded_map_path:
                             current_map_base_name_if_loaded = os.path.splitext(os.path.basename(editor_state.current_loaded_map_path))[0]

                        if editor_state.map_name_for_function == map_name_to_delete or \
                           current_map_base_name_if_loaded == map_name_to_delete:
                            logger.info(f"Map '{map_name_to_delete}' which might have been active was deleted. Resetting map context.")
                            editor_state.reset_map_context()
                            if editor_state.current_editor_mode == "editing_map":
                                editor_state.current_editor_mode = "menu"
                                pygame.display.set_caption("Platformer Level Editor - Menu")
                else:
                    editor_state.set_status_message("No map selected for deletion.", 2)

            start_file_load_dialog(editor_state,
                                   prompt_override="Select Map to PERMANENTLY DELETE",
                                   on_confirm=on_delete_file_selected,
                                   on_cancel=lambda: editor_state.set_status_message("Delete operation cancelled.", 2),
                                   file_extension=ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)

        elif ui_rects.get("menu_quit",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Quit' button clicked.")
            pygame.event.post(pygame.event.Event(pygame.QUIT))