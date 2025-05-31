# assets.py
# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations from GIF files using Pillow and PySide6.
Includes a helper function `resource_path` to ensure correct asset pathing.
Stone/Smashed animations are common and loaded by character base classes.
MODIFIED: Log level for missing non-core animations changed to DEBUG for EnemyKnight.
MODIFIED: Ensured QApplication is initialized for __main__ test block.
"""
# version 2.0.7 (Refined __main__ test block, consistent placeholders)

from PySide6.QtWidgets import (
    QApplication # Only needed if running this file directly for testing
)
import os
import sys
from PIL import Image # Pillow library for GIF processing
from typing import Dict, List, Optional, Tuple # For type hinting

from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont # PySide6 image/drawing tools
from PySide6.QtCore import QSize, Qt # For QSize and Qt enums

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ASSETS: logger.py not found. Falling back to print statements for logging.")
    def info(msg: str, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg: str, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg: str, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg: str, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg: str, *args, **kwargs): print(f"CRITICAL: {msg}")

# --- Import Constants ---
try:
    import constants as C
    QCOLOR_RED_FALLBACK = QColor(*C.RED)
    QCOLOR_BLACK_FALLBACK = QColor(*C.BLACK)
    QCOLOR_BLUE_FALLBACK = QColor(*C.BLUE)
    QCOLOR_YELLOW_FALLBACK = QColor(*C.YELLOW)
    QCOLOR_MAGENTA_FALLBACK = QColor(*C.MAGENTA)
except ImportError:
    warning("Assets Warning: Failed to import 'constants'. Using hardcoded fallback colors.")
    QCOLOR_RED_FALLBACK = QColor(255, 0, 0)
    QCOLOR_BLACK_FALLBACK = QColor(0, 0, 0)
    QCOLOR_BLUE_FALLBACK = QColor(0, 0, 255)
    QCOLOR_YELLOW_FALLBACK = QColor(255, 255, 0)
    QCOLOR_MAGENTA_FALLBACK = QColor(255,0,255)
except AttributeError as e_attr:
    warning(f"Assets Warning: Imported 'constants' but an attribute is missing: {e_attr}. Using hardcoded fallback colors.")
    QCOLOR_RED_FALLBACK = QColor(255, 0, 0)
    QCOLOR_BLACK_FALLBACK = QColor(0, 0, 0)
    QCOLOR_BLUE_FALLBACK = QColor(0, 0, 255)
    QCOLOR_YELLOW_FALLBACK = QColor(255, 255, 0)
    QCOLOR_MAGENTA_FALLBACK = QColor(255,0,255)
except Exception as e_general_import:
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using hardcoded fallback colors.")
    QCOLOR_RED_FALLBACK = QColor(255, 0, 0)
    QCOLOR_BLACK_FALLBACK = QColor(0, 0, 0)
    QCOLOR_BLUE_FALLBACK = QColor(0, 0, 255)
    QCOLOR_YELLOW_FALLBACK = QColor(255, 255, 0)
    QCOLOR_MAGENTA_FALLBACK = QColor(255,0,255)


# --- Helper Function for PyInstaller Compatibility ---
def get_project_root_dev_mode() -> str:
    # Assumes assets.py is in the project root directory.
    # If it's in a subfolder (e.g., 'utils/'), change to:
    # os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if '__file__' in globals():
        return os.path.dirname(os.path.abspath(__file__))
    return os.getcwd() # Fallback if __file__ is not defined

def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS # type: ignore PyInstaller creates a temp folder
    except AttributeError:
        base_path = get_project_root_dev_mode()
    return os.path.join(base_path, relative_path)

# --- Placeholder Creation Helper ---
def _create_error_placeholder(color: QColor, text: str = "ERR", size: QSize = QSize(30,40)) -> QPixmap:
    pixmap = QPixmap(size)
    if pixmap.isNull():
        error(f"Assets Error: Failed to create placeholder QPixmap of size {size.width()}x{size.height()} for text '{text}'.")
        # Return an even more basic, tiny magenta pixmap if the requested size fails
        tiny_fallback = QPixmap(1,1); tiny_fallback.fill(QCOLOR_MAGENTA_FALLBACK); return tiny_fallback
    
    pixmap.fill(color)
    painter = QPainter(pixmap)
    painter.setPen(QCOLOR_BLACK_FALLBACK)
    painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1)) # Border
    try:
        font = QFont(); font.setPointSize(max(6, int(size.height() / 4))); painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text[:3].upper()) # Max 3 chars
    except Exception as e_font: error(f"Assets PlaceholderFontError: {e_font}")
    painter.end()
    return pixmap

# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[QPixmap]:
    loaded_frames: List[QPixmap] = []
    normalized_path = os.path.normpath(full_path_to_gif_file)
    
    if not os.path.exists(normalized_path):
        # FileNotFoundError is now handled by the calling function for better context.
        # error(f"Assets Error: GIF file not found at: '{normalized_path}'") # Redundant log
        return [_create_error_placeholder(QCOLOR_RED_FALLBACK, "FNF")] # Return placeholder for file not found

    try:
        pil_gif_image = Image.open(normalized_path)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                qimage_frame = QImage(rgba_pil_frame.tobytes(), rgba_pil_frame.width, rgba_pil_frame.height,
                                      rgba_pil_frame.width * 4, QImage.Format.Format_RGBA8888)
                if qimage_frame.isNull():
                    error(f"Assets Error: QImage conversion failed for frame {frame_index} in '{normalized_path}'."); frame_index += 1; continue
                qpixmap_frame = QPixmap.fromImage(qimage_frame)
                if qpixmap_frame.isNull():
                    error(f"Assets Error: QPixmap conversion failed for frame {frame_index} in '{normalized_path}'."); frame_index += 1; continue
                loaded_frames.append(qpixmap_frame); frame_index += 1
            except EOFError: break # End of frames
            except Exception as e_frame: error(f"Assets Error: Exception processing frame {frame_index} in '{normalized_path}': {e_frame}"); frame_index += 1
        
        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{normalized_path}' (possibly empty or corrupt GIF).")
             return [_create_error_placeholder(QCOLOR_RED_FALLBACK, "GIF0")]
        return loaded_frames
    except Exception as e_load: # Catch other Pillow/Qt errors during open or initial processing
        error(f"Assets Error: General exception loading GIF '{normalized_path}': {e_load}")
        return [_create_error_placeholder(QCOLOR_RED_FALLBACK, "LDE")]


# --- Player Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[QPixmap]]]:
    animations_dict: Dict[str, List[QPixmap]] = {}
    animation_filenames_map = { # Player-specific animation file names
        'idle': '__Idle.gif', 'run': '__Run.gif', 'jump': '__Jump.gif', 'fall': '__Fall.gif',
        'attack': '__Attack.gif', 'attack2': '__Attack2.gif', 'attack_combo': '__AttackCombo2hit.gif',
        'attack_nm': '__AttackNoMovement.gif', 'attack2_nm': '__Attack2NoMovement.gif',
        'attack_combo_nm': '__AttackComboNoMovement.gif',
        'crouch': '__Crouch.gif', 'crouch_trans': '__CrouchTransition.gif',
        'crouch_walk': '__CrouchWalk.gif', 'crouch_attack': '__CrouchAttack.gif',
        'dash': '__Dash.gif', 'death': '__Death.gif', 'death_nm': '__DeathNoMovement.gif',
        'hit': '__Hit.gif', 'jump_fall_trans': '__JumpFallInbetween.gif',
        'roll': '__Roll.gif', 'slide': '__SlideAll.gif',
        'slide_trans_start': '__SlideTransitionStart.gif', 'slide_trans_end': '__SlideTransitionEnd.gif',
        'turn': '__TurnAround.gif', 'wall_climb': '__WallClimb.gif',
        'wall_climb_nm': '__WallClimbNoMovement.gif', 'wall_hang': '__WallHang.gif',
        'wall_slide': '__WallSlide.gif', 'frozen': '__Frozen.gif', 'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', 'burning': '__Burning.gif',
        'aflame_crouch': '__Aflame_crouch.gif', 'burning_crouch': '__Burning_crouch.gif',
        'deflame': '__Deflame.gif', 'deflame_crouch': '__Deflame_crouch.gif',
        'zapped': '__Zapped.gif',
    }
    core_player_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit', 'zapped']
    missing_files_report: List[str] = []

    for anim_state_name, gif_filename in animation_filenames_map.items():
         absolute_gif_path = resource_path(os.path.join(relative_asset_folder, gif_filename))
         if not os.path.exists(absolute_gif_path):
             if anim_state_name in core_player_animations:
                 missing_files_report.append(f"CORE '{anim_state_name}' ({gif_filename})")
             animations_dict[anim_state_name] = [_create_error_placeholder(QCOLOR_RED_FALLBACK if anim_state_name in core_player_animations else QCOLOR_BLUE_FALLBACK, anim_state_name[:3])]
             continue
         animations_dict[anim_state_name] = load_gif_frames(absolute_gif_path)

    if missing_files_report:
        warning(f"Assets (Player '{relative_asset_folder}'): Missing CORE animation files: {', '.join(missing_files_report)}")

    if not animations_dict.get('idle') or _is_placeholder_qpixmap_check(animations_dict['idle'][0]):
        critical(f"CRITICAL Assets Error: 'idle' animation for PLAYER FOLDER '{relative_asset_folder}' missing or placeholder. Load failed.")
        return None
    
    for anim_name, frames in animations_dict.items():
        if not frames or _is_placeholder_qpixmap_check(frames[0]):
             if anim_name not in core_player_animations and anim_name not in missing_files_report: # Avoid double logging for core
                debug(f"Assets Debug (Player '{relative_asset_folder}'): Non-core animation '{anim_name}' is placeholder or missing.")
    return animations_dict

# --- Enemy Animation Loading Function ---
def load_enemy_animations(relative_asset_folder: str) -> Optional[Dict[str, List[QPixmap]]]:
    animations_dict: Dict[str, List[QPixmap]] = {}
    enemy_animation_filenames_map = { # Generic enemy animation file names
        'idle': '__Idle.gif', 'run': '__Run.gif', 'attack': '__Attack.gif',
        'attack_nm': '__AttackNoMovement.gif', 'hit': '__Hit.gif',
        'death': '__Death.gif', 'death_nm': '__DeathNoMovement.gif',
        'frozen': '__Frozen.gif', 'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', 'deflame': '__Deflame.gif',
        'zapped': '__Zapped.gif',
    }
    core_enemy_animations = ['idle', 'run', 'attack', 'death', 'hit', 'zapped']
    important_status_anims = ['frozen','defrost','aflame','deflame']
    missing_files_report: List[str] = []

    for anim_state_name, gif_filename in enemy_animation_filenames_map.items():
        absolute_gif_path = resource_path(os.path.join(relative_asset_folder, gif_filename))
        if not os.path.exists(absolute_gif_path):
            is_optional = '_nm' in anim_state_name
            if not is_optional:
                missing_files_report.append(f"'{anim_state_name}' ({gif_filename})")
            # Always provide a placeholder if file is missing
            placeholder_color = QCOLOR_BLUE_FALLBACK
            if anim_state_name in core_enemy_animations: placeholder_color = QCOLOR_RED_FALLBACK
            elif anim_state_name in important_status_anims: placeholder_color = QCOLOR_YELLOW_FALLBACK
            animations_dict[anim_state_name] = [_create_error_placeholder(placeholder_color, anim_state_name[:3])]
            continue
        animations_dict[anim_state_name] = load_gif_frames(absolute_gif_path)

    if missing_files_report:
        warning(f"Assets (Enemy '{relative_asset_folder}'): Missing animation files: {', '.join(missing_files_report)}")

    if not animations_dict.get('idle') or _is_placeholder_qpixmap_check(animations_dict['idle'][0]):
        critical(f"CRITICAL Assets Error: 'idle' animation for ENEMY FOLDER '{relative_asset_folder}' missing or placeholder. Load failed.")
        return None
        
    for anim_name, frames in animations_dict.items():
        if not frames or _is_placeholder_qpixmap_check(frames[0]):
             is_optional = '_nm' in anim_name
             if not is_optional and anim_name not in core_enemy_animations and anim_name not in important_status_anims:
                 debug(f"Assets Debug (Enemy '{relative_asset_folder}'): Non-core/status animation '{anim_name}' is placeholder or missing.")
    return animations_dict

def _is_placeholder_qpixmap_check(pixmap: QPixmap, size: QSize = QSize(30,40)) -> bool:
    """Checks if a given pixmap is likely one of the error placeholders."""
    if pixmap.isNull(): return True
    if pixmap.size() == size: # Check against common placeholder size
        qimage = pixmap.toImage()
        if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
            color_at_origin = qimage.pixelColor(0,0)
            if color_at_origin in [QCOLOR_RED_FALLBACK, QCOLOR_BLUE_FALLBACK, QCOLOR_YELLOW_FALLBACK, QCOLOR_MAGENTA_FALLBACK]:
                return True
    return False


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    # QApplication instance is required for QPixmap operations
    app = QApplication.instance() 
    if app is None: app = QApplication(sys.argv)
    
    info("Running assets.py directly for testing (PySide6 version)...")
    # ... (rest of the __main__ test block from previous version, it should work fine) ...
    player1_asset_folder_relative = os.path.join('characters', 'player1')
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_p1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    if loaded_p1_animations:
        info(f"Assets Test (Player 1): Successfully loaded PLAYER animation data. Found states: {', '.join(k for k,v in loaded_p1_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
    else: error("\nAssets Test (Player 1): PLAYER Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    green_enemy_asset_folder_relative = os.path.join('characters', 'green')
    info(f"\n--- Testing load_enemy_animations for Green Enemy: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_enemy_animations = load_enemy_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    if loaded_green_enemy_animations:
        info(f"Assets Test (Green Enemy): Successfully loaded ENEMY animation data. Found states: {', '.join(k for k,v in loaded_green_enemy_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
    else: error("\nAssets Test (Green Enemy): ENEMY Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    knight_asset_folder_relative = os.path.join('characters', 'Knight_1')
    info(f"\n--- Testing generic load_enemy_animations for Knight_1 (EXPECTS __Idle.gif etc.): '{knight_asset_folder_relative}' ---")
    # This tests if Knight_1 folder *happens* to have generic __Idle.gif etc.
    # EnemyKnight class itself uses KNIGHT_ANIM_PATHS and its own _load_knight_animations.
    loaded_knight_as_generic_animations = load_enemy_animations(relative_asset_folder=knight_asset_folder_relative)
    if loaded_knight_as_generic_animations:
        info(f"Assets Test (Knight as Generic): Found generic keys: {', '.join(k for k,v in loaded_knight_as_generic_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
        if 'idle' in loaded_knight_as_generic_animations and loaded_knight_as_generic_animations['idle'] and not _is_placeholder_qpixmap_check(loaded_knight_as_generic_animations['idle'][0]):
            info("  '__Idle.gif' for Knight (as generic) seems to be present and loaded.")
        else:
            error("  '__Idle.gif' for Knight (as generic) is MISSING or FAILED to load.")
    else:
        error(f"\nAssets Test (Knight as Generic): Animation loading FAILED for '{knight_asset_folder_relative}' using generic enemy loader.")

    info("Assets.py direct run test finished.")
    # No app.exec() here, just testing loading.