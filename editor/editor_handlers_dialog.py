# editor/editor_handlers_dialog.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events for active dialogs in the editor.
"""
import pygame
import os
import logging
from typing import Optional, Tuple

import editor_config as ED_CONFIG 
from editor_state import EditorState

logger = logging.getLogger(__name__)

def handle_dialog_events(event: pygame.event.Event, editor_state: EditorState):
    """
    Processes events when a dialog is active.
    Modifies editor_state based on interactions.
    """
    if not editor_state.active_dialog_type: 
        return

    confirmed, cancelled, selected_value = False, False, None
    dialog_type = editor_state.active_dialog_type

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE: 
            cancelled = True
            editor_state.dialog_input_text_selected = False 
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            if dialog_type=="text_input": 
                confirmed=True
                selected_value=editor_state.dialog_input_text
                editor_state.dialog_input_text_selected = False 
            elif dialog_type=="file_load" and editor_state.dialog_selected_file_index != -1 and \
                 0 <= editor_state.dialog_selected_file_index < len(editor_state.dialog_file_list):
                confirmed=True; selected_value=os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
            elif dialog_type=="file_load": editor_state.set_status_message("No file selected.", 2.5)
        
        if dialog_type=="text_input":
            if event.key==pygame.K_BACKSPACE: 
                if editor_state.dialog_input_text_selected:
                    editor_state.dialog_input_text = ""
                    editor_state.dialog_input_text_selected = False
                else:
                    editor_state.dialog_input_text=editor_state.dialog_input_text[:-1]
            elif event.unicode.isprintable()and(event.unicode.isalnum()or event.unicode in ['.','_','-',' ',',','/','\\']): 
                if editor_state.dialog_input_text_selected:
                    editor_state.dialog_input_text = event.unicode
                    editor_state.dialog_input_text_selected = False
                else:
                    editor_state.dialog_input_text+=event.unicode
        elif dialog_type=="file_load" and editor_state.dialog_file_list:
            ll=len(editor_state.dialog_file_list)
            if ll>0:
                if event.key==pygame.K_UP: editor_state.dialog_selected_file_index=(editor_state.dialog_selected_file_index-1+ll)%ll
                elif event.key==pygame.K_DOWN: editor_state.dialog_selected_file_index=(editor_state.dialog_selected_file_index+1)%ll
            else: editor_state.dialog_selected_file_index=-1
            if editor_state.dialog_selected_file_index != -1:
                editor_state.dialog_input_text = editor_state.dialog_file_list[editor_state.dialog_selected_file_index]
            else:
                editor_state.dialog_input_text = ""
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos):
            if dialog_type=="color_picker":
                for name,rect in editor_state.color_picker_rects.items():
                    abs_rect=rect.move(editor_state.dialog_rect.left,editor_state.dialog_rect.top)
                    if abs_rect.collidepoint(event.pos): selected_value=ED_CONFIG.COLOR_PICKER_PRESETS.get(name); confirmed=bool(selected_value); break
            elif dialog_type=="file_load":
                ok_rect = editor_state.ui_elements_rects.get("dialog_file_load_ok")
                cancel_rect = editor_state.ui_elements_rects.get("dialog_file_load_cancel")
                if ok_rect and ok_rect.collidepoint(event.pos) and editor_state.dialog_selected_file_index != -1:
                    confirmed=True; selected_value=os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
                elif cancel_rect and cancel_rect.collidepoint(event.pos): cancelled=True
                else:
                    for item_info in editor_state.ui_elements_rects.get('dialog_file_item_rects', []): 
                        if item_info["rect"].collidepoint(event.pos):
                            editor_state.dialog_selected_file_index=item_info["index"]
                            editor_state.dialog_input_text=item_info["text"]; break
                    scrollbar_handle_rect = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
                    if scrollbar_handle_rect and scrollbar_handle_rect.collidepoint(event.pos):
                        editor_state.is_dragging_scrollbar=True
                        editor_state.scrollbar_drag_mouse_offset_y=event.pos[1]-scrollbar_handle_rect.top
            elif dialog_type == "text_input": 
                input_box = editor_state.ui_elements_rects.get('dialog_text_input_box')
                if input_box and not input_box.collidepoint(event.pos): 
                    editor_state.dialog_input_text_selected = False
                elif input_box and input_box.collidepoint(event.pos): 
                    editor_state.dialog_input_text_selected = False 
        elif dialog_type!="text_input": 
            if not (editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos)):
                 cancelled = True 
        elif dialog_type == "text_input": 
             if not (editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos)):
                editor_state.dialog_input_text_selected = False
                cancelled = True


    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1: editor_state.is_dragging_scrollbar=False
    elif event.type == pygame.MOUSEMOTION and editor_state.is_dragging_scrollbar:
        area,handle=editor_state.ui_elements_rects.get('file_dialog_scrollbar_area'), editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
        if area and handle and editor_state.dialog_file_list:
            my_area=event.pos[1]-area.top; h_pos_y=my_area-editor_state.scrollbar_drag_mouse_offset_y
            font=ED_CONFIG.FONT_CONFIG.get("small"); item_h=(font.get_height()+6)if font else 22 
            content_h=len(editor_state.dialog_file_list)*item_h; display_h=area.height 
            track_h=max(1,display_h-handle.height); scroll_px=max(0,content_h-display_h) 
            if track_h>0 and scroll_px>0: clamped_y=max(0,min(h_pos_y,track_h)); ratio=clamped_y/track_h; editor_state.dialog_file_scroll_y=ratio*scroll_px
    elif event.type == pygame.MOUSEWHEEL and dialog_type=="file_load" and editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(pygame.mouse.get_pos()):
        font_s=ED_CONFIG.FONT_CONFIG.get("small");item_h=(font_s.get_height()+6)if font_s else 22 
        scroll_v=event.y*item_h;content_h=len(editor_state.dialog_file_list)*item_h 
        font_m=ED_CONFIG.FONT_CONFIG.get("medium");prompt_h=(font_m.get_height()+25)if font_m else 55 
        btns_h=40;display_h=editor_state.dialog_rect.height-prompt_h-btns_h-10
        max_s=max(0,content_h-display_h);editor_state.dialog_file_scroll_y-=scroll_v;editor_state.dialog_file_scroll_y=max(0,min(editor_state.dialog_file_scroll_y,max_s))

    if confirmed or cancelled:
        logger.debug(f"Dialog '{dialog_type}' outcome: {'CONFIRMED' if confirmed else 'CANCELLED'}")
        cb_confirm, cb_cancel = editor_state.dialog_callback_confirm, editor_state.dialog_callback_cancel
        editor_state.active_dialog_type = None # This also sets dialog_input_text_selected to False
        if confirmed and cb_confirm:
            val_pass = selected_value
            logger.debug(f"Calling confirm_callback for '{dialog_type}' with value: '{val_pass}'")
            try: cb_confirm(val_pass) # type: ignore
            except Exception as e:logger.error(f"Err Confirm CB for {dialog_type}:{e}", exc_info=True)
        elif cancelled and cb_cancel:
            logger.debug(f"Calling cancel_callback for '{dialog_type}'.")
            try: cb_cancel()
            except Exception as e:logger.error(f"Err Cancel CB for {dialog_type}:{e}", exc_info=True)
        
        if editor_state.active_dialog_type is None: # Should always be true after setting above
            logger.debug("No new dialog active. Cleaning up dialog state.")
            editor_state.dialog_callback_confirm, editor_state.dialog_callback_cancel = None,None
            editor_state.dialog_input_text, editor_state.dialog_selected_file_index = "",-1
            editor_state.is_dragging_scrollbar = False