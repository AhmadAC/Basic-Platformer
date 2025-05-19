#################### START OF FILE: game_setup.py ####################

# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities for PySide6.
Translates map data from (currently) Pygame-based level files into
PySide6-compatible game object structures.
"""
# version 2.0.0 (PySide6 Refactor)
import sys
import os
import random
import traceback
import importlib
from typing import Dict, Optional, Any, Tuple, List

# PySide6 imports (minimal, as this module creates data structures)
from PySide6.QtCore import QRectF # For patrol_area if used with QRectF

# Game imports (refactored classes)
import constants as C
from player import Player
from enemy import Enemy
from items import Chest # Refactored Chest
from statue import Statue # Refactored Statue
from tiles import Platform, Ladder, Lava # Refactored tile classes
from camera import Camera # Refactored Camera
import config as game_config

DEFAULT_LEVEL_MODULE_NAME = "level_default"

try:
    from logger import info, debug, warning, critical, error
except ImportError:
    print("CRITICAL GAME_SETUP: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    def error(msg): print(f"ERROR: {msg}")

def initialize_game_elements(current_width: int, current_height: int,
                             for_game_mode: str = "unknown",
                             existing_game_elements: Optional[Dict[str, Any]] = None, # Changed name
                             map_module_name: Optional[str] = None
                             ) -> Optional[Dict[str, Any]]:
    info(f"GameSetup: Initializing elements for PySide6. Mode: '{for_game_mode}', Screen: {current_width}x{current_height}, Map: '{map_module_name}'")

    # Initialize lists to hold game objects
    platforms_list: List[Platform] = []
    ladders_list: List[Ladder] = []
    hazards_list: List[Lava] = []
    enemy_list: List[Enemy] = []
    collectible_list: List[Chest] = [] # For chests, etc.
    statue_objects_list: List[Statue] = []
    
    # For projectiles, if we preserve them across resets, they'd also be in a list.
    # For now, assume projectiles are cleared on full setup.
    projectiles_list: List[Any] = [] # List of Projectile instances
    
    # This "all_renderable_objects" list will replace all_sprites group for drawing logic
    all_renderable_objects: List[Any] = []

    level_data_loaded_successfully = False
    target_map_name_for_load = map_module_name if map_module_name else DEFAULT_LEVEL_MODULE_NAME

    # Default values, to be overridden by loaded map data
    level_background_color = C.LIGHT_BLUE
    local_enemy_spawns_data_list: List[Dict[str,Any]] = []
    collectible_spawns_data_list_from_map: List[Dict[str,Any]] = [] # Renamed for clarity
    statue_spawns_data_list_from_map: List[Dict[str,Any]] = [] # Renamed for clarity

    # Default player spawn positions (midbottom reference)
    player1_spawn_pos_tuple: Tuple[float, float] = (100.0, float(current_height - (C.TILE_SIZE * 2)))
    player1_props_for_init = {}
    player2_spawn_pos_tuple: Tuple[float, float] = (150.0, float(current_height - (C.TILE_SIZE * 2)))

    level_pixel_width = float(current_width)
    lvl_min_y_abs = 0.0
    lvl_max_y_abs = float(current_height)
    ground_level_y_ref = float(current_height - C.TILE_SIZE)
    ground_platform_height_ref = float(C.TILE_SIZE)
    loaded_map_name_return: Optional[str] = None

    if target_map_name_for_load:
        safe_map_name_for_func = target_map_name_for_load.replace('-', '_').replace(' ', '_')
        expected_level_load_func_name = f"load_map_{safe_map_name_for_func}"
        debug(f"GameSetup: Attempting to load map module 'maps.{target_map_name_for_load}' and call '{expected_level_load_func_name}'")

        try:
            map_module_full_path = f"maps.{target_map_name_for_load}"
            if map_module_full_path in sys.modules:
                map_module = importlib.reload(sys.modules[map_module_full_path])
            else:
                map_module = importlib.import_module(map_module_full_path)

            load_level_function = getattr(map_module, expected_level_load_func_name)
            
            # The loaded map function still returns Pygame sprite groups and Pygame-based values
            pg_platforms, pg_ladders, pg_hazards, enemy_spawns_raw, collectible_spawns_raw, \
            p1_spawn_raw, p1_props_raw, map_width_raw, min_y_raw, max_y_raw, \
            ground_y_raw, ground_h_raw, bg_color_raw, statues_raw = \
                load_level_function(current_width, current_height) # Call the Pygame map loader

            # --- Translate Pygame map data to PySide6-compatible objects ---
            if pg_platforms:
                for pg_plat in pg_platforms: # pg_plat is a pygame.sprite.Sprite (Platform from old tiles.py)
                    platforms_list.append(Platform(float(pg_plat.rect.x), float(pg_plat.rect.y),
                                                   float(pg_plat.rect.width), float(pg_plat.rect.height),
                                                   pg_plat.color, pg_plat.platform_type))
            if pg_ladders:
                for pg_lad in pg_ladders:
                    ladders_list.append(Ladder(float(pg_lad.rect.x), float(pg_lad.rect.y),
                                               float(pg_lad.rect.width), float(pg_lad.rect.height)))
            if pg_hazards:
                for pg_haz in pg_hazards: # Assuming pg_haz is a Lava instance from old tiles.py
                    if isinstance(pg_haz, Lava): # Check to be sure (old Lava class)
                         hazards_list.append(Lava(float(pg_haz.rect.x), float(pg_haz.rect.y),
                                                  float(pg_haz.rect.width), float(pg_haz.rect.height),
                                                  pg_haz.color_tuple if hasattr(pg_haz, 'color_tuple') else C.ORANGE_RED))
            
            local_enemy_spawns_data_list = enemy_spawns_raw if isinstance(enemy_spawns_raw, list) else []
            collectible_spawns_data_list_from_map = collectible_spawns_raw if isinstance(collectible_spawns_raw, list) else []
            statue_spawns_data_list_from_map = statues_raw if isinstance(statues_raw, list) else []

            player1_spawn_pos_tuple = (float(p1_spawn_raw[0]), float(p1_spawn_raw[1]))
            player1_props_for_init = p1_props_raw if isinstance(p1_props_raw, dict) else {}
            
            p2_spawn_x = player1_spawn_pos_tuple[0] + C.TILE_SIZE * 1.5
            if isinstance(map_width_raw, (int, float)) and map_width_raw > 0:
                if p2_spawn_x + (C.TILE_SIZE / 2.0) > map_width_raw - C.TILE_SIZE:
                    p2_spawn_x = map_width_raw - C.TILE_SIZE * 2.5
                if p2_spawn_x - (C.TILE_SIZE / 2.0) < C.TILE_SIZE:
                    p2_spawn_x = C.TILE_SIZE * 2.5
            player2_spawn_pos_tuple = (p2_spawn_x, player1_spawn_pos_tuple[1])

            level_pixel_width = float(map_width_raw) if isinstance(map_width_raw, (int,float)) else float(current_width)
            lvl_min_y_abs = float(min_y_raw) if isinstance(min_y_raw, (int,float)) else 0.0
            lvl_max_y_abs = float(max_y_raw) if isinstance(max_y_raw, (int,float)) else float(current_height)
            ground_level_y_ref = float(ground_y_raw) if isinstance(ground_y_raw, (int,float)) else float(current_height - C.TILE_SIZE)
            ground_platform_height_ref = float(ground_h_raw) if isinstance(ground_h_raw, (int,float)) else float(C.TILE_SIZE)
            
            if isinstance(bg_color_raw, (tuple, list)) and len(bg_color_raw) == 3:
                level_background_color = bg_color_raw

            debug(f"GameSetup: Pygame level data translated. Platforms: {len(platforms_list)}, Ladders: {len(ladders_list)}, Hazards: {len(hazards_list)}")
            level_data_loaded_successfully = True
            loaded_map_name_return = target_map_name_for_load

        except Exception as e:
            critical(f"GameSetup CRITICAL Error processing map '{target_map_name_for_load}': {e}"); traceback.print_exc()
            if target_map_name_for_load != DEFAULT_LEVEL_MODULE_NAME:
                warning(f"GameSetup: Falling back to default map '{DEFAULT_LEVEL_MODULE_NAME}'.")
                return initialize_game_elements(current_width, current_height, for_game_mode, existing_game_elements, DEFAULT_LEVEL_MODULE_NAME)
            else: critical("GameSetup FATAL: Default map also failed."); return None
    else:
        debug("GameSetup: No map module name provided. Using default values for level geometry.")
        loaded_map_name_return = None # Or "default_empty_map"

    all_renderable_objects.extend(platforms_list)
    all_renderable_objects.extend(ladders_list)
    all_renderable_objects.extend(hazards_list)

    player1: Optional[Player] = None
    player2: Optional[Player] = None

    if for_game_mode in ["host", "couch_play", "join_lan", "join_ip"]:
        player1 = Player(player1_spawn_pos_tuple[0], player1_spawn_pos_tuple[1], player_id=1)
        if not player1._valid_init: critical("P1 init failed!"); return None
        player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE
        if "joystick" in player1.control_scheme:
            try: player1.joystick_id_idx = int(player1.control_scheme.split('_')[-1])
            except: player1.joystick_id_idx = None # Should be int or None
        all_renderable_objects.append(player1)
        # if player1_props_for_init: player1.apply_properties(player1_props_for_init) # If you have such a method

    if for_game_mode == "couch_play":
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2)
        if not player2._valid_init: critical("P2 (couch) init failed!"); return None
        player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
        if "joystick" in player2.control_scheme:
            try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
            except: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)
    elif for_game_mode in ["join_lan", "join_ip", "host"]: # Shell P2 for network modes
        player2 = Player(player2_spawn_pos_tuple[0], player2_spawn_pos_tuple[1], player_id=2)
        if not player2._valid_init: critical("P2 (shell) init failed!"); return None
        if for_game_mode != "host": # Client controls P2
            player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
            if "joystick" in player2.control_scheme:
                try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
                except: player2.joystick_id_idx = None
        all_renderable_objects.append(player2)
    
    # Simplified projectile reference for now
    game_elements_ref_for_proj = {"projectiles_list": projectiles_list, "all_renderable_objects": all_renderable_objects, "platforms_list": platforms_list}
    if player1: player1.game_elements_ref_for_projectiles = game_elements_ref_for_proj
    if player2: player2.game_elements_ref_for_projectiles = game_elements_ref_for_proj


    if (for_game_mode == "host" or for_game_mode == "couch_play") and local_enemy_spawns_data_list:
        debug(f"GameSetup: Spawning {len(local_enemy_spawns_data_list)} enemies from level data...")
        for i, spawn_info in enumerate(local_enemy_spawns_data_list):
            try:
                patrol_rect_data = spawn_info.get('patrol') # This is pygame.Rect from map file
                patrol_qrectf: Optional[QRectF] = None
                if patrol_rect_data: # Convert pygame.Rect data to QRectF
                    patrol_qrectf = QRectF(float(patrol_rect_data.x), float(patrol_rect_data.y),
                                           float(patrol_rect_data.width), float(patrol_rect_data.height))
                
                enemy_color_id = spawn_info.get('enemy_color_id')
                enemy_instance = Enemy(start_x=float(spawn_info['pos'][0]), start_y=float(spawn_info['pos'][1]),
                                       patrol_area=patrol_qrectf, enemy_id=i, color_name=enemy_color_id)
                if enemy_instance._valid_init:
                    all_renderable_objects.append(enemy_instance); enemy_list.append(enemy_instance)
                else: warning(f"Enemy {i} (Color: {enemy_color_id}) at {spawn_info['pos']} failed init.")
            except Exception as e: error(f"Error spawning enemy {i}: {e}"); traceback.print_exc()

    if (for_game_mode == "host" or for_game_mode == "couch_play") and statue_spawns_data_list_from_map:
        for i, statue_data in enumerate(statue_spawns_data_list_from_map):
            try:
                s_id = statue_data.get('id', f"map_statue_{i}")
                s_pos_x, s_pos_y = float(statue_data['pos'][0]), float(statue_data['pos'][1])
                new_statue = Statue(s_pos_x, s_pos_y, statue_id=s_id) # Custom paths not handled here yet
                if new_statue._valid_init:
                    all_renderable_objects.append(new_statue); statue_objects_list.append(new_statue)
                else: warning(f"Statue {s_id} at {statue_data['pos']} failed init.")
            except Exception as e: error(f"Error spawning statue {i}: {e}"); traceback.print_exc()

    current_chest_obj: Optional[Chest] = None
    if Chest and (for_game_mode == "host" or for_game_mode == "couch_play"):
        if collectible_spawns_data_list_from_map:
            for item_data in collectible_spawns_data_list_from_map:
                if item_data.get('type') == 'chest':
                    try:
                        chest_x, chest_y = float(item_data['pos'][0]), float(item_data['pos'][1])
                        current_chest_obj = Chest(chest_x, chest_y)
                        if current_chest_obj._valid_init:
                            all_renderable_objects.append(current_chest_obj); collectible_list.append(current_chest_obj)
                            break
                        else: warning(f"Chest from map at {item_data['pos']} failed init.")
                    except Exception as e: error(f"Error spawning map chest: {e}")
        if not current_chest_obj:
            current_chest_obj = spawn_chest_qt(platforms_list, ground_level_y_ref) # Use Qt-based spawn
            if current_chest_obj:
                all_renderable_objects.append(current_chest_obj); collectible_list.append(current_chest_obj)
            else: debug("GameSetup: Random chest spawn failed.")

    camera_instance = Camera(level_pixel_width, lvl_min_y_abs, lvl_max_y_abs, float(current_width), float(current_height))

    game_elements_dict = {
        "player1": player1, "player2": player2, "camera": camera_instance,
        "current_chest": current_chest_obj, "enemy_list": enemy_list,
        "platforms_list": platforms_list, "ladders_list": ladders_list, # Changed from _sprites
        "hazards_list": hazards_list, # Changed from _sprites
        "collectible_list": collectible_list, # Changed from _sprites
        "projectiles_list": projectiles_list, # Changed from _sprites
        "all_renderable_objects": all_renderable_objects, # Replaces all_sprites
        "statue_objects": statue_objects_list,
        "level_pixel_width": level_pixel_width,
        "level_min_y_absolute": lvl_min_y_abs,
        "level_max_y_absolute": lvl_max_y_abs,
        "ground_level_y_ref": ground_level_y_ref, # Renamed for clarity
        "ground_platform_height_ref": ground_platform_height_ref, # Renamed
        "player1_spawn_pos": player1_spawn_pos_tuple, # Renamed
        "player1_spawn_props": player1_props_for_init,
        "player2_spawn_pos": player2_spawn_pos_tuple, # Renamed
        "enemy_spawns_data_cache": local_enemy_spawns_data_list,
        "level_background_color": level_background_color,
        "loaded_map_name": loaded_map_name_return
    }
    debug(f"GameSetup: Elements initialized. Renderables: {len(all_renderable_objects)}")
    return game_elements_dict


def spawn_chest_qt(platforms_list_qt: List[Platform], main_ground_y_surface: float) -> Optional[Chest]:
    """
    Spawns a Chest on a suitable 'ledge' platform, using Qt-based Platform objects.
    """
    if not Chest: warning("GameSetup (spawn_chest_qt): Chest class not available."); return None
    try:
        ledge_platforms_qt = [p for p in platforms_list_qt if p.platform_type == "ledge" and p.rect.width() > C.TILE_SIZE * 1.25]
        if not ledge_platforms_qt: debug("GameSetup (spawn_chest_qt): No suitable ledges."); return None
        
        chosen_platform = random.choice(ledge_platforms_qt)
        inset = C.TILE_SIZE * 0.5
        min_cx = chosen_platform.rect.left() + inset
        max_cx = chosen_platform.rect.right() - inset
        cx = random.uniform(min_cx, max_cx) if min_cx < max_cx else chosen_platform.rect.center().x()
        cy_midbottom = chosen_platform.rect.top() # Chest midbottom will be on top of platform

        new_chest = Chest(cx, cy_midbottom) # Chest init takes midbottom
        if new_chest._valid_init:
            debug(f"GameSetup (spawn_chest_qt): Random chest spawned at ({new_chest.rect.left()},{new_chest.rect.top()})")
            return new_chest
        else: warning(f"GameSetup (spawn_chest_qt): New chest at ({cx},{cy_midbottom}) failed init.")
    except Exception as e: error(f"GameSetup Error in spawn_chest_qt: {e}"); traceback.print_exc()
    return None

# Remove old Pygame-based spawn_chest if it's no longer needed or rename it.
# For clarity, I've created spawn_chest_qt.

#################### END OF FILE: game_setup.py ####################