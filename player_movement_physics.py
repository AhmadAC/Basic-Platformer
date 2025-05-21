# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
"""
# version 2.0.2 (Corrected gravity application after landing/wall interaction for dead players too)
# version 2.0.3 (Further refined gravity and state interactions)

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
def get_current_ticks():
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def manage_player_state_timers_and_cooldowns(player):
    current_time_ms = get_current_ticks()

    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide': # Ensure it was in main slide state, not transition
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else: # If no transition, go to crouch or idle
                set_player_state(player, 'crouch' if player.is_crouching else 'idle')

    # Hit stun / invincibility cooldown
    if player.is_taking_hit and (current_time_ms - player.hit_timer >= player.hit_cooldown):
        player.is_taking_hit = False # End invincibility period
        # If player was visually in 'hit' state and no longer taking damage, transition
        if player.state == 'hit' and not player.is_dead: # Check is_dead also
             set_player_state(player, 'idle' if player.on_ground else 'fall')


def apply_player_movement_and_physics(player):
    # Determine if gravity should be applied
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # If actively moving up wall
        player.is_dashing or # Dashing often ignores gravity
        player.is_frozen or # Frozen players don't move
        player.is_defrosting or # Defrosting players might be static
        (player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground) # Petrified on ground
    )

    # Set vertical acceleration (gravity)
    # Ladders manage their own vertical movement, so gravity is off.
    # Petrified on ground also means no gravity.
    if player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground:
        player.acc.setY(0.0)
    elif not player.on_ladder: # Ladders handle their own vertical movement/acceleration
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))


    # Apply gravity to vertical velocity if applicable
    if should_apply_gravity:
        player.vel.setY(player.vel.y() + player.acc.y()) # acc.y is gravity

    # Horizontal acceleration based on player intent (set by input handler)
    # Player.acc.x is set by the input handler based on is_trying_to_move_left/right
    # Modify base acceleration and speed limits based on status effects
    base_player_accel = C.PLAYER_ACCEL
    base_player_run_speed_limit = C.PLAYER_RUN_SPEED_LIMIT

    if player.is_aflame:
        base_player_accel *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_AFLAME_SPEED_MULTIPLIER', 1.0)
    elif player.is_deflaming:
        base_player_accel *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_DEFLAME_SPEED_MULTIPLIER', 1.0)
    
    # Horizontal velocity logic
    if player.is_rolling:
        # Allow some air control or directional influence during roll
        roll_control_accel_magnitude = base_player_accel * C.PLAYER_ROLL_CONTROL_ACCEL_FACTOR
        nudge_accel_x = 0.0
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            nudge_accel_x = roll_control_accel_magnitude

        player.vel.setX(player.vel.x() + nudge_accel_x) # Apply nudge

        # Cap roll speed but also ensure a minimum speed if rolling in current facing direction
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15 # Allow slight overshoot
        min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4  # Maintain some momentum
        current_vel_x = player.vel.x()
        if current_vel_x > 0: # Moving right
            current_vel_x = min(current_vel_x, max_roll_speed_cap)
            if player.facing_right: current_vel_x = max(current_vel_x, min_roll_speed_cap) # Min speed if rolling with facing
        elif current_vel_x < 0: # Moving left
            current_vel_x = max(current_vel_x, -max_roll_speed_cap)
            if not player.facing_right: current_vel_x = min(current_vel_x, -min_roll_speed_cap) # Min speed if rolling with facing
        player.vel.setX(current_vel_x)

        # Apply slight friction if no directional input during roll
        if nudge_accel_x == 0 and abs(player.vel.x()) > 0.1:
             player.vel.setX(player.vel.x() * 0.99) # Slight decay
             if abs(player.vel.x()) < 0.5: player.vel.setX(0.0) # Stop if very slow
    else: # Not rolling - standard horizontal physics
        # Determine if horizontal physics should apply
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or
            (player.state == 'wall_climb' and player.vel.y() <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # If actively climbing
            player.is_frozen or player.is_defrosting or
            (player.is_petrified and not getattr(player, 'is_stone_smashed', False)) # Petrified players don't respond to horizontal input
        )

        if should_apply_horizontal_physics:
            # Apply player's intended acceleration (from input handler)
            actual_accel_to_apply = player.acc.x() # acc.x is set by input based on intent
            if player.is_aflame: actual_accel_to_apply *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: actual_accel_to_apply *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)

            player.vel.setX(player.vel.x() + actual_accel_to_apply)

            # Apply friction
            friction_coeff = 0.0
            if player.on_ground and player.acc.x() == 0 and not player.is_sliding and player.state != 'slide': # No input, on ground
                friction_coeff = C.PLAYER_FRICTION
            elif not player.on_ground and not player.is_attacking and \
                 player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']: # Air friction (less)
                friction_coeff = C.PLAYER_FRICTION * 0.2 # Less air friction
            elif player.is_sliding or player.state == 'slide': # Sliding friction
                friction_coeff = C.PLAYER_FRICTION * 0.7

            if friction_coeff != 0: # Apply friction if calculated
                 friction_force = player.vel.x() * friction_coeff
                 if abs(player.vel.x()) > 0.1: player.vel.setX(player.vel.x() + friction_force)
                 else: player.vel.setX(0.0) # Stop if very slow

                 # If sliding and slowed down enough, transition out of slide
                 if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                     if slide_end_key: set_player_state(player, slide_end_key)
                     else: set_player_state(player, 'crouch' if player.is_crouching else 'idle')

            # Clamp horizontal speed if not dashing, rolling, or sliding
            current_h_speed_limit = base_player_run_speed_limit
            if player.is_crouching and player.state == 'crouch_walk': current_h_speed_limit *= 0.6
            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))
        elif player.is_frozen or player.is_defrosting or \
             (player.is_petrified and not getattr(player, 'is_stone_smashed', False)):
            # Ensure no horizontal movement if frozen/petrified
            player.vel.setX(0.0); player.acc.setX(0.0)


    # Clamp vertical speed (terminal velocity)
    # Apply only if not on ladder (ladder climbing controls its own Y velocity)
    if player.vel.y() > 0 and not player.on_ladder: # Falling
        player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))


def update_player_core_logic(player, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    if not player._valid_init or not player.alive(): return # Player is not active

    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_START")

    # Handle dead player physics (simplified fall, no input/complex states)
    if player.is_dead and not player.is_petrified: # Normal death
        if player.alive() and not player.death_animation_finished: # Still "alive" for animation purposes
            # Apply gravity if not on ground
            if not player.on_ground:
                player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
                player.vel.setY(player.vel.y() + player.acc.y())
                player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                # Apply vertical movement (dt_sec scaling if vel is per second)
                player.pos.setY(player.pos.y() + player.vel.y()) # Assuming vel is per-frame for simplicity here
                if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()

                player.on_ground = False # Assume not on ground until collision
                check_player_platform_collisions(player, 'y', platforms_list) # Check for landing
                # Update pos from rect after collision
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
        if hasattr(player, 'animate'): player.animate() # Continue death animation
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END", "Player is dead (normal)")
        return

    if player.is_petrified: # Petrified or Smashed
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_PETRIFIED_START", f"Smashed: {player.is_stone_smashed}, OnGround: {player.on_ground}")
        if not player.is_stone_smashed and not player.on_ground: # Petrified but not smashed, and in air
            # Apply gravity
            player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
            player.vel.setY(player.vel.y() + player.acc.y())
            player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
            player.pos.setY(player.pos.y() + player.vel.y()) # Assuming per-frame velocity
            if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
            check_player_platform_collisions(player, 'y', platforms_list) # Check for landing
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos
        elif player.is_stone_smashed: # Smashed stone does not move
            player.vel = QPointF(0,0)
            player.acc = QPointF(0,0)

        if hasattr(player, 'animate'): player.animate() # Animate petrified/smashed state
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END", "Player is petrified/smashed")
        return

    # --- Active Player Logic ---
    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list) # Updates player.can_grab_ladder
    if player.on_ladder and not player.can_grab_ladder: # If moved off a ladder
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player) # Updates velocities based on accel and states

    # Reset collision states before checks
    player.touching_wall = 0 # Reset per frame, will be set by X collision if applicable
    player.on_ground = False # Reset before Y collision checks

    # --- Horizontal movement and collision ---
    # dt_sec scaling is applied if velocities are per second.
    # If velocities are already per-frame, simple addition is fine.
    # Assuming velocities are per-frame based on how gravity/accel are usually added.
    player.pos.setX(player.pos.x() + player.vel.x()) # Apply horizontal velocity
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_MOVE_APPLIED")
    check_player_platform_collisions(player, 'x', platforms_list)
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_PLAT_COLL_DONE")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) # Re-sync pos from rect after char collision
        check_player_platform_collisions(player, 'x', platforms_list) # Re-check platform collision
        if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "X_PLAT_RECHECK")

    # --- Vertical movement and collision ---
    player.pos.setY(player.pos.y() + player.vel.y()) # Apply vertical velocity
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_MOVE_APPLIED")
    check_player_platform_collisions(player, 'y', platforms_list) # This sets player.on_ground
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_PLAT_COLL_DONE")

    if not collided_horizontally_char: # Only check Y char collision if no X char collision resolved it
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Re-sync
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check
            if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "Y_PLAT_RECHECK")

    # Final position sync (anchor to midbottom of the rect)
    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "FINAL_POS_SYNC")

    check_player_hazard_collisions(player, hazards_list) # Handle hazard interactions

    # Player attacks (if any)
    if player.alive() and not player.is_dead and player.is_attacking: # Ensure player is in a state to attack
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    if hasattr(player, 'animate'): player.animate() # Update animation
    if ENABLE_DETAILED_PHYSICS_LOGS: log_player_physics(player, "UPDATE_END")