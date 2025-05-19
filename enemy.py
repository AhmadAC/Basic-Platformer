#################### START OF FILE: enemy.py ####################

# enemy.py
# -*- coding: utf-8 -*-
## version 2.0.1 (PySide6 Refactor - Added missing imports)
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
"""
from typing import Optional, List # Added Optional, List

# Game constants
import constants as C # Added constants import

# --- Import Base Class (will be refactored for PySide6) ---
from enemy_base import EnemyBase

# --- Import Handler Modules (these will also need PySide6 adaptation) ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY (Main): logger.py not found. Falling back to print statements.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

try:
    from enemy_ai_handler import enemy_ai_update, set_enemy_new_patrol_target
    from enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage
    from enemy_network_handler import get_enemy_network_data, set_enemy_network_data
    from enemy_state_handler import set_enemy_state
    from enemy_animation_handler import update_enemy_animation
    from enemy_status_effects import (
        update_enemy_status_effects,
        apply_aflame_effect as apply_aflame_to_enemy,
        apply_freeze_effect as apply_freeze_to_enemy,
        petrify_enemy as petrify_this_enemy,
        stomp_kill_enemy as stomp_kill_this_enemy,
        smash_petrified_enemy as smash_this_petrified_enemy
    )
    from enemy_physics_handler import update_enemy_physics_and_collisions
except ImportError as e:
    critical(f"ENEMY (Main) CRITICAL: Failed to import one or more handler modules: {e}")
    raise

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_main = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_enemy_main) * 1000)


class Enemy(EnemyBase):
    def __init__(self, start_x: float, start_y: float, patrol_area=None, # patrol_area will be QRectF
                 enemy_id=None, color_name: Optional[str] = None):
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name)
        
        if not self._valid_init:
            critical(f"Enemy (ID: {self.enemy_id}) did not initialize correctly in EnemyBase. Main Enemy class init incomplete.")
            return
        
        set_enemy_new_patrol_target(self)
        debug(f"Enemy (ID: {self.enemy_id}, Color: {self.color_name}) main class initialized. Patrol target set.")

    def apply_aflame_effect(self): apply_aflame_to_enemy(self)
    def apply_freeze_effect(self): apply_freeze_to_enemy(self)
    def petrify(self): petrify_this_enemy(self)
    def smash_petrification(self): smash_this_petrified_enemy(self)
    def stomp_kill(self): stomp_kill_this_enemy(self)

    def take_damage(self, damage_amount_taken: int): enemy_take_damage(self, damage_amount_taken)

    def get_network_data(self): return get_enemy_network_data(self)
    def set_network_data(self, received_network_data): set_enemy_network_data(self, received_network_data)

    def set_state(self, new_state: str): set_enemy_state(self, new_state)
    def animate(self): update_enemy_animation(self)

    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list, 
               hazards_list: list,   
               all_enemies_list: list):
        if not self._valid_init or not self._alive: 
            return

        current_time_ms = get_current_ticks()

        if update_enemy_status_effects(self, current_time_ms, platforms_list): 
            if self.is_petrified and not self.is_stone_smashed and not self.on_ground:
                update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            update_enemy_animation(self)
            if self.is_dead and self.death_animation_finished and self.alive():
                self.kill()
            return

        if self.is_dead:
            if self.alive():
                if not self.death_animation_finished:
                    if not self.on_ground:
                        self.vel.setY(self.vel.y() + self.acc.y()) 
                        self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                        self.pos.setY(self.pos.y() + self.vel.y())
                        self._update_rect_from_image_and_pos() 
                        
                        self.on_ground = False
                        for platform_obj in platforms_list: 
                            if hasattr(platform_obj, 'rect') and self.rect.intersects(platform_obj.rect):
                                if self.vel.y() > 0 and self.rect.bottom() > platform_obj.rect.top() and \
                                   (self.pos.y() - self.vel.y()) <= platform_obj.rect.top() + 1:
                                    self.rect.moveBottom(platform_obj.rect.top())
                                    self.on_ground = True; self.vel.setY(0.0); self.acc.setY(0.0)
                                    self.pos.setY(self.rect.bottom()); break
                update_enemy_animation(self)
                if self.death_animation_finished:
                    self.kill()
            return

        enemy_ai_update(self, players_list_for_logic)
        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self]
        )
        if self.is_attacking:
            check_enemy_attack_collisions(self, players_list_for_logic)
        update_enemy_animation(self)

        if self.is_dead and self.death_animation_finished and self.alive():
            self.kill()

    def reset(self):
        super().reset() 
        set_enemy_new_patrol_target(self)
        set_enemy_state(self, 'idle')
        debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {self.state}, AI State: {self.ai_state}")

#################### END OF FILE: enemy.py ####################