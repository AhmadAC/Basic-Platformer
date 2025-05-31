# player/player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles animation selection and frame updates for Player instances using PySide6.
Includes zapped animation.
MODIFIED: Corrected logger import path.
MODIFIED: Ensures player.animations is checked to be a dictionary before using it.
MODIFIED: Fixed QColor initialization TypeError for qcolor_blue.
"""
# version 2.0.9 (Robust animation dict access, QColor fix)

import time
import sys
import os
from typing import List, Optional, Any

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor, QFont # Added QFont for potential placeholder text
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

# Game imports
import main_game.constants as C
from main_game.utils import PrintLimiter


# --- Logger and specific logging utilities Setup ---
import logging

_anim_fallback_logger = logging.getLogger(__name__ + "_anim_fallback")
if not _anim_fallback_logger.hasHandlers():
    _fallback_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_fallback_player_anim")
    if not os.path.exists(_fallback_log_dir):
        try: os.makedirs(_fallback_log_dir)
        except OSError: pass # Silently ignore if logs_fallback can't be created
    _fallback_log_file = os.path.join(_fallback_log_dir, "player_anim_fallback.log")

    _h_console = logging.StreamHandler(sys.stdout)
    _f_console = logging.Formatter('PLAYER_ANIM (FallbackConsole): %(levelname)s - %(message)s')
    _h_console.setFormatter(_f_console)
    _anim_fallback_logger.addHandler(_h_console)

    if os.path.exists(_fallback_log_dir):
        try:
            _h_file = logging.FileHandler(_fallback_log_file, mode='a')
            _f_file = logging.Formatter('%(asctime)s - PLAYER_ANIM (FallbackFile): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
            _h_file.setFormatter(_f_file)
            _anim_fallback_logger.addHandler(_h_file)
        except Exception:
            _anim_fallback_logger.warning("Could not create fallback file logger for player_animation_handler.")

    _anim_fallback_logger.setLevel(logging.DEBUG)
    _anim_fallback_logger.propagate = False

def _fb_debug(msg, *args, **kwargs): _anim_fallback_logger.debug(msg, *args, **kwargs)
def _fb_info(msg, *args, **kwargs): _anim_fallback_logger.info(msg, *args, **kwargs)
def _fb_warning(msg, *args, **kwargs): _anim_fallback_logger.warning(msg, *args, **kwargs)
def _fb_critical(msg, *args, **kwargs): _anim_fallback_logger.critical(msg, *args, **kwargs)
def _fb_error(msg, *args, **kwargs): _anim_fallback_logger.error(msg, *args, **kwargs)

# Assign fallbacks, then try to override with project logger
debug = _fb_debug
info = _fb_info
warning = _fb_warning
critical = _fb_critical
error = _fb_error
ENABLE_DETAILED_PHYSICS_LOGS = False # Fallback value
def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""): pass # Fallback stub

try:
    # This assumes logger.py is in main_game directory, relative to project root
    from main_game.logger import (
        ENABLE_DETAILED_PHYSICS_LOGS as _project_ENABLE_DETAILED_PHYSICS_LOGS,
        log_player_physics as _project_log_player_physics,
        debug as _project_debug,
        info as _project_info,
        warning as _project_warning,
        error as _project_error,
        critical as _project_critical
    )
    ENABLE_DETAILED_PHYSICS_LOGS = _project_ENABLE_DETAILED_PHYSICS_LOGS
    log_player_physics = _project_log_player_physics
    debug = _project_debug
    info = _project_info
    warning = _project_warning
    error = _project_error
    critical = _project_critical
    debug("PlayerAnimationHandler: Successfully aliased project's logger and detailed physics log settings.")
except ImportError:
    critical("CRITICAL PLAYER_ANIM_HANDLER: Failed to import logger/detailed physics settings from main_game.logger. Using fallbacks.")
# --- End Logger Setup ---


_start_time_player_anim_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns milliseconds since this module was loaded, for consistent timing."""
    return int((time.monotonic() - _start_time_player_anim_monotonic) * 1000)


def determine_animation_key(player: Any) -> str:
    player_id_log = getattr(player, 'player_id', 'Unknown')
    current_logical_state = getattr(player, 'state', 'idle')
    
    vel_x = 0.0
    if hasattr(player, 'vel') and player.vel is not None and hasattr(player.vel, 'x') and callable(player.vel.x):
        vel_x = player.vel.x()
    vel_y = 0.0
    if hasattr(player, 'vel') and player.vel is not None and hasattr(player.vel, 'y') and callable(player.vel.y):
        vel_y = player.vel.y()
    
    animations_dict = getattr(player, 'animations', None)
    animations_available = isinstance(animations_dict, dict) and animations_dict # Ensure it's a non-empty dict

    is_petrified = getattr(player, 'is_petrified', False)
    is_stone_smashed = getattr(player, 'is_stone_smashed', False)
    is_dead = getattr(player, 'is_dead', False)
    is_frozen = getattr(player, 'is_frozen', False)
    is_defrosting = getattr(player, 'is_defrosting', False)
    is_aflame = getattr(player, 'is_aflame', False)
    is_deflaming = getattr(player, 'is_deflaming', False)
    is_zapped = getattr(player, 'is_zapped', False)
    is_attacking = getattr(player, 'is_attacking', False)
    is_crouching = getattr(player, 'is_crouching', False)
    on_ground = getattr(player, 'on_ground', False)
    on_ladder = getattr(player, 'on_ladder', False)
    touching_wall = getattr(player, 'touching_wall', 0)


    # --- Highest Priority: Terminal/Overriding Visual States ---
    if is_petrified:
        was_crouching_at_petrify = getattr(player, 'was_crouching_when_petrified', False)
        if is_stone_smashed:
            return 'smashed_crouch' if was_crouching_at_petrify and animations_available and animations_available.get('smashed_crouch') else 'smashed'
        else:
            return 'petrified_crouch' if was_crouching_at_petrify and animations_available and animations_available.get('petrified_crouch') else 'petrified'

    if is_dead:
        is_still_nm = abs(vel_x) < 0.5 and abs(vel_y) < 1.0 # More lenient velocity check for "no movement"
        key_variant = 'death_nm' if is_still_nm and animations_available and animations_available.get('death_nm') else 'death'
        # Fallback to 'death' if 'death_nm' isn't available, then to 'idle' as absolute last resort
        return key_variant if animations_available and animations_available.get(key_variant) else \
               ('death' if animations_available and animations_available.get('death') else 'idle')

    # --- Next Priority: Other Major Status Effects ---
    if is_zapped: return 'zapped' if animations_available and animations_available.get('zapped') else 'idle'
    if is_frozen: return 'frozen' if animations_available and animations_available.get('frozen') else 'idle'
    if is_defrosting: return 'defrost' if animations_available and animations_available.get('defrost') else \
                             ('frozen' if animations_available and animations_available.get('frozen') else 'idle') # Show frozen if defrost anim missing

    # Aflame/Burning/Deflame has visual priority over normal actions if active
    if is_aflame:
        if is_crouching: return 'aflame_crouch' if animations_available and animations_available.get('aflame_crouch') else \
                                 ('burning_crouch' if animations_available and animations_available.get('burning_crouch') else \
                                 ('aflame' if animations_available and animations_available.get('aflame') else 'idle'))
        return 'burning' if animations_available and animations_available.get('burning') else \
               ('aflame' if animations_available and animations_available.get('aflame') else 'idle')
    if is_deflaming:
        if is_crouching: return 'deflame_crouch' if animations_available and animations_available.get('deflame_crouch') else \
                                  ('deflame' if animations_available and animations_available.get('deflame') else 'idle')
        return 'deflame' if animations_available and animations_available.get('deflame') else 'idle'

    # --- Action States ---
    if current_logical_state == 'hit': # Hit has priority over movement/idle if active
        return 'hit' if animations_available and animations_available.get('hit') else 'idle'

    # Post-attack pause check (should be idle during this)
    post_attack_pause_timer_val = getattr(player, 'post_attack_pause_timer', 0)
    if post_attack_pause_timer_val > 0 and get_current_ticks_monotonic() < post_attack_pause_timer_val:
        return 'idle'

    # Attacking state
    if is_attacking:
        attack_type = getattr(player, 'attack_type', 0)
        if attack_type == 4 or current_logical_state == 'crouch_attack': # Type 4 is crouch attack
            return 'crouch_attack' if animations_available and animations_available.get('crouch_attack') else \
                   ('crouch' if is_crouching and animations_available and animations_available.get('crouch') else 'idle')
        
        base_key = ''
        if attack_type == 1: base_key = 'attack'
        elif attack_type == 2: base_key = 'attack2'
        elif attack_type == 3: base_key = 'attack_combo'
        
        if base_key:
            # Determine if a "no movement" variant should be used
            is_intentionally_moving_lr_anim = getattr(player, 'is_trying_to_move_left', False) or \
                                              getattr(player, 'is_trying_to_move_right', False)
            is_player_actually_moving_slow_anim = abs(vel_x) < 0.5 # Threshold for "no movement"

            use_nm_variant = (not is_intentionally_moving_lr_anim and is_player_actually_moving_slow_anim)

            nm_variant_key = f"{base_key}_nm"
            moving_variant_key = base_key

            if use_nm_variant and animations_available and animations_available.get(nm_variant_key):
                return nm_variant_key
            elif animations_available and animations_available.get(moving_variant_key):
                return moving_variant_key
            elif animations_available and animations_available.get(nm_variant_key): # Fallback to NM if moving doesn't exist but NM does
                return nm_variant_key
            else: return 'idle' # Fallback if specific attack anim missing
    
    # Handle specific short-duration action states (dash, roll, slide, turn, crouch_trans)
    if current_logical_state in ['dash', 'roll', 'slide', 'slide_trans_start', 'slide_trans_end', 'turn', 'crouch_trans']:
        return current_logical_state if animations_available and animations_available.get(current_logical_state) else 'idle'

    # --- Movement States based on AI and Physics ---
    if on_ladder:
        return 'ladder_climb' if abs(vel_y) > 0.1 else 'ladder_idle'

    if touching_wall != 0 and not on_ground: # Touching wall and airborne
        if current_logical_state == 'wall_slide': # Explicitly set by physics for sliding down
            return 'wall_slide' if animations_available and animations_available.get('wall_slide') else 'fall'
        if current_logical_state in ['wall_hang', 'wall_climb', 'wall_climb_nm']: # Explicitly set
             return current_logical_state if animations_available and animations_available.get(current_logical_state) else 'fall'


    # Airborne states (not on ladder or wall handling specific state)
    if not on_ground:
        if current_logical_state == 'jump': # If player's logical state is 'jump'
            return 'jump' if animations_available and animations_available.get('jump') else 'fall'
        if current_logical_state == 'jump_fall_trans': # Specific transition animation
            return 'jump_fall_trans' if animations_available and animations_available.get('jump_fall_trans') else 'fall'
        # Default to 'fall' if airborne and not in a specific jump/transition state
        return 'fall' if animations_available and animations_available.get('fall') else 'idle' # Fallback to idle if 'fall' anim missing

    # Grounded states (not on ladder)
    if is_crouching:
        if current_logical_state in ['crouch', 'crouch_walk'] and animations_available and animations_available.get(current_logical_state):
            return current_logical_state
        # Fallback for crouch if specific state (like crouch_walk) anim missing
        player_is_intending_to_move_lr_crouch = getattr(player, 'is_trying_to_move_left', False) or \
                                                getattr(player, 'is_trying_to_move_right', False)
        crouch_key_variant = 'crouch_walk' if player_is_intending_to_move_lr_crouch else 'crouch'
        return crouch_key_variant if animations_available and animations_available.get(crouch_key_variant) else \
               ('crouch' if animations_available and animations_available.get('crouch') else 'idle')

    # Standing on ground, not crouching
    player_is_intending_to_move_lr_stand = getattr(player, 'is_trying_to_move_left', False) or \
                                           getattr(player, 'is_trying_to_move_right', False)
    if player_is_intending_to_move_lr_stand: # Player is trying to move
        return 'run' if animations_available and animations_available.get('run') else 'idle'

    # Default to current logical state if it has an animation and no other rule matched
    # (This is a safety net, ideally other rules cover most cases)
    if animations_available and animations_available.get(current_logical_state):
        return current_logical_state

    # Absolute fallback if no other state matched or logical state has no animation
    if animations_available and animations_available.get('idle'): return 'idle' # Corrected: Check get() before returning
    warning(f"PlayerAnimHandler ({player_id_log}): No valid animation key determined, and 'idle' missing. This is critical.")
    return 'idle' # Should ideally not be reached if 'idle' always exists.


def advance_frame_and_handle_state_transitions(player: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    # --- LOCAL IMPORT to break circular dependency ---
    try:
        from player.player_state_handler import set_player_state
    except ImportError:
        critical("PLAYER_ANIM_HANDLER (advance_frame): Failed to import set_player_state locally.")
        def set_player_state(player_arg: Any, new_state_arg: str, current_game_time_ms_param: Optional[int]=None): # type: ignore
            if hasattr(player_arg, 'state'): player_arg.state = new_state_arg
            warning(f"FALLBACK set_player_state used in player_animation_handler for P{getattr(player_arg, 'player_id', '?')} to {new_state_arg}. CROUCH WILL BE BROKEN.")
    # --- END LOCAL IMPORT ---

    if not current_animation_frames_list or not current_animation_frames_list[0] or current_animation_frames_list[0].isNull():
        # This case should ideally be caught by the fallback logic in update_player_animation before calling this.
        warning(f"PlayerAnimHandler: advance_frame called with empty/invalid frames_list for key '{current_animation_key}'. ID: P{getattr(player, 'player_id', 'N/A')}")
        player.current_frame = 0
        return

    # --- Handle special static or single-frame-hold animations ---
    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'):
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    # If petrified (not smashed), hold the first frame of the (potentially crouched) stone image
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0 # 'petrified' or 'petrified_crouch' are single-frame from Player's stone_image_frame
        return
    
    # If frozen, hold the last frame of 'frozen' animation (or first if single-frame)
    if player.is_frozen:
        player.current_frame = 0 # Default to first frame
        if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen': # Check if it's actually 'frozen' anim
            player.current_frame = len(current_animation_frames_list) - 1
        return

    # If dead and animation finished (and not petrified), hold last frame
    if player.is_dead and player.death_animation_finished and not player.is_petrified:
        player.current_frame = len(current_animation_frames_list) - 1 if current_animation_frames_list else 0
        return
    
    # Zapped animation is a loop, so it falls through to standard frame advancement

    # --- Standard Frame Advancement ---
    if current_time_ms - player.last_anim_update > ms_per_frame:
        player.last_anim_update = current_time_ms
        player.current_frame += 1

        if player.current_frame >= len(current_animation_frames_list):
            # --- Handle Animation End ---
            # Death/Smashed: Hold last frame and set death_animation_finished
            is_dead_not_petrified = player.is_dead and not player.is_petrified
            is_petrified_and_smashed = player.is_petrified and player.is_stone_smashed

            if is_dead_not_petrified or is_petrified_and_smashed:
                player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                player.death_animation_finished = True # Signal animation is done
                return # Stop further processing for this frame update for dead/smashed

            # Non-looping animations that transition to another state
            non_looping_anim_keys_with_transitions = [
                'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end'
            ]
            # Animations that hold their last frame (after one play-through)
            non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost']

            is_transitional_anim = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold_last_frame_anim = current_animation_key in non_looping_hold_last_frame_keys

            if is_transitional_anim:
                next_state_after_transition = player.state # Default to current state if no specific transition
                player_is_intending_to_move_lr = getattr(player, 'is_trying_to_move_left', False) or \
                                                 getattr(player, 'is_trying_to_move_right', False)

                if current_animation_key == 'jump':
                    next_state_after_transition = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans':
                    next_state_after_transition = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False # End hit stun logic
                    # Determine next state based on fire status and ground status
                    if player.is_aflame: next_state_after_transition = 'aflame_crouch' if player.is_crouching else 'burning'
                    elif player.is_deflaming: next_state_after_transition = 'deflame_crouch' if player.is_crouching else 'deflame'
                    else: next_state_after_transition = 'idle' if player.on_ground and not player.on_ladder else 'fall'
                elif current_animation_key == 'turn':
                    next_state_after_transition = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_attack':
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    next_state_after_transition = 'crouch'
                elif 'attack' in current_animation_key: # General attack finished
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    # Post-attack behavior (e.g., pause) is handled by player_state_handler or AI
                    if player.on_ladder: next_state_after_transition = 'ladder_idle'
                    elif not player.on_ground: next_state_after_transition = 'fall'
                    else: next_state_after_transition = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_trans':
                    # Should transition to 'crouch' or 'crouch_walk' based on intent
                    next_state_after_transition = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                    player.is_sliding = False
                    next_state_after_transition = 'crouch' # End in crouch state
                elif current_animation_key == 'slide_trans_start':
                    next_state_after_transition = 'slide'
                elif current_animation_key == 'dash':
                    player.is_dashing = False
                    next_state_after_transition = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll':
                    player.is_rolling = False
                    next_state_after_transition = 'idle' if player.on_ground else 'fall'
                
                # Only change state if the calculated next state is different
                if player.state == current_animation_key and next_state_after_transition != player.state:
                    player.set_state(next_state_after_transition, current_time_ms) # Use player.set_state()
                    return # State changed, animation will be re-evaluated next tick
                else: # If no state change, or was already in a different logical state, loop the current visual
                    player.current_frame = 0
            
            elif is_hold_last_frame_anim: # e.g., deflame, defrost
                player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
            
            else: # Default: Loop animation if it's not one of the above non-looping types
                player.current_frame = 0

    # Safeguard frame index again after all logic
    if not current_animation_frames_list or player.current_frame < 0 or \
       player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0


def update_player_animation(player: Any):
    # --- Define fallback QColors at the start of the function for clarity ---
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    # Corrected: Use getattr for C.BLUE or fallback tuple if C.BLUE is not defined
    qcolor_blue = QColor(*(getattr(C, 'BLUE') if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))
    
    # --- Initial validity checks ---
    if not getattr(player, '_valid_init', False) or not hasattr(player, 'animations') or not isinstance(player.animations, dict) or not player.animations:
        # If player is invalid or animations are not a loaded dictionary, set to placeholder and return.
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_magenta) # Fill existing image with magenta
        # else: # Player might not even have an image attribute yet if init failed very early
            # Consider creating a placeholder pixmap and assigning it to player.image if necessary
        return

    # --- Determine if animation update should proceed ---
    can_animate_now = (hasattr(player, 'alive') and player.alive()) or \
                      (getattr(player, 'is_dead', False) and not getattr(player, 'death_animation_finished', True) and not getattr(player, 'is_petrified', False)) or \
                      getattr(player, 'is_petrified', False) # Petrified (even smashed) can animate

    if not can_animate_now:
        return # Player is fully dead/inactive, or alive but in a state that shouldn't animate further

    current_time_ms = get_current_ticks_monotonic()
    determined_key_for_logic = determine_animation_key(player) # This gets the logical animation key

    # --- Retrieve animation frames based on the determined key ---
    current_frames_list: Optional[List[QPixmap]] = None
    if determined_key_for_logic == 'petrified':
        # Petrified uses specific frames from Player class, not animations dict
        current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_key_for_logic == 'smashed':
        current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations: # player.animations is confirmed to be a dict here
        current_frames_list = player.animations.get(determined_key_for_logic)

    # --- Validate frames, fallback to 'idle' if necessary ---
    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    # Check if it's a placeholder (e.g., 30x40 red/blue rect) unless it's a core static visual state
    elif len(current_frames_list) == 1 and \
         determined_key_for_logic not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'crouch', 'crouch_attack', 'ladder_idle', 'wall_hang']: # These can be single valid frames
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40): # Common placeholder size from assets.py
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue: # Check against defined fallbacks
                    is_current_animation_valid = False

    if not is_current_animation_valid:
        original_determined_key_before_fallback = determined_key_for_logic
        # Try falling back to 'idle'
        if determined_key_for_logic != 'idle': # Avoid re-logging if 'idle' was already the failing key
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_frames_missing_P{player.player_id}_{determined_key_for_logic}"):
                warning(f"PlayerAnimHandler Warning (P{player.player_id}): Animation for key '{determined_key_for_logic}' (State: {player.state}) missing/placeholder. Attempting 'idle'.")
        
        determined_key_for_logic = 'idle'
        current_frames_list = player.animations.get('idle') if player.animations else None # player.animations is a dict here

        # Check if 'idle' itself is also invalid
        is_idle_still_invalid = not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))

        if is_idle_still_invalid:
            critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): Fallback 'idle' ALSO missing/placeholder! Player visuals will be broken. Original key was '{original_determined_key_before_fallback}'.")
            # Set to a magenta placeholder if even idle fails
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(qcolor_magenta)
            return # Cannot proceed if idle is broken

    if not current_frames_list: # Should be caught by above, but as a final safeguard
        critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): current_frames_list is None even after fallbacks. Key: '{determined_key_for_logic}'.")
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_blue)
        return

    # --- Advance frame and handle state transitions based on animation end ---
    advance_frame_and_handle_state_transitions(player, current_frames_list, current_time_ms, determined_key_for_logic)

    # --- Re-determine animation key if logical state might have changed during advance_frame ---
    # This is important if advance_frame_and_handle_state_transitions changed player.state
    render_key_for_final_image = determined_key_for_logic # Start with the key used for frame advance
    current_player_logical_state_after_advance = getattr(player, 'state', 'idle')
    
    # If the logical state changed and it's not a terminal visual state like petrified/smashed
    if current_player_logical_state_after_advance != determined_key_for_logic and \
       not (player.is_petrified and determined_key_for_logic in ['petrified', 'smashed']):
        
        new_render_key_candidate = determine_animation_key(player) # Get the NEW correct key for rendering
        
        if new_render_key_candidate != determined_key_for_logic: # If it's truly different
            render_key_for_final_image = new_render_key_candidate
            # Update current_frames_list based on the new render_key for the final image assignment
            if render_key_for_final_image == 'petrified':
                current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_key_for_final_image == 'smashed':
                current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations: # animations is a dict here
                new_frames_for_render = player.animations.get(render_key_for_final_image)
                # Ensure new frames are valid before overriding current_frames_list
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                # Else, if new frames are bad, current_frames_list remains from the advance_frame logic
                # or if it too was bad, it would have fallen back to idle or error image.
                elif not (current_frames_list and current_frames_list[0] and not current_frames_list[0].isNull()): # If current_frames_list itself was bad
                    current_frames_list = player.animations.get('idle', [player.image] if player.image and not player.image.isNull() else [])


    # --- Final Safeguard and Image Assignment ---
    # Re-check current_frames_list after potential re-determination.
    if not current_frames_list or player.current_frame < 0 or player.current_frame >= len(current_frames_list):
        player.current_frame = 0 # Reset to first frame if index is out of bounds
        if not current_frames_list: # Absolute fallback if list became empty/None somehow
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(qcolor_yellow) # Use a different fallback color
            return

    image_for_this_frame = current_frames_list[player.current_frame]
    if image_for_this_frame.isNull(): # Should be caught earlier by validation
        critical(f"PlayerAnimHandler (P{player.player_id}): image_for_this_frame is NULL for key '{render_key_for_final_image}', frame {player.current_frame}. This should not happen.")
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_magenta)
        return

    # Determine facing for visual display (petrified state uses facing_at_petrification)
    display_facing_right = player.facing_right
    if render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed':
        display_facing_right = player.facing_at_petrification

    final_image_to_set = image_for_this_frame
    # Flip image if facing left (unless it's a static stone image, those are usually pre-rendered for one direction)
    if not display_facing_right:
        # Don't flip static stone images here if they are pre-rendered for one direction
        # The stone frames are already selected based on was_crouching_when_petrified and facing_at_petrification
        if not (render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed'):
            q_img = image_for_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            
    # Check if image content or visual facing direction actually changed
    image_content_has_changed = (not hasattr(player, 'image') or player.image is None) or \
                                (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                                 player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                                (player.image is not final_image_to_set) # Direct reference check for same QPixmap object

    # Compare current visual facing with the direction stored on the player object
    facing_direction_for_flip_check = player.facing_at_petrification if (render_key_for_final_image in ['petrified', 'smashed']) else player.facing_right

    if image_content_has_changed or (player._last_facing_right_visual != facing_direction_for_flip_check):
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom()) if hasattr(player, 'rect') and player.rect else player.pos

        player.image = final_image_to_set
        # Call the method to update rect based on new image and position
        # This method is defined in the Player class
        if hasattr(player, '_update_rect_from_image_and_pos') and callable(player._update_rect_from_image_and_pos):
            player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else: # Fallback rect update if method is missing (should not happen)
            player.rect = QRectF(old_rect_midbottom_qpointf - QPointF(player.image.width()/2.0, float(player.image.height())), player.image.size())
        
        player._last_facing_right_visual = facing_direction_for_flip_check # Store the visual facing used