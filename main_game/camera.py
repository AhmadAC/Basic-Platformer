# camera.py
# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport, using PySide6 types.
The camera's position determines what part of the game world is visible on screen.
"""
# version 2.0.3 (Enhanced robustness, logging, and clarity)

from PySide6.QtCore import QRectF, QPointF, QSizeF
from typing import Any, Optional

try:
    from main_game.logger import debug, info, warning
except ImportError:
    # Fallback logger if the main logger isn't available during isolated testing
    import logging
    logging.basicConfig(level=logging.DEBUG, format='FallbackCameraLogger - %(levelname)s - %(message)s')
    logger_fallback = logging.getLogger(__name__ + "_fallback")
    def debug(msg): logger_fallback.debug(msg)
    def info(msg): logger_fallback.info(msg)
    def warning(msg): logger_fallback.warning(msg)

class Camera:
    def __init__(self,
                 initial_level_width: float,
                 initial_world_start_x: float,
                 initial_world_start_y: float,
                 initial_level_bottom_y_abs: float,
                 screen_width: float,
                 screen_height: float):
        """
        Initializes the camera. All coordinates and dimensions are expected to be floats.

        Args:
            initial_level_width (float): The total horizontal span of the game world (e.g., max_x - min_x).
                                         Must be > 0.
            initial_world_start_x (float): The absolute leftmost X-coordinate of the game world.
            initial_world_start_y (float): The absolute topmost Y-coordinate of the game world.
            initial_level_bottom_y_abs (float): The absolute bottommost Y-coordinate of the game world.
                                                Must be > initial_world_start_y.
            screen_width (float): The initial width of the screen/viewport where the game is rendered. Must be > 0.
            screen_height (float): The initial height of the screen/viewport. Must be > 0.
        """
        self.screen_width = max(1.0, float(screen_width))
        self.screen_height = max(1.0, float(screen_height))
        
        # self.camera_rect defines the camera's view.
        # Its topLeft() QPointF stores the negative of the world coordinates that should appear
        # at the screen's (0,0). So, self.camera_rect.x() is typically <= 0.
        # Its size is always the current screen_width and screen_height.
        self.camera_rect = QRectF(0.0, 0.0, self.screen_width, self.screen_height)
        
        # World boundaries
        self.world_start_x = float(initial_world_start_x)
        self.level_top_y_abs = float(initial_world_start_y)
        self.level_width = max(1.0, float(initial_level_width)) # Ensure positive width
        self.level_bottom_y_abs = float(initial_level_bottom_y_abs)
        
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs
        if self.effective_level_height <= 0:
            warning(f"Camera Init: Effective level height is <= 0 ({self.effective_level_height}). "
                    f"BottomY: {self.level_bottom_y_abs}, TopY: {self.level_top_y_abs}. Adjusting to be at least screen height.")
            self.effective_level_height = self.screen_height # Fallback
            self.level_bottom_y_abs = self.level_top_y_abs + self.screen_height

        info(f"Camera initialized: Viewport({self.screen_width:.1f}x{self.screen_height:.1f}), "
             f"WorldBounds(X: {self.world_start_x:.1f} to {self.world_start_x + self.level_width:.1f}, "
             f"Y: {self.level_top_y_abs:.1f} to {self.level_bottom_y_abs:.1f})")

    def apply(self, target_rect_world: QRectF) -> QRectF:
        """
        Applies the camera offset to a target QRectF that is in world coordinates.
        Returns a new QRectF representing the target's position on the screen.
        self.camera_rect.topLeft() is the camera's offset.
        """
        if not isinstance(target_rect_world, QRectF):
            raise TypeError("Camera.apply() target_rect_world must be a QRectF.")
        # To get screen coordinates, add the camera's offset (which is negative or zero)
        # to the target's world coordinates.
        return target_rect_world.translated(self.camera_rect.topLeft())

    def apply_to_point(self, target_point_world: QPointF) -> QPointF:
        """Applies camera offset to a QPointF in world coordinates."""
        if not isinstance(target_point_world, QPointF):
            raise TypeError("Camera.apply_to_point() target_point_world must be a QPointF.")
        return target_point_world + self.camera_rect.topLeft()

    def update(self, target_entity: Any):
        """
        Updates the camera's position to follow the target_entity.
        The camera's position (self.camera_rect.topLeft()) represents the offset
        to apply to world coordinates to get screen coordinates.
        This means camera_rect.x() and camera_rect.y() will typically be negative or zero.

        Args:
            target_entity (Any): The entity to follow. Must have a 'rect' attribute (QRectF).
        """
        if not target_entity or \
           not hasattr(target_entity, 'rect') or \
           not isinstance(target_entity.rect, QRectF) or \
           target_entity.rect.isNull():
            # warning("Camera Update: Invalid or null target_entity or its rect. Using static update.")
            self.static_update()
            return

        target_center_x_world = target_entity.rect.center().x()
        target_center_y_world = target_entity.rect.center().y()

        # Desired camera offset: This is the value self.camera_rect.topLeft() should aim for.
        # It's calculated so the target_center_world appears at screen_center.
        # offset_x + target_center_x_world = screen_width / 2 => offset_x = screen_width / 2 - target_center_x_world
        desired_camera_offset_x = (self.screen_width / 2.0) - target_center_x_world
        desired_camera_offset_y = (self.screen_height / 2.0) - target_center_y_world

        # --- Horizontal Clamping ---
        # The camera's offset cannot be more positive than -world_start_x.
        # (i.e., world_start_x cannot appear to the right of screen_left_edge 0)
        max_allowed_camera_offset_x = -self.world_start_x

        # The camera's offset cannot be more negative than a value that would show
        # empty space beyond the right edge of the world.
        # world_end_x_abs = self.world_start_x + self.level_width
        # min_allowed_camera_offset_x + world_end_x_abs = self.screen_width
        # min_allowed_camera_offset_x = self.screen_width - world_end_x_abs
        min_allowed_camera_offset_x = self.screen_width - (self.world_start_x + self.level_width)

        final_camera_offset_x: float
        if self.level_width > self.screen_width: # Level is wider than the screen, scrolling is possible
            final_camera_offset_x = max(min_allowed_camera_offset_x, min(max_allowed_camera_offset_x, desired_camera_offset_x))
        else: # Level is narrower than or equal to the screen, center the level horizontally
            final_camera_offset_x = -self.world_start_x + (self.screen_width - self.level_width) / 2.0

        # --- Vertical Clamping ---
        max_allowed_camera_offset_y = -self.level_top_y_abs
        min_allowed_camera_offset_y = self.screen_height - self.level_bottom_y_abs
        
        final_camera_offset_y: float
        if self.effective_level_height > self.screen_height: # Level is taller than the screen
            final_camera_offset_y = max(min_allowed_camera_offset_y, min(max_allowed_camera_offset_y, desired_camera_offset_y))
        else: # Level is shorter than or equal to the screen, center the level vertically
            final_camera_offset_y = -self.level_top_y_abs + (self.screen_height - self.effective_level_height) / 2.0
            # Special case: if level is very short, don't let it scroll too far up if player is near top
            # This can be adjusted based on desired "sky" behavior.
            # final_camera_offset_y = min(max_allowed_camera_offset_y, final_camera_offset_y)


        self.camera_rect.moveTo(final_camera_offset_x, final_camera_offset_y)

        # Optional debug logging for camera movement
        # debug_limiter_key = f"camera_update_{id(target_entity)}"
        # if PrintLimiter.can_print(debug_limiter_key, limit=1, period=1.0): # Example limiter
        #     debug(f"Camera Updated: TargetWorld({target_center_x_world:.1f},{target_center_y_world:.1f}) "
        #           f"-> CamOffset({final_camera_offset_x:.1f},{final_camera_offset_y:.1f})")
        #     debug(f"  WorldBounds: X({self.world_start_x:.1f} to {self.world_start_x+self.level_width:.1f}), "
        #           f"Y({self.level_top_y_abs:.1f} to {self.level_bottom_y_abs:.1f})")
        #     debug(f"  Clamping X: Desired={desired_camera_offset_x:.1f}, MinAllow={min_allowed_camera_offset_x:.1f}, MaxAllow={max_allowed_camera_offset_x:.1f}")
        #     debug(f"  Clamping Y: Desired={desired_camera_offset_y:.1f}, MinAllow={min_allowed_camera_offset_y:.1f}, MaxAllow={max_allowed_camera_offset_y:.1f}")


    def static_update(self):
        """
        Called if no target to follow. Ensures camera stays within bounds.
        Could be used to set a default view or simply maintain the current clamped position.
        """
        # This ensures that even if the camera was moved programmatically (e.g., set_pos)
        # to an out-of-bounds position, a static update will re-clamp it.
        current_offset_x = self.camera_rect.x()
        current_offset_y = self.camera_rect.y()

        max_allowed_camera_offset_x = -self.world_start_x
        min_allowed_camera_offset_x = self.screen_width - (self.world_start_x + self.level_width)
        final_camera_offset_x: float
        if self.level_width > self.screen_width:
            final_camera_offset_x = max(min_allowed_camera_offset_x, min(max_allowed_camera_offset_x, current_offset_x))
        else:
            final_camera_offset_x = -self.world_start_x + (self.screen_width - self.level_width) / 2.0

        max_allowed_camera_offset_y = -self.level_top_y_abs
        min_allowed_camera_offset_y = self.screen_height - self.level_bottom_y_abs
        final_camera_offset_y: float
        if self.effective_level_height > self.screen_height:
            final_camera_offset_y = max(min_allowed_camera_offset_y, min(max_allowed_camera_offset_y, current_offset_y))
        else:
            final_camera_offset_y = -self.level_top_y_abs + (self.screen_height - self.effective_level_height) / 2.0

        if abs(current_offset_x - final_camera_offset_x) > 1e-3 or \
           abs(current_offset_y - final_camera_offset_y) > 1e-3:
            self.camera_rect.moveTo(final_camera_offset_x, final_camera_offset_y)
            # debug(f"Camera StaticUpdate: Clamped position to CamOffset({final_camera_offset_x:.1f},{final_camera_offset_y:.1f})")

    def get_offset(self) -> QPointF:
        """Returns the camera's current top-left offset."""
        return self.camera_rect.topLeft()

    def set_offset(self, x_offset: float, y_offset: float):
        """
        Sets the camera's top-left offset directly.
        The position will be clamped on the next update() or static_update().
        """
        self.camera_rect.moveTo(float(x_offset), float(y_offset))
        # It's often good to immediately apply clamping or trigger an update if manually setting position.
        # self.static_update() # Optionally, force a clamp immediately.

    def set_level_dimensions(self,
                             level_total_width: float,
                             level_min_x_abs: float,
                             level_min_y_abs: float,
                             level_max_y_abs: float):
        """
        Updates the boundaries of the game world for camera clamping.

        Args:
            level_total_width (float): The full horizontal span of the world (e.g., max_x - min_x). Must be > 0.
            level_min_x_abs (float): The absolute minimum X-coordinate of the world.
            level_min_y_abs (float): The absolute minimum Y-coordinate (top-most) of the world.
            level_max_y_abs (float): The absolute maximum Y-coordinate (bottom-most) of the world.
                                     Must be > level_min_y_abs.
        """
        self.world_start_x = float(level_min_x_abs)
        self.level_width = max(1.0, float(level_total_width))
        
        self.level_top_y_abs = float(level_min_y_abs)
        self.level_bottom_y_abs = float(level_max_y_abs)
        
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs
        if self.effective_level_height <= 0:
            warning(f"Camera set_level_dimensions: Effective level height is <= 0 ({self.effective_level_height}). "
                    f"BottomY: {self.level_bottom_y_abs}, TopY: {self.level_top_y_abs}. Adjusting.")
            self.effective_level_height = self.screen_height # Fallback
            self.level_bottom_y_abs = self.level_top_y_abs + self.screen_height

        info(f"Camera Level Dims Set: Width={self.level_width:.1f}, StartX={self.world_start_x:.1f}, "
             f"TopY={self.level_top_y_abs:.1f}, BottomY={self.level_bottom_y_abs:.1f}, "
             f"EffectiveHeight={self.effective_level_height:.1f}")
        
        # After changing level dimensions, the camera might be out of bounds.
        # Force an update to re-clamp it to the new boundaries.
        self.static_update() # Or self.update(current_target) if a target is known

    def set_screen_dimensions(self, screen_width: float, screen_height: float):
        """
        Updates the camera's understanding of the screen/viewport size.
        Called when the game window/widget is resized.

        Args:
            screen_width (float): The new width of the screen. Must be > 0.
            screen_height (float): The new height of the screen. Must be > 0.
        """
        new_screen_width = max(1.0, float(screen_width))
        new_screen_height = max(1.0, float(screen_height))

        if abs(self.screen_width - new_screen_width) > 1e-3 or \
           abs(self.screen_height - new_screen_height) > 1e-3:
            
            self.screen_width = new_screen_width
            self.screen_height = new_screen_height
            self.camera_rect.setSize(QSizeF(self.screen_width, self.screen_height))
            info(f"Camera Screen Dims Set: {self.screen_width:.1f}x{self.screen_height:.1f}")

            # After changing screen dimensions, the camera might need to be re-clamped
            # or re-centered based on its current target or position.
            self.static_update() # Or self.update(current_target)