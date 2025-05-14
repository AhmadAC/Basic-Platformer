########## START OF FILE: enemy_network_handler.py ##########

# enemy_network_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.2 (Updated stomp death networking and client-side image capture)
Handles network-related data serialization and deserialization for the Enemy class.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import constants as C # For any network-specific constants if needed in future
from assets import load_all_player_animations # For client-side enemy animation loading if color changes
import os # For os.path.join if needed for color sync (though GSM usually handles enemy creation)

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
        'enemy_id': enemy.enemy_id, 
        '_valid_init': enemy._valid_init, 
        
        'pos': (enemy.pos.x, enemy.pos.y), 
        'vel': (enemy.vel.x, enemy.vel.y), 
        'facing_right': enemy.facing_right, 
        
        'state': enemy.state, 
        'current_frame': enemy.current_frame, 
        'last_anim_update': enemy.last_anim_update, 
        
        'current_health': enemy.current_health, 
        'is_dead': enemy.is_dead,
        'death_animation_finished': enemy.death_animation_finished,
        
        'is_attacking': enemy.is_attacking, 
        'attack_type': enemy.attack_type, 
        
        'is_taking_hit': enemy.is_taking_hit, 
        'post_attack_pause_timer': enemy.post_attack_pause_timer, 
        'color_name': getattr(enemy, 'color_name', 'default_color'),

        # Stomp death specific fields
        'is_stomp_dying': getattr(enemy, 'is_stomp_dying', False), # Add getattr for safety
        'stomp_death_start_time': getattr(enemy, 'stomp_death_start_time', 0),
        'original_stomp_facing_right': getattr(enemy, 'original_stomp_facing_right', True),
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
    if network_data is None: return 
    
    enemy._valid_init = network_data.get('_valid_init', enemy._valid_init)
    if not enemy._valid_init:
        if enemy.alive(): enemy.kill()  
        return 

    pos_data = network_data.get('pos')
    if pos_data: enemy.pos.x, enemy.pos.y = pos_data
    
    vel_data = network_data.get('vel')
    if vel_data: enemy.vel.x, enemy.vel.y = vel_data
    
    enemy.facing_right = network_data.get('facing_right', enemy.facing_right) # General facing
    
    enemy.current_health = network_data.get('current_health', enemy.current_health)
    new_is_dead_from_net = network_data.get('is_dead', enemy.is_dead)
    enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)

    # Stomp Death Handling
    new_is_stomp_dying_from_net = network_data.get('is_stomp_dying', False)
    if new_is_stomp_dying_from_net and not enemy.is_stomp_dying:
        enemy.is_stomp_dying = True
        enemy.stomp_death_start_time = network_data.get('stomp_death_start_time', pygame.time.get_ticks())
        # Use the server's facing direction at the moment of stomp for visual consistency
        enemy.original_stomp_facing_right = network_data.get('original_stomp_facing_right', enemy.facing_right)
        
        # Client needs to capture its current image (correctly oriented) as the base for scaling.
        # Ensure the enemy's state, frame, and facing are consistent with what the server *would have seen*
        # at the moment it decided to stomp_kill.
        # The server's `get_enemy_network_data` sends `state`, `current_frame`, and `facing_right`.
        # These should be applied *before* this stomp logic if they're part of the same network packet.
        
        # Temporarily set facing_right for image capture to match the server's view at stomp time
        original_facing = enemy.facing_right
        enemy.facing_right = enemy.original_stomp_facing_right
        
        # Animate once to get the correct base frame.
        # Temporarily disable stomp_dying during this animate call to ensure it uses regular animation logic.
        _temp_stomp_flag = enemy.is_stomp_dying
        enemy.is_stomp_dying = False
        enemy.animate() # This should set self.image based on current_frame and new facing_right
        enemy.is_stomp_dying = _temp_stomp_flag # Restore flag

        enemy.original_stomp_death_image = enemy.image.copy()
        enemy.facing_right = original_facing # Restore actual facing direction for subsequent logic if needed

        # Update other death-related states
        enemy.is_dead = True
        enemy.current_health = 0
        enemy.vel.xy = 0,0
        enemy.acc.xy = 0,0
        enemy.death_animation_finished = False # Stomp animation will handle this
        enemy.state = 'stomp_death' # Can be useful for client-side logic, though animation handles visual

    elif not new_is_stomp_dying_from_net and enemy.is_stomp_dying: # Stomp death ended/cancelled
        enemy.is_stomp_dying = False
        enemy.original_stomp_death_image = None
        # If the enemy is now considered alive by the server, the regular death logic below will handle it.

    # Regular Death Status (only if not currently stomp_dying)
    if not enemy.is_stomp_dying:
        if new_is_dead_from_net and not enemy.is_dead: 
            enemy.is_dead = True
            enemy.current_health = 0 
            enemy.set_state('death') 
        elif not new_is_dead_from_net and enemy.is_dead: # Revived
            enemy.is_dead = False
            enemy.death_animation_finished = False 
            if enemy.state in ['death', 'death_nm', 'stomp_death']: # Check stomp_death too
                enemy.set_state('idle') 
        else: 
            enemy.is_dead = new_is_dead_from_net 

    # Combat and Action States (only if not currently stomp_dying)
    if not enemy.is_stomp_dying:
        enemy.is_attacking = network_data.get('is_attacking', enemy.is_attacking)
        enemy.attack_type = network_data.get('attack_type', enemy.attack_type)
        
        new_is_taking_hit_from_net = network_data.get('is_taking_hit', enemy.is_taking_hit)
        if new_is_taking_hit_from_net and not enemy.is_taking_hit: 
            enemy.is_taking_hit = True
            enemy.hit_timer = pygame.time.get_ticks() 
            if enemy.state != 'hit' and not enemy.is_dead: enemy.set_state('hit') 
        elif not new_is_taking_hit_from_net and enemy.is_taking_hit: 
            enemy.is_taking_hit = False
            if enemy.state == 'hit' and not enemy.is_dead: enemy.set_state('idle') 

        enemy.post_attack_pause_timer = network_data.get('post_attack_pause_timer', enemy.post_attack_pause_timer)
        
        # Logical State (if not stomp_dying, as stomp_death state is managed above)
        new_logical_state_from_net = network_data.get('state', enemy.state)
        if enemy.state != 'stomp_death' and enemy.state != new_logical_state_from_net and \
           not (enemy.is_dead and new_logical_state_from_net in ['death', 'death_nm']):
             enemy.set_state(new_logical_state_from_net)
        else: # If state is the same, or it's a death/stomp_death state, just sync animation details
            enemy.current_frame = network_data.get('current_frame', enemy.current_frame)
            enemy.last_anim_update = network_data.get('last_anim_update', enemy.last_anim_update)
    
    enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y)) 
    
    if enemy._valid_init and enemy.alive(): 
        enemy.animate() # This will correctly handle stomp animation if is_stomp_dying is true