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
    # Enemy must be valid, actively attacking, and alive to deal damage
    if not enemy._valid_init or not enemy.is_attacking or enemy.is_dead or not enemy.alive():
        return

    # Position the enemy's attack hitbox based on its facing direction and current position.
    # It's assumed that enemy.attack_hitbox is a pygame.Rect attribute of the enemy instance,
    # and its size is defined in the Enemy class or constants.
    if enemy.facing_right:
        enemy.attack_hitbox.midleft = enemy.rect.midright # Position hitbox to the right
    else:
        enemy.attack_hitbox.midright = enemy.rect.midleft # Position hitbox to the left
    
    # Vertically align the hitbox with the enemy's center (can be adjusted if attacks are high/low)
    enemy.attack_hitbox.centery = enemy.rect.centery 
    
    current_time_ms = pygame.time.get_ticks()

    for player_sprite in player_target_list:
        # Ensure the player target is valid, alive, and not dead
        if not (player_sprite and player_sprite._valid_init and \
                not player_sprite.is_dead and player_sprite.alive()):
            continue

        # --- Check if the player target is currently invincible (e.g., recently hit) ---
        player_is_currently_invincible = False
        if hasattr(player_sprite, 'is_taking_hit') and hasattr(player_sprite, 'hit_timer') and \
           hasattr(player_sprite, 'hit_cooldown'):
            if player_sprite.is_taking_hit and \
               (current_time_ms - player_sprite.hit_timer < player_sprite.hit_cooldown):
                player_is_currently_invincible = True
        
        if player_is_currently_invincible:
            continue # Skip this player if they are invincible

        # --- Perform collision check between enemy's attack hitbox and player's rect ---
        if enemy.attack_hitbox.colliderect(player_sprite.rect):
            # A hit is registered!
            if hasattr(player_sprite, 'take_damage') and callable(player_sprite.take_damage):
                # Apply damage to the player
                damage_to_inflict_on_player = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10) # Default damage
                # Future: Could have different damage based on enemy.attack_type if enemies have multiple attacks
                
                player_sprite.take_damage(damage_to_inflict_on_player)
                
                # Optional: Prevent the same attack swing from hitting the same player multiple times.
                # This might involve adding the player_sprite to a list of 'already_hit_this_swing'
                # on the enemy instance, and clearing that list when a new attack starts.
                # For simplicity here, one hit per check_attack_collisions call against a target.
                # If called every frame an attack is active, it might hit multiple frames.
                # Often, the attack state itself (is_attacking) is cleared after one successful hit check
                # or after a certain number of active frames.
                # For now, let's assume one hit is sufficient for this attack instance.
                # If the game design wants an attack to hit only once per animation,
                # the enemy.is_attacking flag or a specific hit flag should be managed carefully.
                
                # Example: If an attack should only connect once per animation, you might do:
                # if enemy.is_attacking and not getattr(enemy, '_has_hit_this_attack_swing', False):
                #     player_sprite.take_damage(damage_to_inflict_on_player)
                #     enemy._has_hit_this_attack_swing = True # Set a flag
                # (This flag would need to be reset when a new attack starts in enemy.set_state)
                
                # For now, simple damage application on collision.
                # If multiple players can be hit by one swing, this loop continues.
                # If only one player can be hit, you might 'return' here.

def enemy_take_damage(enemy, damage_amount):
    """
    Handles the enemy instance taking a specified amount of damage.
    Updates health and potentially triggers 'hit' or 'death' states for the enemy.

    Args:
        enemy (Enemy): The enemy instance receiving damage.
        damage_amount (int): The amount of damage to inflict.
    """
    current_time_ms = pygame.time.get_ticks()
    
    # Enemy cannot take damage if invalid, already dead, not in game world, or in hit cooldown
    if not enemy._valid_init or enemy.is_dead or not enemy.alive() or \
       (enemy.is_taking_hit and current_time_ms - enemy.hit_timer < enemy.hit_cooldown):
        # if enemy.print_limiter.can_print(f"enemy_{enemy.enemy_id}_damage_ignored_handler", limit=3): # Use enemy's limiter
        #     print(f"DEBUG Enemy {enemy.enemy_id} (CombatHandler): Damage IGNORED due to state/cooldown.")
        return

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health) # Clamp health at 0 (cannot be negative)

    # if enemy.print_limiter.can_print(f"enemy_{enemy.enemy_id}_health_update_handler", limit=5):
    #     print(f"DEBUG Enemy {enemy.enemy_id} (CombatHandler): Took {damage_amount} damage. New HP: {enemy.current_health}/{enemy.max_health}")

    if enemy.current_health <= 0: # Health has reached zero or below
        if not enemy.is_dead: # If not already marked as dead, transition to death state
            enemy.set_state('death') # This will trigger death animation and logic in Enemy class
    else: # Enemy is damaged but still alive
        # Transition to 'hit' state to show visual feedback and potentially interrupt actions,
        # but only if not already in a 'hit' state during its active stun duration.
        # ENEMY_HIT_STUN_DURATION is the duration the enemy is stunned and in 'hit' anim.
        # ENEMY_HIT_COOLDOWN is total invincibility time, which might be longer.
        if not (enemy.state == 'hit' and current_time_ms - enemy.state_timer < getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)):
             enemy.set_state('hit') # Trigger hit animation and stun period