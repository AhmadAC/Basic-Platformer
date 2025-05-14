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
    print(f"Client searching for LAN servers (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.")

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
                 print("Client: LAN server search cancelled by user."); 
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
            # Attempt to decode the received UDP packet
            decoded_messages_list, _ = decode_data_stream(raw_udp_data)
            if not decoded_messages_list: continue # No valid JSON message in packet
            
            decoded_udp_message = decoded_messages_list[0] # Use the first valid message
            # Check if the message matches the expected service
            if (isinstance(decoded_udp_message, dict) and
                decoded_udp_message.get("service") == client_state_obj.service_name and
                isinstance(decoded_udp_message.get("tcp_ip"), str) and
                isinstance(decoded_udp_message.get("tcp_port"), int)):
                
                server_ip = decoded_udp_message["tcp_ip"]
                server_port = decoded_udp_message["tcp_port"]
                print(f"Client: Found server '{client_state_obj.service_name}' at {server_ip}:{server_port} (Broadcast from: {sender_address[0]})")
                found_server_ip, found_server_port = server_ip, server_port
                # break # Found server, exit search loop (already handled by not found_server_ip in while condition)
        except socket.timeout:
            continue # No broadcast received in this interval
        except Exception as e:
            print(f"Client: Error processing received UDP broadcast: {e}")
            traceback.print_exc()

    if listen_socket: listen_socket.close() # Clean up listening socket

    if not found_server_ip and client_state_obj.app_running: # If search timed out and app still running
        print(f"Client: No server found for '{client_state_obj.service_name}' after timeout.")
        screen.fill(C.BLACK)
        if fonts.get("large"):
            fail_surf = fonts["large"].render("Server Not Found!", True, C.RED)
            screen.blit(fail_surf, fail_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip(); time.sleep(3) # Display message briefly
    elif not client_state_obj.app_running:
        print("Client: LAN server search aborted because application is quitting.")
        
    return found_server_ip, found_server_port


def run_client_mode(screen: pygame.Surface, clock: pygame.time.Clock, 
                    fonts: dict, game_elements_ref: dict, 
                    client_state_obj: ClientState, target_ip_port_str: str = None):
    """
    Main function to run the game in client mode.
    Connects to a server (either specified or found via LAN) and synchronizes game state.
    """
    client_state_obj.app_running = True # Ensure flag is set for this mode
    current_width, current_height = screen.get_size()
    
    server_ip_to_connect, server_port_to_connect = None, C.SERVER_PORT_TCP # Default port

    if target_ip_port_str: # Direct IP connection specified
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1: # If port is also specified
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError: 
                print(f"Client Warning: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else: # No direct IP, attempt LAN Discovery
        server_ip_to_connect, found_server_port = find_server_on_lan(screen, fonts, clock, client_state_obj)
        if found_server_port: server_port_to_connect = found_server_port

    if not server_ip_to_connect: # If no server found or specified
        print("Client: Exiting client mode (no server target).")
        return # Return to main menu
    if not client_state_obj.app_running: # If app was closed during server search/input
        print("Client: Exiting client mode (application closed).")
        return

    # --- Attempt to Connect to Server ---
    if client_state_obj.client_tcp_socket: # Close any pre-existing socket
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    connection_succeeded, connection_error_msg = False, "Unknown Connection Error"
    try:
        print(f"Client: Attempting to connect to server at {server_ip_to_connect}:{server_port_to_connect}...")
        pygame.display.set_caption(f"Platformer - Connecting to {server_ip_to_connect}...")
        screen.fill(C.BLACK) # Display "Connecting..."
        if fonts.get("large"):
            conn_text_surf = fonts["large"].render(f"Connecting...", True, C.WHITE)
            screen.blit(conn_text_surf, conn_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip()

        client_state_obj.client_tcp_socket.settimeout(10.0) # Timeout for connection attempt
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        # Set to non-blocking for game loop (very short timeout for recv)
        client_state_obj.client_tcp_socket.settimeout(0.05) 
        print("Client: TCP Connection to server successful!")
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e: connection_error_msg = f"Connection Error ({e.strerror if hasattr(e, 'strerror') else e})"
    except Exception as e: connection_error_msg = f"Unexpected Connection Error: {e}"

    if not connection_succeeded:
        print(f"Client: Failed to connect to server: {connection_error_msg}")
        screen.fill(C.BLACK) # Display connection failed message
        if fonts.get("large"):
            fail_text_surf = fonts["large"].render(f"Connection Failed", True, C.RED)
            screen.blit(fail_text_surf, fail_text_surf.get_rect(center=(current_width//2, current_height//2 - 30)))
        if fonts.get("small"):
            reason_surf = fonts["small"].render(connection_error_msg, True, C.WHITE)
            screen.blit(reason_surf, reason_surf.get_rect(center=(current_width//2, current_height//2 + 30)))
        pygame.display.flip(); time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return # Return to main menu

    pygame.display.set_caption("Platformer - CLIENT (You are P2: WASD+VB | Self-Harm: H | Heal: G | Reset: Enter)")
    
    # --- Client Game Loop ---
    p2_controlled_by_client = game_elements_ref.get("player2") # Local player on this client
    p1_remote_on_client = game_elements_ref.get("player1")     # Remote player (host)
    
    # Key mapping for client's local player (P2)
    p2_client_key_map = { 
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e,
    }

    client_game_active = True
    client_state_obj.server_state_buffer = b"" # Reset buffer for server data
    client_state_obj.last_received_server_state = None # Reset last known server state

    while client_game_active and client_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0 # Delta time
        now_ticks_client = pygame.time.get_ticks()

        # Prepare client-side actions (like reset request)
        client_initiated_actions = {'action_reset': False, 'action_self_harm': False, 'action_heal': False}
        # Check game_over state from last server update to enable/disable reset from client
        server_indicated_game_over = False
        if client_state_obj.last_received_server_state and \
           'game_over' in client_state_obj.last_received_server_state:
            server_indicated_game_over = client_state_obj.last_received_server_state['game_over']

        # Handle Pygame events for client input and window management
        pygame_events_client = pygame.event.get()
        keys_pressed_client = pygame.key.get_pressed()
        for event in pygame_events_client:
            if event.type == pygame.QUIT: client_game_active = False; client_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width,current_height=max(320,event.w),max(240,event.h)
                    screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"): # Update camera screen size
                        game_elements_ref["camera"].screen_width = current_width
                        game_elements_ref["camera"].screen_height = current_height
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: client_game_active = False # Exit client game to main menu
                # Client (P2) can request reset with Enter if server indicated game_over (P1 is down)
                if event.key == pygame.K_RETURN and server_indicated_game_over :
                    client_initiated_actions['action_reset'] = True
                # Client debug keys for their player (P2)
                if event.key == pygame.K_h: client_initiated_actions['action_self_harm'] = True
                if event.key == pygame.K_g: client_initiated_actions['action_heal'] = True
        
        if not client_state_obj.app_running or not client_game_active: break

        # Prepare P2's input state (local client player) to send to server
        p2_input_state_for_server = {}
        if p2_controlled_by_client and hasattr(p2_controlled_by_client, 'get_input_state_for_network'):
             p2_input_state_for_server = p2_controlled_by_client.get_input_state_for_network(
                 keys_pressed_client, pygame_events_client, p2_client_key_map
             )
        p2_input_state_for_server.update(client_initiated_actions) # Add special actions like reset

        # Send local player's input to server
        if client_state_obj.client_tcp_socket:
            client_input_payload = {"input": p2_input_state_for_server}
            encoded_client_payload = encode_data(client_input_payload)
            if encoded_client_payload:
                try:
                    client_state_obj.client_tcp_socket.sendall(encoded_client_payload)
                except socket.error as e:
                    print(f"Client: Send to server failed: {e}. Server might have disconnected.")
                    client_game_active = False; break 
            # else: print("Client Error: Failed to encode input payload for server.")
        
        # Receive game state from server
        if client_state_obj.client_tcp_socket:
            try:
                server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size * 2) 
                if not server_data_chunk: # Server disconnected
                    print("Client: Server disconnected (received empty data from recv).")
                    client_game_active = False; break
                
                client_state_obj.server_state_buffer += server_data_chunk
                # Process buffer for complete game state messages
                decoded_server_states, client_state_obj.server_state_buffer = \
                    decode_data_stream(client_state_obj.server_state_buffer)
                
                if decoded_server_states: # If one or more complete states received
                    client_state_obj.last_received_server_state = decoded_server_states[-1] # Use the latest one
                    # Apply the received state to local game elements, client is P2
                    set_network_game_state(client_state_obj.last_received_server_state, game_elements_ref, client_player_id=2)
            
            except socket.timeout: pass # Normal for non-blocking socket, no data this tick
            except socket.error as e:
                print(f"Client: Recv error from server: {e}. Server might have disconnected.")
                client_game_active = False; break
            except Exception as e:
                print(f"Client: Error processing data from server: {e}"); traceback.print_exc()
                client_game_active = False; break

        # --- Client-Side Updates (mostly visual, based on server state) ---
        # Animate Player 1 (remote, state driven by server)
        if p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and \
           hasattr(p1_remote_on_client, 'animate'):
            p1_remote_on_client.animate() 

        # Animate Player 2 (local client's player)
        # Its state is primarily set by server, but local animation gives responsiveness.
        if p2_controlled_by_client and p2_controlled_by_client.alive() and \
           p2_controlled_by_client._valid_init and hasattr(p2_controlled_by_client, 'animate'):
            p2_controlled_by_client.animate() 

        # Animate enemies based on their state from server
        for enemy_client in game_elements_ref.get("enemy_list", []):
            if enemy_client.alive() and enemy_client._valid_init and hasattr(enemy_client, 'animate'):
                enemy_client.animate()
            # Visual cleanup for enemies whose death animation finished locally
            if enemy_client.is_dead and hasattr(enemy_client, 'death_animation_finished') and \
               enemy_client.death_animation_finished and enemy_client.alive():
                if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"client_killing_enemy_{enemy_client.enemy_id}"):
                     print(f"Client: Visually removing enemy {enemy_client.enemy_id} as death anim finished.")
                enemy_client.kill() 

        # Animate projectiles (state driven by server)
        for proj_client in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if proj_client.alive() and hasattr(proj_client, 'animate'):
                proj_client.animate() 

        # Update collectibles (e.g., Chest animations)
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

        # Update camera: Client's camera focuses on their own player (P2)
        client_camera = game_elements_ref.get("camera")
        if client_camera:
            # Prioritize local P2, fallback to remote P1 if P2 is dead/invalid
            camera_focus_target_client = None
            if p2_controlled_by_client and p2_controlled_by_client.alive() and \
               p2_controlled_by_client._valid_init and not p2_controlled_by_client.is_dead :
                camera_focus_target_client = p2_controlled_by_client
            elif p1_remote_on_client and p1_remote_on_client.alive() and \
                 p1_remote_on_client._valid_init and not p1_remote_on_client.is_dead:
                camera_focus_target_client = p1_remote_on_client # Fallback if P2 is out
            
            if camera_focus_target_client: client_camera.update(camera_focus_target_client)
            else: client_camera.static_update() # No valid target
            
        # Draw the client's view of the game scene
        try:
            draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_client)
        except Exception as e:
            print(f"Client draw error: {e}"); traceback.print_exc()
            client_game_active=False; break
        pygame.display.flip()

    # --- End of Client Game Loop ---
    print("Client: Exiting active game loop.")
    if client_state_obj.client_tcp_socket:
        print("Client: Closing TCP socket to server.")
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    print("Client mode finished and returned to caller.")