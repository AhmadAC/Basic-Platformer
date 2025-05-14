# game_setup.py
# -*- coding: utf-8 -*-
"""
Handles initialization of game elements, levels, and entities.
version 1.0.0.5 (Chest spawning restricted to 'ledge' platform_type)
"""
import pygame
import random
import traceback
import constants as C
from player import Player
from enemy import Enemy
from items import Chest # Ensure Chest is importable
import levels as LevelLoader
from camera import Camera

def initialize_game_elements(current_width, current_height, for_game_mode="unknown", existing_sprites_groups=None):
    """
    Initializes all platformer game elements for a given mode.
    Returns a dictionary containing all initialized game objects and parameters.
    """
    print(f"Initializing platformer elements for mode: {for_game_mode}...")

    platform_sprites = pygame.sprite.Group()
    ladder_sprites = pygame.sprite.Group()
    hazard_sprites = pygame.sprite.Group()
    enemy_sprites = pygame.sprite.Group()
    collectible_sprites = pygame.sprite.Group()
    projectile_sprites = existing_sprites_groups.get('projectile_sprites') if existing_sprites_groups else pygame.sprite.Group()
    all_sprites = existing_sprites_groups.get('all_sprites') if existing_sprites_groups else pygame.sprite.Group()

    # Clear sprite groups passed in or newly created
    # Use .get() for players/chest in case they weren't initialized in a previous run
    player1_to_kill = existing_sprites_groups.get('player1')
    if player1_to_kill and hasattr(player1_to_kill, 'kill'):
        player1_to_kill.kill()
    
    player2_to_kill = existing_sprites_groups.get('player2')
    if player2_to_kill and hasattr(player2_to_kill, 'kill'):
        player2_to_kill.kill()

    current_chest_to_kill = existing_sprites_groups.get('current_chest')
    if current_chest_to_kill and hasattr(current_chest_to_kill, 'kill'):
        current_chest_to_kill.kill()
    
    for sprite_group in [platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites, collectible_sprites, projectile_sprites, all_sprites]:
        if sprite_group is not None: 
            for sprite in sprite_group: 
                 if hasattr(sprite, 'kill'): sprite.kill()
            sprite_group.empty()
            
    enemy_list = []

    print("Loading level data via LevelLoader...")
    try:
        platform_data_group, ladder_data_group, hazard_data_group, local_enemy_spawns_data_list, \
        p1_spawn_tuple, lvl_total_width_pixels, lvl_min_y_abs, lvl_max_y_abs, \
        main_ground_y_reference, main_ground_height_reference = \
            LevelLoader.load_map_cpu(current_width, current_height) # Using load_map_cpu as default

        platform_sprites.add(platform_data_group.sprites())
        ladder_sprites.add(ladder_data_group.sprites())
        hazard_sprites.add(hazard_data_group.sprites())
        
        player1_spawn_pos = p1_spawn_tuple
        p2_spawn_x = p1_spawn_tuple[0] + C.TILE_SIZE * 1.5
        # Ensure P2 spawn is within the playable horizontal area
        if p2_spawn_x + (C.TILE_SIZE / 2) > lvl_total_width_pixels - C.TILE_SIZE: 
            p2_spawn_x = lvl_total_width_pixels - C.TILE_SIZE * 2.5 
        if p2_spawn_x - (C.TILE_SIZE / 2) < C.TILE_SIZE:
            p2_spawn_x = C.TILE_SIZE * 2.5
        player2_spawn_pos = (p2_spawn_x, p1_spawn_tuple[1])
        
        level_pixel_width = lvl_total_width_pixels
        ground_level_y = main_ground_y_reference
        ground_platform_height = main_ground_height_reference
        print(f"Level geometry loaded. Width: {level_pixel_width}, MinY: {lvl_min_y_abs}, MaxY: {lvl_max_y_abs}")
    except Exception as e:
        print(f"CRITICAL ERROR loading level: {e}")
        traceback.print_exc()
        return None

    all_sprites.add(platform_sprites.sprites(), ladder_sprites.sprites(), hazard_sprites.sprites())
    player1, player2 = None, None

    if for_game_mode in ["host", "couch_play", "single_player"]:
        print("Initializing player 1...")
        player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 init failed."); return None
        all_sprites.add(player1)
        print("P1 initialized.")

    if for_game_mode == "couch_play":
        print("Initializing player 2 (couch)...")
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (couch) init failed."); return None
        all_sprites.add(player2)
        print("P2 (couch) initialized.")
    elif for_game_mode == "host": 
        print("Initializing player 2 (remote placeholder for host)...")
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (remote placeholder) init failed."); return None
        all_sprites.add(player2)
        print("P2 (remote placeholder) initialized.")
    elif for_game_mode == "client": 
        print("Initializing player 1 (remote placeholder for client)...")
        player1 = Player(player1_spawn_pos[0], player1_spawn_pos[1], player_id=1)
        if not player1._valid_init: print("CRITICAL: P1 (remote placeholder) init failed."); return None
        all_sprites.add(player1)
        print("P1 (remote placeholder) initialized.")
        
        print("Initializing player 2 (local client)...")
        player2 = Player(player2_spawn_pos[0], player2_spawn_pos[1], player_id=2)
        if not player2._valid_init: print("CRITICAL: P2 (local client) init failed."); return None
        all_sprites.add(player2)
        print("P2 (local client) initialized.")

    if player1 and hasattr(player1, 'set_projectile_group_references'):
        player1.set_projectile_group_references(projectile_sprites, all_sprites)
    if player2 and hasattr(player2, 'set_projectile_group_references'):
        player2.set_projectile_group_references(projectile_sprites, all_sprites)

    if for_game_mode in ["host", "couch_play", "single_player"]: 
        print(f"Spawning {len(local_enemy_spawns_data_list)} enemies (server/local)...")
        for i, spawn_data_item in enumerate(local_enemy_spawns_data_list):
            try:
                patrol_rect_data = spawn_data_item.get('patrol')
                patrol_rect_obj = None
                if patrol_rect_data:
                    try: patrol_rect_obj = pygame.Rect(patrol_rect_data)
                    except TypeError: print(f"Warning: Invalid patrol data for enemy {i}: {patrol_rect_data}")
                
                enemy = Enemy(spawn_data_item['pos'][0], spawn_data_item['pos'][1], patrol_area=patrol_rect_obj, enemy_id=i)
                if enemy._valid_init:
                    all_sprites.add(enemy); enemy_sprites.add(enemy); enemy_list.append(enemy)
                else: print(f"Error: Enemy {i} at {spawn_data_item['pos']} init failed.")
            except Exception as e: print(f"Error spawning enemy {i} at {spawn_data_item.get('pos', 'N/A')}: {e}")
        print(f"Enemies spawned: {len(enemy_list)}")
    
    current_chest = None
    if Chest and for_game_mode in ["host", "couch_play", "single_player"]:
        # Pass all platform_sprites, spawn_chest will filter by platform_type
        current_chest = spawn_chest(platform_sprites, main_ground_y_reference) 
        if current_chest:
            all_sprites.add(current_chest)
            collectible_sprites.add(current_chest)
            # game_elements["current_chest"] will be updated with this return value in main.py
        # else:
            # game_elements["current_chest"] = None # Explicitly ensure it's None if spawn failed

    camera_instance = Camera(level_pixel_width, lvl_min_y_abs, lvl_max_y_abs, current_width, current_height)
    print(f"Camera initialized with: LvlW={level_pixel_width}, LvlMinY={lvl_min_y_abs}, LvlMaxY={lvl_max_y_abs}, ScreenW={current_width}, ScreenH={current_height}")

    return {
        "player1": player1, "player2": player2, "camera": camera_instance,
        "current_chest": current_chest, # current_chest from this scope
        "enemy_list": enemy_list,
        "platform_sprites": platform_sprites, "ladder_sprites": ladder_sprites,
        "hazard_sprites": hazard_sprites, "enemy_sprites": enemy_sprites,
        "collectible_sprites": collectible_sprites, "projectile_sprites": projectile_sprites,
        "all_sprites": all_sprites,
        "level_pixel_width": level_pixel_width, 
        "level_min_y_absolute": lvl_min_y_abs,
        "level_max_y_absolute": lvl_max_y_abs,
        "ground_level_y": ground_level_y,
        "ground_platform_height": ground_platform_height,
        "player1_spawn_pos": player1_spawn_pos, 
        "player2_spawn_pos": player2_spawn_pos,
        "enemy_spawns_data_cache": local_enemy_spawns_data_list 
    }

def spawn_chest(all_platform_sprites_group, main_ground_y_surface_level):
    """
    Spawns a chest ONLY on platforms explicitly marked as 'ledge' (platform_type="ledge").
    Tries to pick a ledge within a reasonable vertical band if possible.
    """
    if Chest is None: 
        print("Warning: Chest class not available for spawning.")
        return None
    try:
        # Filter for platforms that are specifically designated as ledges and are wide enough
        ledge_platforms = [
            p for p in all_platform_sprites_group
            if hasattr(p, 'platform_type') and p.platform_type == "ledge" and p.rect.width > C.TILE_SIZE * 1.25
        ]

        if not ledge_platforms:
            print("Warning: No 'ledge' type platforms found to spawn chest on. Chest will not spawn.")
            return None

        candidate_platforms = []
        # Tier 1: Ledges within a moderate vertical band around the main ground.
        # This encourages chests to spawn in more accessible/central areas.
        moderate_y_min = main_ground_y_surface_level - C.TILE_SIZE * 4 
        moderate_y_max = main_ground_y_surface_level + C.TILE_SIZE * 1 
        candidate_platforms = [
            p for p in ledge_platforms # Start with already filtered ledge_platforms
            if moderate_y_min <= p.rect.top <= moderate_y_max
        ]

        # Tier 2: If no Tier 1, use any available ledge_platform.
        if not candidate_platforms:
            candidate_platforms = list(ledge_platforms) 
            # This ensures we still use a ledge if none were in the "moderate" band.

        if not candidate_platforms: # Should not happen if ledge_platforms was not empty
            print("Error: No suitable 'ledge' platforms remained after tiering. Chest will not spawn.")
            return None

        chosen_platform = random.choice(candidate_platforms)
        
        # Ensure chest spawns within platform horizontal bounds, slightly inset
        chest_inset = C.TILE_SIZE * 0.5 
        min_cx = chosen_platform.rect.left + chest_inset
        max_cx = chosen_platform.rect.right - chest_inset
        
        # If platform is too narrow for inset, place in center
        cx = random.randint(int(min_cx), int(max_cx)) if min_cx < max_cx else chosen_platform.rect.centerx
        # Chest constructor expects midbottom X,Y. Spawn with bottom of chest at the top surface of the platform.
        cy = chosen_platform.rect.top 
        
        new_chest = Chest(cx, cy) # Chest's rect will be anchored midbottom=(cx, cy)
        if hasattr(new_chest, '_valid_init') and new_chest._valid_init:
            platform_info = f"'{chosen_platform.platform_type}' platform (Color: {chosen_platform.color if hasattr(chosen_platform, 'color') else 'N/A'})"
            print(f"Chest object created on {platform_info} at y={chosen_platform.rect.top}. Chest midbottom: ({int(new_chest.rect.midbottom[0])}, {int(new_chest.rect.midbottom[1])}).")
            return new_chest
        else:
            print("Failed to initialize new chest object (invalid init after creation).")
    except Exception as e:
        print(f"Error creating new chest object: {e}")
        traceback.print_exc()
    return None