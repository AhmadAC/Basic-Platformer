########## START OF FILE: player_network_handler.py ##########

# player_network_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0000000.1
Handles network-related data serialization, deserialization, and input processing
for the Player class in a networked environment.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C # For potential network-related constants if any

def get_player_network_data(player):
    """
    Gathers essential player data into a dictionary for network transmission.

    Args:
        player (Player): The player instance whose data is being serialized.

    Returns:
        dict: A dictionary containing the player's network-relevant state.
    """
    # Ensure all serialized values are basic Python types (int, float, bool, str, list, dict)
    # Pygame Vector2 needs to be converted to a tuple of floats.
    data = {
        'player_id': player.player_id, 
        '_valid_init': player._valid_init, # Important for client to know if player is valid
        
        'pos': (player.pos.x, player.pos.y), 
        'vel': (player.vel.x, player.vel.y), 
        'facing_right': player.facing_right, 
        
        'state': player.state, # Current logical state string
        'current_frame': player.current_frame, 
        'last_anim_update': player.last_anim_update, # Timestamp for animation sync
        
        'current_health': player.current_health, 
        'is_dead': player.is_dead,
        'death_animation_finished': player.death_animation_finished,
        
        'is_attacking': player.is_attacking, 
        'attack_type': player.attack_type,
        # Add other relevant boolean flags if needed for precise state replication
        'is_crouching': player.is_crouching,
        'is_dashing': player.is_dashing,
        'is_rolling': player.is_rolling,
        'is_sliding': player.is_sliding,
        'on_ladder': player.on_ladder,
        'is_taking_hit': player.is_taking_hit, # To sync hit stun visuals/invincibility
        
        # Fireball aim direction is crucial for remote players to see where fireballs might go
        'fireball_aim_x': player.fireball_last_input_dir.x, 
        'fireball_aim_y': player.fireball_last_input_dir.y
    }
    # print(f"DEBUG PNH (get_player_network_data) for P{player.player_id}: pos={data['pos']}, valid={data['_valid_init']}, alive (instance): {player.alive() if hasattr(player, 'alive') else 'N/A'}") # DEBUG
    return data

def set_player_network_data(player, network_data): 
    """
    Applies received network data to update the local player instance's state.
    This is typically used on clients to reflect the server's authoritative state,
    or on the server to update a remote player's placeholder.

    Args:
        player (Player): The player instance to be updated.
        network_data (dict): The dictionary of player state received over the network.
    """
    if network_data is None:
        # print(f"DEBUG PNH (set_player_network_data) for P{player.player_id}: Received None network_data. No update.") # DEBUG
        return

    # print(f"DEBUG PNH (set_player_network_data) for P{player.player_id}: Applying network data. Current valid: {player._valid_init}, alive: {player.alive() if hasattr(player, 'alive') else 'N/A'}. Net valid: {network_data.get('_valid_init')}, Net pos: {network_data.get('pos')}") # DEBUG
    
    player_id_from_data = network_data.get('player_id', 'Unknown') # For logging

    # Critical: Update _valid_init first.
    new_valid_init = network_data.get('_valid_init', player._valid_init)
    if player._valid_init != new_valid_init:
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: _valid_init changed from {player._valid_init} to {new_valid_init}") # DEBUG
        player._valid_init = new_valid_init
    
    if not player._valid_init:
        if player.alive(): 
            # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Player became invalid, killing sprite.") # DEBUG
            player.kill()  
        return 

    pos_data = network_data.get('pos')
    if pos_data: 
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Old Pos: {player.pos}, New Net Pos: {pos_data}") # DEBUG
        player.pos.x, player.pos.y = pos_data
    
    vel_data = network_data.get('vel')
    if vel_data: player.vel.x, player.vel.y = vel_data
    
    player.facing_right = network_data.get('facing_right', player.facing_right)
    
    player.current_health = network_data.get('current_health', player.current_health)
    new_is_dead_from_net = network_data.get('is_dead', player.is_dead)
    player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)

    if new_is_dead_from_net and not player.is_dead: 
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Transitioning to DEAD from network.") # DEBUG
        player.is_dead = True
        player.current_health = 0 
        player.set_state('death') 
    elif not new_is_dead_from_net and player.is_dead: 
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Transitioning to ALIVE from network (was dead).") # DEBUG
        player.is_dead = False
        player.death_animation_finished = False 
        if player.state in ['death', 'death_nm']: 
            player.set_state('idle') 
    else: 
        player.is_dead = new_is_dead_from_net 

    player.is_attacking = network_data.get('is_attacking', player.is_attacking)
    player.attack_type = network_data.get('attack_type', player.attack_type)
    player.is_crouching = network_data.get('is_crouching', player.is_crouching)
    player.is_dashing = network_data.get('is_dashing', player.is_dashing)
    player.is_rolling = network_data.get('is_rolling', player.is_rolling)
    player.is_sliding = network_data.get('is_sliding', player.is_sliding)
    player.on_ladder = network_data.get('on_ladder', player.on_ladder)
    
    new_is_taking_hit_from_net = network_data.get('is_taking_hit', player.is_taking_hit)
    if new_is_taking_hit_from_net and not player.is_taking_hit: 
        player.is_taking_hit = True
        player.hit_timer = pygame.time.get_ticks() 
        if player.state != 'hit' and not player.is_dead : player.set_state('hit') 
    elif not new_is_taking_hit_from_net and player.is_taking_hit: 
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead : player.set_state('idle') 

    new_logical_state_from_net = network_data.get('state', player.state)
    if player.state != new_logical_state_from_net and \
       not (player.is_dead and new_logical_state_from_net in ['death', 'death_nm']):
         # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Setting state from '{player.state}' to '{new_logical_state_from_net}'") # DEBUG
         player.set_state(new_logical_state_from_net)
    else: 
        player.current_frame = network_data.get('current_frame', player.current_frame)
        player.last_anim_update = network_data.get('last_anim_update', player.last_anim_update)
    
    fb_aim_x_net = network_data.get('fireball_aim_x')
    fb_aim_y_net = network_data.get('fireball_aim_y')
    if fb_aim_x_net is not None and fb_aim_y_net is not None:
        player.fireball_last_input_dir.x = float(fb_aim_x_net)
        player.fireball_last_input_dir.y = float(fb_aim_y_net)
    
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
    # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Updated rect.midbottom to {player.rect.midbottom}") # DEBUG
    
    if player._valid_init and player.alive(): 
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Player valid and alive, calling animate().") # DEBUG
        player.animate()
    # else: # DEBUG
        # print(f"DEBUG PNH (set_player_network_data) for P{player_id_from_data}: Player NOT valid or NOT alive. Valid: {player._valid_init}, Alive: {player.alive() if hasattr(player, 'alive') else 'N/A'}. Skipping animate.") # DEBUG


def handle_player_network_input(player, received_input_data_dict): 
    """
    Processes input data received over the network for this player instance.
    This is used by the server to update a remote player's actions based on
    what their client sent. It's a simplified version of local input processing.

    Args:
        player (Player): The player instance whose actions are being driven by network input.
        received_input_data_dict (dict): The input state dictionary from the client.
    """
    # print(f"DEBUG PNH (handle_player_network_input) for P{player.player_id}: Processing input: {received_input_data_dict}") # DEBUG
    if not player._valid_init or player.is_dead or not player.alive():
        # print(f"DEBUG PNH (handle_player_network_input) for P{player.player_id}: Input ignored, player not valid/alive. Valid: {player._valid_init}, Dead: {player.is_dead}, Alive: {player.alive() if hasattr(player,'alive') else 'N/A'}") # DEBUG
        return

    player.acc.x = 0 
    
    intends_move_left_net = received_input_data_dict.get('left_held', False)
    intends_move_right_net = received_input_data_dict.get('right_held', False)
    
    net_fireball_aim_x = received_input_data_dict.get('fireball_aim_x')
    net_fireball_aim_y = received_input_data_dict.get('fireball_aim_y')
    if net_fireball_aim_x is not None and net_fireball_aim_y is not None:
        if float(net_fireball_aim_x) != 0.0 or float(net_fireball_aim_y) != 0.0:
            player.fireball_last_input_dir.x = float(net_fireball_aim_x)
            player.fireball_last_input_dir.y = float(net_fireball_aim_y)
    
    can_control_horizontal_via_net = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )
    
    new_facing_direction_net = player.facing_right 
    if can_control_horizontal_via_net:
        if intends_move_left_net and not intends_move_right_net:
            player.acc.x = -C.PLAYER_ACCEL
            new_facing_direction_net = False
        elif intends_move_right_net and not intends_move_left_net:
            player.acc.x = C.PLAYER_ACCEL
            new_facing_direction_net = True
            
    if player.on_ground and player.state in ['idle', 'run'] and not player.is_attacking and \
       player.facing_right != new_facing_direction_net:
        player.facing_right = new_facing_direction_net
        player.set_state('turn') 
    else: 
        player.facing_right = new_facing_direction_net
    
    can_perform_action_net = not player.is_attacking and not player.is_dashing and \
                             not player.is_rolling and not player.is_sliding and \
                             not player.on_ladder and player.state not in ['turn','hit'] \
                             and not player.is_crouching # Prevent actions while crouching for consistency
    
    if received_input_data_dict.get('attack1_pressed_event', False) and can_perform_action_net:
        player.attack_type = 4 if player.is_crouching else 1 # This line might be redundant if can_perform_action_net blocks crouching
        attack_anim_key_net = 'crouch_attack' if player.is_crouching else \
                              ('attack' if (intends_move_left_net or intends_move_right_net) else 'attack_nm')
        player.set_state(attack_anim_key_net)
    
    if received_input_data_dict.get('attack2_pressed_event', False) and can_perform_action_net:
        player.attack_type = 4 if player.is_crouching else 2 # Redundant if crouching blocked
        attack2_anim_key_net = 'crouch_attack' if player.is_crouching else \
                               ('attack2' if (intends_move_left_net or intends_move_right_net) else 'attack2_nm')
        player.set_state(attack2_anim_key_net)

    # Handle new weapon firing events
    if can_perform_action_net: # Ensure not crouching for projectiles too
        if received_input_data_dict.get('fireball_pressed_event', False):
            if hasattr(player, 'fire_fireball'): player.fire_fireball()
        if received_input_data_dict.get('poison_pressed_event', False):
            if hasattr(player, 'fire_poison'): player.fire_poison()
        if received_input_data_dict.get('bolt_pressed_event', False):
            if hasattr(player, 'fire_bolt'): player.fire_bolt()
        if received_input_data_dict.get('blood_pressed_event', False):
            if hasattr(player, 'fire_blood'): player.fire_blood()
        if received_input_data_dict.get('ice_pressed_event', False):
            if hasattr(player, 'fire_ice'): player.fire_ice()


    if received_input_data_dict.get('jump_intent', False) and can_perform_action_net and not player.is_crouching:
         if player.on_ground: 
             player.vel.y = C.PLAYER_JUMP_STRENGTH
             player.set_state('jump')
             player.on_ground = False 

    if received_input_data_dict.get('dash_pressed_event', False) and player.on_ground and \
       can_perform_action_net and not player.is_crouching:
        player.set_state('dash')
    
    if received_input_data_dict.get('roll_pressed_event', False) and player.on_ground and \
       can_perform_action_net and not player.is_crouching:
        player.set_state('roll')
    
    # Set player's intention flags based on network input for server-side update logic
    player.is_holding_crouch_ability_key = received_input_data_dict.get('down_held', False)
    player.is_holding_climb_ability_key = received_input_data_dict.get('up_held', False)
    # print(f"DEBUG PNH (handle_player_network_input) for P{player.player_id}: Accel.x set to {player.acc.x}, FacingRight: {player.facing_right}") # DEBUG


def get_player_input_state_for_network(player, current_pygame_keys, current_pygame_events, key_map):
    """
    Gathers the local player's current input state into a dictionary format
    suitable for sending over the network.

    Args:
        player (Player): The local player instance (used for player_id and weapon key configs).
        current_pygame_keys: The result of pygame.key.get_pressed().
        current_pygame_events: The list from pygame.event.get().
        key_map (dict): The key mapping for this player's movement/action controls.

    Returns:
        dict: A dictionary representing the player's input state.
    """
    input_state_dict = {
        'left_held': bool(current_pygame_keys[key_map['left']]),
        'right_held': bool(current_pygame_keys[key_map['right']]),
        'up_held': bool(current_pygame_keys[key_map['up']]),
        'down_held': bool(current_pygame_keys[key_map['down']]),
        
        'attack1_pressed_event': False, 
        'attack2_pressed_event': False,
        'dash_pressed_event': False, 
        'roll_pressed_event': False,
        'interact_pressed_event': False, 
        'jump_intent': False, 
        
        'fireball_pressed_event': False,
        'poison_pressed_event': False,
        'bolt_pressed_event': False,
        'blood_pressed_event': False,
        'ice_pressed_event': False,
        
        'fireball_aim_x': player.fireball_last_input_dir.x, 
        'fireball_aim_y': player.fireball_last_input_dir.y
    }
    
    for event in current_pygame_events:
        if event.type == pygame.KEYDOWN:
            if event.key == key_map.get('attack1'): input_state_dict["attack1_pressed_event"] = True
            if event.key == key_map.get('attack2'): input_state_dict["attack2_pressed_event"] = True
            if event.key == key_map.get('dash'): input_state_dict["dash_pressed_event"] = True
            if event.key == key_map.get('roll'): input_state_dict["roll_pressed_event"] = True
            if event.key == key_map.get('interact'): input_state_dict["interact_pressed_event"] = True
            if event.key == key_map.get('up'): input_state_dict["jump_intent"] = True 
            
            # Check weapon keys
            if player.fireball_key and event.key == player.fireball_key:
                input_state_dict['fireball_pressed_event'] = True
            elif player.poison_key and event.key == player.poison_key:
                input_state_dict['poison_pressed_event'] = True
            elif player.bolt_key and event.key == player.bolt_key:
                input_state_dict['bolt_pressed_event'] = True
            elif player.blood_key and event.key == player.blood_key:
                input_state_dict['blood_pressed_event'] = True
            elif player.ice_key and event.key == player.ice_key:
                input_state_dict['ice_pressed_event'] = True
                
    # print(f"DEBUG PNH (get_player_input_state_for_network) for P{player.player_id}: Generated input state: {input_state_dict}") # DEBUG
    return input_state_dict

########## END OF FILE: player_network_handler.py ##########