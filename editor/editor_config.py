# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 2.1.0 (Feature Rich Update Config)
Configuration constants for the Platformer Level Editor (PySide6 Version).
- Added config for custom image objects and trigger squares.
- Defined MINIMAP_CATEGORY_COLORS for better minimap visuals.
"""
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any

from PySide6.QtGui import QColor # For MINIMAP_CATEGORY_COLORS

# --- Add parent directory to sys.path ---
current_script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
project_root_dir = os.path.dirname(current_script_dir)

if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    import constants as C 
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{project_root_dir}'. Error: {e}")
    class FallbackConstants: 
        TILE_SIZE = 40 
        WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200); FPS = 60; MAGENTA = (255, 0, 255)
        PURPLE_BACKGROUND = (75,0,130); MAPS_DIR = "maps" 
        EDITOR_SCREEN_INITIAL_WIDTH = 1000; EDITOR_SCREEN_INITIAL_HEIGHT = 800
        LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"; GAME_LEVEL_FILE_EXTENSION = ".py"
        PLAYER_MAX_HEALTH = 100; PLAYER_RUN_SPEED_LIMIT = 7.0; PLAYER_JUMP_STRENGTH = -15.0
        ENEMY_RUN_SPEED_LIMIT = 5.0; ENEMY_MAX_HEALTH = 80; ENEMY_ATTACK_DAMAGE = 10
    C = FallbackConstants() # type: ignore
    print("CRITICAL editor_config.py: Using fallback constants.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")

# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = getattr(C, 'EDITOR_SCREEN_INITIAL_WIDTH', 1380) 
EDITOR_SCREEN_INITIAL_HEIGHT = getattr(C, 'EDITOR_SCREEN_INITIAL_HEIGHT', 820)

# --- Section Preferred Sizes ---
MENU_SECTION_PREFERRED_WIDTH = 250 # Not currently used explicitly by provided code
ASSET_PALETTE_PREFERRED_WIDTH = 300

# --- Grid and Tile Size ---
BASE_GRID_SIZE = getattr(C, 'TILE_SIZE', 40) 

# --- Camera Control & Zoom ---
KEY_PAN_SPEED_UNITS_PER_SECOND = 800
EDGE_SCROLL_ZONE_THICKNESS = 25
EDGE_SCROLL_SPEED_UNITS_PER_SECOND = 300
CONTROLLER_CAMERA_PAN_SPEED_PIXELS = 30 
MIN_ZOOM_LEVEL = 0.1
MAX_ZOOM_LEVEL = 8.0
ZOOM_FACTOR_INCREMENT = 1.2
ZOOM_FACTOR_DECREMENT = 1 / 1.2

# --- Map View Appearance ---
MAP_VIEW_GRID_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_SELECTION_RECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MAP_VIEW_HOVER_RECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))
CURSOR_ASSET_ALPHA = 100
MAP_VIEW_CONTROLLER_CURSOR_COLOR_TUPLE: Tuple[int,int,int,int] = (0, 200, 255, 180) 

# --- Controller Focus Styling ---
PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER = "2px solid orange"
ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER = "2px solid lightgreen"
CONTROLLER_POLL_INTERVAL_MS = 16 

# --- Minimap Configuration ---
MINIMAP_ENABLED = True
MINIMAP_DEFAULT_WIDTH = 200
MINIMAP_DEFAULT_HEIGHT = 150
MINIMAP_BACKGROUND_COLOR_TUPLE: Tuple[int,int,int,int] = (40, 40, 50, 230) 
MINIMAP_BORDER_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MINIMAP_VIEW_RECT_FILL_COLOR_TUPLE: Tuple[int,int,int,int] = (255, 255, 0, 70) 
MINIMAP_VIEW_RECT_BORDER_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MINIMAP_OBJECT_REPRESENTATION_SIZE_PX = 2.0 # For small objects like characters/items
MINIMAP_UPDATE_INTERVAL_MS = 50
MINIMAP_CATEGORY_COLORS: Dict[str, QColor] = {
    "spawn": QColor(0, 255, 0, 180),    # Green
    "enemy": QColor(255, 0, 0, 180),    # Red
    "item": QColor(255, 255, 0, 180),   # Yellow
    "object": QColor(0, 0, 255, 180),   # Blue (e.g., stones)
    "hazard": QColor(255, 100, 0, 200), # Orange/Red (e.g., lava)
    "tile": QColor(150, 150, 150, 200), # Default for tiles
    "background_tile": QColor(100, 100, 120, 150), # Specific for background tiles
    "custom_image": QColor(0, 150, 150, 180), # Teal for custom images
    "trigger": QColor(200, 0, 200, 150),      # Purple for triggers
    "trigger_image": QColor(180, 50, 180, 170), # Slightly different for triggers with images
    "unknown": QColor(255, 0, 255, 150) # Magenta for unknown
}


# --- Asset Palette ---
ASSET_THUMBNAIL_SIZE = getattr(C, 'TILE_SIZE', 40)
ASSET_PALETTE_ICON_SIZE_W = ASSET_THUMBNAIL_SIZE
ASSET_PALETTE_ICON_SIZE_H = ASSET_THUMBNAIL_SIZE
ASSET_ITEM_BACKGROUND_SELECTED_COLOR_TUPLE: Tuple[int,int,int] = (70, 100, 150)

# --- File Paths and Extensions ---
MAPS_DIRECTORY = getattr(C, 'MAPS_DIR', "maps") # Relative to project root
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = getattr(C, "LEVEL_EDITOR_SAVE_FORMAT_EXTENSION", ".json")
GAME_LEVEL_FILE_EXTENSION = getattr(C, "GAME_LEVEL_FILE_EXTENSION", ".py")

# --- Custom Asset Identifiers ---
CUSTOM_IMAGE_ASSET_KEY = "custom_image_object" # Used as asset_editor_key and game_type_id for these
TRIGGER_SQUARE_ASSET_KEY = "trigger_square"     # Used as asset_editor_key for palette
TRIGGER_SQUARE_GAME_TYPE_ID = "trigger_square_link" # Used as game_type_id for properties
CUSTOM_ASSET_PALETTE_PREFIX = "custom:" # Prefix for custom assets listed in palette


TS = BASE_GRID_SIZE 

EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Spawns
    "player1_spawn": {"source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn", "category": "spawn", "name_in_palette": "Player 1 Spawn"},
    
    # Tiles
    "platform_wall_gray": {"surface_params": (TS, TS, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_wall_gray", "category": "tile", "name_in_palette": "Wall (Gray)"},
    
    # Hazards
    "hazard_lava_tile": {"source_file": "characters/assets/lava.gif", "game_type_id": "hazard_lava", "category": "hazard", "name_in_palette": "Lava Tile"},
    
    # Background Tiles
    "background_dark_fill": {"surface_params": (TS * 5, TS * 5, getattr(C, 'DARK_GRAY', (50, 50, 50))), "colorable": True, "game_type_id": "background_dark_fill", "category": "background_tile", "name_in_palette": "BG Dark Fill (5x5)"},

    # NEW: Sample Enemy Asset (adjust 'source_file' to your actual image)
    "enemy_basic_grunt": {
        "source_file": "characters/enemies/grunt_idle_placeholder.png", # Replace with actual path
        "game_type_id": "enemy_grunt", # Unique ID for game logic
        "category": "enemy",
        "name_in_palette": "Grunt Enemy"
    },
    # Add more enemy definitions here, e.g.:
    # "enemy_flyer": {
    #     "source_file": "characters/enemies/flyer.png",
    #     "game_type_id": "enemy_flyer",
    #     "category": "enemy",
    #     "name_in_palette": "Flying Enemy"
    # },

    # Items (Example)
    # "item_coin": {
    #     "source_file": "items/coin.png", 
    #     "game_type_id": "coin",
    #     "category": "item",
    #     "name_in_palette": "Coin"
    # },

    # Logic
    TRIGGER_SQUARE_ASSET_KEY: { 
        "icon_type": "generic_square_icon", 
        "base_color_tuple": (100, 100, 255, 150), 
        "game_type_id": TRIGGER_SQUARE_GAME_TYPE_ID, 
        "category": "logic", 
        "name_in_palette": "Trigger Square"
    },

    # Tools
    "tool_eraser": {"icon_type": "eraser", "base_color_tuple": getattr(C, 'RED', (255,0,0)), "game_type_id": "tool_eraser", "category": "tool", "name_in_palette": "Eraser Tool"},
    "platform_wall_gray_2x2_placer": {"icon_type": "2x2_placer", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "places_asset_key": "platform_wall_gray", "game_type_id": "tool_wall_2x2_placer", "category": "tool", "name_in_palette": "2x2 Wall Placer"},
    "tool_color_picker": {"icon_type": "color_swatch", "base_color_tuple": getattr(C, 'BLUE', (0,0,255)), "game_type_id": "tool_tile_color_picker", "category": "tool", "name_in_palette": "Color Picker Tool"},
}

EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "background_tile", "hazard", "item", "object", "enemy", "spawn", "logic", "Custom", "unknown"]

EDITABLE_ASSET_VARIABLES: Dict[str, Dict[str, Any]] = {
    "player1_spawn": {
        "max_health": {"type": "int", "default": getattr(C, 'PLAYER_MAX_HEALTH', 100), "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 50, "min": 50.0, "max": 1000.0, "label": "Move Speed (units/s)"}, 
        "jump_strength": {"type": "float", "default": getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 60, "min": -1500.0, "max": -300.0, "label": "Jump Strength (units/s)"} 
    },
    # Properties for the sample enemy
    "enemy_grunt": {
        "max_health": {"type": "int", "default": getattr(C, 'ENEMY_MAX_HEALTH', 80), "min": 1, "max": 500, "label": "Max Health"},
        "move_speed": {"type": "float", "default": getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 3.0) * 50, "min": 10.0, "max": 500.0, "label": "Move Speed (units/s)"},
        "attack_damage": {"type": "int", "default": getattr(C, 'ENEMY_ATTACK_DAMAGE', 10), "min": 0, "max": 100, "label": "Attack Damage"},
        "patrol_range": {"type": "int", "default": 200, "min": 0, "max": 1000, "label": "Patrol Range (px)"}
    },
    # Add more enemy property definitions here, matching their game_type_id

    CUSTOM_IMAGE_ASSET_KEY: { 
        "is_background": {"type": "bool", "default": False, "label": "Is Background Image"},
        "is_obstacle": {"type": "bool", "default": True, "label": "Is Obstacle"},
        "destructible": {"type": "bool", "default": False, "label": "Is Destructible"},
        "health": {"type": "int", "default": 100, "min": 0, "max": 1000, "label": "Health (if Destructible)"},
    },
    TRIGGER_SQUARE_GAME_TYPE_ID: { 
        "visible": {"type": "bool", "default": True, "label": "Visible in Game"},
        "fill_color_rgba": {"type": "tuple_color_rgba", "default": (100, 100, 255, 100), "label": "Fill Color (RGBA)"},
        "image_in_square": {"type": "image_path_custom", "default": "", "label": "Image in Square"},
        "linked_map_name": {"type": "str", "default": "", "label": "Linked Map Name"},
    },
}

def get_default_properties_for_asset(game_type_id: str) -> Dict[str, Any]:
    """Helper to get default properties for a given game_type_id."""
    defaults = {}
    if game_type_id in EDITABLE_ASSET_VARIABLES:
        for prop_name, definition in EDITABLE_ASSET_VARIABLES[game_type_id].items():
            defaults[prop_name] = definition["default"]
    return defaults


# --- Map Defaults ---
DEFAULT_MAP_WIDTH_TILES = 40
DEFAULT_MAP_HEIGHT_TILES = 25
DEFAULT_BACKGROUND_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))

# --- Qt Font Configuration ---
FONT_FAMILY_UI_DEFAULT = "Arial"
FONT_SIZE_SMALL = 9; FONT_SIZE_MEDIUM = 10; FONT_SIZE_LARGE = 12
FONT_CATEGORY_TITLE_SIZE = 11; FONT_CATEGORY_TITLE_BOLD = True

# --- Color Presets ---
COLOR_PICKER_PRESETS: Dict[str, Tuple[int,int,int]] = {
    "Light Blue": getattr(C, 'LIGHT_BLUE', (173,216,230)), "White": getattr(C, 'WHITE', (255,255,255)),
    "Magenta": getattr(C, 'MAGENTA', (255, 0, 255))
}

STATUS_BAR_MESSAGE_TIMEOUT = 3000 

# Logging configuration
LOG_LEVEL = "DEBUG" 
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
LOG_FILE_NAME = "editor_qt_debug.log" 