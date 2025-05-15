# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.5 (Added MAGENTA to FallbackConstants)
Configuration constants for the Platformer Level Editor.
"""
import pygame
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any # ADDED Optional, Dict, Tuple, Any for type hints

# --- Add parent directory to sys.path ---
# (sys.path manipulation and constants import remains the same)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
print(f"DEBUG CONFIG: current_dir (editor_config.py location): {current_dir}")
print(f"DEBUG CONFIG: parent_dir (project root attempt): {parent_dir}")

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"DEBUG CONFIG: Added '{parent_dir}' to sys.path for 'constants' import.")
else:
    print(f"DEBUG CONFIG: '{parent_dir}' already in sys.path.")

try:
    import constants as C
    print(f"DEBUG CONFIG: Successfully imported 'constants as C'. TILE_SIZE: {C.TILE_SIZE if hasattr(C, 'TILE_SIZE') else 'NOT FOUND'}")
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{parent_dir}'. Error: {e}")
    print(f"DEBUG CONFIG: sys.path was: {sys.path}")
    class FallbackConstants:
        TILE_SIZE = 32; WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200); FPS = 60
        MAGENTA = (255, 0, 255)  # <--- ADDED MAGENTA HERE
    C = FallbackConstants()
    print("CRITICAL CONFIG ERROR: Using fallback constants. Editor functionality will be impaired.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")


# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = 1280
EDITOR_SCREEN_INITIAL_HEIGHT = 720

MENU_SECTION_WIDTH = 280
MENU_SECTION_HEIGHT = 250

ASSET_PALETTE_SECTION_WIDTH = 220

SECTION_PADDING = 10

MAP_VIEW_SECTION_DEFAULT_WIDTH = EDITOR_SCREEN_INITIAL_WIDTH - MENU_SECTION_WIDTH - ASSET_PALETTE_SECTION_WIDTH - (SECTION_PADDING * 3)
MAP_VIEW_SECTION_DEFAULT_HEIGHT = EDITOR_SCREEN_INITIAL_HEIGHT - (SECTION_PADDING * 2)

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

MAP_VIEW_GRID_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'GRAY', (128,128,128))
MAP_VIEW_CAMERA_PAN_SPEED: int = getattr(C, 'TILE_SIZE', 32) // 2

DIALOG_BG_COLOR: Tuple[int,int,int] = (60, 60, 70)
DIALOG_INPUT_BOX_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_INPUT_TEXT_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))
DIALOG_PROMPT_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
DIALOG_CURSOR_COLOR: Tuple[int,int,int] = getattr(C, 'BLACK', (0,0,0))

COLOR_PICKER_BUTTON_SIZE = 40
COLOR_PICKER_PADDING = 8
COLOR_PICKER_COLS = 5
COLOR_PICKER_BG_COLOR: Tuple[int,int,int] = (40, 40, 50)
COLOR_PICKER_TITLE_COLOR: Tuple[int,int,int] = getattr(C, 'WHITE', (255,255,255))
COLOR_PICKER_HOVER_BORDER_COLOR: Tuple[int,int,int] = getattr(C, 'YELLOW', (255,255,0))

MAPS_DIRECTORY = "maps"

# --- Asset Definitions for Editor Palette ---
EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = { # Added Any
    "player1_spawn": {
        "source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn",
        "tooltip": "P1", "category": "spawn"
    },
    "player2_spawn": {
        "source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn",
        "tooltip": "P2", "category": "spawn"
    },
    "enemy_cyan": {
        "source_file": "characters/cyan/__Idle.gif", "game_type_id": "enemy_cyan",
        "tooltip": "Enemy (Cyan)", "category": "enemy"
    },
    "enemy_green": {
        "source_file": "characters/green/__Idle.gif", "game_type_id": "enemy_green",
        "tooltip": "Enemy (Green)", "category": "enemy"
    },
    "enemy_pink": {
        "source_file": "characters/pink/__Idle.gif", "game_type_id": "enemy_pink",
        "tooltip": "Enemy (Pink)", "category": "enemy"
    },
    "enemy_purple": {
        "source_file": "characters/purple/__Idle.gif", "game_type_id": "enemy_purple",
        "tooltip": "Enemy (Purple)", "category": "enemy"
    },
    "enemy_red": {
        "source_file": "characters/red/__Idle.gif", "game_type_id": "enemy_red",
        "tooltip": "Enemy (Red)", "category": "enemy"
    },
    "enemy_yellow": {
        "source_file": "characters/yellow/__Idle.gif", "game_type_id": "enemy_yellow",
        "tooltip": "Enemy (Yellow)", "category": "enemy"
    },
    "chest": {
        "source_file": "characters/items/chest.gif", "game_type_id": "chest",
        "tooltip": "Chest", "category": "item"
    },
    "platform_wall_gray": {
        "surface_params": (getattr(C, 'TILE_SIZE', 32), getattr(C, 'TILE_SIZE', 32), getattr(C, 'GRAY', (128,128,128))),
        "game_type_id": "platform_wall_gray", "tooltip": "Wall (Gray)", "category": "tile"
    },
    "platform_ledge_green": {
        "surface_params": (getattr(C, 'TILE_SIZE', 32), getattr(C, 'TILE_SIZE', 32), getattr(C, 'DARK_GREEN', (0,100,0))),
        "game_type_id": "platform_ledge_green", "tooltip": "Ledge (Green)", "category": "tile"
    },
    "hazard_lava_tile": {
        "surface_params": (getattr(C, 'TILE_SIZE', 32), getattr(C, 'TILE_SIZE', 32), getattr(C, 'ORANGE_RED', (255,69,0))),
        "game_type_id": "hazard_lava", "tooltip": "Lava Tile", "category": "hazard"
    },
}

EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tile", "hazard", "item", "enemy", "spawn", "unknown"]

DEFAULT_MAP_WIDTH_TILES = 30
DEFAULT_MAP_HEIGHT_TILES = 20
DEFAULT_GRID_SIZE = getattr(C, 'TILE_SIZE', 32)
DEFAULT_BACKGROUND_COLOR: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))

LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

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
    "Dark Purple": (75,0,130), "Sand": (244,164,96),
    "Magenta": getattr(C, 'MAGENTA', (255, 0, 255)) # Ensure Magenta is also here if needed as a selectable preset
}

FONT_CONFIG: Dict[str, Optional[pygame.font.Font]] = {
    "small": None, "medium": None, "large": None, "tooltip": None
}
try:
    if not pygame.font.get_init():
        print("DEBUG CONFIG: pygame.font not initialized, calling pygame.font.init()")
        pygame.font.init()

    if pygame.font.get_init():
        FONT_CONFIG["small"] = pygame.font.Font(None, 22)
        FONT_CONFIG["medium"] = pygame.font.Font(None, 28)
        FONT_CONFIG["large"] = pygame.font.Font(None, 36)
        FONT_CONFIG["tooltip"] = pygame.font.Font(None, TOOLTIP_FONT_SIZE)
        print("DEBUG CONFIG: Successfully initialized fonts in FONT_CONFIG.")
    else:
        print("CRITICAL CONFIG ERROR: pygame.font.init() failed. Fonts will be None.")
except pygame.error as e:
    print(f"CRITICAL CONFIG ERROR: Pygame error initializing fonts in editor_config: {e}"); traceback.print_exc()
except Exception as e_font:
    print(f"CRITICAL CONFIG ERROR: Generic error initializing fonts in editor_config: {e_font}"); traceback.print_exc()

for font_name, font_obj in FONT_CONFIG.items():
    if font_obj is None:
        print(f"WARNING CONFIG: Font '{font_name}' is None. UI elements using it might not render text correctly.")

print("DEBUG CONFIG: editor_config.py loaded.")