# enemy_knight.py
# -*- coding: utf-8 -*-
"""
Defines the EnemyKnight class, a specific type of enemy with unique behaviors
like patrol jumps and multiple attack types. Inherits from the generic Enemy class.
Handles loading its own animations and implements knight-specific AI.
MODIFIED: Corrected __init__ for initial image/rect.
MODIFIED: Implemented _load_knight_animations with fallbacks.
MODIFIED: Added _knight_ai_update for specific AI logic.
MODIFIED: Overrode update method to use _knight_ai_update.
MODIFIED: Ensured patrol_target_x is initialized if not set by super.
MODIFIED: Refined attack logic to use attack_type string consistently.
MODIFIED: Physics for dead falling knight is now handled in the overridden update method.
"""
# version 2.1.1 (Refined AI, attack logic, dead physics)

import os
import random
import math
import time
from typing import List, Optional, Any, Dict, Tuple

# PySide6 imports
from PySide6.QtCore import QRectF, QPointF, Qt, QSize
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont

# Game imports
import constants as C
from enemy import Enemy # Inherits from generic Enemy
from assets import load_gif_frames, resource_path

# Import handlers that EnemyKnight's update method will call directly
try:
    from enemy_status_effects import update_enemy_status_effects
    from enemy_physics_handler import update_enemy_physics_and_collisions
    from enemy_combat_handler import check_enemy_attack_collisions
    # enemy_state_handler.set_enemy_state is called via self.set_state()
    # enemy_animation_handler.update_enemy_animation is called via self.animate()
except ImportError as e_handlers:
    print(f"CRITICAL ENEMY_KNIGHT: Failed to import one or more enemy handlers: {e_handlers}")
    # Define stubs if imports fail to prevent crashes, though functionality will be broken.
    def update_enemy_status_effects(*_args, **_kwargs): return False
    def update_enemy_physics_and_collisions(*_args, **_kwargs): pass
    def check_enemy_attack_collisions(*_args, **_kwargs): pass
    # Note: set_enemy_state and update_enemy_animation are methods on self.

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_KNIGHT: logger.py not found. Using fallback print statements.")
    def info(msg, *args, **kwargs): print(f"INFO KNIGHT: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG KNIGHT: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING KNIGHT: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR KNIGHT: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL KNIGHT: {msg}")

_start_time_knight_monotonic = time.monotonic()
def get_knight_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_knight_monotonic) * 1000)

KNIGHT_ANIM_PATHS = {
    "idle": "characters/Knight_1/idle.gif",
    "run": "characters/Knight_1/run.gif",
    "jump": "characters/Knight_1/jump.gif",
    "fall": "characters/Knight_1/fall.gif",
    "attack1": "characters/Knight_1/attack1.gif",
    "attack2": "characters/Knight_1/attack2.gif",
    "attack3": "characters/Knight_1/attack3.gif",
    "run_attack": "characters/Knight_1/run attack.gif", # Filename with space
    "hurt": "characters/Knight_1/hurt.gif",
    "dead": "characters/Knight_1/dead.gif",
    "defend": "characters/Knight_1/defend.gif",
    "protect": "characters/Knight_1/protect.gif",
}
# Add other knight-specific animations like death_nm if they exist
# e.g., "death_nm": "characters/Knight_1/death_nm.gif",

class EnemyKnight(Enemy):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None,
                 _internal_class_type_override: Optional[str] = "EnemyKnight"):

        super().__init__(start_x, start_y, patrol_area, enemy_id, "knight_type_specific", properties=properties)

        if not self._valid_init:
            critical(f"EnemyKnight (ID: {self.enemy_id}): Critical failure in EnemyBase super().__init__.")
            return

        self.animations = self._load_knight_animations()

        initial_knight_image_set = False
        # Try to set initial image from 'idle', then 'fall', then 'run', then 'attack1'
        for anim_key_init in ['idle', 'fall', 'run', 'attack1']:
            if self.animations and self.animations.get(anim_key_init) and \
               self.animations[anim_key_init][0] and not self.animations[anim_key_init][0].isNull():
                self.image = self.animations[anim_key_init][0]
                self._update_rect_from_image_and_pos()
                initial_knight_image_set = True
                debug(f"EnemyKnight (ID: {self.enemy_id}): Initial image/rect set from knight's '{anim_key_init}'.")
                break
        
        if not initial_knight_image_set:
            critical(f"EnemyKnight (ID: {self.enemy_id}): No valid initial animations found for knight. Marking as invalid.")
            self._create_and_set_error_placeholder_image("K_NO_INIT_IMG")
            self._valid_init = False
            return

        # Knight-Specific Attributes
        # Max Health
        self.max_health = int(self.properties.get("max_health", getattr(C, 'ENEMY_KNIGHT_MAX_HEALTH_DEFAULT', 150)))
        self.current_health = self.max_health
        
        # Movement: Ensure these use units/frame if physics expects that.
        # If editor passes units/sec, convert here or in property getter.
        # For now, assume editor properties are already in appropriate units/frame or that base_speed is a limit.
        self.base_speed = float(self.properties.get("move_speed", getattr(C, 'ENEMY_KNIGHT_BASE_SPEED_DEFAULT', getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75)))
        self.jump_strength = float(self.properties.get("jump_strength", getattr(C, 'ENEMY_KNIGHT_JUMP_STRENGTH_DEFAULT', getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65)))
        
        # AI related patrol jump
        self.patrol_jump_chance = float(self.properties.get("patrol_jump_chance", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_CHANCE_DEFAULT', 0.015)))
        self.patrol_jump_cooldown_ms = int(self.properties.get("patrol_jump_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_PATROL_JUMP_COOLDOWN_MS_DEFAULT', 2500)))
        self.last_patrol_jump_time: int = 0
        self._is_mid_patrol_jump: bool = False

        # Combat attributes
        self.attack_damage_map: Dict[str, int] = {
            'attack1': int(self.properties.get("attack1_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK1_DAMAGE_DEFAULT', 15))),
            'attack2': int(self.properties.get("attack2_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK2_DAMAGE_DEFAULT', 20))),
            'attack3': int(self.properties.get("attack3_damage", getattr(C, 'ENEMY_KNIGHT_ATTACK3_DAMAGE_DEFAULT', 25))),
            'run_attack': int(self.properties.get("run_attack_damage", getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DAMAGE_DEFAULT', 12))),
        }
        # Animation durations for attacks (milliseconds)
        self.attack_duration_map: Dict[str, int] = {
            'attack1': int(getattr(C, 'ENEMY_KNIGHT_ATTACK1_DURATION_MS', 500)), # Default if not in properties
            'attack2': int(getattr(C, 'ENEMY_KNIGHT_ATTACK2_DURATION_MS', 600)),
            'attack3': int(getattr(C, 'ENEMY_KNIGHT_ATTACK3_DURATION_MS', 700)),
            'run_attack': int(getattr(C, 'ENEMY_KNIGHT_RUN_ATTACK_DURATION_MS', 450)),
        }
        # Override with properties if present
        for attack_key_prop in self.attack_duration_map.keys():
            prop_duration_key = f"{attack_key_prop}_duration_ms"
            if prop_duration_key in self.properties:
                self.attack_duration_map[attack_key_prop] = int(self.properties[prop_duration_key])
        
        self.attack_cooldown_duration = int(self.properties.get("attack_cooldown_ms", getattr(C, 'ENEMY_KNIGHT_ATTACK_COOLDOWN_MS_DEFAULT', 1800)))
        self.attack_range = float(self.properties.get("attack_range_px", getattr(C, 'ENEMY_KNIGHT_ATTACK_RANGE_DEFAULT', getattr(C, 'ENEMY_ATTACK_RANGE', 60.0) * 1.2)))
        self.detection_range = float(self.properties.get("detection_range_px", getattr(C, 'ENEMY_KNIGHT_DETECTION_RANGE_DEFAULT', getattr(C, 'ENEMY_DETECTION_RANGE', 200.0))))
        
        # Patrol behavior (e.g., if knight has unique patrol types)
        self.patrol_behavior = self.properties.get("patrol_behavior", "knight_patrol_with_jump")

        # Ensure patrol_target_x is initialized if not set by EnemyBase (which it should be)
        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            self.patrol_target_x = self.pos.x()
        
        # EnemyBase sets self.ai_state to 'patrolling' and self.state to 'idle'
        # If Knight starts differently, set it here.
        self.set_state('idle') # Call our own set_state if it differs, or rely on super()

        info(f"EnemyKnight (ID: {self.enemy_id}) fully initialized. Valid: {self._valid_init}, Health: {self.current_health}/{self.max_health}")

    def _create_and_set_error_placeholder_image(self, text_tag: str):
        # Creates a magenta placeholder and sets it as self.image, then updates rect.
        base_tile_size = getattr(C, 'TILE_SIZE', 40)
        width = int(base_tile_size * 0.75)
        height = int(base_tile_size * 1.5)
        pixmap = QPixmap(max(1, width), max(1, height))
        magenta_color_tuple = getattr(C, 'MAGENTA', (255,0,255))
        pixmap.fill(QColor(*magenta_color_tuple))
        painter = QPainter(pixmap)
        black_color_tuple = getattr(C, 'BLACK', (0,0,0))
        painter.setPen(QColor(*black_color_tuple))
        try:
            font = painter.font(); font.setPointSize(max(6, int(height / 5))); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text_tag)
        except Exception as e: print(f"ENEMY_KNIGHT PlaceholderFontError: {e}")
        painter.end()
        self.image = pixmap
        self._update_rect_from_image_and_pos()

    def _load_knight_animations(self) -> Dict[str, List[QPixmap]]:
        knight_animations: Dict[str, List[QPixmap]] = {}
        for anim_name_key, relative_anim_path_val in KNIGHT_ANIM_PATHS.items():
            full_path_to_gif = resource_path(relative_anim_path_val)
            frames = load_gif_frames(full_path_to_gif) # load_gif_frames returns list or placeholder on fail
            
            if not frames or (frames and frames[0].isNull()) or \
               (len(frames) == 1 and frames[0].size() == QSize(30,40) and frames[0].toImage().pixelColor(0,0) == QColor(*C.RED)): # Check if it's the red placeholder
                
                log_level_func = error if anim_name_key in ["idle", "run", "jump", "attack1", "hurt", "dead"] else warning
                log_level_func(f"EnemyKnight (ID: {self.enemy_id}): Failed to load animation for '{anim_name_key}' from '{full_path_to_gif}'. Using code-generated placeholder.")
                
                # Dimensions from provided list (approximated)
                dims = {"idle": (28,40), "run": (32,40), "jump": (36,40), "fall":(36,40), # Added fall
                        "attack1": (28,40), "attack2": (24,40), "attack3": (30,40),
                        "run_attack": (36,40), "hurt": (32,40), "dead": (31,40),
                        "defend": (30,40), "protect": (29,40)}
                w, h = dims.get(anim_name_key, (30,40)) # Default to 30x40 if key not in dims
                placeholder_color = QColor(255,0,0) if log_level_func == error else QColor(255,165,0) # Red for error, Orange for warning
                
                placeholder_pixmap = QPixmap(w,h)
                placeholder_pixmap.fill(placeholder_color)
                # Optional: Draw X on placeholder
                p = QPainter(placeholder_pixmap); p.setPen(QColor(0,0,0)); p.drawLine(0,0,w,h); p.drawLine(w,0,0,h); p.end()
                frames = [placeholder_pixmap]

            knight_animations[anim_name_key] = frames
            debug(f"EnemyKnight (ID: {self.enemy_id}): Loaded/Placeholder for anim '{anim_name_key}' ({len(frames)} frames). Path tried: '{full_path_to_gif}'")
        return knight_animations

    def _knight_ai_update(self, players_list_for_ai: list, current_time_ms: int):
        # --- Standard AI checks (copied from generic enemy_ai_handler) ---
        if getattr(self, 'is_taking_hit', False) and \
           hasattr(self, 'hit_timer') and hasattr(self, 'hit_cooldown') and \
           current_time_ms - self.hit_timer < self.hit_cooldown:
            if hasattr(self, 'acc') and hasattr(self.acc, 'setX'): self.acc.setX(0.0)
            return

        closest_target_player = None
        min_squared_distance_to_player = float('inf')
        if not (hasattr(self, 'pos') and hasattr(self.pos, 'x') and hasattr(self.pos, 'y')): return
        for player_candidate in players_list_for_ai:
            is_targetable = ( player_candidate and hasattr(player_candidate, '_valid_init') and player_candidate._valid_init and
                              hasattr(player_candidate, 'pos') and hasattr(player_candidate.pos, 'x') and hasattr(player_candidate.pos, 'y') and
                              hasattr(player_candidate, 'alive') and player_candidate.alive() and not getattr(player_candidate, 'is_dead', True) and
                              not getattr(player_candidate, 'is_petrified', False) )
            if is_targetable:
                dx = player_candidate.pos.x() - self.pos.x(); dy = player_candidate.pos.y() - self.pos.y()
                squared_dist = dx*dx + dy*dy
                if squared_dist < min_squared_distance_to_player: min_squared_distance_to_player = squared_dist; closest_target_player = player_candidate
        
        distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')
        
        enemy_rect_height = self.rect.height() if hasattr(self, 'rect') and hasattr(self.rect, 'height') else getattr(C,'TILE_SIZE', 40.0) * 1.5
        vertical_distance_to_player = abs(closest_target_player.rect.center().y() - self.rect.center().y()) if closest_target_player and hasattr(closest_target_player, 'rect') else float('inf')
        has_vertical_los = vertical_distance_to_player < enemy_rect_height * 1.0
        is_player_in_attack_range = distance_to_target_player < self.attack_range and has_vertical_los
        is_player_in_detection_range = distance_to_target_player < self.detection_range and has_vertical_los

        # Post-attack pause
        if getattr(self, 'post_attack_pause_timer', 0) > 0 and current_time_ms < self.post_attack_pause_timer:
            if hasattr(self, 'acc') and hasattr(self.acc, 'setX'): self.acc.setX(0.0)
            if self.state != 'idle': self.set_state('idle')
            return

        # Attack completion
        if getattr(self, 'is_attacking', False):
            current_attack_key = str(getattr(self, 'attack_type', 'attack1')) # attack_type stores the key like 'attack1'
            current_attack_duration = self.attack_duration_map.get(current_attack_key, 500) # Fallback duration
            if current_time_ms - getattr(self, 'attack_timer', 0) >= current_attack_duration:
                self.is_attacking = False
                setattr(self, 'attack_type', "none") # Reset attack type
                self.attack_cooldown_timer = current_time_ms
                post_attack_pause_dur = getattr(self, 'post_attack_pause_duration', 200)
                self.post_attack_pause_timer = current_time_ms + post_attack_pause_dur
                self.set_state('idle')
            if hasattr(self, 'acc') and hasattr(self.acc, 'setX'): self.acc.setX(0.0)
            return

        # Patrol target initialization
        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            from enemy_ai_handler import set_enemy_new_patrol_target # Use the generic one
            set_enemy_new_patrol_target(self)

        is_attack_off_cooldown = current_time_ms - getattr(self, 'attack_cooldown_timer', 0) > self.attack_cooldown_duration
        target_accel_x = 0.0
        target_facing_right = self.facing_right

        # Handle patrol jump if not chasing or attacking
        if self._is_mid_patrol_jump:
            if self.on_ground:
                self._is_mid_patrol_jump = False
                self.set_state('idle') # Transition to idle (or run if still moving) after landing
            self.acc.setX(0.0) # No horizontal AI control during jump
            return # AI done for this tick if mid-jump

        # AI State Machine
        if not closest_target_player or not is_player_in_detection_range: # Patrolling
            self.ai_state = 'patrolling_knight'
            if self.state not in ['run', 'idle', 'jump']: self.set_state('idle') # Ensure valid base state
            
            can_attempt_patrol_jump = (current_time_ms - self.last_patrol_jump_time > self.patrol_jump_cooldown_ms)
            if can_attempt_patrol_jump and self.on_ground and random.random() < self.patrol_jump_chance:
                self.vel.setY(self.jump_strength)
                self.on_ground = False
                self._is_mid_patrol_jump = True
                self.set_state('jump')
                self.last_patrol_jump_time = current_time_ms
                self.acc.setX(0.0) # No horizontal input during jump animation start
                return
            
            if abs(self.pos.x() - self.patrol_target_x) < 10:
                from enemy_ai_handler import set_enemy_new_patrol_target
                set_enemy_new_patrol_target(self)
                if self.state == 'run': self.set_state('idle')
            target_facing_right = (self.patrol_target_x > self.pos.x())
            # Use knight's base_speed to derive acceleration for patrol, or use a generic accel
            patrol_accel_magnitude = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7 
            target_accel_x = patrol_accel_magnitude * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05: self.set_state('run')
        
        elif is_player_in_attack_range and is_attack_off_cooldown: # Attack
            self.ai_state = 'attacking_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            
            chosen_attack_key = 'attack1' # Default
            if abs(self.vel.x()) > self.base_speed * 0.6 and 'run_attack' in self.animations and self.animations['run_attack']:
                chosen_attack_key = 'run_attack'
            elif 'attack2' in self.animations and self.animations['attack2'] and random.random() < 0.3:
                 chosen_attack_key = 'attack2'
            elif 'attack3' in self.animations and self.animations['attack3'] and random.random() < 0.15: # Less chance for attack3
                 chosen_attack_key = 'attack3'
            
            if chosen_attack_key in self.animations:
                self.set_state(chosen_attack_key)
                setattr(self, 'attack_type', chosen_attack_key)
            else:
                self.set_state('attack1'); setattr(self, 'attack_type', 'attack1')
            
            self.is_attacking = True
            self.attack_timer = current_time_ms

        elif is_player_in_detection_range: # Chase
            self.ai_state = 'chasing_knight'
            target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            chase_accel_magnitude = getattr(C, 'ENEMY_ACCEL', 0.4)
            target_accel_x = chase_accel_magnitude * (1 if target_facing_right else -1)
            if self.state not in ['run', 'jump']: self.set_state('run')
        
        else: # Default fallback to patrol if conditions met none above
            self.ai_state = 'patrolling_knight_fallback'
            if self.state not in ['run', 'idle', 'jump']: self.set_state('idle')
            # ... (patrol logic similar to first branch) ...

        # Apply horizontal acceleration and facing
        if hasattr(self, 'acc') and hasattr(self.acc, 'setX') and not self._is_mid_patrol_jump:
            self.acc.setX(target_accel_x)
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

        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        if status_overrode_update:
            self.animate()
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill()
            return

        if getattr(self, 'is_dead', False):
            if self.alive(): # If not yet killed by base class's kill()
                # Apply gravity for falling dead body
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc') and hasattr(self, 'pos'):
                    self.vel.setY(self.vel.y() + self.acc.y()) # acc.y should be gravity
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                    # Position update is handled by physics_handler now
                self.animate()
                if getattr(self, 'death_animation_finished', False):
                    self.kill()
            # Update physics even when "dead" to handle falling/landing, but no char collisions
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            return

        self._knight_ai_update(players_list_for_logic, current_time_ms)

        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
        )

        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic)

        self.animate()

        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            self.kill()

    # set_state and animate are inherited from Enemy, which call generic handlers.
    # take_damage, get_network_data, set_network_data are also inherited.
    # reset is inherited from Enemy -> EnemyBase.
    # The Knight's unique behavior is primarily driven by _knight_ai_update.