#################### START OF FILE: game_setup.py ####################

# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities for PySide6.
PySide6-compatible game object structures.
"""
# version 2.1.6 (Initialize local_enemy_spawns_data_list earlier)
import sys
import os
import random
import traceback
import importlib
from typing import Dict, Optional, Any, Tuple, List
import logging

from PySide6.QtCore import QRectF

import constants as C
from player import Player
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform, Ladder, Lava
from camera import Camera
import config as game_config

DEFAULT_LEVEL_MODULE_NAME = "level_default"
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    _gs_handler = logging.StreamHandler(sys.stdout)
    _gs_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _gs_handler.setFormatter(_gs_formatter)
    logger.addHandler(_gs_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.debug("GameSetup: Basic logger configured for game_setup.py")


def initialize_game_elements(current_width: int, current_height: int,
                             for_game_mode: str = "unknown",
                             existing_game_elements: Optional[Dict[str, Any]] = None,
                             map_module_name: Optional[str] = None
                             ) -> Optional[Dict[str, Any]]:
    logger.info(f"GameSetup: Initializing elements. Mode: '{for_game_mode}', Screen Hint: {current_width}x{current_height}, Map: '{map_module_name}'")

    platforms_list: List[Platform] = []
    ladders_list: List[Ladder] = []
    hazards_list: List[Lava] = []
    enemy_list: List[Enemy] = []
    collectible_list: List[Any] = []
    statue_objects_list: List[Statue] = []
    projectiles_list: List[Any] = []
    all_renderable_objects: List[Any] = []
    
    # Initialize local_enemy_spawns_data_list here
    local_enemy_spawns_data_list: List[Dict[str, Any]] = []


    raw_map_data: Optional[Dict[str, Any]] = None
    target_map_name_for_load = map_module_name if map_module_name else DEFAULT_LEVEL_MODULE_NAME
    loaded_map_name_return: Optional[str] = None

    logger.debug(f"GameSetup: Attempting to load map module: 'maps.{target_map_name_for_load}'")
    if target_map_name_for_load:
        safe_map_name_for_func = target_map_name_for_load.replace('-', '_').replace(' ', '_')
        expected_level_load_func_name = f"load_map_{safe_map_name_for_func}"
        logger.debug(f"GameSetup: Map function to call: '{expected_level_load_func_name}'")

        try:
            map_module_full_path = f"maps.{target_map_name_for_load}"
            if map_module_full_path in sys.modules:
                logger.debug(f"GameSetup: Reloading existing map module: {map_module_full_path}")
                map_module = importlib.reload(sys.modules[map_module_full_path])
            else:
                logger.debug(f"GameSetup: Importing new map module: {map_module_full_path}")
                map_module = importlib.import_module(map_module_full_path)

            load_level_function = getattr(map_module, expected_level_load_func_name)
            raw_map_data = load_level_function()
            
            if not isinstance(raw_map_data, dict):
                logger.error(f"Map function '{expected_level_load_func_name}' did not return a dictionary. Returned: {type(raw_map_data)}")
                raise ValueError(f"Map function '{expected_level_load_func_name}' did not return a dictionary.")
            
            logger.info(f"GameSetup: Successfully loaded and called map function for '{target_map_name_for_load}'.")
            loaded_map_name_return = target_map_name_for_load

        except Exception as e:
            logger.critical(f"GameSetup CRITICAL Error processing map '{target_map_name_for_load}': {e}", exc_info=True)
            if target_map_name_for_load != DEFAULT_LEVEL_MODULE_NAME:
                logger.warning(f"GameSetup: Falling back to default map '{DEFAULT_LEVEL_MODULE_NAME}'.")
                return initialize_game_elements(current_width, current_height, for_game_mode, 
                                                existing_game_elements, DEFAULT_LEVEL_MODULE_NAME)
            else:
                logger.critical("GameSetup FATAL: Default map also failed to load. Cannot proceed.")
                return None
    
    if not raw_map_data:
        logger.critical(f"GameSetup FATAL: raw_map_data is None after attempting to load '{target_map_name_for_load}'. Cannot proceed.")
        return None

    logger.debug(f"GameSetup: Raw map data loaded: {list(raw_map_data.keys())}")

    level_background_color = tuple(raw_map_data.get('background_color', C.LIGHT_BLUE))
    
    player1_spawn_pos_tuple = tuple(raw_map_data.get('player_start_pos_p1', (100.0, float(current_height - (C.TILE_SIZE * 2)))))
    player1_props_for_init = raw_map_data.get('player1_spawn_props', {})
    player2_spawn_pos_tuple = tuple(raw_map_data.get('player_start_pos_p2', (player1_spawn_pos_tuple[0] + C.TILE_SIZE * 2, player1_spawn_pos_tuple[1])))
    player2_props_for_init = raw_map_data.get('player2_spawn_props', {})

    level_pixel_width = float(raw_map_data.get('level_pixel_width', current_width * 2))
    lvl_min_y_abs = float(raw_map_data.get('level_min_y_absolute', 0.0))
    lvl_max_y_abs = float(raw_map_data.get('level_max_y_absolute', current_height))
    logger.debug(f"GameSetup: Level Dims from map: W={level_pixel_width}, MinY={lvl_min_y_abs}, MaxY={lvl_max_y_abs}")


    map_platforms_data = raw_map_data.get('platforms_list', [])
    logger.debug(f"GameSetup: Processing {len(map_platforms_data)} platform entries from map data.")
    for i, p_data in enumerate(map_platforms_data):
        rect_tuple = p_data.get('rect')
        if not rect_tuple or len(rect_tuple) != 4:
            logger.warning(f"Skipping platform entry {i} with invalid rect data: {p_data}")
            continue
        platform_properties = p_data.get('properties', {})
        if platform_properties is None: platform_properties = {}
        
        plat_x, plat_y, plat_w, plat_h = float(rect_tuple[0]), float(rect_tuple[1]), float(rect_tuple[2]), float(rect_tuple[3])
        plat_color = tuple(p_data.get('color', C.GRAY))
        plat_type = str(p_data.get('type', 'generic_platform'))

        # logger.debug(f"GameSetup: Platform entry {i} data: rect=({plat_x},{plat_y},{plat_w},{plat_h}), type='{plat_type}', color={plat_color}") # Less verbose now

        new_platform = Platform(x=plat_x, y=plat_y,
                                width=plat_w, height=plat_h,
                                color_tuple=plat_color,
                                platform_type=plat_type,
                                properties=platform_properties)
        platforms_list.append(new_platform)
        # logger.debug(f"  GameSetup: Created Platform {i}: type='{new_platform.platform_type}', rect={new_platform.rect}, color={new_platform.color_tuple}, image_is_null={new_platform.image.isNull()}, image_size={new_platform.image.size() if new_platform.image else 'N/A'}")

    map_hazards_data = raw_map_data.get('hazards_list', [])
    logger.debug(f"GameSetup: Processing {len(map_hazards_data)} hazard entries from map data.")
    for i, h_data in enumerate(map_hazards_data):
        rect_tuple = h_data.get('rect')
        if not rect_tuple or len(rect_tuple) != 4:
            logger.warning(f"Skipping hazard entry {i} with invalid rect data: {h_data}")
            continue
        
        haz_x, haz_y, haz_w, haz_h = float(rect_tuple[0]), float(rect_tuple[1]), float(rect_tuple[2]), float(rect_tuple[3])
        haz_color = tuple(h_data.get('color', C.ORANGE_RED))
        haz_type_str = str(h_data.get('type', '')).lower()

        # logger.debug(f"GameSetup: Hazard entry {i} data: rect=({haz_x},{haz_y},{haz_w},{haz_h}), type='{haz_type_str}', color={haz_color}") # Less verbose now

        if 'lava' in haz_type_str:
            new_lava = Lava(x=haz_x, y=haz_y,
                            width=haz_w, height=haz_h,
                            color_tuple=haz_color)
            hazards_list.append(new_lava)
            # logger.debug(f"  GameSetup: Created Lava {i}: rect={new_lava.rect}, color={new_lava.color_tuple}, image_is_null={new_lava.image.isNull()}, image_size={new_lava.image.size() if new_lava.image else 'N/A'}")
        else:
            logger.warning(f"Unknown hazard type: {h_data.get('type')}. Skipping hazard {i}.")

    all_renderable_objects.extend(platforms_list)
    all_renderable_objects.extend(ladders_list)
    all_renderable_objects.extend(hazards_list)
    # logger.debug(f"GameSetup: Extended all_renderable_objects with {len(platforms_list)} platforms, {len(ladders_list)} ladders, {len(hazards_list)} hazards.")

    player1: Optional[Player] = None
    player2: Optional[Player] = None
    if for_game_mode in ["host", "couch_play", "join_lan", "join_ip"]:
        logger.debug(f"GameSetup: Initializing Player 1 at {player1_spawn_pos_tuple}")
        player1 = Player(player1_spawn_pos_tuple[0], player1_spawn_pos_tuple[1], player_id=1, initial_properties=player1_props_for_init)
        if not player1._valid_init: logger.critical("P1 init failed!"); return None
        player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE
        if "joystick" in player1.control_scheme:
            try: player1.joystick_id_idx = int(player1.control_scheme.split('_')[-1])
            except ValueError: player1.joystick_id_idx = None
        all_renderable_objects.append(player1)
        # logger.debug(f"GameSetup: Player 1 initialized. Valid: {player1._valid_init}, Rect: {player1.rect}")

    if for_game_mode == "couch_play":
        logger.debug(f"GameSetup: Initializing Player 2 (couch) at {player2_spawn_pos_tuple}")
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2, initial_properties=player2_props_for_init)
        if not player2._valid_init: logger.critical("P2 (couch) init failed!"); return None
        player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
        if "joystick" in player2.control_scheme:
            try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
            except ValueError: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)
        # logger.debug(f"GameSetup: Player 2 (couch) initialized. Valid: {player2._valid_init}, Rect: {player2.rect}")
    elif for_game_mode in ["join_lan", "join_ip", "host"]:
        logger.debug(f"GameSetup: Initializing Player 2 (network shell) at {player2_spawn_pos_tuple}")
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2, initial_properties=player2_props_for_init)
        if not player2._valid_init: logger.critical("P2 (network shell) init failed!"); return None
        if for_game_mode != "host":
            player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
            if "joystick" in player2.control_scheme:
                try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
                except ValueError: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)
        # logger.debug(f"GameSetup: Player 2 (network shell) initialized. Valid: {player2._valid_init}, Rect: {player2.rect}")

    game_elements_ref_for_proj = {"projectiles_list": projectiles_list, "all_renderable_objects": all_renderable_objects, "platforms_list": platforms_list}
    if player1: player1.game_elements_ref_for_projectiles = game_elements_ref_for_proj
    if player2: player2.game_elements_ref_for_projectiles = game_elements_ref_for_proj

    # Assign from map data if present, otherwise it remains the empty list from above
    local_enemy_spawns_data_list = raw_map_data.get('enemies_list', [])

    if (for_game_mode == "host" or for_game_mode == "couch_play") and local_enemy_spawns_data_list:
        logger.debug(f"GameSetup: Spawning {len(local_enemy_spawns_data_list)} enemies from map data...")
        for i, spawn_info in enumerate(local_enemy_spawns_data_list):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data')
                patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']),
                                           float(patrol_raw['width']), float(patrol_raw['height']))
                enemy_color_name_from_map = str(spawn_info.get('type', f'default_enemy_type_{i}'))
                enemy_instance = Enemy(start_x=float(spawn_info['start_pos'][0]),
                                       start_y=float(spawn_info['start_pos'][1]),
                                       patrol_area=patrol_qrectf,
                                       enemy_id=i,
                                       color_name=enemy_color_name_from_map,
                                       properties=spawn_info.get('properties', {}))
                if enemy_instance._valid_init:
                    all_renderable_objects.append(enemy_instance); enemy_list.append(enemy_instance)
                else: logger.warning(f"Enemy {i} (Type: {enemy_color_name_from_map}) at {spawn_info['start_pos']} failed init.")
            except Exception as e: logger.error(f"Error spawning enemy {i}: {e}", exc_info=True)

    statue_spawns_data_list_from_map = raw_map_data.get('statues_list', [])
    if (for_game_mode == "host" or for_game_mode == "couch_play") and statue_spawns_data_list_from_map:
        for i, statue_data in enumerate(statue_spawns_data_list_from_map):
            try:
                s_id = statue_data.get('id', f"map_statue_{i}")
                s_pos_x, s_pos_y = float(statue_data['pos'][0]), float(statue_data['pos'][1])
                new_statue = Statue(s_pos_x, s_pos_y, statue_id=s_id, properties=statue_data.get('properties', {}))
                if new_statue._valid_init:
                    all_renderable_objects.append(new_statue); statue_objects_list.append(new_statue)
                else: logger.warning(f"Statue {s_id} at {statue_data['pos']} failed init.")
            except Exception as e: logger.error(f"Error spawning statue {i}: {e}", exc_info=True)

    current_chest_obj: Optional[Chest] = None
    collectible_spawns_data_list_from_map = raw_map_data.get('items_list', [])
    if Chest and (for_game_mode == "host" or for_game_mode == "couch_play"):
        if collectible_spawns_data_list_from_map:
            for item_data in collectible_spawns_data_list_from_map:
                if item_data.get('type', '').lower() == 'chest':
                    try:
                        chest_midbottom_x, chest_midbottom_y = float(item_data['pos'][0]), float(item_data['pos'][1])
                        logger.debug(f"GameSetup: Attempting to create Chest at ({chest_midbottom_x}, {chest_midbottom_y})")
                        current_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y)
                        if current_chest_obj._valid_init:
                            all_renderable_objects.append(current_chest_obj)
                            collectible_list.append(current_chest_obj)
                            # logger.debug(f"  GameSetup: Created Chest from map: rect={current_chest_obj.rect}, image_null={current_chest_obj.image.isNull() if current_chest_obj.image else 'ImageIsNone'}, state={current_chest_obj.state}, image_size={current_chest_obj.image.size() if current_chest_obj.image else 'N/A'}")
                        else:
                            logger.warning(f"Chest from map at {item_data['pos']} failed init.")
                        break 
                    except Exception as e:
                        logger.error(f"Error spawning map chest: {e}", exc_info=True)
        else:
            logger.debug("GameSetup: No chest defined in map data. No chest will be spawned.")
            
    # logger.debug(f"GameSetup: Initializing Camera. Level W={level_pixel_width}, MinY={lvl_min_y_abs}, MaxY={lvl_max_y_abs}, Screen {current_width}x{current_height}")
    camera_instance = Camera(level_pixel_width, lvl_min_y_abs, lvl_max_y_abs, float(current_width), float(current_height))

    game_elements_dict = {
        "player1": player1, "player2": player2, "camera": camera_instance,
        "enemy_list": enemy_list,
        "platforms_list": platforms_list,
        "ladders_list": ladders_list,
        "hazards_list": hazards_list,
        "collectible_list": collectible_list,
        "projectiles_list": projectiles_list,
        "all_renderable_objects": all_renderable_objects,
        "statue_objects_list": statue_objects_list,
        "level_pixel_width": level_pixel_width,
        "level_min_y_absolute": lvl_min_y_abs,
        "level_max_y_absolute": lvl_max_y_abs,
        "ground_level_y_ref": float(raw_map_data.get('ground_level_y_ref', lvl_max_y_abs - C.TILE_SIZE)),
        "ground_platform_height_ref": float(raw_map_data.get('ground_platform_height_ref', C.TILE_SIZE)),
        "player1_spawn_pos": player1_spawn_pos_tuple,
        "player1_spawn_props": player1_props_for_init,
        "player2_spawn_pos": player2_spawn_pos_tuple,
        "player2_spawn_props": player2_props_for_init,
        "level_background_color": level_background_color,
        "loaded_map_name": loaded_map_name_return,
        "enemy_spawns_data_cache": local_enemy_spawns_data_list, # Now always defined
        "main_app_screen_width": current_width,
        "main_app_screen_height": current_height,
        "current_chest": current_chest_obj
    }

    # logger.debug(f"GameSetup: Final all_renderable_objects count: {len(all_renderable_objects)}")
    # num_platforms_final = sum(1 for obj in all_renderable_objects if isinstance(obj, Platform))
    # num_lava_final = sum(1 for obj in all_renderable_objects if isinstance(obj, Lava))
    # logger.debug(f"GameSetup: Final counts in all_renderable_objects - Platforms: {num_platforms_final}, Lava: {num_lava_final}")

    logger.info(f"GameSetup: Initialization complete for mode '{for_game_mode}'.")
    return game_elements_dict


def spawn_chest_qt(platforms_list_qt: List[Platform], main_ground_y_surface: float) -> Optional[Chest]:
    logger.warning("GameSetup (spawn_chest_qt): This function for random chest spawning is deprecated and should not be called if chests are map-defined.")
    return None

#################### END OF FILE: game_setup.py ####################