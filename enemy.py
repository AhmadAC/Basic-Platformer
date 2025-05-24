# enemy.py
# -*- coding: utf-8 -*-
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
Now includes zapped effect.
"""
# version 2.0.4 (Integrated zapped effect)

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
    print("CRITICAL ENEMY (Main): logger.py not found. Falling back to print statements.")
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
        apply_zapped_effect as apply_zapped_to_enemy, # Added zapped
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

        # Call set_enemy_new_patrol_target only if enemy is valid and has the necessary attributes
        if hasattr(self, 'pos') and hasattr(self, 'rect'): # Basic check
            set_enemy_new_patrol_target(self)
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially by Enemy class.")

        debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class initialized.")

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self): apply_aflame_to_enemy(self)
    def apply_freeze_effect(self): apply_freeze_to_enemy(self)
    def apply_zapped_effect(self): apply_zapped_to_enemy(self) # New
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
        enemy_state_handler.set_enemy_state(self, new_state)
    def animate(self): update_enemy_animation(self)

    # --- Main Update Loop ---
    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive: # Use self._alive (from EnemyBase)
            return

        current_time_ms = get_current_ticks_monotonic()

        # --- 1. Update Status Effects ---
        # update_enemy_status_effects returns True if an effect (like frozen, petrified, zapped, stomp_dying)
        # is active and should override normal AI and physics updates for this frame.
        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)

        if status_overrode_update:
            # If an overriding status effect is active (e.g., frozen, petrified, zapped, stomp_dying):
            # - Petrified and falling: Physics might still apply for falling.
            # - Zapped and falling: Physics might still apply for falling.
            # - Frozen/Stomped: Usually no physics.
            # The update_enemy_status_effects function itself should handle minimal physics if needed for these states.
            # Animation still runs for visual status effects.
            if hasattr(self, 'animate'): self.animate()
            # Check if truly "gone" after status update
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                if hasattr(self, 'kill'): self.kill()
            return # Skip normal AI, physics, and combat if an effect overrode them

        # --- 2. Handle "Normal" Death (if not overridden by a status effect) ---
        if getattr(self, 'is_dead', False): # Player is marked as dead
            if self.alive(): # Still "alive" in terms of needing processing (e.g., death animation)
                # Minimal physics for falling dead body
                if not getattr(self, 'on_ground', True) and hasattr(self, 'vel') and hasattr(self, 'acc') and hasattr(self, 'pos'):
                    self.vel.setY(self.vel.y() + self.acc.y()) # Gravity
                    self.vel.setY(min(self.vel.y(), getattr(C, 'TERMINAL_VELOCITY_Y', 18.0)))
                    # Position update (assuming vel is displacement per frame, or dt_sec*FPS is baked in)
                    self.pos.setY(self.pos.y() + self.vel.y()) # If vel is units/sec: self.pos.setY(self.pos.y() + self.vel.y() * dt_sec)
                    if hasattr(self, '_update_rect_from_image_and_pos'): self._update_rect_from_image_and_pos()

                    # Basic platform collision for falling body
                    self.on_ground = False
                    for platform_obj in platforms_list:
                        if hasattr(platform_obj, 'rect') and hasattr(self, 'rect') and self.rect.intersects(platform_obj.rect):
                            if self.vel.y() > 0 and self.rect.bottom() > platform_obj.rect.top() and \
                               (self.pos.y() - self.vel.y()) <= platform_obj.rect.top() + 1:
                                self.rect.moveBottom(platform_obj.rect.top())
                                self.on_ground = True; self.vel.setY(0.0)
                                if hasattr(self.acc, 'setY'): self.acc.setY(0.0)
                                self.pos.setY(self.rect.bottom()); break
                # Animate death sequence
                if hasattr(self, 'animate'): self.animate()
                # If death animation finished, truly kill the object
                if getattr(self, 'death_animation_finished', False):
                    if hasattr(self, 'kill'): self.kill()
            return # No further AI/Physics/Combat if dead

        # --- 3. AI Update (if no overriding status effect and not dead) ---
        enemy_ai_update(self, players_list_for_logic)

        # --- 4. Physics and Collisions (if no overriding status effect and not dead) ---
        update_enemy_physics_and_collisions(
            self, dt_sec, platforms_list, hazards_list,
            # Pass other players and *other* enemies for character collision
            players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
        )

        # --- 5. Combat (if attacking and no overriding status effect and not dead) ---
        if getattr(self, 'is_attacking', False):
            check_enemy_attack_collisions(self, players_list_for_logic) # Players are primary targets

        # --- 6. Animation (if no overriding status effect and not dead) ---
        if hasattr(self, 'animate'): self.animate()

        # --- 7. Final "is_dead" check after all updates for the frame ---
        # This handles cases where health dropped to 0 during combat or other means this frame.
        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            if hasattr(self, 'kill'): self.kill()


    def reset(self):
        super().reset() # Calls EnemyBase.reset()
        # EnemyBase.reset should set _valid_init and _alive appropriately
        if self._valid_init:
            if hasattr(self, 'pos') and hasattr(self, 'rect'): # Ensure necessary for patrol target
                 set_enemy_new_patrol_target(self)
            enemy_state_handler.set_enemy_state(self, 'idle') # Use qualified call
            debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {getattr(self, 'state', 'N/A')}, AI State: {getattr(self, 'ai_state', 'N/A')}")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): Reset called, but _valid_init is False. State not fully reset.")