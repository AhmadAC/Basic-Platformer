# constants.py
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
"""
# version 1.0.0.2 (Added Network Constants)

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
PLAYER_WALL_CLIMB_SPEED = -4
PLAYER_LADDER_CLIMB_SPEED = 3
PLAYER_MAX_HEALTH = 100
CHARACTER_BOUNCE_VELOCITY = 2.5 # Pixels per frame push back on collision

# --- Animation ---
ANIM_FRAME_DURATION = 80 # ms per frame for most animations

# Player Attack Specifics
PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20
PLAYER_CROUCH_ATTACK_DAMAGE = 5
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5

CHARACTER_ATTACK_STATE_DURATION = 480 # ms

# --- Projectile Constants ---
FIREBALL_DAMAGE = 50
FIREBALL_SPEED = 9
FIREBALL_COOLDOWN = 750
FIREBALL_LIFESPAN = 2500
FIREBALL_SPRITE_PATH = "characters/weapons/fire.gif"
FIREBALL_DIMENSIONS = (61, 58)

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5
ENEMY_ACCEL = 0.4
ENEMY_FRICTION = -0.12
ENEMY_DETECTION_RANGE = 100
ENEMY_ATTACK_RANGE = 60
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500
ENEMY_PATROL_DIST = 150
ENEMY_HIT_STUN_DURATION = 300
ENEMY_HIT_COOLDOWN = 500
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
DARK_RED = (139, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0) 
DARK_GREEN = (0, 100, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_BLUE = (173, 216, 230)
ORANGE_RED = (255, 69, 0)

# --- UI ---
HEALTH_BAR_WIDTH = 50
HEALTH_BAR_HEIGHT = 8
HEALTH_BAR_OFFSET_ABOVE = 5

# --- Map ---
TILE_SIZE = 40
LAVA_PATCH_HEIGHT = 20
LAVA_DAMAGE = 50

# --- Network Constants ---
SERVER_IP_BIND = '0.0.0.0'  # Listen on all available interfaces
SERVER_PORT_TCP = 5555      # Default TCP port for the game server
SERVICE_NAME = "platformer_adventure_lan_v1" # Name for LAN discovery
DISCOVERY_PORT_UDP = 5556   # UDP port for LAN discovery broadcasts
BUFFER_SIZE = 8192          # Network buffer size for send/recv
BROADCAST_INTERVAL_S = 1.0  # How often server broadcasts its presence (seconds)
CLIENT_SEARCH_TIMEOUT_S = 5.0 # How long client searches for LAN server (seconds)

# --- Other ---
PLAYER_SELF_DAMAGE = 10
TERMINAL_VELOCITY_Y = 18