#################### START OF FILE: constants.py ####################
# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
Dynamically sets MAPS_DIR based on execution environment (development vs. PyInstaller bundle).
"""
# version 2.1.0 (Added Editor specific constants, removed semicolons)
import os
import sys
import math

# --- Per-script logging toggle ---
_SCRIPT_LOGGING_ENABLED = True
# --- End per-script logging toggle ---

# --- Project Root ---
try:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    PROJECT_ROOT = os.getcwd()
    if _SCRIPT_LOGGING_ENABLED:
        print(f"CONSTANTS.PY WARNING: __file__ not defined, PROJECT_ROOT defaulted to CWD: {PROJECT_ROOT}")

# --- Gameplay / Physics / Screen Dimensions ---
GAME_WIDTH = 960
GAME_HEIGHT = 600
TILE_SIZE = 40.0 # Changed to float for consistency
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

ANIM_FRAME_DURATION = 80 # milliseconds

PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20
PLAYER_CROUCH_ATTACK_DAMAGE = 5
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5
CHARACTER_ATTACK_STATE_DURATION = 480 # milliseconds

CHEST_CLOSED_SPRITE_PATH = "characters/items/chest.gif"
CHEST_OPEN_DISPLAY_DURATION_MS = 5000
CHEST_FADE_OUT_DURATION_MS = 1000
CHEST_ANIM_FRAME_DURATION_MS = int(ANIM_FRAME_DURATION * 0.7)
CHEST_FRICTION = -0.12
CHEST_MAX_SPEED_X = 3.0
CHEST_PUSH_ACCEL_BASE = 0.8
CHEST_MASS = 5.0

FIREBALL_DAMAGE = 50
FIREBALL_SPEED = 9.0
FIREBALL_COOLDOWN = 750 # milliseconds
FIREBALL_LIFESPAN = 2500 # milliseconds
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"
FIREBALL_DIMENSIONS = (61.0, 58.0)

POISON_DAMAGE = 20
POISON_SPEED = 6.0
POISON_COOLDOWN = 1000 # milliseconds
POISON_LIFESPAN = 3000 # milliseconds
POISON_SPRITE_PATH = "characters/weapons/poison.gif"
POISON_DIMENSIONS = (40.0, 40.0)

BOLT_DAMAGE = 35
BOLT_SPEED = 5.0
BOLT_COOLDOWN = 600 # milliseconds
BOLT_LIFESPAN = 1500 # milliseconds
BOLT_SPRITE_PATH = "characters/weapons/bolt1_resized_11x29.gif"
BOLT_DIMENSIONS = (11.0, 29.0)

BLOOD_DAMAGE = 30
BLOOD_SPEED = 8.0
BLOOD_COOLDOWN = 800 # milliseconds
BLOOD_LIFESPAN = 2000 # milliseconds
BLOOD_SPRITE_PATH = "characters/weapons/blood.gif"
BLOOD_DIMENSIONS = (40.0, 40.0)

ICE_DAMAGE = 10
ICE_SPEED = 5.0
ICE_COOLDOWN = 900 # milliseconds
ICE_LIFESPAN = 2200 # milliseconds
ICE_SPRITE_PATH = "characters/weapons/ice.gif"
ICE_DIMENSIONS = (40.0, 40.0)

SHADOW_PROJECTILE_DAMAGE = 45
SHADOW_PROJECTILE_SPEED = 11.0
SHADOW_PROJECTILE_COOLDOWN = 800 # milliseconds
SHADOW_PROJECTILE_LIFESPAN = 1700 # milliseconds
SHADOW_PROJECTILE_SPRITE_PATH = "characters/weapons/shadow095.gif"
SHADOW_PROJECTILE_DIMENSIONS = (40.0, 40.0)

GREY_PROJECTILE_DAMAGE = 0 # Example utility projectile
GREY_PROJECTILE_SPEED = 5.0
GREY_PROJECTILE_COOLDOWN = 750 # milliseconds
GREY_PROJECTILE_LIFESPAN = 1500 # milliseconds
GREY_PROJECTILE_SPRITE_PATH = "characters/weapons/grey.gif" # Placeholder
GREY_PROJECTILE_DIMENSIONS = (40.0, 40.0)

ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5.0
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250.0
ENEMY_ATTACK_RANGE = 70.0
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500 # milliseconds
ENEMY_PATROL_DIST = 150.0
ENEMY_HIT_STUN_DURATION = 300 # milliseconds
ENEMY_HIT_COOLDOWN = 500 # milliseconds
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3
ENEMY_STOMP_DEATH_DURATION = 300 # milliseconds
ENEMY_POST_ATTACK_PAUSE_DURATION = 200 # milliseconds
ENEMY_AFLAME_SPEED_MULTIPLIER = 1.3
ENEMY_DEFLAME_SPEED_MULTIPLIER = 1.2
ENEMY_STOMP_SQUASH_DURATION_MS = 400 # milliseconds

ENEMY_AFLAME_DURATION_MS = 3000
ENEMY_DEFLAME_DURATION_MS = 2000
ENEMY_AFLAME_DAMAGE_PER_TICK = 5
ENEMY_AFLAME_DAMAGE_INTERVAL_MS = 500
ENEMY_FROZEN_DURATION_MS = 3000
ENEMY_DEFROST_DURATION_MS = 1000
STONE_SMASHED_DURATION_MS = 5000

PLAYER_AFLAME_DURATION_MS = 3000
PLAYER_DEFLAME_DURATION_MS = 3000
PLAYER_AFLAME_DAMAGE_PER_TICK = 5
PLAYER_AFLAME_DAMAGE_INTERVAL_MS = 1000
PLAYER_FROZEN_DURATION_MS = 2800
PLAYER_DEFROST_DURATION_MS = 1200

PLAYER_AFLAME_ACCEL_MULTIPLIER = 1.15
PLAYER_AFLAME_SPEED_MULTIPLIER = 1.1
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
LIGHT_BLUE = (173, 216, 230) # Often used as default background
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (200, 200, 200)
ORANGE_RED = (255, 69, 0)
MAGENTA = (255, 0, 255)
PURPLE_BACKGROUND = (75, 0, 130)
SAND = (244,164,96) # Added from editor_config for consistency

# --- UI / HUD ---
HEALTH_BAR_WIDTH = 50.0
HEALTH_BAR_HEIGHT = 8.0
HEALTH_BAR_OFFSET_ABOVE = 5.0
HUD_HEALTH_BAR_WIDTH = HEALTH_BAR_WIDTH * 2.0
HUD_HEALTH_BAR_HEIGHT = HEALTH_BAR_HEIGHT + 4.0

# --- Hazards ---
LAVA_PATCH_HEIGHT = 20.0 # Example, can be overridden by placed object size
LAVA_DAMAGE = 25
LAVA_SPRITE_PATH = "characters/assets/lava.gif" # Used by editor for default lava tile

# --- File System ---
def get_maps_directory():
    """Determines the maps directory path."""
    # If running as a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # _MEIPASS is the temporary folder where bundled files are extracted
        bundle_dir_meipass = sys._MEIPASS # type: ignore
        bundled_maps_path = os.path.join(bundle_dir_meipass, 'maps')
        if os.path.isdir(bundled_maps_path):
            return bundled_maps_path
        # Fallback: check next to executable if not found in _MEIPASS/maps
        exe_dir = os.path.dirname(sys.executable)
        maps_next_to_exe = os.path.join(exe_dir, 'maps')
        if os.path.isdir(maps_next_to_exe):
            return maps_next_to_exe
        # If still not found, default to the _MEIPASS path (might be an issue with bundle structure)
        return bundled_maps_path
    else:
        # Development mode: 'maps' directory in the project root
        if PROJECT_ROOT:
            return os.path.join(PROJECT_ROOT, 'maps')
        else:
            # Absolute fallback if PROJECT_ROOT failed (should be rare)
            if _SCRIPT_LOGGING_ENABLED:
                print("CONSTANTS.PY ERROR: PROJECT_ROOT not determined. MAPS_DIR defaulting to './maps' relative to CWD.")
            return 'maps'
MAPS_DIR = get_maps_directory()

# --- Networking (if applicable) ---
SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
SERVICE_NAME = "platformer_adventure_lan_v1" # For service discovery
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 8192 # bytes
BROADCAST_INTERVAL_S = 1.0 # seconds
CLIENT_SEARCH_TIMEOUT_S = 5.0 # seconds
MAP_DOWNLOAD_CHUNK_SIZE = 4096 # bytes

# --- Editor Specific (can be overridden or augmented by editor_config.py) ---
# These are game-related defaults that the editor might use or expose.
EDITOR_SCREEN_INITIAL_WIDTH = 1380
EDITOR_SCREEN_INITIAL_HEIGHT = 820
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json" # Editor's own save format
GAME_LEVEL_FILE_EXTENSION = ".py"          # Format the game loads

# --- Gameplay Modifiers / Toggles ---
PLAYER_SELF_DAMAGE = 10 # Example for testing friendly fire
ALLOW_SELF_FIREBALL_DAMAGE = False
ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP = False # If true, game might auto-add a chest

# --- Player State Durations (milliseconds) ---
PLAYER_DASH_DURATION = 150
PLAYER_ROLL_DURATION = 1000
PLAYER_SLIDE_DURATION = 400
PLAYER_WALL_CLIMB_DURATION = 500
PLAYER_COMBO_WINDOW = 250 # Time window to chain combo attacks
PLAYER_HIT_STUN_DURATION = 300 # How long player is stunned when hit
PLAYER_HIT_COOLDOWN = 600 # Invulnerability after being hit

# --- Player Projectile Keys (Defaults for display/reference) ---
# Actual input mapping is handled by input_manager and config.py
P1_FIREBALL_KEY = "1"
P1_POISON_KEY = "2"
P1_BOLT_KEY = "3"
P1_BLOOD_KEY = "4"
P1_ICE_KEY = "5"
P1_SHADOW_PROJECTILE_KEY = "6"
P1_GREY_PROJECTILE_KEY = "7"

P2_FIREBALL_KEY = "Numpad8"
P2_POISON_KEY = "Numpad9"
P2_BOLT_KEY = "Numpad0"
P2_BLOOD_KEY = "NumpadDecimal"
P2_ICE_KEY = "NumpadSubtract"
P2_SHADOW_PROJECTILE_KEY = "NumpadAdd"
P2_GREY_PROJECTILE_KEY = "NumpadEnter"

P3_FIREBALL_KEY = "F1"
P3_POISON_KEY = "F2"
P3_BOLT_KEY = "F3"
P3_BLOOD_KEY = "F4"
P3_ICE_KEY = "F5"
P3_SHADOW_PROJECTILE_KEY = "F6"
P3_GREY_PROJECTILE_KEY = "F7"

P4_FIREBALL_KEY = "F8"
P4_POISON_KEY = "F9"
P4_BOLT_KEY = "F10"
P4_BLOOD_KEY = "F11"
P4_ICE_KEY = "F12"
P4_SHADOW_PROJECTILE_KEY = "Insert"
P4_GREY_PROJECTILE_KEY = "Delete"

# --- Input Handling Constants (used by input_manager) ---
# Lists of actions that might be triggered by joystick axes or hats beyond simple movement
JOYSTICK_AXIS_EVENT_ACTIONS = [
    "jump", "crouch", "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset", "menu_confirm", "menu_cancel",
    "up", "down" # For UI navigation or aiming
]
JOYSTICK_HAT_EVENT_ACTIONS = [
    "jump", "crouch", # Example: D-Pad Up/Down for Jump/Crouch
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", # Example: D-Pad directions for projectiles
    "menu_up", "menu_down", "menu_left", "menu_right",
    "menu_confirm", "menu_cancel", "pause", "reset",
    "up", "down", "left", "right" # General D-Pad directions
]

MAX_JOYSTICK_INSTANCE_IDS_FOR_PREV_STATE = 16 # For tracking previous states of multiple joysticks

# --- Asset Paths (examples, game should manage its own comprehensive asset loading) ---
# This file primarily defines gameplay constants. Specific asset paths are better managed
# by an asset loading system or defined directly where used if simple.
# However, some default paths used by editor for palette items can be here.
ASSETS_SPRITES_DIR = "assets/sprites" # Example, if you centralize sprites
ASSETS_SOUNDS_DIR = "assets/sounds"   # Example

# --- Game States (example enum-like constants) ---
STATE_MENU = "MENU"
STATE_PLAYING = "PLAYING"
STATE_GAME_OVER = "GAME_OVER"
STATE_PAUSED = "PAUSED"
STATE_LEVEL_EDITOR = "LEVEL_EDITOR" # If editor is launched from game

if _SCRIPT_LOGGING_ENABLED:
    print(f"CONSTANTS.PY: PROJECT_ROOT determined as: {PROJECT_ROOT}")
    print(f"CONSTANTS.PY: MAPS_DIR determined as: {MAPS_DIR}")

#################### END OF FILE: constants.py ####################