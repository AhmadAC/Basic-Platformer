# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
"""
# version 2.0.4 (Added more comprehensive debug prints for movement and jump logic)

from typing import List, Any, Optional, TYPE_CHECKING
import time

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
from player_state_handler import set_player_state

from logger import info, debug, warning, error, critical, ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics


_start_time_player_physics = time.monotonic()
def get_current_ticks(): # Renamed for consistency with other modules if needed
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def manage_player_state_timers_and_cooldowns(player):
    current_time_ms = get_current_ticks()
    player_id_str = f"P{player.player_id}"

    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        debug(f"{player_id_str} Physics Timers: Dash timer expired. is_dashing -> False.")
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        debug(f"{player_id_str} Physics Timers: Roll timer expired. is_rolling -> False.")
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide':
            debug(f"{player_id_str} Physics Timers: Slide timer expired. is_sliding -> False.")
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else:
                set_player_state(player, 'crouch' if player.is_crouching else 'idle')

    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        debug(f"{player_id_str} Physics Timers: Hit cooldown expired. is_taking_hit -> False.")
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead:
             set_player_state(player, 'idle' if player.on_ground else 'fall')


def apply_player_movement_and_physics(player):
    player_id_str = f"P{player.player_id}"
    debug_this_call = ENABLE_DETAILED_PHYSICS_LOGS # Use local flag for conciseness

    if debug_this_call:
        debug(f"{player_id_str} ApplyPhysics START: state='{player.state}', on_ground={player.on_ground}, on_ladder={player.on_ladder}, "
              f"is_dashing={player.is_dashing}, is_rolling={player.is_rolling}, is_sliding={player.is_sliding}, "
              f"is_frozen={player.is_frozen}, is_petrified={player.is_petrified}, "
              f"vel=({player.vel.x():.2f}, {player.vel.y():.2f}), acc=({player.acc.x():.2f}, {player.acc.y():.2f})")

    # Determine if gravity should be applied
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or
        player.is_dashing or
        player.is_frozen or
        player.is_defrosting or
        (player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground)
    )
    if debug_this_call: debug(f"{player_id_str} ApplyPhysics: should_apply_gravity = {should_apply_gravity}")

    # Set vertical acceleration (gravity)
    if player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground:
        player.acc.setY(0.0) # No gravity if petrified on ground
        if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Petrified on ground, acc.y set to 0.")
    elif not player.on_ladder: # Ladders handle their own vertical movement/acceleration
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Not on ladder, acc.y set to gravity: {player.acc.y():.2f}")
    # else: acc.y remains as is (might be 0 if on ladder and input handler set it)

    if should_apply_gravity:
        old_vel_y = player.vel.y()
        player.vel.setY(player.vel.y() + player.acc.y())
        if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Gravity applied. Old vel.y={old_vel_y:.2f}, acc.y={player.acc.y():.2f}, New vel.y={player.vel.y():.2f}")

    # Horizontal acceleration and speed limits
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
        if debug_this_call: debug(f"{player_id_str} ApplyPhysics (Rolling): Nudge={nudge_accel_x:.2f}, Final vel.x={player.vel.x():.2f}")
    else: 
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or
            (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or
            player.is_frozen or player.is_defrosting or
            (player.is_petrified and not getattr(player, 'is_stone_smashed', False))
        )
        if debug_this_call: debug(f"{player_id_str} ApplyPhysics: should_apply_horizontal_physics = {should_apply_horizontal_physics}")

        if should_apply_horizontal_physics:
            actual_accel_to_apply = player.acc.x() # player.acc.x is set by input handler
            if player.is_aflame: actual_accel_to_apply *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: actual_accel_to_apply *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
            
            old_vel_x = player.vel.x()
            player.vel.setX(player.vel.x() + actual_accel_to_apply)
            if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Horizontal accel. Old vel.x={old_vel_x:.2f}, input_accel={player.acc.x():.2f}, actual_accel_applied={actual_accel_to_apply:.2f}, New vel.x={player.vel.x():.2f}")

            friction_coeff = 0.0
            if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide':
                friction_coeff = C.PLAYER_FRICTION
            elif not player.on_ground and not player.is_attacking and \
                 player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']:
                friction_coeff = C.PLAYER_FRICTION * 0.2
            elif player.is_sliding or player.state == 'slide':
                friction_coeff = C.PLAYER_FRICTION * 0.7

            if friction_coeff != 0:
                 friction_force = player.vel.x() * friction_coeff
                 if abs(player.vel.x()) > 0.1:
                     player.vel.setX(player.vel.x() + friction_force)
                     if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Friction applied ({friction_coeff:.2f}). New vel.x={player.vel.x():.2f}")
                 else:
                     player.vel.setX(0.0)
                     if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Friction brought vel.x to 0.")

                 if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                     if slide_end_key: set_player_state(player, slide_end_key)
                     else: set_player_state(player, 'crouch' if player.is_crouching else 'idle')
                     if debug_this_call: debug(f"{player_id_str} ApplyPhysics: Exited slide due to low speed.")

            current_h_speed_limit = base_player_run_speed_limit
            if player.is_crouching and player.state == 'crouch_walk': current_h_speed_limit *= 0.6
            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                old_vel_x_before_clamp = player.vel.x()
                player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))
                if debug_this_call and abs(old_vel_x_before_clamp - player.vel.x()) > 0.01:
                    debug(f"{player_id_str} ApplyPhysics: Speed limit applied. Old vel.x={old_vel_x_before_clamp:.2f}, Limit={current_h_speed_limit:.2f}, New vel.x={player.vel.x():.2f}")

        elif player.is_frozen or player.is_defrosting or \
             (player.is_petrified and not getattr(player, 'is_stone_smashed', False)):
            player.vel.setX(0.0); player.acc.setX(0.0) # Ensure no horizontal movement

    # Clamp vertical speed (terminal velocity)
    if player.vel.y() > 0 and not player.on_ladder: # Falling
        old_vel_y_before_terminal = player.vel.y()
        player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
        if debug_this_call and abs(old_vel_y_before_terminal - player.vel.y()) > 0.01 :
            debug(f"{player_id_str} ApplyPhysics: Terminal velocity applied. Old vel.y={old_vel_y_before_terminal:.2f}, New vel.y={player.vel.y():.2f}")

    if debug_this_call: debug(f"{player_id_str} ApplyPhysics END: Final vel=({player.vel.x():.2f}, {player.vel.y():.2f})")


def update_player_core_logic(player, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    player_id_str = f"P{player.player_id}"
    if not player._valid_init or not player.alive():
        debug(f"{player_id_str} CoreLogic: Update skipped. _valid_init={player._valid_init}, alive={player.alive()}")
        return

    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_START")
    debug(f"{player_id_str} CoreLogic START: state={player.state}, pos=({player.pos.x():.1f},{player.pos.y():.1f}), vel=({player.vel.x():.1f},{player.vel.y():.1f}), acc=({player.acc.x():.1f},{player.acc.y():.1f}), on_ground={player.on_ground}")

    # --- Dead Player Physics ---
    if player.is_dead and not player.is_petrified:
        if player.alive() and not player.death_animation_finished:
            if not player.on_ground:
                original_acc_y = player.acc.y()
                player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
                player.vel.setY(player.vel.y() + player.acc.y())
                player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                player.pos.setY(player.pos.y() + player.vel.y()) # Assuming vel is per-frame if dt*FPS is 1
                if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
                player.on_ground = False
                check_player_platform_collisions(player, 'y', platforms_list)
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
                player.acc.setY(original_acc_y) # Restore original acc.y if needed, though usually gravity stays
        if hasattr(player, 'animate'): player.animate()
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END", "Player is dead (normal)")
        debug(f"{player_id_str} CoreLogic END: Player is dead (normal). Final pos=({player.pos.x():.1f},{player.pos.y():.1f})")
        return

    # --- Petrified Player Physics ---
    if player.is_petrified:
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_PETRIFIED_START", f"Smashed: {player.is_stone_smashed}, OnGround: {player.on_ground}")
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
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END", "Player is petrified/smashed")
        debug(f"{player_id_str} CoreLogic END: Player is petrified/smashed. Final pos=({player.pos.x():.1f},{player.pos.y():.1f})")
        return

    # --- Active Player Logic ---
    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list)
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player)

    player.touching_wall = 0
    player.on_ground = False # Reset before Y collision checks for this frame

    # --- Horizontal movement and collision ---
    old_pos_x = player.pos.x()
    # Corrected: velocity should be scaled by dt_sec if it's per-second, or just added if per-frame.
    # If C.FPS is the target and dt_sec is 1/C.FPS, then vel.x() * dt_sec * C.FPS = vel.x()
    # For clarity, let's assume vel.x() is already per-frame delta.
    player.pos.setX(player.pos.x() + player.vel.x()) 
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_MOVE_APPLIED")
    debug(f"{player_id_str} CoreLogic X-Move: old_pos_x={old_pos_x:.2f}, vel_x={player.vel.x():.2f} (intended per-frame delta), new_pos_x_before_coll={player.pos.x():.2f}")
    
    check_player_platform_collisions(player, 'x', platforms_list)
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_PLAT_COLL_DONE")
    debug(f"{player_id_str} CoreLogic X-PlatColl: pos_x_after={player.rect.center().x():.2f}, vel_x_after={player.vel.x():.2f}, touching_wall={player.touching_wall}")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x())
        check_player_platform_collisions(player, 'x', platforms_list) # Re-check
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_PLAT_RECHECK")
        debug(f"{player_id_str} CoreLogic X-CharCollRecheck: pos_x={player.rect.center().x():.2f}, vel_x={player.vel.x():.2f}")

    # --- Vertical movement and collision ---
    old_pos_y = player.pos.y()
    player.pos.setY(player.pos.y() + player.vel.y()) # Assuming vel is per-frame delta
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_MOVE_APPLIED")
    debug(f"{player_id_str} CoreLogic Y-Move: old_pos_y={old_pos_y:.2f}, vel_y={player.vel.y():.2f}, new_pos_y_before_coll={player.pos.y():.2f}")

    check_player_platform_collisions(player, 'y', platforms_list)
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_PLAT_COLL_DONE")
    debug(f"{player_id_str} CoreLogic Y-PlatColl: pos_y_after={player.rect.bottom():.2f}, vel_y_after={player.vel.y():.2f}, on_ground={player.on_ground}")

    if not collided_horizontally_char:
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check
            if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_PLAT_RECHECK")
            debug(f"{player_id_str} CoreLogic Y-CharCollRecheck: pos_y={player.rect.bottom():.2f}, vel_y={player.vel.y():.2f}, on_ground={player.on_ground}")

    player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Final sync
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "FINAL_POS_SYNC")
    debug(f"{player_id_str} CoreLogic FinalSync: pos=({player.pos.x():.1f},{player.pos.y():.1f}) rect_bottom={player.rect.bottom():.1f}")

    check_player_hazard_collisions(player, hazards_list)

    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    if hasattr(player, 'animate'): player.animate()
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END")
    debug(f"{player_id_str} CoreLogic END: state={player.state}, pos=({player.pos.x():.1f},{player.pos.y():.1f}), vel=({player.vel.x():.1f},{player.vel.y():.1f}), on_ground={player.on_ground}")