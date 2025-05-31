# assets.py
# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations from GIF files using Pillow and PySide6.
Includes a helper function `resource_path` to ensure correct asset pathing.
Stone/Smashed animations are now considered common and loaded by character base classes.
MODIFIED: Added 'zapped' animation to player and enemy loading.
MODIFIED: Log level for missing non-core animations changed to DEBUG for EnemyKnight.
"""
# version 2.0.6 (EnemyKnight missing animation logging refinement)

from PySide6.QtWidgets import (
    QApplication # Only needed if running this file directly for testing
)
import os
import sys
from PIL import Image # Pillow library for GIF processing
from typing import Dict, List, Optional, Tuple # For type hinting

from PySide6.QtGui import QPixmap, QImage, QColor, QPainter # PySide6 image/drawing tools
from PySide6.QtCore import QSize # For QSize

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ASSETS: logger.py not found. Falling back to print statements for logging.")
    # Fallback logger functions
    def info(msg: str, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg: str, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg: str, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg: str, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg: str, *args, **kwargs): print(f"CRITICAL: {msg}")

# --- Import Constants ---
try:
    import constants as C
    QCOLOR_RED = QColor(*C.RED)
    QCOLOR_BLACK = QColor(*C.BLACK)
    QCOLOR_BLUE = QColor(*C.BLUE)
    QCOLOR_YELLOW = QColor(*C.YELLOW)
    # MAPS_DIR_FOR_TESTING = C.MAPS_DIR # Removed, not used in this file
except ImportError:
    warning("Assets Warning: Failed to import 'constants'. Using fallback colors.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)
except AttributeError as e_attr:
    warning(f"Assets Warning: Imported 'constants' but an attribute is missing: {e_attr}. Using fallback colors.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)
except Exception as e_general_import:
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using fallback colors.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)


# --- Helper Function for PyInstaller Compatibility ---
def get_project_root_dev_mode() -> str:
    # Assumes assets.py is in the project root or a subfolder.
    # If in project root: os.path.dirname(os.path.abspath(__file__))
    # If in a subfolder (e.g., 'utils/'): os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Let's assume assets.py is in the project root for now, adjust if needed.
    if '__file__' in globals():
        return os.path.dirname(os.path.abspath(__file__))
    return os.getcwd() # Fallback if __file__ is not defined

def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS # type: ignore
    except AttributeError:
        # Not running in a PyInstaller bundle, use normal dev path
        base_path = get_project_root_dev_mode() # Use the robust dev mode root

    return os.path.join(base_path, relative_path)

# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[QPixmap]:
    loaded_frames: List[QPixmap] = []
    try:
        # Normalize path for better OS compatibility
        normalized_path = os.path.normpath(full_path_to_gif_file)
        pil_gif_image = Image.open(normalized_path)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                # Ensure RGBA format for QImage
                rgba_pil_frame = current_pil_frame.convert('RGBA')

                # Create QImage from Pillow frame data
                qimage_frame = QImage(rgba_pil_frame.tobytes(), rgba_pil_frame.width, rgba_pil_frame.height,
                                      rgba_pil_frame.width * 4, # Bytes per line (width * 4 bytes/pixel for RGBA)
                                      QImage.Format.Format_RGBA8888)

                if qimage_frame.isNull():
                    error(f"Assets Error: QImage conversion failed for frame {frame_index} in '{normalized_path}'.")
                    frame_index += 1
                    continue

                qpixmap_frame = QPixmap.fromImage(qimage_frame)
                if qpixmap_frame.isNull():
                    error(f"Assets Error: QPixmap conversion failed for frame {frame_index} in '{normalized_path}'.")
                    frame_index += 1
                    continue

                loaded_frames.append(qpixmap_frame)
                frame_index += 1
            except EOFError:
                # Reached end of GIF frames
                break
            except Exception as e_frame:
                error(f"Assets Error: Exception processing frame {frame_index} in '{normalized_path}': {e_frame}")
                frame_index += 1 # Try next frame
        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{normalized_path}'. Creating a RED placeholder.")
             placeholder_pixmap = QPixmap(30, 40)
             placeholder_pixmap.fill(QCOLOR_RED)
             painter = QPainter(placeholder_pixmap)
             painter.setPen(QCOLOR_BLACK)
             painter.drawRect(placeholder_pixmap.rect().adjusted(0,0,-1,-1))
             painter.end()
             return [placeholder_pixmap]
        return loaded_frames
    except FileNotFoundError:
        # This error is now logged by the calling functions (load_all_player_animations / load_enemy_animations)
        # as they have more context (e.g., which animation key it was for).
        # error(f"Assets Error: GIF file not found at provided path: '{normalized_path}'") # Duplicate if logged here
        pass # Let caller handle logging for FileNotFoundError
    except Exception as e_load:
        error(f"Assets Error: General exception loading GIF '{normalized_path}' with Pillow/Qt: {e_load}")
    
    # Fallback placeholder if any error occurred (except FileNotFoundError which is handled by caller)
    placeholder_pixmap_on_error = QPixmap(30, 40)
    placeholder_pixmap_on_error.fill(QCOLOR_RED)
    painter = QPainter(placeholder_pixmap_on_error)
    painter.setPen(QCOLOR_BLACK)
    painter.drawRect(placeholder_pixmap_on_error.rect().adjusted(0,0,-1,-1))
    painter.end()
    return [placeholder_pixmap_on_error]


# --- Player Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[QPixmap]]]:
    animations_dict: Dict[str, List[QPixmap]] = {}
    
    # Define mapping for player animations
    animation_filenames_map = {
        'attack': '__Attack.gif', 'attack2': '__Attack2.gif', 'attack_combo': '__AttackCombo2hit.gif',
        'attack_nm': '__AttackNoMovement.gif', 'attack2_nm': '__Attack2NoMovement.gif',
        'attack_combo_nm': '__AttackComboNoMovement.gif',
        'crouch': '__Crouch.gif', 'crouch_trans': '__CrouchTransition.gif',
        'crouch_walk': '__CrouchWalk.gif', 'crouch_attack': '__CrouchAttack.gif',
        'dash': '__Dash.gif',
        'death': '__Death.gif', 'death_nm': '__DeathNoMovement.gif',
        'fall': '__Fall.gif', 'hit': '__Hit.gif', 'idle': '__Idle.gif',
        'jump': '__Jump.gif', 'jump_fall_trans': '__JumpFallInbetween.gif',
        'roll': '__Roll.gif', 'run': '__Run.gif',
        'slide': '__SlideAll.gif', 'slide_trans_start': '__SlideTransitionStart.gif',
        'slide_trans_end': '__SlideTransitionEnd.gif',
        'turn': '__TurnAround.gif',
        'wall_climb': '__WallClimb.gif', 'wall_climb_nm': '__WallClimbNoMovement.gif',
        'wall_hang': '__WallHang.gif', 'wall_slide': '__WallSlide.gif',
        'frozen': '__Frozen.gif', 'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', 'burning': '__Burning.gif', # 'burning' can be same as 'aflame' if desired
        'aflame_crouch': '__Aflame_crouch.gif', 'burning_crouch': '__Burning_crouch.gif',
        'deflame': '__Deflame.gif', 'deflame_crouch': '__Deflame_crouch.gif',
        'zapped': '__Zapped.gif',
        # Petrified/Smashed are common and handled by PlayerBase/EnemyBase, not loaded per-character type here.
    }

    missing_files_log: List[Tuple[str, str, str]] = [] # (anim_name, relative_path, absolute_path_checked)
    try:
        base_path_for_log = sys._MEIPASS # type: ignore
    except AttributeError:
        base_path_for_log = get_project_root_dev_mode()

    for anim_state_name, gif_filename in animation_filenames_map.items():
         relative_path_to_gif_for_resource_path = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(relative_path_to_gif_for_resource_path)
         
         if not os.path.exists(absolute_gif_path):
             core_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit', 'zapped']
             if anim_state_name in core_animations:
                 missing_files_log.append((anim_state_name, relative_path_to_gif_for_resource_path, absolute_gif_path))
             animations_dict[anim_state_name] = [] # Mark as missing
             continue # Skip to next animation if file not found
         
         loaded_animation_frames = load_gif_frames(absolute_gif_path)
         animations_dict[anim_state_name] = loaded_animation_frames
         
         # Check if loaded frames are just the red placeholder (indicating load_gif_frames failed internally)
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].size() == QSize(30,40) and \
             animations_dict[anim_state_name][0].toImage().pixelColor(0,0) == QCOLOR_RED):
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}' for player folder '{relative_asset_folder}'. RED Placeholder used by load_gif_frames.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing CORE Animation Files Detected for Player Folder '{relative_asset_folder}' ---")
        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path_checked}' (NOT FOUND)")
        info(f"(Asset loading base path used for these assets: '{base_path_for_log}')")
        warning("-----------------------------------------------------------------\n")

    # Check for critical 'idle' animation
    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or # Empty list (means file not found)
        (len(animations_dict['idle']) == 1 and # Only one frame
         animations_dict['idle'][0].size() == QSize(30,40) and # Placeholder size
         animations_dict['idle'][0].toImage().pixelColor(0,0) == QCOLOR_RED) # Placeholder color
    )
    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path = os.path.join(relative_asset_folder, animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path)
        critical_msg_part = "not found or empty list" if ('idle' not in animations_dict or not animations_dict['idle']) else "failed to load correctly (is RED placeholder)"
        critical(f"CRITICAL Assets Error: 'idle' animation for PLAYER FOLDER '{relative_asset_folder}' {critical_msg_part} from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for PLAYER FOLDER '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None # Indicate critical failure

    # Provide blue placeholders for other missing non-critical animations
    for anim_name_check in animation_filenames_map:
        if anim_name_check == 'idle': continue # Already checked
        
        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or # Empty list
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].size() == QSize(30,40) and
             animations_dict[anim_name_check][0].toImage().pixelColor(0,0) == QCOLOR_RED)
        )

        if animation_is_missing_or_placeholder:
            warning_reason = "file likely missing or load_gif_frames failed"
            warning(f"Assets Warning (Player): Animation state '{anim_name_check}' ({warning_reason} for folder '{relative_asset_folder}'). Providing a BLUE placeholder.")
            blue_placeholder = QPixmap(30, 40)
            blue_placeholder.fill(QCOLOR_BLUE)
            painter = QPainter(blue_placeholder)
            painter.setPen(QCOLOR_RED) # Draw red X on blue placeholder
            painter.drawLine(0,0, 30,40); painter.drawLine(0,40, 30,0)
            painter.end()
            animations_dict[anim_name_check] = [blue_placeholder]
            
    return animations_dict


# --- Enemy Animation Loading Function ---
def load_enemy_animations(relative_asset_folder: str) -> Optional[Dict[str, List[QPixmap]]]:
    animations_dict: Dict[str, List[QPixmap]] = {}
    
    # Define mapping for standard enemy animations
    enemy_animation_filenames_map = {
        'idle': '__Idle.gif',
        'run': '__Run.gif',
        'attack': '__Attack.gif',
        'attack_nm': '__AttackNoMovement.gif', # Optional variant
        'hit': '__Hit.gif',
        'death': '__Death.gif',
        'death_nm': '__DeathNoMovement.gif', # Optional variant
        'frozen': '__Frozen.gif',
        'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', 
        'deflame': '__Deflame.gif',
        'zapped': '__Zapped.gif',
        # Petrified/Smashed are common and handled by EnemyBase.
    }

    missing_files_log: List[Tuple[str, str, str]] = []
    try: base_path_for_log = sys._MEIPASS # type: ignore
    except AttributeError: base_path_for_log = get_project_root_dev_mode()

    for anim_state_name, gif_filename in enemy_animation_filenames_map.items():
        relative_path_to_gif = os.path.join(relative_asset_folder, gif_filename)
        absolute_gif_path = resource_path(relative_path_to_gif)
        
        if not os.path.exists(absolute_gif_path):
            core_enemy_animations = ['idle', 'run', 'attack', 'death', 'hit', 'zapped'] # Core animations
            status_animations = ['frozen','defrost','aflame','deflame'] # Important status effect anims
            
            # Log missing non-optional files
            is_optional_variant = '_nm' in anim_state_name
            if not is_optional_variant:
                missing_files_log.append((anim_state_name, relative_path_to_gif, absolute_gif_path))
            
            animations_dict[anim_state_name] = [] # Mark as missing
            continue
        
        loaded_animation_frames = load_gif_frames(absolute_gif_path)
        animations_dict[anim_state_name] = loaded_animation_frames
        
        if not animations_dict[anim_state_name] or \
           (len(animations_dict[anim_state_name]) == 1 and
            animations_dict[anim_state_name][0].size() == QSize(30,40) and
            animations_dict[anim_state_name][0].toImage().pixelColor(0,0) == QCOLOR_RED):
            warning(f"Assets Warning (Enemy): Failed to load frames for state '{anim_state_name}' from '{absolute_gif_path}' for '{relative_asset_folder}'. RED Placeholder used by load_gif_frames.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing Animation Files Detected for ENEMY '{relative_asset_folder}' ---")
        for name, rel_path, res_path_checked in missing_files_log:
            is_core = name in ['idle', 'run', 'attack', 'death', 'hit', 'zapped'] or name in ['frozen','defrost','aflame','deflame']
            log_level_func = warning if is_core else debug # Use debug for less critical missing enemy anims
            log_level_func(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path_checked}' (NOT FOUND)")
        info(f"(Asset loading base path used for these assets: '{base_path_for_log}')")
        warning("-----------------------------------------------------------------\n")

    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or
        (len(animations_dict['idle']) == 1 and
         animations_dict['idle'][0].size() == QSize(30,40) and
         animations_dict['idle'][0].toImage().pixelColor(0,0) == QCOLOR_RED)
    )
    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path = os.path.join(relative_asset_folder, enemy_animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path)
        critical_msg_part = "not found or empty list" if ('idle' not in animations_dict or not animations_dict['idle']) else "failed to load correctly (is RED placeholder)"
        critical(f"CRITICAL Assets Error: 'idle' animation for ENEMY '{relative_asset_folder}' {critical_msg_part} from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for ENEMY '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None # Indicate critical failure

    for anim_name_check in enemy_animation_filenames_map:
        if anim_name_check == 'idle': continue
        
        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].size() == QSize(30,40) and
             animations_dict[anim_name_check][0].toImage().pixelColor(0,0) == QCOLOR_RED)
        )
        
        is_optional_variant = '_nm' in anim_name_check
        if animation_is_missing_or_placeholder and not is_optional_variant:
            warning_reason = "file likely missing or load_gif_frames failed"
            warning(f"Assets Warning (Enemy): Animation state '{anim_name_check}' ({warning_reason} for '{relative_asset_folder}'). Providing a BLUE placeholder.")
            blue_placeholder = QPixmap(30, 40); blue_placeholder.fill(QCOLOR_BLUE)
            painter = QPainter(blue_placeholder); painter.setPen(QCOLOR_RED); painter.drawLine(0,0, 30,40); painter.drawLine(0,40, 30,0); painter.end()
            animations_dict[anim_name_check] = [blue_placeholder]
        elif animation_is_missing_or_placeholder and is_optional_variant:
            # Optional variants like '_nm' might be legitimately missing, don't warn, just ensure key exists with empty list
            if anim_name_check not in animations_dict: animations_dict[anim_name_check] = []
            debug(f"Assets Info (Enemy): Optional animation '{anim_name_check}' not found or failed for '{relative_asset_folder}'. This is acceptable.")
            
    return animations_dict


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    app = QApplication.instance() 
    if app is None: app = QApplication(sys.argv) # Required for QPixmap/QImage
    info("Running assets.py directly for testing (PySide6 version)...")
    
    player1_asset_folder_relative = os.path.join('characters', 'player1')
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_p1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    if loaded_p1_animations:
        info(f"Assets Test (Player 1): Successfully loaded PLAYER animation data. Found states: {', '.join(k for k,v in loaded_p1_animations.items() if v)}")
        for anim_key in ['idle', 'run', 'jump', 'attack', 'death', 'aflame', 'frozen', 'zapped']: 
            if anim_key in loaded_p1_animations and loaded_p1_animations[anim_key]:
                first_frame = loaded_p1_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Player 1): Animation '{anim_key}' loaded with {len(loaded_p1_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                core_player_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit', 'zapped']
                if anim_key in core_player_animations:
                    warning(f"Assets Test (Player 1) WARNING: CORE Animation '{anim_key}' missing or empty after load.")
    else: error("\nAssets Test (Player 1): PLAYER Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    green_enemy_asset_folder_relative = os.path.join('characters', 'green')
    info(f"\n--- Testing load_enemy_animations for Green Enemy: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_enemy_animations = load_enemy_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    if loaded_green_enemy_animations:
        info(f"Assets Test (Green Enemy): Successfully loaded ENEMY animation data. Found states: {', '.join(k for k,v in loaded_green_enemy_animations.items() if v)}")
        for anim_key in ['idle', 'run', 'attack', 'death', 'aflame', 'zapped']: 
            if anim_key in loaded_green_enemy_animations and loaded_green_enemy_animations[anim_key]:
                first_frame = loaded_green_enemy_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Green Enemy): Animation '{anim_key}' loaded with {len(loaded_green_enemy_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                core_enemy_anims = ['idle', 'run', 'attack', 'death', 'hit', 'zapped']
                if anim_key in core_enemy_anims:
                    warning(f"Assets Test (Green Enemy) WARNING: CORE Animation '{anim_key}' missing or empty after load.")
    else: error("\nAssets Test (Green Enemy): ENEMY Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    # Test EnemyKnight animation loading
    knight_asset_folder_relative = os.path.join('characters', 'Knight_1')
    info(f"\n--- Testing load_enemy_animations for EnemyKnight (using generic enemy loader for now): '{knight_asset_folder_relative}' ---")
    # Note: EnemyKnight might use its own _load_knight_animations in its class.
    # This tests if the generic enemy loader can find a *subset* of animations if they match the generic keys.
    loaded_knight_as_generic_animations = load_enemy_animations(relative_asset_folder=knight_asset_folder_relative)
    if loaded_knight_as_generic_animations:
        info(f"Assets Test (Knight as Generic): Successfully loaded generic animation subset. Found states: {', '.join(k for k,v in loaded_knight_as_generic_animations.items() if v)}")
        # Check for 'idle' specifically
        if 'idle' in loaded_knight_as_generic_animations and loaded_knight_as_generic_animations['idle']:
            info("  'idle' animation for Knight (as generic) seems to be present.")
        else:
            error("  'idle' animation for Knight (as generic) is MISSING or FAILED to load.")
    else:
        error(f"\nAssets Test (Knight as Generic): Animation loading FAILED for '{knight_asset_folder_relative}'. This is expected if it doesn't have an '__Idle.gif' etc. or if 'idle' itself is missing.")

    info("Assets.py direct run test finished.")