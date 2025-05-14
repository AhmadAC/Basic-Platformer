# game_state_manager.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Manages game state, including reset and network synchronization.
"""
import pygame
import traceback
from game_setup import spawn_chest # For respawning chest
from enemy import Enemy # For creating new enemies on client
from items import Chest # For type checking and creating new chests on client
from projectiles import Fireball # For creating projectiles on client

def reset_game_state(game_elements):
    """Resets the state of players, enemies, and collectibles."""
    print("\n--- Resetting Platformer Game State ---")
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
        player1.reset_state(player1_spawn_pos)
        if not player1.alive() and player1._valid_init: all_sprites.add(player1) # Ensure in group
        print("P1 Reset")
    if player2 and hasattr(player2, 'reset_state'):
        player2.reset_state(player2_spawn_pos)
        if not player2.alive() and player2._valid_init: all_sprites.add(player2) # Ensure in group
        print("P2 Reset")

    for enemy_instance in enemy_list:
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset()
            if enemy_instance._valid_init and not enemy_instance.alive(): # If reset somehow made it not alive but valid
                all_sprites.add(enemy_instance) # Re-add to ensure it's drawn/updated if it revives
                enemy_sprites.add(enemy_instance)
    print(f"{len(enemy_list)} enemies processed for reset.")

    if projectile_sprites:
        for proj in projectile_sprites: proj.kill()
        projectile_sprites.empty()

    if current_chest and current_chest.alive(): current_chest.kill()
    
    new_chest = spawn_chest(game_elements.get("platform_sprites"), game_elements.get("ground_level_y"))
    if new_chest:
        all_sprites.add(new_chest)
        collectible_sprites.add(new_chest)
        game_elements["current_chest"] = new_chest # Update the reference in game_elements
        print("Chest respawned.")
    else:
        game_elements["current_chest"] = None # Ensure it's None if spawn fails
        print("Failed to respawn chest or Chest class not available.")
    
    if camera: camera.set_pos(0,0) # Reset camera position to default

    print("--- Game State Reset Finished ---\n")
    return new_chest # Return the new chest so main can update its reference if needed

def get_network_game_state(game_elements):
    """Gathers all relevant game state for network transmission."""
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", [])
    current_chest = game_elements.get("current_chest")
    projectile_sprites = game_elements.get("projectile_sprites", pygame.sprite.Group()) # Default to empty group

    state = {'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 'game_over': False, 'projectiles': []}

    if player1 and hasattr(player1, 'get_network_data'):
        state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'):
        state['p2'] = player2.get_network_data()

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

    return state

def set_network_game_state(network_state_data, game_elements, client_player_id=None):
    """
    Applies received network state to local game elements.
    `client_player_id` indicates which player is local (1 or 2), or None if this is server-side state merging.
    """
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list = game_elements.get("enemy_list", []) # This list will be modified
    current_chest = game_elements.get("current_chest") # This reference will be updated
    all_sprites = game_elements.get("all_sprites")
    enemy_sprites = game_elements.get("enemy_sprites")
    collectible_sprites = game_elements.get("collectible_sprites")
    projectile_sprites = game_elements.get("projectile_sprites", pygame.sprite.Group())
    enemy_spawns_data_cache = game_elements.get("enemy_spawns_data_cache", [])


    # Update Player 1 state from network if it's a remote player
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        is_p1_local = (client_player_id == 1)
        if not is_p1_local: # Only update P1 if it's remote (i.e., this is client with P2, or server updating P1 from somewhere else)
            player1.set_network_data(network_state_data['p1'])
            if player1._valid_init and not player1.alive() and not player1.is_dead: # If validated by network and should be alive
                 all_sprites.add(player1) 

    # Update Player 2 state from network if it's a remote player
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        is_p2_local = (client_player_id == 2)
        if not is_p2_local: # Only update P2 if it's remote
            player2.set_network_data(network_state_data['p2'])
            if player2._valid_init and not player2.alive() and not player2.is_dead:
                 all_sprites.add(player2)

    # Enemy state synchronization (critical for clients)
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies']
        # Build a map of current enemies on the client for quick lookup
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        # Update existing enemies or create new ones based on server state
        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str)
            
            if enemy_data_from_server.get('_valid_init', False): # Server says this enemy should exist and is valid
                if enemy_id_str in current_client_enemies_map: # Enemy already exists on client
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    if hasattr(client_enemy, 'set_network_data'):
                        client_enemy.set_network_data(enemy_data_from_server)
                        # Ensure it's in sprite groups if it became alive/valid again or is dying
                        if client_enemy._valid_init and not client_enemy.alive(): 
                            if (client_enemy.is_dead and not client_enemy.death_animation_finished) or \
                               (not client_enemy.is_dead):
                                 all_sprites.add(client_enemy); enemy_sprites.add(client_enemy)
                else: # Enemy is new to this client, create it
                    try:
                        # Use cached spawn data for original position and patrol, then apply server state
                        spawn_pos_e_default = enemy_data_from_server.get('pos', (0,0)) # Fallback pos from server
                        patrol_area_e_obj = None
                        
                        # Try to get original spawn data from cache
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
                            new_enemy_instance.set_network_data(enemy_data_from_server) # Apply current state from server
                            all_sprites.add(new_enemy_instance); enemy_sprites.add(new_enemy_instance)
                            enemy_list.append(new_enemy_instance) # Add to the tracked list
                        # else: print(f"Client: Failed to initialize new enemy {enemy_id_str} (after creation).")
                    except Exception as e:
                        print(f"Client: Error creating new instance of enemy {enemy_id_str}: {e}")
                        traceback.print_exc()
            
            elif enemy_id_str in current_client_enemies_map: # Server says enemy is NOT valid or doesn't exist anymore
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove) # Remove from tracked list
        
        # Remove any enemies on client that are no longer present in the server's state at all
        server_enemy_ids_present_in_message = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove_fully = set(current_client_enemies_map.keys()) - server_enemy_ids_present_in_message
        for removed_id_str_fully in client_enemy_ids_to_remove_fully:
            if removed_id_str_fully in current_client_enemies_map:
                enemy_to_remove_fully = current_client_enemies_map[removed_id_str_fully]
                if enemy_to_remove_fully.alive(): enemy_to_remove_fully.kill()
                if enemy_to_remove_fully in enemy_list: enemy_list.remove(enemy_to_remove_fully)


    # Chest state synchronization
    if 'chest' in network_state_data:
        chest_data_from_server = network_state_data['chest']
        if chest_data_from_server and Chest is not None: # Chest exists on server side
            chest_pos_center_server = chest_data_from_server.get('pos')
            chest_is_collected_server = chest_data_from_server.get('is_collected', False)

            if chest_is_collected_server: # Server says chest is collected
                if current_chest and current_chest.alive(): current_chest.kill()
                game_elements["current_chest"] = None # Update main game_elements reference
            elif chest_pos_center_server: # Chest exists and is not collected on server
                if not current_chest or not current_chest.alive(): # Client needs to create/respawn chest visually
                    if current_chest: current_chest.kill() # Clean up old one if any ghost remains
                    try:
                        # Chest constructor expects midbottom x, y. Server sends center x, y.
                        # Approximate midbottom y from center y for Chest constructor.
                        # This assumes Chest images are roughly centered vertically.
                        temp_chest_surf_for_height = Chest(0,0).image # Get a temp instance for image height
                        temp_chest_height_approx = temp_chest_surf_for_height.get_height() if temp_chest_surf_for_height else 30
                        
                        chest_spawn_x_midbottom = chest_pos_center_server[0] # x is same for center/midbottom if rect anchor is midbottom
                        chest_spawn_y_midbottom = chest_pos_center_server[1] + temp_chest_height_approx / 2
                        
                        new_chest_instance_client = Chest(chest_spawn_x_midbottom, chest_spawn_y_midbottom)
                        if hasattr(new_chest_instance_client, '_valid_init') and new_chest_instance_client._valid_init:
                            all_sprites.add(new_chest_instance_client)
                            collectible_sprites.add(new_chest_instance_client)
                            game_elements["current_chest"] = new_chest_instance_client
                            if hasattr(game_elements["current_chest"], 'is_collected'):
                                game_elements["current_chest"].is_collected = False # Ensure it's not marked collected
                        else:
                            game_elements["current_chest"] = None # Creation failed
                            # print("Client: Failed to init chest from network state during creation.")
                    except Exception as e:
                        # print(f"Client: Error creating chest from network state: {e}")
                        game_elements["current_chest"] = None
                elif current_chest: # Chest exists on client, ensure its collected status matches server
                    if hasattr(current_chest, 'is_collected'):
                        current_chest.is_collected = False # Should not be collected if server sent its data (implying it's active)
        
        elif not network_state_data.get('chest'): # Server explicitly says no chest (e.g. collected and not respawned yet)
            if current_chest and current_chest.alive(): current_chest.kill()
            game_elements["current_chest"] = None


    # Projectile state synchronization
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if 'id' in p_data}
        current_client_proj_map = {p.projectile_id: p for p in projectile_sprites if hasattr(p, 'projectile_id')}

        # Update existing projectiles or create new ones
        for proj_id_server, proj_data_server in received_proj_data_map.items():
            if proj_id_server in current_client_proj_map: # Projectile exists on client
                existing_proj_client = current_client_proj_map[proj_id_server]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
            else: # Projectile is new to this client, create it
                owner_instance_client = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server is not None: # Determine owner
                    if owner_id_from_server == 1 and player1: owner_instance_client = player1
                    elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server:
                    direction_vec_server = pygame.math.Vector2(proj_data_server['vel'])
                    # Ensure direction vector is not zero length (should be handled by projectile init too)
                    if direction_vec_server.length_squared() == 0:
                        direction_vec_server = pygame.math.Vector2(1,0) if owner_instance_client.facing_right else pygame.math.Vector2(-1,0)
                    
                    try:
                        new_proj_client = Fireball(proj_data_server['pos'][0], proj_data_server['pos'][1], 
                                             direction_vec_server, owner_instance_client)
                        new_proj_client.projectile_id = proj_id_server # Assign ID from network state
                        if hasattr(new_proj_client, 'set_network_data'): # Apply full state after creation
                            new_proj_client.set_network_data(proj_data_server) 
                        projectile_sprites.add(new_proj_client)
                        all_sprites.add(new_proj_client)
                    except Exception as e:
                        # print(f"Client: Error creating projectile {proj_id_server} from network: {e}")
                        traceback.print_exc()
        
        # Remove projectiles on client that are no longer in server state
        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - set(received_proj_data_map.keys())
        for removed_proj_id_client in client_proj_ids_to_remove:
            if removed_proj_id_client in current_client_proj_map:
                proj_to_kill_client = current_client_proj_map[removed_proj_id_client]
                if proj_to_kill_client.alive(): proj_to_kill_client.kill()