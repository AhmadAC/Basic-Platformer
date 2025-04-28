# -*- coding: utf-8 -*-
"""
Functions to create and load different level layouts.
Returns sprite groups for platforms, ladders, hazards, spawns, level width, ground Y, and ground height.
"""
import pygame
import random
from tiles import Platform, Ladder, Lava # Import tile classes
from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT

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
    platforms.add(Platform(550, initial_height - 300, 180, 20, GRAY))
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

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_level_y_ref, ground_platform_height


def load_map_cpu_extended(initial_width, initial_height):
    """ Creates a larger level with CPU enemy and DEEP LAVA WELLS. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (100, initial_height - 41) # Start on first ground segment

    level_width = initial_width * 4.0 # Make the level much wider

    # Ground Definition
    ground_y = initial_height - 40
    ground_height = 40
    lava_well_visual_depth = 200 # How far down the lava extends visually in the gap
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

    # --- Create Lava Wells in the Gaps ---
    for i in range(len(segment_defs) - 1):
        lava_start_x = segment_defs[i][1] # End X of the previous segment
        lava_end_x = segment_defs[i+1][0] # Start X of the next segment
        lava_width = lava_end_x - lava_start_x # Calculate the gap width

        if lava_width > 0:
            # Create the damaging lava rect (thin, at the top of the well)
            # Place its top slightly below ground surface for feet collision
            lava_collision_y = ground_y + 1
            hazards.add(Lava(lava_start_x, lava_collision_y, lava_width, lava_collision_height, ORANGE_RED))

            # Optional: Add a visual-only lava sprite below for the deep well effect
            # This one won't be added to 'hazards' group, just 'all_sprites' in main.py
            # visual_lava = Platform(lava_start_x, lava_collision_y + lava_collision_height, lava_width, lava_well_visual_depth - lava_collision_height, ORANGE_RED)
            # all_sprites.add(visual_lava) # Need access to all_sprites here, maybe return visual sprites separately?
            # For simplicity, let's just use the single damaging Lava rect for now.

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
    # Spawn near middle on ground segment 2
    enemy_spawns_data.append({'pos': (segment_defs[1][0] + 100, ground_y - 1), 'patrol': None})
    # Spawn on platform over gap
    enemy_spawns_data.append({'pos': (1450, initial_height - 181), 'patrol': None})
    # Spawn patrolling near end on ground segment
    patrol_rect = pygame.Rect(segment_defs[-1][0] + 50, ground_y - 100, 350, 100) # Area for patrol target selection
    enemy_spawns_data.append({'pos': (segment_defs[-1][0] + 100, ground_y - 1), 'patrol': patrol_rect})

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height

# -*- coding: utf-8 -*-
"""
Functions to create and load different level layouts.
Returns sprite groups for platforms, ladders, hazards, spawns, level width, ground Y, and ground height.
"""
import pygame
import random
from tiles import Platform, Ladder, Lava # Import tile classes
from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT

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
    platforms.add(Platform(550, initial_height - 300, 180, 20, GRAY))
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

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_level_y_ref, ground_platform_height


def load_map_cpu_extended(initial_width, initial_height):
    """ Creates a larger level with CPU enemy and DEEP LAVA WELLS. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (100, initial_height - 41) # Start on first ground segment

    level_width = initial_width * 4.0 # Make the level much wider

    # Ground Definition
    ground_y = initial_height - 40
    ground_height = 40
    lava_well_visual_depth = 200 # How far down the lava extends visually in the gap
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

    # --- Create Lava Wells in the Gaps ---
    for i in range(len(segment_defs) - 1):
        lava_start_x = segment_defs[i][1] # End X of the previous segment
        lava_end_x = segment_defs[i+1][0] # Start X of the next segment
        lava_width = lava_end_x - lava_start_x # Calculate the gap width

        if lava_width > 0:
            # Create the damaging lava rect (thin, at the top of the well)
            # Place its top slightly below ground surface for feet collision
            lava_collision_y = ground_y + 1
            hazards.add(Lava(lava_start_x, lava_collision_y, lava_width, lava_collision_height, ORANGE_RED))

            # Optional: Add a visual-only lava sprite below for the deep well effect
            # This one won't be added to 'hazards' group, just 'all_sprites' in main.py
            # visual_lava = Platform(lava_start_x, lava_collision_y + lava_collision_height, lava_width, lava_well_visual_depth - lava_collision_height, ORANGE_RED)
            # all_sprites.add(visual_lava) # Need access to all_sprites here, maybe return visual sprites separately?
            # For simplicity, let's just use the single damaging Lava rect for now.

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
    # Spawn near middle on ground segment 2
    enemy_spawns_data.append({'pos': (segment_defs[1][0] + 100, ground_y - 1), 'patrol': None})
    # Spawn on platform over gap
    enemy_spawns_data.append({'pos': (1450, initial_height - 181), 'patrol': None})
    # Spawn patrolling near end on ground segment
    patrol_rect = pygame.Rect(segment_defs[-1][0] + 50, ground_y - 100, 350, 100) # Area for patrol target selection
    enemy_spawns_data.append({'pos': (segment_defs[-1][0] + 100, ground_y - 1), 'patrol': patrol_rect})

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height

# Alias for easy switching in main.py
load_map_cpu = load_map_cpu_extended