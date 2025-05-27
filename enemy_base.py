#################### START OF FILE: enemy_base.py ####################

# enemy_base.py
# -*- coding: utf-8 -*-
"""
Defines the EnemyBase class, the foundational class for enemies.
Handles core attributes, animation loading, and common assets for PySide6.
Now uses load_enemy_animations.
MODIFIED: Added zapped attributes.
MODIFIED: Added overall_fire_effect_start_time for 5s fire cycle management.
MODIFIED: Zapped GIF path added.
"""
# version 2.0.8 (Zapped GIF path addition)

import os
import random
import time
from typing import List, Optional, Any, Dict, Tuple

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

import constants as C
from assets import load_enemy_animations, load_gif_frames, resource_path # Corrected import from previous step

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_BASE: logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}", *args)
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}", *args)
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}", *args)
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}", *args)
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}", *args)

_start_time_enemy_base_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_base_monotonic) * 1000)


class EnemyBase:
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, color_name: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None):

        self.spawn_pos = QPointF(float(start_x), float(start_y))
        self.patrol_area = patrol_area
        self.enemy_id = enemy_id if enemy_id is not None else id(self)
        self._valid_init = True
        self._alive = True
        self.final_asset_color_name = "unknown"
        self.properties = properties if properties is not None else {}

        character_base_asset_folder = 'characters'
        available_enemy_asset_folders = ['green', 'pink', 'purple', 'gray', 'yellow', 'orange']

        processed_color_input = color_name
        if isinstance(processed_color_input, str) and processed_color_input.startswith("enemy_"):
            processed_color_input = processed_color_input.replace("enemy_", "", 1)

        if processed_color_input and processed_color_input in available_enemy_asset_folders:
            self.final_asset_color_name = processed_color_input
        elif color_name:
            warning(f"EnemyBase Warning (ID: {self.enemy_id}): Processed color '{processed_color_input}' (from input '{color_name}') not in {available_enemy_asset_folders}. Using random.")
            self.final_asset_color_name = random.choice(available_enemy_asset_folders) if available_enemy_asset_folders else "unknown"
        else:
            self.final_asset_color_name = random.choice(available_enemy_asset_folders) if available_enemy_asset_folders else "unknown"

        if self.final_asset_color_name == "unknown":
            if available_enemy_asset_folders:
                self.final_asset_color_name = available_enemy_asset_folders[0]
                warning(f"EnemyBase Warning (ID: {self.enemy_id}): color_name resolved to 'unknown', falling back to first available: '{self.final_asset_color_name}'.")
            else:
                critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}): No available enemy asset folders to choose from. Animation loading will fail.")
                self._valid_init = False
        
        self.color_name = self.final_asset_color_name # Store the chosen color_name
        debug(f"EnemyBase (ID: {self.enemy_id}): Initializing with final_asset_color_name: '{self.final_asset_color_name}' (input was '{color_name}').")

        self.animations: Optional[Dict[str, List[QPixmap]]] = None
        if self._valid_init and self.final_asset_color_name != "unknown":
            chosen_enemy_asset_folder = os.path.join(character_base_asset_folder, self.final_asset_color_name)
            debug(f"EnemyBase (ID: {self.enemy_id}): Loading ENEMY animations from: '{chosen_enemy_asset_folder}'")
            self.animations = load_enemy_animations(relative_asset_folder=chosen_enemy_asset_folder)

        self.image: Optional[QPixmap] = None
        self.rect = QRectF()

        if self.animations is None:
            critical_msg_suffix = f"from '{chosen_enemy_asset_folder}'" if self.final_asset_color_name != "unknown" else "(no valid color/asset path)"
            critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, FinalAssetColor: {self.final_asset_color_name}): Failed loading ENEMY animations {critical_msg_suffix}.")
            blue_color = getattr(C, 'BLUE', (0, 0, 255))
            self.image = self._create_placeholder_qpixmap(QColor(*blue_color), f"AnimFail-{self.final_asset_color_name[:3]}")
            self._update_rect_from_image_and_pos(QPointF(float(start_x), float(start_y)))
            self._valid_init = False; self._alive = False; self.is_dead = True
            self.pos = QPointF(float(start_x), float(start_y)); self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, 0.0)
            self.state = 'idle'; self.current_frame = 0; self.last_anim_update = 0
            self.facing_right = True; self.on_ground = False
            self.current_health = 0; self.max_health = 0
        else:
            self._last_facing_right_visual: bool = True # Initialize for animation handler
            self._last_state_for_debug: str = "init"
            self.state: str = 'idle'
            self.current_frame: int = 0
            self.last_anim_update: int = get_current_ticks_monotonic()

            initial_idle_animation = self.animations.get('idle')
            if not initial_idle_animation or not initial_idle_animation[0] or initial_idle_animation[0].isNull():
                 warning(f"EnemyBase Warning (ID: {self.enemy_id}, FinalAssetColor: {self.final_asset_color_name}): ENEMY 'idle' animation missing/empty. Attempting fallback.")
                 first_anim_key = next((key for key, anim_list in self.animations.items() if anim_list and anim_list[0] and not anim_list[0].isNull()), None)
                 initial_idle_animation = self.animations.get(first_anim_key) if first_anim_key else None

            if initial_idle_animation and initial_idle_animation[0] and not initial_idle_animation[0].isNull():
                self.image = initial_idle_animation[0]
            else:
                blue_color = getattr(C, 'BLUE', (0, 0, 255))
                self.image = self._create_placeholder_qpixmap(QColor(*blue_color), f"NoIdle-{self.final_asset_color_name[:3]}")
                critical(f"EnemyBase CRITICAL (ID: {self.enemy_id}, FinalAssetColor: {self.final_asset_color_name}): No suitable initial ENEMY animation. Enemy invalid.")
                self._valid_init = False; self._alive = False; self.is_dead = True

            self._update_rect_from_image_and_pos(QPointF(float(start_x), float(start_y)))
        
        self.pos = QPointF(float(start_x), float(start_y))
        self.vel = QPointF(0.0, 0.0)
        enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.acc = QPointF(0.0, enemy_gravity)
        self.facing_right: bool = random.choice([True, False])
        self.on_ground: bool = False

        self.ai_state: str = 'patrolling'
        self.patrol_target_x: float = float(start_x)

        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = int(getattr(C, 'ENEMY_ATTACK_STATE_DURATION', getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 500)))
        self.attack_type: int = 0; self.attack_cooldown_timer: int = 0
        self.post_attack_pause_timer: int = 0
        self.post_attack_pause_duration: int = int(getattr(C, 'ENEMY_POST_ATTACK_PAUSE_DURATION', 200))

        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'ENEMY_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'ENEMY_HIT_COOLDOWN', 500))

        self.is_dead: bool = not self._valid_init
        self.death_animation_finished: bool = False
        self.state_timer: int = 0 # General timer for states

        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'ENEMY_MAX_HEALTH', 80)))
        self.current_health: int = self.max_health if self._valid_init else 0

        self.attack_hitbox = QRectF(0, 0, 50.0, 35.0) # Default, adjust as needed

        try:
            if self.animations and self.animations.get('idle') and self.animations['idle'][0] and not self.animations['idle'][0].isNull():
                self.standard_height: float = float(self.animations['idle'][0].height())
            else: self.standard_height: float = 60.0
        except Exception: self.standard_height: float = 60.0

        # Status Effect Flags & Timers
        self.is_stomp_dying: bool = False; self.stomp_death_start_time: int = 0
        self.original_stomp_death_image: Optional[QPixmap] = None
        self.original_stomp_facing_right: bool = self.facing_right

        self.is_frozen: bool = False; self.is_defrosting: bool = False; self.frozen_effect_timer: int = 0
        
        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.has_ignited_another_enemy_this_cycle: bool = False
        self.overall_fire_effect_start_time: int = 0

        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = self.facing_right
        
        self.is_zapped: bool = False
        self.zapped_timer_start: int = 0
        self.zapped_damage_last_tick: int = 0
        self.zapped_gif_path = os.path.join(character_base_asset_folder, self.final_asset_color_name, "__Zapped.gif") # MODIFIED: Path to zapped GIF


        gray_color = getattr(C, 'GRAY', (128, 128, 128))
        dark_gray_color = getattr(C, 'DARK_GRAY', (50, 50, 50))
        self.stone_image_frame_original: QPixmap = self._create_placeholder_qpixmap(QColor(*gray_color), "Stone")
        self.stone_smashed_frames_original: List[QPixmap] = [self._create_placeholder_qpixmap(QColor(*dark_gray_color), "Smash")]

        if self._valid_init:
            stone_common_folder = os.path.join('characters', 'Stone')
            common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
            common_stone_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))

            loaded_stone_frames = load_gif_frames(common_stone_png_path)
            if loaded_stone_frames and not self._is_placeholder_qpixmap(loaded_stone_frames[0]):
                self.stone_image_frame_original = loaded_stone_frames[0]
            else: warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __Stone.png. Using placeholder.")

            loaded_smashed_frames = load_gif_frames(common_stone_smashed_gif_path)
            if loaded_smashed_frames and not self._is_placeholder_qpixmap(loaded_smashed_frames[0]):
                self.stone_smashed_frames_original = loaded_smashed_frames
            else: warning(f"EnemyBase (ID: {self.enemy_id}): Failed to load common __StoneSmashed.gif. Using placeholder.")

        self.stone_image_frame: QPixmap = self.stone_image_frame_original.copy()
        self.stone_smashed_frames: List[QPixmap] = [f.copy() for f in self.stone_smashed_frames_original]

        if not self._valid_init:
            warning(f"EnemyBase (ID: {self.enemy_id}): Initialization completed with _valid_init as False.")

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40): # Common placeholder size used in assets.py
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
        width = base_tile_size
        height = int(base_tile_size * 1.5) 

        pixmap = QPixmap(max(1, width), max(1, height))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        black_color_tuple = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color_tuple))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1)) 
        try:
            font = QFont(); font.setPointSize(max(6, int(height / 4))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"ENEMY_BASE PlaceholderFontError: {e}") 
        painter.end()
        return pixmap

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF): 
            target_pos = self.pos if isinstance(self.pos, QPointF) else self.spawn_pos

        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = target_pos.x() - img_w / 2.0
            rect_y = target_pos.y() - img_h 
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif hasattr(self, 'rect'): 
             fallback_h = self.standard_height if hasattr(self, 'standard_height') and self.standard_height > 10 else 60.0
             fallback_w = fallback_h * 0.6 
             self.rect.setRect(target_pos.x() - fallback_w / 2.0,
                               target_pos.y() - fallback_h,
                               fallback_w, fallback_h)

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        debug(f"EnemyBase (ID: {self.enemy_id}): kill() called. Setting _alive to False.")
        self._alive = False

    def reset(self):
        # Attempt to re-load animations if they failed initially
        if not self._valid_init and self.animations is None and self.final_asset_color_name != "unknown":
             chosen_enemy_asset_folder = os.path.join('characters', self.final_asset_color_name)
             self.animations = load_enemy_animations(relative_asset_folder=chosen_enemy_asset_folder)
             if self.animations is not None:
                 self._valid_init = True
                 idle_frames = self.animations.get('idle')
                 if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                     self.image = idle_frames[0]
                 else:
                     blue_color = getattr(C, 'BLUE', (0,0,255))
                     self.image = self._create_placeholder_qpixmap(QColor(*blue_color), "RstFail")
             else:
                 warning(f"EnemyBase (ID: {self.enemy_id}): Still failed to load anims on reset. Remains invalid.")
                 self.is_dead = True; self.current_health = 0; self._alive = False; return

        if not self._valid_init:
            self.is_dead = True; self.current_health = 0; self._alive = False
            self.pos = QPointF(self.spawn_pos) if self.spawn_pos else QPointF(0,0)
            self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, 0.0)
            if self.image is None: self.image = self._create_placeholder_qpixmap(QColor(255,0,255), "NoImgRst")
            self._update_rect_from_image_and_pos()
            return

        self.pos = QPointF(self.spawn_pos)
        self._update_rect_from_image_and_pos()

        self.vel = QPointF(0.0, 0.0)
        enemy_gravity = float(getattr(C, 'ENEMY_GRAVITY', getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.acc = QPointF(0.0, enemy_gravity)
        self.current_health = self.max_health
        self.is_dead = False
        self.death_animation_finished = False
        self.is_taking_hit = False
        self.is_attacking = False
        self.attack_type = 0
        self.hit_timer = 0
        self.attack_timer = 0
        self.attack_cooldown_timer = 0
        self.post_attack_pause_timer = 0
        self.facing_right = random.choice([True, False])
        self.on_ground = False
        self.ai_state = 'patrolling'
        self.patrol_target_x = self.spawn_pos.x()

        # Reset status effects
        self.is_stomp_dying = False; self.stomp_death_start_time = 0
        self.original_stomp_death_image = None; self.original_stomp_facing_right = self.facing_right
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_aflame = False; self.aflame_timer_start = 0
        self.is_deflaming = False; self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.has_ignited_another_enemy_this_cycle = False
        self.overall_fire_effect_start_time = 0
        self.is_petrified = False; self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right
        
        self.is_zapped = False; self.zapped_timer_start = 0; self.zapped_damage_last_tick = 0

        self.stone_image_frame = self.stone_image_frame_original.copy()
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]
        
        self._alive = True
        self.state = 'idle'
        self.current_frame = 0
        self.last_anim_update = get_current_ticks_monotonic()
        debug(f"EnemyBase (ID: {self.enemy_id}): Core attributes reset.")

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return

        should_draw = self._alive or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      self.is_petrified 

        if not should_draw:
            return

        screen_rect_qrectf = camera.apply(self.rect) 
        
        if painter.window().intersects(screen_rect_qrectf.toRect()):
            painter.drawPixmap(screen_rect_qrectf.topLeft(), self.image)

            if getattr(C, "DRAW_ENEMY_ABOVE_HEALTH_BAR", False) and \
               self.current_health < self.max_health and not self.is_dead and not self.is_petrified:
                
                hb_w = float(getattr(C, 'HEALTH_BAR_WIDTH', 50.0))
                hb_h = float(getattr(C, 'HEALTH_BAR_HEIGHT', 8.0))
                hb_offset_above = float(getattr(C, 'HEALTH_BAR_OFFSET_ABOVE', 5.0))
                
                hb_x = screen_rect_qrectf.center().x() - hb_w / 2.0
                hb_y = screen_rect_qrectf.top() - hb_h - hb_offset_above
                
                try:
                    from game_ui import draw_health_bar_qt
                    draw_health_bar_qt(painter, hb_x, hb_y, hb_w, hb_h, 
                                       float(self.current_health), float(self.max_health))
                except ImportError:
                    if hasattr(self, 'print_limiter') and self.print_limiter.can_log(f"draw_health_bar_missing_{self.enemy_id}"):
                        warning(f"EnemyBase {self.enemy_id}: draw_health_bar_qt not found, cannot draw health bar.")

#################### END OF FILE: enemy_base.py ####################