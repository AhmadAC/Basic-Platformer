# player_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects on the player,
including duration checks, damage over time, and state transitions.
MODIFIED: PetrifyPlayer now adds the statue to platforms_list.
MODIFIED: Implements 5-second overall fire effect timeout to force 'idle'.
"""
# version 2.0.3 (5s fire cycle override)

import time
from typing import TYPE_CHECKING, Dict, Any, Optional # Added Dict, Any, Optional

# Game imports
import constants as C
from statue import Statue # Ensure Statue is imported

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE # For type hinting

# Logger and state handler
try:
    from logger import debug, info, warning, error
    from player_state_handler import set_player_state
except ImportError:
    print("CRITICAL PLAYER_STATUS_EFFECTS: Failed to import logger or player_state_handler.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATUS: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PSTATUS: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATUS: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PSTATUS: {msg}") # Added error for consistency
    def set_player_state(player, new_state, current_game_time_ms_param=None):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used in player_status_effects.py for P{getattr(player, 'player_id', '?')} to '{new_state}'")


_start_time_player_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_status_monotonic) * 1000)


def petrify_player(player: 'PlayerClass_TYPE', game_elements: Dict[str, Any]):
    # ... (petrify_player logic remains the same)
    if player.is_petrified or (player.is_dead and not player.is_petrified):
        debug(f"PlayerStatusEffects (P{player.player_id}): petrify_player called but already petrified or truly dead. Ignoring.")
        return

    player_id_log = getattr(player, 'player_id', 'Unknown')
    info(f"PlayerStatusEffects (P{player_id_log}): Petrifying player.")

    facing_at_moment = player.facing_right
    was_crouching_at_moment = player.is_crouching
    
    # Force clear fire states before petrifying
    player.is_aflame = False
    player.is_deflaming = False
    player.overall_fire_effect_start_time = 0

    if hasattr(player, 'petrify') and callable(player.petrify):
        player.petrify() 
    else: 
        player.is_petrified = True
        player.is_stone_smashed = False
        player.is_dead = True 
        player.current_health = 0
        player.facing_at_petrification = facing_at_moment
        player.was_crouching_when_petrified = was_crouching_at_moment
        set_player_state(player, 'petrified', get_current_ticks_monotonic()) 

    statue_center_x = player.rect.center().x()
    statue_center_y = player.rect.center().y()

    statue_props = {
        "original_entity_type": "player",
        "original_player_id": player.player_id,
        "was_crouching": was_crouching_at_moment,
        "facing_at_petrification": facing_at_moment,
        "initial_image_path": getattr(player, 'stone_crouch_image_frame_original_path', None) if was_crouching_at_moment else getattr(player, 'stone_image_frame_original_path', None),
        "smashed_anim_path": getattr(player, 'stone_crouch_smashed_frames_original_path', None) if was_crouching_at_moment else getattr(player, 'stone_smashed_frames_original_path', None)
    }

    new_statue = Statue(statue_center_x, statue_center_y,
                        statue_id=f"player_statue_{player.player_id}_{get_current_ticks_monotonic()}",
                        properties=statue_props)

    if was_crouching_at_moment:
        if hasattr(player, 'stone_crouch_image_frame') and player.stone_crouch_image_frame:
            new_statue.image = player.stone_crouch_image_frame.copy()
            new_statue.initial_image_frames = [player.stone_crouch_image_frame.copy()]
        if hasattr(player, 'stone_crouch_smashed_frames') and player.stone_crouch_smashed_frames:
            new_statue.smashed_frames = [f.copy() for f in player.stone_crouch_smashed_frames]
    else: 
        if hasattr(player, 'stone_image_frame') and player.stone_image_frame:
            new_statue.image = player.stone_image_frame.copy()
            new_statue.initial_image_frames = [player.stone_image_frame.copy()]
        if hasattr(player, 'stone_smashed_frames') and player.stone_smashed_frames:
            new_statue.smashed_frames = [f.copy() for f in player.stone_smashed_frames]
    
    new_statue._update_rect_from_image_and_pos()

    if not new_statue._valid_init:
        error(f"PlayerStatusEffects (P{player_id_log}): Failed to initialize Statue for petrified player. Player not fully removed.")
        return

    statue_objects_list = game_elements.get("statue_objects")
    if statue_objects_list is not None:
        statue_objects_list.append(new_statue)
    else:
        warning(f"PlayerStatusEffects (P{player_id_log}): 'statue_objects' list not found in game_elements. Cannot add new statue.")

    all_renderables_list = game_elements.get("all_renderable_objects")
    if all_renderables_list is not None:
        all_renderables_list.append(new_statue)
    else:
        warning(f"PlayerStatusEffects (P{player_id_log}): 'all_renderable_objects' list not found in game_elements.")

    if not new_statue.is_smashed: 
        platforms_list_ref = game_elements.get("platforms_list")
        if platforms_list_ref is not None:
            platforms_list_ref.append(new_statue)
            info(f"PlayerStatusEffects (P{player_id_log}): New statue ID {new_statue.statue_id} added to platforms_list.")
        else:
            warning(f"PlayerStatusEffects (P{player_id_log}): 'platforms_list' not found in game_elements. Statue will not be solid.")
    
    player.kill() 
    info(f"PlayerStatusEffects (P{player_id_log}): Player petrified, new Statue ID {new_statue.statue_id} created.")


def update_player_status_effects(player: 'PlayerClass_TYPE', current_time_ms: int) -> bool:
    player_id_log = f"P{player.player_id}"

    # --- MODIFIED: Overall 5-second fire effect timeout ---
    # This check takes precedence for ending fire effects.
    if (player.is_aflame or player.is_deflaming) and \
       hasattr(player, 'overall_fire_effect_start_time') and \
       player.overall_fire_effect_start_time > 0:
        
        if current_time_ms - player.overall_fire_effect_start_time > 5000: # 5 seconds
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"force_idle_after_5s_fire_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Overall 5s fire effect duration met. Forcing state to 'idle'.")
            
            # Force clear all fire-related flags
            player.is_aflame = False
            player.is_deflaming = False
            player.overall_fire_effect_start_time = 0 # Reset this specific timer

            # Force state to 'idle' and ensure player is on ground visually/logically for this state.
            # If player was airborne, this might look a bit jerky for one frame before physics corrects to 'fall'.
            # However, "MUST change to idle" implies this override.
            player.on_ground = True # Force on_ground for 'idle' state
            player.vel.setY(0)      # Stop vertical movement
            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'): player.acc.setY(0)
            set_player_state(player, 'idle', current_time_ms)
            
            return True # This change takes precedence for this frame.
    # --- END MODIFICATION ---

    if player.is_stone_smashed:
        if current_time_ms - player.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
            if not player.death_animation_finished:
                player.death_animation_finished = True
            player.kill()
        return True

    if player.is_petrified:
        # Gravity for petrified statues is handled by Statue.apply_physics_step()
        # Player object is effectively 'dead' and managed by the Statue object.
        return True

    # Zapped - (Add if Player class gets this status effect logic here)

    if player.is_frozen:
        if current_time_ms - player.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
            set_player_state(player, 'defrost', current_time_ms)
        return True # Frozen overrides other movement/actions
    elif player.is_defrosting:
        if current_time_ms - player.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
            # is_defrosting flag will be cleared by set_player_state when transitioning to idle/fall
            set_player_state(player, 'idle' if player.on_ground else 'fall', current_time_ms)
            # Fall through to allow normal logic if defrost just ended this frame.
        else:
            return True # Defrosting still overrides other movement/actions

    # Aflame/Deflame logic (will only run if the 5s overall timer hasn't forced 'idle' yet)
    if player.is_aflame:
        if current_time_ms - player.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
            # Player has been aflame for 3s, transition to deflame.
            # overall_fire_effect_start_time is NOT reset here.
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"aflame_to_deflame_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Aflame duration ({C.PLAYER_AFLAME_DURATION_MS}ms) ended. Transitioning to 'deflame'.")
            set_player_state(player, 'deflame_crouch' if player.is_crouching else 'deflame', current_time_ms)
        elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - player.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(player, 'take_damage'):
                player.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
            player.aflame_damage_last_tick = current_time_ms
        # Aflame allows controlled movement, so don't return True; let core logic run.
    elif player.is_deflaming:
        if current_time_ms - player.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
            # Deflame duration (another 3s) ended. This path is taken if the 5s overall timer didn't fire first.
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"deflame_to_normal_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Deflame duration ({C.PLAYER_DEFLAME_DURATION_MS}ms) ended. Transitioning to normal state.")
            
            player_state_on_deflame_end = 'crouch' if player.is_crouching else ('idle' if player.on_ground else 'fall')
            
            # Explicitly clear flags and overall timer here as this is the natural end of the fire cycle
            player.is_aflame = False # Should already be false
            player.is_deflaming = False
            player.overall_fire_effect_start_time = 0
            
            set_player_state(player, player_state_on_deflame_end, current_time_ms)
        # Deflaming allows controlled movement.

    # Standard death animation handling (if not petrified, etc.)
    if player.is_dead and not player.death_animation_finished:
        # This is for normal deaths, not petrified/smashed which are handled above.
        # Death animation itself might have a duration or rely on player.current_frame.
        # Player.animate() should set player.death_animation_finished when done.
        if player.death_animation_finished: # Check again in case animate() just finished it
            player.kill()
        return True # Death animation is playing, overrides normal AI/physics

    return False # No status effect fully overrode the update cycle that wasn't handled by an early return.