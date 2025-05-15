# game_ui.py
# -*- coding: utf-8 -*-
## version 1.0.0.4 (Added select_map_dialog)
"""
Functions for drawing User Interface elements like health bars, player HUDs,
main menus, input dialogs, and the main game scene.
"""
import pygame
import time 
import os # Needed for listing map files
import constants as C 
from typing import Dict, Optional, Any, List # Added List

# --- (PYPERCLIP_AVAILABLE_UI_MODULE and SCRAP_INITIALIZED_UI_MODULE setup remains the same) ---
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

# --- (draw_health_bar, draw_player_hud, draw_platformer_scene_on_surface, show_main_menu, get_server_ip_input_dialog remain the same as your provided version) ---
# --- Health Bar Drawing Function ---
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
        except Exception as e: label_height_offset = getattr(hud_font_obj, 'get_height', lambda: 20)()
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
        except Exception as e: pass

def draw_platformer_scene_on_surface(screen_surface: pygame.Surface, game_elements: Dict[str, Any], 
                                     fonts: Dict[str, Optional[pygame.font.Font]], current_game_time_ticks: int,
                                     # Added optional parameters for download status
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
               hasattr(enemy_sprite, 'current_health') and hasattr(enemy_sprite, 'max_health'):
                enemy_rect_on_screen = camera_instance.apply(enemy_sprite.rect) 
                hb_w, hb_h = getattr(C, 'HEALTH_BAR_WIDTH', 50), getattr(C, 'HEALTH_BAR_HEIGHT', 8)
                hb_x, hb_y = enemy_rect_on_screen.centerx - hb_w // 2, enemy_rect_on_screen.top - hb_h - getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5) 
                draw_health_bar(screen_surface, hb_x, hb_y, hb_w, hb_h, enemy_sprite.current_health, enemy_sprite.max_health)
    elif all_sprites_group: all_sprites_group.draw(screen_surface)
    if player1_instance and getattr(player1_instance, '_valid_init', False) and player1_instance.alive():
        draw_player_hud(screen_surface, 10, 10, player1_instance, 1, font_for_hud)
    if player2_instance and getattr(player2_instance, '_valid_init', False) and player2_instance.alive():
        p2_hud_w = getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH',50)*2) + 120 
        draw_player_hud(screen_surface, current_screen_width - p2_hud_w - 10, 10, player2_instance, 2, font_for_hud)

    # Draw download status overlay if provided (typically for the host watching a client download)
    if download_status_message and font_for_hud:
        dialog_rect = pygame.Rect(0, 0, current_screen_width * 0.6, current_screen_height * 0.3)
        dialog_rect.center = (current_screen_width // 2, current_screen_height // 2)
        pygame.draw.rect(screen_surface, C.DARK_GRAY, dialog_rect, border_radius=10)
        pygame.draw.rect(screen_surface, C.WHITE, dialog_rect, 2, border_radius=10)

        status_surf = font_for_hud.render(download_status_message, True, C.WHITE)
        status_rect = status_surf.get_rect(centerx=dialog_rect.centerx, top=dialog_rect.top + 20)
        screen_surface.blit(status_surf, status_rect)

        if download_progress_percent is not None and download_progress_percent >= 0:
            bar_width = dialog_rect.width * 0.8
            bar_height = 30
            bar_x = dialog_rect.centerx - bar_width / 2
            bar_y = status_rect.bottom + 20
            
            # Background of the progress bar
            pygame.draw.rect(screen_surface, C.GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
            # Filled part of the progress bar
            fill_width = (download_progress_percent / 100) * bar_width
            pygame.draw.rect(screen_surface, C.GREEN, (bar_x, bar_y, fill_width, bar_height), border_radius=5)
            # Border for the progress bar
            pygame.draw.rect(screen_surface, C.WHITE, (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)

            progress_text = f"{download_progress_percent:.1f}%"
            font_small = fonts.get("small") or pygame.font.Font(None, 24)
            if font_small:
                text_surf = font_small.render(progress_text, True, C.BLACK)
                text_rect_prog = text_surf.get_rect(center=(bar_x + bar_width / 2, bar_y + bar_height / 2))
                screen_surface.blit(text_surf, text_rect_prog)


def show_main_menu(screen_surface: pygame.Surface, clock_obj: pygame.time.Clock, 
                   fonts: Dict[str, Optional[pygame.font.Font]], app_status_obj: Any) -> Optional[str]:
    button_w, button_h, spacing, title_gap = 350, 55, 20, 60
    current_w, current_h = screen_surface.get_size()
    font_title = fonts.get("large") or (pygame.font.Font(None, 60) if pygame.font.get_init() else None)
    if not font_title: return "quit"
    title_surf = font_title.render("Platformer Adventure LAN", True, getattr(C, 'WHITE',(255,255,255)))
    menu_buttons = {"host": {"text": "Host Game", "action": "host"}, "join_lan": {"text": "Join LAN", "action": "join_lan"},
                    "join_ip": {"text": "Join by IP", "action": "join_ip"}, "couch_play": {"text": "Couch Play", "action": "couch_play"},
                    "quit": {"text": "Quit", "action": "quit"}}
    font_button = fonts.get("medium") or (pygame.font.Font(None, 30) if pygame.font.get_init() else None)
    if not font_button: return "quit"
    title_rect = title_surf.get_rect(center=(current_w // 2, current_h // 4))
    
    def update_btn_geo():
        nonlocal title_rect 
        current_w_local, current_h_local = screen_surface.get_size() 
        title_rect = title_surf.get_rect(center=(current_w_local // 2, current_h_local // 4))
        btn_y = title_rect.bottom + title_gap
        for props in menu_buttons.values():
            props["rect"] = pygame.Rect(0, 0, button_w, button_h); props["rect"].centerx, props["rect"].top = current_w_local // 2, btn_y
            props["text_surf"] = font_button.render(props["text"], True, getattr(C, 'WHITE',(255,255,255)))
            props["text_rect"] = props["text_surf"].get_rect(center=props["rect"].center); btn_y += button_h + spacing
    update_btn_geo()
    selected_action = None
    while selected_action is None and app_status_obj.app_running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_status_obj.app_running = False; selected_action = "quit"
            if event.type == pygame.VIDEORESIZE and not (screen_surface.get_flags() & pygame.FULLSCREEN):
                try:
                    current_w, current_h = max(320,event.w), max(240,event.h)
                    screen_surface = pygame.display.set_mode((current_w,current_h), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    update_btn_geo()
                except pygame.error as e: print(f"Menu resize error: {e}")
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: app_status_obj.app_running = False; selected_action = "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for props in menu_buttons.values():
                    if "rect" in props and props["rect"].collidepoint(mouse_pos): selected_action = props["action"]; break
        if not app_status_obj.app_running: break
        screen_surface.fill(getattr(C, 'BLACK',(0,0,0))); screen_surface.blit(title_surf, title_rect)
        for props in menu_buttons.values():
            if "rect" in props:
                hover = props["rect"].collidepoint(mouse_pos)
                color = getattr(C, 'GREEN',(0,255,0)) if hover else getattr(C, 'BLUE',(0,0,255))
                pygame.draw.rect(screen_surface, color, props["rect"], border_radius=8)
                if "text_surf" in props and "text_rect" in props: screen_surface.blit(props["text_surf"], props["text_rect"])
        pygame.display.flip(); clock_obj.tick(30)
    return selected_action

def get_server_ip_input_dialog(screen_surface: pygame.Surface, clock_obj: pygame.time.Clock, 
                               fonts: Dict[str, Optional[pygame.font.Font]], app_status_obj: Any, 
                               default_input_text: str = "") -> Optional[str]:
    current_input = default_input_text; active = True; cursor_visible = True; last_blink = time.time()
    current_w, current_h = screen_surface.get_size()
    box_w = max(200, current_w // 2); box_rect = pygame.Rect(0,0, box_w, 50); box_rect.center = (current_w//2, current_h//2)
    pygame.key.set_repeat(250, 25); paste_msg = None; paste_time = 0
    check_pygame_scrap_init_status()
    font_prompt = fonts.get("medium") or (pygame.font.Font(None,30) if pygame.font.get_init() else None)
    font_info = fonts.get("small") or (pygame.font.Font(None,20) if pygame.font.get_init() else None)
    font_input = fonts.get("medium") or (pygame.font.Font(None,30) if pygame.font.get_init() else None)
    if not all([font_prompt, font_info, font_input]): pygame.key.set_repeat(0,0); return None
    while active and app_status_obj.app_running:
        now = time.time()
        if now - last_blink > 0.5: cursor_visible = not cursor_visible; last_blink = now
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_status_obj.app_running = False; active = False; current_input = None
            if event.type == pygame.VIDEORESIZE and not (screen_surface.get_flags() & pygame.FULLSCREEN):
                try:
                    current_w,current_h=max(320,event.w),max(240,event.h)
                    screen_surface=pygame.display.set_mode((current_w,current_h), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    box_w = max(200, current_w // 2); box_rect = pygame.Rect(0,0, box_w, 50); box_rect.center = (current_w//2, current_h//2)
                except pygame.error as e: print(f"IP Dialog resize error: {e}")
            if event.type == pygame.KEYDOWN:
                paste_msg = None
                if event.key == pygame.K_ESCAPE: active = False; current_input = None
                elif event.key == pygame.K_RETURN: active = False
                elif event.key == pygame.K_BACKSPACE: current_input = current_input[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META):
                    pasted = ""; method = "None"
                    try:
                        if SCRAP_INITIALIZED_UI_MODULE:
                            cb_bytes = pygame.scrap.get(pygame.SCRAP_TEXT); 
                            if cb_bytes: pasted = cb_bytes.decode('utf-8','ignore').replace('\x00','').strip()
                            if pasted: method = "scrap"
                        if not pasted and PYPERCLIP_AVAILABLE_UI_MODULE:
                            cb_str = pyperclip.paste()
                            if isinstance(cb_str,str): pasted = cb_str.replace('\x00','').strip()
                            if pasted: method = "pyperclip"
                    except Exception as e: print(f"Paste error (Method {method}): {e}")
                    if pasted: current_input += pasted
                    else: paste_msg = "Paste Failed/Empty"; paste_time = now
                elif event.unicode.isprintable() and (event.unicode.isalnum() or event.unicode in ['.',':','-']): current_input += event.unicode
        if not app_status_obj.app_running: break
        screen_surface.fill(getattr(C,'BLACK',(0,0,0)))
        prompt_surf = font_prompt.render("Enter Host IP or IP:Port", True, getattr(C,'WHITE',(255,255,255)))
        screen_surface.blit(prompt_surf, prompt_surf.get_rect(center=(current_w//2, current_h//2-60)))
        info_surf = font_info.render("(Enter=OK, Esc=Cancel, Ctrl+V=Paste)", True, getattr(C,'GRAY',(128,128,128)))
        screen_surface.blit(info_surf, info_surf.get_rect(center=(current_w//2, current_h-40)))
        pygame.draw.rect(screen_surface, getattr(C,'GRAY',(128,128,128)), box_rect,0,5)
        pygame.draw.rect(screen_surface, getattr(C,'WHITE',(255,255,255)), box_rect,2,5)
        input_surf = font_input.render(current_input, True, getattr(C,'BLACK',(0,0,0)))
        input_rect = input_surf.get_rect(midleft=(box_rect.left+10, box_rect.centery))
        clip_area = box_rect.inflate(-12,-12)
        if input_rect.width > clip_area.width: input_rect.right = clip_area.right
        else: input_rect.left = clip_area.left
        screen_surface.set_clip(clip_area); screen_surface.blit(input_surf, input_rect); screen_surface.set_clip(None)
        if cursor_visible:
            cursor_x = max(clip_area.left, min(input_rect.right+2, clip_area.right-1))
            pygame.draw.line(screen_surface, getattr(C,'BLACK',(0,0,0)), (cursor_x,box_rect.top+5), (cursor_x,box_rect.bottom-5),2)
        if paste_msg and now - paste_time < 2.0:
            msg_surf = font_info.render(paste_msg, True, getattr(C,'RED',(255,0,0)))
            screen_surface.blit(msg_surf, msg_surf.get_rect(center=(current_w//2,box_rect.bottom+30)))
        elif paste_msg: paste_msg = None
        pygame.display.flip(); clock_obj.tick(30)
    pygame.key.set_repeat(0,0)
    return current_input.strip() if current_input is not None else None


MAPS_DIRECTORY_GAME_UI = getattr(C, "MAPS_DIR", "maps")

def select_map_dialog(screen: pygame.Surface, clock: pygame.time.Clock, 
                      fonts: Dict[str, Optional[pygame.font.Font]], 
                      app_status: Any) -> Optional[str]:
    print("GAME_UI: Opening select_map_dialog...")
    map_module_names: List[str] = []
    if os.path.exists(MAPS_DIRECTORY_GAME_UI) and os.path.isdir(MAPS_DIRECTORY_GAME_UI):
        try:
            for f_name in os.listdir(MAPS_DIRECTORY_GAME_UI):
                if f_name.endswith(".py") and f_name != "__init__.py":
                    map_module_names.append(f_name[:-3]) 
            map_module_names.sort()
            print(f"GAME_UI: Found maps: {map_module_names}")
        except OSError as e:
            print(f"GAME_UI Error: Could not read maps directory '{MAPS_DIRECTORY_GAME_UI}': {e}")
            map_module_names = [] 
    else:
        print(f"GAME_UI Warning: Maps directory '{MAPS_DIRECTORY_GAME_UI}' not found.")

    if not map_module_names:
        font_medium = fonts.get("medium") or (pygame.font.Font(None, 36) if pygame.font.get_init() else None)
        if font_medium:
            screen_w, screen_h = screen.get_size()
            screen.fill(getattr(C, 'BLACK', (0,0,0)))
            msg_surf = font_medium.render(f"No Maps Found in '{C.MAPS_DIR}/' folder.", True, getattr(C, 'RED', (255,0,0)))
            screen.blit(msg_surf, msg_surf.get_rect(center=(screen_w//2, screen_h//2)))
            pygame.display.flip()
            pygame.time.wait(2500) 
        return None 

    selected_index = 0
    dialog_active = True
    
    font_title = fonts.get("large") or (pygame.font.Font(None, 60) if pygame.font.get_init() else None)
    font_item = fonts.get("medium") or (pygame.font.Font(None, 30) if pygame.font.get_init() else None)
    font_instr = fonts.get("small") or (pygame.font.Font(None, 24) if pygame.font.get_init() else None)

    if not all([font_title, font_item, font_instr]):
        print("GAME_UI Error: Essential fonts for map selection dialog missing.")
        return map_module_names[0] if map_module_names else None 

    maps_per_page = 8 
    current_page = 0
    max_pages = (len(map_module_names) + maps_per_page - 1) // maps_per_page

    button_height = 45
    button_spacing = 10
    button_width_factor = 0.6 
    
    color_white = getattr(C, 'WHITE', (255,255,255))
    color_black = getattr(C, 'BLACK', (0,0,0))
    color_blue = getattr(C, 'BLUE', (0,0,255))
    color_green = getattr(C, 'GREEN', (0,255,0))
    color_gray = getattr(C, 'GRAY', (128,128,128))

    while dialog_active and app_status.app_running:
        screen_w, screen_h = screen.get_size()
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                app_status.app_running = False; dialog_active = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    dialog_active = False; return None 
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    if 0 <= selected_index < len(map_module_names):
                        print(f"GAME_UI: Map selected: {map_module_names[selected_index]}")
                        return map_module_names[selected_index]
                elif event.key == pygame.K_UP:
                    selected_index = (selected_index - 1 + len(map_module_names)) % len(map_module_names)
                    current_page = selected_index // maps_per_page
                elif event.key == pygame.K_DOWN:
                    selected_index = (selected_index + 1) % len(map_module_names)
                    current_page = selected_index // maps_per_page
                elif event.key == pygame.K_PAGEUP or (event.key == pygame.K_LEFT and max_pages > 1) : 
                    current_page = max(0, current_page - 1)
                    selected_index = current_page * maps_per_page 
                elif event.key == pygame.K_PAGEDOWN or (event.key == pygame.K_RIGHT and max_pages > 1): 
                    current_page = min(max_pages - 1, current_page + 1)
                    selected_index = current_page * maps_per_page
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                start_idx = current_page * maps_per_page
                end_idx = min(start_idx + maps_per_page, len(map_module_names))
                visible_maps_on_page = map_module_names[start_idx:end_idx]

                title_surf = font_title.render("Select a Map", True, color_white)
                title_rect = title_surf.get_rect(center=(screen_w // 2, screen_h * 0.15))
                current_btn_y = title_rect.bottom + 40

                for i, map_name in enumerate(visible_maps_on_page):
                    actual_map_index = start_idx + i
                    item_rect = pygame.Rect(0, 0, screen_w * button_width_factor, button_height)
                    item_rect.centerx = screen_w // 2
                    item_rect.top = current_btn_y
                    if item_rect.collidepoint(mouse_pos):
                        print(f"GAME_UI: Map selected by click: {map_name}")
                        return map_name 
                    current_btn_y += button_height + button_spacing
        
        if not app_status.app_running: break

        screen.fill(color_black)
        
        title_surf = font_title.render("Select a Map to Play", True, color_white)
        title_rect = title_surf.get_rect(center=(screen_w // 2, screen_h * 0.15))
        screen.blit(title_surf, title_rect)

        instr_text = "Use UP/DOWN Arrows, Enter to Select. PgUp/PgDn or LEFT/RIGHT for pages. ESC to cancel."
        instr_surf = font_instr.render(instr_text, True, color_gray)
        instr_rect = instr_surf.get_rect(center=(screen_w // 2, title_rect.bottom + 20))
        screen.blit(instr_surf, instr_rect)
        
        start_idx = current_page * maps_per_page
        end_idx = min(start_idx + maps_per_page, len(map_module_names))
        visible_maps_on_page = map_module_names[start_idx:end_idx]

        current_btn_y = title_rect.bottom + 60 

        for i, map_name in enumerate(visible_maps_on_page):
            actual_map_index = start_idx + i 
            
            item_text = f"{map_name}"
            item_color = color_white
            bg_color = color_blue

            if actual_map_index == selected_index:
                item_color = color_black 
                bg_color = color_green   
            
            item_surf = font_item.render(item_text, True, item_color)
            
            item_rect = pygame.Rect(0, 0, screen_w * button_width_factor, button_height)
            item_rect.centerx = screen_w // 2
            item_rect.top = current_btn_y
            
            pygame.draw.rect(screen, bg_color, item_rect, border_radius=5)
            pygame.draw.rect(screen, color_white, item_rect, 1, border_radius=5) 
            
            text_rect = item_surf.get_rect(center=item_rect.center)
            screen.blit(item_surf, text_rect)
            
            current_btn_y += button_height + button_spacing

        if max_pages > 1:
            page_text = f"Page {current_page + 1} of {max_pages}"
            page_surf = font_instr.render(page_text, True, color_gray)
            page_rect = page_surf.get_rect(center=(screen_w // 2, screen_h - 30))
            screen.blit(page_surf, page_rect)

        pygame.display.flip()
        clock.tick(30) 

    print("GAME_UI: Exiting select_map_dialog.")
    return None 


def draw_download_dialog(screen: pygame.Surface, fonts: dict, title: str, message: str, progress_percent: float = -1):
    """
    Draws a generic dialog for showing download status or messages.
    progress_percent: -1 means no bar, 0-100 shows progress.
    """
    screen_w, screen_h = screen.get_size()
    dialog_w = screen_w * 0.7
    dialog_h = screen_h * 0.4
    dialog_rect = pygame.Rect(0, 0, dialog_w, dialog_h)
    dialog_rect.center = (screen_w // 2, screen_h // 2)

    font_large = fonts.get("large") or pygame.font.Font(None, 48)
    font_medium = fonts.get("medium") or pygame.font.Font(None, 32)

    screen.fill(C.BLACK) # Full screen dim for focus

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
        bar_width = dialog_rect.width * 0.8
        bar_height = 30
        bar_x = dialog_rect.centerx - bar_width / 2
        bar_y = msg_rect.bottom + 30
        
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