########## START OF FILE: couch_play_logic.py ##########
# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.1.0 (Corrected Enemy.update() call for petrified enemies)
Handles the game logic for the local couch co-op (two players on one machine) mode.
"""
import pygame
import traceback

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
import game_ui # Changed import
import config as game_config
from statue import Statue # Import Statue

def run_couch_play_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                        fonts: dict, game_elements_ref: dict, app_status_obj):
    pygame.display.set_caption("Platformer - Couch Co-op (P1: Configured, P2: Configured | Harm:H,N | Heal:G,M | Reset:Q)")
    current_width, current_height = screen.get_size()

    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")

    p1_action_events = {}
    p2_action_events = {}

    couch_game_active = True
    while couch_game_active and app_status_obj.app_running:
        dt_sec = clock.tick(C.FPS) / 1000.0
        now_ticks_couch = pygame.time.get_ticks()

        pygame_events = pygame.event.get()
        keys_pressed = pygame.key.get_pressed()

        host_requested_reset_couch = False

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
                        game_elements_ref["camera"].screen_width = current_width
                        game_elements_ref["camera"].screen_height = current_height
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    couch_game_active = False
                    break
                if event.key == pygame.K_q:
                    host_requested_reset_couch = True

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

        if p1 and p1._valid_init and not p1.is_dead and hasattr(p1, 'process_input'):
            p1_action_events = p1.process_input(pygame_events, keys_pressed_override=keys_pressed)

        if p2 and p2._valid_init and not p2.is_dead:
            if hasattr(p2, 'process_input') and p2.control_scheme is not None:
                 p2_action_events = p2.process_input(pygame_events, keys_pressed_override=keys_pressed)
            elif hasattr(p2, 'handle_mapped_input'):
                 p2_key_map_config = game_config.DEFAULT_KEYBOARD_P1_MAPPINGS.copy() if p2.control_scheme == "keyboard_p1" \
                                     else game_config.DEFAULT_KEYBOARD_P2_MAPPINGS.copy()
                 temp_events = p2.handle_mapped_input(keys_pressed, pygame_events, p2_key_map_config)
                 p2_action_events = temp_events if temp_events is not None else {}


        if host_requested_reset_couch:
            info("Couch Play: Game state reset triggered by 'Q' key.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)
            if p1 and p1._valid_init and not p1.alive(): game_elements_ref["all_sprites"].add(p1)
            if p2 and p2._valid_init and not p2.alive(): game_elements_ref["all_sprites"].add(p2)


        if p1 and p1._valid_init:
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.game_elements_ref_for_projectiles = game_elements_ref
            p1.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"],
                      game_elements_ref["hazard_sprites"], other_players_for_p1_update, game_elements_ref["enemy_list"])

        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.game_elements_ref_for_projectiles = game_elements_ref
            p2.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"],
                      game_elements_ref["hazard_sprites"], other_players_for_p2_update, game_elements_ref["enemy_list"])

        active_players_for_enemy_ai_couch = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_couch in list(game_elements_ref.get("enemy_list", [])):
            if enemy_couch._valid_init:
                # Enemy.update() handles its own petrified state internally.
                # Always call it with the full set of arguments.
                enemy_couch.update(dt_sec, active_players_for_enemy_ai_couch,
                                   game_elements_ref["platform_sprites"],
                                   game_elements_ref["hazard_sprites"],
                                   game_elements_ref["enemy_list"])

                if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
                   enemy_couch.death_animation_finished and enemy_couch.alive():
                    debug(f"Couch Play: Auto-killing enemy {enemy_couch.enemy_id} as death anim finished.")
                    enemy_couch.kill()

        statue_objects = game_elements_ref.get("statue_objects", [])
        for statue in statue_objects:
            if hasattr(statue, 'update'):
                statue.update(dt_sec)


        hittable_characters_couch_group = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init and not getattr(p1, 'is_petrified', False): hittable_characters_couch_group.add(p1)
        if p2 and p2.alive() and p2._valid_init and not getattr(p2, 'is_petrified', False): hittable_characters_couch_group.add(p2)
        for enemy_inst_proj_couch in game_elements_ref.get("enemy_list", []):
            if enemy_inst_proj_couch and enemy_inst_proj_couch.alive() and enemy_inst_proj_couch._valid_init:
                hittable_characters_couch_group.add(enemy_inst_proj_couch)

        for statue in statue_objects:
            if statue.alive() and hasattr(statue, 'is_smashed') and not statue.is_smashed:
                hittable_characters_couch_group.add(statue)


        for proj in game_elements_ref.get("projectile_sprites", pygame.sprite.Group()):
            if hasattr(proj, 'game_elements_ref') and proj.game_elements_ref is None:
                proj.game_elements_ref = game_elements_ref
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(
            dt_sec, game_elements_ref["platform_sprites"], hittable_characters_couch_group
        )

        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)

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

        try:
            # Use game_ui.draw_platformer_scene_on_surface
            game_ui.draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_couch)
        except Exception as e_draw:
            error(f"Couch Play draw error: {e_draw}", exc_info=True)
            couch_game_active=False; break
        pygame.display.flip()

    info("Exiting Couch Play mode.")
########## END OF FILE: couch_play_logic.py ##########