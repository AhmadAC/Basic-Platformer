# levels.py
# -*- coding: utf-8 -*-
"""
levels.py
Returns data structures (lists of dictionaries) for platforms, ladders, hazards, 
spawns, level width, and absolute min/max Y coordinates for the entire level.
This data is then used by game_setup.py to create PySide6 game objects.
"""
# version 2.0.0 
import random
from typing import List, Dict, Tuple, Any, Optional

# Game imports
# 'tiles.py' is no longer directly used here for instantiation,
# but its class names might be referenced in 'type' fields if needed by game_setup.
import constants as C
# Use constants directly from C, e.g., C.TILE_SIZE, C.GRAY
# from constants import TILE_SIZE, GRAY, DARK_GREEN, ORANGE_RED, LAVA_PATCH_HEIGHT, BLACK

FENCE_WIDTH = 8
FENCE_HEIGHT = 15
FENCE_COLOR = C.GRAY # Use C.GRAY

def _calculate_content_extents(
    platforms_data: List[Dict[str, Any]],
    ladders_data: List[Dict[str, Any]],
    hazards_data: List[Dict[str, Any]],
    initial_screen_height_fallback: float
) -> Tuple[float, float]:
    """Calculates min_y and max_y from lists of object data dictionaries."""
    all_tops: List[float] = []
    all_bottoms: List[float] = []

    for data_list in [platforms_data, ladders_data, hazards_data]:
        for obj_data in data_list:
            y, h = obj_data.get('y', 0.0), obj_data.get('h', 0.0)
            all_tops.append(y)
            all_bottoms.append(y + h)

    if not all_tops: # No objects with y/h defined
        # Fallback if no content to measure (e.g., an empty map definition)
        min_y_content = 0.0 - C.TILE_SIZE * 5
        max_y_content = initial_screen_height_fallback
        print(f"Warning: _calculate_content_extents found no measurable content. Using fallbacks: min_y={min_y_content}, max_y={max_y_content}")
    else:
        min_y_content = min(all_tops) if all_tops else 0.0
        max_y_content = max(all_bottoms) if all_bottoms else initial_screen_height_fallback
    
    return min_y_content, max_y_content


def _add_map_boundary_walls_data(
    platforms_data_list: List[Dict[str, Any]], 
    map_total_width: float,
    ladders_data_list: List[Dict[str, Any]], # Added for extents calculation
    hazards_data_list: List[Dict[str, Any]], # Added for extents calculation
    initial_screen_height_fallback: float, 
    extra_sky_clearance: float = 0.0
) -> Tuple[float, float]:
    """
    Calculates content extents from data lists and adds boundary wall data dictionaries
    to platforms_data_list.
    Returns min_y_overall, max_y_overall (absolute top/bottom of level including walls).
    """
    min_y_content, max_y_content = _calculate_content_extents(
        platforms_data_list, ladders_data_list, hazards_data_list, initial_screen_height_fallback
    )

    ceiling_object_top_y = min_y_content - C.TILE_SIZE - extra_sky_clearance
    level_min_y_abs = ceiling_object_top_y
    level_max_y_abs = max_y_content + C.TILE_SIZE
    boundary_box_height = level_max_y_abs - level_min_y_abs

    boundary_color = getattr(C, 'DARK_GRAY', (50,50,50)) # Consistent boundary color

    platforms_data_list.append({'x': 0.0, 'y': ceiling_object_top_y, 'w': map_total_width, 'h': float(C.TILE_SIZE), 'color': boundary_color, 'type': "boundary_wall_top"})
    platforms_data_list.append({'x': 0.0, 'y': max_y_content, 'w': map_total_width, 'h': float(C.TILE_SIZE), 'color': boundary_color, 'type': "boundary_wall_bottom"})
    platforms_data_list.append({'x': 0.0, 'y': level_min_y_abs, 'w': float(C.TILE_SIZE), 'h': boundary_box_height, 'color': boundary_color, 'type': "boundary_wall_left"})
    platforms_data_list.append({'x': map_total_width - C.TILE_SIZE, 'y': level_min_y_abs, 'w': float(C.TILE_SIZE), 'h': boundary_box_height, 'color': boundary_color, 'type': "boundary_wall_right"})

    return level_min_y_abs, level_max_y_abs


def load_map_original(initial_width: float, initial_height: float) -> Tuple[
    List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], 
    List[Dict[str, Any]], Optional[Dict[str, Any]], Tuple[float, float], Optional[Dict[str, Any]],
    float, float, float, float, float, Tuple[int, int, int], Optional[List[Dict[str, Any]]]
]:
    """ Returns data for the original level layout. """
    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = [] # Added
    statue_spawns_data: List[Dict[str, Any]] = [] # Added

    map_total_width = initial_width * 2.5
    player_spawn_pos = (C.TILE_SIZE + 60.0, initial_height - C.TILE_SIZE * 2.0 - 1.0)
    player_spawn_props = {} # Default empty props
    main_ground_y_ref = initial_height - C.TILE_SIZE
    main_ground_segment_height_ref = float(C.TILE_SIZE)

    platforms_data.append({'x': float(C.TILE_SIZE), 'y': main_ground_y_ref, 'w': map_total_width - 2 * C.TILE_SIZE, 'h': main_ground_segment_height_ref, 'color': C.GRAY, 'type': "ground"})
    platforms_data.append({'x': C.TILE_SIZE + 160.0, 'y': initial_height - 150.0, 'w': 250.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    platforms_data.append({'x': C.TILE_SIZE + 410.0, 'y': initial_height - 300.0, 'w': 180.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    platforms_data.append({'x': min(map_total_width - C.TILE_SIZE - 200.0, C.TILE_SIZE + initial_width - 350.0), 'y': initial_height - 450.0, 'w': 200.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    platforms_data.append({'x': min(map_total_width - C.TILE_SIZE - 150.0, C.TILE_SIZE + initial_width + 150.0), 'y': initial_height - 250.0, 'w': 150.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    platforms_data.append({'x': C.TILE_SIZE + 860.0, 'y': initial_height - 550.0, 'w': 100.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})

    wall_mid_x = C.TILE_SIZE + 760.0
    wall_mid_width = 30.0
    if wall_mid_x + wall_mid_width > map_total_width - C.TILE_SIZE:
        wall_mid_width = max(1.0, (map_total_width - C.TILE_SIZE) - wall_mid_x)
    platforms_data.append({'x': wall_mid_x, 'y': initial_height - 400.0, 'w': wall_mid_width, 'h': 360.0, 'color': C.GRAY, 'type': "wall"})

    ladder_width = 40.0
    ladder_height_main = 250.0
    ladders_data.append({'x': min(map_total_width - C.TILE_SIZE - ladder_width, C.TILE_SIZE + initial_width - 500.0), 'y': main_ground_y_ref - ladder_height_main, 'w': ladder_width, 'h': ladder_height_main})
    ladders_data.append({'x': C.TILE_SIZE + 310.0, 'y': initial_height - 250.0, 'w': ladder_width, 'h': 150.0})

    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=C.TILE_SIZE * 5.0)
    
    level_bg_color = getattr(C, "PURPLE_BACKGROUND", (75,0,130)) # Example default

    return (platforms_data, ladders_data, hazards_data, enemy_spawns_data, collectible_spawns_data,
            player_spawn_pos, player_spawn_props,
            map_total_width, level_min_y_abs, level_max_y_abs,
            main_ground_y_ref, main_ground_segment_height_ref,
            level_bg_color, statue_spawns_data)


def load_map_lava(initial_width: float, initial_height: float) -> Tuple[
    List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], 
    List[Dict[str, Any]], Optional[Dict[str, Any]], Tuple[float, float], Optional[Dict[str, Any]],
    float, float, float, float, float, Tuple[int, int, int], Optional[List[Dict[str, Any]]]
]:
    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = []
    statue_spawns_data: List[Dict[str, Any]] = []

    map_total_width = initial_width * 2.8
    player_spawn_x = C.TILE_SIZE + 30.0
    player_spawn_y = initial_height - 120.0 - C.TILE_SIZE
    player_spawn_pos = (player_spawn_x, player_spawn_y)
    player_spawn_props = {}
    main_ground_y_ref = initial_height - C.TILE_SIZE

    platforms_data.append({'x': float(C.TILE_SIZE), 'y': initial_height - 120.0, 'w': 150.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    # ... (add other platforms similarly) ...
    platforms_data.append({'x': C.TILE_SIZE + 1560.0, 'y': initial_height - 480.0, 'w': 200.0, 'h': 20.0, 'color': C.DARK_GREEN, 'type': "ledge"})
    
    wall1_height = main_ground_y_ref - (initial_height - 400.0)
    platforms_data.append({'x': C.TILE_SIZE + 1060.0, 'y': initial_height - 400.0, 'w': 30.0, 'h': wall1_height, 'color': C.GRAY, 'type': "wall"})
    wall2_height = main_ground_y_ref - (initial_height - 500.0)
    platforms_data.append({'x': C.TILE_SIZE + 1410.0, 'y': initial_height - 500.0, 'w': 30.0, 'h': wall2_height, 'color': C.GRAY, 'type': "wall"})

    lava_y_surface = main_ground_y_ref
    hazards_data.append({'type': 'lava', 'x': float(C.TILE_SIZE), 'y': lava_y_surface, 'w': (C.TILE_SIZE + 1060.0) - C.TILE_SIZE, 'h': float(C.LAVA_PATCH_HEIGHT), 'color': C.ORANGE_RED})
    # ... (add other hazards similarly) ...
    lava3_start_x = C.TILE_SIZE + 1410.0 + 30.0
    lava3_width = (map_total_width - C.TILE_SIZE) - lava3_start_x
    if lava3_width > 0:
        hazards_data.append({'type': 'lava', 'x': lava3_start_x, 'y': lava_y_surface, 'w': lava3_width, 'h': float(C.LAVA_PATCH_HEIGHT), 'color': C.ORANGE_RED})

    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=C.TILE_SIZE * 5.0)
    level_bg_color = getattr(C, "PURPLE_BACKGROUND", (75,0,130))

    return (platforms_data, ladders_data, hazards_data, enemy_spawns_data, collectible_spawns_data,
            player_spawn_pos, player_spawn_props,
            map_total_width, level_min_y_abs, level_max_y_abs,
            main_ground_y_ref, 0.0, # Ground segment height is 0 for lava level
            level_bg_color, statue_spawns_data)


def load_map_cpu_extended(initial_width: float, initial_height: float) -> Tuple[
    List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], 
    List[Dict[str, Any]], Optional[Dict[str, Any]], Tuple[float, float], Optional[Dict[str, Any]],
    float, float, float, float, float, Tuple[int, int, int], Optional[List[Dict[str, Any]]]
]:
    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = []
    statue_spawns_data: List[Dict[str, Any]] = []

    map_total_width = initial_width * 3.5
    main_ground_y_ref = initial_height - C.TILE_SIZE
    main_ground_segment_height_ref = float(C.TILE_SIZE)
    player_spawn_pos = (C.TILE_SIZE * 2.0, main_ground_y_ref - 1.0)
    player_spawn_props = {}
    gap_width_lava = C.TILE_SIZE * 4.0
    lava_collision_y_level = main_ground_y_ref + 1.0
    fence_y_pos = main_ground_y_ref - FENCE_HEIGHT

    # Ground Segments
    seg1_start_x = float(C.TILE_SIZE)
    seg1_width = (initial_width * 0.7) - C.TILE_SIZE
    seg1_end_x = seg1_start_x + seg1_width
    platforms_data.append({'x': seg1_start_x, 'y': main_ground_y_ref, 'w': seg1_width, 'h': main_ground_segment_height_ref, 'color': C.GRAY, 'type': "ground"})

    # Lava Pit 1 with Fences
    lava1_start_x = seg1_end_x
    lava1_width = gap_width_lava
    hazards_data.append({'type': 'lava', 'x': lava1_start_x, 'y': lava_collision_y_level, 'w': lava1_width, 'h': float(C.LAVA_PATCH_HEIGHT), 'color': C.ORANGE_RED})
    platforms_data.append({'x': lava1_start_x - FENCE_WIDTH, 'y': fence_y_pos, 'w': float(FENCE_WIDTH), 'h': float(FENCE_HEIGHT), 'color': FENCE_COLOR, 'type': "fence"})
    platforms_data.append({'x': lava1_start_x + lava1_width, 'y': fence_y_pos, 'w': float(FENCE_WIDTH), 'h': float(FENCE_HEIGHT), 'color': FENCE_COLOR, 'type': "fence"})

    # Ground Segment 2
    seg2_start_x = lava1_start_x + lava1_width
    seg2_width = initial_width * 1.0
    seg2_end_x = seg2_start_x + seg2_width
    platforms_data.append({'x': seg2_start_x, 'y': main_ground_y_ref, 'w': seg2_width, 'h': main_ground_segment_height_ref, 'color': C.GRAY, 'type': "ground"})
    
    # ... (Continue converting other platforms, hazards, enemy_spawns like above) ...
    # Example for enemy patrol:
    # patrol_rect_enemy1_data = {'x': seg2_start_x + C.TILE_SIZE, 'y': main_ground_y_ref - C.TILE_SIZE*2, 
    #                           'w': seg2_width - C.TILE_SIZE*2, 'h': C.TILE_SIZE*2}
    # enemy_spawns_data.append({'pos': (enemy1_x_pos, spawn_y_on_ground), 'patrol_rect_data': patrol_rect_enemy1_data})


    # Floating Platforms
    plat1_x = C.TILE_SIZE + (initial_width * 0.3 - C.TILE_SIZE)
    plat1_x = max(seg1_start_x + C.TILE_SIZE, min(plat1_x, seg1_end_x - C.TILE_SIZE*7))
    platforms_data.append({'x': plat1_x, 'y': main_ground_y_ref - C.TILE_SIZE * 1.8, 'w': C.TILE_SIZE * 6.0, 'h': C.TILE_SIZE * 0.5, 'color': C.DARK_GREEN, 'type': "ledge"})
    platforms_data.append({'x': seg2_start_x + C.TILE_SIZE * 2.0, 'y': main_ground_y_ref - C.TILE_SIZE * 3.0, 'w': C.TILE_SIZE * 8.0, 'h': C.TILE_SIZE * 0.5, 'color': C.DARK_GREEN, 'type': "ledge"})
    
    seg3_start_x = seg2_start_x + seg2_width + gap_width_lava * 0.8 # After lava pit 2
    seg3_width = (map_total_width - C.TILE_SIZE) - seg3_start_x
    if seg3_width > C.TILE_SIZE * 8 :
        platforms_data.append({'x': seg3_start_x + C.TILE_SIZE * 4.0, 'y': main_ground_y_ref - C.TILE_SIZE * 5.5, 'w': C.TILE_SIZE * 7.0, 'h': C.TILE_SIZE * 0.5, 'color': C.DARK_GREEN, 'type': "ledge"})

    # Enemy Spawns (convert patrol rect if needed)
    spawn_y_on_ground = main_ground_y_ref - 1.0
    enemy1_x_pos = seg2_start_x + seg2_width * 0.5
    patrol_data_e1 = {'x': seg2_start_x + C.TILE_SIZE, 'y': main_ground_y_ref - C.TILE_SIZE*2, 'width': seg2_width - C.TILE_SIZE*2, 'height': C.TILE_SIZE*2.0}
    enemy_spawns_data.append({'pos': (enemy1_x_pos, spawn_y_on_ground), 'patrol_rect_data': patrol_data_e1}) # Note: key changed

    # For Enemy 2, find its platform data to get coordinates
    # This is tricky as platforms_data is just data. game_setup.py would resolve this.
    # For now, let's estimate. Platform 2 on seg2:
    enemy2_platform_y = main_ground_y_ref - C.TILE_SIZE * 3.0
    enemy2_platform_x = seg2_start_x + C.TILE_SIZE * 2.0
    enemy2_x_pos = enemy2_platform_x + (C.TILE_SIZE * 8.0) / 2.0 # Center of that platform
    enemy2_y_pos = enemy2_platform_y - 1.0
    enemy_spawns_data.append({'pos': (enemy2_x_pos, enemy2_y_pos), 'patrol_rect_data': None})
    
    if seg3_width > C.TILE_SIZE:
        enemy3_x_pos = seg3_start_x + seg3_width * 0.3
        enemy_spawns_data.append({'pos': (enemy3_x_pos, spawn_y_on_ground), 'patrol_rect_data': None})


    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=C.TILE_SIZE * 10.0)
    level_bg_color = getattr(C, "LIGHT_BLUE", (173, 216, 230))

    return (platforms_data, ladders_data, hazards_data, enemy_spawns_data, collectible_spawns_data,
            player_spawn_pos, player_spawn_props,
            map_total_width, level_min_y_abs, level_max_y_abs,
            main_ground_y_ref, main_ground_segment_height_ref,
            level_bg_color, statue_spawns_data)


load_map_cpu = load_map_cpu_extended # Alias for convenience

# Testing would be done by running the main game and loading these maps.