# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization and FULL RE-INITIALIZATION (reset) of game elements,
levels, and entities. Employs aggressive cache busting for map reloading.
"""
# version 2.0.4 (Aggressive map module cache busting for reset)
import sys
import os
import importlib
import gc # Garbage Collector
from typing import Dict, Optional, Any, Tuple, List

from PySide6.QtCore import QRectF

import constants as C
from player import Player
from enemy import Enemy
from items import Chest
from statue import Statue
from camera import Camera
from level_loader import LevelLoader # LevelLoader itself should handle import/reload
import config as game_config

from tiles import Platform, Ladder, Lava, BackgroundTile

DEFAULT_LEVEL_MODULE_NAME = "level_default"

try:
    from logger import info, debug, warning, critical, error
except ImportError:
    print("CRITICAL GAME_SETUP: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")

def initialize_game_elements(
    current_width: int,
    current_height: int,
    game_elements_ref: Dict[str, Any], # This dictionary will be modified IN-PLACE
    for_game_mode: str = "unknown",
    map_module_name: Optional[str] = None
) -> bool:
    """
    Terminates existing game elements and re-initializes all game elements
    by reloading the map file from disk and rebuilding all entities.
    Modifies game_elements_ref in-place.
    """
    # Determine the map to load. Prioritize provided name, then existing, then default.
    current_map_to_load = map_module_name
    if not current_map_to_load:
        current_map_to_load = game_elements_ref.get("loaded_map_name")
        if not current_map_to_load:
            current_map_to_load = DEFAULT_LEVEL_MODULE_NAME
            info(f"GameSetup: No specific map name provided or found in game_elements, defaulting to '{DEFAULT_LEVEL_MODULE_NAME}'.")

    info(f"GameSetup: FULL MAP RESET & RE-INITIALIZATION. Mode: '{for_game_mode}', Screen: {current_width}x{current_height}, Target Map: '{current_map_to_load}'")

    # --- 1. Aggressively Clear Existing Game Elements from the passed-in dictionary ---
    debug("GameSetup: Aggressively clearing game_elements_ref...")
    
    # Remove player instances (allow garbage collection)
    for i in range(1, 5):
        player_key = f"player{i}"
        if player_key in game_elements_ref and game_elements_ref[player_key] is not None:
            # If players are PySide QObjects or Pygame Sprites with a kill() method:
            # if hasattr(game_elements_ref[player_key], 'kill'):
            #     try:
            #         game_elements_ref[player_key].kill() # For Pygame sprites
            #     except Exception as e_kill:
            #         debug(f"GameSetup: Error during player {i} kill(): {e_kill}")
            game_elements_ref[player_key] = None
    
    if "camera" in game_elements_ref and game_elements_ref["camera"] is not None:
        # If camera has explicit cleanup, call it
        # if hasattr(game_elements_ref["camera"], 'cleanup'): game_elements_ref["camera"].cleanup()
        game_elements_ref["camera"] = None

    if "current_chest" in game_elements_ref and game_elements_ref["current_chest"] is not None:
        # if hasattr(game_elements_ref["current_chest"], 'kill'): game_elements_ref["current_chest"].kill()
        game_elements_ref["current_chest"] = None

    # Clear all lists that will be repopulated
    list_keys_to_clear = [
        "enemy_list", "statue_objects", "collectible_list", "projectiles_list",
        "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
        "all_renderable_objects"
    ]
    for key in list_keys_to_clear:
        if key in game_elements_ref:
            if isinstance(game_elements_ref[key], list):
                # For lists of complex objects, just clearing the list is usually enough for Python's GC
                # if there are no other strong references.
                game_elements_ref[key].clear()
            else: # If it wasn't a list, re-initialize as empty list
                game_elements_ref[key] = []
        else: # Ensure the key exists as an empty list
            game_elements_ref[key] = []

    # Call garbage collector to be extra sure old objects are released if possible
    gc.collect()
    debug("GameSetup: Existing game elements cleared and garbage collected.")

    # --- 2. Force Reload Map Data from Disk ---
    level_data: Optional[Dict[str, Any]] = None
    loader = LevelLoader() # LevelLoader already handles importlib.reload

    maps_dir_path_for_loader = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_dir_path_for_loader):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_guess = os.path.dirname(current_file_dir)
        if not os.path.isdir(os.path.join(project_root_guess, "maps")):
             project_root_guess = os.path.dirname(project_root_guess)
        maps_dir_path_for_loader = os.path.join(str(project_root_guess), maps_dir_path_for_loader)

    # AGGRESSIVE CACHE BUSTING for the map module
    map_module_py_name = f"maps.{current_map_to_load}"
    if map_module_py_name in sys.modules:
        debug(f"GameSetup: Removing '{map_module_py_name}' from sys.modules to force re-read from disk.")
        del sys.modules[map_module_py_name]
        # importlib.invalidate_caches() # Further ensure filesystem checks

    level_data = loader.load_map(current_map_to_load, maps_dir_path_for_loader)

    if not level_data or not isinstance(level_data, dict):
        critical(f"GameSetup FATAL: Failed to load/reload map data for '{current_map_to_load}'. Reset aborted.")
        game_elements_ref["loaded_map_name"] = None # Indicate failure
        # Optionally, try to load a default/empty map state here
        return False
    
    # Store the freshly loaded data IN THE PASSED-IN REFERENCE
    game_elements_ref["level_data"] = level_data
    game_elements_ref["loaded_map_name"] = current_map_to_load
    info(f"GameSetup: Successfully reloaded pristine map data for '{current_map_to_load}'.")

    # --- 3. Populate Game Elements from Freshly Loaded Map Data (modifying game_elements_ref) ---
    # Update core map properties
    game_elements_ref["level_background_color"] = tuple(level_data.get('background_color', C.LIGHT_BLUE))
    game_elements_ref["level_pixel_width"] = float(level_data.get('level_pixel_width', current_width * 2.0))
    game_elements_ref["level_min_x_absolute"] = float(level_data.get('level_min_x_absolute', 0.0))
    game_elements_ref["level_min_y_absolute"] = float(level_data.get('level_min_y_absolute', 0.0))
    game_elements_ref["level_max_y_absolute"] = float(level_data.get('level_max_y_absolute', float(current_height)))
    game_elements_ref["ground_level_y_ref"] = float(level_data.get('ground_level_y_ref', game_elements_ref["level_max_y_absolute"] - C.TILE_SIZE))
    game_elements_ref["ground_platform_height_ref"] = float(level_data.get('ground_platform_height_ref', C.TILE_SIZE))
    game_elements_ref["enemy_spawns_data_cache"] = list(level_data.get('enemies_list', [])) # For server logic, if needed
    game_elements_ref["statue_spawns_data_cache"] = list(level_data.get('statues_list', [])) # For server logic

    # Create Static Tile Instances (these lists were cleared above)
    for p_data in level_data.get('platforms_list', []):
        try:
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["platforms_list"].append(Platform(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(p_data.get('color', C.GRAY)),
                    platform_type=str(p_data.get('type', 'generic_platform')),
                    properties=p_data.get('properties', {}) ))
        except Exception as e: error(f"GameSetup: Error creating platform: {e}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["platforms_list"])
    
    for l_data in level_data.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["ladders_list"].append(Ladder(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]) ))
        except Exception as e: error(f"GameSetup: Error creating ladder: {e}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["ladders_list"])

    for h_data in level_data.get('hazards_list', []):
        try:
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4 and \
               (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()):
                game_elements_ref["hazards_list"].append(Lava(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(h_data.get('color', C.ORANGE_RED)) ))
        except Exception as e: error(f"GameSetup: Error creating hazard: {e}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["hazards_list"])

    for bg_data in level_data.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["background_tiles_list"].append(BackgroundTile(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(bg_data.get('color', C.DARK_GRAY)),
                    tile_type=str(bg_data.get('type', 'generic_background')),
                    image_path=bg_data.get('image_path'),
                    properties=bg_data.get('properties', {}) ))
        except Exception as e: error(f"GameSetup: Error creating background tile: {e}", exc_info=True)
    game_elements_ref["all_renderable_objects"].extend(game_elements_ref["background_tiles_list"])

    # Create Player Instances (Up to 4, if defined in map)
    active_player_count = 0
    player1_default_spawn_pos_x = float(level_data.get('player_start_pos_p1', (100.0, float(current_height - (C.TILE_SIZE * 2))))[0])
    player1_default_spawn_pos_y = float(level_data.get('player_start_pos_p1', (100.0, float(current_height - (C.TILE_SIZE * 2))))[1])

    for i in range(1, 5): 
        player_key = f"player{i}"
        spawn_pos_key = f"player_start_pos_p{i}"
        spawn_props_key = f"player{i}_spawn_props"

        player_spawn_pos_tuple = level_data.get(spawn_pos_key)
        player_props_for_init = level_data.get(spawn_props_key, {})
        game_elements_ref[spawn_pos_key] = player_spawn_pos_tuple # Store original spawn pos from map
        game_elements_ref[spawn_props_key] = player_props_for_init # Store original props

        if player_spawn_pos_tuple and isinstance(player_spawn_pos_tuple, (tuple, list)) and len(player_spawn_pos_tuple) == 2:
            spawn_x = float(player_spawn_pos_tuple[0])
            spawn_y = float(player_spawn_pos_tuple[1])
        elif i == 1 :
            spawn_x = player1_default_spawn_pos_x
            spawn_y = player1_default_spawn_pos_y
            game_elements_ref[spawn_pos_key] = (spawn_x, spawn_y) # Store default if not in map
            debug(f"GameSetup: {spawn_pos_key} not in map data. Using default for P1: ({spawn_x},{spawn_y})")
        else:
            game_elements_ref[player_key] = None
            continue

        player_instance = Player(spawn_x, spawn_y, player_id=i, initial_properties=player_props_for_init)
        if not player_instance._valid_init:
            critical(f"GameSetup CRITICAL: {player_key} initialization failed!");
            game_elements_ref[player_key] = None; continue
        
        player_instance.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
        if "joystick" in player_instance.control_scheme:
            try: player_instance.joystick_id_idx = int(player_instance.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player_instance.joystick_id_idx = None
        
        game_elements_ref[player_key] = player_instance
        game_elements_ref["all_renderable_objects"].append(player_instance)
        player_instance.set_projectile_group_references(
            game_elements_ref["projectiles_list"], 
            game_elements_ref["all_renderable_objects"], 
            game_elements_ref["platforms_list"]
        )
        active_player_count +=1
        info(f"GameSetup: {player_key} created. Control: {player_instance.control_scheme}")
    info(f"GameSetup: Total active players created: {active_player_count}")

    # Spawn Dynamic Entities (Enemies, Statues, Chest) - if server/authoritative
    authoritative_modes_for_spawn = ["couch_play", "host"]
    if for_game_mode in authoritative_modes_for_spawn:
        debug(f"GameSetup: Spawning dynamic entities for authoritative mode '{for_game_mode}'.")
        enemy_spawns_from_data = level_data.get('enemies_list', [])
        for i, spawn_info in enumerate(enemy_spawns_from_data):
            # ... (Enemy creation as before) ...
            try:
                patrol_raw = spawn_info.get('patrol_rect_data')
                patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']), float(patrol_raw['width']), float(patrol_raw['height']))
                enemy_color_name = str(spawn_info.get('type', 'enemy_green'))
                start_pos = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))
                props = spawn_info.get('properties', {})
                new_enemy = Enemy(start_x=start_pos[0], start_y=start_pos[1], patrol_area=patrol_qrectf, enemy_id=i, color_name=enemy_color_name, properties=props)
                if new_enemy._valid_init and new_enemy.alive():
                    game_elements_ref["enemy_list"].append(new_enemy); game_elements_ref["all_renderable_objects"].append(new_enemy)
            except Exception as e: error(f"GameSetup: Error spawning enemy {i}: {e}", exc_info=True)

        statue_spawns_from_data = level_data.get('statues_list', [])
        for i, statue_data in enumerate(statue_spawns_from_data):
            # ... (Statue creation as before) ...
            try:
                s_id = statue_data.get('id', f"map_statue_{i}")
                s_pos = tuple(map(float, statue_data.get('pos', (200.0, 200.0))))
                s_props = statue_data.get('properties', {})
                new_statue = Statue(s_pos[0], s_pos[1], statue_id=s_id, properties=s_props)
                if new_statue._valid_init and new_statue.alive():
                    game_elements_ref["statue_objects"].append(new_statue); game_elements_ref["all_renderable_objects"].append(new_statue)
            except Exception as e: error(f"GameSetup: Error spawning statue {i}: {e}", exc_info=True)
            
        current_chest_obj: Optional[Chest] = None
        items_from_data = level_data.get('items_list', [])
        if items_from_data:
            for item_data in items_from_data:
                if item_data.get('type', '').lower() == 'chest':
                    # ... (Chest creation as before) ...
                    try:
                        chest_pos = tuple(map(float, item_data.get('pos', (300.0, 300.0))))
                        current_chest_obj = Chest(chest_pos[0], chest_pos[1])
                        if current_chest_obj._valid_init:
                            game_elements_ref["collectible_list"].append(current_chest_obj); game_elements_ref["all_renderable_objects"].append(current_chest_obj)
                            info(f"GameSetup: Chest spawned at {chest_pos} from map data.")
                        else: warning("GameSetup: Chest from map data failed to init.")
                        break 
                    except Exception as e: error(f"GameSetup: Error spawning chest from map data: {e}", exc_info=True)
        game_elements_ref["current_chest"] = current_chest_obj
    else:
        debug(f"GameSetup: Dynamic entities not spawned for mode '{for_game_mode}'.")
        game_elements_ref["current_chest"] = None

    # --- Camera Initialization ---
    camera_instance = Camera(
        initial_level_width=game_elements_ref["level_pixel_width"],
        initial_world_start_x=game_elements_ref["level_min_x_absolute"],
        initial_world_start_y=game_elements_ref["level_min_y_absolute"],
        initial_level_bottom_y_abs=game_elements_ref["level_max_y_absolute"],
        screen_width=float(current_width),
        screen_height=float(current_height)
    )
    game_elements_ref["camera"] = camera_instance
    
    game_elements_ref["game_ready_for_logic"] = True
    game_elements_ref["initialization_in_progress"] = False
    game_elements_ref["camera_level_dims_set"] = True

    info(f"GameSetup: Re-initialization complete for map '{current_map_to_load}'. Mode '{for_game_mode}'.")
    return True

# Removed the old spawn_chest function for random placement.