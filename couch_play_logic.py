# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.11 (Fixed old_chest_bottom definition, refined chest physics check)
# version 2.0.12 (Ensure player references are valid before use)

import time
from typing import Dict, List, Any, Optional
from tiles import Platform, Ladder, Lava, BackgroundTile # BackgroundTile used in all_renderable filter
# --- PySide6 Imports for Type Checking ---
from PySide6.QtCore import QRectF, QPointF
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

import constants as C
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest
from statue import Statue
# Player is implicitly used via game_elements_ref, no direct Player import needed here

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

    player1: Optional[Any] = game_elements_ref.get("player1")
    player2: Optional[Any] = game_elements_ref.get("player2")
    platforms_list: List[Any] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Any] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Any] = game_elements_ref.get("hazards_list", [])
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_list: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list: List[Any] = game_elements_ref.get("collectible_list", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")

    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1, platforms_list)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
       hasattr(player2, 'control_scheme') and player2.control_scheme is not None: # P2 might be a shell if host
        p2_action_events = get_p2_input_callback(player2, platforms_list)

    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        log_info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        return False

    if p1_action_events.get("reset") or p2_action_events.get("reset"):
        log_info("Couch Play: Game state reset initiated by player action.")
        new_chest_after_reset = reset_game_state(game_elements_ref)
        game_elements_ref["current_chest"] = new_chest_after_reset
        # Refresh local list references after reset_game_state as it modifies game_elements_ref
        current_enemies_list = game_elements_ref.get("enemy_list", [])
        statue_list = game_elements_ref.get("statue_objects", [])
        projectiles_list = game_elements_ref.get("projectiles_list", [])
        collectible_items_list = game_elements_ref.get("collectible_list", [])
        # Ensure players are back in renderables if they were removed by death
        if player1 and player1._valid_init and player1.alive() and player1 not in game_elements_ref.get("all_renderable_objects",[]):
             game_elements_ref.get("all_renderable_objects",[]).append(player1)
        if player2 and player2._valid_init and player2.alive() and player2 not in game_elements_ref.get("all_renderable_objects",[]):
             game_elements_ref.get("all_renderable_objects",[]).append(player2)


    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        other_players_for_p1 = [p for p in [player2] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player1]
        player1.game_elements_ref_for_projectiles = game_elements_ref # Ensure ref is set
        player1.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p1, current_enemies_list)

    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        other_players_for_p2 = [p for p in [player1] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player2]
        player2.game_elements_ref_for_projectiles = game_elements_ref # Ensure ref is set
        player2.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p2, current_enemies_list)

    active_players_for_ai = [p for p in [player1, player2] if p and hasattr(p, '_valid_init') and p._valid_init and not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]

    for enemy_instance in list(current_enemies_list): # Iterate over a copy for safe removal
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
            else:
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list, hazards_list, current_enemies_list)

            if not (hasattr(enemy_instance, 'alive') and enemy_instance.alive()):
                if enemy_instance in current_enemies_list: current_enemies_list.remove(enemy_instance)

    for statue_instance in list(statue_list): # Iterate over a copy
        if hasattr(statue_instance, 'update') and hasattr(statue_instance, 'alive') and statue_instance.alive():
            statue_instance.update(dt_sec)
        if not (hasattr(statue_instance, 'alive') and statue_instance.alive()):
            if statue_instance in statue_list: statue_list.remove(statue_instance)

    hittable_targets_for_projectiles: List[Any] = []
    if player1 and hasattr(player1, 'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and not getattr(player1, 'is_petrified', False): hittable_targets_for_projectiles.append(player1)
    if player2 and hasattr(player2, 'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and not getattr(player2, 'is_petrified', False): hittable_targets_for_projectiles.append(player2)
    for enemy_target in current_enemies_list:
        if hasattr(enemy_target, 'alive') and enemy_target.alive() and hasattr(enemy_target, '_valid_init') and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    for statue_target in statue_list:
        if hasattr(statue_target, 'alive') and statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed:
            hittable_targets_for_projectiles.append(statue_target)

    for proj_instance in list(projectiles_list): # Iterate over a copy
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list, hittable_targets_for_projectiles)
        if not (hasattr(proj_instance, 'alive') and proj_instance.alive()):
            if proj_instance in projectiles_list: projectiles_list.remove(proj_instance)

    # --- Physics and Collision for Chest ---
    current_chest = game_elements_ref.get("current_chest")
    if current_chest and isinstance(current_chest, Chest) and current_chest.alive() and \
       not current_chest.is_collected_flag_internal and current_chest.state == 'closed':

        if hasattr(current_chest, '_update_rect_from_image_and_pos'):
            current_chest._update_rect_from_image_and_pos()

        old_chest_bottom_for_collision_check = 0.0
        if hasattr(current_chest, 'rect') and isinstance(current_chest.rect, QRectF):
             old_chest_bottom_for_collision_check = current_chest.rect.bottom()

        if hasattr(current_chest, 'apply_physics_step'):
            current_chest.apply_physics_step(dt_sec)

        current_chest.on_ground = False
        if hasattr(current_chest, 'rect') and isinstance(current_chest.rect, QRectF):
            for platform_collidable in platforms_list:
                if not hasattr(platform_collidable, 'rect') or not isinstance(platform_collidable.rect, QRectF):
                    continue

                if current_chest.rect.intersects(platform_collidable.rect):
                    if current_chest.vel_y >= 0 and \
                       current_chest.rect.bottom() >= platform_collidable.rect.top() and \
                       old_chest_bottom_for_collision_check <= platform_collidable.rect.top() + 1.0 :

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
        else:
            log_warning(f"Couch Play: Chest object missing valid rect attribute for physics after apply_physics_step.")


    # --- Update Collectibles (Animation & State - after physics) ---
    for collectible in list(collectible_items_list): # Iterate over a copy
        if hasattr(collectible, 'update') and hasattr(collectible, 'alive') and collectible.alive():
            collectible.update(dt_sec)

        if not (hasattr(collectible, 'alive') and collectible.alive()):
            if collectible in collectible_items_list: collectible_items_list.remove(collectible)
            if game_elements_ref.get("current_chest") is collectible:
                game_elements_ref["current_chest"] = None


    # --- Chest Interaction ---
    current_chest_for_interaction = game_elements_ref.get("current_chest")
    if current_chest_for_interaction and isinstance(current_chest_for_interaction, Chest) and \
       current_chest_for_interaction.alive() and \
       not getattr(current_chest_for_interaction, 'is_collected_flag_internal', True):
        player_interacted_chest: Optional[Any] = None
        if player1 and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and player1.alive() and \
           not getattr(player1, 'is_petrified', False) and \
           hasattr(player1, 'rect') and player1.rect.intersects(current_chest_for_interaction.rect) and \
           p1_action_events.get("interact", False):
            player_interacted_chest = player1
        elif player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and player2.alive() and \
             not getattr(player2, 'is_petrified', False) and \
             hasattr(player2, 'rect') and player2.rect.intersects(current_chest_for_interaction.rect) and \
             p2_action_events.get("interact", False):
            player_interacted_chest = player2

        if player_interacted_chest: current_chest_for_interaction.collect(player_interacted_chest)

    if camera_obj:
        focus_target = None
        if player1 and hasattr(player1,'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False): focus_target = player1
        elif player2 and hasattr(player2,'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False): focus_target = player2
        elif player1 and hasattr(player1,'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init: focus_target = player1 # Fallback to any alive P1
        elif player2 and hasattr(player2,'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init: focus_target = player2 # Fallback to any alive P2

        if focus_target: camera_obj.update(focus_target)
        else: camera_obj.static_update()

    # Update all_renderable_objects list
    current_all_renderables = game_elements_ref.get("all_renderable_objects", [])
    new_all_renderable_objects = []

    for obj in current_all_renderables:
        if isinstance(obj, (Platform, Ladder, Lava, BackgroundTile)): # Static elements
            new_all_renderable_objects.append(obj)
        elif hasattr(obj, 'alive') and obj.alive(): # Dynamic elements if alive
            new_all_renderable_objects.append(obj)
    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects

    # Game Over Check
    p1_gone = True
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        if player1.alive(): # alive() from Player class checks internal _alive flag
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False): p1_gone = False # Petrified but not smashed is still "on screen"
                elif not getattr(player1, 'death_animation_finished', True): p1_gone = False # Death anim playing
            else: p1_gone = False # Not dead
    
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
        process_qt_events_callback() # Allow UI to update with message
        time.sleep(1.5) # Brief pause before exiting mode
        return False # Signal to stop the game mode

    return True