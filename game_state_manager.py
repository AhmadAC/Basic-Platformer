# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.0.3 (More robust None checks for player spawn positions)
import os
from typing import Optional, List, Dict, Any, Tuple # Ensure Tuple is imported

from PySide6.QtCore import QRectF, QPointF, QSize, Qt # QSize, Qt not directly used here but good for context
# Game-specific imports
from game_setup import spawn_chest_qt # Assuming this is kept for now, though map data should handle chests
from enemy import Enemy # Assuming Enemy class definition for PySide6
from items import Chest # Assuming Chest class definition for PySide6
from statue import Statue # Assuming Statue class definition for PySide6
from player import Player # Assuming Player class definition for PySide6
from projectiles import ( # Import all your projectile types
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
import constants as C

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    import logging # Fallback if central logger fails
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

    # Fetch spawn positions; these should be set by _initialize_game_entities
    player1_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player1_spawn_pos")
    player2_spawn_pos_tuple: Optional[Tuple[float, float]] = game_elements.get("player2_spawn_pos")

    all_renderable_objects: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", [])

    # Reset Player 1
    if player1 and hasattr(player1, 'reset_state'):
        debug(f"GSM: Resetting P1 at {player1_spawn_pos_tuple if player1_spawn_pos_tuple else 'initial spawn'}")
        player1.reset_state(player1_spawn_pos_tuple) # Player.reset_state must handle None gracefully
        if player1._valid_init and player1.alive() and player1 not in all_renderable_objects:
            all_renderable_objects.append(player1)
        elif not player1.alive() and player1 in all_renderable_objects: # Ensure dead players are removed if reset doesn't revive
            all_renderable_objects.remove(player1)
        debug("GSM: P1 Reset complete.")

    # Reset Player 2
    if player2 and hasattr(player2, 'reset_state'):
        debug(f"GSM: Resetting P2 at {player2_spawn_pos_tuple if player2_spawn_pos_tuple else 'initial spawn'}")
        player2.reset_state(player2_spawn_pos_tuple) # Player.reset_state must handle None
        if player2._valid_init and player2.alive() and player2 not in all_renderable_objects:
            all_renderable_objects.append(player2)
        elif not player2.alive() and player2 in all_renderable_objects:
            all_renderable_objects.remove(player2)
        debug("GSM: P2 Reset complete.")

    # Reset Enemies (assuming they are respawned based on map data if needed, or just reset state)
    # If enemies are fully re-instantiated from map data by _initialize_game_entities,
    # this loop might just ensure existing instances are properly reset or killed.
    # For a full reset, _initialize_game_entities should be the primary source of truth for enemies.
    # This loop is more for resetting existing enemy instances if they persist across resets.
    for enemy_instance in list(enemy_list): # Iterate copy if modifying list
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset() # Enemy.reset should handle its alive state and visual reset
            if enemy_instance._valid_init and enemy_instance.alive() and enemy_instance not in all_renderable_objects:
                all_renderable_objects.append(enemy_instance)
            elif not enemy_instance.alive() and enemy_instance in all_renderable_objects:
                all_renderable_objects.remove(enemy_instance)
    # If enemies are re-created by _initialize_game_entities, then `enemy_list` in game_elements
    # will be repopulated by it. This loop then ensures any stragglers are handled.
    # A cleaner approach is for _initialize_game_entities to clear and rebuild enemy_list.
    # For now, this tries to reset existing ones.
    debug(f"GSM: {len(enemy_list)} enemies processed for reset (current instances).")


    # Reset Statues
    for statue_instance in statue_objects_list:
        if hasattr(statue_instance, 'is_smashed'): statue_instance.is_smashed = False
        if hasattr(statue_instance, 'is_dead'): statue_instance.is_dead = False # Statues are usually not "dead" but "smashed"
        if hasattr(statue_instance, 'death_animation_finished'): statue_instance.death_animation_finished = False
        if hasattr(statue_instance, '_alive'): statue_instance._alive = True # Reset alive state
        
        # Reset image to initial state
        if hasattr(statue_instance, 'image') and hasattr(statue_instance, 'initial_image_frames') and \
           statue_instance.initial_image_frames and not statue_instance.initial_image_frames[0].isNull():
            statue_instance.image = statue_instance.initial_image_frames[0]
            if hasattr(statue_instance, '_update_rect_from_image_and_pos'):
                statue_instance._update_rect_from_image_and_pos()
        
        if statue_instance.alive() and statue_instance not in all_renderable_objects:
            all_renderable_objects.append(statue_instance)
    debug(f"GSM: {len(statue_objects_list)} statues processed for state reset.")

    # Clear Projectiles
    projectiles_to_remove = [p for p in all_renderable_objects if isinstance(p, tuple(projectile_class_map.values()))] # Use defined map
    for p_rem in projectiles_to_remove:
        if hasattr(p_rem, 'kill'): p_rem.kill() # Mark as not alive
        if p_rem in all_renderable_objects: all_renderable_objects.remove(p_rem)
    projectiles_list.clear()
    debug("GSM: Projectiles cleared from lists and renderables.")

    # Reset Chest (or re-spawn if logic dictates)
    if current_chest_obj:
        if hasattr(current_chest_obj, 'kill') and current_chest_obj.alive(): current_chest_obj.kill()
        if current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)
        if current_chest_obj in collectible_list_ref: collectible_list_ref.remove(current_chest_obj)
    debug(f"GSM: Existing chest removed (if any).")

    # Chest spawning should ideally be driven by map data loaded in _initialize_game_entities.
    # If spawn_chest_qt is for random spawning, it might conflict with map-defined chests.
    # For now, let's assume _initialize_game_entities sets up the chest from map data.
    # If no chest from map data, then spawn_chest_qt could be a fallback.
    
    new_chest_obj: Optional[Chest] = None
    # Check if a chest was defined in the map data (loaded by _initialize_game_entities)
    # This assumes _initialize_game_entities already populated game_elements['collectible_list'] with map chests
    map_defined_chests = [item for item in game_elements.get('collectible_list', []) if isinstance(item, Chest)]
    if map_defined_chests:
        new_chest_obj = map_defined_chests[0] # Assume one chest for now
        if hasattr(new_chest_obj, 'is_collected_flag_internal'): new_chest_obj.is_collected_flag_internal = False
        if hasattr(new_chest_obj, 'state'): new_chest_obj.state = 'closed'
        if hasattr(new_chest_obj, '_alive'): new_chest_obj._alive = True
        if new_chest_obj.initial_image_frames: new_chest_obj.image = new_chest_obj.initial_image_frames[0]
        if hasattr(new_chest_obj, '_update_rect_from_image_and_pos'): new_chest_obj._update_rect_from_image_and_pos()
        if new_chest_obj not in all_renderable_objects: all_renderable_objects.append(new_chest_obj)
        debug("GSM: Reset existing map-defined chest.")
    elif hasattr(C, 'ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP') and C.ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP:
        # Fallback to random spawn only if enabled and no map chest
        ground_y_for_chest = game_elements.get("ground_level_y_ref", float(C.GAME_HEIGHT - C.TILE_SIZE))
        new_chest_obj = spawn_chest_qt(game_elements.get("platforms_list", []), ground_y_for_chest)
        if new_chest_obj:
            if new_chest_obj not in all_renderable_objects: all_renderable_objects.append(new_chest_obj)
            collectible_list_ref.append(new_chest_obj) # Add to the main list
            debug("GSM: Random chest respawned (fallback).")
        else: debug("GSM: Failed to respawn random chest (fallback).")
    else:
        debug("GSM: No map-defined chest and random spawning disabled.")

    game_elements["current_chest"] = new_chest_obj
    # Ensure collectible_list reflects the current state
    game_elements["collectible_list"] = [c for c in collectible_list_ref if hasattr(c, 'alive') and c.alive()]
    if new_chest_obj and new_chest_obj.alive() and new_chest_obj not in game_elements["collectible_list"]:
        game_elements["collectible_list"].append(new_chest_obj)


    # Camera reset (simple position reset, zoom/bounds are map-specific)
    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset'): # Camera uses set_offset
        camera.set_offset(0.0, 0.0) # Reset to origin or default view
        # If camera needs to refocus on player1:
        # if player1 and player1.alive(): camera.update(player1)
    debug("GSM: Camera position reset/re-evaluated.")

    # Ensure all_renderable_objects is clean of dead things
    game_elements["all_renderable_objects"] = [obj for obj in all_renderable_objects if hasattr(obj, 'alive') and obj.alive()]

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
        'map_name': game_elements.get("map_name", "unknown_map") # Include map name
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
            # Send enemies that are alive OR are dead but their death animation isn't finished OR are petrified/smashed
            if enemy.alive() or \
               (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or \
               getattr(enemy, 'is_petrified', False): # Petrified/smashed are important states to sync
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    for s_obj in statue_list:
        # Send statues that are alive (not smashed yet) OR smashed but not yet faded
        if (hasattr(s_obj, 'alive') and s_obj.alive()) or \
           (getattr(s_obj, 'is_smashed', False) and not getattr(s_obj, 'death_animation_finished', True)):
            if hasattr(s_obj, 'get_network_data'):
                state['statues'].append(s_obj.get_network_data())

    if current_chest and hasattr(current_chest, 'rect'):
        # Send chest if it's alive OR in a state that needs visual syncing (e.g., opening, fading)
        if current_chest.alive() or current_chest.state in ['opening', 'opened', 'fading']: # 'killed' implies it will be removed
            state['chest'] = current_chest.get_network_data()
        else: state['chest'] = None
    else: state['chest'] = None

    # Check game over based on P1's state (primary player for server determining game over)
    p1_truly_gone = True
    if player1 and player1._valid_init:
        if player1.alive(): # If player is in sprite groups, it's "active"
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False):
                    p1_truly_gone = False # Petrified but not smashed is not "truly gone" for game over
                elif not getattr(player1, 'death_animation_finished', True):
                    p1_truly_gone = False # Death animation playing
            else:
                p1_truly_gone = False # Alive and not dead
        # If not player1.alive(), it means it has been 'killed' and removed from sprite groups, so truly gone.
    state['game_over'] = p1_truly_gone

    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]

    return state


def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None):
    """
    Updates the local game state based on data received from the server.
    Client player ID helps differentiate local player from remote.
    """
    # --- Lazy import Player for set_network_data context if needed ---
    # from player import Player # Already imported at top
    from enemy import Enemy
    from statue import Statue
    from items import Chest

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")

    all_renderable_objects: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", []) # Use existing or create
    
    # On client, enemy_spawns_data_cache might not be relevant if server dictates all spawns.
    # However, if client needs to re-create enemies from scratch based on server ID:
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    if not enemy_spawns_data_cache and game_elements.get("level_data"): # Populate if empty from loaded level data
        enemy_spawns_data_cache = game_elements["level_data"].get('enemies_list', [])
        game_elements["enemy_spawns_data_cache"] = enemy_spawns_data_cache


    # Player data
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        # Ensure player is in renderables if active, removed if not
        is_p1_renderable = player1._valid_init and (player1.alive() or (player1.is_dead and not player1.death_animation_finished) or player1.is_petrified)
        if is_p1_renderable and player1 not in all_renderable_objects: all_renderable_objects.append(player1)
        elif not is_p1_renderable and player1 in all_renderable_objects: all_renderable_objects.remove(player1)

    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        is_p2_renderable = player2._valid_init and (player2.alive() or (player2.is_dead and not player2.death_animation_finished) or player2.is_petrified)
        if is_p2_renderable and player2 not in all_renderable_objects: all_renderable_objects.append(player2)
        elif not is_p2_renderable and player2 in all_renderable_objects: all_renderable_objects.remove(player2)


    # Enemy data
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies'] # Dict by enemy_id string
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}
        active_server_enemy_ids = set()

        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            active_server_enemy_ids.add(enemy_id_str)
            enemy_id_int = int(enemy_id_str) # Convert string ID from JSON key to int

            if enemy_data_server.get('_valid_init', False):
                if enemy_id_str in current_client_enemies_map:
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    client_enemy.set_network_data(enemy_data_server)
                    # Add/remove from renderables based on new state
                    is_enemy_renderable = client_enemy.alive() or (client_enemy.is_dead and not client_enemy.death_animation_finished) or client_enemy.is_petrified
                    if is_enemy_renderable and client_enemy not in all_renderable_objects:
                        all_renderable_objects.append(client_enemy)
                    elif not is_enemy_renderable and client_enemy in all_renderable_objects:
                        all_renderable_objects.remove(client_enemy)
                else: # New enemy seen from server, create it
                    # Try to get original spawn info if available (for patrol_area, color)
                    original_spawn_info: Optional[Dict[str,Any]] = None
                    if enemy_spawns_data_cache and enemy_id_int < len(enemy_spawns_data_cache):
                        original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                    
                    spawn_pos_e_default = enemy_data_server.get('pos', (100.0,100.0)) # Fallback if pos missing
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
                        new_enemy.set_network_data(enemy_data_server) # Apply detailed state from server
                        if new_enemy.alive() or (new_enemy.is_dead and not new_enemy.death_animation_finished) or new_enemy.is_petrified:
                            all_renderable_objects.append(new_enemy)
                        enemy_list.append(new_enemy)
                    else: error(f"GSM Client: Failed to init new enemy {enemy_id_str} from server data.")
            elif enemy_id_str in current_client_enemies_map: # Server says enemy invalid/gone
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill() # Mark for removal
                # Pruning from lists will happen at the end of this function
        
        # Remove enemies present on client but not in server's active list
        client_ids_to_remove = set(current_client_enemies_map.keys()) - active_server_enemy_ids
        for removed_id_str in client_ids_to_remove:
            if removed_id_str in current_client_enemies_map:
                enemy_to_kill = current_client_enemies_map[removed_id_str]
                if enemy_to_kill.alive(): enemy_to_kill.kill()
        
        # Update main list in game_elements, keeping only truly active/animating ones
        game_elements["enemy_list"] = [e for e in enemy_list if e.alive() or (e.is_dead and not e.death_animation_finished) or e.is_petrified]

    # Statue data (similar logic to enemies)
    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if isinstance(s_data, dict) and 'id' in s_data}
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client if hasattr(s, 'statue_id')}
        active_server_statue_ids = set()

        for statue_id_server_str, statue_data_server in received_statue_data_map.items():
            active_server_statue_ids.add(statue_id_server_str)
            # statue_id_obj = statue_id_server_str # ID is already string or compatible
            
            if statue_data_server.get('_valid_init', False): # Check if server thinks it's valid
                if statue_id_server_str in current_client_statues_map:
                    client_statue = current_client_statues_map[statue_id_server_str]
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    is_statue_renderable = client_statue.alive() or (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True))
                    if is_statue_renderable and client_statue not in all_renderable_objects: all_renderable_objects.append(client_statue)
                    elif not is_statue_renderable and client_statue in all_renderable_objects: all_renderable_objects.remove(client_statue)
                else: # New statue from server
                    s_pos_data = statue_data_server.get('pos', (200.0, 200.0))
                    s_props = statue_data_server.get('properties', {})
                    new_statue = Statue(center_x=float(s_pos_data[0]), center_y=float(s_pos_data[1]), statue_id=statue_id_server_str, properties=s_props)
                    if new_statue._valid_init:
                        if hasattr(new_statue, 'set_network_data'): new_statue.set_network_data(statue_data_server)
                        if new_statue.alive() or (getattr(new_statue,'is_smashed',False) and not getattr(new_statue,'death_animation_finished',True)):
                            all_renderable_objects.append(new_statue)
                        statue_objects_list_client.append(new_statue)
                    else: error(f"GSM Client: Failed to init new statue {statue_id_server_str} from server data.")
            elif statue_id_server_str in current_client_statues_map: # Server says statue invalid/gone
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
        if chest_data_server and isinstance(chest_data_server, dict): # Server has a chest
            if not current_chest_obj or not current_chest_obj.alive() or \
               (current_chest_obj.state == 'killed' and chest_data_server.get('chest_state') != 'killed'):
                # Client needs to create or revive the chest
                if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill() # Kill old if exists
                
                chest_pos_center = chest_data_server.get('pos_center', (300.0, 300.0))
                # Chest constructor takes midbottom. Estimate from center and a default height.
                temp_chest_height = float(getattr(C, 'TILE_SIZE', 40.0)) # Default height
                chest_midbottom_x = float(chest_pos_center[0])
                chest_midbottom_y = float(chest_pos_center[1]) + temp_chest_height / 2.0
                current_chest_obj = Chest(x=chest_midbottom_x, y=chest_midbottom_y)
                if current_chest_obj._valid_init:
                    game_elements["current_chest"] = current_chest_obj
                    collectible_list_ref.append(current_chest_obj) # Add to general collectibles
                    all_renderable_objects.append(current_chest_obj)
                else: game_elements["current_chest"] = None; current_chest_obj = None
            
            if current_chest_obj and hasattr(current_chest_obj, 'set_network_data'):
                current_chest_obj.set_network_data(chest_data_server)
                is_chest_renderable = current_chest_obj.alive() or current_chest_obj.state in ['opening', 'opened', 'fading']
                if is_chest_renderable and current_chest_obj not in all_renderable_objects: all_renderable_objects.append(current_chest_obj)
                elif not is_chest_renderable and current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)

        elif not chest_data_server: # Server says no chest
            if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill()
            game_elements["current_chest"] = None
        
        # Update main collectible list
        game_elements["collectible_list"] = [c for c in collectible_list_ref if hasattr(c, 'alive') and c.alive()]


    # Projectile data
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if isinstance(p_data,dict) and 'id' in p_data}
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list if hasattr(p, 'projectile_id')}
        active_server_proj_ids = set()

        for proj_id_server_str, proj_data_server in received_proj_data_map.items():
            active_server_proj_ids.add(proj_id_server_str)
            if proj_id_server_str in current_client_proj_map: # Existing projectile
                existing_proj_client = current_client_proj_map[proj_id_server_str]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
                if existing_proj_client.alive() and existing_proj_client not in all_renderable_objects:
                    all_renderable_objects.append(existing_proj_client)
            else: # New projectile from server
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

                        # Pass game_elements to projectile, which should have reference to projectile_list and all_renderables
                        # This assumes projectile constructor doesn't auto-add to lists, but Player methods do.
                        # For client-side creation from network, we manage list addition here.
                        new_proj_client = ProjClass(float(pos_data[0]), float(pos_data[1]),
                                                    direction_qpointf, owner_instance_client)
                        new_proj_client.projectile_id = proj_id_server_str # Set the ID from server
                        if hasattr(new_proj_client, 'set_network_data'): new_proj_client.set_network_data(proj_data_server)
                        
                        # Crucially set the game_elements_ref for the new projectile
                        new_proj_client.game_elements_ref = game_elements 

                        projectiles_list.append(new_proj_client)
                        all_renderable_objects.append(new_proj_client)
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
    game_elements["all_renderable_objects"] = [obj for obj in all_renderable_objects if hasattr(obj, 'alive') and obj.alive()]

    # Update game over state locally based on P1 from server (or both if P2 is client_player_id)
    game_over_net = network_state_data.get('game_over', False)
    game_elements['game_over_server_state'] = game_over_net # Store server's game_over state

    # Update Camera if map changed or for initial setup
    # Client's camera gets its world dimensions from server-sent map data.
    # If the map name received from server differs or if it's the first proper sync:
    server_map_name = network_state_data.get('map_name')
    if server_map_name and game_elements.get('camera') and \
       (game_elements.get('map_name') != server_map_name or not game_elements.get('camera_level_dims_set')):
        
        # This part implies that when the client receives 'set_map' from server (in client_logic.py),
        # it should then request full map data if needed, load it into game_elements['level_data'],
        # and then _initialize_game_entities (or a similar function) is called to set up
        # local entities and camera based on this new map data.
        # For simplicity here, we assume level_data for the new map is already in game_elements
        # if server_map_name has been updated. This is a bit of a chicken-and-egg problem.
        # A more robust flow:
        # 1. Server sends "set_map: new_map_name"
        # 2. Client receives, if map differs, client logic requests new map data.
        # 3. Server sends map data.
        # 4. Client receives map data, calls a function like _initialize_game_entities_for_client(new_map_data).
        # 5. That function sets up camera with new level dims, THEN server sends full game state.
        
        # For now, assume level_data in game_elements is for the server_map_name
        client_level_data = game_elements.get('level_data')
        if client_level_data and game_elements.get('map_name') == server_map_name:
            cam = game_elements['camera']
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            cam.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True # Mark that camera is set for this level
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")