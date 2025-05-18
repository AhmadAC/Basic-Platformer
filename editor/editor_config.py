# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.10 (Added Asset Properties Editor Config)
Configuration constants for the Platformer Level Editor.
"""
import pygame
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any

# --- Add parent directory to sys.path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    import constants as C # Your main game constants
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{parent_dir}'. Error: {e}")
    class FallbackConstants: # Define essential fallbacks if main constants are missing
        TILE_SIZE = 32 # CRITICAL: Must match your game's TILE_SIZE
        WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200); FPS = 60
        MAGENTA = (255, 0, 255)
        PURPLE_BACKGROUND = (75,0,130) # Example
        MAPS_DIR = "maps" # Fallback maps directory
    C = FallbackConstants()
    print("CRITICAL editor_config.py: Using fallback constants. Ensure TILE_SIZE matches your game.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")


# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = 1280
EDITOR_SCREEN_INITIAL_HEIGHT = 720

MENU_SECTION_WIDTH = 280
MENU_SECTION_HEIGHT = 250 # Approx height for menu content area

ASSET_PALETTE_SECTION_WIDTH = 250 # Increased width for potential dropdown
ASSET_PALETTE_OPTIONS_DROPDOWN_WIDTH = 200 # Width of the dropdown itself
ASSET_PALETTE_OPTIONS_DROPDOWN_ITEM_HEIGHT = 30 # Height of each item in the dropdown
ASSET_PALETTE_HEADER_AREA_HEIGHT = 40 # Space at the top of asset palette for the options dropdown button


SECTION_PADDING = 10 # Padding around UI sections

# Default dimensions for map view when editor starts
MAP_VIEW_SECTION_DEFAULT_WIDTH = EDITOR_SCREEN_INITIAL_WIDTH - MENU_SECTION_WIDTH - ASSET_PALETTE_SECTION_WIDTH - (SECTION_PADDING * 3)
MAP_VIEW_SECTION_DEFAULT_HEIGHT = EDITOR_SCREEN_INITIAL_HEIGHT - (SECTION_PADDING * 2)


# --- Camera Control ---
KEY_PAN_SPEED_PIXELS_PER_SECOND = 300
EDGE_SCROLL_ZONE_THICKNESS = 30
EDGE_SCROLL_SPEED_PIXELS_PER_SECOND = 250
CAMERA_MOMENTUM_INITIAL_MULTIPLIER = 1.5
CAMERA_MOMENTUM_DAMPING_FACTOR = 0.96
CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD = 5.0
CAMERA_MOMENTUM_BOUNDARY_DAMP_FACTOR = 0.5

# --- Cursor Asset Visuals ---
CURSOR_ASSET_ALPHA = 128 # 50% transparent (0-255)
CURSOR_ASSET_HUE_COLOR = (255, 0, 0, 70) # RGBA for red hue overlay (adjust alpha for strength of hue)


# --- Minimap Configuration ---
MINIMAP_AREA_HEIGHT = 120
MINIMAP_PADDING = 5
MINIMAP_BG_COLOR: Tuple[int,int,int] = (10, 10, 10)
MINIMAP_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MINIMAP_CAMERA_VIEW_RECT_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MINIMAP_CAMERA_VIEW_RECT_ALPHA = 100

# --- UI Element Sizes & Colors ---
BUTTON_WIDTH_STANDARD = 200
BUTTON_HEIGHT_STANDARD = 50
BUTTON_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
BUTTON_COLOR_NORMAL: Tuple[int,int,int] = getattr(C, 'BLUE', (0,0,255))
BUTTON_COLOR_HOVER: Tuple[int,int,int] = getattr(C, 'GREEN', (0,255,0))
BUTTON_COLOR_BORDER: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
BUTTON_BORDER_WIDTH = 2

ASSET_THUMBNAIL_MAX_WIDTH = getattr(C, 'TILE_SIZE', 32) * 2
ASSET_THUMBNAIL_MAX_HEIGHT = getattr(C, 'TILE_SIZE', 32) * 2
ASSET_PALETTE_ITEM_PADDING = 5
ASSET_PALETTE_BG_COLOR: Tuple[int,int,int] = (30, 30, 30)
ASSET_PALETTE_CATEGORY_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
ASSET_PALETTE_TOOLTIP_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_GRAY', (200,200,200))
ASSET_PALETTE_HOVER_BG_COLOR: Tuple[int,int,int] = (50, 80, 50)
ASSET_PALETTE_BOTTOM_OVERHANG_PX = 72
ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET = 2


ASSET_PALETTE_SCROLL_KICK_MULTIPLIER = 2000.0
ASSET_PALETTE_FLING_DAMPING_FACTOR = 0.92
ASSET_PALETTE_FLING_MIN_SPEED_THRESHOLD = 50.0
ASSET_PALETTE_MAX_MOMENTUM = 2000.0

MAP_VIEW_GRID_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))

DIALOG_BG_COLOR: Tuple[int,int,int] = (60, 60, 70)
DIALOG_INPUT_BOX_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_INPUT_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
DIALOG_PROMPT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_CURSOR_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
DIALOG_DROPDOWN_BG_COLOR: Tuple[int,int,int] = (50,50,60) # For dropdowns within dialogs
DIALOG_DROPDOWN_HOVER_COLOR: Tuple[int,int,int] = (70,70,90)
DIALOG_DROPDOWN_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_LABEL_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_GRAY', (200,200,200))


COLOR_PICKER_BUTTON_SIZE = 40
COLOR_PICKER_PADDING = 8
COLOR_PICKER_COLS = 5
COLOR_PICKER_BG_COLOR: Tuple[int,int,int] = (40, 40, 50)
COLOR_PICKER_TITLE_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
COLOR_PICKER_HOVER_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))

MAPS_DIRECTORY = C.MAPS_DIR
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

TS = getattr(C, 'TILE_SIZE', 32)

EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Spawns
    "player1_spawn": {
        "source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn",
        "tooltip": "P1", "category": "spawn"
    },
    "player2_spawn": {
        "source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn",
        "tooltip": "P2", "category": "spawn"
    },
    # Enemies
    "enemy_gray": {"source_file": "characters/gray/__Idle.gif", "game_type_id": "enemy_gray", "tooltip": "Enemy (gray)", "category": "enemy"},
    "enemy_green": { "source_file": "characters/green/__Idle.gif", "game_type_id": "enemy_green", "tooltip": "Enemy (Green)", "category": "enemy"},
    "enemy_pink": { "source_file": "characters/pink/__Idle.gif", "game_type_id": "enemy_pink", "tooltip": "Enemy (Pink)", "category": "enemy"},
    "enemy_purple": { "source_file": "characters/purple/__Idle.gif", "game_type_id": "enemy_purple", "tooltip": "Enemy (Purple)", "category": "enemy"},
    "enemy_orange": { "source_file": "characters/orange/__Idle.gif", "game_type_id": "enemy_red", "tooltip": "Enemy (Orange)", "category": "enemy"}, # Note: game_type_id is enemy_red
    "enemy_yellow": { "source_file": "characters/yellow/__Idle.gif", "game_type_id": "enemy_yellow", "tooltip": "Enemy (Yellow)", "category": "enemy"},
    # Items
    "chest": {"source_file": "characters/items/chest.gif", "game_type_id": "chest", "tooltip": "Chest", "category": "item"},
    # Tiles - Full Size
    "platform_wall_gray": {
        "surface_params": (TS, TS, getattr(C, 'GRAY', (128,128,128))), "colorable": True,
        "game_type_id": "platform_wall_gray", "tooltip": "Wall Block (Gray)", "category": "tile"
    },
    "platform_ledge_green_full": { 
        "surface_params": (TS, TS, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True,
        "game_type_id": "platform_ledge_green", "tooltip": "Ledge Block (Green)", "category": "tile"
    },
    # Tiles - Thin Ledges
    "platform_ledge_green_one_fourth": {
        "surface_params": (TS, TS // 4, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True,
        "game_type_id": "platform_ledge_green_one_fourth",
        "tooltip": "Ledge 1/4H (Green)", "category": "tile"
    },
    "platform_ledge_gray_one_fourth": {
        "surface_params": (TS, TS // 4, getattr(C, 'GRAY', (128,128,128))), "colorable": True,
        "game_type_id": "platform_ledge_gray_one_fourth",
        "tooltip": "Ledge 1/4H (Gray)", "category": "tile"
    },
    "platform_ledge_green_one_third": {
        "surface_params": (TS, TS // 3, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True,
        "game_type_id": "platform_ledge_green_one_third",
        "tooltip": "Ledge 1/3H (Green)", "category": "tile"
    },
    "platform_ledge_gray_one_third": {
        "surface_params": (TS, TS // 3, getattr(C, 'GRAY', (128,128,128))), "colorable": True,
        "game_type_id": "platform_ledge_gray_one_third",
        "tooltip": "Ledge 1/3H (Gray)", "category": "tile"
    },
    # Tiles - Half Tiles
    "platform_wall_gray_left_half": {"render_mode": "half_tile", "half_type": "left", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_left_half", "tooltip": "Wall L-Half (Gray)", "category": "tile"},
    "platform_wall_gray_right_half": {"render_mode": "half_tile", "half_type": "right", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_right_half", "tooltip": "Wall R-Half (Gray)", "category": "tile"},
    "platform_wall_gray_top_half": {"render_mode": "half_tile", "half_type": "top", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_top_half", "tooltip": "Wall T-Half (Gray)", "category": "tile"},
    "platform_wall_gray_bottom_half": {"render_mode": "half_tile", "half_type": "bottom", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)), "colorable": True, "game_type_id": "platform_wall_gray_bottom_half", "tooltip": "Wall B-Half (Gray)", "category": "tile"},
    
    # Hazards
    "hazard_lava_tile": { # MODIFIED HERE
        "source_file": "characters/assets/lava.gif", # Path for resource_path
        "game_type_id": "hazard_lava", 
        "tooltip": "Lava Tile (Animated)", 
        "category": "hazard"
        # "colorable" property removed as tinting GIFs is complex and not handled by default.
        # Original GIF size is 40x41. This will be used by editor_assets.py for original_size_pixels.
    },

    # Tools
    "platform_wall_gray_2x2_placer": { 
        "icon_type": "2x2_placer", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)),
        "places_asset_key": "platform_wall_gray", 
        "game_type_id": "tool_wall_2x2_placer", 
        "tooltip": "Wall 2x2 Placer (Gray)", "category": "tool"
    },
}

EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"]

# --- Editable Asset Variables Configuration ---
# Defines variables that can be edited per asset game_type_id in the Asset Properties Editor.
# Structure: asset_game_type_id: {var_name: {type: "int"/"float"/"str"/"bool", default: val, (optional) min: val, max: val, (optional) options: [], (optional) tooltip: "..."}}
EDITABLE_ASSET_VARIABLES: Dict[str, Dict[str, Any]] = {
    "player1_spawn": {
        "max_health": {"type": "int", "default": 100, "min": 1, "max": 999, "tooltip": "P1: Maximum health points."},
        "move_speed": {"type": "float", "default": 300.0, "min": 50.0, "max": 1000.0, "tooltip": "P1: Movement speed in pixels/sec."},
        "jump_strength": {"type": "float", "default": -900.0, "min": -1500.0, "max": -300.0, "tooltip": "P1: Initial vertical velocity for jump."}
    },
    "player2_spawn": { 
        "max_health": {"type": "int", "default": 100, "min": 1, "max": 999, "tooltip": "P2: Maximum health points."},
        "move_speed": {"type": "float", "default": 300.0, "min": 50.0, "max": 1000.0, "tooltip": "P2: Movement speed in pixels/sec."},
        "jump_strength": {"type": "float", "default": -900.0, "min": -1500.0, "max": -300.0, "tooltip": "P2: Initial vertical velocity for jump."}
    },

    "enemy_green": {
        "patrol_range_tiles": {"type": "int", "default": 6, "min": 0, "max": 50},
        "move_speed": {"type": "float", "default": 80.0, "min": 10.0, "max": 300.0},
        "health": {"type": "int", "default": 4, "min": 1, "max": 20},
        "can_fly": {"type": "bool", "default": False}
    },
    "enemy_pink": {
        "health": {"type": "int", "default": 2, "min": 1, "max": 20},
        "move_speed": {"type": "float", "default": 120.0, "min": 10.0, "max": 300.0},
        "patrol_behavior": {"type": "str", "default": "turn_on_edge", "options": ["turn_on_edge", "fall_off_edge", "hover_patrol"], "tooltip": "How enemy behaves at edges."}
    },
    "enemy_purple": {
        "health": {"type": "int", "default": 5, "min": 1, "max": 20},
        "attack_damage": {"type": "int", "default": 2, "min": 0, "max": 10, "tooltip": "Damage dealt on contact."},
         "can_fly": {"type": "bool", "default": True}
    },
    "enemy_orange": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20},
        "is_aggressive": {"type": "bool", "default": True, "tooltip": "Will it chase player if in range?"},
        "aggro_range_tiles": {"type": "int", "default": 8, "min":0, "max": 30, "tooltip":"Range (tiles) to detect player."}
    },
    "enemy_yellow": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20},
        "move_speed": {"type": "float", "default": 150.0, "min": 10.0, "max": 400.0},
    },
        "enemy_gray": {
        "health": {"type": "int", "default": 3, "min": 1, "max": 20},
        "move_speed": {"type": "float", "default": 150.0, "min": 10.0, "max": 400.0},
    },
    "chest": {
        "item_type": {"type": "str", "default": "coin", "options": ["coin", "gem", "potion_health", "potion_speed"], "tooltip": "Type of item inside the chest."},
        "item_quantity": {"type": "int", "default": 1, "min": 1, "max": 100, "tooltip": "Number of items if applicable."}
    },
    # Example for a tile, though less common to have individual properties this way
    # "platform_wall_gray": {
    #     "is_breakable": {"type": "bool", "default": False, "tooltip": "Can this wall be destroyed?"},
    #     "break_hits": {"type": "int", "default": 3, "min": 1, "max": 10, "tooltip": "Hits to break if breakable."}
    # }
}


DEFAULT_MAP_WIDTH_TILES = 30
DEFAULT_MAP_HEIGHT_TILES = 20
DEFAULT_GRID_SIZE = TS
DEFAULT_BACKGROUND_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))

TOOLTIP_FONT_SIZE = 18
TOOLTIP_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
TOOLTIP_BG_COLOR: Tuple[int,int,int] = (240, 240, 210)
TOOLTIP_PADDING = 5
TOOLTIP_OFFSET_Y = 25

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

FONT_CONFIG: Dict[str, Optional[pygame.font.Font]] = {
    "small": None, "medium": None, "large": None, "tooltip": None
}
try:
    if not pygame.font.get_init():
        pygame.font.init()
    if pygame.font.get_init():
        FONT_CONFIG["small"] = pygame.font.Font(None, 22)
        FONT_CONFIG["medium"] = pygame.font.Font(None, 28)
        FONT_CONFIG["large"] = pygame.font.Font(None, 36)
        FONT_CONFIG["tooltip"] = pygame.font.Font(None, TOOLTIP_FONT_SIZE)
        if any(font is None for font in FONT_CONFIG.values()):
            print(f"Warning editor_config: One or more fonts failed to load despite pygame.font.get_init() being true.")
    else:
        print("CRITICAL editor_config: pygame.font.init() failed. Fonts will not be available.")
except pygame.error as e_font_load:
    print(f"CRITICAL editor_config: Pygame error initializing fonts: {e_font_load}"); traceback.print_exc()
except Exception as e_font_generic:
    print(f"CRITICAL editor_config: Generic error initializing fonts: {e_font_generic}"); traceback.print_exc()