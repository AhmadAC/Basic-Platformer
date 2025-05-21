# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution for PySide6.
"""
# version 2.0.3 (Corrected QRectF.moveTopLeft/Right argument, refined stomp logic)

from typing import List, Any, Optional, TYPE_CHECKING
import time 

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# Game imports
import constants as C
from tiles import Lava # Assuming Lava is the primary hazard type from tiles
from enemy import Enemy # For isinstance checks
from statue import Statue # For isinstance checks

if TYPE_CHECKING: # To avoid circular import issues at runtime but allow type hinting
    from player import Player as PlayerClass_TYPE

# Logger and physics logging helper
try:
    from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics, debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_PCOLLISION: {msg}")
    def info(msg): print(f"INFO_PCOLLISION: {msg}")
    def warning(msg): print(f"WARNING_PCOLLISION: {msg}")
    ENABLE_DETAILED_PHYSICS_LOGS = False
    def log_player_physics(player, tag, extra=""): pass


_start_time_pcollision = time.monotonic()
def get_current_ticks_monotonic(): # Renamed for clarity
    """
    Returns the number of milliseconds since this module was initialized.
    """
    return int((time.monotonic() - _start_time_pcollision) * 1000)


def check_player_platform_collisions(player: 'PlayerClass_TYPE', direction: str, platforms_list: List[Any]):
    if not player._valid_init: return

    # Store the rect's position *before* this axis's potential movement for more accurate "was previously clear" checks
    # This assumes player.pos was updated by velocity for this axis, then player.rect was synced to that new pos.
    rect_before_collision_resolution_for_this_axis = QRectF(player.rect)
    collided_with_wall_on_side = 0 # Reset for this axis check

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF):
             warning(f"Player Collision: Platform object {platform_obj} missing valid rect. Skipping.")
             continue

        if not player.rect.intersects(platform_obj.rect):
            continue

        # Log only if ENABLE_DETAILED_PHYSICS_LOGS is True (handled by log_player_physics itself)
        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}",
                           (QRectF(player.rect), QRectF(platform_obj.rect), getattr(platform_obj, 'platform_type', 'unknown')))

        if direction == 'x':
            if player.vel.x() > 0: # Moving right, collided with left edge of platform
                # Check if player was to the left of or just touching the platform's left edge before this frame's X move
                if player.rect.right() > platform_obj.rect.left() and \
                   rect_before_collision_resolution_for_this_axis.right() <= platform_obj.rect.left() + 1.0: # +1 for slight tolerance
                    player.rect.moveRight(platform_obj.rect.left())
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder: # Check if it's a wall hit
                        # Ensure significant vertical overlap for wall detection
                        if player.rect.bottom() > platform_obj.rect.top() + C.MIN_WALL_OVERLAP_PX and \
                           player.rect.top() < platform_obj.rect.bottom() - C.MIN_WALL_OVERLAP_PX:
                            collided_with_wall_on_side = 1
            elif player.vel.x() < 0: # Moving left, collided with right edge of platform
                if player.rect.left() < platform_obj.rect.right() and \
                   rect_before_collision_resolution_for_this_axis.left() >= platform_obj.rect.right() - 1.0: # -1 for slight tolerance
                    player.rect.moveLeft(platform_obj.rect.right())
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom() > platform_obj.rect.top() + C.MIN_WALL_OVERLAP_PX and \
                           player.rect.top() < platform_obj.rect.bottom() - C.MIN_WALL_OVERLAP_PX:
                            collided_with_wall_on_side = -1
            # Sync player.pos.x to the new rect center after X collision
            player.pos.setX(player.rect.center().x())
            log_player_physics(player, f"PLAT_COLL_RESOLVED_X", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.x(), player.on_ground, 'x'))


        elif direction == 'y':
            if player.vel.y() >= 0: # Moving down (or stationary but intersecting)
                # Check if player was above or at the same level as platform top before this frame's Y move
                if player.rect.bottom() >= platform_obj.rect.top() and \
                   rect_before_collision_resolution_for_this_axis.bottom() <= platform_obj.rect.top() + 1.0: # +1 for slight tolerance

                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15)
                    min_horizontal_overlap = player.rect.width() * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right(), platform_obj.rect.right()) - \
                                           max(player.rect.left(), platform_obj.rect.left())

                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.moveBottom(platform_obj.rect.top())
                        if not player.on_ground and player.vel.y() > 0: # If just landed
                            player.can_wall_jump = False; player.wall_climb_timer = 0
                            if not player.is_sliding and not (hasattr(player, 'state') and str(player.state).startswith('slide_trans')):
                                player.vel.setX(player.vel.x() * C.LANDING_FRICTION_MULTIPLIER)
                        player.on_ground = True; player.vel.setY(0.0)
                        # Sync player.pos.y to the new rect bottom (anchor point)
                        player.pos.setY(player.rect.bottom())
                        log_player_physics(player, f"PLAT_COLL_Y_LAND", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.y(), player.on_ground, 'y_land'))


            elif player.vel.y() < 0: # Moving up
                # Check if player was below or at the same level as platform bottom before this frame's Y move
                if player.rect.top() <= platform_obj.rect.bottom() and \
                   rect_before_collision_resolution_for_this_axis.top() >= platform_obj.rect.bottom() - 1.0: # -1 for tolerance

                    min_overlap_ratio_ceil = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15)
                    min_horizontal_overlap_ceil = player.rect.width() * min_overlap_ratio_ceil
                    actual_overlap_width_ceil = min(player.rect.right(), platform_obj.rect.right()) - \
                                                max(player.rect.left(), platform_obj.rect.left())

                    if actual_overlap_width_ceil >= min_horizontal_overlap_ceil:
                        if player.on_ladder: player.on_ladder = False # Knock off ladder if hitting ceiling
                        player.rect.moveTop(platform_obj.rect.bottom())
                        player.vel.setY(0.0) # Stop upward movement
                        # Sync player.pos.y to the new rect bottom (anchor point)
                        player.pos.setY(player.rect.bottom())
                        log_player_physics(player, f"PLAT_COLL_Y_CEIL", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.y(), player.on_ground, 'y_ceil'))

    # Update touching_wall status based on side collisions
    if direction == 'x' and collided_with_wall_on_side != 0 and not player.on_ground and not player.on_ladder:
        player.touching_wall = collided_with_wall_on_side
        # Allow wall jump if not actively climbing up and just hit a wall
        can_set_wall_jump = not (hasattr(player, 'state') and player.state == 'wall_climb' and \
                                 hasattr(player, 'is_holding_climb_ability_key') and player.is_holding_climb_ability_key)
        if can_set_wall_jump:
            player.can_wall_jump = True


def check_player_ladder_collisions(player: 'PlayerClass_TYPE', ladders_list: List[Any]):
    if not player._valid_init: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    # Use a slightly smaller rect for ladder grabbing to make it feel more intentional
    ladder_check_rect = QRectF(player.rect)
    ladder_check_rect.setWidth(player.rect.width() * 0.4) # Narrower check
    ladder_check_rect.setHeight(player.rect.height() * 0.9) # Slightly shorter
    ladder_check_rect.moveCenter(player.rect.center())

    player.can_grab_ladder = False
    for ladder_obj in ladders_list:
        if not hasattr(ladder_obj, 'rect') or not isinstance(ladder_obj.rect, QRectF):
             warning(f"Player Collision: Ladder object {ladder_obj} missing valid rect. Skipping."); continue
        
        if ladder_check_rect.intersects(ladder_obj.rect):
            # Check if player is somewhat centered on the ladder and within its vertical bounds
            if abs(player.rect.center().x() - ladder_obj.rect.center().x()) < ladder_obj.rect.width() * 0.7 and \
               ladder_obj.rect.top() < player.rect.center().y() < ladder_obj.rect.bottom():
                  player.can_grab_ladder = True; break


def check_player_character_collisions(player: 'PlayerClass_TYPE', direction: str, characters_list: List[Any]) -> bool:
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified:
        return False
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return False


    collision_occurred_this_axis = False
    for other_char in characters_list:
        if other_char is player or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()):
            continue
        
        if not (hasattr(other_char, '_valid_init') and other_char._valid_init and \
                hasattr(other_char, 'is_dead') and \
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False))): # Allow collision with petrified "dead" entities
            continue

        if player.rect.intersects(other_char.rect):
            current_player_rect_for_log = QRectF(player.rect) # For logging before resolution
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}",
                               (current_player_rect_for_log, QRectF(other_char.rect), # Ensure QRectF for logging
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', getattr(other_char, 'statue_id', 'UnknownChar')))))

            collision_occurred_this_axis = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)

            # Player aflame ignites other character (if other is an Enemy)
            if isinstance(other_char, Enemy) and getattr(player, 'is_aflame', False) and \
               hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               not getattr(other_char, 'is_aflame', False) and not getattr(other_char, 'is_deflaming', False) and \
               not getattr(other_char, 'is_frozen', False) and not getattr(other_char, 'is_defrosting', False) and \
               not getattr(other_char, 'is_petrified', False): # Can't ignite petrified
                
                other_char_id_log = getattr(other_char, 'enemy_id', 'UnknownEnemy')
                debug(f"Player {player.player_id} (aflame) touched Enemy {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                # Typically, fire spread doesn't cause immediate physical pushback in this way
                continue # No physical pushback for this interaction for now

            # Stomp Logic
            is_enemy_stompable = isinstance(other_char, Enemy) and not other_char.is_dead and \
                                 not getattr(other_char, 'is_stomp_dying', False) and \
                                 not getattr(other_char, 'is_aflame', False) and \
                                 not getattr(other_char, 'is_frozen', False) and \
                                 not getattr(other_char, 'is_petrified', False)
            is_statue_stompable = isinstance(other_char, Statue) and not getattr(other_char, 'is_smashed', False)

            if (is_enemy_stompable or is_statue_stompable) and direction == 'y' and player.vel.y() > 0.5: # Player moving down
                # Previous bottom: use player.pos.y() (midbottom) - player.vel.y() (if vel is displacement)
                # Or, if rect was just updated by X-movement, use current rect.bottom() - Y-velocity component for this frame
                # More robust: compare rect.bottom() with target's rect.top()
                
                # Condition: Player's feet are now at or below the target's "head" area,
                # AND the player was above the target's "head" area in the previous logic step for this axis.
                # player.pos.y() is midbottom. player.rect.bottom() is also midbottom.
                # player.vel.y() is current downward velocity.
                # rect_before_y_move_bottom = player.rect.bottom() - (player.vel.y() * dt_sec * C.FPS) # Estimate based on speed
                # For simplicity, if rect is already after Y-pos update:
                rect_before_y_move_bottom = current_player_rect_for_log.bottom() # Use the rect logged before Y collision resolution

                stomp_head_grace = C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                target_stomp_effective_top_y = other_char.rect.top() + stomp_head_grace

                if rect_before_y_move_bottom <= target_stomp_effective_top_y + 1.0 and \
                   player.rect.bottom() >= other_char.rect.top() and \
                   player.rect.bottom() <= other_char.rect.top() + (other_char.rect.height() * 0.50): # Landed on upper part
                    
                    stomp_processed = False
                    if is_enemy_stompable and hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill(); stomp_processed = True
                    elif is_statue_stompable and hasattr(other_char, 'take_damage') and callable(other_char.take_damage): # Statues can be "smashed" by stomp
                        other_char.take_damage(999); stomp_processed = True # Assume high damage smashes it

                    if stomp_processed:
                        player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH)
                        player.on_ground = False # Stomp bounce makes player airborne
                        if hasattr(player, 'set_state'): player.set_state('jump') # Transition to jump state
                        # Adjust player position slightly to ensure they are above the target
                        player.rect.moveBottom(other_char.rect.top() - 1.0) 
                        player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                        log_player_physics(player, f"CHAR_COLL_STOMP_{type(other_char).__name__}", (QRectF(player.rect), current_player_rect_for_log, (player.pos.x(),player.pos.y()), player.vel.y(), f'y_stomp'))
                    return True # Stomp collision handled, no further character collision needed for this pair this frame

            # General Character-to-Character Pushback (if not a stomp)
            player_state_str = str(getattr(player, 'state', '')).lower()
            is_attacking_self = getattr(player, 'is_attacking', False) or ('attack' in player_state_str)

            if direction == 'x':
                if is_attacking_self and not is_other_petrified_solid: # Player attacking, doesn't get pushed back easily
                    # Player pushes other char if not petrified
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX'): # Check method
                        push_dir_other = 1 if player.rect.center().x() < other_char.rect.center().x() else -1
                        other_char.vel.setX(push_dir_other * C.CHARACTER_BOUNCE_VELOCITY * 0.5) # Other char gets pushed less
                else: # Player not attacking, or other is petrified (acts like a wall)
                    bounce_vel = C.CHARACTER_BOUNCE_VELOCITY
                    push_dir_self = 0
                    if player.rect.center().x() < other_char.rect.center().x(): # Player is to the left of other
                        player.rect.moveRight(other_char.rect.left()); push_dir_self = -1 # Move self, set dir for vel
                    else: # Player is to the right
                        player.rect.moveLeft(other_char.rect.right()); push_dir_self = 1
                    player.vel.setX(push_dir_self * bounce_vel)

                    # Other character also gets pushed if not petrified and not in a super-armor state
                    other_char_state_str = str(getattr(other_char, 'state', '')).lower()
                    can_push_other = not (getattr(other_char, 'is_attacking', False) or ('attack' in other_char_state_str)) and \
                                     not is_other_petrified_solid and \
                                     not getattr(other_char, 'is_dashing', False) and \
                                     not getattr(other_char, 'is_rolling', False) and \
                                     not getattr(other_char, 'is_aflame', False) and \
                                     not getattr(other_char, 'is_frozen', False)
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other: 
                        other_char.vel.setX(-push_dir_self * bounce_vel) # Push other in opposite direction
                    if hasattr(other_char, 'pos') and hasattr(other_char, 'rect') and can_push_other:
                        other_char.pos.setX(other_char.pos.x() + (-push_dir_self * 1.0)) # Small displacement
                        if hasattr(other_char, '_update_rect_from_image_and_pos'): other_char._update_rect_from_image_and_pos()
                        elif hasattr(other_char.rect, 'moveCenter'): other_char.rect.moveCenter(QPointF(other_char.pos.x(), other_char.rect.center().y()))

                player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos
                log_player_physics(player, f"CHAR_COLL_X_RESOLVED", (QRectF(player.rect), current_player_rect_for_log, (player.pos.x(),player.pos.y()), player.vel.x(), 'x_push/stop'))

            elif direction == 'y': # Vertical collision (not a stomp)
                if player.vel.y() > 0 and player.rect.bottom() > other_char.rect.top() and \
                   player.rect.center().y() < other_char.rect.center().y(): # Player landing on other
                    player.rect.moveBottom(other_char.rect.top())
                    player.on_ground = True; player.vel.setY(0.0)
                elif player.vel.y() < 0 and player.rect.top() < other_char.rect.bottom() and \
                     player.rect.center().y() > other_char.rect.center().y(): # Player hitting other from below
                    player.rect.moveTop(other_char.rect.bottom())
                    player.vel.setY(0.0)
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos
                log_player_physics(player, f"CHAR_COLL_Y_STOP", (QRectF(player.rect), current_player_rect_for_log, (player.pos.x(),player.pos.y()), player.vel.y(), 'y_char_stop'))

    return collision_occurred_this_axis


def check_player_hazard_collisions(player: 'PlayerClass_TYPE', hazards_list: List[Any]):
    current_time_ms = get_current_ticks_monotonic() 
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or \
       player.is_petrified or player.is_frozen:
        return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    damaged_this_frame = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF):
            warning(f"Player Collision: Hazard object {hazard_obj} missing valid rect. Skipping."); continue
        
        if not player.rect.intersects(hazard_obj.rect): continue

        if isinstance(hazard_obj, Lava):
            # Check for significant overlap with lava
            player_feet_in_lava = player.rect.bottom() > hazard_obj.rect.top() + (player.rect.height() * 0.2) # Feet are submerged
            min_horizontal_hazard_overlap = player.rect.width() * 0.20
            actual_overlap_width = min(player.rect.right(), hazard_obj.rect.right()) - max(player.rect.left(), hazard_obj.rect.left())

            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame: # Apply damage only once per frame from hazards
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (QRectF(player.rect), QRectF(hazard_obj.rect)))
                    if hasattr(player, 'apply_aflame_effect') and callable(player.apply_aflame_effect):
                        player.apply_aflame_effect()
                    if C.LAVA_DAMAGE > 0 and hasattr(player, 'take_damage') and callable(player.take_damage):
                        player.take_damage(C.LAVA_DAMAGE)
                    damaged_this_frame = True
                    
                    if not player.is_dead: # If still alive after lava damage, apply bounce
                         player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75) # Lava bounce
                         # Determine push direction away from hazard center
                         push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1
                         player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6)
                         player.on_ground = False; player.on_ladder = False # Knocked off ground/ladder
                    break # Processed one lava collision, exit loop for this frame
        # Add other hazard types here if needed (e.g., spikes)
        if damaged_this_frame: break