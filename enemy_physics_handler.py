# enemy_physics_handler.py
# -*- coding: utf-8 -*-
"""
# version 1.0.2 (Allow aflame/deflame physics, block only for frozen/defrosting)
Handles enemy physics, including movement, gravity, friction,
and collision detection/response with platforms, characters, and hazards.
Ensures aflame enemies can ignite other characters.
"""
import pygame
import constants as C
from tiles import Lava 
import enemy as enemy_module_ref 

try:
    from enemy_ai_handler import set_enemy_new_patrol_target
except ImportError:
    def set_enemy_new_patrol_target(enemy):
        print(f"WARNING ENEMY_PHYSICS: enemy_ai_handler.set_enemy_new_patrol_target not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")


try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_PHYSICS_HANDLER: logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error_log_func(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
    error = error_log_func

# --- Internal Helper Functions for Collision ---

def _check_enemy_platform_collisions(enemy, direction: str, platforms_group: pygame.sprite.Group):
    """
    Handles collisions between the enemy and solid platforms.
    Modifies enemy.rect, enemy.vel, enemy.on_ground.
    Calls set_enemy_new_patrol_target if a wall is hit during patrolling.
    """
    for platform_sprite in pygame.sprite.spritecollide(enemy, platforms_group, False):
        if direction == 'x':
            original_vel_x = enemy.vel.x
            if enemy.vel.x > 0: enemy.rect.right = platform_sprite.rect.left
            elif enemy.vel.x < 0: enemy.rect.left = platform_sprite.rect.right
            enemy.vel.x = 0
            if enemy.ai_state == 'patrolling' and abs(original_vel_x) > 0.1:
                if (abs(enemy.rect.right - platform_sprite.rect.left) < 2 or \
                    abs(enemy.rect.left - platform_sprite.rect.right) < 2):
                    set_enemy_new_patrol_target(enemy)
        elif direction == 'y':
            if enemy.vel.y > 0: 
                if enemy.rect.bottom > platform_sprite.rect.top and \
                   (enemy.pos.y - enemy.vel.y) <= platform_sprite.rect.top + 1: 
                     enemy.rect.bottom = platform_sprite.rect.top
                     enemy.on_ground = True
                     enemy.vel.y = 0
            elif enemy.vel.y < 0: 
                if enemy.rect.top < platform_sprite.rect.bottom and \
                   ((enemy.pos.y - enemy.standard_height) - enemy.vel.y) >= platform_sprite.rect.bottom - 1: 
                     enemy.rect.top = platform_sprite.rect.bottom
                     enemy.vel.y = 0
        if direction == 'x': enemy.pos.x = enemy.rect.centerx
        else: enemy.pos.y = enemy.rect.bottom


def _check_enemy_character_collision(enemy, direction: str, character_list: list):
    """
    Handles collisions between the enemy and other characters (players, other enemies).
    Applies pushback. Allows aflame enemies to ignite other non-aflame characters.
    Returns True if a collision occurred, False otherwise.
    """
    collision_occurred = False
    for other_char_sprite in character_list:
        if other_char_sprite is enemy: continue 

        if not (other_char_sprite and hasattr(other_char_sprite, '_valid_init') and \
                other_char_sprite._valid_init and hasattr(other_char_sprite, 'is_dead') and \
                (not other_char_sprite.is_dead or getattr(other_char_sprite, 'is_petrified', False)) and \
                other_char_sprite.alive()):
            continue

        if enemy.rect.colliderect(other_char_sprite.rect):
            collision_occurred = True
            is_other_petrified = getattr(other_char_sprite, 'is_petrified', False)
            is_other_character_aflame_or_deflaming = getattr(other_char_sprite, 'is_aflame', False) or \
                                                     getattr(other_char_sprite, 'is_deflaming', False)
            is_other_character_frozen_or_defrosting = getattr(other_char_sprite, 'is_frozen', False) or \
                                                      getattr(other_char_sprite, 'is_defrosting', False)


            # Aflame spread logic: enemy to another character (player or enemy)
            if enemy.is_aflame and hasattr(other_char_sprite, 'apply_aflame_effect') and \
               not is_other_character_aflame_or_deflaming and \
               not is_other_character_frozen_or_defrosting and \
               not enemy.has_ignited_another_enemy_this_cycle and not is_other_petrified:
                
                # Specific logic for enemy-to-enemy ignition (only one)
                if isinstance(other_char_sprite, enemy_module_ref.Enemy): # MODIFIED: enemy_module_ref.Enemy
                    debug(f"Enemy {enemy.enemy_id} (aflame) touched Enemy {getattr(other_char_sprite, 'enemy_id', 'Unknown')}. Igniting.")
                    other_char_sprite.apply_aflame_effect()
                    enemy.has_ignited_another_enemy_this_cycle = True 
                # Logic for enemy-to-player ignition
                elif 'Player' in other_char_sprite.__class__.__name__: # Check if it's a Player instance
                    debug(f"Enemy {enemy.enemy_id} (aflame) touched Player {getattr(other_char_sprite, 'player_id', 'Unknown')}. Igniting player.")
                    other_char_sprite.apply_aflame_effect()
                    # Note: has_ignited_another_enemy_this_cycle might prevent igniting multiple players too quickly,
                    # or you might want a separate flag/timer for player ignition cooldown from a single enemy.
                    # For now, the single flag applies to igniting *any* other character once.
                    enemy.has_ignited_another_enemy_this_cycle = True

                continue # Skip pushback if just ignited

            bounce_vel = getattr(C, 'CHARACTER_BOUNCE_VELOCITY', 2.5)
            if direction == 'x':
                push_dir_self = -1 if enemy.rect.centerx < other_char_sprite.rect.centerx else 1
                if push_dir_self == -1: enemy.rect.right = other_char_sprite.rect.left
                else: enemy.rect.left = other_char_sprite.rect.right
                enemy.vel.x = push_dir_self * bounce_vel

                if not is_other_petrified: 
                    can_push_other = True
                    if hasattr(other_char_sprite, 'is_attacking') and other_char_sprite.is_attacking: can_push_other = False
                    if hasattr(other_char_sprite, 'is_aflame') and other_char_sprite.is_aflame: can_push_other = False
                    if hasattr(other_char_sprite, 'is_frozen') and other_char_sprite.is_frozen: can_push_other = False
                    if hasattr(other_char_sprite, 'is_dashing') and other_char_sprite.is_dashing: can_push_other = False
                    if hasattr(other_char_sprite, 'is_rolling') and other_char_sprite.is_rolling: can_push_other = False

                    if hasattr(other_char_sprite, 'vel') and can_push_other:
                        other_char_sprite.vel.x = -push_dir_self * bounce_vel
                    if hasattr(other_char_sprite, 'pos') and hasattr(other_char_sprite, 'rect') and can_push_other:
                        other_char_sprite.pos.x += (-push_dir_self * 1.5) 
                        other_char_sprite.rect.centerx = round(other_char_sprite.pos.x)
                        other_char_sprite.rect.bottom = round(other_char_sprite.pos.y)
                        other_char_sprite.pos.x = other_char_sprite.rect.centerx
                        other_char_sprite.pos.y = other_char_sprite.rect.bottom
                enemy.pos.x = enemy.rect.centerx

            elif direction == 'y': 
                if enemy.vel.y > 0 and enemy.rect.bottom > other_char_sprite.rect.top and \
                   enemy.rect.centery < other_char_sprite.rect.centery:
                    enemy.rect.bottom = other_char_sprite.rect.top
                    enemy.on_ground = True
                    enemy.vel.y = 0
                elif enemy.vel.y < 0 and enemy.rect.top < other_char_sprite.rect.bottom and \
                     enemy.rect.centery > other_char_sprite.rect.centery:
                    enemy.rect.top = other_char_sprite.rect.bottom
                    enemy.vel.y = 0
                enemy.pos.y = enemy.rect.bottom
    return collision_occurred


def _check_enemy_hazard_collisions(enemy, hazards_group: pygame.sprite.Group):
    """Handles collisions between the enemy and hazards like lava."""
    current_time_ms = pygame.time.get_ticks()
    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       (enemy.is_taking_hit and current_time_ms - enemy.hit_timer < enemy.hit_cooldown) or \
       enemy.is_petrified or enemy.is_frozen: # Petrified or Frozen enemies are immune to standard hazards
        return

    damage_taken_this_frame = False
    hazard_check_point = (enemy.rect.centerx, enemy.rect.bottom - 1) 

    for hazard in hazards_group:
        if isinstance(hazard, Lava) and hazard.rect.collidepoint(hazard_check_point):
            if not damage_taken_this_frame:
                if hasattr(enemy, 'take_damage'): 
                    enemy.take_damage(getattr(C, 'LAVA_DAMAGE', 25)) 
                damage_taken_this_frame = True

                if not enemy.is_dead: 
                    enemy.vel.y = getattr(C, 'PLAYER_JUMP_STRENGTH', -15) * 0.3 
                    push_dir = 1 if enemy.rect.centerx < hazard.rect.centerx else -1
                    enemy.vel.x = -push_dir * 4 
                    enemy.on_ground = False 
                break 
        if damage_taken_this_frame: break 


# --- Main Physics and Collision Update Function ---

def update_enemy_physics_and_collisions(enemy, dt_sec, platforms_group, hazards_group, all_other_characters_list):
    """
    Applies all physics (gravity, friction, movement) and handles all collisions
    for the given enemy instance.
    This is called from the main Enemy.update() method if the enemy is not in an
    overriding state (like frozen, petrified, smashed, etc.).
    MODIFIED: Now allows physics processing for aflame/deflaming states.
    """
    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       enemy.is_petrified or enemy.is_frozen or enemy.is_defrosting: # MODIFIED: Removed aflame/deflaming from this blocking condition
        # Petrified, Frozen, Defrosting enemies have simplified or no physics handled here.
        # Gravity for petrified is in status_effects, others are stationary.
        return

    # --- Apply Gravity ---
    enemy.vel.y += enemy.acc.y # acc.y should be gravity

    # --- Horizontal Movement and Friction (based on AI decisions in enemy.acc.x) ---
    enemy_friction = getattr(C, 'ENEMY_FRICTION', -0.12)
    
    # Determine speed limit based on state
    if enemy.is_aflame:
        current_speed_limit = getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5) * getattr(C, 'ENEMY_AFLAME_SPEED_MULTIPLIER', 1.0)
    elif enemy.is_deflaming:
        current_speed_limit = getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5) * getattr(C, 'ENEMY_DEFLAME_SPEED_MULTIPLIER', 1.0)
    else:
        current_speed_limit = getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5)

    terminal_velocity = getattr(C, 'TERMINAL_VELOCITY_Y', 18)

    enemy.vel.x += enemy.acc.x # Apply AI-driven acceleration

    if enemy.on_ground and enemy.acc.x == 0:
        friction_force = enemy.vel.x * enemy_friction
        if abs(enemy.vel.x) > 0.1:
            enemy.vel.x += friction_force
        else:
            enemy.vel.x = 0 

    enemy.vel.x = max(-current_speed_limit, min(current_speed_limit, enemy.vel.x))
    enemy.vel.y = min(enemy.vel.y, terminal_velocity)

    enemy.on_ground = False 

    enemy.pos.x += enemy.vel.x
    enemy.rect.centerx = round(enemy.pos.x) 
    _check_enemy_platform_collisions(enemy, 'x', platforms_group)
    collided_x_char = _check_enemy_character_collision(enemy, 'x', all_other_characters_list)
    enemy.pos.x = enemy.rect.centerx 

    enemy.pos.y += enemy.vel.y
    enemy.rect.bottom = round(enemy.pos.y) 
    _check_enemy_platform_collisions(enemy, 'y', platforms_group)
    if not collided_x_char: 
        _check_enemy_character_collision(enemy, 'y', all_other_characters_list)
    enemy.pos.y = enemy.rect.bottom 

    _check_enemy_hazard_collisions(enemy, hazards_group)
