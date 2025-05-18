# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.3 (Allow movement during hit stun if on fire)
Handles player combat: attacks, damage dealing/taking, healing, and projectile firing.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C
from projectiles import Fireball # Needed for instantiating Fireball (though firing is in player.py)
from statue import Statue # Import Statue to check instance type

try:
    from logger import debug, info # Assuming these are sufficient for this module
except ImportError:
    def debug(msg): print(f"DEBUG_PCOMBAT: {msg}")
    def info(msg): print(f"INFO_PCOMBAT: {msg}")

# Note: Firing logic for projectiles like fireball is now directly in Player class (_generic_fire_projectile)
# This module focuses on hit detection and damage application.

def check_player_attack_collisions(player, targets_list):
    """
    Checks if the player's current attack hits any target in the list.
    Applies damage to the target if a hit is registered.
    Targets can be Enemies or Statues.

    Args:
        player (Player): The attacking player instance.
        targets_list (list): A list of Sprites (Enemies, other Players, Statues) to check against.
    """
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive() or player.is_petrified:
        return

    # Position the attack hitbox based on facing direction and crouch state
    if player.facing_right:
        player.attack_hitbox.midleft = player.rect.midright
    else:
        player.attack_hitbox.midright = player.rect.midleft

    # Adjust hitbox vertical position if crouching and doing a crouch attack
    vertical_offset_for_crouch_attack = 0
    if player.is_crouching and player.attack_type == 4: # Assuming attack_type 4 is crouch_attack
        # Example: Lower the hitbox slightly for a crouch attack. Adjust as needed.
        vertical_offset_for_crouch_attack = 10 # Pixels downwards
    player.attack_hitbox.centery = player.rect.centery + vertical_offset_for_crouch_attack

    current_time_ms = pygame.time.get_ticks()

    for target_sprite in targets_list:
        if target_sprite is player: # Player cannot hit themselves with melee
            continue

        is_statue = isinstance(target_sprite, Statue)

        # --- Logic for hitting Statues ---
        if is_statue:
            if player.attack_hitbox.colliderect(target_sprite.rect):
                if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                    # Determine damage based on player's attack type
                    damage_to_inflict_on_statue = 0
                    if player.attack_type == 1: damage_to_inflict_on_statue = C.PLAYER_ATTACK1_DAMAGE
                    elif player.attack_type == 2: damage_to_inflict_on_statue = C.PLAYER_ATTACK2_DAMAGE
                    elif player.attack_type == 3: damage_to_inflict_on_statue = C.PLAYER_COMBO_ATTACK_DAMAGE
                    elif player.attack_type == 4: damage_to_inflict_on_statue = C.PLAYER_CROUCH_ATTACK_DAMAGE
                    
                    if damage_to_inflict_on_statue > 0:
                        debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Statue {target_sprite.statue_id} for {damage_to_inflict_on_statue} damage.")
                        target_sprite.take_damage(damage_to_inflict_on_statue)
                        # Attack might hit one statue and stop, or continue. For now, assume one hit per attack action.
                        # If attack should continue, remove this 'continue' or 'return'.
            continue # Move to next target if current was a statue (whether hit or not)

        # --- Existing logic for hitting other characters (Enemies, other Players) ---
        if not (target_sprite and hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and target_sprite.alive()):
            continue # Skip invalid or already "dead" (non-petrified) targets

        # Check invincibility (hit cooldown)
        target_is_currently_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and \
           hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and \
               (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                target_is_currently_invincible = True
        
        if target_is_currently_invincible:
            continue

        if getattr(target_sprite, 'is_petrified', False) and not getattr(target_sprite, 'is_stone_smashed', False):
            # If target is petrified (but not yet smashed), player attacks should "smash" it.
            if player.attack_hitbox.colliderect(target_sprite.rect):
                 if hasattr(target_sprite, 'smash_petrification') and callable(target_sprite.smash_petrification):
                    debug(f"Player {player.player_id} hit petrified target {getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))}. Smashing.")
                    target_sprite.smash_petrification()
            continue # Processed petrified target


        if player.attack_hitbox.colliderect(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                # Determine damage based on player's attack type
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE
                
                if damage_to_inflict > 0:
                    target_id_log = getattr(target_sprite, 'player_id', getattr(target_sprite, 'enemy_id', 'Unknown'))
                    debug(f"Player {player.player_id} (AttackType {player.attack_type}) hit Target {target_id_log} for {damage_to_inflict} damage.")
                    target_sprite.take_damage(damage_to_inflict)
                    # Optional: if one attack can hit multiple targets, don't break/return.
                    # For now, assume one successful hit per check_player_attack_collisions call for simplicity,
                    # but player's attack animation might still be active.
                    # The player's 'is_attacking' flag manages how long the hitbox is active.


def player_take_damage(player, damage_amount):
    """
    Handles the player instance taking a specified amount of damage.
    Updates health, and potentially triggers 'hit' or 'death' states.
    If player is on fire, 'hit' state is not set, but damage and cooldown apply.

    Args:
        player (Player): The player instance receiving damage.
        damage_amount (int): The amount of damage to inflict.
    """
    current_time_ms = pygame.time.get_ticks()
    player_id_log = f"P{player.player_id}"
    
    # Check if player is immune to damage (e.g., already dead, in hit cooldown, petrified)
    if not player._valid_init or player.is_dead or not player.alive(): return
    if player.is_petrified: # Includes smashed state, which is also is_dead
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player is petrified/smashed.")
        return
    if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_cooldown): 
        debug(f"PlayerCombatHandler ({player_id_log}): Take damage ({damage_amount}) ignored, player in hit cooldown.")
        return
    # If frozen or defrosting, typically damage might be ignored or have special rules (e.g., shatter)
    # For now, let's assume frozen/defrosting players can still take damage that might break them out or kill them.

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health) # Clamp health at 0
    debug(f"PlayerCombatHandler ({player_id_log}): Took {damage_amount} damage. Health: {player.current_health}/{player.max_health}")

    player.is_taking_hit = True # Always grant invulnerability window after taking a hit
    player.hit_timer = current_time_ms # Start timer for hit cooldown

    if player.current_health <= 0: 
        if not player.is_dead: # Ensure death state is only set once
            debug(f"PlayerCombatHandler ({player_id_log}): Health <= 0. Setting state to 'death'.")
            player.set_state('death') # Use the state handler
    else: # Player is damaged but not dead
        # If player is visually on fire, they remain visually on fire but still get the hit invulnerability.
        # The 'hit' animation is usually a flinch; on fire, they continue burning.
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        
        if not is_in_fire_visual_state:
            # Only transition to 'hit' state if not currently in a fire animation.
            # The player.is_taking_hit flag itself provides the brief invulnerability.
            # The 'hit' state is for the visual flinch animation.
            if player.state != 'hit': # If not already in hit state from a very recent hit
                 player.set_state('hit') # Use the state handler
        else:
            if player.print_limiter.can_print(f"player_hit_while_on_fire_{player.player_id}"):
                debug(f"PlayerCombatHandler ({player_id_log}): Took damage while on fire. State remains '{player.state}'. is_taking_hit=True (for invulnerability).")


def player_self_inflict_damage(player, damage_amount): # For debug keys primarily
    """Allows the player to inflict damage upon themselves."""
    if not player._valid_init or player.is_dead or not player.alive():
        return
    # Self-inflicted damage should probably bypass normal hit cooldown for debug purposes
    # Call player_take_damage but it handles its own cooldown logic if needed.
    player_take_damage(player, damage_amount)


def player_heal_to_full(player): # For debug keys or chest item
    """Heals the player to their maximum health."""
    if not player._valid_init:
        return
    
    # Cannot heal if petrified or smashed (effectively dead in a way that healing doesn't reverse)
    if player.is_petrified or player.is_stone_smashed:
        debug(f"PlayerCombatHandler (P{player.player_id}): Cannot heal, player is petrified/smashed.")
        return

    # If "truly" dead (not just petrified), healing might revive them or just set health for a reset.
    # For now, let's assume healing implies they are not in a permanent death state.
    if player.is_dead and player.current_health <=0 :
        # If we want healing to revive from normal death, this needs more logic.
        # For now, if dead, maybe just set health but don't change 'is_dead' flag here.
        # The game reset logic would handle full revival.
        debug(f"PlayerCombatHandler (P{player.player_id}): Healing a 'dead' player. Setting health, but is_dead status may persist until reset.")

    player.current_health = player.max_health
    debug(f"PlayerCombatHandler (P{player.player_id}): Healed to full health: {player.current_health}/{player.max_health}")

    # If player was in hit stun, clear it as healing implies recovery
    if player.is_taking_hit:
        player.is_taking_hit = False
    
    # If player was visually in 'hit' state and not dead, transition to idle
    if player.state == 'hit' and not player.is_dead:
        player.set_state('idle') # Use state handler