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
from typing import Optional, Dict # Added Dict

import constants as C
from network_comms import get_local_ip, encode_data, decode_data_stream
from game_state_manager import get_network_game_state, reset_game_state
from enemy import Enemy
import game_ui
from items import Chest
from statue import Statue
import config as game_config
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


client_lock = threading.Lock()

class ServerState:
    def __init__(self):
        self.client_connection = None
        self.client_address = None
        self.client_input_buffer: Dict = {} # Ensure it's a dict
        self.app_running = True
        self.server_tcp_socket = None
        self.server_udp_socket = None
        self.broadcast_thread = None
        self.client_handler_thread = None
        self.service_name = getattr(C, "SERVICE_NAME", "platformer_adventure_lan_v1")
        self.discovery_port_udp = getattr(C, "DISCOVERY_PORT_UDP", 5556)
        self.server_port_tcp = getattr(C, "SERVER_PORT_TCP", 5555)
        self.buffer_size = getattr(C, "BUFFER_SIZE", 8192)
        self.broadcast_interval_s = getattr(C, "BROADCAST_INTERVAL_S", 1.0)
        self.current_map_name: Optional[str] = None
        self.client_map_status: str = "unknown"
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
        server_state_obj.server_udp_socket.settimeout(0.5)
    except socket.error as e:
        error(f"Server Error: Failed to create UDP broadcast socket: {e}")
        server_state_obj.server_udp_socket = None
        return
    broadcast_address = ('<broadcast>', server_state_obj.discovery_port_udp)
    debug(f"Server (broadcast_presence_thread): Broadcasting presence: {broadcast_message_dict} to {broadcast_address} (LAN IP: {current_lan_ip})")
    while server_state_obj.app_running:
        try:
            server_state_obj.server_udp_socket.sendto(broadcast_message_bytes, broadcast_address)
        except socket.error: pass
        except Exception as e: warning(f"Server Warning: Unexpected error during broadcast send: {e}")
        for _ in range(int(server_state_obj.broadcast_interval_s * 10)):
            if not server_state_obj.app_running: break
            time.sleep(0.1)
    if server_state_obj.server_udp_socket:
        server_state_obj.server_udp_socket.close()
        server_state_obj.server_udp_socket = None
    debug("Server (broadcast_presence_thread): Broadcast thread stopped.")


def handle_client_connection_thread(conn: socket.socket, addr, server_state_obj: ServerState):
    debug(f"Server (handle_client_connection_thread): Client connected from {addr}. Handler thread started.")
    conn.settimeout(1.0)
    partial_data_from_client = b""
    if server_state_obj.current_map_name:
        try:
            conn.sendall(encode_data({"command": "set_map", "name": server_state_obj.current_map_name}))
            debug(f"Server Handler ({addr}): Sent initial map info: {server_state_obj.current_map_name}")
        except socket.error as e:
            debug(f"Server Handler ({addr}): Error sending initial map info: {e}. Client may have disconnected early.")
    else:
        critical(f"Server Handler ({addr}): CRITICAL - server_state_obj.current_map_name is None. Cannot send initial map info.")

    while server_state_obj.app_running:
        with client_lock:
            if server_state_obj.client_connection is not conn:
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
                            chunk_to_send = map_content_bytes[offset : offset + C.MAP_DOWNLOAD_CHUNK_SIZE]
                            conn.sendall(encode_data({"command": "map_data_chunk", "data": chunk_to_send.decode('utf-8', 'replace'), "seq": offset}))
                            offset += len(chunk_to_send)
                        conn.sendall(encode_data({"command": "map_transfer_end", "name": map_name_req}))
                        debug(f"Server Handler ({addr}): Sent map file '{map_name_req}' to client.")
                    else:
                        error(f"Server Error: Client requested map '{map_name_req}' but not found at '{map_file_path}'.")
                        conn.sendall(encode_data({"command": "map_file_error", "name": map_name_req, "reason": "not_found"}))
                elif command == "report_download_progress":
                    with client_lock: server_state_obj.client_download_progress = msg.get("progress", 0)
                elif "input" in msg:
                    with client_lock:
                        if server_state_obj.client_connection is conn:
                            server_state_obj.client_input_buffer = msg["input"]
        except socket.timeout: continue
        except socket.error as e:
            if server_state_obj.app_running: debug(f"Server Handler ({addr}): Socket error: {e}. Assuming disconnect.")
            break
        except Exception as e:
            if server_state_obj.app_running: error(f"Server Handler ({addr}): Unexpected error: {e}", exc_info=True)
            break
    with client_lock:
        if server_state_obj.client_connection is conn:
            debug(f"Server Handler ({addr}): Closing active connection from handler.")
            server_state_obj.client_connection = None
            server_state_obj.client_input_buffer = {"disconnect": True}
            server_state_obj.client_map_status = "disconnected"
    try: conn.shutdown(socket.SHUT_RDWR)
    except: pass
    try: conn.close()
    except: pass
    debug(f"Server: Client handler for {addr} finished.")


def run_server_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                    fonts: dict, game_elements_ref: dict, server_state_obj: ServerState):
    debug("DEBUG Server: Entering run_server_mode.")
    pygame.display.set_caption("Platformer - HOST (P1: Configured | P2: Client | Reset: Q)")
    server_state_obj.app_running = True
    current_width, current_height = screen.get_size()
    if server_state_obj.current_map_name is None:
        critical("CRITICAL SERVER: server_state_obj.current_map_name is None at start of run_server_mode.")
        return
    if not (server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive()):
        debug("DEBUG Server: Starting broadcast thread.")
        server_state_obj.broadcast_thread = threading.Thread(target=broadcast_presence_thread, args=(server_state_obj,), daemon=True)
        server_state_obj.broadcast_thread.start()
    if server_state_obj.server_tcp_socket:
        debug("DEBUG Server: Closing existing TCP socket before creating new one.")
        try: server_state_obj.server_tcp_socket.close()
        except: pass
    server_state_obj.server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_state_obj.server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_state_obj.server_tcp_socket.bind((C.SERVER_IP_BIND, server_state_obj.server_port_tcp))
        server_state_obj.server_tcp_socket.listen(1)
        server_state_obj.server_tcp_socket.settimeout(1.0)
        debug(f"DEBUG Server: Listening on {C.SERVER_IP_BIND}:{server_state_obj.server_port_tcp}")
    except socket.error as e:
        critical(f"FATAL SERVER ERROR: Failed to bind/listen TCP socket: {e}")
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
        if server_state_obj.client_connection is None:
            try:
                temp_conn, temp_addr = server_state_obj.server_tcp_socket.accept()
                with client_lock:
                    server_state_obj.client_connection = temp_conn; server_state_obj.client_address = temp_addr
                    server_state_obj.client_input_buffer = {}; server_state_obj.client_map_status = "waiting_client_report"
                    server_state_obj.game_start_signaled_to_client = False
                debug(f"DEBUG Server: Accepted connection from {temp_addr}")
                if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive():
                    server_state_obj.client_handler_thread.join(timeout=0.1)
                server_state_obj.client_handler_thread = threading.Thread(target=handle_client_connection_thread, args=(temp_conn, temp_addr, server_state_obj), daemon=True)
                server_state_obj.client_handler_thread.start()
            except socket.timeout: pass
            except Exception as e: error(f"Server: Error accepting client: {e}", exc_info=True)
        dialog_title_sync = "Server Hosting"; dialog_msg_sync = "Waiting for Player 2..."; dialog_prog_sync = -1
        with client_lock:
            if server_state_obj.client_connection:
                if server_state_obj.client_map_status == "waiting_client_report": dialog_msg_sync = f"P2 ({server_state_obj.client_address[0]}) connected. Map sync..."
                elif server_state_obj.client_map_status == "missing": dialog_msg_sync = f"P2 missing map. Sending..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "downloading_ack": dialog_msg_sync = f"P2 downloading map..."; dialog_prog_sync = server_state_obj.client_download_progress
                elif server_state_obj.client_map_status == "present": dialog_msg_sync = f"P2 has map. Ready."; dialog_prog_sync = 100.0; client_sync_wait_active = False
                elif server_state_obj.client_map_status == "disconnected": dialog_msg_sync = "P2 disconnected. Waiting..."; server_state_obj.client_connection = None
        game_ui.draw_download_dialog(screen, fonts, dialog_title_sync, dialog_msg_sync, dialog_prog_sync)
        clock.tick(10)
    if not server_state_obj.app_running or server_state_obj.client_connection is None or server_state_obj.client_map_status != "present":
        debug(f"DEBUG Server: Exiting sync (app_running: {server_state_obj.app_running}, client_conn: {server_state_obj.client_connection is not None}, map_status: {server_state_obj.client_map_status}).")
        server_state_obj.app_running = False
        if server_state_obj.broadcast_thread and server_state_obj.broadcast_thread.is_alive(): server_state_obj.broadcast_thread.join(timeout=0.5)
        if server_state_obj.client_handler_thread and server_state_obj.client_handler_thread.is_alive(): server_state_obj.client_handler_thread.join(timeout=0.5)
        if server_state_obj.server_tcp_socket: server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
        return
    debug(f"DEBUG Server: Client {server_state_obj.client_address} connected, map synced. Starting game...")
    p1 = game_elements_ref.get("player1"); p2 = game_elements_ref.get("player2")
    if p1: debug(f"DEBUG Server: P1 instance: {p1}, Valid: {p1._valid_init if p1 else 'N/A'}")
    if p2: debug(f"DEBUG Server: P2 instance: {p2}, Valid: {p2._valid_init if p2 else 'N/A'}")
    server_game_active = True
    p1_action_events = {} # Initialize action events dict for P1

    while server_game_active and server_state_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0; now_ticks_server = pygame.time.get_ticks()
        pygame_events = pygame.event.get(); keys_pressed_p1 = pygame.key.get_pressed()
        is_p1_game_over_for_reset = (p1 and p1._valid_init and p1.is_dead and (not p1.alive() or (hasattr(p1, 'death_animation_finished') and p1.death_animation_finished))) or (not p1 or not p1._valid_init)
        host_requested_reset = False
        for event in pygame_events:
            if event.type == pygame.QUIT: server_game_active = False; server_state_obj.app_running = False; break
            if event.type == pygame.VIDEORESIZE and not (screen.get_flags() & pygame.FULLSCREEN):
                current_width,current_height = max(320,event.w),max(240,event.h)
                screen=pygame.display.set_mode((current_width,current_height),pygame.RESIZABLE|pygame.DOUBLEBUF)
                if game_elements_ref.get("camera"): game_elements_ref["camera"].set_screen_dimensions(current_width, current_height)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: server_game_active = False # K_ESCAPE still exits game mode
                if event.key == pygame.K_q: host_requested_reset = True
                if p1 and p1._valid_init:
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'): p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'): p1.heal_to_full()
        if not server_state_obj.app_running or not server_game_active: break

        if p1 and p1._valid_init and not p1.is_dead and hasattr(p1, 'process_input'):
            p1_action_events = p1.process_input(pygame_events, game_elements_ref["platform_sprites"], keys_pressed_override=keys_pressed_p1)
            if p1_action_events.get("pause"): # Host (P1) "pause" action
                info("Server: P1 pause action detected. Returning to main menu.")
                server_game_active = False
        if not server_game_active: break # Check if P1 paused

        p2_network_input, client_disconnected_signal, p2_requested_reset, p2_requested_pause = None, False, False, False
        with client_lock:
            if server_state_obj.client_input_buffer:
                buffered_input = server_state_obj.client_input_buffer.copy()
                server_state_obj.client_input_buffer.clear()
                if buffered_input.get("disconnect"): client_disconnected_signal = True
                elif buffered_input.get("action_reset", False): p2_requested_reset = True
                if buffered_input.get("pause_event", False): p2_requested_pause = True # Check if client sent pause
                if p2 and p2._valid_init:
                    if buffered_input.get("action_self_harm", False) and hasattr(p2, 'self_inflict_damage'): p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    elif buffered_input.get("action_heal", False) and hasattr(p2, 'heal_to_full'): p2.heal_to_full()
                p2_network_input = buffered_input
        if client_disconnected_signal:
            debug("DEBUG Server: Client disconnected signal received in main loop.")
            server_game_active = False; server_state_obj.client_connection = None; server_state_obj.client_map_status = "unknown"
            break
        if p2_requested_pause: # If client signals pause
            info("Server: Client (P2) requested pause. Returning to main menu.")
            server_game_active = False
        if not server_game_active: break # Check if P2 paused

        if p2 and p2._valid_init and p2_network_input and hasattr(p2, 'handle_network_input'):
            p2.handle_network_input(p2_network_input)
        if host_requested_reset or (p2_requested_reset and is_p1_game_over_for_reset):
            info("DEBUG Server: Game state reset triggered.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref["all_sprites"].add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref["all_sprites"].add(p2)
        if p1 and p1._valid_init:
            other_players_p1 = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref
            p1.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"], game_elements_ref["hazard_sprites"], other_players_p1, game_elements_ref["enemy_list"])
        if p2 and p2._valid_init:
            other_players_p2 = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"], game_elements_ref["hazard_sprites"], other_players_p2, game_elements_ref["enemy_list"])
        active_players_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_instance in list(game_elements_ref.get("enemy_list", [])):
            if enemy_instance._valid_init:
                if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified: continue
                enemy_instance.update(dt_sec, active_players_ai, game_elements_ref["platform_sprites"], game_elements_ref["hazard_sprites"], game_elements_ref["enemy_list"])
                if enemy_instance.is_dead and hasattr(enemy_instance, 'death_animation_finished') and enemy_instance.death_animation_finished and enemy_instance.alive():
                    if hasattr(Enemy, 'print_limiter') and Enemy.print_limiter.can_print(f"server_killing_enemy_{enemy_instance.enemy_id}"): debug(f"Server: Auto-killing enemy {enemy_instance.enemy_id} as death anim finished.")
                    enemy_instance.kill()
        statues = game_elements_ref.get("statue_objects", [])
        for statue_instance in statues:
            if hasattr(statue_instance, 'update'): statue_instance.update(dt_sec)
        hittable_chars_server = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_chars_server.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_chars_server.add(p2)
        for enemy_proj_target in game_elements_ref.get("enemy_list", []):
            if enemy_proj_target and enemy_proj_target.alive() and enemy_proj_target._valid_init and not getattr(enemy_proj_target, 'is_petrified', False): hittable_chars_server.add(enemy_proj_target)
        for statue_target in statues:
            if statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed: hittable_chars_server.add(statue_target)
        for proj_instance in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj_instance, 'game_elements_ref') and proj_instance.game_elements_ref is None: proj_instance.game_elements_ref = game_elements_ref
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(dt_sec, game_elements_ref["platform_sprites"], hittable_chars_server)
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)
        chest_instance_server = game_elements_ref.get("current_chest")
        if isinstance(chest_instance_server, Chest) and chest_instance_server.alive() and not chest_instance_server.is_collected_flag_internal:
            interacted_player = None
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and pygame.sprite.collide_rect(p1, chest_instance_server) and p1_action_events.get("interact", False):
                interacted_player = p1
            # P2 interact for chest on server side (client sends interact event)
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and pygame.sprite.collide_rect(p2, chest_instance_server) and p2_network_input and p2_network_input.get("interact_pressed_event", False):
                interacted_player = p2
            if interacted_player: chest_instance_server.collect(interacted_player)
        camera_instance_server = game_elements_ref.get("camera")
        if camera_instance_server:
            focus_target = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1,'is_petrified', False): focus_target = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2,'is_petrified', False): focus_target = p2
            elif p1 and p1.alive() and p1._valid_init: focus_target = p1
            elif p2 and p2.alive() and p2._valid_init: focus_target = p2
            if focus_target: camera_instance_server.update(focus_target)
            else: camera_instance_server.static_update()
        if server_state_obj.client_connection:
            net_state_to_send = get_network_game_state(game_elements_ref)
            encoded_state = encode_data(net_state_to_send)
            if encoded_state:
                try: server_state_obj.client_connection.sendall(encoded_state)
                except socket.error as e:
                    debug(f"DEBUG Server: Send failed: {e}. Client likely disconnected."); server_game_active = False; server_state_obj.client_connection = None; break
        try:
            dl_status_s, dl_prog_s = None, None
            with client_lock:
                if server_state_obj.client_map_status in ["missing", "downloading_ack"]:
                    dl_status_s = f"P2 Downloading: {server_state_obj.current_map_name}"; dl_prog_s = server_state_obj.client_download_progress
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_server, download_status_message=dl_status_s, download_progress_percent=dl_prog_s)
        except Exception as e_draw: error(f"Server draw error: {e_draw}", exc_info=True); server_game_active=False; break
        pygame.display.flip()
    debug("DEBUG Server: Exiting active game loop.")
    conn_to_close_server = None
    with client_lock:
        if server_state_obj.client_connection: conn_to_close_server = server_state_obj.client_connection; server_state_obj.client_connection = None
    if conn_to_close_server:
        debug("DEBUG Server: Mode exit cleanup - closing client connection.")
        try: conn_to_close_server.shutdown(socket.SHUT_RDWR); conn_to_close_server.close()
        except: pass
    if server_state_obj.server_tcp_socket:
        debug("DEBUG Server: Closing main TCP listening socket.")
        server_state_obj.server_tcp_socket.close(); server_state_obj.server_tcp_socket = None
    debug("DEBUG Server: Server mode finished and returned to caller.")