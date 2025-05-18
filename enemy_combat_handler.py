# enemy_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.3 (Corrected was_deflaming_before_hit initialization)
Handles enemy combat mechanics: checking attack collisions and processing damage taken.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import constants as C
from statue import Statue # Import Statue class for type checking

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


def check_enemy_attack_collisions(enemy, hittable_targets_list):
    """
    Checks if the enemy's current attack (if any) hits any target in the list.
    Applies damage to the target if a hit is registered.
    Targets can be Players or Statues.

    Args:
        enemy (Enemy): The attacking enemy instance.
        hittable_targets_list (list): A list of Sprites (Players, Statues) to check for collision.
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

    for target_sprite in hittable_targets_list:
        # --- Logic for hitting Statues ---
        if isinstance(target_sprite, Statue):
            if enemy.attack_hitbox.colliderect(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage) and \
                   not getattr(target_sprite, 'is_smashed', False): # Don't hit already smashed statues
                    damage_to_inflict_on_statue = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                    debug(f"Enemy {enemy.enemy_id} (Color: {enemy.color_name}) hit Statue {target_sprite.statue_id} for {damage_to_inflict_on_statue} damage.")
                    target_sprite.take_damage(damage_to_inflict_on_statue)
                    # Consider if enemy attack should hit multiple targets or stop after one
            continue # Processed statue, move to next target

        # --- Existing logic for hitting Players ---
        # Ensure target_sprite is a valid, alive, non-petrified player not in hit cooldown
        if not (target_sprite and hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and target_sprite.alive()):
            continue

        player_is_currently_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and \
           hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and \
               (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                player_is_currently_invincible = True
        
        if getattr(target_sprite, 'is_petrified', False): # Cannot damage petrified players with normal attacks
            continue

        if player_is_currently_invincible:
            continue

        if enemy.attack_hitbox.colliderect(target_sprite.rect): # target_sprite here is a player
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_inflict_on_player = getattr(C, 'ENEMY_ATTACK_DAMAGE', 10)
                debug(f"Enemy {enemy.enemy_id} (Color: {enemy.color_name}) hit Player {getattr(target_sprite, 'player_id', 'Unknown')} for {damage_to_inflict_on_player} damage.")
                target_sprite.take_damage(damage_to_inflict_on_player)
                # Potentially break after hitting one player, or allow multi-hit
                # For now, assume one hit per attack check for simplicity


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
        debug(f"EnemyCombatHandler ({enemy_id_log}): Take damage ({damage_amount}) ignored, not valid or not alive.")
        return
    if enemy.is_dead and not enemy.is_petrified: # If already undergoing normal death, ignore
        debug(f"EnemyCombatHandler ({enemy_id_log}): Take damage ({damage_amount}) ignored, already in normal death process.")
        return
    if enemy.is_stone_smashed: # If already smashed, ignore
        debug(f"EnemyCombatHandler ({enemy_id_log}): Take damage ({damage_amount}) ignored, already stone_smashed.")
        return
    if enemy.is_taking_hit and (current_time_ms - enemy.hit_timer < enemy.hit_cooldown):
        debug(f"EnemyCombatHandler ({enemy_id_log}): Take damage ({damage_amount}) ignored, in hit cooldown.")
        return
    if enemy.is_frozen or enemy.is_defrosting: # Cannot take damage if frozen/defrosting
        debug(f"EnemyCombatHandler ({enemy_id_log}): Take damage ({damage_amount}) ignored, frozen or defrosting.")
        return

    # --- Apply Damage ---
    was_aflame_before_hit = enemy.is_aflame
    was_deflaming_before_hit = enemy.is_deflaming # Correctly initialized here

    enemy.current_health -= damage_amount
    enemy.current_health = max(0, enemy.current_health) # Clamp health at 0
    debug(f"EnemyCombatHandler ({enemy_id_log}, Color: {enemy.color_name}) took {damage_amount} damage. Health: {enemy.current_health}/{enemy.max_health}. WasAflame: {was_aflame_before_hit}, WasDeflaming: {was_deflaming_before_hit}")

    # --- Handle Petrified Enemy Taking Damage ---
    if enemy.is_petrified: # And not smashed (checked above)
        if enemy.current_health <= 0:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} health reached 0 after damage. Smashing.")
            from enemy_status_effects import smash_petrified_enemy # Local import to avoid circularity if status_effects imports combat_handler
            smash_petrified_enemy(enemy) # This will call set_enemy_state('smashed') via status_effects
        else:
            debug(f"EnemyCombatHandler: Petrified Enemy {enemy_id_log} took damage but health > 0. Remains petrified.")
            enemy.is_taking_hit = True # Still grant invulnerability window
            enemy.hit_timer = current_time_ms
            # No state change to 'hit' if petrified; it remains 'petrified'
        return # Damage to petrified enemy handled, exit function

    # --- Handle Non-Petrified Enemy Taking Damage ---
    enemy.is_taking_hit = True # Grant invulnerability window
    enemy.hit_timer = current_time_ms

    if enemy.current_health <= 0: # Enemy died from this hit
        if not enemy.is_dead: # Ensure death state is only set once
            debug(f"EnemyCombatHandler ({enemy_id_log}): Health <= 0. Setting state to 'death'.")
            set_enemy_state(enemy, 'death') # Use the state handler for proper transition
    else: # Health > 0, enemy is damaged but not dead
        # If the enemy was NOT already on fire (aflame/deflaming), then set to 'hit' state.
        # If it WAS on fire, it remains visually on fire but gets the invulnerability from is_taking_hit.
        if not was_aflame_before_hit and not was_deflaming_before_hit:
            # Only change to 'hit' state if not already in 'hit' from a very recent concurrent hit
            # and the hit cooldown for the *previous* hit has passed (or this is the first hit in a sequence).
            # The primary invulnerability is handled by the `is_taking_hit` flag and `hit_timer`.
            # The 'hit' state is for the visual flinch.
            if enemy.state != 'hit': # If not already in 'hit' state from a previous frame's damage
                debug(f"EnemyCombatHandler ({enemy_id_log}): Health > 0, not aflame/deflaming. Setting state to 'hit'.")
                set_enemy_state(enemy, 'hit') # Use state handler
        else:
            debug(f"EnemyCombatHandler ({enemy_id_log}): Was aflame/deflaming. Took damage, now in hit cooldown, but remains visually aflame/deflaming.")
            # Enemy remains visually aflame/deflaming.
            # The is_taking_hit flag and hit_timer provide invulnerability.
            # The animation handler will prioritize showing aflame/deflame over a 'hit' animation if those flags are true.
            pass