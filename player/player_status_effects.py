# player/player_status_effects.py
# -*- coding: utf-8 -*-
"""
Handles the application and management of status effects on the player,
including duration checks, damage over time, and state transitions for PySide6.
Version 2.0.8 (Corrected petrify_player state setting and statue asset handling)
"""
import time
from typing import TYPE_CHECKING, Dict, Any, Optional, List

from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtCore import QPointF # Not directly used here, but common for game logic

import main_game.constants as C
from player.statue import Statue

if TYPE_CHECKING:
    from player import Player as PlayerClass_TYPE

# Logger and state handler
try:
    from main_game.logger import debug, info, warning, error, critical # Corrected import path
    # No direct import of player_state_handler.set_player_state needed here.
    # We will use player.set_state() method which calls it internally.
except ImportError:
    print("CRITICAL PLAYER_STATUS_EFFECTS: Failed to import logger from main_game.logger. Using fallback print.")
    def debug(msg, *args, **kwargs): print(f"DEBUG_PSTATUS: {msg}")
    def info(msg, *args, **kwargs): print(f"INFO_PSTATUS: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_PSTATUS: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_PSTATUS: {msg}")
    def critical(msg, *args, **kwargs): print(f"CRITICAL_PSTATUS: {msg}")

_start_time_player_status_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns milliseconds since this module was loaded, for consistent timing."""
    return int((time.monotonic() - _start_time_player_status_monotonic) * 1000)


def _get_next_state_after_effect(player: 'PlayerClass_TYPE') -> str:
    """Determines the appropriate next state after a status effect ends."""
    if not getattr(player, 'on_ground', False):
        # If airborne, usually transition to 'fall'.
        # Player animation handler might further refine to 'jump_fall_trans' if coming from a jump.
        return 'fall'
    # If on ground, default to idle. Input handler will transition to run if moving.
    return 'idle'


# --- Functions to APPLY status effects (called by other modules) ---
def apply_aflame_effect(player: 'PlayerClass_TYPE'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(player, 'is_aflame', False) or \
       getattr(player, 'is_deflaming', False) or \
       getattr(player, 'is_dead', False) or \
       getattr(player, 'is_petrified', False) or \
       getattr(player, 'is_frozen', False) or \
       getattr(player, 'is_defrosting', False) or \
       getattr(player, 'is_zapped', False):
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_aflame_blocked_P{player.player_id}"):
            debug(f"PlayerStatusEffects (P{player.player_id}): apply_aflame_effect called but already in conflicting state. Ignoring.")
        return
    
    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_aflame_success_P{player.player_id}"):
        debug(f"PlayerStatusEffects (P{player.player_id}): Applying aflame effect.")
    
    # player_state_handler (via player.set_state) will set is_aflame and related timers.
    player.set_state('aflame_crouch' if player.is_crouching else 'aflame', current_time_ms)
    
    # Ensure attack is cancelled
    if hasattr(player, 'is_attacking'): player.is_attacking = False
    if hasattr(player, 'attack_type'): setattr(player, 'attack_type', 0) # 0 for no attack

def apply_freeze_effect(player: 'PlayerClass_TYPE'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(player, 'is_frozen', False) or \
       getattr(player, 'is_defrosting', False) or \
       getattr(player, 'is_dead', False) or \
       getattr(player, 'is_petrified', False) or \
       getattr(player, 'is_aflame', False) or \
       getattr(player, 'is_deflaming', False) or \
       getattr(player, 'is_zapped', False):
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_freeze_blocked_P{player.player_id}"):
            debug(f"PlayerStatusEffects (P{player.player_id}): apply_freeze_effect called but already in conflicting state. Ignoring.")
        return
        
    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_freeze_success_P{player.player_id}"):
        debug(f"PlayerStatusEffects (P{player.player_id}): Applying freeze effect.")
    
    player.set_state('frozen', current_time_ms)
    
    if hasattr(player, 'is_attacking'): player.is_attacking = False
    if hasattr(player, 'attack_type'): setattr(player, 'attack_type', 0)
    # player_state_handler will also zero out velocity/accel for 'frozen'

def apply_zapped_effect(player: 'PlayerClass_TYPE'):
    current_time_ms = get_current_ticks_monotonic()
    if getattr(player, 'is_zapped', False) or \
       getattr(player, 'is_dead', False) or \
       getattr(player, 'is_petrified', False) or \
       getattr(player, 'is_frozen', False) or \
       getattr(player, 'is_defrosting', False) or \
       getattr(player, 'is_aflame', False) or \
       getattr(player, 'is_deflaming', False):
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_zapped_blocked_P{player.player_id}"):
            debug(f"PlayerStatusEffects (P{player.player_id}): apply_zapped_effect called but already in conflicting state. Ignoring.")
        return
    
    if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"apply_zapped_success_P{player.player_id}"):
        debug(f"PlayerStatusEffects (P{player.player_id}): Applying ZAPPED effect.")
    
    player.set_state('zapped', current_time_ms)
    
    if hasattr(player, 'is_attacking'): player.is_attacking = False
    if hasattr(player, 'attack_type'): setattr(player, 'attack_type', 0)

def petrify_player(player: 'PlayerClass_TYPE', game_elements: Dict[str, Any]):
    player_id_log = getattr(player, 'player_id', 'UnknownP')
    
    # Guard clause: if already petrified or truly dead (not from petrification), do nothing.
    if player.is_petrified or (player.is_dead and not player.is_petrified) or player.is_zapped:
        if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"petrify_blocked_{player_id_log}"):
            debug(f"PlayerStatusEffects (P{player_id_log}): petrify_player called but already handled. Ignoring.")
        return

    info(f"PlayerStatusEffects (P{player_id_log}): Petrifying player.")
    current_time = get_current_ticks_monotonic()

    # Store pre-petrification state needed for statue visuals
    player.facing_at_petrification = player.facing_right
    player.was_crouching_when_petrified = player.is_crouching

    # Critical: Set the player's logical state to 'petrified' FIRST.
    # player_state_handler will then manage is_petrified, is_dead, and clear other effects.
    player.set_state('petrified', current_time) # This calls player_state_handler

    # --- Statue Creation Logic ---
    statue_center_x = player.rect.center().x()
    statue_center_y = player.rect.center().y() # Or player.rect.bottom() if statues spawn at feet

    statue_props = {
        "original_entity_type": "player",
        "original_player_id": player.player_id,
        "was_crouching": player.was_crouching_when_petrified,
        "facing_at_petrification": player.facing_at_petrification,
        # Statue class now uses player's existing stone assets internally
    }
    new_statue = Statue(statue_center_x, statue_center_y,
                        statue_id=f"player_statue_{player.player_id}_{current_time}",
                        properties=statue_props)

    # Mirroring logic for Statue visuals
    def get_mirrored_pixmap_if_needed(original_pixmap: QPixmap, should_mirror: bool) -> QPixmap:
        if not should_mirror or original_pixmap.isNull(): return original_pixmap.copy()
        q_img = original_pixmap.toImage()
        return QPixmap.fromImage(q_img.mirrored(True, False)) if not q_img.isNull() else original_pixmap.copy()

    def get_mirrored_frames_if_needed(original_frames: List[QPixmap], should_mirror: bool) -> List[QPixmap]:
        return [get_mirrored_pixmap_if_needed(f, should_mirror) for f in original_frames if f and not f.isNull()]

    should_mirror_statue_visuals = not player.facing_at_petrification

    # Apply mirrored assets to the new_statue instance
    # The Statue class should ideally handle its own asset loading, but if Player holds them:
    if player.was_crouching_when_petrified:
        if hasattr(player, 'stone_crouch_image_frame_original') and player.stone_crouch_image_frame_original:
            new_statue.initial_image_frames = [get_mirrored_pixmap_if_needed(player.stone_crouch_image_frame_original, should_mirror_statue_visuals)]
        if hasattr(player, 'stone_crouch_smashed_frames_original') and player.stone_crouch_smashed_frames_original:
            new_statue.smashed_frames = get_mirrored_frames_if_needed(player.stone_crouch_smashed_frames_original, should_mirror_statue_visuals)
    else:
        if hasattr(player, 'stone_image_frame_original') and player.stone_image_frame_original:
            new_statue.initial_image_frames = [get_mirrored_pixmap_if_needed(player.stone_image_frame_original, should_mirror_statue_visuals)]
        if hasattr(player, 'stone_smashed_frames_original') and player.stone_smashed_frames_original:
            new_statue.smashed_frames = get_mirrored_frames_if_needed(player.stone_smashed_frames_original, should_mirror_statue_visuals)
    
    # Set initial image for the statue
    if new_statue.initial_image_frames and not new_statue.initial_image_frames[0].isNull():
        new_statue.image = new_statue.initial_image_frames[0]
    # Ensure smashed frames are also set (even if empty list, Statue handles it)
    if not new_statue.smashed_frames and hasattr(player, '_create_placeholder_qpixmap'):
        new_statue.smashed_frames = [player._create_placeholder_qpixmap(QColor(*getattr(C, 'DARK_GRAY',(50,50,50))), "SmashFail")]


    new_statue._update_rect_from_image_and_pos()

    if not new_statue._valid_init:
        error(f"PlayerStatusEffects (P{player_id_log}): Failed to initialize Statue for petrified player. Statue not added.")
        # player.kill() is called by set_state('petrified') -> player_state_handler
        return

    # Add statue to game lists
    statue_objects_list = game_elements.get("statue_objects")
    if statue_objects_list is not None: statue_objects_list.append(new_statue)
    else: warning(f"PlayerStatusEffects (P{player_id_log}): 'statue_objects' list missing. Cannot add statue.")
    
    all_renderables_list = game_elements.get("all_renderable_objects")
    if all_renderables_list is not None: all_renderables_list.append(new_statue)
    else: warning(f"PlayerStatusEffects (P{player_id_log}): 'all_renderable_objects' list missing. Statue may not render.")

    if not new_statue.is_smashed: # Solid statue acts as platform
        platforms_list_ref = game_elements.get("platforms_list")
        if platforms_list_ref is not None: platforms_list_ref.append(new_statue)
        else: warning(f"PlayerStatusEffects (P{player_id_log}): 'platforms_list' missing. Statue will not be solid.")

    # Player.kill() is implicitly handled when player.is_dead becomes True via set_state
    info(f"PlayerStatusEffects (P{player_id_log}): Player petrified, new Statue ID {new_statue.statue_id} created.")


# --- Function to UPDATE status effects ---
def update_player_status_effects(player: 'PlayerClass_TYPE', current_time_ms: int) -> bool:
    player_id_log = f"P{player.player_id}"

    # Overall 5-second fire effect timeout
    if (player.is_aflame or player.is_deflaming) and \
       hasattr(player, 'overall_fire_effect_start_time') and \
       player.overall_fire_effect_start_time > 0:
        
        if current_time_ms - player.overall_fire_effect_start_time > 5000:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"force_idle_after_5s_fire_P{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Overall 5s fire effect duration met. Forcing to normal state.")
            # player.set_state handles clearing fire flags and resetting overall_fire_effect_start_time
            player.set_state(_get_next_state_after_effect(player), current_time_ms)
            return True # Update was overridden by this status logic

    if player.is_stone_smashed:
        if current_time_ms - player.stone_smashed_timer_start > C.STONE_SMASHED_DURATION_MS:
            if not player.death_animation_finished: player.death_animation_finished = True
            player.kill() # Ensure final kill
        return True # Smashed state overrides AI

    if player.is_petrified: # Not smashed, just stone form
        # Petrified players are effectively dead and don't process other effects.
        # They might fall if airborne (handled by physics).
        return True # Petrified state overrides other logic

    # Zapped Effect
    if player.is_zapped:
        if current_time_ms - player.zapped_timer_start > C.PLAYER_ZAPPED_DURATION_MS:
            debug(f"PlayerStatusEffects ({player_id_log}): Zapped duration ended.")
            player.set_state(_get_next_state_after_effect(player), current_time_ms)
            # Fall through if zapped just ended, allowing other logic if any
        else: # Still zapped
            if C.PLAYER_ZAPPED_DAMAGE_PER_TICK > 0 and \
               current_time_ms - player.zapped_damage_last_tick > C.PLAYER_ZAPPED_DAMAGE_INTERVAL_MS:
                if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"zapped_damage_tick_P{player.player_id}"):
                    debug(f"PlayerStatusEffects ({player_id_log}): Taking zapped damage.")
                if hasattr(player, 'take_damage'): player.take_damage(C.PLAYER_ZAPPED_DAMAGE_PER_TICK)
                player.zapped_damage_last_tick = current_time_ms
            return True # Zapped state overrides other movement/action logic

    if player.is_frozen:
        if player.is_aflame or player.is_deflaming: # If frozen while on fire, extinguish
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"frozen_cancels_fire_P{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Player is frozen. Extinguishing active fire/deflame state.")
            # player_state_handler will handle clearing these if new state is 'frozen'
            player.is_aflame = False; player.is_deflaming = False
            if hasattr(player, 'overall_fire_effect_start_time'): player.overall_fire_effect_start_time = 0

        if current_time_ms - player.frozen_effect_timer > C.PLAYER_FROZEN_DURATION_MS:
            player.set_state('defrost', current_time_ms) # Transition to defrost
        return True # Frozen state (or transition to defrost) overrides other logic
    elif player.is_defrosting:
        if current_time_ms - player.frozen_effect_timer > (C.PLAYER_FROZEN_DURATION_MS + C.PLAYER_DEFROST_DURATION_MS):
            player.set_state(_get_next_state_after_effect(player), current_time_ms) # Defrost finished
        else:
            return True # Still defrosting, overrides other logic

    # Aflame / Deflaming (check after Frozen/Defrosting which can extinguish fire)
    if player.is_aflame:
        if current_time_ms - player.aflame_timer_start > C.PLAYER_AFLAME_DURATION_MS:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"aflame_to_deflame_P{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Aflame duration ended. Transitioning to deflame state.")
            player.set_state('deflame_crouch' if player.is_crouching else 'deflame', current_time_ms)
        elif C.PLAYER_AFLAME_DAMAGE_PER_TICK > 0 and \
             current_time_ms - player.aflame_damage_last_tick > C.PLAYER_AFLAME_DAMAGE_INTERVAL_MS:
            if hasattr(player, 'take_damage'): player.take_damage(C.PLAYER_AFLAME_DAMAGE_PER_TICK)
            player.aflame_damage_last_tick = current_time_ms
        # Aflame does not return True here, as AI/input should still run (with modified movement)
    elif player.is_deflaming:
        if current_time_ms - player.deflame_timer_start > C.PLAYER_DEFLAME_DURATION_MS:
            if hasattr(player, 'print_limiter') and player.print_limiter.can_log(f"deflame_to_normal_P{player.player_id}"):
                debug(f"PlayerStatusEffects ({player_id_log}): Deflame duration ended. Transitioning to normal state.")
            player.set_state(_get_next_state_after_effect(player), current_time_ms)
        # Deflaming also does not return True, AI/input still runs

    # If player is logically dead but death animation isn't finished (and not due to petrification)
    if player.is_dead and not player.death_animation_finished and not player.is_petrified:
        # The main player update loop will call player.kill() once death_animation_finished becomes true.
        # This return True means other AI/physics logic won't run while death anim plays (except gravity).
        return True

    return False # No status effect fully overrode the update this frame