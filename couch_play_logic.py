# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.17 (Fixed missing debug import)

import time
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QRectF
import constants as C
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest # Make sure Chest is imported
from statue import Statue
from tiles import Platform, Ladder, Lava, BackgroundTile # For type checking
from player import Player # For type checking

# --- Per-script logging toggle ---
_SCRIPT_LOGGING_ENABLED = True
# --- End per-script logging toggle ---

# Logger
import logging
logger_couch = logging.getLogger(__name__) # Changed logger name to avoid potential conflicts

# Define aliases at the module level, initially as fallbacks
def log_info(msg, *args, **kwargs): logger_couch.info(msg, *args, **kwargs)
def log_debug(msg, *args, **kwargs): logger_couch.debug(msg, *args, **kwargs) # Ensure this uses logger_couch
def log_warning(msg, *args, **kwargs): logger_couch.warning(msg, *args, **kwargs)
def log_error(msg, *args, **kwargs): logger_couch.error(msg, *args, **kwargs)
def log_critical(msg, *args, **kwargs): logger_couch.critical(msg, *args, **kwargs)

try:
    # Attempt to import the project's configured logger functions
    from logger import info as project_info, debug as project_debug, \
                       warning as project_warning, error as project_error, \
                       critical as project_critical
    
    # If successful, re-assign the aliases to use the project's logger functions
    log_info = project_info
    log_debug = project_debug # <<<< THIS WAS THE KEY CORRECTION AREA
    log_warning = project_warning
    log_error = project_error
    log_critical = project_critical
    # Use log_debug (which now points to project_debug or the fallback)
    if _SCRIPT_LOGGING_ENABLED: log_debug("CouchPlayLogic: Successfully aliased project's logger functions.") 

except ImportError:
    if not logger_couch.hasHandlers() and not logging.getLogger().hasHandlers():
        _couch_fallback_handler_specific = logging.StreamHandler()
        _couch_fallback_formatter_specific = logging.Formatter('COUCH_PLAY (ImportFallbackConsole - specific): %(levelname)s - %(message)s')
        _couch_fallback_handler_specific.setFormatter(_couch_fallback_formatter_specific)
        logger_couch.addHandler(_couch_fallback_handler_specific)
        logger_couch.setLevel(logging.DEBUG)
        logger_couch.propagate = False
    if _SCRIPT_LOGGING_ENABLED: log_critical("CouchPlayLogic: Failed to import project's logger. Using isolated fallback for couch_play_logic.py.")
# Now, instead of directly using `logger.debug`, use `log_debug`
# and rename the local logger instance to avoid confusion if `logger` is imported directly
# from the main logger module elsewhere in this file.

# Rename the module-level logger instance to avoid conflict if 'logger' is imported directly
# from your main logger.py file later in this script (though direct import is less likely now).
# logger = logger_couch # This line is not needed if we use log_debug() etc.

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
    ) -> bool:

    if not game_elements_ref.get('game_ready_for_logic', False) or \
       game_elements_ref.get('initialization_in_progress', True):
        if _SCRIPT_LOGGING_ENABLED and (not hasattr(run_couch_play_mode, "_init_wait_logged_couch") or not run_couch_play_mode._init_wait_logged_couch): # type: ignore
            log_debug("COUCH_PLAY: Waiting for game elements initialization to complete...") # Use log_debug
            run_couch_play_mode._init_wait_logged_couch = True # type: ignore
        return True

    if hasattr(run_couch_play_mode, "_init_wait_logged_couch"):
        delattr(run_couch_play_mode, "_init_wait_logged_couch")

    player1: Optional[Player] = game_elements_ref.get("player1")
    player2: Optional[Player] = game_elements_ref.get("player2")
    platforms_list: List[Platform] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Ladder] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Lava] = game_elements_ref.get("hazards_list", [])
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_list: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list_ref: List[Any] = game_elements_ref.get("collectible_list", [])
    current_chest: Optional[Chest] = game_elements_ref.get("current_chest")
    all_renderable_objects_ref: List[Any] = game_elements_ref.get("all_renderable_objects", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")

    if _SCRIPT_LOGGING_ENABLED and (not hasattr(run_couch_play_mode, "_platform_debug_printed_couch") or not run_couch_play_mode._platform_debug_printed_couch) : # type: ignore
        log_debug(f"COUCH_PLAY: First valid tick. Platforms: {len(platforms_list)}, Ladders: {len(ladders_list)}, Hazards: {len(hazards_list)}, Chest: {'Present' if current_chest else 'None'}") # Use log_debug
        run_couch_play_mode._platform_debug_printed_couch = True # type: ignore

    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
       hasattr(player2, 'control_scheme') and player2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(player2)

    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        if _SCRIPT_LOGGING_ENABLED: log_info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        run_couch_play_mode._platform_debug_printed_couch = False
        return False

    if p1_action_events.get("reset") or p2_action_events.get("reset"):
        if _SCRIPT_LOGGING_ENABLED: log_info("Couch Play: Game state reset initiated by player action.")
        new_chest_after_reset = reset_game_state(game_elements_ref)
        current_chest = game_elements_ref.get("current_chest")
        current_enemies_list = game_elements_ref.get("enemy_list", [])
        statue_list = game_elements_ref.get("statue_objects", [])
        projectiles_list = game_elements_ref.get("projectiles_list", [])
        collectible_items_list_ref = game_elements_ref.get("collectible_list", [])
        all_renderable_objects_ref = game_elements_ref.get("all_renderable_objects", [])
        if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY Reset: Enemies={len(current_enemies_list)}, Statues={len(statue_list)}, Collectibles={len(collectible_items_list_ref)}, CurrentChest: {'Present' if current_chest else 'None'}") # Use log_debug

    if current_chest and isinstance(current_chest, Chest) and current_chest.alive():
        current_chest.apply_physics_step(dt_sec)
        current_chest.on_ground = False
        if not current_chest.is_collected_flag_internal and current_chest.state == 'closed':
            for platform_collidable in platforms_list:
                if not hasattr(platform_collidable, 'rect') or not isinstance(platform_collidable.rect, QRectF):
                    continue
                if current_chest.rect.intersects(platform_collidable.rect):
                    if current_chest.vel_x > 0 and current_chest.rect.right() > platform_collidable.rect.left():
                        current_chest.rect.moveRight(platform_collidable.rect.left() - 0.1)
                        current_chest.vel_x = 0
                        current_chest.pos_midbottom.setX(current_chest.rect.center().x())
                    elif current_chest.vel_x < 0 and current_chest.rect.left() < platform_collidable.rect.right():
                        current_chest.rect.moveLeft(platform_collidable.rect.right() + 0.1)
                        current_chest.vel_x = 0
                        current_chest.pos_midbottom.setX(current_chest.rect.center().x())
                    previous_chest_bottom_y_estimate = current_chest.rect.bottom() - (current_chest.vel_y * dt_sec * C.FPS if current_chest.vel_y > 0 else 0)
                    if current_chest.vel_y >= 0 and \
                       current_chest.rect.bottom() >= platform_collidable.rect.top() and \
                       previous_chest_bottom_y_estimate <= platform_collidable.rect.top() + C.GROUND_SNAP_THRESHOLD :
                        min_overlap_ratio_chest = 0.1
                        min_horizontal_overlap_chest = current_chest.rect.width() * min_overlap_ratio_chest
                        actual_overlap_width_chest = min(current_chest.rect.right(), platform_collidable.rect.right()) - \
                                                   max(current_chest.rect.left(), platform_collidable.rect.left())
                        if actual_overlap_width_chest >= min_horizontal_overlap_chest:
                            current_chest.rect.moveBottom(platform_collidable.rect.top())
                            current_chest.pos_midbottom.setY(current_chest.rect.bottom())
                            current_chest.vel_y = 0.0
                            current_chest.on_ground = True
                            break
            if hasattr(current_chest, '_update_rect_from_image_and_pos'):
                current_chest._update_rect_from_image_and_pos()

    all_other_characters_for_p1 = [p for p in [player2, current_chest] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player1]
    all_other_characters_for_p2 = [p for p in [player1, current_chest] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player2]
    
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        player1.game_elements_ref_for_projectiles = game_elements_ref
        player1.update(dt_sec, platforms_list, ladders_list, hazards_list, all_other_characters_for_p1, current_enemies_list)

    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        player2.game_elements_ref_for_projectiles = game_elements_ref
        player2.update(dt_sec, platforms_list, ladders_list, hazards_list, all_other_characters_for_p2, current_enemies_list)

    active_players_for_ai = [p for p in [player1, player2] if p and hasattr(p, '_valid_init') and p._valid_init and not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]
    for enemy_instance in list(current_enemies_list):
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
            else:
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list, hazards_list, current_enemies_list)
            if not (hasattr(enemy_instance, 'alive') and enemy_instance.alive()):
                if enemy_instance in current_enemies_list: current_enemies_list.remove(enemy_instance)

    for statue_instance in list(statue_list):
        if hasattr(statue_instance, 'update') and hasattr(statue_instance, 'alive') and statue_instance.alive():
            statue_instance.update(dt_sec)
        if not (hasattr(statue_instance, 'alive') and statue_instance.alive()):
            if statue_instance in statue_list: statue_list.remove(statue_instance)

    hittable_targets_for_projectiles: List[Any] = []
    if player1 and player1.alive() and player1._valid_init and not getattr(player1, 'is_petrified', False): hittable_targets_for_projectiles.append(player1)
    if player2 and player2.alive() and player2._valid_init and not getattr(player2, 'is_petrified', False): hittable_targets_for_projectiles.append(player2)
    for enemy_target in current_enemies_list:
        if enemy_target.alive() and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    for statue_target in statue_list:
        if statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed:
            hittable_targets_for_projectiles.append(statue_target)

    for proj_instance in list(projectiles_list):
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list, hittable_targets_for_projectiles)
        if not (hasattr(proj_instance, 'alive') and proj_instance.alive()):
            if proj_instance in projectiles_list: projectiles_list.remove(proj_instance)

    if current_chest and isinstance(current_chest, Chest) and current_chest.alive():
        current_chest.update(dt_sec)
        if current_chest.state == 'closed':
            player_interacted_chest: Optional[Player] = None
            if player1 and player1.alive() and not player1.is_dead and not getattr(player1,'is_petrified',False) and \
               player1.rect.intersects(current_chest.rect) and \
               p1_action_events.get("interact", False):
                player_interacted_chest = player1
            elif player2 and player2.alive() and not player2.is_dead and not getattr(player2,'is_petrified',False) and \
                 player2.rect.intersects(current_chest.rect) and \
                 p2_action_events.get("interact", False):
                player_interacted_chest = player2
            if player_interacted_chest:
                current_chest.collect(player_interacted_chest)
                if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY: Player {player_interacted_chest.player_id} collected chest (state: {current_chest.state}).") # Use log_debug

    if current_chest and not current_chest.alive():
        if current_chest in collectible_items_list_ref:
            collectible_items_list_ref.remove(current_chest)
        game_elements_ref["current_chest"] = None
        current_chest = None

    if camera_obj:
        focus_target = None
        if player1 and player1.alive() and player1._valid_init and not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False): focus_target = player1
        elif player2 and player2.alive() and player2._valid_init and not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False): focus_target = player2
        elif player1 and player1.alive() and player1._valid_init: focus_target = player1
        elif player2 and player2.alive() and player2._valid_init: focus_target = player2
        if focus_target: camera_obj.update(focus_target)
        else: camera_obj.static_update()

    new_all_renderable_objects = []
    for obj_to_render in all_renderable_objects_ref:
        if isinstance(obj_to_render, (Platform, Ladder, Lava, BackgroundTile)):
            new_all_renderable_objects.append(obj_to_render)
        elif hasattr(obj_to_render, 'alive') and obj_to_render.alive():
            new_all_renderable_objects.append(obj_to_render)
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
        if _SCRIPT_LOGGING_ENABLED: log_info("Couch Play: Both players are gone. Game Over.")
        if show_status_message_callback: show_status_message_callback("Game Over! Both players defeated.")
        process_qt_events_callback()
        time.sleep(1.5)
        run_couch_play_mode._platform_debug_printed_couch = False
        return False

    return True