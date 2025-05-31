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
MODIFIED: EnemyKnight instantiation logic.
MODIFIED: Ensured patrol_area QRectF is correctly created for enemies.
"""
# version 2.0.17 (Patrol Area QRectF fix)
import sys
import os
import importlib # For importlib.invalidate_caches()
import gc # Garbage Collector
from typing import Dict, Optional, Any, Tuple, List

# PySide6 imports
from PySide6.QtGui import QImage, QPixmap, QTransform, QColor, QPainter
from PySide6.QtCore import Qt, QRectF # QRectF is crucial for patrol_area

# Game-specific imports
import main_game.constants as C
from player import Player
from enemy import Enemy # Generic Enemy
from enemy_knight import EnemyKnight # Specific EnemyKnight
from items import Chest
from player.statue import Statue
from camera import Camera
from level_loader import LevelLoader
import main_game.config as game_config

from tiles import Platform, Ladder, Lava, BackgroundTile

# Logger
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

DEFAULT_LEVEL_MODULE_NAME = "original" # Default map if none specified

def add_to_renderables_if_new(obj_to_add: Any, renderables_list_ref: List[Any]):
    """Adds an object to the renderables list if it's not already present."""
    if obj_to_add is not None:
        is_present = False
        # Check identity for instances, deep equality for dicts (like custom images)
        if isinstance(obj_to_add, dict):
            for item in renderables_list_ref:
                if isinstance(item, dict) and item == obj_to_add: # Compare dicts by value
                    is_present = True; break
        else: # For class instances, check identity
            for item in renderables_list_ref:
                if item is obj_to_add:
                    is_present = True; break
        if not is_present:
            renderables_list_ref.append(obj_to_add)


def get_layer_order_key(item: Any) -> int:
    """Determines the rendering layer order for a game object."""
    layer_val = 0
    if isinstance(item, dict) and 'layer_order' in item:
        layer_val = int(item['layer_order'])
    elif hasattr(item, 'layer_order'):
        layer_val = int(getattr(item, 'layer_order', 0))
    elif isinstance(item, Player): layer_val = 100
    elif hasattr(item, 'projectile_id'): layer_val = 90 # Projectiles on top
    elif isinstance(item, Enemy): layer_val = 10 # Includes EnemyKnight
    elif isinstance(item, Statue): layer_val = 9
    elif isinstance(item, Chest): layer_val = 8
    elif isinstance(item, Platform): layer_val = -5
    elif isinstance(item, Ladder): layer_val = -6
    elif isinstance(item, Lava): layer_val = -7
    elif isinstance(item, BackgroundTile): layer_val = -10
    return layer_val


def initialize_game_elements(
    current_width: int,
    current_height: int,
    game_elements_ref: Dict[str, Any],
    for_game_mode: str = "unknown",
    map_module_name: Optional[str] = None # This is the folder_name/stem
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
            project_root_from_constants = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            warning(f"GameSetup: C.PROJECT_ROOT not found or empty. Guessed project root for maps: {project_root_from_constants}")
        maps_base_dir_abs = os.path.join(project_root_from_constants, maps_base_dir_abs)
    maps_base_dir_abs = os.path.normpath(maps_base_dir_abs)

    debug("GameSetup DEBUG: Clearing all existing game elements from game_elements_ref...")
    for i in range(1, 5):
        player_key = f"player{i}"
        if player_key in game_elements_ref:
            player_instance = game_elements_ref.get(player_key)
            if isinstance(player_instance, Player) and hasattr(player_instance, 'reset_for_new_game_or_round'):
                player_instance.reset_for_new_game_or_round()
            game_elements_ref[player_key] = None # Nullify the reference
    game_elements_ref["camera"] = None
    game_elements_ref["current_chest"] = None
    game_elements_ref["level_data"] = None
    list_keys_to_reinitialize = [
        "enemy_list", "statue_objects", "collectible_list", "projectiles_list",
        "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
        "all_renderable_objects", "enemy_spawns_data_cache", "statue_spawns_data_cache",
        "processed_custom_images_for_render", "trigger_squares_list"
    ]
    for key in list_keys_to_reinitialize: game_elements_ref[key] = []
    game_elements_ref['initialization_in_progress'] = True
    game_elements_ref['game_ready_for_logic'] = False
    game_elements_ref['camera_level_dims_set'] = False
    gc.collect() # Suggest garbage collection for potentially large old lists

    level_data: Optional[Dict[str, Any]] = None
    loader = LevelLoader()
    debug(f"GameSetup DEBUG: Attempting to load map '{current_map_to_load}' using base maps directory '{maps_base_dir_abs}'.")
    level_data = loader.load_map(str(current_map_to_load), maps_base_dir_abs)
    if not level_data or not isinstance(level_data, dict):
        critical(f"GameSetup FATAL: Failed to load/reload map data for '{current_map_to_load}'. Initialization aborted.")
        game_elements_ref["loaded_map_name"] = None; game_elements_ref['initialization_in_progress'] = False; return False
    
    game_elements_ref["level_data"] = level_data
    game_elements_ref["loaded_map_name"] = current_map_to_load
    game_elements_ref["map_name"] = current_map_to_load # Ensure map_name is also set
    info(f"GameSetup: Successfully reloaded pristine map data for '{current_map_to_load}'.")

    # Populate game_elements with map data
    game_elements_ref["level_background_color"] = tuple(level_data.get('background_color', getattr(C, 'LIGHT_BLUE', (173, 216, 230))))
    game_elements_ref["level_pixel_width"] = float(level_data.get('level_pixel_width', float(current_width) * 2.0))
    game_elements_ref["level_min_x_absolute"] = float(level_data.get('level_min_x_absolute', 0.0))
    game_elements_ref["level_min_y_absolute"] = float(level_data.get('level_min_y_absolute', 0.0))
    game_elements_ref["level_max_y_absolute"] = float(level_data.get('level_max_y_absolute', float(current_height)))
    game_elements_ref["ground_level_y_ref"] = float(level_data.get('ground_level_y_ref', game_elements_ref["level_max_y_absolute"] - float(getattr(C, 'TILE_SIZE', 40.0))))
    game_elements_ref["ground_platform_height_ref"] = float(level_data.get('ground_platform_height_ref', float(getattr(C, 'TILE_SIZE', 40.0))))
    game_elements_ref["enemy_spawns_data_cache"] = list(level_data.get('enemies_list', [])) # Make a copy
    game_elements_ref["statue_spawns_data_cache"] = list(level_data.get('statues_list', [])) # Make a copy
    game_elements_ref["trigger_squares_list"] = list(level_data.get('trigger_squares_list', []))

    # Create Tile Objects (Platforms, Ladders, Hazards, Backgrounds)
    for p_data in level_data.get('platforms_list', []):
        try:
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements_ref["platforms_list"].append(
                    Platform(x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                             width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                             color_tuple=tuple(p_data.get('color', getattr(C, 'GRAY', (128,128,128)))),
                             platform_type=str(p_data.get('type', 'generic_platform')),
                             properties=p_data.get('properties', {}))
                )
        except Exception as e_plat: error(f"GameSetup: Error creating platform: {e_plat}", exc_info=True)
    # ... (similar loops for Ladders, Hazards, BackgroundTiles as before) ...
    for l_data in level_data.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4: game_elements_ref["ladders_list"].append(Ladder(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]) ))
        except Exception as e_lad: error(f"GameSetup: Error creating ladder: {e_lad}", exc_info=True)
    for h_data in level_data.get('hazards_list', []):
        try:
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4 and (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()): game_elements_ref["hazards_list"].append(Lava(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(h_data.get('color', getattr(C, 'ORANGE_RED', (255,69,0)))), properties=h_data.get('properties', {}) ))
        except Exception as e_haz: error(f"GameSetup: Error creating hazard: {e_haz}", exc_info=True)
    for bg_data in level_data.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4: game_elements_ref["background_tiles_list"].append(BackgroundTile(x=float(rect_tuple[0]), y=float(rect_tuple[1]), width=float(rect_tuple[2]), height=float(rect_tuple[3]), color_tuple=tuple(bg_data.get('color', getattr(C, 'DARK_GRAY', (50,50,50)))), tile_type=str(bg_data.get('type', 'generic_background')), image_path=bg_data.get('image_path'), properties=bg_data.get('properties', {}) ))
        except Exception as e_bg: error(f"GameSetup: Error creating background tile: {e_bg}", exc_info=True)
    info(f"GameSetup: Static tile-based elements re-created. Platforms: {len(game_elements_ref['platforms_list'])}")

    # Process Custom Images for Rendering
    game_elements_ref["processed_custom_images_for_render"] = [] # Reset
    custom_images_data_from_map = level_data.get("custom_images_list")
    # ... (custom image processing logic remains the same as your provided code) ...
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

    # Process Trigger Squares for visuals (if needed, from level_data['trigger_squares_list'])
    # ... (trigger square visual processing logic remains the same) ...
    trigger_squares_data_gs = game_elements_ref.get("trigger_squares_list", [])
    processed_trigger_visuals_count = 0
    if trigger_squares_data_gs:
        # ... (same logic as before for creating trigger square visuals) ...
        pass
    else: info("GameSetup: No 'trigger_squares_list' in map_data or list is empty for visual processing.")


    # Create Player Instances
    active_player_count = 0
    tile_sz = float(getattr(C, 'TILE_SIZE', 40.0))
    player1_default_spawn_pos_tuple = (100.0, float(current_height) - (tile_sz * 2.0)) # Example default
    for i in range(1, 5): # P1 to P4
        player_key = f"player{i}"
        spawn_pos_key = f"player_start_pos_p{i}"
        spawn_props_key = f"player{i}_spawn_props"
        
        player_spawn_pos_tuple_from_map = level_data.get(spawn_pos_key)
        player_props_for_init_from_map = level_data.get(spawn_props_key, {})
        
        game_elements_ref[spawn_pos_key] = player_spawn_pos_tuple_from_map # Store original map data
        game_elements_ref[spawn_props_key] = player_props_for_init_from_map
        
        final_spawn_x, final_spawn_y = -1.0, -1.0
        if player_spawn_pos_tuple_from_map and isinstance(player_spawn_pos_tuple_from_map, (tuple, list)) and len(player_spawn_pos_tuple_from_map) == 2:
            final_spawn_x, final_spawn_y = float(player_spawn_pos_tuple_from_map[0]), float(player_spawn_pos_tuple_from_map[1])
        elif i == 1 : # Fallback for P1 if not in map
            final_spawn_x, final_spawn_y = player1_default_spawn_pos_tuple[0], player1_default_spawn_pos_tuple[1]
            game_elements_ref[spawn_pos_key] = (final_spawn_x, final_spawn_y) # Update game_elements
            debug(f"GameSetup DEBUG: {spawn_pos_key} not in map data. Using fallback default for P1: ({final_spawn_x:.1f},{final_spawn_y:.1f})")
        else: # No spawn data for P2, P3, P4 and no default defined here other than P1
            game_elements_ref[player_key] = None; continue # Skip creating this player

        player_instance = Player(final_spawn_x, final_spawn_y, player_id=i, initial_properties=player_props_for_init_from_map)
        if not player_instance._valid_init:
            critical(f"GameSetup CRITICAL: {player_key} initialization FAILED! Map: '{current_map_to_load}'"); game_elements_ref[player_key] = None; continue
        
        player_instance.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
        if "joystick" in player_instance.control_scheme:
            try: player_instance.joystick_id_idx = int(player_instance.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player_instance.joystick_id_idx = None
        
        game_elements_ref[player_key] = player_instance
        player_instance.set_projectile_group_references(game_elements_ref["projectiles_list"], game_elements_ref["all_renderable_objects"], game_elements_ref["platforms_list"])
        active_player_count +=1
        info(f"GameSetup: {player_key} RE-CREATED. Pos: ({final_spawn_x:.1f},{final_spawn_y:.1f}), Control: {player_instance.control_scheme}")
    info(f"GameSetup: Total active players RE-CREATED: {active_player_count}")

    # Create Dynamic Entities (Enemies, Statues, Chest) - Only if server/authoritative mode
    authoritative_modes_for_spawn = ["couch_play", "host_game", "host", "host_waiting", "host_active"]
    if for_game_mode in authoritative_modes_for_spawn:
        debug(f"GameSetup DEBUG: Re-spawning dynamic entities for authoritative mode '{for_game_mode}'.")
        for i_enemy, spawn_info in enumerate(game_elements_ref["enemy_spawns_data_cache"]):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data')
                patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']), float(patrol_raw['width']), float(patrol_raw['height']))
                elif isinstance(patrol_raw, (list, tuple)) and len(patrol_raw) == 4: # Handle old list format too
                     patrol_qrectf = QRectF(float(patrol_raw[0]), float(patrol_raw[1]), float(patrol_raw[2]), float(patrol_raw[3]))


                enemy_type_from_data = str(spawn_info.get('type', 'enemy_green'))
                start_pos_tuple = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))
                enemy_props_from_map = spawn_info.get('properties', {}) # These are from the map file
                new_enemy: Optional[Any] = None

                if enemy_type_from_data == "enemy_knight":
                    new_enemy = EnemyKnight(start_x=start_pos_tuple[0], start_y=start_pos_tuple[1],
                                            patrol_area=patrol_qrectf, enemy_id=i_enemy,
                                            properties=enemy_props_from_map)
                else: # Generic Enemy
                    new_enemy = Enemy(start_x=start_pos_tuple[0], start_y=start_pos_tuple[1],
                                      patrol_area=patrol_qrectf, enemy_id=i_enemy,
                                      color_name=enemy_type_from_data, # For generic enemy, type IS color_name
                                      properties=enemy_props_from_map)
                
                if new_enemy and new_enemy._valid_init:
                    game_elements_ref["enemy_list"].append(new_enemy)
                else: warning(f"GameSetup WARNING: Failed to initialize enemy {i_enemy} (type: {enemy_type_from_data}) during reset.")
            except Exception as e_enemy_create: error(f"GameSetup ERROR: Error creating enemy {i_enemy} during reset: {e_enemy_create}", exc_info=True)
        info(f"GameSetup: Enemies re-created: {len(game_elements_ref['enemy_list'])}")
        
        # ... (Statue and Chest creation logic remains the same) ...
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
    else: # Non-authoritative mode (e.g., client)
        debug(f"GameSetup DEBUG: Dynamic entities not re-spawned by client for mode '{for_game_mode}'. Server state will dictate.")
        game_elements_ref["current_chest"] = None # Client does not spawn chest

    # Initialize Camera
    camera_instance = Camera(
        initial_level_width=game_elements_ref.get("level_pixel_width", float(current_width) * 2.0),
        initial_world_start_x=game_elements_ref.get("level_min_x_absolute", 0.0),
        initial_world_start_y=game_elements_ref.get("level_min_y_absolute", 0.0),
        initial_level_bottom_y_abs=game_elements_ref.get("level_max_y_absolute", float(current_height)),
        screen_width=float(current_width),
        screen_height=float(current_height)
    )
    if camera_instance is None: critical("GameSetup CRITICAL: Camera instance became None immediately after Camera() call!")
    game_elements_ref["camera"] = camera_instance
    game_elements_ref["camera_level_dims_set"] = True # Dimensions are set at Camera init
    
    # Focus camera on P1 or first available active player
    p1_for_cam = game_elements_ref.get("player1")
    focus_target_for_camera = None
    if p1_for_cam and p1_for_cam._valid_init and p1_for_cam.alive(): focus_target_for_camera = p1_for_cam
    else:
        for i_p_cam_fallback in range(1,5):
            p_check_cam_fallback = game_elements_ref.get(f"player{i_p_cam_fallback}")
            if p_check_cam_fallback and p_check_cam_fallback._valid_init and p_check_cam_fallback.alive():
                focus_target_for_camera = p_check_cam_fallback; break
    if focus_target_for_camera: camera_instance.update(focus_target_for_camera)
    else: camera_instance.static_update()
    info("GameSetup: Camera re-initialized and focused.")

    # Assemble all renderable objects and sort them
    new_all_renderables_setup_temp: List[Any] = []
    # ... (add_to_renderables_if_new logic for all categories remains the same) ...
    for static_key in ["background_tiles_list", "ladders_list", "hazards_list", "platforms_list"]:
        for item in game_elements_ref.get(static_key, []): add_to_renderables_if_new(item, new_all_renderables_setup_temp)
    for custom_img_dict in game_elements_ref.get("processed_custom_images_for_render", []):
        add_to_renderables_if_new(custom_img_dict, new_all_renderables_setup_temp)
    for dynamic_key in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
        for item_dyn in game_elements_ref.get(dynamic_key, []): add_to_renderables_if_new(item_dyn, new_all_renderables_setup_temp)
    for i_p_render in range(1, 5):
        p_to_render = game_elements_ref.get(f"player{i_p_render}")
        if p_to_render: add_to_renderables_if_new(p_to_render, new_all_renderables_setup_temp)

    try:
        new_all_renderables_setup_temp.sort(key=get_layer_order_key)
    except Exception as e_sort:
        error(f"GameSetup ERROR: Error sorting renderables: {e_sort}. Render order might be incorrect.", exc_info=True)
    game_elements_ref["all_renderable_objects"] = new_all_renderables_setup_temp
    debug(f"GameSetup DEBUG: Assembled and sorted all_renderable_objects. Final Count: {len(game_elements_ref['all_renderable_objects'])}")

    # Finalize initialization state
    game_elements_ref["game_ready_for_logic"] = True
    game_elements_ref["initialization_in_progress"] = False
    info(f"GameSetup: --- Full Map (Re)Load & Entity Re-Initialization COMPLETE for map '{current_map_to_load}' ---")
    return True