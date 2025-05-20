# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.3 (Robust list handling, consistent alive checks)

import time
from typing import Dict, List, Any, Optional

# --- Logger Setup ---
# Attempt to import custom logger functions; if fails, logger instance below will use basic config.
import logging # Import standard logging
try:
    from logger import info as log_info, debug as log_debug, \
                       warning as log_warning, error as log_error, \
                       critical as log_critical
    logger = logging.getLogger(__name__) # Get a logger instance for this module
    if not logger.hasHandlers() and not logging.getLogger().hasHandlers():
        _couch_fallback_console_handler = logging.StreamHandler()
        _couch_fallback_console_formatter = logging.Formatter('COUCH_PLAY (FallbackConsole): %(levelname)s - %(message)s')
        _couch_fallback_console_handler.setFormatter(_couch_fallback_console_formatter)
        logger.addHandler(_couch_fallback_console_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.warning("Central logger might be unconfigured; couch_play_logic.py added its own console handler.")
    else:
        logger.debug("couch_play_logic.py using centrally configured logger.")
except ImportError:
    logging.basicConfig(level=logging.DEBUG,
                        format='COUCH_PLAY (CriticalImportFallback): %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    logger = logging.getLogger(__name__)
    logger.critical("Failed to import custom logger. Using isolated fallback for couch_play_logic.py.")
    def log_info(msg, *args, **kwargs): logger.info(msg, *args, **kwargs)
    def log_debug(msg, *args, **kwargs): logger.debug(msg, *args, **kwargs)
    def log_warning(msg, *args, **kwargs): logger.warning(msg, *args, **kwargs)
    def log_error(msg, *args, **kwargs): logger.error(msg, *args, **kwargs)
    def log_critical(msg, *args, **kwargs): logger.critical(msg, *args, **kwargs)
# --- End Logger Setup ---

import constants as C
from game_state_manager import reset_game_state # For reset action
from enemy import Enemy # For isinstance checks and type hinting
from items import Chest # For isinstance checks
from statue import Statue # For isinstance checks
from tiles import Platform, Ladder, Lava # For pruning all_renderables

_start_time_couch_play_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_couch_play_monotonic) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any, # Main application status (e.g., for app_running check)
    get_p1_input_callback: callable, # (player_instance, platforms_list) -> Dict[str, bool]
    get_p2_input_callback: callable, # (player_instance, platforms_list) -> Dict[str, bool]
    process_qt_events_callback: callable, # lambda: QApplication.processEvents()
    dt_sec_provider: callable, # lambda: dt_sec (delta time in seconds)
    show_status_message_callback: Optional[callable] = None # For UI messages
    ) -> bool: # Returns True to continue, False to stop game mode
    
    # --- Fetch Core Game Elements ---
    player1: Optional[Any] = game_elements_ref.get("player1")
    player2: Optional[Any] = game_elements_ref.get("player2")
    platforms_list: List[Any] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Any] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Any] = game_elements_ref.get("hazards_list", [])
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", []) # Get with default
    statue_list: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list: List[Any] = game_elements_ref.get("collectible_list", [])
    current_chest: Optional[Chest] = game_elements_ref.get("current_chest")
    all_renderables_list: List[Any] = game_elements_ref.get("all_renderable_objects", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")

    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    # --- Process Inputs ---
    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1, platforms_list)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
       hasattr(player2, 'control_scheme') and player2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(player2, platforms_list)

    # --- Handle Universal Actions (Pause, Reset) ---
    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        log_info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        return False # Signal to stop the game mode

    if p1_action_events.get("reset") or p2_action_events.get("reset"):
        log_info("Couch Play: Game state reset initiated by player action.")
        # reset_game_state should repopulate game_elements_ref correctly
        new_chest_after_reset = reset_game_state(game_elements_ref)
        game_elements_ref["current_chest"] = new_chest_after_reset # Update current chest reference
        # Ensure players are in renderables if reset logic made them non-alive then alive again.
        # reset_game_state should ideally handle adding them back to game_elements['all_renderable_objects']
        # if they are made active again.
        # For safety, we could re-check here, but it's better if reset_game_state is comprehensive.

    # --- Player Updates ---
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        other_players_for_p1 = [p for p in [player2] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player1]
        player1.game_elements_ref_for_projectiles = game_elements_ref # Ensure it has the latest ref
        player1.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p1, current_enemies_list)

    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        other_players_for_p2 = [p for p in [player1] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player2]
        player2.game_elements_ref_for_projectiles = game_elements_ref
        player2.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p2, current_enemies_list)

    # --- Enemy Updates ---
    active_players_for_ai = [p for p in [player1, player2] if p and hasattr(p, '_valid_init') and p._valid_init and not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]
    
    # Iterate a copy for safe removal during updates if necessary
    for enemy_instance in list(current_enemies_list):
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init and hasattr(enemy_instance, 'alive') and enemy_instance.alive():
            # Petrified enemies might have limited updates (e.g., status effects, falling)
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
                # If petrified enemy is "killed" (smashed and anim finished), it will be pruned later
            else: # Normal update
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list, hazards_list, current_enemies_list)
    
    # Prune dead enemies from main list (and all_renderables will be pruned later)
    game_elements_ref["enemy_list"] = [e for e in current_enemies_list if hasattr(e, 'alive') and e.alive()]


    # --- Statue Updates ---
    for statue_instance in list(statue_list): # Iterate copy
        if hasattr(statue_instance, 'update') and hasattr(statue_instance, 'alive') and statue_instance.alive():
            statue_instance.update(dt_sec)
    game_elements_ref["statue_objects"] = [s for s in statue_list if hasattr(s, 'alive') and s.alive()]


    # --- Projectile Updates ---
    hittable_targets_for_projectiles: List[Any] = []
    if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and not getattr(player1, 'is_petrified', False): hittable_targets_for_projectiles.append(player1)
    if player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and not getattr(player2, 'is_petrified', False): hittable_targets_for_projectiles.append(player2)
    
    # Use the already updated enemy_list from game_elements_ref
    for enemy_target in game_elements_ref.get("enemy_list", []):
        if enemy_target.alive() and hasattr(enemy_target, '_valid_init') and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    
    # Use the already updated statue_list
    for statue_target in game_elements_ref.get("statue_objects", []):
        if statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed:
            hittable_targets_for_projectiles.append(statue_target)
    
    for proj_instance in list(projectiles_list): # Iterate copy
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list, hittable_targets_for_projectiles)
    game_elements_ref["projectiles_list"] = [p for p in projectiles_list if hasattr(p, 'alive') and p.alive()]


    # --- Collectible Updates (Chest) ---
    for collectible in list(collectible_items_list): # Iterate copy
        if hasattr(collectible, 'update') and hasattr(collectible, 'alive') and collectible.alive():
            collectible.update(dt_sec) # dt_sec for Chest animation
    game_elements_ref["collectible_list"] = [c for c in collectible_items_list if hasattr(c, 'alive') and c.alive()]
    # Update current_chest reference if it got removed from collectible_list
    if current_chest and (not hasattr(current_chest, 'alive') or not current_chest.alive()):
        game_elements_ref["current_chest"] = None
        current_chest = None # Update local var


    # --- Chest Interaction Logic ---
    if current_chest and isinstance(current_chest, Chest) and \
       hasattr(current_chest, 'alive') and current_chest.alive() and \
       not getattr(current_chest, 'is_collected_flag_internal', True): # Check if NOT collected
        
        player_interacted_chest: Optional[Any] = None
        if player1 and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and player1.alive() and \
           not getattr(player1, 'is_petrified', False) and \
           hasattr(player1, 'rect') and player1.rect.intersects(current_chest.rect) and \
           p1_action_events.get("interact", False):
            player_interacted_chest = player1
        elif player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and player2.alive() and \
             not getattr(player2, 'is_petrified', False) and \
             hasattr(player2, 'rect') and player2.rect.intersects(current_chest.rect) and \
             p2_action_events.get("interact", False):
            player_interacted_chest = player2
        
        if player_interacted_chest:
            current_chest.collect(player_interacted_chest)


    # --- Camera Update ---
    if camera_obj:
        focus_target = None
        # Prioritize P1 if alive and not petrified/dead
        if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False):
            focus_target = player1
        # Else, try P2 if alive and not petrified/dead
        elif player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False):
            focus_target = player2
        # Fallback to P1 even if petrified/dead (camera might still want to show their last spot)
        elif player1 and hasattr(player1, '_valid_init') and player1._valid_init:
            focus_target = player1
        # Fallback to P2
        elif player2 and hasattr(player2, '_valid_init') and player2._valid_init:
            focus_target = player2
        
        if focus_target:
            camera_obj.update(focus_target)
        else: # No valid player focus target
            camera_obj.static_update() # Maintain position or default view

    # --- Generic Pruning of `all_renderable_objects` ---
    # This ensures static tiles are kept, and dynamic objects are pruned if not alive.
    new_all_renderable_objects = []
    for obj in all_renderables_list: # Iterate the original list fetched at start of function
        if isinstance(obj, (Platform, Ladder, Lava)): # Keep all static tiles by type
            new_all_renderable_objects.append(obj)
        elif hasattr(obj, 'alive') and obj.alive(): # For dynamic objects, check if alive
            new_all_renderable_objects.append(obj)
        # elif hasattr(obj, 'alive') and not obj.alive():
            # entity_type_for_log = type(obj).__name__
            # entity_id_for_log = getattr(obj, 'player_id', getattr(obj, 'enemy_id', getattr(obj, 'statue_id', getattr(obj, 'projectile_id', id(obj)))))
            # log_debug(f"CouchPlay: Pruning dead object {entity_type_for_log} (ID: {entity_id_for_log}) from all_renderables.")
    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects


    # --- Check Game Over for Couch Co-op (Both players dead and animations finished) ---
    p1_gone = True
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        if player1.alive(): # If player is in sprite groups (or should be), it's "active"
            if getattr(player1, 'is_dead', False):
                 # Petrified but not smashed is not "truly gone" for game over condition
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False): p1_gone = False
                # Death animation still playing
                elif not getattr(player1, 'death_animation_finished', True): p1_gone = False
            else: p1_gone = False # Alive and not dead
    
    p2_gone = True
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        if player2.alive():
            if getattr(player2, 'is_dead', False):
                if getattr(player2, 'is_petrified', False) and not getattr(player2, 'is_stone_smashed', False): p2_gone = False
                elif not getattr(player2, 'death_animation_finished', True): p2_gone = False
            else: p2_gone = False

    if p1_gone and p2_gone:
        log_info("Couch Play: Both players are gone. Game Over.")
        if show_status_message_callback: show_status_message_callback("Game Over! Both players defeated.")
        # Give a moment to see "Game Over" before returning to menu
        process_qt_events_callback() # Process events one last time
        time.sleep(1.5) # Brief pause
        return False # Signal to stop the game mode

    return True # Continue game mode