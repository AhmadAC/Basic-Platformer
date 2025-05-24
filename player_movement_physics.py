# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
"""
# version 2.0.6 (File-level global rate limit for all logs: max 1 per second from this file)

from typing import List, Any, Optional, TYPE_CHECKING
import time

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C
from statue import Statue 
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
from player_state_handler import set_player_state

# Logger import - import the module itself and specific flags/classes
import logger as app_logger
from logger import ENABLE_DETAILED_PHYSICS_LOGS, RateLimiter # Make sure RateLimiter is importable from logger.py

# --- File-specific Rate Limiter Setup ---
# This rate limiter ensures that this entire script ('player_movement_physics.py')
# does not log more than one message (of any level) per second.
_physics_file_rate_limiter = RateLimiter(default_period_sec=1.0)
_PHYSICS_FILE_LOG_KEY = "player_movement_physics_log_tick_v2" # Unique key for this file

def _can_log_from_this_file_internal() -> bool:
    """Checks if a log message can be emitted from this file based on its rate limit."""
    # This check is independent of whether LOGGING_ENABLED is true in app_logger,
    # as the app_logger functions will handle that.
    return _physics_file_rate_limiter.can_proceed(_PHYSICS_FILE_LOG_KEY, period_sec=1.0)

# --- Local Logging Wrappers for this File ---
# These wrappers apply the file-specific rate limit before calling the app_logger.

def _file_debug(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal():
        app_logger.debug(message, *args, **kwargs)

def _file_info(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal():
        app_logger.info(message, *args, **kwargs)

def _file_warning(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal():
        app_logger.warning(message, *args, **kwargs)

def _file_error(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal():
        app_logger.error(message, *args, **kwargs)

def _file_critical(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal():
        app_logger.critical(message, *args, **kwargs)

def _file_log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    # app_logger.log_player_physics already checks ENABLE_DETAILED_PHYSICS_LOGS
    # and uses its own (potentially global debug) rate limiter.
    # We add this file's specific rate limit on top.
    if _can_log_from_this_file_internal():
        app_logger.log_player_physics(player, message_tag, extra_info)
# --- End of Local Logging Wrappers ---


_start_time_player_physics = time.monotonic()
def get_current_ticks() -> int: 
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def manage_player_state_timers_and_cooldowns(player: Any): 
    current_time_ms = get_current_ticks()
    player_id_str = f"P{player.player_id}"

    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        _file_debug(f"{player_id_str} Physics Timers: Dash timer expired. is_dashing -> False.")
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        _file_debug(f"{player_id_str} Physics Timers: Roll timer expired. is_rolling -> False.")
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide': 
            _file_debug(f"{player_id_str} Physics Timers: Slide timer expired. is_sliding -> False.")
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else: 
                set_player_state(player, 'crouch' if player.is_crouching else 'idle')

    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        _file_debug(f"{player_id_str} Physics Timers: Hit cooldown expired. is_taking_hit -> False.")
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead: 
             set_player_state(player, 'idle' if player.on_ground else 'fall')


def apply_player_movement_and_physics(player: Any): 
    player_id_str = f"P{player.player_id}"
    debug_this_call = ENABLE_DETAILED_PHYSICS_LOGS 

    # if debug_this_call:
    #     _file_debug(f"{player_id_str} ApplyPhysics START: state='{player.state}', on_ground={player.on_ground}, on_ladder={player.on_ladder}, "
    #           f"is_dashing={player.is_dashing}, is_rolling={player.is_rolling}, is_sliding={player.is_sliding}, "
    #           f"is_frozen={player.is_frozen}, is_petrified={player.is_petrified}, "
    #           f"vel=({player.vel.x():.2f}, {player.vel.y():.2f}), acc=({player.acc.x():.2f}, {player.acc.y():.2f})")

    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        player.is_dashing or
        player.is_frozen or
        player.is_defrosting or
        (player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground)
    )
    # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: should_apply_gravity = {should_apply_gravity}")

    if player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground:
        player.acc.setY(0.0)
        # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Petrified on ground, acc.y set to 0.")
    elif not player.on_ladder:
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Not on ladder, acc.y set to gravity: {player.acc.y():.2f}")

    if should_apply_gravity:
        old_vel_y = player.vel.y()
        player.vel.setY(player.vel.y() + player.acc.y()) 
        # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Gravity applied. Old vel.y={old_vel_y:.2f}, acc.y={player.acc.y():.2f}, New vel.y={player.vel.y():.2f}")

    base_player_accel = C.PLAYER_ACCEL
    base_player_run_speed_limit = C.PLAYER_RUN_SPEED_LIMIT
    if player.is_aflame:
        base_player_accel *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_AFLAME_SPEED_MULTIPLIER', 1.0)
    elif player.is_deflaming:
        base_player_accel *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_DEFLAME_SPEED_MULTIPLIER', 1.0)
    
    if player.is_rolling:
        roll_control_accel_magnitude = base_player_accel * C.PLAYER_ROLL_CONTROL_ACCEL_FACTOR
        nudge_accel_x = 0.0
        if player.is_trying_to_move_left and not player.is_trying_to_move_right: nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left: nudge_accel_x = roll_control_accel_magnitude
        player.vel.setX(player.vel.x() + nudge_accel_x) 
        
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15; min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4
        current_vel_x = player.vel.x()
        if current_vel_x > 0:
            current_vel_x = min(current_vel_x, max_roll_speed_cap)
            if player.facing_right: current_vel_x = max(current_vel_x, min_roll_speed_cap) 
        elif current_vel_x < 0:
            current_vel_x = max(current_vel_x, -max_roll_speed_cap)
            if not player.facing_right: current_vel_x = min(current_vel_x, -min_roll_speed_cap) 
        player.vel.setX(current_vel_x)
        
        if nudge_accel_x == 0 and abs(player.vel.x()) > 0.1: 
             player.vel.setX(player.vel.x() * 0.99) 
             if abs(player.vel.x()) < 0.5: player.vel.setX(0.0) 
        # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics (Rolling): Nudge={nudge_accel_x:.2f}, Final vel.x={player.vel.x():.2f}")
    else: 
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or
            player.is_frozen or player.is_defrosting or
            (player.is_petrified and not getattr(player, 'is_stone_smashed', False))
        )
        # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: should_apply_horizontal_physics = {should_apply_horizontal_physics}")

        if should_apply_horizontal_physics:
            actual_accel_to_apply_x = player.acc.x() 
            
            old_vel_x = player.vel.x()
            player.vel.setX(player.vel.x() + actual_accel_to_apply_x) 
            # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Horizontal accel. Old vel.x={old_vel_x:.2f}, input_accel={player.acc.x():.2f}, actual_accel_applied={actual_accel_to_apply_x:.2f}, New vel.x={player.vel.x():.2f}")

            friction_coeff = 0.0
            if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide':
                friction_coeff = C.PLAYER_FRICTION 
            elif not player.on_ground and not player.is_attacking and \
                 player.state not in ['wall_slide','wall_hang']: 
                friction_coeff = C.PLAYER_FRICTION * 0.2 
            elif player.is_sliding or player.state == 'slide':
                friction_coeff = C.PLAYER_FRICTION * 0.7 

            if friction_coeff != 0: 
                 friction_force_per_frame = player.vel.x() * friction_coeff 
                 if abs(player.vel.x()) > 0.1:
                     player.vel.setX(player.vel.x() + friction_force_per_frame)
                     # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Friction applied ({friction_coeff:.2f}). New vel.x={player.vel.x():.2f}")
                 else:
                     player.vel.setX(0.0)
                     # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Friction brought vel.x to 0.")

                 if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                     if slide_end_key: set_player_state(player, slide_end_key)
                     else: set_player_state(player, 'crouch' if player.is_crouching else 'idle')
                     # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics: Exited slide due to low speed.")

            current_h_speed_limit = base_player_run_speed_limit
            if player.is_crouching and player.state == 'crouch_walk':
                current_h_speed_limit *= 0.6
            
            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                old_vel_x_before_clamp = player.vel.x()
                player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))
                # if debug_this_call and abs(old_vel_x_before_clamp - player.vel.x()) > 0.01:
                #     _file_debug(f"{player_id_str} ApplyPhysics: Speed limit applied. Old vel.x={old_vel_x_before_clamp:.2f}, Limit={current_h_speed_limit:.2f}, New vel.x={player.vel.x():.2f}")

        elif player.is_frozen or player.is_defrosting or \
             (player.is_petrified and not getattr(player, 'is_stone_smashed', False)):
            player.vel.setX(0.0); player.acc.setX(0.0) 

    if player.vel.y() > 0 and not player.on_ladder: 
        old_vel_y_before_terminal = player.vel.y()
        player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
        # if debug_this_call and abs(old_vel_y_before_terminal - player.vel.y()) > 0.01 :
        #     _file_debug(f"{player_id_str} ApplyPhysics: Terminal velocity applied. Old vel.y={old_vel_y_before_terminal:.2f}, New vel.y={player.vel.y():.2f}")

    # if debug_this_call: _file_debug(f"{player_id_str} ApplyPhysics END: Final vel=({player.vel.x():.2f}, {player.vel.y():.2f})")


def update_player_core_logic(player: Any, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    player_id_str = f"P{player.player_id}"
    if not player._valid_init or not player.alive():
        _file_debug(f"{player_id_str} CoreLogic: Update skipped. _valid_init={player._valid_init}, alive={player.alive()}")
        return

    _file_log_player_physics(player, "UPDATE_START")
    # _file_debug(f"{player_id_str} CoreLogic START: state={player.state}, pos=({player.pos.x():.1f},{player.pos.y():.1f}), vel=({player.vel.x():.1f},{player.vel.y():.1f}), acc=({player.acc.x():.1f},{player.acc.y():.1f}), on_ground={player.on_ground}")

    if player.is_dead and not player.is_petrified: 
        if player.alive() and not player.death_animation_finished: 
            if not player.on_ground: 
                original_acc_y_dead = player.acc.y() 
                player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
                player.vel.setY(player.vel.y() + player.acc.y())
                player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                player.pos.setY(player.pos.y() + player.vel.y()) 
                if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
                
                player.on_ground = False 
                check_player_platform_collisions(player, 'y', platforms_list)
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) 
                player.acc.setY(original_acc_y_dead) 
        
        if hasattr(player, 'animate'): player.animate()
        _file_log_player_physics(player, "UPDATE_END", "Player is dead (normal)")
        _file_debug(f"{player_id_str} CoreLogic END (Dead): Final pos=({player.pos.x():.1f},{player.pos.y():.1f})")
        return

    if player.is_petrified:
        _file_log_player_physics(player, "UPDATE_PETRIFIED_START", f"Smashed: {player.is_stone_smashed}, OnGround: {player.on_ground}")
        if not player.is_stone_smashed and not player.on_ground: 
            original_acc_y_petri = player.acc.y()
            player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
            player.vel.setY(player.vel.y() + player.acc.y())
            player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
            player.pos.setY(player.pos.y() + player.vel.y())
            if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
            check_player_platform_collisions(player, 'y', platforms_list)
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
            player.acc.setY(original_acc_y_petri)
        elif player.is_stone_smashed: 
            player.vel = QPointF(0,0); player.acc = QPointF(0,0)
        
        if hasattr(player, 'animate'): player.animate() 
        _file_log_player_physics(player, "UPDATE_END", "Player is petrified/smashed")
        _file_debug(f"{player_id_str} CoreLogic END (Petrified): Final pos=({player.pos.x():.1f},{player.pos.y():.1f})")
        return

    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list) 
    
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player) 

    player.touching_wall = 0 
    player.on_ground = False 

    old_pos_x = player.pos.x()
    player.pos.setX(player.pos.x() + player.vel.x()) 
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "X_MOVE_APPLIED")
    # _file_debug(f"{player_id_str} CoreLogic X-Move: old_pos_x={old_pos_x:.2f}, vel_x={player.vel.x():.2f}, new_pos_x_before_coll={player.pos.x():.2f}")
    
    check_player_platform_collisions(player, 'x', platforms_list)
    _file_log_player_physics(player, "X_PLAT_COLL_DONE")
    # _file_debug(f"{player_id_str} CoreLogic X-PlatColl: pos_x_after={player.rect.center().x():.2f}, vel_x_after={player.vel.x():.2f}, touching_wall={player.touching_wall}")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        _file_log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) 
        check_player_platform_collisions(player, 'x', platforms_list) 
        _file_log_player_physics(player, "X_PLAT_RECHECK")
        # _file_debug(f"{player_id_str} CoreLogic X-CharCollRecheck: pos_x={player.rect.center().x():.2f}, vel_x={player.vel.x():.2f}")

    old_pos_y = player.pos.y()
    player.pos.setY(player.pos.y() + player.vel.y()) 
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "Y_MOVE_APPLIED")
    # _file_debug(f"{player_id_str} CoreLogic Y-Move: old_pos_y={old_pos_y:.2f}, vel_y={player.vel.y():.2f}, new_pos_y_before_coll={player.pos.y():.2f}")

    check_player_platform_collisions(player, 'y', platforms_list) 
    _file_log_player_physics(player, "Y_PLAT_COLL_DONE")
    # _file_debug(f"{player_id_str} CoreLogic Y-PlatColl: pos_y_after={player.rect.bottom():.2f}, vel_y_after={player.vel.y():.2f}, on_ground={player.on_ground}")

    if not collided_horizontally_char: 
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            _file_log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) 
            check_player_platform_collisions(player, 'y', platforms_list) 
            _file_log_player_physics(player, "Y_PLAT_RECHECK")
            # _file_debug(f"{player_id_str} CoreLogic Y-CharCollRecheck: pos_y={player.rect.bottom():.2f}, vel_y={player.vel.y():.2f}, on_ground={player.on_ground}")

    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
    _file_log_player_physics(player, "FINAL_POS_SYNC")
    # _file_debug(f"{player_id_str} CoreLogic FinalSync: pos=({player.pos.x():.1f},{player.pos.y():.1f}) rect_bottom={player.rect.bottom():.1f}")

    check_player_hazard_collisions(player, hazards_list)

    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        statues_list_for_attack = player.game_elements_ref_for_projectiles.get("statue_objects", []) if player.game_elements_ref_for_projectiles else []
        targets_for_player_attack.extend([s for s in statues_list_for_attack if isinstance(s, Statue) and s.alive()])


        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    if hasattr(player, 'animate'): player.animate()
    _file_log_player_physics(player, "UPDATE_END")
    # _file_debug(f"{player_id_str} CoreLogic END: state={player.state}, pos=({player.pos.x():.1f},{player.pos.y():.1f}), vel=({player.vel.x():.1f},{player.vel.y():.1f}), on_ground={player.on_ground}")