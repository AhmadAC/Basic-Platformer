# game_ui.py
# -*- coding: utf-8 -*-
"""
Manages UI elements for the PySide6 version of the game.
This includes GameSceneWidget rendering and dialogs.
MODIFIED: Corrected Qt.AlignmentFlag.WordWrap to Qt.TextFlag.WordWrap.
MODIFIED: Added dynamic title to the status message overlay.
MODIFIED: Health text in HUD now has a semi-transparent rounded black background and white text.
MODIFIED: Ensured fallback logger has correct formatting if project logger fails.
"""
# version 2.0.16 (Fallback logger formatting)

import sys
import os
import time
from typing import Dict, Optional, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget,QLabel, QDialog, QListWidget, QListWidgetItem, QLineEdit,
    QDialogButtonBox, QMessageBox, QVBoxLayout, QProgressBar
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPixmap, QPalette,
    QFontMetrics, QResizeEvent, QPaintEvent, QImage, QTransform
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF

import main_game.constants as C
from tiles import Platform, Ladder, Lava, BackgroundTile # For type checking (though not drawn directly by these classes here)
from player import Player
from camera import Camera
from utils import PrintLimiter


# --- Logging Setup ---
import logging
logger_game_ui = logging.getLogger(__name__)

# Define aliases at the module level, initially as fallbacks
def log_info(msg, *args, **kwargs): logger_game_ui.info(msg, *args, **kwargs)
def log_debug(msg, *args, **kwargs): logger_game_ui.debug(msg, *args, **kwargs)
def log_warning(msg, *args, **kwargs): logger_game_ui.warning(msg, *args, **kwargs)
def log_error(msg, *args, **kwargs): logger_game_ui.error(msg, *args, **kwargs)
def log_critical(msg, *args, **kwargs): logger_game_ui.critical(msg, *args, **kwargs)

try:
    from logger import info as project_info, debug as project_debug, \
                       warning as project_warning, error as project_error, \
                       critical as project_critical
    log_info = project_info
    log_debug = project_debug
    log_warning = project_warning
    log_error = project_error
    log_critical = project_critical
    log_debug("GameUI: Successfully aliased project's logger functions.")
except ImportError:
    if not logger_game_ui.hasHandlers() and not logging.getLogger().hasHandlers():
        # Configure fallback logger if project logger fails and no other handler is set
        _gameui_fallback_console_handler = logging.StreamHandler(sys.stdout)
        _gameui_fallback_console_formatter = logging.Formatter(
            'GAME_UI (ImportFallbackConsole - %(filename)s:%(lineno)d): %(levelname)s - %(message)s' # Added filename and line
        )
        _gameui_fallback_console_handler.setFormatter(_gameui_fallback_console_formatter)
        logger_game_ui.addHandler(_gameui_fallback_console_handler)
        logger_game_ui.setLevel(logging.DEBUG)
        logger_game_ui.propagate = False
    log_critical("GameUI: Failed to import project's logger. Using isolated fallback for game_ui.py.")


# --- Helper Drawing Functions ---
def draw_health_bar_qt(painter: QPainter, x: float, y: float,
                       width: float, height: float,
                       current_hp: float, max_hp: float):
    if max_hp <= 0: return
    current_hp_clamped = max(0.0, min(current_hp, max_hp))
    bar_width = max(1.0, float(width)); bar_height = max(1.0, float(height))
    health_ratio = current_hp_clamped / max_hp

    # Use constants for colors, with fallbacks
    color_red_rgb = getattr(C, 'RED', (255,0,0))
    color_green_rgb = getattr(C, 'GREEN', (0,255,0))
    color_dark_gray_rgb = getattr(C, 'DARK_GRAY', (50,50,50))
    color_black_rgb = getattr(C, 'BLACK', (0,0,0))

    qcolor_red = QColor(*color_red_rgb); qcolor_green = QColor(*color_green_rgb)
    qcolor_dark_gray = QColor(*color_dark_gray_rgb); qcolor_black = QColor(*color_black_rgb)

    # Interpolate color from red to green based on health ratio
    r = int(qcolor_red.redF()   * (1 - health_ratio) * 255 + qcolor_green.redF()   * health_ratio * 255)
    g = int(qcolor_red.greenF() * (1 - health_ratio) * 255 + qcolor_green.greenF() * health_ratio * 255)
    b = int(qcolor_red.blueF()  * (1 - health_ratio) * 255 + qcolor_green.blueF()  * health_ratio * 255)
    health_qcolor = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    background_rect = QRectF(x, y, bar_width, bar_height)
    painter.fillRect(background_rect, qcolor_dark_gray)
    health_fill_width = bar_width * health_ratio
    if health_fill_width > 0: painter.fillRect(QRectF(x, y, health_fill_width, bar_height), health_qcolor)

    pen = QPen(qcolor_black); pen.setWidth(1) # Ensure pen width is integer
    painter.setPen(pen); painter.drawRect(background_rect)

def draw_player_hud_qt(painter: QPainter, x: float, y: float, player_instance: Player,
                       player_number: int, hud_qfont: QFont):
    if not player_instance or not hasattr(player_instance, 'current_health') or not hasattr(player_instance, 'max_health'):
        log_warning(f"draw_player_hud_qt: Invalid player_instance or missing health attributes for P{player_number}.")
        return

    player_label_text = f"P{player_number}"
    qcolor_white = QColor(*getattr(C, 'WHITE', (255,255,255)))
    qcolor_black_transparent_bg = QColor(0, 0, 0, int(255 * 0.35)) # Black with 35% opacity for better contrast

    painter.setFont(hud_qfont)
    painter.setPen(qcolor_white)

    font_metrics = QFontMetrics(hud_qfont)
    label_text_height = float(font_metrics.height())
    # Draw "P1", "P2" etc.
    painter.drawText(QPointF(x, y + label_text_height - float(font_metrics.descent())), player_label_text)

    label_height_offset = label_text_height
    health_bar_pos_x = x
    health_bar_pos_y = y + label_height_offset + 5.0 # Space below "Px"

    hud_health_bar_width = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', 100.0))
    hud_health_bar_height = float(getattr(C, 'HUD_HEALTH_BAR_HEIGHT', 12.0))

    # Draw the green/red health bar
    draw_health_bar_qt(painter, health_bar_pos_x, health_bar_pos_y,
                       hud_health_bar_width, hud_health_bar_height,
                       float(player_instance.current_health), float(player_instance.max_health))

    # Health Text (e.g., "100/100")
    health_value_text = f"{int(player_instance.current_health)}/{int(player_instance.max_health)}"
    text_bounding_rect = font_metrics.boundingRect(health_value_text)

    text_bg_padding_x = 4
    text_bg_padding_y = 2
    
    text_bg_rect_x = health_bar_pos_x + hud_health_bar_width + 5.0 # Position to the right of health bar
    text_bg_rect_y = health_bar_pos_y + (hud_health_bar_height / 2.0) - (text_bounding_rect.height() / 2.0) - text_bg_padding_y
    text_bg_rect_width = text_bounding_rect.width() + 2 * text_bg_padding_x
    text_bg_rect_height = text_bounding_rect.height() + 2 * text_bg_padding_y
    
    text_bg_qrectf = QRectF(text_bg_rect_x, text_bg_rect_y, text_bg_rect_width, text_bg_rect_height)
    corner_radius = 5.0

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(qcolor_black_transparent_bg)
    painter.drawRoundedRect(text_bg_qrectf, corner_radius, corner_radius)

    health_text_pos_x = text_bg_rect_x + text_bg_padding_x
    health_text_pos_y = text_bg_rect_y + text_bg_padding_y + label_text_height - float(font_metrics.descent())

    painter.setPen(qcolor_white)
    painter.drawText(QPointF(health_text_pos_x, health_text_pos_y), health_value_text)


class GameSceneWidget(QWidget):
    paint_event_limiter = PrintLimiter(default_limit=1, default_period=2.0)
    paint_event_detail_limiter = PrintLimiter(default_limit=1, default_period=5.0)

    def __init__(self, game_elements_ref: Dict[str, Any], fonts_ref: Dict[str, QFont], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.game_elements = game_elements_ref
        self.fonts = fonts_ref
        self.download_status_message: Optional[str] = None
        self.download_status_title: Optional[str] = None
        self.download_progress_percent: Optional[float] = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) # May improve performance if bg is always fully drawn
        self.setAutoFillBackground(False) # We handle background fill in paintEvent
        
        # Initialize level dimension fallbacks
        self._level_pixel_width: float = float(getattr(C, 'GAME_WIDTH', 960.0) * 2) # Default large size
        self._level_min_x_abs: float = 0.0
        self._level_min_y_abs: float = 0.0
        self._level_max_y_abs: float = float(getattr(C, 'GAME_HEIGHT', 600.0) * 2) # Default large size
        log_debug("GameSceneWidget initialized.")

    def get_camera(self) -> Optional[Camera]:
        cam = self.game_elements.get("camera")
        if not isinstance(cam, Camera):
            if GameSceneWidget.paint_event_limiter.can_log("camera_missing_type_gsw"):
                 log_warning(f"GameSceneWidget: 'camera' in game_elements is not a Camera instance (type: {type(cam)}).")
            return None
        return cam

    def set_level_dimensions(self,level_total_width: float,level_min_x: float,level_min_y: float,level_max_y: float):
        self._level_pixel_width = float(level_total_width)
        self._level_min_x_abs = float(level_min_x)
        self._level_min_y_abs = float(level_min_y)
        self._level_max_y_abs = float(level_max_y)
        camera = self.get_camera()
        if camera: camera.set_level_dimensions(self._level_pixel_width, self._level_min_x_abs, self._level_min_y_abs, self._level_max_y_abs)
        log_info(f"GameSceneWidget: Level dimensions set - TotalW:{self._level_pixel_width:.1f}, MinX:{self._level_min_x_abs:.1f}, MinY:{self._level_min_y_abs:.1f}, MaxY:{self._level_max_y_abs:.1f}")
        self.update() # Request repaint as dimensions changed

    def update_game_state(self, game_time_ticks_ignored: int, download_title: Optional[str] = None, download_msg: Optional[str] = None, download_prog: Optional[float] = None):
        self.download_status_title = download_title
        self.download_status_message = download_msg
        self.download_progress_percent = download_prog
        self.update() # Schedule a repaint

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        new_width = float(event.size().width())
        new_height = float(event.size().height())
        log_info(f"GameSceneWidget resizeEvent to: {new_width:.1f}x{new_height:.1f}")
        camera = self.get_camera()
        if camera:
            camera.set_screen_dimensions(new_width, new_height)
            # Re-focus camera after resize
            player1 = self.game_elements.get("player1")
            player2 = self.game_elements.get("player2") # Assuming P2 might also be a focus target
            focus_target = None
            # Prioritize P1, then P2, or any valid player for focus
            if player1 and isinstance(player1, Player) and player1.alive() and player1._valid_init and not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False):
                focus_target = player1
            elif player2 and isinstance(player2, Player) and player2.alive() and player2._valid_init and not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False):
                focus_target = player2
            # Extend for P3, P4 if they can be primary focus
            elif player1 and isinstance(player1, Player) and player1.alive() and player1._valid_init : focus_target = player1
            elif player2 and isinstance(player2, Player) and player2.alive() and player2._valid_init : focus_target = player2

            if focus_target: camera.update(focus_target)
            else: camera.static_update()
        
        self.game_elements['main_app_screen_width'] = new_width
        self.game_elements['main_app_screen_height'] = new_height
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self) # Correctly initialize QPainter for this widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False) # Typically off for pixel art
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False) # Also off for pixel art

        camera = self.get_camera()
        bg_color_tuple = self.game_elements.get("level_background_color", getattr(C, 'LIGHT_BLUE', (173, 216, 230)))
        painter.fillRect(self.rect(), QColor(*bg_color_tuple))

        if not camera:
            log_warning("GameSceneWidget Paint WARNING: No camera instance. Drawing fallback message.")
            painter.setPen(QColor(Qt.GlobalColor.red))
            painter.setFont(self.fonts.get("medium", QFont("Arial", 16))) # Slightly larger for error
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "GAME CAMERA NOT INITIALIZED")
            painter.end(); return # Crucial to end painter if returning early

        all_renderables: List[Any] = self.game_elements.get("all_renderable_objects", [])
        
        for entity in all_renderables:
            if hasattr(entity, 'draw_pyside') and callable(entity.draw_pyside):
                entity.draw_pyside(painter, camera)
            elif isinstance(entity, dict) and 'rect' in entity and 'image' in entity: # For custom images
                # ... (custom image dict drawing logic as before) ...
                custom_image_dict = entity
                rect_to_draw_qrectf = custom_image_dict['rect']
                pixmap_to_draw_qpix = custom_image_dict['image']
                opacity_float = custom_image_dict.get('opacity_float', 1.0)
                if not isinstance(rect_to_draw_qrectf, QRectF) or not isinstance(pixmap_to_draw_qpix, QPixmap) or pixmap_to_draw_qpix.isNull():
                    continue
                screen_rect_qrectf_custom = camera.apply(rect_to_draw_qrectf)
                if painter.window().intersects(screen_rect_qrectf_custom.toRect()):
                    original_painter_opacity_custom = painter.opacity()
                    painter.setOpacity(opacity_float * original_painter_opacity_custom)
                    painter.drawPixmap(screen_rect_qrectf_custom.topLeft(), pixmap_to_draw_qpix)
                    painter.setOpacity(original_painter_opacity_custom)
            # ... (fallback generic entity drawing, if any, was removed; entities should have draw_pyside)

        # Draw HUD
        player1: Optional[Player] = self.game_elements.get("player1")
        player2: Optional[Player] = self.game_elements.get("player2")
        player3: Optional[Player] = self.game_elements.get("player3")
        player4: Optional[Player] = self.game_elements.get("player4")
        num_active_players_for_hud = self.game_elements.get('num_active_players_for_mode', 0)
        
        active_players_for_hud: List[Player] = []
        if player1 and isinstance(player1, Player) and num_active_players_for_hud >= 1: active_players_for_hud.append(player1)
        if player2 and isinstance(player2, Player) and num_active_players_for_hud >= 2: active_players_for_hud.append(player2)
        if player3 and isinstance(player3, Player) and num_active_players_for_hud >= 3: active_players_for_hud.append(player3)
        if player4 and isinstance(player4, Player) and num_active_players_for_hud >= 4: active_players_for_hud.append(player4)

        hud_font = self.fonts.get("medium", QFont("Arial", 12))
        start_x_hud = 10.0
        for p_instance_hud in active_players_for_hud:
             if p_instance_hud and hasattr(p_instance_hud, 'alive') and p_instance_hud.alive() and \
                not getattr(p_instance_hud, 'is_petrified', False): # Don't draw HUD for petrified players
                draw_player_hud_qt(painter, start_x_hud, 10.0, p_instance_hud, p_instance_hud.player_id, hud_font)
                hud_width_estimate = float(getattr(C, 'HUD_HEALTH_BAR_WIDTH', 100.0)) + 120.0 # Approx width of Px + Bar + Text
                start_x_hud += hud_width_estimate + 15.0 # Spacing for next HUD

        # Draw Download/Status Message Overlay
        if self.download_status_message:
            # ... (status message overlay drawing logic as before, ensuring Qt.TextFlag.WordWrap) ...
            dialog_w = self.width() * 0.6; dialog_h = self.height() * 0.3
            dialog_rect = QRectF(0, 0, dialog_w, dialog_h)
            dialog_rect.moveCenter(QPointF(self.width() / 2.0, self.height() / 2.0))
            painter.fillRect(dialog_rect, QColor(50,50,50, 200))
            painter.setPen(QColor(*getattr(C, 'WHITE', (255,255,255))))
            painter.drawRect(dialog_rect)
            title_font = self.fonts.get("large", QFont("Arial", 24, QFont.Weight.Bold))
            msg_font = self.fonts.get("medium", QFont("Arial", 12))
            dialog_title_text = self.download_status_title if self.download_status_title else "Status"
            painter.setFont(title_font); title_text_rect = dialog_rect.adjusted(10,10,-10,-10)
            painter.drawText(title_text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, dialog_title_text) # type: ignore
            painter.setFont(msg_font); title_fm = QFontMetrics(title_font); msg_y_start = title_text_rect.top() + float(title_fm.height()) + 10.0
            msg_rect_adjusted = QRectF(dialog_rect.left() + 10, msg_y_start, dialog_rect.width() - 20, dialog_rect.height() - msg_y_start - 10)
            alignment_flags_for_text = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.WordWrap # Corrected flag
            painter.drawText(msg_rect_adjusted, int(alignment_flags_for_text), self.download_status_message)
            if self.download_progress_percent is not None and self.download_progress_percent >= 0:
                # ... (progress bar drawing as before) ...
                bar_margin = 20.0; bar_h = 30.0; msg_fm = QFontMetrics(msg_font)
                approx_msg_height = float(msg_fm.height()) * (len(self.download_status_message) // 30 + 1)
                bar_y_pos = msg_y_start + approx_msg_height + 15.0
                if bar_y_pos + bar_h > dialog_rect.bottom() - bar_margin: bar_y_pos = dialog_rect.center().y() + 10
                bar_rect = QRectF(dialog_rect.left() + bar_margin, bar_y_pos, dialog_rect.width() - 2 * bar_margin, bar_h)
                if bar_rect.bottom() > dialog_rect.bottom() - bar_margin: bar_rect.setHeight(max(5.0, dialog_rect.bottom() - bar_margin - bar_y_pos))
                painter.fillRect(bar_rect, QColor(*getattr(C, 'GRAY', (128,128,128))))
                fill_width = bar_rect.width() * (self.download_progress_percent / 100.0)
                painter.fillRect(QRectF(bar_rect.topLeft(), QSizeF(fill_width, bar_rect.height())), QColor(*getattr(C, 'GREEN', (0,255,0))))
                painter.setPen(QColor(*getattr(C, 'WHITE', (255,255,255)))); painter.drawRect(bar_rect)
                prog_text = f"{self.download_progress_percent:.1f}%"; painter.setPen(QColor(*getattr(C, 'BLACK', (0,0,0))))
                painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, prog_text) # type: ignore
        
        painter.end() # Crucial: end the painter

    def clear_scene_for_new_game(self):
        log_info("GameSceneWidget: Clearing visual state for new game (download messages).")
        self.download_status_title = None
        self.download_status_message = None
        self.download_progress_percent = None
        self.update() # Request repaint to clear overlay

# --- Dialog Classes (SelectMapDialog, IPInputDialog) remain the same as your v2.0.15 ---
# (Assuming they don't have QPainter issues and were working correctly before)

class SelectMapDialog(QDialog):
    # ... (No changes from your v2.0.15, ensure it's correct)
    def __init__(self, fonts: Dict[str, QFont], parent: Optional[QWidget] = None):
        super().__init__(parent); self.setWindowTitle("Select Map"); self.selected_map_name: Optional[str] = None; self.fonts = fonts
        layout = QVBoxLayout(self); self.list_widget = QListWidget(self); self.populate_maps()
        layout.addWidget(self.list_widget)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept); self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box); self.list_widget.itemDoubleClicked.connect(self.accept); self.setMinimumWidth(350)
    def populate_maps(self):
        self.list_widget.clear(); maps_dir_from_const = getattr(C, "MAPS_DIR", "maps")
        project_root_guess = getattr(C, "PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        maps_dir_abs = maps_dir_from_const
        if not os.path.isabs(maps_dir_from_const): maps_dir_abs = os.path.join(project_root_guess, maps_dir_from_const)
        log_debug(f"SelectMapDialog: Populating maps from '{maps_dir_abs}' (PY files only)")
        if os.path.exists(maps_dir_abs) and os.path.isdir(maps_dir_abs):
            try:
                available_map_folder_names: List[str] = []
                for entry_name in os.listdir(maps_dir_abs):
                    potential_map_folder_path = os.path.join(maps_dir_abs, entry_name)
                    if os.path.isdir(potential_map_folder_path):
                        expected_map_py_file = os.path.join(potential_map_folder_path, f"{entry_name}.py")
                        if os.path.isfile(expected_map_py_file): available_map_folder_names.append(entry_name)
                prio_maps = ["original", "lava", "cpu_extended", "noenemy", "bigmap1", "one", "8", "back", "big", "chest", "custom", "three"]
                final_ordered_maps = [m for m in prio_maps if m in available_map_folder_names] + \
                                     [m for m in sorted(available_map_folder_names) if m not in prio_maps]
                if final_ordered_maps: self.list_widget.addItems(final_ordered_maps);
                if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)
                else: self.list_widget.addItem("No selectable game maps (folders with .py) found."); self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            except OSError as e: self.list_widget.addItem(f"Error reading maps: {e}"); self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else: self.list_widget.addItem(f"Maps directory not found: {maps_dir_abs}"); self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    def accept(self):
        current_item = self.list_widget.currentItem()
        if current_item and current_item.text() and not current_item.text().startswith("No") and not current_item.text().startswith("Error"):
            self.selected_map_name = current_item.text(); log_info(f"SelectMapDialog: Map '{self.selected_map_name}' selected."); super().accept()
        elif current_item: QMessageBox.information(self, "No Map", "The selected item is not a valid map.")
        else: QMessageBox.warning(self, "Selection Error", "Please select a map or cancel.")

class IPInputDialog(QDialog):
    # ... (No changes from your v2.0.15, ensure it's correct)
    def __init__(self, default_ip_port: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent); self.setWindowTitle("Enter Server IP & Port"); self.ip_port_string: Optional[str] = None
        if default_ip_port is None: default_ip_port = f"127.0.0.1:{getattr(C, 'SERVER_PORT_TCP', 5555)}"
        layout = QVBoxLayout(self)
        self.label = QLabel(f"Format: IP_ADDRESS:PORT (e.g., {default_ip_port})\nCtrl+V to paste may work."); self.label.setWordWrap(True)
        layout.addWidget(self.label); self.line_edit = QLineEdit(self); self.line_edit.setText(default_ip_port)
        layout.addWidget(self.line_edit)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept); self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box); self.line_edit.returnPressed.connect(self.accept); self.setMinimumWidth(350)
    def accept(self):
        text = self.line_edit.text().strip()
        if text: self.ip_port_string = text; log_info(f"IPInputDialog: Accepted IP:Port '{self.ip_port_string}'"); super().accept()
        else: QMessageBox.warning(self, "Input Error", "IP and Port cannot be empty.")
    def clear_input_and_focus(self): self.line_edit.clear(); self.line_edit.setFocus()
    def get_ip_port(self) -> Optional[str]: return self.ip_port_string