# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations.
Uses a helper function `resource_path` to work correctly
both locally and when packaged by PyInstaller (--onedir).
"""
import pygame
import os
import sys
from PIL import Image
import numpy as np # Pillow might use this

# Import constants (specifically colors for placeholders)
try:
    from constants import RED, BLACK, BLUE
except ImportError:
    # Provide fallback colors if constants cannot be imported (e.g., during spec generation)
    print("Warning: Failed to import constants. Using fallback colors.")
    RED = (255, 0, 0)
    BLACK = (0, 0, 0)
    BLUE = (0, 0, 255)

# --- Helper Function for PyInstaller Compatibility ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # For --onedir, _MEIPASS usually points to the executable's directory
        base_path = sys._MEIPASS
        # print(f"Running from PyInstaller bundle: _MEIPASS={base_path}") # Debug print
    except AttributeError:
        # _MEIPASS attribute not found, running in normal Python environment
        # Assume assets are relative to the main script or project root.
        # Using os.path.abspath(".") assumes you run your script from the project root.
        # If assets.py is not in the root, adjust accordingly, e.g.:
        # base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # If assets.py is in a 'src' subdir
        base_path = os.path.abspath(".")
        # print(f"Running locally: base_path={base_path}") # Debug print

    full_path = os.path.join(base_path, relative_path)
    # print(f"Resolved path for '{relative_path}': {full_path}") # Debug print
    return full_path
# ----------------------------------------------------

# Asset Loading (Modified to use resource_path implicitly via load_all_player_animations)
def load_gif_frames(full_path_filename):
    """Loads frames from a GIF file using Pillow and converts them to Pygame Surfaces.
       Expects the *full, resolved path* to the file."""
    frames = []
    try:
        # Use Pillow to open the GIF using the provided full path
        pil_gif = Image.open(full_path_filename)
        frame_num = 0
        while True:
            try:
                # Seek to the next frame
                pil_gif.seek(frame_num)
                current_pil_frame = pil_gif.copy()
                rgba_frame = current_pil_frame.convert('RGBA') # Ensure RGBA for transparency
                frame_data = rgba_frame.tobytes()
                frame_size = rgba_frame.size
                frame_mode = rgba_frame.mode # Should be RGBA now

                # Create Pygame surface from RGBA data
                surface = pygame.image.frombuffer(frame_data, frame_size, "RGBA")
                surface = surface.convert_alpha() # Ensure optimal format for Pygame

                frames.append(surface)
                frame_num += 1

            except EOFError:
                # Reached the end of the GIF frames
                break
            except Exception as e:
                print(f"Error processing frame {frame_num} in {full_path_filename}: {e}")
                frame_num += 1 # Try next frame even if one fails

        if not frames:
             print(f"Error: No frames loaded from {full_path_filename}. Creating placeholder.")
             placeholder = pygame.Surface((30, 40)).convert_alpha()
             placeholder.fill(RED)
             pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
             return [placeholder]
        return frames

    except FileNotFoundError:
        print(f"Error: GIF file not found at resolved path: {full_path_filename}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
        return [placeholder]
    except Exception as e:
        print(f"Error loading GIF {full_path_filename} with Pillow: {e}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 2)
        return [placeholder]

# --- Modified function to use resource_path ---
def load_all_player_animations(relative_asset_folder='characters/player1'):
    """Loads all animations for the player/enemy using the defined map.
       Uses resource_path to find the assets correctly."""
    animations = {}
    # Define the animation mapping (can be reused by Enemy if needed)
    anim_files_map = {
        'attack': '__Attack.gif', 'attack2': '__Attack2.gif', 'attack_combo': '__AttackCombo2hit.gif',
        'attack_nm': '__AttackNoMovement.gif', 'attack2_nm': '__Attack2NoMovement.gif',
        'attack_combo_nm': '__AttackComboNoMovement.gif', 'crouch': '__Crouch.gif',
        'crouch_trans': '__CrouchTransition.gif', 'crouch_walk': '__CrouchWalk.gif',
        'crouch_attack': '__CrouchAttack.gif', 'dash': '__Dash.gif', 'death': '__Death.gif',
        'death_nm': '__DeathNoMovement.gif', 'fall': '__Fall.gif', 'hit': '__Hit.gif',
        'idle': '__Idle.gif', 'jump': '__Jump.gif', 'jump_fall_trans': '__JumpFallInbetween.gif',
        'roll': '__Roll.gif', 'run': '__Run.gif', 'slide': '__SlideAll.gif',
        'slide_trans_start': '__SlideTransitionStart.gif', 'slide_trans_end': '__SlideTransitionEnd.gif',
        'turn': '__TurnAround.gif', 'wall_climb': '__WallClimb.gif',
        'wall_climb_nm': '__WallClimbNoMovement.gif', 'wall_hang': '__WallHang.gif',
        'wall_slide': '__WallSlide.gif',
        # Add 'ladder_idle' and 'ladder_climb' if you have those GIFs (currently not used)
    }

    print(f"Attempting to load animations from relative folder: '{relative_asset_folder}'")
    missing_files_details = [] # Store tuples of (name, expected_relative_path, resolved_path)

    # Determine the base path once
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".") # Or adjust as needed for your local structure

    print(f"Using base path for assets: {base_path}")

    for name, filename in anim_files_map.items():
         # Construct the relative path first (for reporting)
         relative_path_to_file = os.path.join(relative_asset_folder, filename)
         # Use resource_path to get the full, absolute path
         full_path = resource_path(relative_path_to_file)

         # Check existence using the *full* path
         if not os.path.exists(full_path):
             missing_files_details.append((name, relative_path_to_file, full_path))
             animations[name] = [] # Mark as missing
             continue # Skip loading if file doesn't exist

         # Load using the full path
         loaded_frames = load_gif_frames(full_path)
         animations[name] = loaded_frames

         if not animations[name]: # load_gif_frames returns placeholder on failure
             print(f"Warning: Failed to load frames for state '{name}' from existing file '{full_path}'. Placeholder used.")
             # Placeholder already created by load_gif_frames if loading failed after finding file
         #else:
             # print(f"Successfully loaded {len(animations[name])} frames for '{name}' from '{full_path}'") # Verbose success

    if missing_files_details:
        print("\n--- Missing Animation Files ---")
        for name, rel_path, res_path in missing_files_details:
            print(f"- State '{name}': Expected relative path: '{rel_path}', Resolved path checked: '{res_path}'")
        print(f"(Base path used: {base_path})")
        print("-----------------------------\n")
        print("Ensure these files exist relative to your script/executable OR")
        print("Ensure PyInstaller's '--add-data' or spec file 'datas' includes the asset folder correctly.")

    # Critical check for idle animation (using the placeholder if it failed)
    if 'idle' not in animations or not animations['idle'] or animations['idle'][0].get_size() == (30, 40): # Check if it's a placeholder
        is_missing = 'idle' not in animations or not animations['idle']
        is_placeholder = not is_missing and animations['idle'][0].get_size() == (30, 40) # Basic placeholder check

        if is_missing:
            print("CRITICAL ERROR: Idle animation state not found in map or file missing entirely.")
        elif is_placeholder:
             print(f"CRITICAL ERROR: Idle animation failed to load from '{resource_path(os.path.join(relative_asset_folder, anim_files_map['idle']))}'. Using placeholder.")

        # Create a minimal dummy animation to prevent crashes during init elsewhere ONLY if it's truly absent
        if is_missing:
            placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(RED)
            animations['idle'] = [placeholder] # Ensure 'idle' key exists
        # The calling function should still check for this failure state
        # Returning None might be too drastic if only idle failed but others loaded
        # Let's return the animations dict but signal the caller to check idle specifically.
        # Or, make it return None to force a halt. Let's return None for safety.
        print("Returning None due to critical idle animation failure.")
        return None # Indicate critical failure

    # Provide placeholders for any *other* missing/failed animations AFTER checking idle
    for name in anim_files_map:
        if name == 'idle': continue # Already handled

        if name not in animations or not animations[name] or animations[name][0].get_size() == (30, 40):
            if name not in animations or not animations[name]:
                 print(f"Warning: Animation state '{name}' was missing. Providing placeholder.")
            else: # It exists but must be a placeholder from load_gif_frames
                 print(f"Warning: Animation state '{name}' failed during loading. Using placeholder.")

            # Create a different placeholder for non-idle missing animations
            placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
            pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
            animations[name] = [placeholder] # Ensure the key exists with the placeholder

    print(f"Finished loading animations. {len(animations)} animation states processed.")
    return animations
# ------------------------------------------

# Example Usage (if you run this file directly for testing)
if __name__ == "__main__":
    print("Running asset loader directly for testing...")
    pygame.init() # Pygame needed for surface creation

    # --- Determine where the script thinks the 'characters' folder should be ---
    # This assumes your project structure is like:
    # project_root/
    #   assets.py
    #   constants.py
    #   main.py (or similar)
    #   characters/
    #     player1/
    #       __Idle.gif
    #       ...
    # If assets.py is in a subdirectory, adjust the relative path passed.
    test_asset_folder = 'characters/player1'
    print(f"\nTesting load_all_player_animations with relative folder: '{test_asset_folder}'")
    loaded_animations = load_all_player_animations(test_asset_folder)

    if loaded_animations:
        print(f"\nSuccessfully loaded animation data.")
        # print("Loaded states:", list(loaded_animations.keys()))
        # Example: Check frames for 'idle'
        if 'idle' in loaded_animations and loaded_animations['idle']:
            print(f"Idle animation loaded with {len(loaded_animations['idle'])} frames.")
            # Check if it's a placeholder
            if loaded_animations['idle'][0].get_width() == 30 and loaded_animations['idle'][0].get_height() == 40:
                 if loaded_animations['idle'][0].get_at((0,0)) == RED:
                     print("WARNING: Idle animation appears to be a RED placeholder!")
                 elif loaded_animations['idle'][0].get_at((0,0)) == BLUE:
                     print("WARNING: Idle animation appears to be a BLUE placeholder!")

        else:
            print("Idle animation missing or empty in returned dictionary.")
    else:
        print("\nAnimation loading failed (returned None), likely due to critical idle animation issue.")

    pygame.quit()
