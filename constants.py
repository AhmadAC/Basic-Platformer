#################### START OF FILE: constants.py ####################

# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
Dynamically sets MAPS_DIR based on execution environment.
"""
# version 2.1.0 (Incorporated common stone asset paths and zapped effect constants)
# MODIFIED: Added ENEMY_ZAPPED constants (version 2.1.1)
import os
import sys
import math

# --- Per-script logging toggle ---
_SCRIPT_LOGGING_ENABLED = True # Set to False to suppress print statements from this file during init
# --- End per-script logging toggle ---

# --- Project Root ---
try:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError: # Fallback if __file__ is not defined (e.g., in some frozen environments)
    PROJECT_ROOT = os.getcwd()
    if _SCRIPT_LOGGING_ENABLED:
        print(f"CONSTANTS.PY WARNING: __file__ not defined, PROJECT_ROOT defaulted to CWD: {PROJECT_ROOT}")

# --- Gameplay / Physics / Screen Dimensions ---
GAME_WIDTH = 960
GAME_HEIGHT = 600
TILE_SIZE = 40.0  # Master tile size, used for grid and scaling
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
# PLAYER_WALL_CLIMB_SPEED = -4.0 # Wall climb was removed
PLAYER_LADDER_CLIMB_SPEED = 3.0
PLAYER_MAX_HEALTH = 100
CHARACTER_BOUNCE_VELOCITY = 2.5 # General bounce when characters collide
PLAYER_STOMP_BOUNCE_STRENGTH = -8.0
PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX = 8 # How many pixels player's feet can be "inside" enemy top for stomp
TERMINAL_VELOCITY_Y = 18.0 # Max falling speed

MIN_WALL_OVERLAP_PX = 5.0 # Min overlap to register as wall touch
MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING = 0.15 # Percentage of player width needed to land
MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING = 0.15 # Percentage of player width to register ceiling hit
LANDING_FRICTION_MULTIPLIER = 0.8 # Reduce horizontal speed on landing
GROUND_SNAP_THRESHOLD = 5.0 # How many pixels below a platform top the player can be to "snap" to it
CEILING_SNAP_THRESHOLD = 2.0 # How many pixels above a platform bottom the player can be to "snap" to it
MIN_SIGNIFICANT_FALL_VEL = 1.5 # Min Y velocity to trigger 'fall' animation if not jumping

ANIM_FRAME_DURATION = 80 # Milliseconds per animation frame (base)

# --- Items ---
CHEST_CLOSED_SPRITE_PATH = "characters/items/chest.gif"
CHEST_OPEN_DISPLAY_DURATION_MS = 3000 # How long chest stays open visually
CHEST_FADE_OUT_DURATION_MS = 1000   # How long chest takes to fade after display
CHEST_ANIM_FRAME_DURATION_MS = int(ANIM_FRAME_DURATION * 0.7) # Faster anim for chest
CHEST_FRICTION = -0.12
CHEST_MAX_SPEED_X = 3.0
CHEST_PUSH_ACCEL_BASE = 0.8
CHEST_MASS = 5.0 # For physics interactions (conceptual for now)

# --- Projectiles ---
# (Damage, Speed, Cooldown_ms, Lifespan_ms, Sprite_Path, Dimensions_tuple)
FIREBALL_DAMAGE = 50; FIREBALL_SPEED = 9.0; FIREBALL_COOLDOWN = 750; FIREBALL_LIFESPAN = 2500
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"; FIREBALL_DIMENSIONS = (61.0, 58.0)

POISON_DAMAGE = 20; POISON_SPEED = 6.0; POISON_COOLDOWN = 1000; POISON_LIFESPAN = 3000
POISON_SPRITE_PATH = "characters/weapons/poison.gif"; POISON_DIMENSIONS = (40.0, 40.0)

BOLT_DAMAGE = 35; BOLT_SPEED = 5.0; BOLT_COOLDOWN = 600; BOLT_LIFESPAN = 1500
BOLT_SPRITE_PATH = "characters/weapons/bolt1_resized_11x29.gif"; BOLT_DIMENSIONS = (11.0, 29.0)

BLOOD_DAMAGE = 30; BLOOD_SPEED = 8.0; BLOOD_COOLDOWN = 800; BLOOD_LIFESPAN = 2000
BLOOD_SPRITE_PATH = "characters/weapons/blood.gif"; BLOOD_DIMENSIONS = (40.0, 40.0)

ICE_DAMAGE = 10; ICE_SPEED = 5.0; ICE_COOLDOWN = 900; ICE_LIFESPAN = 2200
ICE_SPRITE_PATH = "characters/weapons/ice.gif"; ICE_DIMENSIONS = (40.0, 40.0)

SHADOW_PROJECTILE_DAMAGE = 45; SHADOW_PROJECTILE_SPEED = 11.0; SHADOW_PROJECTILE_COOLDOWN = 800; SHADOW_PROJECTILE_LIFESPAN = 1700
SHADOW_PROJECTILE_SPRITE_PATH = "characters/weapons/shadow095.gif"; SHADOW_PROJECTILE_DIMENSIONS = (40.0, 40.0)

GREY_PROJECTILE_DAMAGE = 0; GREY_PROJECTILE_SPEED = 5.0; GREY_PROJECTILE_COOLDOWN = 750; GREY_PROJECTILE_LIFESPAN = 1500
GREY_PROJECTILE_SPRITE_PATH = "characters/weapons/grey.gif"; GREY_PROJECTILE_DIMENSIONS = (40.0, 40.0)


# --- Enemy Stats ---
ENEMY_MAX_HEALTH = 80; ENEMY_RUN_SPEED_LIMIT = 5.0; ENEMY_ACCEL = 0.4; ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250.0; ENEMY_ATTACK_RANGE = 70.0; ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500; ENEMY_PATROL_DIST = 150.0; ENEMY_HIT_STUN_DURATION = 300
ENEMY_HIT_COOLDOWN = 500; ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3
ENEMY_STOMP_DEATH_DURATION = 300 # Not used, squash duration is now primary
ENEMY_POST_ATTACK_PAUSE_DURATION = 200
ENEMY_AFLAME_SPEED_MULTIPLIER = 1.3; ENEMY_DEFLAME_SPEED_MULTIPLIER = 1.2
ENEMY_STOMP_SQUASH_DURATION_MS = 400 # How long stomp squash animation takes

# --- Status Effect Durations & Damage (ENEMY) ---
ENEMY_AFLAME_DURATION_MS = 3000; ENEMY_DEFLAME_DURATION_MS = 2000
ENEMY_AFLAME_DAMAGE_PER_TICK = 5; ENEMY_AFLAME_DAMAGE_INTERVAL_MS = 500
ENEMY_FROZEN_DURATION_MS = 3000; ENEMY_DEFROST_DURATION_MS = 1000
# PETRIFIED_DURATION_MS = 5000 # Petrified is indefinite until smashed or interacted with
STONE_SMASHED_DURATION_MS = 2000 # How long smashed pieces remain / anim plays
ENEMY_ZAPPED_DURATION_MS = 2500 # Duration of zapped effect on enemy
ENEMY_ZAPPED_DAMAGE_PER_TICK = 8   # Damage per tick while zapped
ENEMY_ZAPPED_DAMAGE_INTERVAL_MS = 750 # Interval for zapped damage ticks


# --- Status Effect Durations & Damage (PLAYER) ---
PLAYER_AFLAME_DURATION_MS = 3000; PLAYER_DEFLAME_DURATION_MS = 3000 # Player deflame might be longer
PLAYER_AFLAME_DAMAGE_PER_TICK = 5; PLAYER_AFLAME_DAMAGE_INTERVAL_MS = 1000
PLAYER_FROZEN_DURATION_MS = 2800; PLAYER_DEFROST_DURATION_MS = 1200
PLAYER_ZAPPED_DURATION_MS = 3000
PLAYER_ZAPPED_DAMAGE_PER_TICK = 10
PLAYER_ZAPPED_DAMAGE_INTERVAL_MS = 1000


# --- Player Movement Speed Multipliers for Status Effects ---
PLAYER_AFLAME_ACCEL_MULTIPLIER = 1.15; PLAYER_AFLAME_SPEED_MULTIPLIER = 1.1
PLAYER_DEFLAME_ACCEL_MULTIPLIER = 1.1; PLAYER_DEFLAME_SPEED_MULTIPLIER = 1.05

# --- Colors (RGB Tuples) ---
WHITE = (255, 255, 255); BLACK = (0, 0, 0); RED = (255, 0, 0); DARK_RED = (139, 0, 0)
GREEN = (0, 255, 0); DARK_GREEN = (0, 100, 0); BLUE = (0, 0, 255); LIGHT_BLUE = (173, 216, 230)
YELLOW = (255, 255, 0); GRAY = (128, 128, 128); DARK_GRAY = (50, 50, 50); LIGHT_GRAY = (200, 200, 200)
ORANGE_RED = (255, 69, 0); MAGENTA = (255, 0, 255); PURPLE_BACKGROUND = (75, 0, 130)

# --- UI / HUD ---
HEALTH_BAR_WIDTH = 50.0; HEALTH_BAR_HEIGHT = 8.0; HEALTH_BAR_OFFSET_ABOVE = 5.0
HUD_HEALTH_BAR_WIDTH = HEALTH_BAR_WIDTH * 2.0; HUD_HEALTH_BAR_HEIGHT = HEALTH_BAR_HEIGHT + 4.0
DRAW_ENEMY_ABOVE_HEALTH_BAR = True # If true, enemies also get health bars above them

# --- Hazards ---
LAVA_PATCH_HEIGHT = 20.0; LAVA_DAMAGE = 25
LAVA_SPRITE_PATH = "characters/assets/lava.gif" # Animated lava

# --- Common Stone Asset Paths (Relative to project root) ---
STONE_ASSET_FOLDER = "characters/Stone" # Base folder for common stone assets
STONE_IDLE_SPRITE_PATH = os.path.join(STONE_ASSET_FOLDER, "__Stone.png")
STONE_CROUCH_SPRITE_PATH = os.path.join(STONE_ASSET_FOLDER, "__StoneCrouch.png")
STONE_SMASHED_SPRITE_PATH = os.path.join(STONE_ASSET_FOLDER, "__StoneSmashed.gif")
STONE_CROUCH_SMASHED_SPRITE_PATH = os.path.join(STONE_ASSET_FOLDER, "__StoneCrouchSmashed.gif")

# --- File Paths & Directories ---
def get_maps_directory():
    # Handles both normal execution and PyInstaller bundled execution
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        bundle_dir_meipass = sys._MEIPASS # MEIPASS is the temp folder
        bundled_maps_path = os.path.join(bundle_dir_meipass, 'maps')
        if os.path.isdir(bundled_maps_path):
            return bundled_maps_path
        # Fallback: check next to .exe if 'maps' wasn't bundled inside MEIPASS root
        exe_dir = os.path.dirname(sys.executable)
        maps_next_to_exe = os.path.join(exe_dir, 'maps')
        if os.path.isdir(maps_next_to_exe):
            return maps_next_to_exe
        # If still not found, default to assuming it's in MEIPASS (might fail later if not)
        return bundled_maps_path # PyInstaller usually puts data here
    else:
        # Normal execution (not bundled)
        if PROJECT_ROOT:
            return os.path.join(PROJECT_ROOT, 'maps')
        else: # Should not happen if PROJECT_ROOT is correctly defined
            if _SCRIPT_LOGGING_ENABLED: print("CONSTANTS.PY ERROR: PROJECT_ROOT not determined. MAPS_DIR relative to CWD.")
            return 'maps' # Fallback to relative path

MAPS_DIR = get_maps_directory()

# --- Network Settings ---
SERVER_IP_BIND = '0.0.0.0' # Bind to all available interfaces
SERVER_PORT_TCP = 5555
SERVICE_NAME = "platformer_adventure_lan_v1" # For LAN discovery
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 8192 # Bytes for network buffers
BROADCAST_INTERVAL_S = 1.0 # How often server broadcasts its presence
CLIENT_SEARCH_TIMEOUT_S = 5.0 # How long client searches for LAN games
MAP_DOWNLOAD_CHUNK_SIZE = 4096 # Bytes per map data chunk

# --- Editor Defaults (Minimal - Full editor config is in editor_config.py) ---
EDITOR_SCREEN_INITIAL_WIDTH = 1380 # Default width if editor is run standalone
EDITOR_SCREEN_INITIAL_HEIGHT = 820 # Default height
LEVEL_EDITOR_SAVE_FORMAT_EXTENSION = ".json" # Editor's own save format
GAME_LEVEL_FILE_EXTENSION = ".py"      # Exported game-ready level format

# --- Player Gameplay Specifics ---
PLAYER_SELF_DAMAGE = 10 # e.g., for blood magic
ALLOW_SELF_FIREBALL_DAMAGE = False # If player's own fireball can hurt them
ENABLE_RANDOM_CHEST_SPAWN_IF_NONE_IN_MAP = False # If true, game_setup might add a chest if map has none

# --- Player Action Timings (milliseconds) ---
PLAYER_DASH_DURATION = 150
PLAYER_ROLL_DURATION = 1000 # Roll gives longer invulnerability or movement
PLAYER_SLIDE_DURATION = 400
# PLAYER_WALL_CLIMB_DURATION = 500 # Wall climb was removed
PLAYER_COMBO_WINDOW = 250 # Time window to chain combo attacks
PLAYER_HIT_STUN_DURATION = 300 # How long player is stunned after taking a hit
PLAYER_HIT_COOLDOWN = 600 # Invulnerability after being hit

# --- Player Projectile Default Keys (String representations - actual mapping in config.py) ---
P1_FIREBALL_KEY = "1"; P1_POISON_KEY = "2"; P1_BOLT_KEY = "3"; P1_BLOOD_KEY = "4"; P1_ICE_KEY = "5"; P1_SHADOW_PROJECTILE_KEY = "6"; P1_GREY_PROJECTILE_KEY = "7"
P2_FIREBALL_KEY = "Numpad8"; P2_POISON_KEY = "Numpad9"; P2_BOLT_KEY = "Numpad0"; P2_BLOOD_KEY = "NumpadDecimal"; P2_ICE_KEY = "NumpadSubtract"; P2_SHADOW_PROJECTILE_KEY = "NumpadAdd"; P2_GREY_PROJECTILE_KEY = "NumpadEnter"
P3_FIREBALL_KEY = "F1"; P3_POISON_KEY = "F2"; P3_BOLT_KEY = "F3"; P3_BLOOD_KEY = "F4"; P3_ICE_KEY = "F5"; P3_SHADOW_PROJECTILE_KEY = "F6"; P3_GREY_PROJECTILE_KEY = "F7"
P4_FIREBALL_KEY = "F8"; P4_POISON_KEY = "F9"; P4_BOLT_KEY = "F10"; P4_BLOOD_KEY = "F11"; P4_ICE_KEY = "F12"; P4_SHADOW_PROJECTILE_KEY = "Insert"; P4_GREY_PROJECTILE_KEY = "Delete"

# --- Input Handling Constants ---
# Lists of game actions that might be triggered by joystick axes/hats as DISCRETE events
# (Movement itself is continuous, not listed here)
JOYSTICK_AXIS_EVENT_ACTIONS = [
    "jump", "crouch", "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "reset", "menu_confirm", "menu_cancel",
    "up", "down" # "up" and "down" can be discrete for menus or combined actions
]
JOYSTICK_HAT_EVENT_ACTIONS = [ # D-pad often used for discrete menu nav or quick actions
    "jump", "crouch", # If D-pad up/down also maps to jump/crouch
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7", # If D-pad directions map to projectiles
    "menu_up", "menu_down", "menu_left", "menu_right", # Standard D-pad menu nav
    "menu_confirm", "menu_cancel", "pause", "reset", # If D-pad buttons are mapped to these
    "up", "down", "left", "right" # If D-pad directions are also considered discrete events
]
MAX_JOYSTICK_INSTANCE_IDS_FOR_PREV_STATE = 16 # Max Pygame joystick instance_ids to pre-allocate prev_state for

# Initial print to confirm constants loaded, if logging is on for this file
if _SCRIPT_LOGGING_ENABLED:
    print(f"CONSTANTS.PY: Loaded. PROJECT_ROOT='{PROJECT_ROOT}', MAPS_DIR='{MAPS_DIR}'")
    if not os.path.isdir(MAPS_DIR):
        print(f"CONSTANTS.PY WARNING: MAPS_DIR '{MAPS_DIR}' does not exist or is not a directory!")

#################### END OF FILE: constants.py ####################