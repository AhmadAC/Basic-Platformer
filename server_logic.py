# server_logic.py
# -*- coding: utf-8 -*-
"""
Handles server-side game logic, connection management, and broadcasting for PySide6.
UI updates are handled by emitting signals or using callbacks.
"""
# version 2.0.4 (Fixed platforms_list not defined in chest physics, general consistency)
from tiles import Platform, Ladder, Lava, BackgroundTile 
import os
import socket
import threading
import time
import traceback
from typing import Optional, Dict, Any, List

# PySide6 imports (none strictly needed for core server logic, but good for context)
from PySide6.QtCore import QRectF, QPointF # Added for type hints

# Game imports
import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform # Import Platform for type hint if needed by Chest
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
        self.client_ready: bool = False


def broadcast_presence_thread(server_state_obj: ServerState):
    current_lan_ip = get_local_ip()
    broadcast_message_dict = {
        "service": server_state_obj.service_name,
        "tcp_ip": current_lan_ip,
        "tcp_port": server_state_obj.server_port_tcp,
        "map_name": server_state_obj.current_map_name or "Unknown Map"
    }
    broadcast_message_bytes = encode_data(broadcast_message_dict)
    if not broadcast_message_bytes:
        error("Server Error: Could not encode broadcast message for LAN discovery."); return

    try:
        server_state_obj.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_state_obj.server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_state_obj.server_udp_socket.settimeout(0.5)
    except socket.error as e:
        error(f"Server Error: Failed to create UDP broadcast socket: {e}"); server_state_obj.server_udp_socket = None; return

    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    debug(f"Server (broadcast): Broadcasting {broadcast_message_dict} to {broadcast_address}")

    while server_state_obj.app_running:
        if server_state_obj.current_map_name != broadcast_message_dict.get("map_name"):
            broadcast_message_dict["map_name"] = server_state_obj.current_map_name or "Unknown Map"
            new_broadcast_bytes = encode_data(broadcast_message_dict) # Use new variable
            if not new_broadcast_bytes:
                error("Server Error: Could not re-encode broadcast message with updated map name.")
            else:
                broadcast_message_bytes = new_broadcast_bytes # Assign if successful
                debug(f"Server (broadcast): Updated broadcast message with map: {server_state_obj.current_map_name}")

        try:
            if server_state_obj.server_udp_socket:
                server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error as se:
            warning(f"Server Warning: Broadcast send socket error: {se}")
        except Exception as e:
            warning(f"Server Warning: Unexpected broadcast send error: {e}")
        
        sleep_chunk = 0.1
        num_chunks = int(server_state_obj.broadcast_interval_s / sleep_chunk)
        for _ in range(max(1, num_chunks)):
            if not server_state_obj.app_running: break
            time.sleep(sleep_chunk)
            
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close(); server_state_obj.server_udp_socket = None
    debug("Server (broadcast): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr: Any, server_state_obj: ServerState, client_fully_synced_callback: Optional[callable]):
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
            if server_state_obj.client_connection is not conn: debug(f"Server Handler ({addr}): Stale connection for this thread. Exiting."); break
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
                                server_state_obj.client_ready = True 
                                if client_fully_synced_callback: client_fully_synced_callback()
                                debug(f"Server Handler ({addr}): Client has map. Sent start_game_now. Client marked as ready.")
                elif command == "request_map_file":
                    map_name_req = msg.get("name")
                    debug(f"Server Handler ({addr}): Client requested map: '{map_name_req}'")
                    maps_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
                    if not os.path.isabs(maps_dir_abs):
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
                        maps_dir_abs = os.path.join(project_root, maps_dir_abs)

                    map_file_path = os.path.join(maps_dir_abs, (map_name_req or "") + ".py") 
                    if os.path.exists(map_file_path):
                        with open(map_file_path, "r", encoding="utf-8") as f_map: map_content_str = f_map.read()
                        map_bytes_utf8 = map_content_str.encode('utf-8')
                        conn.sendall(encode_data({"command": "map_file_info", "name": map_name_req, "size": len(map_bytes_utf8)}))
                        offset = 0
                        while offset < len(map_bytes_utf8):
                            chunk_to_send_bytes = map_bytes_utf8[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send_bytes.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send_bytes)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                        debug(f"Server Handler ({addr}): Map '{map_name_req}' transfer complete.")
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
            if server_state_obj.app_running: debug(f"Server Handler ({addr}): Socket error: {e_sock}. Client likely disconnected."); break
        except Exception as e_unexp:
            if server_state_obj.app_running: error(f"Server Handler ({addr}): Unexpected error: {e_unexp}", exc_info=True); break

    with client_lock:
        if server_state_obj.client_connection is conn: 
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True} 
            server_state_obj.client_map_status = "disconnected"
            server_state_obj.game_start_signaled_to_client = False
            server_state_obj.client_ready = False 
            debug(f"Server: Client {addr} handler set client_connection to None and client_ready to False.")
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass 
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
    server_state_obj.app_running = True 
    
    if server_state_obj.current_map_name is None:
        map_name_from_ge = game_elements_ref.get('map_name', game_elements_ref.get('loaded_map_name'))
        if map_name_from_ge:
            server_state_obj.current_map_name = map_name_from_ge
            info(f"ServerLogic: current_map_name was None, set from game_elements to '{map_name_from_ge}'")
        else:
            critical("CRITICAL SERVER: current_map_name is None and not found in game_elements. Cannot host."); return

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
        server_state_obj.server_tcp_socket.bind((str(C.SERVER_IP_BIND), server_state_obj.server_port_tcp)) 
        server_state_obj.server_tcp_socket.listen(1) 
        server_state_obj.server_tcp_socket.settimeout(1.0) 
        debug(f"ServerLogic: TCP socket listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e_bind:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e_bind}")
        _temp_app_running_state = server_state_obj.app_running
        server_state_obj.app_running = False 
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive():
            server_state_obj.broadcast_thread.join(timeout=0.5)
        server_state_obj.app_running = _temp_app_running_state 
        return

    debug("ServerLogic: Waiting for Player 2 connection and map synchronization...")
    with client_lock:
        server_state_obj.client_map_status = "unknown"
        server_state_obj.client_download_progress = 0.0
        server_state_obj.game_start_signaled_to_client = False
        server_state_obj.client_connection = None 
        server_state_obj.client_ready = False 

    client_sync_wait_active = True
    last_ui_cb_time = 0.0 
    while client_sync_wait_active and server_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback() 
        if not server_state_obj.app_running: break

        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock: 
                    server_state_obj.client_connection = temp_conn
                    server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {} 
                    server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False 
                    server_state_obj.client_ready = False 
                
                debug(f"ServerLogic: Accepted client connection from {temp_addr}")
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    debug("ServerLogic: Joining previous client handler thread...")
                    server_state_obj.client_handler_thread.join(timeout=0.1) 
                server_state_obj.client_handler_thread = threading.Thread(
                    target=handle_client_connection_thread,
                    args=(temp_conn, temp_addr, server_state_obj, client_fully_synced_callback), 
                    daemon=True
                )
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass 
            except Exception as e_accept:
                error(f"ServerLogic: Error accepting client connection: {e_accept}", exc_info=True)
        
        if ui_status_update_callback and (time.monotonic() - last_ui_cb_time > 0.2):
            title, msg, prog = "Server Hosting", "Waiting for Player 2...", -1.0
            with client_lock: 
                if server_state_obj.client_connection:
                    client_ip_str = str(server_state_obj.client_address[0]) if server_state_obj.client_address else 'Connecting...'
                    current_status = server_state_obj.client_map_status
                    current_map = server_state_obj.current_map_name or "selected map"
                    current_progress = server_state_obj.client_download_progress

                    if current_status == "waiting_client_report": msg = f"Player 2 ({client_ip_str}) connected. Syncing map info..."
                    elif current_status == "missing": msg = f"Player 2 needs '{current_map}'. Sending file..."; prog = max(0.0, current_progress)
                    elif current_status == "downloading_ack" or current_status == "downloading": msg = f"Player 2 downloading '{current_map}' ({current_progress:.0f}%)..."; prog = max(0.0, current_progress)
                    elif current_status == "present": msg = f"Player 2 has '{current_map}'. Ready for game start."; prog = 100.0
                    
                    if server_state_obj.client_ready: 
                        client_sync_wait_active = False 
                    elif current_status == "disconnected": 
                        msg = "Player 2 disconnected. Waiting for a new connection..."
                        server_state_obj.client_connection = None 
                        server_state_obj.client_ready = False
                        prog = -1.0
            ui_status_update_callback(title, msg, prog)
            last_ui_cb_time = time.monotonic()
        
        time.sleep(0.01) 

    if not server_state_obj.app_running or not server_state_obj.client_ready:
        debug(f"ServerLogic: Exiting client sync wait phase. AppRunning: {server_state_obj.app_running}, ClientReady: {server_state_obj.client_ready}")
        server_state_obj.app_running = False 
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return 

    debug(f"ServerLogic: Client synced successfully. Starting main game loop...")
    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")
    server_game_active = True
    
    frame_duration = 1.0 / C.FPS
    
    while server_game_active and server_state_obj.app_running:
        frame_start_time = time.monotonic()

        if process_qt_events_callback: process_qt_events_callback() 
        if not server_state_obj.app_running: break

        dt_sec = frame_duration 

        # --- Fetch platforms_list for this frame ---
        platforms_list_this_frame: List[Any] = game_elements_ref.get("platforms_list", [])


        p1_action_events_current_frame: Dict[str, bool] = {}
        if p1 and hasattr(p1, '_valid_init') and p1._valid_init and get_p1_input_snapshot_callback:
            p1_action_events_current_frame = get_p1_input_snapshot_callback(p1, platforms_list_this_frame)
            if p1_action_events_current_frame.get("pause"):
                server_game_active = False; info("Server: P1 (host) pressed Pause. Ending game mode.")
            if p1_action_events_current_frame.get("reset"):
                 info("Server: P1 (host) requested Reset action."); game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                 if p1 and p1._valid_init and not p1.alive() and p1 not in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                 if p2 and p2._valid_init and not p2.alive() and p2 not in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if not server_game_active: break 

        p2_network_input_data: Optional[Dict[str, Any]] = None
        with client_lock:
            if server_state_obj.client_input_buffer:
                p2_network_input_data = server_state_obj.client_input_buffer.copy()
                server_state_obj.client_input_buffer.clear() 
                if p2_network_input_data.get("disconnect"): 
                    server_game_active = False; server_state_obj.client_connection = None
                    info("Server: Client P2 disconnected via input buffer."); break
                if p2_network_input_data.get("pause", False) or p2_network_input_data.get("pause_event", False): 
                    server_game_active = False; info("Server: Client P2 requested Pause.")
                if p2_network_input_data.get("reset", False) or p2_network_input_data.get("action_reset_global", False):
                    is_p1_truly_dead = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or p1.death_animation_finished)) or (not p1 or not p1._valid_init)
                    if is_p1_truly_dead: 
                        info("Server: Client P2 reset action received and P1 is game over. Resetting state.")
                        game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
                        if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p1)
                        if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_renderable_objects",[]).append(p2)
        if not server_game_active: break

        if p2 and hasattr(p2, '_valid_init') and p2._valid_init and p2_network_input_data and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input_data)
        
        current_game_ticks_val = get_current_ticks_monotonic()

        if p1 and hasattr(p1, '_valid_init') and p1._valid_init:
            other_players_for_p1 = [char for char in [p2] if char and hasattr(char, '_valid_init') and char._valid_init and hasattr(char, 'alive') and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref 
            p1.update(dt_sec, platforms_list_this_frame, 
                      game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), 
                      other_players_for_p1, 
                      game_elements_ref.get("enemy_list", []))

        if p2 and hasattr(p2, '_valid_init') and p2._valid_init:
            other_players_for_p2 = [char for char in [p1] if char and hasattr(char, '_valid_init') and char._valid_init and hasattr(char, 'alive') and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, platforms_list_this_frame, 
                      game_elements_ref.get("ladders_list", []), 
                      game_elements_ref.get("hazards_list", []), 
                      other_players_for_p2, 
                      game_elements_ref.get("enemy_list", []))
        
        active_players_for_ai = [char for char in [p1,p2] if char and hasattr(char,'_valid_init') and char._valid_init and not getattr(char,'is_dead',True) and hasattr(char,'alive') and char.alive()]
        current_enemies_list_ref = game_elements_ref.get("enemy_list", [])
        for enemy_instance in list(current_enemies_list_ref): 
            if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
                if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified: 
                    if hasattr(enemy_instance, 'update_enemy_status_effects'): 
                        enemy_instance.update_enemy_status_effects(current_game_ticks_val, platforms_list_this_frame)
                    if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
                    if getattr(enemy_instance, 'is_dead', False) and getattr(enemy_instance, 'death_animation_finished', False) and enemy_instance.alive():
                        enemy_instance.kill()
                    continue 
                
                enemy_instance.update(dt_sec, active_players_for_ai, 
                                      platforms_list_this_frame, 
                                      game_elements_ref.get("hazards_list", []), 
                                      current_enemies_list_ref) 
                if getattr(enemy_instance, 'is_dead', False) and hasattr(enemy_instance, 'death_animation_finished') and enemy_instance.death_animation_finished and enemy_instance.alive():
                    enemy_instance.kill()
        
        game_elements_ref["enemy_list"][:] = [e for e in current_enemies_list_ref if hasattr(e, 'alive') and e.alive()]

        current_statue_list_ref = game_elements_ref.get("statue_objects", [])
        for statue_obj in list(current_statue_list_ref):
            if hasattr(statue_obj, 'update'): statue_obj.update(dt_sec)
            if not (hasattr(statue_obj, 'alive') and statue_obj.alive()):
                if statue_obj in current_statue_list_ref: current_statue_list_ref.remove(statue_obj)
            
        hittable_targets_on_server = []
        if p1 and p1.alive() and p1._valid_init and not getattr(p1,'is_petrified',False): hittable_targets_on_server.append(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2,'is_petrified',False): hittable_targets_on_server.append(p2)
        for en_target in game_elements_ref.get("enemy_list",[]):
            if en_target.alive() and en_target._valid_init and not getattr(en_target,'is_petrified',False): hittable_targets_on_server.append(en_target)
        for st_target in game_elements_ref.get("statue_objects",[]):
            if st_target.alive() and not getattr(st_target,'is_smashed',False) : hittable_targets_on_server.append(st_target)
        
        projectiles_current_list_ref = game_elements_ref.get("projectiles_list", [])
        for proj_obj in list(projectiles_current_list_ref): 
            if hasattr(proj_obj, 'update'):
                proj_obj.update(dt_sec, platforms_list_this_frame, hittable_targets_on_server)
            if not (hasattr(proj_obj, 'alive') and proj_obj.alive()):
                if proj_obj in projectiles_current_list_ref: projectiles_current_list_ref.remove(proj_obj)
        
        # Chest Physics (Server-side)
        current_chest_on_server = game_elements_ref.get("current_chest")
        if current_chest_on_server and isinstance(current_chest_on_server, Chest) and \
           current_chest_on_server.alive() and not current_chest_on_server.is_collected_flag_internal and \
           current_chest_on_server.state == 'closed':
            if hasattr(current_chest_on_server, 'apply_physics_step'):
                current_chest_on_server.apply_physics_step(dt_sec)

            current_chest_on_server.on_ground = False
            if hasattr(current_chest_on_server, 'rect') and isinstance(current_chest_on_server.rect, QRectF): # Use QRectF
                old_chest_bottom = current_chest_on_server.rect.bottom() - (current_chest_on_server.vel_y * dt_sec * C.FPS)
                for platform_coll in platforms_list_this_frame: # Use fetched list
                    if hasattr(platform_coll, 'rect') and isinstance(platform_coll.rect, QRectF) and \
                       current_chest_on_server.rect.intersects(platform_coll.rect):
                        if current_chest_on_server.vel_y >= 0 and \
                           old_chest_bottom <= platform_coll.rect.top() + 1 and \
                           current_chest_on_server.rect.bottom() >= platform_coll.rect.top():
                            min_overlap_ratio_c = 0.1
                            min_horizontal_overlap_c = current_chest_on_server.rect.width() * min_overlap_ratio_c
                            actual_overlap_c = min(current_chest_on_server.rect.right(), platform_coll.rect.right()) - \
                                               max(current_chest_on_server.rect.left(), platform_coll.rect.left())
                            if actual_overlap_c >= min_horizontal_overlap_c:
                                current_chest_on_server.rect.moveBottom(platform_coll.rect.top())
                                current_chest_on_server.pos_midbottom.setY(current_chest_on_server.rect.bottom())
                                current_chest_on_server.vel_y = 0.0
                                current_chest_on_server.on_ground = True; break
                if hasattr(current_chest_on_server, '_update_rect_from_image_and_pos'):
                    current_chest_on_server._update_rect_from_image_and_pos()

        # Collectible Animation/State Update (after physics)
        collectibles_current_list_ref = game_elements_ref.get("collectible_list", [])
        for collectible_obj in list(collectibles_current_list_ref): 
            if hasattr(collectible_obj, 'update'): collectible_obj.update(dt_sec) 
            if not (hasattr(collectible_obj, 'alive') and collectible_obj.alive()):
                 if collectible_obj in collectibles_current_list_ref: collectibles_current_list_ref.remove(collectible_obj)
                 if game_elements_ref.get("current_chest") is collectible_obj: game_elements_ref["current_chest"] = None

        if current_chest_on_server and isinstance(current_chest_on_server, Chest) and \
           current_chest_on_server.alive() and not current_chest_on_server.is_collected_flag_internal:
            interacting_player_server = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False) and \
               hasattr(p1, 'rect') and p1.rect.intersects(current_chest_on_server.rect) and p1_action_events_current_frame.get("interact", False):
                interacting_player_server = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False) and \
                 hasattr(p2, 'rect') and p2.rect.intersects(current_chest_on_server.rect) and \
                 p2_network_input_data and p2_network_input_data.get("interact_pressed_event", False): 
                interacting_player_server = p2
            if interacting_player_server: current_chest_on_server.collect(interacting_player_server)
        
        camera_on_server = game_elements_ref.get("camera")
        if camera_on_server:
            server_focus_target = p1 if (p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified',False)) else \
                                  (p2 if (p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified',False)) else \
                                  (p1 if p1 and p1.alive() else p2)) 
            if server_focus_target: camera_on_server.update(server_focus_target)
            else: camera_on_server.static_update()
            
        current_all_renderables_server = game_elements_ref.get("all_renderable_objects", [])
        new_all_renderables_server = []
        for obj_server in current_all_renderables_server:
            if isinstance(obj_server, (Platform, Ladder, Lava, BackgroundTile)):
                new_all_renderables_server.append(obj_server)
            elif hasattr(obj_server, 'alive') and obj_server.alive():
                new_all_renderables_server.append(obj_server)
        game_elements_ref["all_renderable_objects"] = new_all_renderables_server


        if server_state_obj.client_connection:
            network_game_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state = encode_data(network_game_state_to_send)
            if encoded_state:
                try:
                    server_state_obj.client_connection.sendall(encoded_state)
                except socket.error as e_send:
                    debug(f"Server: Send game state failed: {e_send}. Client likely disconnected.");
                    server_game_active = False; server_state_obj.client_connection = None; break 
        
        time_spent_this_frame = time.monotonic() - frame_start_time
        sleep_duration = frame_duration - time_spent_this_frame
        if sleep_duration > 0:
            time.sleep(sleep_duration)

    debug("ServerLogic: Exiting server game active loop.")
    
    active_conn_to_close = None
    with client_lock:
        if server_state_obj.client_connection:
            active_conn_to_close = server_state_obj.client_connection
            server_state_obj.client_connection = None 
    if active_conn_to_close:
        try: active_conn_to_close.shutdown(socket.SHUT_RDWR)
        except: pass
        try: active_conn_to_close.close()
        except: pass
        debug("ServerLogic: Active client connection closed after game loop.")

    if server_state_obj.server_tcp_socket: 
        server_state_obj.server_tcp_socket.close()
        server_state_obj.server_tcp_socket = None
    
    debug("ServerLogic: Server mode (run_server_mode) finished.")