#################### START OF FILE: game_state_manager.py ####################

# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
Reset functionality now fully relies on game_setup.initialize_game_elements
to ensure a pristine reload of the map and all entities.
Network state synchronization handles creating/updating entities on the client
based on server data.
MODIFIED: Handles adding/removing Statues from platforms_list based on network state.
"""
# version 2.2.0 (Statue solidity sync for client)
import os
import sys
import gc # Garbage Collector
from typing import Optional, List, Dict, Any, Tuple

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor

# Game-specific imports
from enemy import Enemy
from items import Chest
from statue import Statue # Ensure Statue is imported
from player import Player
from tiles import Platform, Ladder, Lava, BackgroundTile
from camera import Camera
import constants as C
from assets import load_all_player_animations
import config as game_config
from game_setup import initialize_game_elements

try:
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    PROJECTILES_MODULE_AVAILABLE = True
except ImportError:
    PROJECTILES_MODULE_AVAILABLE = False
    class Fireball: pass
    class PoisonShot: pass
    class BoltProjectile: pass
    class BloodShot: pass
    class IceShard: pass
    class ShadowProjectile: pass
    class GreyProjectile: pass


try:
    from logger import info, debug, warning, error, critical
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
    def set_player_state(player: Any, new_state: str):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")
    critical("GameStateManager: Failed to import project's logger or player_state_handler. Using isolated fallbacks.")

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
    info("GameStateManager: reset_game_state called. Deferring to game_setup.initialize_game_elements for full reset.")
    
    current_map_to_reset = game_elements.get("map_name", game_elements.get("loaded_map_name"))
    if not current_map_to_reset:
        critical("GameStateManager Reset: CRITICAL - 'map_name' is missing from game_elements. Cannot reload map. Reset ABORTED.")
        return game_elements.get("current_chest")

    screen_width = game_elements.get('main_app_screen_width', getattr(C, 'GAME_WIDTH', 960))
    screen_height = game_elements.get('main_app_screen_height', getattr(C, 'GAME_HEIGHT', 600))
    current_game_mode = game_elements.get("current_game_mode", "couch_play")

    success = initialize_game_elements(
        current_width=int(screen_width),
        current_height=int(screen_height),
        game_elements_ref=game_elements,
        for_game_mode=current_game_mode,
        map_module_name=current_map_to_reset
    )

    if success:
        info("GameStateManager: reset_game_state completed successfully via initialize_game_elements.")
    else:
        error("GameStateManager: reset_game_state FAILED (initialize_game_elements returned False).")
    return game_elements.get("current_chest")


def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'p3': None, 'p4': None,
        'enemies': {}, 
        'chest': None, 
        'statues': [], 
        'projectiles': [], 
        'game_over': False, 
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name", "unknown_map"))
    }

    for i in range(1, 5):
        player_key = f"player{i}"
        player_instance = game_elements.get(player_key)
        if player_instance and hasattr(player_instance, '_valid_init') and player_instance._valid_init and \
           hasattr(player_instance, 'get_network_data'):
            state[player_key] = player_instance.get_network_data()

    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    for enemy in enemy_list:
        if hasattr(enemy, '_valid_init') and enemy._valid_init and hasattr(enemy, 'enemy_id') and \
           hasattr(enemy, 'get_network_data'):
            is_enemy_net_relevant = (
                (hasattr(enemy, 'alive') and enemy.alive()) or
                (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or
                getattr(enemy, 'is_petrified', False)
            )
            if is_enemy_net_relevant:
                state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    statue_list: List[Statue] = game_elements.get("statue_objects", [])
    for statue_obj in statue_list:
        if hasattr(statue_obj, '_valid_init') and statue_obj._valid_init and \
           hasattr(statue_obj, 'get_network_data'):
            is_statue_net_relevant = (
                (hasattr(statue_obj, 'alive') and statue_obj.alive()) or # If it's alive (not smashed or mid-smash anim)
                (getattr(statue_obj, 'is_smashed', False) and not getattr(statue_obj, 'death_animation_finished', True)) # Or smashed and anim playing
            )
            if is_statue_net_relevant:
                state['statues'].append(statue_obj.get_network_data())

    current_chest: Optional[Chest] = game_elements.get("current_chest")
    if current_chest and hasattr(current_chest, '_valid_init') and current_chest._valid_init and \
       hasattr(current_chest, 'get_network_data'):
        is_chest_net_relevant = (
            (hasattr(current_chest, 'alive') and current_chest.alive()) or
            getattr(current_chest, 'state', 'closed') in ['opening', 'opened_visible', 'fading']
        )
        if is_chest_net_relevant:
            state['chest'] = current_chest.get_network_data()
        else:
            state['chest'] = None
    else:
        state['chest'] = None

    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    state['projectiles'] = [
        proj.get_network_data() for proj in projectiles_list 
        if hasattr(proj, 'get_network_data') and hasattr(proj, 'alive') and proj.alive()
    ]

    any_player_active_and_not_truly_gone = False
    for i in range(1, 5):
        player = game_elements.get(f"player{i}")
        if player and hasattr(player, '_valid_init') and player._valid_init:
            if hasattr(player, 'alive') and player.alive():
                any_player_active_and_not_truly_gone = True; break
            elif getattr(player, 'is_dead', False):
                if getattr(player, 'is_petrified', False) and not getattr(player, 'is_stone_smashed', False):
                    any_player_active_and_not_truly_gone = True; break
                elif not getattr(player, 'death_animation_finished', True):
                    any_player_active_and_not_truly_gone = True; break
    state['game_over'] = not any_player_active_and_not_truly_gone
    
    return state


def _add_to_renderables_if_new_gsm(obj_to_add: Any, renderables_list_ref: List[Any]):
    """Helper local to GSM to prevent duplicates in all_renderable_objects list."""
    if obj_to_add is not None and obj_to_add not in renderables_list_ref:
        renderables_list_ref.append(obj_to_add)

def set_network_game_state(
    network_state_data: Dict[str, Any],
    game_elements: Dict[str, Any],
    client_player_id: Optional[int] = None
):
    if not network_state_data:
        warning("GSM set_network_game_state: Received empty network_state_data. No changes made.")
        return

    debug(f"GSM Client: Processing received network state. Client Player ID: {client_player_id}")

    new_all_renderables: List[Any] = []
    
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        # For static elements, we assume they are fixed and loaded from map,
        # but statues (which can be platforms) need careful handling below.
        # Here, we just add the non-statue static elements.
        # We'll rebuild platforms_list after processing statues.
        if static_list_key == "platforms_list":
            continue # Handle platforms_list carefully after statues
        for static_item in game_elements.get(static_list_key, []):
            _add_to_renderables_if_new_gsm(static_item, new_all_renderables)
    
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])

    # --- Players ---
    for i in range(1, 5):
        player_key_net = f"p{i}"
        player_key_local = f"player{i}"
        player_instance_local = game_elements.get(player_key_local)
        player_data_from_server = network_state_data.get(player_key_net)

        if player_data_from_server and isinstance(player_data_from_server, dict):
            if not player_instance_local or not getattr(player_instance_local, '_valid_init', False):
                spawn_pos_from_net = player_data_from_server.get('pos', (100.0 + i*50, float(getattr(C, 'GAME_HEIGHT', 600)) - 100.0))
                initial_props_for_new_player = game_elements.get(f"player{i}_spawn_props", {})
                player_instance_local = Player(float(spawn_pos_from_net[0]), float(spawn_pos_from_net[1]), 
                                               player_id=i, initial_properties=initial_props_for_new_player)
                player_instance_local.control_scheme = getattr(game_config, f"CURRENT_P{i}_INPUT_DEVICE", game_config.UNASSIGNED_DEVICE_ID)
                if "joystick" in player_instance_local.control_scheme:
                    try: player_instance_local.joystick_id_idx = int(player_instance_local.control_scheme.split('_')[-1])
                    except: player_instance_local.joystick_id_idx = None

                game_elements[player_key_local] = player_instance_local
                if hasattr(player_instance_local, 'set_projectile_group_references') and callable(player_instance_local.set_projectile_group_references):
                    player_instance_local.set_projectile_group_references(
                        game_elements.get("projectiles_list",[]), 
                        game_elements.get("all_renderable_objects",[]), 
                        game_elements.get("platforms_list",[]))
                debug(f"GSM Client: Created NEW Player {i} instance from network state.")
            
            if player_instance_local and hasattr(player_instance_local, 'set_network_data'):
                player_instance_local.set_network_data(player_data_from_server)
                is_renderable_player = getattr(player_instance_local, '_valid_init', False) and (
                    (hasattr(player_instance_local, 'alive') and player_instance_local.alive()) or
                    (getattr(player_instance_local, 'is_dead', False) and not getattr(player_instance_local, 'death_animation_finished', True) and not getattr(player_instance_local, 'is_petrified', False)) or
                    getattr(player_instance_local, 'is_petrified', False)
                )
                if is_renderable_player:
                    _add_to_renderables_if_new_gsm(player_instance_local, new_all_renderables)
        elif player_instance_local and getattr(player_instance_local, '_valid_init', False):
            if hasattr(player_instance_local, 'alive') and player_instance_local.alive() and hasattr(player_instance_local, 'kill'):
                player_instance_local.kill()
            game_elements[player_key_local] = None
            debug(f"GSM Client: Player {i} not in network state, marked as None/killed locally.")

    # --- Enemies (Logic largely unchanged, but ensure they use add_to_renderables_if_new_gsm) ---
    new_enemy_list_for_client: List[Enemy] = []
    current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in game_elements.get("enemy_list", []) if hasattr(enemy, 'enemy_id')}
    server_enemy_data_map = network_state_data.get('enemies', {})
    if isinstance(server_enemy_data_map, dict):
        for enemy_id_str, enemy_data_from_server in server_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server. Skipping."); continue
            client_enemy_instance: Optional[Enemy] = current_client_enemies_map.get(enemy_id_str)
            if enemy_data_from_server.get('_valid_init', False):
                if not client_enemy_instance or not getattr(client_enemy_instance, '_valid_init', False):
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
                if client_enemy_instance and getattr(client_enemy_instance, '_valid_init', False):
                    if hasattr(client_enemy_instance, 'set_network_data'):
                        client_enemy_instance.set_network_data(enemy_data_from_server)
                    new_enemy_list_for_client.append(client_enemy_instance)
                    if (hasattr(client_enemy_instance, 'alive') and client_enemy_instance.alive()) or \
                       (getattr(client_enemy_instance, 'is_dead', False) and not getattr(client_enemy_instance, 'death_animation_finished', True) and not getattr(client_enemy_instance, 'is_petrified', False)) or \
                       getattr(client_enemy_instance, 'is_petrified', False):
                        _add_to_renderables_if_new_gsm(client_enemy_instance, new_all_renderables)
    game_elements["enemy_list"] = new_enemy_list_for_client

    # --- Statues (MODIFIED for platform list management) ---
    new_statue_list_for_client_active: List[Statue] = [] # Statues that are active (alive or animating death)
    current_client_statues_map = {str(s.statue_id): s for s in game_elements.get("statue_objects", []) if hasattr(s, 'statue_id')}
    server_statue_ids_received = set()
    
    platforms_list_client_ref = game_elements.get("platforms_list", [])
    # Start with only non-statue platforms, statues will be added back if solid
    platforms_list_client_ref[:] = [p for p in platforms_list_client_ref if not isinstance(p, Statue)]


    server_statue_data_list = network_state_data.get('statues', [])
    if isinstance(server_statue_data_list, list):
        for statue_data_from_server in server_statue_data_list:
            if not (isinstance(statue_data_from_server,dict) and 'id' in statue_data_from_server): continue
            statue_id_from_server = str(statue_data_from_server['id'])
            server_statue_ids_received.add(statue_id_from_server)
            client_statue_instance: Optional[Statue] = current_client_statues_map.get(statue_id_from_server)

            is_valid_on_server = statue_data_from_server.get('_valid_init', False)
            is_alive_on_server = statue_data_from_server.get('_alive', True) # Server sends _alive
            is_smashed_on_server = statue_data_from_server.get('is_smashed', False)

            if is_valid_on_server:
                if not client_statue_instance or not getattr(client_statue_instance, '_valid_init', False):
                    original_statue_info = next((s_inf for s_inf in statue_spawns_data_cache if s_inf.get('id') == statue_id_from_server), None)
                    s_pos_tuple = statue_data_from_server.get('pos', original_statue_info.get('pos') if original_statue_info else (200.0,200.0))
                    s_props_dict = statue_data_from_server.get('properties', original_statue_info.get('properties',{}) if original_statue_info else {})
                    # Add original entity type if present (for player-turned-statues)
                    s_props_dict["original_entity_type"] = statue_data_from_server.get('original_entity_type')
                    s_props_dict["original_player_id"] = statue_data_from_server.get('original_player_id')
                    
                    client_statue_instance = Statue(float(s_pos_tuple[0]), float(s_pos_tuple[1]), statue_id=statue_id_from_server, properties=s_props_dict)
                    debug(f"GSM Client: Created NEW Statue ID {statue_id_from_server} from network state.")
                
                if client_statue_instance and getattr(client_statue_instance, '_valid_init', False):
                    if hasattr(client_statue_instance, 'set_network_data'):
                        client_statue_instance.set_network_data(statue_data_from_server)
                    
                    # is_alive_on_server should reflect if it's rendering or animating its death
                    if is_alive_on_server or (getattr(client_statue_instance, 'is_smashed', False) and not getattr(client_statue_instance, 'death_animation_finished', True)):
                        new_statue_list_for_client_active.append(client_statue_instance)
                        _add_to_renderables_if_new_gsm(client_statue_instance, new_all_renderables)

                        if not is_smashed_on_server: # If not smashed, it's a platform
                            if client_statue_instance not in platforms_list_client_ref:
                                platforms_list_client_ref.append(client_statue_instance)
                                debug(f"GSM Client: Added Statue ID {statue_id_from_server} to platforms_list (not smashed).")
                        # else: Smashed statues are already excluded from platforms_list by the reset at the start of this section
                    # else: If not alive on server and not animating death, it's truly gone.
            elif client_statue_instance: # Valid on server is false, but exists on client: ensure removed
                 if client_statue_instance in platforms_list_client_ref: # Redundant due to reset, but safe
                    platforms_list_client_ref.remove(client_statue_instance)
                    debug(f"GSM Client: Removed Invalid-On-Server Statue ID {statue_id_from_server} from platforms_list.")

    game_elements["statue_objects"] = new_statue_list_for_client_active

    # Add back non-statue platforms to renderables
    for p_item in game_elements.get("platforms_list", []):
        if not isinstance(p_item, Statue): # Only add if it's not a statue (statues handled above)
            _add_to_renderables_if_new_gsm(p_item, new_all_renderables)
        elif p_item in new_statue_list_for_client_active and not p_item.is_smashed: # If it's a statue that IS active and NOT smashed
             _add_to_renderables_if_new_gsm(p_item, new_all_renderables) # Ensure it's in renderables

    # --- Chest (Logic largely unchanged, ensure uses add_to_renderables_if_new_gsm) ---
    current_chest_obj_synced_client: Optional[Chest] = None
    current_chest_obj_local_client: Optional[Chest] = game_elements.get("current_chest")
    chest_data_from_server = network_state_data.get('chest')
    if chest_data_from_server and isinstance(chest_data_from_server, dict) and \
       chest_data_from_server.get('_valid_init', False) and \
       (chest_data_from_server.get('_alive', True) or chest_data_from_server.get('chest_state', 'closed') in ['opening', 'opened_visible', 'fading']):
        if not current_chest_obj_local_client or not getattr(current_chest_obj_local_client, '_valid_init', False):
            chest_pos_tuple_net = chest_data_from_server.get('pos_midbottom', (300.0,300.0))
            current_chest_obj_local_client = Chest(x=float(chest_pos_tuple_net[0]), y=float(chest_pos_tuple_net[1]))
            game_elements["current_chest"] = current_chest_obj_local_client
        if current_chest_obj_local_client and getattr(current_chest_obj_local_client, '_valid_init', False):
            if hasattr(current_chest_obj_local_client, 'set_network_data'):
                current_chest_obj_local_client.set_network_data(chest_data_from_server)
            current_chest_obj_synced_client = current_chest_obj_local_client
            if (hasattr(current_chest_obj_synced_client, 'alive') and current_chest_obj_synced_client.alive()) or \
               getattr(current_chest_obj_synced_client, 'state', 'closed') in ['opening', 'opened_visible', 'fading']:
                _add_to_renderables_if_new_gsm(current_chest_obj_synced_client, new_all_renderables)
    else:
        game_elements["current_chest"] = None 
    game_elements.get("collectible_list", []).clear()
    if current_chest_obj_synced_client: game_elements.get("collectible_list", []).append(current_chest_obj_synced_client)

    # --- Projectiles (Logic largely unchanged, ensure uses add_to_renderables_if_new_gsm) ---
    new_projectiles_list_for_client: List[Any] = []
    current_client_proj_map = {str(p.projectile_id): p for p in game_elements.get("projectiles_list", []) if hasattr(p, 'projectile_id')}
    server_projectile_data_list = network_state_data.get('projectiles', [])
    if isinstance(server_projectile_data_list, list):
        for proj_data_from_server in server_projectile_data_list:
            if not (isinstance(proj_data_from_server, dict) and 'id' in proj_data_from_server): continue
            proj_id_from_server = str(proj_data_from_server['id'])
            client_proj_instance: Optional[Any] = current_client_proj_map.get(proj_id_from_server)
            if not client_proj_instance:
                owner_id_net = proj_data_from_server.get('owner_id')
                owner_instance_client: Optional[Player] = None
                for i_p_owner in range(1,5):
                    p_inst_check_owner = game_elements.get(f"player{i_p_owner}")
                    if p_inst_check_owner and hasattr(p_inst_check_owner, 'player_id') and \
                       p_inst_check_owner.player_id == owner_id_net:
                        owner_instance_client = p_inst_check_owner; break
                proj_type_str = proj_data_from_server.get('type')
                ProjectileClass = projectile_class_map.get(str(proj_type_str)) if proj_type_str else None
                if owner_instance_client and ProjectileClass and all(k in proj_data_from_server for k in ['pos','vel']):
                    pos_data_proj, vel_data_proj = proj_data_from_server['pos'], proj_data_from_server['vel']
                    spawn_dir_qpointf = QPointF(float(vel_data_proj[0]), float(vel_data_proj[1])).normalized()
                    client_proj_instance = ProjectileClass(float(pos_data_proj[0]), float(pos_data_proj[1]), 
                                                           spawn_dir_qpointf, owner_instance_client)
                    if hasattr(client_proj_instance, 'projectile_id'): client_proj_instance.projectile_id = proj_id_from_server
                    if hasattr(client_proj_instance, 'game_elements_ref'): client_proj_instance.game_elements_ref = game_elements
            if client_proj_instance and hasattr(client_proj_instance, 'set_network_data'):
                client_proj_instance.set_network_data(proj_data_from_server)
                if hasattr(client_proj_instance, 'alive') and client_proj_instance.alive():
                    new_projectiles_list_for_client.append(client_proj_instance)
                    _add_to_renderables_if_new_gsm(client_proj_instance, new_all_renderables)
    game_elements["projectiles_list"] = new_projectiles_list_for_client

    game_elements["all_renderable_objects"] = new_all_renderables
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)

    # --- Camera Sync (unchanged) ---
    server_map_name = network_state_data.get('map_name')
    camera_instance_client: Optional[Camera] = game_elements.get('camera')
    if server_map_name and camera_instance_client and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set', False)):
        client_level_data_for_cam = game_elements.get('level_data')
        if client_level_data_for_cam and isinstance(client_level_data_for_cam, dict) and \
           game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data_for_cam.get('level_pixel_width', getattr(C, 'GAME_WIDTH', 960) * 2.0))
            cam_min_x = float(client_level_data_for_cam.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data_for_cam.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data_for_cam.get('level_max_y_absolute', getattr(C, 'GAME_HEIGHT', 600)))
            camera_instance_client.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True
    debug(f"GSM Client set_network_game_state END: Renderables: {len(game_elements['all_renderable_objects'])}, Platforms: {len(game_elements['platforms_list'])}")