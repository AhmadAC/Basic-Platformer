# -*- coding: utf-8 -*-
"""
levels.py
Returns sprite groups for platforms, ladders, hazards, spawns, level width, ground Y, and ground height.
"""
# version 1.00000.2 (updated for boundary improvements and test block fix)
import pygame
import random
from tiles import Platform, Ladder, Lava # Import tile classes
from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT, LIGHT_BLUE

# Constants for fences (can be adjusted)
FENCE_WIDTH = 8
FENCE_HEIGHT = 15 # Short enough to jump over easily
FENCE_COLOR = GRAY # Match ground or use a distinct color like DARK_GRAY

# Define a very thick boundary to ensure no phasing
BOUNDARY_THICKNESS = TILE_SIZE * 2 # e.g., 80 pixels thick

def load_map_original(initial_width, initial_height):
    """ Creates the original level layout. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (100, initial_height - 41) 
    ground_width = initial_width * 2.5
    ground_y = initial_height - 40
    ground_height = 40 
    
    ground = Platform(0, ground_y, ground_width, ground_height, GRAY)
    platforms.add(ground)

    platforms.add(Platform(200, initial_height - 150, 250, 20, GRAY))
    platforms.add(Platform(450, initial_height - 300, 180, 20, GRAY))
    platforms.add(Platform(initial_width - 350, initial_height - 450, 200, 20, GRAY))
    platforms.add(Platform(initial_width + 150, initial_height - 250, 150, 20, GRAY))
    platforms.add(Platform(900, initial_height - 550, 100, 20, GRAY))

    platforms.add(Platform(-BOUNDARY_THICKNESS, -initial_height * 2, BOUNDARY_THICKNESS, initial_height * 4, GRAY))
    platforms.add(Platform(ground_width, -initial_height * 2, BOUNDARY_THICKNESS, initial_height * 4, GRAY))
    platforms.add(Platform(0, -initial_height * 2, ground_width, BOUNDARY_THICKNESS, GRAY))

    wall_mid = Platform(800, initial_height - 400, 30, 360, GRAY)
    platforms.add(wall_mid)

    ladder_width = 40; ladder_height = 250; ladder_x = initial_width - 500; ladder_y = ground_y - ladder_height
    ladders.add(Ladder(ladder_x, ladder_y, ladder_width, ladder_height))
    ladders.add(Ladder(350, initial_height - 250, ladder_width, 150))

    # Determine effective level height for camera (min_y will be very negative due to high ceiling)
    all_level_rects = [p.rect for p in platforms]
    min_y_coord = min(r.top for r in all_level_rects) if all_level_rects else -initial_height * 2
    max_y_coord = max(r.bottom for r in all_level_rects) if all_level_rects else ground_y + ground_height
    effective_level_height = max_y_coord - min_y_coord
    
    # The function now returns the effective level height and the y-coordinate of the highest platform (ceiling)
    # This might be useful for camera logic if you want the camera to be aware of the absolute top.
    # For now, the map functions return ground_y and ground_height, which refer to the main playable ground.
    # The camera will use level_width and the calculated effective_level_height.
    # The return signature is kept the same for compatibility with existing main.py:
    # platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height
    # `level_height` for the camera should be calculated in main.py based on all platforms.

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, ground_width, ground_y, ground_height

def load_map_lava(initial_width, initial_height):
    """ Creates a level with lava rivers/pools. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (80, initial_height - 150)
    level_width = initial_width * 2.8
    ground_level_y_ref = initial_height - 40 
    ground_platform_height = 0 

    platforms.add(Platform(50, initial_height - 120, 150, 20, DARK_GREEN))
    platforms.add(Platform(300, initial_height - 180, 120, 20, DARK_GREEN))
    platforms.add(Platform(500, initial_height - 150, 100, 20, DARK_GREEN))
    platforms.add(Platform(700, initial_height - 200, 130, 20, DARK_GREEN))
    platforms.add(Platform(900, initial_height - 250, 100, 20, DARK_GREEN))
    platforms.add(Platform(1100, initial_height - 400, 30, 400, GRAY))
    platforms.add(Platform(1250, initial_height - 350, 150, 20, DARK_GREEN))
    platforms.add(Platform(1450, initial_height - 500, 30, 500, GRAY)) 
    platforms.add(Platform(1600, initial_height - 480, 200, 20, DARK_GREEN))

    lava_y = ground_level_y_ref
    lava_height = 60 
    hazards.add(Lava(0, lava_y, 1100, lava_height, ORANGE_RED))
    hazards.add(Lava(1130, lava_y, 320, lava_height, ORANGE_RED))
    hazards.add(Lava(1550, lava_y, level_width - 1550, lava_height, ORANGE_RED))

    platforms.add(Platform(-BOUNDARY_THICKNESS, -initial_height * 2, BOUNDARY_THICKNESS, initial_height * 4, GRAY))
    platforms.add(Platform(level_width, -initial_height * 2, BOUNDARY_THICKNESS, initial_height * 4, GRAY))
    platforms.add(Platform(0, -initial_height * 2, level_width, BOUNDARY_THICKNESS, GRAY))
    
    # The return signature is kept the same for compatibility:
    # platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height
    # Note: ground_y and ground_height here refer to ground_level_y_ref and 0 respectively for this map.

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_level_y_ref, ground_platform_height


def load_map_cpu_extended(initial_width, initial_height):
    """ Creates a larger level with CPU enemy and DEEP LAVA WELLS with fences. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    player_spawn = (100, initial_height - 41 - FENCE_HEIGHT) 

    level_width = initial_width * 4.0 
    ground_y = initial_height - 40
    ground_height = 40
    lava_collision_height = LAVA_PATCH_HEIGHT

    gap_width = 120 
    segment_defs = [
        (0, 500), (500 + gap_width, 1100), (1100 + gap_width, 1700),
        (1700 + gap_width, 2300), (2300 + gap_width, level_width) 
    ]
    for start_x, end_x in segment_defs:
        width = end_x - start_x
        if width > 0: platforms.add(Platform(start_x, ground_y, width, ground_height, GRAY))

    for i in range(len(segment_defs) - 1):
        lava_start_x = segment_defs[i][1]; lava_end_x = segment_defs[i+1][0]
        lava_width = lava_end_x - lava_start_x
        if lava_width > 0:
            lava_collision_y = ground_y + 1 
            hazards.add(Lava(lava_start_x, lava_collision_y, lava_width, lava_collision_height, ORANGE_RED))
            fence_y = ground_y - FENCE_HEIGHT
            platforms.add(Platform(lava_start_x - FENCE_WIDTH, fence_y, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR))
            platforms.add(Platform(lava_end_x, fence_y, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR))

    platforms.add(Platform(300, initial_height - 160, 200, 20, DARK_GREEN))
    platforms.add(Platform(700, initial_height - 280, 150, 20, DARK_GREEN))
    platforms.add(Platform(1400, initial_height - 180, 250, 20, DARK_GREEN)) 
    platforms.add(Platform(2000, initial_height - 160, 150, 20, DARK_GREEN))
    platforms.add(Platform(level_width - 400, initial_height- 240, 180, 20, DARK_GREEN))

    boundary_y_start = -initial_height * 3 
    boundary_height_total = initial_height * 5 

    platforms.add(Platform(-BOUNDARY_THICKNESS, boundary_y_start, BOUNDARY_THICKNESS, boundary_height_total, GRAY))
    platforms.add(Platform(level_width, boundary_y_start, BOUNDARY_THICKNESS, boundary_height_total, GRAY))
    platforms.add(Platform(0, boundary_y_start, level_width, BOUNDARY_THICKNESS, GRAY)) 
    
    lowest_point_in_level = ground_y + lava_collision_height + 50 
    platforms.add(Platform(0, lowest_point_in_level, level_width, BOUNDARY_THICKNESS, GRAY))

    spawn_y_on_ground_fenced = ground_y - FENCE_HEIGHT - 1 
    enemy_spawns_data.append({'pos': (segment_defs[1][0] + 100, spawn_y_on_ground_fenced), 'patrol': None})
    enemy_spawns_data.append({'pos': (1450, initial_height - 181), 'patrol': None})
    patrol_rect = pygame.Rect(segment_defs[-1][0] + 50, ground_y - 100, 350, 100) 
    enemy_spawns_data.append({'pos': (segment_defs[-1][0] + 100, spawn_y_on_ground_fenced), 'patrol': patrol_rect})
    
    # The return signature is kept the same for compatibility:
    # platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height
    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, level_width, ground_y, ground_height

load_map_cpu = load_map_cpu_extended

if __name__ == '__main__':
    pygame.init()
    # Define screen_width and screen_height for the test environment
    screen_width_test = 800  # Use a distinct name for test variable
    screen_height_test = 600 # This acts as 'initial_height' for the test call
    screen = pygame.display.set_mode((screen_width_test, screen_height_test))
    pygame.display.set_caption("Level Boundary Test")

    # Test the map with extended boundaries
    platforms, ladders, hazards, enemy_spawns, player_spawn_pos, level_w, ground_y_pos, ground_h_val = \
        load_map_cpu_extended(screen_width_test, screen_height_test) # Pass the defined screen dimensions

    all_draw_sprites = pygame.sprite.Group() 
    all_draw_sprites.add(platforms.sprites(), ladders.sprites()) # Use .sprites() to add individuals
    all_draw_sprites.add(hazards.sprites())

    class DummyPlayer(pygame.sprite.Sprite):
        def __init__(self, x, y):
            super().__init__()
            self.image = pygame.Surface((30,40))
            self.image.fill((0,255,0)) 
            self.rect = self.image.get_rect(midbottom=(x,y))
            self.vel = pygame.math.Vector2(0,0)
            self.on_ground_test = False 

        def update(self, plats):
            self.vel.y += 0.5 
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]: self.vel.x = -5
            elif keys[pygame.K_RIGHT]: self.vel.x = 5
            else: self.vel.x = 0
            if keys[pygame.K_UP] and self.on_ground_test: self.vel.y = -12

            self.rect.x += self.vel.x
            self.collision_test('x', plats)
            self.rect.y += self.vel.y
            self.on_ground_test = False 
            self.collision_test('y', plats)
        
        def collision_test(self, direction, plats):
            for p in pygame.sprite.spritecollide(self, plats, False):
                if direction == 'x':
                    if self.vel.x > 0: self.rect.right = p.rect.left
                    if self.vel.x < 0: self.rect.left = p.rect.right
                    self.vel.x = 0
                if direction == 'y':
                    if self.vel.y > 0: self.rect.bottom = p.rect.top; self.on_ground_test = True
                    if self.vel.y < 0: self.rect.top = p.rect.bottom
                    self.vel.y = 0
    
    test_player = DummyPlayer(player_spawn_pos[0], player_spawn_pos[1])
    all_draw_sprites.add(test_player)

    running = True
    camera_offset_x = 0 
    camera_offset_y = 0 
    clock = pygame.time.Clock()

    # Calculate effective level height for camera clamping in the test
    min_y_test = 0
    max_y_test = screen_height_test # Default to screen height
    if platforms:
        all_test_rects = [p.rect for p in platforms]
        min_y_test = min(r.top for r in all_test_rects)
        max_y_test = max(r.bottom for r in all_test_rects)
    effective_level_h_test = max_y_test - min_y_test


    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        test_player.update(platforms)

        camera_offset_x = -test_player.rect.centerx + screen_width_test // 2
        camera_offset_y = -test_player.rect.centery + screen_height_test // 2

        camera_offset_x = min(0, camera_offset_x)
        if level_w > screen_width_test:
            camera_offset_x = max(-(level_w - screen_width_test), camera_offset_x)
        else:
            camera_offset_x = 0
        
        camera_offset_y = min(0, camera_offset_y)
        # Use the calculated effective_level_h_test for vertical clamping in the test
        # The camera needs to know its own screen_height_test to clamp correctly.
        # The max negative offset is -(total_level_height - screen_height)
        if effective_level_h_test > screen_height_test:
             # The camera's top y is effectively min_y_test for the level content.
             # So, offset should not make min_y_test appear below 0 on screen.
             # And should not make max_y_test appear above screen_height_test.
             # camera_offset_y = max(-(max_y_test - screen_height_test - min_y_test), camera_offset_y) # This is tricky
             # Simpler: clamp based on the overall span
            camera_offset_y = max(-(effective_level_h_test - screen_height_test), camera_offset_y + min_y_test) - min_y_test

        else: # Level is shorter than screen
            camera_offset_y = 0 # Or center it: (screen_height_test - effective_level_h_test) / 2 - min_y_test
            # For simplicity, just fix at top if shorter.
            # A proper camera would handle centering levels smaller than the screen view.
            # The camera_offset_y should be such that the top of the level (min_y_test) is shown at y=0 on screen
            # if the level is shorter than the screen, or centered.
            # The current main camera code handles this better. This test block is simplified.

        screen.fill((135, 206, 235)) 

        for sprite in all_draw_sprites:
            # When applying camera offset, remember that platform coordinates are absolute world coordinates.
            # The camera_offset_y already includes the shift needed if min_y_test is negative.
            screen.blit(sprite.image, (sprite.rect.x + camera_offset_x, sprite.rect.y + camera_offset_y))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()