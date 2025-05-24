#################### START OF FILE: levels.py ####################

# levels.py
# -*- coding: utf-8 -*-
"""
levels.py
Returns data structures (dictionaries) for platforms, ladders, hazards,
spawns, level width, and absolute min/max Y coordinates for the entire level.
This data is then used by game_setup.py to create PySide6 game objects.
"""
# version 2.0.4 (Corrected level_max_y_absolute for camera centering)
import random
from typing import List, Dict, Tuple, Any, Optional

# Game imports
import constants as C

FENCE_WIDTH = 8.0 
FENCE_HEIGHT = 15.0 
FENCE_COLOR = C.GRAY

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
            rect_coords = obj_data.get('rect')
            if isinstance(rect_coords, (list, tuple)) and len(rect_coords) == 4:
                y, h = float(rect_coords[1]), float(rect_coords[3])
                all_tops.append(y)
                all_bottoms.append(y + h)
            elif all(k in obj_data for k in ['x','y','w','h']): # Legacy check
                print(f"Levels.py Warning: Object data {obj_data.get('type', 'Unknown type')} is using legacy x,y,w,h keys. Please migrate to 'rect'.")
                y, h = float(obj_data['y']), float(obj_data['h'])
                all_tops.append(y)
                all_bottoms.append(y + h)


    if not all_tops: # Handle empty levels
        min_y_content = 0.0 - C.TILE_SIZE * 5 # Default sky area
        max_y_content = initial_screen_height_fallback
        print(f"Warning: _calculate_content_extents found no measurable content. Using fallbacks: min_y={min_y_content}, max_y={max_y_content}")
    else:
        min_y_content = min(all_tops) if all_tops else 0.0
        max_y_content = max(all_bottoms) if all_bottoms else initial_screen_height_fallback
    
    return min_y_content, max_y_content


def _add_map_boundary_walls_data(
    platforms_data_list: List[Dict[str, Any]],
    map_total_width: float,
    ladders_data_list: List[Dict[str, Any]], 
    hazards_data_list: List[Dict[str, Any]],   
    initial_screen_height_fallback: float,
    extra_sky_clearance: float = 0.0
) -> Tuple[float, float]: 
    """
    Calculates content extents and adds boundary wall data.
    Returns min_y_abs_for_camera, max_y_abs_for_camera.
    The returned max_y_abs_for_camera is now based on the original content's bottom,
    not necessarily the bottom of the lowest decorative boundary wall added below it.
    """
    min_y_content, max_y_content_original = _calculate_content_extents(
        platforms_data_list, ladders_data_list, hazards_data_list, initial_screen_height_fallback
    )

    # This is the top of the highest boundary wall (ceiling) for camera consideration
    level_min_y_abs_for_camera = min_y_content - float(C.TILE_SIZE) - extra_sky_clearance
    
    # The camera should consider the bottom of the *original content*
    # as the "bottom" of the level for its clamping and centering logic if the level is small.
    level_max_y_abs_for_camera = max_y_content_original
    
    # The boundary walls themselves will extend beyond these camera-focused extents if needed.
    # Height of the overall bounding box for walls (can extend below max_y_abs_for_camera for safety floor)
    # The safety floor's top is at max_y_content_original, extending TILE_SIZE down.
    overall_boundary_box_height_for_walls = (max_y_content_original + float(C.TILE_SIZE)) - level_min_y_abs_for_camera

    boundary_color = getattr(C, 'DARK_GRAY', (50,50,50))

    # Top boundary wall (ceiling) - its bottom edge aligns with level_min_y_abs_for_camera + TILE_SIZE
    platforms_data_list.append(_create_platform_data(0.0, level_min_y_abs_for_camera, map_total_width, float(C.TILE_SIZE), boundary_color, "boundary_wall_top", {"is_boundary": True}))
    
    # Bottom boundary wall (safety floor) - its top edge aligns with max_y_content_original
    platforms_data_list.append(_create_platform_data(0.0, max_y_content_original, map_total_width, float(C.TILE_SIZE), boundary_color, "boundary_wall_bottom", {"is_boundary": True}))
    
    # Left boundary wall - spans the full height of the wall bounding box
    platforms_data_list.append(_create_platform_data(0.0, level_min_y_abs_for_camera, float(C.TILE_SIZE), overall_boundary_box_height_for_walls, boundary_color, "boundary_wall_left", {"is_boundary": True}))
    
    # Right boundary wall - spans the full height of the wall bounding box
    platforms_data_list.append(_create_platform_data(map_total_width - float(C.TILE_SIZE), level_min_y_abs_for_camera, float(C.TILE_SIZE), overall_boundary_box_height_for_walls, boundary_color, "boundary_wall_right", {"is_boundary": True}))

    return level_min_y_abs_for_camera, level_max_y_abs_for_camera

def _create_platform_data(x: float, y: float, w: float, h: float, color: Tuple[int,int,int], p_type: str, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'rect': (float(x), float(y), float(w), float(h)), 'color': color, 'type': p_type, 'properties': props or {}}

def _create_ladder_data(x: float, y: float, w: float, h: float) -> Dict[str, Any]:
    return {'rect': (float(x), float(y), float(w), float(h))}

def _create_hazard_data(h_type: str, x: float, y: float, w: float, h: float, color: Tuple[int,int,int]) -> Dict[str, Any]:
    return {'type': h_type, 'rect': (float(x), float(y), float(w), float(h)), 'color': color}

def _create_enemy_spawn_data(start_pos_tuple: Tuple[float,float], enemy_type_str: str, patrol_rect_data_dict: Optional[Dict[str,float]]=None, props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    data = {'start_pos': start_pos_tuple, 'type': enemy_type_str, 'properties': props or {}}
    if patrol_rect_data_dict: # Only add if not None
        data['patrol_rect_data'] = patrol_rect_data_dict
    return data


def _create_item_spawn_data(item_type_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'type': item_type_str, 'pos': pos_tuple, 'properties': props or {}}

def _create_statue_spawn_data(statue_id_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'id': statue_id_str, 'pos': pos_tuple, 'properties': props or {}}


def load_map_original() -> Dict[str, Any]:
    """ Returns data for the original level layout. """
    initial_height = float(C.TILE_SIZE * 15)
    initial_width = float(C.TILE_SIZE * 20)

    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = []
    statue_spawns_data: List[Dict[str, Any]] = []

    map_total_width = initial_width * 2.5
    player_spawn_pos = (float(C.TILE_SIZE) + 60.0, initial_height - float(C.TILE_SIZE) * 2.0 - 1.0)
    player_spawn_props = {} # Add any specific P1 properties here if needed
    main_ground_y_ref = initial_height - float(C.TILE_SIZE)
    main_ground_segment_height_ref = float(C.TILE_SIZE)

    platforms_data.append(_create_platform_data(float(C.TILE_SIZE), main_ground_y_ref, map_total_width - 2 * float(C.TILE_SIZE), main_ground_segment_height_ref, C.GRAY, "ground"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 160.0, initial_height - 150.0, 250.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 410.0, initial_height - 300.0, 180.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(min(map_total_width - float(C.TILE_SIZE) - 200.0, float(C.TILE_SIZE) + initial_width - 350.0), initial_height - 450.0, 200.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(min(map_total_width - float(C.TILE_SIZE) - 150.0, float(C.TILE_SIZE) + initial_width + 150.0), initial_height - 250.0, 150.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 860.0, initial_height - 550.0, 100.0, 20.0, C.DARK_GREEN, "ledge"))

    wall_mid_x = float(C.TILE_SIZE) + 760.0
    wall_mid_width = 30.0
    if wall_mid_x + wall_mid_width > map_total_width - float(C.TILE_SIZE):
        wall_mid_width = max(1.0, (map_total_width - float(C.TILE_SIZE)) - wall_mid_x)
    platforms_data.append(_create_platform_data(wall_mid_x, initial_height - 400.0, wall_mid_width, 360.0, C.GRAY, "wall"))

    ladder_width = 40.0
    ladder_height_main = 250.0
    ladders_data.append(_create_ladder_data(min(map_total_width - float(C.TILE_SIZE) - ladder_width, float(C.TILE_SIZE) + initial_width - 500.0), main_ground_y_ref - ladder_height_main, ladder_width, ladder_height_main))
    ladders_data.append(_create_ladder_data(float(C.TILE_SIZE) + 310.0, initial_height - 250.0, ladder_width, 150.0))

    level_min_y_abs_for_cam, level_max_y_abs_for_cam = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=float(C.TILE_SIZE) * 5.0)
    level_bg_color = getattr(C, "PURPLE_BACKGROUND", (75,0,130))

    return {
        "level_name": "original",
        "platforms_list": platforms_data,
        "ladders_list": ladders_data,
        "hazards_list": hazards_data,
        "enemies_list": enemy_spawns_data,
        "items_list": collectible_spawns_data,
        "statues_list": statue_spawns_data,
        "player_start_pos_p1": player_spawn_pos,
        "player1_spawn_props": player_spawn_props, 
        "level_pixel_width": map_total_width,
        "level_min_x_absolute": 0.0, # Assuming level starts at x=0
        "level_min_y_absolute": level_min_y_abs_for_cam,
        "level_max_y_absolute": level_max_y_abs_for_cam, # Use the value for camera centering
        "ground_level_y_ref": main_ground_y_ref,
        "ground_platform_height_ref": main_ground_segment_height_ref,
        "background_color": level_bg_color
    }


def load_map_lava() -> Dict[str, Any]:
    initial_height = float(C.TILE_SIZE * 15)
    initial_width = float(C.TILE_SIZE * 20)

    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = []
    statue_spawns_data: List[Dict[str, Any]] = []

    map_total_width = initial_width * 2.8
    player_spawn_x = float(C.TILE_SIZE) + 30.0
    player_spawn_y = initial_height - 120.0 - float(C.TILE_SIZE) # Spawn on the first ledge
    player_spawn_pos = (player_spawn_x, player_spawn_y)
    player_spawn_props = {}
    main_ground_y_ref = initial_height - float(C.TILE_SIZE) # Theoretical ground if no lava

    platforms_data.append(_create_platform_data(float(C.TILE_SIZE), initial_height - 120.0, 150.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 260.0, initial_height - 180.0, 150.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 520.0, initial_height - 250.0, 150.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 800.0, initial_height - 320.0, 150.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 1100.0, initial_height - 400.0, 200.0, 20.0, C.DARK_GREEN, "ledge"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 1560.0, initial_height - 480.0, 200.0, 20.0, C.DARK_GREEN, "ledge"))

    wall1_height = main_ground_y_ref - (initial_height - 400.0) # Height from its top to theoretical ground
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 1060.0, initial_height - 400.0, 30.0, wall1_height, C.GRAY, "wall"))
    wall2_height = main_ground_y_ref - (initial_height - 500.0)
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) + 1410.0, initial_height - 500.0, 30.0, wall2_height, C.GRAY, "wall"))

    lava_y_surface = main_ground_y_ref # Lava fills up to the theoretical ground level
    hazards_data.append(_create_hazard_data('lava', float(C.TILE_SIZE), lava_y_surface, (float(C.TILE_SIZE) + 1060.0) - float(C.TILE_SIZE), float(C.LAVA_PATCH_HEIGHT), C.ORANGE_RED))
    hazards_data.append(_create_hazard_data('lava', float(C.TILE_SIZE) + 1060.0 + 30.0, lava_y_surface, (float(C.TILE_SIZE) + 1410.0) - (float(C.TILE_SIZE) + 1060.0 + 30.0), float(C.LAVA_PATCH_HEIGHT), C.ORANGE_RED))
    lava3_start_x = float(C.TILE_SIZE) + 1410.0 + 30.0
    lava3_width = (map_total_width - float(C.TILE_SIZE)) - lava3_start_x
    if lava3_width > 0:
        hazards_data.append(_create_hazard_data('lava', lava3_start_x, lava_y_surface, lava3_width, float(C.LAVA_PATCH_HEIGHT), C.ORANGE_RED))

    level_min_y_abs_for_cam, level_max_y_abs_for_cam = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=float(C.TILE_SIZE) * 5.0)
    level_bg_color = getattr(C, "PURPLE_BACKGROUND", (75,0,130))

    return {
        "level_name": "lava",
        "platforms_list": platforms_data,
        "ladders_list": ladders_data,
        "hazards_list": hazards_data,
        "enemies_list": enemy_spawns_data,
        "items_list": collectible_spawns_data,
        "statues_list": statue_spawns_data,
        "player_start_pos_p1": player_spawn_pos,
        "player1_spawn_props": player_spawn_props,
        "level_pixel_width": map_total_width,
        "level_min_x_absolute": 0.0,
        "level_min_y_absolute": level_min_y_abs_for_cam,
        "level_max_y_absolute": level_max_y_abs_for_cam,
        "ground_level_y_ref": main_ground_y_ref, # Theoretical ground, actual ground is lava surface
        "ground_platform_height_ref": 0.0, # No single "main" ground platform
        "background_color": level_bg_color
    }


def load_map_cpu_extended() -> Dict[str, Any]:
    initial_height = float(C.TILE_SIZE * 15)
    initial_width = float(C.TILE_SIZE * 20)

    platforms_data: List[Dict[str, Any]] = []
    ladders_data: List[Dict[str, Any]] = []
    hazards_data: List[Dict[str, Any]] = []
    enemy_spawns_data: List[Dict[str, Any]] = []
    collectible_spawns_data: List[Dict[str, Any]] = []
    statue_spawns_data: List[Dict[str, Any]] = []

    map_total_width = initial_width * 3.5 
    main_ground_y_ref = initial_height - float(C.TILE_SIZE)
    main_ground_segment_height_ref = float(C.TILE_SIZE)
    player_spawn_pos = (float(C.TILE_SIZE) * 2.0, main_ground_y_ref - 1.0) 
    player_spawn_props = {}
    gap_width_lava = float(C.TILE_SIZE) * 4.0
    lava_collision_y_level = main_ground_y_ref + 1.0 
    fence_y_pos = main_ground_y_ref - FENCE_HEIGHT

    seg1_start_x = float(C.TILE_SIZE)
    seg1_width = (initial_width * 0.7) - float(C.TILE_SIZE)
    seg1_end_x = seg1_start_x + seg1_width
    platforms_data.append(_create_platform_data(seg1_start_x, main_ground_y_ref, seg1_width, main_ground_segment_height_ref, C.GRAY, "ground"))

    lava1_start_x = seg1_end_x
    lava1_width = gap_width_lava
    hazards_data.append(_create_hazard_data('lava', lava1_start_x, lava_collision_y_level, lava1_width, float(C.LAVA_PATCH_HEIGHT), C.ORANGE_RED))
    platforms_data.append(_create_platform_data(lava1_start_x - FENCE_WIDTH, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, "fence"))
    platforms_data.append(_create_platform_data(lava1_start_x + lava1_width, fence_y_pos, FENCE_WIDTH, FENCE_HEIGHT, FENCE_COLOR, "fence"))

    seg2_start_x = lava1_start_x + lava1_width
    seg2_width = initial_width * 1.0
    platforms_data.append(_create_platform_data(seg2_start_x, main_ground_y_ref, seg2_width, main_ground_segment_height_ref, C.GRAY, "ground"))
    
    plat1_x = float(C.TILE_SIZE) + (initial_width * 0.3 - float(C.TILE_SIZE))
    plat1_x = max(seg1_start_x + float(C.TILE_SIZE), min(plat1_x, seg1_end_x - float(C.TILE_SIZE)*7)) 
    platforms_data.append(_create_platform_data(plat1_x, main_ground_y_ref - float(C.TILE_SIZE) * 1.8, float(C.TILE_SIZE) * 6.0, float(C.TILE_SIZE) * 0.5, C.DARK_GREEN, "ledge"))
    
    enemy2_platform_y = main_ground_y_ref - float(C.TILE_SIZE) * 3.0
    enemy2_platform_x_start = seg2_start_x + float(C.TILE_SIZE) * 2.0
    enemy2_platform_width = float(C.TILE_SIZE) * 8.0
    platforms_data.append(_create_platform_data(enemy2_platform_x_start, enemy2_platform_y, enemy2_platform_width, float(C.TILE_SIZE) * 0.5, C.DARK_GREEN, "ledge"))
    
    seg3_start_x = seg2_start_x + seg2_width + gap_width_lava * 0.8
    seg3_width = (map_total_width - float(C.TILE_SIZE)) - seg3_start_x
    if seg3_width > float(C.TILE_SIZE) * 8 : 
        platforms_data.append(_create_platform_data(seg3_start_x + float(C.TILE_SIZE) * 4.0, main_ground_y_ref - float(C.TILE_SIZE) * 5.5, float(C.TILE_SIZE) * 7.0, float(C.TILE_SIZE) * 0.5, C.DARK_GREEN, "ledge"))

    spawn_y_on_ground = main_ground_y_ref - 1.0
    enemy1_x_pos = seg2_start_x + seg2_width * 0.5
    patrol_data_e1 = {'x': seg2_start_x + float(C.TILE_SIZE), 'y': main_ground_y_ref - float(C.TILE_SIZE)*2, 'width': seg2_width - float(C.TILE_SIZE)*2, 'height': float(C.TILE_SIZE)*2.0}
    enemy_spawns_data.append(_create_enemy_spawn_data((enemy1_x_pos, spawn_y_on_ground), 'enemy_green', patrol_data_e1))

    enemy2_x_pos = enemy2_platform_x_start + enemy2_platform_width / 2.0
    enemy2_y_pos = enemy2_platform_y - 1.0
    enemy_spawns_data.append(_create_enemy_spawn_data((enemy2_x_pos, enemy2_y_pos), 'enemy_pink'))
    
    if seg3_width > float(C.TILE_SIZE):
        enemy3_x_pos = seg3_start_x + seg3_width * 0.3
        enemy_spawns_data.append(_create_enemy_spawn_data((enemy3_x_pos, spawn_y_on_ground), 'enemy_purple'))

    chest_x_midbottom = enemy2_platform_x_start + enemy2_platform_width - float(C.TILE_SIZE) * 1.5 
    chest_y_midbottom = enemy2_platform_y 
    collectible_spawns_data.append(_create_item_spawn_data('chest', (chest_x_midbottom, chest_y_midbottom)))


    level_min_y_abs_for_cam, level_max_y_abs_for_cam = _add_map_boundary_walls_data(platforms_data, map_total_width, ladders_data, hazards_data, initial_height, extra_sky_clearance=float(C.TILE_SIZE) * 10.0)
    level_bg_color = getattr(C, "LIGHT_BLUE", (173, 216, 230))

    return {
        "level_name": "cpu_extended",
        "platforms_list": platforms_data,
        "ladders_list": ladders_data,
        "hazards_list": hazards_data,
        "enemies_list": enemy_spawns_data,
        "items_list": collectible_spawns_data,
        "statues_list": statue_spawns_data,
        "player_start_pos_p1": player_spawn_pos,
        "player1_spawn_props": player_spawn_props,
        "level_pixel_width": map_total_width,
        "level_min_x_absolute": 0.0,
        "level_min_y_absolute": level_min_y_abs_for_cam,
        "level_max_y_absolute": level_max_y_abs_for_cam,
        "ground_level_y_ref": main_ground_y_ref,
        "ground_platform_height_ref": main_ground_segment_height_ref,
        "background_color": level_bg_color
    }

load_map_cpu = load_map_cpu_extended

#################### END OF FILE: levels.py ####################