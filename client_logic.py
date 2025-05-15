# client_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.2 (Integrated global logger)
Handles client-side game logic, connection to server, and LAN discovery.
"""
import pygame
import socket
import time
import traceback
import os # For os.path and os.makedirs
import importlib # For importlib.invalidate_caches()
from typing import Optional # Added import for Optional

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL CLIENT_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
# --- End Logger ---

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import set_network_game_state
from enemy import Enemy # For print_limiter access if needed, or for type hinting
from game_ui import draw_platformer_scene_on_surface, draw_download_dialog # For drawing client's view
from game_setup import initialize_game_elements # To re-init after map download

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

        # Map download state
        self.server_selected_map_name: Optional[str] = None
        self.map_download_status: str = "unknown" # "unknown", "checking", "missing", "downloading", "present", "error"
        self.map_download_progress: float = 0.0 # 0.0 to 100.0
        self.map_total_size_bytes: int = 0
        self.map_received_bytes: int = 0
        self.map_file_buffer: bytes = b""


def find_server_on_lan(screen: pygame.Surface, fonts: dict,
                       clock_obj: pygame.time.Clock, client_state_obj: ClientState): # Changed clock to clock_obj
    """
    Searches for a game server on the LAN by listening for UDP broadcasts.
    Displays a "Searching..." message on the screen.
    Returns (found_server_ip, found_server_port) or (None, None) if not found or cancelled.
    """
    debug("Client (find_server_on_lan): Starting LAN server search.")
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
        debug(f"Client (find_server_on_lan): UDP listen socket bound to port {client_state_obj.discovery_port_udp}.")
    except socket.error as e_socket:
        error(f"Client Error: Failed to bind UDP listen socket on port {client_state_obj.discovery_port_udp}: {e_socket}")
        screen.fill(C.BLACK)
        err_msg = f"Error: Cannot listen on UDP port {client_state_obj.discovery_port_udp}."
        if fonts.get("small"):
            err_surf = fonts["small"].render(err_msg, True, C.RED)
            screen.blit(err_surf, err_surf.get_rect(center=(current_width//2, current_height // 2)))
        pygame.display.flip(); time.sleep(4)
        return None, None

    start_search_time = time.time()
    client_local_ip = get_local_ip()
    debug(f"Client (find_server_on_lan): Searching for LAN servers (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.")

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
                 debug("Client (find_server_on_lan): LAN server search cancelled by user.")
                 if listen_socket: listen_socket.close()
                 return None, None # Exit search and return to menu
        if not client_state_obj.app_running: break

        # Update "Searching..." display
        screen.fill(C.BLACK)
        screen.blit(search_text_surf, search_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip()
        clock_obj.tick(10) # Low FPS during search # Used clock_obj here

        raw_udp_data, decoded_udp_message = None, None
        try:
            raw_udp_data, sender_address = listen_socket.recvfrom(client_state_obj.buffer_size)
            # debug(f"Client (find_server_on_lan): Received UDP data from {sender_address}: {raw_udp_data[:60]}...") # DEBUG - noisy
            decoded_messages_list, _ = decode_data_stream(raw_udp_data)
            if not decoded_messages_list: continue

            decoded_udp_message = decoded_messages_list[0]
            # debug(f"Client (find_server_on_lan): Decoded UDP message: {decoded_udp_message}")
            if (isinstance(decoded_udp_message, dict) and
                decoded_udp_message.get("service") == client_state_obj.service_name and
                isinstance(decoded_udp_message.get("tcp_ip"), str) and
                isinstance(decoded_udp_message.get("tcp_port"), int)):

                server_ip = decoded_udp_message["tcp_ip"]
                server_port = decoded_udp_message["tcp_port"]
                info(f"Client (find_server_on_lan): Found server '{client_state_obj.service_name}' at {server_ip}:{server_port}")
                found_server_ip, found_server_port = server_ip, server_port
        except socket.timeout:
            continue
        except Exception as e_udp:
            error(f"Client: Error processing received UDP broadcast: {e_udp}", exc_info=True)

    if listen_socket: listen_socket.close()

    if not found_server_ip and client_state_obj.app_running:
        info(f"Client (find_server_on_lan): No server found for '{client_state_obj.service_name}' after timeout.")
        screen.fill(C.BLACK)
        if fonts.get("large"):
            fail_surf = fonts["large"].render("Server Not Found!", True, C.RED)
            screen.blit(fail_surf, fail_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip(); time.sleep(3)
    elif not client_state_obj.app_running:
        info("Client (find_server_on_lan): LAN server search aborted because application is quitting.")

    return found_server_ip, found_server_port


def run_client_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                    fonts: dict, game_elements_ref: dict,
                    client_state_obj: ClientState, target_ip_port_str: Optional[str] = None):
    """
    Main function to run the game in client mode.
    Connects to a server (either specified or found via LAN) and synchronizes game state.
    """
    info("Client (run_client_mode): Entering client mode.")
    client_state_obj.app_running = True
    current_width, current_height = screen.get_size()

    server_ip_to_connect, server_port_to_connect = None, C.SERVER_PORT_TCP

    if target_ip_port_str:
        info(f"Client (run_client_mode): Direct IP specified: {target_ip_port_str}")
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1:
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError:
                warning(f"Client Warning: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else:
        info("Client (run_client_mode): No direct IP, attempting LAN discovery.")
        server_ip_to_connect, found_server_port = find_server_on_lan(screen, fonts, clock, client_state_obj)
        if found_server_port: server_port_to_connect = found_server_port

    if not server_ip_to_connect:
        info("Client (run_client_mode): Exiting client mode (no server target).")
        return
    if not client_state_obj.app_running:
        info("Client (run_client_mode): Exiting client mode (application closed).")
        return

    if client_state_obj.client_tcp_socket:
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    connection_succeeded, connection_error_msg = False, "Unknown Connection Error"
    try:
        info(f"Client (run_client_mode): Attempting to connect to server at {server_ip_to_connect}:{server_port_to_connect}...")
        pygame.display.set_caption(f"Platformer - Connecting to {server_ip_to_connect}...")
        draw_download_dialog(screen, fonts, "Connecting to server...", f"{server_ip_to_connect}:{server_port_to_connect}", 0)


        client_state_obj.client_tcp_socket.settimeout(10.0)
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        client_state_obj.client_tcp_socket.settimeout(0.05) # Short timeout for non-blocking recv
        info("Client (run_client_mode): TCP Connection to server successful!")
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e_sock: connection_error_msg = f"Connection Error ({e_sock.strerror if hasattr(e_sock, 'strerror') else e_sock})"
    except Exception as e_conn: connection_error_msg = f"Unexpected Connection Error: {e_conn}"

    if not connection_succeeded:
        error(f"Client (run_client_mode): Failed to connect to server: {connection_error_msg}")
        draw_download_dialog(screen, fonts, "Connection Failed", connection_error_msg, -1) # -1 for error indication
        time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return

    # --- Map Synchronization Phase ---
    client_state_obj.map_download_status = "waiting_map_info"
    client_state_obj.server_state_buffer = b"" # Clear buffer for fresh messages

    map_sync_phase_active = True
    while map_sync_phase_active and client_state_obj.app_running:
        current_width, current_height = screen.get_size() # Handle resize during this phase
        for event in pygame.event.get():
            if event.type == pygame.QUIT: client_state_obj.app_running = False; map_sync_phase_active = False; break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width, current_height = max(320,event.w), max(240,event.h)
                    screen = pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                 client_state_obj.app_running = False; map_sync_phase_active = False; break
        if not client_state_obj.app_running: break

        dialog_title = "Synchronizing"
        dialog_message = "Waiting for map information from server..."
        dialog_progress = -1 # Indicates waiting, not progress value

        if client_state_obj.map_download_status == "checking":
            dialog_message = f"Checking for map: {client_state_obj.server_selected_map_name}..."
        elif client_state_obj.map_download_status == "missing":
            dialog_message = f"Map '{client_state_obj.server_selected_map_name}' missing. Requesting download..."
        elif client_state_obj.map_download_status == "downloading":
            dialog_title = f"Downloading Map: {client_state_obj.server_selected_map_name}"
            dialog_message = f"Received {client_state_obj.map_received_bytes / 1024:.1f} / {client_state_obj.map_total_size_bytes / 1024:.1f} KB"
            dialog_progress = client_state_obj.map_download_progress
        elif client_state_obj.map_download_status == "error":
            dialog_title = "Map Download Error"
            dialog_message = f"Failed to download map: {client_state_obj.server_selected_map_name}"
            dialog_progress = -1 # Error indication

        draw_download_dialog(screen, fonts, dialog_title, dialog_message, dialog_progress)

        try:
            server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size)
            if not server_data_chunk:
                info("Client: Server disconnected during map sync."); map_sync_phase_active = False; break
            client_state_obj.server_state_buffer += server_data_chunk

            decoded_messages, client_state_obj.server_state_buffer = decode_data_stream(client_state_obj.server_state_buffer)

            for msg in decoded_messages:
                command = msg.get("command")
                if command == "set_map":
                    client_state_obj.server_selected_map_name = msg.get("name")
                    info(f"Client: Received map name from server: {client_state_obj.server_selected_map_name}")
                    client_state_obj.map_download_status = "checking"

                    map_file_path = os.path.join(C.MAPS_DIR, client_state_obj.server_selected_map_name + ".py")
                    if os.path.exists(map_file_path):
                        info(f"Client: Map '{client_state_obj.server_selected_map_name}' found locally.")
                        client_state_obj.map_download_status = "present"
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command": "report_map_status", "name": client_state_obj.server_selected_map_name, "status": "present"}))
                        map_sync_phase_active = False # Ready to start game
                    else:
                        info(f"Client: Map '{client_state_obj.server_selected_map_name}' MISSING. Requesting file.")
                        client_state_obj.map_download_status = "missing" # UI will show this briefly
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command": "report_map_status", "name": client_state_obj.server_selected_map_name, "status": "missing"}))
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command": "request_map_file", "name": client_state_obj.server_selected_map_name}))
                        client_state_obj.map_download_status = "downloading" # Switch to downloading state
                        client_state_obj.map_received_bytes = 0
                        client_state_obj.map_total_size_bytes = 0
                        client_state_obj.map_file_buffer = b""

                elif command == "map_file_info" and client_state_obj.map_download_status == "downloading":
                    client_state_obj.map_total_size_bytes = msg.get("size", 0)
                    debug(f"Client: Expecting map file of size {client_state_obj.map_total_size_bytes} bytes.")

                elif command == "map_data_chunk" and client_state_obj.map_download_status == "downloading":
                    chunk_data_str = msg.get("data", "")
                    chunk_data_bytes = chunk_data_str.encode('utf-8') # Server sends as string, client decodes to bytes
                    client_state_obj.map_file_buffer += chunk_data_bytes
                    client_state_obj.map_received_bytes = len(client_state_obj.map_file_buffer)
                    if client_state_obj.map_total_size_bytes > 0:
                        client_state_obj.map_download_progress = (client_state_obj.map_received_bytes / client_state_obj.map_total_size_bytes) * 100
                    client_state_obj.client_tcp_socket.sendall(encode_data({"command": "report_download_progress", "progress": client_state_obj.map_download_progress}))

                elif command == "map_transfer_end" and client_state_obj.map_download_status == "downloading":
                    if client_state_obj.map_received_bytes == client_state_obj.map_total_size_bytes:
                        map_file_to_save = os.path.join(C.MAPS_DIR, client_state_obj.server_selected_map_name + ".py")
                        try:
                            # Ensure maps directory exists
                            if not os.path.exists(C.MAPS_DIR): os.makedirs(C.MAPS_DIR)
                            with open(map_file_to_save, "wb") as f: # write bytes
                                f.write(client_state_obj.map_file_buffer)
                            info(f"Client: Map '{client_state_obj.server_selected_map_name}' downloaded and saved to '{map_file_to_save}'.")
                            client_state_obj.map_download_status = "present"
                            importlib.invalidate_caches() # Important for re-importing
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command": "report_map_status", "name": client_state_obj.server_selected_map_name, "status": "present"})) # Inform server map is now present
                            map_sync_phase_active = False # Ready to start game
                        except Exception as e_save:
                            error(f"Client Error: Failed to save downloaded map '{map_file_to_save}': {e_save}")
                            client_state_obj.map_download_status = "error"
                            # Optionally send error status to server
                    else:
                        error(f"Client Error: Map download size mismatch. Expected {client_state_obj.map_total_size_bytes}, got {client_state_obj.map_received_bytes}.")
                        client_state_obj.map_download_status = "error"

                elif command == "start_game_now": # Server signals game can start
                    if client_state_obj.map_download_status == "present":
                        info(f"Client: Received start_game_now. Map is present. Proceeding.")
                        map_sync_phase_active = False
                    else:
                        info(f"Client: Received start_game_now, but map status is '{client_state_obj.map_download_status}'. Waiting.")


        except socket.timeout: pass # No data received, continue loop
        except socket.error as e_sock_map:
            error(f"Client: Socket error during map sync: {e_sock_map}. Server might have disconnected.")
            map_sync_phase_active = False; break
        except Exception as e_map_sync:
            error(f"Client: Error processing data during map sync: {e_map_sync}", exc_info=True)
            map_sync_phase_active = False; break

        clock.tick(C.FPS) # Keep UI responsive

    if not client_state_obj.app_running or client_state_obj.map_download_status != "present":
        info(f"Client: Exiting client mode (app closed or map not ready: {client_state_obj.map_download_status}).")
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket = None
        return

    # --- Re-initialize game elements with the correct map ---
    info(f"Client: Map '{client_state_obj.server_selected_map_name}' is present. Initializing game elements...")
    current_screen_width, current_screen_height = screen.get_size()
    updated_game_elements = initialize_game_elements(
        current_screen_width, current_screen_height,
        for_game_mode="join_ip", # Or "join_lan", doesn't matter much here for element creation
        existing_sprites_groups=game_elements_ref, # Pass existing groups to preserve instances
        map_module_name=client_state_obj.server_selected_map_name
    )
    if updated_game_elements is None:
        critical(f"Client CRITICAL: Failed to initialize game elements with map '{client_state_obj.server_selected_map_name}'.")
        # Show error on screen
        draw_download_dialog(screen, fonts, "Error", f"Failed to load map: {client_state_obj.server_selected_map_name}", -1)
        time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket = None
        return

    game_elements_ref.update(updated_game_elements)
    # Ensure camera is updated if it was re-created
    if game_elements_ref.get("camera"):
        cam_instance = game_elements_ref["camera"]
        if hasattr(cam_instance, "set_screen_dimensions"):
            cam_instance.set_screen_dimensions(current_screen_width, current_screen_height)

    # --- Main Game Loop (starts after map sync) ---
    pygame.display.set_caption("Platformer - CLIENT (You are P2: WASD+VB | Self-Harm: H | Heal: G | Reset: Enter)")

    p2_controlled_by_client = game_elements_ref.get("player2")
    p1_remote_on_client = game_elements_ref.get("player1")
    debug(f"Client (run_client_mode): P1 (remote) instance: {p1_remote_on_client}, P2 (local) instance: {p2_controlled_by_client}")
    if p1_remote_on_client: debug(f"Client: P1 Valid: {p1_remote_on_client._valid_init}, P1 Pos: {p1_remote_on_client.pos if hasattr(p1_remote_on_client, 'pos') else 'N/A'}")
    if p2_controlled_by_client: debug(f"Client: P2 Valid: {p2_controlled_by_client._valid_init}, P2 Pos: {p2_controlled_by_client.pos if hasattr(p2_controlled_by_client, 'pos') else 'N/A'}")


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
                    # debug(f"Client: Sending input to server: {client_input_payload}") # Noisy
                    client_state_obj.client_tcp_socket.sendall(encoded_client_payload)
                except socket.error as e_send:
                    error(f"Client: Send to server failed: {e_send}. Server might have disconnected.")
                    client_game_active = False; break

        if client_state_obj.client_tcp_socket:
            try:
                server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size * 2)
                if not server_data_chunk:
                    info("Client: Server disconnected (received empty data from recv).")
                    client_game_active = False; break

                # debug(f"Client: Received chunk from server: {server_data_chunk[:100]}...") # Noisy
                client_state_obj.server_state_buffer += server_data_chunk
                decoded_server_states, client_state_obj.server_state_buffer = \
                    decode_data_stream(client_state_obj.server_state_buffer)

                if decoded_server_states:
                    client_state_obj.last_received_server_state = decoded_server_states[-1]
                    # debug(f"Client: Received new game state. P1 pos: {client_state_obj.last_received_server_state.get('p1', {}).get('pos')}, P2 pos: {client_state_obj.last_received_server_state.get('p2', {}).get('pos')}")
                    set_network_game_state(client_state_obj.last_received_server_state, game_elements_ref, client_player_id=2)
                    # p1_after_update = game_elements_ref.get("player1")
                    # p2_after_update = game_elements_ref.get("player2")
                    # if p1_after_update: debug(f"Client: P1 after state update. Pos: {p1_after_update.pos if hasattr(p1_after_update, 'pos') else 'N/A'}, Valid: {p1_after_update._valid_init}, Alive: {p1_after_update.alive() if hasattr(p1_after_update, 'alive') else 'N/A'}")
                    # if p2_after_update: debug(f"Client: P2 after state update. Pos: {p2_after_update.pos if hasattr(p2_after_update, 'pos') else 'N/A'}, Valid: {p2_after_update._valid_init}, Alive: {p2_after_update.alive() if hasattr(p2_after_update, 'alive') else 'N/A'}")


            except socket.timeout: pass
            except socket.error as e_recv:
                error(f"Client: Recv error from server: {e_recv}. Server might have disconnected.")
                client_game_active = False; break
            except Exception as e_process_server:
                error(f"Client: Error processing data from server: {e_process_server}", exc_info=True)
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
                # Use global logger; Enemy.print_limiter will be handled when enemy.py is updated
                debug(f"Client: Visually removing enemy {enemy_client.enemy_id} as death anim finished.")
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
        except Exception as e_draw:
            error(f"Client draw error: {e_draw}", exc_info=True)
            client_game_active=False; break
        pygame.display.flip()

    info("Client: Exiting active game loop.")
    if client_state_obj.client_tcp_socket:
        info("Client: Closing TCP socket to server.")
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    info("Client: Client mode finished and returned to caller.")