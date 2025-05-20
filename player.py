# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes, collision heights, and
delegating state, animation, physics, collisions, input, combat, and network handling
to respective handler modules. Refactored for PySide6.
"""
# version 2.0.3 (Added initial_properties to __init__)
import os
import sys
import math # For vector math if QPointF isn't sufficient (e.g. normalize)
import time # For monotonic timer
from typing import Dict, List, Optional, Any, Tuple # Ensure Optional, Dict, Any, Tuple are imported

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game imports
from utils import PrintLimiter
import constants as C
import config as game_config
from assets import load_all_player_animations, load_gif_frames, resource_path # Qt-based

# Handler modules
try:
    from player_state_handler import set_player_state
    from player_animation_handler import update_player_animation
    from player_movement_physics import update_player_core_logic
    from player_collision_handler import (
        check_player_platform_collisions,
        check_player_ladder_collisions,
        check_player_character_collisions,
        check_player_hazard_collisions
    )
    # Assuming player_input_handler.py now has process_player_input_logic_pyside
    from player_input_handler import process_player_input_logic_pyside as process_player_input_logic
    from player_combat_handler import (
        check_player_attack_collisions,
        player_take_damage, player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input
    )
    from projectiles import (
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
except ImportError as e:
    print(f"CRITICAL PLAYER: Failed to import a handler or projectile module: {e}")
    # Consider re-raising or a more graceful exit if critical modules are missing
    raise

# --- Monotonic Timer ---
_start_time_player_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_player_monotonic) * 1000)
# --- End Monotonic Timer ---


class Player:
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x: float, start_y: float, player_id: int = 1,
                 initial_properties: Optional[Dict[str, Any]] = None): # Added initial_properties
        self.player_id = player_id
        self._valid_init = True
        self.properties = initial_properties if initial_properties is not None else {} # Store properties
        self.control_scheme: Optional[str] = None # e.g., "keyboard_p1", "joystick_0"
        self.joystick_id_idx: Optional[int] = None # For direct joystick access if needed by input handler
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None # For projectile creation context

        asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
        self.animations: Optional[Dict[str, List[QPixmap]]] = load_all_player_animations(relative_asset_folder=asset_folder)

        # Status Effect Flags & Timers
        self.is_aflame = False; self.aflame_timer_start = 0
        self.is_deflaming = False; self.deflame_timer_start = 0
        self.aflame_damage_last_tick = 0
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_petrified = False; self.is_stone_smashed = False
        self.stone_smashed_timer_start = 0
        self.facing_at_petrification = True
        self.was_crouching_when_petrified = False

        self.image: Optional[QPixmap] = None
        self.rect = QRectF() # Initialize as an empty QRectF

        if self.animations is None:
            print(f"CRITICAL Player Init Error (ID: {self.player_id}): Failed loading animations from '{asset_folder}'.")
            # Ensure C.RED is a tuple (r,g,b)
            red_color = getattr(C, 'RED', (255,0,0))
            self.image = self._create_placeholder_qpixmap(QColor(*red_color), "AnimFail")
            self.pos = QPointF(float(start_x), float(start_y)) # Init pos before _update_rect
            self._update_rect_from_image_and_pos()
            self.is_dead = True; self._valid_init = False; self._alive = False
            self.standing_collision_height = 0.0; self.crouching_collision_height = 0.0; self.standard_height = 0.0
            self._init_fallback_stone_assets() # Initialize stone assets even on fail for consistency
            # Essential physics attributes for fallback
            self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, 0.0)
            self.state = 'idle'; self.current_frame = 0; self.last_anim_update = 0
            self.facing_right = True; self.on_ground = False
            self.current_health = 0; self.max_health = 0
            return # Exit early if animations failed

        # Collision heights
        self.standing_collision_height = 0.0; self.crouching_collision_height = 0.0
        try:
            idle_frames = self.animations.get('idle')
            if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                self.standing_collision_height = float(idle_frames[0].height())
            else:
                self.standing_collision_height = 60.0 # Fallback
                if Player.print_limiter.can_print(f"p_init_no_idle_h_{self.player_id}"):
                    print(f"Player {self.player_id} Warning: 'idle' animation frame for height not found. Defaulting standing height.")

            crouch_frames = self.animations.get('crouch')
            if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                self.crouching_collision_height = float(crouch_frames[0].height())
            else:
                self.crouching_collision_height = self.standing_collision_height / 2.0 # Fallback
                if Player.print_limiter.can_print(f"p_init_no_crouch_h_{self.player_id}"):
                     print(f"Player {self.player_id} Warning: 'crouch' animation frame for height not found. Defaulting crouching height.")

            if self.standing_collision_height <= 1e-6 or self.crouching_collision_height <= 1e-6 or \
               self.crouching_collision_height >= self.standing_collision_height:
                print(f"Player {self.player_id} CRITICAL: Invalid collision heights after load/fallback. StandH:{self.standing_collision_height}, CrouchH:{self.crouching_collision_height}")
                self._valid_init = False # Mark as invalid if heights are problematic
        except Exception as e:
            print(f"Player {self.player_id} Error setting collision heights: {e}")
            self.standing_collision_height = 60.0; self.crouching_collision_height = 30.0; self._valid_init = False
        self.standard_height = self.standing_collision_height # Used by camera, etc.

        # Animation and State
        self._last_facing_right = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0
        self.last_anim_update = get_current_ticks_monotonic() # Use monotonic timer

        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
            self.image = initial_idle_frames[0]
        else: # This case should be rare if previous height check passed, but good for safety
            h_fallback = self.standing_collision_height if self.standing_collision_height > 1e-6 else 60.0
            red_color_tuple = getattr(C, 'RED', (255,0,0))
            self.image = QPixmap(30, int(h_fallback)); self.image.fill(QColor(*red_color_tuple))
            print(f"Player {self.player_id} CRITICAL: 'idle' frames missing for initial image. Using RED placeholder.")
            self._valid_init = False

        self.pos = QPointF(float(start_x), float(start_y)) # Midbottom reference
        self._update_rect_from_image_and_pos() # Set initial rect

        # Physics
        player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
        self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, player_gravity)
        self.facing_right = True; self.on_ground = False; self.on_ladder = False
        self.can_grab_ladder = False; self.touching_wall = 0; self.can_wall_jump = False
        self.wall_climb_timer = 0 # Timestamp of when wall climb started

        # Action States
        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = int(getattr(C, 'PLAYER_ROLL_DURATION', 300))
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        # Combat States
        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300 # Default, can be overridden by animation
        self.attack_type = 0; self.can_combo = False
        self.combo_window = int(getattr(C, 'PLAYER_COMBO_WINDOW', 250))
        self.wall_climb_duration = int(getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500))

        self.is_taking_hit = False; self.hit_timer = 0
        self.hit_duration = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600))

        # Health & Status
        self.is_dead = not self._valid_init
        self.death_animation_finished = False
        self.state_timer = 0 # General timer for current state if needed

        self.max_health = int(self.properties.get("max_health", C.PLAYER_MAX_HEALTH)) # Use property if available
        self.current_health = self.max_health if self._valid_init else 0
        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0) # Relative to player, adjusted in combat handler

        # Input Intentions (set by input handler)
        self.is_trying_to_move_left = False; self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False
        self.is_holding_crouch_ability_key = False

        # Projectile Cooldowns & Aiming
        self.fireball_cooldown_timer = 0; self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0; self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0; self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0
        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aim direction

        # Group references (set externally by game_setup)
        self.projectile_sprites_group: Optional[List[Any]] = None # Will hold Projectile instances
        self.all_sprites_group: Optional[List[Any]] = None # Will hold all renderable game objects

        self._assign_projectile_keys() # Assigns string key names from constants
        self._init_stone_assets()      # Load stone/smashed visuals
        self._alive = self._valid_init # Player is alive if initialized correctly

        if not self._valid_init:
            print(f"Player {self.player_id}: Initialization marked as invalid after all setup steps.")

    def _init_fallback_stone_assets(self):
        qcolor_gray = QColor(*(getattr(C,'GRAY', (128,128,128))))
        qcolor_dark_gray = QColor(*(getattr(C,'DARK_GRAY', (50,50,50))))
        self.stone_image_frame_original = self._create_placeholder_qpixmap(qcolor_gray, "StonePFail")
        self.stone_image_frame = self.stone_image_frame_original.copy()
        self.stone_smashed_frames_original = [self._create_placeholder_qpixmap(qcolor_dark_gray, "SmashPFail")]
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]
        self.stone_crouch_image_frame_original = self._create_placeholder_qpixmap(qcolor_gray, "SCrouchFailP")
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()
        self.stone_crouch_smashed_frames_original = [self._create_placeholder_qpixmap(qcolor_dark_gray, "SCSmashFailP")]
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]

    def _init_stone_assets(self):
        stone_common_folder = os.path.join('characters', 'Stone')
        qcolor_gray = QColor(*(getattr(C,'GRAY', (128,128,128))))
        qcolor_dark_gray = QColor(*(getattr(C,'DARK_GRAY', (50,50,50))))

        # Helper to load frames or use placeholder
        def load_or_placeholder(path, default_placeholder_color, default_placeholder_text, is_list=False):
            frames = load_gif_frames(resource_path(path))
            if frames and not self._is_placeholder_qpixmap(frames[0]):
                return frames if is_list else frames[0]

            # Fallback to animation dict if defined
            anim_key = 'petrified' if not is_list and "Stone.png" in path else \
                       ('smashed' if is_list and "Smashed.gif" in path else None) # Basic heuristic
            if anim_key and self.animations and self.animations.get(anim_key):
                anim_frames = self.animations.get(anim_key, [])
                if anim_frames and not self._is_placeholder_qpixmap(anim_frames[0]):
                    return anim_frames if is_list else anim_frames[0]

            # Ultimate fallback: create new placeholder
            placeholder = self._create_placeholder_qpixmap(default_placeholder_color, default_placeholder_text)
            return [placeholder] if is_list else placeholder

        self.stone_image_frame_original = load_or_placeholder(os.path.join(stone_common_folder, '__Stone.png'), qcolor_gray, "StoneP")
        self.stone_image_frame = self.stone_image_frame_original.copy()

        self.stone_smashed_frames_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneSmashed.gif'), qcolor_dark_gray, "SmashP", is_list=True)
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        self.stone_crouch_image_frame_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneCrouch.png'), qcolor_gray, "SCrouchP")
        if self.stone_crouch_image_frame_original == self._create_placeholder_qpixmap(qcolor_gray, "SCrouchP"): # If it's the generic fallback
            self.stone_crouch_image_frame_original = self.stone_image_frame_original.copy() # Use standing stone as better fallback
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()

        self.stone_crouch_smashed_frames_original = load_or_placeholder(os.path.join(stone_common_folder, '__StoneCrouchSmashed.gif'), qcolor_dark_gray, "SCSmashP", is_list=True)
        if len(self.stone_crouch_smashed_frames_original) == 1 and self._is_placeholder_qpixmap(self.stone_crouch_smashed_frames_original[0]): # If generic fallback
             self.stone_crouch_smashed_frames_original = [f.copy() for f in self.stone_smashed_frames_original] # Use standing smashed as better fallback
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
        h = getattr(self, 'standing_collision_height', 60.0)
        if h <= 1e-6 : h = 60.0 # Ensure positive height
        pixmap = QPixmap(30, int(h))
        pixmap.fill(q_color)
        painter = QPainter(pixmap);
        black_color_tuple = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color_tuple))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(max(6, int(h / 6))); painter.setFont(font) # Dynamic font size
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"PLAYER PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40): # Standard placeholder size from assets.py
            qimage = pixmap.toImage()
            if not qimage.isNull():
                color_at_origin = qimage.pixelColor(0,0)
                qcolor_red = QColor(*(getattr(C, 'RED', (255,0,0))))
                qcolor_blue = QColor(*(getattr(C, 'BLUE', (0,0,255)))) # For other placeholder types
                if color_at_origin == qcolor_red or color_at_origin == qcolor_blue:
                    return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf else self.pos
        if not isinstance(target_pos, QPointF): # Ensure target_pos is valid
            target_pos = QPointF(0,0)
            if Player.print_limiter.can_print(f"player_update_rect_invalid_pos_{self.player_id}"):
                 print(f"Player {self.player_id} Warning: Invalid target_pos in _update_rect_from_image_and_pos. Defaulting to (0,0).")


        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = target_pos.x() - img_w / 2.0
            rect_y = target_pos.y() - img_h
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif hasattr(self, 'rect'): # Ensure rect attribute exists
             h_fallback = self.standing_collision_height if hasattr(self, 'standing_collision_height') and self.standing_collision_height > 1e-6 else 60.0
             self.rect.setRect(target_pos.x() - 15, target_pos.y() - h_fallback, 30, h_fallback)

    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False
        # print(f"Player {self.player_id} kill() called.") # Debugging

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            if Player.print_limiter.can_print(f"player_apply_aflame_blocked_{self.player_id}"):
                print(f"Player {self.player_id} Log: apply_aflame_effect blocked due to conflicting state.")
            return
        if Player.print_limiter.can_print(f"player_apply_aflame_{self.player_id}"):
            print(f"Player {self.player_id} Log: Applying aflame effect.")
        self.is_aflame = True; self.is_deflaming = False
        self.aflame_timer_start = get_current_ticks_monotonic(); self.aflame_damage_last_tick = self.aflame_timer_start
        set_player_state(self, 'aflame_crouch' if self.is_crouching else 'aflame')
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            if Player.print_limiter.can_print(f"player_apply_frozen_blocked_{self.player_id}"):
                print(f"Player {self.player_id} Log: apply_freeze_effect blocked due to conflicting state.")
            return
        if Player.print_limiter.can_print(f"player_apply_frozen_{self.player_id}"):
            print(f"Player {self.player_id} Log: Applying freeze effect.")
        set_player_state(self, 'frozen')
        self.is_attacking = False; self.attack_type = 0
        if hasattr(self, 'vel'): self.vel = QPointF(0,0) # Ensure vel is QPointF
        if hasattr(self, 'acc') and hasattr(self.acc, 'setX'): self.acc.setX(0)


    def update_status_effects(self, current_time_ms: int):
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                self.is_aflame = False; self.is_deflaming = True; self.deflame_timer_start = current_time_ms
                set_player_state(self, 'deflame_crouch' if self.is_crouching else 'deflame')
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK) # Assumes take_damage exists
                self.aflame_damage_last_tick = current_time_ms
        elif self.is_deflaming:
            if current_time_ms - self.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
                self.is_deflaming = False
                set_player_state(self, 'crouch' if self.is_crouching else ('idle' if self.on_ground else 'fall'))

        if self.is_frozen:
            if current_time_ms - self.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
                set_player_state(self, 'defrost')
        elif self.is_defrosting:
            if current_time_ms - self.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
                set_player_state(self, 'idle' if self.on_ground else 'fall')

    def petrify(self):
        if self.is_petrified or (self.is_dead and not self.is_petrified): return
        self.facing_at_petrification = self.facing_right
        self.was_crouching_when_petrified = self.is_crouching
        self.is_petrified = True; self.is_stone_smashed = False; self.is_dead = True
        self.current_health = 0
        if hasattr(self, 'vel'): self.vel = QPointF(0,0)
        if hasattr(self, 'acc'): self.acc = QPointF(0,0)
        self.is_attacking = False; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        self.is_aflame = False; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False
        self.death_animation_finished = True
        set_player_state(self, 'petrified')

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            self.is_stone_smashed = True; self.stone_smashed_timer_start = get_current_ticks_monotonic() # Use monotonic
            self.death_animation_finished = False
            set_player_state(self, 'smashed')

    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any]):
        self.projectile_sprites_group = projectile_list
        self.all_sprites_group = all_elements_list

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True
        if self.standing_collision_height <= self.crouching_collision_height + 1e-6 : return True # Add tolerance for float comparison

        current_feet_y = self.rect.bottom(); current_center_x = self.rect.center().x()
        # Use standing width if different from crouch width, otherwise current rect width
        standing_width = self.rect.width() # Assuming width doesn't change significantly for standing anim
        if self.animations and self.animations.get('idle') and self.animations['idle'][0]:
            standing_width = float(self.animations['idle'][0].width())

        potential_standing_rect = QRectF(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.moveBottom(current_feet_y)
        potential_standing_rect.moveCenterX(current_center_x)

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and isinstance(platform_obj.rect, QRectF) and \
               potential_standing_rect.intersects(platform_obj.rect):
                # Check if the platform is TRULY above the player's current crouched head
                # and would intersect the standing rect.
                if platform_obj.rect.bottom() > potential_standing_rect.top() and \
                   platform_obj.rect.top() < self.rect.top(): # Platform is between crouched head and standing head
                    return False
        return True

    def set_state(self, new_state: str): set_player_state(self, new_state)
    def animate(self): update_player_animation(self)

    # process_input is called by main.py which provides Qt input data
    def process_input(self,
                      qt_keys_held_snapshot: Dict[Qt.Key, bool],
                      qt_key_events_this_frame: List[Any], # List[QKeyEvent]
                      platforms_list: List[Any],
                      joystick_data_for_handler: Optional[Dict[str, Any]] = None
                      ):
        active_mappings = {}
        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_"):
            active_mappings = game_config.LOADED_JOYSTICK_MAPPINGS if game_config.LOADED_JOYSTICK_MAPPINGS else game_config.DEFAULT_JOYSTICK_FALLBACK_MAPPINGS
        else: # Fallback to default P1 keyboard if control_scheme is None or unrecognized
            active_mappings = game_config.P1_MAPPINGS

        return process_player_input_logic(self, qt_keys_held_snapshot, qt_key_events_this_frame,
                                          active_mappings, platforms_list, joystick_data_for_handler)

    def _generic_fire_projectile(self, projectile_class, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting: return
        if self.game_elements_ref_for_projectiles is None:
            if Player.print_limiter.can_print(f"proj_fire_no_game_elements_{self.player_id}"):
                print(f"Player {self.player_id} Warning: game_elements_ref_for_projectiles not set. Cannot fire {projectile_config_name}.")
            return

        projectiles_list_ref = self.game_elements_ref_for_projectiles.get("projectiles_list")
        all_renderables_ref = self.game_elements_ref_for_projectiles.get("all_renderable_objects")
        if projectiles_list_ref is None or all_renderables_ref is None:
            if Player.print_limiter.can_print(f"proj_fire_no_lists_{self.player_id}"):
                print(f"Player {self.player_id} Warning: Projectile/renderable lists missing in game_elements_ref. Cannot fire {projectile_config_name}.")
            return


        current_time_ms = get_current_ticks_monotonic() # Use monotonic timer
        last_fire_time = getattr(self, cooldown_attr_name, 0)
        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)

            # Ensure rect is valid for calculating spawn position
            if not hasattr(self, 'rect') or self.rect.isNull():
                self._update_rect_from_image_and_pos() # Try to update/create it
                if self.rect.isNull():
                     if Player.print_limiter.can_print(f"proj_fire_no_rect_{self.player_id}"):
                         print(f"Player {self.player_id} Error: Cannot fire {projectile_config_name}, player rect is null.")
                     return

            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (abs(aim_dir.x()) < 1e-6 and abs(aim_dir.y()) < 1e-6):
                 aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0)

            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10.0,10.0)) # Ensure float
            # Calculate offset based on aim direction more robustly
            offset_dist = (self.rect.width() / 2.0) + (float(proj_dims_tuple[0]) / 2.0) - 5.0 # Reduced offset
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): # More vertical aim
                offset_dist = (self.rect.height() / 2.0) + (float(proj_dims_tuple[1]) / 2.0) - 5.0

            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length

            spawn_x += norm_x * offset_dist; spawn_y += norm_y * offset_dist

            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles # Pass context

            projectiles_list_ref.append(new_projectile)
            all_renderables_ref.append(new_projectile)

            if projectile_config_name == 'blood' and self.current_health > 0: # Blood magic cost
                self.current_health -= self.current_health * 0.05 # Example: 5% of current health
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
    def self_inflict_damage_local_debug(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)
    def heal_to_full_local_debug(self): player_heal_to_full(self)

    def get_network_data(self) -> Dict[str, Any]:
        data = get_player_network_data(self)
        data['was_crouching_when_petrified'] = self.was_crouching_when_petrified
        return data

    def set_network_data(self, received_network_data: Dict[str, Any]):
        set_player_network_data(self, received_network_data)
        self.was_crouching_when_petrified = received_network_data.get('was_crouching_when_petrified', self.was_crouching_when_petrified)

    def handle_network_input(self, network_input_data_dict: Dict[str, Any]): handle_player_network_input(self, network_input_data_dict)

    def get_input_state_for_network(self,
                                    current_qt_keys_pressed_map: Dict[Qt.Key, bool],
                                    current_qt_key_events: List[Any], # List[QKeyEvent]
                                    key_map_config: Dict[str, Any],
                                    joystick_data_for_handler: Optional[Dict[str, Any]] = None
                                    ) -> Dict[str, Any]:
        # Determine platforms_list from game_elements_ref_for_projectiles
        platforms_list_for_input: List[Any] = []
        if self.game_elements_ref_for_projectiles:
            platforms_list_for_input = self.game_elements_ref_for_projectiles.get("platforms_list", [])


        processed_action_events = process_player_input_logic(
            self, current_qt_keys_pressed_map, current_qt_key_events,
            key_map_config, platforms_list_for_input, joystick_data_for_handler
        )

        network_input_dict = {
            'left_held': self.is_trying_to_move_left, 'right_held': self.is_trying_to_move_right,
            'up_held': self.is_holding_climb_ability_key, 'down_held': self.is_holding_crouch_ability_key,
            'is_crouching_state': self.is_crouching,
            'fireball_aim_x': self.fireball_last_input_dir.x(),
            'fireball_aim_y': self.fireball_last_input_dir.y()
        }
        network_input_dict.update(processed_action_events) # Add all discrete action events
        return network_input_dict

    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]): return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any], hazards_list: List[Any],
               other_players_list: List[Any], enemies_list: List[Any]):
        current_time_ms_for_status = get_current_ticks_monotonic() # Use monotonic timer
        self.update_status_effects(current_time_ms_for_status)

        if self.is_stone_smashed: # Smashed petrification is a terminal state until duration ends
            if current_time_ms_for_status - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                if hasattr(self, 'kill'): self.kill() # Ensure kill method exists
                return
            if hasattr(self, 'animate'): self.animate()
            return
        if self.is_petrified: # Petrified (not smashed) is immobile
            if hasattr(self, 'vel'): self.vel = QPointF(0,0)
            if hasattr(self, 'acc'): self.acc = QPointF(0,0)
            if hasattr(self, 'animate'): self.animate()
            return

        # If not in an overriding terminal state, proceed with core logic
        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)

    def reset_state(self, spawn_position_tuple: Tuple[float, float]):
        if not self._valid_init and self.animations is None:
            # Attempt to reload animations if initial load failed
            asset_folder = 'characters/player1' if self.player_id == 1 else 'characters/player2'
            self.animations = load_all_player_animations(relative_asset_folder=asset_folder)
            if self.animations is not None:
                self._valid_init = True # Assume valid now, will be checked by height loading
                # Re-attempt to load collision heights and initial image
                try:
                    idle_f = self.animations.get('idle')
                    self.standing_collision_height = float(idle_f[0].height()) if idle_f and idle_f[0] and not idle_f[0].isNull() else 60.0
                    crouch_f = self.animations.get('crouch')
                    self.crouching_collision_height = float(crouch_f[0].height()) if crouch_f and crouch_f[0] and not crouch_f[0].isNull() else self.standing_collision_height / 2.0
                    if self.standing_collision_height <= 1e-6 or self.crouching_collision_height <= 1e-6 or self.crouching_collision_height >= self.standing_collision_height: self._valid_init = False
                    self.standard_height = self.standing_collision_height
                except: self._valid_init = False # Mark invalid if errors during height setup

                initial_idle_frames_reset = self.animations.get('idle')
                if initial_idle_frames_reset and initial_idle_frames_reset[0] and not initial_idle_frames_reset[0].isNull():
                    self.image = initial_idle_frames_reset[0]
                else: # If still no valid idle image
                    red_color_tuple = getattr(C, 'RED', (255,0,0))
                    self.image = self._create_placeholder_qpixmap(QColor(*red_color_tuple), "ResetAnimFail")
                    self._valid_init = False # Mark invalid if essential image missing
            else: # Animations still None after reload attempt
                if Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"):
                     print(f"Player {self.player_id} Warning: Animations still failed to load on reset. Player invalid.")
                self._valid_init = False # Ensure it stays invalid

        # If still not valid after trying to reload, bail or ensure dead state
        if not self._valid_init:
            self.is_dead = True; self._alive = False; self.current_health = 0
            # Ensure critical physics attributes exist even if invalid, for safety
            if not hasattr(self, 'pos'): self.pos = QPointF(float(spawn_position_tuple[0]), float(spawn_position_tuple[1]))
            if not hasattr(self, 'vel'): self.vel = QPointF(0.0, 0.0)
            if not hasattr(self, 'acc'): self.acc = QPointF(0.0, 0.0)
            return

        # Proceed with reset for a valid or re-validated player
        self.pos = QPointF(float(spawn_position_tuple[0]), float(spawn_position_tuple[1]))
        self._update_rect_from_image_and_pos() # Ensure rect matches initial image and pos

        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.current_health = self.max_health # Should be set from C.PLAYER_MAX_HEALTH in __init__

        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True

        self.hit_timer = 0; self.dash_timer = 0; self.roll_timer = 0; self.slide_timer = 0
        self.attack_timer = 0; self.wall_climb_timer = 0;

        # Reset cooldowns
        self.fireball_cooldown_timer = 0; self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0; self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0; self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0
        self.fireball_last_input_dir = QPointF(1.0, 0.0) # Default aim

        # Reset status effects
        self.is_aflame = False; self.aflame_timer_start = 0; self.is_deflaming = False
        self.deflame_timer_start = 0; self.aflame_damage_last_tick = 0
        self.is_frozen = False; self.is_defrosting = False; self.frozen_effect_timer = 0
        self.is_petrified = False; self.is_stone_smashed = False; self.stone_smashed_timer_start = 0
        self.facing_at_petrification = self.facing_right # Reset to current facing
        self.was_crouching_when_petrified = False

        self._init_stone_assets() # Re-initialize stone assets to their default state

        self._alive = True # Player is alive after reset

        # Ensure image has alpha correctly handled if it's from an RGBA source
        if self.image and hasattr(self.image, 'toImage') and not self.image.toImage().isNull():
            q_img = self.image.toImage()
            if q_img.hasAlphaChannel() and \
               q_img.format() != QImage.Format.Format_ARGB32_Premultiplied and \
               q_img.format() != QImage.Format.Format_ARGB32:
                self.image = QPixmap.fromImage(q_img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied))

        set_player_state(self, 'idle') # Set to a known good state
        print(f"Player {self.player_id} reset_state complete. State: {self.state}")