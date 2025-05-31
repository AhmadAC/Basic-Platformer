# enemy_knight.py
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
MODIFIED: Refined attack logic to use attack_type string consistently.
MODIFIED: Physics for dead falling knight is now handled in the overridden update method.
MODIFIED: Corrected set_state calls to use self.set_state (which inherits from Enemy->EnemyBase).
MODIFIED: Fallback animation for initial image now includes more options.
MODIFIED: Corrected logger fallback and import path.
"""
# version 2.1.3 (Logger import path fix, asset path refactor)

import os
import random
import math
import time
import sys # Added for logger fallback
from typing import List, Optional, Any, Dict, Tuple

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF, Qt, QSize
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont

# Game imports
import main_game.constants as C
from enemy import Enemy # Inherits from generic Enemy
from assets import load_gif_frames, resource_path

# Import handlers that EnemyKnight's update method will call directly
# These should already have their own robust logger fallbacks if needed.
_HANDLERS_AVAILABLE = True
try:
    from enemy_status_effects import update_enemy_status_effects
    from enemy_physics_handler import update_enemy_physics_and_collisions
    from enemy_combat_handler import check_enemy_attack_collisions
except ImportError as e_handlers:
    print(f"CRITICAL ENEMY_KNIGHT: Failed to import one or more enemy handlers: {e_handlers}")
    _HANDLERS_AVAILABLE = False
    def update_enemy_status_effects(*_args, **_kwargs): return False
    def update_enemy_physics_and_collisions(*_args, **_kwargs): pass
    def check_enemy_attack_collisions(*_args, **_kwargs): pass

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
    debug("EnemyKnight: Successfully aliased project's logger functions from main_game.logger.")
except ImportError:
    critical("CRITICAL ENEMY_KNIGHT: Failed to import logger from main_game.logger. Using internal fallback print statements for logging.")
except Exception as e_logger_init_knight:
    critical(f"CRITICAL ENEMY_KNIGHT: Unexpected error during logger setup from main_game.logger: {e_logger_init_knight}. Using internal fallback.")
# --- End Logger Setup ---


_start_time_knight_monotonic = time.monotonic()
def get_knight_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_knight_monotonic) * 1000)

# MODIFIED: All paths now include "assets/" prefix
KNIGHT_ANIM_PATHS = {
    "idle": "assets/enemy_characters/knight/idle.gif",
    "run": "assets/enemy_characters/knight/run.gif",
    "jump": "assets/enemy_characters/knight/jump.gif",
    "fall": "assets/enemy_characters/knight/fall.gif",
    "attack1": "assets/enemy_characters/knight/attack1.gif",
    "attack2": "assets/enemy_characters/knight/attack2.gif",
    "attack3": "assets/enemy_characters/knight/attack3.gif",
    "run_attack": "assets/enemy_characters/knight/run_attack.gif",
    "hurt": "assets/enemy_characters/knight/hurt.gif",
    "dead": "assets/enemy_characters/knight/dead.gif",
    "death_nm": "assets/enemy_characters/knight/dead_nm.gif",
    "defend": "assets/enemy_characters/knight/defend.gif",
    "protect": "assets/enemy_characters/knight/protect.gif",
    # Add "zapped" if knight has a specific zapped animation
    # "zapped": "assets/enemy_characters/knight/zapped.gif",
}

class EnemyKnight(Enemy):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None,
                 _internal_class_type_override: Optional[str] = "EnemyKnight"): # Used by network handler for type

        # Pass "knight_type_specific" to EnemyBase's color_name.
        # This prevents EnemyBase from trying to load generic soldier animations,
        # as EnemyKnight will load its own specific set.
        super().__init__(start_x, start_y, patrol_area, enemy_id, "knight_type_specific", properties=properties)

        if not self._valid_init:
            critical(f"EnemyKnight (ID: {self.enemy_id}): Critical failure in EnemyBase super().__init__.")
            return
        if not _HANDLERS_AVAILABLE:
            warning(f"EnemyKnight (ID: {self.enemy_id}): Critical handlers missing. Functionality will be impaired.")

        self.animations = self._load_knight_animations()

        initial_knight_image_set = False
        # Prioritized list for finding a valid initial image
        initial_anim_keys_priority = ['idle', 'fall', 'run', 'jump', 'attack1', 'dead']
        for anim_key_init in initial_anim_keys_priority:
            if self.animations and self.animations.get(anim_key_init) and \
               self.animations[anim_key_init][0] and not self.animations[anim_key_init][0].isNull():
                self.image = self.animations[anim_key_init][0]
                self._update_rect_from_image_and_pos() # Update rect based on actual loaded image
                initial_knight_image_set = True
                debug(f"EnemyKnight (ID: {self.enemy_id}): Initial image/rect set from knight's '{anim_key_init}'.")
                break
        
        if not initial_knight_image_set:
            # If no priority animation found, try any animation
            if self.animations:
                for anim_key_fallback in self.animations: # Iterate through whatever keys were loaded
                    if self.animations.get(anim_key_fallback) and self.animations[anim_key_fallback][0] and not self.animations[anim_key_fallback][0].isNull():
                        self.image = self.animations[anim_key_fallback][0]
                        self._update_rect_from_image_and_pos()
                        initial_knight_image_set = True
                        warning(f"EnemyKnight (ID: {self.enemy_id}): Initial image/rect set from knight's fallback '{anim_key_fallback}'.")
                        break
            
            if not initial_knight_image_set:
                critical(f"EnemyKnight (ID: {self.enemy_id}): No valid initial animations found for knight even after full fallback. Marking as invalid.")
                self._create_and_set_error_placeholder_image("K_NO_INIT_IMG") # Method to create placeholder
                self._valid_init = False # Mark as invalid if all animation loading fails
                return

        # --- Knight-Specific Attributes ---
        self.max_health = int(self.properties.get("max_health", getattr(C, 'ENEMY_KNIGHT_MAX_HEALTH_DEFAULT', 150)))
        self.current_health = self.max_health
        
        self.base_speed = float(self.properties.get("move_speed", getattr(C, 'ENEMY_KNIGHT_BASE_SPEED_DEFAULT', getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75)))
        self.jump_strength = float(self.properties.get("jump_strength", getattr(C, 'ENEMY_KNIGHT_JUMP_STRENGTH_DEFAULT', getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65)))
        
        self.patrol_jump_chance = float(self.properties.get("patrol_jump_chance", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_CHANCE_DEFAULT', 0.015)))
        self.patrol_jump_cooldown_ms = int(self.properties.get("patrol_jump_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_COOLDOWN_MS_DEFAULT', 2500)))
        self.last_patrol_jump_time: int = 0
        self._is_mid_patrol_jump: bool = False # Internal flag for jump state

        # Attack damages and durations
        self.attack_damage_map: Dict[str, int] = {
            'attack1': int(self.properties.get("attack1_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK1_DAMAGE_DEFAULT', 15))),
            'attack2': int(self.properties.get("attack2_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK2_DAMAGE_DEFAULT', 20))),
            'attack3': int(self.properties.get("attack3_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK3_DAMAGE_DEFAULT', 25))),
            'run_attack': int(self.properties.get("run_attack_damage", getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DAMAGE_DEFAULT', 12))),
        }
        self.attack_duration_map: Dict[str, int] = { # In milliseconds
            'attack1': int(self.properties.get("attack1_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK1_DURATION_MS', 500))),
            'attack2': int(self.properties.get("attack2_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK2_DURATION_MS', 600))),
            'attack3': int(self.properties.get("attack3_duration_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK3_DURATION_MS', 700))),
            'run_attack': int(self.properties.get("run_attack_duration_ms", getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DURATION_MS', 450))),
        }
        self.attack_cooldown_duration = int(self.properties.get("attack_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK_COOLDOWN_MS_DEFAULT', 1800)))
        # Note: attack_range and detection_range are inherited from EnemyBase but can be overridden by properties
        self.attack_range = float(self.properties.get("attack_range_px", getattr(C, 'ENEMY_KNIGHT_ATTACK_RANGE_DEFAULT', getattr(C, 'ENEMY_ATTACK_RANGE', 60.0) * 1.2)))
        self.detection_range = float(self.properties.get("detection_range_px", getattr(C, 'ENEMY_KNIGHT_DETECTION_RANGE_DEFAULT', getattr(C, 'ENEMY_DETECTION_RANGE', 200.0))))
        
        self.patrol_behavior = self.properties.get("patrol_behavior", "knight_patrol_with_jump")

        # Initialize patrol_target_x if not set by super() (which it might not be if base_speed was 0 initially)
        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            self.patrol_target_x = self.pos.x() if hasattr(self, 'pos') and self.pos else start_x
        
        # Knight's attack_type will be a string key for its attack_damage_map/attack_duration_map
        self.attack_type: str = "none" 

        info(f"EnemyKnight (ID: {self.enemy_id}) fully initialized. Valid: {self._valid_init}, Health: {self.current_health}/{self.max_health}")

    def _create_and_set_error_placeholder_image(self, text_tag: str):
        # Inherited from EnemyBase, uses self._create_placeholder_qpixmap
        base_tile_size = getattr(C, 'TILE_SIZE', 40)
        width = int(base_tile_size * 0.75) # Knight might be slightly slimmer
        height = int(base_tile_size * 1.8) # Knight might be taller
        magenta_color_tuple = getattr(C, 'MAGENTA', (255,0,255))
        placeholder_image = self._create_placeholder_qpixmap(QColor(*magenta_color_tuple), text_tag)
        self.image = placeholder_image
        self._update_rect_from_image_and_pos()

    def _load_knight_animations(self) -> Dict[str, List[QPixmap]]:
        knight_animations: Dict[str, List[QPixmap]] = {}
        for anim_name_key, relative_anim_path_val in KNIGHT_ANIM_PATHS.items():
            # `resource_path` expects path relative to project root.
            # KNIGHT_ANIM_PATHS now includes "assets/" prefix.
            full_path_to_gif = resource_path(relative_anim_path_val)
            frames = load_gif_frames(full_path_to_gif)
            
            # Check if frames list is empty or the first frame is a placeholder
            if not frames or (frames and frames[0].isNull()) or \
               (len(frames) == 1 and self._is_placeholder_qpixmap(frames[0])): # Use self._is_placeholder_qpixmap
                
                is_core_anim = anim_name_key in ["idle", "run", "jump", "fall", "attack1", "hurt", "dead"]
                log_level_func = error if is_core_anim else warning # Log as error for missing core anims
                # MODIFIED: Log level for missing non-core changed to DEBUG
                if not is_core_anim: log_level_func = debug 

                log_level_func(f"EnemyKnight (ID: {self.enemy_id}): Animation '{anim_name_key}' from '{full_path_to_gif}' missing or invalid. Using code-generated placeholder.")
                
                # Define some estimated dimensions for knight placeholders
                dims = {"idle": (28,50), "run": (32,50), "jump": (36,50), "fall":(36,50),
                        "attack1": (40,50), "attack2": (42,50), "attack3": (45,50),
                        "run_attack": (48,50), "hurt": (32,50), "dead": (50,30), "death_nm": (50,30),
                        "defend": (30,50), "protect": (29,50)}
                w, h = dims.get(anim_name_key, (30,50)) # Default placeholder size for knight
                
                # Create a distinct placeholder color for knight issues if needed
                placeholder_color = QColor(200,0,0) if is_core_anim else QColor(200,100,0) # Darker red/orange
                
                placeholder_pixmap = QPixmap(w,h); placeholder_pixmap.fill(placeholder_color)
                p = QPainter(placeholder_pixmap); p.setPen(QColor(0,0,0)); p.drawLine(0,0,w,h); p.drawLine(w,0,0,h); p.end()
                frames = [placeholder_pixmap]

            knight_animations[anim_name_key] = frames
            debug(f"EnemyKnight (ID: {self.enemy_id}): Loaded/Placeholder for anim '{anim_name_key}' ({len(frames)} frames).")
        return knight_animations

    def _knight_ai_update(self, players_list_for_ai: list, current_time_ms: int):
        """Knight-specific AI logic."""
        if getattr(self, 'is_taking_hit', False) and \
           current_time_ms - getattr(self, 'hit_timer', 0) < getattr(self, 'hit_cooldown', C.ENEMY_HIT_COOLDOWN):
            if hasattr(self, 'acc'): self.acc.setX(0.0) # Stop horizontal movement if stunned
            return # In hit stun

        # Player detection
        closest_target_player = None
        min_squared_distance_to_player = float('inf')
        if not (hasattr(self, 'pos') and self.pos): return # Guard clause

        for p_cand in players_list_for_ai:
            if p_cand and getattr(p_cand, '_valid_init', False) and hasattr(p_cand, 'pos') and \
               getattr(p_cand, 'alive', False) and not getattr(p_cand, 'is_dead', True) and not getattr(p_cand, 'is_petrified', False):
                dx = p_cand.pos.x() - self.pos.x()
                dy = p_cand.pos.y() - self.pos.y()
                dist_sq = dx*dx + dy*dy
                if dist_sq < min_squared_distance_to_player:
                    min_squared_distance_to_player = dist_sq
                    closest_target_player = p_cand
        
        distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')
        
        # Vertical LOS check (simplified: player needs to be roughly on the same vertical plane)
        enemy_rect_h = self.rect.height() if hasattr(self, 'rect') else C.TILE_SIZE * 1.8 # Knight is taller
        vertical_dist = abs(closest_target_player.rect.center().y() - self.rect.center().y()) if closest_target_player and hasattr(closest_target_player,'rect') and hasattr(self,'rect') else float('inf')
        has_vertical_los = vertical_dist < enemy_rect_h * 1.1 # More lenient for taller knight

        is_player_in_attack_range = distance_to_target_player < self.attack_range and has_vertical_los
        is_player_in_detection_range = distance_to_target_player < self.detection_range and has_vertical_los

        # Post-attack pause
        if getattr(self, 'post_attack_pause_timer', 0) > 0 and current_time_ms < self.post_attack_pause_timer:
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            if self.state != 'idle': self.set_state('idle') # Use self.set_state
            return

        # Attack completion
        if getattr(self, 'is_attacking', False):
            current_attack_key = str(getattr(self, 'attack_type', 'attack1')) # Ensure it's a string
            current_attack_duration = self.attack_duration_map.get(current_attack_key, 500) # Default if key missing

            if current_time_ms - getattr(self, 'attack_timer', 0) >= current_attack_duration:
                self.is_attacking = False
                setattr(self, 'attack_type', "none") # Reset attack_type to "none" string
                self.attack_cooldown_timer = current_time_ms
                self.post_attack_pause_timer = current_time_ms + getattr(self, 'post_attack_pause_duration', 200)
                self.set_state('idle') # Use self.set_state
            if hasattr(self, 'acc'): self.acc.setX(0.0) # No horizontal movement during attack
            return

        # Ensure patrol target is set
        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            from enemy_ai_handler import set_enemy_new_patrol_target # Local import is okay for this utility
            set_enemy_new_patrol_target(self)

        # Cooldown check for next attack
        is_attack_off_cooldown = current_time_ms - getattr(self, 'attack_cooldown_timer', 0) > self.attack_cooldown_duration
        
        target_accel_x = 0.0
        target_facing_right = self.facing_right

        # --- Knight AI State Machine ---
        # Patrol Jump Logic
        if self._is_mid_patrol_jump:
            if self.on_ground: # Landed from patrol jump
                self._is_mid_patrol_jump = False
                self.set_state('idle') # Transition to idle after landing
            # No horizontal AI control during the jump physics, physics handler moves it
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            return # Let physics handle the jump/fall

        # No Player or Player out of range: Patrol
        if not closest_target_player or not is_player_in_detection_range:
            self.ai_state = 'patrolling_knight' # Knight-specific patrol AI state
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle') # Knight uses 'jump'/'fall' for jumps

            # Patrol Jump attempt
            can_attempt_jump = (current_time_ms - self.last_patrol_jump_time > self.patrol_jump_cooldown_ms)
            if self.patrol_behavior == "knight_patrol_with_jump" and \
               can_attempt_jump and self.on_ground and random.random() < self.patrol_jump_chance:
                
                self.vel.setY(self.jump_strength) # Apply jump impulse
                self.on_ground = False # No longer on ground
                self._is_mid_patrol_jump = True
                self.set_state('jump') # Knight specific jump state
                self.last_patrol_jump_time = current_time_ms
                if hasattr(self, 'acc'): self.acc.setX(0.0) # No horizontal AI input during jump
                return # Exit AI update for this frame, physics will handle jump

            # Standard Patrol Movement
            if abs(self.pos.x() - self.patrol_target_x) < 10: # Reached target
                from enemy_ai_handler import set_enemy_new_patrol_target
                set_enemy_new_patrol_target(self) # Get new target
                if self.state == 'run': self.set_state('idle') # Pause briefly at target
            
            target_facing_right = (self.patrol_target_x > self.pos.x())
            patrol_accel = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7 # Slower patrol
            target_accel_x = patrol_accel * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05 and not self._is_mid_patrol_jump : self.set_state('run')
        
        # Player in Attack Range and Cooldown Ready: Attack
        elif is_player_in_attack_range and is_attack_off_cooldown:
            self.ai_state = 'attacking_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            
            # Knight attack selection logic (example)
            chosen_attack_key = 'attack1' # Default attack
            if abs(self.vel.x()) > self.base_speed * 0.5 and 'run_attack' in self.animations and self.animations['run_attack']:
                chosen_attack_key = 'run_attack'
            elif 'attack2' in self.animations and self.animations['attack2'] and random.random() < 0.4: # More chance for attack2
                chosen_attack_key = 'attack2'
            elif 'attack3' in self.animations and self.animations['attack3'] and random.random() < 0.2:
                chosen_attack_key = 'attack3'
            
            self.set_state(chosen_attack_key) # Set state to the chosen attack key
            setattr(self, 'attack_type', chosen_attack_key) # Store the string key
            self.is_attacking = True
            self.attack_timer = current_time_ms
            
        # Player in Detection Range (but not attack range or attack on cooldown): Chase
        elif is_player_in_detection_range:
            self.ai_state = 'chasing_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            chase_accel = getattr(C, 'ENEMY_ACCEL', 0.4) # Standard chase accel
            target_accel_x = chase_accel * (1 if target_facing_right else -1)
            if self.state not in ['run', 'jump', 'fall']: self.set_state('run') # Transition to run if not already moving/airborne
        
        else: # Player out of detection range (fallback to patrol)
            self.ai_state = 'patrolling_knight_fb' # fb for fallback state name
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle')
            if abs(self.pos.x() - self.patrol_target_x) < 10:
                from enemy_ai_handler import set_enemy_new_patrol_target
                set_enemy_new_patrol_target(self)
            target_facing_right = (self.patrol_target_x > self.pos.x())
            target_accel_x = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7 * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05 and not self._is_mid_patrol_jump : self.set_state('run')


        # Apply horizontal acceleration if not jumping or attacking
        if hasattr(self, 'acc') and not self._is_mid_patrol_jump and not self.is_attacking:
            self.acc.setX(target_accel_x)
        
        # Update facing direction if not attacking or jumping
        if not getattr(self, 'is_attacking', False) and not self._is_mid_patrol_jump:
             if self.facing_right != target_facing_right:
                 self.facing_right = target_facing_right

    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive:
            return

        current_time_ms = get_knight_current_ticks_monotonic()

        # Status effects can override AI and physics
        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        if status_overrode_update:
            self.animate() # Animate even if status effect overrides
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill() # Ensure kill if death anim finished via status effect
            return

        # Handle dead state (physics for falling while dead, then kill)
        if getattr(self, 'is_dead', False):
            if self.alive(): # Death animation playing
                # Apply gravity if not on ground. Position update handled by physics.
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc'):
                    self.vel.setY(self.vel.y() + self.acc.y()) # Gravity should be in acc.y
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                
                self.animate() # Play death animation
                if getattr(self, 'death_animation_finished', False):
                    self.kill() # Mark as no longer active for game logic
            
            # Call physics even for "dead but animating" to handle falling/platform interaction
            # Pass empty list for `other_characters` to avoid dead knight interacting with others.
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            return

        # --- Knight-Specific AI Update ---
        self._knight_ai_update(players_list_for_logic, current_time_ms)

        # --- Physics and Collisions ---
        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
        )

        # --- Attack Collision Check ---
        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic)

        # --- Animation ---
        self.animate() # This will call the generic update_enemy_animation