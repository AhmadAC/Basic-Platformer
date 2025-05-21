# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution for PySide6.
"""
# version 2.0.5 (Corrected gravity application logic after landing/wall interaction)

from typing import List, Any, Optional, TYPE_CHECKING
import time

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF

# Game imports
import constants as C
from tiles import Lava
from enemy import Enemy
from statue import Statue

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE

try:
    from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics, debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_PCOLLISION: {msg}")
    def info(msg): print(f"INFO_PCOLLISION: {msg}")
    def warning(msg): print(f"WARNING_PCOLLISION: {msg}")
    ENABLE_DETAILED_PHYSICS_LOGS = False
    def log_player_physics(player, tag, extra=""): pass


_start_time_pcollision = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_pcollision) * 1000)


def check_player_platform_collisions(player: 'PlayerClass_TYPE', direction: str, platforms_list: List[Any]):
    if not player._valid_init: return

    rect_before_collision_resolution_for_this_axis = QRectF(player.rect)
    collided_with_wall_on_side_this_frame = 0 # Track wall collision for this specific axis check

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF):
             warning(f"Player Collision: Platform object {platform_obj} missing valid rect. Skipping.")
             continue

        if not player.rect.intersects(platform_obj.rect):
            continue

        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}",
                           (QRectF(player.rect), QRectF(platform_obj.rect), getattr(platform_obj, 'platform_type', 'unknown')))

        if direction == 'x':
            wall_snap_tolerance = getattr(C, 'CEILING_SNAP_THRESHOLD', 2.0)

            if player.vel.x() > 0: # Moving right
                if player.rect.right() > platform_obj.rect.left() and \
                   rect_before_collision_resolution_for_this_axis.right() <= platform_obj.rect.left() + wall_snap_tolerance:
                    player.rect.moveRight(platform_obj.rect.left())
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom() > platform_obj.rect.top() + C.MIN_WALL_OVERLAP_PX and \
                           player.rect.top() < platform_obj.rect.bottom() - C.MIN_WALL_OVERLAP_PX:
                            collided_with_wall_on_side_this_frame = 1
            elif player.vel.x() < 0: # Moving left
                if player.rect.left() < platform_obj.rect.right() and \
                   rect_before_collision_resolution_for_this_axis.left() >= platform_obj.rect.right() - wall_snap_tolerance:
                    player.rect.moveLeft(platform_obj.rect.right())
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom() > platform_obj.rect.top() + C.MIN_WALL_OVERLAP_PX and \
                           player.rect.top() < platform_obj.rect.bottom() - C.MIN_WALL_OVERLAP_PX:
                            collided_with_wall_on_side_this_frame = -1
            player.pos.setX(player.rect.center().x())
            log_player_physics(player, f"PLAT_COLL_RESOLVED_X", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.x(), player.on_ground, 'x'))

        elif direction == 'y':
            if player.vel.y() >= 0: # Moving down (or stationary and intersecting)
                if player.rect.bottom() >= platform_obj.rect.top() and \
                   rect_before_collision_resolution_for_this_axis.bottom() <= platform_obj.rect.top() + C.GROUND_SNAP_THRESHOLD:
                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15)
                    min_horizontal_overlap = player.rect.width() * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right(), platform_obj.rect.right()) - \
                                           max(player.rect.left(), platform_obj.rect.left())

                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.moveBottom(platform_obj.rect.top())
                        if not player.on_ground and player.vel.y() > 0:
                            player.can_wall_jump = False; player.wall_climb_timer = 0
                            if not player.is_sliding and not (hasattr(player, 'state') and str(player.state).startswith('slide_trans')):
                                player.vel.setX(player.vel.x() * C.LANDING_FRICTION_MULTIPLIER)
                        player.on_ground = True; player.vel.setY(0.0)
                        # player.acc.setY(0.0) # REMOVED - Gravity should persist in acc.y
                        player.pos.setY(player.rect.bottom())
                        log_player_physics(player, f"PLAT_COLL_Y_LAND", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.y(), player.on_ground, 'y_land'))

            elif player.vel.y() < 0: # Moving up
                if player.rect.top() <= platform_obj.rect.bottom() and \
                   rect_before_collision_resolution_for_this_axis.top() >= platform_obj.rect.bottom() - C.CEILING_SNAP_THRESHOLD:
                    min_overlap_ratio_ceil = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15)
                    min_horizontal_overlap_ceil = player.rect.width() * min_overlap_ratio_ceil
                    actual_overlap_width_ceil = min(player.rect.right(), platform_obj.rect.right()) - \
                                                max(player.rect.left(), platform_obj.rect.left())
                    if actual_overlap_width_ceil >= min_horizontal_overlap_ceil:
                        if player.on_ladder: player.on_ladder = False
                        player.rect.moveTop(platform_obj.rect.bottom())
                        player.vel.setY(0.0)
                        player.pos.setY(player.rect.bottom())
                        log_player_physics(player, f"PLAT_COLL_Y_CEIL", (QRectF(player.rect), QRectF(rect_before_collision_resolution_for_this_axis), (player.pos.x(), player.pos.y()), player.vel.y(), player.on_ground, 'y_ceil'))

    # Update touching_wall status only if a wall collision occurred in this axis check
    # and player is not on ground or ladder (which would override wall interactions)
    if direction == 'x' and collided_with_wall_on_side_this_frame != 0:
        if not player.on_ground and not player.on_ladder:
            player.touching_wall = collided_with_wall_on_side_this_frame
            can_set_wall_jump = not (hasattr(player, 'state') and player.state == 'wall_climb' and \
                                     hasattr(player, 'is_holding_climb_ability_key') and player.is_holding_climb_ability_key)
            if can_set_wall_jump:
                player.can_wall_jump = True
        # If player became grounded during this X-axis check (unlikely but possible due to complex shapes),
        # then wall interactions might be voided. However, on_ground is primarily set by Y-axis collision.
    elif direction == 'x' and collided_with_wall_on_side_this_frame == 0:
        # If no X collision with a platform this frame, and not already on a ladder, clear touching_wall
        # (unless it's maintained by a character collision, handled elsewhere)
        if not player.on_ladder:
             player.touching_wall = 0 # Reset if no wall hit this frame for X
             player.can_wall_jump = False # Cannot wall jump if not touching wall from platform


def check_player_ladder_collisions(player: 'PlayerClass_TYPE', ladders_list: List[Any]):
    if not player._valid_init: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    ladder_check_rect = QRectF(player.rect)
    ladder_check_rect.setWidth(player.rect.width() * 0.4)
    ladder_check_rect.setHeight(player.rect.height() * 0.9)
    ladder_check_rect.moveCenter(player.rect.center())

    player.can_grab_ladder = False
    for ladder_obj in ladders_list:
        if not hasattr(ladder_obj, 'rect') or not isinstance(ladder_obj.rect, QRectF):
             warning(f"Player Collision: Ladder object {ladder_obj} missing valid rect. Skipping."); continue

        if ladder_check_rect.intersects(ladder_obj.rect):
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
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False))):
            continue

        if player.rect.intersects(other_char.rect):
            current_player_rect_for_log = QRectF(player.rect)
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}",
                               (current_player_rect_for_log, QRectF(other_char.rect),
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', getattr(other_char, 'statue_id', 'UnknownChar')))))

            collision_occurred_this_axis = True
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)

            if isinstance(other_char, Enemy) and getattr(player, 'is_aflame', False) and \
               hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and \
               not getattr(other_char, 'is_aflame', False) and not getattr(other_char, 'is_deflaming', False) and \
               not getattr(other_char, 'is_frozen', False) and not getattr(other_char, 'is_defrosting', False) and \
               not getattr(other_char, 'is_petrified', False):
                other_char_id_log = getattr(other_char, 'enemy_id', 'UnknownEnemy')
                debug(f"Player {player.player_id} (aflame) touched Enemy {other_char_id_log}. Igniting.")
                other_char.apply_aflame_effect()
                continue

            is_enemy_stompable = isinstance(other_char, Enemy) and not other_char.is_dead and \
                                 not getattr(other_char, 'is_stomp_dying', False) and \
                                 not getattr(other_char, 'is_aflame', False) and \
                                 not getattr(other_char, 'is_frozen', False) and \
                                 not getattr(other_char, 'is_petrified', False)
            is_statue_stompable = isinstance(other_char, Statue) and not getattr(other_char, 'is_smashed', False)

            if (is_enemy_stompable or is_statue_stompable) and direction == 'y' and player.vel.y() > 0.5:
                rect_before_y_move_bottom = current_player_rect_for_log.bottom()
                stomp_head_grace = C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                target_stomp_effective_top_y = other_char.rect.top() + stomp_head_grace

                if rect_before_y_move_bottom <= target_stomp_effective_top_y + 1.0 and \
                   player.rect.bottom() >= other_char.rect.top() and \
                   player.rect.bottom() <= other_char.rect.top() + (other_char.rect.height() * 0.50):
                    stomp_processed = False
                    if is_enemy_stompable and hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill(); stomp_processed = True
                    elif is_statue_stompable and hasattr(other_char, 'take_damage') and callable(other_char.take_damage):
                        other_char.take_damage(999); stomp_processed = True

                    if stomp_processed:
                        player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH)
                        player.on_ground = False
                        if hasattr(player, 'set_state'): player.set_state('jump')
                        player.rect.moveBottom(other_char.rect.top() - 1.0)
                        player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                        log_player_physics(player, f"CHAR_COLL_STOMP_{type(other_char).__name__}", (QRectF(player.rect), current_player_rect_for_log, (player.pos.x(),player.pos.y()), player.vel.y(), f'y_stomp'))
                    return True

            player_state_str = str(getattr(player, 'state', '')).lower()
            is_attacking_self = getattr(player, 'is_attacking', False) or ('attack' in player_state_str)

            if direction == 'x':
                if is_attacking_self and not is_other_petrified_solid:
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX'):
                        push_dir_other = 1 if player.rect.center().x() < other_char.rect.center().x() else -1
                        other_char.vel.setX(push_dir_other * C.CHARACTER_BOUNCE_VELOCITY * 0.5)
                else:
                    bounce_vel = C.CHARACTER_BOUNCE_VELOCITY
                    push_dir_self = 0
                    if player.rect.center().x() < other_char.rect.center().x():
                        player.rect.moveRight(other_char.rect.left()); push_dir_self = -1
                    else:
                        player.rect.moveLeft(other_char.rect.right()); push_dir_self = 1
                    player.vel.setX(push_dir_self * bounce_vel)
                    other_char_state_str = str(getattr(other_char, 'state', '')).lower()
                    can_push_other = not (getattr(other_char, 'is_attacking', False) or ('attack' in other_char_state_str)) and \
                                     not is_other_petrified_solid and \
                                     not getattr(other_char, 'is_dashing', False) and \
                                     not getattr(other_char, 'is_rolling', False) and \
                                     not getattr(other_char, 'is_aflame', False) and \
                                     not getattr(other_char, 'is_frozen', False)
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other:
                        other_char.vel.setX(-push_dir_self * bounce_vel)
                    if hasattr(other_char, 'pos') and hasattr(other_char, 'rect') and can_push_other:
                        other_char.pos.setX(other_char.pos.x() + (-push_dir_self * 1.0))
                        if hasattr(other_char, '_update_rect_from_image_and_pos'): other_char._update_rect_from_image_and_pos()
                        elif hasattr(other_char.rect, 'moveCenter'): other_char.rect.moveCenter(QPointF(other_char.pos.x(), other_char.rect.center().y()))
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                log_player_physics(player, f"CHAR_COLL_X_RESOLVED", (QRectF(player.rect), current_player_rect_for_log, (player.pos.x(),player.pos.y()), player.vel.x(), 'x_push/stop'))

            elif direction == 'y':
                if player.vel.y() > 0 and player.rect.bottom() > other_char.rect.top() and \
                   player.rect.center().y() < other_char.rect.center().y():
                    player.rect.moveBottom(other_char.rect.top())
                    player.on_ground = True; player.vel.setY(0.0)
                elif player.vel.y() < 0 and player.rect.top() < other_char.rect.bottom() and \
                     player.rect.center().y() > other_char.rect.center().y():
                    player.rect.moveTop(other_char.rect.bottom())
                    player.vel.setY(0.0)
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
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
            player_feet_in_lava = player.rect.bottom() > hazard_obj.rect.top() + (player.rect.height() * 0.2)
            min_horizontal_hazard_overlap = player.rect.width() * 0.20
            actual_overlap_width = min(player.rect.right(), hazard_obj.rect.right()) - max(player.rect.left(), hazard_obj.rect.left())

            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame:
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (QRectF(player.rect), QRectF(hazard_obj.rect)))
                    if hasattr(player, 'apply_aflame_effect') and callable(player.apply_aflame_effect):
                        player.apply_aflame_effect()
                    if C.LAVA_DAMAGE > 0 and hasattr(player, 'take_damage') and callable(player.take_damage):
                        player.take_damage(C.LAVA_DAMAGE)
                    damaged_this_frame = True
                    if not player.is_dead:
                         player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75)
                         push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1
                         player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6)
                         player.on_ground = False; player.on_ladder = False
                    break
        if damaged_this_frame: break