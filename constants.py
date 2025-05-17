# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
Dynamically sets MAPS_DIR based on execution environment (development vs. PyInstaller bundle).
"""
# version 1.0.0.11 (Added 'reset' to JOYSTICK_EVENT_ACTIONS)
import os
import sys
import pygame # For K_ constants

# --- Gameplay / Physics ---
PLAYER_ROLL_CONTROL_ACCEL_FACTOR = 0.4
FPS = 60
PLAYER_ACCEL = 0.5
PLAYER_FRICTION = -0.15  # Negative value!
PLAYER_GRAVITY = 0.7
PLAYER_JUMP_STRENGTH = -15
PLAYER_RUN_SPEED_LIMIT = 7
PLAYER_DASH_SPEED = 18
PLAYER_ROLL_SPEED = 14# MODIFIED: Was 9
PLAYER_WALL_SLIDE_SPEED = 2
PLAYER_WALL_CLIMB_SPEED = -4    # Negative for upward movement
PLAYER_LADDER_CLIMB_SPEED = 3
PLAYER_MAX_HEALTH = 100
CHARACTER_BOUNCE_VELOCITY = 2.5 # Pixels per frame push back on character-character collision
PLAYER_STOMP_BOUNCE_STRENGTH = -8.0 # Upwards velocity after stomping an enemy
PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX = 8 # Pixel grace for landing on enemy's head for stomp
TERMINAL_VELOCITY_Y = 18 # Maximum downward speed

# Collision Specifics
MIN_WALL_OVERLAP_PX = 5                # Minimum vertical overlap to consider a side collision a "wall touch"
MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING = 0.15 # Player width ratio for landing on platform
MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING = 0.15 # Player width ratio for hitting ceiling
LANDING_FRICTION_MULTIPLIER = 0.8      # Multiplier for X-velocity on landing (e.g., 0.8 = 20% reduction)
GROUND_SNAP_THRESHOLD = 5.0            # Used in older collision logic, might be useful for some scenarios
CEILING_SNAP_THRESHOLD = 2.0           # Used in older collision logic
MIN_SIGNIFICANT_FALL_VEL = 1.5       # Minimum Y velocity to be considered "falling significantly"

# --- Animation ---
ANIM_FRAME_DURATION = 80 # ms per frame for most animations

# Player Attack Specifics
PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20
PLAYER_CROUCH_ATTACK_DAMAGE = 5
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5 # If attack2 animation is slower/faster

CHARACTER_ATTACK_STATE_DURATION = 480 # ms, general duration for an attack state if not animation-driven

# --- Item Constants ---
CHEST_CLOSED_SPRITE_PATH = "characters/items/chest.gif"
CHEST_OPEN_SPRITE_PATH = "characters/items/chest_open.gif"
CHEST_STAY_OPEN_DURATION_MS = 3000
CHEST_FADE_OUT_DURATION_MS = 1000


# --- Projectile Constants ---
# Fireball (Key 1)
FIREBALL_DAMAGE = 50
FIREBALL_SPEED = 9
FIREBALL_COOLDOWN = 750 # ms
FIREBALL_LIFESPAN = 2500 # ms
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"
FIREBALL_DIMENSIONS = (61, 58) # width, height

# Poison (Key 2)
POISON_DAMAGE = 20
POISON_SPEED = 6
POISON_COOLDOWN = 1000 # ms
POISON_LIFESPAN = 3000 # ms
POISON_SPRITE_PATH = "characters/weapons/poison.gif"
POISON_DIMENSIONS = (40, 40)

# Bolt (Key 3)
BOLT_DAMAGE = 35
BOLT_SPEED = 15
BOLT_COOLDOWN = 600 # ms
BOLT_LIFESPAN = 1500 # ms
BOLT_SPRITE_PATH = "characters/weapons/bolt1_resized_11x29.gif"
BOLT_DIMENSIONS = (11, 29)

# Blood (Key 4)
BLOOD_DAMAGE = 30
BLOOD_SPEED = 8
BLOOD_COOLDOWN = 800 # ms
BLOOD_LIFESPAN = 2000 # ms
BLOOD_SPRITE_PATH = "characters/weapons/blood.gif"
BLOOD_DIMENSIONS = (40, 40)

# Ice (Key 5)
ICE_DAMAGE = 10
ICE_SPEED = 7
ICE_COOLDOWN = 900 # ms
ICE_LIFESPAN = 2200 # ms
ICE_SPRITE_PATH = "characters/weapons/ice.gif"
ICE_DIMENSIONS = (40, 40)

# Shadow Projectile (Key 6)
SHADOW_PROJECTILE_DAMAGE = 45
SHADOW_PROJECTILE_SPEED = 11
SHADOW_PROJECTILE_COOLDOWN = 800 # ms
SHADOW_PROJECTILE_LIFESPAN = 1700 # ms
SHADOW_PROJECTILE_SPRITE_PATH = "characters/weapons/shadow095.gif"
SHADOW_PROJECTILE_DIMENSIONS = (40, 40)

# Grey Projectile (Key 7)
GREY_PROJECTILE_DAMAGE = 0 # Petrifies instead of direct damage
GREY_PROJECTILE_SPEED = 13
GREY_PROJECTILE_COOLDOWN = 750 # ms
GREY_PROJECTILE_LIFESPAN = 1500 # ms
GREY_PROJECTILE_SPRITE_PATH = "characters/weapons/grey.gif"
GREY_PROJECTILE_DIMENSIONS = (40, 40)


# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250
ENEMY_ATTACK_RANGE = 70
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500 # ms
ENEMY_PATROL_DIST = 150
ENEMY_HIT_STUN_DURATION = 300 # ms
ENEMY_HIT_COOLDOWN = 500 # ms (invulnerability after being hit)
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3
ENEMY_STOMP_DEATH_DURATION = 300 # ms, visual duration of stomp death scale effect
ENEMY_POST_ATTACK_PAUSE_DURATION = 200 # ms, brief pause after an enemy attack animation finishes

# --- Enemy Status Effect Constants ---
ENEMY_AFLAME_DURATION_MS = 3000
ENEMY_DEFLAME_DURATION_MS = 2000
ENEMY_AFLAME_DAMAGE_PER_TICK = 5
ENEMY_AFLAME_DAMAGE_INTERVAL_MS = 1000
ENEMY_FROZEN_DURATION_MS = 3000
ENEMY_DEFROST_DURATION_MS = 1000

# --- Petrification Constants ---
STONE_SMASHED_DURATION_MS = 5000 # Time for smashed stone to disappear (Player and Statue)


# --- Colors ---
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
PURPLE_BACKGROUND = (75, 0, 130) # Default map background if not specified

# --- UI ---
HEALTH_BAR_WIDTH = 50
HEALTH_BAR_HEIGHT = 8
HEALTH_BAR_OFFSET_ABOVE = 5 # Pixels above character's head
HUD_HEALTH_BAR_WIDTH = HEALTH_BAR_WIDTH * 2
HUD_HEALTH_BAR_HEIGHT = HEALTH_BAR_HEIGHT + 4


# --- Map ---
TILE_SIZE = 40
LAVA_PATCH_HEIGHT = 20 # Default height for lava tiles if not specified by map
LAVA_DAMAGE = 25       # Damage per hit from lava (can be time-based via hit cooldown)

def get_maps_directory():
    """
    Determines the absolute path to the 'maps' directory for file operations.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir_meipass = sys._MEIPASS
        desired_bundled_maps_path = os.path.join(bundle_dir_meipass, 'maps')
        _maps_dir_to_use = desired_bundled_maps_path
        if not os.path.isdir(desired_bundled_maps_path):
            exe_dir = os.path.dirname(sys.executable)
            maps_next_to_exe = os.path.join(exe_dir, 'maps')
            if os.path.isdir(maps_next_to_exe):
                _maps_dir_to_use = maps_next_to_exe
        return _maps_dir_to_use
    else:
        project_root_guess = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        dev_maps_path = os.path.join(project_root_guess, 'maps')
        return dev_maps_path

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

# --- Other ---
PLAYER_SELF_DAMAGE = 10

# --- Player Ability Durations/Cooldowns ---
PLAYER_DASH_DURATION = 150 # ms
PLAYER_ROLL_DURATION = 1000 # ms # MODIFIED: Was 300
PLAYER_SLIDE_DURATION = 400 # ms
PLAYER_WALL_CLIMB_DURATION = 500 # ms
PLAYER_COMBO_WINDOW = 250 # ms
PLAYER_HIT_STUN_DURATION = 300 # ms
PLAYER_HIT_COOLDOWN = 600 # ms

# --- Player 1 Projectile Keys ---
# P1_FIREBALL_KEY = pygame.K_1
P1_FIREBALL_KEY = pygame.K_7
P1_POISON_KEY = pygame.K_2
P1_BOLT_KEY = pygame.K_3
P1_BLOOD_KEY = pygame.K_4
P1_ICE_KEY = pygame.K_5
P1_SHADOW_PROJECTILE_KEY = pygame.K_6
# P1_GREY_PROJECTILE_KEY = pygame.K_7
P1_GREY_PROJECTILE_KEY = pygame.K_1

# --- Player 2 Projectile Keys ---
P2_FIREBALL_KEY = pygame.K_KP_1
P2_POISON_KEY = pygame.K_KP_2
P2_BOLT_KEY = pygame.K_KP_3
P2_BLOOD_KEY = pygame.K_KP_4
P2_ICE_KEY = pygame.K_KP_5
P2_SHADOW_PROJECTILE_KEY = pygame.K_KP_6
P2_GREY_PROJECTILE_KEY = pygame.K_KP_7

# --- Input Handling Constants for Joysticks ---
# Actions that, if mapped to a joystick HAT, should trigger a single event
JOYSTICK_HAT_EVENT_ACTIONS = [
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "menu_up", "menu_down", "menu_left", "menu_right",
    "menu_confirm", "menu_cancel", "pause", "reset" # Added "reset"
]

# Actions that, if mapped to a joystick AXIS (and cross a threshold),
# should trigger a single event.
JOYSTICK_AXIS_EVENT_ACTIONS = [
    "jump",
    "attack1", "attack2", "dash", "roll", "interact",
    "projectile1", "projectile2", "projectile3", "projectile4",
    "projectile5", "projectile6", "projectile7",
    "pause", "menu_confirm", "menu_cancel", "reset" # Added "reset"
]