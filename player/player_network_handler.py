#################### START OF FILE: player_network_handler.py ####################

# player_network_handler.py
# -*- coding: utf-8 -*-
"""
Handles network data serialization, deserialization, and input processing
for the Player class in a PySide6 environment.
"""
# version 2.0.2

from typing import Dict, Any, List
import time # For get_current_ticks fallback

# PySide6 imports
from PySide6.QtCore import QPointF

# Game imports
import main_game.constants as C
# from player_state_handler import set_player_state # Import only where needed or ensure no circularity

# Logger
try:
    from logger import debug
except ImportError:
    def debug(msg): print(f"DEBUG_PNET: {msg}")

_start_time_player_net = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.

    """
    return int((time.monotonic() - _start_time_player_net) * 1000)


def get_player_network_data(player) -> Dict[str, Any]:
    pos_x = player.pos.x() if hasattr(player.pos, 'x') else 0.0
    pos_y = player.pos.y() if hasattr(player.pos, 'y') else 0.0
    vel_x = player.vel.x() if hasattr(player.vel, 'x') else 0.0
    vel_y = player.vel.y() if hasattr(player.vel, 'y') else 0.0
    aim_x = player.fireball_last_input_dir.x() if hasattr(player.fireball_last_input_dir, 'x') else 0.0
    aim_y = player.fireball_last_input_dir.y() if hasattr(player.fireball_last_input_dir, 'y') else 0.0

    data = {
        'player_id': player.player_id, '_valid_init': player._valid_init,
        'pos': (pos_x, pos_y), 'vel': (vel_x, vel_y),
        'facing_right': player.facing_right, 'state': player.state,
        'current_frame': player.current_frame, 'last_anim_update': player.last_anim_update,
        'current_health': player.current_health, 'is_dead': player.is_dead,
        'death_animation_finished': player.death_animation_finished,
        'is_attacking': player.is_attacking, 'attack_type': player.attack_type,
        'is_crouching': player.is_crouching, 'is_dashing': player.is_dashing,
        'is_rolling': player.is_rolling, 'is_sliding': player.is_sliding,
        'on_ladder': player.on_ladder, 'is_taking_hit': player.is_taking_hit,
        'hit_timer': player.hit_timer,
        'fireball_aim_x': aim_x, 'fireball_aim_y': aim_y,
        'is_aflame': player.is_aflame, 'aflame_timer_start': player.aflame_timer_start,
        'is_deflaming': player.is_deflaming, 'deflame_timer_start': player.deflame_timer_start,
        'is_frozen': player.is_frozen, 'is_defrosting': player.is_defrosting,
        'frozen_effect_timer': player.frozen_effect_timer,
        'is_petrified': player.is_petrified, 'is_stone_smashed': player.is_stone_smashed,
        'stone_smashed_timer_start': player.stone_smashed_timer_start,
        'facing_at_petrification': player.facing_at_petrification,
        'was_crouching_when_petrified': player.was_crouching_when_petrified,
    }
    return data

def set_player_network_data(player, network_data: Dict[str, Any]):
    if network_data is None: return
    from player_state_handler import set_player_state # Local import

    player._valid_init = network_data.get('_valid_init', player._valid_init)
    if not player._valid_init:
        if player.alive(): player.kill()
        return

    pos_data = network_data.get('pos')
    if pos_data and len(pos_data) == 2: player.pos.setX(pos_data[0]); player.pos.setY(pos_data[1])
    vel_data = network_data.get('vel')
    if vel_data and len(vel_data) == 2: player.vel.setX(vel_data[0]); player.vel.setY(vel_data[1])
    player.facing_right = network_data.get('facing_right', player.facing_right)
    player.current_health = network_data.get('current_health', player.current_health)
    new_is_dead_net = network_data.get('is_dead', player.is_dead)
    player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)

    new_is_petrified_net = network_data.get('is_petrified', player.is_petrified)
    new_is_smashed_net = network_data.get('is_stone_smashed', player.is_stone_smashed)
    player.was_crouching_when_petrified = network_data.get('was_crouching_when_petrified', player.was_crouching_when_petrified)
    player.facing_at_petrification = network_data.get('facing_at_petrification', player.facing_at_petrification)

    state_changed_by_priority = False
    if new_is_petrified_net:
        if not player.is_petrified: player.is_petrified = True; state_changed_by_priority = True
        player.is_aflame = False; player.is_deflaming = False
        player.is_frozen = False; player.is_defrosting = False
        if new_is_smashed_net:
            if not player.is_stone_smashed: player.is_stone_smashed = True; state_changed_by_priority = True
            player.stone_smashed_timer_start = network_data.get('stone_smashed_timer_start', player.stone_smashed_timer_start)
            player.is_dead = True
            player.death_animation_finished = network_data.get('death_animation_finished', player.death_animation_finished)
            if player.state != 'smashed': set_player_state(player, 'smashed')
        else:
            if player.is_stone_smashed: player.is_stone_smashed = False; state_changed_by_priority = True
            player.is_dead = True
            player.death_animation_finished = True
            if player.state != 'petrified': set_player_state(player, 'petrified')
    elif player.is_petrified:
        player.is_petrified = False; player.is_stone_smashed = False; state_changed_by_priority = True
        player.was_crouching_when_petrified = False

    if not player.is_petrified:
        if new_is_dead_net != player.is_dead:
            player.is_dead = new_is_dead_net
            state_changed_by_priority = True
            if player.is_dead:
                player.current_health = 0
                if player.state not in ['death', 'death_nm']: set_player_state(player, 'death')
            else:
                if player.state in ['death', 'death_nm']: set_player_state(player, 'idle')
                player.death_animation_finished = False
        else: player.is_dead = new_is_dead_net

    can_sync_other_statuses = not player.is_petrified and not (player.is_dead and player.death_animation_finished)
    if can_sync_other_statuses:
        new_is_aflame = network_data.get('is_aflame', player.is_aflame)
        if new_is_aflame and not player.is_aflame: player.aflame_timer_start = network_data.get('aflame_timer_start', get_current_ticks())
        player.is_aflame = new_is_aflame
        new_is_deflaming = network_data.get('is_deflaming', player.is_deflaming)
        if new_is_deflaming and not player.is_deflaming: player.deflame_timer_start = network_data.get('deflame_timer_start', get_current_ticks())
        player.is_deflaming = new_is_deflaming
        new_is_frozen = network_data.get('is_frozen', player.is_frozen)
        if new_is_frozen and not player.is_frozen: player.frozen_effect_timer = network_data.get('frozen_effect_timer', get_current_ticks())
        player.is_frozen = new_is_frozen
        new_is_defrosting = network_data.get('is_defrosting', player.is_defrosting)
        if new_is_defrosting and not player.is_defrosting: player.frozen_effect_timer = network_data.get('frozen_effect_timer', get_current_ticks())
        player.is_defrosting = new_is_defrosting

    can_sync_actions = can_sync_other_statuses and not (player.is_aflame or player.is_deflaming or player.is_frozen or player.is_defrosting)
    if can_sync_actions:
        player.is_attacking = network_data.get('is_attacking', player.is_attacking)
        player.attack_type = network_data.get('attack_type', player.attack_type)
        player.is_crouching = network_data.get('is_crouching', player.is_crouching)
        player.is_dashing = network_data.get('is_dashing', player.is_dashing)
        player.is_rolling = network_data.get('is_rolling', player.is_rolling)
        player.is_sliding = network_data.get('is_sliding', player.is_sliding)
        player.on_ladder = network_data.get('on_ladder', player.on_ladder)
        new_is_taking_hit = network_data.get('is_taking_hit', player.is_taking_hit)
        new_hit_timer = network_data.get('hit_timer', player.hit_timer)
        if new_is_taking_hit != player.is_taking_hit or (new_is_taking_hit and player.hit_timer != new_hit_timer):
            player.is_taking_hit = new_is_taking_hit
            player.hit_timer = new_hit_timer
            if player.is_taking_hit and player.state != 'hit' and not player.is_dead: set_player_state(player, 'hit')
            elif not player.is_taking_hit and player.state == 'hit' and not player.is_dead: set_player_state(player, 'idle')

    if not state_changed_by_priority:
        new_logical_state_from_net = network_data.get('state', player.state)
        is_current_state_overriding = player.state in ['aflame','burning','aflame_crouch','burning_crouch',
                                                      'deflame','deflame_crouch','frozen','defrost',
                                                      'petrified','smashed','death','death_nm']
        if not is_current_state_overriding and player.state != new_logical_state_from_net:
            set_player_state(player, new_logical_state_from_net)
        else:
            player.current_frame = network_data.get('current_frame', player.current_frame)
            player.last_anim_update = network_data.get('last_anim_update', player.last_anim_update)

    aim_x_net = network_data.get('fireball_aim_x')
    aim_y_net = network_data.get('fireball_aim_y')
    if aim_x_net is not None and aim_y_net is not None:
        player.fireball_last_input_dir.setX(float(aim_x_net))
        player.fireball_last_input_dir.setY(float(aim_y_net))

    if hasattr(player, '_update_rect_from_image_and_pos'): player._update_rect_from_image_and_pos()
    else: player.rect.moveCenter(player.pos); player.rect.moveBottom(player.pos.y())

    if player._valid_init and player.alive():
        if hasattr(player, 'animate'): player.animate()


def handle_player_network_input(player, received_input_data_dict: Dict[str, Any]):
    if not player._valid_init or player.is_dead or not player.alive() or player.is_petrified: return
    from player_state_handler import set_player_state # Local import

    player.is_trying_to_move_left = received_input_data_dict.get('left_held', False)
    player.is_trying_to_move_right = received_input_data_dict.get('right_held', False)
    player.is_holding_climb_ability_key = received_input_data_dict.get('up_held', False)
    player.is_holding_crouch_ability_key = received_input_data_dict.get('down_held', False)

    net_aim_x = received_input_data_dict.get('fireball_aim_x')
    net_aim_y = received_input_data_dict.get('fireball_aim_y')
    if net_aim_x is not None and net_aim_y is not None:
        if float(net_aim_x) != 0.0 or float(net_aim_y) != 0.0:
            player.fireball_last_input_dir.setX(float(net_aim_x))
            player.fireball_last_input_dir.setY(float(net_aim_y))
        elif player.fireball_last_input_dir.isNull() or \
             (player.fireball_last_input_dir.x() == 0 and player.fireball_last_input_dir.y() == 0) :
            player.fireball_last_input_dir.setX(1.0 if player.facing_right else -1.0)
            player.fireball_last_input_dir.setY(0.0)

    current_accel_x = 0.0
    new_facing_net = player.facing_right
    can_control_horizontal_net = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang', 'frozen', 'defrost']
    )
    is_on_fire_visual_net = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    if player.is_taking_hit and not is_on_fire_visual_net and player.state == 'hit':
        can_control_horizontal_net = False

    if can_control_horizontal_net:
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            current_accel_x = -C.PLAYER_ACCEL; new_facing_net = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            current_accel_x = C.PLAYER_ACCEL; new_facing_net = True
    player.acc.setX(current_accel_x)

    if player.on_ground and player.state in ['idle', 'run'] and not player.is_attacking and \
       player.facing_right != new_facing_net and not is_on_fire_visual_net:
        player.facing_right = new_facing_net
        set_player_state(player, 'turn')
    else: player.facing_right = new_facing_net

    can_perform_general_action_net = not player.is_attacking and not player.is_dashing and \
                                     not player.is_rolling and not player.is_sliding and \
                                     not player.on_ladder and player.state not in ['turn','hit', 'frozen', 'defrost'] and \
                                     not is_on_fire_visual_net

    if received_input_data_dict.get('crouch_event', False):
        if player.is_crouching:
            if hasattr(player, 'can_stand_up') and player.can_stand_up(player.game_elements_ref_for_projectiles.get('platform_sprites',[])): # This part needs platform_sprites
                player.is_crouching = False
                if player.is_aflame or player.is_deflaming:
                     next_f_state = 'burning' if player.is_aflame else 'deflame'
                     set_player_state(player, next_f_state)
                else: set_player_state(player, 'idle')
        else:
            can_crouch_now_net = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now_net:
                player.is_crouching = True
                if player.is_aflame: set_player_state(player, 'aflame_crouch')
                elif player.is_deflaming: set_player_state(player, 'deflame_crouch')
                else: set_player_state(player, 'crouch_trans' if player.animations and player.animations.get('crouch_trans') else 'crouch')

    if received_input_data_dict.get('jump_pressed_event', False):
        can_initiate_jump_action_net = not (player.is_attacking or player.is_dashing or
                                         player.is_rolling or player.is_sliding or
                                         player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost'])
        if not is_on_fire_visual_net:
            if player.state == 'hit': can_initiate_jump_action_net = False
            if player.is_taking_hit and (get_current_ticks() - player.hit_timer < player.hit_duration): can_initiate_jump_action_net = False
        if can_initiate_jump_action_net:
            can_actually_execute_jump_net = not player.is_crouching or \
                (hasattr(player, 'can_stand_up') and player.can_stand_up(player.game_elements_ref_for_projectiles.get('platform_sprites',[])))
            if player.is_crouching and can_actually_execute_jump_net:
                 player.is_crouching = False
                 if player.is_aflame: set_player_state(player, 'burning')
                 elif player.is_deflaming: set_player_state(player, 'deflame')
            if can_actually_execute_jump_net:
                if player.on_ground: player.vel.setY(C.PLAYER_JUMP_STRENGTH); set_player_state(player, 'jump'); player.on_ground = False
                elif player.on_ladder:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8)
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1))
                    player.on_ladder = False; set_player_state(player, 'jump')
                elif player.can_wall_jump and player.touching_wall != 0:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH)
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall))
                    player.facing_right = not player.facing_right
                    set_player_state(player, 'jump'); player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0

    if received_input_data_dict.get('attack1_pressed_event', False) and can_perform_general_action_net:
        player.attack_type = 4 if player.is_crouching else 1
        set_player_state(player, 'crouch_attack' if player.is_crouching else ('attack' if (player.is_trying_to_move_left or player.is_trying_to_move_right) else 'attack_nm'))
    if received_input_data_dict.get('attack2_pressed_event', False) and can_perform_general_action_net:
        if player.is_crouching and not player.is_attacking : player.attack_type = 4; set_player_state(player, 'crouch_attack')
        elif not player.is_attacking: player.attack_type = 2; set_player_state(player, 'attack2' if (player.is_trying_to_move_left or player.is_trying_to_move_right) else 'attack2_nm')
    if received_input_data_dict.get('dash_pressed_event', False) and player.on_ground and can_perform_general_action_net and not player.is_crouching: set_player_state(player, 'dash')
    if received_input_data_dict.get('roll_pressed_event', False) and player.on_ground and can_perform_general_action_net and not player.is_crouching: set_player_state(player, 'roll')
    if received_input_data_dict.get('interact_pressed_event', False) and not is_on_fire_visual_net:
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel = QPointF(0,0); player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            set_player_state(player, 'ladder_idle')
        elif player.on_ladder: player.on_ladder = False; set_player_state(player, 'fall' if not player.on_ground else 'idle')

    if can_perform_general_action_net:
        if received_input_data_dict.get('fireball_pressed_event', False) and hasattr(player, 'fire_fireball'): player.fire_fireball()
        if received_input_data_dict.get('poison_pressed_event', False) and hasattr(player, 'fire_poison'): player.fire_poison()
        if received_input_data_dict.get('bolt_pressed_event', False) and hasattr(player, 'fire_bolt'): player.fire_bolt()
        if received_input_data_dict.get('blood_pressed_event', False) and hasattr(player, 'fire_blood'): player.fire_blood()
        if received_input_data_dict.get('ice_pressed_event', False) and hasattr(player, 'fire_ice'): player.fire_ice()
        if received_input_data_dict.get('fire_shadow_event', False) and hasattr(player, 'fire_shadow'): player.fire_shadow()
        if received_input_data_dict.get('fire_grey_event', False) and hasattr(player, 'fire_grey'): player.fire_grey()


def get_player_input_state_for_network(player,
                                       qt_keys_pressed_snapshot: Dict[int, bool],
                                       qt_input_events: List[Any],
                                       key_map_config: Dict[str, Any],
                                       platforms_list: List[Any]
                                       ) -> Dict[str, Any]:
    from player_input_handler import process_player_input_logic # Local import
    processed_action_events = process_player_input_logic(
        player, qt_keys_pressed_snapshot, qt_input_events, key_map_config, platforms_list
    )
    network_payload = {
        'left_held': player.is_trying_to_move_left,
        'right_held': player.is_trying_to_move_right,
        'up_held': player.is_holding_climb_ability_key,
        'down_held': player.is_holding_crouch_ability_key,
        'is_crouching_state': player.is_crouching,
        'fireball_aim_x': player.fireball_last_input_dir.x(),
        'fireball_aim_y': player.fireball_last_input_dir.y(),
        'action_self_harm': processed_action_events.get('self_harm', False),
        'action_heal': processed_action_events.get('heal', False),
        'action_reset_global': processed_action_events.get('reset', False)
    }
    network_payload.update(processed_action_events)
    return network_payload

#################### END OF FILE: player_network_handler.py ####################