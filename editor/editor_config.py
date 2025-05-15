# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.2 (Added EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER and debug prints)
Configuration constants for the Platformer Level Editor.
"""
import pygame
import sys
import os
import traceback # ADDED for font init error

# --- Add parent directory to sys.path ---
# This ensures that 'import constants as C' works when this config file is imported by other editor scripts.
# The 'editor' directory is assumed to be a direct subfolder of the project root where 'constants.py' resides.
current_dir = os.path.dirname(os.path.abspath(__file__)) # Should be /path/to/project/editor
parent_dir = os.path.dirname(current_dir)                 # Should be /path/to/project
print(f"DEBUG CONFIG: current_dir (editor_config.py location): {current_dir}")
print(f"DEBUG CONFIG: parent_dir (project root attempt): {parent_dir}")

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"DEBUG CONFIG: Added '{parent_dir}' to sys.path for 'constants' import.")
else:
    print(f"DEBUG CONFIG: '{parent_dir}' already in sys.path.")

try:
    import constants as C # Now this should work
    print(f"DEBUG CONFIG: Successfully imported 'constants as C'. TILE_SIZE: {C.TILE_SIZE}")
except ImportError as e:
    print(f"CRITICAL CONFIG ERROR: Failed to import 'constants as C' from '{parent_dir}'. Error: {e}")
    print(f"DEBUG CONFIG: sys.path was: {sys.path}")
    # Fallback for C if import fails, to prevent further crashes, though editor will be broken.
    class FallbackConstants:
        TILE_SIZE = 32
        WHITE = (255,255,255); BLACK = (0,0,0); RED = (255,0,0); GREEN = (0,255,0)
        BLUE = (0,0,255); GRAY = (128,128,128); DARK_GRAY = (50,50,50); YELLOW = (255,255,0)
        LIGHT_BLUE = (173,216,230); DARK_GREEN = (0,100,0); ORANGE_RED = (255,69,0)
        LIGHT_GRAY = (200,200,200)
        FPS = 60
    C = FallbackConstants()
    print("CRITICAL CONFIG ERROR: Using fallback constants. Editor functionality will be impaired.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}")
    traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")


# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = 1280
EDITOR_SCREEN_INITIAL_HEIGHT = 720

MENU_SECTION_WIDTH = 280
MENU_SECTION_HEIGHT = 250 # Approximate, can be dynamic

ASSET_PALETTE_SECTION_WIDTH = 220

SECTION_PADDING = 10

MAP_VIEW_SECTION_DEFAULT_WIDTH = EDITOR_SCREEN_INITIAL_WIDTH - MENU_SECTION_WIDTH - ASSET_PALETTE_SECTION_WIDTH - (SECTION_PADDING * 4) # Adjusted for more padding considerations
MAP_VIEW_SECTION_DEFAULT_HEIGHT = EDITOR_SCREEN_INITIAL_HEIGHT - (SECTION_PADDING * 2)



# --- UI Element Sizes & Colors ---
BUTTON_WIDTH_STANDARD = 200
BUTTON_HEIGHT_STANDARD = 50
BUTTON_TEXT_COLOR = C.WHITE
BUTTON_COLOR_NORMAL = C.BLUE
BUTTON_COLOR_HOVER = C.GREEN
BUTTON_COLOR_BORDER = C.BLACK
BUTTON_BORDER_WIDTH = 2

ASSET_THUMBNAIL_MAX_WIDTH = C.TILE_SIZE * 2
ASSET_THUMBNAIL_MAX_HEIGHT = C.TILE_SIZE * 2
ASSET_PALETTE_ITEM_PADDING = 5
ASSET_PALETTE_BG_COLOR = (30, 30, 30)
ASSET_PALETTE_CATEGORY_TEXT_COLOR = C.YELLOW
ASSET_PALETTE_TOOLTIP_COLOR = C.LIGHT_GRAY
ASSET_PALETTE_HOVER_BG_COLOR = (50, 80, 50)

MAP_VIEW_GRID_COLOR = C.GRAY
MAP_VIEW_BORDER_COLOR = C.GRAY
MAP_VIEW_CAMERA_PAN_SPEED = C.TILE_SIZE // 2

DIALOG_BG_COLOR = (60, 60, 70)
DIALOG_INPUT_BOX_COLOR = C.WHITE
DIALOG_INPUT_TEXT_COLOR = C.BLACK
DIALOG_PROMPT_COLOR = C.WHITE
DIALOG_CURSOR_COLOR = C.BLACK

COLOR_PICKER_BUTTON_SIZE = 40
COLOR_PICKER_PADDING = 8
COLOR_PICKER_COLS = 5
COLOR_PICKER_BG_COLOR = (40, 40, 50)
COLOR_PICKER_TITLE_COLOR = C.WHITE
COLOR_PICKER_HOVER_BORDER_COLOR = C.YELLOW

MAPS_DIRECTORY = "maps" # Relative to the project root (where constants.py is)

# --- Asset Definitions for Editor Palette ---
EDITOR_PALETTE_ASSETS = {
    "player1_spawn": {
        "source_file": "characters/player1/__Idle.gif", "game_type_id": "player1_spawn",
        "tooltip": "P1 Spawn", "category": "spawn"
    },
    "player2_spawn": {
        "source_file": "characters/player2/__Idle.gif", "game_type_id": "player2_spawn",
        "tooltip": "P2 Spawn", "category": "spawn"
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
        "surface_params": (C.TILE_SIZE, C.TILE_SIZE, C.GRAY), "game_type_id": "platform_wall_gray",
        "tooltip": "Wall (Gray)", "category": "tile"
    },
    "platform_ledge_green": {
        "surface_params": (C.TILE_SIZE, C.TILE_SIZE, C.DARK_GREEN), "game_type_id": "platform_ledge_green",
        "tooltip": "Ledge (Green)", "category": "tile"
    },
    "hazard_lava_tile": {
        "surface_params": (C.TILE_SIZE, C.TILE_SIZE, C.ORANGE_RED), "game_type_id": "hazard_lava",
        "tooltip": "Lava Tile", "category": "hazard"
    },
    # Example for a new asset type:
    # "ladder_tile": {
    #     "surface_params": (C.TILE_SIZE, C.TILE_SIZE, C.BLUE), # Placeholder color
    #     "game_type_id": "ladder", "tooltip": "Ladder", "category": "tile"
    # },
}

# Define the order for displaying categories in the asset palette
EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tile", "hazard", "item", "enemy", "spawn", "unknown"]


# Default map settings
DEFAULT_MAP_WIDTH_TILES = 30
DEFAULT_MAP_HEIGHT_TILES = 20
DEFAULT_GRID_SIZE = C.TILE_SIZE
DEFAULT_BACKGROUND_COLOR = C.LIGHT_BLUE

# File paths
# MAPS_DIRECTORY is already defined above
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

# Tooltip settings
TOOLTIP_FONT_SIZE = 18
TOOLTIP_TEXT_COLOR = C.BLACK
TOOLTIP_BG_COLOR = (240, 240, 210) # Light yellow
TOOLTIP_PADDING = 5
TOOLTIP_OFFSET_Y = 25

# --- Color Picker Presets ---
COLOR_PICKER_PRESETS = {
    "Light Blue": C.LIGHT_BLUE, "White": C.WHITE, "Black": C.BLACK, "Gray": C.GRAY,
    "Dark Gray": C.DARK_GRAY, "Red": C.RED, "Green": C.GREEN, "Blue": C.BLUE,
    "Yellow": C.YELLOW, "Orange": C.ORANGE_RED, "Purple": (128, 0, 128),
    "Brown": (139, 69, 19), "Dark Green": C.DARK_GREEN, "Sky Blue": (100, 150, 255),
    "Dark Purple": (75,0,130), "Sand": (244,164,96)
}

# --- Font Definitions ---
# This block should be one of the last things, as it depends on pygame.font
FONT_CONFIG = {
    "small": None, "medium": None, "large": None, "tooltip": None
}
try:
    if not pygame.font.get_init(): # Check if font module is initialized
        print("DEBUG CONFIG: pygame.font not initialized, calling pygame.font.init()")
        pygame.font.init()
    
    if pygame.font.get_init(): # Double check if init was successful
        FONT_CONFIG["small"] = pygame.font.Font(None, 22)
        FONT_CONFIG["medium"] = pygame.font.Font(None, 28)
        FONT_CONFIG["large"] = pygame.font.Font(None, 36)
        FONT_CONFIG["tooltip"] = pygame.font.Font(None, TOOLTIP_FONT_SIZE)
        print("DEBUG CONFIG: Successfully initialized fonts in FONT_CONFIG.")
    else:
        print("CRITICAL CONFIG ERROR: pygame.font.init() failed. Fonts will be None.")
        # FONT_CONFIG remains with Nones

except pygame.error as e:
    print(f"CRITICAL CONFIG ERROR: Pygame error initializing fonts in editor_config: {e}")
    traceback.print_exc()
    # FONT_CONFIG remains with Nones
except Exception as e_font:
    print(f"CRITICAL CONFIG ERROR: Generic error initializing fonts in editor_config: {e_font}")
    traceback.print_exc()
    # FONT_CONFIG remains with Nones

if FONT_CONFIG["small"] is None:
    print("WARNING CONFIG: Font 'small' is None. UI elements using it might not render text.")
if FONT_CONFIG["medium"] is None:
    print("WARNING CONFIG: Font 'medium' is None. UI elements using it might not render text.")
if FONT_CONFIG["large"] is None:
    print("WARNING CONFIG: Font 'large' is None. UI elements using it might not render text.")

print("DEBUG CONFIG: editor_config.py loaded.")