########## START OF FILE: enemy_ai_handler.py ##########

"""
version 1.0.0.3 (Added aflame/deflame check to block attacks)
Handles AI logic for enemies, including patrolling, chasing, and attacking decisions.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import random
import math
import constants as C # For accessing enemy-specific constants and general game constants

def set_enemy_new_patrol_target(enemy):
    """
    Sets a new patrol target X-coordinate for the enemy instance.
    If a patrol_area (pygame.Rect) is defined for the enemy, it patrols within that area.
    Otherwise, it patrols a set distance from its current position.

    Args:
        enemy (Enemy): The enemy instance for which to set a new patrol target.
    """

    if enemy.patrol_area and isinstance(enemy.patrol_area, pygame.Rect):
         min_x_patrol = enemy.patrol_area.left + enemy.rect.width / 2
         max_x_patrol = enemy.patrol_area.right - enemy.rect.width / 2
         
         if min_x_patrol < max_x_patrol: 
             enemy.patrol_target_x = random.uniform(min_x_patrol, max_x_patrol)
         else: 
             enemy.patrol_target_x = enemy.patrol_area.centerx
    else: 
        patrol_direction = 1 if random.random() > 0.5 else -1
        enemy.patrol_target_x = enemy.pos.x + patrol_direction * getattr(C, 'ENEMY_PATROL_DIST', 150)


def enemy_ai_update(enemy, players_list_for_ai):
    """
    Updates the enemy's AI state (e.g., patrolling, chasing, attacking) and behavior
    based on player proximity and other conditions. Modifies the enemy instance directly.

    Args:
        enemy (Enemy): The enemy instance to update.
        players_list_for_ai (list): A list of player Sprites that the AI can target.
    """
    if enemy.is_frozen or enemy.is_defrosting: 
        enemy.acc.x = 0 
        return

    current_time_ms = pygame.time.get_ticks() 
    
    if enemy.post_attack_pause_timer > 0 and current_time_ms < enemy.post_attack_pause_timer:
        enemy.acc.x = 0 
        if enemy.state != 'idle': 
            enemy.set_state('idle') 
        return 

    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       (enemy.is_taking_hit and current_time_ms - enemy.hit_timer < enemy.hit_cooldown):
        enemy.acc.x = 0 
        return

    closest_target_player = None
    min_squared_distance_to_player = float('inf') 

    for player_candidate in players_list_for_ai:
        is_candidate_targetable = (
            player_candidate and player_candidate._valid_init and
            hasattr(player_candidate, 'pos') and hasattr(player_candidate, 'rect') and
            player_candidate.alive() and not getattr(player_candidate, 'is_dead', True) 
        )
        if is_candidate_targetable:
            squared_dist = (player_candidate.pos.x - enemy.pos.x)**2 + \
                           (player_candidate.pos.y - enemy.pos.y)**2
            if squared_dist < min_squared_distance_to_player:
                min_squared_distance_to_player = squared_dist
                closest_target_player = player_candidate
    
    if not closest_target_player: 
        enemy.ai_state = 'patrolling' 
        if enemy.state not in ['patrolling', 'run', 'aflame', 'deflame']: # Allow burning anims
            enemy.set_state('patrolling') 
        
        if abs(enemy.pos.x - enemy.patrol_target_x) < 10: 
            set_enemy_new_patrol_target(enemy) 
        
        should_face_right_for_patrol = (enemy.patrol_target_x > enemy.pos.x)
        patrol_acceleration = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7 
        enemy.acc.x = patrol_acceleration * (1 if should_face_right_for_patrol else -1)
        
        if not enemy.is_attacking and enemy.facing_right != should_face_right_for_patrol:
            enemy.facing_right = should_face_right_for_patrol
        return 

    distance_to_target_player = math.sqrt(min_squared_distance_to_player) 
    enemy_attack_cooldown_duration = getattr(C, 'ENEMY_ATTACK_COOLDOWN', 1500) 
    enemy_attack_range = getattr(C, 'ENEMY_ATTACK_RANGE', 60) 
    enemy_detection_range = getattr(C, 'ENEMY_DETECTION_RANGE', 200) 
    enemy_standard_acceleration = getattr(C, 'ENEMY_ACCEL', 0.4)
    is_attack_off_cooldown = current_time_ms - enemy.attack_cooldown_timer > enemy_attack_cooldown_duration
    vertical_distance_to_player = abs(closest_target_player.rect.centery - enemy.rect.centery)
    has_vertical_line_of_sight = vertical_distance_to_player < enemy.rect.height * 1.0 
    is_player_in_attack_range = distance_to_target_player < enemy_attack_range and has_vertical_line_of_sight
    is_player_in_detection_range = distance_to_target_player < enemy_detection_range and has_vertical_line_of_sight

    if enemy.is_attacking and current_time_ms - enemy.attack_timer >= enemy.attack_duration:
         enemy.is_attacking = False; enemy.attack_type = 0      
         enemy.attack_cooldown_timer = current_time_ms 
         enemy.post_attack_pause_timer = current_time_ms + enemy.post_attack_pause_duration 
         # Don't force idle if aflame/deflame, let those states persist if active
         if not (enemy.is_aflame or enemy.is_deflaming):
            enemy.set_state('idle')
         enemy.acc.x = 0         
         return 

    if enemy.is_attacking: # Already in an attack animation
        enemy.acc.x = 0 
        return

    # Check if aflame/deflaming, if so, block new attack initiation
    if enemy.is_aflame or enemy.is_deflaming:
        # "Runs around" behavior: continue chasing or patrolling but no attacks
        if is_player_in_detection_range:
            enemy.ai_state = 'chasing'
            current_target_facing_right_aflame = (closest_target_player.pos.x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * (1 if current_target_facing_right_aflame else -1)
            if enemy.facing_right != current_target_facing_right_aflame:
                enemy.facing_right = current_target_facing_right_aflame
            # Let 'aflame' or 'deflame' state persist for animation
            if enemy.state not in ['aflame', 'deflame', 'run', 'chasing']: # Only switch to run if not already in a burn anim
                 enemy.set_state('run') # Or 'chasing' if you have distinct anims
        else: # Patrol if not detecting player
            enemy.ai_state = 'patrolling'
            if abs(enemy.pos.x - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            current_target_facing_right_aflame = (enemy.patrol_target_x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * 0.7 * (1 if current_target_facing_right_aflame else -1)
            if enemy.facing_right != current_target_facing_right_aflame:
                enemy.facing_right = current_target_facing_right_aflame
            if enemy.state not in ['aflame', 'deflame', 'run', 'patrolling']:
                enemy.set_state('run') # Or 'patrolling'
        return # Skip attack logic


    current_target_acceleration_x = 0 
    current_target_facing_right = enemy.facing_right 

    if is_player_in_attack_range and is_attack_off_cooldown: # This block is now skipped if aflame/deflaming
        enemy.ai_state = 'attacking'
        current_target_facing_right = (closest_target_player.pos.x > enemy.pos.x) 
        enemy.facing_right = current_target_facing_right
        attack_animation_key_to_use = 'attack_nm' if 'attack_nm' in enemy.animations and \
                                       enemy.animations['attack_nm'] else 'attack'
        enemy.set_state(attack_animation_key_to_use) 
        return 
    
    elif is_player_in_detection_range:
        enemy.ai_state = 'chasing'
        current_target_facing_right = (closest_target_player.pos.x > enemy.pos.x) 
        current_target_acceleration_x = enemy_standard_acceleration * (1 if current_target_facing_right else -1)
        if enemy.state not in ['chasing', 'run', 'aflame', 'deflame']: # Allow burn anims
            enemy.set_state('chasing') 
    
    else: 
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['patrolling', 'run', 'aflame', 'deflame']: # Allow burn anims
            enemy.set_state('patrolling')
        
        if abs(enemy.pos.x - enemy.patrol_target_x) < 10: 
            set_enemy_new_patrol_target(enemy) 
        
        current_target_facing_right = (enemy.patrol_target_x > enemy.pos.x)
        current_target_acceleration_x = enemy_standard_acceleration * 0.7 * \
                                        (1 if current_target_facing_right else -1)

    enemy.acc.x = current_target_acceleration_x
    if not enemy.is_attacking and enemy.facing_right != current_target_facing_right:
         enemy.facing_right = current_target_facing_right