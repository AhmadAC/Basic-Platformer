#################### START OF FILE: couch_play_logic.py ####################

# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.0 (PySide6 Refactor)

from typing import Dict, List, Any, Optional # Added Optional, List

# Game imports (refactored classes and modules)
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
from game_state_manager import reset_game_state # Refactored
from enemy import Enemy # Refactored
from items import Chest # Refactored
from statue import Statue # Refactored
import config as game_config # Refactored

# Placeholder for pygame.time.get_ticks()
try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_couch_play = time.monotonic()
    def get_current_ticks():
        return int((time.monotonic() - _start_time_couch_play) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any, # Contains app_running flag
    # Callbacks from main Qt application:
    get_p1_input_callback: callable, # Args: (player1_instance, platforms_list) -> Dict[str, bool] action_events
    get_p2_input_callback: callable, # Args: (player2_instance, platforms_list) -> Dict[str, bool] action_events
    process_qt_events_callback: callable, # Call to process Qt's event loop
    dt_sec_provider: callable, # Called to get dt_sec for the current frame
    show_status_message_callback: Optional[callable] = None # (message_str) -> None
    ):
    """
    Runs one tick of the game loop for couch co-op mode.
    This function will be called repeatedly by a QTimer in the main application.
    """
    info("CouchPlayLogic: Executing one tick of Couch Play mode.")
    # Pygame.display.set_caption is now handled by main Qt window

    p1: Optional[Any] = game_elements_ref.get("player1")
    p2: Optional[Any] = game_elements_ref.get("player2")
    
    dt_sec = dt_sec_provider() # Get delta time from the main loop
    # now_ticks_couch = get_current_ticks() # Current game time (if needed for logic beyond dt)

    # --- Process Input (via callbacks from main Qt app) ---
    # The main Qt app handles QKeyEvents, QGamepadEvents, etc., and translates them
    # into action event dictionaries for each player via the provided callbacks.
    
    p1_action_events: Dict[str, bool] = {}
    if p1 and p1._valid_init:
        p1_action_events = get_p1_input_callback(p1, game_elements_ref.get("platforms_list", []))

    p2_action_events: Dict[str, bool] = {}
    if p2 and p2._valid_init and p2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(p2, game_elements_ref.get("platforms_list", []))

    # Check for universal actions (reset game, pause/exit mode)
    # Pause in couch mode usually means exit to main menu for the app.
    # The callbacks themselves might set app_status_obj.app_running = False if Escape is hit.
    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        info("Couch Play: Pause action detected. Signaling app to exit mode.")
        # The main app loop will see app_status_obj.app_running change or handle this signal
        # to transition away from couch play mode.
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        return False # Signal to the caller (main loop) to stop this mode

    host_requested_reset = p1_action_events.get("reset", False)
    p2_requested_reset = p2_action_events.get("reset", False)
    
    # Developer reset key (e.g., "Q") might be handled by the get_p1_input_callback too
    # For simplicity, we rely on the "reset" action event from input processing.

    # --- Game Action Logic ---
    if host_requested_reset or p2_requested_reset: # Either player can request reset
        info("Couch Play: Game state reset initiated.")
        # reset_game_state now operates on lists and Qt-based objects
        game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
        # Ensure players are in all_renderable_objects if reset and alive
        all_renderables = game_elements_ref.get("all_renderable_objects", [])
        if p1 and p1._valid_init and not p1.alive() and p1 not in all_renderables: all_renderables.append(p1)
        if p2 and p2._valid_init and not p2.alive() and p2 not in all_renderables: all_renderables.append(p2)


    # --- Update P1 (Host player) ---
    if p1 and p1._valid_init: 
        other_players_for_p1 = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
        p1.game_elements_ref_for_projectiles = game_elements_ref 
        p1.update(dt_sec, game_elements_ref.get("platforms_list", []),
                  game_elements_ref.get("ladders_list", []),
                  game_elements_ref.get("hazards_list", []),
                  other_players_for_p1,
                  game_elements_ref.get("enemy_list", []))

    # --- Update P2 (Second local player) ---
    if p2 and p2._valid_init:
        other_players_for_p2 = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
        p2.game_elements_ref_for_projectiles = game_elements_ref
        p2.update(dt_sec, game_elements_ref.get("platforms_list", []),
                  game_elements_ref.get("ladders_list", []),
                  game_elements_ref.get("hazards_list", []),
                  other_players_for_p2,
                  game_elements_ref.get("enemy_list", []))

    # --- Update Enemies ---
    active_players_for_ai = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
    # Iterate over a copy if enemies can be removed during update
    for enemy_couch in list(game_elements_ref.get("enemy_list", [])): 
        if enemy_couch._valid_init:
            if hasattr(enemy_couch, 'is_petrified') and enemy_couch.is_petrified:
                if hasattr(enemy_couch, 'update_enemy_status_effects'): # Assuming Enemy has this method
                     enemy_couch.update_enemy_status_effects(get_current_ticks(), game_elements_ref.get("platforms_list", []))
                enemy_couch.animate()
                if enemy_couch.is_dead and enemy_couch.death_animation_finished and enemy_couch.alive():
                    enemy_couch.kill() # Will set _alive = False
                continue

            enemy_couch.update(dt_sec, active_players_for_ai,
                               game_elements_ref.get("platforms_list", []),
                               game_elements_ref.get("hazards_list", []),
                               game_elements_ref.get("enemy_list", []))
            if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
               enemy_couch.death_animation_finished and enemy_couch.alive():
                debug(f"Couch Play: Auto-killing enemy {enemy_couch.enemy_id} as death anim finished.")
                enemy_couch.kill()
    # Prune dead enemies from main list and render list
    game_elements_ref["enemy_list"] = [e for e in game_elements_ref.get("enemy_list", []) if e.alive()]
    game_elements_ref["all_renderable_objects"] = [obj for obj in game_elements_ref.get("all_renderable_objects", []) if not (isinstance(obj, Enemy) and not obj.alive())]


    # --- Update Statues ---
    statue_list_couch: List[Statue] = game_elements_ref.get("statue_objects", [])
    for statue_instance in statue_list_couch:
        if hasattr(statue_instance, 'update'):
            statue_instance.update(dt_sec)
    game_elements_ref["statue_objects"] = [s for s in statue_list_couch if s.alive()]
    game_elements_ref["all_renderable_objects"] = [obj for obj in game_elements_ref.get("all_renderable_objects", []) if not (isinstance(obj, Statue) and not obj.alive())]


    # --- Update Projectiles ---
    hittable_targets_couch_list: List[Any] = [] # Build list of hittable objects
    if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_targets_couch_list.append(p1)
    if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_targets_couch_list.append(p2)
    for enemy_target in game_elements_ref.get("enemy_list", []):
        if enemy_target and enemy_target.alive() and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_couch_list.append(enemy_target)
    for statue_target_couch in statue_list_couch:
        if statue_target_couch.alive() and hasattr(statue_target_couch, 'is_smashed') and not statue_target_couch.is_smashed:
            hittable_targets_couch_list.append(statue_target_couch)
    
    projectiles_list_ref: List[Any] = game_elements_ref.get("projectiles_list", [])
    for proj_instance in list(projectiles_list_ref): # Iterate copy
        if hasattr(proj_instance, 'update'):
            proj_instance.update(dt_sec, game_elements_ref.get("platforms_list", []), hittable_targets_couch_list)
            if not proj_instance.alive(): # If projectile killed itself
                if proj_instance in projectiles_list_ref: projectiles_list_ref.remove(proj_instance)
                if proj_instance in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).remove(proj_instance)


    # --- Update Collectibles (Chests, etc.) ---
    collectible_list_ref: List[Chest] = game_elements_ref.get("collectible_list", [])
    for collectible in list(collectible_list_ref): # Iterate copy
        if hasattr(collectible, 'update'):
            collectible.update(dt_sec)
            if not collectible.alive():
                if collectible in collectible_list_ref: collectible_list_ref.remove(collectible)
                if collectible in game_elements_ref.get("all_renderable_objects",[]): game_elements_ref.get("all_renderable_objects",[]).remove(collectible)
                if game_elements_ref.get("current_chest") is collectible: game_elements_ref["current_chest"] = None


    # --- Chest Interaction Logic ---
    couch_current_chest = game_elements_ref.get("current_chest")
    if isinstance(couch_current_chest, Chest) and couch_current_chest.alive() and \
       not couch_current_chest.is_collected_flag_internal:
        player_interacted_chest: Optional[Any] = None
        if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
           p1.rect.intersects(couch_current_chest.rect) and p1_action_events.get("interact", False):
            player_interacted_chest = p1
        elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
             p2.rect.intersects(couch_current_chest.rect) and p2_action_events.get("interact", False):
            player_interacted_chest = p2
        if player_interacted_chest:
            couch_current_chest.collect(player_interacted_chest)

    # --- Update Camera ---
    couch_camera = game_elements_ref.get("camera")
    if couch_camera:
        focus_target = None
        if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1, 'is_petrified', False): focus_target = p1
        elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2, 'is_petrified', False): focus_target = p2
        elif p1 and p1.alive() and p1._valid_init: focus_target = p1
        elif p2 and p2.alive() and p2._valid_init: focus_target = p2
        
        if focus_target: couch_camera.update(focus_target)
        else: couch_camera.static_update()

    # --- Rendering is handled by the GameSceneWidget in the main Qt app ---
    # The main app will call GameSceneWidget.update() which triggers its paintEvent.

    return True # Indicate couch play tick was successful and should continue

#################### END OF FILE: couch_play_logic.py ####################