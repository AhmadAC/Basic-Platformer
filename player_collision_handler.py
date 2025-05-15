# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution.
Logs detailed physics information if enabled.
"""
import pygame
import constants as C
from tiles import Lava
from enemy import Enemy

# Import the shared logging flag and helper function from logger.py
from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics

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

    # This rect represents the player's position *after* movement on the current axis
    # but *before* any collision resolution (snapping) within this function.
    # It's assumed player.rect has been updated based on player.vel before this function is called.
    rect_after_current_axis_move = player.rect.copy()
    collided_with_wall_on_side = 0  # Used for X-axis: -1 for left wall, 1 for right wall

    colliding_platforms = pygame.sprite.spritecollide(player, platforms_group, False)

    for platform_sprite in colliding_platforms:
        # For logging, capture the player's rect state *before* this specific platform collision is resolved.
        current_player_rect_for_log = player.rect.copy()

        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}",
                           (current_player_rect_for_log, platform_sprite.rect, platform_sprite.platform_type))

        if direction == 'x':
            # --- X-Axis Collision Resolution ---
            if player.vel.x > 0:  # Moving right
                # Check if the player *just* crossed the left edge of the platform
                if player.rect.right > platform_sprite.rect.left and \
                   rect_after_current_axis_move.left < platform_sprite.rect.left:
                    player.rect.right = platform_sprite.rect.left
                    player.vel.x = 0
                    if not player.on_ground and not player.on_ladder:
                        # Check for significant vertical overlap to confirm it's a wall
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = 1
                    # Update precise position: X from center, Y from bottom (feet)
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_R",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))

            elif player.vel.x < 0:  # Moving left
                # Check if the player *just* crossed the right edge of the platform
                if player.rect.left < platform_sprite.rect.right and \
                   rect_after_current_axis_move.right > platform_sprite.rect.right:
                    player.rect.left = platform_sprite.rect.right
                    player.vel.x = 0
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = -1
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_L",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))

        elif direction == 'y':
            # --- Y-Axis Collision Resolution ---
            if player.vel.y >= 0:  # Moving down or stationary (after gravity)
                # Condition: Player's bottom is at/below platform top, AND player's top was previously above platform top.
                if player.rect.bottom >= platform_sprite.rect.top and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.top and \
                   rect_after_current_axis_move.top < platform_sprite.rect.top + 1: # +1 for int/float tolerance

                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15)
                    min_horizontal_overlap = player.rect.width * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - \
                                           max(player.rect.left, platform_sprite.rect.left)

                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.bottom = platform_sprite.rect.top # Snap to platform

                        # Actions on fresh landing (was in air, moving down)
                        if not player.on_ground and player.vel.y > 0:
                            player.can_wall_jump = False
                            player.wall_climb_timer = 0 # Reset wall climb state
                            if not player.is_sliding and not (hasattr(player, 'state') and player.state.startswith('slide_trans')):
                                landing_friction = getattr(C, 'LANDING_FRICTION_MULTIPLIER', 0.8)
                                player.vel.x *= landing_friction

                        player.on_ground = True
                        player.vel.y = 0
                        player.pos.x = player.rect.centerx
                        player.pos.y = player.rect.bottom # Anchor Y to feet
                        log_player_physics(player, f"PLAT_COLL_Y_LAND",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_land'))

            elif player.vel.y < 0:  # Moving up
                # Condition: Player's top is at/above platform bottom, AND player's bottom was previously below platform bottom.
                if player.rect.top <= platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.top < platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.bottom -1: # -1 for tolerance

                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15)
                    min_horizontal_overlap = player.rect.width * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - \
                                           max(player.rect.left, platform_sprite.rect.left)

                    if actual_overlap_width >= min_horizontal_overlap:
                        if player.on_ladder: player.on_ladder = False # Knock off ladder
                        player.rect.top = platform_sprite.rect.bottom # Snap to ceiling
                        player.vel.y = 0  # Stop upward movement
                        player.pos.x = player.rect.centerx
                        player.pos.y = player.rect.bottom # Anchor Y to feet
                        log_player_physics(player, f"PLAT_COLL_Y_CEIL_NORMAL",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_ceil_norm'))

    # Update player's touching_wall status based on X-axis collisions resolved in this call
    # This is done *after* iterating through all platforms for the current axis.
    if direction == 'x':
        if collided_with_wall_on_side != 0 and not player.on_ground and not player.on_ladder:
            player.touching_wall = collided_with_wall_on_side
            # Allow wall jump unless actively climbing up the wall
            player.can_wall_jump = not (hasattr(player, 'state') and player.state == 'wall_climb' and player.is_holding_climb_ability_key)
        # else:
            # Consider if/how touching_wall should be cleared if no X collision occurs.
            # Often, touching_wall is reset at the start of the player's broader update cycle.
            # If not, player.touching_wall might "stick" if they move away from a wall.
            # For now, this function only SETS touching_wall, doesn't clear it if no x-collision.


# --- The rest of your functions remain unchanged ---
def check_player_ladder_collisions(player, ladders_group: pygame.sprite.Group):
    if not player._valid_init: return
    ladder_check_rect = player.rect.inflate(-player.rect.width * 0.6, -player.rect.height * 0.1)
    player.can_grab_ladder = False
    for ladder_sprite in pygame.sprite.spritecollide(player, ladders_group, False,
                           collided=lambda p_sprite, l_sprite: ladder_check_rect.colliderect(l_sprite.rect)):
        if abs(player.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
           ladder_sprite.rect.top < player.rect.centery < ladder_sprite.rect.bottom :
              player.can_grab_ladder = True; break


def check_player_character_collisions(player, direction: str, characters_list: list):
    if not player._valid_init or player.is_dead or not player.alive(): return False
    collision_occurred_this_axis = False

    # rect_after_axis_move_before_char_snapping = player.rect.copy() # Not strictly used by current logic below

    for other_char in characters_list:
        if other_char is player: continue

        if not (other_char and hasattr(other_char, '_valid_init') and \
                other_char._valid_init and hasattr(other_char, 'is_dead') and \
                not other_char.is_dead and other_char.alive()):
            continue

        if player.rect.colliderect(other_char.rect):
            current_player_rect_for_log = player.rect.copy()
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}",
                               (current_player_rect_for_log, other_char.rect,
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', 'UnknownChar'))))

            collision_occurred_this_axis = True

            is_enemy_stompable = isinstance(other_char, Enemy) and \
                                     not other_char.is_dead and \
                                     not getattr(other_char, 'is_stomp_dying', False)

            if is_enemy_stompable and direction == 'y' and player.vel.y > 0.5: # Ensure downward velocity for stomp
                # More robust stomp check: player's feet were above enemy's head, now at/below
                # rect_after_current_axis_move is needed if you check against player's previous position
                # For simplicity, using current player.pos.y - player.vel.y as a rough estimate of previous bottom
                # A more accurate previous_rect_bottom would be better if available from player's main update
                previous_player_bottom_y_estimate = player.pos.y - player.vel.y # Assuming pos.y is rect.bottom
                # A small grace for enemy head height for stomp
                stomp_head_grace = getattr(C, 'PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX', 5)
                enemy_stomp_target_top = other_char.rect.top + stomp_head_grace

                player_landed_on_enemy_head = (
                    previous_player_bottom_y_estimate <= enemy_stomp_target_top and # Was above
                    player.rect.bottom >= other_char.rect.top and # Is now at or below (but not too far below)
                    player.rect.bottom <= other_char.rect.top + (other_char.rect.height * 0.40) # Don't stomp if already passed through
                )
                if player_landed_on_enemy_head:
                    if hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill() # Enemy handles its death
                        player.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH # Player bounces
                        player.on_ground = False # Player is now in the air
                        if hasattr(player, 'set_state'): player.set_state('jump')
                        player.rect.bottom = other_char.rect.top -1 # Place player just above enemy
                        player.pos.x = player.rect.centerx # Sync pos
                        player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_STOMP",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.y, 'y_stomp'))
                    return True # Stomp collision handled, often no further char collision needed this frame for Y

            # --- Standard Pushback Collision Resolution (if not a stomp) ---
            player_state_str = str(getattr(player, 'state', '')).lower()
            is_attacking_self = getattr(player, 'is_attacking', False) or \
                                ('attack' in player_state_str)

            if direction == 'x':
                if is_attacking_self:
                    # Player is attacking: Snap position, stop own X-velocity.
                    if player.vel.x > 0 or (player.vel.x == 0 and player.rect.centerx < other_char.rect.centerx):
                        player.rect.right = other_char.rect.left
                    elif player.vel.x < 0 or (player.vel.x == 0 and player.rect.centerx >= other_char.rect.centerx):
                        player.rect.left = other_char.rect.right
                    player.vel.x = 0
                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_ATTACK_X_STOP",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_attack_stop'))
                else:
                    # Standard pushback if player is NOT attacking
                    bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                    push_dir_self = 0
                    if player.rect.centerx < other_char.rect.centerx:
                        player.rect.right = other_char.rect.left
                        push_dir_self = -1
                    else:
                        player.rect.left = other_char.rect.right
                        push_dir_self = 1
                    player.vel.x = push_dir_self * bounce_vel

                    other_char_state_str = str(getattr(other_char, 'state', '')).lower()
                    is_attacking_other = getattr(other_char, 'is_attacking', False) or \
                                         ('attack' in other_char_state_str)

                    if hasattr(other_char, 'vel') and not is_attacking_other:
                        other_char.vel.x = -push_dir_self * bounce_vel
                    if hasattr(other_char, 'pos') and hasattr(other_char, 'rect') and not is_attacking_other:
                        # Nudge other char slightly further if possible
                        other_char.pos.x += (-push_dir_self * 1.0) # Reduced nudge to prevent overcorrection
                        other_char.rect.centerx = round(other_char.pos.x) # Assuming other_char.pos.x is its center
                        other_char.rect.bottom = round(other_char.pos.y)   # Assuming other_char.pos.y is its bottom
                        # Re-sync other_char.pos if its rect was directly manipulated
                        if hasattr(other_char, 'pos'): # Re-check because we modified rect
                            other_char.pos.x = other_char.rect.centerx
                            other_char.pos.y = other_char.rect.bottom


                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_X_PUSHBACK",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_push'))

            elif direction == 'y': # Non-stomp vertical character collisions
                # This logic is simple; more robust might involve predicting pass-through
                if player.vel.y > 0 and player.rect.bottom > other_char.rect.top and \
                   player.rect.centery < other_char.rect.centery: # Player is landing on top
                    player.rect.bottom = other_char.rect.top
                    player.on_ground = True # Potentially landing on another character
                    player.vel.y = 0
                elif player.vel.y < 0 and player.rect.top < other_char.rect.bottom and \
                     player.rect.centery > other_char.rect.centery: # Player is hitting from below
                    player.rect.top = other_char.rect.bottom
                    player.vel.y = 0
                player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                log_player_physics(player, f"CHAR_COLL_Y_STOP",
                                   (player.rect.copy(), current_player_rect_for_log,
                                    (player.pos.x, player.pos.y), player.vel.y, 'y_char_stop'))
    return collision_occurred_this_axis


def check_player_hazard_collisions(player, hazards_group: pygame.sprite.Group):
    current_time_ms = pygame.time.get_ticks()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown):
        return

    damaged_this_frame = False
    # Use a slightly inflated rect for hazard collision to make it a bit more forgiving or sensitive
    # hazard_check_rect = player.rect.inflate(2, 2)
    # collided_hazards = pygame.sprite.spritecollide(player, hazards_group, False, pygame.sprite.collide_rect_ratio(0.8)) # Example
    collided_hazards = pygame.sprite.spritecollide(player, hazards_group, False)


    for hazard in collided_hazards:
        if isinstance(hazard, Lava): # Example for Lava, expand for other hazard types
            # More precise check for lava: feet significantly in lava
            player_feet_in_lava = player.rect.bottom > hazard.rect.top + (player.rect.height * 0.2) # e.g. 20% of player height in lava
            min_horizontal_hazard_overlap = player.rect.width * 0.20 # Need some horizontal overlap
            actual_overlap_width = min(player.rect.right, hazard.rect.right) - max(player.rect.left, hazard.rect.left)

            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame:
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (player.rect.copy(), hazard.rect))
                    if hasattr(player, 'take_damage'): player.take_damage(C.LAVA_DAMAGE)
                    damaged_this_frame = True

                    if not player.is_dead: # Knockback from lava
                         player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 # Bounce up
                         # Determine knockback direction based on player's center vs hazard's center
                         if player.rect.centerx < hazard.rect.centerx:
                             player.vel.x = -getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         else:
                             player.vel.x = getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         player.on_ground = False
                         player.on_ladder = False
                         if hasattr(player, 'set_state'): player.set_state('hit' if 'hit' in player.animations else 'jump') # Or a specific 'hit_lava' state
                    break # Processed one hazard damage this frame
        # Add elif for other hazard types here if needed

        if damaged_this_frame: break