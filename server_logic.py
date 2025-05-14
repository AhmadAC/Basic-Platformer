########## START OF FILE: server_logic.py ##########

# server_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles server-side game logic, connection management, and broadcasting.
"""
import pygame
import socket
import threading
import time
import traceback
import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy # For print_limiter access if needed, or just for type hinting
from game_ui import draw_platformer_scene_on_surface # For drawing the server's view

# Shared lock for client connection and input buffer
client_lock = threading.Lock()

class ServerState:
    """
    A simple class to hold server-specific shared state used by the server's
    main loop and its threads. This helps in managing shared resources and
    the running state of the server components.
    """
    def __init__(self):
        self.client_connection = None  # Holds the active client socket object
        self.client_address = None     # Holds the (IP, port) of the active client
        self.client_input_buffer = {}  # Stores the last processed input from the client
        self.app_running = True        # Global flag: True if the application is running
        
        # Network socket objects
        self.server_tcp_socket = None  # TCP socket for listening to client connections
        self.server_udp_socket = None  # UDP socket for broadcasting server presence
        
        # Thread objects
        self.broadcast_thread = None       # Thread for LAN broadcasting
        self.client_handler_thread = None  # Thread for handling communication with the connected client
        
        # Configuration (can be loaded from constants.py or passed)
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)
        self.broadcast_interval_s = getattr(C, "BROADCAST_INTERVAL_S", 1.0)


def broadcast_presence_thread(server_state_obj: ServerState):
    """
    Thread function to periodically broadcast the server's presence on the LAN.
    Uses UDP to send a discovery message.
    """
    current_lan_ip = get_local_ip() # Get the server's LAN IP for the broadcast message
    broadcast_message_dict = {
        "service": server_state_obj.service_name,
        "tcp_ip": current_lan_ip,
        "tcp_port": server_state_obj.server_port_tcp
    }
    broadcast_message_bytes = encode_data(broadcast_message_dict)

    if not broadcast_message_bytes:
        print("Server Error: Could not encode broadcast message for presence.")
        return

    try:
        # Create and configure the UDP socket for broadcasting
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5) # Timeout for socket operations to allow periodic checks
    except socket.error as e:
        print(f"Server Error: Failed to create UDP broadcast socket: {e}")
        server_state_obj.server_udp_socket = None
        return
    
    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    print(f"DEBUG Server (broadcast_presence_thread): Broadcasting presence: {broadcast_message_dict} to {broadcast_address} (LAN IP: {current_lan_ip})") # DEBUG

    while server_state_obj.app_running:
        try:
            server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
            # print(f"DEBUG Server (broadcast_presence_thread): Broadcast sent.") # DEBUG - can be very noisy
        except socket.error as sock_err:
            print(f"DEBUG Server (broadcast_presence_thread): Socket error during broadcast send: {sock_err}") # DEBUG
            pass 
        except Exception as e:
            print(f"Server Warning: Unexpected error during broadcast send: {e}")
        
        # Sleep for the broadcast interval, checking app_running periodically for a timely exit
        for _ in range(int(server_state_obj.broadcast_interval_s * 10)): # e.g., check every 100ms
            if not server_state_obj.app_running: break
            time.sleep(0.1)
            
    # Cleanup UDP socket when the thread stops
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close()
        server_state_obj.server_udp_socket = None
    print("DEBUG Server (broadcast_presence_thread): Broadcast thread stopped.") # DEBUG


def handle_client_connection_thread(conn: socket.socket, addr, server_state_obj: ServerState):
    """
    Thread function to handle receiving data from a single connected client.
    Updates the server_state_obj.client_input_buffer with the latest client input.
    """
    print(f"DEBUG Server (handle_client_connection_thread): Client connected from {addr}. Handler thread started.") # DEBUG
    conn.settimeout(1.0) # Use a timeout for recv to keep the loop responsive
    partial_data_from_client = b"" # Buffer for accumulating partial messages

    while server_state_obj.app_running:
        with client_lock: # Synchronize access to shared server state
            if server_state_obj.client_connection is not conn:
                print(f"DEBUG Server Handler ({addr}): Stale connection. Exiting thread.") # DEBUG
                break 
        try:
            chunk = conn.recv(server_state_obj.buffer_size)
            if not chunk: 
                print(f"DEBUG Server Handler ({addr}): Client disconnected (received empty data).") # DEBUG
                break
            
            # print(f"DEBUG Server Handler ({addr}): Received chunk: {chunk[:60]}...") # DEBUG - can be noisy
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)

            if decoded_inputs:
                last_input_data = decoded_inputs[-1] 
                # print(f"DEBUG Server Handler ({addr}): Decoded client input: {last_input_data}") # DEBUG
                if "input" in last_input_data:
                    with client_lock:
                        if server_state_obj.client_connection is conn: 
                            server_state_obj.client_input_buffer = last_input_data["input"]
                            # print(f"DEBUG Server Handler ({addr}): Updated client_input_buffer: {server_state_obj.client_input_buffer}") # DEBUG
        except socket.timeout:
            continue 
        except socket.error as e:
            if server_state_obj.app_running:
                print(f"DEBUG Server Handler ({addr}): Socket error: {e}. Assuming disconnect.") # DEBUG
            break 
        except Exception as e:
            if server_state_obj.app_running:
                print(f"DEBUG Server Handler ({addr}): Unexpected error: {e}") # DEBUG
                traceback.print_exc()
            break

    with client_lock:
        if server_state_obj.client_connection is conn: 
            print(f"DEBUG Server Handler ({addr}): Closing active connection from handler.") # DEBUG
            server_state_obj.client_connection = None 
            server_state_obj.client_input_buffer = {"disconnect": True} 
    try:
        conn.shutdown(socket.SHUT_RDWR) 
    except: pass 
    try:
        conn.close() 
    except: pass
    print(f"DEBUG Server: Client handler for {addr} finished.") # DEBUG


def run_server_mode(screen: pygame.Surface, clock: pygame.time.Clock, 
                    fonts: dict, game_elements_ref: dict, server_state_obj: ServerState):
    """
    Main function to run the game in server mode.
    Manages client connections, game loop, and state synchronization.
    """
    print("DEBUG Server: Entering run_server_mode.") # DEBUG
    pygame.display.set_caption("Platformer - HOST (P1: WASD+VB | Self-Harm: H | Heal: G | Reset: R)")
    
    server_state_obj.app_running = True 
    current_width, current_height = screen.get_size()

    if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
        print("DEBUG Server: Broadcast thread already running (normal if re-entering server mode without full app restart).") # DEBUG
    else:
        print("DEBUG Server: Starting broadcast thread.") # DEBUG
        server_state_obj.broadcast_thread = threading.Thread(
            target=broadcast_presence_thread, args=(server_state_obj,), daemon=True
        )
        server_state_obj.broadcast_thread.start()

    if server_state_obj.server_tcp_socket: 
        print("DEBUG Server: Closing existing TCP socket before creating new one.") # DEBUG
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1) 
        server_state_obj.server_tcp_socket.settimeout(1.0) 
        print(f"DEBUG Server: Listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}") # DEBUG
    except socket.error as e:
        print(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e}")
        return 

    print("DEBUG Server: Waiting for Player 2 to connect...") # DEBUG
    temp_client_conn_obj = None 
    while temp_client_conn_obj is None and server_state_obj.app_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: server_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width, current_height = max(320,event.w), max(240,event.h)
                    screen = pygame.display.set_mode((current_width, current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"): 
                        game_elements_ref["camera"].screen_width = current_width
                        game_elements_ref["camera"].screen_height = current_height
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                server_state_obj.app_running = False; break 
        if not server_state_obj.app_running: break
        
        screen.fill(C.BLACK)
        if fonts.get("large"):
            wait_text_surf = fonts["large"].render("Waiting for P2...", True, C.WHITE)
            screen.blit(wait_text_surf, wait_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip()
        clock.tick(10) 

        try:
            temp_client_conn_obj, temp_client_addr_tuple = server_state_obj.server_tcp_socket.accept()
            with client_lock:
                 if server_state_obj.client_connection: 
                     print("DEBUG Server: Closing pre-existing client connection before new one.") # DEBUG
                     try: server_state_obj.client_connection.close()
                     except: pass
                 server_state_obj.client_connection = temp_client_conn_obj
                 server_state_obj.client_address = temp_client_addr_tuple
                 server_state_obj.client_input_buffer = {} 
                 print(f"DEBUG Server: Accepted connection from {temp_client_addr_tuple}") # DEBUG
        except socket.timeout:
            continue 
        except Exception as e:
            if server_state_obj.app_running:
                print(f"DEBUG Server: Error during client accept: {e}") # DEBUG
            break 
    
    if not server_state_obj.app_running or server_state_obj.client_connection is None:
        print("DEBUG Server: Exiting wait loop (no client connected or app closed).") # DEBUG
        return 

    print(f"DEBUG Server: Client {server_state_obj.client_address} connected. Starting game...") # DEBUG
    if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
        print("DEBUG Server: Previous client handler thread still alive. Attempting to join.") # DEBUG
        server_state_obj.client_handler_thread.join(timeout=0.2) 
    
    server_state_obj.client_handler_thread = threading.Thread(
        target=handle_client_connection_thread, 
        args=(server_state_obj.client_connection, server_state_obj.client_address, server_state_obj), 
        daemon=True
    )
    server_state_obj.client_handler_thread.start()
    print("DEBUG Server: Client handler thread started.") # DEBUG

    p1 = game_elements_ref.get("player1") 
    p2 = game_elements_ref.get("player2") 
    if p1: print(f"DEBUG Server: P1 instance from game_elements: {p1}, Valid: {p1._valid_init if p1 else 'N/A'}") # DEBUG
    if p2: print(f"DEBUG Server: P2 instance from game_elements: {p2}, Valid: {p2._valid_init if p2 else 'N/A'}") # DEBUG


    p1_key_map_config = { 
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e
    }
    
    server_game_active = True
    while server_game_active and server_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0 
        now_ticks_server = pygame.time.get_ticks() 
        
        pygame_events = pygame.event.get()
        keys_pressed_p1 = pygame.key.get_pressed()

        is_p1_game_over_for_reset = False
        if p1 and p1._valid_init:
            if p1.is_dead and (not p1.alive() or (hasattr(p1, 'death_animation_finished') and p1.death_animation_finished)):
                is_p1_game_over_for_reset = True
        else: 
            is_p1_game_over_for_reset = True

        host_requested_reset = False
        for event in pygame_events:
            if event.type == pygame.QUIT: server_game_active = False; server_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width, current_height = max(320,event.w), max(240,event.h)
                    screen = pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"):
                        game_elements_ref["camera"].screen_width = current_width
                        game_elements_ref["camera"].screen_height = current_height
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: server_game_active = False 
                if event.key == pygame.K_r: host_requested_reset = True
                if p1 and p1._valid_init: 
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'): p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'): p1.heal_to_full()
        
        if not server_state_obj.app_running or not server_game_active: break

        if p1 and p1._valid_init and not p1.is_dead:
            if hasattr(p1, 'handle_mapped_input'):
                p1.handle_mapped_input(keys_pressed_p1, pygame_events, p1_key_map_config)

        p2_network_input, client_disconnected_signal, p2_requested_reset = None, False, False
        with client_lock: 
            if server_state_obj.client_input_buffer:
                buffered_input = server_state_obj.client_input_buffer
                # print(f"DEBUG Server: Processing client_input_buffer: {buffered_input}") # DEBUG
                if buffered_input.get("disconnect"): client_disconnected_signal = True
                elif buffered_input.get("action_reset", False): p2_requested_reset = True
                elif p2 and p2._valid_init:
                    if buffered_input.get("action_self_harm", False) and hasattr(p2, 'self_inflict_damage'):
                        p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    elif buffered_input.get("action_heal", False) and hasattr(p2, 'heal_to_full'):
                        p2.heal_to_full()
                else: 
                    p2_network_input = buffered_input.copy()
                server_state_obj.client_input_buffer = {} 

        if client_disconnected_signal:
            print("DEBUG Server: Client disconnected signal received in main loop.") # DEBUG
            server_game_active = False 
            break 

        if p2 and p2._valid_init and p2_network_input and hasattr(p2, 'handle_network_input'):
            # print(f"DEBUG Server: Handling P2 network input: {p2_network_input}") # DEBUG
            p2.handle_network_input(p2_network_input) 

        if host_requested_reset or (p2_requested_reset and is_p1_game_over_for_reset):
            print("DEBUG Server: Game state reset triggered.") # DEBUG
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)

        if p1 and p1._valid_init:
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"], 
                      game_elements_ref["hazard_sprites"], other_players_for_p1_update, game_elements_ref["enemy_list"])

        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"], 
                      game_elements_ref["hazard_sprites"], other_players_for_p2_update, game_elements_ref["enemy_list"])

        active_players_for_enemy_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy in list(game_elements_ref.get("enemy_list", [])): 
            if enemy._valid_init:
                enemy.update(dt_sec, active_players_for_enemy_ai, game_elements_ref["platform_sprites"], game_elements_ref["hazard_sprites"])
                if enemy.is_dead and hasattr(enemy, 'death_animation_finished') and \
                   enemy.death_animation_finished and enemy.alive():
                    if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"server_killing_enemy_{enemy.enemy_id}"):
                         print(f"Server: Auto-killing enemy {enemy.enemy_id} as death anim finished.")
                    enemy.kill() 
            
        hittable_characters_server_group = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init: hittable_characters_server_group.add(p1)
        if p2 and p2.alive() and p2._valid_init: hittable_characters_server_group.add(p2)
        for enemy_inst_proj in game_elements_ref.get("enemy_list", []):
            if enemy_inst_proj and enemy_inst_proj.alive() and enemy_inst_proj._valid_init:
                hittable_characters_server_group.add(enemy_inst_proj)
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(dt_sec, game_elements_ref["platform_sprites"], hittable_characters_server_group)
        
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)
        server_current_chest = game_elements_ref.get("current_chest")
        if server_current_chest and server_current_chest.alive(): 
            player_who_collected_chest = None
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and pygame.sprite.collide_rect(p1, server_current_chest):
                player_who_collected_chest = p1
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and pygame.sprite.collide_rect(p2, server_current_chest):
                player_who_collected_chest = p2
            
            if player_who_collected_chest:
                server_current_chest.collect(player_who_collected_chest) 
                game_elements_ref["current_chest"] = None 
        
        server_camera = game_elements_ref.get("camera")
        if server_camera:
            camera_focus_target = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead: camera_focus_target = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead: camera_focus_target = p2
            
            if camera_focus_target: server_camera.update(camera_focus_target)
            else: server_camera.static_update() 

        if server_state_obj.client_connection: 
            network_state_to_send = get_network_game_state(game_elements_ref)
            # print(f"DEBUG Server: State to send: P1 pos {network_state_to_send.get('p1', {}).get('pos')}, P2 pos {network_state_to_send.get('p2', {}).get('pos')}") # DEBUG
            encoded_game_state = encode_data(network_state_to_send)
            if encoded_game_state:
                try:
                    server_state_obj.client_connection.sendall(encoded_game_state)
                except socket.error as e:
                    print(f"DEBUG Server: Send failed to client: {e}. Client likely disconnected.") # DEBUG
                    server_game_active = False 
                    with client_lock: server_state_obj.client_connection = None 
                    break 
            # else: print("DEBUG Server Error: Failed to encode game state for sending.") # DEBUG
        
        try:
            draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_server)
        except Exception as e:
            print(f"Server draw error: {e}"); traceback.print_exc()
            server_game_active = False; break
        pygame.display.flip()

    print("DEBUG Server: Exiting active game loop.") # DEBUG
    
    connection_to_close_at_server_exit = None
    with client_lock:
        if server_state_obj.client_connection:
            connection_to_close_at_server_exit = server_state_obj.client_connection
            server_state_obj.client_connection = None 
    if connection_to_close_at_server_exit:
        print("DEBUG Server: Mode exit cleanup - closing client connection.") # DEBUG
        try:
            connection_to_close_at_server_exit.shutdown(socket.SHUT_RDWR)
            connection_to_close_at_server_exit.close()
        except: pass 

    if server_state_obj.server_tcp_socket:
        print("DEBUG Server: Closing main TCP listening socket.") # DEBUG
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
    
    print("DEBUG Server: Server mode finished and returned to caller.") # DEBUG

########## END OF FILE: server_logic.py ##########