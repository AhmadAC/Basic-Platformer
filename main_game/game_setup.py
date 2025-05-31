# main_game/game_setup.py
# -*- coding: utf-8 -*-
"""
Handles the initialization of all game elements for a given map and game mode.
This includes loading map data, creating players, enemies, tiles, items, statues,
custom images, trigger squares, and setting up the camera.
Map paths are expected in the format: maps_base_dir/map_name_folder/map_name_file.py
MODIFIED: Corrected imports for sibling packages (player, enemy).
MODIFIED: Player spawn assignment now more robustly handles missing P3/P4 spawns
          for 2-player modes, ensuring P1 and P2 are prioritized.
MODIFIED: Enemy creation now uses properties directly from spawn_data.
MODIFIED: Chest creation ensures properties are passed if defined in map data.
MODIFIED: Statue creation also uses properties from spawn_data.
MODIFIED: Camera focus logic prioritizes P1, then P2, then any active player for initial view.
MODIFIED: Trigger squares and custom images are processed even if their lists are empty in map_data.
MODIFIED: Added enemy_spawns_data_cache and statue_spawns_data_cache for client-side entity recreation.
MODIFIED: Ensured player.animations is checked to be a dictionary before using it.
MODIFIED: Removed assignment to a single 'current_chest', now relies on 'collectible_list' for all chests.
MODIFIED: Corrected _process_trigger_squares to handle QRectF directly for 'rect' property.
"""
# version 2.2.12 (Handle QRectF in _process_trigger_squares)

import os
import sys
import random
from typing import Dict, Optional, Any, List, Tuple, cast

from PySide6.QtCore import QRectF, QPointF, QSize, Qt
from PySide6.QtGui import QPixmap, QImage, QTransform # Added QTransform

_GAME_SETUP_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_GAME_SETUP = os.path.dirname(_GAME_SETUP_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_GAME_SETUP not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_GAME_SETUP)

try:
    from main_game.logger import info, debug, warning, error, critical
    import main_game.constants as C
    import main_game.config as game_config
    from main_game.level_loader import LevelLoader
    from main_game.tiles import Platform, Ladder, Lava, BackgroundTile
    from main_game.items import Chest
    from main_game.camera import Camera
    from main_game.assets import resource_path

    from player.player import Player
    from enemy.enemy import Enemy
    from enemy.enemy_knight import EnemyKnight
    from player.statue import Statue

except ImportError as e_gs_imp:
    import logging
    _gs_fallback_logger = logging.getLogger(__name__ + "_gs_fallback")
    if not _gs_fallback_logger.hasHandlers():
        _gs_fallback_handler = logging.StreamHandler(sys.stdout)
        _gs_fallback_formatter = logging.Formatter('GAME_SETUP (ImportErrorFallback): %(levelname)s - %(message)s')
        _gs_fallback_handler.setFormatter(_gs_fallback_formatter)
        _gs_fallback_logger.addHandler(_gs_fallback_handler)
        _gs_fallback_logger.setLevel(logging.DEBUG)
    _gs_fallback_logger.critical(f"CRITICAL GameSetup Import Error: {e_gs_imp}. Game setup will fail.", exc_info=True)
    raise

def get_layer_order_key(item: Any) -> int:
    if isinstance(item, dict):
        return int(item.get('layer_order', 0))
    elif hasattr(item, 'layer_order'):
        return int(getattr(item, 'layer_order', 0))
    elif isinstance(item, BackgroundTile): return -10
    elif isinstance(item, Platform): return 0
    elif isinstance(item, Ladder): return 1
    elif isinstance(item, Lava): return 2
    elif isinstance(item, Chest): return 5
    elif isinstance(item, Statue): return 8
    elif isinstance(item, Enemy): return 10
    elif isinstance(item, Player): return 20
    elif hasattr(item, 'owner_player'): return 30 # Projectiles higher
    return 0

def _create_player_instance(player_id: int, spawn_pos_tuple: Optional[Tuple[float,float]],
                            default_spawn_pos: Tuple[float,float],
                            initial_props: Optional[Dict[str, Any]] = None) -> Player:
    pos_to_use = spawn_pos_tuple if spawn_pos_tuple else default_spawn_pos
    player_instance = Player(pos_to_use[0], pos_to_use[1], player_id, initial_properties=initial_props)
    device_id_str = getattr(game_config, f"CURRENT_P{player_id}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
    player_instance.control_scheme = device_id_str
    if device_id_str.startswith("joystick_pygame_"):
        try:
            idx_part = device_id_str.split('_')[-1]
            if idx_part.isdigit():
                player_instance.joystick_id_idx = int(idx_part)
        except (ValueError, IndexError):
            warning(f"GameSetup: Could not parse joystick index from '{device_id_str}' for P{player_id}.")
            player_instance.joystick_id_idx = None
    debug(f"GameSetup: Created Player {player_id}. Spawn: {pos_to_use}, Device: '{device_id_str}', JoystickIdx: {player_instance.joystick_id_idx}, Props: {initial_props is not None}")
    return player_instance

def _create_enemy_instance(spawn_data: Dict[str, Any], enemy_idx: int) -> Optional[Enemy]:
    start_pos = spawn_data.get('start_pos')
    enemy_type_str = spawn_data.get('type')
    patrol_rect_data = spawn_data.get('patrol_rect_data')
    properties = spawn_data.get('properties', {}) # Use properties from spawn_data
    if not start_pos or not enemy_type_str:
        error(f"GameSetup: Invalid enemy spawn data (missing start_pos or type): {spawn_data}")
        return None
    patrol_area_qrectf: Optional[QRectF] = None
    if isinstance(patrol_rect_data, dict):
        patrol_area_qrectf = QRectF(
            float(patrol_rect_data.get('x', 0)), float(patrol_rect_data.get('y', 0)),
            float(patrol_rect_data.get('width', 100)), float(patrol_rect_data.get('height', 50))
        )
    unique_enemy_id = spawn_data.get('id', f"enemy_{enemy_type_str}_{enemy_idx}")
    if enemy_type_str == "enemy_knight":
        return EnemyKnight(float(start_pos[0]), float(start_pos[1]), patrol_area_qrectf, unique_enemy_id, properties=properties)
    else:
        color_name_for_generic = enemy_type_str.replace("enemy_", "", 1) if enemy_type_str.startswith("enemy_") else enemy_type_str
        return Enemy(float(start_pos[0]), float(start_pos[1]), patrol_area_qrectf, unique_enemy_id, color_name=color_name_for_generic, properties=properties)

def _create_platform_data_list_from_map(map_platforms: List[Dict[str, Any]]) -> List[Platform]:
    platforms_list: List[Platform] = []
    for p_data in map_platforms:
        rect_coords = p_data.get('rect')
        color_tuple = tuple(p_data.get('color', C.GRAY)) # type: ignore
        p_type = p_data.get('type', "generic_platform")
        props = p_data.get('properties')
        if rect_coords and len(rect_coords) == 4:
            platforms_list.append(Platform(rect_coords[0], rect_coords[1], rect_coords[2], rect_coords[3], color_tuple, p_type, props)) # type: ignore
    return platforms_list

def _create_ladder_data_list_from_map(map_ladders: List[Dict[str, Any]]) -> List[Ladder]:
    ladders_list: List[Ladder] = []
    for l_data in map_ladders:
        rect_coords = l_data.get('rect')
        if rect_coords and len(rect_coords) == 4:
            ladders_list.append(Ladder(rect_coords[0], rect_coords[1], rect_coords[2], rect_coords[3]))
    return ladders_list

def _create_hazard_data_list_from_map(map_hazards: List[Dict[str, Any]]) -> List[Lava]:
    hazards_list: List[Lava] = []
    for h_data in map_hazards:
        rect_coords = h_data.get('rect')
        h_type = h_data.get('type', 'unknown_hazard')
        color_tuple = tuple(h_data.get('color', C.ORANGE_RED)) # type: ignore
        props = h_data.get('properties')
        if h_type == "hazard_lava" and rect_coords and len(rect_coords) == 4:
            hazards_list.append(Lava(rect_coords[0], rect_coords[1], rect_coords[2], rect_coords[3], color_tuple, props)) # type: ignore
    return hazards_list

def _create_background_tile_list_from_map(map_bg_tiles: List[Dict[str, Any]]) -> List[BackgroundTile]:
    background_tiles_list: List[BackgroundTile] = []
    for bg_data in map_bg_tiles:
        rect_coords = bg_data.get('rect')
        color_tuple = tuple(bg_data.get('color', C.DARK_GRAY)) # type: ignore
        bg_type = bg_data.get('type', "generic_background_tile")
        image_path_rel_to_project = bg_data.get('image_path') # Path from ED_CONFIG.EDITOR_PALETTE_ASSETS (e.g., "assets/...")
        props = bg_data.get('properties')
        if rect_coords and len(rect_coords) == 4:
            background_tiles_list.append(BackgroundTile(
                rect_coords[0], rect_coords[1], rect_coords[2], rect_coords[3],
                color_tuple, bg_type, image_path_rel_to_project, props # type: ignore
            ))
    return background_tiles_list

def _create_item_list_from_map(map_items: List[Dict[str, Any]]) -> List[Chest]:
    items_list: List[Chest] = [] # Changed type hint to List[Chest] for clarity
    for item_data in map_items:
        pos_tuple = item_data.get('pos')
        item_type = item_data.get('type')
        props = item_data.get('properties') # Get properties for chest
        if item_type == "chest" and pos_tuple and len(pos_tuple) == 2:
            new_chest = Chest(pos_tuple[0], pos_tuple[1])
            if props: new_chest.properties = props # Assign properties if they exist
            items_list.append(new_chest)
    return items_list

def _create_statue_list_from_map(map_statues: List[Dict[str, Any]]) -> List[Statue]:
    statue_list: List[Statue] = []
    for statue_data in map_statues:
        pos_tuple = statue_data.get('pos')
        statue_id = statue_data.get('id')
        props = statue_data.get('properties', {}) # Use properties from spawn_data
        if pos_tuple and len(pos_tuple) == 2 and statue_id:
            statue_list.append(Statue(pos_tuple[0], pos_tuple[1], statue_id, properties=props))
    return statue_list

def _process_custom_images(map_custom_images: List[Dict[str, Any]], base_map_folder_for_custom_assets: str) -> List[Dict[str, Any]]:
    processed_images: List[Dict[str, Any]] = []
    if not base_map_folder_for_custom_assets:
        warning("GameSetup: Base map folder path for custom assets is not provided. Cannot load custom images.")
        return processed_images
    for img_data in map_custom_images:
        rel_path_from_map_folder = img_data.get("source_file_path")
        if not rel_path_from_map_folder: continue
        full_abs_path = os.path.normpath(os.path.join(base_map_folder_for_custom_assets, rel_path_from_map_folder))
        qimage = QImage(full_abs_path)
        if qimage.isNull():
            warning(f"GameSetup: Failed to load custom image from '{full_abs_path}' (original relative: '{rel_path_from_map_folder}'). Skipping.")
            continue
        pixmap = QPixmap.fromImage(qimage)
        if pixmap.isNull():
            warning(f"GameSetup: Failed to convert QImage to QPixmap for '{full_abs_path}'. Skipping.")
            continue
        is_flipped_h = img_data.get("is_flipped_h", False)
        rotation_deg = img_data.get("rotation", 0)
        if is_flipped_h:
            pixmap = pixmap.transformed(QTransform().scale(-1, 1))
        if rotation_deg != 0:
            img_center = QPointF(pixmap.width() / 2.0, pixmap.height() / 2.0)
            transform = QTransform().translate(img_center.x(), img_center.y()).rotate(float(rotation_deg)).translate(-img_center.x(), -img_center.y())
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        opacity_percent = img_data.get("properties", {}).get("opacity", 100)
        opacity_float = max(0.0, min(1.0, float(opacity_percent) / 100.0))
        processed_images.append({
            'rect': QRectF(float(img_data.get("rect")[0]), float(img_data.get("rect")[1]), # type: ignore
                           float(img_data.get("rect")[2]), float(img_data.get("rect")[3])), # type: ignore
            'image': pixmap,
            'layer_order': int(img_data.get("layer_order", 0)),
            'scroll_factor_x': float(img_data.get("properties", {}).get("scroll_factor_x", 1.0)),
            'scroll_factor_y': float(img_data.get("properties", {}).get("scroll_factor_y", 1.0)),
            'is_obstacle': bool(img_data.get("properties", {}).get("is_obstacle", False)),
            'opacity_float': opacity_float
        })
    return processed_images

def _process_trigger_squares(map_trigger_squares: List[Dict[str, Any]], base_map_folder_for_custom_assets: str) -> List[Dict[str, Any]]:
    processed_triggers: List[Dict[str, Any]] = []
    for trig_data in map_trigger_squares:
        rect_data_from_map = trig_data.get("rect")
        current_rect: Optional[QRectF] = None

        if isinstance(rect_data_from_map, QRectF):
            current_rect = rect_data_from_map # Already a QRectF from editor JSON
        elif isinstance(rect_data_from_map, (list, tuple)) and len(rect_data_from_map) == 4:
            try: # Attempt to parse from tuple (older format or direct definition)
                current_rect = QRectF(float(rect_data_from_map[0]), float(rect_data_from_map[1]),
                                      float(rect_data_from_map[2]), float(rect_data_from_map[3]))
            except (TypeError, ValueError) as e_rect_parse:
                error(f"GameSetup: Error parsing trigger rect tuple {rect_data_from_map}: {e_rect_parse}")
                continue
        else: # Invalid rect data format
            warning(f"GameSetup: Trigger square has invalid rect data: {rect_data_from_map}. Skipping.")
            continue

        if current_rect is None or current_rect.isNull() or not current_rect.isValid():
            warning(f"GameSetup: Trigger square rect is null or invalid after processing: {trig_data}. Skipping.")
            continue
            
        processed_trig = trig_data.copy()
        processed_trig['rect'] = current_rect # Store the QRectF object

        image_path_in_props = trig_data.get("properties", {}).get("image_in_square", "")
        if image_path_in_props and base_map_folder_for_custom_assets:
            full_abs_path_trigger_img = os.path.normpath(os.path.join(base_map_folder_for_custom_assets, image_path_in_props))
            qimage_trig = QImage(full_abs_path_trigger_img)
            if not qimage_trig.isNull():
                pixmap_trig = QPixmap.fromImage(qimage_trig)
                if not pixmap_trig.isNull():
                    processed_trig['image_pixmap'] = pixmap_trig
            else:
                warning(f"GameSetup: Failed to load image '{image_path_in_props}' for trigger square. Path: {full_abs_path_trigger_img}")
        processed_triggers.append(processed_trig)
    return processed_triggers


def initialize_game_elements(current_width: int, current_height: int,
                             game_elements_ref: Dict[str, Any],
                             for_game_mode: str,
                             map_module_name: str) -> bool:
    info(f"GameSetup: Initializing game elements for map '{map_module_name}', mode '{for_game_mode}'. Screen: {current_width}x{current_height}")
    game_elements_ref.clear()
    game_elements_ref['game_ready_for_logic'] = False
    game_elements_ref['initialization_in_progress'] = True
    game_elements_ref['num_active_players_for_mode'] = game_elements_ref.get('num_active_players_for_mode', 1 if for_game_mode != "couch_play" else 2)
    game_elements_ref['current_game_mode'] = for_game_mode

    level_loader = LevelLoader()
    maps_base_dir_abs_for_loader = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs_for_loader):
        project_root_from_constants_loader = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_base_dir_abs_for_loader = os.path.join(project_root_from_constants_loader, maps_base_dir_abs_for_loader)

    map_data = level_loader.load_map(map_module_name, maps_base_dir_abs_for_loader)
    if map_data is None:
        error(f"GameSetup FATAL: Failed to load map data for '{map_module_name}' from loader. Cannot proceed.")
        game_elements_ref['initialization_in_progress'] = False
        return False

    game_elements_ref['loaded_map_name'] = map_module_name # Store the stem name for reloads
    game_elements_ref['map_name'] = map_data.get("level_name", map_module_name) # The display/logical name
    game_elements_ref['level_background_color'] = map_data.get("background_color", C.LIGHT_BLUE)
    game_elements_ref['level_pixel_width'] = float(map_data.get("level_pixel_width", current_width * 2.0))
    game_elements_ref['level_min_x_absolute'] = float(map_data.get("level_min_x_absolute", 0.0))
    game_elements_ref['level_min_y_absolute'] = float(map_data.get("level_min_y_absolute", 0.0))
    game_elements_ref['level_max_y_absolute'] = float(map_data.get("level_max_y_absolute", current_height))
    game_elements_ref['ground_level_y_ref'] = float(map_data.get("ground_level_y_ref", current_height - C.TILE_SIZE))
    game_elements_ref['ground_platform_height_ref'] = float(map_data.get("ground_platform_height_ref", C.TILE_SIZE))
    # Store absolute path to the specific map's folder (e.g., .../maps/map_name_folder/)
    game_elements_ref['map_folder_path'] = os.path.join(maps_base_dir_abs_for_loader, map_module_name)

    game_elements_ref["platforms_list"] = _create_platform_data_list_from_map(map_data.get("platforms_list", []))
    game_elements_ref["ladders_list"] = _create_ladder_data_list_from_map(map_data.get("ladders_list", []))
    game_elements_ref["hazards_list"] = _create_hazard_data_list_from_map(map_data.get("hazards_list", []))
    game_elements_ref["background_tiles_list"] = _create_background_tile_list_from_map(map_data.get("background_tiles_list", []))
    game_elements_ref["trigger_squares_list"] = _process_trigger_squares(map_data.get("trigger_squares_list", []), game_elements_ref['map_folder_path'])
    game_elements_ref["processed_custom_images_for_render"] = _process_custom_images(map_data.get("custom_images_list", []), game_elements_ref['map_folder_path'])

    num_players_expected = game_elements_ref.get('num_active_players_for_mode', 1)
    player_spawn_positions = [map_data.get(f"player_start_pos_p{i+1}") for i in range(4)]
    player_spawn_props_from_map = [map_data.get(f"player{i+1}_spawn_props", {}) for i in range(4)]

    default_p1_spawn = (C.TILE_SIZE * 2.0, game_elements_ref['ground_level_y_ref'] - 1.0)
    player_instances: List[Optional[Player]] = [None, None, None, None]

    player_assignment_order = [0, 1, 2, 3] # 0-indexed for lists
    if num_players_expected == 1: player_assignment_order = [0]
    elif num_players_expected == 2: player_assignment_order = [0, 1]
    elif num_players_expected == 3: player_assignment_order = [0, 1, 2]
    # For 4 players, default order is fine

    players_created_count = 0
    for p_idx_zero_based in player_assignment_order:
        if players_created_count >= num_players_expected: break # Stop if we've created enough players for the mode

        player_id_one_based = p_idx_zero_based + 1
        spawn_pos_for_this_player = player_spawn_positions[p_idx_zero_based]
        fallback_spawn_for_this_player = (default_p1_spawn[0] + p_idx_zero_based * C.TILE_SIZE * 2.5, default_p1_spawn[1])
        
        initial_props_for_player = player_spawn_props_from_map[p_idx_zero_based]
        if not initial_props_for_player: # If no props from map, get from game_config or hardcoded defaults
            config_props_key = f"P{player_id_one_based}_PROPERTIES" # Check game_config for P1_PROPERTIES etc.
            if hasattr(game_config, config_props_key):
                initial_props_for_player = getattr(game_config, config_props_key).copy()
            else: # Absolute fallback if not in map or config
                initial_props_for_player = {
                    "max_health": C.PLAYER_MAX_HEALTH,
                    "move_speed": C.PLAYER_RUN_SPEED_LIMIT * 50, # Convert to units/sec for consistency
                    "jump_strength": C.PLAYER_JUMP_STRENGTH * 60 # Convert to units/sec for consistency
                }

        player_instance = _create_player_instance(player_id_one_based, spawn_pos_for_this_player, fallback_spawn_for_this_player, initial_props_for_player)
        player_instances[p_idx_zero_based] = player_instance
        game_elements_ref[f"player{player_id_one_based}"] = player_instance
        players_created_count += 1
        if player_instance and hasattr(player_instance, 'reset_for_new_game_or_round'):
            player_instance.reset_for_new_game_or_round()


    map_enemies_spawn_data = map_data.get("enemies_list", [])
    game_elements_ref["enemy_list"] = [_create_enemy_instance(e_data, idx) for idx, e_data in enumerate(map_enemies_spawn_data) if _create_enemy_instance(e_data, idx) is not None]
    game_elements_ref["enemy_spawns_data_cache"] = list(map_enemies_spawn_data) # Store raw spawn data

    map_items_data = map_data.get("items_list", [])
    items_list_temp = _create_item_list_from_map(map_items_data)
    game_elements_ref["collectible_list"] = items_list_temp # Store all chests (and potentially other items)
    # Removed: game_elements_ref["current_chest"] assignment

    map_statues_data = map_data.get("statues_list", [])
    game_elements_ref["statue_objects"] = _create_statue_list_from_map(map_statues_data)
    game_elements_ref["statue_spawns_data_cache"] = list(map_statues_data) # Store raw spawn data

    # Camera initialization (ensure dimensions are floats)
    camera = Camera(game_elements_ref['level_pixel_width'],
                    game_elements_ref['level_min_x_absolute'],
                    game_elements_ref['level_min_y_absolute'],
                    game_elements_ref['level_max_y_absolute'],
                    float(current_width), float(current_height))
    game_elements_ref["camera"] = camera

    # Initial camera focus logic
    focus_target_for_camera: Optional[Player] = None
    player_focus_priority = [0, 1, 2, 3] # Prioritize P1 (index 0), then P2, etc.
    for p_idx_focus in player_focus_priority:
        p_instance_focus = player_instances[p_idx_focus]
        # Check if player exists, is valid, alive, and not dead/petrified
        if p_instance_focus and isinstance(p_instance_focus.animations, dict) and p_instance_focus.animations and p_instance_focus.alive():
            focus_target_for_camera = p_instance_focus
            break # Found a valid player to focus on

    if focus_target_for_camera:
        debug(f"GameSetup: Camera initial focus on Player {focus_target_for_camera.player_id}")
        camera.update(focus_target_for_camera)
    else:
        debug("GameSetup: Camera initial static update (no valid player focus target).")
        camera.static_update()

    game_elements_ref['camera_level_dims_set'] = True # Flag that camera knows level bounds
    game_elements_ref['initialization_in_progress'] = False
    game_elements_ref['game_ready_for_logic'] = True
    info(f"GameSetup: Initialization for map '{map_module_name}' completed. Game ready for mode '{for_game_mode}'.")
    return True