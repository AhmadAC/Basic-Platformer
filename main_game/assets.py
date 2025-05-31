# main_game/assets.py
# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations from GIF files using Pillow and PySide6.
Includes a helper function `resource_path` to ensure correct asset pathing.
Stone/Smashed animations are common and loaded by character base classes.
MODIFIED: Log level for missing non-core animations changed to DEBUG for EnemyKnight.
MODIFIED: Ensured QApplication is initialized for __main__ test block.
MODIFIED: All internal path constructions within loading functions now assume
          `relative_asset_folder` is a path *relative to the project root*
          (e.g., "assets/category/subcategory") and `resource_path` is applied
          to the full combined path including the GIF filename.
"""
# version 2.0.8 (Refined internal path construction for resource_path)

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
    import main_game.constants as C # This now has the updated PROJECT_ROOT
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
    QCOLOR_RED_FALLBACK = QColor(255, 0, 0); QCOLOR_BLACK_FALLBACK = QColor(0, 0, 0); QCOLOR_BLUE_FALLBACK = QColor(0, 0, 255); QCOLOR_YELLOW_FALLBACK = QColor(255, 255, 0); QCOLOR_MAGENTA_FALLBACK = QColor(255,0,255)
except Exception as e_general_import:
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using hardcoded fallback colors.")
    QCOLOR_RED_FALLBACK = QColor(255, 0, 0); QCOLOR_BLACK_FALLBACK = QColor(0, 0, 0); QCOLOR_BLUE_FALLBACK = QColor(0, 0, 255); QCOLOR_YELLOW_FALLBACK = QColor(255, 255, 0); QCOLOR_MAGENTA_FALLBACK = QColor(255,0,255)


# --- Helper Function for PyInstaller Compatibility ---
def resource_path(relative_path_from_project_root: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller.
        `relative_path_from_project_root` should be like "assets/category/file.ext".
    """
    try:
        # PyInstaller creates a temp folder and stores assets in `_MEIPASS`.
        # This path is already absolute.
        base_path = sys._MEIPASS # type: ignore
    except AttributeError:
        # Not bundled, use the PROJECT_ROOT from constants.py
        base_path = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isabs(base_path): # Ensure base_path is absolute
            base_path = os.path.abspath(base_path)

    final_path = os.path.join(base_path, relative_path_from_project_root)
    return os.path.normpath(final_path)

# --- Placeholder Creation Helper ---
def _create_error_placeholder(color: QColor, text: str = "ERR", size: QSize = QSize(30,40)) -> QPixmap:
    pixmap = QPixmap(size)
    if pixmap.isNull():
        error(f"Assets Error: Failed to create placeholder QPixmap of size {size.width()}x{size.height()} for text '{text}'.")
        tiny_fallback = QPixmap(1,1); tiny_fallback.fill(QCOLOR_MAGENTA_FALLBACK); return tiny_fallback
    
    pixmap.fill(color)
    painter = QPainter(pixmap)
    painter.setPen(QCOLOR_BLACK_FALLBACK)
    painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
    try:
        font = QFont(); font.setPointSize(max(6, int(size.height() / 4))); painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text[:3].upper())
    except Exception as e_font: error(f"Assets PlaceholderFontError: {e_font}")
    painter.end()
    return pixmap

# --- GIF Loading Function ---
def load_gif_frames(full_absolute_path_to_gif_file: str) -> List[QPixmap]:
    """Loads all frames from a GIF file into a list of QPixmaps."""
    loaded_frames: List[QPixmap] = []
    normalized_path = os.path.normpath(full_absolute_path_to_gif_file)
    
    if not os.path.exists(normalized_path):
        # FileNotFoundError handled by calling functions, but log here too for asset-specific trace
        error(f"Assets Error (load_gif_frames): GIF file not found at: '{normalized_path}'")
        return [_create_error_placeholder(QCOLOR_RED_FALLBACK, "FNF")]

    try:
        pil_gif_image = Image.open(normalized_path)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                # Convert to RGBA to handle various GIF palette modes consistently
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                # Create QImage from Pillow frame data
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
    except Exception as e_load:
        error(f"Assets Error: General exception loading GIF '{normalized_path}': {e_load}")
        return [_create_error_placeholder(QCOLOR_RED_FALLBACK, "LDE")]


# --- Player Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str) -> Optional[Dict[str, List[QPixmap]]]:
    """
    Loads all player animations from a specified folder.
    `relative_asset_folder` should be the path from the project root,
    e.g., "assets/playable_characters/player1".
    """
    animations_dict: Dict[str, List[QPixmap]] = {}
    animation_filenames_map = {
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
        'zapped': '__Zapped.gif', # Added Zapped
    }
    core_player_animations = ['idle', 'run', 'jump', 'fall', 'attack', 'death', 'hit', 'zapped']
    missing_files_report: List[str] = []

    for anim_state_name, gif_filename in animation_filenames_map.items():
         # Construct path relative to project root, then pass to resource_path
         path_relative_to_project_root = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(path_relative_to_project_root)

         if not os.path.exists(absolute_gif_path):
             if anim_state_name in core_player_animations:
                 missing_files_report.append(f"CORE '{anim_state_name}' ({gif_filename} at '{absolute_gif_path}')")
             # Use a specific placeholder color based on importance
             placeholder_color = QCOLOR_RED_FALLBACK if anim_state_name in core_player_animations else QCOLOR_BLUE_FALLBACK
             animations_dict[anim_state_name] = [_create_error_placeholder(placeholder_color, anim_state_name[:3])]
             continue
         animations_dict[anim_state_name] = load_gif_frames(absolute_gif_path)

    if missing_files_report:
        warning(f"Assets (Player Folder: '{relative_asset_folder}'): Missing CORE animation files: {', '.join(missing_files_report)}")

    # Critical check for 'idle' animation
    if not animations_dict.get('idle') or _is_placeholder_qpixmap_check(animations_dict['idle'][0]):
        critical(f"CRITICAL Assets Error: 'idle' animation for PLAYER FOLDER '{relative_asset_folder}' missing or placeholder. Load failed.")
        return None # Fail entirely if idle is missing
    
    # Log placeholders for non-core animations at DEBUG level
    for anim_name, frames in animations_dict.items():
        if not frames or _is_placeholder_qpixmap_check(frames[0]):
             # Avoid double logging for core animations already reported as missing
             if anim_name not in core_player_animations and anim_name not in missing_files_report:
                debug(f"Assets Debug (Player Folder: '{relative_asset_folder}'): Non-core animation '{anim_name}' is placeholder or missing.")
    return animations_dict

# --- Enemy Animation Loading Function ---
def load_enemy_animations(relative_asset_folder: str) -> Optional[Dict[str, List[QPixmap]]]:
    """
    Loads generic enemy animations from a specified folder.
    `relative_asset_folder` should be the path from the project root,
    e.g., "assets/enemy_characters/soldier/green".
    """
    animations_dict: Dict[str, List[QPixmap]] = {}
    enemy_animation_filenames_map = {
        'idle': '__Idle.gif', 'run': '__Run.gif', 'attack': '__Attack.gif',
        'attack_nm': '__AttackNoMovement.gif', 'hit': '__Hit.gif',
        'death': '__Death.gif', 'death_nm': '__DeathNoMovement.gif',
        'frozen': '__Frozen.gif', 'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif', 'deflame': '__Deflame.gif',
        'zapped': '__Zapped.gif', # Added Zapped
    }
    core_enemy_animations = ['idle', 'run', 'attack', 'death', 'hit', 'zapped']
    important_status_anims = ['frozen','defrost','aflame','deflame']
    missing_files_report: List[str] = []

    for anim_state_name, gif_filename in enemy_animation_filenames_map.items():
        path_relative_to_project_root = os.path.join(relative_asset_folder, gif_filename)
        absolute_gif_path = resource_path(path_relative_to_project_root)

        if not os.path.exists(absolute_gif_path):
            is_optional = '_nm' in anim_state_name # Consider no-movement variants optional
            if not is_optional:
                missing_files_report.append(f"'{anim_state_name}' ({gif_filename} at '{absolute_gif_path}')")
            
            placeholder_color = QCOLOR_BLUE_FALLBACK
            if anim_state_name in core_enemy_animations: placeholder_color = QCOLOR_RED_FALLBACK
            elif anim_state_name in important_status_anims: placeholder_color = QCOLOR_YELLOW_FALLBACK
            animations_dict[anim_state_name] = [_create_error_placeholder(placeholder_color, anim_state_name[:3])]
            continue
        animations_dict[anim_state_name] = load_gif_frames(absolute_gif_path)

    if missing_files_report:
        warning(f"Assets (Enemy Folder: '{relative_asset_folder}'): Missing animation files: {', '.join(missing_files_report)}")

    if not animations_dict.get('idle') or _is_placeholder_qpixmap_check(animations_dict['idle'][0]):
        critical(f"CRITICAL Assets Error: 'idle' animation for ENEMY FOLDER '{relative_asset_folder}' missing or placeholder. Load failed.")
        return None # Fail if idle is missing
        
    for anim_name, frames in animations_dict.items():
        if not frames or _is_placeholder_qpixmap_check(frames[0]):
             is_optional = '_nm' in anim_name
             if not is_optional and anim_name not in core_enemy_animations and anim_name not in important_status_anims:
                 debug(f"Assets Debug (Enemy Folder: '{relative_asset_folder}'): Non-core/status animation '{anim_name}' is placeholder or missing.")
    return animations_dict

def _is_placeholder_qpixmap_check(pixmap: QPixmap, size: QSize = QSize(30,40)) -> bool:
    """Checks if a given pixmap is likely one of the error placeholders."""
    if pixmap.isNull(): return True
    # Check common placeholder size (30x40) and also a generic small size (1x1 magenta)
    if pixmap.size() == size or (pixmap.width()==1 and pixmap.height()==1):
        qimage = pixmap.toImage()
        if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
            color_at_origin = qimage.pixelColor(0,0)
            if color_at_origin in [QCOLOR_RED_FALLBACK, QCOLOR_BLUE_FALLBACK, QCOLOR_YELLOW_FALLBACK, QCOLOR_MAGENTA_FALLBACK]:
                return True
    return False


if __name__ == "__main__":
    app = QApplication.instance() 
    if app is None: app = QApplication(sys.argv)
    
    info("Running assets.py directly for testing (PySide6 version)...")
    
    project_root_test_assets = getattr(C, 'PROJECT_ROOT', os.path.dirname(os.path.abspath(__file__)))
    info(f"Assets Test: Using PROJECT_ROOT: {project_root_test_assets}")

    player1_asset_folder_relative = os.path.join('assets', 'playable_characters', 'player1') # Corrected for new structure
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_p1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    if loaded_p1_animations:
        info(f"Assets Test (Player 1): Successfully loaded PLAYER animation data. Found states: {', '.join(k for k,v in loaded_p1_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
    else: error("\nAssets Test (Player 1): PLAYER Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    green_enemy_asset_folder_relative = os.path.join('assets', 'enemy_characters', 'soldier', 'green') # Corrected for new structure
    info(f"\n--- Testing load_enemy_animations for Green Soldier: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_enemy_animations = load_enemy_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    if loaded_green_enemy_animations:
        info(f"Assets Test (Green Soldier): Successfully loaded ENEMY animation data. Found states: {', '.join(k for k,v in loaded_green_enemy_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
    else: error("\nAssets Test (Green Soldier): ENEMY Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    knight_asset_folder_relative = os.path.join('assets', 'enemy_characters', 'knight') # Corrected for new structure
    info(f"\n--- Testing generic load_enemy_animations for Knight (EXPECTS __Idle.gif etc.): '{knight_asset_folder_relative}' ---")
    loaded_knight_as_generic_animations = load_enemy_animations(relative_asset_folder=knight_asset_folder_relative)
    if loaded_knight_as_generic_animations:
        info(f"Assets Test (Knight as Generic): Found generic keys: {', '.join(k for k,v in loaded_knight_as_generic_animations.items() if v and not _is_placeholder_qpixmap_check(v[0]))}")
        if 'idle' in loaded_knight_as_generic_animations and loaded_knight_as_generic_animations['idle'] and not _is_placeholder_qpixmap_check(loaded_knight_as_generic_animations['idle'][0]):
            info("  '__Idle.gif' for Knight (as generic) seems to be present and loaded.")
        else:
            error("  '__Idle.gif' for Knight (as generic) is MISSING or FAILED to load.")
    else:
        error(f"\nAssets Test (Knight as Generic): Animation loading FAILED for '{knight_asset_folder_relative}' using generic enemy loader.")

    # Test a specific file that should exist
    chest_path_relative = getattr(C, 'CHEST_CLOSED_SPRITE_PATH', 'assets/items/chest.gif')
    chest_path_abs = resource_path(chest_path_relative)
    info(f"\n--- Testing load_gif_frames for Chest: '{chest_path_abs}' (Original relative: '{chest_path_relative}') ---")
    chest_frames = load_gif_frames(chest_path_abs)
    if chest_frames and not _is_placeholder_qpixmap_check(chest_frames[0]):
        info(f"Assets Test (Chest): Successfully loaded {len(chest_frames)} frames for chest.")
    else:
        error(f"Assets Test (Chest): FAILED to load frames for chest from '{chest_path_abs}'.")

    info("Assets.py direct run test finished.")