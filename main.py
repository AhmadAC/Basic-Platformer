# main.py
# -*- coding: utf-8 -*-
"""
Main game script for the Platformer.
Handles initialization, game loop, events, drawing, and level loading.
"""
import pygame
import sys
import os
import math
import random

# Import modules
import constants as C
from player import Player  # Ensure Player class is imported
from enemy import Enemy
from tiles import Platform, Ladder, Lava
# Assuming items.py exists and contains Chest
try:
    from items import Chest
except ImportError:
    print("Warning: items.py or Chest class not found. Chests will not be available.")
    Chest = None # Define Chest as None if it can't be imported

import level as LevelLoader
import ui                   # Ensure UI module is imported
import assets

# --- Game Setup ---
pygame.init()

# Dynamic Screen Setup
try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w; monitor_height = display_info.current_h
    initial_width = max(800, min(1600, monitor_width * 3 // 4))
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    SCREEN_WIDTH = initial_width; SCREEN_HEIGHT = initial_height
    fullscreen = False # Start windowed
    flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    # If you want to START fullscreen, set fullscreen=True and uncomment below
    # if fullscreen:
    #     flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
    #     SCREEN_WIDTH = monitor_width; SCREEN_HEIGHT = monitor_height
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
    print(f"Initial window: {SCREEN_WIDTH}x{SCREEN_HEIGHT} {'(Fullscreen)' if fullscreen else '(Windowed)'}")
except Exception as e:
    print(f"Error setting up display: {e}")
    pygame.quit(); sys.exit()

pygame.display.set_caption("Platformer Adventure")
clock = pygame.time.Clock()

# --- Debug Font ---
try: debug_font = pygame.font.Font(None, 20)
except Exception: debug_font = None; print("Warning: Debug font not loaded.")

# --- Load Level ---
current_map_loader = LevelLoader.load_map_cpu_extended

print("Loading level...")
try:
    platform_sprites, ladder_sprites, hazard_sprites, enemy_spawns_data, \
    player_spawn_pos, level_pixel_width, ground_level_y, ground_platform_height = \
        current_map_loader(initial_width, initial_height)
    print("Level loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR loading level: {e}")
    pygame.quit(); sys.exit()

# --- Sprite Groups ---
all_sprites = pygame.sprite.Group()
enemy_sprites = pygame.sprite.Group()
player_sprite_group = pygame.sprite.GroupSingle()
collectible_sprites = pygame.sprite.Group()

# --- Create Player ---
print("Initializing player...")
player = Player(player_spawn_pos[0], player_spawn_pos[1])
if not player._valid_init:
    print("CRITICAL: Player initialization failed. Check animation files. Exiting.")
    pygame.quit(); sys.exit()
all_sprites.add(player)
player_sprite_group.add(player)
print("Player initialized.")

# --- Create Enemies ---
enemy_list = []
print(f"\nAttempting to spawn {len(enemy_spawns_data)} enemies...")
for i, spawn_data in enumerate(enemy_spawns_data):
    try:
        spawn_pos = spawn_data['pos']
        patrol_area = spawn_data.get('patrol', None)
        print(f"Spawning enemy {i+1} at {spawn_pos} {'with patrol area' if patrol_area else ''}...")
        enemy = Enemy(spawn_pos[0], spawn_pos[1], patrol_area=patrol_area)
        if enemy._valid_init:
            print(f"Enemy {i+1} ({enemy.color_name}) initialized successfully.")
            all_sprites.add(enemy)
            enemy_sprites.add(enemy)
            enemy_list.append(enemy)
        else:
            print(f"ERROR: Failed to initialize enemy {i+1} (Check console for details).")
    except Exception as e:
        print(f"ERROR Spawning enemy {i+1} at {spawn_data.get('pos', 'Unknown Pos')}: {e}")
print(f"Finished spawning. Total enemies active: {len(enemy_list)}\n")

# --- Add Level Geometry Sprites to Drawing Group ---
all_sprites.add(platform_sprites)
all_sprites.add(ladder_sprites)
all_sprites.add(hazard_sprites)

# --- Function to Spawn Chest (Ensure Chest Class Exists) ---
def spawn_chest(platforms, collectibles, all_draw_sprites):
    """Finds a suitable platform and spawns a chest."""
    if Chest is None:
        print("Info: Chest class not available, skipping chest spawn.")
        return None

    print("Attempting to spawn chest...")
    suitable_platforms = [p for p in platforms if p.rect.width > 40 and p.rect.height > 0 and p.rect.top < ground_level_y - 5]
    if not suitable_platforms: suitable_platforms = [p for p in platforms if p.rect.width > 20 and p.rect.height > 0]

    if suitable_platforms:
        chosen_platform = random.choice(suitable_platforms)
        spawn_min_x = chosen_platform.rect.left + chosen_platform.rect.width * 0.3
        spawn_max_x = chosen_platform.rect.right - chosen_platform.rect.width * 0.3
        if spawn_min_x >= spawn_max_x:
             spawn_min_x = chosen_platform.rect.left + 10; spawn_max_x = chosen_platform.rect.right - 10
             chest_spawn_x = chosen_platform.rect.centerx if spawn_min_x >= spawn_max_x else random.uniform(spawn_min_x, spawn_max_x)
        else: chest_spawn_x = random.uniform(spawn_min_x, spawn_max_x)
        chest_spawn_y = chosen_platform.rect.top # Chest bottom rests on platform top

        try:
            # Ensure Chest class takes x, y for midbottom or adjust accordingly
            new_chest = Chest(chest_spawn_x, chest_spawn_y) # This might need adjustment based on Chest init
            if hasattr(new_chest, 'rect'): # Adjust position after creation if needed
                 new_chest.rect.midbottom = (chest_spawn_x, chest_spawn_y)

            if hasattr(new_chest,'_valid_init') and new_chest._valid_init: # Check if chest initialized correctly
                print(f"Chest spawned successfully at ({int(new_chest.rect.centerx)}, {int(new_chest.rect.bottom)}) on platform {chosen_platform.rect}.")
                all_draw_sprites.add(new_chest)
                collectibles.add(new_chest)
                return new_chest
            else:
                print("ERROR: Failed to initialize Chest object (Check Chest class/assets).")
                return None
        except Exception as e:
            print(f"ERROR Creating Chest object: {e}")
            return None
    else:
        print("Warning: No suitable platforms found to spawn chest on.")
        return None

# --- Initial Chest Spawn ---
current_chest = spawn_chest(platform_sprites, collectible_sprites, all_sprites)

# --- Camera Offset ---
camera_offset_x = 0; camera_offset_y = 0

# --- UI Constants ---
HEALTH_BAR_OFFSET_ABOVE = 8 # Pixels above sprite's effective 'head'

# --- Game Loop ---
running = True
print("Starting game loop...")
while running:
    # --- Timing ---
    dt_raw = clock.tick(C.FPS)
    dt_sec = 0 # Use 0 if physics are frame-dependent
    now = pygame.time.get_ticks()

    # --- Event Handling ---
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.VIDEORESIZE:
            if not screen.get_flags() & pygame.FULLSCREEN:
                try:
                    new_w = max(320, event.w); new_h = max(240, event.h)
                    SCREEN_WIDTH = new_w; SCREEN_HEIGHT = new_h
                    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE | pygame.DOUBLEBUF)
                    print(f"Resized to: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
                except pygame.error as e:
                    print(f"Error resizing window: {e}")
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            # <<< --- MODIFIED 'F' KEY LOGIC --- >>>
            if event.key == pygame.K_f: # Heal Player to Full
                 # Check if player exists and has the heal method
                 if player and hasattr(player, 'heal_to_full') and callable(player.heal_to_full):
                     if not player.is_dead:
                          print("Debug: Healing Player to Full (F pressed)")
                          player.heal_to_full() # Call the player's heal method
                 else:
                     print("Warning: Player object or heal_to_full method not found.")
            # <<< --- END OF MODIFIED 'F' KEY LOGIC --- >>>

            # Debug Keys
            if event.key == pygame.K_h: # Damage Player
                 if not player.is_dead:
                      print("Debug: Damaging player (-25 HP)")
                      player.take_damage(25)
            if event.key == pygame.K_p: # Kill Player
                 if not player.is_dead:
                      print("Debug: Killing player")
                      player.take_damage(player.max_health * 2)
            # Reset Key (R)
            if event.key == pygame.K_r:
                 print("\n--- Resetting Game State (R pressed) ---")
                 # Reset Player
                 print("Resetting Player...")
                 player.pos = pygame.math.Vector2(player_spawn_pos[0], player_spawn_pos[1])
                 player.vel = pygame.math.Vector2(0, 0); player.acc = pygame.math.Vector2(0, C.PLAYER_GRAVITY); player.current_health = player.max_health
                 player.is_dead = False; player.is_taking_hit = False; player.is_attacking = False; player.is_crouching = False; player.is_dashing = False; player.is_rolling = False; player.is_sliding = False; player.on_ladder = False; player.can_grab_ladder = False; player.touching_wall = 0; player.can_wall_jump = False; player.wall_climb_timer = 0
                 player.rect.midbottom = (round(player.pos.x), round(player.pos.y)); player.set_state('idle')
                 print("Player reset.")
                 # Reset Enemies
                 print("Resetting Enemies...")
                 for enemy in enemy_list: enemy.reset()
                 print(f"{len(enemy_list)} Enemies reset.")
                 # Respawn Chest
                 print("Removing old chest...")
                 if current_chest and current_chest.alive(): current_chest.kill()
                 print("Respawning new chest...")
                 current_chest = spawn_chest(platform_sprites, collectible_sprites, all_sprites)
                 print("----------------------------------------\n")

    # --- Handle Player Input ---
    keys = pygame.key.get_pressed()
    player.handle_input(keys, events)

    # --- Update Game State ---
    try:
        player.update(dt_sec, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites)
    except Exception as e:
        print(f"CRITICAL ERROR during player update: {e}"); pygame.event.post(pygame.event.Event(pygame.QUIT))
    try:
        enemy_sprites.update(dt_sec, player, platform_sprites, hazard_sprites)
    except Exception as e:
        print(f"CRITICAL ERROR during enemy update: {e}"); pygame.event.post(pygame.event.Event(pygame.QUIT))
    try:
        collectible_sprites.update(dt_sec)
    except Exception as e:
        print(f"ERROR during collectible update: {e}")

    # --- Check Player-Chest Collision ---
    if Chest is not None and not player.is_dead and current_chest and current_chest.alive():
        if pygame.sprite.collide_rect(player, current_chest):
             print("Player collected chest!")
             current_chest.collect(player)
             current_chest = None # Will be respawned on Reset

    # --- Camera Update ---
    target_camera_x = player.rect.centerx - SCREEN_WIDTH // 2
    min_cam_x = 0; max_cam_x = max(0, level_pixel_width - SCREEN_WIDTH)
    camera_offset_x = max(min_cam_x, min(target_camera_x, max_cam_x))

    world_view_top_target = ground_level_y - SCREEN_HEIGHT * (2/3)
    min_cam_y = 0; max_cam_y = max(0, (ground_level_y + ground_platform_height) - SCREEN_HEIGHT)
    clamped_target_y = max(min_cam_y, min(world_view_top_target, max_cam_y))
    lerp_factor_y = 0.08; lerp_speed = 1 - math.exp(-lerp_factor_y * dt_raw * 0.06)
    camera_offset_y += (clamped_target_y - camera_offset_y) * lerp_speed
    camera_offset_y = max(min_cam_y, min(camera_offset_y, max_cam_y)) # Final clamp

    # --- Drawing ---
    screen.fill(C.LIGHT_BLUE)

    screen_bounds = screen.get_rect().inflate(100, 100)
    for sprite in all_sprites:
        if hasattr(sprite, 'image') and hasattr(sprite, 'rect'):
            try:
                screen_x = sprite.rect.left - int(camera_offset_x)
                screen_y = sprite.rect.top - int(camera_offset_y)
                sprite_screen_rect = pygame.Rect(screen_x, screen_y, sprite.rect.width, sprite.rect.height)
                if not screen_bounds.colliderect(sprite_screen_rect): continue
                screen.blit(sprite.image, (screen_x, screen_y))

                # --- Health Bar Drawing Logic ---
                if hasattr(sprite, 'current_health') and hasattr(sprite, 'max_health') and \
                   hasattr(sprite, 'is_dead') and not sprite.is_dead and sprite.current_health < sprite.max_health:
                    bar_w = C.HEALTH_BAR_WIDTH; bar_h = C.HEALTH_BAR_HEIGHT
                    bar_x = screen_x + (sprite.rect.width / 2) - (bar_w / 2)
                    ref_height = sprite.standard_height if hasattr(sprite, 'standard_height') else sprite.rect.height
                    screen_visual_bottom_y = screen_y + sprite.rect.height
                    bar_y = screen_visual_bottom_y - ref_height - bar_h - HEALTH_BAR_OFFSET_ABOVE
                    bar_y = max(0, bar_y)
                    ui.draw_health_bar(screen, bar_x, bar_y, bar_w, bar_h, sprite.current_health, sprite.max_health)

            except AttributeError as e: pass
            except Exception as e: print(f"Error drawing sprite {sprite}: {e}")

    # --- Draw Debug Info (Optional) ---
    # if debug_font:
    #     try:
    #         debug_texts = []
    #         p_state = player.state if hasattr(player,'state') else 'N/A'; p_hp = f"{player.current_health}/{player.max_health}" if hasattr(player,'current_health') else 'N/A'; p_pos = f"({int(player.pos.x)}, {int(player.pos.y)})" if hasattr(player,'pos') else 'N/A'; p_vel = f"({player.vel.x:.1f}, {player.vel.y:.1f})" if hasattr(player,'vel') else 'N/A'; p_ground = f"G:{player.on_ground}" if hasattr(player,'on_ground') else ''; p_hit = f"Hit:{player.is_taking_hit}" if hasattr(player,'is_taking_hit') else ''
    #         debug_texts.append(f"P: {p_state} HP:{p_hp} {p_hit}"); debug_texts.append(f" Pos:{p_pos} Vel:{p_vel} {p_ground}")
    #         for i, enemy in enumerate(enemy_list):
    #             if i >= 2: break;
    #             if not enemy.alive(): continue
    #             e_state = enemy.state if hasattr(enemy,'state') else 'N/A'; e_ai = f"({enemy.ai_state})" if hasattr(enemy,'ai_state') else ''; e_hp = f"{enemy.current_health}/{enemy.max_health}" if hasattr(enemy,'current_health') else 'N/A'; e_hit = f"Hit:{enemy.is_taking_hit}" if hasattr(enemy,'is_taking_hit') else ''
    #             try: dist = math.hypot(player.pos.x - enemy.pos.x, player.pos.y - enemy.pos.y)
    #             except AttributeError: dist = -1
    #             debug_texts.append(f" E{i+1}({enemy.color_name}):{e_state}{e_ai} HP:{e_hp} D:{dist:.0f} {e_hit}")
    #         cam_pos = f"Cam:({int(camera_offset_x)}, {int(camera_offset_y)})"; sprites_count = f"Sprites:{len(all_sprites)}"; chest_status = f"Chest:{'Active' if current_chest and current_chest.alive() else 'None'}"; fps = f"FPS: {clock.get_fps():.1f}"
    #         debug_texts.append(f"{cam_pos} {sprites_count} {chest_status} {fps}")
    #         y_offset = 5
    #         for text in debug_texts:
    #             if not text: continue
    #             text_surface = debug_font.render(text, True, C.BLACK)
    #             text_bg = pygame.Surface((text_surface.get_width() + 4, text_surface.get_height() + 2), pygame.SRCALPHA); text_bg.fill((211, 211, 211, 180))
    #             text_bg.blit(text_surface, (2, 1)); screen.blit(text_bg, (5, y_offset)); y_offset += text_bg.get_height() + 1
    #     except Exception as e: print(f"Error drawing debug info: {e}")

    pygame.display.flip()

# --- Cleanup ---
print("Exiting game.")
pygame.quit()
sys.exit()
