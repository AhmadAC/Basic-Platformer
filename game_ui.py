########## START OF FILE: game_ui.py ##########

# ui.py
# -*- coding: utf-8 -*-
## version 1.0.0.3 (Added default_input_text to get_server_ip_input_dialog)
"""
Functions for drawing User Interface elements like health bars, player HUDs,
main menus, input dialogs, and the main game scene.
"""
import pygame
import time # For cursor blinking in input dialog and message display timings
import constants as C # For accessing color constants and UI-related dimensions
from typing import Dict, Optional, Any # For type hinting

# --- Pyperclip & Pygame Scrap Check (for paste functionality in input dialog) ---
PYPERCLIP_AVAILABLE_UI_MODULE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_UI_MODULE = True
except ImportError:
    pass 

SCRAP_INITIALIZED_UI_MODULE = False # This will be updated by check_pygame_scrap_init_status

def check_pygame_scrap_init_status():
    """Checks and updates the status of Pygame's scrap module initialization."""
    global SCRAP_INITIALIZED_UI_MODULE
    try:
        if pygame.scrap.get_init(): 
            SCRAP_INITIALIZED_UI_MODULE = True
        else:
            SCRAP_INITIALIZED_UI_MODULE = False
    except (AttributeError, pygame.error): 
        SCRAP_INITIALIZED_UI_MODULE = False
    return SCRAP_INITIALIZED_UI_MODULE


# --- Health Bar Drawing Function ---
def draw_health_bar(surface: pygame.Surface, x: int, y: int, 
                    width: int, height: int, 
                    current_hp: float, max_hp: float):
    if max_hp <= 0: return

    current_hp_clamped = max(0, min(current_hp, max_hp))
    bar_width = max(1, int(width)) # Ensure width is at least 1 and int
    bar_height = max(1, int(height)) # Ensure height is at least 1 and int
    
    health_ratio = current_hp_clamped / max_hp

    # Determine health bar color (lerping from red to green)
    # Ensure C.RED and C.GREEN are available, otherwise fallback
    color_red = getattr(C, 'RED', (255,0,0))
    color_green = getattr(C, 'GREEN', (0,255,0))
    color_dark_gray = getattr(C, 'DARK_GRAY', (50,50,50))
    color_black = getattr(C, 'BLACK', (0,0,0))

    try: 
        # Pygame's Color.lerp is convenient if available
        health_color = pygame.Color(color_red).lerp(pygame.Color(color_green), health_ratio)
    except AttributeError: # Fallback manual lerp if pygame.Color.lerp is not available or constants are not Color objects
        r = int(color_red[0] * (1 - health_ratio) + color_green[0] * health_ratio)
        g = int(color_red[1] * (1 - health_ratio) + color_green[1] * health_ratio)
        b = int(color_red[2] * (1 - health_ratio) + color_green[2] * health_ratio)
        health_color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    background_rect = pygame.Rect(x, y, bar_width, bar_height)
    pygame.draw.rect(surface, color_dark_gray, background_rect)

    health_fill_width = int(bar_width * health_ratio)
    if health_fill_width > 0: 
        health_fill_rect = pygame.Rect(x, y, health_fill_width, bar_height)
        pygame.draw.rect(surface, health_color, health_fill_rect)
    
    pygame.draw.rect(surface, color_black, background_rect, 1) 


# --- Player HUD Drawing Function ---
def draw_player_hud(surface: pygame.Surface, x: int, y: int, 
                    player_instance: Any, 
                    player_number: int, 
                    hud_font_obj: Optional[pygame.font.Font]):
    if not player_instance or not hasattr(player_instance, 'current_health') or \
       not hasattr(player_instance, 'max_health'):
        # print(f"DEBUG UI (draw_player_hud): P{player_number} instance invalid or no health attributes. Skipping HUD.") # DEBUG
        return

    # DEBUG: Print player instance details for HUD
    # if hasattr(player_instance, 'player_id'):
    #     print(f"DEBUG UI (draw_player_hud): Drawing HUD for P{player_number} (ID: {player_instance.player_id}). Valid: {getattr(player_instance, '_valid_init', 'N/A')}, Alive: {player_instance.alive() if hasattr(player_instance, 'alive') else 'N/A'}, Pos: {getattr(player_instance, 'pos', 'N/A')}") # DEBUG
    # else:
    #     print(f"DEBUG UI (draw_player_hud): Drawing HUD for P{player_number}. Instance has no player_id.") # DEBUG


    player_label_text = f"P{player_number}"
    label_height_offset = 0 
    color_white = getattr(C, 'WHITE', (255,255,255))
    
    if hud_font_obj: 
        try:
            label_surface = hud_font_obj.render(player_label_text, True, color_white) 
            surface.blit(label_surface, (x, y)) 
            label_height_offset = label_surface.get_height() 
        except Exception as e: 
            print(f"UI Warning: Could not render HUD label for P{player_number}: {e}")
            label_height_offset = getattr(hud_font_obj, 'get_height', lambda: 20)() # Fallback height
    else: 
        # print(f"DEBUG UI (draw_player_hud): No HUD font for P{player_number} label.") # DEBUG
        label_height_offset = 0 

    health_bar_pos_x = x
    health_bar_pos_y = y + label_height_offset + 5  
    hud_health_bar_width = getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH', 50) * 2)
    hud_health_bar_height = getattr(C, 'HUD_HEALTH_BAR_HEIGHT', getattr(C, 'HEALTH_BAR_HEIGHT', 8) + 4)

    draw_health_bar(surface, health_bar_pos_x, health_bar_pos_y,
                    hud_health_bar_width, hud_health_bar_height,
                    player_instance.current_health, player_instance.max_health)

    if hud_font_obj: 
        try:
            health_value_text = f"{int(player_instance.current_health)}/{int(player_instance.max_health)}"
            health_text_surface = hud_font_obj.render(health_value_text, True, color_white)
            health_text_pos_x = health_bar_pos_x + hud_health_bar_width + 10 
            health_text_pos_y = health_bar_pos_y + (hud_health_bar_height - health_text_surface.get_height()) // 2 # Use // for int
            surface.blit(health_text_surface, (health_text_pos_x, health_text_pos_y))
        except Exception as e: 
            print(f"UI Warning: Could not render HUD health text for P{player_number}: {e}")
    # else:
        # print(f"DEBUG UI (draw_player_hud): No HUD font for P{player_number} health text.") # DEBUG


# --- Main Game Scene Drawing Function ---
def draw_platformer_scene_on_surface(screen_surface: pygame.Surface, 
                                     game_elements: Dict[str, Any], 
                                     fonts: Dict[str, Optional[pygame.font.Font]], 
                                     current_game_time_ticks: int): 
    # print(f"DEBUG UI (draw_scene): Frame {current_game_time_ticks // (1000//C.FPS if C.FPS > 0 else 16)}") # DEBUG frame number
    camera_instance = game_elements.get("camera")
    all_sprites_group = game_elements.get("all_sprites") 
    enemy_list_for_health_bars = game_elements.get("enemy_list", [])
    player1_instance = game_elements.get("player1")
    player2_instance = game_elements.get("player2")
    
    font_for_hud = fonts.get("medium")
    if font_for_hud is None:
        font_for_hud = pygame.font.Font(None, 24) if pygame.font.get_init() else None
        
    current_screen_width, _ = screen_surface.get_size()
    bg_color = getattr(C, 'LIGHT_BLUE', (135, 206, 235))
    screen_surface.fill(bg_color) 

    if camera_instance and all_sprites_group:
        # print(f"DEBUG UI (draw_scene): Camera Pos: {camera_instance.get_pos()}, Num All Sprites: {len(all_sprites_group)}") # DEBUG
        drawn_p1 = False
        drawn_p2 = False
        for entity_sprite in all_sprites_group: 
            if entity_sprite.alive() and hasattr(entity_sprite, 'image') and hasattr(entity_sprite, 'rect'):
                 applied_rect = camera_instance.apply(entity_sprite.rect)
                 # DEBUG Player specific draw info
                 if entity_sprite is player1_instance:
                     # print(f"DEBUG UI (draw_scene): Drawing P1 (ID {getattr(entity_sprite, 'player_id', 'N/A')}). Alive: {entity_sprite.alive()}, Valid: {getattr(entity_sprite, '_valid_init', 'N/A')}. World Rect: {entity_sprite.rect}, Screen Rect: {applied_rect}, Image Size: {entity_sprite.image.get_size() if entity_sprite.image else 'No Image'}") # DEBUG
                     drawn_p1 = True
                 elif entity_sprite is player2_instance:
                     # print(f"DEBUG UI (draw_scene): Drawing P2 (ID {getattr(entity_sprite, 'player_id', 'N/A')}). Alive: {entity_sprite.alive()}, Valid: {getattr(entity_sprite, '_valid_init', 'N/A')}. World Rect: {entity_sprite.rect}, Screen Rect: {applied_rect}, Image Size: {entity_sprite.image.get_size() if entity_sprite.image else 'No Image'}") # DEBUG
                     drawn_p2 = True

                 screen_surface.blit(entity_sprite.image, applied_rect)
        # if player1_instance and not drawn_p1:
            # print(f"DEBUG UI (draw_scene): P1 instance exists but was NOT drawn from all_sprites. Alive: {player1_instance.alive() if hasattr(player1_instance, 'alive') else 'N/A'}, Valid: {getattr(player1_instance, '_valid_init', 'N/A')}") # DEBUG
        # if player2_instance and not drawn_p2:
            # print(f"DEBUG UI (draw_scene): P2 instance exists but was NOT drawn from all_sprites. Alive: {player2_instance.alive() if hasattr(player2_instance, 'alive') else 'N/A'}, Valid: {getattr(player2_instance, '_valid_init', 'N/A')}") # DEBUG

        
        for enemy_sprite in enemy_list_for_health_bars:
            if enemy_sprite.alive() and getattr(enemy_sprite, '_valid_init', False) and not \
               (getattr(enemy_sprite, 'is_dead', False) and getattr(enemy_sprite, 'death_animation_finished', False)) and \
               hasattr(enemy_sprite, 'current_health') and hasattr(enemy_sprite, 'max_health'):
                
                enemy_rect_on_screen = camera_instance.apply(enemy_sprite.rect) 
                health_bar_width_enemy = getattr(C, 'HEALTH_BAR_WIDTH', 50)
                health_bar_height_enemy = getattr(C, 'HEALTH_BAR_HEIGHT', 8)
                health_bar_pos_x_enemy = enemy_rect_on_screen.centerx - health_bar_width_enemy // 2 # Use //
                health_bar_pos_y_enemy = enemy_rect_on_screen.top - health_bar_height_enemy - \
                                         getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5) 
                
                draw_health_bar(screen_surface, health_bar_pos_x_enemy, health_bar_pos_y_enemy, 
                                health_bar_width_enemy, health_bar_height_enemy, 
                                enemy_sprite.current_health, enemy_sprite.max_health)
    elif all_sprites_group: 
        # print(f"DEBUG UI (draw_scene): No camera, using all_sprites.draw(). Num All Sprites: {len(all_sprites_group)}") # DEBUG
        all_sprites_group.draw(screen_surface) # Fallback if no camera

    if player1_instance and getattr(player1_instance, '_valid_init', False) and player1_instance.alive():
        # print(f"DEBUG UI (draw_scene): P1 is valid and alive for HUD. HP: {player1_instance.current_health}") # DEBUG
        draw_player_hud(screen_surface, 10, 10, player1_instance, 1, font_for_hud)
    # elif player1_instance:
        # print(f"DEBUG UI (draw_scene): P1 instance exists for HUD but is not valid or not alive. Valid: {getattr(player1_instance, '_valid_init', 'N/A')}, Alive: {player1_instance.alive() if hasattr(player1_instance, 'alive') else 'N/A'}") # DEBUG
    # else:
        # print(f"DEBUG UI (draw_scene): P1 instance is None for HUD.") # DEBUG

    
    if player2_instance and getattr(player2_instance, '_valid_init', False) and player2_instance.alive():
        # print(f"DEBUG UI (draw_scene): P2 is valid and alive for HUD. HP: {player2_instance.current_health}") # DEBUG
        p2_hud_estimated_width = getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH',50)*2) + 120 
        p2_hud_pos_x = current_screen_width - p2_hud_estimated_width - 10 
        draw_player_hud(screen_surface, p2_hud_pos_x, 10, player2_instance, 2, font_for_hud)
    # elif player2_instance:
        # print(f"DEBUG UI (draw_scene): P2 instance exists for HUD but is not valid or not alive. Valid: {getattr(player2_instance, '_valid_init', 'N/A')}, Alive: {player2_instance.alive() if hasattr(player2_instance, 'alive') else 'N/A'}") # DEBUG
    # else:
        # print(f"DEBUG UI (draw_scene): P2 instance is None for HUD.") # DEBUG


# --- Main Menu Function ---
def show_main_menu(screen_surface: pygame.Surface, clock_obj: pygame.time.Clock, 
                   fonts: Dict[str, Optional[pygame.font.Font]], 
                   app_status_obj: Any) -> Optional[str]:
    button_standard_width = 350
    button_standard_height = 55
    button_vertical_spacing = 20
    gap_after_title = 60
    
    current_screen_width, current_screen_height = screen_surface.get_size()

    font_title = fonts.get("large")
    if font_title is None : font_title = pygame.font.Font(None, 60) if pygame.font.get_init() else None
    if font_title is None: 
        print("UI Error: Large font for menu title not available.")
        return "quit"
        
    title_text_surface = font_title.render("Platformer Adventure LAN", True, getattr(C, 'WHITE', (255,255,255)))
    
    menu_buttons_definition = {
        "host":       {"text": "Host Game",       "action": "host"},
        "join_lan":   {"text": "Join Game (LAN)", "action": "join_lan"},
        "join_ip":    {"text": "Join by IP",      "action": "join_ip"},
        "couch_play": {"text": "Couch Play",      "action": "couch_play"},
        "quit":       {"text": "Quit Game",       "action": "quit"}
    }
    
    font_button_text = fonts.get("medium")
    if font_button_text is None: font_button_text = pygame.font.Font(None, 30) if pygame.font.get_init() else None
    if font_button_text is None: 
        print("UI Error: Medium font for menu buttons not available.")
        return "quit"

    title_rect_for_display = title_text_surface.get_rect(center=(current_screen_width // 2, current_screen_height // 4))
    
    def update_menu_button_geometries(): # Removed title_rect_for_display from nonlocal as it's recalculated
        nonlocal current_screen_width, current_screen_height # Allow modification
        # title_rect_calculated = title_text_surface.get_rect(center=(current_screen_width // 2, current_screen_height // 4))
        
        num_menu_buttons = len(menu_buttons_definition)
        # total_buttons_block_height = (num_menu_buttons * button_standard_height) + \
        #                              ((num_menu_buttons - 1) * button_vertical_spacing)
        first_button_start_y = title_rect_for_display.bottom + gap_after_title # Use the member title_rect
        
        current_button_y_pos = first_button_start_y
        for _, button_props_dict in menu_buttons_definition.items():
            button_props_dict["rect"] = pygame.Rect(0, 0, button_standard_width, button_standard_height)
            button_props_dict["rect"].centerx = current_screen_width // 2 
            button_props_dict["rect"].top = current_button_y_pos
            button_props_dict["text_surf"] = font_button_text.render(button_props_dict["text"], True, getattr(C, 'WHITE', (255,255,255)))
            button_props_dict["text_rect"] = button_props_dict["text_surf"].get_rect(
                center=button_props_dict["rect"].center
            )
            current_button_y_pos += button_standard_height + button_vertical_spacing 
        # return title_rect_calculated # Not needed to return if modifying global/nonlocal directly

    update_menu_button_geometries() # Initial setup

    selected_menu_action = None 
    while selected_menu_action is None and app_status_obj.app_running:
        mouse_cursor_pos = pygame.mouse.get_pos() 
        
        for event in pygame.event.get(): 
            if event.type == pygame.QUIT:
                app_status_obj.app_running = False 
                selected_menu_action = "quit" 
            if event.type == pygame.VIDEORESIZE: 
                 if not screen_surface.get_flags() & pygame.FULLSCREEN: 
                     try:
                         current_screen_width,current_screen_height=max(320,event.w),max(240,event.h) 
                         screen_surface=pygame.display.set_mode((current_screen_width,current_screen_height), 
                                                                pygame.RESIZABLE|pygame.DOUBLEBUF)
                         # Recalculate title_rect here as screen size changed
                         title_rect_for_display = title_text_surface.get_rect(center=(current_screen_width // 2, current_screen_height // 4))
                         update_menu_button_geometries() 
                     except pygame.error as e: print(f"UI Menu resize error: {e}")
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: 
                    app_status_obj.app_running = False
                    selected_menu_action = "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: 
                for button_props_item in menu_buttons_definition.values():
                    if "rect" in button_props_item and button_props_item["rect"].collidepoint(mouse_cursor_pos):
                        selected_menu_action = button_props_item["action"] 
                        break 
        if not app_status_obj.app_running: break 

        screen_surface.fill(getattr(C, 'BLACK', (0,0,0))) 
        if title_rect_for_display: screen_surface.blit(title_text_surface, title_rect_for_display) 
        
        for button_properties in menu_buttons_definition.values():
            if "rect" in button_properties: # Ensure rect exists
                is_mouse_hovering_button = button_properties["rect"].collidepoint(mouse_cursor_pos)
                button_color_to_draw = getattr(C, 'GREEN', (0,255,0)) if is_mouse_hovering_button else getattr(C, 'BLUE', (0,0,255))
                pygame.draw.rect(screen_surface, button_color_to_draw, button_properties["rect"], border_radius=8)
                if "text_surf" in button_properties and "text_rect" in button_properties:
                    screen_surface.blit(button_properties["text_surf"], button_properties["text_rect"])
        
        pygame.display.flip() 
        clock_obj.tick(30) 
        
    return selected_menu_action


# --- IP Address Input Dialog Function ---
def get_server_ip_input_dialog(screen_surface: pygame.Surface, clock_obj: pygame.time.Clock, 
                               fonts: Dict[str, Optional[pygame.font.Font]], 
                               app_status_obj: Any, 
                               default_input_text: str = "") -> Optional[str]: # Added default_input_text
    """
    Displays a dialog to get server IP address input from the user.
    """
    current_input_text = default_input_text # Use the passed default_input_text
    input_dialog_active = True
    is_cursor_visible = True 
    last_cursor_blink_time = time.time() 
    
    current_screen_width, current_screen_height = screen_surface.get_size()
    # Ensure input_box_rect width is reasonable, at least some minimum
    input_box_width = max(200, current_screen_width // 2)
    input_box_rect = pygame.Rect(0, 0, input_box_width, 50)
    input_box_rect.center = (current_screen_width // 2, current_screen_height // 2)
    
    pygame.key.set_repeat(250, 25) 
    paste_status_message = None 
    paste_message_display_start_time = 0 
    
    check_pygame_scrap_init_status() # Ensure SCRAP_INITIALIZED_UI_MODULE is up-to-date

    font_prompt_text = fonts.get("medium")
    if font_prompt_text is None: font_prompt_text = pygame.font.Font(None, 30) if pygame.font.get_init() else None
    font_info_text = fonts.get("small")
    if font_info_text is None: font_info_text = pygame.font.Font(None, 20) if pygame.font.get_init() else None
    font_input_field_text = fonts.get("medium") # Using medium for input field text
    if font_input_field_text is None: font_input_field_text = pygame.font.Font(None, 30) if pygame.font.get_init() else None

    if not all([font_prompt_text, font_info_text, font_input_field_text]):
        print("UI Error: Essential fonts for IP input dialog not available.")
        pygame.key.set_repeat(0,0) # Reset key repeat
        return None # Cannot render dialog

    while input_dialog_active and app_status_obj.app_running:
        current_loop_time = time.time()
        if current_loop_time - last_cursor_blink_time > 0.5: 
            is_cursor_visible = not is_cursor_visible
            last_cursor_blink_time = current_loop_time
        
        for event in pygame.event.get(): 
            if event.type == pygame.QUIT:
                app_status_obj.app_running = False; input_dialog_active = False; current_input_text = None
            if event.type == pygame.VIDEORESIZE: 
                 if not screen_surface.get_flags() & pygame.FULLSCREEN:
                     try:
                         current_screen_width,current_screen_height=max(320,event.w),max(240,event.h)
                         screen_surface=pygame.display.set_mode((current_screen_width,current_screen_height),
                                                                pygame.RESIZABLE|pygame.DOUBLEBUF)
                         input_box_width = max(200, current_screen_width // 2)
                         input_box_rect = pygame.Rect(0,0, input_box_width, 50)
                         input_box_rect.center = (current_screen_width // 2, current_screen_height // 2)
                     except pygame.error as e: print(f"UI IP Input Dialog resize error: {e}")
            if event.type == pygame.KEYDOWN:
                paste_status_message = None 
                if event.key == pygame.K_ESCAPE: 
                    input_dialog_active = False; current_input_text = None 
                elif event.key == pygame.K_RETURN: 
                    input_dialog_active = False 
                elif event.key == pygame.K_BACKSPACE: 
                    current_input_text = current_input_text[:-1]
                elif event.key == pygame.K_v and \
                     (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META): # Ctrl+V or Cmd+V
                    
                    pasted_text_content = ""
                    paste_method_attempted = "None"
                    try:
                        if SCRAP_INITIALIZED_UI_MODULE:
                            clipboard_data_bytes = pygame.scrap.get(pygame.SCRAP_TEXT) 
                            if clipboard_data_bytes: # Ensure it's not None
                                pasted_text_content = clipboard_data_bytes.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                            if pasted_text_content: paste_method_attempted = "pygame.scrap"
                        
                        if not pasted_text_content and PYPERCLIP_AVAILABLE_UI_MODULE:
                            clipboard_data_str = pyperclip.paste()
                            if isinstance(clipboard_data_str, str):
                                pasted_text_content = clipboard_data_str.replace('\x00', '').strip()
                            if pasted_text_content: paste_method_attempted = "pyperclip"
                    except Exception as e_paste_error:
                        print(f"UI Paste error (Method: {paste_method_attempted}): {e_paste_error}")

                    if pasted_text_content: current_input_text += pasted_text_content 
                    else: 
                        paste_status_message = "Paste Failed or Clipboard Empty"
                        paste_message_display_start_time = current_loop_time
                # Allow letters, numbers, '.', ':', '-' for IP/Port and hostnames
                elif event.unicode.isprintable() and \
                     (event.unicode.isalnum() or event.unicode in ['.', ':', '-']): 
                    current_input_text += event.unicode 
        
        if not app_status_obj.app_running: break 

        screen_surface.fill(getattr(C, 'BLACK', (0,0,0))) 
        
        prompt_text_surface = font_prompt_text.render("Enter Host IP Address or IP:Port", True, getattr(C, 'WHITE', (255,255,255)))
        screen_surface.blit(prompt_text_surface, prompt_text_surface.get_rect(
            center=(current_screen_width // 2, current_screen_height // 2 - 60))
        )
        
        info_text_surface = font_info_text.render("(Enter=Confirm, Esc=Cancel, Ctrl+V=Paste)", True, getattr(C, 'GRAY', (128,128,128)))
        screen_surface.blit(info_text_surface, info_text_surface.get_rect(
            center=(current_screen_width // 2, current_screen_height - 40))
        )

        pygame.draw.rect(screen_surface, getattr(C, 'GRAY', (128,128,128)), input_box_rect, border_radius=5) 
        pygame.draw.rect(screen_surface, getattr(C, 'WHITE', (255,255,255)), input_box_rect, 2, border_radius=5) 

        input_text_surface = font_input_field_text.render(current_input_text, True, getattr(C, 'BLACK', (0,0,0))) 
        input_text_rect_render = input_text_surface.get_rect(
            midleft=(input_box_rect.left + 10, input_box_rect.centery) 
        )
        
        # Clipping logic for text input field
        input_box_clipping_area = input_box_rect.inflate(-12, -12) # Small padding
        if input_text_rect_render.width > input_box_clipping_area.width: 
            input_text_rect_render.right = input_box_clipping_area.right # Scroll text left
        else: 
            input_text_rect_render.left = input_box_clipping_area.left # Align left if fits

        screen_surface.set_clip(input_box_clipping_area)
        screen_surface.blit(input_text_surface, input_text_rect_render)
        screen_surface.set_clip(None) # Reset clipping area

        # Draw cursor
        if is_cursor_visible:
            cursor_pos_x = input_text_rect_render.right + 2 # Position cursor after text
            # Ensure cursor stays within the visible input box area
            cursor_pos_x = max(input_box_clipping_area.left, 
                               min(cursor_pos_x, input_box_clipping_area.right - 1))
            pygame.draw.line(screen_surface, getattr(C, 'BLACK', (0,0,0)), 
                             (cursor_pos_x, input_box_rect.top + 5), 
                             (cursor_pos_x, input_box_rect.bottom - 5), 2) 
        
        # Display paste status message if any
        if paste_status_message and current_loop_time - paste_message_display_start_time < 2.0:
            paste_message_surf = font_info_text.render(paste_status_message, True, getattr(C, 'RED', (255,0,0)))
            screen_surface.blit(paste_message_surf, paste_message_surf.get_rect(
                center=(current_screen_width//2, input_box_rect.bottom + 30))
            )
        elif paste_status_message: # Clear message after timeout
            paste_status_message = None 
            
        pygame.display.flip() 
        clock_obj.tick(30) # Lower FPS for UI dialogs is fine
        
    pygame.key.set_repeat(0,0) # Disable key repeat when dialog closes
    
    return current_input_text.strip() if current_input_text is not None else None
########## END OF FILE: game_ui.py ##########