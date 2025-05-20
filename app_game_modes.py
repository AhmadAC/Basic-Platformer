# app_game_modes.py
import os
import sys
import time
import random # For potential random elements like player colors
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# PySide6 imports
from PySide6.QtWidgets import QListWidgetItem, QDialogButtonBox, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt, QRectF, QPointF # Added QRectF, QPointF

# Project-specific imports
from logger import info, debug, warning, error, critical # Use critical from logger
import constants as C
import config as game_config

# UI Creator Imports
from app_ui_creator import (
    _show_status_dialog,
    _update_status_dialog,
    _close_status_dialog,
    _show_lan_search_dialog,
    _update_lan_search_list_focus,
    _update_ip_dialog_button_focus
)

# Game logic and elements
from game_ui import IPInputDialog
from game_state_manager import reset_game_state
from player import Player
# --- ADD THESE IMPORTS for game object classes ---
from enemy import Enemy
from statue import Statue
from items import Chest
from tiles import Platform, Ladder, Lava
# --- END OF ADDED IMPORTS ---
from camera import Camera # Your PySide6 Camera
from level_loader import LevelLoader # Ensure this exists and works

# Networking
from server_logic import ServerState
from client_logic import ClientState

# Tiles for populating all_renderable_objects correctly
from tiles import Platform, Ladder, Lava # Assuming these are your tile classes

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any

# --- Placeholder for LAN Server Discovery Thread (same as before) ---
class LANServerSearchThread(QThread):
    found_server_signal = Signal(str, str, int, str) # server_name, ip, port, map_name
    search_status_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        self._running = True
        self.search_status_signal.emit("Searching for LAN games...")
        info("LAN_SEARCH_THREAD: Placeholder search started.")
        time.sleep(2)
        if self._running:
            # self.found_server_signal.emit("Dummy LAN Game", "127.0.0.1", C.SERVER_PORT_TCP, "original")
            # self.search_status_signal.emit("Found 1 server. Still searching...")
            pass
        if self._running:
            time.sleep(1)
            self.search_status_signal.emit("No LAN games found. Retry or enter IP manually.")
        info("LAN_SEARCH_THREAD: Placeholder search finished.")
        self._running = False

    def stop(self):
        self._running = False
        self.search_status_signal.emit("Search stopped.")


# --- Game Initialization Helper ---
def _initialize_game_entities(main_window: 'MainWindow', map_name: str, mode: str) -> bool:
    info(f"GAME_MODES: Initializing game entities for map '{map_name}' in mode '{mode}'.")
    reset_game_state(main_window.game_elements) # Clears and prepares game_elements

    try:
        level_loader = LevelLoader()
        maps_dir_path = C.MAPS_DIR # Assumes C.MAPS_DIR is absolute or resolvable
        if not os.path.isabs(maps_dir_path):
             # If C.MAPS_DIR is relative, assume it's relative to project root
             project_root = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
             maps_dir_path = os.path.join(project_root, maps_dir_path)
        
        info(f"Attempting to load map '{map_name}' from directory '{maps_dir_path}'")
        level_data = level_loader.load_map(map_name, maps_dir_path)

        if not level_data:
            error_msg = f"Failed to load map data for '{map_name}'. Ensure '{map_name}.json' exists in '{maps_dir_path}'."
            error(error_msg)
            _update_status_dialog(main_window, "Map Load Error", error_msg, -1)
            QMessageBox.critical(main_window, "Map Load Error", error_msg)
            return False

        main_window.game_elements['map_name'] = map_name
        main_window.game_elements['level_data'] = level_data # Keep raw data if needed

        # Initialize lists in game_elements
        main_window.game_elements['platforms_list'] = []
        main_window.game_elements['ladders_list'] = []
        main_window.game_elements['hazards_list'] = []
        main_window.game_elements['enemy_list'] = []
        main_window.game_elements['statue_objects'] = []
        main_window.game_elements['collectible_list'] = []
        main_window.game_elements['projectiles_list'] = []
        main_window.game_elements['all_renderable_objects'] = []


        # --- Populate Game World Entities from Level Data ---
        # Platforms
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
        
        # Ladders
        for l_data in level_data.get('ladders_list', []):
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                lad = Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                             width=float(rect_tuple[2]), height=float(rect_tuple[3]))
                main_window.game_elements['ladders_list'].append(lad)
                main_window.game_elements['all_renderable_objects'].append(lad)

        # Hazards (e.g., Lava)
        for h_data in level_data.get('hazards_list', []):
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                if str(h_data.get('type', '')).lower() == 'lava': # Example check
                    lava = Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                color_tuple=tuple(h_data.get('color', C.ORANGE_RED)))
                    main_window.game_elements['hazards_list'].append(lava)
                    main_window.game_elements['all_renderable_objects'].append(lava)
        
        # Player 1
        p1_start_pos_tuple = tuple(level_data.get('player_start_pos_p1', (50.0, float(C.GAME_HEIGHT - C.TILE_SIZE * 2))))
        player1_props = level_data.get('player1_spawn_props', {})
        player1 = Player(p1_start_pos_tuple[0], p1_start_pos_tuple[1], 1, initial_properties=player1_props)
        main_window.game_elements['player1'] = player1
        if player1._valid_init: main_window.game_elements['all_renderable_objects'].append(player1)
        else: critical(f"P1 failed to initialize for map {map_name}"); return False

        # Player 2
        if mode in ["couch_play", "join_ip", "join_lan", "host"]: # Host also needs P2 instance for server logic
            p2_start_pos_tuple = tuple(level_data.get('player_start_pos_p2', (100.0, float(C.GAME_HEIGHT - C.TILE_SIZE * 2))))
            player2_props = level_data.get('player2_spawn_props', {})
            player2 = Player(p2_start_pos_tuple[0], p2_start_pos_tuple[1], 2, initial_properties=player2_props)
            main_window.game_elements['player2'] = player2
            if player2._valid_init: main_window.game_elements['all_renderable_objects'].append(player2)
            else: warning(f"P2 failed to initialize for map {map_name} in mode {mode}.") # Non-critical for host initially
        else:
             main_window.game_elements['player2'] = None

        # Pass game elements reference to players for projectile spawning
        ge_ref_for_proj = {
            "projectiles_list": main_window.game_elements['projectiles_list'],
            "all_renderable_objects": main_window.game_elements['all_renderable_objects'],
            "platforms_list": main_window.game_elements['platforms_list']
        }
        if player1: player1.game_elements_ref_for_projectiles = ge_ref_for_proj
        player2_ref = main_window.game_elements.get('player2')
        if player2_ref: player2_ref.game_elements_ref_for_projectiles = ge_ref_for_proj


        # Enemies (Only for host or couch_play, client receives from server)
        if mode in ["host_game", "couch_play"]:
            for i, e_data in enumerate(level_data.get('enemies_list', [])):
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

        # Statues (Host/Couch)
        if mode in ["host_game", "couch_play"]:
            from statue import Statue # Local import if not globally available
            for i, s_data in enumerate(level_data.get('statues_list', [])):
                try:
                    statue_pos = tuple(map(float, s_data.get('pos', (200.0, 200.0))))
                    statue = Statue(center_x=statue_pos[0], center_y=statue_pos[1],
                                    statue_id=s_data.get('id', f"statue_{i}"),
                                    properties=s_data.get('properties', {}))
                    if statue._valid_init:
                        main_window.game_elements['statue_objects'].append(statue)
                        main_window.game_elements['all_renderable_objects'].append(statue)
                except Exception as ex_statue: error(f"Error spawning statue {i}: {ex_statue}", exc_info=True)

        # Items (e.g., Chest) (Host/Couch)
        if mode in ["host_game", "couch_play"]:
            from items import Chest # Local import if not globally available
            for i_data in level_data.get('items_list', []):
                if str(i_data.get('type', '')).lower() == 'chest':
                    try:
                        chest_pos = tuple(map(float, i_data.get('pos', (300.0, 300.0))))
                        chest = Chest(x=chest_pos[0], y=chest_pos[1]) # Chest constructor expects midbottom
                        if chest._valid_init:
                            main_window.game_elements['collectible_list'].append(chest)
                            main_window.game_elements['all_renderable_objects'].append(chest)
                            main_window.game_elements['current_chest'] = chest # Assume one chest for now
                    except Exception as ex_item: error(f"Error spawning item (chest): {ex_item}", exc_info=True)


        # --- Camera Initialization ---
        lvl_total_width = float(level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
        lvl_min_x_abs = float(level_data.get('level_min_x_absolute', 0.0))
        lvl_min_y_abs = float(level_data.get('level_min_y_absolute', 0.0))
        lvl_max_y_abs = float(level_data.get('level_max_y_absolute', C.GAME_HEIGHT))

        initial_screen_width = float(main_window.game_scene_widget.width())
        initial_screen_height = float(main_window.game_scene_widget.height())
        if initial_screen_width <= 1: initial_screen_width = float(C.GAME_WIDTH)
        if initial_screen_height <= 1: initial_screen_height = float(C.GAME_HEIGHT)

        camera_instance = Camera(
            initial_level_width=lvl_total_width, initial_world_start_x=lvl_min_x_abs,
            initial_world_start_y=lvl_min_y_abs, initial_level_bottom_y_abs=lvl_max_y_abs,
            screen_width=initial_screen_width, screen_height=initial_screen_height
        )
        main_window.game_elements['camera'] = camera_instance
        
        # Store level dimensions in game_elements for access by GameSceneWidget or other systems
        main_window.game_elements['level_pixel_width'] = lvl_total_width
        main_window.game_elements['level_min_x_absolute'] = lvl_min_x_abs
        main_window.game_elements['level_min_y_absolute'] = lvl_min_y_abs
        main_window.game_elements['level_max_y_absolute'] = lvl_max_y_abs
        main_window.game_elements['level_background_color'] = tuple(level_data.get('background_color', C.LIGHT_BLUE))
        main_window.game_elements['ground_level_y_ref'] = float(level_data.get('ground_level_y_ref', lvl_max_y_abs - C.TILE_SIZE)) # Fallback
        main_window.game_elements['ground_platform_height_ref'] = float(level_data.get('ground_platform_height_ref', C.TILE_SIZE)) # Fallback

        # If GameSceneWidget needs to be explicitly told about the new level dimensions
        if hasattr(main_window.game_scene_widget, 'set_level_dimensions'):
            main_window.game_scene_widget.set_level_dimensions(
                lvl_total_width, lvl_min_x_abs, lvl_min_y_abs, lvl_max_y_abs
            )

        info("GAME_MODES: Game entities initialized successfully.")
        return True

    except Exception as e:
        critical(f"Exception during game entity initialization for map '{map_name}': {e}", exc_info=True)
        _update_status_dialog(main_window, f"Error: Critical error initializing game: {e}", -1)
        QMessageBox.critical(main_window, "Game Init Error", f"A critical error occurred: {e}")
        return False


# --- Map Selection Initiators ---
def initiate_couch_play_map_selection(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating map selection for Couch Co-op.")
    if main_window.map_select_title_label:
        main_window.map_select_title_label.setText("Select Map (Couch Co-op)")
    main_window._populate_map_list_for_selection("couch_coop") # MainWindow method
    main_window.show_view("map_select")

def initiate_host_game_map_selection(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating map selection for Hosting Game.")
    if main_window.map_select_title_label:
        main_window.map_select_title_label.setText("Select Map to Host")
    main_window._populate_map_list_for_selection("host_game") # MainWindow method
    main_window.show_view("map_select")

# --- Game Start Triggers ---
def start_couch_play_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Couch Co-op with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "couch_play", map_name)

def start_host_game_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Host Game with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "host_game", map_name)

# --- Dialog Initiators ---
def initiate_join_lan_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join LAN Dialog.")
    _show_lan_search_dialog(main_window) # from app_ui_creator

def initiate_join_ip_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join by IP Dialog.")
    if main_window.ip_input_dialog is None:
        main_window.ip_input_dialog = IPInputDialog(parent=main_window) # Ensure parent is passed
        main_window.ip_input_dialog.accepted.connect(
            lambda: prepare_and_start_game_logic(
                main_window, "join_ip",
                target_ip_port=main_window.ip_input_dialog.ip_port_string # Use property from dialog
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
    _update_ip_dialog_button_focus(main_window) # from app_ui_creator
    main_window.ip_input_dialog.clear_input_and_focus()
    main_window.ip_input_dialog.show()


# --- Core Game Setup and Management ---
def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Preparing game. Mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
    main_window.current_game_mode = mode

    if mode in ["couch_play", "host_game"]:
        if not map_name:
            # ... (error handling as before)
            error("Map name required for couch_play/host_game."); return
        _show_status_dialog(main_window, f"Starting {mode.replace('_',' ').title()}", f"Loading map: {map_name}...")
        if not _initialize_game_entities(main_window, map_name, mode):
            # ... (error handling as before)
            error("Failed to init entities."); _close_status_dialog(main_window); main_window.show_view("menu"); return
        _update_status_dialog(main_window, "Entities initialized.", 50) # Progress update
    elif mode in ["join_ip", "join_lan"]:
        if not target_ip_port:
            # ... (error handling as before)
            error("Target IP:Port required."); return
        _show_status_dialog(main_window, f"Joining Game ({mode.replace('_',' ').title()})", f"Connecting to {target_ip_port}...")
        reset_game_state(main_window.game_elements) # Clear local state
        # Client dummy camera until server sends map data
        initial_sw = float(main_window.game_scene_widget.width()) if main_window.game_scene_widget.width() > 1 else float(C.GAME_WIDTH)
        initial_sh = float(main_window.game_scene_widget.height()) if main_window.game_scene_widget.height() > 1 else float(C.GAME_HEIGHT)
        main_window.game_elements['camera'] = Camera(C.GAME_WIDTH, 0,0,C.GAME_HEIGHT, initial_sw, initial_sh)
    else:
        error(f"Unknown game mode: {mode}"); main_window.show_view("menu"); return

    if mode == "couch_play":
        _close_status_dialog(main_window)
        main_window.show_view("game_scene")
    elif mode == "host_game":
        main_window.current_game_mode = "host_waiting"
        _update_status_dialog(main_window, "Starting server...", 75)
        start_network_mode_logic(main_window, "host") # Network thread handles further status updates
        main_window.show_view("game_scene") # Host sees game while waiting
    elif mode in ["join_ip", "join_lan"]:
        start_network_mode_logic(main_window, "join", target_ip_port)
        # Status dialog managed by network thread updates

# --- Network Logic and LAN Search (largely unchanged from previous, ensure imports and ServerState.current_map_name is set) ---
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
    reset_game_state(main_window.game_elements); main_window.current_game_mode = None
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
        main_window.server_state = ServerState(); main_window.server_state.current_map_name = ge_ref.get('map_name')
        main_window.network_thread = main_window.NetworkThread(mode="host", game_elements_ref=ge_ref, server_state_ref=main_window.server_state, parent=main_window)
        _update_status_dialog(main_window, "Server Setup", "Server starting. Waiting for client...")
    elif mode_name == "join":
        if not target_ip_port: error("Target IP:Port required for join."); _update_status_dialog(main_window, "Connection Error", "No target IP.", -1); return
        main_window.client_state = ClientState()
        main_window.network_thread = main_window.NetworkThread(mode="join", game_elements_ref=ge_ref, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
        _update_status_dialog(main_window, "Connecting...", f"Attempting to connect to {target_ip_port}...")
    else: error(f"Unknown network mode: {mode_name}"); return
    main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot)
    main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot)
    main_window.network_thread.client_fully_synced_signal.connect(main_window.on_client_fully_synced_for_host)
    main_window.network_thread.start(); info(f"GAME_MODES: NetworkThread for '{mode_name}' started.")

def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'):
    info("GAME_MODES (Host): Client fully synced. Transitioning to active game.")
    if main_window.current_game_mode == "host_waiting" and main_window.server_state:
        main_window.current_game_mode = "host_active"; main_window.server_state.client_ready = True
        _close_status_dialog(main_window); main_window.show_view("game_scene")
        info("Client connected. Game started for host.")
    else: warning("GAME_MODES: Received client_fully_synced in unexpected state.")

def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float):
    debug(f"GAME_MODES (Net Status): {title} - {message} - Prog: {progress}")
    is_net_mode = main_window.current_game_mode in ["host_game", "host_waiting", "host_active", "join_ip", "join_lan"]
    if progress == -2.0: _close_status_dialog(main_window)
    elif (not main_window.status_dialog or not main_window.status_dialog.isVisible()) and is_net_mode :
        _show_status_dialog(main_window, title, message)
        if progress >= 0: _update_status_dialog(main_window, message, progress)
    elif main_window.status_dialog and main_window.status_dialog.isVisible(): _update_status_dialog(main_window, message, progress)

def on_network_operation_finished_logic(main_window: 'MainWindow', result_message: str):
    info(f"GAME_MODES: Network op finished: {result_message}")
    _close_status_dialog(main_window); current_mode_stopped = main_window.current_game_mode
    stop_current_game_mode_logic(main_window, show_menu=False)
    if result_message == "host_ended": QMessageBox.information(main_window, "Server Closed", "Game server closed.")
    elif result_message == "client_ended": QMessageBox.information(main_window, "Disconnected", "Disconnected from server.")
    elif "error" in result_message.lower() or "failed" in result_message.lower():
        err_type = "Server Error" if "host" in result_message or (current_mode_stopped and "host" in current_mode_stopped) else "Connection Error"
        QMessageBox.critical(main_window, err_type, f"Network op failed: {result_message}")
    elif result_message == "client_initial_sync_complete":
        info("Client initial sync complete. Showing game scene."); main_window.current_game_mode = "join_active"
        main_window.show_view("game_scene"); return
    main_window.show_view("menu")

_lan_search_thread_instance: Optional[LANServerSearchThread] = None
def on_lan_server_search_status_update_logic(main_window: 'MainWindow', data: Any):
    if not main_window.lan_search_dialog or not main_window.lan_search_dialog.isVisible(): return
    if isinstance(data, str): main_window.lan_search_status_label.setText(data)
    elif isinstance(data, tuple) and len(data) == 4:
        s_name, ip, port, map_name = data; item_text = f"{s_name} ({ip}:{port}) - Map: {map_name}"
        list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name))
        main_window.lan_servers_list_widget.addItem(list_item)
        if main_window.lan_servers_list_widget.count() == 1: main_window._lan_search_list_selected_idx = 0
        _update_lan_search_list_focus(main_window); main_window.lan_search_status_label.setText(f"Found: {s_name}. Searching...")
    else: warning(f"Malformed LAN server data: {data}")

def start_lan_server_search_thread_logic(main_window: 'MainWindow'):
    global _lan_search_thread_instance; info("GAME_MODES: Starting LAN server search.")
    if _lan_search_thread_instance and _lan_search_thread_instance.isRunning():
        info("LAN search running. Stopping/restarting."); _lan_search_thread_instance.stop(); _lan_search_thread_instance.wait(500)
    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Initializing search...")
    main_window._lan_search_list_selected_idx = 0
    _lan_search_thread_instance = LANServerSearchThread(main_window)
    _lan_search_thread_instance.found_server_signal.connect(main_window.lan_server_search_status)
    _lan_search_thread_instance.search_status_signal.connect(main_window.lan_server_search_status)
    _lan_search_thread_instance.start()

def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'):
    info("GAME_MODES: Attempting to join selected LAN server.")
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget: error("LAN dialog/list not available."); return
    item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
    if not item: QMessageBox.warning(main_window.lan_search_dialog, "No Server", "Select a server."); return
    data = item.data(Qt.ItemDataRole.UserRole)
    if not data or len(data) < 2: error(f"Invalid server data: {data}"); QMessageBox.critical(main_window.lan_search_dialog, "Error", "Invalid data."); return
    ip, port, map_name_lan = data[0], data[1], data[2] if len(data) > 2 else "Unknown"
    target_ip_port = f"{ip}:{port}"; info(f"Selected LAN server: {target_ip_port}, Map: {map_name_lan}")
    main_window.lan_search_dialog.accept(); setattr(main_window, 'current_modal_dialog', None)
    prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=target_ip_port)