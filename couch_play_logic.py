#################### START OF FILE: couch_play_logic.py ####################

# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.2 (Corrected pruning of all_renderable_objects to keep static tiles)

import time
from typing import Dict, List, Any, Optional

try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL COUCH_PLAY_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")

import constants as C
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue
import config as game_config

# --- ADD THESE IMPORTS ---
from tiles import Platform, Ladder, Lava
# --- END OF ADDED IMPORTS ---

_start_time_couch_play_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_couch_play_monotonic) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any,
    get_p1_input_callback: callable,
    get_p2_input_callback: callable,
    process_qt_events_callback: callable,
    dt_sec_provider: callable,
    show_status_message_callback: Optional[callable] = None
    ):
    p1: Optional[Any] = game_elements_ref.get("player1")
    p2: Optional[Any] = game_elements_ref.get("player2")
    
    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    p1_action_events: Dict[str, bool] = {}
    if p1 and p1._valid_init:
        p1_action_events = get_p1_input_callback(p1, game_elements_ref.get("platforms_list", []))

    p2_action_events: Dict[str, bool] = {}
    if p2 and p2._valid_init and hasattr(p2, 'control_scheme') and p2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(p2, game_elements_ref.get("platforms_list", []))

    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        info("Couch Play: Pause action detected. Signaling app to exit mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        return False # Signal to stop the game mode

    host_requested_reset = p1_action_events.get("reset", False)
    p2_requested_reset = p2_action_events.get("reset", False)
    
    if host_requested_reset or p2_requested_reset:
        info("Couch Play: Game state reset initiated.")
        game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
        # Ensure players are re-added to renderables if reset made them non-alive temporarily
        all_renderables = game_elements_ref.get("all_renderable_objects", []) # Get a fresh reference
        if p1 and p1._valid_init and not p1.alive() and p1 not in all_renderables: all_renderables.append(p1)
        if p2 and p2._valid_init and not p2.alive() and p2 not in all_renderables: all_renderables.append(p2)


    # --- Player Updates ---
    if p1 and p1._valid_init: 
        other_players_for_p1 = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
        p1.game_elements_ref_for_projectiles = game_elements_ref 
        p1.update(dt_sec, game_elements_ref.get("platforms_list", []),
                  game_elements_ref.get("ladders_list", []),
                  game_elements_ref.get("hazards_list", []),
                  other_players_for_p1,
                  game_elements_ref.get("enemy_list", []))

    if p2 and p2._valid_init:
        other_players_for_p2 = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
        p2.game_elements_ref_for_projectiles = game_elements_ref
        p2.update(dt_sec, game_elements_ref.get("platforms_list", []),
                  game_elements_ref.get("ladders_list", []),
                  game_elements_ref.get("hazards_list", []),
                  other_players_for_p2,
                  game_elements_ref.get("enemy_list", []))

    # --- Enemy Updates ---
    active_players_for_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
    # Create a copy for iteration if enemies can be removed during update
    for enemy_couch in list(game_elements_ref.get("enemy_list", [])): 
        if enemy_couch._valid_init: # Ensure enemy itself is valid before updating
            if hasattr(enemy_couch, 'is_petrified') and enemy_couch.is_petrified:
                if hasattr(enemy_couch, 'update_enemy_status_effects'):
                     enemy_couch.update_enemy_status_effects(current_game_time_ms, game_elements_ref.get("platforms_list", []))
                if hasattr(enemy_couch, 'animate'): enemy_couch.animate()
                if enemy_couch.is_dead and hasattr(enemy_couch,'death_animation_finished') and enemy_couch.death_animation_finished and enemy_couch.alive():
                    enemy_couch.kill()
                continue

            enemy_couch.update(dt_sec, active_players_for_ai,
                               game_elements_ref.get("platforms_list", []),
                               game_elements_ref.get("hazards_list", []),
                               game_elements_ref.get("enemy_list", [])) # Pass current list of enemies for interactions
            if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
               enemy_couch.death_animation_finished and enemy_couch.alive():
                enemy_couch.kill()
    
    # Prune dead enemies from main list and all_renderable_objects
    game_elements_ref["enemy_list"][:] = [e for e in game_elements_ref.get("enemy_list", []) if e.alive()]
    # This specific pruning of Enemy from all_renderables might be redundant if the generic one below works
    # game_elements_ref["all_renderable_objects"] = [obj for obj in game_elements_ref.get("all_renderable_objects", []) if not (isinstance(obj, Enemy) and not obj.alive())]

    # --- Statue Updates ---
    statue_list_couch: List[Statue] = game_elements_ref.get("statue_objects", [])
    for statue_instance in list(statue_list_couch):
        if hasattr(statue_instance, 'update'):
            statue_instance.update(dt_sec)
            # Pruning statues is now handled by the generic alive check below

    # --- Projectile Updates ---
    hittable_targets_couch_list: List[Any] = []
    if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_targets_couch_list.append(p1)
    if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_targets_couch_list.append(p2)
    for enemy_target in game_elements_ref.get("enemy_list", []): # Use the already pruned enemy_list
        if enemy_target and enemy_target.alive() and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_couch_list.append(enemy_target)
    for statue_target_couch in game_elements_ref.get("statue_objects", []):
        if statue_target_couch.alive() and hasattr(statue_target_couch, 'is_smashed') and not statue_target_couch.is_smashed:
            hittable_targets_couch_list.append(statue_target_couch)
    
    projectiles_list_ref: List[Any] = game_elements_ref.get("projectiles_list", [])
    for proj_instance in list(projectiles_list_ref):
        if hasattr(proj_instance, 'update'):
            proj_instance.update(dt_sec, game_elements_ref.get("platforms_list", []), hittable_targets_couch_list)
            # Pruning projectiles is handled by the generic alive check below

    # --- Collectible Updates (Chest) ---
    collectible_list_ref: List[Chest] = game_elements_ref.get("collectible_list", [])
    for collectible in list(collectible_list_ref):
        if hasattr(collectible, 'update'):
            collectible.update(dt_sec)
            # Pruning collectibles handled by generic alive check below

    # --- Chest Interaction Logic ---
    couch_current_chest = game_elements_ref.get("current_chest")
    if isinstance(couch_current_chest, Chest) and couch_current_chest.alive() and \
       not couch_current_chest.is_collected_flag_internal:
        player_interacted_chest: Optional[Any] = None
        if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
           hasattr(p1, 'rect') and p1.rect.intersects(couch_current_chest.rect) and p1_action_events.get("interact", False):
            player_interacted_chest = p1
        elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
             hasattr(p2, 'rect') and p2.rect.intersects(couch_current_chest.rect) and p2_action_events.get("interact", False):
            player_interacted_chest = p2
        if player_interacted_chest:
            couch_current_chest.collect(player_interacted_chest)

    # --- Camera Update ---
    couch_camera = game_elements_ref.get("camera")
    if couch_camera:
        focus_target = None
        if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1, 'is_petrified', False): focus_target = p1
        elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2, 'is_petrified', False): focus_target = p2
        elif p1 and p1.alive() and p1._valid_init: focus_target = p1 # Fallback if one is petrified/dead
        elif p2 and p2.alive() and p2._valid_init: focus_target = p2 # Fallback
        
        if focus_target: couch_camera.update(focus_target)
        else: couch_camera.static_update()

    # --- Generic Pruning of all_renderable_objects ---
    # This will now correctly keep Platform, Ladder, Lava objects
    new_all_renderable_objects = []
    for obj in game_elements_ref.get("all_renderable_objects", []):
        if isinstance(obj, (Platform, Ladder, Lava)): # Keep all static tiles
            new_all_renderable_objects.append(obj)
        elif hasattr(obj, 'alive') and obj.alive(): # For dynamic objects, check if alive
            new_all_renderable_objects.append(obj)
        # elif hasattr(obj, 'alive') and not obj.alive(): # Optional: Log pruned dynamic objects
            # debug(f"CouchPlay: Pruning dead object {type(obj).__name__} (ID: {getattr(obj, 'player_id', getattr(obj, 'enemy_id', getattr(obj, 'statue_id', getattr(obj, 'projectile_id', id(obj)))) )}) from all_renderables.")
    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects

    return True # Continue game mode

#################### END OF FILE: couch_play_logic.py ####################