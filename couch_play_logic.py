# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.2 (Reset/Pause events process even if player is dead)
Handles the game logic for the local couch co-op (two players on one machine) mode.
"""
import pygame
import traceback
from typing import Dict

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
import game_ui
import config as game_config
from statue import Statue # Import Statue

def run_couch_play_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                        fonts: dict, game_elements_ref: dict, app_status_obj):
    pygame.display.set_caption(f"Platformer - Couch Co-op (P1: {game_config.CURRENT_P1_INPUT_DEVICE}, P2: {game_config.CURRENT_P2_INPUT_DEVICE} | Reset: Mapped Keys / Q)")
    current_width, current_height = screen.get_size()

    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")

    couch_game_active = True
    while couch_game_active and app_status_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0
        now_ticks_couch = pygame.time.get_ticks()

        pygame_events = pygame.event.get()
        keys_pressed = pygame.key.get_pressed()

        # Flags for universal actions
        any_player_requested_reset = False
        any_player_requested_pause = False

        # --- Process Pygame Events for Global Actions (Escape, Q, debug keys) ---
        for event in pygame_events:
            if event.type == pygame.QUIT:
                couch_game_active = False
                app_status_obj.app_running = False
                break
            if event.type == pygame.VIDEORESIZE:
                if not screen.get_flags() & pygame.FULLSCREEN:
                    current_width, current_height = max(320,event.w), max(240,event.h)
                    screen = pygame.display.set_mode((current_width,current_height), pygame.RESIZABLE|pygame.DOUBLEBUF)
                    if game_elements_ref.get("camera"):
                        game_elements_ref["camera"].set_screen_dimensions(current_width, current_height)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: # K_ESCAPE still exits immediately
                    any_player_requested_pause = True # Treat ESC as a pause request to exit mode
                    info("Couch Play: Global ESC key pressed, treating as pause/exit mode.")
                    break
                if event.key == pygame.K_q: # Dev reset key
                    any_player_requested_reset = True
                    info("Couch Play: Dev 'Q' key reset triggered.")

                # Player-specific self-harm/heal debug keys
                if p1 and p1._valid_init:
                    if event.key == pygame.K_h and hasattr(p1, 'self_inflict_damage'):
                        p1.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_g and hasattr(p1, 'heal_to_full'):
                        p1.heal_to_full()
                if p2 and p2._valid_init:
                    if event.key == pygame.K_n and hasattr(p2, 'self_inflict_damage'):
                        p2.self_inflict_damage(C.PLAYER_SELF_DAMAGE)
                    if event.key == pygame.K_m and hasattr(p2, 'heal_to_full'):
                        p2.heal_to_full()
        
        if not app_status_obj.app_running or not couch_game_active: break
        if any_player_requested_pause: # If global ESC was pressed
            couch_game_active = False
            break

        # --- Process P1 input ---
        p1_action_events: Dict[str, bool] = {}
        if p1 and p1._valid_init and hasattr(p1, 'process_input'):
            # Call process_input regardless of p1.is_dead to capture universal events
            p1_action_events = p1.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed)
        
        # Check for universal events from P1
        if p1_action_events.get("pause"):
            any_player_requested_pause = True
            info("Couch Play: P1 pause action detected.")
        if p1_action_events.get("reset"):
            any_player_requested_reset = True
            info("Couch Play: P1 reset action detected.")
        
        if any_player_requested_pause: # Check if P1 paused
            couch_game_active = False; break


        # --- Process P2 input ---
        p2_action_events: Dict[str, bool] = {}
        if p2 and p2._valid_init and hasattr(p2, 'process_input') and p2.control_scheme is not None:
            # Call process_input regardless of p2.is_dead
            p2_action_events = p2.process_input(pygame_events, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), keys_pressed_override=keys_pressed)

        # Check for universal events from P2
        if p2_action_events.get("pause"):
            any_player_requested_pause = True
            info("Couch Play: P2 pause action detected.")
        if p2_action_events.get("reset"):
            any_player_requested_reset = True
            info("Couch Play: P2 reset action detected.")

        if any_player_requested_pause: # Check if P2 paused
            couch_game_active = False; break


        # --- Game Action Logic ---
        if any_player_requested_reset:
            info("Couch Play: Game state reset initiated.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            # Ensure players are re-added to sprite groups if they were killed then reset
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref.get("all_sprites", pygame.sprite.Group()).add(p2)

        # Update P1 (only if not fully dead for game actions, or needs death animation)
        if p1 and p1._valid_init: # Physics/animation update even if dead but anim not finished
            # Universal events (reset/pause) are already handled above.
            # p1.process_input was called above to get p1_action_events.
            # The player.update call handles physics, other animations, and game logic based on player state.
            # player.is_dead check inside player.update will gate most game actions.
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref
            p1.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                      other_players_for_p1_update,
                      game_elements_ref.get("enemy_list", []))

        # Update P2 (similarly)
        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("ladder_sprites", pygame.sprite.Group()),
                      game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                      other_players_for_p2_update,
                      game_elements_ref.get("enemy_list", []))

        # Update Enemies
        active_players_for_enemy_ai_couch = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_couch in list(game_elements_ref.get("enemy_list", [])):
            if enemy_couch._valid_init:
                enemy_couch.update(dt_sec, active_players_for_enemy_ai_couch,
                                   game_elements_ref.get("platform_sprites", pygame.sprite.Group()),
                                   game_elements_ref.get("hazard_sprites", pygame.sprite.Group()),
                                   game_elements_ref.get("enemy_list", []))
                if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
                   enemy_couch.death_animation_finished and enemy_couch.alive():
                    debug(f"Couch Play: Auto-killing enemy {enemy_couch.enemy_id} as death anim finished.")
                    enemy_couch.kill()

        # Update Statues
        statue_objects = game_elements_ref.get("statue_objects", [])
        for statue in statue_objects:
            if hasattr(statue, 'update'):
                statue.update(dt_sec)

        # Update Projectiles
        hittable_characters_couch_group = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_characters_couch_group.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_characters_couch_group.add(p2)
        for enemy_inst_proj_couch in game_elements_ref.get("enemy_list", []):
            if enemy_inst_proj_couch and enemy_inst_proj_couch.alive() and enemy_inst_proj_couch._valid_init and not getattr(enemy_inst_proj_couch, 'is_petrified', False):
                hittable_characters_couch_group.add(enemy_inst_proj_couch)
        for statue in statue_objects:
            if statue.alive() and hasattr(statue, 'is_smashed') and not statue.is_smashed:
                hittable_characters_couch_group.add(statue)
        for proj in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj, 'game_elements_ref') and proj.game_elements_ref is None:
                proj.game_elements_ref = game_elements_ref
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(
            dt_sec, game_elements_ref.get("platform_sprites", pygame.sprite.Group()), hittable_characters_couch_group
        )

        # Update Collectibles (Chests, etc.)
        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

        # Chest Interaction Logic (uses action_events from input processing)
        couch_current_chest = game_elements_ref.get("current_chest")
        if isinstance(couch_current_chest, Chest) and couch_current_chest.alive() and \
           not couch_current_chest.is_collected_flag_internal:
            player_who_interacted_with_chest = None
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and not getattr(p1, 'is_petrified', False) and \
               pygame.sprite.collide_rect(p1, couch_current_chest) and p1_action_events.get("interact", False):
                player_who_interacted_with_chest = p1
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and not getattr(p2, 'is_petrified', False) and \
                 pygame.sprite.collide_rect(p2, couch_current_chest) and p2_action_events.get("interact", False):
                player_who_interacted_with_chest = p2
            if player_who_interacted_with_chest:
                couch_current_chest.collect(player_who_interacted_with_chest)

        # Update Camera
        couch_camera = game_elements_ref.get("camera")
        if couch_camera:
            camera_focus_target_couch = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead and not getattr(p1, 'is_petrified', False):
                camera_focus_target_couch = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead and not getattr(p2, 'is_petrified', False):
                camera_focus_target_couch = p2
            elif p1 and p1.alive() and p1._valid_init and (p1.is_dead or getattr(p1, 'is_petrified', False)):
                 camera_focus_target_couch = p1
            elif p2 and p2.alive() and p2._valid_init and (p2.is_dead or getattr(p2, 'is_petrified', False)):
                 camera_focus_target_couch = p2
            if camera_focus_target_couch: couch_camera.update(camera_focus_target_couch)
            else: couch_camera.static_update()

        # Draw Scene
        try:
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_couch)
        except Exception as e_draw:
            error(f"Couch Play draw error: {e_draw}", exc_info=True)
            couch_game_active=False; break
        pygame.display.flip()

    info("Exiting Couch Play mode.")