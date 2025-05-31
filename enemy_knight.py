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
"""
# version 2.1.2 (set_state calls corrected, refined initial image fallback)

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
    _HANDLERS_AVAILABLE = True
except ImportError as e_handlers:
    print(f"CRITICAL ENEMY_KNIGHT: Failed to import one or more enemy handlers: {e_handlers}")
    _HANDLERS_AVAILABLE = False
    # Define stubs if imports fail
    def update_enemy_status_effects(*_args, **_kwargs): return False
    def update_enemy_physics_and_collisions(*_args, **_kwargs): pass
    def check_enemy_attack_collisions(*_args, **_kwargs): pass

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
    "run_attack": "characters/Knight_1/run_attack.gif", # Corrected: assume underscore, not space
    "hurt": "characters/Knight_1/hurt.gif",
    "dead": "characters/Knight_1/dead.gif",
    "death_nm": "characters/Knight_1/dead_nm.gif", # Example if you add no-movement death
    "defend": "characters/Knight_1/defend.gif",
    "protect": "characters/Knight_1/protect.gif",
}

class EnemyKnight(Enemy):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None,
                 _internal_class_type_override: Optional[str] = "EnemyKnight"):

        super().__init__(start_x, start_y, patrol_area, enemy_id, "knight_type_specific", properties=properties)

        if not self._valid_init:
            critical(f"EnemyKnight (ID: {self.enemy_id}): Critical failure in EnemyBase super().__init__.")
            return
        if not _HANDLERS_AVAILABLE:
            warning(f"EnemyKnight (ID: {self.enemy_id}): Critical handlers missing. Functionality will be impaired.")
            # Don't necessarily mark as invalid, as base might still be okay, but it won't update properly.

        self.animations = self._load_knight_animations()

        initial_knight_image_set = False
        for anim_key_init in ['idle', 'fall', 'run', 'jump', 'attack1', 'dead']: # Prioritized fallback list
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

        # --- Knight-Specific Attributes ---
        self.max_health = int(self.properties.get("max_health", getattr(C, 'ENEMY_KNIGHT_MAX_HEALTH_DEFAULT', 150)))
        self.current_health = self.max_health
        
        self.base_speed = float(self.properties.get("move_speed", getattr(C, 'ENEMY_KNIGHT_BASE_SPEED_DEFAULT', getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75)))
        self.jump_strength = float(self.properties.get("jump_strength", getattr(C, 'ENEMY_KNIGHT_JUMP_STRENGTH_DEFAULT', getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65)))
        
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
            self.patrol_target_x = self.pos.x() if hasattr(self, 'pos') and self.pos else start_x
        
        # Initial state set by EnemyBase is 'idle', AI state 'patrolling'. Knight can override if needed.
        # self.set_state('idle') # EnemyBase already does this.

        info(f"EnemyKnight (ID: {self.enemy_id}) fully initialized. Valid: {self._valid_init}, Health: {self.current_health}/{self.max_health}")

    def _create_and_set_error_placeholder_image(self, text_tag: str):
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
               (len(frames) == 1 and frames[0].size() == QSize(30,40) and frames[0].toImage().pixelColor(0,0) == QColor(*C.RED)):
                
                is_core_anim = anim_name_key in ["idle", "run", "jump", "fall", "attack1", "hurt", "dead"]
                log_level_func = error if is_core_anim else warning
                log_level_func(f"EnemyKnight (ID: {self.enemy_id}): Animation '{anim_name_key}' from '{full_path_to_gif}' missing or invalid. Using code-generated placeholder.")
                
                dims = {"idle": (28,40), "run": (32,40), "jump": (36,40), "fall":(36,40),
                        "attack1": (28,40), "attack2": (24,40), "attack3": (30,40),
                        "run_attack": (36,40), "hurt": (32,40), "dead": (31,40), "death_nm": (31,40),
                        "defend": (30,40), "protect": (29,40)}
                w, h = dims.get(anim_name_key, (30,40))
                placeholder_color = QColor(255,0,0) if is_core_anim else QColor(255,165,0)
                
                placeholder_pixmap = QPixmap(w,h); placeholder_pixmap.fill(placeholder_color)
                p = QPainter(placeholder_pixmap); p.setPen(QColor(0,0,0)); p.drawLine(0,0,w,h); p.drawLine(w,0,0,h); p.end()
                frames = [placeholder_pixmap]

            knight_animations[anim_name_key] = frames
            debug(f"EnemyKnight (ID: {self.enemy_id}): Loaded/Placeholder for anim '{anim_name_key}' ({len(frames)} frames).")
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
        enemy_rect_h = self.rect.height() if hasattr(self, 'rect') else C.TILE_SIZE * 1.5
        vertical_dist = abs(closest_target_player.rect.center().y() - self.rect.center().y()) if closest_target_player and hasattr(closest_target_player,'rect') and hasattr(self,'rect') else float('inf')
        has_vertical_los = vertical_dist < enemy_rect_h * 1.1 # Slightly more lenient
        is_player_in_attack_range = distance_to_target_player < self.attack_range and has_vertical_los
        is_player_in_detection_range = distance_to_target_player < self.detection_range and has_vertical_los

        if getattr(self, 'post_attack_pause_timer', 0) > 0 and current_time_ms < self.post_attack_pause_timer:
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            if self.state != 'idle': self.set_state('idle') # Uses Enemy.set_state
            return

        if getattr(self, 'is_attacking', False):
            current_attack_key = str(getattr(self, 'attack_type', 'attack1'))
            current_attack_duration = self.attack_duration_map.get(current_attack_key, 500)
            if current_time_ms - getattr(self, 'attack_timer', 0) >= current_attack_duration:
                self.is_attacking = False; setattr(self, 'attack_type', "none")
                self.attack_cooldown_timer = current_time_ms
                self.post_attack_pause_timer = current_time_ms + getattr(self, 'post_attack_pause_duration', 200)
                self.set_state('idle')
            if hasattr(self, 'acc'): self.acc.setX(0.0)
            return

        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            from enemy_ai_handler import set_enemy_new_patrol_target # Okay for this utility
            set_enemy_new_patrol_target(self)

        is_attack_off_cooldown = current_time_ms - getattr(self, 'attack_cooldown_timer', 0) > self.attack_cooldown_duration
        target_accel_x = 0.0; target_facing_right = self.facing_right

        if self._is_mid_patrol_jump:
            if self.on_ground:
                self._is_mid_patrol_jump = False; self.set_state('idle')
            if hasattr(self, 'acc'): self.acc.setX(0.0) # No horizontal AI control during jump physics
            return

        if not closest_target_player or not is_player_in_detection_range:
            self.ai_state = 'patrolling_knight'
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle')
            
            can_attempt_jump = (current_time_ms - self.last_patrol_jump_time > self.patrol_jump_cooldown_ms)
            if can_attempt_jump and self.on_ground and random.random() < self.patrol_jump_chance:
                self.vel.setY(self.jump_strength); self.on_ground = False
                self._is_mid_patrol_jump = True; self.set_state('jump')
                self.last_patrol_jump_time = current_time_ms; self.acc.setX(0.0)
                return
            
            if abs(self.pos.x() - self.patrol_target_x) < 10:
                from enemy_ai_handler import set_enemy_new_patrol_target
                set_enemy_new_patrol_target(self)
                if self.state == 'run': self.set_state('idle')
            target_facing_right = (self.patrol_target_x > self.pos.x())
            patrol_accel = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7
            target_accel_x = patrol_accel * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05: self.set_state('run')
        
        elif is_player_in_attack_range and is_attack_off_cooldown:
            self.ai_state = 'attacking_knight'; target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            chosen_attack = 'attack1'
            if abs(self.vel.x()) > self.base_speed * 0.5 and 'run_attack' in self.animations and self.animations['run_attack']: chosen_attack = 'run_attack'
            elif 'attack2' in self.animations and self.animations['attack2'] and random.random() < 0.4: chosen_attack = 'attack2' # Increased chance
            elif 'attack3' in self.animations and self.animations['attack3'] and random.random() < 0.2: chosen_attack = 'attack3'
            
            self.set_state(chosen_attack); setattr(self, 'attack_type', chosen_attack)
            self.is_attacking = True; self.attack_timer = current_time_ms

        elif is_player_in_detection_range:
            self.ai_state = 'chasing_knight'; target_facing_right = (closest_target_player.pos.x() > self.pos.x())
            target_accel_x = getattr(C, 'ENEMY_ACCEL', 0.4) * (1 if target_facing_right else -1)
            if self.state not in ['run', 'jump', 'fall']: self.set_state('run')
        
        else: # Fallback to patrol
            self.ai_state = 'patrolling_knight_fb' # (fb for fallback)
            if self.state not in ['run', 'idle', 'jump', 'fall']: self.set_state('idle')
            # Simplified patrol movement if target lost
            if abs(self.pos.x() - self.patrol_target_x) < 10:
                from enemy_ai_handler import set_enemy_new_patrol_target
                set_enemy_new_patrol_target(self)
            target_facing_right = (self.patrol_target_x > self.pos.x())
            target_accel_x = getattr(C, 'ENEMY_ACCEL', 0.4) * 0.7 * (1 if target_facing_right else -1)
            if self.state == 'idle' and abs(target_accel_x) > 0.05 and not self._is_mid_patrol_jump : self.set_state('run')


        if hasattr(self, 'acc') and not self._is_mid_patrol_jump and not self.is_attacking:
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
            if self.alive():
                # Apply gravity only if not on ground. Position update handled by physics.
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc'):
                    self.vel.setY(self.vel.y() + self.acc.y()) # Gravity should be in acc.y
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                self.animate()
                if getattr(self, 'death_animation_finished', False):
                    self.kill()
            # Physics for dead falling objects is handled by update_enemy_physics_and_collisions
            # when it detects is_dead=True and alive()=False.
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            return

        self._knight_ai_update(players_list_for_logic, current_time_ms)

        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
        )

        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic)

        self.animate() # Calls Enemy.animate() -> generic update_enemy_animation

        # Final check for death anim is implicitly handled by the dead block at the start on next tick
        # Or by the status_effects update if a status caused death.