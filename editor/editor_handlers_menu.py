# editor/editor_handlers_menu.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events for the main menu of the editor.
"""
import pygame
import os
import logging
from typing import Optional

import editor_config as ED_CONFIG
from editor_state import EditorState
from editor_ui import start_text_input_dialog, start_file_load_dialog # color_picker dialog not used in menu
from editor_map_utils import (init_new_map_state, save_map_to_json,
                              load_map_from_json, export_map_to_game_python_script,
                              delete_map_files)

logger = logging.getLogger(__name__)

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
                editor_state.map_name_for_function_input=name
                def on_map_size(size_str:str):
                    try:
                        w,h=map(int,size_str.replace(" ","").split(','))
                        if not(w>0 and h>0): raise ValueError("Dims>0")
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
            def on_file_sel(fp:str):
                if load_map_from_json(editor_state,fp): 
                    editor_state.current_editor_mode="editing_map"
                    pygame.display.set_caption(f"Editor - {editor_state.map_name_for_function}.py")
            start_file_load_dialog(editor_state,on_confirm=on_file_sel,on_cancel=lambda:None)

        elif ui_rects.get("menu_delete_map", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Delete Map' button clicked.")
            def on_delete_file_selected(filepath_to_delete: str):
                if filepath_to_delete:
                    map_name_to_delete = os.path.basename(filepath_to_delete).replace(ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION, "")
                    logger.info(f"Attempting direct deletion of map: {map_name_to_delete} ({filepath_to_delete})")
                    
                    if delete_map_files(editor_state, filepath_to_delete):
                        editor_state.set_status_message(f"Map '{map_name_to_delete}' deleted.", 3)
                        # If current map was deleted, reset context (but stay in menu)
                        # The map context being reset ensures no lingering data of the deleted map.
                        # If editor was in 'editing_map' mode for the deleted map, it should have been handled
                        # by the callback of the dialog that led to this point.
                        # Here, we are already in 'menu' mode.
                        # Check if the active map data matches the deleted one, if so, clear it.
                        current_map_base_name = ""
                        if editor_state.current_map_filename:
                             current_map_base_name = os.path.basename(editor_state.current_map_filename).replace(ED_CONFIG.GAME_LEVEL_FILE_EXTENSION, "")

                        if editor_state.map_name_for_function == map_name_to_delete or \
                           current_map_base_name == map_name_to_delete:
                            logger.info(f"Map '{map_name_to_delete}' which might have been active was deleted. Resetting map context.")
                            editor_state.reset_map_context() 
                            # No need to change editor_mode here, as we are already in menu.
                else:
                    editor_state.set_status_message("No map selected for deletion.", 2)
            
            start_file_load_dialog(editor_state, 
                                   prompt_override="Select Map to PERMANENTLY DELETE", 
                                   on_confirm=on_delete_file_selected, 
                                   on_cancel=lambda: editor_state.set_status_message("Delete operation cancelled.", 2))

        elif ui_rects.get("menu_quit",pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
            logger.info("Menu: 'Quit' button clicked.")
            pygame.event.post(pygame.event.Event(pygame.QUIT))