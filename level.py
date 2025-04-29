# -*- coding: utf-8 -*-
"""
Functions to create and load different level layouts.
Returns sprite groups for platforms, ladders, hazards, spawns, level width, ground Y, and ground height.
"""
import pygame
import random
from tiles import Platform, Ladder, Lava # Import tile classes
from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT

# Constants for fences (can be adjusted)
FENCE_WIDTH = 8
FENCE_HEIGHT = 15 # Short enough to jump over easily
FENCE_COLOR = GRAY # Match ground or use a distinct color like DARK_GRAY


def load_map_original(initial_width, initial_height):
    """ Creates the original level layout. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = [] # List of dictionaries {'pos': (x,y), 'patrol': rect or None}
    player_spawn = (100, initial_height - 41)
    ground_width = initial_width * 2.5
    ground_y = initial_height - 40
    ground_height = 40
    ground = Platform(0, ground_y, ground_width, ground_height, GRAY)
    platforms.add(ground)

    # Platforms
    platforms.add(Platform(200, initial_height - 150, 250, 20, GRAY))
    platforms.add(Platform(450, initial_height - 300, 180, 20, GRAY))
    platforms.add(Platform(initial_width - 350, initial_height - 450, 200, 20, GRAY))
    platforms.add(Platform(initial_width + 150, initial_height - 250, 150, 20, GRAY))
    platforms.add(Platform(900, initial_height - 550, 100, 20, GRAY))

    # Walls
    wall_left = Platform(-20, -initial_height, 20, initial_height * 2 + ground_height, GRAY) # Extend up/down
    wall_right_level_end = Platform(ground_width, -initial_height, 20, initial_height * 2 + ground_height, GRAY) # Extend up/down
    wall_mid = Platform(800, initial_height - 400, 30, 360, GRAY)
    platforms.add(wall_left, wall_right_level_end, wall_mid)

    # Ladders
    ladder_width = 40; ladder_height = 250; ladder_x = initial_width - 500; ladder_y = ground_y - ladder_height
    ladders.add(Ladder(ladder_x, ladder_y, ladder_width, ladder_height))
    ladders.add(Ladder(350, initial_height - 250, ladder_width, 150))

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, ground_width, ground_y, ground_height

def load_map_lava(initial_width, initial_height):
    """ Creates a level with lava rivers/pools. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (80, initial_height - 150)
    level_width = initial_width * 2.8
    ground_level_y_ref = initial_height - 40 # Reference Y where lava sits
    ground_platform_height = 0 # No single ground platform

    # Platforms
    platforms.add(Platform(50, initial_height - 120, 150, 20, DARK_GREEN))
    platforms.add(Platform(300, initial_height - 180, 120, 20, DARK_GREEN))
    platforms.add(Platform(500, initial_height - 150, 100, 20, DARK_GREEN))
    platforms.add(Platform(700, initial_height - 200, 130, 20, DARK_GREEN))
    platforms.add(Platform(900, initial_height - 250, 100, 20, DARK_GREEN))
    platforms.add(Platform(1100, initial_height - 400, 30, 400, GRAY)) # Wall climb
    platforms.add(Platform(1250, initial_height - 350, 150, 20, DARK_GREEN))
    platforms.add(Platform(1450, initial_height - 500, 30, 500, GRAY)) # Wall climb
    platforms.add(Platform(1600, initial_height - 480, 200, 20, DARK_GREEN)) # Final

    # Lava Pools
    lava_y = ground_level_y_ref
    lava_height = 60 # Make visually deeper
    hazards.add(Lava(0, lava_y, 1100, lava_height, ORANGE_RED))
    hazards.add(Lava(1130, lava_y, 320, lava_height, ORANGE_RED))
    hazards.add(Lava(1550, lava_y, level_width - 1550, lava_height, ORANGE_RED))

    # Boundary walls
    platforms.add(Platform(-20, -initial_height, 20, initial_height * 2 + lava_height, GRAY))
    platforms.add(Platform(level_width, -initial_height, 20, initial_height * 2 + lava_height, GRAY))

    # TODO: Add fences for load_map_lava if desired, similar to load_map_cpu_extended below

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_level_y_ref, ground_platform_height


def load_map_cpu_extended(initial_width, initial_height):
    """ Creates a larger level with CPU enemy and DEEP LAVA WELLS with fences. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (100, initial_height - 41 - FENCE_HEIGHT) # Adjust spawn height for fence

    level_width = initial_width * 4.0 # Make the level much wider

    # Ground Definition
    ground_y = initial_height - 40
    ground_height = 40
    # lava_well_visual_depth = 200 # How far down the lava extends visually in the gap (unused for now)
    lava_collision_height = LAVA_PATCH_HEIGHT # Use constant for collision rect height

    # --- Create Ground Segments with Gaps ---
    gap_width = 120 # Width of the lava gaps
    # Define segments by their start and end X coordinates
    segment_defs = [
        (0, 500),               # Segment 1: Start=0, End=500
        (500 + gap_width, 1100), # Segment 2: Start=620, End=1100
        (1100 + gap_width, 1700),# Segment 3: Start=1220, End=1700
        (1700 + gap_width, 2300),# Segment 4: Start=1820, End=2300
        (2300 + gap_width, level_width) # Final Segment: Start=2420, End=level_width
    ]

    # Create platform sprites for ground segments
    for start_x, end_x in segment_defs:
        width = end_x - start_x
        if width > 0: # Ensure non-zero width
            platforms.add(Platform(start_x, ground_y, width, ground_height, GRAY))

    # --- Create Lava Wells AND FENCES in the Gaps ---
    for i in range(len(segment_defs) - 1):
        lava_start_x = segment_defs[i][1] # End X of the previous segment
        lava_end_x = segment_defs[i+1][0] # Start X of the next segment
        lava_width = lava_end_x - lava_start_x # Calculate the gap width

        if lava_width > 0:
            # Create the damaging lava rect (thin, at the top of the well)
            # Place its top slightly below ground surface for feet collision
            lava_collision_y = ground_y + 1
            hazards.add(Lava(lava_start_x, lava_collision_y, lava_width, lava_collision_height, ORANGE_RED))

            # --- Add Little Fences ---
            fence_y = ground_y - FENCE_HEIGHT # Place top of fence FENCE_HEIGHT pixels above ground Y

            # Fence before the gap (at the end of the previous ground segment)
            # Its right edge is at lava_start_x, so its left edge (x) is lava_start_x - FENCE_WIDTH
            platforms.add(Platform(lava_start_x - FENCE_WIDTH, fence_y, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR))

            # Fence after the gap (at the start of the next ground segment)
            # Its left edge is at lava_end_x
            platforms.add(Platform(lava_end_x, fence_y, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR))

            # Optional: Add a visual-only lava sprite below for the deep well effect
            # visual_lava = Platform(lava_start_x, lava_collision_y + lava_collision_height, lava_width, lava_well_visual_depth - lava_collision_height, ORANGE_RED)
            # Needs separate handling for drawing if not in 'platforms' or 'hazards'

    # --- Platforms above ground ---
    platforms.add(Platform(300, initial_height - 160, 200, 20, DARK_GREEN))
    platforms.add(Platform(700, initial_height - 280, 150, 20, DARK_GREEN))
    platforms.add(Platform(1400, initial_height - 180, 250, 20, DARK_GREEN)) # Over a gap
    platforms.add(Platform(2000, initial_height - 160, 150, 20, DARK_GREEN))
    platforms.add(Platform(level_width - 400, initial_height- 240, 180, 20, DARK_GREEN)) # Near end

    # --- Boundary Walls ---
    # Make walls very tall to prevent jumping over, start high above ground too
    wall_height = initial_height * 3 + ground_height
    wall_y = -initial_height * 2
    platforms.add(Platform(-20, wall_y, 20, wall_height, GRAY)) # Tall Left wall
    platforms.add(Platform(level_width, wall_y, 20, wall_height, GRAY)) # Tall Right wall

    # --- Enemy Spawns ---
    # Adjust spawn Y for fences if spawning near an edge
    spawn_y_on_ground = ground_y - 1 # Standard Y just above ground
    spawn_y_on_ground_fenced = ground_y - FENCE_HEIGHT - 1 # Y just above fence height

    # Spawn near middle on ground segment 2 (needs to clear fence if near edge)
    enemy_spawns_data.append({'pos': (segment_defs[1][0] + 100, spawn_y_on_ground_fenced), 'patrol': None})
    # Spawn on platform over gap (no fence here)
    enemy_spawns_data.append({'pos': (1450, initial_height - 181), 'patrol': None})
    # Spawn patrolling near end on ground segment (needs to clear fence if near edge)
    patrol_rect = pygame.Rect(segment_defs[-1][0] + 50, ground_y - 100, 350, 100) # Area for patrol target selection
    enemy_spawns_data.append({'pos': (segment_defs[-1][0] + 100, spawn_y_on_ground_fenced), 'patrol': patrol_rect})

    # Adjust player spawn Y slightly just in case it's near a fence edge initially
    # (The previous adjustment at the top should handle the general case)
    # player_spawn = (player_spawn[0], ground_y - FENCE_HEIGHT - 1) # Ensure player starts above fence level

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height

# Alias for easy switching in main.py
load_map_cpu = load_map_cpu_extended

# Example usage (if you were to run this file directly for testing)
if __name__ == '__main__':
    pygame.init()
    screen_width = 800
    screen_height = 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Level Test")

    # Test the map with fences
    platforms, ladders, hazards, enemy_spawns, player_spawn_pos, level_w, ground_y_pos, ground_h_val = load_map_cpu_extended(screen_width, screen_height)

    all_sprites = pygame.sprite.Group()
    all_sprites.add(platforms, ladders, hazards) # Add all created sprites

    # Basic game loop for visualization
    running = True
    camera_x = 0
    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                 if event.key == pygame.K_LEFT:
                     camera_x += 20
                 if event.key == pygame.K_RIGHT:
                     camera_x -= 20


        # Clear screen
        screen.fill((135, 206, 235)) # Light blue background

        # Draw everything (shifted by camera)
        for sprite in all_sprites:
            screen.blit(sprite.image, (sprite.rect.x + camera_x, sprite.rect.y))

        # Draw player spawn position marker
        pygame.draw.circle(screen, (0, 255, 0), (player_spawn_pos[0] + camera_x, player_spawn_pos[1]), 5)

        # Draw enemy spawn position markers
        for spawn_data in enemy_spawns:
            pygame.draw.circle(screen, (255, 0, 0), (spawn_data['pos'][0] + camera_x, spawn_data['pos'][1]), 5)
            if spawn_data['patrol']:
                 patrol_vis_rect = spawn_data['patrol'].move(camera_x, 0)
                 pygame.draw.rect(screen, (255, 255, 0), patrol_vis_rect, 1)


        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
