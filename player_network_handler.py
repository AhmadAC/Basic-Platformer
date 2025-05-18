#################### START OF MODIFIED FILE: player_network_handler.py ####################

########## START OF FILE: player_network_handler.py ##########

# player_network_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.4 (Add was_crouching_when_petrified to network data)
Handles network-related data serialization, deserialization, and input processing
for the Player class in a networked environment.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C

def get_player_network_data(player):
    """
    Gathers essential player data into a dictionary for network transmission.
    """
    data = {
        'player_id': player.player_id,
        '_valid_init': player._valid_init,
        'pos': (player.pos.x, player.pos.y),
        'vel': (player.vel.x, player.vel.y),
        'facing_right': player.facing_right,
        'state': player.state,
        'current_frame': player.current_frame,
        'last_anim_update': player.last_anim_update,
        'current_health': player.current_health,
        'is_dead': player.is_dead,
        'death_animation_finished': player.death_animation_finished,
        'is_attacking': player.is_attacking,
        'attack_type': player.attack_type,
        'is_crouching': player.is_crouching,
        'is_dashing': player.is_dashing,
        'is_rolling': player.is_rolling,
        'is_sliding': player.is_sliding,
        'on_ladder': player.on_ladder,
        'is_taking_hit': player.is_taking_hit,
        'fireball_aim_x': player.fireball_last_input_dir.x,
        'fireball_aim_y': player.fireball_last_input_dir.y,
        # Status effect flags
        'is_aflame': player.is_aflame,
        'aflame_timer_start': player.aflame_timer_start,
        'is_deflaming': player.is_deflaming,
        'deflame_timer_start': player.deflame_timer_start,
        'is_frozen': player.is_frozen,
        'is_defrosting': player.is_defrosting,
        'frozen_effect_timer': player.frozen_effect_timer,
        'is_petrified': player.is_petrified,
        'is_stone_smashed': player.is_stone_smashed,
        'stone_smashed_timer_start': player.stone_smashed_timer_start,
        'facing_at_petrification': player.facing_at_petrification,
        'was_crouching_when_petrified': player.was_crouching_when_petrified, # MODIFIED: Added this flag
    }
    return data

def set_player_network_data(player, network_data):
    """
    Applies received network data to update the local player instance's state.
    """
    if network_data is None:
        return

    # ... (existing code for setting _valid_init, pos, vel, facing_right, health, death status, actions) ...
    player_id_from_data = network_data.get('player_id', 'Unknown')

    new_valid_init = network_data.get('_valid_init', player._valid_init)
    if player._valid_init != new_valid_init:
        player._valid_init = new_valid_init
    
    if not player._valid_init:
        if player.alive():
            player.kill()
        return

    pos_data = network_data.get('pos')
    if pos_data:
        player.pos.x, player.pos.y = pos_data
    
    vel_data = network_data.get('vel')
    if vel_data: player.vel.x, player.vel.y = vel_data
    
    player.facing_right = network_data.get('facing_right', player.facing_right)
    
    player.current_health = network_data.get('current_health', player.current_health)
    new_is_dead_from_net = network_data.get('is_dead', player.is_dead)
    player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)

    # Petrify status must be set before general death status to ensure correct animation
    new_is_petrified_net = network_data.get('is_petrified', player.is_petrified)
    new_is_smashed_net = network_data.get('is_stone_smashed', player.is_stone_smashed)
    player.was_crouching_when_petrified = network_data.get('was_crouching_when_petrified', player.was_crouching_when_petrified) # MODIFIED
    player.facing_at_petrification = network_data.get('facing_at_petrification', player.facing_at_petrification)


    state_changed_by_priority_status = False
    if new_is_petrified_net:
        if not player.is_petrified:
            player.is_petrified = True; state_changed_by_priority_status = True
            # Clear other active statuses if just became petrified
            player.is_aflame = False; player.is_deflaming = False
            player.is_frozen = False; player.is_defrosting = False
        player.is_petrified = True # Ensure
        if new_is_smashed_net:
            if not player.is_stone_smashed:
                player.is_stone_smashed = True; state_changed_by_priority_status = True
            player.stone_smashed_timer_start = network_data.get('stone_smashed_timer_start', player.stone_smashed_timer_start)
            player.is_dead = True # Smashed is dead
            player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)
            if player.state != 'smashed': player.set_state('smashed')
        else: # Petrified but not smashed
            if player.is_stone_smashed: player.is_stone_smashed = False; state_changed_by_priority_status = True
            player.is_dead = True # Petrified counts as "dead" for game over, but can be smashed
            player.death_animation_finished = True # Petrified is visually "done" until smashed
            if player.state != 'petrified': player.set_state('petrified')
    elif player.is_petrified: # Was petrified, but server says no longer
        player.is_petrified = False; player.is_stone_smashed = False; state_changed_by_priority_status = True
        player.was_crouching_when_petrified = False


    # Sync regular death status only if not petrified (petrified handles its own 'is_dead')
    if not player.is_petrified:
        if new_is_dead_from_net and not player.is_dead:
            player.is_dead = True
            player.current_health = 0
            if player.state not in ['death', 'death_nm']: player.set_state('death')
            state_changed_by_priority_status = True
        elif not new_is_dead_from_net and player.is_dead:
            player.is_dead = False
            player.death_animation_finished = False
            if player.state in ['death', 'death_nm']: player.set_state('idle')
            state_changed_by_priority_status = True
        else:
            player.is_dead = new_is_dead_from_net


    # Sync other status effects if not petrified or just died normally
    if not player.is_petrified and not (player.is_dead and player.state in ['death', 'death_nm']):
        new_is_aflame = network_data.get('is_aflame', player.is_aflame)
        if new_is_aflame and not player.is_aflame: player.aflame_timer_start = network_data.get('aflame_timer_start', pygame.time.get_ticks())
        player.is_aflame = new_is_aflame

        new_is_deflaming = network_data.get('is_deflaming', player.is_deflaming)
        if new_is_deflaming and not player.is_deflaming: player.deflame_timer_start = network_data.get('deflame_timer_start', pygame.time.get_ticks())
        player.is_deflaming = new_is_deflaming

        new_is_frozen = network_data.get('is_frozen', player.is_frozen)
        if new_is_frozen and not player.is_frozen: player.frozen_effect_timer = network_data.get('frozen_effect_timer', pygame.time.get_ticks())
        player.is_frozen = new_is_frozen

        new_is_defrosting = network_data.get('is_defrosting', player.is_defrosting)
        if new_is_defrosting and not player.is_defrosting: player.frozen_effect_timer = network_data.get('frozen_effect_timer', pygame.time.get_ticks()) # Uses same base timer
        player.is_defrosting = new_is_defrosting

    # ... (rest of the setters for is_attacking, attack_type, is_crouching, etc.) ...
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
        if player.state != 'hit' and not player.is_dead and not player.is_petrified : player.set_state('hit')
    elif not new_is_taking_hit_from_net and player.is_taking_hit:
        player.is_taking_hit = False
        if player.state == 'hit' and not player.is_dead and not player.is_petrified : player.set_state('idle')


    if not state_changed_by_priority_status : # Only set general state if not overridden by petrify/death
        new_logical_state_from_net = network_data.get('state', player.state)
        if player.state != new_logical_state_from_net:
            player.set_state(new_logical_state_from_net)
        else: # If state is the same, still sync animation frame details
            player.current_frame = network_data.get('current_frame', player.current_frame)
            player.last_anim_update = network_data.get('last_anim_update', player.last_anim_update)

    fb_aim_x_net = network_data.get('fireball_aim_x')
    fb_aim_y_net = network_data.get('fireball_aim_y')
    if fb_aim_x_net is not None and fb_aim_y_net is not None:
        player.fireball_last_input_dir.x = float(fb_aim_x_net)
        player.fireball_last_input_dir.y = float(fb_aim_y_net)

    player.rect.midbottom = (round(player.pos.x), round(player.pos.y))

    if player._valid_init and player.alive():
        player.animate() # Call animate to update visual based on new state


def handle_player_network_input(player, received_input_data_dict):
    # ... (existing method) ...
    if not player._valid_init or player.is_dead or not player.alive():
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
                             and not player.is_crouching
    
    if received_input_data_dict.get('attack1_pressed_event', False) and can_perform_action_net:
        player.attack_type = 4 if player.is_crouching else 1
        attack_anim_key_net = 'crouch_attack' if player.is_crouching else \
                              ('attack' if (intends_move_left_net or intends_move_right_net) else 'attack_nm')
        player.set_state(attack_anim_key_net)
    
    if received_input_data_dict.get('attack2_pressed_event', False) and can_perform_action_net:
        player.attack_type = 4 if player.is_crouching else 2
        attack2_anim_key_net = 'crouch_attack' if player.is_crouching else \
                               ('attack2' if (intends_move_left_net or intends_move_right_net) else 'attack2_nm')
        player.set_state(attack2_anim_key_net)

    if can_perform_action_net:
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
        if received_input_data_dict.get('fire_shadow_event', False):
            if hasattr(player, 'fire_shadow'): player.fire_shadow()
        if received_input_data_dict.get('fire_grey_event', False):
            if hasattr(player, 'fire_grey'): player.fire_grey()


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
    
    player.is_holding_crouch_ability_key = received_input_data_dict.get('down_held', False)
    player.is_holding_climb_ability_key = received_input_data_dict.get('up_held', False)


def get_player_input_state_for_network(player, current_pygame_keys, current_pygame_events, key_map):
    # ... (existing method) ...
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
        'fire_shadow_event': False,
        'fire_grey_event': False,
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
            elif player.shadow_key and event.key == player.shadow_key:
                input_state_dict['fire_shadow_event'] = True
            elif player.grey_key and event.key == player.grey_key:
                input_state_dict['fire_grey_event'] = True
    return input_state_dict

########## END OF FILE: player_network_handler.py ##########