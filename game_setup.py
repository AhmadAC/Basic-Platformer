#################### START OF FILE: game_setup.py ####################

# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization and FULL RE-INITIALIZATION (reset) of game elements,
levels, and entities. Employs aggressive cache busting for map reloading.
Map paths now use map_name_folder/map_name_file.py structure.
MODIFIED: Adds map-defined Statues to platforms_list.
"""
# version 2.0.7 (Statues added to platforms_list)
import sys
import os
import importlib # For importlib.invalidate_caches()
import gc # Garbage Collector
from typing import Dict, Optional, Any, Tuple, List

from PySide6.QtCore import QRectF

# Game-specific imports
import constants as C
from player import Player
from enemy import Enemy
from items import Chest
from statue import Statue # Ensure Statue is imported
from camera import Camera
from level_loader import LevelLoader
import config as game_config

from tiles import Platform, Ladder, Lava, BackgroundTile

DEFAULT_LEVEL_MODULE_NAME = "original"

try:
    from logger import info, debug, warning, critical, error
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG, format='GAME_SETUP (Fallback): %(levelname)s - %(message)s')
    _fallback_logger_gs = logging.getLogger(__name__ + "_fallback_gs")
    def info(msg, *args, **kwargs): _fallback_logger_gs.info(msg, *args, **kwargs)
    def debug(msg, *args, **kwargs): _fallback_logger_gs.debug(msg, *args, **kwargs)
    def warning(msg, *args, **kwargs): _fallback_logger_gs.warning(msg, *args, **kwargs)
    def critical(msg, *args, **kwargs): _fallback_logger_gs.critical(msg, *args, **kwargs)
    def error(msg, *args, **kwargs): _fallback_logger_gs.error(msg, *args, **kwargs)
    critical("GameSetup: Failed to import project's logger. Using isolated fallback.")


def initialize_game_elements(
    current_width: int, 
    current_height: int, 
    game_elements_ref: Dict[str, Any], 
    for_game_mode: str = "unknown",
    map_module_name: Optional[str] = None
) -> bool:
    current_map_to_load = map_module_name
    if not current_map_to_load:
        current_map_to_load = game_elements_ref.get("map_name", game_elements_ref.get("loaded_map_name"))
        if not current_map_to_load:
            current_map_to_load = DEFAULT_LEVEL_MODULE_NAME
            info(f"GameSetup: No specific map name for (re)load, defaulting to '{DEFAULT_LEVEL_MODULE_NAME}'.")

    info(f"GameSetup: --- FULL MAP (RE)LOAD & ENTITY RE-INITIALIZATION ---")
    info(f"GameSetup: Mode: '{for_game_mode}', Screen: {current_width}x{current_height}, Target Map Folder/Stem: '{current_map_to_load}'")

    debug("GameSetup: Clearing all existing game elements from game_elements_ref...")
    for i in range(1, 5):
        player_key = f"player{i}"
        if player_key in game_elements_ref:
            if isinstance(game_elements_ref[player_key], Player) and hasattr(game_elements_ref[player_key], 'reset_for_new_game_or_round'):
                game_elements_ref[player_key].reset_for_new_game_or_round() # Call reset for input priming
            game_elements_ref[player_key] = None
    game_elements_ref["camera"] = None
    game_elements_ref["current_chest"] = None
    game_elements_ref["level_data"] = None
    list_keys_to_reinitialize = [
        "enemy_list", "statue_objects", "collectible_list", "projectiles_list",
        "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
        "all_renderable_objects", "enemy_spawns_data_cache", "statue_spawns_data_cache"
    ]
    for key in list_keys_to_reinitialize:
        game_elements_ref[key] = []
    game_elements_ref['initialization_in_progress'] = True
    game_elements_ref['game_ready_for_logic'] = False
    game_elements_ref['camera_level_dims_set'] = False
    gc.collect()
    debug("GameSetup: Existing game elements cleared and lists re-initialized.")

    level_data: Optional[Dict[str, Any]] = None
    loader = LevelLoader() 

    maps_base_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs):
        project_root_from_constants = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)
    
    debug(f"GameSetup: Attempting to load map '{current_map_to_load}' using base maps directory '{maps_base_dir_abs}'.")
    level_data = loader.load_map(current_map_to_load, maps_base_dir_abs) 

    if not level_data or not isinstance(level_data, dict):
        critical(f"GameSetup FATAL: Failed to load/reload map data for '{current_map_to_load}' from base '{maps_base_dir_abs}'. Initialization aborted.")
        game_elements_ref["loaded_map_name"] = None
        game_elements_ref['initialization_in_progress'] = False
        return False

    game_elements_ref["level_data"] = level_data
    game_elements_ref["loaded_map_name"] = current_map_to_load
    game_elements_ref["map_name"] = current_map_to_load
    info(f"GameSetup: Successfully reloaded pristine map data for '{current_map_to_load}'.")

    game_elements_ref["level_background_color"] = tuple(level_data.get('background_color', getattr(C, 'LIGHT_BLUE', (173, 216, 230))))
    game_elements_ref["level_pixel_width"] = float(level_data.get('level_pixel_width', float(current_width) * 2.0))
    game_elements_ref["level_min_x_absolute"] = float(level_data.get('level_min_x_absolute', 0.0))
    game_elements_ref["level_min_y_absolute"] = float(level_data.get('level_min_y_absolute', 0.0))
    game_elements_ref["level_max_y_absolute"] = float(level_data.get('level_max_y_absolute', float(current_height)))
    game_elements_ref["ground_level_y_ref"] = float(level_data.get('ground_level_y_ref', game_elements_ref["level_max_y_absolute"] - float(getattr(C, 'TILE_SIZE', 40.0))))
    game_elements_ref["ground_platform_height_ref"] = float(level_data.get('ground_platform_height_ref', float(getattr(C, 'TILE_SIZE', 40.0))))
    
    game_elements_ref["enemy_spawns_data_cache"] = list(level_data.get('enemies_list', []))
    game_elements_ref["statue_spawns_data_cache"] = list(level_data.get('statues_list', [])) # This comes from editor map data

    # Create NEW Static Tile Instances
    for p_data in level_data.get('platforms_list', []):
        try:
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["platforms_list"].append(Platform(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(p_data.get('color', getattr(C, 'GRAY', (128,128,128)))),
                    platform_type=str(p_data.get('type', 'generic_platform')),
                    properties=p_data.get('properties', {}) ))
        except Exception as e_plat: error(f"GameSetup: Error creating platform: {e_plat}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["platforms_list"])
    
    for l_data in level_data.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["ladders_list"].append(Ladder(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]) ))
        except Exception as e_lad: error(f"GameSetup: Error creating ladder: {e_lad}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["ladders_list"])

    for h_data in level_data.get('hazards_list', []):
        try:
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4 and \
               (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()):
                game_elements_ref["hazards_list"].append(Lava(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(h_data.get('color', getattr(C, 'ORANGE_RED', (255,69,0)))) ))
        except Exception as e_haz: error(f"GameSetup: Error creating hazard: {e_haz}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["hazards_list"])

    for bg_data in level_data.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["background_tiles_list"].append(BackgroundTile(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(bg_data.get('color', getattr(C, 'DARK_GRAY', (50,50,50)))),
                    tile_type=str(bg_data.get('type', 'generic_background')),
                    image_path=bg_data.get('image_path'), # This path is relative to map's Custom folder if applicable
                    properties=bg_data.get('properties', {}) ))
        except Exception as e_bg: error(f"GameSetup: Error creating background tile: {e_bg}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["background_tiles_list"])
    info(f"GameSetup: Static map elements re-created. Platforms: {len(game_elements_ref['platforms_list'])}")

    # Create NEW Player Instances
    active_player_count = 0
    tile_sz = float(getattr(C, 'TILE_SIZE', 40.0))
    player1_default_spawn_pos_tuple = (100.0, float(current_height) - (tile_sz * 2.0))

    for i in range(1, 5): 
        player_key = f"player{i}"
        spawn_pos_key = f"player_start_pos_p{i}"
        spawn_props_key = f"player{i}_spawn_props"

        player_spawn_pos_tuple_from_map = level_data.get(spawn_pos_key)
        player_props_for_init_from_map = level_data.get(spawn_props_key, {})
        
        game_elements_ref[spawn_pos_key] = player_spawn_pos_tuple_from_map
        game_elements_ref[spawn_props_key] = player_props_for_init_from_map

        final_spawn_x, final_spawn_y = -1.0, -1.0

        if player_spawn_pos_tuple_from_map and isinstance(player_spawn_pos_tuple_from_map, (tuple, list)) and len(player_spawn_pos_tuple_from_map) == 2:
            final_spawn_x, final_spawn_y = float(player_spawn_pos_tuple_from_map[0]), float(player_spawn_pos_tuple_from_map[1])
        elif i == 1 : 
            final_spawn_x, final_spawn_y = player1_default_spawn_pos_tuple[0], player1_default_spawn_pos_tuple[1]
            game_elements_ref[spawn_pos_key] = (final_spawn_x, final_spawn_y)
            debug(f"GameSetup: {spawn_pos_key} not in map data. Using fallback default for P1: ({final_spawn_x:.1f},{final_spawn_y:.1f})")
        else:
            game_elements_ref[player_key] = None 
            continue

        player_instance = Player(final_spawn_x, final_spawn_y, player_id=i, initial_properties=player_props_for_init_from_map)
        if not player_instance._valid_init:
            critical(f"GameSetup CRITICAL: {player_key} initialization FAILED! Map: '{current_map_to_load}'");
            game_elements_ref[player_key] = None; continue
        
        player_instance.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
        if "joystick" in player_instance.control_scheme:
            try: player_instance.joystick_id_idx = int(player_instance.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player_instance.joystick_id_idx = None
        
        game_elements_ref[player_key] = player_instance
        add_to_renderables_if_new(player_instance, game_elements_ref["all_renderable_objects"])
        player_instance.set_projectile_group_references(
            game_elements_ref["projectiles_list"], 
            game_elements_ref["all_renderable_objects"], 
            game_elements_ref["platforms_list"] # Pass the main platforms list
        )
        active_player_count +=1
        info(f"GameSetup: {player_key} RE-CREATED. Pos: ({final_spawn_x:.1f},{final_spawn_y:.1f}), Control: {player_instance.control_scheme}")
    info(f"GameSetup: Total active players RE-CREATED: {active_player_count}")

    authoritative_modes_for_spawn = ["couch_play", "host_game", "host", "host_waiting", "host_active"]
    if for_game_mode in authoritative_modes_for_spawn:
        debug(f"GameSetup: Re-spawning dynamic entities for authoritative mode '{for_game_mode}'.")
        
        for i_enemy, spawn_info in enumerate(game_elements_ref["enemy_spawns_data_cache"]):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data'); patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']), float(patrol_raw['width']), float(patrol_raw['height']))
                
                enemy_color_name = str(spawn_info.get('type', 'enemy_green'))
                start_pos_tuple = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))
                enemy_props = spawn_info.get('properties', {})

                new_enemy = Enemy(start_x=start_pos_tuple[0], start_y=start_pos_tuple[1], 
                                  patrol_area=patrol_qrectf, enemy_id=i_enemy, 
                                  color_name=enemy_color_name, properties=enemy_props)
                if new_enemy._valid_init:
                    game_elements_ref["enemy_list"].append(new_enemy)
                    add_to_renderables_if_new(new_enemy, game_elements_ref["all_renderable_objects"])
                else: warning(f"GameSetup: Failed to initialize enemy {i_enemy} (type: {enemy_color_name}) during reset.")
            except Exception as e_enemy_create: error(f"GameSetup: Error creating enemy {i_enemy} during reset: {e_enemy_create}", exc_info=True)
        info(f"GameSetup: Enemies re-created: {len(game_elements_ref['enemy_list'])}")

        # MODIFIED: Add map-defined statues to platforms_list
        for i_statue, statue_data in enumerate(game_elements_ref["statue_spawns_data_cache"]):
            try:
                s_id = statue_data.get('id', f"map_statue_rs_{i_statue}") 
                s_pos = tuple(map(float, statue_data.get('pos', (200.0, 200.0))))
                s_props = statue_data.get('properties', {})
                # Pass center_x, center_y to Statue constructor
                new_statue = Statue(s_pos[0], s_pos[1], statue_id=s_id, properties=s_props)
                if new_statue._valid_init:
                    game_elements_ref["statue_objects"].append(new_statue)
                    add_to_renderables_if_new(new_statue, game_elements_ref["all_renderable_objects"])
                    if not new_statue.is_smashed: # Map-defined statues are not initially smashed
                        game_elements_ref["platforms_list"].append(new_statue)
                        debug(f"GameSetup: Map-defined Statue ID {s_id} added to platforms_list.")
                else: warning(f"GameSetup: Failed to initialize statue {i_statue} (id: {s_id}) during reset.")
            except Exception as e_statue_create: error(f"GameSetup: Error creating statue {i_statue} during reset: {e_statue_create}", exc_info=True)
        info(f"GameSetup: Statues re-created: {len(game_elements_ref['statue_objects'])}")
            
        new_chest_instance: Optional[Chest] = None
        items_from_fresh_map_data = level_data.get('items_list', [])
        for item_data_fresh in items_from_fresh_map_data:
            if item_data_fresh.get('type', '').lower() == 'chest':
                try:
                    chest_pos_fresh = tuple(map(float, item_data_fresh.get('pos', (300.0, 300.0))))
                    new_chest_instance = Chest(x=chest_pos_fresh[0], y=chest_pos_fresh[1])
                    
                    if new_chest_instance._valid_init:
                        game_elements_ref["collectible_list"].append(new_chest_instance)
                        add_to_renderables_if_new(new_chest_instance, game_elements_ref["all_renderable_objects"])
                        info(f"GameSetup (Reset): Chest RE-CREATED at {chest_pos_fresh} from fresh map data.")
                    else:
                        warning("GameSetup (Reset): NEW Chest instance from map data failed to initialize.")
                    break 
                except Exception as e_chest_create:
                    error(f"GameSetup: Error creating NEW Chest instance during reset: {e_chest_create}", exc_info=True)
        game_elements_ref["current_chest"] = new_chest_instance 
    else: 
        debug(f"GameSetup: Dynamic entities (enemies, statues, chest) not re-spawned by client for mode '{for_game_mode}'. Server state will dictate.")
        game_elements_ref["current_chest"] = None 

    camera_instance = Camera(
        initial_level_width=game_elements_ref.get("level_pixel_width", float(current_width) * 2.0),
        initial_world_start_x=game_elements_ref.get("level_min_x_absolute", 0.0),
        initial_world_start_y=game_elements_ref.get("level_min_y_absolute", 0.0),
        initial_level_bottom_y_abs=game_elements_ref.get("level_max_y_absolute", float(current_height)),
        screen_width=float(current_width),
        screen_height=float(current_height)
    )
    game_elements_ref["camera"] = camera_instance
    game_elements_ref["camera_level_dims_set"] = True
    
    p1_for_cam = game_elements_ref.get("player1")
    if p1_for_cam and p1_for_cam._valid_init and p1_for_cam.alive():
        camera_instance.update(p1_for_cam)
    else:
        first_active_player_for_cam = None
        for i_p_cam in range(1,5):
            p_check_cam = game_elements_ref.get(f"player{i_p_cam}")
            if p_check_cam and p_check_cam._valid_init and p_check_cam.alive():
                first_active_player_for_cam = p_check_cam; break
        if first_active_player_for_cam: camera_instance.update(first_active_player_for_cam)
        else: camera_instance.static_update()
    info("GameSetup: Camera re-initialized and focused.")

    game_elements_ref["game_ready_for_logic"] = True
    game_elements_ref["initialization_in_progress"] = False
    
    info(f"GameSetup: --- Full Map (Re)Load & Entity Re-Initialization COMPLETE for map '{current_map_to_load}' ---")
    return True

def add_to_renderables_if_new(obj_to_add: Any, renderables_list_ref: List[Any]):
    """Helper to prevent duplicates in all_renderable_objects list."""
    if obj_to_add is not None and obj_to_add not in renderables_list_ref:
        renderables_list_ref.append(obj_to_add)