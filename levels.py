#################### START OF FILE: levels.py ####################

# levels.py
# -*- coding: utf-8 -*-
"""
levels.py
Returns sprite groups for platforms, ladders, hazards, spawns, level width,
and absolute min/max Y coordinates for the entire level.
"""
# version 1.0.0.9 (Added platform_type tags to all platforms)
import pygame
import random
from tiles import Platform, Ladder, Lava # Import tile classes
from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT, BLACK
import constants as C # Already imported, but C alias is good practice

FENCE_WIDTH = 8
FENCE_HEIGHT = 15
FENCE_COLOR = GRAY

def _add_map_boundary_walls(platforms_group, map_total_width, all_content_sprites_list,
                            initial_screen_height_fallback, extra_sky_clearance=0):
    """
    Calculates content extents and adds TILE_SIZE thick boundary walls.
    map_total_width is the outer width including walls.
    extra_sky_clearance pushes the ceiling collision object higher.
    Returns min_y_overall, max_y_overall (absolute top/bottom of level including walls).
    """
    if not all_content_sprites_list:
        print("Warning: _add_map_boundary_walls called with empty content list. Using fallback extents.")
        min_y_content = 0 - TILE_SIZE * 5
        max_y_content = initial_screen_height_fallback
    else:
        all_rects = [s.rect for s in all_content_sprites_list if hasattr(s, 'rect')]
        if not all_rects:
            min_y_content = 0 - TILE_SIZE * 5
            max_y_content = initial_screen_height_fallback
        else:
            min_y_content = min(r.top for r in all_rects)
            max_y_content = max(r.bottom for r in all_rects)

    ceiling_object_top_y = min_y_content - TILE_SIZE - extra_sky_clearance
    level_min_y_abs = ceiling_object_top_y
    level_max_y_abs = max_y_content + TILE_SIZE
    boundary_box_height = level_max_y_abs - level_min_y_abs

    platforms_group.add(Platform(0, ceiling_object_top_y, map_total_width, TILE_SIZE, GRAY, platform_type="boundary"))
    platforms_group.add(Platform(0, max_y_content, map_total_width, TILE_SIZE, GRAY, platform_type="boundary"))
    platforms_group.add(Platform(0, level_min_y_abs, TILE_SIZE, boundary_box_height, GRAY, platform_type="boundary"))
    platforms_group.add(Platform(map_total_width - TILE_SIZE, level_min_y_abs, TILE_SIZE, boundary_box_height, GRAY, platform_type="boundary"))

    return level_min_y_abs, level_max_y_abs


def load_map_original(initial_width, initial_height):
    """ Creates the original level layout with boundary walls and colored ledges. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = [] # This would contain dicts for enemy spawn info

    # Define level dimensions and player spawn based on initial screen size
    map_total_width = initial_width * 2.5 # Example: level is 2.5 times screen width
    # Player spawn point (ensure it's on the ground or a starting platform)
    player_spawn = (TILE_SIZE + 60, initial_height - TILE_SIZE - TILE_SIZE - 1) # x, y (midbottom)
    main_ground_y_ref = initial_height - TILE_SIZE # Y coordinate of the top of the main ground
    main_ground_segment_height_ref = TILE_SIZE


    # Ground Platform
    ground = Platform(TILE_SIZE, main_ground_y_ref, map_total_width - 2 * TILE_SIZE, main_ground_segment_height_ref, GRAY, platform_type="ground")
    platforms.add(ground)

    # Example Ledges (x, y, width, height, color, type)
    # Note: y is top of platform
    platforms.add(Platform(TILE_SIZE + 160, initial_height - 150, 250, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 410, initial_height - 300, 180, 20, DARK_GREEN, platform_type="ledge"))
    # Ensure platforms are within map width
    platforms.add(Platform(min(map_total_width - TILE_SIZE - 200, TILE_SIZE + initial_width - 350), initial_height - 450, 200, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(min(map_total_width - TILE_SIZE - 150, TILE_SIZE + initial_width + 150), initial_height - 250, 150, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 860, initial_height - 550, 100, 20, DARK_GREEN, platform_type="ledge")) # Higher platform

    # Example Structural Wall
    wall_mid_x = TILE_SIZE + 760
    wall_mid_width = 30
    # Ensure wall doesn't go past map edge
    if wall_mid_x + wall_mid_width > map_total_width - TILE_SIZE:
        wall_mid_width = max(1, (map_total_width - TILE_SIZE) - wall_mid_x) # Adjust width if too long
    platforms.add(Platform(wall_mid_x, initial_height - 400, wall_mid_width, 360, GRAY, platform_type="wall"))


    # Example Ladders
    ladder_width = 40
    ladder_height_main = 250 # Example height
    ladders.add(Ladder(min(map_total_width - TILE_SIZE - ladder_width, TILE_SIZE + initial_width - 500),
                       main_ground_y_ref - ladder_height_main, ladder_width, ladder_height_main))
    ladders.add(Ladder(TILE_SIZE + 310, initial_height - 250, ladder_width, 150))


    # Collect all sprites that define the level's content boundaries
    all_content_sprites = list(platforms.sprites()) + list(ladders.sprites()) + list(hazards.sprites())
    # Add boundary walls based on content extents
    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls(platforms, map_total_width, all_content_sprites, initial_height, extra_sky_clearance=TILE_SIZE*5)


    # Return all relevant data for the game to use
    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, \
           map_total_width, level_min_y_abs, level_max_y_abs, \
           main_ground_y_ref, main_ground_segment_height_ref # Return ground references


def load_map_lava(initial_width, initial_height):
    """ Creates a level with lava, boundary walls, and colored ledges. """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    map_total_width = initial_width * 2.8
    player_spawn_x = TILE_SIZE + 30
    player_spawn_y = initial_height - 120 - TILE_SIZE # On the first platform
    player_spawn = (player_spawn_x, player_spawn_y)
    main_ground_y_ref = initial_height - TILE_SIZE # Top of the lava/ground level

    # Ledges
    platforms.add(Platform(TILE_SIZE, initial_height - 120, 150, 20, DARK_GREEN, platform_type="ledge")) # Start platform
    platforms.add(Platform(TILE_SIZE + 260, initial_height - 180, 120, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 460, initial_height - 150, 100, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 660, initial_height - 200, 130, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 860, initial_height - 250, 100, 20, DARK_GREEN, platform_type="ledge"))
    platforms.add(Platform(TILE_SIZE + 1210, initial_height - 350, 150, 20, DARK_GREEN, platform_type="ledge")) # Higher platform
    platforms.add(Platform(TILE_SIZE + 1560, initial_height - 480, 200, 20, DARK_GREEN, platform_type="ledge")) # Highest platform

    # Structural Walls
    wall1_height = (main_ground_y_ref) - (initial_height - 400) # Wall from platform up to lava level
    platforms.add(Platform(TILE_SIZE + 1060, initial_height - 400, 30, wall1_height, GRAY, platform_type="wall"))
    wall2_height = (main_ground_y_ref) - (initial_height - 500)
    platforms.add(Platform(TILE_SIZE + 1410, initial_height - 500, 30, wall2_height, GRAY, platform_type="wall"))

    # Lava - assuming lava surface is at main_ground_y_ref
    lava_y_surface = main_ground_y_ref # Lava top is aligned with where ground would be
    # Lava Pit 1 (spans from TILE_SIZE to near wall1)
    hazards.add(Lava(TILE_SIZE, lava_y_surface, (TILE_SIZE + 1060) - TILE_SIZE, LAVA_PATCH_HEIGHT, ORANGE_RED))
    # Lava Pit 2 (between wall1 and wall2)
    hazards.add(Lava(TILE_SIZE + 1060 + 30, lava_y_surface, (TILE_SIZE + 1410) - (TILE_SIZE + 1060 + 30), LAVA_PATCH_HEIGHT, ORANGE_RED))
    # Lava Pit 3 (from wall2 to end of map content area)
    lava3_start_x = TILE_SIZE + 1410 + 30
    lava3_width = (map_total_width - TILE_SIZE) - lava3_start_x
    if lava3_width > 0 :
        hazards.add(Lava(lava3_start_x, lava_y_surface, lava3_width, LAVA_PATCH_HEIGHT, ORANGE_RED))

    all_content_sprites = list(platforms.sprites()) + list(hazards.sprites())
    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls(platforms, map_total_width, all_content_sprites, initial_height, extra_sky_clearance=TILE_SIZE*5)

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, \
           map_total_width, level_min_y_abs, level_max_y_abs, \
           main_ground_y_ref, 0 # Ground segment height is 0 as it's lava level

def load_map_cpu_extended(initial_width, initial_height):
    """
    Creates a larger level with CPU enemies, DEEP LAVA WELLS with fences,
    boundary walls, and colored ledges. Platform height adjusted.
    """
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    map_total_width = initial_width * 3.5
    main_ground_y_ref = initial_height - TILE_SIZE
    main_ground_segment_height_ref = TILE_SIZE # Height of the solid ground parts
    player_spawn = (TILE_SIZE * 2, main_ground_y_ref - 1) # Spawn on the first ground segment
    gap_width_lava = TILE_SIZE * 4
    lava_collision_y_level = main_ground_y_ref + 1 # So player feet sink in a bit before damage
    fence_y_pos = main_ground_y_ref - FENCE_HEIGHT

    # Ground Segments
    seg1_start_x = TILE_SIZE
    seg1_width = (initial_width * 0.7) - TILE_SIZE # Example width
    seg1_end_x = seg1_start_x + seg1_width
    platforms.add(Platform(seg1_start_x, main_ground_y_ref, seg1_width, main_ground_segment_height_ref, GRAY, platform_type="ground"))

    # Lava Pit 1 with Fences
    lava1_start_x = seg1_end_x
    lava1_width = gap_width_lava
    hazards.add(Lava(lava1_start_x, lava_collision_y_level, lava1_width, LAVA_PATCH_HEIGHT, ORANGE_RED))
    # Fences (thin platforms)
    platforms.add(Platform(lava1_start_x - FENCE_WIDTH, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, platform_type="fence"))
    platforms.add(Platform(lava1_start_x + lava1_width, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, platform_type="fence"))

    # Ground Segment 2
    seg2_start_x = lava1_start_x + lava1_width
    seg2_width = initial_width * 1.0 # Example width
    seg2_end_x = seg2_start_x + seg2_width
    platforms.add(Platform(seg2_start_x, main_ground_y_ref, seg2_width, main_ground_segment_height_ref, GRAY, platform_type="ground"))

    # Lava Pit 2 with Fences
    lava2_start_x = seg2_end_x
    lava2_width = gap_width_lava * 0.8 # Slightly smaller
    hazards.add(Lava(lava2_start_x, lava_collision_y_level, lava2_width, LAVA_PATCH_HEIGHT, ORANGE_RED))
    platforms.add(Platform(lava2_start_x - FENCE_WIDTH, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, platform_type="fence"))
    platforms.add(Platform(lava2_start_x + lava2_width, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, platform_type="fence"))

    # Ground Segment 3 (to end of map content width)
    seg3_start_x = lava2_start_x + lava2_width
    seg3_width = (map_total_width - TILE_SIZE) - seg3_start_x # Remaining width
    if seg3_width > 0:
        platforms.add(Platform(seg3_start_x, main_ground_y_ref, seg3_width, main_ground_segment_height_ref, GRAY, platform_type="ground"))

    # Floating Platforms (Ledges) - ensure they are above ground segments or lava pits
    # Platform 1 (on seg1)
    plat1_x = TILE_SIZE + (initial_width * 0.3 - TILE_SIZE) # Original x-logic
    plat1_x = max(seg1_start_x + TILE_SIZE, min(plat1_x, seg1_end_x - TILE_SIZE*7)) # Clamp within seg1
    platforms.add(Platform(plat1_x, main_ground_y_ref - TILE_SIZE * 1.8, TILE_SIZE * 6, TILE_SIZE * 0.5, DARK_GREEN, platform_type="ledge"))

    # Platform 2 (on seg2)
    platforms.add(Platform(seg2_start_x + TILE_SIZE * 2, main_ground_y_ref - TILE_SIZE * 3, TILE_SIZE * 8, TILE_SIZE * 0.5, DARK_GREEN, platform_type="ledge"))
    
    # Platform 3 (on seg3, if seg3 exists)
    if seg3_width > TILE_SIZE * 8 : # Ensure space for it
        platforms.add(Platform(seg3_start_x + TILE_SIZE * 4, main_ground_y_ref - TILE_SIZE * 5.5, TILE_SIZE * 7, TILE_SIZE * 0.5, DARK_GREEN, platform_type="ledge"))

    # Enemy Spawns
    spawn_y_on_ground = main_ground_y_ref -1 # Midbottom reference point for ground enemies
    # Enemy 1 (on Ground Segment 2)
    enemy1_x_pos = seg2_start_x + seg2_width * 0.5
    # Patrol area for enemy 1 on segment 2
    patrol_rect_enemy1 = pygame.Rect(
        seg2_start_x + TILE_SIZE,       # Left bound of patrol
        main_ground_y_ref - TILE_SIZE*2, # Top of patrol area (allow some vertical room if needed)
        seg2_width - TILE_SIZE*2,       # Width of patrol on this segment
        TILE_SIZE*2                     # Height of patrol area
    )
    enemy_spawns_data.append({'pos': (enemy1_x_pos, spawn_y_on_ground), 'patrol': patrol_rect_enemy1})

    # Enemy 2 (on Platform 2 - the one on seg2)
    enemy2_platform_ref_x = seg2_start_x + TILE_SIZE * 2 # Reference for finding the platform
    enemy2_platform = next((p for p in platforms if p.rect.left == enemy2_platform_ref_x and \
                            p.rect.width == TILE_SIZE * 8 and p.platform_type == "ledge"), None)
    if enemy2_platform:
        enemy2_x_pos = enemy2_platform.rect.centerx
        enemy2_y_pos = enemy2_platform.rect.top -1 # Spawn on top of this platform
        enemy_spawns_data.append({'pos': (enemy2_x_pos, enemy2_y_pos), 'patrol': None}) # No specific patrol area, will use default

    # Enemy 3 (on Ground Segment 3, if it exists)
    if seg3_width > TILE_SIZE:
        enemy3_x_pos = seg3_start_x + seg3_width * 0.3
        enemy_spawns_data.append({'pos': (enemy3_x_pos, spawn_y_on_ground), 'patrol': None})


    all_content_sprites = list(platforms.sprites()) + list(hazards.sprites()) + list(ladders.sprites())
    sky_clearance = TILE_SIZE * 10 # More room above the highest platform
    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls(platforms, map_total_width, all_content_sprites, initial_height, extra_sky_clearance=sky_clearance)

    return platforms, ladders, hazards, enemy_spawns_data, player_spawn, \
           map_total_width, level_min_y_abs, level_max_y_abs, \
           main_ground_y_ref, main_ground_segment_height_ref


load_map_cpu = load_map_cpu_extended # Alias for convenience

if __name__ == '__main__':
    pygame.init()
    screen_width_test = 1000
    screen_height_test = 700
    test_screen = pygame.display.set_mode((screen_width_test, screen_height_test), pygame.RESIZABLE)

    test_platforms, test_ladders, test_hazards, test_enemy_spawns, test_player_spawn, \
    test_level_width, test_level_min_y, test_level_max_y, \
    test_main_ground_y, test_main_ground_h = \
        load_map_cpu_extended(screen_width_test, screen_height_test)
    pygame.display.set_caption("Level.py - Map Test (load_map_cpu_extended)")

    all_test_sprites = pygame.sprite.Group()
    all_test_sprites.add(test_platforms.sprites(), test_ladders.sprites(), test_hazards.sprites())

    if test_enemy_spawns:
        for spawn_info in test_enemy_spawns:
            spawn_pos = spawn_info['pos']
            enemy_placeholder = pygame.sprite.Sprite()
            enemy_placeholder.image = pygame.Surface((TILE_SIZE*0.5, TILE_SIZE*0.8))
            enemy_placeholder.image.fill(ORANGE_RED)
            enemy_placeholder.rect = enemy_placeholder.image.get_rect(midbottom=spawn_pos)
            all_test_sprites.add(enemy_placeholder)
            if spawn_info.get('patrol'): # If patrol rect data exists
                patrol_rect_vis = spawn_info['patrol'].copy() # pygame.Rect is expected
                patrol_placeholder = pygame.sprite.Sprite()
                patrol_placeholder.image = pygame.Surface((patrol_rect_vis.width, patrol_rect_vis.height), pygame.SRCALPHA)
                patrol_placeholder.image.fill((255,0,255,50)) # Semi-transparent magenta
                pygame.draw.rect(patrol_placeholder.image, (255,0,255, 150), patrol_placeholder.image.get_rect(), 1) # Border
                patrol_placeholder.rect = patrol_rect_vis
                all_test_sprites.add(patrol_placeholder)

    # Dummy player for testing camera and basic movement
    class TestDummyPlayer(pygame.sprite.Sprite):
        def __init__(self, x, y):
            super().__init__()
            self.image = pygame.Surface((TILE_SIZE * 0.75, TILE_SIZE))
            self.image.fill(DARK_GREEN)
            self.rect = self.image.get_rect(midbottom=(x,y))
            self.vel = pygame.math.Vector2(0,0) # Pygame vector for test
            self.on_ground_flag = False
            # Use constants from C if available, otherwise fallback
            self.gravity = getattr(C, 'PLAYER_GRAVITY', 0.8)
            self.jump_strength = getattr(C, 'PLAYER_JUMP_STRENGTH', -15)
            self.terminal_velocity_y = getattr(C, 'TERMINAL_VELOCITY_Y', 18)


        def update(self, platform_group_for_collision):
            self.vel.y += self.gravity
            if self.vel.y > self.terminal_velocity_y: self.vel.y = self.terminal_velocity_y # Use defined terminal velocity

            pressed_keys = pygame.key.get_pressed()
            if pressed_keys[pygame.K_LEFT]: self.vel.x = -5
            elif pressed_keys[pygame.K_RIGHT]: self.vel.x = 5
            else: self.vel.x = 0

            if pressed_keys[pygame.K_UP] and self.on_ground_flag:
                self.vel.y = self.jump_strength
                self.on_ground_flag = False # Player is now in air

            # Move and collide
            self.rect.x += self.vel.x
            self.test_collision_resolution('x', platform_group_for_collision)
            self.rect.y += self.vel.y
            self.on_ground_flag = False # Assume not on ground until collision check proves otherwise
            self.test_collision_resolution('y', platform_group_for_collision)

        def test_collision_resolution(self, direction, platform_group_to_collide_with):
            for plat in pygame.sprite.spritecollide(self, platform_group_to_collide_with, False):
                if plat.image.get_alpha() == 0 : continue # Skip fully transparent platforms (like some ladders)

                if direction == 'x':
                    if self.vel.x > 0: self.rect.right = plat.rect.left
                    if self.vel.x < 0: self.rect.left = plat.rect.right
                    self.vel.x = 0
                if direction == 'y':
                    if self.vel.y > 0: # Moving down
                        self.rect.bottom = plat.rect.top
                        self.on_ground_flag = True
                        self.vel.y = 0
                    if self.vel.y < 0: # Moving up
                        self.rect.top = plat.rect.bottom
                        self.vel.y = 0 # Stop upward movement

    dummy_test_player = TestDummyPlayer(test_player_spawn[0], test_player_spawn[1])
    all_test_sprites.add(dummy_test_player)

    # Basic Camera Logic for Testing
    camera_x_offset = 0
    camera_y_offset = 0
    test_game_running = True
    test_clock = pygame.time.Clock()
    effective_level_height_for_test = test_level_max_y - test_level_min_y


    while test_game_running:
        current_screen_width, current_screen_height = test_screen.get_size()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                test_game_running = False
            if event.type == pygame.VIDEORESIZE:
                 test_screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        dummy_test_player.update(test_platforms)

        # Camera update
        camera_x_offset = -dummy_test_player.rect.centerx + current_screen_width // 2
        camera_y_offset = -dummy_test_player.rect.centery + current_screen_height // 2

        # Clamp camera to level boundaries
        camera_x_offset = min(0, camera_x_offset) # Don't scroll past left edge of defined map content
        if test_level_width > current_screen_width: # Only clamp right if level is wider than screen
            camera_x_offset = max(-(test_level_width - current_screen_width), camera_x_offset)
        else: # Level is narrower than screen
            camera_x_offset = 0 # Or center it: (current_screen_width - test_level_width) / 2

        if effective_level_height_for_test <= current_screen_height:
            # Center vertically if level is shorter than screen
            camera_y_offset = -(test_level_min_y + effective_level_height_for_test / 2 - current_screen_height / 2)
        else:
            # Clamp to top and bottom of level content
            camera_y_offset = min(-test_level_min_y, camera_y_offset) # Don't scroll past top
            camera_y_offset = max(-(test_level_max_y - current_screen_height), camera_y_offset) # Don't scroll past bottom


        test_screen.fill(BLACK) # Use BLACK from constants
        for sprite_to_draw in all_test_sprites:
            test_screen.blit(sprite_to_draw.image,
                             (sprite_to_draw.rect.x + camera_x_offset,
                              sprite_to_draw.rect.y + camera_y_offset))

        pygame.display.flip()
        test_clock.tick(60) # Target 60 FPS

    pygame.quit()

#################### END OF FILE: levels.py ####################