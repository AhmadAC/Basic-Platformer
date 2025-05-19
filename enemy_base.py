#################### START OF FILE: enemy_base.py ####################

# enemy_base.py
# -*- coding: utf-8 -*-
"""
Defines the EnemyBase class, the foundational class for enemies.
Handles core attributes, animation loading, and common assets for PySide6.
"""
# version 2.0.0 (PySide6 Refactor)
import os
import random
from typing import List, Optional, Any, Dict # Added Dict

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game imports
import constants as C
from assets import load_all_player_animations, load_gif_frames, resource_path # Now Qt-based

# Logger import
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_BASE: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}") # Define error for fallback
    def critical(msg): print(f"CRITICAL: {msg}")

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_base = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_base) * 1000)


class EnemyBase:
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None, # patrol_area QRectF
                 enemy_id: Optional[Any] = None, color_name: Optional[str] = None):
        
        self.spawn_pos = QPointF(float(start_x), float(start_y))
        self.patrol_area = patrol_area # Should be QRectF if provided
        self.enemy_id = enemy_id if enemy_id is not None else id(self)
        self._valid_init = True
        self.color_name = "unknown"

        character_base_asset_folder = 'characters'
        available_enemy_colors = ['green', 'pink', 'purple', 'gray', 'yellow', 'orange']

        if not available_enemy_colors:
             warning(f"EnemyBase Warning (ID: {self.enemy_id}): No enemy colors defined! Defaulting to 'player1' assets for structure.")
             available_enemy_colors = ['player1']

        if color_name and color_name in available_enemy_colors:
            self.color_name = color_name
        elif color_name:
            warning(f"EnemyBase Warning (ID: {self.enemy_id}): Specified color '{color_name}' not in available. Choosing random.")
            self.color_name = random.choice(available_enemy_colors)
        else:
            self.color_name = random.choice(available_enemy_colors)
        debug(f"EnemyBase (ID: {self.enemy_id}): Initializing with color: {self.color_name}")

        chosen_enemy_asset_folder = os.path.join(character_base_asset_folder, self.color_name)
        self.animations: Optional[Dict[str, List[QPixmap]]] = load_all_player_animations(relative_asset_folder=chosen_enemy_asset_folder)

        self.image: Optional[QPixmap] = None
        self.rect = QRectF() # Initialize as empty QRectF

        if self.animations is None:
            critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): Failed loading animations from '{chosen_enemy_asset_folder}'.")
            self.image = self._create_placeholder_qpixmap(QColor(*C.BLUE), f"AnimLoadFail-{self.color_name[:3]}")
            self._update_rect_from_image_and_pos(QPointF(float(start_x), float(start_y))) # Set rect using placeholder
            self._valid_init = False
            self.is_dead = True
            # Initialize essential physics attributes to prevent crashes
            self.pos = QPointF(float(start_x), float(start_y))
            self.vel = QPointF(0.0, 0.0)
            self.acc = QPointF(0.0, 0.0)
            self.state = 'idle'; self.current_frame = 0; self.last_anim_update = 0
            self.facing_right = True; self.on_ground = False
            self.current_health = 0; self.max_health = 0
        else:
            self._last_facing_right = True
            self._last_state_for_debug = "init"
            self.state = 'idle'
            self.current_frame = 0
            self.last_anim_update = get_current_ticks()

            initial_idle_animation = self.animations.get('idle')
            if not initial_idle_animation or not initial_idle_animation[0] or initial_idle_animation[0].isNull():
                 warning(f"EnemyBase Warning (ID: {self.enemy_id}, Color: {self.color_name}): 'idle' animation missing/empty. Fallback.")
                 first_anim_key = next(iter(self.animations), None)
                 initial_idle_animation = self.animations.get(first_anim_key) if first_anim_key and self.animations.get(first_anim_key) else None

            if initial_idle_animation and initial_idle_animation[0] and not initial_idle_animation[0].isNull():
                self.image = initial_idle_animation[0]
            else:
                self.image = self._create_placeholder_qpixmap(QColor(*C.BLUE), f"NoIdle-{self.color_name[:3]}")
                critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, Color: {self.color_name}): No suitable initial animation. Enemy invalid.")
                self._valid_init = False; self.is_dead = True
            
            self._update_rect_from_image_and_pos(QPointF(float(start_x), float(start_y))) # Anchor: midbottom

        # Physics and state (common initialization)
        self.pos = QPointF(float(start_x), float(start_y)) # midbottom reference
        self.vel = QPointF(0.0, 0.0)
        enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)))
        self.acc = QPointF(0.0, enemy_gravity)
        self.facing_right = random.choice([True, False])
        self.on_ground = False

        self.ai_state = 'patrolling'
        self.patrol_target_x = float(start_x)

        self.is_attacking = False; self.attack_timer = 0
        self.attack_duration = int(getattr(C, 'ENEMY_ATTACK_STATE_DURATION', getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 500)))
        self.attack_type = 0; self.attack_cooldown_timer = 0
        self.post_attack_pause_timer = 0
        self.post_attack_pause_duration = int(getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200))

        self.is_taking_hit = False; self.hit_timer = 0
        self.hit_duration = int(getattr(C, 'ENEMY_HIT_STUN_DURATION', 300))
        self.hit_cooldown = int(getattr(C, 'ENEMY_HIT_COOLDOWN', 500))

        self.is_dead = False if self._valid_init else True
        self.death_animation_finished = False
        self.state_timer = 0

        self.max_health = int(getattr(C, 'ENEMY_MAX_HEALTH', 80))
        self.current_health = self.max_health if self._valid_init else 0
        
        # Default attack hitbox, QRectF for precision
        self.attack_hitbox = QRectF(0, 0, 50.0, 35.0) 

        try: # Standard height for camera or other logic
            if self.animations and self.animations.get('idle') and self.animations['idle'][0] and not self.animations['idle'][0].isNull():
                self.standard_height = float(self.animations['idle'][0].height())
            else: self.standard_height = 60.0
        except: self.standard_height = 60.0

        # Status effect flags & timers
        self.is_stomp_dying = False; self.stomp_death_start_time = 0
        self.original_stomp_death_image: Optional[QPixmap] = None
        self.original_stomp_facing_right = True

        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_aflame = False; self.aflame_timer_start = 0
        self.is_deflaming = False; self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.has_ignited_another_enemy_this_cycle = False

        self.is_petrified = False; self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right

        # Load Common Stone Assets
        stone_common_folder = os.path.join('characters', 'Stone')
        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))

        loaded_stone_frames = load_gif_frames(common_stone_png_path)
        if loaded_stone_frames and not self._is_placeholder_qpixmap(loaded_stone_frames[0]):
            self.stone_image_frame_original = loaded_stone_frames[0]
        else:
            warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __Stone.png. Placeholder.");
            self.stone_image_frame_original = self._create_placeholder_qpixmap(QColor(*C.GRAY), "Stone")
        self.stone_image_frame = self.stone_image_frame_original.copy()

        loaded_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
        if loaded_smashed_frames and not self._is_placeholder_qpixmap(loaded_smashed_frames[0]):
            self.stone_smashed_frames_original = loaded_smashed_frames
        else:
            warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __StoneSmashed.gif. Placeholder.");
            self.stone_smashed_frames_original = [self._create_placeholder_qpixmap(QColor(*C.DARK_GRAY), "Smash")]
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        if not self._valid_init:
            warning(f"EnemyBase (ID: {self.enemy_id}): Post-init check found _valid_init is False.")

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True # Null pixmap is definitely a problem
        if pixmap.size() == QSize(30,40): # Check against common placeholder size
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*C.RED) if hasattr(C, 'RED') else QColor(255,0,0)
                if color_at_origin == qcolor_red: return True
        return False

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        ts = C.TILE_SIZE if hasattr(C, 'TILE_SIZE') else 40
        width = ts; height = int(ts * 1.5)
        pixmap = QPixmap(width, height)
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        painter.setPen(QColor(*C.BLACK))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(10); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"ENEMY_BASE PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        """Updates self.rect based on self.image and a midbottom QPointF (self.pos by default)."""
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf else self.pos
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = target_pos.x() - img_w / 2.0
            rect_y = target_pos.y() - img_h
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif self.rect.isNull(): # Fallback if image is null and rect is also uninit
             self.rect.setRect(target_pos.x() - 15, target_pos.y() - 30, 30, 30) # Default small rect

    def alive(self) -> bool:
        # Basic alive check. More complex logic might involve sprite groups if used.
        return self._valid_init and not self.is_dead # Or a more specific check if needed

    def kill(self):
        # Placeholder for sprite removal. If using QGraphicsScene, this would remove the item.
        self._alive = False # Simple flag
        # If you have a list of active enemies, it would be removed from there.

    def reset(self):
        if not self._valid_init: # Attempt to re-validate if initial load failed
            # Try re-loading animations (or critical parts) if they were the cause
            if self.animations is None:
                 chosen_enemy_asset_folder = os.path.join('characters', self.color_name)
                 self.animations = load_all_player_animations(relative_asset_folder=chosen_enemy_asset_folder)
                 if self.animations is not None: # If animations loaded successfully this time
                     self._valid_init = True # Potentially valid now
                     # Re-initialize image from idle
                     idle_frames = self.animations.get('idle')
                     if idle_frames and idle_frames[0] and not idle_frames[0].isNull(): self.image = idle_frames[0]
                     else: self.image = self._create_placeholder_qpixmap(QColor(*C.BLUE), "ResetFail")
                 else:
                     warning(f"EnemyBase (ID: {self.enemy_id}): Still failed to load anims on reset. Remains invalid.")
                     self.is_dead = True; self.current_health = 0; return

        self.pos = self.spawn_pos.copy()
        self._update_rect_from_image_and_pos() # Update rect based on spawn_pos and current image
        self.vel = QPointF(0.0, 0.0)
        enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.8)))
        self.acc = QPointF(0.0, enemy_gravity)
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.hit_timer = 0; self.attack_timer = 0; self.attack_cooldown_timer = 0
        self.post_attack_pause_timer = 0
        self.facing_right = random.choice([True, False])
        self.on_ground = False
        self.ai_state = 'patrolling'
        # patrol_target_x will be set by AI handler or Enemy class

        self.is_stomp_dying = False; self.stomp_death_start_time = 0
        self.original_stomp_death_image = None; self.original_stomp_facing_right = self.facing_right
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_aflame = False; self.aflame_timer_start = 0
        self.is_deflaming = False; self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.has_ignited_another_enemy_this_cycle = False
        self.is_petrified = False; self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right

        # Ensure stone assets are reset to original (non-flipped) state
        self.stone_image_frame = self.stone_image_frame_original.copy()
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]
        
        self._alive = True # Make sure it's considered alive if reset
        self.state = 'idle'; self.current_frame = 0
        self.last_anim_update = get_current_ticks()
        debug(f"EnemyBase (ID: {self.enemy_id}): Core attributes reset.")

#################### END OF FILE: enemy_base.py ####################