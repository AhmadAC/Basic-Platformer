#################### START OF FILE: player_movement_physics.py ####################

# player_movement_physics.py
# -*- coding: utf-8 -*-
"""
Handles core movement physics, state timers, and collision orchestration for the Player using PySide6 types.
"""
# version 2.0.7 (Refined logging and debug messages for clarity)

from typing import List, Any, Optional, TYPE_CHECKING
import time
from items import Chest
# PySide6 imports
from PySide6.QtCore import QPointF, QRectF

# Game imports
import constants as C
from statue import Statue # For type hinting
from player_collision_handler import (
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
from player_state_handler import set_player_state

# Logger import - import the module itself and specific flags/classes
import logger as app_logger 
from logger import ENABLE_DETAILED_PHYSICS_LOGS, RateLimiter 

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE


# --- File-specific Rate Limiter Setup ---
_physics_file_rate_limiter = RateLimiter(default_period_sec=1.0) # Log from this file at most once per second
_PHYSICS_FILE_LOG_KEY = "player_movement_physics_log_tick_v3" 

def _can_log_from_this_file_internal() -> bool:
    return _physics_file_rate_limiter.can_proceed(_PHYSICS_FILE_LOG_KEY, period_sec=1.0)

# --- Local Logging Wrappers for this File ---
def _file_debug(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): app_logger.debug(message, *args, **kwargs)
def _file_info(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): app_logger.info(message, *args, **kwargs)
def _file_warning(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): app_logger.warning(message, *args, **kwargs)
def _file_error(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): app_logger.error(message, *args, **kwargs)
def _file_critical(message: str, *args: Any, **kwargs: Any):
    if _can_log_from_this_file_internal(): app_logger.critical(message, *args, **kwargs)
def _file_log_player_physics(player: Any, message_tag: str, extra_info: Any = ""):
    # log_player_physics has its own global debug rate limiter via _shared_debug_rate_limiter
    # This file's _can_log_from_this_file_internal() adds an additional layer of throttling for physics logs from THIS file.
    if ENABLE_DETAILED_PHYSICS_LOGS and _can_log_from_this_file_internal():
        app_logger.log_player_physics(player, message_tag, extra_info)
# --- End of Local Logging Wrappers ---


_start_time_player_physics = time.monotonic()
def get_current_ticks() -> int: 
    return int((time.monotonic() - _start_time_player_physics) * 1000)


def manage_player_state_timers_and_cooldowns(player: 'PlayerClass_TYPE'): 
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


def apply_player_movement_and_physics(player: 'PlayerClass_TYPE'): 
    player_id_str = f"P{player.player_id}"
    
    should_apply_gravity = not (
        player.on_ladder or
        player.state == 'wall_hang' or
        player.is_dashing or
        player.is_frozen or
        player.is_defrosting or
        (player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground)
    )

    if player.is_petrified and not getattr(player, 'is_stone_smashed', False) and player.on_ground:
        player.acc.setY(0.0)
    elif not player.on_ladder: # Not on ladder OR not petrified on ground (or other conditions above met)
        player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))

    if should_apply_gravity:
        player.vel.setY(player.vel.y() + player.acc.y()) 

    # Determine base acceleration and speed limit, potentially modified by status effects
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
    else: # Not rolling
        should_apply_horizontal_physics = not (
            player.is_dashing or player.on_ladder or
            player.is_frozen or player.is_defrosting or
            (player.is_petrified and not getattr(player, 'is_stone_smashed', False))
        )

        if should_apply_horizontal_physics:
            actual_accel_to_apply_x = player.acc.x() # player.acc.x is set by input_handler based on intent
            player.vel.setX(player.vel.x() + actual_accel_to_apply_x) 

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
                 else:
                     player.vel.setX(0.0)

                 if abs(player.vel.x()) < 0.5 and (player.is_sliding or player.state == 'slide'):
                     player.is_sliding = False
                     slide_end_key = 'slide_trans_end' if player.animations and 'slide_trans_end' in player.animations else None
                     if slide_end_key: set_player_state(player, slide_end_key)
                     else: set_player_state(player, 'crouch' if player.is_crouching else 'idle')

            current_h_speed_limit = base_player_run_speed_limit
            if player.is_crouching and player.state == 'crouch_walk':
                current_h_speed_limit *= 0.6
            
            if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
                player.vel.setX(max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x())))

        elif player.is_frozen or player.is_defrosting or \
             (player.is_petrified and not getattr(player, 'is_stone_smashed', False)):
            player.vel.setX(0.0); player.acc.setX(0.0) 

    if player.vel.y() > 0 and not player.on_ladder: 
        player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))


def update_player_core_logic(player: 'PlayerClass_TYPE', dt_sec: float, platforms_list: List[Any], ladders_list: List[Any],
                             hazards_list: List[Any], other_players_list: List[Any], enemies_list: List[Any]):
    player_id_str = f"P{player.player_id}"
    if not player._valid_init or not player.alive():
        _file_debug(f"{player_id_str} CoreLogic: Update skipped. _valid_init={player._valid_init}, alive={player.alive()}")
        return

    _file_log_player_physics(player, "UPDATE_START")

    if player.is_dead and not player.is_petrified: 
        if player.alive() and not player.death_animation_finished: # Still "alive" for animation
            if not player.on_ground: # Apply gravity to dead body
                original_acc_y_dead = player.acc.y() 
                player.acc.setY(float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
                player.vel.setY(player.vel.y() + player.acc.y())
                player.vel.setY(min(player.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                # Use per-frame velocity for position update (dt_sec * FPS is already baked in by how vel is used)
                player.pos.setY(player.pos.y() + player.vel.y()) 
                if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
                
                player.on_ground = False # Assume not on ground until check
                check_player_platform_collisions(player, 'y', platforms_list) # Minimal collision for falling body
                player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) # Sync pos from rect
                player.acc.setY(original_acc_y_dead) # Restore original acc.y if needed (though usually 0 for dead)
        
        if hasattr(player, 'animate'): player.animate()
        _file_log_player_physics(player, "UPDATE_END", "Player is dead (normal)")
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
        return

    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_list) 
    
    if player.on_ladder and not player.can_grab_ladder: # Fell off ladder
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')

    apply_player_movement_and_physics(player) 

    player.touching_wall = 0 
    player.on_ground = False # Reset before Y collision checks

    # --- Horizontal Movement and Collisions ---
    # Scale velocity by frame time (dt_sec * FPS_CONSTANT) to get per-frame displacement
    # Assuming velocity is units/second, displacement = vel * dt_sec
    # If velocity is units/frame (already scaled by FPS elsewhere), then displacement = vel
    # Your code uses vel * dt_sec * C.FPS, which suggests vel is in units "per physics tick at reference FPS"
    # If dt_sec is actual time slice, then vel * dt_sec is correct displacement.
    # Let's assume vel is units per "conceptual frame" if FPS is stable.
    # If dt_sec = 1/FPS, then vel * dt_sec * C.FPS = vel. This implies vel is "displacement per fixed update".
    # For now, proceeding with current logic: vel * dt_sec * C.FPS
    
    scaled_vel_x = player.vel.x() * dt_sec * C.FPS
    scaled_vel_y = player.vel.y() * dt_sec * C.FPS

    player.pos.setX(player.pos.x() + scaled_vel_x) 
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "X_MOVE_APPLIED")
    
    check_player_platform_collisions(player, 'x', platforms_list)
    _file_log_player_physics(player, "X_PLAT_COLL_DONE")

    all_other_char_sprites = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                             [e for e in enemies_list if e and e._valid_init and e.alive()] # Only consider alive enemies
    
    # Add Statues and Chest if they are physical obstacles
    for item in player.game_elements_ref_for_projectiles.get("collectible_list", []):
        if isinstance(item, Chest) and item.alive() and item.state == 'closed':
            all_other_char_sprites.append(item)
    for item in player.game_elements_ref_for_projectiles.get("statue_objects", []):
        if isinstance(item, Statue) and item.alive() and not item.is_smashed:
            all_other_char_sprites.append(item)


    collided_horizontally_char = check_player_character_collisions(player, 'x', all_other_char_sprites)
    if collided_horizontally_char:
        _file_log_player_physics(player, "X_CHAR_COLL_POST")
        player.pos.setX(player.rect.center().x()) 
        check_player_platform_collisions(player, 'x', platforms_list) # Re-check platforms after char push
        _file_log_player_physics(player, "X_PLAT_RECHECK_POST_CHAR")

    # --- Vertical Movement and Collisions ---
    player.pos.setY(player.pos.y() + scaled_vel_y) 
    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    _file_log_player_physics(player, "Y_MOVE_APPLIED")

    check_player_platform_collisions(player, 'y', platforms_list) 
    _file_log_player_physics(player, "Y_PLAT_COLL_DONE")

    if not collided_horizontally_char: # Only check vertical char collision if no horizontal occurred this frame
        collided_vertically_char = check_player_character_collisions(player, 'y', all_other_char_sprites)
        if collided_vertically_char:
            _file_log_player_physics(player, "Y_CHAR_COLL_POST")
            player.pos = QPointF(player.rect.center().x(), player.rect.bottom()) 
            check_player_platform_collisions(player, 'y', platforms_list) # Re-check platforms after char push
            _file_log_player_physics(player, "Y_PLAT_RECHECK_POST_CHAR")

    # Final position sync from rect after all resolutions for this axis
    player.pos = QPointF(player.rect.center().x(), player.rect.bottom())
    _file_log_player_physics(player, "FINAL_POS_SYNC")

    check_player_hazard_collisions(player, hazards_list)

    # Player Attack Collision (after all movement resolved for this frame)
    if player.alive() and not player.is_dead and player.is_attacking:
        targets_for_player_attack = [p for p in other_players_list if p and p._valid_init and p.alive() and p is not player] + \
                                    [e for e in enemies_list if e and e._valid_init and e.alive()]
        statues_list_for_attack = player.game_elements_ref_for_projectiles.get("statue_objects", []) if player.game_elements_ref_for_projectiles else []
        targets_for_player_attack.extend([s for s in statues_list_for_attack if isinstance(s, Statue) and s.alive()])

        if hasattr(player, 'check_attack_collisions'):
            player.check_attack_collisions(targets_for_player_attack)

    if hasattr(player, 'animate'): player.animate()
    _file_log_player_physics(player, "UPDATE_END")

#################### END OF FILE: player_movement_physics.py ####################