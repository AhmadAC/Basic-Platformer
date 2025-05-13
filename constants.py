# -*- coding: utf-8 -*-
"""
Stores constant values used throughout the game.
"""
# version 1.00000.1 # (Assuming this version comment is for the file itself)

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
# PLAYER_ATTACK_DAMAGE = 15 # Old generic player attack damage, replaced by specific types
PLAYER_ATTACK1_DAMAGE = 10
PLAYER_ATTACK2_DAMAGE = 5
PLAYER_COMBO_ATTACK_DAMAGE = 20  # Damage for the third attack in a combo sequence
PLAYER_CROUCH_ATTACK_DAMAGE = 5   # Damage for an attack performed while crouching
PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER = 1.5 # Attack 2 frames last 50% longer, making it slower

# --- Character Attack State Duration (Shared by Player and Enemy if desired) ---
# This is the duration (in ms) that the character's LOGICAL attack state remains active.
# The visual animation will play during this time. If the animation is shorter, it might loop
# or hold its last frame depending on animation handling.
# If the animation is longer, the logical attack might end before the visual animation finishes.
# Set based on the desired feel of the attack commitment.
# For example, if your attack animation has 6 frames and ANIM_FRAME_DURATION is 80ms,
# the visual animation takes 6 * 80 = 480ms. You might want the attack state to last this long.
CHARACTER_ATTACK_STATE_DURATION = 480 # ms (Example: 6 frames * 80ms/frame = 480ms)

# --- Enemy Constants ---
ENEMY_MAX_HEALTH = 80
ENEMY_RUN_SPEED_LIMIT = 5 # Give enemy its own speed limit
ENEMY_ACCEL = 0.4         # Give enemy its own acceleration
ENEMY_FRICTION = -0.12    # Give enemy its own friction
ENEMY_DETECTION_RANGE = 20
ENEMY_ATTACK_RANGE = 60
ENEMY_ATTACK_DAMAGE = 10  # Damage dealt by enemies
ENEMY_ATTACK_COOLDOWN = 1500 # ms
ENEMY_PATROL_DIST = 150 # How far to move before turning in patrol
# ENEMY_ATTACK_STATE_DURATION can be CHARACTER_ATTACK_STATE_DURATION if you want them identical,
# or you can define a separate one for enemies if you want them to differ.
# For identical: Enemy class will use CHARACTER_ATTACK_STATE_DURATION by default if ENEMY_ATTACK_STATE_DURATION is not found.
# If you want it different, uncomment and set:
# ENEMY_SPECIFIC_ATTACK_STATE_DURATION = 600 # ms, example if enemy attack is longer

ENEMY_HIT_STUN_DURATION = 300 # ms, how long enemy is stunned when hit
ENEMY_HIT_COOLDOWN = 500      # ms, invincibility after being hit
ENEMY_HIT_BOUNCE_Y = PLAYER_JUMP_STRENGTH * 0.3 # Vertical bounce when enemy is hit


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

# --- UI ---
HEALTH_BAR_WIDTH = 50
HEALTH_BAR_HEIGHT = 8
HEALTH_BAR_OFFSET_ABOVE = 5 # Distance enemy health bar is drawn above enemy

# --- Map ---
TILE_SIZE = 40 # Example, if you use a grid later
LAVA_PATCH_HEIGHT = 20 # How tall lava patches/wells rects are for collision (can be diff from visual depth)
LAVA_DAMAGE = 50 # Damage per hit/tick from lava

# --- Other ---
PLAYER_SELF_DAMAGE = 10 # Damage player inflicts on self with debug key
TERMINAL_VELOCITY_Y = 18 # Max fall speed for characters