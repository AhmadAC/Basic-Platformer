# assets.py
# -*- coding: utf-8 -*-
## version 1.0.0.9 (Corrected resource_path for dev mode)
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
    # info("Assets: Successfully imported 'constants' as C and attributes.") # Less verbose for editor
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
def get_project_root_dev_mode() -> str:
    """
    Determines the project root when running in development mode.
    This function assumes that 'assets.py' is located directly within the project root directory.
    Example: ProjectRoot/assets.py
    """
    # os.path.abspath(__file__) gives the absolute path to this current file (assets.py)
    # os.path.dirname() then gives the directory containing this file.
    # If assets.py is at ProjectRoot/assets.py, then this is ProjectRoot.
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for development and for PyInstaller.
    When running as a PyInstaller bundle (especially --onedir or --onefile),
    assets are often bundled relative to sys._MEIPASS.

    This function is intended for general game assets (images, sounds, fonts)
    that are bundled with the application.
    Map files (.py, .json) are handled using C.MAPS_DIR directly by consuming code.

    Args:
        relative_path (str): The path to the resource relative to the project root
                             (or where assets are expected to be by PyInstaller's bundling).

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        # When bundled, relative_path should be relative to the bundle root (where _MEIPASS points)
        # e.g., if 'characters' is at the root of your bundle, relative_path would be 'characters/...'
        # debug(f"Assets (resource_path): Running bundled. _MEIPASS base path: {base_path}") # Less verbose for editor
    except AttributeError:
        # Not bundled, running in development mode.
        base_path = get_project_root_dev_mode()
        # debug(f"Assets (resource_path): Running in dev mode. Project root base path: {base_path}") # Less verbose for editor

    full_asset_path = os.path.join(base_path, relative_path)
    # Normalization can be done here or in the calling function (editor_assets.py does it)
    # full_asset_path = os.path.normpath(full_asset_path)
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
                # Ensure conversion to RGBA for consistent handling, especially for transparency
                rgba_pil_frame = current_pil_frame.convert('RGBA')
                frame_pixel_data = rgba_pil_frame.tobytes() # "raw", "RGBA"
                frame_dimensions = rgba_pil_frame.size
                # Create Pygame surface from RGBA pixel data
                pygame_surface_frame = pygame.image.frombuffer(frame_pixel_data, frame_dimensions, "RGBA")
                pygame_surface_frame = pygame_surface_frame.convert_alpha() # Optimize for Pygame display
                loaded_frames.append(pygame_surface_frame)
                frame_index += 1
            except EOFError:
                # End of frames in the GIF
                break
            except Exception as e_frame:
                error(f"Assets Error: Processing frame {frame_index} in '{full_path_to_gif_file}': {e_frame}")
                frame_index += 1 # Attempt to continue to next frame if possible

        if not loaded_frames:
             error(f"Assets Error: No frames loaded from '{full_path_to_gif_file}'. Creating a RED placeholder.")
             placeholder_surface = pygame.Surface((30, 40)).convert_alpha() # Standard placeholder size
             placeholder_surface.fill(RED)
             pygame.draw.rect(placeholder_surface, BLACK, placeholder_surface.get_rect(), 1)
             return [placeholder_surface]
        return loaded_frames
    except FileNotFoundError:
        error(f"Assets Error: GIF file not found at provided path: '{full_path_to_gif_file}'")
    except Exception as e_load:
        error(f"Assets Error: Loading GIF '{full_path_to_gif_file}' with Pillow: {e_load}")

    # Fallback placeholder if any error occurs during loading
    placeholder_surface_on_error = pygame.Surface((30, 40)).convert_alpha()
    placeholder_surface_on_error.fill(RED)
    pygame.draw.rect(placeholder_surface_on_error, BLACK, placeholder_surface_on_error.get_rect(), 2)
    return [placeholder_surface_on_error]


# --- Player/Enemy Animation Loading Function ---
def load_all_player_animations(relative_asset_folder: str = 'characters/player1') -> Optional[Dict[str, List[pygame.Surface]]]:
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
        'frozen': '__Frozen.gif',
        'defrost': '__Defrost.gif',
        'aflame': '__Aflame.gif',       # Initial standing fire (plays once then to 'burning')
        'burning': '__Burning.gif',     # Looping standing/moving fire
        'aflame_crouch': '__Aflame_crouch.gif', # Initial fire while crouching (plays once then to 'burning_crouch')
        'burning_crouch': '__Burning_crouch.gif',# Looping fire while crouching
        'deflame': '__Deflame.gif',     # Standing fire going out
        'deflame_crouch': '__Deflame_crouch.gif',# Crouched fire going out
        # Note: 'petrified' and 'smashed' for players/enemies are typically common assets (like Stone.png/StoneSmashed.gif)
        # and are loaded directly in Player/EnemyBase classes, not per character folder here.
        # If character-specific versions were desired, they could be added to this map.
    }

    # info(f"Assets Info: Attempting to load animations from relative folder: '{relative_asset_folder}'") # Less verbose for editor
    missing_files_log: List[tuple[str, str, str]] = []

    for anim_state_name, gif_filename in animation_filenames_map.items():
         # relative_asset_folder is like "characters/player1"
         # gif_filename is like "__Idle.gif"
         # The path passed to resource_path should be relative to the project root.
         relative_path_to_gif_for_resource_path = os.path.join(relative_asset_folder, gif_filename)
         absolute_gif_path = resource_path(relative_path_to_gif_for_resource_path)

         # os.path.exists should now work correctly with the absolute path
         if not os.path.exists(absolute_gif_path):
             missing_files_log.append(
                 (anim_state_name, relative_path_to_gif_for_resource_path, absolute_gif_path)
             )
             animations_dict[anim_state_name] = [] # Mark as missing so fallback logic can apply
             continue

         loaded_animation_frames = load_gif_frames(absolute_gif_path)
         animations_dict[anim_state_name] = loaded_animation_frames

         # Check if loading resulted in the default RED placeholder (meaning loading itself failed internally)
         if not animations_dict[anim_state_name] or \
            (len(animations_dict[anim_state_name]) == 1 and \
             animations_dict[anim_state_name][0].get_size() == (30,40) and \
             animations_dict[anim_state_name][0].get_at((0,0)) == RED):
             warning(f"Assets Warning: Failed to load frames for state '{anim_state_name}' from existing file '{absolute_gif_path}' for '{relative_asset_folder}'. RED Placeholder used.")

    if missing_files_log:
        warning(f"\n--- Assets: Missing Animation Files Detected for '{relative_asset_folder}' ---")
        try: base_path_for_log = sys._MEIPASS
        except AttributeError: base_path_for_log = get_project_root_dev_mode() # Use corrected root for dev
        for name, rel_path, res_path_checked in missing_files_log:
            warning(f"- State '{name}': Expected relative path (for resource_path): '{rel_path}', Resolved path checked: '{res_path_checked}'")
        info(f"(Asset loading base path used by resource_path for these assets: '{base_path_for_log}')")
        warning("-----------------------------------------------------------------\n")

    # Critical check for 'idle' animation
    idle_anim_is_missing_or_placeholder = (
        'idle' not in animations_dict or
        not animations_dict['idle'] or
        (len(animations_dict['idle']) == 1 and
         animations_dict['idle'][0].get_size() == (30,40) and
         animations_dict['idle'][0].get_at((0,0)) == RED)
    )

    if idle_anim_is_missing_or_placeholder:
        idle_file_rel_path_for_resource_path = os.path.join(relative_asset_folder, animation_filenames_map.get('idle', '__Idle.gif'))
        idle_file_abs_path_checked = resource_path(idle_file_rel_path_for_resource_path) # Use corrected resource_path
        if 'idle' not in animations_dict or not animations_dict['idle']: # File truly missing
            critical(f"CRITICAL Assets Error: 'idle' animation file ('{idle_file_rel_path_for_resource_path}') for '{relative_asset_folder}' not found or empty. Checked: '{idle_file_abs_path_checked}'.")
        else: # File existed, but load_gif_frames returned placeholder
            critical(f"CRITICAL Assets Error: 'idle' animation for '{relative_asset_folder}' failed to load correctly (is RED placeholder) from '{idle_file_abs_path_checked}'.")
        warning(f"Assets: Returning None for '{relative_asset_folder}' due to critical 'idle' animation failure.")
        return None


    # Provide blue placeholder for other missing/failed animations (if idle is okay)
    for anim_name_check in animation_filenames_map:
        if anim_name_check == 'idle': continue # Idle already handled

        animation_is_missing_or_placeholder = (
            anim_name_check not in animations_dict or
            not animations_dict[anim_name_check] or
            (len(animations_dict[anim_name_check]) == 1 and
             animations_dict[anim_name_check][0].get_size() == (30,40) and
             animations_dict[anim_name_check][0].get_at((0,0)) == RED)
        )

        if animation_is_missing_or_placeholder:
            # Differentiate between file missing vs. load failed
            if anim_name_check not in animations_dict or not animations_dict[anim_name_check]:
                 warning(f"Assets Warning: Animation state '{anim_name_check}' (file likely missing for '{relative_asset_folder}'). Providing a BLUE placeholder.")
            else: # File existed, but load_gif_frames returned placeholder
                 warning(f"Assets Warning: Animation state '{anim_name_check}' (load failed for '{relative_asset_folder}', is RED placeholder). Using a BLUE placeholder.")

            blue_placeholder = pygame.Surface((30, 40)).convert_alpha() # Standard placeholder size
            blue_placeholder.fill(BLUE)
            pygame.draw.line(blue_placeholder, RED, (0,0), (30,40), 2) # Diagonal cross
            pygame.draw.line(blue_placeholder, RED, (0,40), (30,0), 2)
            animations_dict[anim_name_check] = [blue_placeholder]

    # info(f"Assets Info: Finished loading animations. {len(animations_dict)} animation states processed for '{relative_asset_folder}'.") # Less verbose for editor
    return animations_dict
# ------------------------------------------


# --- Example Usage (if assets.py is run directly for testing) ---
if __name__ == "__main__":
    # This block is for testing assets.py itself from the command line.
    # It helps verify that resource_path and animation loading work as expected.
    info("Running assets.py directly for testing...")
    pygame.init() # Pygame init is needed for Surface creation

    info(f"\n--- Testing resource_path (from assets.py direct run) ---")
    info(f"Development Project Root (get_project_root_dev_mode()): {get_project_root_dev_mode()}")
    test_relative_asset_path = os.path.join('characters', 'player1', '__Idle.gif') # Example asset
    resolved_test_asset_path = resource_path(test_relative_asset_path)
    info(f"Resolved path for asset '{test_relative_asset_path}': {resolved_test_asset_path}")
    info(f"Does asset exist at resolved path? {os.path.exists(resolved_test_asset_path)}")

    # --- Testing map path resolution (using C.MAPS_DIR directly from constants) ---
    info(f"\n--- Testing map path resolution (using C.MAPS_DIR from constants) ---")
    # MAPS_DIR_FOR_TESTING is already set from constants import
    # Constants.py now handles its own MAPS_DIR resolution based on bundled/dev mode.
    # So, MAPS_DIR_FOR_TESTING should be the correct absolute path.
    test_map_filename = "test_map_for_assets_py.py" # Use a distinct name
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

    # Test loading Player 1 animations
    player1_asset_folder_relative = os.path.join('characters', 'player1') # Relative to project root
    info(f"\n--- Testing load_all_player_animations for Player 1: '{player1_asset_folder_relative}' ---")
    loaded_player1_animations = load_all_player_animations(relative_asset_folder=player1_asset_folder_relative)
    if loaded_player1_animations:
        info(f"Assets Test (Player 1): Successfully loaded animation data. Found states: {', '.join(k for k,v in loaded_player1_animations.items() if v)}")
        # Check a few key animations
        for anim_key in ['idle', 'run', 'aflame', 'burning', 'frozen']:
            if anim_key in loaded_player1_animations and loaded_player1_animations[anim_key]:
                first_frame = loaded_player1_animations[anim_key][0]
                # Check if it's a placeholder
                if first_frame.get_size() == (30,40) and (first_frame.get_at((0,0)) == RED or first_frame.get_at((0,0)) == BLUE):
                     warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Player 1): Animation '{anim_key}' loaded with {len(loaded_player1_animations[anim_key])} frames. First frame size: {first_frame.get_size()}")
            else:
                warning(f"Assets Test (Player 1) WARNING: Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Player 1): Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    # Test loading Green Enemy animations
    green_enemy_asset_folder_relative = os.path.join('characters', 'green') # Relative to project root
    info(f"\n--- Testing load_all_player_animations for Green Enemy: '{green_enemy_asset_folder_relative}' ---")
    loaded_green_animations = load_all_player_animations(relative_asset_folder=green_enemy_asset_folder_relative)
    if loaded_green_animations:
        info(f"Assets Test (Green Enemy): Successfully loaded animation data. Found states: {', '.join(k for k,v in loaded_green_animations.items() if v)}")
        for anim_key in ['idle', 'run', 'attack', 'death', 'hit']:
            if anim_key in loaded_green_animations and loaded_green_animations[anim_key]:
                first_frame = loaded_green_animations[anim_key][0]
                if first_frame.get_size() == (30,40) and (first_frame.get_at((0,0)) == RED or first_frame.get_at((0,0)) == BLUE):
                     warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' is a RED/BLUE placeholder.")
                else:
                     info(f"Assets Test (Green Enemy): Animation '{anim_key}' loaded with {len(loaded_green_animations[anim_key])} frames. First frame size: {first_frame.get_size()}")
            else:
                warning(f"Assets Test (Green Enemy) WARNING: Animation '{anim_key}' missing or empty after load.")
    else:
        error("\nAssets Test (Green Enemy): Animation loading FAILED (returned None). Likely critical 'idle' issue.")

    pygame.quit()
    info("Assets.py direct run test finished.")