########## START OF FILE: settings_ui.py ##########
# settings_ui.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.2 (Corrected reference to game_config.CURRENT_P1_INPUT_DEVICE)
UI for configuring game settings, primarily controls for Player 1 and Player 2.
"""
import pygame
import config as game_config # Import our new config module
import constants as C # For colors or other UI constants if needed

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
BG_COLOR_SELECTED = C.DARK_GREEN # For a selected device button

# Store UI element rects for click detection
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

def _draw_button(surface, id_key, text, rect, font, mouse_pos, current_selection=False):
    """Draws a button and stores its rect in ui_elements."""
    is_hovered = rect.collidepoint(mouse_pos)
    
    bg_color = BG_COLOR_NORMAL
    if current_selection:
        bg_color = BG_COLOR_SELECTED
    if is_hovered:
        bg_color = BG_COLOR_HOVER
        if current_selection:
             bg_color = pygame.Color(BG_COLOR_SELECTED).lerp(pygame.Color(BG_COLOR_HOVER), 0.5)


    pygame.draw.rect(surface, bg_color, rect, border_radius=5)
    pygame.draw.rect(surface, C.BLACK, rect, 2, border_radius=5)
    
    text_color = TEXT_COLOR_SELECTED if current_selection and not is_hovered else TEXT_COLOR
    if is_hovered and current_selection : text_color = C.WHITE

    _draw_text(surface, text, rect.center, font, color=text_color, center_x=True, center_y=True)
    ui_elements[id_key] = rect
    return is_hovered


def _display_key_mappings(surface, start_y, player_id_str, device_id_str, font, screen_width):
    """Displays current key mappings for the selected device."""
    mappings = game_config.get_action_key_map(int(player_id_str[-1]), device_id_str)
    
    col1_x = screen_width * 0.15
    col2_x = screen_width * 0.4
    
    _draw_text(surface, f"{player_id_str} Mappings ({device_id_str.replace('_',' ').title()}):", 
               (screen_width * 0.5, start_y), font, TEXT_COLOR_SELECTED, center_x=True)
    start_y += font.get_height() + 10

    action_idx = 0
    for action in game_config.GAME_ACTIONS:
        if action in ["pause", "menu_confirm", "menu_cancel"]: # Skip some for brevity in player config
            continue

        mapping_info = mappings.get(action)
        display_text = "Not Set"

        if device_id_str.startswith("keyboard"):
            if isinstance(mapping_info, int): # Pygame key constant
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
                    display_text = f"Hat {m_id} Val {m_val}"
        
        current_col_x = col1_x if action_idx % 2 == 0 else col2_x
        _draw_text(surface, f"{action.replace('_',' ').title()}:", (current_col_x, start_y), font, TEXT_COLOR)
        _draw_text(surface, display_text, (current_col_x + 170, start_y), font, TEXT_COLOR_VALUE)
        
        if action_idx % 2 == 1:
            start_y += font.get_height() + 5
        action_idx += 1
    return start_y + SECTION_SPACING


def show_control_settings_screen(screen: pygame.Surface, clock: pygame.time.Clock,
                                 fonts: dict, app_status, joystick_handler):
    """
    Main loop for the control settings screen.
    Args:
        joystick_handler: An instance of a joystick handling class/module.
                          Needs methods like get_joystick_count() and get_joystick_name(id).
    """
    running_settings = True
    ui_elements.clear() # Clear UI elements from previous screens

    # Load current settings when entering the screen
    game_config.load_config()
    p1_device_choice = game_config.CURRENT_P1_INPUT_DEVICE
    p2_device_choice = game_config.CURRENT_P2_INPUT_DEVICE
    
    available_joysticks = []
    if joystick_handler:
        joystick_count = joystick_handler.get_joystick_count()
        for i in range(joystick_count):
            name = joystick_handler.get_joystick_name(i)
            available_joysticks.append({"id": f"joystick_{i}", "name": name if name else f"Joystick {i}"})
            if name and ("pro controller" in name.lower() or "switch" in name.lower()):
                 available_joysticks[-1]["name"] = f"NS Pro Controller ({i})" 

    font_title = fonts.get("large") or pygame.font.Font(None, 50)
    font_header = fonts.get("medium") or pygame.font.Font(None, 36)
    font_button = fonts.get("medium") or pygame.font.Font(None, 28)
    font_text = fonts.get("small") or pygame.font.Font(None, 22)

    while running_settings and app_status.app_running:
        screen_w, screen_h = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()
        
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app_status.app_running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running_settings = False 
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if ui_elements.get("save_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                    game_config.CURRENT_P1_INPUT_DEVICE = p1_device_choice
                    game_config.CURRENT_P2_INPUT_DEVICE = p2_device_choice
                    game_config.update_player_mappings_from_device_choice() 
                    game_config.save_config()
                    running_settings = False
                elif ui_elements.get("cancel_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                    running_settings = False 

                if ui_elements.get("p1_key_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                    p1_old_device = p1_device_choice # Store old P1 device
                    p1_device_choice = "keyboard_p1"
                    # If P1 was on joystick and P2 was using P1's keyboard keys,
                    # P2 should switch to its own dedicated keyboard keys.
                    if p2_device_choice == "keyboard_p1" and p1_old_device.startswith("joystick"):
                        p2_device_choice = "keyboard_p2"
                for joy_info in available_joysticks:
                    if ui_elements.get(f"p1_{joy_info['id']}_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                        p1_device_choice = joy_info['id']
                        p2_device_choice = "keyboard_p1" 

                if p1_device_choice.startswith("keyboard"): 
                    if ui_elements.get("p2_key1_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                        p2_device_choice = "keyboard_p1"
                    if ui_elements.get("p2_key2_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                        p2_device_choice = "keyboard_p2"
                    for joy_info in available_joysticks:
                        if p1_device_choice == joy_info['id']: continue # This check is actually for P1, not P2 against P1.
                                                                      # P2 should not select the same joystick instance P1 *might* be using if P1 is keyboard
                                                                      # Correct logic: if P1 is on keyboard, P2 can pick any joystick.
                                                                      # If P1 is on joystick_X, P2 cannot pick joystick_X.
                        # The problematic line was here, using a global-like CURRENT_P1_INPUT_DEVICE from game_config
                        # instead of the local p1_device_choice to check against P2's joystick selection.
                        # However, the condition `if p1_device_choice.startswith("keyboard"):` already handles
                        # the scenario where P1 is on keyboard, so P2 can choose any joystick.
                        # The critical part is when P1 *is* on a joystick, P2 cannot pick the *same* one.
                        # This will be implicitly handled by the available choices for P2's joystick buttons below.

                        if ui_elements.get(f"p2_{joy_info['id']}_button", pygame.Rect(0,0,0,0)).collidepoint(mouse_pos):
                            p2_device_choice = joy_info['id']
        
        # --- Drawing ---
        screen.fill(C.BLACK)
        _draw_text(screen, "Control Settings", (screen_w // 2, screen_h * 0.05), font_title, center_x=True)

        current_y = screen_h * 0.15

        _draw_text(screen, "Player 1 Input:", (screen_w * 0.1, current_y), font_header)
        current_y += font_header.get_height() + 5
        
        p1_key_rect = pygame.Rect(screen_w * 0.1, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        _draw_button(screen, "p1_key_button", "Keyboard (P1 Default)", p1_key_rect, font_button, mouse_pos, p1_device_choice == "keyboard_p1")
        
        joy_btn_x = screen_w * 0.1 + BUTTON_WIDTH + BUTTON_SPACING
        for joy_info in available_joysticks:
            joy_rect = pygame.Rect(joy_btn_x, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
            _draw_button(screen, f"p1_{joy_info['id']}_button", joy_info["name"], joy_rect, font_button, mouse_pos, p1_device_choice == joy_info['id'])
            joy_btn_x += BUTTON_WIDTH + BUTTON_SPACING
            if joy_btn_x + BUTTON_WIDTH > screen_w * 0.9: 
                joy_btn_x = screen_w * 0.1 + BUTTON_WIDTH + BUTTON_SPACING
                current_y += BUTTON_HEIGHT + 5
        
        current_y += BUTTON_HEIGHT + SECTION_SPACING

        _draw_text(screen, "Player 2 Input:", (screen_w * 0.1, current_y), font_header)
        current_y += font_header.get_height() + 5

        p2_controls_enabled = p1_device_choice.startswith("keyboard")
        p2_text_alpha = 255 if p2_controls_enabled else 100 

        temp_surface = pygame.Surface((BUTTON_WIDTH, BUTTON_HEIGHT), pygame.SRCALPHA)

        p2_key1_rect = pygame.Rect(screen_w * 0.1, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        temp_surface.fill((0,0,0,0))
        _draw_button(temp_surface, "p2_key1_button", "Keyboard (P1 Keys)", temp_surface.get_rect(), font_button, mouse_pos if p2_controls_enabled else (-1,-1), p2_device_choice == "keyboard_p1" and p2_controls_enabled)
        temp_surface.set_alpha(p2_text_alpha)
        screen.blit(temp_surface, p2_key1_rect.topleft)
        if p2_controls_enabled: ui_elements["p2_key1_button"] = p2_key1_rect

        p2_key2_rect = pygame.Rect(screen_w * 0.1 + BUTTON_WIDTH + BUTTON_SPACING, current_y, BUTTON_WIDTH, BUTTON_HEIGHT)
        temp_surface.fill((0,0,0,0))
        _draw_button(temp_surface, "p2_key2_button", "Keyboard (P2 Default)", temp_surface.get_rect(), font_button, mouse_pos if p2_controls_enabled else (-1,-1), p2_device_choice == "keyboard_p2" and p2_controls_enabled)
        temp_surface.set_alpha(p2_text_alpha)
        screen.blit(temp_surface, p2_key2_rect.topleft)
        if p2_controls_enabled: ui_elements["p2_key2_button"] = p2_key2_rect
        
        joy_btn_x_p2 = screen_w * 0.1 + 2 * (BUTTON_WIDTH + BUTTON_SPACING)
        current_joy_y_p2 = current_y # Keep track of Y for P2 joystick buttons separately

        for joy_info in available_joysticks:
            # P2 cannot select the same joystick instance that P1 has chosen
            if p1_device_choice == joy_info['id']: 
                continue 
            
            joy_rect_p2 = pygame.Rect(joy_btn_x_p2, current_joy_y_p2, BUTTON_WIDTH, BUTTON_HEIGHT)
            temp_surface.fill((0,0,0,0))
            _draw_button(temp_surface, f"p2_{joy_info['id']}_button", joy_info["name"], temp_surface.get_rect(), font_button, mouse_pos if p2_controls_enabled else (-1,-1), p2_device_choice == joy_info['id'] and p2_controls_enabled)
            temp_surface.set_alpha(p2_text_alpha)
            screen.blit(temp_surface, joy_rect_p2.topleft)
            if p2_controls_enabled: ui_elements[f"p2_{joy_info['id']}_button"] = joy_rect_p2

            joy_btn_x_p2 += BUTTON_WIDTH + BUTTON_SPACING
            if joy_btn_x_p2 + BUTTON_WIDTH > screen_w * 0.9:
                joy_btn_x_p2 = screen_w * 0.1 + 2 * (BUTTON_WIDTH + BUTTON_SPACING) 
                current_joy_y_p2 += BUTTON_HEIGHT + 5 
        
        # Ensure current_y advances past the P2 joystick buttons if they wrapped
        current_y = max(current_y, current_joy_y_p2) 
        current_y += BUTTON_HEIGHT + SECTION_SPACING

        current_y = _display_key_mappings(screen, current_y, "Player 1", p1_device_choice, font_text, screen_w)
        current_y = _display_key_mappings(screen, current_y, "Player 2", p2_device_choice, font_text, screen_w)

        save_rect = pygame.Rect(0,0, BUTTON_WIDTH // 1.5, BUTTON_HEIGHT)
        save_rect.centerx = screen_w * 0.35
        save_rect.bottom = screen_h - 30
        _draw_button(screen, "save_button", "Save & Back", save_rect, font_button, mouse_pos)

        cancel_rect = pygame.Rect(0,0, BUTTON_WIDTH // 1.5, BUTTON_HEIGHT)
        cancel_rect.centerx = screen_w * 0.65
        cancel_rect.bottom = screen_h - 30
        _draw_button(screen, "cancel_button", "Cancel", cancel_rect, font_button, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    game_config.load_config()
########## END OF FILE: settings_ui.py ##########