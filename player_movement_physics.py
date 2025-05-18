# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.5 (Add speed multipliers for aflame/deflame player)
Handles the core movement physics and state timer updates for the Player.
This includes applying acceleration, velocity, friction, gravity, managing
durations for states, and orchestrating collision checks and responses.
Also handles uncrouching logic with safety checks.
"""
import pygame
import constants as C
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
from player_animation_handler import update_player_animation # For updating animation after state changes
from player_state_handler import set_player_state # For explicit state transitions

# Import the shared logging flag and helper function from logger.py
from logger import info, debug, warning, error, critical, ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics


def manage_player_state_timers_and_cooldowns(player):
    """
    Manages timers for player states like dashing, rolling, sliding, and hit stun.
    Transitions player out of these states when timers expire.
    """
    current_time_ms = pygame.time.get_ticks()

    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        player.is_rolling = False
        # player.vel.x = 0 # Option: kill horizontal speed after roll, or let friction handle it.
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide':
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else:
                if player.is_crouching: # Check the toggled state
                    set_player_state(player, 'crouch')
                else:
                    set_player_state(player, 'idle')


    if player.is_taking_hit and current_time_ms - player.hit_timer > player.hit_cooldown:
        if player.state != 'hit': # Only reset if not already in 'hit' state due to new hit
             player.is_taking_hit = False


def apply_player_movement_and_physics(player):
    """Applies physics like gravity, friction, and velocity limits to the player."""
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or
        player.is_dashing or
        player.is_frozen or # MODIFIED: Frozen players ignore gravity
        player.is_defrosting
    )
    if should_apply_gravity:
        player.vel.y += player.acc.y

    # --- Horizontal Movement and Physics ---
    # MODIFIED: Determine base acceleration and speed limit, then apply multipliers
    base_player_accel = C.PLAYER_ACCEL
    base_player_run_speed_limit = C.PLAYER_RUN_SPEED_LIMIT

    if player.is_aflame:
        # Define PLAYER_AFLAME_ACCEL_MULTIPLIER and PLAYER_AFLAME_SPEED_MULTIPLIER in constants.py
        # e.g., PLAYER_AFLAME_ACCEL_MULTIPLIER = 1.2
        #       PLAYER_AFLAME_SPEED_MULTIPLIER = 1.1
        base_player_accel *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_AFLAME_SPEED_MULTIPLIER', 1.0)
    elif player.is_deflaming:
        # Define PLAYER_DEFLAME_ACCEL_MULTIPLIER and PLAYER_DEFLAME_SPEED_MULTIPLIER in constants.py
        # e.g., PLAYER_DEFLAME_ACCEL_MULTIPLIER = 1.1
        #       PLAYER_DEFLAME_SPEED_MULTIPLIER = 1.05
        base_player_accel *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
        base_player_run_speed_limit *= getattr(C, 'PLAYER_DEFLAME_SPEED_MULTIPLIER', 1.0)


    if player.is_rolling:
        roll_control_accel_magnitude = base_player_accel * C.PLAYER_ROLL_CONTROL_ACCEL_FACTOR # Use modified base_player_accel
        nudge_accel_x = 0

        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            nudge_accel_x = -roll_control_accel_magnitude
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            nudge_accel_x = roll_control_accel_magnitude

        player.vel.x += nudge_accel_x
        max_roll_speed_cap = C.PLAYER_ROLL_SPEED * 1.15 
        min_roll_speed_cap = C.PLAYER_ROLL_SPEED * 0.4

        if player.vel.x > 0:
            player.vel.x = min(player.vel.x, max_roll_speed_cap)
            if player.facing_right: player.vel.x = max(player.vel.x, min_roll_speed_cap)
        elif player.vel.x < 0:
            player.vel.x = max(player.vel.x, -max_roll_speed_cap)
            if not player.facing_right: player.vel.x = min(player.vel.x, -min_roll_speed_cap)

        if nudge_accel_x == 0 and abs(player.vel.x) > 0.1:
             player.vel.x *= 0.99
             if abs(player.vel.x) < 0.5: player.vel.x = 0
    else: # Not rolling
        should_apply_horizontal_physics = not (
            player.is_dashing or
            player.on_ladder or
            (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or
            player.is_frozen or # MODIFIED: Frozen players don't move
            player.is_defrosting
        )
        if should_apply_horizontal_physics:
            # Apply acceleration based on input (player.acc.x should be set by input handler using base_player_accel logic)
            # The input handler will set player.acc.x using the non-multiplied C.PLAYER_ACCEL.
            # We adjust it here if on fire.
            actual_accel_to_apply = player.acc.x
            if player.is_aflame:
                actual_accel_to_apply *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming:
                actual_accel_to_apply *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)

            player.vel.x += actual_accel_to_apply


            friction_coeff = 0
            if player.on_ground and player.acc.x == 0 and not player.is_sliding and player.state != 'slide':
                friction_coeff = C.PLAYER_FRICTION
            elif not player.on_ground and not player.is_attacking and \
                 player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']:
                friction_coeff = C.PLAYER_FRICTION * 0.2
            elif player.is_sliding or player.state == 'slide':
                friction_coeff = C.PLAYER_FRICTION * 0.7

            if friction_coeff != 0:
                 friction_force = player.vel.x * friction_coeff
                 if abs(player.vel.x) > 0.1:
                     player.vel.x += friction_force
                 else:
                     player.vel.x = 0

                 if abs(player.vel.x) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if 'slide_trans_end' in player.animations else None
                     if slide_end_key:
                         set_player_state(player, slide_end_key)
                     else:
                         if player.is_crouching:
                             set_player_state(player, 'crouch')
                         else:
                             set_player_state(player, 'idle')

            current_h_speed_limit = base_player_run_speed_limit # Use the (potentially fire-modified) speed limit
            if player.is_crouching and player.state == 'crouch_walk':
                current_h_speed_limit *= 0.6

            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                player.vel.x = max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x))
        elif player.is_frozen or player.is_defrosting: # MODIFIED: Ensure no movement if frozen/defrosting
            player.vel.x = 0
            player.acc.x = 0


    # --- Vertical Velocity Cap (Terminal Velocity) ---
    if player.vel.y > 0 and not player.on_ladder:
        player.vel.y = min(player.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))


def update_player_core_logic(player, dt_sec, platforms_group, ladders_group, hazards_group,
                             other_players_list, enemies_list):
    """
    Main update function for the player. Processes state timers, physics,
    collisions, and animations.
    """
    if not player._valid_init: return

    if getattr(player, 'is_petrified', False):
        log_player_physics(player, "UPDATE_BLOCKED", "Player is petrified/smashed")
        return

    log_player_physics(player, "UPDATE_START")

    if player.is_dead:
        if player.alive() and hasattr(player, 'animate'):
            if not player.death_animation_finished:
                if not player.on_ground:
                    player.vel.y += player.acc.y
                    player.vel.y = min(player.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
                    player.pos.y += player.vel.y
                    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
                    player.on_ground = False
                    for platform_sprite in pygame.sprite.spritecollide(player, platforms_group, False):
                        if player.vel.y > 0 and player.rect.bottom > platform_sprite.rect.top and \
                           (player.pos.y - player.vel.y) <= platform_sprite.rect.top + 1:
                            player.rect.bottom = platform_sprite.rect.top
                            player.on_ground = True; player.vel.y = 0; player.acc.y = 0
                            player.pos = pygame.math.Vector2(player.rect.midbottom); break
            update_player_animation(player)
        log_player_physics(player, "UPDATE_END", "Player is dead")
        return

    manage_player_state_timers_and_cooldowns(player)

    check_player_ladder_collisions(player, ladders_group)
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player)

    player.touching_wall = 0
    player.on_ground = False

    player.pos.x += player.vel.x
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
    log_player_physics(player, "X_MOVE_APPLIED")

    check_player_platform_collisions(player, 'x', platforms_group)
    log_player_physics(player, "X_PLAT_COLL_DONE")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)

    if collided_horizontally_char:
        log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.x = player.rect.centerx
        player.pos.y = player.rect.bottom
        check_player_platform_collisions(player, 'x', platforms_group)
        log_player_physics(player, "X_PLAT_RECHECK")

    player.pos.y += player.vel.y
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
    log_player_physics(player, "Y_MOVE_APPLIED")

    check_player_platform_collisions(player, 'y', platforms_group)
    log_player_physics(player, "Y_PLAT_COLL_DONE")

    collided_vertically_char = False
    if not collided_horizontally_char:
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos.x = player.rect.centerx
            player.pos.y = player.rect.bottom
            check_player_platform_collisions(player, 'y', platforms_group)
            log_player_physics(player, "Y_PLAT_RECHECK")

    player.pos = pygame.math.Vector2(player.rect.midbottom)
    log_player_physics(player, "FINAL_POS_SYNC")

    check_player_hazard_collisions(player, hazards_group)

    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        player.check_attack_collisions(targets_for_player_attack)

    update_player_animation(player)
    log_player_physics(player, "UPDATE_END")
