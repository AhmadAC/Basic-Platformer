#################### START OF FILE: player_status_effects.py ####################

# player_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects on the player,
including duration checks, damage over time, and state transitions.
MODIFIED: PetrifyPlayer now adds the statue to platforms_list.
"""
# version 2.0.2 (Statue added to platforms_list)

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
    def set_player_state(player, new_state):
        if hasattr(player, 'state'): player.state = new_state
        warning(f"Fallback set_player_state used in player_status_effects.py for P{getattr(player, 'player_id', '?')} to '{new_state}'")


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

    # Player becomes petrified (this sets is_dead=True on player etc.)
    # The Player.petrify() method should handle setting internal flags.
    # If Player.petrify() doesn't call set_player_state, we might need to do it here explicitly.
    # Assuming Player.petrify() is called by set_player_state('petrified') or internally sets flags.
    if hasattr(player, 'petrify') and callable(player.petrify):
        player.petrify() # This should set player.is_petrified, player.is_dead etc.
    else: # Fallback if direct petrify method isn't preferred
        player.is_petrified = True
        player.is_stone_smashed = False
        player.is_dead = True # Petrified players are considered 'dead' for game logic
        player.current_health = 0
        player.facing_at_petrification = facing_at_moment
        player.was_crouching_when_petrified = was_crouching_at_moment
        set_player_state(player, 'petrified') # This will also update animation

    statue_center_x = player.rect.center().x()
    statue_center_y = player.rect.center().y()

    statue_props = {
        "original_entity_type": "player",
        "original_player_id": player.player_id,
        "was_crouching": was_crouching_at_moment,
        "facing_at_petrification": facing_at_moment,
        # Pass paths to player-specific stone images if they exist on the Player object
        "initial_image_path": getattr(player, 'stone_crouch_image_frame_original_path', None) if was_crouching_at_moment else getattr(player, 'stone_image_frame_original_path', None),
        "smashed_anim_path": getattr(player, 'stone_crouch_smashed_frames_original_path', None) if was_crouching_at_moment else getattr(player, 'stone_smashed_frames_original_path', None)
    }

    new_statue = Statue(statue_center_x, statue_center_y,
                        statue_id=f"player_statue_{player.player_id}_{get_current_ticks_monotonic()}",
                        properties=statue_props)

    # Transfer player's specific stone visuals to the new statue if they exist
    if was_crouching_at_moment:
        if hasattr(player, 'stone_crouch_image_frame') and player.stone_crouch_image_frame:
            new_statue.image = player.stone_crouch_image_frame.copy()
            new_statue.initial_image_frames = [player.stone_crouch_image_frame.copy()]
        if hasattr(player, 'stone_crouch_smashed_frames') and player.stone_crouch_smashed_frames:
            new_statue.smashed_frames = [f.copy() for f in player.stone_crouch_smashed_frames]
    else: # Standing petrification
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

    if not new_statue.is_smashed: # Only add non-smashed statues as platforms
        platforms_list_ref = game_elements.get("platforms_list")
        if platforms_list_ref is not None:
            platforms_list_ref.append(new_statue)
            info(f"PlayerStatusEffects (P{player_id_log}): New statue ID {new_statue.statue_id} added to platforms_list.")
        else:
            warning(f"PlayerStatusEffects (P{player_id_log}): 'platforms_list' not found in game_elements. Statue will not be solid.")
    
    # The player object itself should be effectively "killed" or removed from active processing
    # by the main game loop because player.is_dead is true and player.is_petrified is true.
    # If the player instance needs to be explicitly removed from all_renderable_objects,
    # that should happen in the game loop's entity cleanup phase.
    # For now, just ensure its alive status reflects its new state.
    player.kill() # Player is now a statue, so the "player" entity is gone.
    info(f"PlayerStatusEffects (P{player_id_log}): Player petrified, new Statue ID {new_statue.statue_id} created.")


def update_player_status_effects(player: 'PlayerClass_TYPE', current_time_ms: int) -> bool:
    player_id_log = f"P{player.player_id}"

    if player.is_stone_smashed:
        if current_time_ms - player.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
            if not player.death_animation_finished:
                player.death_animation_finished = True
            player.kill()
        return True

    if player.is_petrified:
        # Petrified players are "dead" but visually distinct.
        # Gravity for petrified statues is handled by Statue.apply_physics_step()
        return True

    # Zapped - (Add if Player class gets this status effect)
    # if getattr(player, 'is_zapped', False): ... return True

    if player.is_frozen:
        if current_time_ms - player.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
            set_player_state(player, 'defrost')
        return True
    elif player.is_defrosting:
        if current_time_ms - player.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
            player.is_defrosting = False
            set_player_state(player, 'idle' if player.on_ground else 'fall')
            return False
        return True

    if player.is_aflame:
        if current_time_ms - player.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
            set_player_state(player, 'deflame_crouch' if player.is_crouching else 'deflame')
        elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - player.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(player, 'take_damage'):
                player.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
            player.aflame_damage_last_tick = current_time_ms
    elif player.is_deflaming:
        if current_time_ms - player.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
            player.is_deflaming = False
            set_player_state(player, 'crouch' if player.is_crouching else ('idle' if player.on_ground else 'fall'))

    return False