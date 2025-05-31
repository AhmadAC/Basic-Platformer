# player/statue.py
# -*- coding: utf-8 -*-
"""
Defines the Statue class, an immobile object that can be smashed.
Refactored for PySide6.
MODIFIED: Applies gravity, handles destruction by attack or player stomp.
Ensures smashed statues are no longer solid platforms.
Handles crouched vs. standing visual variants based on properties.
Statues are now destructible by default unless properties specify otherwise.
Health defaults to 1 if destructible and not specified in properties, to align with editor defaults.
Smashed pieces now respect gravity until their animation finishes.
MODIFIED: Corrected asset paths for stone and smashed stone visuals to align with
          the new 'assets/shared/Stone/' structure.
"""
# version 2.1.7 (Corrected stone asset paths)

import os
import sys # Added for path manipulation if run standalone
import time
from typing import List, Optional, Any, Dict, Tuple

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QImage
from PySide6.QtCore import QRectF, QPointF, QSizeF, Qt

# --- Project Root Setup for Standalone Testing/Linting ---
# Assumes statue.py is in Project_Root/player/
_STATUE_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_STATUE_PY = os.path.dirname(_STATUE_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_STATUE_PY not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_STATUE_PY)
# --- End Project Root Setup ---

# Game imports
import main_game.constants as C
from main_game.assets import load_gif_frames, resource_path # Corrected import path for assets

# Logger import
try:
    from main_game.logger import debug, info, warning # Corrected import path for logger
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_STATUE: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_STATUE: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_STATUE: {msg}")


# --- Monotonic Timer ---
_start_time_statue_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_statue_monotonic) * 1000)
# --- End Monotonic Timer ---


class Statue:
    def __init__(self, center_x: float, center_y: float, statue_id: Optional[Any] = None,
                 initial_image_path_override: Optional[str] = None, # Path relative to project root
                 smashed_anim_path_override: Optional[str] = None,   # Path relative to project root
                 properties: Optional[Dict[str, Any]] = None):
        self.statue_id = statue_id if statue_id is not None else id(self)
        self._valid_init = True
        self.properties = properties if properties is not None else {}
        self.initial_image_frames: List[QPixmap] = []
        self.smashed_frames: List[QPixmap] = []
        self.original_entity_type: Optional[str] = self.properties.get("original_entity_type")
        self.original_player_id: Optional[int] = self.properties.get("original_player_id")

        # --- UPDATED ASSET PATHS ---
        # Common stone assets are now in "assets/shared/Stone/"
        stone_asset_folder_relative_to_project_root = os.path.join('assets', 'shared', 'Stone')
        # --- END UPDATED ASSET PATHS ---

        is_crouched_visual_variant = self.properties.get("is_crouched_variant", False) or \
                                     self.properties.get("was_crouching", False)

        base_initial_image_filename = "__StoneCrouch.png" if is_crouched_visual_variant else "__Stone.png"
        base_smashed_anim_filename = "__StoneCrouchSmashed.gif" if is_crouched_visual_variant else "__StoneSmashed.gif"

        # Use override if provided, otherwise construct path to common stone assets
        actual_initial_image_path_rel = initial_image_path_override if initial_image_path_override \
                                       else os.path.join(stone_asset_folder_relative_to_project_root, base_initial_image_filename)
        actual_smashed_anim_path_rel = smashed_anim_path_override if smashed_anim_path_override \
                                      else os.path.join(stone_asset_folder_relative_to_project_root, base_smashed_anim_filename)

        # `resource_path` expects paths relative to project root
        full_initial_path_abs = resource_path(actual_initial_image_path_rel)
        self.initial_image_frames = load_gif_frames(full_initial_path_abs)

        if not self.initial_image_frames or self._is_placeholder_qpixmap(self.initial_image_frames[0]):
            variant_str = "Crouched" if is_crouched_visual_variant else "Standing"
            warning(f"Statue Error (ID {self.statue_id}): Failed to load initial {variant_str} stone image from '{full_initial_path_abs}'. Using placeholder.")
            gray_color = getattr(C, 'GRAY', (128, 128, 128))
            self.image = self._create_placeholder_qpixmap(QColor(*gray_color), f"Stone{variant_str[0]}")
            self.initial_image_frames = [self.image]
        else:
            self.image = self.initial_image_frames[0]

        full_smashed_path_abs = resource_path(actual_smashed_anim_path_rel)
        self.smashed_frames = load_gif_frames(full_smashed_path_abs)
        if not self.smashed_frames or self._is_placeholder_qpixmap(self.smashed_frames[0]):
            variant_str = "Crouched" if is_crouched_visual_variant else "Standing"
            warning(f"Statue Error (ID {self.statue_id}): Failed to load smashed {variant_str} stone animation from '{full_smashed_path_abs}'. Using placeholder.")
            dark_gray_color = getattr(C, 'DARK_GRAY', (50, 50, 50))
            self.smashed_frames = [self._create_placeholder_qpixmap(QColor(*dark_gray_color), f"Smash{variant_str[0]}")]

        img_w, img_h = float(self.image.width()), float(self.image.height())
        self.pos = QPointF(float(center_x), float(center_y))
        rect_x = self.pos.x() - img_w / 2.0
        rect_y = self.pos.y() - img_h / 2.0 # pos is visual center
        self.rect = QRectF(rect_x, rect_y, img_w, img_h)

        self.is_smashed = False
        self.smashed_timer_start = 0
        self.current_frame_index = 0
        self.last_anim_update = get_current_ticks_monotonic()

        self.is_dead = False
        self.death_animation_finished = False
        self._alive = True

        self.vel = QPointF(0.0, 0.0)
        self.on_ground = False
        self._gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))

        self.is_destructible_by_property = self.properties.get("destructible", True)
        default_health_if_no_prop = 1
        if self.is_destructible_by_property:
            self.max_health = int(self.properties.get("health", default_health_if_no_prop))
        else:
            self.max_health = int(self.properties.get("health", 1_000_000))
        self.current_health = self.max_health
        
        self.can_be_pushed = self.properties.get("can_be_pushed", False)
        self.push_resistance = float(self.properties.get("push_resistance", 10.0))

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSizeF(30,40): # Common placeholder size from assets.py
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0))))
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255))))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        base_tile_size = getattr(C, 'TILE_SIZE', 40)
        is_crouched_form = self.properties.get("is_crouched_variant", False) or \
                           self.properties.get("was_crouching", False)
        height_val = int(base_tile_size * 1.0) if is_crouched_form else int(base_tile_size * 1.5)
        width_val = int(base_tile_size * 0.8) if is_crouched_form else int(base_tile_size * 0.7)
        pixmap = QPixmap(max(1, width_val), max(1, height_val))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        black_color = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(10); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: warning(f"STATUE PlaceholderFontError (ID {self.statue_id}): {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self):
        img_w, img_h = self.dimensions.width(), self.dimensions.height()
        # pos is visual center
        rect_x = self.pos.x() - img_w / 2.0
        rect_y = self.pos.y() - img_h / 2.0
        if not hasattr(self, 'rect') or self.rect is None:
             self.rect = QRectF(rect_x, rect_y, img_w, img_h)
        else:
             self.rect.setRect(rect_x, rect_y, img_w, img_h)

    @property
    def dimensions(self) -> QSizeF:
        if self.image and not self.image.isNull():
            return QSizeF(float(self.image.width()), float(self.image.height()))
        # Fallback dimensions if image is not set (e.g., during init before image load)
        is_crouched_form = self.properties.get("is_crouched_variant", False) or \
                           self.properties.get("was_crouching", False)
        base_tile_size = float(getattr(C, 'TILE_SIZE', 40))
        height_val = base_tile_size * 1.0 if is_crouched_form else base_tile_size * 1.5
        width_val = base_tile_size * 0.8 if is_crouched_form else base_tile_size * 0.7
        return QSizeF(width_val, height_val)

    def alive(self) -> bool: return self._alive
    def kill(self):
        if self._alive: info(f"Statue {self.statue_id} kill() called. Setting _alive = False.")
        self._alive = False; self.is_dead = True; self.death_animation_finished = True

    def smash(self):
        if not self.is_smashed and self._valid_init and self._alive:
            info(f"Statue {self.statue_id} is being smashed.")
            self.is_smashed = True; self.is_dead = True
            self.death_animation_finished = False # Start smashed animation
            self.smashed_timer_start = get_current_ticks_monotonic()
            self.current_frame_index = 0; self.last_anim_update = self.smashed_timer_start
            if self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                self.image = self.smashed_frames[0]
            else: # Fallback if smashed frames are bad
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'DARK_GRAY',(50,50,50))), "Smash")
            self._update_rect_from_image_and_pos()
            # Gravity will take over if it was airborne.
            if self.on_ground: self.vel.setY(0.0) # If it was on ground, stop Y velocity.
            else: self.vel.setY(max(0, self.vel.y())) # Ensure it starts falling if airborne

    def take_damage(self, damage_amount: int):
        if not self.is_smashed and self._valid_init and self._alive:
            if self.is_destructible_by_property:
                self.current_health -= damage_amount
                if self.current_health <= 0:
                    debug(f"Statue {self.statue_id} took {damage_amount} damage, health depleted (current: {self.current_health}). Smashing.")
                    self.smash()
                else:
                    debug(f"Statue {self.statue_id} took {damage_amount} damage. Health: {self.current_health}/{self.max_health}")
            else: debug(f"Statue {self.statue_id} hit, but not destructible by properties.")

    def get_stomped(self, stomping_player: Any):
        if not self.is_smashed and self._valid_init and self._alive:
            player_id_log = getattr(stomping_player, 'player_id', 'UnknownPlayer')
            info(f"Statue {self.statue_id} stomped by Player {player_id_log}. Smashing.")
            self.smash()

    def apply_physics_step(self, dt_sec: float, platforms_list: List[Any]):
        if not self._valid_init or not self._alive:
            return

        if self.is_smashed and self.death_animation_finished: # Fully smashed and animation done
            self.vel.setY(0.0) # Stop moving once rubble animation is done
            self.on_ground = True # Consider it static rubble
            return

        # Apply gravity if not on ground OR if smashed and animation not finished (and not on ground)
        if not self.on_ground:
            self.vel.setY(self.vel.y() + self._gravity) # Assuming _gravity is per-update "tick"
            self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
        elif self.on_ground and not (self.is_smashed and not self.death_animation_finished):
            # Normal statue on ground, or fully finished rubble.
            self.vel.setY(0.0)
        # If smashed, animation not finished, but on_ground is true from a previous frame, vel.y() will be 0.

        # Update position based on velocity (dt_sec is assumed to be 1/FPS for now)
        # Scaled velocity is effectively units per frame
        scaled_vel_y_for_pos_update = self.vel.y() #* dt_sec * C.FPS; # Remove scaling if vel is already units/frame

        if abs(scaled_vel_y_for_pos_update) > 1e-5: # Only move if there's significant velocity
            self.pos.setY(self.pos.y() + scaled_vel_y_for_pos_update)
            self._update_rect_from_image_and_pos() # Update rect after position change

        # Collision detection with platforms for falling statues (intact or smashed pieces)
        if self.vel.y() >= 0 or (self.is_smashed and not self.on_ground): # Check if moving down or if smashed and airborne
            self.on_ground = False # Assume not on ground until collision proves otherwise
            for platform_obj in platforms_list:
                if isinstance(platform_obj, Statue) and platform_obj is self: continue # Don't collide with self
                if isinstance(platform_obj, Statue) and platform_obj.is_smashed: continue # Smashed statues don't support
                if not hasattr(platform_obj, 'rect') or not isinstance(platform_obj.rect, QRectF): continue

                if self.rect.intersects(platform_obj.rect):
                    overlap_y = self.rect.bottom() - platform_obj.rect.top()
                    if overlap_y > 0: # Intersecting from above or already overlapping
                        # Estimate previous bottom based on current frame's velocity
                        prev_bottom_y_estimate = self.rect.bottom() - scaled_vel_y_for_pos_update
                        if prev_bottom_y_estimate <= platform_obj.rect.top() + 1.0: # Was above or barely touching
                            # Check for sufficient horizontal overlap to land
                            min_h_overlap_ratio = 0.1
                            min_h_overlap_pixels = self.rect.width() * min_h_overlap_ratio
                            actual_h_overlap = min(self.rect.right(), platform_obj.rect.right()) - \
                                               max(self.rect.left(), platform_obj.rect.left())
                            if actual_h_overlap >= min_h_overlap_pixels:
                                self.rect.moveBottom(platform_obj.rect.top())
                                self.pos.setY(self.rect.center().y()) # Re-sync pos based on new rect
                                self.vel.setY(0.0)
                                self.on_ground = True
                                break # Landed on one platform
            self._update_rect_from_image_and_pos() # Final rect update after potential collision adjustment


    def update(self, dt_sec: float = 0.0): # dt_sec might not be used if animation is frame-based
        if not self._valid_init or not self._alive: return

        now = get_current_ticks_monotonic()
        image_updated = False

        if self.is_smashed:
            if not self.death_animation_finished:
                # Check if smashed duration has passed
                if now - self.smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                    self.death_animation_finished = True
                    info(f"Statue {self.statue_id} smashed animation/duration ended.")
                elif self.smashed_frames and len(self.smashed_frames) > 1: # If it's an animation
                    anim_speed = C.ANIM_FRAME_DURATION # Or a custom speed for smashed anim
                    if now - self.last_anim_update > anim_speed:
                        self.last_anim_update = now
                        self.current_frame_index += 1
                        if self.current_frame_index >= len(self.smashed_frames):
                            self.current_frame_index = len(self.smashed_frames) - 1 # Hold last frame
                        # Ensure frame index is valid
                        if 0 <= self.current_frame_index < len(self.smashed_frames) and \
                           self.smashed_frames[self.current_frame_index] and not self.smashed_frames[self.current_frame_index].isNull():
                            self.image = self.smashed_frames[self.current_frame_index]
                            self._update_rect_from_image_and_pos(); image_updated = True
                elif self.smashed_frames and len(self.smashed_frames) == 1: # Static smashed image
                     if self.image != self.smashed_frames[0] and self.smashed_frames[0] and not self.smashed_frames[0].isNull():
                        self.image = self.smashed_frames[0]
                        self._update_rect_from_image_and_pos(); image_updated = True
        # If not smashed, ensure the initial image is set (if not already updated)
        if not self.is_smashed and not image_updated:
            if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull():
                 if self.image != self.initial_image_frames[0]: # Only update if different (e.g., after being smashed and reset)
                    self.image = self.initial_image_frames[0]
                    self._update_rect_from_image_and_pos()
                    self.current_frame_index = 0 # Reset frame index for non-smashed state
            else: # Fallback if initial image is somehow invalid
                placeholder_text = "StoneC" if self.properties.get("is_crouched_variant",False) else "StoneS"
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'GRAY', (128,128,128))), placeholder_text)
                self._update_rect_from_image_and_pos()

        if self.is_dead and self.death_animation_finished and self._alive:
            self.kill() # Finalize if dead and animation done

    def get_network_data(self) -> Dict[str, Any]:
        return {
            'id': self.statue_id, 'type': 'Statue', # Class type might be useful
            'pos': (self.pos.x(), self.pos.y()),
            'vel_y': self.vel.y(), # Only sync y-velocity for falling
            'on_ground': self.on_ground,
            'is_smashed': self.is_smashed,
            'smashed_timer_start': self.smashed_timer_start,
            'current_frame_index': self.current_frame_index,
            '_valid_init': self._valid_init,
            '_alive': self._alive,
            'is_dead': self.is_dead, # For client to know if it's truly gone
            'death_animation_finished': self.death_animation_finished,
            'properties': self.properties.copy(), # Send properties for client-side creation/display
        }

    def set_network_data(self, data: Dict[str, Any]):
        self._valid_init = data.get('_valid_init', self._valid_init)
        self._alive = data.get('_alive', self._alive)
        if not self._valid_init or not self._alive:
            return

        if 'pos' in data: self.pos.setX(data['pos'][0]); self.pos.setY(data['pos'][1])
        if 'vel_y' in data: self.vel.setY(data['vel_y'])
        self.on_ground = data.get('on_ground', self.on_ground)
        self.properties = data.get('properties', self.properties).copy() # Sync properties
        self.is_destructible_by_property = self.properties.get("destructible", True)
        self.max_health = int(self.properties.get("health", 1 if self.is_destructible_by_property else 1_000_000))
        # Current health not typically synced for statues unless they have complex damage states beyond "smashed"

        new_is_smashed = data.get('is_smashed', self.is_smashed)
        if new_is_smashed != self.is_smashed: # If smashed state changed
            self.is_smashed = new_is_smashed
            if self.is_smashed:
                self.is_dead = True; self.death_animation_finished = False # Start/sync smashed anim
                self.smashed_timer_start = data.get('smashed_timer_start', get_current_ticks_monotonic())
                self.current_frame_index = data.get('current_frame_index', 0)
                self.last_anim_update = get_current_ticks_monotonic() # Sync anim timer
        
        # Sync dead/death_anim state primarily for consistency if statue becomes non-renderable
        self.is_dead = data.get('is_dead', self.is_dead)
        self.death_animation_finished = data.get('death_animation_finished', self.death_animation_finished)
        
        # Update image based on synced state
        is_crouched_variant_net = self.properties.get("is_crouched_variant", False) or \
                                  self.properties.get("was_crouching", False)

        if self.is_smashed:
            self.smashed_timer_start = data.get('smashed_timer_start', self.smashed_timer_start) # Re-sync for ongoing anim
            self.current_frame_index = data.get('current_frame_index', self.current_frame_index)
            if self.smashed_frames and 0 <= self.current_frame_index < len(self.smashed_frames) and \
               self.smashed_frames[self.current_frame_index] and not self.smashed_frames[self.current_frame_index].isNull():
                self.image = self.smashed_frames[self.current_frame_index]
            elif self.smashed_frames and self.smashed_frames[0] and not self.smashed_frames[0].isNull(): # Fallback to first smashed frame
                self.image = self.smashed_frames[0]
            else: # Absolute fallback
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'DARK_GRAY',(50,50,50))), "SmashNet")
        else: # Not smashed
            self.current_frame_index = 0 # Intact statue is usually static
            if self.initial_image_frames and self.initial_image_frames[0] and not self.initial_image_frames[0].isNull():
                 self.image = self.initial_image_frames[0]
            else: # Absolute fallback
                placeholder_text_net = "StoneCN" if is_crouched_variant_net else "StoneSN"
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'GRAY',(128,128,128))), placeholder_text_net)
        
        self._update_rect_from_image_and_pos()


    @property
    def platform_type(self) -> str: # For platform collision system if it uses types
        return "smashed_debris" if self.is_smashed else "stone_obstacle"

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return

        # Draw if alive OR if smashed and its animation isn't finished
        should_draw = self._alive or (self.is_smashed and not self.death_animation_finished)
        if not should_draw:
            return

        screen_rect_qrectf = camera.apply(self.rect)
        if painter.window().intersects(screen_rect_qrectf.toRect()): # Check if on screen
            painter.drawPixmap(screen_rect_qrectf.topLeft(), self.image)