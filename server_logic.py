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
from typing import Optional, Dict, Any # Added Dict, Any

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy
import game_ui
from items import Chest
from statue import Statue # Import Statue
import config as game_config # For P1 key map
# Import logger
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL SERVER_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")


client_lock = threading.Lock() # Global lock for accessing shared client state

class ServerState:
    def __init__(self):
        self.client_connection: Optional[socket.socket] = None
        self.client_address: Optional[Any] = None
        self.client_input_buffer: Dict[str, Any] = {} # Store last decoded input from client
        self.app_running = True
        self.server_tcp_socket: Optional[socket.socket] = None
        self.server_udp_socket: Optional[socket.socket] = None
        self.broadcast_thread: Optional[threading.Thread] = None
        self.client_handler_thread: Optional[threading.Thread] = None
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)
        self.broadcast_interval_s = getattr(C, "BROADCAST_INTERVAL_S", 1.0)
        self.current_map_name: Optional[str] = None # Set by game_setup before run_server_mode
        self.client_map_status: str = "unknown" # e.g., "unknown", "waiting_client_report", "missing", "downloading_ack", "present", "disconnected"
        self.client_download_progress: float = 0.0
        self.game_start_signaled_to_client: bool = False


def broadcast_presence_thread(server_state_obj: ServerState):
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
    debug(f"Server (handle_client_connection_thread): Client connected from {addr}. Handler thread started.")
    conn.settimeout(1.0) # Use a timeout for recv to keep thread responsive
    partial_data_from_client = b""

    if server_state_obj.current_map_name:
        try:
            conn.sendall(encode_data({"command": "set_map", "name": server_state_obj.current_map_name}))
            debug(f"Server Handler ({addr}): Sent initial map info: {server_state_obj.current_map_name}")
        except socket.error as e:
            debug(f"Server Handler ({addr}): Error sending initial map info: {e}. Client may have disconnected early.")
            # Do not return yet, client might still send data or close cleanly.
    else:
        critical(f"Server Handler ({addr}): CRITICAL - server_state_obj.current_map_name is None. Cannot send initial map info.")
        # Consider closing connection if this is a fatal state for the server.

    while server_state_obj.app_running:
        with client_lock:
            if server_state_obj.client_connection is not conn: # Check if this is still the active connection
                debug(f"Server Handler ({addr}): Stale connection. Exiting thread.")
                break
        try:
            chunk = conn.recv(server_state_obj.buffer_size)
            if not chunk:
                debug(f"Server Handler ({addr}): Client disconnected (received empty data).")
                break
            
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            
            for msg in decoded_inputs:
                command = msg.get("command")
                if command == "report_map_status":
                    map_name = msg.get("name")
                    status = msg.get("status")
                    debug(f"Server Handler ({addr}): Client map status for '{map_name}': {status}")
                    with client_lock:
                        server_state_obj.client_map_status = status
                        if status == "present":
                             server_state_obj.client_download_progress = 100.0
                             # Signal game start only if not already signaled
                             if not server_state_obj.game_start_signaled_to_client:
                                conn.sendall(encode_data({"command": "start_game_now"}))
                                server_state_obj.game_start_signaled_to_client = True
                                debug(f"Server Handler ({addr}): Client has map. Sent start_game_now.")
                elif command == "request_map_file":
                    map_name_req = msg.get("name")
                    debug(f"Server Handler ({addr}): Client requested map file: '{map_name_req}'")
                    map_file_path = os.path.join(C.MAPS_DIR, map_name_req + ".py")
                    if os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding="utf-8") as f: map_content_str = f.read()
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req, "size": len(map_content_str.encode('utf-8'))}))
                        offset = 0
                        map_content_bytes = map_content_str.encode('utf-8')
                        while offset < len(map_content_bytes):
                            chunk_to_send_bytes = map_content_bytes[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            # Send data as string to align with client expecting string for "data" field
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send_bytes.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send_bytes)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                        debug(f"Server Handler ({addr}): Sent map file '{map_name_req}' to client.")
                    else:
                        error(f"Server Error: Client requested map '{map_name_req}' but not found at '{map_file_path}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req, "reason": "not_found"}))
                elif command == "report_download_progress":
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0)
                elif "input" in msg: # Client's game input
                    with client_lock:
                        if server_state_obj.client_connection is conn: # Ensure this is still the active connection
                            server_state_obj.client_input_buffer = msg["input"] # Overwrite with the latest full input state
        except socket.timeout:
            continue # No data received within timeout, loop again
        except socket.error as e:
            if server_state_obj.app_running: # Only log if server is meant to be running
                debug(f"Server Handler ({addr}): Socket error: {e}. Assuming disconnect.")
            break # Exit loop on socket error
        except Exception as e:
            if server_state_obj.app_running:
                error(f"Server Handler ({addr}): Unexpected error: {e}", exc_info=True)
            break # Exit loop on other critical errors

    # Cleanup for this client connection
    with client_lock:
        if server_state_obj.client_connection is conn: # If this was the active connection
            debug(f"Server Handler ({addr}): Closing active connection from handler.")
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True} # Signal disconnect to main server loop
            server_state_obj.client_map_status = "disconnected" # Update status
            server_state_obj.game_start_signaled_to_client = False # Reset for next potential client
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except: pass # Ignore errors if already closed
    try:
        conn.close()
    except: pass
    debug(f"Server: Client handler for {addr} finished.")


def run_server_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                    fonts: dict, game_elements_ref: dict, server_state_obj: ServerState):
    debug("DEBUG Server: Entering run_server_mode.")
    pygame.display.set_caption(f"Platformer - HOST (P1 Controls: {game_config.CURRENT_P1_INPUT_DEVICE} | P2: Client | Reset: P1MappedResetKey/Q)")
    server_state_obj.app_running = True # Ensure app_running is true for this mode
    current_width, current_height = screen.get_size()

    if server_state_obj.current_map_name is None:
        critical("CRITICAL SERVER: server_state_obj.current_map_name is None at start of run_server_mode. Cannot proceed.")
        return # Cannot host without a map selected

    # Start broadcasting presence if not already
    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("DEBUG Server: Starting broadcast thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()

    # Setup TCP listening socket
    if server_state_obj.server_tcp_socket: # Close if somehow already exists
        debug("DEBUG Server: Closing existing TCP socket before creating new one.")
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1) # Listen for one client connection
        server_state_obj.server_tcp_socket.settimeout(1.0) # Non-blocking accept for UI responsiveness
        debug(f"DEBUG Server: Listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e}")
        # Potentially stop broadcast thread and close UDP socket if created
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
            # Signal broadcast thread to stop; it checks app_running
            temp_app_running_for_broadcast_shutdown = server_state_obj.app_running
            server_state_obj.app_running = False 
            server_state_obj.broadcast_thread.join(timeout=0.5)
            server_state_obj.app_running = temp_app_running_for_broadcast_shutdown # Restore state
        return

    debug("DEBUG Server: Waiting for Player 2 to connect...")
    server_state_obj.client_map_status = "unknown"; server_state_obj.client_download_progress = 0.0
    server_state_obj.game_start_signaled_to_client = False
    client_sync_wait_active = True

    while client_sync_wait_active and server_state_obj.app_running:
        current_width, current_height = screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: server_state_obj.app_running = False; client_sync_wait_active = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width, current_height = max(320,event.w), max(240,event.h)
                screen = pygame.display.set_mode((current_width, current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                server_state_obj.app_running = False; client_sync_wait_active = False; break
        if not server_state_obj.app_running: break

        if server_state_obj.client_connection is None: # If no client is currently connected
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock:
                    server_state_obj.client_connection = temp_conn; server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {}; server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False # Reset for new client
                debug(f"DEBUG Server: Accepted connection from {temp_addr}")

                # Start new handler thread for this client
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    server_state_obj.client_handler_thread.join(timeout=0.1) # Ensure previous one is done
                server_state_obj.client_handler_thread = threading.Thread(
                    target=handle_client_connection_thread, args=(temp_conn, temp_addr, server_state_obj), daemon=True
                )
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass # No connection attempt, continue waiting
            except Exception as e: error(f"Server: Error accepting client: {e}", exc_info=True)
        
        dialog_title_sync = "Server Hosting"; dialog_msg_sync = "Waiting for Player 2..."; dialog_prog_sync = -1.0
        with client_lock: # Read shared state safely
            if server_state_obj.client_connection:
                if server_state_obj.client_map_status == "waiting_client_report": dialog_msg_sync = f"P2 ({server_state_obj.client_address[0] if server_state_obj.client_address else 'Unknown'}) connected. Syncing map..."
                elif server_state_obj.client_map_status == "missing": dialog_msg_sync = f"P2 missing map '{server_state_obj.current_map_name}'. Sending..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "downloading_ack": dialog_msg_sync = f"P2 downloading map '{server_state_obj.current_map_name}'..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "present":
                    dialog_msg_sync = f"P2 has map '{server_state_obj.current_map_name}'. Ready."; dialog_prog_sync = 100.0
                    if server_state_obj.game_start_signaled_to_client: # If server has sent start_game_now and client acknowledged map
                        client_sync_wait_active = False # Exit sync loop
                elif server_state_obj.client_map_status == "disconnected":
                    dialog_msg_sync = "P2 disconnected. Waiting for new connection...";
                    server_state_obj.client_connection = None # Allow new connections
        
        game_ui.draw_download_dialog(screen, fonts, dialog_title_sync, dialog_msg_sync, dialog_prog_sync)
        clock.tick(10) # Keep UI responsive during wait

    if not server_state_obj.app_running or server_state_obj.client_connection is None or server_state_obj.client_map_status != "present":
        debug(f"DEBUG Server: Exiting sync (app_running: {server_state_obj.app_running}, client_conn: {server_state_obj.client_connection is not None}, map_status: {server_state_obj.client_map_status}).")
        server_state_obj.app_running = False # Ensure broadcast thread stops
        # Cleanup threads and sockets
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return

    debug(f"DEBUG Server: Client {server_state_obj.client_address if server_state_obj.client_address else 'Unknown'} connected, map synced. Starting game...")
    p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2")
    if p1: debug(f"DEBUG Server: P1 instance: {p1}, Valid: {p1._valid_init if p1 else 'N/A'}")
    if p2: debug(f"DEBUG Server: P2 instance: {p2}, Valid: {p2._valid_init if p2 else 'N/A'}")
    
    server_game_active = True
    p1_action_events: Dict[str, bool] = {} # Stores events like "jump":True for one frame

    while server_game_active and server_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks_server = pygame.time.get_ticks()
        pygame_events = pygame.event.get(); keys_pressed_p1 = pygame.key.get_pressed()
        
        # Reset flags each frame
        host_requested_reset = False
        p2_requested_reset_from_client = False
        client_requested_pause_from_input = False
        client_disconnected_signal = False

        for event in pygame_events:
            if event.type == pygame.QUIT: server_game_active = False; server_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width,current_height = max(320,event.w),max(240,event.h)
                screen=pygame.display.set_mode((current_width,current_height),pygame.RESIZABLE|pygame.DOUBLEBUF)
                if game_elements_ref.get("camera"): game_elements_ref["camera"].set_screen_dimensions(current_width, current_height)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: server_game_active = False
                if event.key == pygame.K_q: # Dev reset key
                    host_requested_reset = True; info("Server: Dev 'Q' key reset triggered.")
                if p1 and p1._valid_init:
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'): p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'): p1.heal_to_full()
        if not server_state_obj.app_running or not server_game_active: break

        # Process P1 input (Host player)
        if p1 and p1._valid_init and not p1.is_dead and hasattr(p1, 'process_input'):
            p1_action_events = p1.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed_p1)
            if p1_action_events.get("pause"):
                info("Server: P1 pause action detected. Returning to main menu.")
                server_game_active = False
            if p1_action_events.get("reset"):
                host_requested_reset = True
                info("Server: P1 reset action detected.")
        if not server_game_active: break

        # Process client (P2) input from buffer
        p2_network_input: Optional[Dict[str, Any]] = None
        with client_lock:
            if server_state_obj.client_input_buffer:
                p2_network_input = server_state_obj.client_input_buffer.copy() # Get the full input state
                server_state_obj.client_input_buffer.clear() # Clear buffer after processing

                if p2_network_input.get("disconnect"): client_disconnected_signal = True
                if p2_network_input.get("reset", False) or p2_network_input.get("action_reset_global", False):
                    p2_requested_reset_from_client = True
                    info(f"Server: Client reset action detected (reset: {p2_network_input.get('reset', False)}, global: {p2_network_input.get('action_reset_global', False)}).")
                if p2_network_input.get("pause_event", False): # Check for pause event from client
                    client_requested_pause_from_input = True
                
                # P2 self-harm/heal from client's input buffer
                if p2 and p2._valid_init:
                    if p2_network_input.get("action_self_harm", False) and hasattr(p2, 'self_inflict_damage'):
                        p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    elif p2_network_input.get("action_heal", False) and hasattr(p2, 'heal_to_full'):
                        p2.heal_to_full()
        
        if client_disconnected_signal:
            debug("DEBUG Server: Client disconnected signal received in main loop.")
            server_game_active = False; server_state_obj.client_connection = None; server_state_obj.client_map_status = "unknown"
            break
        if client_requested_pause_from_input:
            info("Server: Client (P2) requested pause. Returning to main menu.")
            server_game_active = False
        if not server_game_active: break

        # Apply P2's network input to P2's character
        if p2 and p2._valid_init and p2_network_input and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input)
        
        # Game reset logic (handles P1's "game over" state for client-initiated resets)
        is_p1_game_over_for_reset = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or (hasattr(p1, 'death_animation_finished') and p1.death_animation_finished))) or (not p1 or not p1._valid_init)
        if host_requested_reset or (p2_requested_reset_from_client and is_p1_game_over_for_reset):
            info("DEBUG Server: Game state reset triggered by host or client conditional reset.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p2)

        # Update game entities (Players, Enemies, Projectiles, etc.)
        if p1 and p1._valid_init:
            other_players_p1 = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref
            p1.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), game_elements_ref.get("ladder_sprites", pygame.sprite.Group()), game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), other_players_p1, game_elements_ref.get("enemy_list", []))
        
        if p2 and p2._valid_init: # P2 is updated based on its network input
            other_players_p2 = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), game_elements_ref.get("ladder_sprites", pygame.sprite.Group()), game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), other_players_p2, game_elements_ref.get("enemy_list", []))
        
        active_players_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_instance in list(game_elements_ref.get("enemy_list", [])):
            if enemy_instance._valid_init:
                if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified: continue # Petrified enemies don't update
                enemy_instance.update(dt_sec, active_players_ai, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), game_elements_ref.get("hazard_sprites", pygame.sprite.Group()), game_elements_ref.get("enemy_list", []))
                if enemy_instance.is_dead and hasattr(enemy_instance, 'death_animation_finished') and enemy_instance.death_animation_finished and enemy_instance.alive():
                    if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"server_killing_enemy_{enemy_instance.enemy_id}"): debug(f"Server: Auto-killing enemy {enemy_instance.enemy_id} as death anim finished.")
                    enemy_instance.kill()
        
        statues = game_elements_ref.get("statue_objects", []) # Statues
        for statue_instance in statues:
            if hasattr(statue_instance, 'update'): statue_instance.update(dt_sec)
            
        # Projectile updates
        hittable_chars_server = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_chars_server.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_chars_server.add(p2)
        for enemy_proj_target in game_elements_ref.get("enemy_list", []):
            if enemy_proj_target and enemy_proj_target.alive() and enemy_proj_target._valid_init and not getattr(enemy_proj_target, 'is_petrified', False): hittable_chars_server.add(enemy_proj_target)
        for statue_target in statues: # Add statues to hittable group
            if statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed: hittable_chars_server.add(statue_target)

        for proj_instance in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj_instance, 'game_elements_ref') and proj_instance.game_elements_ref is None: proj_instance.game_elements_ref = game_elements_ref
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), hittable_chars_server)
        
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec) # Chests

        # Chest interaction (server authoritative)
        chest_instance_server = game_elements_ref.get("current_chest")
        if isinstance(chest_instance_server, Chest) and chest_instance_server.alive() and not chest_instance_server.is_collected_flag_internal:
            interacted_player = None
            # P1 interaction (host)
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
               pygame.sprite.collide_rect(p1, chest_instance_server) and p1_action_events.get("interact", False):
                interacted_player = p1
            # P2 interaction (client - based on network input)
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
                 pygame.sprite.collide_rect(p2, chest_instance_server) and p2_network_input and p2_network_input.get("interact_pressed_event", False):
                interacted_player = p2
            if interacted_player: chest_instance_server.collect(interacted_player)

        # Camera update (server-side focus for local display)
        camera_instance_server = game_elements_ref.get("camera")
        if camera_instance_server:
            focus_target = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified', False): focus_target = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified', False): focus_target = p2 # Show P2 if P1 is dead
            elif p1 and p1.alive() and p1._valid_init: focus_target = p1 # Fallback to P1 even if dead/petrified
            elif p2 and p2.alive() and p2._valid_init: focus_target = p2 # Fallback to P2
            if focus_target: camera_instance_server.update(focus_target)
            else: camera_instance_server.static_update()

        # Send game state to client
        if server_state_obj.client_connection:
            net_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state = encode_data(net_state_to_send)
            if encoded_state:
                try: server_state_obj.client_connection.sendall(encoded_state)
                except socket.error as e_send:
                    debug(f"DEBUG Server: Send failed: {e_send}. Client likely disconnected."); server_game_active = False; server_state_obj.client_connection = None; break
        
        # Draw server's local view
        try:
            dl_status_s, dl_prog_s = None, None # For download dialog if client is still syncing
            with client_lock:
                if server_state_obj.client_map_status in ["missing", "downloading_ack"]: # Should not happen if game started
                    dl_status_s = f"P2 Downloading: {server_state_obj.current_map_name}"; dl_prog_s = server_state_obj.client_download_progress
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_server, download_status_message=dl_status_s, download_progress_percent=dl_prog_s)
        except Exception as e_draw: error(f"Server draw error: {e_draw}", exc_info=True); server_game_active=False; break
        pygame.display.flip()

    # --- End of Server Game Loop ---
    debug("DEBUG Server: Exiting active game loop.")
    conn_to_close_server = None
    with client_lock: # Ensure thread-safe access to client_connection
        if server_state_obj.client_connection:
            conn_to_close_server = server_state_obj.client_connection
            server_state_obj.client_connection = None # Mark as no longer active
    
    if conn_to_close_server:
        debug("DEBUG Server: Mode exit cleanup - closing client connection.")
        try: conn_to_close_server.shutdown(socket.SHUT_RDWR)
        except: pass
        try: conn_to_close_server.close()
        except: pass
        
    if server_state_obj.server_tcp_socket:
        debug("DEBUG Server: Closing main TCP listening socket.")
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
        
    debug("DEBUG Server: Server mode finished and returned to caller.")