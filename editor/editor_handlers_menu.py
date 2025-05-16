# editor/editor_handlers_menu.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events for the main menu of the editor.
Ensures correct filename handling for rename operations.
"""
import pygame
import os
import json
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
    new_name_str = new_name_str.strip().lower().replace(" ", "_").replace("-", "_") # Clean the new name

    if not new_name_str:
        editor_state.set_status_message("New name cannot be empty after cleaning.", 3)
        logger.warning("Rename cancelled: new name empty after cleaning.")
        start_text_input_dialog(
            editor_state,
            prompt=f"Name empty. New name for '{old_base_filename_no_ext}':",
            default_text=old_base_filename_no_ext,
            on_confirm=lambda new_val: _handle_rename_get_new_name(new_val, old_base_filename_no_ext, editor_state),
            on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
            is_initially_selected=True
        )
        return

    if new_name_str == old_base_filename_no_ext:
        editor_state.set_status_message("Rename cancelled: name unchanged.", 2)
        logger.info("Rename cancelled: name unchanged.")
        return

    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(char in new_name_str for char in invalid_chars):
        editor_state.set_status_message("New name contains invalid characters.", 3)
        logger.warning(f"Invalid new name provided (post-cleaning attempt): '{new_name_str}'")
        start_text_input_dialog(
            editor_state,
            prompt=f"Invalid name. New name for '{old_base_filename_no_ext}':",
            default_text=new_name_str,
            on_confirm=lambda new_val: _handle_rename_get_new_name(new_val, old_base_filename_no_ext, editor_state),
            on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
            is_initially_selected=True
        )
        return

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

    if os.path.normcase(old_full_path_json) != os.path.normcase(new_full_path_json) and os.path.exists(new_full_path_json):
        editor_state.set_status_message(f"Error: JSON file '{new_json_filename}' already exists.", 3)
        logger.warning(f"Target JSON rename path already exists: {new_full_path_json}")
        start_text_input_dialog( editor_state, prompt=f"Name '{new_name_str}' (JSON) exists. New name for '{old_base_filename_no_ext}':", default_text=new_name_str, on_confirm=lambda nv: _handle_rename_get_new_name(nv, old_base_filename_no_ext, editor_state), on_cancel=lambda: editor_state.set_status_message("Rename cancelled.",1),is_initially_selected=True)
        return

    if os.path.normcase(old_full_path_py) != os.path.normcase(new_full_path_py) and os.path.exists(new_full_path_py):
        editor_state.set_status_message(f"Error: Python file '{new_py_filename}' already exists.", 3)
        logger.warning(f"Target PY rename path already exists: {new_full_path_py}")
        start_text_input_dialog( editor_state, prompt=f"Name '{new_name_str}' (PY) exists. New name for '{old_base_filename_no_ext}':", default_text=new_name_str, on_confirm=lambda nv: _handle_rename_get_new_name(nv, old_base_filename_no_ext, editor_state), on_cancel=lambda: editor_state.set_status_message("Rename cancelled.",1),is_initially_selected=True)
        return

    try:
        # --- CRITICAL STEP: Load the content of the map being renamed if it's not already the active map ---
        map_data_loaded_for_rename = False
        
        is_currently_active_map_by_name = (editor_state.map_name_for_function == old_base_filename_no_ext)
        is_currently_active_map_by_json_path = (editor_state.current_json_filename and 
                                                os.path.normcase(editor_state.current_json_filename) == os.path.normcase(old_full_path_json))
        
        # Prioritize loading if the name matches or if the json path matches,
        # but only if the editor is in editing_map mode (or if we are forcing a load).
        # For rename, we always want the data of the file being renamed.

        if not (is_currently_active_map_by_name and editor_state.current_editor_mode == "editing_map"):
            logger.info(f"Map to rename ('{old_base_filename_no_ext}') is not the currently active map in editor mode ('{editor_state.map_name_for_function}'). Loading its data.")
            if load_map_from_json(editor_state, old_full_path_json):
                map_data_loaded_for_rename = True
                # load_map_from_json sets editor_state.map_name_for_function correctly to old_base_filename_no_ext
                logger.info(f"Successfully loaded data for '{old_base_filename_no_ext}' for rename operation.")
            else:
                logger.error(f"Failed to load data for '{old_base_filename_no_ext}' during rename. Aborting rename.")
                editor_state.set_status_message(f"Error loading map data for rename. Aborted.", 4)
                return
        else:
            logger.info(f"Map to rename ('{old_base_filename_no_ext}') is already active. Using current editor state content.")
            map_data_loaded_for_rename = True # Data is already in editor_state

        if not map_data_loaded_for_rename:
            logger.critical("Logic error: Map data was not available for rename export. Aborting.")
            return

        # Now, editor_state.placed_objects (and other map data) pertains to old_base_filename_no_ext.
        # And editor_state.map_name_for_function should be old_base_filename_no_ext.

        # 1. Rename JSON file on disk
        os.rename(old_full_path_json, new_full_path_json)
        logger.info(f"Successfully renamed file '{old_full_path_json}' to '{new_full_path_json}'")

        # 2. Update internal 'map_name_for_function' in the new JSON file
        # This JSON data *should* already reflect old_base_filename_no_ext from the load_map_from_json call
        # or from being the active map. We just need to change the name field.
        editor_state.map_name_for_function = new_name_str # Set the state to the new name before saving JSON
        
        # Create a dictionary with all current editor_state data for saving
        data_to_save_in_renamed_json = {
            "map_name_for_function": editor_state.map_name_for_function, # This is now new_name_str
            "map_width_tiles": editor_state.map_width_tiles,
            "map_height_tiles": editor_state.map_height_tiles,
            "grid_size": editor_state.grid_size,
            "background_color": list(editor_state.background_color),
            "placed_objects": editor_state.placed_objects, # These are objects from old_base_filename_no_ext
            "camera_offset_x": editor_state.camera_offset_x,
            "camera_offset_y": editor_state.camera_offset_y,
            "show_grid": editor_state.show_grid
        }
        try:
            with open(new_full_path_json, 'w') as f: # Write to the new JSON path
                json.dump(data_to_save_in_renamed_json, f, indent=4)
            logger.info(f"Updated 'map_name_for_function' to '{new_name_str}' and saved content to '{new_full_path_json}'")
        except Exception as e_json_update:
            logger.error(f"Error saving content to new JSON '{new_full_path_json}': {e_json_update}", exc_info=True)
            editor_state.set_status_message(f"Error saving to renamed JSON. Check logs.", 4)
            try: os.rename(new_full_path_json, old_full_path_json) # Attempt to roll back file rename
            except Exception as e_rename_back: logger.error(f"Failed to roll back JSON file rename: {e_rename_back}")
            return

        # 3. Rename corresponding PY file on disk if it exists
        if os.path.exists(old_full_path_py):
            try:
                os.rename(old_full_path_py, new_full_path_py)
                logger.info(f"Successfully renamed file '{old_full_path_py}' to '{new_full_path_py}'")
            except OSError as e_py_rename:
                logger.error(f"OSError renaming PY file '{old_full_path_py}' to '{new_full_path_py}': {e_py_rename}", exc_info=True)
                editor_state.set_status_message(f"Error renaming PY file. JSON updated. Check logs.", 4)
        else:
            logger.info(f"Original PY file '{old_full_path_py}' not found. It will be created by export.")

        # 4. Finalize editor state for the new name
        editor_state.current_map_filename = new_full_path_py
        editor_state.current_json_filename = new_full_path_json
        editor_state.unsaved_changes = True # Needs re-export to reflect new name in PY

        logger.info(f"Editor state finalized for renamed map. New name: '{editor_state.map_name_for_function}'. PY target: '{new_full_path_py}'.")
        if editor_state.current_editor_mode == "editing_map":
             pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")

        # 5. CRITICAL: Re-export the Python script with the new name and current (loaded) content
        if export_map_to_game_python_script(editor_state):
            logger.info(f"Successfully re-exported '{editor_state.current_map_filename}' with updated internal names and content.")
            editor_state.set_status_message(f"Map '{old_base_filename_no_ext}' renamed to '{new_name_str}' and exported.", 3)
            if editor_state.current_editor_mode == "editing_map":
                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py") # No asterisk
        else:
            logger.error(f"Failed to re-export '{editor_state.current_map_filename}' after rename. PY script may be inconsistent.")
            editor_state.set_status_message(f"Renamed, but PY export failed. Save/Export again.", 4)
            if editor_state.current_editor_mode == "editing_map":
                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")

    except OSError as e_outer:
        editor_state.set_status_message(f"Error during map rename file system op: {e_outer}", 4)
        logger.error(f"OSError during file rename (system level): {e_outer}", exc_info=True)


def _handle_rename_select_map(selected_path_from_dialog: str, editor_state: EditorState):
    logger.info(f"Map selected for rename (path from dialog): '{selected_path_from_dialog}'")
    if not selected_path_from_dialog:
        editor_state.set_status_message("Rename cancelled: No map selected.", 1)
        logger.info("Rename cancelled: no map selected from dialog.")
        return

    filename_with_ext = os.path.basename(selected_path_from_dialog)
    base_name_no_ext = os.path.splitext(filename_with_ext)[0]

    start_text_input_dialog(
        editor_state,
        prompt=f"Enter new name for '{base_name_no_ext}':",
        default_text=base_name_no_ext,
        on_confirm=lambda new_name: _handle_rename_get_new_name(new_name, base_name_no_ext, editor_state),
        on_cancel=lambda: editor_state.set_status_message("Rename cancelled.", 1),
        is_initially_selected=True
    )

def start_rename_map_flow(editor_state: EditorState):
    logger.info("Starting rename map flow.")
    start_file_load_dialog(
        editor_state,
        on_confirm=lambda path_from_dialog: _handle_rename_select_map(path_from_dialog, editor_state),
        on_cancel=lambda: editor_state.set_status_message("Rename map cancelled.", 1),
        prompt_override="Select Map to Rename",
        file_extension=ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION
    )

def handle_menu_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos
        ui_rects = editor_state.ui_elements_rects

        if ui_rects.get("menu_new_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'New Map' button clicked.")
            def on_new_map_name(name_input:str):
                name_clean = name_input.strip().lower().replace(" ", "_").replace("-", "_")
                
                if not name_clean:
                    editor_state.set_status_message("Map name empty after cleaning.",3)
                    start_text_input_dialog(editor_state,"Name (cleaned version was empty):",name_clean,on_new_map_name,lambda:None, is_initially_selected=True)
                    return

                invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                if any(char in name_clean for char in invalid_chars):
                    editor_state.set_status_message("Map name contains invalid characters.", 3)
                    logger.warning(f"Invalid new map name provided: '{name_clean}'")
                    start_text_input_dialog(editor_state, "Invalid Name. New Map Name:", name_clean, on_new_map_name, lambda: None, is_initially_selected=True)
                    return

                potential_json_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, name_clean + ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION)
                potential_py_path = os.path.join(ED_CONFIG.MAPS_DIRECTORY, name_clean + ED_CONFIG.GAME_LEVEL_FILE_EXTENSION)
                if os.path.exists(potential_json_path) or os.path.exists(potential_py_path):
                    editor_state.set_status_message(f"Map '{name_clean}' already exists.", 3)
                    logger.warning(f"Attempt to create new map with existing name: '{name_clean}'")
                    start_text_input_dialog(editor_state, f"Name '{name_clean}' exists. New Map Name:", name_clean, on_new_map_name, lambda:None, is_initially_selected=True)
                    return

                editor_state.map_name_for_function_input = name_clean
                def on_map_size(size_str:str):
                    try:
                        w,h=map(int,size_str.replace(" ","").split(','))
                        max_w = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 500) 
                        max_h = getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 500)
                        if not(w>0 and h>0 and w <= max_w and h <= max_h):
                             raise ValueError(f"Dims must be >0 and <= max ({max_w}x{max_h})")
                        
                        init_new_map_state(editor_state, editor_state.map_name_for_function_input, w, h)
                        
                        if save_map_to_json(editor_state):
                            logger.info(f"New map JSON '{editor_state.map_name_for_function}.json' saved.")
                            if export_map_to_game_python_script(editor_state):
                                editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' created and exported.",3)
                                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
                            else:
                                editor_state.set_status_message(f"Map '{editor_state.map_name_for_function}' JSON saved, PY export failed.",4)
                                pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        else:
                            editor_state.set_status_message(f"Failed to save new map JSON for '{editor_state.map_name_for_function}'.",4)
                            pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py*")
                        
                        editor_state.current_editor_mode="editing_map"
                    except Exception as e:
                        editor_state.set_status_message(f"Invalid size:{e}",3.5)
                        start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None, is_initially_selected=True)
                start_text_input_dialog(editor_state,"Size (W,H):",f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}",on_map_size,lambda:None, is_initially_selected=True)
            start_text_input_dialog(editor_state,"New Map Name:","my_map",on_new_map_name,lambda:None, is_initially_selected=True)

        elif ui_rects.get("menu_load_map",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Load Map' button clicked.")
            def on_file_sel(path_from_dialog:str):
                logger.debug(f"Attempting to load map from: {path_from_dialog}")
                if load_map_from_json(editor_state, path_from_dialog):
                    editor_state.current_editor_mode="editing_map"
                    caption_asterisk = "*" if editor_state.unsaved_changes else ""
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py{caption_asterisk}")
                else:
                    logger.error(f"Failed to load map from {path_from_dialog}")
            start_file_load_dialog(editor_state,on_confirm=on_file_sel,on_cancel=lambda:None)

        elif ui_rects.get("menu_rename_map", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Rename Map' button clicked.")
            start_rename_map_flow(editor_state)

        elif ui_rects.get("menu_delete_map", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Delete Map' button clicked.")
            def on_delete_file_selected(path_from_dialog: str):
                if path_from_dialog:
                    map_name_to_delete = os.path.splitext(os.path.basename(path_from_dialog))[0]
                    logger.info(f"Attempting deletion of map: {map_name_to_delete} (Path: {path_from_dialog})")

                    if delete_map_files(editor_state, path_from_dialog):
                        was_active_or_loaded_map = (editor_state.map_name_for_function == map_name_to_delete) or \
                                                   (editor_state.current_json_filename and \
                                                    os.path.normcase(editor_state.current_json_filename) == os.path.normcase(path_from_dialog))
                        if was_active_or_loaded_map:
                            logger.info(f"Map '{map_name_to_delete}' which might have been active/loaded was deleted. Resetting map context.")
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