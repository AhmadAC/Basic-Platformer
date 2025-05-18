# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities.
version 1.0.0.8 (Set player control_scheme and joystick_id_idx from game_config)
"""
import sys
import pygame
import random
import traceback
import constants as C
from player import Player
from enemy import Enemy
from items import Chest 
from statue import Statue # Import the Statue class
import levels as LevelLoader # Assuming levels.py has your map loading functions
from camera import Camera
from typing import Dict, Optional, Any, Tuple, List 
import importlib 
import config as game_config # Import the game config


DEFAULT_LEVEL_MODULE_NAME = "level_default" # A fallback map if specific one fails

try:
    from logger import info, debug, warning, critical
except ImportError:
    print("CRITICAL GAME_SETUP: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Define error in the fallbac

def initialize_game_elements(current_width: int, current_height: int, 
                             for_game_mode: str = "unknown", 
                             existing_sprites_groups: Optional[Dict[str, Any]] = None,
                             map_module_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Initializes all game elements including players, enemies, items, platforms,
    and camera based on the selected map and game mode.

    Args:
        current_width (int): Current width of the game screen.
        current_height (int): Current height of the game screen.
        for_game_mode (str): The mode for which elements are being set up 
                             (e.g., "host", "couch_play", "join_lan").
        existing_sprites_groups (Optional[Dict[str, Any]]): 
            A dictionary of sprite groups from a previous state, used for
            preserving projectiles or other specific elements across resets/reloads.
        map_module_name (Optional[str]): The name of the map module to load (e.g., "level_default").

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing all initialized game elements,
                                 or None if a critical error occurs.
    """
    info(f"GameSetup: Initializing elements. Mode: '{for_game_mode}', Screen: {current_width}x{current_height}, Requested Map: '{map_module_name}'")

    # Initialize sprite groups
    platform_sprites = pygame.sprite.Group()
    ladder_sprites = pygame.sprite.Group()
    hazard_sprites = pygame.sprite.Group()
    enemy_sprites = pygame.sprite.Group() # For enemies specifically
    collectible_sprites = pygame.sprite.Group() # For chests, etc.
    statue_objects_list: List[Statue] = [] # List to hold Statue instances

    # Handle existing groups for projectiles and all_sprites
    projectile_sprites_from_existing = existing_sprites_groups.get('projectile_sprites') if existing_sprites_groups else None
    all_sprites_from_existing = existing_sprites_groups.get('all_sprites') if existing_sprites_groups else None

    projectile_sprites = projectile_sprites_from_existing if isinstance(projectile_sprites_from_existing, pygame.sprite.Group) else pygame.sprite.Group()
    all_sprites = all_sprites_from_existing if isinstance(all_sprites_from_existing, pygame.sprite.Group) else pygame.sprite.Group()
    
    debug(f"GameSetup: Initial projectile_sprites count: {len(projectile_sprites.sprites())}")
    debug(f"GameSetup: Initial all_sprites count: {len(all_sprites.sprites())}")

    # --- Clear existing non-persistent sprites from groups ---
    debug("GameSetup: Clearing sprite groups (except projectile_sprites and all_sprites initially)...")
    player1_to_kill = existing_sprites_groups.get('player1') if existing_sprites_groups else None
    if player1_to_kill and hasattr(player1_to_kill, 'kill'): player1_to_kill.kill()
    
    player2_to_kill = existing_sprites_groups.get('player2') if existing_sprites_groups else None
    if player2_to_kill and hasattr(player2_to_kill, 'kill'): player2_to_kill.kill()
    
    current_chest_to_kill = existing_sprites_groups.get('current_chest') if existing_sprites_groups else None
    if current_chest_to_kill and hasattr(current_chest_to_kill, 'kill'): current_chest_to_kill.kill()
    
    # Empty the specific groups that will be repopulated by the level loader
    for group in [platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites]:
        if group is not None: group.empty()
    
    # Clear all_sprites, but preserve projectiles if they were passed in
    if all_sprites_from_existing: # If all_sprites was passed, clear it selectively
        for sprite in list(all_sprites.sprites()): 
             # Don't kill players or chest yet, they are handled above or might be shells
             if sprite not in [player1_to_kill, player2_to_kill, current_chest_to_kill]:
                 # Kill everything else that isn't a Player (shells are okay) or a Projectile
                 if not isinstance(sprite, Player) and not ('Projectile' in sprite.__class__.__name__): 
                    sprite.kill() 
    
    # Clear projectiles specifically if not preserving them (usually done on full reset)
    if projectile_sprites_from_existing: # If this group was passed
        # Typically, for a full level load/reset, projectiles are cleared.
        # If you wanted to preserve projectiles between levels, this logic would change.
        projectile_sprites.empty() 

    debug(f"GameSetup: After clearing, projectile_sprites count: {len(projectile_sprites.sprites())}")
    debug(f"GameSetup: After clearing, all_sprites count: {len(all_sprites.sprites())}")

    enemy_list: List[Enemy] = [] # For direct access to Enemy instances

    # --- Load Level Data ---
    level_data_loaded_successfully = False
    target_map_name_for_load = map_module_name if map_module_name else None # Use requested or default
    
    # Initialize default level properties
    level_background_color = C.LIGHT_BLUE # Default background
    local_enemy_spawns_data_list: List[Dict[str,Any]] = [] 
    collectible_spawns_data_list: List[Dict[str,Any]] = []
    statue_spawns_data_list: List[Dict[str,Any]] = [] # For statues from map file
    
    player1_spawn_pos = (100, current_height - (C.TILE_SIZE * 2)) # Default spawn
    player2_spawn_pos = (150, current_height - (C.TILE_SIZE * 2)) # Default spawn
    
    level_pixel_width = current_width # Default to screen width
    lvl_min_y_abs = 0                 # Default top of level
    lvl_max_y_abs = current_height    # Default bottom of level (kill plane typically below this)
    ground_level_y = current_height - C.TILE_SIZE # Default ground reference
    ground_platform_height = C.TILE_SIZE          # Default ground thickness
    loaded_map_name_return = None                 # Name of the map successfully loaded

    if target_map_name_for_load: 
        # Sanitize map name for function calling (e.g., "my-map" -> "my_map")
        safe_map_name_for_func = target_map_name_for_load.replace('-', '_').replace(' ', '_')
        expected_level_load_func_name = f"load_map_{safe_map_name_for_func}"
        
        debug(f"GameSetup: Attempting to load map module 'maps.{target_map_name_for_load}' and call function '{expected_level_load_func_name}'")

        try:
            map_module_full_path = f"maps.{target_map_name_for_load}" # Assumes maps are in a 'maps' package
            
            # Reload module if already imported to pick up changes during development
            if map_module_full_path in sys.modules: 
                debug(f"GameSetup: Reloading map module '{map_module_full_path}'")
                map_module = importlib.reload(sys.modules[map_module_full_path])
            else:
                map_module = importlib.import_module(map_module_full_path)
            
            load_level_function = getattr(map_module, expected_level_load_func_name)
            
            # Call the map loading function - it should return a tuple of game elements
            # Adjust the expected number of elements if your map files return more/less
            # Example return: (platforms, ladders, hazards, enemies, collectibles, p1_spawn, width, min_y, max_y, ground_y, ground_h, bg_color, statues)
            level_data_tuple = load_level_function(current_width, current_height) 
            
            # Ensure the tuple has enough elements before unpacking
            # Adjust this number based on what your load_map_... functions return
            EXPECTED_ELEMENTS_FROM_MAP_LOAD = 12 # Base + background color
            EXPECTED_ELEMENTS_WITH_STATUES = 13 # If statues are included

            if level_data_tuple and len(level_data_tuple) >= EXPECTED_ELEMENTS_FROM_MAP_LOAD:
                (platform_data_group, ladder_data_group, hazard_data_group, 
                local_enemy_spawns_data_list_loaded, collectible_spawns_data_list_loaded, p1_spawn_tuple, 
                lvl_total_width_pixels_loaded, lvl_min_y_abs_loaded, lvl_max_y_abs_loaded, 
                main_ground_y_reference_loaded, main_ground_height_reference_loaded, 
                *optional_extras) = level_data_tuple[:EXPECTED_ELEMENTS_FROM_MAP_LOAD] # Unpack base elements

                # Populate sprite groups
                platform_sprites.add(platform_data_group.sprites() if platform_data_group else [])
                ladder_sprites.add(ladder_data_group.sprites() if ladder_data_group else [])
                hazard_sprites.add(hazard_data_group.sprites() if hazard_data_group else [])
                
                local_enemy_spawns_data_list = local_enemy_spawns_data_list_loaded if local_enemy_spawns_data_list_loaded else []
                collectible_spawns_data_list = collectible_spawns_data_list_loaded if collectible_spawns_data_list_loaded else []

                player1_spawn_pos = p1_spawn_tuple
                # Calculate P2 spawn relative to P1 and level width
                p2_spawn_x = p1_spawn_tuple[0] + C.TILE_SIZE * 1.5 
                if p2_spawn_x + (C.TILE_SIZE / 2) > lvl_total_width_pixels_loaded - C.TILE_SIZE: 
                    p2_spawn_x = lvl_total_width_pixels_loaded - C.TILE_SIZE * 2.5 
                if p2_spawn_x - (C.TILE_SIZE / 2) < C.TILE_SIZE:
                    p2_spawn_x = C.TILE_SIZE * 2.5
                player2_spawn_pos = (p2_spawn_x, p1_spawn_tuple[1])
                
                # Update level dimensions and references
                level_pixel_width = lvl_total_width_pixels_loaded
                lvl_min_y_abs = lvl_min_y_abs_loaded
                lvl_max_y_abs = lvl_max_y_abs_loaded
                ground_level_y = main_ground_y_reference_loaded
                ground_platform_height = main_ground_height_reference_loaded
                
                # Handle optional background color
                if optional_extras and isinstance(optional_extras[0], (tuple, list)) and len(optional_extras[0]) == 3:
                    level_background_color = optional_extras[0]
                
                # Handle optional statue data if present
                if len(level_data_tuple) >= EXPECTED_ELEMENTS_WITH_STATUES:
                    statue_spawns_data_list_from_map = level_data_tuple[EXPECTED_ELEMENTS_WITH_STATUES -1]
                    if isinstance(statue_spawns_data_list_from_map, list):
                        statue_spawns_data_list = statue_spawns_data_list_from_map
                    else:
                        debug(f"GameSetup: Statue data from map '{target_map_name_for_load}' was not a list.")
                
                debug(f"GameSetup: Level geometry loaded. Width: {level_pixel_width}, MinY: {lvl_min_y_abs}, MaxY: {lvl_max_y_abs}, P1 Spawn: {player1_spawn_pos}, P2 Spawn: {player2_spawn_pos}, BG Color: {level_background_color}, Statues: {len(statue_spawns_data_list)}")
                level_data_loaded_successfully = True
                loaded_map_name_return = target_map_name_for_load # Store the name of the map that was loaded
            else:
                critical(f"GameSetup CRITICAL Error: Map '{target_map_name_for_load}' function '{expected_level_load_func_name}' did not return enough data elements (expected at least {EXPECTED_ELEMENTS_FROM_MAP_LOAD}).")

        except ImportError:
            critical(f"GameSetup CRITICAL Error: Could not import map module 'maps.{target_map_name_for_load}'. Path issue?"); traceback.print_exc()
        except AttributeError:
            critical(f"GameSetup CRITICAL Error: Map module 'maps.{target_map_name_for_load}' does not have function '{expected_level_load_func_name}'."); traceback.print_exc()
        except Exception as e:
            critical(f"GameSetup CRITICAL Error: Unexpected error loading map '{target_map_name_for_load}': {e}"); traceback.print_exc()

        # Fallback to default map if specific map load failed (and it wasn't already the default)
        if not level_data_loaded_successfully:
            if target_map_name_for_load != DEFAULT_LEVEL_MODULE_NAME:
                warning(f"GameSetup Warning: Failed to load map '{target_map_name_for_load}'. Trying default map '{DEFAULT_LEVEL_MODULE_NAME}'.")
                # Recursive call to try loading the default map
                return initialize_game_elements(current_width, current_height, for_game_mode, existing_sprites_groups, DEFAULT_LEVEL_MODULE_NAME)
            else:
                critical(f"GameSetup FATAL: Default map '{DEFAULT_LEVEL_MODULE_NAME}' also failed to load. Cannot proceed."); return None
    else: # No map_module_name provided (e.g., client waiting for server map)
        debug("GameSetup: No map module name provided. Skipping level geometry loading. Players/camera shells will be created if mode requires.")
        loaded_map_name_return = None # No map loaded locally

    # Add loaded platforms, ladders, hazards to all_sprites group
    all_sprites.add(platform_sprites.sprites(), ladder_sprites.sprites(), hazard_sprites.sprites())
    
    # --- Initialize Players ---
    player1, player2 = None, None 

    if for_game_mode in ["host", "couch_play", "join_lan", "join_ip"]: # Modes that require at least P1
        player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1) 
        if not player1._valid_init: critical(f"GameSetup CRITICAL: P1 initialization failed."); return None
        player1.control_scheme = game_config.CURRENT_P1_INPUT_DEVICE # Set control scheme from global config
        if "joystick" in player1.control_scheme: # If P1 is using a joystick
            try: player1.joystick_id_idx = int(player1.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player1.joystick_id_idx = None # Invalid joystick ID format
        all_sprites.add(player1)

    if for_game_mode == "couch_play": # Couch play needs a locally controlled P2
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2) 
        if not player2._valid_init: critical(f"GameSetup CRITICAL: P2 (couch) initialization failed."); return None
        player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE # Set P2 control scheme
        if "joystick" in player2.control_scheme:
            try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
            except (IndexError, ValueError): player2.joystick_id_idx = None
        all_sprites.add(player2)
    elif for_game_mode in ["join_lan", "join_ip", "host"]: # Network modes create a P2 shell
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2) 
        if not player2._valid_init: critical(f"GameSetup CRITICAL: P2 shell initialization failed."); return None
        # For "host", P2 is remote, so no local control scheme needed here for P2.
        # For "join_lan"/"join_ip" (client side), P2 *is* locally controlled by this client machine.
        if for_game_mode != "host": # If this is a client machine (join_lan/join_ip)
            player2.control_scheme = game_config.CURRENT_P2_INPUT_DEVICE
            if "joystick" in player2.control_scheme:
                try: player2.joystick_id_idx = int(player2.control_scheme.split('_')[-1])
                except: player2.joystick_id_idx = None
        all_sprites.add(player2)


    # Set projectile group references for players
    debug(f"GameSetup: Before setting proj groups for P1: projectile_sprites count {len(projectile_sprites.sprites())}, all_sprites count {len(all_sprites.sprites())}")
    if player1 and hasattr(player1, 'set_projectile_group_references'): 
        player1.set_projectile_group_references(projectile_sprites, all_sprites)
    
    debug(f"GameSetup: Before setting proj groups for P2: projectile_sprites count {len(projectile_sprites.sprites())}, all_sprites count {len(all_sprites.sprites())}")
    if player2 and hasattr(player2, 'set_projectile_group_references'): 
        player2.set_projectile_group_references(projectile_sprites, all_sprites)


    # --- Initialize Enemies (Server/Couch Play only) ---
    if (for_game_mode == "host" or for_game_mode == "couch_play") and local_enemy_spawns_data_list:
        debug(f"GameSetup: Spawning {len(local_enemy_spawns_data_list)} enemies from level data...")
        # from enemy import Enemy # Already imported at top
        for i, spawn_info in enumerate(local_enemy_spawns_data_list):
            try:
                patrol_rect = pygame.Rect(spawn_info['patrol']) if spawn_info.get('patrol') else None
                enemy_color_id_from_map = spawn_info.get('enemy_color_id') # Get color from map data
                enemy_instance = Enemy(start_x=spawn_info['pos'][0], start_y=spawn_info['pos'][1], 
                              patrol_area=patrol_rect, enemy_id=i, color_name=enemy_color_id_from_map) 
                if enemy_instance._valid_init: 
                    all_sprites.add(enemy_instance); enemy_sprites.add(enemy_instance); enemy_list.append(enemy_instance)
                else:
                    warning(f"GameSetup Warning: Enemy {i} (Color: {enemy_color_id_from_map}) at {spawn_info['pos']} failed _valid_init during setup.")
            except Exception as e: 
                error(f"GameSetup Error: Spawning enemy {i} with data {spawn_info}: {e}"); traceback.print_exc()
    
    # --- Initialize Statues (Server/Couch Play only, from map data) ---
    if (for_game_mode == "host" or for_game_mode == "couch_play") and statue_spawns_data_list:
        debug(f"GameSetup: Spawning {len(statue_spawns_data_list)} statues from level data...")
        for i, statue_data in enumerate(statue_spawns_data_list):
            try:
                statue_id = statue_data.get('id', f"map_statue_{i}") # Use ID from map or generate one
                statue_pos_center_x, statue_pos_center_y = statue_data['pos'] # Assume 'pos' is center
                
                # Allow map data to specify custom images for this statue instance if desired
                custom_initial_img_path = statue_data.get('initial_image_path')
                custom_smashed_anim_path = statue_data.get('smashed_anim_path')

                new_statue = Statue(statue_pos_center_x, statue_pos_center_y, statue_id=statue_id,
                                    initial_image_path=custom_initial_img_path,
                                    smashed_anim_path=custom_smashed_anim_path)
                if new_statue._valid_init:
                    all_sprites.add(new_statue)
                    statue_objects_list.append(new_statue) # Add to the dedicated list
                    debug(f"GameSetup: Statue {statue_id} spawned at center ({statue_pos_center_x},{statue_pos_center_y}).")
                else:
                    warning(f"GameSetup Warning: Statue {statue_id} at {statue_data['pos']} failed _valid_init.")
            except Exception as e:
                error(f"GameSetup Error: Spawning statue {i} with data {statue_data}: {e}"); traceback.print_exc()


    # --- Initialize Chest (Server/Couch Play only) ---
    current_chest = None
    if Chest and (for_game_mode == "host" or for_game_mode == "couch_play"): 
        # First, try to spawn from collectible_spawns_data_list if a chest is defined
        if collectible_spawns_data_list:
            for item_data in collectible_spawns_data_list:
                if item_data.get('type') == 'chest':
                    try:
                        chest_midbottom_x, chest_midbottom_y = item_data['pos'] # Expect midbottom
                        current_chest = Chest(chest_midbottom_x, chest_midbottom_y) 
                        if current_chest._valid_init:
                            all_sprites.add(current_chest); collectible_sprites.add(current_chest)
                            debug(f"GameSetup: Chest spawned from level data at {current_chest.rect.topleft} (midbottom: {item_data['pos']})")
                            break # Spawned one chest from data, stop looking
                        else: warning(f"GameSetup Warning: Chest from level data at {item_data['pos']} failed _valid_init.")
                    except Exception as e: error(f"GameSetup Error spawning chest from level data: {e}")
        
        # If no chest was spawned from data, try random spawn (if spawn_chest is implemented)
        if not current_chest: 
            debug("GameSetup: No chest from level data, attempting random spawn on ledge...")
            current_chest = spawn_chest(platform_sprites, ground_level_y) # Pass platforms and ground level
            if current_chest:
                all_sprites.add(current_chest); collectible_sprites.add(current_chest)
                debug(f"GameSetup: Random chest spawned at {current_chest.rect.topleft}")
            else: debug("GameSetup: Random chest spawn also failed or returned None.")


    # --- Initialize Camera ---
    camera_instance = Camera(level_pixel_width, lvl_min_y_abs, lvl_max_y_abs, current_width, current_height)

    debug(f"GameSetup: Final counts before return - AllSprites: {len(all_sprites.sprites())}, Projectiles: {len(projectile_sprites.sprites())}, Statues: {len(statue_objects_list)}")

    # --- Prepare and return the dictionary of game elements ---
    game_elements_dict = {
        "player1": player1, "player2": player2, "camera": camera_instance,
        "current_chest": current_chest, "enemy_list": enemy_list,
        "platform_sprites": platform_sprites, "ladder_sprites": ladder_sprites,
        "hazard_sprites": hazard_sprites, "enemy_sprites": enemy_sprites,
        "collectible_sprites": collectible_sprites, "projectile_sprites": projectile_sprites,
        "all_sprites": all_sprites,
        "statue_objects": statue_objects_list, # Add the list of Statue instances
        # Level dimension info
        "level_pixel_width": level_pixel_width, 
        "level_min_y_absolute": lvl_min_y_abs,
        "level_max_y_absolute": lvl_max_y_abs, 
        "ground_level_y": ground_level_y,
        "ground_platform_height": ground_platform_height,
        # Spawn info
        "player1_spawn_pos": player1_spawn_pos, 
        "player2_spawn_pos": player2_spawn_pos,
        "enemy_spawns_data_cache": local_enemy_spawns_data_list, # Cache for respawning or client sync
        # Visuals
        "level_background_color": level_background_color,
        "loaded_map_name": loaded_map_name_return # Name of map loaded (or None)
    }
    return game_elements_dict


def spawn_chest(all_platform_sprites_group: pygame.sprite.Group, main_ground_y_surface_level: int) -> Optional[Chest]:
    """
    Spawns a chest randomly on a suitable 'ledge' platform.
    If no suitable ledges are found, returns None.
    """
    if Chest is None: 
        warning("GameSetup (spawn_chest): Chest class is None, cannot spawn."); return None
    
    try:
        # Filter for platforms that are explicitly typed as "ledge" and are wide enough
        ledge_platforms = [
            p for p in all_platform_sprites_group 
            if hasattr(p, 'platform_type') and p.platform_type == "ledge" and 
               p.rect.width > C.TILE_SIZE * 1.25 # Ensure ledge is wide enough for a chest
        ]
        
        if not ledge_platforms: 
            debug("GameSetup (spawn_chest): No suitable 'ledge' platforms found for chest spawn."); return None
        
        # Optionally, further filter ledges to be within a certain vertical range if desired
        # e.g., not too high, not too low. For now, any valid ledge is a candidate.
        # Example:
        # moderate_y_min = main_ground_y_surface_level - C.TILE_SIZE * 4 
        # moderate_y_max = main_ground_y_surface_level + C.TILE_SIZE * 1 # Allow slightly below main ground too
        # candidate_platforms = [p for p in ledge_platforms if moderate_y_min <= p.rect.top <= moderate_y_max]
        # if not candidate_platforms: candidate_platforms = list(ledge_platforms) # Fallback to any ledge if filtered list is empty
        
        candidate_platforms = list(ledge_platforms) # Use all found ledges for now
        if not candidate_platforms: 
            debug("GameSetup (spawn_chest): No candidate ledges after filtering (if any)."); return None

        chosen_platform = random.choice(candidate_platforms)
        
        # Calculate spawn position on the chosen platform (midbottom)
        # Ensure chest is placed reasonably on the platform, not hanging off edges
        inset = C.TILE_SIZE * 0.5 # How far from edge of platform to spawn
        min_cx = chosen_platform.rect.left + inset
        max_cx = chosen_platform.rect.right - inset
        
        # If platform is too narrow after inset, place at center
        cx = random.randint(int(min_cx), int(max_cx)) if min_cx < max_cx else chosen_platform.rect.centerx
        cy = chosen_platform.rect.top # Chest's bottom will align with platform's top
        
        debug(f"GameSetup (spawn_chest): Attempting to spawn chest at calculated pos (midbottom): ({cx},{cy}) on platform {chosen_platform.rect}")
        new_chest = Chest(cx, cy) # Chest constructor expects midbottom
        
        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
            debug(f"GameSetup (spawn_chest): Random chest spawned on ledge at {new_chest.rect.topleft} (midbottom: ({cx},{cy}))")
            return new_chest
        else:
            warning(f"GameSetup (spawn_chest): New chest created at ({cx},{cy}) failed _valid_init.")
            
    except Exception as e:
        error(f"GameSetup Error in spawn_chest: {e}"); traceback.print_exc()
    return None