# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
Reset functionality now fully relies on game_setup.initialize_game_elements
to ensure a pristine reload of the map and all entities.
Network state synchronization handles creating/updating entities on the client
based on server data.
"""
# version 2.1.9 (Refined network state sync, ensured projectile class map has fallbacks)
import os
import sys
import gc # Garbage Collector
from typing import Optional, List, Dict, Any, Tuple

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF # For type hints and potential use
from PySide6.QtGui import QColor # For type hints

# Game-specific imports
from enemy import Enemy
from items import Chest
from statue import Statue
from player import Player
from tiles import Platform, Ladder, Lava, BackgroundTile # For type checking and potential direct use
from camera import Camera # For type checking camera instance
import constants as C
# from level_loader import LevelLoader # Not directly used here anymore for reset, game_setup handles it
from assets import load_all_player_animations # Might be needed if a player needs re-init due to network
import config as game_config # For player control schemes if needed during re-init
from game_setup import initialize_game_elements # CRUCIAL: This is the new reset mechanism

# Projectile classes for network deserialization
try:
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    PROJECTILES_MODULE_AVAILABLE = True
except ImportError:
    PROJECTILES_MODULE_AVAILABLE = False
    # Define dummy classes if projectiles.py is missing, to prevent NameErrors
    class Fireball: pass
    class PoisonShot: pass
    class BoltProjectile: pass
    class BloodShot: pass
    class IceShard: pass
    class ShadowProjectile: pass
    class GreyProjectile: pass


# Logger setup
try:
    from logger import info, debug, warning, error, critical
    # Player state handler is often closely tied, import if used directly
    from player_state_handler import set_player_state
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG, format='GSM (Fallback): %(levelname)s - %(message)s')
    _fallback_logger_gsm = logging.getLogger(__name__ + "_fallback_gsm")
    def info(msg, *args, **kwargs): _fallback_logger_gsm.info(msg, *args, **kwargs)
    def debug(msg, *args, **kwargs): _fallback_logger_gsm.debug(msg, *args, **kwargs)
    def warning(msg, *args, **kwargs): _fallback_logger_gsm.warning(msg, *args, **kwargs)
    def error(msg, *args, **kwargs): _fallback_logger_gsm.error(msg, *args, **kwargs)
    def critical(msg, *args, **kwargs): _fallback_logger_gsm.critical(msg, *args, **kwargs)
    def set_player_state(player: Any, new_state: str): # Fallback dummy
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")
    critical("GameStateManager: Failed to import project's logger or player_state_handler. Using isolated fallbacks.")

# --- Projectile Class Mapping for Deserialization ---
# Uses getattr with a default to None if projectiles module failed to import
projectile_class_map: Dict[str, Optional[type]] = {
    "Fireball": getattr(sys.modules.get("projectiles"), "Fireball", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "PoisonShot": getattr(sys.modules.get("projectiles"), "PoisonShot", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "BoltProjectile": getattr(sys.modules.get("projectiles"), "BoltProjectile", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "BloodShot": getattr(sys.modules.get("projectiles"), "BloodShot", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "IceShard": getattr(sys.modules.get("projectiles"), "IceShard", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "ShadowProjectile": getattr(sys.modules.get("projectiles"), "ShadowProjectile", None) if PROJECTILES_MODULE_AVAILABLE else None,
    "GreyProjectile": getattr(sys.modules.get("projectiles"), "GreyProjectile", None) if PROJECTILES_MODULE_AVAILABLE else None,
}
if not PROJECTILES_MODULE_AVAILABLE:
    warning("GameStateManager: Projectiles module not available. Projectile net sync will be non-functional.")


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    """
    Resets the game state by calling the comprehensive initialize_game_elements function
    from game_setup.py. This ensures a full reload of the map and re-creation of all entities.
    """
    info("GameStateManager: reset_game_state called. Deferring to game_setup.initialize_game_elements for full reset.")
    
    # Determine the map name to reset/reload
    current_map_to_reset = game_elements.get("map_name", game_elements.get("loaded_map_name"))
    if not current_map_to_reset:
        critical("GameStateManager Reset: CRITICAL - 'map_name' is missing from game_elements. Cannot reload map. Reset ABORTED.")
        return game_elements.get("current_chest") # Return existing chest or None to avoid crashing caller

    # Get necessary parameters for initialize_game_elements
    # These should be present in game_elements if the game was running
    screen_width = game_elements.get('main_app_screen_width', getattr(C, 'GAME_WIDTH', 960))
    screen_height = game_elements.get('main_app_screen_height', getattr(C, 'GAME_HEIGHT', 600))
    current_game_mode = game_elements.get("current_game_mode", "couch_play") # Default to a mode that spawns entities

    # Call the main initialization function which now handles full reload/reset
    # initialize_game_elements modifies game_elements in-place.
    success = initialize_game_elements(
        current_width=int(screen_width),
        current_height=int(screen_height),
        game_elements_ref=game_elements, # This will be modified
        for_game_mode=current_game_mode,
        map_module_name=current_map_to_reset # Pass the specific map to reload
    )

    if success:
        info("GameStateManager: reset_game_state completed successfully via initialize_game_elements.")
    else:
        error("GameStateManager: reset_game_state FAILED (initialize_game_elements returned False).")
        # Consider how to handle this failure, e.g., by informing the main application
        # or attempting to load a fallback default map.

    # Return the (potentially new) chest instance from the reset game_elements
    return game_elements.get("current_chest")


def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serializes the current game state into a dictionary for network transmission.
    Ensures all relevant game entities are included.
    """
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'p3': None, 'p4': None,
        'enemies': {}, 
        'chest': None, 
        'statues': [], 
        'projectiles': [], 
        'game_over': False, 
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name", "unknown_map"))
    }

    # Players (up to 4)
    for i in range(1, 5):
        player_key = f"player{i}"
        player_instance = game_elements.get(player_key)
        if player_instance and hasattr(player_instance, '_valid_init') and player_instance._valid_init and \
           hasattr(player_instance, 'get_network_data'):
            state[player_key] = player_instance.get_network_data()

    # Enemies
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    for enemy in enemy_list:
        if hasattr(enemy, '_valid_init') and enemy._valid_init and hasattr(enemy, 'enemy_id') and \
           hasattr(enemy, 'get_network_data'):
            # Only send enemies that are alive, or recently dead (for death anim), or petrified
            is_enemy_net_relevant = (
                (hasattr(enemy, 'alive') and enemy.alive()) or
                (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or
                getattr(enemy, 'is_petrified', False)
            )
            if is_enemy_net_relevant:
                state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    # Statues
    statue_list: List[Statue] = game_elements.get("statue_objects", [])
    for statue_obj in statue_list:
        if hasattr(statue_obj, '_valid_init') and statue_obj._valid_init and \
           hasattr(statue_obj, 'get_network_data'):
            is_statue_net_relevant = (
                (hasattr(statue_obj, 'alive') and statue_obj.alive()) or
                (getattr(statue_obj, 'is_smashed', False) and not getattr(statue_obj, 'death_animation_finished', True))
            )
            if is_statue_net_relevant:
                state['statues'].append(statue_obj.get_network_data())

    # Chest
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    if current_chest and hasattr(current_chest, '_valid_init') and current_chest._valid_init and \
       hasattr(current_chest, 'get_network_data'):
        # Send chest if it's alive OR in a state that needs syncing (opening, visible, fading)
        is_chest_net_relevant = (
            (hasattr(current_chest, 'alive') and current_chest.alive()) or
            getattr(current_chest, 'state', 'closed') in ['opening', 'opened_visible', 'fading']
        )
        if is_chest_net_relevant:
            state['chest'] = current_chest.get_network_data()
        else:
            state['chest'] = None # Explicitly None if not relevant
    else:
        state['chest'] = None

    # Projectiles
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    state['projectiles'] = [
        proj.get_network_data() for proj in projectiles_list 
        if hasattr(proj, 'get_network_data') and hasattr(proj, 'alive') and proj.alive()
    ]

    # Determine Game Over state based on ALL active players
    any_player_active_and_not_truly_gone = False
    for i in range(1, 5):
        player = game_elements.get(f"player{i}")
        if player and hasattr(player, '_valid_init') and player._valid_init: # Check if player instance exists and is valid
            if hasattr(player, 'alive') and player.alive(): # Actively alive
                any_player_active_and_not_truly_gone = True; break
            elif getattr(player, 'is_dead', False): # Is marked dead
                if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
                    any_player_active_and_not_truly_gone = True; break # Petrified but not smashed is still "in play"
                elif not getattr(player, 'death_animation_finished', True):
                    any_player_active_and_not_truly_gone = True; break # Death animation playing
    state['game_over'] = not any_player_active_and_not_truly_gone
    
    return state


def set_network_game_state(
    network_state_data: Dict[str, Any],
    game_elements: Dict[str, Any],
    client_player_id: Optional[int] = None # Helps client identify its own player object
):
    """
    Updates the client's game state based on data received from the server.
    Creates or updates entities as needed.
    """
    if not network_state_data:
        warning("GSM set_network_game_state: Received empty network_state_data. No changes made.")
        return

    debug(f"GSM Client: Processing received network state. Client Player ID: {client_player_id}")

    # Prepare a new list for all renderable objects for this frame
    new_all_renderables: List[Any] = []
    current_all_renderables_set = set() # To avoid duplicates in new_all_renderables

    def add_to_renderables_if_new(obj: Any):
        if obj is not None and obj not in current_all_renderables_set:
            new_all_renderables.append(obj)
            current_all_renderables_set.add(obj)

    # --- Static elements are assumed to be loaded from map file on client; no network sync needed for them ---
    # Add existing static elements to the render list first (they don't change over network)
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []):
            add_to_renderables_if_new(static_item)
    
    # Fetch spawn data caches (used if new entities need to be created on client)
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])

    # --- Players ---
    for i in range(1, 5):
        player_key_net = f"p{i}" # Key from network data
        player_key_local = f"player{i}" # Key in local game_elements
        player_instance_local = game_elements.get(player_key_local)
        player_data_from_server = network_state_data.get(player_key_net)

        if player_data_from_server and isinstance(player_data_from_server, dict):
            if not player_instance_local or not getattr(player_instance_local, '_valid_init', False):
                # Player doesn't exist locally or is invalid, create it
                spawn_pos_from_net = player_data_from_server.get('pos', (100.0 + i*50, float(getattr(C, 'GAME_HEIGHT', 600)) - 100.0))
                # Get initial properties from game_elements (should have been loaded from map)
                initial_props_for_new_player = game_elements.get(f"player{i}_spawn_props", {})
                
                player_instance_local = Player(float(spawn_pos_from_net[0]), float(spawn_pos_from_net[1]), 
                                               player_id=i, initial_properties=initial_props_for_new_player)
                game_elements[player_key_local] = player_instance_local
                debug(f"GSM Client: Created NEW Player {i} instance from network state.")
            
            if player_instance_local and hasattr(player_instance_local, 'set_network_data'):
                player_instance_local.set_network_data(player_data_from_server)
                # Determine if this player should be rendered
                is_renderable = getattr(player_instance_local, '_valid_init', False) and (
                    (hasattr(player_instance_local, 'alive') and player_instance_local.alive()) or
                    (getattr(player_instance_local, 'is_dead', False) and not getattr(player_instance_local, 'death_animation_finished', True) and not getattr(player_instance_local, 'is_petrified', False)) or
                    getattr(player_instance_local, 'is_petrified', False)
                )
                if is_renderable:
                    add_to_renderables_if_new(player_instance_local)
        elif player_instance_local and getattr(player_instance_local, '_valid_init', False):
            # Server did NOT send data for this player, assume it's gone/invalid on server
            if hasattr(player_instance_local, 'alive') and player_instance_local.alive() and hasattr(player_instance_local, 'kill'):
                player_instance_local.kill()
            game_elements[player_key_local] = None # Remove from active game elements
            debug(f"GSM Client: Player {i} not in network state, marked as None/killed locally.")

    # --- Enemies ---
    new_enemy_list_for_client: List[Enemy] = []
    current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in game_elements.get("enemy_list", []) if hasattr(enemy, 'enemy_id')}
    
    server_enemy_data_map = network_state_data.get('enemies', {})
    if isinstance(server_enemy_data_map, dict):
        for enemy_id_str, enemy_data_from_server in server_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server. Skipping."); continue
            
            client_enemy_instance: Optional[Enemy] = current_client_enemies_map.get(enemy_id_str)

            if enemy_data_from_server.get('_valid_init', False): # Server says this enemy is valid
                if not client_enemy_instance or not getattr(client_enemy_instance, '_valid_init', False):
                    # Create new enemy instance on client
                    original_spawn_info_for_enemy = enemy_spawns_data_cache[enemy_id_int] if enemy_spawns_data_cache and 0 <= enemy_id_int < len(enemy_spawns_data_cache) else None
                    
                    spawn_pos_e_tuple = enemy_data_from_server.get('pos', original_spawn_info_for_enemy.get('start_pos') if original_spawn_info_for_enemy else (100.0,100.0))
                    patrol_area_e_qrectf: Optional[QRectF] = None
                    if original_spawn_info_for_enemy and 'patrol_rect_data' in original_spawn_info_for_enemy and isinstance(original_spawn_info_for_enemy['patrol_rect_data'], dict):
                        pr_d = original_spawn_info_for_enemy['patrol_rect_data']
                        patrol_area_e_qrectf = QRectF(float(pr_d.get('x',0)), float(pr_d.get('y',0)), float(pr_d.get('width',100)), float(pr_d.get('height',50)))
                    
                    e_color_name = enemy_data_from_server.get('color_name', original_spawn_info_for_enemy.get('type') if original_spawn_info_for_enemy else 'enemy_green')
                    e_props_dict = enemy_data_from_server.get('properties', original_spawn_info_for_enemy.get('properties', {}) if original_spawn_info_for_enemy else {})
                    
                    client_enemy_instance = Enemy(start_x=float(spawn_pos_e_tuple[0]), start_y=float(spawn_pos_e_tuple[1]), 
                                                  patrol_area=patrol_area_e_qrectf, enemy_id=enemy_id_int, 
                                                  color_name=e_color_name, properties=e_props_dict)
                    debug(f"GSM Client: Created NEW Enemy ID {enemy_id_int} (Type: {e_color_name}) from network state.")
                
                if client_enemy_instance and getattr(client_enemy_instance, '_valid_init', False):
                    if hasattr(client_enemy_instance, 'set_network_data'):
                        client_enemy_instance.set_network_data(enemy_data_from_server)
                    new_enemy_list_for_client.append(client_enemy_instance)
                    if (hasattr(client_enemy_instance, 'alive') and client_enemy_instance.alive()) or \
                       (getattr(client_enemy_instance, 'is_dead', False) and not getattr(client_enemy_instance, 'death_animation_finished', True) and not getattr(client_enemy_instance, 'is_petrified', False)) or \
                       getattr(client_enemy_instance, 'is_petrified', False):
                        add_to_renderables_if_new(client_enemy_instance)
    game_elements["enemy_list"] = new_enemy_list_for_client

    # --- Statues ---
    new_statue_list_for_client: List[Statue] = []
    current_client_statues_map = {str(s.statue_id): s for s in game_elements.get("statue_objects", []) if hasattr(s, 'statue_id')}
    
    server_statue_data_list = network_state_data.get('statues', [])
    if isinstance(server_statue_data_list, list):
        for statue_data_from_server in server_statue_data_list:
            if not (isinstance(statue_data_from_server,dict) and 'id' in statue_data_from_server): continue
            statue_id_from_server = str(statue_data_from_server['id'])
            client_statue_instance: Optional[Statue] = current_client_statues_map.get(statue_id_from_server)

            if statue_data_from_server.get('_valid_init', False):
                if not client_statue_instance or not getattr(client_statue_instance, '_valid_init', False):
                    original_statue_info = next((s_inf for s_inf in statue_spawns_data_cache if s_inf.get('id') == statue_id_from_server), None)
                    s_pos_tuple = statue_data_from_server.get('pos', original_statue_info.get('pos') if original_statue_info else (200.0,200.0))
                    s_props_dict = statue_data_from_server.get('properties', original_statue_info.get('properties',{}) if original_statue_info else {})
                    client_statue_instance = Statue(float(s_pos_tuple[0]), float(s_pos_tuple[1]), statue_id=statue_id_from_server, properties=s_props_dict)
                    debug(f"GSM Client: Created NEW Statue ID {statue_id_from_server} from network state.")
                
                if client_statue_instance and getattr(client_statue_instance, '_valid_init', False):
                    if hasattr(client_statue_instance, 'set_network_data'): client_statue_instance.set_network_data(statue_data_from_server)
                    new_statue_list_for_client.append(client_statue_instance)
                    if (hasattr(client_statue_instance, 'alive') and client_statue_instance.alive()) or \
                       (getattr(client_statue_instance,'is_smashed',False) and not getattr(client_statue_instance,'death_animation_finished',True)):
                        add_to_renderables_if_new(client_statue_instance)
    game_elements["statue_objects"] = new_statue_list_for_client

    # --- Chest ---
    current_chest_obj_synced_client: Optional[Chest] = None # This will be the one for game_elements
    current_chest_obj_local_client: Optional[Chest] = game_elements.get("current_chest")
    chest_data_from_server = network_state_data.get('chest')

    if chest_data_from_server and isinstance(chest_data_from_server, dict) and \
       chest_data_from_server.get('_valid_init', False) and \
       (chest_data_from_server.get('_alive', True) or chest_data_from_server.get('chest_state', 'closed') in ['opening', 'opened_visible', 'fading']):
        
        if not current_chest_obj_local_client or not getattr(current_chest_obj_local_client, '_valid_init', False):
            # Create new chest instance on client if it doesn't exist or is invalid
            chest_pos_tuple_net = chest_data_from_server.get('pos_midbottom', (300.0,300.0)) # Midbottom for Chest
            # If Chest init needs properties, fetch from item_list in level_data (if it was stored there)
            current_chest_obj_local_client = Chest(x=float(chest_pos_tuple_net[0]), y=float(chest_pos_tuple_net[1]))
            game_elements["current_chest"] = current_chest_obj_local_client # Update main ref
            debug("GSM Client: Created NEW Chest instance from network state.")

        if current_chest_obj_local_client and getattr(current_chest_obj_local_client, '_valid_init', False):
            if hasattr(current_chest_obj_local_client, 'set_network_data'):
                current_chest_obj_local_client.set_network_data(chest_data_from_server)
            current_chest_obj_synced_client = current_chest_obj_local_client
            # Determine if chest should be rendered
            if (hasattr(current_chest_obj_synced_client, 'alive') and current_chest_obj_synced_client.alive()) or \
               getattr(current_chest_obj_synced_client, 'state', 'closed') in ['opening', 'opened_visible', 'fading']:
                add_to_renderables_if_new(current_chest_obj_synced_client)
    else: # Server says no chest or chest is not in a renderable/syncable state
        game_elements["current_chest"] = None 

    game_elements.get("collectible_list", []).clear() # Clear old list
    if current_chest_obj_synced_client:
        game_elements.get("collectible_list", []).append(current_chest_obj_synced_client)

    # --- Projectiles ---
    new_projectiles_list_for_client: List[Any] = []
    current_client_proj_map = {str(p.projectile_id): p for p in game_elements.get("projectiles_list", []) if hasattr(p, 'projectile_id')}
    
    server_projectile_data_list = network_state_data.get('projectiles', [])
    if isinstance(server_projectile_data_list, list):
        for proj_data_from_server in server_projectile_data_list:
            if not (isinstance(proj_data_from_server, dict) and 'id' in proj_data_from_server): continue
            proj_id_from_server = str(proj_data_from_server['id'])
            client_proj_instance: Optional[Any] = current_client_proj_map.get(proj_id_from_server)

            if not client_proj_instance: # Projectile doesn't exist on client, create it
                owner_id_net = proj_data_from_server.get('owner_id')
                owner_instance_client: Optional[Player] = None
                for i_p_owner in range(1,5): # Check all players
                    p_inst_check_owner = game_elements.get(f"player{i_p_owner}")
                    if p_inst_check_owner and hasattr(p_inst_check_owner, 'player_id') and \
                       p_inst_check_owner.player_id == owner_id_net:
                        owner_instance_client = p_inst_check_owner; break
                
                proj_type_str = proj_data_from_server.get('type')
                ProjectileClass = projectile_class_map.get(str(proj_type_str)) if proj_type_str else None

                if owner_instance_client and ProjectileClass and all(k in proj_data_from_server for k in ['pos','vel']):
                    pos_data_proj, vel_data_proj = proj_data_from_server['pos'], proj_data_from_server['vel']
                    spawn_dir_qpointf = QPointF(float(vel_data_proj[0]), float(vel_data_proj[1])).normalized() # Direction from velocity
                    
                    client_proj_instance = ProjectileClass(float(pos_data_proj[0]), float(pos_data_proj[1]), 
                                                           spawn_dir_qpointf, owner_instance_client)
                    if hasattr(client_proj_instance, 'projectile_id'):
                        client_proj_instance.projectile_id = proj_id_from_server # Assign server's ID
                    if hasattr(client_proj_instance, 'game_elements_ref'):
                         client_proj_instance.game_elements_ref = game_elements # Link game elements
                    debug(f"GSM Client: Created NEW {proj_type_str} ID {proj_id_from_server} from network.")
                elif not ProjectileClass:
                     warning(f"GSM Client: Unknown projectile type '{proj_type_str}' from server. Cannot create.")
                elif not owner_instance_client:
                     warning(f"GSM Client: Owner ID '{owner_id_net}' for projectile '{proj_id_from_server}' not found on client.")

            if client_proj_instance and hasattr(client_proj_instance, 'set_network_data'):
                client_proj_instance.set_network_data(proj_data_from_server)
                if hasattr(client_proj_instance, 'alive') and client_proj_instance.alive():
                    new_projectiles_list_for_client.append(client_proj_instance)
                    add_to_renderables_if_new(client_proj_instance)
    game_elements["projectiles_list"] = new_projectiles_list_for_client

    # --- Finalize all_renderable_objects for this frame ---
    game_elements["all_renderable_objects"] = new_all_renderables
    
    # Sync game over state
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)

    # --- Handle Camera Update for Client if Map Dimensions Changed ---
    server_map_name = network_state_data.get('map_name')
    camera_instance_client: Optional[Camera] = game_elements.get('camera')
    # Check if map changed OR if camera dimensions haven't been set yet for the current map
    if server_map_name and camera_instance_client and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set', False)):
        
        client_level_data_for_cam = game_elements.get('level_data')
        if client_level_data_for_cam and isinstance(client_level_data_for_cam, dict) and \
           game_elements.get('loaded_map_name') == server_map_name: # Ensure client's level_data matches server's map
            
            cam_lvl_w = float(client_level_data_for_cam.get('level_pixel_width', getattr(C, 'GAME_WIDTH', 960) * 2.0))
            cam_min_x = float(client_level_data_for_cam.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data_for_cam.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data_for_cam.get('level_max_y_absolute', getattr(C, 'GAME_HEIGHT', 600)))
            
            camera_instance_client.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True # Mark that dimensions are set
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
        else:
            warning(f"GSM Client: Server map '{server_map_name}' but client's level_data is for "
                    f"'{game_elements.get('loaded_map_name')}' or missing. Camera dimensions may be incorrect.")

    debug(f"GSM Client set_network_game_state END: Renderables count: {len(game_elements['all_renderable_objects'])}")