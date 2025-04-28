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
import random # <--- Import random

# Import modules
import constants as C
from player import Player
from enemy import Enemy
from tiles import Platform, Ladder, Lava # Import Lava if needed for checks here
from items import Chest # <--- Import Chest
import level as LevelLoader
import ui
import assets

# --- Game Setup ---
pygame.init()

# Dynamic Screen Setup
try:
    display_info = pygame.display.Info()
    monitor_width = display_info.current_w; monitor_height = display_info.current_h
    # Adjust initial size calculation if needed
    initial_width = max(800, min(1600, monitor_width * 3 // 4)); # Start larger but not huge
    initial_height = max(600, min(900, monitor_height * 3 // 4))
    SCREEN_WIDTH = initial_width; SCREEN_HEIGHT = initial_height
    fullscreen = False # Start windowed
    flags = pygame.RESIZABLE | pygame.DOUBLEBUF
    if fullscreen:
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
        SCREEN_WIDTH = monitor_width; SCREEN_HEIGHT = monitor_height
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
    print(f"Initial window: {SCREEN_WIDTH}x{SCREEN_HEIGHT} {'(Fullscreen)' if fullscreen else '(Windowed)'}")
except Exception as e:
    print(f"Error setting up display: {e}")
    pygame.quit(); sys.exit()

pygame.display.set_caption("Platformer Adventure") # Changed caption
clock = pygame.time.Clock()

# --- Debug Font ---
try: debug_font = pygame.font.Font(None, 20) # Smaller debug font
except Exception: debug_font = None; print("Warning: Debug font not loaded.")

# --- Load Level ---
# Choose which map to load
# current_map_loader = LevelLoader.load_map_original
# current_map_loader = LevelLoader.load_map_lava
current_map_loader = LevelLoader.load_map_cpu_extended # Using the map with enemies/lava

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
all_sprites = pygame.sprite.Group()           # For drawing all sprites
enemy_sprites = pygame.sprite.Group()         # For enemy-specific logic/collisions
player_sprite_group = pygame.sprite.GroupSingle() # For easy player reference in collisions
collectible_sprites = pygame.sprite.Group()   # For items like chests

# --- Create Player ---
print("Initializing player...")
player = Player(player_spawn_pos[0], player_spawn_pos[1])
if not player._valid_init:
    print("CRITICAL: Player initialization failed. Check 'player1' animation files. Exiting.")
    pygame.quit(); sys.exit()
all_sprites.add(player)
player_sprite_group.add(player)
print("Player initialized.")

# --- Create Enemies ---
enemy_list = [] # Keep a list for potential individual access later
print(f"\nAttempting to spawn {len(enemy_spawns_data)} enemies...")
for i, spawn_data in enumerate(enemy_spawns_data):
    try:
        spawn_pos = spawn_data['pos']
        patrol_area = spawn_data.get('patrol', None) # Safely get patrol area
        print(f"Spawning enemy {i+1} at {spawn_pos} {'with patrol area' if patrol_area else ''}...")
        enemy = Enemy(spawn_pos[0], spawn_pos[1], patrol_area=patrol_area)
        if enemy._valid_init:
            print(f"Enemy {i+1} ({enemy.color_name}) initialized successfully.")
            all_sprites.add(enemy)
            enemy_sprites.add(enemy)
            enemy_list.append(enemy)
        else:
            # Error message already printed in Enemy.__init__
            print(f"ERROR: Failed to initialize enemy {i+1} at {spawn_pos}.")
    except Exception as e:
        print(f"ERROR Spawning enemy {i+1} at {spawn_data.get('pos', 'Unknown Pos')}: {e}")
print(f"Finished spawning. Total enemies active: {len(enemy_list)}\n")

# --- Add Level Geometry Sprites to Drawing Group ---
# Make sure they are added *after* potential characters for correct draw order if needed later
all_sprites.add(platform_sprites)
all_sprites.add(ladder_sprites)
all_sprites.add(hazard_sprites)

# --- Function to Spawn Chest ---
def spawn_chest(platforms, collectibles, all_draw_sprites):
    """Finds a suitable platform and spawns a chest."""
    print("Attempting to spawn chest...")
    # Filter platforms: avoid very narrow or short platforms
    # Also ensure platform has a positive height (important!)
    suitable_platforms = [
        p for p in platforms
        if p.rect.width > 40 and p.rect.height > 0 and p.rect.top < ground_level_y - 5 # Ensure it's not part of the absolute ground
    ]

    if not suitable_platforms: # Fallback: use any platform if no ideal ones found
         suitable_platforms = [p for p in platforms if p.rect.width > 20 and p.rect.height > 0]

    if suitable_platforms:
        chosen_platform = random.choice(suitable_platforms)
        # Spawn chest roughly in the horizontal middle third of the platform's top surface
        spawn_min_x = chosen_platform.rect.left + chosen_platform.rect.width / 3
        spawn_max_x = chosen_platform.rect.right - chosen_platform.rect.width / 3
        # Ensure min is less than max (for very narrow platforms after filtering)
        if spawn_min_x >= spawn_max_x:
             spawn_min_x = chosen_platform.rect.left + 10
             spawn_max_x = chosen_platform.rect.right - 10

        chest_spawn_x = random.uniform(spawn_min_x, spawn_max_x)
        # Place bottom of chest exactly on top of platform
        chest_spawn_y = chosen_platform.rect.top

        new_chest = Chest(chest_spawn_x, chest_spawn_y)
        if new_chest._valid_init:
            print(f"Chest spawned successfully on platform at ({chosen_platform.rect.x}, {chosen_platform.rect.y}) -> Chest pos ({new_chest.rect.centerx}, {new_chest.rect.centery})")
            all_draw_sprites.add(new_chest)
            collectibles.add(new_chest)
            return new_chest # Return the spawned chest if needed
        else:
            print("ERROR: Failed to initialize Chest object after loading GIF.")
            return None
    else:
        print("Warning: No suitable platforms found to spawn chest on.")
        return None

# --- Initial Chest Spawn ---
current_chest = spawn_chest(platform_sprites, collectible_sprites, all_sprites)

# --- Camera Offset ---
camera_offset_x = 0; camera_offset_y = 0

# --- Game Loop ---
running = True
print("Starting game loop...")
while running:
    # --- Timing ---
    dt_raw = clock.tick(C.FPS) # Get time elapsed since last frame in milliseconds
    dt = dt_raw / 1000.0      # Convert delta time to seconds (useful for physics)
    now = pygame.time.get_ticks() # Get current time in milliseconds

    # --- Event Handling ---
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.VIDEORESIZE:
            # Handle window resizing if not fullscreen
            if not screen.get_flags() & pygame.FULLSCREEN:
                try:
                    # Basic sanity check on resize values
                    new_w = max(320, event.w); new_h = max(240, event.h)
                    SCREEN_WIDTH = new_w; SCREEN_HEIGHT = new_h
                    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE | pygame.DOUBLEBUF)
                    print(f"Resized to: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
                except pygame.error as e:
                    print(f"Error resizing window: {e}") # Catch potential display errors
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            # Debug Keys
            if event.key == pygame.K_h: # Damage player
                 if not player.is_dead:
                      print("Debug: Damaging player (-25 HP)")
                      player.take_damage(25)
            if event.key == pygame.K_p: # Kill player
                 if not player.is_dead:
                      print("Debug: Killing player")
                      player.take_damage(player.max_health * 2) # Overkill
            if event.key == pygame.K_f: # Heal Player (Full)
                 if not player.is_dead:
                      print("Debug: Healing Player to Full")
                      player.heal_to_full()

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

                 # Remove existing chest (if any) and respawn a new one
                 print("Removing old chest...")
                 if current_chest and current_chest.alive(): # Check if chest exists and is in groups
                     current_chest.kill()
                 print("Respawning new chest...")
                 current_chest = spawn_chest(platform_sprites, collectible_sprites, all_sprites)
                 print("----------------------------------------\n")


    # --- Handle Player Input (Continuous) ---
    # Pass keys state and discrete events list to player input handler
    keys = pygame.key.get_pressed()
    player.handle_input(keys, events) # Pass events for single-press actions

    # --- Update Game State ---
    # Update Player (Physics, Collisions, State Changes)
    try:
        player.update(dt, platform_sprites, ladder_sprites, hazard_sprites, enemy_sprites)
    except Exception as e:
        print(f"CRITICAL ERROR during player update: {e}")
        running = False # Stop game on critical error

    # Update Enemies (AI, Physics, Collisions)
    try:
        # Pass dt, player ref, platforms, hazards
        enemy_sprites.update(dt, player, platform_sprites, hazard_sprites)
    except Exception as e:
        print(f"CRITICAL ERROR during enemy update: {e}")
        running = False

    # Update Collectibles (e.g., Chest animation)
    try:
        collectible_sprites.update(dt) # Pass dt for potential animation timing
    except Exception as e:
        print(f"ERROR during collectible update: {e}")
        # Non-critical, maybe just log it


    # --- Check Player-Chest Collision ---
    # Perform this check *after* the player's position has been updated for the frame
    if not player.is_dead and current_chest and current_chest.alive(): # Only check if player alive and chest exists
        # Use spritecollide. The 'True' argument removes the chest from groups upon collision.
        collided_chests = pygame.sprite.spritecollide(player, collectible_sprites, True) # Group check is efficient
        for chest_collided in collided_chests:
            # Ensure it's the correct type (future-proofing if more items added)
             if isinstance(chest_collided, Chest):
                  chest_collided.collect(player) # Trigger the chest's collection logic
                  current_chest = None # Mark that the chest is gone


    # --- Camera Update ---
    # Simple camera follows player horizontally, keeps ground level near bottom vertically
    # Calculate target X based on player position and screen center
    target_camera_x = player.rect.centerx - SCREEN_WIDTH // 2
    # Clamp camera X to level boundaries
    min_cam_x = 0
    max_cam_x = max(0, level_pixel_width - SCREEN_WIDTH) # Ensure max_cam_x is not negative
    camera_offset_x = max(min_cam_x, min(target_camera_x, max_cam_x))

    # Calculate target Y to keep the reference ground level near the bottom of the screen
    # world_view_bottom_y is the Y coordinate in the game world that should be at the screen bottom
    world_view_bottom_y = ground_level_y + ground_platform_height # Use ground level from map data
    camera_offset_y = world_view_bottom_y - SCREEN_HEIGHT # Set camera Y offset

    # Optional: Smooth camera movement (Lerp)
    # lerp_factor = 0.1 # Adjust for desired smoothness (0=no move, 1=instant)
    # camera_offset_x += (target_camera_x - camera_offset_x) * lerp_factor
    # camera_offset_y += (target_camera_y - camera_offset_y) * lerp_factor # Need target_camera_y if using vertical follow
    # camera_offset_x = max(min_cam_x, min(camera_offset_x, max_cam_x)) # Re-clamp after lerp


    # --- Drawing ---
    # Fill background
    screen.fill(C.LIGHT_BLUE)

    # Draw all sprites adjusted by camera offset
    # Sorting by Y can create pseudo-depth but might not be necessary/desired
    # sorted_sprites = sorted(all_sprites, key=lambda sprite: sprite.rect.centery)
    # for sprite in sorted_sprites:
    for sprite in all_sprites:
        if hasattr(sprite, 'image') and hasattr(sprite, 'rect'):
            try:
                # Calculate screen position based on world position and camera offset
                screen_x = sprite.rect.left - int(camera_offset_x)
                screen_y = sprite.rect.top - int(camera_offset_y)

                # Basic Culling: Only blit if sprite is potentially visible on screen
                sprite_screen_rect = pygame.Rect(screen_x, screen_y, sprite.rect.width, sprite.rect.height)
                screen_bounds = screen.get_rect().inflate(50, 50) # Add padding for safety
                if screen_bounds.colliderect(sprite_screen_rect):
                     screen.blit(sprite.image, (screen_x, screen_y))

                # Draw Health Bars for Player and Enemies (only if alive)
                if hasattr(sprite, 'current_health') and hasattr(sprite, 'max_health') and \
                   hasattr(sprite, 'is_dead') and not sprite.is_dead and sprite.current_health < sprite.max_health: # Only draw if not full HP? Optional.
                    # Calculate bar position relative to sprite's *screen* position
                    bar_w = C.HEALTH_BAR_WIDTH; bar_h = C.HEALTH_BAR_HEIGHT
                    # Center bar horizontally above sprite
                    bar_x = screen_x + (sprite.rect.width / 2) - (bar_w / 2)

                    # Get reference height (idle frame height or rect height)
                    ref_height = sprite.standard_height if hasattr(sprite, 'standard_height') else sprite.rect.height
                    # Position bar above the sprite's visual top
                    bar_y = screen_y - bar_h - 5 # pixels above the sprite's top edge

                    # Ensure bar stays within screen bounds (simple top clamp)
                    bar_y = max(0, bar_y)

                    ui.draw_health_bar(screen, bar_x, bar_y, bar_w, bar_h, sprite.current_health, sprite.max_health)

                # Optional: Draw Debug Rects
                # if isinstance(sprite, Player) or isinstance(sprite, Enemy):
                #    pygame.draw.rect(screen, (255, 0, 0), sprite_screen_rect, 1)
                # if isinstance(sprite, Player) and sprite.is_attacking:
                #    attack_box_screen = sprite.attack_hitbox.move(-int(camera_offset_x), -int(camera_offset_y))
                #    pygame.draw.rect(screen, (0, 255, 255), attack_box_screen, 1)

            except AttributeError as e:
                 print(f"Error drawing sprite {sprite}: Missing attribute {e}")
            except Exception as e:
                 print(f"Error drawing sprite {sprite}: {e}")


    # --- Draw Debug Info (Optional) ---
    # if debug_font:
    #     try:
    #         # Consolidate debug text generation
    #         debug_texts = []
    #         # Player Info
    #         p_state = player.state if hasattr(player,'state') else 'N/A'
    #         p_hp = f"{player.current_health}/{player.max_health}" if hasattr(player,'current_health') else 'N/A'
    #         p_pos = f"({int(player.pos.x)}, {int(player.pos.y)})" if hasattr(player,'pos') else 'N/A'
    #         p_vel = f"({player.vel.x:.1f}, {player.vel.y:.1f})" if hasattr(player,'vel') else 'N/A'
    #         p_ground = f"G:{player.on_ground}" if hasattr(player,'on_ground') else ''
    #         p_ladder = f"L:{player.on_ladder}({player.can_grab_ladder})" if hasattr(player,'on_ladder') else ''
    #         p_wall = f"W:{player.touching_wall}" if hasattr(player,'touching_wall') else ''
    #         p_hit = f"Hit:{player.is_taking_hit}({now - player.hit_timer if player.is_taking_hit else '-'})" if hasattr(player,'is_taking_hit') else ''

    #         debug_texts.append(f"P: {p_state} HP:{p_hp} {p_hit}")
    #         debug_texts.append(f" Pos:{p_pos} Vel:{p_vel} {p_ground} {p_ladder} {p_wall}")

    #         # Enemy Info (Show first few)
    #         for i, enemy in enumerate(enemy_list):
    #             if i >= 2: break # Limit displayed enemies
    #             if not enemy.alive(): continue # Skip dead/killed enemies
    #             e_state = enemy.state if hasattr(enemy,'state') else 'N/A'
    #             e_ai = f"({enemy.ai_state})" if hasattr(enemy,'ai_state') else ''
    #             e_hp = f"{enemy.current_health}/{enemy.max_health}" if hasattr(enemy,'current_health') else 'N/A'
    #             e_hit = f"Hit:{enemy.is_taking_hit}" if hasattr(enemy,'is_taking_hit') else ''
    #             try: dist = math.hypot(player.pos.x - enemy.pos.x, player.pos.y - enemy.pos.y)
    #             except AttributeError: dist = -1
    #             debug_texts.append(f" E{i+1}({enemy.color_name}): {e_state}{e_ai} HP:{e_hp} D:{dist:.0f} {e_hit}")

    #         # General Info
    #         cam_pos = f"Cam:({int(camera_offset_x)}, {int(camera_offset_y)})"
    #         sprites_count = f"Sprites:{len(all_sprites)}"
    #         chest_status = f"Chest:{'Active' if current_chest and current_chest.alive() else 'None'}"
    #         fps = f"FPS: {clock.get_fps():.1f}"
    #         debug_texts.append(f"{cam_pos} {sprites_count} {chest_status} {fps}")


    #         # Render Debug Texts
    #         y_offset = 5
    #         for text in debug_texts:
    #             text_surface = debug_font.render(text, True, C.BLACK)
    #             # Add semi-transparent background for readability
    #             text_bg = pygame.Surface(text_surface.get_size(), pygame.SRCALPHA)
    #             text_bg.fill((211, 211, 211, 180)) # Light gray, semi-transparent
    #             text_bg.blit(text_surface, (0,0))
    #             screen.blit(text_bg, (5, y_offset))
    #             y_offset += 16 # Move down for next line
    #     except Exception as e:
    #         print(f"Error drawing debug info: {e}") # Catch errors here

    # --- Update Display ---
    pygame.display.flip() # Update the full screen

# --- Cleanup ---
print("Exiting game.")
pygame.quit()
sys.exit()