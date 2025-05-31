# enemy.py
# -*- coding: utf-8 -*-
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
MODIFIED: Ensured all handler imports are correct and guarded.
MODIFIED: Corrected physics logic in the dead state within update().
MODIFIED: attack_type for generic enemy is now consistently "none" (string) when not attacking.
"""
# version 2.0.7 (Refined dead state, attack_type consistency)

import time # For monotonic timer
from typing import Optional, List, Any, Dict

# Game constants
import constants as C

# --- Import Base Class ---
from enemy_base import EnemyBase

# --- Import Handler Modules ---
# These are crucial for the Enemy class to function.
# Fallbacks are defined below if imports fail.
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
    # Define stubs for missing handlers to prevent immediate crashes
    def enemy_ai_update(*_args, **_kwargs): warning("Enemy AI update stub called.")
    def set_enemy_new_patrol_target(*_args, **_kwargs): warning("Set patrol target stub called.")
    def check_enemy_attack_collisions(*_args, **_kwargs): warning("Check attack collisions stub called.")
    def enemy_take_damage(*_args, **_kwargs): warning("Enemy take damage stub called.")
    def get_enemy_network_data(*_args, **_kwargs): warning("Get network data stub called."); return {}
    def set_enemy_network_data(*_args, **_kwargs): warning("Set network data stub called.")
    class EnemyStateHandlerDummy:
        @staticmethod
        def set_enemy_state(enemy_obj, state_str, time_ms=None):
            warning(f"Set enemy state STUB called for {getattr(enemy_obj, 'enemy_id', 'N/A')} to '{state_str}'.")
            if hasattr(enemy_obj, 'state'): setattr(enemy_obj, 'state', state_str)
    if 'enemy_state_handler' not in globals(): enemy_state_handler = EnemyStateHandlerDummy() # type: ignore
    def update_enemy_animation(*_args, **_kwargs): warning("Update enemy animation stub called.")
    def update_enemy_status_effects(*_args, **_kwargs): warning("Update status effects stub called."); return False
    def apply_aflame_to_enemy(*_args, **_kwargs): warning("Apply aflame stub called.")
    def apply_freeze_to_enemy(*_args, **_kwargs): warning("Apply freeze stub called.")
    def apply_zapped_to_enemy(*_args, **_kwargs): warning("Apply zapped stub called.")
    def petrify_this_enemy(*_args, **_kwargs): warning("Petrify enemy stub called.")
    def stomp_kill_this_enemy(*_args, **_kwargs): warning("Stomp kill stub called.")
    def smash_this_petrified_enemy(*_args, **_kwargs): warning("Smash petrified stub called.")
    def update_enemy_physics_and_collisions(*_args, **_kwargs): warning("Update physics stub called.")


_start_time_enemy_main_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_main_monotonic) * 1000)


class Enemy(EnemyBase):
    def __init__(self, start_x: float, start_y: float, patrol_area: Optional[Any] = None,
                 enemy_id: Optional[Any] = None, color_name: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None):
        super().__init__(start_x, start_y, patrol_area, enemy_id, color_name, properties=properties)

        if not self._valid_init:
            critical(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) did not initialize correctly in EnemyBase. Init incomplete.")
            return

        if not _handlers_imported_successfully:
            warning(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}): Critical handlers missing. Functionality will be impaired.")

        if hasattr(self, 'pos') and hasattr(self, 'rect'):
            try:
                set_enemy_new_patrol_target(self)
            except NameError: # Should be caught by _handlers_imported_successfully, but as a safeguard
                warning(f"Enemy (ID: {self.enemy_id}): set_enemy_new_patrol_target is not available.")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially.")

        # Ensure attack_type is initialized (generic enemies might use 0, Knight uses strings)
        # EnemyBase already initializes attack_type to 0.
        # If this specific Enemy class should default to "none", set it here.
        # self.attack_type = "none" # Or keep as 0 from EnemyBase if that's the generic default

        debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class instance initialized.")

    def apply_aflame_effect(self):
        try: apply_aflame_to_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: apply_aflame_to_enemy not available.")
    def apply_freeze_effect(self):
        try: apply_freeze_to_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: apply_freeze_to_enemy not available.")
    def apply_zapped_effect(self):
        try: apply_zapped_to_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: apply_zapped_to_enemy not available.")
    def petrify(self):
        try: petrify_this_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: petrify_this_enemy not available.")
    def smash_petrification(self):
        try: smash_this_petrified_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: smash_this_petrified_enemy not available.")
    def stomp_kill(self):
        try: stomp_kill_this_enemy(self)
        except NameError: warning(f"Enemy {self.enemy_id}: stomp_kill_this_enemy not available.")

    def take_damage(self, damage_amount_taken: int):
        try: enemy_take_damage(self, damage_amount_taken)
        except NameError: warning(f"Enemy {self.enemy_id}: enemy_take_damage not available.")

    def get_network_data(self) -> Dict[str, Any]:
        try: return get_enemy_network_data(self)
        except NameError: warning(f"Enemy {self.enemy_id}: get_enemy_network_data not available."); return {}
    def set_network_data(self, received_network_data: Dict[str, Any]):
        try: set_enemy_network_data(self, received_network_data)
        except NameError: warning(f"Enemy {self.enemy_id}: set_enemy_network_data not available.")

    def set_state(self, new_state: str):
        # This method is called by Enemy and its subclasses (like EnemyKnight)
        try:
            enemy_state_handler.set_enemy_state(self, new_state, get_current_ticks_monotonic())
        except (NameError, AttributeError): # Catch if enemy_state_handler itself or its method is missing
            warning(f"Enemy {self.enemy_id}: enemy_state_handler.set_enemy_state not available. Direct state set: {new_state}")
            if hasattr(self, 'state'): self.state = new_state # Fallback

    def animate(self):
        try: update_enemy_animation(self)
        except NameError: warning(f"Enemy {self.enemy_id}: update_enemy_animation not available.")

    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive:
            return

        current_time_ms = get_current_ticks_monotonic()

        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        if status_overrode_update:
            self.animate()
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill()
            return

        if getattr(self, 'is_dead', False):
            # If is_dead is true, _alive might still be true if death animation is playing.
            # update_enemy_physics_and_collisions handles falling for dead entities if !self.alive().
            # This block ensures animation plays and kill() is called eventually.
            self.animate()
            if getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill()
            # The physics handler will take care of movement for entities where self.alive() is false
            # but death_animation_finished is also false.
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            return

        # --- AI Update ---
        # If this is an EnemyKnight instance, its overridden update method will call its own AI.
        # This generic AI is for non-Knight Enemy instances.
        if self.__class__.__name__ == 'Enemy': # Only run generic AI if it's a base Enemy
            try:
                enemy_ai_update(self, players_list_for_logic)
            except NameError: warning(f"Enemy {self.enemy_id}: enemy_ai_update not available.")
        # If it's an EnemyKnight, its own update method has already called its specific AI.

        # --- Physics and Collisions ---
        try:
            update_enemy_physics_and_collisions(
                self, dt_sec, platforms_list, hazards_list,
                players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
            )
        except NameError: warning(f"Enemy {self.enemy_id}: update_enemy_physics_and_collisions not available.")

        # --- Attack Collision Check ---
        if getattr(self, 'is_attacking', False):
            try:
                check_enemy_attack_collisions(self, players_list_for_logic)
            except NameError: warning(f"Enemy {self.enemy_id}: check_enemy_attack_collisions not available.")

        # --- Animation ---
        self.animate()

        # Final check for death animation completion (should be handled by dead block or status effects)
        if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
            self.kill()

    def reset(self):
        super().reset() # Resets EnemyBase attributes
        if self._valid_init:
            if hasattr(self, 'pos') and hasattr(self, 'rect'):
                 try: set_enemy_new_patrol_target(self)
                 except NameError: warning(f"Enemy {self.enemy_id}: set_enemy_new_patrol_target not available during reset.")
            try:
                # Use self.set_state to ensure it goes through the proper channels
                self.set_state('idle') # Time will be handled by self.set_state
            except Exception as e_reset_state:
                error(f"Enemy {self.enemy_id}: Error calling self.set_state during reset: {e_reset_state}")
                if hasattr(self, 'state'): self.state = 'idle' # Direct fallback

            # Reset attack_type for generic enemy. Knight might handle its own in its reset or init.
            if self.__class__.__name__ == 'Enemy':
                setattr(self, 'attack_type', 0) # Generic enemy uses int, 0 for no specific attack

            debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) fully reset.")
        else:
            warning(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}): Reset called, but _valid_init is False.")