# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.9 (Added Asset Palette Fling Scroll Config)
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

ASSET_PALETTE_SECTION_WIDTH = 220 # Width for the asset palette UI

SECTION_PADDING = 10 # Padding around UI sections

# Default dimensions for map view when editor starts
MAP_VIEW_SECTION_DEFAULT_WIDTH = EDITOR_SCREEN_INITIAL_WIDTH - MENU_SECTION_WIDTH - ASSET_PALETTE_SECTION_WIDTH - (SECTION_PADDING * 3)
MAP_VIEW_SECTION_DEFAULT_HEIGHT = EDITOR_SCREEN_INITIAL_HEIGHT - (SECTION_PADDING * 2)


# --- Camera Control ---
KEY_PAN_SPEED_PIXELS_PER_SECOND = 300       # Speed of camera pan with WASD keys
EDGE_SCROLL_ZONE_THICKNESS = 30             # Thickness of screen edge for mouse scroll
EDGE_SCROLL_SPEED_PIXELS_PER_SECOND = 250   # Speed of camera pan with mouse at edge
CAMERA_MOMENTUM_INITIAL_MULTIPLIER = 1.5    # Multiplier for mouse velocity when starting fling
CAMERA_MOMENTUM_DAMPING_FACTOR = 0.96       # Damping per frame for fling (closer to 1 = longer)
CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD = 5.0   # Speed below which momentum stops
CAMERA_MOMENTUM_BOUNDARY_DAMP_FACTOR = 0.5  # How much momentum is reduced when hitting map edge


# --- Minimap Configuration ---
MINIMAP_AREA_HEIGHT = 120 # Fixed height for the minimap area in the palette
MINIMAP_PADDING = 5
MINIMAP_BG_COLOR: Tuple[int,int,int] = (10, 10, 10)
MINIMAP_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MINIMAP_CAMERA_VIEW_RECT_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
MINIMAP_CAMERA_VIEW_RECT_ALPHA = 100 # Alpha for the camera view rectangle on minimap

# --- UI Element Sizes & Colors ---
BUTTON_WIDTH_STANDARD = 200
BUTTON_HEIGHT_STANDARD = 50
BUTTON_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
BUTTON_COLOR_NORMAL: Tuple[int,int,int] = getattr(C, 'BLUE', (0,0,255))
BUTTON_COLOR_HOVER: Tuple[int,int,int] = getattr(C, 'GREEN', (0,255,0))
BUTTON_COLOR_BORDER: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
BUTTON_BORDER_WIDTH = 2

ASSET_THUMBNAIL_MAX_WIDTH = getattr(C, 'TILE_SIZE', 32) * 2 # Max width for asset thumbs in palette
ASSET_THUMBNAIL_MAX_HEIGHT = getattr(C, 'TILE_SIZE', 32) * 2 # Max height
ASSET_PALETTE_ITEM_PADDING = 5
ASSET_PALETTE_BG_COLOR: Tuple[int,int,int] = (30, 30, 30)
ASSET_PALETTE_CATEGORY_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))
ASSET_PALETTE_TOOLTIP_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_GRAY', (200,200,200))
ASSET_PALETTE_HOVER_BG_COLOR: Tuple[int,int,int] = (50, 80, 50) # Background for hovered asset
ASSET_PALETTE_BOTTOM_OVERHANG_PX = 72 # Extra space at bottom of scrollable asset list for easier interaction
ASSET_PALETTE_TOOLTIP_TEXT_V_OFFSET = 2 # Vertical offset for asset name text below thumbnail

# --- Asset Palette Scroll ---
ASSET_PALETTE_SCROLL_KICK_MULTIPLIER = 2000.0 # Speed added on mouse wheel tick
ASSET_PALETTE_FLING_DAMPING_FACTOR = 0.92     # Damping for scroll momentum
ASSET_PALETTE_FLING_MIN_SPEED_THRESHOLD = 50.0 # Momentum below which fling stops
ASSET_PALETTE_MAX_MOMENTUM = 2000.0           # Max scroll speed (pixels/sec)

MAP_VIEW_GRID_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128)) # Border for the map editing area

DIALOG_BG_COLOR: Tuple[int,int,int] = (60, 60, 70)
DIALOG_INPUT_BOX_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_INPUT_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
DIALOG_PROMPT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_CURSOR_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0)) # For text input dialog

COLOR_PICKER_BUTTON_SIZE = 40 # Size of each color swatch in the picker
COLOR_PICKER_PADDING = 8
COLOR_PICKER_COLS = 5 # Number of columns for color swatches
COLOR_PICKER_BG_COLOR: Tuple[int,int,int] = (40, 40, 50)
COLOR_PICKER_TITLE_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
COLOR_PICKER_HOVER_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))

# --- Map File and Directory Configuration ---
MAPS_DIRECTORY = C.MAPS_DIR # Use the dynamically determined absolute path from main constants
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json" # Editor's internal save format
GAME_LEVEL_FILE_EXTENSION = ".py"      # Format for game-consumable levels

TS = getattr(C, 'TILE_SIZE', 32) # Local alias for TILE_SIZE for convenience in this file

# --- Asset Palette Definitions ---
# Defines assets available in the editor's palette.
# game_type_id: Used in the exported Python map file to identify the object type for the game.
# places_asset_key: If this is a "tool" (like a 2x2 placer), this key points to the actual asset being placed.
# colorable: True if the object's color can be changed in the editor.
# render_mode: "half_tile" for special rendering of half-width/height tiles.
# surface_params: (width, height, color_tuple) for procedurally generated palette icons.
# icon_type: For special icons like "2x2_placer".
EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Spawns
    "player1_spawn": {
        "source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn",
        "tooltip": "P1 Spawn", "category": "spawn"
    },
    "player2_spawn": {
        "source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn",
        "tooltip": "P2 Spawn", "category": "spawn"
    },
    # Enemies (using their idle animations for the palette)
    "enemy_cyan": {"source_file": "characters/cyan/__Idle.gif", "game_type_id": "enemy_cyan", "tooltip": "Enemy (Cyan)", "category": "enemy"},
    "enemy_green": { "source_file": "characters/green/__Idle.gif", "game_type_id": "enemy_green", "tooltip": "Enemy (Green)", "category": "enemy"},
    "enemy_pink": { "source_file": "characters/pink/__Idle.gif", "game_type_id": "enemy_pink", "tooltip": "Enemy (Pink)", "category": "enemy"},
    "enemy_purple": { "source_file": "characters/purple/__Idle.gif", "game_type_id": "enemy_purple", "tooltip": "Enemy (Purple)", "category": "enemy"},
    "enemy_red": { "source_file": "characters/red/__Idle.gif", "game_type_id": "enemy_red", "tooltip": "Enemy (Red)", "category": "enemy"},
    "enemy_yellow": { "source_file": "characters/yellow/__Idle.gif", "game_type_id": "enemy_yellow", "tooltip": "Enemy (Yellow)", "category": "enemy"},
    # Items
    "chest": {"source_file": "characters/items/chest.gif", "game_type_id": "chest", "tooltip": "Chest", "category": "item"},
    # Tiles - Full Size
    "platform_wall_gray": {
        "surface_params": (TS, TS, getattr(C, 'GRAY', (128,128,128))), "colorable": True,
        "game_type_id": "platform_wall_gray", "tooltip": "Wall Block (Gray)", "category": "tile"
    },
    "platform_ledge_green_full": { # Renamed from platform_ledge_green for clarity
        "surface_params": (TS, TS, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True, # Made it full tile for palette
        "game_type_id": "platform_ledge_green", "tooltip": "Ledge Block (Green)", "category": "tile"
         # Note: In game, a "ledge" might have different properties or just be a visual distinction.
         # The actual height for the game object will come from its properties during export.
         # If you want the palette icon to be thin, you'd adjust surface_params height here,
         # but then its game_type_id needs to be specific if it's always thin, or the editor
         # needs a way to specify 'ledge of X height'. For simplicity, making palette icon full.
    },
    # Tiles - Thin Ledges (NEW)
    "platform_ledge_green_one_fourth": {
        "surface_params": (TS, TS // 4, getattr(C, 'DARK_GREEN', (0,100,0))), "colorable": True,
        "game_type_id": "platform_ledge_green_one_fourth", # Exported object will use these dimensions
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
    # (You might want half-tiles for ledges too, following the same pattern if needed)

    # Hazards
    "hazard_lava_tile": {
        "surface_params": (TS, TS, getattr(C, 'ORANGE_RED', (255,69,0))), "colorable": True,
        "game_type_id": "hazard_lava", "tooltip": "Lava Tile", "category": "hazard"
    },
    # Tools
    "platform_wall_gray_2x2_placer": { # Example tool
        "icon_type": "2x2_placer", "base_color_tuple": getattr(C, 'GRAY', (128,128,128)),
        "places_asset_key": "platform_wall_gray", # This tool places "platform_wall_gray" assets
        "game_type_id": "tool_wall_2x2_placer", # game_type_id indicates it's a tool
        "tooltip": "Wall 2x2 Placer (Gray)", "category": "tool"
    },
}

# Order of categories in the asset palette
EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "hazard", "item", "enemy", "spawn", "unknown"]

# --- Default Map Settings ---
DEFAULT_MAP_WIDTH_TILES = 30
DEFAULT_MAP_HEIGHT_TILES = 20
DEFAULT_GRID_SIZE = TS # Grid size in pixels, usually same as TILE_SIZE
DEFAULT_BACKGROUND_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))

# --- Tooltip Configuration ---
TOOLTIP_FONT_SIZE = 18 # Font size for tooltips
TOOLTIP_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
TOOLTIP_BG_COLOR: Tuple[int,int,int] = (240, 240, 210) # Light yellowish background
TOOLTIP_PADDING = 5
TOOLTIP_OFFSET_Y = 25 # How far below the mouse the tooltip appears

# --- Color Picker Presets ---
COLOR_PICKER_PRESETS: Dict[str, Tuple[int,int,int]] = {
    "Light Blue": getattr(C, 'LIGHT_BLUE', (173,216,230)), "White": getattr(C, 'WHITE', (255,255,255)),
    "Black": getattr(C, 'BLACK', (0,0,0)), "Gray": getattr(C, 'GRAY', (128,128,128)),
    "Dark Gray": getattr(C, 'DARK_GRAY', (50,50,50)), "Red": getattr(C, 'RED', (255,0,0)),
    "Green": getattr(C, 'GREEN', (0,255,0)), "Blue": getattr(C, 'BLUE', (0,0,255)),
    "Yellow": getattr(C, 'YELLOW', (255,255,0)), "Orange": getattr(C, 'ORANGE_RED', (255,69,0)),
    "Purple": (128, 0, 128), "Brown": (139, 69, 19),
    "Dark Green": getattr(C, 'DARK_GREEN', (0,100,0)), "Sky Blue": (100, 150, 255), # Example custom color
    "Dark Purple BG": getattr(C, 'PURPLE_BACKGROUND', (75,0,130)), # Example for a common BG
    "Sand": (244,164,96), # Example custom
    "Magenta": getattr(C, 'MAGENTA', (255, 0, 255)) # Useful for debugging
}

# --- Font Configuration ---
# Initialize fonts. This relies on pygame.font.init() having been called.
FONT_CONFIG: Dict[str, Optional[pygame.font.Font]] = {
    "small": None, "medium": None, "large": None, "tooltip": None
}
try:
    if not pygame.font.get_init(): # Ensure font module is initialized
        pygame.font.init()
    if pygame.font.get_init(): # Check again after explicit init
        FONT_CONFIG["small"] = pygame.font.Font(None, 22)
        FONT_CONFIG["medium"] = pygame.font.Font(None, 28)
        FONT_CONFIG["large"] = pygame.font.Font(None, 36)
        FONT_CONFIG["tooltip"] = pygame.font.Font(None, TOOLTIP_FONT_SIZE)
        if any(font is None for font in FONT_CONFIG.values()): # Check if any failed
            print(f"Warning editor_config: One or more fonts failed to load despite pygame.font.get_init() being true.")
    else:
        print("CRITICAL editor_config: pygame.font.init() failed. Fonts will not be available.")
except pygame.error as e_font_load: # Catch Pygame-specific font errors
    print(f"CRITICAL editor_config: Pygame error initializing fonts: {e_font_load}"); traceback.print_exc()
except Exception as e_font_generic: # Catch any other unexpected error
    print(f"CRITICAL editor_config: Generic error initializing fonts: {e_font_generic}"); traceback.print_exc()