# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
"""
# version 1.0.0.3 (Added collision-specific constants)

# --- Gameplay / Physics ---
FPS = 60
PLAYER_ACCEL = 0.5
PLAYER_FRICTION = -0.15  # Negative value!
PLAYER_GRAVITY = 0.7
PLAYER_JUMP_STRENGTH = -15
PLAYER_RUN_SPEED_LIMIT = 7
PLAYER_DASH_SPEED = 15
PLAYER_ROLL_SPEED = 9
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

# --- Projectile Constants ---
FIREBALL_DAMAGE = 50
FIREBALL_SPEED = 9
FIREBALL_COOLDOWN = 750 # ms
FIREBALL_LIFESPAN = 2500 # ms
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"
FIREBALL_DIMENSIONS = (61, 58) # width, height

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 250 # Increased for better AI reaction
ENEMY_ATTACK_RANGE = 70   # Slightly increased
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500 # ms
ENEMY_PATROL_DIST = 150
ENEMY_HIT_STUN_DURATION = 300 # ms
ENEMY_HIT_COOLDOWN = 500 # ms (invulnerability after being hit)
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3 # Upward bounce when enemy is hit

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

# --- Map ---
TILE_SIZE = 40
LAVA_PATCH_HEIGHT = 20 # Default height for lava tiles if not specified by map
LAVA_DAMAGE = 25       # Damage per hit from lava (can be time-based via hit cooldown)
MAPS_DIR = "maps"

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
PLAYER_SELF_DAMAGE = 10 # For debug purposes