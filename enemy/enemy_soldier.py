# enemy_soldier.py
# -*- coding: utf-8 -*-
"""
Defines the EnemySoldier class.
EnemySoldiers use the same animation assets and structure as the Player class,
but are loaded from their specific color variant folders.
Refactored for new asset paths.
MODIFIED: Corrected logger fallback assignment and import path.
"""
# version 3.0.1 (Asset path refactor, Logger fix)

import os
import sys # Added for logger fallback
from typing import List, Optional, Any, Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import QRectF, QPointF, QSize, Qt # Added Qt, QSize

# Game imports
import main_game.constants as C
from enemy.enemy import Enemy # Inherits from the main Enemy class
from main_game.assets import load_all_player_animations, resource_path

# --- Logger Setup ---
import logging
_enemy_soldier_logger_instance = logging.getLogger(__name__ + "_enemy_soldier_internal_fallback")
if not _enemy_soldier_logger_instance.hasHandlers():
    _handler_es_fb = logging.StreamHandler(sys.stdout)
    _formatter_es_fb = logging.Formatter('ENEMY_SOLDIER (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_es_fb.setFormatter(_formatter_es_fb)
    _enemy_soldier_logger_instance.addHandler(_handler_es_fb)
    _enemy_soldier_logger_instance.setLevel(logging.DEBUG)
    _enemy_soldier_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_soldier_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_soldier_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_soldier_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_soldier_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_soldier_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info
debug = _fallback_log_debug
warning = _fallback_log_warning
error = _fallback_log_error
critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info
    debug = project_debug
    warning = project_warning
    error = project_error
    critical = project_critical
    debug("EnemySoldier: Successfully aliased project's logger functions from main_game.logger.")
except ImportError:
    critical("CRITICAL ENEMY_SOLDIER: Failed to import logger from main_game.logger. Using internal fallback print statements for logging.")
except Exception as e_logger_init_soldier:
    critical(f"CRITICAL ENEMY_SOLDIER: Unexpected error during logger setup from main_game.logger: {e_logger_init_soldier}. Using internal fallback.")
# --- End Logger Setup ---


class EnemySoldier(Enemy):
    def __init__(self, start_x: float, start_y: float,
                 color_name: str,
                 patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None,
                 properties: Optional[Dict[str, Any]] = None):

        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name=color_name, properties=properties)

        if not self._valid_init:
            critical(f"EnemySoldier (ID: {self.enemy_id}, Color: {color_name}): "
                     f"Critical failure in EnemyBase/Enemy super().__init__. Initialization aborted.")
            return

        self.soldier_color = color_name
        
        debug(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): Initializing with player-like animations.")

        soldier_asset_folder_relative_path = os.path.join("assets", "enemy_characters", "soldier", self.soldier_color)
        
        self.animations = load_all_player_animations(relative_asset_folder=soldier_asset_folder_relative_path)

        if self.animations is None or not self.animations.get('idle') or \
           (self.animations.get('idle') and (not self.animations['idle'] or self.animations['idle'][0].isNull())):
            critical_msg = (f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                            f"Failed loading player-like animations from '{soldier_asset_folder_relative_path}'. "
                            "The 'idle' animation is missing or invalid.")
            critical(critical_msg)
            
            if not hasattr(self, 'image') or self.image is None or self.image.isNull():
                self.image = self._create_placeholder_qpixmap(QColor(255, 0, 255, 180), f"S-{self.soldier_color[:1].upper()}Fail")
                self._update_rect_from_image_and_pos()

            self._valid_init = False
            self.current_health = 0
            self.is_dead = True
            self._alive = False
            return

        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
            self.image = initial_idle_frames[0]
            
            # These collision dimensions are typical for player-like sprites.
            # EnemyBase might have set different defaults if it loaded generic enemy anims initially.
            # We override them here based on the soldier's (player-like) idle sprite.
            self.standard_height = float(initial_idle_frames[0].height() * 0.85) 
            self.base_standing_collision_width = float(initial_idle_frames[0].width() * 0.50)
            
            crouch_frames = self.animations.get('crouch')
            if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                self.crouching_collision_height = float(crouch_frames[0].height() * 0.90)
                self.base_crouch_collision_width = float(crouch_frames[0].width() * 0.70)
            else:
                self.crouching_collision_height = self.standard_height * 0.55
                self.base_crouch_collision_width = self.base_standing_collision_width * 1.1
            
            self._update_rect_from_image_and_pos()
            debug(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                  f"Animations reloaded. Initial image set from '{soldier_asset_folder_relative_path}/__Idle.gif'. "
                  f"Rect: ({self.rect.x():.1f},{self.rect.y():.1f} {self.rect.width():.1f}x{self.rect.height():.1f})")
        else:
            warning(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                    f"Fallback: 'idle' animation still missing/invalid after attempting load from "
                    f"'{soldier_asset_folder_relative_path}'. Visuals might be incorrect.")
            if not hasattr(self, 'image') or self.image is None or self.image.isNull():
                 self.image = self._create_placeholder_qpixmap(QColor(255, 0, 255, 180), f"S-IdleFail")
                 self._update_rect_from_image_and_pos()

        info(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}) "
             f"finished initialization with assets from '{soldier_asset_folder_relative_path}'. Valid: {self._valid_init}")


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    print("--- Testing EnemySoldier Standalone ---")
    
    _project_root_test_soldier = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root_test_soldier not in sys.path:
        sys.path.insert(0, _project_root_test_soldier)
        print(f"Test: Added project root '{_project_root_test_soldier}' to sys.path for asset loading.")

    test_soldier_green = EnemySoldier(start_x=100, start_y=100, color_name="green")
    if test_soldier_green._valid_init:
        print(f"Green Soldier (ID: {test_soldier_green.enemy_id}) created successfully. State: {test_soldier_green.state}")
        if test_soldier_green.animations:
            print(f"  Loaded animations: {list(test_soldier_green.animations.keys())}")
            if test_soldier_green.image:
                print(f"  Initial image size: {test_soldier_green.image.size()}")
                print(f"  Collision rect: {test_soldier_green.rect}")
    else:
        print(f"Green Soldier FAILED to initialize. ID: {test_soldier_green.enemy_id}")

    test_soldier_pink = EnemySoldier(start_x=150, start_y=100, color_name="pink")
    if test_soldier_pink._valid_init:
        print(f"Pink Soldier (ID: {test_soldier_pink.enemy_id}) created successfully. State: {test_soldier_pink.state}")
    else:
        print(f"Pink Soldier FAILED to initialize. ID: {test_soldier_pink.enemy_id}")

    test_soldier_blue_nonexistent = EnemySoldier(start_x=200, start_y=100, color_name="blue_variant")
    if test_soldier_blue_nonexistent._valid_init:
         print(f"Blue Variant Soldier (ID: {test_soldier_blue_nonexistent.enemy_id}) created. Actual color: {test_soldier_blue_nonexistent.soldier_color}")
    else:
        print(f"Blue Variant Soldier FAILED to initialize. ID: {test_soldier_blue_nonexistent.enemy_id}")
        if hasattr(test_soldier_blue_nonexistent, 'image') and test_soldier_blue_nonexistent.image: # Check if image exists
            print(f"  Fallback image size: {test_soldier_blue_nonexistent.image.size()}")

    print(f"\nTest Info:")
    print(f"  Current working directory for test: {os.getcwd()}")
    print(f"  Assumed project root for test: {_project_root_test_soldier}")
    green_asset_path_for_test = os.path.join("assets", "enemy_characters", "soldier", "green", "__Idle.gif")
    resolved_green_path = resource_path(green_asset_path_for_test)
    print(f"  Example resolved path for green soldier idle: {resolved_green_path}")
    print(f"  Does it exist? {os.path.exists(resolved_green_path)}")

    print("--- EnemySoldier Test Finished ---")