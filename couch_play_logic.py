########## START OF FILE: couch_play_logic.py ##########

# couch_play_logic.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.5 (Pass full enemy list to enemy.update)
Handles the game logic for the local couch co-op (two players on one machine) mode.
"""
import pygame
import traceback # For detailed error logging if needed

# --- Import Logger ---
try:
    from logger import info, debug, warning, error, critical
except ImportError:
    print("CRITICAL COUCH_PLAY_LOGIC: logger.py not found. Falling back to print statements for logging.")
    def info(msg): print(f"INFO: {msg}")
    def debug(msg): print(f"DEBUG: {msg}")
    def warning(msg): print(f"WARNING: {msg}")
    def error(msg): print(f"ERROR: {msg}")
    def critical(msg): print(f"CRITICAL: {msg}")
# --- End Logger ---

import constants as C
from game_state_manager import reset_game_state # For resetting the game
from enemy import Enemy # For potential type hinting
from items import Chest # For type checking if Chest is valid
from game_ui import draw_platformer_scene_on_surface # For drawing the game scene

def run_couch_play_mode(screen: pygame.Surface, clock: pygame.time.Clock,
                        fonts: dict, game_elements_ref: dict, app_status_obj):
    """
    Main loop for the couch co-op game mode.
    Manages input for two local players and updates the game state.

    Args:
        screen: The main Pygame display surface.
        clock: The Pygame clock for managing FPS.
        fonts: A dictionary of loaded Pygame font objects.
        game_elements_ref: A dictionary containing references to game objects
                           (players, sprite groups, camera, etc.).
        app_status_obj: An object (like main's AppStatus) with an 'app_running' attribute
                        to signal if the whole application should quit.
    """
    pygame.display.set_caption("Platformer - Couch Co-op (P1:WASD+VB, P2:IJKL+OP | Harm:H,N | Heal:G,M | Reset:Q)") # Updated caption
    current_width, current_height = screen.get_size()

    # Get player instances from the game_elements dictionary
    p1 = game_elements_ref.get("player1")
    p2 = game_elements_ref.get("player2")

    # Define key mappings for Player 1 and Player 2
    p1_key_map_config = {
        'left': pygame.K_a, 'right': pygame.K_d, 'up': pygame.K_w, 'down': pygame.K_s,
        'attack1': pygame.K_v, 'attack2': pygame.K_b, 'dash': pygame.K_LSHIFT,
        'roll': pygame.K_LCTRL, 'interact': pygame.K_e
    }
    p2_key_map_config = {
        'left': pygame.K_j, 'right': pygame.K_l, 'up': pygame.K_i, 'down': pygame.K_k,
        'attack1': pygame.K_o, 'attack2': pygame.K_p,
        'dash': pygame.K_SEMICOLON,
        'roll': pygame.K_QUOTE,
        'interact': pygame.K_BACKSLASH
    }

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

        if p1 and p1._valid_init and not p1.is_dead:
            if hasattr(p1, 'handle_mapped_input'):
                p1.handle_mapped_input(keys_pressed, pygame_events, p1_key_map_config)

        if p2 and p2._valid_init and not p2.is_dead:
            if hasattr(p2, 'handle_mapped_input'):
                p2.handle_mapped_input(keys_pressed, pygame_events, p2_key_map_config)

        if host_requested_reset_couch:
            info("Couch Play: Game state reset triggered by 'Q' key.")
            game_elements_ref["current_chest"] = reset_game_state(game_elements_ref)

        if p1 and p1._valid_init:
            other_players_for_p1_update = [char for char in [p2] if char and char._valid_init and char.alive() and char is not p1]
            p1.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"],
                      game_elements_ref["hazard_sprites"], other_players_for_p1_update, game_elements_ref["enemy_list"])

        if p2 and p2._valid_init:
            other_players_for_p2_update = [char for char in [p1] if char and char._valid_init and char.alive() and char is not p2]
            p2.update(dt_sec, game_elements_ref["platform_sprites"], game_elements_ref["ladder_sprites"],
                      game_elements_ref["hazard_sprites"], other_players_for_p2_update, game_elements_ref["enemy_list"])

        active_players_for_enemy_ai_couch = [char for char in [p1, p2] if char and char._valid_init and not char.is_dead and char.alive()]
        for enemy_couch in list(game_elements_ref.get("enemy_list", [])):
            if enemy_couch._valid_init:
                enemy_couch.update(dt_sec, active_players_for_enemy_ai_couch,
                                   game_elements_ref["platform_sprites"], 
                                   game_elements_ref["hazard_sprites"],
                                   game_elements_ref["enemy_list"]) # Pass full enemy_list
                if enemy_couch.is_dead and hasattr(enemy_couch, 'death_animation_finished') and \
                   enemy_couch.death_animation_finished and enemy_couch.alive():
                    debug(f"Couch Play: Auto-killing enemy {enemy_couch.enemy_id} as death anim finished.")
                    enemy_couch.kill()

        hittable_characters_couch_group = pygame.sprite.Group()
        if p1 and p1.alive() and p1._valid_init: hittable_characters_couch_group.add(p1)
        if p2 and p2.alive() and p2._valid_init: hittable_characters_couch_group.add(p2)
        for enemy_inst_proj_couch in game_elements_ref.get("enemy_list", []):
            if enemy_inst_proj_couch and enemy_inst_proj_couch.alive() and enemy_inst_proj_couch._valid_init:
                hittable_characters_couch_group.add(enemy_inst_proj_couch)
        game_elements_ref.get("projectile_sprites", pygame.sprite.Group()).update(
            dt_sec, game_elements_ref["platform_sprites"], hittable_characters_couch_group
        )

        game_elements_ref.get("collectible_sprites", pygame.sprite.Group()).update(dt_sec)
        couch_current_chest = game_elements_ref.get("current_chest")
        if Chest and couch_current_chest and couch_current_chest.alive():
            player_who_collected_chest_couch = None
            if p1 and p1._valid_init and not p1.is_dead and p1.alive() and \
               pygame.sprite.collide_rect(p1, couch_current_chest):
                player_who_collected_chest_couch = p1
            elif p2 and p2._valid_init and not p2.is_dead and p2.alive() and \
                 pygame.sprite.collide_rect(p2, couch_current_chest):
                player_who_collected_chest_couch = p2

            if player_who_collected_chest_couch:
                couch_current_chest.collect(player_who_collected_chest_couch)
                game_elements_ref["current_chest"] = None

        couch_camera = game_elements_ref.get("camera")
        if couch_camera:
            camera_focus_target_couch = None
            if p1 and p1.alive() and p1._valid_init and not p1.is_dead:
                camera_focus_target_couch = p1
            elif p2 and p2.alive() and p2._valid_init and not p2.is_dead:
                camera_focus_target_couch = p2

            if camera_focus_target_couch: couch_camera.update(camera_focus_target_couch)
            else: couch_camera.static_update()

        try:
            draw_platformer_scene_on_surface(screen, game_elements_ref, fonts, now_ticks_couch)
        except Exception as e_draw:
            error(f"Couch Play draw error: {e_draw}", exc_info=True)
            couch_game_active=False; break
        pygame.display.flip()

    info("Exiting Couch Play mode.")