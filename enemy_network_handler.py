# enemy_network_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.4 (Sync petrification flags)
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
        'is_dead': enemy.is_dead, # This will reflect if enemy is "game over" dead (e.g. smashed or regular death)
        'death_animation_finished': enemy.death_animation_finished,
        
        'is_attacking': enemy.is_attacking, 
        'attack_type': enemy.attack_type, 
        
        'is_taking_hit': enemy.is_taking_hit, 
        'post_attack_pause_timer': enemy.post_attack_pause_timer, 
        'color_name': getattr(enemy, 'color_name', 'default_color'),

        'is_stomp_dying': getattr(enemy, 'is_stomp_dying', False), 
        'stomp_death_start_time': getattr(enemy, 'stomp_death_start_time', 0),
        'original_stomp_facing_right': getattr(enemy, 'original_stomp_facing_right', True),

        # Frozen/Defrost state
        'is_frozen': getattr(enemy, 'is_frozen', False),
        'is_defrosting': getattr(enemy, 'is_defrosting', False),
        'frozen_effect_timer': getattr(enemy, 'frozen_effect_timer', 0),
        
        # Aflame/Deflame state
        'is_aflame': getattr(enemy, 'is_aflame', False),
        'aflame_timer_start': getattr(enemy, 'aflame_timer_start', 0),
        'is_deflaming': getattr(enemy, 'is_deflaming', False),
        'deflame_timer_start': getattr(enemy, 'deflame_timer_start', 0),
        'has_ignited_another_enemy_this_cycle': getattr(enemy, 'has_ignited_another_enemy_this_cycle', False),

        # Petrification state
        'is_petrified': getattr(enemy, 'is_petrified', False),
        'is_stone_smashed': getattr(enemy, 'is_stone_smashed', False),
        'stone_smashed_timer_start': getattr(enemy, 'stone_smashed_timer_start', 0),
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
    
    enemy.facing_right = network_data.get('facing_right', enemy.facing_right) 
    
    enemy.current_health = network_data.get('current_health', enemy.current_health)
    # Note: is_dead and death_animation_finished will be set based on petrified/smashed status first,
    # then by regular death status if not petrified.
    
    # --- Petrified State Synchronization (handle this early as it overrides others) ---
    new_is_petrified_net = network_data.get('is_petrified', enemy.is_petrified)
    new_is_smashed_net = network_data.get('is_stone_smashed', enemy.is_stone_smashed)
    net_stone_smashed_timer_start = network_data.get('stone_smashed_timer_start', enemy.stone_smashed_timer_start)
    net_is_dead_for_petrify = network_data.get('is_dead', enemy.is_dead) # Server's overall dead status
    net_death_anim_finished_for_petrify = network_data.get('death_animation_finished', enemy.death_animation_finished)

    state_changed_by_petrify_logic = False

    if new_is_petrified_net:
        if not enemy.is_petrified: # Client wasn't petrified, but server says it is
            enemy.is_petrified = True # Set flag first
            # Apply local side-effects of becoming petrified
            enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
            enemy.is_attacking = False; enemy.attack_type = 0
            enemy.is_taking_hit = False
            enemy.is_frozen = False; enemy.is_defrosting = False
            enemy.is_aflame = False; enemy.is_deflaming = False
            state_changed_by_petrify_logic = True
        
        enemy.is_petrified = True # Ensure it's set

        if new_is_smashed_net:
            if not enemy.is_stone_smashed: # Client was petrified but not smashed, server says smashed
                enemy.is_stone_smashed = True
                state_changed_by_petrify_logic = True
            enemy.is_dead = net_is_dead_for_petrify # Smashed means it's game-over dead
            enemy.death_animation_finished = net_death_anim_finished_for_petrify
            enemy.stone_smashed_timer_start = net_stone_smashed_timer_start
            enemy.set_state('smashed') # This will also handle animation
        else: # Petrified but not smashed
            if enemy.is_stone_smashed: # Client was smashed, but server says only petrified (e.g. error or complex rollback)
                enemy.is_stone_smashed = False
                state_changed_by_petrify_logic = True
            # For unsmashed petrified, is_dead is False by new logic, health is > 0
            # Server should send is_dead = False if it's just petrified with health.
            enemy.is_dead = net_is_dead_for_petrify 
            enemy.set_state('petrified') # This will also handle animation

    elif enemy.is_petrified: # Client is petrified, but server says it's not (e.g. reset)
        enemy.is_petrified = False
        enemy.is_stone_smashed = False
        state_changed_by_petrify_logic = True
        # is_dead will be handled by general death sync below if not petrified
        # This usually means it's resetting to 'idle' or another normal state
        
    # If state was set by petrify/smash logic, it might have handled is_dead.
    # Sync overall is_dead status from server, especially if not petrified.
    enemy.is_dead = network_data.get('is_dead', enemy.is_dead)
    enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)


    # --- Aflame/Frozen/Stomp logic (only if NOT petrified) ---
    if not enemy.is_petrified:
        # Frozen/Defrost State Synchronization
        new_is_frozen_net = network_data.get('is_frozen', enemy.is_frozen)
        new_is_defrosting_net = network_data.get('is_defrosting', enemy.is_defrosting)
        net_frozen_effect_timer = network_data.get('frozen_effect_timer', enemy.frozen_effect_timer)

        # Aflame/Deflame State Synchronization
        new_is_aflame_net = network_data.get('is_aflame', enemy.is_aflame)
        new_is_deflaming_net = network_data.get('is_deflaming', enemy.is_deflaming)
        net_aflame_timer_start = network_data.get('aflame_timer_start', enemy.aflame_timer_start)
        net_deflame_timer_start = network_data.get('deflame_timer_start', enemy.deflame_timer_start)
        enemy.has_ignited_another_enemy_this_cycle = network_data.get('has_ignited_another_enemy_this_cycle', enemy.has_ignited_another_enemy_this_cycle)

        # Priority: Aflame > Frozen > Normal
        if new_is_aflame_net and not enemy.is_aflame:
            enemy.is_aflame = True; enemy.is_deflaming = False
            enemy.aflame_timer_start = net_aflame_timer_start
            enemy.is_frozen = False; enemy.is_defrosting = False 
            enemy.set_state('aflame')
        elif not new_is_aflame_net and enemy.is_aflame:
            enemy.is_aflame = False

        if new_is_deflaming_net and not enemy.is_deflaming:
            enemy.is_deflaming = True; enemy.is_aflame = False 
            enemy.deflame_timer_start = net_deflame_timer_start
            enemy.is_frozen = False; enemy.is_defrosting = False
            enemy.set_state('deflame')
        elif not new_is_deflaming_net and enemy.is_deflaming:
            enemy.is_deflaming = False

        # If not aflame or deflaming, then check frozen status
        if not (new_is_aflame_net or new_is_deflaming_net):
            if new_is_frozen_net and not enemy.is_frozen:
                enemy.is_frozen = True; enemy.is_defrosting = False
                enemy.frozen_effect_timer = net_frozen_effect_timer
                enemy.set_state('frozen')
            elif not new_is_frozen_net and enemy.is_frozen:
                enemy.is_frozen = False

            if new_is_defrosting_net and not enemy.is_defrosting:
                enemy.is_defrosting = True; enemy.is_frozen = False
                enemy.frozen_effect_timer = net_frozen_effect_timer
                enemy.set_state('defrost')
            elif not new_is_defrosting_net and enemy.is_defrosting:
                enemy.is_defrosting = False
                
            if not new_is_frozen_net and not new_is_defrosting_net:
                enemy.is_frozen = False; enemy.is_defrosting = False

        # If server says not under any major status, ensure local flags are cleared
        if not new_is_aflame_net and not new_is_deflaming_net and not new_is_frozen_net and not new_is_defrosting_net:
            enemy.is_aflame = False; enemy.is_deflaming = False
            enemy.is_frozen = False; enemy.is_defrosting = False
            if enemy.state in ['aflame', 'deflame', 'frozen', 'defrost'] and \
               network_data.get('state', enemy.state) not in ['aflame', 'deflame', 'frozen', 'defrost']:
                 enemy.set_state(network_data.get('state', 'idle'))

        # Stomp Death Handling (only if not petrified, aflame, frozen etc.)
        if not (enemy.is_aflame or enemy.is_deflaming or enemy.is_frozen or enemy.is_defrosting):
            new_is_stomp_dying_from_net = network_data.get('is_stomp_dying', False)
            if new_is_stomp_dying_from_net and not enemy.is_stomp_dying:
                enemy.is_stomp_dying = True
                enemy.stomp_death_start_time = network_data.get('stomp_death_start_time', pygame.time.get_ticks())
                enemy.original_stomp_facing_right = network_data.get('original_stomp_facing_right', enemy.facing_right)
                
                # Temporarily set facing for correct original_stomp_death_image generation
                original_facing_for_stomp_img = enemy.facing_right
                enemy.facing_right = enemy.original_stomp_facing_right
                _temp_stomp_flag_for_anim = enemy.is_stomp_dying # Store and restore
                enemy.is_stomp_dying = False # Temporarily unset for clean animate call
                enemy.animate() # Call animate to get the base image for stomp
                enemy.is_stomp_dying = _temp_stomp_flag_for_anim # Restore
                enemy.original_stomp_death_image = enemy.image.copy() # Capture the correctly oriented frame
                enemy.facing_right = original_facing_for_stomp_img # Restore original facing

                enemy.is_dead = True; enemy.current_health = 0 # Stomp kill always sets health to 0
                enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
                enemy.death_animation_finished = False 
                enemy.state = 'stomp_death' 
            elif not new_is_stomp_dying_from_net and enemy.is_stomp_dying: 
                enemy.is_stomp_dying = False
                enemy.original_stomp_death_image = None

        # Regular Death Status (only if not under a priority status effect like stomp/fire/freeze and not petrified)
        if not enemy.is_stomp_dying and not enemy.is_frozen and not enemy.is_defrosting and \
           not enemy.is_aflame and not enemy.is_deflaming:
            
            # is_dead was synced earlier based on petrification.
            # If not petrified, this handles regular death.
            if enemy.is_dead and enemy.state not in ['death', 'death_nm']: # If server says dead, but client state isn't death
                # Health should already be 0 from server if it's a regular death
                enemy.set_state('death') 
            elif not enemy.is_dead and enemy.state in ['death', 'death_nm']: # Server says not dead, but client is in death state
                enemy.death_animation_finished = False # Reset this too
                enemy.set_state('idle') 

    # --- Combat and Action States (only if not under an overriding effect like petrified, stomp, fire, freeze) ---
    if not enemy.is_petrified and not enemy.is_stomp_dying and not enemy.is_frozen and \
       not enemy.is_defrosting and not enemy.is_aflame and not enemy.is_deflaming:
        enemy.is_attacking = network_data.get('is_attacking', enemy.is_attacking)
        enemy.attack_type = network_data.get('attack_type', enemy.attack_type)
        
        new_is_taking_hit_from_net = network_data.get('is_taking_hit', enemy.is_taking_hit)
        if new_is_taking_hit_from_net and not enemy.is_taking_hit: 
            enemy.is_taking_hit = True
            enemy.hit_timer = pygame.time.get_ticks() 
            if enemy.state != 'hit' and not enemy.is_dead : enemy.set_state('hit') 
        elif not new_is_taking_hit_from_net and enemy.is_taking_hit: 
            enemy.is_taking_hit = False
            if enemy.state == 'hit' and not enemy.is_dead : enemy.set_state('idle') 

        enemy.post_attack_pause_timer = network_data.get('post_attack_pause_timer', enemy.post_attack_pause_timer)
        
    # --- Final State and Animation Sync if not set by petrify/smashed logic ---
    if not state_changed_by_petrify_logic:
        new_logical_state_from_net = network_data.get('state', enemy.state)
        # Only set state if it's truly different and current state isn't an overriding one
        # and also not a petrified/smashed state (which were handled above)
        is_priority_override_state = enemy.state in ['stomp_death', 'frozen', 'defrost', 'aflame', 'deflame', 'petrified', 'smashed']
        
        if not is_priority_override_state and enemy.state != new_logical_state_from_net:
            # Also ensure that if enemy.is_dead is true, the new state is a death state
            if not (enemy.is_dead and new_logical_state_from_net not in ['death', 'death_nm']):
                enemy.set_state(new_logical_state_from_net)
        else: # If state is the same or an override, just sync frame and anim time
            enemy.current_frame = network_data.get('current_frame', enemy.current_frame)
            enemy.last_anim_update = network_data.get('last_anim_update', enemy.last_anim_update)
    
    enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y)) 
    
    if enemy._valid_init and enemy.alive(): 
        enemy.animate()