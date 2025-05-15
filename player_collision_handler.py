# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.1
Handles all player-related collision detection and resolution.
"""
import pygame
import constants as C
from tiles import Lava # For type checking in hazard collision
from enemy import Enemy # For type checking in stomp

def check_player_platform_collisions(player, direction: str, platforms_group: pygame.sprite.Group):
    collided_with_wall_on_side = 0
    
    for platform_sprite in pygame.sprite.spritecollide(player, platforms_group, False):
        if direction == 'x':
            if player.vel.x > 0:
                player.rect.right = platform_sprite.rect.left
                if not player.on_ground and not player.on_ladder and player.rect.bottom > platform_sprite.rect.top + 5:
                    collided_with_wall_on_side = 1
            elif player.vel.x < 0:
                player.rect.left = platform_sprite.rect.right
                if not player.on_ground and not player.on_ladder and player.rect.bottom > platform_sprite.rect.top + 5:
                    collided_with_wall_on_side = -1
            player.vel.x = 0
            player.pos.x = float(player.rect.centerx) # Sync precise pos after snapping
        
        elif direction == 'y':
            if player.vel.y >= 0: # Changed from > to >=
                is_landing_on_top = (
                    player.rect.bottom >= platform_sprite.rect.top and
                    (player.pos.y - player.vel.y) <= platform_sprite.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                )
                if is_landing_on_top:
                    min_horizontal_overlap = player.rect.width * 0.3
                    overlap_left = max(0, player.rect.right - platform_sprite.rect.left)
                    overlap_right = max(0, platform_sprite.rect.right - player.rect.left)
                    horizontal_overlap = min(overlap_left, overlap_right, player.rect.width, platform_sprite.rect.width)

                    if horizontal_overlap >= min_horizontal_overlap:
                        player.rect.bottom = platform_sprite.rect.top
                        if not player.on_ground and player.vel.y > 0: # Just landed
                            player.can_wall_jump=False; player.wall_climb_timer=0
                            if not player.is_sliding and player.state != 'slide_trans_end':
                                player.vel.x *= 0.8
                        player.on_ground = True; player.vel.y = 0
                        player.pos.y = float(player.rect.bottom) # Sync precise pos
            
            elif player.vel.y < 0:
                is_hitting_ceiling = (
                    player.rect.top <= platform_sprite.rect.bottom and
                    ((player.pos.y - player.rect.height) - player.vel.y) >= platform_sprite.rect.bottom -1 
                )
                if is_hitting_ceiling:
                     if player.on_ladder: player.on_ladder = False
                     player.rect.top = platform_sprite.rect.bottom
                     player.vel.y = 0
                     player.pos.y = float(player.rect.bottom) # Sync precise pos
    
    if direction == 'x' and collided_with_wall_on_side != 0 and \
       not player.on_ground and not player.on_ladder:
         player.touching_wall = collided_with_wall_on_side
         player.can_wall_jump = not (player.state == 'wall_climb' and player.is_holding_climb_ability_key)

def check_player_ladder_collisions(player, ladders_group: pygame.sprite.Group):
    if not player._valid_init: return
    ladder_check_rect = player.rect.inflate(-player.rect.width * 0.6, -player.rect.height * 0.1)
    player.can_grab_ladder = False
    for ladder_sprite in pygame.sprite.spritecollide(player, ladders_group, False, 
                           collided=lambda p, l: ladder_check_rect.colliderect(l.rect)):
        if abs(player.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
           ladder_sprite.rect.top < player.rect.centery < ladder_sprite.rect.bottom : 
              player.can_grab_ladder = True; break

def check_player_character_collisions(player, direction: str, characters_list: list):
    if not player._valid_init or player.is_dead or not player.alive(): return False
    collision_occurred = False
    for other_char in characters_list:
        if other_char is player: continue
        if not (other_char and hasattr(other_char, '_valid_init') and \
                other_char._valid_init and hasattr(other_char, 'is_dead') and \
                not other_char.is_dead and other_char.alive()):
            continue 

        if player.rect.colliderect(other_char.rect):
            collision_occurred = True
            is_enemy_stompable = isinstance(other_char, Enemy) and \
                                     not other_char.is_dead and \
                                     not getattr(other_char, 'is_stomp_dying', False)

            if is_enemy_stompable and direction == 'y' and player.vel.y > 0.5:
                player_bottom_vs_enemy_top_diff = player.rect.bottom - other_char.rect.top
                previous_player_bottom = player.pos.y - player.vel.y 
                if (previous_player_bottom <= other_char.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX and \
                    player_bottom_vs_enemy_top_diff >= 0 and \
                    player_bottom_vs_enemy_top_diff < other_char.rect.height * 0.33):
                    if hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill()
                        player.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH
                        player.on_ground = False
                        from player_state_handler import set_player_state # Local import
                        set_player_state(player, 'jump')
                        player.rect.bottom = other_char.rect.top -1
                        player.pos.y = float(player.rect.bottom)
                    return True # Stomp handled

            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            if direction == 'x':
                push_dir_self = -1 if player.rect.centerx < other_char.rect.centerx else 1
                if push_dir_self == -1: player.rect.right = other_char.rect.left
                else: player.rect.left = other_char.rect.right
                player.vel.x = push_dir_self * bounce_vel
                if hasattr(other_char, 'vel'): other_char.vel.x = -push_dir_self * bounce_vel
                if hasattr(other_char, 'pos') and hasattr(other_char, 'rect'): 
                    other_char.pos.x += (-push_dir_self * 1.5)
                    other_char.rect.centerx = round(other_char.pos.x)
                player.pos.x = float(player.rect.centerx)
            elif direction == 'y':
                if player.vel.y > 0 and player.rect.bottom > other_char.rect.top and \
                   player.rect.centery < other_char.rect.centery:
                    player.rect.bottom = other_char.rect.top; player.on_ground = True; player.vel.y = 0
                elif player.vel.y < 0 and player.rect.top < other_char.rect.bottom and \
                     player.rect.centery > other_char.rect.centery:
                    player.rect.top = other_char.rect.bottom; player.vel.y = 0
                player.pos.y = float(player.rect.bottom)
    return collision_occurred

def check_player_hazard_collisions(player, hazards_group: pygame.sprite.Group):
    current_time_ms = pygame.time.get_ticks()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown): 
        return
    damaged_this_frame = False
    check_point = (player.rect.centerx, player.rect.bottom - 2) 
    for hazard in hazards_group:
        if isinstance(hazard, Lava) and hazard.rect.collidepoint(check_point):
            if not damaged_this_frame:
                player.take_damage(C.LAVA_DAMAGE) # This is a method call on player instance
                damaged_this_frame = True
                if not player.is_dead:
                     player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75
                     push_dir = 1 if player.rect.centerx < hazard.rect.centerx else -1
                     player.vel.x = -push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.5
                     player.on_ground = False; player.on_ladder = False
                break