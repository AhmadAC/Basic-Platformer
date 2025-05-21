# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
"""
# version 2.0.15 (Enhanced debugging, robust access to game_elements, clear entity list management)

import time
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QRectF
import constants as C
from game_state_manager import reset_game_state # Assuming reset_game_state is robust
from enemy import Enemy
from items import Chest
from statue import Statue
from tiles import Platform, Ladder, Lava, BackgroundTile # For type checking
from player import Player # For type checking

# Logger
import logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers() and not logging.getLogger().hasHandlers():
    _couch_fallback_handler = logging.StreamHandler()
    _couch_fallback_formatter = logging.Formatter('COUCH_PLAY (Fallback): %(levelname)s - %(message)s')
    _couch_fallback_handler.setFormatter(_couch_fallback_formatter)
    logger.addHandler(_couch_fallback_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.warning("Central logger possibly unconfigured; couch_play_logic.py using its own console handler.")

_start_time_couch_play_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_couch_play_monotonic) * 1000)


def run_couch_play_mode(
    game_elements_ref: Dict[str, Any],
    app_status_obj: Any,
    get_p1_input_callback: callable, # Expected signature: (player_instance: Player) -> Dict[str, bool]
    get_p2_input_callback: callable, # Expected signature: (player_instance: Player) -> Dict[str, bool]
    process_qt_events_callback: callable,
    dt_sec_provider: callable,
    show_status_message_callback: Optional[callable] = None
    ) -> bool: # Returns True to continue, False to stop

    # --- Initial Safety Checks & Fetch Core Elements ---
    if not game_elements_ref.get('game_ready_for_logic', False) or \
       game_elements_ref.get('initialization_in_progress', True):
        if not hasattr(run_couch_play_mode, "_init_wait_logged_couch") or not run_couch_play_mode._init_wait_logged_couch: # type: ignore
            logger.debug("COUCH_PLAY: Waiting for game elements initialization to complete...")
            run_couch_play_mode._init_wait_logged_couch = True # type: ignore
        return True # Keep game loop ticking, but don't process logic yet

    # Reset init wait log flag if game is ready
    if hasattr(run_couch_play_mode, "_init_wait_logged_couch"):
        delattr(run_couch_play_mode, "_init_wait_logged_couch")


    player1: Optional[Player] = game_elements_ref.get("player1")
    player2: Optional[Player] = game_elements_ref.get("player2")
    platforms_list: List[Platform] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Ladder] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Lava] = game_elements_ref.get("hazards_list", [])
    # These lists will be modified in place, so fetch them once.
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_list: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list: List[Any] = game_elements_ref.get("collectible_list", [])
    all_renderable_objects_ref: List[Any] = game_elements_ref.get("all_renderable_objects", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")
    
    # Debug: Log content of platforms_list on first valid tick
    if not hasattr(run_couch_play_mode, "_platform_debug_printed_couch") or not run_couch_play_mode._platform_debug_printed_couch : # type: ignore
        logger.debug(f"COUCH_PLAY: First valid tick. Platforms: {len(platforms_list)}, Ladders: {len(ladders_list)}, Hazards: {len(hazards_list)}")
        if platforms_list:
            for i, p_debug in enumerate(platforms_list[:min(3, len(platforms_list))]):
                 logger.debug(f"  Platform {i}: rect={getattr(p_debug, 'rect', 'N/A')}, type={getattr(p_debug, 'platform_type', 'N/A')}")
        elif not game_elements_ref.get("level_data"):
            logger.warning("COUCH_PLAY: platforms_list is empty AND level_data is missing from game_elements!")
        else:
            logger.warning("COUCH_PLAY: platforms_list is empty. This is unusual if a map was loaded.")
        run_couch_play_mode._platform_debug_printed_couch = True # type: ignore


    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    # --- Player Input ---
    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
       hasattr(player2, 'control_scheme') and player2.control_scheme is not None:
        p2_action_events = get_p2_input_callback(player2)

    # --- Handle Pause/Reset ---
    if p1_action_events.get("pause") or p2_action_events.get("pause"):
        logger.info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        run_couch_play_mode._platform_debug_printed_couch = False # Reset for next game
        return False # Signal to stop

    if p1_action_events.get("reset") or p2_action_events.get("reset"):
        logger.info("Couch Play: Game state reset initiated by player action.")
        # reset_game_state now re-populates lists in game_elements_ref directly
        new_chest_after_reset = reset_game_state(game_elements_ref)
        game_elements_ref["current_chest"] = new_chest_after_reset
        # Re-fetch list references as reset_game_state might have changed them
        current_enemies_list = game_elements_ref.get("enemy_list", [])
        statue_list = game_elements_ref.get("statue_objects", [])
        projectiles_list = game_elements_ref.get("projectiles_list", [])
        collectible_items_list = game_elements_ref.get("collectible_list", [])
        all_renderable_objects_ref = game_elements_ref.get("all_renderable_objects", [])
        logger.debug(f"COUCH_PLAY Reset: Enemies={len(current_enemies_list)}, Statues={len(statue_list)}, Collectibles={len(collectible_items_list)}")


    # --- Player Updates ---
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        other_players_for_p1 = [p for p in [player2] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player1]
        player1.game_elements_ref_for_projectiles = game_elements_ref
        player1.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p1, current_enemies_list)

    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        other_players_for_p2 = [p for p in [player1] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive() and p is not player2]
        player2.game_elements_ref_for_projectiles = game_elements_ref
        player2.update(dt_sec, platforms_list, ladders_list, hazards_list, other_players_for_p2, current_enemies_list)

    # --- Enemy Updates ---
    active_players_for_ai = [p for p in [player1, player2] if p and hasattr(p, '_valid_init') and p._valid_init and not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]
    
    # Iterate over a copy of the list if modifications (removal) are done inside the loop
    for enemy_instance in list(current_enemies_list): # Use the list fetched at the start
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
            else:
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list, hazards_list, current_enemies_list)

            if not (hasattr(enemy_instance, 'alive') and enemy_instance.alive()):
                if enemy_instance in current_enemies_list: # Check before removing
                    current_enemies_list.remove(enemy_instance) # Modify the fetched list

    # --- Statue Updates ---
    for statue_instance in list(statue_list): # Use the list fetched at the start
        if hasattr(statue_instance, 'update') and hasattr(statue_instance, 'alive') and statue_instance.alive():
            statue_instance.update(dt_sec)
        if not (hasattr(statue_instance, 'alive') and statue_instance.alive()):
            if statue_instance in statue_list: # Check before removing
                statue_list.remove(statue_instance)

    # --- Projectile Updates ---
    hittable_targets_for_projectiles: List[Any] = []
    # Build list of hittable targets (Players, Enemies, Statues)
    if player1 and hasattr(player1, 'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and not getattr(player1, 'is_petrified', False): hittable_targets_for_projectiles.append(player1)
    if player2 and hasattr(player2, 'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and not getattr(player2, 'is_petrified', False): hittable_targets_for_projectiles.append(player2)
    for enemy_target in current_enemies_list: # Use the already potentially modified list
        if hasattr(enemy_target, 'alive') and enemy_target.alive() and hasattr(enemy_target, '_valid_init') and enemy_target._valid_init and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    for statue_target in statue_list: # Use the already potentially modified list
        if hasattr(statue_target, 'alive') and statue_target.alive() and hasattr(statue_target, 'is_smashed') and not statue_target.is_smashed:
            hittable_targets_for_projectiles.append(statue_target)

    for proj_instance in list(projectiles_list): # Use the list fetched at the start
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list, hittable_targets_for_projectiles)
        if not (hasattr(proj_instance, 'alive') and proj_instance.alive()):
            if proj_instance in projectiles_list: # Check before removing
                projectiles_list.remove(proj_instance)

    # --- Collectible (Chest) Physics & Interaction ---
    current_chest = game_elements_ref.get("current_chest")
    if current_chest and isinstance(current_chest, Chest) and current_chest.alive() and \
       not current_chest.is_collected_flag_internal and current_chest.state == 'closed':
        
        # Ensure rect is up-to-date before physics
        if hasattr(current_chest, '_update_rect_from_image_and_pos'):
            current_chest._update_rect_from_image_and_pos()

        # Apply physics step (gravity)
        if hasattr(current_chest, 'apply_physics_step'):
            current_chest.apply_physics_step(dt_sec) # Chest handles its own physics now

        # Check for ground collision after physics step
        # This part needs to be precise and use the chest's current rect after its pos was updated by physics
        current_chest.on_ground = False # Assume not on ground
        if hasattr(current_chest, 'rect') and isinstance(current_chest.rect, QRectF):
            # The chest's rect should have been updated by _update_rect_from_image_and_pos within apply_physics_step
            # So, its rect.bottom() is now its new potential bottom.
            # We need to compare this new bottom with platform tops.
            # To correctly check if it *was* above, we need its position *before* this frame's Y velocity was applied.
            # This is tricky if apply_physics_step already moved it.
            # A common way is to resolve Y collision *after* Y movement.
            # Let's assume apply_physics_step updates pos_midbottom, then _update_rect_from_image_and_pos updates rect.
            
            # Simplified check: If it's intersecting and its bottom is below or at platform top, consider it landed.
            # This is less precise than checking "was_above_last_frame".
            for platform_collidable in platforms_list:
                if not hasattr(platform_collidable, 'rect') or not isinstance(platform_collidable.rect, QRectF):
                    continue

                if current_chest.rect.intersects(platform_collidable.rect):
                    # A more robust check would involve knowing the chest's velocity
                    # and its position *before* the Y-velocity was applied in this frame.
                    # If we assume vel_y is per-frame delta:
                    previous_bottom_y = current_chest.rect.bottom() - current_chest.vel_y
                    
                    if current_chest.vel_y >= 0 and \
                       current_chest.rect.bottom() >= platform_collidable.rect.top() and \
                       previous_bottom_y <= platform_collidable.rect.top() + 1.0 : # +1 for small tolerance

                        min_overlap_ratio_chest = 0.1
                        min_horizontal_overlap_chest = current_chest.rect.width() * min_overlap_ratio_chest
                        actual_overlap_width_chest = min(current_chest.rect.right(), platform_collidable.rect.right()) - \
                                                   max(current_chest.rect.left(), platform_collidable.rect.left())

                        if actual_overlap_width_chest >= min_horizontal_overlap_chest:
                            current_chest.rect.moveBottom(platform_collidable.rect.top())
                            current_chest.pos_midbottom.setY(current_chest.rect.bottom())
                            current_chest.vel_y = 0.0
                            current_chest.on_ground = True
                            if hasattr(current_chest, '_update_rect_from_image_and_pos'): # Final rect sync
                                current_chest._update_rect_from_image_and_pos()
                            break # Landed on one platform

    # Collectible Animation/State Update (after physics and collision)
    for collectible in list(collectible_items_list): # Use the list fetched at the start
        if hasattr(collectible, 'update') and hasattr(collectible, 'alive') and collectible.alive():
            collectible.update(dt_sec) # This handles animation, opening, etc.

        if not (hasattr(collectible, 'alive') and collectible.alive()):
            if collectible in collectible_items_list: collectible_items_list.remove(collectible)
            if game_elements_ref.get("current_chest") is collectible:
                game_elements_ref["current_chest"] = None

    # Chest Interaction (after physics and animation updates)
    current_chest_for_interaction = game_elements_ref.get("current_chest")
    if current_chest_for_interaction and isinstance(current_chest_for_interaction, Chest) and \
       current_chest_for_interaction.alive() and \
       not getattr(current_chest_for_interaction, 'is_collected_flag_internal', True): # Check if not already collected
        player_interacted_chest: Optional[Player] = None
        # Check P1
        if player1 and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and player1.alive() and \
           not getattr(player1, 'is_petrified', False) and \
           hasattr(player1, 'rect') and player1.rect.intersects(current_chest_for_interaction.rect) and \
           p1_action_events.get("interact", False):
            player_interacted_chest = player1
        # Check P2 (if no P1 interaction)
        elif player2 and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and player2.alive() and \
             not getattr(player2, 'is_petrified', False) and \
             hasattr(player2, 'rect') and player2.rect.intersects(current_chest_for_interaction.rect) and \
             p2_action_events.get("interact", False):
            player_interacted_chest = player2

        if player_interacted_chest:
            current_chest_for_interaction.collect(player_interacted_chest)
            logger.debug(f"COUCH_PLAY: Player {player_interacted_chest.player_id} collected chest.")


    # --- Camera Update ---
    if camera_obj:
        focus_target = None
        if player1 and hasattr(player1,'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init and \
           not getattr(player1, 'is_dead', True) and not getattr(player1, 'is_petrified', False): focus_target = player1
        elif player2 and hasattr(player2,'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init and \
             not getattr(player2, 'is_dead', True) and not getattr(player2, 'is_petrified', False): focus_target = player2
        elif player1 and hasattr(player1,'alive') and player1.alive() and hasattr(player1, '_valid_init') and player1._valid_init: focus_target = player1 # Fallback if one is dead/petrified
        elif player2 and hasattr(player2,'alive') and player2.alive() and hasattr(player2, '_valid_init') and player2._valid_init: focus_target = player2

        if focus_target: camera_obj.update(focus_target)
        else: camera_obj.static_update()

    # --- Prune all_renderable_objects list ---
    # This list is primarily for GameSceneWidget. It should contain all visible static and dynamic objects.
    new_all_renderable_objects = []
    for obj_to_render in all_renderable_objects_ref: # Iterate over the list fetched at the start
        if isinstance(obj_to_render, (Platform, Ladder, Lava, BackgroundTile)): # Static tiles are always "alive"
            new_all_renderable_objects.append(obj_to_render)
        elif hasattr(obj_to_render, 'alive') and obj_to_render.alive(): # Dynamic objects check alive()
            new_all_renderable_objects.append(obj_to_render)
    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects # Update the reference in game_elements

    # --- Check Game Over Condition ---
    p1_gone = True
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        if player1.alive(): # Player instance might be "alive" but game character is "dead"
            if getattr(player1, 'is_dead', False):
                if getattr(player1, 'is_petrified', False) and not getattr(player1, 'is_stone_smashed', False): p1_gone = False # Petrified but not smashed is not "gone"
                elif not getattr(player1, 'death_animation_finished', True): p1_gone = False # Death anim not finished
            else: p1_gone = False # Not dead
    
    p2_gone = True
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        if player2.alive():
            if getattr(player2, 'is_dead', False):
                if getattr(player2, 'is_petrified', False) and not getattr(player2, 'is_stone_smashed', False): p2_gone = False
                elif not getattr(player2, 'death_animation_finished', True): p2_gone = False
            else: p2_gone = False

    if p1_gone and p2_gone:
        logger.info("Couch Play: Both players are gone. Game Over.")
        if show_status_message_callback: show_status_message_callback("Game Over! Both players defeated.")
        process_qt_events_callback() # Allow UI to update with message
        time.sleep(1.5) # Brief pause to show message
        run_couch_play_mode._platform_debug_printed_couch = False # Reset for next game
        return False # Signal to stop game mode

    return True # Continue game mode