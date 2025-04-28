# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations.
"""
import pygame
import os
import sys
from PIL import Image
import numpy as np # Pillow might use this

# Import constants (specifically colors for placeholders)
from constants import RED, BLACK, BLUE

# Asset Loading (Copied directly from original, ensure PIL and numpy are installed)
def load_gif_frames(filename):
    """Loads frames from a GIF file using Pillow and converts them to Pygame Surfaces."""
    frames = []
    try:
        # Use Pillow to open the GIF
        pil_gif = Image.open(filename)
        frame_num = 0
        while True:
            try:
                # Seek to the next frame
                pil_gif.seek(frame_num)
                current_pil_frame = pil_gif.copy()
                rgba_frame = current_pil_frame.convert('RGBA')
                frame_data = rgba_frame.tobytes()
                frame_size = rgba_frame.size
                frame_mode = rgba_frame.mode

                # Create Pygame surface
                if frame_mode == 'RGBA':
                    surface = pygame.image.frombuffer(frame_data, frame_size, "RGBA")
                elif frame_mode == 'RGB':
                     surface = pygame.image.frombuffer(frame_data, frame_size, "RGB")
                     surface = surface.convert_alpha() # Convert RGB to RGBA with opaque alpha
                else:
                    print(f"Warning: Unexpected PIL mode '{frame_mode}' in {filename}")
                    frame_num += 1
                    continue

                surface = surface.convert_alpha() # Ensure optimal format
                frames.append(surface)
                frame_num += 1

            except EOFError:
                # Reached the end of the GIF frames
                break
            except Exception as e:
                print(f"Error processing frame {frame_num} in {filename}: {e}")
                frame_num += 1 # Try next frame even if one fails

        if not frames:
             print(f"Error: No frames loaded from {filename}. Creating placeholder.")
             # Use constants for placeholder colors
             placeholder = pygame.Surface((30, 40)).convert_alpha()
             placeholder.fill(RED)
             pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
             return [placeholder]
        return frames

    except FileNotFoundError:
        print(f"Error: GIF file not found: {filename}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
        return [placeholder]
    except Exception as e:
        print(f"Error loading GIF {filename} with Pillow: {e}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 2)
        return [placeholder]

def load_all_player_animations(asset_folder='player1'):
    """Loads all animations for the player/enemy using the defined map."""
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

    print(f"Loading animations from folder: {asset_folder}")
    missing_files = []
    for name, filename in anim_files_map.items():
         path = os.path.join(asset_folder, filename)
         if not os.path.exists(path):
             missing_files.append(path)
             animations[name] = [] # Mark as missing
             continue # Skip loading if file doesn't exist

         animations[name] = load_gif_frames(path)
         if not animations[name]:
             print(f"Warning: Failed to load frames for state '{name}' from existing file '{path}'.")
             # Provide a fallback placeholder if loading frames failed
             if name != 'idle':
                  placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
                  pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
                  animations[name] = [placeholder]

    if missing_files:
        print("\n--- Missing Animation Files ---")
        for f in missing_files:
            print(f"- {f}")
        print("-----------------------------\n")


    # Critical check for idle animation
    if 'idle' not in animations or not animations['idle']:
        print("CRITICAL ERROR: Idle animation missing or failed to load. Check file path and integrity.")
        # Create a minimal dummy animation to prevent crashes during init elsewhere
        placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(RED)
        animations = {'idle': [placeholder]}
        # The calling function should handle the exit/critical failure based on this.
        return None # Indicate critical failure

    # Provide placeholders for any other missing animations AFTER checking idle
    for name in anim_files_map:
        if name not in animations or not animations[name]:
            print(f"Warning: Providing placeholder for missing/failed animation '{name}'.")
            placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
            pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
            animations[name] = [placeholder]


    print(f"Finished loading animations. {len(animations)} states found.")

# -*- coding: utf-8 -*-
"""
Handles loading game assets, primarily animations.
"""
import pygame
import os
import sys
from PIL import Image
import numpy as np # Pillow might use this

# Import constants (specifically colors for placeholders)
from constants import RED, BLACK, BLUE

# Asset Loading (Copied directly from original, ensure PIL and numpy are installed)
def load_gif_frames(filename):
    """Loads frames from a GIF file using Pillow and converts them to Pygame Surfaces."""
    frames = []
    try:
        # Use Pillow to open the GIF
        pil_gif = Image.open(filename)
        frame_num = 0
        while True:
            try:
                # Seek to the next frame
                pil_gif.seek(frame_num)
                current_pil_frame = pil_gif.copy()
                rgba_frame = current_pil_frame.convert('RGBA')
                frame_data = rgba_frame.tobytes()
                frame_size = rgba_frame.size
                frame_mode = rgba_frame.mode

                # Create Pygame surface
                if frame_mode == 'RGBA':
                    surface = pygame.image.frombuffer(frame_data, frame_size, "RGBA")
                elif frame_mode == 'RGB':
                     surface = pygame.image.frombuffer(frame_data, frame_size, "RGB")
                     surface = surface.convert_alpha() # Convert RGB to RGBA with opaque alpha
                else:
                    print(f"Warning: Unexpected PIL mode '{frame_mode}' in {filename}")
                    frame_num += 1
                    continue

                surface = surface.convert_alpha() # Ensure optimal format
                frames.append(surface)
                frame_num += 1

            except EOFError:
                # Reached the end of the GIF frames
                break
            except Exception as e:
                print(f"Error processing frame {frame_num} in {filename}: {e}")
                frame_num += 1 # Try next frame even if one fails

        if not frames:
             print(f"Error: No frames loaded from {filename}. Creating placeholder.")
             # Use constants for placeholder colors
             placeholder = pygame.Surface((30, 40)).convert_alpha()
             placeholder.fill(RED)
             pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
             return [placeholder]
        return frames

    except FileNotFoundError:
        print(f"Error: GIF file not found: {filename}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 1)
        return [placeholder]
    except Exception as e:
        print(f"Error loading GIF {filename} with Pillow: {e}")
        placeholder = pygame.Surface((30, 40)).convert_alpha()
        placeholder.fill(RED)
        pygame.draw.rect(placeholder, BLACK, placeholder.get_rect(), 2)
        return [placeholder]

def load_all_player_animations(asset_folder='player1'):
    """Loads all animations for the player/enemy using the defined map."""
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

    print(f"Loading animations from folder: {asset_folder}")
    missing_files = []
    for name, filename in anim_files_map.items():
         path = os.path.join(asset_folder, filename)
         if not os.path.exists(path):
             missing_files.append(path)
             animations[name] = [] # Mark as missing
             continue # Skip loading if file doesn't exist

         animations[name] = load_gif_frames(path)
         if not animations[name]:
             print(f"Warning: Failed to load frames for state '{name}' from existing file '{path}'.")
             # Provide a fallback placeholder if loading frames failed
             if name != 'idle':
                  placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
                  pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
                  animations[name] = [placeholder]

    if missing_files:
        print("\n--- Missing Animation Files ---")
        for f in missing_files:
            print(f"- {f}")
        print("-----------------------------\n")


    # Critical check for idle animation
    if 'idle' not in animations or not animations['idle']:
        print("CRITICAL ERROR: Idle animation missing or failed to load. Check file path and integrity.")
        # Create a minimal dummy animation to prevent crashes during init elsewhere
        placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(RED)
        animations = {'idle': [placeholder]}
        # The calling function should handle the exit/critical failure based on this.
        return None # Indicate critical failure

    # Provide placeholders for any other missing animations AFTER checking idle
    for name in anim_files_map:
        if name not in animations or not animations[name]:
            print(f"Warning: Providing placeholder for missing/failed animation '{name}'.")
            placeholder = pygame.Surface((30, 40)).convert_alpha(); placeholder.fill(BLUE)
            pygame.draw.line(placeholder, RED, (0,0), (30,40), 2); pygame.draw.line(placeholder, RED, (0,40), (30,0), 2)
            animations[name] = [placeholder]


    print(f"Finished loading animations. {len(animations)} states found.")
    return animations
