#################### START OF FILE: enemy\enemy.py ####################
# enemy/enemy.py
# -*- coding: utf-8 -*-
"""
Defines the main Enemy class, which coordinates various handlers for AI,
physics, combat, state, animation, status effects, and network communication.
Inherits core attributes and methods from EnemyBase.
MODIFIED: Ensured all handler imports are correct and guarded.
MODIFIED: Corrected physics logic in the dead state within update().
MODIFIED: attack_type for generic enemy is now consistently "none" (string) when not attacking.
          This aligns with EnemyKnight and simplifies logic that might check attack_type.
MODIFIED: set_state now correctly calls self.set_state to ensure proper method dispatch
          if overridden in subclasses (though EnemyBase has the primary set_state).
MODIFIED: Logger fallback improved for clarity if main logger fails.
"""
# version 2.0.8 (Consistent "none" attack_type, self.set_state usage, logger fallback)

import time # For monotonic timer
from typing import Optional, List, Any, Dict

# --- Project Root Setup ---
import os
import sys
_ENEMY_PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_FOR_ENEMY_PY = os.path.dirname(_ENEMY_PY_FILE_DIR)
if _PROJECT_ROOT_FOR_ENEMY_PY not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FOR_ENEMY_PY)
# --- End Project Root Setup ---

# Game constants
import main_game.constants as C

# --- Import Base Class ---
try:
    from enemy.enemy_base import EnemyBase # Relative import if enemy_base is in the same package
except ImportError:
    # Fallback if running standalone or structure is different
    from enemy_base import EnemyBase # type: ignore

# --- Logger Setup ---
# Use a local fallback logger first, then try to alias the project's logger.
import logging
_enemy_logger_instance = logging.getLogger(__name__ + "_enemy_internal_fallback")
if not _enemy_logger_instance.hasHandlers():
    _handler_enemy_fb = logging.StreamHandler(sys.stdout)
    _formatter_enemy_fb = logging.Formatter('ENEMY (InternalFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    _handler_enemy_fb.setFormatter(_formatter_enemy_fb)
    _enemy_logger_instance.addHandler(_handler_enemy_fb)
    _enemy_logger_instance.setLevel(logging.DEBUG)
    _enemy_logger_instance.propagate = False

def _fallback_log_info(msg, *args, **kwargs): _enemy_logger_instance.info(msg, *args, **kwargs)
def _fallback_log_debug(msg, *args, **kwargs): _enemy_logger_instance.debug(msg, *args, **kwargs)
def _fallback_log_warning(msg, *args, **kwargs): _enemy_logger_instance.warning(msg, *args, **kwargs)
def _fallback_log_error(msg, *args, **kwargs): _enemy_logger_instance.error(msg, *args, **kwargs)
def _fallback_log_critical(msg, *args, **kwargs): _enemy_logger_instance.critical(msg, *args, **kwargs)

info = _fallback_log_info; debug = _fallback_log_debug; warning = _fallback_log_warning;
error = _fallback_log_error; critical = _fallback_log_critical

try:
    from main_game.logger import info as project_info, debug as project_debug, \
                               warning as project_warning, error as project_error, \
                               critical as project_critical
    info = project_info; debug = project_debug; warning = project_warning;
    error = project_error; critical = project_critical
    debug("Enemy (Main): Successfully aliased project's logger.")
except ImportError:
    critical("CRITICAL ENEMY (Main): Failed to import logger from main_game.logger. Using internal fallback.")
except Exception as e_logger_init_enemy:
    critical(f"CRITICAL ENEMY (Main): Unexpected error during logger setup from main_game.logger: {e_logger_init_enemy}. Using internal fallback.")
# --- End Logger Setup ---


# --- Import Handler Modules ---
_handlers_imported_successfully = True
try:
    # Assuming handlers are in the same 'enemy' package
    from enemy.enemy_ai_handler import enemy_ai_update, set_enemy_new_patrol_target
    from enemy.enemy_combat_handler import check_enemy_attack_collisions, enemy_take_damage
    from enemy.enemy_network_handler import get_enemy_network_data, set_enemy_network_data
    from enemy import enemy_state_handler # For qualified call: enemy_state_handler.set_enemy_state
    from enemy.enemy_animation_handler import update_enemy_animation
    from enemy.enemy_status_effects import (
        update_enemy_status_effects,
        apply_aflame_effect as apply_aflame_to_enemy,
        apply_freeze_effect as apply_freeze_to_enemy,
        apply_zapped_effect as apply_zapped_to_enemy,
        petrify_enemy as petrify_this_enemy,
        stomp_kill_enemy as stomp_kill_this_enemy,
        smash_petrified_enemy as smash_this_petrified_enemy
    )
    from enemy.enemy_physics_handler import update_enemy_physics_and_collisions
except ImportError as e:
    critical(f"ENEMY (Main) CRITICAL: Failed to import one or more handler modules (likely from enemy.enemy package): {e}")
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
    if 'enemy_state_handler' not in globals() or enemy_state_handler is None: # Check if it was defined
        enemy_state_handler = EnemyStateHandlerDummy() # type: ignore
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
            except NameError:
                warning(f"Enemy (ID: {self.enemy_id}): set_enemy_new_patrol_target is not available.")
        else:
            warning(f"Enemy (ID: {self.enemy_id}): pos or rect not fully initialized by EnemyBase. Patrol target not set initially.")

        # Generic enemies will use string "none" for attack_type when not actively attacking.
        # Specific attack types (like "attack1" for Knight) will be set by state transitions.
        # This makes it consistent with how EnemyKnight handles its attack_type.
        self.attack_type: str = "none"

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
        """
        Centralized method to set the enemy's state.
        This calls the set_enemy_state function from the enemy_state_handler module.
        Subclasses (like EnemyKnight) might override this if they have very specific
        state pre-processing, but generally, they should also call super().set_state()
        or directly call the handler function.
        """
        try:
            # Ensure enemy_state_handler is the actual module, not the dummy
            if hasattr(enemy_state_handler, 'set_enemy_state') and callable(enemy_state_handler.set_enemy_state):
                enemy_state_handler.set_enemy_state(self, new_state, get_current_ticks_monotonic())
            else: # Fallback if the method within the (potentially dummy) handler is missing
                raise NameError("enemy_state_handler.set_enemy_state not callable")
        except (NameError, AttributeError) as e_set_state_call:
            warning(f"Enemy {self.enemy_id}: Error calling enemy_state_handler.set_enemy_state: {e_set_state_call}. Direct state set: {new_state}")
            if hasattr(self, 'state'): self.state = new_state # Direct fallback

    def animate(self):
        try: update_enemy_animation(self)
        except NameError: warning(f"Enemy {self.enemy_id}: update_enemy_animation not available.")

    def update(self, dt_sec: float, players_list_for_logic: list,
               platforms_list: list,
               hazards_list: list,
               all_enemies_list: list):
        if not self._valid_init or not self._alive: # Use _alive from EnemyBase
            return

        current_time_ms = get_current_ticks_monotonic()

        status_overrode_update = update_enemy_status_effects(self, current_time_ms, platforms_list)
        if status_overrode_update:
            self.animate()
            if getattr(self, 'is_dead', False) and getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill() # Calls EnemyBase.kill() which sets _alive = False
            return

        if getattr(self, 'is_dead', False):
            # Logic for when the enemy is marked as 'is_dead' but might still be animating or falling.
            # The main physics update handles movement if self.alive() is false.
            update_enemy_physics_and_collisions(self, dt_sec, platforms_list, hazards_list, [])
            self.animate() # Continue playing death animation
            if getattr(self, 'death_animation_finished', False) and self.alive():
                self.kill() # Mark as no longer active
            return

        # --- AI Update ---
        # This generic AI is for non-Knight Enemy instances.
        # EnemyKnight will have its own update method that calls its specific AI.
        if self.__class__.__name__ == 'Enemy':
            try: enemy_ai_update(self, players_list_for_logic)
            except NameError: warning(f"Enemy {self.enemy_id}: enemy_ai_update not available.")
        # Note: If this is an EnemyKnight instance, its overridden `update` method
        # should have already called its specific AI logic.

        # --- Physics and Collisions ---
        try:
            update_enemy_physics_and_collisions(
                self, dt_sec, platforms_list, hazards_list,
                players_list_for_logic + [e for e in all_enemies_list if e is not self and hasattr(e, 'alive') and e.alive()]
            )
        except NameError: warning(f"Enemy {self.enemy_id}: update_enemy_physics_and_collisions not available.")

        # --- Attack Collision Check ---
        if getattr(self, 'is_attacking', False):
            try: check_enemy_attack_collisions(self, players_list_for_logic)
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

            # Use self.set_state to ensure it goes through the proper channels (and its own potential override)
            self.set_state('idle')

            # Reset attack_type. Generic enemy uses "none", Knight might set its own in its reset.
            if self.__class__.__name__ == 'Enemy':
                self.attack_type = "none" # Standardize to string "none"

            debug(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}) main class instance fully reset.")
        else:
            warning(f"Enemy (ID: {self.enemy_id}, Color: {getattr(self, 'color_name', 'N/A')}): Reset called, but _valid_init is False.")

#################### END OF FILE: enemy/enemy.py ####################