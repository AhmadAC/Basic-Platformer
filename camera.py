# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport, refactored for PySide6.
"""
# version 2.0.2 (Incorporated world_start_x for proper clamping)

from PySide6.QtCore import QRectF, QPointF, QSizeF

from typing import Any # For type hint of target_entity
# from logger import debug # Optional: if you need specific camera debug logs

class Camera:
    def __init__(self, initial_level_width: float, initial_world_start_x: float, initial_world_start_y: float, 
                 initial_level_bottom_y_abs: float, screen_width: float, screen_height: float):
        """
        Initializes the camera. Coordinates are expected to be floats.
        world_start_x, world_start_y are the absolute top-left coordinates of the game world.
        level_width is the total span of the game world (max_x - min_x).
        level_bottom_y_abs is the absolute bottom Y coordinate of the game world.
        """
        self.screen_width = float(screen_width)
        self.screen_height = float(screen_height)
        self.camera_rect = QRectF(0.0, 0.0, self.screen_width, self.screen_height)
        
        # World boundaries
        self.world_start_x = float(initial_world_start_x)
        self.level_top_y_abs = float(initial_world_start_y) # This is effectively world_start_y
        self.level_width = float(initial_level_width) # This is the total span (max_x - min_x)
        self.level_bottom_y_abs = float(initial_level_bottom_y_abs)
        
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs

    def apply(self, target_rect: QRectF) -> QRectF:
        """
        Applies the camera offset to a target QRectF.
        target_rect is in world coordinates. camera_rect.topLeft() is the camera's offset.
        """
        if not isinstance(target_rect, QRectF):
            raise TypeError("Camera.apply() target_rect must be a QRectF.")
        # To get screen coordinates, subtract camera's world position from target's world position
        # camera_rect.x() and camera_rect.y() are negative or zero.
        # So, adding them effectively subtracts the camera's magnitude of offset.
        return target_rect.translated(self.camera_rect.topLeft())


    def apply_to_point(self, target_point: QPointF) -> QPointF:
        """Applies camera offset to a QPointF."""
        if not isinstance(target_point, QPointF):
            raise TypeError("Camera.apply_to_point() target_point must be a QPointF.")
        return target_point + self.camera_rect.topLeft()

    def update(self, target_entity: Any): 
        """
        Updates the camera's position to follow the target_entity.
        The camera's position (self.camera_rect.topLeft()) represents the
        top-left corner of the *world* that should be drawn at the screen's (0,0).
        This means camera_rect.x() and camera_rect.y() will typically be negative or zero.
        """
        if not target_entity or not hasattr(target_entity, 'rect') or not isinstance(target_entity.rect, QRectF):
            self.static_update() # No valid target, perhaps maintain current position or default
            return

        target_center_x_world = target_entity.rect.center().x()
        target_center_y_world = target_entity.rect.center().y()

        # Calculate desired camera top-left X and Y in world coordinates
        # such that the target_entity is centered on the screen.
        # camera_world_x = target_center_x_world - self.screen_width / 2.0
        # camera_world_y = target_center_y_world - self.screen_height / 2.0
        # The self.camera_rect.x/y is the negative of this, or the offset to apply.
        
        desired_camera_offset_x = self.screen_width / 2.0 - target_center_x_world
        desired_camera_offset_y = self.screen_height / 2.0 - target_center_y_world

        # Horizontal Clamping
        # Max camera_offset_x (least negative): when world_start_x is at screen left (0)
        #   camera_offset_x = 0 - world_start_x
        max_cam_offset_x = -self.world_start_x
        
        # Min camera_offset_x (most negative): when world_end_x is at screen right
        #   world_end_x_abs = self.world_start_x + self.level_width
        #   camera_offset_x + world_end_x_abs = self.screen_width
        #   camera_offset_x = self.screen_width - world_end_x_abs
        min_cam_offset_x = self.screen_width - (self.world_start_x + self.level_width)

        if self.level_width > self.screen_width:
            final_camera_offset_x = max(min_cam_offset_x, min(max_cam_offset_x, desired_camera_offset_x))
        else: # Level is narrower than screen, center it
            final_camera_offset_x = -self.world_start_x + (self.screen_width - self.level_width) / 2.0

        # Vertical Clamping
        # Max camera_offset_y: when level_top_y_abs (world_start_y) is at screen top (0)
        #   camera_offset_y = 0 - level_top_y_abs
        max_cam_offset_y = -self.level_top_y_abs
        
        # Min camera_offset_y: when level_bottom_y_abs is at screen bottom
        #   camera_offset_y + level_bottom_y_abs = self.screen_height
        #   camera_offset_y = self.screen_height - level_bottom_y_abs
        min_cam_offset_y = self.screen_height - self.level_bottom_y_abs
        
        if self.effective_level_height > self.screen_height: # Level content is taller than screen
            final_camera_offset_y = max(min_cam_offset_y, min(max_cam_offset_y, desired_camera_offset_y))
        else: # Level content is shorter than screen, center it
            final_camera_offset_y = -self.level_top_y_abs + (self.screen_height - self.effective_level_height) / 2.0

        self.camera_rect.moveTo(final_camera_offset_x, final_camera_offset_y)
        # debug(f"Camera Updated: TargetWorld({target_center_x_world:.1f},{target_center_y_world:.1f}) -> CamOffset({final_camera_offset_x:.1f},{final_camera_offset_y:.1f})")
        # debug(f"  WorldBounds: X({self.world_start_x:.1f} to {self.world_start_x+self.level_width:.1f}), Y({self.level_top_y_abs:.1f} to {self.level_bottom_y_abs:.1f})")

    def static_update(self):
        """Called if no target. Camera could be set to a default view or remain."""
        # For now, do nothing, maintain current position.
        # Could be changed to center on map origin, etc.
        pass

    def get_pos(self) -> QPointF:
        """Returns the camera's current top-left offset (world coordinates at screen 0,0)."""
        return self.camera_rect.topLeft()

    def set_pos(self, x_offset: float, y_offset: float):
        """Sets the camera's top-left offset directly."""
        self.camera_rect.moveTo(float(x_offset), float(y_offset))

    def set_level_dimensions(self, level_total_width: float, level_min_x_abs: float, 
                             level_min_y_abs: float, level_max_y_abs: float):
        """
        Sets the boundaries of the game world for camera clamping.
        level_total_width: The full span of the world (max_x - min_x).
        level_min_x_abs: The absolute minimum X coordinate of the world.
        level_min_y_abs: The absolute minimum Y coordinate (top-most) of the world.
        level_max_y_abs: The absolute maximum Y coordinate (bottom-most) of the world.
        """
        self.world_start_x = float(level_min_x_abs)
        self.level_width = float(level_total_width) 
        
        self.level_top_y_abs = float(level_min_y_abs) # This is effectively world_start_y
        self.level_bottom_y_abs = float(level_max_y_abs)
        
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs
        # debug(f"Camera Level Dims Set: Width={self.level_width}, StartX={self.world_start_x}, TopY={self.level_top_y_abs}, BottomY={self.level_bottom_y_abs}")


    def set_screen_dimensions(self, screen_width: float, screen_height: float):
        """Updates the camera's understanding of the screen size."""
        self.screen_width = float(screen_width)
        self.screen_height = float(screen_height)
        self.camera_rect.setSize(QSizeF(self.screen_width, self.screen_height))
        # debug(f"Camera Screen Dims Set: {self.screen_width}x{self.screen_height}")