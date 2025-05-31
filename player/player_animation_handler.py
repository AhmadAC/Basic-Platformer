# player/player_animation_handler.py
# -*- coding: utf-8 -*-
"""
Handles player animation selection and frame updates for PySide6.
Correctly anchors the player's rect when height changes.
MODIFIED: Corrected animation priority for frozen/aflame states.
NOTE: Gravity for dead players is handled by the physics simulation.
MODIFIED: Improved crouch animation logic and attack animation selection.
MODIFIED: Uses local import for set_player_state to mitigate circular dependencies.
"""
# version 2.0.7 (Local import for set_player_state)

import time
import sys 
import os 
from typing import List, Optional, Any 

# PySide6 imports
from PySide6.QtGui import QPixmap, QImage, QTransform, QColor, QFont
from PySide6.QtCore import QPointF, QRectF, Qt, QSize

# Game imports
import main_game.constants as C
from main_game.utils import PrintLimiter


# --- Logger and specific logging utilities Setup ---
import logging # Keep this for the fallback logger definition

# Define fallback logger functions FIRST
_anim_fallback_logger = logging.getLogger(__name__ + "_anim_fallback")
if not _anim_fallback_logger.hasHandlers():
    _fallback_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_fallback_player_anim")
    if not os.path.exists(_fallback_log_dir):
        try: os.makedirs(_fallback_log_dir)
        except OSError: pass 
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
ENABLE_DETAILED_PHYSICS_LOGS = False 
def log_player_physics(player: Any, message_tag: str, extra_info: Any = ""): pass 

try:
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
    
    # Safely get velocities, defaulting to 0 if attributes are missing
    vel_x = 0.0
    if hasattr(player, 'vel') and player.vel is not None and hasattr(player.vel, 'x') and callable(player.vel.x):
        vel_x = player.vel.x()
    vel_y = 0.0
    if hasattr(player, 'vel') and player.vel is not None and hasattr(player.vel, 'y') and callable(player.vel.y):
        vel_y = player.vel.y()
    
    animations_available = hasattr(player, 'animations') and player.animations is not None

    # Player status flags
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
    touching_wall = getattr(player, 'touching_wall', 0) # 0: no wall, -1: left, 1: right


    # --- HIGHEST PRIORITY: Terminal Visual States ---
    if is_petrified:
        was_crouching_at_petrify = getattr(player, 'was_crouching_when_petrified', False)
        if is_stone_smashed:
            return 'smashed_crouch' if was_crouching_at_petrify and animations_available and animations_available.get('smashed_crouch') else 'smashed'
        else:
            return 'petrified_crouch' if was_crouching_at_petrify and animations_available and animations_available.get('petrified_crouch') else 'petrified'

    if is_dead:
        is_still_nm = abs(vel_x) < 0.5 and abs(vel_y) < 1.0 
        key_variant = 'death_nm' if is_still_nm and animations_available and animations_available.get('death_nm') else 'death'
        return key_variant if animations_available and animations_available.get(key_variant) else \
               ('death' if animations_available and animations_available.get('death') else 'idle') 

    # --- Next Priority: Overriding Status Effects (Zapped, Frozen before Fire) ---
    if is_zapped: return 'zapped' if animations_available and animations_available.get('zapped') else 'idle'
    if is_frozen: return 'frozen' if animations_available and animations_available.get('frozen') else 'idle'
    if is_defrosting: return 'defrost' if animations_available and animations_available.get('defrost') else \
                             ('frozen' if animations_available and animations_available.get('frozen') else 'idle')

    # --- Fire Status Effects (Consider crouch) ---
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

    # --- Action States (Hit, Attack - consider crouch for attack) ---
    if current_logical_state == 'hit':
        return 'hit' if animations_available and animations_available.get('hit') else 'idle'

    # Post-attack pause check
    post_attack_pause_timer_val = getattr(player, 'post_attack_pause_timer', 0)
    if post_attack_pause_timer_val > 0 and get_current_ticks_monotonic() < post_attack_pause_timer_val:
        return 'idle' 

    if is_attacking:
        attack_type = getattr(player, 'attack_type', 0)
        if attack_type == 4 or current_logical_state == 'crouch_attack': 
            return 'crouch_attack' if animations_available and animations_available.get('crouch_attack') else \
                   ('crouch' if is_crouching and animations_available and animations_available.get('crouch') else 'idle') 
        
        base_key = ''
        if attack_type == 1: base_key = 'attack'
        elif attack_type == 2: base_key = 'attack2'
        elif attack_type == 3: base_key = 'attack_combo'
        
        if base_key:
            is_intentionally_moving_lr_anim = getattr(player, 'is_trying_to_move_left', False) or \
                                              getattr(player, 'is_trying_to_move_right', False)
            is_player_actually_moving_slow_anim = abs(vel_x) < 0.5 

            use_nm_variant = (not is_intentionally_moving_lr_anim and is_player_actually_moving_slow_anim)

            nm_variant_key = f"{base_key}_nm"
            moving_variant_key = base_key

            if use_nm_variant and animations_available and animations_available.get(nm_variant_key):
                return nm_variant_key
            elif animations_available and animations_available.get(moving_variant_key): 
                return moving_variant_key
            elif animations_available and animations_available.get(nm_variant_key): 
                return nm_variant_key 
            else: return 'idle' 
    
    # Other specific action states
    if current_logical_state in ['dash', 'roll', 'slide', 'slide_trans_start', 'slide_trans_end', 'turn', 'crouch_trans']:
        return current_logical_state if animations_available and animations_available.get(current_logical_state) else 'idle'

    # --- Movement States (Ladder, Wall, Air, Ground) ---
    if on_ladder:
        return 'ladder_climb' if abs(vel_y) > 0.1 else 'ladder_idle' 

    if touching_wall != 0 and not on_ground: 
        if current_logical_state == 'wall_slide':
            return 'wall_slide' if animations_available and animations_available.get('wall_slide') else 'fall'
        if current_logical_state in ['wall_hang', 'wall_climb', 'wall_climb_nm']:
             return current_logical_state if animations_available and animations_available.get(current_logical_state) else 'fall'


    if not on_ground: 
        if current_logical_state == 'jump':
            return 'jump' if animations_available and animations_available.get('jump') else 'fall'
        if current_logical_state == 'jump_fall_trans': 
            return 'jump_fall_trans' if animations_available and animations_available.get('jump_fall_trans') else 'fall'
        return 'fall' if animations_available and animations_available.get('fall') else 'idle' 

    # Grounded states (Crouch, Run, Idle)
    if is_crouching: 
        if current_logical_state in ['crouch', 'crouch_walk'] and animations_available and animations_available.get(current_logical_state):
            return current_logical_state
        player_is_intending_to_move_lr_crouch = getattr(player, 'is_trying_to_move_left', False) or \
                                                getattr(player, 'is_trying_to_move_right', False)
        crouch_key_variant = 'crouch_walk' if player_is_intending_to_move_lr_crouch else 'crouch'
        return crouch_key_variant if animations_available and animations_available.get(crouch_key_variant) else \
               ('crouch' if animations_available and animations_available.get('crouch') else 'idle') 

    # Standing movement
    player_is_intending_to_move_lr_stand = getattr(player, 'is_trying_to_move_left', False) or \
                                           getattr(player, 'is_trying_to_move_right', False)
    if player_is_intending_to_move_lr_stand: 
        return 'run' if animations_available and animations_available.get('run') else 'idle'

    # Absolute fallback
    if animations_available and animations_available.get('idle'): return 'idle'
    # If 'idle' itself is missing (should be caught by initial load check), this is a problem
    warning(f"PlayerAnimHandler ({player_id_log}): No valid animation key determined, and 'idle' missing. This is critical.")
    return 'idle' # Last resort


def advance_frame_and_handle_state_transitions(player: Any, current_animation_frames_list: List[QPixmap], current_time_ms: int, current_animation_key: str):
    # --- LOCAL IMPORT to break circular dependency ---
    try:
        from .player_state_handler import set_player_state
    except ImportError:
        critical("PLAYER_ANIM_HANDLER (advance_frame): Failed to import set_player_state locally.")
        def set_player_state(player_arg: Any, new_state_arg: str, current_game_time_ms_param: Optional[int] = None):
            if hasattr(player_arg, 'state'): player_arg.state = new_state_arg
            warning(f"FALLBACK set_player_state used in player_animation_handler for P{getattr(player_arg, 'player_id', '?')} to {new_state_arg}. CROUCH WILL BE BROKEN.")
    # --- END LOCAL IMPORT ---

    if not current_animation_frames_list or not current_animation_frames_list[0] or current_animation_frames_list[0].isNull():
        warning(f"PlayerAnimHandler: advance_frame called with empty/invalid frames_list for key '{current_animation_key}'. ID: P{getattr(player, 'player_id', 'N/A')}")
        player.current_frame = 0
        return

    ms_per_frame = C.ANIM_FRAME_DURATION
    if player.is_attacking and player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'): # Attack Type 2 (e.g. secondary attack)
        ms_per_frame = int(C.ANIM_FRAME_DURATION * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)

    # --- Handle static or special-cased animations ---
    if player.is_petrified and not player.is_stone_smashed:
        player.current_frame = 0; return # Petrified (whole) holds first frame
    if player.is_frozen:
        player.current_frame = 0 
        if len(current_animation_frames_list) > 1 and current_animation_key == 'frozen':
            player.current_frame = len(current_animation_frames_list) -1
        return
    # Smashed stone and Zapped animations are handled by standard frame advancement below

    # Death animation holds last frame once finished (and not petrified)
    if player.is_dead and player.death_animation_finished and not player.is_petrified:
        player.current_frame = len(current_animation_frames_list) - 1 if current_animation_frames_list else 0
        return

    # --- Standard Frame Advancement ---
    if current_time_ms - player.last_anim_update > ms_per_frame:
        player.last_anim_update = current_time_ms
        player.current_frame += 1

        if player.current_frame >= len(current_animation_frames_list):
            # --- Handle Animation End ---
            if player.is_dead and not player.is_petrified: # Regular death animation finished
                player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                player.death_animation_finished = True
                return # Death anim finished, no further state transitions from here

            elif player.is_stone_smashed: # Smashed stone animation finished
                player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
                # death_animation_finished for smashed stone is handled by status_effects based on duration
                return

            # --- Non-looping animations that transition to other states ---
            non_looping_anim_keys_with_transitions = [
                'attack', 'attack_nm', 'attack2', 'attack2_nm', 'attack_combo', 'attack_combo_nm',
                'crouch_attack', 'dash', 'roll', 'slide', 'hit', 'turn', 'jump',
                'jump_fall_trans', 'crouch_trans', 'slide_trans_start', 'slide_trans_end'
            ]
            # Define keys that hold their last frame (visual only, logic handled elsewhere)
            non_looping_hold_last_frame_keys = ['deflame', 'deflame_crouch', 'defrost'] # 'aflame' etc. are looping

            is_transitional_anim = current_animation_key in non_looping_anim_keys_with_transitions
            is_hold_last_frame_anim = current_animation_key in non_looping_hold_last_frame_keys

            if is_transitional_anim:
                next_state_after_transition = player.state # Default to no change
                player_is_intending_to_move_lr = getattr(player, 'is_trying_to_move_left', False) or \
                                                 getattr(player, 'is_trying_to_move_right', False)

                # Determine next logical state based on current animation
                if current_animation_key == 'jump':
                    next_state_after_transition = 'jump_fall_trans' if player.animations and player.animations.get('jump_fall_trans') else 'fall'
                elif current_animation_key == 'jump_fall_trans':
                    next_state_after_transition = 'fall'
                elif current_animation_key == 'hit':
                    player.is_taking_hit = False # Clear hit flag as animation ends
                    if player.is_aflame: next_state_after_transition = 'aflame_crouch' if player.is_crouching else 'burning'
                    elif player.is_deflaming: next_state_after_transition = 'deflame_crouch' if player.is_crouching else 'deflame'
                    else: next_state_after_transition = 'idle' if player.on_ground and not player.on_ladder else 'fall'
                elif current_animation_key == 'turn':
                    next_state_after_transition = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_attack':
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    next_state_after_transition = 'crouch' 
                elif 'attack' in current_animation_key: # Generic attack end
                    player.is_attacking = False; player.attack_type = 0; player.can_combo = False
                    if player.on_ladder: next_state_after_transition = 'ladder_idle'
                    elif not player.on_ground: next_state_after_transition = 'fall'
                    else: next_state_after_transition = 'run' if player_is_intending_to_move_lr else 'idle'
                elif current_animation_key == 'crouch_trans': # Transition from standing to crouch completed
                    next_state_after_transition = 'crouch_walk' if player_is_intending_to_move_lr else 'crouch'
                elif current_animation_key == 'slide' or current_animation_key == 'slide_trans_end':
                    player.is_sliding = False
                    next_state_after_transition = 'crouch' # End in crouch
                elif current_animation_key == 'slide_trans_start':
                    next_state_after_transition = 'slide'
                elif current_animation_key == 'dash':
                    player.is_dashing = False
                    next_state_after_transition = 'idle' if player.on_ground else 'fall'
                elif current_animation_key == 'roll':
                    player.is_rolling = False
                    next_state_after_transition = 'idle' if player.on_ground else 'fall'
                
                if player.state == current_animation_key and next_state_after_transition != player.state:
                    set_player_state(player, next_state_after_transition, current_time_ms) # Pass time
                    return # State changed, animation will be updated by new state
                else: 
                    player.current_frame = 0 # Loop this (transitional) animation if no state change occurs
            
            elif is_hold_last_frame_anim:
                player.current_frame = len(current_animation_frames_list) - 1 # Hold last frame
            else: # Default: Loop animation (e.g., idle, run, fall, aflame, zapped)
                player.current_frame = 0
    
    # Safeguard frame index again after all logic
    if not current_animation_frames_list or player.current_frame < 0 or \
       player.current_frame >= len(current_animation_frames_list):
        player.current_frame = 0 # Default to first frame if index is somehow invalid


def update_player_animation(player: Any):
    qcolor_magenta = QColor(*(C.MAGENTA if hasattr(C, 'MAGENTA') else (255,0,255)))
    qcolor_red = QColor(*(C.RED if hasattr(C, 'RED') else (255,0,0)))
    qcolor_blue = QColor(*(C.BLUE if hasattr(C, 'BLUE') else (0,0,255)))
    qcolor_yellow = QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0)))
    
    if not getattr(player, '_valid_init', False) or not hasattr(player, 'animations') or not player.animations:
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_magenta) 
        return

    can_animate_now = (hasattr(player, 'alive') and player.alive()) or \
                      (getattr(player, 'is_dead', False) and not getattr(player, 'death_animation_finished', True) and not getattr(player, 'is_petrified', False)) or \
                      getattr(player, 'is_petrified', False) 

    if not can_animate_now: return

    current_time_ms = get_current_ticks_monotonic()
    determined_key_for_logic = determine_animation_key(player)

    # Get frames based on determined key
    current_frames_list: Optional[List[QPixmap]] = None
    if determined_key_for_logic == 'petrified': 
        current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
    elif determined_key_for_logic == 'smashed':
        current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
    elif player.animations: # Generic animation lookup
        current_frames_list = player.animations.get(determined_key_for_logic)


    is_current_animation_valid = True
    if not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull():
        is_current_animation_valid = False
    elif len(current_frames_list) == 1 and \
         determined_key_for_logic not in ['petrified', 'idle', 'run', 'fall', 'frozen', 'crouch', 'crouch_attack', 'ladder_idle', 'wall_hang']: 
        frame_pixmap = current_frames_list[0]
        if frame_pixmap.size() == QSize(30, 40): 
            qimg = frame_pixmap.toImage()
            if not qimg.isNull():
                pixel_color = qimg.pixelColor(0,0)
                if pixel_color == qcolor_red or pixel_color == qcolor_blue:
                    is_current_animation_valid = False 

    if not is_current_animation_valid:
        original_determined_key_before_fallback = determined_key_for_logic
        if determined_key_for_logic != 'idle': 
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"anim_frames_missing_P{player.player_id}_{determined_key_for_logic}"):
                warning(f"PlayerAnimHandler Warning (P{player.player_id}): Animation for key '{determined_key_for_logic}' (State: {player.state}) missing/placeholder. Attempting 'idle'.")
        
        determined_key_for_logic = 'idle'
        current_frames_list = player.animations.get('idle') if player.animations else None

        is_idle_still_invalid = not current_frames_list or not current_frames_list[0] or current_frames_list[0].isNull() or \
                                (len(current_frames_list) == 1 and current_frames_list[0].size() == QSize(30,40) and \
                                 (current_frames_list[0].toImage().pixelColor(0,0) == qcolor_red or \
                                  current_frames_list[0].toImage().pixelColor(0,0) == qcolor_blue))

        if is_idle_still_invalid:
            critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): Fallback 'idle' ALSO missing/placeholder! Visuals broken. Original key was '{original_determined_key_before_fallback}'.")
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(qcolor_magenta)
            return 

    if not current_frames_list: 
        critical(f"PlayerAnimHandler CRITICAL (P{player.player_id}): current_frames_list is None even after fallbacks. Key: '{determined_key_for_logic}'.")
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_blue) 
        return

    advance_frame_and_handle_state_transitions(player, current_frames_list, current_time_ms, determined_key_for_logic)

    render_key_for_final_image = determined_key_for_logic
    current_player_logical_state_after_advance = getattr(player, 'state', 'idle')
    if current_player_logical_state_after_advance != determined_key_for_logic and \
       not (getattr(player, 'is_petrified', False) and determined_key_for_logic in ['petrified', 'smashed']):
        new_render_key_candidate = determine_animation_key(player)
        if new_render_key_candidate != determined_key_for_logic:
            render_key_for_final_image = new_render_key_candidate
            # Update current_frames_list based on the new render_key
            if render_key_for_final_image == 'petrified':
                current_frames_list = [player.stone_crouch_image_frame if player.was_crouching_when_petrified else player.stone_image_frame]
            elif render_key_for_final_image == 'smashed':
                current_frames_list = player.stone_crouch_smashed_frames if player.was_crouching_when_petrified else player.stone_smashed_frames
            elif player.animations:
                new_frames_for_render = player.animations.get(render_key_for_final_image)
                if new_frames_for_render and new_frames_for_render[0] and not new_frames_for_render[0].isNull():
                    current_frames_list = new_frames_for_render
                elif not (current_frames_list and current_frames_list[0] and not current_frames_list[0].isNull()):
                    current_frames_list = player.animations.get('idle', [player.image] if player.image and not player.image.isNull() else [])


    if not current_frames_list or player.current_frame < 0 or player.current_frame >= len(current_frames_list):
        player.current_frame = 0 
        if not current_frames_list: 
            if hasattr(player, 'image') and player.image and not player.image.isNull():
                player.image.fill(QColor(*(C.YELLOW if hasattr(C, 'YELLOW') else (255,255,0))))
            return

    image_for_this_frame = current_frames_list[player.current_frame]
    if image_for_this_frame.isNull(): 
        critical(f"PlayerAnimHandler (P{player.player_id}): image_for_this_frame is NULL for key '{render_key_for_final_image}', frame {player.current_frame}.")
        if hasattr(player, 'image') and player.image and not player.image.isNull():
            player.image.fill(qcolor_magenta)
        return

    display_facing_right = player.facing_right
    if render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed':
        display_facing_right = player.facing_at_petrification 

    final_image_to_set = image_for_this_frame
    if not display_facing_right:
        if not (render_key_for_final_image == 'petrified' or render_key_for_final_image == 'smashed'):
            q_img = image_for_this_frame.toImage()
            if not q_img.isNull():
                final_image_to_set = QPixmap.fromImage(q_img.mirrored(True, False))
            
    image_content_has_changed = (not hasattr(player, 'image') or player.image is None) or \
                                (hasattr(player.image, 'cacheKey') and hasattr(final_image_to_set, 'cacheKey') and \
                                 player.image.cacheKey() != final_image_to_set.cacheKey()) or \
                                (player.image is not final_image_to_set) 

    facing_direction_for_flip_check = player.facing_at_petrification if (render_key_for_final_image in ['petrified', 'smashed']) else player.facing_right

    if image_content_has_changed or (player._last_facing_right != facing_direction_for_flip_check):
        old_rect_midbottom_qpointf = QPointF(player.rect.center().x(), player.rect.bottom()) if hasattr(player, 'rect') and player.rect else player.pos

        player.image = final_image_to_set 
        if hasattr(player, '_update_rect_from_image_and_pos') and callable(player._update_rect_from_image_and_pos):
            player._update_rect_from_image_and_pos(old_rect_midbottom_qpointf)
        else: 
            player.rect = QRectF(old_rect_midbottom_qpointf - QPointF(player.image.width()/2.0, float(player.image.height())), player.image.size())
        
        player._last_facing_right = facing_direction_for_flip_check 