# app_game_modes.py
# -*- coding: utf-8 -*-
"""
Handles game mode logic: initialization, starting/stopping modes,
managing network interactions, and UI dialogs for PySide6.
"""
# version 2.0.9 (Enhanced initialization sequence, camera setup timing, readiness flags)

import os
import sys
import time
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QListWidgetItem, QDialogButtonBox, QMessageBox, QApplication # Added QApplication
from PySide6.QtCore import QThread, Signal, Qt, QRectF, QPointF

from logger import info, debug, warning, error, critical
import constants as C
import config as game_config

from app_ui_creator import ( # Assuming these are correctly defined in app_ui_creator
    _show_status_dialog,
    _update_status_dialog,
    _close_status_dialog,
    _show_lan_search_dialog,
    _update_lan_search_list_focus,
    _update_ip_dialog_button_focus
)

from game_ui import IPInputDialog
from game_state_manager import reset_game_state
from player import Player
from enemy import Enemy
from statue import Statue
from items import Chest
from tiles import Platform, Ladder, Lava, BackgroundTile
from camera import Camera
from level_loader import LevelLoader

from server_logic import ServerState
from client_logic import ClientState, find_server_on_lan # Added find_server_on_lan here

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any # Fallback for runtime if app_core is not available for type hint


class LANServerSearchThread(QThread):
    # Emits: (status_key: str, data: Any)
    # status_key can be "searching", "found", "timeout", "error", "cancelled", "final_result"
    # data for "found" is (ip, port, map_name_if_known_else_empty_str)
    # data for "final_result" is (ip,port) or None
    # data for others is usually a message string.
    search_event_signal = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self.client_state_for_search = ClientState() # Each search uses its own ClientState

    def run(self):
        self._running = True
        self.search_event_signal.emit("searching", "Searching for LAN games...")
        info("LAN_SEARCH_THREAD: Actual search started using find_server_on_lan.")
        
        def search_update_callback(status_key: str, message_data: Any):
            if not self._running: return
            # For 'found', message_data is (ip, port). Map name isn't directly part of find_server_on_lan's UDP discovery.
            # We'll emit a generic map name or handle map name exchange later if needed.
            if status_key == "found" and isinstance(message_data, tuple) and len(message_data) == 2:
                 self.search_event_signal.emit(status_key, (message_data[0], message_data[1], "Map via TCP")) # Map name obtained after TCP connect
            else:
                self.search_event_signal.emit(status_key, message_data)

        # find_server_on_lan will call search_update_callback multiple times.
        # The final result is what it returns.
        result_server_info = find_server_on_lan(self.client_state_for_search, search_update_callback)
        
        if self._running: # If not stopped by an earlier 'found' that led to dialog closure
            self.search_event_signal.emit("final_result", result_server_info)
        
        info("LAN_SEARCH_THREAD: Actual search finished.")
        self._running = False

    def stop_search(self):
        info("LAN_SEARCH_THREAD: Stop requested.")
        self._running = False
        if hasattr(self.client_state_for_search, 'app_running'):
            self.client_state_for_search.app_running = False # Signal find_server_on_lan to stop


def _initialize_game_entities(main_window: 'MainWindow', map_name: str, mode: str) -> bool:
    info(f"GAME_MODES: === INITIALIZING NEW GAME SESSION === Map: '{map_name}', Mode: '{mode}'.")
    debug(f"GAME_MODES Init Start: Current game_elements keys before clear: {list(main_window.game_elements.keys())}")

    main_window.game_elements.clear()
    main_window.game_elements['initialization_in_progress'] = True
    main_window.game_elements['game_ready_for_logic'] = False
    debug("GAME_MODES Init: Cleared main_window.game_elements and set init flags.")

    level_loader = LevelLoader()
    maps_dir_path = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_dir_path):
        project_root_path = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_dir_path = os.path.join(str(project_root_path), maps_dir_path)
        debug(f"GAME_MODES Init: Resolved maps_dir_path to: {maps_dir_path}")

    level_data = level_loader.load_map(map_name, maps_dir_path)
    if not level_data or not isinstance(level_data, dict):
        error(f"GAME_MODES Init: Failed to load map data for '{map_name}'. LevelLoader returned: {type(level_data)}.");
        _update_status_dialog(main_window, title="Map Load Error", message=f"Failed to load map: {map_name}", progress=-1.0)
        main_window.game_elements['initialization_in_progress'] = False # Reset flag on failure
        return False
    debug(f"GAME_MODES Init: Map data for '{map_name}' loaded successfully. Keys: {list(level_data.keys())}")

    main_window.game_elements['level_data'] = level_data
    debug(f"GAME_MODES Init: Stored fresh level_data for '{map_name}'. Platform count in data: {len(level_data.get('platforms_list', []))}")

    # Populate game_elements with map definitions and default lists
    main_window.game_elements['map_name'] = map_name
    main_window.game_elements['loaded_map_name'] = map_name
    main_window.game_elements['enemy_spawns_data_cache'] = list(level_data.get('enemies_list', []))
    main_window.game_elements['statue_spawns_data_cache'] = list(level_data.get('statues_list', []))
    
    p1_default_spawn = (50.0, float(main_window.game_scene_widget.height() - C.TILE_SIZE * 2)) # Use current widget height as fallback basis
    p2_default_spawn = (100.0, float(main_window.game_scene_widget.height() - C.TILE_SIZE * 2))
    main_window.game_elements['player1_spawn_pos'] = tuple(level_data.get('player_start_pos_p1', p1_default_spawn))
    main_window.game_elements['player1_spawn_props'] = dict(level_data.get('player1_spawn_props', {}))
    main_window.game_elements['player2_spawn_pos'] = tuple(level_data.get('player_start_pos_p2', p2_default_spawn))
    main_window.game_elements['player2_spawn_props'] = dict(level_data.get('player2_spawn_props', {}))

    main_window.game_elements['level_pixel_width'] = float(level_data.get('level_pixel_width', main_window.game_scene_widget.width() * 2.0))
    main_window.game_elements['level_min_x_absolute'] = float(level_data.get('level_min_x_absolute', 0.0))
    main_window.game_elements['level_min_y_absolute'] = float(level_data.get('level_min_y_absolute', 0.0))
    main_window.game_elements['level_max_y_absolute'] = float(level_data.get('level_max_y_absolute', main_window.game_scene_widget.height()))
    main_window.game_elements['level_background_color'] = tuple(level_data.get('background_color', C.LIGHT_BLUE))
    main_window.game_elements['ground_level_y_ref'] = float(level_data.get('ground_level_y_ref', main_window.game_elements['level_max_y_absolute'] - C.TILE_SIZE))
    main_window.game_elements['ground_platform_height_ref'] = float(level_data.get('ground_platform_height_ref', C.TILE_SIZE))
    
    debug(f"GAME_MODES Init: Populated map dims. LevelPixelWidth: {main_window.game_elements['level_pixel_width']:.1f}, "
          f"MinX: {main_window.game_elements['level_min_x_absolute']:.1f}, MinY: {main_window.game_elements['level_min_y_absolute']:.1f}, MaxY: {main_window.game_elements['level_max_y_absolute']:.1f}")


    # Initialize entity lists
    platforms_list: List[Platform] = []
    ladders_list: List[Ladder] = []
    hazards_list: List[Lava] = []
    background_tiles_list: List[BackgroundTile] = []
    enemy_list: List[Enemy] = []
    statue_objects_list: List[Statue] = []
    collectible_list: List[Any] = []
    projectiles_list: List[Any] = []
    all_renderable_objects: List[Any] = []
    current_chest_obj: Optional[Chest] = None

    # Populate STATIC entities
    for p_data in level_data.get('platforms_list', []):
        rect_tuple = p_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4:
            plat = Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                            color_tuple=tuple(p_data.get('color', C.GRAY)), platform_type=str(p_data.get('type', 'generic_platform')),
                            properties=p_data.get('properties', {}))
            platforms_list.append(plat)
    all_renderable_objects.extend(platforms_list)
    debug(f"GAME_MODES Init: Created {len(platforms_list)} Platform objects.")


    for l_data in level_data.get('ladders_list', []):
        rect_tuple = l_data.get('rect');
        if rect_tuple and len(rect_tuple) == 4: ladders_list.append(Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3])))
    all_renderable_objects.extend(ladders_list)

    for h_data in level_data.get('hazards_list', []):
        rect_tuple = h_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4 and (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()):
            hazards_list.append(Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(h_data.get('color', C.ORANGE_RED))))
    all_renderable_objects.extend(hazards_list)

    for bg_data in level_data.get('background_tiles_list', []):
        rect_tuple = bg_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4:
            background_tiles_list.append(BackgroundTile(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                     color_tuple=tuple(bg_data.get('color', C.DARK_GRAY)), tile_type=str(bg_data.get('type', 'generic_background')),
                                     image_path=bg_data.get('image_path'), properties=bg_data.get('properties', {})))
    all_renderable_objects.extend(background_tiles_list)

    main_window.game_elements['platforms_list'] = platforms_list
    main_window.game_elements['ladders_list'] = ladders_list
    main_window.game_elements['hazards_list'] = hazards_list
    main_window.game_elements['background_tiles_list'] = background_tiles_list


    # Initialize Players
    player1 = Player(main_window.game_elements['player1_spawn_pos'][0], main_window.game_elements['player1_spawn_pos'][1], 1, initial_properties=main_window.game_elements['player1_spawn_props'])
    if not player1._valid_init: critical(f"P1 failed to initialize for map {map_name}"); main_window.game_elements['initialization_in_progress'] = False; return False
    player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE # Set control scheme
    all_renderable_objects.append(player1)
    main_window.game_elements['player1'] = player1
    debug(f"GAME_MODES Init: Player 1 initialized. Control: {player1.control_scheme}")

    player2 = None
    if mode in ["couch_play", "join_ip", "join_lan", "host"]:
        p2_spawn_pos = main_window.game_elements['player2_spawn_pos']
        p2_props = main_window.game_elements['player2_spawn_props']
        player2 = Player(p2_spawn_pos[0], p2_spawn_pos[1], 2, initial_properties=p2_props)
        if not player2._valid_init: warning(f"P2 failed to initialize for map {map_name} in mode {mode}.")
        else: all_renderable_objects.append(player2)
        if mode != "host": player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
        debug(f"GAME_MODES Init: Player 2 initialized for mode {mode}. Control: {getattr(player2, 'control_scheme', 'N/A')}")
    main_window.game_elements['player2'] = player2
    
    # Initialize Camera
    # Get actual screen dimensions from GameSceneWidget *after* it's potentially sized by show_view
    # However, _initialize_game_entities is called *before* show_view usually.
    # So, we use the main window's current size as a hint, which should be fairly stable.
    # The camera's set_screen_dimensions will be called again in prepare_and_start_game_logic AFTER show_view.
    screen_w_hint = float(main_window.width())
    screen_h_hint = float(main_window.height())
    debug(f"GAME_MODES Init: Camera using screen hint: {screen_w_hint}x{screen_h_hint}")

    camera_instance = Camera(
        initial_level_width=main_window.game_elements['level_pixel_width'],
        initial_world_start_x=main_window.game_elements['level_min_x_absolute'],
        initial_world_start_y=main_window.game_elements['level_min_y_absolute'],
        initial_level_bottom_y_abs=main_window.game_elements['level_max_y_absolute'],
        screen_width=screen_w_hint,
        screen_height=screen_h_hint
    )
    main_window.game_elements['camera'] = camera_instance
    main_window.game_elements['camera_level_dims_set'] = False # Mark as not yet finalized with widget size
    debug(f"GAME_MODES Init: Camera INSTANTIATED with initial hints.")

    # Initialize DYNAMIC entities
    if mode in ["host", "couch_play", "host_game"]: # "host_game" might be redundant if "host" is used
        for i, e_data in enumerate(main_window.game_elements['enemy_spawns_data_cache']):
            # ... (enemy spawning logic as before) ...
            try:
                start_pos = tuple(map(float, e_data.get('start_pos', (100.0, 100.0))))
                enemy_type = str(e_data.get('type', 'enemy_green'))
                patrol_raw = e_data.get('patrol_rect_data')
                patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']), float(patrol_raw['width']), float(patrol_raw['height']))
                enemy = Enemy(start_x=start_pos[0], start_y=start_pos[1], patrol_area=patrol_qrectf, enemy_id=i, color_name=enemy_type, properties=e_data.get('properties', {}))
                if enemy._valid_init: enemy_list.append(enemy); all_renderable_objects.append(enemy)
            except Exception as ex_enemy: error(f"Error spawning enemy {i}: {ex_enemy}", exc_info=True)
        debug(f"GAME_MODES Init: Created {len(enemy_list)} Enemy objects.")


        for i, s_data in enumerate(main_window.game_elements['statue_spawns_data_cache']):
            # ... (statue spawning logic as before) ...
            try:
                statue_pos = tuple(map(float, s_data.get('pos', (200.0, 200.0))))
                statue = Statue(center_x=statue_pos[0], center_y=statue_pos[1], statue_id=s_data.get('id', f"statue_{i}"), properties=s_data.get('properties', {}))
                if statue._valid_init: statue_objects_list.append(statue); all_renderable_objects.append(statue)
            except Exception as ex_statue: error(f"Error spawning statue {i}: {ex_statue}", exc_info=True)
        debug(f"GAME_MODES Init: Created {len(statue_objects_list)} Statue objects.")


        for i_data in level_data.get('items_list', []): # Use fresh level_data
            if str(i_data.get('type', '')).lower() == 'chest':
                try:
                    chest_pos = tuple(map(float, i_data.get('pos', (300.0, 300.0))))
                    chest = Chest(x=chest_pos[0], y=chest_pos[1])
                    if chest._valid_init:
                        collectible_list.append(chest); all_renderable_objects.append(chest)
                        current_chest_obj = chest # Assign to local variable
                        debug(f"GAME_MODES Init: Chest created from level_data at ({chest_pos[0]}, {chest_pos[1]})")
                    else: warning("GAME_MODES Init: Map-defined chest failed to initialize.")
                except Exception as ex_item: error(f"Error spawning item (chest): {ex_item}", exc_info=True)
                break # Assuming only one chest from map data
    
    main_window.game_elements['enemy_list'] = enemy_list
    main_window.game_elements['statue_objects'] = statue_objects_list
    main_window.game_elements['collectible_list'] = collectible_list
    main_window.game_elements['current_chest'] = current_chest_obj # Assign the locally created chest
    main_window.game_elements['projectiles_list'] = projectiles_list
    main_window.game_elements['all_renderable_objects'] = all_renderable_objects

    ge_ref_for_proj = {
        "projectiles_list": main_window.game_elements['projectiles_list'],
        "all_renderable_objects": main_window.game_elements['all_renderable_objects'],
        "platforms_list": main_window.game_elements['platforms_list']
    }
    if player1: player1.game_elements_ref_for_projectiles = ge_ref_for_proj
    if player2: player2.game_elements_ref_for_projectiles = ge_ref_for_proj

    if hasattr(main_window.game_scene_widget, 'set_level_dimensions'):
        main_window.game_scene_widget.set_level_dimensions(
            main_window.game_elements['level_pixel_width'], main_window.game_elements['level_min_x_absolute'],
            main_window.game_elements['level_min_y_absolute'], main_window.game_elements['level_max_y_absolute']
        )
    
    main_window.game_elements['initialization_in_progress'] = False
    main_window.game_elements['game_ready_for_logic'] = True
    debug(f"GAME_MODES Init End: game_ready_for_logic=True. All_renderables count: {len(all_renderable_objects)}")
    info("GAME_MODES: Game entities fully initialized and populated from new map data.")
    return True


# --- Map Selection Initiators ---
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

# --- Game Start Triggers ---
def start_couch_play_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Couch Co-op with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "couch_play", map_name)

def start_host_game_logic(main_window: 'MainWindow', map_name: str):
    info(f"GAME_MODES: Starting Host Game with map '{map_name}'.")
    prepare_and_start_game_logic(main_window, "host_game", map_name) # Changed mode to "host_game"

# --- Dialog Initiators ---
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
                target_ip_port=str(main_window.ip_input_dialog.ip_port_string if main_window.ip_input_dialog and main_window.ip_input_dialog.ip_port_string else "")
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


# --- Core Game Setup and Management ---
def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Preparing game. Mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
    main_window.current_game_mode = mode
    main_window.game_elements['current_game_mode'] = mode # Also store in game_elements

    if mode in ["couch_play", "host_game"]: # Changed "host" to "host_game" for clarity if needed
        if not map_name: error("Map name required for couch_play/host_game."); main_window.show_view("menu"); return
        _show_status_dialog(main_window, f"Starting {mode.replace('_',' ').title()}", f"Loading map: {map_name}...")
        if not _initialize_game_entities(main_window, map_name, mode):
            error(f"Failed to initialize game entities for map '{map_name}'. Mode '{mode}'.");
            _close_status_dialog(main_window); main_window.show_view("menu"); return
        _update_status_dialog(main_window, message="Entities initialized successfully.", progress=50.0, title=f"Starting {mode.replace('_',' ').title()}")
    elif mode in ["join_ip", "join_lan"]:
        if not target_ip_port: error("Target IP:Port required for join."); _close_status_dialog(main_window); main_window.show_view("menu"); return
        _show_status_dialog(main_window, title=f"Joining Game ({mode.replace('_',' ').title()})", message=f"Connecting to {target_ip_port}...")
        main_window.game_elements.clear() # Client starts with empty elements, server will provide map & state
        main_window.game_elements['initialization_in_progress'] = True # Client also in init phase
        main_window.game_elements['game_ready_for_logic'] = False
        # Client needs a placeholder camera until server sends map dimensions
        initial_sw = float(main_window.game_scene_widget.width()) if main_window.game_scene_widget.width() > 1 else float(C.GAME_WIDTH)
        initial_sh = float(main_window.game_scene_widget.height()) if main_window.game_scene_widget.height() > 1 else float(C.GAME_HEIGHT)
        main_window.game_elements['camera'] = Camera(initial_level_width=initial_sw, initial_world_start_x=0.0, initial_world_start_y=0.0, initial_level_bottom_y_abs=initial_sh, screen_width=initial_sw, screen_height=initial_sh)
        main_window.game_elements['camera_level_dims_set'] = False
    else:
        error(f"Unknown game mode: {mode}"); main_window.show_view("menu"); return

    # Call show_view AFTER basic game_elements are populated enough for GameSceneWidget to render something (even if just background)
    main_window.show_view("game_scene")
    QApplication.processEvents() # Crucial: Allow UI to update, especially for GameSceneWidget to get its size

    # Now, finalize camera screen dimensions with actual widget size
    camera = main_window.game_elements.get("camera")
    game_scene_widget = main_window.game_scene_widget
    if camera and game_scene_widget:
        actual_screen_w = float(game_scene_widget.width())
        actual_screen_h = float(game_scene_widget.height())
        if actual_screen_w <= 1 or actual_screen_h <= 1: # If widget size is still not valid, use main window
            actual_screen_w = float(main_window.width())
            actual_screen_h = float(main_window.height())
        debug(f"GAME_MODES: Finalizing camera screen dimensions to: {actual_screen_w}x{actual_screen_h}")
        camera.set_screen_dimensions(actual_screen_w, actual_screen_h)
        
        # If level dimensions are already known (e.g., host/couch), re-update camera focus
        if main_window.game_elements.get('camera_level_dims_set', False) or \
           (main_window.game_elements.get('level_pixel_width') is not None): # Check if level dims are set
            player1_focus = main_window.game_elements.get("player1")
            if player1_focus and hasattr(player1_focus, 'alive') and player1_focus.alive():
                camera.update(player1_focus)
            else:
                camera.static_update()
        main_window.game_elements['camera_level_dims_set'] = True # Mark as fully set

    if mode == "couch_play":
        _close_status_dialog(main_window)
        info("GAME_MODES: Couch play ready.")
    elif mode == "host_game": # "host_game" is the trigger for server logic
        main_window.current_game_mode = "host_waiting" # Transition to waiting state
        _update_status_dialog(main_window, message="Server starting. Waiting for client connection...", progress=75.0, title="Server Hosting")
        start_network_mode_logic(main_window, "host") # "host" is for NetworkThread mode
    elif mode in ["join_ip", "join_lan"]:
        # Status dialog is already open and showing "Connecting..."
        start_network_mode_logic(main_window, "join", target_ip_port) # "join" is for NetworkThread mode


def stop_current_game_mode_logic(main_window: 'MainWindow', show_menu: bool = True):
    current_mode_being_stopped = main_window.current_game_mode
    info(f"GAME_MODES: Stopping current game mode: {current_mode_being_stopped}")

    # Signal network threads to stop
    if main_window.network_thread and main_window.network_thread.isRunning():
        info("GAME_MODES: Stopping network thread...")
        if main_window.server_state: main_window.server_state.app_running = False
        if main_window.client_state: main_window.client_state.app_running = False
        # No need to join here if QThread.quit() is used; QThread handles cleanup
        main_window.network_thread.quit() # Politely ask to stop
        if not main_window.network_thread.wait(1000): # Wait for a bit
            warning("GAME_MODES: Network thread did not stop gracefully. Terminating.")
            main_window.network_thread.terminate() # Force stop if necessary
            main_window.network_thread.wait(200) # Wait for termination
        main_window.network_thread = None
        info("GAME_MODES: Network thread processing finished.")

    main_window.server_state = None
    main_window.client_state = None
    main_window.current_game_mode = None # Clear the game mode *before* clearing elements

    # Reset flags in game_elements before clearing, or just clear and re-init next time
    if 'game_elements' in main_window.__dict__: # Check if it exists
        main_window.game_elements['initialization_in_progress'] = False
        main_window.game_elements['game_ready_for_logic'] = False
        main_window.game_elements['camera_level_dims_set'] = False
        if show_menu:
            info("GAME_MODES: Clearing all game_elements as returning to menu.")
            main_window.game_elements.clear()
        else:
            # If not showing menu, it implies an internal reset or error state.
            # reset_game_state might be called externally or if this is part of an error recovery.
            # For simplicity, if we are not going to menu, we might not want to clear elements
            # if another part of the system is about to handle a reset/reload.
            # However, for a clean stop, clearing is safer.
            info("GAME_MODES: Clearing all game_elements (show_menu=False).")
            main_window.game_elements.clear()

    _close_status_dialog(main_window)
    if hasattr(main_window, 'lan_search_dialog') and main_window.lan_search_dialog and main_window.lan_search_dialog.isVisible():
        main_window.lan_search_dialog.reject() # Close LAN search dialog

    if hasattr(main_window, 'game_scene_widget') and hasattr(main_window.game_scene_widget, 'clear_scene_for_new_game'):
        main_window.game_scene_widget.clear_scene_for_new_game()

    if show_menu:
        main_window.show_view("menu")

    info(f"GAME_MODES: Game mode '{current_mode_being_stopped}' stopped and resources cleaned up.")


# --- Network Logic and LAN Search ---
def start_network_mode_logic(main_window: 'MainWindow', mode_name: str, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Starting network mode: {mode_name}")
    if main_window.network_thread and main_window.network_thread.isRunning():
        warning("GAME_MODES: Network thread already running. Stopping existing one first.");
        main_window.network_thread.quit()
        main_window.network_thread.wait(500) # Give it a moment to finish
        main_window.network_thread = None

    ge_ref = main_window.game_elements # This should now be populated by _initialize_game_entities
    
    if mode_name == "host":
        main_window.server_state = ServerState()
        server_map_name = ge_ref.get('map_name', ge_ref.get('loaded_map_name', "unknown_map_at_host_start"))
        main_window.server_state.current_map_name = server_map_name
        debug(f"GAME_MODES (Host): Server starting with map: {server_map_name}")
        main_window.network_thread = main_window.NetworkThread(mode="host", game_elements_ref=ge_ref, server_state_ref=main_window.server_state, parent=main_window)
    elif mode_name == "join":
        if not target_ip_port:
            error("GAME_MODES (Join): Target IP:Port required for join mode.");
            _update_status_dialog(main_window, title="Connection Error", message="No target IP specified.", progress=-1.0); return
        main_window.client_state = ClientState()
        main_window.network_thread = main_window.NetworkThread(mode="join", game_elements_ref=ge_ref, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
    else:
        error(f"GAME_MODES: Unknown network mode specified: {mode_name}"); return

    if main_window.network_thread:
        main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot)
        main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot)
        main_window.network_thread.client_fully_synced_signal.connect(main_window.on_client_fully_synced_for_host) # Connect host-specific signal
        main_window.network_thread.start()
        info(f"GAME_MODES: NetworkThread for '{mode_name}' started.")
    else:
        error(f"GAME_MODES: Failed to create NetworkThread for mode '{mode_name}'.")


def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'):
    info("GAME_MODES (Host): Client fully synced. Transitioning game to active state.")
    if main_window.current_game_mode == "host_waiting" and main_window.server_state:
        main_window.current_game_mode = "host_active" # Server is now fully active with a client
        main_window.server_state.client_ready = True
        _close_status_dialog(main_window) # Close "Waiting for client..." dialog
        info("GAME_MODES (Host): Client connected and synced. Game is now fully active for host.")
    else:
        warning(f"GAME_MODES: Received client_fully_synced_for_host in unexpected state: {main_window.current_game_mode}")


def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float):
    debug(f"GAME_MODES (Net Status Update): Title='{title}', Msg='{message}', Prog={progress}")
    is_network_setup_phase = main_window.current_game_mode in ["host_waiting", "join_ip", "join_lan"]
    
    if progress == -2.0: # Special signal to immediately close dialog (e.g., game starting)
        _close_status_dialog(main_window)
        return

    if is_network_setup_phase:
        if not main_window.status_dialog or not main_window.status_dialog.isVisible():
            _show_status_dialog(main_window, title, message)
        
        if main_window.status_dialog and main_window.status_dialog.isVisible():
             _update_status_dialog(main_window, message=message, progress=progress, title=title)
    
    # If the game has started (e.g., client received "start_game_now" or host knows client is ready)
    # and the GameSceneWidget is active, status can be shown there.
    if main_window.current_view_name == "game_scene" and \
       (main_window.current_game_mode == "join_active" or main_window.current_game_mode == "host_active"):
        if hasattr(main_window.game_scene_widget, 'update_game_state'):
            # If it's a download message, pass it to GameSceneWidget to display over the game
            if "Downloading" in title or "Synchronizing Map" in title or "Map Error" in title:
                main_window.game_scene_widget.update_game_state(0, download_msg=message, download_prog=progress)
            else: # For other statuses, just update, maybe don't use overlay
                main_window.game_scene_widget.update_game_state(0) # Basic repaint
    
    # If client's map sync is done and server says start, or host's client is ready
    if (title == "Client Map Sync" and "Map ready, starting game" in message and progress >= 99.9) or \
       (title == "Server Hosting" and "Ready for game start" in message and progress >= 99.9 and main_window.current_game_mode == "host_waiting"):
        if main_window.current_game_mode == "join_lan" or main_window.current_game_mode == "join_ip":
            main_window.current_game_mode = "join_active" # Client is now in active game
            info("GAME_MODES (Client): Map synced and server signaled start. Game active.")
        # Host transition to host_active is handled by on_client_fully_synced_for_host_logic
        _close_status_dialog(main_window)


def on_network_operation_finished_logic(main_window: 'MainWindow', result_message: str):
    info(f"GAME_MODES: Network operation finished: {result_message}")
    _close_status_dialog(main_window)
    current_mode_that_finished = str(main_window.current_game_mode)

    stop_current_game_mode_logic(main_window, show_menu=False) # Stop mode internally first

    if result_message == "host_ended":
        QMessageBox.information(main_window, "Server Closed", "Game server session ended.")
    elif result_message == "client_ended":
        QMessageBox.information(main_window, "Disconnected", "Disconnected from server.")
    elif "error" in result_message.lower() or "failed" in result_message.lower():
        err_type = "Server Error" if "host" in result_message or (current_mode_that_finished and "host" in current_mode_that_finished) else "Connection Error"
        QMessageBox.critical(main_window, err_type, f"Network operation failed: {result_message}")
    
    main_window.show_view("menu")


_lan_search_thread_instance: Optional[LANServerSearchThread] = None
def on_lan_server_search_status_update_logic(main_window: 'MainWindow', data_tuple: Any):
    if not main_window.lan_search_dialog or not main_window.lan_search_dialog.isVisible() or \
       not main_window.lan_search_status_label or not main_window.lan_servers_list_widget:
        info("LAN search status update received, but dialog is not visible. Ignoring.")
        return

    if not isinstance(data_tuple, tuple) or len(data_tuple) != 2:
        warning(f"Malformed data_tuple received in on_lan_server_search_status_update: {data_tuple}")
        return
        
    status_key, data = data_tuple
    debug(f"LAN Search Status Update: Key='{status_key}', Data='{str(data)[:150]}'")

    if status_key == "searching":
        main_window.lan_search_status_label.setText(str(data))
    elif status_key == "found":
        if isinstance(data, tuple) and len(data) == 3: # (ip, port, map_name)
            ip, port, map_name_lan = data
            item_text = f"Server at {ip}:{port} (Map: {map_name_lan})"
            # Check if this server (IP:Port) is already in the list
            found_existing = False
            for i in range(main_window.lan_servers_list_widget.count()):
                item = main_window.lan_servers_list_widget.item(i)
                existing_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(existing_data, tuple) and existing_data[0] == ip and existing_data[1] == port:
                    item.setText(item_text) # Update text if map name changed
                    item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan))
                    found_existing = True; break
            if not found_existing:
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan))
                main_window.lan_servers_list_widget.addItem(list_item)
            
            if hasattr(main_window.lan_search_dialog, 'button_box'):
                main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            if main_window.lan_servers_list_widget.count() == 1 and main_window._lan_search_list_selected_idx == -1 : # Auto-select first found
                 main_window._lan_search_list_selected_idx = 0
            _update_lan_search_list_focus(main_window)

    elif status_key == "timeout" or status_key == "error" or status_key == "cancelled":
        msg = str(data) if data else f"Search {status_key}."
        if main_window.lan_servers_list_widget.count() == 0:
            main_window.lan_search_status_label.setText(f"{msg} No servers found.")
        else:
            main_window.lan_search_status_label.setText(f"{msg} Select a server or retry.")
    elif status_key == "final_result": # find_server_on_lan returned
        if data is None and main_window.lan_servers_list_widget.count() == 0:
            main_window.lan_search_status_label.setText("Search complete. No servers found.")
        elif data is not None: # A final best server was identified by find_server_on_lan itself
            ip, port = data
            item_text_final = f"Server at {ip}:{port} (Map via TCP)"
            # Highlight this one if it's new
            found_existing_final = False
            for i in range(main_window.lan_servers_list_widget.count()):
                item = main_window.lan_servers_list_widget.item(i)
                existing_data_final = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(existing_data_final, tuple) and existing_data_final[0] == ip and existing_data_final[1] == port:
                    if main_window.lan_servers_list_widget.currentItem() != item:
                         main_window.lan_servers_list_widget.setCurrentItem(item)
                         main_window._lan_search_list_selected_idx = i
                    found_existing_final = True; break
            if not found_existing_final:
                list_item_final = QListWidgetItem(item_text_final)
                list_item_final.setData(Qt.ItemDataRole.UserRole, (ip, port, "Map via TCP"))
                main_window.lan_servers_list_widget.addItem(list_item_final)
                main_window.lan_servers_list_widget.setCurrentItem(list_item_final)
                main_window._lan_search_list_selected_idx = main_window.lan_servers_list_widget.count() -1
            _update_lan_search_list_focus(main_window)
            main_window.lan_search_status_label.setText("Search complete. Select a server.")
            if hasattr(main_window.lan_search_dialog, 'button_box'):
                main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        else: # data is None but list might have items from earlier "found" signals
            main_window.lan_search_status_label.setText("Search complete. Select a server or retry.")


def start_lan_server_search_thread_logic(main_window: 'MainWindow'):
    global _lan_search_thread_instance
    info("GAME_MODES: Starting LAN server search thread.")
    if _lan_search_thread_instance and _lan_search_thread_instance.isRunning():
        info("LAN search already running. Stopping and restarting.");
        _lan_search_thread_instance.stop_search() # Use specific stop method
        if not _lan_search_thread_instance.wait(500):
            _lan_search_thread_instance.terminate()
            _lan_search_thread_instance.wait(100)
        _lan_search_thread_instance = None

    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Initializing search...")
    main_window._lan_search_list_selected_idx = -1 # No selection initially
    if hasattr(main_window.lan_search_dialog, 'button_box'):
        main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)


    _lan_search_thread_instance = LANServerSearchThread(main_window)
    _lan_search_thread_instance.search_event_signal.connect(main_window.on_lan_server_search_status_update_slot) # Connect to the unified signal
    _lan_search_thread_instance.finished.connect(_lan_search_thread_instance.deleteLater) # Qt best practice for QThread cleanup
    _lan_search_thread_instance.start()


def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'):
    info("GAME_MODES: Attempting to join selected LAN server.")
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget:
        error("LAN dialog/list widget not available."); return

    selected_item = main_window.lan_servers_list_widget.currentItem() # Use currentItem for single selection
    if not selected_item:
        # Fallback to index if no currentItem but index is valid
        if 0 <= main_window._lan_search_list_selected_idx < main_window.lan_servers_list_widget.count():
            selected_item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
        else:
            QMessageBox.warning(main_window.lan_search_dialog, "No Server Selected", "Please select a server from the list to join.")
            return
    
    if not selected_item: # Still no item
         QMessageBox.warning(main_window.lan_search_dialog, "Selection Error", "Could not retrieve selected server item.")
         return

    data = selected_item.data(Qt.ItemDataRole.UserRole)
    if not data or not isinstance(data, tuple) or len(data) < 2: # Expect at least (ip, port)
        error(f"Invalid server data associated with list item: {data}")
        QMessageBox.critical(main_window.lan_search_dialog, "Error", "Invalid server data for selected item.")
        return

    ip, port = str(data[0]), int(data[1])
    # Map name from LAN discovery is not strictly needed for connection, server will send map info
    # map_name_lan = str(data[2]) if len(data) > 2 else "Unknown (from LAN)" 
    target_ip_port = f"{ip}:{port}"
    info(f"Selected LAN server: {target_ip_port}")

    main_window.lan_search_dialog.accept() # Close dialog
    setattr(main_window, 'current_modal_dialog', None) # Clear modal state

    prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=target_ip_port)