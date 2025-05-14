# main.py
# -*- coding: utf-8 -*-
## version 1.0.0.3 (Moved pygame.scrap.init(), updated game_elements keys, camera screen update)
# -*- coding: utf-8 -*-
import sys
import os
import pygame
import traceback # For detailed error logging

# --- Pyperclip Check ---
PYPERCLIP_AVAILABLE_MAIN = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_MAIN = True
    print("Pyperclip library found and imported successfully for main.")
except ImportError:
    print("Main: Pyperclip library not found (pip install pyperclip). Paste in UI may be limited.")

# --- Platformer Game Module Imports ---
try:
    import constants as C
    from camera import Camera
    from items import Chest
    import levels as LevelLoader
    from game_setup import initialize_game_elements
    from server_logic import ServerState, run_server_mode
    from client_logic import ClientState, run_client_mode
    from couch_play_logic import run_couch_play_mode
    import game_ui # For main menu, input dialog, and scene drawing

    print("Platformer modules imported successfully.")
except ImportError as e:
    print(f"FATAL MAIN: Failed to import a required platformer module: {e}")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"FATAL MAIN: An unexpected error occurred during platformer module imports: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Pygame Initialization ---
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0' # Attempt to position window at top-left
pygame.init() # Initialize all Pygame modules (sound, font, etc.)
pygame.font.init() # Explicitly initialize font module

# --- Application State Object ---
class AppStatus:
    """Simple object to hold the global application running flag."""
    def __init__(self):
        self.app_running = True

# --- Display Setup ---
try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w
    monitor_height = display_info.current_h
    initial_width = max(800, min(1600, monitor_width * 3 // 4))
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    WIDTH, HEIGHT = initial_width, initial_height
    screen_flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH, HEIGHT), screen_flags)
    pygame.display.set_caption("Platformer Adventure LAN")
    print(f"Initial window dimensions: {WIDTH}x{HEIGHT}")
except Exception as e:
    print(f"FATAL MAIN: Error setting up Pygame display: {e}")
    pygame.quit()
    sys.exit(1)

# --- Pygame Scrap Initialization (AFTER display is set up) ---
SCRAP_INITIALIZED_MAIN = False
try:
    pygame.scrap.init() 
    SCRAP_INITIALIZED_MAIN = pygame.scrap.get_init()
    if SCRAP_INITIALIZED_MAIN: print("Main: pygame.scrap clipboard module initialized successfully.")
    else: print("Main Warning: pygame.scrap initialized but status check failed (video system likely not ready when first called).")
except AttributeError: 
    print("Main Warning: pygame.scrap module not found or available on this system.")
except pygame.error as e: # Catches specific Pygame errors, e.g., "video system not initialized"
    print(f"Main Warning: pygame.scrap module could not be initialized: {e}")
except Exception as e: 
    print(f"Main Warning: An unexpected error occurred during pygame.scrap init: {e}")


# --- Global Game Variables (managed primarily within game modes) ---
game_elements = {
    "player1": None, "player2": None, "camera": None,
    "current_chest": None, "enemy_list": [],
    "platform_sprites": pygame.sprite.Group(),
    "ladder_sprites": pygame.sprite.Group(),
    "hazard_sprites": pygame.sprite.Group(),
    "enemy_sprites": pygame.sprite.Group(),
    "collectible_sprites": pygame.sprite.Group(),
    "projectile_sprites": pygame.sprite.Group(),
    "all_sprites": pygame.sprite.Group(),
    # These will be properly updated by initialize_game_elements from level data
    "level_pixel_width": WIDTH, 
    "level_min_y_absolute": 0, 
    "level_max_y_absolute": HEIGHT,
    "ground_level_y": HEIGHT - C.TILE_SIZE if 'C' in globals() and C.TILE_SIZE else HEIGHT - 40,
    "ground_platform_height": C.TILE_SIZE if 'C' in globals() and C.TILE_SIZE else 40,
    "player1_spawn_pos": (100, HEIGHT - (C.TILE_SIZE*2 if 'C' in globals() and C.TILE_SIZE else 80)),
    "player2_spawn_pos": (150, HEIGHT - (C.TILE_SIZE*2 if 'C' in globals() and C.TILE_SIZE else 80)),
    "enemy_spawns_data_cache": []
}

# --- Main Execution ---
if __name__ == "__main__":
    main_clock = pygame.time.Clock()
    app_status = AppStatus()

    fonts = {
        "small": None, "medium": None, "large": None, "debug": None
    }
    try:
        fonts["small"] = pygame.font.Font(None, 28)
        fonts["medium"] = pygame.font.Font(None, 36)
        fonts["large"] = pygame.font.Font(None, 72)
        fonts["debug"] = pygame.font.Font(None, 20)
        if any(f is None for f in fonts.values()): # Check if any font failed to load
            raise pygame.error("One or more default fonts failed to load.")
        print("Fonts loaded successfully.")
    except pygame.error as e:
        print(f"FATAL MAIN: Font loading error: {e}. Ensure Pygame font module is working.")
        app_status.app_running = False 
    except Exception as e:
        print(f"FATAL MAIN: Unexpected error during font loading: {e}")
        app_status.app_running = False

    # --- Main Application Loop ---
    while app_status.app_running:
        current_screen_width, current_screen_height = screen.get_size()
        pygame.display.set_caption("Platformer Adventure - Main Menu")
        
        menu_choice = game_ui.show_main_menu(screen, main_clock, fonts, app_status)
        
        if not app_status.app_running or menu_choice == "quit":
            app_status.app_running = False
            break

        initialized_elements = initialize_game_elements(
            current_screen_width, current_screen_height, 
            for_game_mode=menu_choice,
            existing_sprites_groups={ 
                "all_sprites": game_elements["all_sprites"],
                "projectile_sprites": game_elements["projectile_sprites"],
                "player1": game_elements.get("player1"), 
                "player2": game_elements.get("player2"),
                "current_chest": game_elements.get("current_chest")
            }
        )

        if initialized_elements is None:
            print(f"Main Error: Failed to initialize game elements for mode '{menu_choice}'. Returning to menu.")
            # Use getattr for constants in case C failed to load, providing a fallback
            screen.fill(getattr(C, 'BLACK', (0,0,0))) 
            if fonts.get("medium"):
                err_text = f"Error starting {menu_choice} mode."
                err_color = getattr(C, 'RED', (255,0,0))
                err_surf = fonts["medium"].render(err_text, True, err_color)
                screen.blit(err_surf, err_surf.get_rect(center=(current_screen_width//2, current_screen_height//2)))
            pygame.display.flip()
            pygame.time.wait(3000)
            continue

        game_elements.update(initialized_elements)
        
        # Ensure camera knows about current screen dimensions, especially after potential resize
        if game_elements.get("camera"):
            # The camera was initialized with screen_width/height from initialize_game_elements
            # but if the screen was resized *while in the menu*, this updates it.
            if hasattr(game_elements["camera"], "set_screen_dimensions"):
                 game_elements["camera"].set_screen_dimensions(current_screen_width, current_screen_height)
            else: # Fallback if method doesn't exist (older camera version)
                 game_elements["camera"].screen_width = current_screen_width
                 game_elements["camera"].screen_height = current_screen_height
                 game_elements["camera"].camera_rect.width = current_screen_width
                 game_elements["camera"].camera_rect.height = current_screen_height


        # --- Launch the selected game mode ---
        if menu_choice == "host":
            server_state = ServerState() 
            server_state.app_running = app_status.app_running 
            run_server_mode(screen, main_clock, fonts, game_elements, server_state)
            app_status.app_running = server_state.app_running
        
        elif menu_choice == "join_lan":
            client_state = ClientState() 
            client_state.app_running = app_status.app_running
            run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=None)
            app_status.app_running = client_state.app_running
            
        elif menu_choice == "join_ip":
            target_ip_input = game_ui.get_server_ip_input_dialog( 
                screen, main_clock, fonts, app_status, default_input_text="127.0.0.1:5555" # MODIFIED HERE
            )
            if target_ip_input and app_status.app_running: 
                client_state = ClientState()
                client_state.app_running = app_status.app_running
                run_client_mode(screen, main_clock, fonts, game_elements, client_state, target_ip_port_str=target_ip_input)
                app_status.app_running = client_state.app_running
            elif not app_status.app_running: 
                 print("Main: IP input cancelled due to application quit.")
                 break 
            
        elif menu_choice == "couch_play":
            run_couch_play_mode(screen, main_clock, fonts, game_elements, app_status)

    # --- Application Cleanup ---
    print("Main: Exiting application gracefully.")
    pygame.quit()
    if SCRAP_INITIALIZED_MAIN:
        try:
            if pygame.scrap.get_init(): # Check again before quitting
                pygame.scrap.quit()
        except Exception as e: # Catch any error during scrap.quit
            print(f"Main Warning: Error during pygame.scrap.quit(): {e}")
    sys.exit(0)