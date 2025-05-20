# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.5 (Integrated provided robust pruning for all_renderable_objects)

import time
from typing import Dict, List, Any, Optional

# --- Logger Setup ---
import logging
try:
    from logger import info as log_info, debug as log_debug, \
                       warning as log_warning, error as log_error, \
                       critical as log_critical
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers() and not logging.getLogger().hasHandlers():
        _couch_fallback_console_handler = logging.StreamHandler()
        _couch_fallback_console_formatter = logging.Formatter('COUCH_PLAY (FallbackConsole): %(levelname)s - %(message)s')
        _couch_fallback_console_handler.setFormatter(_couch_fallback_console_formatter)
        logger.addHandler(_couch_fallback_console_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        # logger.warning("Central logger might be unconfigured; couch_play_logic.py added its own console handler.") # Less verbose
    # else:
        # logger.debug("couch_play_logic.py using centrally configured logger.") # Less verbose
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
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform, Ladder, Lava # Essential for isinstance checks

_start_time_couch_play_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    """Returns monotonic time in milliseconds since module load or a fixed point."""
    return int((time.monotonic() - _start_time_couch_play_monotonic) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any,
    get_p1_input_callback: callable,
    get_p2_input_callback: callable,
    process_qt_events_callback: callable,
    dt_sec_provider: callable,
    show_status_message_callback: Optional[callable] = None
    ) -> bool:
    
    player1: Optional[Any] = game_elements_ref.get("player1")
    player2: Optional[Any] = game_elements_ref.get("player2")
    platforms_list: List[Any] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Any] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Any] = game_elements_ref.get("hazards_list", [])
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_list: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list: List[Any] = game_elements_ref.get("collectible_list", [])
    current_chest: Optional[Chest] = game_elements_ref.get("current_chest")
    all_renderables_list_original_ref: List[Any] = game_elements_ref.get("all_renderable_objects", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")

    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1, platforms_list)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
       hasattr(player2, 'control_scheme') and player2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(player2, platforms_list)

    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        log_info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        return False

    if p1_action_events.get("reset") or p2_action_events.get("reset"):
        log_info("Couch Play: Game state reset initiated by player action.")
        new_chest_after_reset = reset_game_state(game_elements_ref)
        game_elements_ref["current_chest"] = new_chest_after_reset
        all_renderables_list_original_ref = game_elements_ref.get("all_renderable_objects", [])


    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        other_players_for_p1 = [p for p in [player2] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player1]
        player1.game_elements_ref_for_projectiles = game_elements_ref
        player1.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p1, current_enemies_list)

    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        other_players_for_p2 = [p for p in [player1] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player2]
        player2.game_elements_ref_for_projectiles = game_elements_ref
        player2.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p2, current_enemies_list)

    active_players_for_ai = [p for p in [player1, player2] if p and hasattr(p, '_valid_init') and p._valid_init and not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]
    
    temp_enemy_list = list(current_enemies_list)
    for enemy_instance in temp_enemy_list:
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
            else:
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list, hazards_list, current_enemies_list)
            
            if not (hasattr(enemy_instance, 'alive') and enemy_instance.alive()):
                if enemy_instance in current_enemies_list: current_enemies_list.remove(enemy_instance)
    
    temp_statue_list = list(statue_list)
    for statue_instance in temp_statue_list:
        if hasattr(statue_instance, 'update') and hasattr(statue_instance, 'alive') and statue_instance.alive():
            statue_instance.update(dt_sec)
        if not (hasattr(statue_instance, 'alive') and statue_instance.alive()):
            if statue_instance in statue_list: statue_list.remove(statue_instance)

    hittable_targets_for_projectiles: List[Any] = []
    if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and not getattr(player1, 'is_petrified', False): hittable_targets_for_projectiles.append(player1)
    if player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and not getattr(player2, 'is_petrified', False): hittable_targets_for_projectiles.append(player2)
    for enemy_target in current_enemies_list:
        if enemy_target.alive() and hasattr(enemy_target, '_valid_init') and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    for statue_target in statue_list:
        if statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed:
            hittable_targets_for_projectiles.append(statue_target)
    
    temp_projectiles_list = list(projectiles_list)
    for proj_instance in temp_projectiles_list:
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list, hittable_targets_for_projectiles)
        if not (hasattr(proj_instance, 'alive') and proj_instance.alive()):
            if proj_instance in projectiles_list: projectiles_list.remove(proj_instance)

    temp_collectible_list = list(collectible_items_list)
    for collectible in temp_collectible_list:
        if hasattr(collectible, 'update') and hasattr(collectible, 'alive') and collectible.alive():
            collectible.update(dt_sec)
        if not (hasattr(collectible, 'alive') and collectible.alive()):
            if collectible in collectible_items_list: collectible_items_list.remove(collectible)
            if game_elements_ref.get("current_chest") is collectible: game_elements_ref["current_chest"] = None

    current_chest = game_elements_ref.get("current_chest")
    if current_chest and isinstance(current_chest, Chest) and \
       hasattr(current_chest, 'alive') and current_chest.alive() and \
       not getattr(current_chest, 'is_collected_flag_internal', True):
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
        if player_interacted_chest: current_chest.collect(player_interacted_chest)

    if camera_obj:
        focus_target = None
        if player1 and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False): focus_target = player1
        elif player2 and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False): focus_target = player2
        elif player1 and hasattr(player1, '_valid_init') and player1._valid_init and player1.alive(): focus_target = player1
        elif player2 and hasattr(player2, '_valid_init') and player2._valid_init and player2.alive(): focus_target = player2
        if focus_target: camera_obj.update(focus_target)
        else: camera_obj.static_update()

    # --- Generic Pruning of all_renderable_objects ---
    # This will now correctly keep Platform, Ladder, Lava objects
    new_all_renderable_objects = []
    # Iterate over the list that was fetched at the start of the function,
    # or if a reset happened, it should be the fresh list from game_elements_ref.
    # It's crucial that all_renderables_list_original_ref is up-to-date if reset_game_state modifies it.
    # The safest is to always re-fetch before this loop if reset might have occurred.
    current_all_renderables = game_elements_ref.get("all_renderable_objects", [])

    for obj in current_all_renderables:
        if isinstance(obj, (Platform, Ladder, Lava)): # Keep all static tiles
            new_all_renderable_objects.append(obj)
        elif hasattr(obj, 'alive') and obj.alive(): # For dynamic objects, check if alive
            new_all_renderable_objects.append(obj)
        # elif hasattr(obj, 'alive') and not obj.alive(): # Optional: Log pruned dynamic objects
            # log_debug(f"CouchPlay: Pruning dead object {type(obj).__name__} (ID: {getattr(obj, 'player_id', getattr(obj, 'enemy_id', getattr(obj, 'statue_id', getattr(obj, 'projectile_id', id(obj)))) )}) from all_renderables.")
    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects


    p1_gone = True
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        if player1.alive():
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False): p1_gone = False
                elif not getattr(player1, 'death_animation_finished', True): p1_gone = False
            else: p1_gone = False
    
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
        process_qt_events_callback()
        time.sleep(1.5)
        return False

    return True