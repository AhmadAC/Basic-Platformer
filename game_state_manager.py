# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
Ensures full map reset by ALWAYS re-parsing original map data for all entities.
"""
# version 2.1.6 (FORCE map reload from file on reset for pristine state)
import os
import sys
from typing import Optional, List, Dict, Any, Tuple
from camera import Camera
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor

# Game-specific imports
from enemy import Enemy
from items import Chest
from statue import Statue
from player import Player
from tiles import Platform, Ladder, Lava, BackgroundTile # Ensure ALL tile types are here
from projectiles import (
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
import constants as C
from level_loader import LevelLoader # Crucial for reloading map data
from assets import load_all_player_animations # For re-initializing player anims if needed
# Import for set_player_state
try:
    from player_state_handler import set_player_state
except ImportError as e_psh:
    # This is a critical dependency for player reset. Log and define a fallback.
    _print_func_gsm = print if 'print' in globals() else sys.stdout.write
    _print_func_gsm(f"CRITICAL GSM Import Error: Failed to import set_player_state: {e_psh}\n")
    def set_player_state(player: Any, new_state: str): # Fallback
        if hasattr(player, 'state'): player.state = new_state
        _print_func_gsm(f"FALLBACK GSM: set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'\n")

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG, format='GSM (Fallback): %(levelname)s - %(message)s')
    logger_gsm = logging.getLogger(__name__ + "_fallback_gsm")
    def info(msg, *args, **kwargs): logger_gsm.info(msg, *args, **kwargs)
    def debug(msg, *args, **kwargs): logger_gsm.debug(msg, *args, **kwargs)
    def warning(msg, *args, **kwargs): logger_gsm.warning(msg, *args, **kwargs)
    def error(msg, *args, **kwargs): logger_gsm.error(msg, *args, **kwargs)
    def critical(msg, *args, **kwargs): logger_gsm.critical(msg, *args, **kwargs)


def _reset_player_attributes_internal(player_instance: Player,
                                      spawn_pos_tuple: Optional[Tuple[float, float]],
                                      initial_props: Optional[Dict[str, Any]] = None,
                                      player_id_for_log: str = "P?"):
    """Helper to reset individual player attributes."""
    # (This helper function remains the same as the version 2.1.3 you approved - it's for player attributes only)
    if not isinstance(player_instance, Player):
        error(f"GSM _reset_player_attributes: Invalid object for {player_id_for_log}. Expected Player, got {type(player_instance)}")
        return
    info(f"GSM _reset_player_attributes: Resetting {player_id_for_log}. Spawn requested: {spawn_pos_tuple}")
    initial_props = initial_props or {}
    if not player_instance._valid_init and player_instance.animations is None:
        asset_folder = 'characters/player1' if player_instance.player_id == 1 else 'characters/player2'
        warning(f"GSM _reset_player_attributes ({player_id_for_log}): Anim reload attempt from '{asset_folder}'.")
        try:
            player_instance.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if player_instance.animations:
                player_instance._valid_init = True
                idle_frames = player_instance.animations.get('idle')
                player_instance.standing_collision_height = float(idle_frames[0].height()) if idle_frames and idle_frames[0] and not idle_frames[0].isNull() else 60.0
                crouch_frames = player_instance.animations.get('crouch')
                player_instance.crouching_collision_height = float(crouch_frames[0].height()) if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull() else player_instance.standing_collision_height / 2.0
                if not (1e-6 < player_instance.standing_collision_height < 1000 and 1e-6 < player_instance.crouching_collision_height < player_instance.standing_collision_height):
                    error(f"GSM _reset_player_attributes ({player_id_for_log}): Invalid collision heights post-anim-reload. Invalidating.")
                    player_instance._valid_init = False
                player_instance.standard_height = player_instance.standing_collision_height
                initial_idle_frames_reset = player_instance.animations.get('idle')
                if initial_idle_frames_reset and initial_idle_frames_reset[0] and not initial_idle_frames_reset[0].isNull(): player_instance.image = initial_idle_frames_reset[0]
                else: player_instance.image = player_instance._create_placeholder_qpixmap(QColor(*getattr(C,'RED',(255,0,0))), "RstIdleFail"); player_instance._valid_init = False
            else: player_instance._valid_init = False
        except Exception as e_anim_reset: error(f"GSM _reset_player_attributes ({player_id_for_log}) exc re-init anims: {e_anim_reset}", exc_info=True); player_instance._valid_init = False
    if not player_instance._valid_init:
        player_instance.is_dead = True; player_instance._alive = False; player_instance.current_health = 0
        player_instance.pos = QPointF(player_instance.initial_spawn_pos) if isinstance(player_instance.initial_spawn_pos, QPointF) else QPointF(50,500)
        player_instance.vel = QPointF(0.0, 0.0); player_instance.acc = QPointF(0.0, 0.0)
        if player_instance.image is None or player_instance.image.isNull(): player_instance.image = player_instance._create_placeholder_qpixmap(QColor(*getattr(C, 'MAGENTA', (255,0,255))), "InvRst")
        if hasattr(player_instance, '_update_rect_from_image_and_pos'): player_instance._update_rect_from_image_and_pos()
        critical(f"GSM _reset_player_attributes ({player_id_for_log}): Player still invalid. Minimal reset.")
        return
    actual_spawn_pos = QPointF(player_instance.initial_spawn_pos)
    if spawn_pos_tuple and isinstance(spawn_pos_tuple, (tuple, list)) and len(spawn_pos_tuple) == 2:
        try: actual_spawn_pos = QPointF(float(spawn_pos_tuple[0]), float(spawn_pos_tuple[1]))
        except (TypeError, ValueError): warning(f"GSM _reset_player_attributes ({player_id_for_log}): Invalid spawn_pos_tuple '{spawn_pos_tuple}'. Using default.")
    player_instance.pos = actual_spawn_pos
    player_instance.vel = QPointF(0.0, 0.0)
    player_instance.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
    player_instance.max_health = int(initial_props.get("max_health", getattr(player_instance, 'max_health', getattr(C, 'PLAYER_MAX_HEALTH', 100))))
    player_instance.current_health = player_instance.max_health
    player_instance.is_dead = False; player_instance.death_animation_finished = False; player_instance._alive = True
    player_instance.is_taking_hit = False; player_instance.is_attacking = False; player_instance.attack_type = 0
    player_instance.is_dashing = False; player_instance.is_rolling = False; player_instance.is_sliding = False; player_instance.is_crouching = False
    player_instance.on_ladder = False; player_instance.touching_wall = 0; player_instance.facing_right = True; player_instance.on_ground = False
    player_instance.hit_timer = 0; player_instance.dash_timer = 0; player_instance.roll_timer = 0; player_instance.slide_timer = 0
    player_instance.attack_timer = 0; player_instance.wall_climb_timer = 0;
    player_instance.fireball_cooldown_timer = 0; player_instance.poison_cooldown_timer = 0; player_instance.bolt_cooldown_timer = 0
    player_instance.blood_cooldown_timer = 0; player_instance.ice_cooldown_timer = 0; player_instance.shadow_cooldown_timer = 0
    player_instance.grey_cooldown_timer = 0;
    player_instance.fireball_last_input_dir = QPointF(1.0, 0.0)
    player_instance.is_aflame = False; player_instance.aflame_timer_start = 0; player_instance.is_deflaming = False
    player_instance.deflame_timer_start = 0; player_instance.aflame_damage_last_tick = 0
    player_instance.is_frozen = False; player_instance.is_defrosting = False; player_instance.frozen_effect_timer = 0
    player_instance.is_petrified = False; player_instance.is_stone_smashed = False; player_instance.stone_smashed_timer_start = 0
    player_instance.facing_at_petrification = player_instance.facing_right
    player_instance.was_crouching_when_petrified = False
    if hasattr(player_instance, '_init_stone_assets') and callable(player_instance._init_stone_assets): player_instance._init_stone_assets()
    set_player_state(player_instance, 'idle')
    if hasattr(player_instance, '_update_rect_from_image_and_pos') and callable(player_instance._update_rect_from_image_and_pos): player_instance._update_rect_from_image_and_pos()
    info(f"GSM _reset_player_attributes: {player_id_for_log} instance reset. State: {player_instance.state}, Pos: ({player_instance.pos.x():.1f},{player_instance.pos.y():.1f}), Alive: {player_instance._alive}")


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    info("GSM: --- Resetting Full Game State (PySide6) ---")
    map_name_for_reset = game_elements.get("map_name", game_elements.get("loaded_map_name"))

    # --- 1. Force RELOAD Map Definition Data to ensure it's pristine ---
    level_data_for_reset: Optional[Dict[str, Any]] = None
    if not map_name_for_reset:
        critical("GSM Reset: CRITICAL - 'map_name' is missing. Cannot reload map data. Reset will be severely incomplete.")
    else:
        info(f"GSM Reset: Force RELOADING map '{map_name_for_reset}' to ensure pristine data for all entities.")
        loader = LevelLoader()
        maps_dir_path = str(getattr(C, "MAPS_DIR", "maps"))
        if not os.path.isabs(maps_dir_path):
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root_guess = os.path.dirname(current_file_dir)
            if not os.path.isdir(os.path.join(project_root_guess, "maps")):
                 project_root_guess = os.path.dirname(project_root_guess)
            maps_dir_path = os.path.join(str(project_root_guess), maps_dir_path)
        
        level_data_for_reset = loader.load_map(map_name_for_reset, maps_dir_path)
        if level_data_for_reset:
            # Update game_elements with this pristine data. This is the new source of truth for this reset.
            game_elements["level_data"] = level_data_for_reset
            game_elements["enemy_spawns_data_cache"] = list(level_data_for_reset.get('enemies_list', []))
            game_elements["statue_spawns_data_cache"] = list(level_data_for_reset.get('statues_list', []))
            game_elements["player1_spawn_pos"] = level_data_for_reset.get("player_start_pos_p1")
            game_elements["player1_spawn_props"] = level_data_for_reset.get("player1_spawn_props", {})
            game_elements["player2_spawn_pos"] = level_data_for_reset.get("player_start_pos_p2")
            game_elements["player2_spawn_props"] = level_data_for_reset.get("player2_spawn_props", {})
            for key in ["level_pixel_width", "level_min_x_absolute", "level_min_y_absolute", 
                        "level_max_y_absolute", "ground_level_y_ref", "ground_platform_height_ref",
                        "level_background_color", "map_name", "loaded_map_name"]: # Ensure map_name is also updated
                if key in level_data_for_reset or (key == "map_name" or key == "loaded_map_name"): # map_name might not be in level_data itself
                    value_to_set = level_data_for_reset.get(key) if key in level_data_for_reset else map_name_for_reset
                    game_elements[key] = value_to_set
            info(f"GSM Reset: Successfully reloaded and updated game_elements with map data for '{map_name_for_reset}'.")
        else:
            critical(f"GSM Reset: CRITICAL - Failed to reload map data for '{map_name_for_reset}'. Reset cannot proceed correctly.")
            return game_elements.get("current_chest") # Return early if map load fails

    # --- 2. Re-initialize Static Entities (Platforms, Ladders, Hazards, Backgrounds) from Fresh level_data ---
    # Clear old static entity lists first
    for static_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        game_elements[static_key] = []
    
    if level_data_for_reset:
        # Re-create Platforms
        for p_data in level_data_for_reset.get('platforms_list', []):
            try:
                rect_tuple = p_data.get('rect')
                if rect_tuple and len(rect_tuple) == 4:
                    game_elements["platforms_list"].append(Platform(
                        x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                        width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                        color_tuple=tuple(p_data.get('color', C.GRAY)),
                        platform_type=str(p_data.get('type', 'generic_platform')),
                        properties=p_data.get('properties', {})
                    ))
            except Exception as e: error(f"GSM Reset: Error creating platform: {e}", exc_info=True)
        # Re-create Ladders
        for l_data in level_data_for_reset.get('ladders_list', []):
            try:
                rect_tuple = l_data.get('rect')
                if rect_tuple and len(rect_tuple) == 4:
                    game_elements["ladders_list"].append(Ladder(
                        x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                        width=float(rect_tuple[2]), height=float(rect_tuple[3])
                    ))
            except Exception as e: error(f"GSM Reset: Error creating ladder: {e}", exc_info=True)
        # Re-create Hazards
        for h_data in level_data_for_reset.get('hazards_list', []):
            try:
                rect_tuple = h_data.get('rect')
                if rect_tuple and len(rect_tuple) == 4 and \
                   (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()):
                    game_elements["hazards_list"].append(Lava(
                        x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                        width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                        color_tuple=tuple(h_data.get('color', C.ORANGE_RED))
                    ))
            except Exception as e: error(f"GSM Reset: Error creating hazard: {e}", exc_info=True)
        # Re-create Background Tiles
        for bg_data in level_data_for_reset.get('background_tiles_list', []):
            try:
                rect_tuple = bg_data.get('rect')
                if rect_tuple and len(rect_tuple) == 4:
                    game_elements["background_tiles_list"].append(BackgroundTile(
                        x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                        width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                        color_tuple=tuple(bg_data.get('color', C.DARK_GRAY)),
                        tile_type=str(bg_data.get('type', 'generic_background')),
                        image_path=bg_data.get('image_path'),
                        properties=bg_data.get('properties', {})
                    ))
            except Exception as e: error(f"GSM Reset: Error creating background tile: {e}", exc_info=True)
        info(f"GSM Reset: Static map elements (platforms, etc.) re-instantiated from fresh level_data.")
    else:
        error("GSM Reset: Cannot re-instantiate static map elements because level_data is unavailable.")

    # --- 3. Clear Dynamic Entity Lists in game_elements ---
    game_elements["enemy_list"] = []
    game_elements["statue_objects"] = []
    game_elements["projectiles_list"] = []
    game_elements["collectible_list"] = []
    game_elements["current_chest"] = None

    # --- 4. Rebuild `all_renderable_objects` ---
    game_elements["all_renderable_objects"] = []
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        game_elements["all_renderable_objects"].extend(game_elements.get(static_list_key, []))

    # --- 5. Reset Players ---
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    p1_spawn_pos = game_elements.get("player1_spawn_pos")
    p1_props = game_elements.get("player1_spawn_props")
    p2_spawn_pos = game_elements.get("player2_spawn_pos")
    p2_props = game_elements.get("player2_spawn_props")

    if player1 and isinstance(player1, Player):
        _reset_player_attributes_internal(player1, p1_spawn_pos, p1_props, "P1")
        if player1._valid_init and player1.alive():
            game_elements["all_renderable_objects"].append(player1)

    if player2 and isinstance(player2, Player):
        _reset_player_attributes_internal(player2, p2_spawn_pos, p2_props, "P2")
        if player2._valid_init and player2.alive():
            game_elements["all_renderable_objects"].append(player2)

    # --- 6. Respawn Dynamic Entities from fresh map data if in authoritative mode ---
    current_game_mode = game_elements.get("current_game_mode", "unknown")
    server_authoritative_modes = ["couch_play", "host_waiting", "host_active"]

    if current_game_mode in server_authoritative_modes:
        debug(f"GSM: Respawning dynamic entities for authoritative mode '{current_game_mode}'.")
        
        enemy_spawns_from_data = level_data_for_reset.get('enemies_list', []) if level_data_for_reset else []
        statue_spawns_from_data = level_data_for_reset.get('statues_list', []) if level_data_for_reset else []
        items_from_data = level_data_for_reset.get('items_list', []) if level_data_for_reset else []

        if enemy_spawns_from_data:
            for i, spawn_info in enumerate(enemy_spawns_from_data):
                # ... (Enemy creation logic, same as before) ...
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
                        game_elements["enemy_list"].append(new_enemy); game_elements["all_renderable_objects"].append(new_enemy)
                except Exception as e: error(f"GSM: Error respawning enemy {i}: {e}", exc_info=True)
        
        if statue_spawns_from_data:
            for i, statue_data in enumerate(statue_spawns_from_data):
                # ... (Statue creation logic, same as before) ...
                try:
                    s_id = statue_data.get('id', f"map_statue_reset_{i}")
                    s_pos = tuple(map(float, statue_data.get('pos', (200.0, 200.0))))
                    s_props = statue_data.get('properties', {})
                    new_statue = Statue(s_pos[0], s_pos[1], statue_id=s_id, properties=s_props)
                    if new_statue._valid_init and new_statue.alive():
                        game_elements["statue_objects"].append(new_statue); game_elements["all_renderable_objects"].append(new_statue)
                except Exception as e: error(f"GSM: Error respawning statue {i}: {e}", exc_info=True)
            
        new_chest_obj: Optional[Chest] = None
        if items_from_data:
            for item_data in items_from_data:
                if item_data.get('type', '').lower() == 'chest':
                    try:
                        # ... (Chest creation logic, same as before) ...
                        chest_pos = tuple(map(float, item_data.get('pos', (300.0, 300.0))))
                        new_chest_obj = Chest(chest_pos[0], chest_pos[1]) # Add properties if Chest constructor takes them
                        if new_chest_obj._valid_init:
                            game_elements["collectible_list"].append(new_chest_obj); game_elements["all_renderable_objects"].append(new_chest_obj)
                            info(f"GSM: Chest respawned at {chest_pos}.")
                        else: warning("GSM: Chest failed to init on reset from items_list.")
                        break 
                    except Exception as e: error(f"GSM: Error respawning chest: {e}", exc_info=True)
        game_elements["current_chest"] = new_chest_obj
    else: # Not an authoritative mode
        debug(f"GSM: Dynamic entities not respawned for mode '{current_game_mode}'.")
        game_elements["current_chest"] = None

    # --- 7. Camera Reset ---
    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset') and level_data_for_reset: # Ensure level_data is available for camera
        # Update camera level dimensions based on the reloaded level_data
        cam_lvl_w = float(level_data_for_reset.get('level_pixel_width', C.GAME_WIDTH * 2))
        cam_min_x = float(level_data_for_reset.get('level_min_x_absolute', 0.0))
        cam_min_y = float(level_data_for_reset.get('level_min_y_absolute', 0.0))
        cam_max_y = float(level_data_for_reset.get('level_max_y_absolute', C.GAME_HEIGHT))
        camera.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
        
        camera.set_offset(0.0, 0.0) # Reset camera offset
        focus_target_cam = None
        if player1 and player1.alive() and player1._valid_init: focus_target_cam = player1
        elif player2 and player2.alive() and player2._valid_init: focus_target_cam = player2
        if focus_target_cam: camera.update(focus_target_cam)
        else: camera.static_update()
    debug("GSM: Camera state reset and re-evaluated.")
    
    info("GSM: --- Full Game State Reset Finished (PySide6) ---")
    return game_elements.get("current_chest")


# --- Projectile Class Map (for network deserialization) ---
# (This remains unchanged)
projectile_class_map: Dict[str, type] = {
    "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
    "BloodShot": BloodShot, "IceShard": IceShard,
    "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
}

def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    # (This function remains unchanged from version 2.1.3)
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'enemies': {}, 'chest': None,
        'statues': [], 'projectiles': [], 'game_over': False,
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name","unknown_map"))
    }
    player1: Optional[Player] = game_elements.get("player1")
    player2: Optional[Player] = game_elements.get("player2")
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    for enemy in enemy_list:
        if hasattr(enemy, '_valid_init') and enemy._valid_init and hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            is_enemy_net_relevant = (enemy.alive() or (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or getattr(enemy, 'is_petrified', False))
            if is_enemy_net_relevant: state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()
    statue_list: List[Statue] = game_elements.get("statue_objects", [])
    for s_obj in statue_list:
        if hasattr(s_obj, '_valid_init') and s_obj._valid_init and hasattr(s_obj, 'get_network_data'):
            is_statue_net_relevant = ((hasattr(s_obj, 'alive') and s_obj.alive()) or (getattr(s_obj, 'is_smashed', False) and not getattr(s_obj, 'death_animation_finished', True)))
            if is_statue_net_relevant: state['statues'].append(s_obj.get_network_data())
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    if current_chest and hasattr(current_chest, '_valid_init') and current_chest._valid_init and hasattr(current_chest, 'get_network_data'):
        is_chest_net_relevant = current_chest.alive() or current_chest.state in ['opening', 'opened_visible', 'fading']
        if is_chest_net_relevant: state['chest'] = current_chest.get_network_data()
        else: state['chest'] = None
    else: state['chest'] = None
    p1_truly_gone = True
    if player1 and player1._valid_init:
        if player1.alive(): p1_truly_gone = False
        elif player1.is_dead:
            if player1.is_petrified and not player1.is_stone_smashed: p1_truly_gone = False
            elif not player1.death_animation_finished: p1_truly_gone = False
    state['game_over'] = p1_truly_gone
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]
    return state


def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None):
    # (This function remains unchanged from version 2.1.3)
    player1: Optional[Player] = game_elements.get("player1")
    player2: Optional[Player] = game_elements.get("player2")
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client_ref: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj_client: Optional[Chest] = game_elements.get("current_chest")
    projectiles_list_ref: List[Any] = game_elements.get("projectiles_list", [])
    new_all_renderables: List[Any] = []; current_all_renderables_set = set()
    def add_to_renderables_if_new(obj: Any):
        if obj is not None and obj not in current_all_renderables_set: new_all_renderables.append(obj); current_all_renderables_set.add(obj)
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []): add_to_renderables_if_new(static_item)
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        is_p1_renderable = player1._valid_init and (player1.alive() or (player1.is_dead and not player1.death_animation_finished and not player1.is_petrified) or player1.is_petrified )
        if is_p1_renderable: add_to_renderables_if_new(player1)
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        is_p2_renderable = player2._valid_init and (player2.alive() or (player2.is_dead and not player2.death_animation_finished and not player2.is_petrified) or player2.is_petrified )
        if is_p2_renderable: add_to_renderables_if_new(player2)
    new_enemy_list_client: List[Enemy] = []
    if 'enemies' in network_state_data and isinstance(network_state_data['enemies'], dict):
        received_enemy_data_map = network_state_data['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list_ref if hasattr(enemy, 'enemy_id')}
        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server."); continue
            client_enemy: Optional[Enemy] = None
            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map: client_enemy = current_client_enemies_map[enemy_id_str]
                else:
                    original_spawn_info = enemy_spawns_data_cache[enemy_id_int] if enemy_spawns_data_cache and 0 <= enemy_id_int < len(enemy_spawns_data_cache) else None
                    spawn_pos_e = enemy_data_server.get('pos', original_spawn_info.get('start_pos') if original_spawn_info else (100.0,100.0))
                    patrol_area_e: Optional[QRectF] = None
                    if original_spawn_info and 'patrol_rect_data' in original_spawn_info and isinstance(original_spawn_info['patrol_rect_data'], dict):
                        pr_d = original_spawn_info['patrol_rect_data']
                        patrol_area_e = QRectF(float(pr_d.get('x',0)), float(pr_d.get('y',0)), float(pr_d.get('width',100)), float(pr_d.get('height',50)))
                    e_color = enemy_data_server.get('color_name', original_spawn_info.get('type') if original_spawn_info else 'enemy_green')
                    e_props = enemy_data_server.get('properties', original_spawn_info.get('properties', {}) if original_spawn_info else {})
                    client_enemy = Enemy(start_x=float(spawn_pos_e[0]), start_y=float(spawn_pos_e[1]), patrol_area=patrol_area_e, enemy_id=enemy_id_int, color_name=e_color, properties=e_props)
                if client_enemy and client_enemy._valid_init:
                    client_enemy.set_network_data(enemy_data_server)
                    new_enemy_list_client.append(client_enemy)
                    if client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished and not client_enemy.is_petrified) or client_enemy.is_petrified: add_to_renderables_if_new(client_enemy)
    game_elements["enemy_list"] = new_enemy_list_client
    new_statue_list_client: List[Statue] = []
    if 'statues' in network_state_data and isinstance(network_state_data['statues'], list):
        received_statue_data_list = network_state_data['statues']
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client_ref if hasattr(s, 'statue_id')}
        for statue_data_server in received_statue_data_list:
            if not (isinstance(statue_data_server,dict) and 'id' in statue_data_server): continue
            statue_id_s = str(statue_data_server['id']); client_statue: Optional[Statue] = None
            if statue_data_server.get('_valid_init',False):
                if statue_id_s in current_client_statues_map: client_statue = current_client_statues_map[statue_id_s]
                else:
                    orig_s_info = next((s_inf for s_inf in statue_spawns_data_cache if s_inf.get('id') == statue_id_s),None)
                    s_pos = statue_data_server.get('pos', orig_s_info.get('pos') if orig_s_info else (200.0,200.0))
                    s_props = statue_data_server.get('properties', orig_s_info.get('properties',{}) if orig_s_info else {})
                    client_statue = Statue(float(s_pos[0]), float(s_pos[1]), statue_id=statue_id_s, properties=s_props)
                if client_statue and client_statue._valid_init:
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    new_statue_list_client.append(client_statue)
                    if client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True)): add_to_renderables_if_new(client_statue)
    game_elements["statue_objects"] = new_statue_list_client
    new_collectible_list_client: List[Any] = []; current_chest_obj_synced: Optional[Chest] = None
    chest_data_from_server = network_state_data.get('chest')
    if chest_data_from_server and isinstance(chest_data_from_server, dict) and chest_data_from_server.get('_alive', True):
        if not current_chest_obj_client or not current_chest_obj_client._valid_init:
            chest_pos = chest_data_from_server.get('pos_midbottom', (300.0,300.0))
            current_chest_obj_client = Chest(x=float(chest_pos[0]), y=float(chest_pos[1]))
            game_elements["current_chest"] = current_chest_obj_client
        if current_chest_obj_client and current_chest_obj_client._valid_init:
            if hasattr(current_chest_obj_client, 'set_network_data'): current_chest_obj_client.set_network_data(chest_data_from_server)
            current_chest_obj_synced = current_chest_obj_client
            if current_chest_obj_synced.alive() or current_chest_obj_synced.state in ['opening', 'opened_visible', 'fading']: add_to_renderables_if_new(current_chest_obj_synced)
    game_elements["current_chest"] = current_chest_obj_synced
    if current_chest_obj_synced: new_collectible_list_client.append(current_chest_obj_synced)
    game_elements["collectible_list"] = new_collectible_list_client
    new_projectiles_list_client: List[Any] = []
    if 'projectiles' in network_state_data and isinstance(network_state_data['projectiles'], list):
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list_ref if hasattr(p, 'projectile_id')}
        for proj_data_server in network_state_data['projectiles']:
            if not (isinstance(proj_data_server, dict) and 'id' in proj_data_server): continue
            proj_id_s = str(proj_data_server['id']); client_proj: Optional[Any] = None
            if proj_id_s in current_client_proj_map: client_proj = current_client_proj_map[proj_id_s]
            else:
                owner_inst: Optional[Player] = None
                owner_id_net = proj_data_server.get('owner_id')
                if owner_id_net == 1 and player1: owner_inst = player1
                elif owner_id_net == 2 and player2: owner_inst = player2
                if owner_inst and all(k in proj_data_server for k in ['pos','vel','type']):
                    ProjClass = projectile_class_map.get(proj_data_server['type'])
                    if ProjClass:
                        pos_d, vel_d = proj_data_server['pos'], proj_data_server['vel']
                        dir_qpf = QPointF(float(vel_d[0]), float(vel_d[1]))
                        client_proj = ProjClass(float(pos_d[0]),float(pos_d[1]), dir_qpf, owner_inst)
                        client_proj.projectile_id = proj_id_s
                        client_proj.game_elements_ref = game_elements
            if client_proj:
                if hasattr(client_proj,'set_network_data'): client_proj.set_network_data(proj_data_server)
                if client_proj.alive(): new_projectiles_list_client.append(client_proj); add_to_renderables_if_new(client_proj)
    game_elements["projectiles_list"] = new_projectiles_list_client
    game_elements["all_renderable_objects"] = new_all_renderables
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)
    server_map_name = network_state_data.get('map_name')
    camera_instance: Optional[Camera] = game_elements.get('camera')
    if server_map_name and camera_instance and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set', False)):
        client_level_data = game_elements.get('level_data')
        if client_level_data and isinstance(client_level_data, dict) and game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
    debug(f"GSM Client set_network_game_state END: Renderables: {len(game_elements['all_renderable_objects'])}")