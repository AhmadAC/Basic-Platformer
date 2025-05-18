# editor/editor_handlers_dialog.py
# -*- coding: utf-8 -*-
"""
Handles Pygame events for active dialogs in the editor.
Includes key repeat for backspace.
"""
import pygame
import os
import logging
from typing import Optional, Tuple # Keep Tuple, Optional if used for type hints

import editor_config as ED_CONFIG
from editor_state import EditorState

logger = logging.getLogger(__name__)

def _handle_backspace_action(editor_state: EditorState):
    """Performs the backspace action on the dialog input text."""
    if editor_state.dialog_input_text_selected: # If all text is selected
        editor_state.dialog_input_text = ""
        editor_state.dialog_input_text_selected = False # Deselect after clearing
    elif editor_state.dialog_input_text: # If there's text and not all selected, delete last char
        editor_state.dialog_input_text = editor_state.dialog_input_text[:-1]

def handle_dialog_key_repeat(editor_state: EditorState):
    """
    Handles key repeat logic for dialogs (specifically BACKSPACE).
    This function should be called once per game loop tick when a dialog is active.
    """
    # Only process if a text input dialog is active and BACKSPACE was the key held down
    if editor_state.active_dialog_type == "text_input" and \
       editor_state.key_held_down == pygame.K_BACKSPACE:

        keys_currently_pressed = pygame.key.get_pressed() # Get current hardware state of keys

        if keys_currently_pressed[pygame.K_BACKSPACE]: # Check if BACKSPACE is *still* physically held
            current_time_ticks = pygame.time.get_ticks() # Current time in milliseconds
            
            # Time elapsed since the key was first pressed OR since the last repeat action
            time_since_last_action_or_press = current_time_ticks - editor_state.key_held_down_timer_start

            # Determine if this is the first repeat (after initial delay) or a subsequent repeat
            # editor_state.key_repeat_action_performed_this_frame is a bit of a misnomer here;
            # it's more like "has_an_action_been_taken_since_initial_press_or_last_repeat".
            # The `KEYDOWN` event handles the very first action.
            # This `handle_dialog_key_repeat` handles actions *after* the initial press.

            # If `key_repeat_action_performed_this_frame` is True, it means the KEYDOWN event already
            # processed the first backspace. We now wait for `key_repeat_delay_ms`.
            # If it's False, it means we are checking for a *subsequent* repeat action after the delay.

            # Logic:
            # 1. If initial KEYDOWN just happened, `key_repeat_action_performed_this_frame` is True.
            #    We wait for `key_repeat_delay_ms`.
            # 2. Once `key_repeat_delay_ms` passes, we perform the action, set `key_repeat_action_performed_this_frame` to False (or rather, reset the timer for *interval*),
            #    and subsequent checks will use `key_repeat_interval_ms`.

            # Simpler logic:
            # The KEYDOWN event handles the first immediate action.
            # This function handles the *repeats*.
            # The `key_held_down_timer_start` is set on KEYDOWN.
            # The first repeat happens after `key_repeat_delay_ms`.
            # Subsequent repeats happen after `key_repeat_interval_ms`.

            # Let's refine `key_repeat_action_performed_this_frame` to mean "was a repeat action done by *this function* in the current frame/logic cycle?"
            # This helps avoid multiple repeats if this function were somehow called multiple times too quickly (unlikely with pygame.time.get_ticks()).

            # We need a flag to distinguish between "waiting for initial delay" and "waiting for interval"
            if not hasattr(editor_state, '_key_repeat_initial_delay_passed'):
                 editor_state._key_repeat_initial_delay_passed = False

            if not editor_state._key_repeat_initial_delay_passed:
                if time_since_last_action_or_press >= editor_state.key_repeat_delay_ms:
                    _handle_backspace_action(editor_state)
                    editor_state.key_held_down_timer_start = current_time_ticks # Reset timer for next *interval*
                    editor_state._key_repeat_initial_delay_passed = True # Initial delay has passed
            else: # Initial delay has passed, now use interval
                if time_since_last_action_or_press >= editor_state.key_repeat_interval_ms:
                    _handle_backspace_action(editor_state)
                    editor_state.key_held_down_timer_start = current_time_ticks # Reset timer for next interval
        
        else: # BACKSPACE key is no longer physically held
            editor_state.key_held_down = None # Stop tracking
            editor_state._key_repeat_initial_delay_passed = False # Reset for next key press sequence
    
    elif editor_state.key_held_down and editor_state.key_held_down != pygame.K_BACKSPACE:
        # If a different key was being tracked (e.g., for a different dialog type)
        editor_state.key_held_down = None
        editor_state._key_repeat_initial_delay_passed = False


def handle_dialog_events(event: pygame.event.Event, editor_state: EditorState):
    """
    Processes Pygame events when a dialog is active.
    Modifies editor_state based on interactions.
    Handles initial key presses; `handle_dialog_key_repeat` handles continuous presses.
    """
    if not editor_state.active_dialog_type:
        return

    confirmed, cancelled, selected_value = False, False, None
    dialog_type = editor_state.active_dialog_type

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            cancelled = True
            editor_state.dialog_input_text_selected = False # Deselect text on cancel
            editor_state.key_held_down = None # Stop any key repeat
            editor_state._key_repeat_initial_delay_passed = False
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER: # Confirm dialog
            if dialog_type == "text_input":
                confirmed = True
                selected_value = editor_state.dialog_input_text
                editor_state.dialog_input_text_selected = False
            elif dialog_type == "file_load": # Confirm file selection
                if editor_state.dialog_selected_file_index != -1 and \
                   0 <= editor_state.dialog_selected_file_index < len(editor_state.dialog_file_list):
                    # Construct full path using the actual filename from dialog_file_list
                    confirmed = True
                    selected_value = os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
                else: # No file selected to confirm
                    editor_state.set_status_message("No file selected to confirm.", 2.5)
            editor_state.key_held_down = None # Stop key repeat on confirm
            editor_state._key_repeat_initial_delay_passed = False
        
        # Handle text input for "text_input" dialog
        if dialog_type == "text_input":
            if event.key == pygame.K_BACKSPACE:
                _handle_backspace_action(editor_state) # Perform first backspace action
                editor_state.key_held_down = pygame.K_BACKSPACE # Mark backspace as held
                editor_state.key_held_down_timer_start = pygame.time.get_ticks() # Start timer for repeats
                editor_state._key_repeat_initial_delay_passed = False # Mark that initial delay needs to pass
            elif event.unicode.isprintable() and \
                 (event.unicode.isalnum() or event.unicode in ['.', '_', '-', ' ', ',', '/', '\\']): # Allow specific symbols
                if editor_state.dialog_input_text_selected: # If text was selected, replace it
                    editor_state.dialog_input_text = event.unicode
                    editor_state.dialog_input_text_selected = False # Typing deselects
                else: # Append new character
                    editor_state.dialog_input_text += event.unicode
                editor_state.key_held_down = None # Pressing other keys stops backspace repeat
                editor_state._key_repeat_initial_delay_passed = False
        
        # Handle UP/DOWN arrow navigation in "file_load" dialog
        elif dialog_type == "file_load" and editor_state.dialog_file_list: # Ensure list is not empty
            num_files = len(editor_state.dialog_file_list)
            if num_files > 0:
                if event.key == pygame.K_UP:
                    editor_state.dialog_selected_file_index = (editor_state.dialog_selected_file_index - 1 + num_files) % num_files
                elif event.key == pygame.K_DOWN:
                    editor_state.dialog_selected_file_index = (editor_state.dialog_selected_file_index + 1) % num_files
            else: # No files to navigate
                editor_state.dialog_selected_file_index = -1
            
            # Update input text preview if a file is selected (though not directly editable here)
            if editor_state.dialog_selected_file_index != -1:
                editor_state.dialog_input_text = editor_state.dialog_file_list[editor_state.dialog_selected_file_index]
            else:
                editor_state.dialog_input_text = ""
            editor_state.key_held_down = None # Stop key repeat if navigating file list
            editor_state._key_repeat_initial_delay_passed = False

    elif event.type == pygame.KEYUP: # Handle key release
        if dialog_type == "text_input" and event.key == pygame.K_BACKSPACE and \
           editor_state.key_held_down == pygame.K_BACKSPACE:
            editor_state.key_held_down = None # Stop tracking backspace for repeat
            editor_state._key_repeat_initial_delay_passed = False # Reset for next press

    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # Left mouse button down
        editor_state.key_held_down = None # Clicking stops any key repeat
        editor_state._key_repeat_initial_delay_passed = False

        if editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos): # Click inside dialog
            if dialog_type == "color_picker":
                for name, rect_relative_to_dialog in editor_state.color_picker_rects.items():
                    # Convert relative rect to absolute screen rect for collision check
                    absolute_swatch_rect = rect_relative_to_dialog.move(editor_state.dialog_rect.left, editor_state.dialog_rect.top)
                    if absolute_swatch_rect.collidepoint(event.pos):
                        selected_value = ED_CONFIG.COLOR_PICKER_PRESETS.get(name)
                        confirmed = bool(selected_value) # Confirm if a valid color was clicked
                        break
            elif dialog_type == "file_load":
                ok_rect = editor_state.ui_elements_rects.get("dialog_file_load_ok")
                cancel_rect = editor_state.ui_elements_rects.get("dialog_file_load_cancel")
                if ok_rect and ok_rect.collidepoint(event.pos) and editor_state.dialog_selected_file_index != -1:
                    confirmed = True
                    selected_value = os.path.join(ED_CONFIG.MAPS_DIRECTORY, editor_state.dialog_file_list[editor_state.dialog_selected_file_index])
                elif cancel_rect and cancel_rect.collidepoint(event.pos):
                    cancelled = True
                else: # Check for clicks on file list items or scrollbar
                    for item_info in editor_state.ui_elements_rects.get('dialog_file_item_rects', []): 
                        if item_info["rect"].collidepoint(event.pos): # Rects are absolute screen coords
                            editor_state.dialog_selected_file_index = item_info["index"]
                            # Update preview text (though not directly editable)
                            editor_state.dialog_input_text = editor_state.dialog_file_list[item_info["index"]]
                            break
                    scrollbar_handle_rect = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
                    if scrollbar_handle_rect and scrollbar_handle_rect.collidepoint(event.pos):
                        editor_state.is_dragging_scrollbar = True
                        # Calculate offset from mouse click to top of scrollbar handle
                        editor_state.scrollbar_drag_mouse_offset_y = event.pos[1] - scrollbar_handle_rect.top
            
            elif dialog_type == "text_input": 
                input_box = editor_state.ui_elements_rects.get('dialog_text_input_box')
                # If clicked outside the input box but still inside the dialog, deselect text.
                # If clicked inside, the behavior is often to place cursor, not select all.
                # For simplicity, let's say clicking inside also deselects for now.
                if input_box and input_box.collidepoint(event.pos):
                    editor_state.dialog_input_text_selected = False # Clicking in box focuses for typing
                elif input_box and not input_box.collidepoint(event.pos): # Clicked outside input box, inside dialog
                    editor_state.dialog_input_text_selected = False # Lose focus / selection
        
        elif dialog_type != "text_input": # Clicked outside dialog (for non-text_input types)
            # If click is outside dialog for color picker or file load, cancel it.
            if not (editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos)):
                 cancelled = True 
        elif dialog_type == "text_input": # Clicked outside text_input dialog
             if not (editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(event.pos)):
                editor_state.dialog_input_text_selected = False # Lose focus/selection
                cancelled = True # Cancel if clicked outside dialog entirely


    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1: # Left mouse button up
        editor_state.is_dragging_scrollbar = False # Stop scrollbar drag
        # editor_state.key_held_down = None # Redundant if MOUSEBUTTONDOWN handles it, but safe

    elif event.type == pygame.MOUSEMOTION and editor_state.is_dragging_scrollbar: # Mouse moved while dragging scrollbar
        scrollbar_area_rect = editor_state.ui_elements_rects.get('file_dialog_scrollbar_area')
        scrollbar_handle_rect = editor_state.ui_elements_rects.get('file_dialog_scrollbar_handle')
        if scrollbar_area_rect and scrollbar_handle_rect and editor_state.dialog_file_list:
            # Calculate new handle Y position based on mouse, clamped to scrollbar track
            mouse_y_relative_to_track_top = event.pos[1] - scrollbar_area_rect.top
            new_handle_top_y_in_track = mouse_y_relative_to_track_top - editor_state.scrollbar_drag_mouse_offset_y
            
            # Font and item height needed to calculate scroll range
            font_small_for_scroll = ED_CONFIG.FONT_CONFIG.get("small")
            item_height_for_scroll = (font_small_for_scroll.get_height() + 6) if font_small_for_scroll else 22
            
            total_content_height = len(editor_state.dialog_file_list) * item_height_for_scroll
            visible_list_height = scrollbar_area_rect.height # Height of the visible part of the list
            
            scrollable_track_height = max(1, visible_list_height - scrollbar_handle_rect.height) # Actual draggable range for handle top
            total_scrollable_pixels_content = max(0, total_content_height - visible_list_height) # How much content is hidden
            
            if scrollable_track_height > 0 and total_scrollable_pixels_content > 0:
                clamped_handle_top_y = max(0, min(new_handle_top_y_in_track, scrollable_track_height))
                scroll_ratio = clamped_handle_top_y / scrollable_track_height
                editor_state.dialog_file_scroll_y = scroll_ratio * total_scrollable_pixels_content

    elif event.type == pygame.MOUSEWHEEL and dialog_type == "file_load": # Mouse wheel scroll for file list
        # Ensure mouse is over the dialog to scroll its list
        if editor_state.dialog_rect and editor_state.dialog_rect.collidepoint(pygame.mouse.get_pos()):
            font_small_for_wheel = ED_CONFIG.FONT_CONFIG.get("small")
            item_height_for_wheel = (font_small_for_wheel.get_height() + 6) if font_small_for_wheel else 22
            
            scroll_amount_per_wheel_tick = event.y * item_height_for_wheel # event.y is usually +/- 1
            
            total_content_height_wheel = len(editor_state.dialog_file_list) * item_height_for_wheel
            
            # Calculate visible height of the list area
            prompt_font_for_calc = ED_CONFIG.FONT_CONFIG.get("medium")
            title_h_for_calc = (prompt_font_for_calc.get_height() + 25) if prompt_font_for_calc else 55
            buttons_h_for_calc = ED_CONFIG.BUTTON_HEIGHT_STANDARD // 2 + 20
            visible_list_height_wheel = editor_state.dialog_rect.height - title_h_for_calc - buttons_h_for_calc - 10 # -10 for padding

            max_scroll_y_wheel = max(0, total_content_height_wheel - visible_list_height_wheel)
            
            editor_state.dialog_file_scroll_y -= scroll_amount_per_wheel_tick # Adjust scroll position
            # Clamp scroll_y within valid range [0, max_scroll_y]
            editor_state.dialog_file_scroll_y = max(0, min(editor_state.dialog_file_scroll_y, max_scroll_y_wheel))

    # --- Dialog Confirmation/Cancellation (handles closing the dialog) ---
    if confirmed or cancelled:
        logger.debug(f"Dialog '{dialog_type}' outcome: {'CONFIRMED' if confirmed else 'CANCELLED'}")
        editor_state.key_held_down = None # Ensure key repeat stops when dialog closes
        editor_state._key_repeat_initial_delay_passed = False

        callback_to_confirm = editor_state.dialog_callback_confirm
        callback_to_cancel = editor_state.dialog_callback_cancel
        
        # Crucially, set active_dialog_type to None *before* calling callbacks.
        # This allows callbacks to potentially open new dialogs without interference.
        editor_state.active_dialog_type = None 
        
        if confirmed and callback_to_confirm:
            value_to_pass_to_callback = selected_value
            logger.debug(f"Calling confirm_callback for '{dialog_type}' with value: '{value_to_pass_to_callback}'")
            try:
                callback_to_confirm(value_to_pass_to_callback) # type: ignore
            except Exception as e_cb_confirm:
                logger.error(f"Error in dialog confirm_callback for {dialog_type}: {e_cb_confirm}", exc_info=True)
        elif cancelled and callback_to_cancel:
            logger.debug(f"Calling cancel_callback for '{dialog_type}'.")
            try:
                callback_to_cancel()
            except Exception as e_cb_cancel:
                logger.error(f"Error in dialog cancel_callback for {dialog_type}: {e_cb_cancel}", exc_info=True)
        
        # active_dialog_type is already None here due to the assignment above.
        # The setter for active_dialog_type handles resetting general dialog properties.
        if editor_state.active_dialog_type is None: 
            logger.debug("Dialog closed. General dialog state should have been reset by active_dialog_type setter.")
            # Specific additional cleanup if needed beyond what the setter does
            editor_state.dialog_input_text = "" # Ensure text is cleared
            editor_state.dialog_selected_file_index = -1
            editor_state.is_dragging_scrollbar = False