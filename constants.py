# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
"""

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
PLAYER_ATTACK_DAMAGE = 15
CHARACTER_BOUNCE_VELOCITY = 2.5 # Pixels per frame push back on collision

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5 # Give enemy its own speed limit
ENEMY_ACCEL = 0.4         # Give enemy its own acceleration
ENEMY_FRICTION = -0.12    # Give enemy its own friction
ENEMY_DETECTION_RANGE = 350
ENEMY_ATTACK_RANGE = 60
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500
ENEMY_PATROL_DIST = 150 # How far to move before turning in patrol

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
DARK_RED = (139, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 100, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_BLUE = (173, 216, 230)
ORANGE_RED = (255, 69, 0) # For Lava

# --- Animation ---
ANIM_FRAME_DURATION = 80 # ms per frame

# --- UI ---
HEALTH_BAR_WIDTH = 50
HEALTH_BAR_HEIGHT = 8

# --- Map ---
TILE_SIZE = 40 # Example, if you use a grid later
LAVA_PATCH_HEIGHT = 20 # How tall lava patches/wells rects are for collision (can be diff from visual depth)

# --- Other ---
# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
"""

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
PLAYER_ATTACK_DAMAGE = 15
CHARACTER_BOUNCE_VELOCITY = 2.5 # Pixels per frame push back on collision

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5 # Give enemy its own speed limit
ENEMY_ACCEL = 0.4         # Give enemy its own acceleration
ENEMY_FRICTION = -0.12    # Give enemy its own friction
ENEMY_DETECTION_RANGE = 350
ENEMY_ATTACK_RANGE = 60
ENEMY_ATTACK_DAMAGE = 10
ENEMY_ATTACK_COOLDOWN = 1500
ENEMY_PATROL_DIST = 150 # How far to move before turning in patrol

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
DARK_RED = (139, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 100, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
LIGHT_BLUE = (173, 216, 230)
ORANGE_RED = (255, 69, 0) # For Lava

# --- Animation ---
ANIM_FRAME_DURATION = 80 # ms per frame

# --- UI ---
HEALTH_BAR_WIDTH = 50
HEALTH_BAR_HEIGHT = 8

# --- Map ---
TILE_SIZE = 40 # Example, if you use a grid later
LAVA_PATCH_HEIGHT = 20 # How tall lava patches/wells rects are for collision (can be diff from visual depth)

LAVA_DAMAGE = 50