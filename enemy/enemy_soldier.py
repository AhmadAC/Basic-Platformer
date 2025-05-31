# enemy_soldier.py
# -*- coding: utf-8 -*-
"""
Defines the EnemySoldier class.
EnemySoldiers use the same animation assets and structure as the Player class,
but are loaded from their specific color variant folders.
Refactored for new asset paths.
"""
# version 3.0.0 (Asset path refactor)

import os
from typing import List, Optional, Any, Dict

# PySide6 imports (usually not directly needed for logic if visuals handled by base/handlers)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont # For placeholder if needed
from PySide6.QtCore import QRectF, QPointF, QSize

# Game imports
import main_game.constants as C
from enemy import Enemy # Inherits from the main Enemy class
from assets import load_all_player_animations, resource_path # Key import for player-like animations

# Logger
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    # Fallback logger
    def info(msg, *args, **kwargs): print(f"INFO_SOLDIER: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG_SOLDIER: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_SOLDIER: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_SOLDIER: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_SOLDIER: {msg}")

class EnemySoldier(Enemy):
    def __init__(self, start_x: float, start_y: float,
                 color_name: str, # e.g., "green", "gray", "pink"
                 patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None,
                 properties: Optional[Dict[str, Any]] = None):
        """
        Initializes an EnemySoldier.

        Args:
            start_x (float): Initial X position (center of the base).
            start_y (float): Initial Y position (bottom of the base).
            color_name (str): The color variant of the soldier (e.g., "green", "gray").
                              This determines the asset subfolder to load from.
            patrol_area (Optional[QRectF]): The rectangular area this enemy patrols.
            enemy_id (Optional[Any]): A unique identifier for this enemy instance.
            properties (Optional[Dict[str, Any]]): Custom properties for this enemy instance.
        """

        # Call the parent Enemy's __init__.
        # The `color_name` passed here is used by EnemyBase's initial animation load attempt,
        # but EnemySoldier will immediately override self.animations with player-like ones.
        # We still pass it so EnemyBase can try to resolve `final_asset_color_name` which might be used
        # for other things like placeholder naming or default image selection if our override fails.
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name=color_name, properties=properties)

        if not self._valid_init:
            # This means EnemyBase or Enemy failed critical initialization (e.g., logger missing, constants error)
            critical(f"EnemySoldier (ID: {self.enemy_id}, Color: {color_name}): "
                     f"Critical failure in EnemyBase/Enemy super().__init__. Initialization aborted.")
            return

        self.soldier_color = color_name # Store the specific color for this soldier
        # `self.color_name` from EnemyBase will also be set to this `color_name` due to the super call.
        
        debug(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): Initializing with player-like animations.")

        # Override animations with player-like animations from the new, correct path structure.
        # New path structure: "assets/enemy_characters/soldier/{color_name}"
        soldier_asset_folder_relative_path = os.path.join("assets", "enemy_characters", "soldier", self.soldier_color)
        
        # Use `load_all_player_animations` because soldier assets are structured like player assets.
        # `load_all_player_animations` internally uses `resource_path` for each GIF.
        self.animations = load_all_player_animations(relative_asset_folder=soldier_asset_folder_relative_path)

        if self.animations is None or not self.animations.get('idle') or \
           (self.animations.get('idle') and (not self.animations['idle'] or self.animations['idle'][0].isNull())):
            critical_msg = (f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                            f"Failed loading player-like animations from '{soldier_asset_folder_relative_path}'. "
                            "The 'idle' animation is missing or invalid.")
            critical(critical_msg)
            
            # Attempt to create a visible placeholder if animations failed critically
            # EnemyBase might have already set an image; this ensures one if base failed or ours did.
            if not hasattr(self, 'image') or self.image is None or self.image.isNull():
                self.image = self._create_placeholder_qpixmap(QColor(255, 0, 255, 180), f"S-{self.soldier_color[:1].upper()}Fail") # Magenta placeholder
                self._update_rect_from_image_and_pos() # Ensure rect is updated with placeholder

            self._valid_init = False # Mark as invalid if critical animations (like idle) are missing
            # Set health to 0 and mark as dead to prevent interaction if init fails badly
            self.current_health = 0
            self.is_dead = True
            self._alive = False # Ensure it's not considered alive
            return # Stop further initialization if animations are broken

        # Reset initial image, collision dimensions, and rect based on newly loaded (player-like) animations.
        # This overrides what EnemyBase might have set using generic enemy animation assumptions.
        initial_idle_frames = self.animations.get('idle') # This should be valid due to the check above
        if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
            self.image = initial_idle_frames[0] # Set current image to the first idle frame
            
            # Update collision dimensions based on the loaded idle animation (player-like).
            # Player class calculates these based on sprite dimensions. Soldiers should too.
            # These are approximate, adjust factors as needed for good gameplay feel.
            self.standard_height = float(initial_idle_frames[0].height() * 0.85) 
            self.base_standing_collision_width = float(initial_idle_frames[0].width() * 0.50)
            
            # For crouch, if player-like soldiers can crouch, they'd need crouch anims.
            # If soldiers don't crouch, these can be simplified or based on standing.
            crouch_frames = self.animations.get('crouch')
            if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                self.crouching_collision_height = float(crouch_frames[0].height() * 0.90)
                self.base_crouch_collision_width = float(crouch_frames[0].width() * 0.70)
            else: # Fallback if no crouch animation (e.g., soldier doesn't crouch)
                self.crouching_collision_height = self.standard_height * 0.55 # Example default
                self.base_crouch_collision_width = self.base_standing_collision_width * 1.1
            
            self._update_rect_from_image_and_pos() # Re-update rect with new image and collision dimensions
            debug(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                  f"Animations reloaded. Initial image set from '{soldier_asset_folder_relative_path}/__Idle.gif'. "
                  f"Rect: ({self.rect.x():.1f},{self.rect.y():.1f} {self.rect.width():.1f}x{self.rect.height():.1f})")
        else:
            # This case should ideally be caught by the null check for `animations` or `idle` above.
            warning(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}): "
                    f"Fallback: 'idle' animation still missing/invalid after attempting load from "
                    f"'{soldier_asset_folder_relative_path}'. Visuals might be incorrect.")
            if not hasattr(self, 'image') or self.image is None or self.image.isNull():
                 self.image = self._create_placeholder_qpixmap(QColor(255, 0, 255, 180), f"S-IdleFail")
                 self._update_rect_from_image_and_pos()

        # The `update` method is inherited from `Enemy`.
        # `EnemySoldier` will use the generic AI logic from `enemy_ai_handler.py` by default.
        # If `EnemySoldier` needs unique AI behaviors, you would override `update()` or
        # add a specific `_soldier_ai_update()` method and call it from an overridden `update()`.

        # The `animate()` method is inherited from `Enemy` (which calls `enemy_animation_handler.update_enemy_animation`).
        # This should work correctly as long as `self.animations` is populated with keys that
        # `determine_enemy_animation_key` (in `enemy_animation_handler`) can resolve to,
        # which should be the case since player-like animation keys are common (idle, run, attack, etc.).

        info(f"EnemySoldier (ID: {self.enemy_id}, Color: {self.soldier_color}) "
             f"finished initialization with assets from '{soldier_asset_folder_relative_path}'. Valid: {self._valid_init}")

    # Methods like `_create_placeholder_qpixmap` and `_update_rect_from_image_and_pos`
    # are inherited from `EnemyBase` (via `Enemy`) and should work as is.

# Example Standalone Test Block (optional, for direct testing of this file)
if __name__ == '__main__':
    # This requires a QApplication instance if QPixmap operations are involved.
    # It also requires the logger and constants to be available.
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    print("--- Testing EnemySoldier Standalone ---")
    
    # --- Mock Project Root Setup for Testing ---
    # This assumes enemy_soldier.py is in a directory, and the project root is one level up.
    _project_root_test = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root_test not in sys.path:
        sys.path.insert(0, _project_root_test)
        print(f"Test: Added project root '{_project_root_test}' to sys.path for asset loading.")
    # --- End Mock Project Root Setup ---

    # Test with a color that should exist
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

    # Test with another color
    test_soldier_pink = EnemySoldier(start_x=150, start_y=100, color_name="pink")
    if test_soldier_pink._valid_init:
        print(f"Pink Soldier (ID: {test_soldier_pink.enemy_id}) created successfully. State: {test_soldier_pink.state}")
    else:
        print(f"Pink Soldier FAILED to initialize. ID: {test_soldier_pink.enemy_id}")

    # Test with a color that might not exist to see fallback/error handling
    test_soldier_blue_nonexistent = EnemySoldier(start_x=200, start_y=100, color_name="blue_variant")
    if test_soldier_blue_nonexistent._valid_init:
         print(f"Blue Variant Soldier (ID: {test_soldier_blue_nonexistent.enemy_id}) created. Actual color: {test_soldier_blue_nonexistent.soldier_color}")
    else:
        print(f"Blue Variant Soldier FAILED to initialize. ID: {test_soldier_blue_nonexistent.enemy_id}")
        if test_soldier_blue_nonexistent.image:
            print(f"  Fallback image size: {test_soldier_blue_nonexistent.image.size()}")

    # For this test to run correctly and find assets:
    # 1. `assets.py` must be in the project root or correctly importable.
    # 2. `resource_path` in `assets.py` must correctly resolve paths from the project root.
    # 3. The actual asset folders (e.g., assets/enemy_characters/soldier/green/) must exist.
    print(f"\nTest Info:")
    print(f"  Current working directory for test: {os.getcwd()}")
    print(f"  Assumed project root for test: {_project_root_test}")
    green_asset_path_for_test = os.path.join("assets", "enemy_characters", "soldier", "green", "__Idle.gif")
    resolved_green_path = resource_path(green_asset_path_for_test)
    print(f"  Example resolved path for green soldier idle: {resolved_green_path}")
    print(f"  Does it exist? {os.path.exists(resolved_green_path)}")

    print("--- EnemySoldier Test Finished ---")