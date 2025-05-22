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

from game_ui import IPInputDialog # Assuming this is your custom IP input dialog
from game_state_manager import reset_game_state
from player import Player
from enemy import Enemy # Assuming Enemy class
from statue import Statue # Assuming Statue class
from items import Chest # Assuming Chest class
from tiles import Platform, Ladder, Lava, BackgroundTile # Assuming these tile classes
from camera import Camera
from level_loader import LevelLoader # Assuming your LevelLoader class

# Network related imports - ensure these are correct
try:
    from server_logic import ServerState
except ImportError:
    warning("server_logic.ServerState not found, using placeholder if needed.")
    class ServerState: pass # Basic placeholder
try:
    from client_logic import ClientState, find_server_on_lan
except ImportError:
    warning("client_logic components not found, using placeholders if needed.")
    class ClientState: pass # Basic placeholder
    def find_server_on_lan(*args, **kwargs): # Placeholder
        print("Warning: find_server_on_lan (placeholder) called.")
        if 'callback' in kwargs and callable(kwargs['callback']):
            kwargs['callback']("timeout", "Search (placeholder) timed out.")
        return None


if TYPE_CHECKING:
    from app_core import MainWindow # Assuming app_core.py defines MainWindow
else:
    MainWindow = Any # Fallback for runtime if app_core is not available for type hint


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
            if status_key == "found" and isinstance(message_data, tuple) and len(message_data) == 2:
                 self.search_event_signal.emit(status_key, (message_data[0], message_data[1], "Map via TCP"))
            else:
                self.search_event_signal.emit(status_key, message_data)

        result_server_info = find_server_on_lan(self.client_state_for_search, search_update_callback)

        if self._running:
            self.search_event_signal.emit("final_result", result_server_info)

        info("LAN_SEARCH_THREAD: Actual search finished.")
        self._running = False

    def stop_search(self):
        info("LAN_SEARCH_THREAD: Stop requested.")
        self._running = False
        if hasattr(self.client_state_for_search, 'app_running'):
            self.client_state_for_search.app_running = False


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
        main_window.game_elements['initialization_in_progress'] = False
        return False
    debug(f"GAME_MODES Init: Map data for '{map_name}' loaded successfully. Keys: {list(level_data.keys())}")

    main_window.game_elements['level_data'] = level_data # Store the raw loaded data
    main_window.game_elements['map_name'] = map_name # Store the requested map name
    main_window.game_elements['loaded_map_name'] = map_name # Explicitly store the name of the map whose data is loaded

    # Populate game_elements with map definitions and default lists
    main_window.game_elements['enemy_spawns_data_cache'] = list(level_data.get('enemies_list', []))
    main_window.game_elements['statue_spawns_data_cache'] = list(level_data.get('statues_list', []))

    p1_default_spawn = (50.0, float(main_window.game_scene_widget.height() - C.TILE_SIZE * 2 if main_window.game_scene_widget and C.TILE_SIZE else 400.0) )
    p2_default_spawn = (100.0, float(main_window.game_scene_widget.height() - C.TILE_SIZE * 2 if main_window.game_scene_widget and C.TILE_SIZE else 400.0) )
    main_window.game_elements['player1_spawn_pos'] = tuple(level_data.get('player_start_pos_p1', p1_default_spawn))
    main_window.game_elements['player1_spawn_props'] = dict(level_data.get('player1_spawn_props', {}))
    main_window.game_elements['player2_spawn_pos'] = tuple(level_data.get('player_start_pos_p2', p2_default_spawn))
    main_window.game_elements['player2_spawn_props'] = dict(level_data.get('player2_spawn_props', {}))

    default_level_width = float(main_window.game_scene_widget.width() * 2.0 if main_window.game_scene_widget else C.GAME_WIDTH * 2.0)
    default_level_height = float(main_window.game_scene_widget.height() if main_window.game_scene_widget else C.GAME_HEIGHT)
    main_window.game_elements['level_pixel_width'] = float(level_data.get('level_pixel_width', default_level_width))
    main_window.game_elements['level_min_x_absolute'] = float(level_data.get('level_min_x_absolute', 0.0))
    main_window.game_elements['level_min_y_absolute'] = float(level_data.get('level_min_y_absolute', 0.0))
    main_window.game_elements['level_max_y_absolute'] = float(level_data.get('level_max_y_absolute', default_level_height))
    main_window.game_elements['level_background_color'] = tuple(level_data.get('background_color', C.LIGHT_BLUE if hasattr(C, 'LIGHT_BLUE') else (173, 216, 230)))
    main_window.game_elements['ground_level_y_ref'] = float(level_data.get('ground_level_y_ref', main_window.game_elements['level_max_y_absolute'] - (C.TILE_SIZE if hasattr(C, 'TILE_SIZE') else 32.0)))
    main_window.game_elements['ground_platform_height_ref'] = float(level_data.get('ground_platform_height_ref', (C.TILE_SIZE if hasattr(C, 'TILE_SIZE') else 32.0)))

    debug(f"GAME_MODES Init: Populated map dims. LevelPixelWidth: {main_window.game_elements['level_pixel_width']:.1f}, MaxY: {main_window.game_elements['level_max_y_absolute']:.1f}")

    platforms_list: List[Platform] = []
    ladders_list: List[Ladder] = []
    hazards_list: List[Lava] = [] # Assuming Lava is the primary hazard type for now
    background_tiles_list: List[BackgroundTile] = []
    enemy_list: List[Enemy] = []
    statue_objects_list: List[Statue] = []
    collectible_list: List[Any] = [] # Includes chests, other items
    projectiles_list: List[Any] = []
    all_players_list: List[Player] = [] # Central list for all player objects
    all_renderable_objects: List[Any] = [] # For GameSceneWidget
    current_chest_obj: Optional[Chest] = None

    for p_data in level_data.get('platforms_list', []):
        rect_tuple = p_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4:
            plat = Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                            color_tuple=tuple(p_data.get('color', C.GRAY if hasattr(C, 'GRAY') else (128,128,128))), platform_type=str(p_data.get('type', 'generic_platform')),
                            properties=p_data.get('properties', {}))
            platforms_list.append(plat)
    all_renderable_objects.extend(platforms_list)
    debug(f"GAME_MODES Init: Created {len(platforms_list)} Platform objects.")

    for l_data in level_data.get('ladders_list', []):
        rect_tuple = l_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4: ladders_list.append(Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3])))
    all_renderable_objects.extend(ladders_list)

    for h_data in level_data.get('hazards_list', []):
        rect_tuple = h_data.get('rect')
        hazard_type_str = str(h_data.get('type', '')).lower()
        if rect_tuple and len(rect_tuple) == 4 and ("lava" in hazard_type_str or "spike" in hazard_type_str): # Generalize hazard
            # Could differentiate Lava vs Spike class if they have different behaviors
            hazards_list.append(Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(h_data.get('color', C.ORANGE_RED if hasattr(C, 'ORANGE_RED') else (255,69,0)))))
    all_renderable_objects.extend(hazards_list)

    for bg_data in level_data.get('background_tiles_list', []):
        rect_tuple = bg_data.get('rect')
        if rect_tuple and len(rect_tuple) == 4:
            background_tiles_list.append(BackgroundTile(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                     color_tuple=tuple(bg_data.get('color', C.DARK_GRAY if hasattr(C, 'DARK_GRAY') else (169,169,169))), tile_type=str(bg_data.get('type', 'generic_background')),
                                     image_path=bg_data.get('image_path'), properties=bg_data.get('properties', {})))
    all_renderable_objects.extend(background_tiles_list)

    main_window.game_elements['platforms_list'] = platforms_list
    main_window.game_elements['ladders_list'] = ladders_list
    main_window.game_elements['hazards_list'] = hazards_list
    main_window.game_elements['background_tiles_list'] = background_tiles_list

    # --- Player 1 Initialization ---
    player1_spawn_coords = main_window.game_elements['player1_spawn_pos']
    player1_props = main_window.game_elements['player1_spawn_props']
    player1 = Player(player1_spawn_coords[0], player1_spawn_coords[1], player_id=1, initial_properties=player1_props)
    if not player1._valid_init: critical(f"P1 failed to initialize for map {map_name}"); main_window.game_elements['initialization_in_progress'] = False; return False

    p1_active_device_id = game_config.UNASSIGNED_DEVICE_ID
    if game_config.P1_CONTROLLER_ENABLED and game_config.CURRENT_P1_CONTROLLER_DEVICE != game_config.UNASSIGNED_DEVICE_ID:
        p1_active_device_id = game_config.CURRENT_P1_CONTROLLER_DEVICE
        info(f"GameModes: P1 initializing with CONTROLLER: {p1_active_device_id}")
    elif game_config.P1_KEYBOARD_ENABLED and game_config.CURRENT_P1_KEYBOARD_DEVICE != game_config.UNASSIGNED_DEVICE_ID:
        p1_active_device_id = game_config.CURRENT_P1_KEYBOARD_DEVICE
        info(f"GameModes: P1 initializing with KEYBOARD: {p1_active_device_id}")
    else:
        info(f"GameModes: P1 has no active input device assigned. Control scheme will be '{p1_active_device_id}'.")
    player1.control_scheme = p1_active_device_id
    all_renderable_objects.append(player1)
    all_players_list.append(player1)
    main_window.game_elements['player1'] = player1
    debug(f"GAME_MODES Init: Player 1 initialized. Control scheme: {player1.control_scheme}")


    player2 = None
    if mode in ["couch_play", "join_ip", "join_lan", "host_game", "host"]: # Added host_game
        p2_spawn_coords = main_window.game_elements['player2_spawn_pos']
        p2_props = main_window.game_elements['player2_spawn_props']
        player2 = Player(p2_spawn_coords[0], p2_spawn_coords[1], player_id=2, initial_properties=p2_props)

        p2_active_device_id = game_config.UNASSIGNED_DEVICE_ID
        can_add_p2 = False
        if mode != "host_game" and mode != "host": # For couch, join_ip, join_lan, P2 uses local P2 config
            if game_config.P2_CONTROLLER_ENABLED and game_config.CURRENT_P2_CONTROLLER_DEVICE != game_config.UNASSIGNED_DEVICE_ID:
                p2_active_device_id = game_config.CURRENT_P2_CONTROLLER_DEVICE
                can_add_p2 = True
                info(f"GameModes: P2 (local) initializing with CONTROLLER: {p2_active_device_id}")
            elif game_config.P2_KEYBOARD_ENABLED and game_config.CURRENT_P2_KEYBOARD_DEVICE != game_config.UNASSIGNED_DEVICE_ID:
                p2_active_device_id = game_config.CURRENT_P2_KEYBOARD_DEVICE
                can_add_p2 = True
                info(f"GameModes: P2 (local) initializing with KEYBOARD: {p2_active_device_id}")
            else:
                info(f"GameModes: P2 (local) has no active input device assigned for mode {mode}. P2 will not be controllable by local P2 config.")
        elif mode == "host_game" or mode == "host": # For host mode, P2 is remote, no local control scheme initially
            p2_active_device_id = "remote_player" # Placeholder for remote
            can_add_p2 = True # Add P2 object for server to manage
            info(f"GameModes: P2 (remote) object created for host mode.")

        if player2 and player2._valid_init and can_add_p2:
            player2.control_scheme = p2_active_device_id
            all_renderable_objects.append(player2)
            all_players_list.append(player2)
            main_window.game_elements['player2'] = player2
            debug(f"GAME_MODES Init: Player 2 initialized for mode {mode}. Control scheme: {player2.control_scheme}")
        elif player2 and not player2._valid_init:
            warning(f"P2 failed to initialize Player object for map {map_name} in mode {mode}.")
            player2 = None # Don't add invalid player
        elif not can_add_p2:
            debug(f"GAME_MODES Init: Player 2 not added for mode {mode} due to no active local device or mode type.")
            player2 = None # Ensure player2 is None if not added
    main_window.game_elements['player2'] = player2 # Store even if None
    main_window.game_elements['all_players_list'] = all_players_list


    screen_w_hint = float(main_window.width() if main_window else C.GAME_WIDTH)
    screen_h_hint = float(main_window.height() if main_window else C.GAME_HEIGHT)
    camera_instance = Camera(
        initial_level_width=main_window.game_elements['level_pixel_width'],
        initial_world_start_x=main_window.game_elements['level_min_x_absolute'],
        initial_world_start_y=main_window.game_elements['level_min_y_absolute'],
        initial_level_bottom_y_abs=main_window.game_elements['level_max_y_absolute'],
        screen_width=screen_w_hint, screen_height=screen_h_hint
    )
    main_window.game_elements['camera'] = camera_instance
    main_window.game_elements['camera_level_dims_set'] = False
    debug(f"GAME_MODES Init: Camera INSTANTIATED with initial hints.")

    # DYNAMIC entities (enemies, statues, items) - only if server or local play
    if mode in ["host_game", "host", "couch_play"]:
        for i, e_data in enumerate(main_window.game_elements['enemy_spawns_data_cache']):
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
            try:
                statue_pos = tuple(map(float, s_data.get('pos', (200.0, 200.0))))
                statue = Statue(center_x=statue_pos[0], center_y=statue_pos[1], statue_id=s_data.get('id', f"statue_{i}"), properties=s_data.get('properties', {}))
                if statue._valid_init: statue_objects_list.append(statue); all_renderable_objects.append(statue)
            except Exception as ex_statue: error(f"Error spawning statue {i}: {ex_statue}", exc_info=True)
        debug(f"GAME_MODES Init: Created {len(statue_objects_list)} Statue objects.")

        for i_data in level_data.get('items_list', []):
            if str(i_data.get('type', '')).lower() == 'chest':
                try:
                    chest_pos = tuple(map(float, i_data.get('pos', (300.0, 300.0))))
                    chest = Chest(x=chest_pos[0], y=chest_pos[1]) # Assuming Chest takes x, y
                    if chest._valid_init:
                        collectible_list.append(chest); all_renderable_objects.append(chest)
                        current_chest_obj = chest
                        debug(f"GAME_MODES Init: Chest created at ({chest_pos[0]}, {chest_pos[1]})")
                    else: warning("GAME_MODES Init: Map-defined chest failed to initialize.")
                except Exception as ex_item: error(f"Error spawning item (chest): {ex_item}", exc_info=True)
                # break # Decide if only one chest is allowed from map data

    main_window.game_elements['enemy_list'] = enemy_list
    main_window.game_elements['statue_objects_list'] = statue_objects_list # Corrected key
    main_window.game_elements['collectible_list'] = collectible_list
    main_window.game_elements['current_chest'] = current_chest_obj
    main_window.game_elements['projectiles_list'] = projectiles_list # Init as empty
    main_window.game_elements['all_renderable_objects'] = all_renderable_objects

    # Pass projectile management refs to players
    ge_ref_for_proj = {
        "projectiles_list": main_window.game_elements['projectiles_list'],
        "all_renderable_objects": main_window.game_elements['all_renderable_objects'],
        "platforms_list": main_window.game_elements['platforms_list']
    }
    for p_obj in all_players_list:
        if p_obj: p_obj.game_elements_ref_for_projectiles = ge_ref_for_proj


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
    prepare_and_start_game_logic(main_window, "host_game", map_name)

# --- Dialog Initiators ---
def initiate_join_lan_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join LAN Dialog.")
    _show_lan_search_dialog(main_window) # This should exist in app_ui_creator

def initiate_join_ip_dialog(main_window: 'MainWindow'):
    info("GAME_MODES: Initiating Join by IP Dialog.")
    if not hasattr(main_window, 'ip_input_dialog') or main_window.ip_input_dialog is None:
        # Ensure IPInputDialog class is available, e.g., from game_ui or app_ui_creator
        try:
            # from game_ui import IPInputDialog # Or wherever it's defined
            if main_window.ip_input_dialog_class_ref: # Check if class_ref was set in MainWindow.__init__
                 main_window.ip_input_dialog = main_window.ip_input_dialog_class_ref(parent=main_window)
            else:
                error("IPInputDialog class reference not found in MainWindow. Cannot create dialog.")
                return
        except ImportError:
            error("Failed to import IPInputDialog. Cannot create dialog.")
            return

        main_window.ip_input_dialog.accepted.connect(
            lambda: prepare_and_start_game_logic(
                main_window, "join_ip",
                target_ip_port=str(main_window.ip_input_dialog.ip_port_string if main_window.ip_input_dialog else "")
            )
        )
        main_window.ip_input_dialog.rejected.connect(
            lambda: (main_window.show_view("menu"), setattr(main_window, 'current_modal_dialog', None))
        )
        # Assuming IPInputDialog has a buttonBox attribute
        if hasattr(main_window.ip_input_dialog, 'button_box'):
            ok_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
            cancel_button = main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
            main_window._ip_dialog_buttons_ref = [btn for btn in [ok_button, cancel_button] if btn]
        else:
            warning("IPInputDialog does not have a 'button_box' attribute. Button refs not set.")


    main_window.current_modal_dialog = "ip_input"
    main_window._ip_dialog_selected_button_idx = 0 # Default to OK button
    _update_ip_dialog_button_focus(main_window) # In app_ui_creator
    if hasattr(main_window.ip_input_dialog, 'clear_input_and_focus'):
        main_window.ip_input_dialog.clear_input_and_focus()
    main_window.ip_input_dialog.show()


# --- Core Game Setup and Management ---
def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None):
    info(f"GAME_MODES: Preparing game. Mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
    main_window.current_game_mode = mode
    main_window.game_elements['current_game_mode'] = mode

    if mode in ["couch_play", "host_game"]:
        if not map_name: error(f"Map name required for mode '{mode}'."); main_window.show_view("menu"); return
        _show_status_dialog(main_window, f"Starting {mode.replace('_',' ').title()}", f"Loading map: {map_name}...")
        if not _initialize_game_entities(main_window, map_name, mode):
            error(f"Failed to initialize game entities for map '{map_name}'. Mode '{mode}'.");
            _close_status_dialog(main_window); main_window.show_view("menu"); return
        _update_status_dialog(main_window, message="Entities initialized successfully.", progress=50.0, title=f"Starting {mode.replace('_',' ').title()}")
    elif mode in ["join_ip", "join_lan"]:
        if not target_ip_port: error("Target IP:Port required for join."); _close_status_dialog(main_window); main_window.show_view("menu"); return
        _show_status_dialog(main_window, title=f"Joining Game ({mode.replace('_',' ').title()})", message=f"Connecting to {target_ip_port}...")
        main_window.game_elements.clear()
        main_window.game_elements['initialization_in_progress'] = True
        main_window.game_elements['game_ready_for_logic'] = False
        initial_sw = float(main_window.game_scene_widget.width() if main_window.game_scene_widget and main_window.game_scene_widget.width() > 1 else C.GAME_WIDTH)
        initial_sh = float(main_window.game_scene_widget.height() if main_window.game_scene_widget and main_window.game_scene_widget.height() > 1 else C.GAME_HEIGHT)
        main_window.game_elements['camera'] = Camera(initial_level_width=initial_sw, initial_world_start_x=0.0, initial_world_start_y=0.0, initial_level_bottom_y_abs=initial_sh, screen_width=initial_sw, screen_height=initial_sh)
        main_window.game_elements['camera_level_dims_set'] = False
    else:
        error(f"Unknown game mode: {mode}"); main_window.show_view("menu"); return

    main_window.show_view("game_scene")
    QApplication.processEvents() # Crucial for UI update

    camera = main_window.game_elements.get("camera")
    game_scene_widget = main_window.game_scene_widget
    if camera and game_scene_widget:
        actual_screen_w = float(game_scene_widget.width())
        actual_screen_h = float(game_scene_widget.height())
        if actual_screen_w <= 1 or actual_screen_h <= 1:
            actual_screen_w = float(main_window.width())
            actual_screen_h = float(main_window.height())
        debug(f"GAME_MODES: Finalizing camera screen dimensions to: {actual_screen_w}x{actual_screen_h}")
        camera.set_screen_dimensions(actual_screen_w, actual_screen_h)

        if main_window.game_elements.get('level_pixel_width') is not None:
            player1_focus = main_window.game_elements.get("player1")
            if player1_focus and hasattr(player1_focus, 'alive') and player1_focus.alive():
                camera.update(player1_focus) # Initial camera focus
            else:
                camera.static_update() # Fallback if no player or P1 not alive
        main_window.game_elements['camera_level_dims_set'] = True

    if mode == "couch_play":
        _close_status_dialog(main_window)
        info("GAME_MODES: Couch play ready.")
    elif mode == "host_game":
        main_window.current_game_mode = "host_waiting"
        _update_status_dialog(main_window, message="Server starting. Waiting for client connection...", progress=75.0, title="Server Hosting")
        start_network_mode_logic(main_window, "host")
    elif mode in ["join_ip", "join_lan"]:
        start_network_mode_logic(main_window, "join", target_ip_port)


def stop_current_game_mode_logic(main_window: 'MainWindow', show_menu: bool = True):
    current_mode_being_stopped = main_window.current_game_mode
    info(f"GAME_MODES: Stopping current game mode: {current_mode_being_stopped}")

    if main_window.network_thread and main_window.network_thread.isRunning():
        info("GAME_MODES: Stopping network thread...")
        if main_window.server_state and hasattr(main_window.server_state, 'app_running'): main_window.server_state.app_running = False
        if main_window.client_state and hasattr(main_window.client_state, 'app_running'): main_window.client_state.app_running = False
        main_window.network_thread.quit()
        if not main_window.network_thread.wait(1000):
            warning("GAME_MODES: Network thread did not stop gracefully. Terminating.")
            main_window.network_thread.terminate()
            main_window.network_thread.wait(200)
        main_window.network_thread = None
        info("GAME_MODES: Network thread processing finished.")

    main_window.server_state = None
    main_window.client_state = None
    main_window.current_game_mode = None

    if 'game_elements' in main_window.__dict__:
        main_window.game_elements['initialization_in_progress'] = False
        main_window.game_elements['game_ready_for_logic'] = False
        main_window.game_elements['camera_level_dims_set'] = False
        info("GAME_MODES: Clearing all game_elements.")
        main_window.game_elements.clear() # Always clear elements on stop for cleanliness

    _close_status_dialog(main_window)
    if hasattr(main_window, 'lan_search_dialog') and main_window.lan_search_dialog and main_window.lan_search_dialog.isVisible():
        main_window.lan_search_dialog.reject()

    if hasattr(main_window.game_scene_widget, 'clear_scene_for_new_game'):
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
        main_window.network_thread.wait(500)
        main_window.network_thread = None

    ge_ref = main_window.game_elements

    if mode_name == "host":
        main_window.server_state = ServerState() # Create new ServerState instance
        server_map_name = ge_ref.get('map_name', ge_ref.get('loaded_map_name', "unknown_map_at_host_start"))
        if hasattr(main_window.server_state, 'current_map_name'):
             main_window.server_state.current_map_name = server_map_name
        debug(f"GAME_MODES (Host): Server starting with map: {server_map_name}")
        main_window.network_thread = main_window.NetworkThread(mode="host", game_elements_ref=ge_ref, server_state_ref=main_window.server_state, parent=main_window)
    elif mode_name == "join":
        if not target_ip_port:
            error("GAME_MODES (Join): Target IP:Port required for join mode.");
            _update_status_dialog(main_window, title="Connection Error", message="No target IP specified.", progress=-1.0); return
        main_window.client_state = ClientState() # Create new ClientState instance
        main_window.network_thread = main_window.NetworkThread(mode="join", game_elements_ref=ge_ref, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
    else:
        error(f"GAME_MODES: Unknown network mode specified: {mode_name}"); return

    if main_window.network_thread:
        main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot)
        main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot)
        main_window.network_thread.client_fully_synced_signal.connect(main_window.on_client_fully_synced_for_host)
        main_window.network_thread.start()
        info(f"GAME_MODES: NetworkThread for '{mode_name}' started.")
    else:
        error(f"GAME_MODES: Failed to create NetworkThread for mode '{mode_name}'.")


def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'):
    info("GAME_MODES (Host): Client fully synced. Transitioning game to active state.")
    if main_window.current_game_mode == "host_waiting" and main_window.server_state and hasattr(main_window.server_state, 'client_ready'):
        main_window.current_game_mode = "host_active"
        main_window.server_state.client_ready = True
        _close_status_dialog(main_window)
        info("GAME_MODES (Host): Client connected and synced. Game is now fully active for host.")
    else:
        warning(f"GAME_MODES: Received client_fully_synced_for_host in unexpected state: {main_window.current_game_mode}")


def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float):
    debug(f"GAME_MODES (Net Status Update): Title='{title}', Msg='{message}', Prog={progress}")
    is_network_setup_phase = main_window.current_game_mode in ["host_waiting", "join_ip", "join_lan"]

    if progress == -2.0: _close_status_dialog(main_window); return

    if is_network_setup_phase:
        if not main_window.status_dialog or not main_window.status_dialog.isVisible():
            _show_status_dialog(main_window, title, message)
        if main_window.status_dialog and main_window.status_dialog.isVisible():
             _update_status_dialog(main_window, message=message, progress=progress, title=title)

    if main_window.current_view_name == "game_scene" and \
       (main_window.current_game_mode == "join_active" or main_window.current_game_mode == "host_active"):
        if hasattr(main_window.game_scene_widget, 'update_game_state'):
            if "Downloading" in title or "Synchronizing Map" in title or "Map Error" in title:
                main_window.game_scene_widget.update_game_state(0, download_msg=message, download_prog=progress)
            else:
                main_window.game_scene_widget.update_game_state(0)

    if (title == "Client Map Sync" and "Map ready, starting game" in message and progress >= 99.9) or \
       (title == "Server Hosting" and "Ready for game start" in message and progress >= 99.9 and main_window.current_game_mode == "host_waiting"):
        if main_window.current_game_mode in ["join_lan", "join_ip"]:
            main_window.current_game_mode = "join_active"
            info("GAME_MODES (Client): Map synced and server signaled start. Game active.")
        _close_status_dialog(main_window)


def on_network_operation_finished_logic(main_window: 'MainWindow', result_message: str):
    info(f"GAME_MODES: Network operation finished: {result_message}")
    _close_status_dialog(main_window)
    current_mode_that_finished = str(main_window.current_game_mode)

    stop_current_game_mode_logic(main_window, show_menu=False)

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
       not hasattr(main_window, 'lan_search_status_label') or not main_window.lan_search_status_label or \
       not hasattr(main_window, 'lan_servers_list_widget') or not main_window.lan_servers_list_widget:
        info("LAN search status update received, but dialog/widgets not available. Ignoring.")
        return

    if not isinstance(data_tuple, tuple) or len(data_tuple) != 2:
        warning(f"Malformed data_tuple received in on_lan_server_search_status_update: {data_tuple}")
        return

    status_key, data = data_tuple
    debug(f"LAN Search Status Update: Key='{status_key}', Data='{str(data)[:150]}'")

    if status_key == "searching":
        main_window.lan_search_status_label.setText(str(data))
    elif status_key == "found":
        if isinstance(data, tuple) and len(data) == 3:
            ip, port, map_name_lan = data
            item_text = f"Server at {ip}:{port} (Map: {map_name_lan})"
            found_existing = False
            for i in range(main_window.lan_servers_list_widget.count()):
                item = main_window.lan_servers_list_widget.item(i)
                existing_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(existing_data, tuple) and existing_data[0] == ip and existing_data[1] == port:
                    item.setText(item_text); item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan))
                    found_existing = True; break
            if not found_existing:
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, (ip, port, map_name_lan))
                main_window.lan_servers_list_widget.addItem(list_item)

            if hasattr(main_window.lan_search_dialog, 'buttonBox') and \
               hasattr(main_window.lan_search_dialog.buttonBox(), 'button'): # More robust check
                ok_button = main_window.lan_search_dialog.buttonBox().button(QDialogButtonBox.StandardButton.Ok)
                if ok_button: ok_button.setEnabled(True)

            if main_window.lan_servers_list_widget.count() == 1 and main_window._lan_search_list_selected_idx == -1 :
                 main_window._lan_search_list_selected_idx = 0
            _update_lan_search_list_focus(main_window)

    elif status_key in ["timeout", "error", "cancelled"]:
        msg = str(data) if data else f"Search {status_key}."
        label_text = f"{msg} No servers found." if main_window.lan_servers_list_widget.count() == 0 else f"{msg} Select a server or retry."
        main_window.lan_search_status_label.setText(label_text)
    elif status_key == "final_result":
        if data is None and main_window.lan_servers_list_widget.count() == 0:
            main_window.lan_search_status_label.setText("Search complete. No servers found.")
        elif data is not None:
            ip, port = data
            item_text_final = f"Server at {ip}:{port} (Map via TCP)"
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
            if hasattr(main_window.lan_search_dialog, 'buttonBox') and \
               hasattr(main_window.lan_search_dialog.buttonBox(), 'button'):
                ok_button_final = main_window.lan_search_dialog.buttonBox().button(QDialogButtonBox.StandardButton.Ok)
                if ok_button_final: ok_button_final.setEnabled(True)
        else:
            main_window.lan_search_status_label.setText("Search complete. Select a server or retry.")


def start_lan_server_search_thread_logic(main_window: 'MainWindow'):
    global _lan_search_thread_instance
    info("GAME_MODES: Starting LAN server search thread.")
    if _lan_search_thread_instance and _lan_search_thread_instance.isRunning():
        info("LAN search already running. Stopping and restarting.");
        _lan_search_thread_instance.stop_search()
        if not _lan_search_thread_instance.wait(500):
            _lan_search_thread_instance.terminate(); _lan_search_thread_instance.wait(100)
        _lan_search_thread_instance = None

    if hasattr(main_window, 'lan_servers_list_widget') and main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if hasattr(main_window, 'lan_search_status_label') and main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Initializing search...")
    main_window._lan_search_list_selected_idx = -1
    
    if hasattr(main_window, 'lan_search_dialog') and main_window.lan_search_dialog and \
       hasattr(main_window.lan_search_dialog, 'buttonBox') and \
       hasattr(main_window.lan_search_dialog.buttonBox(), 'button'):
        ok_button_init = main_window.lan_search_dialog.buttonBox().button(QDialogButtonBox.StandardButton.Ok)
        if ok_button_init: ok_button_init.setEnabled(False)

    _lan_search_thread_instance = LANServerSearchThread(main_window)
    _lan_search_thread_instance.search_event_signal.connect(main_window.on_lan_server_search_status_update_slot)
    _lan_search_thread_instance.finished.connect(_lan_search_thread_instance.deleteLater)
    _lan_search_thread_instance.start()


def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'):
    info("GAME_MODES: Attempting to join selected LAN server.")
    if not hasattr(main_window, 'lan_search_dialog') or not main_window.lan_search_dialog or \
       not hasattr(main_window, 'lan_servers_list_widget') or not main_window.lan_servers_list_widget:
        error("LAN dialog/list widget not available for join operation."); return

    selected_item = main_window.lan_servers_list_widget.currentItem()
    if not selected_item:
        if 0 <= main_window._lan_search_list_selected_idx < main_window.lan_servers_list_widget.count():
            selected_item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
        else:
            QMessageBox.warning(main_window.lan_search_dialog, "No Server Selected", "Please select a server from the list to join.")
            return
    if not selected_item:
         QMessageBox.warning(main_window.lan_search_dialog, "Selection Error", "Could not retrieve selected server item.")
         return

    data = selected_item.data(Qt.ItemDataRole.UserRole)
    if not data or not isinstance(data, tuple) or len(data) < 2:
        error(f"Invalid server data associated with list item: {data}")
        QMessageBox.critical(main_window.lan_search_dialog, "Error", "Invalid server data for selected item.")
        return

    ip, port = str(data[0]), int(data[1])
    target_ip_port = f"{ip}:{port}"
    info(f"Selected LAN server: {target_ip_port}")

    main_window.lan_search_dialog.accept()
    setattr(main_window, 'current_modal_dialog', None)

    prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=target_ip_port)