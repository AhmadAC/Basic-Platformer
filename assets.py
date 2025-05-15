# assets.py
# -*- coding: utf-8 -*-
## version 1.0.0.4 (Integrated global logger)
"""
Handles loading game assets, primarily animations from GIF files.
Includes a helper function `resource_path` to ensure correct asset pathing
both during local development and when the game is packaged by PyInstaller (especially --onedir).
"""
import pygame
import os
import sys
from PIL import Image # Pillow library for GIF processing
from typing import Dict, List, Optional # For type hinting

# --- Import Logger ---
try:
    # Import the specific logging functions that check LOGGING_ENABLED
    from logger import info, debug, warning, error, critical
except ImportError:
    # Fallback if logger.py is not found - this should not happen in a correct setup
    print("CRITICAL ASSETS: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

# --- Import Constants (specifically colors for placeholder images) ---
# Attempting a different import style for diagnostics
try:
    import constants # Import the whole module
    RED = constants.RED
    BLACK = constants.BLACK
    BLUE = constants.BLUE
    YELLOW = constants.YELLOW
    MAPS_DIR = constants.MAPS_DIR # Added for assets to know where maps are, if ever needed by assets directly
    info("Assets: Successfully imported 'constants' and attributes.")
except ImportError:
    warning("Assets Warning: Failed to import 'constants' (using 'import constants'). Using fallback colors and MAPS_DIR.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    MAPS_DIR = "maps" # Fallback
except AttributeError as e_attr:
    # This block will catch if 'constants' was imported but one of the specific color names is missing.
    warning(f"Assets Warning: Imported 'constants' but an attribute is missing: {e_attr}. Using fallback colors and MAPS_DIR.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    # Safely try to get MAPS_DIR if constants module was at least partially imported
    if 'constants' in sys.modules:
        MAPS_DIR = getattr(sys.modules['constants'], "MAPS_DIR", "maps")
    else:
        MAPS_DIR = "maps"
except Exception as e_general_import: # Catch any other unexpected error during constants import
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using fallback colors and MAPS_DIR.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    MAPS_DIR = "maps" # Fallback


# --- Helper Function for PyInstaller Compatibility ---
def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for development and for PyInstaller.
    When running as a PyInstaller bundle (especially --onedir or --onefile),
    assets are often bundled relative to sys._MEIPASS.

    Args:
        relative_path (str): The path to the resource relative to the project root
                             (or where assets are expected to be found).

    Returns:
        str: The absolute path to the resource.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    # Check if relative_path is for the maps directory
    # If so, ensure it's treated as relative to the project root, not potentially sys._MEIPASS
    # This is important because maps are user-modifiable/downloadable and should be in a predictable user-accessible location.
    if relative_path.startswith(MAPS_DIR + os.sep) or relative_path == MAPS_DIR:
        # Always use os.path.abspath(".") for maps, ensuring they are in the CWD/script dir (or project root for dev)
        # and not inside _MEIPASS if bundled.
        base_path_for_maps = os.path.abspath(".")
        full_asset_path = os.path.join(base_path_for_maps, relative_path)
        # debug(f"DEBUG resource_path (map): relative='{relative_path}', base='{base_path_for_maps}', full='{full_asset_path}'")
        return full_asset_path

    full_asset_path = os.path.join(base_path, relative_path)
    # debug(f"DEBUG resource_path (asset): relative='{relative_path}', base='{base_path}', full='{full_asset_path}'")
    return full_asset_path
# ----------------------------------------------------


# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[pygame.Surface]:
    """
    Loads all frames from a GIF file using the Pillow library and converts them
    into a list of Pygame Surface objects. Handles transparency.
    """
    loaded_frames: List[pygame.Surface] = []
    try:
        pil_gif_image = Image.open(full_path_to_gif_file)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                frame_pixel_data = rgba_pil_frame.tobytes()
                frame_dimensions = rgba_pil_frame.size
                pygame_surface_frame = pygame.image.frombuffer(frame_pixel_data, frame_dimensions, "RGBA")
                pygame_surface_frame = pygame_surface_frame.convert_alpha()
                loaded_frames.append(pygame_surface_frame)
                frame_index += 1
            except EOFError:
                break # End of frames
            except Exception as e_frame:
                error(f"Assets Error: Processing frame {frame_index} in '{full_path_to_gif_file}': {e_frame}")
                frame_index += 1 # Try next frame

        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{full_path_to_gif_file}'. Creating a RED placeholder.")
             placeholder_surface = pygame.Surface((30, 40)).convert_alpha()
             placeholder_surface.fill(RED) # Use RED from constants or fallback
             pygame.draw.rect(placeholder_surface, BLACK, placeholder_surface.get_rect(), 1) # Use BLACK
             return [placeholder_surface]

        return loaded_frames

    except FileNotFoundError:
        error(f"Assets Error: GIF file not found at resolved path: '{full_path_to_gif_file}'")
    except Exception as e_load:
        error(f"Assets Error: Loading GIF '{full_path_to_gif_file}' with Pillow: {e_load}")

    # Fallback placeholder if any error occurs during loading
    placeholder_surface_on_error = pygame.Surface((30, 40)).convert_alpha()
    placeholder_surface_on_error.fill(RED) # Use RED
    pygame.draw.rect(placeholder_surface_on_error, BLACK, placeholder_surface_on_error.get_rect(), 2) # Use BLACK
    return [placeholder_surface_on_error]


# --- Player/Enemy Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[pygame.Surface]]]:
    """
    Loads all defined animations for a character.
    """
    animations_dict: Dict[str, List[pygame.Surface]] = {}
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
    }

    info(f"Assets Info: Attempting to load animations from relative folder: '{relative_asset_folder}'")
    missing_files_log: List[tuple[str, str, str]] = []

    for anim_state_name, gif_filename in animation_filenames_map.items():
         relative_path_to_gif = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(relative_path_to_gif)

         if not os.path.exists(absolute_gif_path):
             missing_files_log.append(
                 (anim_state_name, relative_path_to_gif, absolute_gif_path)
             )
             animations_dict[anim_state_name] = [] # Mark as missing for later placeholder generation
             continue

         loaded_animation_frames = load_gif_frames(absolute_gif_path)
         animations_dict[anim_state_name] = loaded_animation_frames

         # Check if load_gif_frames returned its RED placeholder due to an internal error
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].get_size() == (30,40) and \
             animations_dict[anim_state_name][0].get_at((0,0)) == RED): # RED from constants/fallback
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}'. RED Placeholder used.")

    if missing_files_log:
        warning("\n--- Assets: Missing Animation Files Detected ---")
        try: base_path_for_log = sys._MEIPASS
        except AttributeError: base_path_for_log = os.path.abspath(".")

        for name, rel_path, res_path in missing_files_log:
            warning(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path}'")
        info(f"(Asset loading base path used by resource_path: '{base_path_for_log}')") # Can be info or debug
        warning("--------------------------------------------\n")

    # Check for critical 'idle' animation
    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or
        (len(animations_dict['idle']) == 1 and
         animations_dict['idle'][0].get_size() == (30,40) and
         animations_dict['idle'][0].get_at((0,0)) == RED) # RED from constants/fallback
    )

    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path = os.path.join(relative_asset_folder, animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path)
        if 'idle' not in animations_dict or not animations_dict['idle']:
            critical(f"CRITICAL Assets Error: 'idle' animation file ('{idle_file_rel_path}') not found or empty. Checked: '{idle_file_abs_path_checked}'.")
        else: # It's the RED placeholder
            critical(f"CRITICAL Assets Error: 'idle' animation failed to load correctly (is RED placeholder) from '{idle_file_abs_path_checked}'.")
        warning("Assets: Returning None due to critical 'idle' animation failure.")
        return None

    # Provide blue placeholders for other missing/failed non-critical animations
    for anim_name_check in animation_filenames_map:
        if anim_name_check == 'idle': continue # Already handled

        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].get_size() == (30,40) and
             animations_dict[anim_name_check][0].get_at((0,0)) == RED) # RED from constants/fallback
        )

        if animation_is_missing_or_placeholder:
            if anim_name_check not in animations_dict or not animations_dict[anim_name_check]:
                 # This case means the file was missing (missing_files_log handled the print)
                 # and animations_dict[anim_name_check] was set to []
                 warning(f"Assets Warning: Animation state '{anim_name_check}' (file missing). Providing a BLUE placeholder.")
            else: # This case means file existed but load_gif_frames returned the RED placeholder
                 warning(f"Assets Warning: Animation state '{anim_name_check}' (load failed, is RED placeholder). Using a BLUE placeholder.")

            blue_placeholder = pygame.Surface((30, 40)).convert_alpha()
            blue_placeholder.fill(BLUE) # BLUE from constants/fallback
            pygame.draw.line(blue_placeholder, RED, (0,0), (30,40), 2) # RED for cross
            pygame.draw.line(blue_placeholder, RED, (0,40), (30,0), 2)
            animations_dict[anim_name_check] = [blue_placeholder]

    info(f"Assets Info: Finished loading animations. {len(animations_dict)} animation states processed for '{relative_asset_folder}'.")
    return animations_dict
# ------------------------------------------


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    info("Running assets.py directly for testing...")
    # Pygame init is needed for Surface creation, even for tests not drawing to screen
    pygame.init()
    # Note: If constants.py is in the same dir, 'import constants' should work here.
    # If it fails here too, the problem is more fundamental with constants.py visibility.

    info("\n--- Testing resource_path ---")
    test_relative_path = 'characters/player1/__Idle.gif'
    resolved_test_path = resource_path(test_relative_path)
    info(f"Resolved path for '{test_relative_path}': {resolved_test_path}")
    info(f"Does it exist? {os.path.exists(resolved_test_path)}")

    test_map_path_rel = os.path.join(MAPS_DIR, "test_map.py") # MAPS_DIR is defined at the top
    resolved_map_path = resource_path(test_map_path_rel)
    info(f"Resolved path for map '{test_map_path_rel}': {resolved_map_path}")
    # Create dummy map dir and file for testing resource_path with maps
    try:
        if not os.path.exists(MAPS_DIR): os.makedirs(MAPS_DIR)
        with open(resolved_map_path, "w") as f: f.write("# Test map file")
        info(f"Does map file exist after creation? {os.path.exists(resolved_map_path)}")
    except Exception as e_test_map:
        error(f"Error creating test map file/dir: {e_test_map}")


    test_character_asset_folder = 'characters/player1'
    info(f"\n--- Testing load_all_player_animations with relative folder: '{test_character_asset_folder}' ---")

    loaded_player_animations = load_all_player_animations(relative_asset_folder=test_character_asset_folder)

    if loaded_player_animations:
        info(f"\nAssets Test: Successfully loaded animation data dictionary.")
        if 'idle' in loaded_player_animations and loaded_player_animations['idle']:
            info(f"Idle animation loaded with {len(loaded_player_animations['idle'])} frames.")
            first_idle_frame = loaded_player_animations['idle'][0]
            if first_idle_frame.get_size() == (30, 40): # Standard placeholder size
                 # Check color using the RED defined at the top of this file (either from constants or fallback)
                 if first_idle_frame.get_at((0,0)) == RED:
                     warning("Assets Test WARNING: 'idle' animation appears to be the RED (load failure) placeholder!")
                 elif first_idle_frame.get_at((0,0)) == BLUE: # BLUE defined at top
                     warning("Assets Test WARNING: 'idle' animation appears to be a BLUE (non-critical missing) placeholder! (This shouldn't happen for idle due to critical check)")
        else:
            error("Assets Test ERROR: 'idle' animation missing or empty in the returned dictionary (after critical check).")
    else:
        error("\nAssets Test: Animation loading failed (load_all_player_animations returned None). Likely due to critical 'idle' animation issue.")

    pygame.quit()
    info("Assets.py direct run test finished.")