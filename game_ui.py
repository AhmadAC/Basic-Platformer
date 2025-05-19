########## START OF FILE: game_ui.py ##########
# game_ui.py
# -*- coding: utf-8 -*-
## version 1.0.0.15 (Align with Mapper utility for MENU_CONFIRM/CANCEL keys)
## version 1.0.0.16 (Hide level_default from map selection dialog)
"""
Functions for drawing User Interface elements like health bars, player HUDs,
main menus, input dialogs, and the main game scene.
"""
import pygame
import time
import os
import constants as C # For game-wide color constants
from typing import Dict, Optional, Any, List
import joystick_handler # Import joystick_handler
import config as game_config # For default joystick mappings for menu AND AXIS_THRESHOLD_DEFAULT

PYPERCLIP_AVAILABLE_UI_MODULE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_UI_MODULE = True
except ImportError:
    pass

SCRAP_INITIALIZED_UI_MODULE = False

def check_pygame_scrap_init_status():
    global SCRAP_INITIALIZED_UI_MODULE
    try:
        if pygame.scrap.get_init(): SCRAP_INITIALIZED_UI_MODULE = True
        else: SCRAP_INITIALIZED_UI_MODULE = False
    except (AttributeError, pygame.error): SCRAP_INITIALIZED_UI_MODULE = False
    return SCRAP_INITIALIZED_UI_MODULE

def draw_health_bar(surface: pygame.Surface, x: int, y: int,
                    width: int, height: int,
                    current_hp: float, max_hp: float):
    if max_hp <= 0: return
    current_hp_clamped = max(0, min(current_hp, max_hp))
    bar_width = max(1, int(width)); bar_height = max(1, int(height))
    health_ratio = current_hp_clamped / max_hp
    color_red = getattr(C, 'RED', (255,0,0)); color_green = getattr(C, 'GREEN', (0,255,0))
    color_dark_gray = getattr(C, 'DARK_GRAY', (50,50,50)); color_black = getattr(C, 'BLACK', (0,0,0))
    try: health_color = pygame.Color(color_red).lerp(pygame.Color(color_green), health_ratio)
    except AttributeError:
        r = int(color_red[0] * (1 - health_ratio) + color_green[0] * health_ratio)
        g = int(color_red[1] * (1 - health_ratio) + color_green[1] * health_ratio)
        b = int(color_red[2] * (1 - health_ratio) + color_green[2] * health_ratio)
        health_color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    background_rect = pygame.Rect(x, y, bar_width, bar_height)
    pygame.draw.rect(surface, color_dark_gray, background_rect)
    health_fill_width = int(bar_width * health_ratio)
    if health_fill_width > 0: pygame.draw.rect(surface, health_color, pygame.Rect(x, y, health_fill_width, bar_height))
    pygame.draw.rect(surface, color_black, background_rect, 1)

def draw_player_hud(surface: pygame.Surface, x: int, y: int, player_instance: Any,
                    player_number: int, hud_font_obj: Optional[pygame.font.Font]):
    if not player_instance or not hasattr(player_instance, 'current_health') or not hasattr(player_instance, 'max_health'): return
    player_label_text = f"P{player_number}"; label_height_offset = 0; color_white = getattr(C, 'WHITE', (255,255,255))
    if hud_font_obj:
        try:
            label_surface = hud_font_obj.render(player_label_text, True, color_white)
            surface.blit(label_surface, (x, y)); label_height_offset = label_surface.get_height()
        except Exception: label_height_offset = getattr(hud_font_obj, 'get_height', lambda: 20)() # type: ignore
    health_bar_pos_x = x; health_bar_pos_y = y + label_height_offset + 5
    hud_health_bar_width = getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH', 50) * 2)
    hud_health_bar_height = getattr(C, 'HUD_HEALTH_BAR_HEIGHT', getattr(C, 'HEALTH_BAR_HEIGHT', 8) + 4)
    draw_health_bar(surface, health_bar_pos_x, health_bar_pos_y, hud_health_bar_width, hud_health_bar_height,
                    player_instance.current_health, player_instance.max_health)
    if hud_font_obj:
        try:
            health_value_text = f"{int(player_instance.current_health)}/{int(player_instance.max_health)}"
            health_text_surface = hud_font_obj.render(health_value_text, True, color_white)
            health_text_pos_x = health_bar_pos_x + hud_health_bar_width + 10
            health_text_pos_y = health_bar_pos_y + (hud_health_bar_height - health_text_surface.get_height()) // 2
            surface.blit(health_text_surface, (health_text_pos_x, health_text_pos_y))
        except Exception: pass

def draw_platformer_scene_on_surface(screen_surface: pygame.Surface, game_elements: Dict[str, Any],
                                     fonts: Dict[str, Optional[pygame.font.Font]], current_game_time_ticks: int,
                                     download_status_message: Optional[str] = None,
                                     download_progress_percent: Optional[float] = None):
    camera_instance = game_elements.get("camera"); all_sprites_group = game_elements.get("all_sprites")
    enemy_list_for_health_bars = game_elements.get("enemy_list", [])
    player1_instance, player2_instance = game_elements.get("player1"), game_elements.get("player2")
    font_for_hud = fonts.get("medium") or (pygame.font.Font(None, 24) if pygame.font.get_init() else None)
    current_screen_width, current_screen_height = screen_surface.get_size(); bg_color = getattr(C, 'LIGHT_BLUE', (135, 206, 235))
    level_bg_color = game_elements.get("level_background_color", bg_color)
    screen_surface.fill(level_bg_color)
    if camera_instance and all_sprites_group:
        for entity_sprite in all_sprites_group:
            if entity_sprite.alive() and hasattr(entity_sprite, 'image') and hasattr(entity_sprite, 'rect'):
                 screen_surface.blit(entity_sprite.image, camera_instance.apply(entity_sprite.rect))
        for enemy_sprite in enemy_list_for_health_bars:
            if enemy_sprite.alive() and getattr(enemy_sprite, '_valid_init', False) and not \
               (getattr(enemy_sprite, 'is_dead', False) and getattr(enemy_sprite, 'death_animation_finished', False)) and \
               hasattr(enemy_sprite, 'current_health') and hasattr(enemy_sprite, 'max_health') and not getattr(enemy_sprite, 'is_petrified', False):
                enemy_rect_on_screen = camera_instance.apply(enemy_sprite.rect)
                hb_w, hb_h = getattr(C, 'HEALTH_BAR_WIDTH', 50), getattr(C, 'HEALTH_BAR_HEIGHT', 8)
                hb_x, hb_y = enemy_rect_on_screen.centerx - hb_w // 2, enemy_rect_on_screen.top - hb_h - getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5)
                draw_health_bar(screen_surface, hb_x, hb_y, hb_w, hb_h, enemy_sprite.current_health, enemy_sprite.max_health)
    elif all_sprites_group: all_sprites_group.draw(screen_surface)

    if player1_instance and getattr(player1_instance, '_valid_init', False) and player1_instance.alive() and not getattr(player1_instance, 'is_petrified', False):
        draw_player_hud(screen_surface, 10, 10, player1_instance, 1, font_for_hud)
    if player2_instance and getattr(player2_instance, '_valid_init', False) and player2_instance.alive() and not getattr(player2_instance, 'is_petrified', False):
        p2_hud_w = getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH',50)*2) + 120
        draw_player_hud(screen_surface, current_screen_width - p2_hud_w - 10, 10, player2_instance, 2, font_for_hud)

    if download_status_message and font_for_hud:
        dialog_rect = pygame.Rect(0, 0, current_screen_width * 0.6, current_screen_height * 0.3)
        dialog_rect.center = (current_screen_width // 2, current_screen_height // 2)
        pygame.draw.rect(screen_surface, C.DARK_GRAY, dialog_rect, border_radius=10)
        pygame.draw.rect(screen_surface, C.WHITE, dialog_rect, 2, border_radius=10)
        status_surf = font_for_hud.render(download_status_message, True, C.WHITE)
        status_rect = status_surf.get_rect(centerx=dialog_rect.centerx, top=dialog_rect.top + 20)
        screen_surface.blit(status_surf, status_rect)
        if download_progress_percent is not None and download_progress_percent >= 0:
            bar_width = dialog_rect.width * 0.8; bar_height = 30
            bar_x = dialog_rect.centerx - bar_width / 2; bar_y = status_rect.bottom + 20
            pygame.draw.rect(screen_surface, C.GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
            fill_width = (download_progress_percent / 100) * bar_width
            pygame.draw.rect(screen_surface, C.GREEN, (bar_x, bar_y, fill_width, bar_height), border_radius=5)
            pygame.draw.rect(screen_surface, C.WHITE, (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)
            progress_text = f"{download_progress_percent:.1f}%"
            font_small = fonts.get("small") or pygame.font.Font(None, 24)
            if font_small:
                text_surf_prog = font_small.render(progress_text, True, C.BLACK)
                text_rect_prog = text_surf_prog.get_rect(center=(bar_x + bar_width / 2, bar_y + bar_height / 2))
                screen_surface.blit(text_surf_prog, text_rect_prog)

def show_main_menu(screen_surface: pygame.Surface, clock_obj: pygame.time.Clock,
                   fonts: Dict[str, Optional[pygame.font.Font]], app_status_obj: Any) -> Optional[str]:
    button_w, button_h, spacing, title_gap = 350, 55, 15, 50
    current_w, current_h = screen_surface.get_size()
    font_title = fonts.get("large") or (pygame.font.Font(None, 60) if pygame.font.get_init() else None)
    if not font_title: return "quit"
    title_surf = pygame.Surface((0,0)) # Placeholder, not used for rendering directly
    title_rect = title_surf.get_rect(center=(current_w // 2, current_h // 5)) # Used for y-pos calculation

    menu_buttons = {
        "host": {"text": "Host Game", "action": "host"},
        "join_lan": {"text": "Join LAN", "action": "join_lan"},
        "join_ip": {"text": "Join by IP", "action": "join_ip"},
        "couch_play": {"text": "Couch Play", "action": "couch_play"},
        "quit": {"text": "Quit", "action": "quit"}
    }
    button_order = ["host", "join_lan", "join_ip", "couch_play", "quit"]
    selected_button_index = 0

    font_button = fonts.get("medium") or (pygame.font.Font(None, 30) if pygame.font.get_init() else None)
    if not font_button: return "quit"

    color_bg = getattr(C, 'BLACK', (0,0,0))
    color_text_normal = getattr(C, 'WHITE', (255,255,255))
    color_text_selected = getattr(C, 'YELLOW', (255,255,0))
    color_button_normal_bg = getattr(C, 'BLUE', (0,0,255))
    color_button_hover_bg = getattr(C, 'GREEN', (0,255,0))
    color_button_selected_bg = getattr(C, 'DARK_GREEN', (0,100,0))
    color_button_selected_hover_bg = pygame.Color(color_button_selected_bg).lerp(pygame.Color(color_button_hover_bg), 0.5) # type: ignore

    joystick_menu_nav_instance = None
    active_joystick_map_for_menu = game_config.DEFAULT_JOYSTICK_FALLBACK_MAPPINGS
    p1_device = game_config.CURRENT_P1_INPUT_DEVICE

    if p1_device.startswith("joystick_"):
        try:
            p1_joy_id = int(p1_device.split("_")[-1])
            if 0 <= p1_joy_id < joystick_handler.get_joystick_count():
                joystick_menu_nav_instance = joystick_handler.get_joystick_instance(p1_joy_id)
                active_joystick_map_for_menu = game_config.P1_MAPPINGS
        except (ValueError, IndexError): pass

    if not joystick_menu_nav_instance and joystick_handler.get_joystick_count() > 0:
        joystick_menu_nav_instance = joystick_handler.get_joystick_instance(0)
        if game_config.CURRENT_P1_INPUT_DEVICE == "joystick_0" and active_joystick_map_for_menu is not game_config.P1_MAPPINGS:
             active_joystick_map_for_menu = game_config.P1_MAPPINGS
        elif game_config.CURRENT_P2_INPUT_DEVICE == "joystick_0":
             active_joystick_map_for_menu = game_config.P2_MAPPINGS

    if joystick_menu_nav_instance:
        map_name = "Fallback"
        if active_joystick_map_for_menu is game_config.P1_MAPPINGS: map_name = "P1"
        elif active_joystick_map_for_menu is game_config.P2_MAPPINGS: map_name = "P2"
        print(f"GAME_UI: Main menu using joystick: {joystick_menu_nav_instance.get_name()} with map: {map_name}")
    else: print(f"GAME_UI: No joystick active for main menu navigation.")


    JOY_NAV_COOLDOWN_MS = 200
    last_joy_nav_time = 0
    axis_y_was_active_negative = False
    axis_y_was_active_positive = False
    buttons_top_margin = current_h * 0.15 # Recalculate based on current height

    def update_btn_geo():
        nonlocal buttons_top_margin # Ensure we are using the potentially updated current_h
        current_w_local, current_h_local = screen_surface.get_size()
        buttons_top_margin = current_h_local * 0.25 # Adjusted for better centering with title
        
        # Dynamic Title
        title_text = "Platformer Adventure LAN"
        dynamic_title_surf = font_title.render(title_text, True, color_text_normal) # type: ignore
        dynamic_title_rect = dynamic_title_surf.get_rect(center=(current_w_local // 2, current_h_local * 0.1))
        
        btn_y = dynamic_title_rect.bottom + title_gap # Start buttons below title

        for key_ordered in button_order:
            props = menu_buttons[key_ordered]
            props["rect"] = pygame.Rect(0, 0, button_w, button_h)
            props["rect"].centerx = current_w_local // 2
            props["rect"].top = btn_y
            props["text_surf"] = font_button.render(props["text"], True, color_text_normal) # type: ignore
            props["text_rect"] = props["text_surf"].get_rect(center=props["rect"].center)
            btn_y += button_h + spacing
    update_btn_geo()

    selected_action = None
    while selected_action is None and app_status_obj.app_running:
        mouse_pos = pygame.mouse.get_pos()
        current_time_ms_menu = pygame.time.get_ticks()
        can_trigger_new_joy_nav = (current_time_ms_menu - last_joy_nav_time > JOY_NAV_COOLDOWN_MS)
        
        current_w, current_h = screen_surface.get_size() # Get current size for rendering

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_status_obj.app_running = False; selected_action = "quit"
            if event.type == pygame.VIDEORESIZE and not (screen_surface.get_flags() & pygame.FULLSCREEN):
                try:
                    # current_w and current_h are updated from screen_surface.get_size() at start of loop
                    screen_surface = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    update_btn_geo() # Recalculate button positions based on new size
                except pygame.error as e: print(f"Menu resize error: {e}")

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_status_obj.app_running = False; selected_action = "quit"
                elif event.key == pygame.K_UP:
                    selected_button_index = (selected_button_index - 1 + len(button_order)) % len(button_order)
                elif event.key == pygame.K_DOWN:
                    selected_button_index = (selected_button_index + 1) % len(button_order)
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    selected_action = menu_buttons[button_order[selected_button_index]]["action"]

            if joystick_menu_nav_instance and hasattr(event, 'joy') and event.joy == joystick_menu_nav_instance.get_id():
                confirm_mapping = active_joystick_map_for_menu.get("menu_confirm", {})
                cancel_mapping = active_joystick_map_for_menu.get("menu_cancel", {})

                is_confirm_from_config = confirm_mapping.get("type") == "button"
                effective_confirm_button_id = confirm_mapping.get("id") if is_confirm_from_config else 1 

                is_cancel_from_config = cancel_mapping.get("type") == "button"
                effective_cancel_button_id = cancel_mapping.get("id") if is_cancel_from_config else 2 

                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == effective_confirm_button_id:
                        selected_action = menu_buttons[button_order[selected_button_index]]["action"]
                        source_confirm = "config (menu_confirm)" if is_confirm_from_config else "default (A=1)"
                        print(f"GAME_UI: MainMenu Joystick Confirm (Button {event.button}, effective: {effective_confirm_button_id}, source: {source_confirm}) -> Action: {selected_action}")
                    elif event.button == effective_cancel_button_id:
                        selected_action = "quit"
                        source_cancel = "config (menu_cancel)" if is_cancel_from_config else "default (Y=2)"
                        print(f"GAME_UI: MainMenu Joystick Cancel (Button {event.button}, effective: {effective_cancel_button_id}, source: {source_cancel}) -> Quitting")

                if event.type == pygame.JOYHATMOTION:
                    menu_up_hat_cfg = active_joystick_map_for_menu.get("menu_up", {})
                    menu_down_hat_cfg = active_joystick_map_for_menu.get("menu_down", {})

                    if event.hat == menu_up_hat_cfg.get("id", 0) and can_trigger_new_joy_nav: 
                        hat_y_val = event.value[1]
                        expected_up_val = menu_up_hat_cfg.get("value", (0,0))[1] 
                        expected_down_val = menu_down_hat_cfg.get("value", (0,0))[1]

                        if hat_y_val == expected_up_val and expected_up_val != 0:
                            selected_button_index = (selected_button_index - 1 + len(button_order)) % len(button_order)
                            last_joy_nav_time = current_time_ms_menu
                        elif hat_y_val == expected_down_val and expected_down_val != 0 : 
                            selected_button_index = (selected_button_index + 1) % len(button_order)
                            last_joy_nav_time = current_time_ms_menu
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, key_ordered_mouse in enumerate(button_order):
                    props_mouse = menu_buttons[key_ordered_mouse]
                    if "rect" in props_mouse and props_mouse["rect"].collidepoint(mouse_pos):
                        selected_button_index = i; selected_action = props_mouse["action"]; break

        if joystick_menu_nav_instance:
            menu_nav_axis_cfg_up = active_joystick_map_for_menu.get("up", active_joystick_map_for_menu.get("menu_up",{}))
            menu_nav_axis_id = menu_nav_axis_cfg_up.get("id", active_joystick_map_for_menu.get("up", {}).get("id", 1) )
            menu_nav_axis_threshold = menu_nav_axis_cfg_up.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
            menu_nav_axis_up_val = menu_nav_axis_cfg_up.get("value", -1)
            menu_nav_axis_cfg_down = active_joystick_map_for_menu.get("down", active_joystick_map_for_menu.get("menu_down",{}))
            menu_nav_axis_down_val = menu_nav_axis_cfg_down.get("value", 1)
            if menu_nav_axis_id != -1 and 0 <= menu_nav_axis_id < joystick_menu_nav_instance.get_numaxes():
                current_axis_y_val = joystick_menu_nav_instance.get_axis(menu_nav_axis_id)
                if (menu_nav_axis_up_val < 0 and current_axis_y_val < -menu_nav_axis_threshold) or \
                   (menu_nav_axis_up_val > 0 and current_axis_y_val > menu_nav_axis_threshold and menu_nav_axis_up_val != 0):
                    if not axis_y_was_active_negative and can_trigger_new_joy_nav:
                        selected_button_index = (selected_button_index - 1 + len(button_order)) % len(button_order)
                        last_joy_nav_time = current_time_ms_menu
                    axis_y_was_active_negative = True
                else: axis_y_was_active_negative = False
                if (menu_nav_axis_down_val > 0 and current_axis_y_val > menu_nav_axis_threshold) or \
                   (menu_nav_axis_down_val < 0 and current_axis_y_val < -menu_nav_axis_threshold and menu_nav_axis_down_val != 0):
                    if not axis_y_was_active_positive and can_trigger_new_joy_nav:
                        selected_button_index = (selected_button_index + 1) % len(button_order)
                        last_joy_nav_time = current_time_ms_menu
                    axis_y_was_active_positive = True
                else: axis_y_was_active_positive = False
            else: axis_y_was_active_negative = False; axis_y_was_active_positive = False

        if not app_status_obj.app_running: break
        screen_surface.fill(color_bg)
        
        # Render Title
        title_text_render = "Platformer Adventure LAN" # Keep title static or fetch dynamically
        rendered_title_surf = font_title.render(title_text_render, True, color_text_normal) # type: ignore
        rendered_title_rect = rendered_title_surf.get_rect(center=(current_w // 2, current_h * 0.1))
        screen_surface.blit(rendered_title_surf, rendered_title_rect)

        for i, key_ordered_draw in enumerate(button_order):
            props_draw = menu_buttons[key_ordered_draw]
            if "rect" in props_draw:
                is_hovered_by_mouse_draw = props_draw["rect"].collidepoint(mouse_pos)
                is_selected_by_nav_draw = (i == selected_button_index)
                current_bg_draw = color_button_normal_bg; current_txt_col_draw = color_text_normal
                if is_selected_by_nav_draw:
                    current_txt_col_draw = color_text_selected
                    current_bg_draw = color_button_selected_hover_bg if is_hovered_by_mouse_draw else color_button_selected_bg # type: ignore
                elif is_hovered_by_mouse_draw: current_bg_draw = color_button_hover_bg
                pygame.draw.rect(screen_surface, current_bg_draw, props_draw["rect"], border_radius=8)
                final_text_surf_draw = font_button.render(props_draw["text"], True, current_txt_col_draw) # type: ignore
                final_text_rect_draw = final_text_surf_draw.get_rect(center=props_draw["rect"].center)
                screen_surface.blit(final_text_surf_draw, final_text_rect_draw)
        pygame.display.flip()
        clock_obj.tick(30)
    return selected_action

MAPS_DIRECTORY_GAME_UI = getattr(C, "MAPS_DIR", "maps")
if not MAPS_DIRECTORY_GAME_UI:
    MAPS_DIRECTORY_GAME_UI = "maps"
    print(f"GAME_UI Warning: MAPS_DIRECTORY_GAME_UI was initially None, defaulted to '{MAPS_DIRECTORY_GAME_UI}'")

def select_map_dialog(screen: pygame.Surface, clock_obj: pygame.time.Clock,
                      fonts: Dict[str, Optional[pygame.font.Font]],
                      app_status: Any) -> Optional[str]:
    print("GAME_UI: Opening select_map_dialog...")
    map_module_names_unfiltered: List[str] = []
    global MAPS_DIRECTORY_GAME_UI
    if os.path.exists(MAPS_DIRECTORY_GAME_UI) and os.path.isdir(MAPS_DIRECTORY_GAME_UI):
        try:
            for f_name in os.listdir(MAPS_DIRECTORY_GAME_UI):
                if f_name.endswith(".py") and f_name != "__init__.py":
                    map_module_names_unfiltered.append(f_name[:-3])
            # Filter out 'level_default'
            map_module_names = [m for m in map_module_names_unfiltered if m != "level_default"]
            map_module_names.sort()
            print(f"GAME_UI: Found selectable maps: {map_module_names}")
        except OSError as e: print(f"GAME_UI Error: Could not read maps directory '{MAPS_DIRECTORY_GAME_UI}': {e}"); map_module_names = []
    else: print(f"GAME_UI Warning: Maps directory '{MAPS_DIRECTORY_GAME_UI}' not found."); map_module_names = []

    if not map_module_names:
        font_medium = fonts.get("medium") or (pygame.font.Font(None, 36) if pygame.font.get_init() else None)
        if font_medium:
            screen_w, screen_h = screen.get_size(); screen.fill(getattr(C, 'BLACK', (0,0,0)))
            msg_surf = font_medium.render(f"No Selectable Maps Found in '{os.path.basename(MAPS_DIRECTORY_GAME_UI)}/' folder.", True, getattr(C, 'RED', (255,0,0)))
            screen.blit(msg_surf, msg_surf.get_rect(center=(screen_w//2, screen_h//2)))
            pygame.display.flip(); pygame.time.wait(2500)
        return None

    selected_index = 0; dialog_active = True
    font_title = fonts.get("large"); font_item = fonts.get("medium"); font_instr = fonts.get("small")
    if not all([font_title, font_item, font_instr]): return map_module_names[0] if map_module_names else None

    maps_per_page = 8; current_page = 0; max_pages = (len(map_module_names) + maps_per_page - 1) // maps_per_page
    button_height = 45; button_spacing = 10; button_width_factor = 0.6
    color_white = getattr(C, 'WHITE', (255,255,255)); color_black = getattr(C, 'BLACK', (0,0,0))
    color_gray = getattr(C, 'GRAY', (128,128,128)); color_button_normal_bg = getattr(C, 'BLUE', (0,0,255))
    color_button_hover_bg = getattr(C, 'GREEN', (0,255,0)); color_button_selected_bg = getattr(C, 'DARK_GREEN', (0,100,0))
    color_button_selected_hover_bg = pygame.Color(color_button_selected_bg).lerp(pygame.Color(color_button_hover_bg), 0.5) # type: ignore
    color_text_normal = color_white; color_text_selected = getattr(C, 'YELLOW', (255,255,0))

    joy_map_dialog_instance = None
    active_joy_map_for_map_dialog = game_config.DEFAULT_JOYSTICK_FALLBACK_MAPPINGS
    p1_dev_map_dialog = game_config.CURRENT_P1_INPUT_DEVICE
    if p1_dev_map_dialog.startswith("joystick_"):
        try:
            p1_joy_id_map = int(p1_dev_map_dialog.split("_")[-1])
            if 0 <= p1_joy_id_map < joystick_handler.get_joystick_count():
                joy_map_dialog_instance = joystick_handler.get_joystick_instance(p1_joy_id_map)
                active_joy_map_for_map_dialog = game_config.P1_MAPPINGS
        except: pass
    if not joy_map_dialog_instance and joystick_handler.get_joystick_count() > 0:
        joy_map_dialog_instance = joystick_handler.get_joystick_instance(0)
        if game_config.CURRENT_P1_INPUT_DEVICE == "joystick_0" and active_joy_map_for_map_dialog is not game_config.P1_MAPPINGS:
             active_joy_map_for_map_dialog = game_config.P1_MAPPINGS
        elif game_config.CURRENT_P2_INPUT_DEVICE == "joystick_0":
             active_joy_map_for_map_dialog = game_config.P2_MAPPINGS

    if joy_map_dialog_instance:
        map_name_dialog = "Fallback"
        if active_joy_map_for_map_dialog is game_config.P1_MAPPINGS: map_name_dialog = "P1"
        elif active_joy_map_for_map_dialog is game_config.P2_MAPPINGS: map_name_dialog = "P2"
        print(f"GAME_UI: Map select dialog using joystick: {joy_map_dialog_instance.get_name()} with map: {map_name_dialog}")


    joy_nav_cooldown_map_dialog = 200
    last_joy_nav_time_map_dialog = 0
    axis_y_was_active_neg_map_dialog = False
    axis_y_was_active_pos_map_dialog = False

    while dialog_active and app_status.app_running:
        screen_w, screen_h = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()
        frame_title_surf = font_title.render("Select a Map", True, color_white) # type: ignore
        frame_title_rect = frame_title_surf.get_rect(center=(screen_w // 2, screen_h * 0.15))
        current_time_map_dialog = pygame.time.get_ticks()
        can_trigger_joy_nav_map_dialog = (current_time_map_dialog - last_joy_nav_time_map_dialog > joy_nav_cooldown_map_dialog)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_status.app_running = False; dialog_active = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: dialog_active = False; return None
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if 0 <= selected_index < len(map_module_names): return map_module_names[selected_index]
                elif event.key == pygame.K_UP:
                    selected_index=(selected_index - 1 + len(map_module_names)) % len(map_module_names); current_page = selected_index // maps_per_page
                elif event.key == pygame.K_DOWN:
                    selected_index=(selected_index + 1) % len(map_module_names); current_page = selected_index // maps_per_page
                elif event.key == pygame.K_PAGEUP or (event.key == pygame.K_LEFT and max_pages > 1) :
                    current_page = max(0, current_page - 1); selected_index = current_page * maps_per_page
                elif event.key == pygame.K_PAGEDOWN or (event.key == pygame.K_RIGHT and max_pages > 1):
                    current_page = min(max_pages - 1, current_page + 1); selected_index = current_page * maps_per_page

            if joy_map_dialog_instance and hasattr(event, 'joy') and event.joy == joy_map_dialog_instance.get_id():
                confirm_mapping_dialog = active_joy_map_for_map_dialog.get("menu_confirm", {})
                cancel_mapping_dialog = active_joy_map_for_map_dialog.get("menu_cancel", {})

                is_confirm_from_config_dialog = confirm_mapping_dialog.get("type") == "button"
                effective_confirm_btn_id = confirm_mapping_dialog.get("id") if is_confirm_from_config_dialog else 1 

                is_cancel_from_config_dialog = cancel_mapping_dialog.get("type") == "button"
                effective_cancel_btn_id = cancel_mapping_dialog.get("id") if is_cancel_from_config_dialog else 2 

                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == effective_confirm_btn_id:
                        if 0 <= selected_index < len(map_module_names):
                            source_confirm = "config (menu_confirm)" if is_confirm_from_config_dialog else "default (A=1)"
                            print(f"GAME_UI: MapSelect Joystick Confirm (Button {event.button}, effective: {effective_confirm_btn_id}, source: {source_confirm})")
                            return map_module_names[selected_index]
                    elif event.button == effective_cancel_btn_id:
                        source_cancel = "config (menu_cancel)" if is_cancel_from_config_dialog else "default (Y=2)"
                        print(f"GAME_UI: MapSelect Joystick Cancel (Button {event.button}, effective: {effective_cancel_btn_id}, source: {source_cancel})")
                        dialog_active = False; return None

                if event.type == pygame.JOYHATMOTION: 
                    menu_up_hat_cfg_dialog = active_joy_map_for_map_dialog.get("menu_up", {})
                    menu_down_hat_cfg_dialog = active_joy_map_for_map_dialog.get("menu_down", {})
                    if event.hat == menu_up_hat_cfg_dialog.get("id",0) and can_trigger_joy_nav_map_dialog:
                        hat_y = event.value[1]
                        expected_up = menu_up_hat_cfg_dialog.get("value",(0,0))[1]
                        expected_down = menu_down_hat_cfg_dialog.get("value",(0,0))[1]
                        if hat_y == expected_up and expected_up !=0:
                            selected_index=(selected_index - 1 + len(map_module_names)) % len(map_module_names); current_page = selected_index // maps_per_page
                            last_joy_nav_time_map_dialog = current_time_map_dialog
                        elif hat_y == expected_down and expected_down != 0:
                            selected_index=(selected_index + 1) % len(map_module_names); current_page = selected_index // maps_per_page
                            last_joy_nav_time_map_dialog = current_time_map_dialog

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                _start_idx_click = current_page * maps_per_page; _end_idx_click = min(_start_idx_click + maps_per_page, len(map_module_names))
                _visible_maps_on_page_click = map_module_names[_start_idx_click:_end_idx_click]
                _current_btn_y_click = frame_title_rect.bottom + 60
                for i, map_name_item in enumerate(_visible_maps_on_page_click):
                    item_rect_click = pygame.Rect(0, 0, screen_w * button_width_factor, button_height)
                    item_rect_click.centerx = screen_w // 2; item_rect_click.top = _current_btn_y_click
                    if item_rect_click.collidepoint(mouse_pos): selected_index = _start_idx_click + i; return map_name_item
                    _current_btn_y_click += button_height + button_spacing

        if joy_map_dialog_instance: 
            axis_cfg_up = active_joy_map_for_map_dialog.get("up", active_joy_map_for_map_dialog.get("menu_up",{}))
            axis_id = axis_cfg_up.get("id", 1)
            axis_thresh = axis_cfg_up.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
            axis_up_val_expected = axis_cfg_up.get("value", -1)
            axis_cfg_down = active_joy_map_for_map_dialog.get("down", active_joy_map_for_map_dialog.get("menu_down",{}))
            axis_down_val_expected = axis_cfg_down.get("value", 1)

            if 0 <= axis_id < joy_map_dialog_instance.get_numaxes():
                current_axis_val = joy_map_dialog_instance.get_axis(axis_id)
                if (axis_up_val_expected < 0 and current_axis_val < -axis_thresh) or \
                   (axis_up_val_expected > 0 and current_axis_val > axis_thresh and axis_up_val_expected !=0):
                    if not axis_y_was_active_neg_map_dialog and can_trigger_joy_nav_map_dialog:
                        selected_index=(selected_index - 1 + len(map_module_names)) % len(map_module_names); current_page = selected_index // maps_per_page
                        last_joy_nav_time_map_dialog = current_time_map_dialog
                    axis_y_was_active_neg_map_dialog = True
                else: axis_y_was_active_neg_map_dialog = False
                if (axis_down_val_expected > 0 and current_axis_val > axis_thresh) or \
                   (axis_down_val_expected < 0 and current_axis_val < -axis_thresh and axis_down_val_expected != 0):
                    if not axis_y_was_active_pos_map_dialog and can_trigger_joy_nav_map_dialog:
                        selected_index=(selected_index + 1) % len(map_module_names); current_page = selected_index // maps_per_page
                        last_joy_nav_time_map_dialog = current_time_map_dialog
                    axis_y_was_active_pos_map_dialog = True
                else: axis_y_was_active_pos_map_dialog = False
            else: axis_y_was_active_neg_map_dialog = False; axis_y_was_active_pos_map_dialog = False

        if not app_status.app_running: break
        screen.fill(color_black); screen.blit(frame_title_surf, frame_title_rect)
        instr_text = "Use Arrows/Enter. PgUp/PgDn or L/R for pages. ESC to cancel."
        instr_surf = font_instr.render(instr_text, True, color_gray); instr_rect = instr_surf.get_rect(center=(screen_w // 2, frame_title_rect.bottom + 20)); screen.blit(instr_surf, instr_rect) # type: ignore
        start_idx_draw = current_page * maps_per_page; end_idx_draw = min(start_idx_draw + maps_per_page, len(map_module_names))
        visible_maps_on_page_draw = map_module_names[start_idx_draw:end_idx_draw]; current_btn_y_draw = frame_title_rect.bottom + 60
        for i, map_name_item_draw in enumerate(visible_maps_on_page_draw):
            actual_map_index = start_idx_draw + i; item_text = f"{map_name_item_draw}"
            item_rect_draw = pygame.Rect(0, 0, screen_w * button_width_factor, button_height)
            item_rect_draw.centerx = screen_w // 2; item_rect_draw.top = current_btn_y_draw
            is_keyboard_selected = (actual_map_index == selected_index); is_mouse_hovered = item_rect_draw.collidepoint(mouse_pos)
            current_bg_color_item = color_button_normal_bg; current_text_color_item = color_text_normal
            if is_keyboard_selected:
                current_text_color_item = color_text_selected
                if is_mouse_hovered: current_bg_color_item = color_button_selected_hover_bg # type: ignore
                else: current_bg_color_item = color_button_selected_bg
            elif is_mouse_hovered: current_bg_color_item = color_button_hover_bg
            pygame.draw.rect(screen, current_bg_color_item, item_rect_draw, border_radius=5)
            pygame.draw.rect(screen, color_white, item_rect_draw, 1, border_radius=5)
            item_surf = font_item.render(item_text, True, current_text_color_item); text_rect = item_surf.get_rect(center=item_rect_draw.center); screen.blit(item_surf, text_rect) # type: ignore
            current_btn_y_draw += button_height + button_spacing
        if max_pages > 1:
            page_text = f"Page {current_page + 1} of {max_pages}"
            page_surf = font_instr.render(page_text, True, color_gray); page_rect = page_surf.get_rect(center=(screen_w // 2, screen_h - 30)); screen.blit(page_surf, page_rect) # type: ignore
        pygame.display.flip()
        clock_obj.tick(30)
    return None

def draw_download_dialog(screen: pygame.Surface, fonts: dict, title: str, message: str, progress_percent: float = -1):
    screen_w, screen_h = screen.get_size()
    dialog_w = screen_w * 0.7; dialog_h = screen_h * 0.4
    dialog_rect = pygame.Rect(0, 0, dialog_w, dialog_h); dialog_rect.center = (screen_w // 2, screen_h // 2)
    font_large = fonts.get("large") or pygame.font.Font(None, 48)
    font_medium = fonts.get("medium") or pygame.font.Font(None, 32)
    screen.fill(C.BLACK)
    pygame.draw.rect(screen, C.DARK_GRAY, dialog_rect, border_radius=10)
    pygame.draw.rect(screen, C.WHITE, dialog_rect, 2, border_radius=10)
    if font_large:
        title_surf = font_large.render(title, True, C.WHITE)
        title_rect_ui = title_surf.get_rect(centerx=dialog_rect.centerx, top=dialog_rect.top + 20)
        screen.blit(title_surf, title_rect_ui)
    if font_medium:
        msg_surf = font_medium.render(message, True, C.LIGHT_GRAY)
        msg_rect = msg_surf.get_rect(centerx=dialog_rect.centerx, top=(dialog_rect.top + 20 + (font_large.get_height() if font_large else 50) + 15))
        screen.blit(msg_surf, msg_rect)
    if progress_percent >= 0:
        bar_width = dialog_rect.width * 0.8; bar_height = 30
        bar_x = dialog_rect.centerx - bar_width / 2; bar_y = msg_rect.bottom + 30
        pygame.draw.rect(screen, C.GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
        fill_width = (progress_percent / 100.0) * bar_width
        pygame.draw.rect(screen, C.GREEN, (bar_x, bar_y, fill_width, bar_height), border_radius=5)
        pygame.draw.rect(screen, C.WHITE, (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)
        font_small = fonts.get("small") or pygame.font.Font(None, 24)
        if font_small:
            progress_text = f"{progress_percent:.1f}%"
            text_surf_prog = font_small.render(progress_text, True, C.BLACK)
            text_rect_p = text_surf_prog.get_rect(center=(bar_x + bar_width / 2, bar_y + bar_height / 2))
            screen.blit(text_surf_prog, text_rect_p)
    pygame.display.flip()

# Function get_server_ip_input_dialog remains unchanged as it doesn't list maps.
def get_server_ip_input_dialog(screen: pygame.Surface, clock_obj: pygame.time.Clock,
                               fonts: Dict[str, Optional[pygame.font.Font]], app_status: Any,
                               default_input_text: str = "127.0.0.1:5555") -> Optional[str]:
    # ... (function content is unchanged) ...
    input_text = default_input_text
    dialog_active = True
    input_font = fonts.get("medium") or pygame.font.Font(None, 36)
    if not input_font: return None # Critical if font missing
    
    title_font = fonts.get("large") or pygame.font.Font(None, 48)
    instr_font = fonts.get("small") or pygame.font.Font(None, 24)
    
    color_white = getattr(C, 'WHITE', (255,255,255))
    color_black = getattr(C, 'BLACK', (0,0,0))
    color_gray = getattr(C, 'GRAY', (128,128,128))
    color_input_bg = getattr(C, 'DARK_GRAY', (50,50,50))
    color_input_border = getattr(C, 'LIGHT_GRAY', (200,200,200))
    
    text_cursor_visible = True
    text_cursor_timer = pygame.time.get_ticks()
    TEXT_CURSOR_BLINK_MS = 500
    
    check_pygame_scrap_init_status() # Update global scrap status
    can_paste = PYPERCLIP_AVAILABLE_UI_MODULE or SCRAP_INITIALIZED_UI_MODULE

    while dialog_active and app_status.app_running:
        screen_w, screen_h = screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_status.app_running = False; dialog_active = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: dialog_active = False; return None
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER: dialog_active = False; return input_text
                if event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if can_paste:
                        try:
                            if PYPERCLIP_AVAILABLE_UI_MODULE: pasted_text = pyperclip.paste()
                            elif SCRAP_INITIALIZED_UI_MODULE: 
                                paste_type = pygame.scrap.get_types()[0] # Get first available type
                                pasted_bytes = pygame.scrap.get(paste_type)
                                pasted_text = pasted_bytes.decode('utf-8', 'replace').replace('\x00','') if pasted_bytes else ""
                            else: pasted_text = ""
                            input_text += pasted_text.strip()
                        except Exception as e: print(f"Error pasting: {e}")
                elif event.unicode.isprintable(): input_text += event.unicode
        
        if not app_status.app_running: break
        
        # Blinking cursor
        if pygame.time.get_ticks() - text_cursor_timer > TEXT_CURSOR_BLINK_MS:
            text_cursor_visible = not text_cursor_visible
            text_cursor_timer = pygame.time.get_ticks()
            
        screen.fill(color_black)
        if title_font:
            title_surf = title_font.render("Enter Server IP & Port", True, color_white)
            title_rect = title_surf.get_rect(center=(screen_w//2, screen_h * 0.3))
            screen.blit(title_surf, title_rect)

        if instr_font:
            paste_instr_text = "(Ctrl+V to paste)" if can_paste else "(Pasting not available)"
            instr_text = f"Format: IP_ADDRESS:PORT (e.g., 192.168.1.100:5555). ESC to cancel. {paste_instr_text}"
            instr_surf = instr_font.render(instr_text, True, color_gray)
            instr_rect_y_offset = title_font.get_height() // 2 + 15 if title_font else 40
            instr_rect = instr_surf.get_rect(center=(screen_w//2, screen_h * 0.3 + instr_rect_y_offset))
            screen.blit(instr_surf, instr_rect)

        input_box_width = screen_w * 0.6
        input_box_height = input_font.get_height() + 20
        input_box_rect = pygame.Rect(0, 0, input_box_width, input_box_height)
        input_box_y_offset = instr_font.get_height() + 25 if instr_font and title_font else 70
        input_box_rect.center = (screen_w // 2, screen_h * 0.3 + instr_rect_y_offset + input_box_y_offset)
        
        pygame.draw.rect(screen, color_input_bg, input_box_rect, border_radius=5)
        pygame.draw.rect(screen, color_input_border, input_box_rect, 2, border_radius=5)
        
        text_surface = input_font.render(input_text, True, color_white)
        text_rect = text_surface.get_rect(midleft=(input_box_rect.left + 10, input_box_rect.centery))
        screen.blit(text_surface, text_rect)
        
        # Draw cursor
        if text_cursor_visible:
            cursor_x = text_rect.right + 2
            cursor_y_start = input_box_rect.top + 5
            cursor_y_end = input_box_rect.bottom - 5
            pygame.draw.line(screen, color_white, (cursor_x, cursor_y_start), (cursor_x, cursor_y_end), 2)

        pygame.display.flip()
        clock_obj.tick(30)
    return None
########## END OF FILE: game_ui.py ##########