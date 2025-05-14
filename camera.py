# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport.
"""
# version 1.00000.1
# theres fire now
import pygame

class Camera:
    def __init__(self, level_width, level_height, screen_width, screen_height):
        """
        Initializes the camera.

        Args:
            level_width (int): The total width of the game level.
            level_height (int): The total effective height of the game level (from highest reachable to lowest point).
            screen_width (int): The width of the game screen/window.
            screen_height (int): The height of the game screen/window.
        """
        self.camera_rect = pygame.Rect(0, 0, screen_width, screen_height)
        self.level_width = level_width
        self.level_height = level_height # This should represent the full scrollable height of the level
        self.screen_width = screen_width
        self.screen_height = screen_height
        # print(f"Camera Initialized: Level WxH: {level_width}x{level_height}, Screen WxH: {screen_width}x{screen_height}")

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
            raise TypeError("Camera.apply() target must be a Sprite or Rect.")


    def update(self, target_sprite):
        """
        Updates the camera's position to follow the target_sprite.
        The camera attempts to keep the target_sprite centered on the screen,
        while respecting the level boundaries.

        Args:
            target_sprite (pygame.sprite.Sprite): The sprite the camera should follow.
                                                 Expected to have a 'rect' attribute.
        """
        if not target_sprite or not hasattr(target_sprite, 'rect'):
            self.static_update() 
            return

        # Desired camera topleft x to center target: screen_center_x - target_center_x
        # Since camera_rect.x is the offset added to world coords, it's negative.
        x = -target_sprite.rect.centerx + int(self.screen_width / 2)
        y = -target_sprite.rect.centery + int(self.screen_height / 2)

        # Clamp scrolling to level boundaries

        # Horizontal clamping:
        # Don't scroll left past the beginning of the level (x should not be > 0)
        x = min(0, x)
        # Don't scroll right past the end of the level.
        # max_camera_x is -(level_width - screen_width). If level is smaller than screen, this is positive.
        # We want camera_x to be AT LEAST this value.
        # If level_width < screen_width, we want x to be 0 to keep level fixed.
        if self.level_width > self.screen_width:
            x = max(-(self.level_width - self.screen_width), x)
        else: # Level is narrower than or equal to the screen, so no horizontal scrolling needed
            x = 0 

        # Vertical clamping:
        # Don't scroll up past the "top" of the level (y should not be > 0)
        y = min(0, y)
        # Don't scroll down past the "bottom" of the level.
        # max_camera_y is -(level_height - screen_height)
        if self.level_height > self.screen_height:
            y = max(-(self.level_height - self.screen_height), y)
        else: # Level is shorter than or equal to the screen, so no vertical scrolling needed
            y = 0
            
        self.camera_rect.x = x
        self.camera_rect.y = y
        # print(f"Camera Updated: Target ({target_sprite.rect.centerx},{target_sprite.rect.centery}), CamRect ({self.camera_rect.x},{self.camera_rect.y})")


    def static_update(self):
        """
        Called when there's no target to follow or if static camera behavior is desired.
        The camera remains in its current position.
        """
        pass 

    def get_pos(self):
        """ Returns the camera's current topleft offset (usually negative or zero values). """
        return (self.camera_rect.x, self.camera_rect.y)

    def set_pos(self, x, y):
        """ Manually sets the camera's topleft offset. """
        self.camera_rect.x = x
        self.camera_rect.y = y
        # print(f"Camera Position Manually Set: ({x},{y})")

    def set_level_dimensions(self, level_width, level_height):
        """
        Updates the camera's knowledge of the level dimensions.
        Useful if the level changes or its boundaries are redefined.
        """
        self.level_width = level_width
        self.level_height = level_height
        # print(f"Camera Level Dimensions Updated: Level WxH: {level_width}x{level_height}")
        # Optionally, re-clamp camera position immediately if needed:
        # self.update(None) # Or pass the current target if available