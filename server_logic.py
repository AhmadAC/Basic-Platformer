# server_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.6 (Pause action returns to main menu, client can also signal pause)
Handles server-side game logic, connection management, and broadcasting.
"""
import os
import pygame
import socket
import threading
import time
import traceback
from typing import Optional, Dict, Any, List # Added List

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy # For type hinting and instanceof if needed
import game_ui # For drawing status/dialogs on server screen
from items import Chest # For type hinting
from statue import Statue # Import Statue for server-side logic
import config as game_config # For P1 key map if server is also P1

# Import logger
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL SERVER_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Defined error for fallback
    def critical(msg): print(f"CRITICAL: {msg}")


client_lock = threading.Lock() # Global lock for accessing shared client state

class ServerState:
    def __init__(self):
        self.client_connection: Optional[socket.socket] = None
        self.client_address: Optional[Any] = None # Stores tuple (ip, port)
        self.client_input_buffer: Dict[str, Any] = {} # Store last decoded input from client
        self.app_running = True # Controls main loop and threads
        self.server_tcp_socket: Optional[socket.socket] = None # For listening for client
        self.server_udp_socket: Optional[socket.socket] = None # For LAN discovery broadcast
        self.broadcast_thread: Optional[threading.Thread] = None
        self.client_handler_thread: Optional[threading.Thread] = None
        
        # Configuration from constants
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)
        self.broadcast_interval_s = getattr(C, "BROADCAST_INTERVAL_S", 1.0)
        
        self.current_map_name: Optional[str] = None # Set by game_setup before run_server_mode
        self.client_map_status: str = "unknown" # e.g., "unknown", "waiting_client_report", "missing", "downloading_ack", "present", "disconnected"
        self.client_download_progress: float = 0.0
        self.game_start_signaled_to_client: bool = False # True after server sends "start_game_now"


def broadcast_presence_thread(server_state_obj: ServerState):
    """
    Thread function that periodically broadcasts the server's presence on the LAN.
    """
    current_lan_ip = get_local_ip()
    broadcast_message_dict = {
        "service": server_state_obj.service_name,
        "tcp_ip": current_lan_ip,
        "tcp_port": server_state_obj.server_port_tcp
    }
    broadcast_message_bytes = encode_data(broadcast_message_dict)
    if not broadcast_message_bytes:
        error("Server Error: Could not encode broadcast message for presence.")
        return

    try:
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5) # Non-blocking for periodic send
    except socket.error as e:
        error(f"Server Error: Failed to create UDP broadcast socket: {e}")
        server_state_obj.server_udp_socket = None
        return

    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    debug(f"Server (broadcast_presence_thread): Broadcasting presence: {broadcast_message_dict} to {broadcast_address} (LAN IP: {current_lan_ip})")

    while server_state_obj.app_running:
        try:
            if server_state_obj.server_udp_socket: # Check if socket is still valid
                server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error: pass # Ignore send errors if socket becomes invalid temporarily
        except Exception as e: warning(f"Server Warning: Unexpected error during broadcast send: {e}")
        
        # Sleep in small chunks to allow faster thread exit if app_running becomes False
        for _ in range(int(server_state_obj.broadcast_interval_s * 10)): # e.g., 1.0s -> 10 * 0.1s
            if not server_state_obj.app_running: break
            time.sleep(0.1)
            
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close()
        server_state_obj.server_udp_socket = None
    debug("Server (broadcast_presence_thread): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr, server_state_obj: ServerState):
    """
    Thread function to handle communication with a single connected client.
    Manages map synchronization and receives client input.
    """
    debug(f"Server (handle_client_connection_thread): Client connected from {addr}. Handler thread started.")
    conn.settimeout(1.0) # Use a timeout for recv to keep thread responsive
    partial_data_from_client = b""

    # Initial map synchronization with the client
    if server_state_obj.current_map_name:
        try:
            conn.sendall(encode_data({"command": "set_map", "name": server_state_obj.current_map_name}))
            debug(f"Server Handler ({addr}): Sent initial map info: {server_state_obj.current_map_name}")
        except socket.error as e_send_map_info:
            debug(f"Server Handler ({addr}): Error sending initial map info: {e_send_map_info}. Client may have disconnected early.")
            # Do not return immediately, client might still send data or close cleanly.
    else:
        critical(f"Server Handler ({addr}): CRITICAL - server_state_obj.current_map_name is None. Cannot send initial map info.")
        # This is a fatal state for the server, consider how to handle (e.g., disconnect client).

    while server_state_obj.app_running:
        with client_lock: # Ensure this is still the active connection being handled
            if server_state_obj.client_connection is not conn: 
                debug(f"Server Handler ({addr}): Stale connection (new client likely connected). Exiting thread for old connection.")
                break
        try:
            chunk = conn.recv(server_state_obj.buffer_size)
            if not chunk: # Client disconnected gracefully (sent empty data)
                debug(f"Server Handler ({addr}): Client disconnected (received empty data).")
                break
            
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            
            for msg in decoded_inputs:
                command = msg.get("command")
                if command == "report_map_status":
                    map_name_client_report = msg.get("name")
                    status_client_report = msg.get("status")
                    debug(f"Server Handler ({addr}): Client map status for '{map_name_client_report}': {status_client_report}")
                    with client_lock: # Update shared server state
                        server_state_obj.client_map_status = status_client_report
                        if status_client_report == "present":
                             server_state_obj.client_download_progress = 100.0
                             # Signal game start only if not already signaled (prevents multiple start signals)
                             if not server_state_obj.game_start_signaled_to_client:
                                conn.sendall(encode_data({"command": "start_game_now"}))
                                server_state_obj.game_start_signaled_to_client = True
                                debug(f"Server Handler ({addr}): Client has map. Sent start_game_now command.")
                elif command == "request_map_file":
                    map_name_req = msg.get("name")
                    debug(f"Server Handler ({addr}): Client requested map file: '{map_name_req}'")
                    map_file_path = os.path.join(C.MAPS_DIR, map_name_req + ".py") # MAPS_DIR should be absolute
                    if os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding="utf-8") as f_map: map_content_str = f_map.read()
                        map_content_bytes_utf8 = map_content_str.encode('utf-8')
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req, "size": len(map_content_bytes_utf8)}))
                        
                        offset = 0
                        while offset < len(map_content_bytes_utf8):
                            chunk_to_send_bytes_data = map_content_bytes_utf8[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            # Client expects the "data" field to be a string, so decode the chunk back to string (UTF-8 assumed)
                            conn.sendall(encode_data({"command": "map_data_chunk", 
                                                     "data": chunk_to_send_bytes_data.decode('utf-8', 'replace'), # Send as string
                                                     "seq": offset}))
                            offset += len(chunk_to_send_bytes_data)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                        debug(f"Server Handler ({addr}): Sent map file '{map_name_req}' to client.")
                    else:
                        error(f"Server Error: Client requested map '{map_name_req}' but it was not found at '{map_file_path}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req, "reason": "not_found_on_server"}))
                
                elif command == "report_download_progress":
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0)
                
                elif "input" in msg: # Client's game input
                    with client_lock:
                        if server_state_obj.client_connection is conn: # Ensure this is still the active connection
                            server_state_obj.client_input_buffer = msg["input"] # Overwrite with the latest full input state from client
        
        except socket.timeout:
            continue # No data received within timeout, loop again to check app_running and recv
        except socket.error as e_sock:
            if server_state_obj.app_running: # Only log if server is meant to be running
                debug(f"Server Handler ({addr}): Socket error: {e_sock}. Assuming client disconnected.")
            break # Exit loop on socket error (likely client closed connection)
        except Exception as e_unexpected:
            if server_state_obj.app_running:
                error(f"Server Handler ({addr}): Unexpected error in client handler loop: {e_unexpected}", exc_info=True)
            break # Exit loop on other critical errors

    # --- Cleanup for this specific client connection ---
    with client_lock: # Ensure thread-safe modification of shared server state
        if server_state_obj.client_connection is conn: # If this handler was for the currently active connection
            debug(f"Server Handler ({addr}): Closing active connection from handler thread. Client map status was: {server_state_obj.client_map_status}")
            server_state_obj.client_connection = None # No active client
            server_state_obj.client_input_buffer = {"disconnect": True} # Signal disconnect to main server loop if it checks
            server_state_obj.client_map_status = "disconnected" # Update status for UI
            server_state_obj.game_start_signaled_to_client = False # Reset for next potential client
    
    # Attempt to gracefully close the socket
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass # Ignore errors if already closed or problematic
    try: conn.close()
    except: pass
    
    debug(f"Server: Client handler thread for {addr} finished.")


def run_server_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                    fonts: dict, game_elements_ref: dict, server_state_obj: ServerState):
    """
    Main function to run the game in server (host) mode.
    Handles waiting for a client, map synchronization, game loop, and network communication.
    """
    debug("ServerLogic: Entering run_server_mode.")
    pygame.display.set_caption(f"Platformer - HOST (P1 Controls: {game_config.CURRENT_P1_INPUT_DEVICE} | P2: Client | Reset: P1MappedResetKey/Q)")
    server_state_obj.app_running = True # Ensure app_running is true for this mode
    current_width, current_height = screen.get_size()

    if server_state_obj.current_map_name is None: # This should be set by game_setup
        critical("CRITICAL SERVER: server_state_obj.current_map_name is None at start of run_server_mode. Cannot host.")
        return

    # Start broadcasting server presence if not already running
    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("ServerLogic: Starting broadcast presence thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()

    # Setup TCP listening socket for client connection
    if server_state_obj.server_tcp_socket: # Close if somehow already exists (e.g., from a previous failed run)
        debug("ServerLogic: Closing existing TCP listening socket before creating a new one.")
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1) # Listen for one client connection
        server_state_obj.server_tcp_socket.settimeout(1.0) # Non-blocking accept for UI responsiveness
        debug(f"ServerLogic: TCP socket listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e_bind:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e_bind}")
        # Attempt to stop broadcast thread gracefully
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
            temp_app_running_for_shutdown = server_state_obj.app_running
            server_state_obj.app_running = False # Signal thread to stop
            server_state_obj.broadcast_thread.join(timeout=0.5) # Wait briefly
            server_state_obj.app_running = temp_app_running_for_shutdown # Restore flag
        return # Cannot proceed if socket fails

    debug("ServerLogic: Waiting for Player 2 to connect and synchronize map...")
    # Reset client-specific state for a new session
    with client_lock:
        server_state_obj.client_map_status = "unknown"
        server_state_obj.client_download_progress = 0.0
        server_state_obj.game_start_signaled_to_client = False
        server_state_obj.client_connection = None # Ensure no old connection lingers
        server_state_obj.client_address = None

    client_sync_wait_active = True
    while client_sync_wait_active and server_state_obj.app_running:
        current_width, current_height = screen.get_size() # For UI updates
        for event in pygame.event.get():
            if event.type == pygame.QUIT: server_state_obj.app_running = False; client_sync_wait_active = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width, current_height = max(320,event.w), max(240,event.h)
                screen = pygame.display.set_mode((current_width, current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: # Allow server to cancel waiting
                server_state_obj.app_running = False; client_sync_wait_active = False; break
        if not server_state_obj.app_running: break

        # Accept new client connection if none is active
        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock: # Safely update shared state
                    server_state_obj.client_connection = temp_conn
                    server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {} # Clear old input
                    server_state_obj.client_map_status = "waiting_client_report" # Initial status for new client
                    server_state_obj.game_start_signaled_to_client = False # Reset flag
                debug(f"ServerLogic: Accepted new client connection from {temp_addr}")

                # Start a new handler thread for this client
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    server_state_obj.client_handler_thread.join(timeout=0.1) # Wait for old one to finish if any
                server_state_obj.client_handler_thread = threading.Thread(
                    target=handle_client_connection_thread, args=(temp_conn, temp_addr, server_state_obj), daemon=True
                )
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass # No connection attempt, continue waiting loop
            except Exception as e_accept: error(f"ServerLogic: Error accepting client connection: {e_accept}", exc_info=True)
        
        # Update UI with current sync status
        dialog_title_sync = "Server Hosting"; dialog_msg_sync = "Waiting for Player 2..."; dialog_prog_sync = -1.0
        with client_lock: # Read shared state safely for UI
            if server_state_obj.client_connection: # If a client is connected
                client_ip_str = server_state_obj.client_address[0] if server_state_obj.client_address else 'Unknown IP'
                if server_state_obj.client_map_status == "waiting_client_report": dialog_msg_sync = f"P2 ({client_ip_str}) connected. Syncing map..."
                elif server_state_obj.client_map_status == "missing": dialog_msg_sync = f"P2 missing map '{server_state_obj.current_map_name}'. Sending..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "downloading_ack": dialog_msg_sync = f"P2 downloading map '{server_state_obj.current_map_name}' ({server_state_obj.client_download_progress:.0f}%)..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "present":
                    dialog_msg_sync = f"P2 has map '{server_state_obj.current_map_name}'. Ready to start."; dialog_prog_sync = 100.0
                    # Game starts when server has sent "start_game_now" AND client confirmed "present"
                    if server_state_obj.game_start_signaled_to_client: 
                        client_sync_wait_active = False # Exit sync loop, game can begin
                elif server_state_obj.client_map_status == "disconnected":
                    dialog_msg_sync = "P2 disconnected. Waiting for new connection...";
                    server_state_obj.client_connection = None # Allow new connections by setting to None
        
        game_ui.draw_download_dialog(screen, fonts, dialog_title_sync, dialog_msg_sync, dialog_prog_sync)
        clock.tick(10) # Keep UI responsive during this waiting/sync phase

    # --- Check conditions for proceeding to game loop ---
    if not server_state_obj.app_running or server_state_obj.client_connection is None or server_state_obj.client_map_status != "present":
        debug(f"ServerLogic: Exiting client sync wait loop. Conditions not met for game start. "
              f"app_running: {server_state_obj.app_running}, client_conn active: {server_state_obj.client_connection is not None}, "
              f"client_map_status: {server_state_obj.client_map_status}")
        server_state_obj.app_running = False # Ensure broadcast thread stops if it hasn't
        # Cleanup threads and sockets before returning
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return # Return to main menu

    # --- Main Server Game Loop ---
    debug(f"ServerLogic: Client {server_state_obj.client_address if server_state_obj.client_address else 'Unknown'} connected, map synced. Starting game loop...")
    p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2") # Get player instances
    if p1: debug(f"ServerLogic: P1 instance: {p1}, Valid: {p1._valid_init if p1 else 'N/A'}")
    if p2: debug(f"ServerLogic: P2 instance: {p2}, Valid: {p2._valid_init if p2 else 'N/A'}") # P2 is shell for client
    
    server_game_active = True
    p1_action_events: Dict[str, bool] = {} # Stores events like "jump":True for one frame for P1

    while server_game_active and server_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks_server = pygame.time.get_ticks()
        pygame_events = pygame.event.get(); keys_pressed_p1 = pygame.key.get_pressed() # For host's P1
        
        # Reset flags each frame
        host_requested_reset = False
        p2_requested_reset_from_client = False
        client_requested_pause_from_input = False
        client_disconnected_signal = False

        # Handle global events (quit, resize, debug keys for P1)
        for event in pygame_events:
            if event.type == pygame.QUIT: server_game_active = False; server_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width,current_height = max(320,event.w),max(240,event.h)
                screen=pygame.display.set_mode((current_width,current_height),pygame.RESIZABLE|pygame.DOUBLEBUF)
                if game_elements_ref.get("camera"): game_elements_ref["camera"].set_screen_dimensions(current_width, current_height)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: server_game_active = False # Server Esc exits current game mode
                if event.key == pygame.K_q: # Dev reset key for host
                    host_requested_reset = True; info("Server: Dev 'Q' key reset triggered by host.")
                # P1 specific debug keys (self-harm/heal for host player)
                if p1 and p1._valid_init:
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'): p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'): p1.heal_to_full()
        
        if not server_state_obj.app_running or not server_game_active: break # Exit if app closed or mode ended

        # Process P1 input (Host player)
        # P1 input processing happens even if P1 is dead, to catch reset/pause events.
        if p1 and p1._valid_init and hasattr(p1, 'process_input'):
            p1_action_events = p1.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed_p1)
            if p1_action_events.get("pause"): # P1 pressed pause
                info("Server: P1 (host) pause action detected. Returning to main menu.")
                server_game_active = False 
            if p1_action_events.get("reset"): # P1 pressed reset
                host_requested_reset = True
                info("Server: P1 (host) reset action detected.")
        
        if not server_game_active: break # Exit if P1 paused

        # Process client (P2) input from buffer (handled by client_handler_thread)
        p2_network_input_for_frame: Optional[Dict[str, Any]] = None
        with client_lock: # Safely access shared client input buffer
            if server_state_obj.client_input_buffer:
                p2_network_input_for_frame = server_state_obj.client_input_buffer.copy() # Get the latest full input state
                server_state_obj.client_input_buffer.clear() # Clear buffer after processing for this frame

                if p2_network_input_for_frame.get("disconnect"): client_disconnected_signal = True
                if p2_network_input_for_frame.get("reset", False) or p2_network_input_for_frame.get("action_reset_global", False):
                    p2_requested_reset_from_client = True
                    info(f"Server: Client (P2) reset action detected (reset: {p2_network_input_for_frame.get('reset', False)}, global_reset: {p2_network_input_for_frame.get('action_reset_global', False)}).")
                if p2_network_input_for_frame.get("pause", False): # Check for 'pause' event from client
                    client_requested_pause_from_input = True
                
                # P2 self-harm/heal based on client's input buffer
                if p2 and p2._valid_init: # P2 is the server's representation of the client player
                    if p2_network_input_for_frame.get("action_self_harm", False) and hasattr(p2, 'self_inflict_damage'):
                        p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    elif p2_network_input_for_frame.get("action_heal", False) and hasattr(p2, 'heal_to_full'):
                        p2.heal_to_full()
        
        if client_disconnected_signal: # If client handler thread signaled disconnect
            debug("ServerLogic: Client disconnected signal received in main game loop.")
            server_game_active = False; server_state_obj.client_connection = None; server_state_obj.client_map_status = "unknown"
            break
        if client_requested_pause_from_input: # If client (P2) sent a pause event
            info("Server: Client (P2) requested pause via network input. Returning to main menu.")
            server_game_active = False
        if not server_game_active: break # Exit if client paused

        # Apply P2's network input to P2's character on the server
        if p2 and p2._valid_init and p2_network_input_for_frame and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input_for_frame)
        
        # --- Game Reset Logic ---
        # Reset if host requests it, OR if client requests it AND P1 is already game-over.
        is_p1_game_over_for_reset_check = (p1 and p1._valid_init and p1.is_dead and \
                                          (not p1.alive() or (hasattr(p1, 'death_animation_finished') and p1.death_animation_finished))) \
                                          or (not p1 or not p1._valid_init) # P1 doesn't exist or invalid
        
        if host_requested_reset or (p2_requested_reset_from_client and is_p1_game_over_for_reset_check):
            info("ServerLogic: Game state reset triggered by host, or by client when P1 is game-over.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            # Ensure players are re-added to sprite groups if they were killed then reset
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p2)

        # --- Update Game Entities (Players, Enemies, Statues, Projectiles, etc.) ---
        # Update P1 (Host player) based on local input
        if p1 and p1._valid_init:
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref # Ensure projectiles can access game elements
            p1.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), 
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()), 
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), 
                      other_players_for_p1_update, game_elements_ref.get("enemy_list", []))
        
        # Update P2 (Client's character on server) based on its (network-synced) state
        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), 
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()), 
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), 
                      other_players_for_p2_update, game_elements_ref.get("enemy_list", []))
        
        # Update Enemies (AI targets active players)
        active_players_for_enemy_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_instance in list(game_elements_ref.get("enemy_list", [])): # Iterate copy if modifying list
            if enemy_instance._valid_init:
                # Petrified enemies generally don't update their AI/physics in the same way
                if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified: 
                    # Still update status effects for petrified (e.g., for smash timer)
                    if hasattr(enemy_instance, 'update_enemy_status_effects'): # Assuming this method exists
                         enemy_instance.update_enemy_status_effects(now_ticks_server, game_elements_ref.get("platform_sprites"))
                    enemy_instance.animate() # Keep animating petrified/smashed state
                    if enemy_instance.is_dead and enemy_instance.death_animation_finished and enemy_instance.alive():
                        enemy_instance.kill()
                    continue # Skip full AI/physics update for petrified

                enemy_instance.update(dt_sec, active_players_for_enemy_ai, 
                                      game_elements_ref.get("platform_sprites", pygame.sprite.Group()), 
                                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), 
                                      game_elements_ref.get("enemy_list", []))
                # Server authoritative removal of enemies if their death animation is finished
                if enemy_instance.is_dead and hasattr(enemy_instance, 'death_animation_finished') and \
                   enemy_instance.death_animation_finished and enemy_instance.alive():
                    # Using a print limiter for enemy class if available, or just debug
                    if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"server_killing_enemy_{enemy_instance.enemy_id}"): 
                        debug(f"Server: Auto-killing enemy {enemy_instance.enemy_id} as death animation finished.")
                    enemy_instance.kill()
        
        # Update Statues
        server_statues_list: List[Statue] = game_elements_ref.get("statue_objects", [])
        for statue_instance_server in server_statues_list:
            if hasattr(statue_instance_server, 'update'): 
                statue_instance_server.update(dt_sec) # Handles smash animation and self.kill()
            
        # --- Projectile Updates ---
        # Define which characters/objects projectiles can hit on the server
        hittable_targets_on_server = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_targets_on_server.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_targets_on_server.add(p2)
        
        for enemy_for_proj_target in game_elements_ref.get("enemy_list", []):
            if enemy_for_proj_target and enemy_for_proj_target.alive() and enemy_for_proj_target._valid_init and \
               not getattr(enemy_for_proj_target, 'is_petrified', False): # Projectiles don't hit petrified enemies
                hittable_targets_on_server.add(enemy_for_proj_target)
        
        for statue_for_proj_target in server_statues_list: # Add active statues to hittable group
            if statue_for_proj_target.alive() and hasattr(statue_for_proj_target, 'is_smashed') and \
               not statue_for_proj_target.is_smashed: # Can only hit non-smashed statues
                hittable_targets_on_server.add(statue_for_proj_target)

        # Ensure projectiles have access to game elements if needed (e.g., for spawning sub-projectiles)
        for proj_instance_server in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj_instance_server, 'game_elements_ref') and proj_instance_server.game_elements_ref is None:
                proj_instance_server.game_elements_ref = game_elements_ref
        
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(
            dt_sec, 
            game_elements_ref.get("platform_sprites", pygame.sprite.Group()), 
            hittable_targets_on_server # Pass the comprehensive list of hittable targets
        )
        
        # Update Collectibles (e.g., Chests)
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

        # Chest Interaction Logic (Server is authoritative)
        chest_instance_server_loop = game_elements_ref.get("current_chest")
        if isinstance(chest_instance_server_loop, Chest) and chest_instance_server_loop.alive() and \
           not chest_instance_server_loop.is_collected_flag_internal:
            player_who_interacted_with_chest_server = None
            # P1 interaction (host player)
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
               pygame.sprite.collide_rect(p1, chest_instance_server_loop) and p1_action_events.get("interact", False):
                player_who_interacted_with_chest_server = p1
            # P2 interaction (client player, based on network input processed earlier)
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
                 pygame.sprite.collide_rect(p2, chest_instance_server_loop) and \
                 p2_network_input_for_frame and p2_network_input_for_frame.get("interact_pressed_event", False): # Check event from P2's input
                player_who_interacted_with_chest_server = p2
            
            if player_who_interacted_with_chest_server:
                chest_instance_server_loop.collect(player_who_interacted_with_chest_server)

        # --- Camera Update (Server-side focus for local display) ---
        camera_instance_server_loop = game_elements_ref.get("camera")
        if camera_instance_server_loop:
            focus_target_server = None
            # Prioritize P1 if alive and not dead/petrified
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified', False): 
                focus_target_server = p1
            # Else, try P2 if alive and not dead/petrified (only if P1 doesn't meet criteria)
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified', False): 
                focus_target_server = p2
            # Fallbacks if both are dead/petrified or one is missing
            elif p1 and p1.alive() and p1._valid_init: focus_target_server = p1 
            elif p2 and p2.alive() and p2._valid_init: focus_target_server = p2 
            
            if focus_target_server: camera_instance_server_loop.update(focus_target_server)
            else: camera_instance_server_loop.static_update() # If no valid target

        # --- Send Game State to Client ---
        if server_state_obj.client_connection:
            net_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state_to_send = encode_data(net_state_to_send)
            if encoded_state_to_send:
                try:
                    server_state_obj.client_connection.sendall(encoded_state_to_send)
                except socket.error as e_send_state:
                    debug(f"ServerLogic: Send game state failed: {e_send_state}. Client likely disconnected."); 
                    server_game_active = False; server_state_obj.client_connection = None; break # End game on send fail
        
        # --- Draw Server's Local View ---
        try:
            # Check if client is still syncing (should ideally not happen if game loop started, but for safety)
            download_status_for_server_ui, download_progress_for_server_ui = None, None 
            with client_lock: # Access shared state for UI
                if server_state_obj.client_map_status in ["missing", "downloading_ack"]: 
                    download_status_for_server_ui = f"P2 Downloading: {server_state_obj.current_map_name}"
                    download_progress_for_server_ui = server_state_obj.client_download_progress
            
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_server, 
                                                     download_status_message=download_status_for_server_ui, 
                                                     download_progress_percent=download_progress_for_server_ui)
        except Exception as e_draw_scene: 
            error(f"ServerLogic: Error during draw_platformer_scene_on_surface: {e_draw_scene}", exc_info=True)
            server_game_active=False; break # Critical draw error, stop game
        
        pygame.display.flip() # Update the server's screen

    # --- End of Server Game Loop ---
    debug("ServerLogic: Exiting active game loop.")
    
    # --- Cleanup Client Connection (if still active) ---
    connection_to_close_on_exit = None
    with client_lock: # Ensure thread-safe access to client_connection
        if server_state_obj.client_connection:
            connection_to_close_on_exit = server_state_obj.client_connection
            server_state_obj.client_connection = None # Mark as no longer active for handler thread
    
    if connection_to_close_on_exit:
        debug("ServerLogic: Game mode exit cleanup - closing client connection.")
        try: connection_to_close_on_exit.shutdown(socket.SHUT_RDWR)
        except: pass # Ignore errors if already closed
        try: connection_to_close_on_exit.close()
        except: pass
        
    # Close TCP listening socket (if open)
    if server_state_obj.server_tcp_socket:
        debug("ServerLogic: Closing main TCP listening socket.")
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
        
    debug("ServerLogic: Server mode finished. Control returned to caller (main.py).")