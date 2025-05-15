# player_movement_physics.py
# -*- coding: utf-8 -*-
import pygame
import constants as C
from player_collision_handler import ( 
    check_player_platform_collisions,
    check_player_ladder_collisions,
    check_player_character_collisions,
    check_player_hazard_collisions
)
from player_animation_handler import update_player_animation
from player_state_handler import set_player_state 

# Import the shared logging flag and helper function from logger.py
from logger import info, debug, warning, error, critical, ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics 


def manage_player_state_timers_and_cooldowns(player):
    current_time_ms = pygame.time.get_ticks()
    if player.is_dashing and current_time_ms - player.dash_timer > player.dash_duration:
        player.is_dashing = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')
    if player.is_rolling and current_time_ms - player.roll_timer > player.roll_duration:
        player.is_rolling = False
        set_player_state(player, 'idle' if player.on_ground else 'fall')
    if player.is_sliding and current_time_ms - player.slide_timer > player.slide_duration:
        if player.state == 'slide':
            player.is_sliding = False
            slide_end_anim_key = 'slide_trans_end' if 'slide_trans_end' in player.animations else None
            if slide_end_anim_key: set_player_state(player, slide_end_anim_key)
            else: set_player_state(player, 'crouch' if player.is_holding_crouch_ability_key else 'idle')
    if player.is_taking_hit and current_time_ms - player.hit_timer > player.hit_cooldown:
        if player.state == 'hit': player.is_taking_hit = False
        else: player.is_taking_hit = False

def apply_player_movement_and_physics(player):
    should_apply_gravity = not (
        player.on_ladder or player.state == 'wall_hang' or
        (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1) or
        player.is_dashing
    )
    if should_apply_gravity: player.vel.y += player.acc.y

    should_apply_horizontal_physics = not (
        player.is_dashing or player.is_rolling or player.on_ladder or
        (player.state == 'wall_climb' and player.vel.y <= C.PLAYER_WALL_CLIMB_SPEED + 0.1)
    )
    if should_apply_horizontal_physics:
        player.vel.x += player.acc.x
        friction_coeff = 0
        if player.on_ground and player.acc.x == 0 and not player.is_sliding and player.state != 'slide': friction_coeff = C.PLAYER_FRICTION
        elif not player.on_ground and not player.is_attacking and player.state not in ['wall_slide','wall_hang','wall_climb','wall_climb_nm']: friction_coeff = C.PLAYER_FRICTION * 0.2
        elif player.is_sliding or player.state == 'slide': friction_coeff = C.PLAYER_FRICTION * 0.7
        if friction_coeff != 0:
             friction_force = player.vel.x * friction_coeff
             if abs(player.vel.x) > 0.1: player.vel.x += friction_force
             else: player.vel.x = 0
             if abs(player.vel.x) < 0.5 and (player.is_sliding or player.state == 'slide'):
                 player.is_sliding = False
                 slide_end_key = 'slide_trans_end' if 'slide_trans_end' in player.animations and player.animations['slide_trans_end'] else None
                 if slide_end_key: set_player_state(player, slide_end_key)
                 else:
                     player.is_crouching = player.is_holding_crouch_ability_key
                     set_player_state(player, 'crouch' if player.is_crouching else 'idle')
        current_h_speed_limit = C.PLAYER_RUN_SPEED_LIMIT
        if player.is_crouching and player.state == 'crouch_walk': current_h_speed_limit *= 0.6
        if not player.is_dashing and not player.is_rolling and not player.is_sliding and player.state != 'slide':
            player.vel.x = max(-current_h_speed_limit, min(current_h_speed_limit, player.vel.x))
    if player.vel.y > 0 and not player.on_ladder:
        player.vel.y = min(player.vel.y, getattr(C, 'TERMINAL_VELOCITY_Y', 18))

def update_player_core_logic(player, dt_sec, platforms_group, ladders_group, hazards_group,
                             other_players_list, enemies_list):
    if not player._valid_init: return
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
        debug("------------------------------") # Use the imported debug
        return

    manage_player_state_timers_and_cooldowns(player)
    check_player_ladder_collisions(player, ladders_group)
    if player.on_ladder and not player.can_grab_ladder:
        player.on_ladder = False
        set_player_state(player, 'fall' if not player.on_ground else 'idle')
    apply_player_movement_and_physics(player)

    player.touching_wall = 0
    player.on_ground = False

    # --- HORIZONTAL MOVEMENT & COLLISION ---
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
        player.rect.midbottom = (round(player.pos.x), round(player.pos.y)) 
        check_player_platform_collisions(player, 'x', platforms_group) 
        log_player_physics(player, "X_PLAT_RECHECK")

    # --- VERTICAL MOVEMENT & COLLISION ---
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
            player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
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
    debug("------------------------------")