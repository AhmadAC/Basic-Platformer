# enemy.py
# -*- coding: utf-8 -*-
## version 2.0.2
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
"""
import time # For monotonic timer
from typing import Optional, List, Any # Ensure Any is imported if used for type hints

# Game constants
import constants as C

# --- Import Base Class ---
from enemy_base import EnemyBase

# --- Import Handler Modules ---
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
    raise # Re-raise to halt execution if critical handlers are missing

# --- Monotonic Timer ---
_start_time_enemy_main_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_enemy_main_monotonic) * 1000)
# --- End Monotonic Timer ---


class Enemy(EnemyBase):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[Any] = None, # patrol_area should be QRectF
                 enemy_id: Optional[Any] = None, color_name: Optional[str] = None):
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name)
        
        if not self._valid_init:
            critical(f"Enemy (ID: {self.enemy_id}) did not initialize correctly in EnemyBase. Main Enemy class init incomplete.")
            return
        
        # Call set_enemy_new_patrol_target only if enemy is valid and has the necessary attributes
        if hasattr(self, 'pos') and hasattr(self, 'rect'): # Basic check
            set_enemy_new_patrol_target(self)
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially by Enemy class.")

        debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class initialized.")

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
        if not self._valid_init or not self._alive: # Use self._alive if it's the primary flag from EnemyBase
            return

        current_time_ms = get_current_ticks_monotonic() # Use monotonic timer

        # update_enemy_status_effects returns True if an effect overrides normal updates
        if update_enemy_status_effects(self, current_time_ms, platforms_list): 
            # If petrified and falling, physics might still apply
            if getattr(self, 'is_petrified', False) and not getattr(self, 'is_stone_smashed', False) and not getattr(self, 'on_ground', True):
                # Ensure all necessary attributes for physics are present
                if hasattr(self, 'vel') and hasattr(self, 'pos') and hasattr(self, 'rect'):
                    update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            
            if hasattr(self, 'animate'): self.animate() # Animation still runs for visual status effects

            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive(): # Use self.alive()
                if hasattr(self, 'kill'): self.kill()
            return

        if getattr(self, 'is_dead', False):
            if self.alive(): # Still "alive" in terms of needing processing (e.g., death animation)
                if not getattr(self, 'death_animation_finished', True):
                    if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc') and hasattr(self, 'pos'):
                        self.vel.setY(self.vel.y() + self.acc.y()) 
                        self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                        self.pos.setY(self.pos.y() + self.vel.y())
                        if hasattr(self, '_update_rect_from_image_and_pos'): self._update_rect_from_image_and_pos()
                        
                        self.on_ground = False # Assume not on ground until collision check
                        for platform_obj in platforms_list: 
                            if hasattr(platform_obj, 'rect') and hasattr(self, 'rect') and self.rect.intersects(platform_obj.rect):
                                if self.vel.y() > 0 and self.rect.bottom() > platform_obj.rect.top() and \
                                   (self.pos.y() - self.vel.y()) <= platform_obj.rect.top() + 1: # Was above before this frame's Y move
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
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()] # Ensure others are alive
        )
        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic)
        
        if hasattr(self, 'animate'): self.animate()

        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            if hasattr(self, 'kill'): self.kill()

    def reset(self):
        super().reset() # Calls EnemyBase.reset()
        # EnemyBase.reset should set _valid_init and _alive appropriately
        if self._valid_init:
            if hasattr(self, 'pos') and hasattr(self, 'rect'): # Ensure necessary for patrol target
                 set_enemy_new_patrol_target(self)
            set_enemy_state(self, 'idle')
            debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {getattr(self, 'state', 'N/A')}, AI State: {getattr(self, 'ai_state', 'N/A')}")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): Reset called, but _valid_init is False. State not fully reset.")