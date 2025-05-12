# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper for PyInstaller compatibility.
"""
# version 1.00000.1
import pygame
import os
import sys # Needed for resource_path logic (imported via assets)
import random

# Import necessary components
import constants as C
# Import BOTH the loader AND the path helper from assets.py
from assets import load_gif_frames, resource_path

class Chest(pygame.sprite.Sprite):
    """
    A chest that restores player health when collected.
    """
    def __init__(self, x, y):
        super().__init__()

        # --- Define the relative path to the asset ---
        # This path is relative to the project root (or wherever resource_path resolves from)
        relative_chest_path = os.path.join('characters', 'items', 'chest.gif')

        # --- Use resource_path to get the correct full path ---
        # resource_path figures out if we're running bundled or locally
        full_chest_path = resource_path(relative_chest_path)
        print(f"Attempting to load chest GIF from resolved path: {full_chest_path}") # Debug print resolved path

        # --- Load frames using the full path ---
        self.frames = load_gif_frames(full_chest_path)

        # --- Error Handling and Placeholder ---
        # Check if loading failed OR if load_gif_frames returned its standard red placeholder
        # (assuming the standard placeholder size is 30x40 from assets.py)
        is_placeholder = False
        if self.frames and len(self.frames) == 1:
             placeholder_check_surf = self.frames[0]
             # Basic check based on size and maybe color (adjust size if your placeholder is different)
             if placeholder_check_surf.get_size() == (30, 40) and placeholder_check_surf.get_at((0,0)) == C.RED:
                 is_placeholder = True

        if not self.frames or is_placeholder:
            # Provide a specific fallback surface for the chest if loading fails OR returns default placeholder
            if not self.frames:
                print(f"Error: Failed to load chest from '{full_chest_path}'. Using placeholder.")
            else: # It returned a placeholder
                print(f"Warning: Chest loaded as a default placeholder from '{full_chest_path}'. Check file/path.")

            self.image = pygame.Surface((30, 30)).convert_alpha()
            self.image.fill(C.YELLOW) # Use a distinct placeholder color for chest issues
            pygame.draw.rect(self.image, C.BLACK, self.image.get_rect(), 1)
            pygame.draw.line(self.image, C.BLACK, (0, 0), (30, 30), 1) # Add cross to placeholder
            pygame.draw.line(self.image, C.BLACK, (0, 30), (30, 0), 1)
            self.frames = [self.image] # Make frames list contain the specific chest placeholder
            self._valid_init = False # Indicate potential issue, though it might still draw
        else:
            # Successfully loaded actual frames
            self.image = self.frames[0] # Use the first frame
            self._valid_init = True
            print(f"Successfully loaded {len(self.frames)} frame(s) for chest.")

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.pos = pygame.math.Vector2(x, y) # Store position if needed later

        # Animation state
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()
        self.is_collected = False # Flag to prevent multiple collections

    def update(self, dt):
        """ Handles animation if the GIF has multiple frames. dt is not used here yet. """
        # Don't animate if initialization potentially failed or only 1 frame (placeholder/static)
        if not self._valid_init or len(self.frames) <= 1:
            return

        now = pygame.time.get_ticks()
        # Adjust ANIM_FRAME_DURATION if chest animation speed should differ
        anim_speed_multiplier = 2 # Example: make chest animation slower than player/enemy
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION * anim_speed_multiplier:
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1) % len(self.frames) # Loop animation
            current_midbottom = self.rect.midbottom # Store position anchor
            self.image = self.frames[self.current_frame]
            # Re-center rect if frame sizes change during animation (unlikely for simple items)
            self.rect = self.image.get_rect(midbottom=current_midbottom) # Re-anchor rect after getting new image

    def collect(self, player):
        """ Action when the player collects the chest. """
        # Only collect if properly initialized and not already collected
        if not self.is_collected and self._valid_init:
            print("Player collected chest!")
            # Ensure player has the heal_to_full method before calling it
            if hasattr(player, 'heal_to_full') and callable(player.heal_to_full):
                player.heal_to_full()
            else:
                print("Warning: Player object does not have 'heal_to_full' method.")
            self.is_collected = True
            self.kill() # Remove sprite from all groups it belongs to