#################### START OF FILE: player_input_handler.py ####################

# player_input_handler.py
# -*- coding: utf-8 -*-
"""
Version 2.1.7 (Corrected PrintLimiter.can_log call)
Handles processing of player input (Qt keyboard events, Pygame joystick polling)
and translating it to game actions.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QPointF

import constants as C
import config as game_config
from utils import PrintLimiter
from logger import debug, warning, error

try:
    from player_state_handler import set_player_state
except ImportError:
    error("CRITICAL PLAYER_INPUT_HANDLER: Failed to import 'set_player_state' from 'player_state_handler'. State changes will fail.")
    def set_player_state(player: Any, new_state: str): # Fallback dummy
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")


input_print_limiter = PrintLimiter(default_limit=10, default_period=3.0)

_input_handler_start_time = time.monotonic()
def get_input_handler_ticks():
    return int((time.monotonic() - _input_handler_start_time) * 1000)

def process_player_input_logic(
    player: Any,
    qt_keys_held_snapshot: Dict[Qt.Key, bool],
    qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
    active_mappings: Dict[str, Any],
    platforms_list: List[Any], # For player's can_stand_up check
    joystick_data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    if not hasattr(player, '_valid_init') or not player._valid_init:
        # Corrected call to PrintLimiter's method (assuming it was intended to be can_print or a similar existing method)
        # If can_log was a custom method, ensure it's defined in PrintLimiter.
        # For now, using can_print as it's a common pattern for these limiters.
        if input_print_limiter.can_print(f"invalid_player_input_handler_{getattr(player, 'player_id', 'unknown')}skip"):
            warning(f"PlayerInputHandler: Skipping input for invalid player instance (ID: {getattr(player, 'player_id', 'unknown')}).")
        return {}

    current_time_ms = get_input_handler_ticks()
    player_id_str = f"P{player.player_id}"
    
    debug_this_frame = input_print_limiter.can_print(f"input_proc_tick_{player_id_str}")

    is_pygame_joystick_input = player.control_scheme and player.control_scheme.startswith("joystick_pygame_")
    action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    player.is_trying_to_move_left = False
    player.is_trying_to_move_right = False
    player.is_holding_climb_ability_key = False 
    player.is_holding_crouch_ability_key = False

    # --- 1. Process Keyboard Input (Qt Events) ---
    if not is_pygame_joystick_input:
        for action_name in ["left", "right", "up", "down"]:
            key_code_for_action = active_mappings.get(action_name)
            if isinstance(key_code_for_action, Qt.Key) and qt_keys_held_snapshot.get(key_code_for_action, False):
                if action_name == "left": player.is_trying_to_move_left = True
                elif action_name == "right": player.is_trying_to_move_right = True
                elif action_name == "up": player.is_holding_climb_ability_key = True 
                elif action_name == "down": player.is_holding_crouch_ability_key = True
        
        if debug_this_frame and input_print_limiter.can_print(f"kbd_intent_{player.player_id}"):
            debug(f"{player_id_str} Kbd Intent: L={player.is_trying_to_move_left}, R={player.is_trying_to_move_right}, U={player.is_holding_climb_ability_key}, D={player.is_holding_crouch_ability_key}")

        for event_type, key_code_from_event, _is_auto_repeat in qt_key_event_data_this_frame:
            if event_type == QKeyEvent.Type.KeyPress: 
                for action_name, mapped_qt_key in active_mappings.items():
                    if isinstance(mapped_qt_key, Qt.Key) and key_code_from_event == mapped_qt_key:
                        action_events[action_name] = True
                        if action_name == "up": action_events["jump"] = True
                        if action_name == "down": action_events["crouch"] = True 
                        break 
    
    # --- 2. Process Pygame Joystick Input ---
    elif is_pygame_joystick_input and joystick_data:
        current_axes = joystick_data.get('axes', {})
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {})
        current_hats = joystick_data.get('hats', {})

        if not hasattr(player, '_prev_discrete_axis_hat_state'):
            player._prev_discrete_axis_hat_state = {}

        for action_name, mapping_details in active_mappings.items():
            if not isinstance(mapping_details, dict): continue
            m_type = mapping_details.get("type"); m_id = mapping_details.get("id")
            
            if m_type == "axis":
                axis_val = current_axes.get(m_id, 0.0)
                m_axis_direction = mapping_details.get("value") 
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                is_axis_held_active = (m_axis_direction == -1 and axis_val < -m_threshold) or \
                                      (m_axis_direction == 1 and axis_val > m_threshold)

                if action_name == "left": player.is_trying_to_move_left = is_axis_held_active or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_axis_held_active or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_axis_held_active or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_axis_held_active or player.is_holding_crouch_ability_key
                
                if action_name in getattr(C, 'JOYSTICK_AXIS_EVENT_ACTIONS', []): 
                    axis_event_key = ("axis", m_id, m_axis_direction) 
                    was_previously_active_for_event = player._prev_discrete_axis_hat_state.get(axis_event_key, False)
                    if is_axis_held_active and not was_previously_active_for_event:
                        action_events[action_name] = True
                        if action_name == "up": action_events["jump"] = True
                        if action_name == "down": action_events["crouch"] = True
                    player._prev_discrete_axis_hat_state[axis_event_key] = is_axis_held_active

            elif m_type == "button":
                is_pressed_now = current_buttons.get(m_id, False)
                was_pressed_prev = prev_buttons.get(m_id, False)
                if is_pressed_now and not was_pressed_prev: 
                    action_events[action_name] = True
                    if action_name == "up": action_events["jump"] = True
                    if action_name == "down": action_events["crouch"] = True
            
            elif m_type == "hat":
                hat_val_target_tuple = tuple(mapping_details.get("value", (0,0))) 
                current_hat_val_tuple = tuple(current_hats.get(m_id, (0,0))) 
                is_hat_held_active = (current_hat_val_tuple == hat_val_target_tuple and hat_val_target_tuple != (0,0))

                if action_name == "left": player.is_trying_to_move_left = is_hat_held_active or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_hat_held_active or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_hat_held_active or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_hat_held_active or player.is_holding_crouch_ability_key

                if action_name in getattr(C, 'JOYSTICK_HAT_EVENT_ACTIONS', []):
                    hat_event_key = ("hat", m_id, hat_val_target_tuple)
                    was_previously_active_for_event = player._prev_discrete_axis_hat_state.get(hat_event_key, False)
                    if is_hat_held_active and not was_previously_active_for_event:
                        action_events[action_name] = True
                        if action_name == "up": action_events["jump"] = True
                        if action_name == "down": action_events["crouch"] = True
                    player._prev_discrete_axis_hat_state[hat_event_key] = is_hat_held_active
        
        if debug_this_frame and input_print_limiter.can_print(f"joy_intent_{player.player_id}"):
            debug(f"{player_id_str} Joy Intent: L={player.is_trying_to_move_left}, R={player.is_trying_to_move_right}, U={player.is_holding_climb_ability_key}, D={player.is_holding_crouch_ability_key}")

    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right

    # --- 3. Update Player Aiming Direction ---
    aim_x, aim_y = 0.0, 0.0
    if player.is_trying_to_move_left: aim_x = -1.0
    elif player.is_trying_to_move_right: aim_x = 1.0
    if player.is_holding_climb_ability_key: aim_y = -1.0 
    elif player.is_holding_crouch_ability_key or getattr(player, 'is_crouching', False): aim_y = 1.0 

    if not hasattr(player, 'fireball_last_input_dir') or not isinstance(player.fireball_last_input_dir, QPointF):
        player.fireball_last_input_dir = QPointF(1.0 if getattr(player, 'facing_right', True) else -1.0, 0.0)

    if abs(aim_x) > 1e-6 or abs(aim_y) > 1e-6: 
        player.fireball_last_input_dir.setX(aim_x)
        player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (abs(player.fireball_last_input_dir.x()) < 1e-6 and abs(player.fireball_last_input_dir.y()) < 1e-6) : 
        player.fireball_last_input_dir.setX(1.0 if getattr(player, 'facing_right', True) else -1.0)
        player.fireball_last_input_dir.setY(0.0)

    # --- 4. Block Input Processing for Certain Player States ---
    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    
    if is_fully_action_blocked:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0.0) 
        if debug_this_frame: debug(f"{player_id_str} Input: Fully action blocked. State={player.state}")
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- 5. Set Horizontal Acceleration based on Intent ---
    if hasattr(player, 'acc') and hasattr(player.acc, 'setX'):
        intended_accel_x = 0.0
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            intended_accel_x = -C.PLAYER_ACCEL
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                set_player_state(player, 'turn')
            player.facing_right = False 
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            intended_accel_x = C.PLAYER_ACCEL
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                set_player_state(player, 'turn')
            player.facing_right = True
        
        can_control_horizontal_movement = not (
            player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
            (player.is_attacking and player.state.endswith('_nm')) or 
            player.state in ['turn','hit','death','death_nm','wall_hang','wall_slide', 'frozen', 'defrost']
        )
        if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit':
            can_control_horizontal_movement = False

        if can_control_horizontal_movement:
            accel_to_apply_x = intended_accel_x
            if player.is_aflame: accel_to_apply_x *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: accel_to_apply_x *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
            player.acc.setX(accel_to_apply_x)
    else:
        if input_print_limiter.can_print(f"player_acc_missing_{player_id_str}"): # Use can_print for this limiter
            warning(f"{player_id_str} Input: Player 'acc' attribute or 'setX' method missing!")

    # --- 6. Ladder Movement (vertical only) ---
    if player.on_ladder:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0.0) 
        if hasattr(player, 'vel') and hasattr(player.vel, 'setY'):
            if player.is_holding_climb_ability_key: 
                player.vel.setY(-C.PLAYER_LADDER_CLIMB_SPEED)
            elif player.is_holding_crouch_ability_key: 
                player.vel.setY(C.PLAYER_LADDER_CLIMB_SPEED)
            else:
                player.vel.setY(0.0) 

    # --- 7. Process Discrete Action Events ---
    is_stunned_or_busy_for_general_actions = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                     player.is_attacking or player.is_dashing or player.is_rolling or \
                                     player.is_sliding or player.state == 'turn'

    if action_events.get("crouch"): 
        if player.is_crouching: 
            if player.can_stand_up(platforms_list):
                next_state_after_uncrouch = ('burning' if player.is_aflame else \
                                            ('deflame' if player.is_deflaming else \
                                            ('run' if player_intends_horizontal_move else 'idle')))
                set_player_state(player, next_state_after_uncrouch)
        else: 
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                next_state_to_crouch = ('aflame_crouch' if player.is_aflame else \
                                       ('deflame_crouch' if player.is_deflaming else \
                                       ('crouch_trans' if player.animations and player.animations.get('crouch_trans') else 'crouch')))
                set_player_state(player, next_state_to_crouch)
    
    if not is_pygame_joystick_input and action_events.get("up") and \
       active_mappings.get("jump") == active_mappings.get("up"): 
        if player.is_crouching and player.can_stand_up(platforms_list):
            next_state_after_uncrouch_key = ('burning' if player.is_aflame else \
                                            ('deflame' if player.is_deflaming else \
                                            ('run' if player_intends_horizontal_move else 'idle')))
            set_player_state(player, next_state_after_uncrouch_key)
            action_events["jump"] = False 

    if action_events.get("jump"): 
        can_initiate_jump_action = not (player.is_attacking or player.is_dashing or
                                         player.is_rolling or player.is_sliding or
                                         player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost'])
        if not is_on_fire_visual:
            if player.state == 'hit': can_initiate_jump_action = False
            if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration):
                can_initiate_jump_action = False
        
        if can_initiate_jump_action:
            can_actually_execute_jump = True 
            if player.is_crouching: 
                can_actually_execute_jump = player.can_stand_up(platforms_list)
                if can_actually_execute_jump: 
                    player_intends_move_after_uncrouch = player.is_trying_to_move_left or player.is_trying_to_move_right
                    next_state_after_uncrouch_for_jump = ('burning' if player.is_aflame else \
                                                          ('deflame' if player.is_deflaming else \
                                                          ('run' if player_intends_move_after_uncrouch else 'idle')))
                    set_player_state(player, next_state_after_uncrouch_for_jump)
            
            if can_actually_execute_jump: 
                if player.on_ground:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH); set_player_state(player, 'jump'); player.on_ground = False
                elif player.on_ladder:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8) 
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1)) 
                    player.on_ladder = False; set_player_state(player, 'jump')
                elif player.can_wall_jump and player.touching_wall != 0: 
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH)
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)) 
                    player.facing_right = not player.facing_right 
                    set_player_state(player, 'jump')
                    player.can_wall_jump = False; player.touching_wall = 0

    can_perform_other_abilities_now = not is_on_fire_visual and not is_stunned_or_busy_for_general_actions

    if action_events.get("attack1") and can_perform_other_abilities_now: set_player_state(player, 'attack') 
    if action_events.get("attack2") and can_perform_other_abilities_now: set_player_state(player, 'attack2')
    if action_events.get("dash") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: set_player_state(player, 'dash')
    if action_events.get("roll") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: set_player_state(player, 'roll')
    
    if action_events.get("interact") and not is_on_fire_visual: 
        if player.can_grab_ladder and not player.on_ladder:
            set_player_state(player, 'ladder_idle') 
        elif player.on_ladder:
            set_player_state(player, 'fall' if not player.on_ground else 'idle') 

    if can_perform_other_abilities_now: 
        if action_events.get("projectile1") and hasattr(player, 'fire_fireball'): player.fire_fireball()
        if action_events.get("projectile2") and hasattr(player, 'fire_poison'): player.fire_poison()
        if action_events.get("projectile3") and hasattr(player, 'fire_bolt'): player.fire_bolt()
        if action_events.get("projectile4") and hasattr(player, 'fire_blood'): player.fire_blood()
        if action_events.get("projectile5") and hasattr(player, 'fire_ice'): player.fire_ice()
        if action_events.get("projectile6") and hasattr(player, 'fire_shadow'): player.fire_shadow()
        if action_events.get("projectile7") and hasattr(player, 'fire_grey'): player.fire_grey()

    # --- 8. Final State Transitions based on Movement/Environment ---
    is_in_non_interruptible_action_by_movement = player.is_attacking or player.is_dashing or \
                                                 player.is_rolling or player.is_sliding or \
                                                 player.is_taking_hit or player.state in [
                                                     'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                     'crouch_trans', 'slide_trans_start','slide_trans_end',
                                                     'wall_hang','wall_slide',
                                                     'ladder_idle','ladder_climb', 'frozen', 'defrost',
                                                     'petrified', 'smashed'
                                                 ]

    if not is_in_non_interruptible_action_by_movement or is_on_fire_visual: 
        if player.on_ladder:
            if abs(player.vel.y()) > 0.1 and player.state != 'ladder_climb': set_player_state(player, 'ladder_climb')
            elif abs(player.vel.y()) <= 0.1 and player.state != 'ladder_idle': set_player_state(player, 'ladder_idle')
        elif player.on_ground:
            if player.is_crouching: 
                crouch_prefix = 'burning' if player.is_aflame else ('deflame' if player.is_deflaming else '')
                target_crouch_state = (crouch_prefix + ('_crouch' if crouch_prefix else ('crouch_walk' if player_intends_horizontal_move else 'crouch')) )
                if player.state != target_crouch_state and player.animations and player.animations.get(target_crouch_state):
                    set_player_state(player, target_crouch_state)
            elif player_intends_horizontal_move: 
                target_run_state = ('burning' if player.is_aflame else ('deflame' if player.is_deflaming else 'run'))
                if player.state != target_run_state and player.animations and player.animations.get(target_run_state):
                    set_player_state(player, target_run_state)
            else: 
                target_idle_state = ('burning' if player.is_aflame else ('deflame' if player.is_deflaming else 'idle'))
                if player.state != target_idle_state and player.animations and player.animations.get(target_idle_state):
                    set_player_state(player, target_idle_state)
        else: # In air, not on ladder
            if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                if player.vel.y() > C.PLAYER_WALL_SLIDE_SPEED * 0.5 : 
                    if player.state != 'wall_slide': set_player_state(player, 'wall_slide'); player.can_wall_jump = True
            elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and \
               player.state not in ['jump','jump_fall_trans']: 
                target_fall_state = ('burning' if player.is_aflame else ('deflame' if player.is_deflaming else 'fall'))
                if player.state != target_fall_state and player.animations and player.animations.get(target_fall_state):
                    set_player_state(player, target_fall_state)
            elif player.state not in ['jump','jump_fall_trans','fall', 'wall_slide', 'wall_hang'] and not is_on_fire_visual and player.state != 'idle': 
                set_player_state(player, 'idle')

    if debug_this_frame and input_print_limiter.can_print(f"p_input_final_{player.player_id}"):
        active_events_str = ", ".join([f"{k.replace('_pressed_event','')}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        debug(f"{player_id_str} InputHandler Final: state='{player.state}', "
              f"is_trying_L/R=({player.is_trying_to_move_left}/{player.is_trying_to_move_right}), "
              f"acc.x={player.acc.x():.2f}, vel.y={player.vel.y():.2f}, "
              f"Events Fired: [{active_events_str}]")

    return action_events