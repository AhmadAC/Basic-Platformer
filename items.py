# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
"""
import pygame
import os
import random

# Import necessary components
import constants as C
from assets import load_gif_frames # Use the existing GIF loader

class Chest(pygame.sprite.Sprite):
    """
    A chest that restores player health when collected.
    """
    def __init__(self, x, y):
        super().__init__()

        # Construct the full path relative to the main script location
        chest_gif_path = os.path.join('characters', 'items', 'chest.gif')
        print(f"Attempting to load chest GIF from: {os.path.abspath(chest_gif_path)}") # Debug print absolute path

        self.frames = load_gif_frames(chest_gif_path)
        if not self.frames:
            # Provide a fallback surface if loading fails
            print(f"Error: Failed to load {chest_gif_path}. Using placeholder.")
            self.image = pygame.Surface((30, 30)).convert_alpha()
            self.image.fill(C.RED) # Use a color from constants
            pygame.draw.rect(self.image, C.BLACK, self.image.get_rect(), 1)
            self._valid_init = False
        else:
            self.image = self.frames[0] # Use the first frame
            self._valid_init = True
            print(f"Successfully loaded {len(self.frames)} frame(s) for chest.")

        self.rect = self.image.get_rect(midbottom=(x, y))
        self.pos = pygame.math.Vector2(x, y) # Store position if needed later

        # Animation state (if GIF is animated)
        self.current_frame = 0
        self.last_anim_update = pygame.time.get_ticks()
        self.is_collected = False # Flag to prevent multiple collections

    def update(self, dt):
        """ Handles animation if the GIF has multiple frames. dt is not used here yet. """
        if not self._valid_init or len(self.frames) <= 1:
            return # No animation needed or failed init

        now = pygame.time.get_ticks()
        # Adjust ANIM_FRAME_DURATION if chest animation speed should differ
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION * 2: # Example: slower animation
            self.last_anim_update = now
            self.current_frame = (self.current_frame + 1) % len(self.frames) # Loop animation
            current_midbottom = self.rect.midbottom # Store position anchor
            self.image = self.frames[self.current_frame]
            # Re-center rect if frame sizes differ significantly
            self.rect = self.image.get_rect(midbottom=current_midbottom)

    def collect(self, player):
        """ Action when the player collects the chest. """
        if not self.is_collected:
            print("Player collected chest!")
            player.heal_to_full()
            self.is_collected = True
            self.kill() # Remove sprite from all groups it belongs to