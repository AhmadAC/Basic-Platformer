# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution.
Logs detailed physics information if enabled.
Players can be set aflame by enemies that are aflame.
"""
import pygame
import constants as C
from tiles import Lava # For type checking hazards
from enemy import Enemy # For isinstance checks (player vs enemy, enemy stomp)
from statue import Statue # Import Statue for stomp-smashing

# Import the shared logging flag and helper function from logger.py
try:
    from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics, debug, info
except ImportError:
    def debug(msg): print(f"DEBUG_PCOLLISION: {msg}")
    def info(msg): print(f"INFO_PCOLLISION: {msg}")
    ENABLE_DETAILED_PHYSICS_LOGS = False # Fallback if logger is missing
    def log_player_physics(player, tag, extra=""): pass # No-op if logger missing


def check_player_platform_collisions(player, direction: str, platforms_group: pygame.sprite.Group):
    """
    Handles collisions between the player and solid platforms.
    Resolves collisions by adjusting player position and velocity.
    Updates `player.on_ground` and `player.touching_wall` flags.

    Args:
        player (Player): The player instance.
        direction (str): The axis of movement being checked ('x' or 'y').
        platforms_group (pygame.sprite.Group): Group of platform sprites.
    """
    if not player._valid_init: return

    # Store the player's rect *before* any potential collision resolution on this axis
    rect_after_current_axis_move = player.rect.copy() # Rect after vel has been applied to pos for this axis
    collided_with_wall_on_side = 0  # -1 for left, 1 for right, 0 for none

    # Get all platforms the player is currently colliding with (after this axis's move)
    colliding_platforms = pygame.sprite.spritecollide(player, platforms_group, False)

    for platform_sprite in colliding_platforms:
        # Log the state before resolving this specific platform collision
        current_player_rect_for_log = player.rect.copy() # Rect state *before* this specific platform resolves
        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}",
                           (current_player_rect_for_log, platform_sprite.rect, platform_sprite.platform_type))

        if direction == 'x': # Horizontal collision
            if player.vel.x > 0:  # Moving right
                # Check if player was to the left of the platform before this move step
                if player.rect.right > platform_sprite.rect.left and \
                   rect_after_current_axis_move.left < platform_sprite.rect.left: # Player penetrated from left
                    player.rect.right = platform_sprite.rect.left
                    player.vel.x = 0
                    # Check for wall touch (significant vertical overlap)
                    if not player.on_ground and not player.on_ladder: # Only if in air
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = 1 # Touched right wall
                    # Update pos from resolved rect
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom # Keep consistent with midbottom anchor
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_R",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))
            elif player.vel.x < 0:  # Moving left
                if player.rect.left < platform_sprite.rect.right and \
                   rect_after_current_axis_move.right > platform_sprite.rect.right: # Player penetrated from right
                    player.rect.left = platform_sprite.rect.right
                    player.vel.x = 0
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = -1 # Touched left wall
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_L",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))
        
        elif direction == 'y': # Vertical collision
            if player.vel.y >= 0:  # Moving down or stationary but overlapping (e.g. spawned in ground)
                # Check if player was above the platform before this move step (or very slightly interpenetrating)
                if player.rect.bottom >= platform_sprite.rect.top and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.top and \
                   rect_after_current_axis_move.top < platform_sprite.rect.top + 1: # +1 for slight tolerance
                    
                    # Check for sufficient horizontal overlap to consider it a landing
                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15)
                    min_horizontal_overlap = player.rect.width * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - \
                                           max(player.rect.left, platform_sprite.rect.left)
                    
                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.bottom = platform_sprite.rect.top # Snap to top of platform
                        if not player.on_ground and player.vel.y > 0: # If just landed
                            player.can_wall_jump = False # Reset wall jump on landing
                            player.wall_climb_timer = 0 # Reset wall climb timer
                            # Apply landing friction if not sliding
                            if not player.is_sliding and not (hasattr(player, 'state') and player.state.startswith('slide_trans')):
                                landing_friction = getattr(C, 'LANDING_FRICTION_MULTIPLIER', 0.8)
                                player.vel.x *= landing_friction
                        player.on_ground = True
                        player.vel.y = 0 # Stop vertical movement
                        player.pos.x = player.rect.centerx # Update pos from resolved rect
                        player.pos.y = player.rect.bottom 
                        log_player_physics(player, f"PLAT_COLL_Y_LAND",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_land'))
            
            elif player.vel.y < 0:  # Moving up
                # Check if player was below the platform before this move
                if player.rect.top <= platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.top < platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.bottom -1: # -1 for tolerance
                    
                    min_overlap_ratio_ceil = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15)
                    min_horizontal_overlap_ceil = player.rect.width * min_overlap_ratio_ceil
                    actual_overlap_width_ceil = min(player.rect.right, platform_sprite.rect.right) - \
                                                max(player.rect.left, platform_sprite.rect.left)
                    
                    if actual_overlap_width_ceil >= min_horizontal_overlap_ceil:
                        if player.on_ladder: player.on_ladder = False # Knock off ladder if head bonk
                        player.rect.top = platform_sprite.rect.bottom # Snap to bottom of platform
                        player.vel.y = 0  # Stop upward movement
                        player.pos.x = player.rect.centerx # Update pos
                        player.pos.y = player.rect.bottom 
                        log_player_physics(player, f"PLAT_COLL_Y_CEIL_NORMAL",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_ceil_norm'))

    # Update player's wall touch status based on resolved collisions this frame
    if direction == 'x':
        # Only set touching_wall if in air and not on ladder (wall interactions usually imply this)
        if collided_with_wall_on_side != 0 and not player.on_ground and not player.on_ladder:
            player.touching_wall = collided_with_wall_on_side
            # Allow wall jump if touching wall, unless actively wall climbing (climbing uses the wall)
            player.can_wall_jump = not (hasattr(player, 'state') and player.state == 'wall_climb' and player.is_holding_climb_ability_key)


def check_player_ladder_collisions(player, ladders_group: pygame.sprite.Group):
    """
    Checks if the player is in a position to grab a ladder.
    Updates `player.can_grab_ladder`.
    """
    if not player._valid_init: return

    # Use a slightly smaller rect for checking ladder grab to avoid grabbing from too far
    ladder_check_rect = player.rect.inflate(-player.rect.width * 0.6, -player.rect.height * 0.1)
    
    player.can_grab_ladder = False # Reset before check
    for ladder_sprite in pygame.sprite.spritecollide(player, ladders_group, False,
                           collided=lambda p_sprite, l_sprite: ladder_check_rect.colliderect(l_sprite.rect)):
        # Player must be somewhat centered on the ladder and within its vertical span
        if abs(player.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
           ladder_sprite.rect.top < player.rect.centery < ladder_sprite.rect.bottom : # Check if player's center is within ladder's Y
              player.can_grab_ladder = True; break


def check_player_character_collisions(player, direction: str, characters_list: list):
    """
    Handles collisions between the player and other characters (Enemies, other Players).
    Applies pushback. Handles player stomping enemies.
    Handles player getting ignited by aflame enemies.

    Returns:
        bool: True if a collision occurred that was resolved, False otherwise.
    """
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: # Petrified players don't interact
        return False
    
    collision_occurred_this_axis = False

    for other_char in characters_list:
        if other_char is player: continue # Cannot collide with self

        # Ensure other character is valid and "active" for collision
        if not (other_char and hasattr(other_char, '_valid_init') and \
                other_char._valid_init and hasattr(other_char, 'is_dead') and \
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False)) and \
                other_char.alive()): # Petrified entities can still be collided with
            continue

        if player.rect.colliderect(other_char.rect):
            current_player_rect_for_log = player.rect.copy() # For logging
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}",
                               (current_player_rect_for_log, other_char.rect,
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', getattr(other_char, 'statue_id', 'UnknownChar')))))
            
            collision_occurred_this_axis = True # A collision is detected
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)
            
            # Player getting ignited by an aflame enemy
            if isinstance(other_char, Enemy) and getattr(other_char, 'is_aflame', False) and \
               not player.is_aflame and not player.is_deflaming and \
               not player.is_frozen and not player.is_defrosting and not player.is_petrified:
                if hasattr(player, 'apply_aflame_effect'):
                    player.apply_aflame_effect()
                # No pushback if ignited this frame, focus on the fire effect
                continue # Processed ignition, move to next potential character collision

            # --- Player Stomp Logic (on Enemies or Statues) ---
            is_enemy_stompable = isinstance(other_char, Enemy) and \
                                     not other_char.is_dead and \
                                     not getattr(other_char, 'is_stomp_dying', False) and \
                                     not getattr(other_char, 'is_aflame', False) and \
                                     not getattr(other_char, 'is_frozen', False) and \
                                     not getattr(other_char, 'is_petrified', False) # Can't stomp petrified enemy

            is_statue_stompable = isinstance(other_char, Statue) and \
                                     not getattr(other_char, 'is_smashed', False)


            if (is_enemy_stompable or is_statue_stompable) and direction == 'y' and player.vel.y > 0.5: # Player moving downwards
                # Estimate player's bottom position in the *previous* frame
                previous_player_bottom_y_estimate = player.pos.y - player.vel.y # pos.y is current bottom
                
                # Define target area on top of the character for a successful stomp
                stomp_head_grace = getattr(C, 'PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX', 5) # Pixels from top of enemy head
                target_stomp_top_y = other_char.rect.top + stomp_head_grace
                
                # Conditions for a successful stomp:
                # 1. Player was above the target's stomp area in the previous frame.
                # 2. Player's bottom is now at or below the target's actual top.
                # 3. Player's bottom is not too far below the target's top (e.g., landed mostly on head).
                player_landed_on_target_head = (
                    previous_player_bottom_y_estimate <= target_stomp_top_y and 
                    player.rect.bottom >= other_char.rect.top and 
                    player.rect.bottom <= other_char.rect.top + (other_char.rect.height * 0.40) # Landed on upper 40%
                )
                if player_landed_on_target_head:
                    stomp_processed = False
                    if is_enemy_stompable and hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        info(f"Player {player.player_id} stomped on Enemy {getattr(other_char, 'enemy_id', 'Unknown')}")
                        other_char.stomp_kill() 
                        stomp_processed = True
                    elif is_statue_stompable and hasattr(other_char, 'take_damage'): # Stomping a statue smashes it
                        info(f"Player {player.player_id} stomped on Statue {getattr(other_char, 'statue_id', 'Unknown')}")
                        other_char.take_damage(999) # High damage to ensure smash
                        stomp_processed = True
                    
                    if stomp_processed:
                        player.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH # Bounce player up
                        player.on_ground = False # No longer on ground after bounce
                        if hasattr(player, 'set_state'): player.set_state('jump') # Visual jump
                        player.rect.bottom = other_char.rect.top -1 # Ensure player is just above
                        # Update player position based on new rect
                        player.pos.x = player.rect.centerx 
                        player.pos.y = player.rect.bottom
                        log_player_physics(player, f"CHAR_COLL_STOMP_{type(other_char).__name__}",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, f'y_stomp_{type(other_char).__name__}'))
                    return True # Collision handled by stomp

            # --- Standard Character Pushback Logic (if not a stomp) ---
            player_state_str = str(getattr(player, 'state', '')).lower()
            is_attacking_self = getattr(player, 'is_attacking', False) or \
                                ('attack' in player_state_str) # Is player currently in an attack animation?

            if direction == 'x': # Horizontal collision
                if is_attacking_self and not is_other_petrified_solid: # Player is attacking, push target (if not solid petrified)
                    # Player should not be pushed back if they are the one attacking
                    # Target might be pushed by attack logic in combat_handler if hit
                    # For simple collision, just stop player if they run into someone while attacking
                    if player.vel.x > 0 : player.rect.right = other_char.rect.left
                    elif player.vel.x < 0 : player.rect.left = other_char.rect.right
                    player.vel.x = 0
                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_ATTACK_X_STOP",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_attack_stop'))
                else: # Player is NOT attacking, or target is solid petrified: apply mutual pushback
                    bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                    push_dir_self = 0 # Direction player will be pushed
                    if player.rect.centerx < other_char.rect.centerx: # Player is to the left of other
                        player.rect.right = other_char.rect.left # Snap player
                        push_dir_self = -1 # Player pushed left
                    else: # Player is to the right
                        player.rect.left = other_char.rect.right # Snap player
                        push_dir_self = 1 # Player pushed right
                    player.vel.x = push_dir_self * bounce_vel # Apply bounce to player

                    # Push the other character if it's not attacking, petrified, or in a special move
                    other_char_state_str = str(getattr(other_char, 'state', '')).lower()
                    is_attacking_other = getattr(other_char, 'is_attacking', False) or \
                                         ('attack' in other_char_state_str)
                    can_push_other = not is_attacking_other and not is_other_petrified_solid and \
                                     not getattr(other_char, 'is_dashing', False) and \
                                     not getattr(other_char, 'is_rolling', False) and \
                                     not getattr(other_char, 'is_aflame', False) and \
                                     not getattr(other_char, 'is_frozen', False)


                    if hasattr(other_char, 'vel') and can_push_other:
                        other_char.vel.x = -push_dir_self * bounce_vel # Push other in opposite direction
                    # Update other_char's position immediately for visual consistency if pushed
                    if hasattr(other_char, 'pos') and hasattr(other_char, 'rect') and can_push_other:
                        other_char.pos.x += (-push_dir_self * 1.0) # Small immediate displacement
                        other_char.rect.centerx = round(other_char.pos.x) 
                        other_char.rect.bottom = round(other_char.pos.y) # Maintain y anchor   
                        if hasattr(other_char, 'pos'): # Re-sync pos from rect
                            other_char.pos.x = other_char.rect.centerx
                            other_char.pos.y = other_char.rect.bottom
                    
                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom # Update player pos
                    log_player_physics(player, f"CHAR_COLL_X_PUSHBACK",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_push'))

            elif direction == 'y': # Vertical collision (usually landing on top, or bonking head)
                # This part is less common for direct character-on-character vertical resolution
                # unless one is explicitly on top of the other like a platform.
                # Stomping is the primary vertical interaction.
                # If not stomping, simple vertical separation:
                if player.vel.y > 0 and player.rect.bottom > other_char.rect.top and \
                   player.rect.centery < other_char.rect.centery: # Player landing on other
                    player.rect.bottom = other_char.rect.top
                    player.on_ground = True # Considered on ground if landed on another character
                    player.vel.y = 0
                elif player.vel.y < 0 and player.rect.top < other_char.rect.bottom and \
                     player.rect.centery > other_char.rect.centery: # Player bonking head on other from below
                    player.rect.top = other_char.rect.bottom
                    player.vel.y = 0
                
                player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom # Update player pos
                log_player_physics(player, f"CHAR_COLL_Y_STOP",
                                   (player.rect.copy(), current_player_rect_for_log,
                                    (player.pos.x, player.pos.y), player.vel.y, 'y_char_stop'))
    
    return collision_occurred_this_axis


def check_player_hazard_collisions(player, hazards_group: pygame.sprite.Group):
    """
    Handles collisions between the player and hazards like lava.
    Applies damage and effects (e.g., sets player aflame from lava).
    """
    current_time_ms = pygame.time.get_ticks()
    # Check if player is immune to damage (e.g., already dead, in hit cooldown, petrified, frozen)
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or \
       player.is_petrified or player.is_frozen: # Petrified or Frozen players are immune to standard hazards
        return

    damaged_this_frame = False # Flag to ensure damage/effect is applied only once per frame from hazards
    
    # Optimized check: use a point slightly inside the player's bottom center for lava detection
    # This helps avoid issues if only a tiny corner touches.
    # hazard_check_point = (player.rect.centerx, player.rect.bottom - 1) 
    # For more robust detection, check collision with player's rect directly

    collided_hazards = pygame.sprite.spritecollide(player, hazards_group, False)

    for hazard in collided_hazards:
        if isinstance(hazard, Lava): # Check if the hazard is Lava
            # More robust check: ensure significant overlap with lava, not just a pixel
            player_feet_in_lava = player.rect.bottom > hazard.rect.top + (player.rect.height * 0.2) # Feet are reasonably deep
            min_horizontal_hazard_overlap = player.rect.width * 0.20 # At least 20% horizontal overlap
            actual_overlap_width = min(player.rect.right, hazard.rect.right) - max(player.rect.left, hazard.rect.left)

            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame: # Process only once per collision check loop
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (player.rect.copy(), hazard.rect))
                    
                    # --- Apply Effects from Lava ---
                    # 1. Set player aflame
                    if hasattr(player, 'apply_aflame_effect'):
                        player.apply_aflame_effect() # This will handle state changes and timers
                    
                    # 2. Apply initial contact damage from lava (if any)
                    if C.LAVA_DAMAGE > 0 and hasattr(player, 'take_damage'):
                        player.take_damage(C.LAVA_DAMAGE)
                        
                    damaged_this_frame = True # Mark that an interaction with lava happened this frame

                    # Apply knockback/bounce effect from lava
                    if not player.is_dead: # Don't apply bounce if damage killed them
                         player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 # Bounce upwards
                         # Push away horizontally from lava center (or a fixed direction)
                         if player.rect.centerx < hazard.rect.centerx:
                             player.vel.x = -getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         else:
                             player.vel.x = getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         
                         player.on_ground = False # Player is now in air
                         player.on_ladder = False # Knock off ladder
                         # State will be managed by apply_aflame_effect or subsequent logic in player update
                    break # Processed this lava collision, exit hazard loop for this frame
        
        if damaged_this_frame: break # Stop checking other hazards if already interacted with lava