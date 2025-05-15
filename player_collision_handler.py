# player_collision_handler.py
# -*- coding: utf-8 -*-
"""
Handles all player-related collision detection and resolution.
Logs detailed physics information if enabled.
"""
import pygame
import constants as C
from tiles import Lava 
from enemy import Enemy 

# Import the shared logging flag and helper function from logger.py
from logger import ENABLE_DETAILED_PHYSICS_LOGS, log_player_physics 
# No need to import the 'logger' instance directly if only using log_player_physics

def check_player_platform_collisions(player, direction: str, platforms_group: pygame.sprite.Group):
    """
    Handles collisions between the player and solid platforms.
    Resolves collisions by adjusting player position and velocity.
    Updates `player.on_ground` and `player.touching_wall` flags.
    Logs detailed steps if ENABLE_DETAILED_PHYSICS_LOGS is True.
    """
    collided_with_wall_on_side = 0 # -1 for left, 1 for right
    
    # Iterate over potentially colliding platforms
    colliding_platforms = pygame.sprite.spritecollide(player, platforms_group, False)
    
    for platform_sprite in colliding_platforms:
        original_rect_before_this_snap = player.rect.copy() # For logging comparison
        original_pos_before_this_snap = player.pos.copy()   # For logging comparison

        log_player_physics(player, f"PLAT_COLL_CHECK DIR:{direction}", 
                           (original_rect_before_this_snap, platform_sprite.rect, platform_sprite.platform_type))
        
        if direction == 'x':
            if player.vel.x > 0: # Moving right
                player.rect.right = platform_sprite.rect.left
                if not player.on_ground and not player.on_ladder and player.rect.bottom > platform_sprite.rect.top + 5:
                    collided_with_wall_on_side = 1
            elif player.vel.x < 0: # Moving left
                player.rect.left = platform_sprite.rect.right
                if not player.on_ground and not player.on_ladder and player.rect.bottom > platform_sprite.rect.top + 5:
                    collided_with_wall_on_side = -1
            player.vel.x = 0 # Stop horizontal movement due to collision
            player.pos = pygame.math.Vector2(player.rect.midbottom) # Sync pos from snapped rect
            log_player_physics(player, f"PLAT_COLL_RESOLVED_X", 
                               (player.rect.copy(), original_rect_before_this_snap, 
                                (player.pos.x, player.pos.y), player.vel.x, player.on_ground, 'x'))
        
        elif direction == 'y':
            current_on_ground_status_before_y_resolve = player.on_ground 
            if player.vel.y >= 0: # Moving down or stationary vertically
                is_landing_on_top = (
                    player.rect.bottom >= platform_sprite.rect.top and
                    (original_pos_before_this_snap.y - player.vel.y) <= platform_sprite.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX
                )
                if is_landing_on_top:
                    min_horizontal_overlap = player.rect.width * 0.3
                    actual_overlap_width = min(player.rect.right, platform_sprite.rect.right) - max(player.rect.left, platform_sprite.rect.left)
                    
                    if actual_overlap_width >= min_horizontal_overlap:
                        player.rect.bottom = platform_sprite.rect.top
                        if not current_on_ground_status_before_y_resolve and player.vel.y > 0: 
                            player.can_wall_jump=False; player.wall_climb_timer=0
                            if not player.is_sliding and player.state != 'slide_trans_end':
                                player.vel.x *= 0.8
                        player.on_ground = True; player.vel.y = 0
            
            elif player.vel.y < 0: # Moving up
                is_hitting_ceiling = (
                    player.rect.top <= platform_sprite.rect.bottom and
                    ((original_pos_before_this_snap.y - player.rect.height) - player.vel.y) >= platform_sprite.rect.bottom -1 
                )
                if is_hitting_ceiling:
                     if player.on_ladder: player.on_ladder = False
                     player.rect.top = platform_sprite.rect.bottom
                     player.vel.y = 0
            
            player.pos = pygame.math.Vector2(player.rect.midbottom) # Sync pos from snapped rect
            log_player_physics(player, f"PLAT_COLL_RESOLVED_Y", 
                               (player.rect.copy(), original_rect_before_this_snap, 
                                (player.pos.x, player.pos.y), player.vel.y, player.on_ground, 'y'))
    
    if direction == 'x' and collided_with_wall_on_side != 0 and \
       not player.on_ground and not player.on_ladder: # Wall interactions generally only in air
         player.touching_wall = collided_with_wall_on_side
         player.can_wall_jump = not (player.state == 'wall_climb' and player.is_holding_climb_ability_key)

def check_player_ladder_collisions(player, ladders_group: pygame.sprite.Group):
    if not player._valid_init: return
    ladder_check_rect = player.rect.inflate(-player.rect.width * 0.6, -player.rect.height * 0.1)
    player.can_grab_ladder = False
    for ladder_sprite in pygame.sprite.spritecollide(player, ladders_group, False, 
                           collided=lambda p_sprite, l_sprite: ladder_check_rect.colliderect(l_sprite.rect)): # Ensure correct lambda usage
        if abs(player.rect.centerx - ladder_sprite.rect.centerx) < ladder_sprite.rect.width * 0.7 and \
           ladder_sprite.rect.top < player.rect.centery < ladder_sprite.rect.bottom : 
              player.can_grab_ladder = True; break

def check_player_character_collisions(player, direction: str, characters_list: list):
    if not player._valid_init or player.is_dead or not player.alive(): return False
    collision_occurred_this_axis = False # More descriptive name
    for other_char in characters_list:
        if other_char is player: continue
        if not (other_char and hasattr(other_char, '_valid_init') and \
                other_char._valid_init and hasattr(other_char, 'is_dead') and \
                not other_char.is_dead and other_char.alive()):
            continue 

        if player.rect.colliderect(other_char.rect):
            original_rect_before_char_snap = player.rect.copy()
            log_player_physics(player, f"CHAR_COLL_CHECK DIR:{direction}", 
                               (original_rect_before_char_snap, other_char.rect, 
                                getattr(other_char, 'player_id', getattr(other_char, 'enemy_id', 'UnknownChar'))))
            
            collision_occurred_this_axis = True
            is_enemy_stompable = isinstance(other_char, Enemy) and \
                                     not other_char.is_dead and \
                                     not getattr(other_char, 'is_stomp_dying', False)

            if is_enemy_stompable and direction == 'y' and player.vel.y > 0.5:
                previous_player_bottom_y = player.pos.y - player.vel.y 
                player_landed_on_enemy_head = (
                    previous_player_bottom_y <= other_char.rect.top + C.PLAYER_STOMP_LAND_ON_ENEMY_GRACE_PX and
                    player.rect.bottom >= other_char.rect.top and 
                    player.rect.bottom <= other_char.rect.top + (other_char.rect.height * 0.33) 
                )
                if player_landed_on_enemy_head:
                    if hasattr(other_char, 'stomp_kill') and callable(other_char.stomp_kill):
                        other_char.stomp_kill()
                        player.vel.y = C.PLAYER_STOMP_BOUNCE_STRENGTH
                        player.on_ground = False
                        player.set_state('jump') 
                        player.rect.bottom = other_char.rect.top -1 
                        player.pos = pygame.math.Vector2(player.rect.midbottom) 
                    log_player_physics(player, f"CHAR_COLL_STOMP", 
                                       (player.rect.copy(), original_rect_before_char_snap, 
                                        (player.pos.x, player.pos.y), player.vel.x, 'y'))
                    return True # Stomp handled, implies collision occurred

            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            if direction == 'x':
                push_dir_self = -1 if player.rect.centerx < other_char.rect.centerx else 1
                if push_dir_self == -1: player.rect.right = other_char.rect.left
                else: player.rect.left = other_char.rect.right
                player.vel.x = push_dir_self * bounce_vel
                if hasattr(other_char, 'vel'): other_char.vel.x = -push_dir_self * bounce_vel
                if hasattr(other_char, 'pos') and hasattr(other_char, 'rect'): 
                    other_char.pos.x += (-push_dir_self * 1.5)
                    other_char.rect.midbottom = (round(other_char.pos.x), round(other_char.pos.y)) 
                    other_char.pos = pygame.math.Vector2(other_char.rect.midbottom) 
                player.pos = pygame.math.Vector2(player.rect.midbottom) 
                log_player_physics(player, f"CHAR_COLL_RESOLVED_X", 
                                   (player.rect.copy(), original_rect_before_char_snap, 
                                    (player.pos.x, player.pos.y), player.vel.x, 'x'))
            elif direction == 'y': # This part is for non-stomp vertical character collisions
                if player.vel.y > 0 and player.rect.bottom > other_char.rect.top and \
                   player.rect.centery < other_char.rect.centery: # Landing on other
                    player.rect.bottom = other_char.rect.top; player.on_ground = True; player.vel.y = 0
                elif player.vel.y < 0 and player.rect.top < other_char.rect.bottom and \
                     player.rect.centery > other_char.rect.centery: # Hitting other from below
                    player.rect.top = other_char.rect.bottom; player.vel.y = 0
                player.pos = pygame.math.Vector2(player.rect.midbottom) 
                log_player_physics(player, f"CHAR_COLL_RESOLVED_Y", 
                                   (player.rect.copy(), original_rect_before_char_snap, 
                                    (player.pos.x, player.pos.y), player.vel.y, 'y'))
            # If any character collision happened on this axis, we might want to stop checking others for this axis
            # to prevent multiple pushbacks in one frame, or let it iterate if that's desired.
            # For now, we'll let it iterate, but collision_occurred_this_axis is set.
    return collision_occurred_this_axis

def check_player_hazard_collisions(player, hazards_group: pygame.sprite.Group):
    current_time_ms = pygame.time.get_ticks()
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown): 
        return
    
    damaged_this_frame = False
    # Use spritecollide for broader check first
    collided_hazards = pygame.sprite.spritecollide(player, hazards_group, False)

    for hazard in collided_hazards:
        if isinstance(hazard, Lava):
            player_feet_in_lava = player.rect.bottom > hazard.rect.top + 1 
            min_horizontal_hazard_overlap = player.rect.width * 0.25 # Example: 25% of player width
            
            # Calculate actual horizontal overlap
            actual_overlap_width = min(player.rect.right, hazard.rect.right) - max(player.rect.left, hazard.rect.left)
            
            if player_feet_in_lava and actual_overlap_width >= min_horizontal_hazard_overlap:
                if not damaged_this_frame:
                    log_player_physics(player, f"HAZARD_COLL_LAVA", (player.rect.copy(), hazard.rect))
                    player.take_damage(C.LAVA_DAMAGE) # This is a method call on player instance
                    damaged_this_frame = True
                    
                    if not player.is_dead: # If player survived
                         player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.75 
                         push_dir = 1 if player.rect.centerx < hazard.rect.centerx else -1
                         player.vel.x = -push_dir * getattr(C, 'PLAYER_RUN_SPEED_LIMIT', 7) * 0.5
                         player.on_ground = False 
                         player.on_ladder = False 
                    break # Process one lava collision per frame
        # Can add checks for other hazard types here
        if damaged_this_frame: break