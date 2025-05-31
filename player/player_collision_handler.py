# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution for PySide6.
MODIFIED: Player stomp destroys statues. Smashed statues are not solid.
MODIFIED: Statue stomp detection is more lenient on the top surface.
MODIFIED: Lava instant death property check.
MODIFIED: Character collision does not include solid Statues.
MODIFIED: Added extensive logging for Y-platform collision.
"""
# version 2.0.15 (Enhanced Y-platform collision logging)

from typing import List, Any, Optional, TYPE_CHECKING
import time

from PySide6.QtCore import QRectF, QPointF

import main_game.constants as C
from tiles import Lava
from enemy import Enemy
from player.statue import Statue
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

    collided_with_wall_on_side_this_frame = 0
    player_id_log_collision = f"P{player.player_id} Coll"


    for platform_idx, platform_obj in enumerate(platforms_list):
        if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF) or not platform_obj.rect.isValid():
             if _SCRIPT_LOGGING_ENABLED: warning(f"{player_id_log_collision}: Platform object {platform_idx} missing valid rect. Skipping.")
             continue

        if isinstance(platform_obj, Statue) and platform_obj.is_smashed:
            if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_ignore_smashed_{player.player_id}_{platform_obj.statue_id}"):
                log_player_physics(player, "PLAT_IGNORE_SMASH", f"StatueID: {platform_obj.statue_id}")
            continue

        if not player.rect.intersects(platform_obj.rect):
            continue

        # Intersection detected
        plat_type_debug = getattr(platform_obj, 'platform_type', getattr(platform_obj, 'tile_type', type(platform_obj).__name__))
        # if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_intersect_{player.player_id}_{platform_idx}_{direction}"):
        #     log_player_physics(player, f"INTERSECT DIR:{direction}",
        #                        (f"PlatIdx:{platform_idx} Type:{plat_type_debug} PRect:({platform_obj.rect.x():.1f},{platform_obj.rect.y():.1f} {platform_obj.rect.width():.0f}x{platform_obj.rect.height():.0f})",
        #                         f"PlayerRect:({player.rect.x():.1f},{player.rect.y():.1f} {player.rect.width():.0f}x{player.rect.height():.0f})"))


        original_vel_x_for_ai_reaction = player.vel.x() # Used for enemy AI, player doesn't need this

        if direction == 'x':
            if player.vel.x() > 0: # Moving right, collided with left edge of platform
                overlap_x = player.rect.right() - platform_obj.rect.left()
                if overlap_x > 0:
                    player.rect.translate(-overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder: # Potential wall interaction
                        min_v_overlap_for_wall = player.rect.height() * 0.3
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = 1 # Hit wall on right
            elif player.vel.x() < 0: # Moving left, collided with right edge of platform
                overlap_x = platform_obj.rect.right() - player.rect.left()
                if overlap_x > 0:
                    player.rect.translate(overlap_x, 0)
                    player.vel.setX(0.0)
                    if not player.on_ground and not player.on_ladder: # Potential wall interaction
                        min_v_overlap_for_wall = player.rect.height() * 0.3
                        actual_v_overlap = min(player.rect.bottom(), platform_obj.rect.bottom()) - max(player.rect.top(), platform_obj.rect.top())
                        if actual_v_overlap > min_v_overlap_for_wall:
                            collided_with_wall_on_side_this_frame = -1 # Hit wall on left
            
            player.pos.setX(player.rect.center().x()) # Sync pos X from resolved rect center
            # if ENABLE_DETAILED_PHYSICS_LOGS and _SCRIPT_LOGGING_ENABLED and player.print_limiter.can_log(f"plat_coll_x_res_{player.player_id}_{platform_idx}"):
            #      log_player_physics(player, f"PLAT_COLL_RESOLVED_X", f"PlatIdx:{platform_idx} Rect: {player.rect.x():.1f},{player.rect.y():.1f} {player.rect.width():.0f}x{player.rect.height():.0f}, VelX: {player.vel.x():.1f}")

        elif direction == 'y':
            if player.vel.y() >= 0: # Moving downwards or on ground and snapping
                overlap_y = player.rect.bottom() - platform_obj.rect.top()
                if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_coll_y_detail_P{player.player_id}_Plat{platform_idx}"):
                    debug(f"{player_id_log_collision} Y-DOWN INTERSECT PlatIdx:{platform_idx} ({plat_type_debug} at {platform_obj.rect.topLeft().y():.1f}) OverlapY:{overlap_y:.2f} PlayerBottom:{player.rect.bottom():.2f} PlayerVelY:{player.vel.y():.2f} PlayerOnGround:{player.on_ground}")

                if overlap_y > 0: # Potential collision with top surface of platform
                    min_h_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.1)
                    min_h_overlap_pixels = player.rect.width() * min_h_overlap_ratio
                    actual_h_overlap = min(player.rect.right(), platform_obj.rect.right()) - \
                                       max(player.rect.left(), platform_obj.rect.left())
                    
                    if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_coll_y_horiz_overlap_P{player.player_id}_Plat{platform_idx}"):
                        debug(f"{player_id_log_collision} Y-DOWN HorizOverlap Check PlatIdx:{platform_idx}: ActualHOverlap:{actual_h_overlap:.2f}, MinHPixels:{min_h_overlap_pixels:.2f} (PlayerW:{player.rect.width():.1f})")

                    if actual_h_overlap >= min_h_overlap_pixels:
                        if isinstance(platform_obj, Statue) and not platform_obj.is_smashed and player.vel.y() > 0.5: # Stomp
                            previous_player_bottom_y_for_stomp_calc = player.rect.bottom() - player.vel.y() # Approx based on current frame vel
                            statue_top_surface_for_check = platform_obj.rect.top()
                            can_stomp_this_statue = False
                            if previous_player_bottom_y_for_stomp_calc <= statue_top_surface_for_check + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX + 1.0 and \
                               player.rect.bottom() >= statue_top_surface_for_check and \
                               player.rect.bottom() <= statue_top_surface_for_check + (platform_obj.rect.height() * 0.75): # Allow some penetration for stomp registration
                                can_stomp_this_statue = True
                            if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"stomp_statue_check_P{player.player_id}_Statue{platform_obj.statue_id}"):
                                debug(f"{player_id_log_collision} StompStatue Check: CanStomp:{can_stomp_this_statue}, PrevPlayerBottom:{previous_player_bottom_y_for_stomp_calc:.1f}, StatueTop:{statue_top_surface_for_check:.1f}")
                            if can_stomp_this_statue:
                                if hasattr(platform_obj, 'get_stomped') and callable(platform_obj.get_stomped):
                                    platform_obj.get_stomped(player)
                                    player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH)
                                    player.on_ground = False
                                    if hasattr(player, 'set_state'): player.set_state('jump')
                                    player.rect.moveBottom(platform_obj.rect.top() - 1.0)
                                    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                                    if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "STOMPED_STATUE", f"StatueID: {platform_obj.statue_id}")
                                    continue # Processed stomp, skip rest for this platform

                        previous_player_bottom_y_estimate = player.rect.bottom() - player.vel.y()
                        was_above_or_at_surface_epsilon = 1.0
                        was_truly_above_or_at_surface = previous_player_bottom_y_estimate <= platform_obj.rect.top() + was_above_or_at_surface_epsilon
                        can_snap_down_from_current = player.on_ground and \
                                                     player.rect.bottom() > platform_obj.rect.top() and \
                                                     player.rect.bottom() <= platform_obj.rect.top() + getattr(C, 'GROUND_SNAP_THRESHOLD', 5.0)

                        if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_coll_y_snap_check_P{player.player_id}_Plat{platform_idx}"):
                            debug(f"{player_id_log_collision} Y-DOWN SnapCheck PlatIdx:{platform_idx}: WasAbove:{was_truly_above_or_at_surface}, CanSnap:{can_snap_down_from_current}, PrevPlayerBottomEst:{previous_player_bottom_y_estimate:.1f}, PlatTop:{platform_obj.rect.top():.1f}")

                        if was_truly_above_or_at_surface or can_snap_down_from_current:
                            just_landed = not player.on_ground
                            player.rect.moveBottom(platform_obj.rect.top())
                            player.on_ground = True
                            player.vel.setY(0.0)
                            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'): player.acc.setY(0.0)
                            if just_landed:
                                player.can_wall_jump = False
                                if not player.is_sliding and not (hasattr(player, 'state') and str(player.state).startswith('slide_trans')):
                                    player.vel.setX(player.vel.x() * C.LANDING_FRICTION_MULTIPLIER)
                            if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_coll_y_land_P{player.player_id}_Plat{platform_idx}"):
                                 log_player_physics(player, f"PLAT_COLL_Y_LANDED", f"PlatIdx:{platform_idx} JustLand:{just_landed}")
            
            elif player.vel.y() < 0: # Moving upwards, collided with bottom surface of platform
                overlap_y = platform_obj.rect.bottom() - player.rect.top()
                if overlap_y > 0:
                    min_h_overlap_ratio_ceil = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.1)
                    min_h_overlap_pixels_ceil = player.rect.width() * min_h_overlap_ratio_ceil
                    actual_h_overlap_ceil = min(player.rect.right(), platform_obj.rect.right()) - \
                                            max(player.rect.left(), platform_obj.rect.left())
                    if actual_h_overlap_ceil >= min_h_overlap_pixels_ceil:
                        if player.on_ladder: player.on_ladder = False
                        player.rect.translate(0, overlap_y) # Move player down
                        player.vel.setY(0.0) # Stop upward movement
                        if _SCRIPT_LOGGING_ENABLED and ENABLE_DETAILED_PHYSICS_LOGS and player.print_limiter.can_log(f"plat_coll_y_ceil_P{player.player_id}_Plat{platform_idx}"):
                            log_player_physics(player, f"PLAT_COLL_Y_CEILING", f"PlatIdx:{platform_idx}")
            
            player.pos.setY(player.rect.bottom()) # Sync pos Y from resolved rect bottom

    if direction == 'x':
        if collided_with_wall_on_side_this_frame != 0:
            player.touching_wall = collided_with_wall_on_side_this_frame
            can_set_wall_jump_now = not (hasattr(player, 'state') and player.state == 'wall_climb' and \
                                         hasattr(player, 'is_holding_climb_ability_key') and player.is_holding_climb_ability_key)
            if can_set_wall_jump_now: player.can_wall_jump = True
        else:
            if not player.on_ladder: player.touching_wall = 0


def check_player_ladder_collisions(player: 'PlayerClass_TYPE', ladders_list: List[Any]):
    # ... (this function remains largely the same) ...
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
    # ... (this function remains largely the same, but ensure Statue logic is correct) ...
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: return False
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return False
    collision_occurred_this_axis = False
    rect_before_char_coll_resolve = QRectF(player.rect)
    for other_char in characters_list:
        if other_char is player or not hasattr(other_char, 'rect') or not isinstance(other_char.rect, QRectF) or \
           not (hasattr(other_char, 'alive') and other_char.alive()): continue
        if isinstance(other_char, Statue) and not other_char.is_smashed: continue # Solid statues are platforms
        is_chest = isinstance(other_char, Chest); is_enemy = isinstance(other_char, Enemy)
        if not is_chest:
            is_other_valid_target = (hasattr(other_char, '_valid_init') and other_char._valid_init and hasattr(other_char, 'is_dead') and (not other_char.is_dead or (getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)) ) )
            if not is_other_valid_target: continue
        if player.rect.intersects(other_char.rect):
            collision_occurred_this_axis = True; is_other_petrified_solid = getattr(other_char, 'is_petrified', False) and not getattr(other_char, 'is_stone_smashed', False)
            if is_chest:
                chest_obj = other_char
                if chest_obj.state == 'closed':
                    if direction == 'x':
                        push_force_dir = 0; overlap_x_chest = 0.0
                        if player.vel.x() > 0 and player.rect.right() > chest_obj.rect.left() and player.rect.center().x() < chest_obj.rect.center().x(): overlap_x_chest = player.rect.right() - chest_obj.rect.left(); player.rect.translate(-overlap_x_chest, 0); push_force_dir = 1
                        elif player.vel.x() < 0 and player.rect.left() < chest_obj.rect.right() and player.rect.center().x() > chest_obj.rect.center().x(): overlap_x_chest = chest_obj.rect.right() - player.rect.left(); player.rect.translate(overlap_x_chest, 0); push_force_dir = -1
                        if push_force_dir != 0 and hasattr(chest_obj, 'acc_x') and hasattr(player, 'vel') and hasattr(player.vel, 'x'): chest_obj.acc_x = C.CHEST_PUSH_ACCEL_BASE * push_force_dir * (abs(player.vel.x()) / C.PLAYER_RUN_SPEED_LIMIT if C.PLAYER_RUN_SPEED_LIMIT > 0 else 1.0); player.vel.setX(0)
                        if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())
                    elif direction == 'y':
                        if player.vel.y() > 0 and player.rect.bottom() > chest_obj.rect.top() and rect_before_char_coll_resolve.bottom() <= chest_obj.rect.top() + 1: player.rect.moveBottom(chest_obj.rect.top()); player.on_ground = True; player.vel.setY(0)
                        elif player.vel.y() < 0 and player.rect.top() < chest_obj.rect.bottom() and rect_before_char_coll_resolve.top() >= chest_obj.rect.bottom() -1 : player.rect.moveTop(chest_obj.rect.bottom()); player.vel.setY(0)
                        if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())
                continue
            is_other_susceptible_to_fire = not (getattr(other_char, 'is_aflame', False) or getattr(other_char, 'is_frozen', False) or getattr(other_char, 'is_petrified', False))
            if is_enemy and getattr(player, 'is_aflame', False) and hasattr(other_char, 'apply_aflame_effect') and callable(other_char.apply_aflame_effect) and is_other_susceptible_to_fire and not is_other_petrified_solid: other_char.apply_aflame_effect()
            is_enemy_stompable = is_enemy and not other_char.is_dead and not getattr(other_char, 'is_stomp_dying', False) and not getattr(other_char, 'is_aflame', False) and not getattr(other_char, 'is_frozen', False) and not is_other_petrified_solid
            if is_enemy_stompable and direction == 'y' and player.vel.y() > 0.5:
                previous_player_bottom_y_for_stomp_calc = rect_before_char_coll_resolve.bottom() - player.vel.y()
                stomp_head_grace_enemy = C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX; target_stomp_effective_top_y_enemy = other_char.rect.top() + stomp_head_grace_enemy
                if previous_player_bottom_y_for_stomp_calc <= target_stomp_effective_top_y_enemy + 1.0 and player.rect.bottom() >= other_char.rect.top() and player.rect.bottom() <= other_char.rect.top() + (other_char.rect.height() * 0.65):
                    if hasattr(other_char, 'stomp_kill'): other_char.stomp_kill(); player.vel.setY(C.PLAYER_STOMP_BOUNCE_STRENGTH); player.on_ground = False;
                    if hasattr(player, 'set_state'): player.set_state('jump'); player.rect.moveBottom(other_char.rect.top() - 1.0)
                    if hasattr(player, 'pos'): player.pos = QPointF(player.rect.center().x(), player.rect.bottom()); return True
            if direction == 'x':
                if getattr(player, 'is_attacking', False) and not is_other_petrified_solid:
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX'): push_dir_other = 1 if player.rect.center().x() < other_char.rect.center().x() else -1; other_char.vel.setX(push_dir_other * C.CHARACTER_BOUNCE_VELOCITY * 0.5)
                else:
                    bounce_vel = C.CHARACTER_BOUNCE_VELOCITY; push_dir_self = 0; overlap_x_char = 0.0
                    if player.rect.center().x() < other_char.rect.center().x(): overlap_x_char = player.rect.right() - other_char.rect.left(); player.rect.translate(-overlap_x_char, 0.0); push_dir_self = -1
                    else: overlap_x_char = other_char.rect.right() - player.rect.left(); player.rect.translate(overlap_x_char, 0.0); push_dir_self = 1
                    player.vel.setX(push_dir_self * bounce_vel)
                    can_push_other = not (getattr(other_char, 'is_attacking', False) or is_other_petrified_solid or getattr(other_char, 'is_dashing', False) or getattr(other_char, 'is_rolling', False) or getattr(other_char, 'is_aflame', False) or getattr(other_char, 'is_frozen', False) )
                    if hasattr(other_char, 'vel') and hasattr(other_char.vel, 'setX') and can_push_other: other_char.vel.setX(-push_dir_self * bounce_vel)
                if hasattr(player, 'pos'): player.pos.setX(player.rect.center().x())
            elif direction == 'y':
                overlap_y_char = 0.0
                if player.vel.y() > 0 and player.rect.bottom() > other_char.rect.top() and player.rect.center().y() < other_char.rect.center().y(): overlap_y_char = player.rect.bottom() - other_char.rect.top(); player.rect.translate(0, -overlap_y_char); player.on_ground = True; player.vel.setY(0.0)
                elif player.vel.y() < 0 and player.rect.top() < other_char.rect.bottom() and player.rect.center().y() > other_char.rect.center().y(): overlap_y_char = other_char.rect.bottom() - player.rect.top(); player.rect.translate(0, overlap_y_char); player.vel.setY(0.0)
                if hasattr(player, 'pos'): player.pos.setY(player.rect.bottom())
    return collision_occurred_this_axis


def check_player_hazard_collisions(player: 'PlayerClass_TYPE', hazards_list: List[Any]):
    # ... (this function remains largely the same) ...
    current_time_ms = get_current_ticks_monotonic()
    if not player._valid_init or player.is_dead or not player.alive() or (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or player.is_petrified or player.is_frozen: return
    if not hasattr(player, 'rect') or not isinstance(player.rect, QRectF): return
    damaged_this_frame_by_hazard = False
    for hazard_obj in hazards_list:
        if not hasattr(hazard_obj, 'rect') or not isinstance(hazard_obj.rect, QRectF):
            if _SCRIPT_LOGGING_ENABLED: warning(f"Player Collision: Hazard object {hazard_obj} missing valid rect. Skipping."); continue
        if not player.rect.intersects(hazard_obj.rect): continue
        if isinstance(hazard_obj, Lava):
            player_feet_in_lava = player.rect.bottom() > hazard_obj.rect.top() + (player.rect.height() * 0.2)
            min_h_overlap = player.rect.width() * 0.20
            actual_h_overlap = min(player.rect.right(), hazard_obj.rect.right()) - max(player.rect.left(), hazard_obj.rect.left())
            if player_feet_in_lava and actual_h_overlap >= min_h_overlap:
                if hasattr(hazard_obj, 'properties') and hazard_obj.properties.get("is_instant_death", False):
                    if hasattr(player, 'insta_kill'): player.insta_kill(); info(f"Player {player.player_id} insta-killed by lava hazard (property).")
                    else: player.take_damage(player.max_health * 10)
                    damaged_this_frame_by_hazard = True
                    if not player.is_dead: player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75); push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1; player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6); player.on_ground = False; player.on_ladder = False
                    break
                elif not damaged_this_frame_by_hazard:
                    if hasattr(player, 'apply_aflame_effect'): player.apply_aflame_effect()
                    lava_damage = int(getattr(C, 'LAVA_DAMAGE', 25))
                    if lava_damage > 0 and hasattr(player, 'take_damage'): player.take_damage(lava_damage)
                    damaged_this_frame_by_hazard = True
                    if not player.is_dead: player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.75); push_dir = 1 if player.rect.center().x() < hazard_obj.rect.center().x() else -1; player.vel.setX(-push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7.0) * 0.6); player.on_ground = False; player.on_ladder = False
                    break
        if damaged_this_frame_by_hazard: break