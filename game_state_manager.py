# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.0.5 (Refined reset logic for dynamic entities, fixed QRectF import)
# version 2.0.6 (Ensure level_data is passed to enemy/statue respawn, added more debug for chest reset)
# version 2.0.7 (Preserve level_data during reset, rely on _initialize_game_entities for loading it)
# version 2.0.8 (Removed self-import of reset_game_state)
# version 2.0.9 (Corrected game mode check for entity respawn)
import os
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import QRectF, QPointF
# Game-specific imports
# from game_setup import spawn_chest_qt # spawn_chest_qt is deprecated for random spawns
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


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    info("GSM: --- Resetting Game State (PySide6) ---")
    debug(f"GSM: game_elements at START of reset_game_state: Keys={list(game_elements.keys())}")
    
    level_data_for_reset = game_elements.get("level_data")
    enemy_spawns_cache = game_elements.get("enemy_spawns_data_cache")
    statue_spawns_cache = game_elements.get("statue_spawns_data_cache")
    map_name_cache = game_elements.get("map_name")
    loaded_map_name_cache = game_elements.get("loaded_map_name")
    platforms_list_cache = game_elements.get("platforms_list")
    ladders_list_cache = game_elements.get("ladders_list")
    hazards_list_cache = game_elements.get("hazards_list")
    background_tiles_list_cache = game_elements.get("background_tiles_list")
    player1_spawn_pos_cache = game_elements.get("player1_spawn_pos")
    player1_spawn_props_cache = game_elements.get("player1_spawn_props")
    player2_spawn_pos_cache = game_elements.get("player2_spawn_pos")
    player2_spawn_props_cache = game_elements.get("player2_spawn_props")
    level_pixel_width_cache = game_elements.get("level_pixel_width")
    level_min_x_abs_cache = game_elements.get("level_min_x_absolute")
    level_min_y_abs_cache = game_elements.get("level_min_y_absolute")
    level_max_y_abs_cache = game_elements.get("level_max_y_absolute")
    ground_level_y_ref_cache = game_elements.get("ground_level_y_ref")
    ground_platform_height_ref_cache = game_elements.get("ground_platform_height_ref")
    level_background_color_cache = game_elements.get("level_background_color")

    game_elements["enemy_list"] = []
    game_elements["statue_objects"] = []
    game_elements["projectiles_list"] = []
    game_elements["collectible_list"] = []
    game_elements["all_renderable_objects"] = []

    if platforms_list_cache: game_elements["all_renderable_objects"].extend(platforms_list_cache)
    if ladders_list_cache: game_elements["all_renderable_objects"].extend(ladders_list_cache)
    if hazards_list_cache: game_elements["all_renderable_objects"].extend(hazards_list_cache)
    if background_tiles_list_cache: game_elements["all_renderable_objects"].extend(background_tiles_list_cache)

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")

    if player1 and hasattr(player1, 'reset_state'):
        debug(f"GSM: Resetting P1 at {player1_spawn_pos_cache if player1_spawn_pos_cache else 'initial spawn'} with props: {player1_spawn_props_cache}")
        player1.reset_state(player1_spawn_pos_cache)
        if player1._valid_init and player1.alive():
            game_elements["all_renderable_objects"].append(player1)
        debug("GSM: P1 Reset complete.")

    if player2 and hasattr(player2, 'reset_state'):
        debug(f"GSM: Resetting P2 at {player2_spawn_pos_cache if player2_spawn_pos_cache else 'initial spawn'} with props: {player2_spawn_props_cache}")
        player2.reset_state(player2_spawn_pos_cache)
        if player2._valid_init and player2.alive():
            game_elements["all_renderable_objects"].append(player2)
        debug("GSM: P2 Reset complete.")

    current_game_mode = game_elements.get("current_game_mode", "unknown")
    
    # MODIFIED Condition: Changed the list of game modes where dynamic entities are respawned.
    # "host_game" is an initial setup mode. The active modes where reset occurs are "host_waiting" (host alone)
    # or "host_active" (host + client). "couch_play" is for local co-op.
    server_authoritative_modes = ["couch_play", "host_waiting", "host_active"]
    debug(f"GSM: Current game mode for entity respawn check: '{current_game_mode}'. Authoritative modes: {server_authoritative_modes}")

    if current_game_mode in server_authoritative_modes:
        debug(f"GSM: Respawning dynamic entities for authoritative mode '{current_game_mode}'.")
        if enemy_spawns_cache:
            debug(f"GSM: Respawning {len(enemy_spawns_cache)} enemies from cache.")
            for i, spawn_info in enumerate(enemy_spawns_cache):
                try:
                    patrol_raw = spawn_info.get('patrol_rect_data')
                    patrol_qrectf: Optional[QRectF] = None
                    if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                        patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']),
                                               float(patrol_raw['width']), float(patrol_raw['height']))
                    enemy_color_name_from_map = str(spawn_info.get('type', 'enemy_green'))
                    start_pos_tuple_enemy = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))
                    new_enemy_instance = Enemy(start_x=start_pos_tuple_enemy[0], start_y=start_pos_tuple_enemy[1],
                                               patrol_area=patrol_qrectf, enemy_id=i,
                                               color_name=enemy_color_name_from_map,
                                               properties=spawn_info.get('properties', {}))
                    if new_enemy_instance._valid_init and new_enemy_instance.alive():
                        game_elements["enemy_list"].append(new_enemy_instance)
                        game_elements["all_renderable_objects"].append(new_enemy_instance)
                except Exception as e_respawn: error(f"GSM: Error respawning enemy {i} from cache: {e_respawn}", exc_info=True)

        if statue_spawns_cache:
            debug(f"GSM: Respawning {len(statue_spawns_cache)} statues from cache.")
            for i, statue_data in enumerate(statue_spawns_cache):
                try:
                    s_id = statue_data.get('id', f"map_statue_reset_{i}")
                    s_pos_x, s_pos_y = float(statue_data['pos'][0]), float(statue_data['pos'][1])
                    new_statue = Statue(s_pos_x, s_pos_y, statue_id=s_id, properties=statue_data.get('properties', {}))
                    if new_statue._valid_init and new_statue.alive():
                        game_elements["statue_objects"].append(new_statue)
                        game_elements["all_renderable_objects"].append(new_statue)
                except Exception as e_stat_respawn: error(f"GSM: Error respawning statue {i} from cache: {e_stat_respawn}", exc_info=True)
        
        new_chest_obj: Optional[Chest] = None
        map_items_data_for_reset = []
        if level_data_for_reset and isinstance(level_data_for_reset, dict):
            map_items_data_for_reset = level_data_for_reset.get("items_list", [])
            debug(f"GSM: items_list from (preserved) level_data for chest reset: {map_items_data_for_reset}")
            if not map_items_data_for_reset:
                 debug("GSM: 'items_list' is empty or not found in level_data during reset.")
        elif not level_data_for_reset:
             error("GSM: Preserved 'level_data' is missing during reset. Cannot respawn chest from map definition.")

        if map_items_data_for_reset:
            for item_data in map_items_data_for_reset:
                if item_data.get('type', '').lower() == 'chest':
                    try:
                        chest_midbottom_x, chest_midbottom_y = float(item_data['pos'][0]), float(item_data['pos'][1])
                        new_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y)
                        if new_chest_obj._valid_init:
                            game_elements["collectible_list"].append(new_chest_obj)
                            game_elements["all_renderable_objects"].append(new_chest_obj)
                            debug(f"GSM: Chest respawned from map data at ({chest_midbottom_x},{chest_midbottom_y}). Added to lists.")
                        else:
                            debug("GSM: Map-defined chest failed to init on reset.")
                        break 
                    except Exception as e_chest_map: error(f"GSM: Error respawning chest from map data: {e_chest_map}", exc_info=True)
        else:
            debug("GSM: No chest data in map_items_data (or level_data was missing). No chest will be respawned for authoritative mode.")
        game_elements["current_chest"] = new_chest_obj
    else:
        debug(f"GSM: Dynamic entities (enemies, statues, chest) not respawned for mode '{current_game_mode}'.")
        game_elements["current_chest"] = None # Ensure chest is None if not in authoritative mode

    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset'):
        camera.set_offset(0.0, 0.0)
        if player1 and player1.alive() and player1._valid_init: camera.update(player1)
        elif player2 and player2.alive() and player2._valid_init: camera.update(player2)
        else: camera.static_update()
    debug("GSM: Camera position reset/re-evaluated.")
    
    if level_data_for_reset is not None: game_elements["level_data"] = level_data_for_reset
    if enemy_spawns_cache is not None: game_elements["enemy_spawns_data_cache"] = enemy_spawns_cache
    if statue_spawns_cache is not None: game_elements["statue_spawns_data_cache"] = statue_spawns_cache
    if map_name_cache is not None: game_elements["map_name"] = map_name_cache
    if loaded_map_name_cache is not None: game_elements["loaded_map_name"] = loaded_map_name_cache
    if player1_spawn_pos_cache is not None: game_elements["player1_spawn_pos"] = player1_spawn_pos_cache
    if player1_spawn_props_cache is not None: game_elements["player1_spawn_props"] = player1_spawn_props_cache
    if player2_spawn_pos_cache is not None: game_elements["player2_spawn_pos"] = player2_spawn_pos_cache
    if player2_spawn_props_cache is not None: game_elements["player2_spawn_props"] = player2_spawn_props_cache
    if level_pixel_width_cache is not None: game_elements["level_pixel_width"] = level_pixel_width_cache
    if level_min_x_abs_cache is not None: game_elements["level_min_x_absolute"] = level_min_x_abs_cache
    if level_min_y_abs_cache is not None: game_elements["level_min_y_absolute"] = level_min_y_abs_cache
    if level_max_y_abs_cache is not None: game_elements["level_max_y_absolute"] = level_max_y_abs_cache
    if ground_level_y_ref_cache is not None: game_elements["ground_level_y_ref"] = ground_level_y_ref_cache
    if ground_platform_height_ref_cache is not None: game_elements["ground_platform_height_ref"] = ground_platform_height_ref_cache
    if level_background_color_cache is not None: game_elements["level_background_color"] = level_background_color_cache

    debug(f"GSM END: current_chest is now: {'None' if game_elements.get('current_chest') is None else type(game_elements.get('current_chest'))}. Collectibles count: {len(game_elements['collectible_list'])}. Renderables count: {len(game_elements['all_renderable_objects'])}")
    if 'level_data' in game_elements and game_elements['level_data'] is not None:
        debug(f"GSM: 'level_data' IS PRESENT at END of reset. Items: {game_elements['level_data'].get('items_list', 'N/A') if isinstance(game_elements['level_data'], dict) else 'Not a dict'}")
    else:
        error("GSM: CRITICAL - 'level_data' is MISSING at END of reset.")

    info("GSM: --- Game State Reset Finished (PySide6) ---")
    return game_elements.get("current_chest")


projectile_class_map: Dict[str, type] = {
    "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
    "BloodShot": BloodShot, "IceShard": IceShard,
    "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
}

def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'enemies': {}, 'chest': None,
        'statues': [], 'projectiles': [], 'game_over': False,
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name","unknown_map"))
    }
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_list: List[Statue] = game_elements.get("statue_objects", [])
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])

    if player1 and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()

    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            if enemy.alive() or \
               (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
               getattr(enemy, 'is_petrified', False):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    for s_obj in statue_list:
        if (hasattr(s_obj, 'alive') and s_obj.alive()) or \
           (getattr(s_obj, 'is_smashed', False) and not getattr(s_obj, 'death_animation_finished', True)):
            if hasattr(s_obj, 'get_network_data'):
                state['statues'].append(s_obj.get_network_data())

    if current_chest and hasattr(current_chest, 'rect'):
        if current_chest.alive() or current_chest.state in ['opening', 'opened', 'fading']:
            state['chest'] = current_chest.get_network_data()
        else: state['chest'] = None
    else: state['chest'] = None

    p1_truly_gone = True
    if player1 and player1._valid_init:
        if player1.alive():
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False):
                    p1_truly_gone = False
                elif not getattr(player1, 'death_animation_finished', True):
                    p1_truly_gone = False
            else:
                p1_truly_gone = False
    state['game_over'] = p1_truly_gone

    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]
    return state


def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None):
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client_ref: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")
    all_renderable_objects_ref: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list_ref: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", [])
    
    new_all_renderables: List[Any] = []
    current_all_renderables_set = set()

    def add_to_renderables(obj: Any):
        if obj not in current_all_renderables_set:
            new_all_renderables.append(obj)
            current_all_renderables_set.add(obj)

    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []):
            add_to_renderables(static_item)

    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    if not enemy_spawns_data_cache and game_elements.get("level_data"):
        enemy_spawns_data_cache = game_elements["level_data"].get('enemies_list', [])
        game_elements["enemy_spawns_data_cache"] = enemy_spawns_data_cache
    
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])
    if not statue_spawns_data_cache and game_elements.get("level_data"):
        statue_spawns_data_cache = game_elements["level_data"].get('statues_list', [])
        game_elements["statue_spawns_data_cache"] = statue_spawns_data_cache

    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        is_p1_renderable = player1._valid_init and (player1.alive() or (player1.is_dead and not player1.death_animation_finished) or player1.is_petrified)
        if is_p1_renderable: add_to_renderables(player1)

    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        is_p2_renderable = player2._valid_init and (player2.alive() or (player2.is_dead and not player2.death_animation_finished) or player2.is_petrified)
        if is_p2_renderable: add_to_renderables(player2)

    new_enemy_list_client: List[Enemy] = []
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list_ref if hasattr(enemy, 'enemy_id')}
        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server."); continue
            client_enemy: Optional[Enemy] = None
            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map: client_enemy = current_client_enemies_map[enemy_id_str]
                else:
                    original_spawn_info: Optional[Dict[str,Any]] = None
                    if enemy_spawns_data_cache and enemy_id_int < len(enemy_spawns_data_cache): original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                    spawn_pos_e_default = enemy_data_server.get('pos', (100.0,100.0))
                    if original_spawn_info and 'start_pos' in original_spawn_info: spawn_pos_e_default = tuple(map(float, original_spawn_info['start_pos']))
                    patrol_area_e_obj: Optional[QRectF] = None
                    if original_spawn_info and 'patrol_rect_data' in original_spawn_info:
                        pr_data = original_spawn_info['patrol_rect_data']
                        if isinstance(pr_data, dict): patrol_area_e_obj = QRectF(float(pr_data.get('x',0)), float(pr_data.get('y',0)), float(pr_data.get('width',100)), float(pr_data.get('height',50)))
                    enemy_color_name = enemy_data_server.get('color_name', original_spawn_info.get('type') if original_spawn_info else 'enemy_green')
                    enemy_props = enemy_data_server.get('properties', original_spawn_info.get('properties', {}) if original_spawn_info else {})
                    client_enemy = Enemy(start_x=spawn_pos_e_default[0], start_y=spawn_pos_e_default[1], patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int, color_name=enemy_color_name, properties=enemy_props)
                if client_enemy and client_enemy._valid_init:
                    client_enemy.set_network_data(enemy_data_server)
                    new_enemy_list_client.append(client_enemy)
                    is_enemy_renderable = client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished) or client_enemy.is_petrified
                    if is_enemy_renderable: add_to_renderables(client_enemy)
                elif client_enemy and not client_enemy._valid_init: error(f"GSM Client: Failed to init/update enemy {enemy_id_str} from server data.")
    game_elements["enemy_list"] = new_enemy_list_client

    new_statue_list_client: List[Statue] = []
    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if isinstance(s_data, dict) and 'id' in s_data}
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client_ref if hasattr(s, 'statue_id')}
        for statue_id_server_str, statue_data_server in received_statue_data_map.items():
            client_statue: Optional[Statue] = None
            if statue_data_server.get('_valid_init', False):
                if statue_id_server_str in current_client_statues_map: client_statue = current_client_statues_map[statue_id_server_str]
                else:
                    original_statue_spawn_info: Optional[Dict[str,Any]] = next((s_info for s_info in statue_spawns_data_cache if s_info.get('id') == statue_id_server_str), None)
                    s_pos_data = statue_data_server.get('pos', original_statue_spawn_info.get('pos') if original_statue_spawn_info else (200.0, 200.0))
                    s_props = statue_data_server.get('properties', original_statue_spawn_info.get('properties', {}) if original_statue_spawn_info else {})
                    client_statue = Statue(center_x=float(s_pos_data[0]), center_y=float(s_pos_data[1]), statue_id=statue_id_server_str, properties=s_props)
                if client_statue and client_statue._valid_init:
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    new_statue_list_client.append(client_statue)
                    is_statue_renderable = client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True))
                    if is_statue_renderable: add_to_renderables(client_statue)
                elif client_statue and not client_statue._valid_init: error(f"GSM Client: Failed to init/update statue {statue_id_server_str} from server data.")
    game_elements["statue_objects"] = new_statue_list_client

    new_collectible_list_client: List[Any] = []
    current_chest_obj_synced: Optional[Chest] = None
    if 'chest' in network_state_data:
        chest_data_server = network_state_data['chest']
        if chest_data_server and isinstance(chest_data_server, dict) and chest_data_server.get('_alive', True):
            if not current_chest_obj or not current_chest_obj._valid_init:
                chest_pos_midbottom = chest_data_server.get('pos_midbottom', (300.0, 300.0))
                current_chest_obj = Chest(x=float(chest_pos_midbottom[0]), y=float(chest_pos_midbottom[1]))
            if current_chest_obj._valid_init:
                if hasattr(current_chest_obj, 'set_network_data'): current_chest_obj.set_network_data(chest_data_server)
                current_chest_obj_synced = current_chest_obj
                is_chest_renderable = current_chest_obj.alive() or current_chest_obj.state in ['opening', 'opened', 'fading']
                if is_chest_renderable: add_to_renderables(current_chest_obj)
            else: current_chest_obj_synced = None
    game_elements["current_chest"] = current_chest_obj_synced
    if current_chest_obj_synced: new_collectible_list_client.append(current_chest_obj_synced)
    game_elements["collectible_list"] = new_collectible_list_client

    new_projectiles_list_client: List[Any] = []
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if isinstance(p_data,dict) and 'id' in p_data}
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list_ref if hasattr(p, 'projectile_id')}
        for proj_id_server_str, proj_data_server in received_proj_data_map.items():
            client_proj: Optional[Any] = None
            if proj_id_server_str in current_client_proj_map: client_proj = current_client_proj_map[proj_id_server_str]
            else:
                owner_instance_client: Optional[Player] = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server == 1 and player1: owner_instance_client = player1
                elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server and 'type' in proj_data_server:
                    proj_type_name = proj_data_server['type']
                    ProjClass = projectile_class_map.get(proj_type_name)
                    if ProjClass:
                        net_vel_data = proj_data_server['vel']
                        direction_qpointf = QPointF(float(net_vel_data[0]), float(net_vel_data[1]))
                        pos_data = proj_data_server['pos']
                        client_proj = ProjClass(float(pos_data[0]), float(pos_data[1]), direction_qpointf, owner_instance_client)
                        client_proj.projectile_id = proj_id_server_str
                        client_proj.game_elements_ref = game_elements
                    else: warning(f"GSM Client: Unknown projectile type '{proj_type_name}' from server.")
                elif not owner_instance_client: warning(f"GSM Client: Owner P{owner_id_from_server} for projectile {proj_id_server_str} not found.")
                else: warning(f"GSM Client: Insufficient data for new projectile {proj_id_server_str}.")
            if client_proj:
                if hasattr(client_proj, 'set_network_data'): client_proj.set_network_data(proj_data_server)
                if client_proj.alive():
                    new_projectiles_list_client.append(client_proj)
                    add_to_renderables(client_proj)
    game_elements["projectiles_list"] = new_projectiles_list_client

    game_elements["all_renderable_objects"] = new_all_renderables
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)

    server_map_name = network_state_data.get('map_name')
    camera_instance = game_elements.get('camera')
    if server_map_name and camera_instance and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set')):
        client_level_data = game_elements.get('level_data')
        if client_level_data and game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
        elif client_level_data and game_elements.get('loaded_map_name') != server_map_name:
            warning(f"GSM Client: Map name mismatch ({game_elements.get('loaded_map_name')} vs {server_map_name}). Camera dimensions will be set after new map load.")