#################### START OF FILE: enemy\enemy_knight.py ####################
# enemy/enemy_knight.py
# -*- coding: utf-8 -*-
"""
Defines the EnemyKnight, a new type of enemy that uses specific animations
and is capable of jumping during its patrol routine.
Uses relative paths for animations, resolved via assets.resource_path.
MODIFIED: Corrected __init__ for initial image/rect.
MODIFIED: Implemented _load_knight_animations with fallbacks.
MODIFIED: Added _knight_ai_update for specific AI logic.
MODIFIED: Overrode update method to use _knight_ai_update.
MODIFIED: Ensured patrol_target_x is initialized if not set by super.
MODIFIED: Refined attack logic to use attack_type string consistently ("none" when not attacking).
MODIFIED: Physics for dead falling knight is now handled in the overridden update method.
MODIFIED: Corrected set_state calls to use self.set_state (which inherits from Enemy->EnemyBase).
MODIFIED: Fallback animation for initial image now includes more options.
MODIFIED: Corrected logger import path and general import paths for enemy package.
MODIFIED: Ensured `patrol_target_x` is initialized in `reset` if missing.
"""
# version 2.1.4 (Logger/import paths, reset patrol_target_x)

import os
import random
import math
import time
import sys
from typing import List, Optional, Any, Dict, Tuple

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF, Qt, QSize
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont

# --- Project Root Setup ---
_ENEMY_KNIGHT_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_ENEMY_KNIGHT = os.path.dirname(_ENEMY_KNIGHT_PY_FILE_DIR) # Up one level to 'enemy'
if _PROJECT_ROOT_FOR_ENEMY_KNIGHT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_ENEMY_KNIGHT) # Add 'enemy' package's parent
_PROJECT_ROOT_GRANDPARENT_KNIGHT = os.path.dirname(_PROJECT_ROOT_FOR_ENEMY_KNIGHT) # Up two levels to project root
if _PROJECT_ROOT_GRANDPARENT_KNIGHT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_GRANDPARENT_KNIGHT) # Add actual project root
# --- End Project Root Setup ---


# Game imports
import main_game.constants as C
from main_game.assets import load_gif_frames, resource_path # Corrected path for assets

# Base Enemy Class (relative import from within enemy package)
try:
    from .enemy import Enemy # Inherits from generic Enemy
except ImportError:
    from enemy import Enemy # type: ignore Fallback for some linters/test runners

# Import handlers that EnemyKnight's update method will call directly
# These should already have their own robust logger fallbacks if needed.
_HANDLERS_AVAILABLE = True
try:
    # Relative imports for handlers within the 'enemy' package
    from .enemy_status_effects import update_enemy_status_effects
    from .enemy_physics_handler import update_enemy_physics_and_collisions
    from .enemy_combat_handler import check_enemy_attack_collisions
    from .enemy_ai_handler import set_enemy_new_patrol_target # Utility from generic AI
except ImportError as e_handlers:
    print(f"CRITICAL ENEMY_KNIGHT: Failed to import one or more enemy handlers (from .enemy package): {e_handlers}")
    _HANDLERS_AVAILABLE = False
    def update_enemy_status_effects(*_args, **_kwargs): return False
    def update_enemy_physics_and_collisions(*_args, **_kwargs): pass
    def check_enemy_attack_collisions(*_args, **_kwargs): pass
    def set_enemy_new_patrol_target(enemy: Any): pass


# --- Logger Setup ---
import logging
_enemy_knight_logger_instance = logging.getLogger(__name__ + "_enemy_knight_internal_fallback")
if not _enemy_knight_logger_instance.hasHandlers():
    _handler_ek_fb = logging.StreamHandler(sys.stdout)
    _formatter_ek_fb = logging.Formatter('ENEMY_KNIGHT (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_ek_fb.setFormatter(_formatter_ek_fb)
    _enemy_knight_logger_instance.addHandler(_handler_ek_fb)
    _enemy_knight_logger_instance.setLevel(logging.DEBUG)
    _enemy_knight_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_knight_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_knight_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_knight_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_knight_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_knight_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("EnemyKnight: Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL ENEMY_KNIGHT: Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_knight:
    critical(f"CRITICAL ENEMY_KNIGHT: Unexpected error during logger setup from main_game.logger: {e_logger_init_knight}. Using internal fallback.")
# --- End Logger Setup ---


_start_time_knight_monotonic = time.monotonic()
def get_knight_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_knight_monotonic) * 1000)

# All paths now include "assets/" prefix relative to project root
KNIGHT_ANIM_PATHS = {
    "idle": "assets/enemy_characters/knight/idle.gif",
    "run": "assets/enemy_characters/knight/run.gif",
    "jump": "assets/enemy_characters/knight/jump.gif",
    "fall": "assets/enemy_characters/knight/fall.gif", # Assuming 'fall.gif' exists, or it will use placeholder
    "attack1": "assets/enemy_characters/knight/attack1.gif",
    "attack2": "assets/enemy_characters/knight/attack2.gif",
    "attack3": "assets/enemy_characters/knight/attack3.gif",
    "run_attack": "assets/enemy_characters/knight/run_attack.gif",
    "hurt": "assets/enemy_characters/knight/hurt.gif",
    "dead": "assets/enemy_characters/knight/dead.gif",
    "death_nm": "assets/enemy_characters/knight/dead.gif", # Knight specific 'dead_nm' might not exist, using 'dead'
    "defend": "assets/enemy_characters/knight/defend.gif",
    "protect": "assets/enemy_characters/knight/protect.gif",
    "zapped": "assets/enemy_characters/knight/hurt.gif", # Fallback zapped to hurt if no specific zapped anim
    # Status effects like aflame, frozen will use common assets from EnemyBase if not overridden here.
}

class EnemyKnight(Enemy):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None,
                 _internal_class_type_override: Optional[str] = "EnemyKnight"):

        super().__init__(start_x, start_y, patrol_area, enemy_id, "knight_type_specific", properties=properties)

        if not self._valid_init:
            critical(f"EnemyKnight (ID: {self.enemy_id}): Critical failure in EnemyBase/Enemy super().__init__.")
            return
        if not _HANDLERS_AVAILABLE:
            warning(f"EnemyKnight (ID: {self.enemy_id}): Critical handlers missing. Functionality will be impaired.")

        self.animations = self._load_knight_animations() # Override EnemyBase's generic animations

        initial_knight_image_set = False
        initial_anim_keys_priority = ['idle', 'run', 'jump', 'fall', 'attack1', 'dead']
        for anim_key_init in initial_anim_keys_priority:
            if self.animations and self.animations.get(anim_key_init) and \
               self.animations[anim_key_init][0] and not self.animations[anim_key_init][0].isNull():
                self.image = self.animations[anim_key_init][0]
                self._update_rect_from_image_and_pos()
                initial_knight_image_set = True
                debug(f"EnemyKnight (ID: {self.enemy_id}): Initial image/rect set from knight's '{anim_key_init}'.")
                break

        if not initial_knight_image_set:
            if self.animations:
                for anim_key_fallback in self.animations:
                    if self.animations.get(anim_key_fallback) and self.animations[anim_key_fallback][0] and not self.animations[anim_key_fallback][0].isNull():
                        self.image = self.animations[anim_key_fallback][0]
                        self._update_rect_from_image_and_pos()
                        initial_knight_image_set = True
                        warning(f"EnemyKnight (ID: {self.enemy_id}): Initial image/rect set from knight's fallback '{anim_key_fallback}'.")
                        break
            if not initial_knight_image_set:
                critical(f"EnemyKnight (ID: {self.enemy_id}): No valid initial animations found for knight even after full fallback. Marking as invalid.")
                self._create_and_set_error_placeholder_image("K_NO_INIT_IMG")
                self._valid_init = False; return

        # --- Knight-Specific Attributes ---
        self.max_health = int(self.properties.get("max_health", getattr(C, 'ENEMY_KNIGHT_MAX_HEALTH_DEFAULT', 150)))
        self.current_health = self.max_health
        
        # Base speed for Knight is in units/second from properties, convert to units/frame for internal use
        speed_units_per_sec = float(self.properties.get("move_speed", getattr(C, 'ENEMY_KNIGHT_BASE_SPEED_DEFAULT', getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75 * 50.0 )))
        self.base_speed_units_per_frame = speed_units_per_sec / C.FPS # Used for speed limit internally
        
        # Jump strength from properties is units/second^2, convert to impulse (change in velocity per frame)
        jump_strength_units_per_sec_sq = float(self.properties.get("jump_strength", getattr(C, 'ENEMY_KNIGHT_JUMP_STRENGTH_DEFAULT', getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65 * 60.0 )))
        # If jump_strength is given as a direct velocity change (like player's), this conversion is not needed.
        # Assuming it's an impulse similar to player's jump:
        self.jump_strength = jump_strength_units_per_sec_sq / C.FPS # This is a velocity change, not accel
        
        self.patrol_jump_chance = float(self.properties.get("patrol_jump_chance", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_CHANCE_DEFAULT', 0.015)))
        self.patrol_jump_cooldown_ms = int(self.properties.get("patrol_jump_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_COOLDOWN_MS_DEFAULT', 2500)))
        self.last_patrol_jump_time: int = 0
        self._is_mid_patrol_jump: bool = False

        self.attack_damage_map: Dict[str, int] = {
            'attack1': int(self.properties.get("attack1_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK1_DAMAGE_DEFAULT', 15))),
            'attack2': int(self.properties.get("attack2_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK2_DAMAGE_DEFAULT', 20))),
            'attack3': int(self.properties.get("attack3_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK3_DAMAGE_DEFAULT', 25))),
            'run_attack': int(self.properties.get("run_attack_damage", getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DAMAGE_DEFAULT', 12))),
        }
        self.attack_duration_map: Dict[str, int] = {
            'attack1': int(self.properties.get("attack1_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK1_DURATION_MS', 500))),
            'attack2': int(self.properties.get("attack2_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK2_DURATION_MS', 600))),
            'attack3': int(self.properties.get("attack3_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK3_DURATION_MS', 700))),
            'run_attack': int(self.properties.get("run_attack_duration_ms", getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DURATION_MS', 450))),
        }
        self.attack_cooldown_duration = int(self.properties.get("attack_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK_COOLDOWN_MS_DEFAULT', 1800)))
        self.attack_range = float(self.properties.get("attack_range_px", getattr(C, 'ENEMY_KNIGHT_ATTACK_RANGE_DEFAULT', getattr(C, 'ENEMY_ATTACK_RANGE', 60.0) * 1.2)))
        self.detection_range = float(self.properties.get("detection_range_px", getattr(C, 'ENEMY_KNIGHT_DETECTION_RANGE_DEFAULT', getattr(C, 'ENEMY_DETECTION_RANGE', 200.0))))
        
        self.patrol_behavior = self.properties.get("patrol_behavior", "knight_patrol_with_jump")

        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            current_x_for_patrol_init = self.pos.x() if hasattr(self, 'pos') and self.pos else start_x
            patrol_range_knight = float(self.properties.get("patrol_range_tiles", 5) * C.TILE_SIZE)
            self.patrol_target_x = current_x_for_patrol_init + random.uniform(-patrol_range_knight, patrol_range_knight)

        self.attack_type: str = "none"

        info(f"EnemyKnight (ID: {self.enemy_id}) fully initialized. Valid: {self._valid_init}, Health: {self.current_health}/{self.max_health}")

    def _create_and_set_error_placeholder_image(self, text_tag: str):
        base_tile_size = getattr(C, 'TILE_SIZE', 40)
        width = int(base_tile_size * 0.75)
        height = int(base_tile_size * 1.8)
        magenta_color_tuple = getattr(C, 'MAGENTA', (255,0,255))
        placeholder_image = self._create_placeholder_qpixmap(QColor(*magenta_color_tuple), text_tag, QSize(width, height))
        self.image = placeholder_image
        self._update_rect_from_image_and_pos()

    def _load_knight_animations(self) -> Dict[str, List[QPixmap]]:
        knight_animations: Dict[str, List[QPixmap]] = {}
        for anim_name_key, relative_anim_path_val in KNIGHT_ANIM_PATHS.items():
            full_path_to_gif = resource_path(relative_anim_path_val) # resource_path needs path relative to project root
            frames = load_gif_frames(full_path_to_gif)
            
            if not frames or (frames and frames[0].isNull()) or \
               (len(frames) == 1 and self._is_placeholder_qpixmap(frames[0])):
                is_core_anim = anim_name_key in ["idle", "run", "jump", "attack1", "hurt", "dead"]
                log_level_func = error if is_core_anim else debug # Log as error for core, debug for non-core placeholders
                log_level_func(f"EnemyKnight (ID: {self.enemy_id}): Animation '{anim_name_key}' from '{full_path_to_gif}' missing or invalid. Using code-generated placeholder.")
                dims = {"idle": (28,50), "run": (32,50), "jump": (36,50), "fall":(36,50),
                        "attack1": (40,50), "attack2": (42,50), "attack3": (45,50),
                        "run_attack": (48,50), "hurt": (32,50), "dead": (50,30), "death_nm": (50,30),
                        "defend": (30,50), "protect": (29,50), "zapped": (32,50)}
                w, h = dims.get(anim_name_key, (30,50))
                placeholder_color = QColor(200,0,0) if is_core_anim else QColor(200,100,0)
                frames = [self._create_placeholder_qpixmap(placeholder_color, anim_name_key[:3].upper(), QSize(w,h))]
            knight_animations[anim_name_key] = frames
        return knight_animations

    def _knight_ai_update(self, players_list_for_ai: list, current_time_ms: int):
        if getattr(self, 'is_taking_hit', False) and \
           current_time_ms - getattr(self, 'hit_timer', 0) < getattr(self, 'hit_cooldown', C.ENEMY_HIT_COOLDOWN):
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            return

        closest_target_player = None; min_squared_distance_to_player = float('inf')
        if not (hasattr(self, 'pos') and self.pos): return

        for p_cand in players_list_for_ai:
            if p_cand and getattr(p_cand, '_valid_init', False) and hasattr(p_cand, 'pos') and \
               getattr(p_cand, 'alive', False) and not getattr(p_cand, 'is_dead', True) and not getattr(p_cand, 'is_petrified', False):
                dx = p_cand.pos.x() - self.pos.x(); dy = p_cand.pos.y() - self.pos.y()
                dist_sq = dx*dx + dy*dy
                if dist_sq < min_squared_distance_to_player: min_squared_distance_to_player = dist_sq; closest_target_player = p_cand
        distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')
        
        enemy_rect_h = self.rect.height() if hasattr(self, 'rect') else C.TILE_SIZE * 1.8
        vertical_dist = abs(closest_target_player.rect.center().y() - self.rect.center().y()) if closest_target_player and hasattr(closest_target_player,'rect') and hasattr(self,'rect') else float('inf')
        has_vertical_los = vertical_dist < enemy_rect_h * 1.1

        is_player_in_attack_range = distance_to_target_player < self.attack_range and has_vertical_los
        is_player_in_detection_range = distance_to_target_player < self.detection_range and has_vertical_los

        post_attack_pause_duration = getattr(self, 'post_attack_pause_duration', C.ENEMY_POST_ATTACK_PAUSE_DURATION)
        if getattr(self, 'post_attack_pause_timer', 0) > 0 and current_time_ms < self.post_attack_pause_timer:
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            if self.state != 'idle': self.set_state('idle') # Use self.set_state
            return

        if getattr(self, 'is_attacking', False):
            current_attack_key = str(getattr(self, 'attack_type', 'attack1'))
            current_attack_duration = self.attack_duration_map.get(current_attack_key, 500)
            if current_time_ms - getattr(self, 'attack_timer', 0) >= current_attack_duration:
                self.is_attacking = False; setattr(self, 'attack_type', "none") # Reset to "none"
                self.attack_cooldown_timer = current_time_ms
                self.post_attack_pause_timer = current_time_ms + post_attack_pause_duration
                self.set_state('idle') # Use self.set_state
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            return

        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            set_enemy_new_patrol_target(self) # This is from generic enemy_ai_handler

        is_attack_off_cooldown = current_time_ms - getattr(self, 'attack_cooldown_timer', 0) > self.attack_cooldown_duration
        target_accel_x = 0.0; target_facing_right = self.facing_right

        if self._is_mid_patrol_jump:
            if self.on_ground: self._is_mid_patrol_jump = False; self.set_state('idle')
            if hasattr(self, 'acc'): self.acc.setX(0.0); return

        if not closest_target_player or not is_player_in_detection_range: # Patrol
            self.ai_state = 'patrolling_knight'
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle')
            can_attempt_jump = (current_time_ms - self.last_patrol_jump_time > self.patrol_jump_cooldown_ms)
            if self.patrol_behavior == "knight_patrol_with_jump" and can_attempt_jump and self.on_ground and random.random() < self.patrol_jump_chance:
                self.vel.setY(self.jump_strength); self.on_ground = False; self._is_mid_patrol_jump = True
                self.set_state('jump'); self.last_patrol_jump_time = current_time_ms
                if hasattr(self, 'acc'): self.acc.setX(0.0); return
            if abs(self.pos.x() - self.patrol_target_x) < 10:
                set_enemy_new_patrol_target(self)
                if self.state == 'run': self.set_state('idle')
            target_facing_right = (self.patrol_target_x > self.pos.x())
            # Knight acceleration derived from its base_speed_units_per_frame and time_to_max
            time_to_max_knight = 0.3 * C.FPS # Slightly quicker to react
            knight_patrol_accel = (self.base_speed_units_per_frame * 0.7) / time_to_max_knight if time_to_max_knight > 0 else 0.2
            target_accel_x = knight_patrol_accel * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05 and not self._is_mid_patrol_jump : self.set_state('run')
        elif is_player_in_attack_range and is_attack_off_cooldown: # Attack
            self.ai_state = 'attacking_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            chosen_attack_key = 'attack1'
            if abs(self.vel.x()) > self.base_speed_units_per_frame * 0.5 and 'run_attack' in self.animations and self.animations['run_attack']: chosen_attack_key = 'run_attack'
            elif 'attack2' in self.animations and self.animations['attack2'] and random.random() < 0.4: chosen_attack_key = 'attack2'
            elif 'attack3' in self.animations and self.animations['attack3'] and random.random() < 0.2: chosen_attack_key = 'attack3'
            self.set_state(chosen_attack_key); setattr(self, 'attack_type', chosen_attack_key) # Set string attack_type
            self.is_attacking = True; self.attack_timer = current_time_ms
        elif is_player_in_detection_range: # Chase
            self.ai_state = 'chasing_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            knight_chase_accel = self.base_speed_units_per_frame / (0.25 * C.FPS) if C.FPS > 0 else 0.3
            target_accel_x = knight_chase_accel * (1 if target_facing_right else -1)
            if self.state not in ['run', 'jump', 'fall']: self.set_state('run')
        else: # Fallback Patrol
            self.ai_state = 'patrolling_knight_fb'
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle')
            if abs(self.pos.x() - self.patrol_target_x) < 10: set_enemy_new_patrol_target(self)
            target_facing_right = (self.patrol_target_x > self.pos.x())
            knight_patrol_accel_fb = (self.base_speed_units_per_frame * 0.7) / (0.3 * C.FPS) if C.FPS > 0 else 0.2
            target_accel_x = knight_patrol_accel_fb * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05 and not self._is_mid_patrol_jump : self.set_state('run')

        if hasattr(self, 'acc') and not self._is_mid_patrol_jump and not self.is_attacking: self.acc.setX(target_accel_x)
        if not getattr(self, 'is_attacking', False) and not self._is_mid_patrol_jump:
             if self.facing_right != target_facing_right: self.facing_right = target_facing_right

    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive: return
        current_time_ms = get_knight_current_ticks_monotonic()
        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        if status_overrode_update:
            self.animate()
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive(): self.kill()
            return
        if getattr(self, 'is_dead', False):
            if self.alive(): # Death animation playing
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc'):
                    self.vel.setY(self.vel.y() + self.acc.y())
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                self.animate()
                if getattr(self, 'death_animation_finished', False): self.kill()
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            return
        self._knight_ai_update(players_list_for_logic, current_time_ms)
        update_enemy_physics_and_collisions( self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()] )
        if getattr(self, 'is_attacking', False): check_enemy_attack_collisions(self, players_list_for_logic)
        self.animate() # Calls generic update_enemy_animation

    def reset(self):
        super().reset() # Resets EnemyBase, then Enemy attributes.
        if self._valid_init:
            # Reload knight-specific animations if they were somehow cleared or if reset needs fresh load
            # Note: super().reset() might have set self.animations to generic if Enemy.reset() was complex.
            # Explicitly re-load knight animations to ensure correctness.
            self.animations = self._load_knight_animations()
            if self.animations and self.animations.get('idle') and self.animations['idle'][0] and not self.animations['idle'][0].isNull():
                self.image = self.animations['idle'][0]
            else: # Fallback if knight-specific idle is still bad after reset
                self._create_and_set_error_placeholder_image("K_RST_FAIL")

            self._update_rect_from_image_and_pos() # Update rect with potentially new initial image
            self.attack_type = "none" # Knight uses string "none" when not attacking
            self._is_mid_patrol_jump = False
            self.last_patrol_jump_time = 0
            if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
                current_x_for_patrol_init_reset = self.pos.x() if hasattr(self, 'pos') and self.pos else self.spawn_pos.x()
                patrol_range_knight_reset = float(self.properties.get("patrol_range_tiles", 5) * C.TILE_SIZE)
                self.patrol_target_x = current_x_for_patrol_init_reset + random.uniform(-patrol_range_knight_reset, patrol_range_knight_reset)

            self.set_state('idle') # Ensure correct initial state for Knight
            debug(f"EnemyKnight (ID: {self.enemy_id}) fully reset with knight-specifics.")
        else:
            warning(f"EnemyKnight (ID: {self.enemy_id}): Reset called, but _valid_init is False.")

#################### END OF FILE: enemy/enemy_knight.py ####################