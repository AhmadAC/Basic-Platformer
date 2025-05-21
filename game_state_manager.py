# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.0.5 (Refined reset logic for dynamic entities, fixed QRectF import)
# version 2.0.6 (Ensure level_data is passed to enemy/statue respawn, added more debug for chest reset)
import os
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import QRectF, QPointF # Import QRectF and QPointF
# Game-specific imports
# from game_setup import spawn_chest_qt # spawn_chest_qt is deprecated for random spawns
from enemy import Enemy
from items import Chest
from statue import Statue
from player import Player
from tiles import Platform, Ladder, Lava, BackgroundTile # Added BackgroundTile
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
    """
    Resets the game state.
    Static elements (platforms, ladders, hazards, background_tiles) are assumed to be persistent
    and correctly loaded by _initialize_game_entities. They are re-added to all_renderable_objects.
    Dynamic elements (players, enemies, projectiles, statues, chests) are reset or re-created.
    Relies on 'level_data' being present in game_elements for respawning map-defined entities.
    """
    info("GSM: --- Resetting Game State (PySide6) ---")

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    level_data_for_reset = game_elements.get("level_data") # Crucial for respawning

    if not level_data_for_reset or not isinstance(level_data_for_reset, dict):
        error("GSM: CRITICAL - 'level_data' is missing or not a dict in game_elements. Cannot properly reset map-defined entities.")
        # Proceed with player reset if possible, but other entities might not respawn.
    else:
        debug(f"GSM: Resetting with level_data. Keys: {list(level_data_for_reset.keys())}")


    # --- Prepare the new all_renderable_objects list ---
    all_renderable_objects_accumulator: List[Any] = []
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        static_list = game_elements.get(static_list_key)
        if isinstance(static_list, list):
            all_renderable_objects_accumulator.extend(static_list)
        elif static_list is not None:
            warning(f"GSM: Expected list for '{static_list_key}' but got {type(static_list)}. Skipping for renderables.")


    # Reset Player 1
    player1_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player1_spawn_pos")
    if player1 and hasattr(player1, 'reset_state'):
        p1_spawn_props = game_elements.get("player1_spawn_props", {}) # Get props for reset if needed
        debug(f"GSM: Resetting P1 at {player1_spawn_pos_tuple if player1_spawn_pos_tuple else 'initial spawn (from player object)'} with props: {p1_spawn_props}")
        player1.reset_state(player1_spawn_pos_tuple) # Player's reset_state should handle its own props if necessary
        if player1._valid_init and player1.alive():
            all_renderable_objects_accumulator.append(player1)
        debug("GSM: P1 Reset complete.")

    # Reset Player 2
    player2_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player2_spawn_pos")
    if player2 and hasattr(player2, 'reset_state'):
        p2_spawn_props = game_elements.get("player2_spawn_props", {})
        debug(f"GSM: Resetting P2 at {player2_spawn_pos_tuple if player2_spawn_pos_tuple else 'initial spawn (from player object)'} with props: {p2_spawn_props}")
        player2.reset_state(player2_spawn_pos_tuple)
        if player2._valid_init and player2.alive():
            all_renderable_objects_accumulator.append(player2)
        debug("GSM: P2 Reset complete.")

    # Reset/Re-spawn Enemies
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", [])
    enemy_list_ref.clear()
    # Use enemy_spawns_data_cache if available, otherwise try to get from level_data directly
    enemy_spawns_data_for_reset = game_elements.get("enemy_spawns_data_cache")
    if not enemy_spawns_data_for_reset and level_data_for_reset:
        enemy_spawns_data_for_reset = level_data_for_reset.get('enemies_list', [])
        game_elements["enemy_spawns_data_cache"] = enemy_spawns_data_for_reset # Cache it if freshly read

    current_game_mode = game_elements.get("current_game_mode", "unknown")

    if (current_game_mode in ["host", "couch_play", "host_game"]) and enemy_spawns_data_for_reset:
        debug(f"GSM: Respawning {len(enemy_spawns_data_for_reset)} enemies from data for {current_game_mode} mode.")
        for i, spawn_info in enumerate(enemy_spawns_data_for_reset):
            try:
                patrol_raw = spawn_info.get('patrol_rect_data')
                patrol_qrectf: Optional[QRectF] = None
                if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                    patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']),
                                           float(patrol_raw['width']), float(patrol_raw['height']))

                enemy_color_name_from_map = str(spawn_info.get('type', 'enemy_green'))
                start_pos_tuple_enemy = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))

                new_enemy_instance = Enemy(start_x=start_pos_tuple_enemy[0],
                                           start_y=start_pos_tuple_enemy[1],
                                           patrol_area=patrol_qrectf,
                                           enemy_id=i,
                                           color_name=enemy_color_name_from_map,
                                           properties=spawn_info.get('properties', {}))
                if new_enemy_instance._valid_init and new_enemy_instance.alive():
                    enemy_list_ref.append(new_enemy_instance)
                    all_renderable_objects_accumulator.append(new_enemy_instance)
            except Exception as e_respawn:
                error(f"GSM: Error respawning enemy {i} from data: {e_respawn}", exc_info=True)

    # Reset/Re-spawn Statues
    statue_objects_list_ref: List[Statue] = game_elements.get("statue_objects", [])
    statue_objects_list_ref.clear()
    statue_spawns_data_for_reset = game_elements.get("statue_spawns_data_cache")
    if not statue_spawns_data_for_reset and level_data_for_reset:
        statue_spawns_data_for_reset = level_data_for_reset.get('statues_list', [])
        game_elements["statue_spawns_data_cache"] = statue_spawns_data_for_reset

    if (current_game_mode in ["host", "couch_play", "host_game"]) and statue_spawns_data_for_reset:
        for i, statue_data in enumerate(statue_spawns_data_for_reset):
            try:
                s_id = statue_data.get('id', f"map_statue_reset_{i}")
                s_pos_x, s_pos_y = float(statue_data['pos'][0]), float(statue_data['pos'][1])
                new_statue = Statue(s_pos_x, s_pos_y, statue_id=s_id, properties=statue_data.get('properties', {}))
                if new_statue._valid_init and new_statue.alive():
                    statue_objects_list_ref.append(new_statue)
                    all_renderable_objects_accumulator.append(new_statue)
            except Exception as e_stat_respawn: error(f"GSM: Error respawning statue {i} from data: {e_stat_respawn}", exc_info=True)
    debug(f"GSM: Statues processed for reset. New count: {len(statue_objects_list_ref)}.")

    # Clear Projectiles
    projectiles_list_ref: List[Any] = game_elements.get("projectiles_list", [])
    projectiles_list_ref.clear()
    debug("GSM: Projectiles list cleared.")

    # Reset/Re-spawn Chest
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", [])
    collectible_list_ref.clear()

    new_chest_obj: Optional[Chest] = None
    map_items_data_for_reset = []
    if level_data_for_reset:
        map_items_data_for_reset = level_data_for_reset.get("items_list", [])
        debug(f"GSM: items_list from level_data for chest reset: {map_items_data_for_reset}")
    else:
        debug("GSM: level_data missing, cannot check map_items_data for chest reset.")


    if (current_game_mode in ["host", "couch_play", "host_game"]) and map_items_data_for_reset:
        for item_data in map_items_data_for_reset:
            if item_data.get('type', '').lower() == 'chest':
                try:
                    chest_midbottom_x, chest_midbottom_y = float(item_data['pos'][0]), float(item_data['pos'][1])
                    new_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y)
                    if new_chest_obj._valid_init:
                        collectible_list_ref.append(new_chest_obj)
                        all_renderable_objects_accumulator.append(new_chest_obj)
                        debug(f"GSM: Chest respawned from map data at ({chest_midbottom_x},{chest_midbottom_y}).")
                    else: debug("GSM: Map-defined chest failed to init on reset.")
                    break
                except Exception as e_chest_map: error(f"GSM: Error respawning chest from map data: {e_chest_map}", exc_info=True)
    elif current_game_mode in ["host", "couch_play", "host_game"]:
        debug("GSM: No chest data in map_items_data. No chest will be respawned from map definition.")


    # Fallback random chest spawn (if enabled and no chest from map)
    # This logic is usually deprecated if maps define chests.
    # if not new_chest_obj and getattr(C, 'ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP', False) and \
    #    (current_game_mode in ["host", "couch_play", "host_game"]):
    #     ground_y_for_chest = game_elements.get("ground_level_y_ref", float(C.GAME_HEIGHT - C.TILE_SIZE))
    #     new_chest_obj = spawn_chest_qt(game_elements.get("platforms_list", []), ground_y_for_chest) # spawn_chest_qt is deprecated
    #     if new_chest_obj and new_chest_obj._valid_init:
    #         collectible_list_ref.append(new_chest_obj)
    #         all_renderable_objects_accumulator.append(new_chest_obj)
    #         debug("GSM: Random chest respawned (fallback).")
    #     else: debug("GSM: Failed to respawn random chest (fallback).")

    game_elements["current_chest"] = new_chest_obj

    # Camera reset
    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset'):
        camera.set_offset(0.0, 0.0) # Reset camera offset
        # Re-focus camera on player if available
        if player1 and player1.alive() and player1._valid_init: camera.update(player1)
        elif player2 and player2.alive() and player2._valid_init: camera.update(player2)
        else: camera.static_update() # Fallback if no player is active
    debug("GSM: Camera position reset/re-evaluated.")

    # Assign the newly built list of all renderable objects
    game_elements["all_renderable_objects"] = all_renderable_objects_accumulator

    info("GSM: --- Game State Reset Finished (PySide6) ---")
    return new_chest_obj


# Define the projectile class map for set_network_game_state
projectile_class_map: Dict[str, type] = {
    "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
    "BloodShot": BloodShot, "IceShard": IceShard,
    "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
}

def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes the current game state for network transmission."""
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'enemies': {}, 'chest': None,
        'statues': [], 'projectiles': [], 'game_over': False,
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name","unknown_map"))
    }
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_list: List[Statue] = game_elements.get("statue_objects", []) # Corrected key
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])

    if player1 and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()

    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            # Send data if enemy is alive, or dead but animation not finished, or petrified
            if enemy.alive() or \
               (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
               getattr(enemy, 'is_petrified', False):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    for s_obj in statue_list: # Use statue_list
        if (hasattr(s_obj, 'alive') and s_obj.alive()) or \
           (getattr(s_obj, 'is_smashed', False) and not getattr(s_obj, 'death_animation_finished', True)):
            if hasattr(s_obj, 'get_network_data'):
                state['statues'].append(s_obj.get_network_data())

    if current_chest and hasattr(current_chest, 'rect'): # Check if chest object exists and is valid
        if current_chest.alive() or current_chest.state in ['opening', 'opened', 'fading']: # Send if active
            state['chest'] = current_chest.get_network_data()
        else: state['chest'] = None # Not active, send None
    else: state['chest'] = None # No chest object, send None

    # Determine game_over based on P1 state for server logic (can be adapted)
    p1_truly_gone = True
    if player1 and player1._valid_init:
        if player1.alive(): # Player.alive() checks internal _alive flag
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False):
                    p1_truly_gone = False # Petrified but not smashed is still "on screen"
                elif not getattr(player1, 'death_animation_finished', True):
                    p1_truly_gone = False # Death animation still playing
            else: # Not dead
                p1_truly_gone = False
    state['game_over'] = p1_truly_gone # For server, P1 (host) defeat might mean game over

    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]

    return state


def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None):
    """
    Updates the local game state based on data received from the server.
    """
    # Player class is used for type checking, but instances are from game_elements
    # from player import Player
    # from enemy import Enemy
    # from statue import Statue
    # from items import Chest

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client_ref: List[Statue] = game_elements.get("statue_objects", []) # Corrected key
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
    
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", []) # Corrected key
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

    # Enemy data
    new_enemy_list_client: List[Enemy] = []
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list_ref if hasattr(enemy, 'enemy_id')}

        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server."); continue
            
            client_enemy: Optional[Enemy] = None

            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map:
                    client_enemy = current_client_enemies_map[enemy_id_str]
                else: # Create new enemy instance on client
                    original_spawn_info: Optional[Dict[str,Any]] = None
                    if enemy_spawns_data_cache and enemy_id_int < len(enemy_spawns_data_cache):
                        original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                    
                    spawn_pos_e_default = enemy_data_server.get('pos', (100.0,100.0)) # Fallback
                    if original_spawn_info and 'start_pos' in original_spawn_info:
                        spawn_pos_e_default = tuple(map(float, original_spawn_info['start_pos']))

                    patrol_area_e_obj: Optional[QRectF] = None
                    if original_spawn_info and 'patrol_rect_data' in original_spawn_info:
                        pr_data = original_spawn_info['patrol_rect_data']
                        if isinstance(pr_data, dict):
                             patrol_area_e_obj = QRectF(float(pr_data.get('x',0)), float(pr_data.get('y',0)),
                                                       float(pr_data.get('width',100)), float(pr_data.get('height',50)))
                    
                    enemy_color_name = enemy_data_server.get('color_name', original_spawn_info.get('type') if original_spawn_info else 'enemy_green')
                    enemy_props = enemy_data_server.get('properties', original_spawn_info.get('properties', {}) if original_spawn_info else {})

                    client_enemy = Enemy(start_x=spawn_pos_e_default[0], start_y=spawn_pos_e_default[1],
                                         patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int,
                                         color_name=enemy_color_name, properties=enemy_props)
                
                if client_enemy and client_enemy._valid_init:
                    client_enemy.set_network_data(enemy_data_server)
                    new_enemy_list_client.append(client_enemy)
                    is_enemy_renderable = client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished) or client_enemy.is_petrified
                    if is_enemy_renderable: add_to_renderables(client_enemy)
                elif client_enemy and not client_enemy._valid_init:
                     error(f"GSM Client: Failed to init/update enemy {enemy_id_str} from server data.")

    game_elements["enemy_list"] = new_enemy_list_client

    # Statue data
    new_statue_list_client: List[Statue] = []
    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if isinstance(s_data, dict) and 'id' in s_data}
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client_ref if hasattr(s, 'statue_id')}

        for statue_id_server_str, statue_data_server in received_statue_data_map.items():
            client_statue: Optional[Statue] = None
            if statue_data_server.get('_valid_init', False):
                if statue_id_server_str in current_client_statues_map:
                    client_statue = current_client_statues_map[statue_id_server_str]
                else: # Create new statue instance on client
                    original_statue_spawn_info: Optional[Dict[str,Any]] = next((s_info for s_info in statue_spawns_data_cache if s_info.get('id') == statue_id_server_str), None)
                    s_pos_data = statue_data_server.get('pos', original_statue_spawn_info.get('pos') if original_statue_spawn_info else (200.0, 200.0))
                    s_props = statue_data_server.get('properties', original_statue_spawn_info.get('properties', {}) if original_statue_spawn_info else {})
                    client_statue = Statue(center_x=float(s_pos_data[0]), center_y=float(s_pos_data[1]), statue_id=statue_id_server_str, properties=s_props)

                if client_statue and client_statue._valid_init:
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    new_statue_list_client.append(client_statue)
                    is_statue_renderable = client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True))
                    if is_statue_renderable: add_to_renderables(client_statue)
                elif client_statue and not client_statue._valid_init:
                    error(f"GSM Client: Failed to init/update statue {statue_id_server_str} from server data.")
    game_elements["statue_objects"] = new_statue_list_client # Corrected key

    # Chest data
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
            else:
                current_chest_obj_synced = None
    
    game_elements["current_chest"] = current_chest_obj_synced
    if current_chest_obj_synced:
        new_collectible_list_client.append(current_chest_obj_synced)
    game_elements["collectible_list"] = new_collectible_list_client


    # Projectile data
    new_projectiles_list_client: List[Any] = []
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if isinstance(p_data,dict) and 'id' in p_data}
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list_ref if hasattr(p, 'projectile_id')}

        for proj_id_server_str, proj_data_server in received_proj_data_map.items():
            client_proj: Optional[Any] = None
            if proj_id_server_str in current_client_proj_map:
                client_proj = current_client_proj_map[proj_id_server_str]
            else: # Create new projectile instance
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
                        client_proj.projectile_id = proj_id_server_str # Ensure ID is set
                        client_proj.game_elements_ref = game_elements # Pass game_elements ref
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

    game_over_net = network_state_data.get('game_over', False)
    game_elements['game_over_server_state'] = game_over_net # Store for UI or local logic

    # Camera dimension update (if map changes or first sync)
    server_map_name = network_state_data.get('map_name')
    camera_instance = game_elements.get('camera')
    if server_map_name and camera_instance and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set')):
        
        client_level_data = game_elements.get('level_data') # This is the client's *current* loaded map data
        if client_level_data and game_elements.get('loaded_map_name') == server_map_name:
            # If client already has the correct map data locally
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
        elif client_level_data and game_elements.get('loaded_map_name') != server_map_name:
            # This case implies the client needs to load a new map.
            # The camera dimensions will be fully set once the new map is loaded and entities re-initialized by client_logic.
            warning(f"GSM Client: Map name mismatch ({game_elements.get('loaded_map_name')} vs {server_map_name}). Camera dimensions will be set after new map load.")
            # No need to set camera_level_dims_set = True here yet. client_logic will handle re-init.