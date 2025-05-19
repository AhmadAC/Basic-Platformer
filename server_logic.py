# server_logic.py
# -*- coding: utf-8 -*-
"""
Handles server-side game logic, connection management, and broadcasting for PySide6.
UI updates are handled by emitting signals or using callbacks.
"""
# version 2.0.2 

import os
import socket
import threading
import time
import traceback
from typing import Optional, Dict, Any, List

# Game imports
import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state 
from enemy import Enemy 
from items import Chest
from statue import Statue 
import config as game_config 

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL SERVER_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# --- Monotonic Timer ---
_start_time_server_logic_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_server_logic_monotonic) * 1000)
# --- End Monotonic Timer ---

client_lock = threading.Lock() # Remains a standard library threading lock

class ServerState:
    def __init__(self):
        self.client_connection: Optional[socket.socket] = None
        self.client_address: Optional[Any] = None # socket.accept() returns (conn, address_tuple)
        self.client_input_buffer: Dict[str, Any] = {}
        self.app_running = True # Controlled by the main application loop
        self.server_tcp_socket: Optional[socket.socket] = None
        self.server_udp_socket: Optional[socket.socket] = None
        self.broadcast_thread: Optional[threading.Thread] = None
        self.client_handler_thread: Optional[threading.Thread] = None
        
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = int(getattr(C, "BUFFER_SIZE", 8192))
        self.broadcast_interval_s = float(getattr(C, "BROADCAST_INTERVAL_S", 1.0))
        
        self.current_map_name: Optional[str] = None
        self.client_map_status: str = "unknown" # e.g., "unknown", "waiting_client_report", "missing", "present", "downloading", "disconnected"
        self.client_download_progress: float = 0.0 # Percentage for UI
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
        error("Server Error: Could not encode broadcast message for LAN discovery."); return

    try:
        # UDP socket for broadcasting
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5) # Non-blocking send attempts
    except socket.error as e:
        error(f"Server Error: Failed to create UDP broadcast socket: {e}"); server_state_obj.server_udp_socket = None; return

    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp) # Broadcast to all interfaces
    debug(f"Server (broadcast): Broadcasting {broadcast_message_dict} to {broadcast_address}")

    while server_state_obj.app_running: # Loop controlled by main app status
        try:
            if server_state_obj.server_udp_socket:
                server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error as se:
            warning(f"Server Warning: Broadcast send socket error: {se}") # e.g., network interface down
        except Exception as e:
            warning(f"Server Warning: Unexpected broadcast send error: {e}")
        
        # Sleep for the broadcast interval, but check app_running frequently to exit quickly
        sleep_chunk = 0.1 # seconds
        num_chunks = int(server_state_obj.broadcast_interval_s / sleep_chunk)
        for _ in range(max(1, num_chunks)): # Ensure at least one sleep if interval is very short
            if not server_state_obj.app_running: break
            time.sleep(sleep_chunk)
            
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close(); server_state_obj.server_udp_socket = None
    debug("Server (broadcast): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr: Any, server_state_obj: ServerState):
    # The use of os.path.join and C.MAPS_DIR is standard.
    # The map file reading is standard Python file I/O.
    # Existing implementation is fine.
    debug(f"Server (client_handler): Client {addr} connected. Thread started.")
    conn.settimeout(1.0)
    partial_data_from_client = b""

    if server_state_obj.current_map_name:
        try:
            conn.sendall(encode_data({"command": "set_map", "name": server_state_obj.current_map_name}))
            debug(f"Server Handler ({addr}): Sent initial map info: {server_state_obj.current_map_name}")
        except socket.error as e: debug(f"Server Handler ({addr}): Error sending map info: {e}.")
    else: critical(f"Server Handler ({addr}): CRITICAL - current_map_name is None.")

    while server_state_obj.app_running:
        with client_lock:
            if server_state_obj.client_connection is not conn: debug(f"Server Handler ({addr}): Stale connection. Exiting."); break
        try:
            chunk = conn.recv(server_state_obj.buffer_size)
            if not chunk: debug(f"Server Handler ({addr}): Client disconnected (empty data)."); break
            
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            
            for msg in decoded_inputs:
                command = msg.get("command")
                if command == "report_map_status":
                    map_name_client = msg.get("name"); status_client = msg.get("status")
                    debug(f"Server Handler ({addr}): Client map '{map_name_client}': {status_client}")
                    with client_lock:
                        server_state_obj.client_map_status = status_client
                        if status_client == "present":
                            server_state_obj.client_download_progress = 100.0
                            if not server_state_obj.game_start_signaled_to_client:
                                conn.sendall(encode_data({"command": "start_game_now"}))
                                server_state_obj.game_start_signaled_to_client = True
                                debug(f"Server Handler ({addr}): Client has map. Sent start_game_now.")
                elif command == "request_map_file":
                    map_name_req = msg.get("name")
                    debug(f"Server Handler ({addr}): Client requested map: '{map_name_req}'")
                    # MAPS_DIR should be absolute or correctly relative from project root.
                    # Assuming C.MAPS_DIR is correctly configured (as it is in constants.py provided).
                    map_file_path = os.path.join(C.MAPS_DIR, (map_name_req or "") + ".py")
                    if os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding="utf-8") as f_map: map_content_str = f_map.read()
                        map_bytes_utf8 = map_content_str.encode('utf-8')
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req, "size": len(map_bytes_utf8)}))
                        offset = 0
                        while offset < len(map_bytes_utf8):
                            chunk_to_send = map_bytes_utf8[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            # Send data as string, as JSON requires strings for text content
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                        debug(f"Server Handler ({addr}): Map '{map_name_req}' transfer complete.")
                    else:
                        error(f"Server: Client map request '{map_name_req}' not found at '{map_file_path}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req, "reason": "not_found_on_server"}))
                elif command == "report_download_progress":
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0.0)
                elif "input" in msg: # Client input data
                    with client_lock:
                        if server_state_obj.client_connection is conn: # Ensure still the active connection
                            server_state_obj.client_input_buffer = msg["input"]
        
        except socket.timeout: continue # Normal for non-blocking recv
        except socket.error as e_sock:
            if server_state_obj.app_running: debug(f"Server Handler ({addr}): Socket error: {e_sock}. Client likely disconnected."); break
        except Exception as e_unexp:
            if server_state_obj.app_running: error(f"Server Handler ({addr}): Unexpected error: {e_unexp}", exc_info=True); break

    # Cleanup for this specific client connection
    with client_lock:
        if server_state_obj.client_connection is conn: # If this thread was still managing the active connection
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True} # Signal disconnect to main server loop
            server_state_obj.client_map_status = "disconnected"
            server_state_obj.game_start_signaled_to_client = False
            debug(f"Server: Client {addr} handler set client_connection to None.")
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass # Ignore errors on shutdown (e.g., if already closed)
    try: conn.close()
    except: pass
    debug(f"Server: Client handler thread for {addr} finished and connection closed.")


def run_server_mode(server_state_obj: ServerState,
                    game_elements_ref: Dict[str, Any],
                    ui_status_update_callback: Optional[callable] = None, 
                    get_p1_input_snapshot_callback: Optional[callable] = None, 
                    process_qt_events_callback: Optional[callable] = None 
                    ):
    debug("ServerLogic: Entering run_server_mode.")
    server_state_obj.app_running = True # Ensure server loop runs
    
    if server_state_obj.current_map_name is None:
        critical("CRITICAL SERVER: current_map_name is None. Cannot host."); return

    # Start broadcast thread if not already running
    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("ServerLogic: Starting broadcast presence thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()

    # Setup TCP listening socket
    if server_state_obj.server_tcp_socket: # Close if already exists
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1) # Listen for one client connection
        server_state_obj.server_tcp_socket.settimeout(1.0) # Non-blocking accept
        debug(f"ServerLogic: TCP socket listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e_bind:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e_bind}")
        # Ensure broadcast thread is stopped if server can't start
        _temp_app_running_state = server_state_obj.app_running
        server_state_obj.app_running = False # Signal threads to stop
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
            server_state_obj.broadcast_thread.join(timeout=0.5)
        server_state_obj.app_running = _temp_app_running_state # Restore if needed by caller
        return

    debug("ServerLogic: Waiting for Player 2 connection and map synchronization...")
    # Reset client-specific state
    with client_lock:
        server_state_obj.client_map_status = "unknown"
        server_state_obj.client_download_progress = 0.0
        server_state_obj.game_start_signaled_to_client = False
        server_state_obj.client_connection = None # Ensure no stale connection

    client_sync_wait_active = True
    last_ui_cb_time = 0.0 # Use float for time.monotonic()
    while client_sync_wait_active and server_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback() # Keep UI responsive
        if not server_state_obj.app_running: break

        # Accept new client connection if none active
        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock: # Protect shared server_state_obj attributes
                    server_state_obj.client_connection = temp_conn
                    server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {} # Clear buffer for new client
                    server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False # Reset flag
                
                debug(f"ServerLogic: Accepted client connection from {temp_addr}")
                # Start a new thread to handle this client
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    debug("ServerLogic: Joining previous client handler thread...")
                    server_state_obj.client_handler_thread.join(timeout=0.1) # Brief wait
                server_state_obj.client_handler_thread = threading.Thread(
                    target=handle_client_connection_thread,
                    args=(temp_conn, temp_addr, server_state_obj),
                    daemon=True
                )
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass # Normal for non-blocking accept
            except Exception as e_accept:
                error(f"ServerLogic: Error accepting client connection: {e_accept}", exc_info=True)
        
        # Update UI status periodically
        if ui_status_update_callback and (time.monotonic() - last_ui_cb_time > 0.2):
            title, msg, prog = "Server Hosting", "Waiting for Player 2...", -1.0
            with client_lock: # Access shared state safely
                if server_state_obj.client_connection:
                    client_ip_str = server_state_obj.client_address[0] if server_state_obj.client_address else 'Connecting...'
                    current_status = server_state_obj.client_map_status
                    current_map = server_state_obj.current_map_name or "selected map"
                    current_progress = server_state_obj.client_download_progress

                    if current_status == "waiting_client_report": msg = f"Player 2 ({client_ip_str}) connected. Syncing map info..."
                    elif current_status == "missing": msg = f"Player 2 needs '{current_map}'. Sending file..."; prog = max(0.0, current_progress)
                    elif current_status == "downloading_ack": msg = f"Player 2 downloading '{current_map}' ({current_progress:.0f}%)..."; prog = max(0.0, current_progress)
                    elif current_status == "present": msg = f"Player 2 has '{current_map}'. Ready for game start."; prog = 100.0
                    
                    if server_state_obj.game_start_signaled_to_client and current_status == "present":
                        client_sync_wait_active = False # Exit wait loop, game can start
                    elif current_status == "disconnected": # Client disconnected during sync
                        msg = "Player 2 disconnected. Waiting for a new connection..."
                        server_state_obj.client_connection = None # Allow accepting new client
                        prog = -1.0
            ui_status_update_callback(title, msg, prog)
            last_ui_cb_time = time.monotonic()
        
        time.sleep(0.01) # Yield CPU

    # Check exit conditions for the sync loop
    if not server_state_obj.app_running or \
       server_state_obj.client_connection is None or \
       server_state_obj.client_map_status != "present" or \
       not server_state_obj.game_start_signaled_to_client:
        debug(f"ServerLogic: Exiting client sync wait phase. AppRunning: {server_state_obj.app_running}, ClientConn: {server_state_obj.client_connection is not None}, MapStatus: {server_state_obj.client_map_status}, GameStartSent: {server_state_obj.game_start_signaled_to_client}")
        server_state_obj.app_running = False # Signal all threads to stop
        # Join threads and close sockets (cleanup)
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return # Exit server mode if sync failed or app closing

    # --- Main Server Game Loop ---
    debug(f"ServerLogic: Client synced successfully. Starting main game loop...")
    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")
    server_game_active = True
    
    frame_duration = 1.0 / C.FPS
    last_tick_time = time.monotonic() # For precise frame timing

    while server_game_active and server_state_obj.app_running:
        frame_start_time = time.monotonic()

        if process_qt_events_callback: process_qt_events_callback() # Keep UI responsive
        if not server_state_obj.app_running: break

        dt_sec = frame_duration # Use fixed dt for simulation consistency

        # P1 (Host) Input
        p1_action_events_current_frame: Dict[str, bool] = {}
        if p1 and hasattr(p1, '_valid_init') and p1._valid_init and get_p1_input_snapshot_callback:
            p1_action_events_current_frame = get_p1_input_snapshot_callback(p1, game_elements_ref.get("platforms_list", []))
            if p1_action_events_current_frame.get("pause"):
                server_game_active = False; info("Server: P1 (host) pressed Pause. Ending game mode.")
            if p1_action_events_current_frame.get("reset"):
                 info("Server: P1 (host) requested Reset action."); game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                 # Ensure players are re-added to renderables if reset made them non-alive temporarily
                 if p1 and p1._valid_init and not p1.alive() and p1 not in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                 if p2 and p2._valid_init and not p2.alive() and p2 not in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if not server_game_active: break # Exit if P1 paused

        # P2 (Client) Input
        p2_network_input_data: Optional[Dict[str, Any]] = None
        with client_lock:
            if server_state_obj.client_input_buffer:
                p2_network_input_data = server_state_obj.client_input_buffer.copy()
                server_state_obj.client_input_buffer.clear() # Consume the buffer
                if p2_network_input_data.get("disconnect"): # Client signaled disconnect
                    server_game_active = False; server_state_obj.client_connection = None
                    info("Server: Client P2 disconnected via input buffer."); break
                if p2_network_input_data.get("pause", False): # Client paused
                    server_game_active = False; info("Server: Client P2 requested Pause.")
                if p2_network_input_data.get("reset", False) or p2_network_input_data.get("action_reset_global", False):
                    is_p1_truly_dead = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or p1.death_animation_finished)) or (not p1 or not p1._valid_init)
                    if is_p1_truly_dead: # Only allow client reset if P1 is also out
                        info("Server: Client P2 reset action received and P1 is game over. Resetting state.")
                        game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                        if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                        if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if not server_game_active: break

        if p2 and hasattr(p2, '_valid_init') and p2._valid_init and p2_network_input_data and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input_data)
        
        # --- Update Game Logic (Players, Enemies, Items, etc.) ---
        # (This part is largely the same as couch_play_logic, but uses current_ticks_monotonic)
        current_game_ticks_val = get_current_ticks_monotonic()

        if p1 and hasattr(p1, '_valid_init') and p1._valid_init:
            other_players_for_p1 = [char for char in [p2] if char and hasattr(char, '_valid_init') and char._valid_init and hasattr(char, 'alive') and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref # Pass full context
            p1.update(dt_sec, game_elements_ref.get("platforms_list", []), 
                      game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), 
                      other_players_for_p1, 
                      game_elements_ref.get("enemy_list", []))

        if p2 and hasattr(p2, '_valid_init') and p2._valid_init:
            other_players_for_p2 = [char for char in [p1] if char and hasattr(char, '_valid_init') and char._valid_init and hasattr(char, 'alive') and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platforms_list", []), 
                      game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), 
                      other_players_for_p2, 
                      game_elements_ref.get("enemy_list", []))
        
        active_players_for_ai = [char for char in [p1,p2] if char and hasattr(char,'_valid_init') and char._valid_init and not getattr(char,'is_dead',True) and hasattr(char,'alive') and char.alive()]
        for enemy_instance in list(game_elements_ref.get("enemy_list", [])): # Iterate copy for safe removal
            if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
                if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified: 
                    if hasattr(enemy_instance, 'update_enemy_status_effects'): 
                        enemy_instance.update_enemy_status_effects(current_game_ticks_val, game_elements_ref.get("platforms_list",[]))
                    if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
                    if getattr(enemy_instance, 'is_dead', False) and getattr(enemy_instance, 'death_animation_finished', False) and enemy_instance.alive():
                        enemy_instance.kill()
                    continue # Skip normal update for petrified
                
                enemy_instance.update(dt_sec, active_players_for_ai, 
                                      game_elements_ref.get("platforms_list", []), 
                                      game_elements_ref.get("hazards_list", []), 
                                      game_elements_ref.get("enemy_list", []))
                if getattr(enemy_instance, 'is_dead', False) and hasattr(enemy_instance, 'death_animation_finished') and enemy_instance.death_animation_finished and enemy_instance.alive():
                    enemy_instance.kill()
        
        # Prune dead enemies
        game_elements_ref["enemy_list"][:] = [e for e in game_elements_ref.get("enemy_list", []) if hasattr(e, 'alive') and e.alive()]

        for statue_obj in list(game_elements_ref.get("statue_objects", [])):
            if hasattr(statue_obj, 'update'): statue_obj.update(dt_sec)
            if not (hasattr(statue_obj, 'alive') and statue_obj.alive()):
                game_elements_ref.get("statue_objects", []).remove(statue_obj)
            
        # Projectile update (same as couch play)
        hittable_targets_on_server = []
        if p1 and p1.alive() and p1._valid_init and not getattr(p1,'is_petrified',False): hittable_targets_on_server.append(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2,'is_petrified',False): hittable_targets_on_server.append(p2)
        for en_target in game_elements_ref.get("enemy_list",[]):
            if en_target.alive() and en_target._valid_init and not getattr(en_target,'is_petrified',False): hittable_targets_on_server.append(en_target)
        for st_target in game_elements_ref.get("statue_objects",[]):
            if st_target.alive() and not getattr(st_target,'is_smashed',False) : hittable_targets_on_server.append(st_target)
        
        projectiles_current_list = game_elements_ref.get("projectiles_list", [])
        for proj_obj in list(projectiles_current_list): # Iterate copy
            if hasattr(proj_obj, 'update'):
                proj_obj.update(dt_sec, game_elements_ref.get("platforms_list",[]), hittable_targets_on_server)
            if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                if proj_obj in projectiles_current_list: projectiles_current_list.remove(proj_obj)
        
        # Collectible update
        collectibles_current_list = game_elements_ref.get("collectible_list", [])
        for collectible_obj in list(collectibles_current_list): # Iterate copy
            if hasattr(collectible_obj, 'update'): collectible_obj.update(dt_sec)
            if not (hasattr(collectible_obj, 'alive') and collectible_obj.alive()):
                 if collectible_obj in collectibles_current_list: collectibles_current_list.remove(collectible_obj)
                 if game_elements_ref.get("current_chest") is collectible_obj: game_elements_ref["current_chest"] = None

        # Chest interaction (server side)
        current_chest_on_server = game_elements_ref.get("current_chest")
        if isinstance(current_chest_on_server, Chest) and current_chest_on_server.alive() and not current_chest_on_server.is_collected_flag_internal:
            interacting_player = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False) and \
               p1.rect.intersects(current_chest_on_server.rect) and p1_action_events_current_frame.get("interact", False):
                interacting_player = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False) and \
                 p2.rect.intersects(current_chest_on_server.rect) and \
                 p2_network_input_data and p2_network_input_data.get("interact_pressed_event", False):
                interacting_player = p2
            if interacting_player: current_chest_on_server.collect(interacting_player)
        
        # Camera update on server (for potential server-side view or replay data)
        camera_on_server = game_elements_ref.get("camera")
        if camera_on_server:
            server_focus_target = p1 if (p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False)) else \
                                  (p2 if (p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False)) else \
                                  (p1 if p1 and p1.alive() else p2)) # Fallbacks
            if server_focus_target: camera_on_server.update(server_focus_target)
            else: camera_on_server.static_update()
            
        # Send game state to client
        if server_state_obj.client_connection:
            network_game_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state = encode_data(network_game_state_to_send)
            if encoded_state:
                try:
                    server_state_obj.client_connection.sendall(encoded_state)
                except socket.error as e_send:
                    debug(f"Server: Send game state failed: {e_send}. Client likely disconnected.");
                    server_game_active = False; server_state_obj.client_connection = None; break # End game loop
        
        # Frame rate control
        time_spent_this_frame = time.monotonic() - frame_start_time
        sleep_duration = frame_duration - time_spent_this_frame
        if sleep_duration > 0:
            time.sleep(sleep_duration)
        last_tick_time = time.monotonic() # Update for next frame's dt calculation if it were dynamic

    # --- End of Main Server Game Loop ---
    debug("ServerLogic: Exiting server game active loop.")
    
    # Ensure client connection is properly closed if loop exited
    active_conn_to_close = None
    with client_lock:
        if server_state_obj.client_connection:
            active_conn_to_close = server_state_obj.client_connection
            server_state_obj.client_connection = None # Nullify to prevent handler from using it
    if active_conn_to_close:
        try: active_conn_to_close.shutdown(socket.SHUT_RDWR)
        except: pass
        try: active_conn_to_close.close()
        except: pass
        debug("ServerLogic: Active client connection closed after game loop.")

    if server_state_obj.server_tcp_socket: # Close listening socket
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
    
    debug("ServerLogic: Server mode (run_server_mode) finished.")
    # Broadcast thread will stop when server_state_obj.app_running is False (set by main window)