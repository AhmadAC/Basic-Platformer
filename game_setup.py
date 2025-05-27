# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization and FULL RE-INITIALIZATION (reset) of game elements,
levels, and entities. Employs aggressive cache busting for map reloading.
Map paths now use map_name_folder/map_name_file.py structure.
MODIFIED: Adds map-defined Statues to platforms_list (only if not smashed).
MODIFIED: Processes custom_images_list from map data for rendering.
MODIFIED: Sorts all_renderable_objects by layer_order.
MODIFIED: Enhanced logging for custom image processing and path handling.
"""
# version 2.0.11 (Enhanced logging for custom image processing and path handling)
import sys
import os
import importlib # For importlib.invalidate_caches()
import gc # Garbage Collector
from typing import Dict, Optional, Any, Tuple, List

# PySide6 imports for custom image processing
from PySide6.QtGui import QImage, QPixmap, QTransform, QColor
from PySide6.QtCore import Qt, QRectF

# Game-specific imports
import constants as C
from player import Player
from enemy import Enemy
from items import Chest
from statue import Statue
from camera import Camera
from level_loader import LevelLoader
import config as game_config

from tiles import Platform, Ladder, Lava, BackgroundTile

DEFAULT_LEVEL_MODULE_NAME = "original" # Or your preferred default map name

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

def add_to_renderables_if_new(obj_to_add: Any, renderables_list_ref: List[Any]):
    """Helper to prevent duplicates in all_renderable_objects list."""
    if obj_to_add is not None and obj_to_add not in renderables_list_ref:
        renderables_list_ref.append(obj_to_add)

def get_layer_order_key(item: Any) -> int:
    """
    Key function for sorting renderable objects by layer_order.
    Higher values are drawn on top.
    """
    if isinstance(item, dict) and 'layer_order' in item:
        return item['layer_order']
    if isinstance(item, Player):
        return 100
    direct_layer_order = getattr(item, 'layer_order', None)
    if direct_layer_order is not None:
        return int(direct_layer_order)
    properties_dict = getattr(item, 'properties', None)
    if isinstance(properties_dict, dict):
        return int(properties_dict.get('layer_order', 0))
    if hasattr(item, 'projectile_id'): return 90
    if isinstance(item, Enemy): return 10
    if isinstance(item, Statue): return 9
    if isinstance(item, Chest): return 8
    if isinstance(item, Platform): return -5
    if isinstance(item, Ladder): return -6
    if isinstance(item, Lava): return -7
    if isinstance(item, BackgroundTile): return -10
    return 0


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

    # --- Determine absolute path to the base "maps" directory ---
    maps_base_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs):
        # If C.PROJECT_ROOT is not set or empty, derive from this file's location (assuming specific project structure)
        project_root_from_constants = getattr(C, 'PROJECT_ROOT', None)
        if not project_root_from_constants: # Fallback if C.PROJECT_ROOT is empty or not set
            project_root_from_constants = os.path.dirname(os.path.abspath(__file__)) # Assumes game_setup.py is in project root
            # If game_setup.py is in a subfolder (e.g., 'game_logic'), adjust this:
            # project_root_from_constants = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            warning(f"GameSetup: C.PROJECT_ROOT not found or empty. Guessed project root for maps: {project_root_from_constants}")

        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)
    maps_base_dir_abs = os.path.normpath(maps_base_dir_abs) # Normalize path
    debug(f"GameSetup: Resolved absolute base maps directory to: {maps_base_dir_abs}")
    # --- End Base Maps Directory Determination ---

    debug("GameSetup: Clearing all existing game elements from game_elements_ref...")
    for i in range(1, 5):
        player_key = f"player{i}"
        if player_key in game_elements_ref:
            if isinstance(game_elements_ref[player_key], Player) and hasattr(game_elements_ref[player_key], 'reset_for_new_game_or_round'):
                game_elements_ref[player_key].reset_for_new_game_or_round()
            game_elements_ref[player_key] = None
    game_elements_ref["camera"] = None
    game_elements_ref["current_chest"] = None
    game_elements_ref["level_data"] = None
    list_keys_to_reinitialize = [
        "enemy_list", "statue_objects", "collectible_list", "projectiles_list",
        "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
        "all_renderable_objects", "enemy_spawns_data_cache", "statue_spawns_data_cache",
        "processed_custom_images_for_render"
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

    debug(f"GameSetup: Attempting to load map '{current_map_to_load}' using base maps directory '{maps_base_dir_abs}'.")
    level_data = loader.load_map(str(current_map_to_load), maps_base_dir_abs)

    if not level_data or not isinstance(level_data, dict):
        critical(f"GameSetup FATAL: Failed to load/reload map data for '{current_map_to_load}' from base '{maps_base_dir_abs}'. Initialization aborted.")
        game_elements_ref["loaded_map_name"] = None
        game_elements_ref['initialization_in_progress'] = False
        return False

    game_elements_ref["level_data"] = level_data
    game_elements_ref["loaded_map_name"] = current_map_to_load
    game_elements_ref["map_name"] = current_map_to_load # Ensure map_name is also set for consistency
    info(f"GameSetup: Successfully reloaded pristine map data for '{current_map_to_load}'.")

    # Extract level properties from loaded data
    game_elements_ref["level_background_color"] = tuple(level_data.get('background_color', getattr(C, 'LIGHT_BLUE', (173, 216, 230))))
    game_elements_ref["level_pixel_width"] = float(level_data.get('level_pixel_width', float(current_width) * 2.0))
    game_elements_ref["level_min_x_absolute"] = float(level_data.get('level_min_x_absolute', 0.0))
    game_elements_ref["level_min_y_absolute"] = float(level_data.get('level_min_y_absolute', 0.0))
    game_elements_ref["level_max_y_absolute"] = float(level_data.get('level_max_y_absolute', float(current_height)))
    game_elements_ref["ground_level_y_ref"] = float(level_data.get('ground_level_y_ref', game_elements_ref["level_max_y_absolute"] - float(getattr(C, 'TILE_SIZE', 40.0))))
    game_elements_ref["ground_platform_height_ref"] = float(level_data.get('ground_platform_height_ref', float(getattr(C, 'TILE_SIZE', 40.0))))

    # Cache spawn data (used if server/authoritative mode)
    game_elements_ref["enemy_spawns_data_cache"] = list(level_data.get('enemies_list', []))
    game_elements_ref["statue_spawns_data_cache"] = list(level_data.get('statues_list', []))

    # Create NEW Static Tile Instances (Platforms, Ladders, Hazards, BackgroundTiles)
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

    for l_data in level_data.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["ladders_list"].append(Ladder(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]) ))
        except Exception as e_lad: error(f"GameSetup: Error creating ladder: {e_lad}", exc_info=True)

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

    for bg_data in level_data.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["background_tiles_list"].append(BackgroundTile(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(bg_data.get('color', getattr(C, 'DARK_GRAY', (50,50,50)))),
                    tile_type=str(bg_data.get('type', 'generic_background')),
                    image_path=bg_data.get('image_path'),
                    properties=bg_data.get('properties', {}) ))
        except Exception as e_bg: error(f"GameSetup: Error creating background tile: {e_bg}", exc_info=True)
    info(f"GameSetup: Static tile-based elements re-created. Platforms: {len(game_elements_ref['platforms_list'])}")

    # --- Custom Image Processing (with Enhanced Logging) ---
    game_elements_ref["processed_custom_images_for_render"] = []
    custom_images_data_from_map = level_data.get("custom_images_list")
    if custom_images_data_from_map is None:
        info("GameSetup: 'custom_images_list' key NOT FOUND in level_data. No custom images will be loaded.")
    elif not custom_images_data_from_map: # It was found, but it's an empty list
        info("GameSetup: 'custom_images_list' key FOUND in level_data, but the list is EMPTY.")
    else:
        info(f"GameSetup: Found 'custom_images_list' with {len(custom_images_data_from_map)} entries. Processing them...")
        # `current_map_to_load` is the folder/stem name (e.g., "chest")
        current_map_folder_path = os.path.join(maps_base_dir_abs, str(current_map_to_load))
        debug(f"GameSetup: Custom image base folder path: {current_map_folder_path}")

        for img_idx, img_data_raw in enumerate(custom_images_data_from_map):
            try:
                rect_tuple = img_data_raw.get('rect')
                rel_path = img_data_raw.get('source_file_path') # This path is relative to current_map_folder_path
                layer_order = img_data_raw.get('layer_order', 0)
                is_flipped_h = img_data_raw.get('is_flipped_h', False)
                rotation_angle = float(img_data_raw.get('rotation', 0))

                if not rect_tuple or not rel_path:
                    warning(f"GameSetup: Custom image data entry {img_idx} missing rect or source_file_path: {img_data_raw}")
                    continue

                full_image_path = os.path.join(current_map_folder_path, rel_path)
                debug(f"GameSetup: Checking custom image {img_idx}. Relative path from map: '{rel_path}'. Full constructed path for loading: '{full_image_path}'")

                if not os.path.exists(full_image_path):
                    error(f"GameSetup: Custom image file NOT FOUND: {full_image_path}") # More prominent error
                    continue

                q_image_original = QImage(full_image_path)
                if q_image_original.isNull():
                    error(f"GameSetup: Failed to load custom image (QImage isNull): {full_image_path}")
                    continue

                target_w = float(rect_tuple[2]); target_h = float(rect_tuple[3])
                if target_w <= 0 or target_h <= 0:
                    warning(f"GameSetup: Invalid target dimensions ({target_w}x{target_h}) for custom image {rel_path}. Using original size.")
                    target_w = float(q_image_original.width()); target_h = float(q_image_original.height())

                processed_image = q_image_original.scaled(int(target_w), int(target_h),
                                                          Qt.AspectRatioMode.IgnoreAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation)
                if is_flipped_h: processed_image = processed_image.mirrored(True, False)
                if rotation_angle != 0:
                    transform = QTransform()
                    img_center_x = processed_image.width() / 2.0; img_center_y = processed_image.height() / 2.0
                    transform.translate(img_center_x, img_center_y); transform.rotate(rotation_angle); transform.translate(-img_center_x, -img_center_y)
                    processed_image = processed_image.transformed(transform, Qt.TransformationMode.SmoothTransformation)

                final_pixmap = QPixmap.fromImage(processed_image)
                if final_pixmap.isNull():
                    error(f"GameSetup: Failed to create QPixmap from processed image for {full_image_path}")
                    continue

                renderable_custom_image = {
                    'rect': QRectF(float(rect_tuple[0]), float(rect_tuple[1]), target_w, target_h),
                    'image': final_pixmap, 'layer_order': layer_order, 'source_file_path_debug': rel_path
                }
                game_elements_ref["processed_custom_images_for_render"].append(renderable_custom_image)
                debug(f"GameSetup: Processed custom image '{rel_path}' for rendering. Layer: {layer_order}")
            except Exception as e_custom_img:
                error(f"GameSetup: Error processing custom image data entry {img_idx} ({img_data_raw}): {e_custom_img}", exc_info=True)
    info(f"GameSetup: Custom images processed: {len(game_elements_ref['processed_custom_images_for_render'])}")
    # --- End Custom Image Processing ---

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
        player_instance.set_projectile_group_references(
            game_elements_ref["projectiles_list"],
            game_elements_ref["all_renderable_objects"],
            game_elements_ref["platforms_list"]
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
                else: warning(f"GameSetup: Failed to initialize enemy {i_enemy} (type: {enemy_color_name}) during reset.")
            except Exception as e_enemy_create: error(f"GameSetup: Error creating enemy {i_enemy} during reset: {e_enemy_create}", exc_info=True)
        info(f"GameSetup: Enemies re-created: {len(game_elements_ref['enemy_list'])}")

        for i_statue, statue_data in enumerate(game_elements_ref["statue_spawns_data_cache"]):
            try:
                s_id = statue_data.get('id', f"map_statue_rs_{i_statue}")
                s_pos_tuple = tuple(map(float, statue_data.get('pos', (200.0, 200.0))))
                s_props = statue_data.get('properties', {})

                new_statue = Statue(center_x=s_pos_tuple[0], center_y=s_pos_tuple[1],
                                    statue_id=s_id, properties=s_props)
                if new_statue._valid_init:
                    game_elements_ref["statue_objects"].append(new_statue)
                    if not new_statue.is_smashed:
                        game_elements_ref["platforms_list"].append(new_statue)
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
                        info(f"GameSetup (Reset): Chest RE-CREATED at {chest_pos_fresh} from fresh map data.")
                    else: warning("GameSetup (Reset): NEW Chest instance from map data failed to initialize.")
                    break
                except Exception as e_chest_create: error(f"GameSetup: Error creating NEW Chest instance during reset: {e_chest_create}", exc_info=True)
        game_elements_ref["current_chest"] = new_chest_instance
    else:
        debug(f"GameSetup: Dynamic entities not re-spawned by client for mode '{for_game_mode}'. Server state will dictate.")
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

    new_all_renderables_setup_temp: List[Any] = []
    for static_key in ["background_tiles_list", "ladders_list", "hazards_list", "platforms_list"]:
        for item in game_elements_ref.get(static_key, []):
            add_to_renderables_if_new(item, new_all_renderables_setup_temp)
    for custom_img_dict in game_elements_ref.get("processed_custom_images_for_render", []):
        add_to_renderables_if_new(custom_img_dict, new_all_renderables_setup_temp)
    for dynamic_key in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
        for item_dyn in game_elements_ref.get(dynamic_key, []):
            add_to_renderables_if_new(item_dyn, new_all_renderables_setup_temp)
    for i_p_render in range(1, 5):
        p_to_render = game_elements_ref.get(f"player{i_p_render}")
        if p_to_render:
            add_to_renderables_if_new(p_to_render, new_all_renderables_setup_temp)

    new_all_renderables_setup_temp.sort(key=get_layer_order_key)
    game_elements_ref["all_renderable_objects"] = new_all_renderables_setup_temp
    debug(f"GameSetup: Assembled and sorted all_renderable_objects. Count: {len(game_elements_ref['all_renderable_objects'])}")

    game_elements_ref["game_ready_for_logic"] = True
    game_elements_ref["initialization_in_progress"] = False

    info(f"GameSetup: --- Full Map (Re)Load & Entity Re-Initialization COMPLETE for map '{current_map_to_load}' ---")
    return True