# editor_config.py
# -*- coding: utf-8 -*-
"""
## version 2.2.10 (Verified Asset Paths)
Configuration constants for the Platformer Level Editor (PySide6 Version).
- Verified that source_file paths in EDITOR_PALETTE_ASSETS align with the new asset organization
  (e.g., assets/category/subcategory/file.ext).
- Added "Select Tool".
- Defined various wall segment assets for cycling (1/3, 1/4 dimensions).
- Added WALL_VARIANTS_CYCLE list.
- Uncommented wall corner rounding properties for slider implementation.
- Added "is_crouched_variant" to stone object properties.
- Added "apply_gravity" to custom image properties.
- Added "opacity" slider (0-100) for custom images and trigger squares.
- Added EnemyKnight to editor palette and properties.
"""
import sys
import os
import traceback
from typing import Dict, Optional, Tuple, Any, List

from PySide6.QtGui import QColor # For MINIMAP_CATEGORY_COLORS

# --- Add parent directory to sys.path ---
current_script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
project_root_dir = os.path.dirname(current_script_dir)

if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    import main_game.constants as C
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
        ENEMY_RUN_SPEED_LIMIT = 3.0; ENEMY_MAX_HEALTH = 80; ENEMY_ATTACK_DAMAGE = 10
        ENEMY_ATTACK_RANGE = 60.0; ENEMY_DETECTION_RANGE = 200.0 # Added for knight props
    C = FallbackConstants() # type: ignore
    print("CRITICAL editor_config.py: Using fallback constants.")
except Exception as e_gen:
    print(f"CRITICAL CONFIG ERROR: Unexpected error importing 'constants': {e_gen}"); traceback.print_exc()
    sys.exit("Failed to initialize constants in editor_config.py")

# --- Editor Window Dimensions ---
EDITOR_SCREEN_INITIAL_WIDTH = getattr(C, 'EDITOR_SCREEN_INITIAL_WIDTH', 1380)
EDITOR_SCREEN_INITIAL_HEIGHT = getattr(C, 'EDITOR_SCREEN_INITIAL_HEIGHT', 820)

# --- Section Preferred Sizes ---
MENU_SECTION_PREFERRED_WIDTH = 250
ASSET_PALETTE_PREFERRED_WIDTH = 300

# --- Grid and Tile Size ---
BASE_GRID_SIZE = getattr(C, 'TILE_SIZE', 40)
TS = BASE_GRID_SIZE # Shortcut for TILE_SIZE

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
MINIMAP_OBJECT_REPRESENTATION_SIZE_PX = 2.0
MINIMAP_UPDATE_INTERVAL_MS = 50
MINIMAP_CATEGORY_COLORS: Dict[str, QColor] = {
    "spawn": QColor(0, 255, 0, 180),
    "enemy": QColor(255, 0, 0, 180),
    "item": QColor(255, 255, 0, 180),
    "object": QColor(0, 0, 255, 180),
    "hazard": QColor(255, 100, 0, 200),
    "tile": QColor(150, 150, 150, 200),
    "background_tile": QColor(100, 100, 120, 150),
    "custom_image": QColor(0, 150, 150, 180),
    "trigger": QColor(200, 0, 200, 150),
    "trigger_image": QColor(180, 50, 180, 170),
    "unknown": QColor(255, 0, 255, 150)
}


# --- Asset Palette ---
ASSET_THUMBNAIL_SIZE = getattr(C, 'TILE_SIZE', 40)
ASSET_PALETTE_ICON_SIZE_W = ASSET_THUMBNAIL_SIZE
ASSET_PALETTE_ICON_SIZE_H = ASSET_THUMBNAIL_SIZE
ASSET_ITEM_BACKGROUND_SELECTED_COLOR_TUPLE: Tuple[int,int,int] = (70, 100, 150)

# --- File Paths and Extensions ---
MAPS_DIRECTORY = getattr(C, 'MAPS_DIR', "maps")
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = getattr(C, "LEVEL_EDITOR_SAVE_FORMAT_EXTENSION", ".json")
GAME_LEVEL_FILE_EXTENSION = getattr(C, "GAME_LEVEL_FILE_EXTENSION", ".py")

# --- Custom Asset Identifiers ---
CUSTOM_IMAGE_ASSET_KEY = "custom_image_object"
TRIGGER_SQUARE_ASSET_KEY = "trigger_square" # This is the palette key
TRIGGER_SQUARE_GAME_TYPE_ID = "trigger_square_link" # This is used to key into EDITABLE_ASSET_VARIABLES
CUSTOM_ASSET_PALETTE_PREFIX = "custom:"

GRAY_COLOR = getattr(C, 'GRAY', (128,128,128))
DARK_GREEN_COLOR = getattr(C, 'DARK_GREEN', (0,100,0))

EDITOR_PALETTE_ASSETS: Dict[str, Dict[str, Any]] = {
    # Tools
    "tool_select": {"icon_type": "select_cursor_icon", "base_color_tuple": getattr(C, 'BLUE', (0,0,255)), "game_type_id": "tool_select", "category": "tool", "name_in_palette": "Select Tool"},
    "tool_eraser": {"icon_type": "eraser", "base_color_tuple": getattr(C, 'RED', (255,0,0)), "game_type_id": "tool_eraser", "category": "tool", "name_in_palette": "Eraser Tool"},
    "platform_wall_gray_2x2_placer": {"icon_type": "2x2_placer", "base_color_tuple": GRAY_COLOR, "places_asset_key": "platform_wall_gray", "game_type_id": "tool_wall_2x2_placer", "category": "tool", "name_in_palette": "2x2 Wall Placer"},
    "tool_color_picker": {"icon_type": "color_swatch", "base_color_tuple": getattr(C, 'BLUE', (0,0,255)), "game_type_id": "tool_tile_color_picker", "category": "tool", "name_in_palette": "Color Picker Tool"},

    # Spawns
    "player1_spawn": {"source_file": "assets/playable_characters/player1/__Idle.gif", "game_type_id": "player1_spawn", "category": "spawn", "name_in_palette": "Player 1 Spawn"},
    "player2_spawn": {"source_file": "assets/playable_characters/player2/__Idle.gif", "game_type_id": "player2_spawn", "category": "spawn", "name_in_palette": "Player 2 Spawn"},
    "player3_spawn": {"source_file": "assets/playable_characters/player3/__Idle.gif", "game_type_id": "player3_spawn", "category": "spawn", "name_in_palette": "Player 3 Spawn"},
    "player4_spawn": {"source_file": "assets/playable_characters/player4/__Idle.gif", "game_type_id": "player4_spawn", "category": "spawn", "name_in_palette": "Player 4 Spawn"},

    # Enemies
    "enemy_green": {"source_file": "assets/enemy_characters/soldier/green/__Idle.gif", "game_type_id": "enemy_green", "category": "enemy", "name_in_palette": "Enemy Green"},
    "enemy_gray": {"source_file": "assets/enemy_characters/soldier/gray/__Idle.gif", "game_type_id": "enemy_gray", "category": "enemy", "name_in_palette": "Enemy Gray"},
    "enemy_pink": {"source_file": "assets/enemy_characters/soldier/pink/__Idle.gif", "game_type_id": "enemy_pink", "category": "enemy", "name_in_palette": "Enemy Pink"},
    "enemy_purple": {"source_file": "assets/enemy_characters/soldier/purple/__Idle.gif", "game_type_id": "enemy_purple", "category": "enemy", "name_in_palette": "Enemy Purple"},
    "enemy_orange": {"source_file": "assets/enemy_characters/soldier/orange/__Idle.gif", "game_type_id": "enemy_orange", "category": "enemy", "name_in_palette": "Enemy Orange (Red)"},
    "enemy_yellow": {"source_file": "assets/enemy_characters/soldier/yellow/__Idle.gif", "game_type_id": "enemy_yellow", "category": "enemy", "name_in_palette": "Enemy Yellow"},
    "enemy_cactus": {"source_file": "assets/enemy_characters/cactus/Cactus_Idle.png", "game_type_id": "enemy_cactus", "category": "enemy", "name_in_palette": "Cactus"},
    "enemy_truck": {"source_file": "assets/enemy_characters/truck/Truck_Idle.png", "game_type_id": "enemy_truck", "category": "enemy", "name_in_palette": "Truck"},
    "enemy_knight": {
        "source_file": "assets/enemy_characters/knight/idle.gif",
        "game_type_id": "enemy_knight",
        "category": "enemy",
        "name_in_palette": "Knight Enemy"
    },

    # Items
    "item_chest": {"source_file": "assets/items/chest.gif", "game_type_id": "chest", "category": "item", "name_in_palette": "Chest"},

    # Objects
    "object_stone_idle": {"source_file": "assets/shared/Stone/__Stone.png", "game_type_id": "object_stone_idle", "category": "object", "name_in_palette": "Stone Block"},
    "object_stone_crouch": {"source_file": "assets/shared/Stone/__StoneCrouch.png", "game_type_id": "object_stone_crouch", "category": "object", "name_in_palette": "Stone Crouch"},

    # Tiles (procedural)
    "platform_wall_gray": {"surface_params": (TS, TS, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray", "category": "tile", "name_in_palette": "Wall (Gray)"},
    "platform_wall_gray_1_3_top": {"surface_params": (TS, TS // 3, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_3_top", "category": "tile", "name_in_palette": "Wall 1/3 Top"},
    "platform_wall_gray_1_3_right": {"surface_params": (TS // 3, TS, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_3_right", "category": "tile", "name_in_palette": "Wall 1/3 Right"},
    "platform_wall_gray_1_3_bottom": {"surface_params": (TS, TS // 3, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_3_bottom", "category": "tile", "name_in_palette": "Wall 1/3 Bottom"},
    "platform_wall_gray_1_3_left": {"surface_params": (TS // 3, TS, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_3_left", "category": "tile", "name_in_palette": "Wall 1/3 Left"},
    "platform_wall_gray_1_4_top_left": {"surface_params": (TS // 2, TS // 2, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_4_top_left", "category": "tile", "name_in_palette": "Wall 1/4 TL"},
    "platform_wall_gray_1_4_top_right": {"surface_params": (TS // 2, TS // 2, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_4_top_right", "category": "tile", "name_in_palette": "Wall 1/4 TR"},
    "platform_wall_gray_1_4_bottom_right": {"surface_params": (TS // 2, TS // 2, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_4_bottom_right", "category": "tile", "name_in_palette": "Wall 1/4 BR"},
    "platform_wall_gray_1_4_bottom_left": {"surface_params": (TS // 2, TS // 2, GRAY_COLOR), "colorable": True, "game_type_id": "platform_wall_gray_1_4_bottom_left", "category": "tile", "name_in_palette": "Wall 1/4 BL"},

    "platform_ledge_green_full": {"surface_params": (TS, TS, DARK_GREEN_COLOR), "colorable": True, "game_type_id": "platform_ledge_green", "category": "tile", "name_in_palette": "Ledge (Green)"},
    "platform_ledge_green_one_fourth": {"surface_params": (TS, TS // 4, DARK_GREEN_COLOR), "colorable": True, "game_type_id": "platform_ledge_green_one_fourth", "category": "tile", "name_in_palette": "Ledge 1/4 (Green)"},

    # Hazards
    "hazard_lava_tile": {"source_file": "assets/environment/lava.gif", "game_type_id": "hazard_lava", "category": "hazard", "name_in_palette": "Lava Tile"},

    # Background Tiles
    "background_dark_fill": {"surface_params": (TS * 5, TS * 5, getattr(C, 'DARK_GRAY', (50, 50, 50))), "colorable": True, "game_type_id": "background_dark_fill", "category": "background_tile", "name_in_palette": "BG Dark Fill (5x5)"},

    # Logic
    TRIGGER_SQUARE_ASSET_KEY: {
        "icon_type": "generic_square_icon",
        "base_color_tuple": (100, 100, 255, 150),
        "game_type_id": TRIGGER_SQUARE_GAME_TYPE_ID,
        "category": "logic",
        "name_in_palette": "Trigger Square"
    },
}

EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER = ["tool", "tile", "background_tile", "hazard", "item", "object", "enemy", "spawn", "logic", "Custom", "unknown"]

# --- Wall Variant Cycling ---
WALL_BASE_KEY = "platform_wall_gray" # The primary key used in the palette to represent the cycle
WALL_VARIANTS_CYCLE: List[str] = [ # Actual asset keys for each variant in cycle order
    "platform_wall_gray",
    "platform_wall_gray_1_3_top",
    "platform_wall_gray_1_3_right",
    "platform_wall_gray_1_3_bottom",
    "platform_wall_gray_1_3_left",
    "platform_wall_gray_1_4_top_left",
    "platform_wall_gray_1_4_top_right",
    "platform_wall_gray_1_4_bottom_right",
    "platform_wall_gray_1_4_bottom_left",
]

# --- Asset Orientation Rules ---
ROTATABLE_ASSET_KEYS: List[str] = [
    key for key in EDITOR_PALETTE_ASSETS
    if ("wall" in key.lower() or "ledge" in key.lower()) and EDITOR_PALETTE_ASSETS[key].get("category") == "tile"
]
FLIPPABLE_ASSET_CATEGORIES: List[str] = ["object", "enemy", "spawn", "item", "hazard"]


_PLAYER_DEFAULT_PROPS_TEMPLATE = {
    "max_health": {"type": "int", "default": getattr(C, 'PLAYER_MAX_HEALTH', 100), "min": 1, "max": 999, "label": "Max Health"},
    "move_speed": {"type": "float", "default": getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 50, "min": 50.0, "max": 1000.0, "label": "Move Speed (units/s)"},
    "jump_strength": {"type": "float", "default": getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 60, "min": -1500.0, "max": -300.0, "label": "Jump Strength (units/s)"}
}
_ENEMY_DEFAULT_PROPS_TEMPLATE = {
    "max_health": {"type": "int", "default": getattr(C, 'ENEMY_MAX_HEALTH', 80), "min": 1, "max": 500, "label": "Max Health"},
    "move_speed": {"type": "float", "default": getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 3.0) * 50, "min": 10.0, "max": 500.0, "label": "Move Speed (units/s)"},
    "attack_damage": {"type": "int", "default": getattr(C, 'ENEMY_ATTACK_DAMAGE', 10), "min": 0, "max": 100, "label": "Base Attack Damage"}, # Generic
    "patrol_range_tiles": {"type": "int", "default": 5, "min": 0, "max": 50, "label": "Patrol Range (Tiles)"},
    "patrol_behavior": {"type": "str", "default": "turn_on_edge", "label": "Patrol Behavior", "options": ["turn_on_edge", "turn_at_range_limit", "stationary", "follow_player"]}
}
_BASE_WALL_PROPERTIES = {
    "destructible": {"type": "bool", "default": False, "label": "Is Destructible"},
    "health": {"type": "int", "default": 100, "min": 0, "max": 500, "label": "Health (if Dest.)"},
    "material_type": {"type": "str", "default": "stone", "label": "Material", "options": ["stone", "wood", "metal", "ice"]},
    "corner_radius": {"type": "slider", "default": 0, "min": 0, "max": TS // 2, "label": "Corner Radius"},
    "round_top_left": {"type": "bool", "default": True, "label": "Round Top-Left"},
    "round_top_right": {"type": "bool", "default": True, "label": "Round Top-Right"},
    "round_bottom_left": {"type": "bool", "default": True, "label": "Round Bottom-Left"},
    "round_bottom_right": {"type": "bool", "default": True, "label": "Round Bottom-Right"},
    "is_boundary": {"type": "bool", "default": False, "label": "Is Map Boundary"},
}


EDITABLE_ASSET_VARIABLES: Dict[str, Dict[str, Any]] = {
    "player1_spawn": _PLAYER_DEFAULT_PROPS_TEMPLATE.copy(),
    "player2_spawn": _PLAYER_DEFAULT_PROPS_TEMPLATE.copy(),
    "player3_spawn": _PLAYER_DEFAULT_PROPS_TEMPLATE.copy(),
    "player4_spawn": _PLAYER_DEFAULT_PROPS_TEMPLATE.copy(),

    "enemy_green":  {**_ENEMY_DEFAULT_PROPS_TEMPLATE.copy(), "can_fly": {"type": "bool", "default": False, "label": "Can Fly"}},
    "enemy_gray":   _ENEMY_DEFAULT_PROPS_TEMPLATE.copy(),
    "enemy_pink":   _ENEMY_DEFAULT_PROPS_TEMPLATE.copy(),
    "enemy_purple": {**_ENEMY_DEFAULT_PROPS_TEMPLATE.copy(), "teleport_range_tiles": {"type": "int", "default": 0, "min":0, "max":20, "label": "Teleport Range (Tiles)"}},
    "enemy_orange": _ENEMY_DEFAULT_PROPS_TEMPLATE.copy(),
    "enemy_yellow": {**_ENEMY_DEFAULT_PROPS_TEMPLATE.copy(), "is_invincible_while_charging": {"type": "bool", "default": False, "label": "Invincible Charge"}},
    "enemy_cactus": {**_ENEMY_DEFAULT_PROPS_TEMPLATE.copy(), "shoot_interval_ms": {"type": "int", "default": 2000, "min": 500, "max": 10000, "label": "Shoot Interval (ms)"}, "projectile_type": {"type": "str", "default": "thorn", "label": "Projectile", "options":["thorn", "fast_thorn"]}},
    "enemy_truck": {**_ENEMY_DEFAULT_PROPS_TEMPLATE.copy(), "charge_speed_multiplier": {"type": "float", "default": 2.0, "min": 1.0, "max": 5.0, "label": "Charge Speed Multiplier"}, "charge_cooldown_ms": {"type": "int", "default": 3000, "min": 1000, "max": 10000, "label": "Charge Cooldown (ms)"}},
    "enemy_knight": {
        "max_health": {"type": "int", "default": 150, "min": 1, "max": 999, "label": "Max Health"},
        "move_speed": {"type": "float", "default": getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75 * 50, "min": 10.0, "max": 700.0, "label": "Move Speed (units/s)"},
        "jump_strength": {"type": "float", "default": getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65 * 60, "min": -1500.0, "max": -100.0, "label": "Jump Strength (units/s, negative for up)"},
        "patrol_jump_chance": {"type": "float", "default": 0.015, "min": 0.0, "max": 1.0, "label": "Patrol Jump Chance (0-1)"},
        "patrol_jump_cooldown_ms": {"type": "int", "default": 2500, "min": 500, "max": 20000, "label": "Patrol Jump Cooldown (ms)"},
        "attack1_damage": {"type": "int", "default": 15, "min": 0, "max": 100, "label": "Attack 1 Damage"},
        "attack2_damage": {"type": "int", "default": 20, "min": 0, "max": 100, "label": "Attack 2 Damage"},
        "attack3_damage": {"type": "int", "default": 25, "min": 0, "max": 100, "label": "Attack 3 Damage"},
        "run_attack_damage": {"type": "int", "default": 12, "min": 0, "max": 100, "label": "Run Attack Damage"},
        "attack_cooldown_ms": {"type": "int", "default": 1800, "min": 100, "max": 10000, "label": "Attack Cooldown (ms)"},
        "attack_range_px": {"type": "float", "default": getattr(C, 'ENEMY_ATTACK_RANGE', 60.0) * 1.2, "min": 10.0, "max": 500.0, "label": "Attack Range (px)"},
        "detection_range_px": {"type": "float", "default": getattr(C, 'ENEMY_DETECTION_RANGE', 200.0), "min": 50.0, "max": 1000.0, "label": "Detection Range (px)"},
        "patrol_range_tiles": {"type": "int", "default": 5, "min": 0, "max": 50, "label": "Patrol Range (Tiles)"},
        "patrol_behavior": {"type": "str", "default": "knight_patrol_with_jump", "label": "Patrol Behavior", "options": ["turn_on_edge", "turn_at_range_limit", "stationary", "follow_player", "knight_patrol_with_jump"]}
    },

    "platform_wall_gray": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_3_top": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_3_right": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_3_bottom": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_3_left": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_4_top_left": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_4_top_right": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_4_bottom_right": _BASE_WALL_PROPERTIES.copy(),
    "platform_wall_gray_1_4_bottom_left": _BASE_WALL_PROPERTIES.copy(),

    "platform_ledge_green": {"destructible": {"type": "bool", "default": False, "label": "Is Destructible"}, "health": {"type": "int", "default": 80, "min": 0, "max": 400, "label": "Health (if Dest.)"}, "is_slippery": {"type": "bool", "default": False, "label": "Is Slippery"}},
    "platform_ledge_green_one_fourth": {"destructible": {"type": "bool", "default": False, "label": "Is Destructible"}, "health": {"type": "int", "default": 20, "min": 0, "max": 100, "label": "Health (if Dest.)"}, "is_breakable_by_heavy": {"type": "bool", "default": True, "label": "Breaks Under Heavy"}},

    "object_stone_idle": {"destructible": {"type": "bool", "default": True, "label": "Is Destructible"}, "health": {"type": "int", "default": 1, "min": 0, "max": 1000, "label": "Health (if Dest.)"}, "can_be_pushed": {"type": "bool", "default": True, "label": "Can Be Pushed"}, "push_resistance": {"type": "float", "default": 1.0, "min":0.1, "max": 10.0, "label": "Push Resistance"}, "drops_item_on_destroy": {"type": "str", "default": "", "label": "Drops Item (ID or empty)"}, "is_crouched_variant": {"type": "bool", "default": False, "label": "Is Crouched Stone Visual"}},
    "object_stone_crouch": {"destructible": {"type": "bool", "default": True, "label": "Is Destructible"}, "health": {"type": "int", "default": 1, "min": 0, "max": 1000, "label": "Health (if Dest.)"}, "can_be_pushed": {"type": "bool", "default": True, "label": "Can Be Pushed"}, "is_heavy": {"type": "bool", "default": True, "label": "Is Heavy"}, "is_crouched_variant": {"type": "bool", "default": True, "label": "Is Crouched Stone Visual"}},

    "chest": {"item_type": {"type": "str", "default": "coin", "label": "Item Type", "options": ["coin", "health_potion", "key", "weapon_upgrade", "star_fragment"]}, "item_quantity": {"type": "int", "default": 1, "min": 1, "max": 10, "label": "Item Quantity"}, "requires_key_id": {"type": "str", "default": "", "label": "Requires Key ID (empty if none)"}},
    "hazard_lava": {"damage_per_tick": {"type": "int", "default": 5, "min": 0, "max": 50, "label": "Damage Per Tick"}, "is_instant_death": {"type": "bool", "default": False, "label": "Instant Death"}},

    CUSTOM_IMAGE_ASSET_KEY: {
        "is_background": {"type": "bool", "default": True, "label": "Is Background Image"},
        "is_obstacle": {"type": "bool", "default": False, "label": "Is Obstacle"},
        "destructible": {"type": "bool", "default": False, "label": "Is Destructible"},
        "health": {"type": "int", "default": 100, "min": 0, "max": 1000, "label": "Health (if Destructible)"},
        "scroll_factor_x": {"type": "float", "default": 1.0, "min": 0.0, "max": 2.0, "label": "Scroll Factor X (Parallax)"},
        "scroll_factor_y": {"type": "float", "default": 1.0, "min": 0.0, "max": 2.0, "label": "Scroll Factor Y (Parallax)"},
        "apply_gravity": {"type": "bool", "default": False, "label": "Apply Gravity"},
        "opacity": {"type": "slider", "default": 100, "min": 0, "max": 100, "label": "Opacity (%)"},
    },
    TRIGGER_SQUARE_GAME_TYPE_ID: {
        "visible": {"type": "bool", "default": True, "label": "Visible in Game"},
        "fill_color_rgba": {"type": "tuple_color_rgba", "default": (100, 100, 255, 100), "label": "Fill Color (RGBA)"},
        "image_in_square": {"type": "image_path_custom", "default": "", "label": "Image in Square"},
        "opacity": {"type": "slider", "default": 100, "min": 0, "max": 100, "label": "Opacity (%)"},
        "linked_map_name": {"type": "str", "default": "", "label": "Linked Map Name"},
        "trigger_event_type": {"type": "str", "default": "player_enter", "label": "Event Type", "options": ["player_enter", "player_use", "enemy_enter", "object_overlap", "projectile_hit"]},
        "one_time_trigger": {"type": "bool", "default": True, "label": "One-Time Trigger"},
        "activation_id": {"type": "str", "default": "", "label": "Activation ID (for scripts)"}
    },
}

def get_default_properties_for_asset(game_type_id: str) -> Dict[str, Any]:
    defaults = {}
    if game_type_id in EDITABLE_ASSET_VARIABLES:
        for prop_name, definition in EDITABLE_ASSET_VARIABLES[game_type_id].items():
            defaults[prop_name] = definition["default"]
    return defaults

DEFAULT_MAP_WIDTH_TILES = 40
DEFAULT_MAP_HEIGHT_TILES = 25
DEFAULT_BACKGROUND_COLOR_TUPLE: Tuple[int,int,int] = getattr(C, 'LIGHT_BLUE', (173,216,230))
FONT_FAMILY_UI_DEFAULT = "Arial"
FONT_SIZE_SMALL = 9; FONT_SIZE_MEDIUM = 10; FONT_SIZE_LARGE = 12
FONT_CATEGORY_TITLE_SIZE = 11; FONT_CATEGORY_TITLE_BOLD = True
COLOR_PICKER_PRESETS: Dict[str, Tuple[int,int,int]] = {
    "Light Blue": getattr(C, 'LIGHT_BLUE', (173,216,230)), "White": getattr(C, 'WHITE', (255,255,255)),
    "Magenta": getattr(C, 'MAGENTA', (255, 0, 255))
}
STATUS_BAR_MESSAGE_TIMEOUT = 3000
LOG_LEVEL = "DEBUG"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
LOG_FILE_NAME = "editor_qt_debug.log"