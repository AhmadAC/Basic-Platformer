# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 2.0.2 (PySide6 Conversion - Added PNGs, Relative Paths)
Configuration constants for the Platformer Level Editor (PySide6 Version).
Tooltips have been removed.
"""
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any

# --- Add parent directory to sys.path ---
# This assumes your 'editor' directory is directly inside your project root.
# If 'constants.py' is in the project root, this setup should allow its import.
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir) # Assumes 'editor' is one level down

if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
    print(f"DEBUG editor_config: Added '{project_root_dir}' to sys.path for constants import.")

try:
    import constants as C # Your main game constants
    print(f"DEBUG editor_config: Successfully imported 'constants' module. TILE_SIZE from C: {getattr(C, 'TILE_SIZE', 'Not Found')}")
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{project_root_dir}'. Error: {e}")
    print(f"Current sys.path: {sys.path}")
    class FallbackConstants:
        TILE_SIZE = 32
        WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200); FPS = 60
        MAGENTA = (255, 0, 255)
        PURPLE_BACKGROUND = (75,0,130)
        MAPS_DIR = "maps" # Relative to project root
    C = FallbackConstants()
    print("CRITICAL editor_config.py: Using fallback constants. Ensure TILE_SIZE matches your game.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")


# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = 1380
EDITOR_SCREEN_INITIAL_HEIGHT = 820

# --- Section Preferred Sizes (Qt Layouts will manage actual sizes) ---
MENU_SECTION_PREFERRED_WIDTH = 250
ASSET_PALETTE_PREFERRED_WIDTH = 300

# --- Grid and Tile Size ---
BASE_GRID_SIZE = getattr(C, 'TILE_SIZE', 32)

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

# --- Minimap Configuration (if implemented as a custom Qt widget) ---
MINIMAP_PREFERRED_HEIGHT = 150
MINIMAP_BG_COLOR_TUPLE: Tuple[int,int,int] = (20, 20, 20)
MINIMAP_BORDER_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MINIMAP_CAMERA_VIEW_RECT_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MINIMAP_CAMERA_VIEW_RECT_ALPHA = 100

# --- Asset Palette ---
ASSET_THUMBNAIL_SIZE = getattr(C, 'TILE_SIZE', 32)# For display in the palette
ASSET_PALETTE_ICON_SIZE_W = ASSET_THUMBNAIL_SIZE
ASSET_PALETTE_ICON_SIZE_H = ASSET_THUMBNAIL_SIZE
ASSET_ITEM_BACKGROUND_SELECTED_COLOR_TUPLE: Tuple[int,int,int] = (70, 100, 150)

# --- File Paths and Extensions ---
# MAPS_DIRECTORY is relative to the project root (where constants.py is)
# This will be joined with project_root by resource_path or similar logic later if needed,
# or used directly if the editor scripts are run from the project root.
# For now, keep it as a simple string; actual path joining is handled by consuming code.
MAPS_DIRECTORY = getattr(C, 'MAPS_DIR', "maps") # From your constants or fallback
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

TS = BASE_GRID_SIZE # Alias for TILE_SIZE for asset definitions

# The 'source_file' paths here are relative to the project root.
# Example: if project root is 'Platformer/', and image is 'Platformer/characters/player1/__Idle.gif',
# then source_file should be 'characters/player1/__Idle.gif'
EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Spawns
    "player1_spawn": {"source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn", "category": "spawn", "name_in_palette": "Player 1 Spawn"},
    "player2_spawn": {"source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn", "category": "spawn", "name_in_palette": "Player 2 Spawn"},
    # Enemies
    "enemy_gray": {"source_file": "characters/gray/__Idle.gif", "game_type_id": "enemy_gray", "category": "enemy", "name_in_palette": "Enemy Gray"},
    "enemy_green": { "source_file": "characters/green/__Idle.gif", "game_type_id": "enemy_green", "category": "enemy", "name_in_palette": "Enemy Green"},
    "enemy_pink": { "source_file": "characters/pink/__Idle.gif", "game_type_id": "enemy_pink", "category": "enemy", "name_in_palette": "Enemy Pink"},
    "enemy_purple": { "source_file": "characters/purple/__Idle.gif", "game_type_id": "enemy_purple", "category": "enemy", "name_in_palette": "Enemy Purple"},
    "enemy_orange": { "source_file": "characters/orange/__Idle.gif", "game_type_id": "enemy_red", "category": "enemy", "name_in_palette": "Enemy Orange (Red)"}, # Clarify game ID if different
    "enemy_yellow": { "source_file": "characters/yellow/__Idle.gif", "game_type_id": "enemy_yellow", "category": "enemy", "name_in_palette": "Enemy Yellow"},
    # Items
    "chest": {"source_file": "characters/items/chest.gif", "game_type_id": "chest", "category": "item", "name_in_palette": "Chest"},
    # New PNG Assets
    "object_stone_idle": {
        "source_file": "characters/Stone/__Stone.png",
        "game_type_id": "object_stone_idle",
        "category": "object", # Or "tile", "decoration", etc.
        "name_in_palette": "Stone Block" # More descriptive
    },
    "object_stone_crouch": {
        "source_file": "characters/Stone/__StoneCrouch.png",
        "game_type_id": "object_stone_crouch",
        "category": "object",
        "name_in_palette": "Stone Crouch Block"
    },
    # Tiles - Full Size (Procedurally generated)
    "platform_wall_gray": {"surface_params": (TS, TS, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_wall_gray", "category": "tile", "name_in_palette": "Wall (Gray)"},
    "platform_ledge_green_full": {"surface_params": (TS, TS, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green", "category": "tile", "name_in_palette": "Ledge (Green)"},
    # Tiles - Thin Ledges (Procedurally generated)
    "platform_ledge_green_one_fourth": {"surface_params": (TS, TS // 4, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green_one_fourth", "category": "tile", "name_in_palette": "Ledge 1/4 (Green)"},
    "platform_ledge_gray_one_fourth": {"surface_params": (TS, TS // 4, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_ledge_gray_one_fourth", "category": "tile", "name_in_palette": "Ledge 1/4 (Gray)"},
    "platform_ledge_green_one_third": {"surface_params": (TS, TS // 3, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, "game_type_id": "platform_ledge_green_one_third", "category": "tile", "name_in_palette": "Ledge 1/3 (Green)"},
    "platform_ledge_gray_one_third": {"surface_params": (TS, TS // 3, getattr(C, 'GRAY', (128,128,128))), "colorable": True, "game_type_id": "platform_ledge_gray_one_third", "category": "tile", "name_in_palette": "Ledge 1/3 (Gray)"},
    # Tiles - Half Tiles (Procedurally generated)
    "platform_wall_gray_left_half": {"render_mode": "half_tile", "half_type": "left", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_left_half", "category": "tile", "name_in_palette": "Wall Left Half (Gray)"},
    "platform_wall_gray_right_half": {"render_mode": "half_tile", "half_type": "right", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_right_half", "category": "tile", "name_in_palette": "Wall Right Half (Gray)"},
    "platform_wall_gray_top_half": {"render_mode": "half_tile", "half_type": "top", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_top_half", "category": "tile", "name_in_palette": "Wall Top Half (Gray)"},
    "platform_wall_gray_bottom_half": {"render_mode": "half_tile", "half_type": "bottom", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_bottom_half", "category": "tile", "name_in_palette": "Wall Bottom Half (Gray)"},
    # Hazards
    "hazard_lava_tile": {"source_file": "characters/assets/lava.gif", "game_type_id": "hazard_lava", "category": "hazard", "name_in_palette": "Lava Tile"},
    # Tools (Generated icons)
    "tool_eraser": {"icon_type": "eraser", "base_color_tuple": getattr(C, 'RED', (255,0,0)), "game_type_id": "tool_eraser", "category": "tool", "name_in_palette": "Eraser Tool"},
    "platform_wall_gray_2x2_placer": {"icon_type": "2x2_placer", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "places_asset_key": "platform_wall_gray", "game_type_id": "tool_wall_2x2_placer", "category": "tool", "name_in_palette": "2x2 Wall Placer"},
    "tool_color_picker": {"icon_type": "color_swatch", "base_color_tuple": getattr(C, 'BLUE', (0,0,255)), "game_type_id": "tool_tile_color_picker", "category": "tool", "name_in_palette": "Color Picker Tool"},
}

# Define the order of categories for the asset palette UI
EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "hazard", "item", "object", "enemy", "spawn", "unknown"]

# Editable properties for specific game_type_id assets
EDITABLE_ASSET_VARIABLES: Dict[str, Dict[str, Any]] = {
    "player1_spawn": {
        "max_health": {"type": "int", "default": 100, "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": 300.0, "min": 50.0, "max": 1000.0, "label": "Move Speed"},
        "jump_strength": {"type": "float", "default": -900.0, "min": -1500.0, "max": -300.0, "label": "Jump Strength"}
    },
    "player2_spawn": { # Assuming similar properties to player1
        "max_health": {"type": "int", "default": 100, "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": 300.0, "min": 50.0, "max": 1000.0, "label": "Move Speed"},
        "jump_strength": {"type": "float", "default": -900.0, "min": -1500.0, "max": -300.0, "label": "Jump Strength"}
    },
    "enemy_green": {
        "patrol_range_tiles": {"type": "int", "default": 6, "min": 0, "max": 50, "label": "Patrol Range (Tiles)"},
        "move_speed": {"type": "float", "default": 80.0, "min": 10.0, "max": 300.0, "label": "Move Speed"},
        "health": {"type": "int", "default": 4, "min": 1, "max": 20, "label": "Health"},
        "can_fly": {"type": "bool", "default": False, "label": "Can Fly"}
    },
    "enemy_pink": {
        "health": {"type": "int", "default": 2, "min": 1, "max": 20, "label": "Health"},
        "move_speed": {"type": "float", "default": 120.0, "min": 10.0, "max": 300.0, "label": "Move Speed"},
        "patrol_behavior": {"type": "str", "default": "turn_on_edge", "options": ["turn_on_edge", "fall_off_edge", "hover_patrol"], "label": "Patrol Behavior"}
    },
    "enemy_purple": {
        "health": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "Health"},
        "attack_damage": {"type": "int", "default": 2, "min": 0, "max": 10, "label": "Attack Damage"},
         "can_fly": {"type": "bool", "default": True, "label": "Can Fly"}
    },
    "enemy_red": { # Changed from enemy_orange to match game_type_id consistently
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
    # Example properties for the new stone objects (if they need any)
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

# --- Qt Font Configuration (Examples) ---
FONT_FAMILY_UI_DEFAULT = "Arial" # Or a more common cross-platform font like "Segoe UI", "Helvetica", "sans-serif"
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

# --- Pygame Font Loading (Optional - for custom rendering to QPixmap if needed) ---
# This is generally not needed for a Qt application unless you have specific Pygame rendering routines.
PYGAME_FONTS: Dict[str, Any] = {"small": None, "medium": None, "large": None}
_pygame_initialized = False
try:
    import pygame
    pygame.init() # Initialize all Pygame modules, including font
    _pygame_initialized = True
    PYGAME_FONTS["small"] = pygame.font.Font(None, 20)
    PYGAME_FONTS["medium"] = pygame.font.Font(None, 24)
    PYGAME_FONTS["large"] = pygame.font.Font(None, 30)
    print("DEBUG CONFIG: Pygame and Pygame fonts initialized.")
except ImportError:
    print("WARNING CONFIG: Pygame not found. Pygame-dependent features (if any) will not be available.")
except pygame.error as e_font:
    print(f"ERROR CONFIG: Pygame font initialization error: {e_font}")
except Exception as e_font_generic:
    print(f"ERROR CONFIG: Generic error initializing Pygame components: {e_font_generic}")

# Status bar message timeout (in milliseconds for QStatusBar.showMessage)
STATUS_BAR_MESSAGE_TIMEOUT = 3000 # 3 seconds

# Logging configuration (These are defaults, can be overridden by editor_logging.py if that's used for setup)
LOG_LEVEL = "DEBUG" # "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
LOG_FILE_NAME = "editor_qt_debug.log" # Placed in 'logs' subdirectory relative to the editor script.