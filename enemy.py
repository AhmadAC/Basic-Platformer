# enemy.py
# -*- coding: utf-8 -*-
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
MODIFIED: Ensured all handler imports are correct and guarded.
MODIFIED: Corrected a minor issue in the dead state physics logic within update().
"""
# version 2.0.6 (Refined dead state physics, guarded imports)

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

_handlers_imported_successfully = True
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
    _handlers_imported_successfully = False
    # Fallback dummy functions if critical handlers are missing, to prevent crashes
    # but functionality will be severely impacted.
    def enemy_ai_update(*args, **kwargs): pass
    def set_enemy_new_patrol_target(*args, **kwargs): pass
    def check_enemy_attack_collisions(*args, **kwargs): pass
    def enemy_take_damage(*args, **kwargs): pass
    def get_enemy_network_data(*args, **kwargs): return {}
    def set_enemy_network_data(*args, **kwargs): pass
    class EnemyStateHandlerDummy:
        @staticmethod
        def set_enemy_state(*args, **kwargs): pass
    if 'enemy_state_handler' not in globals():
        enemy_state_handler = EnemyStateHandlerDummy # type: ignore
    def update_enemy_animation(*args, **kwargs): pass
    def update_enemy_status_effects(*args, **kwargs): return False
    def apply_aflame_to_enemy(*args, **kwargs): pass
    def apply_freeze_to_enemy(*args, **kwargs): pass
    def apply_zapped_to_enemy(*args, **kwargs): pass
    def petrify_this_enemy(*args, **kwargs): pass
    def stomp_kill_this_enemy(*args, **kwargs): pass
    def smash_this_petrified_enemy(*args, **kwargs): pass
    def update_enemy_physics_and_collisions(*args, **kwargs): pass
    # No need to re-raise here, as the game might attempt to run with stubs for debugging purposes.
    # However, critical errors will likely occur elsewhere.

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

        if not _handlers_imported_successfully:
            warning(f"Enemy (ID: {self.enemy_id}): One or more critical handlers failed to import. Enemy functionality will be limited.")
            # No need to mark _valid_init as False here, as EnemyBase might still be valid.
            # The stubs will prevent crashes but behavior will be wrong.

        if hasattr(self, 'pos') and hasattr(self, 'rect'):
            try:
                set_enemy_new_patrol_target(self)
            except NameError: # Fallback if set_enemy_new_patrol_target didn't import
                warning(f"Enemy (ID: {self.enemy_id}): set_enemy_new_patrol_target not available. Patrol target not set.")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially by Enemy class.")

        debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class initialized.")

    # --- Status Effect Application Methods ---
    def apply_aflame_effect(self):
        try: apply_aflame_to_enemy(self)
        except NameError: warning("apply_aflame_to_enemy not available.")
    def apply_freeze_effect(self):
        try: apply_freeze_to_enemy(self)
        except NameError: warning("apply_freeze_to_enemy not available.")
    def apply_zapped_effect(self):
        try: apply_zapped_to_enemy(self)
        except NameError: warning("apply_zapped_to_enemy not available.")
    def petrify(self):
        try: petrify_this_enemy(self)
        except NameError: warning("petrify_this_enemy not available.")
    def smash_petrification(self):
        try: smash_this_petrified_enemy(self)
        except NameError: warning("smash_this_petrified_enemy not available.")
    def stomp_kill(self):
        try: stomp_kill_this_enemy(self)
        except NameError: warning("stomp_kill_this_enemy not available.")

    # --- Combat ---
    def take_damage(self, damage_amount_taken: int):
        try: enemy_take_damage(self, damage_amount_taken)
        except NameError: warning("enemy_take_damage not available.")

    # --- Network ---
    def get_network_data(self) -> Dict[str, Any]: # Ensure return type hint matches
        try: return get_enemy_network_data(self)
        except NameError: warning("get_enemy_network_data not available."); return {}
    def set_network_data(self, received_network_data: Dict[str, Any]): # Ensure param type hint matches
        try: set_enemy_network_data(self, received_network_data)
        except NameError: warning("set_enemy_network_data not available.")

    # --- State and Animation ---
    def set_state(self, new_state: str):
        try:
            enemy_state_handler.set_enemy_state(self, new_state, get_current_ticks_monotonic())
        except (NameError, AttributeError):
            warning("enemy_state_handler.set_enemy_state not available. Setting state directly (if possible).")
            if hasattr(self, 'state'): self.state = new_state

    def animate(self):
        try: update_enemy_animation(self)
        except NameError: warning("update_enemy_animation not available.")

    # --- Main Update Loop ---
    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive:
            return

        current_time_ms = get_current_ticks_monotonic()

        status_overrode_update = False
        try:
            status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        except NameError: warning("update_enemy_status_effects not available.")

        if status_overrode_update:
            self.animate() # Still animate if status effects handled visuals
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill()
            return

        # If dead but animation not finished (e.g. falling after death, not petrified)
        if getattr(self, 'is_dead', False):
            if self.alive(): # Check if kill() hasn't been called yet
                # Basic physics for falling while dead (if not on ground)
                # Full physics for dead entities (including platform collision) is now handled by update_enemy_physics_and_collisions
                # when it sees is_dead is true but self.alive() is false (or _alive is false).
                # This block can be simplified or removed if update_enemy_physics_and_collisions handles it fully.
                self.animate()
                if getattr(self, 'death_animation_finished', False):
                    self.kill()
            # Call physics handler for dead entities to handle falling/landing
            try:
                update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, []) # No character collisions for dead
            except NameError: warning("update_enemy_physics_and_collisions not available for dead enemy.")
            return

        # AI Update
        try:
            enemy_ai_update(self, players_list_for_logic)
        except NameError: warning("enemy_ai_update not available.")

        # Physics and Collisions Update
        try:
            update_enemy_physics_and_collisions(
                self, dt_sec, platforms_list, hazards_list,
                players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
            )
        except NameError: warning("update_enemy_physics_and_collisions not available.")

        # Attack Collision Check
        if getattr(self, 'is_attacking', False):
            try:
                check_enemy_attack_collisions(self, players_list_for_logic)
            except NameError: warning("check_enemy_attack_collisions not available.")

        # Animation Update
        self.animate()

        # Check for death animation completion (redundant if dead block handles it, but safe)
        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            self.kill()


    def reset(self):
        super().reset() # Resets EnemyBase attributes
        if self._valid_init:
            if hasattr(self, 'pos') and hasattr(self, 'rect'):
                 try: set_enemy_new_patrol_target(self)
                 except NameError: warning("set_enemy_new_patrol_target not available during reset.")
            try:
                enemy_state_handler.set_enemy_state(self, 'idle', get_current_ticks_monotonic())
            except (NameError, AttributeError):
                warning("enemy_state_handler.set_enemy_state not available during reset. Setting state directly.")
                if hasattr(self, 'state'): self.state = 'idle'
            debug(f"Enemy (ID: {self.enemy_id}) fully reset. State: {getattr(self, 'state', 'N/A')}, AI State: {getattr(self, 'ai_state', 'N/A')}")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): Reset called, but _valid_init is False. State not fully reset.")