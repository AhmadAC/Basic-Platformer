#################### START OF FILE: items.py ####################

# items.py
# -*- coding: utf-8 -*-
"""
Defines collectible items like Chests.
Uses resource_path helper. Refactored for PySide6.
"""
# version 2.0.2
import os
import sys
import random
from typing import List, Optional, Any
import time # For get_current_ticks fallback

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QSize, Qt, QPointF

# Game imports (already PySide6 compatible or will be)
import constants as C
from assets import load_gif_frames, resource_path # load_gif_frames now returns List[QPixmap]

# Logger import
try:
    from logger import debug, info, warning
except ImportError:
    def debug(msg): print(f"DEBUG_ITEMS: {msg}")
    def info(msg): print(f"INFO_ITEMS: {msg}")
    def warning(msg): print(f"WARNING_ITEMS: {msg}")

_start_time_items = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.

    """
    return int((time.monotonic() - _start_time_items) * 1000)


class Chest:
    """
    A chest that opens, stays open for a bit, fades, and then restores player health.
    Uses QPixmap for visuals.
    """
    def __init__(self, x: float, y: float): # x, y are for midbottom
        self._valid_init = True
        self.frames_closed: List[QPixmap] = []
        self.frames_open: List[QPixmap] = []

        full_chest_closed_path = resource_path(C.CHEST_CLOSED_SPRITE_PATH)
        self.frames_closed = load_gif_frames(full_chest_closed_path)
        if not self.frames_closed or self._is_placeholder_qpixmap(self.frames_closed[0]):
            warning(f"Chest: Failed to load closed frames from '{full_chest_closed_path}'. Using placeholder.")
            self._valid_init = False
            self.frames_closed = [self._create_placeholder_qpixmap(QColor(*C.YELLOW), "ClosedErr")]

        full_chest_open_path = resource_path(C.CHEST_OPEN_SPRITE_PATH)
        self.frames_open = load_gif_frames(full_chest_open_path)
        if not self.frames_open or self._is_placeholder_qpixmap(self.frames_open[0]):
            warning(f"Chest: Failed to load open frames from '{full_chest_open_path}'. Using placeholder.")
            self.frames_open = [self._create_placeholder_qpixmap(QColor(*C.BLUE), "OpenErr")]

        self.state = 'closed'
        self.is_collected_flag_internal = False
        self.player_to_heal: Optional[Any] = None

        self.frames_current_set = self.frames_closed
        self.image: QPixmap = self.frames_current_set[0]

        img_width = self.image.width()
        img_height = self.image.height()
        rect_x = float(x - img_width / 2.0)
        rect_y = float(y - img_height)
        self.rect = QRectF(rect_x, rect_y, float(img_width), float(img_height))

        self.pos_midbottom = QPointF(float(x), float(y))

        self.current_frame_index = 0
        self.animation_timer = get_current_ticks()
        self.time_opened_start = 0
        self.fade_alpha = 255
        self._alive = True

        if not self._valid_init:
             self.image = self.frames_closed[0]
             self._update_rect_from_image_and_pos()

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.size() == QSize(30,40): # Placeholder size defined in load_gif_frames
            qimage = pixmap.toImage()
            if not qimage.isNull():
                # Check a few pixels to be more robust against minor color variations
                # if using a specific placeholder pattern.
                # For now, checking a known color and text used in _create_placeholder_qpixmap
                # might be fragile if placeholder generation changes.
                # Simpler: Assume any 30x40 is a placeholder if it's not the expected sprite.
                # This logic is heuristic and depends on how placeholders are generated.
                # If placeholders are always red or blue (as per _create_placeholder_qpixmap),
                # this check is okay.
                color_at_origin = qimage.pixelColor(0,0)
                if color_at_origin == QColor(*C.YELLOW) or color_at_origin == QColor(*C.BLUE) or color_at_origin == QColor(*C.RED): # Added RED from load_gif_frames
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        pixmap = QPixmap(30, 30) # Consistent placeholder size
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*C.BLACK))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e:
            print(f"ITEMS PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        if self.image and not self.image.isNull():
            img_width = float(self.image.width())
            img_height = float(self.image.height())
            rect_x = self.pos_midbottom.x() - img_width / 2.0
            rect_y = self.pos_midbottom.y() - img_height
            self.rect.setRect(rect_x, rect_y, img_width, img_height)
        else: # Fallback if image is null
            self.rect.setRect(self.pos_midbottom.x() - 15, self.pos_midbottom.y() - 30, 30, 30) # Default size

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def update(self, dt_sec: float):
        if self.state == 'killed' or not self._alive:
            return

        now = get_current_ticks()
        anim_speed_ms = C.ANIM_FRAME_DURATION
        if self.state == 'opening':
            anim_speed_ms = int(anim_speed_ms * 0.7)

        if now - self.animation_timer > anim_speed_ms:
            self.animation_timer = now
            self.current_frame_index += 1

            if self.current_frame_index >= len(self.frames_current_set):
                if self.state == 'opening':
                    self.current_frame_index = len(self.frames_current_set) - 1
                    self.state = 'opened'
                    self.time_opened_start = now
                    debug("Chest state changed to: opened")
                elif self.state == 'closed':
                    self.current_frame_index = 0

            if self.state != 'fading':
                if self.frames_current_set and 0 <= self.current_frame_index < len(self.frames_current_set):
                    self.image = self.frames_current_set[self.current_frame_index]
                    self._update_rect_from_image_and_pos()

        if self.state == 'opened':
            if now - self.time_opened_start >= C.CHEST_STAY_OPEN_DURATION_MS:
                self.state = 'fading'
                self.fade_alpha = 255
                self.animation_timer = now
                debug("Chest state changed to: fading")

        elif self.state == 'fading':
            elapsed_fade_time = now - self.animation_timer
            fade_progress = min(1.0, elapsed_fade_time / C.CHEST_FADE_OUT_DURATION_MS)
            self.fade_alpha = int(255 * (1.0 - fade_progress))

            if self.frames_open and self.frames_open[-1]:
                base_image_pixmap = self.frames_open[-1] # This is a QPixmap

                # Create a QImage for alpha manipulation
                qimage_alpha = base_image_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                if qimage_alpha.isNull(): # Check if conversion failed
                    warning("Chest: Failed to convert base_image_pixmap to QImage for fading.")
                    return

                # Iterate and set alpha per pixel
                for y_px in range(qimage_alpha.height()):
                    for x_px in range(qimage_alpha.width()):
                        current_pixel_color = qimage_alpha.pixelColor(x_px, y_px)
                        current_pixel_color.setAlpha(max(0, self.fade_alpha))
                        qimage_alpha.setPixelColor(x_px, y_px, current_pixel_color)

                self.image = QPixmap.fromImage(qimage_alpha)

            if self.fade_alpha <= 0:
                debug("Chest fully faded out.")
                if self.player_to_heal and hasattr(self.player_to_heal, 'heal_to_full'):
                    info(f"Player {getattr(self.player_to_heal, 'player_id', 'Unknown')} healed by chest after fade.")
                    self.player_to_heal.heal_to_full()
                self.state = 'killed'
                self.kill()

    def collect(self, player: Any):
        if self.is_collected_flag_internal or not self._valid_init or self.state != 'closed' or not self._alive:
            return

        info(f"Player {getattr(player, 'player_id', 'Unknown')} interacted with chest. State changing to 'opening'.")
        self.is_collected_flag_internal = True
        self.player_to_heal = player

        self.state = 'opening'
        self.frames_current_set = self.frames_open
        self.current_frame_index = 0
        self.animation_timer = get_current_ticks()

        if self.frames_current_set and self.frames_current_set[0]:
            self.image = self.frames_current_set[0]
            self._update_rect_from_image_and_pos()
        else:
            warning("Chest: Collect called, but 'open' frames are invalid. Chest might not animate correctly.")

#################### END OF FILE: items.py ####################