# player/player_input_handler.py
# -*- coding: utf-8 -*-
"""
Version 2.2.3 (Corrected logger import, added get_input_handler_ticks, refined interact, safer animation access)
Handles processing of player input (Qt keyboard events, Pygame joystick polling)
and translating it to game actions.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QPointF

import main_game.constants as C
import main_game.config as game_config
from main_game.utils import PrintLimiter # Corrected import path for utils

# Corrected logger import
try:
    from main_game.logger import debug, warning, error
except ImportError:
    print("CRITICAL PLAYER_INPUT_HANDLER: Failed to import logger from main_game.logger. Using fallback print.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PINPUT: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PINPUT: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PINPUT: {msg}")

# State handler import
try:
    from player_state_handler import set_player_state
except ImportError:
    error("CRITICAL PLAYER_INPUT_HANDLER: Failed to import 'set_player_state' from 'player_state_handler'. State changes will fail.")
    def set_player_state(player: Any, new_state: str, current_game_time_ms_param: Optional[int] = None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used for P{getattr(player, 'player_id', '?')} to '{new_state}'")


input_print_limiter = PrintLimiter(default_limit=10, default_period_sec=1.0)

# Define get_input_handler_ticks at the module level
_input_handler_start_time_monotonic = time.monotonic()
def get_input_handler_ticks() -> int:
    """Returns milliseconds since this module was loaded, for consistent timing."""
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
    
    debug_this_frame = input_print_limiter.can_log(f"input_proc_tick_{player_id_str}")

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

    # Reset continuous intent flags before processing current input
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

        if debug_this_frame and input_print_limiter.can_log(f"kbd_intent_{player.player_id}_handler"):
            debug(f"INPUT_HANDLER ({player_id_str}) Kbd Intent (Handler): L={player.is_trying_to_move_left}, R={player.is_trying_to_move_right}, U={player.is_holding_climb_ability_key}, D={player.is_holding_crouch_ability_key}")

        for event_type, key_code_from_event, _is_auto_repeat in qt_key_event_data_this_frame:
            if event_type == QKeyEvent.Type.KeyPress: # Process only actual key presses, not auto-repeats for events
                for action_name, mapped_qt_key in active_mappings.items():
                    if isinstance(mapped_qt_key, Qt.Key) and key_code_from_event == mapped_qt_key:
                        action_events[action_name] = True
                        if debug_this_frame and input_print_limiter.can_log(f"kbd_event_handler_{player.player_id}_{action_name}"):
                             debug(f"INPUT_HANDLER ({player_id_str}): KBD EVENT '{action_name}' = True (Key: {key_code_from_event})")
                        # Special handling for combined actions from one key
                        if action_name == "up" and active_mappings.get("jump") == key_code_from_event: action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch") == key_code_from_event:
                            action_events["crouch"] = True
                        elif action_name == "crouch": # Direct mapping to "crouch"
                            action_events["crouch"] = True
                        break
    
    # --- 2. Process Pygame Joystick Input ---
    elif is_pygame_joystick_input and joystick_data:
        current_axes = joystick_data.get('axes', {})
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {}) # This comes from app_input_manager already copied
        current_hats = joystick_data.get('hats', {})

        if not hasattr(player, '_prev_discrete_axis_hat_state') or not isinstance(player._prev_discrete_axis_hat_state, dict):
            player._prev_discrete_axis_hat_state = {} # Initialize if missing

        is_first_poll_for_player_joystick = not getattr(player, '_first_joystick_input_poll_done', False)

        for action_name, mapping_details in active_mappings.items():
            if not isinstance(mapping_details, dict): continue
            m_type = mapping_details.get("type"); m_id = mapping_details.get("id")
            
            if m_type == "axis":
                axis_val = current_axes.get(m_id, 0.0)
                m_axis_direction_value = mapping_details.get("value") # e.g., -1 or 1
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                is_axis_held_active = (m_axis_direction_value == -1 and axis_val < -m_threshold) or \
                                      (m_axis_direction_value == 1 and axis_val > m_threshold)

                # Update continuous intent flags
                if action_name == "left": player.is_trying_to_move_left = is_axis_held_active or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_axis_held_active or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_axis_held_active or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_axis_held_active or player.is_holding_crouch_ability_key
                
                # Check for discrete event generation (rising edge)
                if action_name in getattr(C, 'JOYSTICK_AXIS_EVENT_ACTIONS', []): # Ensure this action can be an event
                    axis_event_key_tuple = ("axis", m_id, m_axis_direction_value) # Unique key for this axis direction
                    was_previously_active_for_event = player._prev_discrete_axis_hat_state.get(axis_event_key_tuple, False)
                    
                    if is_first_poll_for_player_joystick: # On first poll, just prime the state
                        player._prev_discrete_axis_hat_state[axis_event_key_tuple] = is_axis_held_active
                    elif is_axis_held_active and not was_previously_active_for_event: # Rising edge detected
                        action_events[action_name] = True
                        if debug_this_frame and input_print_limiter.can_log(f"joy_axis_event_handler_{player.player_id}_{action_name}"):
                            debug(f"INPUT_HANDLER ({player_id_str}): JOY AXIS EVENT '{action_name}' = True (AxisID: {m_id}, Val: {axis_val:.2f})")
                        # Special handling for combined actions from one axis input
                        if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump", {}).get("value") == m_axis_direction_value and active_mappings.get("jump",{}).get("type") == "axis": 
                            action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch", {}).get("value") == m_axis_direction_value and active_mappings.get("crouch",{}).get("type") == "axis": 
                            action_events["crouch"] = True
                    
                    if not is_first_poll_for_player_joystick: # Always update prev state after first poll
                         player._prev_discrete_axis_hat_state[axis_event_key_tuple] = is_axis_held_active

            elif m_type == "button":
                is_pressed_now = current_buttons.get(m_id, False)
                was_pressed_prev = prev_buttons.get(m_id, False) 
                if is_pressed_now and not was_pressed_prev: # Rising edge for button press
                    action_events[action_name] = True
                    if debug_this_frame and input_print_limiter.can_log(f"joy_btn_event_handler_{player.player_id}_{action_name}"): 
                        debug(f"INPUT_HANDLER ({player_id_str}): JOY BTN EVENT '{action_name}' = True (BtnID: {m_id})")
                    # Special handling for combined actions
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "button": action_events["jump"] = True
                    if action_name == "down" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "button": action_events["crouch"] = True
            
            elif m_type == "hat":
                hat_val_target_tuple = tuple(mapping_details.get("value", (0,0))) # e.g., (0,1) for up
                current_hat_val_tuple = tuple(current_hats.get(m_id, (0,0))) # Pygame returns tuple for hat
                is_hat_held_active_now = (current_hat_val_tuple == hat_val_target_tuple and hat_val_target_tuple != (0,0))

                # Update continuous intent flags
                if action_name == "left": player.is_trying_to_move_left = is_hat_held_active_now or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_hat_held_active_now or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_hat_held_active_now or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_hat_held_active_now or player.is_holding_crouch_ability_key
                
                # Check for discrete event generation
                if action_name in getattr(C, 'JOYSTICK_HAT_EVENT_ACTIONS', []):
                    hat_event_key_tuple = ("hat", m_id, hat_val_target_tuple) # Unique key for this hat direction
                    was_hat_held_active_prev = player._prev_discrete_axis_hat_state.get(hat_event_key_tuple, False)

                    if is_first_poll_for_player_joystick:
                        player._prev_discrete_axis_hat_state[hat_event_key_tuple] = is_hat_held_active_now
                    elif is_hat_held_active_now and not was_hat_held_active_prev: # Rising edge
                        action_events[action_name] = True
                        if debug_this_frame and input_print_limiter.can_log(f"joy_hat_event_handler_{player.player_id}_{action_name}"):
                            debug(f"INPUT_HANDLER ({player_id_str}): JOY HAT EVENT '{action_name}' = True (HatID: {m_id}, Val: {current_hat_val_tuple})")
                        # Special handling for combined actions
                        if action_name == "up" and active_mappings.get("jump", {}).get("value") == hat_val_target_tuple and active_mappings.get("jump", {}).get("type") == "hat" and active_mappings.get("jump", {}).get("id") == m_id:
                            action_events["jump"] = True
                        if action_name == "down" and active_mappings.get("crouch", {}).get("value") == hat_val_target_tuple and active_mappings.get("crouch", {}).get("type") == "hat" and active_mappings.get("crouch", {}).get("id") == m_id:
                            action_events["crouch"] = True
                    
                    if not is_first_poll_for_player_joystick:
                        player._prev_discrete_axis_hat_state[hat_event_key_tuple] = is_hat_held_active_now
        
        if is_first_poll_for_player_joystick:
            player._first_joystick_input_poll_done = True
            if debug_this_frame: debug(f"{player_id_str} Joy Input: First poll priming complete for discrete axis/hat states.")

        if debug_this_frame and input_print_limiter.can_log(f"joy_intent_{player.player_id}"):
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
        player.fireball_last_input_dir.setX(aim_x); player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (abs(player.fireball_last_input_dir.x()) < 1e-6 and abs(player.fireball_last_input_dir.y()) < 1e-6) : 
        player.fireball_last_input_dir.setX(1.0 if getattr(player, 'facing_right', True) else -1.0); player.fireball_last_input_dir.setY(0.0)

    # --- 4. Block Input Processing for Certain Player States ---
    if is_fully_action_blocked:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0.0) 
        if debug_this_frame: debug(f"{player_id_str} Input: Fully action blocked. State={player.state}")
        # Only allow pause/reset if fully blocked
        reset_event = action_events.get("reset", False); pause_event = action_events.get("pause", False)
        action_events["pause_event"] = pause_event # For client_logic check
        return {"reset": reset_event, "pause": pause_event, "pause_event": pause_event}

    # --- 5. Set Horizontal Acceleration based on Intent ---
    if hasattr(player, 'acc') and hasattr(player.acc, 'setX'):
        intended_accel_x = 0.0; new_facing_based_on_intent = player.facing_right
        if player.is_trying_to_move_left and not player.is_trying_to_move_right: intended_accel_x = -C.PLAYER_ACCEL; new_facing_based_on_intent = False 
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left: intended_accel_x = C.PLAYER_ACCEL; new_facing_based_on_intent = True
        
        can_control_horizontal_movement = not (
            player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
            (player.is_attacking and player.state.endswith('_nm')) or 
            player.state in ['turn','hit','death','death_nm','wall_hang','wall_slide', 'frozen', 'defrost']
        )
        # Further refinement for hit state: allow control if on fire (panicked movement)
        if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit': can_control_horizontal_movement = False
        
        if can_control_horizontal_movement:
            accel_to_apply_x = intended_accel_x
            if player.is_aflame: accel_to_apply_x *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
            elif player.is_deflaming: accel_to_apply_x *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)
            player.acc.setX(accel_to_apply_x)
            
            # Handle turning if intent changes direction
            if player.facing_right != new_facing_based_on_intent and \
               player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                set_player_state(player, 'turn', current_time_ms)
            player.facing_right = new_facing_based_on_intent # Update facing based on intent
    else:
        if input_print_limiter.can_log(f"player_acc_missing_input_handler_{player_id_str}"):
            warning(f"INPUT_HANDLER ({player_id_str}): Player 'acc' attribute or 'setX' method missing!")

    # --- 6. Ladder Movement (vertical only) ---
    if player.on_ladder:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0.0) # Stop horizontal accel on ladder
        if hasattr(player, 'vel') and hasattr(player.vel, 'setY'):
            if player.is_holding_climb_ability_key:
                player.vel.setY(-C.PLAYER_LADDER_CLIMB_SPEED)
            elif player.is_holding_crouch_ability_key:
                player.vel.setY(C.PLAYER_LADDER_CLIMB_SPEED)
            else:
                player.vel.setY(0.0)

    # --- 7. Process Discrete Action Events ---
    if debug_this_frame and input_print_limiter.can_log(f"input_before_discrete_actions_handler_{player_id_str}"):
        active_events_str_before_discrete = ", ".join([f"{k}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        debug(f"INPUT_HANDLER ({player_id_str}): Before discrete actions. Events: [{active_events_str_before_discrete}], Stunned/Busy: {is_stunned_or_busy_general}, OnFire: {is_on_fire_visual}")
    
    # Crouch Toggle Logic
    if action_events.get("crouch"): 
        if player.is_crouching: 
            if player.can_stand_up(platforms_list):
                player_intends_horizontal_move_after_uncrouch = player.is_trying_to_move_left or player.is_trying_to_move_right
                next_state_after_uncrouch = ('burning' if player.is_aflame else \
                                            ('deflame' if player.is_deflaming else \
                                            ('run' if player_intends_horizontal_move_after_uncrouch else 'idle')))
                set_player_state(player, next_state_after_uncrouch, current_time_ms)
        else: 
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                next_state_to_crouch = ('aflame_crouch' if player.is_aflame else \
                                       ('deflame_crouch' if player.is_deflaming else \
                                       ('crouch_trans' if player.animations and player.animations.get('crouch_trans') else 'crouch')))
                set_player_state(player, next_state_to_crouch, current_time_ms)
        action_events["crouch"] = False # Consume event

    # Uncrouch with "Up/Jump" key for keyboard only
    if not is_pygame_joystick_input and action_events.get("up") and active_mappings.get("jump") == active_mappings.get("up"): 
        if player.is_crouching and player.can_stand_up(platforms_list):
            player_intends_horizontal_move_after_uncrouch_key = player.is_trying_to_move_left or player.is_trying_to_move_right
            next_state_after_uncrouch_key = ('burning' if player.is_aflame else \
                                            ('deflame' if player.is_deflaming else \
                                            ('run' if player_intends_horizontal_move_after_uncrouch_key else 'idle')))
            set_player_state(player, next_state_after_uncrouch_key, current_time_ms)
            action_events["jump"] = False # Don't also jump if uncrouching with up key
        action_events["up"] = False # Consume the 'up' event in this specific case

    # Jump Logic
    if action_events.get("jump"): 
        can_initiate_jump_action = not (player.is_attacking or player.is_dashing or
                                         player.is_rolling or player.is_sliding or
                                         player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost'])
        if not is_on_fire_visual: # If not on fire, hit stun blocks jump
            if player.state == 'hit': can_initiate_jump_action = False
            if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration):
                can_initiate_jump_action = False

        if can_initiate_jump_action:
            # Can always attempt to stand up from crouch, jump if successful
            can_actually_execute_jump = not player.is_crouching or \
                (hasattr(player, 'can_stand_up') and player.can_stand_up(platforms_list))

            if player.is_crouching and can_actually_execute_jump: # If uncrouched to jump
                 player.is_crouching = False # Manually set here as set_player_state below might not imply it for 'jump'
                 if player.is_aflame: set_player_state(player, 'burning', current_time_ms)
                 elif player.is_deflaming: set_player_state(player, 'deflame', current_time_ms)
            
            if can_actually_execute_jump: # If successfully uncrouched or was already standing
                if player.on_ground:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH); set_player_state(player, 'jump', current_time_ms); player.on_ground = False
                elif player.on_ladder:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8)
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1))
                    player.on_ladder = False; set_player_state(player, 'jump', current_time_ms)
                elif player.can_wall_jump and player.touching_wall != 0:
                    player.vel.setY(C.PLAYER_JUMP_STRENGTH)
                    player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)) # Push off wall
                    player.facing_right = not player.facing_right # Turn away from wall
                    set_player_state(player, 'jump', current_time_ms)
                    player.can_wall_jump = False; player.touching_wall = 0;
        action_events["jump"] = False # Consume event

    # Other abilities
    can_perform_other_abilities_now = not is_on_fire_visual and not is_stunned_or_busy_general and not player.on_ladder
    
    player_intends_horizontal_move_for_attack = player.is_trying_to_move_left or player.is_trying_to_move_right
    is_player_actually_moving_slow_for_attack = abs(getattr(player.vel, 'x', lambda: 0.0)()) < 0.5 # Threshold for "no movement"

    if action_events.get("attack1") and can_perform_other_abilities_now: 
        if player.is_crouching:
            player.attack_type = 4 # Crouch attack
            set_player_state(player, 'crouch_attack', current_time_ms)
        else:
            player.attack_type = 1 # Standard attack 1
            nm_key = 'attack_nm'; moving_key = 'attack'; chosen_attack_state = moving_key
            # Prefer no-movement variant if not intending to move AND actually slow
            if (not player_intends_horizontal_move_for_attack and is_player_actually_moving_slow_for_attack) and \
               player.animations and player.animations.get(nm_key): chosen_attack_state = nm_key
            # Fallback to NM if moving variant doesn't exist but NM does
            elif not (player.animations and player.animations.get(moving_key)) and \
                 (player.animations and player.animations.get(nm_key)):
                chosen_attack_state = nm_key
            set_player_state(player, chosen_attack_state, current_time_ms)
        action_events["attack1"] = False 
    
    if action_events.get("attack2") and can_perform_other_abilities_now: 
        if player.is_crouching: # Assuming crouch attack is the same for attack1/2 inputs
            player.attack_type = 4
            set_player_state(player, 'crouch_attack', current_time_ms)
        else:
            player.attack_type = 2 # Standard attack 2
            nm_key = 'attack2_nm'; moving_key = 'attack2'; chosen_attack_state = moving_key
            if (not player_intends_horizontal_move_for_attack and is_player_actually_moving_slow_for_attack) and \
               player.animations and player.animations.get(nm_key): chosen_attack_state = nm_key
            elif not (player.animations and player.animations.get(moving_key)) and \
                 (player.animations and player.animations.get(nm_key)):
                chosen_attack_state = nm_key
            set_player_state(player, chosen_attack_state, current_time_ms)
        action_events["attack2"] = False

    if action_events.get("dash") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: 
        set_player_state(player, 'dash', current_time_ms); action_events["dash"] = False
    if action_events.get("roll") and can_perform_other_abilities_now and player.on_ground and not player.is_crouching: 
        set_player_state(player, 'roll', current_time_ms); action_events["roll"] = False
    
    if action_events.get("interact") and not is_on_fire_visual: # Interact not blocked by general busy/stun, but by fire
        interact_event_consumed_by_ladder = False
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False # Cannot be crouching on ladder
            set_player_state(player, 'ladder_idle', current_time_ms); interact_event_consumed_by_ladder = True
        elif player.on_ladder: 
            set_player_state(player, 'fall' if not player.on_ground else 'idle', current_time_ms); interact_event_consumed_by_ladder = True
        
        if interact_event_consumed_by_ladder:
            action_events["interact"] = False # Consume event if used for ladder
        # If not consumed by ladder, it remains True for other systems (e.g., chest)
    
    # Projectiles
    if can_perform_other_abilities_now: # General check for projectile firing
        for proj_idx in range(1, 8):
            proj_action_key = f"projectile{proj_idx}"
            proj_fire_method_name = f"fire_{C.PROJECTILE_CONFIG_ORDER[proj_idx-1]}" if proj_idx-1 < len(C.PROJECTILE_CONFIG_ORDER) else None
            if proj_fire_method_name and action_events.get(proj_action_key) and hasattr(player, proj_fire_method_name):
                getattr(player, proj_fire_method_name)(); action_events[proj_action_key] = False

    # --- 8. Final State Adjustments based on Movement (mostly handled by player_movement_physics.py now) ---
    # This section could be simplified or removed if movement physics handles all these transitions.
    # For now, keeping some basic ground/air transitions.
    
    is_in_non_interruptible_action_by_movement = player.is_attacking or player.is_dashing or \
                                                 player.is_rolling or player.is_sliding or \
                                                 player.is_taking_hit or player.state in [
                                                     'jump','turn','death','death_nm','hit','jump_fall_trans',
                                                     'crouch_trans', 'slide_trans_start','slide_trans_end',
                                                     'wall_hang','wall_slide',
                                                     'ladder_idle','ladder_climb', 'frozen', 'defrost',
                                                     'petrified', 'smashed'
                                                 ]

    if not is_in_non_interruptible_action_by_movement or is_on_fire_visual: # Allow fire states to transition
        if player.on_ladder:
            # Ladder state transitions are now mostly handled by interact and movement physics
            pass
        elif player.on_ground:
            # Grounded state transitions (idle/run/crouch) also largely handled by physics or crouch toggle
            pass
        else: # Airborne
            if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                # Wall slide logic is now more in physics/state handler based on vel.y > C.PLAYER_WALL_SLIDE_SPEED * 0.5
                pass
            elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and \
               player.state not in ['jump','jump_fall_trans', 'wall_slide', 'wall_hang']: # Avoid interrupting jump or wall states
                target_fall_state = ('burning' if player.is_aflame else ('deflame' if player.is_deflaming else 'fall'))
                if player.state != target_fall_state and player.animations and player.animations.get(target_fall_state):
                    set_player_state(player, target_fall_state, current_time_ms)
            # If just fell off and not in jump/fall, might transition to idle (player_movement_physics handles this)

    if debug_this_frame and input_print_limiter.can_log(f"p_input_final_{player.player_id}"):
        active_events_str = ", ".join([f"{k.replace('_pressed_event','')}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        debug(f"{player_id_str} InputHandler Final: state='{player.state}', "
              f"is_trying_L/R=({player.is_trying_to_move_left}/{player.is_trying_to_move_right}), "
              f"is_crouching={player.is_crouching}, "
              f"acc.x={player.acc.x():.2f}, vel.y={player.vel.y():.2f}, "
              f"Events Fired: [{active_events_str}]")

    return action_events