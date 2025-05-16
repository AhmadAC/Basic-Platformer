# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles enemy combat mechanics: checking attack collisions and processing damage taken.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import constants as C # For accessing damage values, hit stun duration, etc.

def check_enemy_attack_collisions(enemy, player_target_list):
    """
    Checks if the enemy's current attack (if any) hits any player in the target list.
    Applies damage to the player if a hit is registered.

    Args:
        enemy (Enemy): The attacking enemy instance.
        player_target_list (list): A list of Player sprites to check for collision.
    """
    if enemy.is_frozen or enemy.is_defrosting: # Prevent attacks if frozen or defrosting
        return

    if not enemy._valid_init or not enemy.is_attacking or enemy.is_dead or not enemy.alive():
        return

    if enemy.facing_right:
        enemy.attack_hitbox.midleft = enemy.rect.midright 
    else:
        enemy.attack_hitbox.midright = enemy.rect.midleft 
    
    enemy.attack_hitbox.centery = enemy.rect.centery 
    
    current_time_ms = pygame.time.get_ticks()

    for player_sprite in player_target_list:
        if not (player_sprite and player_sprite._valid_init and \
                not player_sprite.is_dead and player_sprite.alive()):
            continue

        player_is_currently_invincible = False
        if hasattr(player_sprite, 'is_taking_hit') and hasattr(player_sprite, 'hit_timer') and \
           hasattr(player_sprite, 'hit_cooldown'):
            if player_sprite.is_taking_hit and \
               (current_time_ms - player_sprite.hit_timer < player_sprite.hit_cooldown):
                player_is_currently_invincible = True
        
        if player_is_currently_invincible:
            continue 

        if enemy.attack_hitbox.colliderect(player_sprite.rect):
            if hasattr(player_sprite, 'take_damage') and callable(player_sprite.take_damage):
                damage_to_inflict_on_player = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10) 
                player_sprite.take_damage(damage_to_inflict_on_player)

def enemy_take_damage(enemy, damage_amount):
    """
    Handles the enemy instance taking a specified amount of damage.
    Updates health and potentially triggers 'hit' or 'death' states for the enemy.

    Args:
        enemy (Enemy): The enemy instance receiving damage.
        damage_amount (int): The amount of damage to inflict.
    """
    current_time_ms = pygame.time.get_ticks()
    
    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       (enemy.is_taking_hit and current_time_ms - enemy.hit_timer < enemy.hit_cooldown) or \
       enemy.is_frozen or enemy.is_defrosting: # Cannot take damage if frozen/defrosting (unless it's a special shatter damage type)
        return

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health) 

    if enemy.current_health <= 0: 
        if not enemy.is_dead: 
            enemy.set_state('death') 
    else: 
        if not (enemy.state == 'hit' and current_time_ms - enemy.state_timer < getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)):
             enemy.set_state('hit') 