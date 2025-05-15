# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.5 (Disabled fireball while crouching)
Handles processing of player input and translating it to actions.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C

def process_player_input_logic(player, keys_pressed, pygame_events, key_config_map):
    """
    Core logic for processing raw Pygame input (held keys and events)
    into player actions and state changes.
    Modifies the 'player' instance directly based on the input and key configuration.

    Args:
        player (Player): The player instance to be controlled.
        keys_pressed (pygame.key.ScancodeWrapper): Snapshot of currently held keys
                                                   (from pygame.key.get_pressed()).
        pygame_events (list): List of Pygame events for the current frame
                              (from pygame.event.get()).
        key_config_map (dict): A dictionary mapping action strings
                               (e.g., 'left', 'attack1') to Pygame key constants
                               (e.g., pygame.K_a, pygame.K_v).
    """
    if not player._valid_init: return # Do nothing if player initialization failed

    current_time_ms = pygame.time.get_ticks() # For managing state timers and cooldowns

    is_input_blocked = player.is_dead or \
                       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration)

    if is_input_blocked:
        player.acc.x = 0
        return

    player.is_trying_to_move_left = keys_pressed[key_config_map['left']]
    player.is_trying_to_move_right = keys_pressed[key_config_map['right']]
    player.is_holding_climb_ability_key = keys_pressed[key_config_map['up']]
    player.is_holding_crouch_ability_key = keys_pressed[key_config_map['down']] # Still used for ladder down & fireball aim

    fireball_aim_x_input = 0.0
    fireball_aim_y_input = 0.0
    if keys_pressed[key_config_map['left']]: fireball_aim_x_input = -1.0
    elif keys_pressed[key_config_map['right']]: fireball_aim_x_input = 1.0

    if keys_pressed[key_config_map['up']]: fireball_aim_y_input = -1.0
    elif player.is_holding_crouch_ability_key: fireball_aim_y_input = 1.0

    if fireball_aim_x_input != 0.0 or fireball_aim_y_input != 0.0:
        player.fireball_last_input_dir.x = fireball_aim_x_input
        player.fireball_last_input_dir.y = fireball_aim_y_input
    elif player.fireball_last_input_dir.length_squared() == 0:
        player.fireball_last_input_dir.x = 1.0 if player.facing_right else -1.0
        player.fireball_last_input_dir.y = 0.0

    player.acc.x = 0
    player_intends_horizontal_move = False

    can_player_control_horizontal_movement = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state in ['attack_nm','attack2_nm','attack_combo_nm','crouch_attack']) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang']
    )

    if can_player_control_horizontal_movement:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.x = -C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.x = C.PLAYER_ACCEL
            player_intends_horizontal_move = True
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run']:
                player.set_state('turn')
            player.facing_right = True

    if player.on_ladder:
         player.vel.y = 0
         if player.is_holding_climb_ability_key:
             player.vel.y = -C.PLAYER_LADDER_CLIMB_SPEED
         elif player.is_holding_crouch_ability_key: # Uses HOLD for ladder
             player.vel.y = C.PLAYER_LADDER_CLIMB_SPEED

    for event in pygame_events:
        if event.type == pygame.KEYDOWN:
            if event.key == key_config_map['up']:
                  can_perform_jump_action = not player.is_attacking and \
                                            not player.is_rolling and not player.is_sliding and \
                                            not player.is_dashing and \
                                            player.state not in ['turn','hit','death','death_nm']
                  if can_perform_jump_action:
                      if player.on_ground:
                          if player.is_crouching:
                              player.is_crouching = False
                          player.vel.y = C.PLAYER_JUMP_STRENGTH
                          player.set_state('jump')
                          player.on_ground = False
                      elif player.on_ladder:
                          player.is_crouching = False
                          player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.8
                          player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)
                          player.on_ladder = False
                          player.set_state('jump')
                      elif player.can_wall_jump and player.touching_wall != 0:
                          player.is_crouching = False
                          player.vel.y = C.PLAYER_JUMP_STRENGTH
                          player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)
                          player.facing_right = not player.facing_right
                          player.set_state('jump')
                          player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0

            if event.key == key_config_map['attack1']:
                  can_perform_attack_action = not player.is_attacking and not player.is_dashing and \
                                              not player.is_rolling and not player.is_sliding and \
                                              not player.on_ladder and player.state not in ['turn','hit']
                  if can_perform_attack_action:
                       player.attack_type = 1
                       is_moving_for_attack_anim = (player.acc.x !=0 or abs(player.vel.x) > 1.0)
                       attack_animation_key = 'attack' if is_moving_for_attack_anim and \
                                              'attack' in player.animations and player.animations['attack'] \
                                              else 'attack_nm'
                       if player.is_crouching:
                           player.attack_type = 4
                           attack_animation_key = 'crouch_attack'
                       player.set_state(attack_animation_key)

            if event.key == key_config_map['attack2']:
                  can_perform_attack2_action = not player.is_dashing and not player.is_rolling and \
                                               not player.is_sliding and not player.on_ladder and \
                                               player.state not in ['turn','hit']
                  if can_perform_attack2_action:
                       is_moving_for_attack2_anim = (player.acc.x != 0 or abs(player.vel.x) > 1.0)
                       time_since_attack1_ended = current_time_ms - (player.attack_timer + player.attack_duration)
                       is_in_combo_window_for_attack3 = (player.attack_type == 1 and not player.is_attacking and
                                                         time_since_attack1_ended < player.combo_window)
                       selected_attack2_anim_key = ''
                       if is_in_combo_window_for_attack3 and \
                          'attack_combo' in player.animations and player.animations['attack_combo']:
                           player.attack_type = 3
                           selected_attack2_anim_key = 'attack_combo' if is_moving_for_attack2_anim else 'attack_combo_nm'
                       elif player.is_crouching and 'crouch_attack' in player.animations and \
                            player.animations['crouch_attack'] and not player.is_attacking :
                           player.attack_type = 4; selected_attack2_anim_key = 'crouch_attack'
                       elif not player.is_attacking and 'attack2' in player.animations and player.animations['attack2']:
                           player.attack_type = 2
                           selected_attack2_anim_key = 'attack2' if is_moving_for_attack2_anim else 'attack2_nm'
                       elif not player.is_attacking and player.attack_type == 0 and \
                            'attack' in player.animations and player.animations['attack']:
                           player.attack_type = 1
                           selected_attack2_anim_key = 'attack' if is_moving_for_attack2_anim else 'attack_nm'
                       if selected_attack2_anim_key : player.set_state(selected_attack2_anim_key)

            if event.key == key_config_map['dash']:
                  if player.on_ground and not player.is_dashing and not player.is_rolling and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('dash')

            if event.key == key_config_map['roll']:
                  if player.on_ground and not player.is_rolling and not player.is_dashing and \
                     not player.is_attacking and not player.is_crouching and not player.on_ladder and \
                     player.state not in ['turn','hit']:
                      player.set_state('roll')

            if event.key == key_config_map['down']:
                can_initiate_slide_action = player.on_ground and player.state == 'run' and \
                                            abs(player.vel.x) > C.PLAYER_RUN_SPEED_LIMIT * 0.6 and \
                                            not player.is_sliding and not player.is_crouching and \
                                            not player.is_attacking and not player.is_rolling and \
                                            not player.is_dashing and not player.on_ladder and \
                                            player.state not in ['turn','hit']
                if can_initiate_slide_action:
                    slide_start_anim_key = 'slide_trans_start' if 'slide_trans_start' in player.animations and \
                                             player.animations['slide_trans_start'] else 'slide'
                    if slide_start_anim_key in player.animations and player.animations[slide_start_anim_key]:
                        player.set_state(slide_start_anim_key)
                        player.is_crouching = False
                else:
                    can_player_toggle_crouch = player.on_ground and not player.on_ladder and \
                                               not player.is_sliding and \
                                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                                    player.state in ['turn','hit','death','death_nm'])
                    if can_player_toggle_crouch:
                        if not player.is_crouching:
                            player.is_crouching = True
                            player.is_sliding = False
                            if 'crouch_trans' in player.animations and player.animations['crouch_trans'] and \
                               player.state not in ['crouch','crouch_walk','crouch_trans']:
                                player.set_state('crouch_trans')
                            elif player.state not in ['crouch', 'crouch_walk', 'crouch_trans']:
                                player.set_state('crouch')
                        else:
                            player.is_crouching = False
                            if 'stand_up_trans' in player.animations and player.animations['stand_up_trans'] and \
                               player.state not in ['idle','run','stand_up_trans']:
                                player.set_state('stand_up_trans')

            if event.key == key_config_map['interact']:
                  if player.can_grab_ladder and not player.on_ladder:
                      player.is_crouching = False
                      player.on_ladder = True; player.vel.y=0; player.vel.x=0; player.on_ground=False
                      player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
                      player.set_state('ladder_idle')
                  elif player.on_ladder:
                      player.on_ladder = False
                      player.set_state('fall' if not player.on_ground else 'idle')

            # --- MODIFIED FIREBALL LOGIC ---
            if player.fireball_key and event.key == player.fireball_key:
                 if not player.is_crouching: # <-- ADDED THIS CHECK
                     print(f"DEBUG PIH (P{player.player_id}): Matched fireball key press ({event.key}) and not crouching. Calling player.fire_fireball().")
                     if hasattr(player, 'fire_fireball'):
                         player.fire_fireball()
                 else:
                     print(f"DEBUG PIH (P{player.player_id}): Matched fireball key press ({event.key}) BUT player is crouching. Fireball blocked.")
            # --- END OF MODIFIED FIREBALL LOGIC ---


    is_in_manual_override_or_transition_state = player.is_attacking or player.is_dashing or \
                                                player.is_rolling or player.is_sliding or \
                                                player.is_taking_hit or \
                                                player.state in [
                                                    'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                    'crouch_trans', 'stand_up_trans',
                                                    'slide_trans_start','slide_trans_end',
                                                    'wall_climb','wall_climb_nm','wall_hang','wall_slide',
                                                    'ladder_idle','ladder_climb'
                                                ]

    if not is_in_manual_override_or_transition_state:
        if player.on_ladder:
            if abs(player.vel.y) > 0.1 :
                player.set_state('ladder_climb' if 'ladder_climb' in player.animations and \
                                 player.animations['ladder_climb'] else 'idle')
            else:
                player.set_state('ladder_idle' if 'ladder_idle' in player.animations and \
                                 player.animations['ladder_idle'] else 'idle')
        elif player.on_ground:
             if player.is_crouching:
                 target_crouch_state_key = 'crouch_walk' if player_intends_horizontal_move and \
                                             'crouch_walk' in player.animations and player.animations['crouch_walk'] \
                                             else 'crouch'
                 if player.state not in ['crouch', 'crouch_walk'] or player.state != target_crouch_state_key:
                    player.set_state(target_crouch_state_key if target_crouch_state_key in player.animations and \
                                     player.animations[target_crouch_state_key] else 'crouch')
             elif player_intends_horizontal_move:
                 player.set_state('run' if 'run' in player.animations and player.animations['run'] else 'idle')
             else:
                 player.set_state('idle')
        else:
             if player.touching_wall != 0:
                 current_wall_time_ms = pygame.time.get_ticks()
                 is_wall_climb_duration_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and
                                                   current_wall_time_ms - player.wall_climb_timer > player.wall_climb_duration)
                 if player.vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or is_wall_climb_duration_expired:
                     player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x) < 1.0 and \
                      not is_wall_climb_duration_expired and 'wall_climb' in player.animations and player.animations['wall_climb']:
                     player.set_state('wall_climb'); player.can_wall_jump = False
                 else:
                     player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y > 1.0 and player.state not in ['jump','jump_fall_trans']:
                  player.set_state('fall' if 'fall' in player.animations and player.animations['fall'] else 'idle')
             elif player.state not in ['jump','jump_fall_trans','fall']:
                  player.set_state('idle')