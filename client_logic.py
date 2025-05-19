#################### START OF FILE: client_logic.py ####################

# client_logic.py
# -*- coding: utf-8 -*-
"""
Handles client-side game logic, connection to server, and LAN discovery for PySide6.
UI updates are handled by emitting signals to the main application.
"""
# version 2.0.0 (PySide6 Refactor)

import socket
import time
import traceback
import os
import importlib
from typing import Optional, Dict, Any, Tuple # Added Tuple

# PySide6 for signals (if emitting directly from here, or main app handles it)
# from PySide6.QtCore import QObject, Signal # Example if ClientLogic becomes a QObject

# Game imports
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL CLIENT_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import set_network_game_state # Assumes this is refactored
# from enemy import Enemy # Not directly instantiated here by client
from game_setup import initialize_game_elements # Assumes this is refactored
# from items import Chest # Not directly instantiated
import config as game_config


class ClientState:
    """ Holds the state for the client operations. """
    def __init__(self):
        self.client_tcp_socket: Optional[socket.socket] = None
        self.server_state_buffer: bytes = b""
        self.last_received_server_state: Optional[Dict[str, Any]] = None
        self.app_running = True # Controlled by the main application
        
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.client_search_timeout_s = float(getattr(C, "CLIENT_SEARCH_TIMEOUT_S", 5.0))
        self.buffer_size = int(getattr(C, "BUFFER_SIZE", 8192))
        
        self.server_selected_map_name: Optional[str] = None
        self.map_download_status: str = "unknown" # e.g., "waiting_map_info", "checking", "missing", "downloading", "present", "error"
        self.map_download_progress: float = 0.0
        self.map_total_size_bytes: int = 0
        self.map_received_bytes: int = 0
        self.map_file_buffer: bytes = b""

        # --- Signals for UI updates (conceptual, main app would connect to these) ---
        # If ClientLogic were a QObject:
        # search_status_changed = Signal(str) # "Searching...", "Server Found: IP", "Timeout"
        # connection_status_changed = Signal(str, str) # title, message (e.g. "Connecting", "IP:Port" or "Failed", "Reason")
        # map_sync_status_changed = Signal(str, str, float) # title, message, progress_percent (-1 if no progress bar)
        # game_ready_to_start = Signal() # When map sync is complete and server says start
        # client_disconnected = Signal(str) # Reason for disconnect


def find_server_on_lan(client_state_obj: ClientState, 
                       # UI interaction now via signals or callbacks passed from main app
                       ui_update_callback: Optional[callable] = None 
                       ) -> Optional[Tuple[str, int]]:
    """
    Searches for a server on the LAN using UDP broadcasts.
    Updates UI via ui_update_callback(status_key, message_data).
    Status keys: "searching", "found", "timeout", "error", "cancelled"
    Returns (ip, port) tuple if server found, else None.
    """
    debug("Client (find_server_on_lan): Starting LAN server search.")
    if ui_update_callback: ui_update_callback("searching", "Searching for server on LAN...")

    listen_socket: Optional[socket.socket] = None
    found_server_ip: Optional[str] = None
    found_server_port: Optional[int] = None

    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', client_state_obj.discovery_port_udp))
        listen_socket.settimeout(0.5) # For non-blocking recvfrom
        debug(f"Client (find_server_on_lan): UDP listen socket bound to port {client_state_obj.discovery_port_udp}.")
    except socket.error as e_socket:
        error_msg = f"Failed to bind UDP listen socket on port {client_state_obj.discovery_port_udp}: {e_socket}"
        error(f"Client Error: {error_msg}")
        if ui_update_callback: ui_update_callback("error", error_msg)
        return None

    start_search_time = time.monotonic() # Use monotonic for durations
    client_local_ip = get_local_ip()
    debug(f"Client (find_server_on_lan): Searching (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.")

    while (time.monotonic() - start_search_time) < client_state_obj.client_search_timeout_s:
        if not client_state_obj.app_running: # Check if main app requested stop
            debug("Client (find_server_on_lan): LAN server search aborted (app_running is False).")
            if ui_update_callback: ui_update_callback("cancelled", "Search cancelled by application.")
            break 
        
        # In a Qt app, events (like Escape key) would be handled by the main event loop,
        # which would set client_state_obj.app_running = False if user cancels search dialog.
        
        try:
            if listen_socket:
                raw_udp_data, sender_address = listen_socket.recvfrom(client_state_obj.buffer_size)
                decoded_messages_list, _ = decode_data_stream(raw_udp_data)
                if not decoded_messages_list: continue
                
                decoded_udp_message = decoded_messages_list[0]
                if (isinstance(decoded_udp_message, dict) and
                    decoded_udp_message.get("service") == client_state_obj.service_name and
                    isinstance(decoded_udp_message.get("tcp_ip"), str) and
                    isinstance(decoded_udp_message.get("tcp_port"), int)):
                    
                    server_ip = decoded_udp_message["tcp_ip"]
                    server_port = decoded_udp_message["tcp_port"]
                    info(f"Client (find_server_on_lan): Found server '{client_state_obj.service_name}' at {server_ip}:{server_port}")
                    found_server_ip, found_server_port = server_ip, server_port
                    if ui_update_callback: ui_update_callback("found", (server_ip, server_port))
                    break # Server found
        except socket.timeout:
            continue # No broadcast received in this short interval
        except Exception as e_udp:
            error_msg = f"Client: Error processing UDP broadcast: {e_udp}"
            error(error_msg, exc_info=True)
            if ui_update_callback: ui_update_callback("error", error_msg)
            # Decide if this error is fatal for the search
    
    if listen_socket:
        listen_socket.close()

    if not found_server_ip and client_state_obj.app_running:
        info(f"Client (find_server_on_lan): No server for '{client_state_obj.service_name}' after timeout.")
        if ui_update_callback: ui_update_callback("timeout", f"No server found for '{client_state_obj.service_name}'.")
    
    return (found_server_ip, found_server_port) if found_server_ip and found_server_port else None


def run_client_mode(client_state_obj: ClientState, 
                    game_elements_ref: Dict[str, Any],
                    # Callbacks for UI updates, replacing direct Pygame drawing
                    ui_status_update_callback: Optional[callable] = None, # (title, message, progress_float)
                    target_ip_port_str: Optional[str] = None,
                    # FPS and dt_sec will be managed by main Qt loop
                    get_input_snapshot_callback: Optional[callable] = None, # Called to get current P2 input from Qt
                    process_qt_events_callback: Optional[callable] = None # For main loop to pump Qt events
                    ):
    """
    Runs the client mode: connects to a server, synchronizes map, and enters game loop.
    UI is updated via `ui_status_update_callback`.
    Input is fetched via `get_input_snapshot_callback`.
    """
    info("Client (run_client_mode): Entering client mode.")
    client_state_obj.app_running = True # Ensure it's set for this mode
    server_ip_to_connect: Optional[str] = None
    server_port_to_connect: int = C.SERVER_PORT_TCP # Default

    if target_ip_port_str:
        info(f"Client (run_client_mode): Direct IP specified: {target_ip_port_str}")
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1:
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError: warning(f"Client: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else:
        info("Client (run_client_mode): No direct IP, attempting LAN discovery.")
        # The LAN discovery UI is now handled by the main app, which calls find_server_on_lan
        # This function assumes discovery was done, or target_ip_port_str was provided.
        # For simplicity here, if no target_ip_port_str, we assume it's an error for now.
        # In a full app, the main menu flow would ensure target_ip_port_str is set after discovery.
        error("Client (run_client_mode): No target IP provided and LAN discovery flow is externalized. Cannot proceed.")
        if ui_status_update_callback: ui_status_update_callback("Error", "No server target specified.", -1)
        return

    if not server_ip_to_connect or not client_state_obj.app_running:
        info(f"Client: Exiting client mode (no server target or app closed).")
        return

    if client_state_obj.client_tcp_socket: # Close any old socket
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    connection_succeeded = False
    connection_error_msg = "Unknown Connection Error"
    
    try:
        info(f"Client: Attempting connection to server at {server_ip_to_connect}:{server_port_to_connect}...")
        if ui_status_update_callback: ui_status_update_callback("Connecting...", f"{server_ip_to_connect}:{server_port_to_connect}", 0)
        
        client_state_obj.client_tcp_socket.settimeout(10.0) # Blocking connect with timeout
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        client_state_obj.client_tcp_socket.settimeout(0.05) # Non-blocking for game loop recv
        info("Client: TCP Connection to server successful!")
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e_sock: connection_error_msg = f"Connection Error ({e_sock.strerror if hasattr(e_sock, 'strerror') else e_sock})"
    except Exception as e_conn: connection_error_msg = f"Unexpected Connection Error: {e_conn}"

    if not connection_succeeded:
        error(f"Client: Failed to connect: {connection_error_msg}")
        if ui_status_update_callback: ui_status_update_callback("Connection Failed", connection_error_msg, -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return

    # --- Map Synchronization Phase ---
    client_state_obj.map_download_status = "waiting_map_info"; client_state_obj.server_state_buffer = b""
    map_sync_phase_active = True
    last_ui_update_time = 0

    while map_sync_phase_active and client_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback() # Allow Qt events to be processed
        if not client_state_obj.app_running: break # Check after processing events

        # Update UI periodically or on change
        if ui_status_update_callback and (time.monotonic() - last_ui_update_time > 0.1 or client_state_obj.map_download_status == "changed_internally"):
            dialog_title_map = "Synchronizing Map"; dialog_msg_map = "Waiting for map info..."; dialog_prog_map = 0.0
            if client_state_obj.map_download_status == "checking": dialog_msg_map = f"Checking: {client_state_obj.server_selected_map_name or 'Unknown Map'}..."
            elif client_state_obj.map_download_status == "missing": dialog_msg_map = f"Map '{client_state_obj.server_selected_map_name}' missing. Requesting..."
            elif client_state_obj.map_download_status == "downloading":
                dialog_title_map = f"Downloading: {client_state_obj.server_selected_map_name or 'Unknown Map'}"
                dialog_msg_map = f"{client_state_obj.map_received_bytes/1024.0:.1f}/{client_state_obj.map_total_size_bytes/1024.0:.1f}KB"
                dialog_prog_map = client_state_obj.map_download_progress if client_state_obj.map_total_size_bytes > 0 else 0.0
            elif client_state_obj.map_download_status == "present":
                dialog_msg_map = f"Map '{client_state_obj.server_selected_map_name}' ready. Waiting for server..."; dialog_prog_map = 100.0
            elif client_state_obj.map_download_status == "error":
                dialog_title_map = "Map Error"; dialog_msg_map = f"Failed map sync: {client_state_obj.server_selected_map_name or 'Unknown'}"; dialog_prog_map = -1.0
            
            ui_status_update_callback(dialog_title_map, dialog_msg_map, dialog_prog_map)
            last_ui_update_time = time.monotonic()
            if client_state_obj.map_download_status == "changed_internally": client_state_obj.map_download_status = "processing" # Reset temp status

        try:
            server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size)
            if not server_data_chunk: info("Client: Server disconnected during map sync."); map_sync_phase_active = False; break
            client_state_obj.server_state_buffer += server_data_chunk
            decoded_messages, client_state_obj.server_state_buffer = decode_data_stream(client_state_obj.server_state_buffer)
            
            for msg in decoded_messages:
                cmd = msg.get("command")
                # ... (map sync command processing logic as before, calling client_state_obj.map_download_status = "changed_internally" on changes) ...
                # Example for one command:
                if cmd == "set_map":
                    client_state_obj.server_selected_map_name = msg.get("name")
                    info(f"Client: Server map: {client_state_obj.server_selected_map_name}")
                    client_state_obj.map_download_status = "checking"
                    map_file_path = os.path.join(C.MAPS_DIR, (client_state_obj.server_selected_map_name or "") + ".py")
                    if os.path.exists(map_file_path):
                        client_state_obj.map_download_status = "present"
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                    else:
                        client_state_obj.map_download_status = "missing"
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"missing"}))
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"request_map_file", "name":client_state_obj.server_selected_map_name}))
                        client_state_obj.map_download_status = "downloading"; client_state_obj.map_received_bytes = 0; client_state_obj.map_total_size_bytes = 0; client_state_obj.map_file_buffer = b""
                    client_state_obj.map_download_status = "changed_internally" # Signal UI update
                # ... (map_file_info, map_data_chunk, map_transfer_end, map_file_error logic)
                elif cmd == "map_file_info" and client_state_obj.map_download_status=="downloading":
                    client_state_obj.map_total_size_bytes = msg.get("size",0)
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "map_data_chunk" and client_state_obj.map_download_status=="downloading":
                    chunk_data_bytes = msg.get("data","").encode('utf-8')
                    client_state_obj.map_file_buffer += chunk_data_bytes
                    client_state_obj.map_received_bytes = len(client_state_obj.map_file_buffer)
                    if client_state_obj.map_total_size_bytes > 0: client_state_obj.map_download_progress = (client_state_obj.map_received_bytes/client_state_obj.map_total_size_bytes)*100.0
                    # No need to send progress back for now unless server requests it
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "map_transfer_end" and client_state_obj.map_download_status=="downloading":
                    # ... (save map logic as before) ...
                    if client_state_obj.map_received_bytes == client_state_obj.map_total_size_bytes:
                        map_file_to_save = os.path.join(C.MAPS_DIR, (client_state_obj.server_selected_map_name or "") + ".py")
                        try:
                            if not os.path.exists(C.MAPS_DIR): os.makedirs(C.MAPS_DIR)
                            with open(map_file_to_save, "wb") as f: f.write(client_state_obj.map_file_buffer)
                            info(f"Client: Map '{client_state_obj.server_selected_map_name}' saved.")
                            client_state_obj.map_download_status = "present"; importlib.invalidate_caches()
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                        except Exception as e_save: error(f"Client Error: Failed to save map: {e_save}"); client_state_obj.map_download_status="error"
                    else: error("Client Error: Map download mismatch."); client_state_obj.map_download_status="error"
                    client_state_obj.map_download_status = "changed_internally"

                elif cmd == "start_game_now":
                    if client_state_obj.map_download_status == "present":
                        info(f"Client: Received start_game_now. Map present. Proceeding."); map_sync_phase_active = False
                        # if ui_status_update_callback: ui_status_update_callback("game_starting", "Map ready, starting game...", 100.0) # Signal game start
                    else: info(f"Client: start_game_now received, but map status is '{client_state_obj.map_download_status}'. Waiting.")
        except socket.timeout: pass
        except socket.error as e_sock_map: error(f"Client: Socket error during map sync: {e_sock_map}."); map_sync_phase_active=False; break
        except Exception as e_map_sync: error(f"Client: Error during map sync: {e_map_sync}", exc_info=True); map_sync_phase_active=False; break
        
        # Main Qt loop will handle its own timing for UI responsiveness
        time.sleep(0.01) # Small sleep to yield CPU

    if not client_state_obj.app_running or client_state_obj.map_download_status != "present":
        info(f"Client: Exiting (app closed or map not ready: {client_state_obj.map_download_status}).")
        if ui_status_update_callback: ui_status_update_callback("Error", f"Map sync failed: {client_state_obj.map_download_status}", -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return

    # --- Initialize Game Elements (after successful map sync) ---
    info(f"Client: Map '{client_state_obj.server_selected_map_name}' present. Initializing game elements...")
    if ui_status_update_callback: ui_status_update_callback("Loading Level...", f"Initializing '{client_state_obj.server_selected_map_name}'", 100.0)
    
    # Game setup now uses screen dimensions from the main app, not Pygame screen
    screen_width_main_app, screen_height_main_app = C.TILE_SIZE*20, C.TILE_SIZE*15 # Placeholder, main app provides this
    # In real app, these dimensions would be passed in or obtained from a shared config/state.
    # For now, using placeholders.
    if 'main_app_screen_width' in game_elements_ref and 'main_app_screen_height' in game_elements_ref:
         screen_width_main_app = game_elements_ref['main_app_screen_width']
         screen_height_main_app = game_elements_ref['main_app_screen_height']


    updated_game_elements = initialize_game_elements(
        screen_width_main_app, screen_height_main_app, "join_ip", # or "join_lan"
        game_elements_ref, client_state_obj.server_selected_map_name
    )
    if updated_game_elements is None:
        critical_msg = f"Client CRITICAL: Failed to init game elements with map '{client_state_obj.server_selected_map_name}'."
        critical(critical_msg)
        if ui_status_update_callback: ui_status_update_callback("Error", critical_msg, -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return
    game_elements_ref.update(updated_game_elements)
    
    # Camera setup (if exists)
    camera_client = game_elements_ref.get("camera")
    if camera_client:
        camera_client.set_screen_dimensions(screen_width_main_app, screen_height_main_app)
        if "level_pixel_width" in game_elements_ref: # Check if map loaded these
            camera_client.set_level_dimensions(
                game_elements_ref["level_pixel_width"], 
                game_elements_ref["level_min_y_absolute"], 
                game_elements_ref["level_max_y_absolute"]
            )

    p2_controlled_by_client = game_elements_ref.get("player2")
    p1_remote_on_client = game_elements_ref.get("player1")
    
    # --- Main Client Game Loop (driven by main Qt QTimer) ---
    # This loop is now conceptual. The actual "loop" is one tick of the main app's QTimer.
    # This function would now return, and the main app calls an `update_client_tick` function.
    # For this refactor, we keep the while loop structure but note it's conceptual.
    
    client_game_active = True
    client_state_obj.server_state_buffer = b"" 
    client_state_obj.last_received_server_state = None
    
    # if ui_status_update_callback: ui_status_update_callback("game_active", "Game Started!", -1) # Signal game started

    # This while loop will be replaced by a single tick function called by the main Qt QTimer
    # For now, it simulates the continuous game processing.
    while client_game_active and client_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback() # Main app processes Qt events
        if not client_state_obj.app_running: break # Main app can stop this

        # dt_sec would be passed by the main QTimer's loop
        # now_ticks_client would be get_current_ticks()

        # Get P2 input state (this needs to come from the main Qt application's input handling)
        p2_input_payload_for_server: Dict[str, Any] = {}
        if get_input_snapshot_callback:
            p2_input_payload_for_server = get_input_snapshot_callback(p2_controlled_by_client) # Pass P2 instance
        
        # Local client-side actions based on P2's input snapshot
        if p2_input_payload_for_server.get("pause_event"): # Assuming input snapshot includes discrete events
            info("Client: P2 local pause action detected. Signaling server and exiting local game loop.")
            client_game_active = False # This will signal the outer loop in main.py to stop client mode

        # Global client actions (like K_RETURN on game over)
        # These would also be signaled from the main Qt event handler
        # Example: if main_app.global_reset_requested_by_qt_event:
        #              p2_input_payload_for_server['action_reset_global'] = True
        #              main_app.global_reset_requested_by_qt_event = False


        if not client_state_obj.app_running or not client_game_active: break
        
        # Send P2's input state to server
        if client_state_obj.client_tcp_socket and p2_input_payload_for_server:
            encoded_payload = encode_data({"input": p2_input_payload_for_server})
            if encoded_payload:
                try: client_state_obj.client_tcp_socket.sendall(encoded_payload)
                except socket.error as e_send: error(f"Client: Send to server failed: {e_send}."); client_game_active=False; break
        
        # Receive and process server state
        if client_state_obj.client_tcp_socket:
            try:
                server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size * 2)
                if not server_data_chunk: info("Client: Server disconnected (empty recv)."); client_game_active=False; break
                client_state_obj.server_state_buffer += server_data_chunk
                decoded_server_states, client_state_obj.server_state_buffer = decode_data_stream(client_state_obj.server_state_buffer)
                if decoded_server_states:
                    client_state_obj.last_received_server_state = decoded_server_states[-1]
                    set_network_game_state(client_state_obj.last_received_server_state, game_elements_ref, client_player_id=2)
            except socket.timeout: pass 
            except socket.error as e_recv: error(f"Client: Recv error: {e_recv}."); client_game_active=False; break
            except Exception as e_proc_serv: error(f"Client: Error processing server data: {e_proc_serv}", exc_info=True); client_game_active=False; break
        
        # Animate local representations based on received state (these are now QPixmap based)
        # The actual drawing is handled by GameSceneWidget. This just updates animation frames.
        if p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and hasattr(p1_remote_on_client,'animate'): p1_remote_on_client.animate()
        if p2_controlled_by_client and p2_controlled_by_client.alive() and p2_controlled_by_client._valid_init and hasattr(p2_controlled_by_client,'animate'): p2_controlled_by_client.animate()
        
        for enemy_client in game_elements_ref.get("enemy_list",[]):
            if enemy_client.alive() and enemy_client._valid_init and hasattr(enemy_client,'animate'): enemy_client.animate()
            if enemy_client.is_dead and hasattr(enemy_client,'death_animation_finished') and enemy_client.death_animation_finished and enemy_client.alive():
                enemy_client.kill() # Mark as not alive for rendering list
        
        for proj_client in game_elements_ref.get("projectiles_list",[]): # Now a list
            if proj_client.alive() and hasattr(proj_client,'animate'): proj_client.animate()
        
        for statue_obj in game_elements_ref.get("statue_objects",[]):
            if hasattr(statue_obj,'update'): statue_obj.update(0.016) # Pass dummy dt_sec or server-synced time

        # Collectibles list update (if any animation or timed logic)
        for collectible in game_elements_ref.get("collectible_list", []):
            if hasattr(collectible, 'update'): collectible.update(0.016) # Pass dummy dt_sec

        # Camera update (client P2 is usually the focus)
        if camera_client:
            cam_focus_target_client = p2_controlled_by_client if (p2_controlled_by_client and p2_controlled_by_client.alive() and p2_controlled_by_client._valid_init and not p2_controlled_by_client.is_dead and not getattr(p2_controlled_by_client,'is_petrified',False)) else \
                                  (p1_remote_on_client if (p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and not p1_remote_on_client.is_dead and not getattr(p1_remote_on_client,'is_petrified',False)) else \
                                  (p2_controlled_by_client if p2_controlled_by_client and p2_controlled_by_client.alive() else p1_remote_on_client)) # Fallbacks
            
            if cam_focus_target_client: camera_client.update(cam_focus_target_client)
            else: camera_client.static_update()
            
        # The main Qt loop will call GameSceneWidget.update() to trigger repaint
        time.sleep(1.0 / C.FPS) # Simulate game tick delay; Qt QTimer handles this in real app

    # --- End of Client Game Loop ---
    info("Client: Exiting active game simulation.")
    if client_state_obj.client_tcp_socket:
        info("Client: Closing TCP socket to server.")
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    
    # if ui_status_update_callback: ui_status_update_callback("disconnected", "Disconnected from server.", -1) # Signal disconnect
    info("Client: Client mode finished and returned to caller.")


#################### END OF FILE: client_logic.py ####################