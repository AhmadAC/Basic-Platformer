# editor/editor_handlers_global.py
# -*- coding: utf-8 -*-
"""
Handles global Pygame events for the editor (QUIT, RESIZE).
"""
import pygame
import logging
from editor_state import EditorState # Assuming EditorState is in the same directory or sys.path is set

logger = logging.getLogger(__name__)

def handle_global_events(event: pygame.event.Event, editor_state: EditorState, main_screen: pygame.Surface) -> bool:
    """
    Handles global events like QUIT and VIDEORESIZE.
    Returns False if a QUIT event is fully processed (application should exit), True otherwise.
    """
    if event.type == pygame.QUIT:
        logger.info("pygame.QUIT event received.")
        if editor_state.unsaved_changes:
            if not getattr(editor_state, '_quit_attempted_with_unsaved_changes', False):
                editor_state.set_status_message("Unsaved changes! Quit again to exit without saving, or save your map.", 5.0)
                setattr(editor_state, '_quit_attempted_with_unsaved_changes', True)
                return True  # Continue running, first quit attempt
            else:
                logger.info("Second quit attempt with unsaved changes. Proceeding to quit.")
                if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                    delattr(editor_state, '_quit_attempted_with_unsaved_changes')
                return False # Signal to quit
        else:
            if hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
                delattr(editor_state, '_quit_attempted_with_unsaved_changes')
            return False # Signal to quit

    if event.type == pygame.VIDEORESIZE:
        logger.info(f"pygame.VIDEORESIZE to {event.w}x{event.h}")
        # The main loop in editor.py will handle screen resizing and layout recalculation.
        # This function just acknowledges the event for logging or specific state changes if needed.
        editor_state.set_status_message(f"Resized to {event.w}x{event.h}", 2.0)
        editor_state.minimap_needs_regeneration = True # Flag for minimap to redraw
    
    # If any other event type clears the quit attempt flag
    if event.type != pygame.QUIT and hasattr(editor_state, '_quit_attempted_with_unsaved_changes'):
        delattr(editor_state, '_quit_attempted_with_unsaved_changes')
        logger.debug("Quit attempt flag cleared due to other event.")

    return True # Continue running