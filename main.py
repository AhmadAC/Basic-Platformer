# main.py
# -*- coding: utf-8 -*-
## version 1.0.0.8 (Integrate settings UI, config, joystick_handler)
import sys
import os
import pygame 
import traceback
from typing import Dict, Optional, Any 

_maps_package_import_path_added = "None"
_maps_package_physical_location_debug = "Not determined"
_is_frozen = getattr(sys, 'frozen', False)
_bundle_dir_meipass = getattr(sys, '_MEIPASS', None) 

if _is_frozen and _bundle_dir_meipass:
    _path_to_maps_in_bundle_root = os.path.join(_bundle_dir_meipass, 'maps')
    _maps_package_physical_location_debug = f"Expected at: {_path_to_maps_in_bundle_root}"
    if os.path.isdir(_path_to_maps_in_bundle_root):
        if _bundle_dir_meipass not in sys.path:
            sys.path.insert(0, _bundle_dir_meipass)
            _maps_package_import_path_added = _bundle_dir_meipass
            _maps_package_physical_location_debug += " (Found, _MEIPASS added to sys.path)"
        else:
            _maps_package_physical_location_debug += " (Found, _MEIPASS already in sys.path)"
    else:
        _maps_package_physical_location_debug += " (NOT found in _MEIPASS)"
        _exe_parent_dir = os.path.dirname(sys.executable)
        _maps_next_to_exe_path = os.path.join(_exe_parent_dir, 'maps')
        if os.path.isdir(_maps_next_to_exe_path):
            if _exe_parent_dir not in sys.path:
                sys.path.insert(0, _exe_parent_dir) 
                _maps_package_import_path_added = _exe_parent_dir
                _maps_package_physical_location_debug = f"Found next to EXE at '{_maps_next_to_exe_path}' (Parent '{_exe_parent_dir}' added)"
else:
    _project_root = os.path.abspath(os.path.dirname(__file__))
    _dev_maps_package_path = os.path.join(_project_root, 'maps')
    _maps_package_physical_location_debug = f"Expected at: {_dev_maps_package_path}"
    if os.path.isdir(_dev_maps_package_path):
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
            _maps_package_import_path_added = _project_root
            _maps_package_physical_location_debug += " (Found, project root added to sys.path)"
        else:
            _maps_package_physical_location_debug += " (Found, project root already in sys.path)"
    else:
        _maps_package_physical_location_debug += " (NOT found in project root)"

PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    print("Main: Pyperclip library found and imported successfully.")
except ImportError:
    print("Main: Pyperclip library not found (pip install pyperclip). Paste in UI may be limited.")

try:
    import constants as C 
    from camera import Camera
    from items import Chest
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode
    from couch_play_logic import run_couch_play_mode
    import game_ui
    import config as game_config # New import
    import joystick_handler     # New import
    import settings_ui          # New import

    print("Platformer modules imported successfully.")
except ImportError as e:
    print(f"FATAL MAIN: Failed to import a required platformer module: {e}")
    print(f"Current sys.path was: {sys.path}") 
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"FATAL MAIN: An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc()
    sys.exit(1)

print(f"Main (Post-Constants Import): Path added to sys.path for 'maps' package import: {_maps_package_import_path_added}")
print(f"Main (Post-Constants Import): Physical location check for 'maps' package: {_maps_package_physical_location_debug}")
print(f"Main (Post-Constants Import): C.MAPS_DIR (for file ops) is: {C.MAPS_DIR}")

os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0' 
pygame.init()
pygame.font.init() 
joystick_handler.init_joysticks() # Initialize joysticks
game_config.load_config() # Load game config (controls, etc.)

class AppStatus:
    def __init__(self):
        self.app_running = True

try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w
    monitor_height = display_info.current_h
    initial_width = max(800, min(1600, int(monitor_width * 0.75))) 
    initial_height = max(600, min(900, int(monitor_height * 0.75))) 
    WIDTH_MAIN, HEIGHT_MAIN = initial_width, initial_height
    screen_flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH_MAIN, HEIGHT_MAIN), screen_flags)
    pygame.display.set_caption("Platformer Adventure LAN")
    print(f"Main: Initial window dimensions: {WIDTH_MAIN}x{HEIGHT_MAIN}")
except Exception as e:
    print(f"FATAL MAIN: Error setting up Pygame display: {e}")
    traceback.print_exc()
    pygame.quit()
    sys.exit(1)

SCRAP_INITIALIZED_MAIN = False
try:
    if pygame.display.get_init(): 
        pygame.scrap.init()
        SCRAP_INITIALIZED_MAIN = pygame.scrap.get_init()
        if SCRAP_INITIALIZED_MAIN:
            print("Main: pygame.scrap clipboard module initialized successfully.")
        else:
            print("Main Warning: pygame.scrap.init() called but pygame.scrap.get_init() returned False.")
    else:
        print("Main Warning: Display not initialized before pygame.scrap.init() attempt.")
except AttributeError:
    print("Main Warning: pygame.scrap module not found or available on this system (common on non-X11 Linux).")
except pygame.error as e:
    print(f"Main Warning: pygame.scrap module could not be initialized: {e}")
except Exception as e: 
    print(f"Main Warning: An unexpected error occurred during pygame.scrap init: {e}")


_TILE_SIZE_DEFAULT = getattr(C, 'TILE_SIZE', 40)
_LIGHT_BLUE_DEFAULT = getattr(C, 'LIGHT_BLUE', (173, 216, 230))

game_elements: Dict[str, Any] = {
    "player1": None, "player2": None, "camera": None,
    "current_chest": None, "enemy_list": [],
    "platform_sprites": pygame.sprite.Group(),
    "ladder_sprites": pygame.sprite.Group(),
    "hazard_sprites": pygame.sprite.Group(),
    "enemy_sprites": pygame.sprite.Group(),
    "collectible_sprites": pygame.sprite.Group(),
    "projectile_sprites": pygame.sprite.Group(),
    "all_sprites": pygame.sprite.Group(),
    "level_pixel_width": WIDTH_MAIN, 
    "level_min_y_absolute": 0,
    "level_max_y_absolute": HEIGHT_MAIN, 
    "ground_level_y": HEIGHT_MAIN - _TILE_SIZE_DEFAULT,
    "ground_platform_height": _TILE_SIZE_DEFAULT,
    "player1_spawn_pos": (100, HEIGHT_MAIN - (_TILE_SIZE_DEFAULT * 2)),
    "player2_spawn_pos": (150, HEIGHT_MAIN - (_TILE_SIZE_DEFAULT * 2)),
    "enemy_spawns_data_cache": [], 
    "level_background_color": _LIGHT_BLUE_DEFAULT,
    "loaded_map_name": None 
}

if __name__ == "__main__":
    print("MAIN: Starting __main__ execution block.")
    main_clock = pygame.time.Clock()
    app_status = AppStatus()

    fonts: Dict[str, Optional[pygame.font.Font]] = {
        "small": None, "medium": None, "large": None, "debug": None
    }
    try:
        fonts["small"] = pygame.font.Font(None, 28)
        fonts["medium"] = pygame.font.Font(None, 36)
        fonts["large"] = pygame.font.Font(None, 72)
        fonts["debug"] = pygame.font.Font(None, 20) 
        if any(f is None for f in fonts.values()):
            raise pygame.error("One or more default fonts failed to load after init.")
        print("MAIN: Fonts loaded successfully.")
    except pygame.error as e:
        print(f"FATAL MAIN: Font loading error: {e}. Ensure Pygame font module is working.")
        traceback.print_exc()
        app_status.app_running = False 
    except Exception as e: 
        print(f"FATAL MAIN: Unexpected error during font loading: {e}")
        traceback.print_exc()
        app_status.app_running = False


    while app_status.app_running:
        current_screen_width, current_screen_height = screen.get_size()
        pygame.display.set_caption("Platformer Adventure - Main Menu")

        print("\nMAIN: Showing main menu...")
        menu_choice = game_ui.show_main_menu(screen, main_clock, fonts, app_status)
        print(f"MAIN: Main menu choice: '{menu_choice}'")

        if not app_status.app_running or menu_choice == "quit":
            app_status.app_running = False
            break
        
        if menu_choice == "settings":
            print("MAIN: Entering Control Settings screen...")
            settings_ui.show_control_settings_screen(screen, main_clock, fonts, app_status, joystick_handler)
            if not app_status.app_running:
                print("MAIN: App quit during settings.")
                break
            print("MAIN: Exited Control Settings screen. Returning to main menu.")
            continue # Go back to the main menu after settings


        map_to_load_for_game: Optional[str] = None
        if menu_choice in ["couch_play", "host"]:
            print(f"MAIN: Mode '{menu_choice}' requires map selection. Opening map dialog...")
            map_to_load_for_game = game_ui.select_map_dialog(screen, main_clock, fonts, app_status)
            if not app_status.app_running:
                print("MAIN: App quit during map selection.")
                break
            if map_to_load_for_game is None:
                print("MAIN: Map selection cancelled/no maps. Returning to main menu.")
                continue 
            print(f"MAIN: Map selected for '{menu_choice}': '{map_to_load_for_game}'")
            if menu_choice == "host":
                server_state = ServerState() 
                server_state.current_map_name = map_to_load_for_game


        print(f"MAIN: Initializing game elements for mode '{menu_choice}' with map '{map_to_load_for_game if map_to_load_for_game else 'Default/Server-defined'}'...")
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
            print(f"Main Error: Failed to initialize game elements for mode '{menu_choice}' (Map: '{map_to_load_for_game}'). Returning to menu.")
            screen.fill(getattr(C, 'BLACK', (0,0,0))) 
            if fonts.get("medium"):
                err_msg_surf = fonts["medium"].render(f"Error starting {menu_choice} mode. Check logs.", True, getattr(C, 'RED', (255,0,0)))
                screen.blit(err_msg_surf, err_msg_surf.get_rect(center=(current_screen_width//2, current_screen_height//2)))
            pygame.display.flip()
            pygame.time.wait(3000) 
            continue 

        game_elements.update(initialized_elements) 

        if game_elements.get("camera"):
            cam_instance = game_elements["camera"]
            if hasattr(cam_instance, "set_screen_dimensions"):
                 cam_instance.set_screen_dimensions(current_screen_width, current_screen_height)
            else: 
                 cam_instance.screen_width = current_screen_width
                 cam_instance.screen_height = current_screen_height
                 if hasattr(cam_instance, 'camera_rect'):
                    cam_instance.camera_rect.width = current_screen_width
                    cam_instance.camera_rect.height = current_screen_height
            print(f"MAIN: Camera screen dimensions updated to {current_screen_width}x{current_screen_height} for mode '{menu_choice}'")


        print(f"MAIN: Launching game mode: '{menu_choice}'")
        if menu_choice == "host":
            if 'server_state' not in locals() or server_state.current_map_name != map_to_load_for_game :
                print("MAIN Warning: ServerState not initialized or map mismatch for host mode. Re-initializing.")
                server_state = ServerState()
                server_state.current_map_name = map_to_load_for_game

            server_state.app_running = app_status.app_running 
            run_server_mode(screen, main_clock, fonts, game_elements, server_state)
            app_status.app_running = server_state.app_running 
        elif menu_choice == "join_lan":
            client_state = ClientState()
            client_state.app_running = app_status.app_running
            run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=None)
            app_status.app_running = client_state.app_running
        elif menu_choice == "join_ip":
            print("MAIN: Requesting IP input for 'join_ip' mode...")
            target_ip_input = game_ui.get_server_ip_input_dialog(screen, main_clock, fonts, app_status, default_input_text="127.0.0.1:5555")
            print(f"MAIN: IP input dialog returned: '{target_ip_input}'")
            if target_ip_input and app_status.app_running:
                client_state = ClientState()
                client_state.app_running = app_status.app_running
                run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=target_ip_input)
                app_status.app_running = client_state.app_running
            elif not app_status.app_running:
                print("MAIN: IP input cancelled or app quit during dialog.")
            else:
                print("MAIN: No IP entered. Returning to main menu.")
        elif menu_choice == "couch_play":
            run_couch_play_mode(screen, main_clock, fonts, game_elements, app_status)

        print(f"MAIN: Returned from game mode '{menu_choice}'. App running: {app_status.app_running}")

    print("MAIN: Exiting application loop gracefully.")
    joystick_handler.quit_joysticks() # Uninitialize joysticks
    pygame.quit()
    if SCRAP_INITIALIZED_MAIN and pygame.scrap.get_init(): 
        try:
            pygame.scrap.quit()
            print("Main: pygame.scrap quit successfully.")
        except Exception as e:
            print(f"Main Warning: Error during pygame.scrap.quit(): {e}")
    print("MAIN: Application terminated.")
    sys.exit(0)