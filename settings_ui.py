########## START OF FILE: settings_ui.py ##########
# settings_ui.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.4 (Simplified _display_key_mappings column logic)
UI for configuring game settings, primarily controls for Player 1 and Player 2.
"""
import pygame
import config as game_config 
import constants as C 
import joystick_handler

# --- UI Element Properties ---
BUTTON_WIDTH = 250 
BUTTON_HEIGHT = 40
BUTTON_SPACING = 15
SECTION_SPACING = 30
TEXT_COLOR = C.WHITE
TEXT_COLOR_SELECTED = C.YELLOW
TEXT_COLOR_VALUE = C.LIGHT_BLUE
BG_COLOR_NORMAL = C.BLUE
BG_COLOR_HOVER = C.GREEN
BG_COLOR_SELECTED = C.DARK_GREEN 

ui_elements = {}


def _draw_text(surface, text, pos, font, color=TEXT_COLOR, center_x=False, center_y=False):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if center_x:
        text_rect.centerx = pos[0]
    else:
        text_rect.left = pos[0]
    if center_y:
        text_rect.centery = pos[1]
    else:
        text_rect.top = pos[1]
    surface.blit(text_surface, text_rect)
    return text_rect

def _draw_button(surface, id_key, text, rect, font, mouse_pos, current_selection=False, enabled=True):
    """Draws a button and stores its rect in ui_elements."""
    is_hovered = False
    if enabled and rect.collidepoint(mouse_pos):
        is_hovered = True
    
    bg_color = BG_COLOR_NORMAL
    current_text_color = TEXT_COLOR

    if not enabled:
        bg_color = tuple(c // 2 for c in BG_COLOR_NORMAL) 
        current_text_color = tuple(c // 2 for c in TEXT_COLOR) 
    elif current_selection:
        bg_color = BG_COLOR_SELECTED
        current_text_color = TEXT_COLOR_SELECTED 
        if is_hovered:
             bg_color = pygame.Color(BG_COLOR_SELECTED).lerp(pygame.Color(BG_COLOR_HOVER), 0.5)
             current_text_color = C.WHITE 
    elif is_hovered:
        bg_color = BG_COLOR_HOVER
    
    pygame.draw.rect(surface, bg_color, rect, border_radius=5)
    pygame.draw.rect(surface, C.BLACK if enabled else C.DARK_GRAY, rect, 2, border_radius=5)
    
    _draw_text(surface, text, rect.center, font, color=current_text_color, center_x=True, center_y=True)
    if enabled: 
        ui_elements[id_key] = rect
    elif id_key in ui_elements: 
        del ui_elements[id_key]
        
    return is_hovered


def _display_key_mappings(surface, start_y, player_id_str, device_id_str, font, screen_width):
    """Displays current key mappings for the selected device."""
    mappings = game_config.get_action_key_map(int(player_id_str[-1]), device_id_str)
    
    col1_x = screen_width * 0.15
    col2_x = screen_width * 0.55 
    
    _draw_text(surface, f"{player_id_str} Mappings ({device_id_str.replace('_',' ').title()}):", 
               (screen_width * 0.5, start_y), font, TEXT_COLOR_SELECTED, center_x=True)
    current_y_for_items = start_y + font.get_height() + 10 # Y position for the first item in a column

    action_idx = 0
    # max_actions_per_col = 10 # Define how many items before switching column
    
    # For now, simple single column layout that might wrap off screen if too many actions.
    # A proper two-column layout needs careful Y management.
    
    y_offset_in_column = 0

    for action in game_config.GAME_ACTIONS:
        if action in ["pause", "menu_confirm", "menu_cancel", "menu_up", "menu_down", "menu_left", "menu_right"] and not device_id_str.startswith("keyboard"):
            pass 
        elif action.startswith("menu_") and not device_id_str.startswith("keyboard"): 
            continue

        mapping_info = mappings.get(action)
        display_text = "Not Set"

        if device_id_str.startswith("keyboard"):
            if isinstance(mapping_info, int): 
                display_text = pygame.key.name(mapping_info).title()
        elif device_id_str.startswith("joystick"):
            if isinstance(mapping_info, dict):
                m_type = mapping_info.get("type")
                m_id = mapping_info.get("id")
                m_val = mapping_info.get("value")
                if m_type == "button":
                    display_text = f"Button {m_id}"
                elif m_type == "axis":
                    direction = "Pos" if m_val == 1 else ("Neg" if m_val == -1 else "")
                    display_text = f"Axis {m_id} {direction}"
                elif m_type == "hat":
                    hat_x, hat_y = m_val
                    hat_dir = ""
                    if hat_x == -1: hat_dir += "Left"
                    if hat_x == 1: hat_dir += "Right"
                    if hat_y == 1: hat_dir += "Up"
                    if hat_y == -1: hat_dir += "Down"
                    display_text = f"Hat {m_id} {hat_dir if hat_dir else str(m_val)}"
        
        # Simplified to one column for now to avoid the NameError
        _draw_text(surface, f"{action.replace('_',' ').title()}:", (col1_x, current_y_for_items + y_offset_in_column), font, TEXT_COLOR)
        _draw_text(surface, display_text, (col1_x + 170, current_y_for_items + y_offset_in_column), font, TEXT_COLOR_VALUE)
        
        y_offset_in_column += font.get_height() + 5
        action_idx += 1
        
    return current_y_for_items + y_offset_in_column + SECTION_SPACING


def show_control_settings_screen(screen: pygame.Surface, clock: pygame.time.Clock,
                                 fonts: dict, app_status, joystick_handler):
    # global current_y_mappings_title # This global is no longer needed with simplified mapping display

    running_settings = True
    ui_elements.clear() 

    game_config.load_config() 
    p1_device_choice_ui = str(game_config.CURRENT_P1_INPUT_DEVICE) 
    p2_device_choice_ui = str(game_config.CURRENT_P2_INPUT_DEVICE)
    
    available_joysticks = []
    if joystick_handler:
        joystick_count = joystick_handler.get_joystick_count()
        for i in range(joystick_count):
            name = joystick_handler.get_joystick_name(i)
            joy_id_str = f"joystick_{i}"
            display_name = name if name and name != f"Joystick {i}" else f"Controller {i}"
            if name and ("pro controller" in name.lower() or "switch" in name.lower()):
                 display_name = f"NS Pro ({i})"
            elif name and ("xbox 360" in name.lower()):
                 display_name = f"Xbox 360 ({i})"
            available_joysticks.append({"id": joy_id_str, "name": display_name})


    font_title = fonts.get("large") or pygame.font.Font(None, 50)
    font_header = fonts.get("medium") or pygame.font.Font(None, 36)
    font_button = fonts.get("medium") or pygame.font.Font(None, 28)
    font_text = fonts.get("small") or pygame.font.Font(None, 22)

    while running_settings and app_status.app_running:
        screen_w, screen_h = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app_status.app_running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running_settings = False 
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_element = None
                for id_key, rect in ui_elements.items():
                    if rect.collidepoint(mouse_pos):
                        clicked_element = id_key
                        break
                
                if clicked_element == "save_button":
                    game_config.CURRENT_P1_INPUT_DEVICE = p1_device_choice_ui
                    game_config.CURRENT_P2_INPUT_DEVICE = p2_device_choice_ui
                    game_config.update_player_mappings_from_device_choice() 
                    game_config.save_config()
                    running_settings = False
                elif clicked_element == "cancel_button":
                    running_settings = False 
                
                elif clicked_element == "p1_key_button":
                    p1_old_device_ui = p1_device_choice_ui 
                    p1_device_choice_ui = "keyboard_p1"
                    if p2_device_choice_ui == "keyboard_p1" and p1_old_device_ui.startswith("joystick"):
                         p2_device_choice_ui = "keyboard_p2" 
                else:
                    for joy_info in available_joysticks:
                        if clicked_element == f"p1_{joy_info['id']}_button":
                            p1_device_choice_ui = joy_info['id']
                            p2_device_choice_ui = "keyboard_p1" 
                            break
                
                if p1_device_choice_ui.startswith("keyboard"):
                    if clicked_element == "p2_key1_button":
                        p2_device_choice_ui = "keyboard_p1"
                    elif clicked_element == "p2_key2_button":
                        p2_device_choice_ui = "keyboard_p2"
                    else:
                        for joy_info in available_joysticks:
                            if clicked_element == f"p2_{joy_info['id']}_button":
                                p2_device_choice_ui = joy_info['id']
                                break
        
        screen.fill(C.BLACK)
        _draw_text(screen, "Control Settings", (screen_w // 2, screen_h * 0.05), font_title, center_x=True)

        current_y = screen_h * 0.12 

        _draw_text(screen, "Player 1 Input:", (screen_w * 0.05, current_y), font_header)
        current_y += font_header.get_height() + 10
        
        row_x = screen_w * 0.05
        p1_key_rect = pygame.Rect(row_x, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        _draw_button(screen, "p1_key_button", "Keyboard (P1 Default)", p1_key_rect, font_button, mouse_pos, p1_device_choice_ui == "keyboard_p1")
        row_x += BUTTON_WIDTH + BUTTON_SPACING
        
        for joy_info in available_joysticks:
            if row_x + BUTTON_WIDTH > screen_w * 0.95 : 
                row_x = screen_w * 0.05
                current_y += BUTTON_HEIGHT + 5
            joy_rect = pygame.Rect(row_x, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
            _draw_button(screen, f"p1_{joy_info['id']}_button", joy_info["name"], joy_rect, font_button, mouse_pos, p1_device_choice_ui == joy_info['id'])
            row_x += BUTTON_WIDTH + BUTTON_SPACING
        
        current_y += BUTTON_HEIGHT + SECTION_SPACING

        _draw_text(screen, "Player 2 Input:", (screen_w * 0.05, current_y), font_header)
        current_y += font_header.get_height() + 10
        p2_controls_enabled = p1_device_choice_ui.startswith("keyboard")
        
        row_x = screen_w * 0.05
        p2_key1_rect = pygame.Rect(row_x, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        _draw_button(screen, "p2_key1_button", "Keyboard (P1 Keys)", p2_key1_rect, font_button, mouse_pos, 
                     p2_device_choice_ui == "keyboard_p1" and p2_controls_enabled, enabled=p2_controls_enabled)
        row_x += BUTTON_WIDTH + BUTTON_SPACING

        p2_key2_rect = pygame.Rect(row_x, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        _draw_button(screen, "p2_key2_button", "Keyboard (P2 Default)", p2_key2_rect, font_button, mouse_pos, 
                     p2_device_choice_ui == "keyboard_p2" and p2_controls_enabled, enabled=p2_controls_enabled)
        row_x += BUTTON_WIDTH + BUTTON_SPACING
        
        current_joy_y_p2 = current_y # Store y for this row of joystick buttons
        for joy_info in available_joysticks:
            if p1_device_choice_ui == joy_info['id'] and p1_device_choice_ui.startswith("joystick"):
                 is_p2_joy_button_enabled = False 
            else:
                 is_p2_joy_button_enabled = p2_controls_enabled

            if row_x + BUTTON_WIDTH > screen_w * 0.95 : 
                row_x = screen_w * 0.05
                current_joy_y_p2 += BUTTON_HEIGHT + 5 # Use separate Y for P2 joystick buttons if they wrap
            
            joy_rect_p2 = pygame.Rect(row_x, current_joy_y_p2, BUTTON_WIDTH, BUTTON_HEIGHT)
            _draw_button(screen, f"p2_{joy_info['id']}_button", joy_info["name"], joy_rect_p2, font_button, mouse_pos, 
                         p2_device_choice_ui == joy_info['id'] and is_p2_joy_button_enabled, enabled=is_p2_joy_button_enabled)
            row_x += BUTTON_WIDTH + BUTTON_SPACING
        
        current_y = max(current_y, current_joy_y_p2) # Ensure current_y is past the P2 joystick buttons
        current_y += BUTTON_HEIGHT + SECTION_SPACING
        
        # current_y_mappings_title = current_y # This was part of the complex column logic

        current_y = _display_key_mappings(screen, current_y, "Player 1", p1_device_choice_ui, font_text, screen_w)
        if p2_controls_enabled : # Only show P2 mappings if P2 controls are active
            current_y = _display_key_mappings(screen, current_y + SECTION_SPACING //2 , "Player 2", p2_device_choice_ui, font_text, screen_w)
        else: # Add some space if P2 mappings are not shown
            current_y += font_text.get_height() * 2 # Approximate space for a mappings header


        save_rect = pygame.Rect(0,0, BUTTON_WIDTH // 1.2, BUTTON_HEIGHT)
        save_rect.centerx = screen_w * 0.30
        save_rect.bottom = screen_h - 25
        _draw_button(screen, "save_button", "Save & Back", save_rect, font_button, mouse_pos)

        cancel_rect = pygame.Rect(0,0, BUTTON_WIDTH // 1.2, BUTTON_HEIGHT)
        cancel_rect.centerx = screen_w * 0.70
        cancel_rect.bottom = screen_h - 25
        _draw_button(screen, "cancel_button", "Cancel (No Save)", cancel_rect, font_button, mouse_pos)

        pygame.display.flip()
        clock.tick(C.FPS)

    game_config.load_config()
########## END OF FILE: settings_ui.py ##########