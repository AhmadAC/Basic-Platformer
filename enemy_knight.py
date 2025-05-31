# enemy_knight.py
# -*- coding: utf-8 -*-
"""
Defines the EnemyKnight, a new type of enemy that uses specific animations
and is capable of jumping during its patrol routine.
Uses relative paths for animations, resolved via assets.resource_path.
"""
import os
import random
import math
import time
from typing import List, Optional, Any, Dict, Tuple

from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import QRectF, QPointF

import constants as C
from enemy_base import EnemyBase # Inherits core attributes and methods
from assets import load_gif_frames, resource_path # For loading animations

# Logger import (assuming logger.py is in the project root or accessible)
try:
    from logger import debug, info, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY_KNIGHT: logger.py not found. Using fallback print statements.")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

# --- Monotonic Timer ---
_start_time_knight_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_knight_monotonic) * 1000)

# Relative animation paths
# These paths are relative to the location defined by the resource_path function in assets.py
# (typically the project root in development, or the MEIPASS folder in a bundle).
KNIGHT_ANIM_PATHS = {
    "attack1":    "characters/Knight_1/attack1.gif",
    "attack2":    "characters/Knight_1/attack2.gif",
    "attack3":    "characters/Knight_1/attack3.gif",
    "dead":       "characters/Knight_1/dead.gif",
    "defend":     "characters/Knight_1/defend.gif",
    "hurt":       "characters/Knight_1/hurt.gif",
    "idle":       "characters/Knight_1/idle.gif",
    "jump":       "characters/Knight_1/jump.gif",
    "protect":    "characters/Knight_1/protect.gif",
    "run_attack": "characters/Knight_1/run attack.gif", # Note: spaces in filenames can sometimes be problematic.
    "run":        "characters/Knight_1/run.gif",
}


class EnemyKnight(EnemyBase):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[QRectF] = None,
                 enemy_id: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None):
        
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name="knight_type_specific", properties=properties)

        if not self._valid_init:
            critical(f"EnemyKnight (ID: {self.enemy_id}): Critical failure in EnemyBase super().__init__.")
            return

        self.animations: Dict[str, List[QPixmap]] = {} 
        for anim_name, relative_anim_path in KNIGHT_ANIM_PATHS.items():
            full_path = resource_path(relative_anim_path) # Resolve relative path
            frames = load_gif_frames(full_path)
            if not frames or (frames and frames[0].isNull()):
                warning(f"EnemyKnight (ID: {self.enemy_id}): Failed to load animation for '{anim_name}' from '{full_path}' (relative: '{relative_anim_path}'). Using placeholder.")
                frames = [self._create_placeholder_qpixmap(QColor(255,0,0), anim_name[:3].upper())]
            self.animations[anim_name] = frames
            debug(f"EnemyKnight (ID: {self.enemy_id}): Loaded animation '{anim_name}' with {len(frames)} frames from '{full_path}'.")

        if not self.animations.get("idle") or not self.animations["idle"][0] or self.animations["idle"][0].isNull():
            critical(f"EnemyKnight (ID: {self.enemy_id}): 'idle' animation is missing or failed to load. Knight marked as invalid.")
            self._valid_init = False 
            if self.image is None or self.image.isNull(): 
                 self.image = self._create_placeholder_qpixmap(QColor(0,0,255), "KFAIL")
                 self._update_rect_from_image_and_pos()
            return

        self.image = self.animations["idle"][0]
        self._update_rect_from_image_and_pos()

        self.max_health = self.properties.get("max_health", 150)
        self.current_health = self.max_health
        self.base_speed = self.properties.get("speed", getattr(C, 'ENEMY_RUN_SPEED_LIMIT', 5.0) * 0.75)
        self.jump_strength = self.properties.get("jump_strength", getattr(C, 'PLAYER_JUMP_STRENGTH', -15.0) * 0.65)
        self.patrol_jump_chance = self.properties.get("patrol_jump_chance", 0.015) 
        self.patrol_jump_cooldown_ms = self.properties.get("patrol_jump_cooldown_ms", 2500) 
        self.last_patrol_jump_time = 0
        self._is_mid_patrol_jump = False 

        self.attack_damage_map = {
            'attack1': self.properties.get("attack1_damage", 15),
            'attack2': self.properties.get("attack2_damage", 20),
            'attack3': self.properties.get("attack3_damage", 25),
            'run_attack': self.properties.get("run_attack_damage", 12),
        }
        self.attack_cooldown_duration = self.properties.get("attack_cooldown_duration", 1800)
        self.attack_range = self.properties.get("attack_range", C.ENEMY_ATTACK_RANGE * 1.2)
        self.detection_range = self.properties.get("detection_range", C.ENEMY_DETECTION_RANGE)
        
        if not hasattr(self, 'patrol_target_x') or self.patrol_target_x is None:
            self.patrol_target_x = self.pos.x()

        self.ai_state: str = 'patrolling'
        self.set_state('idle')
        
        info(f"EnemyKnight (ID: {self.enemy_id}) initialized. Valid: {self._valid_init}, Health: {self.current_health}/{self.max_health}")

    def set_state(self, new_state: str):
        if self.state != new_state:
            debug(f"EnemyKnight (ID: {self.enemy_id}): State changing from '{self.state}' to '{new_state}'")
            self.state = new_state
            self.current_frame = 0
            self.last_anim_update = get_current_ticks_monotonic()

    def animate(self):
        anim_key = self.state
        
        if self.is_dead: anim_key = 'dead'
        elif self.is_taking_hit: anim_key = 'hurt'
        elif self.is_attacking:
            if self.state not in self.animations: anim_key = 'attack1' 
        elif self._is_mid_patrol_jump: anim_key = 'jump'
        elif self.state == 'patrolling' or self.state == 'chasing':
            anim_key = 'run' if abs(self.vel.x()) > 0.1 else 'idle'
        
        if anim_key not in self.animations or not self.animations[anim_key]:
            anim_key = 'idle'
            if 'idle' not in self.animations or not self.animations['idle']:
                if self.image is None or self.image.isNull():
                     self.image = self._create_placeholder_qpixmap(QColor(255,0,0), "IMG!")
                return

        frames = self.animations[anim_key]
        if not frames:
            if self.image is None or self.image.isNull():
                self.image = self._create_placeholder_qpixmap(QColor(255,0,0), "FRM!")
            return

        now = get_current_ticks_monotonic()
        if now - self.last_anim_update > C.ANIM_FRAME_DURATION:
            self.last_anim_update = now
            self.current_frame += 1

            if self.current_frame >= len(frames):
                if anim_key == 'dead':
                    self.death_animation_finished = True
                    self.current_frame = len(frames) - 1 
                elif anim_key == 'jump':
                    if self.on_ground: 
                        self._is_mid_patrol_jump = False
                        self.set_state('idle') 
                    else: 
                        self.current_frame = len(frames) - 1 
                elif anim_key == 'hurt':
                    self.is_taking_hit = False
                    self.set_state('idle') 
                elif 'attack' in anim_key or anim_key == 'run_attack':
                    self.is_attacking = False
                    self.attack_cooldown_timer = now
                    self.set_state('idle') 
                else: 
                    self.current_frame = 0
            
            self.image = frames[self.current_frame]
            self._update_rect_from_image_and_pos()

    def _handle_patrol_ai(self, dt_sec: float, platforms_list: List[Any]):
        current_time = get_current_ticks_monotonic()

        if self._is_mid_patrol_jump:
            if self.on_ground:
                self._is_mid_patrol_jump = False
                self.set_state('patrolling') 
            return 

        can_attempt_jump = (current_time - self.last_patrol_jump_time > self.patrol_jump_cooldown_ms)
        jump_probability_this_tick = self.patrol_jump_chance 
        
        if can_attempt_jump and self.on_ground and random.random() < jump_probability_this_tick:
            self.vel.setY(self.jump_strength)
            self.on_ground = False
            self._is_mid_patrol_jump = True
            self.set_state('jump') 
            self.last_patrol_jump_time = current_time
            debug(f"EnemyKnight (ID: {self.enemy_id}) initiated patrol jump.")
            return 

        if self.patrol_target_x is None or abs(self.pos.x() - self.patrol_target_x) < self.rect.width() * 0.5:
            if self.patrol_area and not self.patrol_area.isNull():
                self.patrol_target_x = random.uniform(self.patrol_area.left() + self.rect.width() / 2,
                                                      self.patrol_area.right() - self.rect.width() / 2)
            else: 
                self.patrol_target_x = self.spawn_pos.x() + random.uniform(-C.ENEMY_PATROL_DIST, C.ENEMY_PATROL_DIST)
            if self.state != 'idle': self.set_state('idle')

        if self.patrol_target_x > self.pos.x():
            self.acc.setX(C.ENEMY_ACCEL)
            self.facing_right = True
        else:
            self.acc.setX(-C.ENEMY_ACCEL)
            self.facing_right = False
        
        if abs(self.vel.x()) > 0.1 and self.state != 'run':
             if self.state == 'idle' or self.state == 'patrolling':
                 self.set_state('run')
        elif abs(self.vel.x()) <= 0.1 and self.state == 'run':
            self.set_state('idle')

    def update(self, dt_sec: float, players_list: List[Any], platforms_list: List[Any],
               hazards_list: List[Any], all_enemies_list: List[Any]):
        
        if not self._valid_init or not self._alive: return

        if self.is_dead:
            if not self.death_animation_finished: self.animate()
            else: self.kill() 
            if not self.on_ground:
                self.vel.setY(self.vel.y() + (self.acc.y() * dt_sec * C.FPS) )
                self.pos.setY(self.pos.y() + (self.vel.y() * dt_sec * C.FPS) )
                self._update_rect_from_image_and_pos()
                for plat in platforms_list:
                    if self.rect.intersects(plat.rect) and self.vel.y() > 0 and self.rect.bottom() > plat.rect.top():
                        self.rect.moveBottom(plat.rect.top()); self.pos.setY(self.rect.bottom())
                        self.vel.setY(0); self.on_ground = True; break
            return

        current_time = get_current_ticks_monotonic()
        if self.is_taking_hit and current_time - self.hit_timer > self.hit_duration:
            self.is_taking_hit = False
            self.set_state('idle') 
        if self.is_taking_hit: self.acc.setX(0) 
        
        if not self.is_attacking and not self.is_taking_hit:
            closest_player = None; min_dist_sq = float('inf')
            for p in players_list:
                if p.alive() and not p.is_dead and not getattr(p, 'is_petrified', False):
                    dx = p.pos.x() - self.pos.x(); dy = p.pos.y() - self.pos.y()
                    dist_sq = dx*dx + dy*dy
                    if dist_sq < min_dist_sq: min_dist_sq = dist_sq; closest_player = p
            
            if closest_player and min_dist_sq < self.attack_range**2 and \
               (current_time - self.attack_cooldown_timer > self.attack_cooldown_duration):
                self.ai_state = 'attacking'
                # Determine attack type (e.g., 'attack1', 'run_attack')
                if abs(self.vel.x()) > self.base_speed * 0.5 and 'run_attack' in self.animations:
                    self.attack_type = 'run_attack' # Custom type string or mapped to int
                    self.set_state('run_attack')
                else:
                    self.attack_type = 'attack1' # Default to attack1
                    self.set_state('attack1') 
                self.is_attacking = True
                self.attack_timer = current_time
                self.facing_right = (closest_player.pos.x() > self.pos.x())
                self.acc.setX(0) 
            elif closest_player and min_dist_sq < self.detection_range**2:
                self.ai_state = 'chasing'; self.set_state('run')
                if closest_player.pos.x() > self.pos.x(): self.acc.setX(C.ENEMY_ACCEL); self.facing_right = True
                else: self.acc.setX(-C.ENEMY_ACCEL); self.facing_right = False
            else: 
                self.ai_state = 'patrolling'
                self._handle_patrol_ai(dt_sec, platforms_list)
        
        if not self.is_attacking and not self.is_taking_hit:
            if not self.on_ground and not self._is_mid_patrol_jump:
                self.vel.setY(self.vel.y() + self.acc.y())

            self.vel.setX(self.vel.x() + self.acc.x())
            
            if self.on_ground and abs(self.acc.x()) < 0.01 and not self._is_mid_patrol_jump:
                self.vel.setX(self.vel.x() * (1.0 - 0.15))
                if abs(self.vel.x()) < 0.1: self.vel.setX(0)

            self.vel.setX(max(-self.base_speed, min(self.base_speed, self.vel.x())))
            self.vel.setY(min(self.vel.y(), C.TERMINAL_VELOCITY_Y))
        
        scaled_dt_fps = dt_sec * C.FPS
        self.pos.setX(self.pos.x() + self.vel.x() * scaled_dt_fps)
        self.pos.setY(self.pos.y() + self.vel.y() * scaled_dt_fps)
        self._update_rect_from_image_and_pos()

        self.on_ground = False 
        for plat in platforms_list:
            if self.rect.intersects(plat.rect):
                if self.vel.x() > 0: self.rect.setRight(plat.rect.left()); self.vel.setX(0)
                elif self.vel.x() < 0: self.rect.setLeft(plat.rect.right()); self.vel.setX(0)
                self.pos.setX(self.rect.center().x()) 
                self._update_rect_from_image_and_pos()
        for plat in platforms_list:
            if self.rect.intersects(plat.rect):
                if self.vel.y() > 0: 
                    self.rect.setBottom(plat.rect.top()); self.vel.setY(0); self.on_ground = True
                    if self._is_mid_patrol_jump: self._is_mid_patrol_jump = False; self.set_state('idle')
                elif self.vel.y() < 0: 
                    self.rect.setTop(plat.rect.bottom()); self.vel.setY(0)
                self.pos.setY(self.rect.bottom()) 
                self._update_rect_from_image_and_pos()
        
        for hazard in hazards_list:
            if self.rect.intersects(hazard.rect):
                self.take_damage(getattr(C, 'LAVA_DAMAGE', 10))
                break

        if self.is_attacking and self.attack_type in self.attack_damage_map:
            # Simplified attack collision (actual damage dealing needs target iteration)
            damage_this_attack = self.attack_damage_map[str(self.attack_type)]
            # debug(f"Knight attacking, potential damage: {damage_this_attack}")
            pass

        self.animate()
        if self.ai_state not in ['chasing', 'patrolling'] or self.is_attacking or self.is_taking_hit:
            self.acc.setX(0)

    def take_damage(self, damage_amount: int):
        if self.is_dead or self.is_taking_hit: return 
        current_time = get_current_ticks_monotonic()
        self.current_health -= damage_amount
        self.is_taking_hit = True
        self.hit_timer = current_time
        self.hit_duration = C.ENEMY_HIT_STUN_DURATION 
        self.set_state('hurt') 

        if self.current_health <= 0:
            self.is_dead = True
            self.set_state('dead')
            self.vel = QPointF(0,0) 
            self.acc = QPointF(0,0)
            info(f"EnemyKnight (ID: {self.enemy_id}) died.")
        else:
            info(f"EnemyKnight (ID: {self.enemy_id}) took {damage_amount} damage. HP: {self.current_health}/{self.max_health}")