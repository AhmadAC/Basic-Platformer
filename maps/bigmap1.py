# Level: bigmap1
# Generated by Platformer Level Editor
import pygame
from tiles import Platform, Ladder, Lava
from statue import Statue
import constants as C

LEVEL_SPECIFIC_BACKGROUND_COLOR = (173, 216, 230)
player1_spawn_pos = (90.0, 1918.0)
player1_spawn_props = {}

def load_map_bigmap1(initial_screen_width, initial_screen_height):
    """Loads the 'bigmap1' level."""
    platforms = pygame.sprite.Group()
    ladders = pygame.sprite.Group()
    hazards = pygame.sprite.Group()
    enemy_spawns_data = []
    collectible_spawns_data = []
    statue_spawns_data = []

    platforms.add(Platform(160, 1880.0, 80, 13, (0, 100, 0), platform_type='ledge'))
    platforms.add(Platform(240, 1880, 40, 10, (0, 100, 0), platform_type='ledge'))
    platforms.add(Platform(120, 1880, 40, 10, (128, 128, 128), platform_type='ledge'))
    platforms.add(Platform(0, 600, 80, 200, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 1160.0, 80, 120, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 1360.0, 80, 560, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 0, 120, 600, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 800.0, 120, 360, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 1280.0, 120, 80, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 1920.0, 360, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(0, 1960.0, 4040, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(80, 2000, 640, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(680, 1920, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(960.0, 2000, 200, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(1200.0, 1920.0, 1680, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(1280.0, 2000.0, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(1400.0, 2000.0, 360, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(1760.0, 1880, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(2080.0, 2000, 120, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(2120.0, 1880, 120, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(2520.0, 1880, 120, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(2600.0, 2000, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(2760.0, 2000, 320, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3040.0, 1920, 320, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3360.0, 2000, 280, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3400.0, 1920, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3560.0, 1880.0, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3560.0, 1920.0, 480, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3760, 2000, 80, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3800.0, 1880.0, 240, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3840.0, 1840.0, 200, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3920.0, 0, 80, 1600, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3920, 1600.0, 120, 80, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3920.0, 2000, 120, 40, (128, 128, 128), platform_type='wall'))
    platforms.add(Platform(3960, 1680.0, 80, 160, (128, 128, 128), platform_type='wall'))
    # No ladders placed.
    hazards.add(Lava(880.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(920.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(1000.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(1040.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(960.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(1080.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(1120.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(840.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(800.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(760.0, 1920, 40, 41, (255, 69, 0)))
    hazards.add(Lava(1160.0, 1920, 40, 41, (255, 69, 0)))
    enemy_spawns_data.append({'pos': (330, 1918), 'patrol': None, 'enemy_color_id': 'yellow', 'properties': {}})
    enemy_spawns_data.append({'pos': (410, 1958), 'patrol': None, 'enemy_color_id': 'purple', 'properties': {}})
    enemy_spawns_data.append({'pos': (450, 1958), 'patrol': None, 'enemy_color_id': 'pink', 'properties': {}})
    enemy_spawns_data.append({'pos': (490, 1958.0), 'patrol': None, 'enemy_color_id': 'green', 'properties': {}})
    collectible_spawns_data.append({'type': 'chest', 'pos': (1315.0, 1930), 'properties': {}})
    # No statue spawns defined.

    map_total_width_pixels = 4200
    level_min_y_absolute = -80
    level_max_y_absolute = 2040
    main_ground_y_reference = 2040
    main_ground_height_reference = 40

    _boundary_thickness = 80
    _boundary_wall_height = 2280
    _boundary_color = (50, 50, 50)

    platforms.add(Platform(4040, -160, 160, 2280, _boundary_color, platform_type='wall'))

    platforms.add(Platform(0, level_min_y_absolute - _boundary_thickness, 4200, _boundary_thickness, _boundary_color, platform_type="boundary_wall_top"))
    platforms.add(Platform(0, level_max_y_absolute, 4200, _boundary_thickness, _boundary_color, platform_type="boundary_wall_bottom"))
    platforms.add(Platform(0 - _boundary_thickness, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_left"))
    platforms.add(Platform(map_total_width_pixels, level_min_y_absolute - _boundary_thickness, _boundary_thickness, _boundary_wall_height, _boundary_color, platform_type="boundary_wall_right"))

    print(f"Map 'load_map_bigmap1' loaded with: {len(platforms)} platforms, {len(ladders)} ladders, {len(hazards)} hazards, {len(statue_spawns_data)} statues.")
    return (platforms, ladders, hazards, enemy_spawns_data, collectible_spawns_data,
            player1_spawn_pos, player1_spawn_props,
            map_total_width_pixels, level_min_y_absolute, level_max_y_absolute,
            main_ground_y_reference, main_ground_height_reference,
            LEVEL_SPECIFIC_BACKGROUND_COLOR,
            statue_spawns_data)
