# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles player combat: attacks, damage dealing/taking, healing, and projectile firing.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C
from projectiles import Fireball # Needed for instantiating Fireball

def fire_player_fireball(player):
    """
    Handles the logic for the player instance firing a fireball.
    Checks cooldowns, determines spawn position and direction, and adds
    the fireball to appropriate sprite groups.

    Args:
        player (Player): The player instance attempting to fire.
    """
    # Basic validation: Player must be valid, alive, and have sprite group references
    if not player._valid_init or player.is_dead or not player.alive():
        return
    if player.projectile_sprites_group is None or player.all_sprites_group is None:
        if player.print_limiter.can_print(f"player_{player.player_id}_fireball_no_group_ref_handler"):
            # Use a unique key for PrintLimiter to avoid message collision
            print(f"Player {player.player_id} (CombatHandler): Cannot fire fireball, projectile/all_sprites group not set.")
        return

    current_time_ms = pygame.time.get_ticks()
    # Check if fireball is off cooldown
    if current_time_ms - player.fireball_cooldown_timer >= C.FIREBALL_COOLDOWN:
        player.fireball_cooldown_timer = current_time_ms # Reset cooldown timer

        # Determine fireball spawn position relative to player
        spawn_x = player.rect.centerx
        spawn_y = player.rect.centery 
        
        # Use the player's last stored aim direction for the fireball
        current_aim_direction = player.fireball_last_input_dir.copy()
        # Ensure the aim direction has a non-zero length (fallback to facing direction)
        if current_aim_direction.length_squared() == 0: 
            current_aim_direction.x = 1.0 if player.facing_right else -1.0
            current_aim_direction.y = 0.0
        
        # Calculate an offset for the fireball's spawn point so it appears slightly in front of the player
        # This helps prevent immediate self-collision or spawning inside walls.
        # Tuned offset value; may need adjustment based on player/fireball sprite sizes.
        offset_distance = (player.rect.width / 2) + (C.FIREBALL_DIMENSIONS[0] / 2) - 35 
        
        # If aiming significantly up or down, adjust offset based on height
        if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x): # More vertical than horizontal aim
            offset_distance = (player.rect.height / 2) + (C.FIREBALL_DIMENSIONS[1] / 2) - 35
        
        # Apply the offset in the aim direction
        if current_aim_direction.length_squared() > 0: # Should always be true after fallback
            offset_vector = current_aim_direction.normalize() * offset_distance
            spawn_x += offset_vector.x
            spawn_y += offset_vector.y
        # else: # This case should ideally not be reached due to the fallback above
        #    spawn_x += (1.0 if player.facing_right else -1.0) * offset_distance

        # Create the new Fireball instance
        new_fireball = Fireball(spawn_x, spawn_y, current_aim_direction, player)
        # Add the fireball to the game's projectile and all_sprites groups
        player.projectile_sprites_group.add(new_fireball)
        player.all_sprites_group.add(new_fireball)
        
        if player.print_limiter.can_print(f"player_{player.player_id}_fire_fireball_msg_combat_handler"):
            print(f"Player {player.player_id} (CombatHandler) fires fireball. Aim Dir: {current_aim_direction}, Spawn Pos: ({spawn_x:.1f}, {spawn_y:.1f})")
    else: # Fireball is on cooldown
        if player.print_limiter.can_print(f"player_{player.player_id}_fireball_cooldown_combat_handler"):
            print(f"Player {player.player_id} (CombatHandler): Fireball on cooldown.")


def check_player_attack_collisions(player, targets_list):
    """
    Checks for collisions between the player's active attack hitbox and a list of targets.
    Applies damage to targets if a hit is registered.

    Args:
        player (Player): The attacking player instance.
        targets_list (list): A list of potential target Sprites (e.g., enemies, other players).
    """
    # Player must be valid, actively attacking, and alive to deal damage
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive():
        return

    # --- Position the player's attack hitbox based on facing direction and state ---
    if player.facing_right:
        player.attack_hitbox.midleft = player.rect.midright # Hitbox to the right
    else:
        player.attack_hitbox.midright = player.rect.midleft # Hitbox to the left
    
    # Vertically adjust hitbox if crouching and performing a crouch attack
    # (Assuming attack_type 4 is designated for crouch attacks)
    vertical_offset_for_crouch_attack = -10 if player.is_crouching and player.attack_type == 4 else 0
    player.attack_hitbox.centery = player.rect.centery + vertical_offset_for_crouch_attack
    
    current_time_ms = pygame.time.get_ticks()
    for target_sprite in targets_list:
        if target_sprite is player: continue # Player cannot hit themselves with melee attacks

        # Ensure the target is valid, alive, and not dead
        if not (target_sprite and hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and target_sprite.alive()):
            continue

        # --- Check if the target is currently invincible (e.g., recently hit) ---
        target_is_currently_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and \
           hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and \
               (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                target_is_currently_invincible = True
        
        if target_is_currently_invincible:
            continue # Skip this target if it's invincible

        # --- Perform collision check between player's attack hitbox and target's rect ---
        if player.attack_hitbox.colliderect(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                # Determine damage amount based on player's current attack type
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE
                
                if damage_to_inflict > 0:
                    target_sprite.take_damage(damage_to_inflict) # Call target's take_damage method
                    # Optional: Implement logic for one-hit-per-attack-animation if needed.
                    # This could involve a list on the player of targets already hit in this attack swing.
                    # For simplicity, this example allows multiple targets to be hit if they overlap the hitbox
                    # during the attack's active frames. Many games make attacks hit only once or a few targets.
                    
                    # player.can_combo = False # Example: A successful hit might end a combo window,
                                            # or this is managed by the attack animation finishing.


def player_take_damage(player, damage_amount):
    """
    Handles the player instance taking a specified amount of damage.
    Updates health, and potentially triggers 'hit' or 'death' states.

    Args:
        player (Player): The player instance receiving damage.
        damage_amount (int): The amount of damage to inflict.
    """
    current_time_ms = pygame.time.get_ticks()
    # if player.print_limiter.can_print(f"player_{player.player_id}_take_damage_call_combat_handler", limit=10, period=1.0):
    #     print(f"DEBUG Player {player.player_id} (CombatHandler): take_damage({damage_amount}) called. HP: {player.current_health}")
    
    # Player cannot take damage if invalid, already dead, not in sprite groups, or in hit cooldown
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown): 
        # if player.print_limiter.can_print(f"player_{player.player_id}_damage_ignored_combat_handler", limit=3, period=1.0):
        #     print(f"DEBUG Player {player.player_id} (CombatHandler): Damage IGNORED due to state/cooldown.")
        return

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health) # Clamp health at 0

    # if player.print_limiter.can_print(f"player_{player.player_id}_health_update_combat_handler", limit=10, period=1.0):
    #     print(f"DEBUG Player {player.player_id} (CombatHandler): New HP: {player.current_health}/{player.max_health}")

    if player.current_health <= 0: # Health has reached zero or below
        if not player.is_dead: # If not already marked as dead, transition to death state
            player.set_state('death') 
    else: # Player is damaged but still alive
        # Transition to 'hit' state if not already in 'hit' state during its active stun duration
        if not (player.state == 'hit' and current_time_ms - player.state_timer < player.hit_duration):
             player.set_state('hit') # Trigger hit animation and stun

def player_self_inflict_damage(player, damage_amount):
    """
    Allows the player instance to inflict damage on themselves.
    Typically used for debugging or special abilities.

    Args:
        player (Player): The player instance.
        damage_amount (int): The amount of damage for self-infliction.
    """
    if not player._valid_init or player.is_dead or not player.alive(): return # Basic validation
    
    # print(f"Player {player.player_id} (CombatHandler) self-inflicted {damage_amount} damage. HP before: {player.current_health}")
    player_take_damage(player, damage_amount) # Use the standardized take_damage logic
    # print(f"Player {player.player_id} (CombatHandler) HP after self-inflict: {player.current_health}/{player.max_health}")

def player_heal_to_full(player):
    """
    Heals the player instance to their maximum health.
    Can also cancel 'hit' stun state.

    Args:
        player (Player): The player instance to be healed.
    """
    if not player._valid_init: return
    # Cannot heal if fully dead and health is zero (unless game has revival mechanics not shown here)
    if player.is_dead and player.current_health <=0 : return 
    
    player.current_health = player.max_health
    # print(f"Player {player.player_id} (CombatHandler) healed to full: {player.current_health}/{player.max_health}")
    
    # If player was in a 'hit' stun, cancel it by transitioning to idle
    if player.is_taking_hit: player.is_taking_hit = False 
    if player.state == 'hit': player.set_state('idle')