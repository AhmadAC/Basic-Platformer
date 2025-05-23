# Level: booooi
# Generated by Platformer Level Editor
import pygame
from tiles import Platform, Ladder, Lava
from statue import Statue
import constants as C

LEVEL_SPECIFIC_BACKGROUND_COLOR = (170, 255, 127)
player1_spawn_pos = (10, 358)
player1_spawn_props = {}

def load_map_booooi(initial_screen_width, initial_screen_height):
    """Loads the 'booooi' level."""
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    collectible_spawns_data = []
    statue_spawns_data = []

    platforms.add(Platform(0, 380, 120, 20, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(120, 340, 40, 20, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(120, 360, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(320, 360, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(360, 340, 40, 20, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(400, 380, 120, 20, (128, 128, 128), platform_type='wall'))
    # No ladders placed.
    hazards.add(Lava(520, 360, 40, 41, (255, 69, 0)))
    hazards.add(Lava(560, 360, 40, 41, (255, 69, 0)))
    hazards.add(Lava(600, 360, 40, 41, (255, 69, 0)))
    hazards.add(Lava(80, 480, 40, 41, (255, 69, 0)))
    # No enemy spawns defined.
    # No collectible spawns defined.
    # No statue spawns defined.

    map_total_width_pixels = 1000
    level_min_y_absolute = 240
    level_max_y_absolute = 521
    main_ground_y_reference = 521
    main_ground_height_reference = 40

    _boundary_thickness = 80
    _boundary_wall_height = 441
    _boundary_color = (50, 50, 50)

    platforms.add(Platform(640, 160, 360, 441, _boundary_color, platform_type='wall'))

    platforms.add(Platform(0, level_min_y_absolute - _boundary_thickness, 1000, _boundary_thickness, _boundary_color, platform_type="boundary_wall_top"))
    platforms.add(Platform(0, level_max_y_absolute, 1000, _boundary_thickness, _boundary_color, platform_type="boundary_wall_bottom"))
    platforms.add(Platform(0 - _boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_left"))
    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_right"))

    print(f"Map 'load_map_booooi' loaded with: {len(platforms)} platforms, {len(ladders)} ladders, {len(hazards)} hazards, {len(statue_spawns_data)} statues.")
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn_pos, player1_spawn_props,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR,
            statue_spawns_data)
