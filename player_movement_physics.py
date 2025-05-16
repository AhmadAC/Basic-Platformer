# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.2 (Refined uncrouch logic in core update)
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
        set_player_state(player, 'idle' if player.on_ground else 'fall')

    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide': # If still in the looping slide state
            player.is_sliding = False # Ensure flag is false
            slide_end_anim_key = 'slide_trans_end' if 'slide_trans_end' in player.animations else None
            if slide_end_anim_key:
                set_player_state(player, slide_end_anim_key)
            else: # No transition out animation, decide based on crouch key
                # The player.is_crouching flag might still be true if they slid into crouch.
                # Or it might be false if slide was a distinct action.
                # Check if they are still holding the crouch key to determine next state.
                if player.is_holding_crouch_ability_key:
                    set_player_state(player, 'crouch')
                else:
                    player.is_crouching = False # Ensure this is false if not holding key
                    set_player_state(player, 'idle')

    # Cooldown for taking hits (invincibility period ending)
    # This doesn't change the 'hit' state itself, just allows taking damage again.
    # The 'hit' state (stun animation) duration is typically shorter than hit_cooldown.
    if player.is_taking_hit and current_time_ms - player.hit_timer > player.hit_cooldown:
        # If the player is still in the 'hit' state (meaning the stun animation hasn't finished
        # and transitioned them out via advance_frame_and_handle_state_transitions),
        # this just means their invincibility window is over.
        # The actual state transition out of 'hit' is handled by the animation finishing.
        # However, if they were hit, and hit_cooldown expires, but they weren't in 'hit' state (e.g. got hit mid-dash),
        # then we can clear is_taking_hit.
        if player.state != 'hit': # If not actively in hit animation anymore
             player.is_taking_hit = False
        # If player.state IS 'hit', then advance_frame... will set is_taking_hit=False when anim ends.


def apply_player_movement_and_physics(player):
    """Applies physics like gravity, friction, and velocity limits to the player."""
    # --- Apply Gravity ---
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or # Allow slight deviation
        player.is_dashing # Dash usually overrides gravity
    )
    if should_apply_gravity:
        player.vel.y += player.acc.y # player.acc.y is usually C.PLAYER_GRAVITY

    # --- Horizontal Physics (Acceleration, Friction, Speed Limit) ---
    should_apply_horizontal_physics = not (
        player.is_dashing or # Dash has its own speed
        player.is_rolling or # Roll has its own speed
        player.on_ladder or  # No horizontal physics on ladder
        (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) # Climbing wall
    )

    if should_apply_horizontal_physics:
        player.vel.x += player.acc.x # Apply acceleration from input

        # Apply Friction
        friction_coeff = 0
        if player.on_ground and player.acc.x == 0 and not player.is_sliding and player.state != 'slide':
            friction_coeff = C.PLAYER_FRICTION # Ground friction when no input
        elif not player.on_ground and not player.is_attacking and \
             player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']:
            friction_coeff = C.PLAYER_FRICTION * 0.2 # Air friction (less)
        elif player.is_sliding or player.state == 'slide':
            friction_coeff = C.PLAYER_FRICTION * 0.7 # Sliding friction (higher)

        if friction_coeff != 0:
             friction_force = player.vel.x * friction_coeff
             if abs(player.vel.x) > 0.1: # Only apply if moving noticeably
                 player.vel.x += friction_force
             else:
                 player.vel.x = 0 # Stop if very slow

             # If sliding friction stops the player
             if abs(player.vel.x) < 0.5 and (player.is_sliding or player.state == 'slide'):
                 player.is_sliding = False
                 slide_end_key = 'slide_trans_end' if 'slide_trans_end' in player.animations else None
                 if slide_end_key:
                     set_player_state(player, slide_end_key)
                 else:
                     # Check if still holding crouch to determine if player should remain crouched
                     if player.is_holding_crouch_ability_key:
                         player.is_crouching = True # Explicitly set if was sliding
                         set_player_state(player, 'crouch')
                     else:
                         player.is_crouching = False
                         set_player_state(player, 'idle')

        # Speed Limiting (except for dash, roll, slide which have their own speeds)
        current_h_speed_limit = C.PLAYER_RUN_SPEED_LIMIT
        if player.is_crouching and player.state == 'crouch_walk':
            current_h_speed_limit *= 0.6 # Slower when crouch-walking

        if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
            player.vel.x = max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x))

    # --- Terminal Velocity (Vertical) ---
    if player.vel.y > 0 and not player.on_ladder: # Only apply if moving down and not on ladder
        player.vel.y = min(player.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))


def update_player_core_logic(player, dt_sec, platforms_group, ladders_group, hazards_group,
                             other_players_list, enemies_list):
    """
    Main update function for the player. Processes state timers, physics,
    collisions, and animations.
    """
    if not player._valid_init: return
    log_player_physics(player, "UPDATE_START")

    if player.is_dead:
        if player.alive() and hasattr(player, 'animate'): # Check if sprite is still in groups
            if not player.death_animation_finished:
                # Apply minimal physics for falling while dead
                if not player.on_ground:
                    player.vel.y += player.acc.y # player.acc.y should be gravity
                    player.vel.y = min(player.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))
                    player.pos.y += player.vel.y
                    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
                    # Simplified ground check for dead player
                    player.on_ground = False
                    for platform_sprite in pygame.sprite.spritecollide(player, platforms_group, False):
                        if player.vel.y > 0 and player.rect.bottom > platform_sprite.rect.top and \
                           (player.pos.y - player.vel.y) <= platform_sprite.rect.top + 1: # Was above or at same level
                            player.rect.bottom = platform_sprite.rect.top
                            player.on_ground = True; player.vel.y = 0; player.acc.y = 0 # Stop falling
                            player.pos = pygame.math.Vector2(player.rect.midbottom); break # Sync pos
            update_player_animation(player) # Continue animating death
        log_player_physics(player, "UPDATE_END", "Player is dead")
        debug("------------------------------") # Use the imported debug
        return

    # --- Update State Timers and Cooldowns (Dash, Roll, Slide, Hit Stun) ---
    manage_player_state_timers_and_cooldowns(player)

    # --- Handle Uncrouching Logic ---
    # This happens before applying movement physics for the frame.
    # player.is_holding_crouch_ability_key is updated by the input handler.
    if player.is_crouching and not player.is_holding_crouch_ability_key:
        if player.can_stand_up(platforms_group): # Check for overhead clearance
            player.is_crouching = False
            # Determine next state based on current movement intention
            if player.is_trying_to_move_left or player.is_trying_to_move_right:
                set_player_state(player, 'run')
            else:
                set_player_state(player, 'idle')
            # The animation handler will take care of updating the rect height via set_player_state -> update_player_animation
        else:
            # Cannot stand up, player remains crouching.
            # Ensure the state reflects crouching if it somehow got changed (e.g. by an attack ending).
            if player.state not in ['crouch', 'crouch_walk', 'crouch_attack', 'crouch_trans']:
                is_moving = player.is_trying_to_move_left or player.is_trying_to_move_right
                set_player_state(player, 'crouch_walk' if is_moving else 'crouch')

    # --- Ladder Interaction Check ---
    check_player_ladder_collisions(player, ladders_group) # Updates player.can_grab_ladder
    if player.on_ladder and not player.can_grab_ladder: # Fell off or moved away from ladder
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')


    # --- Apply Movement Physics (Gravity, Friction, Input Acceleration, Speed Limits) ---
    apply_player_movement_and_physics(player)


    # --- Collision Detection and Resolution ---
    player.touching_wall = 0 # Reset wall touch status each frame before horizontal check
    player.on_ground = False # Reset ground status each frame before vertical check

    # --- HORIZONTAL MOVEMENT & COLLISION ---
    player.pos.x += player.vel.x
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y)) # Update rect to new potential X position
    log_player_physics(player, "X_MOVE_APPLIED")

    check_player_platform_collisions(player, 'x', platforms_group) # Snaps rect, updates vel.x, pos.x, touching_wall
    log_player_physics(player, "X_PLAT_COLL_DONE")

    # Combine other players and enemies for character collision checks
    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()]
    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)

    if collided_horizontally_char: # If character collision pushed player
        log_player_physics(player, "X_CHAR_COLL_POST")
        player.rect.midbottom = (round(player.pos.x), round(player.pos.y)) # Update rect from potentially new pos.x
        check_player_platform_collisions(player, 'x', platforms_group) # Re-check platforms with new pos
        log_player_physics(player, "X_PLAT_RECHECK")


    # --- VERTICAL MOVEMENT & COLLISION ---
    player.pos.y += player.vel.y
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y)) # Update rect to new potential Y position
    log_player_physics(player, "Y_MOVE_APPLIED")

    check_player_platform_collisions(player, 'y', platforms_group) # Snaps rect, updates vel.y, pos.y, on_ground
    log_player_physics(player, "Y_PLAT_COLL_DONE")

    collided_vertically_char = False
    # Only check vertical character collision if no horizontal one occurred this frame
    # (to avoid complex simultaneous collision resolution logic for now)
    if not collided_horizontally_char:
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char: # If character collision pushed player
            log_player_physics(player, "Y_CHAR_COLL_POST")
            player.rect.midbottom = (round(player.pos.x), round(player.pos.y)) # Update rect from potentially new pos.y
            check_player_platform_collisions(player, 'y', platforms_group) # Re-check platforms
            log_player_physics(player, "Y_PLAT_RECHECK")

    # --- Final Position Sync ---
    # After all X and Y collisions, player.rect is authoritatively set.
    # Sync player.pos (the float vector) to match the rect's midbottom.
    # This ensures player.pos accurately reflects the true integer pixel position's anchor.
    player.pos = pygame.math.Vector2(player.rect.midbottom)
    log_player_physics(player, "FINAL_POS_SYNC")

    # --- Hazard Collision ---
    check_player_hazard_collisions(player, hazards_group) # Can change health, velocity, state

    # --- Player Attack Collision (if player is attacking) ---
    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        player.check_attack_collisions(targets_for_player_attack) # From player_combat_handler

    # --- Update Animation ---
    # This should be called last in the update sequence, after all physics and state changes,
    # so the animation reflects the final state and position for this frame.
    update_player_animation(player)
    log_player_physics(player, "UPDATE_END")
    if ENABLE_DETAILED_PHYSICS_LOGS: debug("------------------------------") # Separator for logs