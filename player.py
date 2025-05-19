#################### START OF FILE: player.py ####################

# player.py
# -*- coding: utf-8 -*-
"""
Defines the Player class, handling core attributes, collision heights, and
delegating state, animation, physics, collisions, input, combat, and network handling
to respective handler modules. Refactored for PySide6.
"""
# version 2.0.1 (PySide6 Refactor - Added missing Tuple import)
import os
import sys
import math # For vector math if QPointF isn't sufficient (e.g. normalize)
from typing import Dict, List, Optional, Any, Tuple # Added Tuple

# PySide6 imports
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QTransform, QImage
from PySide6.QtCore import QRectF, QPointF, QSize, Qt

# Game imports
from utils import PrintLimiter
import constants as C
import config as game_config
from assets import load_all_player_animations, load_gif_frames, resource_path # Now Qt-based

# Handler modules (assuming they will be refactored or adapt)
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
    from player_input_handler import process_player_input_logic
    from player_combat_handler import (
        check_player_attack_collisions,
        player_take_damage, player_self_inflict_damage, player_heal_to_full
    )
    from player_network_handler import (
        get_player_network_data, set_player_network_data,
        handle_player_network_input # get_player_input_state_for_network is part of Player class
    )
    from projectiles import ( # These will also be refactored
        Fireball, PoisonShot, BoltProjectile, BloodShot,
        IceShard, ShadowProjectile, GreyProjectile
    )
except ImportError as e:
    print(f"CRITICAL PLAYER: Failed to import a handler or projectile module: {e}")
    raise

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_player = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_player) * 1000)


class Player:
    print_limiter = PrintLimiter(default_limit=5, default_period=3.0)

    def __init__(self, start_x: float, start_y: float, player_id: int = 1):
        self.player_id = player_id
        self._valid_init = True
        self.control_scheme: Optional[str] = None
        self.joystick_id_idx: Optional[int] = None
        self.game_elements_ref_for_projectiles: Optional[Dict[str, Any]] = None

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
        self.rect = QRectF()

        if self.animations is None:
            print(f"CRITICAL Player Init Error (ID: {self.player_id}): Failed animations from '{asset_folder}'.")
            self.image = self._create_placeholder_qpixmap(QColor(*C.RED), "AnimFail")
            self._update_rect_from_image_and_pos(QPointF(float(start_x), float(start_y)))
            self.is_dead = True; self._valid_init = False
            self.standing_collision_height = 0.0; self.crouching_collision_height = 0.0; self.standard_height = 0.0
            self._init_fallback_stone_assets()
            return

        self.standing_collision_height = 0.0; self.crouching_collision_height = 0.0
        try:
            idle_frames = self.animations.get('idle')
            if idle_frames and idle_frames[0] and not idle_frames[0].isNull():
                self.standing_collision_height = float(idle_frames[0].height())
            else: self.standing_collision_height = 60.0; Player.print_limiter.can_print(f"p_init_no_idle_h_{self.player_id}")

            crouch_frames = self.animations.get('crouch')
            if crouch_frames and crouch_frames[0] and not crouch_frames[0].isNull():
                self.crouching_collision_height = float(crouch_frames[0].height())
            else: self.crouching_collision_height = self.standing_collision_height / 2.0; Player.print_limiter.can_print(f"p_init_no_crouch_h_{self.player_id}")

            if self.standing_collision_height <= 0 or self.crouching_collision_height <= 0 or \
               self.crouching_collision_height >= self.standing_collision_height:
                print(f"Player {self.player_id} CRITICAL: Invalid collision heights. Stand:{self.standing_collision_height}, Crouch:{self.crouching_collision_height}")
                self._valid_init = False
        except Exception as e:
            print(f"Player {self.player_id} Error setting collision heights: {e}")
            self.standing_collision_height = 60.0; self.crouching_collision_height = 30.0; self._valid_init = False
        self.standard_height = self.standing_collision_height

        self._last_facing_right = True; self._last_state_for_debug = "init"
        self.state = 'idle'; self.current_frame = 0; self.last_anim_update = get_current_ticks()

        initial_idle_frames = self.animations.get('idle')
        if initial_idle_frames and initial_idle_frames[0] and not initial_idle_frames[0].isNull():
            self.image = initial_idle_frames[0]
        else:
            h = self.standing_collision_height if self.standing_collision_height > 0 else 60.0
            self.image = QPixmap(30, int(h)); self.image.fill(QColor(*C.RED))
            print(f"Player {self.player_id} CRITICAL: 'idle' frames missing. Using RED placeholder.")
            self._valid_init = False
        
        self.pos = QPointF(float(start_x), float(start_y)) 
        self._update_rect_from_image_and_pos()

        player_gravity = float(getattr(C, 'PLAYER_GRAVITY', 0.7))
        self.vel = QPointF(0.0, 0.0); self.acc = QPointF(0.0, player_gravity)
        self.facing_right = True; self.on_ground = False; self.on_ladder = False
        self.can_grab_ladder = False; self.touching_wall = 0; self.can_wall_jump = False
        self.wall_climb_timer = 0

        self.is_crouching = False
        self.is_dashing = False; self.dash_timer = 0; self.dash_duration = int(getattr(C, 'PLAYER_DASH_DURATION', 150))
        self.is_rolling = False; self.roll_timer = 0; self.roll_duration = int(getattr(C, 'PLAYER_ROLL_DURATION', 300))
        self.is_sliding = False; self.slide_timer = 0; self.slide_duration = int(getattr(C, 'PLAYER_SLIDE_DURATION', 400))

        self.is_attacking = False; self.attack_timer = 0; self.attack_duration = 300
        self.attack_type = 0; self.can_combo = False
        self.combo_window = int(getattr(C, 'PLAYER_COMBO_WINDOW', 150))
        self.wall_climb_duration = int(getattr(C, 'PLAYER_WALL_CLIMB_DURATION', 500))

        self.is_taking_hit = False; self.hit_timer = 0
        self.hit_duration = int(getattr(C, 'PLAYER_HIT_STUN_DURATION', 300))
        self.hit_cooldown = int(getattr(C, 'PLAYER_HIT_COOLDOWN', 600))

        self.is_dead = False if self._valid_init else True
        self.death_animation_finished = False
        self.state_timer = 0

        self.max_health = int(C.PLAYER_MAX_HEALTH)
        self.current_health = self.max_health if self._valid_init else 0
        self.attack_hitbox = QRectF(0, 0, 45.0, 30.0)

        self.is_trying_to_move_left = False; self.is_trying_to_move_right = False
        self.is_holding_climb_ability_key = False
        self.is_holding_crouch_ability_key = False

        self.fireball_cooldown_timer = 0; self.poison_cooldown_timer = 0
        self.bolt_cooldown_timer = 0; self.blood_cooldown_timer = 0
        self.ice_cooldown_timer = 0; self.shadow_cooldown_timer = 0
        self.grey_cooldown_timer = 0
        self.fireball_last_input_dir = QPointF(1.0, 0.0)

        self.projectile_sprites_group: Optional[List[Any]] = None
        self.all_sprites_group: Optional[List[Any]] = None 

        self.fireball_key: Optional[str] = None; self.poison_key: Optional[str] = None
        self.bolt_key: Optional[str] = None; self.blood_key: Optional[str] = None
        self.ice_key: Optional[str] = None; self.shadow_key: Optional[str] = None
        self.grey_key: Optional[str] = None
        self._assign_projectile_keys()
        self._init_stone_assets()
        self._alive = self._valid_init

        if not self._valid_init:
            print(f"Player {self.player_id}: Initialization marked invalid after all setup.")

    def _init_fallback_stone_assets(self):
        qcolor_gray = QColor(*C.GRAY) if hasattr(C,'GRAY') else QColor(128,128,128)
        qcolor_dark_gray = QColor(*C.DARK_GRAY) if hasattr(C,'DARK_GRAY') else QColor(50,50,50)
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
        qcolor_gray = QColor(*C.GRAY) if hasattr(C,'GRAY') else QColor(128,128,128)
        qcolor_dark_gray = QColor(*C.DARK_GRAY) if hasattr(C,'DARK_GRAY') else QColor(50,50,50)

        common_stone_png_path = resource_path(os.path.join(stone_common_folder, '__Stone.png'))
        frames = load_gif_frames(common_stone_png_path)
        self.stone_image_frame_original = (frames[0] if frames and not self._is_placeholder_qpixmap(frames[0]) else
                                     (self.animations.get('petrified',[self._create_placeholder_qpixmap(qcolor_gray, "StoneP")])[0] if self.animations else self._create_placeholder_qpixmap(qcolor_gray, "StoneP")))
        self.stone_image_frame = self.stone_image_frame_original.copy()

        common_smashed_gif_path = resource_path(os.path.join(stone_common_folder, '__StoneSmashed.gif'))
        frames = load_gif_frames(common_smashed_gif_path)
        self.stone_smashed_frames_original = (frames if frames and not self._is_placeholder_qpixmap(frames[0]) else
                                       (self.animations.get('smashed',[self._create_placeholder_qpixmap(qcolor_dark_gray, "SmashP")]) if self.animations else [self._create_placeholder_qpixmap(qcolor_dark_gray, "SmashP")]))
        self.stone_smashed_frames = [f.copy() for f in self.stone_smashed_frames_original]

        common_crouch_png_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouch.png'))
        frames = load_gif_frames(common_crouch_png_path)
        self.stone_crouch_image_frame_original = (frames[0] if frames and not self._is_placeholder_qpixmap(frames[0]) else
                                           self.stone_image_frame_original.copy()) 
        self.stone_crouch_image_frame = self.stone_crouch_image_frame_original.copy()
        
        common_crouch_smashed_path = resource_path(os.path.join(stone_common_folder, '__StoneCrouchSmashed.gif'))
        frames = load_gif_frames(common_crouch_smashed_path)
        self.stone_crouch_smashed_frames_original = (frames if frames and not self._is_placeholder_qpixmap(frames[0]) else
                                               [f.copy() for f in self.stone_smashed_frames_original]) 
        self.stone_crouch_smashed_frames = [f.copy() for f in self.stone_crouch_smashed_frames_original]

    def _assign_projectile_keys(self):
        if self.player_id == 1:
            self.fireball_key = C.P1_FIREBALL_KEY; self.poison_key = C.P1_POISON_KEY
            self.bolt_key = C.P1_BOLT_KEY; self.blood_key = C.P1_BLOOD_KEY
            self.ice_key = C.P1_ICE_KEY; self.shadow_key = C.P1_SHADOW_PROJECTILE_KEY
            self.grey_key = C.P1_GREY_PROJECTILE_KEY
        elif self.player_id == 2:
            self.fireball_key = C.P2_FIREBALL_KEY; self.poison_key = C.P2_POISON_KEY
            self.bolt_key = C.P2_BOLT_KEY; self.blood_key = C.P2_BLOOD_KEY
            self.ice_key = C.P2_ICE_KEY; self.shadow_key = C.P2_SHADOW_PROJECTILE_KEY
            self.grey_key = C.P2_GREY_PROJECTILE_KEY

    def _create_placeholder_qpixmap(self, q_color: QColor, text: str = "Err") -> QPixmap:
        h = self.standing_collision_height if hasattr(self, 'standing_collision_height') and self.standing_collision_height > 0 else 60.0
        pixmap = QPixmap(30, int(h))
        pixmap.fill(q_color)
        painter = QPainter(pixmap); painter.setPen(QColor(*C.BLACK))
        painter.drawRect(pixmap.rect().adjusted(0,0,-1,-1))
        try:
            font = QFont(); font.setPointSize(10); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        except Exception as e: print(f"PLAYER PlaceholderFontError: {e}")
        painter.end()
        return pixmap

    def _is_placeholder_qpixmap(self, pixmap: QPixmap) -> bool:
        if pixmap.isNull(): return True
        if pixmap.size() == QSize(30,40):
            qimg = pixmap.toImage()
            if not qimg.isNull():
                color_at_origin = qimg.pixelColor(0,0)
                qcolor_red = QColor(*C.RED) if hasattr(C, 'RED') else QColor(255,0,0)
                if color_at_origin == qcolor_red: return True
        return False

    def _update_rect_from_image_and_pos(self, midbottom_pos_qpointf: Optional[QPointF] = None):
        target_pos = midbottom_pos_qpointf if midbottom_pos_qpointf else self.pos
        if self.image and not self.image.isNull():
            img_w, img_h = float(self.image.width()), float(self.image.height())
            rect_x = target_pos.x() - img_w / 2.0
            rect_y = target_pos.y() - img_h
            self.rect.setRect(rect_x, rect_y, img_w, img_h)
        elif self.rect.isNull(): 
             h_fallback = self.standing_collision_height if self.standing_collision_height > 0 else 60.0
             self.rect.setRect(target_pos.x() - 15, target_pos.y() - h_fallback, 30, h_fallback)
    
    def alive(self) -> bool:
        return self._alive

    def kill(self):
        self._alive = False

    def apply_aflame_effect(self):
        if self.is_aflame or self.is_deflaming or self.is_dead or self.is_petrified or self.is_frozen or self.is_defrosting:
            Player.print_limiter.can_print(f"player_apply_aflame_blocked_{self.player_id}")
            return
        Player.print_limiter.can_print(f"player_apply_aflame_{self.player_id}")
        self.is_aflame = True; self.is_deflaming = False
        self.aflame_timer_start = get_current_ticks(); self.aflame_damage_last_tick = self.aflame_timer_start
        set_player_state(self, 'aflame_crouch' if self.is_crouching else 'aflame')
        self.is_attacking = False; self.attack_type = 0

    def apply_freeze_effect(self):
        if self.is_frozen or self.is_defrosting or self.is_dead or self.is_petrified or self.is_aflame or self.is_deflaming:
            Player.print_limiter.can_print(f"player_apply_frozen_blocked_{self.player_id}")
            return
        Player.print_limiter.can_print(f"player_apply_frozen_{self.player_id}")
        set_player_state(self, 'frozen')
        self.is_attacking = False; self.attack_type = 0
        self.vel = QPointF(0,0); self.acc.setX(0)

    def update_status_effects(self, current_time_ms: int):
        if self.is_aflame:
            if current_time_ms - self.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
                self.is_aflame = False; self.is_deflaming = True; self.deflame_timer_start = current_time_ms
                set_player_state(self, 'deflame_crouch' if self.is_crouching else 'deflame')
            elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
                 current_time_ms - self.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
                self.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
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
        self.current_health = 0; self.vel = QPointF(0,0); self.acc = QPointF(0,0)
        self.is_attacking = False; self.is_dashing = False; self.is_rolling = False; self.is_sliding = False
        self.on_ladder = False; self.is_taking_hit = False
        self.is_aflame = False; self.is_deflaming = False; self.is_frozen = False; self.is_defrosting = False
        self.death_animation_finished = True 
        set_player_state(self, 'petrified')

    def smash_petrification(self):
        if self.is_petrified and not self.is_stone_smashed:
            self.is_stone_smashed = True; self.stone_smashed_timer_start = get_current_ticks()
            self.death_animation_finished = False 
            set_player_state(self, 'smashed')

    def set_projectile_group_references(self, projectile_list: List[Any], all_elements_list: List[Any]):
        self.projectile_sprites_group = projectile_list
        self.all_sprites_group = all_elements_list

    def can_stand_up(self, platforms_list: List[Any]) -> bool:
        if not self.is_crouching or not self._valid_init: return True
        if self.standing_collision_height <= self.crouching_collision_height: return True

        current_feet_y = self.rect.bottom(); current_center_x = self.rect.center().x()
        standing_width = self.rect.width()
        
        potential_standing_rect = QRectF(0, 0, standing_width, self.standing_collision_height)
        potential_standing_rect.moveBottom(current_feet_y)
        potential_standing_rect.moveCenterX(current_center_x)

        for platform_obj in platforms_list:
            if hasattr(platform_obj, 'rect') and potential_standing_rect.intersects(platform_obj.rect):
                if platform_obj.rect.bottom() > potential_standing_rect.top() and platform_obj.rect.top() < self.rect.top():
                    return False
        return True

    def set_state(self, new_state: str): set_player_state(self, new_state)
    def animate(self): update_player_animation(self)
    
    def process_input(self, qt_events: List[Any], platforms_list: List[Any], qt_keys_pressed_snapshot: Optional[Dict[int, bool]] = None):
        active_mappings = {}
        if self.control_scheme == "keyboard_p1": active_mappings = game_config.P1_MAPPINGS
        elif self.control_scheme == "keyboard_p2": active_mappings = game_config.P2_MAPPINGS
        elif self.control_scheme and self.control_scheme.startswith("joystick_"):
            active_mappings = game_config.P1_MAPPINGS if self.player_id == 1 else game_config.P2_MAPPINGS
        else: active_mappings = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS
        
        # process_player_input_logic will need to be adapted for Qt events and key snapshot
        return process_player_input_logic(self, qt_keys_pressed_snapshot or {}, qt_events, active_mappings, platforms_list)

    def _generic_fire_projectile(self, projectile_class, cooldown_attr_name: str, cooldown_const: int, projectile_config_name: str):
        if not self._valid_init or self.is_dead or not self._alive or self.is_petrified or self.is_frozen or self.is_defrosting: return
        if self.projectile_sprites_group is None or self.all_sprites_group is None: return

        current_time_ms = get_current_ticks()
        last_fire_time = getattr(self, cooldown_attr_name, 0)
        if current_time_ms - last_fire_time >= cooldown_const:
            setattr(self, cooldown_attr_name, current_time_ms)
            spawn_x, spawn_y = self.rect.center().x(), self.rect.center().y()
            aim_dir = QPointF(self.fireball_last_input_dir.x(), self.fireball_last_input_dir.y())
            if aim_dir.isNull() or (aim_dir.x() == 0 and aim_dir.y() == 0): # check if zero vector
                 aim_dir.setX(1.0 if self.facing_right else -1.0); aim_dir.setY(0.0)
            
            proj_dims_tuple = getattr(C, f"{projectile_config_name.upper()}_DIMENSIONS", (10,10))
            offset_dist = (self.rect.width() / 2.0) + (proj_dims_tuple[0] / 2.0) - 30.0
            if abs(aim_dir.y()) > 0.8 * abs(aim_dir.x()): offset_dist = (self.rect.height() / 2.0) + (proj_dims_tuple[1] / 2.0) - 10.0
            
            norm_x, norm_y = 0.0, 0.0
            length = math.sqrt(aim_dir.x()**2 + aim_dir.y()**2)
            if length > 1e-6: norm_x = aim_dir.x()/length; norm_y = aim_dir.y()/length
            
            spawn_x += norm_x * offset_dist; spawn_y += norm_y * offset_dist
            
            new_projectile = projectile_class(spawn_x, spawn_y, aim_dir, self)
            if hasattr(self, 'game_elements_ref_for_projectiles'): new_projectile.game_elements_ref = self.game_elements_ref_for_projectiles
            self.projectile_sprites_group.append(new_projectile) 
            self.all_sprites_group.append(new_projectile)
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
    def self_inflict_damage_local_debug(self, damage_amount_to_self: int): player_self_inflict_damage(self, damage_amount_to_self)
    def heal_to_full(self): player_heal_to_full(self)
    def heal_to_full_local_debug(self): player_heal_to_full(self)

    def get_network_data(self) -> Dict[str, Any]:
        data = get_player_network_data(self) # This already handles base player data
        data['was_crouching_when_petrified'] = self.was_crouching_when_petrified # Ensure this is included
        return data

    def set_network_data(self, received_network_data: Dict[str, Any]):
        set_player_network_data(self, received_network_data) # Handles base player data
        self.was_crouching_when_petrified = received_network_data.get('was_crouching_when_petrified', self.was_crouching_when_petrified)

    def handle_network_input(self, network_input_data_dict: Dict[str, Any]): handle_player_network_input(self, network_input_data_dict)
    
    def get_input_state_for_network(self, current_qt_keys_pressed_map: Dict[int, bool], current_qt_events: List[Any], key_map_config: Dict[str, Any]) -> Dict[str, Any]:
        platforms_list_for_input: List[Any] = []
        if hasattr(self, 'game_elements_ref_for_projectiles') and \
           self.game_elements_ref_for_projectiles and \
           'platform_sprites' in self.game_elements_ref_for_projectiles:
            platforms_list_for_input = self.game_elements_ref_for_projectiles['platform_sprites']

        processed_action_events = process_player_input_logic(self, current_qt_keys_pressed_map, current_qt_events, key_map_config, platforms_list_for_input)
        
        network_input_dict = {
            'left_held': self.is_trying_to_move_left, 'right_held': self.is_trying_to_move_right,
            'up_held': self.is_holding_climb_ability_key, 'down_held': self.is_holding_crouch_ability_key,
            'is_crouching_state': self.is_crouching,
            'fireball_aim_x': self.fireball_last_input_dir.x(), 'fireball_aim_y': self.fireball_last_input_dir.y()
        }
        network_input_dict.update(processed_action_events)
        return network_input_dict

    def check_platform_collisions(self, direction: str, platforms_list: List[Any]): check_player_platform_collisions(self, direction, platforms_list)
    def check_ladder_collisions(self, ladders_list: List[Any]): check_player_ladder_collisions(self, ladders_list)
    def check_character_collisions(self, direction: str, characters_list: List[Any]): return check_player_character_collisions(self, direction, characters_list)
    def check_hazard_collisions(self, hazards_list: List[Any]): check_player_hazard_collisions(self, hazards_list)

    def update(self, dt_sec: float, platforms_list: List[Any], ladders_list: List[Any], hazards_list: List[Any],
               other_players_list: List[Any], enemies_list: List[Any]):
        current_time_ms_for_status = get_current_ticks()
        self.update_status_effects(current_time_ms_for_status)

        if self.is_stone_smashed:
            if current_time_ms_for_status - self.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
                self.kill(); return
            self.animate(); return
        if self.is_petrified:
            self.vel = QPointF(0,0); self.acc = QPointF(0,0)
            self.animate(); return
        update_player_core_logic(self, dt_sec, platforms_list, ladders_list, hazards_list, other_players_list, enemies_list)

    def reset_state(self, spawn_position_tuple: Tuple[float, float]):
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
                    if self.standing_collision_height <= 0 or self.crouching_collision_height <= 0 or self.crouching_collision_height >= self.standing_collision_height: self._valid_init = False
                except: self._valid_init = False
                idle_frames = self.animations.get('idle')
                if idle_frames and idle_frames[0] and not idle_frames[0].isNull(): self.image = idle_frames[0]
                else: self.image = self._create_placeholder_qpixmap(QColor(*C.RED), "ResetAnimFail")
            else: Player.print_limiter.can_print(f"player_reset_anim_fail_{self.player_id}"); return
        
        self.pos = QPointF(float(spawn_position_tuple[0]), float(spawn_position_tuple[1]))
        self._update_rect_from_image_and_pos()
        self.vel = QPointF(0.0, 0.0)
        self.acc = QPointF(0.0, float(getattr(C, 'PLAYER_GRAVITY', 0.7)))
        self.current_health = self.max_health
        self.is_dead = False; self.death_animation_finished = False
        self.is_taking_hit = False; self.is_attacking = False; self.attack_type = 0
        self.is_dashing = False; self.is_rolling = False; self.is_sliding = False; self.is_crouching = False
        self.on_ladder = False; self.touching_wall = 0; self.facing_right = True
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
        if self.image and hasattr(self.image, 'toImage') and not self.image.toImage().isNull() and self.image.toImage().hasAlphaChannel():
            # If image has alpha, ensure it's fully opaque unless intended otherwise
            if self.image.toImage().format() != QImage.Format.Format_ARGB32_Premultiplied and \
               self.image.toImage().format() != QImage.Format.Format_ARGB32:
                self.image = QPixmap.fromImage(self.image.toImage().convertToFormat(QImage.Format.Format_ARGB32))
            # If alpha needs to be set to 255 across the board (less common for QPixmap)
            # img_copy = self.image.copy(); painter = QPainter(img_copy); painter.setCompositionMode(QPainter.CompositionMode_DestinationIn); painter.fillRect(img_copy.rect(), Qt.GlobalColor.black); painter.end(); self.image = img_copy
        
        set_player_state(self, 'idle')

#################### END OF FILE: player.py ####################