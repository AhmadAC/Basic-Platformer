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
    from enemy import Enemy
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
    
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
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
SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 4096
BROADCAST_INTERVAL_S = 1.0
CLIENT_SEARCH_TIMEOUT_S = 5.0
SERVICE_NAME = "platformer_adventure_lan_v1"

try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w; monitor_height = display_info.current_h
    initial_width = max(800, min(1600, monitor_width * 3 // 4))
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    WIDTH = initial_width; HEIGHT = initial_height
    flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    print(f"Initial window: {WIDTH}x{HEIGHT}")
except Exception as e: print(f"Error setting up display: {e}"); pygame.quit(); sys.exit()

clock = None
font_small, font_medium, font_large, debug_font = None, None, None, None
app_running = True

server_tcp_socket, server_udp_socket, client_connection, client_address = None, None, None, None
client_input_buffer = {}; client_state_buffer = b""; client_lock = threading.Lock()
broadcast_thread, client_handler_thread = None, None
client_tcp_socket = None; server_state_buffer = b""

player1, player2, camera, current_chest = None, None, None, None
platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, all_sprites = \
    pygame.sprite.Group(), pygame.sprite.Group(), pygame.sprite.Group(), \
    pygame.sprite.Group(), pygame.sprite.Group(), pygame.sprite.Group()
enemy_list = [] 
level_pixel_width, level_pixel_height = WIDTH, HEIGHT
ground_level_y, ground_platform_height = HEIGHT - 40, 40
player1_spawn_pos, player2_spawn_pos = (100, HEIGHT - 80), (150, HEIGHT - 80)
enemy_spawns_data = [] 

# --- Helper Functions (Network) ---
def get_local_ip():
    best_ip = '127.0.0.1'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        best_ip = s.getsockname()[0]; s.close()
    except Exception:
        try: best_ip = socket.gethostbyname(socket.gethostname())
        except Exception: best_ip = '127.0.0.1'
    return best_ip

def encode_data(data):
    try: return json.dumps(data).encode('utf-8') + b'\n'
    except TypeError as e: print(f"Encoding Error: {e} Data: {str(data)[:100]}"); return None
    except Exception as e: print(f"Unexpected Encoding Error: {e}"); return None

def decode_data_stream(byte_buffer):
    decoded_objects, remaining_buffer = [], byte_buffer
    while b'\n' in remaining_buffer:
        message, remaining_buffer = remaining_buffer.split(b'\n', 1)
        if not message: continue
        try: decoded_objects.append(json.loads(message.decode('utf-8')))
        except Exception: continue 
    return decoded_objects, remaining_buffer

# --- Platformer Specific Helper Functions ---
def initialize_platformer_elements(for_game_mode="unknown"):
    global platform_sprites, ladder_sprites, hazard_sprites, enemy_spawns_data, \
           player1_spawn_pos, player2_spawn_pos, level_pixel_width, level_pixel_height, ground_level_y, \
           ground_platform_height, all_sprites, enemy_sprites, \
           collectible_sprites, player1, player2, enemy_list, \
           current_chest, WIDTH, HEIGHT, camera

    print(f"Initializing platformer elements for mode: {for_game_mode}...")
    if player1: player1.kill(); player1 = None
    if player2: player2.kill(); player2 = None
    if current_chest: current_chest.kill(); current_chest = None
    for sprite in all_sprites: sprite.kill() 
    all_sprites.empty(); platform_sprites.empty(); ladder_sprites.empty(); hazard_sprites.empty()
    enemy_sprites.empty(); collectible_sprites.empty(); enemy_list.clear()

    print("Loading level data via LevelLoader...")
    try:
        platform_data_group, ladder_data_group, hazard_data_group, enemy_spawns_data_list, \
        p1_spawn_tuple, lvl_width_pixels, ground_y_coord, ground_h_pixels = \
            LevelLoader.load_map_cpu(WIDTH, HEIGHT) 
        
        enemy_spawns_data = enemy_spawns_data_list 
        
        platform_sprites.add(platform_data_group.sprites()) 
        ladder_sprites.add(ladder_data_group.sprites())
        hazard_sprites.add(hazard_data_group.sprites())
        player1_spawn_pos = p1_spawn_tuple
        player2_spawn_pos = (p1_spawn_tuple[0] + 60, p1_spawn_tuple[1]) 
        level_pixel_width = lvl_width_pixels; 
        level_pixel_height = HEIGHT 
        ground_level_y = ground_y_coord; ground_platform_height = ground_h_pixels
        print("Level geometry loaded.")
    except Exception as e: print(f"CRITICAL ERROR loading level: {e}"); traceback.print_exc(); return False

    all_sprites.add(platform_sprites.sprites(), ladder_sprites.sprites(), hazard_sprites.sprites())

    if for_game_mode in ["host", "couch_play", "single_player"]: 
        print("Initializing player 1..."); player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 init failed."); return False
        all_sprites.add(player1); print("P1 initialized.")
    
    if for_game_mode == "couch_play":
        print("Initializing player 2 (couch)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (couch) init failed."); return False
        all_sprites.add(player2); print("P2 (couch) initialized.")
    elif for_game_mode == "host": 
        print("Initializing player 2 (remote placeholder)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (remote) init failed."); return False
        all_sprites.add(player2); print("P2 (remote) initialized.")
    elif for_game_mode == "client": 
        print("Initializing player 1 (remote placeholder)..."); player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 (remote) init failed."); return False
        all_sprites.add(player1); print("P1 (remote) initialized.")
        print("Initializing player 2 (local client)..."); player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (local client) init failed."); return False
        all_sprites.add(player2); print("P2 (local client) initialized.")

    enemy_list.clear() 
    print(f"Spawning {len(enemy_spawns_data)} enemies...") 
    for i, spawn_data in enumerate(enemy_spawns_data): 
        try:
            enemy = Enemy(spawn_data['pos'][0], spawn_data['pos'][1], spawn_data.get('patrol'), enemy_id=i)
            if enemy._valid_init: 
                all_sprites.add(enemy)
                enemy_sprites.add(enemy)
                enemy_list.append(enemy)
            else: print(f"Error: Enemy {i} at {spawn_data['pos']} init failed.")
        except Exception as e: print(f"Error spawning enemy {i} at {spawn_data['pos']}: {e}")
    print(f"Enemies spawned: {len(enemy_list)}")

    current_chest = spawn_chest_platformer() 
    if current_chest: 
        all_sprites.add(current_chest)
        collectible_sprites.add(current_chest)
    
    camera = Camera(level_pixel_width, level_pixel_height, WIDTH, HEIGHT)
    return True

def spawn_chest_platformer():
    global platform_sprites, collectible_sprites, all_sprites, ground_level_y, Chest
    if Chest is None: return None
    try:
        valid_plats = [p for p in platform_sprites if p.rect.top < ground_level_y - 50 and p.rect.width > 50]
        if not valid_plats: valid_plats = list(platform_sprites) 
        if not valid_plats: print("No valid platforms to spawn chest on."); return None
        
        chosen_platform = random.choice(valid_plats)
        cx = random.randint(chosen_platform.rect.left + 20, chosen_platform.rect.right - 20)
        cy = chosen_platform.rect.top 
        new_chest = Chest(cx, cy) 
        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
            print(f"Chest object created at ({int(new_chest.rect.centerx)}, {int(new_chest.rect.bottom)}).")
            return new_chest
        else: print("Failed to initialize new chest object (invalid init).")
    except Exception as e: print(f"Error creating new chest object: {e}")
    return None

def reset_platformer_game_state():
    global player1, player2, enemy_list, current_chest, player1_spawn_pos, player2_spawn_pos, all_sprites, enemy_sprites, collectible_sprites
    print("\n--- Resetting Platformer Game State ---")

    if player1 and hasattr(player1, 'reset_state'): 
        player1.reset_state(player1_spawn_pos)
        if not player1.alive() and player1._valid_init: all_sprites.add(player1)
        print("P1 Reset")
    if player2 and hasattr(player2, 'reset_state'): 
        player2.reset_state(player2_spawn_pos)
        if not player2.alive() and player2._valid_init: all_sprites.add(player2)
        print("P2 Reset")
    
    for enemy in enemy_list: 
        if hasattr(enemy, 'reset'): 
            enemy.reset()
            if enemy._valid_init:
                if not enemy.alive(): 
                    all_sprites.add(enemy)
                    enemy_sprites.add(enemy)
                else: 
                    all_sprites.add(enemy) 
                    enemy_sprites.add(enemy)
    print(f"{len(enemy_list)} enemies processed for reset.")
    
    if current_chest and current_chest.alive(): current_chest.kill()
    current_chest = spawn_chest_platformer() 
    if current_chest:
        all_sprites.add(current_chest) 
        collectible_sprites.add(current_chest) 
        print("Chest respawned.")
    else:
        print("Failed to respawn chest or Chest class not available.")
    print("--- Game State Reset Finished ---\n")

def get_platformer_network_state():
    global player1, player2, enemy_list, current_chest
    state = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 'game_over': False}
    if player1 and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()
    
    for enemy in enemy_list: 
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data') and enemy.alive():
            state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()
            
    if current_chest and current_chest.alive() and hasattr(current_chest, 'rect'):
        state['chest'] = {'pos': (current_chest.rect.centerx, current_chest.rect.centery), 
                          'is_collected': getattr(current_chest, 'is_collected', False)}
    
    p1_truly_gone = True 
    if player1 and player1._valid_init:
        if player1.alive(): 
            if hasattr(player1, 'is_dead') and player1.is_dead:
                if hasattr(player1, 'death_animation_finished') and not player1.death_animation_finished:
                    p1_truly_gone = False 
            else: 
                p1_truly_gone = False
        
    state['game_over'] = p1_truly_gone 
    return state

def set_platformer_network_state(network_state):
    global player1, player2, enemy_list, enemy_sprites, current_chest, all_sprites, collectible_sprites, Chest, enemy_spawns_data
    
    if player1 and 'p1' in network_state and network_state['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state['p1'])
        if player1._valid_init and not player1.alive(): all_sprites.add(player1) 
    if player2 and 'p2' in network_state and network_state['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state['p2'])
        if player2._valid_init and not player2.alive(): all_sprites.add(player2) 

    if 'enemies' in network_state:
        received_enemy_data_map = network_state['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str) 
            if enemy_data_from_server.get('_valid_init', False): 
                if enemy_id_str in current_client_enemies_map: 
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    if hasattr(client_enemy, 'set_network_data'): 
                        client_enemy.set_network_data(enemy_data_from_server)
                        if not client_enemy.alive() and client_enemy._valid_init : 
                            all_sprites.add(client_enemy)
                            enemy_sprites.add(client_enemy)
                else: 
                    print(f"Client: Creating new enemy {enemy_id_str} from server state.")
                    try:
                        spawn_pos_e = enemy_data_from_server.get('pos', (0,0)) 
                        patrol_area_e = None 
                        color_name_e = enemy_data_from_server.get('color_name') 
                        matching_spawn_data = next((sd for sd_idx, sd in enumerate(enemy_spawns_data) if sd_idx == enemy_id_int), None)
                        if matching_spawn_data: patrol_area_e = matching_spawn_data.get('patrol')
                        new_enemy = Enemy(spawn_pos_e[0], spawn_pos_e[1], 
                                          patrol_area=patrol_area_e, 
                                          enemy_id=enemy_id_int) 
                        if new_enemy._valid_init:
                            new_enemy.set_network_data(enemy_data_from_server) 
                            all_sprites.add(new_enemy); enemy_sprites.add(new_enemy); enemy_list.append(new_enemy)
                        else: print(f"Client: Failed to initialize new enemy {enemy_id_str} from server.")
                    except Exception as e: print(f"Client: Error creating new enemy {enemy_id_str}: {e}")
            elif enemy_id_str in current_client_enemies_map: 
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

        server_enemy_ids = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove = set(current_client_enemies_map.keys()) - server_enemy_ids
        for removed_id_str in client_enemy_ids_to_remove:
            if removed_id_str in current_client_enemies_map:
                enemy_to_remove = current_client_enemies_map[removed_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

    if 'chest' in network_state:
        chest_data = network_state['chest']
        if chest_data and Chest is not None: 
            chest_pos_center = chest_data.get('pos'); chest_is_collected = chest_data.get('is_collected', False)
            if chest_is_collected: 
                if current_chest and current_chest.alive(): current_chest.kill(); current_chest = None
            elif chest_pos_center: 
                if not current_chest or not current_chest.alive(): 
                    if current_chest: current_chest.kill() 
                    try:
                        temp_chest_height_approx = getattr(Chest(0,0).image, 'get_height', lambda: 30)() 
                        chest_spawn_x_mid = chest_pos_center[0]
                        chest_spawn_y_bottom = chest_pos_center[1] + temp_chest_height_approx / 2
                        new_chest = Chest(chest_spawn_x_mid, chest_spawn_y_bottom)
                        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
                             all_sprites.add(new_chest); collectible_sprites.add(new_chest)
                             current_chest = new_chest
                             if hasattr(current_chest, 'is_collected'): current_chest.is_collected = False 
                        else: current_chest = None; print("Client: Failed to init chest from net.")
                    except Exception as e: print(f"Client: Error creating chest from net: {e}"); current_chest = None
                elif current_chest: 
                    if hasattr(current_chest, 'is_collected'): current_chest.is_collected = False
        elif not network_state.get('chest'): 
            if current_chest and current_chest.alive(): current_chest.kill(); current_chest = None
    

def draw_platformer_scene(target_screen, current_time_ticks):
    global all_sprites, camera, player1, player2, screen, debug_font, WIDTH, HEIGHT, enemy_list
    target_screen.fill(getattr(C, 'LIGHT_BLUE', (135, 206, 235)))
    if camera:
        for entity in all_sprites: 
            if entity.alive() and hasattr(entity, 'image') and hasattr(entity, 'rect'): 
                 target_screen.blit(entity.image, camera.apply(entity.rect))
        
        for enemy in enemy_list: 
            if enemy.alive() and enemy._valid_init and not enemy.is_dead and hasattr(enemy, 'current_health') and hasattr(enemy, 'max_health'):
                enemy_screen_rect = camera.apply(enemy.rect)
                bar_w = getattr(C, 'HEALTH_BAR_WIDTH', 50); bar_h = getattr(C, 'HEALTH_BAR_HEIGHT', 8)
                bar_x = enemy_screen_rect.centerx - bar_w / 2
                bar_y = enemy_screen_rect.top - bar_h - getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5)
                if hasattr(ui, 'draw_health_bar'):
                    ui.draw_health_bar(target_screen, bar_x, bar_y, bar_w, bar_h, enemy.current_health, enemy.max_health)
    else: 
        all_sprites.draw(target_screen) 

    if hasattr(ui, 'draw_player_hud'):
        if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init: 
            ui.draw_player_hud(target_screen, 10, 10, player1, 1)
        if player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init: 
            p2_hud_x = WIDTH - (getattr(C, 'HEALTH_BAR_WIDTH', 50) * 2) - 120 
            ui.draw_player_hud(target_screen, p2_hud_x, 10, player2, 2)
            
def update_camera_platformer(target_focus=None, target2_focus=None):
    global camera
    if not camera: return
    actual_target = None
    if target_focus and target_focus.alive() and hasattr(target_focus, '_valid_init') and target_focus._valid_init and hasattr(target_focus, 'is_dead') and not target_focus.is_dead:
        actual_target = target_focus
    elif target2_focus and target2_focus.alive() and hasattr(target2_focus, '_valid_init') and target2_focus._valid_init and hasattr(target2_focus, 'is_dead') and not target2_focus.is_dead:
        actual_target = target2_focus
    
    if actual_target: camera.update(actual_target)
    else: camera.static_update() 

# --- Server Functions ---
def broadcast_presence(server_lan_ip):
    global app_running, server_udp_socket, SERVICE_NAME, SERVER_PORT_TCP, DISCOVERY_PORT_UDP, BROADCAST_INTERVAL_S
    broadcast_message_dict = {"service": SERVICE_NAME, "tcp_ip": server_lan_ip, "tcp_port": SERVER_PORT_TCP}
    broadcast_message_bytes = encode_data(broadcast_message_dict) 
    if not broadcast_message_bytes: print("Error: Could not encode broadcast message."); return
    try:
        server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); server_udp_socket.settimeout(0.5)
    except socket.error as e: print(f"Error creating UDP broadcast socket: {e}"); server_udp_socket = None; return
    broadcast_address = ('<broadcast>', DISCOVERY_PORT_UDP)
    while app_running:
        try: server_udp_socket.sendto(broadcast_message_bytes[:-1], broadcast_address) 
        except socket.error: pass 
        except Exception as e: print(f"Unexpected error during broadcast send: {e}")
        time.sleep(BROADCAST_INTERVAL_S)
    if server_udp_socket: server_udp_socket.close(); server_udp_socket = None

def handle_client_connection(conn, addr):
    global client_input_buffer, app_running, client_lock, client_connection, BUFFER_SIZE
    print(f"Client connected via TCP: {addr}"); conn.settimeout(1.0) 
    partial_data_from_client = b""
    while app_running:
        with client_lock: 
            if client_connection is not conn: break
        try:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk: print(f"Client {addr} disconnected (received empty data)."); break
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            if decoded_inputs:
                last_input_data = decoded_inputs[-1] 
                if "input" in last_input_data: 
                    with client_lock:
                        if client_connection is conn: client_input_buffer = last_input_data["input"]
        except socket.timeout: continue 
        except socket.error as e:
            if app_running: print(f"Socket error with client {addr}: {e}. Assuming disconnect."); break
        except Exception as e: 
             if app_running: print(f"Unexpected error handling client {addr}: {e}"); traceback.print_exc(); break
    
    with client_lock:
        if client_connection is conn: 
            client_connection = None
            client_input_buffer = {"disconnect": True} 
    try: conn.shutdown(socket.SHUT_RDWR) 
    except: pass 
    try: conn.close()
    except: pass

def run_server_mode():
    global app_running, screen, clock, camera, client_connection, client_address, client_input_buffer, player1, player2, enemy_list, server_tcp_socket, broadcast_thread, client_handler_thread, client_lock, WIDTH, HEIGHT, current_chest, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites

    if not initialize_platformer_elements(for_game_mode="host"):
        print("Server: Failed to initialize platformer elements.")
        return 
    
    pygame.display.set_caption("Platformer - HOST (P1: WASD+VB | Self-Harm: H | Heal: G | Reset: R)")
    server_lan_ip = get_local_ip()
    p1_key_map = {
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e} 

    broadcast_thread = threading.Thread(target=broadcast_presence, args=(server_lan_ip,), daemon=True); broadcast_thread.start()
    server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_tcp_socket.bind((SERVER_IP_BIND, SERVER_PORT_TCP)); server_tcp_socket.listen(1)
        server_tcp_socket.settimeout(1.0); print(f"Server TCP listening on {SERVER_IP_BIND}:{SERVER_PORT_TCP}")
    except socket.error as e: print(f"FATAL: Failed to bind TCP socket: {e}"); app_running = False; return

    print("Waiting for Player 2 to connect..."); temp_client_conn = None
    while temp_client_conn is None and app_running: 
        try:
            events = pygame.event.get(); 
            for event in events:
                if event.type == pygame.QUIT: app_running = False; break
                if event.type == pygame.VIDEORESIZE: 
                     if not screen.get_flags() & pygame.FULLSCREEN: 
                        try:
                            WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                            screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                            if camera: camera.screen_width = WIDTH; camera.screen_height = HEIGHT 
                        except pygame.error as e: print(f"Resize error: {e}")
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: app_running = False; break
            if not app_running: break 
            
            screen.fill(C.BLACK); wait_text = font_large.render("Waiting for P2...", True, C.WHITE)
            screen.blit(wait_text, wait_text.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip(); clock.tick(10)
            
            temp_client_conn, temp_client_addr = server_tcp_socket.accept()
            with client_lock: 
                 if client_connection: client_connection.close() 
                 client_connection = temp_client_conn; client_address = temp_client_addr; client_input_buffer = {}
        except socket.timeout: continue 
        except Exception as e: print(f"Error during client wait/accept: {e}"); app_running = False; break 
    
    if not app_running or client_connection is None: print("Exiting server (no client connected or app closed)."); return

    print(f"Client connected: {client_address}. Starting game...")
    client_handler_thread = threading.Thread(target=handle_client_connection, args=(client_connection, client_address), daemon=True)
    client_handler_thread.start()

    server_running_game = True
    while server_running_game and app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks = pygame.time.get_ticks()
        p1_events = pygame.event.get(); keys_p1 = pygame.key.get_pressed()
        
        game_over_for_p2_reset_request = False 
        if player1 and player1._valid_init:
            if player1.is_dead and (not player1.alive() or (hasattr(player1, 'death_animation_finished') and player1.death_animation_finished)):
                game_over_for_p2_reset_request = True
        else: game_over_for_p2_reset_request = True
        
        reset_now = False

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
                if event.key == pygame.K_r: # MODIFIED: Allow reset anytime by P1
                    print("DEBUG: 'R' key pressed (Server Mode) - unconditional P1 reset requested.")
                    reset_now = True
                if event.key == pygame.K_h and player1 and player1._valid_init and hasattr(player1, 'self_inflict_damage'):
                    player1.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_g and player1 and player1._valid_init and hasattr(player1, 'heal_to_full'):
                    player1.heal_to_full()

        if not app_running or not server_running_game: break
        
        if player1 and player1._valid_init and not player1.is_dead:
            player1.handle_mapped_input(keys_p1, p1_events, p1_key_map)

        remote_p2_input_copy, client_was_disconnected, reset_req_p2 = None, False, False
        with client_lock:
            if client_input_buffer:
                if client_input_buffer.get("disconnect"): client_was_disconnected = True
                elif client_input_buffer.get("action_reset", False): reset_req_p2 = True
                elif client_input_buffer.get("action_self_harm", False) and player2 and player2._valid_init: 
                    player2.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                elif client_input_buffer.get("action_heal", False) and player2 and player2._valid_init: 
                    player2.heal_to_full()
                else: remote_p2_input_copy = client_input_buffer.copy()
                client_input_buffer = {} 
        
        if client_was_disconnected: print("Client disconnected signal received."); server_running_game = False; break 
        
        if player2 and player2._valid_init and remote_p2_input_copy and hasattr(player2, 'handle_network_input'):
            player2.handle_network_input(remote_p2_input_copy)

        # MODIFIED: P1 pressing 'R' always resets. P2 can request reset if P1 is game over.
        if reset_now or (reset_req_p2 and game_over_for_p2_reset_request): 
            print("DEBUG: Triggering reset_platformer_game_state() in Server Mode.")
            reset_platformer_game_state()
            if camera: camera.set_pos(0,0); 
            reset_req_p2 = False; reset_now = False
        
        if player1 and player1._valid_init: 
            other_players_for_p1 = [p for p in [player2] if p and p._valid_init and p.alive() and p is not player1]
            player1.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p1, enemy_list)
        
        if player2 and player2._valid_init: 
            other_players_for_p2 = [p for p in [player1] if p and p._valid_init and p.alive() and p is not player2]
            player2.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p2, enemy_list)
        
        active_players_for_enemies = [p for p in [player1, player2] if p and p._valid_init and not p.is_dead and p.alive()]
        for enemy_instance in enemy_list:
            if enemy_instance._valid_init: 
                enemy_instance.update(dt_sec, active_players_for_enemies, platform_sprites, hazard_sprites)
        
        collectible_sprites.update(dt_sec) 
        if Chest and current_chest and current_chest.alive():
            if player1 and player1._valid_init and not player1.is_dead and player1.alive() and pygame.sprite.collide_rect(player1, current_chest):
                 current_chest.collect(player1); current_chest = None 
            elif player2 and player2._valid_init and not player2.is_dead and player2.alive() and \
                 current_chest and current_chest.alive() and pygame.sprite.collide_rect(player2, current_chest):
                 current_chest.collect(player2); current_chest = None
        
        update_camera_platformer(player1, player2) 
        
        if client_connection: 
            net_state = get_platformer_network_state()
            encoded_state = encode_data(net_state)
            if encoded_state:
                try: client_connection.sendall(encoded_state)
                except socket.error as e: print(f"Send failed to client: {e}"); server_running_game = False; break
        
        try: draw_platformer_scene(screen, now_ticks)
        except Exception as e: print(f"Server draw error: {e}"); traceback.print_exc(); server_running_game=False; break
        pygame.display.flip()

    print("Exiting server game loop.")
    app_running = False 
    temp_conn_to_close = None
    with client_lock: 
        temp_conn_to_close = client_connection; client_connection = None 
    if temp_conn_to_close:
        try: temp_conn_to_close.shutdown(socket.SHUT_RDWR); temp_conn_to_close.close()
        except: pass 
    if server_tcp_socket: server_tcp_socket.close(); server_tcp_socket = None
    if broadcast_thread and broadcast_thread.is_alive(): broadcast_thread.join(0.2) 
    if client_handler_thread and client_handler_thread.is_alive(): client_handler_thread.join(0.2)
    print("Server mode finished.")

def run_client_mode(target_ip_port=None):
    global app_running, screen, clock, camera, client_tcp_socket, server_state_buffer, player1, player2, enemy_list, WIDTH, HEIGHT, current_chest, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites

    if not initialize_platformer_elements(for_game_mode="client"):
        print("Client: Failed to initialize platformer elements.")
        return
    
    server_ip_connect, server_port_connect = None, SERVER_PORT_TCP 
    if target_ip_port: 
        parts = target_ip_port.rsplit(':', 1); server_ip_connect = parts[0]
        if len(parts) > 1:
            try: server_port_connect = int(parts[1])
            except ValueError: print(f"Invalid port in '{target_ip_port}'. Using default {SERVER_PORT_TCP}.")
    else: 
        server_ip_connect, found_port = find_server(screen, font_small, font_large)
        if found_port: server_port_connect = found_port
    
    if not server_ip_connect: print("Exiting client (no server found/specified)."); return
    if not app_running: print("Exiting client (app closed before connection)."); return 
    
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
        client_tcp_socket.settimeout(0.05); print("TCP Connection successful!"); connection_successful = True 
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
        game_over_from_server = False
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
                if event.key == pygame.K_RETURN and game_over_from_server : # Client requests reset if server says game over
                    client_input_actions['action_reset'] = True
                if event.key == pygame.K_h: client_input_actions['action_self_harm'] = True 
                if event.key == pygame.K_g: client_input_actions['action_heal'] = True 

        if not app_running or not client_running_game: break
        
        p2_input_dict_to_send = {} 
        if player2 and hasattr(player2, 'get_input_state'): 
             p2_input_dict_to_send = player2.get_input_state(keys_client, client_events, p2_local_key_map_for_input_state)
        p2_input_dict_to_send.update(client_input_actions) 

        if client_tcp_socket: 
            client_payload = {"input": p2_input_dict_to_send}
            encoded_payload = encode_data(client_payload)
            if encoded_payload:
                try: client_tcp_socket.sendall(encoded_payload)
                except socket.error as e: print(f"Client send failed: {e}"); client_running_game=False; break 
        
        if client_tcp_socket:
            try:
                chunk = client_tcp_socket.recv(BUFFER_SIZE * 2) 
                if not chunk: print("Server disconnected."); client_running_game=False; break 
                server_state_buffer += chunk
                decoded_states, server_state_buffer = decode_data_stream(server_state_buffer)
                if decoded_states:
                    last_received_server_state = decoded_states[-1] 
                    set_platformer_network_state(last_received_server_state) 
            except socket.error as e: 
                if e.errno != 10035 and e.errno != 11: 
                    print(f"Client recv error: {e}"); client_running_game=False; break
            except Exception as e: print(f"Client data processing error: {e}"); traceback.print_exc(); client_running_game=False; break
        
        if player1 and player1.alive() and player1._valid_init: player1.animate() 
        if player2 and player2.alive() and player2._valid_init: player2.animate() 
        for enemy_instance in enemy_list: 
            if enemy_instance.alive() and enemy_instance._valid_init:
                enemy_instance.animate()

        collectible_sprites.update(dt_sec) 

        cam_target_client = None 
        if player2 and player2.alive() and player2._valid_init and not player2.is_dead :
            cam_target_client = player2
        elif player1 and player1.alive() and player1._valid_init and not player1.is_dead:
            cam_target_client = player1
        
        if cam_target_client: camera.update(cam_target_client)
        else: camera.static_update() 

        try: draw_platformer_scene(screen, now_ticks)
        except Exception as e: print(f"Client draw error: {e}"); traceback.print_exc(); client_running_game=False; break
        pygame.display.flip()

    print("Exiting client game loop.")
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
    
    p1_key_map = {
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e }
    p2_key_map = {
        'left': pygame.K_j, 'right': pygame.K_l, 'up': pygame.K_i, 'down': pygame.K_k,
        'attack1': pygame.K_o, 'attack2': pygame.K_p, 'dash': pygame.K_SEMICOLON, 
        'roll': pygame.K_QUOTE, 'interact': pygame.K_BACKSLASH } 

    couch_running_game = True
    while couch_running_game and app_running:
        dt_sec = clock.tick(getattr(C, 'FPS', 60)) / 1000.0; now_ticks = pygame.time.get_ticks()
        events = pygame.event.get(); keys = pygame.key.get_pressed()
        reset_now_couch = False
        
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
                
                if event.key == pygame.K_r: # MODIFIED: Allow reset anytime
                    print("DEBUG: 'R' key pressed (Couch Mode) - unconditional reset requested.")
                    reset_now_couch = True 
                
                if event.key == pygame.K_h and player1 and player1._valid_init and hasattr(player1, 'self_inflict_damage'):
                    player1.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_g and player1 and player1._valid_init and hasattr(player1, 'heal_to_full'):
                    player1.heal_to_full()
                
                if event.key == pygame.K_n and player2 and player2._valid_init and hasattr(player2, 'self_inflict_damage'):
                    player2.self_inflict_damage(getattr(C, 'PLAYER_SELF_DAMAGE', 10))
                if event.key == pygame.K_m and player2 and player2._valid_init and hasattr(player2, 'heal_to_full'):
                    player2.heal_to_full()

        if not app_running or not couch_running_game: break

        if player1 and player1._valid_init and not player1.is_dead:
            player1.handle_mapped_input(keys, events, p1_key_map)
        if player2 and player2._valid_init and not player2.is_dead:
            player2.handle_mapped_input(keys, events, p2_key_map)

        if reset_now_couch:
            print("DEBUG: Triggering reset_platformer_game_state() in Couch Mode.")
            reset_platformer_game_state()
            if camera: camera.set_pos(0,0); 
            reset_now_couch = False
        
        if player1 and player1._valid_init: 
            other_players_for_p1 = [p for p in [player2] if p and p._valid_init and p.alive() and p is not player1]
            player1.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p1, enemy_list)
        if player2 and player2._valid_init: 
            other_players_for_p2 = [p for p in [player1] if p and p._valid_init and p.alive() and p is not player2]
            player2.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, other_players_for_p2, enemy_list)
        
        active_players_for_enemies = [p for p in [player1, player2] if p and p._valid_init and not p.is_dead and p.alive()]
        for enemy_instance in enemy_list: 
            if enemy_instance._valid_init: 
                enemy_instance.update(dt_sec, active_players_for_enemies, platform_sprites, hazard_sprites)
        
        collectible_sprites.update(dt_sec)
        if Chest and current_chest and current_chest.alive():
            if player1 and player1._valid_init and not player1.is_dead and player1.alive() and pygame.sprite.collide_rect(player1, current_chest):
                current_chest.collect(player1); current_chest = None
            elif player2 and player2._valid_init and not player2.is_dead and player2.alive() and \
                 current_chest and current_chest.alive() and pygame.sprite.collide_rect(player2, current_chest):
                current_chest.collect(player2); current_chest = None
        
        update_camera_platformer(player1, player2) 
        try: draw_platformer_scene(screen, now_ticks)
        except Exception as e: print(f"Couch draw error: {e}"); traceback.print_exc(); couch_running_game=False; break
        pygame.display.flip()
    print("Exiting Couch Play mode.")

def get_server_id_input(screen_surf, font_prompt, font_input, font_info, clock_obj):
    global app_running, SCRAP_INITIALIZED, PYPERCLIP_AVAILABLE, WIDTH, HEIGHT
    input_text = ""; input_active = True; cursor_visible = True; last_cursor_toggle = time.time()
    input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50)
    pygame.key.set_repeat(500, 50); paste_info_msg = None; paste_msg_start_time = 0
    while input_active and app_running:
        current_time = time.time()
        if current_time - last_cursor_toggle > 0.5: cursor_visible = not cursor_visible; last_cursor_toggle = current_time
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: app_running = False; input_active = False
            if event.type == pygame.VIDEORESIZE:
                 if not screen.get_flags() & pygame.FULLSCREEN:
                     try:
                         WIDTH=max(320,event.w); HEIGHT=max(240,event.h)
                         screen_surf=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                         input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50) 
                     except pygame.error as e: print(f"Resize error: {e}")
            if event.type == pygame.KEYDOWN:
                paste_info_msg = None 
                if event.key == pygame.K_ESCAPE: input_active = False; input_text = None 
                elif event.key == pygame.K_RETURN:
                    if input_text.strip(): input_active = False 
                    else: input_text = "" 
                elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META): 
                    pasted_content, paste_method_used = None, "None"
                    if SCRAP_INITIALIZED: 
                        try:
                            cb_data = pygame.scrap.get(pygame.SCRAP_TEXT) 
                            if cb_data: pasted_content = cb_data.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                            if pasted_content: paste_method_used = "pygame.scrap"
                        except Exception as e_scrap: print(f"pygame.scrap paste error: {e_scrap}")
                    if not pasted_content and PYPERCLIP_AVAILABLE: 
                        try:
                            cb_data = pyperclip.paste()
                            if isinstance(cb_data, str): pasted_content = cb_data.replace('\x00', '').strip()
                            if pasted_content: paste_method_used = "pyperclip"
                        except Exception as e_pyperclip: print(f"pyperclip paste error: {e_pyperclip}")
                    if pasted_content: input_text += pasted_content
                    else: paste_info_msg = "Paste Failed/Empty"; paste_msg_start_time = current_time
                elif event.unicode.isalnum() or event.unicode in ['.', ':', '-']: input_text += event.unicode 
        
        screen_surf.fill(C.BLACK)
        prompt_surf = font_prompt.render("Enter Host IP Address or IP:Port", True, C.WHITE)
        screen_surf.blit(prompt_surf, prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
        info_surf = font_info.render("(Enter=Confirm, Esc=Cancel, Ctrl+V=Paste)", True, C.GREY) 
        screen_surf.blit(info_surf, info_surf.get_rect(center=(WIDTH // 2, HEIGHT - 40)))
        pygame.draw.rect(screen_surf, C.GREY, input_rect, border_radius=5) 
        pygame.draw.rect(screen_surf, C.WHITE, input_rect, 2, border_radius=5) 
        text_surf = font_input.render(input_text, True, C.BLACK) 
        text_rect_render = text_surf.get_rect(midleft=(input_rect.left + 10, input_rect.centery))
        clip_render_area = input_rect.inflate(-12, -12) 
        if text_rect_render.right > clip_render_area.right : text_rect_render.right = clip_render_area.right 
        screen_surf.set_clip(clip_render_area); screen_surf.blit(text_surf, text_rect_render); screen_surf.set_clip(None) 
        if cursor_visible: 
            cursor_x_pos = text_rect_render.right + 2
            if cursor_x_pos < clip_render_area.left + 2: cursor_x_pos = clip_render_area.left + 2
            if cursor_x_pos > clip_render_area.right -1: cursor_x_pos = clip_render_area.right -1
            pygame.draw.line(screen_surf, C.BLACK, (cursor_x_pos, input_rect.top + 5), (cursor_x_pos, input_rect.bottom - 5), 2)
        if paste_info_msg and current_time - paste_msg_start_time < 2.0: 
            msg_s = font_info.render(paste_info_msg, True, C.RED); screen_surf.blit(msg_s, msg_s.get_rect(center=(WIDTH//2, input_rect.bottom+30)))
        elif paste_info_msg: paste_info_msg = None 
        pygame.display.flip(); clock_obj.tick(30)
    pygame.key.set_repeat(0,0) 
    return input_text.strip() if input_text is not None else None

def find_server(screen_surf, font_small_obj, font_large_obj):
    global app_running, clock, WIDTH, HEIGHT, SERVICE_NAME, DISCOVERY_PORT_UDP, CLIENT_SEARCH_TIMEOUT_S, BUFFER_SIZE
    pygame.display.set_caption("Platformer - Searching LAN...")
    search_text_surf = font_large_obj.render("Searching for server on LAN...", True, C.WHITE)
    listen_socket, found_server_ip, found_server_port = None, None, None
    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', DISCOVERY_PORT_UDP)); listen_socket.settimeout(0.5) 
    except socket.error as e:
        print(f"Error binding UDP listen socket {DISCOVERY_PORT_UDP}: {e}")
        screen_surf.fill(C.BLACK); err1 = font_small_obj.render(f"Error: Cannot listen on UDP {DISCOVERY_PORT_UDP}.", True, C.RED)
        screen_surf.blit(err1, err1.get_rect(center=(WIDTH//2, HEIGHT // 2))); pygame.display.flip(); time.sleep(4)
        return None, None 
    start_time, my_ip = time.time(), get_local_ip() 
    while time.time() - start_time < CLIENT_SEARCH_TIMEOUT_S and app_running:
        for event in pygame.event.get(): 
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
            if addr[0] == my_ip: continue 
            decoded_msgs, _ = decode_data_stream(data + b'\n') 
            if not decoded_msgs: continue; message = decoded_msgs[0] 
            if (message and message.get("service") == SERVICE_NAME and 
                isinstance(message.get("tcp_ip"), str) and isinstance(message.get("tcp_port"), int)):
                ip, port = message["tcp_ip"], message["tcp_port"]
                print(f"Found server: {ip}:{port} from {addr[0]}"); found_server_ip, found_server_port = ip, port; break 
        except socket.timeout: continue 
        except Exception as e: print(f"Error processing UDP broadcast: {e}")
    if listen_socket: listen_socket.close() 
    if not found_server_ip and app_running: 
        print(f"No server found for '{SERVICE_NAME}'.")
        screen_surf.fill(C.BLACK); fail1 = font_large_obj.render("Server Not Found!", True, C.RED)
        screen_surf.blit(fail1, fail1.get_rect(center=(WIDTH//2, HEIGHT//2))); pygame.display.flip(); time.sleep(3)
    return found_server_ip, found_server_port

def show_main_menu():
    global screen, clock, font_small, font_medium, font_large, app_running, WIDTH, HEIGHT
    button_width, button_height, spacing = 350, 55, 20; title_button_gap = 60
    title_color = C.WHITE; btn_txt_color = C.WHITE; btn_color = C.BLUE; btn_hover = C.GREEN
    title_surf = font_large.render("Platformer Adventure LAN", True, title_color)
    buttons_data = { 
        "host": {"text": "Host Game (Online)", "action": "host"}, 
        "join_lan": {"text": "Join Game (LAN)", "action": "join_lan"},
        "join_internet": {"text": "Join Game (Internet)", "action": "join_internet"}, 
        "couch_play": {"text": "Couch Play (Local)", "action": "couch_play"},
        "quit": {"text": "Quit Game", "action": "quit"}}
    _title_rect_cache = None 
    def update_button_geometries_menu(): 
        nonlocal _title_rect_cache 
        _title_rect_cache = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        current_y_pos = _title_rect_cache.bottom + title_button_gap
        for key, props_dict in buttons_data.items():
            props_dict["rect"] = pygame.Rect(0,0,button_width,button_height); props_dict["rect"].centerx = WIDTH // 2
            props_dict["rect"].top = current_y_pos
            props_dict["text_surf"] = font_medium.render(props_dict["text"], True, btn_txt_color)
            props_dict["text_rect"] = props_dict["text_surf"].get_rect(center=props_dict["rect"].center)
            current_y_pos += button_height + spacing
    update_button_geometries_menu() 
    selected_option_menu = None
    while selected_option_menu is None and app_running:
        mouse_pos_menu = pygame.mouse.get_pos(); events_menu = pygame.event.get()
        for event_m in events_menu:
            if event_m.type == pygame.QUIT: app_running = False; selected_option_menu = "quit"
            if event_m.type == pygame.VIDEORESIZE:
                 if not screen.get_flags() & pygame.FULLSCREEN: 
                     try:
                         WIDTH=max(320,event_m.w); HEIGHT=max(240,event_m.h)
                         screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.RESIZABLE|pygame.DOUBLEBUF)
                         update_button_geometries_menu() 
                     except pygame.error as e: print(f"Menu resize error: {e}")
            if event_m.type == pygame.KEYDOWN and event_m.key == pygame.K_ESCAPE: app_running = False; selected_option_menu = "quit"
            if event_m.type == pygame.MOUSEBUTTONDOWN and event_m.button == 1: 
                for props_m in buttons_data.values(): 
                    if props_m["rect"].collidepoint(mouse_pos_menu): selected_option_menu = props_m["action"]; break 
        screen.fill(C.BLACK) 
        if _title_rect_cache: screen.blit(title_surf, _title_rect_cache) 
        for props_m in buttons_data.values(): 
            hover_m = props_m["rect"].collidepoint(mouse_pos_menu)
            pygame.draw.rect(screen, btn_hover if hover_m else btn_color, props_m["rect"], border_radius=8)
            screen.blit(props_m["text_surf"], props_m["text_rect"]) 
        pygame.display.flip(); clock.tick(30) 
    return selected_option_menu

# --- Main Execution ---
if __name__ == "__main__":
    clock = pygame.time.Clock()
    try:
        font_small = pygame.font.Font(None, 28); font_medium = pygame.font.Font(None, 36)
        font_large = pygame.font.Font(None, 72); debug_font = pygame.font.Font(None, 20)
    except Exception as e: print(f"FATAL: Font loading error: {e}"); pygame.quit(); sys.exit(1)

    while app_running:
        pygame.display.set_caption("Platformer Adventure - Main Menu")
        menu_choice = show_main_menu()
        
        if menu_choice == "quit": app_running = False; break 
        if not app_running: break 
        app_running = True 
        if menu_choice == "host": run_server_mode()
        elif menu_choice == "join_lan": run_client_mode() 
        elif menu_choice == "join_internet":
            target_ip = get_server_id_input(screen, font_medium, font_medium, font_small, clock)
            if target_ip and app_running: run_client_mode(target_ip_port=target_ip)
        elif menu_choice == "couch_play": run_couch_play_mode()
        
    print("Exiting application gracefully.")
    pygame.quit()
    try: 
        if SCRAP_INITIALIZED and pygame.scrap.get_init(): pygame.scrap.quit()
    except Exception: pass 
    sys.exit(0)