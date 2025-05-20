# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities for PySide6.
PySide6-compatible game object structures.
"""
# version 2.1.2 (Fix Platform and Enemy instantiation args)
import sys
import os
import random
import traceback
import importlib
from typing import Dict, Optional, Any, Tuple, List
import logging # Import the logging module

# PySide6 imports
from PySide6.QtCore import QRectF

# Game imports
import constants as C
from player import Player
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform, Ladder, Lava
from camera import Camera
import config as game_config

DEFAULT_LEVEL_MODULE_NAME = "level_default"

# --- LOGGER SETUP ---
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    _game_setup_handler = logging.StreamHandler(sys.stdout)
    _game_setup_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _game_setup_handler.setFormatter(_game_setup_formatter)
    logger.addHandler(_game_setup_handler)
    logger.setLevel(logging.INFO) 
    logger.propagate = False
    # Removed the initial "Basic logger configured" message here as it was printed by main.py's logger earlier.
    # If game_setup is run standalone or imported before main's logger setup, this would still print.
# --- END OF LOGGER SETUP ---


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

    raw_map_data: Optional[Dict[str, Any]] = None
    target_map_name_for_load = map_module_name if map_module_name else DEFAULT_LEVEL_MODULE_NAME
    loaded_map_name_return: Optional[str] = None

    # --- Load Map Data ---
    if target_map_name_for_load:
        safe_map_name_for_func = target_map_name_for_load.replace('-', '_').replace(' ', '_')
        expected_level_load_func_name = f"load_map_{safe_map_name_for_func}"
        logger.debug(f"GameSetup: Attempting to load map module 'maps.{target_map_name_for_load}' and call '{expected_level_load_func_name}'")

        try:
            map_module_full_path = f"maps.{target_map_name_for_load}"
            if map_module_full_path in sys.modules:
                map_module = importlib.reload(sys.modules[map_module_full_path])
            else:
                map_module = importlib.import_module(map_module_full_path)

            load_level_function = getattr(map_module, expected_level_load_func_name)
            
            # The map loading functions (e.g., load_map_original) in levels.py now return a single dictionary
            raw_map_data = load_level_function() # No arguments needed if maps return full dict
            
            if not isinstance(raw_map_data, dict):
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
        if target_map_name_for_load == DEFAULT_LEVEL_MODULE_NAME:
            logger.critical("GameSetup FATAL: No map data loaded, even after fallback attempt. Exiting initialization.")
            return None
        logger.warning("GameSetup: No specific map loaded. Proceeding with empty/default elements.")
        raw_map_data = {}

    # --- Process Map Data ---
    level_background_color = tuple(raw_map_data.get('background_color', C.LIGHT_BLUE))
    
    player1_spawn_pos_tuple = tuple(raw_map_data.get('player_start_pos_p1', (100.0, float(current_height - (C.TILE_SIZE * 2)))))
    player1_props_for_init = raw_map_data.get('player1_spawn_props', {})
    player2_spawn_pos_tuple = tuple(raw_map_data.get('player_start_pos_p2', (player1_spawn_pos_tuple[0] + C.TILE_SIZE * 2, player1_spawn_pos_tuple[1])))
    player2_props_for_init = raw_map_data.get('player2_spawn_props', {}) # Added for P2 consistency

    level_pixel_width = float(raw_map_data.get('level_pixel_width', current_width * 2))
    lvl_min_y_abs = float(raw_map_data.get('level_min_y_absolute', 0.0))
    lvl_max_y_abs = float(raw_map_data.get('level_max_y_absolute', current_height))
    ground_level_y_ref = float(raw_map_data.get('ground_level_y_ref', lvl_max_y_abs - C.TILE_SIZE))
    ground_platform_height_ref = float(raw_map_data.get('ground_platform_height_ref', C.TILE_SIZE))

    for p_data in raw_map_data.get('platforms_list', []):
        rect_tuple = p_data.get('rect')
        if not rect_tuple or len(rect_tuple) != 4:
            logger.warning(f"Skipping platform with invalid rect data: {p_data}")
            continue
        platforms_list.append(Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                       width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                       color_tuple=tuple(p_data.get('color', C.GRAY)),
                                       platform_type=str(p_data.get('type', 'generic_platform')),
                                       properties=p_data.get('properties', {})))
    for l_data in raw_map_data.get('ladders_list', []):
        rect_tuple = l_data.get('rect')
        if not rect_tuple or len(rect_tuple) != 4:
            logger.warning(f"Skipping ladder with invalid rect data: {l_data}")
            continue
        ladders_list.append(Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                   width=float(rect_tuple[2]), height=float(rect_tuple[3])))
    for h_data in raw_map_data.get('hazards_list', []):
        rect_tuple = h_data.get('rect')
        if not rect_tuple or len(rect_tuple) != 4:
            logger.warning(f"Skipping hazard with invalid rect data: {h_data}")
            continue
        if h_data.get('type', '').lower() == 'hazard_lava' or 'lava' in h_data.get('type', '').lower():
            hazards_list.append(Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                                     width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                                     color_tuple=tuple(h_data.get('color', C.ORANGE_RED))))
        else:
            logger.warning(f"Unknown hazard type: {h_data.get('type')}. Skipping.")

    all_renderable_objects.extend(platforms_list)
    all_renderable_objects.extend(ladders_list)
    all_renderable_objects.extend(hazards_list)

    player1: Optional[Player] = None
    player2: Optional[Player] = None

    if for_game_mode in ["host", "couch_play", "join_lan", "join_ip"]:
        player1 = Player(player1_spawn_pos_tuple[0], player1_spawn_pos_tuple[1], player_id=1, initial_properties=player1_props_for_init)
        if not player1._valid_init: logger.critical("P1 init failed!"); return None
        player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE
        if "joystick" in player1.control_scheme:
            try: player1.joystick_id_idx = int(player1.control_scheme.split('_')[-1])
            except ValueError: player1.joystick_id_idx = None
        all_renderable_objects.append(player1)

    if for_game_mode == "couch_play":
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2, initial_properties=player2_props_for_init)
        if not player2._valid_init: logger.critical("P2 (couch) init failed!"); return None
        player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
        if "joystick" in player2.control_scheme:
            try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
            except ValueError: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)
    elif for_game_mode in ["join_lan", "join_ip", "host"]:
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2, initial_properties=player2_props_for_init)
        if not player2._valid_init: logger.critical("P2 (shell for network) init failed!"); return None
        if for_game_mode != "host": # Client controls P2 if joining
            player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
            if "joystick" in player2.control_scheme:
                try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
                except ValueError: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)

    game_elements_ref_for_proj = {"projectiles_list": projectiles_list, "all_renderable_objects": all_renderable_objects, "platforms_list": platforms_list}
    if player1: player1.game_elements_ref_for_projectiles = game_elements_ref_for_proj
    if player2: player2.game_elements_ref_for_projectiles = game_elements_ref_for_proj

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

    statue_spawns_data_list_from_map = raw_map_data.get('statues_list', []) # Assuming key 'statues_list'
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
                        current_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y) # Properties can be added if Chest supports
                        if current_chest_obj._valid_init:
                            all_renderable_objects.append(current_chest_obj); collectible_list.append(current_chest_obj)
                        else: logger.warning(f"Chest from map at {item_data['pos']} failed init.")
                    except Exception as e: logger.error(f"Error spawning map chest: {e}", exc_info=True)

        if not any(isinstance(item, Chest) for item in collectible_list):
            current_chest_obj = spawn_chest_qt(platforms_list, ground_level_y_ref)
            if current_chest_obj:
                all_renderable_objects.append(current_chest_obj); collectible_list.append(current_chest_obj)
            else: logger.debug("GameSetup: Random chest spawn fallback failed or no suitable platforms.")

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
        "ground_level_y_ref": ground_level_y_ref,
        "ground_platform_height_ref": ground_platform_height_ref,
        "player1_spawn_pos": player1_spawn_pos_tuple,
        "player1_spawn_props": player1_props_for_init,
        "player2_spawn_pos": player2_spawn_pos_tuple,
        "player2_spawn_props": player2_props_for_init,
        "level_background_color": level_background_color,
        "loaded_map_name": loaded_map_name_return,
        "enemy_spawns_data_cache": local_enemy_spawns_data_list
    }
    if current_chest_obj and any(item == current_chest_obj for item in collectible_list):
        game_elements_dict["current_chest"] = current_chest_obj
    elif collectible_list and isinstance(collectible_list[0], Chest):
         game_elements_dict["current_chest"] = collectible_list[0]

    logger.debug(f"GameSetup: Elements initialized. Renderables: {len(all_renderable_objects)}")
    return game_elements_dict


def spawn_chest_qt(platforms_list_qt: List[Platform], main_ground_y_surface: float) -> Optional[Chest]:
    if not Chest: logger.warning("GameSetup (spawn_chest_qt): Chest class not available."); return None
    try:
        suitable_platforms = [p for p in platforms_list_qt if p.rect.width() > C.TILE_SIZE * 1.25 and p.platform_type not in ['wall', 'boundary_wall_top', 'boundary_wall_bottom', 'boundary_wall_left', 'boundary_wall_right']]

        if not suitable_platforms:
            logger.debug("GameSetup (spawn_chest_qt): No suitable platforms for chest spawn."); return None

        chosen_platform = random.choice(suitable_platforms)

        chest_width_approx = C.TILE_SIZE
        min_cx = chosen_platform.rect.left() + chest_width_approx / 2
        max_cx = chosen_platform.rect.right() - chest_width_approx / 2

        if min_cx >= max_cx:
            cx = chosen_platform.rect.center().x()
        else:
            cx = random.uniform(min_cx, max_cx)

        cy_midbottom = chosen_platform.rect.top()

        new_chest = Chest(cx, cy_midbottom)
        if new_chest._valid_init:
            logger.debug(f"GameSetup (spawn_chest_qt): Random chest spawned at ({new_chest.rect.left()},{new_chest.rect.top()}) on platform type '{chosen_platform.platform_type}'")
            return new_chest
        else: logger.warning(f"GameSetup (spawn_chest_qt): New chest at ({cx},{cy_midbottom}) failed init.")
    except Exception as e: logger.error(f"GameSetup Error in spawn_chest_qt: {e}", exc_info=True)
    return None