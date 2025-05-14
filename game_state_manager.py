########## START OF FILE: game_state_manager.py ##########

# game_state_manager.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.3 (Players always update from network state on client; enemy color sync)
Manages game state, including reset and network synchronization.
"""
import pygame
import traceback
import os # Added for os.path.join
from game_setup import spawn_chest # For respawning chest
from enemy import Enemy # For creating new enemies on client
from items import Chest # For type checking and creating new chests on client
from projectiles import Fireball # For creating projectiles on client
from assets import load_all_player_animations # Added for reloading enemy animations
import constants as C # Added for fallback color C.BLUE

def reset_game_state(game_elements):
    """Resets the state of players, enemies, and collectibles."""
    print("DEBUG GSM: --- Resetting Platformer Game State ---") # DEBUG
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
        print(f"DEBUG GSM: Resetting P1 at {player1_spawn_pos}") # DEBUG
        player1.reset_state(player1_spawn_pos)
        if not player1.alive() and player1._valid_init: all_sprites.add(player1) # Ensure in group
        print("DEBUG GSM: P1 Reset complete.") # DEBUG
    if player2 and hasattr(player2, 'reset_state'):
        print(f"DEBUG GSM: Resetting P2 at {player2_spawn_pos}") # DEBUG
        player2.reset_state(player2_spawn_pos)
        if not player2.alive() and player2._valid_init: all_sprites.add(player2) # Ensure in group
        print("DEBUG GSM: P2 Reset complete.") # DEBUG

    for enemy_instance in enemy_list:
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset()
            if enemy_instance._valid_init and not enemy_instance.alive(): # If reset somehow made it not alive but valid
                all_sprites.add(enemy_instance) # Re-add to ensure it's drawn/updated if it revives
                enemy_sprites.add(enemy_instance)
    print(f"DEBUG GSM: {len(enemy_list)} enemies processed for reset.") # DEBUG

    if projectile_sprites:
        for proj in projectile_sprites: proj.kill()
        projectile_sprites.empty()
        print("DEBUG GSM: Projectiles cleared.") # DEBUG


    if current_chest and current_chest.alive(): current_chest.kill()
    print(f"DEBUG GSM: Existing chest killed (if any).") # DEBUG


    new_chest = spawn_chest(game_elements.get("platform_sprites"), game_elements.get("ground_level_y"))
    if new_chest:
        all_sprites.add(new_chest)
        collectible_sprites.add(new_chest)
        game_elements["current_chest"] = new_chest # Update the reference in game_elements
        print("DEBUG GSM: Chest respawned.") # DEBUG
    else:
        game_elements["current_chest"] = None # Ensure it's None if spawn fails
        print("DEBUG GSM: Failed to respawn chest or Chest class not available.") # DEBUG

    if camera: camera.set_pos(0,0) # Reset camera position to default
    print("DEBUG GSM: Camera position reset.") # DEBUG

    print("DEBUG GSM: --- Game State Reset Finished ---\n") # DEBUG
    return new_chest # Return the new chest so main can update its reference if needed

def get_network_game_state(game_elements):
    """Gathers all relevant game state for network transmission."""
    # print("DEBUG GSM (get_network_game_state): Gathering state...") # DEBUG
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", [])
    current_chest = game_elements.get("current_chest")
    projectile_sprites = game_elements.get("projectile_sprites", pygame.sprite.Group()) # Default to empty group

    state = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 'game_over': False, 'projectiles': []}

    if player1 and hasattr(player1, 'get_network_data'):
        state['p1'] = player1.get_network_data()
        # print(f"DEBUG GSM (get_network_game_state): P1 data: {state['p1']}") # DEBUG
    if player2 and hasattr(player2, 'get_network_data'):
        state['p2'] = player2.get_network_data()
        # print(f"DEBUG GSM (get_network_game_state): P2 data: {state['p2']}") # DEBUG


    # Include enemies that are alive or in the process of dying (animation not finished)
    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            if enemy.alive() or (enemy.is_dead and not enemy.death_animation_finished):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    if current_chest and current_chest.alive() and hasattr(current_chest, 'rect'):
        state['chest'] = {
            'pos': (current_chest.rect.centerx, current_chest.rect.centery),
            'is_collected': getattr(current_chest, 'is_collected', False)
        }

    # Determine game_over based on P1's state (typical for host/P1 centric games)
    p1_truly_gone = True # Assume P1 is gone
    if player1 and player1._valid_init: # If P1 was properly initialized
        if player1.alive(): # Is in sprite groups (could be dead but animating)
            if hasattr(player1, 'is_dead') and player1.is_dead: # Logically dead
                if hasattr(player1, 'death_animation_finished') and not player1.death_animation_finished:
                    p1_truly_gone = False # Still animating death, so not truly gone for game over
            else: # Alive and not dead
                p1_truly_gone = False
    state['game_over'] = p1_truly_gone # True if P1 is invalid OR dead AND death animation finished

    state['projectiles'] = [proj.get_network_data() for proj in projectile_sprites if hasattr(proj, 'get_network_data')]
    # print(f"DEBUG GSM (get_network_game_state): Final state to send (P1 Pos: {state['p1'].get('pos') if state['p1'] else 'N/A'}, P2 Pos: {state['p2'].get('pos') if state['p2'] else 'N/A'}, Num Enemies: {len(state['enemies'])})") # DEBUG
    return state

def set_network_game_state(network_state_data, game_elements, client_player_id=None): # client_player_id kept for potential future use
    """
    Applies received network state to local game elements.
    On the client, this updates both remote players and the client's own player
    to reflect the server's authoritative state.
    """
    # print(f"DEBUG GSM (set_network_game_state): Applying network state. Client ID: {client_player_id}") # DEBUG
    # if network_state_data: # DEBUG
        # print(f"DEBUG GSM (set_network_game_state): Received P1 data: {network_state_data.get('p1')}") # DEBUG
        # print(f"DEBUG GSM (set_network_game_state): Received P2 data: {network_state_data.get('p2')}") # DEBUG
    # else: # DEBUG
        # print("DEBUG GSM (set_network_game_state): network_state_data is None.") # DEBUG
        # return # DEBUG

    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", []) 
    current_chest = game_elements.get("current_chest") 
    all_sprites = game_elements.get("all_sprites")
    enemy_sprites = game_elements.get("enemy_sprites")
    collectible_sprites = game_elements.get("collectible_sprites")
    projectile_sprites = game_elements.get("projectile_sprites", pygame.sprite.Group())
    enemy_spawns_data_cache = game_elements.get("enemy_spawns_data_cache", [])


    # Update Player 1 state from network data
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        # print(f"DEBUG GSM (set_network_game_state): Applying state to P1. Current P1 valid: {player1._valid_init}, alive: {player1.alive() if hasattr(player1, 'alive') else 'N/A'}") # DEBUG
        p1_data = network_state_data['p1']
        # print(f"DEBUG GSM (set_network_game_state): P1 network data being applied: pos={p1_data.get('pos')}, state={p1_data.get('state')}, valid={p1_data.get('_valid_init')}") # DEBUG
        player1.set_network_data(p1_data)
        # print(f"DEBUG GSM (set_network_game_state): P1 after set_network_data. Valid: {player1._valid_init}, Alive: {player1.alive()}, Pos: {player1.pos if hasattr(player1, 'pos') else 'N/A'}") # DEBUG
        if player1._valid_init and not player1.is_dead and not player1.alive():
             # print(f"DEBUG GSM (set_network_game_state): P1 became valid/alive but not in all_sprites. Adding.") # DEBUG
             all_sprites.add(player1)
        # elif not player1._valid_init and player1.alive(): # Should be handled by player1.set_network_data
            # print(f"DEBUG GSM (set_network_game_state): P1 became INvalid but IS in all_sprites. kill() should have been called.") #DEBUG

    # Update Player 2 state from network data
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        # print(f"DEBUG GSM (set_network_game_state): Applying state to P2. Current P2 valid: {player2._valid_init}, alive: {player2.alive() if hasattr(player2, 'alive') else 'N/A'}") # DEBUG
        p2_data = network_state_data['p2']
        # print(f"DEBUG GSM (set_network_game_state): P2 network data being applied: pos={p2_data.get('pos')}, state={p2_data.get('state')}, valid={p2_data.get('_valid_init')}") # DEBUG
        player2.set_network_data(p2_data)
        # print(f"DEBUG GSM (set_network_game_state): P2 after set_network_data. Valid: {player2._valid_init}, Alive: {player2.alive()}, Pos: {player2.pos if hasattr(player2, 'pos') else 'N/A'}") # DEBUG
        if player2._valid_init and not player2.is_dead and not player2.alive():
             # print(f"DEBUG GSM (set_network_game_state): P2 became valid/alive but not in all_sprites. Adding.") # DEBUG
             all_sprites.add(player2)
        # elif not player2._valid_init and player2.alive(): # Should be handled by player2.set_network_data
            # print(f"DEBUG GSM (set_network_game_state): P2 became INvalid but IS in all_sprites. kill() should have been called.") #DEBUG


    # Enemy state synchronization (critical for clients)
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies']
        # print(f"DEBUG GSM (set_network_game_state): Syncing {len(received_enemy_data_map)} enemies from network.") # DEBUG
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str)
            # print(f"DEBUG GSM (set_network_game_state): Processing enemy ID {enemy_id_str} from network. Data: {enemy_data_from_server.get('pos')}, valid: {enemy_data_from_server.get('_valid_init')}") # DEBUG

            if enemy_data_from_server.get('_valid_init', False): 
                if enemy_id_str in current_client_enemies_map: 
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    # print(f"DEBUG GSM (set_network_game_state): Updating existing enemy ID {enemy_id_str}.") # DEBUG
                    if hasattr(client_enemy, 'set_network_data'):
                        client_enemy.set_network_data(enemy_data_from_server)
                        if client_enemy._valid_init and not client_enemy.alive():
                            if (client_enemy.is_dead and not client_enemy.death_animation_finished) or \
                               (not client_enemy.is_dead):
                                 # print(f"DEBUG GSM (set_network_game_state): Re-adding enemy {enemy_id_str} to sprite groups.") # DEBUG
                                 all_sprites.add(client_enemy); enemy_sprites.add(client_enemy)
                else: 
                    # print(f"DEBUG GSM (set_network_game_state): Creating NEW enemy ID {enemy_id_str}.") # DEBUG
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
                        # print(f"DEBUG GSM (set_network_game_state): New enemy {enemy_id_str} created. Valid: {new_enemy_instance._valid_init}") # DEBUG


                        if new_enemy_instance._valid_init:
                            server_color_name = enemy_data_from_server.get('color_name')
                            if server_color_name and hasattr(new_enemy_instance, 'color_name') and new_enemy_instance.color_name != server_color_name:
                                # print(f"DEBUG GSM (set_network_game_state): Enemy {enemy_id_str} color mismatch (local '{new_enemy_instance.color_name}', net '{server_color_name}'). Reloading animations.") # DEBUG
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
                                # print(f"DEBUG GSM (set_network_game_state): Enemy {enemy_id_str} animations reloaded. New valid: {new_enemy_instance._valid_init}") # DEBUG


                        if new_enemy_instance._valid_init:
                            new_enemy_instance.set_network_data(enemy_data_from_server)
                            all_sprites.add(new_enemy_instance); enemy_sprites.add(new_enemy_instance)
                            enemy_list.append(new_enemy_instance)
                            # print(f"DEBUG GSM (set_network_game_state): New enemy {enemy_id_str} added to lists and groups.") # DEBUG
                        # else: # DEBUG
                            # print(f"DEBUG GSM (set_network_game_state): New enemy {enemy_id_str} was NOT valid after creation/color sync.") # DEBUG
                    except Exception as e:
                        print(f"Client: Error creating new instance of enemy {enemy_id_str}: {e}")
                        traceback.print_exc()

            elif enemy_id_str in current_client_enemies_map: # Server says enemy invalid, but client has it
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                # print(f"DEBUG GSM (set_network_game_state): Server marked enemy {enemy_id_str} as invalid. Removing from client.") # DEBUG
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

        server_enemy_ids_present_in_message = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove_fully = set(current_client_enemies_map.keys()) - server_enemy_ids_present_in_message
        for removed_id_str_fully in client_enemy_ids_to_remove_fully:
            if removed_id_str_fully in current_client_enemies_map:
                enemy_to_remove_fully = current_client_enemies_map[removed_id_str_fully]
                # print(f"DEBUG GSM (set_network_game_state): Enemy {removed_id_str_fully} not in server message. Removing from client.") # DEBUG
                if enemy_to_remove_fully.alive(): enemy_to_remove_fully.kill()
                if enemy_to_remove_fully in enemy_list: enemy_list.remove(enemy_to_remove_fully)


    # Chest state synchronization
    if 'chest' in network_state_data:
        chest_data_from_server = network_state_data['chest']
        # print(f"DEBUG GSM (set_network_game_state): Chest data from server: {chest_data_from_server}") # DEBUG
        if chest_data_from_server and Chest is not None: 
            chest_pos_center_server = chest_data_from_server.get('pos')
            chest_is_collected_server = chest_data_from_server.get('is_collected', False)

            if chest_is_collected_server: 
                if current_chest and current_chest.alive(): current_chest.kill()
                game_elements["current_chest"] = None 
                # print(f"DEBUG GSM (set_network_game_state): Server says chest collected. Cleared local chest.") # DEBUG
            elif chest_pos_center_server: 
                if not current_chest or not current_chest.alive(): 
                    # print(f"DEBUG GSM (set_network_game_state): Client needs to create chest at {chest_pos_center_server}.") # DEBUG
                    if current_chest: current_chest.kill() 
                    try:
                        temp_chest_surf_for_height = Chest(0,0).image
                        temp_chest_height_approx = temp_chest_surf_for_height.get_height() if temp_chest_surf_for_height else 30
                        chest_spawn_x_midbottom = chest_pos_center_server[0]
                        chest_spawn_y_midbottom = chest_pos_center_server[1] + temp_chest_height_approx / 2
                        new_chest_instance_client = Chest(chest_spawn_x_midbottom, chest_spawn_y_midbottom)
                        if hasattr(new_chest_instance_client, '_valid_init') and new_chest_instance_client._valid_init:
                            all_sprites.add(new_chest_instance_client)
                            collectible_sprites.add(new_chest_instance_client)
                            game_elements["current_chest"] = new_chest_instance_client
                            if hasattr(game_elements["current_chest"], 'is_collected'):
                                game_elements["current_chest"].is_collected = False
                            # print(f"DEBUG GSM (set_network_game_state): New client chest created: {new_chest_instance_client}") # DEBUG
                        else:
                            game_elements["current_chest"] = None
                            # print(f"DEBUG GSM (set_network_game_state): New client chest FAILED init.") # DEBUG
                    except Exception as e:
                        # print(f"DEBUG GSM (set_network_game_state): Exception creating client chest: {e}") # DEBUG
                        game_elements["current_chest"] = None
                elif current_chest: # Client has a chest, server has one uncollected - ensure local not marked collected
                    # print(f"DEBUG GSM (set_network_game_state): Client and server both have uncollected chest. Ensuring local is_collected is False.") # DEBUG
                    if hasattr(current_chest, 'is_collected'):
                        current_chest.is_collected = False

        elif not network_state_data.get('chest'): # Server says no chest
            if current_chest and current_chest.alive(): current_chest.kill()
            game_elements["current_chest"] = None
            # print(f"DEBUG GSM (set_network_game_state): Server says NO chest. Cleared local chest.") # DEBUG


    # Projectile state synchronization
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if 'id' in p_data}
        # print(f"DEBUG GSM (set_network_game_state): Syncing {len(received_proj_data_map)} projectiles from network.") # DEBUG
        current_client_proj_map = {p.projectile_id: p for p in projectile_sprites if hasattr(p, 'projectile_id')}

        for proj_id_server, proj_data_server in received_proj_data_map.items():
            # print(f"DEBUG GSM (set_network_game_state): Processing projectile ID {proj_id_server} from network. Pos: {proj_data_server.get('pos')}") # DEBUG
            if proj_id_server in current_client_proj_map:
                existing_proj_client = current_client_proj_map[proj_id_server]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
            else: # New projectile for this client
                owner_instance_client = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server is not None:
                    if owner_id_from_server == 1 and player1: owner_instance_client = player1
                    elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                # print(f"DEBUG GSM (set_network_game_state): Attempting to create new projectile {proj_id_server}. Owner ID: {owner_id_from_server}, Owner instance client-side: {owner_instance_client}") # DEBUG


                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server:
                    direction_vec_server = pygame.math.Vector2(proj_data_server['vel'])
                    if direction_vec_server.length_squared() == 0:
                        direction_vec_server = pygame.math.Vector2(1,0) if owner_instance_client.facing_right else pygame.math.Vector2(-1,0)

                    try:
                        new_proj_client = Fireball(proj_data_server['pos'][0], proj_data_server['pos'][1],
                                             direction_vec_server, owner_instance_client)
                        new_proj_client.projectile_id = proj_id_server
                        if hasattr(new_proj_client, 'set_network_data'):
                            new_proj_client.set_network_data(proj_data_server)
                        projectile_sprites.add(new_proj_client)
                        all_sprites.add(new_proj_client)
                        # print(f"DEBUG GSM (set_network_game_state): New projectile {proj_id_server} created and added.") # DEBUG
                    except Exception as e:
                        print(f"DEBUG GSM (set_network_game_state): Error creating new projectile {proj_id_server}: {e}") # DEBUG
                        traceback.print_exc()
                # else: # DEBUG
                    # print(f"DEBUG GSM (set_network_game_state): Cannot create projectile {proj_id_server} - owner missing or data incomplete.") # DEBUG


        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - set(received_proj_data_map.keys())
        for removed_proj_id_client in client_proj_ids_to_remove:
            if removed_proj_id_client in current_client_proj_map:
                proj_to_kill_client = current_client_proj_map[removed_proj_id_client]
                # print(f"DEBUG GSM (set_network_game_state): Projectile {removed_proj_id_client} not in server message. Removing from client.") # DEBUG
                if proj_to_kill_client.alive(): proj_to_kill_client.kill()
    # print(f"DEBUG GSM (set_network_game_state): Network state application finished. P1 alive: {player1.alive() if player1 else 'N/A'}, P2 alive: {player2.alive() if player2 else 'N/A'}") # DEBUG

########## END OF FILE: game_state_manager.py ##########