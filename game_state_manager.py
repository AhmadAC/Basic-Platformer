#################### START OF FILE: game_state_manager.py ####################

# game_state_manager.py
# -*- coding: utf-8 -*-
"""
Manages game state, including reset and network synchronization for PySide6.
"""
# version 2.0.1 (PySide6 Refactor - Corrected current_height and Chest frame access)
import os
from typing import Optional, List, Dict, Any
from PySide6.QtCore import QRectF, QPointF, QSize, Qt
# Game-specific imports (refactored classes)
from game_setup import spawn_chest_qt
from enemy import Enemy
from items import Chest
from statue import Statue
from projectiles import (
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
import constants as C

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL GAME_STATE_MANAGER: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

try:
    import pygame 
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_gsm = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_gsm) * 1000)


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    info("GSM: --- Resetting Game State (PySide6) ---")
    
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")
    
    player1_spawn_pos_tuple = game_elements.get("player1_spawn_pos")
    player2_spawn_pos_tuple = game_elements.get("player2_spawn_pos")
    
    all_renderable_objects: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    
    if player1 and hasattr(player1, 'reset_state'):
        debug(f"GSM: Resetting P1 at {player1_spawn_pos_tuple}")
        player1.reset_state(player1_spawn_pos_tuple)
        if player1._valid_init and not player1.alive():
            if player1 not in all_renderable_objects: all_renderable_objects.append(player1)
        debug("GSM: P1 Reset complete.")
        
    if player2 and hasattr(player2, 'reset_state'):
        debug(f"GSM: Resetting P2 at {player2_spawn_pos_tuple}")
        player2.reset_state(player2_spawn_pos_tuple)
        if player2._valid_init and not player2.alive():
            if player2 not in all_renderable_objects: all_renderable_objects.append(player2)
        debug("GSM: P2 Reset complete.")

    for enemy_instance in enemy_list:
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset() 
            if enemy_instance._valid_init and not any(enemy_instance is obj for obj in all_renderable_objects if isinstance(obj, Enemy) and obj.enemy_id == enemy_instance.enemy_id):
                 all_renderable_objects.append(enemy_instance)
    debug(f"GSM: {len(enemy_list)} enemies processed for reset.")

    for statue_instance in statue_objects_list:
        if hasattr(statue_instance, 'is_smashed'): statue_instance.is_smashed = False
        if hasattr(statue_instance, 'is_dead'): statue_instance.is_dead = False
        if hasattr(statue_instance, 'death_animation_finished'): statue_instance.death_animation_finished = False
        if hasattr(statue_instance, '_alive'): statue_instance._alive = True
        if hasattr(statue_instance, 'image') and hasattr(statue_instance, 'initial_image_frames') and \
           statue_instance.initial_image_frames and not statue_instance.initial_image_frames[0].isNull():
            statue_instance.image = statue_instance.initial_image_frames[0]
            if hasattr(statue_instance, '_update_rect_from_image_and_pos'): statue_instance._update_rect_from_image_and_pos()
        if not any(statue_instance is obj for obj in all_renderable_objects if isinstance(obj, Statue) and obj.statue_id == statue_instance.statue_id):
            all_renderable_objects.append(statue_instance)
    debug(f"GSM: {len(statue_objects_list)} statues processed for state reset.")

    projectiles_to_remove = [p for p in all_renderable_objects if any(isinstance(p, proj_class) for proj_class in [Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard, ShadowProjectile, GreyProjectile])]
    for p_rem in projectiles_to_remove:
        if hasattr(p_rem, 'kill'): p_rem.kill()
        if p_rem in all_renderable_objects: all_renderable_objects.remove(p_rem)
    projectiles_list.clear()
    debug("GSM: Projectiles cleared from lists.")

    collectible_list_ref = game_elements.get("collectible_list", [])
    if current_chest_obj and current_chest_obj.alive():
        current_chest_obj.kill()
        if current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)
        if current_chest_obj in collectible_list_ref: collectible_list_ref.remove(current_chest_obj)
    debug(f"GSM: Existing chest removed (if any).")

    # Use ground_level_y_ref from game_elements for spawning chest
    ground_y_for_chest = game_elements.get("ground_level_y_ref", float(C.TILE_SIZE * 15)) # Fallback height
    new_chest_obj = spawn_chest_qt(game_elements.get("platforms_list", []), ground_y_for_chest)
    
    if new_chest_obj:
        if new_chest_obj not in all_renderable_objects: all_renderable_objects.append(new_chest_obj)
        collectible_list_ref = [new_chest_obj] # Replace or ensure it's the only one
        game_elements["current_chest"] = new_chest_obj
        debug("GSM: Chest respawned.")
    else:
        game_elements["current_chest"] = None
        collectible_list_ref = []
        debug("GSM: Failed to respawn chest.")
    game_elements["collectible_list"] = collectible_list_ref # Update main list
    
    camera = game_elements.get("camera")
    if camera: camera.set_pos(0.0, 0.0)
    debug("GSM: Camera position reset.")

    info("GSM: --- Game State Reset Finished (PySide6) ---\n")
    return new_chest_obj


def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 
                             'statues': [], 'projectiles': [], 'game_over': False}
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
            if enemy.alive() or (enemy.is_dead and not enemy.death_animation_finished):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    for s_obj in statue_list:
        if s_obj.alive() or (s_obj.is_smashed and not s_obj.death_animation_finished):
            if hasattr(s_obj, 'get_network_data'):
                state['statues'].append(s_obj.get_network_data())

    if current_chest and hasattr(current_chest, 'rect'): 
        if current_chest.alive() or current_chest.state in ['fading', 'killed']:
            state['chest'] = {
                'pos_center': (current_chest.rect.center().x(), current_chest.rect.center().y()),
                'is_collected_internal': getattr(current_chest, 'is_collected_flag_internal', False),
                'chest_state': current_chest.state, 
                'animation_timer': getattr(current_chest, 'animation_timer', 0), 
                'time_opened_start': getattr(current_chest, 'time_opened_start', 0),
                'fade_alpha': getattr(current_chest, 'fade_alpha', 255),
                'current_frame_index': getattr(current_chest, 'current_frame_index', 0),
            }
        else: state['chest'] = None
    else: state['chest'] = None
    
    p1_truly_gone = True
    if player1 and player1._valid_init: 
        if player1.alive():
            if player1.is_dead:
                if player1.is_petrified and not player1.is_stone_smashed: p1_truly_gone = False
                elif not player1.death_animation_finished: p1_truly_gone = False
            else: p1_truly_gone = False
    state['game_over'] = p1_truly_gone 

    state['projectiles'] = [proj.get_network_data() for proj in projectiles_list if hasattr(proj, 'get_network_data') and proj.alive()]
    
    return state


def set_network_game_state(network_state_data: Dict[str, Any], 
                           game_elements: Dict[str, Any], 
                           client_player_id: Optional[int] = None): 
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list_client: List[Statue] = game_elements.get("statue_objects", [])
    current_chest_obj: Optional[Chest] = game_elements.get("current_chest")
    
    all_renderable_objects: List[Any] = game_elements.get("all_renderable_objects", [])
    projectiles_list: List[Any] = game_elements.get("projectiles_list", [])
    collectible_list: List[Chest] = game_elements.get("collectible_list", []) # Ensure this is fetched
    
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])

    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        if player1._valid_init and not player1.alive():
            is_p1_gone = player1.is_dead and (not player1.is_petrified or player1.is_stone_smashed) and player1.death_animation_finished
            if not is_p1_gone and player1 not in all_renderable_objects: all_renderable_objects.append(player1)
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        if player2._valid_init and not player2.alive():
            is_p2_gone = player2.is_dead and (not player2.is_petrified or player2.is_stone_smashed) and player2.death_animation_finished
            if not is_p2_gone and player2 not in all_renderable_objects: all_renderable_objects.append(player2)

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
                    if client_enemy.alive() and client_enemy not in all_renderable_objects:
                        all_renderable_objects.append(client_enemy)
                    elif not client_enemy.alive() and client_enemy in all_renderable_objects:
                        all_renderable_objects.remove(client_enemy)
                else: 
                    spawn_pos_e_default = enemy_data_server.get('pos', (0.0,0.0))
                    patrol_area_e_obj: Optional[QRectF] = None
                    enemy_color_name_cache = None
                    if enemy_id_int < len(enemy_spawns_data_cache):
                        original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                        spawn_pos_e_default = original_spawn_info.get('pos', spawn_pos_e_default)
                        patrol_data_raw = original_spawn_info.get('patrol') 
                        if patrol_data_raw: 
                             patrol_area_e_obj = QRectF(float(patrol_data_raw[0]), float(patrol_data_raw[1]), float(patrol_data_raw[2]), float(patrol_data_raw[3]))
                        enemy_color_name_cache = original_spawn_info.get('enemy_color_id')
                    final_color = enemy_data_server.get('color_name', enemy_color_name_cache)
                    new_enemy = Enemy(spawn_pos_e_default[0], spawn_pos_e_default[1],
                                      patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int, color_name=final_color)
                    if new_enemy._valid_init:
                        new_enemy.set_network_data(enemy_data_server)
                        if new_enemy.alive(): all_renderable_objects.append(new_enemy)
                        enemy_list.append(new_enemy)
            elif enemy_id_str in current_client_enemies_map: 
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in all_renderable_objects: all_renderable_objects.remove(enemy_to_remove)
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)
        client_ids_to_remove = set(current_client_enemies_map.keys()) - active_server_enemy_ids
        for removed_id_str in client_ids_to_remove:
            if removed_id_str in current_client_enemies_map:
                enemy_to_kill = current_client_enemies_map[removed_id_str]
                if enemy_to_kill.alive(): enemy_to_kill.kill()
                if enemy_to_kill in all_renderable_objects: all_renderable_objects.remove(enemy_to_kill)
                if enemy_to_kill in enemy_list: enemy_list.remove(enemy_to_kill)
        game_elements["enemy_list"] = [e for e in enemy_list if e.alive()]


    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if 'id' in s_data}
        current_client_statues_map = {s.statue_id: s for s in statue_objects_list_client if hasattr(s, 'statue_id')}
        active_server_statue_ids = set()
        for statue_id_server, statue_data_server in received_statue_data_map.items():
            active_server_statue_ids.add(statue_id_server)
            if statue_data_server.get('_valid_init', False):
                if statue_id_server in current_client_statues_map:
                    client_statue = current_client_statues_map[statue_id_server]
                    client_statue.set_network_data(statue_data_server)
                    if client_statue.alive() and client_statue not in all_renderable_objects:
                        all_renderable_objects.append(client_statue)
                    elif not client_statue.alive() and client_statue in all_renderable_objects:
                        all_renderable_objects.remove(client_statue)
                else: 
                    s_pos = statue_data_server.get('pos', (0.0,0.0))
                    new_statue = Statue(s_pos[0], s_pos[1], statue_id=statue_id_server)
                    if new_statue._valid_init:
                        new_statue.set_network_data(statue_data_server)
                        if new_statue.alive(): all_renderable_objects.append(new_statue)
                        statue_objects_list_client.append(new_statue)
            elif statue_id_server in current_client_statues_map:
                statue_to_remove = current_client_statues_map[statue_id_server]
                if statue_to_remove.alive(): statue_to_remove.kill()
                if statue_to_remove in all_renderable_objects: all_renderable_objects.remove(statue_to_remove)
                if statue_to_remove in statue_objects_list_client: statue_objects_list_client.remove(statue_to_remove)
        client_statue_ids_to_remove = set(current_client_statues_map.keys()) - active_server_statue_ids
        for removed_s_id in client_statue_ids_to_remove:
            if removed_s_id in current_client_statues_map:
                statue_to_kill = current_client_statues_map[removed_s_id]
                if statue_to_kill.alive(): statue_to_kill.kill()
                if statue_to_kill in all_renderable_objects: all_renderable_objects.remove(statue_to_kill)
                if statue_to_kill in statue_objects_list_client: statue_objects_list_client.remove(statue_to_kill)
        game_elements["statue_objects"] = [s for s in statue_objects_list_client if s.alive()]


    if 'chest' in network_state_data:
        chest_data_server = network_state_data['chest']
        if chest_data_server and isinstance(Chest, type):
            server_chest_pos_center_tuple = chest_data_server.get('pos_center')
            server_chest_state = chest_data_server.get('chest_state')
            if server_chest_state == 'killed' or not server_chest_pos_center_tuple:
                if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill()
                if current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)
                if current_chest_obj in collectible_list: collectible_list.remove(current_chest_obj) # Use fetched list
                game_elements["current_chest"] = None
            else:
                if not current_chest_obj or not current_chest_obj.alive() or \
                   (current_chest_obj.state == 'killed' and server_chest_state != 'killed'):
                    if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill()
                    if current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)
                    if current_chest_obj in collectible_list: collectible_list.remove(current_chest_obj)
                    
                    temp_chest_height = float(C.TILE_SIZE) # Default
                    # Attempt to get a more accurate height from a temporary Chest instance if possible
                    try:
                        # This relies on Chest class being fully importable and instantiable
                        # It might be safer to have a static CHEST_DEFAULT_HEIGHT constant
                        temp_chest_for_dims = Chest(0,0) # Create dummy to get frame height
                        if temp_chest_for_dims.frames_closed and not temp_chest_for_dims.frames_closed[0].isNull():
                             temp_chest_height = float(temp_chest_for_dims.frames_closed[0].height())
                    except Exception: pass 
                    
                    chest_midbottom_x = server_chest_pos_center_tuple[0]
                    chest_midbottom_y = server_chest_pos_center_tuple[1] + temp_chest_height / 2.0
                    current_chest_obj = Chest(chest_midbottom_x, chest_midbottom_y)
                    if current_chest_obj._valid_init:
                        all_renderable_objects.append(current_chest_obj); collectible_list.append(current_chest_obj)
                        game_elements["current_chest"] = current_chest_obj
                    else: game_elements["current_chest"] = None; current_chest_obj = None
                
                if current_chest_obj: 
                    current_chest_obj.state = server_chest_state
                    current_chest_obj.is_collected_flag_internal = chest_data_server.get('is_collected_internal', False)
                    current_chest_obj.animation_timer = chest_data_server.get('animation_timer', get_current_ticks())
                    current_chest_obj.time_opened_start = chest_data_server.get('time_opened_start', 0)
                    current_chest_obj.fade_alpha = chest_data_server.get('fade_alpha', 255)
                    current_chest_obj.current_frame_index = chest_data_server.get('current_frame_index', 0)
                    current_chest_obj.rect.moveCenter(QPointF(server_chest_pos_center_tuple[0], server_chest_pos_center_tuple[1]))
                    current_chest_obj.pos_midbottom = QPointF(current_chest_obj.rect.center().x(), current_chest_obj.rect.bottom())
        elif not network_state_data.get('chest'): 
            if current_chest_obj and current_chest_obj.alive(): current_chest_obj.kill()
            if current_chest_obj in all_renderable_objects: all_renderable_objects.remove(current_chest_obj)
            if current_chest_obj in collectible_list: collectible_list.remove(current_chest_obj)
            game_elements["current_chest"] = None
        game_elements["collectible_list"] = [c for c in collectible_list if c.alive()]


    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if 'id' in p_data}
        current_client_proj_map = {p.projectile_id: p for p in projectiles_list if hasattr(p, 'projectile_id')}
        active_server_proj_ids = set()
        projectile_class_map = {
            "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
            "BloodShot": BloodShot, "IceShard": IceShard,
            "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
        }
        for proj_id_server, proj_data_server in received_proj_data_map.items():
            active_server_proj_ids.add(proj_id_server)
            if proj_id_server in current_client_proj_map:
                existing_proj_client = current_client_proj_map[proj_id_server]
                if hasattr(existing_proj_client, 'set_network_data'): existing_proj_client.set_network_data(proj_data_server)
                if existing_proj_client.alive() and existing_proj_client not in all_renderable_objects: all_renderable_objects.append(existing_proj_client)
            else: 
                owner_instance_client = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server == 1 and player1: owner_instance_client = player1
                elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server and 'type' in proj_data_server:
                    proj_type_name = proj_data_server['type']
                    ProjClass = projectile_class_map.get(proj_type_name)
                    if ProjClass:
                        net_vel = proj_data_server['vel']
                        direction_qpointf = QPointF(net_vel[0], net_vel[1]) 
                        
                        new_proj_client = ProjClass(proj_data_server['pos'][0], proj_data_server['pos'][1],
                                                 direction_qpointf, owner_instance_client)
                        new_proj_client.projectile_id = proj_id_server
                        if hasattr(new_proj_client, 'set_network_data'): new_proj_client.set_network_data(proj_data_server) 
                        projectiles_list.append(new_proj_client)
                        all_renderable_objects.append(new_proj_client)
                    else: warning(f"GSM Client: Unknown projectile type '{proj_type_name}' from server.")
                else: warning(f"GSM Client: Insufficient data for projectile {proj_id_server}.")
        
        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - active_server_proj_ids
        for removed_proj_id in client_proj_ids_to_remove:
            if removed_proj_id in current_client_proj_map:
                proj_to_kill = current_client_proj_map[removed_proj_id]
                if proj_to_kill.alive(): proj_to_kill.kill()
                if proj_to_kill in projectiles_list: projectiles_list.remove(proj_to_kill)
                if proj_to_kill in all_renderable_objects: all_renderable_objects.remove(proj_to_kill)
        game_elements["projectiles_list"] = [p for p in projectiles_list if p.alive()]

    game_elements["all_renderable_objects"] = [obj for obj in all_renderable_objects if hasattr(obj, 'alive') and obj.alive()]

#################### END OF FILE: game_state_manager.py ####################