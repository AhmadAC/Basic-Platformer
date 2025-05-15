# player_animation_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.1
Handles player animation selection and frame updates.
"""
import pygame
import constants as C
# from player_state_handler import set_player_state # Careful with circular imports if set_state calls animate

def update_player_animation(player):
    """
    Updates the player's current image based on its state, frame, and facing direction.
    Operates on the 'player' instance.
    """
    if not player._valid_init or not hasattr(player, 'animations') or not player.animations:
        return
    if not player.alive():
        return 

    current_time_ms = pygame.time.get_ticks()
    animation_key_to_use = player.state
    player_is_intending_to_move_lr = player.is_trying_to_move_left or player.is_trying_to_move_right

    if player.is_dead: 
        animation_key_to_use = 'death_nm' if abs(player.vel.x) < 0.5 and abs(player.vel.y) < 1.0 and \
                                 'death_nm' in player.animations and player.animations['death_nm'] \
                              else 'death'
        if animation_key_to_use not in player.animations or not player.animations[animation_key_to_use]:
            animation_key_to_use = 'death'
    elif player.is_attacking:
        if player.attack_type == 1: animation_key_to_use = 'attack' if player_is_intending_to_move_lr and 'attack' in player.animations and player.animations['attack'] else 'attack_nm'
        elif player.attack_type == 2: animation_key_to_use = 'attack2' if player_is_intending_to_move_lr and 'attack2' in player.animations and player.animations['attack2'] else 'attack2_nm'
        elif player.attack_type == 3: animation_key_to_use = 'attack_combo' if player_is_intending_to_move_lr and 'attack_combo' in player.animations and player.animations['attack_combo'] else 'attack_combo_nm'
        elif player.attack_type == 4: animation_key_to_use = 'crouch_attack'
        if animation_key_to_use not in player.animations or not player.animations[animation_key_to_use]:
             base_attack_state_key = animation_key_to_use.replace('_nm', '')
             if base_attack_state_key in player.animations and player.animations[base_attack_state_key]:
                 animation_key_to_use = base_attack_state_key
             else: animation_key_to_use = 'idle'
    elif player.state == 'wall_climb':
         player_is_actively_climbing_wall = player.is_holding_climb_ability_key and \
                                abs(player.vel.y - C.PLAYER_WALL_CLIMB_SPEED) < 0.1
         animation_key_to_use = 'wall_climb' if player_is_actively_climbing_wall and 'wall_climb' in player.animations and player.animations['wall_climb'] else 'wall_climb_nm'
         if animation_key_to_use not in player.animations or not player.animations[animation_key_to_use]:
             animation_key_to_use = 'wall_climb'
    elif player.state == 'hit': animation_key_to_use = 'hit'
    elif not player.on_ground and not player.on_ladder and player.touching_wall == 0 and \
         player.state not in ['jump', 'jump_fall_trans'] and player.vel.y > 1:
         animation_key_to_use = 'fall'
    elif player.on_ladder:
        animation_key_to_use = 'ladder_climb' if abs(player.vel.y) > 0.1 else 'ladder_idle'
        if animation_key_to_use not in player.animations or not player.animations[animation_key_to_use]:
            animation_key_to_use = 'idle'
    elif player.is_dashing: animation_key_to_use = 'dash'
    elif player.is_rolling: animation_key_to_use = 'roll'
    elif player.is_sliding: animation_key_to_use = 'slide'
    elif player.state == 'slide_trans_start': animation_key_to_use = 'slide_trans_start'
    elif player.state == 'slide_trans_end': animation_key_to_use = 'slide_trans_end'
    elif player.state == 'crouch_trans': animation_key_to_use = 'crouch_trans'
    elif player.state == 'turn': animation_key_to_use = 'turn'
    elif player.state == 'jump': animation_key_to_use = 'jump'
    elif player.state == 'jump_fall_trans': animation_key_to_use = 'jump_fall_trans'
    elif player.state == 'wall_slide': animation_key_to_use = 'wall_slide'
    elif player.state == 'wall_hang': animation_key_to_use = 'wall_hang'
    elif player.on_ground:
        if player.is_crouching:
            animation_key_to_use = 'crouch_walk' if player_is_intending_to_move_lr and 'crouch_walk' in player.animations and player.animations['crouch_walk'] else 'crouch'
        elif player_is_intending_to_move_lr: animation_key_to_use = 'run'
        else: animation_key_to_use = 'idle'
    
    if animation_key_to_use not in player.animations or not player.animations[animation_key_to_use]: 
        animation_key_to_use = 'idle'
    
    current_animation_frames_list = player.animations.get(animation_key_to_use)

    if not current_animation_frames_list:
        if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
        if player.print_limiter.can_print(f"player_animate_no_frames_{player.player_id}_{animation_key_to_use}"):
            print(f"CRITICAL Player Animate Error ({player.player_id}): No frames found for anim key '{animation_key_to_use}' (Logical state: {player.state})")
        return

    ms_per_frame_for_current_anim = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame_for_current_anim = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    if not (player.is_dead and player.death_animation_finished):
        if current_time_ms - player.last_anim_update > ms_per_frame_for_current_anim:
            player.last_anim_update = current_time_ms
            player.current_frame += 1
            
            if player.current_frame >= len(current_animation_frames_list):
                if player.is_dead:
                    player.current_frame = len(current_animation_frames_list) - 1
                    player.death_animation_finished = True
                    final_death_image_surface = current_animation_frames_list[player.current_frame]
                    if not player.facing_right: final_death_image_surface = pygame.transform.flip(final_death_image_surface, True, False)
                    old_player_midbottom = player.rect.midbottom
                    player.image = final_death_image_surface
                    player.rect = player.image.get_rect(midbottom=old_player_midbottom)
                    return
                
                non_looping_animation_states = [
                    'attack','attack_nm','attack2','attack2_nm','attack_combo','attack_combo_nm',
                    'crouch_attack','dash','roll','slide','hit','turn','jump',
                    'jump_fall_trans','crouch_trans','slide_trans_start','slide_trans_end']
                
                if player.state in non_looping_animation_states:
                     next_logical_state_after_anim = None
                     current_logical_state_of_player = player.state 
                     player_is_intending_to_move_at_anim_end = player.is_trying_to_move_left or player.is_trying_to_move_right

                     if current_logical_state_of_player == 'jump':
                         next_logical_state_after_anim = 'jump_fall_trans' if 'jump_fall_trans' in player.animations and player.animations['jump_fall_trans'] else 'fall'
                     elif current_logical_state_of_player == 'jump_fall_trans':
                         next_logical_state_after_anim = 'fall'
                     elif current_logical_state_of_player == 'hit': 
                         next_logical_state_after_anim = 'fall' if not player.on_ground and not player.on_ladder else 'idle'
                     elif current_logical_state_of_player == 'turn':
                         next_logical_state_after_anim = 'run' if player_is_intending_to_move_at_anim_end else 'idle'
                     elif 'attack' in current_logical_state_of_player:
                          player.is_attacking = False; player.attack_type = 0
                          if player.on_ladder: pass
                          elif player.is_crouching: next_logical_state_after_anim = 'crouch'
                          elif not player.on_ground: next_logical_state_after_anim = 'fall'
                          elif player_is_intending_to_move_at_anim_end : next_logical_state_after_anim = 'run'
                          else: next_logical_state_after_anim = 'idle'
                     elif current_logical_state_of_player == 'crouch_trans':
                         player.is_crouching = player.is_holding_crouch_ability_key
                         next_logical_state_after_anim = 'crouch' if player.is_crouching else 'idle'
                     elif current_logical_state_of_player == 'slide_trans_start':
                         next_logical_state_after_anim = 'slide'
                     elif current_logical_state_of_player in ['slide_trans_end', 'slide']:
                         player.is_sliding = False
                         player.is_crouching = player.is_holding_crouch_ability_key
                         next_logical_state_after_anim = 'crouch' if player.is_crouching else 'idle'
                     else:
                          if current_logical_state_of_player == 'dash': player.is_dashing = False
                          if current_logical_state_of_player == 'roll': player.is_rolling = False
                          if player.on_ladder: pass 
                          elif player.is_crouching: next_logical_state_after_anim = 'crouch'
                          elif not player.on_ground: next_logical_state_after_anim = 'fall'
                          elif player_is_intending_to_move_at_anim_end : next_logical_state_after_anim = 'run'
                          else: next_logical_state_after_anim = 'idle'
                     
                     if next_logical_state_after_anim:
                         from player_state_handler import set_player_state # Local import
                         set_player_state(player, next_logical_state_after_anim)
                         return
                     else: player.current_frame = 0
                else: player.current_frame = 0
            
            if player.current_frame >= len(current_animation_frames_list): player.current_frame = 0
    
    if not current_animation_frames_list or player.current_frame < 0 or player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0
        if not current_animation_frames_list:
            if hasattr(player, 'image') and player.image: player.image.fill(C.RED)
            return

    image_for_this_frame = current_animation_frames_list[player.current_frame]
    if not player.facing_right: 
        image_for_this_frame = pygame.transform.flip(image_for_this_frame, True, False)
    
    if player.image is not image_for_this_frame or player._last_facing_right != player.facing_right:
        old_player_midbottom_pos = player.rect.midbottom
        player.image = image_for_this_frame
        player.rect = player.image.get_rect(midbottom=old_player_midbottom_pos)
        player._last_facing_right = player.facing_right