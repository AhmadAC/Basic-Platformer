# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution.
Logs detailed physics information if enabled.
Players can be set aflame by enemies that are aflame.
"""
import pygame
import constants as C
from tiles import Lava
from enemy import Enemy # For isinstance checks

# Import the shared logging flag and helper function from logger.py
from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics

def check_player_platform_collisions(player, direction: str, platforms_group: pygame.sprite.Group):
    """
    Handles collisions between the player and solid platforms.
    Resolves collisions by adjusting player position and velocity.
    Updates `player.on_ground` and `player.touching_wall` flags.

    Args:
        player (Player): The player instance.
        direction (str): The axis of movement being checked ('x' or 'y').
        platforms_group (pygame.sprite.Group): Group of platform sprites.
    """
    if not player._valid_init: return

    rect_after_current_axis_move = player.rect.copy()
    collided_with_wall_on_side = 0  

    colliding_platforms = pygame.sprite.spritecollide(player, platforms_group, False)

    for platform_sprite in colliding_platforms:
        current_player_rect_for_log = player.rect.copy()
        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}",
                           (current_player_rect_for_log, platform_sprite.rect, platform_sprite.platform_type))

        if direction == 'x':
            if player.vel.x > 0:  
                if player.rect.right > platform_sprite.rect.left and \
                   rect_after_current_axis_move.left < platform_sprite.rect.left:
                    player.rect.right = platform_sprite.rect.left
                    player.vel.x = 0
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = 1
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_R",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))
            elif player.vel.x < 0:  
                if player.rect.left < platform_sprite.rect.right and \
                   rect_after_current_axis_move.right > platform_sprite.rect.right:
                    player.rect.left = platform_sprite.rect.right
                    player.vel.x = 0
                    if not player.on_ground and not player.on_ladder:
                        if player.rect.bottom > platform_sprite.rect.top + getattr(C, 'MIN_WALL_OVERLAP_PX', 5) and \
                           player.rect.top < platform_sprite.rect.bottom - getattr(C, 'MIN_WALL_OVERLAP_PX', 5):
                            collided_with_wall_on_side = -1
                    player.pos.x = player.rect.centerx
                    player.pos.y = player.rect.bottom
                    log_player_physics(player, f"PLAT_COLL_RESOLVED_X_L",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))
        elif direction == 'y':
            if player.vel.y >= 0:  
                if player.rect.bottom >= platform_sprite.rect.top and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.top and \
                   rect_after_current_axis_move.top < platform_sprite.rect.top + 1: 
                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_LANDING', 0.15)
                    min_horizontal_overlap = player.rect.width * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - \
                                           max(player.rect.left, platform_sprite.rect.left)
                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.bottom = platform_sprite.rect.top 
                        if not player.on_ground and player.vel.y > 0:
                            player.can_wall_jump = False
                            player.wall_climb_timer = 0 
                            if not player.is_sliding and not (hasattr(player, 'state') and player.state.startswith('slide_trans')):
                                landing_friction = getattr(C, 'LANDING_FRICTION_MULTIPLIER', 0.8)
                                player.vel.x *= landing_friction
                        player.on_ground = True
                        player.vel.y = 0
                        player.pos.x = player.rect.centerx
                        player.pos.y = player.rect.bottom 
                        log_player_physics(player, f"PLAT_COLL_Y_LAND",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_land'))
            elif player.vel.y < 0:  
                if player.rect.top <= platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.top < platform_sprite.rect.bottom and \
                   rect_after_current_axis_move.bottom > platform_sprite.rect.bottom -1: 
                    min_overlap_ratio = getattr(C, 'MIN_PLATFORM_OVERLAP_RATIO_FOR_CEILING', 0.15)
                    min_horizontal_overlap = player.rect.width * min_overlap_ratio
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - \
                                           max(player.rect.left, platform_sprite.rect.left)
                    if actual_overlap_width >= min_horizontal_overlap:
                        if player.on_ladder: player.on_ladder = False 
                        player.rect.top = platform_sprite.rect.bottom 
                        player.vel.y = 0  
                        player.pos.x = player.rect.centerx
                        player.pos.y = player.rect.bottom 
                        log_player_physics(player, f"PLAT_COLL_Y_CEIL_NORMAL",
                                           (player.rect.copy(), current_player_rect_for_log,
                                            (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y_ceil_norm'))

    if direction == 'x':
        if collided_with_wall_on_side != 0 and not player.on_ground and not player.on_ladder:
            player.touching_wall = collided_with_wall_on_side
            player.can_wall_jump = not (hasattr(player, 'state') and player.state == 'wall_climb' and player.is_holding_climb_ability_key)


def check_player_ladder_collisions(player, ladders_group: pygame.sprite.Group):
    if not player._valid_init: return
    ladder_check_rect = player.rect.inflate(-player.rect.width * 0.6, -player.rect.height * 0.1)
    player.can_grab_ladder = False
    for ladder_sprite in pygame.sprite.spritecollide(player, ladders_group, False,
                           collided=lambda p_sprite, l_sprite: ladder_check_rect.colliderect(l_sprite.rect)):
        if abs(player.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
           ladder_sprite.rect.top < player.rect.centery < ladder_sprite.rect.bottom :
              player.can_grab_ladder = True; break


def check_player_character_collisions(player, direction: str, characters_list: list):
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: return False
    collision_occurred_this_axis = False

    for other_char in characters_list:
        if other_char is player: continue

        if not (other_char and hasattr(other_char, '_valid_init') and \
                other_char._valid_init and hasattr(other_char, 'is_dead') and \
                (not other_char.is_dead or getattr(other_char, 'is_petrified', False)) and \
                other_char.alive()):
            continue

        if player.rect.colliderect(other_char.rect):
            current_player_rect_for_log = player.rect.copy()
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}",
                               (current_player_rect_for_log, other_char.rect,
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', 'UnknownChar'))))
            collision_occurred_this_axis = True
            is_other_petrified = getattr(other_char, 'is_petrified', False)
            
            # Player getting ignited by an aflame enemy
            if isinstance(other_char, Enemy) and getattr(other_char, 'is_aflame', False) and \
               not player.is_aflame and not player.is_deflaming and \
               not player.is_frozen and not player.is_defrosting and not player.is_petrified:
                if hasattr(player, 'apply_aflame_effect'):
                    player.apply_aflame_effect()
                # No pushback here if ignited, similar to enemy-to-enemy ignition
                continue 

            is_enemy_stompable = isinstance(other_char, Enemy) and \
                                     not other_char.is_dead and \
                                     not getattr(other_char, 'is_stomp_dying', False) and \
                                     not getattr(other_char, 'is_aflame', False) and \
                                     not getattr(other_char, 'is_frozen', False) and \
                                     not getattr(other_char, 'is_petrified', False)


            if is_enemy_stompable and direction == 'y' and player.vel.y > 0.5: 
                previous_player_bottom_y_estimate = player.pos.y - player.vel.y 
                stomp_head_grace = getattr(C, 'PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX', 5)
                enemy_stomp_target_top = other_char.rect.top + stomp_head_grace
                player_landed_on_enemy_head = (
                    previous_player_bottom_y_estimate <= enemy_stomp_target_top and 
                    player.rect.bottom >= other_char.rect.top and 
                    player.rect.bottom <= other_char.rect.top + (other_char.rect.height * 0.40) 
                )
                if player_landed_on_enemy_head:
                    if hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill() 
                        player.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH 
                        player.on_ground = False 
                        if hasattr(player, 'set_state'): player.set_state('jump')
                        player.rect.bottom = other_char.rect.top -1 
                        player.pos.x = player.rect.centerx 
                        player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_STOMP",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.y, 'y_stomp'))
                    return True 

            player_state_str = str(getattr(player, 'state', '')).lower()
            is_attacking_self = getattr(player, 'is_attacking', False) or \
                                ('attack' in player_state_str)

            if direction == 'x':
                if is_attacking_self:
                    if player.vel.x > 0 or (player.vel.x == 0 and player.rect.centerx < other_char.rect.centerx):
                        player.rect.right = other_char.rect.left
                    elif player.vel.x < 0 or (player.vel.x == 0 and player.rect.centerx >= other_char.rect.centerx):
                        player.rect.left = other_char.rect.right
                    player.vel.x = 0
                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_ATTACK_X_STOP",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_attack_stop'))
                else:
                    bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
                    push_dir_self = 0
                    if player.rect.centerx < other_char.rect.centerx:
                        player.rect.right = other_char.rect.left
                        push_dir_self = -1
                    else:
                        player.rect.left = other_char.rect.right
                        push_dir_self = 1
                    player.vel.x = push_dir_self * bounce_vel

                    other_char_state_str = str(getattr(other_char, 'state', '')).lower()
                    is_attacking_other = getattr(other_char, 'is_attacking', False) or \
                                         ('attack' in other_char_state_str)

                    if hasattr(other_char, 'vel') and not is_attacking_other and not is_other_petrified:
                        other_char.vel.x = -push_dir_self * bounce_vel
                    if hasattr(other_char, 'pos') and hasattr(other_char, 'rect') and not is_attacking_other and not is_other_petrified:
                        other_char.pos.x += (-push_dir_self * 1.0) 
                        other_char.rect.centerx = round(other_char.pos.x) 
                        other_char.rect.bottom = round(other_char.pos.y)   
                        if hasattr(other_char, 'pos'): 
                            other_char.pos.x = other_char.rect.centerx
                            other_char.pos.y = other_char.rect.bottom
                    player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                    log_player_physics(player, f"CHAR_COLL_X_PUSHBACK",
                                       (player.rect.copy(), current_player_rect_for_log,
                                        (player.pos.x, player.pos.y), player.vel.x, 'x_push'))

            elif direction == 'y': 
                if player.vel.y > 0 and player.rect.bottom > other_char.rect.top and \
                   player.rect.centery < other_char.rect.centery: 
                    player.rect.bottom = other_char.rect.top
                    player.on_ground = True 
                    player.vel.y = 0
                elif player.vel.y < 0 and player.rect.top < other_char.rect.bottom and \
                     player.rect.centery > other_char.rect.centery: 
                    player.rect.top = other_char.rect.bottom
                    player.vel.y = 0
                player.pos.x = player.rect.centerx; player.pos.y = player.rect.bottom
                log_player_physics(player, f"CHAR_COLL_Y_STOP",
                                   (player.rect.copy(), current_player_rect_for_log,
                                    (player.pos.x, player.pos.y), player.vel.y, 'y_char_stop'))
    return collision_occurred_this_axis


def check_player_hazard_collisions(player, hazards_group: pygame.sprite.Group):
    current_time_ms = pygame.time.get_ticks()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown) or \
       player.is_petrified or player.is_frozen: # Petrified or Frozen players are immune to standard hazards
        return

    damaged_this_frame = False
    collided_hazards = pygame.sprite.spritecollide(player, hazards_group, False)

    for hazard in collided_hazards:
        if isinstance(hazard, Lava): 
            player_feet_in_lava = player.rect.bottom > hazard.rect.top + (player.rect.height * 0.2) 
            min_horizontal_hazard_overlap = player.rect.width * 0.20 
            actual_overlap_width = min(player.rect.right, hazard.rect.right) - max(player.rect.left, hazard.rect.left)

            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame:
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (player.rect.copy(), hazard.rect))
                    if hasattr(player, 'take_damage'): player.take_damage(C.LAVA_DAMAGE)
                    damaged_this_frame = True

                    if not player.is_dead: 
                         player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 
                         if player.rect.centerx < hazard.rect.centerx:
                             player.vel.x = -getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         else:
                             player.vel.x = getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.6
                         player.on_ground = False
                         player.on_ladder = False
                         if hasattr(player, 'set_state'): player.set_state('hit' if 'hit' in player.animations else 'jump') 
                    break 
        if damaged_this_frame: break