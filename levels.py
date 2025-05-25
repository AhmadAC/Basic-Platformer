# levels.py
# -*- coding: utf-8 -*-
"""
levels.py
Contains helper functions for creating map data structures.
Actual map data is now defined in individual .py files within named map folders
(e.g., maps/original/original.py).
"""
# version 2.1.0 (Refactored to be a helper module)
import random
from typing import List, Dict, Tuple, Any, Optional

# Game imports
import constants as C

FENCE_WIDTH = 8.0 
FENCE_HEIGHT = 15.0 
FENCE_COLOR = C.GRAY

# --- Helper functions (previously used by load_map_xxx functions) ---

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
                # This warning can be removed if all map files are updated
                # print(f"Levels.py Helper Warning: Object data {obj_data.get('type', 'Unknown type')} is using legacy x,y,w,h keys. Please migrate to 'rect'.")
                y, h = float(obj_data['y']), float(obj_data['h'])
                all_tops.append(y)
                all_bottoms.append(y + h)

    if not all_tops: 
        min_y_content = 0.0 - C.TILE_SIZE * 5 
        max_y_content = initial_screen_height_fallback
        # print(f"Warning: _calculate_content_extents found no measurable content. Using fallbacks: min_y={min_y_content}, max_y={max_y_content}")
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
    """
    min_y_content, max_y_content_original = _calculate_content_extents(
        platforms_data_list, ladders_data_list, hazards_data_list, initial_screen_height_fallback
    )

    level_min_y_abs_for_camera = min_y_content - float(C.TILE_SIZE) - extra_sky_clearance
    level_max_y_abs_for_camera = max_y_content_original
    
    overall_boundary_box_height_for_walls = (max_y_content_original + float(C.TILE_SIZE)) - level_min_y_abs_for_camera

    boundary_color = getattr(C, 'DARK_GRAY', (50,50,50))

    platforms_data_list.append(_create_platform_data(0.0, level_min_y_abs_for_camera, map_total_width, float(C.TILE_SIZE), boundary_color, "boundary_wall_top", {"is_boundary": True}))
    platforms_data_list.append(_create_platform_data(0.0, max_y_content_original, map_total_width, float(C.TILE_SIZE), boundary_color, "boundary_wall_bottom", {"is_boundary": True}))
    platforms_data_list.append(_create_platform_data(0.0, level_min_y_abs_for_camera, float(C.TILE_SIZE), overall_boundary_box_height_for_walls, boundary_color, "boundary_wall_left", {"is_boundary": True}))
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
    if patrol_rect_data_dict:
        data['patrol_rect_data'] = patrol_rect_data_dict
    return data

def _create_item_spawn_data(item_type_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'type': item_type_str, 'pos': pos_tuple, 'properties': props or {}}

def _create_statue_spawn_data(statue_id_str: str, pos_tuple: Tuple[float,float], props: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return {'id': statue_id_str, 'pos': pos_tuple, 'properties': props or {}}

# --- Example of a programmatically generated fallback map ---
# This could be used if LevelLoader fails to find any map.
def load_map_level_default() -> Dict[str, Any]:
    """ Returns data for a very basic default level. """
    initial_height = float(C.TILE_SIZE * 15)
    map_total_width = float(C.TILE_SIZE * 25)
    platforms_data: List[Dict[str, Any]] = []
    
    main_ground_y = initial_height - float(C.TILE_SIZE)
    platforms_data.append(_create_platform_data(0.0, main_ground_y, map_total_width, float(C.TILE_SIZE), C.GRAY, "ground"))
    platforms_data.append(_create_platform_data(float(C.TILE_SIZE) * 5, main_ground_y - float(C.TILE_SIZE) * 3, float(C.TILE_SIZE) * 5, float(C.TILE_SIZE) * 0.5, C.DARK_GREEN, "ledge"))
    
    player_spawn_pos = (float(C.TILE_SIZE) * 2.0, main_ground_y - 1.0)
    
    level_min_y_abs, level_max_y_abs = _add_map_boundary_walls_data(platforms_data, map_total_width, [], [], initial_height)

    return {
        "level_name": "level_default",
        "platforms_list": platforms_data,
        "ladders_list": [],
        "hazards_list": [],
        "enemies_list": [],
        "items_list": [],
        "statues_list": [],
        "player_start_pos_p1": player_spawn_pos,
        "player1_spawn_props": {},
        "level_pixel_width": map_total_width,
        "level_min_x_absolute": 0.0,
        "level_min_y_absolute": level_min_y_abs,
        "level_max_y_absolute": level_max_y_abs,
        "ground_level_y_ref": main_ground_y,
        "ground_platform_height_ref": float(C.TILE_SIZE),
        "background_color": C.LIGHT_BLUE
    }

if __name__ == '__main__':
    print("levels.py now primarily contains helper functions for map data creation.")
    print("To test individual map loading, run level_loader.py or the main game.")
    print("Testing load_map_level_default():")
    default_map_data = load_map_level_default()
    if default_map_data:
        print(f"  Default map name: {default_map_data.get('level_name')}")
        print(f"  Number of platforms: {len(default_map_data.get('platforms_list', []))}")
    else:
        print("  Failed to load default map data.")