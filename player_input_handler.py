# player_input_handler.py
# -*- coding: utf-8 -*-
"""
Version 2.1.2 (Enhanced debug for movement/jump, clearer can_control checks)
Handles processing of player input (Qt keyboard events, Pygame joystick polling)
and translating it to game actions.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QPointF # Added QPointF for aim_dir

import constants as C
import config as game_config
from utils import PrintLimiter
from logger import debug, warning # Assuming logger is configured

input_print_limiter = PrintLimiter(default_limit=10, default_period=3.0)

_input_handler_start_time = time.monotonic()
def get_input_handler_ticks():
    return int((time.monotonic() - _input_handler_start_time) * 1000)


def process_player_input_logic_pyside(
    player: Any,
    qt_keys_held_snapshot: Dict[Qt.Key, bool],
    qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
    active_mappings: Dict[str, Any],
    platforms_list: List[Any],
    joystick_data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:

    if not player._valid_init:
        return {}

    current_time_ms = get_input_handler_ticks()
    player_id_str = f"P{player.player_id}"

    is_pygame_joystick_input = player.control_scheme and player.control_scheme.startswith("joystick_pygame_")
    action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    # --- Determine Player's Intent (Continuous Inputs) ---
    player.is_trying_to_move_left = False
    player.is_trying_to_move_right = False
    player.is_holding_climb_ability_key = False
    player.is_holding_crouch_ability_key = False

    if not is_pygame_joystick_input: # Keyboard
        for action_name in ["left", "right", "up", "down"]:
            qt_key_for_action = active_mappings.get(action_name)
            if isinstance(qt_key_for_action, Qt.Key) and qt_keys_held_snapshot.get(qt_key_for_action, False):
                if action_name == "left": player.is_trying_to_move_left = True
                elif action_name == "right": player.is_trying_to_move_right = True
                elif action_name == "up": player.is_holding_climb_ability_key = True
                elif action_name == "down": player.is_holding_crouch_ability_key = True
    elif joystick_data: # Pygame Joystick
        current_axes = joystick_data.get('axes', {})
        current_hats = joystick_data.get('hats', {})
        current_buttons_held = joystick_data.get('buttons_current', {})

        for action_name in ["left", "right", "up", "down"]:
            mapping_details = active_mappings.get(action_name)
            if not isinstance(mapping_details, dict): continue

            m_type, m_id = mapping_details.get("type"), mapping_details.get("id")
            m_axis_direction = mapping_details.get("value") # For axes/hats
            m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
            is_input_active = False

            if m_type == "axis":
                axis_val = current_axes.get(m_id, 0.0)
                if (m_axis_direction == -1 and axis_val < -m_threshold) or \
                   (m_axis_direction == 1 and axis_val > m_threshold):
                    is_input_active = True
            elif m_type == "hat":
                hat_val_target = tuple(m_axis_direction) # m_axis_direction is (x,y) for hats
                if tuple(current_hats.get(m_id, (0,0))) == hat_val_target and hat_val_target != (0,0):
                    is_input_active = True
            elif m_type == "button": # Some might map movement to buttons
                if current_buttons_held.get(m_id, False):
                    is_input_active = True
            
            if is_input_active:
                if action_name == "left": player.is_trying_to_move_left = True
                elif action_name == "right": player.is_trying_to_move_right = True
                elif action_name == "up": player.is_holding_climb_ability_key = True
                elif action_name == "down": player.is_holding_crouch_ability_key = True

    # --- Update Aiming Direction ---
    aim_x, aim_y = 0.0, 0.0
    if player.is_trying_to_move_left: aim_x = -1.0
    elif player.is_trying_to_move_right: aim_x = 1.0
    if player.is_holding_climb_ability_key: aim_y = -1.0
    elif player.is_holding_crouch_ability_key or player.is_crouching: aim_y = 1.0

    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.setX(aim_x)
        player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (player.fireball_last_input_dir.x() == 0 and player.fireball_last_input_dir.y() == 0):
        player.fireball_last_input_dir.setX(1.0 if player.facing_right else -1.0)
        player.fireball_last_input_dir.setY(0.0)

    # --- Determine Discrete Action Events (Button Presses) ---
    if not is_pygame_joystick_input: # Keyboard events
        for event_type, key_code_from_event, _is_auto_repeat in qt_key_event_data_this_frame:
            if event_type == QKeyEvent.Type.KeyPress:
                for action_name, mapped_qt_key in active_mappings.items():
                    if mapped_qt_key == key_code_from_event:
                        action_events[action_name] = True
                        if action_name == "up" and active_mappings.get("jump") == mapped_qt_key: action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == mapped_qt_key) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == mapped_qt_key):
                             action_events["crouch"] = True
                        break
    elif joystick_data: # Pygame Joystick events
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {})
        current_hats = joystick_data.get('hats',{}) # Assuming hats can also trigger discrete events
        
        for action_name, mapping_details in active_mappings.items():
            if not isinstance(mapping_details, dict): continue
            m_type = mapping_details.get("type")
            m_id = mapping_details.get("id")
            
            if m_type == "button":
                if current_buttons.get(m_id, False) and not prev_buttons.get(m_id, False):
                    action_events[action_name] = True
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "button": action_events["jump"] = True
                    if (action_name == "down" and active_mappings.get("down", {}).get("id") == m_id and active_mappings.get("down",{}).get("type") == "button") or \
                       (action_name == "crouch" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "button"):
                         action_events["crouch"] = True
            elif m_type == "hat" and action_name in getattr(C, 'JOYSTICK_HAT_EVENT_ACTIONS', []):
                 hat_val_target = tuple(mapping_details.get("value", (0,0)))
                 current_hat_val = tuple(current_hats.get(m_id, (0,0)))
                 # This needs a "previous hat state" to detect a press, which is complex.
                 # For now, if the hat is active and it's meant for an event, we trigger it.
                 # This might mean continuous events if hat is held. Refine if needed.
                 if current_hat_val == hat_val_target and hat_val_target != (0,0):
                     action_events[action_name] = True
                     if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "hat": action_events["jump"] = True
                     if (action_name == "down" and active_mappings.get("down", {}).get("id") == m_id and active_mappings.get("down",{}).get("type") == "hat") or \
                        (action_name == "crouch" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "hat"):
                          action_events["crouch"] = True


    # --- Universal Actions (Reset, Pause) ---
    # These are already in action_events if they occurred (from keyboard or joystick discrete press)

    # --- Early Exit for Fully Blocked States ---
    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    if is_fully_action_blocked:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0)
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- Horizontal Movement Logic ---
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right
    if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): # Check if acc and setX exist
        player.acc.setX(0.0) # Default to no horizontal acceleration
    else:
        warning(f"{player_id_str} Input: Player object missing 'acc' or 'acc.setX'. Horizontal movement will fail.")
        return action_events # Cannot proceed with movement logic

    # Determine if player can control horizontal movement
    can_control_horizontal = not (
        player.is_dashing or player.is_rolling or player.is_sliding or player.on_ladder or
        (player.is_attacking and player.state.endswith('_nm')) or # No movement if attacking without movement variant
        player.state in ['turn', 'hit', 'death', 'death_nm', 'wall_climb', 'wall_climb_nm', 'wall_hang', 'frozen', 'defrost']
    )
    if player.is_taking_hit and not is_on_fire_visual and player.state == 'hit': # Stricter block if flinching and not on fire
        can_control_horizontal = False

    # DEBUG PRINT for Horizontal Control Gate
    if input_print_limiter.can_print(f"horiz_control_gate_{player.player_id}"):
        debug(f"{player_id_str} Horizontal Control Gate: can_control_horizontal={can_control_horizontal} "
              f"(dashing={player.is_dashing}, rolling={player.is_rolling}, sliding={player.is_sliding}, "
              f"on_ladder={player.on_ladder}, attacking_nm={(player.is_attacking and player.state.endswith('_nm'))}, "
              f"state='{player.state}', taking_hit_active={player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration)})")


    if can_control_horizontal:
        accel_val = C.PLAYER_ACCEL
        if player.is_aflame: accel_val *= getattr(C, 'PLAYER_AFLAME_ACCEL_MULTIPLIER', 1.0)
        elif player.is_deflaming: accel_val *= getattr(C, 'PLAYER_DEFLAME_ACCEL_MULTIPLIER', 1.0)

        if player.is_trying_to_move_left and not player.is_trying_to_move_right:
            player.acc.setX(-accel_val)
            if player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = False
        elif player.is_trying_to_move_right and not player.is_trying_to_move_left:
            player.acc.setX(accel_val)
            if not player.facing_right and player.on_ground and not player.is_crouching and \
               not player.is_attacking and player.state in ['idle','run'] and not is_on_fire_visual:
                player.set_state('turn')
            player.facing_right = True
        
        # DEBUG PRINT for Applied Acceleration
        if player.acc.x() != 0 and input_print_limiter.can_print(f"horiz_accel_applied_{player.player_id}"):
            debug(f"{player_id_str} Horizontal Accel Applied: acc.x = {player.acc.x():.2f} (Intent L/R: {player.is_trying_to_move_left}/{player.is_trying_to_move_right})")
    elif input_print_limiter.can_print(f"no_horiz_control_{player.player_id}"):
         debug(f"{player_id_str} No Horizontal Control: acc.x remains {player.acc.x():.2f}")


    # --- Vertical Movement on Ladders ---
    if player.on_ladder:
        player.acc.setX(0) # No horizontal accel on ladder
        if player.is_holding_climb_ability_key: player.vel.setY(-C.PLAYER_LADDER_CLIMB_SPEED)
        elif player.is_holding_crouch_ability_key: player.vel.setY(C.PLAYER_LADDER_CLIMB_SPEED)
        else: player.vel.setY(0)

    # --- Crouching Logic ---
    if action_events.get("crouch"): # Discrete event for "S" or crouch button
        if player.is_crouching:
            if player.can_stand_up(platforms_list):
                # player.is_crouching = False; # set_state will handle this
                next_f_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else ('run' if player_intends_horizontal_move else 'idle')
                player.set_state(next_f_state)
                debug(f"{player_id_str} Input: Uncrouched via crouch event. New state: {player.state}")
        else: # Not crouching, try to crouch
            can_crouch_now = player.on_ground and not player.on_ladder and not player.is_sliding and \
                               not (player.is_dashing or player.is_rolling or player.is_attacking or \
                                    player.state in ['turn','hit','death','death_nm', 'frozen', 'defrost', 'jump'])
            if can_crouch_now:
                # player.is_crouching = True; # set_state will handle this
                next_f_state = ('aflame_crouch' if player.is_aflame else 'deflame_crouch') if (player.is_aflame or player.is_deflaming) else ('crouch_trans' if player.animations and player.animations.get('crouch_trans') else 'crouch')
                player.set_state(next_f_state)
                debug(f"{player_id_str} Input: Crouched via crouch event. New state: {player.state}")
    
    # Uncrouch with "up" key if applicable (typically keyboard specific)
    if action_events.get("up") and not is_pygame_joystick_input:
        qt_key_for_up = active_mappings.get("up")
        qt_key_for_jump = active_mappings.get("jump")
        if qt_key_for_up is not None and qt_key_for_up == qt_key_for_jump: # 'up' and 'jump' are the same key
            if player.is_crouching and player.can_stand_up(platforms_list):
                # player.is_crouching = False; # set_state handles this
                player_intends_horizontal_move_after_uncrouch = player.is_trying_to_move_left or player.is_trying_to_move_right
                next_f_state_after_uncrouch = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else ('run' if player_intends_horizontal_move_after_uncrouch else 'idle')
                player.set_state(next_f_state_after_uncrouch)
                action_events["jump"] = False # Consume jump if 'up' was used to uncrouch
                debug(f"{player_id_str} Input: Uncrouched via 'up' (jump) key. New state: {player.state}")


    # --- Jump Logic ---
    can_initiate_jump_action = not (player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding) and \
                               player.state not in ['turn', 'death', 'death_nm', 'frozen', 'defrost']
    if not is_on_fire_visual: # Fire states might allow jumping, but hit stun does not
        if player.state == 'hit': can_initiate_jump_action = False
        if player.is_taking_hit and (current_time_ms - player.hit_timer < player.hit_duration): can_initiate_jump_action = False

    if action_events.get("jump") and can_initiate_jump_action:
        can_actually_execute_jump = not player.is_crouching # If crouched, "up/jump" key might have uncrouched already
        
        if can_actually_execute_jump:
            if player.on_ground:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH); player.set_state('jump'); player.on_ground = False
                debug(f"{player_id_str} Input: Jumped from ground.")
            elif player.on_ladder:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH * 0.8); player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 0.5 * (1 if player.facing_right else -1))
                player.on_ladder = False; player.set_state('jump')
                debug(f"{player_id_str} Input: Jumped from ladder.")
            elif player.can_wall_jump and player.touching_wall != 0:
                player.vel.setY(C.PLAYER_JUMP_STRENGTH); player.vel.setX(C.PLAYER_RUN_SPEED_LIMIT * 1.5 * (-player.touching_wall))
                player.facing_right = not player.facing_right; player.set_state('jump')
                player.can_wall_jump = False; player.touching_wall = 0; player.wall_climb_timer = 0
                debug(f"{player_id_str} Input: Wall jumped.")
        elif input_print_limiter.can_print(f"jump_blocked_crouch_{player.player_id}"):
            debug(f"{player_id_str} Input: Jump attempted but blocked by crouch state (possibly uncrouched instead).")
    elif action_events.get("jump") and not can_initiate_jump_action and input_print_limiter.can_print(f"jump_blocked_state_{player.player_id}"):
         debug(f"{player_id_str} Input: Jump event occurred, but can_initiate_jump_action is False (state: {player.state}).")


    # --- Other Abilities (Attack, Dash, Roll, Interact, Projectiles) ---
    is_stunned_or_busy_for_other_abilities = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                             player.is_attacking or player.is_dashing or player.is_rolling or \
                                             player.is_sliding or player.state in ['turn', 'frozen', 'defrost']
    can_perform_other_abilities = not is_on_fire_visual and not is_stunned_or_busy_for_other_abilities

    if action_events.get("attack1") and can_perform_other_abilities:
        player.set_state('attack') # set_state in Player will handle attack_type and nm variants
    if action_events.get("attack2") and can_perform_other_abilities:
        player.set_state('attack2')
    if action_events.get("dash") and can_perform_other_abilities and player.on_ground and not player.is_crouching:
        player.set_state('dash')
    if action_events.get("roll") and can_perform_other_abilities and player.on_ground and not player.is_crouching:
        player.set_state('roll')
    
    if action_events.get("interact") and not is_on_fire_visual: # Interact not blocked by busy states like attack
        if player.can_grab_ladder and not player.on_ladder:
            player.set_state('ladder_idle')
        elif player.on_ladder:
            player.set_state('fall' if not player.on_ground else 'idle')

    if can_perform_other_abilities: # Projectiles
        if action_events.get("projectile1") and hasattr(player, 'fire_fireball'): player.fire_fireball()
        if action_events.get("projectile2") and hasattr(player, 'fire_poison'): player.fire_poison()
        # ... add all other projectiles
        if action_events.get("projectile3") and hasattr(player, 'fire_bolt'): player.fire_bolt()
        if action_events.get("projectile4") and hasattr(player, 'fire_blood'): player.fire_blood()
        if action_events.get("projectile5") and hasattr(player, 'fire_ice'): player.fire_ice()
        if action_events.get("projectile6") and hasattr(player, 'fire_shadow'): player.fire_shadow()
        if action_events.get("projectile7") and hasattr(player, 'fire_grey'): player.fire_grey()


    # --- Final State Adjustments based on Movement/Context (if no major action overrides) ---
    is_in_non_interruptible_action_by_movement = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost'
                                   ]
    
    if not is_in_non_interruptible_action_by_movement or is_on_fire_visual:
        if player.on_ladder:
            if abs(player.vel.y()) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y()) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
            if player.is_crouching:
                crouch_fire_prefix = 'burning' if player.is_aflame else ('deflame' if player.is_deflaming else '')
                target_crouch_state = (crouch_fire_prefix + ('_crouch' if crouch_fire_prefix else 'crouch_walk')) if player_intends_horizontal_move else \
                                      (crouch_fire_prefix + ('_crouch' if crouch_fire_prefix else 'crouch'))
                if player.state != target_crouch_state and player.animations and player.animations.get(target_crouch_state):
                    player.set_state(target_crouch_state)
            elif player_intends_horizontal_move:
                target_run_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'run'
                if player.state != target_run_state and player.animations and player.animations.get(target_run_state):
                    player.set_state(target_run_state)
            else: # Not moving horizontally on ground
                target_idle_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'idle'
                if player.state != target_idle_state and player.animations and player.animations.get(target_idle_state):
                    player.set_state(target_idle_state)
        else: # In air
            if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                wall_time = get_input_handler_ticks()
                climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and wall_time - player.wall_climb_timer > player.wall_climb_duration)
                if player.vel.y() > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                elif player.is_holding_climb_ability_key and abs(player.vel.x()) < 1.0 and not climb_expired and player.animations and player.animations.get('wall_climb'):
                    if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                else: # Not actively climbing up, default to slide/hang
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
            elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                target_fall_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'fall'
                if player.state != target_fall_state and player.animations and player.animations.get(target_fall_state):
                    player.set_state(target_fall_state)
            elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual and player.state != 'idle': # Catch-all for weird air states
                player.set_state('idle')


    if input_print_limiter.can_print(f"p_input_final_{player.player_id}"):
        debug(f"{player_id_str} Final Input State: is_trying_L/R=({player.is_trying_to_move_left}/{player.is_trying_to_move_right}), "
              f"acc.x={player.acc.x():.2f}, state='{player.state}', "
              f"Events Fired: { {k:v for k,v in action_events.items() if v} }")

    return action_events