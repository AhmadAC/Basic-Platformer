# game_ui.py
# -*- coding: utf-8 -*-
"""
Manages UI elements for the PySide6 version of the game.
This includes menus, dialogs, HUD, and game scene rendering.
"""
# version 2.0.3 (Implemented Option A for static tile rendering)

import sys
import os
import time

from typing import Dict, Optional, Any, List, Tuple
# PySide6 imports
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QDialog, QListWidget, QListWidgetItem, QLineEdit, QProgressBar,
    QDialogButtonBox, QMessageBox
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPixmap, QPalette,
    QFontMetrics
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, Signal, QTimer

# Game imports
import constants as C
import config as game_config # Though not directly used in this version of game_ui.py, good for context
import joystick_handler # Same as above
from tiles import Platform, Ladder, Lava # Import static tile types

_start_time_game_ui = time.monotonic()
def get_current_ticks():
    """
    Returns the number of milliseconds since this module was initialized.
    """
    return int((time.monotonic() - _start_time_game_ui) * 1000)

PYPERCLIP_AVAILABLE_UI_MODULE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE_UI_MODULE = True
except ImportError:
    pass


def get_clipboard_text_qt() -> Optional[str]: # Added for completeness, though not used in this file
    clipboard = QApplication.clipboard()
    return clipboard.text() if clipboard else None

def set_clipboard_text_qt(text: str): # Added for completeness, though not used in this file
    clipboard = QApplication.clipboard()
    if clipboard: clipboard.setText(text)


def draw_health_bar_qt(painter: QPainter, x: float, y: float,
                       width: float, height: float,
                       current_hp: float, max_hp: float):
    if max_hp <= 0: return
    current_hp_clamped = max(0.0, min(current_hp, max_hp))
    bar_width = max(1.0, float(width))
    bar_height = max(1.0, float(height))
    health_ratio = current_hp_clamped / max_hp

    color_red_rgb = getattr(C, 'RED', (255,0,0))
    color_green_rgb = getattr(C, 'GREEN', (0,255,0))
    color_dark_gray_rgb = getattr(C, 'DARK_GRAY', (50,50,50))
    color_black_rgb = getattr(C, 'BLACK', (0,0,0))

    qcolor_red = QColor(*color_red_rgb)
    qcolor_green = QColor(*color_green_rgb)
    qcolor_dark_gray = QColor(*color_dark_gray_rgb)
    qcolor_black = QColor(*color_black_rgb)

    r = int(qcolor_red.redF() * (1 - health_ratio) * 255 + qcolor_green.redF() * health_ratio * 255)
    g = int(qcolor_red.greenF() * (1 - health_ratio) * 255 + qcolor_green.greenF() * health_ratio * 255)
    b = int(qcolor_red.blueF() * (1 - health_ratio) * 255 + qcolor_green.blueF() * health_ratio * 255)
    health_qcolor = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    background_rect = QRectF(x, y, bar_width, bar_height)
    painter.fillRect(background_rect, qcolor_dark_gray)

    health_fill_width = bar_width * health_ratio
    if health_fill_width > 0:
        painter.fillRect(QRectF(x, y, health_fill_width, bar_height), health_qcolor)

    pen = QPen(qcolor_black)
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawRect(background_rect)

def draw_player_hud_qt(painter: QPainter, x: float, y: float, player_instance: Any,
                       player_number: int, hud_qfont: QFont):
    if not player_instance or not hasattr(player_instance, 'current_health') or \
       not hasattr(player_instance, 'max_health'): return

    player_label_text = f"P{player_number}"
    qcolor_white = QColor(*getattr(C, 'WHITE', (255,255,255)))

    painter.setFont(hud_qfont)
    painter.setPen(qcolor_white)

    font_metrics = QFontMetrics(hud_qfont)
    label_text_height = float(font_metrics.height())
    painter.drawText(QPointF(x, y + label_text_height - font_metrics.descent()), player_label_text)
    label_height_offset = label_text_height

    health_bar_pos_x = x
    health_bar_pos_y = y + label_height_offset + 5.0
    hud_health_bar_width = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', getattr(C, 'HEALTH_BAR_WIDTH', 50) * 2))
    hud_health_bar_height = float(getattr(C, 'HUD_HEALTH_BAR_HEIGHT', getattr(C, 'HEALTH_BAR_HEIGHT', 8) + 4))

    draw_health_bar_qt(painter, health_bar_pos_x, health_bar_pos_y,
                       hud_health_bar_width, hud_health_bar_height,
                       player_instance.current_health, player_instance.max_health)

    health_value_text = f"{int(player_instance.current_health)}/{int(player_instance.max_health)}"
    text_bounding_rect = font_metrics.boundingRect(health_value_text)

    health_text_pos_x = health_bar_pos_x + hud_health_bar_width + 10.0
    health_text_pos_y = health_bar_pos_y + (hud_health_bar_height - text_bounding_rect.height()) / 2.0 + font_metrics.ascent()
    painter.drawText(QPointF(health_text_pos_x, health_text_pos_y), health_value_text)


class GameSceneWidget(QWidget):
    def __init__(self, game_elements_ref: Dict[str, Any], fonts_ref: Dict[str, QFont], parent=None):
        super().__init__(parent)
        self.game_elements = game_elements_ref
        self.fonts = fonts_ref
        self.current_game_time_ticks = 0
        self.download_status_message: Optional[str] = None
        self.download_progress_percent: Optional[float] = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAutoFillBackground(False)
        # For debugging rendering issues
        # self._printed_renderables_once = False 

    def update_game_state(self, game_time_ticks: int, download_msg: Optional[str] = None, download_prog: Optional[float] = None):
        self.current_game_time_ticks = game_time_ticks
        self.download_status_message = download_msg
        self.download_progress_percent = download_prog
        self.update()

    def paintEvent(self, event: Any): # event type is QPaintEvent
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        camera_instance = self.game_elements.get("camera")
        all_renderables: List[Any] = self.game_elements.get("all_renderable_objects", [])
        bg_color_tuple = self.game_elements.get("level_background_color", C.LIGHT_BLUE)
        painter.fillRect(self.rect(), QColor(*bg_color_tuple))

        # --- DEBUG PRINT FOR RENDERABLES (Optional, enable if needed) ---
        # if not self._printed_renderables_once and all_renderables:
        #     print(f"DEBUG GameSceneWidget.paintEvent: Total renderables: {len(all_renderables)}")
        #     for i, ent in enumerate(all_renderables):
        #         if isinstance(ent, Platform):
        #             print(f"  Renderable {i}: Platform - Rect: {ent.rect}, Type: {ent.platform_type}, ImageNull: {ent.image.isNull()}, Color: {ent.color_tuple}")
        #         # else:
        #         #     print(f"  Renderable {i}: {type(ent).__name__}, Rect: {getattr(ent, 'rect', 'N/A')}")
        #     self._printed_renderables_once = True
        # --- END DEBUG PRINT ---

        if camera_instance:
            for entity in all_renderables:
                is_static_tile = isinstance(entity, (Platform, Ladder, Lava))
                can_render_entity = False
                if is_static_tile:
                    can_render_entity = hasattr(entity, 'image') and entity.image and not entity.image.isNull() and \
                                        hasattr(entity, 'rect') and entity.rect and entity.rect.isValid()
                else:
                    can_render_entity = hasattr(entity, 'image') and entity.image and not entity.image.isNull() and \
                                        hasattr(entity, 'rect') and entity.rect and entity.rect.isValid() and \
                                        hasattr(entity, 'alive') and entity.alive()

                if can_render_entity:
                    screen_rect_qrectf = camera_instance.apply(entity.rect)
                    screen_rect_qrect = screen_rect_qrectf.toRect()

                    # --- DEBUG PRINT FOR SPECIFIC TILES (Optional) ---
                    # if isinstance(entity, Platform) and "wall_gray" in entity.platform_type:
                    #     if entity.rect.x() == 0 and entity.rect.y() < 800: # Log first few top-left walls
                    #         print(f"DEBUG Wall Tile: WorldRect={entity.rect}, ScreenRect={screen_rect_qrectf}, WidgetRect={self.rect()}, Intersects={self.rect().intersects(screen_rect_qrect)}")
                    # --- END DEBUG PRINT ---
                    
                    if self.rect().intersects(screen_rect_qrect):
                        painter.drawPixmap(screen_rect_qrectf.topLeft(), entity.image)
            # ... (rest of enemy health bar, player HUD rendering) ...
            enemy_list_for_hb: List[Any] = self.game_elements.get("enemy_list", [])
            for enemy in enemy_list_for_hb:
                if hasattr(enemy, 'alive') and enemy.alive() and \
                   getattr(enemy, '_valid_init', False) and not \
                   (getattr(enemy, 'is_dead', False) and getattr(enemy, 'death_animation_finished', False)) and \
                   hasattr(enemy, 'current_health') and hasattr(enemy, 'max_health') and \
                   not getattr(enemy, 'is_petrified', False):
                    enemy_screen_rect = camera_instance.apply(enemy.rect)
                    hb_w = float(getattr(C, 'HEALTH_BAR_WIDTH', 50))
                    hb_h = float(getattr(C, 'HEALTH_BAR_HEIGHT', 8))
                    hb_x = enemy_screen_rect.center().x() - hb_w / 2.0
                    hb_y = enemy_screen_rect.top() - hb_h - float(getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5))
                    draw_health_bar_qt(painter, hb_x, hb_y, hb_w, hb_h, enemy.current_health, enemy.max_health)
        else:
            for entity in all_renderables:
                is_static_tile_no_cam = isinstance(entity, (Platform, Ladder, Lava))
                can_render_no_cam = False
                if is_static_tile_no_cam:
                    can_render_no_cam = hasattr(entity, 'image') and entity.image and not entity.image.isNull() and \
                                        hasattr(entity, 'rect') and entity.rect and entity.rect.isValid()
                else:
                    can_render_no_cam = hasattr(entity, 'image') and entity.image and not entity.image.isNull() and \
                                        hasattr(entity, 'rect') and entity.rect and entity.rect.isValid() and \
                                        hasattr(entity, 'alive') and entity.alive()
                if can_render_no_cam:
                     painter.drawPixmap(entity.rect.topLeft(), entity.image)


        player1 = self.game_elements.get("player1")
        player2 = self.game_elements.get("player2")
        hud_font = self.fonts.get("medium_qfont", QFont("Arial", 12))

        if player1 and hasattr(player1, '_valid_init') and player1._valid_init and \
           hasattr(player1, 'alive') and player1.alive() and not getattr(player1, 'is_petrified', False):
            draw_player_hud_qt(painter, 10.0, 10.0, player1, 1, hud_font)

        if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
           hasattr(player2, 'alive') and player2.alive() and not getattr(player2, 'is_petrified', False):
            p2_hud_w_est = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', 100) + 120)
            draw_player_hud_qt(painter, self.width() - p2_hud_w_est - 10.0, 10.0, player2, 2, hud_font)

        if self.download_status_message:
            dialog_w = self.width() * 0.6; dialog_h = self.height() * 0.3
            dialog_rect = QRectF(0, 0, dialog_w, dialog_h)
            dialog_rect.moveCenter(QPointF(self.width() / 2.0, self.height() / 2.0))
            painter.fillRect(dialog_rect, QColor(50,50,50, 200))
            painter.setPen(QColor(*C.WHITE)); painter.drawRect(dialog_rect)

            title_font = self.fonts.get("large_qfont", QFont("Arial", 24, QFont.Weight.Bold))
            msg_font = self.fonts.get("medium_qfont", QFont("Arial", 12))

            painter.setFont(title_font)
            painter.drawText(dialog_rect.adjusted(10,10,-10,-10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "File Transfer")

            painter.setFont(msg_font)
            painter.drawText(dialog_rect.adjusted(10, QFontMetrics(title_font).height() + 20, -10, -10),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.download_status_message)

            if self.download_progress_percent is not None and self.download_progress_percent >= 0:
                bar_margin = 20.0; bar_h = 30.0
                msg_text_rect = QFontMetrics(msg_font).boundingRect(dialog_rect.adjusted(10, QFontMetrics(title_font).height() + 20, -10, -10),
                                                                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.download_status_message)
                bar_y_pos = dialog_rect.top() + QFontMetrics(title_font).height() + 20 + msg_text_rect.height() + 15
                bar_rect = QRectF(dialog_rect.left() + bar_margin, bar_y_pos,
                                  dialog_rect.width() - 2 * bar_margin, bar_h)
                if bar_rect.bottom() > dialog_rect.bottom() - bar_margin:
                    bar_rect.setHeight(max(5.0, dialog_rect.bottom() - bar_margin - bar_y_pos))

                painter.fillRect(bar_rect, QColor(*C.GRAY))
                fill_width = bar_rect.width() * (self.download_progress_percent / 100.0)
                painter.fillRect(QRectF(bar_rect.topLeft(), QSizeF(fill_width, bar_rect.height())), QColor(*C.GREEN))
                painter.setPen(QColor(*C.WHITE)); painter.drawRect(bar_rect)

                prog_text = f"{self.download_progress_percent:.1f}%"
                painter.setPen(QColor(*C.BLACK))
                painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, prog_text)
        painter.end()


class SelectMapDialog(QDialog):
    def __init__(self, fonts: Dict[str, QFont], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Select Map")
        self.selected_map_name: Optional[str] = None
        self.fonts = fonts

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.populate_maps()
        layout.addWidget(self.list_widget)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.list_widget.itemDoubleClicked.connect(self.accept)

    def populate_maps(self):
        self.list_widget.clear()
        maps_dir = getattr(C, "MAPS_DIR", "maps")
        if not os.path.isabs(maps_dir):
            project_root_from_game_ui = os.path.dirname(os.path.abspath(__file__))
            maps_dir = os.path.join(project_root_from_game_ui, maps_dir)

        if os.path.exists(maps_dir) and os.path.isdir(maps_dir):
            try:
                map_files = [f[:-3] for f in os.listdir(maps_dir) if f.endswith(".py") and f != "__init__.py" and f[:-3] != "level_default"]
                map_files.sort()
                if map_files:
                    self.list_widget.addItems(map_files)
                    if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)
                else:
                    self.list_widget.addItem("No selectable maps found.")
                    self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            except OSError as e:
                self.list_widget.addItem(f"Error reading maps: {e}")
                self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self.list_widget.addItem(f"Maps directory not found: {maps_dir}")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def accept(self):
        current_item = self.list_widget.currentItem()
        if current_item and current_item.text() and not current_item.text().startswith("No") and not current_item.text().startswith("Error"):
            self.selected_map_name = current_item.text()
            super().accept()
        elif current_item:
            QMessageBox.information(self, "No Map", "No valid map selected.")
        else:
             QMessageBox.warning(self, "Selection Error", "Please select a map or cancel.")


class IPInputDialog(QDialog):
    def __init__(self, default_ip_port: str = "127.0.0.1:5555", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Enter Server IP & Port")
        self.ip_port_string: Optional[str] = None

        layout = QVBoxLayout(self)
        self.label = QLabel(f"Format: IP_ADDRESS:PORT (e.g., 192.168.1.100:5555)\nCtrl+V to paste may work.")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.line_edit = QLineEdit(self)
        self.line_edit.setText(default_ip_port)
        layout.addWidget(self.line_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.line_edit.returnPressed.connect(self.accept)

    def accept(self):
        text = self.line_edit.text().strip()
        if text:
            self.ip_port_string = text
            super().accept()
        else:
            QMessageBox.warning(self, "Input Error", "IP and Port cannot be empty.")