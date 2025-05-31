# joystick_handler.py
# (effectively player_input_handler.py in your project)
# -*- coding: utf-8 -*-
"""
Version 2.2.2 (Added missing get_input_handler_ticks definition)
MODIFIED: Added conditional consumption of "interact" event for ladders.
MODIFIED: Added extensive debug logging for tracing "interact" action.
MODIFIED: Defined get_input_handler_ticks at the module level.
Handles processing of player input (Qt keyboard events, Pygame joystick polling)
and translating it to game actions.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent # For type hinting Qt key events
from PySide6.QtCore import Qt, QPointF       # For Qt.Key enum

import main_game.constants as C
import main_game.config as game_config # For GAME_ACTIONS and AXIS_THRESHOLD_DEFAULT
from utils import PrintLimiter # Assuming utils.py and PrintLimiter are available

# Logger import
from logger import debug, warning, error # Ensure these are imported

try:
    from player_state_handler import set_player_state
except ImportError:
    error("CRITICAL PLAYER_INPUT_HANDLER: Failed to import 'set_player_state' from 'player_state_handler'. State changes will fail.")
    def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")


input_print_limiter = PrintLimiter(default_limit=10, default_period=1.0) # Shortened period for more frequent logs

_input_handler_start_time_monotonic = time.monotonic()
def get_input_handler_ticks() -> int:
    return int((time.monotonic() - _input_handler_start_time_monotonic) * 1000)


def process_player_input_logic( 
    player: Any,
    qt_keys_held_snapshot: Dict[Qt.Key, bool],
    qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
    active_mappings: Dict[str, Any], 
    platforms_list: List[Any], 
    joystick_data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    if not hasattr(player, '_valid_init') or not player._valid_init: 
        if input_print_limiter.can_log(f"invalid_player_input_handler_{getattr(player, 'player_id', 'unknown')}skip"):
            warning(f"PlayerInputHandler: Skipping input for invalid player instance (ID: {getattr(player, 'player_id', 'unknown')}).")
        return {}

    current_time_ms = get_input_handler_ticks()
    player_id_str = f"P{player.player_id}"
    
    is_pygame_joystick_input = player.control_scheme and player.control_scheme.startswith("joystick_pygame_")
    action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    
    is_stunned_or_busy_general = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                  player.is_attacking or player.is_dashing or player.is_rolling or \
                                  player.is_sliding or player.state == 'turn'

    player.is_trying_to_move_left = False
    player.is_trying_to_move_right = False
    player.is_holding_climb_ability_key = False
    player.is_holding_crouch_ability_key = False

    if not is_pygame_joystick_input:
        # ... (keyboard intent and event logic remains the same as your updated version) ...
        for action_name in ["left", "right", "up", "down"]:
            key_code_for_action = active_mappings.get(action_name)
            if isinstance(key_code_for_action, Qt.Key) and qt_keys_held_snapshot.get(key_code_for_action, False):
                if action_name == "left": player.is_trying_to_move_left = True
                elif action_name == "right": player.is_trying_to_move_right = True
                elif action_name == "up": player.is_holding_climb_ability_key = True 
                elif action_name == "down": player.is_holding_crouch_ability_key = True
        
        if input_print_limiter.can_log(f"kbd_intent_{player.player_id}_handler"):
            debug(f"INPUT_HANDLER ({player_id_str}) Kbd Intent (Handler): L={player.is_trying_to_move_left}, R={player.is_trying_to_move_right}, U={player.is_holding_climb_ability_key}, D={player.is_holding_crouch_ability_key}")

        for event_type, key_code_from_event, _is_auto_repeat in qt_key_event_data_this_frame:
            if event_type == QKeyEvent.Type.KeyPress:
                for action_name, mapped_qt_key in active_mappings.items():
                    if isinstance(mapped_qt_key, Qt.Key) and key_code_from_event == mapped_qt_key:
                        action_events[action_name] = True
                        if input_print_limiter.can_log(f"kbd_event_handler_{player.player_id}_{action_name}"):
                             debug(f"INPUT_HANDLER ({player_id_str}): KBD EVENT '{action_name}' = True (Key: {key_code_from_event})")
                        if action_name == "up" and active_mappings.get("jump") == key_code_from_event: action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch") == key_code_from_event: action_events["crouch"] = True 
                        elif action_name == "crouch": action_events["crouch"] = True
                        break
    
    elif is_pygame_joystick_input and joystick_data:
        current_axes = joystick_data.get('axes', {})
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {}) # This comes from app_input_manager already copied
        current_hats = joystick_data.get('hats', {})

        if not hasattr(player, '_prev_discrete_axis_hat_state') or not isinstance(player._prev_discrete_axis_hat_state, dict):
            player._prev_discrete_axis_hat_state = {}
        is_first_poll_for_player_joystick = not getattr(player, '_first_joystick_input_poll_done', False)

        for action_name, mapping_details in active_mappings.items():
            if not isinstance(mapping_details, dict): continue
            m_type = mapping_details.get("type"); m_id = mapping_details.get("id")
            
            if m_type == "axis":
                # ... (axis logic for continuous movement intent and discrete events) ...
                axis_val = current_axes.get(m_id, 0.0)
                m_axis_direction_value = mapping_details.get("value") 
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                is_axis_held_active = (m_axis_direction_value == -1 and axis_val < -m_threshold) or \
                                      (m_axis_direction_value == 1 and axis_val > m_threshold)

                if action_name == "left": player.is_trying_to_move_left = is_axis_held_active or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_axis_held_active or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_axis_held_active or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_axis_held_active or player.is_holding_crouch_ability_key
                
                if action_name in getattr(C, 'JOYSTICK_AXIS_EVENT_ACTIONS', []): 
                    axis_event_key_tuple = ("axis", m_id, m_axis_direction_value) 
                    was_previously_active_for_event = player._prev_discrete_axis_hat_state.get(axis_event_key_tuple, False)
                    
                    if is_first_poll_for_player_joystick: 
                        player._prev_discrete_axis_hat_state[axis_event_key_tuple] = is_axis_held_active
                    elif is_axis_held_active and not was_previously_active_for_event: 
                        action_events[action_name] = True
                        if input_print_limiter.can_log(f"joy_axis_event_handler_{player.player_id}_{action_name}"):
                            debug(f"INPUT_HANDLER ({player_id_str}): JOY AXIS EVENT '{action_name}' = True (AxisID: {m_id}, Val: {axis_val:.2f})")
                        if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump", {}).get("value") == m_axis_direction_value and active_mappings.get("jump",{}).get("type") == "axis": 
                            action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch", {}).get("value") == m_axis_direction_value and active_mappings.get("crouch",{}).get("type") == "axis": 
                            action_events["crouch"] = True
                    
                    if not is_first_poll_for_player_joystick:
                         player._prev_discrete_axis_hat_state[axis_event_key_tuple] = is_axis_held_active

            elif m_type == "button":
                is_pressed_now = current_buttons.get(m_id, False)
                was_pressed_prev = prev_buttons.get(m_id, False) 
                # --- DEBUG ---
                if input_print_limiter.can_log(f"joy_btn_check_handler_{player_id_str}_{action_name}_{m_id}"):
                    debug(f"INPUT_HANDLER ({player_id_str}): Checking Joy Button '{action_name}' (mapped ID: {m_id}). Now: {is_pressed_now}, Prev: {was_pressed_prev}")
                # --- END DEBUG ---
                if is_pressed_now and not was_pressed_prev: 
                    action_events[action_name] = True
                    if input_print_limiter.can_log(f"joy_btn_event_handler_{player.player_id}_{action_name}"): 
                        debug(f"INPUT_HANDLER ({player_id_str}): JOY BTN EVENT '{action_name}' = True (BtnID: {m_id})")
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "button": action_events["jump"] = True
                    if action_name == "down" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "button": action_events["crouch"] = True
            
            elif m_type == "hat":
                # ... (hat logic for continuous movement intent and discrete events) ...
                hat_val_target_tuple = tuple(mapping_details.get("value", (0,0))) 
                current_hat_val_tuple = tuple(current_hats.get(m_id, (0,0))) 
                is_hat_held_active_now = (current_hat_val_tuple == hat_val_target_tuple and hat_val_target_tuple != (0,0))

                if action_name == "left": player.is_trying_to_move_left = is_hat_held_active_now or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_hat_held_active_now or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_hat_held_active_now or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_hat_held_active_now or player.is_holding_crouch_ability_key
                
                if action_name in getattr(C, 'JOYSTICK_HAT_EVENT_ACTIONS', []):
                    hat_event_key_tuple = ("hat", m_id, hat_val_target_tuple) 
                    was_hat_held_active_prev = player._prev_discrete_axis_hat_state.get(hat_event_key_tuple, False)

                    if is_first_poll_for_player_joystick: 
                        player._prev_discrete_axis_hat_state[hat_event_key_tuple] = is_hat_held_active_now
                    elif is_hat_held_active_now and not was_hat_held_active_prev: 
                        action_events[action_name] = True
                        if input_print_limiter.can_log(f"joy_hat_event_handler_{player.player_id}_{action_name}"):
                            debug(f"INPUT_HANDLER ({player_id_str}): JOY HAT EVENT '{action_name}' = True (HatID: {m_id}, Val: {current_hat_val_tuple})")
                        if action_name == "up" and active_mappings.get("jump", {}).get("value") == hat_val_target_tuple and active_mappings.get("jump", {}).get("type") == "hat" and active_mappings.get("jump", {}).get("id") == m_id:
                            action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch", {}).get("value") == hat_val_target_tuple and active_mappings.get("crouch", {}).get("type") == "hat" and active_mappings.get("crouch", {}).get("id") == m_id:
                            action_events["crouch"] = True
                    
                    if not is_first_poll_for_player_joystick:
                        player._prev_discrete_axis_hat_state[hat_event_key_tuple] = is_hat_held_active_now
        
        if is_first_poll_for_player_joystick:
            player._first_joystick_input_poll_done = True
            if input_print_limiter.can_log(f"joy_first_poll_handler_{player.player_id}"):
                debug(f"INPUT_HANDLER ({player_id_str}) Joy Input: First poll priming complete for discrete axis/hat states. PrevStates: {player._prev_discrete_axis_hat_state}")

        if input_print_limiter.can_log(f"joy_intent_handler_{player.player_id}"):
            debug(f"INPUT_HANDLER ({player_id_str}) Joy Intent (Handler): L={player.is_trying_to_move_left}, R={player.is_trying_to_move_right}, U={player.is_holding_climb_ability_key}, D={player.is_holding_crouch_ability_key}")


    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right
    
    aim_x, aim_y = 0.0, 0.0
    if player.is_trying_to_move_left: aim_x = -1.0
    elif player.is_trying_to_move_right: aim_x = 1.0
    if player.is_holding_climb_ability_key: aim_y = -1.0 
    elif player.is_holding_crouch_ability_key or getattr(player, 'is_crouching', False): aim_y = 1.0 
    if not hasattr(player, 'fireball_last_input_dir') or not isinstance(player.fireball_last_input_dir, QPointF):
        player.fireball_last_input_dir = QPointF(1.0 if getattr(player, 'facing_right', True) else -1.0, 0.0)
    if abs(aim_x) > 1e-6 or abs(aim_y) > 1e-6: 
        player.fireball_last_input_dir.setX(aim_x); player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (abs(player.fireball_last_input_dir.x()) < 1e-6 and abs(player.fireball_last_input_dir.y()) < 1e-6) : 
        player.fireball_last_input_dir.setX(1.0 if getattr(player, 'facing_right', True) else -1.0); player.fireball_last_input_dir.setY(0.0)

    if is_fully_action_blocked:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0.0) 
        if input_print_limiter.can_log(f"input_blocked_handler_{player.player_id}"):
            debug(f"INPUT_HANDLER ({player_id_str}): Fully action blocked. State={player.state}")
        reset_event = action_events.get("reset", False); pause_event = action_events.get("pause", False)
        action_events["pause_event"] = pause_event 
        return {"reset": reset_event, "pause": pause_event, "pause_event": pause_event}

    if hasattr(player, 'acc') and hasattr(player.acc, 'setX'):
        intended_accel_x = 0.0; new_facing_based_on_intent = player.facing_right
        if player.is_trying_to_move_left and not player.is_trying_to_move_right: intended_accel_x = -C.PLAYER_ACCEL; new_facing_based_on_intent = False 
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left: intended_accel_x = C.PLAYER_ACCEL; new_facing_based_on_intent = True
        can_control_horizontal_movement = not (
            player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
            (player.is_attacking and player.state.endswith('_nm')) or 
            player.state in ['turn','hit','death','death_nm','wall_hang','wall_slide', 'frozen', 'defrost']
        )
        if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit': can_control_horizontal_movement = False
        if can_control_horizontal_movement:
            accel_to_apply_x = intended_accel_x
            if player.is_aflame: accel_to_apply_x *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: accel_to_apply_x *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
            player.acc.setX(accel_to_apply_x)
            if player.facing_right != new_facing_based_on_intent and \
               player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                set_player_state(player, 'turn', current_time_ms)
            player.facing_right = new_facing_based_on_intent
    else:
        if input_print_limiter.can_log(f"player_acc_missing_input_handler_{player_id_str}"):
            warning(f"INPUT_HANDLER ({player_id_str}): Player 'acc' attribute or 'setX' method missing!")

    # --- Discrete Action Event Processing ---
    if input_print_limiter.can_log(f"input_before_discrete_actions_handler_{player_id_str}"):
        active_events_str_before_discrete = ", ".join([f"{k}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        debug(f"INPUT_HANDLER ({player_id_str}): Before discrete actions. Events: [{active_events_str_before_discrete}], Stunned/Busy: {is_stunned_or_busy_general}, OnFire: {is_on_fire_visual}")
    
    if action_events.get("crouch"): 
        if player.is_crouching: 
            if player.can_stand_up(platforms_list):
                set_player_state(player, 'idle' if not (player.is_aflame or player.is_deflaming) else ('burning' if player.is_aflame else 'deflame'), current_time_ms)
        else: 
            if player.on_ground and not player.on_ladder and not player.is_sliding and \
               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump']):
                set_player_state(player, 'aflame_crouch' if player.is_aflame else ('deflame_crouch' if player.is_deflaming else ('crouch_trans' if player.animations and player.animations.get('crouch_trans') else 'crouch')), current_time_ms)
        action_events["crouch"] = False

    if not is_pygame_joystick_input and action_events.get("up") and active_mappings.get("jump") == active_mappings.get("up"): 
        if player.is_crouching and player.can_stand_up(platforms_list):
            set_player_state(player, 'idle' if not (player.is_aflame or player.is_deflaming) else ('burning' if player.is_aflame else 'deflame'), current_time_ms)
            action_events["jump"] = False 
        action_events["up"] = False 

    if action_events.get("jump"): 
        if not (player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost'] or (player.state == 'hit' and not is_on_fire_visual) or (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration and not is_on_fire_visual)):
            if not player.is_crouching or (hasattr(player, 'can_stand_up') and player.can_stand_up(platforms_list)):
                if player.is_crouching: 
                    player.is_crouching = False; 
                    if player.is_aflame: set_player_state(player, 'burning', current_time_ms)
                    elif player.is_deflaming: set_player_state(player, 'deflame', current_time_ms)
                set_player_state(player, 'jump', current_time_ms)
        action_events["jump"] = False

    can_perform_other_abilities_now = not is_on_fire_visual and not is_stunned_or_busy_general and not player.on_ladder
    
    if action_events.get("attack1") and can_perform_other_abilities_now: 
        set_player_state(player, 'attack', current_time_ms); action_events["attack1"] = False 
    if action_events.get("attack2") and can_perform_other_abilities_now: 
        set_player_state(player, 'attack2', current_time_ms); action_events["attack2"] = False
    if action_events.get("dash") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: 
        set_player_state(player, 'dash', current_time_ms); action_events["dash"] = False
    if action_events.get("roll") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: 
        set_player_state(player, 'roll', current_time_ms); action_events["roll"] = False
    
    if action_events.get("interact") and not is_on_fire_visual: 
        interact_event_consumed_by_ladder = False
        if player.can_grab_ladder and not player.on_ladder:
            set_player_state(player, 'ladder_idle', current_time_ms); interact_event_consumed_by_ladder = True
            if input_print_limiter.can_log(f"interact_ladder_grab_handler_{player_id_str}"): debug(f"INPUT_HANDLER ({player_id_str}): Interact event GRABBED ladder.")
        elif player.on_ladder: 
            set_player_state(player, 'fall' if not player.on_ground else 'idle', current_time_ms); interact_event_consumed_by_ladder = True
            if input_print_limiter.can_log(f"interact_ladder_release_handler_{player_id_str}"): debug(f"INPUT_HANDLER ({player_id_str}): Interact event RELEASED ladder.")
        if interact_event_consumed_by_ladder: action_events["interact"] = False
        else:
            if input_print_limiter.can_log(f"interact_ladder_noconsume_handler_{player_id_str}"): debug(f"INPUT_HANDLER ({player_id_str}): Interact event NOT consumed by ladder. Interact State: {action_events.get('interact')}")
    
    if can_perform_other_abilities_now: 
        for proj_idx in range(1, 8):
            proj_action_key = f"projectile{proj_idx}"
            proj_fire_method_name = f"fire_{C.PROJECTILE_CONFIG_ORDER[proj_idx-1]}" if proj_idx-1 < len(C.PROJECTILE_CONFIG_ORDER) else None
            if proj_fire_method_name and action_events.get(proj_action_key) and hasattr(player, proj_fire_method_name):
                getattr(player, proj_fire_method_name)(); action_events[proj_action_key] = False

    if input_print_limiter.can_log(f"p_input_final_handler_{player.player_id}"):
        final_active_events_str_handler = ", ".join([f"{k}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        debug(f"INPUT_HANDLER ({player_id_str}) END: Final action_events: [{final_active_events_str_handler}]")

    return action_events