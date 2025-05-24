#################### START OF FILE: player_collision_handler.py ####################

# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution for PySide6.
"""
# version 2.0.11 (Refined landing logic for glitch jump fix)

from typing import List, Any, Optional, TYPE_CHECKING
import time

from PySide6.QtCore import QRectF, QPointF

import constants as C
from tiles import Lava # For type hinting
from enemy import Enemy
from statue import Statue
from items import Chest

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE

_SCRIPT_LOGGING_ENABLED = True

try:
    from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics, debug, info, warning
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_PCOLLISION: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PCOLLISION: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PCOLLISION: {msg}")
    ENABLE_DETAILED_PHYSICS_LOGS = False
    def log_player_physics(player, tag, extra=""): pass


_start_time_pcollision = time.monotonic()
def get_current_ticks_monotonic():
    return int((time.monotonic() - _start_time_pcollision) * 1000)


def check_player_platform_collisions(player: 'PlayerClass_TYPE', direction: str, platforms_list: List[Any]):
    if not player._valid_init: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF) or not player.rect.isValid():
        if _SCRIPT_LOGGING_ENABLED: warning(f"Player {player.player_id}: Invalid player rect for platform collision. Skipping.")
        return
    if not hasattr(player, 'vel') or not isinstance(player.vel, QPointF):
        if _SCRIPT_LOGGING_ENABLED: warning(f"Player {player.player_id}: Missing vel attribute. Skipping platform collision.")
        return
    if not hasattr(player, 'pos') or not isinstance(player.pos, QPointF):
        if _SCRIPT_LOGGING_ENABLED: warning(f"Player {player.player_id}: Missing pos attribute. Skipping platform collision.")
        return

    collided_with_wall_on_side_this_frame = 0 # 0: no, 1: right wall, -1: left wall

    for platform_obj in platforms_list:
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or not platform_obj.rect.isValid():
             if _SCRIPT_LOGGING_ENABLED: warning(f"Player Collision: Platform object {platform_obj} missing valid rect. Skipping.")
             continue
        
        if not player.rect.intersects(platform_obj.rect):
            continue

        if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED:
            log_player_physics(player, f"INTERSECT DIR:{direction}",
                               (QRectF(player.rect), QRectF(platform_obj.rect), getattr(platform_obj, 'platform_type', 'unknown')))

        if direction == 'x':
            if player.vel.x() > 0: # Moving right
                overlap_x = player.rect.right() - platform_obj.rect.left()
                if overlap_x > 0: # Collided with platform's left edge
                    player.rect.translate(-overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder:
                        min_v_overlap_for_wall = player.rect.height() * 0.3 
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = 1 
            elif player.vel.x() < 0: # Moving left
                overlap_x = platform_obj.rect.right() - player.rect.left()
                if overlap_x > 0: # Collided with platform's right edge
                    player.rect.translate(overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder:
                        min_v_overlap_for_wall = player.rect.height() * 0.3
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = -1 
            
            if hasattr(player, 'pos') and isinstance(player.pos, QPointF):
                player.pos.setX(player.rect.center().x())

            if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED:
                 log_player_physics(player, f"PLAT_COLL_RESOLVED_X", f"Rect: {player.rect.x():.1f},{player.rect.y():.1f} {player.rect.width():.0f}x{player.rect.height():.0f}, VelX: {player.vel.x():.1f}")

        elif direction == 'y':
            if player.vel.y() >= 0: # Moving down or stationary and intersecting
                overlap_y = player.rect.bottom() - platform_obj.rect.top()
                if overlap_y > 0: 
                    min_h_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.1)
                    min_h_overlap_pixels = player.rect.width() * min_h_overlap_ratio
                    actual_h_overlap = min(player.rect.right(), platform_obj.rect.right()) - \
                                       max(player.rect.left(), platform_obj.rect.left())

                    if actual_h_overlap >= min_h_overlap_pixels:
                        previous_player_bottom_y_estimate = player.rect.bottom() - player.vel.y()
                        was_above_or_at_surface_epsilon = 1.0 
                        was_truly_above_or_at_surface = previous_player_bottom_y_estimate <= platform_obj.rect.top() + was_above_or_at_surface_epsilon
                        
                        can_snap_down_from_current = player.rect.bottom() > platform_obj.rect.top() and \
                                                     player.rect.bottom() <= platform_obj.rect.top() + getattr(C, 'GROUND_SNAP_THRESHOLD', 5.0)

                        # Land if player was truly above OR if already considered on_ground and within snap distance
                        if was_truly_above_or_at_surface or (player.on_ground and can_snap_down_from_current):
                            just_landed = not player.on_ground
                            player.rect.moveBottom(platform_obj.rect.top()) 
                            player.on_ground = True
                            player.vel.setY(0.0)
                            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'): player.acc.setY(0.0)
                            
                            if just_landed:
                                player.can_wall_jump = False
                                if not player.is_sliding and not (hasattr(player, 'state') and str(player.state).startswith('slide_trans')):
                                    player.vel.setX(player.vel.x() * C.LANDING_FRICTION_MULTIPLIER)
                            if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED:
                                 log_player_physics(player, f"PLAT_COLL_Y_LANDED", f"WasAbove:{was_truly_above_or_at_surface}, CanSnap:{can_snap_down_from_current}")
            
            elif player.vel.y() < 0: # Moving up, collided with platform's bottom edge (ceiling)
                overlap_y = platform_obj.rect.bottom() - player.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio_ceil = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.1)
                    min_h_overlap_pixels_ceil = player.rect.width() * min_h_overlap_ratio_ceil
                    actual_h_overlap_ceil = min(player.rect.right(), platform_obj.rect.right()) - \
                                            max(player.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap_ceil >= min_h_overlap_pixels_ceil:
                        if player.on_ladder: player.on_ladder = False 
                        player.rect.translate(0, overlap_y) 
                        player.vel.setY(0.0) 
                        if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED:
                            log_player_physics(player, f"PLAT_COLL_Y_CEILING")
            
            if hasattr(player, 'pos') and isinstance(player.pos, QPointF):
                 player.pos.setY(player.rect.bottom())

    if direction == 'x':
        if collided_with_wall_on_side_this_frame != 0:
            player.touching_wall = collided_with_wall_on_side_this_frame
            can_set_wall_jump_now = not (hasattr(player, 'state') and player.state == 'wall_climb' and \
                                         hasattr(player, 'is_holding_climb_ability_key') and player.is_holding_climb_ability_key)
            if can_set_wall_jump_now:
                player.can_wall_jump = True
        else: 
            if not player.on_ladder: 
                 player.touching_wall = 0


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
             if _SCRIPT_LOGGING_ENABLED: warning(f"Player Collision: Ladder object {ladder_obj} missing valid rect. Skipping.")
             continue
        if ladder_check_rect.intersects(ladder_obj.rect):
            if abs(player.rect.center().x() - ladder_obj.rect.center().x()) < ladder_obj.rect.width() * 0.7 and \
               ladder_obj.rect.top() < player.rect.center().y() < ladder_obj.rect.bottom():
                  player.can_grab_ladder = True; break 

def check_player_character_collisions(player: 'PlayerClass_TYPE', direction: str, characters_list: List[Any]) -> bool:
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: return False
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return False

    collision_occurred_this_axis = False
    rect_before_char_coll_resolve = QRectF(player.rect)

    for other_char in characters_list:
        if other_char is player or \
           not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()):
            continue

        is_chest = isinstance(other_char, Chest)
        is_enemy = isinstance(other_char, Enemy)
        is_statue = isinstance(other_char, Statue)

        if not is_chest and \
           not (hasattr(other_char, '_valid_init') and other_char._valid_init and
                hasattr(other_char, 'is_dead') and
                (not other_char.is_dead or (getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)) ) ):
            continue

        if player.rect.intersects(other_char.rect):
            collision_occurred_this_axis = True
            
            if is_chest:
                chest_obj = other_char 
                if chest_obj.state == 'closed': 
                    if direction == 'x':
                        push_force_dir = 0; overlap_x_chest = 0.0
                        if player.vel.x() > 0 and player.rect.right() > chest_obj.rect.left() and player.rect.center().x() < chest_obj.rect.center().x():
                            overlap_x_chest = player.rect.right() - chest_obj.rect.left()
                            if overlap_x_chest > 0: player.rect.translate(-overlap_x_chest, 0); push_force_dir = 1
                        elif player.vel.x() < 0 and player.rect.left() < chest_obj.rect.right() and player.rect.center().x() > chest_obj.rect.center().x():
                            overlap_x_chest = chest_obj.rect.right() - player.rect.left()
                            if overlap_x_chest > 0: player.rect.translate(overlap_x_chest, 0); push_force_dir = -1
                        if push_force_dir != 0:
                            chest_obj.acc_x = C.CHEST_PUSH_ACCEL_BASE * push_force_dir * (abs(player.vel.x()) / C.PLAYER_RUN_SPEED_LIMIT if C.PLAYER_RUN_SPEED_LIMIT > 0 else 1.0)
                            player.vel.setX(0)
                        if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())
                    elif direction == 'y':
                        if player.vel.y() > 0 and player.rect.bottom() > chest_obj.rect.top() and rect_before_char_coll_resolve.bottom() <= chest_obj.rect.top() + 1:
                            player.rect.moveBottom(chest_obj.rect.top()); player.on_ground = True; player.vel.setY(0)
                        elif player.vel.y() < 0 and player.rect.top() < chest_obj.rect.bottom() and rect_before_char_coll_resolve.top() >= chest_obj.rect.bottom() -1 :
                            player.rect.moveTop(chest_obj.rect.bottom()); player.vel.setY(0)
                        if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())
                continue
            
            is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)

            if is_enemy and getattr(player, 'is_aflame', False) and hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and not getattr(other_char, 'is_aflame', False) and not getattr(other_char, 'is_deflaming', False) and not getattr(other_char, 'is_frozen', False) and not getattr(other_char, 'is_defrosting', False) and not getattr(other_char, 'is_petrified', False) :
                other_char.apply_aflame_effect(); continue 

            is_enemy_stompable = is_enemy and not other_char.is_dead and not getattr(other_char, 'is_stomp_dying', False) and \
                                 not getattr(other_char, 'is_aflame', False) and not getattr(other_char, 'is_frozen', False) and \
                                 not getattr(other_char, 'is_petrified', False) 
            is_statue_stompable = is_statue and not getattr(other_char, 'is_smashed', False)

            if (is_enemy_stompable or is_statue_stompable) and direction == 'y' and player.vel.y() > 0.5: 
                stomp_head_grace = C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                target_stomp_effective_top_y = other_char.rect.top() + stomp_head_grace
                previous_player_bottom_y_for_stomp_calc = player.rect.bottom() - player.vel.y()

                if previous_player_bottom_y_for_stomp_calc <= target_stomp_effective_top_y + 1.0 and \
                   player.rect.bottom() >= other_char.rect.top() and \
                   player.rect.bottom() <= other_char.rect.top() + (other_char.rect.height() * 0.50):
                    
                    stomp_processed = False
                    if is_enemy_stompable and hasattr(other_char, 'stomp_kill'):
                        other_char.stomp_kill(); stomp_processed = True
                    elif is_statue_stompable and hasattr(other_char, 'take_damage'): 
                        other_char.take_damage(999); stomp_processed = True 
                    
                    if stomp_processed:
                        player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH)
                        player.on_ground = False 
                        if hasattr(player, 'set_state'): player.set_state('jump') 
                        player.rect.moveBottom(other_char.rect.top() - 1.0) 
                        if hasattr(player, 'pos'): player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                    return True 
            
            if direction == 'x':
                if getattr(player, 'is_attacking', False) and not is_other_petrified_solid: 
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX'):
                        push_dir_other = 1 if player.rect.center().x() < other_char.rect.center().x() else -1
                        other_char.vel.setX(push_dir_other * C.CHARACTER_BOUNCE_VELOCITY * 0.5) 
                else: 
                    bounce_vel = C.CHARACTER_BOUNCE_VELOCITY; push_dir_self = 0; overlap_x_char = 0.0
                    if player.rect.center().x() < other_char.rect.center().x(): 
                        overlap_x_char = player.rect.right() - other_char.rect.left()
                        if overlap_x_char > 0: player.rect.translate(-overlap_x_char, 0.0); push_dir_self = -1
                    else: 
                        overlap_x_char = other_char.rect.right() - player.rect.left()
                        if overlap_x_char > 0: player.rect.translate(overlap_x_char, 0.0); push_dir_self = 1
                    
                    player.vel.setX(push_dir_self * bounce_vel)
                    can_push_other = not (getattr(other_char, 'is_attacking', False) or \
                                         is_other_petrified_solid or \
                                         getattr(other_char, 'is_dashing', False) or \
                                         getattr(other_char, 'is_rolling', False) or \
                                         getattr(other_char, 'is_aflame', False) or \
                                         getattr(other_char, 'is_frozen', False) )
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other:
                        other_char.vel.setX(-push_dir_self * bounce_vel)
                if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())

            elif direction == 'y': 
                overlap_y_char = 0.0
                if player.vel.y() > 0 and player.rect.bottom() > other_char.rect.top() and \
                   player.rect.center().y() < other_char.rect.center().y(): 
                    overlap_y_char = player.rect.bottom() - other_char.rect.top()
                    if overlap_y_char > 0:
                        player.rect.translate(0, -overlap_y_char)
                        player.on_ground = True 
                        player.vel.setY(0.0)
                elif player.vel.y() < 0 and player.rect.top() < other_char.rect.bottom() and \
                     player.rect.center().y() > other_char.rect.center().y(): 
                    overlap_y_char = other_char.rect.bottom() - player.rect.top()
                    if overlap_y_char > 0:
                        player.rect.translate(0, overlap_y_char)
                        player.vel.setY(0.0) 
                if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())
    
    return collision_occurred_this_axis


def check_player_hazard_collisions(player: 'PlayerClass_TYPE', hazards_list: List[Any]):
    current_time_ms = get_current_ticks_monotonic()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or \
       player.is_petrified or player.is_frozen: 
        return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return

    damaged_this_frame_by_hazard = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF):
            if _SCRIPT_LOGGING_ENABLED: warning(f"Player Collision: Hazard object {hazard_obj} missing valid rect. Skipping.");
            continue
        
        if not player.rect.intersects(hazard_obj.rect):
            continue

        if isinstance(hazard_obj, Lava):
            player_feet_in_lava = player.rect.bottom() > hazard_obj.rect.top() + (player.rect.height() * 0.2)
            min_h_overlap = player.rect.width() * 0.20 
            actual_h_overlap = min(player.rect.right(), hazard_obj.rect.right()) - max(player.rect.left(), hazard_obj.rect.left())
            
            if player_feet_in_lava and actual_h_overlap >= min_h_overlap:
                if not damaged_this_frame_by_hazard: 
                    if hasattr(player, 'apply_aflame_effect'):
                        player.apply_aflame_effect() 

                    if C.LAVA_DAMAGE > 0 and hasattr(player, 'take_damage'):
                        player.take_damage(C.LAVA_DAMAGE)
                    
                    damaged_this_frame_by_hazard = True 

                    if not player.is_dead: 
                         player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75) 
                         push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1
                         player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6) 
                         player.on_ground = False 
                         player.on_ladder = False 
                    break 
        
        if damaged_this_frame_by_hazard:
            break 

#################### END OF FILE: player_collision_handler.py ####################