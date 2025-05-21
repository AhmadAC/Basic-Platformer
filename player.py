# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes, collision heights, and
delegating state, animation, physics, collisions, input, combat, and network handling
to respective handler modules. Refactored for PySide6.
"""
# version 2.0.5 (Robust reset_state, safer attribute access, consistent QPointF usage)
# version 2.0.6 (Ensure _update_rect_from_image_and_pos handles QPointF correctly)
# version 2.0.7 (Corrected import for load_gif_frames)
# version 2.0.8 (Added TYPE_CHECKING for potential app_core imports to break cycles)

import os
import sys
import math
import time
from assets import load_all_player_animations, load_gif_frames, resource_path
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING # Added TYPE_CHECKING

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage, QKeyEvent
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

from utils import PrintLimiter
import constants as C
import config as game_config


# Handler modules
try:
    from player_state_handler import set_player_state
    from player_animation_handler import update_player_animation
    from player_movement_physics import update_player_core_logic
    from player_collision_handler import (
        check_player_platform_collisions, check_player_ladder_collisions,
        check_player_character_collisions, check_player_hazard_collisions
    )
    from player_input_handler import process_player_input_logic_pyside
    from player_combat_handler import (
        check_player_attack_collisions, player_take_damage,
        player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input
    )
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    from logger import info, debug, warning, error, critical
except ImportError as e:
    print(f"CRITICAL PLAYER INIT: Failed to import a module: {e}. Some functionalities might be impaired.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

# This is crucial for breaking circular imports if any player-related module
# (or this one) needs to type hint app_core.MainWindow
if TYPE_CHECKING:
    from app_core import MainWindow # Example: if MainWindow was needed for a type hint


_start_time_player_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_monotonic) * 1000)

class Player:
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x: float, start_y: float, player_id: int = 1,
                 initial_properties: Optional[Dict[str, Any]] = None):
        self.player_id = player_id
        self._valid_init = True
        self.properties = initial_properties if initial_properties is not None else {}
        self.control_scheme: Optional[str] = None
        self.joystick_id_idx: Optional[int] = None
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None

        self.initial_spawn_pos = QPointF(float(start_x), float(start_y))
        self.pos = QPointF(self.initial_spawn_pos)

        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        self.animations: Optional[Dict[str, List[QPixmap]]] = load_all_player_animations(relative_asset_folder=asset_folder)

        # Initialize all attributes
        self.image: Optional[QPixmap] = None
        self.rect = QRectF()
        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.state: str = 'idle'
        self.current_frame: int = 0
        self.last_anim_update: int = 0
        self._last_facing_right: bool = True
        self.facing_right: bool = True
        self.on_ground: bool = False
        self.on_ladder: bool = False
        self.can_grab_ladder: bool = False
        self.touching_wall: int = 0
        self.can_wall_jump: bool = False
        self.wall_climb_timer: int = 0
        self.is_crouching: bool = False
        self.is_dashing: bool = False; self.dash_timer: int = 0
        self.dash_duration: int = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling: bool = False; self.roll_timer: int = 0
        self.roll_duration: int = int(getattr(C, 'PLAYER_ROLL_DURATION', 300))
        self.is_sliding: bool = False; self.slide_timer: int = 0
        self.slide_duration: int = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))
        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = 300
        self.attack_type: int = 0
        self.can_combo: bool = False
        self.combo_window: int = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))
        self.wall_climb_duration: int = int(getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500))
        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600))
        self.is_dead: bool = False
        self.death_animation_finished: bool = False
        self.state_timer: int = 0
        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'PLAYER_MAX_HEALTH', 100)))
        self.current_health: int = self.max_health
        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0)
        self.standing_collision_height: float = 60.0
        self.crouching_collision_height: float = 30.0
        self.standard_height: float = 60.0
        self.is_trying_to_move_left: bool = False; self.is_trying_to_move_right: bool = False
        self.is_holding_climb_ability_key: bool = False
        self.is_holding_crouch_ability_key: bool = False
        self.fireball_cooldown_timer: int = 0; self.poison_cooldown_timer: int = 0
        self.bolt_cooldown_timer: int = 0; self.blood_cooldown_timer: int = 0
        self.ice_cooldown_timer: int = 0; self.shadow_cooldown_timer: int = 0
        self.grey_cooldown_timer: int = 0
        self.fireball_last_input_dir = QPointF(1.0, 0.0)
        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.is_frozen: bool = False; self.is_defrosting: bool = False
        self.frozen_effect_timer: int = 0
        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = True
        self.was_crouching_when_petrified: bool = False
        self._alive: bool = True

        if self.animations is None:
            critical(f"Player Init Error (ID: {self.player_id}): Failed loading animations from '{asset_folder}'. Player invalid.")
            self._valid_init = False
        else:
            try:
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                    self.standing_collision_height = float(idle_frames[0].height())
                else:
                    if Player.print_limiter.can_print(f"p_init_no_idle_h_{self.player_id}"):
                        warning(f"Player {self.player_id}: 'idle' animation for height not found. Defaulting standing height.")
                crouch_frames = self.animations.get('crouch')
                if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                    self.crouching_collision_height = float(crouch_frames[0].height())
                else:
                    self.crouching_collision_height = self.standing_collision_height / 2.0
                    if Player.print_limiter.can_print(f"p_init_no_crouch_h_{self.player_id}"):
                         warning(f"Player {self.player_id}: 'crouch' animation for height not found. Defaulting crouching height.")
                if self.standing_collision_height <= 1e-6 or self.crouching_collision_height <= 1e-6 or \
                   self.crouching_collision_height >= self.standing_collision_height:
                    critical(f"Player {self.player_id}: Invalid collision heights. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                    self._valid_init = False
            except Exception as e:
                error(f"Player {self.player_id} Error setting collision heights: {e}", exc_info=True)
                self._valid_init = False
            self.standard_height = self.standing_collision_height

        if self._valid_init:
            initial_anim_frames = self.animations.get('idle') # type: ignore
            if initial_anim_frames and initial_anim_frames[0] and not initial_anim_frames[0].isNull():
                self.image = initial_anim_frames[0]
            else:
                self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'RED', (255,0,0))), "NoIdle")
                warning(f"Player {self.player_id}: 'idle' frames missing. Using RED placeholder.")
                self._valid_init = False
        else:
            self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "AnimFail")

        self._update_rect_from_image_and_pos()
        self._assign_projectile_keys()
        self._init_stone_assets()

        self.is_dead = not self._valid_init
        self._alive = self._valid_init

        if not self._valid_init:
            self.current_health = 0
            warning(f"Player {self.player_id}: Initialization failed.")
        else:
            self.last_anim_update = get_current_ticks_monotonic()
            debug(f"Player {self.player_id} initialized successfully.")

    def _init_stone_assets(self):
        stone_common_folder = os.path.join('characters', 'Stone')
        qcolor_gray = QColor(*getattr(C,'GRAY', (128,128,128)))
        qcolor_dark_gray = QColor(*getattr(C,'DARK_GRAY', (50,50,50)))

        def load_or_placeholder(path, default_placeholder_color, default_placeholder_text, is_list=False):
            frames = load_gif_frames(resource_path(path))
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]
            
            anim_key = None
            if "Stone.png" in path: anim_key = 'petrified'
            elif "Smashed.gif" in path: anim_key = 'smashed'
            
            if anim_key and self.animations and self.animations.get(anim_key):
                anim_frames = self.animations.get(anim_key, [])
                if anim_frames and not self._is_placeholder_qpixmap(anim_frames[0]):
                    return anim_frames if is_list else anim_frames[0]
            
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        self.stone_image_frame_original = load_or_placeholder(os.path.join(stone_common_folder, '__Stone.png'), qcolor_gray, "StoneP")
        self.stone_image_frame = self.stone_image_frame_original.copy()

        self.stone_smashed_frames_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneSmashed.gif'), qcolor_dark_gray, "SmashP", is_list=True)
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        self.stone_crouch_image_frame_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneCrouch.png'), qcolor_gray, "SCrouchP")
        if self._is_placeholder_qpixmap(self.stone_crouch_image_frame_original) and not self._is_placeholder_qpixmap(self.stone_image_frame_original):
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy()
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()

        self.stone_crouch_smashed_frames_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneCrouchSmashed.gif'), qcolor_dark_gray, "SCSmashP", is_list=True)
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]) and \
           not (len(self.stone_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_smashed_frames_original[0])):
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original]
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]

    def _assign_projectile_keys(self):
        if self.player_id == 1:
            self.fireball_key_str = C.P1_FIREBALL_KEY; self.poison_key_str = C.P1_POISON_KEY
            self.bolt_key_str = C.P1_BOLT_KEY; self.blood_key_str = C.P1_BLOOD_KEY
            self.ice_key_str = C.P1_ICE_KEY; self.shadow_key_str = C.P1_SHADOW_PROJECTILE_KEY
            self.grey_key_str = C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2:
            self.fireball_key_str = C.P2_FIREBALL_KEY; self.poison_key_str = C.P2_POISON_KEY
            self.bolt_key_str = C.P2_BOLT_KEY; self.blood_key_str = C.P2_BLOOD_KEY
            self.ice_key_str = C.P2_ICE_KEY; self.shadow_key_str = C.P2_SHADOW_PROJECTILE_KEY
            self.grey_key_str = C.P2_GREY_PROJECTILE_KEY

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        h = self.standard_height if hasattr(self, 'standard_height') and self.standard_height > 10 else \
            (self.standing_collision_height if hasattr(self, 'standing_collision_height') and self.standing_collision_height > 10 else 60.0)
        w = h * 0.5
        pixmap = QPixmap(max(10, int(w)), max(10, int(h)))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        black_color_tuple = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color_tuple))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: error(f"PLAYER PlaceholderFontError: {e}", exc_info=True)
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40) or pixmap.size() == QSize(30,60) or pixmap.size() == QSize(10,10) :
            qimage = pixmap.toImage()
            if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_magenta = QColor(*getattr(C, 'MAGENTA', (255,0,255)))
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue or color_at_origin == qcolor_magenta:
                    return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF):
            warning(f"Player {self.player_id}: Invalid target_pos in _update_rect. Using self.pos or default.")
            target_pos = self.pos if isinstance(self.pos, QPointF) else QPointF(self.initial_spawn_pos)


        current_image = self.image
        if self.is_petrified and not self.is_stone_smashed:
            current_image = self.stone_crouch_image_frame if self.was_crouching_when_petrified else self.stone_image_frame
        elif self.is_stone_smashed and self.stone_smashed_frames:
            frame_idx = self.current_frame % len(self.stone_smashed_frames) if self.stone_smashed_frames else 0
            if self.was_crouching_when_petrified and self.stone_crouch_smashed_frames:
                current_image = self.stone_crouch_smashed_frames[frame_idx % len(self.stone_crouch_smashed_frames)]
            else:
                current_image = self.stone_smashed_frames[frame_idx]

        if current_image and not current_image.isNull():
            img_w, img_h = float(current_image.width()), float(current_image.height())
            rect_x = target_pos.x() - img_w / 2.0
            rect_y = target_pos.y() - img_h # Midbottom anchor
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif hasattr(self, 'rect'):
             h_fallback = self.standard_height if hasattr(self, 'standard_height') and self.standard_height > 1e-6 else 60.0
             w_fallback = h_fallback * 0.5
             self.rect.setRect(target_pos.x() - w_fallback / 2.0, target_pos.y() - h_fallback, w_fallback, h_fallback)

    def alive(self) -> bool: return self._alive
    def kill(self): self._alive = False; debug(f"Player {self.player_id} kill() called.")

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            return
        debug(f"Player {self.player_id} Log: Applying aflame effect.")
        self.is_aflame = True; self.is_deflaming = False
        self.aflame_timer_start = get_current_ticks_monotonic(); self.aflame_damage_last_tick = self.aflame_timer_start
        set_player_state(self, 'aflame_crouch' if self.is_crouching else 'aflame')
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            return
        debug(f"Player {self.player_id} Log: Applying freeze effect.")
        set_player_state(self, 'frozen')
        self.is_attacking = False; self.attack_type = 0
        self.vel = QPointF(0,0); self.acc.setX(0)

    def update_status_effects(self, current_time_ms: int):
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                set_player_state(self, 'deflame_crouch' if self.is_crouching else 'deflame')
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
                self.aflame_damage_last_tick = current_time_ms
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
                set_player_state(self, 'crouch' if self.is_crouching else ('idle' if self.on_ground else 'fall'))

        if self.is_frozen:
            if current_time_ms - self.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
                set_player_state(self, 'defrost')
        elif self.is_defrosting:
            if current_time_ms - self.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
                set_player_state(self, 'idle' if self.on_ground else 'fall')

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified): return
        debug(f"Player {self.player_id}: Petrifying.")
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        self.is_petrified = True; self.is_stone_smashed = False; self.is_dead = True
        self.current_health = 0; self.vel = QPointF(0,0); self.acc = QPointF(0,0)
        self.is_attacking = False; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        self.is_aflame = False; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False
        self.death_animation_finished = True
        set_player_state(self, 'petrified')

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            debug(f"Player {self.player_id}: Smashing petrification.")
            self.is_stone_smashed = True; self.stone_smashed_timer_start = get_current_ticks_monotonic()
            self.death_animation_finished = False
            set_player_state(self, 'smashed')

    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any]):
        if self.game_elements_ref_for_projectiles is None: self.game_elements_ref_for_projectiles = {}
        self.game_elements_ref_for_projectiles["projectiles_list"] = projectile_list
        self.game_elements_ref_for_projectiles["all_renderable_objects"] = all_elements_list
        if "platforms_list" not in self.game_elements_ref_for_projectiles:
            warning(f"Player {self.player_id}: 'platforms_list' missing in game_elements_ref_for_projectiles. Projectile collisions with platforms might fail.")


    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True
        current_feet_y = self.rect.bottom()
        current_center_x = self.rect.center().x()
        standing_width = self.rect.width()
        if self.animations and self.animations.get('idle') and self.animations['idle'][0]:
            standing_width = float(self.animations['idle'][0].width())
        potential_standing_rect = QRectF(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.moveBottom(current_feet_y)
        potential_standing_rect.moveCenter(QPointF(current_center_x, potential_standing_rect.center().y()))

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               potential_standing_rect.intersects(platform_obj.rect):
                if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                   platform_obj.rect.top() < self.rect.top():
                    return False
        return True

    # Delegated methods
    def set_state(self, new_state: str): set_player_state(self, new_state)
    def animate(self): update_player_animation(self)

    def process_input(self,
                      qt_keys_held_snapshot: Dict[Qt.Key, bool],
                      qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
                      platforms_list: List[Any],
                      joystick_data_for_handler: Optional[Dict[str, Any]] = None
                      ):
        active_mappings = {}
        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_pygame_"):
            active_mappings = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS if game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS else game_config.DEFAULT_PYGAME_JOYSTICK_MAPPINGS
        else:
            active_mappings = game_config.P1_MAPPINGS if self.player_id == 1 else game_config.P2_MAPPINGS

        return process_player_input_logic_pyside(self, qt_keys_held_snapshot, qt_key_event_data_this_frame,
                                                 active_mappings, platforms_list, joystick_data_for_handler)

    def _generic_fire_projectile(self, projectile_class, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting: return
        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_print(f"proj_fire_no_game_elements_{self.player_id}"):
                warning(f"Player {self.player_id}: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return
        projectiles_list_ref = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref = self.game_elements_ref_for_projectiles.get("all_renderable_objects")
        if projectiles_list_ref is None or all_renderables_ref is None:
            if Player.print_limiter.can_print(f"proj_fire_list_missing_{self.player_id}"):
                warning(f"Player {self.player_id}: Projectile or renderable list missing in ref. Cannot fire {projectile_config_name}.")
            return

        current_time_ms = get_current_ticks_monotonic()
        last_fire_time = getattr(self, cooldown_attr_name, 0)
        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)
            if self.rect.isNull(): self._update_rect_from_image_and_pos()
            if self.rect.isNull(): error(f"Player {self.player_id}: Rect is null, cannot fire."); return

            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6):
                 aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0)
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0))
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()):
                offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0
            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length
            spawn_x += norm_x * offset_dist; spawn_y += norm_y * offset_dist
            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles
            projectiles_list_ref.append(new_projectile); all_renderables_ref.append(new_projectile)
            if projectile_config_name == 'blood' and self.current_health > 0:
                self.current_health -= self.current_health * 0.05
                if self.current_health <= 0 and not self.is_dead: self.set_state('death')

    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')

    def check_attack_collisions(self, list_of_targets: List[Any]): check_player_attack_collisions(self, list_of_targets)
    def take_damage(self, damage_amount_taken: int): player_take_damage(self, damage_amount_taken)
    def self_inflict_damage(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)

    def get_network_data(self) -> Dict[str, Any]: return get_player_network_data(self)
    def set_network_data(self, received_network_data: Dict[str, Any]): set_player_network_data(self, received_network_data)
    def handle_network_input(self, network_input_data_dict: Dict[str, Any]): handle_player_network_input(self, network_input_data_dict)

    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]) -> bool: return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any], hazards_list: List[Any],
               other_players_list: List[Any], enemies_list: List[Any]):
        if not self._valid_init or not self._alive: return

        current_time_ms = get_current_ticks_monotonic()
        self.update_status_effects(current_time_ms)

        if self.is_stone_smashed:
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                self.kill(); return
            self.animate(); return
        if self.is_petrified:
            self.vel = QPointF(0,0); self.acc = QPointF(0,0)
            self.animate(); return

        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)

    def reset_state(self, spawn_position_tuple: Optional[Tuple[float, float]]):
        if not self._valid_init and self.animations is None:
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True
                try:
                    idle_f = self.animations.get('idle')
                    self.standing_collision_height = float(idle_f[0].height()) if idle_f and idle_f[0] and not idle_f[0].isNull() else 60.0
                    crouch_f = self.animations.get('crouch')
                    self.crouching_collision_height = float(crouch_f[0].height()) if crouch_f and crouch_f[0] and not crouch_f[0].isNull() else self.standing_collision_height / 2.0
                    if self.standing_collision_height <= 1e-6 or self.crouching_collision_height <= 1e-6 or self.crouching_collision_height >= self.standing_collision_height: self._valid_init = False
                    self.standard_height = self.standing_collision_height
                    initial_idle_frames_reset = self.animations.get('idle')
                    if initial_idle_frames_reset and initial_idle_frames_reset[0] and not initial_idle_frames_reset[0].isNull():
                        self.image = initial_idle_frames_reset[0]
                    else: self.image = self._create_placeholder_qpixmap(QColor(*getattr(C,'RED',(255,0,0))), "RstIdleFail"); self._valid_init = False
                except Exception as e_anim_reset:
                    error(f"Player {self.player_id} error re-init anims on reset: {e_anim_reset}", exc_info=True); self._valid_init = False
            else:
                warning(f"Player {self.player_id}: Animations still failed to load on reset. Player remains invalid.")

        if not self._valid_init:
            self.is_dead = True; self._alive = False; self.current_health = 0
            self.pos = QPointF(self.initial_spawn_pos) if self.initial_spawn_pos else QPointF(50,500)
            self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, 0.0)
            if self.image is None: self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'MAGENTA', (255,0,255))), "NoImgRst")
            self._update_rect_from_image_and_pos()
            return

        if spawn_position_tuple is not None and len(spawn_position_tuple) == 2:
            try:
                self.pos = QPointF(float(spawn_position_tuple[0]), float(spawn_position_tuple[1]))
            except (TypeError, ValueError) as e_pos:
                warning(f"Player {self.player_id}: Invalid spawn_position_tuple '{spawn_position_tuple}' on reset: {e_pos}. Using initial_spawn_pos {self.initial_spawn_pos}.")
                self.pos = QPointF(self.initial_spawn_pos)
        else:
            self.pos = QPointF(self.initial_spawn_pos)
            if spawn_position_tuple is not None :
                warning(f"Player {self.player_id}: reset_state called with invalid spawn_position_tuple '{spawn_position_tuple}'. Using initial_spawn_pos {self.pos}.")


        self._update_rect_from_image_and_pos()

        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True; self.on_ground = False
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;
        self.fireball_cooldown_timer = 0; self.poison_cooldown_timer = 0; self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0; self.ice_cooldown_timer = 0; self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0; self.fireball_last_input_dir = QPointF(1.0, 0.0)
        self.is_aflame = False; self.aflame_timer_start = 0; self.is_deflaming = False
        self.deflame_timer_start = 0; self.aflame_damage_last_tick = 0
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_petrified = False; self.is_stone_smashed = False; self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right; self.was_crouching_when_petrified = False
        self._init_stone_assets()
        self._alive = True

        set_player_state(self, 'idle')
        info(f"Player {self.player_id} reset_state complete. State: {self.state}, Pos: ({self.pos.x():.1f},{self.pos.y():.1f})")

    def draw_pyside(self, painter: QPainter, camera: Any):
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return

        should_draw = self.alive() or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      self.is_petrified

        if not should_draw:
            return

        screen_rect_qrectf = camera.apply(self.rect)

        if painter.window().intersects(screen_rect_qrectf.toRect()):
            painter.drawPixmap(screen_rect_qrectf.topLeft(), self.image)

            if getattr(C, "DRAW_PLAYER_ABOVE_HEALTH_BAR", False) and self.current_health < self.max_health and not self.is_dead:
                # Health bar drawing logic would go here if re-enabled
                pass