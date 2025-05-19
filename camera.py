#################### START OF FILE: camera.py ####################

# -*- coding: utf-8 -*-
"""
camera.py
Defines the Camera class for managing the game's viewport, refactored for PySide6.
"""
# version 2.0.1 (PySide6 Refactor - Added QSizeF import)

from PySide6.QtCore import QRectF, QPointF, QSizeF # Added QSizeF

from typing import Any # For type hint of target_entity

class Camera:
    def __init__(self, level_width: float, level_top_y_abs: float, level_bottom_y_abs: float,
                 screen_width: float, screen_height: float):
        """
        Initializes the camera. Coordinates are expected to be floats.
        """
        self.camera_rect = QRectF(0.0, 0.0, float(screen_width), float(screen_height))
        self.level_width = float(level_width)
        self.level_top_y_abs = float(level_top_y_abs)
        self.level_bottom_y_abs = float(level_bottom_y_abs)
        self.screen_width = float(screen_width)
        self.screen_height = float(screen_height)
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs

    def apply(self, target_rect: QRectF) -> QRectF:
        """
        Applies the camera offset to a target QRectF.
        """
        if not isinstance(target_rect, QRectF):
            raise TypeError("Camera.apply() target_rect must be a QRectF.")
        return target_rect.translated(self.camera_rect.topLeft())

    def apply_to_point(self, target_point: QPointF) -> QPointF:
        """Applies camera offset to a QPointF."""
        if not isinstance(target_point, QPointF):
            raise TypeError("Camera.apply_to_point() target_point must be a QPointF.")
        return target_point + self.camera_rect.topLeft()

    def update(self, target_entity: Any): 
        """
        Updates the camera's position to follow the target_entity.
        """
        if not target_entity or not hasattr(target_entity, 'rect') or not isinstance(target_entity.rect, QRectF):
            self.static_update()
            return

        target_center_x = target_entity.rect.center().x()
        target_center_y = target_entity.rect.center().y()

        new_camera_x = self.screen_width / 2.0 - target_center_x
        new_camera_y = self.screen_height / 2.0 - target_center_y

        new_camera_x = min(0.0, new_camera_x)
        if self.level_width > self.screen_width:
            new_camera_x = max(-(self.level_width - self.screen_width), new_camera_x)
        else: 
            new_camera_x = 0.0 

        if self.effective_level_height <= self.screen_height:
            new_camera_y = -(self.level_top_y_abs + self.effective_level_height / 2.0 - self.screen_height / 2.0)
        else:
            new_camera_y = min(-self.level_top_y_abs, new_camera_y)
            new_camera_y = max(-(self.level_bottom_y_abs - self.screen_height), new_camera_y)

        self.camera_rect.moveTo(new_camera_x, new_camera_y)

    def static_update(self):
        pass

    def get_pos(self) -> QPointF:
        return self.camera_rect.topLeft()

    def set_pos(self, x: float, y: float):
        self.camera_rect.moveTo(float(x), float(y))

    def set_level_dimensions(self, level_width: float, level_top_y_abs: float, level_bottom_y_abs: float):
        self.level_width = float(level_width)
        self.level_top_y_abs = float(level_top_y_abs)
        self.level_bottom_y_abs = float(level_bottom_y_abs)
        self.effective_level_height = self.level_bottom_y_abs - self.level_top_y_abs

    def set_screen_dimensions(self, screen_width: float, screen_height: float):
        self.screen_width = float(screen_width)
        self.screen_height = float(screen_height)
        self.camera_rect.setSize(QSizeF(self.screen_width, self.screen_height)) # QSizeF used here

#################### END OF FILE: camera.py ####################