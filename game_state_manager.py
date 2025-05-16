########## START OF FILE: game_state_manager.py ##########

# game_state_manager.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.6 (Added missing imports, fixed Chest sync for client)
Manages game state, including reset and network synchronization.
"""
import pygame
import traceback
import os 
from typing import Optional, List, Dict, Any # Added Optional, List, Dict, Any

from game_setup import spawn_chest 
from enemy import Enemy 
from items import Chest 
from projectiles import Fireball, PoisonShot, BoltProjectile, BloodShot, IceShard, ShadowProjectile, GreyProjectile 
from assets import load_all_player_animations, load_gif_frames, resource_path # Added load_gif_frames, resource_path
import constants as C 

def reset_game_state(game_elements):
    """Resets the state of players, enemies, and collectibles."""
    print("DEBUG GSM: --- Resetting Platformer Game State ---") 
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", [])
    current_chest = game_elements.get("current_chest")
    player1_spawn_pos = game_elements.get("player1_spawn_pos")
    player2_spawn_pos = game_elements.get("player2_spawn_pos")
    all_sprites = game_elements.get("all_sprites")
    enemy_sprites = game_elements.get("enemy_sprites")
    collectible_sprites = game_elements.get("collectible_sprites")
    projectile_sprites = game_elements.get("projectile_sprites")
    camera = game_elements.get("camera")

    if player1 and hasattr(player1, 'reset_state'):
        print(f"DEBUG GSM: Resetting P1 at {player1_spawn_pos}") 
        player1.reset_state(player1_spawn_pos)
        if not player1.alive() and player1._valid_init: all_sprites.add(player1) 
        print("DEBUG GSM: P1 Reset complete.") 
    if player2 and hasattr(player2, 'reset_state'):
        print(f"DEBUG GSM: Resetting P2 at {player2_spawn_pos}") 
        player2.reset_state(player2_spawn_pos)
        if not player2.alive() and player2._valid_init: all_sprites.add(player2) 
        print("DEBUG GSM: P2 Reset complete.") 

    for enemy_instance in enemy_list:
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset()
            if enemy_instance._valid_init and not enemy_instance.alive(): 
                all_sprites.add(enemy_instance) 
                enemy_sprites.add(enemy_instance)
    print(f"DEBUG GSM: {len(enemy_list)} enemies processed for reset.") 

    if projectile_sprites:
        for proj in projectile_sprites: proj.kill()
        projectile_sprites.empty()
        print("DEBUG GSM: Projectiles cleared.") 


    if current_chest and current_chest.alive(): current_chest.kill()
    print(f"DEBUG GSM: Existing chest killed (if any).") 


    new_chest = spawn_chest(game_elements.get("platform_sprites"), game_elements.get("ground_level_y"))
    if new_chest:
        all_sprites.add(new_chest)
        collectible_sprites.add(new_chest)
        game_elements["current_chest"] = new_chest 
        print("DEBUG GSM: Chest respawned.") 
    else:
        game_elements["current_chest"] = None 
        print("DEBUG GSM: Failed to respawn chest or Chest class not available.") 

    if camera: camera.set_pos(0,0) 
    print("DEBUG GSM: Camera position reset.") 

    print("DEBUG GSM: --- Game State Reset Finished ---\n") 
    return new_chest 

def get_network_game_state(game_elements):
    """Gathers all relevant game state for network transmission."""
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", [])
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    projectile_sprites = game_elements.get("projectile_sprites", pygame.sprite.Group())

    state = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 'game_over': False, 'projectiles': []}

    if player1 and hasattr(player1, 'get_network_data'):
        state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'):
        state['p2'] = player2.get_network_data()

    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            if enemy.alive() or (enemy.is_dead and not enemy.death_animation_finished):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    if current_chest and hasattr(current_chest, 'rect'): 
        if current_chest.alive() or current_chest.state in ['fading', 'killed']: # Send even if just killed this frame
            state['chest'] = {
                'pos': (current_chest.rect.centerx, current_chest.rect.centery),
                'is_collected_internal': getattr(current_chest, 'is_collected_flag_internal', False),
                'chest_state': current_chest.state, 
                'animation_timer': getattr(current_chest, 'animation_timer', 0), 
                'time_opened_start': getattr(current_chest, 'time_opened_start', 0),
                'fade_alpha': getattr(current_chest, 'fade_alpha', 255),
                'current_frame_index': getattr(current_chest, 'current_frame_index', 0),
            }
        else: 
            state['chest'] = None 
    else: 
        state['chest'] = None
    
    p1_truly_gone = True 
    if player1 and player1._valid_init: 
        if player1.alive(): 
            if hasattr(player1, 'is_dead') and player1.is_dead: 
                if hasattr(player1, 'death_animation_finished') and not player1.death_animation_finished:
                    p1_truly_gone = False 
            else: 
                p1_truly_gone = False
    state['game_over'] = p1_truly_gone 

    state['projectiles'] = [proj.get_network_data() for proj in projectile_sprites if hasattr(proj, 'get_network_data')]
    return state

def set_network_game_state(network_state_data, game_elements, client_player_id=None): 
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", []) 
    current_chest: Optional[Chest] = game_elements.get("current_chest") 
    all_sprites: pygame.sprite.Group = game_elements.get("all_sprites")
    enemy_sprites: pygame.sprite.Group = game_elements.get("enemy_sprites")
    collectible_sprites: pygame.sprite.Group = game_elements.get("collectible_sprites")
    projectile_sprites: pygame.sprite.Group = game_elements.get("projectile_sprites", pygame.sprite.Group())
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])


    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        if player1._valid_init and not player1.is_dead and not player1.alive():
             all_sprites.add(player1)

    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        if player2._valid_init and not player2.is_dead and not player2.alive():
             all_sprites.add(player2)

    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies']
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str)
            if enemy_data_from_server.get('_valid_init', False): 
                if enemy_id_str in current_client_enemies_map: 
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    if hasattr(client_enemy, 'set_network_data'):
                        client_enemy.set_network_data(enemy_data_from_server)
                        if client_enemy._valid_init and not client_enemy.alive():
                            if (client_enemy.is_dead and not client_enemy.death_animation_finished) or \
                               (not client_enemy.is_dead):
                                 all_sprites.add(client_enemy); enemy_sprites.add(client_enemy)
                else: 
                    try:
                        spawn_pos_e_default = enemy_data_from_server.get('pos', (0,0)) 
                        patrol_area_e_obj = None
                        if enemy_id_int < len(enemy_spawns_data_cache):
                            original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                            spawn_pos_e_default = original_spawn_info.get('pos', spawn_pos_e_default)
                            patrol_data_from_level = original_spawn_info.get('patrol')
                            if patrol_data_from_level:
                                try: patrol_area_e_obj = pygame.Rect(patrol_data_from_level)
                                except TypeError: print(f"Client: Invalid patrol data from cache for new enemy {enemy_id_int}.")
                        else:
                            print(f"Client: No original spawn data in cache for new enemy_id {enemy_id_int}.")

                        new_enemy_instance = Enemy(spawn_pos_e_default[0], spawn_pos_e_default[1],
                                             patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int)
                        
                        if new_enemy_instance._valid_init:
                            server_color_name = enemy_data_from_server.get('color_name')
                            if server_color_name and hasattr(new_enemy_instance, 'color_name') and new_enemy_instance.color_name != server_color_name:
                                new_enemy_instance.color_name = server_color_name
                                enemy_asset_folder = os.path.join('characters', server_color_name)
                                new_enemy_instance.animations = load_all_player_animations(
                                    relative_asset_folder=enemy_asset_folder
                                )
                                if new_enemy_instance.animations is None:
                                    print(f"Client CRITICAL: Failed to reload animations for enemy {enemy_id_int} with server color {server_color_name} from '{enemy_asset_folder}'")
                                    new_enemy_instance._valid_init = False
                                    if hasattr(C, 'BLUE'):
                                        new_enemy_instance.image = pygame.Surface((30, 40)).convert_alpha()
                                        new_enemy_instance.image.fill(C.BLUE)
                                        new_enemy_instance.rect = new_enemy_instance.image.get_rect(midbottom=(spawn_pos_e_default[0], spawn_pos_e_default[1]))
                                else:
                                    initial_idle_animation_new_color = new_enemy_instance.animations.get('idle')
                                    if initial_idle_animation_new_color and len(initial_idle_animation_new_color) > 0:
                                        new_enemy_instance.image = initial_idle_animation_new_color[0]
                                    else:
                                        if hasattr(C, 'BLUE'):
                                            new_enemy_instance.image = pygame.Surface((30, 40)).convert_alpha()
                                            new_enemy_instance.image.fill(C.BLUE)
                                    new_enemy_instance.rect = new_enemy_instance.image.get_rect(midbottom=(spawn_pos_e_default[0], spawn_pos_e_default[1]))
                        
                        if new_enemy_instance._valid_init:
                            new_enemy_instance.set_network_data(enemy_data_from_server)
                            all_sprites.add(new_enemy_instance); enemy_sprites.add(new_enemy_instance)
                            enemy_list.append(new_enemy_instance)
                    except Exception as e:
                        print(f"Client: Error creating new instance of enemy {enemy_id_str}: {e}")
                        traceback.print_exc()
            elif enemy_id_str in current_client_enemies_map: 
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

        server_enemy_ids_present_in_message = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove_fully = set(current_client_enemies_map.keys()) - server_enemy_ids_present_in_message
        for removed_id_str_fully in client_enemy_ids_to_remove_fully:
            if removed_id_str_fully in current_client_enemies_map:
                enemy_to_remove_fully = current_client_enemies_map[removed_id_str_fully]
                if enemy_to_remove_fully.alive(): enemy_to_remove_fully.kill()
                if enemy_to_remove_fully in enemy_list: enemy_list.remove(enemy_to_remove_fully)

    if 'chest' in network_state_data:
        chest_data_from_server = network_state_data['chest']
        if chest_data_from_server and isinstance(Chest, type): 
            server_chest_pos_center = chest_data_from_server.get('pos')
            server_chest_state = chest_data_from_server.get('chest_state')
            
            if server_chest_state == 'killed' or not server_chest_pos_center: 
                if current_chest and current_chest.alive():
                    current_chest.kill()
                game_elements["current_chest"] = None
            else: 
                if not current_chest or not current_chest.alive() or \
                   (current_chest and current_chest.state == 'killed' and server_chest_state != 'killed'): 
                    if current_chest and current_chest.alive(): current_chest.kill() 
                    
                    temp_chest_height_approx = 30 
                    # Use frames_closed as it's more likely to be valid than frames_open if there was a partial load error
                    # This is primarily for positioning, actual frames will be synced.
                    temp_frames = Chest(0,0).frames_closed # Get default closed frames from a temp instance
                    if temp_frames and len(temp_frames[0].get_size()) == 2:
                         temp_chest_height_approx = temp_frames[0].get_height()
                    
                    chest_spawn_x_midbottom = server_chest_pos_center[0]
                    chest_spawn_y_midbottom = server_chest_pos_center[1] + temp_chest_height_approx / 2

                    current_chest = Chest(chest_spawn_x_midbottom, chest_spawn_y_midbottom)
                    if current_chest._valid_init:
                        all_sprites.add(current_chest)
                        collectible_sprites.add(current_chest)
                        game_elements["current_chest"] = current_chest
                    else:
                        game_elements["current_chest"] = None
                        current_chest = None 
                
                if current_chest: 
                    current_chest.state = server_chest_state
                    current_chest.is_collected_flag_internal = chest_data_from_server.get('is_collected_internal', False)
                    current_chest.animation_timer = chest_data_from_server.get('animation_timer', pygame.time.get_ticks())
                    current_chest.time_opened_start = chest_data_from_server.get('time_opened_start', 0)
                    current_chest.fade_alpha = chest_data_from_server.get('fade_alpha', 255)
                    
                    net_frame_index = chest_data_from_server.get('current_frame_index', 0)
                    
                    if current_chest.state in ['opening', 'opened', 'fading']:
                        current_chest.frames_current_set = current_chest.frames_open
                    else: 
                        current_chest.frames_current_set = current_chest.frames_closed

                    if current_chest.frames_current_set and 0 <= net_frame_index < len(current_chest.frames_current_set):
                        current_chest.current_frame_index = net_frame_index
                    else: 
                        current_chest.current_frame_index = 0 
                        if current_chest.frames_current_set: 
                             current_chest.current_frame_index = max(0, len(current_chest.frames_current_set) -1)

                    current_chest.rect.center = server_chest_pos_center 
                    current_chest.pos = pygame.math.Vector2(current_chest.rect.midbottom) 
                    
                    if current_chest.frames_current_set and 0 <= current_chest.current_frame_index < len(current_chest.frames_current_set):
                        current_chest.image = current_chest.frames_current_set[current_chest.current_frame_index].copy()
                        if current_chest.state == 'fading':
                            current_chest.image.set_alpha(max(0, min(255,current_chest.fade_alpha)))
                    elif current_chest.frames_closed and current_chest.frames_closed[0]: 
                         current_chest.image = current_chest.frames_closed[0]
                    # Player healing is server-authoritative, client just shows visuals

        elif not network_state_data.get('chest'): 
            if current_chest and current_chest.alive():
                current_chest.kill()
            game_elements["current_chest"] = None


    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if 'id' in p_data}
        current_client_proj_map = {p.projectile_id: p for p in projectile_sprites if hasattr(p, 'projectile_id')}

        projectile_class_map = {
            "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
            "BloodShot": BloodShot, "IceShard": IceShard,
            "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile 
        }

        for proj_id_server, proj_data_server in received_proj_data_map.items():
            if proj_id_server in current_client_proj_map:
                existing_proj_client = current_client_proj_map[proj_id_server]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
            else: 
                owner_instance_client = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server is not None:
                    if owner_id_from_server == 1 and player1: owner_instance_client = player1
                    elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server and 'type' in proj_data_server:
                    proj_type_name = proj_data_server['type']
                    ProjClass = projectile_class_map.get(proj_type_name)

                    if ProjClass:
                        direction_vec_server = pygame.math.Vector2(proj_data_server['vel'])
                        if direction_vec_server.length_squared() == 0:
                            direction_vec_server = pygame.math.Vector2(1,0) if owner_instance_client.facing_right else pygame.math.Vector2(-1,0)
                        try:
                            new_proj_client = ProjClass(proj_data_server['pos'][0], proj_data_server['pos'][1],
                                                 direction_vec_server, owner_instance_client)
                            new_proj_client.projectile_id = proj_id_server 
                            if hasattr(new_proj_client, 'set_network_data'):
                                new_proj_client.set_network_data(proj_data_server) 
                            projectile_sprites.add(new_proj_client)
                            all_sprites.add(new_proj_client)
                        except Exception as e:
                            print(f"GSM: Error creating new projectile of type {proj_type_name} (ID: {proj_id_server}): {e}") 
                            traceback.print_exc()

        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - set(received_proj_data_map.keys())
        for removed_proj_id_client in client_proj_ids_to_remove:
            if removed_proj_id_client in current_client_proj_map:
                proj_to_kill_client = current_client_proj_map[removed_proj_id_client]
                if proj_to_kill_client.alive(): proj_to_kill_client.kill()

########## END OF FILE: game_state_manager.py ##########