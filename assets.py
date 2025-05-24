# assets.py
# -*- coding: utf-8 -*-
## version 2.0.3 (Corrected __main__ block, uses load_enemy_animations)
"""
Handles loading game assets, primarily animations from GIF files using Pillow and PySide6.
Includes a helper function `resource_path` to ensure correct asset pathing.
"""
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QProgressBar,
    QSizePolicy, QScrollArea
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
    def info(msg: str): print(f"INFO: {msg}")
    def debug(msg: str): print(f"DEBUG: {msg}")
    def warning(msg: str): print(f"WARNING: {msg}")
    def error(msg: str): print(f"ERROR: {msg}")
    def critical(msg: str): print(f"CRITICAL: {msg}")

# --- Import Constants ---
try:
    import constants as C
    QCOLOR_RED = QColor(*C.RED)
    QCOLOR_BLACK = QColor(*C.BLACK)
    QCOLOR_BLUE = QColor(*C.BLUE)
    QCOLOR_YELLOW = QColor(*C.YELLOW) # Assuming YELLOW is needed or was present
    MAPS_DIR_FOR_TESTING = C.MAPS_DIR # Used in __main__ if needed for other tests
except ImportError:
    warning("Assets Warning: Failed to import 'constants'. Using fallback colors and MAPS_DIR_FOR_TESTING.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)
    MAPS_DIR_FOR_TESTING = "maps"
except AttributeError as e_attr:
    warning(f"Assets Warning: Imported 'constants' but an attribute is missing: {e_attr}. Using fallback colors and MAPS_DIR_FOR_TESTING.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)
    if 'C' in sys.modules: # Check if C was partially imported
        MAPS_DIR_FOR_TESTING = getattr(C, "MAPS_DIR", "maps")
    else:
        MAPS_DIR_FOR_TESTING = "maps"
except Exception as e_general_import:
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using fallback colors and MAPS_DIR_FOR_TESTING.")
    QCOLOR_RED = QColor(255, 0, 0)
    QCOLOR_BLACK = QColor(0, 0, 0)
    QCOLOR_BLUE = QColor(0, 0, 255)
    QCOLOR_YELLOW = QColor(255, 255, 0)
    MAPS_DIR_FOR_TESTING = "maps"


# --- Helper Function for PyInstaller Compatibility ---
def get_project_root_dev_mode() -> str:
    """Determines the project root in development mode."""
    # Assuming assets.py is in the root directory of the project or alongside the main script
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS # type: ignore
    except AttributeError:
        # _MEIPASS attribute not found, so we are in development mode
        base_path = get_project_root_dev_mode()
        # If assets.py is in a subdirectory (e.g. 'utils'), adjust base_path accordingly:
        # base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    return os.path.join(base_path, relative_path)

# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[QPixmap]:
    """
    Loads all frames from a GIF file into a list of QPixmap objects.
    Handles potential errors and returns a placeholder if loading fails.
    """
    loaded_frames: List[QPixmap] = []
    try:
        pil_gif_image = Image.open(full_path_to_gif_file)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                # Create a copy of the frame to avoid issues with subsequent operations
                current_pil_frame = pil_gif_image.copy()
                # Ensure the frame is in RGBA format for QImage conversion
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                
                # Convert Pillow Image to QImage
                qimage_frame = QImage(rgba_pil_frame.tobytes(), rgba_pil_frame.width, rgba_pil_frame.height, 
                                      rgba_pil_frame.width * 4, # bytesPerLine
                                      QImage.Format.Format_RGBA8888)
                
                if qimage_frame.isNull():
                    error(f"Assets Error: QImage conversion failed for frame {frame_index} in '{full_path_to_gif_file}'.")
                    frame_index += 1
                    continue 
                
                # Convert QImage to QPixmap
                qpixmap_frame = QPixmap.fromImage(qimage_frame)
                if qpixmap_frame.isNull():
                    error(f"Assets Error: QPixmap conversion failed for frame {frame_index} in '{full_path_to_gif_file}'.")
                    frame_index += 1
                    continue

                loaded_frames.append(qpixmap_frame)
                frame_index += 1
            except EOFError:
                # End of GIF frames
                break
            except Exception as e_frame:
                error(f"Assets Error: Exception processing frame {frame_index} in '{full_path_to_gif_file}': {e_frame}")
                frame_index += 1 # Attempt to skip problematic frame
        
        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{full_path_to_gif_file}'. Creating a RED placeholder.")
             placeholder_pixmap = QPixmap(30, 40) # Arbitrary small size for placeholder
             placeholder_pixmap.fill(QCOLOR_RED)
             # Draw a border on the placeholder for visibility
             painter = QPainter(placeholder_pixmap)
             painter.setPen(QCOLOR_BLACK)
             painter.drawRect(placeholder_pixmap.rect().adjusted(0,0,-1,-1)) # adjusted to draw inside
             painter.end()
             return [placeholder_pixmap]
        
        return loaded_frames

    except FileNotFoundError:
        error(f"Assets Error: GIF file not found at provided path: '{full_path_to_gif_file}'")
    except Exception as e_load:
        error(f"Assets Error: General exception loading GIF '{full_path_to_gif_file}' with Pillow/Qt: {e_load}")

    # Fallback placeholder if any error occurs during loading
    placeholder_pixmap_on_error = QPixmap(30, 40)
    placeholder_pixmap_on_error.fill(QCOLOR_RED)
    painter = QPainter(placeholder_pixmap_on_error)
    painter.setPen(QCOLOR_BLACK)
    painter.drawRect(placeholder_pixmap_on_error.rect().adjusted(0,0,-1,-1))
    painter.end()
    return [placeholder_pixmap_on_error]


# --- Player Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[QPixmap]]]:
    """
    Loads all player animations from a specified subfolder within the 'characters' directory.
    The `relative_asset_folder` is relative to the `resource_path` base.
    Example: `load_all_player_animations('characters/player1')`
             `load_all_player_animations('characters/player_custom')`
    Returns a dictionary эмод animation_name -> list_of_QPixmaps, or None if critical animations fail.
    """
    animations_dict: Dict[str, List[QPixmap]] = {}
    
    # This map contains ALL potential player animations.
    # Individual player characters might not have all of them.
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
        'aflame': '__Aflame.gif', 'burning': '__Burning.gif',
        'aflame_crouch': '__Aflame_crouch.gif', 'burning_crouch': '__Burning_crouch.gif',
        'deflame': '__Deflame.gif', 'deflame_crouch': '__Deflame_crouch.gif',
        'petrified': '__Stone.png',  # Assuming a static PNG for petrified state
        'smashed': '__StoneSmashed.gif' # Assuming an animation for smashed state
    }

    missing_files_log: List[Tuple[str, str, str]] = []
    
    # Determine the base path once for logging if needed
    try: base_path_for_log = sys._MEIPASS # type: ignore
    except AttributeError: base_path_for_log = get_project_root_dev_mode()

    for anim_state_name, gif_filename in animation_filenames_map.items():
         # Construct path relative to where assets are located (e.g. project root/assets or MEIPASS/assets)
         # The `relative_asset_folder` is like 'characters/player1'
         relative_path_to_gif_for_resource_path = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(relative_path_to_gif_for_resource_path)

         if not os.path.exists(absolute_gif_path):
             # Only log as "missing" if it's a core animation. Some are optional variants.
             # Let's assume 'idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit' are core.
             core_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit']
             if anim_state_name in core_animations:
                 missing_files_log.append((anim_state_name, relative_path_to_gif_for_resource_path, absolute_gif_path))
             animations_dict[anim_state_name] = [] # Ensure key exists even if file is missing
             continue # Skip to next animation if file doesn't exist

         loaded_animation_frames = load_gif_frames(absolute_gif_path)
         animations_dict[anim_state_name] = loaded_animation_frames
         
         # Check if loading resulted in the default RED placeholder (meaning actual load failed)
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].size() == QSize(30,40) and \
             animations_dict[anim_state_name][0].toImage().pixelColor(0,0) == QCOLOR_RED):
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}' for player folder '{relative_asset_folder}'. RED Placeholder used.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing CORE Animation Files Detected for Player Folder '{relative_asset_folder}' ---")
        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path_checked}'")
        info(f"(Asset loading base path used for these assets: '{base_path_for_log}')")
        warning("-----------------------------------------------------------------\n")

    # Critical check: 'idle' animation MUST be present and valid.
    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or
        (len(animations_dict['idle']) == 1 and
         animations_dict['idle'][0].size() == QSize(30,40) and
         animations_dict['idle'][0].toImage().pixelColor(0,0) == QCOLOR_RED)
    )

    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path = os.path.join(relative_asset_folder, animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path)
        critical_msg_part = "not found or empty" if ('idle' not in animations_dict or not animations_dict['idle']) else "failed to load correctly (is RED placeholder)"
        critical(f"CRITICAL Assets Error: 'idle' animation for PLAYER FOLDER '{relative_asset_folder}' {critical_msg_part} from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for PLAYER FOLDER '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None

    # For other non-critical animations, provide a BLUE placeholder if missing or failed.
    for anim_name_check in animation_filenames_map:
        if anim_name_check == 'idle': continue # Already handled

        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].size() == QSize(30,40) and
             animations_dict[anim_name_check][0].toImage().pixelColor(0,0) == QCOLOR_RED)
        )
        
        if animation_is_missing_or_placeholder:
            warning_reason = "file likely missing" if (anim_name_check not in animations_dict or not animations_dict[anim_name_check]) else "load failed (is RED placeholder)"
            warning(f"Assets Warning (Player): Animation state '{anim_name_check}' ({warning_reason} for folder '{relative_asset_folder}'). Providing a BLUE placeholder.")
            
            blue_placeholder = QPixmap(30, 40) # Placeholder size
            blue_placeholder.fill(QCOLOR_BLUE)
            painter = QPainter(blue_placeholder)
            painter.setPen(QCOLOR_RED) # Draw a red X on it
            painter.drawLine(0,0, 30,40)
            painter.drawLine(0,40, 30,0)
            painter.end()
            animations_dict[anim_name_check] = [blue_placeholder]
            
    return animations_dict


# --- Enemy Animation Loading Function ---
def load_enemy_animations(relative_asset_folder: str) -> Optional[Dict[str, List[QPixmap]]]:
    """
    Loads all enemy animations from a specified subfolder.
    Similar to player animations but tailored for typical enemy states.
    """
    animations_dict: Dict[str, List[QPixmap]] = {}
    
    enemy_animation_filenames_map = {
        'idle': '__Idle.gif',
        'run': '__Run.gif',
        'attack': '__Attack.gif',
        'attack_nm': '__AttackNoMovement.gif', # Optional no-movement variant
        'hit': '__Hit.gif',
        'death': '__Death.gif',
        'death_nm': '__DeathNoMovement.gif', # Optional no-movement variant
        'frozen': '__Frozen.gif',
        'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', # Primary "on fire" animation for enemies
        'deflame': '__Deflame.gif',
        'petrified': '__Stone.png', # Assuming a static PNG for petrified state
        'smashed': '__StoneSmashed.gif' # Assuming an animation for smashed state
    }

    missing_files_log: List[Tuple[str, str, str]] = []
    try: base_path_for_log = sys._MEIPASS # type: ignore
    except AttributeError: base_path_for_log = get_project_root_dev_mode()

    for anim_state_name, gif_filename in enemy_animation_filenames_map.items():
        relative_path_to_gif = os.path.join(relative_asset_folder, gif_filename)
        absolute_gif_path = resource_path(relative_path_to_gif)

        if not os.path.exists(absolute_gif_path):
            # Core enemy animations that are critical
            core_enemy_animations = ['idle', 'run', 'attack', 'death', 'hit'] 
            if anim_state_name in core_enemy_animations or \
               anim_state_name in ['frozen','defrost','aflame','deflame','petrified','smashed']: # Also status effects
                missing_files_log.append((anim_state_name, relative_path_to_gif, absolute_gif_path))
            animations_dict[anim_state_name] = []
            continue

        loaded_animation_frames = load_gif_frames(absolute_gif_path)
        animations_dict[anim_state_name] = loaded_animation_frames

        if not animations_dict[anim_state_name] or \
           (len(animations_dict[anim_state_name]) == 1 and
            animations_dict[anim_state_name][0].size() == QSize(30,40) and
            animations_dict[anim_state_name][0].toImage().pixelColor(0,0) == QCOLOR_RED):
            warning(f"Assets Warning (Enemy): Failed to load frames for state '{anim_state_name}' from '{absolute_gif_path}' for '{relative_asset_folder}'. RED Placeholder used.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing CORE Animation Files Detected for ENEMY '{relative_asset_folder}' ---")
        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path_checked}'")
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
        critical_msg_part = "not found or empty" if ('idle' not in animations_dict or not animations_dict['idle']) else "failed to load correctly (is RED placeholder)"
        critical(f"CRITICAL Assets Error: 'idle' animation for ENEMY '{relative_asset_folder}' {critical_msg_part} from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for ENEMY '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None

    for anim_name_check in enemy_animation_filenames_map:
        if anim_name_check == 'idle': continue # Already handled

        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].size() == QSize(30,40) and
             animations_dict[anim_name_check][0].toImage().pixelColor(0,0) == QCOLOR_RED)
        )
        
        is_optional_variant = '_nm' in anim_name_check # e.g. attack_nm, death_nm
        
        if animation_is_missing_or_placeholder and not is_optional_variant:
            # This is a core animation (or status effect) that's missing or failed
            warning_reason = "file likely missing" if (anim_name_check not in animations_dict or not animations_dict[anim_name_check]) else "load failed (is RED placeholder)"
            warning(f"Assets Warning (Enemy): Animation state '{anim_name_check}' ({warning_reason} for '{relative_asset_folder}'). Providing a BLUE placeholder.")
            blue_placeholder = QPixmap(30, 40)
            blue_placeholder.fill(QCOLOR_BLUE)
            painter = QPainter(blue_placeholder)
            painter.setPen(QCOLOR_RED) # Red X on blue
            painter.drawLine(0,0, 30,40); painter.drawLine(0,40, 30,0)
            painter.end()
            animations_dict[anim_name_check] = [blue_placeholder]
        elif animation_is_missing_or_placeholder and is_optional_variant:
            # Optional variant missing is acceptable, ensure key exists with empty list
            if anim_name_check not in animations_dict: # Should have been set if file not found path was taken
                 animations_dict[anim_name_check] = []
            debug(f"Assets Info (Enemy): Optional animation '{anim_name_check}' not found or failed for '{relative_asset_folder}'. This is acceptable.")

    return animations_dict


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    # Ensure a QApplication instance exists for QPixmap/QImage operations
    app = QApplication.instance() 
    if app is None:
        app = QApplication(sys.argv)
    
    info("Running assets.py directly for testing (PySide6 version)...")
    
    # --- Test Player Animation Loading ---
    player1_asset_folder_relative = os.path.join('characters', 'player1')
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_p1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    
    if loaded_p1_animations:
        info(f"Assets Test (Player 1): Successfully loaded PLAYER animation data. Found states: {', '.join(k for k,v in loaded_p1_animations.items() if v)}")
        # Check a few key animations for Player 1
        for anim_key in ['idle', 'run', 'jump', 'attack', 'death', 'aflame', 'frozen']: 
            if anim_key in loaded_p1_animations and loaded_p1_animations[anim_key]:
                first_frame = loaded_p1_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Player 1): Animation '{anim_key}' loaded with {len(loaded_p1_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                # If it's a core animation, it should have at least a placeholder
                core_player_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit']
                if anim_key in core_player_animations:
                    warning(f"Assets Test (Player 1) WARNING: CORE Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Player 1): PLAYER Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    # --- Test Enemy Animation Loading ---
    green_enemy_asset_folder_relative = os.path.join('characters', 'green')
    info(f"\n--- Testing load_enemy_animations for Green Enemy: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_enemy_animations = load_enemy_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    
    if loaded_green_enemy_animations:
        info(f"Assets Test (Green Enemy): Successfully loaded ENEMY animation data. Found states: {', '.join(k for k,v in loaded_green_enemy_animations.items() if v)}")
        # Check a few key animations for Green Enemy
        for anim_key in ['idle', 'run', 'attack', 'death', 'aflame']: 
            if anim_key in loaded_green_enemy_animations and loaded_green_enemy_animations[anim_key]:
                first_frame = loaded_green_enemy_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Green Enemy): Animation '{anim_key}' loaded with {len(loaded_green_enemy_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                # If it's a core enemy animation, it should have at least a placeholder
                core_enemy_anims = ['idle', 'run', 'attack', 'death', 'hit']
                if anim_key in core_enemy_anims:
                    warning(f"Assets Test (Green Enemy) WARNING: CORE Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Green Enemy): ENEMY Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    gray_enemy_asset_folder_relative = os.path.join('characters', 'gray')
    info(f"\n--- Testing load_enemy_animations for Gray Enemy: '{gray_enemy_asset_folder_relative}' ---")
    loaded_gray_enemy_animations = load_enemy_animations(relative_asset_folder=gray_enemy_asset_folder_relative)
    if loaded_gray_enemy_animations:
        info(f"Assets Test (Gray Enemy): Successfully loaded ENEMY animation data. Found states: {', '.join(k for k,v in loaded_gray_enemy_animations.items() if v)}")
    else:
        error("\nAssets Test (Gray Enemy): ENEMY Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    info("Assets.py direct run test finished.")
    # If app was created for this test, it's good practice to let it process events and exit if desired.
    # sys.exit(app.exec()) # Or just let it fall through if run as a script