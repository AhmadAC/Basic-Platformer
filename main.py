# main.py
# Run this code
# -*- coding: utf-8 -*-
import pygame
import sys
import os
import math # Keep math
import random
import socket
import threading
import time
import json
import traceback

# --- Pyperclip Check ---
PYPERCLIP_AVAILABLE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
    print("Pyperclip library found and imported successfully.")
except ImportError:
    print("Warning: Pyperclip library not found (pip install pyperclip).")

# --- Platformer Imports ---
try:
    import constants as C
    from player import Player 
    from enemy import Enemy # This should be your latest enemy.py
    from tiles import Platform, Ladder, Lava 
    from camera import Camera
    try:
        from items import Chest
    except ImportError:
        print("Warning: items.py or Chest class not found. Chests will not be available.")
        Chest = None
    import levels as LevelLoader
    import ui
    print("Platformer modules imported successfully.")
except ImportError as e:
    print(f"FATAL: Failed to import platformer module: {e}")
    print("Ensure player.py, enemy.py, tiles.py, levels.py, ui.py, camera.py, constants.py are present.")
    sys.exit(1)
except Exception as e:
    print(f"FATAL: Error during platformer module import: {e}")
    sys.exit(1)
    
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0' # Attempt to position window at top-left
# --- Pygame Init ---
pygame.init()
pygame.font.init()

# --- Pygame Scrap Init ---
SCRAP_INITIALIZED = False
try:
    pygame.scrap.init()
    SCRAP_INITIALIZED = pygame.scrap.get_init()
    if SCRAP_INITIALIZED: print("Clipboard (pygame.scrap) module initialized successfully.")
    else: print("Warning: pygame.scrap module initialized but status check failed.")
except pygame.error as e: print(f"Warning: pygame.scrap module could not be initialized: {e}")
except AttributeError: print(f"Warning: pygame.scrap module not found or available on this system.")
except Exception as e: print(f"Warning: An unexpected error occurred during pygame.scrap init: {e}")

# --- Constants & Globals ---
SERVER_IP_BIND = '0.0.0.0' # Listen on all available interfaces for server
SERVER_PORT_TCP = 5555
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 4096 # Increased buffer for potentially larger game states
BROADCAST_INTERVAL_S = 1.0 # How often server broadcasts its presence
CLIENT_SEARCH_TIMEOUT_S = 5.0 # How long client searches for LAN servers
SERVICE_NAME = "platformer_adventure_lan_v1" # Unique name for LAN discovery

try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w; monitor_height = display_info.current_h
    # Set initial window size to be a portion of the monitor, with min/max
    initial_width = max(800, min(1600, monitor_width * 3 // 4))
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    WIDTH = initial_width; HEIGHT = initial_height
    flags = pygame.RESIZABLE | pygame.DOUBLEBUF # Enable resizable window and double buffering
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    print(f"Initial window: {WIDTH}x{HEIGHT}")
except Exception as e: print(f"Error setting up display: {e}"); pygame.quit(); sys.exit()

clock = None # Pygame clock, initialized in main
font_small, font_medium, font_large, debug_font = None, None, None, None # Fonts
app_running = True # Main loop control flag

# Network related globals
server_tcp_socket, server_udp_socket, client_connection, client_address = None, None, None, None
client_input_buffer = {}; client_state_buffer = b""; client_lock = threading.Lock()
broadcast_thread, client_handler_thread = None, None
client_tcp_socket = None; server_state_buffer = b"" # For client mode

# Game element globals
player1, player2, camera, current_chest = None, None, None, None
platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, all_sprites = \
    pygame.sprite.Group(), pygame.sprite.Group(), pygame.sprite.Group(), \
    pygame.sprite.Group(), pygame.sprite.Group(), pygame.sprite.Group()
enemy_list = [] # Keep a list for easier iteration with IDs
level_pixel_width, level_pixel_height = WIDTH, HEIGHT # Dimensions of the entire level
ground_level_y, ground_platform_height = HEIGHT - 40, 40 # Default ground
player1_spawn_pos, player2_spawn_pos = (100, HEIGHT - 80), (150, HEIGHT - 80)
enemy_spawns_data = [] # Loaded from level file

# --- Helper Functions (Network) ---
def get_local_ip():
    """Attempts to get the primary local IP address."""
    best_ip = '127.0.0.1' # Default fallback
    try: # Try connecting to an external IP to determine local interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        best_ip = s.getsockname()[0]; s.close()
    except Exception:
        try: best_ip = socket.gethostbyname(socket.gethostname()) # Fallback
        except Exception: best_ip = '127.0.0.1' # Ultimate fallback
    return best_ip

def encode_data(data):
    """Encodes a Python dictionary to JSON bytes with a newline terminator."""
    try: return json.dumps(data).encode('utf-8') + b'\n'
    except TypeError as e: print(f"Encoding Error: {e} Data: {str(data)[:100]}"); return None
    except Exception as e: print(f"Unexpected Encoding Error: {e}"); return None

def decode_data_stream(byte_buffer):
    """Decodes newline-terminated JSON objects from a byte buffer."""
    decoded_objects, remaining_buffer = [], byte_buffer
    while b'\n' in remaining_buffer:
        message, remaining_buffer = remaining_buffer.split(b'\n', 1)
        if not message: continue # Skip empty messages (e.g., if multiple newlines)
        try: decoded_objects.append(json.loads(message.decode('utf-8')))
        except Exception: continue # Ignore malformed JSON messages silently for now
    return decoded_objects, remaining_buffer

# --- Platformer Specific Helper Functions ---
def initialize_platformer_elements(for_game_mode="unknown"):
    global platform_sprites, ladder_sprites, hazard_sprites, enemy_spawns_data, \
           player1_spawn_pos, player2_spawn_pos, level_pixel_width, level_pixel_height, ground_level_y, \
           ground_platform_height, all_sprites, enemy_sprites, \
           collectible_sprites, player1, player2, enemy_list, \
           current_chest, WIDTH, HEIGHT, camera

    print(f"Initializing platformer elements for mode: {for_game_mode}...")
    # Clear existing game objects
    if player1: player1.kill(); player1 = None
    if player2: player2.kill(); player2 = None
    if current_chest: current_chest.kill(); current_chest = None
    for sprite in all_sprites: sprite.kill() # Ensure all sprites are removed from groups
    all_sprites.empty(); platform_sprites.empty(); ladder_sprites.empty(); hazard_sprites.empty()
    enemy_sprites.empty(); collectible_sprites.empty(); enemy_list.clear()

    print("Loading level data via LevelLoader...")
    try:
        # Load level data (platforms, hazards, spawns, etc.)
        platform_data_group, ladder_data_group, hazard_data_group, enemy_spawns_data_list, \
        p1_spawn_tuple, lvl_width_pixels, ground_y_coord, ground_h_pixels = \
            LevelLoader.load_map_cpu(WIDTH, HEIGHT) # Assuming load_map_cpu is the intended function
        
        enemy_spawns_data = enemy_spawns_data_list # Store raw spawn data for client reconstruction
        
        platform_sprites.add(platform_data_group.sprites()) # Add loaded sprites to groups
        ladder_sprites.add(ladder_data_group.sprites())
        hazard_sprites.add(hazard_data_group.sprites())
        player1_spawn_pos = p1_spawn_tuple
        player2_spawn_pos = (p1_spawn_tuple[0] + 60, p1_spawn_tuple[1]) # Offset P2 spawn
        level_pixel_width = lvl_width_pixels; 
        level_pixel_height = HEIGHT # Assume level height matches screen height for now
        ground_level_y = ground_y_coord; ground_platform_height = ground_h_pixels
        print("Level geometry loaded.")
    except Exception as e: print(f"CRITICAL ERROR loading level: {e}"); traceback.print_exc(); return False

    all_sprites.add(platform_sprites.sprites(), ladder_sprites.sprites(), hazard_sprites.sprites())

    # Initialize players based on game mode
    if for_game_mode in ["host", "couch_play", "single_player"]: # Modes where P1 is local
        print("Initializing player 1..."); player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 init failed."); return False
        all_sprites.add(player1); print("P1 initialized.")
    
    if for_game_mode == "couch_play":
        print("Initializing player 2 (couch)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (couch) init failed."); return False
        all_sprites.add(player2); print("P2 (couch) initialized.")
    elif for_game_mode == "host": # P2 is remote, create a placeholder
        print("Initializing player 2 (remote placeholder)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (remote) init failed."); return False
        all_sprites.add(player2); print("P2 (remote) initialized.")
    elif for_game_mode == "client": # P1 is remote (placeholder), P2 is local
        print("Initializing player 1 (remote placeholder)..."); player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 (remote) init failed."); return False
        all_sprites.add(player1); print("P1 (remote) initialized.")
        print("Initializing player 2 (local client)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (local client) init failed."); return False
        all_sprites.add(player2); print("P2 (local client) initialized.")

    # Spawn enemies (relevant for server/host and single/couch modes)
    # Client mode will receive enemy data from server
    enemy_list.clear() # Ensure list is empty before repopulating
    if for_game_mode in ["host", "couch_play", "single_player"]:
        print(f"Spawning {len(enemy_spawns_data)} enemies...") 
        for i, spawn_data in enumerate(enemy_spawns_data): # Use enumerate for unique enemy_id
            try:
                # Use patrol data from level file if available
                patrol_rect = pygame.Rect(spawn_data['patrol']) if 'patrol' in spawn_data and spawn_data['patrol'] else None
                enemy = Enemy(spawn_data['pos'][0], spawn_data['pos'][1], patrol_area=patrol_rect, enemy_id=i)
                if enemy._valid_init: 
                    all_sprites.add(enemy)
                    enemy_sprites.add(enemy)
                    enemy_list.append(enemy) # Add to list for ID-based access
                else: print(f"Error: Enemy {i} at {spawn_data['pos']} init failed (invalid enemy init).")
            except Exception as e: print(f"Error spawning enemy {i} at {spawn_data['pos']}: {e}")
        print(f"Enemies spawned: {len(enemy_list)}")

    # Spawn chest (relevant for server/host and single/couch modes)
    if Chest and for_game_mode in ["host", "couch_play", "single_player"]:
        current_chest = spawn_chest_platformer() 
        if current_chest: 
            all_sprites.add(current_chest)
            collectible_sprites.add(current_chest)
    
    camera = Camera(level_pixel_width, level_pixel_height, WIDTH, HEIGHT)
    return True

def spawn_chest_platformer():
    global platform_sprites, collectible_sprites, all_sprites, ground_level_y, Chest
    if Chest is None: return None # Chest class not available
    try:
        # Find suitable platforms to spawn chest on (not too low, wide enough)
        valid_plats = [p for p in platform_sprites if p.rect.top < ground_level_y - 50 and p.rect.width > 50]
        if not valid_plats: valid_plats = list(platform_sprites) # Fallback to any platform
        if not valid_plats: print("No valid platforms to spawn chest on."); return None
        
        chosen_platform = random.choice(valid_plats)
        # Spawn chest randomly on the chosen platform
        cx = random.randint(chosen_platform.rect.left + 20, chosen_platform.rect.right - 20)
        cy = chosen_platform.rect.top # Chest's bottom will align with platform top
        new_chest = Chest(cx, cy) # Assuming Chest constructor takes x (center) and y (bottom)
        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
            print(f"Chest object created at ({int(new_chest.rect.centerx)}, {int(new_chest.rect.bottom)}).")
            return new_chest
        else: print("Failed to initialize new chest object (invalid init).")
    except Exception as e: print(f"Error creating new chest object: {e}")
    return None

def reset_platformer_game_state():
    """Resets players, enemies, and chest to their initial states."""
    global player1, player2, enemy_list, current_chest, player1_spawn_pos, player2_spawn_pos, all_sprites, enemy_sprites, collectible_sprites
    print("\n--- Resetting Platformer Game State ---")

    # Reset players
    if player1 and hasattr(player1, 'reset_state'): 
        player1.reset_state(player1_spawn_pos) # Pass spawn position to player's reset
        if not player1.alive() and player1._valid_init: all_sprites.add(player1) # Re-add if killed
        print("P1 Reset")
    if player2 and hasattr(player2, 'reset_state'): 
        player2.reset_state(player2_spawn_pos)
        if not player2.alive() and player2._valid_init: all_sprites.add(player2)
        print("P2 Reset")
    
    # Reset enemies
    for enemy_instance in enemy_list: # Iterate through the master list
        if hasattr(enemy_instance, 'reset'): 
            enemy_instance.reset()
            if enemy_instance._valid_init: # Only proceed if enemy initialized correctly
                if not enemy_instance.alive(): # If it was killed, re-add it to drawing groups
                    all_sprites.add(enemy_instance)
                    enemy_sprites.add(enemy_instance)
                else: # Ensure it's in the groups even if it wasn't killed (e.g. for consistency)
                    all_sprites.add(enemy_instance) # add() is safe, won't duplicate
                    enemy_sprites.add(enemy_instance)
    print(f"{len(enemy_list)} enemies processed for reset.")
    
    # Respawn chest
    if current_chest and current_chest.alive(): current_chest.kill() # Remove old chest
    current_chest = spawn_chest_platformer() # Spawn a new one
    if current_chest:
        all_sprites.add(current_chest) # Add to appropriate groups
        collectible_sprites.add(current_chest) 
        print("Chest respawned.")
    else:
        print("Failed to respawn chest or Chest class not available.")
    print("--- Game State Reset Finished ---\n")

def get_platformer_network_state():
    """Gathers current game state for network transmission."""
    global player1, player2, enemy_list, current_chest
    state = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 'game_over': False}
    if player1 and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()
    
    # Include enemies that are alive and have an ID for mapping
    for enemy in enemy_list: # Iterate through the persistent list
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data') and enemy.alive(): # Only send alive enemies
            state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()
            
    if current_chest and current_chest.alive() and hasattr(current_chest, 'rect'): # Only send if chest exists and alive
        state['chest'] = {'pos': (current_chest.rect.centerx, current_chest.rect.centery), 
                          'is_collected': getattr(current_chest, 'is_collected', False)}
    
    # Determine game_over status (e.g., if P1 is truly gone)
    p1_truly_gone = True # Assume P1 is gone
    if player1 and player1._valid_init:
        if player1.alive(): # If P1 is in sprite groups
            if hasattr(player1, 'is_dead') and player1.is_dead:
                # If P1 is dead but death animation not finished, game is not over yet
                if hasattr(player1, 'death_animation_finished') and not player1.death_animation_finished:
                    p1_truly_gone = False 
            else: # P1 is alive and not dead
                p1_truly_gone = False
        # If P1 not alive but was valid, means P1 was killed and removed (game over)
        
    state['game_over'] = p1_truly_gone 
    return state

def set_platformer_network_state(network_state):
    """Updates local game state based on received network data (for client)."""
    global player1, player2, enemy_list, enemy_sprites, current_chest, all_sprites, collectible_sprites, Chest, enemy_spawns_data
    
    # Update players
    if player1 and 'p1' in network_state and network_state['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state['p1'])
        if player1._valid_init and not player1.alive(): all_sprites.add(player1) # Re-add if necessary
    if player2 and 'p2' in network_state and network_state['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state['p2'])
        if player2._valid_init and not player2.alive(): all_sprites.add(player2) 

    # Update enemies (more complex due to dynamic creation/deletion)
    if 'enemies' in network_state:
        received_enemy_data_map = network_state['enemies'] # Enemies from server {id_str: data}
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        # Update existing enemies or create new ones if they appear in server state
        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str) # Convert ID to int for comparison/indexing
            if enemy_data_from_server.get('_valid_init', False): # Only process if server says enemy is valid
                if enemy_id_str in current_client_enemies_map: # Enemy exists on client
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    if hasattr(client_enemy, 'set_network_data'): 
                        client_enemy.set_network_data(enemy_data_from_server)
                        # Re-add to groups if it became un-alive due to network state but should be
                        if not client_enemy.alive() and client_enemy._valid_init and not client_enemy.is_dead: 
                            all_sprites.add(client_enemy)
                            enemy_sprites.add(client_enemy)
                else: # Enemy is new to the client, create it
                    print(f"Client: Creating new enemy {enemy_id_str} from server state.")
                    try:
                        spawn_pos_e = enemy_data_from_server.get('pos', (0,0)) # Default spawn if not in data
                        patrol_area_e = None # Default
                        # Try to find original spawn data for patrol area if available
                        matching_spawn_data = next((sd for sd_idx, sd in enumerate(enemy_spawns_data) if sd_idx == enemy_id_int), None)
                        if matching_spawn_data: patrol_area_e = pygame.Rect(matching_spawn_data['patrol']) if 'patrol' in matching_spawn_data else None

                        new_enemy = Enemy(spawn_pos_e[0], spawn_pos_e[1], 
                                          patrol_area=patrol_area_e, 
                                          enemy_id=enemy_id_int) # Use the correct ID
                        if new_enemy._valid_init:
                            new_enemy.set_network_data(enemy_data_from_server) # Apply detailed state
                            all_sprites.add(new_enemy); enemy_sprites.add(new_enemy); enemy_list.append(new_enemy)
                        else: print(f"Client: Failed to initialize new enemy {enemy_id_str} from server.")
                    except Exception as e: print(f"Client: Error creating new enemy {enemy_id_str}: {e}")
            elif enemy_id_str in current_client_enemies_map: # Server says enemy is not valid (e.g. should be removed)
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

        # Remove enemies on client that are no longer in server state
        server_enemy_ids = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove = set(current_client_enemies_map.keys()) - server_enemy_ids
        for removed_id_str in client_enemy_ids_to_remove:
            if removed_id_str in current_client_enemies_map:
                enemy_to_remove = current_client_enemies_map[removed_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

    # Update chest
    if 'chest' in network_state:
        chest_data = network_state['chest']
        if chest_data and Chest is not None: # Chest exists in server state and Chest class is available
            chest_pos_center = chest_data.get('pos'); chest_is_collected = chest_data.get('is_collected', False)
            if chest_is_collected: # If server says collected
                if current_chest and current_chest.alive(): current_chest.kill(); current_chest = None
            elif chest_pos_center: # Chest exists and not collected, ensure client has it
                if not current_chest or not current_chest.alive(): # If client doesn't have a chest or it's dead
                    if current_chest: current_chest.kill() # Remove old one just in case
                    try:
                        # Estimate height to convert center to bottom for constructor
                        temp_chest_height_approx = getattr(Chest(0,0).image, 'get_height', lambda: 30)() 
                        chest_spawn_x_mid = chest_pos_center[0]
                        chest_spawn_y_bottom = chest_pos_center[1] + temp_chest_height_approx / 2
                        new_chest = Chest(chest_spawn_x_mid, chest_spawn_y_bottom)
                        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
                             all_sprites.add(new_chest); collectible_sprites.add(new_chest)
                             current_chest = new_chest
                             if hasattr(current_chest, 'is_collected'): current_chest.is_collected = False # Ensure it's not marked collected locally
                        else: current_chest = None; print("Client: Failed to init chest from net.")
                    except Exception as e: print(f"Client: Error creating chest from net: {e}"); current_chest = None
                elif current_chest: # Client has a chest, make sure its collected status matches server
                    if hasattr(current_chest, 'is_collected'): current_chest.is_collected = False
        elif not network_state.get('chest'): # Server says no chest
            if current_chest and current_chest.alive(): current_chest.kill(); current_chest = None
    
# --- Drawing Function ---
def draw_platformer_scene(target_screen, current_time_ticks):
    global all_sprites, camera, player1, player2, screen, debug_font, WIDTH, HEIGHT, enemy_list
    target_screen.fill(getattr(C, 'LIGHT_BLUE', (135, 206, 235))) # Background color
    if camera:
        # Draw all sprites through the camera
        for entity in all_sprites: 
            if entity.alive() and hasattr(entity, 'image') and hasattr(entity, 'rect'): # Check if sprite is drawable
                 target_screen.blit(entity.image, camera.apply(entity.rect))
        
        # Draw health bars for enemies (if UI module and constants are set)
        for enemy in enemy_list: # Iterate through the master list
            if enemy.alive() and enemy._valid_init and not enemy.is_dead and hasattr(enemy, 'current_health') and hasattr(enemy, 'max_health'):
                enemy_screen_rect = camera.apply(enemy.rect)
                bar_w = getattr(C, 'HEALTH_BAR_WIDTH', 50); bar_h = getattr(C, 'HEALTH_BAR_HEIGHT', 8)
                bar_x = enemy_screen_rect.centerx - bar_w / 2
                bar_y = enemy_screen_rect.top - bar_h - getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5)
                if hasattr(ui, 'draw_health_bar'):
                    ui.draw_health_bar(target_screen, bar_x, bar_y, bar_w, bar_h, enemy.current_health, enemy.max_health)
    else: # Fallback if camera is not initialized (should not happen in game modes)
        all_sprites.draw(target_screen) 

    # Draw Player HUDs
    if hasattr(ui, 'draw_player_hud'):
        if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init: # Check player validity
            ui.draw_player_hud(target_screen, 10, 10, player1, 1) # Player 1 HUD top-left
        if player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init: # Check player validity
            p2_hud_x = WIDTH - (getattr(C, 'HEALTH_BAR_WIDTH', 50) * 2) - 120 # Adjust position for P2 HUD (example)
            ui.draw_player_hud(target_screen, p2_hud_x, 10, player2, 2) # Player 2 HUD top-right
            
def update_camera_platformer(target_focus=None, target2_focus=None):
    """Updates camera based on one or two target players."""
    global camera
    if not camera: return
    actual_target = None
    # Prioritize P1 if valid, else P2 if valid
    if target_focus and target_focus.alive() and hasattr(target_focus, '_valid_init') and target_focus._valid_init and \
       hasattr(target_focus, 'is_dead') and not target_focus.is_dead:
        actual_target = target_focus
    elif target2_focus and target2_focus.alive() and hasattr(target2_focus, '_valid_init') and target2_focus._valid_init and \
         hasattr(target2_focus, 'is_dead') and not target2_focus.is_dead:
        actual_target = target2_focus
    
    if actual_target: camera.update(actual_target) # Camera follows the chosen target
    else: camera.static_update() # No valid target, camera remains static or uses default behavior

# --- Server Functions ---
def broadcast_presence(server_lan_ip):
    """UDP broadcast thread function for server presence."""
    global app_running, server_udp_socket, SERVICE_NAME, SERVER_PORT_TCP, DISCOVERY_PORT_UDP, BROADCAST_INTERVAL_S
    broadcast_message_dict = {"service": SERVICE_NAME, "tcp_ip": server_lan_ip, "tcp_port": SERVER_PORT_TCP}
    broadcast_message_bytes = encode_data(broadcast_message_dict) # Encode once
    if not broadcast_message_bytes: print("Error: Could not encode broadcast message."); return
    try:
        server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); server_udp_socket.settimeout(0.5)
    except socket.error as e: print(f"Error creating UDP broadcast socket: {e}"); server_udp_socket = None; return
    broadcast_address = ('<broadcast>', DISCOVERY_PORT_UDP)
    while app_running:
        try: server_udp_socket.sendto(broadcast_message_bytes[:-1], broadcast_address) # Send without the final newline for UDP
        except socket.error: pass # Ignore send errors (e.g. network down)
        except Exception as e: print(f"Unexpected error during broadcast send: {e}")
        time.sleep(BROADCAST_INTERVAL_S)
    if server_udp_socket: server_udp_socket.close(); server_udp_socket = None

def handle_client_connection(conn, addr):
    """TCP handler thread for a connected client."""
    global client_input_buffer, app_running, client_lock, client_connection, BUFFER_SIZE
    print(f"Client connected via TCP: {addr}"); conn.settimeout(1.0) # Short timeout for recv
    partial_data_from_client = b""
    while app_running:
        with client_lock: # Ensure exclusive access to client_connection
            if client_connection is not conn: break # If another client connected, this thread exits
        try:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk: print(f"Client {addr} disconnected (received empty data)."); break
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            if decoded_inputs:
                last_input_data = decoded_inputs[-1] # Process only the most recent full input message
                if "input" in last_input_data: # Ensure it's an input message
                    with client_lock:
                        if client_connection is conn: client_input_buffer = last_input_data["input"]
        except socket.timeout: continue # No data received, loop again
        except socket.error as e:
            if app_running: print(f"Socket error with client {addr}: {e}. Assuming disconnect."); break
        except Exception as e: 
             if app_running: print(f"Unexpected error handling client {addr}: {e}"); traceback.print_exc(); break
    
    # Cleanup when client disconnects or thread stops
    with client_lock:
        if client_connection is conn: # If this was the active connection
            client_connection = None
            client_input_buffer = {"disconnect": True} # Signal disconnect to main server loop
    try: conn.shutdown(socket.SHUT_RDWR) # Gracefully close connection
    except: pass # Ignore errors on shutdown/close
    try: conn.close()
    except: pass

def run_server_mode():
    global app_running, screen, clock, camera, client_connection, client_address, client_input_buffer, player1, player2, enemy_list, server_tcp_socket, broadcast_thread, client_handler_thread, client_lock, WIDTH, HEIGHT, current_chest, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, all_sprites

    if not initialize_platformer_elements(for_game_mode="host"):
        print("Server: Failed to initialize platformer elements.")
        return 
    
    pygame.display.set_caption("Platformer - HOST (P1: WASD+VB | Self-Harm: H | Heal: G | Reset: R)")
    server_lan_ip = get_local_ip()
    p1_key_map = { # P1 controls for host
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e} 

    # Start UDP broadcast for LAN discovery
    broadcast_thread = threading.Thread(target=broadcast_presence, args=(server_lan_ip,), daemon=True); broadcast_thread.start()
    server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_tcp_socket.bind((SERVER_IP_BIND, SERVER_PORT_TCP)); server_tcp_socket.listen(1) # Listen for 1 client
        server_tcp_socket.settimeout(1.0); print(f"Server TCP listening on {SERVER_IP_BIND}:{SERVER_PORT_TCP}")
    except socket.error as e: print(f"FATAL: Failed to bind TCP socket: {e}"); app_running = False; return

    # Wait for a client to connect
    print("Waiting for Player 2 to connect..."); temp_client_conn = None
    while temp_client_conn is None and app_running: # Loop until client connects or app quits
        try:
            events = pygame.event.get(); # Handle window events while waiting
            for event in events:
                if event.type == pygame.QUIT: app_running = False; break
                if event.type == pygame.VIDEORESIZE: # Handle window resize
                     if not screen.get_flags() & pygame.FULLSCREEN: # Only if not fullscreen
                        try:
                            WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                            screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                            if camera: camera.screen_width = WIDTH; camera.screen_height = HEIGHT # Update camera
                        except pygame.error as e: print(f"Resize error: {e}")
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: app_running = False; break
            if not app_running: break # Exit loop if app quit
            
            # Display "Waiting for P2" message
            screen.fill(C.BLACK); wait_text = font_large.render("Waiting for P2...", True, C.WHITE)
            screen.blit(wait_text, wait_text.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip(); clock.tick(10)
            
            temp_client_conn, temp_client_addr = server_tcp_socket.accept() # Accept connection
            with client_lock: # Thread-safe update of client connection
                 if client_connection: client_connection.close() # Close old connection if any
                 client_connection = temp_client_conn; client_address = temp_client_addr; client_input_buffer = {}
        except socket.timeout: continue # No connection attempt, loop
        except Exception as e: print(f"Error during client wait/accept: {e}"); app_running = False; break 
    
    if not app_running or client_connection is None: print("Exiting server (no client connected or app closed)."); return

    print(f"Client connected: {client_address}. Starting game...")
    # Start thread to handle communication with the connected client
    client_handler_thread = threading.Thread(target=handle_client_connection, args=(client_connection, client_address), daemon=True)
    client_handler_thread.start()

    server_running_game = True
    while server_running_game and app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks = pygame.time.get_ticks()
        p1_events = pygame.event.get(); keys_p1 = pygame.key.get_pressed()
        
        # Determine if game is over from P1's perspective (for P2 reset request)
        game_over_for_p2_reset_request = False 
        if player1 and player1._valid_init:
            if player1.is_dead and (not player1.alive() or (hasattr(player1, 'death_animation_finished') and player1.death_animation_finished)):
                game_over_for_p2_reset_request = True
        else: game_over_for_p2_reset_request = True # If P1 failed init, effectively game over
        
        reset_now_by_host = False

        for event in p1_events:
            if event.type == pygame.QUIT: server_running_game = False; app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    try:
                        WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                        screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                        if camera: camera.screen_width = WIDTH; camera.screen_height = HEIGHT
                    except pygame.error as e: print(f"Resize error: {e}")
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: server_running_game = False 
                if event.key == pygame.K_r: # Host can reset game
                    print("DEBUG: 'R' key pressed (Server Mode) - host requested reset.")
                    reset_now_by_host = True
                # P1 debug controls
                if event.key == pygame.K_h and player1 and player1._valid_init and hasattr(player1, 'self_inflict_damage'):
                    player1.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_g and player1 and player1._valid_init and hasattr(player1, 'heal_to_full'):
                    player1.heal_to_full()

        if not app_running or not server_running_game: break
        
        # Handle P1 input
        if player1 and player1._valid_init and not player1.is_dead: # Only if P1 is alive
            player1.handle_mapped_input(keys_p1, p1_events, p1_key_map)

        # Process client input
        remote_p2_input_copy, client_was_disconnected, reset_req_by_client = None, False, False
        with client_lock: # Thread-safe access to client input buffer
            if client_input_buffer:
                if client_input_buffer.get("disconnect"): client_was_disconnected = True
                elif client_input_buffer.get("action_reset", False): reset_req_by_client = True
                # Handle P2 debug actions from client
                elif client_input_buffer.get("action_self_harm", False) and player2 and player2._valid_init: 
                    player2.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                elif client_input_buffer.get("action_heal", False) and player2 and player2._valid_init: 
                    player2.heal_to_full()
                else: remote_p2_input_copy = client_input_buffer.copy() # Get P2's game inputs
                client_input_buffer = {} # Clear buffer after processing
        
        if client_was_disconnected: print("Client disconnected signal received."); server_running_game = False; break 
        
        # Apply P2's game inputs
        if player2 and player2._valid_init and remote_p2_input_copy and hasattr(player2, 'handle_network_input'):
            player2.handle_network_input(remote_p2_input_copy)

        # Handle reset conditions
        if reset_now_by_host or (reset_req_by_client and game_over_for_p2_reset_request): 
            print("DEBUG: Triggering reset_platformer_game_state() in Server Mode.")
            reset_platformer_game_state()
            if camera: camera.set_pos(0,0); # Reset camera position
            # reset_req_by_client = False; reset_now_by_host = False # Flags already reset effectively by game state reset
        
        # Update game entities
        if player1 and player1._valid_init: 
            other_players_for_p1 = [p for p in [player2] if p and p._valid_init and p.alive() and p is not player1]
            player1.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p1, enemy_list)
        
        if player2 and player2._valid_init: 
            other_players_for_p2 = [p for p in [player1] if p and p._valid_init and p.alive() and p is not player2]
            player2.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p2, enemy_list)
        
        active_players_for_enemies = [p for p in [player1, player2] if p and p._valid_init and not p.is_dead and p.alive()]
        for enemy_instance in enemy_list: # Iterate through the master list
            if enemy_instance._valid_init: # Only update valid enemies
                enemy_instance.update(dt_sec, active_players_for_enemies, platform_sprites, hazard_sprites)
            # Check if enemy should be removed after its death animation
            if enemy_instance.is_dead and enemy_instance.death_animation_finished and enemy_instance.alive():
                 if Enemy.print_limiter.can_print(f"main_loop_killing_enemy_{enemy_instance.enemy_id}"):
                    print(f"DEBUG MainLoop (Server): Killing enemy {enemy_instance.enemy_id} as death anim finished.")
                 enemy_instance.kill()
        
        collectible_sprites.update(dt_sec) # Update collectibles (e.g., chest animation)
        # Chest collection logic
        if Chest and current_chest and current_chest.alive():
            if player1 and player1._valid_init and not player1.is_dead and player1.alive() and pygame.sprite.collide_rect(player1, current_chest):
                 current_chest.collect(player1); current_chest = None # P1 collects chest
            elif player2 and player2._valid_init and not player2.is_dead and player2.alive() and \
                 current_chest and current_chest.alive() and pygame.sprite.collide_rect(player2, current_chest):
                 current_chest.collect(player2); current_chest = None # P2 collects chest
        
        update_camera_platformer(player1, player2) # Update camera focus
        
        # Send game state to client
        if client_connection: 
            net_state = get_platformer_network_state()
            encoded_state = encode_data(net_state)
            if encoded_state:
                try: client_connection.sendall(encoded_state)
                except socket.error as e: print(f"Send failed to client: {e}"); server_running_game = False; break
        
        try: draw_platformer_scene(screen, now_ticks) # Draw the game
        except Exception as e: print(f"Server draw error: {e}"); traceback.print_exc(); server_running_game=False; break
        pygame.display.flip()

    print("Exiting server game loop.")
    app_running = False # Ensure other threads also stop
    # Clean up network resources
    temp_conn_to_close = None
    with client_lock: # Safely get current connection to close
        temp_conn_to_close = client_connection; client_connection = None 
    if temp_conn_to_close:
        try: temp_conn_to_close.shutdown(socket.SHUT_RDWR); temp_conn_to_close.close()
        except: pass 
    if server_tcp_socket: server_tcp_socket.close(); server_tcp_socket = None
    if broadcast_thread and broadcast_thread.is_alive(): broadcast_thread.join(0.2) # Wait briefly for thread
    if client_handler_thread and client_handler_thread.is_alive(): client_handler_thread.join(0.2)
    print("Server mode finished.")

def run_client_mode(target_ip_port=None):
    global app_running, screen, clock, camera, client_tcp_socket, server_state_buffer, player1, player2, enemy_list, WIDTH, HEIGHT, current_chest, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, all_sprites

    if not initialize_platformer_elements(for_game_mode="client"):
        print("Client: Failed to initialize platformer elements.")
        return
    
    server_ip_connect, server_port_connect = None, SERVER_PORT_TCP # Default port
    if target_ip_port: # If IP:Port is provided directly
        parts = target_ip_port.rsplit(':', 1); server_ip_connect = parts[0]
        if len(parts) > 1: # If port is also provided
            try: server_port_connect = int(parts[1])
            except ValueError: print(f"Invalid port in '{target_ip_port}'. Using default {SERVER_PORT_TCP}.")
    else: # Search for server on LAN
        server_ip_connect, found_port = find_server(screen, font_small, font_large)
        if found_port: server_port_connect = found_port
    
    if not server_ip_connect: print("Exiting client (no server found/specified)."); return
    if not app_running: print("Exiting client (app closed before connection)."); return 
    
    # P2 (local client) controls mapping
    p2_local_key_map_for_input_state = { 
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e,
    }

    client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection_successful, error_message = False, "Unknown Connection Error"
    try:
        print(f"Connecting to {server_ip_connect}:{server_port_connect}..."); pygame.display.set_caption(f"Platformer - Connecting...")
        screen.fill(C.BLACK); conn_text = font_large.render(f"Connecting...", True, C.WHITE)
        screen.blit(conn_text, conn_text.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip()
        client_tcp_socket.settimeout(10.0); client_tcp_socket.connect((server_ip_connect, server_port_connect))
        client_tcp_socket.settimeout(0.05); print("TCP Connection successful!"); connection_successful = True # Non-blocking for recv
    except socket.error as e: error_message = f"Connection Error ({e.strerror if hasattr(e, 'strerror') else e})"
    except Exception as e: error_message = f"Unexpected Connection Error: {e}"
    
    if not connection_successful:
        print(f"Failed to connect: {error_message}")
        screen.fill(C.BLACK); fail_text = font_large.render(f"Connection Failed", True, C.RED)
        screen.blit(fail_text, fail_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 30))); pygame.display.flip(); time.sleep(3)
        if client_tcp_socket: client_tcp_socket.close(); client_tcp_socket = None
        return

    pygame.display.set_caption("Platformer - CLIENT (You are P2: WASD+VB | Self-Harm: H | Heal: G | Reset: Enter)")
    server_state_buffer = b""; last_received_server_state = None; client_running_game = True
    
    while client_running_game and app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks = pygame.time.get_ticks()
        
        client_input_actions = {'action_reset': False, 'action_self_harm': False, 'action_heal': False} 
        game_over_from_server = False # Check if server indicated game over for P1
        if last_received_server_state and 'game_over' in last_received_server_state:
            game_over_from_server = last_received_server_state['game_over']
        
        client_events = pygame.event.get(); keys_client = pygame.key.get_pressed()
        for event in client_events:
            if event.type == pygame.QUIT: client_running_game = False; app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    try:
                        WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                        screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                        if camera: camera.screen_width = WIDTH; camera.screen_height = HEIGHT
                    except pygame.error as e: print(f"Resize error: {e}")
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: client_running_game = False 
                # Client can request reset if server indicates P1 game over
                if event.key == pygame.K_RETURN and game_over_from_server : 
                    client_input_actions['action_reset'] = True
                # Client (P2) debug controls
                if event.key == pygame.K_h: client_input_actions['action_self_harm'] = True 
                if event.key == pygame.K_g: client_input_actions['action_heal'] = True 

        if not app_running or not client_running_game: break
        
        # Get P2's input state to send to server
        p2_input_dict_to_send = {} 
        if player2 and hasattr(player2, 'get_input_state'): # P2 is the local player on client
             p2_input_dict_to_send = player2.get_input_state(keys_client, client_events, p2_local_key_map_for_input_state)
        p2_input_dict_to_send.update(client_input_actions) # Add any special actions

        # Send input to server
        if client_tcp_socket: 
            client_payload = {"input": p2_input_dict_to_send}
            encoded_payload = encode_data(client_payload)
            if encoded_payload:
                try: client_tcp_socket.sendall(encoded_payload)
                except socket.error as e: print(f"Client send failed: {e}"); client_running_game=False; break 
        
        # Receive game state from server
        if client_tcp_socket:
            try:
                chunk = client_tcp_socket.recv(BUFFER_SIZE * 2) # Receive up to 2x buffer size
                if not chunk: print("Server disconnected."); client_running_game=False; break 
                server_state_buffer += chunk
                decoded_states, server_state_buffer = decode_data_stream(server_state_buffer)
                if decoded_states:
                    last_received_server_state = decoded_states[-1] # Use the latest full state message
                    set_platformer_network_state(last_received_server_state) # Apply the state
            except socket.error as e: # Handle non-blocking socket errors
                if e.errno != 10035 and e.errno != 11: # WSAEWOULDBLOCK / EAGAIN
                    print(f"Client recv error: {e}"); client_running_game=False; break
            except Exception as e: print(f"Client data processing error: {e}"); traceback.print_exc(); client_running_game=False; break
        
        # Client-side animation (driven by server state, but animate locally for smoothness if needed)
        # The set_platformer_network_state should handle most visual updates, but calling animate ensures
        # frame progression based on local time if server updates are infrequent or state has timing info.
        if player1 and player1.alive() and player1._valid_init: player1.animate() 
        if player2 and player2.alive() and player2._valid_init: player2.animate() 
        for enemy_instance in enemy_list: # Animate all enemies based on their current (networked) state
            if enemy_instance.alive() and enemy_instance._valid_init:
                enemy_instance.animate()
            # Check if enemy should be removed after its death animation (client-side check)
            if enemy_instance.is_dead and enemy_instance.death_animation_finished and enemy_instance.alive():
                 if Enemy.print_limiter.can_print(f"main_loop_killing_enemy_client_{enemy_instance.enemy_id}"):
                    print(f"DEBUG MainLoop (Client): Killing enemy {enemy_instance.enemy_id} as death anim finished locally.")
                 enemy_instance.kill()


        collectible_sprites.update(dt_sec) # Animate collectibles

        # Determine camera target for client (usually P2, their local player)
        cam_target_client = None 
        if player2 and player2.alive() and player2._valid_init and not player2.is_dead :
            cam_target_client = player2
        elif player1 and player1.alive() and player1._valid_init and not player1.is_dead: # Fallback to P1 if P2 not valid
            cam_target_client = player1
        
        if cam_target_client: camera.update(cam_target_client)
        else: camera.static_update() # No valid target

        try: draw_platformer_scene(screen, now_ticks) # Draw the game
        except Exception as e: print(f"Client draw error: {e}"); traceback.print_exc(); client_running_game=False; break
        pygame.display.flip()

    print("Exiting client game loop.")
    # Clean up client socket
    if client_tcp_socket:
        try: client_tcp_socket.shutdown(socket.SHUT_RDWR); client_tcp_socket.close()
        except: pass
        client_tcp_socket = None
    print("Client mode finished.")


def run_couch_play_mode():
    global app_running, screen, clock, camera, player1, player2, enemy_list, WIDTH, HEIGHT, current_chest, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, all_sprites

    print("Starting Couch Play mode...")
    pygame.display.set_caption("Platformer - Couch (P1:WASD+VB, P2:IJKL+OP | Harm:H,N | Heal:G,M | Reset:R)")

    if not initialize_platformer_elements(for_game_mode="couch_play"):
        print("Couch: Failed to initialize platformer elements.")
        return
    
    # Define P1 and P2 key mappings for couch play
    p1_key_map = {
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e }
    p2_key_map = {
        'left': pygame.K_j, 'right': pygame.K_l, 'up': pygame.K_i, 'down': pygame.K_k,
        'attack1': pygame.K_o, 'attack2': pygame.K_p, 'dash': pygame.K_SEMICOLON, 
        'roll': pygame.K_QUOTE, 'interact': pygame.K_BACKSLASH } # Example mapping for P2

    couch_running_game = True
    while couch_running_game and app_running:
        dt_sec = clock.tick(getattr(C, 'FPS', 60)) / 1000.0; now_ticks = pygame.time.get_ticks()
        events = pygame.event.get(); keys = pygame.key.get_pressed()
        reset_now_couch = False
        
        # Determine if game is over (both players dead and animations finished)
        p1_gone_couch = True
        if player1 and player1._valid_init:
            if player1.alive() and (not player1.is_dead or (player1.is_dead and not player1.death_animation_finished)):
                p1_gone_couch = False
        
        p2_gone_couch = True
        if player2 and player2._valid_init:
            if player2.alive() and (not player2.is_dead or (player2.is_dead and not player2.death_animation_finished)):
                p2_gone_couch = False

        game_over_couch = p1_gone_couch and p2_gone_couch

        for event in events:
            if event.type == pygame.QUIT: couch_running_game = False; app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    try:
                        WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                        screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                        if camera: camera.screen_width = WIDTH; camera.screen_height = HEIGHT
                    except pygame.error as e: print(f"Resize error: {e}")
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: couch_running_game = False; break 
                
                if event.key == pygame.K_r: # Reset if 'R' is pressed (and game is over or anytime)
                    print("DEBUG: 'R' key pressed (Couch Mode) - reset requested.")
                    reset_now_couch = True 
                
                # Debug controls for P1
                if event.key == pygame.K_h and player1 and player1._valid_init and hasattr(player1, 'self_inflict_damage'):
                    player1.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_g and player1 and player1._valid_init and hasattr(player1, 'heal_to_full'):
                    player1.heal_to_full()
                
                # Debug controls for P2
                if event.key == pygame.K_n and player2 and player2._valid_init and hasattr(player2, 'self_inflict_damage'):
                    player2.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_m and player2 and player2._valid_init and hasattr(player2, 'heal_to_full'):
                    player2.heal_to_full()

        if not app_running or not couch_running_game: break

        # Handle player inputs
        if player1 and player1._valid_init and not player1.is_dead:
            player1.handle_mapped_input(keys, events, p1_key_map)
        if player2 and player2._valid_init and not player2.is_dead:
            player2.handle_mapped_input(keys, events, p2_key_map)

        if reset_now_couch: # If reset was triggered
            print("DEBUG: Triggering reset_platformer_game_state() in Couch Mode.")
            reset_platformer_game_state()
            if camera: camera.set_pos(0,0); # Reset camera
            reset_now_couch = False
        
        # Update game entities
        if player1 and player1._valid_init: 
            other_players_for_p1 = [p for p in [player2] if p and p._valid_init and p.alive() and p is not player1]
            player1.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p1, enemy_list)
        if player2 and player2._valid_init: 
            other_players_for_p2 = [p for p in [player1] if p and p._valid_init and p.alive() and p is not player2]
            player2.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p2, enemy_list)
        
        active_players_for_enemies = [p for p in [player1, player2] if p and p._valid_init and not p.is_dead and p.alive()]
        for enemy_instance in enemy_list: # Iterate through the master list
            if enemy_instance._valid_init: 
                enemy_instance.update(dt_sec, active_players_for_enemies, platform_sprites, hazard_sprites)
            if enemy_instance.is_dead and enemy_instance.death_animation_finished and enemy_instance.alive():
                 if Enemy.print_limiter.can_print(f"main_loop_killing_enemy_couch_{enemy_instance.enemy_id}"):
                    print(f"DEBUG MainLoop (Couch): Killing enemy {enemy_instance.enemy_id} as death anim finished.")
                 enemy_instance.kill()

        
        collectible_sprites.update(dt_sec)
        # Chest collection
        if Chest and current_chest and current_chest.alive():
            if player1 and player1._valid_init and not player1.is_dead and player1.alive() and pygame.sprite.collide_rect(player1, current_chest):
                current_chest.collect(player1); current_chest = None
            elif player2 and player2._valid_init and not player2.is_dead and player2.alive() and \
                 current_chest and current_chest.alive() and pygame.sprite.collide_rect(player2, current_chest):
                current_chest.collect(player2); current_chest = None
        
        update_camera_platformer(player1, player2) # Update camera
        try: draw_platformer_scene(screen, now_ticks) # Draw the game
        except Exception as e: print(f"Couch draw error: {e}"); traceback.print_exc(); couch_running_game=False; break
        pygame.display.flip()
    print("Exiting Couch Play mode.")

def get_server_id_input(screen_surf, font_prompt, font_input, font_info, clock_obj):
    """Gets server IP:Port input from the user."""
    global app_running, SCRAP_INITIALIZED, PYPERCLIP_AVAILABLE, WIDTH, HEIGHT
    input_text = ""; input_active = True; cursor_visible = True; last_cursor_toggle = time.time()
    input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50) # Input field rect
    pygame.key.set_repeat(500, 50); paste_info_msg = None; paste_msg_start_time = 0 # Key repeat for typing
    while input_active and app_running:
        current_time = time.time()
        # Blinking cursor
        if current_time - last_cursor_toggle > 0.5: cursor_visible = not cursor_visible; last_cursor_toggle = current_time
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: app_running = False; input_active = False
            if event.type == pygame.VIDEORESIZE: # Handle resize during input
                 if not screen.get_flags() & pygame.FULLSCREEN:
                     try:
                         WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                         screen_surf=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                         input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50) # Recalculate rect
                     except pygame.error as e: print(f"Resize error: {e}")
            if event.type == pygame.KEYDOWN:
                paste_info_msg = None # Clear paste message on new key press
                if event.key == pygame.K_ESCAPE: input_active = False; input_text = None # Cancel
                elif event.key == pygame.K_RETURN: # Confirm
                    if input_text.strip(): input_active = False # Submit if not empty
                    else: input_text = "" # Clear if only whitespace
                elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1] # Backspace
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META): # Ctrl+V or Cmd+V
                    pasted_content, paste_method_used = None, "None"
                    if SCRAP_INITIALIZED: # Try pygame.scrap first
                        try:
                            cb_data = pygame.scrap.get(pygame.SCRAP_TEXT) # Get bytes
                            if cb_data: pasted_content = cb_data.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                            if pasted_content: paste_method_used = "pygame.scrap"
                        except Exception as e_scrap: print(f"pygame.scrap paste error: {e_scrap}")
                    if not pasted_content and PYPERCLIP_AVAILABLE: # Fallback to pyperclip
                        try:
                            cb_data = pyperclip.paste()
                            if isinstance(cb_data, str): pasted_content = cb_data.replace('\x00', '').strip()
                            if pasted_content: paste_method_used = "pyperclip"
                        except Exception as e_pyperclip: print(f"pyperclip paste error: {e_pyperclip}")
                    if pasted_content: input_text += pasted_content
                    else: paste_info_msg = "Paste Failed/Empty"; paste_msg_start_time = current_time
                elif event.unicode.isalnum() or event.unicode in ['.', ':', '-']: input_text += event.unicode # Allow relevant chars
        
        screen_surf.fill(C.BLACK)
        # Draw UI elements
        prompt_surf = font_prompt.render("Enter Host IP Address or IP:Port", True, C.WHITE)
        screen_surf.blit(prompt_surf, prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
        info_surf = font_info.render("(Enter=Confirm, Esc=Cancel, Ctrl+V=Paste)", True, C.GREY) 
        screen_surf.blit(info_surf, info_surf.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
        pygame.draw.rect(screen_surf, C.GREY, input_rect, border_radius=5) # Input field background
        pygame.draw.rect(screen_surf, C.WHITE, input_rect, 2, border_radius=5) # Input field border
        text_surf = font_input.render(input_text, True, C.BLACK) # Render typed text
        text_rect_render = text_surf.get_rect(midleft=(input_rect.left + 10, input_rect.centery))
        # Clipping to prevent text overflow from input box
        clip_render_area = input_rect.inflate(-12, -12) # Slightly smaller than input_rect for padding
        if text_rect_render.right > clip_render_area.right : text_rect_render.right = clip_render_area.right # Don't let text draw past right edge
        screen_surf.set_clip(clip_render_area); screen_surf.blit(text_surf, text_rect_render); screen_surf.set_clip(None) # Draw text within clip
        # Draw cursor
        if cursor_visible: 
            cursor_x_pos = text_rect_render.right + 2
            # Ensure cursor stays within visible bounds of input field
            if cursor_x_pos < clip_render_area.left + 2: cursor_x_pos = clip_render_area.left + 2
            if cursor_x_pos > clip_render_area.right -1: cursor_x_pos = clip_render_area.right -1
            pygame.draw.line(screen_surf, C.BLACK, (cursor_x_pos, input_rect.top + 5), (cursor_x_pos, input_rect.bottom - 5), 2)
        # Display paste status message
        if paste_info_msg and current_time - paste_msg_start_time < 2.0: 
            msg_s = font_info.render(paste_info_msg, True, C.RED); screen_surf.blit(msg_s, msg_s.get_rect(center=(WIDTH//2, input_rect.bottom+30)))
        elif paste_info_msg: paste_info_msg = None # Clear message after timeout
        pygame.display.flip(); clock_obj.tick(30)
    pygame.key.set_repeat(0,0) # Disable key repeat after input
    return input_text.strip() if input_text is not None else None

def find_server(screen_surf, font_small_obj, font_large_obj):
    """Searches for a server on the LAN using UDP broadcasts."""
    global app_running, clock, WIDTH, HEIGHT, SERVICE_NAME, DISCOVERY_PORT_UDP, CLIENT_SEARCH_TIMEOUT_S, BUFFER_SIZE
    pygame.display.set_caption("Platformer - Searching LAN...")
    search_text_surf = font_large_obj.render("Searching for server on LAN...", True, C.WHITE)
    listen_socket, found_server_ip, found_server_port = None, None, None
    try: # Setup UDP listening socket
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', DISCOVERY_PORT_UDP)); listen_socket.settimeout(0.5) # Listen on all interfaces
    except socket.error as e:
        print(f"Error binding UDP listen socket {DISCOVERY_PORT_UDP}: {e}")
        screen_surf.fill(C.BLACK); err1 = font_small_obj.render(f"Error: Cannot listen on UDP {DISCOVERY_PORT_UDP}.", True, C.RED)
        screen_surf.blit(err1, err1.get_rect(center=(WIDTH//2, HEIGHT // 2))); pygame.display.flip(); time.sleep(4)
        return None, None 
    start_time, my_ip = time.time(), get_local_ip() # To ignore self-broadcasts
    while time.time() - start_time < CLIENT_SEARCH_TIMEOUT_S and app_running:
        for event in pygame.event.get(): # Handle window events
             if event.type == pygame.QUIT: app_running = False; break
             if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    try:
                        WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                        screen_surf=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    except pygame.error as e: print(f"Resize error: {e}")
             if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: print("Search cancelled by user."); app_running = False; break 
        if not app_running: break
        screen_surf.fill(C.BLACK); screen_surf.blit(search_text_surf, search_text_surf.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip(); clock.tick(10)
        try:
            data, addr = listen_socket.recvfrom(BUFFER_SIZE)
            if addr[0] == my_ip: continue # Ignore own broadcasts
            decoded_msgs, _ = decode_data_stream(data + b'\n') # Add newline for stream decoder
            if not decoded_msgs: continue; message = decoded_msgs[0] # Take first message
            # Validate received broadcast message
            if (message and message.get("service") == SERVICE_NAME and 
                isinstance(message.get("tcp_ip"), str) and isinstance(message.get("tcp_port"), int)):
                ip, port = message["tcp_ip"], message["tcp_port"]
                print(f"Found server: {ip}:{port} from {addr[0]}"); found_server_ip, found_server_port = ip, port; break # Server found
        except socket.timeout: continue # No broadcast received
        except Exception as e: print(f"Error processing UDP broadcast: {e}")
    if listen_socket: listen_socket.close() 
    if not found_server_ip and app_running: # If no server found after timeout
        print(f"No server found for '{SERVICE_NAME}'.")
        screen_surf.fill(C.BLACK); fail1 = font_large_obj.render("Server Not Found!", True, C.RED)
        screen_surf.blit(fail1, fail1.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip(); time.sleep(3)
    return found_server_ip, found_server_port

def show_main_menu():
    """Displays the main menu and returns the user's choice."""
    global screen, clock, font_small, font_medium, font_large, app_running, WIDTH, HEIGHT
    button_width, button_height, spacing = 350, 55, 20; title_button_gap = 60
    title_color = C.WHITE; btn_txt_color = C.WHITE; btn_color = C.BLUE; btn_hover = C.GREEN
    title_surf = font_large.render("Platformer Adventure LAN", True, title_color)
    # Define menu buttons
    buttons_data = { 
        "host": {"text": "Host Game (Online)", "action": "host"}, 
        "join_lan": {"text": "Join Game (LAN)", "action": "join_lan"},
        "join_internet": {"text": "Join Game (Internet)", "action": "join_internet"}, 
        "couch_play": {"text": "Couch Play (Local)", "action": "couch_play"},
        "quit": {"text": "Quit Game", "action": "quit"}}
    _title_rect_cache = None # Cache title rect for performance
    def update_button_geometries_menu(): # Recalculates button positions on resize
        nonlocal _title_rect_cache 
        _title_rect_cache = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        current_y_pos = _title_rect_cache.bottom + title_button_gap
        for key, props_dict in buttons_data.items():
            props_dict["rect"] = pygame.Rect(0,0,button_width,button_height); props_dict["rect"].centerx = WIDTH // 2
            props_dict["rect"].top = current_y_pos
            props_dict["text_surf"] = font_medium.render(props_dict["text"], True, btn_txt_color)
            props_dict["text_rect"] = props_dict["text_surf"].get_rect(center=props_dict["rect"].center)
            current_y_pos += button_height + spacing
    update_button_geometries_menu() # Initial calculation
    selected_option_menu = None
    while selected_option_menu is None and app_running:
        mouse_pos_menu = pygame.mouse.get_pos(); events_menu = pygame.event.get()
        for event_m in events_menu:
            if event_m.type == pygame.QUIT: app_running = False; selected_option_menu = "quit"
            if event_m.type == pygame.VIDEORESIZE: # Handle resize
                 if not screen.get_flags() & pygame.FULLSCREEN: 
                     try:
                         WIDTH=max(320,event_m.w); HEIGHT=max(240,event_m.h)
                         screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                         update_button_geometries_menu() # Update button layout
                     except pygame.error as e: print(f"Menu resize error: {e}")
            if event_m.type == pygame.KEYDOWN and event_m.key == pygame.K_ESCAPE: app_running = False; selected_option_menu = "quit"
            if event_m.type == pygame.MOUSEBUTTONDOWN and event_m.button == 1: # Left click
                for props_m in buttons_data.values(): # Check if a button was clicked
                    if props_m["rect"].collidepoint(mouse_pos_menu): selected_option_menu = props_m["action"]; break 
        screen.fill(C.BLACK) # Background
        if _title_rect_cache: screen.blit(title_surf, _title_rect_cache) # Draw title
        # Draw buttons
        for props_m in buttons_data.values(): 
            hover_m = props_m["rect"].collidepoint(mouse_pos_menu) # Check for mouse hover
            pygame.draw.rect(screen, btn_hover if hover_m else btn_color, props_m["rect"], border_radius=8)
            screen.blit(props_m["text_surf"], props_m["text_rect"]) 
        pygame.display.flip(); clock.tick(30) # Limit FPS for menu
    return selected_option_menu

# --- Main Execution ---
if __name__ == "__main__":
    clock = pygame.time.Clock() # Initialize Pygame clock
    try: # Load fonts
        font_small = pygame.font.Font(None, 28); font_medium = pygame.font.Font(None, 36)
        font_large = pygame.font.Font(None, 72); debug_font = pygame.font.Font(None, 20)
    except Exception as e: print(f"FATAL: Font loading error: {e}"); pygame.quit(); sys.exit(1)

    while app_running:
        pygame.display.set_caption("Platformer Adventure - Main Menu")
        menu_choice = show_main_menu() # Display menu and get choice
        
        if menu_choice == "quit": app_running = False; break # Exit condition
        if not app_running: break # Double check after menu
        app_running = True # Ensure it's true before entering a game mode loop
        
        # Launch game mode based on choice
        if menu_choice == "host": run_server_mode()
        elif menu_choice == "join_lan": run_client_mode() # LAN search
        elif menu_choice == "join_internet": # Manual IP entry
            target_ip = get_server_id_input(screen, font_medium, font_medium, font_small, clock)
            if target_ip and app_running: run_client_mode(target_ip_port=target_ip)
        elif menu_choice == "couch_play": run_couch_play_mode()
        
        # After a game mode finishes, app_running might be false. If so, loop will terminate.
        # If app_running is still true, it means a game mode exited but user didn't quit app,
        # so show main menu again.
        
    print("Exiting application gracefully.")
    pygame.quit()
    try: # Attempt to quit scrap module if initialized
        if SCRAP_INITIALIZED and pygame.scrap.get_init(): pygame.scrap.quit()
    except Exception: pass # Ignore errors during scrap quit
    sys.exit(0)