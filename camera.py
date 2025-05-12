# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport.
"""
import pygame

class Camera:
    def __init__(self, level_width, level_height, screen_width, screen_height):
        """
        Initializes the camera.

        Args:
            level_width (int): The total width of the game level.
            level_height (int): The total height of the game level.
            screen_width (int): The width of the game screen/window.
            screen_height (int): The height of the game screen/window.
        """
        self.camera_rect = pygame.Rect(0, 0, screen_width, screen_height)
        self.level_width = level_width
        self.level_height = level_height
        self.screen_width = screen_width
        self.screen_height = screen_height

    def apply(self, target):
        """
        Applies the camera offset to a target sprite or rect.

        Args:
            target (pygame.sprite.Sprite or pygame.Rect): The sprite or rect to offset.

        Returns:
            pygame.Rect: A new Rect representing the target's position on the screen.
        """
        if isinstance(target, pygame.sprite.Sprite):
            return target.rect.move(self.camera_rect.topleft)
        elif isinstance(target, pygame.Rect):
            return target.move(self.camera_rect.topleft)
        else:
            # Handle other types if necessary, or raise an error
            raise TypeError("Camera.apply() target must be a Sprite or Rect.")


    def update(self, target_sprite):
        """
        Updates the camera's position to follow the target_sprite.

        Args:
            target_sprite (pygame.sprite.Sprite): The sprite the camera should follow.
                                                 Expected to have a 'rect' attribute.
        """
        if not target_sprite or not hasattr(target_sprite, 'rect'):
            # print("Warning: Camera update called with invalid target_sprite.")
            self.static_update() # Keep camera still if no valid target
            return

        # Calculate the desired camera position to center the target
        # The camera's topleft x should be such that when added to the target's x,
        # the target appears in the center of the screen.
        # So, target_x + camera_offset_x = screen_center_x
        # camera_offset_x = screen_center_x - target_x
        # The camera_rect.x stores a NEGATIVE offset.
        x = -target_sprite.rect.centerx + int(self.screen_width / 2)
        y = -target_sprite.rect.centery + int(self.screen_height / 2)

        # Clamp scrolling to level boundaries
        # Prevent camera from showing areas outside the level
        x = min(0, x)  # Don't scroll beyond the left edge of the level
        y = min(0, y)  # Don't scroll beyond the top edge of the level

        # Don't scroll beyond the right edge of the level
        # If camera_rect.width (screen_width) is greater than level_width, this ensures x stays at 0
        x = max(-(self.level_width - self.screen_width), x)
        # Don't scroll beyond the bottom edge of the level
        # If camera_rect.height (screen_height) is greater than level_height, this ensures y stays at 0
        y = max(-(self.level_height - self.screen_height), y)


        self.camera_rect.x = x
        self.camera_rect.y = y

    def static_update(self):
        """
        Called when there's no target to follow.
        The camera remains in its current position.
        (Currently does nothing, but can be expanded if needed)
        """
        pass # Camera position doesn't change

    def get_pos(self):
        """ Returns the camera's current topleft offset (usually negative or zero values). """
        return (self.camera_rect.x, self.camera_rect.y)

    def set_pos(self, x, y):
        """ Manually sets the camera's topleft offset. """
        self.camera_rect.x = x
        self.camera_rect.y = y