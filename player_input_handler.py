# player_input_handler.py
# -*- coding: utf-8 -*-
"""
version 2.0.0 (PySide6 Refactor)
Handles processing of player input and translating it to actions,
expecting pre-processed Qt key states and joystick states.
"""
from typing import Dict, List, Any, Tuple, Optional

# PySide6 (Qt) specific key enum if needed for comparison, but config uses strings
# from PySide6.QtCore import Qt as QtKeys

import constants as C
import config as game_config # Assumes config.py mappings are strings for keys,
                             # and for joysticks, uses 'inputs' lib event codes.
from utils import PrintLimiter
# joystick_handler is not directly used here anymore for polling.
# Its role is to provide GamePad instances to MainWindow.

input_print_limiter = PrintLimiter(default_limit=20, default_period=5.0)

# This function now expects more processed input from the main Qt application loop
def process_player_input_logic(
    player: Any,  # Forward reference or import Player if cycle is broken
    qt_keys_held: Dict[str, bool],  # e.g., {"A": True, "Space": False}
    # For joysticks, we expect a pre-processed state dictionary
    # This state would be maintained by MainWindow based on events from the 'inputs' library GamePad object
    joystick_current_states: Dict[str, Any], # Example: {"axes": {"ABS_X": 0.8}, "buttons": {"BTN_SOUTH": True}, "hats": {"HAT0": (1,0)}}
    discrete_action_triggers: Dict[str, bool],  # e.g., {"jump": True, "attack1": True, "reset": False}
    active_mappings: Dict[str, Any], # Player's specific key/button mappings from config.py
    platforms_list: List[Any], # For can_stand_up check
    current_game_ticks_ms: int
) -> Dict[str, bool]: # Returns newly generated events, or potentially modifies player directly and returns empty

    if not player._valid_init: return {}

    player_id_str = f"P{player.player_id}"

    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    is_stunned_or_busy_general = (player.is_taking_hit and current_game_ticks_ms - player.hit_timer < player.hit_duration) or \
                                  player.is_attacking or player.is_dashing or player.is_rolling or \
                                  player.is_sliding or player.state == 'turn'

    # action_state is for continuous "held" actions like movement directions
    action_state = {action: False for action in game_config.GAME_ACTIONS}
    # action_events_generated_here can be used if this function needs to generate new one-shot events
    action_events_generated_here = {action: False for action in game_config.GAME_ACTIONS}


    # --- Part 1: Process universal discrete action triggers (reset, pause) ---
    # These are passed directly from MainWindow's event handling
    if discrete_action_triggers.get("reset"):
        action_events_generated_here["reset"] = True # Pass through
    if discrete_action_triggers.get("pause"):
        action_events_generated_here["pause"] = True # Pass through


    # --- Part 2: Populate action_state for continuous inputs (movement/aiming) ---
    is_joystick_input_type = player.control_scheme and player.control_scheme.startswith("joystick_")

    if not is_joystick_input_type: # Keyboard
        for action_name in ["left", "right", "up", "down"]:
            # active_mappings from config.py uses string keys like "A", "W", "Left", "Right"
            key_str_from_config = active_mappings.get(action_name)
            if key_str_from_config and qt_keys_held.get(key_str_from_config, False):
                action_state[action_name] = True
    else: # Joystick
        # Joystick states (axes, buttons, hats) are passed in `joystick_current_states`
        # The keys in this dict should correspond to `inputs` library event codes (e.g., "ABS_X", "BTN_SOUTH")
        # `active_mappings` for joysticks should map game actions to these event codes and expected values.
        # Example: "left": {"type": "axis", "id": "ABS_X", "value": -1, "threshold": 0.7}
        #          "jump": {"type": "button", "id": "BTN_SOUTH"}
        
        current_joystick_axes = joystick_current_states.get("axes", {})
        current_joystick_buttons = joystick_current_states.get("buttons", {})
        current_joystick_hats = joystick_current_states.get("hats", {})

        for action_name in ["left", "right", "up", "down"]:
            mapping_details = active_mappings.get(action_name)
            if isinstance(mapping_details, dict):
                m_type = mapping_details.get("type")
                m_id = mapping_details.get("id") # This should be the event code string, e.g., "ABS_X"
                m_value_prop = mapping_details.get("value") # Expected direction/value
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)

                if m_type == "axis" and m_id in current_joystick_axes:
                    axis_val = current_joystick_axes[m_id]
                    if isinstance(m_value_prop, (int, float)):
                        if m_value_prop < 0 and axis_val < -m_threshold: action_state[action_name] = True
                        elif m_value_prop > 0 and axis_val > m_threshold: action_state[action_name] = True
                elif m_type == "button" and m_id in current_joystick_buttons:
                    if current_joystick_buttons[m_id]: # If button is currently pressed
                        action_state[action_name] = True
                elif m_type == "hat" and m_id in current_joystick_hats: # m_id for hat could be e.g. "HAT0"
                                                                     # and m_value_prop is tuple e.g. (0,1)
                    hat_tuple_from_state = current_joystick_hats[m_id] # e.g. (x_val, y_val)
                    if hat_tuple_from_state == m_value_prop:
                        action_state[action_name] = True
    
    # Store previous joystick "up" state for "just pressed" logic if needed for jump specifically by joystick analog up
    # This part is tricky if "up" for movement and "jump" for discrete action are mapped to the same joystick control.
    # The `discrete_action_triggers` should ideally handle "jump" events.
    # For now, this specific joystick jump logic based on analog stick 'up' is removed,
    # relying on MainWindow to send a "jump" trigger in `discrete_action_triggers`.
    # setattr(player, '_prev_joystick_up_state', action_state.get("up", False))


    # Update player's intent flags based on action_state
    player.is_trying_to_move_left = action_state["left"]
    player.is_trying_to_move_right = action_state["right"]
    player.is_holding_climb_ability_key = action_state["up"]
    player.is_holding_crouch_ability_key = action_state["down"]
    
    # Aiming logic (remains the same, consumes action_state)
    aim_x, aim_y = 0.0, 0.0
    if action_state["left"]: aim_x = -1.0
    elif action_state["right"]: aim_x = 1.0
    if action_state["up"]: aim_y = -1.0
    elif action_state["down"] or player.is_crouching: aim_y = 1.0
    
    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.setX(aim_x); player.fireball_last_input_dir.setY(aim_y) # Use QPointF methods
    elif player.fireball_last_input_dir.isNull() or (player.fireball_last_input_dir.x() == 0 and player.fireball_last_input_dir.y() == 0) :
        player.fireball_last_input_dir.setX(1.0 if player.facing_right else -1.0)
        player.fireball_last_input_dir.setY(0.0)


    if is_fully_action_blocked:
        player.acc.setX(0) # Ensure no movement if fully blocked
        return action_events_generated_here # Only pass through reset/pause

    # --- Part 3 & 4: Apply discrete actions and update player logic ---
    # Discrete actions are now primarily driven by `discrete_action_triggers`
    
    player.acc.setX(0) # Reset horizontal acceleration
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right
    
    can_control_horizontal = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or 
        player.state in ['turn','hit','death','death_nm','wall_climb','wall_climb_nm','wall_hang', 'frozen', 'defrost']
    )
    if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit':
        can_control_horizontal = False

    if can_control_horizontal:
        target_accel_x = 0.0
        current_facing_right = player.facing_right
        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            target_accel_x = -C.PLAYER_ACCEL
            current_facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            target_accel_x = C.PLAYER_ACCEL
            current_facing_right = True
        player.acc.setX(target_accel_x)

        if player.facing_right != current_facing_right and player.on_ground and \
           not player.is_crouching and not player.is_attacking and \
           player.state in ['idle','run'] and not is_on_fire_visual:
            player.set_state('turn')
        player.facing_right = current_facing_right


    if player.on_ladder:
        player.acc.setX(0) 
        if player.is_holding_climb_ability_key: player.vel.setY(-C.PLAYER_LADDER_CLIMB_SPEED)
        elif player.is_holding_crouch_ability_key: player.vel.setY(C.PLAYER_LADDER_CLIMB_SPEED)
        else: player.vel.setY(0)

    # CROUCH LOGIC
    if discrete_action_triggers.get("crouch"):
        if player.is_crouching:
            if player.can_stand_up(platforms_list):
                player.is_crouching = False
                next_fire_state = 'burning' if player.is_aflame else ('deflame' if player.is_deflaming else None)
                if next_fire_state: player.set_state(next_fire_state)
                else: player.set_state('run' if player_intends_horizontal_move else 'idle')
        else:
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                player.is_crouching = True
                if player.is_aflame: player.set_state('aflame_crouch')
                elif player.is_deflaming: player.set_state('deflame_crouch')
                else: player.set_state('crouch_trans' if player.animations.get('crouch_trans') else 'crouch')

    if player.is_crouching and player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch': player.set_state('crouch_walk')
    elif player.is_crouching and not player_intends_horizontal_move:
        if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch')
        elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
        elif not (player.is_aflame or player.is_deflaming) and player.state == 'crouch_walk': player.set_state('crouch')

    # JUMP LOGIC
    can_initiate_jump_action = not (player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                 player.state in ['turn', 'death', 'death_nm', 'frozen', 'defrost'])
    if not is_on_fire_visual:
        if player.state == 'hit': can_initiate_jump_action = False
        if player.is_taking_hit and (current_game_ticks_ms - player.hit_timer < player.hit_duration): can_initiate_jump_action = False
            
    if discrete_action_triggers.get("jump") and can_initiate_jump_action:
        can_actually_execute_jump = not player.is_crouching or player.can_stand_up(platforms_list)
        if player.is_crouching and can_actually_execute_jump:
            player.is_crouching = False 
            if player.is_aflame: player.set_state('burning')
            elif player.is_deflaming: player.set_state('deflame')

        if can_actually_execute_jump:
            if player.on_ground:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH); player.set_state('jump'); player.on_ground = False
            elif player.on_ladder:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8)
                player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1))
                player.on_ladder = False; player.set_state('jump')
            elif player.can_wall_jump and player.touching_wall != 0:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH)
                player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall)) 
                player.facing_right = not player.facing_right 
                player.set_state('jump'); player.can_wall_jump = False
                player.touching_wall = 0; player.wall_climb_timer = 0

    # Other abilities
    can_perform_other_abilities = not is_on_fire_visual and not is_stunned_or_busy_general

    if discrete_action_triggers.get("attack1") and can_perform_other_abilities:
        player.attack_type = 4 if player.is_crouching else 1
        anim_key = 'crouch_attack' if player.is_crouching else ('attack' if player_intends_horizontal_move else 'attack_nm')
        player.set_state(anim_key)
    if discrete_action_triggers.get("attack2") and can_perform_other_abilities:
        if player.is_crouching and not player.is_attacking: player.attack_type = 4; player.set_state('crouch_attack')
        elif not player.is_attacking: player.attack_type = 2; player.set_state('attack2' if player_intends_horizontal_move else 'attack2_nm')
    
    if discrete_action_triggers.get("dash") and player.on_ground and can_perform_other_abilities and not player.is_crouching: player.set_state('dash')
    if discrete_action_triggers.get("roll") and player.on_ground and can_perform_other_abilities and not player.is_crouching: player.set_state('roll')

    if discrete_action_triggers.get("interact") and not is_on_fire_visual:
        if player.can_grab_ladder and not player.on_ladder:
            player.is_crouching = False; player.on_ladder = True; player.vel.setY(0); player.vel.setX(0); player.on_ground=False
            player.touching_wall=0; player.can_wall_jump=False; player.wall_climb_timer=0
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.on_ladder = False; player.set_state('fall' if not player.on_ground else 'idle')

    if can_perform_other_abilities:
        if discrete_action_triggers.get("projectile1"): player.fire_fireball()
        elif discrete_action_triggers.get("projectile2"): player.fire_poison()
        elif discrete_action_triggers.get("projectile3"): player.fire_bolt()
        elif discrete_action_triggers.get("projectile4"): player.fire_blood()
        elif discrete_action_triggers.get("projectile5"): player.fire_ice()
        elif discrete_action_triggers.get("projectile6"): player.fire_shadow()
        elif discrete_action_triggers.get("projectile7"): player.fire_grey()

    # Auto-state updates
    is_in_non_interruptible_state_for_auto = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost']
    
    if not is_in_non_interruptible_state_for_auto or is_on_fire_visual:
        if player.on_ladder:
            if abs(player.vel.y()) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y()) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
             if player.is_crouching:
                 if player_intends_horizontal_move:
                     if player.is_aflame and player.state not in ['burning_crouch', 'aflame_crouch']: player.set_state('burning_crouch')
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch_walk': player.set_state('crouch_walk')
                 else:
                     if player.is_aflame and player.state not in ['aflame_crouch', 'burning_crouch']: player.set_state('burning_crouch')
                     elif player.is_deflaming and player.state != 'deflame_crouch': player.set_state('deflame_crouch')
                     elif not (player.is_aflame or player.is_deflaming) and player.state != 'crouch': player.set_state('crouch')
             elif player_intends_horizontal_move:
                 if player.is_aflame and player.state not in ['burning','aflame']: player.set_state('burning')
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'run': player.set_state('run')
             else:
                 if player.is_aflame and player.state not in ['aflame', 'burning']: player.set_state('burning')
                 elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                 elif not (player.is_aflame or player.is_deflaming) and player.state != 'idle': player.set_state('idle')
        else: # In air
             if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                 wall_time = current_game_ticks_ms
                 climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and \
                                  wall_time - player.wall_climb_timer > player.wall_climb_duration)
                 if player.vel.y() > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                 elif player.is_holding_climb_ability_key and abs(player.vel.x()) < 1.0 and not climb_expired and player.animations.get('wall_climb'):
                     if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                 else:
                     if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
             elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                  if player.is_aflame and player.state not in ['burning','aflame']: player.set_state('burning')
                  elif player.is_deflaming and player.state != 'deflame': player.set_state('deflame')
                  elif not (player.is_aflame or player.is_deflaming) and player.state != 'fall': player.set_state('fall')
             elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual:
                  if player.state != 'idle': player.set_state('idle')

    return action_events_generated_here