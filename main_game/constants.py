# main_game/constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
Dynamically sets MAPS_DIR based on execution environment (development vs. PyInstaller bundle).
Map paths now refer to map_name_folder/map_name_file.py structure.
MODIFIED: Updated PROJECT_ROOT definition and all asset paths to reflect new structure.
"""
# version 2.1.3 (Asset path refactor applied)

import os
import sys
import math

# --- Per-script logging toggle (for debugging this file itself) ---
_SCRIPT_LOGGING_ENABLED = True
# --- End per-script logging toggle ---

# --- Project Root ---
try:
    # Assumes constants.py is in 'main_game/' directory, which is under the project root.
    _CONSTANTS_PY_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(_CONSTANTS_PY_DIR) # This should now be the actual project root
except NameError:
    PROJECT_ROOT = os.getcwd() # Fallback
    if _SCRIPT_LOGGING_ENABLED:
        print(f"CONSTANTS.PY WARNING: __file__ not defined, PROJECT_ROOT defaulted to CWD: {PROJECT_ROOT}")

# --- Gameplay / Physics / Screen Dimensions ---
GAME_WIDTH = 960
GAME_HEIGHT = 600
TILE_SIZE = 40.0
FPS = 60

PLAYER_ROLL_CONTROL_ACCEL_FACTOR = 0.4
PLAYER_ACCEL = 0.5
PLAYER_FRICTION = -0.15
PLAYER_GRAVITY = 0.7
PLAYER_JUMP_STRENGTH = -15.0
PLAYER_RUN_SPEED_LIMIT = 7.0
PLAYER_DASH_SPEED = 18.0
PLAYER_ROLL_SPEED = 14.0
PLAYER_WALL_SLIDE_SPEED = 2.0
PLAYER_WALL_CLIMB_SPEED = -4.0
PLAYER_LADDER_CLIMB_SPEED = 3.0
PLAYER_MAX_HEALTH = 100
CHARACTER_BOUNCE_VELOCITY = 2.5
PLAYER_STOMP_BOUNCE_STRENGTH = -8.0
PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX = 8
TERMINAL_VELOCITY_Y = 18.0

MIN_WALL_OVERLAP_PX = 5.0
MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING = 0.15
MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING = 0.15
LANDING_FRICTION_MULTIPLIER = 0.8
GROUND_SNAP_THRESHOLD = 5.0
CEILING_SNAP_THRESHOLD = 2.0
MIN_SIGNIFICANT_FALL_VEL = 1.5

ANIM_FRAME_DURATION = 80

PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20
PLAYER_CROUCH_ATTACK_DAMAGE = 5
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5
CHARACTER_ATTACK_STATE_DURATION = 480

# --- Items ---
CHEST_CLOSED_SPRITE_PATH = "assets/items/chest.gif" # UPDATED
CHEST_OPEN_DISPLAY_DURATION_MS = 5000
CHEST_FADE_OUT_DURATION_MS = 1000
CHEST_ANIM_FRAME_DURATION_MS = int(ANIM_FRAME_DURATION * 0.7)
CHEST_FRICTION = -0.4
CHEST_MAX_SPEED_X = 3.0
CHEST_PUSH_ACCEL_BASE = 0.8
CHEST_MASS = 5.0

# --- Projectiles ---
FIREBALL_DAMAGE = 5
FIREBALL_SPEED = 5.0
FIREBALL_COOLDOWN = 750
FIREBALL_LIFESPAN = 2500
FIREBALL_SPRITE_PATH = "assets/weapons/fire.gif" # UPDATED
FIREBALL_DIMENSIONS = (40.0,40.0)

POISON_DAMAGE = 5
POISON_SPEED = 3.0
POISON_COOLDOWN = 1000
POISON_LIFESPAN = 3000
POISON_SPRITE_PATH = "assets/weapons/poison.gif" # UPDATED
POISON_DIMENSIONS = (40.0, 40.0)

BOLT_DAMAGE = 5
BOLT_SPEED = 5.0
BOLT_COOLDOWN = 600
BOLT_LIFESPAN = 1500
BOLT_SPRITE_PATH = "assets/weapons/bolt1_resized_11x29.gif" # UPDATED
BOLT_DIMENSIONS = (15.0, 29.0)

BLOOD_DAMAGE = 5
BLOOD_SPEED = 5.0
BLOOD_COOLDOWN = 800
BLOOD_LIFESPAN = 2000
BLOOD_SPRITE_PATH = "assets/weapons/blood.gif" # UPDATED
BLOOD_DIMENSIONS = (40.0, 40.0)

ICE_DAMAGE = 5
ICE_SPEED = 5.0
ICE_COOLDOWN = 900
ICE_LIFESPAN = 2200
ICE_SPRITE_PATH = "assets/weapons/ice.gif" # UPDATED
ICE_DIMENSIONS = (40.0, 40.0)

SHADOW_PROJECTILE_DAMAGE = 5
SHADOW_PROJECTILE_SPEED = 5
SHADOW_PROJECTILE_COOLDOWN = 800
SHADOW_PROJECTILE_LIFESPAN = 1700
SHADOW_PROJECTILE_SPRITE_PATH = "assets/weapons/shadow095.gif" # UPDATED
SHADOW_PROJECTILE_DIMENSIONS = (40.0, 40.0)

GREY_PROJECTILE_DAMAGE = 0
GREY_PROJECTILE_SPEED = 2.0
GREY_PROJECTILE_COOLDOWN = 750
GREY_PROJECTILE_LIFESPAN = 1500
GREY_PROJECTILE_SPRITE_PATH = "assets/weapons/grey.gif" # UPDATED
GREY_PROJECTILE_DIMENSIONS = (40.0, 40.0)

# --- Enemy Defaults (can be overridden by specific enemy types or properties) ---
ENEMY_MAX_HEALTH = 300
ENEMY_RUN_SPEED_LIMIT = 5.0
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250.0
ENEMY_ATTACK_RANGE = 50.0
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500
ENEMY_PATROL_DIST = 150.0
ENEMY_HIT_STUN_DURATION = 150
ENEMY_HIT_COOLDOWN = 500
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3
ENEMY_STOMP_DEATH_DURATION = 300
ENEMY_POST_ATTACK_PAUSE_DURATION = 300
ENEMY_AFLAME_SPEED_MULTIPLIER = 1.3
ENEMY_DEFLAME_SPEED_MULTIPLIER = 1.2
ENEMY_STOMP_SQUASH_DURATION_MS = 400
ENEMY_GRAVITY = PLAYER_GRAVITY # Default enemy gravity to player's

# --- Enemy Knight Specific Defaults (used if properties don't override) ---
ENEMY_KNIGHT_MAX_HEALTH_DEFAULT = 150
ENEMY_KNIGHT_BASE_SPEED_DEFAULT = ENEMY_RUN_SPEED_LIMIT * 0.75
ENEMY_KNIGHT_JUMP_STRENGTH_DEFAULT = PLAYER_JUMP_STRENGTH * 0.65
ENEMY_KNIGHT_PATROL_JUMP_CHANCE_DEFAULT = 0.015
ENEMY_KNIGHT_PATROL_JUMP_COOLDOWN_MS_DEFAULT = 2500
ENEMY_KNIGHT_ATTACK1_DAMAGE_DEFAULT = 15
ENEMY_KNIGHT_ATTACK2_DAMAGE_DEFAULT = 20
ENEMY_KNIGHT_ATTACK3_DAMAGE_DEFAULT = 25
ENEMY_KNIGHT_RUN_ATTACK_DAMAGE_DEFAULT = 12
ENEMY_KNIGHT_ATTACK1_DURATION_MS = 500
ENEMY_KNIGHT_ATTACK2_DURATION_MS = 600
ENEMY_KNIGHT_ATTACK3_DURATION_MS = 700
ENEMY_KNIGHT_RUN_ATTACK_DURATION_MS = 450
ENEMY_KNIGHT_ATTACK_COOLDOWN_MS_DEFAULT = 1800
ENEMY_KNIGHT_ATTACK_RANGE_DEFAULT = ENEMY_ATTACK_RANGE * 1.2
ENEMY_KNIGHT_DETECTION_RANGE_DEFAULT = ENEMY_DETECTION_RANGE

# --- Status Effect Durations and Damage (milliseconds / per tick) ---
ENEMY_AFLAME_DURATION_MS = 3000
ENEMY_DEFLAME_DURATION_MS = 2000
ENEMY_AFLAME_DAMAGE_PER_TICK = 5
ENEMY_AFLAME_DAMAGE_INTERVAL_MS = 100
ENEMY_FROZEN_DURATION_MS = 3000
ENEMY_DEFROST_DURATION_MS = 1000
STONE_SMASHED_DURATION_MS = 5000
ENEMY_ZAPPED_DURATION_MS = 3000
ENEMY_ZAPPED_DAMAGE_PER_TICK = 3
ENEMY_ZAPPED_DAMAGE_INTERVAL_MS = 300

PLAYER_AFLAME_DURATION_MS = 3000
PLAYER_DEFLAME_DURATION_MS = 2000
PLAYER_AFLAME_DAMAGE_PER_TICK = 5
PLAYER_AFLAME_DAMAGE_INTERVAL_MS = 100
PLAYER_FROZEN_DURATION_MS = 2800
PLAYER_DEFROST_DURATION_MS = 1200
PLAYER_ZAPPED_DURATION_MS = 3000
PLAYER_ZAPPED_DAMAGE_PER_TICK = 3
PLAYER_ZAPPED_DAMAGE_INTERVAL_MS = 300

PLAYER_AFLAME_ACCEL_MULTIPLIER = 1.15
PLAYER_AFLAME_SPEED_MULTIPLIER = 1.3
PLAYER_DEFLAME_ACCEL_MULTIPLIER = 1.1
PLAYER_DEFLAME_SPEED_MULTIPLIER = 1.05

# --- Colors (RGB tuples) ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
DARK_RED = (139, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 100, 0)
BLUE = (0, 0, 255)
LIGHT_BLUE = (173, 216, 230)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (200, 200, 200)
ORANGE_RED = (255, 69, 0)
MAGENTA = (255, 0, 255)
PURPLE_BACKGROUND = (75, 0, 130)
SAND = (244,164,96)
DRAW_ENEMY_ABOVE_HEALTH_BAR = True

# --- UI / HUD ---
HEALTH_BAR_WIDTH = 50.0
HEALTH_BAR_HEIGHT = 8.0
HEALTH_BAR_OFFSET_ABOVE = 5.0
HUD_HEALTH_BAR_WIDTH = HEALTH_BAR_WIDTH * 2.0
HUD_HEALTH_BAR_HEIGHT = HEALTH_BAR_HEIGHT + 4.0

# --- Hazards ---
LAVA_PATCH_HEIGHT = 20.0
LAVA_DAMAGE = 50
LAVA_SPRITE_PATH = "assets/environment/lava.gif" # UPDATED

# --- File System ---
def get_maps_directory():
    maps_dir_name = "maps"
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir_meipass = sys._MEIPASS # type: ignore
        bundled_maps_path = os.path.join(bundle_dir_meipass, maps_dir_name)
        if os.path.isdir(bundled_maps_path): return os.path.normpath(bundled_maps_path)
        exe_dir = os.path.dirname(sys.executable)
        maps_next_to_exe = os.path.join(exe_dir, maps_dir_name)
        if os.path.isdir(maps_next_to_exe): return os.path.normpath(maps_next_to_exe)
        return os.path.normpath(bundled_maps_path)
    else:
        if PROJECT_ROOT: # PROJECT_ROOT is now the actual project root
            return os.path.normpath(os.path.join(PROJECT_ROOT, maps_dir_name))
        else:
            if _SCRIPT_LOGGING_ENABLED:
                print("CONSTANTS.PY ERROR: PROJECT_ROOT not determined for development. MAPS_DIR defaulting to './maps'.")
            return os.path.normpath(maps_dir_name)

MAPS_DIR = get_maps_directory()

# --- Networking ---
SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
SERVICE_NAME = "platformer_adventure_lan_v1"
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 8192
BROADCAST_INTERVAL_S = 1.0
CLIENT_SEARCH_TIMEOUT_S = 5.0
MAP_DOWNLOAD_CHUNK_SIZE = 4096

# --- Editor Specific ---
EDITOR_SCREEN_INITIAL_WIDTH = 2000
EDITOR_SCREEN_INITIAL_HEIGHT = 1000
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json"
GAME_LEVEL_FILE_EXTENSION = ".py"

# --- Gameplay Modifiers / Toggles ---
PLAYER_SELF_DAMAGE = 10
ALLOW_SELF_FIREBALL_DAMAGE = False
ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP = False

# --- Player State Durations (milliseconds) ---
PLAYER_DASH_DURATION = 150
PLAYER_ROLL_DURATION = 1000
PLAYER_SLIDE_DURATION = 400
PLAYER_WALL_CLIMB_DURATION = 500
PLAYER_COMBO_WINDOW = 250
PLAYER_HIT_STUN_DURATION = 300
PLAYER_HIT_COOLDOWN = 600

# --- Player Projectile Configuration ---
PROJECTILE_CONFIG_ORDER = ["fireball", "poison", "bolt", "blood", "ice", "shadow_projectile", "grey_projectile"]
P1_FIREBALL_KEY = "1"; P1_POISON_KEY = "2"; P1_BOLT_KEY = "3"; P1_BLOOD_KEY = "4"; P1_ICE_KEY = "5"; P1_SHADOW_PROJECTILE_KEY = "6"; P1_GREY_PROJECTILE_KEY = "7"
P2_FIREBALL_KEY = "Numpad8"; P2_POISON_KEY = "Numpad9"; P2_BOLT_KEY = "Numpad0"; P2_BLOOD_KEY = "NumpadDecimal"; P2_ICE_KEY = "NumpadSubtract"; P2_SHADOW_PROJECTILE_KEY = "NumpadAdd"; P2_GREY_PROJECTILE_KEY = "NumpadEnter"
P3_FIREBALL_KEY = "F1"; P3_POISON_KEY = "F2"; P3_BOLT_KEY = "F3"; P3_BLOOD_KEY = "F4"; P3_ICE_KEY = "F5"; P3_SHADOW_PROJECTILE_KEY = "F6"; P3_GREY_PROJECTILE_KEY = "F7"
P4_FIREBALL_KEY = "F8"; P4_POISON_KEY = "F9"; P4_BOLT_KEY = "F10"; P4_BLOOD_KEY = "F11"; P4_ICE_KEY = "F12"; P4_SHADOW_PROJECTILE_KEY = "Insert"; P4_GREY_PROJECTILE_KEY = "Delete"

# --- Input Handling Constants ---
JOYSTICK_AXIS_EVENT_ACTIONS = [
    "jump", "crouch", "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset", "menu_confirm", "menu_cancel",
    "up", "down"
]
JOYSTICK_HAT_EVENT_ACTIONS = [
    "jump", "crouch",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "menu_up", "menu_down", "menu_left", "menu_right",
    "menu_confirm", "menu_cancel", "pause", "reset",
    "up", "down", "left", "right"
]
MAX_JOYSTICK_INSTANCE_IDS_FOR_PREV_STATE = 16 # For config.py's prev_button_state list

# --- Asset Paths (Updated or to be removed if unused) ---
ASSETS_SPRITES_DIR = "assets" # Changed to the new root assets folder
ASSETS_SOUNDS_DIR = "assets/sounds" # Assuming sounds are in a subfolder

# --- Game States ---
STATE_MENU = "MENU"; STATE_PLAYING = "PLAYING"; STATE_GAME_OVER = "GAME_OVER"
STATE_PAUSED = "PAUSED"; STATE_LEVEL_EDITOR = "LEVEL_EDITOR"

if _SCRIPT_LOGGING_ENABLED:
    print(f"CONSTANTS.PY: PROJECT_ROOT determined as: {PROJECT_ROOT}")
    print(f"CONSTANTS.PY: MAPS_DIR (base maps folder) determined as: {MAPS_DIR}")
    print(f"CONSTANTS.PY: ASSETS_SPRITES_DIR set to: {ASSETS_SPRITES_DIR}")
    print(f"CONSTANTS.PY: CHEST_CLOSED_SPRITE_PATH set to: {CHEST_CLOSED_SPRITE_PATH}")