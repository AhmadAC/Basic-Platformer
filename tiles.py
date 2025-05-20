# tiles.py
# -*- coding: utf-8 -*-
"""
Defines classes for static and interactive tiles in the game world.
Refactored for PySide6.
"""
# version 2.1.0 (Platform color and properties)

from typing import Optional, Any, Tuple, Dict # Added Tuple, Dict

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
                 color_tuple: Tuple[int, int, int] = C.GRAY,  # Renamed from color to color_tuple for consistency
                 platform_type: str = "generic_platform",    # More descriptive default
                 properties: Optional[Dict[str, Any]] = None): # Added properties

        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        # Store the color tuple
        self.color_tuple = color_tuple 
        self.q_color = QColor(*self.color_tuple) # Store QColor for drawing

        self.image = QPixmap(int(self.width), int(self.height))
        self.image.fill(self.q_color) # Use the instance's color

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self.platform_type = platform_type
        self.properties = properties if properties is not None else {}
        
        # Default properties based on type (can be overridden by passed properties)
        self.is_collidable = True 
        if "boundary" in self.platform_type:
            self.properties.setdefault("is_boundary", True)
        
        # For potential QGraphicsScene integration
        self._graphics_item_ref: Optional[Any] = None 

        if width <= 0 or height <= 0:
            print(f"Warning: Platform created with non-positive dimensions: w={width}, h={height} at ({x},{y}). Type: {platform_type}. Using 1x1.")

    def get_qpixmap(self) -> QPixmap:
        """Returns the QPixmap representation."""
        # Could regenerate if color/properties change dynamically, but for now it's static
        return self.image

    def draw(self, painter: QPainter): # Example draw method
        """Draws the platform using its QPixmap."""
        painter.drawPixmap(self.rect.topLeft(), self.image)
        # Alternatively, if you don't want to pre-render to QPixmap or need dynamic colors:
        # painter.fillRect(self.rect, self.q_color)


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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Keep pixel art crisp

        # Use a more ladder-like color, e.g., brown
        rung_qcolor = QColor(139, 69, 19, 220) # SaddleBrown, slightly transparent
        pen = QPen(rung_qcolor)

        num_rungs = int(self.height / (C.TILE_SIZE * 0.35)) # Adjust rung spacing based on tile size
        if num_rungs > 0:
            rung_spacing = self.height / (num_rungs +1) # +1 for better spacing at ends
            pen.setWidth(max(1, int(C.TILE_SIZE * 0.05))) # Rung thickness relative to tile size
            painter.setPen(pen)
            for i in range(1, num_rungs + 1):
                rung_y_pos = i * rung_spacing
                if rung_y_pos < self.height - 1: # Ensure rung is within bounds
                    painter.drawLine(QPointF(0, rung_y_pos), QPointF(self.width, rung_y_pos))

        rail_thickness = max(2, int(C.TILE_SIZE * 0.075)) # Rail thickness relative to tile size
        pen.setWidth(rail_thickness)
        painter.setPen(pen)

        # Ensure rails are drawn correctly even for narrow ladders
        left_rail_x = float(rail_thickness / 2.0)
        right_rail_x = self.width - float(rail_thickness / 2.0)

        if self.width >= rail_thickness: # Draw left rail
            painter.drawLine(QPointF(left_rail_x, 0), QPointF(left_rail_x, self.height))
        
        if self.width >= rail_thickness * 2: # Draw right rail only if enough space
             painter.drawLine(QPointF(right_rail_x, 0), QPointF(right_rail_x, self.height))
        elif self.width > rail_thickness: # If only enough for one rail centered
            center_rail_x = self.width / 2.0
            painter.drawLine(QPointF(center_rail_x, 0), QPointF(center_rail_x, self.height))


        painter.end()

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None
    
    def get_qpixmap(self) -> QPixmap:
        """Returns the QPixmap representation."""
        return self.image

    def draw(self, painter: QPainter):
        """Draws the ladder using its QPixmap."""
        painter.drawPixmap(self.rect.topLeft(), self.image)


class Lava:
    """
    Dangerous lava tile that damages characters.
    Image is a simple colored rectangle using QPixmap.
    """
    def __init__(self, x: float, y: float, width: float, height: float, 
                 color_tuple: Tuple[int, int, int] = C.ORANGE_RED): # Added type hint
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        self.color_tuple = color_tuple
        self.q_color = QColor(*self.color_tuple)

        self.image = QPixmap(int(self.width), int(self.height))
        self.image.fill(self.q_color)

        self.rect = QRectF(float(x), float(y), self.width, self.height)
        self._graphics_item_ref: Optional[Any] = None

        if width <= 0 or height <= 0:
            print(f"Warning: Lava created with non-positive dimensions: w={width}, h={height} at ({x},{y}). Using 1x1.")

    def get_qpixmap(self) -> QPixmap:
        """Returns the QPixmap representation."""
        return self.image

    def draw(self, painter: QPainter):
        """Draws the lava using its QPixmap."""
        painter.drawPixmap(self.rect.topLeft(), self.image)