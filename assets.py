#################### START OF FILE: assets.py ####################

# assets.py
# -*- coding: utf-8 -*-
## version 2.0.0 (PySide6 Refactor - QPixmap/QImage, removed pygame)
"""
Handles loading game assets, primarily animations from GIF files using Pillow and PySide6.
Includes a helper function `resource_path` to ensure correct asset pathing.
Maps are handled using C.MAPS_DIR from constants.py.
"""
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
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# --- Import Constants (specifically colors for placeholder images and C.MAPS_DIR for testing) ---
try:
    import constants as C
    # Define QColor versions of constants for direct use in PySide6
    QCOLOR_RED = QColor(*C.RED)
    QCOLOR_BLACK = QColor(*C.BLACK)
    QCOLOR_BLUE = QColor(*C.BLUE)
    QCOLOR_YELLOW = QColor(*C.YELLOW)
    MAPS_DIR_FOR_TESTING = C.MAPS_DIR
except ImportError:
    warning("Assets Warning: Failed to import 'constants' (using 'import constants as C'). Using fallback colors and MAPS_DIR_FOR_TESTING.")
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
    if 'C' in sys.modules:
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
    """
    Determines the project root when running in development mode.
    This function assumes that 'assets.py' is located directly within the project root directory.
    Example: ProjectRoot/assets.py
    """
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for development and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = get_project_root_dev_mode()
    return os.path.join(base_path, relative_path)
# ----------------------------------------------------


# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[QPixmap]:
    """
    Loads all frames from a GIF file using Pillow and converts them
    into a list of QPixmap objects. Handles transparency.
    """
    loaded_frames: List[QPixmap] = []
    try:
        pil_gif_image = Image.open(full_path_to_gif_file)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                # Ensure conversion to RGBA for consistent handling, especially for transparency
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                
                # Convert PIL Image to QImage
                # QImage constructor: data, width, height, bytesPerLine, format
                # Pillow's tobytes() gives a flat byte string.
                # QImage needs bytesPerLine which is width * number_of_channels.
                # For RGBA, this is width * 4.
                qimage_frame = QImage(rgba_pil_frame.tobytes(),
                                      rgba_pil_frame.width,
                                      rgba_pil_frame.height,
                                      rgba_pil_frame.width * 4, # bytesPerLine for RGBA
                                      QImage.Format.Format_RGBA8888) # Or Format_ARGB32_Premultiplied if issues
                
                if qimage_frame.isNull():
                    error(f"Assets Error: QImage conversion failed for frame {frame_index} in '{full_path_to_gif_file}'.")
                    # Optionally try another format or skip
                    frame_index += 1
                    continue

                qpixmap_frame = QPixmap.fromImage(qimage_frame)
                if qpixmap_frame.isNull():
                    error(f"Assets Error: QPixmap conversion failed for frame {frame_index} in '{full_path_to_gif_file}'.")
                    frame_index += 1
                    continue
                
                loaded_frames.append(qpixmap_frame)
                frame_index += 1
            except EOFError:
                break # End of frames
            except Exception as e_frame:
                error(f"Assets Error: Processing frame {frame_index} in '{full_path_to_gif_file}': {e_frame}")
                frame_index += 1

        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{full_path_to_gif_file}'. Creating a RED placeholder.")
             placeholder_pixmap = QPixmap(30, 40)
             placeholder_pixmap.fill(QCOLOR_RED)
             painter = QPainter(placeholder_pixmap)
             painter.setPen(QCOLOR_BLACK)
             painter.drawRect(placeholder_pixmap.rect().adjusted(0,0,-1,-1)) # Draw border inside
             painter.end()
             return [placeholder_pixmap]
        return loaded_frames
    except FileNotFoundError:
        error(f"Assets Error: GIF file not found at provided path: '{full_path_to_gif_file}'")
    except Exception as e_load:
        error(f"Assets Error: Loading GIF '{full_path_to_gif_file}' with Pillow/Qt: {e_load}")

    # Fallback placeholder if any error occurs during loading
    placeholder_pixmap_on_error = QPixmap(30, 40)
    placeholder_pixmap_on_error.fill(QCOLOR_RED)
    painter = QPainter(placeholder_pixmap_on_error)
    painter.setPen(QCOLOR_BLACK)
    painter.drawRect(placeholder_pixmap_on_error.rect().adjusted(0,0,-1,-1))
    painter.end()
    return [placeholder_pixmap_on_error]


# --- Player/Enemy Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[QPixmap]]]:
    animations_dict: Dict[str, List[QPixmap]] = {}
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
        'frozen': '__Frozen.gif',
        'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif',
        'burning': '__Burning.gif',
        'aflame_crouch': '__Aflame_crouch.gif',
        'burning_crouch': '__Burning_crouch.gif',
        'deflame': '__Deflame.gif',
        'deflame_crouch': '__Deflame_crouch.gif',
    }

    missing_files_log: List[tuple[str, str, str]] = []

    for anim_state_name, gif_filename in animation_filenames_map.items():
         relative_path_to_gif_for_resource_path = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(relative_path_to_gif_for_resource_path)

         if not os.path.exists(absolute_gif_path):
             missing_files_log.append(
                 (anim_state_name, relative_path_to_gif_for_resource_path, absolute_gif_path)
             )
             animations_dict[anim_state_name] = [] # Mark as missing
             continue

         loaded_animation_frames = load_gif_frames(absolute_gif_path)
         animations_dict[anim_state_name] = loaded_animation_frames

         # Check if loading resulted in the default RED placeholder
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].size() == QSize(30,40) and \
             animations_dict[anim_state_name][0].toImage().pixelColor(0,0) == QCOLOR_RED):
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}' for '{relative_asset_folder}'. RED Placeholder used.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing Animation Files Detected for '{relative_asset_folder}' ---")
        try: base_path_for_log = sys._MEIPASS
        except AttributeError: base_path_for_log = get_project_root_dev_mode()
        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path (for resource_path): '{rel_path}', Resolved path checked: '{res_path_checked}'")
        info(f"(Asset loading base path used by resource_path for these assets: '{base_path_for_log}')")
        warning("-----------------------------------------------------------------\n")

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
        critical(f"CRITICAL Assets Error: 'idle' animation for '{relative_asset_folder}' {critical_msg_part} from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None

    for anim_name_check in animation_filenames_map:
        if anim_name_check == 'idle': continue
        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].size() == QSize(30,40) and
             animations_dict[anim_name_check][0].toImage().pixelColor(0,0) == QCOLOR_RED)
        )
        if animation_is_missing_or_placeholder:
            warning_reason = "file likely missing" if (anim_name_check not in animations_dict or not animations_dict[anim_name_check]) else "load failed (is RED placeholder)"
            warning(f"Assets Warning: Animation state '{anim_name_check}' ({warning_reason} for '{relative_asset_folder}'). Providing a BLUE placeholder.")
            blue_placeholder = QPixmap(30, 40)
            blue_placeholder.fill(QCOLOR_BLUE)
            painter = QPainter(blue_placeholder)
            painter.setPen(QCOLOR_RED)
            painter.drawLine(0,0, 30,40); painter.drawLine(0,40, 30,0) # Diagonal cross
            painter.end()
            animations_dict[anim_name_check] = [blue_placeholder]
    return animations_dict
# ------------------------------------------


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    # PySide6 QApplication instance is needed for QPixmap/QImage operations
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    info("Running assets.py directly for testing (PySide6 version)...")

    info(f"\n--- Testing resource_path (from assets.py direct run) ---")
    info(f"Development Project Root (get_project_root_dev_mode()): {get_project_root_dev_mode()}")
    test_relative_asset_path = os.path.join('characters', 'player1', '__Idle.gif')
    resolved_test_asset_path = resource_path(test_relative_asset_path)
    info(f"Resolved path for asset '{test_relative_asset_path}': {resolved_test_asset_path}")
    info(f"Does asset exist at resolved path? {os.path.exists(resolved_test_asset_path)}")

    info(f"\n--- Testing map path resolution (using C.MAPS_DIR from constants) ---")
    test_map_filename = "test_map_for_assets_py.py"
    absolute_map_path_for_test = os.path.join(MAPS_DIR_FOR_TESTING, test_map_filename)
    info(f"Absolute path for map '{test_map_filename}' (using C.MAPS_DIR): {absolute_map_path_for_test}")
    try:
        if not os.path.exists(MAPS_DIR_FOR_TESTING):
            info(f"Attempting to create test maps directory: {MAPS_DIR_FOR_TESTING}")
            os.makedirs(MAPS_DIR_FOR_TESTING, exist_ok=True)
        with open(absolute_map_path_for_test, "w") as f:
            f.write("# Test map file created by assets.py test block")
        info(f"Does map file exist after creation at '{absolute_map_path_for_test}'? {os.path.exists(absolute_map_path_for_test)}")
    except Exception as e_test_map:
        error(f"Error creating test map file/dir: {e_test_map}")
        critical(f"Make sure the directory for MAPS_DIR_FOR_TESTING ('{MAPS_DIR_FOR_TESTING}') is writable or exists.")

    player1_asset_folder_relative = os.path.join('characters', 'player1')
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_player1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    if loaded_player1_animations:
        info(f"Assets Test (Player 1): Successfully loaded animation data. Found states: {', '.join(k for k,v in loaded_player1_animations.items() if v)}")
        for anim_key in ['idle', 'run', 'aflame', 'burning', 'frozen']:
            if anim_key in loaded_player1_animations and loaded_player1_animations[anim_key]:
                first_frame = loaded_player1_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Player 1): Animation '{anim_key}' loaded with {len(loaded_player1_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Player 1): Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    green_enemy_asset_folder_relative = os.path.join('characters', 'green')
    info(f"\n--- Testing load_all_player_animations for Green Enemy: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_animations = load_all_player_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    if loaded_green_animations:
        info(f"Assets Test (Green Enemy): Successfully loaded animation data. Found states: {', '.join(k for k,v in loaded_green_animations.items() if v)}")
        for anim_key in ['idle', 'run', 'attack', 'death', 'hit']:
            if anim_key in loaded_green_animations and loaded_green_animations[anim_key]:
                first_frame = loaded_green_animations[anim_key][0]
                if first_frame.size() == QSize(30,40) and \
                   (first_frame.toImage().pixelColor(0,0) == QCOLOR_RED or first_frame.toImage().pixelColor(0,0) == QCOLOR_BLUE):
                     warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Green Enemy): Animation '{anim_key}' loaded with {len(loaded_green_animations[anim_key])} frames. First frame size: {first_frame.size().width()}x{first_frame.size().height()}")
            else:
                warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Green Enemy): Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    info("Assets.py direct run test finished.")
    # QApplication instance will exit when the script finishes if it was created here.

#################### END OF FILE: assets.py ####################