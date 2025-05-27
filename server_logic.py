# server_logic.py
# -*- coding: utf-8 -*-
"""
Handles server-side game logic, connection management, and broadcasting for PySide6.
UI updates are handled by emitting signals or using callbacks.
Map paths now use map_name_folder/map_name_file.py structure.
MODIFIED: Statue physics and lifecycle management in game loop.
MODIFIED: Ensures statues are included in hittable targets for player attacks.
"""
# version 2.0.8 (Statue targeting for player attacks)

import os
import socket
import threading
import time
import traceback
from typing import Optional, Dict, Any, List

from PySide6.QtCore import QRectF, QPointF # For type checking

# Game imports
import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue 
from tiles import Platform, Ladder, Lava, BackgroundTile
import config as game_config # For accessing player properties if needed
from player import Player # For type hinting and checks

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL SERVER_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

_start_time_server_logic_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_server_logic_monotonic) * 1000)

client_lock = threading.Lock()

class ServerState:
    def __init__(self):
        self.client_connection: Optional[socket.socket] = None
        self.client_address: Optional[Any] = None
        self.client_input_buffer: Dict[str, Any] = {}
        self.app_running = True
        self.server_tcp_socket: Optional[socket.socket] = None
        self.server_udp_socket: Optional[socket.socket] = None
        self.broadcast_thread: Optional[threading.Thread] = None
        self.client_handler_thread: Optional[threading.Thread] = None
        
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = int(getattr(C, "BUFFER_SIZE", 8192))
        self.broadcast_interval_s = float(getattr(C, "BROADCAST_INTERVAL_S", 1.0))
        
        self.current_map_name: Optional[str] = None # This should be folder_name/stem
        self.client_map_status: str = "unknown" # e.g. "unknown", "present", "missing", "downloading"
        self.client_download_progress: float = 0.0
        self.game_start_signaled_to_client: bool = False
        self.client_ready: bool = False # True when client has map and server has signaled game start


def broadcast_presence_thread(server_state_obj: ServerState):
    current_lan_ip = get_local_ip()
    broadcast_message_dict = {
        "service": server_state_obj.service_name,
        "tcp_ip": current_lan_ip,
        "tcp_port": server_state_obj.server_port_tcp,
        "map_name": server_state_obj.current_map_name or "Unknown Map" # map_name is folder/stem
    }
    broadcast_message_bytes = encode_data(broadcast_message_dict)
    if not broadcast_message_bytes:
        error("Server Error: Could not encode broadcast message for LAN discovery."); return

    try:
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5) # Non-blocking send
    except socket.error as e:
        error(f"Server Error: Failed to create UDP broadcast socket: {e}"); server_state_obj.server_udp_socket = None; return

    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    debug(f"Server (broadcast): Broadcasting {broadcast_message_dict} to {broadcast_address}")

    while server_state_obj.app_running:
        # Update map_name in broadcast if it changed
        if server_state_obj.current_map_name != broadcast_message_dict.get("map_name"):
            broadcast_message_dict["map_name"] = server_state_obj.current_map_name or "Unknown Map"
            new_broadcast_bytes = encode_data(broadcast_message_dict)
            if not new_broadcast_bytes:
                error("Server Error: Could not re-encode broadcast message with updated map name.")
            else:
                broadcast_message_bytes = new_broadcast_bytes
                debug(f"Server (broadcast): Updated broadcast message with map: {server_state_obj.current_map_name}")

        try:
            if server_state_obj.server_udp_socket:
                server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error as se:
            warning(f"Server Warning: Broadcast send socket error: {se}")
        except Exception as e: # Catch any other potential errors during send
            warning(f"Server Warning: Unexpected broadcast send error: {e}")
        
        # Wait for the interval, checking app_running periodically for graceful shutdown
        sleep_chunk = 0.1
        num_chunks = int(server_state_obj.broadcast_interval_s / sleep_chunk)
        for _ in range(max(1, num_chunks)): # Ensure at least one sleep if interval is short
            if not server_state_obj.app_running: break
            time.sleep(sleep_chunk)
            
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close(); server_state_obj.server_udp_socket = None
    debug("Server (broadcast): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr: Any, server_state_obj: ServerState, client_fully_synced_callback: Optional[callable]):
    debug(f"Server (client_handler): Client {addr} connected. Thread started.")
    conn.settimeout(1.0) # Set a timeout for recv operations
    partial_data_from_client = b""

    # Determine absolute path to the base "maps" directory
    maps_base_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs):
        project_root_from_constants = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)

    # Initial map info send
    if server_state_obj.current_map_name: # current_map_name is folder/stem
        try:
            conn.sendall(encode_data({"command": "set_map", "name": server_state_obj.current_map_name}))
            debug(f"Server Handler ({addr}): Sent initial map info (folder/stem): {server_state_obj.current_map_name}")
        except socket.error as e: debug(f"Server Handler ({addr}): Error sending map info: {e}.")
    else: critical(f"Server Handler ({addr}): CRITICAL - current_map_name is None. Cannot send map info.")

    while server_state_obj.app_running:
        with client_lock: # Ensure thread-safe access to client_connection
            if server_state_obj.client_connection is not conn:
                debug(f"Server Handler ({addr}): Stale connection for this thread. Exiting."); break
        try:
            chunk = conn.recv(server_state_obj.buffer_size)
            if not chunk: debug(f"Server Handler ({addr}): Client disconnected (empty data)."); break # Connection closed by client
            
            partial_data_from_client += chunk
            decoded_inputs, partial_data_from_client = decode_data_stream(partial_data_from_client)
            
            for msg in decoded_inputs:
                command = msg.get("command")
                if command == "report_map_status":
                    map_name_client_folder_stem = msg.get("name") # This is folder/stem
                    status_client = msg.get("status")
                    debug(f"Server Handler ({addr}): Client map '{map_name_client_folder_stem}': {status_client}")
                    with client_lock: # Lock access to shared server_state
                        server_state_obj.client_map_status = status_client
                        if status_client == "present":
                            server_state_obj.client_download_progress = 100.0
                            if not server_state_obj.game_start_signaled_to_client: # Signal start only once
                                conn.sendall(encode_data({"command": "start_game_now"}))
                                server_state_obj.game_start_signaled_to_client = True
                                server_state_obj.client_ready = True # Mark client as fully ready
                                if client_fully_synced_callback: client_fully_synced_callback()
                                debug(f"Server Handler ({addr}): Client has map. Sent start_game_now. Client marked as ready.")
                elif command == "request_map_file":
                    map_name_req_folder_stem = msg.get("name") # This is folder/stem
                    debug(f"Server Handler ({addr}): Client requested map: '{map_name_req_folder_stem}'")
                    map_py_file_path_to_send = os.path.join(maps_base_dir_abs, 
                                                            map_name_req_folder_stem, # Subfolder
                                                            f"{map_name_req_folder_stem}.py") # Actual .py file
                    if os.path.exists(map_py_file_path_to_send):
                        with open(map_py_file_path_to_send, "r", encoding="utf-8") as f_map: map_content_str = f_map.read()
                        map_bytes_utf8 = map_content_str.encode('utf-8') # Ensure bytes for len calculation
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req_folder_stem, "size": len(map_bytes_utf8)}))
                        offset = 0
                        while offset < len(map_bytes_utf8):
                            chunk_to_send_bytes = map_bytes_utf8[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send_bytes.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send_bytes)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req_folder_stem}))
                        debug(f"Server Handler ({addr}): Map '{map_name_req_folder_stem}' transfer complete from '{map_py_file_path_to_send}'.")
                    else:
                        error(f"Server: Client map request '{map_name_req_folder_stem}' not found at '{map_py_file_path_to_send}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req_folder_stem, "reason": "not_found_on_server"}))
                elif command == "report_download_progress": # Client sending its download progress
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0.0)
                elif "input" in msg: # Game input from client
                    with client_lock:
                        if server_state_obj.client_connection is conn: # Ensure this is still the active connection
                            server_state_obj.client_input_buffer = msg["input"]
        
        except socket.timeout: continue # Normal if no data received within timeout
        except socket.error as e_sock:
            if server_state_obj.app_running: debug(f"Server Handler ({addr}): Socket error: {e_sock}. Client likely disconnected."); break
        except Exception as e_unexp:
            if server_state_obj.app_running: error(f"Server Handler ({addr}): Unexpected error: {e_unexp}", exc_info=True); break

    # Cleanup when loop exits
    with client_lock:
        if server_state_obj.client_connection is conn: # If this thread was managing the active connection
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True} # Signal main loop about disconnect
            server_state_obj.client_map_status = "disconnected"
            server_state_obj.game_start_signaled_to_client = False
            server_state_obj.client_ready = False 
            debug(f"Server: Client {addr} handler set client_connection to None and client_ready to False.")
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass # Ignore errors if already closed
    try: conn.close()
    except: pass
    debug(f"Server: Client handler thread for {addr} finished and connection closed.")


def run_server_mode(server_state_obj: ServerState,
                    game_elements_ref: Dict[str, Any],
                    ui_status_update_callback: Optional[callable] = None, 
                    get_p1_input_snapshot_callback: Optional[callable] = None, 
                    process_qt_events_callback: Optional[callable] = None,
                    client_fully_synced_callback: Optional[callable] = None 
                    ):
    debug("ServerLogic: Entering run_server_mode.")
    server_state_obj.app_running = True # Ensure app_running is true at start
    
    # Ensure current_map_name (folder/stem) is set
    if server_state_obj.current_map_name is None:
        map_name_from_ge = game_elements_ref.get('map_name', game_elements_ref.get('loaded_map_name'))
        if map_name_from_ge:
            server_state_obj.current_map_name = map_name_from_ge
            info(f"ServerLogic: current_map_name was None, set from game_elements to '{map_name_from_ge}'")
        else:
            critical("CRITICAL SERVER: current_map_name is None and not found in game_elements. Cannot host."); return

    # Start broadcast thread if not already running
    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("ServerLogic: Starting broadcast presence thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()

    # Setup TCP listening socket
    if server_state_obj.server_tcp_socket: # Close existing if any (e.g., from previous attempt)
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # Use C.SERVER_IP_BIND for binding to allow connections from any interface
        server_state_obj.server_tcp_socket.bind((str(C.SERVER_IP_BIND), server_state_obj.server_port_tcp)) 
        server_state_obj.server_tcp_socket.listen(1) # Listen for one connection
        server_state_obj.server_tcp_socket.settimeout(1.0) # Non-blocking accept
        debug(f"ServerLogic: TCP socket listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e_bind:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e_bind}")
        # Ensure graceful shutdown of broadcast if TCP fails
        _temp_app_running_state = server_state_obj.app_running
        server_state_obj.app_running = False
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
            server_state_obj.broadcast_thread.join(timeout=0.5)
        server_state_obj.app_running = _temp_app_running_state # Restore for main app loop if needed
        return

    debug("ServerLogic: Waiting for Player 2 connection and map synchronization...")
    with client_lock: # Initialize/reset client state tracking
        server_state_obj.client_map_status = "unknown"
        server_state_obj.client_download_progress = 0.0
        server_state_obj.game_start_signaled_to_client = False
        server_state_obj.client_connection = None # No client connected yet
        server_state_obj.client_ready = False # Client not ready yet

    client_sync_wait_active = True
    last_ui_cb_time = 0.0 
    while client_sync_wait_active and server_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback() # Process Qt events
        if not server_state_obj.app_running: break

        # Accept new connection if no client is currently connected
        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock: # Set new client connection details
                    server_state_obj.client_connection = temp_conn
                    server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {} # Clear buffer for new client
                    server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False # Reset for new client
                    server_state_obj.client_ready = False # Reset for new client
                debug(f"ServerLogic: Accepted client connection from {temp_addr}")
                # Start a new thread to handle this client
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    debug("ServerLogic: Joining previous client handler thread...")
                    server_state_obj.client_handler_thread.join(timeout=0.1) # Brief wait for old thread
                server_state_obj.client_handler_thread = threading.Thread(
                    target=handle_client_connection_thread,
                    args=(temp_conn, temp_addr, server_state_obj, client_fully_synced_callback), 
                    daemon=True
                )
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass # Normal if no connection attempt within timeout
            except Exception as e_accept:
                error(f"ServerLogic: Error accepting client connection: {e_accept}", exc_info=True)
        
        # Update UI status (e.g., for a "waiting for client" dialog)
        if ui_status_update_callback and (time.monotonic() - last_ui_cb_time > 0.2):
            title, msg, prog = "Server Hosting", "Waiting for Player 2...", -1.0
            with client_lock: # Read shared state safely
                if server_state_obj.client_connection:
                    client_ip_str = str(server_state_obj.client_address[0]) if server_state_obj.client_address else 'Connecting...'
                    current_status = server_state_obj.client_map_status
                    current_map_folder_stem = server_state_obj.current_map_name or "selected map"
                    current_progress = server_state_obj.client_download_progress
                    if current_status == "waiting_client_report": msg = f"Player 2 ({client_ip_str}) connected. Syncing map info..."
                    elif current_status == "missing": msg = f"Player 2 needs '{current_map_folder_stem}'. Sending file..."; prog = max(0.0, current_progress)
                    elif current_status == "downloading_ack" or current_status == "downloading": msg = f"Player 2 downloading '{current_map_folder_stem}' ({current_progress:.0f}%)..."; prog = max(0.0, current_progress)
                    elif current_status == "present": msg = f"Player 2 has '{current_map_folder_stem}'. Ready for game start."; prog = 100.0
                    if server_state_obj.client_ready: # If client_handler_thread marked client as ready
                        client_sync_wait_active = False # Exit this loop
                    elif current_status == "disconnected": # If client_handler_thread detected disconnect
                        msg = "Player 2 disconnected. Waiting for a new connection..."
                        server_state_obj.client_connection = None # Allow accepting new connection
                        server_state_obj.client_ready = False
                        prog = -1.0
            ui_status_update_callback(title, msg, prog)
            last_ui_cb_time = time.monotonic()
        
        time.sleep(0.01) # Small sleep to prevent busy-waiting

    # Check why the sync wait loop exited
    if not server_state_obj.app_running or not server_state_obj.client_ready:
        debug(f"ServerLogic: Exiting client sync wait phase. AppRunning: {server_state_obj.app_running}, ClientReady: {server_state_obj.client_ready}")
        # Cleanup if exiting due to app stop or client not becoming ready
        server_state_obj.app_running = False # Signal threads to stop
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return # End server mode

    # --- Main Game Loop (Client is synced and ready) ---
    debug(f"ServerLogic: Client synced successfully. Starting main game loop for map '{server_state_obj.current_map_name}'...")
    p1: Optional[Player] = game_elements_ref.get("player1")
    p2: Optional[Player] = game_elements_ref.get("player2")
    server_game_active = True
    
    frame_duration = 1.0 / C.FPS # Target frame duration
    
    while server_game_active and server_state_obj.app_running:
        frame_start_time = time.monotonic()

        if process_qt_events_callback: process_qt_events_callback() # Keep UI responsive
        if not server_state_obj.app_running: break

        dt_sec = frame_duration # Use fixed dt for server logic consistency

        # Fetch game element lists (these might be modified by statue removal logic)
        platforms_list_this_frame: List[Any] = game_elements_ref.get("platforms_list", [])
        ladders_list_this_frame: List[Ladder] = game_elements_ref.get("ladders_list", [])
        hazards_list_this_frame: List[Lava] = game_elements_ref.get("hazards_list", [])
        current_enemies_list_ref: List[Enemy] = game_elements_ref.get("enemy_list", [])
        statue_objects_list_ref: List[Statue] = game_elements_ref.get("statue_objects", [])
        projectiles_list_ref: List[Any] = game_elements_ref.get("projectiles_list", [])
        collectible_items_list_ref: List[Any] = game_elements_ref.get("collectible_list", [])

        # Player 1 (Host) Input
        p1_action_events_current_frame: Dict[str, bool] = {}
        if p1 and hasattr(p1, '_valid_init') and p1._valid_init and get_p1_input_snapshot_callback:
            p1_action_events_current_frame = get_p1_input_snapshot_callback(p1)
            if p1_action_events_current_frame.get("pause"): # Host pause
                server_game_active = False; info("Server: P1 (host) pressed Pause. Ending game mode.")
            if p1_action_events_current_frame.get("reset"): # Host reset
                 info("Server: P1 (host) requested Reset action."); 
                 reset_game_state(game_elements_ref) # Full map and entity reload
                 # Re-fetch player instances and lists as they might have been recreated
                 p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2")
                 platforms_list_this_frame = game_elements_ref.get("platforms_list", []) # Re-fetch after reset
                 current_enemies_list_ref = game_elements_ref.get("enemy_list", []) 
                 statue_objects_list_ref = game_elements_ref.get("statue_objects", [])
                 projectiles_list_ref = game_elements_ref.get("projectiles_list", [])
                 collectible_items_list_ref = game_elements_ref.get("collectible_list", [])
        if not server_game_active: break # Exit loop if pause/reset changed active state

        # Player 2 (Client) Input
        p2_network_input_data: Optional[Dict[str, Any]] = None
        with client_lock: # Fetch client input safely
            if server_state_obj.client_input_buffer:
                p2_network_input_data = server_state_obj.client_input_buffer.copy()
                server_state_obj.client_input_buffer.clear() # Consume input
                if p2_network_input_data.get("disconnect"): # Check for disconnect signal
                    server_game_active = False; server_state_obj.client_connection = None # Mark for no more sends
                    info("Server: Client P2 disconnected via input buffer."); break
                if p2_network_input_data.get("pause", False) or p2_network_input_data.get("pause_event", False): # Client pause
                    server_game_active = False; info("Server: Client P2 requested Pause.")
                if p2_network_input_data.get("reset", False) or p2_network_input_data.get("action_reset_global", False):
                    is_p1_truly_dead_server = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or p1.death_animation_finished)) or (not p1 or not p1._valid_init)
                    if is_p1_truly_dead_server: # Allow client reset only if P1 is game over
                        info("Server: Client P2 reset action received and P1 is game over. Resetting state.")
                        reset_game_state(game_elements_ref)
                        p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2")
                        platforms_list_this_frame = game_elements_ref.get("platforms_list", [])
                        current_enemies_list_ref = game_elements_ref.get("enemy_list", []) 
                        statue_objects_list_ref = game_elements_ref.get("statue_objects", [])
                        projectiles_list_ref = game_elements_ref.get("projectiles_list", [])
                        collectible_items_list_ref = game_elements_ref.get("collectible_list", [])
        if not server_game_active: break # Exit loop if client action changed state

        # Apply P2's input if available
        if p2 and hasattr(p2, '_valid_init') and p2._valid_init and p2_network_input_data and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input_data)
        
        current_game_ticks_val = get_current_ticks_monotonic() # For state timers

        # Update Players
        player_instances_to_update_server = [p for p in [p1, p2] if p and hasattr(p, '_valid_init') and p._valid_init]

        for p_instance_server in player_instances_to_update_server:
            all_others_for_this_player_server = [other_p for other_p in player_instances_to_update_server if other_p is not p_instance_server and hasattr(other_p, 'alive') and other_p.alive()]
            current_chest_server_logic = game_elements_ref.get("current_chest")
            if current_chest_server_logic and current_chest_server_logic.alive() and current_chest_server_logic.state == 'closed':
                all_others_for_this_player_server.append(current_chest_server_logic)
            
            p_instance_server.game_elements_ref_for_projectiles = game_elements_ref # Ensure this is set for projectiles
            
            # --- MODIFIED: Construct comprehensive target list for player attacks ---
            hittable_targets_for_player_attacks_server: List[Any] = []
            hittable_targets_for_player_attacks_server.extend(
                [e for e in current_enemies_list_ref if hasattr(e, 'alive') and e.alive()]
            )
            hittable_targets_for_player_attacks_server.extend(
                [s for s in statue_objects_list_ref if hasattr(s, 'alive') and s.alive() and not getattr(s, 'is_smashed', False)]
            )
            # --- END MODIFICATION ---

            p_instance_server.update(dt_sec, 
                                     platforms_list_this_frame, 
                                     ladders_list_this_frame, 
                                     hazards_list_this_frame, 
                                     all_others_for_this_player_server, 
                                     hittable_targets_for_player_attacks_server) # Pass augmented list

        # Update Enemies
        active_players_for_ai_server = [p for p in player_instances_to_update_server if not getattr(p,'is_dead',True) and hasattr(p,'alive') and p.alive()]
        
        enemies_to_keep_server = []
        for enemy_instance_server in list(current_enemies_list_ref): # Iterate a copy
            if hasattr(enemy_instance_server, '_valid_init') and enemy_instance_server._valid_init:
                enemy_instance_server.update(dt_sec, active_players_for_ai_server, platforms_list_this_frame, hazards_list_this_frame, current_enemies_list_ref) 
                if hasattr(enemy_instance_server, 'alive') and enemy_instance_server.alive():
                    enemies_to_keep_server.append(enemy_instance_server)
        game_elements_ref["enemy_list"] = enemies_to_keep_server

        # --- Statue Physics and Update/Removal Logic for Server ---
        statues_to_keep_server = []
        statues_killed_this_frame_server = []
        for statue_obj_server_loop in list(statue_objects_list_ref): # Iterate a copy
            if hasattr(statue_obj_server_loop, 'alive') and statue_obj_server_loop.alive():
                if hasattr(statue_obj_server_loop, 'apply_physics_step') and not statue_obj_server_loop.is_smashed:
                    statue_obj_server_loop.apply_physics_step(dt_sec, platforms_list_this_frame)
                
                if hasattr(statue_obj_server_loop, 'update'):
                    statue_obj_server_loop.update(dt_sec) # Handles smashed animation timing
                
                if statue_obj_server_loop.alive(): # Re-check after update
                    statues_to_keep_server.append(statue_obj_server_loop)
                else:
                    statues_killed_this_frame_server.append(statue_obj_server_loop)
                    debug(f"ServerLogic: Statue {statue_obj_server_loop.statue_id} no longer alive.")
        
        game_elements_ref["statue_objects"] = statues_to_keep_server # Update the main list
        
        # If statues were killed (e.g., smashed and finished animation), remove them from platforms_list
        if statues_killed_this_frame_server:
            current_platforms_server = game_elements_ref.get("platforms_list", [])
            new_platforms_list_server = [
                p_s for p_s in current_platforms_server 
                if not (isinstance(p_s, Statue) and p_s in statues_killed_this_frame_server)
            ]
            if len(new_platforms_list_server) != len(current_platforms_server):
                game_elements_ref["platforms_list"] = new_platforms_list_server
                platforms_list_this_frame = new_platforms_list_server # Update local ref for this frame
                debug(f"ServerLogic: Updated platforms_list after statue removal. Count: {len(new_platforms_list_server)}")
        # --- END Statue Logic ---
            
        # Update Projectiles (Target list includes players, enemies, and statues)
        hittable_targets_on_server_proj: List[Any] = []
        for p_target_serv in player_instances_to_update_server: # Active players
            if hasattr(p_target_serv, 'alive') and p_target_serv.alive() and not getattr(p_target_serv,'is_petrified',False):
                hittable_targets_on_server_proj.append(p_target_serv)
        for en_target_serv in game_elements_ref.get("enemy_list",[]): # Active enemies
            if hasattr(en_target_serv, 'alive') and en_target_serv.alive() and not getattr(en_target_serv,'is_petrified',False):
                hittable_targets_on_server_proj.append(en_target_serv)
        for st_target_serv in game_elements_ref.get("statue_objects", []): # Active, non-smashed statues
            if hasattr(st_target_serv, 'alive') and st_target_serv.alive() and not getattr(st_target_serv,'is_smashed',False) :
                hittable_targets_on_server_proj.append(st_target_serv)
        
        projectiles_to_keep_server = []
        for proj_obj_server in list(projectiles_list_ref): # Iterate a copy
            if hasattr(proj_obj_server, 'update'):
                proj_obj_server.update(dt_sec, platforms_list_this_frame, hittable_targets_on_server_proj)
            if hasattr(proj_obj_server, 'alive') and proj_obj_server.alive():
                projectiles_to_keep_server.append(proj_obj_server)
        game_elements_ref["projectiles_list"] = projectiles_to_keep_server
        
        # Update Chest (Physics, Interaction, Animation)
        current_chest_server_loop = game_elements_ref.get("current_chest")
        if current_chest_server_loop and isinstance(current_chest_server_loop, Chest) and \
           current_chest_server_loop.alive() and not current_chest_server_loop.is_collected_flag_internal and \
           current_chest_server_loop.state == 'closed': # Only apply physics if closed and not collected
            if hasattr(current_chest_server_loop, 'apply_physics_step'):
                current_chest_server_loop.apply_physics_step(dt_sec)
            # Platform collision for chest
            current_chest_server_loop.on_ground = False # Reset before check
            if hasattr(current_chest_server_loop, 'rect') and isinstance(current_chest_server_loop.rect, QRectF):
                old_chest_bottom_s = current_chest_server_loop.rect.bottom() - (current_chest_server_loop.vel_y * dt_sec * C.FPS if current_chest_server_loop.vel_y > 0 else 0)
                for platform_coll_s in platforms_list_this_frame: 
                    if isinstance(platform_coll_s, Statue) and platform_coll_s.is_smashed: continue # Ignore smashed statues
                    if hasattr(platform_coll_s, 'rect') and isinstance(platform_coll_s.rect, QRectF) and \
                       current_chest_server_loop.rect.intersects(platform_coll_s.rect):
                        if current_chest_server_loop.vel_y >= 0 and \
                           old_chest_bottom_s <= platform_coll_s.rect.top() + 1 and \
                           current_chest_server_loop.rect.bottom() >= platform_coll_s.rect.top(): # Check if was above or barely on
                            min_overlap_ratio_cs = 0.1
                            min_horizontal_overlap_cs = current_chest_server_loop.rect.width() * min_overlap_ratio_cs
                            actual_overlap_cs = min(current_chest_server_loop.rect.right(), platform_coll_s.rect.right()) - \
                                                max(current_chest_server_loop.rect.left(), platform_coll_s.rect.left())
                            if actual_overlap_cs >= min_horizontal_overlap_cs:
                                current_chest_server_loop.rect.moveBottom(platform_coll_s.rect.top())
                                if hasattr(current_chest_server_loop, 'pos_midbottom'): current_chest_server_loop.pos_midbottom.setY(current_chest_server_loop.rect.bottom())
                                current_chest_server_loop.vel_y = 0.0
                                current_chest_server_loop.on_ground = True; break # Landed on one platform
                if hasattr(current_chest_server_loop, '_update_rect_from_image_and_pos'):
                    current_chest_server_loop._update_rect_from_image_and_pos()
        
        # Update chest animation/state & handle collection
        collectibles_to_keep_server = []
        if current_chest_server_loop and current_chest_server_loop.alive(): # Check if chest still exists (wasn't collected last frame)
            current_chest_server_loop.update(dt_sec) # Handles opening animation, fading, etc.
            collectibles_to_keep_server.append(current_chest_server_loop)
        game_elements_ref["collectible_list"] = collectibles_to_keep_server
        if not (current_chest_server_loop and current_chest_server_loop.alive()): # If chest was collected and killed
            game_elements_ref["current_chest"] = None # Remove from main game_elements ref

        # Check for chest interaction AFTER physics and state updates for this frame
        current_chest_for_interact = game_elements_ref.get("current_chest") # Re-fetch in case it was just collected
        if current_chest_for_interact and isinstance(current_chest_for_interact, Chest) and \
           current_chest_for_interact.alive() and not current_chest_for_interact.is_collected_flag_internal and \
           current_chest_for_interact.state == 'closed':
            interacting_player_server_chest: Optional[Player] = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False) and \
               hasattr(p1, 'rect') and p1.rect.intersects(current_chest_for_interact.rect) and p1_action_events_current_frame.get("interact", False):
                interacting_player_server_chest = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False) and \
                 hasattr(p2, 'rect') and p2.rect.intersects(current_chest_for_interact.rect) and \
                 p2_network_input_data and p2_network_input_data.get("interact_pressed_event", False): # Check for "event" for P2
                interacting_player_server_chest = p2
            if interacting_player_server_chest:
                current_chest_for_interact.collect(interacting_player_server_chest)
        
        # Update Camera
        camera_on_server_loop = game_elements_ref.get("camera")
        if camera_on_server_loop:
            server_focus_target_loop: Optional[Player] = None
            # Prefer P1 if alive and not petrified/dead, then P2
            for p_cam_check in player_instances_to_update_server:
                if p_cam_check and hasattr(p_cam_check, 'alive') and p_cam_check.alive() and not getattr(p_cam_check, 'is_dead', True) and not getattr(p_cam_check,'is_petrified',False):
                    if server_focus_target_loop is None or p_cam_check.player_id < server_focus_target_loop.player_id: # Prioritize lower player ID
                        server_focus_target_loop = p_cam_check
            if server_focus_target_loop:
                camera_on_server_loop.update(server_focus_target_loop)
            else: # Fallback if all primary targets are gone (e.g., both dead/petrified)
                camera_on_server_loop.static_update()
            
        # Rebuild all_renderable_objects list for internal consistency (not directly used by client, but good practice)
        new_all_renderables_server_loop: List[Any] = []
        for static_list_key_server in ["background_tiles_list", "ladders_list", "hazards_list"]:
            for item_render_server in game_elements_ref.get(static_list_key_server, []):
                if item_render_server not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(item_render_server)
        for platform_item_render_server in game_elements_ref.get("platforms_list", []): # platforms_list now filtered
            if platform_item_render_server not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(platform_item_render_server)
        
        # Add processed custom images to renderables if they exist
        for custom_img_dict_server in game_elements_ref.get("processed_custom_images_for_render", []):
            if custom_img_dict_server not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(custom_img_dict_server)

        for dynamic_list_key_server in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
            for item_render_server_dyn in game_elements_ref.get(dynamic_list_key_server, []):
                if item_render_server_dyn not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(item_render_server_dyn)
        for p_render_server in player_instances_to_update_server:
            if p_render_server and hasattr(p_render_server, 'alive') and p_render_server.alive() and \
               p_render_server not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(p_render_server)
            elif p_render_server and getattr(p_render_server, 'is_dead', False) and \
                 not getattr(p_render_server, 'death_animation_finished', True) and \
                 p_render_server not in new_all_renderables_server_loop: new_all_renderables_server_loop.append(p_render_server) # Render dying player
        
        # Sort renderables by layer_order before assigning to game_elements
        # Assuming get_layer_order_key is available or defined in this scope
        if 'get_layer_order_key' in globals() and callable(globals()['get_layer_order_key']):
            new_all_renderables_server_loop.sort(key=globals()['get_layer_order_key'])
        else: warning("ServerLogic: get_layer_order_key not found. Render order might be incorrect.")
        game_elements_ref["all_renderable_objects"] = new_all_renderables_server_loop

        # Send Game State to Client
        if server_state_obj.client_connection: # Only if client is still connected
            network_game_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state = encode_data(network_game_state_to_send)
            if encoded_state:
                try:
                    server_state_obj.client_connection.sendall(encoded_state)
                except socket.error as e_send:
                    debug(f"Server: Send game state failed: {e_send}. Client likely disconnected.");
                    server_game_active = False; server_state_obj.client_connection = None; break # Mark client as disconnected and exit
        
        # Frame rate limiting
        time_spent_this_frame = time.monotonic() - frame_start_time
        sleep_duration = frame_duration - time_spent_this_frame
        if sleep_duration > 0:
            time.sleep(sleep_duration)

    # --- End of Main Game Loop ---
    debug("ServerLogic: Exiting server game active loop.")
    
    # Cleanup connection if game loop ended but connection was still active
    active_conn_to_close: Optional[socket.socket] = None
    with client_lock:
        if server_state_obj.client_connection:
            active_conn_to_close = server_state_obj.client_connection
            server_state_obj.client_connection = None # Ensure no more sends
    if active_conn_to_close:
        try: active_conn_to_close.shutdown(socket.SHUT_RDWR)
        except: pass
        try: active_conn_to_close.close()
        except: pass
        debug("ServerLogic: Active client connection closed after game loop.")

    # Stop broadcast thread and close server socket when run_server_mode finishes
    # This is typically done by the caller (app_core) which manages ServerState.app_running
    # However, if server_game_active loop breaks internally, ensure sockets are closed here too.
    if server_state_obj.server_tcp_socket: 
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
    
    debug("ServerLogic: Server mode (run_server_mode) finished.")