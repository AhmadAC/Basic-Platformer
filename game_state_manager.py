# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
Ensures full map reset by re-parsing original map data for all entities.
"""
# version 2.1.7 (Fix NameErrors, ensure player reset uses correct config, full map reload)
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
from tiles import Platform, Ladder, Lava, BackgroundTile
from projectiles import (
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
import constants as C
from level_loader import LevelLoader
from assets import load_all_player_animations
import config as game_config # IMPORT game_config HERE

import gc # Garbage Collector
try:
    from logger import info, debug, warning, error, critical
    from player_state_handler import set_player_state
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG, format='GSM (Fallback): %(levelname)s - %(message)s')
    logger_gsm = logging.getLogger(__name__ + "_fallback_gsm")
    # Define fallback loggers and set_player_state
    def info(msg, *args, **kwargs): logger_gsm.info(msg, *args, **kwargs)
    def debug(msg, *args, **kwargs): logger_gsm.debug(msg, *args, **kwargs)
    def warning(msg, *args, **kwargs): logger_gsm.warning(msg, *args, **kwargs)
    def error(msg, *args, **kwargs): logger_gsm.error(msg, *args, **kwargs)
    def critical(msg, *args, **kwargs): logger_gsm.critical(msg, *args, **kwargs)
    def set_player_state(player: Any, new_state: str):
        if hasattr(player, 'state'): player.state = new_state
        logger_gsm.warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")


def _reset_player_attributes_internal(
    player_instance: Player,
    spawn_pos_tuple: Optional[Tuple[float, float]],
    initial_props: Optional[Dict[str, Any]] = None,
    player_id_for_log: str = "P?"
):
    """Helper to reset individual player attributes."""
    if not isinstance(player_instance, Player):
        error(f"GSM _reset_player_attributes: Invalid object for {player_id_for_log}. Expected Player, got {type(player_instance)}")
        return

    info(f"GSM _reset_player_attributes: Resetting {player_id_for_log}. Spawn requested: {spawn_pos_tuple}")
    initial_props = initial_props or {}

    # Animation System Re-check
    if not player_instance._valid_init and player_instance.animations is None:
        asset_folder = 'characters/player1' if player_instance.player_id == 1 else 'characters/player2' # Simplified
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
    
    if not player_instance._valid_init: # If still not valid after attempt
        player_instance.is_dead = True; player_instance._alive = False; player_instance.current_health = 0
        player_instance.pos = QPointF(player_instance.initial_spawn_pos) if isinstance(player_instance.initial_spawn_pos, QPointF) else QPointF(50,500)
        player_instance.vel = QPointF(0.0, 0.0); player_instance.acc = QPointF(0.0, 0.0)
        if player_instance.image is None or player_instance.image.isNull(): player_instance.image = player_instance._create_placeholder_qpixmap(QColor(*getattr(C, 'MAGENTA', (255,0,255))), "InvRst")
        if hasattr(player_instance, '_update_rect_from_image_and_pos'): player_instance._update_rect_from_image_and_pos()
        critical(f"GSM _reset_player_attributes ({player_id_for_log}): Player still invalid. Minimal reset.")
        return

    # Reset Position
    actual_spawn_pos = QPointF(player_instance.initial_spawn_pos)
    if spawn_pos_tuple and isinstance(spawn_pos_tuple, (tuple, list)) and len(spawn_pos_tuple) == 2:
        try: actual_spawn_pos = QPointF(float(spawn_pos_tuple[0]), float(spawn_pos_tuple[1]))
        except (TypeError, ValueError): warning(f"GSM _reset_player_attributes ({player_id_for_log}): Invalid spawn_pos_tuple '{spawn_pos_tuple}'. Using default.")
    player_instance.pos = actual_spawn_pos

    # Reset Core Attributes
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
    
    # Assign control scheme (important for input handling after reset)
    player_instance.control_scheme = getattr(game_config, f"CURRENT_P{player_instance.player_id}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
    if "joystick" in player_instance.control_scheme:
        try: player_instance.joystick_id_idx = int(player_instance.control_scheme.split('_')[-1])
        except: player_instance.joystick_id_idx = None
    
    if hasattr(player_instance, '_init_stone_assets') and callable(player_instance._init_stone_assets): player_instance._init_stone_assets()
    
    set_player_state(player_instance, 'idle')
    if hasattr(player_instance, '_update_rect_from_image_and_pos') and callable(player_instance._update_rect_from_image_and_pos): player_instance._update_rect_from_image_and_pos()

    info(f"GSM _reset_player_attributes: {player_id_for_log} instance reset completed.")


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    info("GSM: --- Resetting Full Game State (Focus: Pristine Map Data) ---")
    map_name_for_reset = game_elements.get("map_name", game_elements.get("loaded_map_name"))

    if not map_name_for_reset:
        critical("GSM Reset: CRITICAL - 'map_name' is missing. Cannot reload map. Reset ABORTED.")
        return game_elements.get("current_chest")
    
    info(f"GSM Reset: Force RELOADING map '{map_name_for_reset}' from disk.")
    loader = LevelLoader()
    maps_dir_path = str(getattr(C, "MAPS_DIR", "maps")) # Corrected variable name
    if not os.path.isabs(maps_dir_path):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_guess = os.path.dirname(current_file_dir)
        if not os.path.isdir(os.path.join(project_root_guess, "maps")):
             project_root_guess = os.path.dirname(project_root_guess)
        maps_dir_path = os.path.join(str(project_root_guess), maps_dir_path)
    
    level_data_for_reset = loader.load_map(map_name_for_reset, maps_dir_path)

    if not level_data_for_reset or not isinstance(level_data_for_reset, dict):
        critical(f"GSM Reset: CRITICAL - Failed to reload map data for '{map_name_for_reset}'. Reset ABORTED.")
        return game_elements.get("current_chest")
    
    game_elements["level_data"] = level_data_for_reset
    game_elements["loaded_map_name"] = map_name_for_reset
    # Update core map properties
    for key in ["level_background_color", "level_pixel_width", "level_min_x_absolute", 
                "level_min_y_absolute", "level_max_y_absolute", "ground_level_y_ref", 
                "ground_platform_height_ref"]:
        if key in level_data_for_reset: game_elements[key] = level_data_for_reset[key]
    game_elements["enemy_spawns_data_cache"] = list(level_data_for_reset.get('enemies_list', []))
    game_elements["statue_spawns_data_cache"] = list(level_data_for_reset.get('statues_list', []))
    info(f"GSM Reset: Successfully reloaded and updated game_elements with map data for '{map_name_for_reset}'.")

    # --- Clear ALL Current Game Entity Lists ---
    debug("GSM Reset: Clearing all entity lists.")
    for i in range(1, 5): game_elements[f"player{i}"] = None
    game_elements["camera"] = None; game_elements["current_chest"] = None
    for key in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list",
                "platforms_list", "ladders_list", "hazards_list", "background_tiles_list",
                "all_renderable_objects"]:
        game_elements[key] = []
    gc.collect()

    # --- Re-Instantiate Static Map Elements ---
    debug("GSM Reset: Re-instantiating static map elements...")
    # Platforms
    for p_data in level_data_for_reset.get('platforms_list', []):
        try:
            rect_tuple = p_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements["platforms_list"].append(Platform(
                    x=float(rect_tuple[0]), y=float(rect_tuple[1]),
                    width=float(rect_tuple[2]), height=float(rect_tuple[3]),
                    color_tuple=tuple(p_data.get('color', C.GRAY)),
                    platform_type=str(p_data.get('type', 'generic_platform')),
                    properties=p_data.get('properties', {}) ))
        except Exception as e: error(f"GSM Reset: Error creating platform: {e}", exc_info=True)
    game_elements["all_renderable_objects"].extend(game_elements["platforms_list"])
    # Ladders
    for l_data in level_data_for_reset.get('ladders_list', []):
        try:
            rect_tuple = l_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements["ladders_list"].append(Ladder(float(rect_tuple[0]), float(rect_tuple[1]), float(rect_tuple[2]), float(rect_tuple[3])))
        except Exception as e: error(f"GSM Reset: Error creating ladder: {e}", exc_info=True)
    game_elements["all_renderable_objects"].extend(game_elements["ladders_list"])
    # Hazards
    for h_data in level_data_for_reset.get('hazards_list', []):
        try:
            rect_tuple = h_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4 and (str(h_data.get('type', '')).lower() == 'lava' or "lava" in str(h_data.get('type', '')).lower()):
                game_elements["hazards_list"].append(Lava(float(rect_tuple[0]), float(rect_tuple[1]), float(rect_tuple[2]), float(rect_tuple[3]), tuple(h_data.get('color', C.ORANGE_RED))))
        except Exception as e: error(f"GSM Reset: Error creating hazard: {e}", exc_info=True)
    game_elements["all_renderable_objects"].extend(game_elements["hazards_list"])
    # Background Tiles
    for bg_data in level_data_for_reset.get('background_tiles_list', []):
        try:
            rect_tuple = bg_data.get('rect')
            if rect_tuple and len(rect_tuple) == 4:
                game_elements["background_tiles_list"].append(BackgroundTile(
                    float(rect_tuple[0]), float(rect_tuple[1]), float(rect_tuple[2]), float(rect_tuple[3]),
                    tuple(bg_data.get('color', C.DARK_GRAY)), str(bg_data.get('type', 'generic_background')),
                    bg_data.get('image_path'), bg_data.get('properties', {})))
        except Exception as e: error(f"GSM Reset: Error creating background_tile: {e}", exc_info=True)
    game_elements["all_renderable_objects"].extend(game_elements["background_tiles_list"])
    info(f"GSM Reset: Static map elements re-instantiated. Platforms: {len(game_elements['platforms_list'])}")

    # --- Re-Create and Reset Player Instances ---
    screen_width = game_elements.get('main_app_screen_width', C.GAME_WIDTH)   # Needed for player spawn fallback
    screen_height = game_elements.get('main_app_screen_height', C.GAME_HEIGHT) # Needed for player spawn fallback

    for i in range(1, 5):
        player_key = f"player{i}"
        spawn_pos_key = f"player_start_pos_p{i}"
        spawn_props_key = f"player{i}_spawn_props"

        # Fetch spawn info directly from the freshly loaded level_data
        player_spawn_pos_tuple = level_data_for_reset.get(spawn_pos_key)
        player_props = level_data_for_reset.get(spawn_props_key, {})
        
        # Store these potentially updated spawn details back into game_elements for consistency
        game_elements[spawn_pos_key] = player_spawn_pos_tuple
        game_elements[spawn_props_key] = player_props

        if player_spawn_pos_tuple:
            try:
                spawn_x = float(player_spawn_pos_tuple[0])
                spawn_y = float(player_spawn_pos_tuple[1])
                
                new_player_instance = Player(spawn_x, spawn_y, player_id=i, initial_properties=player_props)
                if new_player_instance._valid_init:
                    # Control scheme assignment using game_config (which should be imported)
                    new_player_instance.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
                    if "joystick" in new_player_instance.control_scheme:
                        try: new_player_instance.joystick_id_idx = int(new_player_instance.control_scheme.split('_')[-1])
                        except: new_player_instance.joystick_id_idx = None
                    
                    game_elements[player_key] = new_player_instance # Store the NEW instance
                    game_elements["all_renderable_objects"].append(new_player_instance)
                    new_player_instance.set_projectile_group_references(
                        game_elements["projectiles_list"],
                        game_elements["all_renderable_objects"],
                        game_elements["platforms_list"]
                    )
                    info(f"GSM Reset: {player_key} RE-CREATED. Pos: ({spawn_x:.1f},{spawn_y:.1f})")
                else:
                    critical(f"GSM Reset: {player_key} FAILED to initialize during reset.")
                    game_elements[player_key] = None
            except Exception as e_player_create:
                error(f"GSM Reset: Error creating {player_key}: {e_player_create}", exc_info=True)
                game_elements[player_key] = None
        else:
            game_elements[player_key] = None
            debug(f"GSM Reset: No spawn data for {player_key} in map '{map_name_for_reset}'.")

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")

    # --- Respawn Dynamic Entities from Fresh level_data (Enemies, Statues, Chest) ---
    current_game_mode = game_elements.get("current_game_mode", "unknown")
    server_authoritative_modes = ["couch_play", "host_waiting", "host_active", "host"]

    if current_game_mode in server_authoritative_modes:
        debug(f"GSM Reset: Respawning dynamic entities for authoritative mode '{current_game_mode}'.")
        # Enemies
        for i, spawn_info in enumerate(level_data_for_reset.get('enemies_list', [])):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data'); patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict): patrol_qrectf = QRectF(float(patrol_raw.get('x',0)), float(patrol_raw.get('y',0)), float(patrol_raw.get('width',100)), float(patrol_raw.get('height',50)))
                enemy_color_name = str(spawn_info.get('type', 'enemy_green')); start_pos = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0)))); props = spawn_info.get('properties', {})
                new_enemy = Enemy(start_x=start_pos[0], start_y=start_pos[1], patrol_area=patrol_qrectf, enemy_id=i, color_name=enemy_color_name, properties=props)
                if new_enemy._valid_init and new_enemy.alive(): game_elements["enemy_list"].append(new_enemy); game_elements["all_renderable_objects"].append(new_enemy)
            except Exception as e: error(f"GSM Reset: Error respawning enemy {i}: {e}", exc_info=True)
        # Statues
        for i, statue_data in enumerate(level_data_for_reset.get('statues_list', [])):
            try:
                s_id = statue_data.get('id', f"map_statue_reset_{i}"); s_pos = tuple(map(float, statue_data.get('pos', (200.0, 200.0)))); s_props = statue_data.get('properties', {})
                new_statue = Statue(s_pos[0], s_pos[1], statue_id=s_id, properties=s_props)
                if new_statue._valid_init and new_statue.alive(): game_elements["statue_objects"].append(new_statue); game_elements["all_renderable_objects"].append(new_statue)
            except Exception as e: error(f"GSM Reset: Error respawning statue {i}: {e}", exc_info=True)
        # Chest
        new_chest_obj: Optional[Chest] = None
        for item_data in level_data_for_reset.get('items_list', []):
            if item_data.get('type', '').lower() == 'chest':
                try:
                    chest_pos = tuple(map(float, item_data.get('pos', (300.0, 300.0))))
                    new_chest_obj = Chest(chest_pos[0], chest_pos[1])
                    if new_chest_obj._valid_init: game_elements["collectible_list"].append(new_chest_obj); game_elements["all_renderable_objects"].append(new_chest_obj); info(f"GSM Reset: Chest respawned at {chest_pos}.")
                    else: warning("GSM Reset: Chest failed to init.")
                    break 
                except Exception as e: error(f"GSM Reset: Error respawning chest: {e}", exc_info=True)
        game_elements["current_chest"] = new_chest_obj
    else:
        debug(f"GSM Reset: Dynamic entities not respawned for non-authoritative mode '{current_game_mode}'.")
        game_elements["current_chest"] = None

    # --- Camera Re-Initialization ---
    camera_instance = Camera(
        initial_level_width=game_elements.get("level_pixel_width", float(screen_width * 2.0)),
        initial_world_start_x=game_elements.get("level_min_x_absolute", 0.0),
        initial_world_start_y=game_elements.get("level_min_y_absolute", 0.0),
        initial_level_bottom_y_abs=game_elements.get("level_max_y_absolute", float(screen_height)),
        screen_width=float(screen_width), # Use current screen width
        screen_height=float(screen_height) # Use current screen height
    )
    game_elements["camera"] = camera_instance
    focus_target_cam = player1 if player1 and player1.alive() and player1._valid_init else \
                       (player2 if player2 and player2.alive() and player2._valid_init else \
                       (game_elements.get("player3") if game_elements.get("player3") and game_elements.get("player3").alive() and game_elements.get("player3")._valid_init else \
                       (game_elements.get("player4") if game_elements.get("player4") and game_elements.get("player4").alive() and game_elements.get("player4")._valid_init else None)))
    if focus_target_cam: camera_instance.update(focus_target_cam)
    else: camera_instance.static_update()
    game_elements["camera_level_dims_set"] = True
    debug("GSM Reset: Camera re-initialized and focused.")
    
    game_elements["game_ready_for_logic"] = True
    game_elements["initialization_in_progress"] = False

    info("GSM: --- Full Game State Reset Finished ---")
    return game_elements.get("current_chest")


# (get_network_game_state and set_network_game_state remain the same as version 2.1.3)
# ... (Copy those two functions here from the previous response) ...
projectile_class_map: Dict[str, type] = {
    "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
    "BloodShot": BloodShot, "IceShard": IceShard,
    "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
}
def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = {'p1': None, 'p2': None, 'p3':None, 'p4':None,'enemies': {}, 'chest': None, 'statues': [], 'projectiles': [], 'game_over': False, 'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name","unknown_map"))}
    for i in range(1,5):
        player = game_elements.get(f"player{i}")
        if player and hasattr(player, '_valid_init') and player._valid_init and hasattr(player, 'get_network_data'):
            state[f'p{i}'] = player.get_network_data()

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
    
    # Game over if ALL active players are truly gone
    any_player_active_and_not_gone = False
    for i in range(1,5):
        player = game_elements.get(f"player{i}")
        if player and player._valid_init: # Check if player instance exists and is valid
            if player.alive(): any_player_active_and_not_gone = True; break
            elif player.is_dead:
                if player.is_petrified and not player.is_stone_smashed: any_player_active_and_not_gone = True; break
                elif not player.death_animation_finished: any_player_active_and_not_gone = True; break
    state['game_over'] = not any_player_active_and_not_gone

    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]
    return state

def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None): # client_player_id helps client identify its own player
    
    new_all_renderables: List[Any] = []; current_all_renderables_set = set()
    def add_to_renderables_if_new(obj: Any):
        if obj is not None and obj not in current_all_renderables_set: new_all_renderables.append(obj); current_all_renderables_set.add(obj)
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []): add_to_renderables_if_new(static_item)

    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])
    
    for i in range(1, 5):
        player_key = f"player{i}"
        player_instance = game_elements.get(player_key)
        player_net_data = network_state_data.get(player_key)

        if player_net_data and isinstance(player_net_data, dict): # Server sent data for this player
            if not player_instance or not player_instance._valid_init : # Player doesn't exist or is invalid on client
                # Create new player instance on client based on server data and map defaults
                spawn_pos_data = player_net_data.get('pos', game_elements.get(f"player{i}_spawn_pos", (100.0 + i*50, C.GAME_HEIGHT - 100.0)))
                spawn_props_data = game_elements.get(f"player{i}_spawn_props", {}) # Get from game_elements (should be from map)
                
                player_instance = Player(float(spawn_pos_data[0]), float(spawn_pos_data[1]), player_id=i, initial_properties=spawn_props_data)
                game_elements[player_key] = player_instance
                debug(f"GSM Client: Created new Player {i} instance from network state.")
            
            if player_instance and hasattr(player_instance, 'set_network_data'):
                player_instance.set_network_data(player_net_data)
                is_renderable = player_instance._valid_init and (
                    player_instance.alive() or
                    (player_instance.is_dead and not player_instance.death_animation_finished and not player_instance.is_petrified) or
                    player_instance.is_petrified )
                if is_renderable: add_to_renderables_if_new(player_instance)
        elif player_instance and player_instance._valid_init: # Server did NOT send data for this player, assume it's gone/invalid
            if player_instance.alive() and hasattr(player_instance, 'kill'): player_instance.kill()
            game_elements[player_key] = None # Remove from active game elements if server doesn't include it
            debug(f"GSM Client: Player {i} not in network state, marked as None/killed.")


    new_enemy_list_client: List[Enemy] = []
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", []) # Use current client list for matching
    if 'enemies' in network_state_data and isinstance(network_state_data['enemies'], dict):
        received_enemy_data_map = network_state_data['enemies']; current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list_ref if hasattr(enemy, 'enemy_id')}
        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server."); continue
            client_enemy: Optional[Enemy] = None
            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map: client_enemy = current_client_enemies_map[enemy_id_str]
                else:
                    original_spawn_info = enemy_spawns_data_cache[enemy_id_int] if enemy_spawns_data_cache and 0 <= enemy_id_int < len(enemy_spawns_data_cache) else None
                    spawn_pos_e = enemy_data_server.get('pos', original_spawn_info.get('start_pos') if original_spawn_info else (100.0,100.0)); patrol_area_e: Optional[QRectF] = None
                    if original_spawn_info and 'patrol_rect_data' in original_spawn_info and isinstance(original_spawn_info['patrol_rect_data'], dict): pr_d = original_spawn_info['patrol_rect_data']; patrol_area_e = QRectF(float(pr_d.get('x',0)), float(pr_d.get('y',0)), float(pr_d.get('width',100)), float(pr_d.get('height',50)))
                    e_color = enemy_data_server.get('color_name', original_spawn_info.get('type') if original_spawn_info else 'enemy_green'); e_props = enemy_data_server.get('properties', original_spawn_info.get('properties', {}) if original_spawn_info else {})
                    client_enemy = Enemy(start_x=float(spawn_pos_e[0]), start_y=float(spawn_pos_e[1]), patrol_area=patrol_area_e, enemy_id=enemy_id_int, color_name=e_color, properties=e_props)
                if client_enemy and client_enemy._valid_init:
                    client_enemy.set_network_data(enemy_data_server); new_enemy_list_client.append(client_enemy)
                    if client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished and not client_enemy.is_petrified) or client_enemy.is_petrified: add_to_renderables_if_new(client_enemy)
    game_elements["enemy_list"] = new_enemy_list_client

    new_statue_list_client: List[Statue] = []
    statue_objects_list_client_ref: List[Statue] = game_elements.get("statue_objects", [])
    if 'statues' in network_state_data and isinstance(network_state_data['statues'], list):
        received_statue_data_list = network_state_data['statues']; current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client_ref if hasattr(s, 'statue_id')}
        for statue_data_server in received_statue_data_list:
            if not (isinstance(statue_data_server,dict) and 'id' in statue_data_server): continue
            statue_id_s = str(statue_data_server['id']); client_statue: Optional[Statue] = None
            if statue_data_server.get('_valid_init',False):
                if statue_id_s in current_client_statues_map: client_statue = current_client_statues_map[statue_id_s]
                else:
                    orig_s_info = next((s_inf for s_inf in statue_spawns_data_cache if s_inf.get('id') == statue_id_s),None)
                    s_pos = statue_data_server.get('pos', orig_s_info.get('pos') if orig_s_info else (200.0,200.0)); s_props = statue_data_server.get('properties', orig_s_info.get('properties',{}) if orig_s_info else {})
                    client_statue = Statue(float(s_pos[0]), float(s_pos[1]), statue_id=statue_id_s, properties=s_props)
                if client_statue and client_statue._valid_init:
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    new_statue_list_client.append(client_statue)
                    if client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True)): add_to_renderables_if_new(client_statue)
    game_elements["statue_objects"] = new_statue_list_client
    
    new_collectible_list_client: List[Any] = []; current_chest_obj_synced: Optional[Chest] = None
    current_chest_obj_client: Optional[Chest] = game_elements.get("current_chest")
    chest_data_from_server = network_state_data.get('chest')
    if chest_data_from_server and isinstance(chest_data_from_server, dict) and chest_data_from_server.get('_alive', True):
        if not current_chest_obj_client or not current_chest_obj_client._valid_init:
            chest_pos = chest_data_from_server.get('pos_midbottom', (300.0,300.0))
            current_chest_obj_client = Chest(x=float(chest_pos[0]), y=float(chest_pos[1])); game_elements["current_chest"] = current_chest_obj_client
        if current_chest_obj_client and current_chest_obj_client._valid_init:
            if hasattr(current_chest_obj_client, 'set_network_data'): current_chest_obj_client.set_network_data(chest_data_from_server)
            current_chest_obj_synced = current_chest_obj_client
            if current_chest_obj_synced.alive() or current_chest_obj_synced.state in ['opening', 'opened_visible', 'fading']: add_to_renderables_if_new(current_chest_obj_synced)
    game_elements["current_chest"] = current_chest_obj_synced
    if current_chest_obj_synced: new_collectible_list_client.append(current_chest_obj_synced)
    game_elements["collectible_list"] = new_collectible_list_client

    new_projectiles_list_client: List[Any] = []
    projectiles_list_ref: List[Any] = game_elements.get("projectiles_list", [])
    if 'projectiles' in network_state_data and isinstance(network_state_data['projectiles'], list):
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list_ref if hasattr(p, 'projectile_id')}
        for proj_data_server in network_state_data['projectiles']:
            if not (isinstance(proj_data_server, dict) and 'id' in proj_data_server): continue
            proj_id_s = str(proj_data_server['id']); client_proj: Optional[Any] = None
            if proj_id_s in current_client_proj_map: client_proj = current_client_proj_map[proj_id_s]
            else:
                owner_inst: Optional[Player] = None; owner_id_net = proj_data_server.get('owner_id')
                # Determine owner instance based on owner_id_net and existing player instances
                for i_p in range(1,5):
                    p_inst_check = game_elements.get(f"player{i_p}")
                    if p_inst_check and p_inst_check.player_id == owner_id_net: owner_inst = p_inst_check; break
                
                if owner_inst and all(k in proj_data_server for k in ['pos','vel','type']):
                    ProjClass = projectile_class_map.get(proj_data_server['type'])
                    if ProjClass:
                        pos_d, vel_d = proj_data_server['pos'], proj_data_server['vel']; dir_qpf = QPointF(float(vel_d[0]), float(vel_d[1]))
                        client_proj = ProjClass(float(pos_d[0]),float(pos_d[1]), dir_qpf, owner_inst)
                        client_proj.projectile_id = proj_id_s; client_proj.game_elements_ref = game_elements
            if client_proj:
                if hasattr(client_proj,'set_network_data'): client_proj.set_network_data(proj_data_server)
                if client_proj.alive(): new_projectiles_list_client.append(client_proj); add_to_renderables_if_new(client_proj)
    game_elements["projectiles_list"] = new_projectiles_list_client

    game_elements["all_renderable_objects"] = new_all_renderables
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)
    server_map_name = network_state_data.get('map_name')
    camera_instance: Optional[Camera] = game_elements.get('camera')
    if server_map_name and camera_instance and (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set', False)):
        client_level_data = game_elements.get('level_data')
        if client_level_data and isinstance(client_level_data, dict) and game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2)); cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0)); cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y); game_elements['camera_level_dims_set'] = True
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
    debug(f"GSM Client set_network_game_state END: Renderables: {len(game_elements['all_renderable_objects'])}")