# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
Dynamically sets MAPS_DIR based on execution environment (development vs. PyInstaller bundle).
"""
# version 2.0.2 (Added LAVA_SPRITE_PATH, clarified some comments)
import os
import sys

# --- Project Root (useful for resolving relative paths if needed elsewhere) ---
# Assumes constants.py is in the project root directory.
# If it's in a subdirectory, this needs to be adjusted, or PROJECT_ROOT should
# be set by the main entry script of your application.
try:
    # This assumes the script that imports constants.py is in the project root,
    # or that the project root is already in sys.path.
    # For robustness, especially if constants.py might be imported from different locations
    # (e.g., editor scripts vs. main game scripts), it's better if the main application
    # sets a well-defined project root if needed by other modules.
    # However, for `resource_path` in `assets.py`, `os.path.dirname(os.path.abspath(__file__))`
    # where __file__ refers to assets.py itself, is more direct for finding assets relative to assets.py.
    # For MAPS_DIR, we want it relative to the project structure.
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # __file__ is not defined if running in some interactive interpreters or frozen apps without this info.
    # Fallback to current working directory, but this can be unreliable.
    PROJECT_ROOT = os.getcwd()
    print(f"CONSTANTS.PY WARNING: __file__ not defined, PROJECT_ROOT defaulted to CWD: {PROJECT_ROOT}")


# --- Gameplay / Physics / Screen Dimensions ---
GAME_WIDTH = 960  # Default game logical width
GAME_HEIGHT = 600 # Default game logical height
TILE_SIZE = 40.0 # Use float for consistency in calculations
FPS = 60

PLAYER_ROLL_CONTROL_ACCEL_FACTOR = 0.4
PLAYER_ACCEL = 0.5
PLAYER_FRICTION = -0.15  # Negative value!
PLAYER_GRAVITY = 0.7 # Acceleration per frame (if dt is fixed at 1/FPS) or per second (if dt is variable time)
PLAYER_JUMP_STRENGTH = -15.0 # Initial upward velocity change
PLAYER_RUN_SPEED_LIMIT = 7.0
PLAYER_DASH_SPEED = 18.0
PLAYER_ROLL_SPEED = 14.0
PLAYER_WALL_SLIDE_SPEED = 2.0
PLAYER_WALL_CLIMB_SPEED = -4.0    # Negative for upward movement
PLAYER_LADDER_CLIMB_SPEED = 3.0
PLAYER_MAX_HEALTH = 100
CHARACTER_BOUNCE_VELOCITY = 2.5
PLAYER_STOMP_BOUNCE_STRENGTH = -8.0
PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX = 8
TERMINAL_VELOCITY_Y = 18.0 # Maximum downward speed

# Collision Specifics
MIN_WALL_OVERLAP_PX = 5.0 # Min horizontal overlap to be considered 'touching wall'
MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING = 0.15 # Percentage of player width needed to land
MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING = 0.15
LANDING_FRICTION_MULTIPLIER = 0.8
GROUND_SNAP_THRESHOLD = 5.0 # Max distance to snap down to ground
CEILING_SNAP_THRESHOLD = 2.0  # Max distance to snap up to ceiling
MIN_SIGNIFICANT_FALL_VEL = 1.5 # Min Y velocity to trigger 'fall' animation

# --- Animation ---
ANIM_FRAME_DURATION = 80 # ms per frame for most animations

# Player Attack Specifics
PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20
PLAYER_CROUCH_ATTACK_DAMAGE = 5
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5 # attack2 animation plays slower
CHARACTER_ATTACK_STATE_DURATION = 480 # ms (default duration if not derived from animation frames)

# --- Item Constants ---
CHEST_CLOSED_SPRITE_PATH = "characters/items/chest.gif" # Path relative to project root via resource_path
CHEST_STAY_OPEN_DURATION_MS = 3000 # Not currently used if chest stays open indefinitely
CHEST_FADE_OUT_DURATION_MS = 1000  # Not currently used

# --- Projectile Constants ---
# Fireball (Key 1)
FIREBALL_DAMAGE = 50
FIREBALL_SPEED = 9.0
FIREBALL_COOLDOWN = 750 # ms
FIREBALL_LIFESPAN = 2500 # ms
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"
FIREBALL_DIMENSIONS = (61.0, 58.0) # Use floats

# Poison (Key 2)
POISON_DAMAGE = 20
POISON_SPEED = 6.0
POISON_COOLDOWN = 1000 # ms
POISON_LIFESPAN = 3000 # ms
POISON_SPRITE_PATH = "characters/weapons/poison.gif"
POISON_DIMENSIONS = (40.0, 40.0)

# Bolt (Key 3)
BOLT_DAMAGE = 35
BOLT_SPEED = 15.0
BOLT_COOLDOWN = 600 # ms
BOLT_LIFESPAN = 1500 # ms
BOLT_SPRITE_PATH = "characters/weapons/bolt1_resized_11x29.gif"
BOLT_DIMENSIONS = (11.0, 29.0)

# Blood (Key 4)
BLOOD_DAMAGE = 30
BLOOD_SPEED = 8.0
BLOOD_COOLDOWN = 800 # ms
BLOOD_LIFESPAN = 2000 # ms
BLOOD_SPRITE_PATH = "characters/weapons/blood.gif"
BLOOD_DIMENSIONS = (40.0, 40.0)

# Ice (Key 5)
ICE_DAMAGE = 10
ICE_SPEED = 5.0
ICE_COOLDOWN = 900 # ms
ICE_LIFESPAN = 2200 # ms
ICE_SPRITE_PATH = "characters/weapons/ice.gif"
ICE_DIMENSIONS = (40.0, 40.0)

# Shadow Projectile (Key 6)
SHADOW_PROJECTILE_DAMAGE = 45
SHADOW_PROJECTILE_SPEED = 11.0
SHADOW_PROJECTILE_COOLDOWN = 800 # ms
SHADOW_PROJECTILE_LIFESPAN = 1700 # ms
SHADOW_PROJECTILE_SPRITE_PATH = "characters/weapons/shadow095.gif"
SHADOW_PROJECTILE_DIMENSIONS = (40.0, 40.0)

# Grey Projectile (Key 7)
GREY_PROJECTILE_DAMAGE = 0 # Deals no direct damage, petrifies
GREY_PROJECTILE_SPEED = 5.0
GREY_PROJECTILE_COOLDOWN = 750 # ms
GREY_PROJECTILE_LIFESPAN = 1500 # ms
GREY_PROJECTILE_SPRITE_PATH = "characters/weapons/grey.gif"
GREY_PROJECTILE_DIMENSIONS = (40.0, 40.0)

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5.0
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250.0
ENEMY_ATTACK_RANGE = 70.0
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500 # ms
ENEMY_PATROL_DIST = 150.0
ENEMY_HIT_STUN_DURATION = 300 # ms
ENEMY_HIT_COOLDOWN = 500 # ms
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3 # Relative to player jump for consistency
ENEMY_STOMP_DEATH_DURATION = 300 # ms (duration of stomp visual before fully gone)
ENEMY_POST_ATTACK_PAUSE_DURATION = 200 # ms
ENEMY_AFLAME_SPEED_MULTIPLIER = 1.3
ENEMY_DEFLAME_SPEED_MULTIPLIER = 1.2
ENEMY_STOMP_SQUASH_DURATION_MS = 400 # Visual squash duration

# --- Enemy Status Effect Constants ---
ENEMY_AFLAME_DURATION_MS = 3000
ENEMY_DEFLAME_DURATION_MS = 2000
ENEMY_AFLAME_DAMAGE_PER_TICK = 5
ENEMY_AFLAME_DAMAGE_INTERVAL_MS = 500
ENEMY_FROZEN_DURATION_MS = 3000
ENEMY_DEFROST_DURATION_MS = 1000

# --- Petrification Constants ---
STONE_SMASHED_DURATION_MS = 5000 # How long smashed remains appear

# --- Player Status Effect Constants ---
PLAYER_AFLAME_DURATION_MS = 3000
PLAYER_DEFLAME_DURATION_MS = 3000
PLAYER_AFLAME_DAMAGE_PER_TICK = 5
PLAYER_AFLAME_DAMAGE_INTERVAL_MS = 1000
PLAYER_FROZEN_DURATION_MS = 2800
PLAYER_DEFROST_DURATION_MS = 1200

# --- Player Speed Multipliers ---
PLAYER_AFLAME_ACCEL_MULTIPLIER = 1.15
PLAYER_AFLAME_SPEED_MULTIPLIER = 1.1
PLAYER_DEFLAME_ACCEL_MULTIPLIER = 1.1
PLAYER_DEFLAME_SPEED_MULTIPLIER = 1.05

# --- Colors (RGB Tuples) ---
WHITE = (255, 255, 255); BLACK = (0, 0, 0); RED = (255, 0, 0)
DARK_RED = (139, 0, 0); GREEN = (0, 255, 0); DARK_GREEN = (0, 100, 0)
BLUE = (0, 0, 255); LIGHT_BLUE = (173, 216, 230); YELLOW = (255, 255, 0)
GRAY = (128, 128, 128); DARK_GRAY = (50, 50, 50); LIGHT_GRAY = (200, 200, 200)
ORANGE_RED = (255, 69, 0); MAGENTA = (255, 0, 255)
PURPLE_BACKGROUND = (75, 0, 130)

# --- UI ---
HEALTH_BAR_WIDTH = 50.0 
HEALTH_BAR_HEIGHT = 8.0
HEALTH_BAR_OFFSET_ABOVE = 5.0
HUD_HEALTH_BAR_WIDTH = HEALTH_BAR_WIDTH * 2.0
HUD_HEALTH_BAR_HEIGHT = HEALTH_BAR_HEIGHT + 4.0

# --- Map ---
LAVA_PATCH_HEIGHT = 20.0 # Default height for procedural lava if not using GIF dimensions
LAVA_DAMAGE = 25
LAVA_SPRITE_PATH = "characters/assets/lava.gif" # Path for animated lava

def get_maps_directory():
    """
    Determines the absolute path to the 'maps' directory.
    Relies on PROJECT_ROOT being correctly defined at the top of this file.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir_meipass = sys._MEIPASS
        bundled_maps_path = os.path.join(bundle_dir_meipass, 'maps')
        if os.path.isdir(bundled_maps_path):
            return bundled_maps_path
        exe_dir = os.path.dirname(sys.executable)
        maps_next_to_exe = os.path.join(exe_dir, 'maps')
        if os.path.isdir(maps_next_to_exe):
            return maps_next_to_exe
        return bundled_maps_path 
    else:
        # Development mode: 'maps' directory in the project root
        # Ensure PROJECT_ROOT is defined correctly at the top of this file.
        if PROJECT_ROOT:
            return os.path.join(PROJECT_ROOT, 'maps')
        else: # Fallback if PROJECT_ROOT couldn't be determined
            print("CONSTANTS.PY ERROR: PROJECT_ROOT not determined. MAPS_DIR will be relative to CWD.")
            return 'maps'

MAPS_DIR = get_maps_directory()

# --- Network Constants ---
SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
SERVICE_NAME = "platformer_adventure_lan_v1" 
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 8192 
BROADCAST_INTERVAL_S = 1.0 
CLIENT_SEARCH_TIMEOUT_S = 5.0 
MAP_DOWNLOAD_CHUNK_SIZE = 4096 

# --- Editor Specific Constants (referenced by editor_config.py) ---
EDITOR_SCREEN_INITIAL_WIDTH = 1380
EDITOR_SCREEN_INITIAL_HEIGHT = 820
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json" 
GAME_LEVEL_FILE_EXTENSION = ".py"           

# --- Other ---
PLAYER_SELF_DAMAGE = 10
ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP = False # Set to True to enable fallback chest spawn

# --- Player Ability Durations/Cooldowns ---
PLAYER_DASH_DURATION = 150 # ms
PLAYER_ROLL_DURATION = 1000 # ms
PLAYER_SLIDE_DURATION = 400 # ms
PLAYER_WALL_CLIMB_DURATION = 500 # ms
PLAYER_COMBO_WINDOW = 250 # ms
PLAYER_HIT_STUN_DURATION = 300 # ms
PLAYER_HIT_COOLDOWN = 600 # ms

# --- Player Projectile Keys (Defaults, actual mapping via config.py) ---
P1_FIREBALL_KEY = "7"
P1_POISON_KEY = "2"
P1_BOLT_KEY = "3"
P1_BLOOD_KEY = "4"
P1_ICE_KEY = "5"
P1_SHADOW_PROJECTILE_KEY = "6"
P1_GREY_PROJECTILE_KEY = "1"

P2_FIREBALL_KEY = "Num+1"
P2_POISON_KEY = "Num+2"
P2_BOLT_KEY = "Num+3"
P2_BLOOD_KEY = "Num+4"
P2_ICE_KEY = "Num+5"
P2_SHADOW_PROJECTILE_KEY = "Num+6"
P2_GREY_PROJECTILE_KEY = "Num+7"

# --- Input Handling Constants (Internal action names for joystick mapping) ---
JOYSTICK_HAT_EVENT_ACTIONS = [
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "menu_up", "menu_down", "menu_left", "menu_right",
    "menu_confirm", "menu_cancel", "pause", "reset"
]

JOYSTICK_AXIS_EVENT_ACTIONS = [
    "jump", "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "menu_confirm", "menu_cancel", "reset"
]

# --- Qt Type Aliases (Optional, if you want to avoid direct PySide6 imports elsewhere for these specific types) ---
# from PySide6.QtCore import QRectF, QPointF # Example
# QT_RECTF_TYPE = QRectF
# QT_POINTF_TYPE = QPointF
# Using them directly (e.g., `from PySide6.QtCore import QRectF`) in modules that need them is often clearer.