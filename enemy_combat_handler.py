# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.3 (Corrected was_deflaming_before_hit initialization)
Handles enemy combat mechanics: checking attack collisions and processing damage taken.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import constants as C

# Assuming enemy_state_handler.set_enemy_state is available for state transitions
try:
    from enemy_state_handler import set_enemy_state
except ImportError:
    # Fallback if direct import fails (e.g., during early refactoring stages)
    def set_enemy_state(enemy, new_state):
        if hasattr(enemy, 'set_state'): # Check if the old method might still exist on the enemy instance
            enemy.set_state(new_state)
            print(f"ENEMY_COMBAT_HANDLER: Used fallback enemy.set_state for {getattr(enemy, 'enemy_id', 'N/A')}")
        else:
            print(f"CRITICAL ENEMY_COMBAT_HANDLER: enemy_state_handler.set_enemy_state not found for Enemy ID {getattr(enemy, 'enemy_id', 'N/A')}")

# Assuming logger is set up and accessible if you want to use it here
try:
    from logger import debug
except ImportError:
    def debug(msg): print(f"DEBUG_COMBAT_HANDLER: {msg}")


def check_enemy_attack_collisions(enemy, player_target_list):
    """
    Checks if the enemy's current attack (if any) hits any player in the target list.
    Applies damage to the player if a hit is registered.

    Args:
        enemy (Enemy): The attacking enemy instance.
        player_target_list (list): A list of Player sprites to check for collision.
    """
    if enemy.is_frozen or enemy.is_defrosting or enemy.is_petrified: # Prevent attacks if in these states
        return

    if not enemy._valid_init or not enemy.is_attacking or enemy.is_dead or not enemy.alive():
        return

    # Position the attack hitbox based on facing direction
    if enemy.facing_right:
        enemy.attack_hitbox.midleft = enemy.rect.midright
    else:
        enemy.attack_hitbox.midright = enemy.rect.midleft
    enemy.attack_hitbox.centery = enemy.rect.centery # Align vertically with enemy center

    current_time_ms = pygame.time.get_ticks()

    for player_sprite in player_target_list:
        if not (player_sprite and player_sprite._valid_init and \
                not player_sprite.is_dead and player_sprite.alive()):
            continue

        # Check if player is currently invincible (e.g., in hit cooldown from a previous hit)
        player_is_currently_invincible = False
        if hasattr(player_sprite, 'is_taking_hit') and hasattr(player_sprite, 'hit_timer') and \
           hasattr(player_sprite, 'hit_cooldown'):
            if player_sprite.is_taking_hit and \
               (current_time_ms - player_sprite.hit_timer < player_sprite.hit_cooldown):
                player_is_currently_invincible = True
        
        if getattr(player_sprite, 'is_petrified', False): # Cannot damage petrified players with normal attacks
            continue

        if player_is_currently_invincible:
            continue

        if enemy.attack_hitbox.colliderect(player_sprite.rect):
            if hasattr(player_sprite, 'take_damage') and callable(player_sprite.take_damage):
                damage_to_inflict_on_player = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                player_sprite.take_damage(damage_to_inflict_on_player)
                # Potentially break after hitting one player, or allow multi-hit depending on game design
                # For now, assume one hit per attack check for simplicity in this example
                # break


def enemy_take_damage(enemy, damage_amount):
    """
    Handles the enemy instance taking a specified amount of damage.
    Updates health. Triggers invulnerability.
    Sets 'hit' state only if not overridden by a higher-priority visual state like 'aflame'.
    Potentially triggers 'death' or 'smashed' (if petrified) states.
    """
    current_time_ms = pygame.time.get_ticks()
    enemy_id_log = getattr(enemy, 'enemy_id', 'Unknown')

    # --- Initial checks to see if damage should be ignored ---
    if not enemy._valid_init or not enemy.alive():
        debug(f"Enemy {enemy_id_log}: Take damage ({damage_amount}) ignored, not valid or not alive.")
        return
    if enemy.is_dead and not enemy.is_petrified: # If already undergoing normal death, ignore
        debug(f"Enemy {enemy_id_log}: Take damage ({damage_amount}) ignored, already in normal death process.")
        return
    if enemy.is_stone_smashed: # If already smashed, ignore
        debug(f"Enemy {enemy_id_log}: Take damage ({damage_amount}) ignored, already stone_smashed.")
        return
    if enemy.is_taking_hit and (current_time_ms - enemy.hit_timer < enemy.hit_cooldown):
        debug(f"Enemy {enemy_id_log}: Take damage ({damage_amount}) ignored, in hit cooldown.")
        return
    if enemy.is_frozen or enemy.is_defrosting: # Cannot take damage if frozen/defrosting (unless special shatter logic)
        debug(f"Enemy {enemy_id_log}: Take damage ({damage_amount}) ignored, frozen or defrosting.")
        return

    # --- Apply Damage ---
    was_aflame_before_hit = enemy.is_aflame
    was_deflaming_before_hit = enemy.is_deflaming # CORRECTLY INITIALIZED HERE

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health)
    debug(f"Enemy {enemy_id_log} took {damage_amount} damage. Health: {enemy.current_health}. WasAflame: {was_aflame_before_hit}, WasDeflaming: {was_deflaming_before_hit}")

    # --- Handle Petrified Enemy Taking Damage ---
    if enemy.is_petrified: # And not smashed (checked above)
        if enemy.current_health <= 0:
            debug(f"Petrified Enemy {enemy_id_log} health reached 0 after damage. Smashing.")
            from enemy_status_effects import smash_petrified_enemy # Local import
            smash_petrified_enemy(enemy) # This will call set_enemy_state('smashed')
        else:
            debug(f"Petrified Enemy {enemy_id_log} took damage but health > 0. Remains petrified.")
            enemy.is_taking_hit = True
            enemy.hit_timer = current_time_ms
        return # Damage to petrified enemy handled

    # --- Handle Non-Petrified Enemy Taking Damage ---
    enemy.is_taking_hit = True
    enemy.hit_timer = current_time_ms

    if enemy.current_health <= 0:
        if not enemy.is_dead:
            debug(f"Enemy {enemy_id_log}: Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death')
    else: # Health > 0, enemy is not dead
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            if not (enemy.state == 'hit' and current_time_ms - enemy.state_timer < getattr(C, 'ENEMY_HIT_STUN_DURATION', 300)):
                debug(f"Enemy {enemy_id_log}: Health > 0, not aflame/deflaming. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit')
        else:
            debug(f"Enemy {enemy_id_log}: Was aflame/deflaming. Took damage, now in hit cooldown, but remains visually aflame/deflaming.")
            # The enemy remains logically (and should remain visually) aflame/deflaming.
            # The is_taking_hit flag and hit_timer provide invulnerability.
            # Animation handler will prioritize showing aflame/deflame over a 'hit' animation.
            pass