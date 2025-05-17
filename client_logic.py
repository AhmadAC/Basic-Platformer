# client_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.5 (Pause action returns to main menu)
Handles client-side game logic, connection to server, and LAN discovery.
"""
import pygame
import socket
import time
import traceback
import os
import importlib
from typing import Optional, Dict, Any # Added Dict, Any

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
from game_state_manager import set_network_game_state
from enemy import Enemy
import game_ui 
from game_setup import initialize_game_elements
from items import Chest
import config as game_config # For P2 key map if client is also P2

class ClientState:
    def __init__(self):
        self.client_tcp_socket = None
        self.server_state_buffer = b""
        self.last_received_server_state = None
        self.app_running = True
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.client_search_timeout_s = getattr(C, "CLIENT_SEARCH_TIMEOUT_S", 5.0)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)
        self.server_selected_map_name: Optional[str] = None
        self.map_download_status: str = "unknown"
        self.map_download_progress: float = 0.0
        self.map_total_size_bytes: int = 0
        self.map_received_bytes: int = 0
        self.map_file_buffer: bytes = b""


def find_server_on_lan(screen: pygame.Surface, fonts: dict,
                       clock_obj: pygame.time.Clock, client_state_obj: ClientState):
    debug("Client (find_server_on_lan): Starting LAN server search.")
    pygame.display.set_caption("Platformer - Searching for Server on LAN...")
    current_width, current_height = screen.get_size()
    default_font_large = pygame.font.Font(None, 30) if pygame.font.get_init() else None
    search_text_surf = (fonts.get("large") or default_font_large).render( # type: ignore
        "Searching for server on LAN...", True, C.WHITE
    )
    listen_socket, found_server_ip, found_server_port = None, None, None
    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', client_state_obj.discovery_port_udp))
        listen_socket.settimeout(0.5)
        debug(f"Client (find_server_on_lan): UDP listen socket bound to port {client_state_obj.discovery_port_udp}.")
    except socket.error as e_socket:
        error(f"Client Error: Failed to bind UDP listen socket on port {client_state_obj.discovery_port_udp}: {e_socket}")
        screen.fill(C.BLACK)
        err_msg = f"Error: Cannot listen on UDP port {client_state_obj.discovery_port_udp}."
        font_small_err = fonts.get("small") or (pygame.font.Font(None, 24) if pygame.font.get_init() else None)
        if font_small_err:
            err_surf = font_small_err.render(err_msg, True, C.RED)
            screen.blit(err_surf, err_surf.get_rect(center=(current_width//2, current_height // 2)))
        pygame.display.flip(); time.sleep(4)
        return None, None
    start_search_time = time.time()
    client_local_ip = get_local_ip()
    debug(f"Client (find_server_on_lan): Searching (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.")
    while time.time() - start_search_time < client_state_obj.client_search_timeout_s and \
          client_state_obj.app_running and not found_server_ip:
        for event in pygame.event.get():
             if event.type == pygame.QUIT: client_state_obj.app_running = False; break
             if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width,current_height=max(320,event.w),max(240,event.h)
                    screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    search_text_surf = (fonts.get("large") or default_font_large).render("Searching...", True, C.WHITE) # type: ignore
             if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                 debug("Client (find_server_on_lan): LAN server search cancelled by user.")
                 if listen_socket: listen_socket.close()
                 return None, None
        if not client_state_obj.app_running: break
        screen.fill(C.BLACK)
        screen.blit(search_text_surf, search_text_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip(); clock_obj.tick(10)
        try:
            raw_udp_data, sender_address = listen_socket.recvfrom(client_state_obj.buffer_size)
            decoded_messages_list, _ = decode_data_stream(raw_udp_data)
            if not decoded_messages_list: continue
            decoded_udp_message = decoded_messages_list[0]
            if (isinstance(decoded_udp_message, dict) and
                decoded_udp_message.get("service") == client_state_obj.service_name and
                isinstance(decoded_udp_message.get("tcp_ip"), str) and
                isinstance(decoded_udp_message.get("tcp_port"), int)):
                server_ip = decoded_udp_message["tcp_ip"]; server_port = decoded_udp_message["tcp_port"]
                info(f"Client (find_server_on_lan): Found server '{client_state_obj.service_name}' at {server_ip}:{server_port}")
                found_server_ip, found_server_port = server_ip, server_port
        except socket.timeout: continue
        except Exception as e_udp: error(f"Client: Error processing UDP broadcast: {e_udp}", exc_info=True)
    if listen_socket: listen_socket.close()
    if not found_server_ip and client_state_obj.app_running:
        info(f"Client (find_server_on_lan): No server for '{client_state_obj.service_name}' after timeout.")
        screen.fill(C.BLACK)
        font_large_fail = fonts.get("large") or default_font_large
        if font_large_fail:
            fail_surf = font_large_fail.render("Server Not Found!", True, C.RED)
            screen.blit(fail_surf, fail_surf.get_rect(center=(current_width//2, current_height//2)))
        pygame.display.flip(); time.sleep(3)
    elif not client_state_obj.app_running: info("Client (find_server_on_lan): Search aborted (app quitting).")
    return found_server_ip, found_server_port


def run_client_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                    fonts: dict, game_elements_ref: dict,
                    client_state_obj: ClientState, target_ip_port_str: Optional[str] = None):
    info("Client (run_client_mode): Entering client mode.")
    client_state_obj.app_running = True
    server_ip_to_connect, server_port_to_connect = None, C.SERVER_PORT_TCP
    if target_ip_port_str:
        info(f"Client (run_client_mode): Direct IP specified: {target_ip_port_str}")
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1:
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError: warning(f"Client: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else:
        info("Client (run_client_mode): No direct IP, attempting LAN discovery.")
        server_ip_to_connect, found_server_port = find_server_on_lan(screen, fonts, clock, client_state_obj)
        if found_server_port: server_port_to_connect = found_server_port
    if not server_ip_to_connect or not client_state_obj.app_running:
        info(f"Client: Exiting client mode (no server target or app closed).")
        return
    if client_state_obj.client_tcp_socket:
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection_succeeded, connection_error_msg = False, "Unknown Connection Error"
    try:
        info(f"Client: Attempting connection to server at {server_ip_to_connect}:{server_port_to_connect}...")
        pygame.display.set_caption(f"Platformer - Connecting to {server_ip_to_connect}...")
        game_ui.draw_download_dialog(screen, fonts, "Connecting...", f"{server_ip_to_connect}:{server_port_to_connect}", 0)
        client_state_obj.client_tcp_socket.settimeout(10.0)
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        client_state_obj.client_tcp_socket.settimeout(0.05) # Non-blocking for game loop
        info("Client: TCP Connection to server successful!")
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e_sock: connection_error_msg = f"Connection Error ({e_sock.strerror if hasattr(e_sock, 'strerror') else e_sock})"
    except Exception as e_conn: connection_error_msg = f"Unexpected Connection Error: {e_conn}"
    if not connection_succeeded:
        error(f"Client: Failed to connect: {connection_error_msg}")
        game_ui.draw_download_dialog(screen, fonts, "Connection Failed", connection_error_msg, -1)
        time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return
    
    # --- Map Synchronization Phase ---
    client_state_obj.map_download_status = "waiting_map_info"; client_state_obj.server_state_buffer = b""
    map_sync_phase_active = True
    while map_sync_phase_active and client_state_obj.app_running:
        current_width, current_height = screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: client_state_obj.app_running = False; map_sync_phase_active = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width,current_height = max(320,event.w),max(240,event.h)
                screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: client_state_obj.app_running = False; map_sync_phase_active = False; break
        if not client_state_obj.app_running: break
        
        dialog_title = "Synchronizing"; dialog_msg_map = "Waiting for map info..."; dialog_prog_map = -1.0 # Use float
        if client_state_obj.map_download_status == "checking": dialog_msg_map = f"Checking for map: {client_state_obj.server_selected_map_name}..."
        elif client_state_obj.map_download_status == "missing": dialog_msg_map = f"Map '{client_state_obj.server_selected_map_name}' missing. Requesting..."
        elif client_state_obj.map_download_status == "downloading":
            dialog_title = f"Downloading: {client_state_obj.server_selected_map_name}"
            dialog_msg_map = f"{client_state_obj.map_received_bytes/1024.0:.1f}/{client_state_obj.map_total_size_bytes/1024.0:.1f}KB"
            dialog_prog_map = client_state_obj.map_download_progress if client_state_obj.map_total_size_bytes > 0 else 0.0
        elif client_state_obj.map_download_status == "present": dialog_msg_map = f"Map '{client_state_obj.server_selected_map_name}' ready. Waiting..."; dialog_prog_map = 100.0
        elif client_state_obj.map_download_status == "error": dialog_title = "Map Error"; dialog_msg_map = f"Failed map: {client_state_obj.server_selected_map_name}"; dialog_prog_map = -1.0
        
        game_ui.draw_download_dialog(screen, fonts, dialog_title, dialog_msg_map, dialog_prog_map)
        
        try:
            server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size)
            if not server_data_chunk: info("Client: Server disconnected during map sync."); map_sync_phase_active = False; break
            client_state_obj.server_state_buffer += server_data_chunk
            decoded_messages, client_state_obj.server_state_buffer = decode_data_stream(client_state_obj.server_state_buffer)
            
            for msg in decoded_messages:
                cmd = msg.get("command")
                if cmd == "set_map":
                    client_state_obj.server_selected_map_name = msg.get("name")
                    info(f"Client: Server map: {client_state_obj.server_selected_map_name}")
                    client_state_obj.map_download_status = "checking"
                    map_file_path = os.path.join(C.MAPS_DIR, client_state_obj.server_selected_map_name + ".py")
                    debug(f"Client: Checking local map path: {map_file_path}")
                    if os.path.exists(map_file_path):
                        info(f"Client: Map '{client_state_obj.server_selected_map_name}' found locally.")
                        client_state_obj.map_download_status = "present"
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                    else:
                        info(f"Client: Map '{client_state_obj.server_selected_map_name}' MISSING from '{map_file_path}'. Requesting.")
                        client_state_obj.map_download_status = "missing"
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"missing"}))
                        client_state_obj.client_tcp_socket.sendall(encode_data({"command":"request_map_file", "name":client_state_obj.server_selected_map_name}))
                        client_state_obj.map_download_status = "downloading"; client_state_obj.map_received_bytes = 0
                        client_state_obj.map_total_size_bytes = 0; client_state_obj.map_file_buffer = b""
                elif cmd == "map_file_info" and client_state_obj.map_download_status=="downloading":
                    client_state_obj.map_total_size_bytes = msg.get("size",0)
                    debug(f"Client: Expecting map file size {client_state_obj.map_total_size_bytes} bytes.")
                elif cmd == "map_data_chunk" and client_state_obj.map_download_status=="downloading":
                    chunk_data_bytes = msg.get("data","").encode('utf-8') # Server sends string, client encodes
                    client_state_obj.map_file_buffer += chunk_data_bytes
                    client_state_obj.map_received_bytes = len(client_state_obj.map_file_buffer)
                    if client_state_obj.map_total_size_bytes > 0: client_state_obj.map_download_progress = (client_state_obj.map_received_bytes/client_state_obj.map_total_size_bytes)*100.0
                    client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_download_progress", "progress":client_state_obj.map_download_progress}))
                elif cmd == "map_transfer_end" and client_state_obj.map_download_status=="downloading":
                    if client_state_obj.map_received_bytes == client_state_obj.map_total_size_bytes:
                        map_file_to_save = os.path.join(C.MAPS_DIR, client_state_obj.server_selected_map_name + ".py")
                        try:
                            if not os.path.exists(C.MAPS_DIR): debug(f"Client: Maps dir '{C.MAPS_DIR}' missing. Creating."); os.makedirs(C.MAPS_DIR)
                            with open(map_file_to_save, "wb") as f: f.write(client_state_obj.map_file_buffer) # Write bytes
                            info(f"Client: Map '{client_state_obj.server_selected_map_name}' saved to '{map_file_to_save}'.")
                            client_state_obj.map_download_status = "present"; importlib.invalidate_caches()
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                        except Exception as e_save: error(f"Client Error: Failed to save map '{map_file_to_save}': {e_save}", exc_info=True); client_state_obj.map_download_status="error"
                    else: error(f"Client Error: Map download mismatch. Expected {client_state_obj.map_total_size_bytes}, got {client_state_obj.map_received_bytes}."); client_state_obj.map_download_status="error"
                elif cmd == "map_file_error":
                    error(f"Client: Server reported map error '{msg.get('name')}': {msg.get('reason', 'unknown')}")
                    client_state_obj.map_download_status="error"; map_sync_phase_active=False
                elif cmd == "start_game_now":
                    if client_state_obj.map_download_status == "present": info(f"Client: Start_game_now received. Map present. Proceeding."); map_sync_phase_active=False
                    else: info(f"Client: Start_game_now, but map status '{client_state_obj.map_download_status}'. Waiting.")
        except socket.timeout: pass
        except socket.error as e_sock_map: error(f"Client: Socket error during map sync: {e_sock_map}."); map_sync_phase_active=False; break
        except Exception as e_map_sync: error(f"Client: Error during map sync data processing: {e_map_sync}", exc_info=True); map_sync_phase_active=False; break
        clock.tick(C.FPS) # Keep UI responsive
        
    if not client_state_obj.app_running or client_state_obj.map_download_status != "present":
        info(f"Client: Exiting (app closed or map not ready: {client_state_obj.map_download_status}).")
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return

    # --- Initialize Game Elements (after successful map sync) ---
    info(f"Client: Map '{client_state_obj.server_selected_map_name}' present. Initializing game elements...")
    current_screen_width, current_screen_height = screen.get_size()
    updated_game_elements = initialize_game_elements(
        current_screen_width, current_screen_height, "join_ip", game_elements_ref, 
        client_state_obj.server_selected_map_name
    )
    if updated_game_elements is None:
        critical(f"Client CRITICAL: Failed to init game elements with map '{client_state_obj.server_selected_map_name}'.")
        game_ui.draw_download_dialog(screen, fonts, "Error", f"Failed to load map: {client_state_obj.server_selected_map_name}", -1); time.sleep(3)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return
    game_elements_ref.update(updated_game_elements)
    
    if game_elements_ref.get("camera") and "level_pixel_width" in game_elements_ref:
        cam = game_elements_ref["camera"]
        if hasattr(cam, "set_screen_dimensions"): cam.set_screen_dimensions(current_screen_width, current_screen_height)
        if hasattr(cam, "set_level_dimensions"): cam.set_level_dimensions(
            game_elements_ref["level_pixel_width"], 
            game_elements_ref["level_min_y_absolute"], 
            game_elements_ref["level_max_y_absolute"]
        )

    pygame.display.set_caption(f"Platformer - CLIENT (You are P2: {game_config.CURRENT_P2_INPUT_DEVICE} | Harm:H | Heal:G | Reset:P2MappedResetKey/Enter | Weapons: {C.P2_SHADOW_PROJECTILE_KEY % 1000 - C.K_KP0 + 6 if C.K_0 <= C.P2_SHADOW_PROJECTILE_KEY <= C.K_9 else '?'}, {C.P2_GREY_PROJECTILE_KEY % 1000 - C.K_KP0 + 7 if C.K_0 <= C.P2_GREY_PROJECTILE_KEY <= C.K_9 else '?'})")
    
    p2_controlled_by_client = game_elements_ref.get("player2")
    p1_remote_on_client = game_elements_ref.get("player1")

    debug(f"Client: P1 (remote): {p1_remote_on_client}, P2 (local): {p2_controlled_by_client}")
    if p1_remote_on_client: debug(f"Client P1 Valid: {p1_remote_on_client._valid_init if hasattr(p1_remote_on_client, '_valid_init') else 'N/A'}, Pos: {p1_remote_on_client.pos if hasattr(p1_remote_on_client,'pos') else 'N/A'}")
    if p2_controlled_by_client: debug(f"Client P2 Valid: {p2_controlled_by_client._valid_init if hasattr(p2_controlled_by_client, '_valid_init') else 'N/A'}, Pos: {p2_controlled_by_client.pos if hasattr(p2_controlled_by_client,'pos') else 'N/A'}")

    # The client P2 key map should be derived from P2's config settings
    # player.get_input_state_for_network will use P2_MAPPINGS from config.py
    # No need for p2_client_key_map here if player.py handles its own config.

    client_game_active = True
    client_state_obj.server_state_buffer = b"" 
    client_state_obj.last_received_server_state = None
    
    # --- Main Client Game Loop ---
    while client_game_active and client_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0
        now_ticks_client = pygame.time.get_ticks()
        
        server_indicated_game_over = client_state_obj.last_received_server_state and \
                                     client_state_obj.last_received_server_state.get('game_over', False)
        
        pygame_events_client = pygame.event.get()
        keys_pressed_client = pygame.key.get_pressed() # For keyboard based P2 on client

        p2_input_state_for_server: Dict[str, Any] = {} # This will hold all actions from P2
        p2_local_actions: Dict[str, bool] = {}       # Store P2's processed input for local checks

        if p2_controlled_by_client and p2_controlled_by_client._valid_init and \
           hasattr(p2_controlled_by_client, 'get_input_state_for_network'):
            # get_input_state_for_network now correctly uses P2_MAPPINGS from config.py
            # and processes inputs to generate actions like "reset", "pause", "fire_shadow_event", etc.
            p2_input_state_for_server = p2_controlled_by_client.get_input_state_for_network(
                keys_pressed_client, pygame_events_client, game_config.P2_MAPPINGS # Pass P2's current mappings
            )
            p2_local_actions = p2_input_state_for_server # Use the same processed input for local checks

        # Local client-side actions based on P2's processed input
        if p2_local_actions.get("pause"): # Check if P2's processed input contains "pause"
            info("Client: P2 local pause action detected. Signaling server and exiting local game loop.")
            # The "pause" event is already in p2_input_state_for_server to notify the server.
            client_game_active = False 

        # Client-level direct key presses (not tied to P2's character actions, but global client actions)
        client_global_actions_for_server: Dict[str, bool] = {} # For K_RETURN on game over, etc.
        for event in pygame_events_client:
            if event.type == pygame.QUIT: client_game_active = False; client_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width,current_height=max(320,event.w),max(240,event.h)
                screen=pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                if game_elements_ref.get("camera"): game_elements_ref["camera"].set_screen_dimensions(current_width,current_height)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: client_game_active = False # Direct exit
                # Global reset request from client machine (if server says game over)
                if event.key == pygame.K_RETURN and server_indicated_game_over:
                    client_global_actions_for_server['action_reset_global'] = True
                
                # Debug keys for client-side P1/P2 (these don't go to server unless specifically packaged)
                if event.key == pygame.K_h: # P1 Self-harm (client debug)
                    if p1_remote_on_client and hasattr(p1_remote_on_client, 'self_inflict_damage_local_debug'):
                        p1_remote_on_client.self_inflict_damage_local_debug(C.PLAYER_SELF_DAMAGE)
                if event.key == pygame.K_g: # P1 Heal (client debug)
                     if p1_remote_on_client and hasattr(p1_remote_on_client, 'heal_to_full_local_debug'):
                        p1_remote_on_client.heal_to_full_local_debug()
                # Similar for P2 local debugs if needed, but typically P2 actions are sent to server.

        if not client_state_obj.app_running or not client_game_active: break
        
        # Merge global client actions into the payload if any
        if client_global_actions_for_server:
            p2_input_state_for_server.update(client_global_actions_for_server)

        # Send P2's input state (which now includes all actions) to server
        if client_state_obj.client_tcp_socket:
            encoded_payload = encode_data({"input": p2_input_state_for_server})
            if encoded_payload:
                try: client_state_obj.client_tcp_socket.sendall(encoded_payload)
                except socket.error as e_send: error(f"Client: Send to server failed: {e_send}."); client_game_active=False; break
        
        # Receive and process server state
        if client_state_obj.client_tcp_socket:
            try:
                server_data_chunk = client_state_obj.client_tcp_socket.recv(client_state_obj.buffer_size * 2) # Increased buffer slightly
                if not server_data_chunk: info("Client: Server disconnected (empty recv)."); client_game_active=False; break
                client_state_obj.server_state_buffer += server_data_chunk
                decoded_server_states, client_state_obj.server_state_buffer = decode_data_stream(client_state_obj.server_state_buffer)
                if decoded_server_states:
                    client_state_obj.last_received_server_state = decoded_server_states[-1] # Use the latest state
                    set_network_game_state(client_state_obj.last_received_server_state, game_elements_ref, client_player_id=2)
            except socket.timeout: pass # Normal for non-blocking
            except socket.error as e_recv: error(f"Client: Recv error: {e_recv}."); client_game_active=False; break
            except Exception as e_proc_serv: error(f"Client: Error processing server data: {e_proc_serv}", exc_info=True); client_game_active=False; break
        
        # Animate local representations based on received state
        if p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and hasattr(p1_remote_on_client,'animate'): p1_remote_on_client.animate()
        if p2_controlled_by_client and p2_controlled_by_client.alive() and p2_controlled_by_client._valid_init and hasattr(p2_controlled_by_client,'animate'): p2_controlled_by_client.animate()
        
        for enemy_client in game_elements_ref.get("enemy_list",[]):
            if enemy_client.alive() and enemy_client._valid_init and hasattr(enemy_client,'animate'): enemy_client.animate()
            if enemy_client.is_dead and hasattr(enemy_client,'death_animation_finished') and enemy_client.death_animation_finished and enemy_client.alive():
                debug(f"Client: Visually removing enemy {enemy_client.enemy_id} as death anim finished."); enemy_client.kill()
        
        for proj_client in game_elements_ref.get("projectile_sprites",pygame.sprite.Group()):
            if proj_client.alive() and hasattr(proj_client,'animate'): proj_client.animate()
        
        for statue_obj in game_elements_ref.get("statue_objects",[]): # Statues
            if hasattr(statue_obj,'update'): statue_obj.update(dt_sec)
            
        game_elements_ref.get("collectible_sprites",pygame.sprite.Group()).update(dt_sec) # Chests, etc.

        # Camera update
        client_camera = game_elements_ref.get("camera")
        if client_camera:
            cam_focus_target_client = None
            if p2_controlled_by_client and p2_controlled_by_client.alive() and p2_controlled_by_client._valid_init and not p2_controlled_by_client.is_dead and not getattr(p2_controlled_by_client,'is_petrified',False): cam_focus_target_client=p2_controlled_by_client
            elif p1_remote_on_client and p1_remote_on_client.alive() and p1_remote_on_client._valid_init and not p1_remote_on_client.is_dead and not getattr(p1_remote_on_client,'is_petrified',False): cam_focus_target_client=p1_remote_on_client
            elif p2_controlled_by_client and p2_controlled_by_client.alive(): cam_focus_target_client=p2_controlled_by_client # Fallback if dead/petrified
            elif p1_remote_on_client and p1_remote_on_client.alive(): cam_focus_target_client=p1_remote_on_client
            
            if cam_focus_target_client: client_camera.update(cam_focus_target_client)
            else: client_camera.static_update()
            
        # Draw scene
        try:
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_client)
        except Exception as e_draw: error(f"Client draw error: {e_draw}", exc_info=True); client_game_active=False; break
        pygame.display.flip()

    # --- End of Client Game Loop ---
    info("Client: Exiting active game loop.")
    if client_state_obj.client_tcp_socket:
        info("Client: Closing TCP socket to server.")
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    info("Client: Client mode finished and returned to caller.")