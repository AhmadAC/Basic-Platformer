# app_game_modes.py
# -*- coding: utf-8 -*-
"""
Handles game mode logic: initialization, starting/stopping modes,
managing network interactions, and UI dialogs for PySide6.
Map paths now use map_name_folder/map_name_file.py structure.
MODIFIED: Deferred import of initialize_game_elements.
MODIFIED: Refined camera setup timing in prepare_and_start_game_logic.
MODIFIED: Added more debug logs for camera state.
MODIFIED: Ensures MainWindow.map_change_is_active is reset on various exit paths.
"""
# version 2.1.4 (Ensure map_change_is_active reset)

import os
import sys
import time
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QListWidgetItem, QDialogButtonBox, QMessageBox, QApplication
from PySide6.QtCore import QThread, Signal, Qt, QRectF, QPointF

from logger import info, debug, warning, error, critical
import constants as C
import config as game_config

from app_ui_creator import (
    _show_status_dialog,
    _update_status_dialog,
    _close_status_dialog,
    _show_lan_search_dialog,
    _update_lan_search_list_focus,
    _update_ip_dialog_button_focus
)

from game_ui import IPInputDialog
# from game_state_manager import reset_game_state # Handled in app_core

from player import Player
from enemy import Enemy
from statue import Statue
from items import Chest
from tiles import Platform, Ladder, Lava, BackgroundTile
from camera import Camera
from level_loader import LevelLoader
# DEFERRED IMPORT: from game_setup import initialize_game_elements

from server_logic import ServerState
from client_logic import ClientState, find_server_on_lan

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any


class LANServerSearchThread(QThread):
    search_event_signal = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self.client_state_for_search = ClientState()

    def run(self):
        self._running = True
        self.search_event_signal.emit("searching", "Searching for LAN games...")
        info("LAN_SEARCH_THREAD: Actual search started using find_server_on_lan.")

        def search_update_callback(status_key: str, message_data: Any):
            if not self._running: return
            if status_key == "found" and isinstance(message_data, tuple) and len(message_data) == 3:
                 self.search_event_signal.emit(status_key, message_data)
            else:
                self.search_event_signal.emit(status_key, message_data)

        result_server_info_tuple = find_server_on_lan(self.client_state_for_search, search_update_callback)

        if self._running:
            self.search_event_signal.emit("final_result", result_server_info_tuple)

        info("LAN_SEARCH_THREAD: Actual search finished.")
        self._running = False

    def stop_search(self):
        info("LAN_SEARCH_THREAD: Stop requested.")
        self._running = False
        if hasattr(self.client_state_for_search, 'app_running'):
            self.client_state_for_search.app_running = False


def _initialize_game_entities(main_window: 'MainWindow', map_name_folder_stem: str, mode: str, num_players_for_couch_coop: Optional[int] = None) -> bool:
    info(f"GAME_MODES (_initialize_game_entities): Delegating to game_setup.initialize_game_elements for map '{map_name_folder_stem}', mode '{mode}', couch_players: {num_players_for_couch_coop}.")
    debug(f"GAME_MODES DEBUG (_initialize_game_entities): BEFORE game_setup call, main_window.game_elements['camera'] is type: {type(main_window.game_elements.get('camera'))}, ID: {id(main_window.game_elements.get('camera'))}")

    try:
        from game_setup import initialize_game_elements
    except ImportError:
        critical("GAME_MODES CRITICAL (_initialize_game_entities): Failed to import initialize_game_elements! Game setup will fail.")
        _update_status_dialog(main_window, title="Critical Error", message="Failed to load game setup components.", progress=-1.0)
        return False

    screen_w = main_window.game_scene_widget.width() if main_window.game_scene_widget.width() > 1 else main_window.width()
    screen_h = main_window.game_scene_widget.height() if main_window.game_scene_widget.height() > 1 else main_window.height()

    if mode == "couch_play" and num_players_for_couch_coop is not None:
        main_window.game_elements['num_active_players_for_mode'] = num_players_for_couch_coop
    else:
        # For host mode, default to 2 players for camera setup and general logic,
        # actual player count is handled by server/client sync.
        main_window.game_elements['num_active_players_for_mode'] = 2 if mode != "join_ip" and mode != "join_lan" else 1


    success = initialize_game_elements(
        current_width=int(screen_w),
        current_height=int(screen_h),
        game_elements_ref=main_window.game_elements,
        for_game_mode=mode,
        map_module_name=map_name_folder_stem
    )
    debug(f"GAME_MODES DEBUG (_initialize_game_entities): AFTER game_setup call, success: {success}, main_window.game_elements['camera'] is type: {type(main_window.game_elements.get('camera'))}, ID: {id(main_window.game_elements.get('camera'))}")

    if not success:
        error_msg = f"Failed to set up game for map: {map_name_folder_stem}"
        error(f"GAME_MODES: game_setup.initialize_game_elements FAILED for map '{map_name_folder_stem}', mode '{mode}'. Message: {error_msg}")
        _update_status_dialog(main_window, title="Map Load Error", message=error_msg, progress=-1.0)
    else:
        info(f"GAME_MODES: game_setup.initialize_game_elements SUCCEEDED for map '{map_name_folder_stem}', mode '{mode}'.")

    return success


# --- Map Selection Initiators ---
def initiate_couch_play_map_selection(main_window: 'MainWindow'):
    info(f"GAME_MODES: Initiating map selection for Couch Co-op ({main_window.selected_couch_coop_players} players).")
    if main_window.map_select_title_label:
        main_window.map_select_title_label.setText(f"Select Map ({main_window.selected_couch_coop_players} Players Couch Co-op)")
    main_window._populate_map_list_for_selection("couch_coop"); main_window.show_view("map_select")

def initiate_host_game_map_selection(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating map selection for Hosting Game.")
    if main_window.map_select_title_label: main_window.map_select_title_label.setText("Select Map to Host")
    main_window._populate_map_list_for_selection("host_game"); main_window.show_view("map_select")

# --- Game Start Triggers ---
def start_couch_play_logic(main_window: 'MainWindow', map_name_folder_stem: str):
    info(f"GAME_MODES: Starting Couch Co-op with map '{map_name_folder_stem}' for {main_window.selected_couch_coop_players} players.")
    prepare_and_start_game_logic(main_window, "couch_play", map_name_folder_stem, num_players_for_couch_coop=main_window.selected_couch_coop_players)

def start_host_game_logic(main_window: 'MainWindow', map_name_folder_stem: str):
    info(f"GAME_MODES: Starting Host Game with map '{map_name_folder_stem}'.")
    prepare_and_start_game_logic(main_window, "host_game", map_name_folder_stem)

# --- Dialog Initiators ---
def initiate_join_lan_dialog(main_window: 'MainWindow'): info("GAME_MODES: Initiating Join LAN Dialog."); _show_lan_search_dialog(main_window)
def initiate_join_ip_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join by IP Dialog.")
    if main_window.ip_input_dialog is None:
        main_window.ip_input_dialog = IPInputDialog(parent=main_window)
        main_window.ip_input_dialog.accepted.connect(lambda: prepare_and_start_game_logic(main_window, "join_ip",target_ip_port=str(main_window.ip_input_dialog.ip_port_string if main_window.ip_input_dialog and main_window.ip_input_dialog.ip_port_string else "")))
        main_window.ip_input_dialog.rejected.connect(lambda: (main_window.show_view("menu"), setattr(main_window, 'current_modal_dialog', None)))
        ok_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok); cancel_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        main_window._ip_dialog_buttons_ref = [btn for btn in [ok_button, cancel_button] if btn]
    main_window.current_modal_dialog = "ip_input"; main_window._ip_dialog_selected_button_idx = 0
    _update_ip_dialog_button_focus(main_window); main_window.ip_input_dialog.clear_input_and_focus(); main_window.ip_input_dialog.show()

# --- Core Game Setup and Management ---
def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str,
                                 map_name_folder_stem: Optional[str] = None,
                                 target_ip_port: Optional[str] = None,
                                 num_players_for_couch_coop: Optional[int] = None):
    info(f"GAME_MODES: Preparing game. Mode: {mode}, Map: {map_name_folder_stem}, Target: {target_ip_port}, CouchPlayers: {num_players_for_couch_coop}")

    if not main_window or not hasattr(main_window, 'app_status') or not main_window.app_status.app_running:
        info(f"GAME_MODES: prepare_and_start_game_logic called but app is not running or main_window/app_status invalid (Mode: {mode}). Aborting preparation.")
        if hasattr(main_window, 'status_dialog') and main_window.status_dialog and main_window.status_dialog.isVisible():
            _close_status_dialog(main_window)
        if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
        return

    main_window.current_game_mode = mode
    main_window.game_elements['current_game_mode'] = mode
    game_initialized_successfully = False

    if mode == "couch_play":
        if not map_name_folder_stem:
            error("Map name (folder/stem) required for couch_play."); main_window.show_view("menu")
            if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
            return
        _show_status_dialog(main_window, f"Starting Couch Co-op", f"Loading map: {map_name_folder_stem}...")
        if not _initialize_game_entities(main_window, map_name_folder_stem, mode, num_players_for_couch_coop=num_players_for_couch_coop):
            _close_status_dialog(main_window); main_window.show_view("menu")
            if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
            return
        _update_status_dialog(main_window, message="Entities initialized successfully.", progress=50.0, title=f"Starting Couch Co-op")
        game_initialized_successfully = True
    elif mode == "host_game":
        if not map_name_folder_stem:
            error("Map name (folder/stem) required for host_game."); main_window.show_view("menu")
            if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
            return
        _show_status_dialog(main_window, f"Starting Host Game", f"Loading map: {map_name_folder_stem}...")
        if not _initialize_game_entities(main_window, map_name_folder_stem, mode): # num_players not needed, server handles P2 spawn
            _close_status_dialog(main_window); main_window.show_view("menu")
            if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
            return
        _update_status_dialog(main_window, message="Entities initialized successfully.", progress=50.0, title=f"Starting Host Game")
        game_initialized_successfully = True
    elif mode in ["join_ip", "join_lan"]:
        if not target_ip_port:
            error("Target IP:Port required for join."); _close_status_dialog(main_window); main_window.show_view("menu")
            if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
            return
        _show_status_dialog(main_window, title=f"Joining Game ({mode.replace('_',' ').title()})", message=f"Connecting to {target_ip_port}...")
        main_window.game_elements.clear()
        main_window.game_elements['initialization_in_progress'] = True
        main_window.game_elements['game_ready_for_logic'] = False
        initial_sw = float(main_window.game_scene_widget.width()) if main_window.game_scene_widget.width() > 1 else float(C.GAME_WIDTH)
        initial_sh = float(main_window.game_scene_widget.height()) if main_window.game_scene_widget.height() > 1 else float(C.GAME_HEIGHT)
        main_window.game_elements['camera'] = Camera(
            initial_level_width=initial_sw, initial_world_start_x=0.0,
            initial_world_start_y=0.0, initial_level_bottom_y_abs=initial_sh,
            screen_width=initial_sw, screen_height=initial_sh
        )
        debug(f"GAME_MODES DEBUG (prepare_and_start for JOIN): Basic camera created for join mode. ID: {id(main_window.game_elements.get('camera'))}")
        main_window.game_elements['camera_level_dims_set'] = False
        game_initialized_successfully = True # For join mode, success is provisional until map sync
    else:
        error(f"Unknown game mode: {mode}"); main_window.show_view("menu")
        if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
        return

    if not game_initialized_successfully:
        error(f"GAME_MODES: Game initialization failed for mode {mode} before camera setup block. Aborting.")
        _close_status_dialog(main_window); main_window.show_view("menu")
        if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
        return

    debug(f"GAME_MODES DEBUG (prepare_and_start): Entering camera setup block. Current camera type: {type(main_window.game_elements.get('camera'))}, ID: {id(main_window.game_elements.get('camera'))}")
    camera = main_window.game_elements.get("camera")
    game_scene_widget = main_window.game_scene_widget

    if not camera:
        critical("GAME_MODES CRITICAL: Camera object not found in game_elements after entity initialization or basic setup for join mode!")
        _close_status_dialog(main_window); main_window.show_view("menu")
        if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
        return
    if not game_scene_widget:
        critical("GAME_MODES CRITICAL: GameSceneWidget not found on main_window!")
        _close_status_dialog(main_window); main_window.show_view("menu")
        if hasattr(main_window, 'map_change_is_active'): main_window.map_change_is_active = False
        return

    actual_screen_w = float(game_scene_widget.width())
    actual_screen_h = float(game_scene_widget.height())
    if actual_screen_w <= 1 or actual_screen_h <= 1:
        actual_screen_w = float(main_window.width())
        actual_screen_h = float(main_window.height())
    
    debug(f"GAME_MODES DEBUG: Setting camera screen dimensions to: {actual_screen_w}x{actual_screen_h} BEFORE show_view.")
    camera.set_screen_dimensions(actual_screen_w, actual_screen_h)

    if mode in ["couch_play", "host_game"]:
        if main_window.game_elements.get('level_pixel_width') is not None:
            debug(f"GAME_MODES DEBUG: Setting camera level dimensions for {mode}.")
            camera.set_level_dimensions(
                level_total_width=main_window.game_elements['level_pixel_width'],
                level_min_x_abs=main_window.game_elements['level_min_x_absolute'],
                level_min_y_abs=main_window.game_elements['level_min_y_absolute'],
                level_max_y_abs=main_window.game_elements['level_max_y_absolute']
            )
            main_window.game_elements['camera_level_dims_set'] = True
            player1_focus = main_window.game_elements.get("player1")
            if player1_focus and hasattr(player1_focus, 'alive') and player1_focus.alive():
                camera.update(player1_focus)
            else:
                camera.static_update()
        else:
            warning(f"GAME_MODES WARNING: level_pixel_width not set in game_elements for {mode} after _initialize_game_entities. Camera may not be bounded correctly.")
    
    main_window.show_view("game_scene")
    QApplication.processEvents()
    debug("GAME_MODES DEBUG: show_view('game_scene') called.")

    if mode == "couch_play": _close_status_dialog(main_window); info("GAME_MODES: Couch play ready.")
    elif mode == "host_game":
        main_window.current_game_mode = "host_waiting"
        start_network_mode_logic(main_window, "host", map_to_host=map_name_folder_stem)
    elif mode in ["join_ip", "join_lan"]:
        start_network_mode_logic(main_window, "join", target_ip_port)

    # --- FINALIZATION AND FLAG RESET ---
    if hasattr(main_window, 'map_change_is_active') and main_window.map_change_is_active:
        if game_initialized_successfully and main_window.current_game_mode is not None :
            log_msg_suffix = f"for mode '{main_window.current_game_mode}'"
        else:
            log_msg_suffix = "(game initialization failed or mode is None after setup attempt)"
        debug(f"GAME_MODES (prepare_and_start): Resetting main_window.map_change_is_active flag {log_msg_suffix}.")
        main_window.map_change_is_active = False

def stop_current_game_mode_logic(main_window: 'MainWindow', show_menu: bool = True):
    current_mode_being_stopped = main_window.current_game_mode; info(f"GAME_MODES: Stopping current game mode: {current_mode_being_stopped}")
    if main_window.network_thread and main_window.network_thread.isRunning():
        info("GAME_MODES: Stopping network thread.")
        if main_window.server_state: main_window.server_state.app_running = False
        if main_window.client_state: main_window.client_state.app_running = False
        main_window.network_thread.quit()
        if not main_window.network_thread.wait(1000): main_window.network_thread.terminate(); main_window.network_thread.wait(200)
        main_window.network_thread = None; info("GAME_MODES: Network thread processing finished.")
    main_window.server_state = None; main_window.client_state = None; main_window.current_game_mode = None
    if 'game_elements' in main_window.__dict__:
        main_window.game_elements['initialization_in_progress'] = False; main_window.game_elements['game_ready_for_logic'] = False; main_window.game_elements['camera_level_dims_set'] = False
        main_window.game_elements.clear(); info("GAME_MODES: Cleared all game_elements.")
    _close_status_dialog(main_window)
    if hasattr(main_window, 'lan_search_dialog') and main_window.lan_search_dialog and main_window.lan_search_dialog.isVisible(): main_window.lan_search_dialog.reject()
    if hasattr(main_window, 'game_scene_widget') and hasattr(main_window.game_scene_widget, 'clear_scene_for_new_game'): main_window.game_scene_widget.clear_scene_for_new_game()
    if show_menu: main_window.show_view("menu")

    # If a map change was active and this stop is part of it, it should be reset by prepare_and_start.
    # If this stop is for other reasons (e.g., manual pause, game over), and map_change_is_active was somehow still true, reset it.
    if hasattr(main_window, 'map_change_is_active') and main_window.map_change_is_active:
        debug(f"GAME_MODES (stop_current_game_mode): Resetting main_window.map_change_is_active flag because mode '{current_mode_being_stopped}' is stopping.")
        main_window.map_change_is_active = False

    info(f"GAME_MODES: Game mode '{current_mode_being_stopped}' stopped and resources cleaned up.")

def start_network_mode_logic(main_window: 'MainWindow', mode_name: str, target_ip_port: Optional[str] = None, map_to_host: Optional[str] = None):
    info(f"GAME_MODES: Starting network mode: {mode_name}, MapToHost: {map_to_host}")
    if main_window.network_thread and main_window.network_thread.isRunning(): warning("GAME_MODES: Network thread already running. Stopping existing one first."); main_window.network_thread.quit(); main_window.network_thread.wait(500); main_window.network_thread = None
    ge_ref = main_window.game_elements
    if mode_name == "host":
        main_window.server_state = ServerState(); server_map_name_to_use = map_to_host if map_to_host else ge_ref.get('map_name', ge_ref.get('loaded_map_name', "unknown_map_at_host_start"))
        main_window.server_state.current_map_name = server_map_name_to_use; debug(f"GAME_MODES (Host): Server starting with map: {server_map_name_to_use}")
        main_window.network_thread = main_window.NetworkThread(mode="host", game_elements_ref=ge_ref, server_state_ref=main_window.server_state, parent=main_window)
    elif mode_name == "join":
        if not target_ip_port: error("GAME_MODES (Join): Target IP:Port required for join mode."); _update_status_dialog(main_window, title="Connection Error", message="No target IP specified.", progress=-1.0); return
        main_window.client_state = ClientState(); main_window.network_thread = main_window.NetworkThread(mode="join", game_elements_ref=ge_ref, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
    else: error(f"GAME_MODES: Unknown network mode specified: {mode_name}"); return
    if main_window.network_thread: main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot); main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot); main_window.network_thread.client_fully_synced_signal.connect(main_window.on_client_fully_synced_for_host); main_window.network_thread.start(); info(f"GAME_MODES: NetworkThread for '{mode_name}' started.")
    else: error(f"GAME_MODES: Failed to create NetworkThread for mode '{mode_name}'.")

def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'):
    info("GAME_MODES (Host): Client fully synced. Transitioning game to active state.")
    if main_window.current_game_mode == "host_waiting" and main_window.server_state: main_window.current_game_mode = "host_active"; main_window.server_state.client_ready = True; _close_status_dialog(main_window); info("GAME_MODES (Host): Client connected and synced. Game is now fully active for host.")
    else: warning(f"GAME_MODES: Received client_fully_synced_for_host in unexpected state: {main_window.current_game_mode}")

def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float):
    debug(f"GAME_MODES (Net Status Update): Title='{title}', Msg='{message}', Prog={progress}"); is_network_setup_phase = main_window.current_game_mode in ["host_waiting", "join_ip", "join_lan"]
    if progress == -2.0: _close_status_dialog(main_window); return
    if is_network_setup_phase:
        if not main_window.status_dialog or not main_window.status_dialog.isVisible(): _show_status_dialog(main_window, title, message)
        if main_window.status_dialog and main_window.status_dialog.isVisible(): _update_status_dialog(main_window, message=message, progress=progress, title=title)
    if main_window.current_view_name == "game_scene" and (main_window.current_game_mode == "join_active" or main_window.current_game_mode == "host_active"):
        if hasattr(main_window.game_scene_widget, 'update_game_state'):
            if "Downloading" in title or "Synchronizing Map" in title or "Map Error" in title: main_window.game_scene_widget.update_game_state(0, download_title=title, download_msg=message, download_prog=progress)
            else: main_window.game_scene_widget.update_game_state(0)
    if (title == "Client Map Sync" and "Map ready, starting game" in message and progress >= 99.9) or (title == "Server Hosting" and "Ready for game start" in message and progress >= 99.9 and main_window.current_game_mode == "host_waiting"):
        if main_window.current_game_mode == "join_lan" or main_window.current_game_mode == "join_ip": main_window.current_game_mode = "join_active"; info("GAME_MODES (Client): Map synced and server signaled start. Game active.")
        _close_status_dialog(main_window)

def on_network_operation_finished_logic(main_window: 'MainWindow', result_message: str):
    info(f"GAME_MODES: Network operation finished: {result_message}"); _close_status_dialog(main_window); current_mode_that_finished = str(main_window.current_game_mode)
    stop_current_game_mode_logic(main_window, show_menu=False)
    if result_message == "host_ended": QMessageBox.information(main_window, "Server Closed", "Game server session ended.")
    elif result_message == "client_ended": QMessageBox.information(main_window, "Disconnected", "Disconnected from server.")
    elif "error" in result_message.lower() or "failed" in result_message.lower(): err_type = "Server Error" if "host" in result_message or (current_mode_that_finished and "host" in current_mode_that_finished) else "Connection Error"; QMessageBox.critical(main_window, err_type, f"Network operation failed: {result_message}")
    main_window.show_view("menu")

_lan_search_thread_instance: Optional[LANServerSearchThread] = None
def on_lan_server_search_status_update_logic(main_window: 'MainWindow', data_tuple: Any):
    if not main_window.lan_search_dialog or not main_window.lan_search_dialog.isVisible() or not main_window.lan_search_status_label or not main_window.lan_servers_list_widget: info("LAN search status update received, but dialog is not visible. Ignoring."); return
    if not isinstance(data_tuple, tuple) or len(data_tuple) != 2: warning(f"Malformed data_tuple received in on_lan_server_search_status_update: {data_tuple}"); return
    status_key, data = data_tuple; debug(f"LAN Search Status Update: Key='{status_key}', Data='{str(data)[:150]}'")
    if status_key == "searching": main_window.lan_search_status_label.setText(str(data))
    elif status_key == "found":
        if isinstance(data, tuple) and len(data) == 3:
            ip, port, map_name_lan = data; item_text = f"Server at {ip}:{port} (Map: {map_name_lan if map_name_lan else 'Unknown'})"; found_existing = False
            for i in range(main_window.lan_servers_list_widget.count()):
                item = main_window.lan_servers_list_widget.item(i); existing_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(existing_data, tuple) and existing_data[0] == ip and existing_data[1] == port: item.setText(item_text); item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan)); found_existing = True; break
            if not found_existing: list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan)); main_window.lan_servers_list_widget.addItem(list_item)
            if hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            if main_window.lan_servers_list_widget.count() == 1 and main_window._lan_search_list_selected_idx == -1 : main_window._lan_search_list_selected_idx = 0
            _update_lan_search_list_focus(main_window)
    elif status_key == "timeout" or status_key == "error" or status_key == "cancelled": msg = str(data) if data else f"Search {status_key}."; main_window.lan_search_status_label.setText(f"{msg} No servers found." if main_window.lan_servers_list_widget.count() == 0 else f"{msg} Select a server or retry.")
    elif status_key == "final_result":
        if data is None and main_window.lan_servers_list_widget.count() == 0: main_window.lan_search_status_label.setText("Search complete. No servers found.")
        elif data is not None and isinstance(data, tuple) and len(data) == 2:
            ip, port = data; item_text_final = f"Server at {ip}:{port} (Map via TCP)"; found_existing_final = False
            for i in range(main_window.lan_servers_list_widget.count()):
                item = main_window.lan_servers_list_widget.item(i); existing_data_final = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(existing_data_final, tuple) and len(existing_data_final) >=2 and existing_data_final[0] == ip and existing_data_final[1] == port:
                    if main_window.lan_servers_list_widget.currentItem() != item: main_window.lan_servers_list_widget.setCurrentItem(item); main_window._lan_search_list_selected_idx = i
                    found_existing_final = True; break
            if not found_existing_final:
                list_item_final = QListWidgetItem(item_text_final); list_item_final.setData(Qt.ItemDataRole.UserRole, (ip, port, "Map via TCP"));
                main_window.lan_servers_list_widget.addItem(list_item_final); main_window.lan_servers_list_widget.setCurrentItem(list_item_final); main_window._lan_search_list_selected_idx = main_window.lan_servers_list_widget.count() -1
            _update_lan_search_list_focus(main_window); main_window.lan_search_status_label.setText("Search complete. Select a server.")
            if hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        else: main_window.lan_search_status_label.setText("Search complete. Select a server or retry.")

def start_lan_server_search_thread_logic(main_window: 'MainWindow'):
    global _lan_search_thread_instance; info("GAME_MODES: Starting LAN server search thread.")
    if _lan_search_thread_instance and _lan_search_thread_instance.isRunning(): info("LAN search already running. Stopping and restarting."); _lan_search_thread_instance.stop_search();
    if not (_lan_search_thread_instance and _lan_search_thread_instance.wait(500)):
        if _lan_search_thread_instance: _lan_search_thread_instance.terminate(); _lan_search_thread_instance.wait(100) # type: ignore
    _lan_search_thread_instance = None
    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Initializing search...")
    main_window._lan_search_list_selected_idx = -1
    if hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    _lan_search_thread_instance = LANServerSearchThread(main_window)
    _lan_search_thread_instance.search_event_signal.connect(main_window.on_lan_server_search_status_update_slot)
    _lan_search_thread_instance.finished.connect(_lan_search_thread_instance.deleteLater)
    _lan_search_thread_instance.start()

def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'):
    info("GAME_MODES: Attempting to join selected LAN server.")
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget: error("LAN dialog/list widget not available."); return
    selected_item = main_window.lan_servers_list_widget.currentItem()
    if not selected_item:
        if 0 <= main_window._lan_search_list_selected_idx < main_window.lan_servers_list_widget.count(): selected_item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
        else: QMessageBox.warning(main_window.lan_search_dialog, "No Server Selected", "Please select a server from the list to join."); return
    if not selected_item: QMessageBox.warning(main_window.lan_search_dialog, "Selection Error", "Could not retrieve selected server item."); return
    data = selected_item.data(Qt.ItemDataRole.UserRole)
    if not data or not isinstance(data, tuple) or len(data) < 2: error(f"Invalid server data associated with list item: {data}"); QMessageBox.critical(main_window.lan_search_dialog, "Error", "Invalid server data for selected item."); return
    ip, port = str(data[0]), int(data[1]); target_ip_port = f"{ip}:{port}"; info(f"Selected LAN server: {target_ip_port}")
    main_window.lan_search_dialog.accept(); setattr(main_window, 'current_modal_dialog', None)
    prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=target_ip_port)