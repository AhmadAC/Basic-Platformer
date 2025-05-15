# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities.
version 1.0.0.7 (Added debug prints for projectile group assignment)
"""
import sys
import pygame
import random
import traceback
import constants as C
from player import Player
from enemy import Enemy
from items import Chest 
import levels as LevelLoader 
from camera import Camera
from typing import Dict, Optional, Any, Tuple, List 
import importlib 

DEFAULT_LEVEL_MODULE_NAME = "level_default" 

def initialize_game_elements(current_width: int, current_height: int, 
                             for_game_mode: str = "unknown", 
                             existing_sprites_groups: Optional[Dict[str, Any]] = None,
                             map_module_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    print(f"DEBUG GameSetup: Initializing elements. Mode: '{for_game_mode}', Screen: {current_width}x{current_height}, Requested Map: '{map_module_name}'")

    platform_sprites = pygame.sprite.Group()
    ladder_sprites = pygame.sprite.Group()
    hazard_sprites = pygame.sprite.Group()
    enemy_sprites = pygame.sprite.Group()
    collectible_sprites = pygame.sprite.Group()
    
    projectile_sprites_from_existing = existing_sprites_groups.get('projectile_sprites') if existing_sprites_groups else None
    all_sprites_from_existing = existing_sprites_groups.get('all_sprites') if existing_sprites_groups else None

    projectile_sprites = projectile_sprites_from_existing if isinstance(projectile_sprites_from_existing, pygame.sprite.Group) else pygame.sprite.Group()
    all_sprites = all_sprites_from_existing if isinstance(all_sprites_from_existing, pygame.sprite.Group) else pygame.sprite.Group()
    
    print(f"DEBUG GameSetup: Initial projectile_sprites: {projectile_sprites} (Count: {len(projectile_sprites.sprites())})")
    print(f"DEBUG GameSetup: Initial all_sprites: {all_sprites} (Count: {len(all_sprites.sprites())})")


    print("DEBUG GameSetup: Clearing sprite groups (except projectile_sprites and all_sprites initially)...")
    player1_to_kill = existing_sprites_groups.get('player1') if existing_sprites_groups else None
    if player1_to_kill and hasattr(player1_to_kill, 'kill'): player1_to_kill.kill()
    player2_to_kill = existing_sprites_groups.get('player2') if existing_sprites_groups else None
    if player2_to_kill and hasattr(player2_to_kill, 'kill'): player2_to_kill.kill()
    current_chest_to_kill = existing_sprites_groups.get('current_chest') if existing_sprites_groups else None
    if current_chest_to_kill and hasattr(current_chest_to_kill, 'kill'): current_chest_to_kill.kill()
    
    for group in [platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites]:
        if group is not None: group.empty()
    
    if all_sprites_from_existing: 
        for sprite in list(all_sprites.sprites()): # Iterate over a copy
             if sprite not in [player1_to_kill, player2_to_kill, current_chest_to_kill]:
                 if not isinstance(sprite, Player): 
                    sprite.kill() 
    
    if projectile_sprites_from_existing: 
        projectile_sprites.empty() 

    print(f"DEBUG GameSetup: After clearing, projectile_sprites: {projectile_sprites} (Count: {len(projectile_sprites.sprites())})")
    print(f"DEBUG GameSetup: After clearing, all_sprites: {all_sprites} (Count: {len(all_sprites.sprites())})")

            
    enemy_list: List[Enemy] = [] 

    level_data_loaded_successfully = False
    # If map_module_name is None (e.g. client initial call), we don't load level geometry yet.
    target_map_name_for_load = map_module_name if map_module_name else None
    
    # Default values if no map is loaded yet
    level_background_color = C.LIGHT_BLUE 
    local_enemy_spawns_data_list = [] 
    collectible_spawns_data_list = []
    player1_spawn_pos = (100, current_height - (C.TILE_SIZE * 2)) 
    player2_spawn_pos = (150, current_height - (C.TILE_SIZE * 2)) 
    level_pixel_width = current_width
    lvl_min_y_abs = 0
    lvl_max_y_abs = current_height
    ground_level_y = current_height - C.TILE_SIZE
    ground_platform_height = C.TILE_SIZE
    loaded_map_name_return = None # To return the name of the map that was actually loaded

    if target_map_name_for_load: # Only attempt to load map data if a name is provided
        safe_map_name_for_func = target_map_name_for_load.replace('-', '_').replace(' ', '_')
        expected_level_load_func_name = f"load_map_{safe_map_name_for_func}"
        
        print(f"DEBUG GameSetup: Attempting to load map module 'maps.{target_map_name_for_load}' and call function '{expected_level_load_func_name}'")

        try:
            map_module_full_path = f"maps.{target_map_name_for_load}"
            if map_module_full_path in sys.modules: # If already imported, reload for potential updates
                print(f"DEBUG GameSetup: Reloading map module '{map_module_full_path}'")
                map_module = importlib.reload(sys.modules[map_module_full_path])
            else:
                map_module = importlib.import_module(map_module_full_path)
            
            load_level_function = getattr(map_module, expected_level_load_func_name)
            level_data_tuple = load_level_function(current_width, current_height)
            
            if level_data_tuple and len(level_data_tuple) >= 11:
                (platform_data_group, ladder_data_group, hazard_data_group, 
                local_enemy_spawns_data_list_loaded, collectible_spawns_data_list_loaded, p1_spawn_tuple, 
                lvl_total_width_pixels_loaded, lvl_min_y_abs_loaded, lvl_max_y_abs_loaded, 
                main_ground_y_reference_loaded, main_ground_height_reference_loaded, 
                *optional_bg_color_list) = level_data_tuple

                platform_sprites.add(platform_data_group.sprites() if platform_data_group else [])
                ladder_sprites.add(ladder_data_group.sprites() if ladder_data_group else [])
                hazard_sprites.add(hazard_data_group.sprites() if hazard_data_group else [])
                
                local_enemy_spawns_data_list = local_enemy_spawns_data_list_loaded if local_enemy_spawns_data_list_loaded else []
                collectible_spawns_data_list = collectible_spawns_data_list_loaded if collectible_spawns_data_list_loaded else []

                player1_spawn_pos = p1_spawn_tuple
                p2_spawn_x = p1_spawn_tuple[0] + C.TILE_SIZE * 1.5
                if p2_spawn_x + (C.TILE_SIZE / 2) > lvl_total_width_pixels_loaded - C.TILE_SIZE: 
                    p2_spawn_x = lvl_total_width_pixels_loaded - C.TILE_SIZE * 2.5 
                if p2_spawn_x - (C.TILE_SIZE / 2) < C.TILE_SIZE:
                    p2_spawn_x = C.TILE_SIZE * 2.5
                player2_spawn_pos = (p2_spawn_x, p1_spawn_tuple[1])
                
                level_pixel_width = lvl_total_width_pixels_loaded
                lvl_min_y_abs = lvl_min_y_abs_loaded
                lvl_max_y_abs = lvl_max_y_abs_loaded
                ground_level_y = main_ground_y_reference_loaded
                ground_platform_height = main_ground_height_reference_loaded
                
                if optional_bg_color_list and isinstance(optional_bg_color_list[0], (tuple, list)) and len(optional_bg_color_list[0]) == 3:
                    level_background_color = optional_bg_color_list[0]
                    
                print(f"DEBUG GameSetup: Level geometry loaded. Width: {level_pixel_width}, MinY: {lvl_min_y_abs}, MaxY: {lvl_max_y_abs}, P1 Spawn: {player1_spawn_pos}, P2 Spawn: {player2_spawn_pos}, BG Color: {level_background_color}")
                level_data_loaded_successfully = True
                loaded_map_name_return = target_map_name_for_load
            else:
                print(f"CRITICAL GameSetup Error: Map '{target_map_name_for_load}' function '{expected_level_load_func_name}' did not return enough data elements.")

        except ImportError:
            print(f"CRITICAL GameSetup Error: Could not import map module 'maps.{target_map_name_for_load}'."); traceback.print_exc()
        except AttributeError:
            print(f"CRITICAL GameSetup Error: Map module 'maps.{target_map_name_for_load}' no func '{expected_level_load_func_name}'."); traceback.print_exc()
        except Exception as e:
            print(f"CRITICAL GameSetup Error: Unexpected error loading map '{target_map_name_for_load}': {e}"); traceback.print_exc()

        if not level_data_loaded_successfully:
            if target_map_name_for_load != DEFAULT_LEVEL_MODULE_NAME:
                print(f"GAME_SETUP Warning: Failed to load map '{target_map_name_for_load}'. Trying default '{DEFAULT_LEVEL_MODULE_NAME}'.")
                return initialize_game_elements(current_width, current_height, for_game_mode, existing_sprites_groups, DEFAULT_LEVEL_MODULE_NAME)
            else:
                print(f"GAME_SETUP FATAL: Default map '{DEFAULT_LEVEL_MODULE_NAME}' also failed. Cannot proceed."); return None
    else: # No map_module_name provided, e.g., client initial setup
        print("DEBUG GameSetup: No map module name provided, skipping level geometry loading. Only players/camera shells will be created if mode requires.")
        loaded_map_name_return = None # Explicitly none if no map loaded.

    all_sprites.add(platform_sprites.sprites(), ladder_sprites.sprites(), hazard_sprites.sprites())
    
    player1, player2 = None, None 

    if for_game_mode in ["host", "couch_play", "join_lan", "join_ip"]:
        player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1) 
        if not player1._valid_init: print(f"CRITICAL GameSetup: P1 init failed."); return None
        all_sprites.add(player1)

    if for_game_mode == "couch_play":
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2) 
        if not player2._valid_init: print(f"CRITICAL GameSetup: P2 (couch) init failed."); return None
        all_sprites.add(player2)
    elif for_game_mode in ["join_lan", "join_ip", "host"]: # Host also needs a P2 shell for network data
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2) 
        if not player2._valid_init: print(f"CRITICAL GameSetup: P2 shell init failed."); return None
        all_sprites.add(player2)


    print(f"DEBUG GameSetup: Before setting proj groups for P1: projectile_sprites is {('set' if projectile_sprites is not None else 'None')}, all_sprites is {('set' if all_sprites is not None else 'None')}")
    if player1 and hasattr(player1, 'set_projectile_group_references'): 
        player1.set_projectile_group_references(projectile_sprites, all_sprites)
    
    print(f"DEBUG GameSetup: Before setting proj groups for P2: projectile_sprites is {('set' if projectile_sprites is not None else 'None')}, all_sprites is {('set' if all_sprites is not None else 'None')}")
    if player2 and hasattr(player2, 'set_projectile_group_references'): 
        player2.set_projectile_group_references(projectile_sprites, all_sprites)


    if (for_game_mode == "host" or for_game_mode == "couch_play") and local_enemy_spawns_data_list:
        print(f"DEBUG GameSetup: Spawning {len(local_enemy_spawns_data_list)} enemies...")
        from enemy import Enemy 
        for i, spawn_info in enumerate(local_enemy_spawns_data_list):
            try:
                patrol_rect = pygame.Rect(spawn_info['patrol']) if spawn_info.get('patrol') else None
                enemy = Enemy(start_x=spawn_info['pos'][0], start_y=spawn_info['pos'][1], 
                              patrol_area=patrol_rect, enemy_id=i) 
                if enemy._valid_init: 
                    all_sprites.add(enemy); enemy_sprites.add(enemy); enemy_list.append(enemy)
                else:
                    print(f"Warning GameSetup: Enemy {i} at {spawn_info['pos']} failed _valid_init.")
            except Exception as e: print(f"Error spawning enemy {i} with data {spawn_info}: {e}"); traceback.print_exc()
    
    current_chest = None
    if Chest and (for_game_mode == "host" or for_game_mode == "couch_play"): 
        if collectible_spawns_data_list:
            for item_data in collectible_spawns_data_list:
                if item_data.get('type') == 'chest':
                    try:
                        chest_midbottom_x, chest_midbottom_y = item_data['pos']
                        current_chest = Chest(chest_midbottom_x, chest_midbottom_y) 
                        if current_chest._valid_init:
                            all_sprites.add(current_chest); collectible_sprites.add(current_chest)
                            print(f"DEBUG GameSetup: Chest spawned from level data at {current_chest.rect.topleft}")
                            break 
                        else: print(f"Warning GameSetup: Chest from level data at {item_data['pos']} failed _valid_init.")
                    except Exception as e: print(f"Error spawning chest from level data: {e}")
        
        if not current_chest: 
            print("DEBUG GameSetup: No chest from level data, attempting random spawn on ledge...")
            current_chest = spawn_chest(platform_sprites, ground_level_y) 
            if current_chest:
                all_sprites.add(current_chest); collectible_sprites.add(current_chest)
                print(f"DEBUG GameSetup: Random chest spawned at {current_chest.rect.topleft}")
            else: print("DEBUG GameSetup: Random chest spawn also failed or returned None.")


    camera_instance = Camera(level_pixel_width, lvl_min_y_abs, lvl_max_y_abs, current_width, current_height)

    print(f"DEBUG GameSetup: Final counts before return - AllSprites: {len(all_sprites.sprites())}, Projectiles: {len(projectile_sprites.sprites())}")

    game_elements_dict = {
        "player1": player1, "player2": player2, "camera": camera_instance,
        "current_chest": current_chest, "enemy_list": enemy_list,
        "platform_sprites": platform_sprites, "ladder_sprites": ladder_sprites,
        "hazard_sprites": hazard_sprites, "enemy_sprites": enemy_sprites,
        "collectible_sprites": collectible_sprites, "projectile_sprites": projectile_sprites,
        "all_sprites": all_sprites,
        "level_pixel_width": level_pixel_width, "level_min_y_absolute": lvl_min_y_abs,
        "level_max_y_absolute": lvl_max_y_abs, "ground_level_y": ground_level_y,
        "ground_platform_height": ground_platform_height,
        "player1_spawn_pos": player1_spawn_pos, "player2_spawn_pos": player2_spawn_pos,
        "enemy_spawns_data_cache": local_enemy_spawns_data_list, 
        "level_background_color": level_background_color,
        "loaded_map_name": loaded_map_name_return # Return the name of the map loaded
    }
    return game_elements_dict

# RENAMED FUNCTION from spawn_chest_on_ledge to spawn_chest
def spawn_chest(all_platform_sprites_group: pygame.sprite.Group, main_ground_y_surface_level: int) -> Optional[Chest]:
    """
    Spawns a chest ONLY on platforms explicitly marked as 'ledge'.
    """
    if Chest is None: print("Warning GS (spawn_chest): Chest class is None, cannot spawn."); return None
    try:
        ledge_platforms = [p for p in all_platform_sprites_group if hasattr(p, 'platform_type') and p.platform_type == "ledge" and p.rect.width > C.TILE_SIZE * 1.25]
        if not ledge_platforms: print("Warning GS (spawn_chest): No 'ledge' platforms for chest."); return None
        
        moderate_y_min = main_ground_y_surface_level - C.TILE_SIZE * 4 
        moderate_y_max = main_ground_y_surface_level + C.TILE_SIZE * 1 
        candidate_platforms = [p for p in ledge_platforms if moderate_y_min <= p.rect.top <= moderate_y_max]
        if not candidate_platforms: candidate_platforms = list(ledge_platforms)
        if not candidate_platforms: print("Warning GS (spawn_chest): No suitable candidate ledges."); return None

        chosen_platform = random.choice(candidate_platforms)
        inset = C.TILE_SIZE * 0.5 
        min_cx, max_cx = chosen_platform.rect.left + inset, chosen_platform.rect.right - inset
        cx = random.randint(int(min_cx), int(max_cx)) if min_cx < max_cx else chosen_platform.rect.centerx
        cy = chosen_platform.rect.top 
        
        print(f"DEBUG GS (spawn_chest): Attempting to spawn chest at calculated pos: ({cx},{cy}) on platform {chosen_platform.rect}")
        new_chest = Chest(cx, cy) # Chest constructor expects midbottom X, Y for its rect.bottom
        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
            print(f"DEBUG GS (spawn_chest): Chest spawned on ledge at {new_chest.rect.midbottom}")
            return new_chest
        else:
            print(f"Warning GS (spawn_chest): New chest created at ({cx},{cy}) failed _valid_init.")
    except Exception as e:
        print(f"Error in spawn_chest: {e}"); traceback.print_exc()
    return None