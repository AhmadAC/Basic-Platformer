#################### START OF FILE: server_logic.py ####################

# server_logic.py
# -*- coding: utf-8 -*-
"""
Handles server-side game logic, connection management, and broadcasting for PySide6.
UI updates are handled by emitting signals or using callbacks.
"""
# version 2.0.1 (PySide6 Refactor - Added missing Chest import)

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
from items import Chest # Added missing Chest import
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

try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    _start_time_server_logic = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_server_logic) * 1000)

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
        self.current_map_name: Optional[str] = None
        self.client_map_status: str = "unknown"
        self.client_download_progress: float = 0.0
        self.game_start_signaled_to_client: bool = False

def broadcast_presence_thread(server_state_obj: ServerState):
    current_lan_ip = get_local_ip()
    broadcast_message_dict = {"service": server_state_obj.service_name, "tcp_ip": current_lan_ip, "tcp_port": server_state_obj.server_port_tcp}
    broadcast_message_bytes = encode_data(broadcast_message_dict)
    if not broadcast_message_bytes: error("Server Error: Could not encode broadcast message."); return

    try:
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5)
    except socket.error as e: error(f"Server Error: Failed to create UDP broadcast socket: {e}"); server_state_obj.server_udp_socket = None; return

    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    debug(f"Server (broadcast): Broadcasting {broadcast_message_dict} to {broadcast_address}")

    while server_state_obj.app_running:
        try:
            if server_state_obj.server_udp_socket: server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error: pass 
        except Exception as e: warning(f"Server Warning: Broadcast send error: {e}")
        for _ in range(int(server_state_obj.broadcast_interval_s * 10)):
            if not server_state_obj.app_running: break
            time.sleep(0.1)
            
    if server_state_obj.server_udp_socket: server_state_obj.server_udp_socket.close(); server_state_obj.server_udp_socket = None
    debug("Server (broadcast): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr: Any, server_state_obj: ServerState):
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
                    map_file_path = os.path.join(C.MAPS_DIR, (map_name_req or "") + ".py")
                    if os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding="utf-8") as f_map: map_content_str = f_map.read()
                        map_bytes_utf8 = map_content_str.encode('utf-8')
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req, "size": len(map_bytes_utf8)}))
                        offset = 0
                        while offset < len(map_bytes_utf8):
                            chunk_to_send = map_bytes_utf8[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                    else:
                        error(f"Server: Client map request '{map_name_req}' not found at '{map_file_path}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req, "reason": "not_found_on_server"}))
                elif command == "report_download_progress":
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0.0)
                elif "input" in msg:
                    with client_lock:
                        if server_state_obj.client_connection is conn:
                            server_state_obj.client_input_buffer = msg["input"]
        
        except socket.timeout: continue
        except socket.error as e_sock:
            if server_state_obj.app_running: debug(f"Server Handler ({addr}): Socket error: {e_sock}. Client disconnected."); break
        except Exception as e_unexp:
            if server_state_obj.app_running: error(f"Server Handler ({addr}): Unexpected error: {e_unexp}", exc_info=True); break

    with client_lock:
        if server_state_obj.client_connection is conn:
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True}
            server_state_obj.client_map_status = "disconnected"
            server_state_obj.game_start_signaled_to_client = False
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass
    try: conn.close()
    except: pass
    debug(f"Server: Client handler thread for {addr} finished.")


def run_server_mode(server_state_obj: ServerState,
                    game_elements_ref: Dict[str, Any],
                    ui_status_update_callback: Optional[callable] = None, 
                    get_p1_input_snapshot_callback: Optional[callable] = None, 
                    process_qt_events_callback: Optional[callable] = None 
                    ):
    debug("ServerLogic: Entering run_server_mode.")
    server_state_obj.app_running = True
    
    if server_state_obj.current_map_name is None:
        critical("CRITICAL SERVER: current_map_name is None. Cannot host."); return

    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("ServerLogic: Starting broadcast presence thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()

    if server_state_obj.server_tcp_socket:
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1)
        server_state_obj.server_tcp_socket.settimeout(1.0)
        debug(f"ServerLogic: TCP socket listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e_bind:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e_bind}")
        temp_app_running = server_state_obj.app_running; server_state_obj.app_running = False
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        server_state_obj.app_running = temp_app_running
        return

    debug("ServerLogic: Waiting for Player 2 and map sync...")
    with client_lock:
        server_state_obj.client_map_status = "unknown"; server_state_obj.client_download_progress = 0.0
        server_state_obj.game_start_signaled_to_client = False; server_state_obj.client_connection = None

    client_sync_wait_active = True
    last_ui_cb_time = 0
    while client_sync_wait_active and server_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback()
        if not server_state_obj.app_running: break

        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock:
                    server_state_obj.client_connection = temp_conn; server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {}; server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False
                debug(f"ServerLogic: Accepted client from {temp_addr}")
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    server_state_obj.client_handler_thread.join(timeout=0.1)
                server_state_obj.client_handler_thread = threading.Thread(target=handle_client_connection_thread, args=(temp_conn, temp_addr, server_state_obj), daemon=True)
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass
            except Exception as e: error(f"ServerLogic: Error accepting client: {e}", exc_info=True)
        
        if ui_status_update_callback and (time.monotonic() - last_ui_cb_time > 0.2):
            title, msg, prog = "Server Hosting", "Waiting for Player 2...", -1.0
            with client_lock:
                if server_state_obj.client_connection:
                    client_ip = server_state_obj.client_address[0] if server_state_obj.client_address else 'Unknown'
                    status = server_state_obj.client_map_status
                    map_name = server_state_obj.current_map_name or "map"
                    prog = server_state_obj.client_download_progress
                    if status == "waiting_client_report": msg = f"P2 ({client_ip}) connected. Syncing..."
                    elif status == "missing": msg = f"P2 missing '{map_name}'. Sending..."; prog = max(0,prog) 
                    elif status == "downloading_ack": msg = f"P2 downloading '{map_name}' ({prog:.0f}%)..."; prog = max(0,prog)
                    elif status == "present": msg = f"P2 has '{map_name}'. Ready."; prog = 100.0
                    if server_state_obj.game_start_signaled_to_client: client_sync_wait_active = False
                    elif status == "disconnected": msg = "P2 disconnected. Waiting..."; server_state_obj.client_connection = None; prog = -1.0
            ui_status_update_callback(title, msg, prog); last_ui_cb_time = time.monotonic()
        time.sleep(0.01)

    if not server_state_obj.app_running or server_state_obj.client_connection is None or server_state_obj.client_map_status != "present":
        debug(f"ServerLogic: Exiting client sync wait. AppRunning: {server_state_obj.app_running}, ClientConn: {server_state_obj.client_connection is not None}, MapStatus: {server_state_obj.client_map_status}")
        server_state_obj.app_running = False 
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return

    debug(f"ServerLogic: Client synced. Starting game loop...")
    p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2")
    server_game_active = True
    p1_action_events: Dict[str, bool] = {} 

    while server_game_active and server_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback()
        if not server_state_obj.app_running: break

        dt_sec = 1.0 / C.FPS 
        p1_action_events_current_frame: Dict[str, bool] = {} # Events specific to this frame for P1
        if p1 and p1._valid_init and get_p1_input_snapshot_callback:
            # get_p1_input_snapshot_callback is expected to get events from Qt for P1
            # and pass them to player.process_input (which is now Qt-based)
            # This callback itself would call player.process_input internally.
            p1_action_events_current_frame = get_p1_input_snapshot_callback(p1, game_elements_ref.get("platforms_list", []))

            if p1_action_events_current_frame.get("pause"): server_game_active = False; info("Server: P1 pause. Returning to menu.")
            if p1_action_events_current_frame.get("reset"): 
                 info("Server: P1 (host) reset action.")
                 game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                 if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                 if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if not server_game_active: break

        p2_network_input: Optional[Dict[str, Any]] = None
        with client_lock:
            if server_state_obj.client_input_buffer:
                p2_network_input = server_state_obj.client_input_buffer.copy()
                server_state_obj.client_input_buffer.clear()
                if p2_network_input.get("disconnect"): server_game_active = False; server_state_obj.client_connection = None; break
                if p2_network_input.get("pause", False): server_game_active = False; info("Server: Client P2 pause.")
                if p2_network_input.get("reset", False) or p2_network_input.get("action_reset_global", False):
                    is_p1_game_over = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or p1.death_animation_finished)) or (not p1 or not p1._valid_init)
                    if is_p1_game_over:
                        info("Server: Client P2 reset & P1 game over. Resetting state.")
                        game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                        if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                        if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if p2 and p2._valid_init and p2_network_input and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input)
        
        if p1 and p1._valid_init:
            other_players_p1 = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref
            p1.update(dt_sec, game_elements_ref.get("platforms_list", []), game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), other_players_p1, game_elements_ref.get("enemy_list", []))
        if p2 and p2._valid_init:
            other_players_p2 = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platforms_list", []), game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), other_players_p2, game_elements_ref.get("enemy_list", []))
        
        active_players_ai = [char for char in [p1,p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy in list(game_elements_ref.get("enemy_list", [])): 
            if enemy._valid_init:
                if hasattr(enemy, 'is_petrified') and enemy.is_petrified: 
                    if hasattr(enemy, 'update_enemy_status_effects'): enemy.update_enemy_status_effects(get_current_ticks(), game_elements_ref.get("platforms_list",[]))
                    enemy.animate()
                    if enemy.is_dead and enemy.death_animation_finished and enemy.alive(): enemy.kill()
                    continue
                enemy.update(dt_sec, active_players_ai, game_elements_ref.get("platforms_list", []), 
                             game_elements_ref.get("hazards_list", []), game_elements_ref.get("enemy_list", []))
                if enemy.is_dead and hasattr(enemy, 'death_animation_finished') and enemy.death_animation_finished and enemy.alive():
                    enemy.kill()
        
        for statue in game_elements_ref.get("statue_objects", []):
            if hasattr(statue, 'update'): statue.update(dt_sec)
            
        hittable_targets_server = [] 
        if p1 and p1.alive() and p1._valid_init and not getattr(p1,'is_petrified',False): hittable_targets_server.append(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2,'is_petrified',False): hittable_targets_server.append(p2)
        for enemy_target in game_elements_ref.get("enemy_list",[]):
            if enemy_target.alive() and enemy_target._valid_init and not getattr(enemy_target,'is_petrified',False): hittable_targets_server.append(enemy_target)
        for statue_target in game_elements_ref.get("statue_objects",[]):
            if statue_target.alive() and not getattr(statue_target,'is_smashed',False) : hittable_targets_server.append(statue_target)
        
        for proj in game_elements_ref.get("projectiles_list", []):
            if hasattr(proj, 'update'): proj.update(dt_sec, game_elements_ref.get("platforms_list",[]), hittable_targets_server)

        for collectible in game_elements_ref.get("collectible_list", []):
            if hasattr(collectible, 'update'): collectible.update(dt_sec)

        chest_server = game_elements_ref.get("current_chest")
        if isinstance(chest_server, Chest) and chest_server.alive() and not chest_server.is_collected_flag_internal: # Check class
            interactor = None
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1,'is_petrified',False) and \
               p1.rect.intersects(chest_server.rect) and p1_action_events_current_frame.get("interact", False): # Use current frame's events
                interactor = p1
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2,'is_petrified',False) and \
                 p2.rect.intersects(chest_server.rect) and \
                 p2_network_input and p2_network_input.get("interact_pressed_event", False):
                interactor = p2
            if interactor: chest_server.collect(interactor)
        
        camera_server = game_elements_ref.get("camera")
        if camera_server:
            focus_target = p1 if (p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False)) else \
                           (p2 if (p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False)) else \
                           (p1 if p1 and p1.alive() else p2))
            if focus_target: camera_server.update(focus_target)
            else: camera_server.static_update()
            
        if server_state_obj.client_connection:
            net_state = get_network_game_state(game_elements_ref)
            encoded_net_state = encode_data(net_state)
            if encoded_net_state:
                try: server_state_obj.client_connection.sendall(encoded_net_state)
                except socket.error as e: debug(f"Server: Send state failed: {e}."); server_game_active = False; server_state_obj.client_connection = None; break
        
        # Server's local rendering is now handled by the main Qt app's GameSceneWidget
        # The main Qt loop will call its update method.
        # We simulate the tick delay here for headless operation; Qt QTimer would handle this.
        current_loop_end_time = time.monotonic()
        time_to_sleep = (1.0 / C.FPS) - (current_loop_end_time - (get_current_ticks()/1000.0)) # This is not quite right for precise timing
        # A more accurate way for a non-GUI server loop:
        # frame_start_time = time.monotonic()
        # ... game logic ...
        # time_spent = time.monotonic() - frame_start_time
        # time.sleep(max(0, (1.0 / C.FPS) - time_spent))
        time.sleep(max(0, time_to_sleep if time_to_sleep > -0.5 else 0.016)) # Ensure sleep is not negative due to timer drift


    debug("ServerLogic: Exiting server game active loop.")
    connection_to_close = None
    with client_lock:
        if server_state_obj.client_connection: connection_to_close = server_state_obj.client_connection; server_state_obj.client_connection = None
    if connection_to_close:
        try: connection_to_close.shutdown(socket.SHUT_RDWR)
        except: pass
        try: connection_to_close.close()
        except: pass
    if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
    debug("ServerLogic: Server mode finished.")

#################### END OF FILE: server_logic.py ####################