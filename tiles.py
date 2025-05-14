# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
"""
# version 1.0.0.1 (Added platform_type to Platform class)
import pygame
# Import all necessary constants, including DARK_GREEN if not already present
from constants import GRAY, BLUE, ORANGE_RED, DARK_GREEN 

class Platform(pygame.sprite.Sprite):
    """ 
    Standard solid platform.
    Can be tagged with a platform_type (e.g., "ground", "ledge", "wall").
    """
    def __init__(self, x, y, width, height, color=GRAY, platform_type="generic"):
        super().__init__()
        
        # Ensure valid dimensions for the surface
        surf_width = max(1, int(width))
        surf_height = max(1, int(height))
        
        self.image = pygame.Surface((surf_width, surf_height))
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y))
        
        self.color = color # Store the color, can be useful for debugging or logic
        self.platform_type = platform_type # Store the type of platform

        if width <= 0 or height <= 0:
            print(f"Warning: Platform created with non-positive dimensions: w={width}, h={height} at ({x},{y}). Using 1x1.")
            # Surface already created with max(1,...) dimensions, rect is based on original x,y


class Ladder(pygame.sprite.Sprite):
    """ Climbable ladder area. """
    def __init__(self, x, y, width, height):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, int(width))
        height = max(1, int(height))
        self.image = pygame.Surface((width, height)).convert_alpha()
        self.image.fill((0, 0, 0, 0)) # Fully transparent background
        self.image.set_alpha(100) # Make semi-transparent visually

        # Draw visual cues (rungs, rails)
        rung_color = (40, 40, 180, 200) # Slightly transparent dark blue
        num_rungs = int(height / 15)
        if num_rungs > 0: # Avoid division by zero if height is too small
            rung_spacing = height / num_rungs
            for i in range(1, num_rungs + 1): # Iterate to include a rung near the top
                rung_y = i * rung_spacing
                # Ensure rung_y is within bounds before drawing
                if rung_y < height -1 : # -1 to keep it within the surface
                    pygame.draw.line(self.image, rung_color, (0, rung_y), (width, rung_y), 2)
        
        # Draw side rails (ensure lines are within surface bounds)
        # Use min/max to prevent drawing outside the surface if width is very small
        rail_thickness = 3
        left_rail_x = min(rail_thickness -1, width -1) # If width=1, rail is at x=0
        right_rail_x = max(0, width - rail_thickness)   # If width=1, rail is at x=0
        
        pygame.draw.line(self.image, rung_color, (left_rail_x, 0), (left_rail_x, height), rail_thickness)
        if width > rail_thickness * 2: # Only draw second rail if there's space
             pygame.draw.line(self.image, rung_color, (right_rail_x, 0), (right_rail_x, height), rail_thickness)

        self.rect = self.image.get_rect(topleft=(x, y))

class Lava(pygame.sprite.Sprite):
    """ Dangerous lava tile that damages characters. """
    def __init__(self, x, y, width, height, color=ORANGE_RED):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, int(width))
        height = max(1, int(height))
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y))
        # Optional: Add visual effect like simple noise/flicker
        # import random
        # for _ in range(int(width*height*0.05)): # Add some darker spots
        #      px = random.randint(0, width-1)
        #      py = random.randint(0, height-1)
        #      dark_color_r = max(0, color[0]-random.randint(30,70))
        #      dark_color_g = max(0, color[1]-random.randint(10,40))
        #      dark_color_b = max(0, color[2]-random.randint(0,20))
        #      self.image.set_at((px, py), (dark_color_r, dark_color_g, dark_color_b))