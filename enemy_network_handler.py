# enemy_network_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles network-related data serialization and deserialization for the Enemy class.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import constants as C # For any network-specific constants if needed in future

def get_enemy_network_data(enemy):
    """
    Gathers essential enemy data into a dictionary for network transmission.
    This is typically called by the server to send enemy states to clients.

    Args:
        enemy (Enemy): The enemy instance whose data is being serialized.

    Returns:
        dict: A dictionary containing the enemy's network-relevant state.
    """
    # Ensure all serialized values are basic Python types for JSON compatibility
    data = {
        'enemy_id': enemy.enemy_id, # Crucial for identifying the enemy across network
        '_valid_init': enemy._valid_init, # Client needs to know if this enemy is valid
        
        'pos': (enemy.pos.x, enemy.pos.y), 
        'vel': (enemy.vel.x, enemy.vel.y), 
        'facing_right': enemy.facing_right, 
        
        'state': enemy.state, # Current logical state (e.g., 'idle', 'run', 'attack_nm')
        'current_frame': enemy.current_frame, 
        'last_anim_update': enemy.last_anim_update, # Timestamp for animation synchronization
        
        'current_health': enemy.current_health, 
        'is_dead': enemy.is_dead,
        'death_animation_finished': enemy.death_animation_finished,
        
        'is_attacking': enemy.is_attacking, 
        'attack_type': enemy.attack_type, # If enemies have different attack types
        # 'attack_timer': enemy.attack_timer, # Potentially useful for client-side prediction of attack end
        # 'attack_duration': enemy.attack_duration, # Also for prediction
        
        'is_taking_hit': enemy.is_taking_hit, # To sync hit stun visuals/invincibility
        # 'hit_timer': enemy.hit_timer, # For clients to potentially predict end of hit stun

        'post_attack_pause_timer': enemy.post_attack_pause_timer, # For syncing post-attack behavior

        # Optional: Send AI state if clients need to visualize or react to it,
        # though usually AI is server-authoritative and clients just see the results (movement, attacks).
        # 'ai_state': enemy.ai_state, 
        
        # Send color_name so clients can load the correct colored enemy assets
        'color_name': getattr(enemy, 'color_name', 'default_color') # Fallback if not present
    }
    return data

def set_enemy_network_data(enemy, network_data): 
    """
    Applies received network data to update the local enemy instance's state.
    This is primarily used on clients to reflect the server's authoritative state for each enemy.

    Args:
        enemy (Enemy): The enemy instance to be updated.
        network_data (dict): The dictionary of enemy state received over the network.
    """
    if network_data is None: return # No data to apply
    
    # --- Critical: Update _valid_init first ---
    # If the server says this enemy is no longer valid, remove it or mark it.
    # This is important if an enemy is dynamically removed by the server.
    enemy._valid_init = network_data.get('_valid_init', enemy._valid_init)
    if not enemy._valid_init:
        if enemy.alive(): # If the enemy sprite was in any groups
            enemy.kill()  # Remove from all groups
        return # No further updates if enemy is marked invalid by network

    # --- Update core physical attributes ---
    pos_data = network_data.get('pos')
    if pos_data: enemy.pos.x, enemy.pos.y = pos_data
    
    vel_data = network_data.get('vel')
    if vel_data: enemy.vel.x, enemy.vel.y = vel_data
    
    enemy.facing_right = network_data.get('facing_right', enemy.facing_right)
    
    # --- Update health and death status ---
    # Health is authoritative from server
    enemy.current_health = network_data.get('current_health', enemy.current_health)
    new_is_dead_from_net = network_data.get('is_dead', enemy.is_dead)
    enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)

    # --- Handle transitions related to death status, ensuring animations are triggered ---
    if new_is_dead_from_net and not enemy.is_dead: # Enemy was alive, network says it's dead
        enemy.is_dead = True
        enemy.current_health = 0 # Ensure health is zero if dead
        enemy.set_state('death') # Trigger death state logic (animation, physics changes)
    elif not new_is_dead_from_net and enemy.is_dead: # Enemy was dead, network says it's alive (e.g., server reset an enemy)
        enemy.is_dead = False
        enemy.death_animation_finished = False # Reset this flag
        if enemy.state in ['death', 'death_nm']: # If stuck in a death animation state
            enemy.set_state('idle') # Transition to a neutral, alive state
    else: # No change in is_dead status, or local already matches network
        enemy.is_dead = new_is_dead_from_net # Ensure local is_dead matches network

    # --- Update combat and action states ---
    enemy.is_attacking = network_data.get('is_attacking', enemy.is_attacking)
    enemy.attack_type = network_data.get('attack_type', enemy.attack_type)
    # enemy.attack_timer = network_data.get('attack_timer', enemy.attack_timer) # If sent
    # enemy.attack_duration = network_data.get('attack_duration', enemy.attack_duration) # If sent
    
    # Update hit stun state: if network says enemy is taking a hit, reflect that
    new_is_taking_hit_from_net = network_data.get('is_taking_hit', enemy.is_taking_hit)
    if new_is_taking_hit_from_net and not enemy.is_taking_hit: # Start of hit stun based on network
        enemy.is_taking_hit = True
        enemy.hit_timer = pygame.time.get_ticks() # Reset local hit timer for visual/cooldown purposes
        if enemy.state != 'hit' and not enemy.is_dead: enemy.set_state('hit') # Trigger hit anim if not already
    elif not new_is_taking_hit_from_net and enemy.is_taking_hit: # End of hit stun by network
        enemy.is_taking_hit = False
        if enemy.state == 'hit' and not enemy.is_dead: enemy.set_state('idle') # Transition out of hit anim

    enemy.post_attack_pause_timer = network_data.get('post_attack_pause_timer', enemy.post_attack_pause_timer)
    
    # --- Update logical state and animation frame/timestamp for smooth visuals ---
    new_logical_state_from_net = network_data.get('state', enemy.state)
    # Apply new state if different, carefully avoiding re-triggering death anim if already in it
    if enemy.state != new_logical_state_from_net and \
       not (enemy.is_dead and new_logical_state_from_net in ['death', 'death_nm']):
         enemy.set_state(new_logical_state_from_net) # This will reset current_frame and last_anim_update
    else: # If state is the same, or it's a death state, just sync animation details
        enemy.current_frame = network_data.get('current_frame', enemy.current_frame)
        enemy.last_anim_update = network_data.get('last_anim_update', enemy.last_anim_update)
    
    # Sync color_name (important if enemies can change appearance or if client creates them based on net data)
    # This assumes the Enemy class can handle a color change if its assets are structured that way.
    # If color_name only matters at init, this might not be needed here unless an enemy could transform.
    # network_color_name = network_data.get('color_name')
    # if network_color_name and hasattr(enemy, 'color_name') and enemy.color_name != network_color_name:
    #     enemy.color_name = network_color_name
    #     # Potentially trigger a reload of animations if color change means different spritesheets
    #     # enemy.animations = load_all_player_animations(relative_asset_folder=f"characters/{enemy.color_name}")
    #     # This part is complex and depends heavily on how your assets are structured.
    
    # --- Finalize visual position and trigger animation update ---
    enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y)) # Update visual position
    
    # Ensure animation is updated if enemy is valid and part of the game world
    if enemy._valid_init and enemy.alive(): # alive() checks if the sprite is in any groups
        enemy.animate()