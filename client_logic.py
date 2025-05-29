# client_logic.py
# -*- coding: utf-8 -*-
"""
Handles client-side game logic, connection to server, and LAN discovery for PySide6.
UI updates are handled by emitting signals to the main application.
Map paths now use map_name_folder/map_name_file.py structure.
MODIFIED: Deferred import of initialize_game_elements in run_client_mode.
"""
# version 2.1.2 (Deferred import initialize_game_elements in run_client_mode)

import socket
import time
import traceback
import os
import importlib
from typing import Optional, Dict, Any, Tuple

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL CLIENT_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import set_network_game_state
# REMOVE THIS LINE: from game_setup import initialize_game_elements # This was the problematic top-level import
import config as game_config


class ClientState:
    def __init__(self):
        self.client_tcp_socket: Optional[socket.socket] = None
        self.server_state_buffer: bytes = b""
        self.last_received_server_state: Optional[Dict[str, Any]] = None
        self.app_running = True
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.client_search_timeout_s = float(getattr(C, "CLIENT_SEARCH_TIMEOUT_S", 5.0))
        self.buffer_size = int(getattr(C, "BUFFER_SIZE", 8192))
        self.server_selected_map_name: Optional[str] = None
        self.map_download_status: str = "unknown"
        self.map_download_progress: float = 0.0
        self.map_total_size_bytes: int = 0
        self.map_received_bytes: int = 0
        self.map_file_buffer: bytes = b""


def find_server_on_lan(client_state_obj: ClientState,
                       ui_update_callback: Optional[callable] = None
                       ) -> Optional[Tuple[str, int]]:
    debug("Client (find_server_on_lan): Starting LAN server search.")
    if ui_update_callback: ui_update_callback("searching", "Searching for server on LAN...")
    listen_socket: Optional[socket.socket] = None
    found_server_ip: Optional[str] = None
    found_server_port: Optional[int] = None
    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', client_state_obj.discovery_port_udp))
        listen_socket.settimeout(0.5)
        debug(f"Client (find_server_on_lan): UDP listen socket bound to port {client_state_obj.discovery_port_udp}.")
    except socket.error as e_socket:
        error_msg = f"Failed to bind UDP listen socket on port {client_state_obj.discovery_port_udp}: {e_socket}"
        error(f"Client Error: {error_msg}")
        if ui_update_callback: ui_update_callback("error", error_msg)
        return None
    start_search_time = time.monotonic()
    client_local_ip = get_local_ip()
    debug(f"Client (find_server_on_lan): Searching (Service: '{client_state_obj.service_name}'). My IP: {client_local_ip}. Timeout: {client_state_obj.client_search_timeout_s}s.")
    while (time.monotonic() - start_search_time) < client_state_obj.client_search_timeout_s:
        if not client_state_obj.app_running:
            debug("Client (find_server_on_lan): LAN server search aborted (app_running is False).")
            if ui_update_callback: ui_update_callback("cancelled", "Search cancelled by application.")
            break
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
                    server_map_name = decoded_udp_message.get("map_name", "Unknown Map")
                    info(f"Client (find_server_on_lan): Found server '{client_state_obj.service_name}' at {server_ip}:{server_port} (Map: {server_map_name})")
                    found_server_ip, found_server_port = server_ip, server_port
                    if ui_update_callback: ui_update_callback("found", (server_ip, server_port, server_map_name))
                    break
        except socket.timeout: continue
        except Exception as e_udp:
            error_msg = f"Client: Error processing UDP broadcast: {e_udp}"
            error(error_msg, exc_info=True)
            if ui_update_callback: ui_update_callback("error", error_msg)
    if listen_socket: listen_socket.close()
    if not found_server_ip and client_state_obj.app_running:
        info(f"Client (find_server_on_lan): No server for '{client_state_obj.service_name}' after timeout.")
        if ui_update_callback: ui_update_callback("timeout", f"No server found for '{client_state_obj.service_name}'.")
    return (found_server_ip, found_server_port) if found_server_ip and found_server_port else None


def run_client_mode(client_state_obj: ClientState,
                    game_elements_ref: Dict[str, Any],
                    ui_status_update_callback: Optional[callable] = None,
                    target_ip_port_str: Optional[str] = None,
                    get_input_snapshot_callback: Optional[callable] = None,
                    process_qt_events_callback: Optional[callable] = None
                    ):
    info("Client (run_client_mode): Entering client mode.")

    # --- LOCAL IMPORT HERE ---
    try:
        from game_setup import initialize_game_elements # DEFERRED
    except ImportError:
        critical("CLIENT_LOGIC CRITICAL (run_client_mode): Failed to import initialize_game_elements! Game setup will fail.")
        if ui_status_update_callback: ui_status_update_callback("Critical Error", "Game setup components missing.", -1.0)
        return
    # --- END LOCAL IMPORT ---

    client_state_obj.app_running = True
    server_ip_to_connect: Optional[str] = None
    server_port_to_connect: int = C.SERVER_PORT_TCP

    if target_ip_port_str:
        info(f"Client (run_client_mode): Direct IP specified: {target_ip_port_str}")
        ip_parts = target_ip_port_str.rsplit(':', 1)
        server_ip_to_connect = ip_parts[0]
        if len(ip_parts) > 1:
            try: server_port_to_connect = int(ip_parts[1])
            except ValueError: warning(f"Client: Invalid port in '{target_ip_port_str}'. Using default {C.SERVER_PORT_TCP}.")
    else:
        error("Client (run_client_mode): No target IP provided. Cannot proceed.")
        if ui_status_update_callback: ui_status_update_callback("Error", "No server target specified.", -1)
        return

    if not server_ip_to_connect or not client_state_obj.app_running:
        info(f"Client: Exiting client mode (no server target or app closed).")
        return

    if client_state_obj.client_tcp_socket:
        try: client_state_obj.client_tcp_socket.close()
        except: pass
    client_state_obj.client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection_succeeded = False
    connection_error_msg = "Unknown Connection Error"
    try:
        info(f"Client: Attempting connection to server at {server_ip_to_connect}:{server_port_to_connect}...")
        if ui_status_update_callback: ui_status_update_callback("Connecting...", f"{server_ip_to_connect}:{server_port_to_connect}", 0)
        client_state_obj.client_tcp_socket.settimeout(10.0)
        client_state_obj.client_tcp_socket.connect((server_ip_to_connect, server_port_to_connect))
        client_state_obj.client_tcp_socket.settimeout(0.05)
        info("Client: TCP Connection to server successful!")
        connection_succeeded = True
    except socket.timeout: connection_error_msg = "Connection Timed Out"
    except socket.error as e_sock: connection_error_msg = f"Connection Error ({getattr(e_sock, 'strerror', e_sock)})"
    except Exception as e_conn: connection_error_msg = f"Unexpected Connection Error: {e_conn}"

    if not connection_succeeded:
        error(f"Client: Failed to connect: {connection_error_msg}")
        if ui_status_update_callback: ui_status_update_callback("Connection Failed", connection_error_msg, -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close()
        client_state_obj.client_tcp_socket = None
        return

    client_state_obj.map_download_status = "waiting_map_info"; client_state_obj.server_state_buffer = b""
    map_sync_phase_active = True
    last_ui_update_time = 0

    maps_base_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs):
        project_root_from_constants = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)
    debug(f"ClientLogic: Using maps base directory: {maps_base_dir_abs}")

    while map_sync_phase_active and client_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback()
        if not client_state_obj.app_running: break
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
            if client_state_obj.map_download_status == "changed_internally": client_state_obj.map_download_status = "processing"
        try:
            assert client_state_obj.client_tcp_socket is not None
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
                    if client_state_obj.server_selected_map_name:
                        map_folder_path = os.path.join(maps_base_dir_abs, client_state_obj.server_selected_map_name)
                        map_py_file_path = os.path.join(map_folder_path, f"{client_state_obj.server_selected_map_name}.py")
                        if os.path.exists(map_py_file_path):
                            client_state_obj.map_download_status = "present"
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                        else:
                            client_state_obj.map_download_status = "missing"
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"missing"}))
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"request_map_file", "name":client_state_obj.server_selected_map_name}))
                            client_state_obj.map_download_status = "downloading"; client_state_obj.map_received_bytes = 0; client_state_obj.map_total_size_bytes = 0; client_state_obj.map_file_buffer = b""
                    else:
                        error("Client Error: server_selected_map_name is None after set_map command.")
                        client_state_obj.map_download_status = "error"
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "map_file_info" and client_state_obj.map_download_status=="downloading":
                    client_state_obj.map_total_size_bytes = msg.get("size",0)
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "map_data_chunk" and client_state_obj.map_download_status=="downloading":
                    chunk_data_bytes = msg.get("data","").encode('utf-8')
                    client_state_obj.map_file_buffer += chunk_data_bytes
                    client_state_obj.map_received_bytes = len(client_state_obj.map_file_buffer)
                    if client_state_obj.map_total_size_bytes > 0: client_state_obj.map_download_progress = (client_state_obj.map_received_bytes/client_state_obj.map_total_size_bytes)*100.0
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "map_transfer_end" and client_state_obj.map_download_status=="downloading":
                    if client_state_obj.map_received_bytes == client_state_obj.map_total_size_bytes and client_state_obj.server_selected_map_name:
                        map_folder_to_save_in = os.path.join(maps_base_dir_abs, client_state_obj.server_selected_map_name)
                        map_py_file_to_save = os.path.join(map_folder_to_save_in, f"{client_state_obj.server_selected_map_name}.py")
                        try:
                            if not os.path.exists(map_folder_to_save_in): os.makedirs(map_folder_to_save_in); debug(f"Client: Created map folder '{map_folder_to_save_in}' for downloaded map.")
                            map_specific_init_py = os.path.join(map_folder_to_save_in, "__init__.py")
                            if not os.path.exists(map_specific_init_py):
                                with open(map_specific_init_py, "w") as f_init_map: f_init_map.write(f"# Map-specific __init__.py for {client_state_obj.server_selected_map_name} (auto-created by client)\n")
                                debug(f"Client: Created '{map_specific_init_py}' for downloaded map sub-package.")
                            with open(map_py_file_to_save, "wb") as f: f.write(client_state_obj.map_file_buffer)
                            info(f"Client: Map '{client_state_obj.server_selected_map_name}' saved to '{map_py_file_to_save}'.")
                            client_state_obj.map_download_status = "present"; importlib.invalidate_caches()
                            client_state_obj.client_tcp_socket.sendall(encode_data({"command":"report_map_status", "name":client_state_obj.server_selected_map_name, "status":"present"}))
                        except Exception as e_save: error(f"Client Error: Failed to save map: {e_save}"); client_state_obj.map_download_status="error"
                    else: error("Client Error: Map download mismatch or missing map name."); client_state_obj.map_download_status="error"
                    client_state_obj.map_download_status = "changed_internally"
                elif cmd == "start_game_now":
                    if client_state_obj.map_download_status == "present": info(f"Client: Received start_game_now. Map present. Proceeding."); map_sync_phase_active = False
                    else: info(f"Client: start_game_now received, but map status is '{client_state_obj.map_download_status}'. Waiting.")
        except socket.timeout: pass
        except socket.error as e_sock_map: error(f"Client: Socket error during map sync: {e_sock_map}."); map_sync_phase_active=False; break
        except Exception as e_map_sync: error(f"Client: Error during map sync: {e_map_sync}", exc_info=True); map_sync_phase_active=False; break
        time.sleep(0.01)

    if not client_state_obj.app_running or client_state_obj.map_download_status != "present":
        info(f"Client: Exiting (app closed or map not ready: {client_state_obj.map_download_status}).")
        if ui_status_update_callback: ui_status_update_callback("Error", f"Map sync failed: {client_state_obj.map_download_status}", -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return

    info(f"Client: Map '{client_state_obj.server_selected_map_name}' present. Initializing game elements...")
    if ui_status_update_callback: ui_status_update_callback("Loading Level...", f"Initializing '{client_state_obj.server_selected_map_name}'", 100.0)
    screen_width_main_app, screen_height_main_app = C.TILE_SIZE*20, C.TILE_SIZE*15
    if 'main_app_screen_width' in game_elements_ref and 'main_app_screen_height' in game_elements_ref:
         screen_width_main_app = game_elements_ref['main_app_screen_width']
         screen_height_main_app = game_elements_ref['main_app_screen_height']

    init_success = initialize_game_elements( # This will use the locally imported function
        int(screen_width_main_app), int(screen_height_main_app),
        game_elements_ref,
        "join_ip",
        client_state_obj.server_selected_map_name
    )
    if not init_success:
        critical_msg = f"Client CRITICAL: Failed to init game elements with map '{client_state_obj.server_selected_map_name}'."
        critical(critical_msg)
        if ui_status_update_callback: ui_status_update_callback("Error", critical_msg, -1)
        if client_state_obj.client_tcp_socket: client_state_obj.client_tcp_socket.close(); client_state_obj.client_tcp_socket=None
        return

    camera_client = game_elements_ref.get("camera")
    if camera_client:
        camera_client.set_screen_dimensions(screen_width_main_app, screen_height_main_app)
        if "level_pixel_width" in game_elements_ref and \
           "level_min_x_absolute" in game_elements_ref and \
           "level_min_y_absolute" in game_elements_ref and \
           "level_max_y_absolute" in game_elements_ref:
            camera_client.set_level_dimensions( game_elements_ref["level_pixel_width"], game_elements_ref["level_min_x_absolute"], game_elements_ref["level_min_y_absolute"], game_elements_ref["level_max_y_absolute"] )
            game_elements_ref['camera_level_dims_set'] = True

    p2_controlled_by_client = game_elements_ref.get("player2")
    p1_remote_on_client = game_elements_ref.get("player1")
    client_game_active = True
    client_state_obj.server_state_buffer = b""
    client_state_obj.last_received_server_state = None

    while client_game_active and client_state_obj.app_running:
        if process_qt_events_callback: process_qt_events_callback()
        if not client_state_obj.app_running: break
        p2_input_payload_for_server: Dict[str, Any] = {}
        if get_input_snapshot_callback and p2_controlled_by_client:
            p2_input_payload_for_server = get_input_snapshot_callback(p2_controlled_by_client)
        if p2_input_payload_for_server.get("pause_event"):
            info("Client: P2 local pause action detected. Signaling server and exiting local game loop.")
            client_game_active = False
        if not client_state_obj.app_running or not client_game_active: break
        if client_state_obj.client_tcp_socket and p2_input_payload_for_server:
            encoded_payload = encode_data({"input": p2_input_payload_for_server})
            if encoded_payload:
                try: client_state_obj.client_tcp_socket.sendall(encoded_payload)
                except socket.error as e_send: error(f"Client: Send to server failed: {e_send}."); client_game_active=False; break
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
        for p_instance in [p1_remote_on_client, p2_controlled_by_client]:
             if p_instance and hasattr(p_instance, '_valid_init') and p_instance._valid_init and \
                hasattr(p_instance, 'alive') and p_instance.alive() and hasattr(p_instance, 'animate'): p_instance.animate()
        for enemy_client in game_elements_ref.get("enemy_list",[]):
            if hasattr(enemy_client, '_valid_init') and enemy_client._valid_init:
                if hasattr(enemy_client, 'alive') and enemy_client.alive() and hasattr(enemy_client, 'animate'): enemy_client.animate()
                if getattr(enemy_client, 'is_dead', False) and getattr(enemy_client, 'death_animation_finished', False) and \
                   hasattr(enemy_client, 'alive') and enemy_client.alive() and hasattr(enemy_client, 'kill'): enemy_client.kill()
        for proj_client in game_elements_ref.get("projectiles_list",[]):
            if hasattr(proj_client, 'alive') and proj_client.alive() and hasattr(proj_client,'animate'): proj_client.animate()
        for statue_obj in game_elements_ref.get("statue_objects",[]):
            if hasattr(statue_obj,'update'): statue_obj.update(0.016)
        for collectible in game_elements_ref.get("collectible_list", []):
            if hasattr(collectible, 'update'): collectible.update(0.016)
        if camera_client:
            cam_focus_target_client = None
            if p2_controlled_by_client and hasattr(p2_controlled_by_client, '_valid_init') and p2_controlled_by_client._valid_init and \
               hasattr(p2_controlled_by_client, 'alive') and p2_controlled_by_client.alive() and \
               not getattr(p2_controlled_by_client, 'is_dead', True) and not getattr(p2_controlled_by_client,'is_petrified',False):
                cam_focus_target_client = p2_controlled_by_client
            elif p1_remote_on_client and hasattr(p1_remote_on_client, '_valid_init') and p1_remote_on_client._valid_init and \
                 hasattr(p1_remote_on_client, 'alive') and p1_remote_on_client.alive() and \
                 not getattr(p1_remote_on_client, 'is_dead', True) and not getattr(p1_remote_on_client,'is_petrified',False):
                cam_focus_target_client = p1_remote_on_client
            elif p2_controlled_by_client and hasattr(p2_controlled_by_client, '_valid_init') and p2_controlled_by_client._valid_init and \
                 hasattr(p2_controlled_by_client, 'alive') and p2_controlled_by_client.alive():
                 cam_focus_target_client = p2_controlled_by_client
            elif p1_remote_on_client and hasattr(p1_remote_on_client, '_valid_init') and p1_remote_on_client._valid_init and \
                 hasattr(p1_remote_on_client, 'alive') and p1_remote_on_client.alive():
                 cam_focus_target_client = p1_remote_on_client
            if cam_focus_target_client: camera_client.update(cam_focus_target_client)
            else: camera_client.static_update()
        time.sleep(1.0 / C.FPS)

    info("Client: Exiting active game simulation.")
    if client_state_obj.client_tcp_socket:
        info("Client: Closing TCP socket to server.")
        try: client_state_obj.client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except: pass
        try: client_state_obj.client_tcp_socket.close()
        except: pass
        client_state_obj.client_tcp_socket = None
    info("Client: Client mode finished and returned to caller.")