########## START OF FILE: client_logic.py ##########

# client_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles client-side game logic, connection to server, and LAN discovery.
"""
import pygame
import socket
import time
import traceback
import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import set_network_game_state
from enemy import Enemy # For print_limiter access if needed, or for type hinting
from game_ui import draw_platformer_scene_on_surface # For drawing client's view

class ClientState:
    """
    A simple class to hold client-specific state used by the client's
    main loop and helper functions.
    """
    def __init__(self):
        self.client_tcp_socket = None        # TCP socket for communication with the server
        self.server_state_buffer = b""       # Buffer for accumulating data from the server
        self.last_received_server_state = None # Stores the most recent complete game state from server
        self.app_running = True              # Global flag: True if the application is running (controlled by main.py)
        
        # Configuration for LAN discovery (can be loaded from constants.py)
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.client_search_timeout_s = getattr(C, "CLIENT_SEARCH_TIMEOUT_S", 5.0)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)


def find_server_on_lan(screen: pygame.Surface, fonts: dict, 
                       clock_obj: pygame.time.Clock, client_state_obj: ClientState):
    """
    Searches for a game server on the LAN by listening for UDP broadcasts.
    Displays a "Searching..." message on the screen.
    Returns (found_server_ip, found_server_port) or (None, None) if not found or cancelled.
    """
    print("DEBUG Client (find_server_on_lan): Starting LAN server search.") # DEBUG
    pygame.display.set_caption("Platformer - Searching for Server on LAN...")
    current_width, current_height = screen.get_size()
    search_text_surf = fonts.get("large", pygame.font.Font(None, 30)).render( # Fallback font
        "Searching for server on LAN...", True, C.WHITE
    )
    
    listen_socket, found_server_ip, found_server_port = None, None, None

    try:
        # Create and configure the UDP socket for listening to broadcasts
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to all available interfaces on the specified discovery port
        listen_socket.bind(('', client_state_obj.discovery_port_udp)) 
        listen_socket.settimeout(0.5) # Non-blocking recvfrom
        print(f"DEBUG Client (find_server_on_lan): UDP listen socket bound to port {client_state_obj.discovery_port_udp}.") # DEBUG
    except socket.error as e:
        print(f"Client Error: Failed to bind UDP listen socket on port {client_state_obj.discovery_port_udp}: {e}")
        screen.fill(C.BLACK)
        err_msg = f"Error: Cannot listen on UDP port {client_state_obj.discovery_port_udp}."
        if fonts.get("small"):
            err_surf = fonts["small"].render(err_msg, True, C.RED)
            screen.blit(err_surf, err_surf.get_rect(center=(current_width//2, current_height // 2)))
        pygame.display.flip(); time.sleep(4)
        return None, None

    start_search_time = time.time()
    client_local_ip = get_local_ip() 
    print(f"DEBUG Client (find_server_on_lan): Searching for LAN servers (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.") # DEBUG

    # Loop for the duration of the search timeout or until app quits/server found
    while time.time() - start_search_time < client_state_obj.client_search_timeout_s and \
          client_state_obj.app_running and not found_server_ip:
        
        # Handle Pygame events (Quit, Resize, Escape to cancel search)
        for event in pygame.event.get():
             if event.type == pygame.QUIT: client_state_obj.app_running = False; break
             if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width,current_height=max(320,event.w),max(240,event.h)
                    screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    search_text_surf = fonts.get("large", pygame.font.Font(None,30)).render(
                        "Searching for server on LAN...", True, C.WHITE) # Re-render if size changes
             if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                 print("DEBUG Client (find_server_on_lan): LAN server search cancelled by user.");  # DEBUG
                 if listen_socket: listen_socket.close()
                 return None, None # Exit search and return to menu
        if not client_state_obj.app_running: break

        # Update "Searching..." display
        screen.fill(C.BLACK)
        screen.blit(search_text_surf, search_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip()
        clock_obj.tick(10) # Low FPS during search

        raw_udp_data, decoded_udp_message = None, None
        try:
            raw_udp_data, sender_address = listen_socket.recvfrom(client_state_obj.buffer_size)
            # print(f"DEBUG Client (find_server_on_lan): Received UDP data from {sender_address}: {raw_udp_data[:60]}...") # DEBUG - noisy
            decoded_messages_list, _ = decode_data_stream(raw_udp_data)
            if not decoded_messages_list: continue 
            
            decoded_udp_message = decoded_messages_list[0] 
            # print(f"DEBUG Client (find_server_on_lan): Decoded UDP message: {decoded_udp_message}") # DEBUG
            if (isinstance(decoded_udp_message, dict) and
                decoded_udp_message.get("service") == client_state_obj.service_name and
                isinstance(decoded_udp_message.get("tcp_ip"), str) and
                isinstance(decoded_udp_message.get("tcp_port"), int)):
                
                server_ip = decoded_udp_message["tcp_ip"]
                server_port = decoded_udp_message["tcp_port"]
                print(f"DEBUG Client (find_server_on_lan): Found server '{client_state_obj.service_name}' at {server_ip}:{server_port}") # DEBUG
                found_server_ip, found_server_port = server_ip, server_port
        except socket.timeout:
            continue 
        except Exception as e:
            print(f"Client: Error processing received UDP broadcast: {e}")
            traceback.print_exc()

    if listen_socket: listen_socket.close() 

    if not found_server_ip and client_state_obj.app_running: 
        print(f"DEBUG Client (find_server_on_lan): No server found for '{client_state_obj.service_name}' after timeout.") # DEBUG
        screen.fill(C.BLACK)
        if fonts.get("large"):
            fail_surf = fonts["large"].render("Server Not Found!", True, C.RED)
            screen.blit(fail_surf, fail_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip(); time.sleep(3) 
    elif not client_state_obj.app_running:
        print("DEBUG Client (find_server_on_lan): LAN server search aborted because application is quitting.") # DEBUG
        
    return found_server_ip, found_server_port


def run_client_mode(screen: pygame.Surface, clock: pygame.time.Clock, 
                    fonts: dict, game_elements_ref: dict, 
                    client_state_obj: ClientState, target_ip_port_str: str = None):
    """
    Main function to run the game in client mode.
    Connects to a server (either specified or found via LAN) and synchronizes game state.
    """
    print("DEBUG Client (run_client_mode): Entering client mode.") # DEBUG
    client_state_obj.app_running = True 
    current_width, current_height = screen.get_size()
    
    server_ip_to_connect, server_port_to_connect = None, C.SERVER_PORT_TCP 

    if target_ip_port_str: 
        print(f"DEBUG Client (run_client_mode): Direct IP specified: {target_ip_port_str}") # DEBUG
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1: 
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError: 
                print(f"Client Warning: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else: 
        print("DEBUG Client (run_client_mode): No direct IP, attempting LAN discovery.") # DEBUG
        server_ip_to_connect, found_server_port = find_server_on_lan(screen, fonts, clock, client_state_obj)
        if found_server_port: server_port_to_connect = found_server_port

    if not server_ip_to_connect: 
        print("DEBUG Client (run_client_mode): Exiting client mode (no server target).") # DEBUG
        return 
    if not client_state_obj.app_running: 
        print("DEBUG Client (run_client_mode): Exiting client mode (application closed).") # DEBUG
        return

    if client_state_obj.client_tcp_socket: 
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    connection_succeeded, connection_error_msg = False, "Unknown Connection Error"
    try:
        print(f"DEBUG Client (run_client_mode): Attempting to connect to server at {server_ip_to_connect}:{server_port_to_connect}...") # DEBUG
        pygame.display.set_caption(f"Platformer - Connecting to {server_ip_to_connect}...")
        screen.fill(C.BLACK) 
        if fonts.get("large"):
            conn_text_surf = fonts["large"].render(f"Connecting...", True, C.WHITE)
            screen.blit(conn_text_surf, conn_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip()

        client_state_obj.client_tcp_socket.settimeout(10.0) 
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        client_state_obj.client_tcp_socket.settimeout(0.05) 
        print("DEBUG Client (run_client_mode): TCP Connection to server successful!") # DEBUG
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e: connection_error_msg = f"Connection Error ({e.strerror if hasattr(e, 'strerror') else e})"
    except Exception as e: connection_error_msg = f"Unexpected Connection Error: {e}"

    if not connection_succeeded:
        print(f"DEBUG Client (run_client_mode): Failed to connect to server: {connection_error_msg}") # DEBUG
        screen.fill(C.BLACK) 
        if fonts.get("large"):
            fail_text_surf = fonts["large"].render(f"Connection Failed", True, C.RED)
            screen.blit(fail_text_surf, fail_text_surf.get_rect(center=(current_width//2, current_height//2 - 30)))
        if fonts.get("small"):
            reason_surf = fonts["small"].render(connection_error_msg, True, C.WHITE)
            screen.blit(reason_surf, reason_surf.get_rect(center=(current_width//2, current_height//2 + 30)))
        pygame.display.flip(); time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return 

    pygame.display.set_caption("Platformer - CLIENT (You are P2: WASD+VB | Self-Harm: H | Heal: G | Reset: Enter)")
    
    p2_controlled_by_client = game_elements_ref.get("player2") 
    p1_remote_on_client = game_elements_ref.get("player1")     
    print(f"DEBUG Client (run_client_mode): P1 (remote) instance: {p1_remote_on_client}, P2 (local) instance: {p2_controlled_by_client}") # DEBUG
    if p1_remote_on_client: print(f"DEBUG Client: P1 Valid: {p1_remote_on_client._valid_init}, P1 Pos: {p1_remote_on_client.pos if hasattr(p1_remote_on_client, 'pos') else 'N/A'}") # DEBUG
    if p2_controlled_by_client: print(f"DEBUG Client: P2 Valid: {p2_controlled_by_client._valid_init}, P2 Pos: {p2_controlled_by_client.pos if hasattr(p2_controlled_by_client, 'pos') else 'N/A'}") # DEBUG

    
    p2_client_key_map = { 
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e,
    }

    client_game_active = True
    client_state_obj.server_state_buffer = b"" 
    client_state_obj.last_received_server_state = None 

    while client_game_active and client_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0 
        now_ticks_client = pygame.time.get_ticks()

        client_initiated_actions = {'action_reset': False, 'action_self_harm': False, 'action_heal': False}
        server_indicated_game_over = False
        if client_state_obj.last_received_server_state and \
           'game_over' in client_state_obj.last_received_server_state:
            server_indicated_game_over = client_state_obj.last_received_server_state['game_over']

        pygame_events_client = pygame.event.get()
        keys_pressed_client = pygame.key.get_pressed()
        for event in pygame_events_client:
            if event.type == pygame.QUIT: client_game_active = False; client_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width,current_height=max(320,event.w),max(240,event.h)
                    screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"): 
                        game_elements_ref["camera"].screen_width = current_width
                        game_elements_ref["camera"].screen_height = current_height
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: client_game_active = False 
                if event.key == pygame.K_RETURN and server_indicated_game_over :
                    client_initiated_actions['action_reset'] = True
                if event.key == pygame.K_h: client_initiated_actions['action_self_harm'] = True
                if event.key == pygame.K_g: client_initiated_actions['action_heal'] = True
        
        if not client_state_obj.app_running or not client_game_active: break

        p2_input_state_for_server = {}
        if p2_controlled_by_client and hasattr(p2_controlled_by_client, 'get_input_state_for_network'):
             p2_input_state_for_server = p2_controlled_by_client.get_input_state_for_network(
                 keys_pressed_client, pygame_events_client, p2_client_key_map
             )
        p2_input_state_for_server.update(client_initiated_actions) 

        if client_state_obj.client_tcp_socket:
            client_input_payload = {"input": p2_input_state_for_server}
            encoded_client_payload = encode_data(client_input_payload)
            if encoded_client_payload:
                try:
                    # print(f"DEBUG Client: Sending input to server: {client_input_payload}") # DEBUG - noisy
                    client_state_obj.client_tcp_socket.sendall(encoded_client_payload)
                except socket.error as e:
                    print(f"Client: Send to server failed: {e}. Server might have disconnected.")
                    client_game_active = False; break 
        
        if client_state_obj.client_tcp_socket:
            try:
                server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size * 2) 
                if not server_data_chunk: 
                    print("DEBUG Client: Server disconnected (received empty data from recv).") # DEBUG
                    client_game_active = False; break
                
                # print(f"DEBUG Client: Received chunk from server: {server_data_chunk[:100]}...") # DEBUG - noisy
                client_state_obj.server_state_buffer += server_data_chunk
                decoded_server_states, client_state_obj.server_state_buffer = \
                    decode_data_stream(client_state_obj.server_state_buffer)
                
                if decoded_server_states: 
                    client_state_obj.last_received_server_state = decoded_server_states[-1] 
                    # print(f"DEBUG Client: Received new game state. P1 pos: {client_state_obj.last_received_server_state.get('p1', {}).get('pos')}, P2 pos: {client_state_obj.last_received_server_state.get('p2', {}).get('pos')}") # DEBUG
                    set_network_game_state(client_state_obj.last_received_server_state, game_elements_ref, client_player_id=2)
                    # After state update, verify player instances
                    # p1_after_update = game_elements_ref.get("player1")
                    # p2_after_update = game_elements_ref.get("player2")
                    # if p1_after_update: print(f"DEBUG Client: P1 after state update. Pos: {p1_after_update.pos if hasattr(p1_after_update, 'pos') else 'N/A'}, Valid: {p1_after_update._valid_init}, Alive: {p1_after_update.alive() if hasattr(p1_after_update, 'alive') else 'N/A'}") # DEBUG
                    # if p2_after_update: print(f"DEBUG Client: P2 after state update. Pos: {p2_after_update.pos if hasattr(p2_after_update, 'pos') else 'N/A'}, Valid: {p2_after_update._valid_init}, Alive: {p2_after_update.alive() if hasattr(p2_after_update, 'alive') else 'N/A'}") # DEBUG

            
            except socket.timeout: pass 
            except socket.error as e:
                print(f"Client: Recv error from server: {e}. Server might have disconnected.")
                client_game_active = False; break
            except Exception as e:
                print(f"Client: Error processing data from server: {e}"); traceback.print_exc()
                client_game_active = False; break

        if p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and \
           hasattr(p1_remote_on_client, 'animate'):
            p1_remote_on_client.animate() 

        if p2_controlled_by_client and p2_controlled_by_client.alive() and \
           p2_controlled_by_client._valid_init and hasattr(p2_controlled_by_client, 'animate'):
            p2_controlled_by_client.animate() 

        for enemy_client in game_elements_ref.get("enemy_list", []):
            if enemy_client.alive() and enemy_client._valid_init and hasattr(enemy_client, 'animate'):
                enemy_client.animate()
            if enemy_client.is_dead and hasattr(enemy_client, 'death_animation_finished') and \
               enemy_client.death_animation_finished and enemy_client.alive():
                if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"client_killing_enemy_{enemy_client.enemy_id}"):
                     print(f"Client: Visually removing enemy {enemy_client.enemy_id} as death anim finished.")
                enemy_client.kill() 

        for proj_client in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if proj_client.alive() and hasattr(proj_client, 'animate'):
                proj_client.animate() 

        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

        client_camera = game_elements_ref.get("camera")
        if client_camera:
            camera_focus_target_client = None
            if p2_controlled_by_client and p2_controlled_by_client.alive() and \
               p2_controlled_by_client._valid_init and not p2_controlled_by_client.is_dead :
                camera_focus_target_client = p2_controlled_by_client
            elif p1_remote_on_client and p1_remote_on_client.alive() and \
                 p1_remote_on_client._valid_init and not p1_remote_on_client.is_dead:
                camera_focus_target_client = p1_remote_on_client 
            
            if camera_focus_target_client: client_camera.update(camera_focus_target_client)
            else: client_camera.static_update() 
            
        try:
            draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_client)
        except Exception as e:
            print(f"Client draw error: {e}"); traceback.print_exc()
            client_game_active=False; break
        pygame.display.flip()

    print("DEBUG Client: Exiting active game loop.") # DEBUG
    if client_state_obj.client_tcp_socket:
        print("DEBUG Client: Closing TCP socket to server.") # DEBUG
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    print("DEBUG Client: Client mode finished and returned to caller.") # DEBUG

########## END OF FILE: client_logic.py ##########