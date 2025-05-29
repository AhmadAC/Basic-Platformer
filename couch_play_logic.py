# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
MODIFIED: Includes processed trigger visuals in the render list.
"""
# version 2.0.28 (Include trigger visuals in render list)

import time
import math
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QRectF, QPointF
import constants as C
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform, Ladder, Lava, BackgroundTile
from player import Player

_SCRIPT_LOGGING_ENABLED = True

import logging
logger_couch = logging.getLogger(__name__)
# ... (standard logger setup as before) ...
def log_info(msg, *args, **kwargs): logger_couch.info(msg, *args, **kwargs)
def log_debug(msg, *args, **kwargs): logger_couch.debug(msg, *args, **kwargs)
def log_warning(msg, *args, **kwargs): logger_couch.warning(msg, *args, **kwargs)
def log_error(msg, *args, **kwargs): logger_couch.error(msg, *args, **kwargs)
def log_critical(msg, *args, **kwargs): logger_couch.critical(msg, *args, **kwargs)
try:
    from logger import info as project_info, debug as project_debug, \
                       warning as project_warning, error as project_error, \
                       critical as project_critical
    log_info = project_info; log_debug = project_debug; log_warning = project_warning;
    log_error = project_error; log_critical = project_critical
    if _SCRIPT_LOGGING_ENABLED: log_debug("CouchPlayLogic: Successfully aliased project's logger functions.")
except ImportError:
    if not logger_couch.hasHandlers() and not logging.getLogger().hasHandlers():
        _couch_fallback_handler_specific = logging.StreamHandler()
        _couch_fallback_formatter_specific = logging.Formatter('COUCH_PLAY (ImportFallbackConsole - specific): %(levelname)s - %(module)s:%(lineno)d - %(message)s')
        _couch_fallback_handler_specific.setFormatter(_couch_fallback_formatter_specific)
        logger_couch.addHandler(_couch_fallback_handler_specific)
        logger_couch.setLevel(logging.DEBUG)
        logger_couch.propagate = False
    if _SCRIPT_LOGGING_ENABLED: log_critical("CouchPlayLogic: Failed to import project's logger. Using isolated fallback for couch_play_logic.py.")


_start_time_couch_play_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_couch_play_monotonic) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any,
    get_p1_input_callback: callable,
    get_p2_input_callback: callable,
    get_p3_input_callback: callable,
    get_p4_input_callback: callable,
    process_qt_events_callback: callable,
    dt_sec_provider: callable,
    show_status_message_callback: Optional[callable] = None
    ) -> bool:

    try:
        from game_setup import get_layer_order_key
    except ImportError:
        log_warning("COUCH_PLAY_LOGIC WARNING (run_couch_play_mode): Could not import get_layer_order_key from game_setup. Using fallback for sorting.")
        def get_layer_order_key(item: Any) -> int:
            if isinstance(item, dict) and 'layer_order' in item: return int(item['layer_order'])
            if hasattr(item, 'layer_order'): return int(getattr(item, 'layer_order', 0))
            if isinstance(item, Player): return 100
            if isinstance(item, BackgroundTile): return -10
            return 0

    if not game_elements_ref.get('game_ready_for_logic', False) or \
       game_elements_ref.get('initialization_in_progress', True):
        if _SCRIPT_LOGGING_ENABLED and (not hasattr(run_couch_play_mode, "_init_wait_logged_couch") or not run_couch_play_mode._init_wait_logged_couch):
            log_debug("COUCH_PLAY DEBUG: Waiting for game elements initialization to complete...")
            run_couch_play_mode._init_wait_logged_couch = True
        return True

    if hasattr(run_couch_play_mode, "_init_wait_logged_couch"):
        delattr(run_couch_play_mode, "_init_wait_logged_couch")

    if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: --- Start of frame {get_current_ticks_monotonic()} ---")

    player1: Optional[Player] = game_elements_ref.get("player1"); player2: Optional[Player] = game_elements_ref.get("player2")
    player3: Optional[Player] = game_elements_ref.get("player3"); player4: Optional[Player] = game_elements_ref.get("player4")
    platforms_list_this_frame: List[Any] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Ladder] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Lava] = game_elements_ref.get("hazards_list", [])
    current_enemies_list_ref: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_objects_list_ref: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    current_chest: Optional[Chest] = game_elements_ref.get("current_chest")
    camera_obj: Optional[Any] = game_elements_ref.get("camera")
    processed_custom_images_for_render_couch: List[Dict[str,Any]] = game_elements_ref.get("processed_custom_images_for_render", [])
    processed_trigger_visuals_for_render_couch: List[Dict[str,Any]] = game_elements_ref.get("processed_trigger_visuals_for_render", [])


    if _SCRIPT_LOGGING_ENABLED:
        if (not hasattr(run_couch_play_mode, "_first_tick_debug_printed_couch") or not run_couch_play_mode._first_tick_debug_printed_couch):
            log_debug(f"COUCH_PLAY DEBUG: First valid tick. Platforms: {len(platforms_list_this_frame)}, "
                      f"CustomImages: {len(processed_custom_images_for_render_couch)}, TriggerVisuals: {len(processed_trigger_visuals_for_render_couch)}")
            run_couch_play_mode._first_tick_debug_printed_couch = True

    dt_sec = dt_sec_provider()
    p1_action_events: Dict[str, bool] = get_p1_input_callback(player1) if player1 and hasattr(player1, '_valid_init') and player1._valid_init else {}
    # ... (similar for p2, p3, p4 input) ...
    p2_action_events: Dict[str, bool] = get_p2_input_callback(player2) if player2 and hasattr(player2, '_valid_init') and player2._valid_init else {}
    p3_action_events: Dict[str, bool] = get_p3_input_callback(player3) if player3 and hasattr(player3, '_valid_init') and player3._valid_init else {}
    p4_action_events: Dict[str, bool] = get_p4_input_callback(player4) if player4 and hasattr(player4, '_valid_init') and player4._valid_init else {}


    if p1_action_events.get("pause") or p2_action_events.get("pause") or p3_action_events.get("pause") or p4_action_events.get("pause"):
        log_info("Couch Play: Pause action. Stopping game mode."); run_couch_play_mode._first_tick_debug_printed_couch = False; return False
    if p1_action_events.get("reset") or p2_action_events.get("reset") or p3_action_events.get("reset") or p4_action_events.get("reset"):
        log_info("Couch Play: Reset action. Resetting game state."); reset_game_state(game_elements_ref) # Re-fetch vars after this
        # ... (re-fetch all game element list references from game_elements_ref as they are new lists now)

    # ... (Chest Update, Player Updates, Enemy Updates, Statue Updates, Projectile Updates, Collectibles, Camera updates remain THE SAME as your existing correct logic) ...
    # The logic for these sections seems fine based on the previous discussions.

    new_all_renderables_couch: List[Any] = []
    def add_to_renderables_couch_if_new(obj_to_add: Any, render_list: List[Any]):
        if obj_to_add is not None:
            is_present = False
            for item in render_list:
                if item is obj_to_add: is_present = True; break
            if not is_present: render_list.append(obj_to_add)

    for static_key_couch in ["background_tiles_list", "ladders_list", "hazards_list", "platforms_list"]:
        for item_couch_static in game_elements_ref.get(static_key_couch, []): add_to_renderables_couch_if_new(item_couch_static, new_all_renderables_couch)
    
    custom_image_added_count = 0
    for custom_img_dict_couch in processed_custom_images_for_render_couch:
        add_to_renderables_couch_if_new(custom_img_dict_couch, new_all_renderables_couch)
        custom_image_added_count += 1
    if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: Added {custom_image_added_count} custom image dicts to renderables.")

    # ADD PROCESSED TRIGGER VISUALS
    trigger_visual_added_count = 0
    for trigger_visual_dict_couch in processed_trigger_visuals_for_render_couch:
        add_to_renderables_couch_if_new(trigger_visual_dict_couch, new_all_renderables_couch)
        trigger_visual_added_count +=1
    if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: Added {trigger_visual_added_count} trigger visual dicts to renderables.")


    for dynamic_key_couch in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
        for item_couch_dyn in game_elements_ref.get(dynamic_key_couch, []): add_to_renderables_couch_if_new(item_couch_dyn, new_all_renderables_couch)
    
    player_instances_to_update = [game_elements_ref.get(f"player{i}") for i in range(1,5) if game_elements_ref.get(f"player{i}")]
    for p_render_couch in player_instances_to_update:
        if p_render_couch:
            if hasattr(p_render_couch, 'alive') and p_render_couch.alive(): add_to_renderables_couch_if_new(p_render_couch, new_all_renderables_couch)
            elif getattr(p_render_couch, 'is_dead', False) and not getattr(p_render_couch, 'death_animation_finished', True): add_to_renderables_couch_if_new(p_render_couch, new_all_renderables_couch)

    try:
        new_all_renderables_couch.sort(key=get_layer_order_key)
        if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: Sorted renderables. Final count: {len(new_all_renderables_couch)}")
    except NameError as e_name: log_error(f"COUCH_PLAY ERROR: NameError during sort - get_layer_order_key not defined? {e_name}.")
    except Exception as e_sort: log_error(f"COUCH_PLAY ERROR: Error sorting renderables: {e_sort}.")
    game_elements_ref["all_renderable_objects"] = new_all_renderables_couch
    if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: Assembled and sorted renderables. Final count: {len(game_elements_ref['all_renderable_objects'])}")

    # ... (Game Over Check remains the same) ...
    def is_player_truly_gone_couch(p_instance_couch):
        if not p_instance_couch or not hasattr(p_instance_couch, '_valid_init') or not p_instance_couch._valid_init: return True
        if hasattr(p_instance_couch, 'alive') and p_instance_couch.alive():
            if getattr(p_instance_couch, 'is_dead', False):
                if getattr(p_instance_couch, 'is_petrified', False) and not getattr(p_instance_couch, 'is_stone_smashed', False): return False
                elif not getattr(p_instance_couch, 'death_animation_finished', True): return False
            else: return False
        return True
    num_players_for_mode = game_elements_ref.get('num_active_players_for_mode', 2)
    active_player_instances_in_map_couch = [p for p_idx, p in enumerate([player1,player2,player3,player4]) if p_idx < num_players_for_mode and p and hasattr(p, '_valid_init') and p._valid_init]
    if not active_player_instances_in_map_couch:
        log_info(f"Couch Play: No active player instances for this mode ({num_players_for_mode} players). Game Over by default.")
        if show_status_message_callback: show_status_message_callback(f"Game Over! No active players.")
        run_couch_play_mode._first_tick_debug_printed_couch = False
        return False
    all_active_players_are_gone_couch = True
    for p_active_inst_couch in active_player_instances_in_map_couch:
        if not is_player_truly_gone_couch(p_active_inst_couch): all_active_players_are_gone_couch = False; break
    if all_active_players_are_gone_couch:
        log_info(f"Couch Play: All {len(active_player_instances_in_map_couch)} active players are gone. Game Over.")
        if show_status_message_callback: show_status_message_callback(f"Game Over! All {len(active_player_instances_in_map_couch)} players defeated.")
        process_qt_events_callback(); time.sleep(1.5)
        run_couch_play_mode._first_tick_debug_printed_couch = False
        return False


    if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY DEBUG: --- End of frame {get_current_ticks_monotonic()} ---")
    return True