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
    if network_data is None: return # No data to apply
    
    # Critical: Update _valid_init first. If player becomes invalid, stop further processing.
    player._valid_init = network_data.get('_valid_init', player._valid_init)
    if not player._valid_init:
        if player.alive(): # If player was in sprite groups
            player.kill()  # Remove from all groups
        return # No further updates if player is marked invalid

    # --- Update position and velocity directly from network ---
    pos_data = network_data.get('pos')
    if pos_data: player.pos.x, player.pos.y = pos_data
    
    vel_data = network_data.get('vel')
    if vel_data: player.vel.x, player.vel.y = vel_data
    
    player.facing_right = network_data.get('facing_right', player.facing_right)
    
    # --- Update health and death status ---
    player.current_health = network_data.get('current_health', player.current_health)
    new_is_dead_from_net = network_data.get('is_dead', player.is_dead)
    player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)

    # --- Handle transitions related to death status ---
    if new_is_dead_from_net and not player.is_dead: # Player was alive, now network says dead
        player.is_dead = True
        player.current_health = 0 # Ensure health is consistent with death
        player.set_state('death') # Trigger death state logic (animation, physics changes)
    elif not new_is_dead_from_net and player.is_dead: # Player was dead, now network says alive (e.g., reset)
        player.is_dead = False
        player.death_animation_finished = False # Reset this flag
        if player.state in ['death', 'death_nm']: # If stuck in a death animation state
            player.set_state('idle') # Transition to a neutral, alive state
    else: # No change in is_dead status, or already matches
        player.is_dead = new_is_dead_from_net # Ensure local matches network

    # --- Update combat and action states ---
    player.is_attacking = network_data.get('is_attacking', player.is_attacking)
    player.attack_type = network_data.get('attack_type', player.attack_type)
    player.is_crouching = network_data.get('is_crouching', player.is_crouching)
    player.is_dashing = network_data.get('is_dashing', player.is_dashing)
    player.is_rolling = network_data.get('is_rolling', player.is_rolling)
    player.is_sliding = network_data.get('is_sliding', player.is_sliding)
    player.on_ladder = network_data.get('on_ladder', player.on_ladder)
    
    # Hit stun state: if network says player is taking a hit, reflect that
    new_is_taking_hit_from_net = network_data.get('is_taking_hit', player.is_taking_hit)
    if new_is_taking_hit_from_net and not player.is_taking_hit: # Start of hit stun
        player.is_taking_hit = True
        player.hit_timer = pygame.time.get_ticks() # Reset hit timer for local cooldown visual/logic
        if player.state != 'hit' and not player.is_dead : player.set_state('hit') # Trigger hit anim if not already
    elif not new_is_taking_hit_from_net and player.is_taking_hit: # End of hit stun by network
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead : player.set_state('idle') # Transition out of hit anim


    # --- Update logical state and animation frame ---
    new_logical_state_from_net = network_data.get('state', player.state)
    # Apply new state if different, carefully avoiding re-triggering death anim if already in it
    if player.state != new_logical_state_from_net and \
       not (player.is_dead and new_logical_state_from_net in ['death', 'death_nm']):
         player.set_state(new_logical_state_from_net)
    else: # If state is the same, or it's a death state, just sync animation details
        player.current_frame = network_data.get('current_frame', player.current_frame)
        player.last_anim_update = network_data.get('last_anim_update', player.last_anim_update)
    
    # Update fireball aim direction from network data
    fb_aim_x_net = network_data.get('fireball_aim_x')
    fb_aim_y_net = network_data.get('fireball_aim_y')
    if fb_aim_x_net is not None and fb_aim_y_net is not None:
        player.fireball_last_input_dir.x = float(fb_aim_x_net)
        player.fireball_last_input_dir.y = float(fb_aim_y_net)
    
    # --- Finalize visual position and trigger animation update ---
    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))
    
    # Ensure animation is updated if player is valid and part of the game world
    # (alive() checks if the sprite is in any groups)
    if player._valid_init and player.alive(): 
        player.animate()


def handle_player_network_input(player, received_input_data_dict): 
    """
    Processes input data received over the network for this player instance.
    This is used by the server to update a remote player's actions based on
    what their client sent. It's a simplified version of local input processing.

    Args:
        player (Player): The player instance whose actions are being driven by network input.
        received_input_data_dict (dict): The input state dictionary from the client.
    """
    if not player._valid_init or player.is_dead or not player.alive():
        # Cannot process input if player is invalid, dead, or not in game world
        return

    player.acc.x = 0 # Reset acceleration, it will be set based on network input
    
    # --- Movement intentions from network ---
    intends_move_left_net = received_input_data_dict.get('left_held', False)
    intends_move_right_net = received_input_data_dict.get('right_held', False)
    
    # --- Update fireball aim from network input immediately ---
    # This ensures server has the latest aim for when a fireball is requested.
    net_fireball_aim_x = received_input_data_dict.get('fireball_aim_x')
    net_fireball_aim_y = received_input_data_dict.get('fireball_aim_y')
    if net_fireball_aim_x is not None and net_fireball_aim_y is not None:
        # Only update if there's an active aim signal from client to avoid overriding default
        if float(net_fireball_aim_x) != 0.0 or float(net_fireball_aim_y) != 0.0:
            player.fireball_last_input_dir.x = float(net_fireball_aim_x)
            player.fireball_last_input_dir.y = float(net_fireball_aim_y)
    
    # --- Determine facing and acceleration based on network input ---
    # Check if player can currently control horizontal movement (not in specific states)
    can_control_horizontal_via_net = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )
    
    new_facing_direction_net = player.facing_right # Assume current facing
    if can_control_horizontal_via_net:
        if intends_move_left_net and not intends_move_right_net:
            player.acc.x = -C.PLAYER_ACCEL
            new_facing_direction_net = False
        elif intends_move_right_net and not intends_move_left_net:
            player.acc.x = C.PLAYER_ACCEL
            new_facing_direction_net = True
            
    # If on ground and should turn based on new facing direction from network input
    if player.on_ground and player.state in ['idle', 'run'] and not player.is_attacking and \
       player.facing_right != new_facing_direction_net:
        player.facing_right = new_facing_direction_net
        player.set_state('turn') # Initiate turn animation
    else: # Apply facing direction directly if not turning or if state doesn't allow turn anim
        player.facing_right = new_facing_direction_net
    
    # --- Check for event-based actions from network input ---
    # These are typically "pressed_event" flags sent by the client.
    can_perform_action_net = not player.is_attacking and not player.is_dashing and \
                             not player.is_rolling and not player.is_sliding and \
                             not player.on_ladder and player.state not in ['turn','hit']
    
    # Attacks based on client's button press events
    if received_input_data_dict.get('attack1_pressed_event', False) and can_perform_action_net:
        player.attack_type = 4 if player.is_crouching else 1 # Crouching overrides
        attack_anim_key_net = 'crouch_attack' if player.is_crouching else \
                              ('attack' if (intends_move_left_net or intends_move_right_net) else 'attack_nm')
        player.set_state(attack_anim_key_net)
    
    if received_input_data_dict.get('attack2_pressed_event', False) and can_perform_action_net:
        # Server-side combo validation would be complex here without more state.
        # For now, assume client sends intent for attack2 or crouch attack.
        player.attack_type = 4 if player.is_crouching else 2 
        attack2_anim_key_net = 'crouch_attack' if player.is_crouching else \
                               ('attack2' if (intends_move_left_net or intends_move_right_net) else 'attack2_nm')
        player.set_state(attack2_anim_key_net)

    # Fireball action from network
    if received_input_data_dict.get('fireball_pressed_event', False) and can_perform_action_net:
        if hasattr(player, 'fire_fireball'): # Player class should have this method
             player.fire_fireball() # Delegates to player_combat_handler.fire_player_fireball

    # Movement abilities based on client's intent flags/events
    if received_input_data_dict.get('jump_intent', False) and can_perform_action_net and not player.is_crouching:
         if player.on_ground: # Basic jump from ground (server validates context)
             player.vel.y = C.PLAYER_JUMP_STRENGTH
             player.set_state('jump')
             player.on_ground = False # Server sets this authoritatively
         # Server would need to validate more complex jumps (wall, ladder) based on its own state.

    if received_input_data_dict.get('dash_pressed_event', False) and player.on_ground and \
       can_perform_action_net and not player.is_crouching:
        player.set_state('dash')
    
    if received_input_data_dict.get('roll_pressed_event', False) and player.on_ground and \
       can_perform_action_net and not player.is_crouching:
        player.set_state('roll')
    
    # Note on Crouch/Slide from network:
    # Client sends 'down_held'. Server needs to interpret this with context (e.g., if running for slide).
    # The current logic mainly sets player.acc.x and facing. More complex state changes like
    # initiating slide or crouch based purely on network 'down_held' would require
    # the server to replicate parts of the local input processing logic, which can be tricky.
    # Typically, the server's `player.update()` and its collision/state logic would naturally
    # handle transitions into crouch or slide if `player.is_holding_crouch_ability_key` (from net) is true
    # and other conditions (like being on ground) are met by the server's authoritative state.


def get_player_input_state_for_network(player, current_pygame_keys, current_pygame_events, key_map):
    """
    Gathers the local player's current input state into a dictionary format
    suitable for sending over the network.

    Args:
        player (Player): The local player instance (used for player_id and fireball_key config).
        current_pygame_keys: The result of pygame.key.get_pressed().
        current_pygame_events: The list from pygame.event.get().
        key_map (dict): The key mapping for this player's controls.

    Returns:
        dict: A dictionary representing the player's input state.
    """
    input_state_dict = {
        # Held keys (booleans)
        'left_held': bool(current_pygame_keys[key_map['left']]),
        'right_held': bool(current_pygame_keys[key_map['right']]),
        'up_held': bool(current_pygame_keys[key_map['up']]),
        'down_held': bool(current_pygame_keys[key_map['down']]),
        
        # Event-based presses (booleans, true if event occurred this frame)
        'attack1_pressed_event': False, 
        'attack2_pressed_event': False,
        'dash_pressed_event': False, 
        'roll_pressed_event': False,
        'interact_pressed_event': False, 
        'jump_intent': False, # 'up_held' can also indicate climb, 'jump_intent' is for actual jump press
        'fireball_pressed_event': False,
        
        # Send current aim direction for fireball
        'fireball_aim_x': player.fireball_last_input_dir.x, 
        'fireball_aim_y': player.fireball_last_input_dir.y
    }
    
    # Check Pygame events for key presses (KEYDOWN)
    for event in current_pygame_events:
        if event.type == pygame.KEYDOWN:
            if event.key == key_map.get('attack1'): input_state_dict["attack1_pressed_event"] = True
            if event.key == key_map.get('attack2'): input_state_dict["attack2_pressed_event"] = True
            if event.key == key_map.get('dash'): input_state_dict["dash_pressed_event"] = True
            if event.key == key_map.get('roll'): input_state_dict["roll_pressed_event"] = True
            if event.key == key_map.get('interact'): input_state_dict["interact_pressed_event"] = True
            if event.key == key_map.get('up'): input_state_dict["jump_intent"] = True # Jump is an event
            
            # Check for player-specific fireball key press
            if player.fireball_key and event.key == player.fireball_key:
                input_state_dict['fireball_pressed_event'] = True
                
    return input_state_dict