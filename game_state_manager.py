# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.0.4 (Added BackgroundTile to pruning logic in reset_game_state)
import os
from typing import Optional, List, Dict, Any, Tuple 

from PySide6.QtCore import QRectF, QPointF, QSize, Qt 

# Game-specific imports
from game_setup import spawn_chest_qt 
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
    def info(msg): logger_gsm.info(msg)
    def debug(msg): logger_gsm.debug(msg)
    def warning(msg): logger_gsm.warning(msg)
    def error(msg): logger_gsm.error(msg)
    def critical(msg): logger_gsm.critical(msg)


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    """
    Resets the game state to initial conditions or based on map defaults.
    Clears dynamic entities, resets players, enemies, statues, and potentially respawns items like chests.
    """
    info("GSM: --- Resetting Game State (PySide6) ---")

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")

    player1_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player1_spawn_pos")
    player2_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player2_spawn_pos")

    # Fetch all_renderable_objects at the start. It will be rebuilt.
    # Static tiles (Platforms, Ladders, Lava, BackgroundTiles) should NOT be cleared from game_elements
    # but will be re-added to the new all_renderable_objects list if they persist.
    # Dynamic objects (Players, Enemies, Projectiles, Chests, Statues) will be reset or re-instanced.
    
    all_renderable_objects_accumulator: List[Any] = [] # Start with an empty list for re-population

    # Add static tiles directly from their main lists to the accumulator
    # These lists are assumed to be populated by _initialize_game_entities and persist across resets.
    all_renderable_objects_accumulator.extend(game_elements.get("platforms_list", []))
    all_renderable_objects_accumulator.extend(game_elements.get("ladders_list", []))
    all_renderable_objects_accumulator.extend(game_elements.get("hazards_list", []))
    all_renderable_objects_accumulator.extend(game_elements.get("background_tiles_list", [])) # Added

    # Reset Player 1
    if player1 and hasattr(player1, 'reset_state'):
        debug(f"GSM: Resetting P1 at {player1_spawn_pos_tuple if player1_spawn_pos_tuple else 'initial spawn'}")
        player1.reset_state(player1_spawn_pos_tuple) 
        if player1._valid_init and player1.alive(): # Only add if truly active after reset
            all_renderable_objects_accumulator.append(player1)
        debug("GSM: P1 Reset complete.")

    # Reset Player 2
    if player2 and hasattr(player2, 'reset_state'):
        debug(f"GSM: Resetting P2 at {player2_spawn_pos_tuple if player2_spawn_pos_tuple else 'initial spawn'}")
        player2.reset_state(player2_spawn_pos_tuple) 
        if player2._valid_init and player2.alive():
            all_renderable_objects_accumulator.append(player2)
        debug("GSM: P2 Reset complete.")

    # Reset Enemies
    # Server/Couch mode will re-spawn enemies from cache. Client receives from server.
    # Here, we just ensure the list in game_elements is cleared and repopulated if needed.
    enemy_list.clear() # Clear the current list of enemy instances
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    current_game_mode = game_elements.get("current_game_mode", "unknown") # Used for host/couch check
    
    if (current_game_mode in ["host", "couch_play", "host_game"]) and enemy_spawns_data_cache: # "host_game" was "host"
        debug(f"GSM: Respawning {len(enemy_spawns_data_cache)} enemies from cache for {current_game_mode} mode.")
        for i, spawn_info in enumerate(enemy_spawns_data_cache):
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
                    enemy_list.append(new_enemy_instance)
                    all_renderable_objects_accumulator.append(new_enemy_instance)
            except Exception as e_respawn:
                error(f"GSM: Error respawning enemy {i} from cache: {e_respawn}", exc_info=True)
    game_elements["enemy_list"] = enemy_list # Update the main list

    # Reset Statues
    # Statues are re-instantiated from map data if needed, or reset existing.
    # For simplicity, assume _initialize_game_entities handles full re-creation from map data.
    # This reset here is for existing instances if they persist.
    # A cleaner model might have statues also re-created from a cache like enemies if map defines them.
    statue_objects_list.clear() # Clear existing list
    statue_spawns_data_cache = game_elements.get("level_data", {}).get("statues_list", [])
    if (current_game_mode in ["host", "couch_play", "host_game"]) and statue_spawns_data_cache:
        for i, statue_data in enumerate(statue_spawns_data_cache):
            try:
                s_id = statue_data.get('id', f"map_statue_reset_{i}")
                s_pos_x, s_pos_y = float(statue_data['pos'][0]), float(statue_data['pos'][1])
                new_statue = Statue(s_pos_x, s_pos_y, statue_id=s_id, properties=statue_data.get('properties', {}))
                if new_statue._valid_init and new_statue.alive(): # Statues are "alive" until smashed
                    statue_objects_list.append(new_statue)
                    all_renderable_objects_accumulator.append(new_statue)
            except Exception as e_stat_respawn: error(f"GSM: Error respawning statue {i} from cache: {e_stat_respawn}", exc_info=True)
    game_elements["statue_objects"] = statue_objects_list # Update main list
    debug(f"GSM: Statues processed for reset. New count: {len(statue_objects_list)}.")


    # Clear Projectiles
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    projectiles_list.clear() # Empty the list
    debug("GSM: Projectiles list cleared.")

    # Reset Chest
    # Chest is re-created from map data if it exists, or from spawn_chest_qt as fallback.
    # The _initialize_game_entities should be the primary source of truth.
    # This reset primarily ensures no stale chest object persists.
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", [])
    collectible_list_ref.clear() # Clear existing collectibles

    new_chest_obj: Optional[Chest] = None
    map_items_data = game_elements.get("level_data", {}).get("items_list", [])
    if (current_game_mode in ["host", "couch_play", "host_game"]) and map_items_data:
        for item_data in map_items_data:
            if item_data.get('type', '').lower() == 'chest':
                try:
                    chest_midbottom_x, chest_midbottom_y = float(item_data['pos'][0]), float(item_data['pos'][1])
                    new_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y)
                    if new_chest_obj._valid_init:
                        collectible_list_ref.append(new_chest_obj)
                        all_renderable_objects_accumulator.append(new_chest_obj)
                        debug("GSM: Chest respawned from map data.")
                    else: debug("GSM: Map-defined chest failed to init on reset.")
                    break # Assume one chest from map data
                except Exception as e_chest_map: error(f"GSM: Error respawning chest from map data: {e_chest_map}", exc_info=True)
    
    if not new_chest_obj and hasattr(C, 'ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP') and C.ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP and \
       (current_game_mode in ["host", "couch_play", "host_game"]): # Fallback if no map chest & enabled
        ground_y_for_chest = game_elements.get("ground_level_y_ref", float(C.GAME_HEIGHT - C.TILE_SIZE))
        new_chest_obj = spawn_chest_qt(game_elements.get("platforms_list", []), ground_y_for_chest)
        if new_chest_obj and new_chest_obj._valid_init:
            collectible_list_ref.append(new_chest_obj)
            all_renderable_objects_accumulator.append(new_chest_obj)
            debug("GSM: Random chest respawned (fallback).")
        else: debug("GSM: Failed to respawn random chest (fallback).")
    
    game_elements["current_chest"] = new_chest_obj
    game_elements["collectible_list"] = collectible_list_ref # Update main list

    # Camera reset 
    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset'): 
        camera.set_offset(0.0, 0.0) 
        if player1 and player1.alive(): camera.update(player1) # Re-focus on P1
        elif player2 and player2.alive(): camera.update(player2) # Or P2 if P1 not available
        else: camera.static_update() # Or static if no players
    debug("GSM: Camera position reset/re-evaluated.")

    # Assign the newly built list of renderable objects
    game_elements["all_renderable_objects"] = all_renderable_objects_accumulator

    info("GSM: --- Game State Reset Finished (PySide6) ---\n")
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
    statue_list: List[Statue] = game_elements.get("statue_objects", []) # Use "statue_objects"
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
    """
    Updates the local game state based on data received from the server.
    """
    from player import Player # Local import if needed, already at top
    from enemy import Enemy
    from statue import Statue
    from items import Chest

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client: List[Statue] = game_elements.get("statue_objects", []) # Use "statue_objects"
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")

    all_renderable_objects: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", []) 
    
    # Add static tiles to renderables first, as they don't change based on network state
    # They are loaded once from map data.
    current_all_renderables_set = set(all_renderable_objects) # For quick lookups
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []):
            if static_item not in current_all_renderables_set:
                all_renderable_objects.append(static_item)
                current_all_renderables_set.add(static_item)

    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    # If client map data differs, it needs to be re-initialized before this function is called with new state.
    # This function assumes the client's map structure (spawns, etc.) matches the server's current map.
    if not enemy_spawns_data_cache and game_elements.get("level_data"): 
        enemy_spawns_data_cache = game_elements["level_data"].get('enemies_list', [])
        game_elements["enemy_spawns_data_cache"] = enemy_spawns_data_cache
    
    # Statue spawn data cache (similar to enemies)
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])
    if not statue_spawns_data_cache and game_elements.get("level_data"):
        statue_spawns_data_cache = game_elements["level_data"].get('statues_list', [])
        game_elements["statue_spawns_data_cache"] = statue_spawns_data_cache


    # Player data
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        is_p1_renderable = player1._valid_init and (player1.alive() or (player1.is_dead and not player1.death_animation_finished) or player1.is_petrified)
        if is_p1_renderable and player1 not in current_all_renderables_set: all_renderable_objects.append(player1); current_all_renderables_set.add(player1)
        elif not is_p1_renderable and player1 in current_all_renderables_set: all_renderable_objects.remove(player1); current_all_renderables_set.remove(player1)

    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        is_p2_renderable = player2._valid_init and (player2.alive() or (player2.is_dead and not player2.death_animation_finished) or player2.is_petrified)
        if is_p2_renderable and player2 not in current_all_renderables_set: all_renderable_objects.append(player2); current_all_renderables_set.add(player2)
        elif not is_p2_renderable and player2 in current_all_renderables_set: all_renderable_objects.remove(player2); current_all_renderables_set.remove(player2)

    # Enemy data
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies'] 
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}
        active_server_enemy_ids = set()

        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            active_server_enemy_ids.add(enemy_id_str)
            enemy_id_int = int(enemy_id_str) 

            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map:
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    client_enemy.set_network_data(enemy_data_server)
                    is_enemy_renderable = client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished) or client_enemy.is_petrified
                    if is_enemy_renderable and client_enemy not in current_all_renderables_set: all_renderable_objects.append(client_enemy); current_all_renderables_set.add(client_enemy)
                    elif not is_enemy_renderable and client_enemy in current_all_renderables_set: all_renderable_objects.remove(client_enemy); current_all_renderables_set.remove(client_enemy)
                else: 
                    original_spawn_info: Optional[Dict[str,Any]] = None
                    if enemy_spawns_data_cache and enemy_id_int < len(enemy_spawns_data_cache):
                        original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                    
                    spawn_pos_e_default = enemy_data_server.get('pos', (100.0,100.0)) 
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

                    new_enemy = Enemy(start_x=spawn_pos_e_default[0], start_y=spawn_pos_e_default[1],
                                      patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int,
                                      color_name=enemy_color_name, properties=enemy_props)
                    if new_enemy._valid_init:
                        new_enemy.set_network_data(enemy_data_server) 
                        if new_enemy.alive() or (new_enemy.is_dead and not new_enemy.death_animation_finished) or new_enemy.is_petrified:
                            all_renderable_objects.append(new_enemy); current_all_renderables_set.add(new_enemy)
                        enemy_list.append(new_enemy)
                    else: error(f"GSM Client: Failed to init new enemy {enemy_id_str} from server data.")
            elif enemy_id_str in current_client_enemies_map: 
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill() 
        
        client_ids_to_remove = set(current_client_enemies_map.keys()) - active_server_enemy_ids
        for removed_id_str in client_ids_to_remove:
            if removed_id_str in current_client_enemies_map:
                enemy_to_kill = current_client_enemies_map[removed_id_str]
                if enemy_to_kill.alive(): enemy_to_kill.kill()
        
        game_elements["enemy_list"] = [e for e in enemy_list if e.alive() or (e.is_dead and not e.death_animation_finished) or e.is_petrified]

    # Statue data
    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if isinstance(s_data, dict) and 'id' in s_data}
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client if hasattr(s, 'statue_id')}
        active_server_statue_ids = set()

        for statue_id_server_str, statue_data_server in received_statue_data_map.items():
            active_server_statue_ids.add(statue_id_server_str)
            if statue_data_server.get('_valid_init', False):
                if statue_id_server_str in current_client_statues_map:
                    client_statue = current_client_statues_map[statue_id_server_str]
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    is_statue_renderable = client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True))
                    if is_statue_renderable and client_statue not in current_all_renderables_set: all_renderable_objects.append(client_statue); current_all_renderables_set.add(client_statue)
                    elif not is_statue_renderable and client_statue in current_all_renderables_set: all_renderable_objects.remove(client_statue); current_all_renderables_set.remove(client_statue)
                else: 
                    original_statue_spawn_info: Optional[Dict[str,Any]] = next((s_info for s_info in statue_spawns_data_cache if s_info.get('id') == statue_id_server_str), None)
                    
                    s_pos_data = statue_data_server.get('pos', original_statue_spawn_info.get('pos') if original_statue_spawn_info else (200.0, 200.0))
                    s_props = statue_data_server.get('properties', original_statue_spawn_info.get('properties', {}) if original_statue_spawn_info else {})
                    
                    new_statue = Statue(center_x=float(s_pos_data[0]), center_y=float(s_pos_data[1]), statue_id=statue_id_server_str, properties=s_props)
                    if new_statue._valid_init:
                        if hasattr(new_statue, 'set_network_data'): new_statue.set_network_data(statue_data_server)
                        if new_statue.alive() or (getattr(new_statue,'is_smashed',False) and not getattr(new_statue,'death_animation_finished',True)):
                            all_renderable_objects.append(new_statue); current_all_renderables_set.add(new_statue)
                        statue_objects_list_client.append(new_statue)
                    else: error(f"GSM Client: Failed to init new statue {statue_id_server_str} from server data.")
            elif statue_id_server_str in current_client_statues_map: 
                statue_to_remove = current_client_statues_map[statue_id_server_str]
                if statue_to_remove.alive(): statue_to_remove.kill()

        client_statue_ids_to_remove = set(current_client_statues_map.keys()) - active_server_statue_ids
        for removed_s_id_str in client_statue_ids_to_remove:
            if removed_s_id_str in current_client_statues_map:
                statue_to_kill = current_client_statues_map[removed_s_id_str]
                if statue_to_kill.alive(): statue_to_kill.kill()
        
        game_elements["statue_objects"] = [s for s in statue_objects_list_client if s.alive() or (getattr(s,'is_smashed',False) and not getattr(s,'death_animation_finished',True))]

    # Chest data
    if 'chest' in network_state_data:
        chest_data_server = network_state_data['chest']
        if chest_data_server and isinstance(chest_data_server, dict): 
            if not current_chest_obj or not current_chest_obj.alive() or \
               (current_chest_obj.state == 'killed' and chest_data_server.get('chest_state') != 'killed'):
                if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill() 
                
                chest_pos_center = chest_data_server.get('pos_center', (300.0, 300.0))
                temp_chest_height = float(getattr(C, 'TILE_SIZE', 40.0)) 
                chest_midbottom_x = float(chest_pos_center[0])
                chest_midbottom_y = float(chest_pos_center[1]) + temp_chest_height / 2.0
                current_chest_obj = Chest(x=chest_midbottom_x, y=chest_midbottom_y)
                if current_chest_obj._valid_init:
                    game_elements["current_chest"] = current_chest_obj
                    # Ensure collectible_list is initialized if it wasn't
                    if "collectible_list" not in game_elements: game_elements["collectible_list"] = []
                    collectible_list_ref = game_elements["collectible_list"] # Get fresh ref
                    
                    if current_chest_obj not in collectible_list_ref: collectible_list_ref.append(current_chest_obj)
                    if current_chest_obj not in current_all_renderables_set: all_renderable_objects.append(current_chest_obj); current_all_renderables_set.add(current_chest_obj)
                else: game_elements["current_chest"] = None; current_chest_obj = None
            
            if current_chest_obj and hasattr(current_chest_obj, 'set_network_data'):
                current_chest_obj.set_network_data(chest_data_server)
                is_chest_renderable = current_chest_obj.alive() or current_chest_obj.state in ['opening', 'opened', 'fading']
                if is_chest_renderable and current_chest_obj not in current_all_renderables_set: all_renderable_objects.append(current_chest_obj); current_all_renderables_set.add(current_chest_obj)
                elif not is_chest_renderable and current_chest_obj in current_all_renderables_set: all_renderable_objects.remove(current_chest_obj); current_all_renderables_set.remove(current_chest_obj)

        elif not chest_data_server: 
            if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill()
            game_elements["current_chest"] = None
        
        game_elements["collectible_list"] = [c for c in collectible_list_ref if hasattr(c, 'alive') and c.alive()]

    # Projectile data
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if isinstance(p_data,dict) and 'id' in p_data}
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list if hasattr(p, 'projectile_id')}
        active_server_proj_ids = set()

        for proj_id_server_str, proj_data_server in received_proj_data_map.items():
            active_server_proj_ids.add(proj_id_server_str)
            if proj_id_server_str in current_client_proj_map: 
                existing_proj_client = current_client_proj_map[proj_id_server_str]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
                if existing_proj_client.alive() and existing_proj_client not in current_all_renderables_set:
                    all_renderable_objects.append(existing_proj_client); current_all_renderables_set.add(existing_proj_client)
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
                        new_proj_client = ProjClass(float(pos_data[0]), float(pos_data[1]), direction_qpointf, owner_instance_client)
                        new_proj_client.projectile_id = proj_id_server_str 
                        if hasattr(new_proj_client, 'set_network_data'): new_proj_client.set_network_data(proj_data_server)
                        new_proj_client.game_elements_ref = game_elements 
                        projectiles_list.append(new_proj_client)
                        all_renderable_objects.append(new_proj_client); current_all_renderables_set.add(new_proj_client)
                    else: warning(f"GSM Client: Unknown projectile type '{proj_type_name}' from server.")
                elif not owner_instance_client: warning(f"GSM Client: Owner P{owner_id_from_server} for projectile {proj_id_server_str} not found.")
                else: warning(f"GSM Client: Insufficient data for new projectile {proj_id_server_str}.")
        
        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - active_server_proj_ids
        for removed_proj_id_str in client_proj_ids_to_remove:
            if removed_proj_id_str in current_client_proj_map:
                proj_to_kill = current_client_proj_map[removed_proj_id_str]
                if proj_to_kill.alive(): proj_to_kill.kill()
        
        game_elements["projectiles_list"] = [p for p in projectiles_list if p.alive()]

    # Final cleanup of all_renderable_objects
    game_elements["all_renderable_objects"] = [obj for obj in all_renderable_objects if (isinstance(obj, (Platform, Ladder, Lava, BackgroundTile))) or (hasattr(obj, 'alive') and obj.alive())]

    game_over_net = network_state_data.get('game_over', False)
    game_elements['game_over_server_state'] = game_over_net 

    server_map_name = network_state_data.get('map_name')
    camera_instance = game_elements.get('camera')
    if server_map_name and camera_instance and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set')):
        
        client_level_data = game_elements.get('level_data') # This assumes level_data is up-to-date
        if client_level_data and game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True 
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
        elif client_level_data and game_elements.get('loaded_map_name') != server_map_name:
            warning(f"GSM Client: Map name mismatch ({game_elements.get('loaded_map_name')} vs {server_map_name}). Camera might not have correct dimensions until map data is synced and re-initialized.")