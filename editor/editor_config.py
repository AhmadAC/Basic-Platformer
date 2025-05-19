#################### START OF FILE: editor\editor_config.py ####################

# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 2.0.3 
Configuration constants for the Platformer Level Editor (PySide6 Version).
"""
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any

# --- Add parent directory to sys.path ---
# This ensures that 'constants.py' (from the project root) can be imported.
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)

if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
    print(f"DEBUG editor_config: Added '{project_root_dir}' to sys.path for constants import.")

try:
    import constants as C 
    print(f"DEBUG editor_config: Successfully imported 'constants' module. TILE_SIZE from C: {getattr(C, 'TILE_SIZE', 'Not Found')}")
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{project_root_dir}'. Error: {e}")
    print(f"Current sys.path: {sys.path}")
    class FallbackConstants: # Define a fallback if main constants cannot be loaded
        TILE_SIZE = 40 # Ensure this matches your game's default
        WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200); FPS = 60
        MAGENTA = (255, 0, 255)
        PURPLE_BACKGROUND = (75,0,130)
        MAPS_DIR = "maps" # Relative to project root
        EDITOR_SCREEN_INITIAL_WIDTH = 1000 # Example fallback
    C = FallbackConstants()
    print("CRITICAL editor_config.py: Using fallback constants. Ensure TILE_SIZE matches your game.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")


# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = getattr(C, 'EDITOR_SCREEN_INITIAL_WIDTH', 1380) # Use from C if defined, else default
EDITOR_SCREEN_INITIAL_HEIGHT = getattr(C, 'EDITOR_SCREEN_INITIAL_HEIGHT', 820) # Use from C if defined, else default

# --- Section Preferred Sizes (Qt Layouts will manage actual sizes) ---
MENU_SECTION_PREFERRED_WIDTH = 250
ASSET_PALETTE_PREFERRED_WIDTH = 300

# --- Grid and Tile Size ---
BASE_GRID_SIZE = getattr(C, 'TILE_SIZE', 40) # Default to 40 if not in C

# --- Camera Control & Zoom (for QGraphicsView) ---
KEY_PAN_SPEED_UNITS_PER_SECOND = 400
EDGE_SCROLL_ZONE_THICKNESS = 25
EDGE_SCROLL_SPEED_UNITS_PER_SECOND = 300

MIN_ZOOM_LEVEL = 0.1
MAX_ZOOM_LEVEL = 8.0
ZOOM_FACTOR_INCREMENT = 1.2
ZOOM_FACTOR_DECREMENT = 1 / 1.2

# --- Map View Appearance (for QGraphicsView/Scene custom drawing) ---
MAP_VIEW_GRID_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_SELECTION_RECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MAP_VIEW_HOVER_RECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))
CURSOR_ASSET_ALPHA = 100 # Opacity for cursor preview (0-255)

# --- Minimap Configuration ---
MINIMAP_ENABLED = True
MINIMAP_DEFAULT_WIDTH = 200
MINIMAP_DEFAULT_HEIGHT = 150
MINIMAP_BACKGROUND_COLOR_TUPLE: Tuple[int,int,int,int] = (40, 40, 50, 230) # RGBA
MINIMAP_BORDER_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE: Tuple[int,int,int,int] = (255, 255, 0, 70) # Yellow, semi-transparent
MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MINIMAP_OBJECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_GRAY', (200,200,200))
MINIMAP_UPDATE_INTERVAL_MS = 50

# --- Asset Palette ---
ASSET_THUMBNAIL_SIZE = getattr(C, 'TILE_SIZE', 40)
ASSET_PALETTE_ICON_SIZE_W = ASSET_THUMBNAIL_SIZE
ASSET_PALETTE_ICON_SIZE_H = ASSET_THUMBNAIL_SIZE
ASSET_ITEM_BACKGROUND_SELECTED_COLOR_TUPLE: Tuple[int,int,int] = (70, 100, 150)

# --- File Paths and Extensions ---
# MAPS_DIRECTORY is now robustly determined by C.MAPS_DIR.
MAPS_DIRECTORY = getattr(C, 'MAPS_DIR', os.path.join(project_root_dir, "maps")) # Ensure fallback if C.MAPS_DIR missing
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

TS = BASE_GRID_SIZE # Alias for TILE_SIZE for asset definitions

# 'source_file' paths are relative to the project root.
EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Spawns
    "player1_spawn": {"source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn", "category": "spawn", "name_in_palette": "Player 1 Spawn"},
    "player2_spawn": {"source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn", "category": "spawn", "name_in_palette": "Player 2 Spawn"},
    # Enemies
    "enemy_gray": {"source_file": "characters/gray/__Idle.gif", "game_type_id": "enemy_gray", "category": "enemy", "name_in_palette": "Enemy Gray"},
    "enemy_green": { "source_file": "characters/green/__Idle.gif", "game_type_id": "enemy_green", "category": "enemy", "name_in_palette": "Enemy Green"},
    "enemy_pink": { "source_file": "characters/pink/__Idle.gif", "game_type_id": "enemy_pink", "category": "enemy", "name_in_palette": "Enemy Pink"},
    "enemy_purple": { "source_file": "characters/purple/__Idle.gif", "game_type_id": "enemy_purple", "category": "enemy", "name_in_palette": "Enemy Purple"},
    "enemy_orange": { "source_file": "characters/orange/__Idle.gif", "game_type_id": "enemy_red", "category": "enemy", "name_in_palette": "Enemy Orange (Red)"},
    "enemy_yellow": { "source_file": "characters/yellow/__Idle.gif", "game_type_id": "enemy_yellow", "category": "enemy", "name_in_palette": "Enemy Yellow"},
    # Items
    "chest": {"source_file": "characters/items/chest.gif", "game_type_id": "chest", "category": "item", "name_in_palette": "Chest"},
    # New PNG Assets (Stone objects)
    "object_stone_idle": {"source_file": "characters/Stone/__Stone.png", "game_type_id": "object_stone_idle", "category": "object", "name_in_palette": "Stone Block"},
    "object_stone_crouch": {"source_file": "characters/Stone/__StoneCrouch.png", "game_type_id": "object_stone_crouch", "category": "object", "name_in_palette": "Stone Crouch Block"},
    # Tiles - Full Size (Procedurally generated in editor_assets.py)
    "platform_wall_gray": {"surface_params": (TS, TS, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_wall_gray", "category": "tile", "name_in_palette": "Wall (Gray)"},
    "platform_ledge_green_full": {"surface_params": (TS, TS, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green", "category": "tile", "name_in_palette": "Ledge (Green)"},
    # Tiles - Thin Ledges
    "platform_ledge_green_one_fourth": {"surface_params": (TS, TS // 4, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green_one_fourth", "category": "tile", "name_in_palette": "Ledge 1/4 (Green)"},
    "platform_ledge_gray_one_fourth": {"surface_params": (TS, TS // 4, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_ledge_gray_one_fourth", "category": "tile", "name_in_palette": "Ledge 1/4 (Gray)"},
    "platform_ledge_green_one_third": {"surface_params": (TS, TS // 3, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green_one_third", "category": "tile", "name_in_palette": "Ledge 1/3 (Green)"},
    "platform_ledge_gray_one_third": {"surface_params": (TS, TS // 3, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_ledge_gray_one_third", "category": "tile", "name_in_palette": "Ledge 1/3 (Gray)"},
    # Tiles - Half Tiles
    "platform_wall_gray_left_half": {"render_mode": "half_tile", "half_type": "left", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_left_half", "category": "tile", "name_in_palette": "Wall Left Half (Gray)"},
    "platform_wall_gray_right_half": {"render_mode": "half_tile", "half_type": "right", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_right_half", "category": "tile", "name_in_palette": "Wall Right Half (Gray)"},
    "platform_wall_gray_top_half": {"render_mode": "half_tile", "half_type": "top", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_top_half", "category": "tile", "name_in_palette": "Wall Top Half (Gray)"},
    "platform_wall_gray_bottom_half": {"render_mode": "half_tile", "half_type": "bottom", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_bottom_half", "category": "tile", "name_in_palette": "Wall Bottom Half (Gray)"},
    # Hazards
    "hazard_lava_tile": {"source_file": "characters/assets/lava.gif", "game_type_id": "hazard_lava", "category": "hazard", "name_in_palette": "Lava Tile"},
    # Tools (Generated icons in editor_assets.py)
    "tool_eraser": {"icon_type": "eraser", "base_color_tuple": getattr(C, 'RED', (255,0,0)), "game_type_id": "tool_eraser", "category": "tool", "name_in_palette": "Eraser Tool"},
    "platform_wall_gray_2x2_placer": {"icon_type": "2x2_placer", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "places_asset_key": "platform_wall_gray", "game_type_id": "tool_wall_2x2_placer", "category": "tool", "name_in_palette": "2x2 Wall Placer"},
    "tool_color_picker": {"icon_type": "color_swatch", "base_color_tuple": getattr(C, 'BLUE', (0,0,255)), "game_type_id": "tool_tile_color_picker", "category": "tool", "name_in_palette": "Color Picker Tool"},
}

EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "hazard", "item", "object", "enemy", "spawn", "unknown"]

EDITABLE_ASSET_VARIABLES: Dict[str, Dict[str, Any]] = {
    "player1_spawn": {
        "max_health": {"type": "int", "default": getattr(C, 'PLAYER_MAX_HEALTH', 100), "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 50, "min": 50.0, "max": 1000.0, "label": "Move Speed (units/s)"}, # Example scaling
        "jump_strength": {"type": "float", "default": getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 60, "min": -1500.0, "max": -300.0, "label": "Jump Strength (units/s)"} # Example scaling
    },
    "player2_spawn": {
        "max_health": {"type": "int", "default": getattr(C, 'PLAYER_MAX_HEALTH', 100), "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 50, "min": 50.0, "max": 1000.0, "label": "Move Speed (units/s)"},
        "jump_strength": {"type": "float", "default": getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 60, "min": -1500.0, "max": -300.0, "label": "Jump Strength (units/s)"}
    },
    # ... (other enemy and item properties as before) ...
    "enemy_green": {
        "patrol_range_tiles": {"type": "int", "default": 6, "min": 0, "max": 50, "label": "Patrol Range (Tiles)"},
        "move_speed": {"type": "float", "default": getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 20, "min": 10.0, "max": 300.0, "label": "Move Speed (units/s)"},
        "health": {"type": "int", "default": getattr(C, 'ENEMY_MAX_HEALTH', 80)//20, "min": 1, "max": 20, "label": "Health"},
        "can_fly": {"type": "bool", "default": False, "label": "Can Fly"}
    },
    "enemy_pink": {
        "health": {"type": "int", "default": 2, "min": 1, "max": 20, "label": "Health"},
        "move_speed": {"type": "float", "default": 120.0, "min": 10.0, "max": 300.0, "label": "Move Speed"},
        "patrol_behavior": {"type": "str", "default": "turn_on_edge", "options": ["turn_on_edge", "fall_off_edge", "hover_patrol"], "label": "Patrol Behavior"}
    },
    "enemy_purple": {
        "health": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "Health"},
        "attack_damage": {"type": "int", "default": getattr(C, 'ENEMY_ATTACK_DAMAGE',10)//2, "min": 0, "max": 10, "label": "Attack Damage"},
         "can_fly": {"type": "bool", "default": True, "label": "Can Fly"}
    },
    "enemy_red": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20, "label": "Health"},
        "is_aggressive": {"type": "bool", "default": True, "label": "Is Aggressive"},
        "aggro_range_tiles": {"type": "int", "default": 8, "min":0, "max": 30, "label": "Aggro Range (Tiles)"}
    },
    "enemy_yellow": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20, "label": "Health"},
        "move_speed": {"type": "float", "default": 150.0, "min": 10.0, "max": 400.0, "label": "Move Speed"},
    },
    "enemy_gray": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20, "label": "Health"},
        "move_speed": {"type": "float", "default": 150.0, "min": 10.0, "max": 400.0, "label": "Move Speed"},
    },
    "chest": {
        "item_type": {"type": "str", "default": "coin", "options": ["coin", "gem", "potion_health", "potion_speed"], "label": "Item Type"},
        "item_quantity": {"type": "int", "default": 1, "min": 1, "max": 100, "label": "Item Quantity"}
    },
    "object_stone_idle": {
        "destructible": {"type": "bool", "default": False, "label": "Is Destructible"},
        "hardness": {"type": "int", "default": 1, "min": 1, "max": 10, "label": "Hardness"}
    },
    "object_stone_crouch": {
        "is_passable_from_below": {"type": "bool", "default": False, "label": "Passable From Below"}
    }
}

# --- Map Defaults ---
DEFAULT_MAP_WIDTH_TILES = 40
DEFAULT_MAP_HEIGHT_TILES = 25
DEFAULT_BACKGROUND_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))
# In editor_config.py
MINIMAP_OBJECT_REPRESENTATION_SIZE_PX = 2.0 # Or 1.0 or 3.0, experiment for best visibility
# --- Qt Font Configuration (Examples) ---
FONT_FAMILY_UI_DEFAULT = "Arial"
FONT_SIZE_SMALL = 9
FONT_SIZE_MEDIUM = 10
FONT_SIZE_LARGE = 12
FONT_CATEGORY_TITLE_SIZE = 11
FONT_CATEGORY_TITLE_BOLD = True

# --- Color Presets for QColorDialog or custom color pickers ---
COLOR_PICKER_PRESETS: Dict[str, Tuple[int,int,int]] = {
    "Light Blue": getattr(C, 'LIGHT_BLUE', (173,216,230)), "White": getattr(C, 'WHITE', (255,255,255)),
    "Black": getattr(C, 'BLACK', (0,0,0)), "Gray": getattr(C, 'GRAY', (128,128,128)),
    "Dark Gray": getattr(C, 'DARK_GRAY', (50,50,50)), "Red": getattr(C, 'RED', (255,0,0)),
    "Green": getattr(C, 'GREEN', (0,255,0)), "Blue": getattr(C, 'BLUE', (0,0,255)),
    "Yellow": getattr(C, 'YELLOW', (255,255,0)), "Orange": getattr(C, 'ORANGE_RED', (255,69,0)),
    "Purple": (128, 0, 128), "Brown": (139, 69, 19),
    "Dark Green": getattr(C, 'DARK_GREEN', (0,100,0)), "Sky Blue": (100, 150, 255),
    "Dark Purple BG": getattr(C, 'PURPLE_BACKGROUND', (75,0,130)),
    "Sand": (244,164,96),
    "Magenta": getattr(C, 'MAGENTA', (255, 0, 255))
}

# Status bar message timeout (in milliseconds for QStatusBar.showMessage)
STATUS_BAR_MESSAGE_TIMEOUT = 3000 # 3 seconds

# Logging configuration
LOG_LEVEL = "DEBUG"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
LOG_FILE_NAME = "editor_qt_debug.log"

#################### END OF FILE: editor\editor_config.py ####################