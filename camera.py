# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport.
"""
# version 1.0.0.6 (All logging removed from this module)
import pygame

# --- No logging imports or camera-specific log switches needed ---

class Camera:
    def __init__(self, level_width: int, level_top_y_abs: int, level_bottom_y_abs: int,
                 screen_width: int, screen_height: int):
        """
        Initializes the camera.

        Args:
            level_width (int): The total width of the game level.
            level_top_y_abs (int): The absolute Y coordinate of the top of the level.
            level_bottom_y_abs (int): The absolute Y coordinate of the bottom of the level.
            screen_width (int): The width of the game screen/window.
            screen_height (int): The height of the game screen/window.
        """
        self.camera_rect = pygame.Rect(0, 0, screen_width, screen_height)
        self.level_width = level_width
        self.level_top_y_abs = level_top_y_abs
        self.level_bottom_y_abs = level_bottom_y_abs
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs

        # No logging call here

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
            # This is a genuine error condition, so raise an exception
            raise TypeError("Camera.apply() target must be a Sprite or Rect.")

    def update(self, target_sprite):
        """
        Updates the camera's position to follow the target_sprite.

        Args:
            target_sprite (pygame.sprite.Sprite): The sprite the camera should follow.
        """
        if not target_sprite or not hasattr(target_sprite, 'rect'):
            self.static_update()
            return

        x = -target_sprite.rect.centerx + int(self.screen_width / 2)
        y = -target_sprite.rect.centery + int(self.screen_height / 2)

        x = min(0, x)
        if self.level_width > self.screen_width:
            x = max(-(self.level_width - self.screen_width), x)
        else:
            x = 0

        if self.effective_level_height <= self.screen_height:
            y = -(self.level_top_y_abs + self.effective_level_height / 2 - self.screen_height / 2)
        else:
            y = min(-self.level_top_y_abs, y)
            y = max(-(self.level_bottom_y_abs - self.screen_height), y)

        self.camera_rect.x = int(x)
        self.camera_rect.y = int(y)

        # No logging call here

    def static_update(self):
        """
        Called when there's no target to follow or if static camera behavior is desired.
        """
        pass # No action, no logging

    def get_pos(self):
        """ Returns the camera's current topleft offset. """
        return (self.camera_rect.x, self.camera_rect.y)

    def set_pos(self, x, y):
        """ Manually sets the camera's topleft offset. """
        self.camera_rect.x = int(x)
        self.camera_rect.y = int(y)
        # No logging call here

    def set_level_dimensions(self, level_width: int, level_top_y_abs: int, level_bottom_y_abs: int):
        """
        Updates the camera's knowledge of the level dimensions.
        """
        self.level_width = level_width
        self.level_top_y_abs = level_top_y_abs
        self.level_bottom_y_abs = level_bottom_y_abs
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs
        # No logging call here

    def set_screen_dimensions(self, screen_width: int, screen_height: int):
        """
        Updates the camera's knowledge of the screen dimensions.
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.camera_rect.width = screen_width
        self.camera_rect.height = screen_height
        # No logging call here