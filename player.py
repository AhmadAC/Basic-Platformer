# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes, collision heights, and
delegating state, animation, physics, collisions, input, combat, and network handling
to respective handler modules. Refactored for PySide6.
"""
# version 2.0.9 (Robust reset, refined rect updates, fixed projectile imports)

import os
import sys
import math
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage, QKeyEvent
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game-specific imports
from assets import load_all_player_animations, load_gif_frames, resource_path
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
    # CORRECTED IMPORT NAME HERE:
    from player_input_handler import process_player_input_logic
    from player_combat_handler import (
        check_player_attack_collisions, player_take_damage,
        player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input
    )
    # ADDED PROJECTILE IMPORTS HERE:
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
    from logger import info, debug, warning, error, critical
except ImportError as e:
    print()


if TYPE_CHECKING:
    from app_core import MainWindow


_start_time_player_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_monotonic) * 1000)

class Player:
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x: float, start_y: float, player_id: int = 1,
                 initial_properties: Optional[Dict[str, Any]] = None):
        self.player_id = player_id
        self._valid_init = True # Assume valid until a critical failure
        self.properties = initial_properties if initial_properties is not None else {}
        self.control_scheme: Optional[str] = None
        self.joystick_id_idx: Optional[int] = None # Pygame joystick index
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None # For firing projectiles

        self.initial_spawn_pos = QPointF(float(start_x), float(start_y))
        self.pos = QPointF(self.initial_spawn_pos) # Current mid-bottom position

        # --- Animation Loading ---
        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        self.animations: Optional[Dict[str, List[QPixmap]]] = None # Initialize before trying to load
        try:
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
        except Exception as e_anim_load:
            critical(f"Player {self.player_id}: Exception during load_all_player_animations from '{asset_folder}': {e_anim_load}", exc_info=True)
            self._valid_init = False

        if self.animations is None:
            critical(f"Player Init Error (ID: {self.player_id}): Failed loading animations from '{asset_folder}'. Player will be invalid.")
            self._valid_init = False

        # --- Core Attributes (Initialize all to prevent AttributeErrors) ---
        self.image: Optional[QPixmap] = None
        self.rect = QRectF() # Current bounding box
        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))

        self.state: str = 'idle'
        self.current_frame: int = 0
        self.last_anim_update: int = 0
        self._last_facing_right: bool = True # For animation flipping optimization
        self.facing_right: bool = True

        # Collision & Movement State
        self.on_ground: bool = False
        self.on_ladder: bool = False
        self.can_grab_ladder: bool = False
        self.touching_wall: int = 0 # -1 for left, 1 for right, 0 for none
        self.can_wall_jump: bool = False
        self.wall_climb_timer: int = 0 # Timestamp of when wall climb started

        # Action States
        self.is_crouching: bool = False
        self.is_dashing: bool = False; self.dash_timer: int = 0
        self.dash_duration: int = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling: bool = False; self.roll_timer: int = 0
        self.roll_duration: int = int(getattr(C, 'PLAYER_ROLL_DURATION', 300)) # Increased from 300
        self.is_sliding: bool = False; self.slide_timer: int = 0
        self.slide_duration: int = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        # Combat States
        self.is_attacking: bool = False; self.attack_timer: int = 0
        self.attack_duration: int = int(getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)) # Default
        self.attack_type: int = 0 # 1 for attack1, 2 for attack2, 3 for combo, 4 for crouch_attack
        self.can_combo: bool = False
        self.combo_window: int = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))
        self.is_taking_hit: bool = False; self.hit_timer: int = 0
        self.hit_duration: int = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown: int = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600))

        # Health & Death
        self.is_dead: bool = False
        self.death_animation_finished: bool = False
        self.max_health: int = int(self.properties.get("max_health", getattr(C, 'PLAYER_MAX_HEALTH', 100)))
        self.current_health: int = self.max_health
        self._alive: bool = True # Primary liveness flag, managed by self.kill() and reset

        # Dimensions and Hitboxes
        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0) # Relative to player, adjusted in combat_handler
        self.standing_collision_height: float = 60.0 # Default, updated from anims
        self.crouching_collision_height: float = 30.0 # Default, updated from anims
        self.standard_height: float = 60.0 # Used for consistent reference

        # Input Intent (set by input handler)
        self.is_trying_to_move_left: bool = False
        self.is_trying_to_move_right: bool = False
        self.is_holding_climb_ability_key: bool = False
        self.is_holding_crouch_ability_key: bool = False

        # Projectile Cooldowns & Aiming
        self.fireball_cooldown_timer: int = 0; self.poison_cooldown_timer: int = 0
        self.bolt_cooldown_timer: int = 0; self.blood_cooldown_timer: int = 0
        self.ice_cooldown_timer: int = 0; self.shadow_cooldown_timer: int = 0
        self.grey_cooldown_timer: int = 0
        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aim right

        # Status Effects
        self.is_aflame: bool = False; self.aflame_timer_start: int = 0
        self.is_deflaming: bool = False; self.deflame_timer_start: int = 0
        self.aflame_damage_last_tick: int = 0
        self.is_frozen: bool = False; self.is_defrosting: bool = False
        self.frozen_effect_timer: int = 0
        self.is_petrified: bool = False; self.is_stone_smashed: bool = False
        self.stone_smashed_timer_start: int = 0
        self.facing_at_petrification: bool = True # Direction when petrified
        self.was_crouching_when_petrified: bool = False

        self.state_timer: int = 0 # Timestamp of last state change

        # --- Post-Animation Load Setup ---
        if self._valid_init and self.animations: # Only if animations loaded
            try:
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                    self.standing_collision_height = float(idle_frames[0].height())
                else:
                    if Player.print_limiter.can_print(f"p_init_no_idle_h_{self.player_id}"):
                        warning(f"Player {self.player_id}: 'idle' animation for height not found. Using default: {self.standing_collision_height}.")
                
                crouch_frames = self.animations.get('crouch')
                if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                    self.crouching_collision_height = float(crouch_frames[0].height())
                else:
                    self.crouching_collision_height = self.standing_collision_height / 2.0
                    if Player.print_limiter.can_print(f"p_init_no_crouch_h_{self.player_id}"):
                         warning(f"Player {self.player_id}: 'crouch' animation for height not found. Defaulting: {self.crouching_collision_height}.")
                
                if self.standing_collision_height <= 1e-6 or self.crouching_collision_height <= 1e-6 or \
                   self.crouching_collision_height >= self.standing_collision_height:
                    critical(f"Player {self.player_id}: Invalid collision heights after anim load. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                    self._valid_init = False # Animation data led to invalid heights
                self.standard_height = self.standing_collision_height

                initial_idle_frames = self.animations.get('idle')
                if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
                    self.image = initial_idle_frames[0]
                else: # Critical if no idle animation
                    self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'RED', (255,0,0))), "NoIdle")
                    warning(f"Player {self.player_id}: 'idle' frames missing or invalid. Using RED placeholder. Player invalid.")
                    self._valid_init = False
            except Exception as e_col_h:
                error(f"Player {self.player_id} Exception setting collision heights from animations: {e_col_h}", exc_info=True)
                self._valid_init = False
        elif not self._valid_init: # If _valid_init was already false due to animation load failure
             self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'BLUE', (0,0,255))), "AnimFail")


        self._update_rect_from_image_and_pos() # Initial rect based on image and pos
        self._assign_projectile_keys()
        self._init_stone_assets() # Load stone assets

        if not self._valid_init:
            self.is_dead = True
            self._alive = False
            self.current_health = 0
            warning(f"Player {self.player_id}: Initialization failed (likely animation or height issue).")
        else:
            self.last_anim_update = get_current_ticks_monotonic()
            debug(f"Player {self.player_id} initialized successfully. StandH:{self.standing_collision_height:.1f}, CrouchH:{self.crouching_collision_height:.1f}")

    def _init_stone_assets(self):
        # This method should be mostly the same as your provided version, ensure paths and fallbacks are robust.
        stone_common_folder = os.path.join('characters', 'Stone')
        qcolor_gray = QColor(*getattr(C,'GRAY', (128,128,128)))
        qcolor_dark_gray = QColor(*getattr(C,'DARK_GRAY', (50,50,50)))

        def load_or_placeholder(path_suffix, default_placeholder_color, default_placeholder_text, is_list=False):
            full_path = resource_path(os.path.join(stone_common_folder, path_suffix))
            frames = load_gif_frames(full_path)
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]
            
            # Fallback logic: Check player's own animations for 'petrified' or 'smashed'
            anim_key_fallback: Optional[str] = None
            if "Stone.png" in path_suffix: anim_key_fallback = 'petrified'
            elif "Smashed.gif" in path_suffix: anim_key_fallback = 'smashed'
            
            if anim_key_fallback and self.animations and self.animations.get(anim_key_fallback):
                anim_frames_player = self.animations.get(anim_key_fallback, [])
                if anim_frames_player and not self._is_placeholder_qpixmap(anim_frames_player[0]):
                    debug(f"Player {self.player_id} StoneAsset: Using player's own '{anim_key_fallback}' anim for stone effect.")
                    return anim_frames_player if is_list else anim_frames_player[0]
            
            # If player's anims also don't work, then create placeholder
            warning(f"Player {self.player_id} StoneAsset: Failed to load '{path_suffix}' and no suitable player anim. Using placeholder.")
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        self.stone_image_frame_original = load_or_placeholder('__Stone.png', qcolor_gray, "StoneP")
        self.stone_image_frame = self.stone_image_frame_original.copy()

        self.stone_smashed_frames_original = load_or_placeholder('__StoneSmashed.gif', qcolor_dark_gray, "SmashP", is_list=True)
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        self.stone_crouch_image_frame_original = load_or_placeholder('__StoneCrouch.png', qcolor_gray, "SCrouchP")
        if self._is_placeholder_qpixmap(self.stone_crouch_image_frame_original) and not self._is_placeholder_qpixmap(self.stone_image_frame_original):
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy() # Fallback to standing stone
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()

        self.stone_crouch_smashed_frames_original = load_or_placeholder('__StoneCrouchSmashed.gif', qcolor_dark_gray, "SCSmashP", is_list=True)
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]) and \
           not (len(self.stone_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_smashed_frames_original[0])):
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original] # Fallback to standing smashed
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]


    def _assign_projectile_keys(self):
        # (This method seems fine as is)
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
        # Add for P3, P4 if needed, using C.P3_... , C.P4_...

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        # Use current collision height for placeholder if available, else standard_height
        h = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
        if h <= 1e-6 : h = self.standard_height # Fallback if collision heights are zero
        if h <= 1e-6 : h = 60.0 # Absolute fallback
        
        w = h * 0.5 # Typical player aspect ratio
        pixmap = QPixmap(max(10, int(w)), max(10, int(h)))
        pixmap.fill(q_color)
        painter = QPainter(pixmap)
        black_color_tuple = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color_tuple))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: error(f"PLAYER PlaceholderFontError (P{self.player_id}): {e}", exc_info=True)
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        # (This method seems fine as is)
        if pixmap.isNull(): return True
        # Check for specific placeholder sizes and colors (adapt if your placeholders differ)
        if pixmap.size() == QSize(30,40) or pixmap.size() == QSize(30,60) or pixmap.size() == QSize(10,10):
            qimage = pixmap.toImage()
            if not qimage.isNull() and qimage.width() > 0 and qimage.height() > 0:
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*getattr(C, 'RED', (255,0,0)))
                qcolor_blue = QColor(*getattr(C, 'BLUE', (0,0,255)))
                qcolor_magenta = QColor(*getattr(C, 'MAGENTA', (255,0,255))) # Common error color
                if color_at_origin in [qcolor_red, qcolor_blue, qcolor_magenta]:
                    return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf is not None else self.pos
        if not isinstance(target_pos, QPointF):
            warning(f"Player {self.player_id}: Invalid target_pos in _update_rect (type: {type(target_pos)}). Using self.pos or default.")
            target_pos = self.pos if isinstance(self.pos, QPointF) else QPointF(self.initial_spawn_pos)

        current_image = self.image # This should be the currently set animation frame
        
        # Override image if petrified
        if self.is_petrified and not self.is_stone_smashed:
            current_image = self.stone_crouch_image_frame if self.was_crouching_when_petrified else self.stone_image_frame
        elif self.is_stone_smashed and self.stone_smashed_frames:
            # Use current_frame for smashed animation, ensuring it's valid
            frame_idx_smashed = self.current_frame
            smashed_frames_to_use = self.stone_crouch_smashed_frames if self.was_crouching_when_petrified else self.stone_smashed_frames
            if smashed_frames_to_use and len(smashed_frames_to_use) > 0:
                 frame_idx_smashed = frame_idx_smashed % len(smashed_frames_to_use)
                 current_image = smashed_frames_to_use[frame_idx_smashed]
            else: # Fallback if smashed frames are missing
                 current_image = self.stone_image_frame # Or a specific "fully smashed" placeholder

        img_w, img_h = 0.0, 0.0
        if current_image and not current_image.isNull():
            img_w, img_h = float(current_image.width()), float(current_image.height())
        else: # Fallback dimensions if image is bad
            h_fallback = self.crouching_collision_height if self.is_crouching else self.standing_collision_height
            if h_fallback <= 1e-6: h_fallback = self.standard_height
            if h_fallback <= 1e-6: h_fallback = 60.0
            img_h = h_fallback
            img_w = img_h * 0.5 # Approximate player aspect ratio
            if Player.print_limiter.can_print(f"player_rect_no_image_{self.player_id}"):
                warning(f"Player {self.player_id}: _update_rect_from_image_and_pos called with null/bad image. Using fallback dimensions {img_w}x{img_h}.")

        rect_x = target_pos.x() - img_w / 2.0
        rect_y = target_pos.y() - img_h # Midbottom anchor
        
        if not hasattr(self, 'rect') or self.rect is None: # Should not happen if __init__ is correct
             self.rect = QRectF(rect_x, rect_y, img_w, img_h)
        else:
             self.rect.setRect(rect_x, rect_y, img_w, img_h)

    def alive(self) -> bool: return self._alive
    def kill(self):
        if self._alive: # Only log/act if was previously alive
            debug(f"Player {self.player_id} kill() called. Setting _alive to False.")
        self._alive = False
        # self.is_dead should be set by the state that causes death (e.g. health <= 0 in take_damage)

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            return
        debug(f"Player {self.player_id} Log: Applying aflame effect.")
        self.is_aflame = True; self.is_deflaming = False
        self.aflame_timer_start = get_current_ticks_monotonic()
        self.aflame_damage_last_tick = self.aflame_timer_start # Start damage tick immediately
        set_player_state(self, 'aflame_crouch' if self.is_crouching else 'aflame')
        # Clear conflicting action states
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            return
        debug(f"Player {self.player_id} Log: Applying freeze effect.")
        set_player_state(self, 'frozen') # This handles setting is_frozen, is_defrosting etc.
        self.is_attacking = False; self.attack_type = 0
        self.vel = QPointF(0,0); self.acc.setX(0) # Stop movement

    def update_status_effects(self, current_time_ms: int):
        # (This method seems fine as is, relies on PLAYER_... constants from C)
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                set_player_state(self, 'deflame_crouch' if self.is_crouching else 'deflame')
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK) # Self-damage from being aflame
                self.aflame_damage_last_tick = current_time_ms
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
                # Determine state after deflaming (e.g., idle, fall, or crouch if still holding crouch)
                next_state_after_deflame = 'crouch' if self.is_crouching else ('idle' if self.on_ground else 'fall')
                set_player_state(self, next_state_after_deflame)

        if self.is_frozen:
            if current_time_ms - self.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
                set_player_state(self, 'defrost')
        elif self.is_defrosting:
            if current_time_ms - self.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
                set_player_state(self, 'idle' if self.on_ground else 'fall')
        
        if self.is_stone_smashed: # Ensure smashed players eventually "disappear" or are cleaned up
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                if not self.death_animation_finished: self.death_animation_finished = True
                self.kill() # Mark as fully gone

    def petrify(self):
        # (This method seems fine as is)
        if self.is_petrified or (self.is_dead and not self.is_petrified): return
        debug(f"Player {self.player_id}: Petrifying.")
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        self.is_petrified = True; self.is_stone_smashed = False
        self.is_dead = True # Petrified counts as "dead" for game logic (e.g. game over)
        self.current_health = 0; self.vel = QPointF(0,0); self.acc = QPointF(0,0)
        # Clear all action/conflicting status states
        self.is_attacking = False; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        self.is_aflame = False; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False
        self.death_animation_finished = True # Petrified is an instant visual "death" state
        set_player_state(self, 'petrified')

    def smash_petrification(self):
        # (This method seems fine as is)
        if self.is_petrified and not self.is_stone_smashed:
            debug(f"Player {self.player_id}: Smashing petrification.")
            self.is_stone_smashed = True
            self.stone_smashed_timer_start = get_current_ticks_monotonic()
            self.death_animation_finished = False # Smashed has its own "death" animation/timer
            set_player_state(self, 'smashed')

    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any], platforms_list_ref: List[Any]):
        if self.game_elements_ref_for_projectiles is None: self.game_elements_ref_for_projectiles = {}
        self.game_elements_ref_for_projectiles["projectiles_list"] = projectile_list
        self.game_elements_ref_for_projectiles["all_renderable_objects"] = all_elements_list
        self.game_elements_ref_for_projectiles["platforms_list"] = platforms_list_ref # Make sure this is passed and stored

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        # (This method seems fine as is)
        if not self.is_crouching or not self._valid_init: return True
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True # No real height change
        
        current_feet_y = self.rect.bottom() # Current bottom of crouched rect
        current_center_x = self.rect.center().x()
        
        # Determine standing width (usually from idle animation or standard_height aspect ratio)
        standing_width = self.rect.width() # Default to current width
        if self.animations and self.animations.get('idle') and self.animations['idle'][0] and not self.animations['idle'][0].isNull():
            standing_width = float(self.animations['idle'][0].width())
        
        # Potential rect if standing (anchored by feet position)
        potential_standing_rect = QRectF(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.moveBottom(current_feet_y) # Align feet
        potential_standing_rect.moveCenter(QPointF(current_center_x, potential_standing_rect.center().y())) # Center horizontally

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               potential_standing_rect.intersects(platform_obj.rect):
                # Check if the intersecting platform is *above* the player's current crouched head
                # and *below* where their standing head would be.
                # This means the platform would obstruct standing.
                if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                   platform_obj.rect.top() < self.rect.top(): # Compare with current (crouched) rect top
                    return False # Obstruction found
        return True

    # --- Delegated methods to handlers ---
    def set_state(self, new_state: str): set_player_state(self, new_state)
    def animate(self): update_player_animation(self)

    def process_input(self,
                      qt_keys_held_snapshot: Dict[Qt.Key, bool],
                      qt_key_event_data_this_frame: List[Tuple[QKeyEvent.Type, Qt.Key, bool]],
                      platforms_list: List[Any], # Needed for can_stand_up
                      joystick_data_for_handler: Optional[Dict[str, Any]] = None
                      ):
        active_mappings = {}
        # Determine which mapping to use based on player.control_scheme (set by game_setup or config)
        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_pygame_"):
            # Use the player-specific runtime joystick map (e.g., game_config.P1_MAPPINGS if it's joystick for P1)
            # This assumes P1_MAPPINGS, P2_MAPPINGS etc. in game_config are already the *runtime* format.
            if self.player_id == 1: active_mappings = game_config.P1_MAPPINGS
            elif self.player_id == 2: active_mappings = game_config.P2_MAPPINGS
            elif self.player_id == 3: active_mappings = game_config.P3_MAPPINGS
            elif self.player_id == 4: active_mappings = game_config.P4_MAPPINGS
            else: active_mappings = game_config.DEFAULT_GENERIC_JOYSTICK_MAPPINGS # Fallback
        else: # Fallback if control_scheme is unrecognized
            active_mappings = game_config.P1_MAPPINGS if self.player_id == 1 else game_config.P2_MAPPINGS
            if Player.print_limiter.can_print(f"p_input_scheme_fallback_{self.player_id}"):
                warning(f"Player {self.player_id}: Unrecognized control_scheme '{self.control_scheme}'. Using default keyboard map.")

        return process_player_input_logic(self, qt_keys_held_snapshot, qt_key_event_data_this_frame,
                                          active_mappings, platforms_list, joystick_data_for_handler)

    def _generic_fire_projectile(self, projectile_class: type, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        # (This method seems mostly fine, ensure game_elements_ref_for_projectiles["platforms_list"] is populated)
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting: return
        
        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_print(f"proj_fire_no_game_elements_{self.player_id}"):
                warning(f"Player {self.player_id}: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return
        projectiles_list_ref = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref = self.game_elements_ref_for_projectiles.get("all_renderable_objects")
        # platforms_list_for_proj = self.game_elements_ref_for_projectiles.get("platforms_list") # projectiles need this

        if projectiles_list_ref is None or all_renderables_ref is None: # or platforms_list_for_proj is None:
            if Player.print_limiter.can_print(f"proj_fire_list_missing_{self.player_id}"):
                warning(f"Player {self.player_id}: Projectile, renderable, or platform list missing in ref. Cannot fire {projectile_config_name}.")
            return

        current_time_ms = get_current_ticks_monotonic()
        last_fire_time = getattr(self, cooldown_attr_name, 0)

        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)
            
            if self.rect.isNull(): self._update_rect_from_image_and_pos() # Ensure rect is current
            if self.rect.isNull(): error(f"Player {self.player_id}: Rect is null, cannot determine projectile spawn point."); return

            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6):
                 aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0) # Default horizontal aim

            # Offset projectile spawn slightly from player center based on aim
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0))
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0 # Default for horizontal
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): # If aiming more vertically
                offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0
            
            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length
            
            spawn_x += norm_x * offset_dist
            spawn_y += norm_y * offset_dist
            
            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles # Pass the reference dict
            
            projectiles_list_ref.append(new_projectile)
            all_renderables_ref.append(new_projectile)

            if Player.print_limiter.can_print(f"fired_{projectile_config_name}_{self.player_id}"):
                debug(f"Player {self.player_id} fired {projectile_config_name} at ({spawn_x:.1f},{spawn_y:.1f}) with dir ({aim_dir.x():.1f},{aim_dir.y():.1f})")

            if projectile_config_name == 'blood' and self.current_health > 0: # Blood magic costs health
                health_cost = self.current_health * 0.05 
                self.current_health -= health_cost
                if self.current_health <= 0 and not self.is_dead:
                    set_player_state(self, 'death')


    # Fire methods (these are now correctly defined with projectile classes imported)
    def fire_fireball(self): self._generic_fire_projectile(Fireball, 'fireball_cooldown_timer', C.FIREBALL_COOLDOWN, 'fireball')
    def fire_poison(self): self._generic_fire_projectile(PoisonShot, 'poison_cooldown_timer', C.POISON_COOLDOWN, 'poison')
    def fire_bolt(self): self._generic_fire_projectile(BoltProjectile, 'bolt_cooldown_timer', C.BOLT_COOLDOWN, 'bolt')
    def fire_blood(self): self._generic_fire_projectile(BloodShot, 'blood_cooldown_timer', C.BLOOD_COOLDOWN, 'blood')
    def fire_ice(self): self._generic_fire_projectile(IceShard, 'ice_cooldown_timer', C.ICE_COOLDOWN, 'ice')
    def fire_shadow(self): self._generic_fire_projectile(ShadowProjectile, 'shadow_cooldown_timer', C.SHADOW_PROJECTILE_COOLDOWN, 'shadow_projectile')
    def fire_grey(self): self._generic_fire_projectile(GreyProjectile, 'grey_cooldown_timer', C.GREY_PROJECTILE_COOLDOWN, 'grey_projectile')

    # Combat and Collision Wrappers (these are fine)
    def check_attack_collisions(self, list_of_targets: List[Any]): check_player_attack_collisions(self, list_of_targets)
    def take_damage(self, damage_amount_taken: int): player_take_damage(self, damage_amount_taken)
    def self_inflict_damage(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)
    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]) -> bool: return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    # Main Update Method
    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any], hazards_list: List[Any],
               other_players_list: List[Any], enemies_list: List[Any]):
        if not self._valid_init or not self._alive: return

        current_time_ms = get_current_ticks_monotonic()
        self.update_status_effects(current_time_ms)

        # Handle states that bypass normal physics/input update
        if self.is_stone_smashed:
            if current_time_ms - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                self.kill(); return # Fully gone
            self.animate(); return # Just animate smashed state
        if self.is_petrified: # Not smashed yet, but petrified (falls with gravity, no other actions)
            # Petrified physics (gravity if not on ground) is handled by player_movement_physics.update_player_core_logic
            # So, we can proceed to call it, but it will mostly just apply gravity.
             update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)
             return # No other player logic when petrified

        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)

    def reset_state(self, spawn_position_tuple: Optional[Tuple[float, float]]):
        info(f"Player {self.player_id}: reset_state called. Spawn requested: {spawn_position_tuple}")
        # Ensure _valid_init is True if animations are available (even if they failed before)
        if not self._valid_init and self.animations is None: # Try to load animations again if they failed totally
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations: # If loaded successfully now
                self._valid_init = True # Mark as valid
                # Re-attempt to set collision heights from new animations
                try:
                    idle_frames = self.animations.get('idle')
                    self.standing_collision_height = float(idle_frames[0].height()) if idle_frames and idle_frames[0] and not idle_frames[0].isNull() else 60.0
                    crouch_frames = self.animations.get('crouch')
                    self.crouching_collision_height = float(crouch_frames[0].height()) if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull() else self.standing_collision_height / 2.0
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
                self._valid_init = False # Explicitly mark as invalid if animations are still None

        if not self._valid_init: # If still not valid (e.g., animations couldn't load even on retry)
            self.is_dead = True; self._alive = False; self.current_health = 0
            self.pos = QPointF(self.initial_spawn_pos) if self.initial_spawn_pos else QPointF(50,500) # Default if initial_spawn_pos is None
            self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, 0.0)
            if self.image is None: self.image = self._create_placeholder_qpixmap(QColor(*getattr(C, 'MAGENTA', (255,0,255))), "NoImgRst")
            self._update_rect_from_image_and_pos()
            critical(f"Player {self.player_id}: reset_state called but player is still invalid (likely anim issue). Cannot fully reset.")
            return

        # Set position from spawn_position_tuple or fallback to initial_spawn_pos
        if spawn_position_tuple is not None and isinstance(spawn_position_tuple, (tuple, list)) and len(spawn_position_tuple) == 2:
            try:
                self.pos = QPointF(float(spawn_position_tuple[0]), float(spawn_position_tuple[1]))
            except (TypeError, ValueError) as e_pos:
                warning(f"Player {self.player_id}: Invalid spawn_position_tuple '{spawn_position_tuple}' on reset: {e_pos}. Using initial_spawn_pos {self.initial_spawn_pos}.")
                self.pos = QPointF(self.initial_spawn_pos) # Use the QPointF initial_spawn_pos
        else: # spawn_position_tuple is None or invalid
            self.pos = QPointF(self.initial_spawn_pos) # Use the QPointF initial_spawn_pos
            if spawn_position_tuple is not None : # Log if it was provided but invalid
                warning(f"Player {self.player_id}: reset_state called with invalid spawn_position_tuple '{spawn_position_tuple}'. Using initial_spawn_pos {self.pos}.")

        # Reset core attributes
        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.current_health = self.max_health
        self.is_dead = False
        self.death_animation_finished = False
        self._alive = True # Make sure player is marked as alive

        # Reset action/status flags
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True; self.on_ground = False
        
        # Reset timers
        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;
        self.fireball_cooldown_timer = 0; self.poison_cooldown_timer = 0; self.bolt_cooldown_timer = 0
        self.blood_cooldown_timer = 0; self.ice_cooldown_timer = 0; self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0;
        
        # Reset aiming direction
        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aim right

        # Reset status effects
        self.is_aflame = False; self.aflame_timer_start = 0; self.is_deflaming = False
        self.deflame_timer_start = 0; self.aflame_damage_last_tick = 0
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_petrified = False; self.is_stone_smashed = False; self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right # Reset to current (newly reset) facing
        self.was_crouching_when_petrified = False
        
        # Re-initialize stone assets to their original state (in case they were modified)
        self._init_stone_assets()
        
        # Set initial state and update rect
        set_player_state(self, 'idle') # This will also call update_player_animation
        self._update_rect_from_image_and_pos() # Ensure rect is correct after state set and potential image change

        info(f"Player {self.player_id} reset_state complete. State: {self.state}, Pos: ({self.pos.x():.1f},{self.pos.y():.1f}), Alive: {self._alive}")

    def draw_pyside(self, painter: QPainter, camera: Any):
        # (This method seems fine as is)
        if not self._valid_init or not self.image or self.image.isNull() or not self.rect.isValid():
            return

        # Determine if the player should be drawn based on their state
        should_draw = self.alive() or \
                      (self.is_dead and not self.death_animation_finished and not self.is_petrified) or \
                      self.is_petrified # Petrified (even smashed) players are drawn until they fully disappear

        if not should_draw:
            return

        screen_rect_qrectf = camera.apply(self.rect) # Get screen coordinates
        
        # Basic culling: only draw if the rect intersects the painter's window (viewport)
        if painter.window().intersects(screen_rect_qrectf.toRect()):
            painter.drawPixmap(screen_rect_qrectf.topLeft(), self.image)

            # Optional: Draw health bar above player (if not drawing via HUD in game_ui)
            # This was moved to GameSceneWidget.paintEvent in your structure.
            # If you intend for Player to draw its own bar:
            # if getattr(C, "DRAW_PLAYER_ABOVE_HEALTH_BAR", False) and \
            #    self.current_health < self.max_health and not self.is_dead and not self.is_petrified:
            #     # ... (health bar drawing logic as you had it) ...
            #     pass