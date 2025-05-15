# main.py
# -*- coding: utf-8 -*-
## version 1.0.0.7 (Integrated logger.py)
import sys
import os
import pygame
import traceback 
from typing import Dict, Optional, Any

# --- Logger Setup ---
try:
    import logger # Import your new logger module
    logger.info("MAIN: Application starting.") # First log from main
except ImportError:
    # Fallback basic print if logger fails, though it shouldn't if in same dir
    print("FATAL MAIN: logger.py not found. Exiting.")
    sys.exit(1)
except Exception as e:
    print(f"FATAL MAIN: Error importing logger: {e}")
    sys.exit(1)


# --- Pyperclip Check ---
PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    logger.info("Pyperclip library found and imported successfully for main.")
except ImportError:
    logger.warning("Main: Pyperclip library not found (pip install pyperclip). Paste in UI may be limited.")

# --- Platformer Game Module Imports ---
try:
    import constants as C 
    from camera import Camera
    from items import Chest
    from game_setup import initialize_game_elements 
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode
    from couch_play_logic import run_couch_play_mode
    import game_ui 

    logger.info("Platformer modules imported successfully.")
except ImportError as e:
    logger.critical(f"FATAL MAIN: Failed to import a required platformer module: {e}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    logger.critical(f"FATAL MAIN: An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Pygame Initialization ---
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0' 
pygame.init() 
pygame.font.init() 

class AppStatus:
    def __init__(self):
        self.app_running = True

def ensure_maps_directory_exists():
    """Ensures the MAPS_DIR exists, creating it if necessary."""
    maps_dir = C.MAPS_DIR
    if not os.path.exists(maps_dir):
        try:
            os.makedirs(maps_dir)
            logger.info(f"MAIN: Created maps directory at '{maps_dir}'")
        except OSError as e:
            logger.error(f"MAIN Error: Could not create maps directory '{maps_dir}': {e}")
            # Depending on severity, you might want to exit or degrade functionality
            return False
    return True


# --- Display Setup ---
try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w
    monitor_height = display_info.current_h
    initial_width = max(800, min(1600, monitor_width * 3 // 4))
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    WIDTH_MAIN, HEIGHT_MAIN = initial_width, initial_height 
    screen_flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH_MAIN, HEIGHT_MAIN), screen_flags)
    pygame.display.set_caption("Platformer Adventure LAN")
    logger.info(f"Initial window dimensions: {WIDTH_MAIN}x{HEIGHT_MAIN}")
except Exception as e:
    logger.critical(f"FATAL MAIN: Error setting up Pygame display: {e}")
    pygame.quit()
    sys.exit(1)

# --- Pygame Scrap Initialization ---
SCRAP_INITIALIZED_MAIN = False
try:
    if pygame.display.get_init(): 
        pygame.scrap.init() 
        SCRAP_INITIALIZED_MAIN = pygame.scrap.get_init()
        if SCRAP_INITIALIZED_MAIN: logger.info("Main: pygame.scrap clipboard module initialized successfully.")
        else: logger.warning("Main Warning: pygame.scrap.init() called but pygame.scrap.get_init() returned False.")
    else: logger.warning("Main Warning: Display not initialized before pygame.scrap.init() attempt.")
except AttributeError: logger.warning("Main Warning: pygame.scrap module not found or available on this system.")
except pygame.error as e: logger.warning(f"Main Warning: pygame.scrap module could not be initialized: {e}")
except Exception as e: logger.warning(f"Main Warning: An unexpected error occurred during pygame.scrap init: {e}")


_TILE_SIZE_DEFAULT = 40 
_LIGHT_BLUE_DEFAULT = (173, 216, 230)
game_elements: Dict[str, Any] = {
    "player1": None, "player2": None, "camera": None, "current_chest": None, "enemy_list": [],
    "platform_sprites": pygame.sprite.Group(), "ladder_sprites": pygame.sprite.Group(),
    "hazard_sprites": pygame.sprite.Group(), "enemy_sprites": pygame.sprite.Group(),
    "collectible_sprites": pygame.sprite.Group(), "projectile_sprites": pygame.sprite.Group(),
    "all_sprites": pygame.sprite.Group(), "level_pixel_width": WIDTH_MAIN, 
    "level_min_y_absolute": 0, "level_max_y_absolute": HEIGHT_MAIN,
    "ground_level_y": HEIGHT_MAIN - getattr(C, 'TILE_SIZE', _TILE_SIZE_DEFAULT),
    "ground_platform_height": getattr(C, 'TILE_SIZE', _TILE_SIZE_DEFAULT),
    "player1_spawn_pos": (100, HEIGHT_MAIN - (getattr(C, 'TILE_SIZE', _TILE_SIZE_DEFAULT) * 2)),
    "player2_spawn_pos": (150, HEIGHT_MAIN - (getattr(C, 'TILE_SIZE', _TILE_SIZE_DEFAULT) * 2)),
    "enemy_spawns_data_cache": [], "level_background_color": getattr(C, 'LIGHT_BLUE', _LIGHT_BLUE_DEFAULT),
    "loaded_map_name": None # Added to store the name of the map that was loaded
}

if __name__ == "__main__":
    logger.info("MAIN: Starting __main__ execution block.")
    main_clock = pygame.time.Clock()
    app_status = AppStatus()

    if not ensure_maps_directory_exists(): # Create maps dir at startup
        logger.critical("MAIN: Failed to ensure maps directory exists. Game may not function correctly for map loading/downloading.")
        # Optionally, quit if maps dir is critical and cannot be created.
        # app_status.app_running = False 

    fonts: Dict[str, Optional[pygame.font.Font]] = {"small": None, "medium": None, "large": None, "debug": None}
    try:
        fonts["small"] = pygame.font.Font(None, 28)
        fonts["medium"] = pygame.font.Font(None, 36)
        fonts["large"] = pygame.font.Font(None, 72)
        fonts["debug"] = pygame.font.Font(None, 20)
        if any(f is None for f in fonts.values()):
            raise pygame.error("One or more default fonts failed to load after init.")
        logger.info("MAIN: Fonts loaded successfully.")
    except pygame.error as e:
        logger.critical(f"FATAL MAIN: Font loading error: {e}. Ensure Pygame font module is working.")
        app_status.app_running = False 
    except Exception as e:
        logger.critical(f"FATAL MAIN: Unexpected error during font loading: {e}")
        app_status.app_running = False

    while app_status.app_running:
        current_screen_width, current_screen_height = screen.get_size()
        pygame.display.set_caption("Platformer Adventure - Main Menu")
        
        logger.info("\nMAIN: Showing main menu...") 
        menu_choice = game_ui.show_main_menu(screen, main_clock, fonts, app_status)
        logger.info(f"MAIN: Main menu choice: '{menu_choice}'")
        
        if not app_status.app_running or menu_choice == "quit":
            app_status.app_running = False; break 

        map_to_load_for_game: Optional[str] = None 
        if menu_choice in ["couch_play", "host"]:
            logger.info(f"MAIN: Mode '{menu_choice}' requires map selection. Opening map dialog...")
            map_to_load_for_game = game_ui.select_map_dialog(screen, main_clock, fonts, app_status)
            if not app_status.app_running: logger.info("MAIN: App quit during map selection."); break 
            if map_to_load_for_game is None:
                logger.info("MAIN: Map selection cancelled/no maps. Returning to main menu."); continue 
            logger.info(f"MAIN: Map selected for '{menu_choice}': '{map_to_load_for_game}'")
        
        # For client modes, map_module_name is initially None. Client will determine map from server.
        # For host/couch, map_to_load_for_game will have the selected map name.
        initial_map_name_for_setup = map_to_load_for_game if menu_choice in ["host", "couch_play"] else None

        logger.info(f"MAIN: Initializing game elements for mode '{menu_choice}' with map '{initial_map_name_for_setup if initial_map_name_for_setup else 'To be determined by server (for client)'}'...")
        
        initialized_elements = initialize_game_elements( 
            current_screen_width, current_screen_height, 
            for_game_mode=menu_choice,
            existing_sprites_groups={ 
                "all_sprites": game_elements["all_sprites"], "projectile_sprites": game_elements["projectile_sprites"],
                "player1": game_elements.get("player1"), "player2": game_elements.get("player2"),
                "current_chest": game_elements.get("current_chest")
            },
            map_module_name=initial_map_name_for_setup # Pass None for client, selected map for host/couch
        )

        if initialized_elements is None:
            logger.error(f"Main Error: Failed to initialize game elements for mode '{menu_choice}' (Map: '{initial_map_name_for_setup}'). Returning to menu.")
            screen.fill(getattr(C, 'BLACK', (0,0,0))) 
            if fonts.get("medium"):
                err_msg_surf = fonts["medium"].render(f"Error starting {menu_choice} mode.", True, getattr(C, 'RED', (255,0,0)))
                screen.blit(err_msg_surf, err_msg_surf.get_rect(center=(current_screen_width//2, current_screen_height//2)))
            pygame.display.flip(); pygame.time.wait(3000); continue

        game_elements.update(initialized_elements)
        
        if game_elements.get("camera"):
            cam_instance = game_elements["camera"]
            if hasattr(cam_instance, "set_screen_dimensions"):
                 cam_instance.set_screen_dimensions(current_screen_width, current_screen_height)
            else: 
                 cam_instance.screen_width, cam_instance.screen_height = current_screen_width, current_screen_height
                 if hasattr(cam_instance, 'camera_rect'):
                    cam_instance.camera_rect.width, cam_instance.camera_rect.height = current_screen_width, current_screen_height
            logger.info(f"MAIN: Camera screen dimensions updated to {current_screen_width}x{current_screen_height}")

        logger.info(f"MAIN: Launching game mode: '{menu_choice}'")
        if menu_choice == "host":
            server_state = ServerState()
            server_state.app_running = app_status.app_running 
            server_state.current_map_name = game_elements.get("loaded_map_name") # Get from initialized_elements
            run_server_mode(screen, main_clock, fonts, game_elements, server_state)
            app_status.app_running = server_state.app_running
        elif menu_choice == "join_lan":
            client_state = ClientState(); client_state.app_running = app_status.app_running
            run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=None) 
            app_status.app_running = client_state.app_running
        elif menu_choice == "join_ip":
            logger.info("MAIN: Requesting IP input for 'join_ip' mode...")
            target_ip_input = game_ui.get_server_ip_input_dialog(screen, main_clock, fonts, app_status, default_input_text="127.0.0.1:5555")
            logger.info(f"MAIN: IP input dialog returned: '{target_ip_input}'")
            if target_ip_input and app_status.app_running: 
                client_state = ClientState(); client_state.app_running = app_status.app_running
                run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=target_ip_input) 
                app_status.app_running = client_state.app_running
            elif not app_status.app_running: logger.info("MAIN: IP input cancelled or app quit during dialog.")
            else: logger.info("MAIN: No IP entered. Returning to main menu.")
        elif menu_choice == "couch_play":
            run_couch_play_mode(screen, main_clock, fonts, game_elements, app_status) 
        
        logger.info(f"MAIN: Returned from game mode '{menu_choice}'. App running: {app_status.app_running}")

    logger.info("MAIN: Exiting application loop gracefully.")
    pygame.quit()
    if SCRAP_INITIALIZED_MAIN and pygame.scrap.get_init():
        try: pygame.scrap.quit(); logger.info("Main: pygame.scrap quit successfully.")
        except Exception as e: logger.warning(f"Main Warning: Error during pygame.scrap.quit(): {e}")
    logger.info("MAIN: Application terminated.")
    sys.exit(0)