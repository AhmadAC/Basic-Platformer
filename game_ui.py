# game_ui.py
# -*- coding: utf-8 -*-
"""
Manages UI elements for the PySide6 version of the game.
This includes GameSceneWidget rendering and dialogs.
"""
# version 2.0.8 (Added BackgroundTile drawing)

import sys
import os
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget,QLabel, QDialog, QListWidget, QListWidgetItem, QLineEdit,
    QDialogButtonBox, QMessageBox, QVBoxLayout 
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPixmap, QPalette,
    QFontMetrics, QResizeEvent, QPaintEvent 
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF 

# --- Logging Setup ---
import logging 

try:
    from logger import info as log_info, debug as log_debug, \
                       warning as log_warning, error as log_error, \
                       critical as log_critical
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers() and not logging.getLogger().hasHandlers(): 
        _gameui_fallback_console_handler = logging.StreamHandler(sys.stdout)
        _gameui_fallback_console_formatter = logging.Formatter('GAME_UI (FallbackConsole): %(levelname)s - %(message)s')
        _gameui_fallback_console_handler.setFormatter(_gameui_fallback_console_formatter)
        logger.addHandler(_gameui_fallback_console_handler)
        logger.setLevel(logging.DEBUG) 
        logger.propagate = False 
        logger.warning("Central logger might be unconfigured; game_ui.py added its own console handler.")
    # else:
        # logger.debug("game_ui.py using centrally configured logger (or its own if it was set up).")

except ImportError:
    logging.basicConfig(level=logging.DEBUG,
                        format='GAME_UI (CriticalImportFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])
    logger = logging.getLogger(__name__) 
    logger.critical("Failed to import custom logger. Using isolated fallback for game_ui.py.")
    def log_info(msg, *args, **kwargs): logger.info(msg, *args, **kwargs)
    def log_debug(msg, *args, **kwargs): logger.debug(msg, *args, **kwargs)
    def log_warning(msg, *args, **kwargs): logger.warning(msg, *args, **kwargs)
    def log_error(msg, *args, **kwargs): logger.error(msg, *args, **kwargs)
    def log_critical(msg, *args, **kwargs): logger.critical(msg, *args, **kwargs)
# --- End Logging Setup ---


import constants as C
from tiles import Platform, Ladder, Lava, BackgroundTile # Added BackgroundTile
from player import Player 
from camera import Camera 
from utils import PrintLimiter 


# --- Helper Drawing Functions ---

def draw_health_bar_qt(painter: QPainter, x: float, y: float,
                       width: float, height: float,
                       current_hp: float, max_hp: float):
    if max_hp <= 0: return
    current_hp_clamped = max(0.0, min(current_hp, max_hp))
    bar_width = max(1.0, float(width)); bar_height = max(1.0, float(height))
    health_ratio = current_hp_clamped / max_hp
    
    color_red_rgb = getattr(C, 'RED', (255,0,0))
    color_green_rgb = getattr(C, 'GREEN', (0,255,0))
    color_dark_gray_rgb = getattr(C, 'DARK_GRAY', (50,50,50))
    color_black_rgb = getattr(C, 'BLACK', (0,0,0))
    
    qcolor_red = QColor(*color_red_rgb); qcolor_green = QColor(*color_green_rgb)
    qcolor_dark_gray = QColor(*color_dark_gray_rgb); qcolor_black = QColor(*color_black_rgb)
    
    r = int(qcolor_red.redF() * (1 - health_ratio) * 255 + qcolor_green.redF() * health_ratio * 255)
    g = int(qcolor_red.greenF() * (1 - health_ratio) * 255 + qcolor_green.greenF() * health_ratio * 255)
    b = int(qcolor_red.blueF() * (1 - health_ratio) * 255 + qcolor_green.blueF() * health_ratio * 255)
    health_qcolor = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    
    background_rect = QRectF(x, y, bar_width, bar_height)
    painter.fillRect(background_rect, qcolor_dark_gray)
    health_fill_width = bar_width * health_ratio
    if health_fill_width > 0:
        painter.fillRect(QRectF(x, y, health_fill_width, bar_height), health_qcolor)
    
    pen = QPen(qcolor_black); pen.setWidth(1)
    painter.setPen(pen); painter.drawRect(background_rect)

def draw_player_hud_qt(painter: QPainter, x: float, y: float, player_instance: Player,
                       player_number: int, hud_qfont: QFont):
    if not player_instance or not hasattr(player_instance, 'current_health') or \
       not hasattr(player_instance, 'max_health'): return
    
    player_label_text = f"P{player_number}"
    qcolor_white = QColor(*getattr(C, 'WHITE', (255,255,255)))
    
    painter.setFont(hud_qfont); painter.setPen(qcolor_white)
    font_metrics = QFontMetrics(hud_qfont)
    label_text_height = float(font_metrics.height())
    
    painter.drawText(QPointF(x, y + label_text_height - float(font_metrics.descent())), player_label_text)
    
    label_height_offset = label_text_height
    health_bar_pos_x = x
    health_bar_pos_y = y + label_height_offset + 5.0
    
    hud_health_bar_width = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', 100.0))
    hud_health_bar_height = float(getattr(C, 'HUD_HEALTH_BAR_HEIGHT', 12.0))
    
    draw_health_bar_qt(painter, health_bar_pos_x, health_bar_pos_y,
                       hud_health_bar_width, hud_health_bar_height,
                       float(player_instance.current_health), float(player_instance.max_health))
    
    health_value_text = f"{int(player_instance.current_health)}/{int(player_instance.max_health)}"
    text_bounding_rect = font_metrics.boundingRect(health_value_text) 
    health_text_pos_x = health_bar_pos_x + hud_health_bar_width + 10.0
    health_text_pos_y = health_bar_pos_y + (hud_health_bar_height / 2.0) + (float(text_bounding_rect.height()) / 4.0) 
    
    painter.drawText(QPointF(health_text_pos_x, health_text_pos_y), health_value_text)


class GameSceneWidget(QWidget):
    def __init__(self, game_elements_ref: Dict[str, Any], fonts_ref: Dict[str, QFont], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.game_elements = game_elements_ref
        self.fonts = fonts_ref 
        self.download_status_message: Optional[str] = None
        self.download_progress_percent: Optional[float] = None
        
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAutoFillBackground(False)

        self._level_pixel_width: float = float(getattr(C, 'GAME_WIDTH', 800.0))
        self._level_min_x_abs: float = 0.0
        self._level_min_y_abs: float = 0.0
        self._level_max_y_abs: float = float(getattr(C, 'GAME_HEIGHT', 600.0))

        log_debug("GameSceneWidget initialized.")

    def get_camera(self) -> Optional[Camera]:
        return self.game_elements.get("camera")

    def set_level_dimensions(self,
                             level_total_width: float,
                             level_min_x: float,
                             level_min_y: float,
                             level_max_y: float):
        self._level_pixel_width = level_total_width
        self._level_min_x_abs = level_min_x
        self._level_min_y_abs = level_min_y
        self._level_max_y_abs = level_max_y
        camera = self.get_camera()
        if camera:
            camera.set_level_dimensions(level_total_width, level_min_x, level_min_y, level_max_y)
        log_info(f"GameSceneWidget: Level dimensions set - TotalW:{level_total_width}, MinX:{level_min_x}, MinY:{level_min_y}, MaxY:{level_max_y}")
        self.update() 

    def update_game_state(self, game_time_ticks: int, download_msg: Optional[str] = None, download_prog: Optional[float] = None):
        self.download_status_message = download_msg
        self.download_progress_percent = download_prog
        self.update() 

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        new_width = float(event.size().width())
        new_height = float(event.size().height())
        log_info(f"GameSceneWidget resizeEvent to: {new_width}x{new_height}")
        camera = self.get_camera()
        if camera:
            log_debug(f"GameSceneWidget: Updating camera screen dimensions to {new_width}x{new_height}")
            camera.set_screen_dimensions(new_width, new_height)
        self.game_elements['main_app_screen_width'] = new_width 
        self.game_elements['main_app_screen_height'] = new_height
        self.update()

    def paintEvent(self, event: QPaintEvent): 
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        camera = self.get_camera()
        bg_color_tuple = self.game_elements.get("level_background_color", getattr(C, 'LIGHT_BLUE', (173, 216, 230)))
        painter.fillRect(self.rect(), QColor(*bg_color_tuple)) 

        if not camera:
            log_warning("GameSceneWidget Paint: No camera instance. Drawing fallback message.")
            painter.setPen(QColor(Qt.GlobalColor.red))
            font = self.fonts.get("medium", QFont("Arial", 12)) 
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "GAME CAMERA NOT INITIALIZED")
            painter.end()
            return

        # --- Render Background Tiles FIRST ---
        background_tiles: List[BackgroundTile] = self.game_elements.get("background_tiles_list", [])
        for bg_tile in background_tiles:
            if hasattr(bg_tile, 'draw_pyside') and callable(bg_tile.draw_pyside):
                bg_tile.draw_pyside(painter, camera)
            # Add generic rect/image drawing for BackgroundTile if needed, though draw_pyside is preferred.

        # --- Render Main Game Objects ---
        all_renderables: List[Any] = self.game_elements.get("all_renderable_objects", [])
        
        for entity in all_renderables:
            # Skip drawing BackgroundTiles here if they were drawn in a separate pass above
            if isinstance(entity, BackgroundTile): 
                continue

            if hasattr(entity, 'draw_pyside') and callable(entity.draw_pyside):
                entity.draw_pyside(painter, camera) 
            elif hasattr(entity, 'rect') and isinstance(entity.rect, QRectF) and \
                 hasattr(entity, 'image') and isinstance(entity.image, QPixmap) and not entity.image.isNull():
                
                # Check 'alive' attribute for dynamic objects, always draw static tiles if they end up here
                should_draw_generic = True
                if hasattr(entity, 'alive') and not entity.alive(): # Check if it's a dynamic object that is not alive
                    should_draw_generic = False 
                
                if should_draw_generic:
                    screen_rect_qrectf = camera.apply(entity.rect)
                    if self.rect().intersects(screen_rect_qrectf.toRect()): 
                        painter.drawPixmap(screen_rect_qrectf.topLeft(), entity.image)
            # Note: Platform, Ladder, Lava now have draw_pyside, so the old specific instanceof checks aren't strictly needed
            # if they are correctly added to all_renderables and their draw_pyside is called.

        # --- Render HUD ---
        player1 = self.game_elements.get("player1")
        player2 = self.game_elements.get("player2")
        hud_font = self.fonts.get("medium", QFont("Arial", 12))

        if player1 and isinstance(player1, Player) and player1.alive() and not getattr(player1, 'is_petrified', False):
            draw_player_hud_qt(painter, 10.0, 10.0, player1, 1, hud_font)
        
        if player2 and isinstance(player2, Player) and player2.alive() and not getattr(player2, 'is_petrified', False):
            p2_hud_width_estimate = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', 100.0)) + 120.0 
            p2_hud_x = self.width() - p2_hud_width_estimate - 10.0 
            draw_player_hud_qt(painter, p2_hud_x, 10.0, player2, 2, hud_font)

        # --- Render Download Status (if any) ---
        if self.download_status_message:
            dialog_w = self.width() * 0.6; dialog_h = self.height() * 0.3
            dialog_rect = QRectF(0, 0, dialog_w, dialog_h)
            dialog_rect.moveCenter(QPointF(self.width() / 2.0, self.height() / 2.0))

            painter.fillRect(dialog_rect, QColor(50,50,50, 200))
            painter.setPen(QColor(*getattr(C, 'WHITE', (255,255,255))))
            painter.drawRect(dialog_rect)
            
            title_font = self.fonts.get("large", QFont("Arial", 24, QFont.Weight.Bold))
            msg_font = self.fonts.get("medium", QFont("Arial", 12))
            
            painter.setFont(title_font)
            title_text_rect = dialog_rect.adjusted(10,10,-10,-10) 
            painter.drawText(title_text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "File Transfer")
            
            painter.setFont(msg_font)
            title_fm = QFontMetrics(title_font)
            msg_y_start = title_text_rect.top() + float(title_fm.height()) + 10.0 
            msg_rect_adjusted = QRectF(dialog_rect.left() + 10, msg_y_start, dialog_rect.width() - 20, dialog_rect.height() - msg_y_start - 10)

            painter.drawText(msg_rect_adjusted,
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.WordWrap,
                             self.download_status_message)
            
            if self.download_progress_percent is not None and self.download_progress_percent >= 0:
                bar_margin = 20.0; bar_h = 30.0
                msg_fm = QFontMetrics(msg_font)
                approx_msg_height = float(msg_fm.height()) * (len(self.download_status_message) // 30 + 1) 
                bar_y_pos = msg_y_start + approx_msg_height + 15.0
                if bar_y_pos + bar_h > dialog_rect.bottom() - bar_margin:
                    bar_y_pos = dialog_rect.center().y() + 10 
                bar_rect = QRectF(dialog_rect.left() + bar_margin, bar_y_pos, dialog_rect.width() - 2 * bar_margin, bar_h)
                if bar_rect.bottom() > dialog_rect.bottom() - bar_margin: 
                    bar_rect.setHeight(max(5.0, dialog_rect.bottom() - bar_margin - bar_y_pos))
                
                painter.fillRect(bar_rect, QColor(*getattr(C, 'GRAY', (128,128,128))))
                fill_width = bar_rect.width() * (self.download_progress_percent / 100.0)
                painter.fillRect(QRectF(bar_rect.topLeft(), QSizeF(fill_width, bar_rect.height())), QColor(*getattr(C, 'GREEN', (0,255,0))))
                painter.setPen(QColor(*getattr(C, 'WHITE', (255,255,255))))
                painter.drawRect(bar_rect)
                prog_text = f"{self.download_progress_percent:.1f}%"
                painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0))))
                painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, prog_text)
        
        painter.end()

    def clear_scene_for_new_game(self):
        log_info("GameSceneWidget: Clearing visual state for new game.")
        self.download_status_message = None
        self.download_progress_percent = None
        self.update() 


# --- Dialogs ---

class SelectMapDialog(QDialog):
    def __init__(self, fonts: Dict[str, QFont], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Select Map")
        self.selected_map_name: Optional[str] = None
        self.fonts = fonts 
        
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.populate_maps() # Now populates with .py files
        layout.addWidget(self.list_widget)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.list_widget.itemDoubleClicked.connect(self.accept)
        self.setMinimumWidth(350)

    def populate_maps(self):
        self.list_widget.clear()
        maps_dir_from_const = getattr(C, "MAPS_DIR", "maps")
        
        project_root_guess = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(project_root_guess) in ["editor", "controller_settings"]:
            project_root_guess = os.path.dirname(project_root_guess)

        maps_dir_abs = maps_dir_from_const
        if not os.path.isabs(maps_dir_from_const):
            maps_dir_abs = os.path.join(project_root_guess, maps_dir_from_const)
       
        log_debug(f"SelectMapDialog: Populating maps from '{maps_dir_abs}' (PY files only)")

        if os.path.exists(maps_dir_abs) and os.path.isdir(maps_dir_abs):
            try:
                map_files_py = sorted([f[:-3] for f in os.listdir(maps_dir_abs) if f.endswith(".py") and f != "__init__.py" and f[:-3] != "level_default"])
                
                prio_maps = ["original", "lava", "cpu_extended", "noenemy", "bigmap1"] 
                final_ordered_maps = [m for m in prio_maps if m in map_files_py] + \
                                     [m for m in map_files_py if m not in prio_maps]

                if final_ordered_maps:
                    self.list_widget.addItems(final_ordered_maps)
                    if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)
                else:
                    self.list_widget.addItem("No selectable game maps (.py) found.");
                    self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            except OSError as e:
                self.list_widget.addItem(f"Error reading maps: {e}");
                self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self.list_widget.addItem(f"Maps directory not found: {maps_dir_abs}");
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def accept(self):
        current_item = self.list_widget.currentItem()
        if current_item and current_item.text() and \
           not current_item.text().startswith("No") and \
           not current_item.text().startswith("Error"):
            self.selected_map_name = current_item.text()
            log_info(f"SelectMapDialog: Map '{self.selected_map_name}' selected.")
            super().accept()
        elif current_item:
            QMessageBox.information(self, "No Map", "The selected item is not a valid map.")
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a map or cancel.")


class IPInputDialog(QDialog):
    def __init__(self, default_ip_port: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Enter Server IP & Port")
        self.ip_port_string: Optional[str] = None

        if default_ip_port is None:
            default_ip_port = f"127.0.0.1:{getattr(C, 'SERVER_PORT_TCP', 5555)}"

        layout = QVBoxLayout(self)
        self.label = QLabel(f"Format: IP_ADDRESS:PORT (e.g., {default_ip_port})\nCtrl+V to paste may work.")
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
        self.setMinimumWidth(350)

    def accept(self):
        text = self.line_edit.text().strip()
        if text:
            self.ip_port_string = text
            log_info(f"IPInputDialog: Accepted IP:Port '{self.ip_port_string}'")
            super().accept()
        else:
            QMessageBox.warning(self, "Input Error", "IP and Port cannot be empty.")

    def clear_input_and_focus(self):
        self.line_edit.clear()
        self.line_edit.setFocus()

    def get_ip_port(self) -> Optional[str]: 
        return self.ip_port_string