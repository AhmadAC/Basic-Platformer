# player_input_handler.py
# -*- coding: utf-8 -*-
"""
Version 2.1.1 (Complete file for PySide6 with Qt.Key and Pygame Joystick)
Handles processing of player input (Qt keyboard events, Pygame joystick polling)
and translating it to game actions.
This handler directly calls player methods based on processed input.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from PySide6.QtGui import QKeyEvent # For type hinting Qt key events
from PySide6.QtCore import Qt       # For Qt.Key enum

import constants as C
import config as game_config # For GAME_ACTIONS and AXIS_THRESHOLD_DEFAULT
from utils import PrintLimiter # Assuming utils.py and PrintLimiter are available

input_print_limiter = PrintLimiter(default_limit=10, default_period=3.0) # Adjusted limit

_input_handler_start_time = time.monotonic()
def get_input_handler_ticks():
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _input_handler_start_time) * 1000)


def process_player_input_logic_pyside(
    player: Any,
    qt_keys_held_snapshot: Dict[Qt.Key, bool], # Keys are Qt.Key enums
    qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]], # Qt.Key enums
    active_mappings: Dict[str, Any], # For keyboard: values are Qt.Key; For joystick: values are dicts
    platforms_list: List[Any], # For player's can_stand_up check
    joystick_data: Optional[Dict[str, Any]] = None # Pygame joystick data
) -> Dict[str, bool]:
    """
    Processes player input and returns a dictionary of action events.
    'action_events' contains actions that occurred THIS FRAME (e.g., button press).
    Player's internal state (like is_trying_to_move_left) is updated for HELD states.
    This function also directly calls player methods (e.g., player.set_state, player.fire_fireball).
    """
    if not player._valid_init:
        return {}

    current_time_ms = get_input_handler_ticks()
    player_id_str = f"P{player.player_id}"

    # Determine if the current active device is a Pygame joystick
    is_pygame_joystick_input = player.control_scheme and player.control_scheme.startswith("joystick_pygame_")

    # --- Initialize action containers ---
    action_events: Dict[str, bool] = {action: False for action in game_config.GAME_ACTIONS}

    # --- Block input processing for certain player states ---
    is_on_fire_visual = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
    is_fully_action_blocked = player.is_dead or \
                              getattr(player, 'is_petrified', False) or \
                              getattr(player, 'is_frozen', False) or \
                              (getattr(player, 'is_defrosting', False) and player.state == 'defrost')
    
    is_stunned_or_busy_general = (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_duration) or \
                                  player.is_attacking or player.is_dashing or player.is_rolling or \
                                  player.is_sliding or player.state == 'turn'


    # --- 1. Process Keyboard Input (Qt Events) ---
    if not is_pygame_joystick_input:
        # Update player's continuous movement intent from Qt held keys
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        player.is_holding_crouch_ability_key = False

        for action_name in ["left", "right", "up", "down"]:
            qt_key_for_action = active_mappings.get(action_name) # This is now a Qt.Key enum
            if qt_key_for_action is not None and qt_keys_held_snapshot.get(qt_key_for_action, False):
                if action_name == "left": player.is_trying_to_move_left = True
                elif action_name == "right": player.is_trying_to_move_right = True
                elif action_name == "up": player.is_holding_climb_ability_key = True
                elif action_name == "down": player.is_holding_crouch_ability_key = True
        
        # Process discrete key press events from Qt
        for event_type, key_code_from_event, _is_auto_repeat in qt_key_event_data_this_frame:
            if event_type == QKeyEvent.Type.KeyPress: # Only process actual key presses
                for action_name, mapped_qt_key in active_mappings.items():
                    if mapped_qt_key == key_code_from_event: # Direct comparison of Qt.Key enums
                        action_events[action_name] = True
                        # Special handling for combined actions from one key
                        if action_name == "up" and active_mappings.get("jump") == mapped_qt_key:
                            action_events["jump"] = True
                        if (action_name == "down" and active_mappings.get("down") == mapped_qt_key) or \
                           (action_name == "crouch" and active_mappings.get("crouch") == mapped_qt_key):
                             action_events["crouch"] = True # "crouch" event for toggle logic
                        break # Found mapping for this key_code

    # --- 2. Process Pygame Joystick Input ---
    elif is_pygame_joystick_input and joystick_data:
        player.is_trying_to_move_left = False
        player.is_trying_to_move_right = False
        player.is_holding_climb_ability_key = False
        player.is_holding_crouch_ability_key = False

        current_axes = joystick_data.get('axes', {})
        current_buttons = joystick_data.get('buttons_current', {})
        prev_buttons = joystick_data.get('buttons_prev', {})
        current_hats = joystick_data.get('hats', {})

        for action_name, mapping_details in active_mappings.items():
            if not isinstance(mapping_details, dict): continue

            m_type = mapping_details.get("type")
            m_id = mapping_details.get("id")
            
            if m_type == "axis":
                axis_val = current_axes.get(m_id, 0.0)
                m_axis_direction = mapping_details.get("value")
                m_threshold = mapping_details.get("threshold", game_config.AXIS_THRESHOLD_DEFAULT)
                is_axis_active = (m_axis_direction == -1 and axis_val < -m_threshold) or \
                                 (m_axis_direction == 1 and axis_val > m_threshold)

                if action_name == "left": player.is_trying_to_move_left = is_axis_active
                elif action_name == "right": player.is_trying_to_move_right = is_axis_active
                elif action_name == "up": player.is_holding_climb_ability_key = is_axis_active
                elif action_name == "down": player.is_holding_crouch_ability_key = is_axis_active
                elif is_axis_active and action_name in getattr(C, 'JOYSTICK_AXIS_EVENT_ACTIONS', []):
                    action_events[action_name] = True
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "axis": action_events["jump"] = True
                    if (action_name == "down" and active_mappings.get("down", {}).get("id") == m_id and active_mappings.get("down",{}).get("type") == "axis") or \
                       (action_name == "crouch" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "axis"):
                         action_events["crouch"] = True


            elif m_type == "button":
                is_pressed_now = current_buttons.get(m_id, False)
                was_pressed_prev = prev_buttons.get(m_id, False)
                if is_pressed_now and not was_pressed_prev:
                    action_events[action_name] = True
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "button": action_events["jump"] = True
                    if (action_name == "down" and active_mappings.get("down", {}).get("id") == m_id and active_mappings.get("down",{}).get("type") == "button") or \
                       (action_name == "crouch" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "button"):
                         action_events["crouch"] = True

            elif m_type == "hat":
                hat_val_target = tuple(mapping_details.get("value", (0,0)))
                current_hat_val = tuple(current_hats.get(m_id, (0,0)))
                is_hat_active = (current_hat_val == hat_val_target and hat_val_target != (0,0))

                if action_name == "left": player.is_trying_to_move_left = is_hat_active or player.is_trying_to_move_left
                elif action_name == "right": player.is_trying_to_move_right = is_hat_active or player.is_trying_to_move_right
                elif action_name == "up": player.is_holding_climb_ability_key = is_hat_active or player.is_holding_climb_ability_key
                elif action_name == "down": player.is_holding_crouch_ability_key = is_hat_active or player.is_holding_crouch_ability_key
                elif is_hat_active and action_name in getattr(C, 'JOYSTICK_HAT_EVENT_ACTIONS', []):
                    action_events[action_name] = True
                    if action_name == "up" and active_mappings.get("jump", {}).get("id") == m_id and active_mappings.get("jump",{}).get("type") == "hat": action_events["jump"] = True
                    if (action_name == "down" and active_mappings.get("down", {}).get("id") == m_id and active_mappings.get("down",{}).get("type") == "hat") or \
                       (action_name == "crouch" and active_mappings.get("crouch", {}).get("id") == m_id and active_mappings.get("crouch",{}).get("type") == "hat"):
                         action_events["crouch"] = True

    # --- 3. Update Player Aiming Direction ---
    aim_x, aim_y = 0.0, 0.0
    if player.is_trying_to_move_left: aim_x = -1.0
    elif player.is_trying_to_move_right: aim_x = 1.0
    if player.is_holding_climb_ability_key: aim_y = -1.0
    elif player.is_holding_crouch_ability_key or player.is_crouching: aim_y = 1.0

    if aim_x != 0.0 or aim_y != 0.0:
        player.fireball_last_input_dir.setX(aim_x)
        player.fireball_last_input_dir.setY(aim_y)
    elif player.fireball_last_input_dir.isNull() or \
         (player.fireball_last_input_dir.x() == 0 and player.fireball_last_input_dir.y() == 0) :
        player.fireball_last_input_dir.setX(1.0 if player.facing_right else -1.0)
        player.fireball_last_input_dir.setY(0.0)

    # --- 4. Handle Universal Actions (Reset, Pause) already populated in action_events ---

    # --- 5. Return if Fully Action Blocked ---
    if is_fully_action_blocked:
        if hasattr(player, 'acc') and hasattr(player.acc, 'setX'): player.acc.setX(0)
        # Only allow reset/pause if fully blocked
        return {"reset": action_events.get("reset", False), "pause": action_events.get("pause", False)}

    # --- 6. Apply Action Events to Player Logic (if not busy) ---
    player_intends_horizontal_move = player.is_trying_to_move_left or player.is_trying_to_move_right

    # Crouching logic
    if action_events.get("crouch"):
        if player.is_crouching:
            if player.can_stand_up(platforms_list):
                player.set_state('idle') # Player.set_state handles is_crouching = False
        else: # Not crouching, try to crouch
            player.set_state('crouch') # Player.set_state handles can_crouch and is_crouching = True

    # Uncrouch with "up" key if "jump" and "up" are the same (for keyboard)
    # and if "up" event occurred
    if action_events.get("up") and not is_pygame_joystick_input:
        qt_key_for_up = active_mappings.get("up")
        qt_key_for_jump = active_mappings.get("jump")
        if qt_key_for_up is not None and qt_key_for_up == qt_key_for_jump: # Check if 'up' and 'jump' map to the same Qt.Key
            if player.is_crouching and player.can_stand_up(platforms_list):
                player.set_state('idle') # Uncrouch
                action_events["jump"] = False # Consume jump if up was used to uncrouch

    # Jump logic
    if action_events.get("jump"):
        player.set_state('jump')

    # Other abilities
    if not is_stunned_or_busy_general and not is_on_fire_visual:
        if action_events.get("attack1"): player.set_state('attack')
        if action_events.get("attack2"): player.set_state('attack2')
        if action_events.get("dash"): player.set_state('dash')
        if action_events.get("roll"): player.set_state('roll')
        
        if action_events.get("interact"):
            if player.can_grab_ladder and not player.on_ladder:
                player.set_state('ladder_idle')
            elif player.on_ladder:
                player.set_state('fall' if not player.on_ground else 'idle')

        # Projectiles
        if action_events.get("projectile1") and hasattr(player, 'fire_fireball'): player.fire_fireball()
        if action_events.get("projectile2") and hasattr(player, 'fire_poison'): player.fire_poison()
        if action_events.get("projectile3") and hasattr(player, 'fire_bolt'): player.fire_bolt()
        if action_events.get("projectile4") and hasattr(player, 'fire_blood'): player.fire_blood()
        if action_events.get("projectile5") and hasattr(player, 'fire_ice'): player.fire_ice()
        if action_events.get("projectile6") and hasattr(player, 'fire_shadow'): player.fire_shadow()
        if action_events.get("projectile7") and hasattr(player, 'fire_grey'): player.fire_grey()

    # Update visual state based on movement if no major action is overriding
    is_in_non_interruptible_action = player.is_attacking or player.is_dashing or player.is_rolling or player.is_sliding or \
                                   player.is_taking_hit or player.state in [
                                       'jump','turn','death','death_nm','hit','jump_fall_trans', 'crouch_trans',
                                       'slide_trans_start','slide_trans_end', 'wall_climb','wall_climb_nm',
                                       'wall_hang','wall_slide', 'ladder_idle','ladder_climb',
                                       'frozen', 'defrost'
                                   ]
    if not is_in_non_interruptible_action or is_on_fire_visual: # Fire visual states can override normal movement anims
        if player.on_ladder:
            if abs(player.vel.y()) > 0.1 and player.state != 'ladder_climb': player.set_state('ladder_climb')
            elif abs(player.vel.y()) <= 0.1 and player.state != 'ladder_idle': player.set_state('ladder_idle')
        elif player.on_ground:
            if player.is_crouching:
                crouch_state_suffix = '_crouch' if (player.is_aflame or player.is_deflaming) else ''
                fire_prefix = 'burning' if player.is_aflame else ('deflame' if player.is_deflaming else '')
                target_crouch_state = (fire_prefix + ('_crouch' if fire_prefix else 'crouch_walk')) if player_intends_horizontal_move else (fire_prefix + ('_crouch' if fire_prefix else 'crouch'))
                if player.state != target_crouch_state and player.animations and player.animations.get(target_crouch_state): player.set_state(target_crouch_state)
            elif player_intends_horizontal_move:
                target_run_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'run'
                if player.state != target_run_state and player.animations and player.animations.get(target_run_state): player.set_state(target_run_state)
            else: # Not moving horizontally on ground
                target_idle_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'idle'
                if player.state != target_idle_state and player.animations and player.animations.get(target_idle_state): player.set_state(target_idle_state)
        else: # In air
            if player.touching_wall != 0 and not player.is_dashing and not player.is_rolling and not is_on_fire_visual:
                wall_time = get_input_handler_ticks()
                climb_expired = (player.wall_climb_duration > 0 and player.wall_climb_timer > 0 and wall_time - player.wall_climb_timer > player.wall_climb_duration)
                if player.vel.y() > C.PLAYER_WALL_SLIDE_SPEED * 0.5 or climb_expired:
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True
                elif player.is_holding_climb_ability_key and abs(player.vel.x()) < 1.0 and not climb_expired and player.animations and player.animations.get('wall_climb'):
                    if player.state != 'wall_climb': player.set_state('wall_climb'); player.can_wall_jump = False
                else: # Not actively climbing up, default to slide/hang
                    if player.state != 'wall_slide': player.set_state('wall_slide'); player.can_wall_jump = True # Or wall_hang if conditions met
            elif player.vel.y() > getattr(C, 'MIN_SIGNIFICANT_FALL_VEL', 1.0) and player.state not in ['jump','jump_fall_trans']:
                target_fall_state = ('burning' if player.is_aflame else 'deflame') if (player.is_aflame or player.is_deflaming) else 'fall'
                if player.state != target_fall_state and player.animations and player.animations.get(target_fall_state): player.set_state(target_fall_state)
            elif player.state not in ['jump','jump_fall_trans','fall'] and not is_on_fire_visual and player.state != 'idle': # Catch-all for weird air states
                player.set_state('idle')


    # --- Logging input for debugging ---
    if input_print_limiter.can_print(f"p_input_{player.player_id}"):
        held_str = f"L:{player.is_trying_to_move_left} R:{player.is_trying_to_move_right} U:{player.is_holding_climb_ability_key} D:{player.is_holding_crouch_ability_key}"
        events_str = ", ".join([f"{k.replace('_pressed_event','P')}" for k, v in action_events.items() if v and k not in ["left","right","up","down"]])
        # debug(f"{player_id_str} Input: Held=[{held_str}] Events=[{events_str}] Aim=({player.fireball_last_input_dir.x():.1f},{player.fireball_last_input_dir.y():.1f})")

    return action_events