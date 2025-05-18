# game_state_manager.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.6 (Added missing imports, fixed Chest sync for client)
Manages game state, including reset and network synchronization.
"""
import pygame
import traceback
import os
from typing import Optional, List, Dict, Any

# Game-specific imports
from game_setup import spawn_chest # For respawning chest on reset
from enemy import Enemy
from items import Chest
from statue import Statue # Import Statue for network sync
from projectiles import (
    Fireball, PoisonShot, BoltProjectile, BloodShot,
    IceShard, ShadowProjectile, GreyProjectile
)
from assets import load_all_player_animations, load_gif_frames, resource_path # For client-side enemy color sync
import constants as C

# Logger import with fallback
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL GAME_STATE_MANAGER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Define error in fallback
    def critical(msg): print(f"CRITICAL: {msg}")


def reset_game_state(game_elements: Dict[str, Any]) -> Optional[Chest]:
    """
    Resets the state of players, enemies, collectibles, and other game elements
    to their initial or default states for the current level.

    Args:
        game_elements (Dict[str, Any]): The dictionary holding all current game elements.

    Returns:
        Optional[Chest]: The newly spawned chest instance, or None if chest spawning fails.
    """
    info("GSM: --- Resetting Platformer Game State ---")
    
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list: List[Statue] = game_elements.get("statue_objects", []) # Get statues
    current_chest = game_elements.get("current_chest")
    
    player1_spawn_pos = game_elements.get("player1_spawn_pos")
    player2_spawn_pos = game_elements.get("player2_spawn_pos")
    
    all_sprites: pygame.sprite.Group = game_elements.get("all_sprites")
    enemy_sprites: pygame.sprite.Group = game_elements.get("enemy_sprites")
    collectible_sprites: pygame.sprite.Group = game_elements.get("collectible_sprites")
    projectile_sprites: pygame.sprite.Group = game_elements.get("projectile_sprites")
    camera = game_elements.get("camera")

    # Reset Players
    if player1 and hasattr(player1, 'reset_state'):
        debug(f"GSM: Resetting P1 at {player1_spawn_pos}")
        player1.reset_state(player1_spawn_pos)
        if player1._valid_init and not player1.alive(): # Re-add if valid but not in group (e.g., after kill)
            all_sprites.add(player1)
        debug("GSM: P1 Reset complete.")
        
    if player2 and hasattr(player2, 'reset_state'):
        debug(f"GSM: Resetting P2 at {player2_spawn_pos}")
        player2.reset_state(player2_spawn_pos)
        if player2._valid_init and not player2.alive():
            all_sprites.add(player2)
        debug("GSM: P2 Reset complete.")

    # Reset Enemies
    for enemy_instance in enemy_list:
        if hasattr(enemy_instance, 'reset'):
            enemy_instance.reset()
            if enemy_instance._valid_init and not enemy_instance.alive():
                all_sprites.add(enemy_instance)
                enemy_sprites.add(enemy_instance)
    debug(f"GSM: {len(enemy_list)} enemies processed for reset.")

    # Reset Statues (they are part of the level, don't respawn, just reset state if needed)
    # For now, statues simply get re-created if the level is fully reloaded.
    # If they have state that needs resetting without a full level reload (e.g. if they could be damaged but not smashed),
    # add reset logic here. For now, assume they are static or handled by full reload.
    # If statues are dynamic and added to `all_sprites`, ensure they are handled correctly on client creation.
    for statue_instance in statue_objects_list:
        if hasattr(statue_instance, 'is_smashed') and statue_instance.is_smashed:
            # If a statue was smashed, it should be removed or reset.
            # For simplicity, if the game expects statues to reappear on reset, they would
            # typically be re-added by game_setup. If they should persist as smashed until
            # explicitly removed by map logic, this might not need to do anything.
            # For now, let's assume they are part of the map and if smashed, they stay smashed
            # until a full level reload or map-specific reset logic handles them.
            # If they are meant to reappear, they should be killed and re-added by game_setup.
            # Let's assume game_setup handles their initial placement. If a statue is smashed,
            # it will self.kill() after its animation. Resetting here might mean making it unsmashed.
            if hasattr(statue_instance, 'is_smashed'): statue_instance.is_smashed = False
            if hasattr(statue_instance, 'is_dead'): statue_instance.is_dead = False
            if hasattr(statue_instance, 'death_animation_finished'): statue_instance.death_animation_finished = False
            if hasattr(statue_instance, 'image') and hasattr(statue_instance, 'initial_image_frames') and statue_instance.initial_image_frames:
                statue_instance.image = statue_instance.initial_image_frames[0]
                old_center = statue_instance.rect.center
                statue_instance.rect = statue_instance.image.get_rect(center=old_center)
            if not statue_instance.alive(): # If it was killed (e.g. after smash anim)
                all_sprites.add(statue_instance) # Re-add to sprite group
                # statue_objects_list might not need direct manipulation if game_elements dict is source of truth
    debug(f"GSM: {len(statue_objects_list)} statues processed for state reset.")


    # Clear Projectiles
    if projectile_sprites:
        for proj in projectile_sprites: proj.kill()
        projectile_sprites.empty() # Ensure the group is empty
        debug("GSM: Projectiles cleared.")

    # Respawn Chest
    if current_chest and current_chest.alive():
        current_chest.kill() # Remove existing chest
    debug(f"GSM: Existing chest killed (if any).")

    # Spawn new chest (spawn_chest handles adding to groups if successful)
    new_chest = spawn_chest(game_elements.get("platform_sprites"), game_elements.get("ground_level_y"))
    if new_chest:
        # spawn_chest should ideally add to all_sprites and collectible_sprites if it creates one
        # If not, ensure they are added here.
        if not all_sprites.has(new_chest): all_sprites.add(new_chest)
        if not collectible_sprites.has(new_chest): collectible_sprites.add(new_chest)
        game_elements["current_chest"] = new_chest # Update the reference in game_elements
        debug("GSM: Chest respawned.")
    else:
        game_elements["current_chest"] = None # Ensure reference is None if spawn failed
        debug("GSM: Failed to respawn chest or Chest class not available.")

    # Reset Camera
    if camera:
        camera.set_pos(0,0) # Reset camera to default position (or level start)
    debug("GSM: Camera position reset.")

    info("GSM: --- Game State Reset Finished ---\n")
    return new_chest


def get_network_game_state(game_elements: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gathers all relevant game state into a dictionary for network transmission.
    This is typically called by the server.
    """
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", [])
    statue_objects_list: List[Statue] = game_elements.get("statue_objects", [])
    current_chest: Optional[Chest] = game_elements.get("current_chest")
    projectile_sprites: pygame.sprite.Group = game_elements.get("projectile_sprites", pygame.sprite.Group())

    state: Dict[str, Any] = {
        'p1': None, 'p2': None, 'enemies': {}, 'chest': None, 
        'statues': [], 'projectiles': [], 'game_over': False
    }

    # Player states
    if player1 and hasattr(player1, 'get_network_data'):
        state['p1'] = player1.get_network_data()
    if player2 and hasattr(player2, 'get_network_data'):
        state['p2'] = player2.get_network_data()

    # Enemy states (only send if alive or death animation not finished)
    for enemy in enemy_list:
        if hasattr(enemy, 'enemy_id') and hasattr(enemy, 'get_network_data'):
            # Send if enemy is alive, or if it's dead but its death animation hasn't finished playing
            if enemy.alive() or (enemy.is_dead and not enemy.death_animation_finished):
                 state['enemies'][str(enemy.enemy_id)] = enemy.get_network_data()

    # Statue states
    for s_obj in statue_objects_list:
        # Send if statue is alive (not self.kill()ed), OR
        # if it's smashed and its "disappearance" animation isn't logically finished.
        # The statue's own `is_dead` and `death_animation_finished` will reflect this.
        if s_obj.alive() or (s_obj.is_smashed and not s_obj.death_animation_finished):
            if hasattr(s_obj, 'get_network_data'):
                state['statues'].append(s_obj.get_network_data())

    # Chest state
    if current_chest and hasattr(current_chest, 'rect'): 
        # Send chest state if it's alive or in a state that implies it was recently active (like fading)
        if current_chest.alive() or current_chest.state in ['fading', 'killed']: # 'killed' means it just finished fading
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
            state['chest'] = None # Chest exists but is not in a transmittable state (e.g. fully reset but not respawned)
    else: 
        state['chest'] = None # No chest object
    
    # Game over state (simple P1 check for now, could be more complex)
    p1_truly_gone = True # Assume P1 is gone unless proven otherwise
    if player1 and player1._valid_init: 
        if player1.alive(): # If P1 is in any sprite group
            if hasattr(player1, 'is_dead') and player1.is_dead: # If logically dead
                # Check if death animation is still playing (for petrified, death_anim_finished might be true early)
                if hasattr(player1, 'is_petrified') and player1.is_petrified and not player1.is_stone_smashed:
                    p1_truly_gone = False # Petrified but not smashed isn't "game over" yet
                elif hasattr(player1, 'death_animation_finished') and not player1.death_animation_finished:
                    p1_truly_gone = False # Death animation playing
            else: # Alive and not dead
                p1_truly_gone = False
    state['game_over'] = p1_truly_gone 

    # Projectile states
    state['projectiles'] = [proj.get_network_data() for proj in projectile_sprites if hasattr(proj, 'get_network_data')]
    
    return state


def set_network_game_state(network_state_data: Dict[str, Any], 
                           game_elements: Dict[str, Any], 
                           client_player_id: Optional[int] = None): 
    """
    Applies received network data to update the local game state.
    This is primarily used on clients.
    """
    player1 = game_elements.get("player1")
    player2 = game_elements.get("player2")
    enemy_list: List[Enemy] = game_elements.get("enemy_list", []) 
    statue_objects_list_client: List[Statue] = game_elements.get("statue_objects", [])
    current_chest: Optional[Chest] = game_elements.get("current_chest") 
    
    all_sprites: pygame.sprite.Group = game_elements.get("all_sprites")
    enemy_sprites: pygame.sprite.Group = game_elements.get("enemy_sprites")
    collectible_sprites: pygame.sprite.Group = game_elements.get("collectible_sprites")
    projectile_sprites: pygame.sprite.Group = game_elements.get("projectile_sprites", pygame.sprite.Group())
    
    # Cache of enemy spawn data (from level file) for creating new enemies on client
    enemy_spawns_data_cache: List[Dict[str, Any]] = game_elements.get("enemy_spawns_data_cache", [])

    # Player 1 update
    if player1 and 'p1' in network_state_data and network_state_data['p1'] and hasattr(player1, 'set_network_data'):
        player1.set_network_data(network_state_data['p1'])
        # Ensure P1 is in all_sprites if valid and not fully "gone" (e.g., petrified but not smashed is not gone)
        if player1._valid_init and not player1.alive():
            is_p1_permanently_gone = player1.is_dead and \
                                     (not player1.is_petrified or player1.is_stone_smashed) and \
                                     player1.death_animation_finished
            if not is_p1_permanently_gone:
                 all_sprites.add(player1)

    # Player 2 update
    if player2 and 'p2' in network_state_data and network_state_data['p2'] and hasattr(player2, 'set_network_data'):
        player2.set_network_data(network_state_data['p2'])
        if player2._valid_init and not player2.alive():
            is_p2_permanently_gone = player2.is_dead and \
                                     (not player2.is_petrified or player2.is_stone_smashed) and \
                                     player2.death_animation_finished
            if not is_p2_permanently_gone:
                 all_sprites.add(player2)

    # Enemy updates
    if 'enemies' in network_state_data:
        received_enemy_data_map = network_state_data['enemies'] # Keyed by enemy_id as string
        current_client_enemies_map = {str(enemy.enemy_id): enemy for enemy in enemy_list if hasattr(enemy, 'enemy_id')}

        # Update existing enemies or create new ones
        for enemy_id_str, enemy_data_from_server in received_enemy_data_map.items():
            enemy_id_int = int(enemy_id_str) # Convert ID to int for local use
            
            if enemy_data_from_server.get('_valid_init', False): # If server says enemy is valid
                if enemy_id_str in current_client_enemies_map: # Enemy already exists on client
                    client_enemy = current_client_enemies_map[enemy_id_str]
                    if hasattr(client_enemy, 'set_network_data'):
                        client_enemy.set_network_data(enemy_data_from_server)
                        # Ensure enemy is in sprite groups if it should be visible/active
                        if client_enemy._valid_init and not client_enemy.alive():
                            # Add back if dead but anim not finished, OR if not dead at all
                            if (client_enemy.is_dead and not client_enemy.death_animation_finished) or \
                               (not client_enemy.is_dead):
                                 all_sprites.add(client_enemy); enemy_sprites.add(client_enemy)
                else: # New enemy on server, create instance on client
                    try:
                        # Attempt to find original spawn data for this enemy ID
                        spawn_pos_e_default = enemy_data_from_server.get('pos', (0,0)) # Fallback if no cache
                        patrol_area_e_obj = None
                        enemy_color_name_from_cache = None

                        if enemy_id_int < len(enemy_spawns_data_cache): # Check if ID is within cache bounds
                            original_spawn_info = enemy_spawns_data_cache[enemy_id_int]
                            spawn_pos_e_default = original_spawn_info.get('pos', spawn_pos_e_default)
                            patrol_data_from_level = original_spawn_info.get('patrol')
                            if patrol_data_from_level:
                                try: patrol_area_e_obj = pygame.Rect(patrol_data_from_level)
                                except TypeError: debug(f"Client: Invalid patrol data from cache for new enemy {enemy_id_int}.")
                            enemy_color_name_from_cache = original_spawn_info.get('enemy_color_id')
                        else:
                            debug(f"Client: No original spawn data in cache for new enemy_id {enemy_id_int}. Using server pos and default color if needed.")

                        # Create new Enemy instance
                        # Use server's color name if provided and different from cache, otherwise use cache or default
                        server_color_name = enemy_data_from_server.get('color_name')
                        final_color_for_new_enemy = server_color_name if server_color_name else enemy_color_name_from_cache

                        new_enemy_instance = Enemy(spawn_pos_e_default[0], spawn_pos_e_default[1],
                                             patrol_area=patrol_area_e_obj, enemy_id=enemy_id_int,
                                             color_name=final_color_for_new_enemy) # Pass color_name
                        
                        # If animations for this color are missing, _valid_init will be False
                        if new_enemy_instance._valid_init:
                            # If server sent a color and it's different from the one used for init (e.g. if cache was None)
                            # and animations need to be reloaded based on server's authoritative color.
                            # This path is less common if color_name is correctly passed to Enemy constructor.
                            if server_color_name and new_enemy_instance.color_name != server_color_name:
                                new_enemy_instance.color_name = server_color_name
                                enemy_asset_folder = os.path.join('characters', server_color_name)
                                new_enemy_instance.animations = load_all_player_animations(
                                    relative_asset_folder=enemy_asset_folder
                                )
                                if new_enemy_instance.animations is None: # Critical if anims fail for server color
                                    error(f"Client CRITICAL: Failed to reload animations for new enemy {enemy_id_int} with server color {server_color_name} from '{enemy_asset_folder}'")
                                    new_enemy_instance._valid_init = False
                                    # Create visual placeholder if anims fail
                                    if hasattr(C, 'BLUE'):
                                        new_enemy_instance.image = pygame.Surface((30, 40)).convert_alpha()
                                        new_enemy_instance.image.fill(C.BLUE)
                                        new_enemy_instance.rect = new_enemy_instance.image.get_rect(midbottom=(spawn_pos_e_default[0], spawn_pos_e_default[1]))
                                else: # Successfully reloaded anims for server color
                                    initial_idle_animation_new_color = new_enemy_instance.animations.get('idle')
                                    if initial_idle_animation_new_color and len(initial_idle_animation_new_color) > 0:
                                        new_enemy_instance.image = initial_idle_animation_new_color[0]
                                    else: # Fallback if even reloaded idle is bad
                                        if hasattr(C, 'BLUE'):
                                            new_enemy_instance.image = pygame.Surface((30, 40)).convert_alpha()
                                            new_enemy_instance.image.fill(C.BLUE)
                                    new_enemy_instance.rect = new_enemy_instance.image.get_rect(midbottom=(spawn_pos_e_default[0], spawn_pos_e_default[1]))
                        
                        if new_enemy_instance._valid_init:
                            new_enemy_instance.set_network_data(enemy_data_from_server) # Apply rest of server state
                            all_sprites.add(new_enemy_instance); enemy_sprites.add(new_enemy_instance)
                            enemy_list.append(new_enemy_instance) # Add to the game_elements list
                    except Exception as e:
                        error(f"Client: Error creating new instance of enemy {enemy_id_str} from network data: {e}")
                        traceback.print_exc()
            
            elif enemy_id_str in current_client_enemies_map: # Server says this enemy is no longer valid (or gone)
                enemy_to_remove = current_client_enemies_map[enemy_id_str]
                if enemy_to_remove.alive(): enemy_to_remove.kill()
                if enemy_to_remove in enemy_list: enemy_list.remove(enemy_to_remove)

        # Remove enemies on client that no longer exist on server
        server_enemy_ids_present_in_message = set(received_enemy_data_map.keys())
        client_enemy_ids_to_remove_fully = set(current_client_enemies_map.keys()) - server_enemy_ids_present_in_message
        for removed_id_str_fully in client_enemy_ids_to_remove_fully:
            if removed_id_str_fully in current_client_enemies_map:
                enemy_to_remove_fully = current_client_enemies_map[removed_id_str_fully]
                if enemy_to_remove_fully.alive(): enemy_to_remove_fully.kill()
                if enemy_to_remove_fully in enemy_list: enemy_list.remove(enemy_to_remove_fully)
        game_elements["enemy_list"] = enemy_list # Update the main game_elements list

    # Chest update
    if 'chest' in network_state_data:
        chest_data_from_server = network_state_data['chest']
        
        if chest_data_from_server and isinstance(Chest, type): # Ensure Chest is a class and data exists
            server_chest_pos_center = chest_data_from_server.get('pos')
            server_chest_state = chest_data_from_server.get('chest_state')
            
            # If server says chest is gone (state 'killed') or has no position, remove client's chest
            if server_chest_state == 'killed' or not server_chest_pos_center: 
                if current_chest and current_chest.alive():
                    current_chest.kill()
                game_elements["current_chest"] = None # Nullify reference
            else: # Server indicates chest exists and is in some state
                # If client has no chest, or its chest was 'killed' but server says it's back
                if not current_chest or not current_chest.alive() or \
                   (current_chest and current_chest.state == 'killed' and server_chest_state != 'killed'): 
                    if current_chest and current_chest.alive(): current_chest.kill() # Remove old if any
                    
                    # Create new chest instance on client
                    # Chest constructor expects midbottom, server sends center. Adjust.
                    temp_chest_height_approx = 30 # Default, might be refined if Chest class has a static height
                    # Try to get default height from a temporary Chest instance's closed frame
                    try:
                        temp_frames = Chest(0,0).frames_closed # Get default closed frames
                        if temp_frames and len(temp_frames[0].get_size()) == 2:
                             temp_chest_height_approx = temp_frames[0].get_height()
                    except: pass # Ignore if temp instance fails
                    
                    chest_spawn_x_midbottom = server_chest_pos_center[0]
                    chest_spawn_y_midbottom = server_chest_pos_center[1] + temp_chest_height_approx / 2 # Adjust from center to midbottom

                    current_chest = Chest(chest_spawn_x_midbottom, chest_spawn_y_midbottom)
                    if current_chest._valid_init:
                        all_sprites.add(current_chest)
                        collectible_sprites.add(current_chest)
                        game_elements["current_chest"] = current_chest # Update game_elements
                    else: # Failed to create chest
                        game_elements["current_chest"] = None # Ensure it's None
                        current_chest = None # Local var also None
                
                # If chest instance exists (either pre-existing or newly created), sync its state
                if current_chest: 
                    current_chest.state = server_chest_state
                    current_chest.is_collected_flag_internal = chest_data_from_server.get('is_collected_internal', False)
                    current_chest.animation_timer = chest_data_from_server.get('animation_timer', pygame.time.get_ticks()) # Sync timer
                    current_chest.time_opened_start = chest_data_from_server.get('time_opened_start', 0)
                    current_chest.fade_alpha = chest_data_from_server.get('fade_alpha', 255)
                    
                    net_frame_index = chest_data_from_server.get('current_frame_index', 0)
                    
                    # Determine correct frame set based on state
                    if current_chest.state in ['opening', 'opened', 'fading']:
                        current_chest.frames_current_set = current_chest.frames_open
                    else: # 'closed' or unknown default
                        current_chest.frames_current_set = current_chest.frames_closed

                    # Validate and set frame index
                    if current_chest.frames_current_set and 0 <= net_frame_index < len(current_chest.frames_current_set):
                        current_chest.current_frame_index = net_frame_index
                    else: # Fallback if index is bad or frames_current_set is empty
                        current_chest.current_frame_index = 0 
                        if current_chest.frames_current_set: # If set has frames, try to use last valid one
                             current_chest.current_frame_index = max(0, len(current_chest.frames_current_set) -1)

                    # Sync position (rect center)
                    current_chest.rect.center = server_chest_pos_center # Server sends center
                    current_chest.pos = pygame.math.Vector2(current_chest.rect.midbottom) # Update internal pos from rect
                    
                    # Update image based on synced state and frame
                    if current_chest.frames_current_set and 0 <= current_chest.current_frame_index < len(current_chest.frames_current_set):
                        current_chest.image = current_chest.frames_current_set[current_chest.current_frame_index].copy() # Use copy
                        if current_chest.state == 'fading': # Apply alpha for fading
                            current_chest.image.set_alpha(max(0, min(255,current_chest.fade_alpha)))
                    elif current_chest.frames_closed and current_chest.frames_closed[0]: # Fallback to default closed image
                         current_chest.image = current_chest.frames_closed[0]
                    # Player healing is server-authoritative, client just shows visuals.

        elif not network_state_data.get('chest'): # Server explicitly says no chest (or key missing)
            if current_chest and current_chest.alive():
                current_chest.kill()
            game_elements["current_chest"] = None

    # Statue updates (client-side)
    if 'statues' in network_state_data:
        received_statue_data_map = {s_data['id']: s_data for s_data in network_state_data.get('statues', []) if 'id' in s_data}
        current_client_statues_map = {s.statue_id: s for s in statue_objects_list_client if hasattr(s, 'statue_id')}

        for statue_id_server, statue_data_server in received_statue_data_map.items():
            if statue_data_server.get('_valid_init', False): # Server says statue is valid
                if statue_id_server in current_client_statues_map: # Statue exists on client
                    client_statue = current_client_statues_map[statue_id_server]
                    if hasattr(client_statue, 'set_network_data'):
                        client_statue.set_network_data(statue_data_server)
                        # Add back to all_sprites if valid but not alive (e.g., after smash anim but before duration kill)
                        if client_statue._valid_init and not client_statue.alive() and not client_statue.is_dead:
                             all_sprites.add(client_statue)
                else: # New statue on server, create on client
                    try:
                        statue_pos_default = statue_data_server.get('pos', (0,0)) # Server sends center
                        # If map files can specify custom images for statues, client needs to know these paths
                        # For now, assume Statue class loads default stone assets.
                        # custom_initial_path_net = statue_data_server.get('initial_image_path')
                        # custom_smashed_path_net = statue_data_server.get('smashed_anim_path')

                        new_statue_client = Statue(statue_pos_default[0], statue_pos_default[1], statue_id=statue_id_server)
                                                   # initial_image_path=custom_initial_path_net,
                                                   # smashed_anim_path=custom_smashed_path_net)
                        if new_statue_client._valid_init:
                            new_statue_client.set_network_data(statue_data_server)
                            all_sprites.add(new_statue_client)
                            statue_objects_list_client.append(new_statue_client) # Add to local list
                        else:
                             error(f"Client: Failed to init new statue {statue_id_server} from network data.")
                    except Exception as e:
                        error(f"Client: Error creating new statue {statue_id_server} from network: {e}")
                        traceback.print_exc()
            elif statue_id_server in current_client_statues_map: # Server says invalid/gone
                statue_to_remove_invalid = current_client_statues_map[statue_id_server]
                if statue_to_remove_invalid.alive(): statue_to_remove_invalid.kill()
                if statue_to_remove_invalid in statue_objects_list_client: statue_objects_list_client.remove(statue_to_remove_invalid)
        
        # Remove statues on client that no longer exist on server
        server_statue_ids_present = set(received_statue_data_map.keys())
        client_statue_ids_to_remove_fully = set(current_client_statues_map.keys()) - server_statue_ids_present
        for removed_id_statue_fully in client_statue_ids_to_remove_fully:
            if removed_id_statue_fully in current_client_statues_map:
                statue_to_kill_fully = current_client_statues_map[removed_id_statue_fully]
                if statue_to_kill_fully.alive(): statue_to_kill_fully.kill()
                if statue_to_kill_fully in statue_objects_list_client: statue_objects_list_client.remove(statue_to_kill_fully)
        game_elements["statue_objects"] = statue_objects_list_client # Update main game_elements list

    # Projectile updates
    if 'projectiles' in network_state_data:
        received_proj_data_map = {p_data['id']: p_data for p_data in network_state_data.get('projectiles', []) if 'id' in p_data}
        current_client_proj_map = {p.projectile_id: p for p in projectile_sprites if hasattr(p, 'projectile_id')}

        # Map projectile type names (from server) to their classes
        projectile_class_map = {
            "Fireball": Fireball, "PoisonShot": PoisonShot, "BoltProjectile": BoltProjectile,
            "BloodShot": BloodShot, "IceShard": IceShard,
            "ShadowProjectile": ShadowProjectile, "GreyProjectile": GreyProjectile
            # Add other projectile classes here as they are created
        }

        # Update existing or create new projectiles on client
        for proj_id_server, proj_data_server in received_proj_data_map.items():
            if proj_id_server in current_client_proj_map: # Projectile exists on client
                existing_proj_client = current_client_proj_map[proj_id_server]
                if hasattr(existing_proj_client, 'set_network_data'):
                    existing_proj_client.set_network_data(proj_data_server)
            else: # New projectile from server, create on client
                owner_instance_client = None
                owner_id_from_server = proj_data_server.get('owner_id')
                if owner_id_from_server is not None: # Determine owner (P1 or P2)
                    if owner_id_from_server == 1 and player1: owner_instance_client = player1
                    elif owner_id_from_server == 2 and player2: owner_instance_client = player2
                
                # Check if essential data is present to create the projectile
                if owner_instance_client and 'pos' in proj_data_server and 'vel' in proj_data_server and 'type' in proj_data_server:
                    proj_type_name = proj_data_server['type']
                    ProjClass = projectile_class_map.get(proj_type_name) # Get class from map

                    if ProjClass:
                        # Direction vector from server velocity (or default if zero)
                        direction_vec_server = pygame.math.Vector2(proj_data_server['vel'])
                        if direction_vec_server.length_squared() == 0: # Fallback direction
                            direction_vec_server = pygame.math.Vector2(1,0) if owner_instance_client.facing_right else pygame.math.Vector2(-1,0)
                        
                        try:
                            # Create new projectile instance
                            new_proj_client = ProjClass(proj_data_server['pos'][0], proj_data_server['pos'][1],
                                                 direction_vec_server, owner_instance_client)
                            new_proj_client.projectile_id = proj_id_server # Assign server's ID
                            
                            # Apply full network state to new projectile
                            if hasattr(new_proj_client, 'set_network_data'):
                                new_proj_client.set_network_data(proj_data_server) 
                            
                            projectile_sprites.add(new_proj_client)
                            all_sprites.add(new_proj_client)
                        except Exception as e:
                            error(f"GSM Client: Error creating new projectile of type {proj_type_name} (ID: {proj_id_server}): {e}") 
                            traceback.print_exc()
                    else:
                        warning(f"GSM Client: Unknown projectile type '{proj_type_name}' received from server.")
                else:
                     warning(f"GSM Client: Insufficient data to create projectile {proj_id_server} (owner, pos, vel, or type missing).")


        # Remove projectiles on client that no longer exist on server
        client_proj_ids_to_remove = set(current_client_proj_map.keys()) - set(received_proj_data_map.keys())
        for removed_proj_id_client in client_proj_ids_to_remove:
            if removed_proj_id_client in current_client_proj_map:
                proj_to_kill_client = current_client_proj_map[removed_proj_id_client]
                if proj_to_kill_client.alive(): proj_to_kill_client.kill()
        game_elements["projectile_sprites"] = projectile_sprites # Update main game_elements