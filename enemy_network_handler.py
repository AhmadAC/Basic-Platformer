########## START OF FILE: enemy_network_handler.py ##########

"""
version 1.0.0.3 (Added aflame/deflame network sync)
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
        'is_dead': enemy.is_dead,
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
        
        # Aflame/Deflame state (New)
        'is_aflame': getattr(enemy, 'is_aflame', False),
        'aflame_timer_start': getattr(enemy, 'aflame_timer_start', 0),
        'is_deflaming': getattr(enemy, 'is_deflaming', False),
        'deflame_timer_start': getattr(enemy, 'deflame_timer_start', 0),
        'has_ignited_another_enemy_this_cycle': getattr(enemy, 'has_ignited_another_enemy_this_cycle', False),
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
    new_is_dead_from_net = network_data.get('is_dead', enemy.is_dead)
    enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)

    # --- Frozen/Defrost State Synchronization ---
    new_is_frozen_net = network_data.get('is_frozen', enemy.is_frozen)
    new_is_defrosting_net = network_data.get('is_defrosting', enemy.is_defrosting)
    net_frozen_effect_timer = network_data.get('frozen_effect_timer', enemy.frozen_effect_timer)

    # --- Aflame/Deflame State Synchronization (New) ---
    new_is_aflame_net = network_data.get('is_aflame', enemy.is_aflame)
    new_is_deflaming_net = network_data.get('is_deflaming', enemy.is_deflaming)
    net_aflame_timer_start = network_data.get('aflame_timer_start', enemy.aflame_timer_start)
    net_deflame_timer_start = network_data.get('deflame_timer_start', enemy.deflame_timer_start)
    enemy.has_ignited_another_enemy_this_cycle = network_data.get('has_ignited_another_enemy_this_cycle', enemy.has_ignited_another_enemy_this_cycle)


    # Priority of status effects: Aflame > Frozen > Normal
    if new_is_aflame_net and not enemy.is_aflame:
        enemy.is_aflame = True; enemy.is_deflaming = False
        enemy.aflame_timer_start = net_aflame_timer_start
        enemy.is_frozen = False; enemy.is_defrosting = False # Aflame overrides freeze
        enemy.set_state('aflame')
    elif not new_is_aflame_net and enemy.is_aflame:
        enemy.is_aflame = False

    if new_is_deflaming_net and not enemy.is_deflaming:
        enemy.is_deflaming = True; enemy.is_aflame = False # Deflaming means not aflame
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
            
        # If server says not under any major status, ensure local flags are cleared
        if not new_is_frozen_net and not new_is_defrosting_net:
            enemy.is_frozen = False; enemy.is_defrosting = False

    # If server says not aflame AND not deflaming AND not frozen AND not defrosting, clear all flags
    if not new_is_aflame_net and not new_is_deflaming_net and not new_is_frozen_net and not new_is_defrosting_net:
        enemy.is_aflame = False; enemy.is_deflaming = False
        enemy.is_frozen = False; enemy.is_defrosting = False
        if enemy.state in ['aflame', 'deflame', 'frozen', 'defrost'] and network_data.get('state', enemy.state) not in ['aflame', 'deflame', 'frozen', 'defrost']:
             enemy.set_state(network_data.get('state', 'idle'))


    # Stomp Death Handling
    new_is_stomp_dying_from_net = network_data.get('is_stomp_dying', False)
    if new_is_stomp_dying_from_net and not enemy.is_stomp_dying:
        enemy.is_stomp_dying = True
        enemy.stomp_death_start_time = network_data.get('stomp_death_start_time', pygame.time.get_ticks())
        enemy.original_stomp_facing_right = network_data.get('original_stomp_facing_right', enemy.facing_right)
        
        original_facing = enemy.facing_right
        enemy.facing_right = enemy.original_stomp_facing_right
        _temp_stomp_flag = enemy.is_stomp_dying
        enemy.is_stomp_dying = False
        enemy.animate() 
        enemy.is_stomp_dying = _temp_stomp_flag 
        enemy.original_stomp_death_image = enemy.image.copy()
        enemy.facing_right = original_facing 

        enemy.is_dead = True; enemy.current_health = 0
        enemy.vel.xy = 0,0; enemy.acc.xy = 0,0
        enemy.death_animation_finished = False 
        enemy.state = 'stomp_death' 
        enemy.is_frozen = False; enemy.is_defrosting = False 
        enemy.is_aflame = False; enemy.is_deflaming = False # Stomp overrides fire/freeze

    elif not new_is_stomp_dying_from_net and enemy.is_stomp_dying: 
        enemy.is_stomp_dying = False
        enemy.original_stomp_death_image = None

    # Regular Death Status (only if not under a priority status effect)
    if not enemy.is_stomp_dying and not enemy.is_frozen and not enemy.is_defrosting and not enemy.is_aflame and not enemy.is_deflaming:
        if new_is_dead_from_net and not enemy.is_dead: 
            enemy.is_dead = True; enemy.current_health = 0 
            enemy.set_state('death') 
        elif not new_is_dead_from_net and enemy.is_dead: 
            enemy.is_dead = False; enemy.death_animation_finished = False 
            if enemy.state in ['death', 'death_nm', 'stomp_death']: 
                enemy.set_state('idle') 
        else: 
            enemy.is_dead = new_is_dead_from_net 

    # Combat and Action States (only if not under a priority status effect)
    if not enemy.is_stomp_dying and not enemy.is_frozen and not enemy.is_defrosting and not enemy.is_aflame and not enemy.is_deflaming:
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
        
        new_logical_state_from_net = network_data.get('state', enemy.state)
        # Only set state if it's truly different and not a priority override state
        is_priority_state = enemy.state in ['stomp_death', 'frozen', 'defrost', 'aflame', 'deflame']
        if not is_priority_state and enemy.state != new_logical_state_from_net and \
           not (enemy.is_dead and new_logical_state_from_net in ['death', 'death_nm']):
             enemy.set_state(new_logical_state_from_net)
        else: 
            enemy.current_frame = network_data.get('current_frame', enemy.current_frame)
            enemy.last_anim_update = network_data.get('last_anim_update', enemy.last_anim_update)
    
    enemy.rect.midbottom = (round(enemy.pos.x), round(enemy.pos.y)) 
    
    if enemy._valid_init and enemy.alive(): 
        enemy.animate() 