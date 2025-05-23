# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.1.0 (Robust reset with level_data reload, entity respawn fixes)
import os
import sys # For sys.path for LevelLoader fallback
from typing import Optional, List, Dict, Any, Tuple
from camera import Camera
from PySide6.QtCore import QRectF, QPointF # Ensure QPointF is imported

# Game-specific imports
from enemy import Enemy
from items import Chest
from statue import Statue
from player import Player
from tiles import Platform, Ladder, Lava, BackgroundTile # For type hinting, ensure it's available
from projectiles import ( # Ensure these are available for get_network_game_state
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
import constants as C
from level_loader import LevelLoader # Import LevelLoader for map reloading

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
    debug(f"GSM: game_elements at START of reset: Keys={list(game_elements.keys())}")

    # --- Preserve essential data that reset_game_state itself doesn't modify ---
    # This data is critical for respawning entities and setting up the level.
    map_name_for_reset = game_elements.get("map_name", game_elements.get("loaded_map_name"))
    
    # Player spawn info (should be preserved or re-fetched if level_data is reloaded)
    player1_spawn_pos_cache = game_elements.get("player1_spawn_pos")
    player1_spawn_props_cache = game_elements.get("player1_spawn_props")
    player2_spawn_pos_cache = game_elements.get("player2_spawn_pos")
    player2_spawn_props_cache = game_elements.get("player2_spawn_props")

    # --- Attempt to use existing level_data; if missing, try to RELOAD it ---
    level_data_for_reset = game_elements.get("level_data")
    if not level_data_for_reset and map_name_for_reset:
        warning("GSM Reset: 'level_data' missing from game_elements. Attempting to RELOAD map for reset.")
        loader = LevelLoader()
        
        # Robustly determine MAPS_DIR path
        maps_dir_path = str(getattr(C, "MAPS_DIR", "maps"))
        if not os.path.isabs(maps_dir_path):
            # Try to find project root relative to game_state_manager.py
            current_file_dir = os.path.dirname(os.path.abspath(__file__)) # dir of game_state_manager.py
            project_root_guess = os.path.dirname(current_file_dir) # Assume this file is in a subdir of project root
            
            # Check common project structures
            if not os.path.isdir(os.path.join(project_root_guess, "maps")): 
                # If 'maps' is not in parent, assume project_root is current_file_dir's parent's parent (e.g. if in utils/ subdirectory)
                project_root_guess = os.path.dirname(project_root_guess) 
            
            maps_dir_path = os.path.join(str(project_root_guess), maps_dir_path)
            debug(f"GSM Reset: Derived maps_dir_path for reload: {maps_dir_path}")

        reloaded_level_data = loader.load_map(map_name_for_reset, maps_dir_path)
        if reloaded_level_data:
            level_data_for_reset = reloaded_level_data
            game_elements["level_data"] = reloaded_level_data # Store the freshly loaded data
            info(f"GSM Reset: Successfully reloaded map data for '{map_name_for_reset}' during reset.")
            # Re-cache spawn positions from reloaded data if they were missing
            if not player1_spawn_pos_cache: player1_spawn_pos_cache = reloaded_level_data.get("player_start_pos_p1")
            if not player1_spawn_props_cache: player1_spawn_props_cache = reloaded_level_data.get("player1_spawn_props", {})
            if not player2_spawn_pos_cache: player2_spawn_pos_cache = reloaded_level_data.get("player_start_pos_p2")
            if not player2_spawn_props_cache: player2_spawn_props_cache = reloaded_level_data.get("player2_spawn_props", {})
        else:
            error(f"GSM Reset: CRITICAL - Failed to reload map data for '{map_name_for_reset}'. Entities cannot be reliably respawned.")
    elif not level_data_for_reset and not map_name_for_reset:
        error("GSM Reset: CRITICAL - Both 'level_data' and 'map_name' are missing. Cannot respawn entities.")

    # --- Clear dynamic entity lists ---
    game_elements["enemy_list"] = []
    game_elements["statue_objects"] = [] # If your code uses "statue_objects_list", adjust this key
    game_elements["projectiles_list"] = []
    game_elements["collectible_list"] = [] 
    
    # --- Rebuild all_renderable_objects starting with static elements ---
    # Static elements should persist in game_elements or be part of level_data_for_reset
    game_elements["all_renderable_objects"] = []
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        static_items = game_elements.get(static_list_key) # These should already be in game_elements from initial load
        if not static_items and level_data_for_reset: # Fallback: if cleared, try re-getting from (reloaded) level_data
            static_items_from_level_data = level_data_for_reset.get(static_list_key)
            if static_items_from_level_data:
                # This would require re-instantiating Platform, Ladder, etc. objects here
                # For now, assume they persist in game_elements. If not, game_setup.initialize_game_elements logic
                # for these static types would need to be duplicated/called here.
                warning(f"GSM Reset: Static list '{static_list_key}' was missing from game_elements but found in level_data. "
                        "Ideally, static lists persist. Re-adding references.")
                game_elements[static_list_key] = static_items_from_level_data # This assumes they are already object instances
                static_items = static_items_from_level_data

        if static_items:
            game_elements["all_renderable_objects"].extend(static_items)
        else:
            debug(f"GSM Reset: Static list '{static_list_key}' not found in game_elements or reloaded level_data.")


    # --- Reset Players ---
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")

    if player1 and hasattr(player1, 'reset_state'):
        # Ensure spawn_pos is a tuple of floats, fallback to initial_spawn_pos if needed
        p1_spawn_to_use = player1_spawn_pos_cache
        if not isinstance(p1_spawn_to_use, (tuple, list)) or len(p1_spawn_to_use) != 2:
            warning(f"GSM Reset P1: Invalid player1_spawn_pos_cache ({p1_spawn_to_use}). Using player's initial_spawn_pos.")
            p1_spawn_to_use = player1.initial_spawn_pos # QPointF
        if isinstance(p1_spawn_to_use, QPointF): # Convert QPointF to tuple for reset_state
            p1_spawn_to_use = (p1_spawn_to_use.x(), p1_spawn_to_use.y())
            
        debug(f"GSM: Resetting Player 1 to spawn: {p1_spawn_to_use}")
        player1.reset_state(p1_spawn_to_use) # Player.reset_state expects a tuple or None
        if player1._valid_init and player1.alive():
            game_elements["all_renderable_objects"].append(player1)
        info(f"GSM: Player 1 reset. Health: {player1.current_health}, Pos: {player1.pos}")

    if player2 and hasattr(player2, 'reset_state'):
        p2_spawn_to_use = player2_spawn_pos_cache
        if not isinstance(p2_spawn_to_use, (tuple, list)) or len(p2_spawn_to_use) != 2:
            warning(f"GSM Reset P2: Invalid player2_spawn_pos_cache ({p2_spawn_to_use}). Using player's initial_spawn_pos.")
            p2_spawn_to_use = player2.initial_spawn_pos # QPointF
        if isinstance(p2_spawn_to_use, QPointF):
            p2_spawn_to_use = (p2_spawn_to_use.x(), p2_spawn_to_use.y())

        debug(f"GSM: Resetting Player 2 to spawn: {p2_spawn_to_use}")
        player2.reset_state(p2_spawn_to_use)
        if player2._valid_init and player2.alive():
            game_elements["all_renderable_objects"].append(player2)
        info(f"GSM: Player 2 reset. Health: {player2.current_health}, Pos: {player2.pos}")

    # --- Respawn Dynamic Entities (Enemies, Statues, Chest) ---
    current_game_mode = game_elements.get("current_game_mode", "unknown")
    server_authoritative_modes = ["couch_play", "host_waiting", "host_active"]
    debug(f"GSM: Current game mode for entity respawn check: '{current_game_mode}'. Authoritative modes: {server_authoritative_modes}")

    if current_game_mode in server_authoritative_modes:
        debug(f"GSM: Respawning dynamic entities for authoritative mode '{current_game_mode}'.")

        enemies_to_spawn_from_data: Optional[List[Dict[str, Any]]] = None
        statues_to_spawn_from_data: Optional[List[Dict[str, Any]]] = None
        items_to_spawn_from_data: Optional[List[Dict[str, Any]]] = None

        if level_data_for_reset and isinstance(level_data_for_reset, dict):
            enemies_to_spawn_from_data = level_data_for_reset.get('enemies_list')
            statues_to_spawn_from_data = level_data_for_reset.get('statues_list')
            items_to_spawn_from_data = level_data_for_reset.get('items_list')
            debug(f"GSM Reset: Using level_data_for_reset for spawns. Enemies: {len(enemies_to_spawn_from_data) if enemies_to_spawn_from_data else 'None/Empty'}, "
                  f"Statues: {len(statues_to_spawn_from_data) if statues_to_spawn_from_data else 'None/Empty'}, Items: {len(items_to_spawn_from_data) if items_to_spawn_from_data else 'None/Empty'}")
        else:
            error("GSM Reset: level_data_for_reset is missing or invalid. Dynamic entities will NOT respawn from map definition.")

        # Respawn Enemies
        if enemies_to_spawn_from_data:
            for i, spawn_info in enumerate(enemies_to_spawn_from_data):
                try:
                    patrol_raw = spawn_info.get('patrol_rect_data')
                    patrol_qrectf: Optional[QRectF] = None
                    if isinstance(patrol_raw, dict) and all(k in patrol_raw for k in ['x','y','width','height']):
                        patrol_qrectf = QRectF(float(patrol_raw['x']), float(patrol_raw['y']),
                                               float(patrol_raw['width']), float(patrol_raw['height']))
                    enemy_color_name = str(spawn_info.get('type', 'enemy_green'))
                    start_pos = tuple(map(float, spawn_info.get('start_pos', (100.0, 100.0))))
                    props = spawn_info.get('properties', {})
                    
                    new_enemy = Enemy(start_x=start_pos[0], start_y=start_pos[1],
                                      patrol_area=patrol_qrectf, enemy_id=i,
                                      color_name=enemy_color_name, properties=props)
                    if new_enemy._valid_init and new_enemy.alive():
                        game_elements["enemy_list"].append(new_enemy)
                        game_elements["all_renderable_objects"].append(new_enemy)
                except Exception as e: error(f"GSM: Error respawning enemy {i}: {e}", exc_info=True)
        else: debug("GSM: No enemy spawn data in level_data_for_reset.")

        # Respawn Statues
        if statues_to_spawn_from_data:
            for i, statue_data in enumerate(statues_to_spawn_from_data):
                try:
                    s_id = statue_data.get('id', f"map_statue_reset_{i}")
                    s_pos = tuple(map(float, statue_data.get('pos', (200.0, 200.0))))
                    s_props = statue_data.get('properties', {})
                    new_statue = Statue(s_pos[0], s_pos[1], statue_id=s_id, properties=s_props)
                    if new_statue._valid_init and new_statue.alive():
                        game_elements["statue_objects"].append(new_statue)
                        game_elements["all_renderable_objects"].append(new_statue)
                except Exception as e: error(f"GSM: Error respawning statue {i}: {e}", exc_info=True)
        else: debug("GSM: No statue spawn data in level_data_for_reset.")
            
        # Respawn Chest
        new_chest_obj: Optional[Chest] = None
        if items_to_spawn_from_data:
            for item_data in items_to_spawn_from_data:
                if item_data.get('type', '').lower() == 'chest':
                    try:
                        chest_pos = tuple(map(float, item_data.get('pos', (300.0, 300.0))))
                        # Assuming Chest properties are not deeply nested or complex for reset
                        # new_chest_obj = Chest(chest_pos[0], chest_pos[1], properties=item_data.get('properties', {}))
                        new_chest_obj = Chest(chest_pos[0], chest_pos[1]) # If Chest constructor doesn't take properties yet

                        if new_chest_obj._valid_init:
                            game_elements["collectible_list"].append(new_chest_obj)
                            game_elements["all_renderable_objects"].append(new_chest_obj)
                            info(f"GSM: Chest respawned at {chest_pos}.")
                        else: warning("GSM: Chest failed to init on reset from items_list.")
                        break 
                    except Exception as e: error(f"GSM: Error respawning chest from items_list: {e}", exc_info=True)
        else: debug("GSM: No items_list in level_data_for_reset. No chest from map definition.")
        game_elements["current_chest"] = new_chest_obj
    else: # Not an authoritative mode
        debug(f"GSM: Dynamic entities (enemies, statues, chest) not respawned for mode '{current_game_mode}'.")
        game_elements["current_chest"] = None

    # --- Camera Reset ---
    camera = game_elements.get("camera")
    if camera and hasattr(camera, 'set_offset'):
        camera.set_offset(0.0, 0.0)
        focus_target_cam = None
        if player1 and player1.alive() and player1._valid_init: focus_target_cam = player1
        elif player2 and player2.alive() and player2._valid_init: focus_target_cam = player2
        
        if focus_target_cam: camera.update(focus_target_cam)
        else: camera.static_update()
    debug("GSM: Camera position reset/re-evaluated.")
    
    # --- Restore other essential map config data if it was reloaded ---
    # This ensures that if level_data was reloaded, game_elements reflects this fresh data.
    # If level_data was NOT reloaded, these values should already be correct in game_elements.
    if level_data_for_reset:
        game_elements["level_pixel_width"] = level_data_for_reset.get("level_pixel_width", game_elements.get("level_pixel_width"))
        game_elements["level_min_x_absolute"] = level_data_for_reset.get("level_min_x_absolute", game_elements.get("level_min_x_absolute"))
        game_elements["level_min_y_absolute"] = level_data_for_reset.get("level_min_y_absolute", game_elements.get("level_min_y_absolute"))
        game_elements["level_max_y_absolute"] = level_data_for_reset.get("level_max_y_absolute", game_elements.get("level_max_y_absolute"))
        game_elements["ground_level_y_ref"] = level_data_for_reset.get("ground_level_y_ref", game_elements.get("ground_level_y_ref"))
        game_elements["ground_platform_height_ref"] = level_data_for_reset.get("ground_platform_height_ref", game_elements.get("ground_platform_height_ref"))
        game_elements["level_background_color"] = level_data_for_reset.get("level_background_color", game_elements.get("level_background_color"))
        if map_name_for_reset:
             game_elements["map_name"] = map_name_for_reset
             game_elements["loaded_map_name"] = map_name_for_reset
        # Update spawn data caches to reflect the reloaded (or original) level_data
        game_elements["enemy_spawns_data_cache"] = list(level_data_for_reset.get('enemies_list', []))
        game_elements["statue_spawns_data_cache"] = list(level_data_for_reset.get('statues_list', []))
    
    debug(f"GSM END: current_chest is now: {'None' if game_elements.get('current_chest') is None else type(game_elements.get('current_chest'))}. "
          f"Collectibles: {len(game_elements['collectible_list'])}, Enemies: {len(game_elements['enemy_list'])}, "
          f"Renderables: {len(game_elements['all_renderable_objects'])}")

    info("GSM: --- Game State Reset Finished (PySide6) ---")
    return game_elements.get("current_chest")


# --- Projectile Class Map (for network deserialization) ---
projectile_class_map: Dict[str, type] = {
    "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
    "BloodShot": BloodShot, "IceShard": IceShard,
    "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
}

def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    # ... (This function seems mostly okay from your previous version, ensure all entities have get_network_data) ...
    # The main change is ensuring player.alive() and other "liveness" checks are robust.
    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'enemies': {}, 'chest': None,
        'statues': [], 'projectiles': [], 'game_over': False,
        'map_name': game_elements.get("map_name", game_elements.get("loaded_map_name","unknown_map"))
    }
    player1: Optional[Player] = game_elements.get("player1")
    player2: Optional[Player] = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_list: List[Statue] = game_elements.get("statue_objects", []) # or statue_objects_list
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])

    if player1 and hasattr(player1, 'get_network_data'): state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'): state['p2'] = player2.get_network_data()

    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            # Send if alive, or if dead but death animation not finished, or if petrified
            is_enemy_renderable_for_net = (enemy.alive() or 
                                       (getattr(enemy, 'is_dead', False) and not getattr(enemy, 'death_animation_finished', True)) or
                                       getattr(enemy, 'is_petrified', False))
            if is_enemy_renderable_for_net:
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    for s_obj in statue_list:
        is_statue_renderable_for_net = ( (hasattr(s_obj, 'alive') and s_obj.alive()) or
                                      (getattr(s_obj, 'is_smashed', False) and not getattr(s_obj, 'death_animation_finished', True)) )
        if is_statue_renderable_for_net and hasattr(s_obj, 'get_network_data'):
            state['statues'].append(s_obj.get_network_data())

    if current_chest and hasattr(current_chest, 'rect'): # Basic check for validity
        # Send if alive or in a visual state like opening/opened/fading
        is_chest_renderable_for_net = current_chest.alive() or current_chest.state in ['opening', 'opened_visible', 'fading']
        if is_chest_renderable_for_net:
            state['chest'] = current_chest.get_network_data()
        else: state['chest'] = None # Explicitly None if not in a sendable state
    else: state['chest'] = None

    # Determine game_over based on P1 state (host controls game over)
    p1_truly_gone = True
    if player1 and player1._valid_init:
        if player1.alive(): # If P1 is logically alive
            p1_truly_gone = False
        elif player1.is_dead: # If logically dead
            if player1.is_petrified and not player1.is_stone_smashed: # Petrified but not smashed is not "gone" yet
                p1_truly_gone = False
            elif not player1.death_animation_finished: # Normal death anim not finished
                p1_truly_gone = False
            # Else (smashed or normal death anim finished), p1_truly_gone remains True
    state['game_over'] = p1_truly_gone

    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]
    return state


def set_network_game_state(network_state_data: Dict[str, Any],
                           game_elements: Dict[str, Any],
                           client_player_id: Optional[int] = None):
    # ... (This function seems mostly okay from your previous version) ...
    # Key things to ensure:
    # 1. When new enemies/statues/projectiles are created because they don't exist on client:
    #    - Use the FULL original spawn data if possible (from *_spawns_data_cache) for default attributes.
    #    - Then apply the specific network data.
    #    - Add them to all_renderable_objects.
    # 2. When updating existing entities, ensure their _valid_init flag is respected.
    # 3. Handle "kill" signals correctly (if server sends is_dead=True and death_animation_finished=True).

    player1: Optional[Player] = game_elements.get("player1")
    player2: Optional[Player] = game_elements.get("player2")
    enemy_list_ref: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client_ref: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")
    all_renderable_objects_ref: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list_ref: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list_ref: List[Any] = game_elements.get("collectible_list", [])

    # --- Rebuild renderable list from scratch to ensure correctness ---
    new_all_renderables: List[Any] = []
    current_all_renderables_set = set() # To avoid duplicates

    def add_to_renderables_if_new(obj: Any): # Renamed for clarity
        if obj is not None and obj not in current_all_renderables_set:
            new_all_renderables.append(obj)
            current_all_renderables_set.add(obj)

    # Add static elements first
    for static_list_key in ["platforms_list", "ladders_list", "hazards_list", "background_tiles_list"]:
        for static_item in game_elements.get(static_list_key, []):
            add_to_renderables_if_new(static_item)

    # Get spawn caches (crucial for re-instantiating entities if they don't exist on client)
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])
    if not enemy_spawns_data_cache and game_elements.get("level_data"):
        level_data_ref = game_elements["level_data"]
        if isinstance(level_data_ref, dict):
            enemy_spawns_data_cache = list(level_data_ref.get('enemies_list', [])) # Use list() for shallow copy
            game_elements["enemy_spawns_data_cache"] = enemy_spawns_data_cache
    
    statue_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("statue_spawns_data_cache", [])
    if not statue_spawns_data_cache and game_elements.get("level_data"):
        level_data_ref = game_elements["level_data"]
        if isinstance(level_data_ref, dict):
            statue_spawns_data_cache = list(level_data_ref.get('statues_list', []))
            game_elements["statue_spawns_data_cache"] = statue_spawns_data_cache


    # Player 1
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        # Determine if P1 should be rendered based on its state after update
        is_p1_renderable = player1._valid_init and (
            player1.alive() or
            (player1.is_dead and not player1.death_animation_finished and not player1.is_petrified) or # Normal death anim
            player1.is_petrified # Petrified or smashed
        )
        if is_p1_renderable: add_to_renderables_if_new(player1)

    # Player 2
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        is_p2_renderable = player2._valid_init and (
            player2.alive() or
            (player2.is_dead and not player2.death_animation_finished and not player2.is_petrified) or
            player2.is_petrified
        )
        if is_p2_renderable: add_to_renderables_if_new(player2)

    # Enemies
    new_enemy_list_client: List[Enemy] = []
    if 'enemies' in network_state_data and isinstance(network_state_data['enemies'], dict):
        received_enemy_data_map = network_state_data['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list_ref if hasattr(enemy, 'enemy_id')}
        
        for enemy_id_str, enemy_data_server in received_enemy_data_map.items():
            try: enemy_id_int = int(enemy_id_str)
            except ValueError: error(f"GSM Client: Invalid enemy_id '{enemy_id_str}' from server."); continue
            
            client_enemy: Optional[Enemy] = None
            if enemy_data_server.get('_valid_init', False): # Only process if server says it's valid
                if enemy_id_str in current_client_enemies_map:
                    client_enemy = current_client_enemies_map[enemy_id_str]
                else: # Enemy doesn't exist on client, try to create it
                    original_spawn_info: Optional[Dict[str,Any]] = None
                    if enemy_spawns_data_cache and 0 <= enemy_id_int < len(enemy_spawns_data_cache):
                        original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                    
                    spawn_pos_e_default = enemy_data_server.get('pos', (100.0,100.0)) # Fallback if no original_spawn_info
                    if original_spawn_info and 'start_pos' in original_spawn_info:
                        spawn_pos_e_default = tuple(map(float, original_spawn_info['start_pos']))
                    
                    patrol_area_e_obj: Optional[QRectF] = None
                    if original_spawn_info and 'patrol_rect_data' in original_spawn_info:
                        pr_data = original_spawn_info['patrol_rect_data']
                        if isinstance(pr_data, dict):
                            patrol_area_e_obj = QRectF(float(pr_data.get('x',0)), float(pr_data.get('y',0)),
                                                       float(pr_data.get('width',100)), float(pr_data.get('height',50)))
                    
                    enemy_color_name = enemy_data_server.get('color_name', 
                                                             original_spawn_info.get('type') if original_spawn_info else 'enemy_green')
                    enemy_props = enemy_data_server.get('properties', 
                                                        original_spawn_info.get('properties', {}) if original_spawn_info else {})
                    
                    debug(f"GSM Client: Creating new Enemy instance ID {enemy_id_int}, Color: {enemy_color_name} at {spawn_pos_e_default}")
                    client_enemy = Enemy(start_x=spawn_pos_e_default[0], start_y=spawn_pos_e_default[1],
                                         patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int,
                                         color_name=enemy_color_name, properties=enemy_props)

                if client_enemy and client_enemy._valid_init:
                    client_enemy.set_network_data(enemy_data_server)
                    new_enemy_list_client.append(client_enemy)
                    is_enemy_renderable_client = ( client_enemy.alive() or
                                                 (client_enemy.is_dead and not client_enemy.death_animation_finished and not client_enemy.is_petrified) or
                                                 client_enemy.is_petrified )
                    if is_enemy_renderable_client: add_to_renderables_if_new(client_enemy)
                elif client_enemy and not client_enemy._valid_init:
                    error(f"GSM Client: Failed to init/update enemy {enemy_id_str} from server data (still not valid after init).")
            # If server says _valid_init is false for an enemy, it's effectively removed from client view
    game_elements["enemy_list"] = new_enemy_list_client

    # Statues (similar logic to enemies)
    new_statue_list_client: List[Statue] = []
    if 'statues' in network_state_data and isinstance(network_state_data['statues'], list):
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data['statues'] if isinstance(s_data, dict) and 'id' in s_data}
        current_client_statues_map = {str(s.statue_id): s for s in statue_objects_list_client_ref if hasattr(s, 'statue_id')}
        
        for statue_id_server_str, statue_data_server in received_statue_data_map.items():
            client_statue: Optional[Statue] = None
            if statue_data_server.get('_valid_init', False):
                if statue_id_server_str in current_client_statues_map:
                    client_statue = current_client_statues_map[statue_id_server_str]
                else:
                    original_statue_spawn_info: Optional[Dict[str,Any]] = next((s_info for s_info in statue_spawns_data_cache if s_info.get('id') == statue_id_server_str), None)
                    s_pos_data = statue_data_server.get('pos', original_statue_spawn_info.get('pos') if original_statue_spawn_info else (200.0, 200.0))
                    s_props = statue_data_server.get('properties', original_statue_spawn_info.get('properties', {}) if original_statue_spawn_info else {})
                    
                    debug(f"GSM Client: Creating new Statue instance ID {statue_id_server_str} at {s_pos_data}")
                    client_statue = Statue(center_x=float(s_pos_data[0]), center_y=float(s_pos_data[1]),
                                           statue_id=statue_id_server_str, properties=s_props)

                if client_statue and client_statue._valid_init:
                    if hasattr(client_statue, 'set_network_data'): client_statue.set_network_data(statue_data_server)
                    new_statue_list_client.append(client_statue)
                    is_statue_renderable_client = ( client_statue.alive() or
                                                 (getattr(client_statue,'is_smashed',False) and not getattr(client_statue,'death_animation_finished',True)) )
                    if is_statue_renderable_client: add_to_renderables_if_new(client_statue)
                elif client_statue and not client_statue._valid_init:
                    error(f"GSM Client: Failed to init/update statue {statue_id_server_str} from server data.")
    game_elements["statue_objects"] = new_statue_list_client # or "statue_objects_list"

    # Chest
    new_collectible_list_client: List[Any] = []
    current_chest_obj_synced: Optional[Chest] = None
    if 'chest' in network_state_data:
        chest_data_server = network_state_data['chest']
        if chest_data_server and isinstance(chest_data_server, dict) and chest_data_server.get('_alive', True):
            # If current_chest_obj is None or invalid, try to create a new one
            if not current_chest_obj or not current_chest_obj._valid_init:
                chest_pos_midbottom = chest_data_server.get('pos_midbottom', (300.0, 300.0))
                # Assume properties for Chest are simple and can be passed if constructor supports it
                # chest_props_net = chest_data_server.get('properties', {})
                debug(f"GSM Client: Creating new Chest instance at {chest_pos_midbottom}")
                current_chest_obj = Chest(x=float(chest_pos_midbottom[0]), y=float(chest_pos_midbottom[1])) # properties=chest_props_net
            
            if current_chest_obj._valid_init:
                if hasattr(current_chest_obj, 'set_network_data'): current_chest_obj.set_network_data(chest_data_server)
                current_chest_obj_synced = current_chest_obj
                is_chest_renderable_client = current_chest_obj.alive() or current_chest_obj.state in ['opening', 'opened_visible', 'fading']
                if is_chest_renderable_client: add_to_renderables_if_new(current_chest_obj)
            else: current_chest_obj_synced = None
        # If chest_data_server is None, server indicates no chest, so client's should be None too
    game_elements["current_chest"] = current_chest_obj_synced
    if current_chest_obj_synced: new_collectible_list_client.append(current_chest_obj_synced)
    game_elements["collectible_list"] = new_collectible_list_client

    # Projectiles (similar logic to enemies/statues)
    new_projectiles_list_client: List[Any] = []
    if 'projectiles' in network_state_data and isinstance(network_state_data['projectiles'], list):
        # Map by ID for efficient lookup if projectiles persist across frames on client
        current_client_proj_map = {str(p.projectile_id): p for p in projectiles_list_ref if hasattr(p, 'projectile_id')}
        
        for proj_data_server in network_state_data['projectiles']:
            if not (isinstance(proj_data_server, dict) and 'id' in proj_data_server): continue
            proj_id_server_str = str(proj_data_server['id'])
            client_proj: Optional[Any] = None

            if proj_id_server_str in current_client_proj_map:
                client_proj = current_client_proj_map[proj_id_server_str]
            else: # New projectile from server
                owner_instance_client: Optional[Player] = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server == 1 and player1: owner_instance_client = player1
                elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server and 'type' in proj_data_server:
                    proj_type_name = proj_data_server['type']
                    ProjClass = projectile_class_map.get(proj_type_name)
                    if ProjClass:
                        pos_data_proj = proj_data_server['pos']
                        vel_data_proj = proj_data_server['vel']
                        # Direction for projectile constructor is usually normalized velocity vector
                        direction_qpointf = QPointF(float(vel_data_proj[0]), float(vel_data_proj[1]))
                        # Normalize if needed, or assume server sends appropriate direction vector if different from velocity
                        # length_dir = (direction_qpointf.x()**2 + direction_qpointf.y()**2)**0.5
                        # if length_dir > 1e-5: direction_qpointf /= length_dir
                        
                        client_proj = ProjClass(float(pos_data_proj[0]), float(pos_data_proj[1]), direction_qpointf, owner_instance_client)
                        client_proj.projectile_id = proj_id_server_str # Assign the ID from server
                        client_proj.game_elements_ref = game_elements # Important for projectiles
                    else: warning(f"GSM Client: Unknown projectile type '{proj_type_name}' from server.")
                elif not owner_instance_client: warning(f"GSM Client: Owner P{owner_id_from_server} for projectile {proj_id_server_str} not found.")
                else: warning(f"GSM Client: Insufficient data for new projectile {proj_id_server_str} (pos/vel/type/owner).")
            
            if client_proj:
                if hasattr(client_proj, 'set_network_data'): client_proj.set_network_data(proj_data_server)
                if client_proj.alive(): # Check if alive after setting network data
                    new_projectiles_list_client.append(client_proj)
                    add_to_renderables_if_new(client_proj)
    game_elements["projectiles_list"] = new_projectiles_list_client

    # Finalize all_renderable_objects list
    game_elements["all_renderable_objects"] = new_all_renderables
    
    # Game Over State
    game_elements['game_over_server_state'] = network_state_data.get('game_over', False)

    # Camera dimensions sync (if map changed or not yet set for client)
    server_map_name = network_state_data.get('map_name')
    camera_instance: Optional[Camera] = game_elements.get('camera')
    if server_map_name and camera_instance and \
       (game_elements.get('loaded_map_name') != server_map_name or not game_elements.get('camera_level_dims_set', False)):
        
        client_level_data = game_elements.get('level_data') # This should be set by client_logic map sync
        if client_level_data and isinstance(client_level_data, dict) and game_elements.get('loaded_map_name') == server_map_name:
            cam_lvl_w = float(client_level_data.get('level_pixel_width', C.GAME_WIDTH * 2))
            cam_min_x = float(client_level_data.get('level_min_x_absolute', 0.0))
            cam_min_y = float(client_level_data.get('level_min_y_absolute', 0.0))
            cam_max_y = float(client_level_data.get('level_max_y_absolute', C.GAME_HEIGHT))
            
            camera_instance.set_level_dimensions(cam_lvl_w, cam_min_x, cam_min_y, cam_max_y)
            game_elements['camera_level_dims_set'] = True # Mark that dimensions from map are now applied
            debug(f"GSM Client: Camera level dimensions updated for map '{server_map_name}'.")
        elif not client_level_data or game_elements.get('loaded_map_name') != server_map_name:
            # This case should ideally be handled by client_logic.py ensuring map is loaded before game starts.
            warning(f"GSM Client: Map name mismatch ('{game_elements.get('loaded_map_name')}' vs server '{server_map_name}') "
                    f"or client_level_data missing. Camera dimensions might be incorrect until map sync completes.")

    debug(f"GSM Client set_network_game_state END: Entities: P1:{'Yes' if player1 else 'No'}, P2:{'Yes' if player2 else 'No'}, "
          f"Enemies:{len(game_elements['enemy_list'])}, Statues:{len(game_elements['statue_objects'])}, "
          f"Chest:{'Yes' if game_elements['current_chest'] else 'No'}, Proj:{len(game_elements['projectiles_list'])}")