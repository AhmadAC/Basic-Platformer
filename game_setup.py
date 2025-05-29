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
MODIFIED: Corrected call to add_to_renderables_if_new for custom images.
MODIFIED: Added check for camera_instance being None.
"""
# version 2.0.15 (Camera None check)
import sys
import os
import importlib # For importlib.invalidate_caches()
import gc # Garbage Collector
from typing import Dict, Optional, Any, Tuple, List

# PySide6 imports for custom image processing
from PySide6.QtGui import QImage, QPixmap, QTransform, QColor, QPainter
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

# DEFERRED IMPORT: from game_state_manager import reset_game_state # Not used in this file

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

def add_to_renderables_if_new(obj_to_add: Any, renderables_list_ref: List[Any]):
    if obj_to_add is not None:
        is_present = False
        for item in renderables_list_ref:
            if item is obj_to_add:
                is_present = True
                break
        if not is_present:
            renderables_list_ref.append(obj_to_add)

def get_layer_order_key(item: Any) -> int:
    layer_order_source = "unknown_source"; layer_val = 0
    if isinstance(item, dict) and 'layer_order' in item: layer_val = int(item['layer_order']); layer_order_source = f"dict_key ({type(item).__name__})"
    elif isinstance(item, Player): layer_val = 100; layer_order_source = "Player_class"
    else:
        direct_layer_order = getattr(item, 'layer_order', None)
        if direct_layer_order is not None: layer_val = int(direct_layer_order); layer_order_source = f"direct_attr ({type(item).__name__})"
        else:
            properties_dict = getattr(item, 'properties', None)
            if isinstance(properties_dict, dict): layer_val = int(properties_dict.get('layer_order', 0)); layer_order_source = f"properties_dict ({type(item).__name__})"
            elif hasattr(item, 'projectile_id'): layer_val = 90; layer_order_source = "projectile_id_attr"
            elif isinstance(item, Enemy): layer_val = 10; layer_order_source = "Enemy_class"
            elif isinstance(item, Statue): layer_val = 9; layer_order_source = "Statue_class"
            elif isinstance(item, Chest): layer_val = 8; layer_order_source = "Chest_class"
            elif isinstance(item, Platform): layer_val = -5; layer_order_source = "Platform_class"
            elif isinstance(item, Ladder): layer_val = -6; layer_order_source = "Ladder_class"
            elif isinstance(item, Lava): layer_val = -7; layer_order_source = "Lava_class"
            elif isinstance(item, BackgroundTile): layer_val = -10; layer_order_source = "BackgroundTile_class"
            else: layer_order_source = f"default_zero ({type(item).__name__})"; layer_val = 0
    return layer_val


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

    maps_base_dir_abs = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_base_dir_abs):
        project_root_from_constants = getattr(C, 'PROJECT_ROOT', None)
        if not project_root_from_constants:
            project_root_from_constants = os.path.dirname(os.path.abspath(__file__))
            warning(f"GameSetup: C.PROJECT_ROOT not found or empty. Guessed project root for maps: {project_root_from_constants}")
        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)
    maps_base_dir_abs = os.path.normpath(maps_base_dir_abs)
    debug(f"GameSetup DEBUG: Resolved absolute base maps directory to: {maps_base_dir_abs}")

    debug("GameSetup DEBUG: Clearing all existing game elements from game_elements_ref...")
    for i in range(1, 5):
        player_key = f"player{i}"
        if player_key in game_elements_ref:
            if isinstance(game_elements_ref[player_key], Player) and hasattr(game_elements_ref[player_key], 'reset_for_new_game_or_round'):
                game_elements_ref[player_key].reset_for_new_game_or_round()
            game_elements_ref[player_key] = None
    game_elements_ref["camera"] = None # Explicitly set to None before re-creation attempt
    game_elements_ref["current_chest"] = None
    game_elements_ref["level_data"] = None
    list_keys_to_reinitialize = [
        "enemy_list", "statue_objects", "collectible_list", "projectiles_list",
        "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
        "all_renderable_objects", "enemy_spawns_data_cache", "statue_spawns_data_cache",
        "processed_custom_images_for_render"
    ]
    for key in list_keys_to_reinitialize: game_elements_ref[key] = []
    game_elements_ref['initialization_in_progress'] = True
    game_elements_ref['game_ready_for_logic'] = False
    game_elements_ref['camera_level_dims_set'] = False
    gc.collect()
    debug("GameSetup DEBUG: Existing game elements cleared and lists re-initialized.")

    level_data: Optional[Dict[str, Any]] = None; loader = LevelLoader()
    debug(f"GameSetup DEBUG: Attempting to load map '{current_map_to_load}' using base maps directory '{maps_base_dir_abs}'.")
    level_data = loader.load_map(str(current_map_to_load), maps_base_dir_abs)
    if not level_data or not isinstance(level_data, dict):
        critical(f"GameSetup FATAL: Failed to load/reload map data for '{current_map_to_load}' from base '{maps_base_dir_abs}'. Initialization aborted.")
        game_elements_ref["loaded_map_name"] = None; game_elements_ref['initialization_in_progress'] = False; return False
    game_elements_ref["level_data"] = level_data; game_elements_ref["loaded_map_name"] = current_map_to_load
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
    game_elements_ref["statue_spawns_data_cache"] = list(level_data.get('statues_list', []))

    for p_data in level_data.get('platforms_list', []):
        try:
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4: game_elements_ref["platforms_list"].append(Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(p_data.get('color', getattr(C, 'GRAY', (128,128,128)))), platform_type=str(p_data.get('type', 'generic_platform')), properties=p_data.get('properties', {}) ))
        except Exception as e_plat: error(f"GameSetup: Error creating platform: {e_plat}", exc_info=True)
    for l_data in level_data.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4: game_elements_ref["ladders_list"].append(Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]) ))
        except Exception as e_lad: error(f"GameSetup: Error creating ladder: {e_lad}", exc_info=True)
    for h_data in level_data.get('hazards_list', []):
        try:
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4 and (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()): game_elements_ref["hazards_list"].append(Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(h_data.get('color', getattr(C, 'ORANGE_RED', (255,69,0)))) ))
        except Exception as e_haz: error(f"GameSetup: Error creating hazard: {e_haz}", exc_info=True)
    for bg_data in level_data.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4: game_elements_ref["background_tiles_list"].append(BackgroundTile(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(bg_data.get('color', getattr(C, 'DARK_GRAY', (50,50,50)))), tile_type=str(bg_data.get('type', 'generic_background')), image_path=bg_data.get('image_path'), properties=bg_data.get('properties', {}) ))
        except Exception as e_bg: error(f"GameSetup: Error creating background tile: {e_bg}", exc_info=True)
    info(f"GameSetup: Static tile-based elements re-created. Platforms: {len(game_elements_ref['platforms_list'])}")

    game_elements_ref["processed_custom_images_for_render"] = []
    custom_images_data_from_map = level_data.get("custom_images_list")
    if custom_images_data_from_map is None: info("GameSetup: 'custom_images_list' key NOT FOUND in level_data. No custom images will be loaded."); debug("GameSetup DEBUG: custom_images_data_from_map is None.")
    elif not isinstance(custom_images_data_from_map, list): error(f"GameSetup ERROR: 'custom_images_list' in map data is not a list, but type {type(custom_images_data_from_map)}. Cannot process custom images.")
    elif not custom_images_data_from_map: info("GameSetup: 'custom_images_list' key FOUND in level_data, but the list is EMPTY.")
    else:
        info(f"GameSetup: Found 'custom_images_list' with {len(custom_images_data_from_map)} entries. Processing them...")
        current_map_folder_path = os.path.join(maps_base_dir_abs, str(current_map_to_load))
        debug(f"GameSetup DEBUG: Custom image base folder path: {current_map_folder_path}")
        for img_idx, img_data_raw in enumerate(custom_images_data_from_map):
            if not isinstance(img_data_raw, dict): warning(f"GameSetup WARNING: Custom image data entry {img_idx} is not a dictionary. Skipping. Data: {img_data_raw}"); continue
            try:
                debug(f"GameSetup DEBUG: Processing custom image entry {img_idx}: {img_data_raw}"); rect_tuple = img_data_raw.get('rect'); rel_path = img_data_raw.get('source_file_path')
                layer_order = int(img_data_raw.get('layer_order', 0)); is_flipped_h = img_data_raw.get('is_flipped_h', False); rotation_angle = float(img_data_raw.get('rotation', 0))
                opacity_percent = float(img_data_raw.get('properties', {}).get('opacity', 100.0)); opacity_float = max(0.0, min(1.0, opacity_percent / 100.0))
                if not rect_tuple or not isinstance(rect_tuple, (list, tuple)) or len(rect_tuple) != 4: warning(f"GameSetup WARNING: Custom image data entry {img_idx} has invalid 'rect'. Skipping. Rect data: {rect_tuple}"); continue
                if not rel_path or not isinstance(rel_path, str): warning(f"GameSetup WARNING: Custom image data entry {img_idx} has invalid 'source_file_path'. Skipping. Path data: {rel_path}"); continue
                full_image_path = os.path.join(current_map_folder_path, rel_path)
                debug(f"GameSetup DEBUG: Custom image {img_idx}. Relative path from map: '{rel_path}'. Full constructed path for loading: '{full_image_path}'")
                if not os.path.exists(full_image_path): error(f"GameSetup ERROR: Custom image file NOT FOUND: {full_image_path}"); continue
                q_image_original = QImage(full_image_path)
                if q_image_original.isNull(): error(f"GameSetup ERROR: Failed to load custom image (QImage isNull): {full_image_path}"); continue
                debug(f"GameSetup DEBUG: Custom image {img_idx} loaded from disk. Original size: {q_image_original.size().width()}x{q_image_original.size().height()}")
                target_w = float(rect_tuple[2]); target_h = float(rect_tuple[3])
                if target_w <= 0 or target_h <= 0: warning(f"GameSetup WARNING: Invalid target dimensions ({target_w}x{target_h}) for custom image {rel_path}. Using original size."); target_w = float(q_image_original.width()); target_h = float(q_image_original.height())
                debug(f"GameSetup DEBUG: Custom image {img_idx} target render size: {target_w}x{target_h}")
                processed_image = q_image_original.scaled(int(target_w), int(target_h), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if is_flipped_h: debug(f"GameSetup DEBUG: Custom image {img_idx} is flipped horizontally."); processed_image = processed_image.mirrored(True, False)
                if rotation_angle != 0:
                    debug(f"GameSetup DEBUG: Custom image {img_idx} is rotated by {rotation_angle} degrees."); transform = QTransform(); img_center_x = processed_image.width() / 2.0; img_center_y = processed_image.height() / 2.0
                    transform.translate(img_center_x, img_center_y); transform.rotate(rotation_angle); transform.translate(-img_center_x, -img_center_y); processed_image = processed_image.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                final_pixmap = QPixmap.fromImage(processed_image)
                if final_pixmap.isNull(): error(f"GameSetup ERROR: Failed to create QPixmap from processed image for {full_image_path}"); continue
                renderable_custom_image = { 'rect': QRectF(float(rect_tuple[0]), float(rect_tuple[1]), target_w, target_h), 'image': final_pixmap, 'layer_order': layer_order, 'source_file_path_debug': rel_path, 'opacity_float': opacity_float }
                game_elements_ref["processed_custom_images_for_render"].append(renderable_custom_image)
                debug(f"GameSetup DEBUG: Processed custom image '{rel_path}' for rendering. Layer: {layer_order}, Opacity: {opacity_float:.2f}, Final Pixmap Size: {final_pixmap.size().width()}x{final_pixmap.size().height()}")
            except Exception as e_custom_img: error(f"GameSetup ERROR: Error processing custom image data entry {img_idx} ({img_data_raw}): {e_custom_img}", exc_info=True)
    info(f"GameSetup: Custom images processed: {len(game_elements_ref['processed_custom_images_for_render'])}")

    # Process Trigger Squares for visuals (if they are stored with visual properties)
    trigger_squares_data = level_data.get("trigger_squares_list", [])
    game_elements_ref["trigger_squares_list"] = [] # Ensure it's a list for game logic
    processed_trigger_visuals_count = 0
    if trigger_squares_data:
        info(f"GameSetup: Processing {len(trigger_squares_data)} trigger square entries for visuals...")
        for trig_idx, trig_data_raw in enumerate(trigger_squares_data):
            if not isinstance(trig_data_raw, dict): warning(f"GameSetup WARNING: Trigger square entry {trig_idx} is not a dict. Skipping."); continue
            try:
                rect_tuple = trig_data_raw.get('rect')
                if not rect_tuple or not isinstance(rect_tuple, (list, tuple)) or len(rect_tuple) != 4: warning(f"GameSetup WARNING: Trigger square {trig_idx} has invalid 'rect'. Skipping. Data: {rect_tuple}"); continue
                
                # Add the trigger data directly to game_elements for game logic
                game_elements_ref["trigger_squares_list"].append(trig_data_raw)

                # If triggers have a visual representation to be rendered like custom images:
                props = trig_data_raw.get("properties", {})
                if props.get("visible", False): # Only process for rendering if visible
                    q_img_trig: Optional[QImage] = None
                    trig_img_rel_path = props.get("image_in_square")
                    if trig_img_rel_path and isinstance(trig_img_rel_path, str):
                        full_trig_img_path = os.path.join(current_map_folder_path, trig_img_rel_path) # Assumes relative to map folder (e.g. in Custom/)
                        if os.path.exists(full_trig_img_path): q_img_trig = QImage(full_trig_img_path)
                        else: warning(f"GameSetup WARNING: Trigger image not found: {full_trig_img_path}")
                    
                    fill_color_rgba = props.get("fill_color_rgba")
                    target_w_trig = float(rect_tuple[2]); target_h_trig = float(rect_tuple[3])
                    
                    if target_w_trig <=0 or target_h_trig <=0: continue

                    trig_pixmap = QPixmap(int(target_w_trig), int(target_h_trig))
                    trig_pixmap.fill(Qt.GlobalColor.transparent) # Start with transparent
                    painter = QPainter(trig_pixmap)
                    if q_img_trig and not q_img_trig.isNull():
                        painter.drawImage(0,0, q_img_trig.scaled(int(target_w_trig), int(target_h_trig), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    elif fill_color_rgba and isinstance(fill_color_rgba, (list,tuple)) and len(fill_color_rgba)==4:
                        painter.fillRect(trig_pixmap.rect(), QColor(fill_color_rgba[0], fill_color_rgba[1], fill_color_rgba[2], fill_color_rgba[3]))
                    else: # Default fallback visual for visible triggers without image/color
                        painter.fillRect(trig_pixmap.rect(), QColor(100, 100, 255, 70))
                        painter.setPen(QColor(50,50,150,150)); painter.drawRect(trig_pixmap.rect().adjusted(0,0,-1,-1))
                    painter.end()

                    renderable_trigger_visual = {
                        'rect': QRectF(float(rect_tuple[0]), float(rect_tuple[1]), target_w_trig, target_h_trig),
                        'image': trig_pixmap,
                        'layer_order': trig_data_raw.get("layer_order", -1), # Behind most things by default if visible
                        'source_file_path_debug': f"Trigger: {trig_data_raw.get('id', trig_idx)}",
                        'opacity_float': 1.0 # Triggers usually fully visible or fully invisible
                    }
                    game_elements_ref["processed_custom_images_for_render"].append(renderable_trigger_visual)
                    processed_trigger_visuals_count += 1
            except Exception as e_trig_vis: error(f"GameSetup ERROR: Processing trigger visual {trig_idx} ({trig_data_raw}): {e_trig_vis}", exc_info=True)
        info(f"GameSetup: Trigger visuals processed: {processed_trigger_visuals_count}")
    else: info("GameSetup: No 'trigger_squares_list' in map_data or list is empty.")


    active_player_count = 0
    tile_sz = float(getattr(C, 'TILE_SIZE', 40.0))
    player1_default_spawn_pos_tuple = (100.0, float(current_height) - (tile_sz * 2.0))
    for i in range(1, 5):
        player_key = f"player{i}"; spawn_pos_key = f"player_start_pos_p{i}"; spawn_props_key = f"player{i}_spawn_props"
        player_spawn_pos_tuple_from_map = level_data.get(spawn_pos_key)
        player_props_for_init_from_map = level_data.get(spawn_props_key, {})
        game_elements_ref[spawn_pos_key] = player_spawn_pos_tuple_from_map; game_elements_ref[spawn_props_key] = player_props_for_init_from_map
        final_spawn_x, final_spawn_y = -1.0, -1.0
        if player_spawn_pos_tuple_from_map and isinstance(player_spawn_pos_tuple_from_map, (tuple, list)) and len(player_spawn_pos_tuple_from_map) == 2: final_spawn_x, final_spawn_y = float(player_spawn_pos_tuple_from_map[0]), float(player_spawn_pos_tuple_from_map[1])
        elif i == 1 : final_spawn_x, final_spawn_y = player1_default_spawn_pos_tuple[0], player1_default_spawn_pos_tuple[1]; game_elements_ref[spawn_pos_key] = (final_spawn_x, final_spawn_y); debug(f"GameSetup DEBUG: {spawn_pos_key} not in map data. Using fallback default for P1: ({final_spawn_x:.1f},{final_spawn_y:.1f})")
        else: game_elements_ref[player_key] = None; continue
        player_instance = Player(final_spawn_x, final_spawn_y, player_id=i, initial_properties=player_props_for_init_from_map)
        if not player_instance._valid_init: critical(f"GameSetup CRITICAL: {player_key} initialization FAILED! Map: '{current_map_to_load}'"); game_elements_ref[player_key] = None; continue
        player_instance.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
        if "joystick" in player_instance.control_scheme:
            try: player_instance.joystick_id_idx = int(player_instance.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player_instance.joystick_id_idx = None
        game_elements_ref[player_key] = player_instance
        player_instance.set_projectile_group_references(game_elements_ref["projectiles_list"], game_elements_ref["all_renderable_objects"], game_elements_ref["platforms_list"])
        active_player_count +=1; info(f"GameSetup: {player_key} RE-CREATED. Pos: ({final_spawn_x:.1f},{final_spawn_y:.1f}), Control: {player_instance.control_scheme}")
    info(f"GameSetup: Total active players RE-CREATED: {active_player_count}")

    authoritative_modes_for_spawn = ["couch_play", "host_game", "host", "host_waiting", "host_active"]
    if for_game_mode in authoritative_modes_for_spawn:
        debug(f"GameSetup DEBUG: Re-spawning dynamic entities for authoritative mode '{for_game_mode}'.")
        for i_enemy, spawn_info in enumerate(game_elements_ref["enemy_spawns_data_cache"]):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data'); patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']): patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']), float(patrol_raw['width']), float(patrol_raw['height']))
                enemy_color_name = str(spawn_info.get('type', 'enemy_green')); start_pos_tuple = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0)))); enemy_props = spawn_info.get('properties', {})
                new_enemy = Enemy(start_x=start_pos_tuple[0], start_y=start_pos_tuple[1], patrol_area=patrol_qrectf, enemy_id=i_enemy, color_name=enemy_color_name, properties=enemy_props)
                if new_enemy._valid_init: game_elements_ref["enemy_list"].append(new_enemy)
                else: warning(f"GameSetup WARNING: Failed to initialize enemy {i_enemy} (type: {enemy_color_name}) during reset.")
            except Exception as e_enemy_create: error(f"GameSetup ERROR: Error creating enemy {i_enemy} during reset: {e_enemy_create}", exc_info=True)
        info(f"GameSetup: Enemies re-created: {len(game_elements_ref['enemy_list'])}")
        for i_statue, statue_data in enumerate(game_elements_ref["statue_spawns_data_cache"]):
            try:
                s_id = statue_data.get('id', f"map_statue_rs_{i_statue}"); s_pos_tuple = tuple(map(float, statue_data.get('pos', (200.0, 200.0)))); s_props = statue_data.get('properties', {})
                new_statue = Statue(center_x=s_pos_tuple[0], center_y=s_pos_tuple[1], statue_id=s_id, properties=s_props)
                if new_statue._valid_init:
                    game_elements_ref["statue_objects"].append(new_statue)
                    if not new_statue.is_smashed: game_elements_ref["platforms_list"].append(new_statue)
                else: warning(f"GameSetup WARNING: Failed to initialize statue {i_statue} (id: {s_id}) during reset.")
            except Exception as e_statue_create: error(f"GameSetup ERROR: Error creating statue {i_statue} during reset: {e_statue_create}", exc_info=True)
        info(f"GameSetup: Statues re-created: {len(game_elements_ref['statue_objects'])}")
        new_chest_instance: Optional[Chest] = None
        items_from_fresh_map_data = level_data.get('items_list', [])
        for item_data_fresh in items_from_fresh_map_data:
            if item_data_fresh.get('type', '').lower() == 'chest':
                try:
                    chest_pos_fresh = tuple(map(float, item_data_fresh.get('pos', (300.0, 300.0))))
                    new_chest_instance = Chest(x=chest_pos_fresh[0], y=chest_pos_fresh[1])
                    if new_chest_instance._valid_init: game_elements_ref["collectible_list"].append(new_chest_instance); info(f"GameSetup (Reset): Chest RE-CREATED at {chest_pos_fresh} from fresh map data.")
                    else: warning("GameSetup WARNING (Reset): NEW Chest instance from map data failed to initialize.")
                    break
                except Exception as e_chest_create: error(f"GameSetup ERROR: Error creating NEW Chest instance during reset: {e_chest_create}", exc_info=True)
        game_elements_ref["current_chest"] = new_chest_instance
    else:
        debug(f"GameSetup DEBUG: Dynamic entities not re-spawned by client for mode '{for_game_mode}'. Server state will dictate.")
        game_elements_ref["current_chest"] = None

    camera_instance = Camera(initial_level_width=game_elements_ref.get("level_pixel_width", float(current_width) * 2.0), initial_world_start_x=game_elements_ref.get("level_min_x_absolute", 0.0), initial_world_start_y=game_elements_ref.get("level_min_y_absolute", 0.0), initial_level_bottom_y_abs=game_elements_ref.get("level_max_y_absolute", float(current_height)), screen_width=float(current_width), screen_height=float(current_height))
    if camera_instance is None: critical("GameSetup CRITICAL: Camera instance became None immediately after Camera() call!") # New Check
    game_elements_ref["camera"] = camera_instance
    debug(f"GameSetup DEBUG: Directly after assignment, type of game_elements_ref['camera']: {type(game_elements_ref.get('camera'))}, ID: {id(game_elements_ref.get('camera'))}")
    game_elements_ref["camera_level_dims_set"] = True
    p1_for_cam = game_elements_ref.get("player1")
    if p1_for_cam and p1_for_cam._valid_init and p1_for_cam.alive(): camera_instance.update(p1_for_cam)
    else:
        first_active_player_for_cam = None
        for i_p_cam in range(1,5):
            p_check_cam = game_elements_ref.get(f"player{i_p_cam}")
            if p_check_cam and p_check_cam._valid_init and p_check_cam.alive(): first_active_player_for_cam = p_check_cam; break
        if first_active_player_for_cam: camera_instance.update(first_active_player_for_cam)
        else: camera_instance.static_update()
    info("GameSetup: Camera re-initialized and focused.")

    new_all_renderables_setup_temp: List[Any] = []
    for static_key in ["background_tiles_list", "ladders_list", "hazards_list", "platforms_list"]:
        for item in game_elements_ref.get(static_key, []): add_to_renderables_if_new(item, new_all_renderables_setup_temp)
    for custom_img_dict in game_elements_ref.get("processed_custom_images_for_render", []):
        add_to_renderables_if_new(custom_img_dict, new_all_renderables_setup_temp)
        debug(f"GameSetup DEBUG: Added to renderables from processed_custom_images_for_render: {custom_img_dict.get('source_file_path_debug', 'Unknown Custom Image')}")
    for dynamic_key in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
        for item_dyn in game_elements_ref.get(dynamic_key, []): add_to_renderables_if_new(item_dyn, new_all_renderables_setup_temp)
    # Add trigger squares to renderables only if they have visual representation (e.g., are visible)
    # This was already handled in the "Trigger visuals processed" section if they become part of "processed_custom_images_for_render"
    # If they are separate and need to be drawn from trigger_squares_list, that logic would be in GameSceneWidget.

    for i_p_render in range(1, 5):
        p_to_render = game_elements_ref.get(f"player{i_p_render}")
        if p_to_render: add_to_renderables_if_new(p_to_render, new_all_renderables_setup_temp)
    debug(f"GameSetup DEBUG: Before sorting renderables, count: {len(new_all_renderables_setup_temp)}")
    new_all_renderables_setup_temp.sort(key=get_layer_order_key)
    game_elements_ref["all_renderable_objects"] = new_all_renderables_setup_temp
    debug(f"GameSetup DEBUG: Assembled and sorted all_renderable_objects. Final Count: {len(game_elements_ref['all_renderable_objects'])}")

    game_elements_ref["game_ready_for_logic"] = True
    game_elements_ref["initialization_in_progress"] = False
    info(f"GameSetup: --- Full Map (Re)Load & Entity Re-Initialization COMPLETE for map '{current_map_to_load}' ---")
    return True