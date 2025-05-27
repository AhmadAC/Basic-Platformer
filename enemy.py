#################### START OF FILE: enemy.py ####################

# enemy.py
# -*- coding: utf-8 -*-
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
Now includes zapped effect.
MODIFIED: apply_zapped_effect call added.
"""
# version 2.0.5 (Call apply_zapped_effect from status_effects)

import time # For monotonic timer
from typing import Optional, List, Any, Dict # Ensure Optional, Dict, Any are imported

# Game constants
import constants as C

# --- Import Base Class ---
from enemy_base import EnemyBase

# --- Import Handler Modules ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL ENEMY (Main): logger.py not found. Falling back to print statements for logging.")
    def info(msg, *args, **kwargs): print(f"INFO: {msg}")
    def debug(msg, *args, **kwargs): print(f"DEBUG: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL: {msg}")

try:
    from enemy_ai_handler import enemy_ai_update, set_enemy_new_patrol_target
    from enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage
    from enemy_network_handler import get_enemy_network_data, set_enemy_network_data
    import enemy_state_handler # For qualified call: enemy_state_handler.set_enemy_state
    from enemy_animation_handler import update_enemy_animation
    from enemy_status_effects import (
        update_enemy_status_effects,
        apply_aflame_effect as apply_aflame_to_enemy,
        apply_freeze_effect as apply_freeze_to_enemy,
        apply_zapped_effect as apply_zapped_to_enemy, 
        petrify_enemy as petrify_this_enemy,
        stomp_kill_enemy as stomp_kill_this_enemy,
        smash_petrified_enemy as smash_this_petrified_enemy
    )
    from enemy_physics_handler import update_enemy_physics_and_collisions
except ImportError as e:
    critical(f"ENEMY (Main) CRITICAL: Failed to import one or more handler modules: {e}")
    raise # Re-raise to halt execution if critical handlers are missing

# --- Monotonic Timer ---
_start_time_enemy_main_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_main_monotonic) * 1000)
# --- End Monotonic Timer ---


class Enemy(EnemyBase):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[Any] = None, # patrol_area should be QRectF
                 enemy_id: Optional[Any] = None, color_name: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None):
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name, properties=properties)

        if not self._valid_init:
            critical(f"Enemy (ID: {self.enemy_id}) did not initialize correctly in EnemyBase. Main Enemy class init incomplete.")
            return

        if hasattr(self, 'pos') and hasattr(self, 'rect'):
            set_enemy_new_patrol_target(self)
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially by Enemy class.")

        debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class initialized.")

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self): apply_aflame_to_enemy(self)
    def apply_freeze_effect(self): apply_freeze_to_enemy(self)
    def apply_zapped_effect(self): apply_zapped_to_enemy(self)
    def petrify(self): petrify_this_enemy(self)
    def smash_petrification(self): smash_this_petrified_enemy(self)
    def stomp_kill(self): stomp_kill_this_enemy(self)

    # --- Combat ---
    def take_damage(self, damage_amount_taken: int): enemy_take_damage(self, damage_amount_taken)

    # --- Network ---
    def get_network_data(self): return get_enemy_network_data(self)
    def set_network_data(self, received_network_data): set_enemy_network_data(self, received_network_data)

    # --- State and Animation ---
    def set_state(self, new_state: str):
        enemy_state_handler.set_enemy_state(self, new_state, get_current_ticks_monotonic()) # Pass current time
    def animate(self): update_enemy_animation(self)

    # --- Main Update Loop ---
    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive:
            return

        current_time_ms = get_current_ticks_monotonic()

        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)

        if status_overrode_update:
            if hasattr(self, 'animate'): self.animate()
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                if hasattr(self, 'kill'): self.kill()
            return

        if getattr(self, 'is_dead', False):
            if self.alive():
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc') and hasattr(self, 'pos'):
                    self.vel.setY(self.vel.y() + self.acc.y())
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                    self.pos.setY(self.pos.y() + self.vel.y()) 
                    if hasattr(self, '_update_rect_from_image_and_pos'): self._update_rect_from_image_and_pos()

                    self.on_ground = False
                    for platform_obj in platforms_list:
                        if hasattr(platform_obj, 'rect') and hasattr(self, 'rect') and self.rect.intersects(platform_obj.rect):
                            if self.vel.y() > 0 and self.rect.bottom() > platform_obj.rect.top() and \
                               (self.pos.y() - self.vel.y()) <= platform_obj.rect.top() + 1:
                                self.rect.moveBottom(platform_obj.rect.top())
                                self.on_ground = True; self.vel.setY(0.0)
                                if hasattr(self.acc, 'setY'): self.acc.setY(0.0)
                                self.pos.setY(self.rect.bottom()); break
                if hasattr(self, 'animate'): self.animate()
                if getattr(self, 'death_animation_finished', False):
                    if hasattr(self, 'kill'): self.kill()
            return

        enemy_ai_update(self, players_list_for_logic)

        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
        )

        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic)

        if hasattr(self, 'animate'): self.animate()

        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            if hasattr(self, 'kill'): self.kill()


    def reset(self):
        super().reset()
        if self._valid_init:
            if hasattr(self, 'pos') and hasattr(self, 'rect'):
                 set_enemy_new_patrol_target(self)
            enemy_state_handler.set_enemy_state(self, 'idle', get_current_ticks_monotonic()) # Pass time
            debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {getattr(self, 'state', 'N/A')}, AI State: {getattr(self, 'ai_state', 'N/A')}")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): Reset called, but _valid_init is False. State not fully reset.")

#################### END OF FILE: enemy.py ####################