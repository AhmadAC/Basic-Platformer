# assets.py
# -*- coding: utf-8 -*-
## version 1.0.0.5 (Removed special map handling from resource_path; uses C.MAPS_DIR directly if needed)
"""
Handles loading game assets, primarily animations from GIF files.
Includes a helper function `resource_path` to ensure correct asset pathing
both during local development and when the game is packaged by PyInstaller.
Maps are now handled using the absolute C.MAPS_DIR from constants.py, not this resource_path.
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

# --- Import Constants (specifically colors for placeholder images and C.MAPS_DIR for testing) ---
try:
    import constants as C # Import the whole module
    RED = C.RED
    BLACK = C.BLACK
    BLUE = C.BLUE
    YELLOW = C.YELLOW
    # MAPS_DIR is used in the __main__ test block for creating a dummy map.
    # It's not used by the core asset loading functions for maps anymore.
    MAPS_DIR_FOR_TESTING = C.MAPS_DIR
    info("Assets: Successfully imported 'constants' as C and attributes.")
except ImportError:
    warning("Assets Warning: Failed to import 'constants' (using 'import constants as C'). Using fallback colors and MAPS_DIR_FOR_TESTING.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    MAPS_DIR_FOR_TESTING = "maps" # Fallback for testing only
except AttributeError as e_attr:
    warning(f"Assets Warning: Imported 'constants' but an attribute is missing: {e_attr}. Using fallback colors and MAPS_DIR_FOR_TESTING.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    if 'C' in sys.modules: # Check if module C was imported at all
        MAPS_DIR_FOR_TESTING = getattr(C, "MAPS_DIR", "maps")
    else:
        MAPS_DIR_FOR_TESTING = "maps"
except Exception as e_general_import:
    critical(f"Assets CRITICAL: Unexpected error importing 'constants': {e_general_import}. Using fallback colors and MAPS_DIR_FOR_TESTING.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    MAPS_DIR_FOR_TESTING = "maps"


# --- Helper Function for PyInstaller Compatibility ---
def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for development and for PyInstaller.
    When running as a PyInstaller bundle (especially --onedir or --onefile),
    assets are often bundled relative to sys._MEIPASS.

    This function is intended for general game assets (images, sounds, fonts)
    that are bundled with the application.
    Map files (.py, .json) are handled using C.MAPS_DIR directly.

    Args:
        relative_path (str): The path to the resource relative to the project root
                             (or where assets are expected to be by PyInstaller's bundling).

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # For a one-folder build, _MEIPASS is the directory containing the executable
        # UNLESS you are in a --onefile build, then it's a temp dir.
        # If your files are in `_internal` and `_internal` is what `sys._MEIPASS` points to,
        # then `relative_path` should be like `characters/player1/idle.gif` and it will resolve
        # to `_MEIPASS/characters/player1/idle.gif`.
        base_path = sys._MEIPASS
        # debug(f"Assets (resource_path): Running bundled. sys._MEIPASS = {base_path}")
    except AttributeError:
        # Not bundled, running in normal Python environment
        base_path = os.path.abspath(".") # Project root
        # debug(f"Assets (resource_path): Running in dev. os.path.abspath('.') = {base_path}")

    full_asset_path = os.path.join(base_path, relative_path)
    # debug(f"Assets (resource_path): relative='{relative_path}', base='{base_path}', full='{full_asset_path}'")
    return full_asset_path
# ----------------------------------------------------


# --- GIF Loading Function ---
def load_gif_frames(full_path_to_gif_file: str) -> List[pygame.Surface]:
    """
    Loads all frames from a GIF file using the Pillow library and converts them
    into a list of Pygame Surface objects. Handles transparency.
    Uses the provided full_path_to_gif_file directly.
    """
    loaded_frames: List[pygame.Surface] = []
    try:
        pil_gif_image = Image.open(full_path_to_gif_file)
        frame_index = 0
        while True:
            try:
                pil_gif_image.seek(frame_index)
                current_pil_frame = pil_gif_image.copy()
                # Ensure frame is RGBA for consistent transparency handling
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                frame_pixel_data = rgba_pil_frame.tobytes()
                frame_dimensions = rgba_pil_frame.size
                pygame_surface_frame = pygame.image.frombuffer(frame_pixel_data, frame_dimensions, "RGBA")
                pygame_surface_frame = pygame_surface_frame.convert_alpha() # Optimize for Pygame
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
        error(f"Assets Error: GIF file not found at provided path: '{full_path_to_gif_file}'")
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
    'relative_asset_folder' is the path relative to where general assets are found
    (e.g., project root in dev, sys._MEIPASS when bundled).
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
         # Construct the relative path that resource_path expects
         relative_path_to_gif_for_resource_path = os.path.join(relative_asset_folder, gif_filename)
         # Get the absolute path using resource_path for this general asset
         absolute_gif_path = resource_path(relative_path_to_gif_for_resource_path)

         if not os.path.exists(absolute_gif_path):
             missing_files_log.append(
                 (anim_state_name, relative_path_to_gif_for_resource_path, absolute_gif_path)
             )
             animations_dict[anim_state_name] = [] # Mark as missing for later placeholder generation
             continue

         loaded_animation_frames = load_gif_frames(absolute_gif_path) # Pass the direct absolute path
         animations_dict[anim_state_name] = loaded_animation_frames

         # Check if load_gif_frames returned its RED placeholder due to an internal error
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].get_size() == (30,40) and \
             animations_dict[anim_state_name][0].get_at((0,0)) == RED):
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}'. RED Placeholder used.")

    if missing_files_log:
        warning("\n--- Assets: Missing Animation Files Detected ---")
        # Determine the base_path used by resource_path for logging context
        try: base_path_for_log = sys._MEIPASS
        except AttributeError: base_path_for_log = os.path.abspath(".")

        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path (for resource_path): '{rel_path}', Resolved path checked: '{res_path_checked}'")
        info(f"(Asset loading base path used by resource_path for these assets: '{base_path_for_log}')")
        warning("--------------------------------------------\n")

    # Check for critical 'idle' animation
    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or
        (len(animations_dict['idle']) == 1 and
         animations_dict['idle'][0].get_size() == (30,40) and
         animations_dict['idle'][0].get_at((0,0)) == RED)
    )

    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path_for_resource_path = os.path.join(relative_asset_folder, animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path_for_resource_path)
        if 'idle' not in animations_dict or not animations_dict['idle']:
            critical(f"CRITICAL Assets Error: 'idle' animation file ('{idle_file_rel_path_for_resource_path}') not found or empty. Checked: '{idle_file_abs_path_checked}'.")
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
             animations_dict[anim_name_check][0].get_at((0,0)) == RED)
        )

        if animation_is_missing_or_placeholder:
            if anim_name_check not in animations_dict or not animations_dict[anim_name_check]:
                 warning(f"Assets Warning: Animation state '{anim_name_check}' (file missing). Providing a BLUE placeholder.")
            else:
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
    pygame.init() # Pygame init is needed for Surface creation

    info("\n--- Testing resource_path for a general asset ---")
    test_relative_asset_path = os.path.join('characters', 'player1', '__Idle.gif') # Example asset
    resolved_test_asset_path = resource_path(test_relative_asset_path)
    info(f"Resolved path for asset '{test_relative_asset_path}': {resolved_test_asset_path}")
    info(f"Does asset exist? {os.path.exists(resolved_test_asset_path)}")

    # --- Testing map path resolution (using C.MAPS_DIR directly) ---
    info("\n--- Testing map path resolution (using C.MAPS_DIR from constants) ---")
    # MAPS_DIR_FOR_TESTING was set at the top from C.MAPS_DIR or fallback
    test_map_filename = "test_map.py"
    absolute_map_path_for_test = os.path.join(MAPS_DIR_FOR_TESTING, test_map_filename)
    info(f"Absolute path for map '{test_map_filename}' (using C.MAPS_DIR): {absolute_map_path_for_test}")
    # Create dummy map dir and file for testing
    try:
        # Ensure the maps directory (determined by C.MAPS_DIR) exists
        if not os.path.exists(MAPS_DIR_FOR_TESTING):
            info(f"Attempting to create test maps directory: {MAPS_DIR_FOR_TESTING}")
            os.makedirs(MAPS_DIR_FOR_TESTING)
        # Create the dummy file within that directory
        with open(absolute_map_path_for_test, "w") as f:
            f.write("# Test map file created by assets.py test block")
        info(f"Does map file exist after creation at '{absolute_map_path_for_test}'? {os.path.exists(absolute_map_path_for_test)}")
    except Exception as e_test_map:
        error(f"Error creating test map file/dir: {e_test_map}")
        critical(f"Make sure the directory for MAPS_DIR_FOR_TESTING ('{MAPS_DIR_FOR_TESTING}') is writable or exists.")

    # --- Testing animation loading ---
    test_character_asset_folder = os.path.join('characters', 'player1') # This is relative for resource_path
    info(f"\n--- Testing load_all_player_animations with relative folder: '{test_character_asset_folder}' ---")

    loaded_player_animations = load_all_player_animations(relative_asset_folder=test_character_asset_folder)

    if loaded_player_animations:
        info(f"\nAssets Test: Successfully loaded animation data dictionary.")
        if 'idle' in loaded_player_animations and loaded_player_animations['idle']:
            info(f"Idle animation loaded with {len(loaded_player_animations['idle'])} frames.")
            first_idle_frame = loaded_player_animations['idle'][0]
            if first_idle_frame.get_size() == (30, 40): # Standard placeholder size
                 if first_idle_frame.get_at((0,0)) == RED:
                     warning("Assets Test WARNING: 'idle' animation appears to be the RED (load failure) placeholder!")
                 elif first_idle_frame.get_at((0,0)) == BLUE:
                     warning("Assets Test WARNING: 'idle' animation appears to be a BLUE (non-critical missing) placeholder! (This shouldn't happen for idle due to critical check)")
        else:
            error("Assets Test ERROR: 'idle' animation missing or empty in the returned dictionary (after critical check).")
    else:
        error("\nAssets Test: Animation loading failed (load_all_player_animations returned None). Likely due to critical 'idle' animation issue.")

    pygame.quit()
    info("Assets.py direct run test finished.")