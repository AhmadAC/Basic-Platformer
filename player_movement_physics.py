#################### START OF FILE: player_movement_physics.py ####################

# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
"""
# version 2.0.1 

from typing import List, Any, Optional # Added Optional
import time # For get_current_ticks fallback

# PySide6 imports
from PySide6.QtCore import QPointF, QRectF # For type hints and direct use if needed

# Game imports
import constants as C
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
# player_animation_handler is called by player_state_handler
from player_state_handler import set_player_state

from logger import info, debug, warning, error, critical, ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics


_start_time_player_physics = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.

    """
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def manage_player_state_timers_and_cooldowns(player):
    """
    Manages timers for player states like dashing, rolling, sliding, and hit stun.
    Transitions player out of these states when timers expire.
    """
    current_time_ms = get_current_ticks()

    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide': # Only transition if still in the main slide state
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else:
                set_player_state(player, 'crouch' if player.is_crouching else 'idle')

    # Hit stun invulnerability period (is_taking_hit flag)
    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        player.is_taking_hit = False # Invulnerability ends
        # Visual 'hit' state (flinch) duration is typically shorter than cooldown
        # and handled by animation transitions or when player initiates a new action.
        # If player was stuck in 'hit' state visually after cooldown, revert.
        if player.state == 'hit' and not player.is_dead: # Check not dead for safety
             set_player_state(player, 'idle' if player.on_ground else 'fall')


def apply_player_movement_and_physics(player):
    """Applies physics like gravity, friction, and velocity limits to the player."""
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # Use y()
        player.is_dashing or
        player.is_frozen or
        player.is_defrosting
    )
    if should_apply_gravity:
        player.vel.setY(player.vel.y() + player.acc.y()) # Use setY for QPointF

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
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            nudge_accel_x = roll_control_accel_magnitude

        player.vel.setX(player.vel.x() + nudge_accel_x)
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15
        min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4
        current_vel_x = player.vel.x() # Use x()
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
    else:
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or
            (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # Use y()
            player.is_frozen or player.is_defrosting
        )
        if should_apply_horizontal_physics:
            actual_accel_to_apply = player.acc.x() # Use x()
            if player.is_aflame: actual_accel_to_apply *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: actual_accel_to_apply *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)

            player.vel.setX(player.vel.x() + actual_accel_to_apply)

            friction_coeff = 0.0
            if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide': # Use x()
                friction_coeff = C.PLAYER_FRICTION
            elif not player.on_ground and not player.is_attacking and \
                 player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']:
                friction_coeff = C.PLAYER_FRICTION * 0.2
            elif player.is_sliding or player.state == 'slide':
                friction_coeff = C.PLAYER_FRICTION * 0.7

            if friction_coeff != 0:
                 friction_force = player.vel.x() * friction_coeff # Use x()
                 if abs(player.vel.x()) > 0.1: player.vel.setX(player.vel.x() + friction_force)
                 else: player.vel.setX(0.0)

                 if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                     if slide_end_key: set_player_state(player, slide_end_key)
                     else: set_player_state(player, 'crouch' if player.is_crouching else 'idle')

            current_h_speed_limit = base_player_run_speed_limit
            if player.is_crouching and player.state == 'crouch_walk': current_h_speed_limit *= 0.6
            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))
        elif player.is_frozen or player.is_defrosting:
            player.vel.setX(0.0); player.acc.setX(0.0)

    if player.vel.y() > 0 and not player.on_ladder: # Use y()
        player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0))) # Use setY


def update_player_core_logic(player, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    if not player._valid_init or not player.alive(): return # Use player.alive()

    if getattr(player, 'is_petrified', False):
        log_player_physics(player, "UPDATE_BLOCKED", "Player is petrified/smashed")
        return

    log_player_physics(player, "UPDATE_START")

    if player.is_dead: # This block handles "normal" death animation physics
        if player.alive() and hasattr(player, 'animate'): # Use player.alive()
            if not player.death_animation_finished:
                if not player.on_ground:
                    player.vel.setY(player.vel.y() + player.acc.y())
                    player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                    player.pos.setY(player.pos.y() + player.vel.y())
                    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()

                    player.on_ground = False
                    for platform_obj in platforms_list:
                        if hasattr(platform_obj, 'rect') and player.rect.intersects(platform_obj.rect):
                            if player.vel.y() > 0 and player.rect.bottom() > platform_obj.rect.top() and \
                               (player.pos.y() - player.vel.y()) <= platform_obj.rect.top() + 1:
                                player.rect.moveBottom(platform_obj.rect.top())
                                player.on_ground = True; player.vel.setY(0.0); player.acc.setY(0.0)
                                player.pos = QPointF(player.rect.center().x(), player.rect.bottom()); break # Update pos from rect
            # Animation update for death is called outside this if block usually
            if hasattr(player, 'animate'): player.animate() # Call player's own animate method
        log_player_physics(player, "UPDATE_END", "Player is dead")
        return

    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list) # Assumes ladders_list contains objects with .rect (QRectF)
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player)

    player.touching_wall = 0
    player.on_ground = False # Reset before collision checks for current frame

    # Horizontal movement and collision
    player.pos.setX(player.pos.x() + player.vel.x())
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    log_player_physics(player, "X_MOVE_APPLIED")
    check_player_platform_collisions(player, 'x', platforms_list)
    log_player_physics(player, "X_PLAT_COLL_DONE")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) # Sync pos.x from rect center
        # player.pos.setY(player.rect.bottom()) # Keep Y anchor consistent
        check_player_platform_collisions(player, 'x', platforms_list) # Re-check if pushed into platform
        log_player_physics(player, "X_PLAT_RECHECK")

    # Vertical movement and collision
    player.pos.setY(player.pos.y() + player.vel.y())
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    log_player_physics(player, "Y_MOVE_APPLIED")
    check_player_platform_collisions(player, 'y', platforms_list)
    log_player_physics(player, "Y_PLAT_COLL_DONE")

    if not collided_horizontally_char: # Only check vertical char collision if not already resolved by horizontal
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from rect
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check
            log_player_physics(player, "Y_PLAT_RECHECK")

    # Final position sync after all collision resolution
    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
    log_player_physics(player, "FINAL_POS_SYNC")

    check_player_hazard_collisions(player, hazards_list)

    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack) # Call player's method

    if hasattr(player, 'animate'): player.animate() # Call player's own animate method
    log_player_physics(player, "UPDATE_END")

#################### END OF FILE: player_movement_physics.py ####################