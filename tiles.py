# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
"""
import pygame
from constants import GRAY, BLUE, ORANGE_RED # Import colors

class Platform(pygame.sprite.Sprite):
    """ Standard solid platform. """
    def __init__(self, x, y, width, height, color=GRAY):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        # Prevent negative width/height which causes Surface errors
        self.rect = self.image.get_rect(topleft=(x, y))
        if width <= 0 or height <= 0:
            print(f"Warning: Platform created with non-positive dimensions: w={width}, h={height} at ({x},{y})")
            # Optionally create a minimal valid rect/image or handle error
            self.image = pygame.Surface((1, 1)) # Minimal surface
            self.image.fill(color)
            self.rect = self.image.get_rect(topleft=(x,y))


class Ladder(pygame.sprite.Sprite):
    """ Climbable ladder area. """
    def __init__(self, x, y, width, height):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)
        self.image = pygame.Surface((width, height)).convert_alpha()
        self.image.set_alpha(100) # Make semi-transparent
        self.image.fill((0, 0, 0, 0)) # Fully transparent background

        # Draw visual cues (rungs, rails)
        rung_color = (40, 40, 180, 200) # Slightly transparent dark blue
        num_rungs = int(height / 15)
        if num_rungs > 0: # Avoid division by zero if height is too small
            rung_spacing = height / num_rungs
            for i in range(1, num_rungs):
                rung_y = i * rung_spacing
                pygame.draw.line(self.image, rung_color, (0, rung_y), (width, rung_y), 2)
        # Draw side rails (ensure lines are within surface bounds)
        pygame.draw.line(self.image, rung_color, (min(2, width-1), 0), (min(2, width-1), height), 3)
        pygame.draw.line(self.image, rung_color, (max(0, width - 3), 0), (max(0, width - 3), height), 3)

        self.rect = self.image.get_rect(topleft=(x, y))

class Lava(pygame.sprite.Sprite):
    """ Dangerous lava tile that damages characters. """
    def __init__(self, x, y, width, height, color=ORANGE_RED):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        # Optional: Add visual effect like simple noise/flicker
        # for _ in range(int(width*height*0.1)): # Add some darker spots
        #      px = random.randint(0, width-1)
        #      py = random.randint(0, height-1)
        #      dark_color = (max(0,color[0]-50), max(0,color[1]-20), color[2])
        #      self.image.set_at((px, py), dark_color)

# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
"""
import pygame
from constants import GRAY, BLUE, ORANGE_RED # Import colors

class Platform(pygame.sprite.Sprite):
    """ Standard solid platform. """
    def __init__(self, x, y, width, height, color=GRAY):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        # Prevent negative width/height which causes Surface errors
        self.rect = self.image.get_rect(topleft=(x, y))
        if width <= 0 or height <= 0:
            print(f"Warning: Platform created with non-positive dimensions: w={width}, h={height} at ({x},{y})")
            # Optionally create a minimal valid rect/image or handle error
            self.image = pygame.Surface((1, 1)) # Minimal surface
            self.image.fill(color)
            self.rect = self.image.get_rect(topleft=(x,y))


class Ladder(pygame.sprite.Sprite):
    """ Climbable ladder area. """
    def __init__(self, x, y, width, height):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)
        self.image = pygame.Surface((width, height)).convert_alpha()
        self.image.set_alpha(100) # Make semi-transparent
        self.image.fill((0, 0, 0, 0)) # Fully transparent background

        # Draw visual cues (rungs, rails)
        rung_color = (40, 40, 180, 200) # Slightly transparent dark blue
        num_rungs = int(height / 15)
        if num_rungs > 0: # Avoid division by zero if height is too small
            rung_spacing = height / num_rungs
            for i in range(1, num_rungs):
                rung_y = i * rung_spacing
                pygame.draw.line(self.image, rung_color, (0, rung_y), (width, rung_y), 2)
        # Draw side rails (ensure lines are within surface bounds)
        pygame.draw.line(self.image, rung_color, (min(2, width-1), 0), (min(2, width-1), height), 3)
        pygame.draw.line(self.image, rung_color, (max(0, width - 3), 0), (max(0, width - 3), height), 3)

        self.rect = self.image.get_rect(topleft=(x, y))

class Lava(pygame.sprite.Sprite):
    """ Dangerous lava tile that damages characters. """
    def __init__(self, x, y, width, height, color=ORANGE_RED):
        super().__init__()
        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=(x, y))