# player_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects on the player,
including duration checks, damage over time, and state transitions.
MODIFIED: PetrifyPlayer now adds the statue to platforms_list.
MODIFIED: Implements 5-second overall fire effect timeout to force 'idle'.
MODIFIED: If a player is on fire, aflame is cancelled and damage stopped if they become frozen.
MODIFIED: Calls to set_player_state now use player.set_state() for robustness.
"""
# version 2.0.5 (robust set_state calls in update_player_status_effects)

import time
from typing import TYPE_CHECKING, Dict, Any, Optional

# Game imports
import constants as C
from statue import Statue # Ensure Statue is imported

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE # For type hinting

# Logger and state handler
try:
    from logger import debug, info, warning, error
    # We keep the import here for petrify_player, but update_player_status_effects will use player.set_state
    from player_state_handler import set_player_state as psh_set_player_state
except ImportError:
    print("CRITICAL PLAYER_STATUS_EFFECTS: Failed to import logger or player_state_handler.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATUS: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PSTATUS: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATUS: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PSTATUS: {msg}")
    def psh_set_player_state(player, new_state, current_game_time_ms_param=None): # Renamed to avoid conflict if this file uses it elsewhere
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback psh_set_player_state used in player_status_effects.py for P{getattr(player, 'player_id', '?')} to '{new_state}'")


_start_time_player_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_player_status_monotonic) * 1000)


def petrify_player(player: 'PlayerClass_TYPE', game_elements: Dict[str, Any]):
    if player.is_petrified or (player.is_dead and not player.is_petrified):
        debug(f"PlayerStatusEffects (P{player.player_id}): petrify_player called but already petrified or truly dead. Ignoring.")
        return

    player_id_log = getattr(player, 'player_id', 'Unknown')
    info(f"PlayerStatusEffects (P{player_id_log}): Petrifying player.")

    facing_at_moment = player.facing_right
    was_crouching_at_moment = player.is_crouching
    
    player.is_aflame = False
    player.is_deflaming = False
    if hasattr(player, 'overall_fire_effect_start_time'):
        player.overall_fire_effect_start_time = 0

    # If Player class has its own petrify method that calls its own set_state
    if hasattr(player, 'petrify') and callable(player.petrify):
        player.petrify() 
    else: # Fallback direct manipulation + psh_set_player_state from this file's import
        player.is_petrified = True
        player.is_stone_smashed = False
        player.is_dead = True 
        player.current_health = 0
        player.facing_at_petrification = facing_at_moment
        player.was_crouching_when_petrified = was_crouching_at_moment
        psh_set_player_state(player, 'petrified', get_current_ticks_monotonic()) # Use the imported one for this specific function

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
    # This function's content is typically copied into Player.update_status_effects(self, current_time_ms)
    # Therefore, `player` becomes `self`, and `player.set_state` refers to `Player.set_state`.
    # The `set_player_state` imported at the top of this file is aliased to `psh_set_player_state`
    # to avoid ambiguity if this file were to use it for other helper functions.

    player_id_log = f"P{player.player_id}"

    # --- MODIFIED: Overall 5-second fire effect timeout ---
    if (player.is_aflame or player.is_deflaming) and \
       hasattr(player, 'overall_fire_effect_start_time') and \
       player.overall_fire_effect_start_time > 0:
        
        if current_time_ms - player.overall_fire_effect_start_time > 5000: # 5 seconds
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"force_idle_after_5s_fire_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Overall 5s fire effect duration met. Forcing state to 'idle'.")
            
            player.is_aflame = False
            player.is_deflaming = False
            player.overall_fire_effect_start_time = 0 

            player.on_ground = True 
            player.vel.setY(0)      
            if hasattr(player, 'acc') and hasattr(player.acc, 'setY'): player.acc.setY(0)
            player.set_state('idle', current_time_ms) # MODIFIED: Use player.set_state
            
            return True 
    # --- END MODIFICATION ---

    if player.is_stone_smashed:
        if current_time_ms - player.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
            if not player.death_animation_finished:
                player.death_animation_finished = True
            player.kill()
        return True

    if player.is_petrified:
        return True

    if player.is_frozen:
        # ---- NEW LOGIC: Cancel fire if frozen ----
        if player.is_aflame or player.is_deflaming:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"frozen_cancels_fire_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Player is frozen. Extinguishing active fire/deflame state.")
            
            player.is_aflame = False
            player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'):
                player.overall_fire_effect_start_time = 0
        # ---- END NEW LOGIC ----

        if current_time_ms - player.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
            player.set_state('defrost', current_time_ms) # MODIFIED: Use player.set_state
        return True 
    elif player.is_defrosting:
        if current_time_ms - player.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
            player.set_state('idle' if player.on_ground else 'fall', current_time_ms) # MODIFIED: Use player.set_state
        else:
            return True 

    if player.is_aflame:
        if current_time_ms - player.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"aflame_to_deflame_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Aflame duration ({C.PLAYER_AFLAME_DURATION_MS}ms) ended. Transitioning to 'deflame'.")
            player.set_state('deflame_crouch' if player.is_crouching else 'deflame', current_time_ms) # MODIFIED: Use player.set_state
        elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - player.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(player, 'take_damage'):
                player.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
            player.aflame_damage_last_tick = current_time_ms
    elif player.is_deflaming:
        if current_time_ms - player.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"deflame_to_normal_{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Deflame duration ({C.PLAYER_DEFLAME_DURATION_MS}ms) ended. Transitioning to normal state.")
            
            player_state_on_deflame_end = 'crouch' if player.is_crouching else ('idle' if player.on_ground else 'fall')
            
            player.is_aflame = False 
            player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'):
                player.overall_fire_effect_start_time = 0
            
            player.set_state(player_state_on_deflame_end, current_time_ms) # MODIFIED: Use player.set_state

    if player.is_dead and not player.death_animation_finished:
        if player.death_animation_finished: 
            player.kill()
        return True 

    return False