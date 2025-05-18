########## START OF FILE: main.py ##########
# main.py
# -*- coding: utf-8 -*-
## version 1.0.0.11 (Removed settings_ui and redundant external mapping call)
import sys
import os
import pygame
import traceback
from typing import Dict, Optional, Any

script_path = os.path.abspath(__file__)  # Absolute path to this script
script_dir = os.path.dirname(script_path) # Directory of this script
os.chdir(script_dir)


_maps_package_import_path_added = "None"
_maps_package_physical_location_debug = "Not determined"
_is_frozen = getattr(sys, 'frozen', False)
_bundle_dir_meipass = getattr(sys, '_MEIPASS', None)

if _is_frozen and _bundle_dir_meipass:
    _path_to_maps_in_bundle_root = os.path.join(_bundle_dir_meipass, 'maps')
    _maps_package_physical_location_debug = f"Bundled - Expected at: {_path_to_maps_in_bundle_root}"
    if os.path.isdir(_path_to_maps_in_bundle_root):
        if _bundle_dir_meipass not in sys.path:
            sys.path.insert(0, _bundle_dir_meipass)
            _maps_package_import_path_added = _bundle_dir_meipass
            _maps_package_physical_location_debug += " (Found, _MEIPASS added to sys.path for 'maps' import)"
        else:
            _maps_package_physical_location_debug += " (Found, _MEIPASS already in sys.path for 'maps' import)"
    else:
        _exe_parent_dir = os.path.dirname(sys.executable)
        _maps_next_to_exe_path = os.path.join(_exe_parent_dir, 'maps')
        _maps_package_physical_location_debug += f"; Alt check: {_maps_next_to_exe_path}"
        if os.path.isdir(_maps_next_to_exe_path):
            if _exe_parent_dir not in sys.path:
                sys.path.insert(0, _exe_parent_dir)
                _maps_package_import_path_added = _exe_parent_dir
                _maps_package_physical_location_debug += " (Found next to EXE, parent added for 'maps' import)"
            else:
                 _maps_package_physical_location_debug += " (Found next to EXE, parent already in sys.path for 'maps' import)"
        else:
            _maps_package_physical_location_debug += " (NOT found in _MEIPASS or next to EXE)"
else:
    _project_root = os.path.abspath(os.path.dirname(__file__))
    _dev_maps_package_path = os.path.join(_project_root, 'maps')
    _maps_package_physical_location_debug = f"Dev - Expected at: {_dev_maps_package_path}"
    if os.path.isdir(_dev_maps_package_path):
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
            _maps_package_import_path_added = _project_root
            _maps_package_physical_location_debug += " (Found, project root added to sys.path for 'maps' import)"
        else:
            _maps_package_physical_location_debug += " (Found, project root already in sys.path for 'maps' import)"
    else:
        _maps_package_physical_location_debug += " (NOT found in project root)"

def _main_print(msg_type, msg): print(f"MAIN {msg_type}: {msg}")
_main_print("INFO", f"Path added to sys.path for 'maps' package import: {_maps_package_import_path_added}")
_main_print("INFO", f"Physical location check for 'maps' package: {_maps_package_physical_location_debug}")

PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    _main_print("INFO","Pyperclip library found.")
except ImportError:
    _main_print("WARNING", "Pyperclip library not found. Paste in UI may be limited.")

try:
    import constants as C
    _main_print("INFO", f"C.MAPS_DIR (for file ops) is: {C.MAPS_DIR}")
    from camera import Camera
    from items import Chest
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode
    from couch_play_logic import run_couch_play_mode
    import game_ui
    import config as game_config
    import joystick_handler
    # import settings_ui # REMOVED settings_ui import as per your request
    _main_print("INFO", "Platformer modules imported successfully.")
except ImportError as e:
    _main_print("FATAL", f"Failed to import a required platformer module: {e}")
    _main_print("INFO", f"Current sys.path was: {sys.path}")
    traceback.print_exc(); sys.exit(1)
except Exception as e:
    _main_print("FATAL", f"An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc(); sys.exit(1)

os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
pygame.init()
pygame.font.init()

# CORRECT INITIALIZATION ORDER:
# 1. Initialize joysticks so config.py can get an accurate count.
joystick_handler.init_joysticks()

# 2. Load game configuration. config.py now handles loading controller_mappings.json internally.
game_config.load_config()

# THE ERRONEOUS BLOCK THAT WAS HERE HAS BEEN REMOVED.

class AppStatus:
    def __init__(self): self.app_running = True

try:
    display_info = pygame.display.Info()
    monitor_width, monitor_height = display_info.current_w, display_info.current_h
    initial_width = max(800, min(1600, int(monitor_width * 0.75)))
    calculated_initial_height = max(600, min(900, int(monitor_height * 0.75)))
    initial_height = calculated_initial_height + 80 # As per your last main.py version
    WIDTH_MAIN, HEIGHT_MAIN = initial_width, initial_height
    screen_flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH_MAIN, HEIGHT_MAIN), screen_flags)
    pygame.display.set_caption("Platformer Adventure LAN")
    _main_print("INFO", f"Initial window dimensions: {WIDTH_MAIN}x{HEIGHT_MAIN}")
except Exception as e:
    _main_print("FATAL", f"Error setting up Pygame display: {e}")
    traceback.print_exc(); pygame.quit(); sys.exit(1)

SCRAP_INITIALIZED_MAIN = False
try:
    if pygame.display.get_init():
        pygame.scrap.init()
        SCRAP_INITIALIZED_MAIN = pygame.scrap.get_init()
        if SCRAP_INITIALIZED_MAIN: _main_print("INFO", "pygame.scrap clipboard module initialized.")
        else: _main_print("WARNING", "pygame.scrap.init() called but pygame.scrap.get_init() returned False.")
    else: _main_print("WARNING", "Display not initialized before pygame.scrap.init() attempt.")
except AttributeError: _main_print("WARNING", "pygame.scrap module not found or available.")
except pygame.error as e: _main_print("WARNING", f"pygame.scrap module could not be initialized: {e}")
except Exception as e: _main_print("WARNING", f"Unexpected error during pygame.scrap init: {e}")

_TILE_SIZE_DEFAULT = getattr(C, 'TILE_SIZE', 40)
_LIGHT_BLUE_DEFAULT = getattr(C, 'LIGHT_BLUE', (173, 216, 230))
game_elements: Dict[str, Any] = {
    "player1": None, "player2": None, "camera": None, "current_chest": None,
    "enemy_list": [], "platform_sprites": pygame.sprite.Group(),
    "ladder_sprites": pygame.sprite.Group(), "hazard_sprites": pygame.sprite.Group(),
    "enemy_sprites": pygame.sprite.Group(), "collectible_sprites": pygame.sprite.Group(),
    "projectile_sprites": pygame.sprite.Group(), "all_sprites": pygame.sprite.Group(),
    "level_pixel_width": WIDTH_MAIN, "level_min_y_absolute": 0, "level_max_y_absolute": HEIGHT_MAIN,
    "ground_level_y": HEIGHT_MAIN - _TILE_SIZE_DEFAULT, "ground_platform_height": _TILE_SIZE_DEFAULT,
    "player1_spawn_pos": (100, HEIGHT_MAIN - (_TILE_SIZE_DEFAULT * 2)),
    "player2_spawn_pos": (150, HEIGHT_MAIN - (_TILE_SIZE_DEFAULT * 2)),
    "enemy_spawns_data_cache": [], "level_background_color": _LIGHT_BLUE_DEFAULT,
    "loaded_map_name": None, "statue_objects": []
}

if __name__ == "__main__":
    _main_print("INFO", "Starting __main__ execution block.")
    main_clock = pygame.time.Clock()
    app_status = AppStatus()

    fonts: Dict[str, Optional[pygame.font.Font]] = {"small": None, "medium": None, "large": None, "debug": None}
    try:
        fonts["small"] = pygame.font.Font(None, 28)
        fonts["medium"] = pygame.font.Font(None, 36)
        fonts["large"] = pygame.font.Font(None, 72)
        fonts["debug"] = pygame.font.Font(None, 20)
        if any(f is None for f in fonts.values()): raise pygame.error("Font loading failed.")
        _main_print("INFO", "Fonts loaded successfully.")
    except pygame.error as e:
        _main_print("FATAL", f"Font loading error: {e}. Ensure Pygame font module is working.")
        traceback.print_exc(); app_status.app_running = False
    except Exception as e:
        _main_print("FATAL", f"Unexpected error during font loading: {e}")
        traceback.print_exc(); app_status.app_running = False

    while app_status.app_running:
        current_screen_width, current_screen_height = screen.get_size()
        pygame.display.set_caption("Platformer Adventure - Main Menu")

        _main_print("INFO", "\nShowing main menu...")
        menu_choice = game_ui.show_main_menu(screen, main_clock, fonts, app_status)
        _main_print("INFO", f"Main menu choice: '{menu_choice}'")

        if not app_status.app_running or menu_choice == "quit":
            app_status.app_running = False; break

        if menu_choice == "settings": # Since settings_ui is removed
            _main_print("INFO", "Settings chosen, but settings_ui is not integrated. Returning to main menu.")
            if fonts.get("medium"):
                screen.fill(getattr(C, 'BLACK', (0,0,0)))
                msg_surf = fonts["medium"].render("Settings UI not available.", True, getattr(C, 'WHITE', (255,255,255)))
                screen.blit(msg_surf, msg_surf.get_rect(center=(current_screen_width//2, current_screen_height//2)))
                pygame.display.flip()
                pygame.time.wait(1500)
            continue

        map_to_load_for_game: Optional[str] = None
        if menu_choice in ["couch_play", "host"]:
            _main_print("INFO", f"Mode '{menu_choice}' requires map selection. Opening map dialog...")
            map_to_load_for_game = game_ui.select_map_dialog(screen, main_clock, fonts, app_status)
            if not app_status.app_running: _main_print("INFO", "App quit during map selection."); break
            if map_to_load_for_game is None:
                _main_print("INFO", "Map selection cancelled/no maps. Returning to main menu."); continue
            _main_print("INFO", f"Map selected for '{menu_choice}': '{map_to_load_for_game}'")

        _main_print("INFO", f"Initializing game elements for mode '{menu_choice}' with map '{map_to_load_for_game if map_to_load_for_game else 'Default/Server-defined'}'...")
        initialized_elements = initialize_game_elements(
            current_screen_width, current_screen_height,
            for_game_mode=menu_choice,
            existing_sprites_groups={
                "all_sprites": game_elements["all_sprites"],
                "projectile_sprites": game_elements["projectile_sprites"],
                "player1": game_elements.get("player1"),
                "player2": game_elements.get("player2"),
                "current_chest": game_elements.get("current_chest")
            },
            map_module_name=map_to_load_for_game
        )
        if initialized_elements is None:
            _main_print("ERROR", f"Failed to initialize game elements for mode '{menu_choice}' (Map: '{map_to_load_for_game}'). Returning to menu.")
            screen.fill(getattr(C, 'BLACK', (0,0,0)))
            if fonts.get("medium"):
                err_msg_surf = fonts["medium"].render(f"Error starting {menu_choice} mode. Check logs.", True, getattr(C, 'RED', (255,0,0)))
                screen.blit(err_msg_surf, err_msg_surf.get_rect(center=(current_screen_width//2, current_screen_height//2)))
            pygame.display.flip(); pygame.time.wait(3000)
            continue
        game_elements.update(initialized_elements)
        if game_elements.get("camera"):
            cam_instance = game_elements["camera"]
            cam_instance.set_screen_dimensions(current_screen_width, current_screen_height)
            if "level_pixel_width" in game_elements:
                cam_instance.set_level_dimensions(
                    game_elements["level_pixel_width"],
                    game_elements["level_min_y_absolute"],
                    game_elements["level_max_y_absolute"]
                )
            _main_print("INFO", f"Camera reconfigured for mode '{menu_choice}'. Screen: {current_screen_width}x{current_screen_height}")

        _main_print("INFO", f"Launching game mode: '{menu_choice}'")
        if menu_choice == "host":
            server_state = ServerState()
            server_state.current_map_name = game_elements.get("loaded_map_name", map_to_load_for_game)
            server_state.app_running = app_status.app_running
            run_server_mode(screen, main_clock, fonts, game_elements, server_state)
            app_status.app_running = server_state.app_running
        elif menu_choice == "join_lan":
            client_state = ClientState()
            client_state.app_running = app_status.app_running
            run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=None)
            app_status.app_running = client_state.app_running
        elif menu_choice == "join_ip":
            _main_print("INFO", "Requesting IP input for 'join_ip' mode...")
            target_ip_input = game_ui.get_server_ip_input_dialog(screen, main_clock, fonts, app_status, default_input_text="127.0.0.1:5555")
            _main_print("INFO", f"IP input dialog returned: '{target_ip_input}'")
            if target_ip_input and app_status.app_running:
                client_state = ClientState()
                client_state.app_running = app_status.app_running
                run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=target_ip_input)
                app_status.app_running = client_state.app_running
            else: _main_print("INFO", "IP input cancelled or app quit. Returning to main menu.")
        elif menu_choice == "couch_play":
            run_couch_play_mode(screen, main_clock, fonts, game_elements, app_status)
        _main_print("INFO", f"Returned from game mode '{menu_choice}'. App running: {app_status.app_running}")

    _main_print("INFO", "Exiting application loop gracefully.")
    joystick_handler.quit_joysticks()
    pygame.quit()
    if SCRAP_INITIALIZED_MAIN and pygame.scrap.get_init():
        try: pygame.scrap.quit(); _main_print("INFO", "pygame.scrap quit successfully.")
        except Exception as e: _main_print("WARNING", f"Error during pygame.scrap.quit(): {e}")
    _main_print("INFO", "Application terminated.")
    sys.exit(0)

########## END OF FILE: main.py ##########