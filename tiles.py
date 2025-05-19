#################### START OF FILE: tiles.py ####################

# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6.
"""
# version 2.0.2 (PySide6 Refactor - Added missing typing imports)

from typing import Optional, Any # Added Optional and Any

from PySide6.QtGui import QPixmap, QColor, QPainter, QPen
from PySide6.QtCore import QRectF, QPointF, Qt

# Import game constants
import constants as C

class Platform:
    """
    Standard solid platform.
    Can be tagged with a platform_type (e.g., "ground", "ledge", "wall").
    Image is a simple colored rectangle using QPixmap.
    """
    def __init__(self, x: float, y: float, width: float, height: float,
                 color_tuple: tuple = C.GRAY, platform_type: str = "generic"):

        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        self.image = QPixmap(int(self.width), int(self.height))
        self.image.fill(QColor(*color_tuple))

        self.rect = QRectF(float(x), float(y), self.width, self.height)

        self.color_tuple = color_tuple
        self.platform_type = platform_type

        # For potential QGraphicsScene integration
        self._graphics_item_ref: Optional[Any] = None # Could be QGraphicsPixmapItem

        if width <= 0 or height <= 0:
            print(f"Warning: Platform created with non-positive dimensions: w={width}, h={height} at ({x},{y}). Using 1x1.")


class Ladder:
    """
    Climbable ladder area.
    Visually represented with rungs and rails on a QPixmap.
    """
    def __init__(self, x: float, y: float, width: float, height: float):
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        self.image = QPixmap(int(self.width), int(self.height))
        self.image.fill(QColor(0, 0, 0, 0)) # Transparent background

        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rung_qcolor = QColor(40, 40, 180, 200) # Semi-transparent dark blue
        pen = QPen(rung_qcolor)

        num_rungs = int(self.height / 15)
        if num_rungs > 0:
            rung_spacing = self.height / num_rungs
            pen.setWidth(2)
            painter.setPen(pen)
            for i in range(1, num_rungs + 1):
                rung_y_pos = i * rung_spacing
                if rung_y_pos < self.height - 1:
                    painter.drawLine(QPointF(0, rung_y_pos), QPointF(self.width, rung_y_pos))

        rail_thickness = 3
        pen.setWidth(rail_thickness)
        painter.setPen(pen)

        left_rail_x = min(float(rail_thickness / 2.0), self.width - float(rail_thickness / 2.0))
        if self.width >= rail_thickness:
            painter.drawLine(QPointF(left_rail_x, 0), QPointF(left_rail_x, self.height))

        if self.width > rail_thickness * 1.5:
            right_rail_x = max(float(rail_thickness / 2.0), self.width - float(rail_thickness / 2.0))
            painter.drawLine(QPointF(right_rail_x, 0), QPointF(right_rail_x, self.height))

        painter.end()

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None


class Lava:
    """
    Dangerous lava tile that damages characters.
    Image is a simple colored rectangle using QPixmap.
    """
    def __init__(self, x: float, y: float, width: float, height: float, color_tuple: tuple = C.ORANGE_RED):
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        self.image = QPixmap(int(self.width), int(self.height))
        self.image.fill(QColor(*color_tuple))

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.color_tuple = color_tuple
        self._graphics_item_ref: Optional[Any] = None

        if width <= 0 or height <= 0:
            print(f"Warning: Lava created with non-positive dimensions: w={width}, h={height} at ({x},{y}). Using 1x1.")

    def get_qpixmap(self) -> QPixmap:
        """Returns the QPixmap representation."""
        return self.image

#################### END OF FILE: tiles.py ####################