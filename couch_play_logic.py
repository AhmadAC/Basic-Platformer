# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
Handles game logic for local couch co-op mode using PySide6.
UI rendering and input capture are handled by the main Qt application.
MODIFIED: Statue physics and lifecycle management in game loop.
MODIFIED: Chest can insta-kill player if it lands from sufficient height.
MODIFIED: Chest interaction rect is slightly expanded.
"""
# version 2.0.21 (Chest Interaction Rect Expanded)

import time
import math # Added for math.sqrt in chest-crush logic
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QRectF # Ensure QRectF is imported
import constants as C
from game_state_manager import reset_game_state
from enemy import Enemy
from items import Chest # Ensure Chest is imported
from statue import Statue 
from tiles import Platform, Ladder, Lava, BackgroundTile
from player import Player

# --- Per-script logging toggle ---
_SCRIPT_LOGGING_ENABLED = True
# --- End per-script logging toggle ---

# Logger
import logging
logger_couch = logging.getLogger(__name__)

def log_info(msg, *args, **kwargs): logger_couch.info(msg, *args, **kwargs)
def log_debug(msg, *args, **kwargs): logger_couch.debug(msg, *args, **kwargs)
def log_warning(msg, *args, **kwargs): logger_couch.warning(msg, *args, **kwargs)
def log_error(msg, *args, **kwargs): logger_couch.error(msg, *args, **kwargs)
def log_critical(msg, *args, **kwargs): logger_couch.critical(msg, *args, **kwargs)

try:
    from logger import info as project_info, debug as project_debug, \
                       warning as project_warning, error as project_error, \
                       critical as project_critical

    log_info = project_info
    log_debug = project_debug
    log_warning = project_warning
    log_error = project_error
    log_critical = project_critical
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

    if not game_elements_ref.get('game_ready_for_logic', False) or \
       game_elements_ref.get('initialization_in_progress', True):
        if _SCRIPT_LOGGING_ENABLED and (not hasattr(run_couch_play_mode, "_init_wait_logged_couch") or not run_couch_play_mode._init_wait_logged_couch): # type: ignore
            log_debug("COUCH_PLAY: Waiting for game elements initialization to complete...")
            run_couch_play_mode._init_wait_logged_couch = True # type: ignore
        return True

    if hasattr(run_couch_play_mode, "_init_wait_logged_couch"):
        delattr(run_couch_play_mode, "_init_wait_logged_couch")

    player1: Optional[Player] = game_elements_ref.get("player1")
    player2: Optional[Player] = game_elements_ref.get("player2")
    player3: Optional[Player] = game_elements_ref.get("player3")
    player4: Optional[Player] = game_elements_ref.get("player4")
    platforms_list_this_frame: List[Any] = game_elements_ref.get("platforms_list", [])
    ladders_list: List[Ladder] = game_elements_ref.get("ladders_list", [])
    hazards_list: List[Lava] = game_elements_ref.get("hazards_list", [])
    current_enemies_list: List[Enemy] = game_elements_ref.get("enemy_list", [])
    statue_objects_list_ref: List[Statue] = game_elements_ref.get("statue_objects", [])
    projectiles_list: List[Any] = game_elements_ref.get("projectiles_list", [])
    collectible_items_list_ref: List[Any] = game_elements_ref.get("collectible_list", [])
    current_chest: Optional[Chest] = game_elements_ref.get("current_chest")
    all_renderable_objects_ref: List[Any] = game_elements_ref.get("all_renderable_objects", [])
    camera_obj: Optional[Any] = game_elements_ref.get("camera")

    if _SCRIPT_LOGGING_ENABLED and (not hasattr(run_couch_play_mode, "_platform_debug_printed_couch") or not run_couch_play_mode._platform_debug_printed_couch) : # type: ignore
        log_debug(f"COUCH_PLAY: First valid tick. Platforms (inc statues): {len(platforms_list_this_frame)}, Ladders: {len(ladders_list)}, Hazards: {len(hazards_list)}, Chest: {'Present' if current_chest else 'None'}")
        run_couch_play_mode._platform_debug_printed_couch = True # type: ignore

    dt_sec = dt_sec_provider()
    current_game_time_ms = get_current_ticks_monotonic()

    p1_action_events: Dict[str, bool] = {}
    if player1 and hasattr(player1, '_valid_init') and player1._valid_init:
        p1_action_events = get_p1_input_callback(player1)

    p2_action_events: Dict[str, bool] = {}
    if player2 and hasattr(player2, '_valid_init') and player2._valid_init:
        p2_action_events = get_p2_input_callback(player2)

    p3_action_events: Dict[str, bool] = {}
    if player3 and hasattr(player3, '_valid_init') and player3._valid_init:
        p3_action_events = get_p3_input_callback(player3)

    p4_action_events: Dict[str, bool] = {}
    if player4 and hasattr(player4, '_valid_init') and player4._valid_init:
        p4_action_events = get_p4_input_callback(player4)

    if p1_action_events.get("pause") or p2_action_events.get("pause") or \
       p3_action_events.get("pause") or p4_action_events.get("pause"):
        if _SCRIPT_LOGGING_ENABLED: log_info("Couch Play: Pause action detected. Signaling app to stop this game mode.")
        if show_status_message_callback: show_status_message_callback("Exiting Couch Play...")
        run_couch_play_mode._platform_debug_printed_couch = False
        return False

    if p1_action_events.get("reset") or p2_action_events.get("reset") or \
       p3_action_events.get("reset") or p4_action_events.get("reset"):
        if _SCRIPT_LOGGING_ENABLED: log_info("Couch Play: Game state reset initiated by player action.")
        reset_game_state(game_elements_ref)
        player1 = game_elements_ref.get("player1"); player2 = game_elements_ref.get("player2")
        player3 = game_elements_ref.get("player3"); player4 = game_elements_ref.get("player4")
        platforms_list_this_frame = game_elements_ref.get("platforms_list", [])
        ladders_list = game_elements_ref.get("ladders_list", [])
        hazards_list = game_elements_ref.get("hazards_list", [])
        current_enemies_list = game_elements_ref.get("enemy_list", [])
        statue_objects_list_ref = game_elements_ref.get("statue_objects", [])
        projectiles_list = game_elements_ref.get("projectiles_list", [])
        collectible_items_list_ref = game_elements_ref.get("collectible_list", [])
        current_chest = game_elements_ref.get("current_chest")
        if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY Reset: Enemies={len(current_enemies_list)}, Statues={len(statue_objects_list_ref)}, Collectibles={len(collectible_items_list_ref)}, CurrentChest: {'Present' if current_chest else 'None'}")

    # --- Chest Update (Physics and Interactions) ---
    if current_chest and isinstance(current_chest, Chest) and current_chest.alive():
        current_chest.apply_physics_step(dt_sec) # Physics updated, vel_y is current for this frame

        chest_landed_on_player_and_killed = False
        if not current_chest.is_collected_flag_internal and current_chest.state == 'closed':
            player_instances_for_chest_check = [
                p for p in [player1, player2, player3, player4]
                if p and hasattr(p, '_valid_init') and p._valid_init and \
                   hasattr(p, 'alive') and p.alive() and \
                   not getattr(p, 'is_dead', True) and \
                   not getattr(p, 'is_petrified', False)
            ]

            for p_instance_crush_check in player_instances_for_chest_check:
                if not (hasattr(current_chest, 'rect') and isinstance(current_chest.rect, QRectF) and \
                        hasattr(p_instance_crush_check, 'rect') and isinstance(p_instance_crush_check.rect, QRectF)):
                    continue

                if current_chest.rect.intersects(p_instance_crush_check.rect):
                    is_chest_falling_meaningfully = hasattr(current_chest, 'vel_y') and current_chest.vel_y > 1.0
                    vertical_overlap_landing = current_chest.rect.bottom() >= p_instance_crush_check.rect.top() and \
                                             current_chest.rect.top() < p_instance_crush_check.rect.bottom()
                    is_landing_on_head_area = vertical_overlap_landing and \
                                              current_chest.rect.bottom() <= p_instance_crush_check.rect.top() + (p_instance_crush_check.rect.height() * 0.6)
                    min_horizontal_overlap_for_crush = current_chest.rect.width() * 0.3
                    actual_horizontal_overlap_for_crush = min(current_chest.rect.right(), p_instance_crush_check.rect.right()) - \
                                                          max(current_chest.rect.left(), p_instance_crush_check.rect.left())
                    has_sufficient_horizontal_overlap = actual_horizontal_overlap_for_crush >= min_horizontal_overlap_for_crush

                    if is_chest_falling_meaningfully and is_landing_on_head_area and has_sufficient_horizontal_overlap:
                        player_height_for_calc = getattr(p_instance_crush_check, 'standing_collision_height', float(C.TILE_SIZE) * 1.5)
                        if player_height_for_calc <= 0: player_height_for_calc = 60.0
                        
                        required_fall_distance = 2.0 * player_height_for_calc
                        
                        try:
                            gravity_val = float(C.PLAYER_GRAVITY)
                            if gravity_val <= 0: gravity_val = 0.7 
                            if required_fall_distance <=0: required_fall_distance = 1.0 
                            
                            min_vel_y_for_kill_sq = 2 * gravity_val * required_fall_distance
                            vel_y_for_kill_threshold = math.sqrt(min_vel_y_for_kill_sq) if min_vel_y_for_kill_sq > 0 else 0.0
                        except ValueError: 
                            vel_y_for_kill_threshold = 10.0
                            if _SCRIPT_LOGGING_ENABLED: log_error(f"Math error calculating vel_y_for_kill_threshold. Gravity: {C.PLAYER_GRAVITY}, ReqDist: {required_fall_distance}")

                        has_fallen_with_kill_velocity = current_chest.vel_y >= vel_y_for_kill_threshold

                        if _SCRIPT_LOGGING_ENABLED:
                            log_debug(f"Chest-Player Collision: ChestVelY={current_chest.vel_y:.2f}, KillThresholdVelY={vel_y_for_kill_threshold:.2f}, FallDistForVelCalc={required_fall_distance:.1f}")

                        if has_fallen_with_kill_velocity:
                            if hasattr(p_instance_crush_check, 'insta_kill'):
                                if _SCRIPT_LOGGING_ENABLED: log_info(f"CRUSH: Chest landed on Player {p_instance_crush_check.player_id} with kill velocity. Insta-killing.")
                                p_instance_crush_check.insta_kill()
                            else:
                                if _SCRIPT_LOGGING_ENABLED: log_warning(f"CRUSH_FAIL: Player {p_instance_crush_check.player_id} missing insta_kill(). Using take_damage(max_health).")
                                p_instance_crush_check.take_damage(p_instance_crush_check.max_health * 10)
                            
                            current_chest.rect.moveBottom(p_instance_crush_check.rect.top())
                            if hasattr(current_chest, 'pos_midbottom'): current_chest.pos_midbottom.setY(current_chest.rect.bottom())
                            current_chest.vel_y = 0.0
                            current_chest.on_ground = True
                            chest_landed_on_player_and_killed = True
                            if hasattr(current_chest, '_update_rect_from_image_and_pos'):
                                current_chest._update_rect_from_image_and_pos()
                            break # Player was killed, stop checking other players for this chest this frame
        
        current_chest.on_ground = False # Reset before platform collision
        if chest_landed_on_player_and_killed:
            current_chest.on_ground = True # It landed on player and killed them
        
        if not chest_landed_on_player_and_killed and \
           not current_chest.is_collected_flag_internal and current_chest.state == 'closed':
            for platform_collidable in platforms_list_this_frame:
                if isinstance(platform_collidable, Statue) and platform_collidable.is_smashed: continue
                if not hasattr(platform_collidable, 'rect') or not isinstance(platform_collidable.rect, QRectF): continue
                if current_chest.rect.intersects(platform_collidable.rect):
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
                            if hasattr(current_chest, 'pos_midbottom'): current_chest.pos_midbottom.setY(current_chest.rect.bottom())
                            current_chest.vel_y = 0.0
                            current_chest.on_ground = True
                            break
            if hasattr(current_chest, '_update_rect_from_image_and_pos'):
                current_chest._update_rect_from_image_and_pos()
        
        current_chest.update(dt_sec) # Animation and state
        
        if current_chest.state == 'closed' and not current_chest.is_collected_flag_internal:
            player_interacted_chest: Optional[Player] = None
            player_action_pairs = [
                (player1, p1_action_events), (player2, p2_action_events),
                (player3, p3_action_events), (player4, p4_action_events)
            ]
            # MODIFIED INTERACTION CHECK HERE
            interaction_chest_rect_couch = QRectF(current_chest.rect).adjusted(-5, -5, 5, 5) # Expand by 5px
            for p_instance_chest, p_actions_chest in player_action_pairs:
                if p_instance_chest and hasattr(p_instance_chest, 'alive') and p_instance_chest.alive() and \
                   not getattr(p_instance_chest, 'is_dead', True) and not getattr(p_instance_chest,'is_petrified',False) and \
                   hasattr(p_instance_chest, 'rect') and p_instance_chest.rect.intersects(interaction_chest_rect_couch) and \
                   p_actions_chest.get("interact", False): # Use adjusted rect
                    player_interacted_chest = p_instance_chest
                    break
            if player_interacted_chest:
                current_chest.collect(player_interacted_chest)
                if _SCRIPT_LOGGING_ENABLED: log_debug(f"COUCH_PLAY: Player {player_interacted_chest.player_id} collected chest (state: {current_chest.state}).")
    # --- End Chest Update ---

    active_players_for_collision_check = [p for p in [player1, player2, player3, player4] if p and hasattr(p, '_valid_init') and p._valid_init and hasattr(p, 'alive') and p.alive()]
    
    player_instances_to_update = [p for p in [player1, player2, player3, player4] if p and hasattr(p, '_valid_init') and p._valid_init]
    for p_instance in player_instances_to_update:
        all_others_for_this_player = [other_p for other_p in active_players_for_collision_check if other_p is not p_instance]
        if current_chest and current_chest.alive() and current_chest.state == 'closed':
            all_others_for_this_player.append(current_chest)
        p_instance.game_elements_ref_for_projectiles = game_elements_ref
        p_instance.update(dt_sec, platforms_list_this_frame, ladders_list, hazards_list, all_others_for_this_player, current_enemies_list)

    active_players_for_ai = [p for p in player_instances_to_update if not getattr(p, 'is_dead', True) and hasattr(p, 'alive') and p.alive()]
    
    enemies_to_keep_this_frame = []
    for enemy_instance in list(current_enemies_list):
        if hasattr(enemy_instance, '_valid_init') and enemy_instance._valid_init:
            if hasattr(enemy_instance, 'is_petrified') and enemy_instance.is_petrified:
                if hasattr(enemy_instance, 'update_enemy_status_effects'):
                     enemy_instance.update_enemy_status_effects(current_game_time_ms, platforms_list_this_frame)
                if hasattr(enemy_instance, 'animate'): enemy_instance.animate()
            else:
                enemy_instance.update(dt_sec, active_players_for_ai, platforms_list_this_frame, hazards_list, current_enemies_list)
            
            if hasattr(enemy_instance, 'alive') and enemy_instance.alive():
                enemies_to_keep_this_frame.append(enemy_instance)
            elif _SCRIPT_LOGGING_ENABLED:
                log_debug(f"CouchPlay: Enemy {getattr(enemy_instance, 'enemy_id', 'N/A')} no longer alive. Removing.")
    game_elements_ref["enemy_list"] = enemies_to_keep_this_frame

    statues_to_keep_this_frame_couch = []
    statues_killed_this_frame_couch = []
    for statue_instance_couch in list(statue_objects_list_ref):
        if hasattr(statue_instance_couch, 'alive') and statue_instance_couch.alive():
            if hasattr(statue_instance_couch, 'apply_physics_step') and not statue_instance_couch.is_smashed:
                statue_instance_couch.apply_physics_step(dt_sec, platforms_list_this_frame)
            
            if hasattr(statue_instance_couch, 'update'):
                statue_instance_couch.update(dt_sec)
            
            if statue_instance_couch.alive():
                statues_to_keep_this_frame_couch.append(statue_instance_couch)
            else:
                statues_killed_this_frame_couch.append(statue_instance_couch)
                if _SCRIPT_LOGGING_ENABLED: log_debug(f"CouchPlay: Statue {statue_instance_couch.statue_id} no longer alive.")
    
    game_elements_ref["statue_objects"] = statues_to_keep_this_frame_couch
    
    if statues_killed_this_frame_couch:
        current_main_platforms = game_elements_ref.get("platforms_list", [])
        new_main_platforms_list = [
            p for p in current_main_platforms
            if not (isinstance(p, Statue) and p in statues_killed_this_frame_couch)
        ]
        if len(new_main_platforms_list) != len(current_main_platforms):
            game_elements_ref["platforms_list"] = new_main_platforms_list
            platforms_list_this_frame = new_main_platforms_list
            if _SCRIPT_LOGGING_ENABLED: log_debug(f"CouchPlay: Updated main platforms_list after statue removal. Count: {len(new_main_platforms_list)}")

    hittable_targets_for_projectiles: List[Any] = []
    for p_target in player_instances_to_update:
        if hasattr(p_target, 'alive') and p_target.alive() and not getattr(p_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(p_target)
    for enemy_target in game_elements_ref.get("enemy_list",[]):
        if hasattr(enemy_target, 'alive') and enemy_target.alive() and not getattr(enemy_target, 'is_petrified', False):
            hittable_targets_for_projectiles.append(enemy_target)
    for statue_target in game_elements_ref.get("statue_objects", []):
        if hasattr(statue_target, 'alive') and statue_target.alive() and not getattr(statue_target, 'is_smashed', False):
            hittable_targets_for_projectiles.append(statue_target)

    projectiles_to_keep_this_frame = []
    for proj_instance in list(projectiles_list):
        if hasattr(proj_instance, 'update') and hasattr(proj_instance, 'alive') and proj_instance.alive():
            proj_instance.update(dt_sec, platforms_list_this_frame, hittable_targets_for_projectiles)
        if hasattr(proj_instance, 'alive') and proj_instance.alive():
            projectiles_to_keep_this_frame.append(proj_instance)
    game_elements_ref["projectiles_list"] = projectiles_to_keep_this_frame

    # Collectibles list (mainly for chest rendering)
    collectibles_to_keep = []
    if current_chest and current_chest.alive(): # Re-check current_chest as it might have been collected
        collectibles_to_keep.append(current_chest)
    game_elements_ref["collectible_list"] = collectibles_to_keep
    if not (current_chest and current_chest.alive()): # If chest was collected and killed
        game_elements_ref["current_chest"] = None
        current_chest = None # Update local ref for this frame

    if camera_obj:
        focus_targets_alive_couch = [p for p in player_instances_to_update if p and hasattr(p, 'alive') and p.alive() and not getattr(p, 'is_dead', True) and not getattr(p, 'is_petrified', False)]
        if focus_targets_alive_couch:
            focus_target_for_camera_couch = focus_targets_alive_couch[0]
            for p_idx_focus_couch in range(len(focus_targets_alive_couch)):
                current_p_for_cam_focus = focus_targets_alive_couch[p_idx_focus_couch]
                if current_p_for_cam_focus.player_id == 1: focus_target_for_camera_couch = current_p_for_cam_focus; break
                if current_p_for_cam_focus.player_id == 2 and focus_target_for_camera_couch.player_id != 1: focus_target_for_camera_couch = current_p_for_cam_focus
                elif current_p_for_cam_focus.player_id == 3 and focus_target_for_camera_couch.player_id not in [1,2]: focus_target_for_camera_couch = current_p_for_cam_focus
                elif current_p_for_cam_focus.player_id == 4 and focus_target_for_camera_couch.player_id not in [1,2,3]: focus_target_for_camera_couch = current_p_for_cam_focus
            camera_obj.update(focus_target_for_camera_couch)
        else: camera_obj.static_update()

    new_all_renderable_objects_couch = []
    for static_list_key_couch in ["background_tiles_list", "ladders_list", "hazards_list"]:
        for item_render_couch in game_elements_ref.get(static_list_key_couch, []):
             if item_render_couch not in new_all_renderable_objects_couch:
                new_all_renderable_objects_couch.append(item_render_couch)
    
    for platform_item_render_couch in game_elements_ref.get("platforms_list", []):
        if platform_item_render_couch not in new_all_renderable_objects_couch:
            new_all_renderable_objects_couch.append(platform_item_render_couch)

    for dynamic_list_key_couch in ["enemy_list", "statue_objects", "collectible_list", "projectiles_list"]:
        for item_render_couch_dyn in game_elements_ref.get(dynamic_list_key_couch, []):
            if item_render_couch_dyn not in new_all_renderable_objects_couch:
                 new_all_renderable_objects_couch.append(item_render_couch_dyn)
    
    for p_render_couch in player_instances_to_update:
        if p_render_couch and hasattr(p_render_couch, 'alive') and p_render_couch.alive() and \
           p_render_couch not in new_all_renderable_objects_couch:
            new_all_renderable_objects_couch.append(p_render_couch)
        elif p_render_couch and getattr(p_render_couch, 'is_dead', False) and \
             not getattr(p_render_couch, 'death_animation_finished', True) and \
             p_render_couch not in new_all_renderable_objects_couch:
            new_all_renderable_objects_couch.append(p_render_couch)

    game_elements_ref["all_renderable_objects"] = new_all_renderable_objects_couch

    def is_player_truly_gone_couch(p_instance_couch):
        if not p_instance_couch or not hasattr(p_instance_couch, '_valid_init') or not p_instance_couch._valid_init: return True
        if hasattr(p_instance_couch, 'alive') and p_instance_couch.alive():
            if getattr(p_instance_couch, 'is_dead', False):
                if getattr(p_instance_couch, 'is_petrified', False) and not getattr(p_instance_couch, 'is_stone_smashed', False):
                    return False
                elif not getattr(p_instance_couch, 'death_animation_finished', True):
                    return False
            else: return False
        return True
    
    active_player_instances_in_map_couch = [p for p in player_instances_to_update if p and hasattr(p, '_valid_init') and p._valid_init]
    
    if not active_player_instances_in_map_couch: return True
    
    all_active_players_are_gone_couch = True
    for p_active_inst_couch in active_player_instances_in_map_couch:
        if not is_player_truly_gone_couch(p_active_inst_couch):
            all_active_players_are_gone_couch = False
            break
    
    if all_active_players_are_gone_couch:
        if _SCRIPT_LOGGING_ENABLED: log_info(f"Couch Play: All {len(active_player_instances_in_map_couch)} active players are gone. Game Over.")
        if show_status_message_callback: show_status_message_callback(f"Game Over! All {len(active_player_instances_in_map_couch)} players defeated.")
        process_qt_events_callback()
        time.sleep(1.5)
        run_couch_play_mode._platform_debug_printed_couch = False
        return False

    return True