# player_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the updating of active status effects on the player,
including duration checks, damage over time, and state transitions.
"""
# version 2.0.1 (Integrated zapped effect, refined petrified/smashed logic, and return behavior)

import time
from typing import TYPE_CHECKING

# Game imports
import constants as C

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE # For type hinting

# Logger and state handler (assuming they are in the project root or accessible)
try:
    from logger import debug, info, warning
    from player_state_handler import set_player_state
except ImportError:
    print("CRITICAL PLAYER_STATUS_EFFECTS: Failed to import logger or player_state_handler.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATUS: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PSTATUS: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATUS: {msg}")
    def set_player_state(player, new_state):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used in player_status_effects.py for P{getattr(player, 'player_id', '?')} to '{new_state}'")


_start_time_player_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_status_monotonic) * 1000)


def update_player_status_effects(player: 'PlayerClass_TYPE', current_time_ms: int) -> bool:
    """
    Updates active status effects on the player.
    Returns True if a status effect is active and overrides normal updates for this frame, False otherwise.
    """
    player_id_log = f"P{player.player_id}"

    # 1. Smashed (Stone) - Terminal state, plays animation then kills.
    if player.is_stone_smashed:
        if current_time_ms - player.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
            if not player.death_animation_finished:
                debug(f"{player_id_log} StatusUpdate: Stone smashed duration ended. Marking death anim finished.")
                player.death_animation_finished = True
            player.kill()
        # Smashing animation continues, overrides other actions.
        return True

    # 2. Petrified (Stone, not smashed) - Immobile, can take damage to be smashed.
    if player.is_petrified: # Implicitly not smashed due to check above
        # Petrified players are "dead" but visually distinct.
        # Falling while petrified is handled by physics before this status update.
        # No other actions or status effects apply while petrified (until smashed).
        debug(f"{player_id_log} StatusUpdate: Petrified. Overriding normal updates.")
        return True

    # 3. Zapped - Immobilized, takes damage over time.
    if player.is_zapped:
        # Immobilize (movement physics might still apply gravity if zapped mid-air)
        player.vel.setX(0.0)
        player.acc.setX(0.0)
        if player.on_ground: # Only stop Y velocity/acceleration if on ground
            player.vel.setY(0.0)
            if hasattr(player.acc, 'setY'): player.acc.setY(0.0) # Ensure acc has setY

        if current_time_ms - player.zapped_timer_start > C.PLAYER_ZAPPED_DURATION_MS:
            debug(f"{player_id_log} StatusUpdate: Zapped duration ended.")
            player.is_zapped = False
            set_player_state(player, 'idle' if player.on_ground else 'fall')
            return False # Zapped just ended, allow normal updates for this frame's logic.
        else:
            # Apply damage over time
            if current_time_ms - player.zapped_damage_last_tick > C.PLAYER_ZAPPED_DAMAGE_INTERVAL_MS:
                debug(f"{player_id_log} StatusUpdate: Taking zapped damage.")
                if hasattr(player, 'take_damage'): # Check if method exists
                    player.take_damage(C.PLAYER_ZAPPED_DAMAGE_PER_TICK)
                player.zapped_damage_last_tick = current_time_ms
            # Zapped effect is still active and overrides normal input/movement.
            return True

    # 4. Frozen / Defrosting
    if player.is_frozen:
        if current_time_ms - player.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
            debug(f"{player_id_log} StatusUpdate: Frozen duration ended. Transitioning to defrost.")
            set_player_state(player, 'defrost')
        # Frozen overrides other actions.
        return True
    elif player.is_defrosting:
        if current_time_ms - player.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
            debug(f"{player_id_log} StatusUpdate: Defrost duration ended.")
            player.is_defrosting = False
            set_player_state(player, 'idle' if player.on_ground else 'fall')
            return False # Defrost just ended, allow normal updates.
        # Defrosting overrides other actions.
        return True

    # 5. Aflame / Deflaming - These allow movement, so they don't return True to fully override.
    # Their main job here is to transition state and apply DoT.
    if player.is_aflame:
        if current_time_ms - player.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
            debug(f"{player_id_log} StatusUpdate: Aflame duration ended. Transitioning to deflame.")
            set_player_state(player, 'deflame_crouch' if player.is_crouching else 'deflame')
        elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - player.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
            debug(f"{player_id_log} StatusUpdate: Taking aflame damage.")
            if hasattr(player, 'take_damage'):
                player.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
            player.aflame_damage_last_tick = current_time_ms
        # Aflame does not inherently return True here, as movement might still be allowed.
        # The state change to 'aflame' or 'burning' handles the visual aspect.
    elif player.is_deflaming:
        if current_time_ms - player.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
            debug(f"{player_id_log} StatusUpdate: Deflame duration ended.")
            player.is_deflaming = False
            set_player_state(player, 'crouch' if player.is_crouching else ('idle' if player.on_ground else 'fall'))
            # Deflame just ended, allow normal updates.

    # If no immobilizing or terminal status effect was active and returned True,
    # it means normal player logic (movement, input) can proceed.
    return False