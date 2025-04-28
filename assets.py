# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations.
Includes resource_path function for PyInstaller compatibility.
"""
import pygame
import os
import sys  # Required for resource_path
from PIL import Image
import numpy as np # Pillow might use this

# Import constants (specifically colors for placeholders)
from constants import RED, BLACK, BLUE

# --- Resource Path Function (for PyInstaller) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not running as a bundled app (_MEIPASS attribute does not exist),
        # use the directory of the current script file (__file__)
        base_path = os.path.abspath(os.path.dirname(__file__))

    # Join the base path (either _MEIPASS or the script's dir) with the relative path
    return os.path.join(base_path, relative_path)
# --- End Resource Path Function ---


# --- Asset Loading Functions ---
def load_gif_frames(filename):
    """
    Loads frames from a GIF file using Pillow and converts them to Pygame Surfaces.
    Uses resource_path to find the file correctly when bundled.
    """
    frames = []
    # Get the correct absolute path using resource_path
    full_path = resource_path(filename)

    try:
        # Use Pillow to open the GIF using the resolved full path
        pil_gif = Image.open(full_path)
        frame_num = 0
        while True:
            try:
                # Seek to the next frame
                pil_gif.seek(frame_num)
                current_pil_frame = pil_gif.copy()
                # Convert to RGBA for consistency
                rgba_frame = current_pil_frame.convert('RGBA')
                frame_data = rgba_frame.tobytes()
                frame_size = rgba_frame.size

                # Create Pygame surface directly from RGBA buffer
                surface = pygame.image.frombuffer(frame_data, frame_size, "RGBA")

                # Ensure optimal format for Pygame blitting
                surface = surface.convert_alpha()
                frames.append(surface)
                frame_num += 1

            except EOFError:
                # Reached the end of the GIF frames
                break
            except Exception as e:
                print(f"Error processing frame {frame_num} in '{full_path}': {e}")
                frame_num += 1 # Try next frame

        if not frames:
             print(f"Error: No frames loaded from '{full_path}'. Creating placeholder.")
             # Create placeholder surface
             placeholder = pygame.Surface((30, 40)).convert_alpha()
             placeholder.fill(RED)
             pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
             return [placeholder] # Return placeholder list
        return frames

    except FileNotFoundError:
        print(f"Error: GIF file not found: '{full_path}'")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
        return [placeholder] # Return placeholder list
    except Exception as e:
        print(f"Error loading GIF '{full_path}' with Pillow: {e}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 2)
        return [placeholder] # Return placeholder list


def load_all_player_animations(asset_folder='player1'):
    """
    Loads all animations for the player/enemy using the defined map.
    Passes relative paths to load_gif_frames, which handles resource_path internally.
    """
    animations = {}
    # Define the animation mapping
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
    }

    print(f"Loading animations from asset folder: '{asset_folder}'")
    missing_files = [] # Store full paths of missing files for logging
    failed_files = [] # Store full paths of files found but failed to load

    for name, filename in anim_files_map.items():
        # Construct the *relative* path from the script's perspective
        relative_path = os.path.join(asset_folder, filename)

        # Load using the relative path (load_gif_frames handles resource_path)
        loaded_frames = load_gif_frames(relative_path)
        animations[name] = loaded_frames

        # Check if loading failed (placeholder returned)
        # Placeholder surface is identifiable if needed, but checking length is easier
        # For simplicity, assume any list with 1 element could be a placeholder
        # A more robust check would compare the returned surface to a known placeholder instance
        if len(loaded_frames) == 1:
            # Check if the file was actually missing or just failed to load
            full_path_check = resource_path(relative_path)
            if not os.path.exists(full_path_check):
                if full_path_check not in missing_files:
                    missing_files.append(full_path_check)
            else:
                # File exists but loading failed (error printed in load_gif_frames)
                if full_path_check not in failed_files:
                     failed_files.append(full_path_check)
                # If it's not 'idle', ensure the placeholder is the blue cross one
                if name != 'idle':
                    placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
                    pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
                    animations[name] = [placeholder] # Overwrite red placeholder with blue cross one

    # Log missing/failed files
    if missing_files:
        print("\n--- Missing Animation Files ---")
        print("(Paths shown might be temporary paths if running bundled)")
        for f in missing_files: print(f"- {f}")
        print("-----------------------------\n")
    if failed_files:
        print("\n--- Found But Failed to Load Animation Files ---")
        print("(Check file integrity or Pillow compatibility. Paths shown might be temporary paths if running bundled)")
        for f in failed_files: print(f"- {f}")
        print("--------------------------------------------------\n")

    # Critical check for idle animation
    # Needs to handle case where 'idle' key exists but list is empty or contains only placeholder
    if 'idle' not in animations or not animations['idle'] or (len(animations['idle'])==1 and resource_path(os.path.join(asset_folder, anim_files_map['idle'])) in missing_files + failed_files):
        print("CRITICAL ERROR: Idle animation missing or failed to load. Check file path and integrity.")
        placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(RED)
        animations = {'idle': [placeholder]} # Ensure a minimal dict exists
        return None # Indicate critical failure

    # Provide final placeholders for any *other* states that are still missing/empty
    # This ensures all keys exist in the returned dictionary
    for name in anim_files_map:
        if name not in animations or not animations[name]:
            full_path_check = resource_path(os.path.join(asset_folder, anim_files_map[name]))
            if full_path_check not in missing_files and full_path_check not in failed_files:
                print(f"Warning: State '{name}' was unexpectedly missing after initial load. Providing placeholder.")

            placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
            pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
            animations[name] = [placeholder]

    print(f"Finished loading animations. {len(animations)} states processed.")
    return animations