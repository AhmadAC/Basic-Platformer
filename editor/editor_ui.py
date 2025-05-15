# editor_ui.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.8 (Added text highlight and delete map dialog support)
Pygame-based UI functions for the Level Editor.
Includes buttons, input dialogs, color pickers, and tooltips.
"""
import pygame
import os
from typing import Optional, Dict, Tuple, Any, Callable, List
import traceback 

import editor_config as ED_CONFIG
from editor_state import EditorState


def draw_button(surface: pygame.Surface,
                rect: pygame.Rect,
                text: str,
                font: Optional[pygame.font.Font],
                mouse_pos: Tuple[int, int],
                text_color: Tuple[int, int, int] = ED_CONFIG.BUTTON_TEXT_COLOR,
                button_color_normal: Tuple[int, int, int] = ED_CONFIG.BUTTON_COLOR_NORMAL,
                button_color_hover: Tuple[int, int, int] = ED_CONFIG.BUTTON_COLOR_HOVER,
                border_color: Tuple[int, int, int] = ED_CONFIG.BUTTON_COLOR_BORDER,
                border_width: int = ED_CONFIG.BUTTON_BORDER_WIDTH,
                is_active: bool = True) -> bool:
    is_hovered = False
    if is_active and rect.collidepoint(mouse_pos):
        is_hovered = True

    current_button_color = button_color_normal
    current_text_color = text_color

    if not is_active:
        current_button_color = tuple(int(c * 0.67) for c in button_color_normal) 
        current_text_color = tuple(int(c * 0.67) for c in text_color)
    elif is_hovered:
        current_button_color = button_color_hover

    try:
        pygame.draw.rect(surface, current_button_color, rect)
        if border_width > 0:
            pygame.draw.rect(surface, border_color, rect, border_width)

        if font:
            text_surf = font.render(text, True, current_text_color)
            text_rect = text_surf.get_rect(center=rect.center)
            surface.blit(text_surf, text_rect)
        else:
            print(f"Warning UI_DRAW: draw_button called with no font for text '{text}'")
    except Exception as e:
        print(f"ERROR UI_DRAW: Exception in draw_button for '{text}': {e}")
        traceback.print_exc()

    return is_hovered

def draw_tooltip(surface: pygame.Surface,
                 editor_state: EditorState,
                 font: Optional[pygame.font.Font]):
    if editor_state.hovered_tooltip_text and editor_state.hovered_tooltip_pos and font:
        try:
            text_surf = font.render(editor_state.hovered_tooltip_text, True, ED_CONFIG.TOOLTIP_TEXT_COLOR)
            text_rect = text_surf.get_rect(
                topleft=(editor_state.hovered_tooltip_pos[0] + 15,
                         editor_state.hovered_tooltip_pos[1] + 15)
            )
            bg_rect = text_rect.inflate(ED_CONFIG.TOOLTIP_PADDING * 2, ED_CONFIG.TOOLTIP_PADDING * 2)

            bg_rect.clamp_ip(surface.get_rect()) 
            text_rect.clamp_ip(bg_rect.inflate(-ED_CONFIG.TOOLTIP_PADDING, -ED_CONFIG.TOOLTIP_PADDING)) 

            pygame.draw.rect(surface, ED_CONFIG.TOOLTIP_BG_COLOR, bg_rect, border_radius=3)
            pygame.draw.rect(surface, ED_CONFIG.BUTTON_COLOR_BORDER, bg_rect, 1, border_radius=3)
            surface.blit(text_surf, text_rect)
        except Exception as e:
            print(f"ERROR UI_DRAW: Exception in draw_tooltip for '{editor_state.hovered_tooltip_text}': {e}")
            traceback.print_exc()

def draw_status_message(surface: pygame.Surface, editor_state: EditorState, font: Optional[pygame.font.Font]):
    if editor_state.status_message and font:
        try:
            message_surf = font.render(editor_state.status_message, True, getattr(ED_CONFIG.C, 'YELLOW', (255,255,0))) 
            message_rect = message_surf.get_rect(centerx=surface.get_width() // 2,
                                                  bottom=surface.get_height() - 10)
            bg_padding = 5
            bg_rect = message_rect.inflate(bg_padding * 2, bg_padding * 2)
            bg_rect.clamp_ip(surface.get_rect())
            message_rect.clamp_ip(bg_rect)

            s = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            s.fill((50, 50, 50, 180)) 
            surface.blit(s, bg_rect.topleft)
            surface.blit(message_surf, message_rect)
        except Exception as e:
            print(f"ERROR UI_DRAW: Exception in draw_status_message for '{editor_state.status_message}': {e}")
            traceback.print_exc()


def start_text_input_dialog(editor_state: EditorState,
                            prompt: str,
                            default_text: str = "",
                            on_confirm: Optional[Callable[[str], None]] = None,
                            on_cancel: Optional[Callable[[], None]] = None,
                            is_initially_selected: bool = True): # New parameter
    print(f"DEBUG UI_DIALOG: start_text_input_dialog. Prompt: '{prompt}', Default: '{default_text}', Selected: {is_initially_selected}")
    editor_state.active_dialog_type = "text_input"
    editor_state.dialog_prompt_message = prompt
    editor_state.dialog_input_text = default_text
    editor_state.dialog_input_default = default_text 
    editor_state.dialog_input_text_selected = is_initially_selected # Set the flag
    editor_state.dialog_callback_confirm = on_confirm
    editor_state.dialog_callback_cancel = on_cancel
    editor_state.dialog_rect = None 

def start_color_picker_dialog(editor_state: EditorState,
                              on_confirm: Optional[Callable[[Tuple[int,int,int]], None]] = None,
                              on_cancel: Optional[Callable[[], None]] = None):
    print(f"DEBUG UI_DIALOG: start_color_picker_dialog.") 
    editor_state.active_dialog_type = "color_picker"
    editor_state.dialog_prompt_message = "Select Background Color (Esc to Cancel)" # Or make generic
    editor_state.color_picker_rects.clear()

    cols = ED_CONFIG.COLOR_PICKER_COLS
    button_size = ED_CONFIG.COLOR_PICKER_BUTTON_SIZE
    padding = ED_CONFIG.COLOR_PICKER_PADDING

    start_x_in_dialog = padding * 2
    current_y_in_dialog = 50 
    current_x_in_dialog = start_x_in_dialog
    idx = 0
    for name in ED_CONFIG.COLOR_PICKER_PRESETS.keys():
        rect = pygame.Rect(current_x_in_dialog, current_y_in_dialog, button_size, button_size)
        editor_state.color_picker_rects[name] = rect
        current_x_in_dialog += button_size + padding
        idx += 1
        if idx % cols == 0:
            current_x_in_dialog = start_x_in_dialog
            current_y_in_dialog += button_size + padding

    editor_state.dialog_callback_confirm = on_confirm
    editor_state.dialog_callback_cancel = on_cancel
    editor_state.dialog_rect = None 

def start_file_load_dialog(editor_state: EditorState,
                           on_confirm: Optional[Callable[[str], None]] = None,
                           on_cancel: Optional[Callable[[], None]] = None,
                           initial_path: str = ED_CONFIG.MAPS_DIRECTORY,
                           file_extension: str = ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION,
                           prompt_override: Optional[str] = None): # New parameter
    print(f"DEBUG UI_DIALOG: start_file_load_dialog. Path: '{initial_path}', Ext: '{file_extension}', Prompt: '{prompt_override}'")
    editor_state.active_dialog_type = "file_load"
    if prompt_override:
        editor_state.dialog_prompt_message = prompt_override
    else:
        editor_state.dialog_prompt_message = f"Select Map to Load (from ./{initial_path})"
    editor_state.dialog_input_text = ""
    editor_state.dialog_file_list = []
    editor_state.dialog_file_scroll_y = 0
    editor_state.dialog_selected_file_index = -1
    editor_state.dialog_rect = None

    if 'dialog_file_item_rects' not in editor_state.ui_elements_rects:
        editor_state.ui_elements_rects['dialog_file_item_rects'] = []
    else:
        editor_state.ui_elements_rects['dialog_file_item_rects'].clear()

    if not os.path.exists(initial_path):
        try:
            os.makedirs(initial_path)
            editor_state.set_status_message(f"Created maps dir '{initial_path}'. No files yet.", 2)
        except OSError as e:
            err_msg = f"Error creating dir '{initial_path}': {e}"
            editor_state.set_status_message(err_msg, 3)
            print(f"ERROR UI_DIALOG: {err_msg}")
            if on_cancel: on_cancel()
            editor_state.active_dialog_type = None
            return

    try:
        for item in os.listdir(initial_path):
            if item.endswith(file_extension) and os.path.isfile(os.path.join(initial_path, item)):
                editor_state.dialog_file_list.append(item)
        editor_state.dialog_file_list.sort()
    except OSError as e:
        err_msg = f"Error listing files in '{initial_path}': {e}"
        editor_state.set_status_message(err_msg, 3)
        print(f"ERROR UI_DIALOG: {err_msg}")
        if on_cancel: on_cancel()
        editor_state.active_dialog_type = None
        return

    if not editor_state.dialog_file_list:
        editor_state.set_status_message(f"No '{file_extension}' files found in ./{initial_path}", 2.5)

    editor_state.dialog_callback_confirm = on_confirm
    editor_state.dialog_callback_cancel = on_cancel


def draw_active_dialog(surface: pygame.Surface, editor_state: EditorState, fonts: Dict[str, Optional[pygame.font.Font]]):
    if not editor_state.active_dialog_type:
        return

    try:
        screen_center_x, screen_center_y = surface.get_rect().center
        dialog_width, dialog_height = 450, 350

        if editor_state.active_dialog_type == "text_input":
            dialog_width, dialog_height = 400, 200
        elif editor_state.active_dialog_type == "color_picker":
            num_colors = len(ED_CONFIG.COLOR_PICKER_PRESETS)
            cols = ED_CONFIG.COLOR_PICKER_COLS
            rows = (num_colors + cols - 1) // cols
            content_w = cols * ED_CONFIG.COLOR_PICKER_BUTTON_SIZE + (cols -1 if cols > 0 else 0) * ED_CONFIG.COLOR_PICKER_PADDING
            content_h = rows * ED_CONFIG.COLOR_PICKER_BUTTON_SIZE + (rows -1 if rows > 0 else 0) * ED_CONFIG.COLOR_PICKER_PADDING
            dialog_width = max(300, content_w + ED_CONFIG.COLOR_PICKER_PADDING * 4)
            title_space = 60
            dialog_height = max(200, content_h + title_space + ED_CONFIG.COLOR_PICKER_PADDING * 2)
        elif editor_state.active_dialog_type == "file_load":
            dialog_width, dialog_height = 400, 350

        current_dialog_rect = pygame.Rect(0, 0, dialog_width, dialog_height)
        current_dialog_rect.center = screen_center_x, screen_center_y
        editor_state.dialog_rect = current_dialog_rect

        pygame.draw.rect(surface, ED_CONFIG.DIALOG_BG_COLOR, current_dialog_rect, border_radius=5)
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), current_dialog_rect, 2, border_radius=5) 

        prompt_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
        if prompt_font and editor_state.dialog_prompt_message:
            prompt_surf = prompt_font.render(editor_state.dialog_prompt_message, True, ED_CONFIG.DIALOG_PROMPT_COLOR)
            prompt_draw_rect = prompt_surf.get_rect(midtop=(current_dialog_rect.centerx, current_dialog_rect.top + 15))
            surface.blit(prompt_surf, prompt_draw_rect)

        if editor_state.active_dialog_type == "text_input":
            _draw_text_input_content(surface, editor_state, current_dialog_rect, fonts)
        elif editor_state.active_dialog_type == "color_picker":
            _draw_color_picker_content(surface, editor_state, current_dialog_rect, fonts)
        elif editor_state.active_dialog_type == "file_load":
            _draw_file_load_content(surface, editor_state, current_dialog_rect, fonts)

    except Exception as e:
        print(f"ERROR UI_DRAW_DIALOG: Exception in draw_active_dialog for type '{editor_state.active_dialog_type}': {e}")
        traceback.print_exc()
        error_font = fonts.get("small")
        if error_font and editor_state.dialog_rect:
            err_surf = error_font.render(f"Dialog Error! See console.", True, getattr(ED_CONFIG.C, 'RED', (255,0,0))) 
            surface.blit(err_surf, err_surf.get_rect(center=editor_state.dialog_rect.center))


def _draw_text_input_content(surface: pygame.Surface, editor_state: EditorState, dialog_rect: pygame.Rect, fonts: Dict[str, Optional[pygame.font.Font]]):
    input_box_rect = pygame.Rect(0, 0, dialog_rect.width - 40, 40)
    input_box_rect.center = dialog_rect.centerx, dialog_rect.centery + 10
    editor_state.ui_elements_rects['dialog_text_input_box'] = input_box_rect # Store for event handling

    pygame.draw.rect(surface, ED_CONFIG.DIALOG_INPUT_BOX_COLOR, input_box_rect)
    pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), input_box_rect, 2) 

    text_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
    current_text_to_render = str(editor_state.dialog_input_text) if editor_state.dialog_input_text is not None else ""

    if text_font:
        # Draw highlight if text is selected
        if editor_state.dialog_input_text_selected:
            text_surf_for_highlight = text_font.render(current_text_to_render, True, ED_CONFIG.DIALOG_INPUT_TEXT_COLOR) # Render once for width
            highlight_width = text_surf_for_highlight.get_width()
            highlight_height = text_surf_for_highlight.get_height()
            
            text_padding_x = 6 
            highlight_rect = pygame.Rect(
                input_box_rect.left + text_padding_x,
                input_box_rect.centery - highlight_height // 2,
                highlight_width,
                highlight_height
            )
            # Clip highlight to be within the input box's drawable area
            clip_area_for_highlight = input_box_rect.inflate(-text_padding_x*2, -8) # Padded area
            highlight_rect = highlight_rect.clip(clip_area_for_highlight)
            
            pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'LIGHT_BLUE', (173,216,230)), highlight_rect)


        input_text_surf = text_font.render(current_text_to_render, True, ED_CONFIG.DIALOG_INPUT_TEXT_COLOR)
        text_clip_area_rect = input_box_rect.inflate(-12, -12) # Area where text is visible
        text_surf_width = input_text_surf.get_width()
        blit_area = None # For scrolling text if too long
        text_draw_pos_on_surface_x = text_clip_area_rect.left

        if text_surf_width > text_clip_area_rect.width:
            text_draw_pos_on_surface_x = text_clip_area_rect.right - text_surf_width
            blit_source_x_offset = text_surf_width - text_clip_area_rect.width
            blit_area = pygame.Rect(blit_source_x_offset, 0, text_clip_area_rect.width, input_text_surf.get_height())

        blit_destination_topleft = (text_draw_pos_on_surface_x,
                                    text_clip_area_rect.top + (text_clip_area_rect.height - input_text_surf.get_height()) // 2)
        
        original_clip = surface.get_clip()
        surface.set_clip(text_clip_area_rect)
        surface.blit(input_text_surf, blit_destination_topleft, area=blit_area)
        surface.set_clip(original_clip)

        # Draw cursor if text is not selected
        if not editor_state.dialog_input_text_selected:
            if blit_area: # Text is scrolled
                cursor_render_x = text_clip_area_rect.right -1
            else: # Text fits or is shorter
                cursor_render_x = text_clip_area_rect.left + input_text_surf.get_width() + 1
            
            cursor_render_x = max(text_clip_area_rect.left, min(cursor_render_x, text_clip_area_rect.right -1))

            if int(pygame.time.get_ticks() / 500) % 2 == 0: # Blinking cursor
                 pygame.draw.line(surface, ED_CONFIG.DIALOG_CURSOR_COLOR,
                                 (cursor_render_x, input_box_rect.top + 5),
                                 (cursor_render_x, input_box_rect.bottom - 5), 2)

    info_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if info_font:
        info_surf = info_font.render("Enter: Confirm, Esc: Cancel", True, getattr(ED_CONFIG.C, 'LIGHT_GRAY', (200,200,200))) 
        surface.blit(info_surf, info_surf.get_rect(midbottom=(dialog_rect.centerx, dialog_rect.bottom - 10)))

def _draw_color_picker_content(surface: pygame.Surface, editor_state: EditorState, dialog_rect: pygame.Rect, fonts: Dict[str, Optional[pygame.font.Font]]):
    mouse_pos_dialog = pygame.mouse.get_pos()
    default_fallback_color = (255, 0, 255) 

    for name, swatch_rect_relative in editor_state.color_picker_rects.items():
        absolute_swatch_rect = swatch_rect_relative.move(dialog_rect.left, dialog_rect.top)
        
        magenta_default = getattr(ED_CONFIG.C, 'MAGENTA', default_fallback_color)
        color_val = ED_CONFIG.COLOR_PICKER_PRESETS.get(name, magenta_default)

        pygame.draw.rect(surface, color_val, absolute_swatch_rect)
        border_col = getattr(ED_CONFIG.C, 'BLACK', (0,0,0)) 
        border_w = 1
        if absolute_swatch_rect.collidepoint(mouse_pos_dialog):
            border_col = getattr(ED_CONFIG, 'COLOR_PICKER_HOVER_BORDER_COLOR', getattr(ED_CONFIG.C, 'YELLOW', (255,255,0))) 
            border_w = 3
        pygame.draw.rect(surface, border_col, absolute_swatch_rect, border_w)

def _draw_file_load_content(surface: pygame.Surface, editor_state: EditorState, dialog_rect: pygame.Rect, fonts: Dict[str, Optional[pygame.font.Font]]):
    prompt_font = fonts.get("medium") or ED_CONFIG.FONT_CONFIG.get("medium")
    title_height = prompt_font.get_height() + 25 if prompt_font else 55
    buttons_panel_height = ED_CONFIG.BUTTON_HEIGHT_STANDARD // 2 + 20

    list_area_y_start = dialog_rect.top + title_height
    list_area_height = dialog_rect.height - title_height - buttons_panel_height

    list_area_rect = pygame.Rect(dialog_rect.left + 10, list_area_y_start, dialog_rect.width - 20, list_area_height)
    pygame.draw.rect(surface, ED_CONFIG.DIALOG_INPUT_BOX_COLOR, list_area_rect)
    pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'BLACK', (0,0,0)), list_area_rect, 1) 

    item_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    item_line_height = (item_font.get_height() + 6) if item_font else 22

    if 'dialog_file_item_rects' not in editor_state.ui_elements_rects: # Ensure it exists
        editor_state.ui_elements_rects['dialog_file_item_rects'] = []
    else:
        editor_state.ui_elements_rects['dialog_file_item_rects'].clear() # Clear for fresh drawing

    list_clip_rect = list_area_rect.inflate(-8, -8)
    total_content_height_pixels = len(editor_state.dialog_file_list) * item_line_height
    scrollbar_width_drawn = 0

    if total_content_height_pixels > list_clip_rect.height:
        scrollbar_width_drawn = 15
        scrollbar_track_rect = pygame.Rect(list_clip_rect.right + 2, list_clip_rect.top,
                                          scrollbar_width_drawn, list_clip_rect.height)
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'DARK_GRAY', (50,50,50)), scrollbar_track_rect) 
        handle_height_ratio = min(1.0, list_clip_rect.height / total_content_height_pixels if total_content_height_pixels > 0 else 1.0)
        handle_height = max(20, scrollbar_track_rect.height * handle_height_ratio)
        scrollable_content_outside_view = max(0, total_content_height_pixels - list_clip_rect.height)
        current_scroll_ratio_of_hidden = editor_state.dialog_file_scroll_y / scrollable_content_outside_view if scrollable_content_outside_view > 0 else 0
        handle_y_pos_on_track = (scrollbar_track_rect.height - handle_height) * current_scroll_ratio_of_hidden
        scrollbar_handle_rect = pygame.Rect(scrollbar_track_rect.left,
                                            scrollbar_track_rect.top + handle_y_pos_on_track,
                                            scrollbar_width_drawn, handle_height)
        pygame.draw.rect(surface, getattr(ED_CONFIG.C, 'GRAY', (128,128,128)), scrollbar_handle_rect, border_radius=3) 
        editor_state.ui_elements_rects['file_dialog_scrollbar_handle'] = scrollbar_handle_rect
        editor_state.ui_elements_rects['file_dialog_scrollbar_area'] = scrollbar_track_rect

    list_item_text_render_width = list_clip_rect.width - (scrollbar_width_drawn + 2 if scrollbar_width_drawn > 0 else 0)
    original_clip_pygame = surface.get_clip()
    surface.set_clip(list_clip_rect)
    current_y_offset_in_clip_rect = 0

    for i, filename in enumerate(editor_state.dialog_file_list):
        item_draw_y_on_surface = list_clip_rect.top + current_y_offset_in_clip_rect - editor_state.dialog_file_scroll_y
        item_full_rect_on_screen = pygame.Rect(list_clip_rect.left, item_draw_y_on_surface,
                                           list_item_text_render_width, item_line_height)
        if list_clip_rect.colliderect(item_full_rect_on_screen):
            editor_state.ui_elements_rects['dialog_file_item_rects'].append(
                {"text": filename, "rect": item_full_rect_on_screen, "index": i}
            )
            if item_font:
                text_color = getattr(ED_CONFIG.C, 'BLACK', (0,0,0)) 
                bg_color_item = ED_CONFIG.DIALOG_INPUT_BOX_COLOR
                if editor_state.dialog_selected_file_index == i:
                    bg_color_item = getattr(ED_CONFIG.C, 'BLUE', (0,0,255)) 
                    text_color = getattr(ED_CONFIG.C, 'WHITE', (255,255,255)) 
                pygame.draw.rect(surface, bg_color_item, item_full_rect_on_screen)
                text_surf = item_font.render(filename, True, text_color)
                text_draw_pos = (item_full_rect_on_screen.left + 5,
                                 item_full_rect_on_screen.centery - text_surf.get_height() // 2)
                surface.blit(text_surf, text_draw_pos)
        current_y_offset_in_clip_rect += item_line_height
    surface.set_clip(original_clip_pygame)

    button_font = fonts.get("small") or ED_CONFIG.FONT_CONFIG.get("small")
    if button_font:
        btn_width = ED_CONFIG.BUTTON_WIDTH_STANDARD // 2 - 15
        btn_height = ED_CONFIG.BUTTON_HEIGHT_STANDARD // 2 + 5
        buttons_y_pos = list_area_rect.bottom + 10
        
        # Determine button text based on prompt (a bit of a hack, better if dialog had a 'purpose' flag)
        ok_text = "Load"
        if "delete" in editor_state.dialog_prompt_message.lower():
            ok_text = "Select" # For delete, the file dialog is just for selection

        ok_button_rect = pygame.Rect(dialog_rect.centerx - btn_width - 5, buttons_y_pos, btn_width, btn_height)
        cancel_button_rect = pygame.Rect(dialog_rect.centerx + 5, buttons_y_pos, btn_width, btn_height)
        mouse_pos = pygame.mouse.get_pos()
        ok_is_active = (editor_state.dialog_selected_file_index != -1 and
                        0 <= editor_state.dialog_selected_file_index < len(editor_state.dialog_file_list))
        draw_button(surface, ok_button_rect, ok_text, button_font, mouse_pos, is_active=ok_is_active)
        draw_button(surface, cancel_button_rect, "Cancel", button_font, mouse_pos)
        editor_state.ui_elements_rects["dialog_file_load_ok"] = ok_button_rect
        editor_state.ui_elements_rects["dialog_file_load_cancel"] = cancel_button_rect