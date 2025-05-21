# app_game_modes.py
# -*- coding: utf-8 -*-
"""
Handles game mode logic: initialization, starting/stopping modes,
managing network interactions, and UI dialogs for PySide6.
"""
# version 2.0.1 (Added BackgroundTile handling)
# version 2.0.2 (Ensured map_dir_path robustness, more logging for level_data)
# version 2.0.3 (Corrected _update_status_dialog arguments)

import os
import sys
import time
import random # For potential random elements like player colors
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# PySide6 imports
from PySide6.QtWidgets import QListWidgetItem, QDialogButtonBox, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt, QRectF, QPointF

# Project-specific imports
from logger import info, debug, warning, error, critical
import constants as C
import config as game_config

# UI Creator Imports
from app_ui_creator import (
    _show_status_dialog,
    _update_status_dialog, # This is the function signature we need to match
    _close_status_dialog,
    _show_lan_search_dialog,
    _update_lan_search_list_focus,
    _update_ip_dialog_button_focus
)

# Game logic and elements
from game_ui import IPInputDialog
from game_state_manager import reset_game_state
from player import Player
from enemy import Enemy
from statue import Statue
from items import Chest
from tiles import Platform, Ladder, Lava, BackgroundTile
from camera import Camera
from level_loader import LevelLoader

# Networking
from server_logic import ServerState
from client_logic import ClientState

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any


class LANServerSearchThread(QThread):
    found_server_signal = Signal(str, str, int, str)
    search_status_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        self._running = True
        self.search_status_signal.emit("Searching for LAN games...")
        info("LAN_SEARCH_THREAD: Placeholder search started.")
        time.sleep(1)
        time.sleep(1.5)

        if self._running:
            self.search_status_signal.emit("No LAN games found. Retry or enter IP manually.")
        info("LAN_SEARCH_THREAD: Placeholder search finished.")
        self._running = False

    def stop(self):
        self._running = False
        self.search_status_signal.emit("Search stopped.")


def _initialize_game_entities(main_window: 'MainWindow', map_name: str, mode: str) -> bool:
    info(f"GAME_MODES: Initializing game entities for map '{map_name}' in mode '{mode}'.")
    reset_game_state(main_window.game_elements)

    try:
        level_loader = LevelLoader()
        maps_dir_path = str(getattr(C, "MAPS_DIR", "maps"))
        if not os.path.isabs(maps_dir_path):
            project_root_path = getattr(C, 'PROJECT_ROOT', None)
            if project_root_path is None:
                project_root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if not os.path.isdir(os.path.join(str(project_root_path), maps_dir_path)):
                    project_root_path = os.path.dirname(os.path.abspath(__file__))
                warning(f"C.PROJECT_ROOT not defined. Guessed project root for maps: {project_root_path}")
            maps_dir_path = os.path.join(str(project_root_path), maps_dir_path)
            info(f"GAME_MODES: Resolved relative MAPS_DIR to absolute: {maps_dir_path}")

        info(f"Attempting to load map '{map_name}' from directory '{maps_dir_path}' (using .py loader)")
        level_data = level_loader.load_map(map_name, maps_dir_path)

        if not level_data or not isinstance(level_data, dict):
            error_msg_detail = f"LevelLoader returned type: {type(level_data)}" if level_data is not None else "LevelLoader returned None."
            error_msg = f"Failed to load map data for '{map_name}'. Ensure 'maps/{map_name}.py' exists and defines 'load_map_{map_name.replace('-', '_').replace(' ', '_')}()' returning a dict. {error_msg_detail}"
            error(error_msg)
            _update_status_dialog(main_window,
                                  title="Map Load Error",
                                  message=error_msg,
                                  progress=-1.0)
            return False

        main_window.game_elements['map_name'] = map_name
        main_window.game_elements['level_data'] = level_data
        debug(f"GAME_MODES: level_data for '{map_name}' loaded. Keys: {list(level_data.keys())}")
        if 'items_list' in level_data:
            debug(f"GAME_MODES: Initial items_list from level_data: {level_data['items_list']}")
        else:
            debug("GAME_MODES: No 'items_list' found in loaded level_data.")

        main_window.game_elements['platforms_list'] = []
        main_window.game_elements['ladders_list'] = []
        main_window.game_elements['hazards_list'] = []
        main_window.game_elements['background_tiles_list'] = []
        main_window.game_elements['enemy_list'] = []
        main_window.game_elements['statue_objects'] = []
        main_window.game_elements['collectible_list'] = []
        main_window.game_elements['projectiles_list'] = []
        main_window.game_elements['all_renderable_objects'] = []

        for p_data in level_data.get('platforms_list', []):
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                plat = Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                color_tuple=tuple(p_data.get('color', C.GRAY)),
                                platform_type=str(p_data.get('type', 'generic_platform')),
                                properties=p_data.get('properties', {}))
                main_window.game_elements['platforms_list'].append(plat)
                main_window.game_elements['all_renderable_objects'].append(plat)

        for l_data in level_data.get('ladders_list', []):
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                lad = Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                             width=float(rect_tuple[2]), height=float(rect_tuple[3]))
                main_window.game_elements['ladders_list'].append(lad)
                main_window.game_elements['all_renderable_objects'].append(lad)

        for h_data in level_data.get('hazards_list', []):
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                if str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower():
                    lava = Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                color_tuple=tuple(h_data.get('color', C.ORANGE_RED)))
                    main_window.game_elements['hazards_list'].append(lava)
                    main_window.game_elements['all_renderable_objects'].append(lava)

        for bg_data in level_data.get('background_tiles_list', []):
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                bg_tile = BackgroundTile(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                         width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                         color_tuple=tuple(bg_data.get('color', C.DARK_GRAY)),
                                         tile_type=str(bg_data.get('type', 'generic_background')),
                                         image_path=bg_data.get('image_path'),
                                         properties=bg_data.get('properties', {}))
                main_window.game_elements['background_tiles_list'].append(bg_tile)
                main_window.game_elements['all_renderable_objects'].append(bg_tile)

        p1_start_pos_tuple = tuple(level_data.get('player_start_pos_p1', (50.0, float(C.GAME_HEIGHT - C.TILE_SIZE * 2))))
        player1_props = level_data.get('player1_spawn_props', {})
        player1 = Player(p1_start_pos_tuple[0], p1_start_pos_tuple[1], 1, initial_properties=player1_props)
        main_window.game_elements['player1'] = player1
        if player1._valid_init: main_window.game_elements['all_renderable_objects'].append(player1)
        else: critical(f"P1 failed to initialize for map {map_name}"); return False
        player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE

        if mode in ["couch_play", "join_ip", "join_lan", "host"]:
            p2_start_pos_tuple = tuple(level_data.get('player_start_pos_p2', (100.0, float(C.GAME_HEIGHT - C.TILE_SIZE * 2))))
            player2_props = level_data.get('player2_spawn_props', {})
            player2 = Player(p2_start_pos_tuple[0], p2_start_pos_tuple[1], 2, initial_properties=player2_props)
            main_window.game_elements['player2'] = player2
            if player2._valid_init: main_window.game_elements['all_renderable_objects'].append(player2)
            else: warning(f"P2 failed to initialize for map {map_name} in mode {mode}.")
            if mode != "host":
                player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
        else:
             main_window.game_elements['player2'] = None

        ge_ref_for_proj = {
            "projectiles_list": main_window.game_elements['projectiles_list'],
            "all_renderable_objects": main_window.game_elements['all_renderable_objects'],
            "platforms_list": main_window.game_elements['platforms_list']
        }
        if player1: player1.game_elements_ref_for_projectiles = ge_ref_for_proj
        player2_ref = main_window.game_elements.get('player2')
        if player2_ref: player2_ref.game_elements_ref_for_projectiles = ge_ref_for_proj

        main_window.game_elements['enemy_spawns_data_cache'] = level_data.get('enemies_list', [])
        if mode in ["host_game", "couch_play"]:
            for i, e_data in enumerate(main_window.game_elements['enemy_spawns_data_cache']):
                try:
                    start_pos = tuple(map(float, e_data.get('start_pos', (100.0, 100.0))))
                    enemy_type = str(e_data.get('type', 'enemy_green'))
                    patrol_raw = e_data.get('patrol_rect_data')
                    patrol_qrectf: Optional[QRectF] = None
                    if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                        patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']),
                                               float(patrol_raw['width']), float(patrol_raw['height']))
                    enemy = Enemy(start_x=start_pos[0], start_y=start_pos[1],
                                  patrol_area=patrol_qrectf, enemy_id=i,
                                  color_name=enemy_type, properties=e_data.get('properties', {}))
                    if enemy._valid_init:
                        main_window.game_elements['enemy_list'].append(enemy)
                        main_window.game_elements['all_renderable_objects'].append(enemy)
                except Exception as ex_enemy: error(f"Error spawning enemy {i}: {ex_enemy}", exc_info=True)

        main_window.game_elements['statue_spawns_data_cache'] = level_data.get('statues_list', [])
        if mode in ["host_game", "couch_play"]:
            for i, s_data in enumerate(main_window.game_elements['statue_spawns_data_cache']):
                try:
                    statue_pos = tuple(map(float, s_data.get('pos', (200.0, 200.0))))
                    statue = Statue(center_x=statue_pos[0], center_y=statue_pos[1],
                                    statue_id=s_data.get('id', f"statue_{i}"),
                                    properties=s_data.get('properties', {}))
                    if statue._valid_init:
                        main_window.game_elements['statue_objects'].append(statue)
                        main_window.game_elements['all_renderable_objects'].append(statue)
                except Exception as ex_statue: error(f"Error spawning statue {i}: {ex_statue}", exc_info=True)

        if mode in ["host_game", "couch_play"]:
            main_window.game_elements['current_chest'] = None
            for i_data in level_data.get('items_list', []):
                if str(i_data.get('type', '')).lower() == 'chest':
                    try:
                        chest_pos = tuple(map(float, i_data.get('pos', (300.0, 300.0))))
                        chest = Chest(x=chest_pos[0], y=chest_pos[1])
                        if chest._valid_init:
                            main_window.game_elements['collectible_list'].append(chest)
                            main_window.game_elements['all_renderable_objects'].append(chest)
                            main_window.game_elements['current_chest'] = chest
                            debug(f"GAME_MODES: Initial chest spawned at ({chest_pos[0]}, {chest_pos[1]})")
                        else:
                            warning("GAME_MODES: Initial map-defined chest failed to initialize.")
                    except Exception as ex_item: error(f"Error spawning item (chest): {ex_item}", exc_info=True)

        lvl_total_width = float(level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
        lvl_min_x_abs = float(level_data.get('level_min_x_absolute', 0.0))
        lvl_min_y_abs = float(level_data.get('level_min_y_absolute', 0.0))
        lvl_max_y_abs = float(level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
        initial_screen_width = float(main_window.game_scene_widget.width())
        initial_screen_height = float(main_window.game_scene_widget.height())
        if initial_screen_width <= 1: initial_screen_width = float(C.GAME_WIDTH)
        if initial_screen_height <= 1: initial_screen_height = float(C.GAME_HEIGHT)
        camera_instance = Camera(initial_level_width=lvl_total_width, initial_world_start_x=lvl_min_x_abs,
                                 initial_world_start_y=lvl_min_y_abs, initial_level_bottom_y_abs=lvl_max_y_abs,
                                 screen_width=initial_screen_width, screen_height=initial_screen_height)
        main_window.game_elements['camera'] = camera_instance
        main_window.game_elements['camera_level_dims_set'] = True

        main_window.game_elements['level_pixel_width'] = lvl_total_width
        main_window.game_elements['level_min_x_absolute'] = lvl_min_x_abs
        main_window.game_elements['level_min_y_absolute'] = lvl_min_y_abs
        main_window.game_elements['level_max_y_absolute'] = lvl_max_y_abs
        main_window.game_elements['level_background_color'] = tuple(level_data.get('background_color', C.LIGHT_BLUE))
        main_window.game_elements['ground_level_y_ref'] = float(level_data.get('ground_level_y_ref', lvl_max_y_abs - C.TILE_SIZE))
        main_window.game_elements['ground_platform_height_ref'] = float(level_data.get('ground_platform_height_ref', C.TILE_SIZE))

        if hasattr(main_window.game_scene_widget, 'set_level_dimensions'):
            main_window.game_scene_widget.set_level_dimensions(lvl_total_width, lvl_min_x_abs, lvl_min_y_abs, lvl_max_y_abs)

        info("GAME_MODES: Game entities initialized successfully.")
        return True

    except Exception as e:
        critical(f"Exception during game entity initialization for map '{map_name}': {e}", exc_info=True)
        _update_status_dialog(main_window, title="Game Init Error", message=f"Critical error initializing game: {e}", progress=-1.0)
        return False


def initiate_couch_play_map_selection(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating map selection for Couch Co-op.")
    if main_window.map_select_title_label:
        main_window.map_select_title_label.setText("Select Map (Couch Co-op)")
    main_window._populate_map_list_for_selection("couch_coop")
    main_window.show_view("map_select")

def initiate_host_game_map_selection(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating map selection for Hosting Game.")
    if main_window.map_select_title_label:
        main_window.map_select_title_label.setText("Select Map to Host")
    main_window._populate_map_list_for_selection("host_game")
    main_window.show_view("map_select")

def start_couch_play_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Couch Co-op with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "couch_play", map_name)

def start_host_game_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Host Game with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "host_game", map_name)

def initiate_join_lan_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join LAN Dialog.")
    _show_lan_search_dialog(main_window)

def initiate_join_ip_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join by IP Dialog.")
    if main_window.ip_input_dialog is None:
        main_window.ip_input_dialog = IPInputDialog(parent=main_window)
        main_window.ip_input_dialog.accepted.connect(
            lambda: prepare_and_start_game_logic(
                main_window, "join_ip",
                target_ip_port=str(main_window.ip_input_dialog.ip_port_string) if main_window.ip_input_dialog else ""
            )
        )
        main_window.ip_input_dialog.rejected.connect(
            lambda: (main_window.show_view("menu"), setattr(main_window, 'current_modal_dialog', None))
        )
        ok_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        main_window._ip_dialog_buttons_ref = [btn for btn in [ok_button, cancel_button] if btn]

    main_window.current_modal_dialog = "ip_input"
    main_window._ip_dialog_selected_button_idx = 0
    _update_ip_dialog_button_focus(main_window)
    main_window.ip_input_dialog.clear_input_and_focus()
    main_window.ip_input_dialog.show()


def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Preparing game. Mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
    main_window.current_game_mode = mode
    main_window.game_elements['camera_level_dims_set'] = False

    if mode in ["couch_play", "host_game"]:
        if not map_name:
            error("Map name required for couch_play/host_game."); return
        _show_status_dialog(main_window, f"Starting {mode.replace('_',' ').title()}", f"Loading map: {map_name}...")
        if not _initialize_game_entities(main_window, map_name, mode):
            error(f"Failed to initialize game entities for map '{map_name}'. Mode '{mode}'.");
            _close_status_dialog(main_window);
            main_window.show_view("menu"); return
        _update_status_dialog(main_window, message="Entities initialized successfully.", progress=50.0, title="Entities initialized.")
    elif mode in ["join_ip", "join_lan"]:
        if not target_ip_port:
            error("Target IP:Port required."); return
        _show_status_dialog(main_window, f"Joining Game ({mode.replace('_',' ').title()})", f"Connecting to {target_ip_port}...")
        reset_game_state(main_window.game_elements)
        initial_sw = float(main_window.game_scene_widget.width()) if main_window.game_scene_widget.width() > 1 else float(C.GAME_WIDTH)
        initial_sh = float(main_window.game_scene_widget.height()) if main_window.game_scene_widget.height() > 1 else float(C.GAME_HEIGHT)
        main_window.game_elements['camera'] = Camera(
            initial_level_width=float(C.GAME_WIDTH), initial_world_start_x=0.0,
            initial_world_start_y=0.0, initial_level_bottom_y_abs=float(C.GAME_HEIGHT),
            screen_width=initial_sw, screen_height=initial_sh
        )
    else:
        error(f"Unknown game mode: {mode}"); main_window.show_view("menu"); return

    if mode == "couch_play":
        _close_status_dialog(main_window)
        main_window.show_view("game_scene")
    elif mode == "host_game":
        main_window.current_game_mode = "host_waiting"
        _update_status_dialog(main_window, message="Server starting. Waiting for client...", progress=75.0, title="Starting server...")
        start_network_mode_logic(main_window, "host")
        main_window.show_view("game_scene")
    elif mode in ["join_ip", "join_lan"]:
        _update_status_dialog(main_window, message=f"Attempting to connect to {target_ip_port}...", progress=0.0, title="Connecting...")
        start_network_mode_logic(main_window, "join", target_ip_port)

def stop_current_game_mode_logic(main_window: 'MainWindow', show_menu: bool = True):
    info(f"GAME_MODES: Stopping current game mode: {main_window.current_game_mode}")
    if main_window.network_thread and main_window.network_thread.isRunning():
        info("GAME_MODES: Stopping network thread...")
        if main_window.server_state: main_window.server_state.app_running = False
        if main_window.client_state: main_window.client_state.app_running = False
        if not main_window.network_thread.wait(1000):
            warning("Network thread did not terminate gracefully, forcing."); main_window.network_thread.terminate(); main_window.network_thread.wait()
        main_window.network_thread = None; info("GAME_MODES: Network thread stopped.")
    main_window.server_state = None; main_window.client_state = None
    reset_game_state(main_window.game_elements);
    main_window.current_game_mode = None
    main_window.game_elements['camera_level_dims_set'] = False
    _close_status_dialog(main_window)
    if hasattr(main_window.game_scene_widget, 'clear_scene_for_new_game'): main_window.game_scene_widget.clear_scene_for_new_game()
    if show_menu: main_window.show_view("menu")
    info("GAME_MODES: Game mode stopped and resources cleaned up.")

def start_network_mode_logic(main_window: 'MainWindow', mode_name: str, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Starting network mode: {mode_name}")
    if main_window.network_thread and main_window.network_thread.isRunning():
        warning("GAME_MODES: Network thread running. Stopping existing first."); stop_current_game_mode_logic(main_window, show_menu=False)
    ge_ref = main_window.game_elements
    if mode_name == "host":
        main_window.server_state = ServerState();
        server_map_name = ge_ref.get('map_name', 'unknown_map_server_default')
        main_window.server_state.current_map_name = server_map_name
        main_window.network_thread = main_window.NetworkThread(mode="host", game_elements_ref=ge_ref, server_state_ref=main_window.server_state, parent=main_window)
        # _update_status_dialog call moved to prepare_and_start_game_logic
    elif mode_name == "join":
        if not target_ip_port: error("Target IP:Port required for join."); _update_status_dialog(main_window, title="Connection Error", message="No target IP.", progress=-1.0); return
        main_window.client_state = ClientState()
        main_window.network_thread = main_window.NetworkThread(mode="join", game_elements_ref=ge_ref, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
        # _update_status_dialog call moved to prepare_and_start_game_logic
    else: error(f"Unknown network mode: {mode_name}"); return

    main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot)
    main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot)
    main_window.network_thread.client_fully_synced_signal.connect(main_window.on_client_fully_synced_for_host)
    main_window.network_thread.start(); info(f"GAME_MODES: NetworkThread for '{mode_name}' started.")

def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'):
    info("GAME_MODES (Host): Client fully synced. Transitioning to active game.")
    if main_window.current_game_mode == "host_waiting" and main_window.server_state:
        main_window.current_game_mode = "host_active"
        main_window.server_state.client_ready = True
        _close_status_dialog(main_window)
        info("Client connected and synced. Game is active for host.")
    else: warning(f"GAME_MODES: Received client_fully_synced in unexpected state: {main_window.current_game_mode}")

def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float):
    debug(f"GAME_MODES (Net Status Update): Title='{title}', Msg='{message}', Prog={progress}")
    is_net_mode = main_window.current_game_mode in ["host_game", "host_waiting", "host_active", "join_ip", "join_lan", "join_active"]

    if progress == -2.0:
        _close_status_dialog(main_window)
    elif (not main_window.status_dialog or not main_window.status_dialog.isVisible()) and is_net_mode:
        _show_status_dialog(main_window, title, message) # Show if not visible, pass title here
    
    # Update existing dialog if visible
    if main_window.status_dialog and main_window.status_dialog.isVisible():
         _update_status_dialog(main_window, message=message, progress=progress, title=title)


def on_network_operation_finished_logic(main_window: 'MainWindow', result_message: str):
    info(f"GAME_MODES: Network op finished: {result_message}")
    _close_status_dialog(main_window)
    current_mode_stopped = str(main_window.current_game_mode)

    if result_message == "client_initial_sync_complete":
        info("Client initial sync complete. Showing game scene.");
        main_window.current_game_mode = "join_active"
        main_window.show_view("game_scene");
        return

    stop_current_game_mode_logic(main_window, show_menu=False)

    if result_message == "host_ended":
        QMessageBox.information(main_window, "Server Closed", "Game server closed.")
    elif result_message == "client_ended":
        QMessageBox.information(main_window, "Disconnected", "Disconnected from server.")
    elif "error" in result_message.lower() or "failed" in result_message.lower():
        err_type = "Server Error" if "host" in result_message or (current_mode_stopped and "host" in current_mode_stopped) else "Connection Error"
        QMessageBox.critical(main_window, err_type, f"Network operation failed: {result_message}")

    main_window.show_view("menu")

_lan_search_thread_instance: Optional[LANServerSearchThread] = None
def on_lan_server_search_status_update_logic(main_window: 'MainWindow', data: Any):
    if not main_window.lan_search_dialog or not main_window.lan_search_dialog.isVisible() or \
       not main_window.lan_search_status_label or not main_window.lan_servers_list_widget:
        return

    if isinstance(data, str):
        main_window.lan_search_status_label.setText(data)
    elif isinstance(data, tuple) and len(data) == 4:
        s_name, ip, port, map_name = data
        item_text = f"{s_name} ({ip}:{port}) - Map: {map_name}"
        list_item = QListWidgetItem(item_text)
        list_item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name))
        main_window.lan_servers_list_widget.addItem(list_item)
        if main_window.lan_servers_list_widget.count() == 1:
            main_window._lan_search_list_selected_idx = 0
        _update_lan_search_list_focus(main_window)
        main_window.lan_search_status_label.setText(f"Found: {s_name}. Searching...")
    else:
        warning(f"Malformed LAN server data received: {data}")

def start_lan_server_search_thread_logic(main_window: 'MainWindow'):
    global _lan_search_thread_instance
    info("GAME_MODES: Starting LAN server search.")
    if _lan_search_thread_instance and _lan_search_thread_instance.isRunning():
        info("LAN search already running. Stopping and restarting.");
        _lan_search_thread_instance.stop()
        _lan_search_thread_instance.wait(500)

    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Initializing search...")
    main_window._lan_search_list_selected_idx = -1

    _lan_search_thread_instance = LANServerSearchThread(main_window)
    _lan_search_thread_instance.found_server_signal.connect(main_window.lan_server_search_status)
    _lan_search_thread_instance.search_status_signal.connect(main_window.lan_server_search_status)
    _lan_search_thread_instance.start()

def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'):
    info("GAME_MODES: Attempting to join selected LAN server.")
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget:
        error("LAN dialog/list widget not available."); return

    selected_row_index = main_window._lan_search_list_selected_idx
    if selected_row_index < 0 or selected_row_index >= main_window.lan_servers_list_widget.count():
        QMessageBox.warning(main_window.lan_search_dialog, "No Server Selected", "Please select a server from the list.")
        return

    item = main_window.lan_servers_list_widget.item(selected_row_index)
    if not item:
        QMessageBox.warning(main_window.lan_search_dialog, "Selection Error", "Could not retrieve selected server item.")
        return

    data = item.data(Qt.ItemDataRole.UserRole)
    if not data or not isinstance(data, tuple) or len(data) < 2:
        error(f"Invalid server data associated with list item: {data}")
        QMessageBox.critical(main_window.lan_search_dialog, "Error", "Invalid server data.")
        return

    ip, port, map_name_lan = str(data[0]), int(data[1]), str(data[2]) if len(data) > 2 else "Unknown"
    target_ip_port = f"{ip}:{port}"
    info(f"Selected LAN server: {target_ip_port}, Map: {map_name_lan}")

    main_window.lan_search_dialog.accept()
    setattr(main_window, 'current_modal_dialog', None)

    prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=target_ip_port)