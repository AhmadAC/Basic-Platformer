# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport.
"""
# version 1.0.0.2 (Adapted to use absolute level Y boundaries)
import pygame

class Camera:
    def __init__(self, level_width: int, level_top_y_abs: int, level_bottom_y_abs: int, 
                 screen_width: int, screen_height: int):
        """
        Initializes the camera.

        Args:
            level_width (int): The total width of the game level.
            level_top_y_abs (int): The absolute Y coordinate of the top of the level (e.g., top of ceiling wall).
            level_bottom_y_abs (int): The absolute Y coordinate of the bottom of the level (e.g., bottom of floor wall).
            screen_width (int): The width of the game screen/window.
            screen_height (int): The height of the game screen/window.
        """
        self.camera_rect = pygame.Rect(0, 0, screen_width, screen_height)
        self.level_width = level_width
        self.level_top_y_abs = level_top_y_abs         # Absolute top Y of the entire level
        self.level_bottom_y_abs = level_bottom_y_abs   # Absolute bottom Y of the entire level
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Calculate effective level height (the total scrollable span)
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs

        # print(f"Camera Initialized: LvlW:{level_width}, LvlTopY:{level_top_y_abs}, LvlBotY:{level_bottom_y_abs} (EffH:{self.effective_level_height}), ScreenWH: {screen_width}x{screen_height}")


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
        while respecting the level boundaries defined by absolute coordinates.

        Args:
            target_sprite (pygame.sprite.Sprite): The sprite the camera should follow.
                                                 Expected to have a 'rect' attribute.
        """
        if not target_sprite or not hasattr(target_sprite, 'rect'):
            self.static_update() 
            return

        # Calculate desired camera top-left (x, y) to center the target_sprite.
        # The camera_rect.x and .y are negative offsets applied to world coordinates.
        x = -target_sprite.rect.centerx + int(self.screen_width / 2)
        y = -target_sprite.rect.centery + int(self.screen_height / 2)

        # --- Horizontal Clamping ---
        # Don't scroll left past the beginning of the level (camera_rect.x should not be > 0).
        x = min(0, x)
        # Don't scroll right past the end of the level.
        if self.level_width > self.screen_width:
            # max_camera_x ensures the right edge of the level aligns with the right edge of the screen.
            x = max(-(self.level_width - self.screen_width), x)
        else: 
            # Level is narrower than or same width as the screen, so no horizontal scrolling needed.
            # Camera x offset can be 0 to align level left, or centered if desired.
            # For now, align left by default (x=0).
            x = 0 

        # --- Vertical Clamping (using absolute level Y boundaries) ---
        if self.effective_level_height <= self.screen_height:
            # Level is shorter than or same height as the screen.
            # Center the level vertically within the screen.
            # The camera's y offset will be such that the level's visual center aligns with screen center.
            # camera_y = -(level_visual_center_y - screen_center_y)
            # level_visual_center_y = self.level_top_y_abs + self.effective_level_height / 2
            # screen_center_y = self.screen_height / 2
            y = -(self.level_top_y_abs + self.effective_level_height / 2 - self.screen_height / 2)
        else:
            # Level is taller than the screen, allow vertical scrolling.
            # Don't scroll above the level's absolute top (camera_rect.y = -level_top_y_abs).
            y = min(-self.level_top_y_abs, y)
            # Don't scroll below the level's absolute bottom.
            # The camera's y should be such that (level_bottom_y_abs + camera_rect.y) == screen_height.
            # So, camera_rect.y = screen_height - level_bottom_y_abs.
            # But since our 'y' is an offset, it's max(-(level_bottom_y_abs - screen_height), y).
            y = max(-(self.level_bottom_y_abs - self.screen_height), y)
            
        self.camera_rect.x = int(x) # Ensure integer positions for rect
        self.camera_rect.y = int(y)
        # print(f"Camera Updated: Target ({target_sprite.rect.centerx},{target_sprite.rect.centery}), CamRect ({self.camera_rect.x},{self.camera_rect.y})")


    def static_update(self):
        """
        Called when there's no target to follow or if static camera behavior is desired.
        The camera remains in its current position.
        """
        # If no target, we might want to ensure camera is still clamped,
        # especially if level dimensions changed.
        # For now, it just keeps its current position.
        # If clamping is needed even without a target, call update(None) or replicate clamping logic.
        pass 

    def get_pos(self):
        """ Returns the camera's current topleft offset (usually negative or zero values). """
        return (self.camera_rect.x, self.camera_rect.y)

    def set_pos(self, x, y):
        """ Manually sets the camera's topleft offset. """
        self.camera_rect.x = int(x)
        self.camera_rect.y = int(y)
        # print(f"Camera Position Manually Set: ({self.camera_rect.x},{self.camera_rect.y})")

    def set_level_dimensions(self, level_width: int, level_top_y_abs: int, level_bottom_y_abs: int):
        """
        Updates the camera's knowledge of the level dimensions.
        Useful if the level changes or its boundaries are redefined.

        Args:
            level_width (int): New total width of the level.
            level_top_y_abs (int): New absolute Y of the level's top.
            level_bottom_y_abs (int): New absolute Y of the level's bottom.
        """
        self.level_width = level_width
        self.level_top_y_abs = level_top_y_abs
        self.level_bottom_y_abs = level_bottom_y_abs
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs
        # print(f"Camera Level Dimensions Updated: LvlW:{self.level_width}, LvlTopY:{self.level_top_y_abs}, LvlBotY:{self.level_bottom_y_abs} (EffH:{self.effective_level_height})")
        
        # Optionally, re-clamp camera position immediately if needed:
        # For example, if a target was being tracked:
        # if self.camera_rect.x != 0 or self.camera_rect.y != 0: # Or some other check if it needs update
        #    current_target = ... (if you store it)
        #    self.update(current_target if current_target else None) 
        # Or, if no target, ensure it's valid for the new boundaries (e.g., set to default 0,0 and then clamp)
        # self.set_pos(self.camera_rect.x, self.camera_rect.y) # Re-apply existing pos to trigger clamping via update
        # (This would require self.update to correctly handle a None target for clamping)
        # For now, manual re-clamping would be done by calling update() after set_level_dimensions.

    def set_screen_dimensions(self, screen_width: int, screen_height: int):
        """
        Updates the camera's knowledge of the screen dimensions.
        Important if the game window is resized.
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.camera_rect.width = screen_width
        self.camera_rect.height = screen_height
        # print(f"Camera Screen Dimensions Updated: {self.screen_width}x{self.screen_height}")
        # After screen resize, the camera position might need re-clamping.
        # This is typically handled by calling self.update(target_sprite) in the main loop's resize event.